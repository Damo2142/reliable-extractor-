"""
SBS Composition Engine v2 — FastAPI Standalone Server

Standalone web server for the composition engine UI.
Runs on port 8087 (separate from DFA platform and composer).

Endpoints:
  GET  /                    - UI (HTML)
  GET  /api/modules         - List all available modules by category
  GET  /api/modules/{id}    - Get module details
  GET  /api/standards       - List standard configurations
  POST /api/assemble        - Assemble a configuration
  POST /api/generate        - Generate Excel + .bas package (returns zip)
"""

import sys
import os
import io
import json
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from composition.assembler import assemble
from composition.excel_gen import generate_excel
from composition.program_loader import inject_program_code
from composition.module_registry import (
    list_modules, list_by_category, get_module, STANDARD_CONFIGS
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
    device_name: str = "{device-name}"
    parent_name: str = "{parent}"
    equipment_family: str = "AHU-VAV"


class GenerateRequest(BaseModel):
    modules: List[str]
    device_name: str = "{device-name}"
    parent_name: str = "{parent}"
    equipment_family: str = "AHU-VAV"


# --- API Endpoints ---

@app.get("/api/modules")
async def api_list_modules():
    """List all modules grouped by category."""
    return list_by_category()


@app.get("/api/modules/{module_id}")
async def api_get_module(module_id: str):
    """Get detailed module info."""
    try:
        mod = get_module(module_id)
    except ValueError:
        raise HTTPException(404, f"Module not found: {module_id}")
    return {
        "id": mod.id,
        "name": mod.name,
        "category": mod.category,
        "description": mod.description,
        "is_core": mod.is_core,
        "requires": mod.requires,
        "conflicts": mod.conflicts,
        "mutually_exclusive_group": mod.mutually_exclusive_group,
        "inputs": len(mod.inputs),
        "outputs": len(mod.outputs),
        "values": len(mod.values),
        "loops": len(mod.loops),
        "programs": len(mod.programs),
        "soo_paragraph": mod.soo_paragraph,
    }


@app.get("/api/standards")
async def api_list_standards():
    """List standard configurations."""
    return STANDARD_CONFIGS


@app.post("/api/assemble")
async def api_assemble(req: AssembleRequest):
    """Assemble a configuration from selected modules."""
    try:
        config = assemble(req.modules, req.device_name, req.parent_name, req.equipment_family)
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
            "inputs": len(config.inputs),
            "outputs": len(config.outputs),
            "values": len(config.values),
            "loops": len(config.loops),
            "tables": len(config.tables),
            "programs": len(config.programs),
            "schedules": len(config.schedules),
            "trends": len(config.trends),
            "system_groups": len(config.system_groups),
        },
        "inputs": [{"row": p.row, "name": p.name, "type": p.point_type, "desc": p.description, "module": p.module} for p in config.inputs],
        "outputs": [{"row": p.row, "name": p.name, "type": p.point_type, "desc": p.description, "module": p.module, "reverse": p.reverse} for p in config.outputs],
        "programs": [{"instance": p.instance, "name": p.name, "filename": p.filename, "enabled": p.enabled, "desc": p.description} for p in sorted(config.programs, key=lambda x: x.exec_order)],
        "soo": config.soo_document,
    }


@app.post("/api/generate")
async def api_generate(req: GenerateRequest):
    """Generate Excel + .bas zip package."""
    try:
        config = assemble(req.modules, req.device_name, req.parent_name, req.equipment_family)
        inject_program_code(config)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Generate Excel
    excel_data = generate_excel(config)

    # Create zip with Excel + .bas files + SOO
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Excel workbook
        fname = f"{config.device_name}-RC-Studio.xlsx" if config.device_name != "{device-name}" else "RC-Studio-Output.xlsx"
        zf.writestr(fname, excel_data)

        # .bas program files
        for prg in config.programs:
            code = prg.code or ""
            if config.device_name != "{device-name}":
                code = code.replace("{device-name}", config.device_name)
            if config.parent_name != "{parent}":
                code = code.replace("{parent}", config.parent_name)
            zf.writestr(f"programs/{prg.filename}", code)

        # SOO document
        zf.writestr("SOO.txt", config.soo_document)

        # Summary JSON
        summary = {
            "modules": config.selected_modules,
            "controller": config.controller_model,
            "expansion": f"{config.expansion_count}x {config.expansion_model}" if config.expansion_count else "none",
            "inputs": len(config.inputs),
            "outputs": len(config.outputs),
            "values": len(config.values),
            "loops": len(config.loops),
            "programs": len(config.programs),
        }
        zf.writestr("summary.json", json.dumps(summary, indent=2))

    zip_buf.seek(0)
    filename = f"{config.device_name}-package.zip" if config.device_name != "{device-name}" else "composition-package.zip"
    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# --- UI ---

@app.get("/", response_class=HTMLResponse)
async def ui():
    """Standalone composition UI."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SBS Composition Engine v2</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0e17; color: #e0e6ed; }
  .header { background: linear-gradient(135deg, #1a237e, #0d47a1); padding: 20px 30px; display: flex; justify-content: space-between; align-items: center; }
  .header h1 { font-size: 1.4em; font-weight: 600; }
  .header .subtitle { color: #90caf9; font-size: 0.85em; }
  .container { display: grid; grid-template-columns: 340px 1fr; gap: 0; height: calc(100vh - 70px); }
  .sidebar { background: #111827; border-right: 1px solid #1e293b; overflow-y: auto; padding: 16px; }
  .main { overflow-y: auto; padding: 20px 24px; }
  .section { margin-bottom: 16px; }
  .section-title { font-size: 0.75em; text-transform: uppercase; letter-spacing: 1px; color: #64748b; margin-bottom: 8px; font-weight: 600; }
  .module-group { margin-bottom: 12px; }
  .module-group-title { font-size: 0.85em; color: #94a3b8; margin-bottom: 4px; font-weight: 500; cursor: pointer; }
  .module-item { display: flex; align-items: center; gap: 8px; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.82em; }
  .module-item:hover { background: #1e293b; }
  .module-item.selected { background: #1e3a5f; color: #60a5fa; }
  .module-item.core { opacity: 0.6; }
  .module-item input[type="checkbox"] { accent-color: #3b82f6; }
  .btn { padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9em; font-weight: 600; }
  .btn-primary { background: #2563eb; color: white; }
  .btn-primary:hover { background: #1d4ed8; }
  .btn-success { background: #059669; color: white; }
  .btn-success:hover { background: #047857; }
  .btn-group { display: flex; gap: 8px; margin: 16px 0; }
  .input-row { display: flex; gap: 8px; margin-bottom: 12px; }
  .input-row label { font-size: 0.8em; color: #94a3b8; min-width: 100px; }
  .input-row input, .input-row select { background: #1e293b; border: 1px solid #334155; color: #e0e6ed; padding: 6px 10px; border-radius: 4px; flex: 1; font-size: 0.85em; }
  .results { background: #111827; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; margin-top: 12px; }
  .results h3 { color: #60a5fa; margin-bottom: 8px; font-size: 1em; }
  .stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; margin: 12px 0; }
  .stat { background: #1e293b; padding: 10px; border-radius: 6px; text-align: center; }
  .stat .value { font-size: 1.5em; font-weight: 700; color: #60a5fa; }
  .stat .label { font-size: 0.75em; color: #94a3b8; }
  table { width: 100%; border-collapse: collapse; font-size: 0.82em; }
  th { background: #1e293b; padding: 8px; text-align: left; color: #94a3b8; font-weight: 500; }
  td { padding: 6px 8px; border-bottom: 1px solid #1e293b; }
  tr.unused td { color: #475569; font-style: italic; }
  .tag { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 0.75em; font-weight: 600; }
  .tag-ai { background: #1e3a5f; color: #60a5fa; }
  .tag-bi { background: #1a3636; color: #5eead4; }
  .tag-ao { background: #3b1f1f; color: #fca5a5; }
  .tag-bo { background: #3b2f1f; color: #fbbf24; }
  .soo-text { white-space: pre-wrap; font-family: 'Courier New', monospace; font-size: 0.8em; line-height: 1.5; background: #0f172a; padding: 16px; border-radius: 6px; max-height: 400px; overflow-y: auto; }
  .standard-card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px; cursor: pointer; }
  .standard-card:hover { border-color: #3b82f6; }
  .standard-card h4 { color: #e0e6ed; font-size: 0.9em; }
  .standard-card p { color: #94a3b8; font-size: 0.8em; margin-top: 4px; }
  #status { padding: 8px 12px; background: #1e293b; border-radius: 4px; font-size: 0.8em; color: #94a3b8; margin-top: 8px; }
  .tab-bar { display: flex; gap: 4px; margin-bottom: 12px; border-bottom: 1px solid #1e293b; padding-bottom: 8px; flex-wrap: wrap; }
  .tab { padding: 6px 14px; border-radius: 4px 4px 0 0; cursor: pointer; font-size: 0.82em; color: #94a3b8; }
  .tab.active { background: #1e293b; color: #60a5fa; font-weight: 600; }
  .tab:hover { color: #e0e6ed; }
  .tab-content { display: none; }
  .tab-content.active { display: block; }
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>SBS Composition Engine v2</h1>
    <div class="subtitle">Vendor-Neutral HVAC Modules + Reliable Controls Output</div>
  </div>
  <div style="display:flex;gap:8px">
    <button class="btn btn-primary" onclick="doAssemble()">Assemble</button>
    <button class="btn btn-success" onclick="doGenerate()">Download Package</button>
  </div>
</div>
<div class="container">
  <div class="sidebar">
    <div class="section">
      <div class="section-title">Device Configuration</div>
      <div class="input-row"><label>Device Name</label><input id="deviceName" value="{device-name}" /></div>
      <div class="input-row"><label>Parent</label><input id="parentName" value="{parent}" /></div>
    </div>
    <div class="section">
      <div class="section-title">Standard Configs</div>
      <div id="standards"></div>
    </div>
    <div class="section">
      <div class="section-title">Module Selection</div>
      <div id="moduleList"></div>
    </div>
  </div>
  <div class="main">
    <div id="status">Select modules or a standard config, then click Assemble.</div>
    <div id="results" style="display:none">
      <div class="stat-grid" id="stats"></div>
      <div class="tab-bar" id="tabBar"></div>
      <div id="tabContents"></div>
    </div>
  </div>
</div>
<script>
let modules = {};
let selected = new Set();
let assemblyResult = null;

async function init() {
  const [mods, stds] = await Promise.all([
    fetch('/api/modules').then(r=>r.json()),
    fetch('/api/standards').then(r=>r.json()),
  ]);
  modules = mods;
  renderModules(mods);
  renderStandards(stds);
}

function renderModules(byCategory) {
  const el = document.getElementById('moduleList');
  let html = '';
  for (const [cat, mods] of Object.entries(byCategory).sort()) {
    html += `<div class="module-group"><div class="module-group-title">${cat.toUpperCase()} (${mods.length})</div>`;
    for (const m of mods) {
      const isCore = m.is_core;
      const checked = isCore || selected.has(m.id) ? 'checked' : '';
      const cls = isCore ? 'module-item core' : 'module-item';
      html += `<div class="${cls}${selected.has(m.id)?' selected':''}">
        <input type="checkbox" ${checked} ${isCore?'disabled':''} onchange="toggleModule('${m.id}',this.checked)" />
        <span>${m.name}</span></div>`;
    }
    html += '</div>';
  }
  el.innerHTML = html;
}

function renderStandards(stds) {
  const el = document.getElementById('standards');
  let html = '';
  for (const [id, cfg] of Object.entries(stds)) {
    html += `<div class="standard-card" onclick="selectStandard('${id}')">
      <h4>${cfg.name}</h4><p>${cfg.description}</p></div>`;
  }
  el.innerHTML = html;
}

function toggleModule(id, on) {
  if (on) selected.add(id); else selected.delete(id);
  renderModules(modules);
}

async function selectStandard(id) {
  const stds = await fetch('/api/standards').then(r=>r.json());
  const cfg = stds[id];
  selected = new Set(cfg.modules);
  renderModules(modules);
  document.getElementById('status').textContent = `Loaded: ${cfg.name}`;
}

async function doAssemble() {
  const mods = [...selected];
  // Add core modules
  for (const [cat, ms] of Object.entries(modules)) {
    for (const m of ms) { if (m.is_core) mods.push(m.id); }
  }
  const body = {
    modules: [...new Set(mods)],
    device_name: document.getElementById('deviceName').value,
    parent_name: document.getElementById('parentName').value,
  };
  document.getElementById('status').textContent = 'Assembling...';
  try {
    const res = await fetch('/api/assemble', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail); }
    assemblyResult = await res.json();
    renderResults(assemblyResult);
    document.getElementById('status').textContent = `Assembled: ${assemblyResult.modules.length} modules, ${assemblyResult.controller.model} + ${assemblyResult.controller.expansion_count}x expansion`;
  } catch(e) { document.getElementById('status').textContent = 'Error: ' + e.message; }
}

function renderResults(r) {
  document.getElementById('results').style.display = 'block';
  // Stats
  const c = r.counts;
  const ctrl = r.controller;
  document.getElementById('stats').innerHTML = `
    <div class="stat"><div class="value">${ctrl.model}</div><div class="label">Controller</div></div>
    <div class="stat"><div class="value">${ctrl.expansion_count}</div><div class="label">Expansion Boards</div></div>
    <div class="stat"><div class="value">${c.inputs}</div><div class="label">Inputs</div></div>
    <div class="stat"><div class="value">${c.outputs}</div><div class="label">Outputs</div></div>
    <div class="stat"><div class="value">${c.values}</div><div class="label">Values</div></div>
    <div class="stat"><div class="value">${c.loops}</div><div class="label">PID Loops</div></div>
    <div class="stat"><div class="value">${c.programs}</div><div class="label">Programs</div></div>
    <div class="stat"><div class="value">${c.trends}</div><div class="label">Trends</div></div>
  `;
  // Tabs
  const tabs = ['Inputs','Outputs','Programs','SOO'];
  document.getElementById('tabBar').innerHTML = tabs.map((t,i) =>
    `<div class="tab${i===0?' active':''}" onclick="showTab(${i})">${t}</div>`).join('');
  let tc = '';
  // Inputs
  tc += `<div class="tab-content active" id="tab0"><table><tr><th>Row</th><th>Type</th><th>Name</th><th>Description</th><th>Module</th></tr>`;
  for (let row=1; row<=ctrl.highest_input_row; row++) {
    const pt = r.inputs.find(p=>p.row===row);
    if (pt) { tc += `<tr><td>${row}</td><td><span class="tag tag-${pt.type.toLowerCase()}">${pt.type}</span></td><td>${pt.name}</td><td>${pt.desc}</td><td>${pt.module}</td></tr>`; }
    else { tc += `<tr class="unused"><td>${row}</td><td></td><td>--- unused ---</td><td></td><td></td></tr>`; }
  }
  tc += '</table></div>';
  // Outputs
  tc += `<div class="tab-content" id="tab1"><table><tr><th>Row</th><th>Type</th><th>Name</th><th>Description</th><th>Module</th></tr>`;
  for (let row=1; row<=ctrl.highest_output_row; row++) {
    const pt = r.outputs.find(p=>p.row===row);
    if (pt) { tc += `<tr><td>${row}</td><td><span class="tag tag-${pt.type.toLowerCase()}">${pt.type}</span></td><td>${pt.name}${pt.reverse?' (REV)':''}</td><td>${pt.desc}</td><td>${pt.module}</td></tr>`; }
    else { tc += `<tr class="unused"><td>${row}</td><td></td><td>--- unused ---</td><td></td><td></td></tr>`; }
  }
  tc += '</table></div>';
  // Programs
  tc += `<div class="tab-content" id="tab2"><table><tr><th>PRG#</th><th>Name</th><th>Filename</th><th>Enabled</th><th>Description</th></tr>`;
  for (const p of r.programs) { tc += `<tr><td>PRG${p.instance}</td><td>${p.name}</td><td>${p.filename}</td><td>${p.enabled?'Yes':'No'}</td><td>${p.desc}</td></tr>`; }
  tc += '</table></div>';
  // SOO
  tc += `<div class="tab-content" id="tab3"><div class="soo-text">${r.soo.replace(/</g,'&lt;')}</div></div>`;
  document.getElementById('tabContents').innerHTML = tc;
}

function showTab(i) {
  document.querySelectorAll('.tab').forEach((t,j) => t.classList.toggle('active',j===i));
  document.querySelectorAll('.tab-content').forEach((t,j) => t.classList.toggle('active',j===i));
}

async function doGenerate() {
  const mods = [...selected];
  for (const [cat, ms] of Object.entries(modules)) {
    for (const m of ms) { if (m.is_core) mods.push(m.id); }
  }
  const body = {
    modules: [...new Set(mods)],
    device_name: document.getElementById('deviceName').value,
    parent_name: document.getElementById('parentName').value,
  };
  document.getElementById('status').textContent = 'Generating package...';
  const res = await fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  if (!res.ok) { document.getElementById('status').textContent = 'Error generating'; return; }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'composition-package.zip'; a.click();
  document.getElementById('status').textContent = 'Package downloaded!';
}

init();
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8087, log_level="info")
