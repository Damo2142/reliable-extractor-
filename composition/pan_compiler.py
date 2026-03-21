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
    total_len = 1 + len(body)
    return bytes([total_len]) + body


def _rec_desc(desc: str) -> bytes:
    """Description property: ctx=0x0000, prop=0x1C, tag=0x75."""
    s = desc.encode('utf-8')
    return _rec(0x0000, 0x1C, 0x75, bytes([len(s) + 1, 0x00]) + s)


def _rec_mu(name: str) -> bytes:
    """Mu name property: ctx=0x0000, prop=0x4D, tag=0x75."""
    s = name.encode('ascii', errors='replace')
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


def _seed_payload(records: list) -> bytes:
    """Build payload from list of record bytes. Strips trailing 0x00 from last record."""
    payload = bytearray(b'\x00\x00\x00')
    for rec in records:
        payload += rec
    if payload[-1] == 0x00:
        payload = payload[:-1]
    return bytes(payload)


# ============================================================
# SEED BLOCK WRITERS
# ============================================================

def write_av_seed(instance: int, name: str, desc: str) -> bytes:
    """AV seed: desc + name + range=0x03."""
    return _build_block(2, instance, _seed_payload([
        _rec_desc(desc), _rec_mu(name), _rec_range(0x03)
    ]))


def write_ai_seed(instance: int, name: str, desc: str) -> bytes:
    """AI seed: desc + name + range=0x03."""
    return _build_block(0, instance, _seed_payload([
        _rec_desc(desc), _rec_mu(name), _rec_range(0x03)
    ]))


def write_ao_seed(instance: int, name: str, desc: str) -> bytes:
    """AO seed: desc + name + range=0x03."""
    return _build_block(1, instance, _seed_payload([
        _rec_desc(desc), _rec_mu(name), _rec_range(0x03)
    ]))


def write_bi_seed(instance: int, name: str, desc: str) -> bytes:
    """BI seed: desc + name + range=0x00."""
    return _build_block(3, instance, _seed_payload([
        _rec_desc(desc), _rec_mu(name), _rec_range(0x00)
    ]))


def write_bo_seed(instance: int, name: str, desc: str) -> bytes:
    """BO seed: desc + name + range=0x02."""
    return _build_block(4, instance, _seed_payload([
        _rec_desc(desc), _rec_mu(name), _rec_range(0x02)
    ]))


def write_bv_seed(instance: int, name: str, desc: str) -> bytes:
    """BV seed: desc + name + range=0x03."""
    return _build_block(5, instance, _seed_payload([
        _rec_desc(desc), _rec_mu(name), _rec_range(0x03)
    ]))


def write_mv_seed(instance: int, name: str, states_desc: str) -> bytes:
    """MV seed: states_as_desc + name + range=0x08.
    states_desc = "1-Occupied/2-Bypass/3-Standby/4-Unoccupied" etc.
    """
    return _build_block(19, instance, _seed_payload([
        _rec_desc(states_desc), _rec_mu(name), _rec_range(0x08)
    ]))


def write_loop_seed(instance: int, name: str, action: str,
                    p_band: float, setpoint: float = 0.0,
                    derivative: float = 0.0) -> bytes:
    """LOOP seed: action + deriv + bias + output + out_units + name + setpoint + p_band."""
    action_val = 0x00 if action == "-" else 0x01
    return _build_block(12, instance, _seed_payload([
        _rec_uint8(0x0000, 0x02, 0x91, action_val),     # action
        _rec_float(0x0000, 0x0E, derivative),             # derivative
        _rec_float(0x0000, 0x1A, 0.0),                    # bias
        _rec_float(0x0000, 0x31, 0.0),                    # output
        _rec_uint8(0x0000, 0x32, 0x91, 0x48),            # output-units (72=min)
        _rec_mu(name),                                     # name
        _rec_float(0x0000, 0x5D, setpoint),                # setpoint
        _rec_float(0x0004, 0x4D, p_band),                  # p-band (vendor)
    ]))


def write_prg_seed(instance: int, name: str, desc: str) -> bytes:
    """PRG seed: desc + name. No bytecode."""
    return _build_block(16, instance, _seed_payload([
        _rec_desc(desc), _rec_mu(name)
    ]))


def write_sched_seed(instance: int, name: str) -> bytes:
    """SCHED seed: name only."""
    return _build_block(17, instance, _seed_payload([
        _rec_mu(name)
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
    """16-byte index entry: 4 x 32-bit as (LE16_hi, LE16_lo) pairs."""
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
