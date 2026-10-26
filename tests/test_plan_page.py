"""The restructured plan page: the call line as the hero, a colour-coded verdict, a short first screen, sections that open on tap,
no repeated coverage fact, and a plan that fits the question. All offline."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import agents
import navigator
from agents import FILLER, plan_agent
from models import CoverageItem
from rules import load_rules
from sections import ADMIN_WRITE_DOWN, WRITE_DOWN
from test_flow import PT_COVERAGE, PT_ROUTER, run
from test_safety import PLAN_REPLY, fake_model, router_reply
from test_site import CSS, HTML, SCRIPT, block, fixtures as base_fixtures, needs_node, node_run, shape

ROOT = Path(__file__).resolve().parents[1]
ACUPUNCTURE = {"items": [{"topic": "Acupuncture", "status": "not_covered", "answer": "Acupuncture is excluded under the Yale student health plan.",
                          "condition": None, "excluded": "The only exception is as a substitute for anesthesia.",
                          "claim": "Acupuncture is excluded under the Yale student health plan.", "rule_ids": ["student.acupuncture_excluded"]}]}
ADMIN = router_reply(intent="administrative", wants="acupuncture", symptom_present=False)
CHATTY_PLAN = {
    "summary": "Call the line above and describe in your own words what you are experiencing.",
    "timeline": [{"when": "Today", "what": "Call (203) 432-0246."}, {"when": "After the referral", "what": "Book PTSMC."}],
    "do_not_forget": [{"point": "Ask for a referral.", "why": "The referral is required to book physical therapy."},
                      {"point": "Describe what you are experiencing.", "why": "So they know."},
                      {"point": "Ask what you need before you are seen, such as a referral.", "why": "Some services need one first."}],
    "checklist": [{"label": "Called"}, {"label": "Referral received"}, {"label": "Booked"}],
}


def admin_plan(monkeypatch, coverage, plan=None, router=None):
    monkeypatch.setattr(agents, "run_agent", fake_model(router=router or ADMIN, plan=plan or CHATTY_PLAN, coverage=coverage))
    return navigator.navigate("student", "Is acupuncture covered?")


# 1. The hero ----------------------------------------------------------------------------------------------

def px(rule: str, prop: str, css: str = CSS) -> int:
    return int(re.search(rf"{re.escape(rule)}\s*\{{[^}}]*\b{prop}:\s*(\d+)px", css).group(1))


def test_the_call_line_is_the_hero_larger_and_stronger_than_every_other_card():
    base = CSS[:CSS.index("/* Media queries come last")]
    assert px(".callhero .phone", "font-size", base) >= 1.5 * px(".phone", "font-size", base)  # the number is much bigger than any other phone number
    assert px(".callhero .linename", "font-size", base) > 17
    hero = re.search(r"\.callhero \{([^}]*)\}", base).group(1)
    assert "background: var(--yale)" in hero and "color: var(--white)" in hero  # solid Yale blue with white text
    assert int(re.search(r"padding: (\d+)px", hero).group(1)) > px(".card", "padding", base)
    assert "box-shadow" in hero and re.search(r"rgba\(0, 53, 107, \.[23]\d", hero)  # a stronger shadow than the cards
    parts = SCRIPT[SCRIPT.index("function renderPlan(data)"):SCRIPT.index("function render(data)")]
    assert parts.index("renderCall(data)") < parts.index("renderCoverage(") < parts.index("renderChecklist(plan)")


def test_the_hero_stays_readable_when_printed_and_shrinks_on_a_phone():
    printing = block(CSS, "@media print")
    assert ".callhero { background: var(--white) !important" in printing and "color: var(--ink) !important" in printing
    phone = block(CSS, "@media (max-width: 560px)")
    assert re.search(r"\.callhero \.phone \{ font-size: (3\d)px", phone)


# 2. The verdict pill --------------------------------------------------------------------------------------

def test_the_verdict_pill_has_three_colour_coded_answers_and_a_fourth_for_unknown():
    assert 'covered: "Covered", conditions: "Covered with conditions", not_covered: "Not covered", not_verified: "Not in the rules"' in SCRIPT
    colours = {}
    for status in ("covered", "conditions", "not_covered", "not_verified"):
        rule = re.search(rf"\.pill\.{status} \{{ ([^}}]*)\}}", CSS).group(1)
        colours[status] = re.search(r"background: ([^;]+);", rule).group(1) + "/" + re.search(r"color: ([^;]+);", rule).group(1)
    assert len(set(colours.values())) == 4, colours  # every answer has its own colours
    assert colours["not_covered"].startswith("var(--alert-bg)") and colours["covered"].startswith("var(--ok-bg)")
    assert re.search(r"\.verdict \.pill \{[^}]*font-size: 14px", CSS)  # bigger on the first screen


def test_the_model_can_say_not_covered_and_the_verifier_accepts_it(monkeypatch):
    out = admin_plan(monkeypatch, ACUPUNCTURE)
    item = out["coverage"]["items"][0]
    assert item["status"] == "not_covered" and item["rules"][0]["id"] == "student.acupuncture_excluded"
    CoverageItem.model_validate(item)
    ungrounded = {"items": [{**ACUPUNCTURE["items"][0], "claim": "Acupuncture is covered for every student."}]}
    assert admin_plan(monkeypatch, ungrounded)["coverage"]["items"][0]["status"] == "not_verified"


def test_the_coverage_prompt_defines_not_covered():
    assert '"not_covered" (a rule states it is excluded or not covered' in (ROOT / "backend" / "prompts" / "coverage.md").read_text()


# 3. A short first screen and sections that open on tap ----------------------------------------------------------

@needs_node
def test_the_first_screen_is_the_call_line_the_coverage_verdict_and_the_checklist(monkeypatch):
    out = node_run("layout", base_fixtures(monkeypatch))
    titles = [(t["cls"].split()[0], t["title"]) for t in out["top"] if t["cls"].split()[0] not in ("dogsays", "callsub")]  # the bulldog's line and the subline are not cards
    assert titles[0] == ("callhero", "Call this line")
    assert titles[1][0] == "card" and titles[1][1].startswith("What your plan covers")
    assert titles[2] == ("card", "Checklist")
    assert out["hasPrint"] and out["hasChatBtn"] is False  # Print lives at the end; chat is the floating button


@needs_node
def test_three_sections_start_closed_and_the_rest_are_open(monkeypatch):
    out = node_run("layout", base_fixtures(monkeypatch))
    collapsed = {t["title"]: t["open"] for t in out["top"] if t["tag"] == "details"}
    assert collapsed == {"Track your referral": False, "Your PCP": False,
                         "If things do not go as planned": False, "Email or MyChart drafts": False, "How it decided": False}  # all closed until tapped
    assert all("collapse" in t["cls"] for t in out["top"] if t["tag"] == "details")
    order = [t["title"] for t in out["top"]]
    assert order.index("Your timeline") < order.index("If things do not go as planned") < order.index("Email or MyChart drafts") < order.index("How it decided")


def test_the_closed_sections_are_real_details_elements_that_open_on_tap_and_the_print_one_opens_for_printing():
    assert 'el("details", "card collapse " + (extraClass || ""))' in SCRIPT
    assert 'collapsible("If things do not go as planned", [sec], "printable")' in SCRIPT
    assert 'collapsible("Email or MyChart drafts", [inner], "printable")' in SCRIPT and re.search(r'collapsible\("How it decided", \[[^;]*\], "printable appendix"\)', SCRIPT)
    assert '"beforeprint"' in SCRIPT and '"afterprint"' in SCRIPT and "showSheetForPrint" in SCRIPT and "hideSheetAfterPrint" in SCRIPT
    assert re.search(r"details\.collapse > summary \{[^}]*cursor: pointer", CSS) and re.search(r"details\.collapse > summary:focus-visible", CSS)


# 4. The coverage fact is not repeated -----------------------------------------------------------------------------

def dedupe_fixture(monkeypatch) -> dict:
    plan = base_fixtures(monkeypatch)["plan"]
    item = plan["coverage"]["items"][0]
    item["answer"] = "Physical therapy is covered 100% under the Yale student health plan with a referral from a PCP."
    item["claim"] = "Physical therapy is covered 100% under the Yale student health plan with a referral from a PCP."
    item["condition"] = "with a referral from a PCP"  # already said in the answer
    item["excluded"] = "Students who waived Hospitalization & Specialty Care coverage are not eligible."  # new information
    item["rules"][0]["quote"] = "QUOTE-SENTINEL a long second quote of the same rule"
    return {"dedupe": plan, "plan": plan}


@needs_node
def test_the_coverage_card_is_the_verdict_and_one_quote_with_no_rule_lines_or_condition(monkeypatch):
    out = node_run("dedupe", dedupe_fixture(monkeypatch))
    card = out["cardText"]
    assert len(out["quotes"]) == 1 and out["quotes"][0].startswith("From the rules: Physical therapy is covered 100%")
    assert "Condition:" not in card  # the verdict sentence already says the condition
    assert "QUOTE-SENTINEL" not in out["text"] and "Exact source line" not in out["text"]
    assert out["text"].count("Physical therapy is covered 100% under the Yale student health plan with a referral from a PCP.") == 2  # the verdict sentence and its quote
    assert "Excluded: Students who waived" in card  # new information still shows
    assert out["cardRuleLines"] == [] and "Rule student.pt_coverage" not in card and "Project owner" not in out["text"]  # no ids, no files, no sources on the card
    assert [p[1] for p in out["pills"]] == ["Covered with conditions"]


@needs_node
def test_the_rule_id_file_and_source_are_in_the_closed_how_it_decided_panel(monkeypatch):
    out = node_run("dedupe", dedupe_fixture(monkeypatch))
    assert out["how"]["open"] is False and out["how"]["title"] == "How it decided"
    lines = out["howRuleLines"]
    assert lines and lines[0].startswith("Rule student.pt_coverage (student file). Source: ") and len(lines) == len(set(lines))
    assert "Rules behind the answers" in out["howText"] and "Physical therapy" in out["howText"]


def test_the_page_no_longer_prints_rule_lines_on_the_card():
    item_box = SCRIPT[SCRIPT.index("function itemBox"):SCRIPT.index("function renderCoverage")]
    assert "ruleRow" not in item_box and "rule.quote" not in item_box and "Condition" not in item_box and "item.rules" not in item_box
    assert "Excluded: " in item_box and "From the rules: " in item_box and "Applies to: " in item_box  # what must stay: the evidence and the scope
    how = SCRIPT[SCRIPT.index("function renderHow"):SCRIPT.index("function clearWritten")]
    assert "ruleRow(r)" in how and "data.coverage.items" in how and "net.rule" in how  # coverage, warning list, explanations and referral help


# 5. A plan that fits the question ------------------------------------------------------------------------------------

def test_a_coverage_only_question_gets_no_timeline_filler_or_referral_reminder(monkeypatch):
    out = admin_plan(monkeypatch, ACUPUNCTURE)
    plan = out["plan"]
    assert plan["timeline"] == [] and plan["checklist"] == [] or all("referral" not in c["label"].lower() for c in plan["checklist"])
    assert plan["summary"] == ""  # the model's filler summary is dropped, and nothing generic replaces it
    text = json.dumps(plan).lower()
    for banned in ["referral", "describe", "experiencing", "own words", "line above", "some services need one first", "before you are seen"]:
        assert banned not in text, banned
    assert plan["calendar"] == [] and plan["write_down"] == ADMIN_WRITE_DOWN
    assert [g["problem"] for g in plan["if_not_as_planned"]] == ["The line is busy or closed"]


def test_a_referral_reminder_stays_when_a_rule_says_a_referral_matters(monkeypatch):
    out = admin_plan(monkeypatch, PT_COVERAGE, router=router_reply(intent="administrative", wants="physical therapy"))
    plan = out["plan"]
    assert plan["timeline"] == []  # still a coverage question: no steps
    assert [p["point"] for p in plan["do_not_forget"]] == ["Ask for a referral."]  # filler points are gone, the real one stays
    assert [c["label"] for c in plan["checklist"]] == ["Called", "Referral received"]  # two items at most, and the referral one is allowed here


def test_a_care_visit_keeps_its_timeline_but_not_a_referral_step_no_rule_calls_for(monkeypatch):
    acute = {"items": [{"topic": "Acute Care", "status": "covered", "answer": "Acute Care is open Sunday to Saturday.",
                        "claim": "Acute Care is open Sunday to Saturday, 8 a.m. to 10 p.m., for urgent same-day needs.", "rule_ids": ["common.acute_care_hours"]}]}
    sick = router_reply(symptom_present=True, timing="today", intent="care_visit", line_id="acute_care", wants="care today")
    monkeypatch.setattr(agents, "run_agent", fake_model(router=sick, plan=CHATTY_PLAN, coverage=acute))
    plan = navigator.navigate("student", "I need care today")["plan"]
    assert [t["when"] for t in plan["timeline"]] == ["Today"]  # "After the referral" is dropped: no rule here mentions a referral
    written_by_the_model = json.dumps([plan["summary"], plan["timeline"], plan["do_not_forget"], plan["checklist"]]).lower()
    assert "referral" not in written_by_the_model


def test_a_care_visit_with_nothing_usable_from_the_model_still_gets_one_concrete_step(monkeypatch):
    empty = {"summary": "", "timeline": [], "do_not_forget": [], "checklist": []}
    out = run(monkeypatch, model={"plan": empty})
    assert out["plan"]["timeline"] == [{"when": "Today", "what": "Call (203) 432-0246."}]  # a real step from the chosen line, not filler
    assert out["plan"]["do_not_forget"] == [] and out["plan"]["checklist"] == [] and out["plan"]["summary"] == ""


def test_the_filler_check_catches_the_old_generic_wording():
    for filler in ["Call the line above and describe in your own words what you are experiencing.", "Describe what you are experiencing.",
                   "Tell them your situation.", "Ask what you need before you are seen, such as a referral.", "Some services need one first."]:
        assert FILLER.search(filler), filler
    for fine in ["Call (203) 432-0246 to book a primary care visit.", "Ask for the PT referral.", "Bring a student ID."]:
        assert not FILLER.search(fine), fine
    source = (ROOT / "backend" / "agents.py").read_text()
    assert "GENERIC_SUMMARY" not in source and "Call the line above and describe" not in source and "Ask what you need before you are seen, such as a referral" not in source.split("FILLER = re.compile(")[0]


def test_the_plan_builder_is_told_the_kind_of_question_and_whether_a_referral_matters(monkeypatch):
    calls: list = []
    monkeypatch.setattr(agents, "run_agent", fake_model(captured=calls, router=ADMIN, coverage=ACUPUNCTURE))
    navigator.navigate("student", "Is acupuncture covered?")
    plan_payload = next(p for ins, p in calls if "You are the Plan Builder" in ins)
    assert plan_payload["question_kind"] == "coverage or administrative question" and plan_payload["a_rule_says_a_referral_matters"] is False
    prompt = (ROOT / "backend" / "prompts" / "plan.md").read_text()
    for needle in ["question_kind", "timeline []", "a_rule_says_a_referral_matters", "never use the word referral", "Never write filler", "describe what you are experiencing"]:
        assert needle in prompt, needle


def test_the_example_plan_and_real_care_visits_still_have_everything(monkeypatch):
    out = run(monkeypatch)
    assert out["plan"]["write_down"] == WRITE_DOWN and out["plan"]["timeline"] and out["plan"]["do_not_forget"] and out["plan"]["checklist"]
    assert len(out["plan"]["if_not_as_planned"]) == 3


@needs_node
def test_empty_sections_are_not_drawn_for_a_coverage_question(monkeypatch):
    plan = shape(admin_plan(monkeypatch, ACUPUNCTURE, plan={"summary": "", "timeline": [], "do_not_forget": [], "checklist": []}))
    out = node_run("admin", {**base_fixtures(monkeypatch), "admin": plan})
    titles = [t["title"] for t in out["top"]]
    assert not {"Your timeline", "Do not forget to mention", "Checklist"} & set(titles)
    titles = [t for t in titles if t]
    assert titles[0] == "Call this line" and titles[1].startswith("What your plan covers") and "Write down" in titles
    assert [p[1] for p in out["pills"]] == ["Not covered"] and out["pills"][0][0].startswith("pill not_covered")


def test_the_summary_never_repeats_the_coverage_verdict(monkeypatch):
    # a coverage question: the verdict is the answer, so even a clean summary is dropped
    nice = {**CHATTY_PLAN, "summary": "Acupuncture is excluded under the Yale student health plan."}
    assert admin_plan(monkeypatch, ACUPUNCTURE, plan=nice)["plan"]["summary"] == ""
    # a care visit: a summary that restates what the coverage item already says is dropped, an action sentence stays
    restates = {**PLAN_REPLY, "summary": "Physical therapy is covered 100% with a PCP referral."}
    assert run(monkeypatch, model={"plan": restates})["plan"]["summary"] == ""
    action = {**PLAN_REPLY, "summary": "Call the main line to arrange a primary care visit."}
    assert run(monkeypatch, model={"plan": action})["plan"]["summary"] == "Call the main line to arrange a primary care visit."
    assert 'never about what is covered' in (ROOT / "backend" / "prompts" / "plan.md").read_text()
