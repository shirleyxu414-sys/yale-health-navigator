"""Safety tests. All offline except the last one, which runs only if a PORTKEY_API_KEY is available."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import agents
import config
import main
import navigator
from rules import ROLES, load_rules
from safety import PHONE, allowed_numbers

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", ".git", "__pycache__", ".pytest_cache", "tests"}


def repo_files(suffixes=(".py", ".md", ".json", ".html", ".txt", ".example")):
    for path in ROOT.rglob("*"):
        if path.is_file() and not (set(path.relative_to(ROOT).parts) & SKIP_DIRS) and path.suffix in suffixes:
            yield path


def router_reply(**over) -> dict:
    base = dict(category="routine", red_flag_reported=False, symptom_present=False, symptom_area=None, timing="unknown",
                intent="administrative", wants="physical therapy", has_referral=False, line_id="member_services",
                also_consider=[], reason="Member Services can help.")
    return {**base, **over}


PLAN_REPLY = {
    "summary": "Call the line.",
    "timeline": [{"when": "Today", "what": "Call the line."}],
    "do_not_forget": [{"point": "Ask for a referral.", "why": "The referral is required to book physical therapy."}],
    "checklist": [{"label": "Called"}],
}
COVERAGE_REPLY = {"items": [{"topic": "Anything", "answer": "Covered.", "status": "covered", "rule_ids": ["not_a_real_id"]}]}


def fake_model(captured: list | None = None, router: dict | None = None, plan: dict | None = None, coverage: dict | None = None):
    """Stands in for the model. Records every payload it is given."""

    def run(instructions: str, payload: dict) -> dict:
        if captured is not None:
            captured.append((instructions, payload))
        if "You are the Router" in instructions:
            return router or router_reply()
        if "You are the Plan Builder" in instructions:
            return plan or PLAN_REPLY
        return coverage or COVERAGE_REPLY

    return run


# 1. Key loading: repo folder first, then the folder above ---------------------------------------

def test_env_repo_folder_wins_then_parent(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / ".env").write_text("PORTKEY_API_KEY=fake-parent-value\n")
    (repo / ".env").write_text("PORTKEY_API_KEY=fake-repo-value\n")
    monkeypatch.delenv("PORTKEY_API_KEY", raising=False)
    config.load_env(repo)
    assert os.environ["PORTKEY_API_KEY"] == "fake-repo-value"

    monkeypatch.delenv("PORTKEY_API_KEY")
    (repo / ".env").unlink()
    config.load_env(repo)
    assert os.environ["PORTKEY_API_KEY"] == "fake-parent-value"


def test_env_missing_everywhere_gives_clear_error(tmp_path, monkeypatch):
    monkeypatch.delenv("PORTKEY_API_KEY", raising=False)
    config.load_env(tmp_path / "nothing")
    with pytest.raises(RuntimeError, match="PORTKEY_API_KEY"):
        config.make_client()


# 2. Model and key hygiene ---------------------------------------------------------------------

def test_only_gpt_6_luna_appears_in_code_and_readme():
    assert config.MODEL == "gpt-6-luna"
    found = {m for p in repo_files() for m in re.findall(r"gpt-[\w.\-]+", re.sub(r"https?://\S+", "", p.read_text()))}  # code, comments, README, prompts, report and slides (web addresses are not model names)
    assert found == {"gpt-6-luna"}, found
    assert "gpt-6-luna" in (ROOT / "README.md").read_text()


def test_no_hardcoded_keys_and_env_example_lists_only_the_key():
    for path in repo_files():
        text = path.read_text()
        assert not re.search(r"\b(sk|pk)-[A-Za-z0-9_\-]{16,}", text), path
        for line in text.splitlines():
            if "PORTKEY_API_KEY" in line and path.name != "test_safety.py":
                assert not re.search(r"PORTKEY_API_KEY\s*=\s*\S", line), (path, "has a value")
    example = [l for l in (ROOT / ".env.example").read_text().splitlines() if l.strip() and not l.startswith("#")]
    assert example == ["PORTKEY_API_KEY="]


def test_env_file_is_ignored_by_git():
    assert ".env" in (ROOT / ".gitignore").read_text().splitlines()


# 3. Emergencies never wait for a model ---------------------------------------------------------

HEADLINE = "Call 911 or go to the emergency room now."


def assert_emergency_only(out: dict):
    assert set(out) - {"_meta"} == {"kind", "emergency"}, "emergency answer must contain nothing but the emergency message"
    assert out["kind"] == "emergency" and out["emergency"]["headline"] == HEADLINE
    text = json.dumps(out["emergency"])
    assert "20 York St" in text and "1450 Chapel St" in text and "(203) 432-7397" in text and "(203) 432-0123" in text
    assert "ID card" in text and "When in doubt, call 911." in text


@pytest.mark.parametrize(
    "text",
    [
        "I have chest pain and I can't breathe",
        "my friend overdosed and is unconscious",
        "worst headache of my life",
        "bad headache and my left arm is weak",
        "headache since I hit my head yesterday",
        "headache with fever and a stiff neck",
        "I had a seizure",
    ],
)
def test_emergency_gets_the_emergency_message_only_and_no_model_call(monkeypatch, text):
    monkeypatch.setattr(agents, "run_agent", lambda *a, **k: pytest.fail("model was called"))
    out = navigator.navigate("student", text)
    assert_emergency_only(out)
    assert out["_meta"]["model_calls"] == 0


def test_a_plain_headache_gets_the_red_flag_list_not_the_emergency_message(monkeypatch):
    monkeypatch.setattr(agents, "run_agent", fake_model(router=router_reply(symptom_present=True, symptom_area="headache", timing="today", intent="care_visit", line_id="acute_care")))
    out = navigator.navigate("student", "I have had a dull headache since this morning")
    assert out["kind"] == "plan"
    net = out["safety_net"]
    assert net["area"] == "headache" and net["closing"] == "Call 911." and net["rule_id"] == "common.safety_net"
    assert net["signs"] == [
        "Sudden, worst headache of your life",
        "Weakness, numbness, trouble speaking, confusion, or vision changes",
        "Fever with stiff neck",
        "Headache after a head injury",
        "Seizure or loss of consciousness",
    ]


def test_back_pain_gets_the_general_red_flag_list_and_a_coverage_question_gets_none(monkeypatch):
    sick = router_reply(symptom_present=True, symptom_area="back_pain", timing="can_wait", intent="care_visit")
    monkeypatch.setattr(agents, "run_agent", fake_model(router=sick))
    assert navigator.navigate("student", "lower back pain")["safety_net"]["area"] == "general"  # no such list: general
    monkeypatch.setattr(agents, "run_agent", fake_model(router=router_reply()))
    assert navigator.navigate("student", "what does my plan cover")["safety_net"] is None


def test_router_reporting_a_red_flag_gives_the_emergency_message_only(monkeypatch):
    calls = []
    monkeypatch.setattr(agents, "run_agent", fake_model(captured=calls, router=router_reply(category="emergency", red_flag_reported=True, symptom_present=True)))
    out = navigator.navigate("staff_faculty", "my vision went blurry and my words are coming out wrong")
    assert_emergency_only(out)
    assert out["_meta"]["model_calls"] == 1 and len(calls) == 1  # coverage and plan agents never ran


@pytest.mark.parametrize("role", list(ROLES))
def test_crisis_goes_to_988_and_911_for_every_role(monkeypatch, role):
    monkeypatch.setattr(agents, "run_agent", lambda *a, **k: pytest.fail("model was called"))
    out = navigator.navigate(role, "I want to kill myself")
    assert out["kind"] == "crisis" and [l["phone"] for l in out["crisis"]["lines"]] == ["988", "911"]
    assert set(out) - {"_meta"} == {"kind", "crisis"}


# 4. Role isolation -----------------------------------------------------------------------------

@pytest.mark.parametrize("role", list(ROLES))
def test_model_only_sees_its_own_role_file_plus_common(monkeypatch, role):
    captured: list = []
    monkeypatch.setattr(agents, "run_agent", fake_model(captured))
    navigator.navigate(role, "lower back pain for weeks, I want physical therapy")
    own = json.loads((ROOT / "data" / f"rules_{role}.json").read_text())
    common = json.loads((ROOT / "data" / "rules_common.json").read_text())
    allowed_facts = {f["id"] for f in own["coverage"] + common["coverage"]}
    allowed_lines = {l["id"] for l in own["lines"] + common["lines"]}
    others = [json.loads((ROOT / "data" / f"rules_{r}.json").read_text()) for r in ROLES if r != role]
    allowed_text = " ".join(f["statement"] for f in own["coverage"] + common["coverage"])
    foreign_text = [
        f["statement"] for o in others for f in o["coverage"] if f["id"] not in allowed_facts and f["statement"] not in allowed_text
    ]
    for _, payload in captured:
        if "rules" in payload:
            assert {f["id"] for f in payload["rules"]} == allowed_facts
        if "available_lines" in payload:
            assert {l["id"] for l in payload["available_lines"]} == allowed_lines
        blob = json.dumps(payload)
        assert not any(t in blob for t in foreign_text)


def test_unknown_role_is_rejected():
    with pytest.raises(ValueError):
        load_rules("alumni")
    res = TestClient(main.app).post("/api/navigate", json={"role": "alumni", "situation": "headache"})
    assert res.status_code == 422


# 5. Guards on model output -----------------------------------------------------------------------

def test_invented_phone_numbers_are_removed(monkeypatch):
    bad = {**PLAN_REPLY, "summary": "Call 555-123-4567 or (203) 432-0246 today.",
           "timeline": [{"when": "Today", "what": "Call 555-123-4567 or (203) 432-0246 today."}]}
    visit = router_reply(symptom_present=True, timing="can_wait", intent="care_visit", line_id="member_services")
    monkeypatch.setattr(agents, "run_agent", fake_model(router=visit, plan=bad))
    out = navigator.navigate("staff_faculty", "I need a checkup")
    text = json.dumps(out["plan"])
    assert "555-123-4567" not in text and "(203) 432-0246" in text and "not verified" in text


def test_allowed_numbers_come_only_from_the_roles_files():
    nums = allowed_numbers(load_rules("visiting_student"))
    assert "8003279240" not in nums  # Magellan is in the staff and dependent files, not here
    assert "2034320290" not in nums  # student-only mental health line


def test_unsupported_coverage_claim_falls_back_to_member_services(monkeypatch):
    monkeypatch.setattr(agents, "run_agent", fake_model())
    out = navigator.navigate("visiting_student", "Is physical therapy free for me?")
    items = out["coverage"]["items"]
    assert items and all(i["status"] == "not_verified" for i in items)
    assert all("(203) 432-0246" in i["answer"] and "ask Yale Health directly" in i["answer"] for i in items)


def test_citing_another_roles_fact_is_not_accepted(monkeypatch):
    def run(instructions, payload):
        if "You are the Coverage" in instructions:
            return {"items": [{"topic": "PT", "answer": "100% covered.", "status": "covered", "rule_ids": ["student.pt_coverage"]}]}
        return fake_model()(instructions, payload)

    monkeypatch.setattr(agents, "run_agent", run)
    out = navigator.navigate("staff_faculty", "physical therapy cost")
    assert out["coverage"]["items"][0]["status"] == "not_verified"
    assert "100%" not in json.dumps(out["coverage"])


def test_unknown_line_from_router_falls_back_to_member_services(monkeypatch):
    def run(instructions, payload):
        if "You are the Router" in instructions:
            return {"line_id": "made_up_line", "reason": "x", "urgency": "routine"}
        return fake_model()(instructions, payload)

    monkeypatch.setattr(agents, "run_agent", run)
    assert navigator.navigate("student", "sore throat")["line"]["id"] == "member_services"


# 5b. Rule files: the only source of truth ---------------------------------------------------------

PREFIX = {"common": "common.", "student": "student.", "staff_faculty": "employee.", "dependent": "dependent.", "visiting_student": "visiting."}


def rule_file(name: str) -> dict:
    return json.loads((ROOT / "data" / f"rules_{name}.json").read_text())


@pytest.mark.parametrize("name", list(PREFIX))
def test_rule_files_have_the_expected_format(name):
    data = rule_file(name)
    assert data["file"] == name
    ids = [f["id"] for f in data["coverage"]]
    assert ids and len(ids) == len(set(ids))
    assert all(i.startswith(PREFIX[name]) for i in ids)
    for fact in data["coverage"]:
        assert {"id", "topic", "statement", "source"} <= set(fact)
    for line in data["lines"]:
        assert {"id", "name", "use_for", "source"} <= set(line)
        assert line.get("phone") or line.get("email") or line.get("kind") == "portal"


def test_common_file_holds_the_shared_facts():
    c = rule_file("common")
    text = json.dumps(c)
    for needle in ["55 Lock Street", "(203) 432-0246", "(203) 432-0123", "Sunday to Saturday, 8 a.m. to 10 p.m.",
                   "Prior authorization is required for all referrals", "pre-existing", "20 York St", "1450 Chapel St",
                   "(203) 432-7397", "member.services@yale.edu", "about two business days"]:
        assert needle in text, needle
    assert c["emergency"]["headline"] == HEADLINE
    assert set(c["red_flags"]) == {"rule_id", "general", "headache"}


def test_student_file_holds_the_student_rules():
    facts = {f["id"]: f["statement"] for f in rule_file("student")["coverage"]}
    assert "(203) 436-5583" in facts["student.ptsmc"]
    assert "100%" in facts["student.pt_coverage"] and "referral from a PCP" in facts["student.pt_coverage"]
    assert "Dry needling" in facts["student.dry_needling"]
    assert "excluded" in facts["student.acupuncture_excluded"] and "anesthesia" in facts["student.acupuncture_excluded"]
    assert "student ID" in facts["student.bring_id"]
    intl = facts["student.international"]
    assert all(x in intl for x in ["J-1/J-2", "evacuation and repatriation", "CISI", "(203) 432-0246"])
    nocov = facts["student.no_coverage"]
    assert all(x in nocov for x in ["911", "Basic Coverage", "alternate plan", "on leave", "never promise free care"])


def test_employee_file_says_at_the_top_what_is_verified_and_missing():
    data = rule_file("staff_faculty")
    assert list(data)[:5] == ["file", "role", "label", "status", "lines"]  # the status block comes before any rule
    status = data["status"]
    assert status["verified"] and status["missing"]
    named = " ".join(status["verified"] + status["verified_but_outside_named_sources"])
    for fact in data["coverage"]:
        assert fact["id"] in named, f"{fact['id']} is not listed as verified in the status block"
    assert "Member Services at (203) 432-0246" in status["rule_for_missing"]


def test_employee_cost_sharing_only_appears_with_a_booklet_source():
    data = rule_file("staff_faculty")
    costed = [f for f in data["coverage"] if "$" in f["statement"] or "%" in f["statement"]]
    assert costed
    for fact in costed:
        assert "Booklet" in fact["source"] and re.search(r"p+\. ?\d+", fact["source"]), fact["id"]


def test_employee_file_is_not_filled_in_from_the_student_file():
    data = rule_file("staff_faculty")
    assert not any(f["id"].startswith("student.") for f in data["coverage"])
    text = json.dumps(data).lower()
    for student_only in ["acupuncture", "dry needling", "student id", "cisi", "(203) 436-5583", "(203) 432-0290"]:
        assert student_only not in text, student_only
    aetna = next(f for f in data["coverage"] if f["id"] == "employee.aetna_after_three_years")
    assert all(x in aetna["statement"] for x in ["three years", "Aetna Smart Care", "Health Savings Account", "Aetna Select"])


@pytest.mark.parametrize("name", ["dependent", "visiting_student"])
def test_dependent_and_visiting_files_stay_small(name):
    data = rule_file(name)
    assert len(data["coverage"]) == 1 and data["lines"] == []
    assert "Member Services" in data["coverage"][0]["statement"]


def test_every_covered_answer_names_the_rules_it_came_from(monkeypatch):
    def run(instructions, payload):
        if "You are the Coverage" in instructions:
            return {"items": [{"topic": "PT", "answer": "Physical therapy is covered 100% with a referral from a PCP.",
                               "status": "conditions", "claim": "Physical therapy is covered 100% under the Yale student health plan with a referral from a PCP.", "rule_ids": ["student.pt_coverage", "common.care_at_center"]}]}
        return fake_model()(instructions, payload)

    monkeypatch.setattr(agents, "run_agent", run)
    item = navigator.navigate("student", "physical therapy")["coverage"]["items"][0]
    assert [r["id"] for r in item["rules"]] == ["student.pt_coverage", "common.care_at_center"]
    assert [r["file"] for r in item["rules"]] == ["student", "common"]
    assert all(r["source"] for r in item["rules"])


def test_no_coverage_item_is_ever_returned_without_a_rule(monkeypatch):
    monkeypatch.setattr(agents, "run_agent", fake_model())
    for role in ROLES:
        for item in navigator.navigate(role, "is this covered?")["coverage"]["items"]:
            assert item["rules"] or item["status"] == "not_verified"


def test_aetna_rule_is_scoped_flagged_and_quoted():
    data = rule_file("staff_faculty")
    fact = next(f for f in data["coverage"] if f["id"] == "employee.aetna_after_three_years")
    scope = "Clerical & Technical, Service & Maintenance, and Security staff only"
    assert fact["scope"] == scope and fact["statement"].startswith("Applies to " + scope[:-5])
    assert "not general staff and faculty coverage" in fact["statement"].replace("This is not general", "not general staff") or "not general" in fact["statement"]
    assert "your.yale.edu" in fact["url"] and "Medical, Dental, & Vision" in fact["source"]
    assert "three years of service" in fact["quote"] and "Aetna Smart Care with a Health Savings Account (HSA) or Aetna Select" in fact["quote"]
    assert "outside_named_sources" in " ".join(data["status"]) and "aetna" in " ".join(data["status"]["verified_but_outside_named_sources"]).lower()


def test_an_answer_that_cites_the_aetna_rule_always_carries_its_scope(monkeypatch):
    def run(instructions, payload):
        if "You are the Coverage" in instructions:
            return {"items": [{"topic": "Aetna", "answer": "You can switch to Aetna after three years.", "status": "conditions",
                               "claim": "After three years of service, these employees may remain a member of Yale Health",
                               "rule_ids": ["employee.aetna_after_three_years"]}]}
        return fake_model()(instructions, payload)

    monkeypatch.setattr(agents, "run_agent", run)
    item = navigator.navigate("staff_faculty", "Can I switch to Aetna?")["coverage"]["items"][0]
    assert item["applies_to"] == ["Clerical & Technical, Service & Maintenance, and Security staff only"]
    assert item["rules"][0]["quote"]


def test_pt_waiver_rule_matches_yales_page_word_for_word():
    fact = next(f for f in rule_file("student")["coverage"] if f["id"] == "student.pt_requires_hospitalization_specialty")
    assert "Students who have waived Yale Health Hospitalization & Specialty Care coverage and Medicare patients are not eligible for treatment in our Physical Therapy Department." in fact["quote"]
    assert "This service is available exclusively for Yale Health members and students with Yale Health Hospitalization & Specialty Care coverage." in fact["quote"]
    assert fact["url"] == "https://yalehealth.yale.edu/department/physical-therapy"


def test_common_file_has_the_crisis_rule_and_the_general_red_flags():
    c = rule_file("common")
    assert c["crisis"]["rule_id"] == "common.crisis" and "not a Yale Health service" in c["crisis"]["label"]
    fact = next(f for f in c["coverage"] if f["id"] == "common.crisis")
    assert all(x in fact["statement"] for x in ["988", "911", "national", "not a Yale Health service"])
    assert c["red_flags"]["general"] == ["Chest pain", "Trouble breathing", "Severe bleeding", "Signs of a stroke", "Any life-threatening symptom"]


def test_crisis_answer_is_labeled_a_national_service(monkeypatch):
    monkeypatch.setattr(agents, "run_agent", lambda *a, **k: pytest.fail("model was called"))
    out = navigator.navigate("student", "I am thinking about suicide")
    assert out["crisis"]["label"] == "988 is a national service, not a Yale Health service." and out["crisis"]["rule_id"] == "common.crisis"


# 5c. The app never diagnoses or recommends treatment --------------------------------------------------

@pytest.mark.parametrize(
    "bad",
    ["This sounds like sciatica.", "You probably have a strain.", "Take ibuprofen and rest.", "Apply ice for 20 minutes.",
     "Try stretching your hamstrings.", "It could be a herniated disc.", "Doctors will diagnose it at the visit."],
)
def test_diagnosis_and_treatment_advice_is_removed_from_plan_and_reason(monkeypatch, bad):
    plan = {"summary": bad, "timeline": [{"when": "Today", "what": bad}, {"when": "On the call", "what": "Have your Yale ID ready."}],
            "do_not_forget": [{"point": bad, "why": "x"}, {"point": "Ask for a referral.", "why": bad}, {"point": "Ask for the PT referral.", "why": "PT needs one."}],
            "checklist": [{"label": bad}, {"label": "Called"}]}
    pt = {"items": [{"topic": "PT", "status": "conditions", "answer": "Covered with a PCP referral.", "claim": "Physical therapy is covered 100% under the Yale student health plan with a referral from a PCP.",
                     "rule_ids": ["student.pt_coverage"]}]}
    sick = router_reply(reason=bad, symptom_present=True, timing="can_wait", intent="care_visit", line_id="student_pcp")
    monkeypatch.setattr(agents, "run_agent", fake_model(router=sick, plan=plan, coverage=pt))
    out = navigator.navigate("student", "my back hurts")
    text = json.dumps({"reason": out["how_it_decided"]["reason"], "plan": out["plan"]})
    assert bad not in text
    assert [t["what"] for t in out["plan"]["timeline"]] == ["Have your Yale ID ready."]
    assert [p["point"] for p in out["plan"]["do_not_forget"]] == ["Ask for the PT referral."]
    assert [c["label"] for c in out["plan"]["checklist"]] == ["Called"]
    assert out["plan"]["summary"] == ""  # a bad summary is dropped; nothing generic takes its place


def test_normal_call_prep_is_not_blocked():
    from safety import violates_safety_net

    for ok in ["Say you are a Yale student with lower back pain that has lasted for weeks.", "Have your Yale ID ready.",
               "Ask for a referral for physical therapy.", "Write down when it started and any medications you take."]:
        assert not violates_safety_net(ok), ok


def test_a_written_channel_is_never_the_first_line(monkeypatch):
    monkeypatch.setattr(agents, "run_agent", fake_model(router=router_reply(line_id="member_services_email", also_consider=["mychart"])))
    out = navigator.navigate("student", "I need an appointment")
    assert out["line"]["id"] == "member_services" and out["line"]["phone"] == "(203) 432-0246"
    assert out["also_consider"][0]["id"] == "mychart" and "phone" not in out["also_consider"][0]


# 6. No health data stored ---------------------------------------------------------------------------

def test_situation_text_is_never_written_anywhere(monkeypatch, tmp_path):
    monkeypatch.setattr(agents, "run_agent", fake_model())
    monkeypatch.setattr(main, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main, "LOG_PATH", tmp_path / "run_log.jsonl")
    sentinel = "ZEBRA-SENTINEL-4471"
    res = TestClient(main.app).post("/api/navigate", json={"role": "student", "situation": f"{sentinel} knee pain"})
    assert res.status_code == 200
    assert res.headers["cache-control"] == "no-store"
    log = (tmp_path / "run_log.jsonl").read_text()
    assert sentinel not in log and "student" in log and "gpt-6-luna" in log
    for path in list(ROOT.rglob("*")) + list(tmp_path.rglob("*")):
        if path.is_file() and not (set(path.parts) & {".venv", ".git", "__pycache__", "tests"}):
            try:
                assert sentinel.encode() not in path.read_bytes(), path
            except PermissionError:
                pass


def test_errors_do_not_echo_the_situation(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise RuntimeError("secret SENTINEL-IN-ERROR")

    monkeypatch.setattr(agents, "run_agent", boom)
    monkeypatch.setattr(main, "LOG_PATH", tmp_path / "run_log.jsonl")
    res = TestClient(main.app).post("/api/navigate", json={"role": "student", "situation": "SENTINEL-IN-ERROR headache"})
    assert res.status_code == 502 and "SENTINEL-IN-ERROR" not in res.text
    assert "SENTINEL-IN-ERROR" not in (tmp_path / "run_log.jsonl").read_text()


def test_frontend_stores_nothing_in_the_browser():
    html = (ROOT / "frontend" / "index.html").read_text()
    assert not re.search(r"localStorage|sessionStorage|indexedDB|document\.cookie", html)


# 7. Live check (needs a key; skipped otherwise) ----------------------------------------------------

@pytest.mark.skipif(not os.environ.get("PORTKEY_API_KEY"), reason="no PORTKEY_API_KEY found in .env")
def test_live_student_physical_therapy():
    out = navigator.navigate("student", "lower back pain for weeks, I want physical therapy")
    rules = load_rules("student")
    assert out["line"]["id"] in rules.line_ids
    allowed = allowed_numbers(rules)
    for number in PHONE.findall(json.dumps(out)):
        assert re.sub(r"\D", "", number).lstrip("1") in allowed or re.sub(r"\D", "", number) in allowed
    assert out["coverage"]["items"] and out["plan"]["do_not_forget"] and out["plan"]["timeline"]


LIVE = pytest.mark.skipif(not os.environ.get("PORTKEY_API_KEY"), reason="no PORTKEY_API_KEY found in .env")


def rule_ids_ok(out: dict, role: str):
    rules = load_rules(role)
    for item in out["coverage"]["items"]:
        assert all(r["id"] in rules.fact_ids for r in item["rules"])
        assert item["rules"] or item["status"] == "not_verified"


@LIVE
def test_live_staff_physical_therapy_gives_every_plan_groups_cost():
    out = navigator.navigate("staff_faculty", "I need physical therapy for my knee. What will it cost me?")
    if out["kind"] != "plan":
        pytest.skip("treated as an emergency")
    rule_ids_ok(out, "staff_faculty")
    text = json.dumps(out["coverage"])
    assert "$20" in text and "100%" in text


@LIVE
def test_live_visiting_student_gets_no_student_rules():
    out = navigator.navigate("visiting_student", "Is physical therapy covered for me?")
    rule_ids_ok(out, "visiting_student")
    assert not any(r["file"] == "student" for i in out["coverage"]["items"] for r in i["rules"])
    assert "100%" not in json.dumps(out["coverage"]) or all(i["status"] == "not_verified" for i in out["coverage"]["items"])


@LIVE
def test_live_student_with_no_insurance_is_sent_to_member_services_without_a_promise():
    out = navigator.navigate("student", "I have no insurance and my knee hurts when I walk", timing="can_wait")
    rule_ids_ok(out, "student")
    text = json.dumps(out)
    assert "(203) 432-0246" in text
    assert not re.search(r"(is|are|will be|be) free|free of charge|at no cost|no charge", json.dumps(out["coverage"]).lower())


# Dental: one common rule, from Yale's own pages, with no yearly prices ----------------------------------------------

def test_the_dental_rule_is_in_the_common_file_and_every_role_sees_it_without_prices():
    import re as _re
    rule = next(f for f in json.load(open(ROOT / "data" / "rules_common.json"))["coverage"] if f["id"] == "common.dental")
    text = rule["statement"]
    for needle in ["does not offer dental insurance for adults", "Delta Dental plan (enrollment is once a year, online)", "faculty and staff can buy a dental plan with partial coverage",
                   "Delta Dental of Connecticut", "automatically enrolled", "any hospital emergency room", "ask Member Services at (203) 432-0246"]:
        assert needle in text, needle
    assert not _re.search(r"\$\s?\d|\d\s?%|premium of|copay of", text)  # no premium amounts or copay percentages: they change yearly
    for source in ("OISS Dental & Vision Care", "Student Guide", "gradprofdenteye.yale.edu"):
        assert source in rule["source"], source
    assert rule["url"].startswith("https://oiss.yale.edu/")
    for role in ROLES:
        assert any(f["id"] == "common.dental" for f in load_rules(role).facts), role  # common rules reach every role
    assert agents.lookup_rules(load_rules("staff_faculty"), "Is dental covered?")[0]["id"] == "common.dental"
