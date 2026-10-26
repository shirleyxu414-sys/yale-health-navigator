"""The one response shape. The backend returns an Answer; the frontend reads only these fields.

Fields that do not apply are left out of the JSON, so an emergency answer is just
{"kind": "emergency", "emergency": {...}} and nothing else.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Line(BaseModel):
    id: str
    name: str
    phone: str | None = None
    email: str | None = None
    kind: str | None = None
    hours: str | None = None
    use_for: str | None = None


class Decision(BaseModel):
    """The "How it decided" panel."""

    role_id: str
    role_label: str
    rule_files: list[str]
    category: Literal["routine", "urgent"]
    category_label: str
    line_id: str
    line_name: str
    contact: str
    reason: str


class RuleRef(BaseModel):
    id: str
    file: str
    source: str
    url: str | None = None
    quote: str | None = None
    source_status: str | None = None  # "unconfirmed" when no Yale Health document backs the rule


class CoverageItem(BaseModel):
    topic: str
    status: Literal["covered", "conditions", "not_covered", "not_verified"]
    answer: str
    claim: str | None = None
    condition: str | None = None
    excluded: str | None = None
    applies_to: list[str] = Field(default_factory=list)
    rules: list[RuleRef] = Field(default_factory=list)


class Coverage(BaseModel):
    items: list[CoverageItem]
    official_url: str | None = None  # the Yale Health coverage page, from the rule files


class DoNotForget(BaseModel):
    point: str
    why: str


class TimelineStep(BaseModel):
    when: str
    what: str


class ChecklistItem(BaseModel):
    id: str
    label: str


class GoWrong(BaseModel):
    problem: str
    what_to_do: str
    action: Literal["has_referral"] | None = None


class CalendarEvent(BaseModel):
    """Pre-filled details for the "Add to calendar" form. The person adds the date and time. Nothing is booked by the app."""

    when: str
    title: str
    location: str
    notes: str


class Plan(BaseModel):
    summary: str
    timeline: list[TimelineStep]
    do_not_forget: list[DoNotForget]
    write_down: list[str]
    checklist: list[ChecklistItem]
    if_not_as_planned: list[GoWrong]
    calendar: list[CalendarEvent]


class SafetyNet(BaseModel):
    area: str
    signs: list[str]
    closing: str
    rule_id: str
    rule: RuleRef | None = None  # shown only in "How it decided", never on the warning list itself


class Draft(BaseModel):
    to: str | None = None
    subject: str | None = None
    body: str


class PreferWriting(BaseModel):
    note: str
    warnings: list[str]
    email: Draft | None = None
    mychart: Draft | None = None


class ErSite(BaseModel):
    name: str
    address: str


class Emergency(BaseModel):
    rule_id: str
    headline: str
    er: list[ErSite]
    notes: list[str]


class Crisis(BaseModel):
    rule_id: str
    headline: str
    label: str
    lines: list[Line]


class ChatContext(BaseModel):
    """What the plan already established, so the chat does not make the person repeat themselves. The page echoes it back."""

    wants: str
    category: Literal["routine", "urgent"]
    line_id: str
    has_referral: bool = False
    topics: list[str] = Field(default_factory=list)


class HelpPoint(BaseModel):
    text: str
    rule: RuleRef


class ReferralHelp(BaseModel):
    """What the plan's referral tools need: the PCP card and the tracker's note."""

    pcp: list[HelpPoint] | None = None  # only when the plan's own steps mention the PCP
    tracker_note: HelpPoint | None = None  # only when the plan involves a referral


class ReferralAnswer(BaseModel):
    """The answer to "Do I need a referral?" for one department. Never names a doctor."""

    verdict: Literal["needed", "not_needed", "unknown", "emergency"]
    department: str | None = None
    answer: str
    next_step: str | None = None
    rule: RuleRef | None = None


class Place(BaseModel):
    """Where the visit happens, from the rule files, for the "Get directions" link."""

    name: str
    address: str


class GlossaryEntry(BaseModel):
    """A jargon term the plan uses, with the one sentence from the rule files that explains it, and which rule it is."""

    term: str
    variants: list[str]
    explanation: str
    rule: RuleRef


class Answer(BaseModel):
    kind: Literal["plan", "emergency", "crisis", "refused", "budget"]
    notice: str | None = None
    how_it_decided: Decision | None = None
    line: Line | None = None
    also_consider: list[Line] | None = None
    plan: Plan | None = None
    coverage: Coverage | None = None
    safety_net: SafetyNet | None = None
    prefer_writing: PreferWriting | None = None
    chat_context: ChatContext | None = None
    timing_assumed: bool | None = None  # true when the person did not say when they need care, so the plan assumed today
    place: Place | None = None
    referral_help: ReferralHelp | None = None
    glossary: list[GlossaryEntry] | None = None
    emergency: Emergency | None = None
    crisis: Crisis | None = None
    disclaimer: str | None = None


class RoleOption(BaseModel):
    value: Literal["student", "staff_faculty", "dependent", "visiting_student"]
    label: str


class Link(BaseModel):
    text: str
    url: str


class ChatReply(BaseModel):
    """One answer in the "Ask a follow-up" chat. Answers are coverage items: each cites its rule and quotes it."""

    kind: Literal["answer", "unknown", "diagnosis", "emergency", "crisis", "refused", "budget", "ask_role", "role_set", "use_plan", "about"]
    text: str | None = None
    role: Literal["student", "staff_faculty", "dependent", "visiting_student"] | None = None
    options: list[RoleOption] | None = None
    items: list[CoverageItem] | None = None
    line: Line | None = None
    link: Link | None = None  # a page from the rule files, for a question about where to read the coverage
    emergency: Emergency | None = None
    crisis: Crisis | None = None
