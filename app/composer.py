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
            # Step 1: Generate changes XML
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
                panx_meta["GroupAssets"] = meta["GroupAssets"]
                features.append("group_assets")
            if features:
                panx_meta["Features"] = features

            meta_json = work_dir / "meta.json"
            meta_json.write_text(json.dumps(panx_meta, indent=2))

            # Step 3: Copy ALL graphics from source variant asset folders
            # Each source variant has an asset dir with all its graphics
            graphics_dir = work_dir / "group_assets" / "pic"
            graphics_dir.mkdir(parents=True, exist_ok=True)

            graphics_sources = meta.get("graphics_sources", [])
            copied_files = set()
            for gs in graphics_sources:
                src_file = (self.cfg.assets_root / gs["from_category"]
                            / gs["from_variant"] / gs["file"])
                if src_file.exists() and gs["file"] not in copied_files:
                    dest = graphics_dir / gs["file"]
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest)
                    copied_files.add(gs["file"])

            # Also copy ALL files from each source variant's asset folder
            seen_variants = set()
            for gs in graphics_sources:
                vkey = f"{gs['from_category']}/{gs['from_variant']}"
                if vkey in seen_variants:
                    continue
                seen_variants.add(vkey)
                asset_dir = (self.cfg.assets_root / gs["from_category"]
                             / gs["from_variant"])
                if asset_dir.exists():
                    for f in asset_dir.iterdir():
                        if f.is_file() and f.name not in copied_files:
                            dest = graphics_dir / f.name
                            shutil.copy2(f, dest)
                            copied_files.add(f.name)

            # Step 4: Package into .panx
            panx_path = output_dir / f"{comp_id}.panx"
            with zipfile.ZipFile(panx_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Add .pan file
                zf.write(pan_path, f"{device_id}.pan")
                # Add meta.json
                zf.write(meta_json, "meta.json")
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
