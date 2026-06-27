"""
VideoClipse — AI Video Farming Studio
Nintendo.com 2001 Design · 1 server = UI + Scheduler + Auto Upload
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
/* ══════════════════════════════════════════════════════════
   NINTENDO.COM (2001) — DESIGN SYSTEM
   Beveled periwinkle chrome · Carbon command layer ·
   Rationed warm wayfinding · Chamfered corners · Arial/Helvetica only
   ══════════════════════════════════════════════════════════ */

:root {
  /* ── Brand & Accent ────────────────────────────── */
  --nintendo-red:      #e60012;
  --signal:            #f68d1f;
  --amber:             #ecab37;
  --nav-gold:          #e48600;

  /* ── Surface / Chrome ──────────────────────────── */
  --canvas:            #7a8aba;
  --periwinkle:        #8ba1d4;
  --sky:               #9fbee7;
  --lavender:          #acace7;
  --ice:               #c0d5e6;
  --chrome-indigo:     #3d4f97;
  --muted-indigo:      #60619c;
  --platinum:          #dedede;
  --surface:           #ffffff;
  --carbon:            #21242e;
  --carbon-soft:       #2a2e3a;

  /* ── Text ──────────────────────────────────────── */
  --ink:               #21242e;
  --ink-soft:          #3d4f97;
  --on-primary:        #ffffff;
  --on-carbon:         #c0d5e6;

  /* ── Semantic ──────────────────────────────────── */
  --error:             #e60012;
  --systems-teal:      #206479;
  --games-red:         #a7282b;

  /* ── Spacing ───────────────────────────────────── */
  --sp-xxs: 2px;  --sp-xs: 4px;  --sp-sm: 8px;
  --sp-md: 12px;  --sp-lg: 16px; --sp-xl: 24px; --sp-xxl: 32px;

  /* ── Radii ─────────────────────────────────────── */
  --r-none: 0px;    --r-xs: 2px;  --r-sm: 4px;
  --r-md: 6px;      --r-lg: 10px; --r-full: 9999px;

  --sidebar-width: 220px;
  --content-max: 800px;

  /* ── Chamfer cut size ──────────────────────────── */
  --chamfer: 4px;

  /* ── Sidebar toggle state ────────────────────── */
  --sidebar-left: 0px;
}

/* ── Chamfered corner mixin ─────────────────────────────── */
.chamfer {
  clip-path: polygon(var(--chamfer) 0, 100% 0, 100% calc(100% - var(--chamfer)), calc(100% - var(--chamfer)) 100%, 0 100%, 0 var(--chamfer));
}

/* ── Base Reset ─────────────────────────────────────────── */
* { box-sizing: border-box; }
html, body, [data-testid="stApp"], .stApp {
  background: var(--canvas) !important;
  font-family: Arial, Helvetica, sans-serif !important;
  color: var(--ink) !important;
}

/* ══════════════════════════════════════════════════════════
   SIDEBAR — Carbon Navy Command Slab with Halftone
   ══════════════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
  background: var(--carbon) !important;
  border: none !important;
  padding: 0 !important;
  min-width: var(--sidebar-width) !important;
  max-width: var(--sidebar-width) !important;
  position: relative;
  background-image:
    radial-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
    linear-gradient(var(--carbon), var(--carbon)) !important;
  background-size: 4px 4px, 100% 100% !important;
}

[data-testid="stSidebar"] > div:first-child {
  background: transparent !important;
  padding: var(--sp-xl) var(--sp-lg) !important;
  height: 100vh;
  overflow-y: auto;
  overflow-x: hidden;
}

[data-testid="stSidebar"] > div:first-child::-webkit-scrollbar { width: 0; }

/* Logo — Nintendo racetrack-pill style */
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
  padding: 0 var(--sp-sm) var(--sp-xl) var(--sp-sm);
  border-bottom: 1px solid rgba(255,255,255,0.08);
  margin-bottom: var(--sp-lg);
}
.sidebar-logo-icon {
  width: 34px; height: 34px;
  background: var(--nintendo-red);
  border-radius: var(--r-full);
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; flex-shrink: 0;
  border: 2px solid var(--surface);
  box-shadow: inset 0 -2px 0 rgba(0,0,0,0.2), 0 0 0 1px var(--chrome-indigo);
}
.sidebar-logo-text {
  font-weight: 700; font-size: 16px;
  letter-spacing: 0.5px;
  color: var(--surface);
  line-height: 1.2;
  text-transform: uppercase;
}
.sidebar-logo-sub {
  font-size: 9px; color: var(--on-carbon);
  letter-spacing: 1px; text-transform: uppercase;
}

/* Sidebar nav buttons — Nav Gold on carbon */
[data-testid="stSidebar"] .stButton > button {
  justify-content: flex-start !important;
  font-size: 13px !important;
  font-family: Arial, Helvetica, sans-serif !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.5px !important;
  padding: 10px 14px !important;
  margin-bottom: 2px !important;
  clip-path: polygon(3px 0, 100% 0, 100% calc(100% - 3px), calc(100% - 3px) 100%, 0 100%, 0 3px) !important;
  background: transparent !important;
  border: none !important;
  color: var(--on-carbon) !important;
  box-shadow: none !important;
  transition: all 0.15s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: rgba(255,255,255,0.06) !important;
  color: var(--surface) !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background: rgba(228,134,0,0.15) !important;
  color: var(--nav-gold) !important;
  box-shadow: inset 2px 0 0 var(--nav-gold) !important;
}

/* Sidebar accounts */
.sidebar-accounts {
  margin-top: auto;
  padding-top: var(--sp-lg);
  border-top: 1px solid rgba(255,255,255,0.08);
}
.sidebar-account-row {
  display: flex; align-items: center; gap: var(--sp-sm);
  padding: 6px 8px; font-size: 11px;
  font-family: Arial, Helvetica, sans-serif;
  color: var(--on-carbon);
  letter-spacing: 0.3px;
}
.sidebar-account-dot {
  width: 8px; height: 8px; border-radius: var(--r-full);
  flex-shrink: 0;
  box-shadow: inset 0 -1px 0 rgba(0,0,0,0.3);
}
.sidebar-footer {
  margin-top: var(--sp-lg); padding: var(--sp-md) var(--sp-sm) 0;
  border-top: 1px solid rgba(255,255,255,0.08);
  font-size: 9px; color: var(--on-carbon);
  line-height: 1.5;
  font-family: Arial, Helvetica, sans-serif;
  letter-spacing: 0.3px;
}

/* Sidebar model select */
.sidebar-model { margin: var(--sp-md) 0 var(--sp-sm) var(--sp-sm); }
.sidebar-model label {
  font-size: 10px; font-weight: 700;
  color: var(--on-carbon);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: block; margin-bottom: 4px;
}
.sidebar-model select {
  font-size: 12px; padding: 4px 8px;
  background: var(--carbon-soft);
  color: var(--surface);
  border: 1px solid rgba(255,255,255,0.1);
  clip-path: polygon(3px 0, 100% 0, 100% calc(100% - 3px), calc(100% - 3px) 100%, 0 100%, 0 3px);
  width: 100%;
  font-family: Arial, Helvetica, sans-serif;
}

/* User badge in sidebar */
.sidebar-user-badge {
  display: flex; align-items: center; gap: var(--sp-sm);
  padding: var(--sp-md) var(--sp-sm);
  border-top: 1px solid rgba(255,255,255,0.08);
}
.sidebar-user-avatar {
  width: 26px; height: 26px; border-radius: var(--r-full);
  background: rgba(228,134,0,0.2);
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; color: var(--nav-gold);
  font-weight: 700; flex-shrink: 0;
  border: 1px solid rgba(228,134,0,0.3);
}
.sidebar-user-name {
  font-size: 11px; color: var(--surface);
  font-weight: 600;
  letter-spacing: 0.3px;
}

/* ══════════════════════════════════════════════════════════
   MAIN CONTENT — Periwinkle Chrome Canvas
   ══════════════════════════════════════════════════════════ */
.main-container {
  max-width: var(--content-max);
  margin: 0 auto;
  padding: var(--sp-xxl) var(--sp-xl);
  position: relative;
}

.page-header {
  font-size: 28px;
  font-weight: 900;
  letter-spacing: -0.3px;
  color: var(--carbon);
  margin: 0 0 2px 0;
  line-height: 1.1;
  font-family: Arial, Helvetica, sans-serif;
  -webkit-text-stroke: 1px var(--surface);
  text-shadow: 2px 2px 0 rgba(0,0,0,0.15);
}
.page-sub {
  font-size: 12px;
  color: var(--ink-soft);
  margin: 0 0 var(--sp-xl) 0;
  line-height: 1.4;
  font-family: Arial, Helvetica, sans-serif;
}

/* ══════════════════════════════════════════════════════════
   DASHBOARD GRID — Chamfered Beveled Stat Cards
   ══════════════════════════════════════════════════════════ */
.dash-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--sp-md);
  margin-bottom: var(--sp-xl);
}
.dash-card {
  background: var(--periwinkle);
  clip-path: polygon(var(--chamfer) 0, 100% 0, 100% calc(100% - var(--chamfer)), calc(100% - var(--chamfer)) 100%, 0 100%, 0 var(--chamfer));
  padding: var(--sp-lg);
  text-align: center;
  position: relative;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.3),
    inset 0 -1px 0 var(--chrome-indigo),
    0 1px 2px rgba(0,0,0,0.1);
  transition: all 0.15s;
}
.dash-card:hover {
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.4),
    inset 0 -2px 0 var(--chrome-indigo),
    0 2px 6px rgba(0,0,0,0.15);
}
.dash-num {
  font-size: 32px; font-weight: 900;
  color: var(--carbon);
  margin: 0; line-height: 1;
  font-family: Arial, Helvetica, sans-serif;
}
.dash-num-dark { color: var(--carbon); }
.dash-label {
  font-size: 10px; color: var(--ink-soft);
  margin: 6px 0 0 0;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-family: Arial, Helvetica, sans-serif;
}
.dash-icon {
  font-size: 22px; margin-bottom: var(--sp-sm);
}

/* Quick actions */
.quick-actions-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--sp-md);
  margin-bottom: var(--sp-lg);
}

/* ══════════════════════════════════════════════════════════
   BUTTONS — Chamfered Signal Orange & Chrome
   ══════════════════════════════════════════════════════════ */
.stButton > button {
  font-family: Arial, Helvetica, sans-serif !important;
  font-weight: 700 !important;
  font-size: 11px !important;
  text-transform: uppercase !important;
  letter-spacing: 0.5px !important;
  padding: 8px 16px !important;
  border: none !important;
  transition: all 0.15s !important;
  cursor: pointer !important;
  line-height: 1.4 !important;
  clip-path: polygon(3px 0, 100% 0, 100% calc(100% - 3px), calc(100% - 3px) 100%, 0 100%, 0 3px) !important;
}
.stButton > button[kind="primary"] {
  background: var(--signal) !important;
  color: var(--surface) !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.3),
    inset 0 -1px 0 rgba(0,0,0,0.2),
    0 1px 2px rgba(0,0,0,0.1) !important;
}
.stButton > button[kind="primary"]:hover {
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.4),
    inset 0 -1px 0 rgba(0,0,0,0.3),
    0 2px 6px rgba(0,0,0,0.2) !important;
}
.stButton > button[kind="primary"]:active {
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.2) !important;
}
.stButton > button[kind="secondary"] {
  background: var(--surface) !important;
  color: var(--ink) !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.5),
    inset 0 -1px 0 var(--chrome-indigo),
    0 1px 2px rgba(0,0,0,0.08) !important;
  border: 1px solid var(--chrome-indigo) !important;
}
.stButton > button[kind="secondary"]:hover {
  border-color: var(--signal) !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.5),
    inset 0 -1px 0 var(--chrome-indigo),
    0 2px 6px rgba(0,0,0,0.12) !important;
}

/* ══════════════════════════════════════════════════════════
   CARDS — Chamfered Beveled Periwinkle Plates
   ══════════════════════════════════════════════════════════ */
.card, .queue-card, .moment-card {
  background: var(--periwinkle);
  clip-path: polygon(var(--chamfer) 0, 100% 0, 100% calc(100% - var(--chamfer)), calc(100% - var(--chamfer)) 100%, 0 100%, 0 var(--chamfer));
  padding: var(--sp-lg);
  margin-bottom: var(--sp-md);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.3),
    inset 0 -1px 0 var(--chrome-indigo),
    0 1px 2px rgba(0,0,0,0.06);
  transition: all 0.15s;
}
.card:hover, .queue-card:hover, .moment-card:hover {
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.4),
    inset 0 -2px 0 var(--chrome-indigo),
    0 2px 6px rgba(0,0,0,0.1);
}
.card-flat { box-shadow: none !important; }

/* ══════════════════════════════════════════════════════════
   STEP BAR — Chamfered Workflow Indicator
   ══════════════════════════════════════════════════════════ */
.step-bar {
  display: flex; align-items: center; gap: var(--sp-sm);
  margin-bottom: var(--sp-xl);
  padding: var(--sp-lg);
  background: var(--periwinkle);
  clip-path: polygon(var(--chamfer) 0, 100% 0, 100% calc(100% - var(--chamfer)), calc(100% - var(--chamfer)) 100%, 0 100%, 0 var(--chamfer));
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.3),
    inset 0 -1px 0 var(--chrome-indigo);
}
.step-item {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; color: var(--muted-indigo);
  font-family: Arial, Helvetica, sans-serif;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  transition: color 0.15s;
}
.step-item.active { color: var(--carbon); }
.step-item.done { color: var(--nav-gold); }
.step-dot {
  width: 6px; height: 6px; border-radius: var(--r-full);
  background: var(--muted-indigo); flex-shrink: 0;
  transition: background 0.15s;
}
.step-item.active .step-dot { background: var(--signal); }
.step-item.done .step-dot { background: var(--nav-gold); }
.step-line {
  width: 16px; height: 1px;
  background: var(--chrome-indigo);
  flex-shrink: 0;
}

/* ══════════════════════════════════════════════════════════
   DOTTED DIVIDER — Chrome Indigo dotted rule
   ══════════════════════════════════════════════════════════ */
.dotted-divider {
  border: none;
  border-top: 1px dotted var(--muted-indigo);
  margin: var(--sp-md) 0;
}

/* ══════════════════════════════════════════════════════════
   TABS — Chrome Indigo Tabs
   ═��════════════════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
  border-bottom: 1px solid var(--chrome-indigo);
  gap: 0;
  background: var(--periwinkle);
  clip-path: polygon(4px 0, 100% 0, 100% calc(100% - 4px), calc(100% - 4px) 100%, 0 100%, 0 4px);
  padding: 0 4px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.2);
}
.stTabs [data-baseweb="tab"] {
  font-family: Arial, Helvetica, sans-serif;
  font-weight: 700;
  font-size: 11px;
  color: var(--muted-indigo);
  text-transform: uppercase;
  letter-spacing: 0.3px;
  padding: 10px 14px;
  transition: color 0.15s;
}
.stTabs [aria-selected="true"] { color: var(--nav-gold) !important; }

/* ══════════════════════════════════════════════════════════
   INPUTS — White Inset Fields
   ══════════════════════════════════════════════════════════ */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > select,
.stNumberInput > div > div > input {
  clip-path: polygon(3px 0, 100% 0, 100% calc(100% - 3px), calc(100% - 3px) 100%, 0 100%, 0 3px) !important;
  border: 1px solid var(--chrome-indigo) !important;
  font-family: Arial, Helvetica, sans-serif !important;
  font-size: 12px !important;
  color: var(--ink) !important;
  background: var(--surface) !important;
  box-shadow:
    inset 0 1px 2px rgba(0,0,0,0.06),
    inset 0 -1px 0 rgba(255,255,255,0.5) !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
  border-color: var(--signal) !important;
  box-shadow:
    inset 0 1px 2px rgba(0,0,0,0.06),
    0 0 0 2px rgba(246,141,31,0.15) !important;
}

/* Checkboxes */
.stCheckbox label {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 12px;
  color: var(--ink);
}
.stCheckbox [data-baseweb="checkbox"] {
  border-color: var(--chrome-indigo) !important;
}
.stCheckbox [data-baseweb="checkbox"][aria-checked="true"] {
  background: var(--signal) !important;
  border-color: var(--signal) !important;
}

/* Radio */
.stRadio label {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 12px;
}
.stRadio [data-baseweb="radio"] {
  border-color: var(--chrome-indigo) !important;
}
.stRadio [data-baseweb="radio"][aria-checked="true"] {
  background: var(--signal) !important;
  border-color: var(--signal) !important;
}

/* Sliders */
.stSlider label {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  color: var(--ink-soft);
}
.stSlider [data-baseweb="slider"] div {
  background: var(--chrome-indigo) !important;
}
.stSlider [data-baseweb="slider"] div[role="slider"] {
  background: var(--signal) !important;
  border-color: var(--signal) !important;
}

.stSelectbox label, .stMultiSelect label, .stNumberInput label, .stFileUploader label {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  color: var(--ink-soft);
}
.stFileUploader [data-testid="stFileUploadDropzone"] {
  border: 1px solid var(--chrome-indigo);
  clip-path: polygon(3px 0, 100% 0, 100% calc(100% - 3px), calc(100% - 3px) 100%, 0 100%, 0 3px);
  background: var(--surface);
  font-family: Arial, Helvetica, sans-serif;
  font-size: 12px;
}

/* ══════════════════════════════════════════════════════════
   PROGRESS — Signal Orange Bar
   ══════════════════════════════════════════════════════════ */
.stProgress > div > div > div > div {
  background: var(--signal) !important;
  clip-path: polygon(3px 0, 100% 0, 100% calc(100% - 3px), calc(100% - 3px) 100%, 0 100%, 0 3px) !important;
}
.stProgress > div > div > div {
  background: var(--chrome-indigo) !important;
  clip-path: polygon(3px 0, 100% 0, 100% calc(100% - 3px), calc(100% - 3px) 100%, 0 100%, 0 3px) !important;
  height: 8px !important;
}

/* ══════════════════════════════════════════════════════════
   ALERTS — Nintendo Red for Error
   ══════════════════════════════════════════════════════════ */
.stAlert {
  clip-path: polygon(3px 0, 100% 0, 100% calc(100% - 3px), calc(100% - 3px) 100%, 0 100%, 0 3px);
  border-left: 3px solid var(--nintendo-red);
  font-family: Arial, Helvetica, sans-serif;
  font-size: 12px;
}

/* ══════════════════════════════════════════════════════════
   BADGES — Amber Utility Chips
   ══════════════════════════════════════════════════════════ */
.badge {
  display: inline-block;
  padding: 2px 8px;
  clip-path: polygon(2px 0, 100% 0, 100% calc(100% - 2px), calc(100% - 2px) 100%, 0 100%, 0 2px);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.3px;
  text-transform: uppercase;
  font-family: Arial, Helvetica, sans-serif;
}
.badge-green { background: var(--amber); color: var(--carbon); }
.badge-gray { background: var(--platinum); color: var(--muted-indigo); }
.badge-red { background: var(--nintendo-red); color: var(--surface); }
.badge-blue { background: var(--sky); color: var(--carbon); }

/* ══════════════════════════════════════════════════════════
   VIDEO — Chamfered Beveled Frame
   ══════════════════════════════════════════════════════════ */
video {
  clip-path: polygon(4px 0, 100% 0, 100% calc(100% - 4px), calc(100% - 4px) 100%, 0 100%, 0 4px);
  border: 1px solid var(--chrome-indigo);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.2);
}

/* ══════════════════════════════════════════════════════════
   DIVIDER
   ══════════════════════════════════════════════════════════ */
hr {
  border: none !important;
  border-top: 1px solid var(--chrome-indigo) !important;
  margin: var(--sp-lg) 0 !important;
}

/* ══════════════════════════════════════════════════════════
   EXPANDER — Carbon Header
   ══════════════════════════════════════════════════════════ */
.streamlit-expanderHeader {
  font-family: Arial, Helvetica, sans-serif !important;
  font-weight: 700 !important;
  font-size: 12px !important;
  text-transform: uppercase !important;
  letter-spacing: 0.3px !important;
  color: var(--surface) !important;
  background: var(--carbon) !important;
  clip-path: polygon(4px 0, 100% 0, 100% calc(100% - 4px), calc(100% - 4px) 100%, 0 100%, 0 4px) !important;
  padding: var(--sp-sm) var(--sp-md) !important;
}
.streamlit-expanderContent {
  background: var(--periwinkle) !important;
  padding: var(--sp-md) !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.2),
    inset 0 -1px 0 var(--chrome-indigo);
}

/* ══════════════════════════════════════════════════════════
   SKELETON LOADING
   ══════════════════════════════════════════════════════════ */
@keyframes skeleton-loading {
  0% { background-position: -200px 0; }
  100% { background-position: calc(200px + 100%) 0; }
}
.skeleton {
  background: linear-gradient(90deg, var(--chrome-indigo) 25%, rgba(255,255,255,0.1) 50%, var(--chrome-indigo) 75%);
  background-size: 200px 100%;
  animation: skeleton-loading 1.5s ease-in-out infinite;
  clip-path: polygon(2px 0, 100% 0, 100% calc(100% - 2px), calc(100% - 2px) 100%, 0 100%, 0 2px);
  height: 16px;
  margin-bottom: var(--sp-sm);
}

/* ══════════════════════════════════════════════════════════
   METRICS
   ══════════════════════════════════════════════════════════ */
.stMetric {
  background: var(--periwinkle);
  clip-path: polygon(4px 0, 100% 0, 100% calc(100% - 4px), calc(100% - 4px) 100%, 0 100%, 0 4px);
  padding: var(--sp-md);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.3),
    inset 0 -1px 0 var(--chrome-indigo);
}
.stMetric label {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--ink-soft);
}
.stMetric [data-testid="stMetricValue"] {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 24px;
  font-weight: 900;
  color: var(--carbon);
}

/* ══════════════════════════════════════════════════════════
   LINKS & TEXT
   ══════════════════════════════════════════════════════════ */
a {
  color: var(--ink-soft) !important;
  font-weight: 700;
  font-family: Arial, Helvetica, sans-serif;
  font-size: 12px;
}
a:hover { color: var(--nav-gold) !important; }

h1, h2, h3, h4, h5, h6 {
  font-family: Arial, Helvetica, sans-serif;
  color: var(--carbon);
}
p {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 12px;
  line-height: 1.4;
  color: var(--ink);
}
code {
  font-size: 11px;
  background: var(--platinum);
  padding: 1px 4px;
  clip-path: polygon(2px 0, 100% 0, 100% calc(100% - 2px), calc(100% - 2px) 100%, 0 100%, 0 2px);
  border: 1px solid var(--chrome-indigo);
}
small { font-size: 10px; color: var(--muted-indigo); }

/* ══════════════════════════════════════════════════════════
   TOAST / SUCCESS / ERROR / WARNING
   ══════════════════════════════════════════════════════════ */
.stSuccess, .stInfo {
  background: var(--sky) !important;
  border-left: 3px solid var(--systems-teal) !important;
  font-family: Arial, Helvetica, sans-serif;
  font-size: 12px;
  clip-path: polygon(3px 0, 100% 0, 100% calc(100% - 3px), calc(100% - 3px) 100%, 0 100%, 0 3px);
}
.stError {
  background: rgba(230,0,18,0.05) !important;
  border-left: 3px solid var(--nintendo-red) !important;
  font-family: Arial, Helvetica, sans-serif;
  font-size: 12px;
  clip-path: polygon(3px 0, 100% 0, 100% calc(100% - 3px), calc(100% - 3px) 100%, 0 100%, 0 3px);
}
.stWarning {
  background: rgba(236,171,55,0.08) !important;
  border-left: 3px solid var(--amber) !important;
  font-family: Arial, Helvetica, sans-serif;
  font-size: 12px;
  clip-path: polygon(3px 0, 100% 0, 100% calc(100% - 3px), calc(100% - 3px) 100%, 0 100%, 0 3px);
}

.stSpinner {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 12px;
  font-weight: 700;
  color: var(--ink-soft);
}

/* ══════════════════════════════════════════════════════════
   HAMBURGER MENU — Tiga garis ☰ toggle sidebar
   ══════════════════════════════════════════════════════════ */
.hamburger-wrap {
  position: absolute;
  top: 6px;
  left: 10px;
  z-index: 99999;
}
.hamburger-wrap .stButton > button {
  width: 40px !important;
  height: 40px !important;
  min-width: 40px !important;
  padding: 0 !important;
  background: var(--carbon) !important;
  border: 1px solid rgba(255,255,255,0.1) !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  font-size: 20px !important;
  font-weight: 400 !important;
  color: var(--on-carbon) !important;
  clip-path: polygon(3px 0, 100% 0, 100% calc(100% - 3px), calc(100% - 3px) 100%, 0 100%, 0 3px) !important;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3) !important;
  cursor: pointer !important;
  line-height: 1 !important;
}
.hamburger-wrap .stButton > button:hover {
  background: var(--carbon-soft) !important;
}
.hamburger-wrap .stButton > button:active {
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.3) !important;
}



/* ══════════════════════════════════════════════════════════
   SIDEBAR — Slide in/out via CSS variable
   ══════════════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* ══════════════════════════════════════════════════════════
   RESPONSIVE — Mobile Stack
   ══════════════════════════════════════════════════════════ */
@media (max-width: 720px) {
  /* Sembunyikan streamlit sidebar toggle bawaan, pake punya kita */
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
  .step-bar { flex-wrap: wrap; gap: 4px; padding: var(--sp-sm); }
  .step-item { font-size: 9px; }
  .step-line { width: 10px; }
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

def _login_page():
    st.markdown("""
    <style>
    .login-container { max-width: 380px; margin: 80px auto; text-align: center; }
    .login-logo { font-size: 44px; margin-bottom: 8px; }
    .login-title { font-size: 28px; font-weight: 900; letter-spacing: -0.3px; margin-bottom: 4px; color: var(--carbon); font-family: Arial, Helvetica, sans-serif; -webkit-text-stroke: 1px var(--s[...]
    .login-sub { font-size: 12px; color: var(--ink-soft); margin-bottom: 32px; font-family: Arial, Helvetica, sans-serif; }
    .login-box { background: var(--periwinkle); clip-path: polygon(6px 0, 100% 0, 100% calc(100% - 6px), calc(100% - 6px) 100%, 0 100%, 0 6px); padding: var(--sp-xl); box-shadow: inset 0 1px 0 rg[...]
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.markdown('<div class="login-logo">⚡</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-title">VideoClipse</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-sub">AI Video Studio · Sign in to continue</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
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
                st.markdown(f'<a href="{sb_url}/auth/v1/authorize?{params}" target="_self"><div style="padding:12px 24px;background:var(--surface);border:1px solid var(--chrome-indigo);clip-path:[...]
            else:
                st.info("Configure SUPABASE_AUTH_CLIENT_ID for Google OAuth, or use Guest mode below.")
        else:
            st.info("Local mode: sign in as guest to continue.")
        name = st.text_input("Nama", placeholder="Your name (guest)", key="guest_name", label_visibility="collapsed")
        if st.button("Continue as Guest", type="primary", use_container_width=True):
            st.session_state.user = {"id": name or "guest", "name": name or "Guest", "email": "", "avatar": ""}
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

def _init_state():
    keys_default = {
        "result": None, "sel_moment": None, "out_video": None,
        "processing": False, "rendering": False,
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
                <div style="font-weight:700;font-size:12px;color:var(--carbon)">{v.name}</div>
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
    st.markdown('<p class="page-sub">Paste a link or upload a file to create viral clips</p>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["\U0001f517 Link", "\U0001f4c1 Upload", "\U0001f33e Farm"])
    with tab1:
        url = st.text_input("Video URL", placeholder="https://youtube.com/...", key="vurl_input", label_visibility="collapsed")
        if url:
            st.session_state.vurl = url
            p = VideoDownloader.detect_platform(url)
            if p:
                st.markdown(f'<p style="color:var(--nav-gold);font-size:11px;margin:4px 0;font-weight:700">\u2713 Platform: {p}</p>', unsafe_allow_html=True)
                mode = st.radio("Metode Analisis Momen", ["Rule-based (Cepat)", "Llama AI (Pintar)"], key="link_moment_mode", horizontal=True)
                st.session_state.moment_mode = mode
                if st.button("Download & Analyze", type="primary", use_container_width=True):
                    st.session_state.src = "url"
                    st.session_state.page = "dashboard"
                    st.session_state.processing = True
                    st.session_state.step = 2
                    st.rerun()
            else:
                st.markdown(f'<p style="color:var(--nintendo-red);font-size:11px;margin:4px 0;font-weight:700">Platform not supported</p>', unsafe_allow_html=True)
    with tab2:
        up = st.file_uploader("Upload Video", type=list(SUPPORTED_VIDEO_EXT), label_visibility="collapsed")
        if up:
            sz = len(up.getvalue()) / (1024*1024)
            st.markdown(f'<p style="color:var(--ink-soft);font-size:11px;margin:4px 0">{up.name} ({sz:.1f} MB)</p>', unsafe_allow_html=True)
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
                st.session_state.page = "dashboard"
                st.session_state.processing = True
                st.session_state.step = 2
                st.rerun()
    with tab3:
        st.markdown('<p style="font-size:12px;color:var(--ink-soft);margin-bottom:var(--sp-lg)">One link \u2192 multiple clips \u2192 scheduled upload</p>', unsafe_allow_html=True)
        furl = st.text_input("Farm URL", placeholder="https://youtube.com/...", key="farm_url_input", label_visibility="collapsed")
        if furl:
            st.session_state.farm_url = furl
        cols = st.columns(3)
        fplat = cols[0].multiselect("Platforms", ["youtube","tiktok","facebook"], default=["youtube"], label_visibility="collapsed")
        fcount = cols[1].number_input("Clips", 1, 10, 8, label_visibility="collapsed")
        ftime = cols[2].text_input("Start time", "08:00", label_visibility="collapsed")
        mode_f = st.radio("Metode Analisis Momen (Farm)", ["Rule-based (Cepat)", "Llama AI (Pintar)"], key="farm_moment_mode", horizontal=True)
        st.session_state.moment_mode = mode_f
        if st.button("Process & Schedule All", type="primary", use_container_width=True, disabled=not furl):
            if furl:
                with st.spinner("Generating clips..."):
                    threading.Thread(target=_farm_multi, args=(furl, fplat, fcount, ftime), daemon=True).start()
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
        html = f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px"><div class="skeleton" style="width:16px;height:16px;flex-shrink:0"></div><span style="color:var(--ink-sof[...]