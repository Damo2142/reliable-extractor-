"""
SBS Composition Engine — .pan Binary Compiler (Seed Format)

Builds .pan seed files matching RC Studio's minimal block format.
RC Studio populates all runtime properties when the file is opened.

CRC: CRC-16/KERMIT, init=0xF321, over block[12:] payload only.
TLV: [total_len 1B] [pad=0x00] [ctx_hi 1B] [ctx_lo 1B] [prop_id 1B] [tag 1B] [value...] [0x00 term]

Seed block format (from ground truth RC Studio reference file):
  AI/AO/AV:  desc + name + range=0x03
  BI:        desc + name + range=0x00
  BO:        desc + name + range=0x02
  BV:        desc + name + range=0x03
  MV:        states_as_desc + name + range=0x08
  LOOP:      action + deriv + bias + output + out_units + name + setpoint + p_band
  PRG:       desc + name (no bytecode)
  SCHED:     name only
  NC_GROUP:  copy from blank
  NOTIF_CLS: name + 0x0485=TRUE
  SYS_GROUP: desc + name
  DEVICE:    copy from blank
  TREND:     not written (RC Studio adds)
  ARRAY:     not written (RC Studio adds)
"""

import struct


# ============================================================
# CRC-16/KERMIT — init=0xF321, payload only
# ============================================================

def crc16_kermit(data: bytes, init: int = 0xF321) -> int:
    crc = init
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return crc


# ============================================================
# TLV Record Builders
# ============================================================

def _rec(ctx: int, prop: int, tag: int, val_data: bytes) -> bytes:
    """Build a TLV record: [len] [0x00] [ctx_hi] [ctx_lo] [prop] [tag] [val_data] [0x00].
    Length byte = total record size including itself.
    """
    body = bytes([0x00, (ctx >> 8) & 0xFF, ctx & 0xFF, prop, tag]) + val_data + b'\x00'
    total_len = (1 + len(body)) & 0xFF  # wraps for large records (e.g. PRG bytecode)
    return bytes([total_len]) + body


def _rec_desc(desc: str) -> bytes:
    """Description property: ctx=0x0000, prop=0x1C, tag=0x75."""
    s = desc.encode('utf-8')
    return _rec(0x0000, 0x1C, 0x75, bytes([len(s) + 1, 0x00]) + s)


def _rec_mu(name: str) -> bytes:
    """Mu name property: ctx=0x0000, prop=0x4D, tag=0x75."""
    s = name.encode('latin-1', errors='replace')
    return _rec(0x0000, 0x4D, 0x75, bytes([len(s) + 1, 0x00]) + s)


def _rec_range(code: int) -> bytes:
    """Vendor range code: ctx=0x0004, prop=0x1D, tag=0x91."""
    return _rec(0x0004, 0x1D, 0x91, bytes([code & 0xFF]))


def _rec_uint8(ctx: int, prop: int, tag: int, val: int) -> bytes:
    """Generic uint8 record."""
    return _rec(ctx, prop, tag, bytes([val & 0xFF]))


def _rec_float(ctx: int, prop: int, val: float) -> bytes:
    """Generic float record: tag=0x44."""
    return _rec(ctx, prop, 0x44, struct.pack('>f', val))


def _rec_bool_true(ctx: int, prop: int) -> bytes:
    """Bool TRUE record: tag=0x11."""
    return _rec(ctx, prop, 0x11, b'')


def _rec_bool_false(ctx: int, prop: int) -> bytes:
    """Bool FALSE record: tag=0x10."""
    return _rec(ctx, prop, 0x10, b'')


def _rec_enum(ctx: int, prop: int, val: int) -> bytes:
    """Enum record: tag=0x71."""
    return _rec(ctx, prop, 0x71, bytes([val & 0xFF]))


def _rec_uint16(ctx: int, prop: int, val: int) -> bytes:
    """uint16 BE record: tag=0x22."""
    return _rec(ctx, prop, 0x22, struct.pack('>H', val))


def _rec_datetime(ctx: int, prop: int, dt_bytes: bytes) -> bytes:
    """Datetime record: tag=0xA4."""
    return _rec(ctx, prop, 0xA4, dt_bytes)


def _rec_complex(ctx: int, prop: int, raw: bytes) -> bytes:
    """Complex/constructed record: tag=0x82."""
    return _rec(ctx, prop, 0x82, raw)


def _rec_objref(ctx: int, prop: int, type_id: int, instance: int, prop_id: int = 0x55) -> bytes:
    """Object property reference: tag=0x0C, [ObjID 4B BE] [0x19] [prop_id]."""
    objid = (type_id << 22) | (instance & 0x3FFFFF)
    return _rec(ctx, prop, 0x0C, struct.pack('>I', objid) + bytes([0x19, prop_id]))


# ============================================================
# Block Header + CRC
# ============================================================

def _build_block(type_id: int, instance: int, payload: bytes) -> bytes:
    """Build complete block: [header 12B] + [payload], with CRC."""
    size = 10 + len(payload)
    header = bytearray(12)
    struct.pack_into('<H', header, 0, size)
    struct.pack_into('>H', header, 4, size)
    objid = (type_id << 22) | (instance & 0x3FFFFF)
    struct.pack_into('>I', header, 6, objid)
    crc = crc16_kermit(payload)
    struct.pack_into('>H', header, 10, crc)
    return bytes(header) + payload


def write_empty_block(type_id: int, instance: int) -> bytes:
    """Empty filler block — header + minimal payload, no properties."""
    payload = b'\x00\x00\x00'
    return _build_block(type_id, instance, payload)


def _rec_last(ctx: int, prop: int, tag: int, val_data: bytes) -> bytes:
    """Build a TLV record WITHOUT trailing 0x00 — for the last record in a block."""
    body = bytes([0x00, (ctx >> 8) & 0xFF, ctx & 0xFF, prop, tag]) + val_data
    total_len = (1 + len(body) + 1) & 0xFF  # len includes the missing terminator
    return bytes([total_len]) + body


def _seed_payload(records: list) -> bytes:
    """Build payload from list of record bytes.
    All records except the last have terminators (from _rec).
    The last record must be built with _rec_last (no terminator) OR
    we rebuild it here by stripping the terminator from the last _rec output.
    """
    if not records:
        return b'\x00\x00\x00'
    payload = bytearray(b'\x00\x00\x00')
    # Add all records except last normally
    for rec in records[:-1]:
        payload += rec
    # Last record: strip the trailing 0x00 terminator that _rec adds
    last = records[-1]
    if last[-1] == 0x00:
        payload += last[:-1]
    else:
        payload += last
    return bytes(payload)


# ============================================================
# SEED BLOCK WRITERS
# ============================================================

def write_av_seed(instance: int, name: str, desc: str, units: int = 95,
                  present_value: float = 0.0) -> bytes:
    """AV seed: desc + name + present-value + units + range=0x03."""
    return _build_block(2, instance, _seed_payload([
        _rec_desc(desc), _rec_mu(name),
        _rec_float(0x0000, 0x55, present_value),
        _rec_uint8(0x0000, 0x75, 0x91, units),
        _rec_range(0x03)
    ]))


def _rec_priority_array_av(present_value: float) -> bytes:
    """AV priority array (prop 0x57): 8 zero bytes + float tag + float + 6 zero bytes."""
    val = (b'\x00' * 8 +
           b'\x44' + struct.pack('>f', present_value) +
           b'\x00' * 6)
    # Tag 0x00, raw bytes — no trailing 0x00 from _rec (already has zeros)
    return _rec(0x0000, 0x57, 0x00, val)


def write_av_block(instance: int, name: str, present_value: float = 0.0,
                   units: int = 95, range_code: int = 0,
                   desc: str = '') -> bytes:
    """Fully populated AV block — 21 properties matching production A201.pan format.
    units: BACnet engineering units enum (64=°F, 98=%, 95=no-units, etc.)
    range_code: vendor range code (0x041D).
    desc: description string (empty = enum 0).
    """
    # Description: string if provided, else enum(0)
    if desc:
        desc_rec = _rec_desc(desc)
    else:
        desc_rec = _rec_enum(0x0000, 0x1C, 0x00)

    return _build_block(2, instance, _seed_payload([
        _rec_uint8(0x0000, 0x11, 0x21, 0x01),              # buffer-size = 1
        _rec_float(0x0000, 0x16, 0.1),                      # increment = 0.1
        _rec_float(0x0000, 0x19, 0.0),                      # deadband = 0.0
        desc_rec,                                             # description
        _rec_complex(0x0000, 0x23, bytes([0x05, 0x00])),    # event-state
        _rec_float(0x0000, 0x2D, 1000.0),                   # max-value = 1000
        _rec_complex(0x0000, 0x34, bytes([0x06, 0xC0])),    # alarm config
        _rec_float(0x0000, 0x3B, -1000.0),                  # min-value = -1000
        _rec_uint8(0x0000, 0x48, 0x91, 0x00),               # logging-type = 0
        _rec_mu(name),                                        # object-name
        _rec_bool_false(0x0000, 0x51),                       # out-of-service = FALSE
        _rec_float(0x0000, 0x55, present_value),             # present-value
        _rec_priority_array_av(present_value),                # priority-array
        _rec_float(0x0000, 0x68, 0.0),                      # relinquish-default = 0
        _rec_uint8(0x0000, 0x71, 0x21, 0x00),               # status-flags = 0
        _rec_uint8(0x0000, 0x75, 0x91, units),              # units
        _rec(0x0001, 0x60, 0x71,                               # vendor-status: 3 chained enums
             bytes([0x00, 0x71, 0x00, 0x71, 0x00])),
        _rec_bool_true(0x0001, 0x61),                        # vendor-flag1
        _rec_bool_false(0x0001, 0x62),                       # vendor-flag2
        _rec_uint8(0x0001, 0x64, 0x21, 0x00),               # vendor-zero
        _rec_uint8(0x0004, 0x1D, 0x91, range_code),         # vendor range
    ]))


def write_ai_seed(instance: int, name: str, desc: str, units: int = 95) -> bytes:
    """AI seed: desc + name + units + range=0x03."""
    return _build_block(0, instance, _seed_payload([
        _rec_desc(desc), _rec_mu(name),
        _rec_uint8(0x0000, 0x75, 0x91, units),
        _rec_range(0x03)
    ]))


def write_ai_block(instance: int, name: str, present_value: float = 0.0,
                   units: int = 95, range_code: int = 3,
                   desc: str = '') -> bytes:
    """Fully populated AI block — 23 properties matching production A201.pan format."""
    if desc:
        desc_rec = _rec_desc(desc)
    else:
        desc_rec = _rec_enum(0x0000, 0x1C, 0x00)

    return _build_block(0, instance, _seed_payload([
        _rec_uint8(0x0000, 0x11, 0x21, 0x01),              # buffer-size = 1
        _rec_float(0x0000, 0x16, 0.1),                      # increment = 0.1
        _rec_float(0x0000, 0x19, 0.0),                      # deadband = 0.0
        desc_rec,                                             # description
        _rec_complex(0x0000, 0x23, bytes([0x05, 0x00])),    # event-state
        _rec_float(0x0000, 0x2D, 1000.0),                   # max-value
        _rec_complex(0x0000, 0x34, bytes([0x06, 0xC0])),    # alarm config
        _rec_float(0x0000, 0x3B, -1000.0),                  # min-value
        _rec_uint8(0x0000, 0x48, 0x91, 0x00),               # logging-type = 0
        _rec_mu(name),                                        # object-name
        _rec_bool_false(0x0000, 0x51),                       # out-of-service = FALSE
        _rec_float(0x0000, 0x55, present_value),             # present-value
        _rec_uint8(0x0000, 0x71, 0x21, 0x00),               # status-flags = 0
        _rec_uint8(0x0000, 0x75, 0x91, units),              # units
        _rec(0x0001, 0x60, 0x71,                             # vendor-status: 3 chained enums
             bytes([0x00, 0x71, 0x00, 0x71, 0x00])),
        _rec_bool_true(0x0001, 0x61),                        # vendor-flag1
        _rec_bool_false(0x0001, 0x62),                       # vendor-flag2
        _rec_uint8(0x0001, 0x64, 0x21, 0x00),               # vendor-zero
        _rec_uint8(0x0004, 0x1D, 0x91, range_code),         # vendor range
        _rec_bool_false(0x0004, 0x1E),                       # vendor-config1
        _rec_float(0x0004, 0x1F, 0.0),                      # vendor-config2
        _rec_uint8(0x0004, 0x20, 0x21, 0x00),               # vendor-config3
        _rec_uint8(0x0005, 0x3B, 0x21, 30),                 # vendor-update-interval
    ]))


def write_ao_seed(instance: int, name: str, desc: str, units: int = 98) -> bytes:
    """AO seed: desc + name + units + range=0x03."""
    return _build_block(1, instance, _seed_payload([
        _rec_desc(desc), _rec_mu(name),
        _rec_uint8(0x0000, 0x75, 0x91, units),
        _rec_range(0x03)
    ]))


def write_ao_block(instance: int, name: str, present_value: float = 0.0,
                   units: int = 98, range_code: int = 3,
                   min_v: float = 2.0, max_v: float = 10.0, desc: str = '') -> bytes:
    """Fully populated AO block — 24 properties matching A201.pan."""
    if desc:
        desc_rec = _rec_desc(desc)
    else:
        desc_rec = _rec_enum(0x0000, 0x1C, 0x00)
    return _build_block(1, instance, _seed_payload([
        _rec_uint8(0x0000, 0x11, 0x21, 0x01),
        _rec_float(0x0000, 0x16, 0.1),
        _rec_float(0x0000, 0x19, 0.0),
        desc_rec,
        _rec_complex(0x0000, 0x23, bytes([0x05, 0x00])),
        _rec_float(0x0000, 0x2D, 1000.0),                   # max-value
        _rec_complex(0x0000, 0x34, bytes([0x06, 0xC0])),
        _rec_float(0x0000, 0x3B, -1000.0),                  # min-value
        _rec_uint8(0x0000, 0x48, 0x91, 0x00),
        _rec_mu(name),
        _rec_bool_false(0x0000, 0x51),                       # out-of-service
        _rec_float(0x0000, 0x55, present_value),
        _rec_priority_array_av(present_value),               # same format as AV
        _rec_float(0x0000, 0x68, 0.0),                      # relinquish-default
        _rec_uint8(0x0000, 0x71, 0x21, 0x00),
        _rec_uint8(0x0000, 0x75, 0x91, units),
        _rec(0x0001, 0x60, 0x71, bytes([0x00, 0x71, 0x00, 0x71, 0x00])),
        _rec_bool_true(0x0001, 0x61),
        _rec_bool_false(0x0001, 0x62),
        _rec_uint8(0x0001, 0x64, 0x21, 0x00),
        _rec_uint8(0x0004, 0x1D, 0x91, range_code),
        _rec_bool_false(0x0004, 0x1E),
        _rec_float(0x0004, 0x22, min_v),                    # min voltage
        _rec_float(0x0004, 0x23, max_v),                    # max voltage
    ]))


def write_bi_seed(instance: int, name: str, desc: str) -> bytes:
    """BI seed: desc + name + range=0x00."""
    return _build_block(3, instance, _seed_payload([
        _rec_desc(desc), _rec_mu(name), _rec_range(0x00)
    ]))


def _bi_vendor_status_default() -> bytes:
    """BI vendor-status: default = 3 chained enums (same as AV/AI)."""
    return _rec(0x0001, 0x60, 0x71, bytes([0x00, 0x71, 0x00, 0x71, 0x00]))


def write_bi_block(instance: int, name: str, present_value: int = 0,
                   range_code: int = 0, desc: str = '') -> bytes:
    """Fully populated BI block — 21 properties matching A201.pan."""
    if desc:
        desc_rec = _rec_desc(desc)
    else:
        desc_rec = _rec_enum(0x0000, 0x1C, 0x00)
    return _build_block(3, instance, _seed_payload([
        _rec_uint8(0x0000, 0x06, 0x91, 0x01),
        _rec_uint16(0x0000, 0x0F, 0),
        _rec_uint8(0x0000, 0x11, 0x21, 0x01),
        desc_rec,
        _rec(0x0000, 0x21, 0x23, bytes([0x00, 0x00, 0x00])),   # alarm-values (fresh)
        _rec_complex(0x0000, 0x23, bytes([0x05, 0x00])),
        _rec_uint8(0x0000, 0x48, 0x91, 0x00),
        _rec_mu(name),
        _rec_bool_false(0x0000, 0x51),
        _rec_uint8(0x0000, 0x54, 0x91, present_value),       # present-value
        _rec_uint8(0x0000, 0x55, 0x91, present_value),       # present-value (dup)
        _rec_uint8(0x0000, 0x71, 0x21, 0x00),
        _rec_datetime(0x0000, 0x73, _DT_WILDCARD),           # change-of-state-time
        _bi_vendor_status_default(),
        _rec_bool_true(0x0001, 0x61),
        _rec_bool_false(0x0001, 0x62),
        _rec_uint8(0x0001, 0x64, 0x21, 0x00),
        _rec_uint8(0x0004, 0x1D, 0x91, range_code),
        _rec_bool_false(0x0004, 0x1E),
        _rec_bool_true(0x0004, 0x3B),                        # vendor min-active
        _rec_uint8(0x0004, 0x58, 0x21, 100),                 # vendor-debounce
    ]))


def write_bo_seed(instance: int, name: str, desc: str) -> bytes:
    """BO seed: desc + name + range=0x02."""
    return _build_block(4, instance, _seed_payload([
        _rec_desc(desc), _rec_mu(name), _rec_range(0x02)
    ]))


def _priority_array_binary(present_value: int = 0) -> bytes:
    """BO/BV priority array: 8 zeros + [0x91] [val] + 6 zeros = 16 bytes."""
    val = (b'\x00' * 8 + bytes([0x91, present_value & 0xFF]) + b'\x00' * 6)
    return _rec(0x0000, 0x57, 0x00, val)


def write_bo_block(instance: int, name: str, present_value: int = 0,
                   range_code: int = 2, desc: str = '') -> bytes:
    """Fully populated BO block — 25 properties matching A201.pan."""
    if desc:
        desc_rec = _rec_desc(desc)
    else:
        desc_rec = _rec_enum(0x0000, 0x1C, 0x00)
    return _build_block(4, instance, _seed_payload([
        _rec_uint16(0x0000, 0x0F, 0),
        _rec_uint8(0x0000, 0x11, 0x21, 0x01),
        desc_rec,
        _rec(0x0000, 0x21, 0x23, bytes([0x00, 0x00, 0x00])),   # alarm-values (fresh)
        _rec_complex(0x0000, 0x23, bytes([0x05, 0x00])),
        _rec_uint8(0x0000, 0x42, 0x21, 0x00),               # feedback-value
        _rec_uint8(0x0000, 0x43, 0x21, 0x00),               # feedback-value2
        _rec_uint8(0x0000, 0x48, 0x91, 0x00),
        _rec_mu(name),
        _rec_bool_false(0x0000, 0x51),
        _rec_uint8(0x0000, 0x54, 0x91, present_value),
        _rec_uint8(0x0000, 0x55, 0x91, present_value),
        _priority_array_binary(present_value),
        _rec_uint8(0x0000, 0x68, 0x91, 0x00),               # relinquish-default
        _rec_uint8(0x0000, 0x71, 0x21, 0x00),
        _rec_datetime(0x0000, 0x73, _DT_WILDCARD),
        _rec(0x0001, 0x60, 0x71, bytes([0x00, 0x71, 0x00, 0x71, 0x00])),
        _rec_bool_true(0x0001, 0x61),
        _rec_bool_false(0x0001, 0x62),
        _rec_uint8(0x0001, 0x64, 0x21, 0x00),
        _rec(0x0004, 0x13, 0xC4, bytes([0xFF, 0xFF, 0xFF, 0xFF])),  # vendor feedback-ref
        _rec_uint8(0x0004, 0x1D, 0x91, range_code),
        _rec_bool_false(0x0004, 0x1E),
        _rec_bool_true(0x0004, 0x3B),
        _rec_uint8(0x0004, 0x58, 0x21, 100),
    ]))


def write_bv_seed(instance: int, name: str, desc: str,
                  present_value: int = 0, range_code: int = 0x00) -> bytes:
    """BV seed: desc + name + present-value + range. Default 0x00 = Off/On."""
    return _build_block(5, instance, _seed_payload([
        _rec_desc(desc), _rec_mu(name),
        _rec_uint8(0x0000, 0x55, 0x91, present_value),
        _rec_range(range_code)
    ]))


def write_bv_block(instance: int, name: str, present_value: int = 0,
                   range_code: int = 0, units: int = 95, desc: str = '') -> bytes:
    """Fully populated BV block — 23 properties matching A201.pan BV22 pattern."""
    if desc:
        desc_rec = _rec_desc(desc)
    else:
        desc_rec = _rec_enum(0x0000, 0x1C, 0x00)
    return _build_block(5, instance, _seed_payload([
        _rec_uint8(0x0000, 0x06, 0x91, 0x01),
        _rec_uint8(0x0000, 0x0F, 0x21, 0x00),
        _rec_uint8(0x0000, 0x11, 0x21, 0x01),
        desc_rec,
        _rec(0x0000, 0x21, 0x23, bytes([0x00, 0x00, 0x00])),   # alarm-values (fresh)
        _rec_complex(0x0000, 0x23, bytes([0x05, 0x00])),
        _rec_uint8(0x0000, 0x42, 0x21, 0x00),
        _rec_uint8(0x0000, 0x43, 0x21, 0x00),
        _rec_uint8(0x0000, 0x48, 0x91, 0x00),
        _rec_mu(name),
        _rec_bool_false(0x0000, 0x51),
        _rec_uint8(0x0000, 0x55, 0x91, present_value),
        _priority_array_binary(present_value),
        _rec_uint8(0x0000, 0x68, 0x91, 0x00),               # relinquish-default
        _rec_uint8(0x0000, 0x71, 0x21, 0x00),
        _rec_datetime(0x0000, 0x73, _DT_WILDCARD),
        _rec(0x0001, 0x60, 0x71, bytes([0x00, 0x71, 0x00, 0x71, 0x00])),
        _rec_bool_true(0x0001, 0x61),
        _rec_bool_false(0x0001, 0x62),
        _rec_uint8(0x0001, 0x64, 0x21, 0x00),
        _rec_uint8(0x0004, 0x1D, 0x91, range_code),
        _rec_bool_true(0x0004, 0x3B),
        _rec_uint8(0x0004, 0x58, 0x21, 100),
    ]))


def write_mv_seed(instance: int, name: str, states_desc: str) -> bytes:
    """MV seed: states_as_desc + name + range=0x08."""
    return _build_block(19, instance, _seed_payload([
        _rec_desc(states_desc), _rec_mu(name), _rec_range(0x08)
    ]))


def _priority_array_mv(present_value: int) -> bytes:
    """MV priority array: 8 zeros + [0x21] [val] + 6 zeros = 16 bytes."""
    val = (b'\x00' * 8 + bytes([0x21, present_value & 0xFF]) + b'\x00' * 6)
    return _rec(0x0000, 0x57, 0x00, val)


def _build_mv_state_text(states_desc: str) -> bytes:
    """Build MV state-text (prop 0x6E) from states description string.
    Input: "1-Ventilation/2-Cool/3-Reheat/4-Heat/5-Initialize"
    Output: chained string records [len 00 text] [75 len 00 text] ...
    Short names (<=3 chars) use tag 0x74 instead of 0x75.
    """
    parts = states_desc.split('/')
    state_names = []
    for part in parts:
        # Parse "1-Ventilation" → "Ventilation"
        part = part.strip()
        if '-' in part:
            state_names.append(part.split('-', 1)[1])
        else:
            state_names.append(part)

    result = bytearray()
    for i, sn in enumerate(state_names):
        s = sn.encode('ascii', errors='replace')
        if i == 0:
            # First: [len+1] [00] [text]
            result += bytes([len(s) + 1, 0x00]) + s
        else:
            # Subsequent: [75 len+1 00 text] or [74 00 text] for short
            if len(s) <= 3:
                result += bytes([0x74, 0x00]) + s
            else:
                result += bytes([0x75, len(s) + 1, 0x00]) + s
    return bytes(result)


def write_mv_block(instance: int, name: str, states_desc: str,
                   present_value: int = 1, range_code: int = 16) -> bytes:
    """Fully populated MV block — 17 properties matching A201.pan."""
    state_text_data = _build_mv_state_text(states_desc)

    return _build_block(19, instance, _seed_payload([
        _rec_uint8(0x0000, 0x11, 0x21, 0x01),
        _rec_desc(states_desc),                              # states in description
        _rec_complex(0x0000, 0x23, bytes([0x05, 0x00])),
        _rec_uint8(0x0000, 0x48, 0x91, 0x00),
        _rec_mu(name),
        _rec_bool_false(0x0000, 0x51),
        _rec_uint8(0x0000, 0x55, 0x21, present_value),      # present-value (uint8)
        _priority_array_mv(present_value),
        _rec_uint8(0x0000, 0x68, 0x21, 0x01),               # relinquish-default = 1
        _rec(0x0000, 0x6E, 0x75, state_text_data),           # state-text (all names)
        _rec_uint8(0x0000, 0x71, 0x21, 0x00),
        _rec(0x0001, 0x60, 0x71, bytes([0x00, 0x71, 0x00, 0x71, 0x00])),
        _rec_bool_true(0x0001, 0x61),
        _rec_bool_false(0x0001, 0x62),
        _rec_uint8(0x0001, 0x64, 0x21, 0x00),
        _rec(0x0004, 0x19, 0x0C,                             # vendor: null obj ref (MV format)
             bytes([0xFF, 0xFF, 0xFF, 0xFF, 0x1B, 0x3F, 0xFF, 0xFF])),
        _rec_uint8(0x0004, 0x1D, 0x91, range_code),
    ]))


def write_loop_seed(instance: int, name: str, action: str,
                    p_band: float, setpoint: float = 0.0,
                    derivative: float = 0.0,
                    input_type: int = 0x3FF, input_inst: int = 0x3FFFFF,
                    sp_type: int = 0x3FF, sp_inst: int = 0x3FFFFF,
                    out_type: int = 0x3FF, out_inst: int = 0x3FFFFF,
                    desc: str = '') -> bytes:
    """LOOP seed with input/setpoint/output ObjID references."""
    action_val = 0x00 if action == "-" else 0x01
    sp_objid = (sp_type << 22) | (sp_inst & 0x3FFFFF)
    sp_ref_data = bytes([0x0C]) + struct.pack('>I', sp_objid) + bytes([0x19, 0x55, 0x0F])
    desc_rec = _rec_desc(desc) if desc else _rec_enum(0x0000, 0x1C, 0x00)
    return _build_block(12, instance, _seed_payload([
        _rec_uint8(0x0000, 0x02, 0x91, action_val),
        _rec_float(0x0000, 0x0E, derivative),
        _rec_objref(0x0000, 0x13, input_type, input_inst),   # input ref
        desc_rec,                                              # description
        _rec_float(0x0000, 0x1A, 0.0),                       # bias
        _rec_float(0x0000, 0x31, 0.0),                       # output
        _rec_uint8(0x0000, 0x32, 0x91, 0x48),                # output-units
        _rec_objref(0x0000, 0x3C, out_type, out_inst),        # output/manip-var ref
        _rec_mu(name),
        _rec_float(0x0000, 0x5D, setpoint),                   # p-band value
        _rec(0x0000, 0x6D, 0x0E, sp_ref_data),                # setpoint ref
        _rec_float(0x0004, 0x4D, p_band),                     # integral value
    ]))


def write_loop_block(instance: int, name: str, action: int,
                     input_type: int, input_inst: int,
                     sp_type: int = 0x3FF, sp_inst: int = 0x3FFFFF,
                     out_type: int = 0x3FF, out_inst: int = 0x3FFFFF,
                     setpoint: float = 0.0, output: float = 0.0,
                     p_band: float = 2.0, integral: float = 0.0,
                     derivative: float = 0.0, bias: float = 0.0,
                     output_units: int = 71, input_units: int = 95,
                     setpoint_units: int = 95, desc: str = '') -> bytes:
    """Fully populated LOOP block — 30 properties matching A201.pan.
    action: 0=reverse(-), 1=direct(+).
    input_type/input_inst: BACnet type+instance of input point.
    sp_type/sp_inst: BACnet type+instance of setpoint point (default=null).
    """
    sp_objid = (sp_type << 22) | (sp_inst & 0x3FFFFF)
    if desc:
        desc_rec = _rec_desc(desc)
    else:
        desc_rec = _rec_enum(0x0000, 0x1C, 0x00)
    return _build_block(12, instance, _seed_payload([
        _rec_uint8(0x0000, 0x02, 0x91, action),             # action
        _rec_float(0x0000, 0x0E, derivative),                # derivative
        _rec_uint8(0x0000, 0x11, 0x21, 0x01),
        _rec_objref(0x0000, 0x13, input_type, input_inst),   # controlled-var-ref (input)
        _rec_float(0x0000, 0x16, 0.0),                      # increment
        _rec_float(0x0000, 0x19, 0.0),                      # deadband
        _rec_float(0x0000, 0x1A, bias),                      # bias
        _rec_uint8(0x0000, 0x1B, 0x91, input_units),         # input-units
        desc_rec,
        _rec_float(0x0000, 0x22, 1000.0),                   # max-output
        _rec_complex(0x0000, 0x23, bytes([0x05, 0x00])),
        _rec_float(0x0000, 0x31, output),                    # output
        _rec_uint8(0x0000, 0x32, 0x91, output_units),        # output-units
        _rec_objref(0x0000, 0x3C, out_type, out_inst),        # manipulated-var-ref (output)
        _rec_uint8(0x0000, 0x48, 0x91, 0x00),
        _rec_mu(name),
        _rec_bool_false(0x0000, 0x51),
        _rec_uint8(0x0000, 0x52, 0x91, 98),                 # output-units-display (%)
        _rec_float(0x0000, 0x55, output),                    # present-value = output
        _rec_uint8(0x0000, 0x58, 0x21, 10),                  # update-interval
        _rec_float(0x0000, 0x5D, setpoint),                  # setpoint
        _rec_uint8(0x0000, 0x5E, 0x91, setpoint_units),     # setpoint-units
        _rec_float(0x0000, 0x6C, integral),                  # integral
        _rec(0x0000, 0x6D, 0x0E,                             # setpoint-ref
             bytes([0x0C]) + struct.pack('>I', sp_objid) +
             bytes([0x19, 0x55, 0x0F])),
        _rec_uint8(0x0000, 0x71, 0x21, 0x00),
        _rec(0x0001, 0x60, 0x71, bytes([0x00, 0x71, 0x00, 0x71, 0x00])),
        _rec_bool_true(0x0001, 0x61),
        _rec_bool_false(0x0001, 0x62),
        _rec_uint8(0x0001, 0x64, 0x21, 0x00),
        _rec_float(0x0004, 0x4D, p_band),                   # vendor p-band
    ]))


def write_prg_seed(instance: int, name: str, desc: str) -> bytes:
    """PRG seed: desc + name. No bytecode."""
    return _build_block(16, instance, _seed_payload([
        _rec_desc(desc), _rec_mu(name)
    ]))


def write_prg_block(instance: int, name: str, bytecode: bytes,
                    enabled: int = 1, desc: str = '') -> bytes:
    """Fully populated PRG block with compiled bytecode."""
    # Append FF end-of-program marker if not already present
    if bytecode and bytecode[-1] == 0xFF:
        full_bc = bytecode
    else:
        full_bc = bytecode + b'\xFF'

    # Build 5-byte FE header: [FE] [size_hi] [size_lo] [checksum] [size_hi]
    bc_size = len(full_bc)
    size_hi = (bc_size >> 8) & 0xFF
    size_lo = bc_size & 0xFF
    chk = 0x00
    fe_header = bytes([0xFE, size_hi, size_lo, chk, size_hi])

    # Bytecode record: ctx=0x0004, prop=0x29, tag=0x65
    bc_blob = fe_header + full_bc
    bc_rec = _rec(0x0004, 0x29, 0x65, bc_blob)

    # Two vendor tail properties (consistent across all production PRG blocks):
    #   0x0441 = FALSE (runtime program status)
    #   0x0540 = 20000 (execution interval in ms)
    tail_0441 = _rec_bool_false(0x0004, 0x41)
    tail_0540 = _rec_uint16(0x0005, 0x40, 20000)

    return _build_block(16, instance, _seed_payload([
        _rec_desc(desc) if desc else _rec_enum(0x0000, 0x1C, 0x00),
        _rec_mu(name),                                # object-name
        _rec_uint8(0x0004, 0x0A, 0x91, enabled),     # program-enabled
        bc_rec,                                        # bytecode
        tail_0441,                                     # vendor: program status
        tail_0540,                                     # vendor: exec interval
    ]))


def write_sched_seed(instance: int, name: str) -> bytes:
    """SCHED seed: name only."""
    return _build_block(17, instance, _seed_payload([
        _rec_mu(name)
    ]))


def _build_weekly_schedule(entries_per_day=None, default_state: int = 0) -> bytes:
    """Build weekly-schedule (prop 0x7B) binary data.
    entries_per_day: list of 7 lists, each containing (hour, minute, state) tuples.
    If None, builds default Mon-Fri 6:05-18:00 occupied, Sat-Sun unoccupied.
    """
    if entries_per_day is None:
        weekday = [(0, 0, 0), (6, 5, 1), (18, 0, 0)]  # midnight→unocc, 6:05→occ, 18:00→unocc
        weekend = [(0, 0, 0)]  # all day unoccupied
        entries_per_day = [weekday]*5 + [weekend]*2

    result = bytearray()
    for i, day_entries in enumerate(entries_per_day):
        for hh, mm, state in day_entries:
            result += bytes([0xB4, hh, mm, 0x00, 0x00, 0x91, state])
        if i < len(entries_per_day) - 1:
            result += bytes([0x0F, 0x0E])  # end of day (not after last day)
        else:
            result += bytes([0x0F])          # last day: 0F only, no trailing 0E
    return bytes(result)


def write_sched_block(instance: int, name: str, default_state: int = 0,
                      range_code: int = 17,
                      weekly_data: bytes = None) -> bytes:
    """Fully populated SCHED block — 9 properties matching A201.pan."""
    if weekly_data is None:
        weekly_data = _build_weekly_schedule(default_state=default_state)

    _DT_WILDCARD_A4 = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xA4, 0xFF, 0xFF, 0xFF, 0xFF])
    return _build_block(17, instance, _seed_payload([
        _rec_enum(0x0000, 0x1C, 0x00),                      # description
        _rec_datetime(0x0000, 0x20, _DT_WILDCARD_A4),        # effective-period (uses A4 not B4)
        _rec_mu(name),
        _rec_bool_false(0x0000, 0x51),                       # out-of-service
        _rec_uint8(0x0000, 0x55, 0x91, default_state),       # present-value
        _rec_uint8(0x0000, 0x58, 0x21, 10),                  # priority
        _rec(0x0000, 0x7B, 0x0E, weekly_data),               # weekly-schedule
        _rec_uint8(0x0000, 0xAE, 0x91, default_state),       # schedule-default
        _rec_uint8(0x0004, 0x1D, 0x91, range_code),          # vendor range
    ]))


def write_notif_cls_seed(instance: int, name: str) -> bytes:
    """NOTIF_CLS seed: name + 0x0485=TRUE."""
    return _build_block(26, instance, _seed_payload([
        _rec_mu(name),
        _rec_bool_true(0x0004, 0x85),
    ]))


def write_sys_group_seed(instance: int, name: str, desc: str) -> bytes:
    """SYS_GROUP/TABLE seed: desc + name. No XY data."""
    return _build_block(141, instance, _seed_payload([
        _rec_desc(desc), _rec_mu(name)
    ]))


def _build_table_xy(xy_pairs: list, max_slots: int = 14) -> bytes:
    """Build TABLE XY data (prop 0x0428) binary.
    xy_pairs: list of (x, y) float tuples.
    max_slots: total slot capacity (empty slots filled with 09 00 19 00).
    """
    result = bytearray([0x00, 0x19, 0x00])  # header
    for x, y in xy_pairs:
        result += bytes([0x0C]) + struct.pack('>f', x)
        result += bytes([0x1C]) + struct.pack('>f', y)
    # Fill remaining slots with empty markers
    for _ in range(max_slots - len(xy_pairs)):
        result += bytes([0x09, 0x00, 0x19, 0x00])
    return bytes(result)


def write_table_block(instance: int, name: str, xy_pairs: list,
                      units: int = 95, max_slots: int = 14, desc: str = '') -> bytes:
    """Fully populated TABLE block — 5 properties matching A201.pan.
    Always uses enum(0) for description — matches A201 format.
    """
    xy_data = _build_table_xy(xy_pairs, max_slots)
    num_points = 5

    return _build_block(141, instance, _seed_payload([
        _rec_enum(0x0000, 0x1C, 0x00),
        _rec_mu(name),
        _rec_uint8(0x0000, 0x75, 0x91, units),              # output units
        _rec(0x0004, 0x28, 0x09, xy_data),                   # XY data
        _rec_uint8(0x0004, 0x4A, 0x91, num_points),          # point capacity
    ]))


# ============================================================
# STL (TREND_LOG) writer — fully populated, 22 properties
# ============================================================

# Wildcarded datetime = "no date/time set"
_DT_WILDCARD = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xB4, 0xFF, 0xFF, 0xFF, 0xFF])


def write_stl_block(instance: int, name: str, logging_type: int,
                    mon_type: int, mon_instance: int,
                    buffer_size: int = 512, log_interval: int = 0,
                    cov_increment: float = 0.2) -> bytes:
    """STL block: 22 properties — 16 fixed + 6 variable from Excel.
    logging_type: 1=Polled, 2=COV.
    mon_type/mon_instance: BACnet type+instance of monitored point.
    buffer_size: from Excel Buffer column.
    log_interval: seconds for Polled, 0 for COV.
    cov_increment: float delta (0.20 default for Polled, delta for COV).
    """
    return _build_block(20, instance, _seed_payload([
        _rec_uint8(0x0000, 0x11, 0x21, 0x41),                  # buffer-size = 65
        _rec_enum(0x0000, 0x1C, 0x00),                          # description = enum 0
        _rec_complex(0x0000, 0x23, bytes([0x05, 0x00])),        # event-state
        _rec_uint8(0x0000, 0x48, 0x91, logging_type),           # logging-type
        _rec_mu(name),                                           # object-name
        _rec_uint16(0x0000, 0x7E, buffer_size),                 # record-count(max)
        _rec_float(0x0000, 0x7F, cov_increment),                # cov-increment
        _rec_uint16(0x0000, 0x80, log_interval),                # log-interval
        _rec_objref(0x0000, 0x84, mon_type, mon_instance),      # monitored-object
        _rec_bool_true(0x0000, 0x85),                            # enable
        _rec_uint16(0x0000, 0x86, 30000),                       # notification-threshold
        _rec_uint8(0x0000, 0x89, 0x21, 0x00),                   # notification-class
        _rec_datetime(0x0000, 0x8E, _DT_WILDCARD),              # start-time
        _rec_datetime(0x0000, 0x8F, _DT_WILDCARD),              # stop-time
        _rec_bool_false(0x0000, 0x90),                           # stop-when-full
        _rec_bool_true(0x0000, 0xC1),                            # align-intervals
        _rec_uint8(0x0000, 0xC3, 0x21, 0x00),                   # interval-offset
        _rec_uint8(0x0000, 0xC5, 0x91, 0x00),                   # trigger
        _rec_enum(0x0001, 0x60, 0x00),                           # vendor-status
        _rec_bool_true(0x0001, 0x61),                            # vendor-flag1
        _rec_bool_false(0x0001, 0x62),                           # vendor-flag2
        _rec_bool_true(0x0004, 0x56),                            # vendor-enable
    ]))


# ============================================================
# NC_GROUP seed writer
# ============================================================

def _rec_status(status_val: int) -> bytes:
    """NC_GROUP status property: ctx=0x0000, prop=0x56, tag=0x21.
    Value = 3 pairs: [val, 0x21, val, 0x21, val] (6 bytes total with tags).
    """
    return _rec(0x0000, 0x56, 0x21, bytes([status_val, 0x21, status_val, 0x21, status_val]))


def _rec_raw(ctx: int, prop: int, tag: int, raw_data: bytes) -> bytes:
    """Build a TLV record with raw binary data — no trailing 0x00 terminator.
    Used for opaque binary blobs like NC_GROUP config.
    """
    body = bytes([0x00, (ctx >> 8) & 0xFF, ctx & 0xFF, prop, tag]) + raw_data
    total_len = 1 + len(body)
    return bytes([total_len]) + body


def _rec_config(config_data: bytes) -> bytes:
    """NC_GROUP config property: ctx=0x0000, prop=0x66, tag=0x82, raw binary.
    Uses _rec (with trailing 0x00) — _seed_payload strips it when config is last record.
    """
    return _rec(0x0000, 0x66, 0x82, config_data)


def write_nc_group_seed(instance: int, name: str, status_val: int,
                        config_data: bytes = None) -> bytes:
    """NC_GROUP seed: name + status + optional config.
    status_val: typically 0x04 or 0x06.
    config_data: raw config blob (tag 0x82 value). None = no config record.
    """
    records = [_rec_mu(name), _rec_status(status_val)]
    if config_data is not None:
        records.append(_rec_config(config_data))
    return _build_block(15, instance, _seed_payload(records))


# ============================================================
# NC_GROUP + DEVICE — copy from blank
# ============================================================

def extract_nc_groups_from_blank(blank_path: str) -> list:
    """Extract NC_GROUP blocks directly from blank .panx."""
    import zipfile
    with zipfile.ZipFile(blank_path) as z:
        pan_name = [n for n in z.namelist() if n.endswith('.pan')][0]
        data = z.read(pan_name)

    def _ri(d, o):
        v = []
        for i in range(4):
            h = struct.unpack_from('<H', d, o + i * 4)[0]
            l = struct.unpack_from('<H', d, o + i * 4 + 2)[0]
            v.append((h << 16) | l)
        return v

    first = _ri(data, 0x400)
    blocks = []
    entries = [(first[1], first[2], first[3])]
    for i in range(1, first[0]):
        e = _ri(data, 0x440 + (i - 1) * 0x40)
        entries.append((e[1], e[2], e[3]))

    for type_id, offset, count in entries:
        if type_id == 15 and offset < len(data):
            pos = offset
            for _ in range(count):
                if pos + 12 >= len(data): break
                sz = struct.unpack_from('<H', data, pos)[0]
                tot = sz + 2
                if pos + tot > len(data): break
                block = bytearray(data[pos:pos + tot])
                # Recompute CRC
                crc = crc16_kermit(bytes(block[12:]))
                struct.pack_into('>H', block, 10, crc)
                blocks.append(bytes(block))
                pos += tot
            break

    # Also check if first entry IS NC_GROUP
    if first[1] == 15 and first[2] < len(data):
        if not blocks:  # didn't find in loop above
            pos = first[2]
            for _ in range(first[3]):
                if pos + 12 >= len(data): break
                sz = struct.unpack_from('<H', data, pos)[0]
                tot = sz + 2
                if pos + tot > len(data): break
                blocks.append(data[pos:pos + tot])
                pos += tot

    return blocks


def extract_device_block_from_blank(blank_path: str) -> bytes:
    """Extract DEVICE block from blank .panx."""
    import zipfile
    with zipfile.ZipFile(blank_path) as z:
        pan_name = [n for n in z.namelist() if n.endswith('.pan')][0]
        data = z.read(pan_name)

    def _ri(d, o):
        v = []
        for i in range(4):
            h = struct.unpack_from('<H', d, o + i * 4)[0]
            l = struct.unpack_from('<H', d, o + i * 4 + 2)[0]
            v.append((h << 16) | l)
        return v

    first = _ri(data, 0x400)
    entries = [(first[1], first[2], first[3])]
    for i in range(1, first[0]):
        e = _ri(data, 0x440 + (i - 1) * 0x40)
        entries.append((e[1], e[2], e[3]))

    for type_id, offset, count in entries:
        if type_id == 8 and offset < len(data):
            sz = struct.unpack_from('<H', data, offset)[0]
            tot = sz + 2
            return data[offset:offset + tot]

    raise ValueError(f"No DEVICE block found in {blank_path}")


def read_blank_header(blank_path: str) -> tuple:
    """Read (magic, devid, secoff) from blank .panx header."""
    import zipfile
    with zipfile.ZipFile(blank_path) as z:
        pan_name = [n for n in z.namelist() if n.endswith('.pan')][0]
        data = z.read(pan_name)
    return (struct.unpack_from('<I', data, 0)[0],
            struct.unpack_from('<I', data, 4)[0],
            struct.unpack_from('<I', data, 8)[0])


# ============================================================
# INDEX TABLE
# ============================================================

def _write_index_entry(val0: int, type_id: int, offset: int, count: int) -> bytes:
    """16-byte index entry matching A201.pan format.
    bytes 0-1: LE16 padding (0 for all except slot 0 which has num_types)
    bytes 2-3: LE16 val0 (num_types for slot 0, else 0)
    bytes 4-5: LE16 padding (always 0)
    bytes 6-7: LE16 type_id
    bytes 8-9: LE16 always 0
    bytes 10-11: LE16 offset low word
    byte 12: offset high byte (page selector)
    byte 13: always 0
    bytes 14-15: LE16 count
    """
    entry = bytearray(16)
    struct.pack_into('<H', entry, 0, (val0 >> 16) & 0xFFFF)
    struct.pack_into('<H', entry, 2, val0 & 0xFFFF)
    struct.pack_into('<H', entry, 4, (type_id >> 16) & 0xFFFF)
    struct.pack_into('<H', entry, 6, type_id & 0xFFFF)
    struct.pack_into('<H', entry, 8, 0)                        # always zero
    struct.pack_into('<H', entry, 10, offset & 0xFFFF)         # offset low word
    entry[12] = (offset >> 16) & 0xFF                           # offset high byte
    entry[13] = 0                                               # always zero
    struct.pack_into('<H', entry, 14, count & 0xFFFF)          # count
    return bytes(entry)
