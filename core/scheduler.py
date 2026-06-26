import os, json, time, threading, datetime
from pathlib import Path
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = os.path.join(BASE_DIR, "queue", "queue.json")
SCHEDULE_FILE = os.path.join(BASE_DIR, "queue", "schedule.json")

def _ensure_files():
    for f in [QUEUE_FILE, SCHEDULE_FILE]:
        if not Path(f).exists():
            with open(f, "w") as fp: json.dump([], fp)

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
        _ensure_files()
        q = _read_json(QUEUE_FILE)
        item = {
            "id": len(q) + 1,
            "url": url,
            "platforms": platforms or ["youtube"],
            "schedule_at": schedule_at,
            "title_template": title_template,
            "clip_duration": clip_duration,
            "min_dur": min_dur,
            "max_dur": clip_duration,
            "status": "pending",
            "added_at": datetime.datetime.now().isoformat(),
            "output_path": "",
            "error": ""
        }
        q.append(item)
        _write_json(QUEUE_FILE, q)
        print(f"[QUEUE] Ditambahkan: {url} -> {platforms}")
        return item["id"]

    @staticmethod
    def list():
        _ensure_files()
        return _read_json(QUEUE_FILE)

    @staticmethod
    def update(item_id: int, **kwargs):
        q = _read_json(QUEUE_FILE)
        for item in q:
            if item["id"] == item_id:
                item.update(kwargs)
                break
        _write_json(QUEUE_FILE, q)

    @staticmethod
    def get_pending():
        return [i for i in Queue.list() if i["status"] == "pending"]

    @staticmethod
    def clear_done():
        q = [i for i in Queue.list() if i["status"] != "done"]
        _write_json(QUEUE_FILE, q)

class ScheduleStore:
    @staticmethod
    def set(name: str, times: list):
        _ensure_files()
        sched = _read_json(SCHEDULE_FILE)
        sched[name] = {"times": times, "updated_at": datetime.datetime.now().isoformat()}
        _write_json(SCHEDULE_FILE, sched)
        print(f"[SCHEDULE] '{name}' diatur: {times}")

    @staticmethod
    def get(name: str) -> list:
        s = _read_json(SCHEDULE_FILE)
        return s.get(name, {}).get("times", [])

    @staticmethod
    def list_all():
        return _read_json(SCHEDULE_FILE)

    @staticmethod
    def delete(name: str):
        sched = _read_json(SCHEDULE_FILE)
        if name in sched:
            del sched[name]
            _write_json(SCHEDULE_FILE, sched)

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
                except: continue

            time.sleep(30)
