"""One chat turn. The bot is an agent with a rule-file lookup tool. Every reply goes through the same screening and the
same verifier as a plan. Nothing is kept between turns: the browser holds the thread and sends back what is needed."""

from __future__ import annotations

import re

from agents import chat_agent
from logs import log_guard
from navigator import screen
from sections import official_coverage_url
from rules import ROLE_OPTIONS, ROLE_QUESTION, ROLE_RULES_NAME, RuleSet, load_common_only, load_rules, parse_role
from safety import DIAGNOSIS_NOTICE, asks_for_diagnosis, detect_injection, public_line, violates_safety_net
from sections import clean_wants

UNKNOWN = "I don't know from the rule files. Call Member Services at (203) 432-0246."  # with no role set


def unknown_text(role: str | None) -> str:
    """The fallback names the role file that was searched, so a correct refusal does not look like a bug."""
    if not role:
        return UNKNOWN
    return f"I don't know from the {ROLE_RULES_NAME[role]} rules I have. Call Member Services at (203) 432-0246."


ABOUT_RULE_FILES = ("The rule files are the Yale Health coverage documents I answer from: your role's file plus the common file. "
                    "I only answer what those files say, and I can't diagnose.")
_FILES_WORD = re.compile(r"\brules?[\s-]?files?\b", re.I)
_FILLER = re.compile(r"\b(rules?[\s-]?files?|what|whats|are|is|the|a|an|these|those|your|do|does|mean|means|you|use|about|tell|me|explain|which|that|this|it)\b|[^\w\s]", re.I)


_PAGE_FILLER = re.compile(r"\b(where|whats|what|is|are|the|a|an|official|yale|health|coverage|page|site|website|link|url|find|can|i|to|give|me|show|do|you|have|for|my)\b|[^\w\s]", re.I)


def asks_for_coverage_page(question: str) -> bool:
    """True when the question is only a request for the official coverage page. Any other word (a service or a topic) goes to the pipeline."""
    q = question.replace("'", "")
    return bool(re.search(r"\b(coverage|official)\b", q, re.I)) and bool(re.search(r"\b(page|site|website|link|url)\b", q, re.I)) and not _PAGE_FILLER.sub(" ", q).split()


def asks_about_rule_files(question: str) -> bool:
    """True only when the question is about the rule files themselves. Any other word (a service, a department, a topic) sends it to the normal pipeline."""
    return bool(_FILES_WORD.search(question)) and not _FILLER.sub(" ", question.replace("'", "")).split()

# A message that asks something goes to the bot. One that describes a situation (and there is no plan yet) goes to the plan pipeline.
QUESTION = re.compile(r"\?\s*$|^\s*(is|are|do|does|did|can|could|will|would|should|how|what|when|where|which|who|why|am)\b", re.I)
USE_PLAN = "That sounds like a situation rather than a question, so I made a plan for you. It is on the page."
MAX_EARLIER = 5
MAX_EARLIER_CHARS = 300


def clean_history(earlier: list[str]) -> list[str]:
    """The thread comes from the browser, so it is untrusted: trimmed, limited, and dropped if it tries to give orders."""
    kept = [" ".join(str(q).split())[:MAX_EARLIER_CHARS] for q in earlier[-MAX_EARLIER:]]
    return [q for q in kept if q and not detect_injection(q)]


def clean_context(context: dict | None, rules: RuleSet) -> dict:
    """The plan's context, echoed back by the page. Untrusted too: only known values and short, safe text get through."""
    context = context or {}
    by_id = {line["id"]: line for line in rules.lines}
    wants = clean_wants(context.get("wants"))
    topics = [" ".join(str(t).split())[:80] for t in (context.get("topics") or [])[:4]]
    topics = [t for t in topics if t and not detect_injection(t) and not violates_safety_net(t)]
    line = by_id.get(context.get("line_id"))
    return {
        "their_plan_was_about": "" if wants == "my question" or detect_injection(wants) else wants,
        "category": context.get("category") if context.get("category") in ("routine", "urgent") else "routine",
        "line_chosen": line["name"] if line else None,
        "has_referral": context.get("has_referral") is True,
        "topics_already_shown": topics,
    }


def step(name: str, result: str) -> dict:
    return {"step": name, "result": result}


def describes_a_situation(text: str) -> bool:
    return not QUESTION.search(text) and len(text.split()) >= 3


def ask_role(text: str = ROLE_QUESTION) -> dict:
    return {"kind": "ask_role", "text": text, "options": [{"value": v, "label": l} for v, l in ROLE_OPTIONS]}


def chat_turn(role: str | None, question: str, earlier: list[str], context: dict | None, steps: list[dict],
              answering_role: bool = False, has_plan: bool = False) -> dict:
    """Returns a reply in the ChatReply shape. `steps` collects what each stage decided, for the audit trail.

    The chat and the form are two doors to the same bot: this is the same pipeline either way. The emergency, crisis,
    injection and diagnosis checks need no role, so they run first. Everything else waits for a role."""
    rules = load_rules(role) if role else load_common_only()  # raises ValueError for an unknown role

    blocked = screen(rules, question)  # emergency and crisis first, then prompt injection
    if blocked:
        steps.append(step("screen", blocked["kind"]))
        if blocked["kind"] == "refused":
            return {"kind": "refused", "text": blocked["notice"]}
        return {key: blocked[key] for key in ("kind", "emergency", "crisis") if key in blocked}
    steps.append(step("screen", "passed"))

    if asks_for_diagnosis(question):  # decided in code, before the model
        log_guard("diagnosis_refused", rules.role)
        steps.append(step("diagnosis_check", "refused"))
        acute = next(line for line in rules.lines if line["id"] == "acute_care")
        return {"kind": "diagnosis", "text": DIAGNOSIS_NOTICE, "line": public_line(acute)}
    steps.append(step("diagnosis_check", "passed"))

    if asks_about_rule_files(question):  # about the app itself: answered in code, no role and no model needed
        steps.append(step("route", "a question about the rule files: answered in code"))
        return {"kind": "about", "text": ABOUT_RULE_FILES}

    if asks_for_coverage_page(question):  # the page comes from the rule files (common.care_at_center); no role and no model needed
        url = official_coverage_url(rules)
        if url:
            steps.append(step("route", "a question about the official coverage page: answered in code from the rule files"))
            return {"kind": "about", "text": "Here is the official Yale Health coverage page.", "link": {"text": "See the official Yale Health coverage page", "url": url}}

    if not role:  # the bot needs a role before it can answer from a role file
        parsed = parse_role(question) if answering_role else None
        if parsed:
            steps.append(step("role", f"set to {parsed}"))
            return {"kind": "role_set", "role": parsed, "text": f"Got it, I'll use the {ROLE_RULES_NAME[parsed]} rules. What would you like to ask?"}
        steps.append(step("role", "asked" if not answering_role else "not understood, asked again"))
        return ask_role(ROLE_QUESTION if not answering_role else "I didn't catch that. " + ROLE_QUESTION)

    if not has_plan and describes_a_situation(question):  # no plan yet: the same plan pipeline, run by the page
        steps.append(step("route", "a situation with no plan yet: sent to the plan pipeline"))
        return {"kind": "use_plan", "text": USE_PLAN}
    steps.append(step("route", "a question: answered by the bot"))

    earlier = clean_history(earlier)
    ctx = clean_context(context, rules)
    steps.append(step("context", f"{len(earlier)} earlier questions, plan context {'used' if ctx['their_plan_was_about'] or ctx['topics_already_shown'] else 'empty'}"))
    out = chat_agent(rules, question, earlier, ctx)  # the bot looks rules up with its tool; its answer is then verified
    shown = [i for i in out["items"] if i["status"] != "not_verified"]
    steps.append(step("lookup_tool", f"{out['lookups']} lookups in the role file and the common file; rules seen: {', '.join(out['rules_seen']) or 'none'}"))
    steps.append(step("verifier", f"{len(shown)} passed citation, grounding, number and no-diagnosis checks; {len(out['items']) - len(shown)} did not"))
    if not shown:  # nothing in the rule files answers it: say so, never guess
        return {"kind": "unknown", "text": unknown_text(role)}
    return {"kind": "answer", "items": shown}


def reply_text(reply: dict) -> str:
    """The answer as plain text, for the log."""
    if reply.get("items"):
        return " ".join(i["answer"] for i in reply["items"])
    if reply.get("emergency"):
        return reply["emergency"]["headline"]
    if reply.get("crisis"):
        return reply["crisis"]["headline"]
    return reply.get("text") or ""


def rules_cited(reply: dict) -> list[str]:
    return [r["id"] for i in reply.get("items") or [] for r in i["rules"]]
