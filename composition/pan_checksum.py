"""
SBS Composition Engine v2 — .pan File Checksum

CRACKED: CRC-16/KERMIT (poly 0x8408) with controller-family init values.

The .pan binary format uses CRC-16/KERMIT for integrity checking.
Each object type block has a 12-byte header where bytes 10-11 contain
the CRC. The CRC covers block[4:block_size] with bytes 10-11 zeroed.

The init value depends on the controller family:
  0x954D — MACH-Pro1, Pro2, ProCom, ProSys, ProWebCom, ProWebSys, ProZone, ProLight
  0x864D — MACH-ProAir (all variants)
  0x9576 — MACH-ProView LCD (all variants)
  0xB44D — RC-FLEXair, RC-FLEXone (all variants)
"""

# Controller family to CRC init value
CRC_INIT = {
    # MACH-Pro family (0x954D)
    "MACH-Pro1-44": 0x954D, "MACH-Pro1-48": 0x954D,
    "MACH-Pro1-84": 0x954D, "MACH-Pro1-88": 0x954D,
    "MACH-Pro2-88": 0x954D, "MACH-Pro2-8C": 0x954D,
    "MACH-Pro2-C8": 0x954D, "MACH-Pro2-CC": 0x954D,
    "MACH-ProCom-88": 0x954D, "MACH-ProCom-8C": 0x954D,
    "MACH-ProCom-C8": 0x954D, "MACH-ProCom-CC": 0x954D,
    "MACH-ProSys-88": 0x954D, "MACH-ProSys-8C": 0x954D,
    "MACH-ProSys-C8": 0x954D, "MACH-ProSys-CC": 0x954D,
    "MACH-ProWebCom-88": 0x954D, "MACH-ProWebSys-88": 0x954D,
    "MACH-ProZone-44": 0x954D, "MACH-ProZone-48": 0x954D,
    "MACH-ProZone-84": 0x954D, "MACH-ProZone-88": 0x954D,
    "MACH-ProLight": 0x954D,
    # MACH-ProAir family (0x864D)
    "MACH-ProAir-08": 0x864D, "MACH-ProAir-08B1": 0x864D,
    "MACH-ProAir-08U1": 0x864D, "MACH-ProAir-18": 0x864D,
    "MACH-ProAir-18B1": 0x864D, "MACH-ProAir-18U1": 0x864D,
    "MACH-ProAir-28": 0x864D, "MACH-ProAir-28B1": 0x864D,
    "MACH-ProAir-28U1": 0x864D,
    # MACH-ProView LCD family (0x9576)
    "MACH-ProView LCD": 0x9576, "MACH-ProView LCD OD": 0x9576,
    "MACH-ProView LCD-R": 0x9576,
    # RC-FLEX family (0xB44D)
    "RC-FLEXair-12-A-F": 0xB44D, "RC-FLEXair-12-A-M": 0xB44D,
    "RC-FLEXair-34-A-F": 0xB44D, "RC-FLEXair-34-A-M": 0xB44D,
    "RC-FLEXair-35-A-F": 0xB44D, "RC-FLEXair-35-A-M": 0xB44D,
    "RC-FLEXair-36-A-F": 0xB44D, "RC-FLEXair-36-A-M": 0xB44D,
    "RC-FLEXone-B4B": 0xB44D, "RC-FLEXone-B6B": 0xB44D,
    "RC-FLEXone-B8B": 0xB44D,
}

# Simplified family lookup
FAMILY_INIT = {
    "Pro1": 0x954D, "Pro2": 0x954D, "ProCom": 0x954D,
    "ProSys": 0x954D, "ProWebCom": 0x954D, "ProWebSys": 0x954D,
    "ProZone": 0x954D, "ProLight": 0x954D,
    "ProAir": 0x864D,
    "ProView": 0x9576,
    "FLEXair": 0xB44D, "FLEXone": 0xB44D,
    # Shorthand IDs from our controller defs
    "MPS": 0x954D, "MPWS": 0x954D, "MP2": 0x954D, "MP1": 0x954D,
    "MPC": 0x954D, "MPWC": 0x954D, "MPZ": 0x954D,
    "MPA": 0x864D, "MPV-LCD": 0x9576,
    "RCFA": 0xB44D, "RCFO": 0xB44D,
}


def crc16_kermit(data: bytes, init: int = 0x0000) -> int:
    """Compute CRC-16/KERMIT (poly 0x8408, reflected)."""
    crc = init
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return crc


def compute_block_checksum(block_data: bytes, controller_model: str) -> int:
    """
    Compute the CRC checksum for a .pan block.
    
    Args:
        block_data: The COMPLETE block (header + template + Mu objects)
        controller_model: Controller model name (e.g. "MPS", "RCFA")
    
    Returns:
        16-bit CRC value to store at block bytes 10-11 (big-endian)
    """
    init = get_init_for_model(controller_model)
    
    # CRC covers block[4:] with bytes 10-11 zeroed
    data = bytearray(block_data[4:])
    data[6] = 0   # byte 10 of block = byte 6 of data
    data[7] = 0   # byte 11 of block = byte 7 of data
    
    return crc16_kermit(bytes(data), init)


def get_init_for_model(model: str) -> int:
    """Get the CRC init value for a controller model."""
    # Try exact match first
    if model in CRC_INIT:
        return CRC_INIT[model]
    # Try family match
    if model in FAMILY_INIT:
        return FAMILY_INIT[model]
    # Try partial match
    for key, val in FAMILY_INIT.items():
        if key.lower() in model.lower() or model.lower() in key.lower():
            return val
    # Default to MACH-Pro family
    return 0x954D


def extract_init_from_pan(pan_data: bytes) -> int:
    """
    Extract the CRC init value from an existing .pan file.
    Useful for unknown controller models.
    """
    import re
    
    # Find the first block with a non-zero checksum
    idx = 0x0400
    mu_positions = sorted(set(m.start() for m in re.finditer(b'\x4d\x75', pan_data)))
    if not mu_positions:
        return 0x954D
    
    while idx + 64 < mu_positions[0]:
        block = pan_data[idx:idx+16]
        if any(block[:16]):
            obj_type = block[6] | (block[7] << 8)
            offset = block[10] | (block[11] << 8)
            count = block[14] | (block[15] << 8)
            
            if count > 0 and offset < len(pan_data):
                block_size = pan_data[offset] + 2
                if offset + block_size <= len(pan_data):
                    stored_crc = (pan_data[offset+10] << 8) | pan_data[offset+11]
                    if stored_crc != 0:
                        # Brute force the init
                        block_data = pan_data[offset:offset+block_size]
                        data = bytearray(block_data[4:])
                        data[6] = 0; data[7] = 0
                        
                        for init in range(0x10000):
                            if crc16_kermit(bytes(data), init) == stored_crc:
                                return init
        idx += 64
    
    return 0x954D
