"""Claude API 를 호출해 검토의견서 JSON 을 생성한다."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from importlib import resources

from .exemplars import load_bundled_exemplars, load_exemplar_dir
from .request_parser import RequestForm
from .schema import ReviewOpinion, strict_schema

DEFAULT_MODEL = os.environ.get("REVIEW_DRAFT_MODEL", "claude-opus-5-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class GenerationResult:
    opinion: ReviewOpinion
    raw_json: str
    model: str
    usage: dict


def load_system_prompt() -> str:
    return (resources.files("review_draft") / "prompts" / "system.md").read_text(encoding="utf-8")


def build_system_blocks(exemplar_dir: str | None = None, max_exemplars: int = 6) -> list[dict]:
    """시스템 프롬프트 블록: [작성 규칙] + [예시들]. 마지막 블록에 캐시 지점을 둔다."""
    rules = load_system_prompt()
    exemplars = load_exemplar_dir(exemplar_dir) if exemplar_dir else load_bundled_exemplars()
    exemplars = exemplars[:max_exemplars]
    ex_text = ["# 작성 예시\n\n아래는 실제 회람된 검토의견서들이다. 문체·위계·판단어휘·비교표 구성을 그대로 따른다."]
    for name, body in exemplars:
        ex_text.append(f"---\n### 예시 {name}\n\n{body}")
    return [
        {"type": "text", "text": rules},
        {"type": "text", "text": "\n\n".join(ex_text), "cache_control": {"type": "ephemeral"}},
    ]


def build_user_message(rf: RequestForm, reviewer: str = "", extra_context: str = "", consult_no: str = "") -> str:
    parts = []
    meta = []
    if consult_no:
        meta.append(f"- 협의번호: {consult_no}")
    if reviewer:
        meta.append(f"- 검토자: {reviewer}")
    if meta:
        parts.append("# 검토 메타정보\n" + "\n".join(meta))
    parts.append(rf.to_prompt_text())
    if extra_context:
        parts.append("# 참고자료 (검토자 제공)\n" + extra_context)
    parts.append(
        "위 사전협의 요청서를 검토하여 검토의견서를 JSON 으로 작성하라. "
        "overview.사업명 은 '협의번호. 사업명 / 요청사유' 형식으로 쓰되 협의번호가 없으면 '사업명 / 요청사유' 로 쓴다."
    )
    return "\n\n".join(parts)


def generate(
    rf: RequestForm,
    *,
    model: str = DEFAULT_MODEL,
    reviewer: str = "",
    consult_no: str = "",
    extra_context: str = "",
    exemplar_dir: str | None = None,
    effort: str = "high",
    max_tokens: int = 32000,
    use_fallback: bool = True,
    client=None,
) -> GenerationResult:
    """요청서 → ReviewOpinion. 스트리밍 + structured output 으로 JSON 을 받는다."""
    import anthropic

    client = client or anthropic.Anthropic()
    schema = strict_schema(ReviewOpinion)
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=build_system_blocks(exemplar_dir),
        messages=[{"role": "user", "content": build_user_message(rf, reviewer, extra_context, consult_no)}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )
    if use_fallback:
        kwargs["betas"] = [FALLBACK_BETA]
        kwargs["fallbacks"] = "default"

    with client.beta.messages.stream(**kwargs) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise RuntimeError("모델이 요청을 거부했습니다 (stop_reason=refusal). 입력 내용을 확인하세요.")
    if message.stop_reason == "max_tokens":
        raise RuntimeError("출력이 max_tokens 에서 잘렸습니다. --max-tokens 를 늘려 다시 실행하세요.")

    text = next((b.text for b in message.content if getattr(b, "type", "") == "text"), "")
    if not text:
        raise RuntimeError("모델 응답에 텍스트 블록이 없습니다.")
    opinion = ReviewOpinion.model_validate_json(text)
    usage = message.usage.model_dump() if hasattr(message.usage, "model_dump") else {}
    return GenerationResult(opinion=opinion, raw_json=json.dumps(json.loads(text), ensure_ascii=False, indent=2), model=message.model, usage=usage)
