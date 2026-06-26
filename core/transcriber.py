import time
from pathlib import Path
from typing import Tuple, List
from dataclasses import dataclass, field

WHISPER_MODEL_SIZE = "tiny"

@dataclass
class WordTimestamp:
    word: str; start: float; end: float

class AudioTranscriber:
    _model = None

    @classmethod
    def _get_model(cls):
        if cls._model is None:
            from faster_whisper import WhisperModel
            cls._model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
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
            segs, info = model.transcribe(audio_path, beam_size=1, word_timestamps=True,
                vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))
            for s in segs:
                t = s.text.strip()
                if t and s.words:
                    for w in s.words:
                        ww = w.word.strip()
                        if ww: all_words.append(WordTimestamp(ww, round(w.start,2), round(w.end,2)))
            if progress_callback: progress_callback("done", "")
        except Exception as e:
            if progress_callback: progress_callback("error", str(e))
            return "", []

        full_text = " ".join(w.word for w in all_words)
        return full_text.strip(), all_words
