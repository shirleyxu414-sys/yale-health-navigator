"""The landing page: the example plan (no model, no tokens), the hint, the three-step strip, the role boxes and the bulldog."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import agents
import budget
import config
import example
import main
from agents import SCRIPT_LIKE, _bad
from grounding import check_item
from models import Answer
from rules import load_rules
from sections import WRITE_DOWN, calendar_events
from test_site import CSS, HTML, SCRIPT, block, fixtures, needs_node, node_run, shape


@pytest.fixture
def no_model(monkeypatch, tmp_path):
    """Any model call, or any attempt to build a model client, fails the test. Logs go to a temp folder."""
    monkeypatch.setattr(agents, "_client", None)
    monkeypatch.setattr(agents, "_client_once", lambda: pytest.fail("the example must not reach the model"))
    monkeypatch.setattr(agents, "make_client", lambda: pytest.fail("the example must not build a model client"))
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main, "LOG_PATH", tmp_path / "run_log.jsonl")
    return tmp_path


# 4. The example plan ----------------------------------------------------------------------------------

def get_example(no_model) -> dict:
    res = TestClient(main.app).get("/api/example")
    assert res.status_code == 200
    return res.json()


def test_the_example_is_a_full_plan_with_no_model_call_and_no_tokens(no_model, monkeypatch):
    monkeypatch.setattr(budget, "GUARD", budget.Guard(10, 10))  # a budget of 10 tokens: any model call would be stopped
    body = get_example(no_model)
    Answer.model_validate(body)
    assert body["kind"] == "plan" and body["how_it_decided"]["role_id"] == "student" and body["line"]["id"] == "student_pcp"
    assert [t["when"] for t in body["plan"]["timeline"]] == ["Today", "On the call", "This week", "After the referral"]
    assert len(body["plan"]["do_not_forget"]) == 3 and body["plan"]["write_down"] == WRITE_DOWN
    assert [c["id"] for c in body["plan"]["checklist"]] == ["called", "booked", "referral", "ptsmc"]
    assert body["coverage"]["items"] and body["safety_net"]["area"] == "general" and "email" not in body["prefer_writing"] and "mychart" not in body["prefer_writing"]
    assert "This is an example plan" in body["notice"] and "not made for you" in body["notice"]
    assert budget.GUARD.sessions.used("anything") == 0


def test_the_example_leaves_no_trace(no_model):
    get_example(no_model)
    assert list(no_model.iterdir()) == []  # no run log, no guard log: nothing was recorded


def test_the_example_covers_the_pt_referral_and_dry_needling_points(no_model):
    body = get_example(no_model)
    points = " ".join(p["point"] + " " + p["why"] for p in body["plan"]["do_not_forget"])
    assert "PT referral" in points and "100%" in points and "dry needling" in points.lower() and "only if you ask" in points


def test_every_claim_in_the_example_is_grounded_in_the_rule_files(no_model):
    body = get_example(no_model)
    rules = load_rules("student")
    by_id = {f["id"]: f for f in rules.facts}
    for item in body["coverage"]["items"]:
        assert item["status"] in ("covered", "conditions") and item["rules"]
        cited = [by_id[r["id"]] for r in item["rules"]]
        assert check_item(item, cited) is None, item["topic"]


def test_the_example_plan_text_passes_the_same_guards_as_a_real_plan(no_model):
    body = get_example(no_model)
    rules = load_rules("student")
    plan = body["plan"]
    texts = [plan["summary"]] + [t["what"] for t in plan["timeline"]] + [t for p in plan["do_not_forget"] for t in (p["point"], p["why"])] + [c["label"] for c in plan["checklist"]]
    for text in texts:
        assert not _bad(text, rules) and not SCRIPT_LIKE.search(text), text


def test_the_code_built_parts_of_the_example_come_from_the_same_code_as_a_real_plan(no_model):
    body = get_example(no_model)
    rules = load_rules("student")
    line = next(l for l in rules.lines if l["id"] == "student_pcp")
    assert body["plan"]["calendar"] == calendar_events(rules, line, "routine", True, "physical therapy", True, False)
    assert body["how_it_decided"]["rule_files"] == ["rules_student.json", "rules_common.json"]
    assert body["plan"]["if_not_as_planned"][2]["action"] == "has_referral"


def test_every_number_in_the_example_is_in_the_rule_files(no_model):
    from safety import PHONE, allowed_numbers

    rules = load_rules("student")
    for number in PHONE.findall(json.dumps(get_example(no_model))):
        assert re.sub(r"\D", "", number).lstrip("1") in allowed_numbers(rules), number


def test_the_example_text_on_the_page_matches_the_one_the_server_used():
    assert f'const EXAMPLE_TEXT = "{example.EXAMPLE_TEXT}"' in SCRIPT
    assert example.EXAMPLE_ROLE == "student"


def test_the_see_an_example_link_is_in_the_hero():
    hero = HTML[HTML.index('<section class="hero">'):HTML.index("</section>", HTML.index('<section class="hero">'))]
    assert 'id="example"' in hero and "See an example plan" in hero
    assert 'fetch("/api/example")' in SCRIPT


@needs_node
def test_clicking_the_example_shows_a_full_plan_with_no_typing(monkeypatch, no_model):
    plan = get_example(no_model)
    out = node_run("example", {**fixtures(monkeypatch), "next": plan})
    assert out["shown"] and out["notice"] and out["referralButton"]
    assert out["fetched"] == 1 and out["situation"] == example.EXAMPLE_TEXT and out["roleChecked"] and out["state"]["role"] == "student"
    assert out["state"]["busy"] is False and out["state"]["ticked"] == []


# 3. The hint next to the Find button -------------------------------------------------------------------

def test_the_hint_text_is_exact_and_sits_next_to_the_button():
    assert "Pick a role and tell me what's going on." in HTML
    assert re.search(r'<div class="gowrap"><span class="dogwrap thinkdog" id="thinkDog" hidden aria-hidden="true"></span><span class="hint" id="goHint">[^<]*</span><button class="primary" id="go"', HTML)


@needs_node
def test_the_hint_shows_while_the_button_is_disabled_and_goes_away_when_it_works(monkeypatch):
    out = node_run("hint", fixtures(monkeypatch))
    assert out["empty"] == {"hintHidden": False, "goDisabled": True}
    assert out["textOnly"] == {"hintHidden": False, "goDisabled": True}  # text but no role
    assert out["ready"] == {"hintHidden": True, "goDisabled": False}
    assert out["roleOnly"] == {"hintHidden": False, "goDisabled": True}  # role but no text


# 5. The how-it-works strip: no numbers, arrows between equal boxes ------------------------------------------------

def test_the_how_it_works_strip_has_no_numbers_and_arrows_between_three_equal_boxes():
    after_hero = HTML[HTML.index("</section>", HTML.index('<section class="hero">')):]
    strip = after_hero[after_hero.index('<div class="steps"'):after_hero.index('id="roleCard"')]
    assert after_hero.index(strip) < after_hero.index('id="roleCard"')
    assert 'class="num"' not in strip and not re.search(r">\s*[123]\s*<", strip)  # one numbering system per page: the form's 1 and 2
    assert re.findall(r'<div class="stepbox" role="listitem">([^<]+)</div>', strip) == ["Tell me in plain words", "I route you to the right line", "You get a plan with coverage"]
    assert strip.count('class="arrow"') == 2 and strip.count("&rarr;") == 2
    base = CSS[:CSS.index("/* Media queries come last")]
    steps, box = re.search(r"\.steps \{([^}]*)\}", base).group(1), re.search(r"\.stepbox \{([^}]*)\}", base).group(1)
    assert "align-items: stretch" in steps  # all three boxes are as tall as the tallest
    assert "display: flex" in box and "align-items: center" in box and "justify-content: center" in box and "text-align: center" in box and "min-height: 64px" in box
    assert re.search(r"\.arrow \{[^}]*align-self: center", base)
    phone = block(CSS, "@media (max-width: 560px)")
    assert re.search(r"\.arrow \{ transform: rotate\(90deg\)", phone)  # the arrows point down when the boxes stack


# 2. The role boxes --------------------------------------------------------------------------------------

def test_staff_or_faculty_is_shortened_because_the_question_already_says_yale():
    roles = SCRIPT[SCRIPT.index("const ROLES"):SCRIPT.index("const ROLE_SUB")]
    assert 'staff_faculty: "Staff or faculty",' in roles and "Yale staff or faculty" not in roles  # the box label; the chat's sentence may still say Yale
    assert load_rules("staff_faculty").label == "Yale staff or faculty"  # the server's label, used in answers, is unchanged


def test_the_role_boxes_are_one_height_with_centred_text():
    box = re.search(r"\.role span \{([^}]*)\}", CSS).group(1)
    assert "flex: 1" in box and "justify-content: center" in box and "min-height: 72px" in box
    assert re.search(r"\.role \{[^}]*display: flex", CSS)  # the label fills the grid cell, so the box does too
    assert re.search(r"\.roles \{[^}]*display: grid", CSS) and "white-space: nowrap" not in re.search(r"\.role span \{[^}]*\}", CSS).group(0)


def test_dependent_is_short_with_a_sub_line_and_the_four_boxes_have_one_height():
    assert 'dependent: "Dependent",' in SCRIPT and 'const ROLE_SUB = { dependent: "of a Yale member" }' in SCRIPT
    assert 'dependent: "Dependent of a Yale member"' not in SCRIPT
    box = re.search(r"\.role span \{([^}]*)\}", CSS).group(1)
    assert "min-height: 72px" in box and "display: flex" in box and "flex-direction: column" in box
    assert re.search(r"\.roles \{[^}]*display: grid", CSS)  # grid rows give equal heights to boxes in a row
    assert len(re.findall(r'(student|staff_faculty|dependent|visiting_student): "', SCRIPT[SCRIPT.index("const ROLES"):SCRIPT.index("const ROLE_SUB")])) == 4


def test_the_label_the_server_uses_for_the_role_is_unchanged():
    assert load_rules("dependent").label == "Dependent of a Yale member"  # the page shortens it only on the role box


# 1. The bulldog -------------------------------------------------------------------------------------------

def angle(rule: str) -> float:
    return float(re.search(rf"{re.escape(rule)} \{{[^}}]*rotate\((-?\d+(?:\.\d+)?)deg\)", CSS).group(1))


def test_the_brows_are_near_horizontal_and_tilt_up_toward_the_middle_not_down():
    left, right = angle(".bulldog .brow.l"), angle(".bulldog .brow.r")
    assert abs(left) <= 5 and abs(right) <= 5  # near-horizontal
    assert left < 0 < right  # inner ends are the higher ends: a gentle look, not a frown
    assert left == -right


def test_the_bulldog_has_a_wide_friendly_smile_and_bright_eyes():
    mouth = re.search(r"\.bulldog \.mouth \{([^}]*)\}", CSS).group(1)
    width = int(re.search(r"width: (\d+)px", mouth).group(1))
    assert width >= 32 and "border-radius: 0 0 36px 36px" in mouth  # a deep U-shaped smile
    assert "border-left" in mouth and "border-right" in mouth  # the smile turns up at the ends
    assert re.search(r"\.bulldog \.eye::after", CSS)  # a highlight in each eye


def test_the_bulldog_has_arched_thin_brows_cheeks_and_no_teeth():
    brow = re.search(r"\.bulldog \.brow \{([^}]*)\}", CSS).group(1)
    assert "border-top: 3px solid var(--dog-line)" in brow and "border-radius: 60% 60% 0 0" in brow  # a soft arch, not a slanted bar
    assert re.search(r"\.bulldog \.cheek \{", CSS) and 'class="cheek l"' in HTML and 'class="cheek r"' in HTML
    assert "tooth" not in HTML and ".tooth" not in CSS  # teeth read as clenched; jowls are part of the English bulldog


def test_the_bulldog_is_still_built_from_html_and_css_only():
    hero = HTML[HTML.index('<div class="bulldog" id="dog"'):HTML.index('<div class="herotext">')]
    assert "<svg" not in hero.lower() and "<img" not in hero.lower() and 'class="head"' in hero  # the creature is divs and CSS
    build = SCRIPT[SCRIPT.index("function buildDog"):SCRIPT.index("// A calm line from the bulldog")]
    assert "<svg" not in build.lower() and "<img" not in build.lower()  # the copies that react are built the same way


def test_the_bulldog_is_an_english_bulldog_white_with_a_brown_patch_and_keeps_the_yale_collar():
    for part in ("patch", "wrinkle a", "wrinkle b", "jowl l", "jowl r", "ear l", "ear r", "muzzle", "nose"):
        assert f'class="{part}"' in HTML, part  # wrinkled brow, jowls, floppy ears, wide muzzle, flat nose, brown patch
    assert re.search(r"\.bulldog \.patch \{[^}]*var\(--dog-brown\)", CSS) and re.search(r"\.bulldog \.ear\.l \{[^}]*var\(--dog-brown\)", CSS)
    assert re.search(r"\.bulldog \.head \{[^}]*var\(--dog-white\)", CSS)
    assert re.search(r"\.bulldog \.collar \{[^}]*var\(--yale\)", CSS) and "cross" in HTML  # the app palette stays Yale blue
    assert not re.search(r"\.bulldog \.ear \{[^}]*var\(--yale\)", CSS)  # no pointy blue ears


def test_the_two_form_questions_have_icon_badges_and_short_one_line_headings():
    roles = HTML[HTML.index('id="roleCard"'):HTML.index('id="askCard"')]
    ask = HTML[HTML.index('id="askCard"'):HTML.index('id="askCard"') + 900]
    assert "<span>Who are you at Yale?</span>" in roles and "<span>What is going on?</span>" in ask
    assert roles.count('<svg') >= 1 and 'class="num" aria-hidden="true"><svg' in roles and 'class="num" aria-hidden="true"><svg' in ask
    assert not re.search(r'class="num"[^>]*>\s*\d', HTML)  # no number is left in a badge
    assert re.search(r"\.num \{[^}]*width: 30px; height: 30px; border-radius: 50%; background: var\(--yale\)", CSS)


def test_the_common_questions_row_has_the_six_chips_plus_three_and_stops_at_nine():
    chips = SCRIPT[SCRIPT.index("const CHIPS = ["):SCRIPT.index("let wantCard")]
    plain = re.findall(r'^\s+"([^"]+)",?$', chips, re.M)
    objects = re.findall(r'text: "([^"]+)"', chips)
    assert plain == ["Is PT covered?", "Is acupuncture covered?", "I have a headache", "I don't have insurance", "What if it's after hours?", "I already have a referral"]
    assert objects == ["Do I need a referral?", "Who is my PCP?", "I need mental health support"]
    assert len(plain) + len(objects) == 9
    assert 'card: "Do I need a referral?"' in chips and 'card: "Your PCP"' in chips  # entry points into the checker and the PCP card


def test_asking_about_a_pcp_brings_the_pcp_card_even_without_a_referral_in_the_answer():
    import navigator
    assert navigator.ASKS_PCP.search("Who is my PCP?") and navigator.ASKS_PCP.search("my primary care provider") and not navigator.ASKS_PCP.search("I need a pcpaste")


# The chat header role line, the map strip and the drafts section ------------------------------------------------

def test_the_chat_header_names_the_active_role_only_once_it_is_set():
    assert '<span id="chatRoleLine" hidden></span>' in HTML
    code = SCRIPT[SCRIPT.index("function syncChatRole"):SCRIPT.index("function redrawChat")]
    assert "tag.hidden = !role" in code and '" rules"' in code and "ROLE_RULES_NAME[role]" in code
    assert "syncChatRole();" in SCRIPT[SCRIPT.index("function redrawChat"):SCRIPT.index("function openChat")]


def test_the_call_card_has_a_pin_and_a_compact_map_strip_at_the_bottom_that_opens_the_directions():
    assert 'MAP_SRC = "https://www.openstreetmap.org/export/embed.html?bbox=-72.938%2C41.30824%2C-72.918%2C41.32424&layer=mapnik&marker=41.31624%2C-72.928"' in SCRIPT
    call = SCRIPT[SCRIPT.index("function renderCall"):SCRIPT.index("let shownPlan")]
    assert call.rstrip().endswith("return sec;\n  }") and call.index("sec.append(placeRow(data.place))") < call.index("sec.append(mapPreview(data.place))") and "also" in call[:call.index("mapPreview(data.place)")]
    assert "directionsLink(place).href" in SCRIPT and "Get directions" in SCRIPT  # the same link, and the link stays
    assert re.search(r"\.mapstrip \{[^}]*height: 150px[^}]*border-radius: 14px", CSS) and re.search(r"\.mapstrip \.maptap \{[^}]*inset: 0", CSS)
    assert 'icon("pin")' in SCRIPT and "noprint" in SCRIPT[SCRIPT.index("function mapPreview"):SCRIPT.index("function mapPreview") + 200]


def test_the_drafts_section_has_the_new_heading_intro_and_two_warnings():
    assert 'collapsible("Email or MyChart drafts"' in SCRIPT and "Prefer writing?" not in HTML
    import sections
    assert sections.WARNINGS == ["MyChart replies take about two business days.", "Member Services hours: Monday-Friday, 8:30 a.m.-5:00 p.m."]
    intro = "Only for coverage, admin, and non-urgent questions. For appointments, symptoms, or anything urgent, call the line above."
    from rules import load_rules
    for intent in ("administrative", "care_team_message", "care_visit"):
        assert sections.prefer_writing(load_rules("student"), intent, "routine", False, "x")["note"] == intro


def test_there_is_no_second_question_screen_and_the_assumption_line_sits_under_the_call_card():
    assert "renderAsk" not in SCRIPT and "ask_timing" not in SCRIPT and "ask_timing" not in (Path(__file__).resolve().parents[1] / "backend" / "navigator.py").read_text()
    plan = SCRIPT[SCRIPT.index("function renderPlan(data)"):SCRIPT.index("if (data.safety_net) parts.push")]
    assert plan.index("renderCall(data)") < plan.index("renderAssumed(data)") < plan.index('"callsub"')
    code = SCRIPT[SCRIPT.index("function renderAssumed"):SCRIPT.index("function renderPlan(")]
    assert "if (!data.timing_assumed) return null" in code and "You didn't say when you need care, so this plan assumes today." in code
    assert "It can wait? Show the routine plan instead." in code and 'run({ timing: "can_wait" })' in code


def test_the_coverage_section_ends_with_one_official_link_taken_from_the_rule_files():
    import json as _json
    from rules import load_rules
    rule = next(f for f in _json.load(open(Path(__file__).resolve().parents[1] / "data" / "rules_common.json"))["coverage"] if f["id"] == "common.care_at_center")
    assert rule["url"] == "https://yalehealth.yale.edu/coverage"
    import sections
    for role in ("student", "staff_faculty", "dependent", "visiting_student"):
        assert sections.official_coverage_url(load_rules(role)) == rule["url"]  # the same page for every role, never typed into the page
    code = SCRIPT[SCRIPT.index("function renderCoverage"):SCRIPT.index("// A section that starts closed")]
    assert "See the official Yale Health coverage page" in code and "cov.official_url" in code and 'link.target = "_blank"' in code and "noopener noreferrer" in code
    assert code.index("itemBox(item)") < code.index("See the official Yale Health coverage page")  # under the answers
    assert "yalehealth.yale.edu/coverage" not in SCRIPT  # the URL comes from the rule files
    assert "What's my insurance policy" not in SCRIPT and "What does my plan cover" not in SCRIPT  # no chip for it


def test_the_assumed_timing_row_is_stacked_with_the_button_below_the_sentence_and_left_aligned():
    row = re.search(r"\.assumed \{([^}]*)\}", CSS).group(1)
    assert "display: flex" in row and "flex-direction: column" in row and "align-items: flex-start" in row
    assert "margin-left: 0" in re.search(r"\.assumed button \{([^}]*)\}", CSS).group(1)
    code = SCRIPT[SCRIPT.index("function renderAssumed"):SCRIPT.index("function renderPlan(")]
    assert "You didn't say when you need care, so this plan assumes today." in code and "It can wait? Show the routine plan instead." in code  # no text changes
