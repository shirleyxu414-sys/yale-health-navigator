"""FastAPI app. Serves the HTML UI and one JSON endpoint. No database, no sessions, no stored situations."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from config import MODEL, OUTPUT_DIR, ROOT
import budget
import config
from logs import log_audit, log_chat_turn, log_guard
from models import Answer, ChatReply, ReferralAnswer
from navigator import navigate
from referral import check_referral, department_names
from rules import load_rules
from rules import ROLES

LOG_PATH = OUTPUT_DIR / "run_log.jsonl"
FRONTEND = ROOT / "frontend"

app = FastAPI(title="Yale Health Navigator")


class Ask(BaseModel):
    role: Literal["student", "staff_faculty", "dependent", "visiting_student"]
    situation: str = Field(min_length=3, max_length=2000)
    timing: Literal["today", "can_wait"] | None = None
    has_referral: bool = False
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{8,64}$")  # a random id from the page; no personal data


@app.middleware("http")
async def no_store(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


def log_run(role: str, kind: str | None, meta: dict | None, started: float, error: str | None) -> None:
    """Metadata only: never the situation text, never the answer text."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    record = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "role": role,
        "kind": kind,
        "line_id": meta["line_id"] if meta else None,
        "model": MODEL,
        "model_calls": meta["model_calls"] if meta else None,
        "seconds": round(time.monotonic() - started, 2),
        "error": error,
    }
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/roles")
def roles():
    return ROLES


def trace_rules(items: list[dict], extra: list[dict | None] | None = None) -> list[dict]:
    """The rules an answer used, with their file and source, for the audit trail. The page shows them only in "How it decided"."""
    seen: dict[str, dict] = {}
    for r in [r for item in items for r in item.get("rules", [])] + [r for r in (extra or []) if r]:
        seen.setdefault(r["id"], {k: r[k] for k in ("id", "file", "source", "source_status") if k in r})
    return list(seen.values())


def answer_extra_rules(answer: dict) -> list[dict | None]:
    """Rules behind the parts of a plan that are not coverage items: the warning list, plain-words terms, and the referral help."""
    help_ = answer.get("referral_help") or {}
    return ([(answer.get("safety_net") or {}).get("rule")] + [g["rule"] for g in answer.get("glossary") or []]
            + [p["rule"] for p in help_.get("pcp") or []] + [(help_.get("tracker_note") or {}).get("rule")])


BUDGET_NOTICES = {
    "session": "This session has reached its limit of {cap:,} input tokens, so I stopped before making another request. "
    "Refresh the page to start a new session, or call Member Services at (203) 432-0246.",
    "address": "There have been too many requests from this network in the last hour, so I stopped. "
    "Please try again later, or call Member Services at (203) 432-0246.",
}


class ChatAsk(BaseModel):
    role: Literal["student", "staff_faculty", "dependent", "visiting_student"] | None = None  # none until the person says
    answering_role: bool = False  # this message answers the bot's role question
    has_plan: bool = False  # a plan already exists in the session, so the chat carries its context
    question: str = Field(min_length=2, max_length=500)
    history: list[str] = Field(default_factory=list, max_length=10)  # the person's earlier questions, kept in the browser only
    context: dict | None = None  # the plan's chat_context, echoed back by the page and re-checked on the server
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{8,64}$")


@app.post("/api/chat", response_model=ChatReply, response_model_exclude_none=True)
def chat_route(ask: ChatAsk, request: Request):
    """One follow-up question. The server keeps no conversation: only budget counters and the logs."""
    from chat import chat_turn, reply_text, rules_cited

    address = f"ip:{request.client.host if request.client else 'unknown'}"
    who = budget.Who(ask.session_id or address, address)
    owner = budget.current.set(who)  # chat turns are charged to the same session budget as plans
    used_before = budget.GUARD.sessions.used(who.session)
    steps: list[dict] = []
    try:
        reply = chat_turn(ask.role, ask.question, ask.history, ask.context, steps, ask.answering_role, ask.has_plan)
    except budget.BudgetExceeded as over:  # stop and say so: nothing more is sent to the model
        scope = "session" if over.cap == config.SESSION_TOKEN_CAP else "address"
        log_guard("budget_exceeded", ask.role or "none", scope=scope, used=over.used, cap=over.cap)
        steps.append({"step": "budget_guard", "result": f"stopped before the model call ({over.used} of {over.cap} tokens used)"})
        reply = {"kind": "budget", "text": BUDGET_NOTICES[scope].format(cap=over.cap)}
    except Exception as exc:  # never echo the question back in an error
        steps.append({"step": "error", "result": type(exc).__name__})
        log_audit("chat", who.session, ask.role or "none", steps, "error", 0)
        return JSONResponse(status_code=502, content={"detail": "The assistant could not answer right now. Please try again, or call Member Services at (203) 432-0246."})
    finally:
        budget.current.reset(owner)
    tokens = budget.GUARD.sessions.used(who.session) - used_before
    log_chat_turn(who.session, ask.role or "none", ask.question, reply_text(reply), rules_cited(reply), reply["kind"], tokens)
    log_audit("chat", who.session, ask.role or "none", steps, reply["kind"], tokens, rules_cited=rules_cited(reply),
              rules=trace_rules(reply.get("items") or []))
    return reply


class ReferralAsk(BaseModel):
    role: Literal["student", "staff_faculty", "dependent", "visiting_student"]
    department: str = Field(min_length=2, max_length=80)
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{8,64}$")


@app.get("/api/departments")
def departments(role: Literal["student", "staff_faculty", "dependent", "visiting_student"]):
    """The department names the picked role's referral checker knows, so the homepage input can suggest them before any plan."""
    return {"departments": department_names(load_rules(role))}


@app.post("/api/referral", response_model=ReferralAnswer, response_model_exclude_none=True)
def referral_route(ask: ReferralAsk):
    """"Do I need a referral?" for one department, from the rule files. No model, no tokens, and the typed text is not kept."""
    reply = check_referral(load_rules(ask.role), ask.department)
    log_audit("referral", ask.session_id, ask.role,
              [{"step": "match", "result": reply["verdict"]}], reply["verdict"], 0, rules=trace_rules([], [reply.get("rule")]))
    return reply


@app.get("/safety-demo")
def safety_demo_page():
    return FileResponse(FRONTEND / "safety_demo.html")


@app.get("/api/safety-demo")
def safety_demo():
    from safety_demo import run_suite

    return run_suite()


@app.get("/api/example", response_model=Answer, response_model_exclude_none=True)
def example():
    """The back-pain physical therapy example as a full plan. No model call, no tokens, nothing stored."""
    from example import build_example

    return build_example()


@app.post("/api/navigate", response_model=Answer, response_model_exclude_none=True)
def navigate_route(ask: Ask, request: Request):
    started = time.monotonic()
    address = f"ip:{request.client.host if request.client else 'unknown'}"
    who = budget.Who(ask.session_id or address, address)
    owner = budget.current.set(who)
    used_before = budget.GUARD.sessions.used(who.session)
    try:
        answer = navigate(ask.role, ask.situation, ask.timing, ask.has_referral)
    except budget.BudgetExceeded as over:  # stop and tell the person; nothing more is sent to the model
        scope = "session" if over.cap == config.SESSION_TOKEN_CAP else "address"
        log_guard("budget_exceeded", ask.role, scope=scope, used=over.used, cap=over.cap)
        answer = {"kind": "budget", "notice": BUDGET_NOTICES[scope].format(cap=over.cap), "_meta": {"model_calls": 0, "line_id": None}}
    except Exception as exc:  # never echo the situation back in an error
        log_run(ask.role, None, None, started, type(exc).__name__)
        return JSONResponse(
            status_code=502,
            content={"detail": "The assistant could not answer right now. Please try again, or call Member Services at (203) 432-0246."},
        )
    finally:
        budget.current.reset(owner)
    meta = answer.pop("_meta")
    log_run(ask.role, answer["kind"], meta, started, None)
    log_audit("plan", who.session, ask.role, [{"step": "pipeline", "result": answer["kind"]}], answer["kind"],
              budget.GUARD.sessions.used(who.session) - used_before, line_id=meta["line_id"], model_calls=meta["model_calls"],
              rules=trace_rules(answer.get("coverage", {}).get("items", []), answer_extra_rules(answer)))
    return answer


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
