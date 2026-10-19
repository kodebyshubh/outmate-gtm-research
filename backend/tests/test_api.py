from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_never_returns_keys():
    body = client.get("/api/health").json()
    assert set(body) == {"status", "exa_configured", "groq_configured", "enrichment"}


def test_requires_name_or_website():
    r = client.post("/api/research", json={"objective": "x"})
    assert r.status_code == 422


def test_cache_returns_same_report_and_refresh_bypasses(monkeypatch):
    from app import main
    from app.schemas import Evidence, Field, Report

    calls = {"n": 0}

    async def fake_run(req, exa, enrichment, synth):
        calls["n"] += 1
        f = Field()
        return Report(company_name=f, website_domain=f, company_description=f, industry=f, target_market=f, employee_size=f,
                      potential_gtm_opportunity=f, contact_information=f, evidence=[Evidence(id="E1", url="https://a.com")])

    monkeypatch.setattr(main, "run_research", fake_run)
    main._cache.clear()
    body = {"company_name": "CacheCo"}
    client.post("/api/research", json=body)
    client.post("/api/research", json=body)
    assert calls["n"] == 1
    client.post("/api/research", json={**body, "refresh": True})
    assert calls["n"] == 2
    main._cache.clear()


def test_empty_runs_are_not_cached(monkeypatch):
    from app import main
    from app.schemas import Field, Report

    calls = {"n": 0}

    async def fake_run(req, exa, enrichment, synth):
        calls["n"] += 1
        f = Field()
        return Report(company_name=f, website_domain=f, company_description=f, industry=f, target_market=f, employee_size=f,
                      potential_gtm_opportunity=f, contact_information=f)

    monkeypatch.setattr(main, "run_research", fake_run)
    main._cache.clear()
    client.post("/api/research", json={"company_name": "NoEvidence"})
    client.post("/api/research", json={"company_name": "NoEvidence"})
    assert calls["n"] == 2
    main._cache.clear()


def test_report_defaults_are_real_lists():
    from app.schemas import Field, Report

    f = Field()
    r = Report(company_name=f, website_domain=f, company_description=f, industry=f, target_market=f, employee_size=f,
               potential_gtm_opportunity=f, contact_information=f)
    assert r.evidence == [] and r.warnings == [] and r.source_urls == [] and r.recent_growth_signals == []
    assert isinstance(r.generated_at, str)


def test_build_providers_picks_skipped_without_key_and_mock_when_asked():
    from app.config import Settings
    from app.main import build_providers
    from app.providers.mock_enrichment import MockEnrichmentProvider
    from app.providers.moltsets import MoltSetsProvider
    from app.providers.skipped_enrichment import SkippedEnrichment

    assert isinstance(build_providers(Settings(enrichment_provider="moltsets", moltsets_api_key="", _env_file=None))[1], SkippedEnrichment)
    assert isinstance(build_providers(Settings(enrichment_provider="none", _env_file=None))[1], SkippedEnrichment)
    assert isinstance(build_providers(Settings(enrichment_provider="mock", _env_file=None))[1], MockEnrichmentProvider)
    assert isinstance(build_providers(Settings(enrichment_provider="moltsets", moltsets_api_key="ms_x", _env_file=None))[1], MoltSetsProvider)
