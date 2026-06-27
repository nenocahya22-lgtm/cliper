# VideoClipse - AI Video Farming Studio

OpusClip-inspired tool to create viral clips from YouTube/TikTok/Facebook videos.

## Features
- Download & analyze videos for viral moments
- Auto-transcribe with Whisper AI
- Smart moment detection (Hook, Climax, CTA) with Rule-based or Llama AI
- **CapCut-like editor**: transitions, text overlay, glitch, speed ramp, PIP, bg music
- Video editing with subtitles, filters, aspect ratios
- Schedule & auto-upload to YouTube/TikTok/Facebook via Playwright
- **Google Sign In** with multi-device database sync (Supabase)
- **Auto-delete**: video files auto-removed after all platforms uploaded
- Farm mode: batch process multiple clips
- **Mobile responsive**: works on phone like Opus Clip

## Quick Start

### Local (No Database)
```bash
streamlit run app.py
```

### Local + Supabase (Multi-device sync)
1. Create free account at https://supabase.com
2. Create project, copy `SUPABASE_URL` and `SUPABASE_KEY`
3. Run SQL from `supabase_schema.sql` in Supabase SQL Editor
4. Set environment variables or create `.env`:
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-anon-key
   ```
5. Run:
   ```bash
   streamlit run app.py
   ```

### Deploy to Streamlit Cloud
1. Push to GitHub
2. Go to https://share.streamlit.io
3. Connect repo, set main file to `app.py`
4. Add secrets (Streamlit Cloud Dashboard -> Advanced -> Secrets):
   ```toml
   SUPABASE_URL = "https://your-project.supabase.co"
   SUPABASE_KEY = "your-anon-key"
   ```
5. Deploy! Google Sign In works automatically via Streamlit Auth.

### API Server
```bash
uvicorn backend:app --reload --host 0.0.0.0 --port 8000
```

### System Dependencies
`packages.txt` auto-installs ffmpeg on Streamlit Cloud.
Playwright browser: `playwright install chromium`

## Architecture

```
app.py              # Streamlit UI
backend.py          # FastAPI REST API
farm.py             # CLI farming tool

core/
  ├── database.py   # Database layer (JSON local / Supabase cloud)
  ├── downloader.py # Video/audio download via yt-dlp + ffmpeg
  ├── transcriber.py# Whisper transcription
  ├── finder.py     # Viral moment detection
  ├── editor.py     # FFmpeg video processing (CapCut-like effects)
  ├── uploader.py   # Playwright auto-upload
  ├── scheduler.py  # Queue + scheduler engine
  ├── describer.py  # AI title/description generation
  └── llm.py        # Ollama/Llama integration

accounts/           # Cookies for YouTube/TikTok/Facebook
queue/              # Queue data (synced via Supabase in cloud mode)
output/             # Rendered clips (auto-deleted after upload)
```
