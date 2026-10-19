from typing import Optional

from app.providers.base import EnrichmentResult


class SkippedEnrichment:
    """Used when enrichment is intentionally off (Outmate said to skip MoltSets, or no key). Adds no data."""

    name = "enrichment"

    def __init__(self, reason: str = "enrichment provider skipped"):
        self.reason = reason

    async def enrich(self, company_name: Optional[str], domain: Optional[str]) -> EnrichmentResult:
        return EnrichmentResult(provider=self.name, state="skipped", warnings=[self.reason])
