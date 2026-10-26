"""Loads rule files. A role only ever sees its own file plus the common file."""

from __future__ import annotations

import json
from dataclasses import dataclass

from config import DATA_DIR

ROLES = {
    "student": "Yale student",
    "staff_faculty": "Yale staff or faculty",
    "dependent": "Dependent of a Yale member",
    "visiting_student": "Visiting student",
}

FILES = {role: f"rules_{role}.json" for role in ROLES}

# Lines that are written channels. They are never the first thing someone is told to use.
WRITTEN_CHANNELS = {"member_services_email", "mychart"}


@dataclass(frozen=True)
class RuleSet:
    role: str
    label: str
    lines: list[dict]  # role lines first, then common lines
    facts: list[dict]  # coverage rules from the role file and the common file only; each has a "file" key
    not_verified: list[str]
    fallback: dict
    emergency: dict
    red_flags: dict
    crisis: dict
    departments: list[dict]
    referral_steps: dict

    @property
    def line_ids(self) -> set[str]:
        return {line["id"] for line in self.lines}

    @property
    def fact_ids(self) -> set[str]:
        return {fact["id"] for fact in self.facts}


def _read(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text())


def load_rules(role: str) -> RuleSet:
    if role not in FILES:
        raise ValueError(f"Unknown role: {role!r}")
    own, common = _read(FILES[role]), _read("rules_common.json")
    facts = [dict(f, file=own["file"]) for f in own["coverage"]] + [dict(f, file="common") for f in common["coverage"]]
    return RuleSet(
        role=role,
        label=own["label"],
        lines=[dict(l, file=own["file"]) for l in own["lines"]] + [dict(l, file="common") for l in common["lines"]],
        facts=facts,
        not_verified=own.get("not_verified", []),
        fallback=common["fallback"],
        emergency=common["emergency"],
        red_flags=common["red_flags"],
        crisis=common["crisis"],
        departments=own.get("departments", []) + common.get("departments", []),  # the role's own departments first
        referral_steps=common.get("referral_steps", {}),
    )


ROLE_QUESTION = "Are you a Yale student, staff or faculty, a dependent, or a visiting student?"
ROLE_RULES_NAME = {"student": "Yale student", "staff_faculty": "staff or faculty", "dependent": "dependent", "visiting_student": "visiting student"}
ROLE_OPTIONS = [("student", "Yale student"), ("staff_faculty", "Staff or faculty"), ("dependent", "Dependent"), ("visiting_student", "Visiting student")]


def load_common_only() -> RuleSet:
    """Just the common file. The emergency, crisis and injection checks need no role, so they run before one is known."""
    common = _read("rules_common.json")
    return RuleSet(
        role="none", label="", lines=[dict(l, file="common") for l in common["lines"]],
        facts=[dict(f, file="common") for f in common["coverage"]], not_verified=[], fallback=common["fallback"],
        emergency=common["emergency"], red_flags=common["red_flags"], crisis=common["crisis"],
        departments=common.get("departments", []), referral_steps=common.get("referral_steps", {}),
    )


def parse_role(text: str) -> str | None:
    """Reads a short answer to the role question. Longer text is a question, not an answer, so it returns None."""
    import re

    t = " ".join(str(text).lower().split())
    if not t or len(t) > 80:
        return None
    if re.search(r"\bvisit", t):
        return "visiting_student"
    if re.search(r"\bdepend|\bspouse|\bpartner|\bmy (child|son|daughter|kid)", t):
        return "dependent"
    if re.search(r"\bstaff|\bfaculty|\bemployee|\bprofessor|\bpost-?doc|\bresearcher|\bsecurity", t):
        return "staff_faculty"
    if re.search(r"\bstudent|\bundergrad|\bgrad\b|\bphd|\bmaster", t):
        return "student"
    return None
