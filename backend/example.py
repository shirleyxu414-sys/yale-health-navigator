"""The example plan: the back-pain physical therapy case, built with no model call and no tokens.

It runs the real pipeline (the router, coverage, plan and every code check) with canned model replies, so the example
always has the current response shape, and a test checks that its claims are grounded in the rule files.
"""

from __future__ import annotations

import agents
from navigator import navigate

EXAMPLE_ROLE = "student"
EXAMPLE_TEXT = "lower back pain for weeks, I want physical therapy"
EXAMPLE_NOTICE = (
    "This is an example plan for a Yale student with lower back pain who wants physical therapy. "
    "It was not made for you. Pick your role and describe your situation to get your own."
)

PT_CLAIM = "Physical therapy is covered 100% under the Yale student health plan with a referral from a PCP."

ROUTER = {
    "category": "routine", "red_flag_reported": False, "symptom_present": True, "symptom_area": "general", "timing": "can_wait",
    "intent": "care_visit", "wants": "physical therapy", "has_referral": False, "line_id": "student_pcp", "also_consider": ["ptsmc"],
    "reason": "Call primary care about your back pain and a referral for physical therapy.",
}

COVERAGE = {
    "items": [
        {
            "topic": "Physical therapy",
            "status": "conditions",
            "answer": "Physical therapy is covered 100% under the Yale student health plan with a referral from a PCP. Without a referral, coverage is not promised.",
            "condition": "A referral from a PCP is needed, and prior authorization is required for referrals. Eligibility depends on having Yale Health Hospitalization & Specialty Care coverage; your status is not known here.",
            "excluded": "Students who have waived Yale Health Hospitalization & Specialty Care coverage and Medicare patients are not eligible for treatment in the Physical Therapy Department.",
            "claim": PT_CLAIM,
            "rule_ids": ["student.pt_coverage", "student.pt_requires_hospitalization_specialty", "common.care_at_center"],
        },
        {
            "topic": "Dry needling",
            "status": "conditions",
            "answer": "Dry needling is available through PTSMC and is covered under a PT referral.",
            "condition": "It needs the PT referral.",
            "excluded": None,
            "claim": "Dry needling is available through PTSMC and is covered under a PT referral.",
            "rule_ids": ["student.dry_needling"],
        },
    ]
}

PLAN = {
    "summary": "Call the main line for a primary care visit and the physical therapy referral, then book PTSMC.",
    "timeline": [
        {"when": "Today", "what": "Call (203) 432-0246 to book a primary care visit."},
        {"when": "On the call", "what": "Ask for the PT referral and confirm prior authorization is arranged."},
        {"when": "This week", "what": "Go to the PCP visit and bring a student ID."},
        {"when": "After the referral", "what": "Book PTSMC. First-visit scheduling is (203) 498-5980."},
    ],
    "do_not_forget": [
        {"point": "Ask for the PT referral.", "why": "PT is covered 100% only with one."},
        {"point": "Ask whether PTSMC offers dry needling.", "why": "It is covered under a PT referral, but only if you ask."},
        {"point": "Check that you kept Hospitalization & Specialty Care coverage.", "why": "Students who waived it are not eligible for PT."},
    ],
    "checklist": [{"label": "Called the main line"}, {"label": "PCP visit booked"}, {"label": "PT referral received"}, {"label": "PTSMC booked"}],
}


def canned_model(instructions: str, payload: dict) -> dict:
    if "You are the Router" in instructions:
        return ROUTER
    if "You are the Plan Builder" in instructions:
        return PLAN
    return COVERAGE


def build_example() -> dict:
    token = agents.canned.set(canned_model)
    try:
        out = navigate(EXAMPLE_ROLE, EXAMPLE_TEXT)
    finally:
        agents.canned.reset(token)
    out.pop("_meta")
    out["notice"] = EXAMPLE_NOTICE
    return out
