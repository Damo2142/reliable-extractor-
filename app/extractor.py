"""
Extraction Engine
Pipeline:
  1. .panx -> rename to .zip -> unzip -> get {deviceid}.pan + meta.json + graphics
  2. Run PFG from /srv/reliable-generator/ with Z:\\ Windows paths
  3. PFG writes {deviceid}.xml in PFG_WORK_DIR (NOT the temp dir) - parse that XML
  4. Store everything as JSON in library folder

Key Wine behavior (proven in testing March 4, 2026):
  - Must run from /srv/reliable-generator/ with no WINEPREFIX
  - PFG writes sidecar XML to its OWN CWD (/srv/reliable-generator/), NOT output dir
  - XML filename = BACnet device instance ID from inside the .pan (e.g., 5001.xml)
  - GRP JSONs also written to CWD (e.g., 5001GRP1.json)
  - Wine hangs after PFG completes - use Popen + poll loop + kill
  - Control-BASIC code inside <code> tags contains raw < and > that break XML parsing
"""

import fcntl
import json
import logging
import os
import re
import shutil
import subprocess
import time
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from app.config import Config
from app.xlsx_reader import read_data_xlsx

logger = logging.getLogger(__name__)

PFG_WORK_DIR = "/srv/reliable-generator"
PFG_LOCK_FILE = Path(PFG_WORK_DIR) / ".pfg_lock"


def to_wine_path(p: Path) -> str:
    return "Z:\\" + str(p).replace("/", "\\")


class ExtractionEngine:
    def __init__(self, config: Config):
        self.cfg = config
        self.descriptions = {}
        if self.cfg.master_descriptions.exists():
            try:
                self.descriptions = json.loads(self.cfg.master_descriptions.read_text())
                logger.info(f"Loaded {len(self.descriptions)} master descriptions")
            except Exception as e:
                logger.warning(f"Failed to load master descriptions: {e}")

    def discover_variants(self) -> dict:
        result = {}
        if not self.cfg.upload_root.exists():
            logger.warning(f"Upload root not found: {self.cfg.upload_root}")
            return result

        for folder_name, cat_key in self.cfg.CATEGORIES.items():
            cat_dir = self.cfg.upload_root / folder_name
            if not cat_dir.exists():
                continue

            xlsx_meta = {}
            for xlsx in cat_dir.glob("*_Data.xlsx"):
                xlsx_meta = read_data_xlsx(xlsx)
                break

            variants = []
            seen = set()

            for panx in sorted(cat_dir.rglob("*.panx")):
                vid = panx.stem
                if vid in seen:
                    continue
                seen.add(vid)
                lib_entry = self._library_path(cat_key, vid)
                desc = xlsx_meta.get(vid, {}).get("description", "") or self.descriptions.get(vid, "")
                variants.append({
                    "id": vid,
                    "format": "panx",
                    "source": str(panx.relative_to(self.cfg.upload_root)),
                    "processed": lib_entry.exists(),
                    "description": desc,
                    "tags": xlsx_meta.get(vid, {}).get("tags", []),
                })

            for pan in sorted(cat_dir.rglob("*.pan")):
                vid = pan.stem
                if vid in seen:
                    continue
                seen.add(vid)
                lib_entry = self._library_path(cat_key, vid)
                # Check for .bas files in same directory
                bas_count = len(list(pan.parent.glob("*.bas")))
                desc = xlsx_meta.get(vid, {}).get("description", "") or self.descriptions.get(vid, "")
                variants.append({
                    "id": vid,
                    "format": "pan",
                    "source": str(pan.relative_to(self.cfg.upload_root)),
                    "has_bas": bas_count > 0,
                    "bas_count": bas_count,
                    "processed": lib_entry.exists(),
                    "description": desc,
                    "tags": xlsx_meta.get(vid, {}).get("tags", []),
                })

            if variants:
                result[cat_key] = variants

        return result

    def process_variant(self, category: str, item: dict) -> dict:
        vid = item["id"]
        fmt = item["format"]
        folder_name = self._cat_folder(category)
        cat_dir = self.cfg.upload_root / folder_name

        work_dir = Path(f"/tmp/rc_{vid}_{int(time.time())}")
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            if fmt == "panx":
                panx_path = next(cat_dir.rglob(f"{vid}.panx"), None)
                if not panx_path:
                    raise FileNotFoundError(f"Cannot find {vid}.panx")
                pan_path, meta, graphics = self._unzip_panx(panx_path, work_dir, category, vid)
            else:
                src_pan = next(cat_dir.rglob(f"{vid}.pan"), None)
                if not src_pan:
                    raise FileNotFoundError(f"Cannot find {vid}.pan")
                pan_path = work_dir / f"{vid}.pan"
                shutil.copy2(src_pan, pan_path)
                meta = {}
                graphics = []

            xml_path = self._run_pfg(pan_path, work_dir, vid)
            parsed = self._parse_xml(xml_path)

            # FIX 5: Collect ALL .bas files from the source directory
            bas_files = {}
            if fmt == "pan":
                orig = next(cat_dir.rglob(f"{vid}.pan"), None)
                if orig:
                    parent = orig.parent
                    for bas in sorted(parent.glob("*.bas")):
                        bas_files[bas.stem] = bas.read_text(errors="replace")
            elif fmt == "panx":
                # Some panx extractions may have .bas in the same upload folder
                panx_path = next(cat_dir.rglob(f"{vid}.panx"), None)
                if panx_path:
                    parent = panx_path.parent
                    for bas in sorted(parent.glob("*.bas")):
                        bas_files[bas.stem] = bas.read_text(errors="replace")

            record = {
                "id": vid,
                "category": category,
                "format": fmt,
                "description": item.get("description", "") or self.descriptions.get(vid, ""),
                "meta": meta,
                "graphics": graphics,
                "objects": parsed,
                "bas_files": bas_files,
                "counts": self._count_objects(parsed),
            }

            self._save_library_entry(category, vid, record)
            return record

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def _unzip_panx(self, panx_path: Path, work_dir: Path, category: str, vid: str):
        tmp_zip = work_dir / f"{vid}.zip"
        shutil.copy2(panx_path, tmp_zip)

        try:
            with zipfile.ZipFile(tmp_zip, "r") as z:
                z.extractall(work_dir)
        except zipfile.BadZipFile:
            raise ValueError(f"{panx_path.name} is not a valid ZIP archive")
        finally:
            tmp_zip.unlink(missing_ok=True)

        pan_files = list(work_dir.rglob("*.pan"))
        if not pan_files:
            raise ValueError(f"No .pan found inside {panx_path.name}")
        pan_path = pan_files[0]

        meta = {}
        meta_file = work_dir / "meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
            except Exception:
                pass

        graphics = []
        asset_dir = self.cfg.assets_root / category / vid
        asset_dir.mkdir(parents=True, exist_ok=True)
        for gfx in work_dir.rglob("*"):
            if gfx.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp"}:
                dest = asset_dir / gfx.name
                shutil.copy2(gfx, dest)
                graphics.append(gfx.name)

        return pan_path, meta, graphics

    # FIX 1 + FIX 4: PFG writes XML to its own CWD, with file lock for safety
    def _run_pfg(self, pan_path: Path, work_dir: Path, vid: str) -> Path:
        # Serialize PFG runs to prevent output file collisions
        PFG_LOCK_FILE.touch(exist_ok=True)
        with open(PFG_LOCK_FILE, 'r') as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                return self._run_pfg_inner(pan_path, work_dir, vid)
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)

    def _run_pfg_inner(self, pan_path: Path, work_dir: Path, vid: str) -> Path:
        out_pan = work_dir / f"{vid}_export.pan"
        log_file = work_dir / f"{vid}.log"

        pfg_dir = Path(PFG_WORK_DIR)

        # FIX 1: Snapshot existing XMLs and JSONs in PFG dir BEFORE running
        existing_xmls = set(pfg_dir.glob("*.xml"))
        existing_jsons = set(pfg_dir.glob("*.json"))

        cmd = [
            "wine",
            "pfg/PanelFileGenerator.exe",
            "-i", to_wine_path(pan_path),
            "-o", to_wine_path(out_pan),
            "-c", to_wine_path(self.cfg.blank_xml),
            "-f", to_wine_path(log_file),
        ]

        logger.info(f"PFG: {' '.join(cmd)}")

        env = {**os.environ, "WINEDEBUG": "-all"}

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=PFG_WORK_DIR,
        )

        deadline = time.time() + self.cfg.pfg_timeout

        while time.time() < deadline:
            time.sleep(0.5)

            # FIX 1: Check PFG's own CWD for new XML files, NOT work_dir
            new_xmls = set(pfg_dir.glob("*.xml")) - existing_xmls
            if new_xmls:
                time.sleep(1.0)
                try:
                    proc.kill()
                except Exception:
                    pass
                break

            if proc.poll() is not None:
                new_xmls = set(pfg_dir.glob("*.xml")) - existing_xmls
                break

        if proc.poll() is None:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass

        # FIX 1: Move new XML and GRP JSONs from PFG dir to work dir
        new_xmls = set(pfg_dir.glob("*.xml")) - existing_xmls
        new_jsons = set(pfg_dir.glob("*.json")) - existing_jsons

        xml_path = None
        for f in new_xmls:
            dest = work_dir / f.name
            shutil.move(str(f), str(dest))
            xml_path = dest
            logger.info(f"Found PFG output XML: {f.name} -> {dest}")

        for f in new_jsons:
            dest = work_dir / f.name
            shutil.move(str(f), str(dest))
            logger.info(f"Found PFG output JSON: {f.name} -> {dest}")

        if xml_path is None:
            # Check if log file has useful info
            log_content = ""
            if log_file.exists():
                log_content = log_file.read_text(errors="replace")
            # Also check work_dir for any XML that might have appeared
            fallback = list(work_dir.glob("*.xml"))
            if fallback:
                xml_path = max(fallback, key=lambda f: f.stat().st_size)
                logger.info(f"Using fallback XML: {xml_path.name}")
            else:
                raise RuntimeError(
                    f"PFG produced no XML for {vid}. "
                    f"Checked {pfg_dir} for new .xml files. "
                    f"Log: {log_content[:500]}"
                )

        return xml_path

    # FIX 2 + FIX 3: Robust XML parsing with aggressive text cleaning
    def _clean_xml_text(self, raw_text: str) -> str:
        """Aggressively clean PFG XML output to make it parseable."""

        # Step 1: Fix Control-BASIC code inside <code> blocks
        # Some PFG versions don't escape < > in BASIC code
        def fix_code_block(match):
            code = match.group(1)
            code = code.replace("&", "&amp;")
            code = code.replace("<", "&lt;")
            code = code.replace(">", "&gt;")
            return f"<code>{code}</code>"

        raw_text = re.sub(r'<code>(.*?)</code>', fix_code_block, raw_text, flags=re.DOTALL)

        # Step 2: Fix bare & characters everywhere (not just code blocks)
        # More robust regex without \b which can be tricky
        raw_text = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#[0-9]+;|#x[0-9a-fA-F]+;)', '&amp;', raw_text)

        # Step 3: Fix "log enabled" attribute - PFG outputs a space in the attribute name
        # which is invalid XML. Every SINGLETREND and MULTITREND has this.
        raw_text = raw_text.replace(' log enabled=', ' logenabled=')

        # Step 4: Remove control characters that break XML
        # Keep tabs, newlines, carriage returns but remove everything else
        raw_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw_text)

        # Step 5: Fix degree symbols and other common special chars in attribute values
        # Replace ° with entity, other problematic chars
        raw_text = raw_text.replace('°', '&#176;')
        raw_text = raw_text.replace('±', '&#177;')
        raw_text = raw_text.replace('²', '&#178;')
        raw_text = raw_text.replace('³', '&#179;')
        raw_text = raw_text.replace('µ', '&#181;')

        return raw_text

    def _parse_xml(self, xml_path: Path) -> dict:
        result = {
            "AI": [], "AO": [], "AV": [],
            "BI": [], "BO": [], "BV": [],
            "MO": [], "MV": [],
            "PROGRAM": [],
            "LOOP": [],
            "TREND": [],
            "SCHEDULE": [],
            "CALENDAR": [],
            "SMARTSENSOR": [],
            "SYSTEMGROUP": [],
            "TABLE": [],
            "ARRAY": [],
            "DEVICE": [],
            "OTHER": [],
        }

        TYPE_MAP = {
            "ANALOGINPUT":      "AI",
            "ANALOGOUTPUT":     "AO",
            "ANALOGVALUE":      "AV",
            "BINARYINPUT":      "BI",
            "BINARYOUTPUT":     "BO",
            "BINARYVALUE":      "BV",
            "MULTISTATEOUTPUT": "MO",
            "MULTISTATEVALUE":  "MV",
            "MULTIOUTPUT":      "MO",
            "MULTIVALUE":       "MV",
        }

        try:
            raw_bytes = xml_path.read_bytes()
            # Try UTF-8, fall back to latin-1 which never fails
            try:
                raw_text = raw_bytes.decode('utf-8')
            except UnicodeDecodeError:
                raw_text = raw_bytes.decode('latin-1')

            raw_text = self._clean_xml_text(raw_text)
            root = ET.fromstring(raw_text)

        except ET.ParseError as e:
            # Save the problematic XML for debugging
            debug_dir = self.cfg.library_root / "_debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_file = debug_dir / xml_path.name

            # Save both raw and cleaned versions
            try:
                raw_original = xml_path.read_bytes()
                (debug_dir / f"{xml_path.stem}_raw.xml").write_bytes(raw_original)
                (debug_dir / f"{xml_path.stem}_cleaned.xml").write_text(raw_text)
            except Exception:
                pass

            logger.warning(
                f"XML parse error in {xml_path.name}: {e} - "
                f"saved debug copies to {debug_dir}/"
            )

            # FALLBACK: Try line-by-line regex extraction
            logger.info(f"Attempting regex fallback parser for {xml_path.name}")
            return self._regex_parse_xml(raw_text, TYPE_MAP, result)

        for elem in root.iter("point"):
            ptype = (elem.get("type") or "").upper()
            attrs = {k.lower(): v for k, v in elem.attrib.items()}

            mapped = TYPE_MAP.get(ptype)
            if mapped:
                result[mapped].append({
                    "type": mapped,
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "description": attrs.get("description", ""),
                    "range": attrs.get("range", ""),
                    "unit": attrs.get("unit", ""),
                    "increment": attrs.get("increment", ""),
                    "present_value": attrs.get("presentvalue", ""),
                })

            elif ptype == "PROGRAM":
                code_elem = elem.find("code")
                code = (code_elem.text or "").strip() if code_elem is not None else (elem.text or "").strip()
                # FIX 2: Unescape back to real Control-BASIC
                code = code.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
                result["PROGRAM"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "description": attrs.get("description", ""),
                    "code": code,
                })

            elif ptype == "LOOP":
                result["LOOP"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "proportional": attrs.get("proportional-constant", ""),
                    "integral": attrs.get("integral", ""),
                    "derivative": attrs.get("derivative", ""),
                    "action": attrs.get("action", ""),
                    "deadband": attrs.get("deadband", ""),
                    "bias": attrs.get("bias", ""),
                    "integralunits": attrs.get("integralunits", ""),
                })

            elif ptype in ("SINGLETREND", "MULTITREND"):
                refs = [attrs.get(f"point{i}") for i in range(1, 9) if attrs.get(f"point{i}")]
                result["TREND"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "interval": attrs.get("interval", ""),
                    "logtype": attrs.get("logtype", ""),
                    "enabled": attrs.get("logenabled", attrs.get("enabled", attrs.get("log", ""))),
                    "type": ptype,
                    "references": refs,
                })

            elif ptype == "SCHEDULE":
                result["SCHEDULE"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "present_value": attrs.get("presentvalue", ""),
                })

            elif ptype == "CALENDAR":
                result["CALENDAR"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "present_value": attrs.get("presentvalue", ""),
                })

            elif ptype == "SMARTSENSOR":
                rows = []
                for row in elem.findall("row"):
                    rows.append({k.lower(): v for k, v in row.attrib.items()})
                result["SMARTSENSOR"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "rows": rows,
                })

            elif ptype == "SYSTEMGROUP":
                result["SYSTEMGROUP"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "groupgraphic": attrs.get("groupgraphic", ""),
                    "jsonpath": attrs.get("jsonpath", ""),
                    "autoupdate": attrs.get("autoupdate", ""),
                })

            # FIX 3: Parse TABLE objects (calibration curves, sensor scaling)
            elif ptype == "TABLE":
                rows = []
                for row in elem.findall("row"):
                    rows.append({
                        "in": row.get("in", ""),
                        "out": row.get("out", ""),
                    })
                result["TABLE"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "description": attrs.get("description", ""),
                    "unit": attrs.get("unit", ""),
                    "inunit": attrs.get("inunit", ""),
                    "rows": rows,
                })

            # FIX 3: Parse ARRAY objects (zone aggregation, IFDD config)
            elif ptype == "ARRAY":
                rows = []
                for row in elem.findall("row"):
                    rows.append(row.get("value", ""))
                result["ARRAY"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "description": attrs.get("description", ""),
                    "size": attrs.get("size", ""),
                    "unit": attrs.get("unit", ""),
                    "values": rows,
                })

            # FIX 3: Parse DEVICE objects (BACnet instance, name, location)
            elif ptype == "DEVICE":
                result["DEVICE"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "description": attrs.get("description", ""),
                    "location": attrs.get("location", ""),
                })

            else:
                if ptype:
                    result["OTHER"].append({
                        "type": ptype,
                        "instance": attrs.get("instance", ""),
                        "name": attrs.get("objectname", ""),
                        "attrs": attrs,
                    })

        return result

    def _regex_parse_xml(self, raw_text: str, TYPE_MAP: dict, result: dict) -> dict:
        """Fallback: extract point data via regex when XML parsing fails."""

        # Extract all <point ...> or <point ...>...</point> blocks
        # Match self-closing: <point type="X" instance="1" ... />
        for m in re.finditer(r'<point\s+(.*?)\s*/>', raw_text, re.DOTALL):
            attrs_str = m.group(1)
            attrs = dict(re.findall(r'(\w[\w-]*)="([^"]*)"', attrs_str))
            attrs = {k.lower(): v for k, v in attrs.items()}
            ptype = attrs.get("type", "").upper()

            mapped = TYPE_MAP.get(ptype)
            if mapped:
                result[mapped].append({
                    "type": mapped,
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "description": attrs.get("description", ""),
                    "range": attrs.get("range", ""),
                    "unit": attrs.get("unit", ""),
                    "increment": attrs.get("increment", ""),
                    "present_value": attrs.get("presentvalue", ""),
                })
            elif ptype == "LOOP":
                result["LOOP"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "proportional": attrs.get("proportional-constant", ""),
                    "integral": attrs.get("integral", ""),
                    "derivative": attrs.get("derivative", ""),
                    "action": attrs.get("action", ""),
                    "deadband": attrs.get("deadband", ""),
                    "bias": attrs.get("bias", ""),
                    "integralunits": attrs.get("integralunits", ""),
                })
            elif ptype in ("SINGLETREND", "MULTITREND"):
                refs = [attrs.get(f"point{i}") for i in range(1, 9) if attrs.get(f"point{i}")]
                result["TREND"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "interval": attrs.get("interval", ""),
                    "logtype": attrs.get("logtype", ""),
                    "type": ptype,
                    "references": refs,
                })
            elif ptype == "SCHEDULE":
                result["SCHEDULE"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                })
            elif ptype == "CALENDAR":
                result["CALENDAR"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                })
            elif ptype == "SMARTSENSOR":
                result["SMARTSENSOR"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                })
            elif ptype == "SYSTEMGROUP":
                result["SYSTEMGROUP"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                })
            elif ptype == "TABLE":
                result["TABLE"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "description": attrs.get("description", ""),
                    "rows": [],
                })
            elif ptype == "ARRAY":
                result["ARRAY"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "description": attrs.get("description", ""),
                    "values": [],
                })
            elif ptype == "DEVICE":
                result["DEVICE"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "description": attrs.get("description", ""),
                    "location": attrs.get("location", ""),
                })

        # Extract PROGRAM blocks with code: <point type="PROGRAM" ...><code>...</code></point>
        for m in re.finditer(
            r'<point\s+(.*?)>\s*<code>(.*?)</code>\s*</point>',
            raw_text, re.DOTALL
        ):
            attrs_str = m.group(1)
            code = m.group(2).strip()
            attrs = dict(re.findall(r'(\w[\w-]*)="([^"]*)"', attrs_str))
            attrs = {k.lower(): v for k, v in attrs.items()}
            ptype = attrs.get("type", "").upper()
            if ptype == "PROGRAM":
                # Unescape any XML entities back to real BASIC
                code = code.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
                result["PROGRAM"].append({
                    "instance": attrs.get("instance", ""),
                    "name": attrs.get("objectname", ""),
                    "description": attrs.get("description", ""),
                    "code": code,
                })

        obj_count = sum(len(v) for v in result.values() if isinstance(v, list))
        logger.info(f"Regex fallback extracted {obj_count} objects")
        return result

    def _library_path(self, category: str, vid: str) -> Path:
        return self.cfg.library_root / category / f"{vid}.json"

    def _save_library_entry(self, category: str, vid: str, record: dict):
        p = self._library_path(category, vid)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(record, indent=2))

    def load_library_entry(self, category: str, vid: str) -> Optional[dict]:
        p = self._library_path(category, vid)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except Exception:
            return None

    def library_summary(self) -> dict:
        summary = {}
        if not self.cfg.library_root.exists():
            return summary
        for cat_dir in sorted(self.cfg.library_root.iterdir()):
            if not cat_dir.is_dir() or cat_dir.name.startswith("_"):
                continue
            variants = []
            for jf in sorted(cat_dir.glob("*.json")):
                try:
                    data = json.loads(jf.read_text())
                    variants.append({
                        "id": data.get("id", jf.stem),
                        "category": data.get("category", cat_dir.name),
                        "format": data.get("format"),
                        "counts": data.get("counts", {}),
                        "meta": data.get("meta", {}),
                        "description": data.get("description", "") or data.get("meta", {}).get("description", ""),
                    })
                except Exception:
                    pass
            if variants:
                summary[cat_dir.name] = variants
        return summary

    def full_library_export(self) -> dict:
        export = {}
        if not self.cfg.library_root.exists():
            return export
        for cat_dir in sorted(self.cfg.library_root.iterdir()):
            if not cat_dir.is_dir() or cat_dir.name.startswith("_"):
                continue
            export[cat_dir.name] = {}
            for jf in sorted(cat_dir.glob("*.json")):
                try:
                    data = json.loads(jf.read_text())
                    export[cat_dir.name][jf.stem] = data
                except Exception:
                    pass
        return export

    def _cat_folder(self, cat_key: str) -> str:
        inv = {v: k for k, v in self.cfg.CATEGORIES.items()}
        return inv.get(cat_key, cat_key)

    def _count_objects(self, parsed: dict) -> dict:
        return {k: len(v) for k, v in parsed.items() if isinstance(v, list) and v}
