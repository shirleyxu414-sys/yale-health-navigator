"""Runs the pipeline for one request. Nothing about the person's situation is kept after it returns.

Order: emergency check in code, router, coverage checker, plan builder. Unknown timing for a symptom defaults to today.
"""

from __future__ import annotations

import re
from agents import MENTAL_HEALTH, coverage_agent, plan_agent, router_agent
from rules import load_rules
from logs import log_guard
from safety import (
    DIAGNOSIS_NOTICE,
    INJECTION_NOTICE,
    asks_for_diagnosis,
    check_urgent,
    detect_injection,
    emergency_answer,
    public_line,
)
from glossary import glossary_for
from referral import referral_help
from sections import (
    ADMIN_WRITE_DOWN,
    WRITE_DOWN,
    also_lines,
    calendar_events,
    clean_wants,
    how_it_decided,
    if_not_as_planned,
    official_coverage_url,
    place_for,
    prefer_writing,
    safety_net,
)

DISCLAIMER = (
    "Educational guidance only. This app does not diagnose or recommend treatment, and it is not a coverage decision. "
    "In an emergency call 911. Confirm details with Yale Health Member Services at (203) 432-0246."
)

def select_line(rules, route: dict, category: str) -> dict:
    """Same-day need goes to Acute Care, routine goes to the primary care line. Mental health and referral lines are kept."""
    by_id = {line["id"]: line for line in rules.lines}
    chosen = route["line_id"]
    pcp = "student_pcp" if "student_pcp" in by_id else "member_services"
    if route["symptom_present"] and chosen not in MENTAL_HEALTH:
        referral_line = route["has_referral"] and "ptsmc" in by_id and chosen == "ptsmc"
        if category == "urgent":
            chosen = "acute_care"
        elif not referral_line:
            chosen = pcp
    return by_id[chosen]


def screen(rules, situation: str, log: bool = True) -> dict | None:
    """Checks that run in code before any model call. Returns a finished answer, or None to carry on.

    Emergencies and crises come first. Then text that tries to give the app orders is refused outright.
    """
    urgent = check_urgent(situation, rules)
    if urgent:
        return urgent
    if detect_injection(situation):
        if log:
            log_guard("injection_refused", rules.role)
        return {"kind": "refused", "notice": INJECTION_NOTICE, "_meta": {"model_calls": 0, "line_id": None}}
    return None


# A referral is part of the plan when the plan's own steps say to get one. "No referral needed" is not that.
NO_REFERRAL = re.compile(r"\b(?:no|without|doesn't need|does not need|don't need)\b[^.;]{0,25}?referral", re.I)


def plan_mentions_referral(texts: list[str]) -> bool:
    return "referral" in NO_REFERRAL.sub(" ", " ".join(texts)).lower()


def plan_mentions_pcp(texts: list[str]) -> bool:
    return bool(ASKS_PCP.search(" ".join(texts)))


# Someone asking about their PCP gets the "Your PCP" card even when the coverage answer does not mention a referral.
ASKS_PCP = re.compile(r"\bPCP\b|primary care (provider|physician)", re.I)


def navigate(role: str, situation: str, timing: str | None = None, has_referral: bool = False) -> dict:
    rules = load_rules(role)  # raises ValueError for an unknown role
    blocked = screen(rules, situation)
    if blocked:
        return blocked

    diagnosis = asks_for_diagnosis(situation)  # decided in code: the app will not diagnose, whatever the model does
    if diagnosis:
        log_guard("diagnosis_refused", rules.role)
    route = router_agent(rules, situation, timing, has_referral, diagnosis)
    if route["red_flag_reported"]:  # emergency short-circuits everything else
        return emergency_answer(rules, model_calls=1)

    symptom = route["symptom_present"]
    timing_assumed = False
    if route["timing"] == "unknown" and (symptom or diagnosis):
        route["timing"] = "today"  # cannot tell how serious it is, so the 24-hour Acute Care nurse line is the safe route
        timing_assumed = bool(symptom)  # the page says so and offers the routine plan
    category = ("urgent" if route["timing"] == "today" else "routine") if symptom else (
        "urgent" if route["category"] == "urgent" else "routine"
    )
    line = select_line(rules, route, category)
    coverage = coverage_agent(rules, situation, category, route["wants"], route["has_referral"])
    care_visit = symptom or route["intent"] == "care_visit"  # otherwise it is a coverage or administrative question
    built = plan_agent(
        rules,
        {"category": category, "line": line, "wants": route["wants"], "has_referral": route["has_referral"], "care_visit": care_visit},
        coverage,
    )
    step_texts = ([s["when"] + " " + s["what"] for s in built["timeline"]] + [t for p in built["do_not_forget"] for t in (p["point"], p["why"])]
                  + [c["label"] for c in built["checklist"]])
    tracker_on = bool(route["has_referral"]) or plan_mentions_referral(step_texts)  # the person has a referral, or the plan says to get one
    pcp_on = plan_mentions_pcp(step_texts) or bool(ASKS_PCP.search(situation))
    involves_referral = any(
        "referral" in (i["answer"] + " " + (i.get("condition") or "")).lower()
        for i in coverage["items"]
        if i["status"] != "not_verified"
    )
    plan = dict(
        built,
        write_down=[w for w in WRITE_DOWN if tracker_on or w != "Referral details"] if care_visit else ADMIN_WRITE_DOWN,
        if_not_as_planned=if_not_as_planned(rules, line, involves_referral, route["has_referral"], care_visit),
        calendar=calendar_events(rules, line, category, care_visit, route["wants"], involves_referral, route["has_referral"]),
    )
    how = how_it_decided(rules, category, symptom, route["intent"], line, route["reason"])
    also = also_lines(rules, [i for i in route["also_consider"] if i != line["id"]])
    plan_texts = (
        [how["reason"], line["name"], line.get("use_for", ""), plan["summary"]]
        + [t for l in also for t in (l["name"], l.get("use_for", ""))]
        + [s["what"] for s in plan["timeline"]] + [t for p in plan["do_not_forget"] for t in (p["point"], p["why"])]
        + [c["label"] for c in plan["checklist"]] + [g["what_to_do"] for g in plan["if_not_as_planned"]]
        + [t for i in coverage["items"] for t in (i["topic"], i["answer"], i.get("condition") or "", i.get("excluded") or "", i.get("claim") or "")]
    )
    return {
        "kind": "plan",
        **({"notice": DIAGNOSIS_NOTICE} if diagnosis else {}),
        "how_it_decided": how,
        "line": public_line(line),
        "also_consider": also,
        "plan": plan,
        "coverage": {**coverage, "official_url": official_coverage_url(rules)},
        "safety_net": safety_net(rules, route["symptom_area"]),
        "prefer_writing": prefer_writing(rules, route["intent"], category, symptom, route["wants"]),
        # What the plan established, for the chat. The page echoes it back with each chat question.
        "chat_context": {
            "wants": clean_wants(route["wants"]),
            "category": category,
            "line_id": line["id"],
            "has_referral": route["has_referral"],
            "topics": [i["topic"] for i in coverage["items"] if i["status"] != "not_verified"][:4],
        },
        "timing_assumed": True if timing_assumed else None,
        "place": place_for(line),
        "referral_help": referral_help(rules, tracker=tracker_on, pcp=pcp_on) if tracker_on or pcp_on else None,
        "glossary": glossary_for(rules, plan_texts) or None,
        "disclaimer": DISCLAIMER,
        "_meta": {"model_calls": 3, "line_id": line["id"]},
    }
