"""SQLite persistence for Aarogya caller memory."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "aarogya.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("""
        CREATE TABLE IF NOT EXISTS callers (
            user_id           TEXT PRIMARY KEY,
            name              TEXT,
            language_pref     TEXT,
            age_band          TEXT,
            conditions        TEXT,
            last_triage       TEXT,
            last_interaction  TEXT,
            phone             TEXT,
            follow_up_needed  INTEGER DEFAULT 0,
            followed_up_at    TEXT
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS escalations (
            ref_id        TEXT PRIMARY KEY,
            user_id       TEXT,
            caller_name   TEXT,
            reason        TEXT,
            summary       TEXT,
            urgency       TEXT,
            language      TEXT,
            agent_checked TEXT,
            status        TEXT DEFAULT 'open',
            created_at    TEXT
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            call_id      TEXT PRIMARY KEY,
            user_id      TEXT,
            started_at   TEXT,
            ended_at     TEXT,
            duration_sec INTEGER,
            outcome      TEXT,
            failure_type TEXT
        )
    """)
    for col, typedef in [
        ("phone", "TEXT"),
        ("follow_up_needed", "INTEGER DEFAULT 0"),
        ("followed_up_at", "TEXT"),
    ]:
        try:
            con.execute(f"ALTER TABLE callers ADD COLUMN {col} {typedef}")
        except Exception:
            pass
    con.commit()
    return con


def get_user(user_id: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM callers WHERE user_id = ?", (user_id,)
        ).fetchone()
    if row is None:
        return None
    d = dict(row)
    for field in ("conditions",):
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def upsert_user(
    user_id: str,
    name: str | None = None,
    language_pref: str | None = None,
    age_band: str | None = None,
    conditions: list[str] | None = None,
    last_triage: str | None = None,
    phone: str | None = None,
    follow_up_needed: bool | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    existing = get_user(user_id) or {}
    follow_up_val = (
        int(follow_up_needed) if follow_up_needed is not None
        else existing.get("follow_up_needed", 0)
    )
    with _conn() as con:
        con.execute("""
            INSERT INTO callers
                (user_id, name, language_pref, age_band, conditions, last_triage,
                 last_interaction, phone, follow_up_needed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name             = COALESCE(excluded.name,          callers.name),
                language_pref    = COALESCE(excluded.language_pref, callers.language_pref),
                age_band         = COALESCE(excluded.age_band,       callers.age_band),
                conditions       = COALESCE(excluded.conditions,     callers.conditions),
                last_triage      = COALESCE(excluded.last_triage,    callers.last_triage),
                last_interaction = excluded.last_interaction,
                phone            = COALESCE(excluded.phone,          callers.phone),
                follow_up_needed = excluded.follow_up_needed
        """, (
            user_id,
            name or existing.get("name"),
            language_pref or existing.get("language_pref"),
            age_band or existing.get("age_band"),
            json.dumps(conditions) if conditions is not None else (
                json.dumps(existing["conditions"]) if isinstance(existing.get("conditions"), list)
                else existing.get("conditions")
            ),
            last_triage or existing.get("last_triage"),
            now,
            phone or existing.get("phone"),
            follow_up_val,
        ))


def create_escalation(
    user_id: str,
    caller_name: str | None,
    reason: str,
    summary: str,
    urgency: str,
    language: str,
    agent_checked: str,
) -> str:
    """Create a human-help escalation. Returns the ref_id."""
    ref_id = "ESC-" + uuid.uuid4().hex[:6].upper()
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as con:
        # Avoid duplicate open escalations for same user+reason
        existing = con.execute(
            "SELECT ref_id FROM escalations WHERE user_id=? AND reason=? AND status='open'",
            (user_id, reason),
        ).fetchone()
        if existing:
            return existing["ref_id"]
        con.execute("""
            INSERT INTO escalations
                (ref_id, user_id, caller_name, reason, summary, urgency,
                 language, agent_checked, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
        """, (ref_id, user_id, caller_name, reason, summary, urgency,
               language, agent_checked, now))
    return ref_id


def list_escalations(status: str = "open") -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM escalations WHERE status=? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_escalation_status(ref_id: str, status: str) -> bool:
    """Update escalation status (e.g. 'open' → 'resolved'). Returns True if found."""
    with _conn() as con:
        cur = con.execute(
            "UPDATE escalations SET status=? WHERE ref_id=?",
            (status, ref_id),
        )
    return cur.rowcount > 0


def get_escalation(ref_id: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM escalations WHERE ref_id=?", (ref_id,)
        ).fetchone()
    return dict(row) if row else None


def record_call(
    call_id: str,
    user_id: str,
    started_at: str,
    ended_at: str,
    duration_sec: int,
    outcome: str,
    failure_type: str | None = None,
) -> None:
    """Record a completed call. outcome: 'success' | 'failed'."""
    with _conn() as con:
        con.execute("""
            INSERT OR REPLACE INTO calls
                (call_id, user_id, started_at, ended_at, duration_sec, outcome, failure_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (call_id, user_id, started_at, ended_at, duration_sec, outcome, failure_type))


def get_call_stats() -> dict:
    """Return total, successful, failed counts and recent calls."""
    with _conn() as con:
        row = con.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(outcome = 'success') AS successful,
                SUM(outcome = 'failed')  AS failed
            FROM calls
        """).fetchone()
        recent = con.execute("""
            SELECT call_id, user_id, started_at, ended_at, duration_sec, outcome, failure_type
            FROM calls ORDER BY started_at DESC LIMIT 20
        """).fetchall()
    return {
        "total":      row["total"]      or 0,
        "successful": row["successful"] or 0,
        "failed":     row["failed"]     or 0,
        "recent":     [dict(r) for r in recent],
    }


def follow_up_due() -> list[dict]:
    """Return callers who need a follow-up call."""
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM callers WHERE follow_up_needed = 1 AND followed_up_at IS NULL"
        ).fetchall()
    return [dict(r) for r in rows]


def mark_followed_up(user_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as con:
        con.execute(
            "UPDATE callers SET followed_up_at = ?, follow_up_needed = 0 WHERE user_id = ?",
            (now, user_id),
        )


def delete_user(user_id: str) -> bool:
    with _conn() as con:
        cur = con.execute("DELETE FROM callers WHERE user_id = ?", (user_id,))
    return cur.rowcount > 0
