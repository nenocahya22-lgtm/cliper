import os, re, time, uuid, subprocess, shutil
from pathlib import Path
from typing import Tuple

FFMPEG_PATH = "ffmpeg"
script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in [os.path.join(script_dir, "ffmpeg.exe"), "ffmpeg", "ffmpeg.exe"]:
    try:
        subprocess.run([_p, "-version"], capture_output=True, text=True, timeout=5)
        FFMPEG_PATH = _p
        break
    except: continue
if FFMPEG_PATH == "ffmpeg":
    _s = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if _s: FFMPEG_PATH = _s

SUPPORTED_PLATFORMS = {"youtube.com":"YouTube","youtu.be":"YouTube","tiktok.com":"TikTok",
    "instagram.com":"Instagram","twitch.tv":"Twitch","facebook.com":"Facebook",
    "fb.com":"Facebook","fb.watch":"Facebook","x.com":"X","twitter.com":"X"}

def _cleanup_part_files(directory: str):
    for f in Path(directory).glob("*.part"):
        try:
            f.unlink(missing_ok=True)
        except:
            pass

def _default_opts(**extra):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "no_part": True,
        "overwrites": True,
        "extract_flat": False,
        "ffmpeg_location": FFMPEG_PATH,
        "extractor_args": {"youtube": {"skip": ["dash", "hls"], "player_client": ["android"]}},
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        },
        "retries": 10,
        "fragment_retries": 10,
        "retry_sleep_functions": {"http": lambda n: 5},
        "socket_timeout": 60,
        "extractor_retries": 5,
    }
    opts.update(extra)
    return opts

class VideoDownloader:
    @staticmethod
    def detect_platform(url: str) -> str:
        for d, n in SUPPORTED_PLATFORMS.items():
            if d in url.lower(): return n
        return ""

    @staticmethod
    def get_subtitle_text(url: str) -> str:
        os.makedirs(script_dir, exist_ok=True)
        import yt_dlp, re, json
        try:
            with yt_dlp.YoutubeDL(_default_opts()) as ydl:
                info = ydl.extract_info(url, download=False)
        except: return ""
        for lang in ["id", "en", "a.en", "a.id", "a.en-US"]:
            subs = info.get("subtitles", {}).get(lang, []) or info.get("automatic_captions", {}).get(lang, [])
            for s in subs:
                if s.get("ext") == "json3":
                    import urllib.request
                    try:
                        resp = urllib.request.urlopen(s["url"], timeout=10)
                        data = json.loads(resp.read().decode())
                        words = []
                        for ev in data.get("events", []):
                            for seg in ev.get("segs", []):
                                w = seg.get("utf8", "").strip()
                                if w: words.append(w)
                        return " ".join(words)
                    except: pass
                elif s.get("ext") in ("vtt", "srv1", "srv2", "srv3"):
                    import urllib.request
                    try:
                        resp = urllib.request.urlopen(s["url"], timeout=10)
                        text = resp.read().decode("utf-8", errors="replace")
                        lines = re.findall(r'(?m)^([A-Za-z].*)$', text)
                        clean = " ".join(l.strip() for l in lines if l.strip() and "-->" not in l and not l.startswith("WEBVTT"))
                        clean = re.sub(r'<[^>]+>', '', clean).strip()
                        if clean: return clean
                    except: pass
        return ""

    @staticmethod
    def download_audio(url: str, out: str, max_dur: float = 600) -> Tuple[str, str, float]:
        os.makedirs(out, exist_ok=True)
        _cleanup_part_files(out)
        import yt_dlp
        try:
            with yt_dlp.YoutubeDL(_default_opts()) as ydl:
                info = ydl.extract_info(url, download=False)
        except: info = {}
        title = info.get("title","Unknown")
        dur = info.get("duration",0) or 0
        limit = min(dur or max_dur, max_dur)
        opts = _default_opts(
            format="bestaudio/best",
            outtmpl=os.path.join(out, "audio_%(id)s.%(ext)s"),
            postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
            external_downloader="ffmpeg",
            external_downloader_args={"ffmpeg": ["-ss", "0", "-t", str(limit)]},
        )
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except:
            opts.pop("external_downloader", None)
            opts.pop("external_downloader_args", None)
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        files = sorted(Path(out).glob("audio_*.wav"))
        if files:
            # Normalize to 16000Hz mono WAV for Whisper
            raw_wav = str(files[0])
            temp_wav = raw_wav + ".normalized.wav"
            subprocess.run([FFMPEG_PATH, "-y", "-i", raw_wav, "-ac", "1", "-ar", "16000", temp_wav], capture_output=True)
            if Path(temp_wav).exists():
                os.replace(temp_wav, raw_wav)
            return (raw_wav, title, dur)
        return ("", title, dur)

    @staticmethod
    def download_video_clip(url: str, out: str, stt: float=0, ett: float=60) -> str:
        os.makedirs(out, exist_ok=True)
        _cleanup_part_files(out)
        import yt_dlp
        cid = str(uuid.uuid4())[:8]
        final = os.path.join(out, f"clip_{cid}.mp4")
        dur = ett - stt
        opts = _default_opts(
            # Quality-first: do not force worstvideo. Use a safer upper bound
            # closer to what opus-clip style tools often keep (typically 720p+ when available).
            format="bestvideo[height<=1080][fps<=60]+bestaudio/best[height<=1080][fps<=60]",
            outtmpl=os.path.join(out, f"raw_{cid}.%(ext)s"),
            merge_output_format="mp4",

            external_downloader="ffmpeg",
            external_downloader_args={"ffmpeg": ["-ss", str(stt), "-t", str(dur)]},
        )
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except:
            opts.pop("external_downloader", None)
            opts.pop("external_downloader_args", None)
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        rfs = sorted(Path(out).glob(f"raw_{cid}.*"))
        if not rfs: return ""
        rf = str(rfs[0])
        if rf != final:
            subprocess.run([FFMPEG_PATH,"-y","-ss",str(stt),"-i",rf,
                "-t",str(dur),"-c:v","libx264","-c:a","aac","-preset","fast",final],
                capture_output=True, text=True)
        return final if Path(final).exists() else rf

    @staticmethod
    def extract_audio_from_local(video_path: str, out: str) -> Tuple[str, float]:
        os.makedirs(out, exist_ok=True)
        aid = str(uuid.uuid4())[:8]
        audio = os.path.join(out, f"audio_{aid}.wav")
        dur = 0.0
        r = subprocess.run([FFMPEG_PATH,"-i",video_path,"-f","null","-"],
            capture_output=True, text=True, timeout=60)
        for line in (r.stderr or "").split("\n"):
            if "Duration" in line:
                m = re.search(r"Duration: (\d+):(\d+):(\d+)\.(\d+)", line)
                if m:
                    dur = int(m[1])*3600 + int(m[2])*60 + int(m[3]) + int(m[4])/100.0
                break
        subprocess.run([FFMPEG_PATH,"-y","-i",video_path,"-ac","1","-ar","16000",
            "-vn",audio], capture_output=True, text=True, timeout=600)
        return (audio, dur) if Path(audio).exists() else ("", dur)

    @staticmethod
    def trim_local_video(video_path: str, out: str, stt: float, ett: float) -> str:
        subprocess.run([FFMPEG_PATH,"-y","-ss",str(stt),"-i",video_path,
            "-t",str(ett-stt),"-c:v","libx264","-c:a","aac","-preset","fast",out],
            capture_output=True, text=True)
        return out if Path(out).exists() else video_path
