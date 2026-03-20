"""
SBS Composition Engine v2 — PAN Binary Builder

Constructs Reliable Controls .pan binary files.
Two modes:
  1. Seed-based: Takes a PFG seed and injects compiled program bytecode
  2. From-scratch: Builds complete .pan from blank template + ControllerConfig

.pan Binary Format (fully reverse-engineered):
  Header (12 bytes):
    [0:4]  Magic: 0xC0BA2300 (LE) = 0x0023BAC0
    [4:8]  Device Instance ID (LE uint32)
    [8:12] Section offset (LE uint32, typically 0x200000)

  Index Table (at offset 0x400, entries every 0x40 bytes):
    Entry format: 4x (LE16_high, LE16_low) = 4x 32-bit values
    [val0] [type] [offset] [count]
    First entry (at 0x400): val0 = number of subsequent type entries

  Object Blocks (self-contained per-object):
    [LE16 size] [00 00] [BE16 size] [ObjID_BE32] [CRC_BE16]
    [pre-Mu template data] [Mu header] [name] [properties]
    Block total = size + 2
    CRC-16/KERMIT covers block[4:size+2] with bytes[10:12]=00

  Mu Header: 4D 75 [name_len+1] 00 [name_bytes] 00
"""

import struct
import re
import zipfile
import io
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from composition.models import ControllerConfig
from composition.cbas_compiler import compile_bas
from composition.pan_checksum import crc16_kermit, get_init_for_model


# BACnet Object Type IDs
BACNET_TYPE = {
    "AI": 0, "AO": 1, "AV": 2, "BI": 3, "BO": 4, "BV": 5,
    "CALENDAR": 6, "COMMAND": 7, "DEVICE": 8, "EVENT": 9,
    "FILE": 10, "GROUP": 11, "LOOP": 12, "MULTI_INPUT": 13,
    "MO": 14, "NOTIFICATION": 15, "PROGRAM": 16, "SCHEDULE": 17,
    "TREND": 20, "MV": 19, "NC_GROUP": 15, "SYS_GROUP": 141,
    "NOTIF_CLS": 26,
}

# RC Studio range codes
RANGE_CODES = {
    "Off/On": 0, "Normal/Alarm": 0, "Clean/Dirty": 0, "Close/Open": 0,
    "Stop/Start": 2,
    "10K -40 ->250": 3,
    "0 ->100% (0-5V)": 1,
    "0 ->100% (0-10V)": 2,
    "0.0 ->100%": 3,
    "Table1": 32, "Table2": 33, "Table3": 34, "Table4": 35, "Table5": 36,
}

UNIT_CODES = {
    "°F": 64, "%": 98, "WC": 195, "ppm": 96, "CFM": 84,
    "FPM": 78, "BTU/lb": 26, "Min.": 72, "#": 95, "Sec": 73,
    "GPM": 82, "PSI": 56, "": 95,
}


def encode_objid(type_name: str, instance: int) -> bytes:
    """Encode a BACnet Object Identifier as 4 bytes big-endian."""
    type_num = BACNET_TYPE.get(type_name, 0)
    val = (type_num << 22) | (instance & 0x3FFFFF)
    return struct.pack('>I', val)


def _compute_block_crc(block: bytearray, controller_model: str = "MPS") -> int:
    """Compute CRC for a block. CRC covers block[4:] with bytes[10:12]=00."""
    size = struct.unpack_from('<H', block, 0)[0]
    total = size + 2
    crc_data = bytearray(block[4:total])
    crc_data[6] = 0
    crc_data[7] = 0
    init = get_init_for_model(controller_model)
    return crc16_kermit(bytes(crc_data), init)


def _build_block_header(size: int, type_name: str, instance: int) -> bytes:
    """Build the 12-byte block header."""
    header = bytearray(12)
    # LE16 size
    struct.pack_into('<H', header, 0, size)
    # Padding
    header[2] = 0; header[3] = 0
    # BE16 size (bytes 4-5)
    struct.pack_into('>H', header, 4, size)
    # ObjID BE32 (bytes 6-9)
    type_num = BACNET_TYPE.get(type_name, 0)
    objid = (type_num << 22) | (instance & 0x3FFFFF)
    struct.pack_into('>I', header, 6, objid)
    # CRC placeholder (bytes 10-11) — filled in later
    header[10] = 0; header[11] = 0
    return bytes(header)


def _build_mu_header(name: str) -> bytes:
    """Build Mu object header: 4D 75 [name_len+1] 00 [name] 00"""
    name_bytes = name.encode('utf-8')
    name_field_len = len(name_bytes) + 1  # +1 for null terminator
    return b'\x4d\x75' + bytes([name_field_len & 0xFF]) + b'\x00' + name_bytes + b'\x00'


def _build_description_block(description: str) -> bytes:
    """Build description property: 1c 75 [len] 00 [text] 00"""
    if not description:
        return b''
    desc_bytes = description.encode('utf-8')
    # 1c 75 [len_byte] 00 [desc_text] 00
    return bytes([0x1c, 0x75, len(desc_bytes) + 1, 0x00]) + desc_bytes + b'\x00'


# ============================================================
# Per-type block builders
# ============================================================

def build_ai_block(name: str, instance: int, range_code: int = 3,
                   description: str = "", controller_model: str = "MPS") -> bytes:
    """Build a complete AI object block."""
    mu = _build_mu_header(name)
    # AI Mu properties: just range
    mu_props = bytes([0x08, 0x00, 0x00, 0x04, 0x1D, 0x91, range_code & 0xFF])

    # Pre-Mu template data
    pre_mu = bytes([0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00])
    desc_block = _build_description_block(description)
    if desc_block:
        pre_mu += desc_block + bytes([0x1a, 0x00, 0x00, 0x00])
    else:
        pre_mu += bytes([0x1a, 0x00, 0x00, 0x00])

    # Calculate total content
    content = pre_mu + mu + mu_props
    size = 12 + len(content) - 2  # size = total - 2
    size = len(content) + 10  # header(12) - 2 + content

    header = _build_block_header(size, "AI", instance)
    block = bytearray(header + content)

    # Compute CRC
    crc = _compute_block_crc(block, controller_model)
    struct.pack_into('>H', block, 10, crc)

    return bytes(block)


def build_ao_block(name: str, instance: int, range_code: int = 3,
                   description: str = "", controller_model: str = "MPS") -> bytes:
    """Build a complete AO object block."""
    mu = _build_mu_header(name)
    mu_props = bytes([0x08, 0x00, 0x00, 0x04, 0x1D, 0x91, range_code & 0xFF])

    pre_mu = bytes([0x00, 0x00, 0x00, 0x1b, 0x00, 0x00, 0x00])
    desc_block = _build_description_block(description)
    if desc_block:
        pre_mu += desc_block + bytes([0x1a, 0x00, 0x00, 0x00])
    else:
        pre_mu += bytes([0x1a, 0x00, 0x00, 0x00])

    content = pre_mu + mu + mu_props
    size = len(content) + 10

    header = _build_block_header(size, "AO", instance)
    block = bytearray(header + content)
    crc = _compute_block_crc(block, controller_model)
    struct.pack_into('>H', block, 10, crc)
    return bytes(block)


def build_av_block(name: str, instance: int, range_code: int = 3,
                   description: str = "", present_value: float = 0.0,
                   controller_model: str = "MPS") -> bytes:
    """Build a complete AV object block."""
    mu = _build_mu_header(name)
    # AV Mu props: range + ObjID allocation + present value
    mu_props = bytearray()
    mu_props += bytes([0x08, 0x00, 0x00, 0x04, 0x1D, 0x91, range_code & 0xFF])

    pre_mu = bytes([0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00])
    desc_block = _build_description_block(description)
    if desc_block:
        pre_mu += desc_block + bytes([0x1e, 0x00, 0x00, 0x00])
    else:
        pre_mu += bytes([0x1e, 0x00, 0x00, 0x00])

    content = pre_mu + mu + bytes(mu_props)
    size = len(content) + 10

    header = _build_block_header(size, "AV", instance)
    block = bytearray(header + content)
    crc = _compute_block_crc(block, controller_model)
    struct.pack_into('>H', block, 10, crc)
    return bytes(block)


def build_bi_block(name: str, instance: int, range_code: int = 0,
                   description: str = "", controller_model: str = "MPS") -> bytes:
    """Build a complete BI object block."""
    mu = _build_mu_header(name)
    mu_props = bytes([0x08, 0x00, 0x00, 0x04, 0x1D, 0x91, range_code & 0xFF])

    pre_mu = bytes([0x00, 0x00, 0x00, 0x1a, 0x00, 0x00, 0x00])
    desc_block = _build_description_block(description)
    if desc_block:
        pre_mu += desc_block + bytes([0x1b, 0x00, 0x00, 0x00])
    else:
        pre_mu += bytes([0x1b, 0x00, 0x00, 0x00])

    content = pre_mu + mu + mu_props
    size = len(content) + 10

    header = _build_block_header(size, "BI", instance)
    block = bytearray(header + content)
    crc = _compute_block_crc(block, controller_model)
    struct.pack_into('>H', block, 10, crc)
    return bytes(block)


def build_bo_block(name: str, instance: int, range_code: int = 2,
                   description: str = "", controller_model: str = "MPS") -> bytes:
    """Build a complete BO object block."""
    mu = _build_mu_header(name)
    mu_props = bytes([0x08, 0x00, 0x00, 0x04, 0x1D, 0x91, range_code & 0xFF])

    pre_mu = bytes([0x00, 0x00, 0x00, 0x1b, 0x00, 0x00, 0x00])
    desc_block = _build_description_block(description)
    if desc_block:
        pre_mu += desc_block + bytes([0x19, 0x00, 0x00, 0x00])
    else:
        pre_mu += bytes([0x19, 0x00, 0x00, 0x00])

    content = pre_mu + mu + mu_props
    size = len(content) + 10

    header = _build_block_header(size, "BO", instance)
    block = bytearray(header + content)
    crc = _compute_block_crc(block, controller_model)
    struct.pack_into('>H', block, 10, crc)
    return bytes(block)


def build_bv_block(name: str, instance: int, range_code: int = 0x11,
                   description: str = "", controller_model: str = "MPS") -> bytes:
    """Build a complete BV object block."""
    mu = _build_mu_header(name)
    mu_props = bytes([0x08, 0x00, 0x00, 0x04, 0x1D, 0x91, range_code & 0xFF])

    pre_mu = bytes([0x00, 0x00, 0x00, 0x1f, 0x00, 0x00, 0x00])
    desc_block = _build_description_block(description)
    if desc_block:
        pre_mu += desc_block + bytes([0x25, 0x00, 0x00, 0x00])
    else:
        pre_mu += bytes([0x25, 0x00, 0x00, 0x00])

    content = pre_mu + mu + mu_props
    size = len(content) + 10

    header = _build_block_header(size, "BV", instance)
    block = bytearray(header + content)
    crc = _compute_block_crc(block, controller_model)
    struct.pack_into('>H', block, 10, crc)
    return bytes(block)


def build_mv_block(name: str, instance: int, num_states: int = 8,
                   state_text: str = "", description: str = "",
                   controller_model: str = "MPS") -> bytes:
    """Build a complete MV object block."""
    mu = _build_mu_header(name)
    mu_props = bytes([0x08, 0x00, 0x00, 0x04, 0x1D, 0x91, 0xF0])

    pre_mu = bytes([0x00, 0x00, 0x00, 0x4b, 0x00, 0x00, 0x00])
    # MV has state text in description area
    if state_text:
        desc_block = _build_description_block(state_text)
    elif description:
        desc_block = _build_description_block(description)
    else:
        desc_block = b''
    if desc_block:
        pre_mu += desc_block + bytes([0x1f, 0x00, 0x00, 0x00])
    else:
        pre_mu += bytes([0x1f, 0x00, 0x00, 0x00])

    content = pre_mu + mu + mu_props
    size = len(content) + 10

    header = _build_block_header(size, "MV", instance)
    block = bytearray(header + content)
    crc = _compute_block_crc(block, controller_model)
    struct.pack_into('>H', block, 10, crc)
    return bytes(block)


def build_loop_block(name: str, instance: int,
                     p_band: float = 12.0, integral: float = 40.0,
                     action: str = "direct", description: str = "",
                     controller_model: str = "MPS") -> bytes:
    """Build a complete LOOP object block."""
    mu = _build_mu_header(name)

    # LOOP Mu properties: P-band and integral
    mu_props = bytearray()
    # P-band: 0B 00 00 00 5D 44 [float_BE]
    mu_props += bytes([0x0B, 0x00, 0x00, 0x00, 0x5D, 0x44])
    mu_props += struct.pack('>f', p_band)
    # Integral: 04 4D 44 [float_BE]
    mu_props += bytes([0x04, 0x4D, 0x44])
    mu_props += struct.pack('>f', integral)

    # Pre-Mu template: action, deadband, bias, P constant, P units
    pre_mu = bytearray()
    pre_mu += bytes([0x00, 0x00, 0x00, 0x08])
    # Action: prop 02 91 [val]
    action_val = 0x01 if action == "direct" else 0x00
    pre_mu += bytes([0x00, 0x00, 0x00, 0x02, 0x91, action_val])
    # Deadband: prop 0E 44 0.0
    pre_mu += bytes([0x00, 0x0b, 0x00, 0x00, 0x00, 0x0e, 0x44])
    pre_mu += struct.pack('>f', 0.0)
    # Bias: prop 1A 44 0.0
    pre_mu += bytes([0x00, 0x0b, 0x00, 0x00, 0x00, 0x1a, 0x44])
    pre_mu += struct.pack('>f', 0.0)
    # P constant: prop 31 44 [p_band]
    pre_mu += bytes([0x00, 0x0b, 0x00, 0x00, 0x00, 0x31, 0x44])
    pre_mu += struct.pack('>f', p_band)
    # P units: prop 32 91 48
    pre_mu += bytes([0x00, 0x08, 0x00, 0x00, 0x00, 0x32, 0x91, 0x48])
    # Description
    desc_block = _build_description_block(description)
    if desc_block:
        pre_mu += bytes([0x00])
        pre_mu += desc_block
    pre_mu += bytes([0x00, 0x23, 0x00, 0x00, 0x00])

    content = bytes(pre_mu) + mu + bytes(mu_props)
    size = len(content) + 10

    header = _build_block_header(size, "LOOP", instance)
    block = bytearray(header + content)
    crc = _compute_block_crc(block, controller_model)
    struct.pack_into('>H', block, 10, crc)
    return bytes(block)


def build_program_block(name: str, instance: int, code: str = "",
                        enabled: bool = True, description: str = "",
                        controller_model: str = "MPS") -> bytes:
    """
    Build a complete PROGRAM object block with compiled bytecode.
    This is the critical function — compiles .bas code to CBAS bytecode
    and embeds it in the block.
    """
    # Compile the program code
    if code and code.strip():
        bytecode = compile_bas(code)
    else:
        bytecode = b''

    mu = _build_mu_header(name)

    # Program Mu properties
    mu_props = bytearray()

    if bytecode:
        # Status flags
        mu_props += bytes([0x08, 0x00, 0x00, 0x00, 0x1c, 0x71, 0x00])
        # Program stop flag
        mu_props += bytes([0x00, 0x07, 0x00, 0x00, 0x04, 0x41, 0x10])
        # Code property: 04 29
        mu_props += bytes([0x04, 0x29])
        # Code header: 65 fe [size_BE16] 91 [state]
        mu_props += bytes([0x65, 0xfe])
        mu_props += struct.pack('>H', len(bytecode))
        state = 0x02 if enabled else 0x00
        mu_props += bytes([0x91, state])
        # Bytecode
        mu_props += bytecode
        # Program enabled: 08 00 00 04 0a 91 [01/00]
        mu_props += bytes([0x08, 0x00, 0x00, 0x04, 0x0a, 0x91])
        mu_props += bytes([0x01 if enabled else 0x00])
    else:
        # Empty program
        mu_props += bytes([0x08, 0x00, 0x00, 0x04, 0x0a, 0x91])
        mu_props += bytes([0x01 if enabled else 0x00])
        mu_props += bytes([0x00, 0x08, 0x00, 0x00, 0x04, 0x29, 0x61])
        mu_props += bytes([0x00, 0x00, 0x07, 0x00, 0x00, 0x04, 0x41, 0x10])

    # Pre-Mu template: description
    pre_mu = bytes([0x00, 0x00, 0x00, 0x43, 0x00, 0x00, 0x00])
    desc_block = _build_description_block(description)
    if desc_block:
        pre_mu += desc_block + bytes([0x21, 0x00, 0x00, 0x00])
    else:
        pre_mu += bytes([0x21, 0x00, 0x00, 0x00])

    content = pre_mu + mu + bytes(mu_props)
    size = len(content) + 10

    header = _build_block_header(size, "PROGRAM", instance)
    block = bytearray(header + content)
    crc = _compute_block_crc(block, controller_model)
    struct.pack_into('>H', block, 10, crc)
    return bytes(block)


def build_schedule_block(name: str, instance: int, description: str = "",
                         controller_model: str = "MPS") -> bytes:
    """Build a SCHEDULE object block."""
    mu = _build_mu_header(name)
    mu_props = bytes([0x08, 0x00, 0x00, 0x04, 0x1D, 0x91, 0x00])

    pre_mu = bytes([0x00, 0x00, 0x00, 0x25, 0x00, 0x00, 0x00])
    desc_block = _build_description_block(description)
    if desc_block:
        pre_mu += desc_block + bytes([0x1e, 0x00, 0x00, 0x00])
    else:
        pre_mu += bytes([0x1e, 0x00, 0x00, 0x00])

    content = pre_mu + mu + mu_props
    size = len(content) + 10

    header = _build_block_header(size, "SCHEDULE", instance)
    block = bytearray(header + content)
    crc = _compute_block_crc(block, controller_model)
    struct.pack_into('>H', block, 10, crc)
    return bytes(block)


def build_sysgroup_block(name: str, instance: int, description: str = "",
                         controller_model: str = "MPS") -> bytes:
    """Build a SYSTEM GROUP (type 141) object block."""
    mu = _build_mu_header(name)
    mu_props = bytes([0x08, 0x00, 0x00, 0x04, 0x1D, 0x91, 0x00])

    pre_mu = bytes([0x00, 0x00, 0x00, 0x1b, 0x00, 0x00, 0x00])
    desc_block = _build_description_block(description)
    if desc_block:
        pre_mu += desc_block + bytes([0x1e, 0x00, 0x00, 0x00])
    else:
        pre_mu += bytes([0x1e, 0x00, 0x00, 0x00])

    content = pre_mu + mu + mu_props
    size = len(content) + 10

    header = _build_block_header(size, "SYS_GROUP", instance)
    block = bytearray(header + content)
    crc = _compute_block_crc(block, controller_model)
    struct.pack_into('>H', block, 10, crc)
    return bytes(block)


# ============================================================
# Index table helpers
# ============================================================

def _write_index_entry(data: bytearray, idx_offset: int,
                       val0: int, type_id: int, offset: int, count: int):
    """Write one 16-byte index entry at idx_offset."""
    # Each value stored as (LE16_high, LE16_low) = 4 bytes
    for i, val in enumerate([val0, type_id, offset, count]):
        hi = (val >> 16) & 0xFFFF
        lo = val & 0xFFFF
        struct.pack_into('<H', data, idx_offset + i * 4, hi)
        struct.pack_into('<H', data, idx_offset + i * 4 + 2, lo)


def _read_index_entry(data: bytes, idx_offset: int) -> Tuple[int, int, int, int]:
    """Read one 16-byte index entry: returns (val0, type, offset, count)."""
    vals = []
    for i in range(4):
        hi = struct.unpack_from('<H', data, idx_offset + i * 4)[0]
        lo = struct.unpack_from('<H', data, idx_offset + i * 4 + 2)[0]
        vals.append((hi << 16) | lo)
    return tuple(vals)


# ============================================================
# Seed-based approach: inject programs into PFG seed
# ============================================================

def inject_programs_into_seed(seed_data: bytes, config: ControllerConfig,
                               controller_model: str = "MPS") -> bytes:
    """
    Take a PFG-generated seed .pan and inject compiled program bytecode.

    The seed has all objects visible but programs are empty shells.
    This function:
    1. Finds the PROGRAM type section in the seed
    2. Builds new program blocks with compiled bytecode
    3. Replaces the program section
    4. Updates index offsets for subsequent type sections
    """
    data = bytearray(seed_data)

    # Parse index table
    first_entry = _read_index_entry(data, 0x400)
    num_types = first_entry[0]

    entries = [first_entry]
    for i in range(num_types):
        entry = _read_index_entry(data, 0x440 + i * 0x40)
        entries.append(entry)

    # Find PROGRAM entry and entries after it
    prg_entry_idx = None
    prg_idx_offset = None
    for i, (v0, type_id, offset, count) in enumerate(entries):
        if type_id == 16:  # PROGRAM
            prg_entry_idx = i
            prg_idx_offset = 0x400 + i * 0x40 if i == 0 else 0x440 + (i - 1) * 0x40
            break

    if prg_entry_idx is None:
        return bytes(data)  # No programs in seed

    _, _, prg_offset, prg_count = entries[prg_entry_idx]

    # Find the end of the program section (start of next type section)
    # Walk through all program blocks
    pos = prg_offset
    for _ in range(prg_count):
        if pos + 2 >= len(data):
            break
        block_size = struct.unpack_from('<H', data, pos)[0] + 2
        pos += block_size
    prg_section_end = pos
    old_prg_section_size = prg_section_end - prg_offset

    # Build new program blocks with bytecode
    new_program_blocks = bytearray()
    for prg in sorted(config.programs, key=lambda p: p.instance):
        code = prg.code or ""
        block = build_program_block(
            name=f"{{device-name}}-{prg.name}",
            instance=prg.instance,
            code=code,
            enabled=prg.enabled,
            description=prg.description or "",
            controller_model=controller_model,
        )
        new_program_blocks += block

    new_prg_section_size = len(new_program_blocks)
    size_diff = new_prg_section_size - old_prg_section_size

    # Replace program section
    result = bytearray(data[:prg_offset]) + new_program_blocks + bytearray(data[prg_section_end:])

    # Update count in program index entry
    _write_index_entry(result, prg_idx_offset,
                       0, 16, prg_offset, len(config.programs))

    # Update offsets for type entries AFTER programs
    for i in range(prg_entry_idx + 1, len(entries)):
        v0, type_id, offset, count = entries[i]
        if offset > prg_offset:
            new_offset = offset + size_diff
            entry_offset = 0x400 + i * 0x40 if i == 0 else 0x440 + (i - 1) * 0x40
            _write_index_entry(result, entry_offset, v0, type_id, new_offset, count)

    return bytes(result)


# ============================================================
# From-scratch approach: build complete .pan from blank
# ============================================================

def _load_blank(controller_model: str) -> bytes:
    """Load the blank .panx for a controller model."""
    from composition.assembler import CONTROLLER_SPECS

    spec = CONTROLLER_SPECS.get(controller_model, CONTROLLER_SPECS.get("MPS"))
    family = spec.get("family", "MACH-ProSys")

    # Map family to blank directory name pattern
    blanks_dir = Path('/srv/dfa/shared/files/vendors/reliable/blanks/')

    # Try exact match first, then fuzzy
    candidates = []
    for d in blanks_dir.iterdir():
        if d.is_dir() and family.replace(' ', '-') in d.name:
            # Prefer -88 variant (most I/O)
            candidates.append(d)

    if not candidates:
        candidates = [d for d in blanks_dir.iterdir() if d.is_dir() and 'ProSys' in d.name]

    # Sort to prefer -88 (most I/O capacity)
    candidates.sort(key=lambda d: ('88' in d.name, d.name), reverse=True)

    if candidates:
        panx_files = list(candidates[0].glob('*.panx'))
        if panx_files:
            with zipfile.ZipFile(panx_files[0]) as z:
                pan_names = [n for n in z.namelist() if n.endswith('.pan')]
                if pan_names:
                    return z.read(pan_names[0])

    # Fallback: return minimal header
    data = bytearray(1024)
    struct.pack_into('<I', data, 0, 0x0023BAC0)
    struct.pack_into('<I', data, 4, 1000)
    struct.pack_into('<I', data, 8, 0x200000)
    return bytes(data)


def build_pan_from_config(config: ControllerConfig,
                          device_id: int = 1000,
                          controller_model: str = "auto") -> bytes:
    """
    Build a complete .pan binary from a ControllerConfig.
    Uses blank template as base, adds all object blocks.
    """
    model = config.controller_model if controller_model == "auto" else controller_model
    if not model or model == "auto":
        model = "MPS"

    # Load blank template
    blank_raw = bytearray(_load_blank(model))

    # Extract NC + DEVICE blocks from the blank
    # These need to be preserved and relocated after the index table
    existing_block_data = {}  # type_id -> list of block bytes
    first_entry = _read_index_entry(blank_raw, 0x400)
    num_existing = first_entry[0]

    valid_types = {0,1,2,3,4,5,8,12,15,16,17,19,20,26,68,141}
    existing_type_info = []  # [(type_id, count, [block_bytes])]

    # First entry is NC_GROUP (type 15)
    if first_entry[1] in valid_types and first_entry[3] < 10000 and first_entry[2] < len(blank_raw):
        blocks = []
        pos = first_entry[2]
        for _ in range(first_entry[3]):
            if pos + 2 < len(blank_raw):
                bs = struct.unpack_from('<H', blank_raw, pos)[0] + 2
                blocks.append(bytes(blank_raw[pos:pos+bs]))
                pos += bs
        existing_type_info.append((first_entry[1], first_entry[3], blocks))

    # Subsequent entries (DEVICE etc.)
    for i in range(min(num_existing, 5)):
        e = _read_index_entry(blank_raw, 0x440 + i * 0x40)
        if e[1] in valid_types and 0 < e[3] < 10000 and e[2] < len(blank_raw):
            blocks = []
            pos = e[2]
            for _ in range(e[3]):
                if pos + 2 < len(blank_raw):
                    bs = struct.unpack_from('<H', blank_raw, pos)[0] + 2
                    blocks.append(bytes(blank_raw[pos:pos+bs]))
                    pos += bs
            existing_type_info.append((e[1], e[3], blocks))

    # Build a fresh file with proper layout
    # Header (12 bytes) + zeros (to 0x400) + index table + data
    blank = bytearray(0x800)  # Reserve space for header + index
    # Copy header from blank
    blank[:12] = blank_raw[:12]
    # Set device ID
    struct.pack_into('<I', blank, 4, device_id)

    # Data starts after index table (0x800 = safe starting point)
    new_section_start = 0x800

    # Place existing blocks (NC + DEVICE) first
    current_offset = new_section_start
    relocated_existing = []  # [(type_id, offset, count)]
    for type_id, count, blocks in existing_type_info:
        offset = current_offset
        for b in blocks:
            while len(blank) < current_offset + len(b):
                blank.extend(b'\x00' * 256)
            blank[current_offset:current_offset+len(b)] = b
            current_offset += len(b)
        relocated_existing.append((type_id, offset, count))

    max_offset = current_offset

    # Build object blocks for each type
    type_sections = {}  # type_id -> (blocks_bytes, count)

    # AI blocks
    ai_blocks = bytearray()
    ai_count = 0
    for pt in config.inputs:
        if pt.point_type == "AI":
            rc = RANGE_CODES.get(pt.range_code, 3)
            block = build_ai_block(
                f"{{device-name}}-{pt.name}", pt.row, rc,
                pt.description or "", model)
            ai_blocks += block
            ai_count += 1
    if ai_count:
        type_sections[0] = (bytes(ai_blocks), ai_count)

    # AO blocks
    ao_blocks = bytearray()
    ao_count = 0
    for pt in config.outputs:
        if pt.point_type == "AO":
            rc = RANGE_CODES.get(pt.range_code, 3)
            block = build_ao_block(
                f"{{device-name}}-{pt.name}", pt.row, rc,
                pt.description or "", model)
            ao_blocks += block
            ao_count += 1
    if ao_count:
        type_sections[1] = (bytes(ao_blocks), ao_count)

    # AV blocks
    av_blocks = bytearray()
    av_count = 0
    for val in config.values:
        if val.point_type == "AV":
            pv = float(val.default) if isinstance(val.default, (int, float)) else 0.0
            block = build_av_block(
                f"{{device-name}}-{val.name}", val.instance, 3,
                val.description or "", pv, model)
            av_blocks += block
            av_count += 1
    if av_count:
        type_sections[2] = (bytes(av_blocks), av_count)

    # BI blocks
    bi_blocks = bytearray()
    bi_count = 0
    for pt in config.inputs:
        if pt.point_type == "BI":
            rc = RANGE_CODES.get(pt.range_code, 0)
            block = build_bi_block(
                f"{{device-name}}-{pt.name}", pt.row, rc,
                pt.description or "", model)
            bi_blocks += block
            bi_count += 1
    if bi_count:
        type_sections[3] = (bytes(bi_blocks), bi_count)

    # BO blocks
    bo_blocks = bytearray()
    bo_count = 0
    for pt in config.outputs:
        if pt.point_type == "BO":
            rc = RANGE_CODES.get(pt.range_code, 2)
            block = build_bo_block(
                f"{{device-name}}-{pt.name}", pt.row, rc,
                pt.description or "", model)
            bo_blocks += block
            bo_count += 1
    if bo_count:
        type_sections[4] = (bytes(bo_blocks), bo_count)

    # BV blocks
    bv_blocks = bytearray()
    bv_count = 0
    for val in config.values:
        if val.point_type == "BV":
            block = build_bv_block(
                f"{{device-name}}-{val.name}", val.instance, 0x11,
                val.description or "", model)
            bv_blocks += block
            bv_count += 1
    if bv_count:
        type_sections[5] = (bytes(bv_blocks), bv_count)

    # MV blocks
    mv_blocks = bytearray()
    mv_count = 0
    for val in config.values:
        if val.point_type == "MV":
            states_text = "/".join(f"{i+1}-{s}" for i, s in enumerate(val.states)) if val.states else ""
            block = build_mv_block(
                f"{{device-name}}-{val.name}", val.instance,
                len(val.states) if val.states else 8,
                states_text, val.description or "", model)
            mv_blocks += block
            mv_count += 1
    if mv_count:
        type_sections[19] = (bytes(mv_blocks), mv_count)

    # LOOP blocks
    loop_blocks = bytearray()
    loop_count = 0
    for lp in config.loops:
        block = build_loop_block(
            f"{{device-name}}-{lp.name}", lp.instance,
            lp.p_band, lp.integral, lp.action,
            lp.description or "", model)
        loop_blocks += block
        loop_count += 1
    if loop_count:
        type_sections[12] = (bytes(loop_blocks), loop_count)

    # SCHEDULE blocks
    sched_blocks = bytearray()
    sched_count = 0
    for sch in config.schedules:
        block = build_schedule_block(
            f"{{device-name}}-{sch.name}", sch.instance,
            sch.description or "", model)
        sched_blocks += block
        sched_count += 1
    if sched_count:
        type_sections[17] = (bytes(sched_blocks), sched_count)

    # PROGRAM blocks (with compiled bytecode!)
    prg_blocks = bytearray()
    prg_count = 0
    for prg in config.programs:
        code = prg.code or ""
        block = build_program_block(
            f"{{device-name}}-{prg.name}", prg.instance,
            code, prg.enabled, prg.description or "", model)
        prg_blocks += block
        prg_count += 1
    if prg_count:
        type_sections[16] = (bytes(prg_blocks), prg_count)

    # SYSTEM GROUP blocks
    sg_blocks = bytearray()
    sg_count = 0
    for i, sg in enumerate(config.system_groups):
        block = build_sysgroup_block(
            f"{{device-name}}-{sg.name}", i + 1,
            sg.description or "", model)
        sg_blocks += block
        sg_count += 1
    if sg_count:
        type_sections[141] = (bytes(sg_blocks), sg_count)

    # Assemble the file
    # Keep blank's header + index area + NC + DEVICE blocks
    # Then append our new type sections

    # New type sections start after existing blocks
    new_section_start = max_offset

    # Order types for output (matches seed order)
    type_order = [0, 1, 2, 3, 4, 5, 19, 12, 17, 16, 141]

    # Build new index entries
    all_new_entries = []
    current_offset = new_section_start

    for type_id in type_order:
        if type_id in type_sections:
            section_data, count = type_sections[type_id]
            all_new_entries.append((type_id, current_offset, count))
            current_offset += len(section_data)

    # Total type entries (excluding the first/header entry)
    num_subsequent = len(relocated_existing) - 1 + len(all_new_entries)
    # -1 because the first relocated entry (NC_GROUP) is the header entry

    # First entry is always NC_GROUP (type 15)
    nc_entry = relocated_existing[0] if relocated_existing else (15, new_section_start, 3)
    _write_index_entry(blank, 0x400,
                       num_subsequent,
                       nc_entry[0], nc_entry[1], nc_entry[2])

    # Write remaining existing entries (DEVICE etc.)
    entry_num = 0
    for type_id, offset, count in relocated_existing[1:]:
        idx_offset = 0x440 + entry_num * 0x40
        _write_index_entry(blank, idx_offset, 0, type_id, offset, count)
        entry_num += 1

    # Write new type entries
    for type_id, offset, count in all_new_entries:
        idx_offset = 0x440 + entry_num * 0x40
        _write_index_entry(blank, idx_offset, 0, type_id, offset, count)
        entry_num += 1

    # Ensure blank is large enough to hold all data
    while len(blank) < new_section_start:
        blank.extend(b'\x00')

    # Append all section data
    result = bytearray(blank[:new_section_start])
    for type_id in type_order:
        if type_id in type_sections:
            result += type_sections[type_id][0]

    return bytes(result)


def build_pan_file(config: ControllerConfig, output_path: str,
                   device_id: int = 1000) -> int:
    """Build and save a .pan file. Returns file size."""
    pan_data = build_pan_from_config(config, device_id)
    with open(output_path, 'wb') as f:
        f.write(pan_data)
    return len(pan_data)


# ============================================================
# Seed + Fill approach (uses PFG seed + data filler + program injection)
# ============================================================

def build_from_seed(seed_path: str, config: ControllerConfig,
                    output_path: str, controller_model: str = "MPS") -> int:
    """
    Build a .pan from a PFG seed:
    1. Fill ranges, loop tuning, etc. (pan_filler)
    2. Inject compiled programs
    3. Save

    Returns file size.
    """
    from composition.pan_filler import fill_pan

    seed_data = Path(seed_path).read_bytes()

    # Fill data (ranges, loop tuning, etc.)
    filled = fill_pan(seed_data, config)

    # Inject compiled programs
    result = inject_programs_into_seed(filled, config, controller_model)

    Path(output_path).write_bytes(result)
    return len(result)


# ============================================================
# Test
# ============================================================

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from composition.assembler import assemble
    from composition.program_loader import inject_program_code
    from composition.module_registry import STANDARD_CONFIGS

    # Build SBS-AHU-101 (basic VAV AHU)
    std = STANDARD_CONFIGS["SBS-AHU-101"]
    config = assemble(std["modules"])
    inject_program_code(config)

    print(f"Config: {len(config.inputs)} inputs, {len(config.outputs)} outputs")
    print(f"  {len(config.values)} values, {len(config.loops)} loops")
    print(f"  {len(config.programs)} programs, {len(config.schedules)} schedules")
    print(f"  Controller: {config.controller_model}")

    # Method 1: Build from scratch
    out_path = "/srv/dfa/drops/SBS-AHU-101-SCRATCH.pan"
    size = build_pan_file(config, out_path, device_id=1000)
    print(f"\nFrom scratch: {out_path} ({size:,} bytes)")

    # Show program sizes
    for prg in config.programs:
        if prg.code:
            bytecode = compile_bas(prg.code)
            print(f"  {prg.name}: {len(prg.code)} chars source -> {len(bytecode)} bytes bytecode")

    # Method 2: If seed exists, use seed-based approach
    seed_path = "/srv/dfa/shared/files/vendors/reliable/seeds/MACH-ProSys-88-AHU114.pan"
    if os.path.exists(seed_path):
        out_path2 = "/srv/dfa/drops/SBS-AHU-101-SEED.pan"
        size2 = build_from_seed(seed_path, config, out_path2, "MPS")
        print(f"\nFrom seed: {out_path2} ({size2:,} bytes)")
