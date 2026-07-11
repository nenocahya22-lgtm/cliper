import time, subprocess
from pathlib import Path
from typing import Tuple, List
from dataclasses import dataclass, field

# Try to get FFMPEG_PATH for GPU detection
FFMPEG_PATH = "ffmpeg"
import shutil
_s = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
if _s: FFMPEG_PATH = _s

WHISPER_MODEL_SIZE = "tiny"

@dataclass
class WordTimestamp:
    word: str; start: float; end: float

class AudioTranscriber:
    _model = None
    _gpu_available = None

    @classmethod
    def check_gpu(cls) -> dict:
        """Check if GPU (CUDA) is available for acceleration."""
        if cls._gpu_available is not None:
            return cls._gpu_available

        result = {"cuda": False, "nvenc": False, "device": "cpu", "compute_type": "int8"}

        # Check CUDA via nvidia-smi
        try:
            r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                parts = r.stdout.strip().split(",")
                result["cuda"] = True
                result["device"] = "cuda"
                result["compute_type"] = "float16"
                if len(parts) >= 1:
                    result["gpu_name"] = parts[0].strip()
                if len(parts) >= 2:
                    result["vram_mb"] = parts[1].strip()
        except:
            pass

        # Check NVENC via ffmpeg
        try:
            r = subprocess.run([FFMPEG_PATH, "-encoders"], capture_output=True, text=True, timeout=5)
            if "h264_nvenc" in r.stdout:
                result["nvenc"] = True
        except:
            pass

        cls._gpu_available = result
        return result

    @classmethod
    def _get_model(cls):
        if cls._model is None:
            import whisper
            gpu = cls.check_gpu()
            device = "cuda" if gpu["cuda"] else "cpu"
            print(f"[Whisper] GPU: {gpu['cuda']} | Device: {device}")
            cls._model = whisper.load_model(WHISPER_MODEL_SIZE)
            if device == "cuda":
                cls._model = cls._model.to("cuda")
        return cls._model

    @staticmethod
    def transcribe(audio_path: str, progress_callback=None) -> Tuple[str, List[WordTimestamp]]:
        if not Path(audio_path).exists(): return "", []
        try:
            model = AudioTranscriber._get_model()
        except Exception as e:
            if progress_callback: progress_callback("error", f"Gagal load Whisper: {e}")
            return "", []

        all_words = []
        try:
            result = model.transcribe(audio_path, word_timestamps=True)
            for seg in result.get("segments", []):
                if seg.get("words"):
                    for w in seg["words"]:
                        ww = w.get("word", "").strip()
                        if ww:
                            all_words.append(WordTimestamp(ww, round(w.get("start", 0), 2), round(w.get("end", 0), 2)))
            if progress_callback: progress_callback("done", "")
        except Exception as e:
            if progress_callback: progress_callback("error", str(e))
            return "", []

        full_text = " ".join(w.word for w in all_words)
        return full_text.strip(), all_words
