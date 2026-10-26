"""Guard log: one line per defense that fired. No situation text, no answer text, no health data."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone

import config

GUARD_LOG = "guard_log.jsonl"


def log_guard(event: str, role: str | None = None, **detail) -> None:
    """event is one of: grounding_failure, injection_refused, diagnosis_refused, budget_exceeded."""
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    record = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event, "role": role, **detail}
    with (config.OUTPUT_DIR / GUARD_LOG).open("a") as f:
        f.write(json.dumps(record) + "\n")


_lock = threading.Lock()


def session_tag(session: str | None) -> str:
    """A short hash of the random session id, so a log can group turns without holding the id itself."""
    return hashlib.sha256((session or "none").encode()).hexdigest()[:10]


def append_json_array(name: str, record: dict, limit: int | None = None) -> None:
    """Add one record to output/<name>, which stays a valid JSON array. Oldest records are dropped past the limit."""
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    path = config.OUTPUT_DIR / name
    with _lock:
        try:
            records = json.loads(path.read_text()) if path.exists() else []
        except json.JSONDecodeError:
            records = []
        records.append(record)
        path.write_text(json.dumps(records[-(limit or config.CHAT_LOG_LIMIT):], indent=2) + "\n")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_chat_turn(session: str | None, role: str, question: str, answer: str, rule_ids: list[str], kind: str, tokens: int) -> None:
    """One line of the chat log: the question, the answer, the rule cited, and the tokens used."""
    shown = question if config.CHAT_LOG_QUESTIONS else f"[{len(question)} characters, not stored]"
    append_json_array(config.CHAT_LOG, {"time": now(), "session": session_tag(session), "role": role, "question": shown,
                                        "answer": answer, "rule_cited": rule_ids, "kind": kind, "tokens_used": tokens})


def log_audit(request: str, session: str | None, role: str, steps: list[dict], outcome: str, tokens: int, **extra) -> None:
    """The audit trail: every step a request went through and what each step decided. No question or answer text."""
    append_json_array(config.AUDIT_LOG, {"time": now(), "request": request, "session": session_tag(session), "role": role,
                                         "steps": steps, "outcome": outcome, "tokens_used": tokens, **extra})
