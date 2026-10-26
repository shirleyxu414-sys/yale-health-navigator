# AI Prompts Log

One section per problem. Each section has the problem number/title, the prompts I sent, and any follow-up prompt I needed.

## Step 1: Follow my past pattern first

First, read my standing instructions and my last homework layout:
1. Read /Users/danxu/Desktop/AI Foundations/AGENTS.md and follow it.
2. Copy the folder layout from /Users/danxu/Desktop/AI Foundations/hw 5/: backend/, frontend/, data/, tests/, output/, README.md, requirements.txt, AI_prompts.md.
3. Log every prompt I give you in AI_prompts.md in this project folder, the way hw 5 does.
4. One thing is different this time, so ignore the creature rule in AGENTS.md. I still want a creature, but make it Yale Healthcare style: a friendly Yale bulldog helper in Yale blue (#00356B) and white, clean and clinical, the look of a real healthcare service. No black-and-pink, no 8-D style. Use the same clean Yale blue styling for the report and slides. can you just keep the content it self?

## Step 2: Build Yale Health Navigator

Work one problem at a time: finish each prompt fully before starting the next. Do not build everything at once.
Model override for this project: ignore the model name in AGENTS.md. The course requires gpt-6-luna only

Build me a web app called Yale Health Navigator. Someone types their situation in plain words, like "lower back pain for weeks, I want physical therapy". The app answers with:
1. Which Yale Health line to call
2. An action plan with the key points to mention on the call and what to ask for
3. What is covered under the Yale student health plan

A few hard rules, do not break any of them:
1. AI calls use the OpenAI package/client with PORTKEY_API_KEY loaded from environment variables. Model: gpt-6-luna ONLY, through Portkey, for every agent. This is a course rule and points are deducted if any other model shows up in code or runs. Ignore the model name in my AGENTS.md for this project. Write gpt-6-luna in the README so there is no confusion later.
2. Never hard-code, print, commit, or expose API keys. Ship a .env.example that lists PORTKEY_API_KEY only.
3. Look for a .env file in two places: first in the repo's own folder, then in the folder above the repo. The teaching staff run it with their .env one level up, and my AGENTS.md keeps the key in the root .env. Test this by moving your own .env up one level.
4. The teaching staff will clone this repo and follow the README. If the app is not running after 10 minutes of following the README, that section scores 0, so keep setup simple: clone, add .env, install, run. Nothing fancy. List every dependency in requirements.txt.
5. Layout: backend/ for the agents and API logic, frontend/ for the HTML UI, data/ for the rules file, tests/ for the safety tests, output/ for logs. README.md explains what the app is and how to run it step by step.
6. Do not store any health data anywhere. Everything is session-only.
7. Scope: this app is built for all Yale members, not just students. The first thing it asks is: "Are you a Yale student, staff or faculty, a dependent, or a visiting student?" The router picks the rule file for that role, and the coverage checker reads only that file plus the common file. Anything not verified in the role file falls back to Member Services at (203) 432-0246. Never answer one role's question from another role's rules.

## Step 3: Update the README

Update the README to these sections, in this order:

1. Project name and one sentence saying what the app does.
2. Who it is for: all Yale members (student, staff or faculty, dependent, visiting student).
3. Prerequisites: Python version, and Node version only if the frontend uses it.
4. How to run it, as numbered steps a stranger can follow: clone the repo, copy .env.example to .env and add PORTKEY_API_KEY (the .env works in the repo folder or one folder above it), install everything in requirements.txt, run the backend, run the frontend. State the ports and URLs.
5. What success looks like: try this (student plus lower back pain wanting physical therapy) and expect this (plan, coverage check, chat panel). No login needed, by design.
6. Model: gpt-6-luna only, through Portkey, for every agent.
7. File tree of the whole repo, plus a folder map with one line per folder and per agent file (what each file holds).
8. Data note: the rule files ship in the repo, no separate data pack is needed. The .env file is local only and is never committed.
9. Tests: how to run tests/, and which checks need the key and which do not.
10. Included outputs: report.html and slides.html open directly in a browser with no key and no server.
11. Prompts: backend/prompts/ holds the runtime prompts, and AI_prompts.md logs every prompt used to build the app.
12. Links: report.html, slides.html, and the app link if online.
13. Safety and limits, one line each: no diagnosis, no stored health data, coverage answers cite the rule files, anything unverified falls back to Member Services at (203) 432-0246.
14. A note that a real .env or API key must never be committed, and .env.example lists PORTKEY_API_KEY only. Output/ starts empty; token_log.json, chat_log.json, and audit_trail.json appear after runs.

For report.html, slides.html, and backend/prompts/, which do not exist yet, leave a placeholder line and fill it in when those files exist.

## Step 4: Rule files

Use the data/ folder and the file format you already set up in the scaffold. Create one rule file per role. These files are the only source of truth for Yale Health facts in this app. No agent is allowed to state a Yale Health fact that is not in the role file for that person plus the common file, and every coverage claim in an answer has to name the rule it came from.

1. The common file, facts shared by all roles:
   1. Yale Health Center, 55 Lock Street. Member Services: (203) 432-0246. Acute Care: (203) 432-0123.
   2. All care happens at the Yale Health Center unless a PCP refers you out, and prior authorization is required for all referrals. No limits for pre-existing conditions.
   3. Acute Care is open Sun to Sat, 8am to 10pm, for urgent same-day needs.
   4. Emergency rule: chest pain, trouble breathing, severe bleeding, signs of stroke, or any life-threatening symptom, the answer is ONLY: "Call 911 or go to the emergency room now." Nearest ER: Yale New Haven Hospital Main Campus, 20 York St, New Haven (also Saint Raphael Campus, 1450 Chapel St). When possible, call Acute Care at (203) 432-0123 before going to the ED. After emergency care, call the Referrals Department at (203) 432-7397 within 48 hours. Carry your Yale Health ID card at all times. When in doubt, call 911. In an emergency the app shows ONLY this message: no plan, no checklist, no coverage talk, no further questions.
   5. Safety-net rule: for any symptom, the app never diagnoses, never names a condition, and never recommends treatment or medication. It routes to care and shows a short "Get emergency help right away if" list of red-flag signs for that symptom area, ending with Call 911. Headache example: sudden worst headache of your life; weakness, numbness, trouble speaking, confusion, or vision changes; fever with stiff neck; headache after a head injury; seizure or loss of consciousness. If someone reports any red-flag sign, the emergency rule above applies.
   6. Written channels: Member Services email member.services@yale.edu (Mon-Fri 8:30am-5pm) for coverage and administrative questions. MyChart messaging is for non-urgent care team messages, replies in about two business days. Neither is for appointments, time-sensitive issues, or emergencies. For those, call.
2. The student file, student coverage:
   1. Yale Health main line / PCP appointments: (203) 432-0246. Call here for a primary care visit and for referrals.
   2. PTSMC (Physical Therapy and Sports Medicine Center), Yale Health Center, 55 Lock Street: (203) 436-5583.
   3. Physical therapy is covered 100% under the Yale student health plan with a referral from a PCP. Without a referral, do not promise coverage.
   4. Dry needling is available through PTSMC and is covered under a PT referral.
   5. Acupuncture is excluded under the Yale student health plan (exception only as a substitute for anesthesia). Never suggest acupuncture as a covered option.
   6. Bring a student ID to appointments.
   7. International students: degree-seeking international students get the same student coverage above. Two wrinkles: J-1/J-2 holders have federal minimums, and the Yale Health Plan does not cover medical evacuation and repatriation. Visiting international students may be on CISI coverage instead. If someone is not sure which coverage they have, the app tells them to call Member Services at (203) 432-0246. It does not guess.
   8. No coverage: if a student says they have no insurance, the app still routes to care by urgency first. Emergencies go to 911 no matter what. Then it explains: Yale requires coverage, so an enrolled student generally has Basic Coverage for primary care at the Yale Health Center. If they waived Yale's hospitalization/specialty plan, their alternate plan governs outside care. If they are on leave, withdrawn, abroad, or recently graduated, coverage may have changed. In every case, the app sends them to Member Services at (203) 432-0246 to confirm enrollment. It never guesses about their plan and never promises free care.
3. The employee file, staff and faculty coverage, sourced ONLY from the Employee Member Coverage Booklet and the Yale Health coverage page, each rule with its source named:
   1. Care at the Yale Health Center unless referred out, prior authorization required, no pre-existing condition limits.
   2. After three years of service, employees can stay in Yale Health or switch to Yale's Aetna plans (Aetna Smart Care high-deductible plan with a Health Savings Account, or Aetna Select).
   3. Any cost-sharing goes in ONLY if the booklet states it, with the amount and the source cited.
   4. The file must say at the top which rules are verified and which are missing. Anything missing falls back to Member Services at (203) 432-0246. Do not fill gaps from the student file.
4. Dependents and visiting students: dependents enroll through the member's plan by the enrollment deadline and can get hospitalization/specialty coverage through Yale Health. Visiting international students may be on CISI coverage instead of Yale Health. Anything beyond that goes to Member Services.

If someone asks about something not in this file, the app has to say it does not know and tell them to ask Yale Health directly. Never guess.

Confirmed:
1. Keep the Aetna rule flagged, with its exact source (Yale benefits page) and scope (Clerical and Technical, Service and Maintenance, and Security staff only). Never present it as general employee coverage.
2. Emergency answer is the headline plus the ER addresses, Acute Care, Referrals, and ID card lines, and nothing else. Not headline alone.
3. For the PT waiver rule, show me the exact source line. If Yale's page does not say it plainly, change it to not_verified and send people to Member Services.
4. Add the crisis rule to the common file: 988 plus 911, labeled as a national service, not Yale Health.
5. Write the general red-flag list into the common file too.

Add one dental rule to the common rule file, so the app can answer "Is dental covered?" instead of falling back. The rule must come only from Yale's own pages, and must not bake in prices that change yearly.
1. The rule's statement, in plain words: Yale Health does not offer dental insurance for adults. Dental care is a separate optional plan: graduate and professional school students and PhD students can buy a Delta Dental plan (enrollment once a year, online), and faculty and staff can buy a dental plan with partial coverage. Pediatric dental care is covered through Delta Dental of Connecticut for students and enrolled dependents through the end of the month they reach age 20, and they are automatically enrolled. A dental emergency can be addressed at any hospital emergency room. For anything beyond that, including which plan fits a given role, ask Member Services at (203) 432-0246.
2. Sources, stated on the rule: the OISS Dental and Vision Care page, the Yale Health Student Guide pediatric dental section, and the graduate dental and eye programs page (gradprofdenteye.yale.edu). Do not copy premium amounts or copay percentages into the rule: they change yearly, so the rule points to the plan page instead.
3. Do not add a dental chip to the "Common questions" row: the row is capped at nine chips. The rule alone lets the bot and the plan pipeline answer dental questions typed or asked in chat.

Do not change anything else in this change.

## Step 5: Plan page and response shape

Keep the three agents you already built (router, coverage checker, plan builder). Do not rebuild them. Now finish the frontend so it shows a full plan, not just next steps, and make the frontend and backend agree on one response shape. Right now the frontend expects fields the backend does not send (kind, safety_net, emergency block), so unify the shape first, then prove it end to end with a real run: student plus lower back pain wanting physical therapy, and one emergency input.

1. Router: first, confirm role. Ask "Are you a Yale student, staff or faculty, a dependent, or a visiting student?" if not already known. Pick the rule file for that role. Then classify the situation as (a) routine PCP visit, (b) urgent care, or (c) emergency. Emergency (red-flag symptoms from the common file) short-circuits the whole pipeline: output only the emergency message, nothing else. For a symptom with no red flags (for example a headache), do not diagnose and do not recommend treatment or medication. Ask the one administrative question (need care today, or can it wait for a regular appointment?), route to Acute Care for same-day need or PCP for routine, and show the safety-net red-flag list for that symptom area. Output: the role, the rule file used, the category, and the phone number to call.
2. Coverage checker: given the category and what the person wants (for example physical therapy), reads only the role file and the common file and answers: is it covered, what condition applies (for example needs a PCP referral), and what is excluded. It has to cite the rule for every claim. If the answer is not in the role file or the common file, it says so and gives Member Services at (203) 432-0246.
3. Plan builder: given the router output and the coverage check output, builds the action plan. It never writes a verbatim script. People know how to talk. It gives only what they would not know:
   1. "Do not forget to mention": the 2 to 3 points I would not know to bring up (for example: ask for the PT referral, because PT is covered 100% only with one; ask whether PTSMC offers dry needling, because it is covered under a referral but only if you ask). One line each on why it matters.
   2. "Write down": date and time of the appointment, referral details, and the name of the person spoken to.
   3. Timeline and checklist (see Frontend below).
   Keep the whole plan short enough to read off a phone screen while calling.

Frontend: show a full plan, not just next steps:
1. Timeline: today (call), on the call, this week (PCP visit), after the referral (PTSMC booking).
2. "Do not forget to mention": the points I would not know to bring up, with one line each on why it matters. Never a verbatim script, never "say this".
3. "Write down": date and time of the appointment, referral details, and the name of the person spoken to.
4. A checklist I can tick off: called, booked, referral received, PTSMC booked.
5. Coverage check with the rule cited for each claim.
6. "If things do not go as planned": line busy or closed, no appointments soon, and what to do after the PCP visit (come back and say you have the referral, and the plan updates).
7. A Print plan button.
8. "How it decided" panel: role, rule file used, category, and line chosen.
9. Common questions: a row of clickable chips ("Is PT covered?", "Is acupuncture covered?", "I have a headache", "I don't have insurance", "What if it's after hours?", "I already have a referral"). A chip fills the input and runs the same pipeline. Chips are shortcuts, not a separate FAQ database.
10. Prefer writing? section: an email draft to Member Services (member.services@yale.edu) for coverage and administrative questions only, and a MyChart message draft for non-urgent care team messages. Drafts are copy-paste text only. The app never sends email itself. Never offer a draft for appointments, symptoms, or urgent issues. Show the warning: email and MyChart are not for urgent care, call instead; MyChart replies take about two business days; Member Services hours Mon-Fri 8:30am-5pm.

Do not build the follow-up chat yet. That is a separate step later.

The plan page is too long, too flat, and hard to follow. Restructure it without changing the Yale blue and white clinical look:

1. Make the "Call this line" card the hero: visibly larger and stronger than every other card, so the answer hits first.
2. Give the coverage verdict a color-coded pill (Covered, Covered with conditions, Not covered) that signals the answer at a glance.
3. Collapse these sections by default: "If things do not go as planned", "Prefer writing?", and "How it decided". They open on tap. The first screen should be the call line, the coverage verdict, and the checklist.
4. Stop repeating the coverage fact. Show it once as the verdict sentence, once as the exact quote from the rules, and once as the rule id. Delete the third repetition.
5. Make the plan builder question-aware. A coverage-only question gets no timeline and no referral reminder unless a rule says a referral matters. Never use generic filler, and never use wording like "describe what you are experiencing" for a coverage question.

Remove the rule metadata lines from the coverage card.

1. Delete the "Rule student.pt_coverage (student file). Source: ..." lines from the coverage card. Real people do not need rule ids, and "Project owner's rule" reads as if the app made the rule up.
2. Keep the verdict sentence and one "From the rules:" quote on the card. That is the answer plus one plain-language evidence line. Delete the separate "Condition:" restatement, since the verdict already states the condition.
3. Move the rule id, rule file, and source into the "How it decided" panel (collapsed by default) and keep them in the audit log, so graders still see full traceability.
4. Check the source field for every rule in the rule files: it must name the actual Yale Health document the rule came from (coverage page, booklet, department listing), never "Project owner's rule". Fix any rule whose source is a placeholder like that.

Remove the rule metadata line from the emergency safety-net section. The "Rule: common.safety_net" line at the bottom of "Get emergency help right away if" must go.

1. No "Rule:" line on any section shown on screen, including emergency and safety-net sections. In an emergency, people must see only the red-flag list and "Call 911", with no internal metadata competing for attention.
2. Rule ids, rule files, and sources live only in the "How it decided" panel (collapsed by default) and the audit log, as already decided for the coverage card. The verifier still checks citations internally.
3. Do not change any other wording in the emergency section. Do not remove or move any other element.

"How it decided" is grader evidence, not plan content, so it should not sit inside the plan's reading flow between the drafts and "Take this plan with you". Move it to the very end.
1. Move the "How it decided" panel to the very end of the plan output, after the disclaimer, so the plan's reading flow ends at "Take this plan with you" and the trace sits below as an appendix.
2. Keep the title, the content, and the collapsed-by-default behavior unchanged. It still shows the current plan's trace, and it is hidden when no plan exists.
3. Print and Copy are unchanged by this move: the trace stays out of both.

The bottom of the plan looks broken: the "How it decided" appendix is a full white card that the floating chat button overlaps, and it reads as an orphan section after the disclaimer. Make the bottom a quiet footnote zone.
1. Render the "How it decided" appendix as a quiet footnote-style row (muted text, no card shadow, smaller than a plan card), not a full white card, so it reads as an appendix rather than another plan section.
2. Make sure the page bottom clears the floating chat button, so the appendix and its expand control are never covered when scrolled to the bottom; increase bottom padding if needed.
3. Do not change the appendix title, content, or collapsed-by-default behavior, and do not change the disclaimer text.

Do not change anything else in this change.

## Step 6: Safety defenses and budget

Keep the tests you already have. Add these four defenses, all enforced in code, not just in prompts. For each one, first check whether an existing test already covers it, and add only what is missing:

1. NO-DIAGNOSIS GUARDRAIL: if someone asks "what do I have?" or "is this serious?", the app refuses to diagnose and replies: "I can't diagnose, that's for a clinician. Here's who to call..." plus the router's recommendation. Put this check in code before the model call, as a keyword and intent rule, so it holds even if the model is confused.
2. PROMPT-INJECTION DEFENSE: treat everything I paste as data, never as instructions. If someone writes "ignore your rules", "you are now a doctor", or pastes fake system instructions, the app has to ignore them and keep the guardrails. Add a test script (tests/injection_test) that feeds 5 injection attempts and checks all 5 are refused.
3. GROUNDING CHECK: before showing any coverage claim, check the claim string appears in the role file or the common file. If not, replace it with "I don't know, ask Yale Health." Log every grounding failure.
4. BUDGET GUARD: cap tokens per session (for example 20,000 input tokens). If a run would go over it, stop and tell the person. This stops a bug or a bad actor from burning the budget.

Then build a "Safety demo" page in the app that runs the injection test live and shows the refusals, so I can screenshot it for the report.

Also delete the stray tests/test_safety.py-E file, it is not a real test file. Then run the full test suite and report the result.

Raise the budget caps so a grader can never hit the wall in a demo, and skip the budget warning (at these caps it would never fire for a grader, so do not build it).
1. In backend/config.py, raise SESSION_TOKEN_CAP from 20,000 to 200,000 and ADDRESS_TOKEN_CAP from 100,000 to 1,000,000. Both numbers matter: refreshing starts a new session and dodges the session cap, but the address cap persists across refreshes, so raising only the session cap would leave the address wall in place.
2. Do not remove the guard itself, the notices, or the safety demo budget test: the guard code stays, the demo uses its own tiny test cap and is unaffected, and the report keeps its budget-guard safety claim. The new caps are a backstop against runaway use, not a target any demo reaches: 200,000 tokens is about 100 chat questions or dozens of plans in one session.

Do not change anything else in this change.

## Step 7: Add to calendar and website fixes

Add one more feature to the plan: "Add to calendar". Next to each booked step (PCP visit, PTSMC booking), add a button that lets me save it to my own calendar:

1. The button opens a small form with the details already filled in from the plan: title (for example "Yale Health PCP visit, back pain PT referral"), location (Yale Health Center, 55 Lock St), and notes (the line to call and the referral details). I fill in the date and time myself, since I only know them after I call.
2. Saving downloads an .ics file I can open in Google Calendar, Apple Calendar, or Outlook. Do not connect to any calendar account, do not ask me to log in, do not send anything to a server. Everything happens in the browser.
3. The app never books appointments itself. I book by phone; this button only saves what I already booked.

Fix these website issues, then run the full test suite and report the result:

1. Checklist state: when the plan re-renders (for example after clicking "I have my referral"), keep the boxes I already ticked. Store the ticked checklist ids in memory and reapply them after every re-render.
2. Calendar form: the date input must not allow a past date. Set its minimum to today.
3. Start over: generate a fresh session id when I start over, so a new plan does not share the previous plan's session. Change the session id from a const to something that can be regenerated.
4. Double-submit: disable the timing-question buttons and the chips while a run is in flight, the same way the main button already disables itself. Re-enable them when the run finishes.
5. Phone layout: add small-screen CSS (max-width around 560px). Stack the hero vertically and shrink the bulldog, shrink the big phone number, and stack the calendar date, time, and length fields into one column. I read this plan on a phone while calling, so test it narrow.
6. Chips: give chips the same visible keyboard focus outline the role options already have.
7. Print: decide whether the How it decided panel prints. Either add the noprint marker to it or remove the print rule that never matches. Do not leave a dead rule.
8. Visual depth: add a soft shadow to cards and a hover border to role options and chips. Keep the Yale blue and white clinical look, no new colors.
9. Safety demo page: the tables squeeze on a narrow phone. Wrap them so they scroll horizontally instead of squashing.

Do not break the rules: no stored health data anywhere (no localStorage, no cookies), no login, no diagnosis language, no phone number that is not in the rule files.

## Step 8: Landing page and bulldog helper

Make the landing page warmer without changing the clinical Yale blue and white look:

1. The bulldog looks grumpy. Soften its brows to near-horizontal and give it a friendly smile, so it reads as a helper, not an annoyed face.
2. The role boxes are uneven because "Dependent of a Yale member" wraps. Shorten it to "Dependent" with a small sub-line "of a Yale member", so all four boxes are the same height.
3. The Find button looks dead when disabled. Add a small hint next to it: "Pick a role and tell me what's going on."
4. Add a "See an example plan" link that loads the back-pain physical therapy example straight into a full plan, with no typing and no model wait. This is the fastest way for someone to see what the app gives them.
5. Add a 3-step strip under the hero: Tell me in plain words, I route you to the right line, You get a plan with coverage.
6. Add the soft card shadows and hover borders from the earlier fix list.

Apply this whole round of amendments together. Keep the Yale blue and white clinical look. Do not change any answers, phone numbers, or rule citations, only presentation, except where an item says otherwise.

LANDING
1. The bulldog still looks grumpy. Soften its brows to near-horizontal and give it a friendly smile, so it reads as a helper.
2. How-it-works strip: remove the numbers completely. The strip's 1, 2, 3 collide with the form's 1, 2, so one numbering system per page. Use arrows or small icons between the three boxes instead. Make all three boxes the same height with vertically centered text.
3. Role cards: make all four boxes the same height with vertically centered text, so no box is taller because its label wraps. Shorten "Yale staff or faculty" to "Staff or faculty" (the question above already says Yale). Keep "Dependent" with its small sub-line "of a Yale member". No label wraps at normal widths.

PLAN PAGE
4. Make the "Call this line" card the hero: visibly larger and stronger than every other card, so the answer hits first.
5. Give the coverage verdict a color-coded pill (Covered, Covered with conditions, Not covered) that signals the answer at a glance.
6. Collapse these sections by default: "If things do not go as planned", "Prefer writing?", and "How it decided". They open on tap. The first screen should be the call line, the coverage verdict, and the checklist.
7. Stop repeating the coverage fact. Show it once as the verdict sentence, once as the exact quote from the rules, and once as the rule id. Delete the third repetition.
8. Make the plan builder question-aware. A coverage-only question gets no timeline and no referral reminder unless a rule says a referral matters. Never use generic filler, and never use wording like "describe what you are experiencing" for a coverage question.

CHAT
9. Replace the current "Ask a follow-up" panel with a real chatbot like the hw 4 Bulldog Bot: a chat window with a message thread, not a single input box. The chat window shows the conversation as a thread: my messages and bot replies as bubbles, with history kept for the whole session. The bot is an agent behind the API with a system prompt file and a rule-file lookup tool, like hw 4. It answers only from the role file and the common file, and every answer cites its rule. Every reply goes through the same pipeline: coverage checker reads only the role file and the common file, verifier checks citations, no diagnosis language, and numbers before anything is shown. If the answer is not in the role file or the common file, the bot says "I don't know from the rule files. Call Member Services at (203) 432-0246." It never guesses. The chat keeps the session only. Log every chat turn in output/chat_log.json with the question, the answer, the rule cited, and the tokens used, plus an audit trail in output/audit_trail.json. The session budget guard also covers chat turns. The plan's role and coverage context carry into the chat so I do not repeat myself.
10. The chat entry must be impossible to miss. Add a floating chat button fixed at the bottom-right of the screen, visible on the whole plan page no matter how far I scroll. It opens the chat window. Use a solid Yale blue button with a chat icon and the label "Chat with the helper", sized so it is easy to tap on a phone, and keep it clear of the footer text. Also restyle the inline "Chat with the helper" button next to "Print plan" as a solid Yale blue primary button, so it no longer looks identical to the outline Print plan button. Both buttons open the same chat window.

CALENDAR
11. The Add to calendar date and time must start empty, not prefilled with today and 12:30, since the label says "add it after you call". Keep the "Save .ics file" button disabled, or show a message, until I pick a date.
12. The line label in the calendar Notes must match the rule file: if the rule file calls (203) 432-0246 Member Services, the calendar note must say Member Services, not "main line".

Standing rules for this round: no stored health data, no localStorage or cookies, no login, no diagnosis language, no phone number that is not in the rule files.

Fix the landing page visual hierarchy. The page is flat: every card is the same white box on pale blue, the same navy text, the same borders, the same spacing, so nothing reads as important. Do not add new colors and do not break the clinical Yale blue and white look.

1. Make the hero a dark Yale blue band with white text instead of another white card, so the top of the page is an instant focal point.
2. Make "Find my next step" the dominant element on the page: a large solid Yale blue button, clearly stronger than every other button and link on the page.
3. Make the selected role unmistakable: solid Yale blue fill with white text, while unselected roles stay outline. The current selected state is too subtle.
4. Make section titles larger and bolder, and make secondary text smaller and muted (the "COMMON QUESTIONS" label, the "Nothing you type is saved" note). Important text is big and dark, secondary text is small and quiet.
5. Make "See an example plan" a visible secondary outline button instead of a plain underlined link, so it reads as an action, not body text.
6. Make the main textarea the visual focus of section 2: thicker border or a subtle blue-tinted background, clearly stronger than the outline chips around it. The chips stay as secondary outline pills.
7. Increase the space between major sections, so the hero, the strip, and the form read as distinct groups instead of one flat list.
8. Check the floating chat button is fully on screen at phone widths and does not cover the chips or the input.

Pull back the landing page styling. The dark hero band plus thick blue borders on everything overshot: instead of one focal point, the page now has many competing strong elements, and it reads as heavy and harsh rather than clean and clinical. Restore restraint. Emphasis comes from size, spacing, and one strong element, not from heavy borders everywhere.

1. Hero goes back to light: a white card on pale blue, not a dark slab. Keep the greeting large and keep "See an example plan" as an outline button.
2. Delete the hero description sentence entirely ("Tell me what is going on in your own words. I will point you to the right Yale Health line, help you plan the call, and check what your plan covers."). It is the third copy of the same promise: the header tagline already says it, and the strip below says it again. The hero keeps only the greeting and the example plan button.
3. Borders go back to light. Role cards return to light grey borders; only the selected card gets a solid Yale blue fill with white text. Strip boxes keep a soft shadow with no heavy border. The textarea keeps a medium border with a light tint, not a thick dark border.
4. The disabled "Find my next step" button stays visually quiet and muted. Emphasis belongs on the enabled button: large and solid Yale blue when it becomes clickable, not a big grey slab while it is dead.
5. Keep the wins from the last round: strip arrows with no numbers, equal-height role cards, "Staff or faculty" label, dominant textarea position, safety demo in the footer, spacing between sections.

Make the "Find my next step" button smaller and less blocky. Right now it is too big and looks like a slab.

1. Reduce it to a medium size: comfortable padding and a font size that matches the form text, not a hero-sized block. It should hug its label rather than stretch wide.
2. Soften or remove the heavy drop shadow so it sits flat on the card instead of floating like a slab.
3. Keep it solid Yale blue with white text when enabled, so it is still clearly the primary action, just proportionate. Keep the disabled state quiet and muted.

Redraw the bulldog helper so it actually looks like an English bulldog (Yale's Handsome Dan is an English bulldog), not a generic cartoon dog.

1. Give it the breed features: a wide wrinkled muzzle, visible jowls, forehead wrinkle lines, floppy ears, and a flat nose. The current round face with pointy dark ears and a smirk reads as a generic dog.
2. Color it like an English bulldog: mostly white face with a brown patch over one eye and ear, like Handsome Dan. Keep the Yale blue collar and cross badge so the app palette stays clinical; the dog itself is white and brown, the UI stays Yale blue and white.
3. Keep the friendly expression: near-horizontal brows and a real smile, not a smirk. The helper must look friendly, not grumpy.
4. Do not copy Yale's official Handsome Dan logo or artwork. Draw an original English bulldog illustration. Keep it as a clean flat illustration that fits the clinical style.
5. Use the same bulldog face in the hero, the chat header, and next to the call card when the plan is ready, so the helper is one consistent character everywhere.

Change the landing form section markers and headings.

1. Replace the numbered circles (1, 2) on the two form questions with icon badges: a person icon for the role question and a speech bubble icon for "What is going on?". Keep the circles the same size and Yale blue, just swap the numbers for icons. This removes the last numbers from the landing page, so nothing competes with the strip arrows.
2. Put each question on one line. Shorten the first question to "Who are you at Yale?" so it fits on one line at normal widths; the four role cards already list the options, so nothing is lost. Keep "What is going on?" as it is, since it already fits on one line. On narrow phone widths, allow the heading to wrap gracefully rather than shrinking the text to unreadable size.

Do not change anything else in this change.

## Step 9: Chatbot

After the plan, add a chat panel called "Ask a follow-up", built on the backend you already have. It answers only from the grounded source: the role file and the common file. It does not have to follow the hw 4 layout. Fit it into the current backend shape instead of copying hw 4.

1. Every follow-up goes through the same pipeline: coverage checker reads only the role file and the common file, verifier checks citations, no diagnosis language, and numbers before anything is shown.
2. If the answer is not in the role file or the common file, the chat says "I don't know from the rule files. Call Member Services at (203) 432-0246." It never guesses.
3. The chat keeps the session only. Nothing is stored past the session. Log every chat turn in output/chat_log.json with the question, the answer, the rule cited, and the tokens used.
4. The session budget guard also covers chat turns. A chat turn that would go over the cap stops with a message instead of calling the model.
5. Reuse the existing backend: the same rule loading, coverage checker, verifier, and safety guards. Add a chat endpoint and a chat system prompt file where the other prompts live. Add an audit trail in output/audit_trail.json.

Replace the current "Ask a follow-up" panel with a real chatbot like the hw 4 Bulldog Bot: a chat window with a message thread, not a single input box.

1. The chat window shows the conversation as a thread: my messages and bot replies as bubbles, with history kept for the whole session.
2. The bot is an agent behind the API with a system prompt file and a rule-file lookup tool, like hw 4. It answers only from the role file and the common file, and every answer cites its rule.
3. Every reply goes through the same pipeline: coverage checker reads only the role file and the common file, verifier checks citations, no diagnosis language, and numbers before anything is shown.
4. If the answer is not in the role file or the common file, the bot says "I don't know from the rule files. Call Member Services at (203) 432-0246." It never guesses.
5. The chat keeps the session only. Nothing is stored past the session. Log every chat turn in output/chat_log.json with the question, the answer, the rule cited, and the tokens used, plus an audit trail in output/audit_trail.json.
6. The session budget guard also covers chat turns. A chat turn that would go over the cap stops with a message instead of calling the model.
7. The chat is easy to find: a visible chat button or panel on the plan page that opens the chat window, and the plan's role and coverage context carry into the chat so I do not repeat myself.

Put the same chatbot on the home page too, not only the plan page.

1. The floating chat button fixed at the bottom-right is visible on the home page as well as the plan page, and opens the same chat window.
2. It is the same bot: same agent, same prompt file, same rule-file lookup tool, same pipeline (coverage checker plus verifier per turn), same grounding (role file plus common file only), same "I don't know from the rule files. Call Member Services at (203) 432-0246." fallback, same session-only rule, same logging to output/chat_log.json plus output/audit_trail.json, same budget guard.
3. The chat needs a role before it can answer coverage questions. If I have already picked a role on the home page, use it. If not, the bot's first message asks: "Are you a Yale student, staff or faculty, a dependent, or a visiting student?" and waits for the answer before answering coverage questions.
4. If a plan already exists in the session, the chat carries the plan context, so follow-ups refer to the plan. If no plan exists yet and I describe a situation instead of asking a question, run the same plan pipeline and show the plan.
5. The form and the chat are two doors to the same bot, not two different bots. No stored health data, no localStorage or cookies, no login, no diagnosis language, no phone number that is not in the rule files.

Fix the chat window. Right now it breaks at the role step: the bot asks for the role, I tap "Visiting student", and the bot replies "Please try a shorter question." instead of accepting the role.

1. Tapping a role chip must set the role directly, not go through the question pipeline. After a role chip is tapped, the bot confirms in one message, for example "Got it, I'll use the visiting student rules. What would you like to ask?", and never replies "Please try a shorter question." to a role answer.
2. Once a role is set, replace the role chips with example-question chips (for example "Is PT covered?", "Is acupuncture covered?", "What if it's after hours?"). Do not keep showing the role chips after the role is already chosen.
3. Fix the "Please try a shorter question." fallback. If there is a real length limit, state it in the message and give an example of a good question. If there is no real limit, remove the rejection. It must never fire for a role answer or a short message.
4. Shorten the input placeholder so it fits the input width, for example "Ask a question...". Nothing may be cut off.
5. Combine the opening greeting and the role question into one opening message, so the chat does not open with two bot bubbles back to back.
6. The chat header avatar must match the hero bulldog helper, not a generic smiley.

Standing rules: no stored health data, no localStorage or cookies, no login, no diagnosis language, no phone number that is not in the rule files.

The chat window says the same thing twice: the header title already names the helper ("Yale Health helper") and the header subtitle already says "Answers only from Yale Health's rules", then the opening bubble repeats both ("Hi, I'm the Yale Health helper... I'll answer only from Yale Health's rules"). Trim the opening bubble to what the header does not already say: "Hi! Ask me what is covered or what to do next. I can't diagnose." Keep the "I can't diagnose" line, since it appears nowhere else in the window. Do not change anything else in this change.

The chat's "I don't know" answer looks like a bug when it is actually a correct refusal, because I cannot see which role's rules were searched. Fix the messaging, not the lookup. Do not add any rule to any role file from another role's file: the staff and faculty file has no acupuncture rule, so "Is acupuncture covered?" as staff or faculty correctly falls back, and that refusal stays.
1. The unknown fallback names the role file searched. When the role is set, the fallback reads: "I don't know from the [role label] rules I have. Call Member Services at (203) 432-0246." Use the role label the app already shows (for example "staff and faculty rules", "Yale student rules"). When no role is set, keep the current line.
2. A question that is only about the rule files themselves (for example "rule files?", "what are rule files?") gets a short plain-words answer about the app, not the coverage fallback: the rule files are the Yale Health coverage documents the bot answers from, your role's file plus the common file, and the bot only answers what those files say and cannot diagnose. Any question that names a service, department, or coverage topic still goes through the normal pipeline even if it mentions rules.
3. Show the active role in the chat header once it is set, so I always know which file the answers come from (for example under the title: "Staff or faculty rules"). With no role set, the header stays as it is.

5. On the "Call this line" card, add a map pin icon next to the Yale Health Center address, and a compact map preview showing Yale Health Center at 55 Lock Street, New Haven (latitude 41.31624, longitude -72.928). Use an OpenStreetMap embed with a marker, no API key: https://www.openstreetmap.org/export/embed.html?bbox=-72.938%2C41.30824%2C-72.918%2C41.32424&layer=mapnik&marker=41.31624%2C-72.928. Size it as a compact strip, about 150 pixels tall and full card width, with rounded corners matching the card. Put the map preview at the bottom of the card, below the call instruction, so the call line and address stay exactly where they are. Tapping the map preview opens the same directions link as "Get directions". Keep the "Get directions" link. Do not change anything else in this change.

6. Rewrite the "Prefer writing?" section to be more direct, and rename it.

1. New heading: "Email or MyChart drafts".
2. New intro line, replacing the current sentence: "Only for coverage, admin, and non-urgent questions. For appointments, symptoms, or anything urgent, call the line above."
3. In the yellow warning box, delete the first bullet ("Email and MyChart are not for urgent care. If it is urgent or time-sensitive, call instead.") because the new intro line already says it. Keep the other two bullets unchanged: "MyChart replies take about two business days." and "Member Services hours: Monday-Friday, 8:30 a.m.-5:00 p.m."

The chatbot feels useless because its example questions (PT, acupuncture, after hours) duplicate the homepage chips, so the chat is a weaker version of the chips. Give it a distinct job: insurance lookups the chips do not cover.
1. Replace the chat's example questions with insurance questions answerable from the common file, so they work for every role: "Is dental covered?", "Do I need prior authorization?", and "Where is the official coverage page?" (the answer gives the coverage page URL from the rule file).
2. Remove the old example questions (PT, acupuncture, after hours) from the chat. The homepage chips keep answering those.
3. Do not change the chat's welcome message, role chips, lookup rules, or grounded-only behavior.

Do not change anything else in this change.

## Step 10: Plan page details and practical functions

Make every "Write down" dotted blank a real field I can type in on the website, not just on paper after printing.

1. Replace each dotted blank in "Write down" with a text input styled with a dotted underline, so it looks the same but accepts typing.
2. Keep what I type in memory for the session only, no localStorage, no cookies, nothing sent anywhere. Closing or refreshing the page clears it, like everything else typed on this site.
3. The typed values must survive plan re-renders. Store them outside the rendered plan HTML and reapply them after every re-render, so clicking a checklist item or a referral button never wipes what I typed.
4. When I print the plan, the typed values print on the dotted lines.

Demote the demo links and add practical functions to the plan page, using only data already in the rule files.

1. Move the "Safety demo" link out of the header into the footer. The demo page itself stays, because it is evidence for the report's safety section, but real people never need it in the header. Keep the "See an example plan" link as a small link in the hero.
2. Open-now status next to each call line, computed in the browser from the device clock and the hours in the rule files, for example "Open now until 10:00 p.m." or "Closed, opens Monday 8:30 a.m.". Only show a live status for lines whose hours are in the rule files. Never guess hours. Lines without hours in the rule files show their hours text with no live badge.
3. Tap-to-call phone numbers: every phone number on the plan is a tel: link, so I can tap to dial on mobile.
4. Copy plan button next to Print plan: copies the whole plan as plain text to the clipboard, so I can paste it into Notes or send it to family. Everything happens in the browser, nothing is sent anywhere.
5. Get directions link next to the Yale Health Center address, opening the address in my maps app.
6. Plain-words explanations for jargon terms used in the plan (referral, prior authorization, Basic Coverage, and similar): tapping a term shows a one-sentence plain explanation taken only from the rule files, with its citation. If a term is not explained in the rule files, show no explanation rather than inventing one.

Make the page feel less dry without changing the layout, the colors, or the clinical style. Add life, not a redesign.

1. Give the bulldog reactions at key moments. While the plan is generating, the bulldog shows a thinking state. When the plan is ready, the bulldog appears next to the call card with one short encouraging line, for example "Here's your plan. First step: call this number." Keep it to one line, warm and calm, never flippant.
2. Add small icons next to the plan section headers (phone for the call line, clipboard for write down, shield or check for coverage, calendar for take this plan with you), in Yale blue, so the cards are scannable and less text-heavy.
3. Add one short human subline under the call card, for example "You don't need to explain everything. Start with one sentence about what's going on." Keep every other header as it is. No new marketing copy anywhere else.
4. Do not change the layout, the color palette, the card order, or any wording of the answers, phone numbers, or rules. Do not remove or move any element. This is a warmth pass only, not a redesign.

People who want more than a plain-words coverage answer have nowhere to go except the collapsed trace sources. Add one official link where coverage is discussed.
1. Under the "What your plan covers" section on the plan, add one link: "See the official Yale Health coverage page". It opens in a new tab, using the coverage page URL from the rule files (common.care_at_center's url, currently https://yalehealth.yale.edu/coverage).
2. Do not add a "What's my insurance policy?" chip: a broad policy question run through the plan pipeline gives a vague answer. The link is the answer to the policy question, not a pipeline run.

Do not change anything else in this change.

## Step 11: Timing question

The timing question screen looks like a dead end: after tapping "Find my next step" for a symptom, the page shows only the question "Do you need care today, or can it wait for a regular appointment?" and two buttons, with no plan and no explanation, so it reads as if Find did nothing. Frame it.
1. Add a line above the question: "One quick question before your plan."
2. Add one plain-words line explaining why it is asked: "Timing decides which line you should call, so your plan appears right after you answer."
3. Keep the two buttons and their labels unchanged, and keep Start over.

The timing question framing did not fix the timing problem, it added words to an extra screen. Delete the extra screen entirely: tapping "Find my next step" must always lead to a plan, never to a second question screen. This replaces the framing lines: do not build them, and remove the ask_timing screen (backend branch and frontend renderAsk) altogether.
1. When a symptom's timing is unknown, default to today and build the plan immediately. Today is the safe default, the same logic the code already uses when it cannot tell how serious a situation is: routing a routine case to Acute Care is safer than delaying a case that needs care today.
2. State the assumption in one line directly under the "Call this line" card: "You didn't say when you need care, so this plan assumes today." Put a one-tap button on the same line: "It can wait? Show the routine plan instead." Tapping it re-runs the same situation with timing set to can_wait. The button appears only when timing was defaulted; a plan built with explicit timing shows no button.
3. Do not add a timing row to the form: the form stays at role plus situation. People who want routine timing say so in words ("it can wait", "next week"), which the router already reads.

The timing assumption row has a layout problem: the button sits inline inside the sentence paragraph, so it floats above the text baseline and wraps awkwardly. Stack the row: sentence on its own line, button below it, left-aligned with the sentence. No text changes, just the layout.

Keep the "If things do not go as planned" section as it is. It is the "what if it goes wrong" part of the plan, it starts collapsed so it costs nothing unless someone needs it, and it is concrete, not filler: Mental Health and Counseling hours, try again when open, Acute Care backup if it has to be today, Member Services backup if no appointments are soon. No change needed.

Do not change anything else in this change.

## Step 12: Referral tools and common questions

Do not add a list of recommended doctors. Yale Health does not work that way, and the app must not invent a roster. Add these related functions instead, all grounded in the rule files, with any unknown routed to Member Services.

1. First add the verified department lists to the common rule file, sourced from Yale Health's Referrals Department page. Departments that need a PCP referral before scheduling: Allergy, Dermatology, Diagnostic Imaging, Endoscopy, Infusion, Inpatient Care, Laboratory Services, Nutrition Counseling, Physical Therapy, Specialty Services. Departments that do not need a referral: Acute Care, Behavioral Health and Mental Health and Counseling, Immunization, Obstetrics and Gynecology, Ophthalmology and Optometry and Eye Care, Screening mammograms. Students additionally need no referral for Student Health, Obstetrics and Gynecology, Mental Health and Counseling, Acute Care, Eye Care, and Immunizations. Any other specialty department, and any care outside 55 Lock Street, needs a PCP referral plus prior authorization, unless it is urgent or emergency care.
2. "Do I need a referral?" checker: I pick a department or service, and the app answers referral needed or not, plus the next step, from the lists above, with its citation. If the department is not in the lists, the answer is "Ask Member Services at (203) 432-0246", never a guess.
3. "Your PCP" explainer card: what a PCP is (the clinician who knows you best and coordinates all your care, backed by a team of doctors, nurse practitioners, physician associates, nurses, medical assistants, and receptionists), that one is assigned automatically upon enrollment, that the welcome letter from the Member Liaison says who it is, and that changing it means calling Member Services at (203) 432-0246 to review available providers. Yale Health also keeps an up-to-date in-network providers, vendors, and locations list: the app never copies that list, it tells people to ask Member Services or the Referrals Department (203) 432-7397 for it.
4. Referral journey tracker: a stage checklist for a referral in progress (PCP visit done, referral requested, referral reviewed and authorized, appointment booked), with a date field per stage and an Add to calendar option per booked stage. The tracker states that a referral from a PCP does not guarantee authorization and that Yale Health notifies you of the status.
5. Never name an individual doctor, never reproduce a provider roster, and never present a department as a doctor recommendation. Departments and lines only.

Add three chips to the "Common questions" row, keeping the existing six unchanged: "Do I need a referral?", "Who is my PCP?", and "I need mental health support". The referral checker and the "Your PCP" card already exist in the app, so these chips are entry points into them, not new functions. Mental Health and Counseling needs no referral and sits under Basic Coverage for students, so that chip has a clean rule-file answer. Cap the row at nine chips total; do not add more after these three. Do not change anything else in this change.

Move the "Do I need a referral?" checker onto the homepage, before any plan, so referral status is checked first instead of buried inside a plan. Referral status decides the first step (PCP visit first versus booking directly), so it belongs before the situation form, not after the plan.
1. Add a compact checker section on the homepage between the role cards and the "What is going on?" question: one department input plus a Check button, reusing the same /api/referral endpoint and the same answer display (verdict pill, answer line, next step) as the plan-page checker.
2. The checker uses the role picked on the form, since department lists differ by role. If no role is picked yet, tapping Check shows a notice ("Pick your role in step 1 first, then check again.") instead of silently doing nothing.
3. The checker needs department suggestions without a plan: provide them (for example a small endpoint returning the picked role's department names, or the same lists the plan-page checker uses) so the input offers department names as I type. Free text still works when I type a department not in the suggestions.
4. Do not give the checker a numbered or icon badge: it is a tool, not a form step, so the form keeps its two icon badges only. Do not remove the checker from the plan page: it stays there too, for plans that include referral help.

After the "Do I need a referral?" checker answers, I am left with nowhere to go: the answer says what to do in words, but the app offers no next action. Add one.
1. When the verdict is "needed" or "not_needed", show a button under the answer: "Get a plan for {department}". Tapping it carries the department into the situation flow: fill "What is going on?" with the department and run the plan immediately, using the role already picked. Do not make me retype the department.
2. When the verdict is "unknown" (department not on the lists), show no plan button: the answer already sends me to Member Services, and a plan built on an unknown department would guess.
3. The button appears on both the homepage checker and the plan-page checker.

The homepage checker can look dead: with the department suggestions dropdown open, tapping Check sometimes does nothing (the tap only closes the dropdown) and the result stays hidden behind it. Make Check always work.
1. Tapping Check always submits, even when the suggestions dropdown is open: dismiss the dropdown as part of pressing Check, so the press is never swallowed by closing it.
2. While a check is running, show "Checking..." in the result area, so a slow check never reads as no response.
3. After the answer appears, scroll it into view so it is never hidden behind the dropdown.

The homepage "Do I need a referral?" checker currently sits between the role cards and the "What is going on?" form, where it interrupts the main flow (role, situation, Find). Move it below the form.
1. Move the homepage checker section to directly below the "What is going on?" form card, as its own section, so the order is: role cards, situation form, checker, then the plan area. The checker stays on the homepage and before any plan.
2. Keep everything about the checker the same: the input, the Check button, the answer display, the "Get a plan for {department}" button, and the "Pick your role in step 1 first" notice (which still scrolls up to the role cards when no role is picked).
3. Do not move the plan-page checker: it stays inside referral help in the plan.

The "Get a plan for {department}" button never produces a special plan: it produces the standard detailed plan for that department, the same plan typing the department into "What is going on?" and tapping Find would give. Its value is purely as a one-tap shortcut. That shortcut is worth it on the homepage, where no plan exists yet, but not on the plan page, where a plan already exists: re-running for the same department rebuilds a near-identical plan while clearing ticks, write-down values, tracker stages, and the last check. This narrows the plan button to the homepage checker only.
1. Show the "Get a plan for {department}" button only on the homepage checker. The plan-page checker shows the verdict, the answer, and the next step, but no plan button.

The department suggestions list is a native datalist, which filters by the text already typed: with a full department name in the box, it shows only that one (or nothing), so I cannot browse other departments without deleting the text first. Replace it with a dropdown that always opens the full list.
1. Replace the native datalist on both checkers (homepage and plan-page) with a custom suggestions dropdown: a dedicated arrow button opens the full department list even when text is already typed; typing in the input filters the list; tapping a department fills the input and closes the list.
2. Keep free text: typing a department not on the list still works, and Check on an unlisted department still gives the "Ask Member Services" answer.
3. Keep the placeholder, the input's aria-label, the Check button, and the answer display unchanged.

The "Your PCP" card's first paragraph duplicates the glossary tap: tapping "PCP" anywhere in the plan already shows "Your primary care provider (PCP) is the medical professional who knows you best and coordinates all of your care." Remove the duplication from the card.
1. Remove the first paragraph (the "what is a PCP" definition plus the clinical team sentence) from the "Your PCP" card. The card keeps the assigned, change, and provider directory paragraphs only.
2. Do not change the glossary, the card title, or when the card appears.

The referral sections appear on plans that do not involve a referral (for example a headache plan that only mentions "referral" in a coverage answer). The current trigger turns on all referral help when any coverage answer contains the word "referral", even "no referral needed". Narrow it.
1. The tracker appears only when I already have a referral or the plan itself tells me to get one (the plan's timeline, do-not-forget points, or checklist says to ask the PCP for a referral). A mere mention of the word "referral" in a coverage answer does not turn it on.
2. The Your PCP card appears only when the plan's own steps (timeline, do-not-forget points, or checklist) mention the PCP or I ask about the PCP. A mere mention of "referral" in a coverage answer does not turn it on.
3. The Write down "Referral details" field appears only when the plan involves a referral (the same condition as the tracker). Otherwise Write down shows only the date and time and the name of the person spoken to.
4. The homepage checker is unchanged and remains the one place to check a department.

Yes, remove the plan-page checker. The homepage checker is the one place to check a department. The tracker and the Your PCP card stay, under their separate conditions.

Do not change anything else in this change.

## Step 13: Print and Copy

Move Print and Copy out of the middle of the plan into one end-of-plan actions section. Right now they sit mid-plan next to "Chat with the helper" on a plan text line, where they compete with reading and are easy to miss.

1. Remove the "Copy plan" and "Print plan" buttons from the mid-plan row next to "Chat with the helper". Remove that mid-plan button row entirely: chat is already reachable from the floating button on every page, so it does not need a mid-plan button.
2. Add a single "Take this plan with you" section at the very end of the plan, after all plan content (after "If things do not go as planned" and "Prefer writing?"), and before the footer disclaimer and "Start over". It holds "Copy plan" and "Print plan" side by side.
3. "Copy plan" copies the whole plan as plain text to the clipboard. "Print plan" prints the whole plan. Printing must expand any collapsed sections, so the printed plan is complete, including the sections that are collapsed on screen, and it must include anything I typed into the "Write down" fields.
4. Keep "Add to calendar" where it is, next to booked checklist steps. Do not duplicate it in the end section.
5. Do not add a sticky bottom bar for these actions: it would cover content on phones and collide with the floating chat button.

Print plan and Copy plan currently carry literally everything. Trim both to the same key info only: the call sheet a person takes to the phone, not the whole app.
1. Both Print and Copy contain exactly this, in this order: title plus "For: {role}"; "Call this line" (line name, number or email, hours, address if any); Why (one line); plan summary (one line); "What your plan covers" as verdict plus answer only, with no rule quotes, no source lines, and no line that repeats the answer; Timeline; "Do not forget to mention"; "Write down" with typed values (blanks as ______); Checklist with ticks; Referral tracker stages with ticks and dates when referral help is present; red flags when present; "If things do not go as planned"; disclaimer.
2. Cut from both: the "How it decided" trace (rule files, rule IDs, sources); rule quotes; the Your PCP card; glossary explanations; the email and MyChart drafts (they stay on screen in "Prefer writing?"); the referral checker answer; also-useful lines; chat, form, hero, and buttons (already hidden in print).
3. The on-screen plan does not change: only the Print and Copy outputs are trimmed.
4. Print and Copy must contain the same key info: a person who prints and a person who copies get the same sheet.

Do not change anything else in this change.

## Step 14: Final dry run, GitHub repo, report and slides

Now do the final dry run, in this order:
1. Final README update and check. The README must have all sections in order: project name and one sentence; who it is for; prerequisites with versions; numbered run steps with ports and URLs; what success looks like; gpt-6-luna only through Portkey; file tree plus a folder map with one line per folder and per agent file; data note; tests and which need the key; report.html and slides.html open with no key and no server; prompts locations; links; safety and limits, one line each; never commit a real key, and output/ starts empty. Add a grounding-design subsection with one example trace. Record the budget caps (SESSION_TOKEN_CAP 200,000, ADDRESS_TOKEN_CAP 1,000,000). Fill in the report.html and slides.html placeholders with the real files and links. If either file does not exist yet, stop and tell me, do not invent a link. The file tree must match the actual repo, including token_log.json and any new files.
2. Full test run. Run the whole tests/ suite and report the result per file. If anything fails, fix it and rerun until the suite passes, and report what changed.
3. Fresh clone test. Clone the repo to a fresh folder and follow only the README, with no extra knowledge from this project. The app must be running within 10 minutes of following the README. Report the time it took and any step that was unclear or missing. If the repo is not pushed to GitHub yet, stop at this step and tell me.
4. .env one level up test. Move the .env file to the folder above the repo and confirm the app still finds the key. Then put it back.
5. Model and key grep. Search the whole repo, including code, comments, README, and prompts, for any model name other than gpt-6-luna. The result must be zero. Confirm no real .env or API key is committed, and .env.example lists PORTKEY_API_KEY only.
6. Repo visibility. Confirm the GitHub repo is public. If you cannot verify that from here, say so.

Do not change any answers, phone numbers, rule citations, or app behavior, except to fix a failing test or a README inaccuracy you find. Do not change anything else in this change.

Good stop, do not invent those links. Proceed like this:
1. Do steps 2, 4, and 5 now: run the whole tests/ suite and report the result per file; move .env to the folder above the repo, confirm the app still finds the key, then put it back; search the whole repo, including code, comments, README, and prompts, for any model name other than gpt-6-luna and confirm no real .env or API key is committed. Steps 3 and 6 stay blocked until the repo is on GitHub, do not attempt them.
2. Initialize a git repo in the project folder and commit the current state. Do not push anywhere yet, there is no remote.
Do not update the README yet, that waits for the final dry run after report.html and slides.html exist. Leave output/ alone for now. Do not change any answers, phone numbers, rule citations, or app behavior, except to fix a failing test.

List only the four logs the app writes. Do not build a token log.

Use the repo name you suggested, and don't include the joke file in the repo.

Just go.

1) HTML of report - put your github repo url in the report so we can clone it

2) HTML of slides - put your github repo url in the report so we can clone it

3) A video of you testing your app (optional)

4) Nothing else - any other files you include will annoy me and be penalized

If your github repo is not in your report and slide files, we cannot clone it and grade it, so do not forget.

Also, if your repo is private, please mention this in your report and slides.

This is the submission requirement. See what we should do next.

This is the project requirement: https://zlisto.github.io/mgt_409_fa26/project_requirements.html

I don't see the links to the report and the slides in the repo. Why can't a link in the repo take a grader straight to the report and the slides? If turning on GitHub Pages helps the grading, do it.

The slides look terrible. They don't look like a presentation.

Check everything and run the tests if necessary, and make sure everything follows the project instructions and the submission rules I posted.

The title slide looks bad and ugly, and I can't see the link either. Can you also polish the report?

Yes, it's my name. I don't think we need a video. The price is fine. How can we solve the missing real-person evidence and the leftover test logs? Let's clean up the leftover test logs first.

I will follow your advice as long as it fully complies with the project requirements. I will run the test on my own, and I will test it at home later.

Now re-test everything. Also try to fine tune the report and the slides. Please fine tune the slides in terms of content, design, and layout. I want more insights and more elaboration in the presentation, especially on the problem and what is new, and also on the impact and what is next. We need to say something insightful, not just tedious stuff.

Check the project instructions from the website I sent you and the submission rules I gave you. Do a final check of the content of the report and the slides. Run one last test of the app. Let me know if it is OK to go.
