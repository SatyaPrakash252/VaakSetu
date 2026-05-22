"""
VaakSetu v2.0 — Emotion Detection Engine
Librosa-based audio feature extraction for panic/fear/calm/distress scoring
Now with proper audio format conversion for browser-recorded audio (webm/opus)
"""
import logging, base64, tempfile, os, subprocess
from typing import Dict, Any

logger = logging.getLogger("vaaksetu.emotion")


def _convert_audio_to_wav(input_path: str) -> str:
    """Convert any audio format to 16kHz mono WAV using ffmpeg or pydub."""
    out_path = input_path + ".converted.wav"
    try:
        # Try ffmpeg first (fastest, handles webm/opus)
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", "-f", "wav", out_path],
            capture_output=True, timeout=15
        )
        if os.path.exists(out_path) and os.path.getsize(out_path) > 44:
            return out_path
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        # Fallback to pydub
        from pydub import AudioSegment
        audio = AudioSegment.from_file(input_path)
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(out_path, format="wav")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 44:
            return out_path
    except Exception as e:
        logger.warning(f"pydub conversion failed: {e}")

    # If conversion fails, return original (librosa might still handle it)
    return input_path


class EmotionEngine:
    def __init__(self):
        self._ready = True
        logger.info("EmotionEngine initialized")

    def analyze(self, audio_base64: str) -> Dict[str, float]:
        """Analyze audio for emotional content using librosa features"""
        temp_path = None
        wav_path = None
        try:
            import librosa
            import numpy as np

            audio_bytes = base64.b64decode(audio_base64)
            # Write raw bytes to temp file
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                f.write(audio_bytes)
                temp_path = f.name

            # Convert to proper WAV (handles webm/opus from browser)
            wav_path = _convert_audio_to_wav(temp_path)

            y, sr = librosa.load(wav_path, sr=16000)

            if len(y) < sr * 0.5:  # Less than 0.5 seconds of audio
                logger.warning("Audio too short for reliable emotion analysis")
                return self._mock_scores()

            # Extract features
            rms = float(librosa.feature.rms(y=y).mean())
            zcr = float(librosa.feature.zero_crossing_rate(y).mean())
            spectral_centroid = float(librosa.feature.spectral_centroid(y=y, sr=sr).mean())
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            mfcc_var = float(np.var(mfcc, axis=1).mean())  # MFCC variance — emotional variation
            pitch = librosa.yin(y, fmin=60, fmax=500)
            pitch_valid = pitch[~np.isnan(pitch)]
            pitch_mean = float(np.mean(pitch_valid)) if len(pitch_valid) > 0 else 200
            pitch_std = float(np.std(pitch_valid)) if len(pitch_valid) > 0 else 0

            # Improved heuristic emotion scoring
            # High pitch + high energy + high ZCR + high MFCC variance = panic/distress
            panic = min(1.0, max(0, (pitch_mean - 220) / 180 + rms * 4 + zcr * 1.5 + mfcc_var * 0.01))
            fear = min(1.0, max(0, (pitch_std / 80) + (zcr - 0.04) * 2.5 + mfcc_var * 0.005))
            distress = min(1.0, max(0, (rms - 0.015) * 8 + (spectral_centroid - 1800) / 2500 + mfcc_var * 0.008))
            calm = max(0, 1.0 - (panic + fear + distress) / 2.5)

            return {
                "panic": round(panic, 3),
                "fear": round(fear, 3),
                "distress": round(distress, 3),
                "calm": round(calm, 3),
                "source": "audio_librosa",
                "features": {
                    "rms": round(rms, 4),
                    "zcr": round(zcr, 4),
                    "pitch_mean": round(pitch_mean, 1),
                    "pitch_std": round(pitch_std, 1),
                    "spectral_centroid": round(spectral_centroid, 1),
                    "mfcc_variance": round(mfcc_var, 4),
                }
            }
        except ImportError:
            logger.warning("Librosa not available, using mock scores")
            return self._mock_scores()
        except Exception as e:
            logger.error(f"Emotion analysis error: {e}")
            return self._mock_scores()
        finally:
            # Clean up temp files
            if temp_path and os.path.exists(temp_path):
                try: os.unlink(temp_path)
                except: pass
            if wav_path and wav_path != temp_path and os.path.exists(wav_path):
                try: os.unlink(wav_path)
                except: pass

    def _mock_scores(self) -> Dict[str, float]:
        return {"panic": 0.1, "fear": 0.1, "distress": 0.15, "calm": 0.65, "source": "mock"}

    def is_ready(self) -> bool:
        return self._ready
