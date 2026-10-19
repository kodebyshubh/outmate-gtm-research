from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional

from app.providers.base import EnrichmentProvider, EnrichmentResult, ProviderError, ResearchProvider, ResearchResult
from app.schemas import Evidence, Field, ProviderStatus, Report, ResearchRequest, Source, Status
from app.services.normalize import normalize_domain
from app.services.verify import RawReport, build_field

# synthesize_fn(evidence, name, domain, objective) -> RawReport
SynthFn = Callable[[list[Evidence], Optional[str], Optional[str], Optional[str]], Awaitable[RawReport]]

UNAVAILABLE = Field(status=Status.UNAVAILABLE)


def _unavailable(note: str) -> Field:
    return Field(status=Status.UNAVAILABLE, note=note)


def _provider_source(provider: str, title: str) -> Source:
    return Source(url=None, title=f"{provider}: {title}")


def _merge_enrichment(report_fields: dict[str, Any], enr: EnrichmentResult, warnings: list[str]) -> None:
    """Merge real provider data. Provider values are labelled provider-reported and conflicts are flagged."""
    src = _provider_source(enr.provider, "provider data")
    comp = enr.company
    if comp and comp.size:
        existing: Field = report_fields["employee_size"]
        if existing.status == Status.VERIFIED and str(existing.value).strip().lower() != str(comp.size).strip().lower():
            warnings.append(f"Employee size conflict: source says '{existing.value}', {enr.provider} says '{comp.size}'. Both shown; provider value kept.")
            report_fields["employee_size"] = Field(value=comp.size, status=Status.PROVIDER_REPORTED, sources=[src] + existing.sources, note=f"conflicts with source value '{existing.value}'")
        else:
            report_fields["employee_size"] = Field(value=comp.size, status=Status.PROVIDER_REPORTED, sources=[src])
    if comp and comp.industry and report_fields["industry"].status == Status.UNAVAILABLE:
        report_fields["industry"] = Field(value=comp.industry, status=Status.PROVIDER_REPORTED, sources=[src])

    people = [
        Field(
            value={"name": p.name, "role": p.title, "seniority": p.seniority, "linkedin_url": p.linkedin_url},
            status=Status.PROVIDER_REPORTED,
            sources=[src],
            note=f"last updated {p.last_updated_at}" if p.last_updated_at else None,
        )
        for p in enr.people
        if p.name
    ]
    known = {(p.name or "").lower() for p in enr.people}
    for f in report_fields["decision_makers"]:
        v = f.value if isinstance(f.value, dict) else {}
        if str(v.get("name", "")).lower() not in known:
            people.append(f)
    report_fields["decision_makers"] = people

    emails = [
        {"name": p.name, "business_email": p.business_email, "risk_score": p.email_risk_score, "validated_at": p.email_validated_at}
        for p in enr.people
        if p.business_email
    ]
    if emails:
        report_fields["contact_information"] = Field(value=emails, status=Status.PROVIDER_REPORTED, sources=[src], note="returned by the provider, not independently verified")


async def run_research(
    req: ResearchRequest,
    exa: ResearchProvider,
    enrichment: EnrichmentProvider,
    synthesize_fn: Optional[SynthFn],
) -> Report:
    name = (req.company_name or "").strip() or None
    domain = normalize_domain(req.website)
    warnings: list[str] = []
    providers: list[ProviderStatus] = []
    if req.website and not domain:
        warnings.append("The website could not be parsed as a domain; searching by company name instead.")

    exa_res: ResearchResult = ResearchResult()
    enr_res: Optional[EnrichmentResult] = None

    async def run_enrichment(d: Optional[str]) -> Optional[EnrichmentResult]:
        try:
            out = await enrichment.enrich(name, d)
        except ProviderError as exc:
            providers.append(ProviderStatus(name=enrichment.name, state="error", message=f"{exc.kind}: {exc.message}"))
            warnings.append(f"Enrichment unavailable ({exc.kind}). Report is based on public research only.")
            return None
        except Exception as exc:  # never let one provider kill the report
            providers.append(ProviderStatus(name=enrichment.name, state="error", message=exc.__class__.__name__))
            warnings.append("Enrichment failed unexpectedly. Report is based on public research only.")
            return None
        providers.append(ProviderStatus(name=out.provider, state=out.state, message="; ".join(out.warnings)))
        return out

    async def run_exa() -> ResearchResult:
        try:
            res = await exa.research(name, domain, req.objective)
        except ProviderError as exc:
            providers.append(ProviderStatus(name=exa.name, state="error", message=f"{exc.kind}: {exc.message}"))
            warnings.append(f"Web research failed ({exc.kind}).")
            return ResearchResult(state="error")
        except Exception as exc:
            providers.append(ProviderStatus(name=exa.name, state="error", message=exc.__class__.__name__))
            warnings.append("Web research failed unexpectedly.")
            return ResearchResult(state="error")
        cost_note = f"cost ${res.cost_usd:.3f}" if res.cost_usd else ""
        providers.append(ProviderStatus(name=exa.name, state=res.state, message="; ".join([m for m in [cost_note, *res.warnings[:3]] if m])))
        warnings.extend(res.warnings)
        return res

    if domain:
        exa_res, enr_res = await asyncio.gather(run_exa(), run_enrichment(domain))
    else:
        exa_res = await run_exa()
        domain = exa_res.resolved_domain
        enr_res = await run_enrichment(domain)

    evidence = exa_res.evidence
    by_id = {e.id: e for e in evidence}

    fields: dict[str, Any] = {
        "company_name": Field(value=name, status=Status.VERIFIED, note="provided by the user") if name else _unavailable("not provided"),
        "website_domain": Field(value=domain, status=Status.VERIFIED, note="provided by the user" if req.website and normalize_domain(req.website) else "taken from the top search result") if domain else _unavailable("not provided"),
        "company_description": _unavailable("no research evidence"),
        "industry": _unavailable("no research evidence"),
        "target_market": _unavailable("no research evidence"),
        "employee_size": _unavailable("no source or provider returned it"),
        "recent_growth_signals": [],
        "potential_gtm_opportunity": _unavailable("no research evidence"),
        "decision_makers": [],
        "contact_information": _unavailable("only shown when an authorized provider returns it"),
    }

    dropped: list[dict[str, Any]] = []

    def checked(label: str, raw_field, sensitive: bool = False) -> Field:
        built = build_field(raw_field, by_id, sensitive=sensitive)
        has_value = raw_field.value not in (None, "", [], {})
        if has_value and built.status == Status.UNAVAILABLE:
            dropped.append({"field": label, "claimed_value": raw_field.value, "reason": built.note})
        return built

    if evidence and synthesize_fn is not None:
        try:
            raw: RawReport = await synthesize_fn(evidence, name, domain, req.objective)
            fields["company_description"] = checked("company_description", raw.company_description)
            fields["industry"] = checked("industry", raw.industry)
            fields["target_market"] = checked("target_market", raw.target_market)
            fields["employee_size"] = checked("employee_size", raw.employee_size, sensitive=True)
            fields["potential_gtm_opportunity"] = checked("potential_gtm_opportunity", raw.potential_gtm_opportunity)
            fields["recent_growth_signals"] = [f for f in (checked("recent_growth_signals", r) for r in raw.recent_growth_signals) if f.status != Status.UNAVAILABLE]
            fields["decision_makers"] = [f for f in (checked("decision_makers", r, sensitive=True) for r in raw.decision_makers) if f.status != Status.UNAVAILABLE]
            if dropped:
                warnings.append(f"{len(dropped)} claim(s) were dropped because their supporting quote could not be verified: " + ", ".join(sorted({d["field"] for d in dropped})) + ".")
            if not name:
                cn = build_field(raw.company_name, by_id)
                if cn.status != Status.UNAVAILABLE:
                    fields["company_name"] = cn
            providers.append(ProviderStatus(name="groq", state="ok"))
        except Exception as exc:
            providers.append(ProviderStatus(name="groq", state="error", message=str(exc)[:200]))
            warnings.append("Summarization failed. Showing evidence only, so most fields are unavailable.")
    elif evidence:
        providers.append(ProviderStatus(name="groq", state="skipped", message="GROQ_API_KEY not configured"))
        warnings.append("Summarization skipped because no Groq key is configured. Showing evidence only.")
    else:
        providers.append(ProviderStatus(name="groq", state="skipped", message="no evidence to summarize"))

    mock_block: Optional[dict[str, Any]] = None
    if enr_res is not None:
        if enr_res.state == "mock":
            mock_block = {
                "label": "MOCK SAMPLE DATA, NOT REAL",
                "people": [p.__dict__ for p in enr_res.people],
                "company": enr_res.company.__dict__ if enr_res.company else None,
            }
            warnings.append("Enrichment is mock sample data and is not used in the report fields.")
        elif enr_res.state == "skipped":
            pass  # shown in the provider status only
        else:
            _merge_enrichment(fields, enr_res, warnings)
            warnings.extend(enr_res.warnings)

    urls: list[str] = []
    for e in evidence:
        if e.url not in urls:
            urls.append(e.url)

    return Report(
        company_name=fields["company_name"],
        website_domain=fields["website_domain"],
        company_description=fields["company_description"],
        industry=fields["industry"],
        target_market=fields["target_market"],
        employee_size=fields["employee_size"],
        recent_growth_signals=fields["recent_growth_signals"],
        potential_gtm_opportunity=fields["potential_gtm_opportunity"],
        decision_makers=fields["decision_makers"],
        contact_information=fields["contact_information"],
        source_urls=urls,
        providers=providers,
        warnings=list(dict.fromkeys(warnings)),
        mock_enrichment=mock_block,
        dropped_claims=dropped,
        evidence=evidence,
    )
