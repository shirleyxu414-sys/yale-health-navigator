"""Step 25: warmth without a redesign. The bulldog reacts, small icons head four cards, one human line sits under the call card."""

from __future__ import annotations

import json
import re

import agents
import navigator
from rules import load_rules
from test_flow import PT_COVERAGE, PT_ROUTER
from test_plan_page import ACUPUNCTURE, ADMIN, admin_plan
from test_site import CSS, HTML, SCRIPT, block, fixtures as base_fixtures, needs_node, node_run, shape

SAYS_PLAN = "Here's your plan. First step: call this number."
SAYS_ANSWER = "Here's your answer. You can call this number to confirm it."
SUBLINE = "You don't need to explain everything. Start with one sentence about what's going on."
ICON_SIGNATURES = {"phone": "M6.6 10.8", "clipboard": "M9 3h6", "shield": "M12 2 4 5", "calendar": "M7 2h2v2", "pin": "M12 2a7 7"}


# 1. The bulldog reacts ------------------------------------------------------------------------------------

@needs_node
def test_when_the_plan_is_ready_the_bulldog_sits_by_the_call_card_with_one_calm_line(monkeypatch):
    out = node_run("warmth", base_fixtures(monkeypatch))
    assert out["order"][:3] == ["dogsays", "callhero", "callsub"]  # the bulldog's line, the call card, the human subline
    assert out["says"] == SAYS_PLAN and out["says"].count(".") == 2 and "\n" not in out["says"] and "!" not in out["says"]  # one calm line, nothing flippant
    assert out["cheer"] is True  # it hops once when the plan arrives
    assert "bulldog cheer" in out["dogClasses"]
    for part in ("ear l", "ear r", "head", "patch", "wrinkle a", "wrinkle b", "jowl l", "jowl r", "brow l", "brow r", "eye l", "eye r", "muzzle", "nose", "mouth", "cheek l", "cheek r", "collar", "cross"):
        assert part in out["dogClasses"], part  # the same bulldog as the hero, made of the same pieces


@needs_node
def test_a_coverage_question_gets_an_honest_line_not_a_first_step_that_does_not_exist(monkeypatch):
    plan = shape(admin_plan(monkeypatch, ACUPUNCTURE, plan={"summary": "", "timeline": [], "do_not_forget": [], "checklist": []}))
    out = node_run("warmth", {**base_fixtures(monkeypatch), "plan": plan})
    assert out["says"] == SAYS_ANSWER and "First step" not in out["says"]


@needs_node
def test_the_bulldog_thinks_while_a_plan_is_made_and_while_the_chat_looks_things_up(monkeypatch):
    out = node_run("thinking", base_fixtures(monkeypatch))
    assert out["start"] == {"hero": False, "thinkHidden": True, "thinkDog": False, "chat": False}
    assert out["whilePlan"]["hero"] and out["whilePlan"]["thinkHidden"] is False and out["whilePlan"]["thinkDog"] and out["button"] == "Thinking..."
    assert out["afterPlan"] == {"hero": False, "thinkHidden": True, "thinkDog": False, "chat": False}  # back to rest
    assert out["whileChat"]["chat"] is True and out["afterChat"]["chat"] is False


@needs_node
def test_the_emergency_screen_stays_bare(monkeypatch):
    from rules import load_rules as _load

    out = node_run("no_dog_for_emergency", {**base_fixtures(monkeypatch), "emergency": {"kind": "emergency", "emergency": _load("student").emergency}})
    assert out["dogsays"] == 0 and out["icons"] == 0  # the emergency message is still only the emergency message


def test_the_reactions_respect_people_who_turn_motion_off_and_the_small_dog_is_hidden_at_rest():
    assert re.search(r"@media \(prefers-reduced-motion: reduce\) \{ \.bulldog\.thinking, \.bulldog\.cheer \{ animation: none; \} \}", CSS)
    assert re.search(r"\.thinkdog\[hidden\] \{ display: none; \}", CSS) and 'id="thinkDog" hidden' in HTML  # no new element shows at rest, so the landing layout is unchanged
    assert "animation: hop .7s ease-out 1" in CSS  # one hop, not a loop


# 2. The icons -------------------------------------------------------------------------------------------------

@needs_node
def test_four_headers_get_a_yale_blue_icon_the_address_gets_a_pin_and_every_other_header_is_left_alone(monkeypatch):
    out = node_run("warmth", base_fixtures(monkeypatch))
    by_header = {i["parent"]: next(k for k, sig in ICON_SIGNATURES.items() if sig in i["html"]) for i in out["icons"]}
    assert by_header == {"label:Call this line": "phone", "What your plan covers (Yale student)": "shield", "Write down": "clipboard", "Take this plan with you": "calendar",
                         "Yale Health Center, 55 Lock Street, New HavenGet directions": "pin"}  # the map pin beside the address
    assert all(i["aria"] == "true" for i in out["icons"])  # decoration only: a screen reader skips them
    with_icon = {text for text, has in out["headers"] if has}
    assert with_icon == {"What your plan covers (Yale student)", "Write down", "Take this plan with you"}
    for text, has in out["headers"]:
        if text not in with_icon:
            assert not has, text  # the timeline, checklist and the rest are unchanged


def test_the_icons_are_fixed_pictures_in_yale_blue_and_the_call_icon_sits_on_a_white_disc():
    icons = SCRIPT[SCRIPT.index("const ICONS = {"):SCRIPT.index("// ---- Rich text.")]
    assert sorted(re.findall(r"^\s{4}(\w+): '<svg", icons, re.M)) == sorted(ICON_SIGNATURES)
    assert "fill=\"currentColor\"" in icons and "http" not in icons and "${" not in icons  # fixed markup, never built from user text
    base = CSS[:CSS.index("/* Media queries come last")]
    assert "color: var(--yale)" in re.search(r"\.ico \{([^}]*)\}", base).group(1)
    on_blue = re.search(r"\.callhero \.label \.ico \{([^}]*)\}", base).group(1)
    assert "background: var(--white)" in on_blue and "color: var(--yale)" in on_blue  # a Yale blue icon, legible on the blue card


# 3. The human subline -------------------------------------------------------------------------------------------

@needs_node
def test_one_human_line_sits_under_the_call_card(monkeypatch):
    out = node_run("warmth", base_fixtures(monkeypatch))
    assert out["sub"] == SUBLINE
    base = CSS[:CSS.index("/* Media queries come last")]
    sub = re.search(r"\.callsub \{([^}]*)\}", base).group(1)
    assert "color: var(--muted)" in sub and int(re.search(r"font-size: (\d+)px", sub).group(1)) <= 14  # quiet


# 4. Only a warmth pass --------------------------------------------------------------------------------------------

@needs_node
def test_the_card_order_and_every_header_are_what_they_were(monkeypatch):
    out = node_run("layout", base_fixtures(monkeypatch))
    titles = [t["title"] for t in out["top"] if t["title"]]
    assert titles == ["Call this line", "What your plan covers (Yale student)", "Checklist", "Your timeline", "Do not forget to mention", "Write down",
                      "Track your referral", "Your PCP",  # the referral tracker and the PCP card, because this plan involves a referral and the PCP
                      "If things do not go as planned", "Email or MyChart drafts", "Take this plan with you", "How it decided"]


def test_the_only_new_words_on_the_page_are_the_bulldogs_two_lines_and_the_subline():
    for line in (SAYS_PLAN, SAYS_ANSWER):
        assert line in SCRIPT
    assert f'"{SUBLINE}"' in SCRIPT
    visible = re.sub(r"<script>.*</script>|<style>.*</style>", "", HTML, flags=re.S)
    assert "Here's" not in visible and "explain everything" not in visible  # the landing page itself gained no copy


def test_nothing_the_answers_say_changed(monkeypatch):
    monkeypatch.setattr(agents, "run_agent", __import__("test_safety").fake_model(router=PT_ROUTER, coverage=PT_COVERAGE))
    out = navigator.navigate("student", "lower back pain for weeks, I want physical therapy")
    assert "says" not in json.dumps(out) and "callsub" not in json.dumps(out)  # warmth is all in the page, never in the answer data
    assert out["line"]["phone"] == "(203) 432-0246" and out["coverage"]["items"][0]["answer"].startswith("Covered 100%")
