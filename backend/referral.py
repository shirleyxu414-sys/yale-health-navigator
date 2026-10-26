"""The referral tools: "Do I need a referral?", the PCP card and the tracker's note. Departments and lines only.

Everything here comes from the rule files. A department that is not in the lists gets "Ask Member Services", never a guess.
No doctor's name and no provider roster is ever returned.
"""

from __future__ import annotations

import re

from rules import RuleSet
from safety import check_urgent, detect_injection


def _rule_ref(rules: RuleSet, rule_id: str) -> dict | None:
    fact = next((f for f in rules.facts if f["id"] == rule_id), None)
    return {k: fact[k] for k in ("id", "file", "source", "url", "source_status") if k in fact} if fact else None


def department_names(rules: RuleSet) -> list[str]:
    seen: list[str] = []
    for d in rules.departments:
        if d["name"] not in seen:
            seen.append(d["name"])
    return seen


def check_referral(rules: RuleSet, text: str) -> dict:
    """The answer for one department. The typed text is matched, never stored and never echoed."""
    urgent = check_urgent(text, rules)
    if urgent:  # a person in an emergency gets the emergency message, not a referral answer
        headline = rules.emergency["headline"] if urgent["kind"] == "emergency" else rules.crisis["headline"]
        return {"verdict": "emergency", "answer": headline}
    unknown = {"verdict": "unknown", "answer": rules.referral_steps["unknown"], "next_step": None}
    if detect_injection(text):
        return unknown
    t = " ".join(text.lower().split())
    best, best_len = None, 0
    for dept in rules.departments:  # the role's own departments come first
        for alias in [dept["name"].lower()] + [a.lower() for a in dept["aliases"]]:
            if len(alias) > best_len and re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", t):
                best, best_len = dept, len(alias)
    if not best:
        return unknown
    steps = rules.referral_steps
    if best["needs_referral"]:
        answer, step = f"{best['name']}: a referral from your PCP is needed before scheduling.", steps["needed"]
    else:
        answer, step = f"{best['name']}: no referral is needed.", steps[best.get("next_step", "not_needed")]
    return {"verdict": "needed" if best["needs_referral"] else "not_needed", "department": best["name"], "answer": answer,
            "next_step": step, "rule": _rule_ref(rules, best["rule_id"])}


def referral_help(rules: RuleSet, tracker: bool = True, pcp: bool = True) -> dict:
    """The PCP card's points (when asked for) and the tracker's note (when asked for), each with its rule."""
    def point(rule_id: str) -> dict:
        fact = next(f for f in rules.facts if f["id"] == rule_id)
        return {"text": fact["statement"], "rule": _rule_ref(rules, rule_id)}

    return {
        "pcp": [point(r) for r in ("common.pcp_assigned", "common.pcp_change", "common.provider_list")] if pcp else None,  # what a PCP is comes from the glossary tap
        "tracker_note": point("common.referral_not_guarantee") if tracker else None,
    }
