"""
Reliable Controls Extraction Tool
FastAPI backend — serves the web UI and REST API for DFA integration
"""

import asyncio
import json
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Optional
import logging

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.extractor import ExtractionEngine
from app.composer import Composer
from app.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Reliable Controls Extraction Tool",
    description="BAS programming library extractor and viewer for Reliable Controls .panx/.pan files",
    version="1.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

cfg = Config()
engine = ExtractionEngine(cfg)
composer = Composer(cfg)

# In-memory job state
jobs: dict[str, dict] = {}


# ─── Static Files & UI ────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = Path(__file__).parent.parent / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text())


# ─── Variant Discovery ────────────────────────────────────────────────────────

@app.get("/api/variants")
async def list_variants():
    """List all discovered variants grouped by category."""
    return engine.discover_variants()


@app.get("/api/variants/{category}/{variant_id}")
async def get_variant(category: str, variant_id: str):
    """Get full extracted data for a single variant."""
    data = engine.load_library_entry(category, variant_id)
    if data is None:
        raise HTTPException(404, f"Variant {variant_id} not yet processed or not found")
    return data


# ─── Processing ───────────────────────────────────────────────────────────────

@app.post("/api/process")
async def process_all(background_tasks: BackgroundTasks, category: Optional[str] = Query(None)):
    """Trigger extraction pipeline. Optionally filter by category."""
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "queued", "progress": 0, "total": 0, "current": "", "errors": [], "done": []}
    background_tasks.add_task(run_extraction, job_id, category, None)
    return {"job_id": job_id, "message": "Extraction started"}


@app.post("/api/process/selected")
async def process_selected(background_tasks: BackgroundTasks, body: dict = None):
    """Process specific variants. Body: { "variants": ["VAV/VAV-IS10001", "RTU/RTU-ISA11110E", ...] }"""
    if not body or "variants" not in body:
        raise HTTPException(400, "Must provide 'variants' list")
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "queued", "progress": 0, "total": 0, "current": "", "errors": [], "done": []}
    background_tasks.add_task(run_extraction, job_id, None, body["variants"])
    return {"job_id": job_id, "message": f"Processing {len(body['variants'])} variants"}


@app.get("/api/process/{job_id}/status")
async def job_status(job_id: str):
    """Poll extraction job status."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]


@app.get("/api/process/{job_id}/stream")
async def job_stream(job_id: str):
    """SSE stream of job progress events."""
    async def event_gen():
        last_progress = -1
        for _ in range(3600):  # max 1hr
            job = jobs.get(job_id, {})
            if job.get("progress") != last_progress or job.get("status") in ("done", "error"):
                last_progress = job.get("progress", 0)
                yield f"data: {json.dumps(job)}\n\n"
            if job.get("status") in ("done", "error"):
                break
            await asyncio.sleep(1)
        yield "data: {\"status\":\"timeout\"}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# ─── Library ──────────────────────────────────────────────────────────────────

@app.get("/api/library")
async def library_summary():
    """Summary of all processed variants with object counts — main dashboard feed."""
    return engine.library_summary()


@app.get("/api/library/compare")
async def compare_variants(a: str = Query(...), b: str = Query(...)):
    """Compare two variants side-by-side."""
    cat_a, var_a = a.split("/", 1)
    cat_b, var_b = b.split("/", 1)
    data_a = engine.load_library_entry(cat_a, var_a)
    data_b = engine.load_library_entry(cat_b, var_b)
    if data_a is None or data_b is None:
        raise HTTPException(404, "One or both variants not found in library")
    return {"a": data_a, "b": data_b}


@app.get("/api/library/export")
async def export_library():
    """Export entire library as a single JSON bundle (for DFA import)."""
    return engine.full_library_export()


# ─── Settings / Categories ────────────────────────────────────────────────────

@app.get("/api/settings/categories")
async def get_categories():
    """Get all category folder mappings (built-in + custom)."""
    # Separate built-in from custom
    builtin = {
        "RC VAV Programming": "VAV", "RC RTU Programming": "RTU",
        "RC FCU Programming": "FCU", "RC AHU Programming": "AHU",
        "RC G36AHU Programming": "G36AHU", "RC G36VAV Programming": "G36VAV",
        "RC UH Programming": "UH", "RC VVT Programming": "VVT",
        "RC WSHP Programming": "WSHP",
    }
    custom = {}
    if engine.cfg.custom_categories_file.exists():
        try:
            custom = json.loads(engine.cfg.custom_categories_file.read_text())
        except Exception:
            pass
    # List existing folders in upload root
    existing_folders = []
    if engine.cfg.upload_root.exists():
        for d in sorted(engine.cfg.upload_root.iterdir()):
            if d.is_dir():
                existing_folders.append(d.name)
    return {
        "builtin": builtin,
        "custom": custom,
        "all": engine.cfg.CATEGORIES,
        "upload_root": str(engine.cfg.upload_root),
        "existing_folders": existing_folders,
    }


@app.post("/api/settings/categories")
async def add_category(body: dict = None):
    """Add a custom category mapping. Body: { "folder": "My Custom AHU", "key": "CUSTOM_AHU" }"""
    if not body or "folder" not in body or "key" not in body:
        raise HTTPException(400, "Must provide 'folder' and 'key'")
    folder = body["folder"].strip()
    key = body["key"].strip().upper()
    if not folder or not key:
        raise HTTPException(400, "Folder and key cannot be empty")

    # Create the folder if it doesn't exist
    folder_path = engine.cfg.upload_root / folder
    folder_path.mkdir(parents=True, exist_ok=True)

    # Load existing custom categories and add new one
    custom = {}
    if engine.cfg.custom_categories_file.exists():
        try:
            custom = json.loads(engine.cfg.custom_categories_file.read_text())
        except Exception:
            pass
    custom[folder] = key
    engine.cfg.save_custom_categories(custom)

    return {"status": "added", "folder": folder, "key": key, "path": str(folder_path)}


@app.delete("/api/settings/categories/{key}")
async def remove_category(key: str):
    """Remove a custom category mapping by key."""
    custom = {}
    if engine.cfg.custom_categories_file.exists():
        try:
            custom = json.loads(engine.cfg.custom_categories_file.read_text())
        except Exception:
            pass
    # Find and remove by key
    to_remove = [k for k, v in custom.items() if v == key.upper()]
    if not to_remove:
        raise HTTPException(404, f"Custom category '{key}' not found")
    for k in to_remove:
        del custom[k]
        # Also remove from live config
        engine.cfg.CATEGORIES.pop(k, None)
    engine.cfg.custom_categories_file.write_text(json.dumps(custom, indent=2))
    return {"status": "removed", "key": key}


# ─── File Serving ─────────────────────────────────────────────────────────────

@app.get("/api/files/assets/{category}/{variant_id}")
async def list_asset_files(category: str, variant_id: str):
    """List all graphics/asset files for a variant."""
    asset_dir = engine.cfg.assets_root / category / variant_id
    if not asset_dir.exists():
        return {"files": []}
    files = []
    for f in sorted(asset_dir.iterdir()):
        if f.is_file():
            mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "mime": mime,
                "is_image": mime.startswith("image/"),
                "url": f"/api/files/assets/{category}/{variant_id}/{f.name}",
            })
    return {"files": files, "count": len(files)}


@app.get("/api/files/assets/{category}/{variant_id}/download")
async def download_variant_assets(category: str, variant_id: str):
    """Download all assets for a variant as a zip.
    Sources (in priority order):
    1. Variant-specific asset folder (from .panx extraction)
    2. Required images parsed from GRP JSON files in the library entry
    3. Shared asset library as fallback
    """
    import zipfile
    import io
    import re as _re

    asset_dir = engine.cfg.assets_root / category / variant_id
    shared_dir = engine.cfg.assets_root / "_shared"

    buf = io.BytesIO()
    added = set()  # Track by full relative path to allow same filename in different dirs

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. Add variant-specific assets if they exist
        if asset_dir.exists():
            for root, dirs, files in os.walk(asset_dir):
                for fname in files:
                    fpath = Path(root) / fname
                    arcname = str(fpath.relative_to(asset_dir))
                    zf.write(fpath, arcname)
                    added.add(arcname.lower().replace('\\', '/'))

        # 2. Parse GRP JSONs + meta GroupAssets for ALL required files
        lib_entry = engine.load_library_entry(category, variant_id)
        required_files = set()
        required_dirs = set()  # Animation directories to include entirely
        if lib_entry:
            grp_files = lib_entry.get("grp_files", {})
            for grp_name, grp_data in grp_files.items():
                text = json.dumps(grp_data)
                for m in _re.finditer(r'"(?:external_file|gel_filename|image|background_image)"\s*:\s*"([^"]+)"', text):
                    val = m.group(1).replace('\\\\', '\\').replace('pic\\', '')
                    if val and '.' in val:
                        required_files.add(val)

            # GroupAssets — includes animation subdirectories
            for ga in lib_entry.get("meta", {}).get("GroupAssets", []):
                job_path = ga.get("JobPath", "").replace('pic\\', '')
                if job_path and '.' in job_path:
                    required_files.add(job_path)
                    # If it's in an Animation subdir, mark the whole dir
                    if 'Animation' in job_path:
                        parts = job_path.replace('\\', '/').split('/')
                        # Animation/DirName/ — include all files in that dir
                        if len(parts) >= 2:
                            anim_dir = '/'.join(parts[:2])  # e.g. "Animation/Damper-Vert-02-V02"
                            required_dirs.add(anim_dir)

        # 3. Find required files in shared library
        if shared_dir.exists():
            # First: copy entire animation directories
            for anim_dir in required_dirs:
                src_dir = shared_dir / anim_dir
                if src_dir.exists():
                    for root, dirs, files in os.walk(src_dir):
                        for fname in files:
                            fpath = Path(root) / fname
                            arcname = str(fpath.relative_to(shared_dir)).replace('\\', '/')
                            if arcname.lower().replace('\\', '/') not in added:
                                zf.write(fpath, arcname)
                                added.add(arcname.lower().replace('\\', '/'))

            # Then: individual files (images, icons)
            for req in required_files:
                req_norm = req.replace('\\', '/')
                if req_norm.lower() in added:
                    continue
                # Try exact relative path first
                exact = shared_dir / req_norm
                if exact.exists():
                    zf.write(exact, req_norm)
                    added.add(req_norm.lower())
                    continue
                # Fallback: search by filename
                matches = list(shared_dir.rglob(Path(req_norm).name))
                if matches:
                    zf.write(matches[0], req_norm)
                    added.add(req_norm.lower())

    if not added:
        raise HTTPException(404, "No assets found for this variant")

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{variant_id}_assets.zip"'}
    )


@app.post("/api/files/assets/{category}/{variant_id}/upload")
async def upload_variant_assets(category: str, variant_id: str, files: list[UploadFile] = File(...)):
    """Upload asset files (images, animations) to a variant's asset folder.
    Supports individual files or a zip of files.
    """
    import zipfile
    import io

    asset_dir = engine.cfg.assets_root / category / variant_id
    asset_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []
    for f in files:
        data = await f.read()

        # If it's a zip, extract its contents
        if f.filename and f.filename.lower().endswith('.zip'):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        # Strip leading folder if all files share one
                        arcname = info.filename
                        dest = asset_dir / arcname
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(zf.read(info))
                        uploaded.append(arcname)
            except zipfile.BadZipFile:
                raise HTTPException(400, f"{f.filename} is not a valid zip")
        else:
            # Save individual file
            dest = asset_dir / f.filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            uploaded.append(f.filename)

    # Also update the library JSON's GroupAssets if it exists
    lib_entry = engine.load_library_entry(category, variant_id)
    if lib_entry:
        existing_assets = set()
        for ga in lib_entry.get("meta", {}).get("GroupAssets", []):
            existing_assets.add(ga.get("Asset", ""))

        new_assets = []
        for fname in uploaded:
            asset_path = f"group_assets\\{fname.replace('/', os.sep)}"
            if asset_path not in existing_assets:
                new_assets.append({
                    "Asset": asset_path,
                    "JobPath": fname.replace('/', os.sep),
                })

        if new_assets:
            lib_entry.setdefault("meta", {}).setdefault("GroupAssets", []).extend(new_assets)
            engine._save_library_entry(category, variant_id, lib_entry)

    return {"status": "uploaded", "count": len(uploaded), "files": uploaded}


@app.get("/api/binary/report/{category}/{variant_id}")
async def binary_point_report(category: str, variant_id: str):
    """Generate a complete point report from the .pan binary.

    Includes data that PFG XML export misses: loop bindings, verified present
    values, trend references, unit mappings.
    """
    from app.pan_binary import PanBinary

    # Find the source .panx or .pan
    folder_name = engine._cat_folder(category)
    cat_dir = engine.cfg.upload_root / folder_name

    src_panx = next(cat_dir.rglob(f"{variant_id}.panx"), None)
    src_pan = next(cat_dir.rglob(f"{variant_id}.pan"), None)

    if src_panx:
        pan = PanBinary.from_panx(src_panx)
    elif src_pan:
        pan = PanBinary.from_file(src_pan)
    else:
        raise HTTPException(404, f"No .pan/.panx found for {variant_id}")

    report = pan.generate_point_report()
    return StreamingResponse(
        __import__('io').BytesIO(report.encode()),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{variant_id}_binary_report.txt"'}
    )


@app.get("/api/binary/data/{category}/{variant_id}")
async def binary_data(category: str, variant_id: str):
    """Get structured binary data as JSON for a variant.

    Returns loops with actual input/setpoint bindings, points with verified
    present values, and trend references — all from the .pan binary.
    """
    from app.pan_binary import PanBinary

    folder_name = engine._cat_folder(category)
    cat_dir = engine.cfg.upload_root / folder_name

    src_panx = next(cat_dir.rglob(f"{variant_id}.panx"), None)
    src_pan = next(cat_dir.rglob(f"{variant_id}.pan"), None)

    if src_panx:
        pan = PanBinary.from_panx(src_panx)
    elif src_pan:
        pan = PanBinary.from_file(src_pan)
    else:
        raise HTTPException(404, f"No .pan/.panx found for {variant_id}")

    return {
        "variant_id": variant_id,
        "object_count": len(pan.objects),
        "loops": pan.get_loops(),
        "trends": pan.get_trends(),
        "points": pan.get_point_details(),
        "summary": {cat: len(items) for cat, items in pan.get_all_objects().items()},
    }


@app.post("/api/binary/diff")
async def binary_diff(body: dict = None):
    """Compare two controllers and return differences.

    Body: {
        "first": {"category": "SBS_AHU", "variant_id": "1003"},
        "second": {"category": "SBS_AHU", "variant_id": "PS-AHU-ERW-0100"}
    }
    """
    from app.pan_binary import diff_controllers

    if not body or 'first' not in body or 'second' not in body:
        raise HTTPException(400, "Must provide 'first' and 'second' controller references")

    paths = []
    for key in ['first', 'second']:
        ref = body[key]
        folder = engine._cat_folder(ref['category'])
        cat_dir = engine.cfg.upload_root / folder
        src = next(cat_dir.rglob(f"{ref['variant_id']}.panx"), None) or \
              next(cat_dir.rglob(f"{ref['variant_id']}.pan"), None)
        if not src:
            raise HTTPException(404, f"Controller not found: {ref['variant_id']}")
        paths.append(src)

    try:
        result = diff_controllers(paths[0], paths[1])
        return result
    except Exception as e:
        raise HTTPException(500, f"Diff failed: {e}")


@app.post("/api/binary/copy")
async def binary_copy(body: dict = None):
    """Copy a controller with new device name and ID.

    Body: {
        "source": {"category": "SBS_AHU", "variant_id": "1003"},
        "new_device_id": 900,
        "new_device_name": "AHU-TEST",    // must be same byte length as source
        "values": {"RMT-SP": 72.0}        // optional value overrides
    }
    """
    from app.pan_binary import PanWriter

    if not body or 'source' not in body:
        raise HTTPException(400, "Must provide 'source' controller reference")

    ref = body['source']
    folder = engine._cat_folder(ref['category'])
    cat_dir = engine.cfg.upload_root / folder
    src = next(cat_dir.rglob(f"{ref['variant_id']}.panx"), None) or \
          next(cat_dir.rglob(f"{ref['variant_id']}.pan"), None)
    if not src:
        raise HTTPException(404, f"Controller not found: {ref['variant_id']}")

    try:
        if str(src).endswith('.panx'):
            writer = PanWriter.from_panx(src)
        else:
            writer = PanWriter.from_file(src)

        if 'new_device_id' in body:
            writer.set_device_id(body['new_device_id'])

        if 'new_device_name' in body:
            # Auto-detect source name
            parser = __import__('app.pan_binary', fromlist=['PanBinary']).PanBinary(bytes(writer.data))
            prefixes = {}
            for obj in parser.objects:
                if '-' in obj['name']:
                    p = obj['name'].split('-')[0].strip()
                    if p and len(p) > 1:
                        prefixes[p] = prefixes.get(p, 0) + 1
            source_name = max(prefixes, key=prefixes.get) if prefixes else ""
            new_name = body['new_device_name']

            if source_name and len(source_name) == len(new_name):
                count = writer.rename_device(source_name, new_name)
            elif source_name:
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"Name length mismatch: source='{source_name}' ({len(source_name)} chars), new='{new_name}' ({len(new_name)} chars). Must be same length."}
                )

        out_path = Path(f"/tmp/binary_copy_{body.get('new_device_id', 'output')}.pan")
        writer.save(out_path)

        return FileResponse(
            out_path,
            filename=f"{body.get('new_device_name', 'controller')}.pan",
            media_type="application/octet-stream",
        )
    except Exception as e:
        raise HTTPException(500, f"Copy failed: {e}")


@app.get("/api/files/assets/shared")
async def list_shared_assets():
    """List all files in the shared asset library."""
    shared_dir = engine.cfg.assets_root / "_shared"
    if not shared_dir.exists():
        return {"files": [], "count": 0}
    files = []
    for root, dirs, fnames in os.walk(shared_dir):
        for fname in sorted(fnames):
            fpath = Path(root) / fname
            rel = str(fpath.relative_to(shared_dir))
            mime = mimetypes.guess_type(fname)[0] or "application/octet-stream"
            files.append({
                "name": fname,
                "path": rel,
                "size": fpath.stat().st_size,
                "mime": mime,
                "is_image": mime.startswith("image/"),
            })
    return {"files": files, "count": len(files)}


@app.post("/api/files/assets/shared/upload")
async def upload_shared_assets(files: list[UploadFile] = File(...)):
    """Upload files to the shared asset library. Supports files or zips."""
    import zipfile
    import io

    shared_dir = engine.cfg.assets_root / "_shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    uploaded = []

    for f in files:
        data = await f.read()
        if f.filename and f.filename.lower().endswith('.zip'):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        dest = shared_dir / info.filename
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(zf.read(info))
                        uploaded.append(info.filename)
            except zipfile.BadZipFile:
                raise HTTPException(400, f"{f.filename} is not a valid zip")
        else:
            dest = shared_dir / f.filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            uploaded.append(f.filename)

    return {"status": "uploaded", "count": len(uploaded), "files": uploaded}


@app.get("/api/files/assets/shared/download")
async def download_shared_assets():
    """Download the entire shared asset library as a zip."""
    import zipfile
    import io

    shared_dir = engine.cfg.assets_root / "_shared"
    if not shared_dir.exists():
        raise HTTPException(404, "No shared assets found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(shared_dir):
            for fname in files:
                fpath = Path(root) / fname
                arcname = str(fpath.relative_to(shared_dir))
                zf.write(fpath, arcname)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="shared_assets.zip"'}
    )


@app.get("/api/files/assets/{category}/{variant_id}/{filename}")
async def serve_asset_file(category: str, variant_id: str, filename: str):
    """Serve a single asset file (image, etc.)."""
    file_path = engine.cfg.assets_root / category / variant_id / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(file_path)


@app.get("/api/files/source/{category}/{variant_id}")
async def list_source_files(category: str, variant_id: str):
    """List original source files (.pan, .bas, .pdf, etc.) for a variant."""
    folder_name = engine._cat_folder(category)
    cat_dir = engine.cfg.upload_root / folder_name
    if not cat_dir.exists():
        return {"files": []}

    files = []
    # Find the variant's source directory
    for src in cat_dir.rglob(f"{variant_id}.*"):
        if src.is_file():
            mime = mimetypes.guess_type(src.name)[0] or "application/octet-stream"
            files.append({
                "name": src.name,
                "size": src.stat().st_size,
                "mime": mime,
                "is_image": mime.startswith("image/"),
                "url": f"/api/files/source/{category}/{variant_id}/{src.name}",
            })

    # Also find .bas files and other files in the same directory
    for pattern in [f"{variant_id}*.bas", f"{variant_id}*.pdf", f"{variant_id}*.txt", f"{variant_id}*.doc*"]:
        for src in cat_dir.rglob(pattern):
            if src.is_file() and not any(f["name"] == src.name for f in files):
                mime = mimetypes.guess_type(src.name)[0] or "application/octet-stream"
                files.append({
                    "name": src.name,
                    "size": src.stat().st_size,
                    "mime": mime,
                    "url": f"/api/files/source/{category}/{variant_id}/{src.name}",
                })

    # Check the variant's parent folder for any extra files
    for panx in cat_dir.rglob(f"{variant_id}.panx"):
        parent = panx.parent
        for f in parent.iterdir():
            if f.is_file() and not any(ef["name"] == f.name for ef in files):
                mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "mime": mime,
                    "url": f"/api/files/source/{category}/{variant_id}/{f.name}",
                })

    for pan in cat_dir.rglob(f"{variant_id}.pan"):
        parent = pan.parent
        for f in parent.iterdir():
            if f.is_file() and not any(ef["name"] == f.name for ef in files):
                mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "mime": mime,
                    "url": f"/api/files/source/{category}/{variant_id}/{f.name}",
                })

    return {"files": files, "count": len(files)}


@app.get("/api/files/source/{category}/{variant_id}/{filename}")
async def serve_source_file(category: str, variant_id: str, filename: str):
    """Serve a source file."""
    folder_name = engine._cat_folder(category)
    cat_dir = engine.cfg.upload_root / folder_name
    # Search for the file
    for f in cat_dir.rglob(filename):
        if f.is_file():
            return FileResponse(f, filename=filename)
    raise HTTPException(404, "File not found")


@app.post("/api/library/{category}/{variant_id}/save")
async def save_variant(category: str, variant_id: str, body: dict = None):
    """Save edits to a library entry (point names, code, trend toggles, etc.)."""
    if not body:
        raise HTTPException(400, "No data to save")
    existing = engine.load_library_entry(category, variant_id)
    if existing is None:
        raise HTTPException(404, "Variant not found")

    # Merge edits into existing record
    if "objects" in body:
        existing["objects"] = body["objects"]
        existing["counts"] = {k: len(v) for k, v in existing["objects"].items() if isinstance(v, list) and v}
    if "meta" in body:
        existing["meta"].update(body["meta"])
    if "description" in body:
        existing["description"] = body["description"]
        # Also update master_descriptions.json so it persists across re-extractions
        _update_master_description(variant_id, body["description"])

    engine._save_library_entry(category, variant_id, existing)
    return {"status": "saved", "id": variant_id}


def _update_master_description(variant_id: str, description: str):
    """Update a single variant description in master_descriptions.json."""
    descs = {}
    if cfg.master_descriptions.exists():
        try:
            descs = json.loads(cfg.master_descriptions.read_text())
        except Exception:
            pass
    descs[variant_id] = description
    cfg.master_descriptions.write_text(json.dumps(descs, indent=2))
    # Also update the extractor's in-memory cache
    engine.descriptions[variant_id] = description


@app.get("/api/library/descriptions")
async def get_all_descriptions():
    """Get all variant descriptions from master_descriptions.json."""
    if cfg.master_descriptions.exists():
        try:
            return json.loads(cfg.master_descriptions.read_text())
        except Exception:
            return {}
    return {}


@app.put("/api/library/{category}/{variant_id}/description")
async def set_variant_description(category: str, variant_id: str, body: dict = None):
    """Set the description for a single variant.
    Body: { "description": "My custom controller description" }
    """
    if not body or "description" not in body:
        raise HTTPException(400, "Must provide 'description' in body")

    description = body["description"]

    # Update master_descriptions.json
    _update_master_description(variant_id, description)

    # Update the library JSON if it exists
    existing = engine.load_library_entry(category, variant_id)
    if existing:
        existing["description"] = description
        engine._save_library_entry(category, variant_id, existing)

    return {"status": "updated", "id": variant_id, "description": description}


@app.put("/api/library/descriptions")
async def set_bulk_descriptions(body: dict = None):
    """Set descriptions for multiple variants at once.
    Body: { "VAV-IS10001": "Single Duct, Floating HW Reheat", "MY-CUSTOM": "My desc" }
    """
    if not body:
        raise HTTPException(400, "Must provide variant_id: description map")

    descs = {}
    if cfg.master_descriptions.exists():
        try:
            descs = json.loads(cfg.master_descriptions.read_text())
        except Exception:
            pass

    descs.update(body)
    cfg.master_descriptions.write_text(json.dumps(descs, indent=2))

    # Update extractor in-memory cache
    engine.descriptions.update(body)

    # Update any existing library JSONs
    updated = []
    for vid, desc in body.items():
        for cat_dir in cfg.library_root.iterdir():
            if not cat_dir.is_dir() or cat_dir.name.startswith("_"):
                continue
            entry_path = cat_dir / f"{vid}.json"
            if entry_path.exists():
                try:
                    entry = json.loads(entry_path.read_text())
                    entry["description"] = desc
                    entry_path.write_text(json.dumps(entry, indent=2))
                    updated.append(vid)
                except Exception:
                    pass

    return {"status": "updated", "count": len(body), "library_updated": updated}


# ─── Composer ────────────────────────────────────────────────────────────────

@app.get("/api/composer/programs")
async def composer_program_index():
    """Get flat index of every program across the entire library with dependencies."""
    return composer.build_program_index()


@app.post("/api/composer/compose")
async def composer_compose(body: dict = None):
    """Compose a new controller from selected programs.

    Body:
    {
        "selections": [
            {"category": "VAV", "variant_id": "VAV-IS10001", "program_instance": "1"},
            {"category": "RTU", "variant_id": "RTU-ISA11110E", "program_instance": "4"},
            ...
        ],
        "device_name": "{device-name}",  (optional, default "{device-name}")
        "device_id": "900"               (optional, default "900")
    }
    """
    if not body or "selections" not in body:
        raise HTTPException(400, "Must provide 'selections' list")

    selections = body["selections"]
    if not selections:
        raise HTTPException(400, "Must select at least one program")

    device_name = body.get("device_name", "{device-name}")
    device_id = body.get("device_id", "900")
    primary_variant = body.get("primary_variant", None)

    try:
        result = composer.compose(selections, device_name, device_id, primary_variant=primary_variant)
        # Cache for Excel export
        composer._last_composition = result
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("Composition failed")
        raise HTTPException(500, f"Composition failed: {e}")


@app.post("/api/composer/save")
async def composer_save(body: dict = None):
    """Save a composed controller to the library.

    Body:
    {
        "name": "My-Custom-VAV",
        "composition": { ... composed controller JSON ... }
    }
    """
    if not body or "name" not in body or "composition" not in body:
        raise HTTPException(400, "Must provide 'name' and 'composition'")

    try:
        path = composer.save_composition(body["name"], body["composition"])
        return {"status": "saved", "path": str(path), "id": body["name"]}
    except Exception as e:
        raise HTTPException(500, f"Save failed: {e}")


@app.get("/api/composer/compositions")
async def composer_list():
    """List all saved compositions."""
    return composer.list_compositions()


@app.get("/api/composer/compositions/{name}")
async def composer_get(name: str):
    """Load a saved composition."""
    data = composer.load_composition(name)
    if data is None:
        raise HTTPException(404, f"Composition '{name}' not found")
    return data


@app.delete("/api/composer/compositions/{name}")
async def composer_delete(name: str):
    """Delete a saved composition."""
    if composer.delete_composition(name):
        return {"status": "deleted", "id": name}
    raise HTTPException(404, f"Composition '{name}' not found")


@app.post("/api/composer/generate-xml")
async def composer_generate_xml(body: dict = None):
    """Generate PFG-compatible XML from a composed controller.

    Body: the composed controller JSON (from /api/composer/compose or /api/composer/compositions/{name})
    OR: {"name": "saved-composition-name"} to load from saved
    """
    from generator import generate_xml

    if not body:
        raise HTTPException(400, "Must provide composition data")

    # If a name is provided, load the saved composition
    if "name" in body and "objects" not in body:
        data = composer.load_composition(body["name"])
        if data is None:
            raise HTTPException(404, f"Composition '{body['name']}' not found")
    else:
        data = body

    device_id = data.get("meta", {}).get("device_id", "900")
    device_name = data.get("meta", {}).get("device_name", "{device-name}")

    try:
        xml = generate_xml(data, device_id=device_id, device_name=device_name)
        return JSONResponse(content={
            "xml": xml,
            "device_id": device_id,
            "device_name": device_name,
        })
    except Exception as e:
        logger.exception("XML generation failed")
        raise HTTPException(500, f"XML generation failed: {e}")


@app.get("/api/composer/descriptions")
async def composer_variant_descriptions():
    """Get auto-generated human-readable descriptions for all variant IDs.
    Analyzes program code dependencies (AO vs BO on reheat) to determine
    floating vs modulating control. Non-VAV types use manual overrides."""
    return composer.build_variant_descriptions()


@app.get("/api/composer/blanks")
async def composer_list_blanks():
    """List available blank controller model templates for .pan/.panx generation."""
    return composer.list_blank_panels()


def _resolve_composition(body: dict) -> dict:
    """Helper: resolve body to composition data (load by name if needed)."""
    if "name" in body and "objects" not in body:
        data = composer.load_composition(body["name"])
        if data is None:
            raise HTTPException(404, f"Composition '{body['name']}' not found")
        return data
    return body


@app.post("/api/composer/generate-pan")
async def composer_generate_pan(body: dict = None):
    """Generate a .pan file from a composed controller.

    Body: {
        ...composition data or {"name": "saved-name"},
        "blank_model": "RC-FLEXair-34-A-F"  (optional, selects controller template)
    }
    Returns the .pan file as a download.
    """
    if not body:
        raise HTTPException(400, "Must provide composition data")

    blank_model = body.pop("blank_model", None)
    data = _resolve_composition(body)

    try:
        pan_path = await asyncio.get_event_loop().run_in_executor(
            None, composer.generate_pan, data, blank_model
        )
        comp_id = data.get("id", "composed")
        # Check if values document was generated alongside
        values_path = pan_path.parent / f"{comp_id}_values.txt"
        headers = {}
        if values_path.exists():
            headers["X-Values-Document"] = "true"
        return FileResponse(
            pan_path,
            filename=f"{comp_id}.pan",
            media_type="application/octet-stream",
            headers=headers,
        )
    except Exception as e:
        logger.exception("PAN generation failed")
        raise HTTPException(500, f"PAN generation failed: {e}")


@app.post("/api/composer/generate-panx")
async def composer_generate_panx(body: dict = None):
    """Generate a .panx file from a composed controller.

    Body: {
        ...composition data or {"name": "saved-name"},
        "blank_model": "RC-FLEXair-34-A-F"  (optional, selects controller template)
    }
    Returns the .panx file as a download.
    """
    if not body:
        raise HTTPException(400, "Must provide composition data")

    blank_model = body.pop("blank_model", None)
    data = _resolve_composition(body)

    try:
        panx_path = await asyncio.get_event_loop().run_in_executor(
            None, composer.generate_panx, data, blank_model
        )
        comp_id = data.get("id", "composed")
        return FileResponse(
            panx_path,
            filename=f"{comp_id}.panx",
            media_type="application/octet-stream",
        )
    except Exception as e:
        logger.exception("PANX generation failed")
        raise HTTPException(500, f"PANX generation failed: {e}")


@app.post("/api/composer/generate-template-package")
async def composer_generate_template_package(body: dict = None):
    """Generate a complete template package zip containing:
    - .pan file (with {device-name} template names)
    - values reference document
    - assets folder (images + animations from primary variant + shared library)

    Uses the first selected variant as the primary source for assets.
    """
    import zipfile as _zf
    import io
    import re as _re_pkg

    if not body:
        raise HTTPException(400, "Must provide composition data")

    blank_model = body.pop("blank_model", None)
    data = _resolve_composition(body)
    comp_id = data.get("id", "composed")

    try:
        # 1. Generate .pan
        pan_path = await asyncio.get_event_loop().run_in_executor(
            None, composer.generate_pan, data, blank_model
        )

        # 2. Get values doc
        values_path = pan_path.parent / f"{comp_id}_values.txt"

        # 3. Collect assets from primary variant + shared library
        meta = data.get("meta", {})
        graphics_sources = meta.get("graphics_sources", [])

        # Primary variant = first graphics source
        primary_cat = graphics_sources[0].get("from_category", "") if graphics_sources else ""
        primary_var = graphics_sources[0].get("from_variant", "") if graphics_sources else ""

        # Gather required files from GRP JSONs + GroupAssets
        required_files = set()
        required_dirs = set()
        grp_files = data.get("grp_files", {})
        for grp_name, grp_data in grp_files.items():
            text = json.dumps(grp_data)
            for m in _re_pkg.finditer(r'"(?:external_file|gel_filename|image|background_image)"\s*:\s*"([^"]+)"', text):
                val = m.group(1).replace('\\\\', '\\').replace('pic\\', '')
                if val and '.' in val:
                    required_files.add(val)

        for ga in meta.get("GroupAssets", []):
            job_path = ga.get("JobPath", "").replace('pic\\', '')
            if job_path and '.' in job_path:
                required_files.add(job_path)
                if 'Animation' in job_path:
                    parts = job_path.replace('\\', '/').split('/')
                    if len(parts) >= 2:
                        required_dirs.add('/'.join(parts[:2]))

        # Build zip
        buf = io.BytesIO()
        with _zf.ZipFile(buf, 'w', _zf.ZIP_DEFLATED) as zf:
            # Add .pan
            zf.write(pan_path, f"{comp_id}.pan")

            # Add values doc
            if values_path.exists():
                zf.write(values_path, f"{comp_id}_values.txt")

            # Add assets
            added_assets = set()
            asset_sources = []

            # Primary variant assets first
            if primary_cat and primary_var:
                pdir = engine.cfg.assets_root / primary_cat / primary_var
                if pdir.exists():
                    asset_sources.append(pdir)

            # Other variant assets
            for gs in graphics_sources[1:]:
                d = engine.cfg.assets_root / gs.get("from_category", "") / gs.get("from_variant", "")
                if d.exists() and d not in asset_sources:
                    asset_sources.append(d)

            # Shared library last
            shared = engine.cfg.assets_root / "_shared"
            if shared.exists():
                asset_sources.append(shared)

            # Copy from variant asset dirs
            for adir in asset_sources:
                if adir.name == "_shared":
                    continue  # Handle shared separately
                for root, dirs, files in os.walk(adir):
                    for fname in files:
                        fpath = Path(root) / fname
                        arcname = "assets/" + str(fpath.relative_to(adir)).replace('\\', '/')
                        if arcname.lower() not in added_assets:
                            zf.write(fpath, arcname)
                            added_assets.add(arcname.lower())

            # Copy animation dirs from shared
            if shared.exists():
                for anim_dir in required_dirs:
                    src_dir = shared / anim_dir
                    if src_dir.exists():
                        for root, dirs, files in os.walk(src_dir):
                            for fname in files:
                                fpath = Path(root) / fname
                                arcname = "assets/" + str(fpath.relative_to(shared)).replace('\\', '/')
                                if arcname.lower() not in added_assets:
                                    zf.write(fpath, arcname)
                                    added_assets.add(arcname.lower())

                # Individual files from shared
                for req in required_files:
                    req_norm = req.replace('\\', '/')
                    arcname = "assets/" + req_norm
                    if arcname.lower() in added_assets:
                        continue
                    exact = shared / req_norm
                    if exact.exists():
                        zf.write(exact, arcname)
                        added_assets.add(arcname.lower())
                    else:
                        matches = list(shared.rglob(Path(req_norm).name))
                        if matches:
                            zf.write(matches[0], arcname)
                            added_assets.add(arcname.lower())

        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{comp_id}_template_package.zip"'}
        )
    except Exception as e:
        logger.exception("Template package generation failed")
        raise HTTPException(500, f"Template package generation failed: {e}")


@app.get("/api/composer/values-document/{comp_id}")
async def composer_values_document(comp_id: str):
    """Download the companion values reference document for a generated controller.

    This text file lists all configured values (present values, PID settings,
    ranges, units) from the source library — useful for verifying or manually
    entering values that PFG may not preserve in the .pan binary.
    """
    output_dir = cfg.library_root / "COMPOSED" / "_output"
    values_path = output_dir / f"{comp_id}_values.txt"
    if not values_path.exists():
        raise HTTPException(404, f"Values document not found for '{comp_id}'")
    return FileResponse(
        values_path,
        filename=f"{comp_id}_values.txt",
        media_type="text/plain",
    )


@app.get("/api/composer/values-document/{comp_id}/excel")
async def composer_values_excel(comp_id: str):
    """Download values as an Excel file for easy copy/paste into RC Studio."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    output_dir = cfg.library_root / "COMPOSED" / "_output"

    # Load the composition data to build Excel
    comp_path = output_dir / f"{comp_id}.pan"
    if not comp_path.exists():
        raise HTTPException(404, f"Composition not found for '{comp_id}'")

    # Try to load from the last compose result
    last_comp = getattr(composer, '_last_composition', None)
    if not last_comp or last_comp.get("id") != comp_id:
        raise HTTPException(404, "Composition data expired — recompose first")

    objects = last_comp.get("objects", {})
    device_name = last_comp.get("meta", {}).get("device_name", "{device-name}")

    wb = Workbook()
    header_font = Font(bold=True, size=11)
    header_fill = PatternFill("solid", fgColor="4472C4")
    header_font_white = Font(bold=True, size=11, color="FFFFFF")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    empty_fill = PatternFill("solid", fgColor="F2F2F2")

    def add_sheet(name, headers, rows):
        """Add a sheet with rows. First column must be instance number.
        Fills empty rows for gaps so the spreadsheet is contiguous for copy/paste."""
        ws = wb.create_sheet(name)
        for c, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=c, value=h)
            cell.font = header_font_white
            cell.fill = header_fill
            cell.border = thin_border

        if not rows:
            return

        # Build dict by instance for gap filling
        by_inst = {}
        for row in rows:
            by_inst[row[0]] = row

        max_inst = max(by_inst.keys())
        r = 2
        for inst in range(1, max_inst + 1):
            if inst in by_inst:
                for c, val in enumerate(by_inst[inst], 1):
                    cell = ws.cell(row=r, column=c, value=val)
                    cell.border = thin_border
            else:
                # Empty row — just instance number, greyed out
                cell = ws.cell(row=r, column=1, value=inst)
                cell.border = thin_border
                cell.fill = empty_fill
                for c in range(2, len(headers) + 1):
                    cell = ws.cell(row=r, column=c, value="")
                    cell.border = thin_border
                    cell.fill = empty_fill
            r += 1

        # Auto-width
        for c in range(1, len(headers) + 1):
            max_len = max(len(str(ws.cell(row, c).value or '')) for row in range(1, r))
            ws.column_dimensions[ws.cell(1, c).column_letter].width = min(max_len + 3, 50)

    # Analog Values
    av_rows = []
    for p in sorted(objects.get("AV", []), key=lambda x: int(x.get("instance", 0))):
        name = p.get("name", "").replace("{device-name}", device_name)
        av_rows.append([int(p.get("instance", 0)), name, p.get("present_value", ""),
                       p.get("range", ""), p.get("unit", ""), p.get("increment", ""),
                       p.get("description", "")])
    if av_rows:
        add_sheet("Analog Values", ["Instance", "Name", "Value", "Range", "Unit", "Increment", "Description"], av_rows)

    # Analog Inputs
    ai_rows = []
    for p in sorted(objects.get("AI", []), key=lambda x: int(x.get("instance", 0))):
        name = p.get("name", "").replace("{device-name}", device_name)
        ai_rows.append([int(p.get("instance", 0)), name, p.get("present_value", ""),
                       p.get("range", ""), p.get("unit", ""), p.get("increment", "")])
    if ai_rows:
        add_sheet("Analog Inputs", ["Instance", "Name", "Value", "Range", "Unit", "Increment"], ai_rows)

    # Analog Outputs
    ao_rows = []
    for p in sorted(objects.get("AO", []), key=lambda x: int(x.get("instance", 0))):
        name = p.get("name", "").replace("{device-name}", device_name)
        ao_rows.append([int(p.get("instance", 0)), name, p.get("present_value", ""),
                       p.get("range", ""), p.get("unit", ""), p.get("increment", "")])
    if ao_rows:
        add_sheet("Analog Outputs", ["Instance", "Name", "Value", "Range", "Unit", "Increment"], ao_rows)

    # Binary Values
    bv_rows = []
    for p in sorted(objects.get("BV", []), key=lambda x: int(x.get("instance", 0))):
        name = p.get("name", "").replace("{device-name}", device_name)
        bv_rows.append([int(p.get("instance", 0)), name, p.get("present_value", ""),
                       p.get("range", ""), p.get("unit", "")])
    if bv_rows:
        add_sheet("Binary Values", ["Instance", "Name", "Value", "Range", "Unit"], bv_rows)

    # Binary Inputs/Outputs
    for btype, sheet_name in [("BI", "Binary Inputs"), ("BO", "Binary Outputs")]:
        b_rows = []
        for p in sorted(objects.get(btype, []), key=lambda x: int(x.get("instance", 0))):
            name = p.get("name", "").replace("{device-name}", device_name)
            b_rows.append([int(p.get("instance", 0)), name, p.get("present_value", ""),
                          p.get("range", ""), p.get("unit", "")])
        if b_rows:
            add_sheet(sheet_name, ["Instance", "Name", "Value", "Range", "Unit"], b_rows)

    # Multistate
    for mtype, sheet_name in [("MV", "Multistate Values"), ("MO", "Multistate Outputs")]:
        m_rows = []
        for p in sorted(objects.get(mtype, []), key=lambda x: int(x.get("instance", 0))):
            name = p.get("name", "").replace("{device-name}", device_name)
            m_rows.append([int(p.get("instance", 0)), name, p.get("present_value", ""),
                          p.get("range", "")])
        if m_rows:
            add_sheet(sheet_name, ["Instance", "Name", "Value", "Range"], m_rows)

    # Loops — include suggested input/setpoint
    import re as _re_xl
    # Build point name lookup
    all_pts = {}
    for ptype in ["AV", "AI", "AO", "BV", "BI", "BO", "MV", "MO"]:
        for p in objects.get(ptype, []):
            pname = p.get("name", "").replace("{device-name}", device_name)
            all_pts[pname] = f"{ptype}{p.get('instance','')}"

    # Find LOOP output assignments from code
    loop_outputs = {}
    for prog in objects.get("PROGRAM", []):
        code = prog.get("code", "").replace("{device-name}", device_name)
        for line in code.split('\n'):
            # AO4 = LOOP8 pattern
            m = _re_xl.search(r'(AO\d+)\s*=\s*LOOP(\d+)', line)
            if m:
                loop_outputs.setdefault(m.group(2), []).append(m.group(1))
            # F = LOOP1 then AO10 = ... pattern
            m2 = _re_xl.search(r'\w+\s*=\s*LOOP(\d+)', line)

    loop_rows = []
    for l in sorted(objects.get("LOOP", []), key=lambda x: int(x.get("instance", 0))):
        name = l.get("name", "").replace("{device-name}", device_name)
        inst = l.get("instance", "")

        # Use binary-extracted bindings first, fall back to inferred suggestions
        input_pt = ""
        setpoint_pt = ""
        output_pt = ""

        # Binary extraction (accurate)
        ir = l.get("input_ref", "")
        irn = l.get("input_name", "").replace("{device-name}", device_name)
        if ir:
            input_pt = f"{ir} ({irn})" if irn else ir
        else:
            # Fallback: inference from name matching
            si = l.get("suggested_input", "")
            sin = l.get("suggested_input_name", "").replace("{device-name}", device_name)
            if si:
                input_pt = f"{si} ({sin}) [inferred]" if sin else f"{si} [inferred]"

        sr = l.get("setpoint_ref", "")
        srn = l.get("setpoint_name", "").replace("{device-name}", device_name)
        if sr:
            setpoint_pt = f"{sr} ({srn})" if srn else sr
        else:
            sp = l.get("suggested_setpoint", "")
            spn = l.get("suggested_setpoint_name", "").replace("{device-name}", device_name)
            if sp:
                setpoint_pt = f"{sp} ({spn}) [inferred]" if spn else f"{sp} [inferred]"

        so = l.get("suggested_output", "")
        son = l.get("suggested_output_name", "").replace("{device-name}", device_name)
        if so:
            output_pt = f"{so} ({son})" if son else so

        loop_rows.append([int(inst), name,
                         l.get("proportional", ""), l.get("integral", ""),
                         l.get("derivative", ""), l.get("bias", ""),
                         l.get("deadband", ""), l.get("action", ""),
                         l.get("integralunits", ""),
                         input_pt, setpoint_pt, output_pt])
    if loop_rows:
        add_sheet("Loops", ["Instance", "Name", "P", "I", "D", "Bias", "Deadband", "Action", "I-Units",
                           "Input (suggested)", "Setpoint (suggested)", "Output"], loop_rows)

    # Programs
    prog_rows = []
    for p in sorted(objects.get("PROGRAM", []), key=lambda x: int(x.get("instance", 0))):
        name = p.get("name", "").replace("{device-name}", device_name)
        pv = p.get("present_value", "1")
        prog_rows.append([int(p.get("instance", 0)), name,
                         "Yes" if str(pv) == "1" else "No",
                         p.get("code", "").replace("{device-name}", device_name)])
    if prog_rows:
        add_sheet("Programs", ["Instance", "Name", "Enabled", "Code"], prog_rows)

    # Trends
    trend_rows = []
    for t in sorted(objects.get("TREND", []), key=lambda x: int(x.get("instance", 0))):
        name = t.get("name", "").replace("{device-name}", device_name)
        refs = ", ".join(r for r in t.get("references", []) if r)
        trend_rows.append([int(t.get("instance", 0)), name, t.get("type", ""),
                          t.get("interval", ""), refs])
    if trend_rows:
        add_sheet("Trends", ["Instance", "Name", "Type", "Interval", "References"], trend_rows)

    # Remove default empty sheet
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{comp_id}_values.xlsx"'}
    )


# ─── Background Task ─────────────────────────────────────────────────────────

async def run_extraction(job_id: str, category_filter: Optional[str], selected_keys: Optional[list]):
    job = jobs[job_id]
    try:
        job["status"] = "running"
        variants = engine.discover_variants()

        flat = []
        if selected_keys:
            # Process only the specified variants
            for key in selected_keys:
                cat, vid = key.split("/", 1)
                for cat_name, items in variants.items():
                    if cat_name.upper() == cat.upper():
                        for item in items:
                            if item["id"] == vid:
                                flat.append((cat_name, item))
                                break
        else:
            for cat, items in variants.items():
                if category_filter and cat.upper() != category_filter.upper():
                    continue
                for item in items:
                    flat.append((cat, item))

        job["total"] = len(flat)
        for i, (cat, item) in enumerate(flat):
            job["current"] = f"{cat}/{item['id']}"
            job["progress"] = i + 1
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, engine.process_variant, cat, item
                )
                job["done"].append(f"{cat}/{item['id']}")
            except Exception as e:
                logger.error(f"Failed {cat}/{item['id']}: {e}")
                job["errors"].append({"variant": f"{cat}/{item['id']}", "error": str(e)})

        job["status"] = "done"
        job["current"] = ""
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        logger.exception("Extraction job failed")
