import os, re, time, uuid, subprocess, shutil
from pathlib import Path
from typing import Tuple

FFMPEG_PATH = "ffmpeg"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNTS_DIR = os.path.join(BASE_DIR, "accounts")
_COOKIE_FILES_CLEANUP = []  # Track temp cookie files for cleanup

for _p in [os.path.join(BASE_DIR, "ffmpeg.exe"), "ffmpeg", "ffmpeg.exe"]:
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

def _cleanup_cookie_files():
    """Hapus semua temp cookie files yang pernah dibuat."""
    global _COOKIE_FILES_CLEANUP
    for f in _COOKIE_FILES_CLEANUP:
        try:
            if os.path.exists(f): os.unlink(f)
        except: pass
    _COOKIE_FILES_CLEANUP = []

def _load_cookies(platform: str) -> list:
    """Load saved cookies from accounts/ directory."""
    pname = platform.lower()
    cfile = os.path.join(ACCOUNTS_DIR, pname, "cookies.json")
    if os.path.exists(cfile):
        try:
            import json
            with open(cfile) as f:
                return json.load(f)
        except:
            pass
    return []

def _detect_platform(url: str) -> str:
    for d, n in SUPPORTED_PLATFORMS.items():
        if d in url.lower():
            return n.lower()
    return ""

def _get_platform_extractor_args(platform: str) -> dict:
    """Get platform-specific extractor_args."""
    args = {}
    if platform == "youtube":
        args["youtube"] = {
            "skip": ["dash", "hls"],
            "player_client": ["android", "web", "ios", "web_safari"],
        }
    elif platform == "tiktok":
        args["tiktok"] = {
            "app_version": "42.0.0",
            "device_id": "",
        }
    elif platform == "facebook":
        args["facebook"] = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
    return args

def _get_platform_headers(platform: str) -> dict:
    # Chrome 130+ — pakai versi terbaru biar gak dicurigai bot
    ua_chrome = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    ua_android = "Mozilla/5.0 (Linux; Android 15; Pixel 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Mobile Safari/537.36"
    ua_iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Mobile/15E148 Safari/604.1"

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    if platform == "youtube":
        headers["User-Agent"] = ua_chrome
        headers["Accept-Language"] = "en-US,en;q=0.9"
    elif platform == "tiktok":
        headers["User-Agent"] = ua_android  # TikTok mobile web works better
        headers["Accept"] = "*/*"
        headers["Referer"] = "https://www.tiktok.com/"
    elif platform == "facebook":
        headers["User-Agent"] = ua_chrome
        headers["Accept-Language"] = "en-US,en;q=0.9"
        headers["Referer"] = "https://www.facebook.com/"
    else:
        headers["User-Agent"] = ua_chrome

    return headers

def _default_opts(url: str = "", **extra):
    platform = _detect_platform(url) if url else ""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "no_part": True,
        "overwrites": True,
        "extract_flat": False,
        "ffmpeg_location": FFMPEG_PATH,
        "http_headers": _get_platform_headers(platform),
        "extractor_args": _get_platform_extractor_args(platform),
        "retries": 10,
        "fragment_retries": 10,
        "retry_sleep_functions": {"http": lambda n: 5},
        "socket_timeout": 60,
        "extractor_retries": 5,
        "sleep_interval": 3,
        "max_sleep_interval": 10,
    }

    # Attach cookies if available for this platform
    cookies = _load_cookies(platform)
    if cookies:
        import tempfile, json
        try:
            # yt-dlp accepts cookies in Netscape format or as a file path
            # For simplicity, convert cookies to Netscape format
            cookie_lines = ["# Netscape HTTP Cookie File"]
            for c in cookies:
                domain = c.get("domain", "")
                if not domain:
                    continue
                flag = "TRUE" if domain.startswith(".") else "FALSE"
                path = c.get("path", "/")
                secure = "TRUE" if c.get("secure", False) else "FALSE"
                name = c.get("name", "")
                value = c.get("value", "")
                expiry = str(int(c.get("expiration_date", 0) or 0))
                cookie_lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}")
            cookie_text = "\n".join(cookie_lines)
            cookie_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
            cookie_file.write(cookie_text)
            cookie_file.close()
            opts["cookiefile"] = cookie_file.name
            _COOKIE_FILES_CLEANUP.append(cookie_file.name)
        except Exception as e:
            print(f"[cookies] Gagal load cookies untuk {platform}: {e}")

    # curl_cffi sudah otomatis dipakai yt-dlp kalau terinstall (TLS fingerprint browser asli)

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
        os.makedirs(BASE_DIR, exist_ok=True)
        import yt_dlp, re, json
        try:
            with yt_dlp.YoutubeDL(_default_opts(url)) as ydl:
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
            with yt_dlp.YoutubeDL(_default_opts(url)) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            print(f"[download_audio] Gagal extract info: {e}")
            info = {}
        title = info.get("title","Unknown")
        dur = info.get("duration",0) or 0
        limit = min(dur or max_dur, max_dur)
        # Strategi #1: native yt-dlp (pakai headers/cookies bawaan, TLS fingerprint lebih baik)
        opts = _default_opts(url,
            format="bestaudio/best",
            outtmpl=os.path.join(out, "audio_%(id)s.%(ext)s"),
            postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        )
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print(f"[download_audio] Native yt-dlp gagal, coba dengan ffmpeg downloader: {e}")
            # Strategi #2: fallback ke ffmpeg downloader (lebih lambat tapi kadang work)
            try:
                opts2 = _default_opts(url,
                    format="bestaudio/best",
                    outtmpl=os.path.join(out, "audio_%(id)s.%(ext)s"),
                    postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
                    external_downloader="ffmpeg",
                    external_downloader_args={"ffmpeg": ["-ss", "0", "-t", str(limit)]},
                )
                with yt_dlp.YoutubeDL(opts2) as ydl:
                    ydl.download([url])
            except Exception as e2:
                print(f"[download_audio] Download gagal total: {e2}")
                return ("", title, dur)
        files = sorted(Path(out).glob("audio_*.wav")) or sorted(Path(out).glob("audio_*.*"))
        if files:
            raw_wav = str(files[0])
            # If not already wav, convert
            if not raw_wav.endswith(".wav"):
                temp_wav = raw_wav.rsplit(".",1)[0] + ".wav"
                r = subprocess.run([FFMPEG_PATH, "-y", "-i", raw_wav, "-ac", "1", "-ar", "16000", temp_wav], capture_output=True, text=True)
                if Path(temp_wav).exists():
                    raw_wav = temp_wav
                else:
                    print(f"[download_audio] Gagal konversi ke WAV: {r.stderr[:200]}")
                    return ("", title, dur)
            else:
                # Normalize to 16000Hz mono WAV for Whisper
                temp_wav = raw_wav + ".normalized.wav"
                r = subprocess.run([FFMPEG_PATH, "-y", "-i", raw_wav, "-ac", "1", "-ar", "16000", temp_wav], capture_output=True, text=True)
                if Path(temp_wav).exists():
                    os.replace(temp_wav, raw_wav)
                else:
                    print(f"[download_audio] Gagal normalize WAV: {r.stderr[:200]}")
            _cleanup_cookie_files()
            return (raw_wav, title, dur)
        _cleanup_cookie_files()
        return ("", title, dur)

    @staticmethod
    def _trim_to_clip(source_path: str, final_path: str, stt: float, dur: float) -> str:
        """Trim source video ke segmen yang diinginkan pakai ffmpeg."""
        if not source_path or not Path(source_path).exists():
            return ""
        if Path(source_path).stat().st_size == 0:
            return ""
        if source_path == final_path or Path(final_path).exists():
            return final_path
        r = subprocess.run([FFMPEG_PATH, "-y", "-ss", str(stt), "-i", source_path,
            "-t", str(dur), "-c:v", "libx264", "-c:a", "aac", "-preset", "fast", final_path],
            capture_output=True, text=True)
        if Path(final_path).exists() and Path(final_path).stat().st_size > 0:
            return final_path
        print(f"[trim] Gagal trim: {r.stderr[:200]}")
        return source_path  # fallback: return source as-is

    @staticmethod
    def download_video_clip(url: str, out: str, stt: float=0, ett: float=60) -> str:
        os.makedirs(out, exist_ok=True)
        _cleanup_part_files(out)
        import yt_dlp
        cid = str(uuid.uuid4())[:8]
        final = os.path.join(out, f"clip_{cid}.mp4")
        dur = ett - stt

        # Strategi #1: native yt-dlp — download FULL video dulu (headers/cookies jalan)
        full_raw = os.path.join(out, f"full_{cid}.%(ext)s")
        full_opts = _default_opts(url,
            format="bestvideo[height<=1080][fps<=60]+bestaudio/best[height<=1080][fps<=60]",
            outtmpl=full_raw,
            merge_output_format="mp4",
        )
        try:
            with yt_dlp.YoutubeDL(full_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print(f"[download_video_clip] Native yt-dlp gagal, coba ffmpeg downloader: {e}")
            # Strategi #2: fallback — ffmpeg downloader langsung segment
            ff_opts = _default_opts(url,
                format="bestvideo[height<=1080][fps<=60]+bestaudio/best[height<=1080][fps<=60]",
                outtmpl=os.path.join(out, f"raw_{cid}.%(ext)s"),
                merge_output_format="mp4",
                external_downloader="ffmpeg",
                external_downloader_args={"ffmpeg": ["-ss", str(stt), "-t", str(dur)]},
            )
            try:
                with yt_dlp.YoutubeDL(ff_opts) as ydl:
                    ydl.download([url])
            except Exception as e2:
                print(f"[download_video_clip] Download gagal total: {e2}")
                _cleanup_cookie_files()
                return ""
            # Trim hasil ffmpeg download
            rfs = sorted(Path(out).glob(f"raw_{cid}.*"))
            if rfs:
                rf = str(rfs[0])
                if Path(rf).stat().st_size > 0:
                    result = VideoDownloader._trim_to_clip(rf, final, 0, dur)
                    _cleanup_cookie_files()
                    return result
            _cleanup_cookie_files()
            return ""

        # Strategi #1 berhasil — trim hasil full video ke segmen
        rfs = sorted(Path(out).glob(f"full_{cid}.*"))
        if not rfs:
            print(f"[download_video_clip] Tidak ada file full_{cid}.*")
            _cleanup_cookie_files()
            return ""
        rf = str(rfs[0])
        result = VideoDownloader._trim_to_clip(rf, final, stt, dur)
        _cleanup_cookie_files()
        return result

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
