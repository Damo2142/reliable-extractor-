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

                    index.append({
                        "source_category": category,
                        "source_variant": variant_id,
                        "source_description": variant_desc,
                        "program_instance": prog.get("instance", ""),
                        "program_name": prog.get("name", ""),
                        "program_description": prog.get("description", ""),
                        "code_preview": code[:200],
                        "code_lines": len(code.split("\n")),
                        "dependencies": dep_summary,
                        "dependency_details": dep_details,
                        "network_refs": net_refs,
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

        # Load overrides from master_descriptions.json (non-VAV types keep manual descriptions)
        override_path = Path("/srv/dfa/shared/files/vendors/reliable/master_descriptions.json")
        if override_path.exists():
            try:
                overrides = json.loads(override_path.read_text())
                # For non-VAV, prefer manual overrides if they exist
                for k, v in overrides.items():
                    if k not in descs or not k.startswith("VAV"):
                        descs[k] = v
            except Exception:
                pass

        return descs

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
                device_id: str = "900") -> dict:
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
        all_trends = []
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
                            # Auto-create placeholder with type-specific defaults
                            # Defaults based on BACnet conventions and RC library norms
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
                            pt_obj = {
                                "type": ptype,
                                "instance": str(inst),
                                "name": f"{{device-name}}-{mnemonic}",
                                "description": f"[auto-created: referenced in program from {key}]",
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

            # Pull ALL trends from source
            for trend in objects.get("TREND", []):
                trend_copy = dict(trend)
                trend_copy["_source"] = key
                all_trends.append(trend_copy)

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
                    all_meta.setdefault("GroupAssets", []).extend(src_meta["GroupAssets"])
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
        for trend in all_trends:
            source = trend.get("_source", "")
            old_refs = trend.get("references", [])
            new_refs = []
            has_valid_ref = False

            for ref in old_refs:
                m = re.match(r'\d+(AI|AO|AV|BI|BO|BV|MO|MV|LOOP|SCHED)(\d+)', ref)
                if m:
                    ref_type = m.group(1)
                    ref_inst = int(m.group(2))
                    new_inst = trend_remap.get((source, ref_type, ref_inst))
                    if new_inst is not None:
                        new_refs.append(f"{device_id}{ref_type}{new_inst}")
                        has_valid_ref = True

            if has_valid_ref:
                trend_name = trend.get("name", "")
                if trend_name not in seen_trend_names:
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

        composed_meta = dict(all_meta)
        composed_meta.update({
            "composed": True,
            "sources": sources,
            "device_id": device_id,
            "device_name": device_name,
            "graphics_sources": all_graphics_sources,
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
        }

        loops = objects.get("LOOP", [])
        if loops:
            lines.append(f"--- Loops (PID Settings) ---")
            lines.append(f"  ** IMPORTANT: Input and Setpoint must be configured in RC Studio **")
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
                # Try to suggest input/setpoint from loop name
                loop_mnem = name.split("-", 1)[1] if "-" in name else name
                prefix = name.rsplit("-" + loop_mnem.split("-")[0], 1)[0] if "-" in name else device_name
                binding = _loop_bindings.get(loop_mnem)
                if binding:
                    # Find matching points
                    inp_name = f"{prefix}-{binding['input']}"
                    sp_name = f"{prefix}-{binding['setpoint']}"
                    inp_ref = all_points.get(inp_name, f"? ({binding['input']})")
                    sp_ref = all_points.get(sp_name, f"? ({binding['setpoint']})")
                    lines.append(f"         -> Input: {inp_ref} ({inp_name})")
                    lines.append(f"         -> Setpoint: {sp_ref} ({sp_name})")
                else:
                    lines.append(f"         -> Input/Setpoint: must be configured manually")
            lines.append("")

        # ── Programs ──
        progs = objects.get("PROGRAM", [])
        if progs:
            lines.append(f"--- Programs ---")
            lines.append(f"{'Inst':>5}  {'Name':<35}  {'Enabled':>8}")
            lines.append(f"{'-'*5}  {'-'*35}  {'-'*8}")
            for p in sorted(progs, key=lambda x: int(x.get("instance", 0))):
                name = p.get("name", "").replace("{device-name}", device_name)
                pv = p.get("present_value", "1")
                enabled = "Yes" if str(pv) == "1" else "No"
                lines.append(f"{p.get('instance',''):>5}  {name:<35}  {enabled:>8}")
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
                refs = ", ".join(r for r in t.get("references", []) if r)
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

        # ── SystemGroups ──
        sgroups = objects.get("SYSTEMGROUP", [])
        if sgroups:
            lines.append(f"--- System Groups ---")
            for sg in sorted(sgroups, key=lambda x: int(x.get("instance", 0))):
                name = sg.get("name", "").replace("{device-name}", device_name)
                lines.append(f"  {sg.get('instance',''):>3}  {name}  graphic={sg.get('groupgraphic','')}  json={sg.get('jsonpath','')}")
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
        with open(PFG_LOCK_FILE, 'r') as lock_fd:
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

        Pipeline:
          1. Generate changes XML from composition
          2. Extract blank .pan from the specified controller model template
          3. Run PFG: blank .pan + changes XML -> output .pan

        Args:
            composition: composed controller JSON
            blank_model: controller model name (e.g. "RC-FLEXair-34-A-F")
                         Must match a folder in blanks/

        Returns path to generated .pan in _output dir.
        """
        import shutil
        import time

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
                if device_id:
                    # GRP JSONs have BACnet_device fields — update them
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

            # Step 1b: Generate changes XML
            # pfg_safe=True excludes DEVICE and TREND (which still crash PFG)
            # but SYSTEMGROUP and SMARTSENSOR are now always included
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

            # Step 3: Run PFG (safe objects only — points, programs, loops, schedules, calendars)
            output_pan = work_dir / f"{comp_id}.pan"
            self._run_pfg_generate(input_pan, changes_xml, output_pan,
                                   work_dir, device_id, device_name)

            # NOTE: TRENDs, SMARTSENSOR, SYSTEMGROUP excluded from PFG (crashes).
            # These are listed in the companion values document for reference.

            # Copy to output dir
            final_pan = output_dir / f"{comp_id}.pan"
            shutil.copy2(output_pan, final_pan)
            logger.info(f"Generated .pan: {final_pan}")

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
            panx_meta = {
                "Device": int(device_id),
                "Database": f"{device_id}.pan",
            }
            features = []
            if meta.get("HardPointConfig"):
                panx_meta["HardPointConfig"] = meta["HardPointConfig"]
                features.append("hardpoint_config")
            if meta.get("GroupAssets"):
                # Deduplicate GroupAssets by Asset path
                seen_assets = set()
                deduped = []
                for ga in meta["GroupAssets"]:
                    key = ga.get("Asset", "")
                    if key not in seen_assets:
                        seen_assets.add(key)
                        deduped.append(ga)
                panx_meta["GroupAssets"] = deduped
                features.append("group_assets")
            panx_meta["ViewAssets"] = meta.get("ViewAssets", [])
            if features:
                panx_meta["Features"] = features

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
            copied_paths = set()
            for asset_dir in asset_dirs:
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
