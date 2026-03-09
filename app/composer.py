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

    def get_variant_objects(self, category: str, variant_id: str) -> Optional[dict]:
        """Load a variant's full objects dict from the library."""
        lib_path = self.cfg.library_root / category / f"{variant_id}.json"
        if not lib_path.exists():
            return None
        try:
            data = json.loads(lib_path.read_text())
            return data.get("objects", {})
        except Exception:
            return None

    def compose(self, selections: list, device_name: str = "{device-name}",
                device_id: str = "900") -> dict:
        """Compose a new controller from selected programs across variants.

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
        # Load all source variants we need
        source_cache = {}
        for sel in selections:
            key = f"{sel['category']}/{sel['variant_id']}"
            if key not in source_cache:
                objects = self.get_variant_objects(sel["category"], sel["variant_id"])
                if objects is None:
                    raise ValueError(f"Variant not found: {key}")
                source_cache[key] = objects

        # Collect all programs and their dependencies
        collected = {
            "programs": [],
            "points": {},     # type -> {instance -> point_obj}
            "loops": {},      # instance -> loop_obj
            "trends": [],
            "schedules": {},  # instance -> schedule_obj
            "calendars": {},
            "smartsensors": [],
            "systemgroups": [],
            "tables": {},     # instance -> table_obj
            "arrays": {},     # instance -> array_obj
        }

        for sel in selections:
            key = f"{sel['category']}/{sel['variant_id']}"
            objects = source_cache[key]
            prog_inst = str(sel["program_instance"])

            # Find the program
            program = None
            for p in objects.get("PROGRAM", []):
                if str(p.get("instance", "")) == prog_inst:
                    program = dict(p)  # copy
                    program["_source"] = key
                    break

            if program is None:
                raise ValueError(
                    f"Program instance {prog_inst} not found in {key}"
                )

            collected["programs"].append(program)

            # Parse code references to find dependencies
            code = program.get("code", "")
            refs = parse_code_references(code)

            # Collect dependent points
            for ptype in POINT_TYPES:
                if ptype in refs:
                    for inst in refs[ptype]:
                        pt_key = f"{ptype}:{inst}"
                        if pt_key not in collected["points"]:
                            # Find the point in source variant
                            for obj in objects.get(ptype, []):
                                if int(obj.get("instance", 0)) == inst:
                                    collected["points"][pt_key] = dict(obj)
                                    collected["points"][pt_key]["_source"] = key
                                    break
                            else:
                                # Point referenced but not defined - create placeholder
                                collected["points"][pt_key] = {
                                    "type": ptype,
                                    "instance": str(inst),
                                    "name": f"{{device-name}}-{ptype}{inst}",
                                    "description": f"[auto-created: referenced in program from {key}]",
                                    "_source": key,
                                }

            # Collect dependent loops
            if "LOOP" in refs:
                for inst in refs["LOOP"]:
                    loop_key = f"LOOP:{inst}"
                    if loop_key not in collected["loops"]:
                        for obj in objects.get("LOOP", []):
                            if int(obj.get("instance", 0)) == inst:
                                collected["loops"][loop_key] = dict(obj)
                                collected["loops"][loop_key]["_source"] = key
                                break

            # Collect dependent schedules
            if "SCHED" in refs:
                for inst in refs["SCHED"]:
                    sched_key = f"SCHED:{inst}"
                    if sched_key not in collected["schedules"]:
                        for obj in objects.get("SCHEDULE", []):
                            if int(obj.get("instance", 0)) == inst:
                                collected["schedules"][sched_key] = dict(obj)
                                collected["schedules"][sched_key]["_source"] = key
                                break

            # Pull trends that reference any of our collected points
            for trend in objects.get("TREND", []):
                trend_copy = dict(trend)
                trend_copy["_source"] = key
                collected["trends"].append(trend_copy)

        # Now remap instances sequentially to avoid conflicts
        return self._remap_and_assemble(collected, device_name, device_id)

    def _remap_and_assemble(self, collected: dict, device_name: str,
                            device_id: str) -> dict:
        """Remap all instance numbers sequentially and update cross-references."""

        # Build remapping tables
        # Key: (source_key, type, old_instance) -> new_instance
        remap = {}

        # Group points by type
        points_by_type = {}
        for pt_key, pt in collected["points"].items():
            ptype = pt["type"]
            points_by_type.setdefault(ptype, []).append(pt)

        # Assign new sequential instances per type
        for ptype in POINT_TYPES:
            pts = points_by_type.get(ptype, [])
            for i, pt in enumerate(pts, 1):
                source = pt.get("_source", "")
                old_inst = int(pt.get("instance", 0))
                remap[(source, ptype, old_inst)] = i
                pt["instance"] = str(i)

        # Remap loops
        loops = list(collected["loops"].values())
        for i, loop in enumerate(loops, 1):
            source = loop.get("_source", "")
            old_inst = int(loop.get("instance", 0))
            remap[(source, "LOOP", old_inst)] = i
            loop["instance"] = str(i)

        # Remap schedules
        schedules = list(collected["schedules"].values())
        for i, sched in enumerate(schedules, 1):
            source = sched.get("_source", "")
            old_inst = int(sched.get("instance", 0))
            remap[(source, "SCHED", old_inst)] = i
            remap[(source, "SCHEDULE", old_inst)] = i
            sched["instance"] = str(i)

        # Remap programs
        programs = collected["programs"]
        for i, prog in enumerate(programs, 1):
            source = prog.get("_source", "")
            old_inst = int(prog.get("instance", 0))
            remap[(source, "PROGRAM", old_inst)] = i
            prog["instance"] = str(i)

            # Remap point references in program code
            code = prog.get("code", "")
            code = self._remap_code_references(code, source, remap)
            prog["code"] = code

        # Filter trends to only those referencing points we kept
        # and remap their references
        kept_trends = []
        seen_trend_names = set()
        for trend in collected["trends"]:
            source = trend.get("_source", "")
            old_refs = trend.get("references", [])
            new_refs = []
            has_valid_ref = False

            for ref in old_refs:
                # References look like "4194293AV1" - extract type+instance
                m = re.match(r'\d+(AI|AO|AV|BI|BO|BV|MO|MV|LOOP|SCHED)(\d+)', ref)
                if m:
                    ref_type = m.group(1)
                    ref_inst = int(m.group(2))
                    new_inst = remap.get((source, ref_type, ref_inst))
                    if new_inst is not None:
                        new_refs.append(f"{device_id}{ref_type}{new_inst}")
                        has_valid_ref = True
                    else:
                        # Point not in our composition, skip this reference
                        pass

            if has_valid_ref:
                trend_name = trend.get("name", "")
                if trend_name not in seen_trend_names:
                    seen_trend_names.add(trend_name)
                    trend["references"] = new_refs
                    kept_trends.append(trend)

        # Remap trend instances
        for i, trend in enumerate(kept_trends, 1):
            trend["instance"] = str(i)

        # Assemble final library-format JSON
        objects = {
            "DEVICE": [{
                "instance": device_id,
                "name": device_name,
                "description": "",
                "location": "",
            }],
        }

        for ptype in POINT_TYPES:
            pts = points_by_type.get(ptype, [])
            objects[ptype] = [
                {k: v for k, v in pt.items() if not k.startswith("_")}
                for pt in pts
            ]

        objects["PROGRAM"] = [
            {k: v for k, v in p.items() if not k.startswith("_")}
            for p in programs
        ]

        objects["LOOP"] = [
            {k: v for k, v in l.items() if not k.startswith("_")}
            for l in loops
        ]

        objects["TREND"] = [
            {k: v for k, v in t.items() if not k.startswith("_")}
            for t in kept_trends
        ]

        objects["SCHEDULE"] = [
            {k: v for k, v in s.items() if not k.startswith("_")}
            for s in schedules
        ]

        # Empty containers for types we don't compose yet
        for obj_type in ["CALENDAR", "SMARTSENSOR", "SYSTEMGROUP", "TABLE", "ARRAY"]:
            objects[obj_type] = []

        # Build counts
        counts = {k: len(v) for k, v in objects.items() if isinstance(v, list) and v}

        # Build source manifest for traceability
        sources = []
        for sel_prog in programs:
            sources.append({
                "program": sel_prog.get("name", ""),
                "from": sel_prog.get("_source", ""),
            })

        result = {
            "id": "composed",
            "category": "COMPOSED",
            "format": "composed",
            "description": f"Custom composed controller",
            "meta": {
                "composed": True,
                "sources": sources,
                "device_id": device_id,
                "device_name": device_name,
            },
            "graphics": [],
            "objects": objects,
            "bas_files": {},
            "counts": counts,
        }

        return result

    def _remap_code_references(self, code: str, source: str,
                               remap: dict) -> str:
        """Remap point references in Control-BASIC code.

        Replaces AV7 -> AV3 (etc.) based on the remap table.
        Must be careful not to remap network references like 1001BI1.
        """

        def replace_ref(match):
            # Check if preceded by a digit (network reference) - don't remap
            start = match.start()
            if start > 0 and code[start - 1].isdigit():
                return match.group(0)

            ptype = match.group(1)
            old_inst = int(match.group(2))
            new_inst = remap.get((source, ptype, old_inst))
            if new_inst is not None:
                return f"{ptype}{new_inst}"
            return match.group(0)  # No mapping, keep original

        return POINT_REF_PATTERN.sub(replace_ref, code)

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
