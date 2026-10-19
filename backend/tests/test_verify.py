from app.schemas import Evidence, Status
from app.services.verify import RawField, build_field, quote_in_evidence

E = {"E1": Evidence(id="E1", url="https://acme.com", title="Acme", published_date="2026-05-01", highlight="Acme helps B2B teams automate outreach.")}


def test_verified_when_quote_found():
    f = build_field(RawField(value="Outreach automation", evidence_ids=["E1"], quote="helps B2B teams automate outreach", basis="stated"), E)
    assert f.status == Status.VERIFIED and f.sources[0].url == "https://acme.com"


def test_stated_claim_with_missing_quote_is_dropped():
    f = build_field(RawField(value="x", evidence_ids=["E1"], quote="we have 500 employees", basis="stated"), E)
    assert f.status == Status.UNAVAILABLE and f.value is None


def test_inferred_with_citation_is_kept_as_inferred():
    f = build_field(RawField(value="Good fit", evidence_ids=["E1"], basis="inferred"), E)
    assert f.status == Status.INFERRED


def test_inferred_without_valid_citation_is_dropped():
    f = build_field(RawField(value="Good fit", evidence_ids=["E9"], basis="inferred"), E)
    assert f.status == Status.UNAVAILABLE


def test_sensitive_field_cannot_be_inferred():
    f = build_field(RawField(value="200", evidence_ids=["E1"], basis="inferred"), E, sensitive=True)
    assert f.status == Status.UNAVAILABLE


def test_empty_value_is_unavailable():
    assert build_field(RawField(value=None), E).status == Status.UNAVAILABLE


def test_quote_matching_ignores_case_and_whitespace():
    assert quote_in_evidence("HELPS  b2b teams", list(E.values()))
    assert not quote_in_evidence("short", list(E.values()))


def test_quote_matching_ignores_markdown_and_curly_quotes():
    ev = [Evidence(id="E1", url="https://x.com", highlight="- Stripe’s total payment volume | increased to **$1.4T** in 2024, up 38%.")]
    assert quote_in_evidence("Stripe's total payment volume increased to $1.4T in 2024", ev)


def test_quote_with_ellipsis_requires_each_part_in_order():
    ev = [Evidence(id="E1", url="https://x.com", highlight="Acme raised a Series B round led by Foo Capital last spring to expand into Europe.")]
    assert quote_in_evidence("Acme raised a Series B round ... to expand into Europe", ev)
    assert not quote_in_evidence("to expand into Europe ... Acme raised a Series B round", ev)


def test_invented_numbers_still_fail():
    ev = [Evidence(id="E1", url="https://x.com", highlight="Acme has about 200 employees.")]
    assert not quote_in_evidence("Acme has about 900 employees", ev)


def test_figures_not_in_source_downgrade_verified_to_inferred():
    ev = {"E1": Evidence(id="E1", url="https://z.com", title="Zoho press", published_date="2025-12-18", highlight="Zoho Launches Zia Chat, an AI interface for frictionless work.")}
    f = build_field(RawField(value="Launched Zia Chat (sep 23, 2026)", evidence_ids=["E1"], quote="Zoho Launches Zia Chat, an AI interface", basis="stated"), ev)
    assert f.status == Status.INFERRED and "2026" in f.note


def test_figures_in_source_or_publication_date_stay_verified():
    ev = {"E1": Evidence(id="E1", url="https://z.com", title="Perplexity launches Enterprise Pro", published_date="2024-04-23T00:00:00.000Z", highlight="Introducing Perplexity Enterprise Pro, now with 134 seats.")}
    f = build_field(RawField(value="Launched Enterprise Pro - 2024-04-23, 134 seats", evidence_ids=["E1"], quote="Introducing Perplexity Enterprise Pro", basis="stated"), ev)
    assert f.status == Status.VERIFIED


def test_comma_numbers_match():
    ev = {"E1": Evidence(id="E1", url="https://z.com", highlight="Number of employees | 18,000+ (2025)")}
    f = build_field(RawField(value="18,000+ (2025)", evidence_ids=["E1"], quote="Number of employees | 18,000+ (2025)", basis="stated"), ev, sensitive=True)
    assert f.status == Status.VERIFIED


def test_sensitive_value_with_invented_number_is_dropped():
    ev = {"E1": Evidence(id="E1", url="https://z.com", highlight="Number of employees | 18,000+ (2025)")}
    f = build_field(RawField(value="25,000 (2025)", evidence_ids=["E1"], quote="Number of employees | 18,000+ (2025)", basis="stated"), ev, sensitive=True)
    assert f.status == Status.UNAVAILABLE
