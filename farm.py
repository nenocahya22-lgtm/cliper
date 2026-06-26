#!/usr/bin/env python3
"""
FARM MODE - VideoClipse Farming Tool
=====================================
Cara pakai:
  python farm.py https://youtu.be/xxx              # Langsung proses + simpan
  python farm.py --queue https://... --schedule 14:00 --max-daily 5
  python farm.py --daemon                           # Jalankan scheduler
  python farm.py --login youtube                    # Login (simpan cookies)
  python farm.py --list                             # Lihat antrian
  python farm.py --schedule harian 08:00,12:00,18:00
  python farm.py --stats                           # Statistik hari ini
"""

import os, sys, time, json, argparse, warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
QUEUE_DIR = os.path.join(BASE_DIR, "queue")
STATS_FILE = os.path.join(QUEUE_DIR, "stats.json")
SCHEDULE_FILE = os.path.join(QUEUE_DIR, "schedule.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(QUEUE_DIR, exist_ok=True)

def _load_stats():
    if not Path(STATS_FILE).exists():
        return {"dates": {}}
    with open(STATS_FILE) as f:
        return json.load(f)

def _save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

def _today_count():
    today = time.strftime("%Y-%m-%d")
    stats = _load_stats()
    return stats.get("dates", {}).get(today, {}).get("uploaded", 0)

def _increment_today():
    today = time.strftime("%Y-%m-%d")
    stats = _load_stats()
    if "dates" not in stats: stats["dates"] = {}
    if today not in stats["dates"]:
        stats["dates"][today] = {"uploaded": 0, "links": []}
    stats["dates"][today]["uploaded"] += 1
    _save_stats(stats)

def _load_schedule():
    if not Path(SCHEDULE_FILE).exists():
        return {}
    with open(SCHEDULE_FILE) as f:
        return json.load(f)

def _today_uploaded_links():
    today = time.strftime("%Y-%m-%d")
    stats = _load_stats()
    return stats.get("dates", {}).get(today, {}).get("links", [])

def _mark_link_done(url):
    today = time.strftime("%Y-%m-%d")
    stats = _load_stats()
    if "dates" not in stats: stats["dates"] = {}
    if today not in stats["dates"]:
        stats["dates"][today] = {"uploaded": 0, "links": []}
    stats["dates"][today]["links"].append(url)
    _save_stats(stats)

def process_one(url: str, min_dur: int = 30, max_dur: int = 60, platforms: list = None,
                with_subtitle: bool = True, subtitle_color: str = "Kuning",
                add_watermark: bool = False, watermark_path: str = "",
                no_upload: bool = False, anti_copy: bool = True):
    """Proses satu link: download -> transkrip -> cari momen -> edit -> output"""
    from core.editor import VideoProcessor

    work_dir = os.path.join(BASE_DIR, "output", f"work_{int(time.time())}")
    print(f"[PROCESS] Memproses: {url}")
    print(f"[PROCESS] Range durasi: {min_dur}-{max_dur}s")
    if anti_copy:
        print("[PROCESS] Anti-copyright: ON (speed+mirror+color+noise random)")

    ok, out_path, title, reason, clip_dur, text, moments = VideoProcessor.auto_process(
        url, work_dir, min_dur, max_dur,
        with_subtitle, subtitle_color,
        add_watermark, watermark_path,
        anti_copy=anti_copy
    )

    if not ok:
        print(f"[ERROR] {out_path}")
        return None

    # Generate judul + deskripsi dari transkrip via Ollama (+ fallback heuristic)
    from core.describer import generate_title, generate_description, generate_tags, generate_hashtag_string

    if not text: text = title
    judul = generate_title(text, title, moments)
    deskripsi = generate_description(text, judul, title, moments)
    tags = generate_tags(text, title)
    hashtags = generate_hashtag_string(text, title)

    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)[:40]
    ts = time.strftime("%Y%m%d_%H%M%S")
    final_name = f"{ts}_{safe_title}.mp4"
    final_path = os.path.join(OUTPUT_DIR, final_name)

    import shutil
    shutil.copy2(out_path, final_path)
    print(f"[OK] {final_path}")
    print(f"[INFO] Durasi: {clip_dur:.0f}s")
    print(f"[INFO] Judul : {judul}")
    print(f"[INFO] Tags  : {hashtags}")

    # Simpan metadata
    meta_path = final_path + ".json"
    with open(meta_path, "w") as f:
        json.dump({"title": judul, "description": deskripsi, "tags": tags,
                   "hashtags": hashtags,
                   "source_url": url, "duration": clip_dur, "reason": reason,
                   "created_at": ts}, f, indent=2)

    if no_upload:
        return final_path

    # Upload jika diminta
    if platforms:
        from core.uploader import Uploader
        for plat in platforms:
            try:
                print(f"[UPLOAD] Mengupload ke {plat}...")
                Uploader.upload(plat, final_path, judul, deskripsi)
                print(f"[UPLOAD] Berhasil ke {plat}")
                _increment_today()
                _mark_link_done(url)
            except Exception as e:
                print(f"[UPLOAD] Gagal ke {plat}: {e}")

    return final_path

def watch_loop(max_daily: int = 10):
    """Watch folder untuk file .txt yang berisi link"""
    watch_dir = os.path.join(BASE_DIR, "queue", "links")
    os.makedirs(watch_dir, exist_ok=True)
    print(f"[WATCH] Memantau folder: {watch_dir}")
    print(f"[WATCH] Max upload/hari: {max_daily}")
    print("[WATCH] Taruh file .txt berisi link (1 link/baris)")

    processed = set()
    while True:
        count_today = _today_count()
        if count_today >= max_daily:
            time.sleep(60)
            continue

        for f in sorted(Path(watch_dir).glob("*.txt")):
            if f.name in processed: continue
            links = [l.strip() for l in f.read_text().strip().split("\n") if l.strip() and not l.startswith("#")]
            for link in links:
                if _today_count() >= max_daily:
                    print(f"[WATCH] Limit {max_daily}/hari tercapai. Sisanya besok.")
                    break
                already = _today_uploaded_links()
                if link in already:
                    print(f"[WATCH] Skip (already done): {link}")
                    continue
                print(f"[WATCH] Link baru: {link}")
                process_one(link)
            processed.add(f.name)
            f.rename(f.with_suffix(".done"))

        time.sleep(10)

def main():
    parser = argparse.ArgumentParser(description="VideoClipse Farming Tool")
    parser.add_argument("url", nargs="?", help="Link video")
    parser.add_argument("--queue", action="store_true", help="Tambah ke antrian")
    parser.add_argument("--platform", nargs="*", default=[], help="Platform tujuan (youtube tiktok facebook)")
    parser.add_argument("--schedule", default="", help="Jadwal upload (format: HH:MM)")
    parser.add_argument("--min-dur", type=int, default=30, help="Durasi minimal (detik)")
    parser.add_argument("--max-dur", type=int, default=60, help="Durasi maksimal (detik)")
    parser.add_argument("--max-daily", type=int, default=10, help="Max upload per hari")
    parser.add_argument("--daemon", action="store_true", help="Jalankan scheduler")
    parser.add_argument("--login", help="Login ke platform (youtube/tiktok/facebook)")
    parser.add_argument("--list", action="store_true", help="Lihat antrian")
    parser.add_argument("--watch", action="store_true", help="Watch folder queue/links/")
    parser.add_argument("--set-schedule", nargs=2, metavar=("NAMA", "JAM"), help="Set jadwal (contoh: harian 08:00,12:00,18:00)")
    parser.add_argument("--stats", action="store_true", help="Statistik upload hari ini")
    parser.add_argument("--no-upload", action="store_true", help="Proses aja, jangan upload")
    parser.add_argument("--no-anti-copy", action="store_true", help="Matikan anti-copyright (speed/mirror/color)")
    parser.add_argument("--multi", type=int, default=0, help="Buat N clip dari 1 video lalu jadwalkan beda hari")

    args = parser.parse_args()

    if args.login:
        from core.uploader import Uploader
        Uploader.login(args.login)
        print(f"\n[INFO] Login {args.login} selesai. Cookies tersimpan.")
        return

    if args.set_schedule:
        from core.scheduler import ScheduleStore
        name, times_str = args.set_schedule
        times = [t.strip() for t in times_str.split(",") if t.strip()]
        ScheduleStore.set(name, times)
        print(f"[SCHEDULE] '{name}' -> {times}")
        return

    if args.stats:
        count = _today_count()
        print(f"[STATS] Upload hari ini: {count}/{args.max_daily}")
        print(f"[STATS] Sisa kuota: {max(0, args.max_daily - count)}")
        links = _today_uploaded_links()
        if links:
            print("[STATS] Link yang sudah diproses hari ini:")
            for l in links:
                print(f"  - {l}")
        return

    if args.list:
        from core.scheduler import Queue
        q = Queue.list()
        if not q:
            print("[QUEUE] Kosong")
            return
        print(f"{'ID':<4} {'Status':<10} {'Jam':<6} {'Platform':<12} {'URL':<50}")
        print("-"*80)
        for item in q:
            print(f"{item['id']:<4} {item['status']:<10} {item.get('schedule_at',''):<6} {' '.join(item.get('platforms',[])):<12} {item['url'][:50]}")
        return

    if args.daemon:
        from core.scheduler import SchedulerEngine, Queue
        def on_process(item):
            print(f"[DAEMON] Memproses: {item['url']}")
            process_one(item["url"],
                       item.get("min_dur", args.min_dur),
                       item.get("max_dur", args.max_dur),
                       item.get("platforms", args.platform) or ["youtube"])
        engine = SchedulerEngine(process_callback=on_process)
        engine.start()
        print(f"[DAEMON] Scheduler running. Max {args.max_daily}/hari.")
        print("[DAEMON] Tekan Ctrl+C untuk stop.")
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            engine.stop()
            print("\n[DAEMON] Stopped.")
        return

    if args.watch:
        watch_loop(args.max_daily)
        return

    if args.url:
        if args.multi > 0:
            from core.editor import VideoProcessor
            work_dir = os.path.join(BASE_DIR, "output", f"multi_{int(time.time())}")
            clips = VideoProcessor.auto_process_multi(args.url, work_dir, args.multi,
                args.min_dur, args.max_dur, True, "Kuning", "",
                not args.no_anti_copy)
            if not clips:
                print("[ERROR] Gagal bikin clip")
                return
            print(f"[INFO] Berhasil bikin {len(clips)} clip dari 1 video")
            from core.describer import generate_title, generate_description, generate_tags
            from core.scheduler import Queue
            base_time = args.schedule or "08:00"
            base_h, base_m = int(base_time.split(":")[0]), int(base_time.split(":")[1])
            for i, c in enumerate(clips):
                day_offset = i
                hours = (base_h + day_offset) % 24
                sched = f"{hours:02d}:{base_m:02d}"
                # Generate judul unik per clip
                snippet = c.get("transcript_snippet", "")
                judul = generate_title(snippet or args.url, args.url)
                Queue.add(args.url, platforms=args.platform or ["youtube"],
                         schedule_at=sched,
                         clip_duration=int(c["duration"]),
                         title_template=judul)
                import shutil
                fname = f"{time.strftime('%Y%m%d')}_{i+1}_{int(c['duration'])}s.mp4"
                shutil.copy2(c["path"], os.path.join(OUTPUT_DIR, fname))
                print(f"  [{i+1}/{len(clips)}] {fname} -> jadwal {sched} | speed={c['speed']}x mirror={c['mirror']} color={c['color']}")
            print(f"[INFO] Semua clip dijadwalkan. Jalankan: python farm.py --daemon")
        else:
            process_one(args.url, args.min_dur, args.max_dur,
                        args.platform or None,
                        no_upload=args.no_upload,
                        anti_copy=not args.no_anti_copy)

            if args.queue:
                from core.scheduler import Queue
                Queue.add(args.url, platforms=args.platform or ["youtube"],
                         schedule_at=args.schedule,
                         clip_duration=args.max_dur)
        return

    parser.print_help()

if __name__ == "__main__":
    main()
