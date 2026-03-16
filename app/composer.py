"""
Controller Composer
Mix and match programs, points, loops, trends, etc. from different library
variants to build custom controllers.

Flow:
  1. Index all programs across the entire library with their dependencies
  2. User selects programs from different variants
  3. Resolve dependencies (points, loops referenced in code)
  4. Remap instance numbers sequentially to avoid conflicts
  5. Assemble into a new library-format JSON
  6. Feed to generator.py → XML → PFG → .panx

All names use {device-name} template format so the controller name is
applied when the template is mapped to real equipment.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

from app.config import Config

logger = logging.getLogger(__name__)

# Program function tags — maps program name patterns to human-readable function tags
# These help techs find programs by function regardless of source category
PROGRAM_FUNCTION_TAGS = {
    'CFG': ['Configuration', 'config'],
    'CONFIG': ['Configuration', 'config'],
    'SP': ['Setpoints', 'setpoint'],
    'MODE': ['Operating Mode', 'mode', 'occupied', 'unoccupied'],
    'OCC': ['Occupancy', 'schedule', 'occupied'],
    'SF': ['Supply Fan', 'fan', 'airflow'],
    'RF': ['Return Fan', 'fan', 'airflow'],
    'ECON': ['Economizer', 'damper', 'free-cooling'],
    'MAD': ['Mixed Air Damper', 'damper'],
    'SAT': ['Supply Air Temp', 'temperature', 'cooling'],
    'DSP': ['Duct Static Pressure', 'pressure', 'airflow'],
    'HW': ['Hot Water', 'heating', 'valve'],
    'HTG': ['Heating', 'heating', 'valve'],
    'CHW': ['Chilled Water', 'cooling', 'valve'],
    'CLG': ['Cooling', 'cooling'],
    'VLV': ['Valve Control', 'valve'],
    'DMP': ['Damper Control', 'damper'],
    'FLO': ['Flow Control', 'airflow', 'cfm'],
    'PRESS': ['Pressure Control', 'pressure'],
    'FRZ': ['Freeze Protection', 'safety'],
    'ALARM': ['Alarm', 'safety', 'monitoring'],
    'FAULT': ['Fault Detection', 'diagnostics', 'monitoring'],
    'NET': ['Network/BACnet', 'communication', 'network'],
    'SCHED': ['Schedule', 'schedule', 'time'],
    'ARRAY': ['Data Arrays', 'configuration'],
    'ARRAYS': ['Data Arrays', 'configuration'],
    'VARS': ['Network/BACnet', 'communication', 'network'],
    'MWU': ['Morning Warmup', 'heating', 'mode'],
    'MCD': ['Morning Cooldown', 'cooling', 'mode'],
    'CONV': ['Unit Conversion', 'configuration'],
    'PGR': ['Staging', 'sequencing'],
    'LEAD': ['Lead/Lag', 'sequencing', 'plant'],
    'PUMP': ['Pump Control', 'pump', 'plant'],
    'BOILER': ['Boiler Control', 'heating', 'plant'],
    'HWP': ['Hot Water Pump', 'pump', 'heating'],
    'CHWP': ['Chilled Water Pump', 'pump', 'cooling'],
    'ERW': ['Energy Recovery', 'energy', 'heat-recovery'],
    'CO2': ['CO2 Control', 'ventilation', 'iaq'],
    'DEHUM': ['Dehumidification', 'humidity'],
    'HUMID': ['Humidification', 'humidity'],
}

VARIANT_FRIENDLY_LABELS = {
    # SBS variants — decode the cryptic codes
    '1003': 'SBS Standard AHU — HW Preheat, CHW, Economizer, SF+RF',
    '1000': 'SBS Master Controller — Zone Networking + Scheduling',
    '1201': 'SBS Plant Controller — HW/CHW, 2 Primary HWP, 1 Chiller, Cascade Boilers',
    '1213': 'SBS Parallel Fan VAV — Mod HW Reheat, Factory Damper, Wallplate',
    '1224': 'SBS Parallel Fan VAV — Mod HW Reheat, Factory Damper, SS3 + Humidity + CO2',
    '2001': 'SBS Space Temp AHU — HW Preheat, HWP, CHW, Economizer, Space Control',
    'ahu1': 'SBS Space Temp AHU — HW Preheat, HWP, CHW, Economizer, Space Control (v2)',
    'PS-AHU-ERW-0100': 'SBS Premium AHU — HW Preheat, CHW, Dehumid, Economizer, Energy Recovery',
}

# Equipment compatibility — which equipment types can use programs with these function tags
_FUNCTION_EQUIPMENT_MAP = {
    'Supply Fan': ['AHU', 'RTU', 'FCU'],
    'Return Fan': ['AHU', 'RTU'],
    'Economizer': ['AHU', 'RTU'],
    'Mixed Air Damper': ['AHU', 'RTU'],
    'Supply Air Temp': ['AHU', 'RTU'],
    'Duct Static Pressure': ['AHU', 'RTU'],
    'Hot Water': ['AHU', 'RTU', 'VAV', 'FCU', 'UH', 'WSHP'],
    'Heating': ['AHU', 'RTU', 'VAV', 'FCU', 'UH', 'WSHP'],
    'Chilled Water': ['AHU', 'RTU', 'FCU', 'WSHP'],
    'Cooling': ['AHU', 'RTU', 'VAV', 'FCU', 'WSHP'],
    'Valve Control': ['AHU', 'RTU', 'VAV', 'FCU', 'UH', 'WSHP'],
    'Damper Control': ['AHU', 'RTU', 'VAV', 'VVT'],
    'Flow Control': ['AHU', 'RTU', 'VAV', 'VVT'],
    'Pump Control': ['PLANT'],
    'Hot Water Pump': ['PLANT'],
    'Chilled Water Pump': ['PLANT'],
    'Boiler Control': ['PLANT'],
    'Lead/Lag': ['PLANT'],
    'Energy Recovery': ['AHU', 'RTU'],
    'CO2 Control': ['AHU', 'RTU', 'VAV'],
    'Dehumidification': ['AHU', 'RTU'],
    'Humidification': ['AHU', 'RTU'],
    'Freeze Protection': ['AHU', 'RTU'],
    'Configuration': ['AHU', 'RTU', 'VAV', 'FCU', 'UH', 'WSHP', 'VVT', 'PLANT'],
    'Network/BACnet': ['AHU', 'RTU', 'VAV', 'FCU', 'UH', 'WSHP', 'VVT', 'PLANT'],
    'Operating Mode': ['AHU', 'RTU', 'VAV', 'FCU', 'UH', 'WSHP', 'VVT'],
    'Occupancy': ['AHU', 'RTU', 'VAV', 'FCU', 'UH', 'WSHP', 'VVT'],
    'Schedule': ['AHU', 'RTU', 'VAV', 'FCU', 'UH', 'WSHP', 'VVT', 'PLANT'],
    'Data Arrays': ['AHU', 'RTU', 'VAV', 'FCU', 'UH', 'WSHP', 'VVT', 'PLANT'],
    'Morning Warmup': ['AHU', 'RTU'],
    'Morning Cooldown': ['AHU', 'RTU'],
    'Unit Conversion': ['AHU', 'RTU', 'VAV', 'FCU', 'UH', 'WSHP', 'VVT', 'PLANT'],
    'Staging': ['AHU', 'RTU', 'PLANT'],
}


def get_function_tags_for_program(program_name: str) -> list:
    """Extract function tags from a program name based on name patterns."""
    tags = []
    # Strip the {device-name}- prefix and -PRGxx suffix
    name = re.sub(r'^\{device-name\}-', '', program_name)
    name = re.sub(r'-PRG\d+$', '', name)
    # Split on hyphens and underscores to get tokens
    tokens = re.split(r'[-_]', name.upper())
    seen = set()
    for token in tokens:
        if token in PROGRAM_FUNCTION_TAGS:
            label = PROGRAM_FUNCTION_TAGS[token][0]
            if label not in seen:
                tags.append(label)
                seen.add(label)
    return tags


def get_all_function_tags_for_variant(programs: list) -> list:
    """Get deduplicated, sorted list of all function tags across a variant's programs."""
    all_tags = set()
    for prog in programs:
        pname = prog.get('name', '') if isinstance(prog, dict) else prog
        for tag in get_function_tags_for_program(pname):
            all_tags.add(tag)
    return sorted(all_tags)


def get_compatible_equipment(function_tags: list) -> list:
    """Derive equipment compatibility from function tags."""
    equip = set()
    for tag in function_tags:
        if tag in _FUNCTION_EQUIPMENT_MAP:
            equip.update(_FUNCTION_EQUIPMENT_MAP[tag])
    return sorted(equip)


# Regex patterns for Control-BASIC point references
# Matches: AV7, AI1, AO2, BI6, BO2, BV24, MO7, MV16, LOOP1, SCHED1
POINT_REF_PATTERN = re.compile(
    r'\b(AI|AO|AV|BI|BO|BV|MO|MV|LOOP|SCHED)(\d+)\b'
)

# For network/cross-device references like 1001BI1 or 1001DEV1001:120
NETWORK_REF_PATTERN = re.compile(
    r'\b(\d+)(AI|AO|AV|BI|BO|BV|MO|MV|DEV)(\d+)\b'
)

POINT_TYPES = ["AI", "AO", "AV", "BI", "BO", "BV", "MO", "MV"]
ALL_OBJECT_TYPES = POINT_TYPES + [
    "PROGRAM", "LOOP", "TREND", "SCHEDULE", "CALENDAR",
    "SMARTSENSOR", "SYSTEMGROUP", "TABLE", "ARRAY"
]


def parse_code_references(code: str) -> dict:
    """Parse Control-BASIC code and extract all local point/loop references.

    Returns dict like:
        {"AI": {1, 4}, "AV": {7, 8, 9}, "LOOP": {1}, "SCHED": {1}, ...}
    """
    refs = {}
    for match in POINT_REF_PATTERN.finditer(code):
        ptype = match.group(1)
        instance = int(match.group(2))
        refs.setdefault(ptype, set()).add(instance)
    return refs


def parse_network_references(code: str) -> list:
    """Extract cross-device references like 1001BI1 from program code.

    These are reads from other controllers on the network and should be
    preserved as-is (not remapped).
    """
    network_refs = []
    for match in NETWORK_REF_PATTERN.finditer(code):
        device_id = match.group(1)
        ptype = match.group(2)
        instance = match.group(3)
        network_refs.append({
            "device_id": device_id,
            "type": ptype,
            "instance": instance,
            "raw": match.group(0),
        })
    return network_refs


class Composer:
    def __init__(self, config: Config):
        self.cfg = config

    def build_program_index(self) -> list:
        """Scan entire library and build a flat index of every program
        with its source variant and dependency analysis.

        Returns list of dicts:
        [
            {
                "source_category": "VAV",
                "source_variant": "VAV-IS10001",
                "source_description": "...",
                "program_instance": "1",
                "program_name": "{device-name}-CFG-PRG",
                "program_description": "...",
                "code_preview": "first 200 chars...",
                "code_lines": 23,
                "dependencies": {
                    "AI": [1, 4],
                    "AV": [7, 8, 9],
                    "LOOP": [1],
                    ...
                },
                "dependency_details": {
                    "AI": [{"instance": "1", "name": "{device-name}-DAT", ...}],
                    ...
                },
                "network_refs": [...],
            },
            ...
        ]
        """
        index = []

        if not self.cfg.library_root.exists():
            return index

        for cat_dir in sorted(self.cfg.library_root.iterdir()):
            if not cat_dir.is_dir() or cat_dir.name.startswith("_"):
                continue
            category = cat_dir.name

            for jf in sorted(cat_dir.glob("*.json")):
                try:
                    data = json.loads(jf.read_text())
                except Exception:
                    continue

                variant_id = data.get("id", jf.stem)
                variant_desc = data.get("description", "")
                objects = data.get("objects", {})

                for prog in objects.get("PROGRAM", []):
                    code = prog.get("code", "")
                    refs = parse_code_references(code)
                    net_refs = parse_network_references(code)

                    # Build dependency details - actual point objects referenced
                    dep_details = {}
                    for ptype, instances in refs.items():
                        if ptype in ("LOOP", "SCHED"):
                            obj_key = ptype if ptype != "SCHED" else "SCHEDULE"
                            source_objs = objects.get(obj_key, [])
                        else:
                            source_objs = objects.get(ptype, [])

                        matched = []
                        for obj in source_objs:
                            if int(obj.get("instance", 0)) in instances:
                                matched.append(obj)
                        if matched:
                            dep_details[ptype] = matched

                    # Clean dependency instances to sorted lists
                    dep_summary = {k: sorted(v) for k, v in refs.items()}

                    prog_name = prog.get("name", "")
                    ftags = get_function_tags_for_program(prog_name)

                    index.append({
                        "source_category": category,
                        "source_variant": variant_id,
                        "source_description": variant_desc,
                        "friendly_label": VARIANT_FRIENDLY_LABELS.get(variant_id, ""),
                        "program_instance": prog.get("instance", ""),
                        "program_name": prog_name,
                        "program_description": prog.get("description", ""),
                        "code_preview": code[:200],
                        "code_lines": len(code.split("\n")),
                        "dependencies": dep_summary,
                        "dependency_details": dep_details,
                        "network_refs": net_refs,
                        "function_tags": ftags,
                    })

        return index

    def build_variant_descriptions(self) -> dict:
        """Auto-generate human-readable descriptions for every variant by
        analyzing program names and AO/BO dependencies on reheat programs.

        Returns dict: { variant_id: description_string }
        """
        if not self.cfg.library_root.exists():
            return {}

        # First pass: collect per-variant program info
        variant_info = {}
        for cat_dir in sorted(self.cfg.library_root.iterdir()):
            if not cat_dir.is_dir() or cat_dir.name.startswith("_"):
                continue
            category = cat_dir.name
            for jf in sorted(cat_dir.glob("*.json")):
                try:
                    data = json.loads(jf.read_text())
                except Exception:
                    continue
                variant_id = data.get("id", jf.stem)
                objects = data.get("objects", {})
                programs = objects.get("PROGRAM", [])

                info = {"category": category, "programs": [], "has_ao_reheat": False, "has_bo_reheat": False,
                        "has_fan": False, "fan_type": "", "has_xdmp": False, "xdmp_type": ""}
                for prog in programs:
                    pname = prog.get("name", "")
                    code = prog.get("code", "")
                    refs = parse_code_references(code)
                    info["programs"].append(pname)

                    # Check reheat programs for AO vs BO
                    is_reheat = any(kw in pname.upper() for kw in ["RH-", "RHT-", "RHV-", "REHEAT", "-RH-PRG", "FLOAT-RHT", "1STG-REHEAT"])
                    is_xdmp = "XDMP" in pname.upper()
                    is_fan = any(kw in pname.upper() for kw in ["FAN-", "PFAN-"])

                    if is_reheat:
                        if refs.get("AO"):
                            info["has_ao_reheat"] = True
                        if refs.get("BO"):
                            info["has_bo_reheat"] = True
                    if is_xdmp:
                        info["has_xdmp"] = True
                        if refs.get("AO"):
                            info["xdmp_type"] = "Modulating"
                        elif refs.get("BO"):
                            info["xdmp_type"] = "Floating"
                    if is_fan:
                        info["has_fan"] = True
                        if "PFAN" in pname.upper():
                            info["fan_type"] = "Parallel"
                        else:
                            info["fan_type"] = "Series"

                variant_info[variant_id] = info

        # Second pass: build descriptions
        descs = {}
        for vid, info in variant_info.items():
            cat = info["category"]
            parts = []

            if cat == "VAV":
                # Duct type
                if "IS2" in vid or "IT2" in vid:
                    parts.append("Dual Duct")
                else:
                    parts.append("Single Duct")

                # Fan — use variant ID to determine type (P=parallel, S=series)
                has_fan_prog = info["has_fan"]
                # Check variant ID for fan position markers
                vid_upper = vid.upper()
                is_parallel = "0P0" in vid_upper or "0P01" in vid_upper or "0P02" in vid_upper or "FP0" in vid_upper
                is_series = "0S0" in vid_upper or "0S02" in vid_upper or "FS0" in vid_upper
                if is_parallel:
                    parts.append("Parallel Fan")
                elif is_series or (has_fan_prog and not is_parallel):
                    parts.append("Series Fan")

                # Reheat valve type
                has_reheat = any(kw in ' '.join(info["programs"]).upper() for kw in ["RH-", "RHT-", "RHV-", "REHEAT"])
                if not has_reheat:
                    parts.append("Cooling Only")
                elif info["has_ao_reheat"] and not info["has_bo_reheat"]:
                    parts.append("Modulating HW Reheat")
                elif info["has_bo_reheat"] and not info["has_ao_reheat"]:
                    parts.append("Floating HW Reheat")
                elif info["has_ao_reheat"] and info["has_bo_reheat"]:
                    parts.append("Floating+Mod HW Reheat")
                else:
                    parts.append("HW Reheat")

                # Crossover damper
                if info["has_xdmp"]:
                    parts.append(f"{info['xdmp_type']} Crossover Dmpr")

                # Sensor type
                if "-E-" in vid:
                    parts.append("External SMART-Net")
                elif "IS" in vid:
                    parts.append("Internal SMART-Net")
                elif "IT" in vid:
                    parts.append("Internal Thermistor")

            else:
                # Non-VAV: use program count and point count as basic description
                n_progs = len(info["programs"])
                parts.append(f"{cat} variant ({n_progs} programs)")

            descs[vid] = ", ".join(parts)

        # Load overrides from master_descriptions.json — user-set descriptions always win
        override_path = Path("/srv/dfa/shared/files/vendors/reliable/master_descriptions.json")
        if override_path.exists():
            try:
                overrides = json.loads(override_path.read_text())
                for k, v in overrides.items():
                    if v:  # Only override if description is non-empty
                        descs[k] = v
            except Exception:
                pass

        return descs

    def build_variant_metadata(self) -> dict:
        """Build enriched metadata for every variant: friendly label, function tags,
        compatible equipment, and description.

        Returns dict: { variant_id: { description, friendly_label, function_tags, compatible_with } }
        """
        descs = self.build_variant_descriptions()
        meta = {}

        if not self.cfg.library_root.exists():
            return meta

        for cat_dir in sorted(self.cfg.library_root.iterdir()):
            if not cat_dir.is_dir() or cat_dir.name.startswith("_"):
                continue
            for jf in sorted(cat_dir.glob("*.json")):
                try:
                    data = json.loads(jf.read_text())
                except Exception:
                    continue
                variant_id = data.get("id", jf.stem)
                objects = data.get("objects", {})
                programs = objects.get("PROGRAM", [])

                ftags = get_all_function_tags_for_variant(programs)
                compat = get_compatible_equipment(ftags)
                friendly = VARIANT_FRIENDLY_LABELS.get(variant_id, "")

                meta[variant_id] = {
                    "description": descs.get(variant_id, ""),
                    "friendly_label": friendly,
                    "function_tags": ftags,
                    "compatible_with": compat,
                    "category": cat_dir.name,
                }

        return meta

    def _cat_folder(self, cat_key: str) -> str:
        """Reverse-map category key (e.g. 'SBS_AHU') to upload folder name."""
        inv = {v: k for k, v in self.cfg.CATEGORIES.items()}
        return inv.get(cat_key, cat_key)

    def get_variant_data(self, category: str, variant_id: str) -> Optional[dict]:
        """Load a variant's full library record (objects, meta, graphics, etc.)."""
        lib_path = self.cfg.library_root / category / f"{variant_id}.json"
        if not lib_path.exists():
            return None
        try:
            return json.loads(lib_path.read_text())
        except Exception:
            return None

    def _get_mnemonic(self, point_obj: dict) -> str:
        """Extract mnemonic from a point's object name.

        The mnemonic is the functional identifier — e.g. 'FLO-SP', 'RMT-ACT'.
        Object names follow the pattern '{device-name}-MNEMONIC'.
        """
        name = point_obj.get("name", "")
        if name.startswith("{device-name}-"):
            return name[len("{device-name}-"):]
        return name

    def _build_instance_to_mnemonic_map(self, objects: dict) -> dict:
        """Build a lookup: (type, instance) -> mnemonic for a variant's objects.

        E.g. {("AV", 38): "FLO-SP-MIN-HTG", ("AI", 1): "DMP-POS", ...}
        """
        mapping = {}
        for ptype in POINT_TYPES:
            for obj in objects.get(ptype, []):
                inst = int(obj.get("instance", 0))
                mnemonic = self._get_mnemonic(obj)
                if mnemonic:
                    mapping[(ptype, inst)] = mnemonic
        for obj in objects.get("LOOP", []):
            inst = int(obj.get("instance", 0))
            mnemonic = self._get_mnemonic(obj)
            if mnemonic:
                mapping[("LOOP", inst)] = mnemonic
        for obj in objects.get("SCHEDULE", []):
            inst = int(obj.get("instance", 0))
            mnemonic = self._get_mnemonic(obj)
            if mnemonic:
                mapping[("SCHED", inst)] = mnemonic
        return mapping

    def compose(self, selections: list, device_name: str = "{device-name}",
                device_id: str = "900", primary_variant: str = None) -> dict:
        """Compose a new controller from selected programs across variants.

        Mnemonic-based composition:
          1. For each selected program, parse code to find referenced instances
          2. Look up the mnemonic (functional name) for each reference from the
             source variant's objects
          3. Merge points by mnemonic — if two programs both reference 'FLO-SP'
             (even at different instances in their source), they share ONE point
          4. Assign fresh sequential instances per type
          5. Rewrite ALL program code with new instance numbers

        Args:
            selections: list of dicts, each with:
                {
                    "category": "VAV",
                    "variant_id": "VAV-IS10001",
                    "program_instance": "1"
                }
            device_name: name template (default "{device-name}")
            device_id: BACnet device instance ID

        Returns:
            A library-format JSON dict ready for generator.py
        """
        # Load all source variants
        source_cache = {}
        for sel in selections:
            key = f"{sel['category']}/{sel['variant_id']}"
            if key not in source_cache:
                data = self.get_variant_data(sel["category"], sel["variant_id"])
                if data is None:
                    raise ValueError(f"Variant not found: {key}")
                source_cache[key] = data

        # ── Phase 1: Collect programs and build per-variant mnemonic maps ──
        programs = []  # list of (program_obj, source_key, inst_to_mnemonic_map)

        # Mnemonic registry: "TYPE:MNEMONIC" -> point_obj (first one wins,
        # later programs with same mnemonic share the same point)
        mnemonic_points = {}    # "AV:FLO-SP" -> point_obj (with _mnemonic set)
        mnemonic_loops = {}     # "LOOP:FLO-CTRL-LOOP" -> loop_obj
        mnemonic_scheds = {}    # "SCHED:LOCAL-SCHED" -> schedule_obj

        # Per-program remap: maps (program_index, type, old_instance) -> mnemonic_key
        # This lets us rewrite code references later
        program_ref_map = {}

        # Also collect trends, calendars, etc.
        all_trends = {}  # keyed by "source_key:instance" to prevent duplicates
        all_calendars = {}
        all_smartsensors = {}
        all_systemgroups = {}
        all_tables = {}
        all_arrays = {}

        # Graphics, meta, and GRP JSONs
        all_graphics = []
        all_meta = {}
        all_graphics_sources = []
        all_grp_files = {}  # "1000GRP1" -> json data

        for sel_idx, sel in enumerate(selections):
            key = f"{sel['category']}/{sel['variant_id']}"
            data = source_cache[key]
            objects = data.get("objects", {})
            prog_inst = str(sel["program_instance"])

            # Build mnemonic lookup for this variant
            inst_to_mnemonic = self._build_instance_to_mnemonic_map(objects)

            # Find the program
            program = None
            for p in objects.get("PROGRAM", []):
                if str(p.get("instance", "")) == prog_inst:
                    program = dict(p)
                    program["_source"] = key
                    break

            if program is None:
                raise ValueError(
                    f"Program instance {prog_inst} not found in {key}"
                )

            programs.append((program, key, inst_to_mnemonic))

            # Parse code references
            code = program.get("code", "")
            prog_name = program.get("name", f"PRG{prog_inst}")
            refs = parse_code_references(code)

            # ── Collect points by mnemonic ──
            for ptype in POINT_TYPES:
                if ptype not in refs:
                    continue
                for inst in refs[ptype]:
                    mnemonic = inst_to_mnemonic.get((ptype, inst))
                    if not mnemonic:
                        # No mnemonic found — use type+instance as fallback
                        mnemonic = f"{ptype}{inst}"

                    mnem_key = f"{ptype}:{mnemonic}"
                    program_ref_map[(sel_idx, ptype, inst)] = mnem_key

                    if mnem_key not in mnemonic_points:
                        # Find the full point object from source variant
                        pt_obj = None
                        for obj in objects.get(ptype, []):
                            if int(obj.get("instance", 0)) == inst:
                                pt_obj = dict(obj)
                                pt_obj["_source"] = key
                                pt_obj["_mnemonic"] = mnemonic
                                break

                        if pt_obj is None:
                            # Auto-create placeholder — find the code line that references it
                            ref_pattern = f"{ptype}{inst}"
                            code_line = ""
                            for line in code.split('\n'):
                                if ref_pattern in line:
                                    code_line = line.strip()[:60]
                                    break

                            _defaults = {
                                "AV": {"present_value": "0", "range": "45", "unit": "45", "increment": "0.100000"},
                                "AI": {"present_value": "0", "range": "3",  "unit": "2",  "increment": "0.200000"},
                                "AO": {"present_value": "0", "range": "15", "unit": "15", "increment": "0.100000"},
                                "BI": {"present_value": "0", "range": "0",  "unit": "",   "increment": ""},
                                "BO": {"present_value": "0", "range": "7",  "unit": "",   "increment": ""},
                                "BV": {"present_value": "0", "range": "7",  "unit": "",   "increment": ""},
                                "MO": {"present_value": "1", "range": "0",  "unit": "",   "increment": ""},
                                "MV": {"present_value": "1", "range": "0",  "unit": "",   "increment": ""},
                            }
                            defs = _defaults.get(ptype, {"present_value": "0", "range": "0", "unit": "", "increment": ""})
                            desc = f"[auto] {prog_name} -> {code_line}" if code_line else f"[auto] referenced by {prog_name}"
                            pt_obj = {
                                "type": ptype,
                                "instance": str(inst),
                                "name": f"{{device-name}}-{mnemonic}",
                                "description": desc,
                                "present_value": defs["present_value"],
                                "range": defs["range"],
                                "unit": defs["unit"],
                                "increment": defs["increment"],
                                "_source": key,
                                "_mnemonic": mnemonic,
                            }

                        mnemonic_points[mnem_key] = pt_obj

            # ── Collect loops by mnemonic ──
            if "LOOP" in refs:
                for inst in refs["LOOP"]:
                    mnemonic = inst_to_mnemonic.get(("LOOP", inst))
                    if not mnemonic:
                        mnemonic = f"LOOP{inst}"
                    mnem_key = f"LOOP:{mnemonic}"
                    program_ref_map[(sel_idx, "LOOP", inst)] = mnem_key

                    if mnem_key not in mnemonic_loops:
                        for obj in objects.get("LOOP", []):
                            if int(obj.get("instance", 0)) == inst:
                                loop_obj = dict(obj)
                                loop_obj["_source"] = key
                                loop_obj["_mnemonic"] = mnemonic
                                mnemonic_loops[mnem_key] = loop_obj
                                break

            # ── Collect schedules by mnemonic ──
            if "SCHED" in refs:
                for inst in refs["SCHED"]:
                    mnemonic = inst_to_mnemonic.get(("SCHED", inst))
                    if not mnemonic:
                        mnemonic = f"SCHED{inst}"
                    mnem_key = f"SCHED:{mnemonic}"
                    program_ref_map[(sel_idx, "SCHED", inst)] = mnem_key

                    if mnem_key not in mnemonic_scheds:
                        for obj in objects.get("SCHEDULE", []):
                            if int(obj.get("instance", 0)) == inst:
                                sched_obj = dict(obj)
                                sched_obj["_source"] = key
                                sched_obj["_mnemonic"] = mnemonic
                                mnemonic_scheds[mnem_key] = sched_obj
                                break

            # Pull ALL trends from source (deduplicate by source+instance)
            for trend in objects.get("TREND", []):
                trend_key = f"{key}:{trend.get('instance', '')}"
                if trend_key not in all_trends:
                    trend_copy = dict(trend)
                    trend_copy["_source"] = key
                    all_trends[trend_key] = trend_copy

            # Pull calendars, smartsensors, etc. (controller-level objects)
            for cal in objects.get("CALENDAR", []):
                cal_key = f"CAL:{cal.get('instance', '')}"
                if cal_key not in all_calendars:
                    all_calendars[cal_key] = dict(cal)
                    all_calendars[cal_key]["_source"] = key

            for ss in objects.get("SMARTSENSOR", []):
                ss_key = f"SS:{ss.get('instance', '')}"
                if ss_key not in all_smartsensors:
                    all_smartsensors[ss_key] = dict(ss)
                    all_smartsensors[ss_key]["_source"] = key

            for sg in objects.get("SYSTEMGROUP", []):
                sg_key = f"SG:{sg.get('instance', '')}"
                if sg_key not in all_systemgroups:
                    all_systemgroups[sg_key] = dict(sg)
                    all_systemgroups[sg_key]["_source"] = key

            # Collect GRP JSON files from source variant
            for grp_name, grp_data in data.get("grp_files", {}).items():
                if grp_name not in all_grp_files:
                    all_grp_files[grp_name] = grp_data

            for tbl in objects.get("TABLE", []):
                tbl_key = f"TBL:{tbl.get('instance', '')}"
                if tbl_key not in all_tables:
                    all_tables[tbl_key] = dict(tbl)
                    all_tables[tbl_key]["_source"] = key

            for arr in objects.get("ARRAY", []):
                arr_key = f"ARR:{arr.get('instance', '')}"
                if arr_key not in all_arrays:
                    all_arrays[arr_key] = dict(arr)
                    all_arrays[arr_key]["_source"] = key

            # Collect graphics
            for gfx in data.get("graphics", []):
                if gfx not in all_graphics:
                    all_graphics.append(gfx)
                    all_graphics_sources.append({
                        "file": gfx,
                        "from_category": sel["category"],
                        "from_variant": sel["variant_id"],
                    })

            # Merge meta
            src_meta = data.get("meta", {})
            if src_meta:
                if "GroupAssets" in src_meta:
                    # Normalize backslash paths to forward slashes for Linux compatibility
                    normalized_ga = []
                    for ga in src_meta["GroupAssets"]:
                        ga_copy = dict(ga)
                        if "Asset" in ga_copy:
                            ga_copy["Asset"] = ga_copy["Asset"].replace("\\", "/")
                        if "JobPath" in ga_copy:
                            ga_copy["JobPath"] = ga_copy["JobPath"].replace("\\", "/")
                        normalized_ga.append(ga_copy)
                    all_meta.setdefault("GroupAssets", []).extend(normalized_ga)
                if "ViewAssets" in src_meta:
                    all_meta.setdefault("ViewAssets", []).extend(src_meta["ViewAssets"])
                if "Model" in src_meta and "Model" not in all_meta:
                    all_meta["Model"] = src_meta["Model"]
                if "HardPointConfig" in src_meta and "HardPointConfig" not in all_meta:
                    all_meta["HardPointConfig"] = src_meta["HardPointConfig"]
                if "Features" in src_meta:
                    existing = set(all_meta.get("Features", []))
                    for f in src_meta["Features"]:
                        if f not in existing:
                            all_meta.setdefault("Features", []).append(f)
                            existing.add(f)

        # ── Phase 1b: Include ALL remaining points from the PRIMARY variant ──
        # The primary variant (most selected programs) gets all its points included
        # since it's the base template. Other variants only contribute what their
        # selected programs reference (already collected in Phase 1).
        # Determine primary variant: explicitly set, or the one with most programs
        if primary_variant:
            primary_key = primary_variant
        else:
            from collections import Counter as _Counter
            variant_prog_count = _Counter(
                f"{sel['category']}/{sel['variant_id']}" for sel in selections
            )
            primary_key = variant_prog_count.most_common(1)[0][0] if variant_prog_count else None

        if primary_key and primary_key in source_cache:
            data = source_cache[primary_key]
            objects = data.get("objects", {})
            inst_to_mnemonic = self._build_instance_to_mnemonic_map(objects)

            for ptype in POINT_TYPES:
                for obj in objects.get(ptype, []):
                    inst = int(obj.get("instance", 0))
                    mnemonic = inst_to_mnemonic.get((ptype, inst))
                    if not mnemonic:
                        mnemonic = f"{ptype}{inst}"
                    mnem_key = f"{ptype}:{mnemonic}"
                    if mnem_key not in mnemonic_points:
                        pt_obj = dict(obj)
                        pt_obj["_source"] = primary_key
                        pt_obj["_mnemonic"] = mnemonic
                        mnemonic_points[mnem_key] = pt_obj

            for loop in objects.get("LOOP", []):
                inst = int(loop.get("instance", 0))
                mnemonic = inst_to_mnemonic.get(("LOOP", inst))
                if not mnemonic:
                    mnemonic = f"LOOP{inst}"
                mnem_key = f"LOOP:{mnemonic}"
                if mnem_key not in mnemonic_loops:
                    loop_obj = dict(loop)
                    loop_obj["_source"] = primary_key
                    loop_obj["_mnemonic"] = mnemonic
                    mnemonic_loops[mnem_key] = loop_obj

            for sched in objects.get("SCHEDULE", []):
                inst = int(sched.get("instance", 0))
                mnemonic = inst_to_mnemonic.get(("SCHED", inst)) or inst_to_mnemonic.get(("SCHEDULE", inst))
                if not mnemonic:
                    mnemonic = f"SCHED{inst}"
                mnem_key = f"SCHED:{mnemonic}"
                if mnem_key not in mnemonic_scheds:
                    sched_obj = dict(sched)
                    sched_obj["_source"] = primary_key
                    sched_obj["_mnemonic"] = mnemonic
                    mnemonic_scheds[mnem_key] = sched_obj

            for trend in objects.get("TREND", []):
                trend_key = f"{primary_key}:{trend.get('instance', '')}"
                if trend_key not in all_trends:
                    trend_copy = dict(trend)
                    trend_copy["_source"] = primary_key
                    all_trends[trend_key] = trend_copy

        # ── Phase 2: Assign instances ──
        #
        # PRESERVE original instance numbers from source variants.
        # The original programmers chose instance numbers that work with
        # the target hardware (avoiding firmware-reserved slots).
        # Renumbering sequentially causes conflicts with PFG blanks.
        #
        # Strategy:
        # - Each point keeps its original instance from the source variant
        # - When merging across variants, if two different mnemonics have
        #   the same (type, instance), the second one gets bumped to the
        #   next available instance above all used instances for that type

        mnem_to_new_inst = {}

        # Group mnemonic points by type
        points_by_type = {}
        for mnem_key, pt in mnemonic_points.items():
            ptype = pt["type"]
            points_by_type.setdefault(ptype, []).append((mnem_key, pt))

        # Assign instances: preserve originals, resolve conflicts
        for ptype in POINT_TYPES:
            pts = points_by_type.get(ptype, [])
            if not pts:
                continue

            # First pass: assign original instances, track conflicts
            used_instances = {}  # instance -> mnem_key (first to claim it)
            deferred = []  # points that need a new instance due to conflict

            for mnem_key, pt in pts:
                orig_inst = int(pt.get("instance", 0))
                if orig_inst not in used_instances:
                    used_instances[orig_inst] = mnem_key
                    mnem_to_new_inst[mnem_key] = orig_inst
                    pt["instance"] = str(orig_inst)
                else:
                    deferred.append((mnem_key, pt))

            # Second pass: assign deferred points to next available instances
            if deferred:
                max_used = max(used_instances.keys()) if used_instances else 0
                next_inst = max_used + 1
                for mnem_key, pt in deferred:
                    while next_inst in used_instances:
                        next_inst += 1
                    used_instances[next_inst] = mnem_key
                    mnem_to_new_inst[mnem_key] = next_inst
                    pt["instance"] = str(next_inst)
                    next_inst += 1

            # Sort by instance for clean output
            points_by_type[ptype].sort(key=lambda x: int(x[1].get("instance", 0)))

        # Assign loop instances
        loops_list = list(mnemonic_loops.items())
        for i, (mnem_key, loop) in enumerate(loops_list, 1):
            mnem_to_new_inst[mnem_key] = i
            loop["instance"] = str(i)

        # Assign schedule instances
        scheds_list = list(mnemonic_scheds.items())
        for i, (mnem_key, sched) in enumerate(scheds_list, 1):
            mnem_to_new_inst[mnem_key] = i
            sched["instance"] = str(i)

        # Renumber calendars, smartsensors, etc.
        calendars = list(all_calendars.values())
        for i, cal in enumerate(calendars, 1):
            cal["instance"] = str(i)

        smartsensors = list(all_smartsensors.values())
        for i, ss in enumerate(smartsensors, 1):
            ss["instance"] = str(i)

        systemgroups = list(all_systemgroups.values())
        for i, sg in enumerate(systemgroups, 1):
            sg["instance"] = str(i)

        tables = list(all_tables.values())
        for i, tbl in enumerate(tables, 1):
            tbl["instance"] = str(i)

        arrays = list(all_arrays.values())
        for i, arr in enumerate(arrays, 1):
            arr["instance"] = str(i)

        # ── Phase 3: Rewrite program code with new instance numbers ──
        # Build per-program remap: (old_type, old_inst) -> new_inst
        for sel_idx, (program, source_key, inst_to_mnemonic) in enumerate(programs):
            # Build this program's remap table
            code_remap = {}  # (type, old_inst) -> new_inst
            code = program.get("code", "")
            refs = parse_code_references(code)

            for ptype_key in list(refs.keys()):
                for old_inst in refs[ptype_key]:
                    mnem_key = program_ref_map.get((sel_idx, ptype_key, old_inst))
                    if mnem_key and mnem_key in mnem_to_new_inst:
                        code_remap[(ptype_key, old_inst)] = mnem_to_new_inst[mnem_key]

            # Apply remap to code
            def make_replacer(remap_table, program_code):
                def replace_ref(match):
                    start = match.start()
                    if start > 0 and program_code[start - 1].isdigit():
                        return match.group(0)  # network ref, don't remap
                    ptype = match.group(1)
                    old_inst = int(match.group(2))
                    new_inst = remap_table.get((ptype, old_inst))
                    if new_inst is not None:
                        return f"{ptype}{new_inst}"
                    return match.group(0)
                return replace_ref

            program["code"] = POINT_REF_PATTERN.sub(
                make_replacer(code_remap, code), code
            )
            program["instance"] = str(sel_idx + 1)

        # ── Phase 4: Remap trend references ──
        # Build a flat remap for trends: (source, type, old_inst) -> new_inst
        trend_remap = {}
        for (sel_idx, ptype, old_inst), mnem_key in program_ref_map.items():
            source_key = programs[sel_idx][1]
            if mnem_key in mnem_to_new_inst:
                trend_remap[(source_key, ptype, old_inst)] = mnem_to_new_inst[mnem_key]

        kept_trends = []
        seen_trend_names = set()
        for trend in all_trends.values():
            source = trend.get("_source", "")
            old_refs = trend.get("references", [])
            new_refs = []

            for ref in old_refs:
                m = re.match(r'\d+(AI|AO|AV|BI|BO|BV|MO|MV|LOOP|SCHED)(\d+)', ref)
                if m:
                    ref_type = m.group(1)
                    ref_inst = int(m.group(2))
                    new_inst = trend_remap.get((source, ref_type, ref_inst))
                    if new_inst is not None:
                        new_refs.append(f"{device_id}{ref_type}{new_inst}")
                    else:
                        # Keep original ref format for unmapped points
                        new_refs.append(f"{device_id}{ref_type}{ref_inst}")

            trend_name = trend.get("name", "")
            # Dedup by name, but allow multiple unnamed trends (empty name)
            if not trend_name or trend_name not in seen_trend_names:
                if trend_name:
                    seen_trend_names.add(trend_name)
                trend["references"] = new_refs
                kept_trends.append(trend)

        for i, trend in enumerate(kept_trends, 1):
            trend["instance"] = str(i)

        # ── Phase 5: Assemble final library-format JSON ──
        def clean(obj):
            return {k: v for k, v in obj.items() if not k.startswith("_")}

        objects = {
            "DEVICE": [{
                "instance": device_id,
                "name": device_name,
                "description": "",
                "location": "",
            }],
        }

        for ptype in POINT_TYPES:
            objects[ptype] = [clean(pt) for _, pt in points_by_type.get(ptype, [])]

        objects["PROGRAM"] = [clean(p) for p, _, _ in programs]
        objects["LOOP"] = [clean(l) for _, l in loops_list]
        objects["TREND"] = [clean(t) for t in kept_trends]
        objects["SCHEDULE"] = [clean(s) for _, s in scheds_list]
        objects["CALENDAR"] = [clean(c) for c in calendars]
        objects["SMARTSENSOR"] = [clean(s) for s in smartsensors]
        objects["SYSTEMGROUP"] = [clean(s) for s in systemgroups]
        objects["TABLE"] = [clean(t) for t in tables]
        objects["ARRAY"] = [clean(a) for a in arrays]

        counts = {k: len(v) for k, v in objects.items() if isinstance(v, list) and v}

        # Build source manifest for traceability
        sources = []
        for prog, src, _ in programs:
            sources.append({
                "program": prog.get("name", ""),
                "from": src,
            })

        # Build ARRAY/TABLE source mapping for binary post-processing
        # Maps object name -> source variant key (e.g. "VAV/VAV-IS10001")
        array_table_sources = {}
        for arr in arrays:
            src = arr.get("_source", "")
            name = arr.get("name", "")
            if src and name:
                array_table_sources[name] = src
        for tbl in tables:
            src = tbl.get("_source", "")
            name = tbl.get("name", "")
            if src and name:
                array_table_sources[name] = src

        composed_meta = dict(all_meta)
        composed_meta.update({
            "composed": True,
            "sources": sources,
            "device_id": device_id,
            "device_name": device_name,
            "graphics_sources": all_graphics_sources,
            "array_table_sources": array_table_sources,
        })

        result = {
            "id": "composed",
            "category": "COMPOSED",
            "format": "composed",
            "description": "Custom composed controller",
            "meta": composed_meta,
            "graphics": all_graphics,
            "objects": objects,
            "bas_files": {},
            "grp_files": all_grp_files,
            "counts": counts,
        }

        # Validate that all referenced graphics exist on disk
        self._validate_graphics(result)

        logger.info(
            f"Composed {len(programs)} programs, "
            f"{sum(len(v) for v in objects.values() if isinstance(v, list))} objects, "
            f"{len(mnemonic_points)} unique points by mnemonic"
        )

        return result

    def save_composition(self, name: str, composition: dict) -> Path:
        """Save a composed controller to the library under COMPOSED category."""
        save_dir = self.cfg.library_root / "COMPOSED"
        save_dir.mkdir(parents=True, exist_ok=True)

        # Use the provided name as the filename
        safe_name = re.sub(r'[^\w\-]', '_', name)
        composition["id"] = safe_name
        save_path = save_dir / f"{safe_name}.json"
        save_path.write_text(json.dumps(composition, indent=2))
        logger.info(f"Saved composition: {save_path}")
        return save_path

    def _validate_graphics(self, composition: dict):
        """Validate that all graphics referenced in GroupAssets and GRP files exist on disk.

        Logs warnings for missing files but does not block composition.
        """
        meta = composition.get("meta", {})
        graphics_sources = meta.get("graphics_sources", [])
        grp_files = composition.get("grp_files", {})
        shared_dir = self.cfg.assets_root / "_shared"

        # Build list of asset directories to search
        asset_dirs = []
        seen_variants = set()
        for gs in graphics_sources:
            vkey = f"{gs.get('from_category', '')}/{gs.get('from_variant', '')}"
            if vkey not in seen_variants:
                seen_variants.add(vkey)
                d = self.cfg.assets_root / gs.get("from_category", "") / gs.get("from_variant", "")
                if d.exists():
                    asset_dirs.append(d)
        if shared_dir.exists():
            asset_dirs.append(shared_dir)

        # Collect all referenced files from GRP JSONs
        referenced = set()
        import json as _json
        for grp_name, grp_data in grp_files.items():
            text = _json.dumps(grp_data)
            for m in re.finditer(
                r'"(?:external_file|gel_filename|image|background_image)"\s*:\s*"([^"]+)"', text
            ):
                val = m.group(1).replace('\\\\', '/').replace('\\', '/').replace('pic/', '')
                if val and '.' in val:
                    referenced.add(val)

        # Collect from GroupAssets
        for ga in meta.get("GroupAssets", []):
            job_path = ga.get("JobPath", "").replace('\\', '/').replace('pic/', '')
            if job_path and '.' in job_path:
                referenced.add(job_path)

        # Check each referenced file
        missing = []
        found = 0
        for ref in sorted(referenced):
            ref_norm = ref.replace('\\', '/')
            exists = False
            for d in asset_dirs:
                if (d / ref_norm).exists():
                    exists = True
                    break
                # Fallback: search by filename only
                if list(d.rglob(Path(ref_norm).name)):
                    exists = True
                    break
            if exists:
                found += 1
            else:
                missing.append(ref)

        if missing:
            logger.warning(
                f"Graphics validation: {len(missing)} referenced files not found on disk: "
                + ", ".join(missing[:20])
                + (f" ... and {len(missing)-20} more" if len(missing) > 20 else "")
            )
        logger.info(f"Graphics validation: {found}/{found + len(missing)} referenced files found")

    def list_compositions(self) -> list:
        """List all saved compositions."""
        save_dir = self.cfg.library_root / "COMPOSED"
        if not save_dir.exists():
            return []

        compositions = []
        for jf in sorted(save_dir.glob("*.json")):
            try:
                data = json.loads(jf.read_text())
                compositions.append({
                    "id": data.get("id", jf.stem),
                    "description": data.get("description", ""),
                    "counts": data.get("counts", {}),
                    "sources": data.get("meta", {}).get("sources", []),
                })
            except Exception:
                pass
        return compositions

    def load_composition(self, name: str) -> Optional[dict]:
        """Load a saved composition by name."""
        safe_name = re.sub(r'[^\w\-]', '_', name)
        save_path = self.cfg.library_root / "COMPOSED" / f"{safe_name}.json"
        if not save_path.exists():
            return None
        try:
            return json.loads(save_path.read_text())
        except Exception:
            return None

    def delete_composition(self, name: str) -> bool:
        """Delete a saved composition."""
        safe_name = re.sub(r'[^\w\-]', '_', name)
        save_path = self.cfg.library_root / "COMPOSED" / f"{safe_name}.json"
        if save_path.exists():
            save_path.unlink()
            return True
        return False

    def list_blank_panels(self) -> list:
        """List available blank controller .panx files for generation."""
        blanks_dir = Path("/srv/dfa/shared/files/vendors/reliable/blanks")
        if not blanks_dir.exists():
            return []
        result = []
        for d in sorted(blanks_dir.iterdir()):
            if d.is_dir():
                panx_files = list(d.glob("*.panx"))
                if panx_files:
                    result.append({
                        "model": d.name,
                        "panx": panx_files[0].name,
                        "path": str(panx_files[0]),
                    })
        return result

    def _binary_post_process(self, pan_path: Path, composition: dict):
        """Post-process a PFG-generated .pan to restore data lost in XML roundtrip.

        PFG generates .pan from XML, but the XML export/import cycle drops:
        - Loop input/setpoint/output ObjID bindings
        - Present values for some object types
        - Array/table data in programs

        This method reads the generated .pan, patches in data from the
        composition's source library entries (which have binary-enriched data),
        and writes the corrected .pan back.
        """
        from app.pan_binary import PanBinary, PanWriter
        import struct

        writer = PanWriter(pan_path.read_bytes())
        parser = PanBinary(writer.data)
        patched = 0

        objects = composition.get("objects", {})

        # Restore LOOP data regions from source .panx binaries
        # PFG generates loops with NO ObjID refs — completely empty shells.
        # The source .pan has the full loop structure (386 bytes) with:
        #   - ObjID refs at offsets 71 (output) and 265 (input)
        #   - PID parameters, present values, action mode
        # We copy the entire loop data region from source, like PFU does.
        meta = composition.get("meta", {})
        source_cache = {}  # variant_key -> PanBinary

        # Build a lookup of which source variant each loop came from
        # Use the composition's source tracking
        lib_loops = objects.get("LOOP", [])
        sources_list = meta.get("sources", [])

        # Find the primary variant (most programs come from here)
        primary_variant = meta.get("primary_variant", "")

        # Try to load source binary for the primary variant
        def _load_source(variant_key):
            if variant_key in source_cache:
                return source_cache[variant_key]
            parts = variant_key.split("/", 1) if "/" in variant_key else []
            if len(parts) != 2:
                return None
            cat_key, var_id = parts
            folder_name = self._cat_folder(cat_key)
            cat_dir = self.cfg.upload_root / folder_name
            src = next(cat_dir.rglob(f"{var_id}.panx"), None) or next(cat_dir.rglob(f"{var_id}.pan"), None)
            if src:
                try:
                    source_cache[variant_key] = PanBinary.from_panx(src) if str(src).endswith('.panx') else PanBinary.from_file(src)
                    return source_cache[variant_key]
                except Exception as e:
                    logger.warning(f"Failed to load source binary {src}: {e}")
            return None

        # Try all variant sources to find loop data
        variant_keys = set()
        if primary_variant:
            variant_keys.add(primary_variant)
        for s in sources_list:
            src_str = s.get("from", "")
            if "/" in src_str:
                variant_keys.add(src_str)
        # Also check array_table_sources for variant keys
        for vk in meta.get("array_table_sources", {}).values():
            if "/" in str(vk):
                variant_keys.add(str(vk))

        # Build source object lookup from ALL available source binaries.
        # Byte-level copy for anything PFG XML roundtrip misses:
        # LOOP (bindings), TABLE (in/out rows), ARRAY (values),
        # TREND (multi-point refs), SCHEDULE (weekly data), etc.
        source_objects = {}  # bare_name -> (source_obj, variant_key)
        for vk in variant_keys:
            src_pan = _load_source(vk)
            if not src_pan:
                continue
            for sobj in src_pan.objects:
                sname = sobj['name'].strip('\x00')
                bare = sname.replace('{device-name}', '').lstrip('-')
                import re as _re2
                bare = _re2.sub(r'^\d+-', '', bare) if bare else bare
                if bare and len(sobj.get('data_region', b'')) > 20:
                    source_objects[bare] = (sobj, vk)

        # For each object in the PFG-generated .pan, check if the source
        # has a richer version. If the source data region is larger (has more
        # data that PFG dropped), do a byte-level copy.
        for target_obj in parser.objects:
            tname = target_obj['name'].strip('\x00')
            tbare = tname.replace('{device-name}', '').lstrip('-')
            target_size = len(target_obj.get('data_region', b''))

            src_match = source_objects.get(tbare)
            if not src_match:
                for sbare, sdata in source_objects.items():
                    if sbare in tbare or tbare in sbare:
                        src_match = sdata
                        break

            if not src_match:
                continue

            src_obj, vk = src_match
            source_size = len(src_obj.get('data_region', b''))

            # Only copy if source has MORE data than PFG generated
            # (meaning PFG stripped something)
            if source_size > target_size + 10:
                if writer.copy_data_region(tname, src_obj['data_region']):
                    patched += 1
                    logger.info(
                        f"Binary post-process: restored '{tname}' "
                        f"({source_size} bytes from source vs {target_size} in PFG) from {vk}"
                    )

        # Restore present values from library
        for ptype in ['AO', 'AV', 'BO', 'BV', 'MO', 'MV']:
            for pt in objects.get(ptype, []):
                pt_name = pt.get("name", "")
                pv = pt.get("present_value")
                if pt_name and pv is not None:
                    try:
                        pv_float = float(pv)
                        if pv_float != 0.0:  # Don't overwrite with zeros
                            if writer.set_present_value(pt_name, pv_float):
                                patched += 1
                    except (ValueError, TypeError):
                        pass

        # Restore ARRAY and TABLE data regions from source .panx binaries
        # The XML roundtrip through PFG drops all ARRAY values and TABLE in/out pairs.
        # We find the source .panx for each ARRAY/TABLE, parse its binary, and copy
        # the raw data region into the PFG-generated .pan.
        meta = composition.get("meta", {})
        array_table_sources = meta.get("array_table_sources", {})

        if array_table_sources:
            # Cache parsed source binaries to avoid re-reading
            source_binary_cache = {}  # variant_key -> PanBinary

            for obj_name, variant_key in array_table_sources.items():
                try:
                    if variant_key not in source_binary_cache:
                        # variant_key is "CATEGORY/variant_id" e.g. "VAV/VAV-IS10001"
                        parts = variant_key.split("/", 1)
                        if len(parts) != 2:
                            continue
                        cat_key, var_id = parts
                        folder_name = self._cat_folder(cat_key)
                        cat_dir = self.cfg.upload_root / folder_name

                        # Find source .panx or .pan
                        src_panx = next(cat_dir.rglob(f"{var_id}.panx"), None)
                        src_pan = next(cat_dir.rglob(f"{var_id}.pan"), None)

                        if src_panx:
                            source_binary_cache[variant_key] = PanBinary.from_panx(src_panx)
                        elif src_pan:
                            source_binary_cache[variant_key] = PanBinary.from_file(src_pan)
                        else:
                            logger.warning(
                                f"Binary post-process: source .panx/.pan not found for "
                                f"{variant_key} in {cat_dir}"
                            )
                            continue

                    source_pan = source_binary_cache[variant_key]

                    # Find the matching object in the source binary by name
                    # Names may differ by device prefix, so match on the suffix
                    # (e.g. source has "1001-AY1", target has "{device-name}-AY1")
                    source_obj = None
                    obj_suffix = obj_name.split('}')[-1] if '}' in obj_name else obj_name
                    # Strip leading dash from suffix for matching
                    obj_suffix_bare = obj_suffix.lstrip('-')

                    for sobj in source_pan.objects:
                        sname = sobj['name']
                        s_suffix = sname.split('}')[-1] if '}' in sname else sname
                        s_suffix_bare = s_suffix.lstrip('-')
                        # Also try stripping numeric device prefix
                        # e.g. "1001-AY1" -> "-AY1" -> "AY1"
                        import re as _re
                        s_stripped = _re.sub(r'^\d+-', '', sname)

                        if (s_suffix_bare == obj_suffix_bare or
                            s_stripped == obj_suffix_bare or
                            sname.endswith(obj_suffix_bare)):
                            source_obj = sobj
                            break

                    if source_obj is None:
                        logger.debug(
                            f"Binary post-process: no source object matching "
                            f"'{obj_name}' (suffix '{obj_suffix_bare}') in {variant_key}"
                        )
                        continue

                    # Instead of copying the entire data region (which can corrupt
                    # structural metadata), write individual float values from the
                    # source ARRAY/TABLE into the target using set_present_value.
                    # PFG creates the correct object structure — we just fill in values.
                    source_data = source_obj['data_region']
                    if not source_data:
                        continue

                    # Extract float values from source data region (0x44 tag = float)
                    source_floats = []
                    i = 0
                    while i < len(source_data) - 5:
                        if source_data[i] == 0x44:
                            try:
                                val = struct.unpack('>f', source_data[i+1:i+5])[0]
                                if val == val and -1e9 < val < 1e9:
                                    source_floats.append((i, val))
                            except struct.error:
                                pass
                            i += 5
                        else:
                            i += 1

                    if not source_floats:
                        continue

                    # Find the target object and write floats at matching positions
                    target_name = obj_name
                    # Find in writer's data
                    name_bytes = target_name.encode('utf-8')
                    try:
                        name_pos = bytes(writer.data).index(name_bytes + b'\x00')
                    except ValueError:
                        # Try without null terminator
                        try:
                            name_pos = bytes(writer.data).index(name_bytes)
                        except ValueError:
                            continue

                    name_end = name_pos + len(name_bytes) + 1
                    # Find target data region
                    next_mu = bytes(writer.data).find(b'\x4d\x75', name_end + 10)
                    if next_mu < 0:
                        next_mu = min(name_end + 500, len(writer.data))

                    target_region = writer.data[name_end:next_mu]

                    # Find float slots in target and overwrite with source values
                    float_idx = 0
                    ti = 0
                    while ti < len(target_region) - 5 and float_idx < len(source_floats):
                        if target_region[ti] == 0x44:
                            # Write source float value here
                            abs_pos = name_end + ti + 1
                            writer.data[abs_pos:abs_pos + 4] = struct.pack('>f', source_floats[float_idx][1])
                            float_idx += 1
                            ti += 5
                        else:
                            ti += 1

                    if float_idx > 0:
                        patched += float_idx
                        logger.info(
                            f"Binary post-process: restored {float_idx} float values for "
                            f"'{obj_name}' from {variant_key}"
                        )

                except Exception as e:
                    logger.warning(
                        f"Binary post-process: failed to restore '{obj_name}' "
                        f"from {variant_key}: {e}"
                    )

        if patched > 0:
            writer.save(pan_path)
            logger.info(f"Binary post-processing: patched {patched} values/bindings in {pan_path.name}")
        else:
            logger.info("Binary post-processing: no patches needed")

    def _generate_values_document(self, composition: dict, output_path: Path):
        """Generate a companion text document listing all configured values.

        PFG may not preserve presentValue and loop PID settings in the .pan
        binary. This document provides a complete reference of all values
        from the source library for manual verification or entry.
        """
        meta = composition.get("meta", {})
        device_name = meta.get("device_name", "{device-name}")
        device_id = meta.get("device_id", "900")
        objects = composition.get("objects", {})

        lines = []
        lines.append(f"Controller Values Reference")
        lines.append(f"{'=' * 60}")
        lines.append(f"Device Name: {device_name}")
        lines.append(f"Device ID:   {device_id}")
        lines.append(f"Generated:   {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        # ── Points ──
        type_labels = {
            "AV": "Analog Values", "AI": "Analog Inputs", "AO": "Analog Outputs",
            "BV": "Binary Values", "BI": "Binary Inputs", "BO": "Binary Outputs",
            "MV": "Multistate Values", "MO": "Multistate Outputs",
        }
        for ptype in ["AV", "AI", "AO", "BV", "BI", "BO", "MV", "MO"]:
            pts = objects.get(ptype, [])
            if not pts:
                continue
            lines.append(f"--- {type_labels.get(ptype, ptype)} ---")
            lines.append(f"{'Inst':>5}  {'Name':<35}  {'Value':>12}  {'Range':>6}  {'Unit':>6}")
            lines.append(f"{'-'*5}  {'-'*35}  {'-'*12}  {'-'*6}  {'-'*6}")
            for p in sorted(pts, key=lambda x: int(x.get("instance", 0))):
                name = p.get("name", "").replace("{device-name}", device_name)
                pv = p.get("present_value", "")
                rng = p.get("range", "")
                unit = p.get("unit", "")
                inst = p.get("instance", "")
                lines.append(f"{inst:>5}  {name:<35}  {str(pv):>12}  {str(rng):>6}  {str(unit):>6}")
            lines.append("")

        # ── Loops ──
        # Build a name lookup for suggesting input/setpoint
        all_points = {}
        for ptype in ["AV", "AI", "AO", "BV", "BI", "BO", "MV", "MO"]:
            for p in objects.get(ptype, []):
                pname = p.get("name", "").replace("{device-name}", device_name)
                all_points[pname] = f"{ptype}{p.get('instance','')}"

        # Common loop-to-point mappings by mnemonic suffix
        _loop_bindings = {
            "FLO-CTRL-LOOP": {"input": "FLO", "setpoint": "FLO-SP"},
            "FLO-LOOP":      {"input": "FLO", "setpoint": "FLO-SP"},
            "RH-LOOP":       {"input": "RMT-ACT", "setpoint": "HTG-SP"},
            "RHT-LOOP":      {"input": "RMT-ACT", "setpoint": "HTG-SP"},
            "RHV-LOOP":      {"input": "RMT-ACT", "setpoint": "HTG-SP"},
            "CLG-LOOP":      {"input": "SAT", "setpoint": "CLG-SAT-SP"},
            "HTG-LOOP":      {"input": "SAT", "setpoint": "HTG-SAT-SP"},
            "DMP-LOOP":      {"input": "DMP-POS", "setpoint": "DMP-SP"},
            "ECON-LOOP":     {"input": "MAT", "setpoint": "ECON-SP"},
            "OAD-LOOP":      {"input": "OAD-POS", "setpoint": "OAD-SP"},
            "OAD-LL-LOOP":   {"input": "MAT", "setpoint": "MAT-LL-SP"},
            "OA-FLO-LOOP":   {"input": "OA-FLO", "setpoint": "OA-FLO-SP"},
            "SA-STP-LOOP":   {"input": "SA-STP", "setpoint": "SA-STP-SP"},
            "SAT-LOOP":      {"input": "SAT", "setpoint": "SAT-SP"},
            "SF-SPD-LOOP":   {"input": "SA-STP", "setpoint": "SA-STP-SP"},
            "SF-SPD-TEMP-LOOP": {"input": "SAT", "setpoint": "SAT-SP"},
            "BLDG-P-LOOP":   {"input": "BLDG-P", "setpoint": "BLDG-P-SP"},
            "HCV-LOOP":      {"input": "SAT", "setpoint": "HTG-SAT-SP"},
            "PHV-LOOP":      {"input": "SAT", "setpoint": "HTG-SAT-SP"},
            # SBS custom loops
            "DSP-LOOP":      {"input": "DSP", "setpoint": "DSP-SP"},
            "MAT-LO-LIMIT-LOOP": {"input": "MAT", "setpoint": "MAT-LO-SP"},
            "MAT-LOOP":      {"input": "MAT", "setpoint": "MAT-SP"},
            "RA-FLOW-LOOP":  {"input": "RA-FLOW", "setpoint": "RA-FLOW-SP"},
            "CHW-VLV-LOOP":  {"input": "SAT", "setpoint": "CLG-SAT-SP"},
            "HW-VLV-LOOP":   {"input": "SAT", "setpoint": "HTG-SAT-SP"},
        }

        # Auto-discover loop bindings from program code:
        # Look for patterns like "LOOP1 = AV4" or "AV5 = LOOP1" in programs
        import re as _re_loop
        _loop_code_bindings = {}  # loop_instance -> {"input": "TYPE:INST", "setpoint": "TYPE:INST"}
        for prog in objects.get("PROGRAM", []):
            code = prog.get("code", "").replace("{device-name}", device_name)
            for line in code.split('\n'):
                stripped = line.strip()
                # Pattern: LOOP1 = expression (setpoint or output assignment)
                # Pattern: AV4 = LOOP1 (loop output to a point)
                # The actual input/setpoint are configured in RC Studio, not in code.
                # But we can find which programs reference which loops
                pass

        loops = objects.get("LOOP", [])
        if loops:
            lines.append(f"--- Loops (PID Settings + Binary Bindings) ---")
            lines.append(f"{'Inst':>5}  {'Name':<30}  {'P':>8}  {'I':>8}  {'D':>8}  {'Bias':>8}  {'DB':>8}  {'Action':>8}  {'I-Units':>8}")
            lines.append(f"{'-'*5}  {'-'*30}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}")
            for l in sorted(loops, key=lambda x: int(x.get("instance", 0))):
                name = l.get("name", "").replace("{device-name}", device_name)
                lines.append(
                    f"{l.get('instance',''):>5}  {name:<30}  "
                    f"{l.get('proportional',''):>8}  {l.get('integral',''):>8}  "
                    f"{l.get('derivative',''):>8}  {l.get('bias',''):>8}  "
                    f"{l.get('deadband',''):>8}  {l.get('action',''):>8}  "
                    f"{l.get('integralunits',''):>8}"
                )
                # Check binary-enriched data first (from library enrichment)
                has_binary = False
                if l.get('output_ref') or l.get('input_ref') or l.get('setpoint_ref') or l.get('setpoint_value') is not None:
                    has_binary = True
                    if l.get('output_ref'):
                        out_name = l.get('output_name', '')
                        lines.append(f"         -> Output:   {l['output_ref']}" + (f" ({out_name})" if out_name else ""))
                    if l.get('input_ref'):
                        inp_name = l.get('input_name', '')
                        lines.append(f"         -> Input:    {l['input_ref']}" + (f" ({inp_name})" if inp_name else ""))
                    if l.get('setpoint_ref'):
                        sp_name = l.get('setpoint_name', '')
                        lines.append(f"         -> Setpoint: {l['setpoint_ref']}" + (f" ({sp_name})" if sp_name else ""))
                    elif l.get('setpoint_value') is not None:
                        lines.append(f"         -> Setpoint: {l['setpoint_value']:.1f} (direct value)")
                    if l.get('binary_proportional') is not None:
                        lines.append(f"         -> PID (binary): P={l.get('binary_proportional','-')} I={l.get('binary_integral','-')} D={l.get('binary_derivative','-')}")

                if not has_binary:
                    # Fallback: try to suggest input/setpoint from loop name
                    loop_mnem = name.split("-", 1)[1] if "-" in name else name
                    prefix = name.rsplit("-" + loop_mnem.split("-")[0], 1)[0] if "-" in name else device_name
                    import re as _re_lm
                    loop_mnem_clean = _re_lm.sub(r'\d+$', '', loop_mnem)
                    binding = _loop_bindings.get(loop_mnem) or _loop_bindings.get(loop_mnem_clean)
                    if binding:
                        inp_name = f"{prefix}-{binding['input']}"
                        sp_name = f"{prefix}-{binding['setpoint']}"
                        inp_ref = all_points.get(inp_name, f"? ({binding['input']})")
                        sp_ref = all_points.get(sp_name, f"? ({binding['setpoint']})")
                        lines.append(f"         -> Input: {inp_ref} ({inp_name})")
                        lines.append(f"         -> Setpoint: {sp_ref} ({sp_name})")
                    else:
                        lines.append(f"         -> Input/Setpoint: not available in library data")
            lines.append("")

        # ── Programs ──
        progs = objects.get("PROGRAM", [])
        if progs:
            lines.append(f"--- Programs ---")
            lines.append(f"{'Inst':>5}  {'Name':<35}  {'Enabled':>8}")
            lines.append(f"{'-'*5}  {'-'*35}  {'-'*8}")
            import re as _re_val
            manual_progs = []
            for p in sorted(progs, key=lambda x: int(x.get("instance", 0))):
                name = p.get("name", "").replace("{device-name}", device_name)
                pv = p.get("present_value", "1")
                enabled = "Yes" if str(pv) == "1" else "No"
                code = p.get("code", "")
                has_ay = bool(_re_val.search(r'\bAY\d+\b', code))
                tag = "  ** MANUAL ENTRY REQUIRED (ARRAY refs)" if has_ay else ""
                lines.append(f"{p.get('instance',''):>5}  {name:<35}  {enabled:>8}{tag}")
                if has_ay:
                    manual_progs.append(p)
            lines.append("")

            # Full code listing for programs that need manual entry
            if manual_progs:
                lines.append("=" * 70)
                lines.append("PROGRAMS REQUIRING MANUAL CODE ENTRY IN RC STUDIO")
                lines.append("PFG cannot compile ARRAY (AY) references.")
                lines.append("Copy/paste the code below into each program in RC Studio.")
                lines.append("=" * 70)
                for p in manual_progs:
                    name = p.get("name", "").replace("{device-name}", device_name)
                    code = p.get("code", "").replace("{device-name}", device_name)
                    lines.append("")
                    lines.append(f"--- Program {p.get('instance','')}: {name} ---")
                    lines.append(code)
                    lines.append(f"--- End Program {p.get('instance','')} ---")
                lines.append("")

        # ── Schedules ──
        scheds = objects.get("SCHEDULE", [])
        if scheds:
            lines.append(f"--- Schedules ---")
            lines.append(f"{'Inst':>5}  {'Name':<35}  {'Enabled':>8}  {'Range':>6}")
            lines.append(f"{'-'*5}  {'-'*35}  {'-'*8}  {'-'*6}")
            for s in sorted(scheds, key=lambda x: int(x.get("instance", 0))):
                name = s.get("name", "").replace("{device-name}", device_name)
                pv = s.get("present_value", "1")
                enabled = "Yes" if str(pv) == "1" else "No"
                lines.append(f"{s.get('instance',''):>5}  {name:<35}  {enabled:>8}  {s.get('range',''):>6}")
            lines.append("")

        # ── Trends ──
        trends = objects.get("TREND", [])
        if trends:
            lines.append(f"--- Trends ---")
            lines.append(f"{'Inst':>5}  {'Name':<35}  {'Type':<15}  {'Interval':>10}  {'References'}")
            lines.append(f"{'-'*5}  {'-'*35}  {'-'*15}  {'-'*10}  {'-'*20}")
            for t in sorted(trends, key=lambda x: int(x.get("instance", 0))):
                name = t.get("name", "").replace("{device-name}", device_name)
                raw_refs = [r for r in t.get("references", []) if r]
                # Replace device ID prefix in refs with device_name
                import re as _re_trend
                display_refs = []
                for r in raw_refs:
                    m = _re_trend.match(r'(\d+)(.*)', r)
                    if m and device_id:
                        display_refs.append(f"{device_name}{m.group(2)}")
                    else:
                        display_refs.append(r)
                refs = ", ".join(display_refs)
                lines.append(
                    f"{t.get('instance',''):>5}  {name:<35}  "
                    f"{t.get('type','SINGLETREND'):<15}  "
                    f"{t.get('interval',''):>10}  {refs}"
                )
            lines.append("")

        # ── SmartSensors ──
        sensors = objects.get("SMARTSENSOR", [])
        if sensors:
            lines.append(f"--- SMART-Net Sensors ---")
            for s in sorted(sensors, key=lambda x: int(x.get("instance", 0))):
                name = s.get("name", "").replace("{device-name}", device_name)
                lines.append(f"  {s.get('instance',''):>3}  {name}")
            lines.append("")

        # ── SystemGroups — full layout spec for recreating graphics ──
        sgroups = objects.get("SYSTEMGROUP", [])
        grp_files = composition.get("grp_files", {})
        if sgroups:
            lines.append("=" * 70)
            lines.append("SYSTEM GROUP LAYOUT REFERENCE")
            lines.append("Use this data to recreate system group graphics in RC Studio.")
            lines.append("=" * 70)

            for sg in sorted(sgroups, key=lambda x: int(x.get("instance", 0))):
                name = sg.get("name", "").replace("{device-name}", device_name)
                lines.append("")
                lines.append(f"--- System Group {sg.get('instance','')}: {name} ---")
                lines.append(f"  Graphic: {sg.get('groupgraphic', '')}")

                # Find matching GRP JSON
                grp_key = None
                jsonpath = sg.get("jsonpath", "")
                import re as _re_grp
                m = _re_grp.search(r'(\d+GRP\d+)', jsonpath)
                if m:
                    grp_key = m.group(1)

                grp_data = grp_files.get(grp_key, {}) if grp_key else {}
                if not grp_data:
                    # Try all grp files by instance number
                    for gk, gd in grp_files.items():
                        if gk.endswith(f"GRP{sg.get('instance', '')}"):
                            grp_data = gd
                            break

                if not grp_data:
                    lines.append("  (No GRP layout data available)")
                    continue

                # Canvas
                bg_w = grp_data.get("background_width", 0)
                bg_h = grp_data.get("background_height", 0)
                bg_img = grp_data.get("background_image", "")
                lines.append(f"  Canvas: {bg_w}x{bg_h}")
                if bg_img:
                    lines.append(f"  Background Image: {bg_img}")
                lines.append("")

                # Elements
                points = grp_data.get("points", [])
                lines.append(f"  Elements ({len(points)}):")
                lines.append(f"  {'#':>3}  {'Type':<10}  {'Image/Animation':<45}  {'Pos (x,y)':<14}  {'Size (w x h)':<14}  {'Font':>4}  {'Colors (norm/hi/lo)'}")
                lines.append(f"  {'-'*3}  {'-'*10}  {'-'*45}  {'-'*14}  {'-'*14}  {'-'*4}  {'-'*30}")

                for i, pt in enumerate(points, 1):
                    gel = pt.get("gel_filename", "")
                    ext = pt.get("external_file", "")
                    gel_type = pt.get("gel_type", "")
                    img = ext or gel or ""
                    img = img.replace("pic\\", "")

                    x = pt.get("x-pos", 0)
                    y = pt.get("y-pos", 0)
                    w = pt.get("width", 0)
                    h = pt.get("height", 0)
                    font = pt.get("font_size", "")
                    norm_rgb = pt.get("normal_colour_RGB", 0)
                    hi_rgb = pt.get("on_high_colour_RGB", 0)
                    lo_rgb = pt.get("off_low_colour_RGB", 0)

                    def rgb_hex(v):
                        if not v:
                            return ""
                        try:
                            return f"#{int(v):06X}"
                        except (ValueError, TypeError):
                            return ""

                    colors = f"{rgb_hex(norm_rgb)} {rgb_hex(hi_rgb)} {rgb_hex(lo_rgb)}".strip()
                    pos = f"({x},{y})"
                    size = f"{w}x{h}" if w or h else ""

                    lines.append(f"  {i:>3}  {gel_type:<10}  {img:<45}  {pos:<14}  {size:<14}  {font:>4}  {colors}")

                    # Show BACnet reference if it has one
                    bdev = pt.get("BACnet_device", 0)
                    binst = pt.get("BACnet_instance", 0)
                    disp_type = pt.get("display_type", "")
                    disp_text = pt.get("display_text", "")
                    role = pt.get("role", "")
                    sec_link = pt.get("secondary_link", "")

                    extras = []
                    if bdev or binst:
                        # Show device name instead of raw ID for template mode
                        dev_label = device_name if device_name != "{device-name}" else "{device-name}"
                        if bdev and bdev != 0:
                            extras.append(f"Point={dev_label}:{binst}")
                        elif binst:
                            extras.append(f"Point=self:{binst}")
                    if disp_type and disp_type != "value":
                        extras.append(f"display={disp_type}")
                    if disp_text:
                        extras.append(f"text=\"{disp_text}\"")
                    if role and role != "operator":
                        extras.append(f"role={role}")
                    if sec_link:
                        extras.append(f"link={sec_link}")

                    # Landing pad info
                    lp = pt.get("landing_pad", {})
                    if lp.get("enabled"):
                        lp_w = lp.get("width", 0)
                        lp_h = lp.get("height", 0)
                        lp_border = "border" if lp.get("border") else ""
                        extras.append(f"pad={lp_w}x{lp_h} {lp_border}".strip())

                    if extras:
                        lines.append(f"       {' | '.join(extras)}")

                # Asset files needed
                asset_files = set()
                for pt in points:
                    for field in ["gel_filename", "external_file"]:
                        v = pt.get(field, "")
                        if v:
                            asset_files.add(v.replace("pic\\", ""))
                    lp_img = pt.get("landing_pad", {}).get("image", "")
                    if lp_img:
                        asset_files.add(lp_img)

                if asset_files:
                    lines.append("")
                    lines.append(f"  Required Assets:")
                    for af in sorted(asset_files):
                        lines.append(f"    - {af}")

            lines.append("")

        content = "\n".join(lines)
        output_path.write_text(content)
        logger.info(f"Generated values document: {output_path} ({len(lines)} lines)")
        return output_path

    def _extract_blank_pan(self, blank_panx: Path, work_dir: Path) -> Path:
        """Extract the .pan file from a blank .panx template."""
        import shutil
        import zipfile

        tmp_zip = work_dir / "blank.zip"
        shutil.copy2(blank_panx, tmp_zip)

        try:
            with zipfile.ZipFile(tmp_zip, "r") as z:
                z.extractall(work_dir / "blank_contents")
        except zipfile.BadZipFile:
            raise ValueError(f"{blank_panx.name} is not a valid ZIP archive")
        finally:
            tmp_zip.unlink(missing_ok=True)

        pan_files = list((work_dir / "blank_contents").rglob("*.pan"))
        if not pan_files:
            raise ValueError(f"No .pan found inside {blank_panx.name}")
        return pan_files[0]

    def _run_pfg_generate(self, input_pan: Path, changes_xml: Path,
                          output_pan: Path, work_dir: Path,
                          device_id: str = None, device_name: str = None) -> Path:
        """Run PFG to merge changes XML into a .pan file.

        PFG command:
          wine PanelFileGenerator.exe -i input.pan -o output.pan -c changes.xml
            [-b BACnet_ID] [-n PanelName]
        """
        import fcntl
        import shutil
        import subprocess
        import time
        from app.extractor import PFG_WORK_DIR, PFG_LOCK_FILE, to_wine_path

        PFG_LOCK_FILE.touch(exist_ok=True)
        with open(PFG_LOCK_FILE, 'r+') as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                pfg_dir = Path(PFG_WORK_DIR)
                existing_pans = set(pfg_dir.glob("*.pan"))
                existing_xmls = set(pfg_dir.glob("*.xml"))

                cmd = [
                    self.cfg.wine_bin,
                    str(self.cfg.pfg_exe),
                    "-i", to_wine_path(input_pan),
                    "-o", to_wine_path(output_pan),
                    "-c", to_wine_path(changes_xml),
                    "-f", to_wine_path(work_dir / "pfg.log"),
                ]
                if device_id:
                    cmd.extend(["-b", str(device_id)])
                if device_name and device_name != "{device-name}":
                    cmd.extend(["-n", device_name])

                logger.info(f"PFG generate: {' '.join(cmd)}")
                env = {**os.environ, "WINEDEBUG": "-all"}

                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env=env, cwd=PFG_WORK_DIR,
                )

                deadline = time.time() + self.cfg.pfg_timeout
                while time.time() < deadline:
                    time.sleep(0.5)
                    if output_pan.exists() and output_pan.stat().st_size > 0:
                        time.sleep(1.0)
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        break
                    new_pans = set(pfg_dir.glob("*.pan")) - existing_pans
                    if new_pans:
                        time.sleep(1.0)
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        for f in new_pans:
                            if not output_pan.exists():
                                shutil.move(str(f), str(output_pan))
                            else:
                                f.unlink()
                        break
                    if proc.poll() is not None:
                        # Process ended, check one more time
                        new_pans = set(pfg_dir.glob("*.pan")) - existing_pans
                        for f in new_pans:
                            if not output_pan.exists():
                                shutil.move(str(f), str(output_pan))
                        break

                if proc.poll() is None:
                    try:
                        proc.kill()
                        proc.wait(timeout=5)
                    except Exception:
                        pass

                # Clean up stray files PFG left in its CWD
                for f in set(pfg_dir.glob("*.xml")) - existing_xmls:
                    f.unlink(missing_ok=True)

            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)

        if not output_pan.exists():
            log_content = ""
            log_file = work_dir / "pfg.log"
            if log_file.exists():
                log_content = log_file.read_text(errors="replace")
            raise RuntimeError(
                f"PFG did not generate .pan file. Log: {log_content[:500]}"
            )

        return output_pan

    def generate_pan(self, composition: dict, blank_model: str = None) -> Path:
        """Generate a .pan file from a composed controller.

        Pipeline (standard — multi-variant):
          1. Generate changes XML from composition
          2. Extract blank .pan from the specified controller model template
          3. Run PFG: blank .pan + changes XML -> output .pan
          4. Binary post-process to restore data PFG drops

        Pipeline (optimized — single-variant):
          If all programs come from one source variant, bypass PFG entirely
          and do a PFU-style binary copy. This preserves ALL data (loops,
          arrays, tables, trends) with zero loss.

        Returns path to generated .pan in _output dir.
        """
        import shutil
        import time

        meta = composition.get("meta", {})
        sources = meta.get("sources", [])
        device_id = meta.get("device_id", "900")
        device_name = meta.get("device_name", "{device-name}")

        # Check if all programs come from a single source variant
        source_variants = set()
        for s in sources:
            src = s.get("from", "")
            if "/" in src:
                source_variants.add(src)

        # Single-variant optimization: bypass PFG, use PFU-style binary copy
        if len(source_variants) == 1:
            variant_key = list(source_variants)[0]
            parts = variant_key.split("/", 1)
            if len(parts) == 2:
                cat_key, var_id = parts
                folder_name = self._cat_folder(cat_key)
                cat_dir = self.cfg.upload_root / folder_name
                src_file = next(cat_dir.rglob(f"{var_id}.panx"), None) or next(cat_dir.rglob(f"{var_id}.pan"), None)

                if src_file:
                    try:
                        from app.pan_binary import PanWriter
                        writer = PanWriter.from_panx(src_file) if str(src_file).endswith('.panx') else PanWriter.from_file(src_file)

                        # Set device ID
                        writer.set_device_id(int(device_id))

                        # Detect source device name for renaming
                        from app.pan_binary import PanBinary
                        parser = PanBinary(bytes(writer.data))
                        prefixes = {}
                        for obj in parser.objects:
                            name = obj['name']
                            if '-' in name:
                                prefix = name.split('-')[0].strip()
                                if prefix and len(prefix) > 1:
                                    prefixes[prefix] = prefixes.get(prefix, 0) + 1
                        source_name = max(prefixes, key=prefixes.get) if prefixes else ""

                        # Rename if device_name is specified and not template mode
                        if device_name and device_name != "{device-name}" and source_name:
                            if len(device_name) == len(source_name):
                                writer.rename_device(source_name, device_name)

                        # Save
                        output_dir = self.cfg.library_root / "COMPOSED" / "_output"
                        output_dir.mkdir(parents=True, exist_ok=True)
                        comp_id = composition.get("id", "composed")
                        final_pan = output_dir / f"{comp_id}.pan"
                        writer.save(final_pan)

                        # Generate companion values document
                        values_doc = output_dir / f"{comp_id}_values.txt"
                        self._generate_values_document(composition, values_doc)

                        logger.info(
                            f"Single-variant optimization: bypassed PFG, "
                            f"binary copy from {src_file.name} -> {final_pan.name} "
                            f"(zero data loss)"
                        )
                        return final_pan

                    except Exception as e:
                        logger.warning(f"Single-variant binary copy failed, falling back to PFG: {e}")

        # Standard multi-variant path: PFG + binary post-process
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from generator import generate_xml

        meta = composition.get("meta", {})
        device_id = meta.get("device_id", "900")
        device_name = meta.get("device_name", "{device-name}")
        comp_id = composition.get("id", "composed")

        output_dir = self.cfg.library_root / "COMPOSED" / "_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        work_dir = Path(f"/tmp/compose_{comp_id}_{int(time.time())}")
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: Place GRP JSON files for SYSTEMGROUP support
            # PFG needs these files to exist at the jsonpath when processing SYSTEMGROUP
            grp_files = composition.get("grp_files", {})
            grp_dir = work_dir / "grp"
            grp_dir.mkdir(parents=True, exist_ok=True)
            grp_wine_paths = {}  # "1000GRP1" -> "Z:\\tmp\\...\\grp\\1000GRP1.json"

            for grp_name, grp_data in grp_files.items():
                grp_path = grp_dir / f"{grp_name}.json"
                # Update device ID in GRP JSON point references
                grp_text = json.dumps(grp_data, indent=2)
                if device_name == "{device-name}":
                    # Template mode: set BACnet_device to 0 (self-reference)
                    grp_text = re.sub(
                        r'"BACnet_device"\s*:\s*\d+',
                        '"BACnet_device": 0',
                        grp_text
                    )
                elif device_id:
                    # Named device: update to actual device ID
                    grp_text = re.sub(
                        r'"BACnet_device"\s*:\s*\d+',
                        f'"BACnet_device": {device_id}',
                        grp_text
                    )
                grp_path.write_text(grp_text)
                from app.extractor import to_wine_path
                grp_wine_paths[grp_name] = to_wine_path(grp_path)
                logger.info(f"Placed GRP JSON: {grp_name} -> {grp_wine_paths[grp_name]}")

            # Update SYSTEMGROUP jsonpath to point to our GRP files
            for sg in composition.get("objects", {}).get("SYSTEMGROUP", []):
                old_path = sg.get("jsonpath", "")
                # Extract GRP filename from old path (e.g., "1000GRP1" from "Z:\tmp\...\1000GRP1.json")
                import re as _re
                m = _re.search(r'(\d+GRP\d+)', old_path)
                if m and m.group(1) in grp_wine_paths:
                    sg["jsonpath"] = grp_wine_paths[m.group(1)]

            # Generate changes XML with all point names using {device-name} template
            # AY (ARRAY) references in program code are REM'd so PFG can compile
            xml_content = generate_xml(composition, device_id=device_id,
                                       device_name=device_name, pfg_safe=True)
            changes_xml = work_dir / "changes.xml"
            changes_xml.write_text(xml_content)
            logger.info(f"Generated changes XML: {len(xml_content)} chars")

            # Step 2: Get blank .pan
            blanks_dir = Path("/srv/dfa/shared/files/vendors/reliable/blanks")
            if not blank_model:
                # Try to find from HardPointConfig
                hpc = meta.get("HardPointConfig", "")
                # Match blanks by HardPointConfig suffix
                for d in blanks_dir.iterdir():
                    if d.is_dir() and hpc and hpc in d.name:
                        blank_model = d.name
                        break
                if not blank_model:
                    # Default to first available
                    available = self.list_blank_panels()
                    if not available:
                        raise ValueError("No blank controller templates found")
                    blank_model = available[0]["model"]
                    logger.warning(f"No blank_model specified, using default: {blank_model}")

            blank_panx = blanks_dir / blank_model
            panx_files = list(blank_panx.glob("*.panx"))
            if not panx_files:
                raise ValueError(f"No .panx found in blanks/{blank_model}")

            input_pan = self._extract_blank_pan(panx_files[0], work_dir)
            logger.info(f"Using blank template: {blank_model} -> {input_pan.name}")

            # Step 3: Run PFG
            output_pan = work_dir / f"{comp_id}.pan"
            self._run_pfg_generate(input_pan, changes_xml, output_pan,
                                   work_dir, device_id, device_name)

            # Copy to output dir
            final_pan = output_dir / f"{comp_id}.pan"
            shutil.copy2(output_pan, final_pan)
            logger.info(f"Generated .pan: {final_pan}")

            # Step 4: Binary post-processing — restore data PFG XML roundtrip loses
            # PFG generates from XML which drops: loop bindings, array data,
            # trend multi-refs, some schedule details. If we have source .pan
            # binaries, patch the missing data back in.
            try:
                self._binary_post_process(final_pan, composition)
            except Exception as e:
                logger.warning(f"Binary post-processing failed (non-fatal): {e}")

            # Generate companion values document
            values_doc = output_dir / f"{comp_id}_values.txt"
            self._generate_values_document(composition, values_doc)

            return final_pan

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def generate_panx(self, composition: dict, blank_model: str = None) -> Path:
        """Generate a .panx file from a composed controller.

        Pipeline:
          1. Generate .pan via generate_pan()
          2. Build meta.json with GroupAssets, HardPointConfig, Features
          3. Copy ALL graphics from source variant asset folders
          4. Package .pan + meta.json + graphics into .panx (zip)

        Returns path to generated .panx file.
        """
        import shutil
        import time
        import zipfile

        meta = composition.get("meta", {})
        device_id = meta.get("device_id", "900")
        comp_id = composition.get("id", "composed")

        output_dir = self.cfg.library_root / "COMPOSED" / "_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        work_dir = Path(f"/tmp/panx_{comp_id}_{int(time.time())}")
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: Generate .pan
            pan_path = self.generate_pan(composition, blank_model)

            # Step 2: Build meta.json
            # Match RC Studio's exact field order: Features, Device, Model, Database, HardPointConfig, GroupAssets
            features = []
            if meta.get("HardPointConfig"):
                features.append("hardpoint_config")
            if meta.get("GroupAssets"):
                features.append("group_assets")

            panx_meta = {}
            if features:
                panx_meta["Features"] = features
            panx_meta["Device"] = int(device_id)
            if meta.get("Model"):
                panx_meta["Model"] = meta["Model"]
            panx_meta["Database"] = f"{device_id}.pan"
            if meta.get("HardPointConfig"):
                panx_meta["HardPointConfig"] = meta["HardPointConfig"]
            if meta.get("GroupAssets"):
                # Deduplicate GroupAssets by Asset path (normalize slashes for comparison)
                seen_assets = set()
                deduped = []
                for ga in meta["GroupAssets"]:
                    # Normalize backslashes to forward slashes
                    ga_norm = dict(ga)
                    if "Asset" in ga_norm:
                        ga_norm["Asset"] = ga_norm["Asset"].replace("\\", "/")
                    if "JobPath" in ga_norm:
                        ga_norm["JobPath"] = ga_norm["JobPath"].replace("\\", "/")
                    key = ga_norm.get("Asset", "")
                    if key not in seen_assets:
                        seen_assets.add(key)
                        deduped.append(ga_norm)
                panx_meta["GroupAssets"] = deduped
            panx_meta["ViewAssets"] = meta.get("ViewAssets", [])

            meta_json = work_dir / "meta.json"
            meta_json.write_text(json.dumps(panx_meta, indent=2))

            # Step 3: Copy graphics from source variant asset folders
            # AND build the Animation subdirectory structure from GroupAssets
            ga_dir = work_dir / "group_assets"
            ga_dir.mkdir(parents=True, exist_ok=True)
            graphics_dir = ga_dir / "pic"
            graphics_dir.mkdir(parents=True, exist_ok=True)

            # Build a set of all source variant asset dirs
            graphics_sources = meta.get("graphics_sources", [])
            seen_variants = set()
            asset_dirs = []
            for gs in graphics_sources:
                vkey = f"{gs['from_category']}/{gs['from_variant']}"
                if vkey not in seen_variants:
                    seen_variants.add(vkey)
                    d = self.cfg.assets_root / gs["from_category"] / gs["from_variant"]
                    if d.exists():
                        asset_dirs.append(d)

            # Copy ALL files from asset dirs (flat + subdirectories) into group_assets/pic/
            # Also search the shared asset library as a fallback
            copied_paths = set()
            shared_dir = self.cfg.assets_root / "_shared"
            all_asset_dirs = asset_dirs + ([shared_dir] if shared_dir.exists() else [])

            for asset_dir in all_asset_dirs:
                for root, dirs, files in os.walk(asset_dir):
                    for fname in files:
                        src = Path(root) / fname
                        rel = src.relative_to(asset_dir)
                        dest = graphics_dir / rel
                        if str(rel) not in copied_paths:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, dest)
                            copied_paths.add(str(rel))

            # Step 4: Generate companion values document
            values_doc = work_dir / f"{comp_id}_values.txt"
            self._generate_values_document(composition, values_doc)
            # Also save a copy alongside the .panx
            values_output = output_dir / f"{comp_id}_values.txt"
            import shutil as _sh
            _sh.copy2(values_doc, values_output)

            # Step 5: Package into .panx
            panx_path = output_dir / f"{comp_id}.panx"
            with zipfile.ZipFile(panx_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Add .pan file
                zf.write(pan_path, f"{device_id}.pan")
                # Add meta.json
                zf.write(meta_json, "meta.json")
                # Add values reference document
                zf.write(values_doc, f"{comp_id}_values.txt")
                # Add all graphics with proper paths for GroupAssets
                for root_path, dirs, files in os.walk(work_dir / "group_assets"):
                    for fname in files:
                        full = Path(root_path) / fname
                        arc_name = str(full.relative_to(work_dir))
                        zf.write(full, arc_name)

            logger.info(f"Generated .panx: {panx_path} ({panx_path.stat().st_size} bytes)")
            return panx_path

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
            # Clean up the intermediate .pan from _output
            intermediate_pan = output_dir / f"{comp_id}.pan"
            if intermediate_pan.exists():
                intermediate_pan.unlink()
