"""The three agents. Each is one gpt-6-luna call with its own prompt and a JSON answer."""

from __future__ import annotations

import json

import budget
from contextvars import ContextVar
from typing import Callable
from config import MODEL, make_client
from grounding import NOT_GROUNDED, ground, plan_text_ungrounded, snap_claim
from rules import WRITTEN_CHANNELS, RuleSet
import re
from pathlib import Path

from safety import public_line, scrub_numbers, violates_safety_net

_client = None

# When set, run_agent answers from this function instead of calling the model. Only the example plan sets it.
canned: ContextVar[Callable[[str, dict], dict] | None] = ContextVar("canned_model", default=None)


def _client_once():
    global _client
    if _client is None:
        _client = make_client()
    return _client


def run_agent(instructions: str, payload: dict) -> dict:
    """One model call. Asks for JSON, retries once if the reply is not valid JSON.

    Every call is checked against the token budget before it is made and charged with the real usage after.
    """
    fake = canned.get()
    if fake:
        return fake(instructions, payload)
    client = _client_once()
    text = "Respond with a single JSON object only.\n" + json.dumps(payload)
    estimate = budget.estimate_tokens(instructions + text)
    who = budget.current.get()
    for attempt in range(2):
        if who:
            budget.GUARD.before_call(who, estimate)  # raises BudgetExceeded: the run stops before spending anything
        response = client.responses.create(
            model=MODEL,
            instructions=instructions,
            input=text,
            text={"format": {"type": "json_object"}},
            store=False,
        )
        if who:
            budget.GUARD.after_call(who, getattr(getattr(response, "usage", None), "input_tokens", None) or estimate)
        try:
            return json.loads(response.output_text)
        except json.JSONDecodeError:
            if attempt == 1:
                raise
    raise RuntimeError("unreachable")


PROMPTS = Path(__file__).parent / "prompts"


def prompt(name: str) -> str:
    """The runtime prompts live in backend/prompts/, one file each."""
    return (PROMPTS / f"{name}.md").read_text().strip()


NEVER = prompt("never")
ROUTER_PROMPT = NEVER + "\n\n" + prompt("router")
COVERAGE_PROMPT = NEVER + "\n\n" + prompt("coverage")
PLAN_PROMPT = NEVER + "\n\n" + prompt("plan")
CHAT_PROMPT = NEVER + "\n\n" + prompt("chat")

WHEN = ["Today", "On the call", "This week", "After the referral"]
# Filler that says nothing. Never allowed in a plan, and wrong for a coverage question.
FILLER = re.compile(
    r"(describe|tell\s+(them|us|the\s+\w+)).{0,40}(what\s+you\s+are\s+experiencing|your\s+situation|in\s+your\s+own\s+words)"
    r"|call\s+the\s+line\s+above|ask\s+what\s+you\s+need\s+before|some\s+services\s+need\s+one\s+first",
    re.I,
)
SCRIPT_LIKE = re.compile(r"[\"\u201c\u201d]|^\s*(say|tell (them|the|him|her)|read|recite|repeat)\b", re.I)
MENTAL_HEALTH = {"mental_health_counseling", "behavioral_health_magellan"}


# Checklist ids are chosen by meaning, in code, so a ticked box can be matched again when the plan is re-built
# (for example after "I have my referral"), even though the model words the labels differently each time.
CHECK_KEYS = [("referral", r"referral"), ("called", r"\bcall"), ("ptsmc", r"\bptsmc\b"), ("booked", r"book|schedul|appointment|visit")]


def checklist_ids(labels: list[str]) -> list[dict]:
    used: set[str] = set()
    items = []
    for n, label in enumerate(labels, 1):
        key = next((k for k, pattern in CHECK_KEYS if k not in used and re.search(pattern, label, re.I)), f"other{n}")
        used.add(key)
        items.append({"id": key, "label": label})
    return items


def _line_view(line: dict) -> dict:
    return public_line(line)


def _clean(text: object, rules: RuleSet) -> str:
    return scrub_numbers(" ".join(str(text or "").split()), rules)


def _bad(text: str, rules: RuleSet) -> bool:
    """True if a plan text diagnoses, recommends treatment, mentions acupuncture, or makes a coverage claim the rules do not."""
    return (
        violates_safety_net(text)
        or "acupuncture" in text.lower()
        or plan_text_ungrounded(text, [f["statement"] for f in rules.facts] + [f"{line['use_for']} {line.get('hours', '')}" for line in rules.lines])
    )


def router_agent(
    role_rules: RuleSet, situation: str, timing: str | None = None, has_referral: bool = False, diagnosis_requested: bool = False
) -> dict:
    out = run_agent(
        ROUTER_PROMPT,
        {
            "role": role_rules.label,
            "situation": situation,
            "timing_given": timing,
            "has_referral_given": has_referral,
            "diagnosis_requested": diagnosis_requested,
            "available_lines": [_line_view(x) for x in role_rules.lines],
            "red_flags": {k: v for k, v in role_rules.red_flags.items() if k != "rule_id"},
        },
    )
    valid = role_rules.line_ids
    category = out.get("category") if out.get("category") in ("emergency", "urgent", "routine") else "routine"
    symptom = out.get("symptom_present") is True or diagnosis_requested  # asking what is wrong implies a symptom
    line_id = out.get("line_id")
    if line_id not in valid or line_id in WRITTEN_CHANNELS:
        line_id = "member_services"
    also = out.get("also_consider", [])
    areas = [k for k in role_rules.red_flags if k != "rule_id"]
    area = out.get("symptom_area")
    reason = _clean(out.get("reason"), role_rules)
    intent = out.get("intent") if out.get("intent") in ("care_visit", "administrative", "care_team_message") else "care_visit"
    return {
        "category": category,
        "red_flag_reported": out.get("red_flag_reported") is True or category == "emergency",
        "symptom_present": symptom,
        "symptom_area": (area if area in areas else "general") if symptom else None,
        "timing": timing or (out.get("timing") if out.get("timing") in ("today", "can_wait") else "unknown"),
        "diagnosis_requested": diagnosis_requested,
        "intent": "care_visit" if symptom else intent,  # a symptom is always a care visit, never a written draft
        "wants": str(out.get("wants") or "")[:60],
        "has_referral": has_referral or out.get("has_referral") is True,
        "line_id": line_id,
        "also_consider": [i for i in (also if isinstance(also, list) else []) if i in valid and i != line_id][:2],
        "reason": "Member Services can route you to the right place." if violates_safety_net(reason) or not reason else reason,
    }


def verify_items(role_rules: RuleSet, raw_items: object, allowed: set[str] | None = None) -> list[dict]:
    """The verifier. Shared by the coverage checker and the chat bot, so both are held to the same checks.

    An item is shown only if it cites rules in the role file or the common file (and, for the chat, only rules the bot
    actually looked up), quotes a claim that is in a cited rule, uses only numbers that are in those rules, and has no
    diagnosis or treatment language. Anything else becomes "not verified"."""
    fallback = role_rules.fallback["text"]
    by_id = {f["id"]: f for f in role_rules.facts if allowed is None or f["id"] in allowed}
    cleaned = []
    for item in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(item, dict):
            continue
        ids = [i for i in item.get("rule_ids", []) if i in by_id] if isinstance(item.get("rule_ids"), list) else []
        status = item.get("status")
        answer = _clean(item.get("answer"), role_rules)
        topic = _clean(item.get("topic"), role_rules)
        topic = "Coverage" if not topic or violates_safety_net(topic) else topic
        if status not in ("covered", "conditions", "not_covered") or not ids or violates_safety_net(answer):
            cleaned.append({"topic": topic, "status": "not_verified", "answer": fallback, "rules": []})
            continue

        cited = [by_id[i] for i in dict.fromkeys(ids)]

        def extra(key: str) -> str | None:
            text = _clean(item.get(key), role_rules)
            return None if not text or text.lower() in ("null", "none") or violates_safety_net(text) else text

        candidate = {
            "topic": topic,
            "status": status,
            "answer": answer,
            "condition": extra("condition"),
            "excluded": extra("excluded"),
            "claim": snap_claim(" ".join(str(item.get("claim") or "").split()), cited),
        }
        if not ground(candidate, cited, role_rules.role):  # the claim is not in the rule files: do not show it
            cleaned.append({"topic": topic, "status": "not_verified", "answer": NOT_GROUNDED, "rules": []})
            continue
        cleaned.append(
            {
                **candidate,
                "applies_to": [f["scope"] for f in cited if "scope" in f],
                "rules": [{k: f[k] for k in ("id", "file", "source", "url", "quote", "source_status") if k in f} for f in cited],
            }
        )
    return cleaned[:4] or [{"topic": "Coverage", "status": "not_verified", "answer": fallback, "rules": []}]


def coverage_agent(role_rules: RuleSet, situation: str, category: str, wants: str, has_referral: bool) -> dict:
    """Reads only this role's rules plus the common rules. Every kept item names the rules it came from."""
    out = run_agent(
        COVERAGE_PROMPT,
        {
            "role": role_rules.label,
            "situation": situation,
            "category": category,
            "wants": wants,
            "has_referral": has_referral,
            "rules": [{k: f[k] for k in ("id", "topic", "statement", "scope") if k in f} for f in role_rules.facts],
            "not_in_the_rules_for_this_role": role_rules.not_verified,
        },
    )
    return {"items": verify_items(role_rules, out.get("items"))}


# ---- The chat bot: an agent with a rule-file lookup tool ---------------------------------------------------

LOOKUP_TOOL = {
    "type": "function",
    "name": "lookup_rules",
    "description": "Search the Yale Health rule files: the person's own role file plus the common file, and nothing else. "
    "Returns up to 4 rules, each with an id, a topic and the rule's exact statement. Returns an empty list when no rule matches.",
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "A few keywords, for example: physical therapy referral"}},
        "required": ["query"],
        "additionalProperties": False,
    },
    "strict": True,
}

STOP = {"the", "and", "for", "are", "what", "does", "how", "can", "you", "with", "this", "that", "from", "have", "has", "was", "will", "any",
        "its", "not", "but", "who", "why", "when", "which", "about", "into", "than", "then", "there", "their", "they", "them", "your", "mine"}
ALIASES = {
    "pt": ["physical", "therapy", "ptsmc"], "er": ["emergency", "room"], "ed": ["emergency"], "pcp": ["primary", "care", "referral"],
    "cost": ["copay", "cost", "costs", "$"], "price": ["copay", "cost"], "pay": ["copay", "cost"], "free": ["cost", "covered", "100%"],
    "insurance": ["coverage", "plan", "enrolled", "waived"], "insured": ["coverage", "plan", "enrolled"], "waive": ["waived", "waiver"],
    "needle": ["needling"], "doctor": ["clinician", "physician"], "appointment": ["visit", "appointments"], "hours": ["open", "hours"],
    "open": ["open", "hours"], "phone": ["phone", "call", "number"], "number": ["phone", "call"], "after": ["after", "hours"],
}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9$%]+", text.lower()) if len(w) >= 2 and w not in STOP}


def lookup_rules(role_rules: RuleSet, query: str, limit: int = 4) -> list[dict]:
    """Keyword search over this role's rules plus the common rules. This is the only thing the bot can read."""
    wanted = _words(query)
    for w in list(wanted):
        wanted |= set(ALIASES.get(w, []))
    scored = []
    for n, fact in enumerate(role_rules.facts):
        score = 3 * len(wanted & _words(fact["topic"])) + len(wanted & _words(fact["statement"]))
        if score:
            scored.append((-score, n, fact))
    return [{k: f[k] for k in ("id", "topic", "statement", "scope") if k in f} for _, _, f in sorted(scored, key=lambda t: t[:2])[:limit]]


def _json_from(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        found = re.search(r"\{.*\}", text, re.S)
        if not found:
            raise
        return json.loads(found.group(0))


def run_agent_with_tools(instructions: str, payload: dict, tools: list[dict], handlers: dict, max_rounds: int = 4) -> dict:
    """A small tool loop. Every round goes through the token budget, so a chat turn that would go over the cap stops first."""
    client = _client_once()
    who = budget.current.get()
    messages: list[dict] = [{"role": "user", "content": "When you are done, reply with a single JSON object only.\n" + json.dumps(payload)}]
    for round_number in range(max_rounds + 1):
        if who:
            budget.GUARD.before_call(who, budget.estimate_tokens(instructions + json.dumps(messages)))
        last = round_number == max_rounds  # on the last round the bot must answer with what it has
        response = client.responses.create(
            model=MODEL, instructions=instructions, input=messages, tools=tools, store=False, **({"tool_choice": "none"} if last else {})
        )
        if who:
            budget.GUARD.after_call(who, getattr(getattr(response, "usage", None), "input_tokens", None) or 1)
        calls = [o for o in response.output if getattr(o, "type", None) == "function_call"]
        if not calls:
            return _json_from(response.output_text)
        for call in calls:
            result = handlers[call.name](json.loads(call.arguments or "{}")) if call.name in handlers else {"error": "unknown tool"}
            messages.append({"type": "function_call", "call_id": call.call_id, "name": call.name, "arguments": call.arguments})
            messages.append({"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(result)})
    raise RuntimeError("unreachable")


def chat_agent(role_rules: RuleSet, question: str, earlier: list[str], context: dict) -> dict:
    """The chat bot. It looks rules up with the tool, answers from what it found, and its answer goes through the same
    verifier as a plan's coverage. It can only cite rules it looked up in this turn."""
    seen: dict[str, dict] = {}
    lookups: list[str] = []

    def handle_lookup(args: dict) -> dict:
        query = str(args.get("query", ""))[:200]
        found = lookup_rules(role_rules, query)
        lookups.append(query)
        seen.update({f["id"]: f for f in found})
        return {"rules": found} if found else {"rules": [], "note": "No rule matches. If nothing else matches, answer with an empty items list."}

    out = run_agent_with_tools(
        CHAT_PROMPT,
        {"role": role_rules.label, "question": question, "earlier_questions": earlier, "plan_context": context},
        [LOOKUP_TOOL],
        {"lookup_rules": handle_lookup},
    )
    return {"items": verify_items(role_rules, out.get("items"), allowed=set(seen)), "lookups": len(lookups), "rules_seen": sorted(seen)}


# ---- The plan builder ----------------------------------------------------------------------------------------

def plan_agent(role_rules: RuleSet, decision: dict, coverage: dict) -> dict:
    """Builds the summary, timeline, do-not-forget points and checklist. It is question-aware: a coverage-only question
    gets no timeline, and a referral reminder appears only if a rule the answer cites says a referral matters."""
    care_visit = decision["care_visit"]
    by_id = {f["id"]: f for f in role_rules.facts}
    cited_text = " ".join(by_id[r["id"]]["statement"] for i in coverage["items"] for r in i["rules"]).lower()
    referral_matters = "referral" in cited_text
    out = run_agent(
        PLAN_PROMPT,
        {
            "role": role_rules.label,
            "question_kind": "care visit" if care_visit else "coverage or administrative question",
            "category": decision["category"],
            "chosen_line": _line_view(decision["line"]),
            "wants": decision["wants"],
            "has_referral": decision["has_referral"],
            "a_rule_says_a_referral_matters": referral_matters,
            "coverage_items": [
                {k: i.get(k) for k in ("topic", "status", "answer", "condition", "excluded")} for i in coverage["items"]
            ],
            "rules": [{"id": f["id"], "statement": f["statement"]} for f in role_rules.facts],
        },
    )

    def usable(text: str) -> bool:
        """No diagnosis, no script, no filler, no coverage claim the rules do not make, and no referral talk unless a rule says so."""
        if not text or _bad(text, role_rules) or SCRIPT_LIKE.search(text) or FILLER.search(text):
            return False
        return referral_matters or "referral" not in text.lower()

    summary = _clean(out.get("summary"), role_rules)
    if not care_visit:
        summary = ""  # for a coverage question the verdict is the answer, so a summary would only say it twice
    else:
        said = [_words(i["answer"]) for i in coverage["items"] if i["status"] != "not_verified"]
        mine = _words(summary)
        if mine and any(len(mine & w) / len(mine | w) >= 0.5 for w in said):  # a summary that restates the coverage verdict is a repeat
            summary = ""

    timeline = []
    for step in out.get("timeline", []) if care_visit and isinstance(out.get("timeline"), list) else []:  # none for a coverage question
        when, what = step.get("when"), _clean(step.get("what"), role_rules)
        if when in WHEN and usable(what) and (referral_matters or when != "After the referral"):
            timeline.append({"when": when, "what": what})
    timeline.sort(key=lambda s: WHEN.index(s["when"]))
    if care_visit and not timeline:
        timeline = [{"when": "Today", "what": f"Call {decision['line'].get('phone') or decision['line']['name']}."}]

    points = []
    for p in out.get("do_not_forget", []) if isinstance(out.get("do_not_forget"), list) else []:
        point, why = _clean(p.get("point"), role_rules), _clean(p.get("why"), role_rules)
        if usable(point) and usable(why):
            points.append({"point": point, "why": why})

    labels = [_clean(c.get("label"), role_rules) for c in out.get("checklist", []) if isinstance(c, dict)]
    booking = re.compile(r"book|appointment|visit|schedul", re.I)  # a coverage question has no appointment to book
    checklist = checklist_ids([t for t in labels if usable(t) and (care_visit or not booking.search(t))][: 5 if care_visit else 2])

    return {
        "summary": summary if usable(summary) else "",
        "timeline": timeline[:4],
        "do_not_forget": points[:3],
        "checklist": checklist,
    }
