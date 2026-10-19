from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from app.config import Settings
from app.schemas import Evidence
from app.services.verify import RawReport

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class SynthesisError(Exception):
    pass


SYSTEM_PROMPT = """You are a careful B2B research analyst. You are given numbered evidence snippets from public web pages.
Use ONLY that evidence. Never use outside knowledge. Never guess.

Return one JSON object with these keys:
company_name, company_description, industry, target_market, employee_size, potential_gtm_opportunity (each is a claim object),
recent_growth_signals (list of claim objects), decision_makers (list of claim objects whose value is {"name": ..., "role": ...}).

A claim object is: {"value": ..., "evidence_ids": ["E1"], "quote": "...", "basis": "stated" or "inferred"}.
Rules:
- basis "stated": the evidence explicitly says it. quote MUST be copied word for word, contiguous, from a cited snippet.
- basis "inferred": you reasoned from evidence. List the evidence ids you relied on. quote may be null.
- potential_gtm_opportunity is always basis "inferred" and should relate to the research objective.
- employee_size and decision_makers: only if a snippet states them explicitly, otherwise value null / empty list.
- If the evidence does not support a field, use {"value": null, "evidence_ids": [], "quote": null, "basis": "stated"}.
- If a snippet gives a date or as-of year for a value (for example an employee count), keep it in the value, like "8,500 (2025)".
- recent_growth_signals: funding, hiring activity (open roles), expansion, product launches and notable customer wins. Include the date in the value when the snippet shows one. Prefer the most recent items. Each signal needs its own quote.
- target_market: who the company sells to (customer types, sizes, industries). Use basis "stated" only with a verbatim quote that literally names the customers; otherwise use basis "inferred" citing customer or product pages.
- decision_makers: list every founder or C-level or head-of person whose name AND title appear together in a snippet (one claim each, with a verbatim quote).
- Every number, date or amount in a value must appear in the cited snippet or in the source date. Do not add figures from memory.
- Quotes must be copied exactly, character for character, from one snippet. Do not merge or paraphrase. If you cannot quote it, use basis "inferred" or return null.
- Keep values short and factual. No marketing language."""


def build_user_prompt(evidence: list[Evidence], name: Optional[str], domain: Optional[str], objective: Optional[str]) -> str:
    lines = [f"Company: {name or 'unknown'}", f"Domain: {domain or 'unknown'}", f"Research objective: {objective or 'Evaluate whether this company could be a good prospect for a B2B GTM service.'}", "", "Evidence:"]
    for e in evidence:
        date = f" ({e.published_date[:10]})" if e.published_date else ""
        lines.append(f"[{e.id}] {e.title or e.url}{date}\nURL: {e.url}\nSnippet: {e.highlight[:1000]}")
    return "\n\n".join(lines)


async def _call_groq(settings: Settings, messages: list[dict[str, str]], client: Optional[httpx.AsyncClient], json_mode: bool = True) -> str:
    headers = {"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {"model": settings.groq_model, "messages": messages, "temperature": 0}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    owns = client is None
    c = client or httpx.AsyncClient(timeout=settings.groq_timeout_seconds)
    try:
        try:
            resp = await c.post(GROQ_URL, json=body, headers=headers, timeout=settings.groq_timeout_seconds)
        except httpx.TimeoutException:
            raise SynthesisError("Groq request timed out")
        except httpx.HTTPError as exc:
            raise SynthesisError(f"Groq network error: {exc.__class__.__name__}")
        if resp.status_code == 429:
            raise SynthesisError("Groq rate limit reached")
        if resp.status_code in (401, 403):
            raise SynthesisError("Groq rejected the key (check GROQ_API_KEY)")
        if resp.status_code == 400 and json_mode:
            # Some models reject response_format. Retry once without it and parse the text ourselves.
            return await _call_groq(settings, messages, c, json_mode=False)
        if resp.status_code == 404:
            raise SynthesisError(f"Groq model not found or retired: {settings.groq_model} (check GROQ_MODEL)")
        if resp.status_code >= 400:
            raise SynthesisError(f"Groq error HTTP {resp.status_code}")
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise SynthesisError("Groq response had an unexpected shape")
        if not content:
            raise SynthesisError("Groq returned an empty message")
        return content
    finally:
        if owns:
            await c.aclose()


def extract_json(text: str) -> Any:
    """Parse JSON, tolerating markdown code fences and text around the object."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned)
    except ValueError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def parse_raw_report(text: str) -> RawReport:
    return RawReport.model_validate(extract_json(text))


async def synthesize(
    settings: Settings,
    evidence: list[Evidence],
    name: Optional[str],
    domain: Optional[str],
    objective: Optional[str],
    client: Optional[httpx.AsyncClient] = None,
) -> RawReport:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(evidence, name, domain, objective)},
    ]
    content = await _call_groq(settings, messages, client)
    try:
        return parse_raw_report(content)
    except (ValueError, TypeError):
        messages += [
            {"role": "assistant", "content": content},
            {"role": "user", "content": "That was not valid JSON for the required schema. Return only the corrected JSON object."},
        ]
        content = await _call_groq(settings, messages, client)
        try:
            return parse_raw_report(content)
        except (ValueError, TypeError):
            raise SynthesisError("LLM returned invalid JSON twice")
