from __future__ import annotations

import asyncio
import time
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.providers.exa import ExaProvider
from app.providers.mock_enrichment import MockEnrichmentProvider
from app.providers.moltsets import MoltSetsProvider
from app.providers.skipped_enrichment import SkippedEnrichment
from app.schemas import Report, ResearchRequest
from app.services.research import run_research
from app.services.synthesis import synthesize

app = FastAPI(title="Outmate Company Research Engine", version="0.1.0")

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_settings.frontend_origin],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class MissingExaKey:
    """Used when EXA_API_KEY is not set, so the API still answers with a clear message."""

    name = "exa"

    async def research(self, company_name, domain, objective):
        from app.providers.base import ProviderError

        raise ProviderError("exa", "auth", "EXA_API_KEY is not configured")


def build_providers(settings: Settings):
    exa = ExaProvider(settings.exa_api_key, timeout=settings.exa_timeout_seconds) if settings.exa_configured else MissingExaKey()
    if settings.enrichment_provider == "moltsets" and settings.moltsets_configured:
        enrichment = MoltSetsProvider(settings.moltsets_api_key, settings.moltsets_base_url, timeout=settings.moltsets_timeout_seconds)
    elif settings.enrichment_provider == "mock":
        enrichment = MockEnrichmentProvider("mock selected in config")
    else:
        enrichment = SkippedEnrichment("Enrichment skipped: MoltSets is not used in this version. Report is based on public research only.")
    synth_fn: Optional[object] = None
    if settings.groq_configured:

        async def synth_fn(evidence, name, domain, objective):  # type: ignore[no-redef]
            return await synthesize(settings, evidence, name, domain, objective)

    return exa, enrichment, synth_fn


CACHE_TTL_SECONDS = 15 * 60
OVERALL_TIMEOUT_SECONDS = 75
_cache: dict[tuple, tuple[float, Report]] = {}


def _cache_key(req: ResearchRequest) -> tuple:
    return ((req.company_name or "").strip().lower(), (req.website or "").strip().lower(), (req.objective or "").strip().lower())


@app.post("/api/research", response_model=Report)
async def research(req: ResearchRequest) -> Report:
    """Run the full workflow. A short in-memory cache protects free-tier credits while testing and demoing."""
    key = _cache_key(req)
    hit = _cache.get(key)
    if hit and not req.refresh and time.time() - hit[0] < CACHE_TTL_SECONDS:
        return hit[1]
    exa, enrichment, synth_fn = build_providers(get_settings())
    try:
        report = await asyncio.wait_for(run_research(req, exa, enrichment, synth_fn), timeout=OVERALL_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Research took too long. Please try again.")
    if report.evidence:  # do not cache empty or failed runs
        _cache[key] = (time.time(), report)
    return report


@app.get("/api/health")
async def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "exa_configured": s.exa_configured,
        "groq_configured": s.groq_configured,
        "enrichment": "moltsets" if (s.enrichment_provider == "moltsets" and s.moltsets_configured) else ("mock" if s.enrichment_provider == "mock" else "skipped"),
    }
