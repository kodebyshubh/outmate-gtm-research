from typing import Optional

from app.providers.base import CompanyInfo, EnrichmentResult, Person


class MockEnrichmentProvider:
    """Stand-in used only when no MoltSets key is available. Output is always labelled as mock and never merged into report fields."""

    name = "mock-enrichment"

    def __init__(self, reason: str = "MoltSets key not configured"):
        self.reason = reason

    async def enrich(self, company_name: Optional[str], domain: Optional[str]) -> EnrichmentResult:
        return EnrichmentResult(
            provider=self.name,
            state="mock",
            people=[Person(name="Sample Person (mock)", title="Head of Growth (mock)", seniority="vp (mock)")],
            company=CompanyInfo(name=company_name, domain=domain, size="51-200 (mock)", industry="Software (mock)"),
            warnings=[f"Enrichment is mock sample data, not real. Reason: {self.reason}."],
        )
