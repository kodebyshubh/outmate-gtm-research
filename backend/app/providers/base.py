from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

from app.schemas import Evidence


class ProviderError(Exception):
    """Typed provider failure. kind is one of: auth, quota, rate_limit, timeout, server, bad_response, forbidden."""

    def __init__(self, provider: str, kind: str, message: str):
        super().__init__(f"{provider}: {kind}: {message}")
        self.provider = provider
        self.kind = kind
        self.message = message


@dataclass
class ResearchResult:
    evidence: list[Evidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    resolved_domain: Optional[str] = None
    state: str = "ok"
    cost_usd: Optional[float] = None


@dataclass
class Person:
    name: Optional[str] = None
    title: Optional[str] = None
    seniority: Optional[str] = None
    linkedin_url: Optional[str] = None
    business_email: Optional[str] = None
    email_risk_score: Optional[str] = None
    email_validated_at: Optional[str] = None
    last_updated_at: Optional[str] = None


@dataclass
class CompanyInfo:
    name: Optional[str] = None
    domain: Optional[str] = None
    size: Optional[str] = None
    industry: Optional[str] = None


@dataclass
class EnrichmentResult:
    provider: str
    state: str = "ok"  # ok, mock
    people: list[Person] = field(default_factory=list)
    company: Optional[CompanyInfo] = None
    warnings: list[str] = field(default_factory=list)


class ResearchProvider(Protocol):
    name: str

    async def research(self, company_name: Optional[str], domain: Optional[str], objective: Optional[str]) -> ResearchResult: ...


class EnrichmentProvider(Protocol):
    name: str

    async def enrich(self, company_name: Optional[str], domain: Optional[str]) -> EnrichmentResult: ...
