from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field as PField, model_validator


class Status(str, Enum):
    VERIFIED = "verified"
    PROVIDER_REPORTED = "provider-reported"
    INFERRED = "inferred"
    UNAVAILABLE = "unavailable"


class ResearchRequest(BaseModel):
    company_name: Optional[str] = PField(default=None, max_length=200)
    website: Optional[str] = PField(default=None, max_length=300)
    objective: Optional[str] = PField(default=None, max_length=500)
    refresh: bool = False  # skip the short in-memory cache

    @model_validator(mode="after")
    def need_name_or_website(self) -> "ResearchRequest":
        if not (self.company_name or "").strip() and not (self.website or "").strip():
            raise ValueError("Provide a company name or a website/domain.")
        return self


class Evidence(BaseModel):
    id: str
    url: str
    title: Optional[str] = None
    published_date: Optional[str] = None
    highlight: str = ""
    category: str = ""
    provider: str = "exa"


class Source(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    published_date: Optional[str] = None
    quote: Optional[str] = None


class Field(BaseModel):
    value: Any = None
    status: Status = Status.UNAVAILABLE
    sources: list[Source] = PField(default_factory=list)
    note: Optional[str] = None


class ProviderStatus(BaseModel):
    name: str
    state: str  # ok, error, skipped, mock
    message: str = ""


class Report(BaseModel):
    company_name: Field
    website_domain: Field
    company_description: Field
    industry: Field
    target_market: Field
    employee_size: Field
    recent_growth_signals: list[Field] = PField(default_factory=list)
    potential_gtm_opportunity: Field
    decision_makers: list[Field] = PField(default_factory=list)
    contact_information: Field
    source_urls: list[str] = PField(default_factory=list)
    providers: list[ProviderStatus] = PField(default_factory=list)
    warnings: list[str] = PField(default_factory=list)
    mock_enrichment: Optional[dict[str, Any]] = None
    dropped_claims: list[dict[str, Any]] = PField(default_factory=list)
    evidence: list[Evidence] = PField(default_factory=list)
    generated_at: str = PField(default_factory=lambda: datetime.now(timezone.utc).isoformat())
