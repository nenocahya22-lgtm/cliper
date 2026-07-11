"""
Cliper — Simple YouTube Clip Maker
Like WayinVideo: paste URL → get video clip
"""
import os, time, uuid, subprocess, shutil
from pathlib import Path
import streamlit as st

APP_NAME = "Cliper"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Lazy imports ────────────────────────────────────────
def _get_downloader():
    from core.downloader import VideoDownloader
    return VideoDownloader

def _get_transcriber():
    from core.transcriber import AudioTranscriber, WordTimestamp
    return AudioTranscriber, WordTimestamp

def _get_finder():
    from core.finder import ViralMomentFinder, ProcessingResult
    return ViralMomentFinder, ProcessingResult

def _get_editor():
    from core.editor import SubtitleGenerator, VideoProcessor, SUBTITLE_COLORS, ASPECT_PRESETS
    return SubtitleGenerator, VideoProcessor, SUBTITLE_COLORS, ASPECT_PRESETS

def _get_ffmpeg():
    from core.downloader import FFMPEG_PATH
    return FFMPEG_PATH

# ── Session state ───────────────────────────────────────
def _init():
    defaults = {
        "step": "input", "result": None, "sel_moment": None,
        "out_video": None, "vurl": "", "processing": False,
        "rendering": False, "render_progress": 0.0, "render_done": False, "wd": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v
    if st.session_state.wd is None or not os.path.exists(st.session_state.wd):
        wd = os.path.join(OUTPUT_DIR, f"work_{uuid.uuid4().hex[:8]}")
        os.makedirs(wd, exist_ok=True)
        st.session_state.wd = wd

def _fmt_time(s):
    h = int(s // 3600); m = int((s % 3600) // 60); sec = int(s % 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"

def _reset_all():
    for k in list(st.session_state.keys()):
        if k not in ("wd",): del st.session_state[k]
    _init()

# ── CSS ─────────────────────────────────────────────────
CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap');
:root { --canvas: #08090d; --surface: #10111a; --ink: #f8fafc; --ink-soft: #94a3b8; --violet: #8b5cf6; --pink: #db2777; }
* { box-sizing: border-box; }
html, body, [data-testid="stApp"], .stApp { background: var(--canvas) !important; font-family: 'Plus Jakarta Sans', sans-serif !important; color: var(--ink) !important; }
[data-testid="stToolbar"] { display: none; } [data-testid="stDecoration"] { display: none; }
#MainMenu { visibility: hidden; } header { display: none !important; }
.appview-container .main .block-container { padding: 0 !important; max-width: none !important; }
.main-wrap { max-width: 720px; margin: 0 auto; padding: 40px 24px; text-align: center; }
.hero-icon { font-size: 56px; margin-bottom: 8px; filter: drop-shadow(0 0 20px rgba(139,92,246,0.3)); }
.hero-title { font-family: 'Space Grotesk', sans-serif; font-size: 42px; font-weight: 800; letter-spacing: -1px; margin: 0 0 4px; background: linear-gradient(135deg, #fff 30%, #a78bfa 70%, #f472b6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; line-height: 1.1; }
.hero-sub { font-size: 16px; color: var(--ink-soft); margin: 0 0 36px; line-height: 1.5; }
.url-box { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.08); border-radius: 20px; padding: 24px; margin-bottom: 24px; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.url-box:hover { border-color: rgba(139,92,246,0.3); }
.stTextInput > div > div > input { border-radius: 14px !important; border: 1px solid rgba(255,255,255,0.1) !important; font-family: 'Plus Jakarta Sans', sans-serif !important; font-size: 18px !important; color: #fff !important; background: rgba(0,0,0,0.3) !important; padding: 16px 20px !important; text-align: center !important; height: 60px !important; transition: all 0.3s ease !important; }
.stTextInput > div > div > input:focus { border-color: var(--violet) !important; box-shadow: 0 0 0 3px rgba(139,92,246,0.15) !important; }
.stButton > button { font-family: 'Plus Jakarta Sans', sans-serif !important; font-weight: 700 !important; font-size: 16px !important; padding: 14px 28px !important; border-radius: 14px !important; border: none !important; height: 56px !important; transition: all 0.3s cubic-bezier(0.4,0,0.2,1) !important; }
.stButton > button[kind="primary"] { background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%) !important; color: #fff !important; box-shadow: 0 4px 20px rgba(124,58,237,0.35) !important; }
.stButton > button[kind="primary"]:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(124,58,237,0.5) !important; }
.stButton > button[kind="secondary"] { background: rgba(255,255,255,0.04) !important; color: var(--ink) !important; border: 1px solid rgba(255,255,255,0.1) !important; }
.moment-card, .result-card { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 16px; padding: 16px; margin-bottom: 12px; text-align: left; transition: all 0.2s ease; }
.moment-card:hover { border-color: rgba(139,92,246,0.3); background: rgba(255,255,255,0.04); transform: translateY(-2px); }
.moment-card.selected { border-color: var(--violet); background: rgba(139,92,246,0.08); box-shadow: 0 0 20px rgba(139,92,246,0.15); }
.moment-cat { font-size: 13px; font-weight: 700; color: #fff; }
.moment-time { font-size: 11px; color: var(--ink-soft); margin-top: 2px; }
.moment-reason { font-size: 11px; color: var(--ink-soft); margin-top: 4px; font-style: italic; }
.stProgress > div > div > div > div { background: linear-gradient(90deg, #8b5cf6, #ec4899) !important; border-radius: 8px !important; }
.stProgress > div > div > div { background: rgba(255,255,255,0.06) !important; border-radius: 8px !important; height: 6px !important; }
.badge { display: inline-block; padding: 3px 10px; border-radius: 8px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
.badge-green { background: rgba(16,185,129,0.15); color: #34d399; }
.badge-red { background: rgba(239,68,68,0.15); color: #f87171; }
.badge-violet { background: rgba(139,92,246,0.15); color: #a78bfa; }
.badge-amber { background: rgba(245,158,11,0.15); color: #f59e0b; }
video { border-radius: 16px !important; border: 1px solid rgba(255,255,255,0.08) !important; box-shadow: 0 8px 32px rgba(0,0,0,0.3) !important; }
.stSelectbox > div > div > select { border-radius: 12px !important; border: 1px solid rgba(255,255,255,0.08) !important; font-family: 'Plus Jakarta Sans', sans-serif !important; font-size: 13px !important; color: #fff !important; background: #111219 !important; padding: 8px 12px !important; }
.stSelectbox label { font-family: 'Plus Jakarta Sans', sans-serif; font-size: 12px; font-weight: 600; color: var(--ink-soft); }
.stCheckbox label { font-family: 'Plus Jakarta Sans', sans-serif; font-size: 13px; color: var(--ink); }
.stCheckbox [data-baseweb="checkbox"] { border-color: rgba(255,255,255,0.2) !important; }
.stCheckbox [data-baseweb="checkbox"][aria-checked="true"] { background: var(--violet) !important; border-color: var(--violet) !important; }
.stNumberInput > div > div > input { border-radius: 12px !important; border: 1px solid rgba(255,255,255,0.08) !important; font-family: 'Plus Jakarta Sans', sans-serif !important; font-size: 13px !important; color: #fff !important; background: #111219 !important; }
.footer { margin-top: 48px; padding-top: 24px; border-top: 1px solid rgba(255,255,255,0.04); font-size: 12px; color: var(--ink-soft); }
.footer a { color: var(--violet) !important; text-decoration: none; }
.footer a:hover { color: #a78bfa !important; }
</style>"""

# ── YouTube helpers ─────────────────────────────────────
def _extract_yt_id(url: str) -> str:
    import re
    patterns = [
        r'(?:youtube\.com|youtu\.be)/(?:watch\?v=|embed/|v/|shorts/|)([\w-]{11})',
        r'youtu\.be/([\w-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m: return m.group(1)
    return ""

def _yt_thumbnail(video_id: str) -> str:
    return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

@st.cache_data(ttl=3600)
def _fetch_yt_title(video_id: str) -> tuple:
    """Fetch video title and duration via oEmbed. Returns (title, channel_name) or empty strings."""
    try:
        import urllib.request, json
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read().decode())
        return data.get("title", ""), data.get("author_name", "")
    except:
        return "", ""

# ── Step 1: Input ───────────────────────────────────────
def _step_input():
    st.markdown(f"""
    <div class="main-wrap">
      <div class="hero-icon">⚡</div>
      <h1 class="hero-title">{APP_NAME}</h1>
      <p class="hero-sub">Tempel link YouTube, dapatkan klip dengan subtitle instan.<br>Gratis, tanpa login.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="url-box">', unsafe_allow_html=True)
    url = st.text_input("Link YouTube", placeholder="https://youtube.com/watch?v=...", key="vurl_input", label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)
    if url:
        st.session_state.vurl = url
        # Show YouTube thumbnail preview kaya WayinVideo
        vid = _extract_yt_id(url)
        if vid:
            thumb_url = _yt_thumbnail(vid)
            title, channel = _fetch_yt_title(vid)
            st.markdown(f"""
            <div style="display:flex;gap:16px;align-items:center;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:12px;margin-bottom:16px;text-align:left">
              <img src="{thumb_url}" style="width:180px;height:101px;border-radius:10px;object-fit:cover;flex-shrink:0;border:1px solid rgba(255,255,255,0.08)"
                   onerror="this.style.display='none'"
                   alt="YouTube thumbnail">
              <div style="flex:1;min-width:0">
                <p style="font-size:15px;font-weight:700;color:#fff;margin:0 0 4px;line-height:1.2">{title if title else 'Video YouTube'}</p>
                <p style="font-size:12px;color:var(--ink-soft);margin:0">{'🎬 ' + channel if channel else '📺 YouTube'}</p>
              </div>
            </div>
            """, unsafe_allow_html=True)
        if st.button("🚀 Proses Video", type="primary", use_container_width=True):
            st.session_state.step = "processing"
            st.rerun()

# ── Step 2: Processing (background thread) ────────────
def _step_processing():
    st.markdown('<div class="main-wrap">', unsafe_allow_html=True)
    st.markdown('<h2 style="font-size:24px;font-weight:700;margin:0 0 8px">Memproses Video...</h2>', unsafe_allow_html=True)
    st.markdown('<p style="color:var(--ink-soft);font-size:14px;margin:0 0 24px">Mengunduh, mentranskripsi, dan menganalisis momen viral</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Start background thread on first call
    if not st.session_state.get("processing", False):
        st.session_state.processing = True
        st.session_state.processing_done = False
        st.session_state.processing_error = ""
        st.session_state.processing_progress = 0.0
        st.session_state.processing_msg = "Memulai..."
        import threading
        threading.Thread(target=_do_process, daemon=True).start()
        st.rerun()
        return

    # Poll for progress
    prog = st.progress(st.session_state.get("processing_progress", 0.0))
    msg = st.session_state.get("processing_msg", "")
    st.markdown(f'<p style="text-align:center;font-size:14px;font-weight:600;color:#fff">{msg}</p>', unsafe_allow_html=True)

    if st.session_state.get("processing_done", False):
        if st.session_state.get("processing_error"):
            st.error(st.session_state.processing_error)
            if st.button("🔄 Coba Lagi", use_container_width=True):
                st.session_state.processing = False; st.session_state.step = "input"; st.rerun()
        else:
            prog.progress(1.0)
            st.markdown(f'<p style="text-align:center;font-size:14px;font-weight:600;color:#34d399">✅ Selesai! Pilih momen di bawah.</p>', unsafe_allow_html=True)
            time.sleep(0.5)
            st.session_state.step = "moments"
            st.rerun()
    else:
        # Still processing — rerun to poll again
        time.sleep(1)
        st.rerun()

# ── Background processing thread ────────────────────────
def _do_process():
    """Run all processing in background thread to avoid Streamlit Cloud timeout."""
    url = st.session_state.get("vurl", "")
    wd = st.session_state.wd
    if not url:
        st.session_state.processing_error = "URL tidak valid"
        st.session_state.processing_done = True
        return
    try:
        import yt_dlp
        VideoDownloader = _get_downloader()

        st.session_state.processing_msg = "Mendapatkan info video..."
        st.session_state.processing_progress = 0.05
        info = {}
        try:
            from core.downloader import _default_opts
            with yt_dlp.YoutubeDL(_default_opts(url)) as ydl:
                info = ydl.extract_info(url, download=False) or {}
        except: pass
        title = info.get("title", "Unknown"); dur = info.get("duration", 0) or 0

        ViralMomentFinder, ProcessingResult = _get_finder()
        res = ProcessingResult()
        res.title = title; res.duration = dur

        st.session_state.processing_msg = "Mengunduh audio..."
        st.session_state.processing_progress = 0.2
        audio, _, _ = VideoDownloader.download_audio(url, wd, max_dur=600)

        st.session_state.processing_msg = "Mentranskripsi dengan Whisper AI..."
        st.session_state.processing_progress = 0.4
        AudioTranscriber, WordTimestamp = _get_transcriber()
        text, wts = AudioTranscriber.transcribe(audio)
        if text: res.transcript = text; res.word_timestamps = wts

        st.session_state.processing_msg = "Menganalisis momen viral..."
        st.session_state.processing_progress = 0.65
        res.viral_moments = ViralMomentFinder.find_moments(res.transcript or "", dur, res.word_timestamps, use_llm=False)

        st.session_state.processing_msg = "Mengunduh klip video..."
        st.session_state.processing_progress = 0.85
        vp = VideoDownloader.download_video_clip(url, wd, 0, min(dur+5, 600))
        if vp: res.video_path = vp

        st.session_state.result = res
        st.session_state.processing_progress = 1.0
        st.session_state.processing_msg = "Selesai!"
        st.session_state.processing_done = True

    except Exception as e:
        st.session_state.processing_error = f"Gagal memproses video: {str(e)[:200]}"
        st.session_state.processing_done = True
        print(f"[process error] {e}")

def _gen_preview(video_path, start, end, output_path):
    """Generate a short preview clip for a moment."""
    try:
        ffmpeg = _get_ffmpeg()
        subprocess.run([ffmpeg, "-y", "-ss", str(start), "-i", video_path,
            "-t", str(min(end - start, 15)),
            "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
            "-c:a", "aac", "-b:a", "64k", output_path
        ], capture_output=True, text=True, timeout=30)
        return Path(output_path).exists()
    except: return False

# ── Step 3: Pick Moment + Editor ────────────────────────
def _step_moments():
    res = st.session_state.get("result")
    if not res or not res.viral_moments:
        st.error("Tidak ada momen yang ditemukan.")
        if st.button("🔄 Kembali", use_container_width=True):
            st.session_state.step = "input"; st.rerun()
        return

    # Header
    st.markdown('<div class="main-wrap">', unsafe_allow_html=True)
    st.markdown(f'<h2 style="font-size:24px;font-weight:700;margin:0 0 4px">Pilih Momen + Edit</h2>', unsafe_allow_html=True)
    st.markdown(f'<p style="color:var(--ink-soft);font-size:14px;margin:0 0 16px">{res.title[:60]} · {res.duration:.0f}s</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Full video preview ───────────────────────────────
    has_video = res.video_path and Path(res.video_path).exists()
    if has_video:
        st.markdown('<div style="max-width:480px;margin:0 auto 24px">', unsafe_allow_html=True)
        st.video(res.video_path, start_time=0)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Video tidak tersedia untuk preview")

    # ── Moment timeline ──────────────────────────────────
    cat_icons = {"HOOK": "🎣", "KLIMAKS": "🔥", "CTA": "📢", "AUTO": "⭐"}
    cat_colors = {"HOOK": "badge-violet", "KLIMAKS": "badge-red", "CTA": "badge-amber", "AUTO": "badge-green"}
    for i, m in enumerate(res.viral_moments):
        d = m.end_time - m.start_time
        icon = cat_icons.get(m.category, "⭐")
        badge_cls = cat_colors.get(m.category, "badge-green")
        selected = st.session_state.get("sel_idx") == i
        sel_cls = "selected" if selected else ""
        st.markdown(f"""
        <div class="moment-card {sel_cls}">
          <div style="display:flex;align-items:center;gap:12px">
            <div style="font-size:22px;flex-shrink:0">{icon}</div>
            <div style="flex:1">
              <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                <span class="moment-cat">{m.category}</span>
                <span class="badge {badge_cls}">{d:.0f}s</span>
              </div>
              <div class="moment-time">⏱ {_fmt_time(m.start_time)} → {_fmt_time(m.end_time)}</div>
              <div class="moment-reason">{m.reason}</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns([3, 1])
        with c2:
            btn_type = "primary" if selected else "secondary"
            if st.button(f"Pilih #{i+1}", key=f"sel_{i}", type=btn_type, use_container_width=True):
                st.session_state.sel_idx = i; st.session_state.sel_moment = m
                # Reset render state
                st.session_state.rendering = False
                st.session_state.render_done = False
                st.session_state.out_video = None
                st.rerun()
        if selected and m.transcript_snippet:
            with c1:
                st.markdown(f'<p style="font-size:11px;color:var(--ink-soft);margin:0;padding:4px 0">📝 {m.transcript_snippet[:200]}</p>', unsafe_allow_html=True)

    # ── Selected moment: preview clip + editor ───────────
    mom = st.session_state.get("sel_moment")
    if not mom:
        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown('<p style="text-align:center;color:var(--ink-soft);font-size:14px">👆 Pilih momen di atas untuk mulai edit</p>', unsafe_allow_html=True)
        return

    st.markdown('<hr>', unsafe_allow_html=True)

    # --- Trimmed preview ---
    preview_path = None
    if has_video:
        preview_path = os.path.join(st.session_state.wd, f"preview_{int(mom.start_time)}_{int(mom.end_time)}.mp4")
        if not Path(preview_path).exists():
            _gen_preview(res.video_path, mom.start_time, mom.end_time, preview_path)
        col_v1, col_v2 = st.columns([2, 1])
        with col_v1:
            if Path(preview_path).exists():
                st.markdown('<p style="font-size:12px;font-weight:600;color:var(--ink-soft);margin:0 0 4px">🎬 Preview Klip</p>', unsafe_allow_html=True)
                st.video(preview_path)
        with col_v2:
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px;">
              <p style="font-size:11px;font-weight:700;color:var(--ink-soft);text-transform:uppercase;letter-spacing:0.3px;margin:0 0 8px">Info Klip</p>
              <p style="font-size:13px;color:#fff;margin:2px 0"><strong>Mulai:</strong> {_fmt_time(mom.start_time)}</p>
              <p style="font-size:13px;color:#fff;margin:2px 0"><strong>Selesai:</strong> {_fmt_time(mom.end_time)}</p>
              <p style="font-size:13px;color:#fff;margin:2px 0"><strong>Durasi:</strong> {mom.end_time - mom.start_time:.0f}s</p>
              <p style="font-size:13px;color:#fff;margin:2px 0"><strong>Kategori:</strong> {mom.category}</p>
            </div>
            """, unsafe_allow_html=True)

    # --- Editor controls ---
    st.markdown('<p style="font-size:14px;font-weight:700;color:#fff;margin:20px 0 12px">✂️ Editor</p>', unsafe_allow_html=True)
    SubtitleGenerator, VideoProcessor, SUBTITLE_COLORS, ASPECT_PRESETS = _get_editor()
    col_o1, col_o2, col_o3 = st.columns(3)
    with col_o1: sub_color = st.selectbox("🎨 Warna Subtitle", list(SUBTITLE_COLORS.keys()), index=0, key="sub_color")
    with col_o2: aspect = st.selectbox("📐 Aspect Ratio", list(ASPECT_PRESETS.keys()), index=0, key="aspect")
    with col_o3: mirror = st.checkbox("🪞 Mirror", value=True, key="mirror")
    col_o4, col_o5, col_o6 = st.columns(3)
    with col_o4: show_sub = st.checkbox("💬 Subtitle", value=True, key="show_sub")
    with col_o5: speed_str = st.selectbox("⚡ Speed", ["1.0x", "1.05x", "1.1x", "1.15x"], index=0, key="speed")
    with col_o6: fade = st.checkbox("✨ Fade", value=True, key="fade")

    # --- Trim controls ---
    st.markdown('<p style="font-size:12px;font-weight:600;color:var(--ink-soft);margin:12px 0 4px">✂️ Trim Waktu (geser sesuai keinginan)</p>', unsafe_allow_html=True)
    clip_dur = float(mom.end_time - mom.start_time)
    c_t1, c_t2 = st.columns(2)
    default_start = max(0.0, float(mom.start_time))
    default_end = min(default_start + clip_dur, float(res.duration))
    with c_t1: start_val = c_t1.number_input("Mulai (detik)", 0.0, max(5.0, float(res.duration)), default_start, 0.5, key="trim_start")
    with c_t2: end_val = c_t2.number_input("Selesai (detik)", float(start_val)+5, max(float(start_val)+5, float(res.duration)), max(float(start_val)+5, min(default_end, float(res.duration))), 0.5, key="trim_end")

    # --- Render + Action buttons ---
    st.markdown('<hr>', unsafe_allow_html=True)
    col_r1, col_r2, col_r3 = st.columns([2, 2, 1])
    with col_r1:
        render_btn = st.button("🎬 Render Klip", type="primary", use_container_width=True, disabled=st.session_state.get("rendering", False))
    with col_r2:
        if preview_path and Path(preview_path).exists():
            if st.button("🔄 Refresh Preview", use_container_width=True):
                if Path(preview_path).exists(): os.remove(preview_path)
                st.rerun()
    with col_r3:
        if st.button("⬅️ Back", use_container_width=True): _reset_all(); st.rerun()

    if render_btn:
        st.session_state.rendering = True; st.session_state.render_progress = 0.0; st.session_state.render_done = False
        import threading
        threading.Thread(target=_do_render, args=(start_val, end_val, show_sub, sub_color, aspect, mirror, speed_str, fade), daemon=True).start()
        st.rerun()

    if st.session_state.get("rendering", False):
        st.progress(st.session_state.render_progress)
        st.markdown(f'<p style="text-align:center;font-size:13px;color:var(--ink-soft)">⏳ Merender video... {st.session_state.render_progress*100:.0f}%</p>', unsafe_allow_html=True)
        time.sleep(0.5); st.rerun()

    if st.session_state.get("render_done", False) and st.session_state.get("out_video"):
        ov = st.session_state.out_video
        if Path(ov).exists():
            sz = Path(ov).stat().st_size / (1024*1024)
            st.markdown(f"""<div style="text-align:center;background:rgba(16,185,129,0.05);border:1px solid rgba(16,185,129,0.15);border-radius:16px;padding:24px;margin:16px 0"><div style="font-size:40px;margin-bottom:8px">✅</div><h3 style="font-size:20px;font-weight:700;color:#fff;margin:0 0 4px">Render Selesai!</h3><p style="font-size:13px;color:var(--ink-soft);margin:0">{os.path.basename(ov)} · {sz:.1f} MB</p></div>""", unsafe_allow_html=True)
            st.video(str(ov))
            with open(ov, "rb") as f:
                st.download_button("📥 Download Video", f, file_name=os.path.basename(ov), mime="video/mp4", use_container_width=True, type="primary")
            st.markdown('<hr>', unsafe_allow_html=True)

            # Upload buttons
            st.markdown(f'<p style="font-size:13px;font-weight:700;color:#fff;margin:0 0 8px">📤 Upload ke Platform</p>', unsafe_allow_html=True)
            col_u1, col_u2, col_u3 = st.columns(3)
            up_yt = col_u1.button("▶️ YouTube", use_container_width=True, disabled=st.session_state.get("_uploading", False))
            up_tt = col_u2.button("🎵 TikTok", use_container_width=True, disabled=st.session_state.get("_uploading", False))
            up_fb = col_u3.button("📘 Facebook", use_container_width=True, disabled=st.session_state.get("_uploading", False))

            if up_yt or up_tt or up_fb:
                plat = "youtube" if up_yt else "tiktok" if up_tt else "facebook"
                st.session_state._uploading = True
                try:
                    from core.uploader import Uploader
                    Uploader.upload(plat, ov, res.title[:100], "")
                    st.success(f"✅ Terupload ke {plat.title()}!")
                except Exception as e:
                    err = str(e)
                    if "cookies" in err.lower() or "login" in err.lower():
                        st.warning("🔑 Belum ada cookies. Buka menu **Settings > Cookies** untuk setup.")
                    else:
                        st.error(f"Gagal upload: {err[:100]}")
                st.session_state._uploading = False
                st.rerun()

            with st.expander("🔑 Settings Cookies (untuk Upload)"):
                plat_sel = st.selectbox("Platform", ["youtube", "tiktok", "facebook"], key="cookie_plat")
                cookies_txt = st.text_area("Tempel Cookies JSON", placeholder='[{ "name": "...", "value": "...", "domain": ".youtube.com", "path": "/" }]', height=100)
                if st.button("💾 Simpan Cookies", use_container_width=True):
                    if cookies_txt.strip():
                        try:
                            import json
                            cdata = json.loads(cookies_txt.strip())
                            if isinstance(cdata, list):
                                from core.uploader import Uploader
                                Uploader.save_cookies(plat_sel, cdata)
                                st.success(f"✅ Cookies {plat_sel.title()} tersimpan!")
                            else: st.error("Format harus array/list")
                        except Exception as ex:
                            st.error(f"Error: {ex}")

            st.markdown('<hr>', unsafe_allow_html=True)
            c_new, _ = st.columns(2)
            if c_new.button("➕ Buat Klip Baru", use_container_width=True, type="primary"): _reset_all(); st.rerun()

def _do_render(start_val, end_val, show_sub, sub_color, aspect, mirror, speed_str, fade):
    res = st.session_state.get("result")
    if not res: st.session_state.rendering = False; return
    wd = st.session_state.wd; cid = uuid.uuid4().hex[:8]
    out = os.path.join(wd, f"out_{cid}.mp4"); sub_path = os.path.join(wd, f"subs_{cid}.ass")
    speed = {"1.0x": 1.0, "1.05x": 1.05, "1.1x": 1.1, "1.15x": 1.15}.get(speed_str, 1.0)
    fi, fo = (0.5, 0.8) if fade else (0, 0)
    try:
        st.session_state.render_progress = 0.1
        VideoDownloader = _get_downloader(); clip_path = res.video_path
        if st.session_state.get("vurl"):
            downloaded = VideoDownloader.download_video_clip(st.session_state.vurl, wd, start_val, end_val)
            if downloaded and Path(downloaded).exists(): clip_path = downloaded
        if not clip_path or not Path(clip_path).exists(): raise Exception("Video source tidak ditemukan")
        st.session_state.render_progress = 0.3
        _, WordTimestamp = _get_transcriber()
        _, VideoProcessor, SUBTITLE_COLORS, _ = _get_editor()
        if show_sub and res.word_timestamps:
            rel = [wt for wt in res.word_timestamps if wt.start < end_val and wt.end > start_val]
            if rel:
                shifted = [WordTimestamp(w.word, max(0, w.start-start_val), w.end-start_val) for w in rel]
                SubtitleGenerator, _, _, _ = _get_editor()
                SubtitleGenerator.generate_ass(shifted, sub_path, SUBTITLE_COLORS.get(sub_color, "&H00FFFF&"))
        st.session_state.render_progress = 0.5
        ok, err = VideoProcessor.process_clip(clip_path, out, sub_path if Path(sub_path).exists() else "", "",
            0, end_val - start_val, fi, fo, speed, mirror, "none", True, aspect=aspect)
        if not ok: raise Exception(err)
        st.session_state.render_progress = 0.8
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in res.title)[:30]
        ts = time.strftime("%Y%m%d_%H%M%S")
        final_name = f"{ts}_{safe_title}.mp4"; final_path = os.path.join(OUTPUT_DIR, final_name)
        shutil.copy2(out, final_path)
        st.session_state.out_video = final_path; st.session_state.render_progress = 1.0; st.session_state.render_done = True
    except Exception as e:
        st.session_state.render_progress = 0.0; print(f"[render error] {e}")
    finally: st.session_state.rendering = False

# ── Main ─────────────────────────────────────────────────
def main():
    st.set_page_config(page_title=APP_NAME, page_icon="⚡", layout="centered")
    st.markdown(CSS, unsafe_allow_html=True); _init()
    step = st.session_state.get("step", "input")
    if step == "input": _step_input()
    elif step == "processing": _step_processing()
    elif step == "moments": _step_moments()
    st.markdown('<div class="main-wrap footer"><p>⚡ Cliper — Buat klip YouTube instan.</p></div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()