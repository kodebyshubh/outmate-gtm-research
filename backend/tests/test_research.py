from app.providers.base import CompanyInfo, EnrichmentResult, Person, ProviderError, ResearchResult
from app.providers.mock_enrichment import MockEnrichmentProvider
from app.schemas import Evidence, ResearchRequest, Status
from app.services.research import run_research
from app.services.verify import RawField, RawReport

EVIDENCE = [Evidence(id="E1", url="https://acme.com", title="Acme", highlight="Acme helps B2B teams automate outreach.", category="profile")]


class FakeExa:
    name = "exa"

    def __init__(self, evidence=None, error=None):
        self.evidence, self.error = evidence if evidence is not None else EVIDENCE, error

    async def research(self, name, domain, objective):
        if self.error:
            raise self.error
        return ResearchResult(evidence=self.evidence, resolved_domain=domain)


class FakeEnrich:
    name = "moltsets"

    def __init__(self, error=None, size="51-200"):
        self.error, self.size = error, size

    async def enrich(self, name, domain):
        if self.error:
            raise self.error
        return EnrichmentResult(provider="moltsets", people=[Person(name="Jane Roe", title="VP Marketing", business_email="jane@acme.com", email_risk_score="A")], company=CompanyInfo(size=self.size, industry="Software"))


async def synth(evidence, name, domain, objective):
    return RawReport(
        company_description=RawField(value="B2B outreach automation", evidence_ids=["E1"], quote="automate outreach", basis="stated"),
        employee_size=RawField(value="500", evidence_ids=["E1"], quote="500 employees", basis="stated"),
        potential_gtm_opportunity=RawField(value="Likely fit", evidence_ids=["E1"], basis="inferred"),
    )


REQ = ResearchRequest(company_name="Acme", website="https://acme.com")


async def test_full_report_labels_each_field_honestly():
    r = await run_research(REQ, FakeExa(), FakeEnrich(), synth)
    assert r.company_description.status == Status.VERIFIED
    assert r.potential_gtm_opportunity.status == Status.INFERRED
    assert r.employee_size.status == Status.PROVIDER_REPORTED and r.employee_size.value == "51-200"
    assert r.decision_makers[0].status == Status.PROVIDER_REPORTED
    assert r.contact_information.status == Status.PROVIDER_REPORTED
    assert r.source_urls == ["https://acme.com"]


async def test_fabricated_employee_count_is_dropped_without_provider():
    class NoSize(FakeEnrich):
        async def enrich(self, name, domain):
            return EnrichmentResult(provider="moltsets")

    r = await run_research(REQ, FakeExa(), NoSize(), synth)
    assert r.employee_size.status == Status.UNAVAILABLE
    assert r.contact_information.status == Status.UNAVAILABLE


async def test_enrichment_failure_still_returns_report():
    r = await run_research(REQ, FakeExa(), FakeEnrich(error=ProviderError("moltsets", "forbidden", "no")), synth)
    assert r.company_description.status == Status.VERIFIED
    assert any(p.name == "moltsets" and p.state == "error" for p in r.providers)
    assert r.warnings


async def test_exa_failure_returns_unavailable_report_with_warning():
    r = await run_research(REQ, FakeExa(error=ProviderError("exa", "auth", "bad key")), FakeEnrich(), synth)
    assert r.company_description.status == Status.UNAVAILABLE
    assert any("Web research failed" in w for w in r.warnings)


async def test_empty_evidence_skips_synthesis():
    r = await run_research(REQ, FakeExa(evidence=[]), FakeEnrich(), synth)
    assert r.company_description.status == Status.UNAVAILABLE


async def test_llm_failure_falls_back_to_evidence_only():
    async def boom(*a):
        raise RuntimeError("down")

    r = await run_research(REQ, FakeExa(), FakeEnrich(), boom)
    assert r.company_description.status == Status.UNAVAILABLE
    assert r.evidence and any("Summarization failed" in w for w in r.warnings)


async def test_mock_enrichment_is_labelled_and_not_merged():
    r = await run_research(REQ, FakeExa(), MockEnrichmentProvider("no key"), synth)
    assert r.mock_enrichment and "MOCK" in r.mock_enrichment["label"]
    assert r.decision_makers == [] and r.employee_size.status == Status.UNAVAILABLE
    assert any(p.state == "mock" for p in r.providers)


async def test_conflicting_employee_size_is_flagged():
    ev = [Evidence(id="E1", url="https://acme.com", title="Acme", highlight="Acme has 500 employees and helps B2B teams.", category="profile")]

    async def stated(evidence, name, domain, objective):
        return RawReport(employee_size=RawField(value="500", evidence_ids=["E1"], quote="Acme has 500 employees", basis="stated"))

    r = await run_research(REQ, FakeExa(evidence=ev), FakeEnrich(size="51-200"), stated)
    assert any("conflict" in w.lower() for w in r.warnings)
    assert r.employee_size.status == Status.PROVIDER_REPORTED


async def test_dropped_claims_are_reported_and_warned():
    async def bad_quote(evidence, name, domain, objective):
        return RawReport(target_market=RawField(value="SMBs", evidence_ids=["E1"], quote="sells to every small business on earth", basis="stated"))

    r = await run_research(REQ, FakeExa(), FakeEnrich(), bad_quote)
    assert r.target_market.status == Status.UNAVAILABLE
    assert r.dropped_claims and r.dropped_claims[0]["field"] == "target_market"
    assert any("dropped" in w for w in r.warnings)


async def test_skipped_enrichment_adds_nothing_and_does_not_break():
    from app.providers.skipped_enrichment import SkippedEnrichment

    r = await run_research(REQ, FakeExa(), SkippedEnrichment("off"), synth)
    assert r.mock_enrichment is None
    assert any(p.state == "skipped" for p in r.providers)
    assert r.contact_information.status == Status.UNAVAILABLE
    assert r.company_description.status == Status.VERIFIED
