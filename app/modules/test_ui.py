"""
SBS Controls — Composition Engine Test UI

Standalone web UI for testing the modular assembler.
Runs on port 8087, separate from the main DFA platform.

Usage:
    cd /srv/reliable-generator-dev
    PYTHONPATH=/srv/reliable-generator-dev python3 -m app.modules.test_ui
"""

import json
import dataclasses
from typing import List, Optional

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel

# Import assembler and registry
from app.modules import list_bases, list_modules, get_base, _MODULE_REGISTRY
from app.modules.assembler import assemble, AssemblyError
from app.modules.pan_generator import assemble_as_library_json, _to_library_format

app = FastAPI(title="SBS Composition Engine — Test UI")

# ── Feature categories for the UI ────────────────────────────────────────────
FEATURE_CATEGORIES = {
    "COOLING": ["CHW", "DX-1", "DX-2"],
    "HEATING": ["HW", "ELEC-1", "ELEC-2", "ELEC-3", "GAS-1"],
    "PREHEAT": ["PH-HW", "PH-ELEC"],
    "REHEAT": ["RH-HW", "RH-ELEC"],
    "SUPPLY FAN": ["SF-VFD", "SF-CS"],
    "RETURN/RELIEF": ["RF-VFD"],
    "ECONOMIZER": ["ECON-DB", "ECON-ENT"],
    "ENERGY RECOVERY": ["ERW"],
    "VENTILATION": ["VENT-CO2"],
    "HUMIDITY": ["HUMID-STM"],
    "SAFETY": ["FLTR-DP", "FREEZE", "SMOKE+FIRE", "COND-OVF"],
    "PRESSURE": ["DSP", "BLDG-P"],
    "VAV OPTIONS": ["FAN-PARALLEL", "RH-HW", "RH-ELEC"],
}

# Map display feature codes to actual registered feature codes
FEATURE_CODE_MAP = {
    "CHW": "CHW",
    "DX-1": "DX-1",
    "DX-2": "DX-2",
    "HW": "HW",
    "ELEC-1": "ELEC-1",
    "ELEC-2": "ELEC-2",
    "ELEC-3": "ELEC-3",
    "GAS-1": "GAS-1",
    "PH-HW": "PH-HW",
    "PH-ELEC": "PH-ELEC",
    "RH-HW": "RH-HW",
    "RH-ELEC": "RH-ELEC",
    "SF-VFD": "SF-VFD",
    "SF-CS": "SF-CS",
    "RF-VFD": "RF-VFD",
    "ECON-DB": "ECON-DB",
    "ECON-ENT": "ECON-ENT",
    "ERW": "ERW",
    "VENT-CO2": "VENT-CO2",
    "HUMID-STM": "HUMID-STM",
    "FLTR-DP": "FLTR-DP",
    "FREEZE": "FREEZE",
    "SMOKE+FIRE": "SMOKE+FIRE",
    "COND-OVF": "COND-OVF",
    "DSP": "DSP",
    "BLDG-P": "BLDG-P",
    "FAN-PARALLEL": "FAN-PARALLEL",
}


# ── Pydantic Models ──────────────────────────────────────────────────────────

class AssembleRequest(BaseModel):
    equipment_type: str
    features: List[str]


# ── Helper: serialize SelectionResult ─────────────────────────────────────────

def _serialize_controller(ctrl) -> dict:
    """Convert SelectionResult dataclass to JSON-safe dict."""
    if ctrl is None:
        return {}
    if isinstance(ctrl, dict):
        return ctrl
    try:
        return {
            "model": ctrl.controller.id,
            "name": ctrl.controller.name,
            "family": ctrl.controller.family,
            "fits": ctrl.fits,
            "ui_used": ctrl.ui_used,
            "ui_available": ctrl.ui_available,
            "uo_used": ctrl.uo_used,
            "uo_available": ctrl.uo_available,
            "bo_used": ctrl.bo_used,
            "bo_available": ctrl.bo_available,
            "bi_used": ctrl.bi_used,
            "bi_available": ctrl.bi_available,
            "ui_spare": ctrl.ui_spare,
            "uo_spare": ctrl.uo_spare,
            "expansion_needed": ctrl.expansion_needed,
            "expansion_modules": ctrl.expansion_modules,
            "notes": ctrl.notes,
            "summary": ctrl.summary(),
        }
    except Exception:
        return {"summary": str(ctrl)}


# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/equipment-types")
def api_equipment_types():
    """Return list of registered base equipment types."""
    bases = list_bases()
    result = []
    for code in bases:
        base = get_base(code)
        result.append({
            "code": code,
            "name": base.get("name", code) if base else code,
        })
    return result


@app.get("/api/features")
def api_features():
    """Return feature modules grouped by category."""
    # Build a set of all registered feature codes
    registered = set()
    for mod in _MODULE_REGISTRY.values():
        feat = mod.get("feature")
        if feat:
            registered.add(feat)

    result = {}
    for category, codes in FEATURE_CATEGORIES.items():
        items = []
        for code in codes:
            mapped = FEATURE_CODE_MAP.get(code, code)
            items.append({
                "code": code,
                "mapped_code": mapped,
                "available": mapped in registered,
            })
        result[category] = items
    return result


@app.post("/api/assemble")
def api_assemble(req: AssembleRequest):
    """Assemble equipment from base type + features."""
    try:
        # Map display codes to actual feature codes
        mapped_features = [FEATURE_CODE_MAP.get(f, f) for f in req.features]

        result = assemble(
            equipment_type=req.equipment_type,
            features=mapped_features,
            device_name="{device-name}",
        )

        # Build library JSON
        library_json = _to_library_format(result, req.equipment_type, mapped_features)

        # Serialize controller
        ctrl_data = _serialize_controller(result.get("controller"))

        return {
            "success": True,
            "equipment_type": result["equipment_type"],
            "device_name": result["device_name"],
            "modules": result["modules"],
            "point_list": result["point_list"],
            "io_map": result["io_map"],
            "io_counts": result["io_counts"],
            "controller": ctrl_data,
            "code": result["code"],
            "warnings": result["warnings"],
            "errors": result["errors"],
            "library_json": library_json,
        }
    except AssemblyError as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(e)},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Internal error: {str(e)}"},
        )


@app.get("/api/download/{equipment_type}")
def api_download(equipment_type: str, features: str = Query("")):
    """Download library JSON for the assembled configuration."""
    feature_list = [f.strip() for f in features.split(",") if f.strip()]
    mapped_features = [FEATURE_CODE_MAP.get(f, f) for f in feature_list]

    try:
        result = assemble(
            equipment_type=equipment_type,
            features=mapped_features,
            device_name="{device-name}",
        )
        library_json = _to_library_format(result, equipment_type, mapped_features)

        feat_str = "_".join(sorted(mapped_features))[:60] if mapped_features else "base"
        filename = f"{equipment_type}_{feat_str}.json"

        return Response(
            content=json.dumps(library_json, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": str(e)},
        )


# ── HTML Page ─────────────────────────────────────────────────────────────────

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SBS Composition Engine — Test UI</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: #1e1e2e;
    color: #cdd6f4;
    min-height: 100vh;
}

header {
    background: #181825;
    border-bottom: 1px solid #313244;
    padding: 12px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

header h1 {
    font-size: 18px;
    font-weight: 600;
    color: #89b4fa;
}

header .subtitle {
    font-size: 12px;
    color: #6c7086;
}

.main-layout {
    display: flex;
    height: calc(100vh - 52px);
}

/* ── Left Panel ── */
.left-panel {
    width: 320px;
    min-width: 280px;
    background: #181825;
    border-right: 1px solid #313244;
    overflow-y: auto;
    padding: 16px;
    flex-shrink: 0;
}

.left-panel h2 {
    font-size: 14px;
    color: #a6adc8;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 12px;
}

.form-group {
    margin-bottom: 16px;
}

.form-group label {
    display: block;
    font-size: 12px;
    color: #a6adc8;
    margin-bottom: 4px;
    font-weight: 500;
}

select {
    width: 100%;
    background: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 13px;
    cursor: pointer;
}

select:focus {
    outline: none;
    border-color: #89b4fa;
}

.category-group {
    margin-bottom: 12px;
}

.category-label {
    font-size: 11px;
    font-weight: 700;
    color: #585b70;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
    padding: 2px 0;
    border-bottom: 1px solid #313244;
}

.feature-checkbox {
    display: inline-flex;
    align-items: center;
    margin: 2px 4px 2px 0;
    padding: 3px 8px;
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    transition: all 0.15s;
    user-select: none;
}

.feature-checkbox:hover {
    border-color: #89b4fa;
    background: #3b3d54;
}

.feature-checkbox.checked {
    background: #1e3a5f;
    border-color: #89b4fa;
    color: #89dceb;
}

.feature-checkbox.unavailable {
    opacity: 0.35;
    cursor: not-allowed;
}

.feature-checkbox input {
    display: none;
}

.feature-checkbox .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #45475a;
    margin-right: 6px;
    transition: background 0.15s;
}

.feature-checkbox.checked .dot {
    background: #89b4fa;
}

.btn-assemble {
    width: 100%;
    padding: 10px;
    background: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    letter-spacing: 0.5px;
    transition: background 0.15s;
    margin-top: 8px;
}

.btn-assemble:hover { background: #74c7ec; }
.btn-assemble:active { background: #b4befe; }
.btn-assemble:disabled { background: #45475a; color: #6c7086; cursor: not-allowed; }

.io-preview {
    margin-top: 12px;
    padding: 10px;
    background: #11111b;
    border-radius: 6px;
    font-size: 11px;
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    color: #a6adc8;
    line-height: 1.6;
}

.io-preview .label { color: #585b70; }
.io-preview .val { color: #f9e2af; }

/* ── Right Panel ── */
.right-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.tab-bar {
    display: flex;
    background: #181825;
    border-bottom: 1px solid #313244;
    padding: 0 12px;
    flex-shrink: 0;
}

.tab-btn {
    padding: 10px 18px;
    font-size: 13px;
    color: #6c7086;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    transition: all 0.15s;
    font-weight: 500;
}

.tab-btn:hover { color: #cdd6f4; }
.tab-btn.active {
    color: #89b4fa;
    border-bottom-color: #89b4fa;
}

.tab-content {
    flex: 1;
    overflow: auto;
    padding: 16px;
}

.tab-page { display: none; }
.tab-page.active { display: block; }

/* ── Summary ── */
.summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px;
    margin-bottom: 16px;
}

.summary-card {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 8px;
    padding: 14px;
}

.summary-card .card-label {
    font-size: 11px;
    color: #585b70;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.summary-card .card-value {
    font-size: 22px;
    font-weight: 700;
    color: #89b4fa;
    margin-top: 4px;
}

.summary-card .card-sub {
    font-size: 12px;
    color: #a6adc8;
    margin-top: 2px;
}

.modules-list {
    list-style: none;
    padding: 0;
}

.modules-list li {
    padding: 4px 8px;
    font-size: 13px;
    border-left: 3px solid #313244;
    margin-bottom: 4px;
    background: #181825;
    border-radius: 0 4px 4px 0;
}

.modules-list li .order {
    display: inline-block;
    width: 28px;
    color: #585b70;
    font-family: monospace;
}

/* ── Tables ── */
.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

.data-table th {
    text-align: left;
    padding: 8px 10px;
    background: #181825;
    color: #a6adc8;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 2px solid #313244;
    position: sticky;
    top: 0;
    z-index: 1;
}

.data-table td {
    padding: 6px 10px;
    border-bottom: 1px solid #232336;
}

.data-table tr:nth-child(even) td {
    background: #1a1a2e;
}

.data-table tr:hover td {
    background: #262640;
}

.type-badge {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 700;
    font-family: monospace;
}

.type-AI { background: #1e3a5f; color: #89dceb; }
.type-AO { background: #2d4a1e; color: #a6e3a1; }
.type-AV { background: #3a2d1e; color: #f9e2af; }
.type-BI { background: #3a1e3a; color: #cba6f7; }
.type-BO { background: #3a1e1e; color: #f38ba8; }
.type-BV { background: #2d1e3a; color: #b4befe; }
.type-MO { background: #1e2d3a; color: #74c7ec; }
.type-MV { background: #1e3a2d; color: #94e2d5; }
.type-LOOP { background: #3a3a1e; color: #f9e2af; }
.type-SCHEDULE { background: #1e3a3a; color: #89dceb; }

/* ── Code Block ── */
.code-container {
    position: relative;
}

.code-toolbar {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-bottom: 6px;
}

.btn-copy {
    padding: 5px 14px;
    background: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
}

.btn-copy:hover { background: #45475a; }
.btn-copy.copied { background: #1e5a3a; border-color: #a6e3a1; color: #a6e3a1; }

pre.code-block {
    background: #11111b;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 14px;
    font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    font-size: 12px;
    line-height: 1.5;
    overflow: auto;
    max-height: calc(100vh - 180px);
    white-space: pre;
    color: #cdd6f4;
    tab-size: 4;
}

/* ── Warnings / Errors ── */
.warnings-box {
    margin-top: 12px;
    padding: 10px;
    background: #3a2d1e;
    border: 1px solid #f9e2af;
    border-radius: 6px;
    font-size: 12px;
    color: #f9e2af;
}

.error-box {
    padding: 16px;
    background: #3a1e1e;
    border: 1px solid #f38ba8;
    border-radius: 8px;
    color: #f38ba8;
    font-size: 14px;
    margin: 20px;
}

/* ── Empty State ── */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #45475a;
    font-size: 16px;
    text-align: center;
    padding: 40px;
}

.empty-state .icon {
    font-size: 48px;
    margin-bottom: 16px;
}

/* ── Loading ── */
.loading-overlay {
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(17,17,27,0.7);
    z-index: 100;
    align-items: center;
    justify-content: center;
}

.loading-overlay.show { display: flex; }

.spinner {
    width: 40px;
    height: 40px;
    border: 3px solid #313244;
    border-top-color: #89b4fa;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.btn-download {
    padding: 5px 14px;
    background: #1e5a3a;
    color: #a6e3a1;
    border: 1px solid #a6e3a1;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
}

.btn-download:hover { background: #2d6b4a; }

/* Controller card */
.ctrl-summary {
    background: #11111b;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 14px;
    font-family: monospace;
    font-size: 13px;
    white-space: pre-wrap;
    line-height: 1.6;
    color: #a6e3a1;
}

/* ── Module Breakdown ── */
.module-card {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 8px;
    margin-bottom: 16px;
    overflow: hidden;
}

.module-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    background: #11111b;
    border-bottom: 1px solid #313244;
    cursor: pointer;
    user-select: none;
}

.module-card-header:hover {
    background: #1a1a2e;
}

.module-card-header h4 {
    font-size: 14px;
    color: #89b4fa;
    font-weight: 600;
    margin: 0;
}

.module-card-header .exec-order {
    font-size: 11px;
    color: #585b70;
    font-family: monospace;
    background: #313244;
    padding: 2px 8px;
    border-radius: 3px;
}

.module-card-body {
    padding: 12px 14px;
}

.module-card-body h5 {
    font-size: 12px;
    color: #a6adc8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 8px 0 4px;
}

.module-card-body h5:first-child {
    margin-top: 0;
}

pre.module-code-block {
    background: #2a2a3e;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 12px;
    font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    font-size: 11px;
    line-height: 1.5;
    overflow: auto;
    max-height: 300px;
    white-space: pre;
    color: #cdd6f4;
    tab-size: 4;
}

/* ── Editable Code Textarea ── */
textarea.code-editor {
    background: #11111b;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 14px;
    font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    font-size: 12px;
    line-height: 1.5;
    width: 100%;
    min-height: 400px;
    max-height: calc(100vh - 220px);
    resize: vertical;
    color: #cdd6f4;
    tab-size: 4;
    outline: none;
}

textarea.code-editor:focus {
    border-color: #4a9eff;
    box-shadow: 0 0 0 1px #4a9eff33;
}

.code-edit-note {
    font-size: 11px;
    color: #585b70;
    font-style: italic;
    margin-top: 6px;
}

/* ── Inline Editable Point Inputs ── */
.pt-input {
    background: transparent;
    border: 1px solid transparent;
    color: #cdd6f4;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
    padding: 4px 6px;
    width: 100%;
    border-radius: 3px;
    outline: none;
    transition: border-color 0.15s, background 0.15s;
}

.pt-input:hover {
    border-color: #45475a;
    background: #232336;
}

.pt-input:focus {
    border-color: #4a9eff;
    background: #1a1a2e;
}

.pt-input-mono {
    font-family: monospace;
    font-size: 12px;
}

.pt-input-narrow {
    width: 60px;
    text-align: right;
}

/* ── Export Button ── */
.btn-export {
    padding: 10px 20px;
    background: #1e3a5f;
    color: #89dceb;
    border: 1px solid #89b4fa;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
    margin-top: 16px;
}

.btn-export:hover {
    background: #264a6f;
}

.export-bar {
    padding: 16px;
    border-top: 1px solid #313244;
    background: #181825;
    display: none;
    flex-shrink: 0;
}
</style>
</head>
<body>

<header>
    <div>
        <h1>SBS Composition Engine</h1>
        <div class="subtitle">Modular BACnet Controller Assembler &mdash; Test UI</div>
    </div>
    <div class="subtitle" style="text-align:right">
        Reliable Controls<br>
        Port 8087
    </div>
</header>

<div class="main-layout">
    <!-- Left Panel -->
    <div class="left-panel">
        <h2>Configuration</h2>

        <div class="form-group">
            <label>Base Equipment Type</label>
            <select id="equipmentType">
                <option value="">Loading...</option>
            </select>
        </div>

        <div id="featureGroups"></div>

        <button class="btn-assemble" id="btnAssemble" onclick="doAssemble()">ASSEMBLE</button>

        <div class="io-preview" id="ioPreview" style="display:none">
            <div><span class="label">Selected features: </span><span class="val" id="prevFeatures">-</span></div>
        </div>
    </div>

    <!-- Right Panel -->
    <div class="right-panel">
        <div class="tab-bar">
            <button class="tab-btn active" data-tab="summary">Summary</button>
            <button class="tab-btn" data-tab="modules">Modules</button>
            <button class="tab-btn" data-tab="points">Point List</button>
            <button class="tab-btn" data-tab="iomap">I/O Map</button>
            <button class="tab-btn" data-tab="code">Code</button>
            <button class="tab-btn" data-tab="library">Library JSON</button>
        </div>

        <div class="tab-content">
            <!-- Summary -->
            <div class="tab-page active" id="tab-summary">
                <div class="empty-state" id="emptyState">
                    <div class="icon">&#9881;</div>
                    <div>Select an equipment type and features, then click <strong>ASSEMBLE</strong></div>
                </div>
                <div id="summaryContent" style="display:none"></div>
            </div>

            <!-- Modules -->
            <div class="tab-page" id="tab-modules">
                <div id="modulesContent"></div>
            </div>

            <!-- Point List -->
            <div class="tab-page" id="tab-points">
                <div id="pointsContent"></div>
            </div>

            <!-- I/O Map -->
            <div class="tab-page" id="tab-iomap">
                <div id="iomapContent"></div>
            </div>

            <!-- Code -->
            <div class="tab-page" id="tab-code">
                <div id="codeContent"></div>
            </div>

            <!-- Library JSON -->
            <div class="tab-page" id="tab-library">
                <div id="libraryContent"></div>
            </div>
        </div>

        <div class="export-bar" id="exportBar">
            <button class="btn-export" onclick="exportModified()">Export Modified (JSON)</button>
        </div>
    </div>
</div>

<div class="loading-overlay" id="loading">
    <div class="spinner"></div>
</div>

<script>
let currentResult = null;

// ── Tab switching ──
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-page').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    });
});

// ── Load equipment types ──
async function loadEquipmentTypes() {
    try {
        const res = await fetch('/api/equipment-types');
        const types = await res.json();
        const sel = document.getElementById('equipmentType');
        sel.innerHTML = types.map(t =>
            `<option value="${t.code}">${t.code} &mdash; ${t.name}</option>`
        ).join('');
    } catch (e) {
        console.error('Failed to load equipment types:', e);
    }
}

// ── Load features ──
async function loadFeatures() {
    try {
        const res = await fetch('/api/features');
        const groups = await res.json();
        const container = document.getElementById('featureGroups');
        let html = '';

        for (const [category, items] of Object.entries(groups)) {
            html += `<div class="category-group">`;
            html += `<div class="category-label">${category}</div>`;
            html += `<div>`;
            for (const item of items) {
                const unavailClass = item.available ? '' : ' unavailable';
                const disabled = item.available ? '' : ' disabled';
                html += `<label class="feature-checkbox${unavailClass}" data-code="${item.code}">
                    <input type="checkbox" value="${item.code}"${disabled}>
                    <span class="dot"></span>
                    ${item.code}
                </label>`;
            }
            html += `</div></div>`;
        }

        container.innerHTML = html;

        // Toggle styling on check
        container.querySelectorAll('.feature-checkbox').forEach(label => {
            const cb = label.querySelector('input');
            if (!cb) return;
            label.addEventListener('click', (e) => {
                if (label.classList.contains('unavailable')) {
                    e.preventDefault();
                    return;
                }
            });
            cb.addEventListener('change', () => {
                label.classList.toggle('checked', cb.checked);
                updatePreview();
            });
        });
    } catch (e) {
        console.error('Failed to load features:', e);
    }
}

// ── Preview update ──
function updatePreview() {
    const selected = getSelectedFeatures();
    const preview = document.getElementById('ioPreview');
    if (selected.length === 0) {
        preview.style.display = 'none';
        return;
    }
    preview.style.display = 'block';
    document.getElementById('prevFeatures').textContent = selected.join(', ');
}

function getSelectedFeatures() {
    const checkboxes = document.querySelectorAll('#featureGroups input[type=checkbox]:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

// ── Assemble ──
async function doAssemble() {
    const equipType = document.getElementById('equipmentType').value;
    if (!equipType) return;

    const features = getSelectedFeatures();
    const btn = document.getElementById('btnAssemble');
    const loading = document.getElementById('loading');

    btn.disabled = true;
    loading.classList.add('show');

    try {
        const res = await fetch('/api/assemble', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ equipment_type: equipType, features }),
        });

        const data = await res.json();

        if (!res.ok || !data.success) {
            showError(data.error || 'Assembly failed');
            return;
        }

        currentResult = data;
        renderSummary(data);
        renderModules(data);
        renderPoints(data);
        renderIOMap(data);
        renderCode(data);
        renderLibrary(data);
        document.getElementById('exportBar').style.display = 'block';

    } catch (e) {
        showError('Network error: ' + e.message);
    } finally {
        btn.disabled = false;
        loading.classList.remove('show');
    }
}

function showError(msg) {
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('summaryContent').style.display = 'block';
    document.getElementById('summaryContent').innerHTML =
        `<div class="error-box">${escapeHtml(msg)}</div>`;
    // Switch to summary tab
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-page').forEach(p => p.classList.remove('active'));
    document.querySelector('[data-tab="summary"]').classList.add('active');
    document.getElementById('tab-summary').classList.add('active');
}

// ── Render: Summary ──
function renderSummary(data) {
    document.getElementById('emptyState').style.display = 'none';
    const el = document.getElementById('summaryContent');
    el.style.display = 'block';

    const io = data.io_counts || {};
    const ctrl = data.controller || {};

    let html = `<div class="summary-grid">`;
    html += summaryCard('Equipment', data.equipment_type, '');
    html += summaryCard('Controller', ctrl.model || 'N/A', ctrl.name || '');
    html += summaryCard('Total Points', String(io.total_points || 0),
        `Physical: ${io.total_physical || 0} | Software: ${io.total_software || 0}`);
    html += summaryCard('Modules', String((data.modules || []).length), '');
    html += summaryCard('Analog In', String(io.num_ai || 0), '');
    html += summaryCard('Analog Out', String(io.num_ao || 0), '');
    html += summaryCard('Digital In', String(io.num_di || 0), '');
    html += summaryCard('Digital Out', String(io.num_do || 0), '');
    html += `</div>`;

    // Controller detail
    if (ctrl.summary) {
        html += `<h3 style="color:#a6adc8;font-size:13px;margin:12px 0 6px">Controller Selection</h3>`;
        html += `<div class="ctrl-summary">${escapeHtml(ctrl.summary)}</div>`;
    }

    // Modules list
    html += `<h3 style="color:#a6adc8;font-size:13px;margin:16px 0 6px">Loaded Modules (${(data.modules||[]).length})</h3>`;
    html += `<ul class="modules-list">`;
    for (const mod of (data.modules || [])) {
        html += `<li><span class="order">[${mod.exec_order}]</span> <strong>${mod.id}</strong> &mdash; ${mod.name}</li>`;
    }
    html += `</ul>`;

    // Warnings
    if (data.warnings && data.warnings.length > 0) {
        html += `<div class="warnings-box"><strong>Warnings (${data.warnings.length})</strong><br>`;
        for (const w of data.warnings) {
            html += `&#x26A0; ${escapeHtml(w)}<br>`;
        }
        html += `</div>`;
    }

    el.innerHTML = html;
}

function summaryCard(label, value, sub) {
    return `<div class="summary-card">
        <div class="card-label">${label}</div>
        <div class="card-value">${escapeHtml(value)}</div>
        ${sub ? `<div class="card-sub">${escapeHtml(sub)}</div>` : ''}
    </div>`;
}

// ── Render: Point List (inline editable) ──
function renderPoints(data) {
    const pts = data.point_list || [];
    let html = `<table class="data-table">
        <thead><tr>
            <th>Type</th><th>Instance</th><th>Name</th><th>Description</th>
            <th>Min</th><th>Max</th><th>Default</th><th>Units</th><th>Source Module</th>
        </tr></thead><tbody>`;

    const counters = {};
    for (let i = 0; i < pts.length; i++) {
        const pt = pts[i];
        if (!counters[pt.type]) counters[pt.type] = 0;
        counters[pt.type]++;
        const inst = counters[pt.type];
        html += `<tr>
            <td><span class="type-badge type-${pt.type}">${pt.type}</span></td>
            <td>${inst}</td>
            <td><input class="pt-input pt-input-mono" data-idx="${i}" data-field="name" value="${escapeAttr(pt.name)}"></td>
            <td><input class="pt-input" data-idx="${i}" data-field="desc" value="${escapeAttr(pt.desc || '')}"></td>
            <td><input class="pt-input pt-input-narrow" data-idx="${i}" data-field="min" value="${pt.min != null ? pt.min : ''}"></td>
            <td><input class="pt-input pt-input-narrow" data-idx="${i}" data-field="max" value="${pt.max != null ? pt.max : ''}"></td>
            <td><input class="pt-input pt-input-narrow" data-idx="${i}" data-field="default" value="${pt.default_value != null ? pt.default_value : ''}"></td>
            <td><input class="pt-input" data-idx="${i}" data-field="units" value="${escapeAttr(pt.units || '')}" style="width:80px"></td>
            <td style="font-size:11px;color:#585b70">${escapeHtml(pt.source_module || '')}</td>
        </tr>`;
    }

    html += `</tbody></table>`;
    document.getElementById('pointsContent').innerHTML = html;
}

// ── Render: I/O Map ──
function renderIOMap(data) {
    const ioMap = data.io_map || {};
    const entries = Object.entries(ioMap).sort(([a], [b]) => a.localeCompare(b));

    if (entries.length === 0) {
        document.getElementById('iomapContent').innerHTML =
            '<div style="color:#585b70;padding:20px">No I/O terminal mappings defined.</div>';
        return;
    }

    let html = `<table class="data-table">
        <thead><tr><th>Terminal</th><th>Point Name</th></tr></thead><tbody>`;

    for (const [terminal, point] of entries) {
        html += `<tr>
            <td style="font-family:monospace;font-weight:700">${escapeHtml(terminal)}</td>
            <td style="font-family:monospace">${escapeHtml(point)}</td>
        </tr>`;
    }

    html += `</tbody></table>`;
    document.getElementById('iomapContent').innerHTML = html;
}

// ── Render: Code (editable textarea) ──
function renderCode(data) {
    const code = data.code || '';
    if (!code.trim()) {
        document.getElementById('codeContent').innerHTML =
            '<div style="color:#585b70;padding:20px">No code generated.</div>';
        return;
    }

    const lineCount = code.trim().split('\\n').length;
    let html = `<div class="code-container">
        <div class="code-toolbar">
            <span style="color:#585b70;font-size:12px">${lineCount} lines</span>
            <button class="btn-copy" onclick="copyCode()">Copy to Clipboard</button>
        </div>
        <textarea class="code-editor" id="codeEditor">${escapeHtml(code)}</textarea>
        <div class="code-edit-note">Edits here are for review only &mdash; to permanently change code, modify the module file</div>
    </div>`;

    document.getElementById('codeContent').innerHTML = html;
}

function copyCode() {
    const editor = document.getElementById('codeEditor');
    const code = editor ? editor.value : (currentResult?.code || '');
    navigator.clipboard.writeText(code).then(() => {
        const btn = document.querySelector('.btn-copy');
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        setTimeout(() => {
            btn.textContent = 'Copy to Clipboard';
            btn.classList.remove('copied');
        }, 2000);
    });
}

// ── Render: Library JSON ──
function renderLibrary(data) {
    const lib = data.library_json || {};
    const jsonStr = JSON.stringify(lib, null, 2);
    const equipType = data.equipment_type || '';
    const features = getSelectedFeatures().join(',');

    let html = `<div class="code-container">
        <div class="code-toolbar">
            <button class="btn-copy" onclick="copyLibrary()">Copy JSON</button>
            <button class="btn-download" onclick="downloadLibrary()">Download JSON</button>
        </div>
        <pre class="code-block" id="libraryBlock">${escapeHtml(jsonStr)}</pre>
    </div>`;

    document.getElementById('libraryContent').innerHTML = html;
}

function copyLibrary() {
    const lib = currentResult?.library_json || {};
    const jsonStr = JSON.stringify(lib, null, 2);
    navigator.clipboard.writeText(jsonStr).then(() => {
        const btns = document.querySelectorAll('#libraryContent .btn-copy');
        if (btns.length) {
            btns[0].textContent = 'Copied!';
            btns[0].classList.add('copied');
            setTimeout(() => {
                btns[0].textContent = 'Copy JSON';
                btns[0].classList.remove('copied');
            }, 2000);
        }
    });
}

function downloadLibrary() {
    if (!currentResult) return;
    const equipType = currentResult.equipment_type || 'unknown';
    const features = getSelectedFeatures().join(',');
    window.open(`/api/download/${equipType}?features=${encodeURIComponent(features)}`, '_blank');
}

// ── Render: Modules Breakdown ──
function renderModules(data) {
    const mods = data.modules || [];
    if (mods.length === 0) {
        document.getElementById('modulesContent').innerHTML =
            '<div style="color:#585b70;padding:20px">No modules loaded.</div>';
        return;
    }

    let html = '';
    for (const mod of mods) {
        html += `<div class="module-card">`;
        html += `<div class="module-card-header" onclick="this.parentElement.querySelector('.module-card-body').style.display = this.parentElement.querySelector('.module-card-body').style.display === 'none' ? 'block' : 'none'">`;
        html += `<h4>${escapeHtml(mod.id)} &mdash; ${escapeHtml(mod.name)}</h4>`;
        html += `<span class="exec-order">exec_order: ${mod.exec_order}</span>`;
        html += `</div>`;
        html += `<div class="module-card-body">`;

        // Points contributed by this module
        const objects = mod.objects || {};
        const objTypes = Object.keys(objects);
        if (objTypes.length > 0) {
            html += `<h5>Points (${objTypes.reduce((s, t) => s + (objects[t] || []).length, 0)})</h5>`;
            html += `<table class="data-table" style="margin-bottom:12px"><thead><tr><th>Type</th><th>Name</th><th>Description</th></tr></thead><tbody>`;
            for (const objType of objTypes) {
                for (const obj of (objects[objType] || [])) {
                    html += `<tr>
                        <td><span class="type-badge type-${objType}">${objType}</span></td>
                        <td style="font-family:monospace;font-size:12px">${escapeHtml(obj.name)}</td>
                        <td>${escapeHtml(obj.desc || '')}</td>
                    </tr>`;
                }
            }
            html += `</tbody></table>`;
        } else {
            html += `<h5>Points</h5><div style="color:#585b70;font-size:12px;margin-bottom:8px">No points in this module</div>`;
        }

        // Code block
        if (mod.code && mod.code.trim()) {
            html += `<h5>BASIC Code</h5>`;
            html += `<pre class="module-code-block">${escapeHtml(mod.code)}</pre>`;
        }

        html += `</div></div>`;
    }

    document.getElementById('modulesContent').innerHTML = html;
}

// ── Export Modified ──
function exportModified() {
    if (!currentResult) return;

    // Gather current code from textarea
    const editor = document.getElementById('codeEditor');
    const modifiedCode = editor ? editor.value : (currentResult.code || '');

    // Gather modified point data from inputs
    const pts = currentResult.point_list || [];
    const modifiedPoints = pts.map((pt, i) => {
        const getVal = (field) => {
            const inp = document.querySelector(`.pt-input[data-idx="${i}"][data-field="${field}"]`);
            return inp ? inp.value : '';
        };
        return {
            type: pt.type,
            name: getVal('name') || pt.name,
            desc: getVal('desc') || pt.desc || '',
            min: getVal('min') || null,
            max: getVal('max') || null,
            default: getVal('default') || null,
            units: getVal('units') || pt.units || '',
            source_module: pt.source_module || '',
        };
    });

    const exportData = {
        equipment_type: currentResult.equipment_type,
        device_name: currentResult.device_name,
        modules: (currentResult.modules || []).map(m => ({ id: m.id, name: m.name, exec_order: m.exec_order })),
        code: modifiedCode,
        point_list: modifiedPoints,
        io_map: currentResult.io_map || {},
        io_counts: currentResult.io_counts || {},
        controller: currentResult.controller || {},
        exported_at: new Date().toISOString(),
        modified: true,
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const equipType = currentResult.equipment_type || 'unknown';
    a.download = `${equipType}_modified_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ── Utility ──
function escapeHtml(str) {
    if (typeof str !== 'string') str = String(str);
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function escapeAttr(str) {
    if (typeof str !== 'string') str = String(str);
    return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ── Init ──
loadEquipmentTypes();
loadFeatures();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def serve_ui():
    return HTML_PAGE


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("  SBS Composition Engine — Test UI")
    print("  http://0.0.0.0:8087")
    print("=" * 60)
    uvicorn.run(
        "app.modules.test_ui:app",
        host="0.0.0.0",
        port=8087,
        reload=False,
        log_level="info",
    )
