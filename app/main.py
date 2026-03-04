"""
Reliable Controls Extraction Tool
FastAPI backend — serves the web UI and REST API for DFA integration
"""

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Optional
import logging

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.extractor import ExtractionEngine
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

engine = ExtractionEngine(Config())

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

    engine._save_library_entry(category, variant_id, existing)
    return {"status": "saved", "id": variant_id}


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
