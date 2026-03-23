"""
SBS Composition Engine — .pan Binary Compiler

Builds complete .pan binary files from scratch using ControllerConfig data.
No seeds, no templates, no PFG.

CRC: CRC-16/KERMIT, init=0xF321, over block[12:] payload only.
TLV: [total_len 1B] [pad=0x00] [ctx_hi 1B] [ctx_lo 1B] [prop_id 1B] [tag 1B] [value...] [0x00 term]
"""

import struct
from composition.models import ValuePoint, InputPoint, OutputPoint


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

def _rec(ctx: int, prop: int, tag: int, value: bytes) -> bytes:
    """Build a single TLV record: [len][0x00][ctx_hi][ctx_lo][prop][tag][value][0x00]"""
    ctx_hi = (ctx >> 8) & 0xFF
    ctx_lo = ctx & 0xFF
    content = bytes([0x00, ctx_hi, ctx_lo, prop, tag]) + value + b'\x00'
    total_len = 1 + len(content)  # 1 byte for the length itself
    return bytes([total_len]) + content


def _rec_bool(ctx: int, prop: int, value: bool) -> bytes:
    """Bool record — tag 0x11 (TRUE) or 0x10 (FALSE), no value data."""
    tag = 0x11 if value else 0x10
    # No value bytes, just: [len][00][ctx_hi][ctx_lo][prop][tag][00]
    ctx_hi = (ctx >> 8) & 0xFF
    ctx_lo = ctx & 0xFF
    content = bytes([0x00, ctx_hi, ctx_lo, prop, tag, 0x00])
    return bytes([1 + len(content)]) + content


def _rec_uint8(ctx: int, prop: int, tag: int, value: int) -> bytes:
    """Uint8 record — tag 0x21 or 0x91."""
    return _rec(ctx, prop, tag, bytes([value]))


def _rec_float(ctx: int, prop: int, value: float) -> bytes:
    """Float BE record — tag 0x44."""
    return _rec(ctx, prop, 0x44, struct.pack('>f', value))


def _rec_string(ctx: int, prop: int, value: str) -> bytes:
    """String record — tag 0x75: [len][0x00][string bytes][0x00 already from _rec]"""
    s_bytes = value.encode('ascii')
    s_len = len(s_bytes) + 1  # +1 for the null terminator added by _rec
    # Value data: [string_len] [0x00] [string_bytes]
    val = bytes([s_len, 0x00]) + s_bytes
    return _rec(ctx, prop, 0x75, val)


def _rec_mu_header(name: str) -> bytes:
    """Mu object name header — prop=0x4D, tag=0x75."""
    name_bytes = name.encode('ascii')
    name_field_len = len(name_bytes) + 1  # +1 for null term
    # Value: [name_field_len] [0x00] [name_bytes]
    val = bytes([name_field_len, 0x00]) + name_bytes
    return _rec(0x0000, 0x4D, 0x75, val)


def _rec_ref(ctx: int, prop: int, ref_bytes: bytes) -> bytes:
    """Object reference record — tag 0x82."""
    return _rec(ctx, prop, 0x82, ref_bytes)


def _rec_objid_plus(ctx: int, prop: int, objid: int, tail: bytes) -> bytes:
    """ObjID + tail data record — tag 0x0C."""
    return _rec(ctx, prop, 0x0C, struct.pack('>I', objid) + tail)


def _rec_string_triple(ctx: int, prop: int, s1: str, s2: str, s3: str) -> bytes:
    """Triple string record — tag 0x75 with 3 embedded strings."""
    # Format: [75] [len1] [00] [str1] [75] [len2] [00] [str2] [75] [len3] [00] [str3]
    def _s(s):
        sb = s.encode('ascii')
        return bytes([0x75, len(sb) + 1, 0x00]) + sb
    val = _s(s1) + _s(s2) + _s(s3)
    return _rec(ctx, prop, 0x75, val[1:])  # skip first 0x75 since _rec adds the tag


def _build_priority_array_av() -> bytes:
    """AV priority array — from reference: 26 total bytes.
    Raw: 1a 00 00 00 57 00 00 00 00 00 00 00 00 00 44 00 00 00 00 00 00 00 00 00 00 00
    Value data (after tag 0x00): 00 00 00 00 00 00 00 00 44 00 00 00 00 00 00 00 00 00 00
    The _rec adds [len][00][ctx_hi][ctx_lo][prop][tag] + value + [00]
    So value should be: 00 00 00 00 00 00 00 00 44 00 00 00 00 00 00 00 00 00 00
    And _rec's trailing 00 makes the last byte.
    Total: 6 (header) + 19 (value) + 1 (term) = 26 = 0x1a. Correct!
    """
    pa_value = bytes([0x00]*8) + bytes([0x44, 0x00, 0x00, 0x00, 0x00]) + bytes([0x00]*6)
    return _rec(0x0000, 0x57, 0x00, pa_value)


# ============================================================
# Block Header Builder
# ============================================================

def _build_block(type_id: int, instance: int, payload: bytes) -> bytes:
    """Build complete block: [header 12B] + [payload], with CRC computed."""
    size = 10 + len(payload)  # size field = total - 2
    header = bytearray(12)
    struct.pack_into('<H', header, 0, size)           # LE16 size
    header[2] = 0; header[3] = 0                       # padding
    struct.pack_into('>H', header, 4, size)            # BE16 size
    objid = (type_id << 22) | (instance & 0x3FFFFF)
    struct.pack_into('>I', header, 6, objid)           # ObjID BE32
    # CRC placeholder
    header[10] = 0; header[11] = 0

    # Compute CRC over payload only
    crc = crc16_kermit(payload)
    struct.pack_into('>H', header, 10, crc)

    return bytes(header) + payload


# ============================================================
# AV Block Writer
# ============================================================

# Import canonical units table from property_schemas
from composition.property_schemas import UNITS_ENUM
UNIT_CODES = UNITS_ENUM

# Range name -> RC Studio range code
RANGE_CODES = {
    '0.0 ->100%': 0x03, '10K -40 ->250': 0x03,
    'Off/On': 0x00, 'Normal/Alarm': 0x00, 'Clean/Dirty': 0x00, 'Close/Open': 0x00,
    'Stop/Start': 0x02,
    'Table1': 0x20, 'Table2': 0x21, 'Table3': 0x22, 'Table4': 0x23, 'Table5': 0x24,
}


def write_av_block(point: ValuePoint) -> bytes:
    """Build a complete AV block from a ValuePoint definition.

    Args:
        point: ValuePoint with instance, name, description, default, units

    Returns:
        Complete block bytes (header + payload) with valid CRC.
    """
    name = point.name  # e.g. "{device-name}-DIAM"
    desc = point.description or ""
    try:
        default_val = float(point.default) if point.default is not None else 0.0
    except (ValueError, TypeError):
        default_val = 0.0
    unit_code = UNIT_CODES.get(point.units, 0x5F)

    # Build payload: 3-byte padding + TLV records in property order
    records = bytearray(b'\x00\x00\x00')

    # Context 0x0000: Standard BACnet properties
    records += _rec_uint8(0x0000, 0x11, 0x21, 0x01)           # polarity = 1
    records += _rec_float(0x0000, 0x16, 0.1)                   # increment = 0.1
    records += _rec_float(0x0000, 0x19, 0.0)                   # min-present-value = 0.0
    records += _rec_string(0x0000, 0x1C, desc)                  # description
    records += _rec_ref(0x0000, 0x23, bytes([0x05, 0x00]))        # sys-group-ref
    records += _rec_float(0x0000, 0x2D, 1000.0)                # max-value
    records += _rec_ref(0x0000, 0x34, bytes([0x06, 0xC0]))        # sys-group-ref2
    records += _rec_float(0x0000, 0x3B, -1000.0)               # min-value
    records += _rec_uint8(0x0000, 0x48, 0x91, 0x00)            # notification-class = 0
    records += _rec_mu_header(name)                              # Mu object name
    records += _rec_bool(0x0000, 0x51, False)                   # out-of-service = FALSE
    records += _rec_float(0x0000, 0x55, default_val)            # present-value
    records += _build_priority_array_av()                        # priority-array
    records += _rec_float(0x0000, 0x68, default_val)            # relinquish-default
    records += _rec_uint8(0x0000, 0x71, 0x21, 0x00)            # status-flags = 0
    records += _rec_uint8(0x0000, 0x75, 0x91, unit_code)        # units

    # Context 0x0001: Alarm/event
    records += _rec_string_triple(0x0001, 0x60,
                                  "Out of Range", "%s Fault", "Out of Range")
    records += _rec_bool(0x0001, 0x61, True)                    # event-detection-enable
    records += _rec_bool(0x0001, 0x62, False)                   # event-enable
    records += _rec_objid_plus(0x0001, 0x63, 0xFFFFFFFF,
                               bytes([0x19, 0x55]))             # notif-class-ref
    records += _rec_uint8(0x0001, 0x64, 0x21, 0x00)            # notify-type = 0

    # Context 0x0004: Vendor-specific
    records += _rec_uint8(0x0004, 0x02, 0x21, 0x00)            # vendor 0x0402 = 0
    range_code = 0x03  # default: 0.0 ->100%
    if hasattr(point, 'range_code'):
        range_code = point.range_code
    records += _rec_uint8(0x0004, 0x1D, 0x91, range_code)      # range code from config
    records += _rec_bool(0x0004, 0x56, True)                    # vendor 0x0456 = TRUE

    # Context 0x0100: Terminal
    records += _rec_uint8(0x0100, 0x09, 0x91, 0x05)            # terminal ref — fixed 0x05 for AV

    # Last record has no trailing 0x00 terminator — strip it
    payload = bytes(records)
    if payload[-1] == 0x00:
        payload = payload[:-1]

    return _build_block(2, point.instance, payload)


# ============================================================
# AI Block Writer
# ============================================================

def write_ai_block(point: InputPoint) -> bytes:
    """Build a complete AI block from an InputPoint definition.

    AI differs from AV: increment=0.2, no priority-array, no relinquish-default,
    no units in standard section. Different vendor props (0x041E-0x0420 vs 0x0402/0x041D).

    Args:
        point: InputPoint with row (=instance), name, description, range_code

    Returns:
        Complete block bytes (header + payload) with valid CRC.
    """
    instance = point.row  # AI instance = row number
    name = point.name
    desc = point.description or ""

    records = bytearray(b'\x00\x00\x00')

    # Context 0x0000: Standard BACnet properties
    records += _rec_uint8(0x0000, 0x11, 0x21, 0x01)           # polarity = 1
    records += _rec_float(0x0000, 0x16, 0.2)                   # increment = 0.2 (AI-specific)
    records += _rec_float(0x0000, 0x19, 0.0)                   # min-present-value = 0.0
    records += _rec_string(0x0000, 0x1C, desc)                  # description
    records += _rec_ref(0x0000, 0x23, bytes([0x05, 0x00]))      # sys-group-ref
    records += _rec_float(0x0000, 0x2D, 1000.0)                # max-value
    records += _rec_ref(0x0000, 0x34, bytes([0x06, 0xC0]))      # sys-group-ref2
    records += _rec_float(0x0000, 0x3B, -1000.0)               # min-value
    records += _rec_uint8(0x0000, 0x48, 0x91, 0x00)            # notification-class = 0
    records += _rec_mu_header(name)                              # Mu object name
    records += _rec_bool(0x0000, 0x51, False)                   # out-of-service = FALSE
    records += _rec_float(0x0000, 0x55, 0.0)                    # present-value = 0.0 (read-only)
    # NO priority-array or relinquish-default for AI
    records += _rec_uint8(0x0000, 0x71, 0x21, 0x00)            # status-flags = 0
    unit_code = UNIT_CODES.get(point.units, 0x5F)
    records += _rec_uint8(0x0000, 0x75, 0x91, unit_code)        # units

    # Context 0x0001: Alarm/event
    records += _rec_string_triple(0x0001, 0x60,
                                  "Out of Range", "%s Fault", "Out of Range")
    records += _rec_bool(0x0001, 0x61, True)                    # event-detection-enable
    records += _rec_bool(0x0001, 0x62, False)                   # event-enable
    records += _rec_objid_plus(0x0001, 0x63, 0xFFFFFFFF,
                               bytes([0x19, 0x55]))             # notif-class-ref
    records += _rec_uint8(0x0001, 0x64, 0x21, 0x00)            # notify-type = 0

    # Context 0x0004: Vendor-specific
    records += _rec_uint8(0x0004, 0x02, 0x21, 0x00)            # vendor 0x0402 = 0
    range_code_1d = 0x17  # default
    if hasattr(point, 'range_code_1d'):
        range_code_1d = point.range_code_1d
    records += _rec_uint8(0x0004, 0x1D, 0x91, range_code_1d)   # vendor 0x041D range
    records += _rec_bool(0x0004, 0x1E, True)                    # vendor 0x041E = TRUE
    records += _rec_float(0x0004, 0x1F, 0.0)                    # vendor 0x041F = 0.0
    range_code = 0x00
    if hasattr(point, 'range_code_num'):
        range_code = point.range_code_num
    records += _rec_uint8(0x0004, 0x20, 0x21, range_code)      # range code
    range_code_39 = 0x02  # default
    if hasattr(point, 'range_code_39'):
        range_code_39 = point.range_code_39
    records += _rec_uint8(0x0004, 0x39, 0x91, range_code_39)   # vendor 0x0439
    records += _rec_bool(0x0004, 0x56, True)                    # vendor 0x0456 = TRUE

    # Context 0x0100: Terminal
    records += _rec_uint8(0x0100, 0x09, 0x91, 0x05)            # terminal ref — fixed 0x05 for AI

    # Last record — strip trailing 0x00
    payload = bytes(records)
    if payload[-1] == 0x00:
        payload = payload[:-1]

    return _build_block(0, instance, payload)


# ============================================================
# BI Block Writer
# ============================================================

def _rec_text(ctx: int, prop: int, tag: int, text: str) -> bytes:
    """Text record — tag 0x73 (active) or 0x74 (inactive): [00] [text] [00 from _rec]"""
    val = bytes([0x00]) + text.encode('ascii')
    return _rec(ctx, prop, tag, val)


def _rec_event_timestamps() -> bytes:
    """Event timestamps: prop=0x10, tag=0xA4, fixed data."""
    # Raw: 10 00 00 00 10 a4 ff ff ff ff b4 ff ff ff ff 00
    val = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xB4, 0xFF, 0xFF, 0xFF, 0xFF])
    return _rec(0x0000, 0x10, 0xA4, val)


def write_bi_block(point: InputPoint) -> bytes:
    """Build a complete BI block from an InputPoint definition.

    Args:
        point: InputPoint with row (=instance), name, description

    Returns:
        Complete block bytes (header + payload) with valid CRC.
    """
    instance = point.row
    name = point.name
    desc = point.description or ""

    records = bytearray(b'\x00\x00\x00')

    # Context 0x0000: Standard BACnet properties
    records += _rec_text(0x0000, 0x04, 0x74, "Yes")             # active-text
    records += _rec_uint8(0x0000, 0x06, 0x91, 0x00)             # change-of-state-count
    records += _rec_uint8(0x0000, 0x0F, 0x21, 0x00)             # event-state
    records += _rec_event_timestamps()                            # event-type-flags
    records += _rec_uint8(0x0000, 0x11, 0x21, 0x01)             # polarity = 1
    records += _rec_string(0x0000, 0x1C, desc)                    # description
    records += _rec_uint8(0x0000, 0x21, 0x21, 0x00)             # feedback-value = 0
    records += _rec_ref(0x0000, 0x23, bytes([0x05, 0x00]))       # sys-group-ref
    records += _rec_text(0x0000, 0x2E, 0x73, "No")              # inactive-text
    records += _rec_uint8(0x0000, 0x48, 0x91, 0x00)             # notification-class = 0
    records += _rec_mu_header(name)                               # Mu object name
    records += _rec_bool(0x0000, 0x51, False)                    # out-of-service = FALSE
    records += _rec_uint8(0x0000, 0x54, 0x91, 0x00)             # polarity2 = 0
    records += _rec_uint8(0x0000, 0x55, 0x91, 0x00)             # present-value = 0
    records += _rec_uint8(0x0000, 0x71, 0x21, 0x00)             # status-flags = 0

    # Context 0x0001: Alarm/event
    records += _rec_string_triple(0x0001, 0x60,
                                  "Change of State", "%s Fault", "Change of State")
    records += _rec_bool(0x0001, 0x61, True)                     # event-detection-enable
    records += _rec_bool(0x0001, 0x62, False)                    # event-enable
    records += _rec_objid_plus(0x0001, 0x63, 0xFFFFFFFF,
                               bytes([0x19, 0x55]))              # notif-class-ref
    records += _rec_uint8(0x0001, 0x64, 0x21, 0x00)             # notify-type = 0

    # Context 0x0004: Vendor-specific
    records += _rec_uint8(0x0004, 0x02, 0x21, 0x00)             # vendor 0x0402 = 0
    records += _rec_uint8(0x0004, 0x0D, 0x21, 0x00)             # vendor 0x040D = 0
    range_code = 0x07  # default
    if hasattr(point, 'range_code_num'):
        range_code = point.range_code_num
    records += _rec_uint8(0x0004, 0x1D, 0x91, range_code)       # range code
    records += _rec_bool(0x0004, 0x1E, True)                     # vendor 0x041E = TRUE
    records += _rec_uint8(0x0004, 0x39, 0x91, 0x00)             # vendor 0x0439 = 0
    records += _rec_bool(0x0004, 0x3B, True)                     # vendor 0x043B = TRUE
    records += _rec_bool(0x0004, 0x56, True)                     # vendor 0x0456 = TRUE
    records += _rec_uint8(0x0004, 0x58, 0x21, 0x64)             # vendor 0x0458 = 100

    # Context 0x0100: Terminal
    records += _rec_uint8(0x0100, 0x09, 0x91, 0x01)             # terminal ref — 0x01 for BI

    # Strip trailing 0x00
    payload = bytes(records)
    if payload[-1] == 0x00:
        payload = payload[:-1]

    return _build_block(3, instance, payload)


# ============================================================
# BO Block Writer
# ============================================================

def _build_priority_array_binary() -> bytes:
    """Binary priority array — 23 bytes total from reference.
    Raw: 17 00 00 00 57 00 00 00 00 00 00 00 00 00 91 00 00 00 00 00 00 00 00
    Value (16B, _rec adds trailing 00): 00 00 00 00 00 00 00 00 91 00 00 00 00 00 00 00
    """
    pa_value = bytes([0x00]*8) + bytes([0x91, 0x00]) + bytes([0x00]*6)
    return _rec(0x0000, 0x57, 0x00, pa_value)


def write_bo_block(point: OutputPoint) -> bytes:
    """Build a complete BO block from an OutputPoint definition."""
    instance = point.row
    name = point.name
    desc = point.description or ""

    records = bytearray(b'\x00\x00\x00')

    # Context 0x0000: Standard
    records += _rec_text(0x0000, 0x04, 0x74, "Yes")             # active-text
    records += _rec_uint8(0x0000, 0x0F, 0x21, 0x00)             # event-state
    records += _rec_event_timestamps()                            # event-type-flags
    records += _rec_uint8(0x0000, 0x11, 0x21, 0x01)             # polarity = 1
    records += _rec_string(0x0000, 0x1C, desc)                    # description
    records += _rec_uint8(0x0000, 0x21, 0x21, 0x00)             # feedback-value
    records += _rec_ref(0x0000, 0x23, bytes([0x05, 0x00]))       # sys-group-ref
    records += _rec_text(0x0000, 0x2E, 0x73, "No")              # inactive-text
    records += _rec_uint8(0x0000, 0x42, 0x21, 0x00)             # min-off-time
    records += _rec_uint8(0x0000, 0x43, 0x21, 0x00)             # min-on-time
    records += _rec_uint8(0x0000, 0x48, 0x91, 0x00)             # notification-class
    records += _rec_mu_header(name)                               # Mu object name
    records += _rec_bool(0x0000, 0x51, False)                    # out-of-service
    records += _rec_uint8(0x0000, 0x54, 0x91, 0x00)             # polarity2
    records += _rec_uint8(0x0000, 0x55, 0x91, 0x00)             # present-value
    records += _build_priority_array_binary()                     # priority-array
    records += _rec_uint8(0x0000, 0x68, 0x91, 0x00)             # relinquish-default
    records += _rec_uint8(0x0000, 0x71, 0x21, 0x00)             # status-flags

    # Context 0x0001: Alarm/event
    records += _rec_string_triple(0x0001, 0x60,
                                  "Command Failure", "%s Fault", "Command Failure")
    records += _rec_bool(0x0001, 0x61, True)
    records += _rec_bool(0x0001, 0x62, False)
    records += _rec_objid_plus(0x0001, 0x63, 0xFFFFFFFF,
                               bytes([0x19, 0x55]))
    records += _rec_uint8(0x0001, 0x64, 0x21, 0x00)

    # Context 0x0004: Vendor-specific
    records += _rec_uint8(0x0004, 0x02, 0x21, 0x00)
    records += _rec_uint8(0x0004, 0x0D, 0x21, 0x00)
    records += _rec(0x0004, 0x13, 0xC4, bytes([0xFF, 0xFF, 0xFF, 0xFF]))  # vendor 0x0413
    range_code = 0x07
    if hasattr(point, 'range_code_num'):
        range_code = point.range_code_num
    records += _rec_uint8(0x0004, 0x1D, 0x91, range_code)
    records += _rec_bool(0x0004, 0x1E, True)
    records += _rec_bool(0x0004, 0x3B, True)
    records += _rec_bool(0x0004, 0x56, True)
    records += _rec_uint8(0x0004, 0x58, 0x21, 0x64)

    # Context 0x0100: Terminal
    records += _rec_uint8(0x0100, 0x09, 0x91, 0x03)             # terminal ref — 0x03 for BO

    payload = bytes(records)
    if payload[-1] == 0x00:
        payload = payload[:-1]

    return _build_block(4, instance, payload)


# ============================================================
# AO Block Writer
# ============================================================

def write_ao_block(point: OutputPoint) -> bytes:
    """Build a complete AO block from an OutputPoint definition.

    AO is structurally identical to AV but with voltage range vendor props
    and no present-value default (output is driven by program).

    Args:
        point: OutputPoint with row (=instance), name, description, units, min_v, max_v
    """
    instance = point.row
    name = point.name
    desc = point.description or ""
    unit_code = UNIT_CODES.get(point.units, 0x5F)
    min_v = getattr(point, 'min_v', 2.0)
    max_v = getattr(point, 'max_v', 10.0)

    records = bytearray(b'\x00\x00\x00')

    # Context 0x0000: Standard (ascending prop_id order like blanks)
    records += _rec_uint8(0x0000, 0x11, 0x21, 0x01)             # polarity
    records += _rec_float(0x0000, 0x16, 0.1)                     # increment
    records += _rec_float(0x0000, 0x19, 0.0)                     # min-present-value
    records += _rec_string(0x0000, 0x1C, desc)                    # description
    records += _rec_ref(0x0000, 0x23, bytes([0x05, 0x00]))        # sys-group-ref
    records += _rec_float(0x0000, 0x2D, 1000.0)                  # max-value
    records += _rec_ref(0x0000, 0x34, bytes([0x06, 0x00]))        # sys-group-ref2 (0x060000 for AO)
    records += _rec_float(0x0000, 0x3B, -1000.0)                 # min-value
    records += _rec_uint8(0x0000, 0x48, 0x91, 0x00)              # notification-class
    records += _rec_mu_header(name)                                # Mu object name
    records += _rec_bool(0x0000, 0x51, False)                     # out-of-service
    records += _rec_float(0x0000, 0x55, 0.0)                      # present-value
    records += _build_priority_array_av()                          # priority-array (AV-style float)
    records += _rec_float(0x0000, 0x68, 0.0)                      # relinquish-default
    records += _rec_uint8(0x0000, 0x71, 0x21, 0x00)              # status-flags
    records += _rec_uint8(0x0000, 0x75, 0x91, unit_code)          # units

    # Context 0x0001: Alarm/event
    records += _rec_string_triple(0x0001, 0x60,
                                  "Out of Range", "%s Fault", "Out of Range")
    records += _rec_bool(0x0001, 0x61, True)
    records += _rec_bool(0x0001, 0x62, False)
    records += _rec_objid_plus(0x0001, 0x63, 0xFFFFFFFF,
                               bytes([0x19, 0x55]))
    records += _rec_uint8(0x0001, 0x64, 0x21, 0x00)

    # Context 0x0004: Vendor-specific (AO-specific voltage props)
    records += _rec_uint8(0x0004, 0x02, 0x21, 0x00)              # vendor 0x0402
    records += _rec_uint8(0x0004, 0x1D, 0x91, 0x03)              # range code (0x03 default)
    records += _rec_bool(0x0004, 0x1E, True)                      # vendor 0x041E
    records += _rec_float(0x0004, 0x22, min_v)                    # min voltage (e.g. 0.0 or 2.0)
    records += _rec_float(0x0004, 0x23, max_v)                    # max voltage (e.g. 10.0)
    records += _rec_bool(0x0004, 0x56, False)                     # vendor 0x0456 = FALSE for AO

    # Context 0x0100: Terminal
    records += _rec_uint8(0x0100, 0x09, 0x91, 0x05)              # terminal ref

    payload = bytes(records)
    if payload[-1] == 0x00:
        payload = payload[:-1]

    return _build_block(1, instance, payload)


# ============================================================
# BV Block Writer
# ============================================================

def write_bv_block(point: ValuePoint) -> bytes:
    """Build a complete BV block from a ValuePoint definition."""
    name = point.name
    desc = point.description or ""
    default_val = int(point.default) if point.default else 0

    records = bytearray(b'\x00\x00\x00')

    # Context 0x0000: Standard
    records += _rec_text(0x0000, 0x04, 0x74, "Yes")              # active-text
    records += _rec_uint8(0x0000, 0x06, 0x91, 0x00)              # change-of-state-count
    records += _rec_uint8(0x0000, 0x0F, 0x21, 0x00)              # event-state
    records += _rec_event_timestamps()                             # event-type-flags
    records += _rec_uint8(0x0000, 0x11, 0x21, 0x01)              # polarity
    records += _rec_string(0x0000, 0x1C, desc)                     # description
    records += _rec_uint8(0x0000, 0x21, 0x21, 0x00)              # feedback-value
    records += _rec_ref(0x0000, 0x23, bytes([0x05, 0x00]))        # sys-group-ref
    records += _rec_text(0x0000, 0x2E, 0x73, "No")               # inactive-text
    records += _rec_uint8(0x0000, 0x42, 0x21, 0x00)              # min-off-time
    records += _rec_uint8(0x0000, 0x43, 0x21, 0x00)              # min-on-time
    records += _rec_uint8(0x0000, 0x48, 0x91, 0x00)              # notification-class
    records += _rec_mu_header(name)                                # Mu object name
    records += _rec_bool(0x0000, 0x51, False)                     # out-of-service
    records += _rec_uint8(0x0000, 0x55, 0x91, default_val & 0xFF) # present-value
    records += _build_priority_array_binary()                      # priority-array (binary)
    records += _rec_uint8(0x0000, 0x68, 0x91, default_val & 0xFF) # relinquish-default
    records += _rec_uint8(0x0000, 0x71, 0x21, 0x00)              # status-flags

    # Context 0x0001: Alarm/event
    records += _rec_string_triple(0x0001, 0x60,
                                  "Change of State", "%s Fault", "Change of State")
    records += _rec_bool(0x0001, 0x61, True)
    records += _rec_bool(0x0001, 0x62, False)
    records += _rec_objid_plus(0x0001, 0x63, 0xFFFFFFFF,
                               bytes([0x19, 0x55]))
    records += _rec_uint8(0x0001, 0x64, 0x21, 0x00)

    # Context 0x0004: Vendor-specific
    records += _rec_uint8(0x0004, 0x02, 0x21, 0x00)
    records += _rec_uint8(0x0004, 0x0D, 0x21, 0x00)
    range_code = 0x07
    if hasattr(point, 'range_code_num'):
        range_code = point.range_code_num
    records += _rec_uint8(0x0004, 0x1D, 0x91, range_code)
    records += _rec_bool(0x0004, 0x3B, True)
    records += _rec_bool(0x0004, 0x56, True)
    records += _rec_uint8(0x0004, 0x58, 0x21, 0x64)

    # Context 0x0100: Terminal
    records += _rec_uint8(0x0100, 0x09, 0x91, 0x01)              # terminal ref — 0x01 for BV

    payload = bytes(records)
    if payload[-1] == 0x00:
        payload = payload[:-1]

    return _build_block(5, point.instance, payload)


# ============================================================
# LOOP Block Writer
# ============================================================

def _encode_objid(type_name: str, instance: int) -> bytes:
    """Encode a BACnet ObjID as 4-byte big-endian."""
    TYPE_IDS = {"AI": 0, "AO": 1, "AV": 2, "BI": 3, "BO": 4, "BV": 5,
                "LOOP": 12, "MO": 14, "PROGRAM": 16, "SCHEDULE": 17, "MV": 19}
    type_num = TYPE_IDS.get(type_name, 0)
    val = (type_num << 22) | (instance & 0x3FFFFF)
    return struct.pack('>I', val)


def write_loop_block(loop) -> bytes:
    """Build a complete LOOP block from a LoopDef.

    Args:
        loop: LoopDef with instance, name, input_ref, setpoint_ref,
              p_band, integral, derivative, action

    Uses RC Studio FCU file property order for maximum compatibility.
    """
    name = loop.name
    action = 0x00 if loop.action == "direct" else 0x01
    p_band = float(loop.p_band)
    integral = float(loop.integral)
    derivative = float(loop.derivative) if hasattr(loop, 'derivative') else 0.0

    # Input ref ObjID — need to resolve from point name to (type, instance)
    # For now, store as null (0xFFFFFFFF) — will be resolved by compiler main loop
    input_objid = bytes([0xFF, 0xFF, 0xFF, 0xFF])
    if hasattr(loop, '_input_objid'):
        input_objid = loop._input_objid

    records = bytearray(b'\x00\x00\x00')

    # RC Studio FCU property order (verified across 3 files)
    records += _rec_float(0x0000, 0x55, 0.0)                     # present-value
    records += _rec_float(0x0000, 0x5D, 0.0)                     # setpoint
    records += _rec_float(0x0000, 0x31, 0.0)                     # output
    records += _rec_float(0x0000, 0x1A, 0.0)                     # bias
    records += _rec_float(0x0000, 0x16, 0.1)                     # increment
    records += _rec_mu_header(name)                                # Mu name
    records += _rec_bool(0x0000, 0x51, False)                     # out-of-service
    records += _rec_uint8(0x0000, 0x52, 0x91, 0x62)              # pv-units
    records += _rec_objid_plus(0x0000, 0x13, 0xFFFFFFFF,
                               bytes([0x19, 0x55]))               # input-ref (null default)
    records += _rec_float(0x0000, 0x6C, integral)                  # integral time
    # setpoint-ref: 6 bytes exactly: 06 00 00 00 6D 00 (no trailing 00 from _rec)
    records += bytes([0x06, 0x00, 0x00, 0x00, 0x6D, 0x00])       # setpoint-ref (empty, raw)
    records += _rec_uint8(0x0000, 0x02, 0x91, action)             # action
    records += _rec_float(0x0000, 0x0E, derivative)                # derivative
    records += _rec_uint8(0x0000, 0x1C, 0x71, 0x00)              # description (null)
    records += _rec_float(0x0004, 0x4D, p_band)                   # p-band (vendor)

    # Alarm
    # LOOP alarm text: "Floating Limit" / null(0x71) / "Floating Limit"
    # Reference: 2a 00 00 01 60 75 0f 00 "Floating Limit" 71 00 75 0f 00 "Floating Limit" 00
    _fl = "Floating Limit".encode('ascii')
    _alarm_val = bytes([len(_fl)+1, 0x00]) + _fl + bytes([0x71, 0x00, 0x75, len(_fl)+1, 0x00]) + _fl
    records += _rec(0x0001, 0x60, 0x75, _alarm_val)

    records += _rec_objid_plus(0x0000, 0x3C, 0xFFFFFFFF,
                               bytes([0x19, 0x55]))               # manip-var-ref (null)
    records += _rec_uint8(0x0000, 0x58, 0x21, 0x0A)              # priority
    records += _rec_uint8(0x0000, 0x5E, 0x91, 0x5F)              # setpoint-units
    records += _rec_uint8(0x0000, 0x32, 0x91, 0x48)              # output-units
    records += _rec_uint8(0x0000, 0x1B, 0x91, 0x5F)              # controlled-var-units
    records += _rec_uint8(0x0100, 0x09, 0x91, 0x04)              # terminal ref
    records += _rec_uint8(0x0000, 0x71, 0x21, 0x00)              # status-flags
    records += _rec_uint8(0x0000, 0x11, 0x21, 0x01)              # polarity
    records += _rec_float(0x0000, 0x22, 0.0)                      # error
    records += _rec_float(0x0000, 0x19, 0.0)                      # min-present-value
    records += _rec_ref(0x0000, 0x23, bytes([0x05, 0x00]))        # sys-group-ref
    records += _rec_uint8(0x0000, 0x48, 0x91, 0x00)              # notification-class
    records += _rec_uint8(0x0001, 0x64, 0x21, 0x00)              # notify-type
    records += _rec_objid_plus(0x0001, 0x63, 0xFFFFFFFF,
                               bytes([0x19, 0x55]))               # notif-class-ref
    records += _rec_bool(0x0001, 0x62, False)                     # event-enable
    records += _rec_bool(0x0001, 0x61, True)                      # event-detection-enable

    payload = bytes(records)
    if payload[-1] == 0x00:
        payload = payload[:-1]

    return _build_block(12, loop.instance, payload)


# ============================================================
# MV Block Writer
# ============================================================

def write_mv_block(point: ValuePoint) -> bytes:
    """Build a complete MV (Multi-state Value) block."""
    name = point.name
    default_val = int(point.default) if point.default else 1
    # First state text — from ValuePoint.states dict or description
    state_text = ""
    if hasattr(point, 'states') and point.states:
        state_text = point.states.get(1, point.states.get(min(point.states.keys()), ""))

    records = bytearray(b'\x00\x00\x00')

    records += _rec_uint8(0x0000, 0x11, 0x21, 0x01)              # polarity
    records += _rec_uint8(0x0000, 0x1C, 0x71, 0x00)              # description (null)
    records += _rec_ref(0x0000, 0x23, bytes([0x05, 0x00]))        # sys-group-ref
    records += _rec_uint8(0x0000, 0x48, 0x91, 0x00)              # notification-class
    records += _rec_mu_header(name)                                # Mu name
    records += _rec_bool(0x0000, 0x51, False)                     # out-of-service
    records += _rec_uint8(0x0000, 0x55, 0x21, default_val & 0xFF) # present-value
    records += _build_priority_array_binary()                      # priority-array (binary/MV style)
    records += _rec_uint8(0x0000, 0x68, 0x21, default_val & 0xFF) # relinquish-default
    if state_text:
        records += _rec_string(0x0000, 0x6E, state_text)          # state-text
    records += _rec_uint8(0x0000, 0x71, 0x21, 0x00)              # status-flags

    # Alarm
    records += _rec_string_triple(0x0001, 0x60,
                                  "Change of State", "%s Fault", "Change of State")
    records += _rec_bool(0x0001, 0x61, True)
    records += _rec_bool(0x0001, 0x62, False)
    records += _rec_objid_plus(0x0001, 0x63, 0xFFFFFFFF,
                               bytes([0x19, 0x55]))
    records += _rec_uint8(0x0001, 0x64, 0x21, 0x00)

    # Vendor
    records += _rec_uint8(0x0004, 0x02, 0x21, 0x00)              # vendor 0x0402
    records += _rec_uint8(0x0004, 0x1D, 0x91, 0x00)              # vendor 0x041D range
    records += _rec_bool(0x0004, 0x56, False)                     # vendor 0x0456 = FALSE for MV

    # Terminal
    records += _rec_uint8(0x0100, 0x09, 0x91, 0x01)

    payload = bytes(records)
    if payload[-1] == 0x00:
        payload = payload[:-1]

    return _build_block(19, point.instance, payload)


# ============================================================
# TREND Block Writer
# ============================================================

def write_trend_block(instance: int) -> bytes:
    """Build a TREND block. Minimal — 4 fixed properties."""
    records = bytearray(b'\x00\x00\x00')
    records += _rec_uint8(0x0000, 0x11, 0x21, 0x41)              # polarity = 0x41
    records += _rec_ref(0x0000, 0x23, bytes([0x05, 0x00]))        # sys-group-ref
    records += _rec_uint8(0x0000, 0x7E, 0x21, 0x64)              # record-count = 100
    records += _rec_uint8(0x0000, 0x89, 0x21, 0x40)              # event-type = 0x40
    records += _rec_bool(0x0000, 0x90, False)                     # stop-when-full = FALSE

    payload = bytes(records)
    if payload[-1] == 0x00:
        payload = payload[:-1]
    return _build_block(20, instance, payload)


# ============================================================
# NC_GROUP Block Writer
# ============================================================

def write_nc_group_block(instance: int, name: str, variant: int = 0x0D) -> bytes:
    """Build an NC_GROUP block.

    Args:
        instance: 0=System, 1=General, 65=Trend
        name: group name (e.g. "NC_0", "NC_1", "NC_65")
        variant: 0x0D for System/General, 0x0E for Trend

    ProZone reference format:
      inst 0/1: 58B payload = 7B pre-Mu + Mu + prop 0x56(12B) + prop 0x66(31B)
      inst 65:  28B payload = 7B pre-Mu + Mu + prop 0x56(12B)
    """
    records = bytearray([0x00, 0x00, 0x00, variant, 0x00, 0x00, 0x00])

    # Mu header
    name_bytes = name.encode('ascii')
    records += b'\x4d\x75' + bytes([len(name_bytes) + 1, 0x00]) + name_bytes + b'\x00'

    # Prop 0x56: 12 bytes — status display config
    # Raw: 0c 00 00 00 56 21 [v1] 21 [v2] 21 [v3] 00
    v56 = 0x04 if instance == 0 else 0x06
    records += bytes([0x0C, 0x00, 0x00, 0x00, 0x56, 0x21, v56, 0x21, v56, 0x21, v56, 0x00])

    # Prop 0x66: only for inst 0 and 1 (System/General), not inst 65 (Trend)
    if instance != 65:
        # Raw from ProZone: 1f 00 00 00 66 82 01 fe b4 00 00 00 00 b4 17 3b 3b 00 1e 22 ff ff 60 1f 21 01 10 82 05 e0
        records += bytes([0x1F, 0x00, 0x00, 0x00, 0x66, 0x82, 0x01, 0xFE,
                          0xB4, 0x00, 0x00, 0x00, 0x00, 0xB4, 0x17, 0x3B,
                          0x3B, 0x00, 0x1E, 0x22, 0xFF, 0xFF, 0x60, 0x1F,
                          0x21, 0x01, 0x10, 0x82, 0x05, 0xE0])

    payload = bytes(records)
    # Last record drops trailing 0x00 (same as all other block types)
    if payload[-1] == 0x00:
        payload = payload[:-1]
    return _build_block(15, instance, payload)


# ============================================================
# SYS_GROUP Block Writer
# ============================================================

def write_sys_group_block(instance: int, name: str, unit_code: int = 0x3A,
                          table_data: list = None) -> bytes:
    """Build a SYS_GROUP (type 141) block.

    Used for graphic pages AND scaling tables (Table1-5).
    Tables are SYS_GROUP blocks with XY data in vendor prop 0x0428.

    Args:
        instance: BACnet instance
        name: Object name
        unit_code: Units enum (0x3A=WC default, or from UNITS_ENUM)
        table_data: Optional list of (x, y) float pairs for scaling tables
    """
    records = bytearray(b'\x00\x00\x00')
    records += _rec_uint8(0x0000, 0x1C, 0x71, 0x00)              # description (null)
    records += _rec_mu_header(name)                                # Mu name
    records += _rec_uint8(0x0000, 0x75, 0x91, unit_code)          # units

    # Vendor prop 0x0428: grid data or table XY data
    if table_data:
        # Table XY encoding: [00 19 00] header, then per-row [0C][float_X][1C][float_Y]
        # Separator between sections: [09 00 19 00]
        # Fill remaining slots with [09 00 19]
        tbl_bytes = bytearray([0x00, 0x19, 0x00])
        for x, y in table_data:
            tbl_bytes += b'\x0c' + struct.pack('>f', x)
            tbl_bytes += b'\x1c' + struct.pack('>f', y)
        # Pad with empty row markers to fill 10 slots
        for _ in range(max(0, 10 - len(table_data))):
            tbl_bytes += bytes([0x09, 0x00, 0x19])
        # Repeat pattern for remaining table sections (same as empty)
        tbl_bytes += bytes([0x00])
        records += _rec(0x0004, 0x28, 0x09, bytes(tbl_bytes))

    records += _rec_uint8(0x0004, 0x4A, 0x91, 0x05)              # vendor 0x044A

    payload = bytes(records)
    if payload[-1] == 0x00:
        payload = payload[:-1]
    return _build_block(141, instance, payload)


# ============================================================
# MO Block Writer
# ============================================================

def write_mo_block(name: str, instance: int, description: str = "Damper Control") -> bytes:
    """Build an MO (Multi-Output, type 14) block."""
    records = bytearray(b'\x00\x00\x00')

    records += _rec_uint8(0x0000, 0x11, 0x21, 0x01)              # polarity
    records += _rec_string(0x0000, 0x1C, description)              # description
    records += _rec_ref(0x0000, 0x23, bytes([0x05, 0x00]))        # sys-group-ref
    records += _rec_uint8(0x0000, 0x28, 0x21, 0x01)              # feedback-ref
    records += _rec_uint8(0x0000, 0x48, 0x91, 0x00)              # notification-class
    records += _rec_mu_header(name)                                # Mu name
    records += _rec_bool(0x0000, 0x51, False)                     # out-of-service
    records += _rec_uint8(0x0000, 0x55, 0x21, 0x03)              # present-value = 3
    records += _build_priority_array_binary()                      # priority-array
    records += _rec_uint8(0x0000, 0x68, 0x21, 0x01)              # relinquish-default = 1
    records += _rec_string(0x0000, 0x6E, "Close")                 # state-text
    records += _rec_uint8(0x0000, 0x71, 0x21, 0x00)              # status-flags

    # Alarm
    records += _rec_string_triple(0x0001, 0x60,
                                  "Command Failure", "%s Fault", "Command Failure")
    records += _rec_bool(0x0001, 0x61, True)
    records += _rec_bool(0x0001, 0x62, False)
    records += _rec_objid_plus(0x0001, 0x63, 0xFFFFFFFF,
                               bytes([0x19, 0x55]))
    records += _rec_uint8(0x0001, 0x64, 0x21, 0x00)

    # Vendor
    records += _rec_uint8(0x0004, 0x02, 0x21, 0x00)              # vendor 0x0402
    records += _rec_uint8(0x0004, 0x1D, 0x91, 0x00)              # vendor 0x041D
    records += _rec_bool(0x0004, 0x1E, True)                      # vendor 0x041E
    records += _rec_bool(0x0004, 0x56, True)                      # vendor 0x0456

    # Terminal
    records += _rec_uint8(0x0100, 0x09, 0x91, 0x03)

    payload = bytes(records)
    if payload[-1] == 0x00:
        payload = payload[:-1]
    return _build_block(14, instance, payload)


# ============================================================
# NOTIF_CLS Block Writer
# ============================================================

def write_notif_cls_block(instance: int, name: str, group_name: str = "") -> bytes:
    """Build a NOTIF_CLS (type 26) block."""
    records = bytearray(b'\x00\x00\x00')
    records += _rec_uint8(0x0000, 0x1C, 0x71, 0x00)              # description (null)
    records += _rec_mu_header(name)                                # Mu name
    records += _rec_bool(0x0000, 0x51, False)                     # out-of-service

    # Vendor — notification config is complex, use empty placeholder
    # 0x0426 will be filled by the main compiler or left empty
    if group_name:
        records += _rec_string(0x0004, 0x27, group_name)          # notification group name

    payload = bytes(records)
    if payload[-1] == 0x00:
        payload = payload[:-1]
    return _build_block(26, instance, payload)


# ============================================================
# PROGRAM Block Writer
# ============================================================

def write_program_block(instance: int, name: str, bytecode: bytes = b'') -> bytes:
    """Build a PROGRAM (type 16) block.

    Args:
        instance: program instance number
        name: program name
        bytecode: compiled CBAS bytecode (from cbas_compiler)
    """
    records = bytearray(b'\x00\x00\x00')

    records += _rec_mu_header(name)                                # Mu name (comes first for PRG)
    records += _rec_uint8(0x0000, 0x1C, 0x71, 0x00)              # description (null)

    # Vendor
    records += _rec_bool(0x0004, 0x41, False)                     # program-enabled = FALSE

    if bytecode:
        # Bytecode: tag 0x65, variable length
        # Size encoding: 0x65 XX for XX<254, 0x65 FE [2B BE] for >=254
        if len(bytecode) < 254:
            bc_header = bytes([0x65, len(bytecode)])
        else:
            bc_header = bytes([0x65, 0xFE]) + struct.pack('>H', len(bytecode))
        records += _rec(0x0004, 0x29, 0x65, bc_header[1:] + bytecode)

    records += _rec_uint8(0x0004, 0x0A, 0x91, 0x01)              # vendor 0x040A = 1

    payload = bytes(records)
    if payload[-1] == 0x00:
        payload = payload[:-1]
    return _build_block(16, instance, payload)


# ============================================================
# DEVICE Block Writer
# ============================================================

def write_device_block_from_blank(blank_panx_path: str, device_name: str = "",
                                   custom_units: list = None) -> bytes:
    """Build a DEVICE block by copying from blank .panx and injecting custom data.

    The DEVICE block contains controller model info, serial number, firmware config,
    table scaling data, and custom unit definitions. Most of this is controller-specific
    and must come from the blank template.

    Args:
        blank_panx_path: Path to blank .panx file for the target controller model
        device_name: Optional device name to inject
        custom_units: Optional list of custom unit definitions to inject

    Returns:
        Complete DEVICE block bytes with valid CRC.
    """
    import zipfile
    from pathlib import Path

    with zipfile.ZipFile(blank_panx_path) as z:
        pan_name = [n for n in z.namelist() if n.endswith('.pan')][0]
        data = z.read(pan_name)

    def _ri(d, o):
        v = []
        for i in range(4):
            h = struct.unpack_from('<H', d, o + i * 4)[0]
            l = struct.unpack_from('<H', d, o + i * 4 + 2)[0]
            v.append((h << 16) | l)
        return v

    # Find DEVICE block (type 8)
    first = _ri(data, 0x400)
    entries = []
    if first[2] < len(data) and first[3] < 10000 and first[3] > 0:
        entries.append((first[1], first[2], first[3]))
    for i in range(first[0]):
        e = _ri(data, 0x440 + i * 0x40)
        if e[1] < 500 and e[2] < len(data) and e[3] < 10000 and e[3] > 0:
            entries.append((e[1], e[2], e[3]))

    for type_id, offset, count in entries:
        if type_id == 8:
            pos = offset
            sz = struct.unpack_from('<H', data, pos)[0]
            tot = sz + 2
            device_block = bytearray(data[pos:pos + tot])

            # TODO: inject device_name into Mu header if provided
            # TODO: inject custom_units into vendor prop 0x043D if provided

            # Recompute CRC
            payload = bytes(device_block[12:])
            crc = crc16_kermit(payload)
            struct.pack_into('>H', device_block, 10, crc)

            return bytes(device_block)

    raise ValueError(f"No DEVICE block found in {blank_panx_path}")


# ============================================================
# SCHEDULE Block Writer (simplified)
# ============================================================

def write_schedule_block(instance: int, name: str, default_state: int = 0) -> bytes:
    """Build a SCHEDULE (type 17) block with empty weekly schedule.

    The weekly schedule data is complex — 7 days × time entries.
    This builds a minimal valid block that can be configured in RC Studio.
    """
    records = bytearray(b'\x00\x00\x00')

    records += _rec_uint8(0x0000, 0x1C, 0x71, 0x00)              # description (null)
    # Effective period: a4 FFFFFFFF a4 FFFFFFFF 00
    records += _rec(0x0000, 0x20, 0xA4,
                    bytes([0xFF]*4) + bytes([0xA4]) + bytes([0xFF]*4))
    records += _rec_mu_header(name)                                # Mu name
    records += _rec_bool(0x0000, 0x51, False)                     # out-of-service
    records += _rec_uint8(0x0000, 0x58, 0x21, 0x0A)              # priority = 10
    # Weekly schedule: 7 days, each with empty schedule (b4 08 00 00 00 91 [state] b4 12 00 00 00 00 0f)
    ws_data = bytearray()
    for day in range(5):  # Mon-Fri
        ws_data += bytes([0xB4, 0x08, 0x00, 0x00, 0x00, 0x91, default_state & 0xFF,
                          0xB4, 0x12, 0x00, 0x00, 0x00, 0x00, 0x0F])
    # Sat, Sun: empty
    ws_data += bytes([0x0E, 0x0F, 0x0E, 0x0F])
    records += _rec(0x0000, 0x7B, 0x0E, bytes(ws_data))

    records += _rec_uint8(0x0000, 0xAE, 0x91, default_state)     # schedule-default

    # Vendor
    records += _rec_uint8(0x0004, 0x1D, 0x91, 0x11)              # range = 0x11 (schedule type)

    payload = bytes(records)
    if payload[-1] == 0x00:
        payload = payload[:-1]
    return _build_block(17, instance, payload)


# ============================================================
# MAIN COMPILER LOOP
# ============================================================

# BACnet type IDs for index table
BACNET_TYPE_ID = {
    "AI": 0, "AO": 1, "AV": 2, "BI": 3, "BO": 4, "BV": 5,
    "DEVICE": 8, "LOOP": 12, "MO": 14, "NC_GROUP": 15,
    "PROGRAM": 16, "SCHEDULE": 17, "MV": 19, "TREND": 20,
    "NOTIF_CLS": 26, "NOTIF2": 27, "SYS_GROUP": 141,
}


def _write_index_entry(val0: int, type_id: int, offset: int, count: int) -> bytes:
    """Write a 16-byte index entry as 4 x (LE16_hi, LE16_lo) values."""
    entry = bytearray(16)
    struct.pack_into('<H', entry, 0, (val0 >> 16) & 0xFFFF)
    struct.pack_into('<H', entry, 2, val0 & 0xFFFF)
    struct.pack_into('<H', entry, 4, (type_id >> 16) & 0xFFFF)
    struct.pack_into('<H', entry, 6, type_id & 0xFFFF)
    struct.pack_into('<H', entry, 8, (offset >> 16) & 0xFFFF)
    struct.pack_into('<H', entry, 10, offset & 0xFFFF)
    struct.pack_into('<H', entry, 12, (count >> 16) & 0xFFFF)
    struct.pack_into('<H', entry, 14, count & 0xFFFF)
    return bytes(entry)


def compile_pan(config, blank_path: str) -> bytes:
    """Compile a complete .pan binary file from ControllerConfig.

    Args:
        config: ControllerConfig from the assembler
        blank_path: Path to blank .panx file for the target controller model

    Returns:
        Complete .pan file bytes ready to write to disk.
    """
    from composition.models import ControllerConfig
    from composition.cbas_compiler import compile_bas

    # ----------------------------------------------------------------
    # Step 1: Load blank .panx for DEVICE block
    # ----------------------------------------------------------------
    device_block = write_device_block_from_blank(blank_path)

    # ----------------------------------------------------------------
    # Step 2: Build all blocks grouped by BACnet type
    # ----------------------------------------------------------------
    blocks_by_type = {}  # type_id -> [block_bytes, ...]

    # NC_GROUP — always 3: System, General, Trend
    nc_blocks = [
        write_nc_group_block(0, "System", 0x0D),
        write_nc_group_block(1, "General", 0x0D),
        write_nc_group_block(65, "Trend", 0x0E),
    ]
    blocks_by_type[15] = nc_blocks

    # AI blocks
    ai_blocks = []
    for inp in config.inputs:
        if inp.point_type == "AI":
            b = write_ai_block(inp)
            ai_blocks.append(b)
    if ai_blocks:
        blocks_by_type[0] = ai_blocks

    # AO blocks
    ao_blocks = []
    for out in config.outputs:
        if out.point_type == "AO":
            b = write_ao_block(out)
            ao_blocks.append(b)
    if ao_blocks:
        blocks_by_type[1] = ao_blocks

    # AV blocks
    av_blocks = []
    for val in config.values:
        if val.point_type == "AV":
            b = write_av_block(val)
            av_blocks.append(b)
    if av_blocks:
        blocks_by_type[2] = av_blocks

    # BI blocks
    bi_blocks = []
    for inp in config.inputs:
        if inp.point_type == "BI":
            b = write_bi_block(inp)
            bi_blocks.append(b)
    if bi_blocks:
        blocks_by_type[3] = bi_blocks

    # BO blocks
    bo_blocks = []
    for out in config.outputs:
        if out.point_type == "BO":
            b = write_bo_block(out)
            bo_blocks.append(b)
    if bo_blocks:
        blocks_by_type[4] = bo_blocks

    # BV blocks
    bv_blocks = []
    for val in config.values:
        if val.point_type == "BV":
            b = write_bv_block(val)
            bv_blocks.append(b)
    if bv_blocks:
        blocks_by_type[5] = bv_blocks

    # MV blocks
    mv_blocks = []
    for val in config.values:
        if val.point_type == "MV":
            b = write_mv_block(val)
            mv_blocks.append(b)
    if mv_blocks:
        blocks_by_type[19] = mv_blocks

    # LOOP blocks
    loop_blocks = []
    for loop in config.loops:
        b = write_loop_block(loop)
        loop_blocks.append(b)
    if loop_blocks:
        blocks_by_type[12] = loop_blocks

    # MO blocks — only if config has them
    # (MO is typically from FLEXair blanks, not user-defined)

    # PROGRAM blocks
    prg_blocks = []
    for prg in config.programs:
        bytecode = b''
        if prg.code:
            try:
                bytecode = compile_bas(prg.code)
            except Exception:
                bytecode = b''  # empty shell if compile fails
        b = write_program_block(prg.instance, prg.name, bytecode)
        prg_blocks.append(b)
    if prg_blocks:
        blocks_by_type[16] = prg_blocks

    # SCHEDULE blocks
    sched_blocks = []
    for sched in config.schedules:
        b = write_schedule_block(sched.instance, sched.name)
        sched_blocks.append(b)
    if sched_blocks:
        blocks_by_type[17] = sched_blocks

    # SYS_GROUP blocks (graphic pages + tables)
    sg_blocks = []
    for sg in config.system_groups:
        b = write_sys_group_block(1, sg.name)
        sg_blocks.append(b)
    for tbl in config.tables:
        xy_data = [(float(p[0]), float(p[1])) for p in tbl.data_points]
        unit_code = UNIT_CODES.get(tbl.output_units, 0x5F)
        b = write_sys_group_block(tbl.instance, tbl.name,
                                   unit_code=unit_code, table_data=xy_data)
        sg_blocks.append(b)
    if sg_blocks:
        blocks_by_type[141] = sg_blocks

    # TREND blocks
    trend_blocks = []
    for trend in config.trends:
        b = write_trend_block(trend.instance)
        trend_blocks.append(b)
    if trend_blocks:
        blocks_by_type[20] = trend_blocks

    # DEVICE block (always present)
    blocks_by_type[8] = [device_block]

    # ----------------------------------------------------------------
    # Step 3: Calculate layout — index table + block offsets
    # ----------------------------------------------------------------
    # Type order for index (matches RC Studio convention)
    type_order = [15, 0, 1, 2, 3, 4, 5, 8, 12, 14, 16, 17, 19, 20, 26, 27, 141]
    present_types = [t for t in type_order if t in blocks_by_type]

    num_types = len(present_types)

    # Index table: entry 0 at 0x400, then entries at 0x440, 0x480, ...
    # Entry 0 holds num_types AND first type data
    # Subsequent entries at 0x440 + (i-1) * 0x40
    index_size = 0x40 * num_types  # entry 0 + (num_types-1) subsequent entries
    blocks_start = 0x400 + index_size

    # Calculate block offsets
    type_offsets = {}  # type_id -> file offset
    current_offset = blocks_start
    for tid in present_types:
        type_offsets[tid] = current_offset
        for blk in blocks_by_type[tid]:
            current_offset += len(blk)

    # ----------------------------------------------------------------
    # Step 4: Build the file
    # ----------------------------------------------------------------
    file_data = bytearray()

    # Header (12 bytes)
    header = bytearray(12)
    struct.pack_into('<I', header, 0, 0x0023BAC0)  # magic
    struct.pack_into('<I', header, 4, 100)          # device ID (default 100)
    # Section offset — from blanks: varies, use a safe default
    struct.pack_into('<I', header, 8, 0x002F0000)
    file_data += header

    # Zero padding from 0x0C to 0x3FF
    file_data += bytes(0x400 - 12)

    # Index table
    for idx, tid in enumerate(present_types):
        count = len(blocks_by_type[tid])
        offset = type_offsets[tid]
        if idx == 0:
            # Entry 0: num_types in val0, plus first type data
            entry = _write_index_entry(num_types, tid, offset, count)
        else:
            entry = _write_index_entry(0, tid, offset, count)

        # Pad entry to 0x40 bytes
        file_data += entry + bytes(0x40 - 16)

    # Blocks in type order
    for tid in present_types:
        for blk in blocks_by_type[tid]:
            file_data += blk

    return bytes(file_data)
