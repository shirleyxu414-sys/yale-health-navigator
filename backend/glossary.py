"""Plain-words explanations for jargon in the plan. Every explanation is one sentence copied word for word from a rule file.

If the rule files do not explain a term, it has no entry here, and the page shows nothing for it. The terms left out on
purpose, because no rule file explains them: "copay" and "dry needling" (the rules use them without saying what they are).
"""

from __future__ import annotations

import re

from rules import RuleSet

GLOSSARY = [
    {"term": "PCP", "variants": ["PCP"],
     "options": [{"rule_id": "common.pcp_what", "sentence": "Your primary care provider (PCP) is the medical professional who knows you best and coordinates all of your care."}]},
    {"term": "prior authorization", "variants": ["prior authorization"],
     "options": [{"rule_id": "common.prior_authorization", "sentence": "Certain services and supplies require Prior Authorization to confirm coverage, eligibility, medical necessity, and support care coordination for services."}]},
    {"term": "referral", "variants": ["referral", "referrals"],
     "options": [{"rule_id": "common.care_at_center", "sentence": "All care happens at the Yale Health Center unless a PCP refers you out."}]},
    {"term": "Basic Student Health Services", "variants": ["Basic Student Health Services"],
     "options": [{"rule_id": "student.basic_services", "sentence": "Basic Student Health Services gives eligible students access to many Yale Health services, including primary care."}]},
    {"term": "Basic Coverage", "variants": ["Basic Coverage"],
     "options": [{"rule_id": "student.no_coverage", "sentence": "Yale requires coverage, so an enrolled student generally has Basic Coverage for primary care at the Yale Health Center."}]},
    {"term": "Hospitalization & Specialty Care coverage", "variants": ["Hospitalization & Specialty Care coverage", "Hospitalization & Specialty Care"],
     "options": [{"rule_id": "student.hospitalization_specialty", "sentence": "The university requires Hospitalization & Specialty Care coverage for students eligible for Basic Student Health Services."}]},
    {"term": "waived", "variants": ["waived", "waive"],
     "options": [{"rule_id": "student.hospitalization_specialty", "sentence": "Students are automatically enrolled and billed unless they waive it."}]},
    {"term": "plan group", "variants": ["plan group", "plan groups"],
     "options": [{"rule_id": "employee.plan_groups", "sentence": "Cost-sharing depends on your plan group."}]},
    {"term": "PTSMC", "variants": ["PTSMC"],
     "options": [{"rule_id": "student.ptsmc", "sentence": "PTSMC (Physical Therapy and Sports Medicine Center) is at the Yale Health Center, 55 Lock Street: (203) 436-5583."},
                 {"rule_id": "employee.physical_therapy", "sentence": "PTSMC at Yale Health is at 55 Lock Street, New Haven."}]},
    {"term": "Acute Care", "variants": ["Acute Care"],
     "options": [{"rule_id": "common.acute_care_hours", "sentence": "Acute Care is open Sunday to Saturday, 8 a.m. to 10 p.m., for urgent same-day needs."}]},
    {"term": "MyChart", "variants": ["MyChart"],
     "options": [{"rule_id": "common.written_channels", "sentence": "MyChart messaging is for non-urgent care team messages, with replies in about two business days."}]},
]


def glossary_for(rules: RuleSet, texts: list[str]) -> list[dict]:
    """The entries for terms that appear in `texts`, using only rules this person's role may read."""
    blob = " ".join(t for t in texts if t)
    by_id = {f["id"]: f for f in rules.facts}
    found = []
    for entry in GLOSSARY:
        if not any(re.search(rf"(?<!\w){re.escape(v)}(?!\w)", blob, re.I) for v in entry["variants"]):
            continue
        for option in entry["options"]:
            fact = by_id.get(option["rule_id"])
            if fact and option["sentence"] in fact["statement"]:  # the sentence must really be in the rule
                rule = {k: fact[k] for k in ("id", "file", "source", "url") if k in fact}
                found.append({"term": entry["term"], "variants": entry["variants"], "explanation": option["sentence"], "rule": rule})
                break
    return found
