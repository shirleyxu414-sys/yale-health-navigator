"""Website behaviour and layout: ticked boxes, past dates, start over, double-submit, phone CSS, focus, print, depth.

The behaviour tests run the page's own script in Node against a tiny fake page (skipped if Node is not installed).
The layout tests read the page's CSS. No model is called.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

import agents
import navigator
from models import Answer
from test_flow import PT_COVERAGE, PT_ROUTER, run
from test_safety import PLAN_REPLY, fake_model, router_reply

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text()
DEMO = (ROOT / "frontend" / "safety_demo.html").read_text()
CSS = re.search(r"<style>(.*?)</style>", HTML, re.S).group(1)
SCRIPT = re.search(r"<script>(.*)</script>", HTML, re.S).group(1)
NODE = shutil.which("node")


def shape(out: dict) -> dict:
    out = dict(out)
    out.pop("_meta", None)
    return Answer.model_validate(out).model_dump(exclude_none=True, mode="json")


def pt_plan(monkeypatch, **kw) -> dict:
    return shape(run(monkeypatch, **kw))


# ---------------------------------------------------------------------------------------------------
# A tiny fake page, enough to run the real script and look at what it did.
DRIVER = r"""
const vm = require("vm"), fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const js = html.match(/<script>([\s\S]*)<\/script>/)[1];
const fixtures = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const all = [];
class El {
  constructor(tag) { this.tag = tag; this.children = []; this.parent = null; this.className = ""; this.listeners = {}; this._text = "";
    this.style = {}; this.attrs = {}; this.hidden = false; this.disabled = false; this.checked = false; this.value = ""; this.min = ""; all.push(this);
    this.classList = { add: (...c) => { this.className += " " + c.join(" "); }, remove: (c) => { this.className = this.className.split(" ").filter((x) => x !== c).join(" "); } }; }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); }
  set textContent(v) { this._text = String(v); this.children = []; }
  append(...n) { n.forEach((x) => { x.parent = this; this.children.push(x); }); }
  replaceChildren(...n) { this.children = []; this._text = ""; this.append(...n); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter((c) => c !== this); }
  setAttribute(k, v) { this.attrs[k] = v; } scrollIntoView() { this.scrolled = (this.scrolled || 0) + 1; } select() {} focus() {} blur() { this.blurred = true; }
  get parentNode() { return this.parent; }
  get firstChild() { return this.children[0]; }
  insertAdjacentElement(pos, node) { const kids = this.parent.children; kids.splice(kids.indexOf(this) + 1, 0, node); node.parent = this.parent; return node; }
  addEventListener(e, f) { (this.listeners[e] = this.listeners[e] || []).push(f); }
  hasClass(c) { return this.className.split(/\s+/).includes(c); }
  walk(f) { f(this); this.children.forEach((c) => c.walk(f)); }
  find(pred) { let hit = null; this.walk((n) => { if (!hit && pred(n)) hit = n; }); return hit; }
  findAll(pred) { const all = []; this.walk((n) => { if (pred(n)) all.push(n); }); return all; }
  querySelector(sel) { const c = sel.replace(".", ""); return this.find((n) => n !== this && n.hasClass(c)); }
  fire(e) { return Promise.all((this.listeners[e] || []).map((f) => f({ preventDefault() {} }))); }
}
const ids = {};
["roles","chips","chipNotice","situation","go","goHint","example","error","result","dog","roleCard","refCard","refForm","refInput","refGo","refNotice","refResult","refCombo","refArrow","refList","askCard","chatFab","chatWin","chatClose","chatThread","chatRoleLine","chatChips","chatForm","chatInput","chatSend","thinkDog","chatDog"].forEach((i) => (ids[i] = new El("div")));
ids.go.textContent = "Find my next step";
// The same starting state as the real page: the chat button is showing, the window is closed, and the send button is marked to lock.
ids.result.hidden = true; ids.refList.hidden = true; ids.refNotice.hidden = true; ids.thinkDog.hidden = true; ids.chatFab.hidden = false; ids.chatWin.hidden = true; ids.chatSend.className = "primary lock";
const doc = {
  getElementById: (i) => ids[i] || (doc.body && doc.body.find((n) => n.id === i)), createElement: (t) => new El(t), createTextNode: (t) => { const n = new El("#t"); n._text = t; return n; },
  createDocumentFragment: () => new El("frag"), body: new El("body"),
  addEventListener(e, f) { (docHandlers[e] = docHandlers[e] || []).push(f); },
  querySelectorAll: (sel) => { const cls = sel.split(",").map((s) => s.trim().replace(".", "")); return all.filter((n) => cls.some((c) => n.hasClass(c))); },
};
const docHandlers = {};
let fetchCalls = 0, pending = null; const bodies = []; const copied = []; let printed = 0; const winHandlers = {};
const ctx = { document: doc, window: { scrollTo() {}, print() { printed++; }, addEventListener(e, f) { (winHandlers[e] = winHandlers[e] || []).push(f); }, matchMedia: () => ({ addEventListener(e, f) { winHandlers.mql = f; } }) }, navigator: { userAgent: "Mozilla/5.0 (Macintosh)", clipboard: { writeText: async (t) => { copied.push(t); } } }, console, Date, Math, TextEncoder, URL: { createObjectURL() { return "blob:x"; }, revokeObjectURL() {} },
  Blob: function () {}, setTimeout, crypto: {},
  fetch: async (url, opts) => { if (String(url).startsWith("/api/departments")) return { ok: true, json: async () => ({ departments: fixtures.departments || ["Dermatology", "Physical Therapy"] }) };
    fetchCalls++; bodies.push({ url, body: opts && opts.body ? JSON.parse(opts.body) : null });
    if (url === "/api/chat" && fixtures.chatFail) return { ok: false, json: async () => ({ detail: [{ type: "missing", loc: ["body", "role"] }] }) };
    if (url === "/api/referral") return { ok: true, json: async () => fixtures.referral };
    const reply = pending ? await pending : (url === "/api/chat" ? (fixtures.chatSeq && fixtures.chatSeq.length ? fixtures.chatSeq.shift() : fixtures.chat) : fixtures.next);
    return { ok: true, json: async () => reply }; } };
vm.createContext(ctx);
vm.runInContext(js + "\n;globalThis.__t = { syncHome: syncHomeDepartments, render, state: () => ({ sessionId, ticked: [...ticked], busy, role }), setRole: (r) => { role = r; }, todayIso, isPastDate, openStatus, planAsText, directionsUrl };", ctx);
const T = ctx.__t, out = {};
const roleInput = {}; all.filter((n) => n.tag === "input" && n.type === "radio").forEach((n) => { roleInput[n.value] = n; });
const live = (root, pred) => root.find(pred);
const byText = (t) => ids.result.find((n) => n.tag === "button" && n.textContent === t);
const checkbox = (id) => ids.result.find((n) => n.tag === "input" && n.id === id);
const chips = () => all.filter((n) => n.hasClass("chip"));
const tick = async (id) => { const b = checkbox(id); b.checked = true; await b.fire("change"); };
const wait = () => new Promise((r) => setTimeout(r, 15));
const scenario = process.argv[4];

(async () => {
  if (!["hint", "example", "home", "home_pending"].includes(scenario)) { T.setRole("student"); ids.situation.value = "lower back pain for weeks, I want physical therapy"; }
  if (scenario === "example") {
    ids.go.disabled = false;
    await ids.example.fire("click"); await wait();
    out.state = T.state(); out.situation = ids.situation.value; out.fetched = fetchCalls; out.shown = !ids.result.hidden;
    out.notice = ids.result.textContent.includes("This is an example plan"); out.referralButton = !!byText("I have my referral");
    out.roleChecked = !!roleInput.student && roleInput.student.checked;
  }
  if (scenario === "hint") {
    ids.situation.value = ""; await ids.situation.fire("input");
    out.empty = { hintHidden: ids.goHint.hidden, goDisabled: ids.go.disabled };
    ids.situation.value = "back pain"; await ids.situation.fire("input");
    out.textOnly = { hintHidden: ids.goHint.hidden, goDisabled: ids.go.disabled };
    T.setRole(null); roleInput.student.checked = true; await roleInput.student.fire("change");
    out.ready = { hintHidden: ids.goHint.hidden, goDisabled: ids.go.disabled };
    ids.situation.value = ""; await ids.situation.fire("input");
    out.roleOnly = { hintHidden: ids.goHint.hidden, goDisabled: ids.go.disabled };
  }
  if (scenario === "status") {
    out.results = fixtures.cases.map((c) => T.openStatus(c.hours, new Date(c.now[0], c.now[1] - 1, c.now[2], c.now[3], c.now[4])).map((r) => r.text));  // months are 1-12 in the test data
    out.parsed = fixtures.hours.map((h) => T.openStatus(h, new Date(2026, 9, 26, 12, 0)).map((r) => [r.label, r.text]));
  }
  if (scenario === "taps") {
    const PHONE = /\(\d{3}\) \d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b|\b911\b|\b988\b/;
    const check = (data) => {
      T.render(data); const bare = [], links = [];
      const walk = (n, inLink) => { const link = inLink || n.tag === "a";
        if (n._text && PHONE.test(n._text) && !link && n.tag !== "textarea" && n.tag !== "input" && n.tag !== "code") bare.push(n._text);
        if (n.tag === "a" && n.hasClass("tel")) links.push([n.textContent, n.href]); n.children.forEach((c) => walk(c, link)); };
      ids.result.children.forEach((c) => walk(c, false));
      return { bare, links };
    };
    out.plan = check(fixtures.plan); out.emergency = check(fixtures.emergency);
  }
  if (scenario === "copy") {
    T.render(fixtures.plan); await tick("called");
    const inputs = ids.result.findAll((n) => n.tag === "input" && n.type === "text");
    inputs[0].value = "Thu Nov 5, 2:30 pm"; await inputs[0].fire("input"); inputs[2].value = "Maria"; await inputs[2].fire("input");
    const before = fetchCalls, btn = byText("Copy plan"); await btn.fire("click"); await wait();
    out.copied = copied; out.label = btn.textContent; out.sent = fetchCalls - before; out.text = T.planAsText();
  }
  if (scenario === "terms") {
    T.render(fixtures.plan);
    const buttons = () => ids.result.findAll((n) => n.tag === "button" && n.hasClass("term"));
    out.terms = buttons().map((b) => [b.textContent, b.parent.tag]);
    const first = buttons()[0]; await first.fire("click");
    const boxes = () => ids.result.findAll((n) => n.hasClass("gloss"));
    out.open = boxes().map((b) => b.textContent); out.expanded = first.attrs["aria-expanded"];
    await first.fire("click"); out.closed = boxes().length; out.expandedAfter = first.attrs["aria-expanded"];
    out.textOnly = ids.result.textContent.includes("prior authorization") || ids.result.textContent.includes("PCP");
    const badTerm = buttons().filter((b) => /copay|dry needling/i.test(b.textContent)).length; out.badTerms = badTerm;
  }
  if (scenario === "home" || scenario === "home_pending") {
    const texts = () => ids.chatThread.children.map((m) => m.textContent.slice(0, 300));
    out.fabOnLoad = { hidden: ids.chatFab.hidden, plan: ids.result.hidden };
    await ids.chatFab.fire("click");
    out.open = { windowShown: !ids.chatWin.hidden, thread: texts(), chips: ids.chatChips.children.map((c) => c.textContent) };
    if (scenario === "home_pending") {
      ids.chatInput.value = "Is physical therapy covered for me?"; await ids.chatForm.fire("submit"); await wait();
      out.afterQuestion = texts();
    }
    const calls = fetchCalls;
    const chip = ids.chatChips.children.find((c) => c.textContent === "Staff or faculty");
    await chip.fire("click"); await wait();
    out.requestsForTheChip = fetchCalls - calls - (scenario === "home_pending" ? 1 : 0);  // the pending question is the only request allowed
    out.state = T.state(); out.radio = !!roleInput.staff_faculty.checked; out.thread = texts();
    out.chipsAfter = ids.chatChips.children.map((c) => c.textContent);
    out.bodies = bodies.map((b) => ({ url: b.url, role: b.body.role, question: b.body.question, answering_role: b.body.answering_role, has_plan: b.body.has_plan, history: b.body.history }));
  }
  if (scenario === "toolong" || scenario === "chat_fail") {
    T.setRole("student"); roleInput.student.checked = true; await ids.chatFab.fire("click");
    const q = scenario === "toolong" ? "x".repeat(600) : "Is PT covered?";
    ids.chatInput.value = q; await ids.chatForm.fire("submit"); await wait();
    out.last = ids.chatThread.children[ids.chatThread.children.length - 1].textContent; out.requests = fetchCalls; out.busy = T.state().busy;
    out.maxLength = ids.chatInput.maxLength;
  }
  if (scenario === "home_plan") {
    T.setRole("student"); roleInput.student.checked = true; ids.situation.value = "";
    await ids.chatFab.fire("click");
    ids.chatInput.value = "lower back pain for weeks"; await ids.chatForm.fire("submit"); await wait(); await wait();
    out.bodies = bodies.map((b) => ({ url: b.url, role: b.body.role, question: b.body.question, situation: b.body.situation, has_plan: b.body.has_plan, session: /^[A-Za-z0-9-]{8,64}$/.test(b.body.session_id) }));
    out.planShown = !ids.result.hidden && ids.result.textContent.includes("Call this line");
    out.chat = { windowHidden: ids.chatWin.hidden, fabShown: !ids.chatFab.hidden };
    out.situationBox = ids.situation.value; out.busy = T.state().busy;
    fixtures.chatSeq = [fixtures.chat]; await ids.chatFab.fire("click");
    ids.chatInput.value = "Is that covered?"; await ids.chatForm.fire("submit"); await wait();
    const last = bodies[bodies.length - 1].body; out.followUp = { url: bodies[bodies.length - 1].url, has_plan: last.has_plan, wants: last.context && last.context.wants, role: last.role };
  }
  if (scenario === "written") {
    ids.go.disabled = false;
    const rows = () => ids.result.findAll((n) => n.tag === "label" && n.hasClass("blank"));
    const snap = () => rows().map((r) => ({ label: r.children[0].textContent, value: r.children[1].value, onPaper: r.children[2].textContent, type: r.children[1].type }));
    const typeAll = async (values) => { for (const [i, v] of values.entries()) { const input = rows()[i].children[1]; input.value = v; await input.fire("input"); } };
    T.render(fixtures.plan);
    out.initial = snap(); out.maxLength = rows()[0].children[1].maxLength; out.autocomplete = rows()[0].children[1].autocomplete;
    await typeAll(["Thu Nov 5, 2:30 pm", "Referral A-1042", "Maria"]);
    out.typed = snap();
    await tick("called"); out.afterTick = snap();                                 // ticking a box redraws nothing it should not
    T.render(fixtures.plan2); out.afterRerender = snap();                         // the plan is drawn again from scratch
    await byText("I have my referral").fire("click"); await wait(); out.afterReferralButton = snap();
    ids.go.disabled = false; ids.situation.value = "something new";
    await ids.go.fire("click"); await wait(); out.afterNewQuestion = snap();      // a brand-new question is a new plan
    await typeAll(["again", "x", "y"]); await byText("Start over").fire("click"); T.render(fixtures.plan); out.afterStartOver = snap();
  }
  if (scenario === "calendar_dirs") {
    T.render(fixtures.plan);
    await ids.result.findAll((x) => x.tag === "button" && x.textContent === "Add to calendar")[0].fire("click");
    const form = ids.result.find((x) => x.hasClass("calform"));
    out.formDirections = form.findAll((x) => x.tag === "a" && x.hasClass("directions")).map((a) => [a.textContent, a.href]);
    out.heroDirections = ids.result.findAll((x) => x.tag === "a" && x.hasClass("directions")).map((a) => [a.textContent, a.href, a.target]);
    out.place = ids.result.find((x) => x.hasClass("placerow")).textContent;
  }
  if (scenario === "takeaway") {
    T.render(fixtures.plan);
    const all = () => ids.result.findAll((n) => n.tag === "details" && n.hasClass("collapse"));
    out.top = ids.result.children.map((n) => ({ cls: n.className.trim(), title: (n.find((x) => x.tag === "h2" || x.tag === "summary") || { textContent: "" }).textContent }));
    out.buttonsInPlan = ids.result.findAll((n) => n.tag === "button").map((b) => [b.textContent, (b.parent || {}).className || ""]);
    const sheet = () => doc.body.find((n) => n.id === "printSheet");
    const sheetText = () => { const sh = sheet(); return sh ? sh.children.map((sec) => sec.children.map((c) => c.textContent).join("\n")).join("\n\n") : null; };
    out.beforePrint = { sheet: !!sheet(), sheeting: doc.body.hasClass("sheeting") };
    // type into Write down and tick a box, then print
    const fields = ids.result.findAll((n) => n.tag === "input" && n.type === "text"); fields[0].value = "Thu 2:30"; await fields[0].fire("input");
    out.copyText = T.planAsText(fixtures.plan);
    await byText("Print plan").fire("click"); out.printed = printed;
    out.duringPrint = { sheet: !!sheet(), sheeting: doc.body.hasClass("sheeting"), text: sheetText(), headings: sheet().findAll((n) => n.tag === "h1" || n.tag === "h2").map((n) => n.textContent) };
    for (const f of winHandlers.beforeprint || []) f();  // a second signal for the same print adds nothing
    out.sheetsDuring = doc.body.findAll((n) => n.id === "printSheet").length;
    for (const f of winHandlers.afterprint || []) f();
    out.afterPrint = { sheet: !!sheet(), sheeting: doc.body.hasClass("sheeting") };
    if (winHandlers.mql) { winHandlers.mql({ matches: true }); out.mqlDuring = !!sheet(); winHandlers.mql({ matches: false }); out.mqlAfter = !!sheet(); }
    out.screenStillComplete = ids.result.findAll((n) => n.tag === "details").length;
  }
  if (scenario === "tracker") {
    T.render(fixtures.plan);
    const stages = () => ids.result.findAll((n) => n.hasClass("stage")).map((r) => ({
      label: r.find((x) => x.hasClass("stagelabel")).textContent, done: r.find((x) => x.tag === "input" && x.type === "checkbox").checked,
      date: r.find((x) => x.tag === "input" && x.type === "date").value, paper: r.find((x) => x.hasClass("printval")).textContent,
      calendar: r.findAll((x) => x.tag === "button" && x.textContent === "Add to calendar").length }));
    out.start = stages();
    out.note = ids.result.find((n) => n.hasClass("tracker")).find((x) => x.hasClass("meta")).textContent;
    const rows = () => ids.result.findAll((n) => n.hasClass("stage"));
    const box = (i) => rows()[i].find((x) => x.tag === "input" && x.type === "checkbox"), date = (i) => rows()[i].find((x) => x.tag === "input" && x.type === "date");
    box(0).checked = true; await box(0).fire("change"); box(1).checked = true; await box(1).fire("change");
    date(0).value = "2026-11-12"; await date(0).fire("input"); date(3).value = "2026-11-20"; await date(3).fire("input");
    out.typed = stages();
    T.render(fixtures.plan2plan); out.afterRender = stages();
    // the calendar from stage 4 starts from the date typed for that stage
    await rows()[3].find((x) => x.tag === "button" && x.textContent === "Add to calendar").fire("click");
    const form = rows()[3].find((x) => x.hasClass("calform"));
    const fdate = form.find((x) => x.tag === "input" && x.type === "date"), ftime = form.find((x) => x.tag === "input" && x.type === "time"), save = form.find((x) => x.tag === "button" && x.type === "submit");
    out.calendar = { date: fdate.value, time: ftime.value, saveDisabled: save.disabled, title: form.find((x) => x.tag === "input" && x.maxLength === 150).value };
    ftime.value = "10:15"; await ftime.fire("input"); out.calendarAfterTime = save.disabled;
    out.copy = T.planAsText();
    await byText("Start over").fire("click"); T.render(fixtures.plan); out.afterStartOver = stages();
  }
  if (scenario === "planbutton") {
    T.setRole("student");
    const btns = (root) => root.findAll((n) => n.tag === "button" && n.textContent.startsWith("Get a plan for")).map((b) => b.textContent);
    ids.refInput.value = "Anything"; await ids.refForm.fire("submit"); await wait();
    out.home = { buttons: btns(ids.refResult) };
    const b = ids.refResult.findAll((n) => n.tag === "button" && n.textContent.startsWith("Get a plan for"))[0];
    if (b) { await b.fire("click"); await wait(); out.tapped = { situation: ids.situation.value, navigate: bodies.filter((x) => x.url === "/api/navigate").map((x) => ({ situation: x.body.situation, role: x.body.role })) }; }
  }
  if (scenario === "presscheck") {
    T.setRole("student"); ids.refInput.value = "Dermatology";
    const during = ids.refResult.textContent;
    const pressed = ids.refGo.fire("pointerdown");  // the press itself submits
    out.whileRunning = ids.refResult.textContent; out.blurred = !!ids.refInput.blurred;
    await ids.refForm.fire("submit");  // the click that follows the same press
    await pressed; await wait();
    out.requests = bodies.filter((b) => b.url === "/api/referral").length; out.result = ids.refResult.textContent; out.scrolled = ids.refResult.scrolled || 0;
  }
  if (scenario === "homeref") {
    T.setRole(null);
    ids.refInput.value = "Dermatology"; await ids.refForm.fire("submit"); await wait();
    out.noRole = { notice: !ids.refNotice.hidden, requests: bodies.filter((b) => b.url === "/api/referral").length, result: ids.refResult.textContent };
    T.setRole("student"); await ids.refForm.fire("submit"); await wait();
    out.withRole = { notice: !!ids.refNotice.hidden, request: bodies.filter((b) => b.url === "/api/referral").map((b) => b.body), result: ids.refResult.textContent, pill: ids.refResult.find((x) => x.hasClass("pill")).className.trim() };
    ids.refInput.value = "x"; await ids.refForm.fire("submit"); out.tooShort = bodies.filter((b) => b.url === "/api/referral").length;
  }
  if (scenario === "checker") {
    T.setRole("student"); await T.syncHome();
    const input = ids.refInput, arrowBtn = ids.refArrow, listEl = ids.refList;
    const items = () => listEl.findAll((n) => n.hasClass("comboitem")).map((x) => x.textContent);
    out.before = ids.refResult.textContent;
    out.listAtStart = listEl.hidden;
    await arrowBtn.fire("click"); out.options = items(); out.openAfterArrow = !listEl.hidden;
    await arrowBtn.fire("click"); out.closedByArrow = listEl.hidden;
    input.value = "Dermatology"; await arrowBtn.fire("click"); out.fullWithTextTyped = items();  // the arrow still shows every department
    input.value = "derm"; await input.fire("input"); out.filtered = items();
    await listEl.find((n) => n.hasClass("comboitem")).fire("click"); out.picked = { value: input.value, closed: listEl.hidden };
    input.value = "Cardiology"; await input.fire("input"); out.noMatchClosed = listEl.hidden; out.freeText = input.value;
    await arrowBtn.fire("click"); for (const f of docHandlers.pointerdown || []) f({ target: {} }); out.closedByOutsidePress = listEl.hidden;
    input.value = "Dermatology"; await ids.refForm.fire("submit"); await wait();
    out.request = bodies.filter((b) => b.url === "/api/referral").map((b) => b.body);
    out.result = ids.refResult.textContent; out.pill = ids.refResult.find((x) => x.hasClass("pill")).className.trim();
    out.noRuleOnPage = ids.refResult.findAll((n) => n.hasClass("rule")).length;
  }

  if (scenario === "norule") {
    T.render(fixtures.plan);
    const how = ids.result.find((n) => n.tag === "details" && n.find((x) => x.tag === "summary" && x.textContent === "How it decided"));
    const outside = []; ids.result.walk((n) => { if (n.hasClass("rule") && !n.hasClass("quote")) { let p = n, inHow = false; while (p) { if (p === how) inHow = true; p = p.parent; } if (!inHow) outside.push(n.textContent); } });
    out.rulesOutsideHow = outside; out.net = ids.result.find((n) => n.hasClass("redflags")).textContent;
    out.howRules = how.findAll((n) => n.hasClass("rule")).map((n) => n.textContent.split(".")[0] + "." + (n.textContent.split(".")[1] || "").split(" ")[0]);
    out.howText = how.textContent;
    const terms = ids.result.findAll((n) => n.tag === "button" && n.hasClass("term")); await terms[0].fire("click");
    out.gloss = ids.result.find((n) => n.hasClass("gloss")).textContent;
    // every details panel but "How it decided": no rule rows
    const others = []; ids.result.findAll((n) => n.tag === "details" && n !== how).forEach((d) => d.walk((n) => { if (n.hasClass("rule") && !n.hasClass("quote")) others.push(n.textContent); })); out.rulesInOtherPanels = others;
  }
  if (scenario === "warmth") {
    T.render(fixtures.plan);
    const kids = ids.result.children;
    out.order = kids.map((n) => n.className.trim().split(" ")[0]).slice(0, 5);
    const says = ids.result.find((n) => n.hasClass("dogsays"));
    out.says = says.find((n) => n.hasClass("says")).textContent;
    out.dogClasses = says.findAll((n) => n.tag === "div" && n.className).map((n) => n.className.trim());
    out.cheer = says.find((n) => n.hasClass("bulldog")).className.includes("cheer");
    out.sub = ids.result.find((n) => n.hasClass("callsub")).textContent;
    out.icons = ids.result.findAll((n) => n.hasClass("ico")).map((n) => ({ parent: (n.parent.hasClass("label") ? "label:" : "") + n.parent.textContent, html: n.innerHTML.slice(0, 200), aria: n.attrs["aria-hidden"] }));
    out.headers = ids.result.findAll((n) => n.tag === "h2").map((n) => [n.textContent, n.children.some((c) => c.hasClass("ico"))]);
  }
  if (scenario === "no_dog_for_emergency") {
    T.render(fixtures.emergency); out.dogsays = ids.result.findAll((n) => n.hasClass("dogsays")).length; out.icons = ids.result.findAll((n) => n.hasClass("ico")).length;
  }
  if (scenario === "thinking") {
    const dogs = () => ({ hero: ids.dog.className.includes("thinking"), thinkHidden: ids.thinkDog.hidden, thinkDog: !!ids.thinkDog.children[0] && ids.thinkDog.children[0].className.includes("thinking"), chat: ids.chatDog.className.includes("thinking") });
    out.start = dogs();
    let release; pending = new Promise((r) => { release = r; }); ids.go.disabled = false;
    const running = ids.go.fire("click"); await wait();
    out.whilePlan = dogs(); out.button = ids.go.textContent;
    release(fixtures.plan); await running; await wait(); out.afterPlan = dogs();
    await ids.chatFab.fire("click"); pending = new Promise((r) => { release = r; });
    ids.chatInput.value = "Is dry needling covered?"; const asking = ids.chatForm.fire("submit"); await wait();
    out.whileChat = dogs(); release(fixtures.chat); await asking; await wait(); out.afterChat = dogs();
  }
  if (scenario === "badges") {
    T.render(fixtures.plan);
    out.hero = ids.result.find((x) => x.hasClass("callhero")).findAll((x) => x.hasClass("openstatus")).map((b) => [b.className.trim(), b.textContent]);
    out.heroHours = ids.result.find((x) => x.hasClass("callhero")).textContent;
  }
  if (scenario === "calendar") {
    T.render(fixtures.plan);
    const openForm = async (n) => { await ids.result.findAll((x) => x.tag === "button" && x.textContent === "Add to calendar")[n].fire("click"); return ids.result.find((x) => x.hasClass("calform")); };
    const form = await openForm(0);
    const date = form.find((x) => x.tag === "input" && x.type === "date"), time = form.find((x) => x.tag === "input" && x.type === "time");
    const save = form.find((x) => x.tag === "button" && x.type === "submit");
    const note = form.find((x) => x.hasClass("fine") && x.textContent.includes("Pick the date and time"));
    const state = () => ({ date: date.value, time: time.value, saveDisabled: save.disabled, messageHidden: !!note.hidden });
    out.start = state();
    const type = async (el, v) => { el.value = v; await el.fire("input"); };
    await type(date, T.todayIso(new Date(Date.now() + 3 * 86400000))); out.dateOnly = state();
    await type(time, "14:30"); out.both = state();
    await type(date, "2020-01-01"); out.pastDate = state();
    await type(date, ""); out.cleared = state();
    out.copy = ids.result.text ? 1 : 0;
  }
  if (scenario === "layout" || scenario === "admin" || scenario === "dedupe") {
    T.render(fixtures[scenario === "layout" ? "plan" : scenario]);
    const title = (n) => { const h = n.find((x) => x.tag === "h2" || x.tag === "summary" || x.hasClass("label")); return h ? h.textContent : ""; };
    out.top = ids.result.children.map((n) => ({ cls: n.className.trim(), tag: n.tag, title: title(n), open: !!n.open }));
    out.text = ids.result.textContent;
    out.buttons = ids.result.children.length ? [] : [];
    out.hasPrint = !!byText("Print plan"); out.hasChatBtn = !!byText("Chat with the helper");
    const pills = []; ids.result.walk((n) => { if (n.hasClass("pill")) pills.push([n.className.trim(), n.textContent]); }); out.pills = pills;
    const quotes = []; ids.result.walk((n) => { if (n.hasClass("quote")) quotes.push(n.textContent); }); out.quotes = quotes;
    const rules = []; ids.result.walk((n) => { if (n.hasClass("rule") && !n.hasClass("quote")) rules.push(n.textContent); }); out.ruleLines = rules;
    const cardEl = ids.result.find((n) => n.hasClass("verdict")); out.cardText = cardEl ? cardEl.textContent : "";
    const cardRules = []; if (cardEl) cardEl.walk((n) => { if (n.hasClass("rule") && !n.hasClass("quote")) cardRules.push(n.textContent); }); out.cardRuleLines = cardRules;
    const howEl = ids.result.find((n) => n.tag === "details" && n.find((x) => x.tag === "summary" && x.textContent === "How it decided"));
    if (howEl) { out.how = { open: !!howEl.open, title: "How it decided" }; out.howText = howEl.textContent; const hl = []; howEl.walk((n) => { if (n.hasClass("rule")) hl.push(n.textContent); }); out.howRuleLines = hl; }
  }
  if (scenario === "chat") {
    T.render(fixtures.plan);
    out.launcher = { fabShown: !ids.chatFab.hidden, windowHidden: ids.chatWin.hidden };
    await ids.chatFab.fire("click");
    out.opened = { windowShown: !ids.chatWin.hidden, fabHidden: ids.chatFab.hidden };
    const texts = () => ids.chatThread.children.map((m) => [m.className.trim(), m.textContent.slice(0, 400)]);
    out.welcome = texts(); out.starters = ids.chatChips.children.map((c) => c.textContent);
    const say = async (q) => { ids.chatInput.value = q; await ids.chatForm.fire("submit"); await wait(); };
    await say("Is dry needling covered?"); out.afterOne = texts();
    await say("What about acupuncture?"); out.afterTwo = texts(); out.startersAfter = ids.chatChips.children.length;
    out.bodies = bodies.map((b) => ({ url: b.url, role: b.body.role, question: b.body.question, history: b.body.history, context: b.body.context,
      hasSession: /^[A-Za-z0-9-]{8,64}$/.test(b.body.session_id) }));
    out.busyAfter = T.state().busy; out.inputCleared = ids.chatInput.value === "";
    await ids.chatClose.fire("click"); out.closed = { windowHidden: ids.chatWin.hidden, fabShown: !ids.chatFab.hidden };
    T.render(fixtures.plan2plan);  // the plan is drawn again (for example after "I have my referral"): the thread stays
    await ids.chatFab.fire("click"); out.afterRerender = texts().length;
    await byText("Start over").fire("click");
    out.afterStartOver = { windowHidden: ids.chatWin.hidden, fabHidden: ids.chatFab.hidden, state: T.state().sessionId !== out.bodies[0].sessionId };
    T.render(fixtures.plan); await ids.chatFab.fire("click"); out.threadAfterStartOver = texts().length;
  }
  if (scenario === "chat_busy") {
    T.render(fixtures.plan); await ids.chatFab.fire("click");
    let release; pending = new Promise((r) => { release = r; });
    ids.chatInput.value = "Is dry needling covered?"; const running = ids.chatForm.fire("submit"); await wait();
    out.during = { busy: T.state().busy, sendDisabled: ids.chatSend.disabled, chipsDisabled: chips().every((c) => c.disabled), typing: ids.chatThread.children.some((m) => m.hasClass("typing")) };
    const calls = fetchCalls; ids.chatInput.value = "again"; await ids.chatForm.fire("submit"); out.extraCalls = fetchCalls - calls;
    release(fixtures.chat); await running; await wait();
    out.after = { busy: T.state().busy, sendDisabled: ids.chatSend.disabled, typing: ids.chatThread.children.some((m) => m.hasClass("typing")) };
  }
  if (scenario === "ticks") {
    T.render(fixtures.plan);
    await tick("called"); await tick("referral");
    const before = ["called", "booked", "referral", "ptsmc"].map((i) => [i, !!checkbox(i)]);
    T.render(fixtures.plan2);  // re-render with a differently worded checklist
    out.ids2 = ids.result.find((n) => n.tag === "input") && all.filter((n) => n.tag === "input" && n.type === "checkbox" && !String(n.id).startsWith("stage-") && ids.result.find((x) => x === n)).map((n) => [n.id, n.checked]);
    out.state = T.state(); out.before = before;
  }
  if (scenario === "startover") {
    T.render(fixtures.plan); await tick("called");
    const sid = T.state().sessionId;
    await byText("Start over").fire("click");
    out.sidChanged = T.state().sessionId !== sid; out.after = T.state(); out.resultHidden = ids.result.hidden; out.formShown = !ids.roleCard.hidden;
  }
  if (scenario === "rerun_keeps_new_question_clears") {
    ids.go.disabled = false;
    await ids.go.fire("click"); await wait();               // first run: renders plan (fetch returns fixtures.next)
    await tick("called"); await tick("booked");
    await byText("I have my referral").fire("click"); await wait();  // same plan, re-run
    out.afterReferral = T.state().ticked;
    ids.go.disabled = false; ids.situation.value = "a new question";
    await ids.go.fire("click"); await wait();               // a brand-new question
    out.afterNew = T.state().ticked;
  }
  if (scenario === "busy") {
    T.render(fixtures.ask);
    const timing = ids.result.find((n) => n.hasClass("lock"));
    let release; pending = new Promise((r) => { release = r; }); fixtures.next = fixtures.plan;
    const running = timing.fire("click");
    await wait();
    out.during = { busy: T.state().busy, chipsDisabled: chips().every((c) => c.disabled), lockDisabled: all.filter((n) => n.hasClass("lock") && ids.result.find((x) => x === n)).every((n) => n.disabled), go: ids.go.disabled, goText: ids.go.textContent };
    const callsBefore = fetchCalls;
    await chips()[0].fire("click"); await ids.go.fire("click"); await timing.fire("click");  // double-submit attempts
    out.extraCalls = fetchCalls - callsBefore;
    release(fixtures.plan); await running; await wait();
    out.after = { busy: T.state().busy, chipsDisabled: chips().some((c) => c.disabled), go: ids.go.disabled, goText: ids.go.textContent };
  }
  if (scenario === "dates") {
    out.today = T.todayIso(new Date(2026, 9, 24, 23, 59)); out.early = T.todayIso(new Date(2026, 0, 5, 0, 1));
    out.past = T.isPastDate("2026-10-23", new Date(2026, 9, 24)); out.same = T.isPastDate("2026-10-24", new Date(2026, 9, 24)); out.future = T.isPastDate("2026-11-01", new Date(2026, 9, 24));
    T.render(fixtures.plan);
    await byText("Add to calendar").fire("click");
    const date = ids.result.find((n) => n.tag === "input" && n.type === "date");
    out.formMin = date.min; out.expectedMin = T.todayIso(new Date()); out.required = date.required;
  }
  console.log(JSON.stringify(out));
})();
"""


def node_run(scenario: str, fixtures: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        driver, data = Path(tmp, "driver.js"), Path(tmp, "fixtures.json")
        driver.write_text(DRIVER)
        data.write_text(json.dumps(fixtures))
        done = subprocess.run([NODE, str(driver), str(ROOT / "frontend" / "index.html"), str(data), scenario], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def fixtures(monkeypatch) -> dict:
    full = {**PLAN_REPLY, "checklist": [{"label": "Called Yale Health"}, {"label": "PCP visit booked"}, {"label": "PT referral received"}, {"label": "PTSMC booked"}]}
    plan = pt_plan(monkeypatch, model={"plan": full})
    plan2 = json.loads(json.dumps(plan))
    plan2["plan"]["checklist"] = [{"id": "called", "label": "Called PTSMC"}, {"id": "referral", "label": "Referral confirmed"}, {"id": "ptsmc", "label": "Visit booked"}]
    monkeypatch.setattr(agents, "run_agent", fake_model(router=router_reply(symptom_present=True, symptom_area="headache", intent="care_visit", timing="unknown")))
    ask = shape(navigator.navigate("student", "I have a headache"))
    chat = {"kind": "answer", "items": [plan["coverage"]["items"][0]]}
    return {"plan": plan, "plan2": plan2, "plan2plan": plan, "ask": ask, "next": plan, "chat": chat}


needs_node = pytest.mark.skipif(not NODE, reason="Node is not installed")


# 1. Checklist state --------------------------------------------------------------------------------

def test_checklist_ids_mean_something_and_stay_the_same_when_the_plan_is_rebuilt(monkeypatch):
    first = pt_plan(monkeypatch)["plan"]["checklist"]
    second = pt_plan(monkeypatch, has_referral=True, model={"router": {**PT_ROUTER, "line_id": "ptsmc", "has_referral": True}})["plan"]["checklist"]
    assert [c["id"] for c in first] == ["called"]  # the fake plan's single "Called" item
    assert agents.checklist_ids(["Called Yale Health", "PCP visit booked", "PT referral received", "PTSMC booked"]) == [
        {"id": "called", "label": "Called Yale Health"}, {"id": "booked", "label": "PCP visit booked"},
        {"id": "referral", "label": "PT referral received"}, {"id": "ptsmc", "label": "PTSMC booked"}]
    assert [c["id"] for c in agents.checklist_ids(["Referral confirmed with PTSMC", "Called PTSMC", "Visit booked"])] == ["referral", "called", "booked"]
    assert [c["id"] for c in agents.checklist_ids(["Do a thing", "Do another"])] == ["other1", "other2"]
    assert second and len({c["id"] for c in second}) == len(second)


@needs_node
def test_ticked_boxes_are_kept_when_the_plan_is_drawn_again(monkeypatch):
    out = node_run("ticks", fixtures(monkeypatch))
    assert sorted(out["state"]["ticked"]) == ["called", "referral"]
    assert dict(out["ids2"]) == {"called": True, "referral": True, "ptsmc": False}


@needs_node
def test_start_over_clears_ticks_and_makes_a_new_session_id(monkeypatch):
    out = node_run("startover", fixtures(monkeypatch))
    assert out["sidChanged"] and out["after"]["ticked"] == [] and out["resultHidden"] and out["formShown"]


@needs_node
def test_a_re_run_of_the_same_plan_keeps_ticks_but_a_new_question_clears_them(monkeypatch):
    out = node_run("rerun_keeps_new_question_clears", fixtures(monkeypatch))
    assert sorted(out["afterReferral"]) == ["booked", "called"] and out["afterNew"] == []


def test_the_session_id_is_regenerated_not_a_constant():
    assert "let sessionId = newSessionId()" in SCRIPT and "const sessionId" not in SCRIPT
    assert "sessionId = newSessionId()" in SCRIPT[SCRIPT.index("function startOverButton"):SCRIPT.index("function renderEmergency")]


# 2. The calendar date can't be in the past -------------------------------------------------------------

@needs_node
def test_the_calendar_date_has_a_minimum_of_today_and_past_dates_are_refused(monkeypatch):
    out = node_run("dates", fixtures(monkeypatch))
    assert out["today"] == "2026-10-24" and out["early"] == "2026-01-05"
    assert out["past"] is True and out["same"] is False and out["future"] is False
    assert out["formMin"] == out["expectedMin"] and re.fullmatch(r"\d{4}-\d{2}-\d{2}", out["formMin"]) and out["required"]
    assert "isPastDate(date.value" in SCRIPT


# 4. No double-submit -----------------------------------------------------------------------------------

@needs_node
def test_chips_and_answer_buttons_are_locked_while_a_run_is_in_flight(monkeypatch):
    out = node_run("busy", fixtures(monkeypatch))
    assert out["during"] == {"busy": True, "chipsDisabled": True, "lockDisabled": True, "go": True, "goText": "Thinking..."}
    assert out["extraCalls"] == 0  # clicking a chip, the main button or the answer button again sent nothing
    assert out["after"] == {"busy": False, "chipsDisabled": False, "go": False, "goText": "Find my next step"}


def test_the_routine_plan_and_referral_buttons_are_marked_to_lock():
    assert 'el("button", "ghost sm lock", "It can wait? Show the routine plan instead.")' in SCRIPT and "I have my referral" in SCRIPT and "primary sm noprint lock" in SCRIPT
    assert 'document.querySelectorAll(".chip, .lock")' in SCRIPT


# 5-9. Layout and look -----------------------------------------------------------------------------------

def block(css: str, header: str) -> str:
    start = css.index(header)
    depth, i = 0, css.index("{", start)
    for j in range(i, len(css)):
        depth += {"{": 1, "}": -1}.get(css[j], 0)
        if depth == 0:
            return css[i + 1:j]
    raise AssertionError(header)


def test_small_screen_css_stacks_the_hero_and_shrinks_the_big_numbers():
    phone = block(CSS, "@media (max-width: 560px)")
    assert re.search(r"\.herowrap\s*\{[^}]*flex-direction:\s*column", phone)  # the hero band stacks its dog and text
    assert re.search(r"\.bulldog\s*\{[^}]*--dog-scale:\s*\.\d+", phone)
    assert re.search(r"\.phone\s*\{[^}]*font-size:\s*2[0-6]px", phone) and re.search(r"\.emergency \.phone\s*\{[^}]*font-size:\s*3[0-2]px", phone)
    assert re.search(r"\.calform \.two\s*\{[^}]*grid-template-columns:\s*1fr\s*;", phone)
    assert re.search(r"\.steps\s*\{[^}]*flex-direction:\s*column", phone)
    desktop = CSS.replace(phone, "")
    assert int(re.search(r"\.phone \{[^}]*font-size: (\d+)px", desktop).group(1)) > 24  # the phone size is smaller than the desktop size


def test_the_bulldog_shrink_does_not_fight_the_thinking_animation():
    assert "scale(var(--dog-scale)) rotate(-5deg)" in CSS and "transform: scale(var(--dog-scale))" in CSS


def test_chips_show_the_same_focus_outline_as_the_role_options():
    role = re.search(r"\.role input:focus-visible \+ span \{ ([^}]*)\}", CSS).group(1).strip()
    chip = re.search(r"\.chip:focus-visible[^{]*\{ ([^}]*)\}", CSS).group(1).strip()
    assert role == chip == "outline: 3px solid var(--yale-mid); outline-offset: 2px;"


def test_every_collapsed_section_prints_and_no_print_rule_is_dead():
    for title in ("If things do not go as planned", "Email or MyChart drafts"):
        assert f'collapsible("{title}"' in SCRIPT and '"printable")' in SCRIPT
    assert re.search(r'collapsible\("How it decided", \[[^;]*\], "printable appendix"\)', SCRIPT)  # the printed plan is the whole plan
    printing = block(CSS, "@media print")
    assert "data-noprint" not in printing
    for cls in set(re.findall(r"\.([A-Za-z][\w-]*)", printing)):
        assert cls in HTML.replace(printing, "") or cls in ("card", "cols"), f"print rule for .{cls} matches nothing"
    for sel in set(re.findall(r"#([A-Za-z]\w*)", printing)):
        if not re.fullmatch(r"[0-9A-Fa-f]{3,6}", sel):  # skip colours such as #999
            assert f'id="{sel}"' in HTML, sel


def test_cards_have_a_soft_shadow_and_role_boxes_and_chips_have_a_hover_border():
    assert re.search(r"\.card \{[^}]*box-shadow: var\(--lift\)", CSS) and "--lift: 0 1px 2px rgba(0, 53, 107" in CSS
    assert re.search(r"\.role:hover span \{ border-color: var\(--yale-mid\)", CSS)
    assert re.search(r"\.chip:hover \{[^}]*border-color: var\(--yale-mid\)", CSS)
    assert "box-shadow: none" in block(CSS, "@media print")


def test_the_look_is_still_yale_blue_and_white_with_no_new_colors():
    allowed = {"#002349", "#00356B", "#17283F", "#1C6B3F", "#286DC0", "#5A6B82", "#7A5300", "#B3261E", "#D3DEEC", "#E6F4EC", "#E8C86A",
               "#EAF1F9", "#F4EFE6", "#FDECEA", "#FFF4D6", "#FFFFFF",
               "#FBF8F2", "#9A6535", "#5B3B1F", "#2A1A0E"}  # the last four are the English bulldog only: white, brown, brown line, dark eye
    used = {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}\b", CSS)}
    assert used <= allowed, used - allowed
    for rgba in re.findall(r"rgba\(([^)]*)\)", CSS):
        assert rgba.startswith(("0, 53, 107", "40, 109, 192", "255,255,255")), rgba  # Yale blue, the lighter Yale blue, and white: nothing new


def test_the_safety_demo_tables_scroll_sideways_on_a_phone():
    tables = re.findall(r"<table>", DEMO)
    wrapped = re.findall(r'<div class="scroll"><table>', DEMO)
    assert len(tables) == len(wrapped) == 3
    assert re.search(r"\.scroll \{[^}]*overflow-x: auto", DEMO) and re.search(r"table \{[^}]*min-width: 560px", DEMO)


def test_no_browser_storage_no_cookies_no_login_anywhere_on_either_page():
    for page in (HTML, DEMO):
        assert not re.search(r"localStorage|sessionStorage|indexedDB|document\.cookie|Set-Cookie|type=\"password\"", page)


def test_the_media_queries_come_last_so_they_beat_the_base_rules():
    """A phone rule placed before the rule it overrides is silently ignored, so the two media blocks must end the CSS."""
    def whole(header: str) -> str:
        start = CSS.index(header)
        return CSS[start:CSS.index("{", start) + 1 + len(block(CSS, header)) + 1]

    phone, printing = whole("@media (max-width: 560px)"), whole("@media print")
    tail = CSS[CSS.index("@media (max-width: 560px)"):]
    leftover = re.sub(r"/\*.*?\*/", "", tail.replace(phone, "").replace(printing, ""), flags=re.S).strip()
    assert leftover == "", f"a rule comes after the phone block and would beat it: {leftover[:80]}"
    assert CSS.index(phone) < CSS.index(printing)
    # and, as a plain check on the real bug this caught: no phone rule's selector is defined again later
    base = CSS[:CSS.index(phone)]
    for selector in re.findall(r"^\s{4}(\.[\w .-]+?)\s*\{", phone, re.M):
        assert re.search(re.escape(selector) + r"\s*\{", base), f"{selector} has no base rule to override"
