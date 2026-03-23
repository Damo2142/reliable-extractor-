"""
.pan Intake Tool — Decompile .pan binary into structured data.
Extracts all block types except PRG (programs).
Uses the same TLV format that pan_compiler.py writes.
"""
import struct

# BACnet object type IDs
OBJ_TYPES = {
    0: "AI", 1: "AO", 2: "AV", 3: "BI", 4: "BO", 5: "BV",
    8: "DEVICE", 12: "LOOP", 15: "NC_GROUP", 16: "PRG",
    17: "SCHED", 19: "MV", 20: "STL", 26: "NOTIF_CLS", 141: "TABLE",
}

# Unit code to string (reverse of compiler's UNIT_CODES)
UNIT_NAMES = {
    64: "°F", 98: "%", 117: "BTU/lb", 96: "ppm", 84: "CFM",
    58: "WC", 77: "FPM", 72: "Min.", 73: "Sec", 95: "#",
    62: "W", 18: "Days", 0: "", 29: "%RH", 85: "kW",
}

# Range code to string (reverse of compiler's RANGE_CODES)
RANGE_NAMES = {
    0: "Off/On", 1: "Close/Open", 2: "Stop/Start", 3: "0.0 ->100%",
    4: "Normal/Alarm", 7: "WC", 15: "CFM", 17: "Min.",
    21: "Clean/Dirty", 22: "0 ->100%", 43: "ppm", 58: "BTU/lb",
}


def _parse_tlv_records(payload: bytes) -> dict:
    """Parse TLV property records from a block payload.

    Returns dict of {prop_id: decoded_value}.
    """
    props = {}
    pos = 0
    while pos < len(payload):
        if payload[pos] == 0x00:
            pos += 1
            continue

        total_len = payload[pos]
        # total_len includes itself: actual body = total_len - 1 bytes
        body_len = total_len - 1
        if body_len <= 0 or pos + total_len > len(payload):
            pos += 1
            continue

        rec_data = payload[pos + 1: pos + 1 + body_len]
        pos += total_len

        # Record body from _rec(): [0x00] [ctx_hi] [ctx_lo] [prop] [tag] [val_data] [0x00]
        # prop_id = (ctx_hi << 16) | (ctx_lo << 8) | prop
        # For simple props (ctx=0): prop_id = prop byte (e.g. 0x4D)
        # For extended props (ctx=4): prop_id = 0x0400 | prop (e.g. 0x041D)
        if len(rec_data) < 5:
            continue

        # rec_data[0] = 0x00 separator
        # rec_data[1] = ctx_hi
        # rec_data[2] = ctx_lo
        # rec_data[3] = prop
        # rec_data[4] = tag
        # rec_data[5:] = val_data (may include trailing 0x00)
        ctx_hi = rec_data[1]
        ctx_lo = rec_data[2]
        prop_byte = rec_data[3]
        ctx = (ctx_hi << 8) | ctx_lo
        prop_id = (ctx << 8) | prop_byte if ctx > 0 else prop_byte

        tag = rec_data[4]
        val_data = rec_data[5:]

        # Decode based on tag
        if tag == 0x75:  # string
            if len(val_data) >= 2:
                slen = struct.unpack_from('<H', val_data, 0)[0]
                text = val_data[2:2 + slen].decode('latin1', errors='replace').rstrip('\x00')
                props[prop_id] = text
        elif tag == 0x44:  # float32 BE
            if len(val_data) >= 4:
                props[prop_id] = struct.unpack_from('>f', val_data, 0)[0]
        elif tag == 0x91:  # uint8
            if len(val_data) >= 1:
                props[prop_id] = val_data[0]
        elif tag == 0x21:  # uint8 variant
            if len(val_data) >= 1:
                props[prop_id] = val_data[0]
        elif tag == 0x10:  # bool false
            props[prop_id] = False
        elif tag == 0x11:  # bool true
            props[prop_id] = True
        elif tag == 0x0C:  # ObjID (4B BE)
            if len(val_data) >= 4:
                objid = struct.unpack_from('>I', val_data, 0)[0]
                obj_type = (objid >> 22) & 0x3FF
                obj_inst = objid & 0x3FFFFF
                type_name = OBJ_TYPES.get(obj_type, f"T{obj_type}")
                props[prop_id] = {"type": type_name, "instance": obj_inst, "raw": objid}
        elif tag == 0x71:  # enum
            if len(val_data) >= 1:
                props[prop_id] = val_data[0]
        elif tag == 0x22:  # uint16
            if len(val_data) >= 2:
                props[prop_id] = struct.unpack_from('>H', val_data, 0)[0]
        elif tag == 0x42:  # uint32
            if len(val_data) >= 4:
                props[prop_id] = struct.unpack_from('>I', val_data, 0)[0]
        else:
            # Store raw bytes for unknown tags
            props[prop_id] = {"tag": tag, "raw": val_data.hex()}

    return props


def _read_index_table(data: bytes) -> list:
    """Read the index table starting at 0x0400.

    Returns list of (type_id, offset, count) tuples.
    """
    first_entry = data[0x0400:0x0410]
    num_types = struct.unpack_from('<H', first_entry, 2)[0]

    entries = []
    for i in range(num_types):
        off = 0x0400 + i * 0x40
        entry = data[off:off + 16]

        # Word layout (8 x uint16 LE): w0, w1(num_types slot0), w2, w3(type_id), w4, w5(offset_lo), w6, w7(count)
        type_id = struct.unpack_from('<H', entry, 6)[0]
        off_lo = struct.unpack_from('<H', entry, 10)[0]
        off_hi = entry[12]
        offset = (off_hi << 16) | off_lo
        count = struct.unpack_from('<H', entry, 14)[0]

        entries.append((type_id, offset, count))

    return entries


def decompile_pan(data: bytes) -> dict:
    """Decompile a .pan binary file into structured data.

    Args:
        data: Raw .pan file bytes

    Returns:
        dict with keys: header, inputs, outputs, values, loops, schedules,
        tables, trends, device, block_counts, total_blocks, file_size
    """
    # Header
    magic = struct.unpack_from('<I', data, 0)[0]
    dev_id = struct.unpack_from('<I', data, 4)[0]
    section_off = struct.unpack_from('<I', data, 8)[0]

    header = {
        "magic": f"0x{magic:08X}",
        "dev_id": dev_id,
        "section_offset": section_off,
        "valid": (magic & 0xFFFF) == 0xBAC0,
    }

    # Read index
    index_entries = _read_index_table(data)

    inputs = []
    outputs = []
    values = []
    loops = []
    schedules = []
    tables = []
    trends = []
    device_info = {}
    block_counts = {}
    total_blocks = 0

    for type_id, offset, count in index_entries:
        type_name = OBJ_TYPES.get(type_id, f"T{type_id}")
        block_counts[type_name] = count
        total_blocks += count

        # Walk blocks for this type
        pos = offset
        for _ in range(count):
            if pos + 12 > len(data):
                break

            block_size = struct.unpack_from('<H', data, pos)[0]
            block_total = block_size + 2
            if pos + block_total > len(data):
                break

            objid = struct.unpack_from('>I', data, pos + 6)[0]
            obj_type = (objid >> 22) & 0x3FF
            instance = objid & 0x3FFFFF

            payload = data[pos + 12: pos + block_total]
            props = _parse_tlv_records(payload)

            name = props.get(0x4D, "")
            desc = props.get(0x1C, "")
            units_code = props.get(0x75, 95)
            units_str = UNIT_NAMES.get(units_code, f"#{units_code}") if isinstance(units_code, int) else ""
            range_code = props.get(0x041D, 0)
            range_str = RANGE_NAMES.get(range_code, f"R{range_code}") if isinstance(range_code, int) else ""

            if type_id == 0:  # AI
                inputs.append({
                    "instance": instance, "name": name, "type": "AI",
                    "desc": desc if isinstance(desc, str) else "",
                    "units": units_str, "range": range_str,
                })
            elif type_id == 3:  # BI
                inputs.append({
                    "instance": instance, "name": name, "type": "BI",
                    "desc": desc if isinstance(desc, str) else "",
                    "units": "", "range": range_str,
                })
            elif type_id == 1:  # AO
                outputs.append({
                    "instance": instance, "name": name, "type": "AO",
                    "desc": desc if isinstance(desc, str) else "",
                    "units": units_str, "range": range_str,
                })
            elif type_id == 4:  # BO
                outputs.append({
                    "instance": instance, "name": name, "type": "BO",
                    "desc": desc if isinstance(desc, str) else "",
                    "units": "", "range": range_str,
                })
            elif type_id == 2:  # AV
                pv = props.get(0x55, 0.0)
                values.append({
                    "instance": instance, "name": name, "type": "AV",
                    "desc": desc if isinstance(desc, str) else "",
                    "units": units_str, "range": range_str,
                    "default": round(pv, 4) if isinstance(pv, float) else pv,
                })
            elif type_id == 5:  # BV
                pv = props.get(0x55, 0)
                values.append({
                    "instance": instance, "name": name, "type": "BV",
                    "desc": desc if isinstance(desc, str) else "",
                    "units": "", "range": range_str,
                    "default": pv,
                })
            elif type_id == 19:  # MV
                values.append({
                    "instance": instance, "name": name, "type": "MV",
                    "desc": "",
                    "states": desc if isinstance(desc, str) else "",
                    "units": "", "range": range_str,
                    "default": 0,
                })
            elif type_id == 12:  # LOOP
                action_val = props.get(0x02, 0)
                loops.append({
                    "instance": instance, "name": name,
                    "action": "+" if action_val == 0 else "-",
                    "p_band": round(props.get(0x5D, 0.0), 4) if isinstance(props.get(0x5D, 0), float) else props.get(0x5D, 0),
                    "integral": round(props.get(0x044D, 0.0), 4) if isinstance(props.get(0x044D, 0), float) else props.get(0x044D, 0),
                    "derivative": round(props.get(0x0E, 0.0), 4) if isinstance(props.get(0x0E, 0), float) else props.get(0x0E, 0),
                    "bias": round(props.get(0x1A, 0.0), 4) if isinstance(props.get(0x1A, 0), float) else props.get(0x1A, 0),
                    "output": props.get(0x31, 0.0),
                    "setpoint": round(props.get(0x5D, 0.0), 4) if isinstance(props.get(0x5D, 0), float) else 0,
                })
            elif type_id == 17:  # SCHED
                schedules.append({
                    "instance": instance, "name": name,
                })
            elif type_id == 141:  # TABLE (or SYS_GROUP, but we treat as TABLE)
                xy_data = props.get(0x0428, [])
                num_points = props.get(0x044A, 0)
                tables.append({
                    "instance": instance, "name": name,
                    "desc": desc if isinstance(desc, str) else "",
                    "units": units_str,
                    "num_points": num_points if isinstance(num_points, int) else 0,
                })
            elif type_id == 20:  # STL/TREND
                log_type = props.get(0x48, 1)
                log_interval = props.get(0x80, 900)
                cov_inc = props.get(0x7F, 0.2)
                buf_size = props.get(0x7E, 512)
                monitored = props.get(0x84, {})

                mon_str = ""
                if isinstance(monitored, dict) and "type" in monitored:
                    mon_str = f"{monitored['type']}{monitored['instance']}"

                trends.append({
                    "instance": instance, "name": name,
                    "type": "Polled" if log_type == 1 else "COV",
                    "interval": log_interval if isinstance(log_interval, int) else 0,
                    "cov_delta": round(cov_inc, 4) if isinstance(cov_inc, float) else cov_inc,
                    "buffer": buf_size if isinstance(buf_size, int) else 512,
                    "monitored": mon_str,
                })
            elif type_id == 8:  # DEVICE
                device_info = {
                    "instance": instance,
                    "name": name,
                }

            pos += block_total

    # Sort by instance
    inputs.sort(key=lambda x: x["instance"])
    outputs.sort(key=lambda x: x["instance"])
    values.sort(key=lambda x: x["instance"])
    loops.sort(key=lambda x: x["instance"])
    schedules.sort(key=lambda x: x["instance"])
    tables.sort(key=lambda x: x["instance"])
    trends.sort(key=lambda x: x["instance"])

    return {
        "header": header,
        "inputs": inputs,
        "outputs": outputs,
        "values": values,
        "loops": loops,
        "schedules": schedules,
        "tables": tables,
        "trends": trends,
        "device": device_info,
        "block_counts": block_counts,
        "total_blocks": total_blocks,
        "file_size": len(data),
    }
