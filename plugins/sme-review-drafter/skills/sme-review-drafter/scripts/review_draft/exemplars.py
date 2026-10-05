"""작성 예시(exemplar) 관리.

기존 검토의견서(.hwp/.hwpx)에서 「검토의견」 부분과 「협의요청서」 부분을 분리해
개인정보(담당자 성명·연락처·이메일)를 가린 평문 예시로 저장한다. 생성 단계에서
이 예시들을 few-shot 으로 투입해 문체·위계·판단어휘를 학습시킨다.
"""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

from .hwp import clean_lines, extract_text
from .request_parser import parse_request_lines, redact_contacts

_REQUEST_TITLE = re.compile(r"중소기업지원사업\s*사전협의\s*요청서")
_REF1 = re.compile(r"^참고\s*1")


def split_review_and_request(lines: list[str]) -> tuple[list[str], list[str]]:
    """검토의견서 평문을 (검토의견 부분, 협의요청서 이하) 로 나눈다."""
    for i, line in enumerate(lines):
        if _REF1.search(line.strip()) or _REQUEST_TITLE.search(line):
            return lines[:i], lines[i:]
    return lines, []


_PERSON_LINE = re.compile(r"^\s*\d\.\s*(신청기관|검토자)\s*$")


def redact_review(lines: list[str]) -> list[str]:
    """개요 표의 담당자·검토자 인적사항을 가린다."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _PERSON_LINE.match(line)
        if m and i + 1 < len(lines):
            label = m.group(1)
            value = lines[i + 1]
            if label == "신청기관":
                value = value.split("/")[0].strip()
            else:
                value = "OOO 연구원"
            out.append(line)
            out.append(value)
            i += 2
            continue
        out.append(redact_contacts(line))
        i += 1
    return out


def build_exemplar(path: str | Path, max_attachment_chars: int = 3000) -> str:
    """검토의견서 파일 하나를 예시 마크다운으로 변환한다."""
    lines = clean_lines(extract_text(path))
    review, request = split_review_and_request(lines)
    review = redact_review(review)
    parts = ["## 입력: 사전협의 요청서 (요약)"]
    if request:
        rf = parse_request_lines(request)
        rf.사업설명서 = ""  # 예시에는 첨부 설명서를 싣지 않는다 (분량·개인정보)
        parts.append(redact_contacts(rf.to_prompt_text(max_attachment_chars=max_attachment_chars)))
    else:
        parts.append("(협의요청서 부분 없음)")
    parts.append("## 출력: 검토의견서")
    parts.append("\n".join(review))
    return "\n\n".join(parts)


def load_bundled_exemplars() -> list[tuple[str, str]]:
    """패키지에 포함된 예시 목록 [(이름, 본문)]."""
    out = []
    pkg = resources.files("review_draft") / "prompts" / "exemplars"
    for entry in sorted(pkg.iterdir(), key=lambda e: e.name):
        if entry.name.endswith(".md"):
            out.append((entry.name[:-3], entry.read_text(encoding="utf-8")))
    return out


def load_exemplar_dir(path: str | Path) -> list[tuple[str, str]]:
    out = []
    for p in sorted(Path(path).glob("*.md")):
        out.append((p.stem, p.read_text(encoding="utf-8")))
    return out
