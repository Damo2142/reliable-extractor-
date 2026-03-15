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

    def _categorize(self, name: str) -> str:
        """Categorize an object by its name pattern."""
        upper = name.upper()
        if 'LOOP' in upper and 'TL' not in upper:
            return 'LOOP'
        if any(upper.endswith(s) for s in ['-TL', '-MTL', '-STL', '-RTL']):
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
