import httpx
import pytest

from app.providers.base import ProviderError
from app.providers.moltsets import MoltSetsProvider, USER_AGENT

BODY = {
    "status": "success",
    "results": {"total": 1, "results": [{
        "name": "Jane Roe", "title": "VP Marketing", "seniority": "vp",
        "linkedin_url": "https://linkedin.com/in/janeroe", "business_email": "jane@acme.com",
        "business_email_risk_score": "A", "business_email_validated_at": "2026-10-01",
        "company": {"name": "Acme", "domain": "acme.com", "size": "51-200", "industry": "Software"},
    }]},
}


def provider(handler):
    return MoltSetsProvider("ms_key", "https://api.test/tools", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), max_wait=0)


async def test_maps_people_and_company_and_sends_required_headers():
    seen = {}

    def handler(r):
        seen["ua"] = r.headers.get("user-agent")
        seen["auth"] = r.headers.get("authorization")
        return httpx.Response(200, json=BODY)

    out = await provider(handler).enrich("Acme", "acme.com")
    assert out.people[0].name == "Jane Roe" and out.people[0].email_risk_score == "A"
    assert out.company.size == "51-200"
    assert seen["ua"] == USER_AGENT and seen["auth"] == "Bearer ms_key"


async def test_not_found_is_http_200_and_not_an_error():
    out = await provider(lambda r: httpx.Response(200, json={"status": "not_found", "results": {"results": [], "total": 0}})).enrich("Acme", "acme.com")
    assert out.people == [] and out.warnings


async def test_no_domain_skips_call():
    out = await provider(lambda r: httpx.Response(500)).enrich("Acme", None)
    assert out.people == [] and out.warnings


@pytest.mark.parametrize("code,kind", [(402, "quota"), (403, "forbidden"), (401, "auth"), (500, "server")])
async def test_error_codes_map_to_kinds(code, kind):
    with pytest.raises(ProviderError) as e:
        await provider(lambda r: httpx.Response(code)).enrich("Acme", "acme.com")
    assert e.value.kind == kind


async def test_429_retries_once_then_fails():
    calls = {"n": 0}

    def handler(r):
        calls["n"] += 1
        return httpx.Response(429, headers={"Retry-After": "0"})

    with pytest.raises(ProviderError) as e:
        await provider(handler).enrich("Acme", "acme.com")
    assert e.value.kind == "rate_limit" and calls["n"] == 2
