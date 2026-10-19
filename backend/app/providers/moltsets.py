from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx

from app.providers.base import CompanyInfo, EnrichmentResult, Person, ProviderError

USER_AGENT = "outmate-research-prototype/0.1"


def _first(d: dict[str, Any], *keys: str) -> Optional[Any]:
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return None


def parse_people(data: dict[str, Any]) -> tuple[list[Person], Optional[CompanyInfo]]:
    """Map a search_people response to Person and CompanyInfo. Handles results being a list or a dict with a nested results list."""
    block = data.get("results")
    if isinstance(block, dict):
        items = block.get("results") or []
    elif isinstance(block, list):
        items = block
    else:
        items = []
    people: list[Person] = []
    company: Optional[CompanyInfo] = None
    for item in items:
        if not isinstance(item, dict):
            continue
        name = _first(item, "name", "full_name")
        if not name:
            parts = [item.get("first_name"), item.get("last_name")]
            name = " ".join(p for p in parts if p) or None
        people.append(
            Person(
                name=name,
                title=_first(item, "title", "headline"),
                seniority=item.get("seniority"),
                linkedin_url=item.get("linkedin_url"),
                business_email=item.get("business_email"),
                email_risk_score=item.get("business_email_risk_score"),
                email_validated_at=item.get("business_email_validated_at"),
                last_updated_at=item.get("last_updated_at"),
            )
        )
        comp = item.get("company")
        if company is None and isinstance(comp, dict):
            company = CompanyInfo(
                name=_first(comp, "name"),
                domain=_first(comp, "domain"),
                size=_first(comp, "size", "employee_range", "employee_count"),
                industry=_first(comp, "industry", "linkedin_industry"),
            )
    return people, company


class MoltSetsProvider:
    name = "moltsets"

    def __init__(self, api_key: str, base_url: str, client: Optional[httpx.AsyncClient] = None, timeout: float = 15.0, max_wait: float = 5.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = client
        self.timeout = timeout
        self.max_wait = max_wait

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        }
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=self.timeout)
        try:
            for attempt in range(2):
                try:
                    resp = await client.post(f"{self.base_url}{path}", json=payload, headers=headers, timeout=self.timeout)
                except httpx.TimeoutException:
                    raise ProviderError(self.name, "timeout", "request timed out")
                except httpx.HTTPError as exc:
                    raise ProviderError(self.name, "server", f"network error: {exc.__class__.__name__}")
                code = resp.status_code
                if code == 429 and attempt == 0:
                    try:
                        wait = float(resp.headers.get("Retry-After", "1"))
                    except ValueError:
                        wait = 1.0
                    await asyncio.sleep(min(wait, self.max_wait))
                    continue
                if code == 429:
                    raise ProviderError(self.name, "rate_limit", "rate or fair-use limit reached")
                if code == 402:
                    raise ProviderError(self.name, "quota", "insufficient tokens or trial used up")
                if code == 403:
                    raise ProviderError(self.name, "forbidden", "key invalid, tool not on plan, or missing User-Agent")
                if code == 401:
                    raise ProviderError(self.name, "auth", "invalid API key")
                if code >= 500:
                    raise ProviderError(self.name, "server", f"HTTP {code}")
                if code >= 400:
                    raise ProviderError(self.name, "bad_response", f"HTTP {code}: {resp.text[:200]}")
                try:
                    return resp.json()
                except ValueError:
                    raise ProviderError(self.name, "bad_response", "response was not valid JSON")
            raise ProviderError(self.name, "rate_limit", "rate limited")
        finally:
            if owns_client:
                await client.aclose()

    async def enrich(self, company_name: Optional[str], domain: Optional[str]) -> EnrichmentResult:
        result = EnrichmentResult(provider=self.name)
        if not domain:
            result.warnings.append("MoltSets lookup skipped: no company domain available.")
            return result
        data = await self._post("/search_people", {"company_domain": domain, "limit": 5})
        status = data.get("status")
        people, company = parse_people(data)
        if status == "not_found" or not people:
            result.warnings.append("MoltSets returned no people for this domain.")
            return result
        result.people = people
        result.company = company
        return result
