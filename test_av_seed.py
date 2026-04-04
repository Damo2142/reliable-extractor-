#!/usr/bin/env python3
"""Test seed block writers — hex dump for byte-exact comparison against RC Studio."""

import struct
from composition.pan_compiler import (
    write_av_seed, write_ai_seed, write_ao_seed,
    write_bi_seed, write_bo_seed, write_bv_seed,
    write_mv_seed, write_loop_seed,
    write_prg_seed, write_sched_seed,
    write_sys_group_seed, write_nc_group_seed,
    write_notif_cls_seed, crc16_kermit,
)

TYPE_NAMES = {0: "AI", 1: "AO", 2: "AV", 3: "BI", 4: "BO", 5: "BV", 12: "LOOP",
              15: "NC_GROUP", 16: "PRG", 17: "SCHED", 19: "MV", 20: "STL", 26: "NOTIF_CLS", 141: "SYS_GROUP"}


def dump_block(label, block):
    """Helper to dump any block."""
    _size_le = struct.unpack_from('<H', block, 0)[0]
    _size_be = struct.unpack_from('>H', block, 4)[0]
    _objid = struct.unpack_from('>I', block, 6)[0]
    _crc_in = struct.unpack_from('>H', block, 10)[0]
    _crc_calc = crc16_kermit(block[12:])
    _obj_type = (_objid >> 22) & 0x3FF
    _obj_inst = _objid & 0x3FFFFF
    print(f"=== {label} ===")
    print(f"Total block: {len(block)} bytes")
    print(f"Size LE={_size_le}  BE={_size_be}  (should match)")
    print(f"ObjID: 0x{_objid:08X}  type={_obj_type}({TYPE_NAMES.get(_obj_type, '?')}) inst={_obj_inst}")
    print(f"CRC:   0x{_crc_in:04X}  calc=0x{_crc_calc:04X}  {'OK' if _crc_in == _crc_calc else 'MISMATCH'}")
    for off in range(0, len(block), 16):
        row = block[off:off + 16]
        hex_part = ' '.join(f'{b:02X}' for b in row)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in row)
        print(f"  {off:04X}: {hex_part:<48s}  {ascii_part}")
    print()


# === Standard I/O types (desc + name + range) ===
for writer, label, inst, name, desc in [
    (write_av_seed, "AV", 10, "AHU-1.SAT",         "Supply Air Temp"),
    (write_ai_seed, "AI",  1, "AHU-1.MAT",         "Mixed Air Temp"),
    (write_ao_seed, "AO",  1, "AHU-1.CLG-O",       "Cooling Valve Output"),
    (write_bi_seed, "BI",  1, "AHU-1.FAN-STATUS",   "Supply Fan Status"),
    (write_bo_seed, "BO",  1, "AHU-1.FAN-CMD",      "Supply Fan Command"),
    (write_bv_seed, "BV",  1, "AHU-1.FAN-ENABLE",   "Supply Fan Enable"),
    (write_mv_seed, "MV",  1, "AHU-1.OCC-MODE",     "1-Occupied/2-Bypass/3-Standby/4-Unoccupied/5-NSB/6-NSF"),
    (write_prg_seed, "PRG", 1, "AHU-1.AHU-PROGRAM", "AHU Control Program"),
    (write_sys_group_seed, "SYS_GROUP", 1, "AHU-1.GRAPHICS",  "AHU Graphics Page"),
    (write_sys_group_seed, "TABLE",     2, "AHU-1.RESET-TBL", "SAT Reset Table"),
]:
    dump_block(f"{label}{inst}  name={name!r}  desc={desc!r}", writer(inst, name, desc))

# === SCHED — name only ===
dump_block("SCHED1  name='AHU-1.OCC-SCHED'", write_sched_seed(1, "AHU-1.OCC-SCHED"))

# === LOOP — 8 properties ===
dump_block("LOOP1  name='AHU-1.SAT-LOOP'  action=direct  p_band=5.0  integral=40.0",
           write_loop_seed(1, "AHU-1.SAT-LOOP", action="+", p_band=5.0, integral=40.0, derivative=0.0))

# === NC_GROUP — with config (matches reference block 0: NC_0, status=0x04) ===
NC0_CONFIG = bytes.fromhex('01FEB400000000B4173B3B001E22FFFF601F2101108205E0')
dump_block("NC_GROUP0  name='NC_0'  status=0x04  with config",
           write_nc_group_seed(0, "NC_0", 0x04, NC0_CONFIG))

# === NC_GROUP — without config (matches reference block 2: NC_65, status=0x06) ===
dump_block("NC_GROUP65  name='NC_65'  status=0x06  no config",
           write_nc_group_seed(65, "NC_65", 0x06))

# === NOTIF_CLS — name + 0x0485=TRUE ===
dump_block("NOTIF_CLS1  name='{device-name}-SYSTEM'",
           write_notif_cls_seed(1, "{device-name}-SYSTEM"))

# === STL (TREND_LOG) — Polled ===
from composition.pan_compiler import write_stl_block
dump_block("STL1 (Polled)  name='MAT-STL'  mon=AI:5  interval=1800  buffer=512",
           write_stl_block(1, "MAT-STL", logging_type=1,
                           mon_type=0, mon_instance=5,
                           buffer_size=512, log_interval=1800, cov_increment=0.2))

# === STL (TREND_LOG) — COV ===
dump_block("STL20 (COV)  name='SF-S-STL'  mon=BI:1  interval=0  cov_delta=0.2",
           write_stl_block(20, "SF-S-STL", logging_type=2,
                           mon_type=3, mon_instance=1,
                           buffer_size=512, log_interval=0, cov_increment=0.2))

# === ARRAY — must produce NOTHING ===
import composition.pan_compiler as pc
array_writers = [name for name in dir(pc) if 'array' in name.lower() and callable(getattr(pc, name))]
print("=== ARRAY verification ===")
print(f"ARRAY writers found: {array_writers if array_writers else 'NONE'}")
assert not array_writers, f"ARRAY writers should not exist: {array_writers}"
print("CONFIRMED: No ARRAY block writers exist. RC Studio manages ARRAY blocks internally.")
print()
