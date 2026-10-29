from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(os.environ.get("AUTOSHORTS_DATA_DIR", "/tmp/autoshorts-web"))
UPLOADS = ROOT / "uploads"
OUTPUTS = ROOT / "outputs"
UPLOADS.mkdir(parents=True, exist_ok=True)
OUTPUTS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AutoShorts Web API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
jobs: dict[str, dict] = {}

def command_version(binary: str) -> bool:
    return shutil.which(binary) is not None

def probe_duration(path: Path) -> float:
    if not command_version("ffprobe"):
        raise HTTPException(status_code=503, detail="FFprobe is missing. Run the Codespaces setup command: sudo apt-get update && sudo apt-get install -y ffmpeg.")
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail="Could not read this media file. Try an MP4 or MOV video.")
    try:
        return max(0.0, float(result.stdout.strip()))
    except ValueError:
        raise HTTPException(status_code=400, detail="Could not determine the video's duration.")

@app.get("/api/health")
def health():
    return {"ok": True, "ffmpeg": command_version("ffmpeg"), "ffprobe": command_version("ffprobe")}

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    name = Path(file.filename or "video.mp4").name
    suffix = Path(name).suffix.lower()
    if suffix not in {".mp4", ".mov", ".mkv", ".webm", ".m4v"}:
        raise HTTPException(status_code=400, detail="Supported video formats: MP4, MOV, MKV, WebM, M4V.")
    video_id = uuid.uuid4().hex
    target = UPLOADS / f"{video_id}{suffix}"
    total = 0
    max_bytes = 1024 * 1024 * 1024
    try:
        with target.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    target.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="Video exceeds the 1 GB prototype limit.")
                out.write(chunk)
    finally:
        await file.close()
    duration = probe_duration(target)
    if duration < 2:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Video is too short to create a clip.")
    clip_len = min(30.0, max(10.0, duration / 4))
    starts = sorted(set([0.0, max(0.0, duration * 0.33 - clip_len / 2), max(0.0, duration * 0.66 - clip_len / 2)]))
    candidates = []
    for i, start in enumerate(starts[:3], 1):
        end = min(duration, start + clip_len)
        candidates.append({"id": f"{video_id}-{i}", "start": round(start, 2), "end": round(end, 2), "title": f"Starter clip {i}", "note": "Timestamp suggestion based on video duration; not AI-selected."})
    jobs[video_id] = {"path": str(target), "filename": name, "duration": duration, "candidates": candidates}
    return {"video_id": video_id, "filename": name, "duration": duration, "candidates": candidates}

class RenderRequest(BaseModel):
    video_id: str
    candidate_id: str
    start: float
    end: float

@app.post("/api/render")
def render(request: RenderRequest):
    if not command_version("ffmpeg"):
        raise HTTPException(status_code=503, detail="FFmpeg is missing. Run the Codespaces setup command: sudo apt-get update && sudo apt-get install -y ffmpeg.")
    job = jobs.get(request.video_id)
    if not job:
        raise HTTPException(status_code=404, detail="Upload session not found. Please upload the video again.")
    candidate = next((c for c in job["candidates"] if c["id"] == request.candidate_id), None)
    if not candidate or abs(candidate["start"] - request.start) > 0.1 or abs(candidate["end"] - request.end) > 0.1:
        raise HTTPException(status_code=400, detail="Clip candidate is invalid.")
    if request.end <= request.start or request.end - request.start > 30.5:
        raise HTTPException(status_code=400, detail="Clip duration must be between 0 and 30 seconds.")
    output = OUTPUTS / f"{request.candidate_id}.mp4"
    command = ["ffmpeg", "-y", "-ss", str(request.start), "-i", job["path"], "-t", str(request.end - request.start), "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=900)
    if result.returncode != 0 or not output.exists():
        detail = (result.stderr or "FFmpeg render failed")[-1500:]
        raise HTTPException(status_code=500, detail=detail)
    return {"download_url": f"/api/download/{output.name}", "filename": output.name}

@app.get("/api/download/{filename}")
def download(filename: str):
    safe = Path(filename).name
    path = OUTPUTS / safe
    if not path.is_file() or path.suffix.lower() != ".mp4":
        raise HTTPException(status_code=404, detail="Rendered clip not found.")
    return FileResponse(path, media_type="video/mp4", filename=safe)
