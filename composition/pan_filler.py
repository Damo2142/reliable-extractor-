"""
SBS Composition Engine v2 — Pan Data Filler

Fills real engineering data into a PFG-generated seed .pan file.
After modifying block data, recomputes CRC using the block's original init.

IMPORTANT: Each object block has its own CRC-16/KERMIT checksum that covers
bytes 4 through size+2 (with CRC field zeroed). The init value is per-block
and must be extracted from the original block before modification.
"""

import struct
import re
from pathlib import Path
from composition.models import ControllerConfig
from composition.pan_checksum import crc16_kermit


# Range code mapping
RANGE_MAP = {
    "10K -40 ->250": 3, "Off/On": 0, "Normal/Alarm": 0,
    "Clean/Dirty": 0, "Close/Open": 0,
    "0.0 ->100%": 3, "Stop/Start": 2,
    "Table1": 32, "Table2": 33, "Table3": 34, "Table4": 35, "Table5": 36,
    "0 ->100% (0-5V)": 1, "0 ->100% (0-10V)": 2,
}


def _step_zeros(init: int, n: int) -> int:
    """Process n zero bytes through CRC-16/KERMIT."""
    crc = init
    for _ in range(n):
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return crc


def _find_block_init(block: bytes) -> int:
    """Find CRC init using CRC linearity (instant, no brute force)."""
    stored_crc = (block[10] << 8) | block[11]
    crc_data = bytearray(block[4:])
    crc_data[6] = 0
    crc_data[7] = 0
    data_bytes = bytes(crc_data)
    N = len(data_bytes)

    crc_zero = crc16_kermit(data_bytes, 0)
    target = stored_crc ^ crc_zero

    basis = [_step_zeros(1 << bit, N) for bit in range(16)]

    matrix = []
    for row in range(16):
        val = 0
        for col in range(16):
            if basis[col] & (1 << row):
                val |= (1 << col)
        if target & (1 << row):
            val |= (1 << 16)
        matrix.append(val)

    for col in range(16):
        pivot = None
        for row in range(col, 16):
            if matrix[row] & (1 << col):
                pivot = row
                break
        if pivot is None:
            continue
        matrix[col], matrix[pivot] = matrix[pivot], matrix[col]
        for row in range(16):
            if row != col and matrix[row] & (1 << col):
                matrix[row] ^= matrix[col]

    init = 0
    for col in range(16):
        if matrix[col] & (1 << 16):
            init |= (1 << col)
    return init


def _recompute_block_crc(data: bytearray, block_start: int, init: int):
    """Recompute CRC for a block in-place."""
    size = struct.unpack_from('<H', data, block_start)[0]
    total = size + 2
    crc_data = bytearray(data[block_start + 4:block_start + total])
    crc_data[6] = 0
    crc_data[7] = 0
    crc = crc16_kermit(bytes(crc_data), init)
    struct.pack_into('>H', data, block_start + 10, crc)


def _read_index_entry(data, off):
    """Read index entry."""
    vals = []
    for i in range(4):
        hi = struct.unpack_from('<H', data, off + i * 4)[0]
        lo = struct.unpack_from('<H', data, off + i * 4 + 2)[0]
        vals.append((hi << 16) | lo)
    return vals


def fill_pan(seed_data: bytes, config: ControllerConfig) -> bytes:
    """
    Fill engineering data and recompute CRC for modified blocks.
    """
    data = bytearray(seed_data)

    # Parse index to find all block positions and their inits
    first = _read_index_entry(data, 0x400)
    num_types = first[0]

    # Build a map of every block: position -> (size, init, type_id, instance)
    block_map = {}  # block_start -> (total_size, init, type_id, instance)

    all_entries = [(first[1], first[2], first[3])]
    for i in range(num_types):
        e = _read_index_entry(data, 0x440 + i * 0x40)
        if e[1] < 200 and e[3] < 10000:
            all_entries.append((e[1], e[2], e[3]))

    for type_id, offset, count in all_entries:
        if offset >= len(data) or count >= 10000:
            continue
        pos = offset
        for _ in range(count):
            if pos + 12 >= len(data):
                break
            size = struct.unpack_from('<H', data, pos)[0]
            total = size + 2
            if pos + total > len(data):
                break
            block = bytes(data[pos:pos+total])
            objid = struct.unpack_from('>I', block, 6)[0]
            inst = objid & 0x3FFFFF
            init = _find_block_init(block)
            block_map[pos] = (total, init, type_id, inst)
            pos += total

    # Build Mu name -> block_start lookup
    mu_to_block = {}  # mu_name -> block_start
    for block_start, (total, init, type_id, inst) in block_map.items():
        block = data[block_start:block_start+total]
        mu_off = block.find(b'\x4d\x75')
        if mu_off >= 0:
            nl = block[mu_off+2]
            nm = block[mu_off+4:mu_off+3+nl].decode('utf-8', errors='replace').strip('\x00')
            mu_to_block[nm] = block_start

    # Track which blocks were modified (need CRC recompute)
    modified_blocks = set()

    # Fill input/output ranges
    for pt in list(config.inputs) + list(config.outputs):
        name = f"{{device-name}}-{pt.name}"
        if name not in mu_to_block:
            continue
        bs = mu_to_block[name]
        total = block_map[bs][0]
        rc = RANGE_MAP.get(pt.range_code, 3)

        # Find prop 0x04 0x1D 0x91 within this block
        for i in range(bs, bs + total - 3):
            if data[i] == 0x04 and data[i+1] == 0x1D and data[i+2] == 0x91:
                if data[i+3] != (rc & 0xFF):
                    data[i+3] = rc & 0xFF
                    modified_blocks.add(bs)
                break

    # Fill loop tuning
    for lp in config.loops:
        name = f"{{device-name}}-{lp.name}"
        if name not in mu_to_block:
            continue
        bs = mu_to_block[name]
        total = block_map[bs][0]

        # P-band: [0x5D] [0x44] [4B float BE]
        for i in range(bs, bs + total - 5):
            if data[i] == 0x5D and data[i+1] == 0x44:
                struct.pack_into('>f', data, i+2, lp.p_band)
                modified_blocks.add(bs)
                break

        # Integral: [0x04] [0x4D] [0x44] [4B float BE]
        for i in range(bs, bs + total - 6):
            if data[i] == 0x04 and data[i+1] == 0x4D and data[i+2] == 0x44:
                struct.pack_into('>f', data, i+3, lp.integral)
                modified_blocks.add(bs)
                break

        # Action: [0x02] [0x91] [val]
        for i in range(bs, bs + total - 2):
            if data[i] == 0x02 and data[i+1] == 0x91:
                new_val = 1 if lp.action == "direct" else 0
                if data[i+2] != new_val:
                    data[i+2] = new_val
                    modified_blocks.add(bs)
                break

    # Recompute CRC for all modified blocks
    for bs in modified_blocks:
        total, init, type_id, inst = block_map[bs]
        _recompute_block_crc(data, bs, init)

    return bytes(data)


def fill_pan_file(seed_path: str, config: ControllerConfig, output_path: str):
    """Fill a PFG seed file and save."""
    seed_data = Path(seed_path).read_bytes()
    filled = fill_pan(seed_data, config)
    Path(output_path).write_bytes(filled)
    return len(filled)
