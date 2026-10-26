"""Grounding check: a coverage claim is only shown if it appears in the rule files."""

from __future__ import annotations

import re

from logs import log_guard
from safety import PHONE

NOT_GROUNDED = "I don't know, ask Yale Health. Member Services: (203) 432-0246."
MIN_CLAIM = 30  # a claim shorter than this proves nothing

NUMBER = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?|\d+(?:\.\d+)?\s?%|\d[\d,]*")


def normalize(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def _numbers(text: str) -> set[str]:
    without_phones = PHONE.sub(" ", text)
    return {re.sub(r"[\s,]", "", n) for n in NUMBER.findall(without_phones)}


def snap_claim(claim: str, cited: list[dict]) -> str:
    """If the model's quote is not word for word in a cited rule, keep the part of it that is.

    Models sometimes tidy a quote (drop the end of a sentence, join two sentences). Rather than throw the answer away, find the
    longest whole sentence inside the quote that really is in a cited rule and use that. A quote with no such sentence stays as it is,
    and then fails the check."""
    statements = [normalize(f["statement"]) for f in cited]
    whole = normalize(claim)
    if len(whole) >= MIN_CLAIM and any(whole in s for s in statements):
        return claim
    pieces = [p.strip() for p in re.split(r"(?<=[.!?])\s+(?=[A-Z$(])", claim.strip())]
    real = [p for p in pieces if len(normalize(p)) >= MIN_CLAIM and any(normalize(p) in s for s in statements)]
    return max(real, key=len) if real else claim


def check_item(item: dict, cited: list[dict]) -> str | None:
    """Return None if the claim is grounded, else the reason it is not.

    The model must copy one claim string word for word from a rule it cites. The string has to appear in a cited
    rule (which comes from the role file or the common file), and every number in the answer has to appear there too.
    """
    claim = normalize(str(item.get("claim") or ""))
    statements = [normalize(f["statement"]) for f in cited]
    if len(claim) < MIN_CLAIM or not any(claim in s for s in statements):
        return "claim_not_in_rules"
    shown = " ".join(str(item.get(k) or "") for k in ("answer", "condition", "excluded"))
    allowed = _numbers(" ".join(statements))
    stray = sorted(n for n in _numbers(shown) if n not in allowed)
    return "number_not_in_rules" if stray else None


def ground(item: dict, cited: list[dict], role: str) -> bool:
    reason = check_item(item, cited)
    if reason:
        log_guard("grounding_failure", role, reason=reason, rule_ids=[f["id"] for f in cited], status=item.get("status"))
    return reason is None


# The plan builder may not make coverage claims of its own. A "free" claim is never allowed, and any number it
# writes has to appear in the rules the person's role can see.
FREE_CLAIM = re.compile(r"\b(is|are|will\s+be|be|it's|they're)\s+(completely\s+|totally\s+)?free\b|\bfree\s+of\s+charge\b|\bno[- ]cost\b|\bat\s+no\s+charge\b|\bwithout\s+charge\b", re.I)


def plan_text_ungrounded(text: str, statements: list[str]) -> bool:
    if FREE_CLAIM.search(text):
        return True
    allowed = _numbers(" ".join(normalize(s) for s in statements))
    return any(n not in allowed for n in _numbers(text))
