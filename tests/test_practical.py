"""Step 18 (open-now, tap-to-call, Copy plan, directions, plain-words terms, demo link in the footer), Step 20 (real sources, no rule
lines on the card, traceability in How it decided and the audit log) and Step 21 (the landing page hierarchy)."""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import agents
import config
import example
import main
from glossary import GLOSSARY, glossary_for
from models import Answer
from rules import load_rules
from sections import CENTER_LINES, place_for
from test_flow import PT_COVERAGE, PT_ROUTER, run
from test_safety import fake_model, router_reply
from test_site import CSS, HTML, SCRIPT, block, fixtures as base_fixtures, needs_node, node_run, shape

ROOT = Path(__file__).resolve().parents[1]


def rule_files() -> dict[str, dict]:
    return {Path(p).stem.replace("rules_", ""): json.load(open(p)) for p in sorted(glob.glob(str(ROOT / "data" / "rules_*.json")))}


def all_rules() -> list[tuple[str, dict]]:
    return [(name, fact) for name, data in rule_files().items() for fact in data["coverage"]]


# ======================================= Step 20: sources ====================================================

def test_no_rule_has_a_placeholder_source():
    for name, fact in all_rules():
        src = fact["source"]
        assert src.strip() and "project owner" not in src.lower() and "placeholder" not in src.lower(), (fact["id"], src)
        assert re.search(r"Yale|988|Booklet|Guide|Schedule|Summer Session", src), f"{fact['id']}: the source must name a document: {src}"


def test_every_source_that_names_a_document_gives_its_address():
    for name, fact in all_rules():
        if fact["id"] in ("common.safety_net", "student.bring_id"):
            assert "url" not in fact  # these have no document to point to
        else:
            assert fact["url"].startswith("https://"), fact["id"]
    sheet = next(f for _, f in all_rules() if f["id"] == "employee.physical_therapy")
    assert sheet["url"].endswith("member%20booklet%20-%202026%20-%20final%20draft.pdf")


def test_rules_that_no_yale_health_document_backs_are_flagged_not_dressed_up():
    flagged = {fact["id"]: fact.get("source_status") for _, fact in all_rules() if fact.get("source_status")}
    assert flagged == {"student.dry_needling": "unconfirmed", "student.bring_id": "unconfirmed", "student.international": "partly_unconfirmed"}
    for _, fact in all_rules():
        if fact["id"] in flagged:
            assert re.search(r"No Yale Health document found|confirm|Confirm", fact["source"]), fact["id"]
    safety = next(f for _, f in all_rules() if f["id"] == "common.safety_net")
    assert "not a Yale Health document" in safety["source"]  # an app policy says so plainly


def test_sources_that_come_from_the_booklet_and_the_student_guide_carry_page_numbers():
    by_id = {f["id"]: f for _, f in all_rules()}
    assert "p. 66" in by_id["student.acupuncture_excluded"]["source"] and "Acupuncture, except when used instead of other anesthesia" in by_id["student.acupuncture_excluded"]["source"]
    assert "p. 3" in by_id["common.facility"]["source"] and "p. 38" in by_id["student.ptsmc"]["source"]
    for fid in ("employee.direct_access", "employee.physical_therapy", "employee.emergency_room_cost", "employee.urgent_care_cost", "employee.behavioral_health"):
        assert re.search(r"p+\. ?\d+", by_id[fid]["source"]), fid


def test_the_source_status_reaches_the_answer(monkeypatch):
    reply = {"items": [{"topic": "Dry needling", "status": "conditions", "answer": "Dry needling is covered under a PT referral.",
                        "claim": "Dry needling is available through PTSMC and is covered under a PT referral.", "rule_ids": ["student.dry_needling"]}]}
    out = run(monkeypatch, model={"coverage": reply})
    rule = out["coverage"]["items"][0]["rules"][0]
    assert rule["source_status"] == "unconfirmed" and "No Yale Health document found" in rule["source"]


def test_the_audit_log_keeps_the_rule_file_and_source(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main, "LOG_PATH", tmp_path / "run_log.jsonl")
    monkeypatch.setattr(agents, "run_agent", fake_model(router=PT_ROUTER, coverage=PT_COVERAGE))
    TestClient(main.app).post("/api/navigate", json={"role": "student", "situation": "lower back pain for weeks, I want physical therapy", "session_id": "audit-session-1"})
    record = json.loads((tmp_path / "audit_trail.json").read_text())[0]
    assert record["rules"] and record["rules"][0]["id"] == "student.pt_coverage" and record["rules"][0]["file"] == "student"
    assert "Schedule of Benefits" in record["rules"][0]["source"]  # the real document, in the log


# ======================================= Step 18: plain-words terms ==============================================

def test_every_glossary_sentence_is_copied_word_for_word_from_a_rule_file():
    statements = {f["id"]: f["statement"] for _, f in all_rules()}
    for entry in GLOSSARY:
        for option in entry["options"]:
            assert option["sentence"] in statements[option["rule_id"]], (entry["term"], option["rule_id"])
            assert option["sentence"][0].isupper() and option["sentence"].endswith(".") and len(option["sentence"]) < 200  # one short sentence


def test_terms_the_rule_files_do_not_explain_have_no_entry():
    terms = {v.lower() for e in GLOSSARY for v in e["variants"]}
    for unexplained in ["copay", "dry needling", "member services", "hmo", "deductible"]:
        assert unexplained not in terms, unexplained
    assert {"pcp", "prior authorization"} <= terms  # the rule files do explain these now
    rules = load_rules("student")
    assert glossary_for(rules, ["You need a copay for dry needling at Member Services."]) == []


def test_a_term_is_explained_only_from_a_rule_the_persons_role_can_read():
    student, staff = load_rules("student"), load_rules("staff_faculty")
    assert [g["term"] for g in glossary_for(student, ["Basic Coverage and Hospitalization & Specialty Care coverage"])] == ["Basic Coverage", "Hospitalization & Specialty Care coverage"]
    assert glossary_for(staff, ["Basic Coverage and Hospitalization & Specialty Care coverage"]) == []  # those are student rules
    ptsmc_staff = glossary_for(staff, ["Book PTSMC."])[0]
    assert ptsmc_staff["rule"]["id"] == "employee.physical_therapy" and ptsmc_staff["explanation"] == "PTSMC at Yale Health is at 55 Lock Street, New Haven."
    assert glossary_for(student, ["Book PTSMC."])[0]["rule"]["id"] == "student.ptsmc"


def test_an_explanation_carries_its_citation_and_only_terms_in_the_plan_are_included(monkeypatch):
    out = run(monkeypatch)
    terms = {g["term"] for g in out["glossary"]}
    assert "referral" in terms and "Basic Coverage" not in terms
    entry = next(g for g in out["glossary"] if g["term"] == "referral")
    assert entry["explanation"] == "All care happens at the Yale Health Center unless a PCP refers you out."
    assert entry["rule"]["id"] == "common.care_at_center" and entry["rule"]["url"] == "https://yalehealth.yale.edu/coverage"
    Answer.model_validate({k: v for k, v in out.items() if k != "_meta"})


# ======================================= Step 18: the Yale Health Center place ====================================

def test_the_address_is_in_the_rule_files_and_directions_appear_only_where_the_visit_is_at_the_center():
    statements = " ".join(f["statement"] for _, f in all_rules())
    assert "55 Lock Street" in next(f for _, f in all_rules() if f["id"] == "common.facility")["statement"] and "55 Lock Street, New Haven" in statements
    rules = load_rules("student")
    by_id = {l["id"]: l for l in rules.lines}
    for line_id in CENTER_LINES:
        assert place_for(by_id[line_id]) == {"name": "Yale Health Center", "address": "55 Lock Street, New Haven"}
    for line_id in ("emergency_911", "crisis_988", "mental_health_counseling", "member_services_email", "mychart", "referrals"):
        assert place_for(by_id[line_id]) is None, line_id


def test_a_plan_at_the_center_carries_the_place_and_a_plan_elsewhere_does_not(monkeypatch):
    assert run(monkeypatch)["place"] == {"name": "Yale Health Center", "address": "55 Lock Street, New Haven"}
    assert example.build_example()["place"]["address"] == "55 Lock Street, New Haven"
    mental = run(monkeypatch, model={"router": {**PT_ROUTER, "line_id": "mental_health_counseling"}})
    assert mental["place"] is None


# ======================================= Step 18: open now, from the hours in the rule files =========================

CASES = [  # (hours text from a rule file, [year, month, day, hour, minute], expected badges)
    ("Monday-Friday, 8:30 a.m.-5:00 p.m.", [2026, 10, 26, 10, 0], ["Open now until 5:00 p.m."]),                       # Monday
    ("Monday-Friday, 8:30 a.m.-5:00 p.m.", [2026, 10, 26, 8, 29], ["Closed, opens today 8:30 a.m."]),
    ("Monday-Friday, 8:30 a.m.-5:00 p.m.", [2026, 10, 26, 8, 30], ["Open now until 5:00 p.m."]),
    ("Monday-Friday, 8:30 a.m.-5:00 p.m.", [2026, 10, 26, 17, 0], ["Closed, opens tomorrow 8:30 a.m."]),
    ("Monday-Friday, 8:30 a.m.-5:00 p.m.", [2026, 10, 30, 18, 0], ["Closed, opens Monday 8:30 a.m."]),                  # Friday evening
    ("Monday-Friday, 8:30 a.m.-5:00 p.m.", [2026, 10, 24, 12, 0], ["Closed, opens Monday 8:30 a.m."]),                  # Saturday
    ("Monday-Friday, 8:30 a.m.-5:00 p.m.", [2026, 11, 1, 12, 0], ["Closed, opens tomorrow 8:30 a.m."]),                  # Sunday
    ("In-person Sunday-Saturday, 8:00 a.m.-10:00 p.m. Nurse triage by phone 24/7.", [2026, 10, 24, 22, 30],
     ["In-person: Closed, opens tomorrow 8:00 a.m.", "Nurse triage by phone: Open now, 24 hours"]),
    ("In-person Sunday-Saturday, 8:00 a.m.-10:00 p.m. Nurse triage by phone 24/7.", [2026, 10, 24, 12, 0],
     ["In-person: Open now until 10:00 p.m.", "Nurse triage by phone: Open now, 24 hours"]),
    ("24/7", [2026, 10, 24, 3, 0], ["Open now, 24 hours"]),
    ("Urgent calls 24/7. Routine scheduling Monday-Friday, 8:30 a.m.-5:00 p.m.", [2026, 10, 24, 12, 0],
     ["Urgent calls: Open now, 24 hours", "Routine scheduling: Closed, opens Monday 8:30 a.m."]),
    ("Not stated", [2026, 10, 26, 12, 0], []),
    ("Not stated in the booklet", [2026, 10, 26, 12, 0], []),
    ("Replies in about two business days", [2026, 10, 26, 12, 0], []),
    ("Mon-Fri 9 to 5", [2026, 10, 26, 12, 0], []),  # a form it cannot read exactly: no badge, never a guess
    ("", [2026, 10, 26, 12, 0], []),
]


@needs_node
def test_open_now_is_worked_out_from_the_rule_file_hours_and_never_guessed(monkeypatch):
    out = node_run("status", {**base_fixtures(monkeypatch), "cases": [{"hours": h, "now": n} for h, n, _ in CASES], "hours": []})
    for (hours, now, expected), got in zip(CASES, out["results"]):
        assert got == expected, (hours, now)


@needs_node
def test_every_line_in_the_rule_files_gets_a_badge_only_when_its_hours_are_in_a_form_the_page_can_read(monkeypatch):
    grammar = re.compile(r"24/7|(Monday-Friday|Sunday-Saturday),?\s+(\d{1,2}):(\d{2})\s+(a\.m\.|p\.m\.)-(\d{1,2}):(\d{2})\s+(a\.m\.|p\.m\.)")  # written again here, on purpose
    hours = [l["hours"] for _, data in rule_files().items() for l in data["lines"] if l.get("phone") and l.get("hours")]
    out = node_run("status", {**base_fixtures(monkeypatch), "cases": [], "hours": hours})
    for text, parsed in zip(hours, out["parsed"]):
        assert len(parsed) == len(list(grammar.finditer(text))), text
    for text, parsed in zip(hours, out["parsed"]):
        if text in ("Not stated", "Not stated in the booklet"):
            assert parsed == [], text  # these lines show their hours text and no live badge
    assert any(parsed for parsed in out["parsed"]) and any(not parsed for parsed in out["parsed"])


@needs_node
def test_the_call_line_shows_the_live_badge_next_to_its_hours(monkeypatch):
    out = node_run("badges", base_fixtures(monkeypatch))
    assert len(out["hero"]) == 1 and out["hero"][0][0] in ("openstatus open", "openstatus closed")
    assert out["hero"][0][1].startswith(("Open now until 5:00 p.m.", "Closed, opens")) and "Monday-Friday, 8:30 a.m.-5:00 p.m." in out["heroHours"]


def test_badges_are_for_call_lines_with_hours_only():
    code = SCRIPT[SCRIPT.index("function openBadges"):SCRIPT.index("function lineBlock")]
    assert "!line.phone || !line.hours" in code and "device's clock" in code
    assert re.search(r"\.openstatus\.open \{[^}]*var\(--ok", CSS) and re.search(r"\.openstatus\.closed \{[^}]*var\(--warn", CSS)


# ======================================= Step 18: tap-to-call =====================================================

@needs_node
def test_every_phone_number_on_the_plan_and_on_the_emergency_screen_is_a_tap_to_call_link(monkeypatch):
    fx = base_fixtures(monkeypatch)
    from rules import load_rules as _load

    fx["emergency"] = {"kind": "emergency", "emergency": _load("student").emergency}
    out = node_run("taps", fx)
    for where in ("plan", "emergency"):
        assert out[where]["bare"] == [], f"phone numbers on the {where} that are not links: {out[where]['bare']}"
        assert out[where]["links"], where
        for text, href in out[where]["links"]:
            assert re.fullmatch(r"tel:\+?\d{3,11}", href) and re.sub(r"\D", "", text) == re.sub(r"\D", "", href), (text, href)
    assert len(out["plan"]["links"]) >= 4


def test_phone_links_are_made_in_one_place_for_every_text_the_page_draws():
    assert 'const el = (tag, cls, text) => richElement(tag, cls, text, false)' in SCRIPT and "a.href = \"tel:\"" in SCRIPT
    assert "\\\\b911\\\\b" in SCRIPT and "\\\\b988\\\\b" in SCRIPT


# ======================================= Step 18: Copy plan ======================================================

@needs_node
def test_copy_plan_copies_the_whole_plan_as_plain_text_in_the_browser(monkeypatch):
    out = node_run("copy", base_fixtures(monkeypatch))
    assert out["sent"] == 0 and out["label"] == "Copied"  # nothing was sent anywhere
    assert out["copied"] == [out["text"]]
    text = out["text"]
    for needle in ["YALE HEALTH NAVIGATOR: YOUR PLAN", "For: Yale student", "CALL THIS LINE", "(203) 432-0246", "Where: Yale Health Center, 55 Lock Street, New Haven",
                   "WHAT YOUR PLAN COVERS", "Covered with conditions", "CHECKLIST", "TIMELINE", "Today: ", "DO NOT FORGET TO MENTION", "WRITE DOWN",
                   "IF THINGS DO NOT GO AS PLANNED", "GET EMERGENCY HELP RIGHT AWAY IF", "Call 911.", "Educational guidance only"]:
        assert needle in text, needle
    assert "[x] " in text and "[ ] " in text  # what was ticked
    assert "Date and time of the appointment: Thu Nov 5, 2:30 pm" in text and "Referral details: ______" in text and "Name of the person you spoke to: Maria" in text
    assert not re.search(r"[{}]\s*\"|\"kind\"", text)  # plain text, not JSON
    assert "Rule student." not in text and "From the rules" not in text and "Applies to" not in text  # no rule ids or quotes in what a person pastes into Notes


def test_the_copy_button_is_next_to_print_in_the_end_section_and_uses_only_the_clipboard():
    end = SCRIPT[SCRIPT.index("function renderTakeAway"):SCRIPT.index("// ---- Add to calendar")]
    assert 'el("button", "ghost", "Copy plan")' in end and end.index('"Copy plan"') < end.index('"Print plan"') and "copyPlan(copy)" in end
    copy = SCRIPT[SCRIPT.index("async function copyPlan"):SCRIPT.index("function renderPlanBar")]
    assert "navigator.clipboard.writeText" in copy and "fetch(" not in copy and "sendBeacon" not in copy and "XMLHttpRequest" not in copy


# ======================================= Step 18: directions =========================================================

@needs_node
def test_get_directions_sits_next_to_the_address_and_in_the_calendar_form(monkeypatch):
    out = node_run("calendar_dirs", base_fixtures(monkeypatch))
    assert out["place"].startswith("Yale Health Center, 55 Lock Street, New Haven") and out["place"].endswith("Get directions")
    assert out["heroDirections"] and all(text == "Get directions" and "55%20Lock%20Street" in href and target == "_blank" for text, href, target in out["heroDirections"])
    assert out["formDirections"] and out["formDirections"][0][0] == "Get directions"


def test_directions_open_the_persons_own_maps_app():
    code = SCRIPT[SCRIPT.index("function directionsUrl"):SCRIPT.index("function directionsLink")]
    assert 'https://maps.apple.com/?q=' in code and "geo:0,0?q=" in code and "https://www.google.com/maps/search/?api=1&query=" in code
    assert "iPhone|iPad|iPod" in code and "Android" in code and 'rel = "noopener noreferrer"' in SCRIPT[SCRIPT.index("function directionsLink"):SCRIPT.index("function placeRow")]


# ======================================= Step 18: plain-words terms on the page ======================================

@needs_node
def test_tapping_a_term_shows_the_rule_files_sentence_and_its_citation_and_tapping_again_hides_it(monkeypatch):
    plan = shape(example.build_example())
    out = node_run("terms", {**base_fixtures(monkeypatch), "plan": plan})
    names = [t for t, _ in out["terms"]]
    assert names and "referral" in names and out["badTerms"] == 0  # words with no explanation (copay, dry needling) are never made tappable
    assert len(names) == len(set(names))  # each term is tappable once, where it first appears: the plan is not covered in underlines
    assert out["open"] and out["open"][0].startswith("In plain words: All care happens at the Yale Health Center unless a PCP refers you out.")
    assert "Rule " not in out["open"][0] and "common.care_at_center" not in out["open"][0]  # no rule line on the page: it is in "How it decided"
    assert out["expanded"] == "true" and out["closed"] == 0 and out["expandedAfter"] == "false"
    assert out["textOnly"]  # "prior authorization" and "PCP" are in the plan as plain words


# ======================================= Step 18: the demo link ====================================================

def test_the_safety_demo_link_is_in_the_footer_not_the_header_and_the_example_stays_in_the_hero():
    header = HTML[HTML.index("<header>"):HTML.index("</header>")]
    assert "safety-demo" not in header and "Safety demo" not in header
    footer = re.search(r'<footer class="sitefoot noprint">(.*?)</footer>', HTML, re.S).group(1)
    assert '<a href="/safety-demo">Safety demo</a>' in footer
    assert HTML.index("</main>") > HTML.index("<footer")  # the footer is inside the page, above the floating button's room
    hero = HTML[HTML.index('<section class="hero">'):HTML.index("</section>", HTML.index('<section class="hero">'))]
    assert 'id="example"' in hero and "See an example plan" in hero
    assert (ROOT / "frontend" / "safety_demo.html").exists()  # the demo page itself stays
    assert TestClient(main.app).get("/safety-demo").status_code == 200


# ======================================= Steps 21 and 22: the landing page, restrained =====================================

BASE = CSS[:CSS.index("/* Media queries come last")]


def rule(selector: str, css: str = BASE) -> str:
    return re.search(re.escape(selector) + r" \{([^}]*)\}", css).group(1)


def test_the_hero_is_a_light_card_in_the_page_with_only_the_greeting_and_the_example_button():
    assert HTML.index("<main>") < HTML.index('<section class="hero">')  # inside the page column, a card, not a full-width slab
    card = rule(".hero")
    assert "background: var(--white)" in card and "border: 1px solid var(--line)" in card and "box-shadow: var(--lift)" in card
    assert "yale-dark" not in card and "background: var(--yale" not in card
    h1 = rule(".hero h1")
    assert int(re.search(r"font-size: (\d+)px", h1).group(1)) >= 34 and "color: var(--yale)" in h1  # the greeting stays large
    hero = HTML[HTML.index('<section class="hero">'):HTML.index("</section>", HTML.index('<section class="hero">'))]
    assert re.findall(r"<(h1|p|button)\b", hero) == ["h1", "button"]  # a greeting and a button, no paragraph
    assert "Tell me what is going on in your own words" not in HTML and "help you plan the call, and check what your plan covers" not in hero


def test_the_promise_is_made_twice_not_three_times():
    assert "Find the right line, plan the call, check coverage" in HTML  # the header tagline
    assert "You get a plan with coverage" in HTML  # the strip
    assert HTML.count("check what your plan covers") == 0 and HTML.count("point you to the right Yale Health line") == 0


def test_see_an_example_plan_is_an_outline_button_in_yale_blue():
    assert re.search(r'<button type="button" class="btn-outline" id="example">See an example plan</button>', HTML)
    button = rule(".btn-outline")
    assert "border: 2px solid var(--yale)" in button and "background: transparent" in button and "color: var(--yale)" in button and "white" not in button


def test_borders_are_light_and_only_the_selected_role_is_filled():
    plain = rule(".role span")
    assert "border: 2px solid var(--line)" in plain and "background: var(--white)" in plain  # light grey
    selected = rule(".role input:checked + span")
    assert "background: var(--yale)" in selected and "color: var(--white)" in selected
    assert re.search(r"\.role:hover span \{ border-color: var\(--yale-mid\)", CSS)  # a hover hint only
    assert "border: none" in rule(".stepbox") and "box-shadow: var(--lift)" in rule(".stepbox")  # soft shadow, no border


def test_the_textarea_has_a_medium_border_and_a_light_tint_not_a_thick_dark_one():
    area = rule("#situation")
    width = int(re.search(r"border: (\d)px solid var\(--(yale-mid|yale)\)", area).group(1))
    assert width == 2 and "var(--yale-mid)" in area and "background: var(--tint)" in area
    assert "3px" not in area and "inset" not in area


def test_the_find_button_is_a_medium_flat_solid_blue_button_when_enabled_and_quiet_when_disabled():
    live, dead = rule("#go:not(:disabled)"), rule("#go:disabled")
    font = int(re.search(r"font-size: (\d+)px", live).group(1))
    assert font == int(re.search(r"font-size: (\d+)px", rule("#situation")).group(1))  # the same size as the text in the form
    padding = [int(n) for n in re.search(r"padding: (\d+)px (\d+)px", live).groups()]
    assert padding[0] <= 14 and padding[1] <= 32 and "min-height" not in live  # comfortable, not a slab
    assert "box-shadow: none" in live  # flat on the card
    assert "background" not in live and "color" not in live  # still the solid Yale blue and white of .primary
    assert "background: var(--yale);" in rule(".primary") and "color: var(--white)" in rule(".primary")
    assert "background: var(--tint)" in dead and "color: var(--muted)" in dead and "box-shadow: none" in dead  # the disabled state is unchanged
    assert int(re.search(r"font-size: (\d+)px", dead).group(1)) <= 16 and "min-height" not in dead and "opacity: 1" in dead
    assert 'class="primary" id="go"' in HTML


def test_the_find_button_hugs_its_label_on_every_screen_size():
    phone = block(CSS, "@media (max-width: 560px)")
    assert "#go" not in phone  # no full-width rule for the button on a phone
    assert "width" not in rule("#go:not(:disabled)") and "width" not in rule("#go:disabled")
    assert re.search(r"\.gowrap \{[^}]*align-items: center", phone) and "align-items: stretch" not in phone[phone.index(".gowrap"):phone.index(".gowrap") + 160]
    assert "button { min-height: 44px; }" in phone  # still an easy tap target on a phone


def test_one_strong_element_on_the_landing_page():
    """Nothing but the selected role and the enabled Find button may carry a solid Yale blue fill on the landing page."""
    solid = [m.group(1).strip() for m in re.finditer(r"([^{}]+)\{[^}]*background: var\(--yale\)[;}\s]", BASE)]
    landing = [sel for sel in solid if re.search(r"^header$|\.role|#go|\.primary|\.num|\.callhero|\.msg|\.chathead|\.chaticon|\.dogwrap|\.fab|\.bulldog|\.timeline", sel)]
    assert not [sel for sel in solid if sel not in landing], solid
    assert ".hero" not in " ".join(solid)


def test_the_wins_from_the_last_round_are_kept():
    assert 'staff_faculty: "Staff or faculty",' in SCRIPT and "ROLE_SUB = { dependent:" in SCRIPT
    assert HTML.count('class="arrow"') == 2 and 'class="num"' not in HTML[HTML.index('<div class="steps"'):HTML.index('id="roleCard"')]
    assert "min-height: 72px" in rule(".role span") and re.search(r"\.role \{[^}]*display: flex", BASE)
    assert HTML.index('id="roleCard"') < HTML.index('id="askCard"') and '<a href="/safety-demo">Safety demo</a>' in HTML
    assert int(re.search(r"margin: 0 0 (\d+)px", rule(".steps")).group(1)) >= 32 and int(re.search(r"margin-bottom: (\d+)px", rule("#roleCard, #askCard")).group(1)) >= 32
    assert int(re.search(r"margin: (\d+)px 0 (\d+)px", rule(".hero")).group(2)) >= 32


def test_section_titles_are_big_and_dark_and_secondary_text_is_small_and_quiet():
    title = rule("#roleCard h2, #askCard h2")
    assert int(re.search(r"font-size: (\d+)px", title).group(1)) >= 22 and "color: var(--ink)" in title
    for selector in (".chips-title", ".privacy", ".hint"):
        css = rule(selector)
        assert int(re.search(r"font-size: (\d+)px", css).group(1)) <= 12 and "color: var(--muted)" in css, selector


def test_the_chat_button_has_phone_room_and_the_page_leaves_space_beneath_the_content():
    phone = block(CSS, "@media (max-width: 560px)")
    assert re.search(r"\.fab \{[^}]*min-height: 5\d+px", phone) and int(re.search(r"main \{ padding: \d+px \d+px (\d+)px", phone).group(1)) >= 100
    fab = rule(".fab")
    assert "position: fixed" in fab and "right: 18px" in fab and "bottom: 18px" in fab and "right: 12px" in phone
