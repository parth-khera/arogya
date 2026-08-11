"""SQLite persistence for Aarogya caller memory."""
import json
import sqlite3
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
    # migrate existing tables that predate these columns
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


def follow_up_due() -> list[dict]:
    """Return callers who need a follow-up call and have a phone number."""
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM callers WHERE follow_up_needed = 1 AND phone IS NOT NULL AND followed_up_at IS NULL"
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
