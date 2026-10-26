# Yale Health Navigator

A web app where you describe your situation in plain words and it tells you which Yale Health line to call, gives you a plan for the call, and checks what your plan covers, quoting the rule behind every claim.

It is a care planner for the Yale community, not a chatbot over documents. One main purpose, getting a person to the right call, and every feature serves it: tap-to-call, a map with directions and an open-now badge, a checklist and write-down list, a referral checker and tracker, add-to-calendar, a printable call sheet, and email or MyChart drafts. Most people ask an AI, make a call, see a doctor, and stop. This app plans the steps and the follow-up, so the whole solution comes in one go.

**Where it could go next** (ideas, not built): dental, vision and other insurers; family and dependent views; more languages; and triage help only if Yale clinicians review it. The report and slides give the full roadmap.

## Who it is for

All Yale members: **students, staff or faculty, dependents, and visiting students**. The first thing the app needs is which of these you are, and it only uses the rules for that role plus the shared rules.

## Prerequisites

- **Python 3.10 or newer** (tested on 3.13)
- **Node.js 18 or newer is optional**, and only for the tests: about 50 tests run the page's own JavaScript in Node and are skipped if Node is not installed. The app itself needs no Node: the frontend is plain HTML files served by the backend.
- A Portkey API key (`PORTKEY_API_KEY`)

## How to run it

1. **Clone the repo** and open a terminal in its folder:

   ```bash
   git clone https://github.com/shirleyxu414-sys/yale-health-navigator.git
   cd yale-health-navigator
   ```
2. **Add your key.** Copy the example file, then paste your key after the `=`:

   ```bash
   cp .env.example .env
   ```

   Set `PORTKEY_API_KEY` in `.env`. The app finds `.env` in the repo folder, or in the folder one level above the repo. The repo folder is checked first.
3. **Install everything in `requirements.txt`:**

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

   On Windows use `.venv\Scripts\pip` and `.venv\Scripts\python`.
4. **Run the backend:**

   ```bash
   .venv/bin/python backend/main.py
   ```

   It listens on port **8000**.
5. **Open the app.** There is no separate frontend to start: the backend serves the page. Open **<http://127.0.0.1:8000>** in your browser. The Safety demo is at <http://127.0.0.1:8000/safety-demo>.

## What success looks like

**Try this:** pick **Yale student**, type `lower back pain for weeks, I want physical therapy`, and press **Find my next step**.

**Expect this:**
- **A line to call:** the Yale Health main line, (203) 432-0246, for a primary care visit and the physical therapy referral, with an open-now badge and a Get directions link. PTSMC appears under "Also useful".
- **Coverage:** a colored verdict (Covered with conditions), the answer, and the quote from the rules behind it. A link to the official Yale Health coverage page sits under it.
- **A plan:** a timeline (Today, On the call, This week, After the referral), the two or three "Do not forget to mention" points, a "Write down" list with real fields, and a checklist you can tick. When the plan involves a referral you also get the referral tracker and the "Your PCP" card.
- **Sections that open on tap:** "If things do not go as planned" and "Email or MyChart drafts" (copy-paste drafts, never sent). At the very end, "Take this plan with you" (Copy plan and Print plan, both giving the same short call sheet) and a collapsed "How it decided" panel that lists the rules behind the answer.
- **Add to calendar:** next to the booked steps, a form that downloads an `.ics` file made in your browser. Nothing is sent anywhere and the app never books for you.
- **Emergency check:** type `I have chest pain and I cannot breathe`. You get only the emergency message, nothing else.
- **A symptom with no timing, such as `I have a headache`:** a plan for today, with one line saying so and a button to see the routine plan instead.
- **Referral checker** (below the form): pick a department, press Check, and get "referral needed", "no referral needed" or "Ask Member Services", with a button to get a plan for that department.
- **Chat:** the floating "Chat with the helper" button opens a chat that answers insurance lookups only from the rule files, for example "Is dental covered?".
- **Safety demo:** the page at `/safety-demo` runs the defenses live: injection attempts refused, diagnosis requests refused, ungrounded claims replaced, and the budget guard stopping a run. It spends no tokens.

No login is needed, by design.

## Model

**`gpt-6-luna` only, through Portkey, for every agent.** It is called with the OpenAI Python client, and the name is set once in `backend/config.py`. A test fails if any other model name appears anywhere in the repo.

## Files

```
.
├── README.md
├── AI_prompts.md
├── report.html
├── slides.html
├── requirements.txt
├── .env.example
├── .gitignore
├── backend/
│   ├── main.py
│   ├── navigator.py
│   ├── agents.py
│   ├── chat.py
│   ├── referral.py
│   ├── sections.py
│   ├── glossary.py
│   ├── example.py
│   ├── safety.py
│   ├── grounding.py
│   ├── budget.py
│   ├── logs.py
│   ├── safety_demo.py
│   ├── rules.py
│   ├── models.py
│   ├── config.py
│   └── prompts/
│       ├── router.md
│       ├── coverage.md
│       ├── plan.md
│       ├── chat.md
│       └── never.md
├── frontend/
│   ├── index.html
│   └── safety_demo.html
├── data/
│   ├── rules_common.json
│   ├── rules_student.json
│   ├── rules_staff_faculty.json
│   ├── rules_dependent.json
│   └── rules_visiting_student.json
├── tests/
│   ├── conftest.py
│   ├── injection_test.py
│   ├── test_safety.py
│   ├── test_defenses.py
│   ├── test_flow.py
│   ├── test_chat.py
│   ├── test_referral.py
│   ├── test_calendar.py
│   ├── test_landing.py
│   ├── test_plan_page.py
│   ├── test_practical.py
│   ├── test_takeaway.py
│   ├── test_warmth.py
│   ├── test_writedown.py
│   └── test_site.py
└── output/
    └── .gitkeep
```

| Folder or file | What it holds |
| --- | --- |
| `backend/` | The agents and API logic |
| `backend/main.py` | The FastAPI app: serves the pages, the `/api/navigate`, `/api/chat`, `/api/referral`, `/api/departments`, `/api/example` and `/api/safety-demo` routes, and the logs |
| `backend/navigator.py` | Runs one plan request: screen, router, coverage checker, plan builder, and the parts of the answer built in code |
| `backend/agents.py` | The three plan agents (router, coverage checker, plan builder), the chat agent with its `lookup_rules` tool, the verifier, and the prompt loader; each model call is one `gpt-6-luna` call |
| `backend/chat.py` | One chat turn: screen, diagnosis check, role handling, then the chat agent; also the code-only answers (rule files, official coverage page) |
| `backend/referral.py` | The "Do I need a referral?" checker and the referral help, answered from the rule files with no model |
| `backend/sections.py` | Parts of the answer built in code from the rule files: write-down list, "if things do not go as planned", the warning list, the email and MyChart drafts, the "How it decided" panel, the coverage page link |
| `backend/glossary.py` | The plain-words explanations of terms such as referral and PCP, each one sentence taken from a rule |
| `backend/example.py` | The example plan, built with a canned model reply so it costs no tokens |
| `backend/safety.py` | Emergency and crisis detection, the prompt-injection and diagnosis-request checks, the no-diagnosis output check, and the phone-number scrubber |
| `backend/grounding.py` | The grounding check: a coverage claim is shown only if it, and every number in it, is in the cited rule |
| `backend/budget.py` | The token budget guard: a cap on input tokens per session and per network address; counters only, nothing stored |
| `backend/logs.py` | The guard log, the run log, the chat log and the audit trail writers |
| `backend/safety_demo.py` | The five injection attempts and the live checks behind the Safety demo page |
| `backend/rules.py` | Loads a role's rule file plus the common file, nothing else |
| `backend/models.py` | The response shapes (pydantic) that the backend returns and the page reads |
| `backend/config.py` | The model name, the budget caps, `.env` loading (repo folder, then the folder above) and the client |
| `backend/prompts/` | The runtime prompts: one file per agent (`router.md`, `coverage.md`, `plan.md`, `chat.md`) and the shared rules every agent must follow (`never.md`) |
| `frontend/` | `index.html` (the app) and `safety_demo.html` (the Safety demo page), plain HTML, CSS and JavaScript |
| `data/` | The rule files: one common file and one per role. They are the only source of Yale Health facts |
| `tests/` | The test suite (see Tests) |
| `output/` | Logs written when the app runs; it starts empty |
| `report.html`, `slides.html` | The report and the slides |
| `AI_prompts.md` | The prompts used to build the app |

## Data

The rule files ship in the repo, so **no separate data pack is needed.** They are the only source of Yale Health facts in the app. The `.env` file stays on your machine and is never committed.

- `data/rules_common.json`: facts for every role (address, phone lines, Acute Care hours, referrals and prior authorization, the PCP, the emergency and crisis rules, the red-flag lists, the department referral lists, dental, email and MyChart).
- `data/rules_student.json`, `rules_staff_faculty.json`, `rules_dependent.json`, `rules_visiting_student.json`: one file per role. A role only ever sees its own file plus the common file.
- Every rule has an id (for example `student.pt_coverage`), a statement, and a source that names the Yale Health document it came from. Where no Yale document says it, the rule says so instead of inventing a source.
- `rules_staff_faculty.json` starts with a `status` block listing which rules are verified and which are missing. Its amounts come only from the Yale Health Member Booklet 2026, with page numbers.
- Anything not in the files gets "I don't know" and Member Services at (203) 432-0246. Nothing is filled in from another role's file.

## Tests

From the repo folder:

```bash
.venv/bin/python -m pytest tests
```

- **495 tests.** Without a key, 491 run: key-loading order, only `gpt-6-luna` in the repo, no hard-coded keys, role isolation, rule-file contents, the emergency message alone, crisis to 988 and 911, no diagnosis, five prompt-injection attempts all refused, the grounding check, the budget guard, the Safety demo, the plan flow and response shape, the chat, the referral tools, Add to calendar, and the call sheet. About 50 of them run the page's own JavaScript in Node and are skipped if Node is not installed.
- **Key needed (4 tests):** real calls for a student asking about physical therapy, staff costs for every plan group, a visiting student who must not get student rules, and a student with no insurance. They are skipped when no `PORTKEY_API_KEY` is found.
- The prompt-injection tests alone: `.venv/bin/python -m pytest tests/injection_test.py -v`

## Included outputs

[`report.html`](report.html) and [`slides.html`](slides.html) are in the repo root. They are single files with the screenshots embedded: download either one and double-click it to open it in a browser, with no key and no server. They are also served as web pages by GitHub Pages: <https://shirleyxu414-sys.github.io/yale-health-navigator/report.html> and <https://shirleyxu414-sys.github.io/yale-health-navigator/slides.html>. (GitHub's own file view shows only the HTML source.) `slides.html` loads reveal.js from a public CDN, so it needs an internet connection; arrow keys move between slides and `F` goes full screen.

## Prompts

- `backend/prompts/` holds the runtime prompts: `router.md`, `coverage.md`, `plan.md` and `chat.md`, one per agent, plus `never.md`, the rules every agent must follow (no diagnosis, nothing outside the rule files, no invented numbers).
- `AI_prompts.md` logs the prompts used to build the app.

## Links

- Repo (public): <https://github.com/shirleyxu414-sys/yale-health-navigator>
- Report: open it at <https://shirleyxu414-sys.github.io/yale-health-navigator/report.html> (file in this repo: [report.html](report.html))
- Slides: open them at <https://shirleyxu414-sys.github.io/yale-health-navigator/slides.html> (file in this repo: [slides.html](slides.html))
- App: not online. Run it locally with the steps above.

## Safety and limits

- **Emergencies:** chest pain, trouble breathing, severe bleeding, signs of stroke or any red-flag sign get only "Call 911 or go to the emergency room now." with the nearest ERs. No plan, no coverage.
- **No diagnosis:** the app never names a condition and never recommends treatment or medication; "What do I have?" and "Is this serious?" are refused in code before the model.
- **Prompt injection:** whatever you type is treated as data; "ignore your rules" and fake system instructions are refused in code, and model answers are checked again on the way out.
- **Cited and grounded coverage:** every coverage answer quotes its rule; a claim, or a number, that is not in the rule is replaced with "I don't know, ask Yale Health."
- **Budget guard:** `SESSION_TOKEN_CAP` is 200,000 input tokens per session and `ADDRESS_TOKEN_CAP` is 1,000,000 per network address, set in `backend/config.py`; a run that would go over stops and says so. A plan uses about 7,700 input tokens.
- **No stored health data:** no login, no cookies, no localStorage; what you type lives in the page and is gone when you refresh. The server writes only local log files that are never committed.
- **Unverified falls back:** anything not in your role's file plus the common file is answered with "I don't know" and Member Services at (203) 432-0246.
- **Not medical or coverage advice:** the app is educational guidance, not a coverage decision; confirm details with Member Services.

## Grounding design

A model is never trusted to state a Yale Health fact. It may only choose and quote from the rule files, and code checks that it did.

1. **Only the right rules are visible.** A role loads its own rule file plus the common file. The chat's lookup tool searches only those, and returns at most four rules.
2. **The model must quote.** For each coverage claim it cites a rule id and copies one sentence from that rule word for word.
3. **Code verifies.** The claim must appear in the cited rule, every number in the answer must appear in it too, there must be no diagnosis or treatment language, and any phone number not in the rule files is removed. A claim that fails is replaced with "I don't know, ask Yale Health." and logged.

Example trace (a real chat turn, student role, "Is dental covered?", from `output/audit_trail.json`):

```
screen            passed
diagnosis_check   passed
route             a question: answered by the bot
lookup_tool       1 lookup; rules seen: common.dental, common.referral_other,
                  student.hospitalization_specialty, student.pt_requires_hospitalization_specialty
verifier          1 passed citation, grounding, number and no-diagnosis checks; 0 did not
outcome           answer, rule cited: common.dental         tokens used: 1,967

claim (quoted):   "Yale Health does not offer dental insurance for adults."
rule source:      Yale OISS Dental & Vision Care page; Yale Health Student Guide 2025-2026,
                  Pediatric Dental Care section; gradprofdenteye.yale.edu
```

## Keys and outputs

Never commit a real `.env` or API key. `.env.example` lists `PORTKEY_API_KEY` only.

`output/` starts empty (it holds only a `.gitkeep`). After runs, these four logs appear there, and none of them is committed:

- `run_log.jsonl`: one line per plan request (time, role, kind, line chosen, model, calls, seconds), with no text from the person.
- `guard_log.jsonl`: one line per defense that fired.
- `chat_log.json`: each chat turn (question, answer, rule cited, tokens). Set `CHAT_LOG_QUESTIONS = False` in `backend/config.py` to drop the question text.
- `audit_trail.json`: the steps, rules and token use behind each plan, chat turn and referral check.
