"""
VideoClipse — AI Video Farming Studio
Nintendo.com 2001 Design · 1 server = UI + Scheduler + Auto Upload
Run: streamlit run app.py
"""
import os, time, uuid, subprocess, shutil, threading, json
from pathlib import Path
import streamlit as st

from core.downloader import VideoDownloader, _default_opts, ProxyRotator, _load_proxies, FFMPEG_PATH
from core.transcriber import AudioTranscriber, WordTimestamp
from core.finder import ViralMomentFinder, ProcessingResult
from core.editor import SubtitleGenerator, VideoProcessor, SUBTITLE_COLORS, ASPECT_PRESETS, TRANSITIONS
from core.uploader import Uploader
from core.scheduler import Queue, ScheduleStore
from core.describer import generate_title, generate_description
import core.database as db
import core.auth as auth

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
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap');

:root {
  /* ── Brand & Accent ────────────────────────────── */
  --nintendo-red:      #ff4a5a;
  --signal:            #8b5cf6; /* Violet */
  --nav-gold:          #a78bfa;

  /* ── Surface / Chrome ──────────────────────────── */
  --canvas:            #08090d;
  --muted-indigo:      #94a3b8;
  --surface:           #10111a;
  --carbon:            #0b0c10;
  --carbon-soft:       #151622;

  /* ── Text ──────────────────────────────────────── */
  --ink:               #f8fafc;
  --ink-soft:          #94a3b8;
  --on-primary:        #ffffff;
  --on-carbon:         #cbd5e1;

  /* ── Semantic ──────────────────────────────────── */

  /* ── Spacing ───────────────────────────────────── */
  --sp-xxs: 2px;  --sp-xs: 4px;  --sp-sm: 8px;
  --sp-md: 12px;  --sp-lg: 16px; --sp-xl: 24px; --sp-xxl: 32px;

  /* ── Radii ─────────────────────────────────────── */
  --r-none: 0px;    --r-xs: 4px;  --r-sm: 8px;
  --r-md: 12px;     --r-lg: 16px; --r-full: 9999px;

  --sidebar-width: 250px;
  --content-max: 840px;
}

/* ── Base Reset ─────────────────────────────────────────── */
* { box-sizing: border-box; }
html, body, [data-testid="stApp"], .stApp {
  background: var(--canvas) !important;
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  color: var(--ink) !important;
}

/* Hide standard Streamlit header/menus */
[data-testid="stToolbar"] { display: none; }
[data-testid="stDecoration"] { display: none; }
#MainMenu { visibility: hidden; }
header { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
.appview-container .main .block-container { padding: 0 !important; max-width: none !important; }

/* ══════════════════════════════════════════════════════════
   SIDEBAR — Cyber Dark Pane
   ══════════════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
  background: var(--carbon) !important;
  border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
  padding: 0 !important;
  min-width: var(--sidebar-width) !important;
  max-width: var(--sidebar-width) !important;
  position: relative;
}

[data-testid="stSidebar"] > div:first-child {
  background: transparent !important;
  padding: var(--sp-xl) var(--sp-lg) !important;
  height: 100vh;
  overflow-y: auto;
  overflow-x: hidden;
}

[data-testid="stSidebar"] > div:first-child::-webkit-scrollbar { width: 0; }

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
  padding: 0 var(--sp-sm) var(--sp-xl) var(--sp-sm);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  margin-bottom: var(--sp-lg);
}
.sidebar-logo-icon {
  width: 36px; height: 36px;
  background: linear-gradient(135deg, #7c3aed, #db2777);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
}
.sidebar-logo-text {
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 700; font-size: 18px;
  letter-spacing: -0.2px;
  color: var(--surface);
  background: linear-gradient(to right, #a78bfa, #f472b6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  line-height: 1.2;
}
.sidebar-logo-sub {
  font-size: 10px; color: var(--on-carbon);
  letter-spacing: 0.5px;
  font-weight: 500;
}

/* Sidebar Nav Buttons */
[data-testid="stSidebar"] .stButton > button {
  justify-content: flex-start !important;
  font-size: 14px !important;
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  font-weight: 600 !important;
  text-transform: none !important;
  letter-spacing: 0px !important;
  padding: 12px 16px !important;
  margin-bottom: var(--sp-xs) !important;
  border-radius: 12px !important;
  background: transparent !important;
  border: none !important;
  color: var(--on-carbon) !important;
  box-shadow: none !important;
  transition: all 0.2s ease !important;
  clip-path: none !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: rgba(255, 255, 255, 0.04) !important;
  color: var(--ink) !important;
  transform: translateX(4px);
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background: rgba(124, 58, 237, 0.1) !important;
  color: var(--nav-gold) !important;
  box-shadow: none !important;
  border-left: 3px solid #7c3aed !important;
  border-radius: 0 12px 12px 0 !important;
}

/* Sidebar accounts list */
.sidebar-accounts {
  margin-top: auto;
  padding-top: var(--sp-lg);
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}
.sidebar-account-row {
  display: flex; align-items: center; gap: var(--sp-sm);
  padding: 8px 10px; font-size: 13px;
  font-family: 'Plus Jakarta Sans', sans-serif;
  color: var(--on-carbon);
}
.sidebar-account-dot {
  width: 8px; height: 8px; border-radius: var(--r-full);
  flex-shrink: 0;
  box-shadow: 0 0 6px currentColor;
}
.sidebar-footer {
  margin-top: var(--sp-lg); padding: var(--sp-md) var(--sp-sm) 0;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  font-size: 11px; color: var(--ink-soft);
  line-height: 1.5;
  font-family: 'Plus Jakarta Sans', sans-serif;
}

/* Sidebar Model Selector */
.sidebar-model { margin: var(--sp-lg) 0 var(--sp-xs) var(--sp-sm); }
.sidebar-model label {
  font-size: 11px; font-weight: 600;
  color: var(--ink-soft);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: block; margin-bottom: 6px;
}
.sidebar-model select {
  font-size: 13px; padding: 8px 12px;
  background: var(--carbon-soft);
  color: var(--ink);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  width: 100%;
  font-family: 'Plus Jakarta Sans', sans-serif;
  clip-path: none !important;
}

/* User Profile Badge */
.sidebar-user-badge {
  display: flex; align-items: center; gap: var(--sp-sm);
  padding: var(--sp-md) var(--sp-sm);
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}
.sidebar-user-avatar {
  width: 32px; height: 32px; border-radius: var(--r-full);
  background: linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(219, 39, 119, 0.2));
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; color: var(--nav-gold);
  font-weight: 700; flex-shrink: 0;
  border: 1px solid rgba(124, 58, 237, 0.3);
}
.sidebar-user-name {
  font-size: 13px; color: var(--ink);
  font-weight: 600;
}

/* ══════════════════════════════════════════════════════════
   MAIN CONTENT AREA
   ══════════════════════════════════════════════════════════ */
.main-container {
  max-width: var(--content-max);
  margin: 0 auto;
  padding: var(--sp-xxl) var(--sp-xl);
  position: relative;
}

.page-header {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.5px;
  color: #fff;
  margin: 0 0 6px 0;
  line-height: 1.2;
  background: linear-gradient(to right, #fff, #a78bfa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: none;
  -webkit-text-stroke: 0px !important;
}
.page-sub {
  font-size: 14px;
  color: var(--ink-soft);
  margin: 0 0 var(--sp-xl) 0;
  line-height: 1.5;
  font-family: 'Plus Jakarta Sans', sans-serif;
}

/* ══════════════════════════════════════════════════════════
   DASHBOARD STATS & LAYOUT
   ══════════════════════════════════════════════════════════ */
.dash-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--sp-lg);
  margin-bottom: var(--sp-xl);
}
.dash-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: var(--sp-xl);
  text-align: center;
  position: relative;
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(8px);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  clip-path: none !important;
}
.dash-card:hover {
  transform: translateY(-4px);
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(139, 92, 246, 0.3);
  box-shadow: 0 12px 40px 0 rgba(139, 92, 246, 0.15);
}
.dash-num {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 36px; font-weight: 700;
  color: #fff;
  margin: 0; line-height: 1;
}
.dash-num-dark { color: #fff; }
.dash-label {
  font-size: 11px; color: var(--ink-soft);
  margin: 8px 0 0 0;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}
.dash-icon {
  font-size: 26px; margin-bottom: var(--sp-xs);
  filter: drop-shadow(0 0 8px currentColor);
}

/* ══════════════════════════════════════════════════════════
   BUTTONS — Glowing Gradient Look
   ══════════════════════════════════════════════════════════ */
.stButton > button {
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  font-weight: 600 !important;
  font-size: 13px !important;
  text-transform: none !important;
  letter-spacing: 0px !important;
  padding: 10px 20px !important;
  border-radius: 12px !important;
  border: none !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
  cursor: pointer !important;
  line-height: 1.4 !important;
  clip-path: none !important;
}
.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%) !important;
  color: var(--on-primary) !important;
  box-shadow: 0 4px 15px rgba(124, 58, 237, 0.35) !important;
}
.stButton > button[kind="primary"]:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(124, 58, 237, 0.5) !important;
}
.stButton > button[kind="primary"]:active {
  transform: translateY(1px);
}
.stButton > button[kind="secondary"] {
  background: rgba(255, 255, 255, 0.04) !important;
  color: var(--ink) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  box-shadow: none !important;
}
.stButton > button[kind="secondary"]:hover {
  background: rgba(255, 255, 255, 0.07) !important;
  border-color: rgba(139, 92, 246, 0.4) !important;
  transform: translateY(-1px);
}

/* ══════════════════════════════════════════════════════════
   CARDS & MEMENT PANELS
   ══════════════════════════════════════════════════════════ */
.card, .queue-card, .moment-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: var(--sp-lg);
  margin-bottom: var(--sp-md);
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.15);
  backdrop-filter: blur(8px);
  transition: all 0.2s ease;
  clip-path: none !important;
}
.card:hover, .queue-card:hover, .moment-card:hover {
  border-color: rgba(139, 92, 246, 0.25);
  background: rgba(255, 255, 255, 0.03);
  transform: translateY(-2px);
}
.card-flat { box-shadow: none !important; border-color: transparent !important; background: transparent !important; }

/* ══════════════════════════════════════════════════════════
   WORKFLOW STEPS BAR
   ══════════════════════════════════════════════════════════ */
.step-bar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: var(--sp-xl);
  padding: var(--sp-lg) var(--sp-xl);
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  clip-path: none !important;
}
.step-item {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: var(--ink-soft);
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 500;
  text-transform: none;
  letter-spacing: 0px;
}
.step-item.active { color: #fff; font-weight: 700; }
.step-item.done { color: var(--nav-gold); }
.step-dot {
  width: 8px; height: 8px; border-radius: var(--r-full);
  background: rgba(255, 255, 255, 0.15); flex-shrink: 0;
  box-shadow: 0 0 0 2px transparent;
  transition: all 0.2s ease;
}
.step-item.active .step-dot { background: #8b5cf6; box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.3), 0 0 10px #8b5cf6; }
.step-item.done .step-dot { background: var(--nav-gold); }
.step-line {
  flex-grow: 1; height: 2px;
  background: rgba(255, 255, 255, 0.06);
  margin: 0 16px;
  flex-shrink: 0;
}

/* ══════════════════════════════════════════════════════════
   TABS — Flat Underlined
   ══════════════════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  gap: 8px;
  background: transparent;
  padding: 0;
  box-shadow: none;
  clip-path: none !important;
}
.stTabs [data-baseweb="tab"] {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 600;
  font-size: 13px;
  color: var(--ink-soft);
  text-transform: none;
  letter-spacing: 0px;
  padding: 12px 18px;
  border-radius: 8px 8px 0 0;
  transition: all 0.2s ease;
}
.stTabs [aria-selected="true"] {
  color: #8b5cf6 !important;
  background: rgba(139, 92, 246, 0.05) !important;
  border-bottom: 2px solid #8b5cf6 !important;
}

/* ══════════════════════════════════════════════════════════
   INPUTS & TEXT FIELDS
   ══════════════════════════════════════════════════════════ */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > select,
.stNumberInput > div > div > input {
  clip-path: none !important;
  border-radius: 12px !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  font-size: 14px !important;
  color: #fff !important;
  background: #111219 !important;
  box-shadow: none !important;
  padding: 10px 14px !important;
  transition: all 0.2s ease !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
  border-color: #8b5cf6 !important;
  box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.25) !important;
}

.stCheckbox label, .stRadio label {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 13px;
  color: var(--on-carbon);
}
.stCheckbox [data-baseweb="checkbox"], .stRadio [data-baseweb="radio"] {
  border-color: rgba(255, 255, 255, 0.2) !important;
}
.stCheckbox [data-baseweb="checkbox"][aria-checked="true"],
.stRadio [data-baseweb="radio"][aria-checked="true"] {
  background: #8b5cf6 !important;
  border-color: #8b5cf6 !important;
}

.stSlider label, .stSelectbox label, .stMultiSelect label, .stNumberInput label, .stFileUploader label {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 12px;
  font-weight: 600;
  text-transform: none;
  letter-spacing: 0px;
  color: var(--ink-soft);
  margin-bottom: 6px;
}
.stSlider [data-baseweb="slider"] div {
  background: rgba(255, 255, 255, 0.1) !important;
}
.stSlider [data-baseweb="slider"] div[role="slider"] {
  background: #8b5cf6 !important;
  border-color: #8b5cf6 !important;
}

.stFileUploader [data-testid="stFileUploadDropzone"] {
  border: 1px dashed rgba(139, 92, 246, 0.4);
  border-radius: 16px;
  background: rgba(139, 92, 246, 0.02);
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 13px;
  padding: 24px;
  transition: all 0.2s ease;
  clip-path: none !important;
}
.stFileUploader [data-testid="stFileUploadDropzone"]:hover {
  border-color: #8b5cf6;
  background: rgba(139, 92, 246, 0.05);
}

/* ══════════════════════════════════════════════════════════
   PROGRESS & UTILITIES
   ══════════════════════════════════════════════════════════ */
.stProgress > div > div > div > div {
  background: linear-gradient(90deg, #8b5cf6, #ec4899) !important;
  clip-path: none !important;
  border-radius: 8px !important;
}
.stProgress > div > div > div {
  background: rgba(255, 255, 255, 0.06) !important;
  clip-path: none !important;
  border-radius: 8px !important;
  height: 6px !important;
}

.stAlert {
  clip-path: none !important;
  border-radius: 12px;
  border-left: 4px solid var(--nintendo-red);
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 13px;
  background: rgba(239, 68, 68, 0.05) !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  font-family: 'Plus Jakarta Sans', sans-serif;
  letter-spacing: 0.5px;
  clip-path: none !important;
}
.badge-green { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.badge-gray { background: rgba(255, 255, 255, 0.05); color: #94a3b8; }
.badge-red { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.badge-blue { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }

/* ══════════════════════════════════════════════════════════
   EXPANDERS
   ══════════════════════════════════════════════════════════ */
.streamlit-expanderHeader {
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  font-weight: 600 !important;
  font-size: 13px !important;
  text-transform: none !important;
  letter-spacing: 0px !important;
  color: #fff !important;
  background: rgba(255, 255, 255, 0.02) !important;
  border: 1px solid rgba(255, 255, 255, 0.06) !important;
  border-radius: 12px !important;
  padding: 12px 16px !important;
  clip-path: none !important;
}
.streamlit-expanderContent {
  background: rgba(255, 255, 255, 0.01) !important;
  border: 1px solid rgba(255, 255, 255, 0.04) !important;
  border-top: none !important;
  border-radius: 0 0 12px 12px !important;
  padding: var(--sp-md) !important;
  box-shadow: none;
}

/* ══════════════════════════════════════════════════════════
   MEDIA & LAYOUTS
   ══════════════════════════════════════════════════════════ */
video {
  border-radius: 16px !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
  clip-path: none !important;
}

hr {
  border-top: 1px solid rgba(255, 255, 255, 0.06) !important;
  margin: var(--sp-lg) 0 !important;
}
.dotted-divider {
  border-top: 1px dashed rgba(255, 255, 255, 0.08);
}

.stMetric {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: var(--sp-lg);
  box-shadow: 0 8px 24px rgba(0,0,0,0.1);
  clip-path: none !important;
}
.stMetric label {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--ink-soft);
}
.stMetric [data-testid="stMetricValue"] {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 28px;
  font-weight: 700;
  color: #fff;
}

@keyframes skeleton-loading {
  0% { background-position: -200px 0; }
  100% { background-position: calc(200px + 100%) 0; }
}
.skeleton {
  background: linear-gradient(90deg, rgba(255,255,255,0.03) 25%, rgba(139,92,246,0.1) 50%, rgba(255,255,255,0.03) 75%);
  background-size: 200px 100%;
  animation: skeleton-loading 1.5s ease-in-out infinite;
  border-radius: 6px;
  height: 16px;
  clip-path: none !important;
}

a {
  color: #a78bfa !important;
  text-decoration: none;
  transition: all 0.2s ease;
}
a:hover { color: #f472b6 !important; }

p, code, small {
  font-family: 'Plus Jakarta Sans', sans-serif;
}
code {
  font-size: 12px;
  background: rgba(255, 255, 255, 0.05);
  color: #f472b6;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  padding: 2px 6px;
  clip-path: none !important;
}

/* Hamburger menu wrap */
.hamburger-wrap {
  position: absolute;
  top: 10px;
  left: 15px;
  z-index: 99999;
}
.hamburger-wrap .stButton > button {
  width: 42px !important;
  height: 42px !important;
  min-width: 42px !important;
  background: rgba(255, 255, 255, 0.04) !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  border-radius: 12px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  font-size: 22px !important;
  color: #fff !important;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
  clip-path: none !important;
}
.hamburger-wrap .stButton > button:hover {
  background: rgba(255, 255, 255, 0.07) !important;
  border-color: rgba(139, 92, 246, 0.4) !important;
}

.stSuccess, .stInfo {
  background: rgba(16, 185, 129, 0.05) !important;
  border-left: 4px solid #10b981 !important;
  border-radius: 12px;
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 13px;
  clip-path: none !important;
}

[data-testid="stSidebar"] {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* RESPONSIVE */
@media (max-width: 720px) {
  [data-testid="stSidebarCollapsedControl"] {
    display: none !important;
  }
  [data-testid="stSidebar"] {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    height: 100vh !important;
    z-index: 99995 !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    min-width: var(--sidebar-width) !important;
    max-width: var(--sidebar-width) !important;
  }
  [data-testid="stSidebar"] .stButton > button span:last-child { display: none; }
  .sidebar-logo-text, .sidebar-logo-sub,
  .sidebar-accounts, .sidebar-footer, .sidebar-user-name { display: none; }
  .sidebar-model label { display: none; }
  .sidebar-model select { font-size: 10px; padding: 2px 4px; min-width: 44px; }
  .sidebar-logo { padding-bottom: var(--sp-sm); }
  .sidebar-logo-icon { width: 28px; height: 28px; font-size: 14px; }
  .sidebar-user-avatar { width: 22px; height: 22px; font-size: 9px; }
  .main-container { padding: var(--sp-lg) var(--sp-md); }
  .dash-grid { grid-template-columns: 1fr 1fr; }
  .quick-actions-grid { grid-template-columns: 1fr; }
  .grid-3 { grid-template-columns: 1fr; }
  .grid-2 { grid-template-columns: 1fr; }
  .step-bar { flex-direction: column; align-items: flex-start; gap: 8px; }
  .step-line { display: none; }
}
</style>"""

def _account_status(platform):
    cfile = os.path.join(ACCOUNTS_DIR, platform.lower(), "cookies.json")
    if Path(cfile).exists():
        try:
            with open(cfile) as f:
                c = json.load(f)
            return "connected", f"{len(c)} cookies"
        except Exception: return "error", "file error"
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
    try:
        if hasattr(st, "experimental_user") and st.experimental_user is not None:
            u = st.experimental_user
            if u.is_logged_in and u.email:
                return {"id": u.email, "name": u.get("name", u.email), "email": u.email, "avatar": u.get("picture", "")}
    except Exception: pass
    if "user" in st.session_state and st.session_state.user:
        return st.session_state.user
    return None

def _fmt_time(seconds):
    """Format detik ke MM:SS atau HH:MM:SS yang jelas."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _login_page():
    st.markdown("""
    <style>
    .login-container { max-width: 400px; margin: 80px auto; text-align: center; }
    .login-logo { font-size: 48px; margin-bottom: 12px; filter: drop-shadow(0 0 10px rgba(124,58,237,0.5)); }
    .login-title { font-size: 32px; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 6px; color: #fff; font-family: 'Space Grotesk', sans-serif; background: linear-gradient(to right, #a78bfa, #f472b6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .login-sub { font-size: 13px; color: #94a3b8; margin-bottom: 32px; font-family: 'Plus Jakarta Sans', sans-serif; }
    .login-box { background: rgba(17,19,28,0.75); border: 1px solid rgba(255,255,255,0.08); border-radius: 20px; backdrop-filter: blur(16px); padding: 32px; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }
    .login-error { color: #f87171; font-size: 12px; font-weight: 600; margin: 8px 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    .login-success { color: #34d399; font-size: 12px; font-weight: 600; margin: 8px 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    .login-toggle { font-size: 12px; color: var(--ink-soft); margin-top: 16px; font-family: 'Plus Jakarta Sans', sans-serif; }
    .login-toggle a { color: var(--nav-gold) !important; cursor: pointer; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.markdown('<div class="login-logo">\u26a1</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-title">VideoClipse</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-sub">AI Video Studio · Masuk dengan akun Anda</div>', unsafe_allow_html=True)

    # Toggle antara Login dan Register
    if "login_mode" not in st.session_state:
        st.session_state.login_mode = "login"

    if "login_msg" in st.session_state:
        msg = st.session_state.login_msg
        cls = "login-success" if msg.startswith("✓") else "login-error"
        st.markdown(f'<div class="{cls}">{msg}</div>', unsafe_allow_html=True)
        del st.session_state.login_msg

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Username", placeholder="Masukkan username", key="login_username", label_visibility="collapsed")
        password = st.text_input("Password", type="password", placeholder="Masukkan password", key="login_password", label_visibility="collapsed")

        col_a, col_b = st.columns(2)
        if st.session_state.login_mode == "login":
            with col_a:
                if st.button("Masuk", type="primary", use_container_width=True):
                    ok, msg, user = auth.login(username, password)
                    if ok:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.session_state.login_msg = f"\u2716 {msg}"
                        st.rerun()
            with col_b:
                if st.button("Daftar", use_container_width=True):
                    st.session_state.login_mode = "register"
                    st.rerun()
        else:
            with col_a:
                if st.button("Daftar Akun Baru", type="primary", use_container_width=True):
                    ok, msg = auth.register(username, password)
                    if ok:
                        st.session_state.login_msg = f"\u2713 {msg}"
                        st.session_state.login_mode = "login"
                    else:
                        st.session_state.login_msg = f"\u2716 {msg}"
                    st.rerun()
            with col_b:
                if st.button("Kembali", use_container_width=True):
                    st.session_state.login_mode = "login"
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

def _init_state():
    keys_default = {
        "result": None, "sel_moment": None, "out_video": None,
        "processing": False, "rendering": False,
        "render_progress": 0.0, "render_step": "", "render_done": False,
        "preview_fx_path": None,
        "step": 1, "src": "url", "page": "dashboard",
        "edit_queue_id": None, "clips_page": 1, "vurl": "", "farm_url": "",
        "user": None, "sidebar_open": False,
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
        steps = ["Masukkan Link", "Proses Video", "Pilih Momen", "Edit Video", "Pratinjau"]
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
    count = db.stats_today_count()
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
    st.markdown('<p style="font-size:11px;font-weight:700;color:var(--ink-soft);margin-bottom:var(--sp-md);text-transform:uppercase;letter-spacing:0.5px">Quick Actions</p>', unsafe_allow_html=True)
    q1, q2, q3 = st.columns(3)
    if q1.button("\U0001f517\nCreate from Link", use_container_width=True):
        st.session_state.page = "new_clip"
        st.rerun()
    if q2.button("\U0001f4c1\nUpload Local", use_container_width=True):
        st.session_state.page = "new_clip"
        st.rerun()

    # ── Dashboard Drag & Drop Zone ─────────────────────────────
    st.markdown(
        '<p style="font-size:11px;font-weight:700;color:var(--ink-soft);'
        'margin:var(--sp-lg) 0 var(--sp-sm);text-transform:uppercase;'
        'letter-spacing:0.5px">📥 Quick Upload — Drop video langsung</p>',
        unsafe_allow_html=True
    )
    dash_up = st.file_uploader(
        "Drop video here to instantly find viral moments",
        type=list(SUPPORTED_VIDEO_EXT),
        key="dash_upload",
        label_visibility="collapsed"
    )
    if dash_up:
        wd = st.session_state.wd
        ext = dash_up.name.rsplit(".",1)[-1].lower()
        p = os.path.join(wd, f"up_{uuid.uuid4().hex[:8]}.{ext}")
        with open(p,"wb") as f:
            f.write(dash_up.getbuffer())
        st.session_state.src = "local"
        st.session_state.local_path = p
        st.session_state.local_name = dash_up.name
        st.session_state.moment_mode = "Rule-based (Cepat)"
        st.session_state.processing = True
        st.session_state.step = 2
        st.rerun()

    if q3.button("\U0001f33e\nFarm Mode", use_container_width=True):
        st.session_state.page = "new_clip"
        st.rerun()
    recent = sorted(Path(OUTPUT_DIR).glob("*.mp4"), key=os.path.getmtime, reverse=True)[:3]
    if recent:
        st.markdown('<p style="font-size:11px;font-weight:700;color:var(--ink-soft);margin:var(--sp-lg) 0 var(--sp-sm);text-transform:uppercase;letter-spacing:0.5px">Recent Clips</p>', unsafe_allow_html=True)
        for v in recent:
            sz = v.stat().st_size / (1024*1024)
            mtime = time.strftime("%b %d, %H:%M", time.localtime(v.stat().st_mtime))
            st.markdown(f"""
            <div class="queue-card" style="display:flex;justify-content:space-between;align-items:center;padding:var(--sp-md) var(--sp-lg)">
              <div>
                <div style="font-weight:700;font-size:12px;color:#fff">{v.name}</div>
                <div style="font-size:10px;color:var(--ink-soft);margin-top:2px">{sz:.1f} MB · {mtime}</div>
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
    st.markdown('<p class="page-sub">Drop video langsung dari desktop &mdash; atau tempel link YouTube/TikTok</p>', unsafe_allow_html=True)

    # Hero: Drag & Drop Zone Raksasa
    st.markdown(
        '<div style="background:rgba(255,255,255,0.02);border:1px dashed rgba(139,92,246,0.3);'
        'border-radius:20px;padding:var(--sp-xl);'
        'text-align:center;margin-bottom:var(--sp-lg);box-shadow:0 8px 32px rgba(0,0,0,0.15)">'
        '<div style="font-size:48px;margin-bottom:var(--sp-sm);filter:drop-shadow(0 0 8px rgba(139,92,246,0.3))">📁</div>'
        '<p style="font-size:18px;font-weight:700;color:#fff;margin:0 0 6px">Drop Video di Sini</p>'
        '<p style="font-size:13px;color:var(--ink-soft);margin:0">'
        'MP4, MOV, AVI, MKV, WEBM &mdash; langsung detect momen viral tanpa download'
        '</p></div>',
        unsafe_allow_html=True
    )
    up = st.file_uploader(
        "Upload Video",
        type=list(SUPPORTED_VIDEO_EXT),
        key="newclip_upload",
        label_visibility="collapsed"
    )
    if up:
        sz = len(up.getvalue()) / (1024*1024)
        st.markdown(f'<p style="color:var(--ink-soft);font-size:11px;margin:4px 0">{up.name} ({sz:.1f} MB)</p>', unsafe_allow_html=True)
        mode_l = st.radio(
            "Metode Analisis Momen",
            ["Rule-based (Cepat)", "Llama AI (Pintar)"],
            key="nc_moment_mode",
            horizontal=True
        )
        st.session_state.moment_mode = mode_l
        if st.button("🎬 Process Video & Find Viral Moments", type="primary", use_container_width=True):
            wd = st.session_state.wd
            ext = up.name.rsplit(".",1)[-1].lower()
            p = os.path.join(wd, f"up_{uuid.uuid4().hex[:8]}.{ext}")
            with open(p,"wb") as f:
                f.write(up.getbuffer())
            st.session_state.src = "local"
            st.session_state.local_path = p
            st.session_state.local_name = up.name
            st.session_state.page = "dashboard"
            st.session_state.processing = True
            st.session_state.step = 2
            st.rerun()

    st.markdown('<hr>', unsafe_allow_html=True)

    # URL Input &mdash; secondary
    with st.expander("🔗 Atau pakai link YouTube / TikTok / Facebook", expanded=False):
        url = st.text_input(
            "Video URL",
            placeholder="https://youtube.com/...",
            key="vurl_input",
            label_visibility="collapsed"
        )
        if url:
            st.session_state.vurl = url
            p = VideoDownloader.detect_platform(url)
            if p:
                st.markdown(f'<p style="color:var(--nav-gold);font-size:11px;margin:4px 0;font-weight:700">\u2713 Platform: {p}</p>', unsafe_allow_html=True)
                mode_url = st.radio(
                    "Metode Analisis Momen",
                    ["Rule-based (Cepat)", "Llama AI (Pintar)"],
                    key="url_moment_mode",
                    horizontal=True
                )
                st.session_state.moment_mode = mode_url
                if st.button("📥 Download & Analyze", type="primary", use_container_width=True):
                    st.session_state.src = "url"
                    st.session_state.page = "dashboard"
                    st.session_state.processing = True
                    st.session_state.step = 2
                    st.rerun()
            else:
                st.markdown(f'<p style="color:var(--nintendo-red);font-size:11px;margin:4px 0;font-weight:700">Platform not supported</p>', unsafe_allow_html=True)

    # Farm Mode &mdash; secondary
    with st.expander("🌾 Farm Mode &mdash; Satu link \u2192 banyak clip \u2192 auto upload", expanded=False):
        furl = st.text_input(
            "Farm URL",
            placeholder="https://youtube.com/...",
            key="farm_url_input",
            label_visibility="collapsed"
        )
        if furl:
            st.session_state.farm_url = furl
        cols = st.columns(3)
        fplat = cols[0].multiselect(
            "Platforms",
            ["youtube","tiktok","facebook"],
            default=["youtube"],
            label_visibility="collapsed"
        )
        fcount = cols[1].number_input(
            "Clips", 1, 10, 5,
            label_visibility="collapsed"
        )
        ftime = cols[2].text_input(
            "Start time", "08:00",
            label_visibility="collapsed"
        )
        mode_farm = st.radio(
            "Metode Analisis Momen (Farm)",
            ["Rule-based (Cepat)", "Llama AI (Pintar)"],
            key="farm_moment_mode",
            horizontal=True
        )
        st.session_state.moment_mode = mode_farm
        if st.button(
            "Process & Schedule All",
            type="primary",
            use_container_width=True,
            disabled=not furl
        ):
            if furl:
                with st.spinner("Generating clips..."):
                    threading.Thread(
                        target=_farm_multi,
                        args=(furl, fplat, fcount, ftime),
                        daemon=True
                    ).start()
                st.success("Farm job started! Check progress in Queue.")

def _farm_multi(url, platforms, count, start_time):
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
    st.markdown('<h1 class="page-header">Memproses Video...</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Mengunduh, mentranskripsi, dan menganalisis video Anda</p>', unsafe_allow_html=True)
    src = st.session_state.get("src", "url")
    wd = st.session_state.wd
    res = ProcessingResult()
    prog = st.progress(0)
    stat = st.empty()
    def step(msg, p, sub=""):
        html = f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px"><div class="skeleton" style="width:16px;height:16px;flex-shrink:0"></div><span style="color:var(--ink-soft);font-size:12px;font-weight:700">{msg}</span></div>'
        if sub:
            html += f'<p style="font-size:10px;color:var(--muted-indigo);margin:0 0 8px 26px">{sub}</p>'
        stat.markdown(html, unsafe_allow_html=True)
        prog.progress(p)
    try:
        if src == "url":
            url = st.session_state.get("vurl", "")
            if not url:
                return
            step("Mendapatkan info video...", 0.05, "Mengambil metadata dari tautan...")
            import yt_dlp
            try:
                with yt_dlp.YoutubeDL(_default_opts()) as ydl:
                    info = ydl.extract_info(url, download=False)
            except Exception: info = {}
            title = info.get("title", "Unknown")
            dur = info.get("duration", 0) or 0
            res.title = title
            res.duration = dur
            step("Mengunduh audio untuk transkripsi...", 0.2, "Mengonversi ke format WAV 16000Hz...")
            audio, _, _ = VideoDownloader.download_audio(url, wd, max_dur=600)
            if audio and Path(audio).exists():
                res.audio_path = audio
                step("Mentranskripsi dengan Whisper AI...", 0.35, "Memproses audio untuk mengenali kata-kata — ini memerlukan waktu")
                text, wts = AudioTranscriber.transcribe(audio)
                if text:
                    res.transcript = text
                    res.word_timestamps = wts
            use_llm = st.session_state.get("moment_mode", "Rule-based (Cepat)") == "Llama AI (Pintar)"
            model_name = st.session_state.get("ollama_model", "llama3.2:latest")
            step("Menganalisis momen viral...", 0.6, "Mendeteksi Hook, Klimaks, dan CTA terbaik...")
            res.viral_moments = ViralMomentFinder.find_moments(res.transcript or "", dur, res.word_timestamps, use_llm=use_llm, model_name=model_name)
            step("Mengunduh klip video...", 0.8, "Mengunduh bagian video resolusi tinggi")
            vp = VideoDownloader.download_video_clip(url, wd, 0, min(dur+5, 600))
            if vp:
                res.video_path = vp
        else:
            lp = st.session_state.get("local_path", "")
            if not lp:
                return
            step("Mengekstrak audio...", 0.1, "Memisahkan audio dari video lokal...")
            audio, dur = VideoDownloader.extract_audio_from_local(lp, wd)
            if not audio:
                return
            res.audio_path = audio
            res.title = st.session_state.get("local_name", "video.mp4")
            res.duration = dur
            res.video_path = lp
            step("Mentranskripsi (mode cepat)...", 0.35, f"Durasi video: {dur:.0f} detik")
            text, wts = AudioTranscriber.transcribe(audio)
            if text:
                res.transcript = text
                res.word_timestamps = wts
            use_llm = st.session_state.get("moment_mode", "Rule-based (Cepat)") == "Llama AI (Pintar)"
            model_name = st.session_state.get("ollama_model", "llama3.2:latest")
            step("Menganalisis momen viral...", 0.65, "Mencari bagian paling menarik dengan AI...")
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
    st.markdown('<h1 class="page-header">Pilih Momen Terbaik</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="page-sub">{res.title[:60]} \u2014 Durasi total {res.duration:.0f} detik</p>', unsafe_allow_html=True)
    _step_bar(3)
    sel = None
    for i, m in enumerate(res.viral_moments):
        d = m.end_time - m.start_time
        icon = '\U0001f3a3' if m.category=='HOOK' else '\U0001f525' if m.category=='KLIMAKS' else '\U0001f4e2' if m.category=='CTA' else '\u2b50'
        st.markdown(f"""
        <div class="moment-card" style="padding:var(--sp-lg)">
          <div style="display:flex;align-items:center;gap:var(--sp-md)">
            <div style="width:40px;height:40px;background:rgba(255,255,255,0.04);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;border:1px solid rgba(255,255,255,0.06)">{icon}</div>
            <div style="flex:1;min-width:0">
              <div style="display:flex;align-items:center;gap:var(--sp-sm);flex-wrap:wrap">
                <span style="font-weight:700;font-size:13px;color:#fff;font-family:Arial,sans-serif">{m.category}</span>
                <span class="badge badge-green">{d:.0f}s</span>
              </div>
              <p style="margin:2px 0 0;font-size:11px;color:var(--ink-soft)">\U0001f504 Mulai: <strong>{_fmt_time(m.start_time)}</strong> \u2013 Selesai: <strong>{_fmt_time(m.end_time)}</strong> (durasi: {d:.0f}s)</p>
              <p style="margin:2px 0 0;font-size:10px;color:var(--muted-indigo)">{m.reason}</p>
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
    st.markdown('<h1 class="page-header">Edit Video</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="page-sub">{mom.category} \u2014 {mom.reason}</p>', unsafe_allow_html=True)
    _step_bar(4)

    c1, c2 = st.columns(2)
    md = min(max(mom.end_time-mom.start_time, 5), 120)
    dur = float(res.duration)
    sv = c1.number_input("Start", 0.0, max(0.0,dur-5), max(0.0,mom.start_time), 0.5)
    ev = c2.number_input("End", sv+5, max(sv+5,dur), max(sv+5, min(sv+md,dur)), 0.5)
    st.markdown(f'<p style="font-size:11px;color:var(--ink-soft);margin-bottom:var(--sp-lg);font-weight:700;text-transform:uppercase;letter-spacing:0.3px">Duration: {ev-sv:.1f}s</p>', unsafe_allow_html=True)
    clip_dur = ev - sv
    st.markdown(f"""
    <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:var(--sp-md);margin-bottom:var(--sp-lg)">
      <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--muted-indigo);margin-bottom:4px">
        <span>{sv:.1f}s</span><span>{ev:.1f}s</span>
      </div>
      <div style="height:20px;background:rgba(255,255,255,0.03);border-radius:6px;position:relative;overflow:hidden">
        <div style="height:100%;width:{min(100,clip_dur/max(dur,0.1)*100)}%;background:var(--signal);opacity:0.8"></div>
      </div>
      <div style="font-size:10px;color:var(--ink-soft);margin-top:4px;font-weight:700">Clip: {clip_dur:.1f}s / Total: {dur:.0f}s</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Video Preview — 9:16 Portrait (YouTube Shorts) ─────────
    if res and res.video_path and Path(res.video_path).exists():
        st.markdown(
            '<p style="font-size:11px;font-weight:700;margin:var(--sp-lg) 0 var(--sp-xs);text-transform:uppercase;letter-spacing:0.3px;color:var(--ink-soft)">'
            '\U0001f4fd Preview Clip (9:16 Portrait)'
            '</p>',
            unsafe_allow_html=True
        )

        # Generate preview clip — nama file deterministic (dari start/end)
        # Biar gak regenerate tiap kali user ubah slider
        preview_path = os.path.join(st.session_state.wd, f"preview_{int(sv)}_{int(ev)}.mp4")
        preview_ready = Path(preview_path).exists()

        if not preview_ready and not st.session_state.get("_rendering_preview", False):
            st.session_state._rendering_preview = True
            try:
                subprocess.run([
                    FFMPEG_PATH, "-y",
                    "-ss", str(sv), "-i", res.video_path,
                    "-t", str(min(clip_dur, 30)),
                    "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
                    "-c:a", "aac", "-b:a", "64k", "-ac", "1",
                    preview_path
                ], capture_output=True, text=True, timeout=30)
                preview_ready = Path(preview_path).exists()
            except:
                pass
            st.session_state._rendering_preview = False

        col_vid1, col_vid2 = st.columns([2, 1])
        with col_vid1:
            if preview_ready:
                # ── Real-time preview seperti CapCut ─────────────────
                # Video container + CSS filter (INSTAN, tanpa ffmpeg)
                st.markdown(
                    '<style>'
                    'video[data-testid="stVideo"] { aspect-ratio: 9/16 !important; max-width: 360px !important; object-fit: cover; }'
                    '[data-testid="stVideo"] { max-width: 360px !important; margin: 0 auto; }'
                    
                    
                    '</style>',
                    unsafe_allow_html=True
                )
                st.video(preview_path)
                # Text overlay preview (real-time, langsung kelihatan)
                # Muncul di bawah video, distyling seperti overlay gelap
                _ov = st.session_state.get("editor_text_overlay", "")
                if _ov.strip():
                    _ov_escaped = _ov.strip().replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    _ov_html = _ov_escaped.replace(chr(10), '<br>')
                    st.markdown(
                        f'<div style="background:rgba(0,0,0,0.7);color:white;padding:12px 16px;'
                        f'margin-top:4px;font-size:16px;font-weight:700;text-align:center;'
                        f'border-radius:12px;'
                        f'border-left:3px solid var(--signal,#f68d1f)">{_ov_html}</div>',
                        unsafe_allow_html=True
                    )
            else:
                st.markdown(
                    '<div style="text-align:center;font-size:10px;color:var(--muted-indigo);font-weight:700;margin:20px 0">'
                    '\u23f3 Menyiapkan preview 9:16...'
                    '</div>',
                    unsafe_allow_html=True
                )
                st.video(res.video_path)

        with col_vid2:
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:var(--sp-md)">
              <p style="font-size:10px;font-weight:700;color:var(--ink-soft);text-transform:uppercase;letter-spacing:0.3px;margin:0 0 6px">\u2139 Info</p>
              <p style="font-size:11px;color:#fff;margin:2px 0"><strong>Mulai:</strong> {_fmt_time(sv)}</p>
              <p style="font-size:11px;color:#fff;margin:2px 0"><strong>Selesai:</strong> {_fmt_time(ev)}</p>
              <p style="font-size:11px;color:#fff;margin:2px 0"><strong>Durasi:</strong> {clip_dur:.0f}s</p>
              <p style="font-size:11px;color:#fff;margin:2px 0"><strong>Kategori:</strong> {mom.category}</p>
              <hr style="margin:8px 0;border:none;border-top:1px dotted var(--muted-indigo)">
              <p style="font-size:9px;color:var(--muted-indigo);margin:0;line-height:1.3">
                \u26a0 Preview ini hanya klip mentah. Efek, subtitle, transisi, teks overlay, dll akan terlihat <strong>setelah Render</strong>.
              </p>
            </div>
            """, unsafe_allow_html=True)
    tabs = st.tabs(["Visual & Effects", "Transitions & Speed", "CapCut Pro", "Text Overlay", "Subtitles", "Audio", "Title & Upload"])
    with tabs[0]:
        col1, col2, col3 = st.columns(3)
        asp = col1.selectbox("Aspect Ratio", list(ASPECT_PRESETS.keys()), index=0)
        cf = col2.selectbox("Color Preset", ["none","warm","cool","vibrant","vintage","neon"], index=0)
        cnt = st.slider("Contrast", 0.5, 2.0, 1.0, 0.1)
        brg = st.slider("Brightness", -0.5, 0.5, 0.0, 0.05)
        sat = st.slider("Saturation", 0.0, 3.0, 1.0, 0.1)
        st.markdown('<p style="font-size:11px;font-weight:700;margin:var(--sp-md) 0 var(--sp-xs) 0;text-transform:uppercase;letter-spacing:0.3px;color:var(--ink-soft)">Effects</p>', unsafe_allow_html=True)
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
        st.markdown('<p style="font-size:11px;font-weight:700;margin:var(--sp-sm) 0 var(--sp-xs);text-transform:uppercase;letter-spacing:0.3px;color:var(--ink-soft)">Transition (opening)</p>', unsafe_allow_html=True)
        trans_keys = list(TRANSITIONS.keys())
        trans = st.selectbox("Transition", trans_keys, index=0, label_visibility="collapsed")
        st.markdown('<p style="font-size:11px;font-weight:700;margin:var(--sp-sm) 0 var(--sp-xs);text-transform:uppercase;letter-spacing:0.3px;color:var(--ink-soft)">Fade</p>', unsafe_allow_html=True)
        fi_c, fo_c = st.columns(2)
        fi = fi_c.slider("Fade In", 0.0, 2.0, 0.5, 0.1)
        fo = fo_c.slider("Fade Out", 0.0, 2.0, 0.8, 0.1)
    with tabs[2]:
        st.markdown('<p style="font-size:11px;font-weight:700;margin-bottom:var(--sp-sm);text-transform:uppercase;letter-spacing:0.3px;color:var(--ink-soft)">Reverse Clip</p>', unsafe_allow_html=True)
        rev = st.checkbox("Putar Mundur (Reverse Video)", value=False, help="Video akan diputar dari akhir ke awal seperti efek mundur di CapCut")
    with tabs[3]:
        st.markdown('<p style="font-size:11px;font-weight:700;margin-bottom:var(--sp-sm);text-transform:uppercase;letter-spacing:0.3px;color:var(--ink-soft)">Text Overlay</p>', unsafe_allow_html=True)
        text_overlay = st.text_area("Teks Overlay", "", height=80, placeholder="Teks yang akan ditampilkan di tengah video...", label_visibility="collapsed", help="Teks akan muncul di tengah video dengan efek animasi", key="editor_text_overlay")
        st.markdown('<hr class="dotted-divider">', unsafe_allow_html=True)
        st.markdown('<p style="font-size:11px;font-weight:700;margin-bottom:var(--sp-sm);text-transform:uppercase;letter-spacing:0.3px;color:var(--ink-soft)">Chroma Key / Green Screen</p>', unsafe_allow_html=True)
        ck_enable = st.checkbox("Aktifkan Chroma Key", value=False, help="Hilangkan background hijau/biru seperti di CapCut")
        ck_color = ""
        ck_sim = 0.4
        ck_blend = 0.1
        if ck_enable:
            from core.editor import CHROMA_KEY_COLORS
            ck_col_name = st.selectbox("Warna Background", list(CHROMA_KEY_COLORS.keys()), index=0)
            ck_color = CHROMA_KEY_COLORS.get(ck_col_name, "")
            c1, c2 = st.columns(2)
            ck_sim = c1.slider("Similarity", 0.0, 1.0, 0.4, 0.05, help="Seberapa mirip warna untuk dihapus")
            ck_blend = c2.slider("Blend", 0.0, 1.0, 0.1, 0.05, help="Haluskan tepi chroma key")
        st.markdown('<hr class="dotted-divider">', unsafe_allow_html=True)
        st.markdown('<p style="font-size:11px;font-weight:700;margin-bottom:var(--sp-sm);text-transform:uppercase;letter-spacing:0.3px;color:var(--ink-soft)">Ken Burns Effect (Pan & Zoom)</p>', unsafe_allow_html=True)
        ken = st.checkbox("Aktifkan Ken Burns", value=False, help="Efek zoom in/out perlahan seperti di CapCut")
        ken_start = 1.0
        ken_end = 1.3
        if ken:
            c1, c2 = st.columns(2)
            ken_start = c1.slider("Zoom Awal", 1.0, 2.0, 1.0, 0.05)
            ken_end = c2.slider("Zoom Akhir", 1.0, 2.5, 1.3, 0.05)
        st.markdown('<hr class="dotted-divider">', unsafe_allow_html=True)
        st.markdown('<p style="font-size:11px;font-weight:700;margin-bottom:var(--sp-sm);text-transform:uppercase;letter-spacing:0.3px;color:var(--ink-soft)">Blur Background</p>', unsafe_allow_html=True)
        blur = st.selectbox("Tipe Blur", ["none","light","medium","heavy","gaussian","pixelate"], index=0, help="Blur background seperti di CapCut")
        st.markdown('<hr class="dotted-divider">', unsafe_allow_html=True)
        st.markdown('<p style="font-size:11px;font-weight:700;margin-bottom:var(--sp-sm);text-transform:uppercase;letter-spacing:0.3px;color:var(--ink-soft)">Stabilization</p>', unsafe_allow_html=True)
        stab = st.checkbox("Stabilize Video (Anti-Goyang)", value=False, help="Kurangi goyangan kamera seperti CapCut stabilize")
        stab_shake = 5
        if stab:
            stab_shake = st.slider("Intensitas", 1, 10, 5, help="1 = sedikit, 10 = maksimal")
    with tabs[4]:
        sb = st.checkbox("Show Subtitles", value=True)
        col1, col2 = st.columns(2)
        sc = col1.selectbox("Color", list(SUBTITLE_COLORS.keys()), index=0)
        sub_sz = col2.slider("Font Size", 10, 100, 44, 2)
        col3, col4 = st.columns(2)
        sub_fnt = col3.text_input("Font", "Montserrat")
        sub_alg_label = col4.selectbox("Align", ["Tengah (Center)", "Bawah (Bottom)"], index=0)
        sub_alg = 5 if "Tengah" in sub_alg_label else 2
        sub_upp = st.checkbox("UPPERCASE", value=True)
    with tabs[5]:
        st.markdown('<p style="font-size:11px;color:var(--ink-soft)">Background music (opsional). Letakkan file MP3 di folder project.</p>', unsafe_allow_html=True)
        music_files = [""] + sorted([f.name for f in Path(".").glob("*.mp3")] + [f.name for f in Path(".").glob("*.wav")])
        bg_music = st.selectbox("Music", music_files, index=0)
        music_vol = st.slider("Music Volume", 0.0, 1.0, 0.3, 0.05) if bg_music else 0.3
    with tabs[6]:
        text = res.transcript or ""
        model_name = st.session_state.get("ollama_model", "llama3.2:latest")
        jd = generate_title(text, res.title, res.viral_moments)
        ds = generate_description(text, jd, res.title, res.viral_moments)
        j = st.text_input("Title", jd)
        d = st.text_area("Description", ds, height=80)
        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown('<p style="font-size:11px;font-weight:700;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.3px;color:var(--ink-soft)">Post to Platforms</p>', unsafe_allow_html=True)
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
    # ── Real-time CSS filter preview (CapCut-style) ────────────
    filter_parts = []
    if cnt != 1.0:
        filter_parts.append(f"contrast({cnt})")
    if brg != 0.0:
        filter_parts.append(f"brightness({1.0 + brg})")
    if sat != 1.0:
        filter_parts.append(f"saturate({sat})")
    if sep:
        filter_parts.append("sepia(1)")
    if gry:
        filter_parts.append("grayscale(1)")
    filter_str = " ".join(filter_parts) if filter_parts else "none"
    mirror_css = "scaleX(-1)" if mr else "none"
    st.markdown(
        f'<style>'
        f'video[data-testid="stVideo"] {{ '
        f'  filter: {filter_str} !important; '
        f'  transform: {mirror_css} !important; '
        f'}}'
        f'</style>',
        unsafe_allow_html=True
    )

    col_render, col_previewfx = st.columns(2)
    if col_render.button("\U0001f3ac Render Clip", type="primary", use_container_width=True, disabled=st.session_state.rendering):
        st.session_state.rendering = True
        st.session_state.render_done = False
        st.session_state.render_progress = 0.0
        st.session_state.render_step = "\U0001f4e6 Menyiapkan render..."
        st.session_state.preview_fx_path = None
        threading.Thread(target=_do_render_thread, args=(
            sv, ev, sb, sc, fi, fo, asp, sp, mr, cf, nr, j, d,
            cnt, brg, sat,
            vig, sep, gry, shp, edg,
            sub_sz, sub_fnt, sub_alg, sub_upp,
            apst, platforms, auto_delete,
            trans, speed_ramp, text_overlay,
            glict, bg_music, music_vol,
            rev,
            ck_color, ck_sim, ck_blend,
            ken, ken_start, ken_end,
            blur,
            stab, stab_shake,
        ), daemon=True).start()

    # ── Preview Effects — render 3 detik dengan semua efek ────────
    if col_previewfx.button("\U0001f441 Preview Effects", use_container_width=True, type="secondary", disabled=st.session_state.rendering):
        st.session_state.rendering = True
        st.session_state.render_done = False
        st.session_state.render_progress = 0.0
        st.session_state.render_step = "\U0001f441 Merender preview efek..."
        threading.Thread(target=_preview_effects, args=(
            sv, ev, sb, sc, fi, fo, asp, sp, mr, cf, nr,
            cnt, brg, sat,
            vig, sep, gry, shp, edg,
            sub_sz, sub_fnt, sub_alg, sub_upp,
            trans, speed_ramp, text_overlay,
            glict, bg_music, music_vol,
            rev,
            ck_color, ck_sim, ck_blend,
            ken, ken_start, ken_end,
            blur,
            stab, stab_shake,
        ), daemon=True).start()

    # ── Render Progress ────────────────────────────────────────────
    if st.session_state.rendering:
        prog_val = st.session_state.render_progress
        step_msg = st.session_state.render_step
        st.progress(prog_val)
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:var(--sp-md)">'
            f'<p style="font-size:11px;color:#fff;font-weight:700;margin:0">{step_msg}</p>'
            f'<p style="font-size:10px;color:var(--muted-indigo);margin:4px 0 0">{prog_val*100:.0f}%</p>'
            f'</div>',
            unsafe_allow_html=True
        )
        time.sleep(1)
        st.rerun()

    # ── Render Result (inline setelah render selesai) ────────────
    if st.session_state.render_done and st.session_state.out_video:
        ov = st.session_state.out_video
        if Path(ov).exists():
            sz = Path(ov).stat().st_size / (1024*1024)
            st.markdown(
                '<div style="background:rgba(16,185,129,0.05);border:1px solid rgba(16,185,129,0.15);border-radius:12px;padding:var(--sp-md);margin-bottom:var(--sp-lg)">'
                '<p style="font-size:13px;font-weight:900;color:#fff;margin:0 0 2px">\u2714\ufe0f Render Selesai!</p>'
                f'<p style="font-size:10px;color:var(--ink-soft);margin:0">{os.path.basename(ov)} \u2022 {sz:.1f} MB</p>'
                '</div>',
                unsafe_allow_html=True
            )
            st.video(str(ov))
            r1, r2, r3 = st.columns(3)
            if r1.button("\U0001f4dd Lanjut ke Preview", type="primary", use_container_width=True):
                st.session_state.step = 5
                st.rerun()
            if r2.button("\U0001f4e4 Upload ke YouTube", use_container_width=True):
                try:
                    Uploader.upload("youtube", ov, st.session_state.get("_title", ""), st.session_state.get("_desc", ""))
                    st.toast("\u2713 Terupload!")
                except Exception as e:
                    st.error(f"Gagal: {e}")
            if r3.button("\u2795 Render Lagi", use_container_width=True):
                st.session_state.render_done = False
                st.session_state.out_video = None
                st.rerun()

    # ── Preview Effects Result (inline) ─────────────────────────
    fx_preview = st.session_state.get("preview_fx_path")
    if fx_preview and Path(fx_preview).exists() and not st.session_state.rendering:
        st.markdown(
            '<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:var(--sp-md);margin-bottom:var(--sp-sm)">'
            '<p style="font-size:11px;font-weight:700;color:#fff;margin:0">\U0001f441 Preview Efek</p>'
            '<p style="font-size:9px;color:var(--muted-indigo);margin:2px 0 0">Preview 3 detik dengan efek saat ini</p>'
            '</div>',
            unsafe_allow_html=True
        )
        st.video(str(fx_preview))

def _do_render_thread(
    stt, ett, show_sub, sub_col, fi, fo, aspect, speed_str, mirror, color_f, noise_r, title, desc,
    contrast=1.0, brightness=0.0, saturation=1.0,
    vignette=False, sepia=False, grayscale=False, sharpen=False, edge_detect=False,
    sub_size=44, sub_font="Montserrat", sub_align=5, sub_upper=True,
    auto_post=False, platforms=None, auto_delete=True,
    transition="none", speed_ramp="none", text_overlay="",
    glitch=False, bg_music="", music_volume=0.3,
    reverse=False,
    chroma_key="", chroma_similarity=0.4, chroma_blend=0.1,
    ken_burns=False, ken_zoom_start=1.0, ken_zoom_end=1.3,
    blur_bg="none",
    stabilize=False, stabilize_shakiness=5
):
    """Render clip — dijalankan di background thread. Update session state untuk progress."""
    res = st.session_state.get("result")
    if not res:
        st.session_state.rendering = False
        st.session_state.render_step = "\u2716 Error: tidak ada result video"
        return
    wd = st.session_state.wd
    cid = uuid.uuid4().hex[:8]
    out = os.path.join(wd, f"out_{cid}.mp4")
    sub_path = os.path.join(wd, f"subs_{cid}.ass")
    src = st.session_state.get("src", "url")
    speed = {"1.0x":1.0,"1.05x":1.05,"1.07x":1.07,"1.1x":1.1,"1.15x":1.15}.get(speed_str, 1.0)
    try:
        st.session_state.render_progress = 0.05
        st.session_state.render_step = "\U0001f4e6 Menyiapkan klip video..."
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

        st.session_state.render_progress = 0.25
        st.session_state.render_step = "\U0001f4dd Membuat subtitle..."
        if show_sub and res.word_timestamps:
            rel = [wt for wt in res.word_timestamps if wt.start<ett and wt.end>stt]
            if rel:
                shifted = [WordTimestamp(w.word, max(0,w.start-stt), w.end-stt) for w in rel]
                SubtitleGenerator.generate_ass(shifted, sub_path, SUBTITLE_COLORS.get(sub_col,"&H00FFFF&"), font=sub_font, size=sub_size, alignment=sub_align, uppercase=sub_upper)

        st.session_state.render_progress = 0.5
        st.session_state.render_step = f"\U0001f3ac Merender video... {speed}x {color_f}"
        ok, err = VideoProcessor.process_clip(
            clip_path, out,
            sub_path if Path(sub_path).exists() else "", "",
            0, ett-stt, fi, fo, speed, mirror, color_f, noise_r, aspect=aspect,
            contrast=contrast, brightness=brightness, saturation=saturation,
            vignette=vignette, sepia=sepia, grayscale=grayscale, sharpen=sharpen, edge_detect=edge_detect,
            transition=transition, text_overlay=text_overlay,
            speed_ramp=speed_ramp, glitch=glitch, bg_music=bg_music, music_volume=music_volume,
            reverse=reverse,
            chroma_key=chroma_key, chroma_similarity=chroma_similarity, chroma_blend=chroma_blend,
            ken_burns=ken_burns, ken_zoom_start=ken_zoom_start, ken_zoom_end=ken_zoom_end,
            blur_bg=blur_bg,
            stabilize=stabilize, stabilize_shakiness=stabilize_shakiness
        )
        if not ok:
            raise Exception(err)

        st.session_state.render_progress = 0.9
        st.session_state.render_step = "\U0001f4be Menyimpan hasil..."
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)[:30]
        ts = time.strftime("%Y%m%d_%H%M%S")
        final_name = f"{ts}_{safe_title}.mp4"
        final_path = os.path.join(OUTPUT_DIR, final_name)
        shutil.copy2(out, final_path)
        st.session_state.out_video = final_path
        st.session_state._title = title
        st.session_state._desc = desc

        st.session_state.render_progress = 1.0
        st.session_state.render_step = "\u2714\ufe0f Render selesai!"

        user = st.session_state.get("user", {})
        clip_id = db.clip_save(
            final_path, title=title, description=desc,
            source_url=st.session_state.get("vurl", ""),
            duration=ett-stt, platforms=platforms or [],
            user_id=user.get("id", "")
        )
        st.session_state._clip_id = clip_id

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
                    if auto_delete:
                        db.clips_cleanup_uploaded()
                threading.Thread(target=bg_upload, daemon=True).start()

    except Exception as e:
        st.session_state.render_step = f"\u2716 Error: {e}"
        st.session_state.render_progress = 0.0
    finally:
        st.session_state.rendering = False
        st.session_state.render_done = True

def _preview_effects(
    stt, ett, show_sub, sub_col, fi, fo, aspect, speed_str, mirror, color_f, noise_r,
    contrast=1.0, brightness=0.0, saturation=1.0,
    vignette=False, sepia=False, grayscale=False, sharpen=False, edge_detect=False,
    sub_size=44, sub_font="Montserrat", sub_align=5, sub_upper=True,
    transition="none", speed_ramp="none", text_overlay="",
    glitch=False, bg_music="", music_volume=0.3,
    reverse=False,
    chroma_key="", chroma_similarity=0.4, chroma_blend=0.1,
    ken_burns=False, ken_zoom_start=1.0, ken_zoom_end=1.3,
    blur_bg="none",
    stabilize=False, stabilize_shakiness=5
):
    """Render preview 3 detik dengan efek — biar user bisa lihat hasil edit sebelum render penuh."""
    res = st.session_state.get("result")
    if not res or not res.video_path or not Path(res.video_path).exists():
        st.session_state.render_step = "\u2716 Error: video source tidak ditemukan"
        st.session_state.rendering = False
        return
    wd = st.session_state.wd
    preview_fx = os.path.join(wd, "preview_fx.mp4")
    sub_path = os.path.join(wd, "preview_fx_subs.ass")
    speed = {"1.0x":1.0,"1.05x":1.05,"1.07x":1.07,"1.1x":1.1,"1.15x":1.15}.get(speed_str, 1.0)
    clip_dur = min(4, ett - stt)  # Cuma 4 detik preview
    try:
        st.session_state.render_step = "\u23f3 Merender preview efek..."
        st.session_state.render_progress = 0.3
        if show_sub and res.word_timestamps:
            rel = [wt for wt in res.word_timestamps if wt.start<ett and wt.end>stt]
            if rel:
                shifted = [WordTimestamp(w.word, max(0,w.start-stt), w.end-stt) for w in rel]
                SubtitleGenerator.generate_ass(shifted, sub_path, SUBTITLE_COLORS.get(sub_col,"&H00FFFF&"), font=sub_font, size=sub_size, alignment=sub_align, uppercase=sub_upper)
        st.session_state.render_progress = 0.6
        ok, err = VideoProcessor.process_clip(
            res.video_path, preview_fx,
            sub_path if Path(sub_path).exists() else "", "",
            stt, stt+clip_dur, min(fi, 0.3), min(fo, 0.3), speed, mirror, color_f, noise_r, aspect=aspect,
            contrast=contrast, brightness=brightness, saturation=saturation,
            vignette=vignette, sepia=sepia, grayscale=grayscale, sharpen=sharpen, edge_detect=edge_detect,
            transition=transition, text_overlay=text_overlay,
            speed_ramp=speed_ramp, glitch=glitch, bg_music=bg_music, music_volume=music_volume,
            reverse=reverse,
            chroma_key=chroma_key, chroma_similarity=chroma_similarity, chroma_blend=chroma_blend,
            ken_burns=ken_burns, ken_zoom_start=ken_zoom_start, ken_zoom_end=ken_zoom_end,
            blur_bg=blur_bg,
            stabilize=stabilize, stabilize_shakiness=stabilize_shakiness
        )
        if ok:
            st.session_state.preview_fx_path = preview_fx
            st.session_state.render_step = "\u2714\ufe0f Preview efek siap!"
        else:
            st.session_state.render_step = f"\u26a0 Gagal render preview: {err[:80]}"
        st.session_state.render_progress = 1.0
    except Exception as e:
        st.session_state.render_step = f"\u2716 Error preview: {e}"
    finally:
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
    st.markdown('<p style="font-size:11px;font-weight:700;margin-bottom:var(--sp-sm);text-transform:uppercase;letter-spacing:0.3px;color:var(--ink-soft)">Upload to</p>', unsafe_allow_html=True)
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
        st.markdown(f'<div style="text-align:center;padding:40px;color:var(--muted-indigo)">\U0001f3ac<p style="font-size:12px;margin-top:8px">No clips yet. Create one from New Clip.</p></div>', unsafe_allow_html=True)
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
              <div style="font-weight:700;font-size:12px;color:#fff;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{v.name}</div>
              <div style="font-size:10px;color:var(--ink-soft);margin:2px 0">{sz:.1f} MB · {mtime}</div>
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
        st.markdown(f'<p style="text-align:center;font-size:10px;color:var(--ink-soft);margin:var(--sp-md) 0">Page {page} of {total_pages} ({total} total)</p>', unsafe_allow_html=True)
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
        st.markdown(f'<div style="text-align:center;padding:40px;color:var(--muted-indigo)">\U0001f4cb<p style="font-size:12px;margin-top:8px">No items in queue. Add from the Farm tab.</p></div>', unsafe_allow_html=True)
        return
    for item in q:
        status_badge = "badge-green" if item['status'] == 'pending' else "badge-gray" if item['status'] == 'done' else "badge-red"
        st.markdown(f"""
        <div class="queue-card">
          <div style="display:flex;justify-content:space-between;align-items:start">
            <div style="flex:1;min-width:0">
              <div style="font-size:12px;font-weight:700;color:#fff;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{item['url'][:60]}</div>
              <div style="font-size:10px;color:var(--ink-soft);margin:4px 0">
                <span class="badge {status_badge}">{item['status']}</span>
                {' '.join(item.get('platforms',['youtube']))} · {item.get('schedule_at','unscheduled')}
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
                Queue.delete(item['id'])
                st.rerun()
    edit_id = st.session_state.get("edit_queue_id")
    if edit_id:
        from core.scheduler import _read_json, _write_json, QUEUE_FILE
        qq = _read_json(QUEUE_FILE)
        target = next((i for i in qq if i['id'] == edit_id), None)
        if target:
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown(f'<h3 style="font-size:16px;font-weight:900;color:#fff">Edit Queue Item</h3>', unsafe_allow_html=True)
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
            <div style="font-weight:700;font-size:13px;color:#fff"><span style="color:{clr}">{dot}</span> {plat.title()}</div>
            <div style="font-size:10px;color:var(--ink-soft)">{'Connected' if sts=='connected' else 'Disconnected'} · {msg}</div>
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
            <div style="font-weight:700;font-size:13px;color:#fff">{name}</div>
            <div style="font-size:10px;color:var(--ink-soft)">{', '.join(data.get('times',[]))}</div>
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
    st.markdown('<h1 class="page-header">Stats</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Daily upload statistics</p>', unsafe_allow_html=True)
    count = db.stats_today_count()
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
        st.markdown('<div class="sidebar-model"><label>Ollama Model</label></div>', unsafe_allow_html=True)
        models = ["llama3.2:latest", "qwen2.5-coder:1.5b", "Custom"]
        sel_model = st.selectbox("Model", models, index=0, key="ollama_model_select", label_visibility="collapsed")
        if sel_model == "Custom":
            custom_model = st.text_input("Nama Model Custom", value="llama3.2:latest", key="custom_ollama_model", label_visibility="collapsed")
            st.session_state.ollama_model = custom_model
        else:
            st.session_state.ollama_model = sel_model

        st.markdown('<div class="sidebar-model" style="margin-top:var(--sp-md)"><label>Auto Cookies Browser</label></div>', unsafe_allow_html=True)
        browsers = ["None", "chrome", "edge", "firefox", "brave", "opera", "vivaldi"]
        st.selectbox("Cookies dari Browser", browsers, index=0, key="local_browser_cookies", label_visibility="collapsed", help="Ambil cookies langsung dari browser lokal Anda secara gratis agar terhindar dari pemblokiran YouTube/TikTok.")

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

        # ── Proxy Configuration ───────────────────────────────────
        st.markdown('<div class="sidebar-model" style="margin-top:var(--sp-lg)"><label>Proxy Settings</label></div>', unsafe_allow_html=True)
        with st.expander("\U0001f310 Proxy Rotating", expanded=False):
            current_proxies = ProxyRotator.get_list() or _load_proxies()
            if current_proxies:
                ProxyRotator.set_proxies(current_proxies)

            proxy_text = st.text_area(
                "Daftar Proxy (1 per baris)",
                value="\n".join(current_proxies),
                height=80,
                placeholder="http://user:pass@host:port\nsocks5://host:1080\nhttp://host:8080",
                label_visibility="collapsed",
                help="Format: protocol://user:pass@host:port\nContoh: socks5://user:pass@1.2.3.4:1080"
            )

            col_save, col_refresh = st.columns(2)
            if col_save.button("\U0001f4be Simpan", use_container_width=True):
                proxies = [p.strip() for p in proxy_text.split("\n") if p.strip()]
                ProxyRotator.set_proxies(proxies)
                st.success(f"{len(proxies)} proxy disimpan!")
                time.sleep(0.5)
                st.rerun()

            # Tombol Refresh — ambil proxy gratis dari internet
            if col_refresh.button("\U0001f504 Refresh", use_container_width=True, type="secondary"):
                with st.spinner("Mengambil proxy gratis dari 5 sumber..."):
                    results = ProxyRotator.fetch_free_proxies(max_per_source=80)
                if results:
                    st.success(f"Dapat {len(results)} proxy gratis!")
                else:
                    st.error("Tidak ada proxy gratis yang hidup. Coba lagi nanti.")
                time.sleep(1)
                st.rerun()

            status = ProxyRotator.status()
            if status["total"] > 0:
                col_rotate, _ = st.columns(2)
                st.markdown(
                    f'<div style="font-size:10px;color:var(--on-carbon);margin-top:4px">'
                    f'<strong>Status:</strong> {status["total"]} proxy '
                    f'| <strong>Aktif:</strong> #{status["current_index"]+1} '
                    f'| <strong>Gagal:</strong> {status["failed"]}'
                    f'</div>',
                    unsafe_allow_html=True
                )
                if status["current"]:
                    cur = status["current"]
                    st.markdown(
                        f'<div style="font-size:9px;color:var(--muted-indigo);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
                        f'{cur[:50]}...'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                if col_rotate.button("\U0001f500 Ganti Manual", use_container_width=True):
                    old = ProxyRotator.get_current()
                    ProxyRotator.rotate()
                    new = ProxyRotator.get_current()
                    st.info(f"Ganti: {old[:30] if old else 'none'} \u2192 {new[:30] if new else 'none'}")
                    time.sleep(0.5)
                    st.rerun()
            else:
                st.markdown(
                    '<div style="font-size:10px;color:var(--muted-indigo);margin-top:4px">'
                    'Belum ada proxy. Klik <strong>Refresh</strong> untuk ambil proxy gratis dari internet, '
                    'atau masukkan proxy manual di atas.'
                    '</div>',
                    unsafe_allow_html=True
                )
                if st.button("\U0001f504 Ambil Proxy Gratis", use_container_width=True, type="primary"):
                    with st.spinner("Mengambil proxy gratis dari 5 sumber..."):
                        results = ProxyRotator.fetch_free_proxies(max_per_source=80)
                    if results:
                        st.success(f"Dapat {len(results)} proxy gratis!")
                    else:
                        st.error("Tidak ada proxy gratis yang hidup. Coba lagi nanti.")
                    time.sleep(1)
                    st.rerun()
        user = st.session_state.get("user", {})
        st.markdown(f"""
        <div class="sidebar-user-badge">
          <div class="sidebar-user-avatar">{user.get('name','?')[0].upper()}</div>
          <div class="sidebar-user-name">{user.get('name','Guest')}</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Logout", key="logout_btn", use_container_width=True):
            st.session_state.user = None
            st.session_state.login_mode = "login"
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

    # ── Hamburger Menu Icon + Sidebar Toggle ─────────────────────
    st.markdown('<div class="hamburger-wrap">', unsafe_allow_html=True)
    if st.button("☰", key="hamburger_btn", help="Buka/Tutup menu navigasi"):
        st.session_state.sidebar_open = not st.session_state.get("sidebar_open", False)
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    page_map.get(current_page, page_dashboard_router)()
    st.markdown('</div>', unsafe_allow_html=True)

    # Sidebar toggle — semua ukuran layar
    sidebar_closed = not st.session_state.get("sidebar_open", False)
    st.markdown(f"""
    <style>
    @media (min-width: 721px) {{
      [data-testid="stSidebar"] {{
        transition: margin-left 0.3s ease, opacity 0.3s ease !important;
        {'margin-left: 0 !important; opacity: 1;' if not sidebar_closed else 'margin-left: calc(-1 * var(--sidebar-width)) !important; opacity: 0; pointer-events: none;'}
      }}
    }}
    @media (max-width: 720px) {{
      [data-testid="stSidebar"] {{
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        height: 100vh !important;
        z-index: 99995 !important;
        min-width: var(--sidebar-width) !important;
        max-width: var(--sidebar-width) !important;
        transition: left 0.3s ease, opacity 0.3s ease !important;
        {'left: 0 !important; opacity: 1; pointer-events: all;' if not sidebar_closed else 'left: calc(-1 * var(--sidebar-width)) !important; opacity: 0; pointer-events: none;'}
      }}
    }}
    </style>
    """, unsafe_allow_html=True)

    # Auto close sidebar setelah navigasi (deteksi page change)
    if "_last_page" not in st.session_state:
        st.session_state._last_page = current_page
    if st.session_state._last_page != current_page:
        st.session_state._last_page = current_page
        st.session_state.sidebar_open = False

if __name__ == "__main__":
    main()
