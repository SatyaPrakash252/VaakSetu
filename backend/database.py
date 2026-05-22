"""
VaakSetu — Database Engine (SQLite with real persistence)
Call sessions, transcripts, feedback, event log
All data persists to vaaksetu.db file
"""
import os, json, uuid, logging, sqlite3
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger("vaaksetu.database")

DB_PATH = os.path.join(os.path.dirname(__file__), "vaaksetu.db")


class DatabaseEngine:
    def __init__(self):
        self._ready = True
        self._db_path = DB_PATH
        logger.info(f"DatabaseEngine initialized — SQLite at: {self._db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_db(self):
        """Create all tables and seed demo data if empty"""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT UNIQUE NOT NULL,
                    caller_number TEXT NOT NULL,
                    agent_id TEXT DEFAULT 'AGENT-001',
                    language TEXT,
                    status TEXT DEFAULT 'active',
                    utcs_score REAL DEFAULT 0.0,
                    utcs_level TEXT DEFAULT 'MINIMAL',
                    summary TEXT,
                    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    ended_at DATETIME,
                    takeover_agent TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT NOT NULL REFERENCES calls(call_id),
                    text TEXT NOT NULL,
                    language TEXT,
                    asr_latency_ms REAL DEFAULT 0,
                    input_mode TEXT DEFAULT 'audio',
                    keywords_json TEXT,
                    nlp_json TEXT,
                    emotion_json TEXT,
                    utcs_json TEXT,
                    noise_json TEXT,
                    keyword_hits INTEGER DEFAULT 0,
                    keyword_severity TEXT DEFAULT 'NONE',
                    utcs_score REAL DEFAULT 0.0,
                    utcs_level TEXT DEFAULT 'MINIMAL',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS verification_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT NOT NULL REFERENCES calls(call_id),
                    status TEXT,
                    summary_text TEXT,
                    corrections TEXT,
                    attempts INTEGER DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS feedback_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT NOT NULL REFERENCES calls(call_id),
                    agent_id TEXT NOT NULL,
                    original_interpretation TEXT,
                    corrected_interpretation TEXT,
                    correction_type TEXT,
                    applied_to_model BOOLEAN DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS event_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    call_id TEXT,
                    message TEXT,
                    severity TEXT DEFAULT 'info',
                    metadata_json TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_calls_status ON calls(status);
                CREATE INDEX IF NOT EXISTS idx_calls_utcs ON calls(utcs_level);
                CREATE INDEX IF NOT EXISTS idx_transcripts_call ON transcripts(call_id);
                CREATE INDEX IF NOT EXISTS idx_events_type ON event_logs(event_type);
            """)
            
            # Seed demo data if calls table is empty
            count = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            if count == 0:
                self._seed_demo_data(conn)
            
            conn.commit()
            logger.info(f"Database ready — {conn.execute('SELECT COUNT(*) FROM calls').fetchone()[0]} calls in DB")
        finally:
            conn.close()

    def _seed_demo_data(self, conn):
        """Pre-seed 3 demo calls so dashboard is never empty"""
        seeds = [
            {"id": "CALL-001", "caller": "+919876543210", "agent": "AGENT-001", "lang": "kn",
             "status": "completed", "utcs_score": 145, "utcs_level": "LOW",
             "summary": "Road pothole complaint in Rajajinagar — 3 days unattended",
             "started": "2026-05-04T10:15:00", "ended": "2026-05-04T10:18:30"},
            {"id": "CALL-002", "caller": "+919876543211", "agent": "AGENT-002", "lang": "hi",
             "status": "completed", "utcs_score": 720, "utcs_level": "CRITICAL",
             "summary": "Domestic violence emergency — citizen in immediate danger",
             "started": "2026-05-04T11:30:00", "ended": "2026-05-04T11:35:00"},
            {"id": "CALL-003", "caller": "+919876543212", "agent": "AGENT-001", "lang": "en",
             "status": "completed", "utcs_score": 580, "utcs_level": "CRITICAL",
             "summary": "Silent emergency — background screaming detected by noise analysis",
             "started": "2026-05-04T14:00:00", "ended": "2026-05-04T14:08:00"},
        ]
        for s in seeds:
            conn.execute(
                """INSERT INTO calls (call_id, caller_number, agent_id, language, status,
                   utcs_score, utcs_level, summary, started_at, ended_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (s["id"], s["caller"], s["agent"], s["lang"], s["status"],
                 s["utcs_score"], s["utcs_level"], s["summary"], s["started"], s.get("ended"))
            )
            conn.execute(
                """INSERT INTO event_logs (event_type, call_id, message, severity, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                ("call_completed", s["id"], f"Call {s['id']}: {s['summary'][:60]}",
                 s["utcs_level"].lower(), s["started"])
            )
        logger.info("Database seeded with 3 demo calls")

    def create_call(self, caller_number: str, agent_id: str = "AGENT-001",
                    language_hint: Optional[str] = None) -> Dict:
        call_id = f"CALL-{uuid.uuid4().hex[:6].upper()}"
        now = datetime.utcnow().isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO calls (call_id, caller_number, agent_id, language, status,
                   utcs_score, utcs_level, started_at)
                   VALUES (?, ?, ?, ?, 'active', 0.0, 'MINIMAL', ?)""",
                (call_id, caller_number, agent_id, language_hint, now)
            )
            conn.execute(
                """INSERT INTO event_logs (event_type, call_id, message, severity, timestamp)
                   VALUES ('new_call', ?, ?, 'info', ?)""",
                (call_id, f"New call from {caller_number}", now)
            )
            conn.commit()
            logger.info(f"Created call {call_id} from {caller_number}")
        finally:
            conn.close()

        return {
            "call_id": call_id, "caller_number": caller_number, "agent_id": agent_id,
            "language": language_hint, "status": "active",
            "started_at": now, "ended_at": None,
            "utcs": {"score": 0, "level": "MINIMAL"}, "summary": None,
        }

    def get_calls(self, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        conn = self._get_conn()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM calls WHERE status = ? ORDER BY started_at DESC LIMIT ?",
                    (status, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM calls ORDER BY started_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [self._row_to_call(r) for r in rows]
        finally:
            conn.close()

    def get_call(self, call_id: str) -> Optional[Dict]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM calls WHERE call_id = ?", (call_id,)).fetchone()
            if not row:
                return None
            call = self._row_to_call(row)
            # Attach transcripts
            t_rows = conn.execute(
                "SELECT * FROM transcripts WHERE call_id = ? ORDER BY timestamp", (call_id,)
            ).fetchall()
            call["transcripts"] = [dict(r) for r in t_rows]
            # Attach verifications
            v_rows = conn.execute(
                "SELECT * FROM verification_logs WHERE call_id = ? ORDER BY timestamp", (call_id,)
            ).fetchall()
            call["verifications"] = [dict(r) for r in v_rows]
            return call
        finally:
            conn.close()

    def _row_to_call(self, row) -> Dict:
        return {
            "call_id": row["call_id"],
            "caller_number": row["caller_number"],
            "agent_id": row["agent_id"],
            "language": row["language"],
            "status": row["status"],
            "utcs": {"score": row["utcs_score"], "level": row["utcs_level"]},
            "summary": row["summary"],
            "started_at": row["started_at"],
            "ended_at": row["ended_at"],
        }

    def end_call(self, call_id: str) -> Dict:
        now = datetime.utcnow().isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE calls SET status = 'completed', ended_at = ? WHERE call_id = ?",
                (now, call_id)
            )
            conn.commit()
        finally:
            conn.close()
        return {"call_id": call_id, "status": "completed"}

    def save_transcript(self, call_id: str, result: Dict):
        conn = self._get_conn()
        try:
            transcript = result.get("transcript", {})
            keywords = result.get("keywords", {})
            nlp = result.get("nlp", {})
            emotion = result.get("emotion", {})
            utcs = result.get("utcs", {})

            conn.execute(
                """INSERT INTO transcripts 
                   (call_id, text, language, asr_latency_ms, input_mode,
                    keywords_json, nlp_json, emotion_json, utcs_json,
                    keyword_hits, keyword_severity, utcs_score, utcs_level)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (call_id,
                 transcript.get("text", ""),
                 transcript.get("language", ""),
                 transcript.get("asr_latency_ms", 0),
                 transcript.get("input_mode", "audio"),
                 json.dumps(keywords),
                 json.dumps(nlp),
                 json.dumps(emotion),
                 json.dumps(utcs),
                 keywords.get("total_hits", 0),
                 keywords.get("severity", "NONE"),
                 utcs.get("score", 0),
                 utcs.get("level", "MINIMAL"))
            )

            # Update call UTCS and cache language (if not already set or set to 'auto')
            detected_language = transcript.get("language")
            if detected_language and detected_language not in ("unknown", "auto"):
                conn.execute(
                    """UPDATE calls 
                       SET utcs_score = ?, utcs_level = ?, summary = ?,
                           language = CASE WHEN language IS NULL OR language = 'auto' THEN ? ELSE language END
                       WHERE call_id = ?""",
                    (utcs.get("score", 0), utcs.get("level", "MINIMAL"),
                     nlp.get("summary"), detected_language, call_id)
                )
            else:
                conn.execute(
                    """UPDATE calls SET utcs_score = ?, utcs_level = ?, summary = ?
                       WHERE call_id = ?""",
                    (utcs.get("score", 0), utcs.get("level", "MINIMAL"),
                     nlp.get("summary"), call_id)
                )

            conn.commit()
            logger.info(f"Saved transcript for {call_id}: {keywords.get('total_hits', 0)} keyword hits, UTCS={utcs.get('score', 0)}")
        finally:
            conn.close()

    def save_verification(self, call_id: str, result: Dict):
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO verification_logs (call_id, status, summary_text, corrections, attempts)
                   VALUES (?, ?, ?, ?, ?)""",
                (call_id, result.get("status"), result.get("confirmed_summary"),
                 result.get("corrections"), result.get("attempts", 0))
            )
            conn.commit()
        finally:
            conn.close()

    def save_interpretation_edit(self, call_id: str, field: str, old_value: str,
                                  new_value: str, agent_id: str) -> Dict:
        now = datetime.utcnow().isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO event_logs (event_type, call_id, message, severity, metadata_json, timestamp)
                   VALUES ('interpretation_edit', ?, ?, 'info', ?, ?)""",
                (call_id, f"Agent edited {field}",
                 json.dumps({"field": field, "old": old_value, "new": new_value, "agent": agent_id}), now)
            )
            conn.commit()
        finally:
            conn.close()
        return {"call_id": call_id, "field": field, "old_value": old_value,
                "new_value": new_value, "agent_id": agent_id, "timestamp": now}

    def flag_takeover(self, call_id: str, agent_id: str) -> Dict:
        now = datetime.utcnow().isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE calls SET status = 'takeover', takeover_agent = ? WHERE call_id = ?",
                (agent_id, call_id)
            )
            conn.execute(
                """INSERT INTO event_logs (event_type, call_id, message, severity, timestamp)
                   VALUES ('human_takeover', ?, ?, 'critical', ?)""",
                (call_id, f"HUMAN TAKEOVER by {agent_id}", now)
            )
            conn.commit()
        finally:
            conn.close()
        return {"call_id": call_id, "status": "takeover", "agent_id": agent_id}

    def save_feedback(self, call_id: str, agent_id: str, original: str,
                      corrected: str, correction_type: str) -> Dict:
        now = datetime.utcnow().isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO feedback_entries 
                   (call_id, agent_id, original_interpretation, corrected_interpretation, correction_type)
                   VALUES (?, ?, ?, ?, ?)""",
                (call_id, agent_id, original, corrected, correction_type)
            )
            conn.commit()
        finally:
            conn.close()
        return {"call_id": call_id, "agent_id": agent_id, "original": original,
                "corrected": corrected, "type": correction_type, "timestamp": now}

    def get_feedback_stats(self) -> Dict:
        conn = self._get_conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM feedback_entries").fetchone()[0]
            rows = conn.execute(
                "SELECT correction_type, COUNT(*) as cnt FROM feedback_entries GROUP BY correction_type"
            ).fetchall()
            by_type = {r["correction_type"]: r["cnt"] for r in rows}
            return {"total_corrections": total, "by_type": by_type}
        finally:
            conn.close()

    def get_dashboard_stats(self) -> Dict:
        conn = self._get_conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM calls WHERE status = 'active'").fetchone()[0]
            critical = conn.execute("SELECT COUNT(*) FROM calls WHERE utcs_level = 'CRITICAL'").fetchone()[0]
            feedback = conn.execute("SELECT COUNT(*) FROM feedback_entries").fetchone()[0]
            events = conn.execute("SELECT COUNT(*) FROM event_logs").fetchone()[0]
            return {
                "total_calls": total, "active_calls": active,
                "critical_calls": critical, "total_feedback": feedback,
                "total_events": events,
            }
        finally:
            conn.close()

    def get_events(self, limit: int = 100) -> List[Dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM event_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Database Viewer Methods ──────────────────────────────────────────────
    def get_table_info(self) -> Dict:
        """Get all tables and their row counts"""
        conn = self._get_conn()
        try:
            tables_raw = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            tables = []
            for t in tables_raw:
                name = t["name"]
                count = conn.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
                # Get column info
                cols = conn.execute(f"PRAGMA table_info([{name}])").fetchall()
                columns = [{"name": c["name"], "type": c["type"], "nullable": not c["notnull"]} for c in cols]
                tables.append({
                    "name": name,
                    "row_count": count,
                    "columns": columns
                })
            return {"tables": tables, "db_path": self._db_path, "db_size_kb": round(os.path.getsize(self._db_path) / 1024, 1) if os.path.exists(self._db_path) else 0}
        finally:
            conn.close()

    def get_table_rows(self, table_name: str, limit: int = 50, offset: int = 0) -> Dict:
        """Get rows from a specific table"""
        allowed_tables = ["calls", "transcripts", "verification_logs", "feedback_entries", "event_logs", "sqlite_sequence"]
        if table_name not in allowed_tables:
            return {"error": f"Table '{table_name}' not found. Available: {allowed_tables}"}
        
        conn = self._get_conn()
        try:
            # Check if 'id' column exists to determine if we can sort by it
            cols = conn.execute(f"PRAGMA table_info([{table_name}])").fetchall()
            has_id = any(c["name"] == "id" for c in cols)
            order_by = "ORDER BY id DESC" if has_id else ""
            
            total = conn.execute(f"SELECT COUNT(*) FROM [{table_name}]").fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM [{table_name}] {order_by} LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            return {
                "table": table_name,
                "total": total,
                "limit": limit,
                "offset": offset,
                "rows": [dict(r) for r in rows]
            }
        finally:
            conn.close()

    def is_ready(self) -> bool:
        return self._ready
