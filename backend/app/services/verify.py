from __future__ import annotations

import json
import re
from typing import Any, Optional

from pydantic import BaseModel, Field as PField

from app.schemas import Evidence, Field, Source, Status


class RawField(BaseModel):
    """One claim as returned by the LLM, before verification."""

    value: Any = None
    evidence_ids: list[str] = PField(default_factory=list)
    quote: Optional[str] = None
    basis: str = "stated"  # stated or inferred


class RawReport(BaseModel):
    company_name: RawField = PField(default_factory=RawField)
    company_description: RawField = PField(default_factory=RawField)
    industry: RawField = PField(default_factory=RawField)
    target_market: RawField = PField(default_factory=RawField)
    employee_size: RawField = PField(default_factory=RawField)
    recent_growth_signals: list[RawField] = PField(default_factory=list)
    potential_gtm_opportunity: RawField = PField(default_factory=RawField)
    decision_makers: list[RawField] = PField(default_factory=list)


def _norm(text: str) -> str:
    """Lowercase and keep only letters and digits as single-space separated words.

    Ignores markdown bullets, table pipes, curly quotes and spacing so a faithful quote is not rejected,
    while still requiring every word to appear in the same order in the source."""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def quote_in_evidence(quote: Optional[str], evidence: list[Evidence]) -> bool:
    """True if the quote appears in a cited snippet. A quote may use ... to skip text, then each part must appear in order."""
    if not quote or len(quote.strip()) < 8:
        return False
    parts = [p for p in re.split(r"\.{3}|…", quote) if len(_norm(p)) >= 8]
    if not parts:
        return False
    for e in evidence:
        hay = _norm(e.highlight)
        pos = 0
        for part in parts:
            idx = hay.find(_norm(part), pos)
            if idx == -1:
                break
            pos = idx + len(_norm(part))
        else:
            return True
    return False


def _source(e: Evidence, quote: Optional[str]) -> Source:
    return Source(url=e.url, title=e.title, published_date=e.published_date, quote=quote)


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUM.findall(text)}


def unsupported_numbers(value: Any, cited: list[Evidence]) -> list[str]:
    """Numbers (counts, years, dates, amounts) in the claimed value that appear nowhere in the cited sources.

    The quote check proves the quote exists, but the value could still add a detail the source never said.
    Source text, title and publication date all count as support."""
    vtext = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    hay: set[str] = set()
    for e in cited:
        hay |= _numbers(f"{e.highlight} {e.title or ''} {e.published_date or ''}")
    return sorted(n for n in _numbers(vtext) if n not in hay)


def build_field(raw: RawField, evidence_by_id: dict[str, Evidence], sensitive: bool = False) -> Field:
    """Turn an LLM claim into a Field with an honest status.

    stated + quote found in a cited source -> verified
    stated + quote missing                 -> unavailable
    inferred + at least one valid citation -> inferred (never for sensitive fields)
    anything without a valid citation      -> unavailable
    """
    value = raw.value
    if value is None or (isinstance(value, str) and not value.strip()):
        return Field(status=Status.UNAVAILABLE, note="no supporting source found")
    cited = [evidence_by_id[i] for i in raw.evidence_ids if i in evidence_by_id]
    if not cited:
        return Field(status=Status.UNAVAILABLE, note="claim had no valid source, so it was dropped")
    if raw.basis == "stated":
        if quote_in_evidence(raw.quote, cited):
            extra = unsupported_numbers(value, cited)
            if extra and sensitive:
                return Field(status=Status.UNAVAILABLE, note=f"value contained figures not found in the source ({', '.join(extra)}), so it was dropped")
            if extra:
                return Field(value=value, status=Status.INFERRED, sources=[_source(e, raw.quote) for e in cited], note=f"quote found, but figures in the value are not in the source ({', '.join(extra)}); treat as unverified")
            return Field(value=value, status=Status.VERIFIED, sources=[_source(e, raw.quote) for e in cited])
        return Field(status=Status.UNAVAILABLE, note="supporting quote was not found in the cited source, so it was dropped")
    if sensitive:
        return Field(status=Status.UNAVAILABLE, note="this field is only shown when a source or provider states it")
    extra = unsupported_numbers(value, cited)
    note = "reasoned from the cited evidence" + (f"; figures not found in the sources: {', '.join(extra)}" if extra else "")
    return Field(value=value, status=Status.INFERRED, sources=[_source(e, None) for e in cited], note=note)
