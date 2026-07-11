import os, subprocess, uuid, random, math, shutil
from pathlib import Path
from typing import List, Tuple

from core.transcriber import WordTimestamp
from core.downloader import FFMPEG_PATH, VideoDownloader

ASPECT_PRESETS = {
    "Portrait 9:16 (Shorts/TikTok)": {"w": 1080, "h": 1920, "label": "9:16"},
    "Landscape 16:9 (YouTube/FB)": {"w": 1920, "h": 1080, "label": "16:9"},
    "Square 1:1 (Instagram)": {"w": 1080, "h": 1080, "label": "1:1"},
}

SUBTITLE_COLORS = {"Kuning":"&H00FFFF&","Merah":"&H0000FF&","Hijau":"&H00FF00&",
    "Cyan":"&HFFFF00&","Pink":"&HFF00FF&","Putih":"&HFFFFFF&"}

COLOR_FILTERS = {
    "none": "",
    "warm": "colorbalance=rs=.1:gs=.05:bs=-.1,eq=saturation=1.1",
    "cool": "colorbalance=rs=-.1:gs=.05:bs=.1,eq=saturation=1.1",
    "vibrant": "eq=saturation=1.4:contrast=1.1:brightness=0.05",
    "vintage": "colorchannelmixer=.3:.4:.3:0:.3:.4:.3:0:.3:.4:.3,eq=saturation=0.6",
    "neon": "eq=saturation=1.8:contrast=1.2:brightness=0.1",
}

TRANSITIONS = {
    "none": "",
    "crossfade": "fade",
    "fade_to_black": "fade=color=black",
    "fade_to_white": "fade=color=white",
    "wipe_right": "wipe=1:0",
    "wipe_left": "wipe=-1:0",
    "slide_right": "slide=w:0",
    "slide_left": "slide=w:0:reverse=1",
    "zoom_in": "zoompan=z='min(zoom+0.001,1.5)':d=1",
    "zoom_out": "zoompan=z='max(zoom-0.001,1.0)':d=1",
}

TEXT_ANIMATIONS = {
    "none": "",
    "fade_in": "fade=t=in",
    "slide_up": "slide=t:0:-1",
    "slide_down": "slide=t:0:1",
    "typewriter": "typewriter",
    "bounce": "bounce",
    "shake": "shake",
    "glitch_text": "glitch",
}

# ── JumpCutDetector — hapus bagian monoton/boring otomatis ────────
class JumpCutDetector:
    """Detect monotonous/boring segments in video using ffmpeg scene detection
    and motion analysis. Removes slow, low-motion parts automatically."""

    @staticmethod
    def detect_scene_changes(in_vid: str, threshold: float = 0.3) -> list:
        """Detect scene changes using ffmpeg scene filter.
        Returns list of frame timestamps where scenes change."""
        if not Path(in_vid).exists():
            return []
        cmd = [FFMPEG_PATH, "-i", in_vid,
               "-filter:v", f"select='gt(scene,{threshold})'",
               "-f", "null", "-"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            output = r.stderr
        except:
            return []
        # Parse pts_time from scene detection output
        changes = []
        for line in output.split("\n"):
            if "pts_time:" in line:
                try:
                    t = float(line.split("pts_time:")[1].strip().split()[0])
                    changes.append(t)
                except:
                    pass
        return changes

    @staticmethod
    def detect_boring_segments(in_vid: str, motion_thresh: float = 0.1,
                                min_boring_dur: float = 2.0) -> list:
        """Detect boring (low motion / no scene change) segments.
        Returns list of (start, end) tuples of boring segments to remove."""
        changes = JumpCutDetector.detect_scene_changes(in_vid, motion_thresh)
        if not changes:
            return []

        r = subprocess.run([FFMPEG_PATH, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", in_vid], capture_output=True, text=True)
        try:
            total_dur = float(r.stdout.strip())
        except:
            total_dur = 0

        if total_dur <= 0:
            return []

        # Segments between scene changes with low motion are boring
        boring = []
        prev = 0.0
        for ch in sorted(changes):
            gap = ch - prev
            if gap >= min_boring_dur:
                boring.append((prev, ch))
            prev = ch
        # Check tail
        if total_dur - prev >= min_boring_dur:
            boring.append((prev, total_dur))

        return boring

    @staticmethod
    def remove_jump_cuts(in_vid: str, out: str, motion_thresh: float = 0.15,
                          min_keep_dur: float = 1.5, min_boring_dur: float = 2.0) -> Tuple[bool, str, float]:
        """Remove boring/monotonous segments (jump cuts).
        Keeps only segments with significant scene changes or motion.
        Returns (success, error, original_duration)."""
        if not Path(in_vid).exists():
            return False, "File tidak ditemukan", 0

        r = subprocess.run([FFMPEG_PATH, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", in_vid], capture_output=True, text=True)
        try:
            total_dur = float(r.stdout.strip())
        except:
            total_dur = 0

        if total_dur <= 0:
            return False, "Gagal dapat durasi", 0

        # Detect boring segments
        boring = JumpCutDetector.detect_boring_segments(in_vid, motion_thresh, min_boring_dur)
        if not boring:
            shutil.copy2(in_vid, out)
            return True, "", total_dur

        # Build keep segments (inverse of boring)
        keep = []
        cur = 0.0
        for bs, be in boring:
            if bs > cur and (bs - cur) >= min_keep_dur:
                keep.append((cur, bs))
            cur = be
        if total_dur > cur and (total_dur - cur) >= min_keep_dur:
            keep.append((cur, total_dur))

        if not keep:
            return False, "Semua segmen terdeteksi boring", total_dur

        if len(keep) == 1 and keep[0][0] == 0 and abs(keep[0][1] - total_dur) < 1.0:
            shutil.copy2(in_vid, out)
            return True, "", total_dur

        # Build select filter
        select_parts = []
        for ks, ke in keep:
            select_parts.append(f"between(t,{ks},{ke})")
        select_expr = "+".join(select_parts)

        cmd = [FFMPEG_PATH, "-y", "-i", in_vid,
               "-filter_complex",
               f"[0:v]select='{select_expr}',setpts=N/FRAME_RATE/TB[outv];"
               f"[0:a]aselect='{select_expr}',asetpts=N/SAMPLE_RATE/TB[outa]",
               "-map", "[outv]", "-map", "[outa]",
               "-c:v", "libx264", "-preset", "fast", "-crf", "23",
               "-c:a", "aac", "-b:a", "128k",
               "-movflags", "+faststart", out]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                return False, r.stderr[-500:], total_dur
            if Path(out).exists():
                return True, "", total_dur
            return False, "Output tidak dibuat", total_dur
        except subprocess.TimeoutExpired:
            return False, "Timeout", total_dur
        except Exception as e:
            return False, str(e), total_dur


# ── SilenceRemover — seperti Videotto smart dead space removal ──────
class SilenceRemover:
    """Detect and remove silence/dead space from video using ffmpeg silencedetect.
    Like Videotto's auto dead space removal."""

    @staticmethod
    def detect_silence(in_vid: str, noise_thresh: str = "-30dB", min_silence_dur: float = 0.5) -> list:
        """Detect silent segments in video. Returns list of (start, end) tuples."""
        if not Path(in_vid).exists():
            return []
        cmd = [FFMPEG_PATH, "-i", in_vid,
               "-af", f"silencedetect=noise={noise_thresh}:d={min_silence_dur}",
               "-f", "null", "-"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            output = r.stderr
        except:
            return []

        # Parse silencedetect output
        silences = []
        start, end = None, None
        for line in output.split("\n"):
            if "silence_start:" in line:
                try:
                    start = float(line.split("silence_start:")[1].strip())
                except:
                    pass
            elif "silence_end:" in line:
                try:
                    parts = line.split("silence_end:")[1].strip().split("|")
                    end = float(parts[0].strip())
                    if start is not None:
                        silences.append((start, end))
                        start, end = None, None
                except:
                    pass
        return silences

    @staticmethod
    def get_keep_segments(silences: list, total_dur: float, min_keep_dur: float = 0.5) -> list:
        """Convert silence segments into non-silence segments to keep.
        Returns list of (start, end) tuples of segments to keep."""
        if not silences:
            return [(0, total_dur)]

        keep = []
        cur = 0.0
        for s_start, s_end in silences:
            if s_start > cur and (s_start - cur) >= min_keep_dur:
                keep.append((cur, s_start))
            cur = s_end
        if total_dur > cur and (total_dur - cur) >= min_keep_dur:
            keep.append((cur, total_dur))
        return keep

    @staticmethod
    def remove_silence(in_vid: str, out: str, noise_thresh: str = "-30dB",
                       min_silence_dur: float = 0.5, min_keep_dur: float = 0.5) -> Tuple[bool, str, float]:
        """Remove silence/dead space from video. Returns (success, error, original_duration).
        Uses ffmpeg select filter to concatenate only non-silent segments."""
        if not Path(in_vid).exists():
            return False, "File tidak ditemukan", 0

        # Get original duration
        r = subprocess.run([FFMPEG_PATH, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", in_vid], capture_output=True, text=True)
        try:
            total_dur = float(r.stdout.strip())
        except:
            total_dur = 0

        if total_dur <= 0:
            return False, "Gagal dapat durasi video", 0

        # Detect silence
        silences = SilenceRemover.detect_silence(in_vid, noise_thresh, min_silence_dur)
        if not silences:
            # No silence detected, just copy
            shutil.copy2(in_vid, out)
            return True, "", total_dur

        # Get keep segments
        keep = SilenceRemover.get_keep_segments(silences, total_dur, min_keep_dur)
        if not keep:
            return False, "Tidak ada segmen yang bisa disimpan setelah hapus silence", total_dur

        if len(keep) == 1 and keep[0][0] == 0 and abs(keep[0][1] - total_dur) < 0.5:
            # No significant silence found, just copy
            shutil.copy2(in_vid, out)
            return True, "", total_dur

        # Build select filter: keep only non-silent segments
        select_parts = []
        for ks, ke in keep:
            select_parts.append(f"between(t,{ks},{ke})")
        select_expr = "+".join(select_parts)

        cmd = [FFMPEG_PATH, "-y", "-i", in_vid,
               "-filter_complex",
               f"[0:v]select='{select_expr}',setpts=N/FRAME_RATE/TB[outv];"
               f"[0:a]aselect='{select_expr}',asetpts=N/SAMPLE_RATE/TB[outa]",
               "-map", "[outv]", "-map", "[outa]",
               "-c:v", "libx264", "-preset", "fast", "-crf", "23",
               "-c:a", "aac", "-b:a", "128k",
               "-movflags", "+faststart",
               out]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                return False, r.stderr[-500:], total_dur
            if Path(out).exists():
                return True, "", total_dur
            return False, "Output file not created", total_dur
        except subprocess.TimeoutExpired:
            return False, "Timeout saat hapus silence", total_dur
        except Exception as e:
            return False, str(e), total_dur


# ── New CapCut-like features ─────────────────────────────────
CHROMA_KEY_COLORS = {
    "Green (Hijau)": "0x00FF00",
    "Blue (Biru)": "0x0000FF",
    "Red (Merah)": "0xFF0000",
    "White (Putih)": "0xFFFFFF",
    "Custom": "custom",
}

class SubtitleGenerator:
    @staticmethod
    def generate_ass(word_ts: List[WordTimestamp], out: str, color: str="&H00FFFF&",
                     font: str="Montserrat", size: int=48, alignment: int=5,
                     uppercase: bool=False) -> str:
        if not word_ts: return ""
        ass = f"""[Script Info]
; Generated by VideoClipse
ScriptType: v4.00+
Collisions: Normal

[v4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},{color},&HFFFFFF&,&H000000&,&H000000&,1,0,0,0,100,100,0,0,1,3,1,{alignment},10,10,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines, cur = [], []
        for wt in word_ts:
            cur.append(wt)
            if len(cur) >= 8: lines.append(cur); cur = []
        if cur: lines.append(cur)

        for lw in lines:
            stt, ett = lw[0].start, lw[-1].end
            def _fmt(s):
                h=int(s//3600); m=int((s%3600)//60); se=int(s%60); cs=int((s-int(s))*100)
                return f"{h}:{m:02d}:{se:02d}.{cs:02d}"
            parts = []
            for wt in lw:
                w = wt.word.strip()
                if not w: continue
                if uppercase:
                    w = w.upper()
                cs_dur = max(1, int((wt.end-wt.start)*100))
                ws = w.replace("{","\\{").replace("}","\\}")
                parts.append(f"{{\\kf{cs_dur}}}{ws} ")
            txt = "".join(parts).strip()
            if txt: ass += f"Dialogue: 0,{_fmt(stt)},{_fmt(ett)},Default,,0,0,0,,{txt}\n"
        with open(out,"w",encoding="utf-8") as f: f.write(ass)
        return out

class VideoProcessor:
    # ── New CapCut Feature Filters ────────────────────────────────
    @staticmethod
    def _reverse_filter(is_enabled: bool = False) -> str:
        """Reverse clip (play backwards) - like CapCut reverse"""
        if not is_enabled:
            return ""
        return "reverse"

    @staticmethod
    def _chroma_key_filter(color_hex: str, similarity: float = 0.4, blend: float = 0.1) -> str:
        """Chroma key / Green screen effect - like CapCut chroma key"""
        if not color_hex or color_hex == "custom":
            return ""
        # Convert hex to RGB for colorkey
        try:
            hex_str = color_hex.replace("0x", "")
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
            return f"colorkey=0x{r:02x}{g:02x}{b:02x}:{similarity}:{blend}"
        except:
            return ""

    @staticmethod
    def _ken_burns_filter(enable: bool = False, zoom_start: float = 1.0, zoom_end: float = 1.3,
                          pan_x_start: float = 0, pan_x_end: float = 0,
                          pan_y_start: float = 0, pan_y_end: float = 0,
                          duration: float = 10, aspect_key: str = "Portrait 9:16 (Shorts/TikTok)") -> str:
        """Ken Burns effect (pan & zoom) - like CapCut keyframe animation"""
        if not enable:
            return ""
        # Dynamic resolution based on aspect ratio
        preset = ASPECT_PRESETS.get(aspect_key, ASPECT_PRESETS["Portrait 9:16 (Shorts/TikTok)"])
        tw, th = preset["w"], preset["h"]
        zoom_rate = (zoom_end - zoom_start) / max(duration, 1)
        pan_rate_x = (pan_x_end - pan_x_start) / max(duration, 1)
        pan_rate_y = (pan_y_end - pan_y_start) / max(duration, 1)
        return f"zoompan=z='{zoom_start}+{zoom_rate}*on':x='iw/2-(iw/zoom/2)+{pan_rate_x}*on':y='ih/2-(ih/zoom/2)+{pan_rate_y}*on':d={int(duration)}:s={tw}x{th}"

    @staticmethod
    def _blur_background_filter(preset: str = "none") -> str:
        """Blur background effect - like CapCut blur"""
        blur_map = {
            "none": "",
            "light": "boxblur=2:1",
            "medium": "boxblur=5:2",
            "heavy": "boxblur=10:3",
            "gaussian": "gblur=sigma=5",
            "pixelate": "pixelize=w=iw/20:h=ih/20",
        }
        return blur_map.get(preset, "")

    @staticmethod
    def _stabilize_filter(enable: bool = False, shakiness: int = 5, accuracy: int = 15) -> str:
        """Video stabilization - like CapCut stabilize"""
        if not enable:
            return ""
        return f"vidstabdetect=shakiness={shakiness}:accuracy={accuracy}:result=transforms.trf"

    @staticmethod
    def _crop_scale_filter(aspect_key: str) -> str:
        preset = ASPECT_PRESETS.get(aspect_key, ASPECT_PRESETS["Portrait 9:16 (Shorts/TikTok)"])
        tw, th = preset["w"], preset["h"]
        label = preset["label"]
        if label == "9:16":
            return f"crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale={tw}:{th}"
        elif label == "16:9":
            return f"crop=iw:iw*9/16:0:(ih-iw*9/16)/2,scale={tw}:{th}"
        elif label == "1:1":
            return f"crop=min(iw,ih):min(iw,ih):(iw-min(iw,ih))/2:(ih-min(iw,ih))/2,scale={tw}:{th}"
        return f"scale={tw}:{th}"

    @staticmethod
    def process_clip(in_vid: str, out: str, sub_ass: str="", wm_path: str="",
                     stt: float=0, ett: float=0, fade_in: float=0.5, fade_out: float=0.8,
                     speed: float=1.0, mirror: bool=False, color_filter: str="none",
                     noise_reduce: bool=False, aspect: str="Portrait 9:16 (Shorts/TikTok)",
                     contrast: float=1.0, brightness: float=0.0, saturation: float=1.0,
                     vignette: bool=False, sepia: bool=False, grayscale: bool=False,
                     sharpen: bool=False, edge_detect: bool=False,
                     transition: str="none", text_overlay: str="",
                     text_animation: str="none", bg_music: str="",
                     music_volume: float=0.3, pip_video: str="",
                     speed_ramp: str="none", glitch: bool=False,
                     subtitle_animation: str="none",
                     # ── New CapCut Features ────────────────────────
                     reverse: bool=False,
                     chroma_key: str="",
                     chroma_similarity: float=0.4,
                     chroma_blend: float=0.1,
                     ken_burns: bool=False,
                     ken_zoom_start: float=1.0,
                     ken_zoom_end: float=1.3,
                     blur_bg: str="none",
                     stabilize: bool=False,
                     stabilize_shakiness: int=5,
                     # ── Silence Removal (seperti Videotto) ──────────
                     remove_silence: bool=False,
                     silence_noise_thresh: str="-30dB",
                     silence_min_dur: float=0.5,
                     # ── Jump Cut / Boring Removal ────────────────────
                     jump_cut: bool=False,
                     jump_cut_thresh: float=0.15) -> Tuple[bool, str]:
        if not Path(in_vid).exists(): return False, "File tidak ditemukan"

        # ── Calculate base duration ──
        if ett > stt:
            dur = ett - stt
        else:
            r = subprocess.run([FFMPEG_PATH,"-v","error","-show_entries","format=duration",
                "-of","default=noprint_wrappers=1:nokey=1", in_vid], capture_output=True, text=True)
            try: dur = float(r.stdout.strip())
            except: dur = 60
            ett = stt + dur

        # ── Step 0: Silence Removal + Jump Cut — apply AFTER trimming ──
        effective_input, temp_files = in_vid, []
        if remove_silence and dur > 0:
            # First trim to clip range, then remove silence on trimmed result
            trimmed = os.path.join(os.path.dirname(out) or ".", f"_trim_{uuid.uuid4().hex[:8]}.mp4")
            trim_cmd = [FFMPEG_PATH, "-y", "-ss", str(stt), "-i", in_vid, "-t", str(dur),
                        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                        "-c:a", "aac", "-b:a", "128k", trimmed]
            try:
                subprocess.run(trim_cmd, capture_output=True, text=True, timeout=300)
            except:
                pass

            if Path(trimmed).exists():
                silence_out = os.path.join(os.path.dirname(out) or ".", f"_nosilence_{uuid.uuid4().hex[:8]}.mp4")
                temp_files.append(silence_out)
                ok, err = SilenceRemover.remove_silence(trimmed, silence_out,
                    noise_thresh=silence_noise_thresh,
                    min_silence_dur=silence_min_dur)[:2]
                # Clean up trimmed temp file
                try: Path(trimmed).unlink(missing_ok=True)
                except: pass

                if ok and Path(silence_out).exists():
                    effective_input = silence_out
                    stt = 0
                    r = subprocess.run([FFMPEG_PATH,"-v","error","-show_entries","format=duration",
                        "-of","default=noprint_wrappers=1:nokey=1", silence_out],
                        capture_output=True, text=True)
                    try:
                        new_dur = float(r.stdout.strip())
                        if new_dur > 0:
                            dur = new_dur
                    except:
                        pass
                elif err:
                    return False, f"Silence removal gagal: {err}"

        # ── Step 0b: Jump Cut Removal — trim first if needed, then remove boring ──
        if jump_cut and dur > 0:
            # If stt > 0, trim first to avoid timestamp alignment bug
            if stt > 0 and effective_input == in_vid:
                trimmed_jc = os.path.join(os.path.dirname(out) or ".", f"_trim_jc_{uuid.uuid4().hex[:8]}.mp4")
                trim_cmd = [FFMPEG_PATH, "-y", "-ss", str(stt), "-i", in_vid, "-t", str(dur),
                            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                            "-c:a", "aac", "-b:a", "128k", trimmed_jc]
                try:
                    subprocess.run(trim_cmd, capture_output=True, text=True, timeout=300)
                    if Path(trimmed_jc).exists():
                        temp_files.append(trimmed_jc)
                        effective_input = trimmed_jc
                        stt = 0
                except:
                    pass
            jump_out = os.path.join(os.path.dirname(out) or ".", f"_jump_{uuid.uuid4().hex[:8]}.mp4")
            temp_files.append(jump_out)
            ok, err = JumpCutDetector.remove_jump_cuts(effective_input, jump_out,
                motion_thresh=jump_cut_thresh)[:2]
            if ok and Path(jump_out).exists():
                effective_input = jump_out
                stt = 0
                r = subprocess.run([FFMPEG_PATH,"-v","error","-show_entries","format=duration",
                    "-of","default=noprint_wrappers=1:nokey=1", jump_out],
                    capture_output=True, text=True)
                try:
                    new_dur = float(r.stdout.strip())
                    if new_dur > 0:
                        dur = new_dur
                except:
                    pass
        if dur <= 0: dur = 10
        fade_in = min(fade_in, dur/2); fade_out = min(fade_out, dur/2)
        fout_start = dur - fade_out

        flt = [VideoProcessor._crop_scale_filter(aspect)]

        if mirror:
            flt.append("hflip")

        # Speed ramp
        if speed_ramp == "ease_in":
            flt.append(f"setpts='if(lte(T,{dur*0.3}),{1/speed}*PTS*((T)/({dur*0.3})+0.5),{1/speed}*PTS)'")
        elif speed_ramp == "ease_out":
            flt.append(f"setpts='if(gte(T,{dur*0.7}),{1/speed}*PTS*(({dur}-T)/({dur*0.3})+0.5),{1/speed}*PTS)'")
        elif speed != 1.0:
            flt.append(f"setpts={1/speed}*PTS")

        cf = COLOR_FILTERS.get(color_filter, "")
        if cf:
            flt.append(cf)
        if contrast != 1.0 or brightness != 0.0 or saturation != 1.0:
            flt.append(f"eq=contrast={contrast}:brightness={brightness}:saturation={saturation}")
        if vignette:
            flt.append("vignette")
        if sepia:
            flt.append("colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131")
        if grayscale:
            flt.append("hue=s=0")
        if sharpen:
            flt.append("unsharp=5:5:1.0:5:5:0.0")
        if edge_detect:
            flt.append("edgedetect=low=0.1:high=0.4")
        if noise_reduce:
            flt.append("hqdn3d=2:2:3:3")
        if glitch:
            flt.append("crop=iw:ih:0:0,split[orig][glitch];[glitch]crop=iw/4:ih/2:iw/2+random(1)*iw/4:0,edgedetect=low=0.2:high=0.5,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)',setpts=PTS+random(1)*0.1/TB[glitch2];[orig][glitch2]overlay")

        if fade_in > 0:
            flt.append(f"fade=t=in:st=0:d={fade_in}")
        if fade_out > 0 and fout_start > 0:
            flt.append(f"fade=t=out:st={fout_start}:d={fade_out}")

        # Transition effect (applied as overlay at the start)
        tr_filter = TRANSITIONS.get(transition, "")
        if tr_filter and transition not in ("none", ""):
            flt.append(tr_filter)

        if sub_ass and Path(sub_ass).exists():
            escaped_path = sub_ass.replace('\\', '/').replace(':', '\\:')
            flt.append(f"ass='{escaped_path}'")

        # Text overlay with animation
        text_inputs = []
        if text_overlay:
            txt_esc = text_overlay.replace("'", "'\\''").replace(":", "\\:")
            anim_filter = TEXT_ANIMATIONS.get(text_animation, "")
            txt_layer = f"drawtext=text='{txt_esc}':fontsize=48:fontcolor=white:shadowcolor=black:shadowx=2:shadowy=2:x=(w-text_w)/2:y=h*0.1:enable='between(t,0,{dur})'"
            if text_animation == "fade_in":
                txt_layer += f":alpha='if(lt(t,0.5),t/0.5,1)'"
            elif text_animation == "slide_up":
                txt_layer += f":y='h*0.1+20*sin(2*PI*t)'"
            elif text_animation == "bounce":
                txt_layer += f":y='h*0.1-10*abs(sin(3*PI*t))'"
            flt.append(txt_layer)

        # PIP overlay
        pip_input = ""
        pip_filter = ""
        if pip_video and Path(pip_video).exists():
            pip_input = " -i " + pip_video
            pip_w = int(ASPECT_PRESETS.get(aspect, {}).get("w", 1080) * 0.3)
            pip_h = int(ASPECT_PRESETS.get(aspect, {}).get("h", 1920) * 0.3)
            pip_filter = f",[pip]scale={pip_w}:{pip_h}[pip_scaled]"

        # ── New CapCut Features ────────────────────────────────────
        # Chroma key / Green screen
        ck = VideoProcessor._chroma_key_filter(chroma_key, chroma_similarity, chroma_blend)
        if ck:
            flt.append(ck)

        # Blur background
        blr = VideoProcessor._blur_background_filter(blur_bg)
        if blr:
            flt.append(blr)

        # Reverse clip
        if reverse:
            flt.append("reverse")
            # Reverse audio too

        # Ken Burns effect (pan & zoom) — fixed aspect-aware version
        if ken_burns:
            kb = VideoProcessor._ken_burns_filter(True, ken_zoom_start, ken_zoom_end,
                0, 0, 0, 0, dur, aspect)
            if kb:
                flt.append(kb)

        # Build filter string
        filter_str = ",".join(flt)

        # Audio filters
        audio_filters = []
        if speed != 1.0 and speed_ramp == "none":
            audio_filters.append(f"atempo={min(speed, 2.0)}")
        if fade_in > 0:
            audio_filters.append(f"afade=t=in:ss=0:d={fade_in}")
        if fade_out > 0 and fout_start > 0:
            audio_filters.append(f"afade=t=out:st={fout_start}:d={fade_out}")

        # Build command
        cmd = [FFMPEG_PATH, "-y", "-ss", str(stt), "-i", effective_input]

        # PIP video input
        if pip_video and Path(pip_video).exists():
            cmd += ["-i", pip_video]

        # Background music
        bg_music_input = ""
        if bg_music and Path(bg_music).exists():
            cmd += ["-i", bg_music]
            bg_music_input = f"[2:a]volume={music_volume}[bga];"

        cmd += ["-t", str(dur)]

        # Combine everything
        if pip_video and Path(pip_video).exists():
            overlays = []
            pip_pos_x = ASPECT_PRESETS.get(aspect, {}).get("w", 1080) - pip_w - 20
            pip_pos_y = 20
            overlays.append(f"[1:v]scale={pip_w}:{pip_h}[pip_scaled];[0:v]{filter_str}[main];[main][pip_scaled]overlay={pip_pos_x}:{pip_pos_y}")
            final_filter = overlays[-1]
        else:
            final_filter = f"[0:v]{filter_str}"

        if bg_music and Path(bg_music).exists():
            af = ",".join(audio_filters) if audio_filters else "anull"
            final_af = f"{bg_music_input}[0:a]{af}[main_a];[main_a][bga]amix=inputs=2:duration=first[outa]"
            cmd += ["-filter_complex", final_filter + ";" + final_af]
            cmd += ["-map", "[outa]"]
        elif audio_filters:
            cmd += ["-af", ",".join(audio_filters)]

        cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out]

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                for tf in temp_files:
                    try: Path(tf).unlink(missing_ok=True)
                    except: pass
                return False, r.stderr[-500:]
            # Clean up all temp files
            for tf in temp_files:
                try: Path(tf).unlink(missing_ok=True)
                except: pass
            return True, ""
        except subprocess.TimeoutExpired:
            for tf in temp_files:
                try: Path(tf).unlink(missing_ok=True)
                except: pass
            return False, "Timeout"
        except Exception as e:
            for tf in temp_files:
                try: Path(tf).unlink(missing_ok=True)
                except: pass
            return False, str(e)

    @staticmethod
    def auto_process(url: str, work_dir: str, min_dur: float = 30, max_dur: float = 60,
                     with_subtitle: bool = True, subtitle_color: str = "Kuning",
                     add_watermark: bool = False, watermark_path: str = "",
                     anti_copy: bool = True,
                     aspect: str = "Portrait 9:16 (Shorts/TikTok)",
                     use_llm: bool = False, model_name: str = None) -> Tuple[bool, str, str, str, float, str, list]:
        os.makedirs(work_dir, exist_ok=True)
        audio, title, dur = VideoDownloader.download_audio(url, work_dir, max_dur=600)
        if not audio or not Path(audio).exists():
            return False, "", "Gagal download audio", "", 0, "", []

        from core.transcriber import AudioTranscriber
        text, wts = AudioTranscriber.transcribe(audio)
        if not text:
            text = f"Video: {title} ({dur:.0f}s)"

        from core.finder import ViralMomentFinder
        moments = ViralMomentFinder.find_moments(text, dur, wts, use_llm=use_llm, model_name=model_name)
        best = ViralMomentFinder.auto_best_moment(moments, min_dur, max_dur)

        clip = VideoDownloader.download_video_clip(url, work_dir, best.start_time, best.end_time)
        if not clip or not Path(clip).exists():
            return False, "", "Gagal download video", "", 0, "", []

        sub_path = ""
        if with_subtitle and wts:
            rel = [wt for wt in wts if wt.start < best.end_time and wt.end > best.start_time]
            if rel:
                shifted = [WordTimestamp(w.word, max(0,w.start-best.start_time), w.end-best.start_time) for w in rel]
                sub_path = os.path.join(work_dir, f"subs_{uuid.uuid4().hex[:8]}.ass")
                SubtitleGenerator.generate_ass(shifted, sub_path, SUBTITLE_COLORS.get(subtitle_color, "&H00FFFF&"))

        clip_dur = best.end_time - best.start_time
        out_path = os.path.join(work_dir, f"out_{uuid.uuid4().hex[:8]}.mp4")

        if anti_copy:
            speed = random.choice([1.0, 1.05, 1.07, 1.1])
            mirror = random.choice([True, False])
            color = random.choice(["none", "warm", "cool", "vibrant"])
            noise = random.choice([True, False])
        else:
            speed, mirror, color, noise = 1.0, False, "none", False

        ok, err = VideoProcessor.process_clip(clip, out_path, sub_path, watermark_path,
            0, clip_dur, 0.5, 0.8, speed, mirror, color, noise, aspect=aspect)
        if not ok:
            return False, "", f"Gagal render: {err}", "", 0, "", []

        return True, out_path, title, best.reason, clip_dur, text, moments

    @staticmethod
    def auto_process_multi(url: str, work_dir: str, n_clips: int = 5,
                           min_dur: float = 30, max_dur: float = 60,
                           with_subtitle: bool = True, subtitle_color: str = "Kuning",
                           watermark_path: str = "",
                           anti_copy: bool = True,
                           aspect: str = "Portrait 9:16 (Shorts/TikTok)",
                           use_llm: bool = False, model_name: str = None) -> List[dict]:
        os.makedirs(work_dir, exist_ok=True)
        audio, title, dur = VideoDownloader.download_audio(url, work_dir, max_dur=600)
        if not audio or not Path(audio).exists():
            return []

        from core.transcriber import AudioTranscriber
        text, wts = AudioTranscriber.transcribe(audio)
        if not text:
            text = f"Video: {title} ({dur:.0f}s)"

        from core.finder import ViralMomentFinder
        moments = ViralMomentFinder.find_moments(text, dur, wts, use_llm=use_llm, model_name=model_name)
        top = ViralMomentFinder.top_moments(moments, text, dur, wts, n_clips, min_dur, max_dur)

        results = []
        for i, m in enumerate(top):
            clip = VideoDownloader.download_video_clip(url, work_dir, m.start_time, m.end_time)
            if not clip or not Path(clip).exists():
                continue

            sub_path = ""
            if with_subtitle and wts:
                rel = [wt for wt in wts if wt.start < m.end_time and wt.end > m.start_time]
                if rel:
                    shifted = [WordTimestamp(w.word, max(0,w.start-m.start_time), w.end-m.start_time) for w in rel]
                    sub_path = os.path.join(work_dir, f"subs_{uuid.uuid4().hex[:8]}.ass")
                    SubtitleGenerator.generate_ass(shifted, sub_path, SUBTITLE_COLORS.get(subtitle_color, "&H00FFFF&"))

            out_path = os.path.join(work_dir, f"clip_{i}_{uuid.uuid4().hex[:8]}.mp4")
            clip_dur = m.end_time - m.start_time

            if anti_copy:
                speed = random.choice([1.0, 1.05, 1.07, 1.1])
                mirror = random.choice([True, False])
                color = random.choice(["none", "warm", "cool", "vibrant", "vintage"])
                noise = random.choice([True, False])
            else:
                speed, mirror, color, noise = 1.0, False, "none", False

            ok, err = VideoProcessor.process_clip(clip, out_path, sub_path, watermark_path,
                0, clip_dur, 0.5, 0.8, speed, mirror, color, noise, aspect=aspect)
            if ok:
                results.append({
                    "path": out_path, "title": title, "reason": m.reason,
                    "duration": clip_dur, "start": m.start_time, "end": m.end_time,
                    "transcript_snippet": m.transcript_snippet,
                    "speed": speed, "mirror": mirror, "color": color, "noise": noise
                })
        return results
