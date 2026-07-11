"""
VideoClipse — FastAPI Backend
Run: uvicorn backend:app --reload --host 0.0.0.0 --port 8000
"""
import os, time, uuid, json, shutil, threading, subprocess
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.downloader import VideoDownloader
from core.transcriber import AudioTranscriber, WordTimestamp
from core.finder import ViralMomentFinder, ProcessingResult
from core.editor import SubtitleGenerator, VideoProcessor, SUBTITLE_COLORS, ASPECT_PRESETS
from core.uploader import Uploader
from core.scheduler import Queue, ScheduleStore
from core.describer import generate_title, generate_description
import core.database as db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ACCOUNTS_DIR = os.path.join(BASE_DIR, "accounts")
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(title="VideoClipse API")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

jobs: dict[str, ProcessingResult] = {}
jobs_lock = threading.Lock()

class ProcessRequest(BaseModel):
    url: str
    moment_mode: str = "Rule-based (Cepat)"
    model_name: str = "llama3.2:latest"

class RenderRequest(BaseModel):
    job_id: str
    start: float
    end: float
    show_subtitles: bool = True
    subtitle_color: str = "Kuning"
    fade_in: float = 0.5
    fade_out: float = 0.8
    aspect: str = "Portrait 9:16 (Shorts/TikTok)"
    speed: str = "1.0x"
    mirror: bool = True
    color_preset: str = "none"
    noise_reduction: bool = True
    title: str = ""
    description: str = ""
    contrast: float = 1.0
    brightness: float = 0.0
    saturation: float = 1.0
    vignette: bool = False
    sepia: bool = False
    grayscale: bool = False
    sharpen: bool = False
    edge_detect: bool = False
    sub_size: int = 44
    sub_font: str = "Montserrat"
    sub_align: int = 5
    sub_upper: bool = True
    auto_post: bool = False
    remove_silence: bool = False
    silence_noise_thresh: str = "-30dB"
    silence_min_dur: float = 0.5
    jump_cut: bool = False
    jump_cut_thresh: float = 0.15

@app.get("/api/health")
def health():
    return {"status": "ok"}

def _process_job(job_id: str, url: str, wd: str, moment_mode: str, model_name: str):
    """Run processing in background thread."""
    from farm import _increment_today, _mark_link_done
    res = ProcessingResult()
    try:
        import yt_dlp
        try:
            with yt_dlp.YoutubeDL({"quiet":True,"no_warnings":True}) as ydl:
                info = ydl.extract_info(url, download=False)
        except:
            info = {}
        title = info.get("title", "Unknown")
        dur = info.get("duration", 0) or 0
        res.title = title
        res.duration = dur

        # max_dur: durasi asli video, capped 1800s (30 menit) untuk hindari timeout
        # Untuk video >30 menit, tool transkripsi 30 menit pertama yg paling padat konten
        max_audio = min(dur or 1800, 1800)
        audio, _, _ = VideoDownloader.download_audio(url, wd, max_dur=max_audio)
        if audio and Path(audio).exists():
            res.audio_path = audio
            text, wts = AudioTranscriber.transcribe(audio)
            if text:
                res.transcript = text
                res.word_timestamps = wts

        use_llm = moment_mode == "Llama AI (Pintar)"
        res.viral_moments = ViralMomentFinder.find_moments(
            res.transcript or "", dur, res.word_timestamps,
            use_llm=use_llm, model_name=model_name
        )

        vp = VideoDownloader.download_video_clip(url, wd, 0, min(dur+5, 600))
        if vp:
            res.video_path = vp

        with jobs_lock:
            jobs[job_id] = res
    except Exception as e:
        res.error = str(e)
        with jobs_lock:
            jobs[job_id] = res

@app.post("/api/process")
def start_process(req: ProcessRequest):
    job_id = uuid.uuid4().hex[:12]
    wd = os.path.join(OUTPUT_DIR, f"job_{job_id}")
    os.makedirs(wd, exist_ok=True)
    with jobs_lock:
        jobs[job_id] = ProcessingResult(title="Processing...")
    threading.Thread(target=_process_job, args=(job_id, req.url, wd, req.moment_mode, req.model_name), daemon=True).start()
    return {"job_id": job_id}

@app.post("/api/process-local")
async def process_local(file: UploadFile = File(...), moment_mode: str = Form("Rule-based (Cepat)"), model_name: str = Form("llama3.2:latest")):
    job_id = uuid.uuid4().hex[:12]
    wd = os.path.join(OUTPUT_DIR, f"job_{job_id}")
    os.makedirs(wd, exist_ok=True)
    ext = file.filename.rsplit(".",1)[-1].lower()
    lp = os.path.join(wd, f"up_{uuid.uuid4().hex[:8]}.{ext}")
    content = await file.read()
    with open(lp, "wb") as f:
        f.write(content)

    res = ProcessingResult()
    try:
        audio, dur = VideoDownloader.extract_audio_from_local(lp, wd)
        if not audio:
            raise Exception("Gagal extract audio")
        res.audio_path = audio
        res.title = file.filename or "video.mp4"
        res.duration = dur
        res.video_path = lp

        text, wts = AudioTranscriber.transcribe(audio)
        if text:
            res.transcript = text
            res.word_timestamps = wts

        use_llm = moment_mode == "Llama AI (Pintar)"
        res.viral_moments = ViralMomentFinder.find_moments(
            res.transcript or "", dur, wts,
            use_llm=use_llm, model_name=model_name
        )
    except Exception as e:
        res.error = str(e)

    with jobs_lock:
        jobs[job_id] = res
    return {"job_id": job_id}

@app.get("/api/job/{job_id}")
def get_job(job_id: str):
    with jobs_lock:
        res = jobs.get(job_id)
    if not res:
        raise HTTPException(404, "Job not found")
    return {
        "title": res.title,
        "duration": res.duration,
        "transcript": res.transcript,
        "video_path": res.video_path,
        "error": res.error,
        "moments": [
            {"start_time": m.start_time, "end_time": m.end_time,
             "reason": m.reason, "category": m.category,
             "transcript_snippet": m.transcript_snippet}
            for m in res.viral_moments
        ],
        "done": not res.error and (res.transcript != "" or res.error != "" or res.duration > 0),
    }

@app.post("/api/render")
def render_clip(req: RenderRequest):
    with jobs_lock:
        res = jobs.get(req.job_id)
    if not res:
        raise HTTPException(404, "Job not found")

    wd = os.path.join(OUTPUT_DIR, f"render_{uuid.uuid4().hex[:8]}")
    os.makedirs(wd, exist_ok=True)
    cid = uuid.uuid4().hex[:8]
    out = os.path.join(wd, f"out_{cid}.mp4")
    sub_path = os.path.join(wd, f"subs_{cid}.ass")

    try:
        speed = {"1.0x":1.0,"1.05x":1.05,"1.07x":1.07,"1.1x":1.1,"1.15x":1.15}.get(req.speed, 1.0)
        clip_path = res.video_path
        if not clip_path or not Path(clip_path).exists():
            raise Exception("No video source")

        if req.show_subtitles and res.word_timestamps:
            rel = [wt for wt in res.word_timestamps if wt.start<req.end and wt.end>req.start]
            if rel:
                shifted = [WordTimestamp(w.word, max(0,w.start-req.start), w.end-req.start) for w in rel]
                SubtitleGenerator.generate_ass(shifted, sub_path,
                    SUBTITLE_COLORS.get(req.subtitle_color,"&H00FFFF&"),
                    font=req.sub_font, size=req.sub_size,
                    alignment=req.sub_align, uppercase=req.sub_upper)

        ok, err = VideoProcessor.process_clip(
            clip_path, out,
            sub_path if Path(sub_path).exists() else "", "",
            0, req.end-req.start, req.fade_in, req.fade_out,
            speed, req.mirror, req.color_preset, req.noise_reduction,
            aspect=req.aspect,
            contrast=req.contrast, brightness=req.brightness, saturation=req.saturation,
            vignette=req.vignette, sepia=req.sepia, grayscale=req.grayscale,
            sharpen=req.sharpen, edge_detect=req.edge_detect,
            remove_silence=req.remove_silence,
            silence_noise_thresh=req.silence_noise_thresh,
            silence_min_dur=req.silence_min_dur,
            jump_cut=req.jump_cut,
            jump_cut_thresh=req.jump_cut_thresh
        )
        if not ok:
            raise Exception(err)

        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in req.title)[:30]
        ts = time.strftime("%Y%m%d_%H%M%S")
        final_name = f"{ts}_{safe_title}.mp4"
        final_path = os.path.join(OUTPUT_DIR, final_name)
        shutil.copy2(out, final_path)

        if req.auto_post:
            connected = []
            for plat in ["youtube","tiktok","facebook"]:
                cfile = os.path.join(ACCOUNTS_DIR, plat, "cookies.json")
                if Path(cfile).exists():
                    connected.append(plat)
            if connected:
                def bg_upload():
                    for p in connected:
                        try:
                            Uploader.upload(p, final_path, req.title, req.description)
                        except Exception as ex:
                            print(f"[AUTO POST ERROR] {p}: {ex}")
                threading.Thread(target=bg_upload, daemon=True).start()

        return {"path": final_path, "name": final_name, "size_mb": round(Path(final_path).stat().st_size/(1024*1024), 1)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/clips")
def list_clips(page: int = Query(1, ge=1)):
    videos = sorted(Path(OUTPUT_DIR).glob("*.mp4"), key=os.path.getmtime, reverse=True)
    per_page = 8
    total = len(videos)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    end = min(start + per_page, total)
    items = []
    for v in videos[start:end]:
        meta_path = str(v) + ".json"
        meta = {}
        if Path(meta_path).exists():
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
            except: pass
        items.append({
            "name": v.name,
            "path": str(v),
            "size_mb": round(v.stat().st_size/(1024*1024), 1),
            "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(v.stat().st_mtime)),
            "title": meta.get("title", ""),
            "description": meta.get("description", ""),
            "tags": meta.get("tags", []),
            "hashtags": meta.get("hashtags", ""),
            "source_url": meta.get("source_url", ""),
            "duration": meta.get("duration", 0),
        })
    return {"items": items, "page": page, "total_pages": total_pages, "total": total}

@app.delete("/api/clips/{name}")
def delete_clip(name: str):
    path = Path(OUTPUT_DIR) / name
    if path.exists():
        path.unlink()
    meta = path.with_suffix(".mp4.json")
    if meta.exists():
        meta.unlink()
    return {"status": "deleted"}

@app.get("/api/video/{name}")
def serve_video(name: str):
    path = Path(OUTPUT_DIR) / name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(str(path), media_type="video/mp4")

def _account_status(platform: str):
    cfile = os.path.join(ACCOUNTS_DIR, platform.lower(), "cookies.json")
    if Path(cfile).exists():
        try:
            with open(cfile) as f:
                c = json.load(f)
            return "connected", f"{len(c)} cookies"
        except:
            return "error", "file error"
    return "disconnected", "not logged in"

@app.get("/api/accounts")
def list_accounts():
    result = {}
    for plat in ["youtube","tiktok","facebook"]:
        sts, msg = _account_status(plat)
        result[plat] = {"status": sts, "message": msg}
    return result

class CookiesSaveRequest(BaseModel):
    platform: str
    cookies: list

@app.post("/api/accounts/cookies")
def save_cookies(req: CookiesSaveRequest):
    try:
        Uploader.save_cookies(req.platform, req.cookies)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/accounts/login/{platform}")
def trigger_login(platform: str):
    subprocess.Popen(f'start cmd /c python farm.py --login {platform}', shell=True)
    return {"status": "login_triggered"}

@app.post("/api/accounts/logout/{platform}")
def logout(platform: str):
    cfile = os.path.join(ACCOUNTS_DIR, platform.lower(), "cookies.json")
    if Path(cfile).exists():
        Path(cfile).unlink()
    return {"status": "logged_out"}

@app.get("/api/queue")
def list_queue():
    return Queue.list()

class QueueEditRequest(BaseModel):
    item_id: int
    url: Optional[str] = None
    platforms: Optional[list] = None
    schedule_at: Optional[str] = None

@app.post("/api/queue/edit")
def edit_queue(req: QueueEditRequest):
    updates = {}
    if req.url is not None: updates["url"] = req.url
    if req.platforms is not None: updates["platforms"] = req.platforms
    if req.schedule_at is not None: updates["schedule_at"] = req.schedule_at
    Queue.update(req.item_id, **updates)
    return {"status": "ok"}

@app.delete("/api/queue/{item_id}")
def delete_queue(item_id: int):
    from core.scheduler import _read_json, _write_json, QUEUE_FILE
    qq = _read_json(QUEUE_FILE)
    qq = [i for i in qq if i["id"] != item_id]
    _write_json(QUEUE_FILE, qq)
    return {"status": "deleted"}

@app.post("/api/queue/clear-done")
def clear_queue_done():
    Queue.clear_done()
    return {"status": "ok"}

@app.get("/api/schedule")
def list_schedules():
    return ScheduleStore.list_all()

class ScheduleSetRequest(BaseModel):
    name: str
    times: list

@app.post("/api/schedule")
def set_schedule(req: ScheduleSetRequest):
    ScheduleStore.set(req.name, req.times)
    return {"status": "ok"}

@app.delete("/api/schedule/{name}")
def delete_schedule(name: str):
    ScheduleStore.delete(name)
    return {"status": "deleted"}

@app.get("/api/stats")
def get_stats():
    from farm import _today_count
    count = _today_count()
    return {
        "uploaded_today": count,
        "remaining": max(0, 10 - count),
        "in_queue": len(Queue.list()),
        "total_clips": len(list(Path(OUTPUT_DIR).glob("*.mp4"))),
    }

@app.get("/api/recent-clips")
def recent_clips(limit: int = 3):
    videos = sorted(Path(OUTPUT_DIR).glob("*.mp4"), key=os.path.getmtime, reverse=True)[:limit]
    items = []
    for v in videos:
        items.append({
            "name": v.name,
            "size_mb": round(v.stat().st_size/(1024*1024), 1),
            "mtime": time.strftime("%b %d, %H:%M", time.localtime(v.stat().st_mtime)),
        })
    return items

@app.post("/api/cleanup")
def trigger_cleanup():
    """Delete video files where all platforms are done uploading."""
    try:
        db.clips_cleanup_uploaded()
        return {"status": "cleaned"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/status")
def server_status():
    return {
        "mode": "cloud" if db.is_cloud() else "local",
        "clips": len(db.clips_list()),
        "queue": len(db.queue_list()),
    }

class UploadRequest(BaseModel):
    platform: str
    path: str
    title: str = ""
    description: str = ""

@app.post("/api/upload")
def upload_clip(req: UploadRequest):
    from core.uploader import Uploader
    try:
        clip_name = req.path.split("/")[-1]
        clip_path = os.path.join(OUTPUT_DIR, clip_name)
        if not Path(clip_path).exists():
            raise HTTPException(404, "Clip not found")
        Uploader.upload(req.platform, clip_path, req.title, req.description)
        # Track upload status
        clip_id = Path(clip_path).stem
        db.clip_update_upload_status(clip_id, req.platform, "done")
        db.stats_increment_today()
        # HAPUS file segera setelah upload berhasil (sekali pakai)
        try:
            Path(clip_path).unlink(missing_ok=True)
            print(f"[CLEANUP] File dihapus setelah upload: {clip_path}")
            # Hapus juga file JSON metadata jika ada
            meta = clip_path + ".json"
            if Path(meta).exists():
                Path(meta).unlink(missing_ok=True)
        except Exception as cleanup_e:
            print(f"[CLEANUP] Gagal hapus file: {cleanup_e}")
        return {"status": "uploaded"}
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Brand Templates ───────────────────────────────────────────────
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
os.makedirs(TEMPLATES_DIR, exist_ok=True)

@app.get("/api/templates")
def list_templates():
    templates = []
    for f in sorted(Path(TEMPLATES_DIR).glob("*.json"), key=os.path.getmtime, reverse=True):
        try:
            with open(f) as fp:
                data = json.load(fp)
            data["name"] = f.stem
            templates.append(data)
        except:
            pass
    return templates

class BrandTemplate(BaseModel):
    name: str
    subtitle_font: str = "Montserrat"
    subtitle_size: int = 44
    subtitle_color: str = "Kuning"
    subtitle_align: int = 5
    subtitle_upper: bool = True
    color_preset: str = "none"
    aspect: str = "Portrait 9:16 (Shorts/TikTok)"
    contrast: float = 1.0
    brightness: float = 0.0
    saturation: float = 1.0
    remove_silence: bool = True
    watermark_text: str = ""

@app.post("/api/templates")
def save_template(req: BrandTemplate):
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in req.name)[:30]
    path = os.path.join(TEMPLATES_DIR, f"{safe_name}.json")
    with open(path, "w") as f:
        json.dump(req.model_dump(), f, indent=2)
    return {"status": "saved", "name": safe_name}

@app.delete("/api/templates/{name}")
def delete_template(name: str):
    path = os.path.join(TEMPLATES_DIR, f"{name}.json")
    if Path(path).exists():
        Path(path).unlink()
    return {"status": "deleted"}

# ── GPU Status ──────────────────────────────────────────────────────
@app.get("/api/gpu")
def get_gpu_status():
    from core.transcriber import AudioTranscriber
    return AudioTranscriber.check_gpu()


from fastapi.responses import RedirectResponse

@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
