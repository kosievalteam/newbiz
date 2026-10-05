"""API 호출 없이 generator 의 요청 구성과 응답 처리를 검증한다 (가짜 클라이언트)."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from review_draft.generator import FALLBACK_BETA, build_system_blocks, build_user_message, generate
from review_draft.request_parser import parse_request_text

FIX = Path(__file__).parent / "fixtures"


class _Stream:
    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.msg


class _FakeClient:
    def __init__(self, text, stop_reason="end_turn"):
        self.calls = []
        self._text = text
        self._stop = stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        msg = SimpleNamespace(
            stop_reason=self._stop,
            model=kwargs["model"],
            content=[SimpleNamespace(type="text", text=self._text)],
            usage=SimpleNamespace(model_dump=lambda: {"input_tokens": 1, "output_tokens": 2}),
        )
        return _Stream(msg)


def _rf():
    return parse_request_text((FIX / "request_sample.txt").read_text(encoding="utf-8"))


def test_system_blocks_have_rules_and_cached_exemplars():
    blocks = build_system_blocks()
    assert "검토의견서" in blocks[0]["text"]
    assert blocks[-1]["cache_control"] == {"type": "ephemeral"}
    assert "### 예시" in blocks[-1]["text"]


def test_user_message_includes_meta_and_form():
    m = build_user_message(_rf(), reviewer="OOO 연구원", consult_no="2026-999", extra_context="참고")
    assert "2026-999" in m and "OOO 연구원" in m and "# 사전협의 요청서" in m and "참고자료" in m


def test_generate_parses_json_and_sets_request_params():
    text = (FIX / "opinion_sample.json").read_text(encoding="utf-8")
    client = _FakeClient(text)
    res = generate(_rf(), client=client, model="claude-opus-5-5")
    assert res.opinion.summary.종합의견 == "권고"
    kw = client.calls[0]
    assert kw["betas"] == [FALLBACK_BETA] and kw["fallbacks"] == "default"
    assert kw["output_config"]["format"]["type"] == "json_schema"
    assert kw["output_config"]["effort"] == "high"
    assert json.loads(res.raw_json)["overview"]["사업명"].startswith("178.")


def test_generate_without_fallback():
    client = _FakeClient((FIX / "opinion_sample.json").read_text(encoding="utf-8"))
    generate(_rf(), client=client, use_fallback=False)
    assert "fallbacks" not in client.calls[0] and "betas" not in client.calls[0]


def test_generate_refusal_raises():
    client = _FakeClient("{}", stop_reason="refusal")
    with pytest.raises(RuntimeError, match="거부"):
        generate(_rf(), client=client)
