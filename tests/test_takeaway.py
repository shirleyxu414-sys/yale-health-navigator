"""The end-of-plan "Take this plan with you" section: Copy and Print together, every collapsed section prints, no sticky bar."""

from __future__ import annotations

import re

from test_site import CSS, HTML, SCRIPT, block, fixtures, needs_node, node_run

TITLES = ["If things do not go as planned", "Email or MyChart drafts"]
ALL = ["Track your referral", "Your PCP", *TITLES, "How it decided"]  # every collapsible section, in page order


@needs_node
def test_copy_and_print_are_in_one_section_at_the_very_end_and_nowhere_else(monkeypatch):
    out = node_run("takeaway", fixtures(monkeypatch))
    titles = [t["title"] for t in out["top"] if t["title"]]  # the Start over row and the disclaimer have no title
    assert titles[-2:] == ["Take this plan with you", "How it decided"]  # the plan ends here; "How it decided" sits below as an appendix
    assert titles.index("Take this plan with you") > max(titles.index(t) for t in TITLES)  # after every collapsed section
    assert titles.index("Take this plan with you") > titles.index("Your timeline")
    shown = [t["title"] for t in out["top"]]
    assert shown[-4:] == ["Take this plan with you", "", "", "How it decided"]  # Start over and the disclaimer follow it, then the trace comes last
    copies = [b for b in out["buttonsInPlan"] if b[0] == "Copy plan"]
    prints = [b for b in out["buttonsInPlan"] if b[0] == "Print plan"]
    assert len(copies) == 1 and len(prints) == 1  # one of each, in the plan
    assert copies[0][1] == prints[0][1] and "actions" in copies[0][1]  # side by side, in the same row
    assert not any(b[0] == "Chat with the helper" for b in out["buttonsInPlan"])  # no mid-plan chat button
    section = next(t for t in out["top"] if t["title"] == "Take this plan with you")
    assert "noprint" in section["cls"].split() and "takeaway" in section["cls"].split()  # the buttons do not print


@needs_node
def test_add_to_calendar_stays_beside_the_booked_steps_and_is_not_repeated_at_the_end(monkeypatch):
    out = node_run("takeaway", fixtures(monkeypatch))
    cal = [b for b in out["buttonsInPlan"] if b[0] == "Add to calendar"]
    assert len(cal) == 4 and all("cal-btn" in parent for _, parent in cal)  # the PCP visit and the PTSMC booking, in the timeline and in the tracker
    assert not any("actions" in parent for _, parent in cal)


@needs_node
def test_print_puts_the_same_call_sheet_on_paper_that_copy_puts_on_the_clipboard(monkeypatch):
    out = node_run("takeaway", fixtures(monkeypatch))
    assert out["printed"] == 1 and out["beforePrint"] == {"sheet": False, "sheeting": False}  # nothing extra on screen
    during = out["duringPrint"]
    assert during["sheet"] and during["sheeting"] and out["sheetsDuring"] == 1  # one sheet, even if two print signals arrive
    assert during["text"] == out["copyText"]  # a person who prints and a person who copies get the same sheet
    assert out["afterPrint"] == {"sheet": False, "sheeting": False}  # and it is taken away again
    assert out["mqlDuring"] is True and out["mqlAfter"] is False  # browsers that only report the print media
    assert out["screenStillComplete"] > 0  # the on-screen plan is untouched


@needs_node
def test_the_call_sheet_has_exactly_the_key_info_in_the_asked_order_and_nothing_else(monkeypatch):
    out = node_run("takeaway", fixtures(monkeypatch))
    heads = out["duringPrint"]["headings"]
    order = ["YALE HEALTH NAVIGATOR: YOUR PLAN", "CALL THIS LINE", "WHAT YOUR PLAN COVERS", "TIMELINE", "DO NOT FORGET TO MENTION", "WRITE DOWN", "CHECKLIST", "REFERRAL TRACKER",
             "GET EMERGENCY HELP RIGHT AWAY IF", "IF THINGS DO NOT GO AS PLANNED"]
    assert heads == order
    text = out["copyText"]
    blocks = text.split("\n\n")
    assert blocks[0].startswith("YALE HEALTH NAVIGATOR: YOUR PLAN\nFor: Yale student") and blocks[1].startswith("CALL THIS LINE\nYale Health main line")
    assert blocks[2].startswith("Why: ") and blocks[-1].startswith("Educational guidance only")  # Why comes right after the call block; the disclaimer is last
    assert "Date and time of the appointment: Thu 2:30" in text and "Referral details: ______" in text  # typed values, blanks as ______
    for cut in ["From the rules", "Applies to", "Excluded", "Rules behind", "common.", "student.", "Your PCP", "Referral check", "In plain words", "Email draft", "MyChart message",
                "Also useful", "Do I need a referral?", "Hello Member Services", "starts the process, but approval is not guaranteed"]:
        assert cut not in text, cut


def test_print_css_keeps_the_sections_and_hides_only_the_controls():
    printing = block(CSS, "@media print")
    assert ".noprint" in printing and "display: none !important" in printing
    assert "details.collapse > summary::after { display: none; }" in printing  # no plus sign on paper
    for printable in ("Email or MyChart drafts", "How it decided", "If things do not go as planned", "Track your referral", "Your PCP"):
        assert re.search(rf'collapsible\("{re.escape(printable)}", [^;]*"printable( appendix)?"\)', SCRIPT), printable
    assert re.findall(r'collapsible\("([^"]+)"[^;]*"noprint"\)', SCRIPT) == []  # the interactive checker is gone from the plan, so every section prints


def test_there_is_no_sticky_bar_for_these_actions():
    assert "position: sticky" not in CSS
    fixed = re.findall(r"([^{}]+)\{[^}]*position: fixed", re.sub(r"/\*.*?\*/", "", CSS, flags=re.S))
    assert sorted(f.strip() for f in fixed) == [".chatwin", ".fab"]  # only the chat button and the chat window float
    assert "takeaway" not in " ".join(fixed)
    assert "position" not in re.search(r"\.takeaway \.actions \{([^}]*)\}", CSS).group(1)


def test_the_mid_plan_row_is_gone_and_the_summary_stays_as_text():
    bar = SCRIPT[SCRIPT.index("function renderPlanBar"):SCRIPT.index("function renderTakeAway")]
    assert "button" not in bar and 'elt("p", "plansummary", plan.summary)' in bar
    assert ".barbtns" not in CSS and ".planbar" not in CSS
    order = SCRIPT[SCRIPT.index("function renderPlan(data)"):SCRIPT.index("function render(data)")]
    assert order.index("renderIfNot(plan)") < order.index("renderWriting(") < order.index("renderTakeAway()") < order.index("startOverButton()") < order.index("data.disclaimer") < order.index("renderHow(")


def test_the_end_section_says_what_it_does_and_copy_keeps_using_the_clipboard():
    end = SCRIPT[SCRIPT.index("function renderTakeAway"):SCRIPT.index("// ---- Add to calendar")]
    assert 'card(null, "Take this plan with you", "calendar")' in end and "window.print()" in end and "copyPlan(copy)" in end
    assert "Add to calendar" not in end  # not duplicated here


def test_how_it_decided_is_a_quiet_footnote_row_and_the_page_bottom_clears_the_chat_button():
    assert re.search(r'collapsible\("How it decided", \[[^;]*\], "printable appendix"\)', SCRIPT)  # same title, content and collapsed behavior
    base = CSS[:CSS.index("/* Media queries come last")]
    row = re.search(r"details\.collapse\.appendix \{([^}]*)\}", base).group(1)
    assert "background: none" in row and "border: none" in row and "box-shadow: none" in row  # not a white card
    assert "color: var(--muted)" in re.search(r"details\.collapse\.appendix > summary \{([^}]*)\}", base).group(1)
    assert int(re.search(r"font-size: (\d+)px", re.search(r"details\.collapse\.appendix > summary \{([^}]*)\}", base).group(1)).group(1)) <= 13
    main = int(re.search(r"main \{[^}]*padding: 0 20px (\d+)px", base).group(1))
    fab = re.search(r"\.fab \{[^}]*bottom: (\d+)px[^}]*min-height: (\d+)px", base)
    assert main >= int(fab.group(1)) + int(fab.group(2)) + 40  # the button never covers the last row when scrolled to the bottom
    phone = block(CSS, "@media (max-width: 560px)")
    assert int(re.search(r"main \{ padding: 14px 12px (\d+)px", phone).group(1)) >= 12 + 52 + 40
