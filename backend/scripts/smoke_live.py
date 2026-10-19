"""Live smoke test. Run this on YOUR machine, where your keys and network access exist.

Usage (from the backend folder, with the venv active):
    python scripts/smoke_live.py                 checks Exa and Groq with one small call each
    python scripts/smoke_live.py example.com     also runs the full pipeline for a domain

What it does:
  1. Calls Exa once and saves the raw response to tests/fixtures/exa_live_sample.json
  2. Calls Groq once with the configured model and checks JSON mode works
  3. Optionally runs the whole workflow and saves docs/sample_output/<domain>.json
Keys are never printed.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.main import build_providers  # noqa: E402
from app.providers.exa import EXA_SEARCH_URL  # noqa: E402
from app.schemas import ResearchRequest  # noqa: E402
from app.services.research import run_research  # noqa: E402
from app.services.synthesis import GROQ_URL  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def ok(msg): print(f"[ok]   {msg}")
def bad(msg): print(f"[FAIL] {msg}")


async def check_exa(s):
    if not s.exa_configured:
        return bad("EXA_API_KEY is still a placeholder")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(EXA_SEARCH_URL, headers={"x-api-key": s.exa_api_key}, json={"query": "Stripe company overview", "type": "auto", "numResults": 2, "contents": {"highlights": True}})
    if r.status_code != 200:
        return bad(f"Exa returned HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / "exa_live_sample.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    first = (data.get("results") or [{}])[0]
    ok(f"Exa works. Result keys: {sorted(first.keys())}")
    ok("Saved tests/fixtures/exa_live_sample.json (check that 'highlights' and 'publishedDate' are present)")


async def check_groq(s):
    if not s.groq_configured:
        return bad("GROQ_API_KEY is still a placeholder")
    body = {"model": s.groq_model, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": 'Return JSON: {"ok": true}'}]}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(GROQ_URL, headers={"Authorization": f"Bearer {s.groq_api_key}"}, json=body)
    if r.status_code != 200:
        return bad(f"Groq returned HTTP {r.status_code} for model {s.groq_model}: {r.text[:200]}")
    content = r.json()["choices"][0]["message"]["content"]
    try:
        json.loads(content)
        ok(f"Groq works with {s.groq_model} and JSON mode. Reply: {content.strip()[:60]}")
    except ValueError:
        bad(f"Groq replied but not as clean JSON: {content[:120]}")


async def full_run(s, domain):
    exa, enrichment, synth = build_providers(s)
    from app.services.synthesis import synthesize

    async def synth_fn(ev, n, d, o):
        return await synthesize(s, ev, n, d, o)

    report = await run_research(ResearchRequest(website=domain), exa, enrichment, synth_fn if s.groq_configured else None)
    out_dir = ROOT / "docs" / "sample_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{domain.replace('/', '_')}.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    ok(f"Full run done. Saved {path.relative_to(ROOT)}")
    print("\nProviders:", [(p.name, p.state) for p in report.providers])
    print("Warnings:", report.warnings)
    for label in ("company_description", "industry", "target_market", "employee_size", "potential_gtm_opportunity"):
        f = getattr(report, label)
        print(f"- {label}: [{f.status.value}] {str(f.value)[:100]}")
    print(f"- sources: {len(report.source_urls)}, growth signals: {len(report.recent_growth_signals)}, decision makers: {len(report.decision_makers)}")


async def main():
    s = get_settings()
    await check_exa(s)
    await check_groq(s)
    print("[info] MoltSets:", "configured" if s.moltsets_configured else "not configured, mock enrichment will be used")
    if len(sys.argv) > 1:
        await full_run(s, sys.argv[1])


asyncio.run(main())
