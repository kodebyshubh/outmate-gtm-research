# Demo Script (3 parts, about 1 minute each)

Repo: https://github.com/kodebyshubh/outmate-gtm-research

## Before recording
1. Backend running (uvicorn) and frontend running (npm run dev). Open the app in the browser.
2. Close other tabs, hide the bookmarks bar, zoom the browser to 110 percent.
3. Do not show .env or any key.
4. Open a second tab with the repo folder in your editor, folders expanded: backend/app/providers, backend/app/services.
5. Pre-pick the companies: Zoho (zoho.com, well covered) and one thin-coverage company (a small or new startup).
6. Tick "Fetch fresh data" for the first run so the result is live, not cached.

## Part 1: What it is and a live run (about 1 min)
Say:
"Hi, I'm Shubh. This is my prototype for Outmate's GTM research task. You enter a company, it researches the public web using Exa, and returns a report where every field says how much you can trust it."

Do:
1. Type Zoho and zoho.com. Objective: "Understand what they sell and who to target".
2. Click Run. While it loads say: "It runs several searches, then an LLM writes the fields, and then a verifier checks every claim."
3. When the report appears, scroll once top to bottom.
4. Point at the status badges: verified, provider-reported, inferred, unavailable.
5. Point at the cost and sources line.

## Part 2: Trust and honest gaps (about 1 min 15 s)
Say:
"Every field carries a status, sources, and a quote. Verified means the quote really appears in the cited source. Inferred is clearly labelled, like the GTM opportunity."

Do:
1. Open one field, show the source link and the quoted text.
2. Click the source link, show that the quote is on the page (quick, 5 seconds).
3. Back to the app, point at the GTM opportunity field marked inferred.
4. Run the thin-coverage company.
5. Show the unavailable fields and their reasons, plus the missing-fields panel and warnings banner.
6. If the "claim(s) rejected by the quote check" list appears, open it.

Say:
"When the web does not support a field, it says unavailable instead of guessing. Contacts and employee size are never inferred. And if the model's claim has a number that is not in the source, it is downgraded or dropped."

## Part 3: Under the hood, tests, limits (about 1 min)
Say:
"The backend is FastAPI with a provider adapter pattern, so Exa for research and other enrichment providers can be swapped in."

Do:
1. In the editor show backend/app/providers (exa, moltsets, mock, skipped) and backend/app/services (research, synthesis, verify).
2. Open verify.py for 5 seconds: "This is where the quote and number checks happen."
3. In a terminal run the tests (pytest -q) and show them passing.
4. Show docs/PRODUCT_EXPLORATION.md briefly, with the Orange Slice and Clay screenshots.

Say:
"I also tried Orange Slice and Clay hands-on. Neither showed a source or confidence per cell, which is the gap this design fills."
"Limits: enrichment is skipped by default because the MoltSets key was not available, though the adapter and tests are in the repo. Reports are in memory only, one company at a time. Next steps: batch table view, a company endpoint, more providers and saved reports."
"Thanks for watching."

## If something goes wrong
- Run fails or times out: say "this is the timeout path" and show the warning banner, then retry once.
- Cached result appears: tick "Fetch fresh data" and run again.
