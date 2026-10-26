"""Deterministic safety checks that run in code, before and after the model."""

from __future__ import annotations

import json
import re

from rules import RuleSet

EMERGENCY = re.compile(
    r"chest (pain|pressure|tightness)|can'?t breathe|cannot breathe|trouble breathing|difficulty breathing|"
    r"short(ness)? of breath|stroke|face (is )?droop|slurred speech|severe bleeding|won'?t stop bleeding|"
    r"overdos|unconscious|passed out|not responsive|seizure|anaphyla|throat (is )?(closing|swelling)|"
    r"choking|poison|loss of consciousness|lost consciousness|blacked out|life[- ]threatening|"
    r"worst headache|fever (and|with) (a )?stiff neck|stiff neck (and|with) (a )?fever",
    re.I,
)
# Headache red flags only count when the person is talking about a headache.
HEADACHE_TOPIC = re.compile(r"head ?ache|migraine|my head", re.I)
HEADACHE_FLAGS = re.compile(
    r"weak(ness)?|numb|trouble speaking|can'?t speak|confus|vision|can'?t see|double vision|"
    r"hit my head|head injury|bumped my head|fell and hit|after (a |the )?(fall|accident|crash|injury)",
    re.I,
)
CRISIS = re.compile(
    r"suicid|kill myself|end my life|want to die|don'?t want to (live|be alive)|hurt myself|harm myself|self[- ]harm|"
    r"take my own life",
    re.I,
)

PHONE = re.compile(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")

# The app never diagnoses, names a condition, or recommends treatment or medication.
DIAGNOSIS = re.compile(
    r"diagnos|you (probably|likely|may|might|could) have|sounds like|"
    r"(could|might|may|can) be (a|an|due|caused|from|because)|caused by|"
    r"\b(sciatica|herniated|slipped disc|arthritis|sprain|strain|pinched nerve|migraine|concussion|pneumonia|"
    r"fracture|tendinitis|tendonitis|bursitis|stenosis|infection|appendicitis|flu|covid)\b",
    re.I,
)
TREATMENT = re.compile(
    r"\b(ibuprofen|advil|motrin|tylenol|acetaminophen|aspirin|naproxen|aleve|antibiotics?|steroids?|opioids?|"
    r"painkillers?|pain relievers?|muscle relaxants?|cortisone|over-the-counter|otc)\b|"
    r"\b(apply|put|use) (an? )?(ice|heat|heating pad)\b|\bice pack\b|\bbed rest\b|\bstretch(ing|es)?\b",
    re.I,
)


def violates_safety_net(text: str) -> bool:
    return bool(DIAGNOSIS.search(text) or TREATMENT.search(text))


def _digits(number: str) -> str:
    d = re.sub(r"\D", "", number)
    return d[1:] if len(d) == 11 and d.startswith("1") else d


def allowed_numbers(rules: RuleSet) -> set[str]:
    """Every phone number that appears in this role's rules plus the common file."""
    text = json.dumps({"lines": rules.lines, "facts": rules.facts, "fallback": rules.fallback, "emergency": rules.emergency})
    return {_digits(m) for m in PHONE.findall(text)}


def scrub_numbers(text: str, rules: RuleSet) -> str:
    """Replace any phone number the rules do not contain, so the model cannot invent one."""
    allowed = allowed_numbers(rules)
    safe = f"[number not verified - call Member Services {rules.fallback['phone']}]"
    return PHONE.sub(lambda m: m.group(0) if _digits(m.group(0)) in allowed else safe, text)


def emergency_answer(rules: RuleSet, model_calls: int = 0) -> dict:
    """The emergency rule, and nothing else: no plan, no checklist, no coverage, no questions."""
    return {"kind": "emergency", "emergency": rules.emergency, "_meta": {"model_calls": model_calls, "line_id": None}}


def crisis_answer(rules: RuleSet) -> dict:
    by_id = {line["id"]: line for line in rules.lines}
    return {
        "kind": "crisis",
        "crisis": {
            "rule_id": rules.crisis["rule_id"],
            "headline": rules.crisis["headline"],
            "label": rules.crisis["label"],
            "lines": [public_line(by_id["crisis_988"]), public_line(by_id["emergency_911"])],
        },
        "_meta": {"model_calls": 0, "line_id": None},
    }


def check_urgent(situation: str, rules: RuleSet) -> dict | None:
    """Return a ready-made answer for emergencies and crises, or None to continue normally."""
    if CRISIS.search(situation):
        return crisis_answer(rules)
    if EMERGENCY.search(situation) or (HEADACHE_TOPIC.search(situation) and HEADACHE_FLAGS.search(situation)):
        return emergency_answer(rules)
    return None


def public_line(line: dict) -> dict:
    return {k: line[k] for k in ("id", "name", "phone", "email", "kind", "hours", "use_for") if k in line}


# ---- Defenses that run in code before any model call ------------------------------------------------

# Prompt injection: everything the person types is data. Text that tries to give the app orders is refused.
INJECTION = re.compile(
    r"""
    \b(ignore|disregard|forget|override|bypass|skip|drop)\b[^.\n]{0,40}\b(rules?|instructions?|guidelines?|guardrails?|prompts?|
        safety|restrictions?|everything\s+(above|before)|previous|prior|earlier)\b
  | \byou\s+are\s+now\b
  | \b(pretend|imagine)\s+(you\s+are|to\s+be|you're)\b
  | \bact\s+as\s+(a|an|my|if)\b
  | \bfrom\s+now\s+on,?\s+(you|answer|act|respond|ignore)\b
  | \b(reveal|show|print|repeat|leak|output)\b[^.\n]{0,30}\b(system|hidden|initial|secret)\s+(prompt|instructions?|message)\b
  | \bsystem\s+prompt\b
  | ^\s*[\[<(]?\s*(system|assistant|developer)\s*[\]>)]?\s*:
  | [\[<]\s*/?\s*(system|assistant|developer|instructions?)\s*[\]>]
  | \#{2,}\s*(system|instructions?)\b
  | \bbegin\s+(system|new)?\s*(instructions?|prompt)\b
  | \bnew\s+(system\s+)?instructions?\s*[:\-]
  | \bjailbreak\b | \bdeveloper\s+mode\b | \bdo\s+anything\s+now\b
    """,
    re.I | re.M | re.X,
)

# Asking for a diagnosis: the app refuses and routes to a clinician.
DIAGNOSIS_REQUEST = re.compile(
    r"""
    \bwhat\s+(do|could|might|can|would)\s+i\s+have\b
  | \bwhat(\s+is|'s|’s)\s+wrong\s+with\s+me\b
  | \bwhat\s+(could|might|can|would)\s+(this|it|that)\s+be\b
  | \bwhat\s+(condition|disease|illness|infection|disorder)\s+(do|could|might)\b
  | \bis\s+(this|it|that)\s+(serious|dangerous|bad|cancer|life[- ]threatening|something\s+(bad|serious|dangerous))\b
  | \bhow\s+(serious|bad|dangerous)\s+(is|are)\b
  | \bdo\s+i\s+have\s+(cancer|diabetes|covid|the\s+flu|a\s+(tumou?r|infection|virus|concussion|fracture|disease|disorder)|
        (a\s+)?(heart\s+(attack|problem|disease)|arthritis|sciatica|migraines?|depression|anxiety|appendicitis))\b
  | \b(diagnose|diagnosis)\s+(me|my|this|it)\b | \bcan\s+you\s+diagnose\b | \bwhat\s+is\s+my\s+diagnosis\b
  | \bam\s+i\s+(sick|dying|going\s+to\s+die)\b
  | \bshould\s+i\s+be\s+(worried|scared|concerned)\b
  | \bwhat\s+does\s+(this|my)\s+(symptoms?|pain|rash|lump|headache)\s+mean\b
    """,
    re.I | re.X,
)

INJECTION_NOTICE = (
    "I can't follow instructions inside your message. I only help you find the right Yale Health line, plan the call, "
    "and check coverage from Yale Health's rules. Please describe your situation in your own words."
)
DIAGNOSIS_NOTICE = "I can't diagnose, that's for a clinician. Here's who to call:"


def detect_injection(text: str) -> bool:
    return bool(INJECTION.search(text))


def asks_for_diagnosis(text: str) -> bool:
    return bool(DIAGNOSIS_REQUEST.search(text))
