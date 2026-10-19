# Outmate Company Research Engine

A small web app and API. Enter a company name or website and get a structured GTM research report. Every field carries its sources and a status: verified, provider-reported, inferred or unavailable. Missing information is shown as missing, never guessed.

Built as the Outmate "AI-Powered GTM Research & Enrichment Prototype" assignment.

## How it works

```
User input
  -> FastAPI POST /api/research
  -> Exa adapter (5 targeted searches, highlights, URLs, dates)   [runs in parallel with]
  -> Enrichment adapter slot (MoltSets, skipped by default)
  -> Evidence pool
  -> Groq synthesis (strict JSON, must cite evidence and quote it)
  -> Verifier (quote must exist in the cited source, else the claim is dropped)
  -> Merge provider data (labelled provider-reported, conflicts flagged)
  -> Structured report -> Next.js report page
```

Status meanings:
- verified: stated in a cited public source, and the supporting quote was found in that source
- provider-reported: returned by MoltSets, not independently checked
- inferred: reasoned from cited evidence (always shown with its evidence)
- unavailable: no source or provider supplied it

Employee size, decision-makers and contact information are never inferred. They appear only when a source states them or MoltSets returns them.

## Project layout

```
backend/    FastAPI app (app/), providers (exa, moltsets, mock), services (research, synthesis, verify, normalize), tests
frontend/   Next.js report UI (talks only to the backend)
docs/       API notes, product exploration
.env        local secrets (gitignored); .env.example shows the shape
```

## Setup

Prerequisites: Python 3.10+, Node 18+.

1. Copy `.env.example` to `.env` (a placeholder `.env` may already exist locally) and add your keys:
   - EXA_API_KEY (required)
   - GROQ_API_KEY (required)
   - MOLTSETS_API_KEY (optional; enrichment is skipped by default)

2. Backend:

```
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

3. Frontend (second terminal):

```
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

## Tests

```
cd backend
pytest
```

Tests use mocked HTTP only. No live API calls and no keys needed.

## API

POST /api/research

```json
{ "company_name": "Example Co", "website": "https://example.com", "objective": "Evaluate fit for a B2B GTM service" }
```

Returns the report: one object per field (value, status, sources, note), plus source_urls, providers, warnings, evidence and generated_at. GET /api/health reports which providers are configured, never the keys.

## Error handling

- Exa: 12 second timeout, 2 retries with backoff on 429 and 5xx, no retry on 401 or 403, empty results reported as a warning.
- MoltSets: required User-Agent, one retry honouring Retry-After on 429, 402 (trial used up) and 403 mapped to clear warnings, "not_found" (HTTP 200) treated as empty.
- Groq: one repair retry on invalid JSON, then the report falls back to evidence only.
- Any provider failure produces warnings, not a failed request.

## Example

Input:

```json
{ "company_name": "Example Co", "website": "https://example.com", "objective": "Evaluate fit for a B2B GTM service" }
```

Output shape (illustrative, values are placeholders, not real data):

```json
{
  "company_description": {
    "value": "Short description",
    "status": "verified",
    "sources": [{ "url": "https://example.com/about", "title": "About", "published_date": "2026-05-01", "quote": "exact sentence from the page" }]
  },
  "employee_size": { "value": null, "status": "unavailable", "sources": [], "note": "no source or provider returned it" },
  "potential_gtm_opportunity": { "value": "Reasoned hypothesis", "status": "inferred", "sources": [] },
  "providers": [{ "name": "exa", "state": "ok" }, { "name": "mock-enrichment", "state": "mock" }],
  "warnings": ["Enrichment is mock sample data and is not used in the report fields."]
}
```

Real outputs from live runs are saved by `python scripts/smoke_live.py <domain>` into docs/sample_output/.

## Live check (run on your machine)

```
cd backend
python scripts/smoke_live.py                # checks Exa and Groq, saves a real Exa fixture
python scripts/smoke_live.py example.com    # also runs the full workflow and saves the report
```

## MoltSets status

Outmate told us to skip MoltSets for this assignment, so enrichment is off by default (ENRICHMENT_PROVIDER=none) and the report says enrichment was skipped. The MoltSets adapter (People Search, Bearer auth, required User-Agent, company_domain filter) is still in the code and tested against mocked responses, so it can be switched on with ENRICHMENT_PROVIDER=moltsets and a key. ENRICHMENT_PROVIDER=mock shows clearly labelled sample data, never merged into report fields. See docs/API_NOTES.md.

## Known limitations

- Quality depends on what Exa finds. Thin-coverage companies will show many unavailable fields, which is intended.
- Name-only input can pick the wrong company. The resolved domain is shown with a warning; prefer giving the website.
- Highlights are short snippets, so verification only covers what the snippet contains.
- The quote check is an exact (normalized) substring match. A correct claim with a paraphrased quote is dropped rather than risked.
- Employee size and decision-makers appear only when a public source states them (and the quote checks out). Contact details are always unavailable while enrichment is skipped.
- Enrichment is skipped (per Outmate). The MoltSets People Search adapter exists but was never run against the live API.
- Single company per request, in-memory 15 minute cache, no database, no authentication.
- Free tiers: Exa credits and Groq rate limits can interrupt heavy testing.

## Next steps

- Add the MoltSets company endpoint when its docs are available, and compare coverage against Exa side by side.
- Batch mode with a spreadsheet-style table and per-row status.
- More providers behind the same adapter interface (Tavily, Parallel and others).
- Persist reports with timestamps and a refresh policy.
- Natural-language prospecting on top of the research engine.
- Stream partial results to the UI as each provider answers.
