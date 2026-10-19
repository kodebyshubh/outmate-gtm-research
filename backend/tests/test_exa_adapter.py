import httpx
import pytest

from app.providers.base import ProviderError
from app.providers.exa import ExaProvider, Query

OK = {"results": [{"url": "https://acme.com/about", "title": "About Acme", "publishedDate": "2026-05-01", "highlights": ["Acme builds widgets for B2B teams."]}]}


def provider(handler, **kw):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ExaProvider("key", client=client, backoff=0, **kw)


async def test_search_maps_results():
    p = provider(lambda r: httpx.Response(200, json=OK))
    res = await p.search(Query("profile", "acme"))
    assert res[0]["url"] == "https://acme.com/about"


async def test_research_builds_evidence_with_urls_and_dates():
    p = provider(lambda r: httpx.Response(200, json=OK))
    out = await p.research("Acme", "acme.com", None)
    assert out.evidence[0].url == "https://acme.com/about"
    assert out.evidence[0].published_date == "2026-05-01"
    assert "widgets" in out.evidence[0].highlight
    assert len(out.evidence) == 1  # deduped across queries


async def test_empty_results_are_not_an_error():
    p = provider(lambda r: httpx.Response(200, json={"results": []}))
    out = await p.research("Acme", "acme.com", None)
    assert out.evidence == []
    assert any("no public results" in w for w in out.warnings)


async def test_retries_on_429_then_succeeds():
    calls = {"n": 0}

    def handler(r):
        calls["n"] += 1
        return httpx.Response(429) if calls["n"] == 1 else httpx.Response(200, json=OK)

    p = provider(handler)
    assert (await p.search(Query("profile", "acme")))[0]["title"] == "About Acme"


async def test_auth_error_is_not_retried():
    calls = {"n": 0}

    def handler(r):
        calls["n"] += 1
        return httpx.Response(401)

    p = provider(handler)
    with pytest.raises(ProviderError) as e:
        await p.search(Query("profile", "acme"))
    assert e.value.kind == "auth" and calls["n"] == 1


async def test_timeout_raises_typed_error():
    def handler(r):
        raise httpx.ReadTimeout("slow")

    p = provider(handler, max_retries=1)
    with pytest.raises(ProviderError) as e:
        await p.search(Query("profile", "acme"))
    assert e.value.kind == "timeout"


async def test_all_searches_failing_marks_state_error():
    p = provider(lambda r: httpx.Response(500), max_retries=0)
    out = await p.research("Acme", "acme.com", None)
    assert out.state == "error" and out.evidence == []


async def test_real_exa_fixture_maps_to_evidence():
    """Uses a response saved from the live API by scripts/smoke_live.py."""
    import json
    from pathlib import Path

    path = Path(__file__).parent / "fixtures" / "exa_live_sample.json"
    if not path.exists():
        pytest.skip("run scripts/smoke_live.py to save a live fixture")
    data = json.loads(path.read_text(encoding="utf-8"))
    p = provider(lambda r: httpx.Response(200, json=data))
    out = await p.research("Stripe", "stripe.com", None)
    assert out.evidence and all(e.url and e.highlight for e in out.evidence)
    assert out.cost_usd and out.cost_usd > 0


async def test_missing_published_date_is_fine():
    body = {"results": [{"url": "https://acme.com/x", "title": "X", "highlights": ["Acme builds widgets for teams."]}]}
    out = await provider(lambda r: httpx.Response(200, json=body)).research("Acme", "acme.com", None)
    assert out.evidence[0].published_date is None


async def test_template_titles_are_dropped():
    body = {"results": [{"url": "https://acme.com/jobs", "title": "{{record.Posting_Title}}", "highlights": ["Current Openings Full time 9 Jobs"]}]}
    out = await provider(lambda r: httpx.Response(200, json=body)).research("Acme", "acme.com", None)
    assert out.evidence[0].title is None
