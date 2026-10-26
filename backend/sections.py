"""Parts of the answer that are built in code from the rule files, never by the model."""

from __future__ import annotations

from rules import RuleSet
from safety import PHONE, public_line, violates_safety_net

WRITE_DOWN = ["Date and time of the appointment", "Referral details", "Name of the person you spoke to"]

ADMIN_WRITE_DOWN = ["Name of the person you spoke to", "What they told you"]

WARNINGS = [
    "MyChart replies take about two business days.",
    "Member Services hours: Monday-Friday, 8:30 a.m.-5:00 p.m.",
]

ROLE_PHRASE = {
    "student": "a Yale student",
    "staff_faculty": "Yale staff or faculty",
    "dependent": "a dependent of a Yale member",
    "visiting_student": "a visiting student",
}


def _line(rules: RuleSet, line_id: str) -> dict:
    return next(line for line in rules.lines if line["id"] == line_id)


def name_in_rules(rules: RuleSet, line: dict) -> str:
    """What the common rule file calls this phone number, so a calendar note says "Member Services", not "main line"."""
    common = next((l["name"] for l in rules.lines if l.get("file") == "common" and line.get("phone") and l.get("phone") == line["phone"]), None)
    return common or line["name"]


def contact_of(line: dict) -> str:
    return line.get("phone") or line.get("email") or line["name"]


def category_label(category: str, symptom: bool, intent: str) -> str:
    if category == "urgent":
        return "Urgent care (same day)"
    return "Routine PCP visit" if symptom or intent == "care_visit" else "Routine (coverage or administrative question)"


def how_it_decided(rules: RuleSet, category: str, symptom: bool, intent: str, line: dict, reason: str) -> dict:
    return {
        "role_id": rules.role,
        "role_label": rules.label,
        "rule_files": [f"rules_{rules.role}.json", "rules_common.json"],
        "category": category,
        "category_label": category_label(category, symptom, intent),
        "line_id": line["id"],
        "line_name": line["name"],
        "contact": contact_of(line),
        "reason": reason,
    }


def safety_net(rules: RuleSet, area: str | None) -> dict | None:
    if not area:
        return None
    rule = next((f for f in rules.facts if f["id"] == rules.red_flags["rule_id"]), None)
    ref = {k: rule[k] for k in ("id", "file", "source", "url", "source_status") if k in rule} if rule else None
    return {"area": area, "signs": rules.red_flags[area], "closing": "Call 911.", "rule_id": rules.red_flags["rule_id"], "rule": ref}


def if_not_as_planned(rules: RuleSet, line: dict, involves_referral: bool, has_referral: bool, care_visit: bool = True) -> list[dict]:
    acute, member = _line(rules, "acute_care")["phone"], _line(rules, "member_services")["phone"]
    if line["id"] == "acute_care":
        busy = f"Acute Care's nurse triage line answers 24 hours a day at {acute}. If it is an emergency, call 911."
    else:
        hours = line.get("hours")
        hours_text = f"{line['name']} hours: {hours.rstrip('.')}. " if hours and hours != "Not stated" else ""
        busy = f"{hours_text}Try again when it is open. If you need to be seen today, call Acute Care at {acute}, which also has a nurse triage line 24 hours a day."
    items = [{"problem": "The line is busy or closed", "what_to_do": busy}]
    if not care_visit:  # a coverage question has no appointment to wait for
        return items
    items.append(
        {
            "problem": "No appointments soon",
            "what_to_do": f"Ask Member Services at {member} what else is open. If you need to be seen today, call Acute Care at {acute}.",
        }
    )
    if involves_referral and not has_referral:
        items.append(
            {
                "problem": "After your PCP visit",
                "what_to_do": "Come back here, tick 'Referral received', and press the button below. The plan updates for booking.",
                "action": "has_referral",
            }
        )
    elif involves_referral and has_referral:
        items.append(
            {
                "problem": "They cannot find or accept your referral",
                "what_to_do": f"Call Member Services at {member} and ask where your referral stands.",
            }
        )
    return items


def clean_wants(wants: object) -> str:
    text = " ".join(str(wants or "").split())[:60]
    return text if text and not violates_safety_net(text) else "my question"


def prefer_writing(rules: RuleSet, intent: str, category: str, symptom: bool, wants: object) -> dict:
    """Copy-paste drafts only. Never for appointments, symptoms or urgent issues. The app never sends anything."""
    email = mychart = None
    topic, who = clean_wants(wants), ROLE_PHRASE[rules.role]
    if not symptom and category == "routine":
        if intent == "administrative":
            email = {
                "to": "member.services@yale.edu",
                "subject": f"Coverage question: {topic}",
                "body": (
                    f"Hello Member Services,\n\nI am {who}. I have a question about {topic}. Could you tell me:\n"
                    "- Whether it is covered under my plan\n"
                    "- Any conditions that apply, such as a referral or prior authorization\n"
                    "- Any costs or exclusions\n\nThank you,\n[Your name]\n[Your NetID or Yale Health ID]"
                ),
            }
        elif intent == "care_team_message":
            mychart = {
                "body": (
                    f"Hello care team,\n\nI have a non-urgent question about {topic}.\n\n[Add your question here]\n\n"
                    "I understand replies can take about two business days. If this becomes urgent I will call.\n\n"
                    "Thank you,\n[Your name]"
                )
            }
    note = "Only for coverage, admin, and non-urgent questions. For appointments, symptoms, or anything urgent, call the line above."
    return {"note": note, "warnings": WARNINGS, "email": email, "mychart": mychart}


def also_lines(rules: RuleSet, ids: list[str]) -> list[dict]:
    by_id = {line["id"]: line for line in rules.lines}
    return [public_line(by_id[i]) for i in ids]


CENTER = "Yale Health Center, 55 Lock Street, New Haven"


def calendar_events(rules: RuleSet, line: dict, category: str, care_visit: bool, wants: object, involves_referral: bool, has_referral: bool) -> list[dict]:
    """Details for the booked steps (PCP visit, PTSMC booking). Only the wording of the plan: no date, no booking."""
    if category != "routine" or not care_visit:
        return []
    topic = clean_wants(wants)
    about = f", {topic}" if topic != "my question" else ""
    bring = "Bring a student ID to appointments." if rules.role == "student" else "Carry your Yale Health ID card."
    ptsmc = next((l for l in rules.lines if l["id"] == "ptsmc"), None)

    def ptsmc_event(when: str) -> dict:
        first_visit = [n for n in PHONE.findall(ptsmc["use_for"]) if n != ptsmc["phone"]]
        extra = f" First-visit scheduling: {first_visit[0]}." if first_visit else ""
        return {
            "when": when,
            "title": f"PTSMC first visit{about}",
            "location": f"PTSMC, {CENTER}",
            "notes": f"Line to call: {ptsmc['name'].split(',')[0]}, {ptsmc['phone']}.{extra} Booked by phone. "
            f"Referral details: [add the referral number or clinician name]. {bring}",
        }

    if has_referral:
        return [ptsmc_event("Today")] if ptsmc else []
    events = [
        {
            "when": "This week",
            "title": f"Yale Health PCP visit{about}{' referral' if involves_referral and about else ''}",
            "location": CENTER,
            "notes": f"Line to call: {name_in_rules(rules, line)}, {contact_of(line)}. Booked by phone. "
            f"Referral details: [add after the visit]. {bring}",
        }
    ]
    if involves_referral and ptsmc:
        events.append(ptsmc_event("After the referral"))
    return events


# Lines whose visit happens at the Yale Health Center (common.care_at_center: "All care happens at the Yale Health Center").
CENTER_LINES = {"student_pcp", "member_services", "acute_care", "ptsmc"}


def official_coverage_url(rules: RuleSet) -> str | None:
    """The Yale Health coverage page, taken from the rule files (common.care_at_center), for the link under "What your plan covers"."""
    fact = next((f for f in rules.facts if f["id"] == "common.care_at_center"), None)
    return fact["url"] if fact else None


def place_for(line: dict) -> dict | None:
    """The Yale Health Center, for the "Get directions" link. The address is the one in the rule files."""
    if line["id"] not in CENTER_LINES:
        return None
    return {"name": "Yale Health Center", "address": "55 Lock Street, New Haven"}
