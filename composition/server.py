"""
SBS Composition Engine v2 — FastAPI Standalone Server

Standalone web server for the composition engine UI.
Runs on port 8087 (separate from DFA platform and composer).
"""

import sys
import os
import io
import json
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from composition.assembler import assemble, CONTROLLER_SPECS
from composition.excel_gen import generate_excel
from composition.program_loader import inject_program_code
from composition.module_registry import (
    list_modules, list_by_category, get_module, STANDARD_CONFIGS, EQUIPMENT_FAMILIES
)

app = FastAPI(
    title="SBS Composition Engine v2",
    description="Vendor-neutral HVAC module composition + Reliable Controls output",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AssembleRequest(BaseModel):
    modules: List[str]
    controller_model: str = "auto"


class GenerateRequest(BaseModel):
    modules: List[str]
    controller_model: str = "auto"


# --- API Endpoints ---

@app.get("/api/modules")
async def api_list_modules():
    return list_by_category()


@app.get("/api/modules/{module_id}")
async def api_get_module(module_id: str):
    try:
        mod = get_module(module_id)
    except ValueError:
        raise HTTPException(404, f"Module not found: {module_id}")
    return {
        "id": mod.id, "name": mod.name, "category": mod.category,
        "description": mod.description, "is_core": mod.is_core,
        "requires": mod.requires, "conflicts": mod.conflicts,
        "mutually_exclusive_group": mod.mutually_exclusive_group,
        "inputs": len(mod.inputs), "outputs": len(mod.outputs),
        "values": len(mod.values), "loops": len(mod.loops),
        "programs": len(mod.programs), "soo_paragraph": mod.soo_paragraph,
    }


@app.get("/api/families")
async def api_list_families():
    return EQUIPMENT_FAMILIES


@app.get("/api/standards")
async def api_list_standards():
    return STANDARD_CONFIGS


@app.get("/api/controllers")
async def api_list_controllers():
    return {"auto": {"family": "Auto-Select", "base_in": 0, "base_out": 0, "max_exp": 0}, **CONTROLLER_SPECS}


@app.post("/api/assemble")
async def api_assemble(req: AssembleRequest):
    try:
        config = assemble(req.modules, controller_model=req.controller_model)
        inject_program_code(config)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {
        "modules": config.selected_modules,
        "controller": {
            "model": config.controller_model,
            "expansion_count": config.expansion_count,
            "expansion_model": config.expansion_model,
            "highest_input_row": config.highest_input_row,
            "highest_output_row": config.highest_output_row,
        },
        "counts": {
            "inputs": len(config.inputs), "outputs": len(config.outputs),
            "values": len(config.values), "loops": len(config.loops),
            "tables": len(config.tables), "programs": len(config.programs),
            "schedules": len(config.schedules), "trends": len(config.trends),
            "system_groups": len(config.system_groups),
            "max_value_inst": max((v.instance for v in config.values), default=0),
            "max_loop_inst": max((l.instance for l in config.loops), default=0),
            "max_prg_inst": max((p.instance for p in config.programs), default=0),
        },
        "inputs": [{"row": p.row, "name": p.name, "type": p.point_type, "desc": p.description, "units": p.units, "range": p.range_code, "module": p.module} for p in config.inputs],
        "outputs": [{"row": p.row, "name": p.name, "type": p.point_type, "desc": p.description, "module": p.module, "reverse": p.reverse, "min_v": p.min_v, "max_v": p.max_v} for p in config.outputs],
        "values": [{"instance": v.instance, "name": v.name, "type": v.point_type, "default": str(v.default), "units": v.units, "desc": v.description, "module": v.module} for v in config.values],
        "loops": [{"instance": l.instance, "name": l.name, "input": l.input_ref, "setpoint": l.setpoint_ref, "p": l.p_band, "i": l.integral, "action": l.action, "desc": l.description} for l in config.loops],
        "programs": [{"instance": p.instance, "name": p.name, "filename": p.filename, "enabled": p.enabled, "desc": p.description, "has_code": bool(p.code and len(p.code) > 50), "code": p.code or ""} for p in sorted(config.programs, key=lambda x: x.exec_order)],
        "soo": config.soo_document,
        "warnings": getattr(config, 'warnings', []),
    }


@app.post("/api/generate")
async def api_generate(req: GenerateRequest):
    try:
        config = assemble(req.modules, controller_model=req.controller_model)
        inject_program_code(config)
    except ValueError as e:
        raise HTTPException(400, str(e))

    excel_data = generate_excel(config)
    readme = _build_readme(config, include_pan=False)
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", readme)
        zf.writestr("RC-Studio-Output.xlsx", excel_data)
        for prg in config.programs:
            zf.writestr(f"programs/{prg.filename}", prg.code or "")
        zf.writestr("SOO.txt", config.soo_document)
        zf.writestr("summary.json", json.dumps({
            "modules": config.selected_modules,
            "controller": config.controller_model,
            "expansion": f"{config.expansion_count}x {config.expansion_model}" if config.expansion_count else "none",
            "counts": {"inputs": len(config.inputs), "outputs": len(config.outputs),
                       "values": len(config.values), "loops": len(config.loops),
                       "programs": len(config.programs), "trends": len(config.trends)},
        }, indent=2))
    zip_buf.seek(0)
    return StreamingResponse(zip_buf, media_type="application/zip",
                             headers={"Content-Disposition": "attachment; filename=composition-package.zip"})


def _build_readme(config, include_pan=False):
    """Build instructions README for download package."""
    model = config.controller_model or "MPS"
    lines = [
        "SBS COMPOSITION ENGINE — PACKAGE INSTRUCTIONS",
        "=" * 55,
        f"Generated by SBS Composition Engine v2",
        f"Controller: {model}" + (f" + {config.expansion_count}x {config.expansion_model}" if config.expansion_count else ""),
        f"Family: {config.equipment_family}",
        f"Modules: {', '.join(config.selected_modules)}",
        "",
        "PACKAGE CONTENTS",
        "-" * 40,
        "  RC-Studio-Output.xlsx  — Full data reference (13 tabs)",
        "  programs/              — Control-BASIC .bas files",
        "  programs/PRG-ALARMS.bas — Auto-generated alarm program",
        "  SOO.txt                — Sequence of Operations",
    ]
    if include_pan:
        lines.append(f"  SBS-{config.equipment_family}-{model}.pan — Controller template file")
    lines += [
        "",
        "STEP-BY-STEP INSTRUCTIONS",
        "-" * 40,
    ]
    if include_pan:
        lines += [
            "",
            "1. OPEN .PAN FILE",
            "   Open the .pan file in RC Studio or PFU.",
            "   The file has all points with correct ranges and loop tuning.",
            "",
            "2. SET DEFAULT VALUES",
            "   Open the Excel file, go to the 'Values' tab.",
            "   For each AV point with a non-zero default:",
            "   - Find the point in RC Studio/PFU",
            "   - Set the Present Value to match the Excel 'Default Value' column",
            "",
            "3. CONFIGURE LOOPS",
            "   Open the Excel 'Loops' tab for full PID parameters.",
            "   In RC Studio, for each loop set:",
            "   - Input point (from 'Input' column)",
            "   - Setpoint point (from 'Setpoint' column)",
            "   - Output point (from 'Output' column)",
            "   - P-band, Integral, Action are already set in the .pan",
            "",
            "4. FILL TABLE SCALING DATA",
            "   Open the Excel 'Tables' tab.",
            "   In RC Studio, for each table enter the data points",
            "   from the 'Data Points' column (input -> output pairs).",
            "",
            "5. PASTE PROGRAM CODE",
            "   For each program in the programs/ folder:",
            "   - Open the .bas file in a text editor",
            "   - In RC Studio/PFU, go to the corresponding program",
            "   - Paste the code into the program editor",
            "   - Compile the program",
            "   Also paste PRG-ALARMS.bas as an additional alarm program.",
            "",
            "6. SET UP TRENDS",
            "   Open the Excel 'Trends' tab.",
            "   In RC Studio, create trend logs matching the list:",
            "   - STL name, monitored point, type (Polled/COV), interval",
            "",
            "7. VERIFY",
            "   Use the 'Commissioning' tab in Excel as a point checkout list.",
            "   Green columns are for field data entry (Actual, Pass, Notes).",
        ]
    else:
        lines += [
            "",
            "1. CREATE PROJECT IN RC STUDIO",
            "   Create a new project for the target controller ({model}).",
            "   Use the Excel 'Inputs' and 'Outputs' tabs to set up I/O points.",
            "",
            "2. IMPORT VALUES",
            "   Use the 'Values' tab to create AV/BV/MV points with defaults.",
            "   MV state text is in the Units/Description columns.",
            "",
            "3. PASTE PROGRAM CODE",
            "   For each program in the programs/ folder:",
            "   - Open the .bas file, copy all text",
            "   - Create the program in RC Studio",
            "   - Paste and compile",
            "   Also create PRG-ALARMS.bas as an additional alarm program.",
            "",
            "4. CONFIGURE LOOPS, TABLES, TRENDS",
            "   Use the Excel tabs as reference for all configuration.",
            "",
            "5. VERIFY WITH COMMISSIONING CHECKLIST",
            "   The 'Commissioning' tab has a point checkout list.",
        ]
    lines += [
        "",
        "EXCEL TABS REFERENCE",
        "-" * 40,
        "  Inputs        — AI/BI points with terminal rows and ranges",
        "  Outputs       — AO/BO points with voltage ranges",
        "  Values        — AV/BV/MV with defaults, units, state text",
        "  Loops         — PID tuning: P-band, integral, action, bindings",
        "  Tables        — Scaling table data points",
        "  Schedules     — Weekly schedule definitions",
        "  Trends        — Trend log definitions (STL polled/COV)",
        "  System Groups — Graphic page assignments",
        "  Programs      — Program list with descriptions",
        "  Custom Units  — SBS standard enumerations",
        "  Alarms        — Alarm definitions + BAS code preview",
        "  Commissioning — Field point checkout (green = fill in)",
        "",
        "Generated by SBS Controls — Ameresco",
    ]
    return "\n".join(lines)


# Store last assembled config for GET-based downloads
_last_config = {"modules": [], "controller_model": "auto"}


@app.post("/api/generate-pan")
async def api_generate_pan(req: GenerateRequest):
    """Generate a .pan binary file with compiled programs."""
    from composition.pan_builder import build_pan_from_config, build_from_seed
    _last_config["modules"] = req.modules
    _last_config["controller_model"] = req.controller_model
    try:
        config = assemble(req.modules, controller_model=req.controller_model)
        inject_program_code(config)
    except ValueError as e:
        raise HTTPException(400, str(e))

    model = config.controller_model or "MPS"

    # Try seed-based approach first (better quality)
    seed_path = Path('/srv/dfa/shared/files/vendors/reliable/seeds/MACH-ProSys-88-AHU114.pan')
    if seed_path.exists() and model in ("MPS", "MPWS", "auto"):
        from composition.pan_filler import fill_pan
        seed_data = seed_path.read_bytes()
        filled = fill_pan(seed_data, config)
        from composition.pan_builder import inject_programs_into_seed
        pan_data = inject_programs_into_seed(filled, config, model)
    else:
        pan_data = build_pan_from_config(config, device_id=1000, controller_model=model)

    buf = io.BytesIO(pan_data)
    filename = f"SBS-{config.equipment_family}-{model}.pan"
    return StreamingResponse(buf, media_type="application/octet-stream",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.post("/api/generate-full")
async def api_generate_full(req: GenerateRequest):
    """Generate complete package: Excel + .bas + .pan + SOO."""
    from composition.pan_builder import build_pan_from_config, build_from_seed
    try:
        config = assemble(req.modules, controller_model=req.controller_model)
        inject_program_code(config)
    except ValueError as e:
        raise HTTPException(400, str(e))

    from composition.alarm_gen import generate_alarm_bas
    model = config.controller_model or "MPS"
    excel_data = generate_excel(config)
    alarm_bas = generate_alarm_bas(config)

    # Build .pan — use seed for data fill only
    seed_path = Path('/srv/dfa/shared/files/vendors/reliable/seeds/MACH-ProSys-88-AHU114.pan')
    if seed_path.exists() and model in ("MPS", "MPWS", "auto"):
        from composition.pan_filler import fill_pan
        seed_data = seed_path.read_bytes()
        pan_data = fill_pan(seed_data, config)
    else:
        pan_data = build_pan_from_config(config, device_id=1000, controller_model=model)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("RC-Studio-Output.xlsx", excel_data)
        zf.writestr(f"SBS-{config.equipment_family}-{model}.pan", pan_data)
        for prg in config.programs:
            zf.writestr(f"programs/{prg.filename}", prg.code or "")
        if alarm_bas:
            zf.writestr("programs/PRG-ALARMS.bas", alarm_bas)
        zf.writestr("SOO.txt", config.soo_document)
        zf.writestr("summary.json", json.dumps({
            "modules": config.selected_modules,
            "controller": model,
            "expansion": f"{config.expansion_count}x {config.expansion_model}" if config.expansion_count else "none",
            "pan_size": len(pan_data),
            "programs_compiled": sum(1 for p in config.programs if p.code),
            "counts": {"inputs": len(config.inputs), "outputs": len(config.outputs),
                       "values": len(config.values), "loops": len(config.loops),
                       "programs": len(config.programs), "trends": len(config.trends)},
        }, indent=2))
    zip_buf.seek(0)
    return StreamingResponse(zip_buf, media_type="application/zip",
                             headers={"Content-Disposition": "attachment; filename=sbs-full-package.zip"})


@app.get("/api/download-pan")
async def api_download_pan(modules: str = "", controller: str = "auto"):
    """GET-based .pan download (browser-friendly)."""
    from composition.pan_filler import fill_pan
    mod_list = [m.strip() for m in modules.split(",") if m.strip()]
    if not mod_list:
        raise HTTPException(400, "No modules specified")
    config = assemble(mod_list, controller_model=controller)
    inject_program_code(config)
    model = config.controller_model or "MPS"
    seed_path = Path('/srv/dfa/shared/files/vendors/reliable/seeds/MACH-ProSys-88-AHU114.pan')
    if seed_path.exists() and model in ("MPS", "MPWS", "auto"):
        pan_data = fill_pan(seed_path.read_bytes(), config)
    else:
        from composition.pan_builder import build_pan_from_config
        pan_data = build_pan_from_config(config, device_id=1000, controller_model=model)
    buf = io.BytesIO(pan_data)
    return StreamingResponse(buf, media_type="application/octet-stream",
                             headers={"Content-Disposition": f"attachment; filename=SBS-{config.equipment_family}-{model}.pan"})


@app.get("/api/download-full")
async def api_download_full(modules: str = "", controller: str = "auto"):
    """GET-based full package download (browser-friendly)."""
    from composition.alarm_gen import generate_alarm_bas
    from composition.pan_filler import fill_pan
    mod_list = [m.strip() for m in modules.split(",") if m.strip()]
    if not mod_list:
        raise HTTPException(400, "No modules specified")
    config = assemble(mod_list, controller_model=controller)
    inject_program_code(config)
    model = config.controller_model or "MPS"
    excel_data = generate_excel(config)
    alarm_bas = generate_alarm_bas(config)
    seed_path = Path('/srv/dfa/shared/files/vendors/reliable/seeds/MACH-ProSys-88-AHU114.pan')
    if seed_path.exists() and model in ("MPS", "MPWS", "auto"):
        pan_data = fill_pan(seed_path.read_bytes(), config)
    else:
        from composition.pan_builder import build_pan_from_config
        pan_data = build_pan_from_config(config, device_id=1000, controller_model=model)
    readme = _build_readme(config, include_pan=True)
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", readme)
        zf.writestr("RC-Studio-Output.xlsx", excel_data)
        zf.writestr(f"SBS-{config.equipment_family}-{model}.pan", pan_data)
        for prg in config.programs:
            zf.writestr(f"programs/{prg.filename}", prg.code or "")
        if alarm_bas:
            zf.writestr("programs/PRG-ALARMS.bas", alarm_bas)
        zf.writestr("SOO.txt", config.soo_document)
    zip_buf.seek(0)
    return StreamingResponse(zip_buf, media_type="application/zip",
                             headers={"Content-Disposition": "attachment; filename=sbs-full-package.zip"})


# --- Admin Auth ---

ADMIN_USER = "Admin"
ADMIN_PASS = "D@mo2142"
# Active sessions: set of token strings
_admin_sessions = set()

import hashlib, time


class LoginRequest(BaseModel):
    username: str
    password: str


class BasSaveRequest(BaseModel):
    filename: str
    code: str
    token: str = ""


def _check_admin(token: str):
    if token not in _admin_sessions:
        raise HTTPException(403, "Not authenticated — login required")


@app.post("/api/admin/login")
async def api_admin_login(req: LoginRequest):
    if req.username != ADMIN_USER or req.password != ADMIN_PASS:
        raise HTTPException(403, "Invalid credentials")
    token = hashlib.sha256(f"{time.time()}-{req.username}".encode()).hexdigest()[:32]
    _admin_sessions.add(token)
    return {"ok": True, "token": token}


# --- .bas Editor API (admin-protected) ---

BAS_DIR = Path(__file__).parent / "programs" / "reliable"


@app.get("/api/bas/list")
async def api_bas_list(token: str = ""):
    """List all .bas template files."""
    _check_admin(token)
    files = sorted(f.name for f in BAS_DIR.glob("*.bas")
                   if not f.name.endswith(".bak-20260323") and not f.name.endswith(".editor-bak"))
    return {"files": files}


@app.get("/api/bas/read")
async def api_bas_read(filename: str, token: str = ""):
    """Read a .bas template file."""
    _check_admin(token)
    path = BAS_DIR / filename
    if not path.exists() or not path.is_file() or ".." in filename:
        raise HTTPException(404, f"File not found: {filename}")
    return {"filename": filename, "code": path.read_text(encoding="utf-8", errors="replace")}


@app.post("/api/bas/save")
async def api_bas_save(req: BasSaveRequest):
    """Save a .bas template file (admin-protected)."""
    _check_admin(req.token)
    if ".." in req.filename or "/" in req.filename or "\\" in req.filename:
        raise HTTPException(400, "Invalid filename")
    path = BAS_DIR / req.filename
    if not path.exists():
        raise HTTPException(404, f"File not found: {req.filename}")
    import shutil
    bak = BAS_DIR / (req.filename + ".editor-bak")
    shutil.copy2(path, bak)
    path.write_text(req.code, encoding="utf-8")
    return {"ok": True, "filename": req.filename, "size": len(req.code)}


# --- Standard I/O Map Export/Import ---

IO_MAP_PATH = Path(__file__).parent / "standard_io_map.json"


@app.get("/api/io-map/export")
async def api_io_map_export(token: str = ""):
    """Export standard I/O map as Excel."""
    _check_admin(token)
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    if not IO_MAP_PATH.exists():
        raise HTTPException(404, "Standard I/O map not found")

    data = json.loads(IO_MAP_PATH.read_text())
    wb = openpyxl.Workbook()

    # --- Inputs sheet ---
    ws = wb.active
    ws.title = "Inputs"
    headers = ["Row", "Name", "Type", "Range", "Units", "Description", "Module"]
    hdr_font = Font(bold=True, color="FFFFFF")
    hdr_fill = PatternFill("solid", fgColor="1a237e")
    thin = Side(style="thin", color="334155")
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = hdr_font
        cell.fill = hdr_fill
    for i, pt in enumerate(data["inputs"], 2):
        ws.cell(row=i, column=1, value=pt["row"])
        ws.cell(row=i, column=2, value=pt["name"])
        ws.cell(row=i, column=3, value=pt["type"])
        ws.cell(row=i, column=4, value=pt["range"])
        ws.cell(row=i, column=5, value=pt.get("units", ""))
        ws.cell(row=i, column=6, value=pt["description"])
        ws.cell(row=i, column=7, value=pt["module"])
    for col in [("A", 6), ("B", 16), ("C", 6), ("D", 18), ("E", 8), ("F", 35), ("G", 16)]:
        ws.column_dimensions[col[0]].width = col[1]

    # --- Outputs sheet ---
    ws2 = wb.create_sheet("Outputs")
    headers2 = ["Row", "Name", "Type", "Range", "Description", "Module", "Min V", "Max V", "Reverse"]
    for c, h in enumerate(headers2, 1):
        cell = ws2.cell(row=1, column=c, value=h)
        cell.font = hdr_font
        cell.fill = hdr_fill
    for i, pt in enumerate(data["outputs"], 2):
        ws2.cell(row=i, column=1, value=pt["row"])
        ws2.cell(row=i, column=2, value=pt["name"])
        ws2.cell(row=i, column=3, value=pt["type"])
        ws2.cell(row=i, column=4, value=pt["range"])
        ws2.cell(row=i, column=5, value=pt["description"])
        ws2.cell(row=i, column=6, value=pt["module"])
        ws2.cell(row=i, column=7, value=pt.get("min_v", ""))
        ws2.cell(row=i, column=8, value=pt.get("max_v", ""))
        ws2.cell(row=i, column=9, value="Yes" if pt.get("reverse") else "")
    for col in [("A", 6), ("B", 20), ("C", 6), ("D", 14), ("E", 35), ("F", 16), ("G", 8), ("H", 8), ("I", 8)]:
        ws2.column_dimensions[col[0]].width = col[1]

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=SBS-Standard-IO-Map.xlsx"})


@app.post("/api/io-map/import")
async def api_io_map_import(file: UploadFile = File(...), token: str = ""):
    """Import standard I/O map from Excel. Updates the JSON reference."""
    _check_admin(token)
    import openpyxl

    content = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)

    inputs = []
    if "Inputs" in wb.sheetnames:
        ws = wb["Inputs"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            inputs.append({
                "row": int(row[0]),
                "name": str(row[1] or ""),
                "type": str(row[2] or ""),
                "range": str(row[3] or ""),
                "units": str(row[4] or "") if len(row) > 4 else "",
                "description": str(row[5] or "") if len(row) > 5 else "",
                "module": str(row[6] or "") if len(row) > 6 else "",
            })

    outputs = []
    if "Outputs" in wb.sheetnames:
        ws = wb["Outputs"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            outputs.append({
                "row": int(row[0]),
                "name": str(row[1] or ""),
                "type": str(row[2] or ""),
                "range": str(row[3] or ""),
                "description": str(row[4] or "") if len(row) > 4 else "",
                "module": str(row[5] or "") if len(row) > 5 else "",
                "min_v": float(row[6]) if len(row) > 6 and row[6] else 0.0,
                "max_v": float(row[7]) if len(row) > 7 and row[7] else 0.0,
                "reverse": (str(row[8] or "").strip().lower() in ("yes", "true", "1")) if len(row) > 8 else False,
            })

    wb.close()

    # Backup existing
    if IO_MAP_PATH.exists():
        import shutil
        shutil.copy2(IO_MAP_PATH, IO_MAP_PATH.with_suffix(".json.bak"))

    data = {"inputs": sorted(inputs, key=lambda x: x["row"]),
            "outputs": sorted(outputs, key=lambda x: x["row"])}
    IO_MAP_PATH.write_text(json.dumps(data, indent=2))

    return {"ok": True, "inputs": len(inputs), "outputs": len(outputs)}


@app.get("/api/io-map/json")
async def api_io_map_json(token: str = ""):
    """Return the standard I/O map as JSON (for UI display)."""
    _check_admin(token)
    if not IO_MAP_PATH.exists():
        raise HTTPException(404, "Standard I/O map not found")
    return json.loads(IO_MAP_PATH.read_text())


# --- UI ---

@app.get("/", response_class=HTMLResponse)
async def ui():
    return HTML_UI


HTML_UI = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SBS Composition Engine v2</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0a0e17;color:#e0e6ed}
.hdr{background:linear-gradient(135deg,#1a237e,#0d47a1);padding:14px 24px;display:flex;justify-content:space-between;align-items:center}
.hdr h1{font-size:1.3em;font-weight:600}
.hdr .sub{color:#90caf9;font-size:0.8em}
.layout{display:grid;grid-template-columns:360px 1fr;height:calc(100vh - 56px)}
.side{background:#111827;border-right:1px solid #1e293b;overflow-y:auto;padding:14px}
.main{overflow-y:auto;padding:16px 20px}
.sec{margin-bottom:14px}
.sec-t{font-size:0.7em;text-transform:uppercase;letter-spacing:1px;color:#64748b;margin-bottom:6px;font-weight:600}
select,input{background:#1e293b;border:1px solid #334155;color:#e0e6ed;padding:7px 10px;border-radius:4px;width:100%;font-size:0.85em;margin-bottom:8px}
select:focus,input:focus{border-color:#3b82f6;outline:none}
.btn{padding:9px 18px;border:none;border-radius:5px;cursor:pointer;font-size:0.85em;font-weight:600;transition:background 0.15s}
.btn-p{background:#2563eb;color:#fff}.btn-p:hover{background:#1d4ed8}
.btn-s{background:#059669;color:#fff}.btn-s:hover{background:#047857}
.btn-o{background:#d97706;color:#fff}.btn-o:hover{background:#b45309}
.btn-grp{display:flex;gap:8px;margin:10px 0}
.cfg-card{background:#1e293b;border:1px solid #334155;border-radius:6px;padding:10px 14px;margin-bottom:6px;cursor:pointer;transition:border 0.15s}
.cfg-card:hover{border-color:#3b82f6}
.cfg-card.active{border-color:#3b82f6;background:#172554}
.cfg-card h4{color:#e0e6ed;font-size:0.85em}
.cfg-card p{color:#94a3b8;font-size:0.75em;margin-top:2px}
.mod-grp{margin-bottom:10px}
.mod-grp-t{font-size:0.8em;color:#94a3b8;margin-bottom:3px;font-weight:500}
.mod-item{display:flex;align-items:center;gap:6px;padding:3px 6px;border-radius:3px;font-size:0.8em}
.mod-item:hover{background:#1e293b}
.mod-item.on{color:#60a5fa}
.mod-item.core{opacity:0.5}
.mod-item input{width:auto;margin:0}
.stat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:6px;margin:10px 0}
.stat{background:#1e293b;padding:8px;border-radius:5px;text-align:center}
.stat .v{font-size:1.4em;font-weight:700;color:#60a5fa}
.stat .l{font-size:0.7em;color:#94a3b8}
.tabs{display:flex;gap:3px;border-bottom:1px solid #1e293b;padding-bottom:6px;margin-bottom:10px;flex-wrap:wrap}
.tab{padding:5px 12px;border-radius:4px 4px 0 0;cursor:pointer;font-size:0.8em;color:#94a3b8;transition:all 0.15s}
.tab.act{background:#1e293b;color:#60a5fa;font-weight:600}
.tab:hover{color:#e0e6ed}
.tp{display:none}.tp.act{display:block}
table{width:100%;border-collapse:collapse;font-size:0.8em}
th{background:#1e293b;padding:6px 8px;text-align:left;color:#94a3b8;font-weight:500;position:sticky;top:0}
td{padding:5px 8px;border-bottom:1px solid #1e293b}
tr.unused td{color:#475569;font-style:italic}
.tag{display:inline-block;padding:1px 5px;border-radius:3px;font-size:0.75em;font-weight:600}
.tag-ai{background:#1e3a5f;color:#60a5fa}.tag-bi{background:#1a3636;color:#5eead4}
.tag-ao{background:#3b1f1f;color:#fca5a5}.tag-bo{background:#3b2f1f;color:#fbbf24}
.tag-av{background:#1e293b;color:#a78bfa}.tag-bv{background:#1e293b;color:#34d399}.tag-mv{background:#1e293b;color:#fb923c}
.soo{white-space:pre-wrap;font-family:'Courier New',monospace;font-size:0.78em;line-height:1.4;background:#0f172a;padding:14px;border-radius:5px;max-height:500px;overflow-y:auto}
#status{padding:6px 10px;background:#1e293b;border-radius:4px;font-size:0.8em;color:#94a3b8;margin-bottom:10px}
.row-label{font-size:0.7em;color:#475569;text-align:right;padding-right:4px}
.modal-bg{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);z-index:1000;justify-content:center;align-items:center}
.modal-bg.open{display:flex}
.modal{background:#111827;border:1px solid #334155;border-radius:8px;width:90%;max-width:1100px;height:85vh;display:flex;flex-direction:column;overflow:hidden}
.modal-hdr{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid #1e293b}
.modal-hdr h3{color:#60a5fa;font-size:1em}
.modal-body{display:flex;flex:1;overflow:hidden}
.modal-side{width:220px;border-right:1px solid #1e293b;overflow-y:auto;padding:8px}
.modal-side .bf{padding:5px 8px;cursor:pointer;border-radius:4px;font-size:0.8em;color:#94a3b8}
.modal-side .bf:hover{background:#1e293b;color:#e0e6ed}
.modal-side .bf.sel{background:#172554;color:#60a5fa}
.modal-edit{flex:1;display:flex;flex-direction:column;padding:10px}
.modal-edit textarea{flex:1;background:#0a0e17;color:#e0e6ed;border:1px solid #334155;border-radius:4px;font-family:'Courier New',monospace;font-size:0.82em;line-height:1.5;padding:10px;resize:none;tab-size:4}
.modal-edit textarea:focus{border-color:#3b82f6;outline:none}
.modal-foot{display:flex;gap:8px;align-items:center;padding:8px 0 0 0}
.modal-foot input{width:180px}
.ed-status{font-size:0.8em;color:#94a3b8;margin-left:auto}
</style>
</head>
<body>
<div class="hdr">
  <div><h1>SBS Composition Engine v2</h1><div class="sub">Reliable Controls Output Tool</div></div>
  <div class="btn-grp">
    <button class="btn btn-p" onclick="doAssemble()">Assemble</button>
    <button class="btn btn-s" onclick="doGenerate()">Download Excel + .bas</button>
    <button class="btn btn-s" style="background:#1e40af" onclick="doGeneratePan()">Download .pan</button>
    <button class="btn btn-s" style="background:#065f46" onclick="doGenerateFull()">Full Package</button>
    <button class="btn btn-o" id="btnAdmin" onclick="showAdminLogin()">Admin</button>
    <button class="btn btn-o" id="btnEditor" style="display:none" onclick="openEditor()">Edit .bas</button>
    <button class="btn btn-o" id="btnExportIO" style="display:none;background:#7c3aed" onclick="exportIOMap()">Export I/O Map</button>
    <button class="btn btn-o" id="btnImportIO" style="display:none;background:#5b21b6" onclick="document.getElementById('ioMapFile').click()">Import I/O Map</button>
    <input type="file" id="ioMapFile" accept=".xlsx" style="display:none" onchange="importIOMap(this)">
    <a id="hiddenDownload" style="display:none"></a>
  </div>
</div>
<div class="layout">
<div class="side">
  <div class="sec">
    <div class="sec-t">Equipment Family</div>
    <select id="selFamily" onchange="onFamilyChange()"><option value="">-- Select Family --</option></select>
    <div id="familyDesc" style="font-size:0.75em;color:#64748b;margin-bottom:8px"></div>
  </div>
  <div class="sec">
    <div class="sec-t">Standard Configuration</div>
    <div id="cfgList"></div>
  </div>
  <div class="sec">
    <div class="sec-t">Controller Model</div>
    <select id="selCtrl"><option value="auto">Auto-Select (recommended)</option></select>
  </div>
  <div class="sec">
    <div class="sec-t">Module Toggles <span style="font-size:0.85em;color:#475569">(on/off from standard)</span></div>
    <div id="modList"></div>
  </div>
</div>
<div class="main">
  <div id="status">Select an equipment family to begin.</div>
  <div id="results" style="display:none">
    <div class="stat-grid" id="stats"></div>
    <div class="tabs" id="tabBar"></div>
    <div id="tabContents"></div>
  </div>
</div>
</div>
<script>
let families={}, standards={}, modules={}, controllers={};
let selected=new Set(), activeCfg='', activeFamily='';

async function init(){
  try{
    var resp=await Promise.all([
      fetch('/api/families'),fetch('/api/standards'),fetch('/api/modules'),fetch('/api/controllers')
    ]);
    families=await resp[0].json();
    standards=await resp[1].json();
    modules=await resp[2].json();
    controllers=await resp[3].json();
    // Family dropdown
    var sf=document.getElementById('selFamily');
    var fkeys=Object.keys(families);
    for(var i=0;i<fkeys.length;i++){
      var o=document.createElement('option');
      o.value=fkeys[i];
      o.textContent=families[fkeys[i]].name;
      sf.appendChild(o);
    }
    // Controller dropdown
    var sc=document.getElementById('selCtrl');
    var ckeys=Object.keys(controllers);
    for(var i=0;i<ckeys.length;i++){
      if(ckeys[i]==='auto')continue;
      var o=document.createElement('option');
      o.value=ckeys[i];
      var cc=controllers[ckeys[i]];
      o.textContent=ckeys[i]+' ('+cc.family+') - '+cc.base_in+'in/'+cc.base_out+'out, '+cc.max_exp+' exp';
      sc.appendChild(o);
    }
    document.getElementById('status').textContent='Loaded: '+fkeys.length+' families, '+Object.keys(standards).length+' configs, '+Object.keys(controllers).length+' controllers. Select a family to begin.';
  }catch(err){
    document.getElementById('status').textContent='ERROR loading: '+err.message;
    console.error('Init error:',err);
  }
}

function onFamilyChange(){
  activeFamily=document.getElementById('selFamily').value;
  const f=families[activeFamily];
  document.getElementById('familyDesc').textContent=f?f.description:'';
  activeCfg='';
  selected.clear();
  renderConfigs();
  renderModules();
  document.getElementById('results').style.display='none';
  document.getElementById('status').textContent=f?'Select a standard configuration, then click Assemble.':'Select an equipment family.';
}

function renderConfigs(){
  var el=document.getElementById('cfgList');
  if(!activeFamily){el.innerHTML='<div style="color:#475569;font-size:0.8em">Select a family first</div>';return;}
  var html='';
  var keys=Object.keys(standards).filter(function(k){return standards[k].family===activeFamily;}).sort();
  if(!keys.length){el.innerHTML='<div style="color:#475569;font-size:0.8em">No configs for this family</div>';return;}
  for(var i=0;i<keys.length;i++){
    var id=keys[i],cfg=standards[id];
    var act=id===activeCfg?' active':'';
    html+='<div class="cfg-card'+act+'" onclick="selectCfg(\\x27'+id+'\\x27)">';
    html+='<h4>'+id+': '+cfg.name+'</h4>';
    html+='<p>'+cfg.description+'</p></div>';
  }
  el.innerHTML=html;
}

function selectCfg(id){
  activeCfg=id;
  const cfg=standards[id];
  selected=new Set(cfg.modules);
  renderConfigs();
  renderModules();
  document.getElementById('status').textContent='Loaded: '+id+' — '+cfg.name;
}

function renderModules(){
  var el=document.getElementById('modList');
  if(!activeFamily){el.innerHTML='';return;}
  var html='';
  var catOrder=['core','fan','cooling','heating','preheat','economizer','energy-recovery','ventilation','humidity','pump','safety','optimum-start'];
  for(var ci=0;ci<catOrder.length;ci++){
    var cat=catOrder[ci];
    var mods=modules[cat];if(!mods)continue;
    html+='<div class="mod-grp"><div class="mod-grp-t">'+cat.toUpperCase()+' ('+mods.length+')</div>';
    for(var mi=0;mi<mods.length;mi++){
      var m=mods[mi];
      var isCore=m.is_core;
      var checked=(isCore||selected.has(m.id))?'checked':'';
      var cls=isCore?'mod-item core':(selected.has(m.id)?'mod-item on':'mod-item');
      html+='<div class="'+cls+'"><input type="checkbox" '+checked+' '+(isCore?'disabled':'')+' onchange="toggleMod(\\x27'+m.id+'\\x27,this.checked)"><span>'+m.name+'</span></div>';
    }
    html+='</div>';
  }
  el.innerHTML=html;
}

function toggleMod(id,on){
  if(on)selected.add(id);else selected.delete(id);
  renderModules();
}

async function doAssemble(){
  var mods=Array.from(selected);
  var cats=Object.keys(modules);
  for(var ci=0;ci<cats.length;ci++){
    var ms=modules[cats[ci]];
    for(var mi=0;mi<ms.length;mi++){
      if(ms[mi].is_core&&mods.indexOf(ms[mi].id)===-1)mods.push(ms[mi].id);
    }
  }
  var body={modules:mods,controller_model:document.getElementById('selCtrl').value};
  document.getElementById('status').textContent='Assembling...';
  try{
    var res=await fetch('/api/assemble',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!res.ok){var e=await res.json();throw new Error(e.detail);}
    var r=await res.json();
    renderResults(r);
  }catch(e){document.getElementById('status').textContent='Error: '+e.message;}
}

function renderResults(r){
  document.getElementById('results').style.display='block';
  const c=r.counts,ctrl=r.controller;
  const exp=ctrl.expansion_count?ctrl.expansion_count+'x '+ctrl.expansion_model:'none';
  var statusText=ctrl.model+(ctrl.expansion_count?' + '+exp:'')+' | '+r.modules.length+' modules | '+c.inputs+' inputs, '+c.outputs+' outputs, '+c.programs+' programs';
  if(r.warnings&&r.warnings.length>0){statusText+=' | ⚠ '+r.warnings.length+' warning(s)';}
  document.getElementById('status').textContent=statusText;
  if(r.warnings&&r.warnings.length>0){
    var whtml='<div style="background:#78350f;border:1px solid #f59e0b;border-radius:6px;padding:12px;margin:8px 0;color:#fef3c7;font-size:13px"><b>⚠ Warnings ('+r.warnings.length+'):</b><ul style="margin:6px 0 0 16px;padding:0">';
    r.warnings.forEach(function(w){whtml+='<li style="margin:2px 0">'+w+'</li>';});
    whtml+='</ul></div>';
    document.getElementById('stats').insertAdjacentHTML('afterend',whtml);
  }

  document.getElementById('stats').innerHTML=
    '<div class="stat"><div class="v">'+ctrl.model+'</div><div class="l">Controller</div></div>'+
    '<div class="stat"><div class="v">'+(ctrl.expansion_count||0)+'</div><div class="l">Expansion</div></div>'+
    '<div class="stat"><div class="v">'+c.inputs+'</div><div class="l">Inputs (r'+ctrl.highest_input_row+')</div></div>'+
    '<div class="stat"><div class="v">'+c.outputs+'</div><div class="l">Outputs (r'+ctrl.highest_output_row+')</div></div>'+
    '<div class="stat"><div class="v">'+c.values+'</div><div class="l">Values</div></div>'+
    '<div class="stat"><div class="v">'+c.loops+'</div><div class="l">PID Loops</div></div>'+
    '<div class="stat"><div class="v">'+c.programs+'</div><div class="l">Programs</div></div>'+
    '<div class="stat"><div class="v">'+c.trends+'</div><div class="l">Trends</div></div>';

  const tabs=['Inputs','Outputs','Values','Loops','Programs','SOO'];
  document.getElementById('tabBar').innerHTML=tabs.map((t,i)=>'<div class="tab'+(i===0?' act':'')+'" onclick="showTab('+i+')">'+t+'</div>').join('');

  let tc='';
  // Inputs
  tc+='<div class="tp act" id="t0"><table><tr><th>Row</th><th>Type</th><th>Name</th><th>Range</th><th>Units</th><th>Description</th><th>Module</th></tr>';
  for(let row=1;row<=ctrl.highest_input_row;row++){
    const pt=r.inputs.find(p=>p.row===row);
    if(pt)tc+='<tr><td>'+row+'</td><td><span class="tag tag-'+pt.type.toLowerCase()+'">'+pt.type+'</span></td><td>{device-name}-'+pt.name+'</td><td>'+pt.range+'</td><td>'+(pt.units||'')+'</td><td>'+pt.desc+'</td><td>'+pt.module+'</td></tr>';
    else tc+='<tr class="unused"><td>'+row+'</td><td></td><td colspan="5">--- unused ---</td></tr>';
  }
  tc+='</table></div>';

  // Outputs
  tc+='<div class="tp" id="t1"><table><tr><th>Row</th><th>Type</th><th>Name</th><th>Min V</th><th>Max V</th><th>Description</th><th>Module</th></tr>';
  for(let row=1;row<=ctrl.highest_output_row;row++){
    const pt=r.outputs.find(p=>p.row===row);
    if(pt)tc+='<tr><td>'+row+'</td><td><span class="tag tag-'+pt.type.toLowerCase()+'">'+pt.type+'</span></td><td>{device-name}-'+pt.name+(pt.reverse?' (REV)':'')+'</td><td>'+(pt.min_v||'')+'</td><td>'+(pt.max_v||'')+'</td><td>'+pt.desc+'</td><td>'+pt.module+'</td></tr>';
    else tc+='<tr class="unused"><td>'+row+'</td><td></td><td colspan="5">--- unused ---</td></tr>';
  }
  tc+='</table></div>';

  // Values — show every row 1..max with empty fillers
  tc+='<div class="tp" id="t2"><table><tr><th>Instance</th><th>Type</th><th>Name</th><th>Default</th><th>Units</th><th>Description</th><th>Module</th></tr>';
  var valMap={};r.values.forEach(function(v){valMap[v.instance]=v;});
  for(var vi=1;vi<=c.max_value_inst;vi++){
    var v=valMap[vi];
    if(v){
      var pre={AV:'AV',BV:'BV',MV:'MV'}[v.type]||'AV';
      tc+='<tr><td>'+pre+vi+'</td><td><span class="tag tag-'+v.type.toLowerCase()+'">'+v.type+'</span></td><td>{device-name}-'+v.name+'</td><td>'+v.default+'</td><td>'+(v.units||'')+'</td><td>'+v.desc+'</td><td>'+v.module+'</td></tr>';
    }else{
      tc+='<tr class="unused"><td>AV'+vi+'</td><td></td><td colspan="5">--- unused ---</td></tr>';
    }
  }
  tc+='</table></div>';

  // Loops — show every row 1..max with fillers
  tc+='<div class="tp" id="t3"><table><tr><th>Loop</th><th>Name</th><th>Input</th><th>Setpoint</th><th>Action</th><th>P Band</th><th>Integral</th><th>Description</th></tr>';
  var loopMap={};r.loops.forEach(function(l){loopMap[l.instance]=l;});
  for(var li=1;li<=c.max_loop_inst;li++){
    var l=loopMap[li];
    if(l){
      tc+='<tr><td>LOOP'+li+'</td><td>'+l.name+'</td><td>{device-name}-'+l.input+'</td><td>{device-name}-'+l.setpoint+'</td><td>'+(l.action==='direct'?'+':'-')+'</td><td>'+l.p+'</td><td>'+l.i+'</td><td>'+l.desc+'</td></tr>';
    }else{
      tc+='<tr class="unused"><td>LOOP'+li+'</td><td colspan="7">--- unused ---</td></tr>';
    }
  }
  tc+='</table></div>';

  // Programs — show every row 1..max with fillers
  window._programs=r.programs;
  var prgMap={};r.programs.forEach(function(p,i){prgMap[p.instance]={p:p,i:i};});
  tc+='<div class="tp" id="t4"><table><tr><th>PRG#</th><th>Name</th><th>Filename</th><th>Enabled</th><th>Status</th><th>Description</th><th>View</th></tr>';
  for(var pi=1;pi<=c.max_prg_inst;pi++){
    var pe=prgMap[pi];
    if(pe){
      var p=pe.p;
      tc+='<tr><td>PRG'+pi+'</td><td>{device-name}-'+p.name+'</td><td>'+p.filename+'</td><td>'+(p.enabled?'Yes':'No')+'</td><td>'+(p.has_code?'OK':'STUB')+'</td><td>'+p.desc+'</td>';
      tc+='<td><button class="btn btn-p" style="padding:3px 10px;font-size:0.75em" onclick="viewProgram('+pe.i+')">View</button></td></tr>';
    }else{
      tc+='<tr class="unused"><td>PRG'+pi+'</td><td colspan="6">--- unused ---</td></tr>';
    }
  }
  tc+='</table><div id="prgViewer" style="display:none;margin-top:12px"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px"><h4 id="prgViewerTitle" style="color:#60a5fa;font-size:0.9em"></h4><button class="btn btn-o" style="padding:3px 10px;font-size:0.75em" onclick="document.getElementById(\\x27prgViewer\\x27).style.display=\\x27none\\x27">Close</button></div><pre class="soo" id="prgViewerCode" style="max-height:400px"></pre></div></div>';

  // SOO
  tc+='<div class="tp" id="t5"><div class="soo">'+r.soo.replace(/</g,'&lt;')+'</div></div>';

  document.getElementById('tabContents').innerHTML=tc;
}

function viewProgram(idx){
  var p=window._programs[idx];
  document.getElementById('prgViewer').style.display='block';
  document.getElementById('prgViewerTitle').textContent='PRG'+p.instance+': '+p.filename;
  document.getElementById('prgViewerCode').textContent=p.code||'(no code)';
  showTab(4);
}

function showTab(i){
  document.querySelectorAll('.tab').forEach((t,j)=>t.classList.toggle('act',j===i));
  document.querySelectorAll('.tp').forEach((t,j)=>t.classList.toggle('act',j===i));
}

async function doGenerate(){
  var mods=Array.from(selected);
  var cats=Object.keys(modules);
  for(var ci=0;ci<cats.length;ci++){
    var ms=modules[cats[ci]];
    for(var mi=0;mi<ms.length;mi++){
      if(ms[mi].is_core&&mods.indexOf(ms[mi].id)===-1)mods.push(ms[mi].id);
    }
  }
  var body={modules:mods,controller_model:document.getElementById('selCtrl').value};
  document.getElementById('status').textContent='Generating package...';
  try{
    var res=await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!res.ok){document.getElementById('status').textContent='Error generating';return;}
    var blob=await res.blob();
    var url=URL.createObjectURL(blob);
    var a=document.createElement('a');a.href=url;a.download='composition-package.zip';a.click();
    document.getElementById('status').textContent='Package downloaded!';
  }catch(e){document.getElementById('status').textContent='Error: '+e.message;}
}

function getModList(){
  var mods=Array.from(selected);
  var cats=Object.keys(modules);
  for(var ci=0;ci<cats.length;ci++){
    var ms=modules[cats[ci]];
    for(var mi=0;mi<ms.length;mi++){
      if(ms[mi].is_core&&mods.indexOf(ms[mi].id)===-1)mods.push(ms[mi].id);
    }
  }
  return mods;
}

async function doGeneratePan(){
  var mods=getModList();
  if(mods.length===0){document.getElementById('status').textContent='Assemble first';return;}
  var body=JSON.stringify({modules:mods,controller_model:document.getElementById('selCtrl').value});
  document.getElementById('status').textContent='Generating .pan...';
  try{
    var res=await fetch('/api/generate-pan',{method:'POST',headers:{'Content-Type':'application/json'},body:body});
    if(!res.ok){document.getElementById('status').textContent='Error';return;}
    var blob=await res.blob();
    var url=URL.createObjectURL(blob);
    var a=document.createElement('a');a.href=url;a.download='SBS-controller.pan';
    document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
    document.getElementById('status').textContent='.pan downloaded ('+Math.round(blob.size/1024)+'KB)';
  }catch(e){document.getElementById('status').textContent='Error: '+e;}
}

async function doGenerateFull(){
  var mods=getModList();
  if(mods.length===0){document.getElementById('status').textContent='Assemble first';return;}
  var body=JSON.stringify({modules:mods,controller_model:document.getElementById('selCtrl').value});
  document.getElementById('status').textContent='Generating full package...';
  try{
    var res=await fetch('/api/generate-full',{method:'POST',headers:{'Content-Type':'application/json'},body:body});
    if(!res.ok){document.getElementById('status').textContent='Error';return;}
    var blob=await res.blob();
    var url=URL.createObjectURL(blob);
    var a=document.createElement('a');a.href=url;a.download='sbs-full-package.zip';
    document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
    document.getElementById('status').textContent='Full package downloaded!';
  }catch(e){document.getElementById('status').textContent='Error: '+e;}
}

// --- Admin Auth ---
var adminToken='';

function showAdminLogin(){
  document.getElementById('loginModal').classList.add('open');
  document.getElementById('loginUser').focus();
}
async function doAdminLogin(){
  var u=document.getElementById('loginUser').value;
  var p=document.getElementById('loginPass').value;
  try{
    var res=await fetch('/api/admin/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});
    if(!res.ok){document.getElementById('loginError').textContent='Invalid credentials';return;}
    var d=await res.json();
    adminToken=d.token;
    document.getElementById('loginModal').classList.remove('open');
    document.getElementById('btnAdmin').style.display='none';
    document.getElementById('btnEditor').style.display='';
    document.getElementById('btnExportIO').style.display='';
    document.getElementById('btnImportIO').style.display='';
    document.getElementById('status').textContent='Admin access granted';
  }catch(e){document.getElementById('loginError').textContent='Error: '+e;}
}

// --- I/O Map Export/Import ---
async function exportIOMap(){
  var a=document.createElement('a');
  a.href='/api/io-map/export?token='+adminToken;a.download='SBS-Standard-IO-Map.xlsx';
  document.body.appendChild(a);a.click();a.remove();
  document.getElementById('status').textContent='I/O Map exported';
}
function importIOMap(input){
  if(!input.files.length)return;
  var fd=new FormData();
  fd.append('file',input.files[0]);
  document.getElementById('status').textContent='Importing I/O map...';
  fetch('/api/io-map/import?token='+adminToken,{method:'POST',body:fd}).then(r=>r.json()).then(d=>{
    if(d.ok)document.getElementById('status').textContent='I/O Map imported: '+d.inputs+' inputs, '+d.outputs+' outputs';
    else document.getElementById('status').textContent='Import error: '+JSON.stringify(d);
  }).catch(e=>{document.getElementById('status').textContent='Import error: '+e;});
  input.value='';
}

// --- .bas Editor ---
var editorDirty=false, editorFile='';

function openEditor(){
  document.getElementById('editorModal').classList.add('open');
  loadBasList();
}
function closeEditor(){
  if(editorDirty&&!confirm('Unsaved changes. Close anyway?'))return;
  document.getElementById('editorModal').classList.remove('open');
  editorDirty=false;
}
async function loadBasList(){
  var res=await fetch('/api/bas/list?token='+adminToken);
  var d=await res.json();
  var el=document.getElementById('basFileList');
  el.innerHTML=d.files.map(function(f){return '<div class="bf'+(f===editorFile?' sel':'')+'" onclick="loadBasFile(\\x27'+f+'\\x27)">'+f+'</div>';}).join('');
}
async function loadBasFile(fn){
  if(editorDirty&&!confirm('Unsaved changes in '+editorFile+'. Discard?'))return;
  var res=await fetch('/api/bas/read?filename='+encodeURIComponent(fn)+'&token='+adminToken);
  if(!res.ok){document.getElementById('edStatus').textContent='Error loading';return;}
  var d=await res.json();
  editorFile=fn;
  document.getElementById('basEditor').value=d.code;
  document.getElementById('edStatus').textContent='Loaded: '+fn+' ('+d.code.length+' chars)';
  editorDirty=false;
  loadBasList();
}
function onEditorChange(){editorDirty=true;document.getElementById('edStatus').textContent=editorFile+' (modified)';}
async function saveBasFile(){
  if(!editorFile){document.getElementById('edStatus').textContent='No file selected';return;}
  var code=document.getElementById('basEditor').value;
  var res=await fetch('/api/bas/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:editorFile,code:code,token:adminToken})});
  if(!res.ok){var e=await res.json();document.getElementById('edStatus').textContent='Error: '+e.detail;return;}
  editorDirty=false;
  document.getElementById('edStatus').textContent='Saved: '+editorFile;
}

init();
</script>
<div class="modal-bg" id="loginModal">
  <div style="background:#111827;border:1px solid #334155;border-radius:8px;padding:24px;width:340px">
    <h3 style="color:#60a5fa;margin-bottom:16px">Admin Login</h3>
    <input type="text" id="loginUser" placeholder="Username" style="margin-bottom:8px" onkeydown="if(event.key==='Enter')document.getElementById('loginPass').focus()">
    <input type="password" id="loginPass" placeholder="Password" style="margin-bottom:12px" onkeydown="if(event.key==='Enter')doAdminLogin()">
    <div id="loginError" style="color:#f87171;font-size:0.8em;margin-bottom:8px"></div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-p" onclick="doAdminLogin()">Login</button>
      <button class="btn btn-o" onclick="document.getElementById('loginModal').classList.remove('open')">Cancel</button>
    </div>
  </div>
</div>
<div class="modal-bg" id="editorModal">
  <div class="modal">
    <div class="modal-hdr">
      <h3>.bas Template Editor</h3>
      <button class="btn btn-o" style="padding:4px 12px;font-size:0.8em" onclick="closeEditor()">Close</button>
    </div>
    <div class="modal-body">
      <div class="modal-side" id="basFileList"></div>
      <div class="modal-edit">
        <textarea id="basEditor" placeholder="Select a .bas file to edit..." oninput="onEditorChange()"></textarea>
        <div class="modal-foot">
          <button class="btn btn-p" style="padding:5px 14px" onclick="saveBasFile()">Save</button>
          <span class="ed-status" id="edStatus">Select a file</span>
        </div>
      </div>
    </div>
  </div>
</div>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8087, log_level="info")
