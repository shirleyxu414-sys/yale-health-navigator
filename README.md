# Yale Health Navigator

A web app where you describe your situation in plain words and it tells you which Yale Health line to call, gives you a plan for the call, and checks what your plan covers.

## Who it is for

All Yale members: **students, staff or faculty, dependents, and visiting students**. The first question the app asks is which of these you are, and it only uses the rules for that role.

## Prerequisites

- **Python 3.10 or newer** (tested on 3.13)
- **Node is not needed.** The frontend is one plain HTML file served by the backend.
- A Portkey API key (`PORTKEY_API_KEY`)

## How to run it

1. **Clone the repo** and open a terminal in its folder.
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
5. **Run the frontend:** there is nothing separate to start. The backend serves the page, so open **<http://127.0.0.1:8000>** in your browser. The JSON API is at `http://127.0.0.1:8000/api/navigate`.

## What success looks like

**Try this:** pick **Yale student**, type `lower back pain for weeks, I want physical therapy`, and press **Find my next step**.

**Expect this:**
- **A line to call:** the Yale Health main line, (203) 432-0246, for a primary care visit and the physical therapy referral. PTSMC appears under "Also useful".
- **A timeline:** Today (call), On the call, This week (PCP visit), After the referral (book PTSMC).
- **Do not forget to mention:** two or three points you would not know to bring up, such as asking for the PT referral and asking whether PTSMC offers dry needling, each with one line on why. Never a script.
- **Write down** (date and time of the appointment, referral details, name of the person you spoke to) and a **checklist** you can tick off.
- **A coverage check:** is it covered, the condition that applies, what is excluded, and the rule cited for each claim.
- **If things do not go as planned**, a **Print plan** button, a **How it decided** panel (role, rule files used, category, line chosen), clickable **common questions**, and a **Prefer writing?** section with copy-paste drafts. A headache asks one question first: "Do you need care today, or can it wait for a regular appointment?"
- **Add to calendar:** next to the PCP visit and PTSMC booking steps, a form with the title, location and notes filled in. You add the date and time after you call, and it downloads an `.ics` file for Google Calendar, Apple Calendar or Outlook. It is made in your browser; nothing is sent anywhere, no login, and the app never books for you.
- **Emergency check:** type `I have chest pain and I cannot breathe`. You get only the emergency message, nothing else.
- **A chat panel:** *placeholder, not built yet. Fill this in when the chat panel exists.*
- **Safety demo:** open <http://127.0.0.1:8000/safety-demo> to watch the defenses run live: 5 prompt-injection attempts refused, diagnosis requests refused, ungrounded coverage claims replaced, and the token budget stopping a run.

No login is needed, by design.

## Model

**`gpt-6-luna` only, through Portkey, for every agent.** It is called with the OpenAI Python client, and the name is set once in `backend/config.py`.

## Files

```
.
├── README.md
├── AI_prompts.md
├── requirements.txt
├── .env.example
├── .gitignore
├── backend/
│   ├── main.py
│   ├── navigator.py
│   ├── agents.py
│   ├── sections.py
│   ├── safety.py
│   ├── grounding.py
│   ├── budget.py
│   ├── logs.py
│   ├── safety_demo.py
│   ├── rules.py
│   ├── models.py
│   └── config.py
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
│   ├── test_safety.py
│   ├── test_flow.py
│   ├── test_defenses.py
│   ├── test_calendar.py
│   └── injection_test.py
├── output/
│   └── .gitkeep
└── joke.txt
```

| Folder or file | What it holds |
| --- | --- |
| `backend/` | The agents and API logic |
| `backend/main.py` | The FastAPI app: serves the page, the `/api/navigate` route, and the metadata-only run log |
| `backend/navigator.py` | Runs one request: emergency check, router, the one timing question, coverage checker, then plan builder |
| `backend/agents.py` | The three agents (router, coverage checker, plan builder) and their prompts, each one `gpt-6-luna` call, plus the checks on what they return |
| `backend/sections.py` | Parts of the answer built in code from the rule files: write-down list, "if things do not go as planned", the red-flag list, the email and MyChart drafts, the "How it decided" panel |
| `backend/models.py` | The one response shape (`Answer`) that the backend returns and the page reads; fields that do not apply are left out |
| `backend/safety.py` | Emergency and crisis detection, the prompt-injection and diagnosis-request checks, the no-diagnosis output check, and the phone-number scrubber |
| `backend/grounding.py` | The grounding check: a coverage claim is shown only if it, and every number in it, is in the rule files |
| `backend/budget.py` | The token budget guard: a cap on input tokens per session (20,000) and per network address; counters only, nothing stored |
| `backend/logs.py` | The guard log (`output/guard_log.jsonl`): one line per defense that fired, with no text from the person |
| `backend/safety_demo.py` | The five injection attempts and the live checks behind the Safety demo page |
| `backend/rules.py` | Loads a role's rule file plus the common file, nothing else |
| `backend/config.py` | The model name, `.env` loading (repo folder, then the folder above), and the client |
| `frontend/` | `index.html` (the app, with the Yale blue styling and the bulldog helper) and `safety_demo.html` (the Safety demo page) |
| `data/` | The rule files: one common file and one per role (the only source of Yale Health facts) |
| `tests/` | `test_safety.py` (safety and rule-file checks), `test_flow.py` (the router, coverage and plan flow, the response shape, and the page contract), `test_defenses.py` (no-diagnosis, grounding, budget and the Safety demo), `injection_test.py` (five injection attempts, all refused) and `test_calendar.py` (Add to calendar and the `.ics` file) |
| `output/` | Logs written when the app runs |
| `joke.txt` | A leftover test file from setting up this folder |

## Data

The rule files ship in the repo, so **no separate data pack is needed.** They are the only source of Yale Health facts in the app. The `.env` file stays on your machine and is never committed.

- `data/rules_common.json`: facts for every role (address, phone numbers, Acute Care hours, referrals, the emergency rule, the crisis rule for 988 and 911, the red-flag lists, email and MyChart).
- `data/rules_student.json`, `rules_staff_faculty.json`, `rules_dependent.json`, `rules_visiting_student.json`: one file per role. A role only ever sees its own file plus the common file.
- Every rule has an id (for example `student.pt_coverage`) and a source. Every coverage answer shows the ids it came from.
- `rules_staff_faculty.json` starts with a `status` block listing which rules are verified and which are missing. Its cost amounts come only from the Yale Health Member Booklet 2026, with page numbers. One rule (the Aetna choice after three years) is from Yale's benefits page, not the booklet. It applies to Clerical & Technical, Service & Maintenance, and Security staff only, and every answer that uses it says so.
- Anything not in the files gets the answer "I don't know this" and Member Services at (203) 432-0246. Nothing is filled in from another role's file.

## Tests

From the repo folder:

```bash
.venv/bin/python -m pytest tests
```

- **No key needed (187 checks):** key-loading order, only `gpt-6-luna` in the code and README, no hard-coded keys, the emergency message appears alone, crisis goes to 988 and 911, role isolation, rule-file contents, no diagnosis (including refusing "what do I have?" and "is this serious?" in code before the model), five prompt-injection attempts all refused, the grounding check (claims and numbers must be in the rule files, every failure logged), the token budget guard, the Safety demo, the router, coverage and plan flow, one response shape that the page matches, the email and MyChart drafts, Add to calendar, and no health text stored. Four of these build a real `.ics` file with Node and are skipped if Node is not installed.
- **Key needed (4 checks, skipped when no `PORTKEY_API_KEY` is found):** real calls for a student asking about physical therapy, staff costs for every plan group, a visiting student who must not get student rules, and a student with no insurance.
- The prompt-injection script alone: `.venv/bin/python -m pytest tests/injection_test.py -v`

## Included outputs

*Placeholder: `report.html` and `slides.html` will open directly in a browser with no key and no server. Fill this in when those files exist.*

## Prompts

*Placeholder: `backend/prompts/` will hold the runtime prompts. Fill this in when that folder exists. For now the three agent prompts are inside `backend/agents.py`.*

`AI_prompts.md` logs the prompts used to build the app.

## Links

- Report: *placeholder, `report.html` does not exist yet*
- Slides: *placeholder, `slides.html` does not exist yet*
- App: *not online. Run it locally with the steps above.*

## Safety and limits

- **Emergencies:** chest pain, trouble breathing, severe bleeding, signs of stroke or any red-flag sign get only "Call 911 or go to the emergency room now." with the nearest ERs. No plan, no checklist, no coverage, no questions.
- **No diagnosis:** the app never names a condition and never recommends treatment or medication. "What do I have?" and "is this serious?" are refused in code before the model, with "I can't diagnose, that's for a clinician. Here's who to call:" and a recommendation.
- **Prompt injection:** whatever you type is treated as data. "Ignore your rules", "you are now a doctor" and fake system instructions are refused in code, and the model's answers are checked again on the way out.
- **Cited and grounded coverage:** every coverage answer names its rule and quotes it. A claim that is not in the rule files, or a number that is not, is replaced with "I don't know, ask Yale Health." and logged.
- **Budget guard:** each session may use up to 20,000 input tokens (about three full plans). A run that would go over stops and tells you. A real plan uses about 6,000.
- **No stored health data:** nothing you type is saved. The logs hold only the time, role, chosen line, model, duration, and which defense fired.
- **Unverified falls back:** anything not in your role's file (plus the common file) is answered with "I don't know" and Member Services at (203) 432-0246.

## Keys and outputs

Never commit a real `.env` or API key. `.env.example` lists `PORTKEY_API_KEY` only.

`output/` starts empty. After runs, `run_log.jsonl` (one line per request) and `guard_log.jsonl` (one line per defense that fired) appear there today. *Placeholder: `token_log.json`, `chat_log.json` and `audit_trail.json` will appear after runs once those logs are built.*
