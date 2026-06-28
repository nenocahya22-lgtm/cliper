"""
Database abstraction layer.
Local mode  -> JSON files (existing behavior, no config needed)
Cloud mode  -> Supabase (set SUPABASE_URL + SUPABASE_KEY in .env or secrets)

Multi-device sync: when cloud mode is active, all data is read/written
via Supabase so every device sees the same data in real time.
"""
import os, json, time, threading
from pathlib import Path
from datetime import datetime
from typing import Optional

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
QUEUE_DIR = BASE_DIR / "queue"
ACCOUNTS_DIR = BASE_DIR / "accounts"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(QUEUE_DIR, exist_ok=True)

# ── Supabase (optional) ─────────────────────────────────────
_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
_SUPABASE = None
_SUPABASE_LOCK = threading.Lock()

def _get_supabase():
    global _SUPABASE
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        return None
    if _SUPABASE is None:
        with _SUPABASE_LOCK:
            if _SUPABASE is None:
                try:
                    from supabase import create_client
                    _SUPABASE = create_client(_SUPABASE_URL, _SUPABASE_KEY)
                except Exception as e:
                    print(f"[DB] Supabase init failed: {e}")
                    return None
    return _SUPABASE

def is_cloud() -> bool:
    return _get_supabase() is not None

# ── Local JSON helpers ─────────────────────────────────────
def _local_read(path: str):
    if not Path(path).exists():
        return None
    with open(path) as f:
        return json.load(f)

def _local_write(path: str, data):
    os.makedirs(Path(path).parent, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# ── Public API ─────────────────────────────────────────────

## Queue
def queue_add(item: dict) -> int:
    sb = _get_supabase()
    if sb:
        item["created_at"] = datetime.utcnow().isoformat()
        item["updated_at"] = item["created_at"]
        r = sb.table("queue").insert(item).execute()
        return r.data[0]["id"] if r.data else 0
    q = _local_read(str(QUEUE_DIR / "queue.json")) or []
    item["id"] = (q[-1]["id"] + 1) if q else 1
    item["created_at"] = datetime.utcnow().isoformat()
    q.append(item)
    _local_write(str(QUEUE_DIR / "queue.json"), q)
    return item["id"]

def queue_list() -> list:
    sb = _get_supabase()
    if sb:
        r = sb.table("queue").select("*").order("created_at", desc=True).execute()
        return r.data or []
    return _local_read(str(QUEUE_DIR / "queue.json")) or []

def queue_update(item_id: int, **kwargs):
    sb = _get_supabase()
    if sb:
        kwargs["updated_at"] = datetime.utcnow().isoformat()
        sb.table("queue").update(kwargs).eq("id", item_id).execute()
        return
    q = _local_read(str(QUEUE_DIR / "queue.json")) or []
    for item in q:
        if item["id"] == item_id:
            item.update(kwargs)
            break
    _local_write(str(QUEUE_DIR / "queue.json"), q)

def queue_delete(item_id: int):
    sb = _get_supabase()
    if sb:
        sb.table("queue").delete().eq("id", item_id).execute()
        return
    q = _local_read(str(QUEUE_DIR / "queue.json")) or []
    q = [i for i in q if i["id"] != item_id]
    _local_write(str(QUEUE_DIR / "queue.json"), q)


def queue_get(item_id: int) -> dict:
    """Get single queue item by ID."""
    sb = _get_supabase()
    if sb:
        r = sb.table("queue").select("*").eq("id", item_id).execute()
        return r.data[0] if r.data else {}
    q = _local_read(str(QUEUE_DIR / "queue.json")) or []
    for item in q:
        if item["id"] == item_id:
            return item
    return {}

def queue_clear_done():
    sb = _get_supabase()
    if sb:
        sb.table("queue").delete().eq("status", "done").execute()
        return
    q = _local_read(str(QUEUE_DIR / "queue.json")) or []
    q = [i for i in q if i["status"] != "done"]
    _local_write(str(QUEUE_DIR / "queue.json"), q)

## Schedule
def schedule_set(name: str, times: list):
    sb = _get_supabase()
    if sb:
        data = {"name": name, "times": times, "updated_at": datetime.utcnow().isoformat()}
        existing = sb.table("schedules").select("*").eq("name", name).execute()
        if existing.data:
            sb.table("schedules").update(data).eq("name", name).execute()
        else:
            sb.table("schedules").insert(data).execute()
        return
    sched = _local_read(str(QUEUE_DIR / "schedule.json")) or {}
    sched[name] = {"times": times, "updated_at": datetime.utcnow().isoformat()}
    _local_write(str(QUEUE_DIR / "schedule.json"), sched)

def schedule_get(name: str) -> list:
    sb = _get_supabase()
    if sb:
        r = sb.table("schedules").select("times").eq("name", name).execute()
        return r.data[0]["times"] if r.data else []
    sched = _local_read(str(QUEUE_DIR / "schedule.json")) or {}
    return sched.get(name, {}).get("times", [])

def schedule_list_all() -> dict:
    sb = _get_supabase()
    if sb:
        r = sb.table("schedules").select("*").execute()
        return {item["name"]: item for item in (r.data or [])}
    return _local_read(str(QUEUE_DIR / "schedule.json")) or {}

def schedule_delete(name: str):
    sb = _get_supabase()
    if sb:
        sb.table("schedules").delete().eq("name", name).execute()
        return
    sched = _local_read(str(QUEUE_DIR / "schedule.json")) or {}
    sched.pop(name, None)
    _local_write(str(QUEUE_DIR / "schedule.json"), sched)

## Stats
def stats_get_today() -> dict:
    today = time.strftime("%Y-%m-%d")
    sb = _get_supabase()
    if sb:
        r = sb.table("stats").select("*").eq("date", today).execute()
        if r.data:
            return r.data[0]
        return {"date": today, "uploaded": 0, "links": []}
    stats = _local_read(str(QUEUE_DIR / "stats.json")) or {"dates": {}}
    return stats.get("dates", {}).get(today, {"uploaded": 0, "links": []})

def stats_increment_today(link: str = ""):
    today = time.strftime("%Y-%m-%d")
    sb = _get_supabase()
    if sb:
        existing = sb.table("stats").select("*").eq("date", today).execute()
        if existing.data:
            row = existing.data[0]
            links = row.get("links", [])
            if link and link not in links:
                links.append(link)
            sb.table("stats").update({"uploaded": row["uploaded"] + 1, "links": links}).eq("date", today).execute()
        else:
            sb.table("stats").insert({"date": today, "uploaded": 1, "links": [link] if link else []}).execute()
        return
    stats = _local_read(str(QUEUE_DIR / "stats.json")) or {"dates": {}}
    if "dates" not in stats: stats["dates"] = {}
    if today not in stats["dates"]:
        stats["dates"][today] = {"uploaded": 0, "links": []}
    stats["dates"][today]["uploaded"] += 1
    if link and link not in stats["dates"][today]["links"]:
        stats["dates"][today]["links"].append(link)
    _local_write(str(QUEUE_DIR / "stats.json"), stats)

def stats_today_count() -> int:
    return stats_get_today().get("uploaded", 0)

def stats_today_links() -> list:
    return stats_get_today().get("links", [])

## Clips / output tracking
def clip_save(path: str, title: str = "", description: str = "", source_url: str = "",
              duration: float = 0, platforms: list = None, user_id: str = ""):
    sb = _get_supabase()
    record = {
        "path": path,
        "name": Path(path).name,
        "title": title,
        "description": description,
        "source_url": source_url,
        "duration": duration,
        "platforms": platforms or [],
        "upload_status": {},  # {"youtube": "pending", "tiktok": "done", ...}
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
        "file_size": Path(path).stat().st_size if Path(path).exists() else 0,
    }
    if sb:
        r = sb.table("clips").insert(record).execute()
        return r.data[0]["id"] if r.data else None
    meta_path = path + ".json"
    _local_write(meta_path, record)
    return meta_path

def clip_update_upload_status(clip_id, platform: str, status: str):
    sb = _get_supabase()
    if sb:
        r = sb.table("clips").select("upload_status").eq("id", clip_id).execute()
        if r.data:
            us = dict(r.data[0].get("upload_status", {}))
            us[platform] = status
            sb.table("clips").update({"upload_status": us}).eq("id", clip_id).execute()
        return
    # Local: find by path + ".json"
    meta_path = str(Path(DATA_DIR) / f"clip_{clip_id}.json")
    rec = _local_read(meta_path)
    if rec:
        rec.setdefault("upload_status", {})[platform] = status
        _local_write(meta_path, rec)

def clips_list(user_id: str = "") -> list:
    sb = _get_supabase()
    if sb:
        q = sb.table("clips").select("*").order("created_at", desc=True)
        if user_id:
            q = q.eq("user_id", user_id)
        r = q.execute()
        return r.data or []
    out_dir = BASE_DIR / "output"
    results = []
    for f in sorted(out_dir.glob("*.mp4"), key=os.path.getmtime, reverse=True):
        meta = {}
        meta_p = str(f) + ".json"
        if Path(meta_p).exists():
            try: meta = json.loads(Path(meta_p).read_text())
            except: pass
        results.append({
            "id": meta.get("id", f.stem),
            "name": f.name,
            "path": str(f),
            "title": meta.get("title", ""),
            "description": meta.get("description", ""),
            "source_url": meta.get("source_url", ""),
            "duration": meta.get("duration", 0),
            "platforms": meta.get("platforms", []),
            "upload_status": meta.get("upload_status", {}),
            "file_size": f.stat().st_size,
            "created_at": meta.get("created_at", time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime))),
        })
    return results

def clip_delete(clip_id):
    sb = _get_supabase()
    if sb:
        r = sb.table("clips").select("path").eq("id", clip_id).execute()
        if r.data:
            path = r.data[0].get("path", "")
            if path and Path(path).exists():
                Path(path).unlink(missing_ok=True)
            meta_p = path + ".json"
            if Path(meta_p).exists():
                Path(meta_p).unlink(missing_ok=True)
        sb.table("clips").delete().eq("id", clip_id).execute()
        return
    # Local: find by path matching
    out_dir = BASE_DIR / "output"
    for f in out_dir.glob("*.mp4"):
        meta_p = str(f) + ".json"
        if Path(meta_p).exists():
            try:
                meta = json.loads(Path(meta_p).read_text())
                if meta.get("id") == clip_id or f.stem == clip_id:
                    f.unlink(missing_ok=True)
                    Path(meta_p).unlink(missing_ok=True)
                    return
            except: pass

def clips_cleanup_uploaded():
    """Delete video files where all platforms are done uploading."""
    sb = _get_supabase()
    if sb:
        r = sb.table("clips").select("*").execute()
        for clip in (r.data or []):
            us = clip.get("upload_status", {})
            platforms = clip.get("platforms", [])
            if platforms and all(us.get(p) == "done" for p in platforms):
                path = clip.get("path", "")
                if path and Path(path).exists():
                    Path(path).unlink(missing_ok=True)
                    print(f"[CLEANUP] Deleted: {path}")
                sb.table("clips").update({"path": "", "file_size": 0}).eq("id", clip["id"]).execute()
        return
    for clip in clips_list():
        us = clip.get("upload_status", {})
        platforms = clip.get("platforms", [])
        if platforms and all(us.get(p) == "done" for p in platforms):
            path = clip.get("path", "")
            if path and Path(path).exists():
                Path(path).unlink(missing_ok=True)
                print(f"[CLEANUP] Deleted: {path}")
            meta_p = path + ".json" if path else ""
            if meta_p and Path(meta_p).exists():
                try:
                    meta = json.loads(Path(meta_p).read_text())
                    meta["path"] = ""
                    meta["file_size"] = 0
                    _local_write(meta_p, meta)
                except: pass

## User accounts (cookies)
def accounts_save_cookies(platform: str, cookies: list):
    path = ACCOUNTS_DIR / platform.lower() / "cookies.json"
    os.makedirs(path.parent, exist_ok=True)
    with open(path, "w") as f:
        json.dump(cookies, f, indent=2)

def accounts_load_cookies(platform: str) -> list:
    path = ACCOUNTS_DIR / platform.lower() / "cookies.json"
    if not path.exists(): return []
    with open(path) as f:
        return json.load(f)

def accounts_status(platform: str):
    cfile = ACCOUNTS_DIR / platform.lower() / "cookies.json"
    if cfile.exists():
        try:
            with open(cfile) as f:
                c = json.load(f)
            return "connected", f"{len(c)} cookies"
        except: return "error", "file error"
    return "disconnected", "not logged in"
