from __future__ import annotations

import os
import json
import datetime
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from fastapi import FastAPI, HTTPException, BackgroundTasks, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .rag_loader import load_rag_sections
from .section_mapper import SectionMapper
from .llm_orchestrator import generate_udd_sections
from .docx_builder import build_docx
from .config import DEFAULT_RAG_PATH, DEFAULT_MAPPING_PATH

app = FastAPI(title="FSD→UDD Generator (BackgroundTasks style)", version="4.0")

# =========================
# Models
# =========================

class GenerateRequest(BaseModel):
    fsd_text: str = Field(..., description="Full FSD plain text string")
    rag_path: Optional[str] = Field(default=None, description="Path to rag.txt (optional, defaults from env)")
    mapping_path: Optional[str] = Field(default=None, description="Path to fs_to_udd_mapping.json (optional)")
    document_title: Optional[str] = Field(default="Unified Design Document")

# =========================
# Background job store
# =========================

_JOBS_LOCK = threading.Lock()
_JOBS: Dict[str, Dict[str, Any]] = {}
# job schema:
# {
#   "status": "pending" | "running" | "done",
#   "attempts": int,
#   "result_path": Optional[str],  # DOCX path when done
#   "error": Optional[str]
# }

def _today_iso() -> str:
    return datetime.date.today().isoformat()

# =========================
# Core generation routine
# =========================

def _generate_docx_bytes(fsd_text: str, rag_path: str, mapping_path: str, title: str) -> bytes:
    rag_sections = load_rag_sections(rag_path)
    mapper = SectionMapper(mapping_path)
    pairs: List[Tuple[str, str]] = generate_udd_sections(fsd_text, rag_sections, mapper)
    return build_docx(pairs, title=title or "Unified Design Document")

def _run_job(job_id: str, req: GenerateRequest) -> None:
    with _JOBS_LOCK:
        _JOBS[job_id]["status"] = "running"
        _JOBS[job_id]["attempts"] = 1

    rag_path = req.rag_path or DEFAULT_RAG_PATH
    mapping_path = req.mapping_path or DEFAULT_MAPPING_PATH
    try:
        docx_bytes = _generate_docx_bytes(req.fsd_text, rag_path, mapping_path, req.document_title or "Unified Design Document")
        out_dir = Path("jobs") / job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "UDD.docx"
        with open(out_path, "wb") as f:
            f.write(docx_bytes)

        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "done"
            _JOBS[job_id]["result_path"] = str(out_path)
            _JOBS[job_id]["error"] = None

    except Exception as e:
        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "done"
            _JOBS[job_id]["result_path"] = None
            _JOBS[job_id]["error"] = str(e)

# =========================
# Endpoints
# =========================

@app.get("/healthz")
def healthz():
    return {"ok": True, "date": _today_iso()}

@app.post("/generate_direct")
def generate_direct(req: GenerateRequest):
    rag_path = req.rag_path or DEFAULT_RAG_PATH
    mapping_path = req.mapping_path or DEFAULT_MAPPING_PATH
    docx_bytes = _generate_docx_bytes(req.fsd_text, rag_path, mapping_path, req.document_title or "Unified Design Document")

    # Stream back as file
    tmp_dir = Path("jobs") / "direct"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / f"UDD_{_today_iso()}.docx"
    with open(out_path, "wb") as f:
        f.write(docx_bytes)
    return FileResponse(str(out_path), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=out_path.name)

@app.post("/generate")
def generate(req: GenerateRequest, background_tasks: BackgroundTasks):
    job_id = os.urandom(8).hex()
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "status": "pending",
            "attempts": 0,
            "result_path": None,
            "error": None,
        }
    background_tasks.add_task(_run_job, job_id, req)
    return {"job_id": job_id}

@app.get("/generate/{job_id}")
def get_job(job_id: str, response: Response):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found")

    if job["status"] == "done":
        if job.get("result_path") and os.path.exists(job["result_path"]):
            # Return the final DOCX
            p = Path(job["result_path"])
            return FileResponse(str(p), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=p.name)
        # Done, but errored
        return {"status": "done", "error": job.get("error")}

    # Not yet complete → 202
    response.status_code = status.HTTP_202_ACCEPTED
    return {"status": job["status"], "attempts": job.get("attempts", 0)}
