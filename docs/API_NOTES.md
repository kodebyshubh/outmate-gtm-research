# API Notes

Fill in as you verify each service. Date each finding.

## Exa (https://exa.ai/docs)

- Endpoint used: POST https://api.exa.ai/search, header x-api-key.
- Request fields used: query, type ("auto"), numResults, contents {highlights: true}, includeDomains, startPublishedDate.
- Free tier (per Exa pricing docs, 18 Oct 2026): $10 credits, about 2,500 instant searches, resets monthly. Contents are billed per page and per content type.
- Rate limits: not listed on the pricing page for standard plans.
- Verified live on 18 Oct 2026 (smoke_live.py): the request shape above works. Response keys per result: id, title, url, highlights, image. publishedDate is present only when Exa has one (about 6 of 21 results in a Stripe run), so the code treats it as optional.
- Top-level response has costDollars (about $0.007 per search with highlights); the adapter sums it per report and shows it in the provider status. A report is about 5 searches, so the $10 free credit covers roughly 250 reports.
- Fixture saved at backend/tests/fixtures/exa_live_sample.json and used by a test.

## MoltSets (https://developer.moltsets.com)

Confirmed from public docs on 18 Oct 2026:
- Base URL https://api.moltsets.com/api/v1/tools
- Auth: Bearer token (ms_...). A non-empty User-Agent header is required or the API returns 403.
- Documented endpoint: POST /search_people. Filters include company_domain, company, title, seniority, department, industry, employee_range, country. limit default 10, max 25.
- Response: results (nested results list and total), status, metadata. A miss is HTTP 200 with status "not_found".
- Person fields: name, title, headline, seniority, location, industry, linkedin_url, business_email, nested company object. Verification metadata: business_email_risk_score, business_email_validated_at, last_updated_at, current_role_start_date.
- Errors: 429 variants (rate_limited, fair_use_limit_exceeded, fair_use_requests_exceeded, search_concurrency_exceeded) with Retry-After, 402 insufficient tokens, 403 tool not on plan.
- Free tier: concurrency 3. A one-time search trial is mentioned, size not stated.

Not confirmed:
- Company search and Get Company endpoints (no request or response details found).
- Free trial size and numeric fair-use quotas.
- Whether a free key can call search_people.
- Exact field names in the live response (the adapter accepts name, full_name or first_name plus last_name, and size, employee_range or employee_count).

TODO: sign up for the free tier, make one real search_people call by company_domain, save the response as a fixture, and record what happened (success, 402, 403).

## Groq (https://console.groq.com)

- Endpoint used: POST https://api.groq.com/openai/v1/chat/completions with response_format json_object.
- Model is set in GROQ_MODEL. llama-3.3-70b-versatile was shut down on 16 Aug 2026 (Groq deprecations page). Using openai/gpt-oss-120b, the recommended replacement; qwen/qwen3.6-27b is the other suggested one.
- Verified live on 18 Oct 2026: openai/gpt-oss-120b returns clean JSON with response_format json_object. A full Stripe report (about 21 snippets) completed without hitting rate limits; snippets are capped at 1000 characters each to stay inside free-tier token limits.
- Free tier has rate limits; a 429 is reported as a warning and the report falls back to evidence only.
