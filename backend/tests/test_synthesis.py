import json

import httpx
import pytest

from app.config import Settings
from app.schemas import Evidence
from app.services import synthesis
from app.services.synthesis import SynthesisError, extract_json, synthesize

GOOD = {"company_description": {"value": "x", "evidence_ids": ["E1"], "quote": "some quote here", "basis": "stated"}}
EV = [Evidence(id="E1", url="https://a.com", highlight="some quote here")]
S = Settings(groq_api_key="k", _env_file=None)


def groq(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def reply(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_extract_json_handles_code_fences_and_prose():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Here you go: {"a": 1} done') == {"a": 1}


async def test_valid_json_parses():
    r = await synthesize(S, EV, "A", "a.com", None, client=groq(lambda req: reply(json.dumps(GOOD))))
    assert r.company_description.value == "x"


async def test_invalid_json_gets_one_repair_retry():
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        return reply("not json at all") if calls["n"] == 1 else reply(json.dumps(GOOD))

    r = await synthesize(S, EV, "A", "a.com", None, client=groq(h))
    assert calls["n"] == 2 and r.company_description.value == "x"


async def test_invalid_json_twice_raises():
    with pytest.raises(SynthesisError):
        await synthesize(S, EV, "A", "a.com", None, client=groq(lambda req: reply("nope")))


async def test_falls_back_when_model_rejects_json_mode():
    seen = []

    def h(req):
        body = json.loads(req.content)
        seen.append("response_format" in body)
        return httpx.Response(400) if "response_format" in body else reply(json.dumps(GOOD))

    r = await synthesize(S, EV, "A", "a.com", None, client=groq(h))
    assert seen == [True, False] and r.company_description.value == "x"


@pytest.mark.parametrize("code,word", [(429, "rate limit"), (401, "rejected"), (404, "retired")])
async def test_groq_errors_have_clear_messages(code, word):
    with pytest.raises(SynthesisError) as e:
        await synthesize(S, EV, "A", "a.com", None, client=groq(lambda req: httpx.Response(code)))
    assert word in str(e.value)
