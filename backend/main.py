"""
VaakSetu — Core Backend (FastAPI)
Real-time AI middleware for 1092 Helpline
"""
import os, json, asyncio, logging, uuid as _uuid
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from keywords import KeywordEngine
from utcs import UTCSEngine
from asr import ASREngine
from nlp import NLPEngine
from emotion import EmotionEngine
from noise import NoiseEngine
from tts import TTSEngine
from verification import VerificationEngine
from database import DatabaseEngine
from websocket_manager import WebSocketManager
from twilio_handler import TwilioHandler
from learning import LearningPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s|%(name)s|%(levelname)s|%(message)s")
logger = logging.getLogger("vaaksetu")

keyword_engine = KeywordEngine()
utcs_engine = UTCSEngine()
asr_engine = ASREngine()
nlp_engine = NLPEngine()
emotion_engine = EmotionEngine()
noise_engine = NoiseEngine()
tts_engine = TTSEngine()
verification_engine = VerificationEngine()
db_engine = DatabaseEngine()
ws_manager = WebSocketManager()
twilio_handler = TwilioHandler()
learning_pipeline = LearningPipeline()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("VaakSetu starting...")
    db_engine.init_db()
    # Start WebSocket heartbeat task
    heartbeat_task = asyncio.create_task(ws_manager.heartbeat_loop())
    yield
    heartbeat_task.cancel()
    logger.info("VaakSetu shutting down...")

app = FastAPI(
    title="VaakSetu",
    version="2.0.0",
    lifespan=lifespan,
    debug=os.getenv("DEBUG", "false").lower() == "true",
)

# Restrict CORS to known origins and Vercel preview domains
allowed_origins = [
    "https://vaak-setu-self.vercel.app",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request ID middleware for traceability ──────────────────────────────────
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", _uuid.uuid4().hex[:12])
    logger.info(f"[req:{request_id}] {request.method} {request.url.path}")
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Serve TTS audio files
from fastapi.staticfiles import StaticFiles
audio_cache_dir = os.path.join(os.path.dirname(__file__), "audio_cache")
os.makedirs(audio_cache_dir, exist_ok=True)
app.mount("/audio", StaticFiles(directory=audio_cache_dir), name="audio")

class CallStartRequest(BaseModel):
    caller_number: str
    agent_id: Optional[str] = "AGENT-001"
    language_hint: Optional[str] = None

class TranscriptionRequest(BaseModel):
    call_id: str
    audio_base64: Optional[str] = None
    text: Optional[str] = None
    language: Optional[str] = "auto"

class VerificationResponse(BaseModel):
    call_id: str
    confirmed: bool
    partial_corrections: Optional[str] = None

class FeedbackRequest(BaseModel):
    call_id: str
    agent_id: str
    original_interpretation: str
    corrected_interpretation: str
    correction_type: str

class AIInterpretationEdit(BaseModel):
    call_id: str
    field: str
    old_value: str
    new_value: str
    agent_id: Optional[str] = "AGENT-001"

@app.get("/")
async def root():
    return {"service":"VaakSetu","version":"2.0.0","status":"operational"}

@app.get("/api/test_reload")
async def test_reload():
    return {"status": "reloaded successfully"}

@app.get("/health")
async def health_check():
    return {"status":"healthy","timestamp":datetime.utcnow().isoformat(),
        "engines":{k:v.is_ready() for k,v in {"asr":asr_engine,"nlp":nlp_engine,"keywords":keyword_engine,"utcs":utcs_engine,"emotion":emotion_engine,"noise":noise_engine,"tts":tts_engine,"database":db_engine}.items()},
        "websocket_connections": ws_manager.connection_count}

@app.post("/api/calls/start")
async def start_call(request: CallStartRequest):
    try:
        call = db_engine.create_call(caller_number=request.caller_number, agent_id=request.agent_id, language_hint=request.language_hint)
        await ws_manager.broadcast({"type":"new_call","call":call,"timestamp":datetime.utcnow().isoformat()})
        return call
    except Exception as e:
        logger.error(f"start_call error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/calls")
async def list_calls(status: Optional[str] = None, limit: int = 50):
    calls = db_engine.get_calls(status=status, limit=limit)
    return {"calls": calls, "total": len(calls)}

@app.get("/api/calls/{call_id}")
async def get_call(call_id: str):
    call = db_engine.get_call(call_id)
    if not call: raise HTTPException(404, "Call not found")
    return call

@app.post("/api/calls/{call_id}/end")
async def end_call(call_id: str):
    result = db_engine.end_call(call_id)
    await ws_manager.broadcast({"type":"call_ended","call_id":call_id,"timestamp":datetime.utcnow().isoformat()})
    return result

@app.post("/api/process")
async def process_audio(request: TranscriptionRequest):
    """Main processing pipeline: ASR→Keywords→NLP→Verification→Emotion→UTCS→Broadcast"""
    call_id = request.call_id
    is_text_input = bool(request.text and request.text.strip())
    asr_error = None
    asr_backend = None

    # Load call session to check cached language
    cached_language = None
    try:
        call_session = db_engine.get_call(call_id)
        if call_session and call_session.get("language") and call_session.get("language") != "auto":
            cached_language = call_session["language"]
            logger.info(f"[{call_id}] Using cached session language: '{cached_language}'")
    except Exception as e:
        logger.warning(f"Failed to fetch call session for language caching: {e}")

    # Step 1: Get transcript text
    if is_text_input:
        transcript_text = request.text.strip()
        detected_language = request.language or "auto"
        asr_latency = 0
        asr_backend = "text_input"
        logger.info(f"[{call_id}] TEXT INPUT: '{transcript_text[:80]}...'")
    else:
        req_lang = cached_language or request.language or "auto"
        r = await asr_engine.transcribe(request.audio_base64, req_lang)
        transcript_text = r.get("text", "").strip()
        detected_language = r.get("language", "unknown")
        asr_latency = r.get("latency_ms", 0)
        asr_backend = r.get("backend", "unknown")
        asr_error = r.get("error", None)
        
        if not transcript_text:
            logger.warning(f"[{call_id}] ASR FAILED: {asr_error or 'Empty transcript'}")
            # Return an informative error result instead of processing empty text
            error_result = {
                "call_id": call_id,
                "timestamp": datetime.utcnow().isoformat(),
                "transcript": {
                    "text": "",
                    "language": detected_language,
                    "asr_latency_ms": asr_latency,
                    "input_mode": "audio",
                    "backend": asr_backend,
                    "error": asr_error or "No speech detected — try speaking louder or use text input",
                },
                "keywords": {"total_hits": 0, "tier_counts": {1: 0, 2: 0, 3: 0}, "hits": [], "highest_tier": None, "severity": "NONE"},
                "nlp": {"intent": {"category": "unknown", "subcategory": "asr_failure", "confidence": 0}, "summary": "ASR failed to transcribe audio", "urgency": "low"},
                "emotion": {"panic": 0.0, "fear": 0.0, "calm": 0.5, "distress": 0.0, "source": "none"},
                "utcs": {"score": 0, "level": "MINIMAL", "color": "#00AAFF", "action": "ROUTINE", "breakdown": {}},
                "verification_required": False,
                "asr_error": asr_error or "No speech detected",
            }
            db_engine.save_transcript(call_id, error_result)
            await ws_manager.broadcast({"type": "processing_result", "data": error_result})
            return error_result
        
        logger.info(f"[{call_id}] ASR[{asr_backend}]: '{transcript_text[:80]}...', lang={detected_language}")

    # Run Keywords, NLP, and Emotion analysis concurrently to minimize pipeline latency
    keyword_task = asyncio.to_thread(keyword_engine.scan, transcript_text)
    nlp_task = nlp_engine.process(transcript_text, detected_language, dialect_zone="general")
    
    if request.audio_base64 and not is_text_input:
        emotion_task = asyncio.to_thread(emotion_engine.analyze, request.audio_base64)
    else:
        emotion_task = None

    if emotion_task:
        keyword_result, nlp_result, emotion_result = await asyncio.gather(keyword_task, nlp_task, emotion_task)
    else:
        keyword_result, nlp_result = await asyncio.gather(keyword_task, nlp_task)
        emotion_result = _estimate_emotion_from_text(keyword_result, nlp_result, transcript_text)

    # Sync dialect_zone from keywords result into NLP result
    nlp_result["dialect_zone"] = keyword_result.get("dialect_zone", "general")
    
    logger.info(f"[{call_id}] KEYWORDS: {keyword_result['total_hits']} hits, severity={keyword_result['severity']}")
    logger.info(f"[{call_id}] NLP: intent={nlp_result.get('intent', {}).get('category')}, urgency={nlp_result.get('urgency')}, dialect={nlp_result['dialect_zone']}")
    logger.info(f"[{call_id}] EMOTION: panic={emotion_result.get('panic')}, fear={emotion_result.get('fear')}")

    # Step 3.5: Wire verification — store NLP summary for later confirmation
    verification_engine.set_summary(call_id, nlp_result.get('summary', ''), detected_language)

    # Step 5: UTCS calculation
    utcs_result = utcs_engine.calculate(
        keyword_hits=keyword_result,
        nlp_result=nlp_result,
        emotion_scores=emotion_result,
        noise_analysis=None
    )
    logger.info(f"[{call_id}] UTCS: score={utcs_result['score']}, level={utcs_result['level']}")

    # Build result
    result = {
        "call_id": call_id,
        "timestamp": datetime.utcnow().isoformat(),
        "transcript": {
            "text": transcript_text,
            "language": detected_language,
            "asr_latency_ms": asr_latency,
            "input_mode": "text" if is_text_input else "audio",
            "backend": asr_backend,
        },
        "keywords": keyword_result,
        "nlp": nlp_result,
        "emotion": emotion_result,
        "utcs": utcs_result,
        "verification_required": utcs_result["score"] < 400,
    }

    # Save to database
    db_engine.save_transcript(call_id, result)

    # Broadcast via WebSocket
    await ws_manager.broadcast({"type": "processing_result", "data": result})

    # Critical alert
    if utcs_result["level"] == "CRITICAL":
        await ws_manager.broadcast({
            "type": "alert", "severity": "critical", "call_id": call_id,
            "message": f"CRITICAL THREAT — UTCS: {utcs_result['score']}",
            "utcs": utcs_result, "timestamp": datetime.utcnow().isoformat()
        })

    return result


def _estimate_emotion_from_text(keyword_result: dict, nlp_result: dict, text: str) -> dict:
    """Estimate emotion scores from text analysis when no audio is available.
    Uses keyword severity and NLP sentiment to approximate emotional state."""
    
    severity = keyword_result.get("severity", "NONE")
    tier_counts = keyword_result.get("tier_counts", {1: 0, 2: 0, 3: 0})
    urgency = nlp_result.get("urgency", "low")
    sentiment = nlp_result.get("sentiment", {})
    neg = sentiment.get("negative", 0.2) if isinstance(sentiment, dict) else 0.3
    
    # Base scores from keyword severity
    if severity == "CRITICAL":
        panic = min(1.0, 0.6 + tier_counts.get(1, 0) * 0.15)
        fear = min(1.0, 0.5 + tier_counts.get(1, 0) * 0.1)
        distress = min(1.0, 0.4 + tier_counts.get(2, 0) * 0.1)
    elif severity == "HIGH":
        panic = 0.35
        fear = min(1.0, 0.4 + tier_counts.get(2, 0) * 0.1)
        distress = min(1.0, 0.5 + tier_counts.get(2, 0) * 0.1)
    elif severity == "MEDIUM":
        panic = 0.15
        fear = 0.25
        distress = 0.35
    elif severity == "LOW":
        panic = 0.05
        fear = 0.1
        distress = 0.15
    else:
        panic = 0.0
        fear = 0.0
        distress = 0.05

    # Boost from NLP urgency
    if urgency == "critical":
        panic = min(1.0, panic + 0.2)
        fear = min(1.0, fear + 0.15)
    elif urgency == "high":
        panic = min(1.0, panic + 0.1)
        fear = min(1.0, fear + 0.1)
    
    # Boost from sentiment negativity
    panic = min(1.0, panic + neg * 0.15)
    fear = min(1.0, fear + neg * 0.1)
    
    calm = max(0.0, 1.0 - (panic + fear + distress) / 2.5)

    return {
        "panic": round(panic, 3),
        "fear": round(fear, 3),
        "distress": round(distress, 3),
        "calm": round(calm, 3),
        "source": "text_estimation"
    }


@app.post("/api/process/noise")
async def process_background_noise(call_id: str = Form(...), audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    noise_result = await asyncio.to_thread(noise_engine.analyze, audio_bytes)
    utcs_update = utcs_engine.update_with_noise(call_id, noise_result)
    await ws_manager.broadcast({"type":"noise_analysis","call_id":call_id,"data":noise_result,"utcs_update":utcs_update,"timestamp":datetime.utcnow().isoformat()})
    return {"call_id":call_id,"noise_analysis":noise_result}

@app.post("/api/process/audio-file")
async def process_audio_file(call_id: str = Form(...), audio: UploadFile = File(...)):
    """Process an uploaded audio file through the full pipeline (ASR→KW→NLP→Emotion→UTCS)"""
    import base64
    audio_bytes = await audio.read()
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    request = TranscriptionRequest(call_id=call_id, audio_base64=audio_b64, language="auto")
    return await process_audio(request)

@app.post("/api/verify")
async def verify_understanding(request: VerificationResponse):
    result = verification_engine.process_response(call_id=request.call_id, confirmed=request.confirmed, corrections=request.partial_corrections)
    db_engine.save_verification(request.call_id, result)
    await ws_manager.broadcast({"type":"verification_result","call_id":request.call_id,"data":result,"timestamp":datetime.utcnow().isoformat()})
    if request.confirmed:
        summary = result.get("confirmed_summary","")
        if summary:
            tts_result = await asyncio.to_thread(tts_engine.synthesize, summary, result.get("language","en"))
            result["tts_audio_url"] = tts_result.get("audio_url")
    return result

@app.post("/api/interpretation/edit")
async def edit_interpretation(edit: AIInterpretationEdit):
    result = db_engine.save_interpretation_edit(call_id=edit.call_id, field=edit.field, old_value=edit.old_value, new_value=edit.new_value, agent_id=edit.agent_id)
    await ws_manager.broadcast({"type":"interpretation_edited","call_id":edit.call_id,"data":{"field":edit.field,"new_value":edit.new_value,"agent_id":edit.agent_id},"timestamp":datetime.utcnow().isoformat()})
    return result

@app.post("/api/calls/{call_id}/takeover")
async def human_takeover(call_id: str, agent_id: str = "AGENT-001"):
    result = db_engine.flag_takeover(call_id, agent_id)
    await ws_manager.broadcast({"type":"human_takeover","call_id":call_id,"agent_id":agent_id,"timestamp":datetime.utcnow().isoformat()})
    return result

@app.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest):
    return db_engine.save_feedback(call_id=request.call_id, agent_id=request.agent_id, original=request.original_interpretation, corrected=request.corrected_interpretation, correction_type=request.correction_type)

@app.get("/api/learning/stats")
async def learning_stats():
    return learning_pipeline.get_stats()

@app.get("/api/learning/signals")
async def learning_signals(correction_type: Optional[str] = None):
    return learning_pipeline.get_training_signals(correction_type=correction_type)

@app.get("/api/dashboard/stats")
async def dashboard_stats():
    return db_engine.get_dashboard_stats()

@app.get("/api/dashboard/events")
async def dashboard_events(limit: int = 100):
    return db_engine.get_events(limit=limit)

# ── Analytics Endpoint ───────────────────────────────────────────────────────
@app.get("/api/analytics/summary")
async def analytics_summary():
    """Aggregate analytics from call database"""
    calls = db_engine.get_calls(limit=500)
    utcs_dist = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "MINIMAL": 0}
    lang_dist = {}
    threat_dist = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "NONE": 0}
    volume_by_hour = {}
    total_calls = len(calls)
    total_threats = 0
    total_utcs = 0
    for c in calls:
        level = c.get("utcs_level", "MINIMAL")
        if level in utcs_dist:
            utcs_dist[level] += 1
        lang = c.get("language", "unknown") or "unknown"
        lang_dist[lang] = lang_dist.get(lang, 0) + 1
        sev = c.get("keyword_severity", "NONE") or "NONE"
        if sev in threat_dist:
            threat_dist[sev] += 1
        if sev in ("CRITICAL", "HIGH"):
            total_threats += 1
        total_utcs += c.get("utcs_score", 0) or 0
        ts = c.get("created_at", "") or ""
        if ts:
            hour = ts[:13]
            volume_by_hour[hour] = volume_by_hour.get(hour, 0) + 1
    return {
        "total_calls": total_calls,
        "total_threats": total_threats,
        "avg_utcs": round(total_utcs / max(1, total_calls), 1),
        "utcs_distribution": utcs_dist,
        "language_distribution": lang_dist,
        "threat_distribution": threat_dist,
        "volume_by_hour": dict(sorted(volume_by_hour.items())),
    }

# ── Database Viewer API ──────────────────────────────────────────────────────
@app.get("/api/db/tables")
async def db_tables():
    """List all database tables and their row counts"""
    return db_engine.get_table_info()

@app.get("/api/db/table/{table_name}")
async def db_table_rows(table_name: str, limit: int = 50, offset: int = 0):
    """Get rows from a specific table"""
    return db_engine.get_table_rows(table_name, limit=limit, offset=offset)

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type")=="ping":
                await websocket.send_json({"type":"pong","timestamp":datetime.utcnow().isoformat()})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

@app.post("/api/demo/scenario/{scenario_id}")
async def run_demo_scenario(scenario_id: int):
    scenarios = {
        1:{"name":"The Language Bridge","caller":"+919876543210","text":"ನಮಸ್ಕಾರ ಸಾರ್, ನಾನು ರಾಜಾಜಿನಗರದಲ್ಲಿ ಇದ್ದೀನಿ. ನಮ್ಮ ಏರಿಯಾದಲ್ಲಿ ರಸ್ತೆಯಲ್ಲಿ ದೊಡ್ಡ ಗುಂಡಿ ಬಿದ್ದಿದೆ.","lang":"kn"},
        2:{"name":"Keyword Emergency","caller":"+919876543211","text":"bachao bachao, wo mujhe maar raha hai! Please help karo, bahut darr lag raha hai.","lang":"hi"},
        3:{"name":"The Silent Emergency","caller":"+919876543212","text":"...help...","lang":"en","noise":True},
    }
    if scenario_id not in scenarios: raise HTTPException(400,"Invalid scenario")
    s = scenarios[scenario_id]
    call = db_engine.create_call(caller_number=s["caller"], agent_id="DEMO-AGENT", language_hint=s["lang"])
    result = await process_audio(TranscriptionRequest(call_id=call["call_id"], text=s["text"], language=s["lang"]))
    if s.get("noise"):
        nr = noise_engine.simulate_distress()
        result["noise_analysis"] = nr
        result["utcs"] = utcs_engine.update_with_noise(call["call_id"], nr)
        await ws_manager.broadcast({"type":"noise_analysis","call_id":call["call_id"],"data":nr,"timestamp":datetime.utcnow().isoformat()})
    return {"scenario":s["name"],"result":result}

from fastapi.responses import Response as XMLResponse
@app.post("/api/twilio/voice")
async def twilio_voice_webhook():
    result = twilio_handler.handle_incoming()
    twiml = result.get('twiml', '') if isinstance(result, dict) else str(result)
    return XMLResponse(content=twiml, media_type='application/xml')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=os.getenv("HOST","0.0.0.0"), port=int(os.getenv("PORT",8000)), reload=True)
