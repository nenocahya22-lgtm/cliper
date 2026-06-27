"""
VideoClipse — AI Video Farming Studio
OpusClip-inspired design · 1 server = UI + Scheduler + Auto Upload
Run: streamlit run app.py
"""
import os, time, uuid, subprocess, shutil, threading, json
from pathlib import Path
import streamlit as st

from core.downloader import VideoDownloader, _default_opts
from core.transcriber import AudioTranscriber, WordTimestamp
from core.finder import ViralMomentFinder, ProcessingResult
from core.editor import SubtitleGenerator, VideoProcessor, SUBTITLE_COLORS, ASPECT_PRESETS, TRANSITIONS
from core.uploader import Uploader
from core.scheduler import Queue, ScheduleStore
from core.describer import generate_title, generate_description
import core.database as db

APP_NAME = "VideoClipse"
APP_ICON = "\u26a1"
SUPPORTED_VIDEO_EXT = {"mp4","mov","avi","mkv","webm","flv","wmv","m4v"}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ACCOUNTS_DIR = os.path.join(BASE_DIR, "accounts")
os.makedirs(OUTPUT_DIR, exist_ok=True)

PAGES = [
    ("dashboard", "Dashboard", "\U0001f4ca"),
    ("new_clip", "New Clip", "\u2795"),
    ("my_clips", "My Clips", "\U0001f3ac"),
    ("queue", "Queue", "\U0001f4cb"),
    ("schedule", "Schedule", "\U0001f4c5"),
    ("accounts", "Accounts", "\U0001f464"),
    ("stats", "Stats", "\U0001f4c8"),
]

PAGE_IDS = [p[0] for p in PAGES]

@st.cache_data(ttl=3600)
def _get_cached_css():
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

:root {
  --bg-sidebar: #0f0f13;
  --bg-main: #f5f5f7;
  --bg-card: #ffffff;
  --primary: #3ecf8e;
  --primary-deep: #2db87a;
  --primary-soft: rgba(62,207,142,0.12);
  --primary-glow: rgba(62,207,142,0.25);
  --ink: #0d0d0d;
  --ink-mute: #6b6b6b;
  --ink-faint: #a1a1a1;
  --ink-on-dark: #e8e8e8;
  --ink-mute-dark: #8a8a8a;
  --hairline: rgba(0,0,0,0.06);
  --hairline-dark: rgba(255,255,255,0.08);
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --shadow-card: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03);
  --shadow-hover: 0 4px 12px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04);
  --sidebar-width: 240px;
  --transition: 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

* { box-sizing: border-box; }

html, body, [data-testid="stApp"] {
  background: var(--bg-main) !important;
  font-family: 'Inter', 'Helvetica Neue', sans-serif;
  color: var(--ink);
}

/* ── Sidebar ────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: var(--bg-sidebar) !important;
  border: none !important;
  padding: 0 !important;
  min-width: var(--sidebar-width) !important;
  max-width: var(--sidebar-width) !important;
  z-index: 100;
}

[data-testid="stSidebar"] > div:first-child {
  background: var(--bg-sidebar) !important;
  padding: 24px 16px !important;
  height: 100vh;
  overflow-y: auto;
  overflow-x: hidden;
}

[data-testid="stSidebar"] > div:first-child::-webkit-scrollbar { width: 0; }

/* Logo */
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 8px 24px 8px;
  border-bottom: 1px solid var(--hairline-dark);
  margin-bottom: 20px;
}

.sidebar-logo-icon {
  width: 32px; height: 32px;
  background: linear-gradient(135deg, var(--primary), var(--primary-deep));
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  box-shadow: 0 2px 8px var(--primary-glow);
}

.sidebar-logo-text {
  font-weight: 700; font-size: 18px; letter-spacing: -0.5px;
  color: #fff; line-height: 1.2;
}

.sidebar-logo-sub {
  font-size: 10px; color: var(--ink-mute-dark);
  letter-spacing: 0.5px; text-transform: uppercase;
}

/* Sidebar buttons */
[data-testid="stSidebar"] .stButton > button {
  justify-content: flex-start !important;
  font-size: 14px !important;
  padding: 10px 14px !important;
  margin-bottom: 2px !important;
  border-radius: var(--radius-md) !important;
  font-weight: 500 !important;
  background: transparent !important;
  border: none !important;
  color: var(--ink-mute-dark) !important;
  box-shadow: none !important;
  transition: all var(--transition) !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: rgba(255,255,255,0.06) !important;
  color: var(--ink-on-dark) !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background: var(--primary-soft) !important;
  color: var(--primary) !important;
  font-weight: 600 !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
  background: var(--primary-soft) !important;
  box-shadow: none !important;
  transform: none !important;
}

/* Account status in sidebar */
.sidebar-accounts {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid var(--hairline-dark);
}

.sidebar-account-row {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 8px; font-size: 12px;
  color: var(--ink-mute-dark);
}

.sidebar-account-dot {
  width: 8px; height: 8px; border-radius: 50%;
  flex-shrink: 0;
}

.sidebar-footer {
  margin-top: 16px; padding: 12px 8px 0;
  border-top: 1px solid var(--hairline-dark);
  font-size: 10px; color: var(--ink-mute-dark);
  line-height: 1.5;
}

/* ── Main Content ───────────────────────────────────────── */
.main-container {
  max-width: 820px; margin: 0 auto; padding: 32px 24px;
}

.page-header {
  font-size: 28px; font-weight: 700; letter-spacing: -0.6px;
  color: var(--ink); margin: 0 0 4px 0;
  line-height: 1.2;
}
.page-sub {
  font-size: 14px; color: var(--ink-mute);
  margin: 0 0 28px 0; line-height: 1.4;
}

/* Cards */
.card {
  background: var(--bg-card); border: 1px solid var(--hairline);
  border-radius: var(--radius-lg); padding: 20px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-card);
  transition: box-shadow var(--transition), border-color var(--transition);
}
.card:hover { box-shadow: var(--shadow-hover); border-color: rgba(0,0,0,0.1); }
.card-flat { box-shadow: none !important; }
.card-flat:hover { box-shadow: none !important; }

/* Dashboard grid */
.dash-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px; margin-bottom: 28px;
}
.dash-card {
  background: var(--bg-card); border-radius: var(--radius-lg);
  padding: 20px; text-align: center;
  border: 1px solid var(--hairline); box-shadow: var(--shadow-card);
  transition: transform var(--transition), box-shadow var(--transition);
}
.dash-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-hover);
}
.dash-num {
  font-size: 34px; font-weight: 700; color: var(--primary);
  margin: 0; line-height: 1;
}
.dash-num-dark { color: var(--ink); }
.dash-label {
  font-size: 12px; color: var(--ink-mute);
  margin: 6px 0 0 0; font-weight: 500;
}
.dash-icon {
  font-size: 24px; margin-bottom: 8px;
}

/* Sidebar button text */
[data-testid="stSidebar"] .stButton > button p {
  font-size: 14px !important;
}

/* Step indicator */
.step-bar {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 24px; padding: 16px; background: var(--bg-card);
  border-radius: var(--radius-lg); border: 1px solid var(--hairline);
}
.step-item {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--ink-faint);
  transition: color var(--transition);
}
.step-item.active { color: var(--ink); font-weight: 600; }
.step-item.done { color: var(--primary); }
.step-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--hairline); flex-shrink: 0;
  transition: background var(--transition);
}
.step-item.active .step-dot { background: var(--primary); }
.step-item.done .step-dot { background: var(--primary); }
.step-line {
  width: 20px; height: 1px; background: var(--hairline); flex-shrink: 0;
}

@media (max-width: 640px) {
  .step-bar {
    flex-wrap: wrap;
    gap: 6px;
    padding: 10px;
  }
  .step-item {
    font-size: 10px;
  }
  .step-line {
    width: 10px;
  }
}

/* Buttons */
.stButton > button {
  border-radius: var(--radius-sm) !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 500 !important; font-size: 14px !important;
  padding: 8px 18px !important;
  border: none !important;
  transition: all var(--transition) !important;
  cursor: pointer !important; line-height: 1.4 !important;
}
.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, var(--primary), var(--primary-deep)) !important;
  color: var(--ink) !important;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
}
.stButton > button[kind="primary"]:hover {
  box-shadow: 0 4px 12px var(--primary-glow) !important;
  transform: translateY(-1px) !important;
}
.stButton > button[kind="primary"]:active {
  transform: translateY(0) !important;
}
.stButton > button[kind="secondary"] {
  background: var(--bg-card) !important;
  color: var(--ink) !important;
  border: 1px solid var(--hairline) !important;
  box-shadow: var(--shadow-card) !important;
}
.stButton > button[kind="secondary"]:hover {
  border-color: var(--primary) !important;
  box-shadow: var(--shadow-hover) !important;
}

/* Inputs */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > select,
.stNumberInput > div > div > input {
  border-radius: var(--radius-sm) !important;
  border: 1px solid var(--hairline) !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 15px !important; color: var(--ink) !important;
  background: var(--bg-card) !important;
  box-shadow: none !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
  border-color: var(--primary) !important;
  box-shadow: 0 0 0 3px var(--primary-soft) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  border-bottom: 1px solid var(--hairline); gap: 0;
  background: var(--bg-card); border-radius: var(--radius-md) var(--radius-md) 0 0;
  padding: 0 4px;
}
.stTabs [data-baseweb="tab"] {
  font-family: 'Inter', sans-serif; font-weight: 500;
  font-size: 13px; color: var(--ink-mute);
  padding: 10px 16px; transition: color var(--transition);
}
.stTabs [aria-selected="true"] { color: var(--primary) !important; }

/* Video */
video { border-radius: var(--radius-lg); border: 1px solid var(--hairline); }

/* Dividers */
hr { border-color: var(--hairline) !important; margin: 20px 0 !important; }

/* Progress */
.stProgress > div > div > div > div { background: linear-gradient(90deg, var(--primary), var(--primary-deep)) !important; }

/* Alerts */
.stAlert { border-radius: var(--radius-sm); border-left: 3px solid var(--primary); }

/* Badges */
.badge {
  display: inline-block; padding: 2px 10px; border-radius: 9999px;
  font-size: 11px; font-weight: 600; letter-spacing: 0.3px;
}
.badge-green { background: var(--primary-soft); color: var(--primary-deep); }
.badge-gray { background: var(--bg-main); color: var(--ink-mute); }
.badge-red { background: rgba(239,68,68,0.1); color: #ef4444; }
.badge-blue { background: rgba(59,130,246,0.1); color: #3b82f6; }

/* Moment cards */
.moment-card {
  background: var(--bg-card); border: 1px solid var(--hairline);
  border-radius: var(--radius-lg); padding: 16px;
  margin-bottom: 10px; box-shadow: var(--shadow-card);
  transition: all var(--transition);
}
.moment-card:hover {
  border-color: var(--primary); box-shadow: var(--shadow-hover);
}

/* Queue cards */
.queue-card {
  background: var(--bg-card); border: 1px solid var(--hairline);
  border-radius: var(--radius-lg); padding: 16px 20px;
  margin-bottom: 10px; box-shadow: var(--shadow-card);
  transition: border-color var(--transition);
}
.queue-card:hover { border-color: var(--primary); }

/* Loading skeleton */
@keyframes skeleton-loading {
  0% { background-position: -200px 0; }
  100% { background-position: calc(200px + 100%) 0; }
}
.skeleton {
  background: linear-gradient(90deg, var(--hairline) 25%, rgba(0,0,0,0.04) 50%, var(--hairline) 75%);
  background-size: 200px 100%; animation: skeleton-loading 1.5s ease-in-out infinite;
  border-radius: var(--radius-sm); height: 16px; margin-bottom: 8px;
}

/* Image placeholder */
.img-placeholder {
  width: 100%; aspect-ratio: 16/9;
  background: linear-gradient(135deg, var(--hairline), var(--bg-main));
  border-radius: var(--radius-lg); display: flex;
  align-items: center; justify-content: center;
  color: var(--ink-faint); font-size: 32px;
}

/* Responsive */
@media (max-width: 640px) {
  .dash-grid { grid-template-columns: 1fr 1fr; }
  .quick-actions { grid-template-columns: 1fr; }
  .main-container { padding: 20px 16px; }
}
</style>"""

def _account_status(platform):
    cfile = os.path.join(ACCOUNTS_DIR, platform.lower(), "cookies.json")
    if Path(cfile).exists():
        try:
            with open(cfile) as f:
                c = json.load(f)
            return "connected", f"{len(c)} cookies"
        except: return "error", "file error"
    return "disconnected", "not logged in"

def _logo():
    st.markdown("""
    <div class="sidebar-logo">
      <div class="sidebar-logo-icon">\u26a1</div>
      <div>
        <div class="sidebar-logo-text">VideoClipse</div>
        <div class="sidebar-logo-sub">AI Video Studio</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

def _get_user():
    """Get current user from Streamlit experimental_user (Cloud) or session state (local)."""
    try:
        if hasattr(st, "experimental_user") and st.experimental_user is not None:
            u = st.experimental_user
            if u.is_logged_in and u.email:
                return {"id": u.email, "name": u.get("name", u.email), "email": u.email, "avatar": u.get("picture", "")}
    except: pass
    if "user" in st.session_state and st.session_state.user:
        return st.session_state.user
    return None

def _login_page():
    st.markdown("""
    <style>
    .login-container { max-width: 400px; margin: 80px auto; text-align: center; }
    .login-logo { font-size: 48px; margin-bottom: 8px; }
    .login-title { font-size: 28px; font-weight: 700; letter-spacing: -0.6px; margin-bottom: 4px; }
    .login-sub { font-size: 14px; color: var(--ink-mute); margin-bottom: 32px; }
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<div class="login-logo">⚡</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-title">VideoClipse</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-sub">AI Video Farming Studio · Sign in to continue</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # On Streamlit Cloud, Google OAuth is built-in
        import urllib.parse
        redirect = "https://videoclipse.streamlit.app"
        if "SUPABASE_URL" in os.environ and "SUPABASE_KEY" in os.environ:
            sb_url = os.environ["SUPABASE_URL"]
            client_id = os.environ.get("SUPABASE_AUTH_CLIENT_ID", "")
            if client_id:
                params = urllib.parse.urlencode({
                    "client_id": client_id,
                    "redirect_uri": redirect + "/oauth/callback",
                    "response_type": "code",
                    "scope": "openid profile email",
                })
                st.markdown(f'<a href="{sb_url}/auth/v1/authorize?{params}" target="_self"><div style="padding:12px 24px;background:#fff;border:1px solid #ddd;border-radius:8px;cursor:pointer;font-weight:500;margin-bottom:12px;display:flex;align-items:center;justify-content:center;gap:8px"><img src="https://www.google.com/favicon.ico" width="18"> Sign in with Google</div></a>', unsafe_allow_html=True)
            else:
                st.info("Configure SUPABASE_AUTH_CLIENT_ID for Google OAuth, or use Guest mode below.")
        else:
            st.info("Local mode: sign in as guest to continue.")

        name = st.text_input("", placeholder="Your name (guest)", key="guest_name")
        if st.button("Continue as Guest", type="primary", use_container_width=True):
            st.session_state.user = {"id": name or "guest", "name": name or "Guest", "email": "", "avatar": ""}
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

def _init_state():
    keys_default = {
        "result": None, "sel_moment": None, "out_video": None,
        "processing": False, "rendering": False,
        "step": 1, "src": "url", "page": "dashboard",
        "edit_queue_id": None, "clips_page": 1, "vurl": "", "farm_url": "",
        "user": None,
    }
    for k, v in keys_default.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if "wd" not in st.session_state or not os.path.exists(st.session_state.wd):
        wd = os.path.join(OUTPUT_DIR, f"work_{uuid.uuid4().hex[:8]}")
        os.makedirs(wd, exist_ok=True)
        st.session_state.wd = wd

def _step_bar(current, steps=None):
    if steps is None:
        steps = ["Input", "Process", "Curate", "Edit", "Preview"]
    n = len(steps)
    html = '<div class="step-bar">'
    for i, s in enumerate(steps):
        idx = i + 1
        cls = "active" if idx == current else ("done" if idx < current else "")
        dot_cls = "active" if idx == current else ("done" if idx < current else "")
        html += f'<span class="step-item {cls}"><span class="step-dot {dot_cls}"></span>{s}</span>'
        if i < n - 1:
            html += '<span class="step-line"></span>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# ── Pages ─────────────────────────────────────────────────

def page_dashboard():
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown('<h1 class="page-header">Dashboard</h1>', unsafe_allow_html=True)
    with col2:
        if st.button("+ New Clip", type="primary", use_container_width=True):
            st.session_state.page = "new_clip"
            st.rerun()

    from farm import _today_count
    count = _today_count()

    st.markdown(f"""
    <div class="dash-grid">
      <div class="dash-card">
        <div class="dash-icon">\U0001f4e8</div>
        <p class="dash-num">{count}</p>
        <p class="dash-label">Uploaded Today</p>
      </div>
      <div class="dash-card">
        <div class="dash-icon">\u23f3</div>
        <p class="dash-num dash-num-dark">{max(0, 10 - count)}</p>
        <p class="dash-label">Remaining Today</p>
      </div>
      <div class="dash-card">
        <div class="dash-icon">\U0001f4cb</div>
        <p class="dash-num dash-num-dark">{len(Queue.list())}</p>
        <p class="dash-label">In Queue</p>
      </div>
      <div class="dash-card">
        <div class="dash-icon">\U0001f3ac</div>
        <p class="dash-num dash-num-dark">{len(list(Path(OUTPUT_DIR).glob("*.mp4")))}</p>
        <p class="dash-label">Total Clips</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<p style="font-size:13px;font-weight:600;color:var(--ink-mute);margin-bottom:10px">Quick Actions</p>', unsafe_allow_html=True)

    q1, q2, q3 = st.columns(3)
    if q1.button("\U0001f517\nCreate from Link", use_container_width=True):
        st.session_state.page = "new_clip"
        st.rerun()
    if q2.button("\U0001f4c1\nUpload Local", use_container_width=True):
        st.session_state.page = "new_clip"
        st.rerun()
    if q3.button("\U0001f33e\nFarm Mode", use_container_width=True):
        st.session_state.page = "new_clip"
        st.rerun()

    recent = sorted(Path(OUTPUT_DIR).glob("*.mp4"), key=os.path.getmtime, reverse=True)[:3]
    if recent:
        st.markdown('<p style="font-size:13px;font-weight:600;color:var(--ink-mute);margin:20px 0 10px">Recent Clips</p>', unsafe_allow_html=True)
        for v in recent:
            sz = v.stat().st_size / (1024*1024)
            mtime = time.strftime("%b %d, %H:%M", time.localtime(v.stat().st_mtime))
            st.markdown(f"""
            <div class="queue-card" style="display:flex;justify-content:space-between;align-items:center">
              <div>
                <div style="font-weight:500;font-size:14px">{v.name}</div>
                <div style="font-size:12px;color:var(--ink-mute)">{sz:.1f} MB \u00b7 {mtime}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

def page_dashboard_router():
    if st.session_state.processing or st.session_state.step == 2:
        return _page_process()
    if st.session_state.step >= 3:
        return _page_multi_step()
    return page_dashboard()

def _page_multi_step():
    if st.session_state.step == 3:
        return _page_curate()
    if st.session_state.step == 4:
        return _page_editor()
    if st.session_state.step == 5:
        return _page_preview()
    return page_dashboard()

def _page_input():
    st.markdown('<h1 class="page-header">New Clip</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Paste a link or upload a file to create viral clips</p>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["\U0001f517 Link", "\U0001f4c1 Upload", "\U0001f33e Farm"])

    with tab1:
        url = st.text_input("", placeholder="https://youtube.com/...", key="vurl_input", label_visibility="collapsed")
        if url:
            st.session_state.vurl = url
            p = VideoDownloader.detect_platform(url)
            if p:
                st.markdown(f'<p style="color:var(--primary);font-size:13px;margin:4px 0">\u2713 Platform: {p}</p>', unsafe_allow_html=True)
                
                # Moment Finder Mode
                mode = st.radio("Metode Analisis Momen", ["Rule-based (Cepat)", "Llama AI (Pintar)"], key="link_moment_mode", horizontal=True)
                st.session_state.moment_mode = mode
                
                if st.button("Download & Analyze", type="primary", use_container_width=True):
                    st.session_state.src = "url"
                    st.session_state.processing = True
                    st.session_state.step = 2
                    st.rerun()
            else:
                st.markdown(f'<p style="color:#ef4444;font-size:13px;margin:4px 0">Platform not supported</p>', unsafe_allow_html=True)

    with tab2:
        up = st.file_uploader("", type=list(SUPPORTED_VIDEO_EXT), label_visibility="collapsed")
        if up:
            sz = len(up.getvalue()) / (1024*1024)
            st.markdown(f'<p style="color:var(--ink-mute);font-size:13px;margin:4px 0">{up.name} ({sz:.1f} MB)</p>', unsafe_allow_html=True)
            
            # Moment Finder Mode
            mode_l = st.radio("Metode Analisis Momen", ["Rule-based (Cepat)", "Llama AI (Pintar)"], key="local_moment_mode", horizontal=True)
            st.session_state.moment_mode = mode_l
            
            if st.button("Process Local Video", type="primary", use_container_width=True):
                wd = st.session_state.wd
                ext = up.name.rsplit(".",1)[-1].lower()
                p = os.path.join(wd, f"up_{uuid.uuid4().hex[:8]}.{ext}")
                with open(p,"wb") as f:
                    f.write(up.getbuffer())
                st.session_state.src = "local"
                st.session_state.local_path = p
                st.session_state.local_name = up.name
                st.session_state.processing = True
                st.session_state.step = 2
                st.rerun()

    with tab3:
        st.markdown('<p style="font-size:14px;color:var(--ink-mute)">One link \u2192 multiple clips \u2192 scheduled upload</p>', unsafe_allow_html=True)
        furl = st.text_input("", placeholder="https://youtube.com/...", key="farm_url_input", label_visibility="collapsed")
        if furl:
            st.session_state.farm_url = furl
        cols = st.columns(3)
        fplat = cols[0].multiselect("Platforms", ["youtube","tiktok","facebook"], default=["youtube"], label_visibility="collapsed")
        fcount = cols[1].number_input("Clips", 1, 10, 5, label_visibility="collapsed")
        ftime = cols[2].text_input("Start time", "08:00", label_visibility="collapsed")
        
        mode_f = st.radio("Metode Analisis Momen (Farm)", ["Rule-based (Cepat)", "Llama AI (Pintar)"], key="farm_moment_mode", horizontal=True)
        st.session_state.moment_mode = mode_f
        
        if st.button("Process & Schedule All", type="primary", use_container_width=True, disabled=not furl):
            if furl:
                with st.spinner("Generating clips..."):
                    threading.Thread(target=_farm_multi, args=(furl, fplat, fcount, ftime), daemon=True).start()
                st.success("Farm job started! Check progress in Queue.")

def _farm_multi(url, platforms, count, start_time):
    from farm import _increment_today, _mark_link_done
    wd = os.path.join(os.path.dirname(__file__), "output", f"farm_{int(time.time())}")
    use_llm = st.session_state.get("moment_mode", "Rule-based (Cepat)") == "Llama AI (Pintar)"
    model_name = st.session_state.get("ollama_model", "llama3.2:latest")
    clips = VideoProcessor.auto_process_multi(url, wd, count, 30, 60, True, "Kuning", "", True, aspect="Portrait 9:16 (Shorts/TikTok)", use_llm=use_llm, model_name=model_name)
    if not clips:
        st.error("Failed to generate clips")
        return
    base_h, base_m = int(start_time.split(":")[0]), int(start_time.split(":")[1])
    for i, c in enumerate(clips):
        hours = (base_h + i) % 24
        sched = f"{hours:02d}:{base_m:02d}"
        Queue.add(url, platforms, sched, "", int(c["duration"]), 30)

def _page_process():
    st.markdown('<h1 class="page-header">Processing...</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Downloading, transcribing, and analyzing your video</p>', unsafe_allow_html=True)
    src = st.session_state.get("src", "url")
    wd = st.session_state.wd
    res = ProcessingResult()
    prog = st.progress(0)
    stat = st.empty()

    def step(msg, p, sub=""):
        html = f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px"><div class="skeleton" style="width:16px;height:16px;border-radius:50%;flex-shrink:0"></div><span style="color:var(--ink-mute);font-size:14px">{msg}</span></div>'
        if sub:
            html += f'<p style="font-size:12px;color:var(--ink-faint);margin:0 0 8px 26px">{sub}</p>'
        stat.markdown(html, unsafe_allow_html=True)
        prog.progress(p)

    try:
        if src == "url":
            url = st.session_state.get("vurl", "")
            if not url:
                return
            step("Mendapatkan info video...", 0.05)
            import yt_dlp
            try:
                with yt_dlp.YoutubeDL(_default_opts()) as ydl:
                    info = ydl.extract_info(url, download=False)
            except: info = {}
            title = info.get("title", "Unknown")
            dur = info.get("duration", 0) or 0
            res.title = title
            res.duration = dur

            step("Download audio untuk transkripsi...", 0.2,
                 "Mengonversi ke 16000Hz mono WAV...")
            audio, _, _ = VideoDownloader.download_audio(url, wd, max_dur=600)
            if audio and Path(audio).exists():
                res.audio_path = audio
                step("Transcribing with Whisper...", 0.35,
                     "Ini yang paling lama — sabar ya")
                text, wts = AudioTranscriber.transcribe(audio)
                if text:
                    res.transcript = text
                    res.word_timestamps = wts
            
            use_llm = st.session_state.get("moment_mode", "Rule-based (Cepat)") == "Llama AI (Pintar)"
            model_name = st.session_state.get("ollama_model", "llama3.2:latest")
            step(f"Analyzing viral moments (menggunakan {'Llama AI' if use_llm else 'Rule-based'})...", 0.6)
            res.viral_moments = ViralMomentFinder.find_moments(res.transcript or "", dur, res.word_timestamps, use_llm=use_llm, model_name=model_name)
            
            step("Downloading video clip...", 0.8,
                 "Mengunduh bagian video berkualitas tinggi")
            vp = VideoDownloader.download_video_clip(url, wd, 0, min(dur+5, 600))
            if vp:
                res.video_path = vp
        else:
            lp = st.session_state.get("local_path", "")
            if not lp:
                return
            step("Extracting audio...", 0.1)
            audio, dur = VideoDownloader.extract_audio_from_local(lp, wd)
            if not audio:
                return
            res.audio_path = audio
            res.title = st.session_state.get("local_name", "video.mp4")
            res.duration = dur
            res.video_path = lp
            step("Transcribing (mode cepat)...", 0.35,
                 f"Durasi: {dur:.0f}s")
            text, wts = AudioTranscriber.transcribe(audio)
            if text:
                res.transcript = text
                res.word_timestamps = wts
            
            use_llm = st.session_state.get("moment_mode", "Rule-based (Cepat)") == "Llama AI (Pintar)"
            model_name = st.session_state.get("ollama_model", "llama3.2:latest")
            step("Analyzing moments...", 0.65)
            res.viral_moments = ViralMomentFinder.find_moments(res.transcript or "", dur, wts, use_llm=use_llm, model_name=model_name)
        prog.progress(1.0)
        st.session_state.result = res
        st.session_state.processing = False
        st.session_state.step = 3
        time.sleep(0.3)
        st.rerun()
    except Exception as e:
        st.error(str(e))
        st.session_state.processing = False
        st.session_state.step = 1
        time.sleep(2)
        st.rerun()

def _page_curate():
    res = st.session_state.get("result")
    if not res:
        st.session_state.step = 1
        st.rerun()
        return
    st.markdown('<h1 class="page-header">Choose a Moment</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="page-sub">{res.title[:60]} \u2014 {res.duration:.0f}s total</p>', unsafe_allow_html=True)
    _step_bar(3)
    sel = None
    for i, m in enumerate(res.viral_moments):
        d = m.end_time - m.start_time
        icon = '\U0001f3a3' if m.category=='HOOK' else '\U0001f525' if m.category=='KLIMAKS' else '\U0001f4e2' if m.category=='CTA' else '\u2b50'
        st.markdown(f"""
        <div class="moment-card" style="padding:16px">
          <div style="display:flex;align-items:center;gap:12px">
            <div style="width:44px;height:44px;background:var(--bg-main);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0">{icon}</div>
            <div style="flex:1;min-width:0">
              <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                <span style="font-weight:600;font-size:14px">{m.category}</span>
                <span class="badge badge-green">{d:.0f}s</span>
              </div>
              <p style="margin:2px 0 0;font-size:12px;color:var(--ink-mute)">{int(m.start_time//60)}:{int(m.start_time%60):02d} \u2013 {int(m.end_time//60)}:{int(m.end_time%60):02d}</p>
              <p style="margin:2px 0 0;font-size:12px;color:var(--ink-faint)">{m.reason}</p>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button(f"Select Moment {i+1}", key=f"sel_{i}", use_container_width=True):
            sel = i
    if sel is not None:
        st.session_state.sel_moment = res.viral_moments[sel]
        st.session_state.step = 4
        st.rerun()

def _page_editor():
    res = st.session_state.get("result")
    mom = st.session_state.get("sel_moment")
    if not res or not mom:
        st.session_state.step = 3
        st.rerun()
        return
    st.markdown('<h1 class="page-header">Edit Clip</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="page-sub">{mom.category} \u2014 {mom.reason}</p>', unsafe_allow_html=True)
    _step_bar(4)

    c1, c2 = st.columns(2)
    md = min(max(mom.end_time-mom.start_time, 5), 120)
    dur = float(res.duration)
    sv = c1.number_input("Start", 0.0, max(0.0,dur-5), max(0.0,mom.start_time), 0.5)
    ev = c2.number_input("End", sv+5, max(sv+5,dur), max(sv+5, min(sv+md,dur)), 0.5)
    st.markdown(f'<p style="font-size:13px;color:var(--ink-mute);margin-bottom:16px">Duration: {ev-sv:.1f}s</p>', unsafe_allow_html=True)

    # Timeline preview (CSS-based)
    clip_dur = ev - sv
    st.markdown(f"""
    <div style="background:var(--bg-card);border:1px solid var(--hairline);border-radius:var(--radius-md);padding:12px;margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--ink-faint);margin-bottom:4px">
        <span>{sv:.1f}s</span><span>{ev:.1f}s</span>
      </div>
      <div style="height:24px;background:var(--bg-main);border-radius:6px;position:relative;overflow:hidden">
        <div style="height:100%;width:{min(100,clip_dur/dur*100)}%;background:linear-gradient(90deg,var(--primary),var(--primary-deep));border-radius:6px;opacity:0.8"></div>
      </div>
      <div style="font-size:11px;color:var(--ink-mute);margin-top:4px">Clip: {clip_dur:.1f}s / Total: {dur:.0f}s</div>
    </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs(["Visual & Effects", "Transitions & Speed", "Text Overlay", "Subtitles", "Audio", "Title & Upload"])

    with tabs[0]:
        col1, col2, col3 = st.columns(3)
        asp = col1.selectbox("Aspect Ratio", list(ASPECT_PRESETS.keys()), index=0)
        cf = col2.selectbox("Color Preset", ["none","warm","cool","vibrant","vintage","neon"], index=0)

        cnt = st.slider("Contrast", 0.5, 2.0, 1.0, 0.1)
        brg = st.slider("Brightness", -0.5, 0.5, 0.0, 0.05)
        sat = st.slider("Saturation", 0.0, 3.0, 1.0, 0.1)

        st.markdown('<p style="font-size:13px;font-weight:600;margin:10px 0 2px 0">Effects</p>', unsafe_allow_html=True)
        cols_eff = st.columns(4)
        vig = cols_eff[0].checkbox("Vignette", value=False)
        sep = cols_eff[1].checkbox("Sepia", value=False)
        gry = cols_eff[2].checkbox("B&W", value=False)
        glict = cols_eff[3].checkbox("Glitch", value=False)

        cols_eff2 = st.columns(3)
        shp = cols_eff2[0].checkbox("Sharpen", value=False)
        edg = cols_eff2[1].checkbox("Edge Detect", value=False)
        mr = cols_eff2[2].checkbox("Mirror (HFlip)", value=True)
        nr = st.checkbox("Noise Reduction", value=True)

    with tabs[1]:
        tr_col1, tr_col2 = st.columns(2)
        sp = tr_col1.selectbox("Speed", ["1.0x","1.05x","1.07x","1.1x","1.15x"], index=0)
        speed_ramp = tr_col2.selectbox("Speed Ramp", ["none","ease_in","ease_out"], index=0)

        st.markdown('<p style="font-size:13px;font-weight:600;margin:8px 0 2px">Transition (opening)</p>', unsafe_allow_html=True)
        trans_keys = list(TRANSITIONS.keys())
        trans = st.selectbox("", trans_keys, index=0, label_visibility="collapsed")

        st.markdown('<p style="font-size:13px;font-weight:600;margin:8px 0 2px">Fade</p>', unsafe_allow_html=True)
        fi_c, fo_c = st.columns(2)
        fi = fi_c.slider("Fade In", 0.0, 2.0, 0.5, 0.1)
        fo = fo_c.slider("Fade Out", 0.0, 2.0, 0.8, 0.1)

    with tabs[2]:
        text_overlay = st.text_input("Overlay Text", "", placeholder="Teks yang muncul di video")
        if text_overlay:
            st.markdown('<p style="font-size:12px;color:var(--ink-mute)">Teks akan muncul di bagian atas video</p>', unsafe_allow_html=True)

    with tabs[3]:
        sb = st.checkbox("Show Subtitles", value=True)
        col1, col2 = st.columns(2)
        sc = col1.selectbox("Color", list(SUBTITLE_COLORS.keys()), index=0)
        sub_sz = col2.slider("Font Size", 10, 100, 44, 2)

        col3, col4 = st.columns(2)
        sub_fnt = col3.text_input("Font", "Montserrat")
        sub_alg_label = col4.selectbox("Align", ["Tengah (Center)", "Bawah (Bottom)"], index=0)
        sub_alg = 5 if "Tengah" in sub_alg_label else 2
        sub_upp = st.checkbox("UPPERCASE", value=True)

    with tabs[4]:
        st.markdown('<p style="font-size:13px;color:var(--ink-mute)">Background music (opsional). Letakkan file MP3 di folder project.</p>', unsafe_allow_html=True)
        music_files = [""] + sorted([f.name for f in Path(".").glob("*.mp3")] + [f.name for f in Path(".").glob("*.wav")])
        bg_music = st.selectbox("Music", music_files, index=0)
        music_vol = st.slider("Music Volume", 0.0, 1.0, 0.3, 0.05) if bg_music else 0.3

    with tabs[5]:
        text = res.transcript or ""
        model_name = st.session_state.get("ollama_model", "llama3.2:latest")
        jd = generate_title(text, res.title, res.viral_moments)
        ds = generate_description(text, jd, res.title, res.viral_moments)
        j = st.text_input("Title", jd)
        d = st.text_area("Description", ds, height=80)

        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown('<p style="font-size:13px;font-weight:500;margin-bottom:4px">Post to Platforms</p>', unsafe_allow_html=True)
        plat_cols = st.columns(3)
        post_youtube = plat_cols[0].checkbox("YouTube", value=True)
        post_tiktok = plat_cols[1].checkbox("TikTok", value=False)
        post_facebook = plat_cols[2].checkbox("Facebook", value=False)
        platforms = []
        if post_youtube: platforms.append("youtube")
        if post_tiktok: platforms.append("tiktok")
        if post_facebook: platforms.append("facebook")

        apst = st.checkbox("Auto-Post ke akun tertaut setelah render", value=False)
        auto_delete = st.checkbox("Auto-delete video setelah semua platform terupload", value=True)

    if st.button("Render Clip", type="primary", use_container_width=True, disabled=st.session_state.rendering):
        st.session_state.rendering = True
        _do_render(
            sv, ev, sb, sc, fi, fo, asp, sp, mr, cf, nr, j, d,
            contrast=cnt, brightness=brg, saturation=sat,
            vignette=vig, sepia=sep, grayscale=gry, sharpen=shp, edge_detect=edg,
            sub_size=sub_sz, sub_font=sub_fnt, sub_align=sub_alg, sub_upper=sub_upp,
            auto_post=apst, platforms=platforms, auto_delete=auto_delete,
            transition=trans, speed_ramp=speed_ramp, text_overlay=text_overlay,
            glitch=glict, bg_music=bg_music, music_volume=music_vol,
        )

def _do_render(stt, ett, show_sub, sub_col, fi, fo, aspect, speed_str, mirror, color_f, noise_r, title, desc,
               contrast=1.0, brightness=0.0, saturation=1.0,
               vignette=False, sepia=False, grayscale=False, sharpen=False, edge_detect=False,
               sub_size=44, sub_font="Montserrat", sub_align=5, sub_upper=True,
               auto_post=False, platforms=None, auto_delete=True,
               transition="none", speed_ramp="none", text_overlay="",
               glitch=False, bg_music="", music_volume=0.3):
    res = st.session_state.get("result")
    if not res:
        return
    sts = st.empty()
    prg = st.progress(0)
    wd = st.session_state.wd
    cid = uuid.uuid4().hex[:8]
    out = os.path.join(wd, f"out_{cid}.mp4")
    sub_path = os.path.join(wd, f"subs_{cid}.ass")
    src = st.session_state.get("src", "url")
    speed = {"1.0x":1.0,"1.05x":1.05,"1.07x":1.07,"1.1x":1.1,"1.15x":1.15}.get(speed_str, 1.0)
    try:
        sts.markdown(f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px"><div class="skeleton" style="width:16px;height:16px;border-radius:50%"></div><span style="color:var(--ink-mute);font-size:14px">Preparing...</span></div>', unsafe_allow_html=True)
        prg.progress(0.1)
        clip_path = None
        if src == "url":
            clip_path = VideoDownloader.download_video_clip(st.session_state.get("vurl",""), wd, stt, ett)
        else:
            lp = st.session_state.get("local_path","")
            if lp and Path(lp).exists():
                clip_path = os.path.join(wd, f"clip_{cid}.mp4")
                VideoDownloader.trim_local_video(lp, clip_path, stt, ett)
                if not Path(clip_path).exists():
                    clip_path = res.video_path
        if not clip_path:
            raise Exception("No video source")
        prg.progress(0.3)
        if show_sub and res.word_timestamps:
            rel = [wt for wt in res.word_timestamps if wt.start<ett and wt.end>stt]
            if rel:
                shifted = [WordTimestamp(w.word, max(0,w.start-stt), w.end-stt) for w in rel]
                SubtitleGenerator.generate_ass(shifted, sub_path, SUBTITLE_COLORS.get(sub_col,"&H00FFFF&"), font=sub_font, size=sub_size, alignment=sub_align, uppercase=sub_upper)
        prg.progress(0.5)
        sts.markdown(f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px"><div class="skeleton" style="width:16px;height:16px;border-radius:50%"></div><span style="color:var(--ink-mute);font-size:14px">Rendering... {speed}x {color_f}</span></div>', unsafe_allow_html=True)
        ok, err = VideoProcessor.process_clip(
            clip_path, out,
            sub_path if Path(sub_path).exists() else "", "",
            0, ett-stt, fi, fo, speed, mirror, color_f, noise_r, aspect=aspect,
            contrast=contrast, brightness=brightness, saturation=saturation,
            vignette=vignette, sepia=sepia, grayscale=grayscale, sharpen=sharpen, edge_detect=edge_detect,
            transition=transition, text_overlay=text_overlay,
            speed_ramp=speed_ramp, glitch=glitch, bg_music=bg_music, music_volume=music_volume
        )
        if not ok:
            raise Exception(err)
        prg.progress(1.0)
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)[:30]
        ts = time.strftime("%Y%m%d_%H%M%S")
        final_name = f"{ts}_{safe_title}.mp4"
        final_path = os.path.join(OUTPUT_DIR, final_name)
        shutil.copy2(out, final_path)
        st.session_state.out_video = final_path
        st.session_state.rendering = False
        st.session_state.step = 5
        st.session_state._title = title
        st.session_state._desc = desc
        
        # Save clip to database
        user = st.session_state.get("user", {})
        clip_id = db.clip_save(
            final_path, title=title, description=desc,
            source_url=st.session_state.get("vurl", ""),
            duration=ett-stt, platforms=platforms or [],
            user_id=user.get("id", "")
        )
        st.session_state._clip_id = clip_id
        
        # Trigger background auto-post if requested
        if auto_post and platforms:
            target_platforms = [p for p in platforms if _account_status(p)[0] == "connected"]
            if target_platforms:
                def bg_upload(clip_path=final_path, clip_title=title, clip_desc=desc, cid=clip_id, plats=target_platforms):
                    from core.uploader import Uploader
                    for p in plats:
                        try:
                            Uploader.upload(p, clip_path, clip_title, clip_desc)
                            db.clip_update_upload_status(cid, p, "done")
                            db.stats_increment_today()
                        except Exception as ex:
                            print(f"[AUTO POST ERROR] Gagal upload ke {p}: {ex}")
                            db.clip_update_upload_status(cid, p, "error")
                    # Auto-delete if all platforms done
                    if auto_delete:
                        db.clips_cleanup_uploaded()
                threading.Thread(target=bg_upload, daemon=True).start()
                st.toast(f"Auto-Post ke {', '.join(target_platforms)} dimulai!")
        
        st.rerun()
    except Exception as e:
        st.error(str(e))
        st.session_state.rendering = False

def _page_preview():
    ov = st.session_state.get("out_video")
    if not ov or not Path(ov).exists():
        st.session_state.step = 4
        st.rerun()
        return
    sz = Path(ov).stat().st_size / (1024*1024)
    fname = Path(ov).name
    st.markdown('<h1 class="page-header">Preview</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="page-sub">{fname} \u2014 {sz:.1f} MB</p>', unsafe_allow_html=True)
    _step_bar(5)

    st.video(str(ov))

    j = st.session_state.get("_title", "")
    d = st.session_state.get("_desc", "")
    with st.expander("Title & Description", expanded=True):
        st.text_input("Title", j, key="pub_title")
        st.text_area("Description", d, height=80, key="pub_desc")
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:14px;font-weight:500;margin-bottom:8px">Upload to</p>', unsafe_allow_html=True)
    cols = st.columns(3)
    for plat, col in zip(["youtube","tiktok","facebook"], cols):
        sts, msg = _account_status(plat)
        if sts == "connected":
            if col.button(f"\U0001f4e4 {plat.title()}", use_container_width=True):
                try:
                    Uploader.upload(plat, ov, st.session_state.get("pub_title",j), st.session_state.get("pub_desc",d))
                    st.success(f"Uploaded to {plat}!")
                except Exception as e:
                    st.error(f"Failed: {e}")
        else:
            col.button(f"\U0001f512 {plat.title()}", disabled=True, use_container_width=True)
    st.markdown("<hr>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("+ New Clip", use_container_width=True):
        for k in ["result","sel_moment","out_video"]:
            st.session_state[k] = None
        st.session_state.step = 1
        st.rerun()
    if c2.button("\U0001f5d1 Delete", type="secondary", use_container_width=True):
        try:
            Path(ov).unlink(missing_ok=True)
            meta = ov + ".json"
            if Path(meta).exists():
                Path(meta).unlink(missing_ok=True)
        except:
            pass
        for k in ["result","sel_moment","out_video"]:
            st.session_state[k] = None
        st.session_state.step = 1
        st.rerun()

def page_my_clips():
    if st.session_state.step == 5:
        return _page_preview()
    st.markdown('<h1 class="page-header">My Clips</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Saved videos in <code>output/</code></p>', unsafe_allow_html=True)
    videos = sorted(Path(OUTPUT_DIR).glob("*.mp4"), key=os.path.getmtime, reverse=True)
    if not videos:
        st.markdown(f'<div style="text-align:center;padding:40px;color:var(--ink-faint)">\U0001f3ac<p style="font-size:14px;margin-top:8px">No clips yet. Create one from New Clip.</p></div>', unsafe_allow_html=True)
        return

    per_page = 8
    total = len(videos)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = st.session_state.get("clips_page", 1)
    if page > total_pages:
        page = total_pages
        st.session_state.clips_page = page

    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total)

    for v in videos[start_idx:end_idx]:
        sz = v.stat().st_size / (1024*1024)
        mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(v.stat().st_mtime))
        st.markdown(f"""
        <div class="queue-card">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div style="flex:1;min-width:0">
              <div style="font-weight:500;font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{v.name}</div>
              <div style="font-size:12px;color:var(--ink-mute);margin:2px 0">{sz:.1f} MB \u00b7 {mtime}</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1,1,1])
        if c1.button("Preview", key=f"pv_{v.stem}", use_container_width=True):
            st.video(str(v))
        if c2.button("Upload", key=f"up_{v.stem}", use_container_width=True):
            st.session_state.out_video = str(v)
            st.session_state._title = v.stem
            st.session_state._desc = ""
            st.session_state.step = 5
            st.rerun()
        if c3.button("Delete", key=f"del_{v.stem}", use_container_width=True):
            try:
                v.unlink(missing_ok=True)
                meta = str(v) + ".json"
                if Path(meta).exists():
                    Path(meta).unlink(missing_ok=True)
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

    if total_pages > 1:
        st.markdown(f'<p style="text-align:center;font-size:12px;color:var(--ink-mute);margin:12px 0">Page {page} of {total_pages} ({total} total)</p>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1,2,1])
        if c1.button("\u25c0 Prev", use_container_width=True, disabled=(page <= 1)):
            st.session_state.clips_page = page - 1
            st.rerun()
        if c3.button("Next \u25b6", use_container_width=True, disabled=(page >= total_pages)):
            st.session_state.clips_page = page + 1
            st.rerun()

def page_queue():
    if st.session_state.step == 5:
        return _page_preview()
    st.markdown('<h1 class="page-header">Queue</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Scheduled uploads \u2014 edit each item before posting</p>', unsafe_allow_html=True)
    q = Queue.list()
    if not q:
        st.markdown(f'<div style="text-align:center;padding:40px;color:var(--ink-faint)">\U0001f4cb<p style="font-size:14px;margin-top:8px">No items in queue. Add from the Farm tab.</p></div>', unsafe_allow_html=True)
        return

    for item in q:
        status_badge = "badge-green" if item['status'] == 'pending' else "badge-gray" if item['status'] == 'done' else "badge-red"
        st.markdown(f"""
        <div class="queue-card">
          <div style="display:flex;justify-content:space-between;align-items:start">
            <div style="flex:1;min-width:0">
              <div style="font-size:14px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{item['url'][:60]}</div>
              <div style="font-size:12px;color:var(--ink-mute);margin:4px 0">
                <span class="badge {status_badge}">{item['status']}</span>
                {' '.join(item.get('platforms',['youtube']))} \u00b7 {item.get('schedule_at','unscheduled')}
              </div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1,1,1])
        if item['status'] == 'pending':
            if c1.button("Edit", key=f"eq_{item['id']}", use_container_width=True):
                st.session_state.edit_queue_id = item['id']
            if c2.button("Skip", key=f"sk_{item['id']}", use_container_width=True):
                Queue.update(item['id'], schedule_at="")
            if c3.button("Delete", key=f"del_{item['id']}", use_container_width=True):
                qq = Queue.list()
                qq = [i for i in qq if i['id'] != item['id']]
                with open(os.path.join(os.path.dirname(__file__),"queue","queue.json"),"w") as f:
                    json.dump(qq, f, indent=2)
                st.rerun()

    edit_id = st.session_state.get("edit_queue_id")
    if edit_id:
        from core.scheduler import _read_json, _write_json, QUEUE_FILE
        qq = _read_json(QUEUE_FILE)
        target = next((i for i in qq if i['id'] == edit_id), None)
        if target:
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown(f'<h3 style="font-size:18px;font-weight:600">Edit Queue Item</h3>', unsafe_allow_html=True)
            new_url = st.text_input("URL", target['url'])
            new_plat = st.multiselect("Platforms", ["youtube","tiktok","facebook"], default=target.get('platforms',['youtube']))
            new_sched = st.text_input("Schedule (HH:MM)", target.get('schedule_at',''))
            if st.button("Save Changes", type="primary"):
                target['url'] = new_url
                target['platforms'] = new_plat
                target['schedule_at'] = new_sched
                _write_json(QUEUE_FILE, qq)
                st.session_state.edit_queue_id = None
                st.rerun()

    if st.button("Clear Completed", use_container_width=True):
        Queue.clear_done()
        st.rerun()

def page_accounts():
    if st.session_state.step == 5:
        return _page_preview()
    st.markdown('<h1 class="page-header">Accounts</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Login once \u2014 cookies stored locally</p>', unsafe_allow_html=True)
    for plat in ["youtube", "tiktok", "facebook"]:
        sts, msg = _account_status(plat)
        dot = "\u25cf" if sts == "connected" else "\u25cb"
        clr = "#3ecf8e" if sts == "connected" else "#5a5a5a"
        st.markdown(f"""
        <div class="queue-card" style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <div style="font-weight:500;font-size:15px"><span style="color:{clr}">{dot}</span> {plat.title()}</div>
            <div style="font-size:12px;color:var(--ink-mute)">{'Connected' if sts=='connected' else 'Disconnected'} \u00b7 {msg}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns([1,1])
        if c1.button(f"Login {plat.title()} (Browser PC)", use_container_width=True):
            st.info(f"Browser akan terbuka untuk login {plat}. Cek jendela CMD yang muncul.")
            subprocess.Popen(f'start cmd /c python farm.py --login {plat}', shell=True)
        if c2.button(f"Logout", key=f"lg_{plat}", use_container_width=True):
            cfile = os.path.join(ACCOUNTS_DIR, plat.lower(), "cookies.json")
            if Path(cfile).exists():
                Path(cfile).unlink()
                st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)
    with st.expander("Metode Instan: Tempel Cookies JSON (HP / Laptop)", expanded=True):
        plat_sel = st.selectbox("Pilih Platform", ["youtube", "tiktok", "facebook"])
        cookies_txt = st.text_area("Tempel Cookies JSON di sini", placeholder='[\n  {\n    "name": "...",\n    "value": "...",\n    ...\n  }\n]', height=150)
        if st.button("Simpan Cookies", type="primary", use_container_width=True):
            if cookies_txt.strip():
                try:
                    cdata = json.loads(cookies_txt.strip())
                    if isinstance(cdata, list):
                        Uploader.save_cookies(plat_sel, cdata)
                        st.success(f"Cookies untuk {plat_sel.title()} berhasil disimpan!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Format tidak valid! Harus berupa JSON List/Array.")
                except Exception as ex:
                    st.error(f"Error parsing JSON: {ex}")
            else:
                st.error("Cookies teks tidak boleh kosong!")

def page_schedule():
    if st.session_state.step == 5:
        return _page_preview()
    st.markdown('<h1 class="page-header">Schedule</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Set daily upload times</p>', unsafe_allow_html=True)
    sched = ScheduleStore.list_all()
    for name, data in sched.items():
        st.markdown(f"""
        <div class="queue-card" style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <div style="font-weight:500;font-size:15px">{name}</div>
            <div style="font-size:12px;color:var(--ink-mute)">{', '.join(data.get('times',[]))}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Delete", key=f"ds_{name}", use_container_width=True):
            ScheduleStore.delete(name)
            st.rerun()
    with st.expander("Add Schedule"):
        name = st.text_input("Name", "harian")
        times = st.text_input("Times (comma separated)", "08:00,12:00,18:00")
        if st.button("Save Schedule", type="primary"):
            ScheduleStore.set(name, [t.strip() for t in times.split(",") if t.strip()])
            st.rerun()

def page_stats():
    if st.session_state.step == 5:
        return _page_preview()
    from farm import _today_count
    st.markdown('<h1 class="page-header">Stats</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Daily upload statistics</p>', unsafe_allow_html=True)
    count = _today_count()
    st.markdown(f"""
    <div class="dash-grid">
      <div class="dash-card">
        <div class="dash-icon">\U0001f4e8</div>
        <p class="dash-num">{count}</p>
        <p class="dash-label">Uploaded Today</p>
      </div>
      <div class="dash-card">
        <div class="dash-icon">\u23f3</div>
        <p class="dash-num dash-num-dark">{max(0, 10-count)}</p>
        <p class="dash-label">Remaining</p>
      </div>
      <div class="dash-card">
        <div class="dash-icon">\U0001f4cb</div>
        <p class="dash-num dash-num-dark">{len(Queue.list())}</p>
        <p class="dash-label">In Queue</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── Main ─────────────────────────────────────────────────

@st.cache_resource
def _start_scheduler():
    from core.scheduler import SchedulerEngine
    from farm import process_one
    eng = SchedulerEngine(process_callback=lambda item: threading.Thread(
        target=process_one, args=(item["url"],),
        kwargs={"platforms": item.get("platforms",["youtube"]),"anti_copy":True}, daemon=True).start())
    eng.start()
    return eng

def main():
    st.set_page_config(page_title="VideoClipse", page_icon="⚡", layout="centered")
    st.markdown(_get_cached_css(), unsafe_allow_html=True)
    _init_state()

    # Auto-login from Streamlit Cloud
    user = _get_user()
    if user:
        st.session_state.user = user
    if not st.session_state.get("user"):
        _login_page()

    _start_scheduler()

    current_page = st.session_state.get("page", "dashboard")
    if current_page not in PAGE_IDS:
        current_page = "dashboard"

    with st.sidebar:
        _logo()

        for pid, label, icon in PAGES:
            is_active = pid == current_page
            if st.button(
                f"{icon} {label}",
                key=f"nav_{pid}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.page = pid
                st.rerun()

        # Ollama Model Selection
        st.markdown('<p style="font-size:12px;font-weight:600;color:var(--ink-mute-dark);margin:12px 0 2px 8px">Ollama Model</p>', unsafe_allow_html=True)
        models = ["llama3.2:latest", "qwen2.5-coder:1.5b", "Custom"]
        sel_model = st.selectbox("", models, index=0, key="ollama_model_select", label_visibility="collapsed")
        if sel_model == "Custom":
            custom_model = st.text_input("Nama Model Custom", value="llama3.2:latest", key="custom_ollama_model", label_visibility="collapsed")
            st.session_state.ollama_model = custom_model
        else:
            st.session_state.ollama_model = sel_model

        st.markdown('<div class="sidebar-accounts">', unsafe_allow_html=True)
        for plat in ["youtube","tiktok","facebook"]:
            sts, msg = _account_status(plat)
            dot = "\u25cf" if sts == "connected" else "\u25cb"
            clr = "#3ecf8e" if sts == "connected" else "#5a5a5a"
            st.markdown(
                f'<div class="sidebar-account-row">'
                f'<span class="sidebar-account-dot" style="background:{clr}"></span>'
                f' {plat.title()}</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        user = st.session_state.get("user", {})
        st.markdown(f"""
        <div style="padding:12px 8px;border-top:1px solid var(--hairline-dark);margin-top:8px">
          <div style="display:flex;align-items:center;gap:8px">
            <div style="width:28px;height:28px;border-radius:50%;background:var(--primary-soft);display:flex;align-items:center;justify-content:center;font-size:12px;color:var(--primary);font-weight:600">{user.get('name','?')[0].upper()}</div>
            <div style="font-size:12px;color:var(--ink-on-dark);font-weight:500">{user.get('name','Guest')}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Logout", key="logout_btn", use_container_width=True):
            st.session_state.user = None
            st.rerun()

        st.markdown(f"""
        <div class="sidebar-footer">
          {APP_NAME} v7 &middot; {"Cloud ☁️" if db.is_cloud() else "Local"} &middot; No API key
        </div>
        """, unsafe_allow_html=True)

    page_map = {
        "dashboard": page_dashboard_router,
        "new_clip": _page_input,
        "my_clips": page_my_clips,
        "queue": page_queue,
        "schedule": page_schedule,
        "accounts": page_accounts,
        "stats": page_stats,
    }

    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    page_map.get(current_page, page_dashboard_router)()
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
