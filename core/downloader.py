import os, re, time, uuid, subprocess, shutil
from pathlib import Path
from typing import Tuple, Optional

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

PROXIES_FILE = os.path.join(BASE_DIR, "proxies.json")

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
                cookies = json.load(f)
            if not isinstance(cookies, list):
                return []
            
            # Filter cookies to prevent HTTP 413: Request Entity Too Large
            essential_keys = {
                # YouTube essential auth & download cookies
                "SID", "HSID", "SSID", "APISID", "SAPISID", "LOGIN_INFO", "PREF", "YSC",
                "__Secure-1PAPISID", "__Secure-1PSID", "__Secure-3PAPISID", "__Secure-3PSID",
                "__Secure-3PSIDTS", "__Secure-3PSIDCC", "__Secure-1PSIDTS", "__Secure-1PSIDCC",
                "VISITOR_INFO1_LIVE", "VISITOR_PRIVACY_METADATA", "GPS",
                # TikTok essential auth cookies
                "sessionid", "sessionid_ss", "sid_tt", "uid_tt", "uid_tt_ss", "tt_webid", "tt_webid_v2", "odin_tt", "msToken",
                # Facebook essential auth cookies
                "c_user", "xs", "fr", "datr", "sb", "spin", "wd"
            }
            
            filtered = []
            for c in cookies:
                name = c.get("name", "")
                # Only keep essential cookies or cookies with small values
                if name in essential_keys:
                    filtered.append(c)
                elif len(c.get("value", "")) < 120:  # Keep other small utility/session cookies
                    filtered.append(c)
            return filtered
        except:
            pass
    return []

def _detect_platform(url: str) -> str:
    for d, n in SUPPORTED_PLATFORMS.items():
        if d in url.lower():
            return n.lower()
    return ""

def _get_platform_extractor_args(platform: str) -> dict:
    """Get platform-specific extractor_args.
    
    Gunakan sesedikit mungkin client untuk menghindari HTTP 413 (Request Entity Too Large)
    di cloud server. Android client paling ringan dan jarang kena block.
    """
    args = {}
    if platform == "youtube":
        args["youtube"] = {
            "player_client": ["android"],  # 1 client saja biar payload kecil
            "skip": ["dash", "hls"],       # skip DASH/HLS manifest — kurangi response size
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
        "socket_timeout": 30,
        "extractor_retries": 3,
        "sleep_interval": 5,
        "max_sleep_interval": 15,
        "sleep_requests": 2,  # jeda antar request API biar gak kena rate limit
    }

    # Auto-fetch cookies from local browser if configured
    try:
        import streamlit as st
        browser = st.session_state.get("local_browser_cookies", "None")
        if browser and browser != "None":
            opts["cookiesfrombrowser"] = (browser,)
    except Exception:
        pass

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
    # Skip format checking — kurangi 1 API call (sering trigger 413 di cloud)
    opts["check_formats"] = "none"  # string "none", bukan None!

    # Proxy TIDAK di-set di sini! Caller harus explicit pass proxy= lewat **extra
    # Ini penting karena _default_opts dipanggil berkali-kali per download attempt
    # (extraction A, extraction B, download native, download ffmpeg, dll)
    # Kalau proxy di-set di sini, tiap panggilan bakal pakai proxy berbeda.

    opts.update(extra)
    return opts

def _load_proxies() -> list:
    """Load proxy list from proxies.json."""
    import json
    if os.path.exists(PROXIES_FILE):
        try:
            with open(PROXIES_FILE) as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "proxies" in data:
                return data["proxies"]
        except:
            pass
    return []

def _save_proxies(proxies: list):
    """Save proxy list to proxies.json."""
    import json
    try:
        with open(PROXIES_FILE, "w") as f:
            json.dump({"proxies": proxies, "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}, f, indent=2)
    except Exception as e:
        print(f"[proxy] Gagal simpan proxy: {e}")


class ProxyRotator:
    """
    Rotating proxy manager untuk yt-dlp.
    Otomatis berganti proxy saat kena block (HTTP 403/413).
    
    Format proxy:
      - http://user:pass@host:port
      - socks5://user:pass@host:port
      - http://host:port
    """
    _proxies: list = []
    _current: int = 0
    _failed_indices: set = set()
    # URL API publik untuk mengambil proxy gratis
    _PROXY_API_URLS = [
        "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=http&proxy_format=protocolipport&format=text&timeout=5000",
        "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=socks5&proxy_format=protocolipport&format=text&timeout=5000",
        "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=socks4&proxy_format=protocolipport&format=text&timeout=5000",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    ]

    @classmethod
    def load(cls):
        """Load proxy list from config file."""
        cls._proxies = _load_proxies()
        cls._current = 0
        cls._failed_indices = set()
        return cls._proxies

    @classmethod
    def save(cls):
        """Save current proxy list to config file."""
        _save_proxies(cls._proxies)

    @classmethod
    def set_proxies(cls, proxies: list):
        """Set proxy list and save."""
        cls._proxies = [p.strip() for p in proxies if p.strip()]
        cls._current = 0
        cls._failed_indices = set()
        cls.save()

    @classmethod
    def get_list(cls) -> list:
        """Get all proxies."""
        return cls._proxies

    @classmethod
    def get_current(cls) -> Optional[str]:
        """Get current active proxy."""
        if not cls._proxies:
            return None
        idx = cls._current % len(cls._proxies)
        return cls._proxies[idx]

    @classmethod
    def get_current_index(cls) -> int:
        return cls._current % max(len(cls._proxies), 1)

    @classmethod
    def rotate(cls) -> Optional[str]:
        """Pindah ke proxy berikutnya (round-robin)."""
        if not cls._proxies:
            return None
        cls._current = (cls._current + 1) % len(cls._proxies)
        return cls.get_current()

    @classmethod
    def mark_failed(cls, proxy: str):
        """Tandai proxy yang gagal (403/413) agar tidak dipakai lagi di sesi ini."""
        if proxy in cls._proxies:
            idx = cls._proxies.index(proxy)
            cls._failed_indices.add(idx)
            print(f"[proxy] Tandai {proxy} sebagai gagal. Tersisa {len(cls._proxies) - len(cls._failed_indices)} proxy.")

    @classmethod
    def get_healthy_proxy(cls) -> Optional[str]:
        """Dapatkan proxy sehat berikutnya (lewati yang gagal)."""
        if not cls._proxies:
            return None
        for _ in range(len(cls._proxies)):
            idx = cls._current % len(cls._proxies)
            cls._current += 1
            if idx not in cls._failed_indices:
                return cls._proxies[idx]
        # Semua proxy gagal — reset failed
        print("[proxy] Semua proxy gagal! Reset daftar failed dan coba lagi.")
        cls._failed_indices = set()
        return cls._proxies[0] if cls._proxies else None

    @classmethod
    def fetch_free_proxies(cls, max_per_source: int = 80) -> list:
        """
        Ambil proxy gratis dari API publik, test langsung ke YouTube.
        Hanya simpan proxy yang benar-benar bisa tembus YouTube.
        """
        import urllib.request
        print("[proxy] Mengambil proxy gratis dari API publik...")
        
        all_raw = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        for url in cls._PROXY_API_URLS:
            try:
                proto = "http"
                if "socks5" in url: proto = "socks5"
                if "socks4" in url: proto = "socks4"
                req = urllib.request.Request(url, headers=headers)
                resp = urllib.request.urlopen(req, timeout=15)
                data = resp.read().decode(errors="replace").strip().split("\n")
                count = 0
                for line in data:
                    line = line.strip()
                    if line and not line.startswith("#") and ":" in line:
                        if not line.startswith("http"):
                            line = f"{proto}://{line}"
                        all_raw.append(line)
                        count += 1
                        if count >= max_per_source:
                            break
                print(f"[proxy]  {len(data[:max_per_source])} dari {url.split('/')[-1][:20]}")
            except Exception as e:
                print(f"[proxy]  Gagal ambil dari {url[:50]}: {str(e)[:40]}")
        
        # Hapus duplikat
        all_raw = list(dict.fromkeys(all_raw))
        print(f"[proxy] Total unik: {len(all_raw)}")
        
        # Test langsung ke YouTube dengan yt-dlp (skip socket — gak cukup)
        import socket as _sock
        living = []
        for i, p in enumerate(all_raw):
            # Socket test dulu (cepat)
            try:
                parts = p.split("://")[1].split(":")
                host = parts[0]
                port = int(parts[1]) if len(parts) > 1 else 80
                s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
                s.settimeout(3)
                s.connect((host, port))
                s.close()
            except:
                continue
            
            # Test dengan yt-dlp ke YouTube (ambil 10 proxy pertama yg tembus)
            if len(living) < 10:
                try:
                    r = subprocess.run([
                        "yt-dlp", "--proxy", p,
                        "--skip-download", "--print", "title",
                        "--socket-timeout", "5",
                        "--no-warnings",
                        "https://www.youtube.com/watch?v=60ssnYN1F_s"
                    ], capture_output=True, text=True, timeout=8)
                    if r.returncode == 0 and r.stdout.strip():
                        living.append(p)
                        print(f"[proxy]  YouTube OK #{len(living)}: {p[:50]}")
                except:
                    pass
            
            if (i+1) % 200 == 0:
                print(f"[proxy]  Progress {i+1}/{len(all_raw)}... {len(living)} proxy tembus YouTube")
        
        print(f"[proxy] Total tembus YouTube: {len(living)}/{len(all_raw)}")
        
        if living:
            cls._proxies = living
            cls._current = 0
            cls._failed_indices = set()
            cls.save()
        
        return living

    @classmethod
    def status(cls) -> dict:
        """Status current proxy rotator."""
        return {
            "total": len(cls._proxies),
            "current": cls.get_current(),
            "current_index": cls.get_current_index(),
            "failed": len(cls._failed_indices),
        }


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
    def _try_extract(ydl_opts: dict, url: str, label: str = "") -> dict:
        """Coba extract info dengan opsi tertentu. Return {} kalau gagal."""
        import yt_dlp
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False) or {}
        except Exception as e:
            err_str = str(e)
            # 413 atau 403 — log dan lanjut fallback
            if "413" in err_str or "403" in err_str:
                print(f"[extract] {label} kena block ({err_str[:80]})")
            else:
                print(f"[extract] {label} gagal: {err_str[:80]}")
            return {}

    @staticmethod
    def _extract_info_safe(url: str, platform: str = "") -> dict:
        """
        Multi-strategy extraction untuk bypass block di cloud server.
        Coba berbagai kombinasi opsi sampai salah satu berhasil.
        """
        # Strategi A: tanpa cookies — penyebab utama 413 adalah cookies terlalu besar
        opts_a = _default_opts(url)
        opts_a.pop("cookiefile", None)
        info = VideoDownloader._try_extract(opts_a, url, "tanpa cookies")
        if info and info.get("title"):
            return info

        # Strategi B: dengan cookies (kalau ada, untuk video age-restricted)
        opts_b = _default_opts(url)
        info = VideoDownloader._try_extract(opts_b, url, "dengan cookies")
        if info and info.get("title"):
            return info

        return {}

    @staticmethod
    def download_audio(url: str, out: str, max_dur: float = 600) -> Tuple[str, str, float]:
        import yt_dlp
        os.makedirs(out, exist_ok=True)
        _cleanup_part_files(out)
        platform = _detect_platform(url)
        info = VideoDownloader._extract_info_safe(url, platform)
        title = info.get("title","Unknown")
        dur = info.get("duration",0) or 0
        limit = min(dur or max_dur, max_dur)

        max_retries = max(len(ProxyRotator.get_list()), 1) * 2  # max retries = jumlah proxy * 2
        for attempt in range(max_retries):
            current_proxy = ProxyRotator.get_current()
            if attempt > 0:
                # Rotate ke proxy berikutnya
                ProxyRotator.rotate()
                new_proxy = ProxyRotator.get_current()
                if new_proxy == current_proxy and len(ProxyRotator.get_list()) > 1:
                    ProxyRotator.rotate()
                print(f"[proxy] Retry #{attempt} — ganti proxy ke: {ProxyRotator.get_current()}")
                time.sleep(2)

            # Dapatkan proxy SEKALI per attempt — pass explicit via extra
            proxy_url = ProxyRotator.get_current()
            proxy_extra = {"proxy": proxy_url} if proxy_url else {}

            # Strategi #1: native yt-dlp
            opts = _default_opts(url,
                format="bestaudio/best",
                outtmpl=os.path.join(out, "audio_%(id)s.%(ext)s"),
                postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
                **proxy_extra,
            )
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                # Berhasil! lanjut ke proses file
                break
            except Exception as e:
                err_str = str(e)
                is_block = "403" in err_str or "413" in err_str or "429" in err_str or "block" in err_str.lower()
                if is_block:
                    proxy = ProxyRotator.get_current()
                    if proxy:
                        ProxyRotator.mark_failed(proxy)
                    print(f"[download_audio] Attempt #{attempt+1} kena block: {err_str[:80]}")
                    if attempt < max_retries - 1:
                        continue  # coba proxy lain
                else:
                    # Bukan block error — coba strategi ffmpeg fallback
                    print(f"[download_audio] Native yt-dlp gagal, coba ffmpeg: {err_str[:80]}")

                # Strategi #2: ffmpeg downloader fallback — pakai proxy yg sama
                try:
                    if is_block:
                        continue  # coba proxy lain dulu
                    opts2 = _default_opts(url,
                        format="bestaudio/best",
                        outtmpl=os.path.join(out, "audio_%(id)s.%(ext)s"),
                        postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
                        external_downloader="ffmpeg",
                        external_downloader_args={"ffmpeg": ["-ss", "0", "-t", str(limit)]},
                        **proxy_extra,
                    )
                    with yt_dlp.YoutubeDL(opts2) as ydl:
                        ydl.download([url])
                    break  # berhasil
                except Exception as e2:
                    print(f"[download_audio] ffmpeg fallback gagal: {str(e2)[:80]}")
                    if "403" in str(e2) or "413" in str(e2):
                        # ffmpeg juga kena block — coba proxy lain
                        proxy = ProxyRotator.get_current()
                        if proxy:
                            ProxyRotator.mark_failed(proxy)
                        if attempt < max_retries - 1:
                            continue
                    return ("", title, dur)
        else:
            # Loop selesai tanpa break — semua retry gagal
            print(f"[download_audio] Semua {max_retries} percobaan gagal")
            _cleanup_cookie_files()
            return ("", title, dur)

        # Proses file hasil download
        files = sorted(Path(out).glob("audio_*.wav")) or sorted(Path(out).glob("audio_*.*"))
        if files:
            raw_wav = str(files[0])
            if not raw_wav.endswith(".wav"):
                temp_wav = raw_wav.rsplit(".",1)[0] + ".wav"
                r = subprocess.run([FFMPEG_PATH, "-y", "-i", raw_wav, "-ac", "1", "-ar", "16000", temp_wav], capture_output=True, text=True)
                if Path(temp_wav).exists():
                    raw_wav = temp_wav
                else:
                    print(f"[download_audio] Gagal konversi ke WAV: {r.stderr[:200]}")
                    _cleanup_cookie_files()
                    return ("", title, dur)
            else:
                temp_wav = raw_wav + ".normalized.wav"
                r = subprocess.run([FFMPEG_PATH, "-y", "-i", raw_wav, "-ac", "1", "-ar", "16000", temp_wav], capture_output=True, text=True)
                if Path(temp_wav).exists():
                    os.replace(temp_wav, raw_wav)
                else:
                    print(f"[download_audio] Gagal normalize WAV: {r.stderr[:200]}")
            # Trim WAV ke max_dur jika durasi asli melebihi batas
            if limit < dur and limit > 0:
                trimmed_wav = raw_wav + ".trimmed.wav"
                r = subprocess.run([FFMPEG_PATH, "-y", "-ss", "0", "-t", str(limit), "-i", raw_wav, "-ac", "1", "-ar", "16000", trimmed_wav],
                    capture_output=True, text=True, timeout=120)
                if Path(trimmed_wav).exists():
                    os.replace(trimmed_wav, raw_wav)
                    dur = limit
                    print(f"[download_audio] Audio di-trim ke {limit:.0f}s (dari {dur:.0f}s)")
                else:
                    print(f"[download_audio] Gagal trim audio: {r.stderr[:100]}")
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

        max_retries = max(len(ProxyRotator.get_list()), 1) * 2
        for attempt in range(max_retries):
            current_proxy = ProxyRotator.get_current()
            if attempt > 0:
                ProxyRotator.rotate()
                new_proxy = ProxyRotator.get_current()
                if new_proxy == current_proxy and len(ProxyRotator.get_list()) > 1:
                    ProxyRotator.rotate()
                print(f"[proxy] Retry video #{attempt} — ganti proxy ke: {ProxyRotator.get_current()}")
                time.sleep(2)

            # Dapatkan proxy SEKALI per attempt
            proxy_url = ProxyRotator.get_current()
            proxy_extra = {"proxy": proxy_url} if proxy_url else {}

            # Strategi #1: native yt-dlp — download FULL video dulu
            full_raw = os.path.join(out, f"full_{cid}.%(ext)s")
            full_opts = _default_opts(url,
                format="bestvideo[height<=1080][fps<=60]+bestaudio/best[height<=1080][fps<=60]",
                outtmpl=full_raw,
                merge_output_format="mp4",
                **proxy_extra,
            )
            try:
                with yt_dlp.YoutubeDL(full_opts) as ydl:
                    ydl.download([url])
                # Berhasil! trim hasil full video ke segmen
                rfs = sorted(Path(out).glob(f"full_{cid}.*"))
                if not rfs:
                    print(f"[download_video_clip] Tidak ada file full_{cid}.*")
                    _cleanup_cookie_files()
                    return ""
                rf = str(rfs[0])
                result = VideoDownloader._trim_to_clip(rf, final, stt, dur)
                _cleanup_cookie_files()
                return result
            except Exception as e:
                err_str = str(e)
                is_block = "403" in err_str or "413" in err_str or "429" in err_str or "block" in err_str.lower()
                if is_block:
                    proxy = ProxyRotator.get_current()
                    if proxy:
                        ProxyRotator.mark_failed(proxy)
                    print(f"[download_video_clip] Attempt #{attempt+1} kena block: {err_str[:80]}")
                    if attempt < max_retries - 1:
                        continue  # coba proxy lain
                else:
                    print(f"[download_video_clip] Native gagal, coba ffmpeg: {err_str[:80]}")

                # Strategi #2: ffmpeg fallback — pakai proxy yg sama
                try:
                    if is_block and attempt < max_retries - 1:
                        continue  # kalo block, coba proxy lain dulu
                    ff_opts = _default_opts(url,
                        format="bestvideo[height<=1080][fps<=60]+bestaudio/best[height<=1080][fps<=60]",
                        outtmpl=os.path.join(out, f"raw_{cid}.%(ext)s"),
                        merge_output_format="mp4",
                        external_downloader="ffmpeg",
                        external_downloader_args={"ffmpeg": ["-ss", str(stt), "-t", str(dur)]},
                        **proxy_extra,
                    )
                    with yt_dlp.YoutubeDL(ff_opts) as ydl:
                        ydl.download([url])
                    # Trim hasil ffmpeg download
                    rfs = sorted(Path(out).glob(f"raw_{cid}.*"))
                    if rfs:
                        rf = str(rfs[0])
                        if Path(rf).stat().st_size > 0:
                            result = VideoDownloader._trim_to_clip(rf, final, 0, dur)
                            _cleanup_cookie_files()
                            return result
                except Exception as e2:
                    print(f"[download_video_clip] ffmpeg gagal: {str(e2)[:80]}")
                    if "403" in str(e2) or "413" in str(e2):
                        proxy = ProxyRotator.get_current()
                        if proxy:
                            ProxyRotator.mark_failed(proxy)
                        if attempt < max_retries - 1:
                            continue
                    _cleanup_cookie_files()
                    return ""

        # Semua retry gagal
        print(f"[download_video_clip] Semua {max_retries} percobaan gagal")
        _cleanup_cookie_files()
        return ""

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
