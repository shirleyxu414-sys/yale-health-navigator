"""Add to calendar: the pre-filled details come from the plan, the .ics file is made in the browser, nothing is booked or sent."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import agents
import navigator
from test_flow import PT_COVERAGE, PT_ROUTER, run
from test_safety import fake_model, router_reply

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text()
SCRIPT = re.search(r"<script>(.*)</script>", HTML, re.S).group(1)


def events(out):
    return {e["when"]: e for e in out["plan"]["calendar"]}


# 1. The details are pre-filled from the plan; the date and time are left to the person --------------

def test_pt_plan_has_a_pcp_visit_and_a_ptsmc_booking_to_save(monkeypatch):
    ev = events(run(monkeypatch))
    pcp, ptsmc = ev["This week"], ev["After the referral"]
    assert pcp["title"] == "Yale Health PCP visit, physical therapy referral"
    assert "Yale Health Center, 55 Lock Street" in pcp["location"]
    assert "(203) 432-0246" in pcp["notes"] and "Line to call" in pcp["notes"] and "Referral details" in pcp["notes"]
    assert "Line to call: Yale Health Member Services, (203) 432-0246." in pcp["notes"] and "main line" not in pcp["notes"]  # the rule file's name for that number
    assert "Booked by phone" in pcp["notes"] and "Bring a student ID" in pcp["notes"]
    assert ptsmc["title"] == "PTSMC first visit, physical therapy"
    assert "55 Lock Street" in ptsmc["location"] and "PTSMC" in ptsmc["location"]
    assert "(203) 436-5583" in ptsmc["notes"] and "(203) 498-5980" in ptsmc["notes"] and "Referral details" in ptsmc["notes"]


def test_the_plan_never_carries_a_date_or_time(monkeypatch):
    for e in run(monkeypatch)["plan"]["calendar"]:
        assert set(e) == {"when", "title", "location", "notes"}
        assert not re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}:\d{2}\s?(am|pm)?\b", json.dumps(e), re.I)


def test_a_referral_holder_only_gets_the_ptsmc_booking(monkeypatch):
    out = run(monkeypatch, has_referral=True, model={"router": {**PT_ROUTER, "line_id": "ptsmc", "has_referral": True}})
    assert [e["title"] for e in out["plan"]["calendar"]] == ["PTSMC first visit, physical therapy"]
    assert out["plan"]["calendar"][0]["when"] == "Today"


def test_no_calendar_buttons_for_urgent_care_questions_or_emergencies(monkeypatch):
    urgent = run(monkeypatch, timing="today", model={"router": router_reply(symptom_present=True, intent="care_visit", line_id="acute_care")})
    assert urgent["plan"]["calendar"] == []  # Acute Care is a same-day call, not a booked appointment
    question = run(monkeypatch, text="Is PT covered?", model={"router": router_reply(intent="administrative")})
    assert question["plan"]["calendar"] == []
    monkeypatch.setattr(agents, "run_agent", lambda *a, **k: pytest.fail("model was called"))
    assert "plan" not in navigator.navigate("student", "I have chest pain")


def test_other_roles_get_a_pcp_visit_but_never_a_ptsmc_booking(monkeypatch):
    out = run(monkeypatch, role="staff_faculty", model={"router": {**PT_ROUTER, "line_id": "member_services"}})
    assert [e["when"] for e in out["plan"]["calendar"]] == ["This week"]
    assert "ptsmc" not in json.dumps(out["plan"]["calendar"]).lower()
    assert "student ID" not in json.dumps(out["plan"]["calendar"])  # that is a student-file rule


def test_calendar_details_carry_no_health_text_or_condition_names(monkeypatch):
    out = run(monkeypatch, text="ZEBRA-SENTINEL-CAL lower back pain, sciatica", model={"router": {**PT_ROUTER, "wants": "sciatica treatment"}})
    text = json.dumps(out["plan"]["calendar"])
    assert "ZEBRA-SENTINEL-CAL" not in text and "sciatica" not in text.lower()


# 2. Everything happens in the browser ---------------------------------------------------------------

CAL_CODE = SCRIPT[SCRIPT.index("// ---- Add to calendar"):SCRIPT.index("function renderTimeline")]


def test_the_calendar_code_never_talks_to_a_server_or_an_account():
    for forbidden in ["fetch(", "XMLHttpRequest", "sendBeacon", "WebSocket", "mailto:", "localStorage", "sessionStorage", "oauth", "gapi", "googleapis", "login", "password"]:
        assert forbidden.lower() not in CAL_CODE.lower(), forbidden
    assert "new Blob(" in CAL_CODE and "text/calendar" in CAL_CODE and ".ics" in CAL_CODE and "URL.createObjectURL" in CAL_CODE


def test_the_form_has_the_prefilled_fields_and_asks_for_date_and_time():
    for needle in ["ev.title", "ev.location", "ev.notes", 'date.type = "date"', 'time.type = "time"', "Add to calendar", "Save .ics file",
                   "Date (add it after you call)"]:
        assert needle in CAL_CODE or needle in SCRIPT, needle
    assert "never books" in CAL_CODE.lower() and "not sent anywhere" in CAL_CODE
    assert "date.required = true" in CAL_CODE and "time.required = true" in CAL_CODE


def test_there_is_a_button_next_to_each_booked_step_in_the_timeline():
    timeline = SCRIPT[SCRIPT.index("function renderTimeline"):SCRIPT.index("function renderDoNotForget")]
    assert "ev.when === step.when" in timeline and "calendarButton(ev)" in timeline


def test_the_page_does_not_book_anything_for_the_user():
    assert "/api/book" not in HTML and "book(" not in SCRIPT.replace("booked", "")


# 3. The .ics file itself (runs the page's own code in Node; skipped if Node is not installed) ---------

NODE = shutil.which("node")
DRIVER = r"""
const vm = require("vm"), fs = require("fs");
const js = fs.readFileSync(process.argv[2], "utf8").match(/<script>([\s\S]*)<\/script>/)[1];
const noop = () => {};
const el = () => ({ append: noop, setAttribute: noop, addEventListener: noop, classList: { add: noop, remove: noop }, style: {}, children: [] });
const ctx = { document: { getElementById: el, createElement: el, createTextNode: el, createDocumentFragment: el, body: el() },
  window: {}, navigator: {}, TextEncoder, crypto: { randomUUID: () => "11111111-2222-3333-4444-555555555555" }, console, Date };
vm.createContext(ctx);
vm.runInContext(js + "\n;globalThis.__ics = buildIcs;", ctx);
const cases = JSON.parse(process.argv[3]);
console.log(JSON.stringify(cases.map((c) => ctx.__ics(c, new Date("2026-10-24T21:00:00Z")))));
"""


def ics_for(*forms: dict) -> list[str]:
    driver = ROOT.parent / "final project" / "tests"  # never write the driver into the repo: use a temp file
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(DRIVER)
    out = subprocess.run([NODE, f.name, str(ROOT / "frontend" / "index.html"), json.dumps(forms)], capture_output=True, text=True, check=True)
    Path(f.name).unlink()
    return json.loads(out.stdout)


BASE = {"title": "Yale Health PCP visit, physical therapy referral", "location": "Yale Health Center, 55 Lock Street, New Haven",
        "notes": "Line to call: Yale Health main line, (203) 432-0246.\nReferral details: [add after the visit]", "date": "2026-11-05", "time": "14:00", "minutes": 60}


@pytest.mark.skipif(not NODE, reason="Node is not installed")
def test_the_ics_file_is_a_valid_one_event_calendar():
    (text,) = ics_for(BASE)
    lines = text.split("\r\n")
    assert text.endswith("\r\n") and "\n" not in text.replace("\r\n", "")  # CRLF line endings throughout
    assert lines[:5] == ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Yale Health Navigator//Add to calendar//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    assert lines[-3:] == ["END:VEVENT", "END:VCALENDAR", ""]
    assert text.count("BEGIN:VEVENT") == 1 and text.count("END:VEVENT") == 1
    for needed in ["UID:11111111-2222-3333-4444-555555555555@yale-health-navigator", "DTSTAMP:20261024T210000Z", "DTSTART:20261105T140000",
                   "DTEND:20261105T150000", "SUMMARY:Yale Health PCP visit\\, physical therapy referral"]:
        assert needed in lines, needed
    assert "TZID" not in text  # local time: it opens in the person's own calendar exactly as typed


@pytest.mark.skipif(not NODE, reason="Node is not installed")
def test_text_is_escaped_and_long_lines_are_folded():
    (text,) = ics_for({**BASE, "title": "A; B, C", "notes": "x" * 200 + "\nsecond line"})
    assert "SUMMARY:A\\; B\\, C" in text
    unfolded = text.replace("\r\n ", "")
    assert "DESCRIPTION:" + "x" * 200 + "\\nsecond line" in unfolded
    assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))


@pytest.mark.skipif(not NODE, reason="Node is not installed")
def test_an_appointment_across_midnight_rolls_the_end_to_the_next_day():
    (text,) = ics_for({**BASE, "time": "23:30", "minutes": 60})
    assert "DTSTART:20261105T233000" in text and "DTEND:20261106T003000" in text


@pytest.mark.skipif(not NODE, reason="Node is not installed")
def test_the_length_the_person_picks_sets_the_end_time():
    ninety, fifteen = ics_for({**BASE, "minutes": 90}, {**BASE, "minutes": 15})
    assert "DTEND:20261105T153000" in ninety and "DTEND:20261105T141500" in fifteen


def test_the_note_names_the_line_the_way_the_common_rule_file_does(monkeypatch):
    from rules import load_rules
    from sections import name_in_rules

    rules = load_rules("student")
    common_name = next(l["name"] for l in rules.lines if l["file"] == "common" and l["phone"] == "(203) 432-0246")
    pcp = next(l for l in rules.lines if l["id"] == "student_pcp")
    assert common_name == "Yale Health Member Services" and name_in_rules(rules, pcp) == common_name
    assert name_in_rules(rules, next(l for l in rules.lines if l["id"] == "ptsmc")) == "PTSMC (Physical Therapy and Sports Medicine Center), Yale Health Center, 55 Lock Street"  # no common line has that number
    staff = run(monkeypatch, role="staff_faculty", model={"router": {**PT_ROUTER, "line_id": "member_services"}})
    assert "Line to call: Yale Health Member Services, (203) 432-0246." in staff["plan"]["calendar"][0]["notes"]


def test_the_date_and_time_are_never_prefilled():
    form = SCRIPT[SCRIPT.index("function calendarForm"):SCRIPT.index("function calendarButton")]
    assert form.count("date.value =") == 1 and "if (prefill) { date.value = prefill;" in form  # only a date the person typed into the tracker
    assert "time.value =" not in form and "defaultValue" not in form and ".valueAsDate" not in form
    timeline = SCRIPT[SCRIPT.index("function renderTimeline"):SCRIPT.index("function renderDoNotForget")]
    assert "calendarButton(ev)" in timeline and "getDate" not in timeline  # the timeline's buttons start empty
    assert "save.disabled = true" in form and "Pick the date and time of your appointment to save it." in form


@pytest.mark.skipif(not NODE, reason="Node is not installed")
def test_saving_waits_for_a_real_date_and_time(monkeypatch):
    from test_site import fixtures, node_run

    out = node_run("calendar", fixtures(monkeypatch))
    assert out["start"] == {"date": "", "time": "", "saveDisabled": True, "messageHidden": False}  # empty, disabled, with a message
    assert out["dateOnly"]["saveDisabled"] is True and out["dateOnly"]["time"] == ""  # a date alone is not enough
    assert out["both"] == {"date": out["both"]["date"], "time": "14:30", "saveDisabled": False, "messageHidden": True}
    assert out["pastDate"]["saveDisabled"] is True  # a past date can't be saved
    assert out["cleared"]["saveDisabled"] is True and out["cleared"]["messageHidden"] is False
