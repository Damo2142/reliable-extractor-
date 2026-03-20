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

from fastapi import FastAPI, HTTPException
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
        },
        "inputs": [{"row": p.row, "name": p.name, "type": p.point_type, "desc": p.description, "units": p.units, "range": p.range_code, "module": p.module} for p in config.inputs],
        "outputs": [{"row": p.row, "name": p.name, "type": p.point_type, "desc": p.description, "module": p.module, "reverse": p.reverse, "min_v": p.min_v, "max_v": p.max_v} for p in config.outputs],
        "values": [{"instance": v.instance, "name": v.name, "type": v.point_type, "default": str(v.default), "units": v.units, "desc": v.description, "module": v.module} for v in config.values],
        "loops": [{"instance": l.instance, "name": l.name, "input": l.input_ref, "setpoint": l.setpoint_ref, "p": l.p_band, "i": l.integral, "action": l.action, "desc": l.description} for l in config.loops],
        "programs": [{"instance": p.instance, "name": p.name, "filename": p.filename, "enabled": p.enabled, "desc": p.description, "has_code": bool(p.code and len(p.code) > 50), "code": p.code or ""} for p in sorted(config.programs, key=lambda x: x.exec_order)],
        "soo": config.soo_document,
    }


@app.post("/api/generate")
async def api_generate(req: GenerateRequest):
    try:
        config = assemble(req.modules, controller_model=req.controller_model)
        inject_program_code(config)
    except ValueError as e:
        raise HTTPException(400, str(e))

    excel_data = generate_excel(config)
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
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
</style>
</head>
<body>
<div class="hdr">
  <div><h1>SBS Composition Engine v2</h1><div class="sub">Reliable Controls Output Tool</div></div>
  <div class="btn-grp">
    <button class="btn btn-p" onclick="doAssemble()">Assemble</button>
    <button class="btn btn-s" onclick="doGenerate()">Download Package</button>
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
  document.getElementById('status').textContent=ctrl.model+(ctrl.expansion_count?' + '+exp:'')+' | '+r.modules.length+' modules | '+c.inputs+' inputs, '+c.outputs+' outputs, '+c.programs+' programs';

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

  // Values
  tc+='<div class="tp" id="t2"><table><tr><th>Instance</th><th>Type</th><th>Name</th><th>Default</th><th>Units</th><th>Description</th><th>Module</th></tr>';
  for(const v of r.values){
    const pre={AV:'AV',BV:'BV',MV:'MV'}[v.type]||'AV';
    tc+='<tr><td>'+pre+v.instance+'</td><td><span class="tag tag-'+v.type.toLowerCase()+'">'+v.type+'</span></td><td>{device-name}-'+v.name+'</td><td>'+v.default+'</td><td>'+(v.units||'')+'</td><td>'+v.desc+'</td><td>'+v.module+'</td></tr>';
  }
  tc+='</table></div>';

  // Loops
  tc+='<div class="tp" id="t3"><table><tr><th>Loop</th><th>Name</th><th>Input</th><th>Setpoint</th><th>Action</th><th>P Band</th><th>Integral</th><th>Description</th></tr>';
  for(const l of r.loops){
    tc+='<tr><td>LOOP'+l.instance+'</td><td>'+l.name+'</td><td>{device-name}-'+l.input+'</td><td>{device-name}-'+l.setpoint+'</td><td>'+(l.action==='direct'?'+':'-')+'</td><td>'+l.p+'</td><td>'+l.i+'</td><td>'+l.desc+'</td></tr>';
  }
  tc+='</table></div>';

  // Programs
  window._programs=r.programs;
  tc+='<div class="tp" id="t4"><table><tr><th>PRG#</th><th>Name</th><th>Filename</th><th>Enabled</th><th>Status</th><th>Description</th><th>View</th></tr>';
  for(var pi=0;pi<r.programs.length;pi++){
    var p=r.programs[pi];
    tc+='<tr><td>PRG'+p.instance+'</td><td>{device-name}-'+p.name+'</td><td>'+p.filename+'</td><td>'+(p.enabled?'Yes':'No')+'</td><td>'+(p.has_code?'OK':'STUB')+'</td><td>'+p.desc+'</td>';
    tc+='<td><button class="btn btn-p" style="padding:3px 10px;font-size:0.75em" onclick="viewProgram('+pi+')">View</button></td></tr>';
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

init();
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8087, log_level="info")
