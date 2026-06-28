import os, json, time, threading, datetime
from pathlib import Path
from typing import Optional

import core.database as db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = os.path.join(BASE_DIR, "queue", "queue.json")
SCHEDULE_FILE = os.path.join(BASE_DIR, "queue", "schedule.json")

def _ensure_files():
    for f in [QUEUE_FILE, SCHEDULE_FILE]:
        if not Path(f).exists():
            default = [] if f == QUEUE_FILE else {}
            with open(f, "w") as fp: json.dump(default, fp)

def _read_json(path):
    with open(path) as f:
        return json.load(f)

def _write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

class Queue:
    @staticmethod
    def add(url: str, platforms: list = None, schedule_at: str = "",
            title_template: str = "", clip_duration: int = 45, min_dur: int = 30):
        item = {
            "url": url,
            "platforms": platforms or ["youtube"],
            "schedule_at": schedule_at,
            "title_template": title_template,
            "clip_duration": clip_duration,
            "min_dur": min_dur,
            "max_dur": clip_duration,
            "status": "pending",
            "output_path": "",
            "error": ""
        }
        return db.queue_add(item)

    @staticmethod
    def list():
        return db.queue_list()

    @staticmethod
    def update(item_id: int, **kwargs):
        db.queue_update(item_id, **kwargs)

    @staticmethod
    def get_pending():
        return [i for i in db.queue_list() if i.get("status") == "pending"]

    @staticmethod
    def delete(item_id: int):
        db.queue_delete(item_id)

    @staticmethod
    def get(item_id: int) -> dict:
        return db.queue_get(item_id)

    @staticmethod
    def clear_done():
        db.queue_clear_done()

class ScheduleStore:
    @staticmethod
    def set(name: str, times: list):
        db.schedule_set(name, times)
        print(f"[SCHEDULE] '{name}' diatur: {times}")

    @staticmethod
    def get(name: str) -> list:
        return db.schedule_get(name)

    @staticmethod
    def list_all():
        return db.schedule_list_all()

    @staticmethod
    def delete(name: str):
        db.schedule_delete(name)

class SchedulerEngine:
    def __init__(self, process_callback=None):
        self._running = False
        self._thread = None
        self._process_callback = process_callback

    def start(self):
        if self._running: return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[SCHEDULER] Engine started")

    def stop(self):
        self._running = False

    def _loop(self):
        processed_today = set()
        while self._running:
            now = datetime.datetime.now()
            today_key = now.strftime("%Y-%m-%d")

            q = Queue.get_pending()
            for item in q:
                sched_time = item.get("schedule_at", "")
                if not sched_time:
                    continue
                try:
                    target = datetime.datetime.strptime(f"{today_key} {sched_time}", "%Y-%m-%d %H:%M")
                    if now >= target and (item["id"], today_key) not in processed_today:
                        processed_today.add((item["id"], today_key))
                        if self._process_callback:
                            try:
                                self._process_callback(item)
                                Queue.update(item["id"], status="done")
                            except Exception as e:
                                Queue.update(item["id"], status="error", error=str(e))
                except:
                    continue

            # Auto-cleanup: delete video files after all platforms done
            try:
                db.clips_cleanup_uploaded()
            except:
                pass

            time.sleep(30)
