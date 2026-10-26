"""The Write down fields: real inputs, held in memory for the session only, kept across re-renders, printed on the dotted lines."""

from __future__ import annotations

import re

from test_site import CSS, HTML, SCRIPT, block, fixtures, needs_node, node_run

LABELS = ["Date and time of the appointment", "Referral details", "Name of the person you spoke to"]


def test_each_blank_is_a_text_input_with_a_dotted_underline():
    base = CSS[:CSS.index("/* Media queries come last")]
    field = re.search(r"\.blank input \{([^}]*)\}", base).group(1)
    assert "border: none" in field and "border-bottom: 1.5px dotted var(--muted)" in field and "background: transparent" in field and "flex: 1" in field
    assert "::after" not in re.search(r"\.blank \{[^}]*\}", base).group(0) and ".blank::after" not in CSS  # the old drawn line is gone
    code = SCRIPT[SCRIPT.index("function renderWriteDown"):SCRIPT.index("function renderSafetyNet")]
    assert 'el("input")' in code and 'input.type = "text"' in code and 'el("label", "blank")' in code and "maxLength" in code
    assert 'input.setAttribute("aria-label", t)' in code  # a screen reader hears which blank it is


def test_what_is_typed_stays_in_memory_only():
    for forbidden in ["localStorage", "sessionStorage", "indexedDB", "document.cookie", "navigator.sendBeacon", "XMLHttpRequest"]:
        assert forbidden not in SCRIPT, forbidden
    code = SCRIPT[SCRIPT.index("function renderWriteDown"):SCRIPT.index("function renderSafetyNet")]
    assert "fetch(" not in code  # typing never sends anything
    assert 'autocomplete = "off"' in code  # and the browser is asked not to remember the entries either
    assert "const written = {}" in SCRIPT and "written[t] = input.value" in code and "input.value = written[t] || \"\"" in code


def test_the_typed_values_are_cleared_with_a_new_plan_but_kept_for_a_re_run():
    assert SCRIPT.count("clearWritten();") == 4  # Start over, a brand-new question, the example plan, a plan the chat starts from a situation
    assert "function clearWritten()" in SCRIPT
    new_question = SCRIPT[SCRIPT.index('$("go").addEventListener("click"'):SCRIPT.index("// Print puts the call sheet on paper")]
    assert "clearWritten();" in new_question
    run_fn = SCRIPT[SCRIPT.index("async function run(extra)"):SCRIPT.index("function selectRole")]
    assert "clearWritten" not in run_fn  # the referral button and the timing buttons re-run the same plan and keep what was typed


def test_printing_shows_the_typed_text_on_the_dotted_line():
    printing = block(CSS, "@media print")
    assert ".blank input, .stage > input[type=date] { display: none; }" in printing  # the box itself is hidden on paper
    paper = re.search(r"\.blank \.printval \{([^}]*)\}", printing).group(1)
    assert "display: block" in paper and "border-bottom: 1.5px dotted var(--ink)" in paper and "overflow-wrap: anywhere" in paper and "min-height" in paper
    assert re.search(r"\.blank \.printval \{ display: none; \}", CSS[:CSS.index("/* Media queries come last")])  # on screen only the input shows
    assert 'onPaper.textContent = input.value' in SCRIPT  # the printed line follows the typing


@needs_node
def test_typed_values_survive_ticks_redraws_and_the_referral_button(monkeypatch):
    out = node_run("written", fixtures(monkeypatch))
    assert [r["label"] for r in out["initial"]] == LABELS and all(r["value"] == "" and r["type"] == "text" for r in out["initial"])
    assert out["maxLength"] == 300 and out["autocomplete"] == "off"
    typed = [("Thu Nov 5, 2:30 pm"), "Referral A-1042", "Maria"]
    for stage in ("typed", "afterTick", "afterRerender", "afterReferralButton"):
        assert [r["value"] for r in out[stage]] == typed, stage
        assert [r["onPaper"] for r in out[stage]] == typed, stage  # the printed copy is kept in step
    assert [r["value"] for r in out["afterNewQuestion"]] == ["", "", ""]  # a new question is a new plan
    assert [r["value"] for r in out["afterStartOver"]] == ["", "", ""] and [r["onPaper"] for r in out["afterStartOver"]] == ["", "", ""]
