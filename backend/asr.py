"""
VaakSetu — ASR Engine (Multi-backend)
Priority: OpenAI Whisper → SpeechRecognition (Google free) → Error
Handles Kannada, Hindi, English, and code-mixed speech
"""
import os, time, base64, tempfile, logging, subprocess
from typing import Dict, Any, Optional

logger = logging.getLogger("vaaksetu.asr")

# Security limits
MAX_AUDIO_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_AUDIO_DURATION_SECONDS = 60           # 60 seconds
SR_TIMEOUT_SECONDS = 10                   # Google SR API timeout


class ASREngine:
    def __init__(self):
        self._ready = True
        self.model = None
        self.backend = None  # 'whisper' | 'speech_recognition' | None
        self.model_size = os.getenv("WHISPER_MODEL", "base")
        self._ffmpeg_available = self._check_ffmpeg()
        self._detect_backend()
        logger.info(f"ASREngine initialized — backend: {self.backend or 'NONE (text-only mode)'}, ffmpeg: {self._ffmpeg_available}")

    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available for audio conversion"""
        try:
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    def _detect_backend(self):
        """Detect the best available ASR backend"""
        try:
            import whisper
            self.backend = "whisper"
            logger.info(f"ASR backend: OpenAI Whisper (model: {self.model_size})")
            return
        except ImportError:
            logger.info("Whisper not installed — trying SpeechRecognition fallback")
        try:
            import speech_recognition as sr
            self.backend = "speech_recognition"
            logger.info("ASR backend: SpeechRecognition (Google Web Speech API)")
            return
        except ImportError:
            logger.warning("SpeechRecognition not installed either")
        self.backend = None
        logger.warning("NO ASR BACKEND AVAILABLE — audio input will not work, use text input instead")

    def _load_whisper(self):
        """Lazy-load Whisper model"""
        if self.model is None and self.backend == "whisper":
            try:
                import whisper
                self.model = whisper.load_model(self.model_size)
                logger.info(f"Whisper model '{self.model_size}' loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                try:
                    import speech_recognition as sr
                    self.backend = "speech_recognition"
                    logger.info("Fell back to SpeechRecognition backend")
                except ImportError:
                    self.backend = None

    async def transcribe(self, audio_base64: Optional[str] = None, language_hint: str = "auto") -> Dict[str, Any]:
        """Transcribe audio from base64-encoded data"""
        start = time.time()
        if not audio_base64:
            return {"text": "", "language": "unknown", "latency_ms": 0, "confidence": 0.0,
                    "error": "No audio data provided"}

        # Security: check base64 size before decoding
        estimated_size = len(audio_base64) * 3 // 4
        if estimated_size > MAX_AUDIO_SIZE_BYTES:
            return {"text": "", "language": "unknown", "latency_ms": 0, "confidence": 0.0,
                    "error": f"Audio too large ({estimated_size // (1024*1024)}MB). Maximum is {MAX_AUDIO_SIZE_BYTES // (1024*1024)}MB."}

        if self.backend == "whisper":
            return await self._transcribe_whisper(audio_base64, start, language_hint)
        elif self.backend == "speech_recognition":
            return await self._transcribe_sr(audio_base64, start, language_hint)
        else:
            return {"text": "", "language": "unknown", "latency_ms": 0, "confidence": 0.0,
                    "error": "No ASR backend available. Install whisper or SpeechRecognition. Use text input instead."}

    async def _transcribe_whisper(self, audio_base64: str, start: float, language_hint: str = "auto") -> Dict[str, Any]:
        """Transcribe using OpenAI Whisper"""
        self._load_whisper()
        if self.model is None:
            if self.backend == "speech_recognition":
                return await self._transcribe_sr(audio_base64, start, language_hint)
            return {"text": "", "language": "unknown", "latency_ms": 0, "confidence": 0.0,
                    "error": "Whisper model failed to load"}
        try:
            audio_bytes = base64.b64decode(audio_base64)

            # Security: check decoded file size
            if len(audio_bytes) > MAX_AUDIO_SIZE_BYTES:
                return {"text": "", "language": "unknown", "latency_ms": 0, "confidence": 0.0,
                        "error": f"Audio file too large ({len(audio_bytes) // (1024*1024)}MB). Maximum is {MAX_AUDIO_SIZE_BYTES // (1024*1024)}MB."}

            # Always convert to WAV first for reliability
            wav_path = self._convert_to_wav(audio_bytes)
            if not wav_path:
                return {"text": "", "language": "unknown", "latency_ms": 0, "confidence": 0.0,
                        "error": "Audio conversion failed"}

            # Security: check audio duration
            duration = self._get_audio_duration(wav_path)
            if duration and duration > MAX_AUDIO_DURATION_SECONDS:
                logger.warning(f"Audio too long ({duration:.1f}s), truncating to {MAX_AUDIO_DURATION_SECONDS}s")
                wav_path = self._truncate_audio(wav_path, MAX_AUDIO_DURATION_SECONDS)
                if not wav_path:
                    return {"text": "", "language": "unknown", "latency_ms": 0, "confidence": 0.0,
                            "error": f"Audio duration ({duration:.0f}s) exceeds limit ({MAX_AUDIO_DURATION_SECONDS}s) and truncation failed."}

            result = self.model.transcribe(wav_path, task="transcribe", language=None, fp16=False)
            self._cleanup(wav_path)

            latency = round((time.time() - start) * 1000, 1)
            detected_lang = result.get("language", "en")
            lang_map = {"kn": "kn", "hi": "hi", "en": "en", "kannada": "kn", "hindi": "hi", "english": "en"}
            detected_lang = lang_map.get(detected_lang, detected_lang)

            logger.info(f"ASR[whisper]: {latency}ms, lang={detected_lang}, text={result['text'][:80]}...")
            return {
                "text": result["text"].strip(), "language": detected_lang,
                "latency_ms": latency, "confidence": 0.85, "backend": "whisper",
                "segments": result.get("segments", [])[:5]
            }
        except Exception as e:
            logger.error(f"Whisper ASR error: {e}")
            try:
                import speech_recognition as sr
                self.backend = "speech_recognition"
                return await self._transcribe_sr(audio_base64, start, language_hint)
            except ImportError:
                pass
            return {"text": "", "language": "unknown", "latency_ms": 0, "confidence": 0.0, "error": str(e)}

    # ── Script Detection Helpers ─────────────────────────────────────────────
    @staticmethod
    def _detect_script(text: str) -> str:
        """Detect the dominant Unicode script in text.
        Returns: 'latin', 'devanagari', 'kannada', or 'mixed'"""
        if not text:
            return "unknown"

        latin = 0
        devanagari = 0
        kannada = 0
        other = 0

        for ch in text:
            cp = ord(ch)
            if ch.isspace() or ch in '.,!?;:\'"()-/0123456789':
                continue  # skip punctuation/spaces
            elif 0x0041 <= cp <= 0x007A:  # Basic Latin letters
                latin += 1
            elif 0x0900 <= cp <= 0x097F:  # Devanagari
                devanagari += 1
            elif 0x0C80 <= cp <= 0x0CFF:  # Kannada
                kannada += 1
            else:
                other += 1

        total = latin + devanagari + kannada + other
        if total == 0:
            return "unknown"

        # Dominant script wins
        if latin / total > 0.5:
            return "latin"
        if devanagari / total > 0.3:
            return "devanagari"
        if kannada / total > 0.3:
            return "kannada"
        if latin > devanagari and latin > kannada:
            return "latin"
        return "mixed"

    @staticmethod
    def _script_matches_lang(script: str, lang: str) -> bool:
        """Check if detected script is consistent with the claimed language."""
        expected = {
            "en": "latin",
            "hi": "devanagari",
            "kn": "kannada",
        }
        return expected.get(lang) == script

    async def _transcribe_sr(self, audio_base64: str, start: float, language_hint: str = "auto") -> Dict[str, Any]:
        """Transcribe using SpeechRecognition (Google Web Speech API — free).
        
        Strategy for accurate language detection:
        1. If user picked a specific language, ONLY try that language — trust the user.
        2. In 'auto' mode, try all 3 languages independently.
        3. For each result, detect the Unicode script of the returned text.
        4. A result is VALID only if the script matches the requested language 
           (e.g. en-IN must return Latin text, kn-IN must return Kannada script).
        5. If kn-IN returns Latin text, it's a transliteration artifact — discard it.
        6. Among valid results, pick the one with highest confidence.
        """
        try:
            import speech_recognition as sr

            audio_bytes = base64.b64decode(audio_base64)

            # Security: check decoded file size
            if len(audio_bytes) > MAX_AUDIO_SIZE_BYTES:
                return {"text": "", "language": "unknown", "latency_ms": 0, "confidence": 0.0,
                        "error": f"Audio file too large ({len(audio_bytes) // (1024*1024)}MB). Maximum is {MAX_AUDIO_SIZE_BYTES // (1024*1024)}MB."}

            # Convert to WAV (critical — SR only reads WAV/FLAC/AIFF)
            wav_path = self._convert_to_wav(audio_bytes)
            if not wav_path:
                return {"text": "", "language": "unknown", "latency_ms": 0, "confidence": 0.0,
                        "error": "Audio conversion to WAV failed. Make sure ffmpeg is installed."}

            # Security: check audio duration
            duration = self._get_audio_duration(wav_path)
            if duration and duration > MAX_AUDIO_DURATION_SECONDS:
                logger.warning(f"Audio too long ({duration:.1f}s), truncating to {MAX_AUDIO_DURATION_SECONDS}s")
                wav_path = self._truncate_audio(wav_path, MAX_AUDIO_DURATION_SECONDS)
                if not wav_path:
                    return {"text": "", "language": "unknown", "latency_ms": 0, "confidence": 0.0,
                            "error": f"Audio duration ({duration:.0f}s) exceeds limit ({MAX_AUDIO_DURATION_SECONDS}s) and truncation failed."}

            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 200
            recognizer.dynamic_energy_threshold = True

            try:
                with sr.AudioFile(wav_path) as source:
                    audio_data = recognizer.record(source)
            except Exception as e:
                self._cleanup(wav_path)
                logger.error(f"Failed to read converted WAV: {e}")
                return {"text": "", "language": "unknown", "latency_ms": 0, "confidence": 0.0,
                        "error": f"Could not read audio file: {e}"}

            # ── Determine which languages to try ─────────────────────────
            if language_hint and language_hint != "auto":
                # User explicitly chose a language — ONLY try that one
                hint_map = {"en": "en-IN", "hi": "hi-IN", "kn": "kn-IN"}
                api_code = hint_map.get(language_hint, "en-IN")
                langs_to_try = [(api_code, language_hint)]
            else:
                # Auto mode: try all three
                langs_to_try = [("en-IN", "en"), ("hi-IN", "hi"), ("kn-IN", "kn")]

            # ── Collect results from each language ───────────────────────
            candidates = []  # List of (text, lang, confidence, script, script_valid)
            all_transcripts = {}

            for api_lang, our_lang in langs_to_try:
                try:
                    result = recognizer.recognize_google(
                        audio_data, language=api_lang, show_all=True
                    )
                    text = ""
                    conf = 0.0

                    if result and isinstance(result, dict):
                        alternatives = result.get("alternative", [])
                        if alternatives:
                            text = alternatives[0].get("transcript", "").strip()
                            conf = alternatives[0].get("confidence", 0.5)
                    elif isinstance(result, str) and result.strip():
                        text = result.strip()
                        conf = 0.5

                    if text:
                        script = self._detect_script(text)
                        script_valid = self._script_matches_lang(script, our_lang)
                        candidates.append({
                            "text": text,
                            "lang": our_lang,
                            "confidence": conf,
                            "script": script,
                            "script_valid": script_valid,
                        })
                        all_transcripts[our_lang] = text
                        logger.info(
                            f"ASR[google] {api_lang}: conf={conf:.3f}, "
                            f"script={script}, valid={script_valid}, "
                            f"text='{text[:60]}...'"
                        )

                except sr.UnknownValueError:
                    logger.debug(f"ASR[google] {api_lang}: No speech recognized")
                    continue
                except sr.RequestError as e:
                    logger.warning(f"Google SR API error for {api_lang}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"SR error for {api_lang}: {e}")
                    continue

            self._cleanup(wav_path)
            latency = round((time.time() - start) * 1000, 1)

            if not candidates:
                logger.warning(f"ASR[google]: No speech recognized in {latency}ms")
                return {
                    "text": "", "language": "unknown", "latency_ms": latency, "confidence": 0.0,
                    "backend": "google_speech",
                    "error": "No speech detected in audio. Try speaking more clearly or check microphone."
                }

            # ── Pick the best result using script validation ──────────────
            # Priority 1: Script-valid results (text script matches the language we asked for)
            valid_candidates = [c for c in candidates if c["script_valid"]]
            
            if valid_candidates:
                # Among script-valid results, pick highest confidence
                best = max(valid_candidates, key=lambda c: c["confidence"])
            else:
                # No script-valid result — fallback logic
                latin_candidates = [c for c in candidates if c["script"] == "latin"]
                if latin_candidates:
                    best = max(latin_candidates, key=lambda c: c["confidence"])
                    best["lang"] = "en"  # Latin text = English
                else:
                    # Just pick highest confidence as last resort
                    best = max(candidates, key=lambda c: c["confidence"])

            logger.info(
                f"ASR[google] FINAL: lang={best['lang']}, conf={best['confidence']:.3f}, "
                f"script={best['script']}, valid={best['script_valid']}, "
                f"text='{best['text'][:80]}...'"
            )

            return {
                "text": best["text"],
                "language": best["lang"],
                "latency_ms": latency,
                "confidence": round(best["confidence"], 3),
                "backend": "google_speech",
                "alternatives": all_transcripts,
            }

        except Exception as e:
            logger.error(f"SpeechRecognition error: {e}")
            return {"text": "", "language": "unknown", "latency_ms": 0, "confidence": 0.0,
                    "error": f"ASR failed: {str(e)}"}

    def _convert_to_wav(self, audio_bytes: bytes) -> Optional[str]:
        """Convert any audio format to 16kHz mono WAV using ffmpeg or pydub.
        This is the CRITICAL fix — browser MediaRecorder produces webm/opus which
        speech_recognition can't read directly."""

        # Detect input format from magic bytes
        fmt = self._detect_format(audio_bytes)
        logger.info(f"Audio input format detected: {fmt}, size: {len(audio_bytes)} bytes")

        # If already WAV, save directly
        if fmt == "wav":
            try:
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp.write(audio_bytes)
                tmp.close()
                # Still re-encode to ensure proper PCM WAV format
                return self._ffmpeg_convert(tmp.name, fmt="wav")
            except Exception as e:
                logger.error(f"WAV save error: {e}")
                return None

        # Save raw audio to temp file with correct extension
        ext = f".{fmt}" if fmt else ".bin"
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            tmp.write(audio_bytes)
            tmp.close()
            raw_path = tmp.name
        except Exception as e:
            logger.error(f"Temp file creation error: {e}")
            return None

        # Method 1: ffmpeg (most reliable)
        if self._ffmpeg_available:
            result = self._ffmpeg_convert(raw_path, fmt=fmt)
            if result:
                return result

        # Method 2: pydub (uses ffmpeg internally but with python API)
        try:
            from pydub import AudioSegment
            if fmt:
                audio = AudioSegment.from_file(raw_path, format=fmt)
            else:
                audio = AudioSegment.from_file(raw_path)
            audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
            tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_wav.close()
            audio.export(tmp_wav.name, format="wav")
            self._cleanup(raw_path)
            logger.info(f"Audio converted via pydub: {tmp_wav.name}")
            return tmp_wav.name
        except Exception as e:
            logger.warning(f"pydub conversion failed: {e}")

        self._cleanup(raw_path)
        return None

    def _ffmpeg_convert(self, input_path: str, fmt: str = None) -> Optional[str]:
        """Use ffmpeg directly to convert audio to 16kHz mono PCM WAV"""
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            wav_path = tmp.name
        except Exception as e:
            logger.error(f"Temp file creation error: {e}")
            return None
        try:
            cmd = [
                "ffmpeg", "-y",  # Overwrite output
                "-i", input_path,
                "-acodec", "pcm_s16le",  # 16-bit PCM
                "-ar", "16000",           # 16kHz sample rate
                "-ac", "1",               # Mono
                wav_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode == 0 and os.path.exists(wav_path) and os.path.getsize(wav_path) > 100:
                logger.info(f"Audio converted via ffmpeg: {input_path} -> {wav_path}")
                self._cleanup(input_path)
                return wav_path
            else:
                stderr = result.stderr.decode("utf-8", errors="replace")[-500:]
                logger.warning(f"ffmpeg conversion failed (rc={result.returncode}): {stderr}")
                self._cleanup(wav_path)
                return None
        except Exception as e:
            logger.warning(f"ffmpeg error: {e}")
            self._cleanup(wav_path)
            return None

    def _get_audio_duration(self, wav_path: str) -> Optional[float]:
        """Get audio duration in seconds using ffprobe or wave module"""
        # Try wave module first (fastest for WAV files)
        try:
            import wave
            with wave.open(wav_path, 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    return frames / float(rate)
        except Exception:
            pass

        # Fallback to ffprobe
        if self._ffmpeg_available:
            try:
                cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                       "-of", "default=noprint_wrappers=1:nokey=1", wav_path]
                result = subprocess.run(cmd, capture_output=True, timeout=10, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    return float(result.stdout.strip())
            except Exception:
                pass

        return None

    def _truncate_audio(self, wav_path: str, max_seconds: float) -> Optional[str]:
        """Truncate audio to max_seconds using ffmpeg"""
        if not self._ffmpeg_available:
            return None
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            out_path = tmp.name
            cmd = [
                "ffmpeg", "-y", "-i", wav_path,
                "-t", str(max_seconds),
                "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                out_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode == 0 and os.path.exists(out_path):
                self._cleanup(wav_path)
                return out_path
            else:
                self._cleanup(out_path)
                return None
        except Exception as e:
            logger.warning(f"Audio truncation failed: {e}")
            return None

    def _detect_format(self, audio_bytes: bytes) -> str:
        """Detect audio format from magic bytes"""
        if len(audio_bytes) < 12:
            return "unknown"
        header = audio_bytes[:12]
        if header[:4] == b'RIFF' and header[8:12] == b'WAVE':
            return "wav"
        if header[:4] == b'\x1aE\xdf\xa3':  # EBML header (WebM/MKV)
            return "webm"
        if header[:3] == b'ID3' or header[:2] == b'\xff\xfb' or header[:2] == b'\xff\xf3':
            return "mp3"
        if header[:4] == b'OggS':
            return "ogg"
        if header[:4] == b'fLaC':
            return "flac"
        if header[:4] == b'FORM':  # AIFF
            return "aiff"
        if header[4:8] == b'ftyp':  # MP4/M4A
            return "mp4"
        return "webm"  # Default to webm since that's what browsers produce

    def _cleanup(self, *paths):
        """Clean up temp files"""
        for p in paths:
            try:
                if p and os.path.exists(p):
                    os.unlink(p)
            except Exception:
                pass

    def is_ready(self) -> bool:
        return self._ready
