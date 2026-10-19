from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from app.providers.base import ProviderError, ResearchResult
from app.schemas import Evidence
from app.services.normalize import domain_from_url, label_for

EXA_SEARCH_URL = "https://api.exa.ai/search"


@dataclass
class Query:
    category: str
    text: str
    include_domains: Optional[list[str]] = None
    start_published_date: Optional[str] = None
    num_results: int = 4


def build_queries(company_name: Optional[str], domain: Optional[str]) -> list[Query]:
    label = label_for(company_name, domain)
    one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00.000Z")
    return [
        Query("profile", f"{label} company overview products and customers", [domain] if domain else None),
        Query("customers", f"who are the customers and target market of {label}", num_results=3),
        Query("news", f"{label} funding OR launch OR partnership OR expansion", None, one_year_ago),
        Query("hiring", f"{label} careers open roles hiring", num_results=3),
        Query("leadership", f"{label} leadership team founders CEO CTO executives", num_results=5),
    ]


def _clean_title(title):
    """Some pages return unrendered template titles like {{record.Posting_Title}}. Drop them so the UI shows the URL."""
    if not title or "{{" in title or "}}" in title:
        return None
    return title


class ExaProvider:
    name = "exa"

    def __init__(self, api_key: str, client: Optional[httpx.AsyncClient] = None, timeout: float = 12.0, max_retries: int = 2, backoff: float = 0.5):
        self.api_key = api_key
        self.client = client
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.cost_total = 0.0  # dollars spent by this instance (one instance per request)

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"x-api-key": self.api_key, "Content-Type": "application/json"}
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=self.timeout)
        try:
            last: Optional[ProviderError] = None
            for attempt in range(self.max_retries + 1):
                try:
                    resp = await client.post(EXA_SEARCH_URL, json=payload, headers=headers, timeout=self.timeout)
                except httpx.TimeoutException:
                    last = ProviderError(self.name, "timeout", "request timed out")
                except httpx.HTTPError as exc:
                    last = ProviderError(self.name, "server", f"network error: {exc.__class__.__name__}")
                else:
                    if resp.status_code in (401, 403):
                        raise ProviderError(self.name, "auth", f"HTTP {resp.status_code}: check EXA_API_KEY")
                    if resp.status_code == 429:
                        last = ProviderError(self.name, "rate_limit", "HTTP 429 rate limited")
                    elif resp.status_code >= 500:
                        last = ProviderError(self.name, "server", f"HTTP {resp.status_code}")
                    elif resp.status_code >= 400:
                        raise ProviderError(self.name, "bad_response", f"HTTP {resp.status_code}: {resp.text[:200]}")
                    else:
                        try:
                            return resp.json()
                        except ValueError:
                            raise ProviderError(self.name, "bad_response", "response was not valid JSON")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff * (2 ** attempt))
            assert last is not None
            raise last
        finally:
            if owns_client:
                await client.aclose()

    async def search(self, query: Query, num_results: Optional[int] = None) -> list[dict[str, Any]]:
        num_results = num_results or query.num_results
        payload: dict[str, Any] = {
            "query": query.text,
            "type": "auto",
            "numResults": num_results,
            "contents": {"highlights": True},
        }
        if query.include_domains:
            payload["includeDomains"] = query.include_domains
        if query.start_published_date:
            payload["startPublishedDate"] = query.start_published_date
        data = await self._post(payload)
        cost = data.get("costDollars")
        if isinstance(cost, dict) and isinstance(cost.get("total"), (int, float)):
            self.cost_total += float(cost["total"])
        results = data.get("results")
        if not isinstance(results, list):
            raise ProviderError(self.name, "bad_response", "missing results list")
        return results

    async def research(self, company_name: Optional[str], domain: Optional[str], objective: Optional[str] = None) -> ResearchResult:
        result = ResearchResult()
        resolved = domain
        if not resolved:
            try:
                first = await self.search(Query("resolve", f"{label_for(company_name, None)} official website"), num_results=3)
                for item in first:
                    guess = domain_from_url(item.get("url", ""))
                    if guess:
                        resolved = guess
                        result.warnings.append(f"Domain was not provided; using {guess} from the top search result. Check it is the right company.")
                        break
            except ProviderError as exc:
                result.warnings.append(f"Could not resolve domain: {exc.message}")
        result.resolved_domain = resolved

        queries = build_queries(company_name, resolved)
        outcomes = await asyncio.gather(*(self.search(q) for q in queries), return_exceptions=True)

        seen: dict[str, Evidence] = {}
        errors: list[ProviderError] = []
        for query, outcome in zip(queries, outcomes):
            if isinstance(outcome, ProviderError):
                errors.append(outcome)
                result.warnings.append(f"Exa '{query.category}' search failed ({outcome.kind}).")
                continue
            if isinstance(outcome, BaseException):
                errors.append(ProviderError(self.name, "server", outcome.__class__.__name__))
                result.warnings.append(f"Exa '{query.category}' search failed unexpectedly.")
                continue
            for item in outcome:
                url = item.get("url")
                if not url or url in seen:
                    continue
                highlights = item.get("highlights") or []
                text = " ... ".join(h for h in highlights if isinstance(h, str)).strip()
                seen[url] = Evidence(
                    id=f"E{len(seen) + 1}",
                    url=url,
                    title=_clean_title(item.get("title")),
                    published_date=item.get("publishedDate"),
                    highlight=text,
                    category=query.category,
                )
        result.evidence = list(seen.values())
        result.cost_usd = round(self.cost_total, 4)
        if errors and len(errors) == len(queries):
            result.state = "error"
            raise_kind = errors[0]
            result.warnings.append(f"All Exa searches failed. First error: {raise_kind.kind}.")
        elif not result.evidence:
            result.warnings.append("Exa returned no public results for this company.")
        return result
