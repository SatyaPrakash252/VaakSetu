"""
VaakSetu v2.0 — Background Noise Analysis Engine
Classifies background audio for threat signals: screaming, struggle, crying
With proper audio format conversion for browser-recorded audio
"""
import logging, subprocess, tempfile, os
from typing import Dict, Any

logger = logging.getLogger("vaaksetu.noise")


class NoiseEngine:
    def __init__(self):
        self._ready = True
        logger.info("NoiseEngine initialized")

    def _convert_to_wav(self, input_path: str) -> str:
        """Convert any audio format to WAV for librosa processing."""
        out_path = input_path + ".converted.wav"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", "-f", "wav", out_path],
                capture_output=True, timeout=15
            )
            if os.path.exists(out_path) and os.path.getsize(out_path) > 44:
                return out_path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(input_path)
            audio = audio.set_frame_rate(16000).set_channels(1)
            audio.export(out_path, format="wav")
            if os.path.exists(out_path) and os.path.getsize(out_path) > 44:
                return out_path
        except Exception as e:
            logger.warning(f"pydub conversion failed: {e}")
        return input_path

    def analyze(self, audio_bytes: bytes) -> Dict[str, Any]:
        """Analyze background audio channel for threat indicators"""
        temp_path = None
        wav_path = None
        try:
            import librosa
            import numpy as np

            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                f.write(audio_bytes)
                temp_path = f.name

            wav_path = self._convert_to_wav(temp_path)
            y, sr = librosa.load(wav_path, sr=16000)

            if len(y) < sr * 0.3:
                logger.warning("Audio too short for noise analysis")
                return {"screaming": 0, "struggle": 0, "crying": 0, "dominant_type": "ambient", "is_threat": False, "confidence": 0}

            rms = float(librosa.feature.rms(y=y).mean())
            zcr = float(librosa.feature.zero_crossing_rate(y).mean())
            spec_bw = float(librosa.feature.spectral_bandwidth(y=y, sr=sr).mean())
            centroid = float(librosa.feature.spectral_centroid(y=y, sr=sr).mean())

            # Heuristic noise classification
            screaming = min(1.0, max(0, (centroid - 3000) / 2000 + rms * 8))
            struggle = min(1.0, max(0, (zcr - 0.1) * 5 + (spec_bw - 2000) / 3000))
            crying = min(1.0, max(0, (rms - 0.01) * 5 + (centroid - 1500) / 2000))

            scores = {"screaming": screaming, "struggle": struggle, "crying": crying}
            dominant = max(scores, key=scores.get)
            is_threat = max(scores.values()) > 0.4

            return {
                "screaming": round(screaming, 3),
                "struggle": round(struggle, 3),
                "crying": round(crying, 3),
                "dominant_type": dominant if is_threat else "ambient",
                "is_threat": is_threat,
                "confidence": round(max(scores.values()), 3),
            }
        except Exception as e:
            logger.error(f"Noise analysis error: {e}")
            return {"screaming": 0, "struggle": 0, "crying": 0, "dominant_type": "ambient", "is_threat": False, "confidence": 0}
        finally:
            if temp_path and os.path.exists(temp_path):
                try: os.unlink(temp_path)
                except: pass
            if wav_path and wav_path != temp_path and os.path.exists(wav_path):
                try: os.unlink(wav_path)
                except: pass

    def simulate_distress(self) -> Dict[str, Any]:
        """Simulate a distress noise scenario for demo"""
        return {
            "screaming": 0.85, "struggle": 0.72, "crying": 0.45,
            "dominant_type": "screaming", "is_threat": True, "confidence": 0.85,
        }

    def is_ready(self) -> bool:
        return self._ready
