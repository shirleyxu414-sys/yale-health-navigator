"""The router -> coverage -> plan flow, the one response shape, and the frontend contract. All offline."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import agents
import main
import models
import navigator
from models import Answer
from rules import ROLES, load_rules
from test_safety import COVERAGE_REPLY, PLAN_REPLY, fake_model, router_reply

ROOT = Path(__file__).resolve().parents[1]
WHEN = ["Today", "On the call", "This week", "After the referral"]

PT_ROUTER = router_reply(symptom_present=True, symptom_area="general", timing="can_wait", intent="care_visit", line_id="student_pcp")
PT_COVERAGE = {"items": [{"topic": "Physical therapy", "answer": "Covered 100% with a PCP referral.", "status": "conditions",
                          "condition": "Needs a PCP referral.", "excluded": None, "claim": "Physical therapy is covered 100% under the Yale student health plan with a referral from a PCP.", "rule_ids": ["student.pt_coverage"]}]}


def run(monkeypatch, role="student", text="lower back pain for weeks, I want physical therapy", **kw):
    monkeypatch.setattr(agents, "run_agent", fake_model(**{"router": PT_ROUTER, "coverage": PT_COVERAGE, **kw.pop("model", {})}))
    return navigator.navigate(role, text, **kw)


# 1. The router --------------------------------------------------------------------------------

def test_router_output_names_role_rule_files_category_and_phone(monkeypatch):
    out = run(monkeypatch)
    how = out["how_it_decided"]
    assert how["role_id"] == "student" and how["role_label"] == "Yale student"
    assert how["rule_files"] == ["rules_student.json", "rules_common.json"]
    assert how["category"] == "routine" and how["category_label"] == "Routine PCP visit"
    assert how["line_id"] == "student_pcp" and how["contact"] == "(203) 432-0246"
    assert out["line"]["phone"] == "(203) 432-0246"


@pytest.mark.parametrize("role", ["staff_faculty", "dependent", "visiting_student"])
def test_each_role_gets_its_own_rule_file(monkeypatch, role):
    out = run(monkeypatch, role=role, model={"router": router_reply(symptom_present=True, timing="can_wait", intent="care_visit", line_id="student_pcp")})
    assert out["how_it_decided"]["rule_files"] == [f"rules_{role}.json", "rules_common.json"]
    assert out["line"]["id"] == "member_services"  # only students have a student primary care line


def test_symptom_with_unknown_timing_builds_the_plan_for_today_and_says_it_assumed_it(monkeypatch):
    out = run(monkeypatch, model={"router": router_reply(symptom_present=True, symptom_area="headache", timing="unknown", intent="care_visit")})
    assert out["kind"] == "plan" and out["timing_assumed"] is True
    assert out["how_it_decided"]["category"] == "urgent" and out["line"]["id"] == "acute_care"  # today is the safe default
    assert "ask" not in out


def test_explicit_timing_builds_the_plan_with_no_assumption_flag(monkeypatch):
    for timing in ("today", "can_wait"):
        out = run(monkeypatch, model={"router": router_reply(symptom_present=True, symptom_area="headache", timing=timing, intent="care_visit")})
        assert out["kind"] == "plan" and out.get("timing_assumed") is None
    given = run(monkeypatch, timing="can_wait", model={"router": router_reply(symptom_present=True, symptom_area="headache", timing="unknown", intent="care_visit")})
    assert given["how_it_decided"]["category"] == "routine" and given.get("timing_assumed") is None  # the button's request is explicit


def test_a_question_with_no_symptom_is_not_given_a_timing_assumption(monkeypatch):
    out = run(monkeypatch)  # the physical therapy case
    assert out.get("timing_assumed") is None


def test_an_answer_to_the_question_routes_same_day_to_acute_care_and_routine_to_primary_care(monkeypatch):
    sick = router_reply(symptom_present=True, symptom_area="headache", timing="unknown", intent="care_visit", line_id="student_pcp")
    today = run(monkeypatch, text="I have a headache", timing="today", model={"router": sick})
    assert today["line"]["id"] == "acute_care" and today["how_it_decided"]["category"] == "urgent"
    assert today["how_it_decided"]["category_label"] == "Urgent care (same day)"
    later = run(monkeypatch, text="I have a headache", timing="can_wait", model={"router": {**sick, "line_id": "acute_care"}})
    assert later["line"]["id"] == "student_pcp" and later["how_it_decided"]["category"] == "routine"


def test_the_router_cannot_send_a_routine_symptom_to_acute_care_or_an_urgent_one_to_the_pcp(monkeypatch):
    wrong = run(monkeypatch, model={"router": {**PT_ROUTER, "line_id": "acute_care"}})
    assert wrong["line"]["id"] == "student_pcp"
    urgent = run(monkeypatch, timing="today", model={"router": {**PT_ROUTER, "line_id": "student_pcp"}})
    assert urgent["line"]["id"] == "acute_care"


def test_a_referral_holder_is_routed_to_ptsmc_and_the_referral_button_goes_away(monkeypatch):
    first = run(monkeypatch)
    assert any(g.get("action") == "has_referral" for g in first["plan"]["if_not_as_planned"])
    second = run(monkeypatch, has_referral=True, model={"router": {**PT_ROUTER, "line_id": "ptsmc", "has_referral": True}})
    assert second["line"]["id"] == "ptsmc" and second["line"]["phone"] == "(203) 436-5583"
    assert not any(g.get("action") for g in second["plan"]["if_not_as_planned"])
    assert "referral" in " ".join(g["problem"] for g in second["plan"]["if_not_as_planned"]).lower()


def test_the_plan_builder_never_gets_the_raw_situation_text(monkeypatch):
    calls: list = []
    monkeypatch.setattr(agents, "run_agent", fake_model(captured=calls, router=PT_ROUTER, coverage=PT_COVERAGE))
    navigator.navigate("student", "ZEBRA-SENTINEL-9 lower back pain")
    plan_payloads = [p for ins, p in calls if "You are the Plan Builder" in ins]
    assert plan_payloads and "ZEBRA-SENTINEL-9" not in json.dumps(plan_payloads)
    assert "coverage_items" in plan_payloads[0] and "chosen_line" in plan_payloads[0]


def test_the_coverage_checker_gets_the_category_and_what_the_person_wants(monkeypatch):
    calls: list = []
    monkeypatch.setattr(agents, "run_agent", fake_model(captured=calls, router=PT_ROUTER, coverage=PT_COVERAGE))
    navigator.navigate("student", "lower back pain for weeks, I want physical therapy")
    payload = next(p for ins, p in calls if "You are the Coverage Checker" in ins)
    assert payload["category"] == "routine" and payload["wants"] == "physical therapy"


# 2. The coverage checker ------------------------------------------------------------------------

def test_coverage_items_carry_condition_excluded_and_the_rule(monkeypatch):
    item = run(monkeypatch)["coverage"]["items"][0]
    assert item["status"] == "conditions" and item["condition"] == "Needs a PCP referral." and item["excluded"] is None
    assert [r["id"] for r in item["rules"]] == ["student.pt_coverage"]


def test_a_question_the_rules_do_not_answer_gets_i_dont_know_and_member_services(monkeypatch):
    out = run(monkeypatch, role="visiting_student", model={"router": router_reply(), "coverage": {"items": [
        {"topic": "PT", "answer": "Yes, covered.", "status": "covered", "rule_ids": ["student.pt_coverage"]}]}})
    item = out["coverage"]["items"][0]
    assert item["status"] == "not_verified" and "I don't know" in item["answer"] and "(203) 432-0246" in item["answer"]
    assert item["rules"] == []


# 3. The plan builder -----------------------------------------------------------------------------

def test_plan_has_every_section_and_a_fixed_write_down_list(monkeypatch):
    plan = run(monkeypatch)["plan"]
    assert plan["write_down"] == ["Date and time of the appointment", "Referral details", "Name of the person you spoke to"]
    assert plan["timeline"] and plan["do_not_forget"] and plan["checklist"] and plan["if_not_as_planned"]
    problems = [g["problem"] for g in plan["if_not_as_planned"]]
    assert problems[:2] == ["The line is busy or closed", "No appointments soon"] and problems[2] == "After your PCP visit"


def test_timeline_is_ordered_and_limited_to_the_four_stages(monkeypatch):
    messy = {**PLAN_REPLY, "timeline": [
        {"when": "After the referral", "what": "Book PTSMC."}, {"when": "Today", "what": "Call the line."},
        {"when": "Next month", "what": "Nope."}, {"when": "This week", "what": "Go to the visit."}, {"when": "On the call", "what": "Get the referral."}]}
    steps = run(monkeypatch, model={"plan": messy})["plan"]["timeline"]
    assert [s["when"] for s in steps] == ["Today", "On the call", "This week", "After the referral"]


def test_do_not_forget_is_two_to_three_points_each_with_a_why_and_never_a_script(monkeypatch):
    many = {**PLAN_REPLY, "do_not_forget": [
        {"point": "Say \"I need a referral for physical therapy\"", "why": "So they hear it."},
        {"point": "Tell them you have back pain.", "why": "So they know."},
        {"point": "Ask for the PT referral.", "why": "PT is covered 100% only with one."},
        {"point": "Ask whether PTSMC offers dry needling.", "why": "It is covered under a referral, but only if you ask."},
        {"point": "Bring your student ID.", "why": "It is needed at appointments."},
        {"point": "Ask about something else.", "why": "A fourth point."}]}
    points = run(monkeypatch, model={"plan": many})["plan"]["do_not_forget"]
    assert [p["point"] for p in points] == ["Ask for the PT referral.", "Ask whether PTSMC offers dry needling.", "Bring your student ID."]
    assert all(p["why"] for p in points)
    assert not any(re.search(r"[\"“]|^(say|tell them)\b", p["point"] + p["why"], re.I) for p in points)


def test_if_things_go_wrong_help_uses_numbers_from_the_rules(monkeypatch):
    rules = load_rules("student")
    text = json.dumps(run(monkeypatch)["plan"]["if_not_as_planned"])
    assert "(203) 432-0123" in text and "(203) 432-0246" in text
    from safety import PHONE, allowed_numbers
    assert all(re.sub(r"\D", "", n).lstrip("1") in allowed_numbers(rules) for n in PHONE.findall(text))


# 4. "Email or MyChart drafts" ------------------------------------------------------------------------------

def test_email_draft_only_for_coverage_and_administrative_questions(monkeypatch):
    out = run(monkeypatch, text="Is PT covered?", model={"router": router_reply(intent="administrative", wants="physical therapy")})
    pw = out["prefer_writing"]
    assert pw["email"]["to"] == "member.services@yale.edu" and "physical therapy" in pw["email"]["subject"]
    assert pw["mychart"] is None
    assert "Never" not in pw["email"]["body"] and "[Your name]" in pw["email"]["body"]


def test_mychart_draft_only_for_a_non_urgent_care_team_message(monkeypatch):
    out = run(monkeypatch, text="Question for my care team", model={"router": router_reply(intent="care_team_message", wants="my care plan")})
    assert out["prefer_writing"]["mychart"] and out["prefer_writing"]["email"] is None


def test_no_draft_for_symptoms_appointments_or_urgent_issues(monkeypatch):
    for router in [
        PT_ROUTER,  # a symptom and an appointment
        router_reply(symptom_present=True, intent="administrative", timing="can_wait"),  # a symptom is never administrative
        router_reply(symptom_present=True, intent="care_team_message", timing="can_wait"),
        router_reply(intent="care_visit", wants="an appointment"),
    ]:
        pw = run(monkeypatch, model={"router": router})["prefer_writing"]
        assert pw["email"] is None and pw["mychart"] is None
    urgent = run(monkeypatch, timing="today", model={"router": router_reply(symptom_present=True, intent="care_visit")})
    assert urgent["prefer_writing"]["email"] is None and urgent["prefer_writing"]["mychart"] is None


def test_drafts_carry_no_health_detail_and_the_warnings_are_always_shown(monkeypatch):
    out = run(monkeypatch, text="ZEBRA-SENTINEL-7 Is PT covered?", model={"router": router_reply(intent="administrative", wants="physical therapy")})
    pw = out["prefer_writing"]
    assert "ZEBRA-SENTINEL-7" not in json.dumps(pw)
    assert pw["warnings"] == [
        "MyChart replies take about two business days.",
        "Member Services hours: Monday-Friday, 8:30 a.m.-5:00 p.m.",
    ]
    assert run(monkeypatch)["prefer_writing"]["warnings"] == pw["warnings"]


def test_a_draft_topic_that_names_a_condition_is_replaced(monkeypatch):
    out = run(monkeypatch, model={"router": router_reply(intent="administrative", wants="sciatica coverage")})
    assert "sciatica" not in json.dumps(out["prefer_writing"]) and "my question" in out["prefer_writing"]["email"]["subject"]


# 5. One response shape -----------------------------------------------------------------------------

@pytest.mark.parametrize("scenario", ["plan", "emergency", "crisis"])
def test_every_kind_of_answer_fits_the_one_shape_and_leaves_out_what_does_not_apply(monkeypatch, scenario):
    client = TestClient(main.app)
    monkeypatch.setattr(agents, "run_agent", fake_model(router=PT_ROUTER, coverage=PT_COVERAGE))
    text = {"plan": "lower back pain for weeks, I want physical therapy",
            "emergency": "I have chest pain", "crisis": "I want to end my life"}[scenario]
    res = client.post("/api/navigate", json={"role": "student", "situation": text})
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == scenario
    Answer.model_validate(body)
    assert "_meta" not in body
    expected = {"plan": {"kind", "how_it_decided", "line", "also_consider", "plan", "coverage", "safety_net", "prefer_writing", "chat_context", "place", "referral_help", "glossary", "disclaimer"},
                "emergency": {"kind", "emergency"}, "crisis": {"kind", "crisis"}}[scenario]
    assert set(body) <= expected and {"kind", scenario} <= set(body)


def test_timing_must_be_one_of_the_two_answers():
    res = TestClient(main.app).post("/api/navigate", json={"role": "student", "situation": "headache", "timing": "maybe"})
    assert res.status_code == 422


def test_the_run_log_gets_kind_and_line_but_no_text(monkeypatch, tmp_path):
    monkeypatch.setattr(agents, "run_agent", fake_model(router=PT_ROUTER, coverage=PT_COVERAGE))
    monkeypatch.setattr(main, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main, "LOG_PATH", tmp_path / "run_log.jsonl")
    TestClient(main.app).post("/api/navigate", json={"role": "student", "situation": "ZEBRA-SENTINEL-5 back pain, physical therapy"})
    record = json.loads((tmp_path / "run_log.jsonl").read_text())
    assert record["kind"] == "plan" and record["line_id"] == "student_pcp" and record["model_calls"] == 3
    assert "ZEBRA-SENTINEL-5" not in json.dumps(record)


# 6. The frontend only reads fields the backend sends ---------------------------------------------

ROOTS = {
    "data": models.Answer, "how": models.Decision, "plan": models.Plan, "cov": models.Coverage, "item": models.CoverageItem,
    "rule": models.RuleRef, "step": models.TimelineStep, "pt": models.DoNotForget, "gw": models.GoWrong,
    "pw": models.PreferWriting, "draft": models.Draft, "em": models.Emergency, "cr": models.Crisis,
    "ev": models.CalendarEvent, "chat": models.ChatReply, "place": models.Place, "gl": models.GlossaryEntry, "help": models.ReferralHelp, "hp": models.HelpPoint, "ans": models.ReferralAnswer, "line": models.Line, "net": models.SafetyNet, "site": models.ErSite, "cl": models.ChecklistItem,
}


def page_script() -> str:
    return re.search(r"<script>(.*)</script>", (ROOT / "frontend" / "index.html").read_text(), re.S).group(1)


def test_every_field_the_page_reads_exists_in_the_response_models():
    js = page_script()
    for root, model in ROOTS.items():
        for field in set(re.findall(rf"\b{root}\.(\w+)", js)):
            assert field in model.model_fields, f"the page reads {root}.{field} but {model.__name__} has no such field"


def test_every_field_the_backend_can_send_is_used_by_the_page():
    js = page_script()
    unused = {f"{model.__name__}.{field}" for root, model in ROOTS.items() for field in model.model_fields
              if not re.search(rf"\b{root}\.{field}\b", js)}
    # Ids and codes that the page does not need to show; Decision.reason is shown through data.how_it_decided.reason.
    assert unused <= {"Decision.role_id", "Decision.category", "Decision.line_id", "Decision.reason", "Line.id", "Line.kind",
                      "Emergency.rule_id", "Crisis.rule_id", "SafetyNet.area", "RuleRef.quote", "ChatReply.role", "ChatReply.options", "GlossaryEntry.term", "CoverageItem.condition", "ReferralAnswer.department", "ReferralAnswer.rule", "SafetyNet.rule_id"}, unused  # RuleRef.quote and CoverageItem.condition stay in the data (the plan builder and the audit use them); the card shows the verdict and the verified claim instead


def test_the_page_handles_every_kind_of_answer():
    js = page_script()
    for kind in ("plan", "emergency", "crisis"):
        assert kind in js or kind == "plan"
    assert 'data.kind === "emergency"' in js and 'data.kind === "crisis"' in js


def test_the_page_has_every_section_chip_and_button_that_was_asked_for():
    html = (ROOT / "frontend" / "index.html").read_text()
    for needle in ["Your timeline", "Do not forget to mention", "Write down", "Checklist", "What your plan covers",
                   "If things do not go as planned", "Print plan", "How it decided", "Common questions", "Email or MyChart drafts",
                   "I have my referral", "Copy text", "window.print()", 'type = "checkbox"']:
        assert needle in html, needle
    for chip in ["Is PT covered?", "Is acupuncture covered?", "I have a headache", "I don't have insurance",
                 "What if it's after hours?", "I already have a referral"]:
        assert f'"{chip}"' in html, chip
    assert "Who are you at Yale?" in html


def test_the_page_never_sends_email_and_has_no_script_text():
    html = (ROOT / "frontend" / "index.html").read_text()
    assert "mailto:" in html and "sendmail" not in html.lower() and "smtp" not in html.lower()
    assert not re.search(r"\bSay this\b|\bsay:", html, re.I)
