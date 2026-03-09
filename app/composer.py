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

    def get_variant_data(self, category: str, variant_id: str) -> Optional[dict]:
        """Load a variant's full library record (objects, meta, graphics, etc.)."""
        lib_path = self.cfg.library_root / category / f"{variant_id}.json"
        if not lib_path.exists():
            return None
        try:
            return json.loads(lib_path.read_text())
        except Exception:
            return None

    def compose(self, selections: list, device_name: str = "{device-name}",
                device_id: str = "900") -> dict:
        """Compose a new controller from selected programs across variants.

        Pulls programs + ALL their dependencies including points, loops,
        schedules, calendars, trends, smartsensors, systemgroups, tables,
        arrays, graphics, and meta.json data.

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
        # Load all source variants (full records, not just objects)
        source_cache = {}  # key -> full variant data
        for sel in selections:
            key = f"{sel['category']}/{sel['variant_id']}"
            if key not in source_cache:
                data = self.get_variant_data(sel["category"], sel["variant_id"])
                if data is None:
                    raise ValueError(f"Variant not found: {key}")
                source_cache[key] = data

        # Collect all programs and their dependencies
        collected = {
            "programs": [],
            "points": {},         # "TYPE:inst" -> point_obj
            "loops": {},          # "LOOP:inst" -> loop_obj
            "trends": [],
            "schedules": {},      # "SCHED:inst" -> schedule_obj
            "calendars": {},      # "CAL:inst" -> calendar_obj
            "smartsensors": {},   # "SS:inst" -> smartsensor_obj
            "systemgroups": {},   # "SG:inst" -> systemgroup_obj
            "tables": {},         # "TBL:inst" -> table_obj
            "arrays": {},         # "ARR:inst" -> array_obj
        }

        # Merge graphics and meta from all source variants
        all_graphics = []
        all_meta = {}
        all_graphics_sources = []  # track which variant each graphic came from

        for sel in selections:
            key = f"{sel['category']}/{sel['variant_id']}"
            data = source_cache[key]
            objects = data.get("objects", {})
            prog_inst = str(sel["program_instance"])

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
                            for obj in objects.get(ptype, []):
                                if int(obj.get("instance", 0)) == inst:
                                    collected["points"][pt_key] = dict(obj)
                                    collected["points"][pt_key]["_source"] = key
                                    break
                            else:
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

            # Pull ALL trends from source (filter to kept points later)
            for trend in objects.get("TREND", []):
                trend_copy = dict(trend)
                trend_copy["_source"] = key
                collected["trends"].append(trend_copy)

            # Pull ALL calendars, smartsensors, systemgroups, tables, arrays
            # from each source variant (these are controller-level objects)
            for cal in objects.get("CALENDAR", []):
                cal_key = f"CAL:{cal.get('instance', '')}"
                if cal_key not in collected["calendars"]:
                    collected["calendars"][cal_key] = dict(cal)
                    collected["calendars"][cal_key]["_source"] = key

            for ss in objects.get("SMARTSENSOR", []):
                ss_key = f"SS:{ss.get('instance', '')}"
                if ss_key not in collected["smartsensors"]:
                    collected["smartsensors"][ss_key] = dict(ss)
                    collected["smartsensors"][ss_key]["_source"] = key

            for sg in objects.get("SYSTEMGROUP", []):
                sg_key = f"SG:{sg.get('instance', '')}"
                if sg_key not in collected["systemgroups"]:
                    collected["systemgroups"][sg_key] = dict(sg)
                    collected["systemgroups"][sg_key]["_source"] = key

            for tbl in objects.get("TABLE", []):
                tbl_key = f"TBL:{tbl.get('instance', '')}"
                if tbl_key not in collected["tables"]:
                    collected["tables"][tbl_key] = dict(tbl)
                    collected["tables"][tbl_key]["_source"] = key

            for arr in objects.get("ARRAY", []):
                arr_key = f"ARR:{arr.get('instance', '')}"
                if arr_key not in collected["arrays"]:
                    collected["arrays"][arr_key] = dict(arr)
                    collected["arrays"][arr_key]["_source"] = key

            # Collect graphics from source variant
            for gfx in data.get("graphics", []):
                if gfx not in all_graphics:
                    all_graphics.append(gfx)
                    all_graphics_sources.append({
                        "file": gfx,
                        "from_category": sel["category"],
                        "from_variant": sel["variant_id"],
                    })

            # Merge meta from source variant
            src_meta = data.get("meta", {})
            if src_meta and key not in [s.get("_merged") for s in [all_meta]]:
                # Merge GroupAssets, HardPointConfig, etc.
                if "GroupAssets" in src_meta:
                    all_meta.setdefault("GroupAssets", []).extend(src_meta["GroupAssets"])
                if "HardPointConfig" in src_meta and "HardPointConfig" not in all_meta:
                    all_meta["HardPointConfig"] = src_meta["HardPointConfig"]
                if "Features" in src_meta:
                    existing = set(all_meta.get("Features", []))
                    for f in src_meta["Features"]:
                        if f not in existing:
                            all_meta.setdefault("Features", []).append(f)
                            existing.add(f)

        # Now remap instances sequentially to avoid conflicts
        return self._remap_and_assemble(
            collected, device_name, device_id,
            all_graphics, all_graphics_sources, all_meta
        )

    def _remap_and_assemble(self, collected: dict, device_name: str,
                            device_id: str, graphics: list,
                            graphics_sources: list, meta: dict) -> dict:
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

        # Remap calendars
        calendars = list(collected["calendars"].values())
        for i, cal in enumerate(calendars, 1):
            cal["instance"] = str(i)

        # Remap smartsensors
        smartsensors = list(collected["smartsensors"].values())
        for i, ss in enumerate(smartsensors, 1):
            ss["instance"] = str(i)

        # Remap systemgroups
        systemgroups = list(collected["systemgroups"].values())
        for i, sg in enumerate(systemgroups, 1):
            sg["instance"] = str(i)

        # Remap tables
        tables = list(collected["tables"].values())
        for i, tbl in enumerate(tables, 1):
            tbl["instance"] = str(i)

        # Remap arrays
        arrays = list(collected["arrays"].values())
        for i, arr in enumerate(arrays, 1):
            arr["instance"] = str(i)

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
                m = re.match(r'\d+(AI|AO|AV|BI|BO|BV|MO|MV|LOOP|SCHED)(\d+)', ref)
                if m:
                    ref_type = m.group(1)
                    ref_inst = int(m.group(2))
                    new_inst = remap.get((source, ref_type, ref_inst))
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

        # Strip internal _source keys from all objects
        def clean(obj):
            return {k: v for k, v in obj.items() if not k.startswith("_")}

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
            objects[ptype] = [clean(pt) for pt in points_by_type.get(ptype, [])]

        objects["PROGRAM"] = [clean(p) for p in programs]
        objects["LOOP"] = [clean(l) for l in loops]
        objects["TREND"] = [clean(t) for t in kept_trends]
        objects["SCHEDULE"] = [clean(s) for s in schedules]
        objects["CALENDAR"] = [clean(c) for c in calendars]
        objects["SMARTSENSOR"] = [clean(s) for s in smartsensors]
        objects["SYSTEMGROUP"] = [clean(s) for s in systemgroups]
        objects["TABLE"] = [clean(t) for t in tables]
        objects["ARRAY"] = [clean(a) for a in arrays]

        counts = {k: len(v) for k, v in objects.items() if isinstance(v, list) and v}

        # Build source manifest for traceability
        sources = []
        for sel_prog in programs:
            sources.append({
                "program": sel_prog.get("name", ""),
                "from": sel_prog.get("_source", ""),
            })

        # Merge meta with device info
        composed_meta = dict(meta)
        composed_meta.update({
            "composed": True,
            "sources": sources,
            "device_id": device_id,
            "device_name": device_name,
            "graphics_sources": graphics_sources,
        })

        result = {
            "id": "composed",
            "category": "COMPOSED",
            "format": "composed",
            "description": "Custom composed controller",
            "meta": composed_meta,
            "graphics": graphics,
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

    def generate_panx(self, composition: dict, output_dir: Path = None) -> Path:
        """Generate a .panx file from a composed controller.

        Pipeline:
          1. Generate changes XML from composition
          2. Run PFG with blank .pan + changes XML to produce a .pan
          3. Build meta.json
          4. Copy graphics from source variants
          5. Package everything into a .panx (zip)

        Returns path to the generated .panx file.
        """
        import fcntl
        import shutil
        import subprocess
        import time
        import zipfile
        from app.extractor import PFG_WORK_DIR, PFG_LOCK_FILE, to_wine_path

        # Import generator
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from generator import generate_xml

        meta = composition.get("meta", {})
        device_id = meta.get("device_id", "900")
        device_name = meta.get("device_name", "{device-name}")
        comp_id = composition.get("id", "composed")

        if output_dir is None:
            output_dir = self.cfg.library_root / "COMPOSED" / "_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        work_dir = Path(f"/tmp/compose_{comp_id}_{int(time.time())}")
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: Generate changes XML
            xml_content = generate_xml(composition, device_id=device_id,
                                       device_name=device_name)
            changes_xml = work_dir / "changes.xml"
            changes_xml.write_text(xml_content)
            logger.info(f"Generated changes XML: {len(xml_content)} chars")

            # Step 2: Run PFG to create .pan from blank + changes
            pan_output = work_dir / f"{comp_id}.pan"

            PFG_LOCK_FILE.touch(exist_ok=True)
            with open(PFG_LOCK_FILE, 'r') as lock_fd:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                try:
                    pfg_dir = Path(PFG_WORK_DIR)

                    # Snapshot existing files
                    existing_pans = set(pfg_dir.glob("*.pan"))
                    existing_xmls = set(pfg_dir.glob("*.xml"))

                    cmd = [
                        self.cfg.wine_bin,
                        str(self.cfg.pfg_exe),
                        "-c", to_wine_path(changes_xml),
                        "-o", to_wine_path(pan_output),
                        "-f", to_wine_path(work_dir / "pfg.log"),
                    ]

                    logger.info(f"PFG generate: {' '.join(cmd)}")
                    env = {**os.environ, "WINEDEBUG": "-all"}

                    proc = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        env=env, cwd=PFG_WORK_DIR,
                    )

                    deadline = time.time() + self.cfg.pfg_timeout
                    while time.time() < deadline:
                        time.sleep(0.5)
                        # Check if output .pan was created
                        if pan_output.exists() and pan_output.stat().st_size > 0:
                            time.sleep(1.0)
                            try:
                                proc.kill()
                            except Exception:
                                pass
                            break
                        # Also check PFG's CWD for new .pan files
                        new_pans = set(pfg_dir.glob("*.pan")) - existing_pans
                        if new_pans:
                            time.sleep(1.0)
                            try:
                                proc.kill()
                            except Exception:
                                pass
                            # Move new .pan to our work dir
                            for f in new_pans:
                                if not pan_output.exists():
                                    shutil.move(str(f), str(pan_output))
                                else:
                                    f.unlink()
                            break
                        if proc.poll() is not None:
                            break

                    if proc.poll() is None:
                        try:
                            proc.kill()
                            proc.wait(timeout=5)
                        except Exception:
                            pass

                    # Clean up any stray files PFG left
                    for f in set(pfg_dir.glob("*.xml")) - existing_xmls:
                        f.unlink(missing_ok=True)

                finally:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)

            if not pan_output.exists():
                # If PFG didn't create the .pan, check log
                log_content = ""
                log_file = work_dir / "pfg.log"
                if log_file.exists():
                    log_content = log_file.read_text(errors="replace")
                raise RuntimeError(
                    f"PFG did not generate .pan file. Log: {log_content[:500]}"
                )

            # Step 3: Build meta.json for .panx package
            panx_meta = {
                "Device": int(device_id),
                "Database": f"{device_id}.pan",
            }
            if meta.get("HardPointConfig"):
                panx_meta["HardPointConfig"] = meta["HardPointConfig"]
                panx_meta["Features"] = ["hardpoint_config"]
            if meta.get("GroupAssets"):
                panx_meta["GroupAssets"] = meta["GroupAssets"]
                panx_meta.setdefault("Features", [])
                if "group_assets" not in panx_meta["Features"]:
                    panx_meta["Features"].append("group_assets")

            meta_json = work_dir / "meta.json"
            meta_json.write_text(json.dumps(panx_meta, indent=2))

            # Step 4: Copy graphics from source variants
            graphics_sources = meta.get("graphics_sources", [])
            for gs in graphics_sources:
                src_file = (self.cfg.assets_root / gs["from_category"]
                            / gs["from_variant"] / gs["file"])
                if src_file.exists():
                    dest = work_dir / gs["file"]
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest)

            # Step 5: Package into .panx (zip)
            panx_path = output_dir / f"{comp_id}.panx"
            with zipfile.ZipFile(panx_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Add .pan file
                zf.write(pan_output, f"{device_id}.pan")
                # Add meta.json
                zf.write(meta_json, "meta.json")
                # Add changes XML for reference
                zf.write(changes_xml, "changes.xml")
                # Add graphics
                for gs in graphics_sources:
                    gfx_path = work_dir / gs["file"]
                    if gfx_path.exists():
                        zf.write(gfx_path, gs["file"])

            logger.info(f"Generated .panx: {panx_path} ({panx_path.stat().st_size} bytes)")
            return panx_path

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
