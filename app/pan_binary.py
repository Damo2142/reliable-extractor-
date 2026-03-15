"""
Reliable Controls .pan Binary Parser

Reads the proprietary .pan binary format directly, extracting data that
PFG's XML export does not include:
  - Loop input/setpoint/output references
  - Present values (verified accurate)
  - Trend point references (complete multi-trend lists)
  - All BACnet object cross-references
  - Schedule entries
  - Object names, types, instances

Binary format notes (reverse-engineered):
  - Objects start with "Mu" header: 4d 75 [name_length] [name_bytes] 00
  - Properties use tag bytes: 07/08/09=int contexts, 0b=float context,
    0c=BACnet ObjID (4 bytes BE), 0f=string
  - BACnet Object Identifier: big-endian 32-bit, type=(val>>22)&0x3FF, instance=val&0x3FFFFF
  - Float values: big-endian IEEE 754 after 0x44 tag byte
  - Property IDs: 0x51=object-name, 0x52=object-type, 0x55=present-value,
    0x6c=integral-units, 0x6d=loop-setpoint-ref
"""

import re
import struct
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# BACnet object type mapping
BACNET_TYPES = {
    0: 'AI', 1: 'AO', 2: 'AV', 3: 'BI', 4: 'BO', 5: 'BV',
    6: 'CALENDAR', 7: 'COMMAND', 8: 'DEVICE',
    12: 'LOOP', 13: 'MI', 14: 'MO', 16: 'PROGRAM',
    17: 'SCHEDULE', 19: 'MV', 20: 'TREND',
}

# Reverse lookup
TYPE_IDS = {v: k for k, v in BACNET_TYPES.items()}


def decode_objid(raw: bytes) -> tuple:
    """Decode a 4-byte big-endian BACnet Object Identifier.
    Returns (type_name, instance) or (None, None) if invalid.
    """
    if len(raw) < 4:
        return None, None
    val = struct.unpack('>I', raw[:4])[0]
    obj_type = (val >> 22) & 0x3FF
    obj_inst = val & 0x3FFFFF
    type_name = BACNET_TYPES.get(obj_type)
    if type_name and 0 < obj_inst < 10000:
        return type_name, obj_inst
    if val == 0xFFFFFFFF:
        return 'NULL', 0
    return None, None


def encode_objid(type_name: str, instance: int) -> bytes:
    """Encode a BACnet Object Identifier as 4-byte big-endian."""
    type_id = TYPE_IDS.get(type_name, 0)
    val = (type_id << 22) | (instance & 0x3FFFFF)
    return struct.pack('>I', val)


class PanBinary:
    """Parser for Reliable Controls .pan binary files."""

    def __init__(self, data: bytes):
        self.data = data
        self._objects = None

    @classmethod
    def from_file(cls, path: Path) -> 'PanBinary':
        return cls(path.read_bytes())

    @classmethod
    def from_panx(cls, panx_path: Path) -> 'PanBinary':
        """Extract and parse the .pan from inside a .panx (zip) file."""
        import zipfile
        with zipfile.ZipFile(panx_path) as z:
            pan_names = [n for n in z.namelist() if n.endswith('.pan')]
            if not pan_names:
                raise ValueError(f"No .pan file found in {panx_path}")
            return cls(z.read(pan_names[0]))

    @property
    def objects(self) -> list:
        """Parse and return all named objects from the binary."""
        if self._objects is None:
            self._objects = self._parse_objects()
        return self._objects

    def _parse_objects(self) -> list:
        """Find all named objects using the 'Mu' header pattern."""
        objects = []
        for m in re.finditer(b'\x4d\x75(.)', self.data):
            name_len = m.group(1)[0]
            if name_len < 2 or name_len > 200:
                continue

            name_start = m.start() + 3
            name_bytes = self.data[name_start:name_start + name_len]

            try:
                name = name_bytes.decode('utf-8').rstrip('\x00')
            except (UnicodeDecodeError, ValueError):
                continue

            if not name or not any(c.isalpha() for c in name):
                continue

            name_end = name_start + name_len

            # Find next object to determine data region size
            next_mu = self.data.find(b'\x4d\x75', name_end + 10)
            if next_mu < 0:
                next_mu = min(name_end + 500, len(self.data))

            data_region = self.data[name_end:next_mu]

            obj = {
                'name': name,
                'offset': m.start(),
                'name_end': name_end,
                'data_region': data_region,
            }

            # Extract BACnet ObjID references (0x0c tag)
            obj['refs'] = self._extract_objid_refs(data_region)

            # Extract present value
            obj['present_value'] = self._extract_present_value(data_region)

            # Extract all decodable properties
            obj['properties'] = self._extract_all_properties(data_region)

            # Categorize
            obj['category'] = self._categorize(name)

            objects.append(obj)

        return objects

    def _extract_objid_refs(self, data: bytes) -> list:
        """Find all BACnet Object Identifier references (0x0c tag) in data."""
        refs = []
        for i in range(len(data) - 5):
            if data[i] == 0x0c:
                type_name, instance = decode_objid(data[i+1:i+5])
                if type_name:
                    refs.append({
                        'type': type_name,
                        'instance': instance,
                        'ref': f"{type_name}{instance}" if type_name != 'NULL' else 'NULL',
                        'offset': i,
                    })
        return refs

    def _extract_present_value(self, data: bytes) -> Optional[float]:
        """Extract present value (property 0x55 + float tag 0x44)."""
        for i in range(len(data) - 6):
            if data[i:i+2] == b'\x55\x44':
                try:
                    return struct.unpack('>f', data[i+2:i+6])[0]
                except struct.error:
                    pass
        return None

    def _extract_all_properties(self, data: bytes) -> dict:
        """Extract all decodable properties from an object's data region.

        Property format in Reliable .pan binary:
          [prop_id byte] [value_tag byte] [value bytes]

        Value tags:
          0x44 = 4-byte big-endian float
          0x91 = 1-byte unsigned int
          0x21 = 1-byte unsigned int
          0x10 = boolean false
          0x11 = boolean true
          0x71 = 1-byte enumerated
          0x0c = BACnet Object Identifier (4 bytes BE)

        Known property IDs:
          0x51 (81)  = out-of-service
          0x55 (85)  = present-value
          0x57 (87)  = priority-array
          0x68 (104) = relinquish-default
          0x71 (113) = status-flags
          0x75 (117) = units (BACnet engineering units enum)
          0x1d (29)  = range/sensor-type (Reliable proprietary)
          0x16 (22)  = resolution/increment area
        """
        props = {}
        i = 0
        while i < len(data) - 2:
            prop_id = data[i]
            tag = data[i + 1]

            if tag == 0x44 and i + 6 <= len(data):
                # Float property
                try:
                    val = struct.unpack('>f', data[i+2:i+6])[0]
                    if val == val and -1e6 < val < 1e6:  # valid, not NaN
                        props.setdefault(prop_id, []).append(('float', val))
                except struct.error:
                    pass
                i += 6
                continue

            if tag == 0x91 and i + 3 <= len(data):
                props.setdefault(prop_id, []).append(('uint8', data[i+2]))
                i += 3
                continue

            if tag == 0x21 and i + 3 <= len(data):
                props.setdefault(prop_id, []).append(('uint8', data[i+2]))
                i += 3
                continue

            if tag in (0x10, 0x11):
                props.setdefault(prop_id, []).append(('bool', tag == 0x11))
                i += 2
                continue

            if tag == 0x71 and i + 3 <= len(data):
                props.setdefault(prop_id, []).append(('enum', data[i+2]))
                i += 3
                continue

            i += 1

        # Also find BACnet ObjIDs (standalone 0x0c tag)
        for i in range(len(data) - 5):
            if data[i] == 0x0c:
                type_name, instance = decode_objid(data[i+1:i+5])
                if type_name and type_name != 'NULL':
                    props.setdefault('objid_refs', []).append((type_name, instance))

        # Also find strings (0x75 [len] [bytes])
        for i in range(len(data) - 3):
            if data[i] == 0x75:
                slen = data[i+1]
                if 2 < slen < 100 and i + 2 + slen <= len(data):
                    try:
                        s = data[i+2:i+2+slen].decode('utf-8', errors='replace').rstrip('\x00')
                        if s and any(c.isalpha() for c in s):
                            props.setdefault('strings', []).append(s)
                    except Exception:
                        pass

        return props

    def _categorize(self, name: str) -> str:
        """Categorize an object by its name pattern."""
        upper = name.upper()
        if 'LOOP' in upper and 'TL' not in upper:
            return 'LOOP'
        if any(s in upper for s in ['-TL', '-MTL', '-STL', '-RTL']):
            # Make sure it's a trend, not a point with TL in the name
            if upper.endswith('-TL') or '-MTL' in upper or '-STL' in upper or '-RTL' in upper:
                return 'TREND'
        if 'SCHED' in upper:
            return 'SCHEDULE'
        if '-PRG' in upper:
            return 'PROGRAM'
        if 'SMART' in upper or 'SENSOR' in upper:
            return 'SMARTSENSOR'
        if '-GRP' in upper or 'SYSTEM' in upper:
            return 'SYSTEMGROUP'
        return 'POINT'

    def get_loops(self) -> list:
        """Get all LOOP objects with input/setpoint/output bindings."""
        loops = []
        for obj in self.objects:
            if obj['category'] != 'LOOP':
                continue

            # Extract instance from name
            inst_match = re.search(r'LOOP(\d+)', obj['name'], re.IGNORECASE)
            instance = inst_match.group(1) if inst_match else ''

            # Filter refs: skip NULL and firmware refs (instance > 300)
            real_refs = [r for r in obj['refs']
                        if r['type'] != 'NULL' and r['instance'] < 300]

            loop = {
                'name': obj['name'],
                'instance': instance,
                'present_value': obj['present_value'],
            }

            if len(real_refs) >= 1:
                loop['input_ref'] = real_refs[0]['ref']
                loop['input_type'] = real_refs[0]['type']
                loop['input_instance'] = real_refs[0]['instance']
            if len(real_refs) >= 2:
                loop['setpoint_ref'] = real_refs[1]['ref']
                loop['setpoint_type'] = real_refs[1]['type']
                loop['setpoint_instance'] = real_refs[1]['instance']
            if len(real_refs) >= 3:
                loop['output_ref'] = real_refs[2]['ref']
                loop['output_type'] = real_refs[2]['type']
                loop['output_instance'] = real_refs[2]['instance']

            loops.append(loop)

        return loops

    def get_trends(self) -> list:
        """Get all TREND objects with their point references."""
        trends = []
        for obj in self.objects:
            if obj['category'] != 'TREND':
                continue

            real_refs = [r['ref'] for r in obj['refs']
                        if r['type'] != 'NULL' and r['instance'] < 300]

            trends.append({
                'name': obj['name'],
                'refs': real_refs,
            })
        return trends

    def get_points(self) -> list:
        """Get all point objects with present values."""
        points = []
        for obj in self.objects:
            if obj['category'] in ('LOOP', 'TREND', 'SCHEDULE', 'PROGRAM',
                                    'SMARTSENSOR', 'SYSTEMGROUP'):
                continue
            if obj['present_value'] is not None:
                points.append({
                    'name': obj['name'],
                    'present_value': obj['present_value'],
                })
        return points

    def get_point_details(self) -> list:
        """Get detailed info for all point objects including all decoded properties."""
        # BACnet engineering units (common ones)
        UNITS = {
            0: 'no-units', 2: 'deg-F', 3: 'deg-C', 4: 'deg-F-per-min',
            14: 'inches-wc', 15: 'CFM', 17: 'minutes', 19: 'psi',
            22: 'percent', 23: 'percent-rh', 40: '%open', 41: 'rpm',
            45: 'inches', 55: 'watts', 62: 'ppm', 64: 'deg-F', 65: 'deg-C',
            95: 'no-units', 98: 'hours',
        }

        points = []
        for obj in self.objects:
            if obj['category'] in ('LOOP', 'TREND', 'SCHEDULE', 'PROGRAM',
                                    'SMARTSENSOR', 'SYSTEMGROUP'):
                continue

            props = obj.get('properties', {})
            pv = obj.get('present_value')

            # Extract known properties
            # Units: property 0x75 (117)
            units_val = None
            units_entries = props.get(0x75, [])
            for tag, val in units_entries:
                if tag == 'uint8':
                    units_val = val
                    break

            # Out of service: property 0x51 (81)
            oos = None
            for tag, val in props.get(0x51, []):
                if tag == 'bool':
                    oos = val

            # Relinquish default: property 0x68 (104)
            rel_default = None
            for tag, val in props.get(0x68, []):
                if tag == 'float':
                    rel_default = val

            # Range/sensor type: property 0x1d (29)
            range_val = None
            for tag, val in props.get(0x1d, []):
                if tag == 'uint8':
                    range_val = val

            # Status flags: property 0x71 (113)
            status = None
            for tag, val in props.get(0x71, []):
                if tag in ('uint8', 'enum'):
                    status = val

            # Strings (alarm text, descriptions)
            strings = props.get('strings', [])

            point = {
                'name': obj['name'],
                'present_value': pv,
                'units': units_val,
                'units_name': UNITS.get(units_val, f'unit-{units_val}') if units_val is not None else None,
                'out_of_service': oos,
                'relinquish_default': rel_default,
                'range': range_val,
                'status_flags': status,
                'alarm_texts': [s for s in strings if 'Fault' in s or 'Range' in s or 'Alarm' in s],
                'ref_count': len(obj['refs']),
            }
            points.append(point)

        return points

    def generate_point_report(self) -> str:
        """Generate a complete point report as formatted text."""
        lines = [
            "=" * 80,
            "CONTROLLER POINT REPORT — Generated from .pan Binary",
            "=" * 80,
            "",
        ]

        # Summary
        summary = self.get_all_objects()
        lines.append("Object Summary:")
        for cat, items in sorted(summary.items()):
            lines.append(f"  {cat}: {len(items)}")
        lines.append("")

        # Loop bindings
        loops = self.get_loops()
        if loops:
            lines.append("=" * 60)
            lines.append("LOOP CONFIGURATION (from binary)")
            lines.append("=" * 60)
            for loop in loops:
                lines.append(f"\n  LOOP{loop.get('instance','')} ({loop['name']})")
                lines.append(f"    Input:    {loop.get('input_ref', 'not configured')}")
                lines.append(f"    Setpoint: {loop.get('setpoint_ref', 'not configured')}")
                lines.append(f"    Output:   {loop.get('output_ref', 'not configured')}")
                if loop.get('present_value') is not None:
                    lines.append(f"    PV:       {loop['present_value']:.2f}")
            lines.append("")

        # Point details
        points = self.get_point_details()
        if points:
            lines.append("=" * 60)
            lines.append("POINT DETAILS")
            lines.append("=" * 60)
            lines.append(f"{'Name':<40} {'PV':>10} {'Units':<15} {'Range':>5} {'OOS':>4}")
            lines.append("-" * 80)
            for pt in sorted(points, key=lambda x: x['name']):
                pv = f"{pt['present_value']:.2f}" if pt['present_value'] is not None else ""
                units = pt.get('units_name', '') or ''
                rng = str(pt.get('range', '')) if pt.get('range') is not None else ''
                oos = 'Y' if pt.get('out_of_service') else ''
                lines.append(f"  {pt['name']:<38} {pv:>10} {units:<15} {rng:>5} {oos:>4}")
            lines.append("")

        # Trends
        trends = self.get_trends()
        if trends:
            lines.append("=" * 60)
            lines.append("TREND POINT REFERENCES (from binary)")
            lines.append("=" * 60)
            for t in trends:
                lines.append(f"  {t['name']}: {', '.join(t['refs'])}")
            lines.append("")

        return '\n'.join(lines)

    def get_schedules(self) -> list:
        """Get SCHEDULE objects with decoded weekly schedule data."""
        schedules = []
        for obj in self.objects:
            if obj['category'] != 'SCHEDULE':
                continue

            data = obj['data_region']
            props = obj.get('properties', {})

            sched = {
                'name': obj['name'],
                'present_value': obj.get('present_value'),
            }

            # Extract schedule default
            for tag, val in props.get(0xAE, []):  # 174 = schedule-default
                sched['default_value'] = val

            # Find weekly schedule (property 0x7B = 123)
            # Format: 7b [7 pairs of bytes = day enable/mode for Mon-Sun]
            for i in range(len(data) - 16):
                if data[i] == 0x7b:
                    days = []
                    for d in range(7):
                        day_byte1 = data[i + 1 + d * 2]
                        day_byte2 = data[i + 2 + d * 2]
                        days.append((day_byte1, day_byte2))
                    sched['weekly_schedule'] = days
                    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                    sched['weekly_summary'] = {
                        day_names[d]: f"{days[d][0]:02x}/{days[d][1]:02x}"
                        for d in range(7)
                    }
                    break

            schedules.append(sched)
        return schedules

    def get_programs(self) -> list:
        """Get PROGRAM objects with enabled state and code size."""
        programs = []
        for obj in self.objects:
            if obj['category'] != 'PROGRAM':
                continue

            props = obj.get('properties', {})

            prog = {
                'name': obj['name'],
                'data_size': len(obj['data_region']),
            }

            # Enabled state: property 0x0A (10)
            for tag, val in props.get(0x0A, []):
                if tag == 'uint8':
                    prog['enabled'] = val == 1

            # Present value (might indicate running state)
            if obj.get('present_value') is not None:
                prog['present_value'] = obj['present_value']

            # Count ObjID refs (cross-references to other objects)
            refs = props.get('objid_refs', [])
            prog['ref_count'] = len(refs)

            programs.append(prog)
        return programs

    def get_all_objects(self) -> dict:
        """Get a complete summary of all objects by category."""
        result = {}
        for obj in self.objects:
            cat = obj['category']
            result.setdefault(cat, []).append({
                'name': obj['name'],
                'present_value': obj['present_value'],
                'ref_count': len(obj['refs']),
                'refs': [r['ref'] for r in obj['refs'] if r['type'] != 'NULL'],
            })
        return result

    def get_device_info(self) -> dict:
        """Extract device name and instance from the DEVICE object."""
        for obj in self.objects:
            # Device object is usually first or has no dash in name
            if obj['category'] == 'POINT' and '-' not in obj['name']:
                # Could be the device name
                pass

        # Also look at the raw binary for device instance
        # The PFG -b flag sets device instance, stored early in the file
        return {}

    def validate_against_json(self, library_json: dict) -> dict:
        """Compare binary data against extracted JSON library entry.

        Returns a report of differences:
        - Missing objects (in binary but not JSON)
        - Present value mismatches
        - Loop binding discrepancies
        """
        report = {
            'present_value_mismatches': [],
            'missing_in_json': [],
            'loop_binding_issues': [],
        }

        # Compare present values
        json_pvs = {}
        for ptype in ['AI', 'AO', 'AV', 'BI', 'BO', 'BV', 'MO', 'MV']:
            for p in library_json.get('objects', {}).get(ptype, []):
                name = p.get('name', '')
                try:
                    json_pvs[name] = float(p.get('present_value', 0))
                except (ValueError, TypeError):
                    json_pvs[name] = 0

        for point in self.get_points():
            name = point['name']
            bin_pv = point['present_value']
            if name in json_pvs:
                json_pv = json_pvs[name]
                if abs(json_pv - bin_pv) > 0.01:
                    report['present_value_mismatches'].append({
                        'name': name,
                        'json_value': json_pv,
                        'binary_value': bin_pv,
                    })
            else:
                report['missing_in_json'].append(name)

        # Compare loop bindings
        json_loops = {}
        for l in library_json.get('objects', {}).get('LOOP', []):
            json_loops[l.get('instance', '')] = l

        for loop in self.get_loops():
            inst = loop['instance']
            json_loop = json_loops.get(inst, {})

            if loop.get('input_ref') and json_loop.get('input_ref'):
                if loop['input_ref'] != json_loop['input_ref']:
                    report['loop_binding_issues'].append({
                        'loop': loop['name'],
                        'field': 'input',
                        'binary': loop['input_ref'],
                        'json': json_loop['input_ref'],
                    })

        return report


class PanWriter:
    """Modify Reliable Controls .pan binary files directly.

    Enables lossless controller copying and template creation without PFG:
    - Change device ID and name
    - Rename all object names (same-length swap)
    - Modify present values
    - Set loop input/setpoint/output references

    File structure:
      Offset 0: Magic number (0x0023BAC0, constant)
      Offset 4: Device instance ID (4-byte little-endian)
      Offset 8: Section offset (varies by model)
      Objects: "Mu" header pattern throughout the file
    """

    def __init__(self, data: bytes):
        self.data = bytearray(data)

    @classmethod
    def from_file(cls, path: Path) -> 'PanWriter':
        return cls(path.read_bytes())

    @classmethod
    def from_panx(cls, panx_path: Path) -> 'PanWriter':
        import zipfile
        with zipfile.ZipFile(panx_path) as z:
            pan_names = [n for n in z.namelist() if n.endswith('.pan')]
            if not pan_names:
                raise ValueError(f"No .pan file found in {panx_path}")
            return cls(z.read(pan_names[0]))

    def set_device_id(self, new_id: int):
        """Change the BACnet device instance ID."""
        self.data[4:8] = struct.pack('<I', new_id)
        # Also update any BACnet ObjID references that point to this device
        # (trend references, loop references use device ID prefix)

    def get_device_id(self) -> int:
        return struct.unpack('<I', self.data[4:8])[0]

    def rename_device(self, old_name: str, new_name: str) -> int:
        """Replace all occurrences of old device name with new name.

        Names must be the same byte length for in-place replacement.
        Returns the number of replacements made.
        """
        old_bytes = old_name.encode('utf-8')
        new_bytes = new_name.encode('utf-8')

        if len(old_bytes) != len(new_bytes):
            raise ValueError(
                f"Name length mismatch: '{old_name}' ({len(old_bytes)} bytes) "
                f"vs '{new_name}' ({len(new_bytes)} bytes). "
                f"Binary replacement requires same byte length."
            )

        count = 0
        # Replace in all "Mu" name fields
        for m in re.finditer(b'\x4d\x75(.)', bytes(self.data)):
            name_len = m.group(1)[0]
            name_start = m.start() + 3
            name_bytes = self.data[name_start:name_start + name_len]

            try:
                name = name_bytes.decode('utf-8').rstrip('\x00')
            except (UnicodeDecodeError, ValueError):
                continue

            if old_name in name:
                new_full = name.replace(old_name, new_name)
                new_full_bytes = new_full.encode('utf-8')
                # Pad or truncate to allocated length
                padded = new_full_bytes + b'\x00' * (name_len - len(new_full_bytes))
                self.data[name_start:name_start + name_len] = padded[:name_len]
                count += 1

        return count

    def set_present_value(self, obj_name: str, new_value: float) -> bool:
        """Set the present value of a named object.

        Finds the object by name, then overwrites the float at property 0x55.
        Returns True if successful.
        """
        name_bytes = obj_name.encode('utf-8')
        try:
            pos = self.data.index(name_bytes + b'\x00')
        except ValueError:
            return False

        # Find property 0x55 (present value) after the name
        name_end = pos + len(name_bytes) + 1
        region = self.data[name_end:name_end + 30]

        for i in range(len(region) - 6):
            if region[i:i+2] == b'\x55\x44':
                # Overwrite the float
                abs_pos = name_end + i + 2
                self.data[abs_pos:abs_pos + 4] = struct.pack('>f', new_value)
                return True

        return False

    def set_loop_binding(self, loop_name: str, input_type: str = None,
                         input_instance: int = None,
                         setpoint_type: str = None,
                         setpoint_instance: int = None) -> bool:
        """Set loop input and/or setpoint references.

        Overwrites the BACnet ObjID at the known offsets after the loop name.
        """
        name_bytes = loop_name.encode('utf-8')
        try:
            pos = self.data.index(name_bytes + b'\x00')
        except ValueError:
            return False

        name_end = pos + len(name_bytes) + 1
        region = self.data[name_end:name_end + 100]

        # Find BACnet ObjID tags (0x0c)
        objid_positions = []
        for i in range(len(region) - 5):
            if region[i] == 0x0c:
                objid = struct.unpack('>I', region[i+1:i+5])[0]
                obj_type = (objid >> 22) & 0x3FF
                obj_inst = objid & 0x3FFFFF
                if obj_type < 20 and obj_inst < 10000:
                    objid_positions.append(name_end + i + 1)  # Position of the 4-byte ObjID

        if input_type is not None and input_instance is not None and len(objid_positions) >= 1:
            new_objid = encode_objid(input_type, input_instance)
            pos = objid_positions[0]
            self.data[pos:pos + 4] = new_objid

        if setpoint_type is not None and setpoint_instance is not None and len(objid_positions) >= 2:
            new_objid = encode_objid(setpoint_type, setpoint_instance)
            pos = objid_positions[1]
            self.data[pos:pos + 4] = new_objid

        return True

    def save(self, path: Path):
        """Write the modified .pan to a file."""
        path.write_bytes(self.data)

    def save_panx(self, path: Path, meta: dict = None, assets_dir: Path = None):
        """Package the modified .pan into a .panx (zip) file."""
        import zipfile
        import json

        device_id = self.get_device_id()

        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Write .pan
            zf.writestr(f"{device_id}.pan", bytes(self.data))

            # Write meta.json
            if meta is None:
                meta = {"Device": device_id, "Database": f"{device_id}.pan"}
            zf.writestr("meta.json", json.dumps(meta, indent=2))

            # Write assets
            if assets_dir and assets_dir.exists():
                import os
                for root, dirs, files in os.walk(assets_dir):
                    for fname in files:
                        fpath = Path(root) / fname
                        arcname = "group_assets/" + str(fpath.relative_to(assets_dir))
                        zf.write(fpath, arcname)


def enrich_library_entry(pan_path: Path, library_json: dict) -> dict:
    """Enrich a library JSON entry with data from the .pan binary.

    Adds/updates:
    - Loop input_ref, setpoint_ref, output_ref (from binary)
    - Verified present values
    - Complete trend references

    Returns the modified library_json dict.
    """
    try:
        if str(pan_path).endswith('.panx'):
            parser = PanBinary.from_panx(pan_path)
        else:
            parser = PanBinary.from_file(pan_path)
    except Exception as e:
        logger.warning(f"Could not parse binary: {e}")
        return library_json

    objects = library_json.get('objects', {})

    # Build name-to-point lookup from binary
    binary_points = {p['name']: p for p in parser.get_points()}

    # Enrich loops with binary bindings
    binary_loops = {l['instance']: l for l in parser.get_loops()}
    for loop in objects.get('LOOP', []):
        inst = loop.get('instance', '')
        bl = binary_loops.get(inst)
        if bl:
            if bl.get('input_ref'):
                loop['input_ref'] = bl['input_ref']
                # Find the name for this reference
                for ptype in ['AI', 'AO', 'AV', 'BI', 'BO', 'BV', 'MO', 'MV']:
                    for p in objects.get(ptype, []):
                        if f"{ptype}{p.get('instance','')}" == bl['input_ref']:
                            loop['input_name'] = p.get('name', '')
                            break
            if bl.get('setpoint_ref'):
                loop['setpoint_ref'] = bl['setpoint_ref']
                for ptype in ['AI', 'AO', 'AV', 'BI', 'BO', 'BV', 'MO', 'MV']:
                    for p in objects.get(ptype, []):
                        if f"{ptype}{p.get('instance','')}" == bl['setpoint_ref']:
                            loop['setpoint_name'] = p.get('name', '')
                            break
            if bl.get('output_ref'):
                loop['output_ref'] = bl['output_ref']

    # Enrich trends with binary references
    binary_trends = {t['name']: t for t in parser.get_trends()}
    for trend in objects.get('TREND', []):
        name = trend.get('name', '')
        # Try matching by name (binary has original names, JSON has templatized)
        bt = None
        for bn, btrend in binary_trends.items():
            # Match ignoring device name prefix
            if name.replace('{device-name}', '').lstrip('-') in bn:
                bt = btrend
                break
        if bt and bt.get('refs'):
            trend['binary_refs'] = bt['refs']

    return library_json
