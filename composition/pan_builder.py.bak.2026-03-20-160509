"""
SBS Composition Engine v2 — PAN Binary Builder

Constructs Reliable Controls .pan binary files directly from assembled configs.
No PFG, no Wine, no RC Studio needed.

.pan Binary Format:
  Header (12 bytes):
    [0:4]  Magic: 0x0023BAC0 (little-endian)
    [4:8]  Device Instance ID (little-endian uint32)
    [8:12] Section offset (little-endian uint32) — database size indicator

  Pre-object region:
    Padding/firmware area between header and first object.
    Copied from blank template.

  Objects:
    Each object starts with "Mu" header:
      4D 75 [name_len] 00 [name_bytes] [null_terminator]
    Followed by property blocks:
      [prop_id] [tag] [value_bytes]

  Property Tags:
    0x44 = 4-byte big-endian float
    0x91 = 1-byte unsigned int (BACnet enumerated)
    0x21 = 1-byte unsigned int
    0x10 = boolean false
    0x11 = boolean true
    0x0C = BACnet Object Identifier (4 bytes big-endian)

  Property IDs (common):
    0x1D (29)  = range/sensor-type (Reliable proprietary)
    0x55 (85)  = present-value
    0x51 (81)  = out-of-service
    0x75 (117) = units (BACnet engineering units enum)
    0x16 (22)  = increment/resolution
    0x2D (45)  = max-value
    0x3B (59)  = min-value
    0x68 (104) = relinquish-default
    0x71 (113) = status-flags
    0x48 (72)  = polarity
    0x0A (10)  = program-enabled
"""

import struct
import re
import zipfile
import io
from pathlib import Path
from typing import Optional
from composition.models import ControllerConfig


# BACnet Object Type IDs (for ObjID encoding)
BACNET_TYPE = {
    "AI": 0, "AO": 1, "AV": 2, "BI": 3, "BO": 4, "BV": 5,
    "CALENDAR": 6, "COMMAND": 7, "DEVICE": 8, "EVENT": 9,
    "FILE": 10, "GROUP": 11, "LOOP": 12, "MULTI_INPUT": 13,
    "MO": 14, "NOTIFICATION": 15, "PROGRAM": 16, "SCHEDULE": 17,
    "TREND": 20, "MV": 19,
}

# RC Studio range codes (numeric)
RANGE_CODES = {
    "Off/On": 0, "Normal/Alarm": 0, "Clean/Dirty": 0, "Close/Open": 0,
    "Stop/Start": 2,
    "10K -40 ->250": 3,     # 10K Type 2 thermistor
    "0 ->100% (0-5V)": 1,   # 0-5V
    "0 ->100% (0-10V)": 2,  # 0-10V
    "0.0 ->100%": 3,        # 0-100% analog
    "Table1": 32, "Table2": 33, "Table3": 34, "Table4": 35, "Table5": 36,
}

# BACnet engineering unit codes
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


def build_mu_header(name: str) -> bytes:
    """Build Mu object header: 4D 75 [len] 00 [name] 00"""
    name_bytes = name.encode('utf-8')
    name_len = len(name_bytes) + 1  # +1 for null terminator
    return b'\x4d\x75' + bytes([name_len]) + b'\x00' + name_bytes + b'\x00'


def build_property(prop_id: int, tag: int, value) -> bytes:
    """Build a single property block: [prop_id] [tag] [value_bytes]"""
    if tag == 0x44:  # float
        return bytes([prop_id, 0x44]) + struct.pack('>f', float(value))
    elif tag == 0x91:  # uint8 enumerated
        return bytes([prop_id, 0x91, int(value) & 0xFF])
    elif tag == 0x21:  # uint8
        return bytes([prop_id, 0x21, int(value) & 0xFF])
    elif tag == 0x10:  # bool false
        return bytes([prop_id, 0x10])
    elif tag == 0x11:  # bool true
        return bytes([prop_id, 0x11])
    elif tag == 0x0C:  # ObjID (value should be bytes)
        return bytes([0x0C]) + value
    else:
        return bytes([prop_id, tag])


def build_ai_object(name: str, instance: int, range_code: int = 3,
                    unit_code: int = 64, present_value: float = 0.0,
                    increment: float = 0.1, description: str = "") -> bytes:
    """Build a complete AI (Analog Input) object binary block."""
    data = build_mu_header(name)

    # Standard AI properties (based on analysis of real .pan files)
    props = bytearray()
    # Size marker + padding (observed pattern)
    props += b'\x08\x00\x00'
    # Range/sensor type (prop 0x041D = Reliable proprietary)
    props += bytes([0x04, 0x1D, 0x91, range_code & 0xFF])
    # Padding/structure bytes observed in real files
    props += b'\x50\x01\x00\x00\x01\x50\x00\x00\x00\x04\x34\x3a\x00\x00\x00'
    # Notification class
    props += build_property(0x11, 0x21, 1)
    # Increment (0x16)
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x16, 0x44, increment)
    # High limit (0x19) - not set
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x19, 0x44, 0.0)
    # Description string area
    if description:
        desc_bytes = description.encode('utf-8')[:100]
        props += b'\x00\x1e\x00\x00\x00\x1c\x75'
        props += bytes([len(desc_bytes)])
        props += b'\x00'
        props += desc_bytes
        props += b'\x00'
    # Out-of-service (0x51) = false
    props += build_property(0x51, 0x10, False)
    # Present value (0x55)
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x55, 0x44, present_value)
    # Status flags (0x71)
    props += b'\x00\x08\x00\x00\x00'
    props += build_property(0x71, 0x21, 0)
    # Units (0x75)
    props += b'\x00\x08\x00\x00\x00'
    props += build_property(0x75, 0x91, unit_code)
    # Polarity (0x48)
    props += b'\x00\x08\x00\x00\x00'
    props += build_property(0x48, 0x91, 0)
    # Max value (0x2D)
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x2D, 0x44, 250.0)
    # Min value (0x3B)
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x3B, 0x44, -40.0)
    # Relinquish default (0x68)
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x68, 0x44, 0.0)
    # End marker
    props += b'\x00\x1e\x00\x00\x00'

    return data + bytes(props)


def build_bi_object(name: str, instance: int, range_code: int = 0,
                    present_value: int = 0) -> bytes:
    """Build a complete BI (Binary Input) object binary block."""
    data = build_mu_header(name)
    props = bytearray()
    props += b'\x08\x00\x00\x04\x1D\x91'
    props += bytes([range_code & 0xFF])
    # Out-of-service
    props += b'\x00\x07\x00\x00\x00\x51\x10'
    # Present value
    props += b'\x00\x08\x00\x00\x00\x55'
    props += bytes([0x91 if present_value else 0x91, present_value & 0xFF])
    # Status flags
    props += b'\x00\x08\x00\x00\x00\x71\x21\x00'
    # Polarity
    props += b'\x00\x08\x00\x00\x00\x48\x91\x00'
    # End
    props += b'\x00\x1e\x00\x00\x00'
    return data + bytes(props)


def build_ao_object(name: str, instance: int, range_code: int = 3,
                    unit_code: int = 98, present_value: float = 0.0,
                    min_v: float = 2.0, max_v: float = 10.0,
                    relinquish: float = 0.0) -> bytes:
    """Build a complete AO (Analog Output) object binary block."""
    data = build_mu_header(name)
    props = bytearray()
    props += b'\x08\x00\x00\x04\x1D\x91'
    props += bytes([range_code & 0xFF])
    # Out-of-service
    props += b'\x00\x07\x00\x00\x00\x51\x10'
    # Present value
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x55, 0x44, present_value)
    # Status flags
    props += b'\x00\x08\x00\x00\x00\x71\x21\x00'
    # Units
    props += b'\x00\x08\x00\x00\x00\x75\x91'
    props += bytes([unit_code & 0xFF])
    # Min value (voltage)
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x3B, 0x44, min_v)
    # Max value (voltage)
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x2D, 0x44, max_v)
    # Relinquish default
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x68, 0x44, relinquish)
    # Polarity
    props += b'\x00\x08\x00\x00\x00\x48\x91\x00'
    # Increment
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x16, 0x44, 0.1)
    # End
    props += b'\x00\x1e\x00\x00\x00'
    return data + bytes(props)


def build_bo_object(name: str, instance: int, range_code: int = 2,
                    present_value: int = 0) -> bytes:
    """Build a complete BO (Binary Output) object binary block."""
    data = build_mu_header(name)
    props = bytearray()
    props += b'\x08\x00\x00\x04\x1D\x91'
    props += bytes([range_code & 0xFF])
    # Out-of-service
    props += b'\x00\x07\x00\x00\x00\x51\x10'
    # Present value
    props += b'\x00\x08\x00\x00\x00\x55\x91'
    props += bytes([present_value & 0xFF])
    # Status flags
    props += b'\x00\x08\x00\x00\x00\x71\x21\x00'
    # Relinquish default
    props += b'\x00\x08\x00\x00\x00\x68\x91\x00'
    # Polarity
    props += b'\x00\x08\x00\x00\x00\x48\x91\x00'
    # End
    props += b'\x00\x1e\x00\x00\x00'
    return data + bytes(props)


def build_av_object(name: str, instance: int, present_value: float = 0.0,
                    unit_code: int = 95, relinquish: float = 0.0,
                    description: str = "") -> bytes:
    """Build a complete AV (Analog Value) object binary block."""
    data = build_mu_header(name)
    props = bytearray()
    # Range (prop 0x041D)
    props += b'\x08\x00\x00\x04\x1D\x91\x02'
    # Padding observed in real files
    props += b'\x29\x00\x00\x00\x00\x29\x00\x80\x00'
    # Present value
    props += build_property(0x55, 0x44, present_value)
    # Units
    if unit_code:
        props += b'\x00\x08\x00\x00\x00\x75\x91'
        props += bytes([unit_code & 0xFF])
    # Relinquish default
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x68, 0x44, relinquish)
    # End
    props += b'\x00\x15\x00\x00\x00'
    return data + bytes(props)


def build_bv_object(name: str, instance: int, present_value: bool = False) -> bytes:
    """Build a complete BV (Binary Value) object binary block."""
    data = build_mu_header(name)
    props = bytearray()
    props += b'\x08\x00\x00\x04\x1D\x91\x11'
    # Padding
    props += b'\x2d\x00\x00\x00\x00\x2d\x01\x40\x00'
    # Present value
    if present_value:
        props += build_property(0x55, 0x11, True)
    else:
        props += build_property(0x55, 0x10, False)
    # End
    props += b'\x00\x19\x00\x00\x00'
    return data + bytes(props)


def build_mv_object(name: str, instance: int, present_value: int = 1,
                    num_states: int = 8, description: str = "") -> bytes:
    """Build a complete MV (Multi-State Value) object binary block."""
    data = build_mu_header(name)
    props = bytearray()
    props += b'\x08\x00\x00\x04\x1D\x91'
    props += bytes([0xF0])  # MV range code
    # Padding
    props += b'\x2c\x00\x00\x00\x00\x2c'
    props += bytes([(num_states & 0xFF)])
    props += b'\xc0\x00'
    # Present value
    props += build_property(0x55, 0x91, present_value)
    # End
    props += b'\x00\x18\x00\x00\x00'
    return data + bytes(props)


def build_loop_object(name: str, instance: int,
                      p_band: float = 12.0, integral: float = 40.0,
                      derivative: float = 0.0, action: str = "direct") -> bytes:
    """Build a LOOP object."""
    data = build_mu_header(name)
    props = bytearray()
    # Proportional (prop 0x5D = 93)
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x5D, 0x44, p_band)
    # Integral constant (prop 0x4D = 77 — observed as integral in real files)
    props += b'\x00\x0b\x00\x00\x04\x4D'
    props += struct.pack('>f', integral)
    # Derivative
    props += b'\x00'
    # Action: 0=reverse, 1=direct (prop 0x02)
    action_val = 1 if action == "direct" else 0
    props += b'\x69\x00\x00\x00\x00\x69\x03\x00\x00'
    props += b'\x02\x83\xae\x00\x00\x00'
    props += build_property(0x02, 0x91, action_val)
    # Deadband (prop 0x0E)
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x0E, 0x44, 0.0)
    # Bias
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x1A, 0x44, 0.0)
    # Proportional constant (prop 0x31)
    props += b'\x00\x0b\x00\x00\x00'
    props += build_property(0x31, 0x44, p_band)
    # Proportional units (prop 0x32)
    props += b'\x00\x08\x00\x00\x00'
    props += build_property(0x32, 0x91, 0x47)  # minutes
    # End
    props += b'\x00\x16\x00\x00\x00'
    return data + bytes(props)


def build_program_object(name: str, instance: int, code: str = "",
                         enabled: bool = True) -> bytes:
    """Build a PROGRAM object with embedded Control-BASIC code."""
    data = build_mu_header(name)
    props = bytearray()

    # Compile the .bas code into the binary program format
    # The code is stored as tokenized lines after some header bytes
    code_bytes = _compile_bas(code)

    # Program header
    props += struct.pack('>H', len(code_bytes))  # code size
    props += b'\x00\x00\x04\x29'  # program object marker
    # Enabled flag (prop 0x0A)
    if enabled:
        props += b'\x65\xfe'
        props += struct.pack('>H', len(code_bytes))
        props += build_property(0x0A, 0x91, 2)  # 2 = running
    else:
        props += b'\x65\xfe'
        props += struct.pack('>H', len(code_bytes))
        props += build_property(0x0A, 0x91, 0)  # 0 = stopped

    # Embedded code
    props += code_bytes

    return data + bytes(props)


def _compile_bas(code: str) -> bytes:
    """
    Convert Control-BASIC source code to the binary token format.

    For now, store as ASCII text with line markers.
    RC Studio stores programs as semi-tokenized text where:
    - Line numbers become 2-byte markers
    - Keywords may be tokenized
    - References to objects use ObjID encoding

    This is a simplified version that stores readable text.
    RC Studio can accept this format for import.
    """
    if not code:
        return b'\x00'

    lines = code.strip().split('\n')
    result = bytearray()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Extract line number if present
        parts = line.split(None, 1)
        if parts and parts[0].isdigit():
            line_num = int(parts[0])
            line_text = parts[1] if len(parts) > 1 else ""
        else:
            line_num = 0
            line_text = line

        # Line format: [line_num as 2 bytes] [line_len] [text bytes]
        text_bytes = line_text.encode('utf-8')
        result += struct.pack('>H', line_num)
        result += bytes([len(text_bytes)])
        result += text_bytes

    return bytes(result)


def build_pan_from_config(config: ControllerConfig,
                          blank_pan_path: Optional[Path] = None,
                          device_id: int = 1000) -> bytes:
    """
    Build a complete .pan binary file from an assembled ControllerConfig.

    If blank_pan_path is provided, uses it as the base template.
    Otherwise constructs from scratch.
    """
    # Start with blank template or minimal header
    if blank_pan_path:
        if str(blank_pan_path).endswith('.panx'):
            with zipfile.ZipFile(blank_pan_path) as z:
                pan_names = [n for n in z.namelist() if n.endswith('.pan')]
                base_data = bytearray(z.read(pan_names[0]))
        else:
            base_data = bytearray(blank_pan_path.read_bytes())
    else:
        # Minimal header
        base_data = bytearray(2048)
        struct.pack_into('<I', base_data, 0, 0x0023BAC0)  # magic
        struct.pack_into('<I', base_data, 4, device_id)    # device ID
        struct.pack_into('<I', base_data, 8, 0x200000)     # section offset

    # Set device ID
    struct.pack_into('<I', base_data, 4, device_id)

    # Find where to append objects
    # If using a blank, append after the existing content
    # Strip trailing zeros from blank
    end = len(base_data)
    while end > 12 and base_data[end-1] == 0:
        end -= 1
    end = max(end, 1024)  # Keep at least 1K of header

    # Build all objects
    objects_data = bytearray()

    # AI objects (inputs that are analog)
    for pt in config.inputs:
        name = f"{{device-name}}-{pt.name}"
        range_code = RANGE_CODES.get(pt.range_code, 3)
        unit_code = UNIT_CODES.get(pt.units, 95)

        if pt.point_type == "AI":
            objects_data += build_ai_object(name, pt.row, range_code, unit_code)
        elif pt.point_type == "BI":
            objects_data += build_bi_object(name, pt.row, range_code)

    # AO/BO objects (outputs)
    for pt in config.outputs:
        name = f"{{device-name}}-{pt.name}"
        range_code = RANGE_CODES.get(pt.range_code, 3)
        unit_code = UNIT_CODES.get(pt.units, 98)

        if pt.point_type == "AO":
            objects_data += build_ao_object(name, pt.row, range_code, unit_code,
                                            min_v=pt.min_v, max_v=pt.max_v)
        elif pt.point_type == "BO":
            objects_data += build_bo_object(name, pt.row, range_code)

    # AV/BV/MV objects (values)
    for val in config.values:
        name = f"{{device-name}}-{val.name}"

        if val.point_type == "AV":
            unit_code = UNIT_CODES.get(val.units, 95)
            pv = float(val.default) if isinstance(val.default, (int, float)) else 0.0
            objects_data += build_av_object(name, val.instance, pv, unit_code)
        elif val.point_type == "BV":
            pv = bool(val.default) if isinstance(val.default, bool) else False
            objects_data += build_bv_object(name, val.instance, pv)
        elif val.point_type == "MV":
            pv = int(val.default) if isinstance(val.default, int) else 1
            n_states = len(val.states) if val.states else 8
            objects_data += build_mv_object(name, val.instance, pv, n_states)

    # LOOP objects
    for lp in config.loops:
        name = f"{{device-name}}-{lp.name}"
        objects_data += build_loop_object(name, lp.instance,
                                          lp.p_band, lp.integral,
                                          lp.derivative, lp.action)

    # PROGRAM objects
    for prg in config.programs:
        name = f"{{device-name}}-{prg.name}"
        objects_data += build_program_object(name, prg.instance,
                                             prg.code or "", prg.enabled)

    # Append objects to base
    result = base_data[:end] + objects_data

    # Update section offset based on total size
    total_size = len(result)
    # Section offset should accommodate the data
    section_offset = ((total_size // 0x10000) + 1) * 0x10000
    struct.pack_into('<I', result, 8, section_offset)

    return bytes(result)


def build_pan_file(config: ControllerConfig, output_path: str,
                   device_id: int = 1000) -> int:
    """Build and save a .pan file. Returns file size."""
    # Use MPS blank as template
    blank_path = Path('/srv/dfa/shared/files/vendors/reliable/blanks/MACH-ProSys-88/MACH-ProSys-88.panx')
    if not blank_path.exists():
        blank_path = None

    pan_data = build_pan_from_config(config, blank_path, device_id)

    with open(output_path, 'wb') as f:
        f.write(pan_data)

    return len(pan_data)


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from composition.assembler import assemble
    from composition.program_loader import inject_program_code
    from composition.module_registry import STANDARD_CONFIGS

    # Build SBS-AHU-109 (the A201 equivalent)
    std = STANDARD_CONFIGS["SBS-AHU-109"]
    config = assemble(std["modules"])
    inject_program_code(config)

    out_path = "/srv/dfa/drops/SBS-AHU-109-TEST.pan"
    size = build_pan_file(config, out_path, device_id=1000)
    print(f"Built: {out_path} ({size:,} bytes)")
    print(f"Inputs: {len(config.inputs)}, Outputs: {len(config.outputs)}")
    print(f"Values: {len(config.values)}, Loops: {len(config.loops)}")
    print(f"Programs: {len(config.programs)}")

    # Verify by reading it back
    from app.pan_binary import PanBinary
    pan = PanBinary(open(out_path, 'rb').read())
    objs = pan.objects
    print(f"\nVerification: read back {len(objs)} objects")
    for o in objs[:10]:
        print(f"  {o['name']} (PV={o['present_value']})")
    if len(objs) > 10:
        print(f"  ... and {len(objs)-10} more")
