"""사전협의 요청서(별지 1 + 사업기획 자체점검표 + 유사중복 자체점검표 + 사업설명서) 파서.

HWP 에서 추출한 평문을 항목별 구간으로 나눈다. 체크박스 상태는 추출 과정에서
유실될 수 있으므로 각 항목의 원문 줄을 그대로 보존하고, 해석은 생성 단계(LLM)에 맡긴다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, fields

from .hwp import clean_lines, extract_text

_PHONE = re.compile(r"0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}")
_EMAIL = re.compile(r"[\w.+-]+@\s*[\w-]+(?:\.[\w-]+)+")


@dataclass
class RequestForm:
    """사전협의 요청서의 항목별 원문."""

    신청기관: str = ""
    신청부서: str = ""
    요청사유: str = ""  # 세부사업 신설 / 내역사업 신설 / 내내역사업 신설 / 사업내용 변경
    사업명: str = ""  # (세부사업) … (내역사업) … (내내역사업) …
    사업개요: str = ""
    타제도협의: str = ""
    이전협의: str = ""
    # 사업기획 자체점검표
    추진근거: str = ""
    추진사유: str = ""
    정책목적: str = ""
    성과지표: str = ""
    정책분야: str = ""
    지원대상: str = ""
    지원내용: str = ""
    지원규모: str = ""
    시행방법: str = ""
    사업제도연계: str = ""
    # 유사중복 자체점검표
    유사중복_점검내용: str = ""
    # 첨부 사업설명서 등 나머지 전부
    사업설명서: str = ""
    raw_text: str = field(default="", repr=False)

    def is_empty(self) -> bool:
        return not any(getattr(self, f.name) for f in fields(self) if f.name not in ("raw_text", "사업설명서"))

    def to_prompt_text(self, max_attachment_chars: int = 12000) -> str:
        """LLM 입력용 정리본."""
        parts = ["# 사전협의 요청서"]
        order = [
            ("신청기관", self.신청기관), ("신청부서", self.신청부서), ("사전협의 요청사유", self.요청사유),
            ("사업명", self.사업명), ("사업개요", self.사업개요), ("타 제도 협의·심사여부", self.타제도협의),
            ("이전년도 협의신청여부", self.이전협의),
        ]
        for k, v in order:
            if v:
                parts.append(f"## {k}\n{v}")
        parts.append("# 사업기획 자체점검표")
        for k in ("추진근거", "추진사유", "정책목적", "성과지표", "정책분야", "지원대상", "지원내용", "지원규모", "시행방법", "사업제도연계"):
            v = getattr(self, k)
            if v:
                parts.append(f"## {k}\n{v}")
        if self.유사중복_점검내용:
            parts.append(f"# 유사중복 자체점검표\n## 점검내용\n{self.유사중복_점검내용}")
        if self.사업설명서:
            body = self.사업설명서
            if len(body) > max_attachment_chars:
                body = body[:max_attachment_chars] + "\n…(이하 생략)"
            parts.append(f"# 첨부: 사업설명서 등\n{body}")
        return "\n\n".join(parts)


def redact_contacts(text: str) -> str:
    """전화번호·이메일을 가린다 (프롬프트·예시 파일에 개인정보가 남지 않도록)."""
    text = _EMAIL.sub("[이메일]", text)
    text = _PHONE.sub("[연락처]", text)
    return text


# ---------------------------------------------------------------------------
# 구간 탐지
# ---------------------------------------------------------------------------

_PUA = re.compile("[-]")
_LEAD_SYMBOLS = re.compile(r"^[\s　□■☑☐○●◇◆▪▫•·\-–—※☆★\[\]【】]+")


def _norm(s: str) -> str:
    """공백·사용자 정의 영역 글머리표(U+F0xx)·장식 기호를 제거한 비교용 문자열."""
    s = _PUA.sub("", s)
    s = _LEAD_SYMBOLS.sub("", s)
    return re.sub(r"[\s　]", "", s)


def _find(lines: list[str], pattern: str, start: int = 0, end: int | None = None) -> int:
    rx = re.compile(pattern)
    end = len(lines) if end is None else end
    for i in range(start, end):
        if rx.search(_norm(lines[i])):
            return i
    return -1


def _find_label(lines: list[str], label: str, start: int, end: int) -> tuple[int, int]:
    """한 줄 또는 두 줄에 걸쳐 쓰인 라벨('추진'/'근거')의 (시작, 값 시작) 위치."""
    target = _norm(label)
    for i in range(start, end):
        a = _norm(lines[i])
        if a == target:
            return i, i + 1
        if i + 1 < end and a and a + _norm(lines[i + 1]) == target:
            return i, i + 2
    return -1, -1


def _join(lines: list[str]) -> str:
    return "\n".join(l for l in lines if l.strip()).strip()


def _slice_between(lines: list[str], start_pat: str, stop_pats: list[str], lo: int, hi: int) -> tuple[str, int]:
    """start_pat 라벨 다음 줄부터 stop_pats 중 하나를 만나기 전까지를 돌려준다."""
    s = _find(lines, start_pat, lo, hi)
    if s < 0:
        return "", lo
    e = hi
    for p in stop_pats:
        j = _find(lines, p, s + 1, hi)
        if j >= 0:
            e = min(e, j)
    return _join(lines[s + 1 : e]), e


_CHECKLIST_LABELS = [
    ("추진근거", "추진근거"),
    ("추진사유", "추진사유"),
    ("정책목적", "정책목적"),
    ("성과지표", "성과지표"),
    ("정책분야", "정책분야"),
    ("지원대상", "지원대상"),
    ("지원내용", "지원내용"),
    ("지원규모", "지원규모"),
    ("시행방법", "시행방법"),
    ("사업제도연계", "사업·제도연계"),
]


def parse_request_lines(lines: list[str]) -> RequestForm:
    rf = RequestForm()
    n = len(lines)

    # 1) 큰 구간 경계
    i_form = _find(lines, r"^중소기업지원사업사전협의요청서$")
    i_check = _find(lines, r"^사업기획자체점검표$", max(i_form, 0))
    i_dup = _find(lines, r"^유사중복자체점검표$", max(i_check, 0))
    # 유사중복 자체점검표 뒤에는 '[지원분야 분류 기준]' 안내표 또는 '참고2. 사업설명서' 가 온다
    cands = [
        _find(lines, pat, max(i_dup, i_check, 0) + 1)
        for pat in (r"^참고2", r"^지원분야분류기준", r"^협의사업사업설명서", r"사업설명서$")
    ]
    cands = [c for c in cands if c >= 0]
    i_ref2 = min(cands) if cands else -1
    form_hi = i_check if i_check >= 0 else (i_dup if i_dup >= 0 else n)
    check_hi = i_dup if i_dup >= 0 else (i_ref2 if i_ref2 >= 0 else n)
    dup_hi = i_ref2 if i_ref2 >= 0 else n

    # 2) 별지1 본문
    lo = i_form + 1 if i_form >= 0 else 0
    rf.신청기관, _ = _slice_between(lines, r"^신청기관$", [r"^신청부서$", r"^사전협의요청사유$"], lo, form_hi)
    rf.신청부서, _ = _slice_between(lines, r"^신청부서$", [r"^사전협의요청사유$"], lo, form_hi)
    rf.요청사유, _ = _slice_between(lines, r"^사전협의요청사유$", [r"^사업명$"], lo, form_hi)
    rf.사업명, _ = _slice_between(lines, r"^사업명$", [r"^사업개요$"], lo, form_hi)
    rf.사업개요, _ = _slice_between(lines, r"^사업개요$", [r"^타제도협의", r"^이전년도", r"^사업담당자"], lo, form_hi)
    rf.타제도협의, _ = _slice_between(lines, r"^타제도협의", [r"^이전년도", r"^사업담당자"], lo, form_hi)
    rf.타제도협의 = _strip_table_heads(rf.타제도협의, ["(해당 시)", "제 도 명", "제도명", "협의부처", "협의일시", "협의결과"])
    rf.이전협의, _ = _slice_between(lines, r"^이전년도", [r"^사업담당자", r"^필수첨부"], lo, form_hi)
    rf.이전협의 = _strip_table_heads(rf.이전협의, ["협의신청여부", "(해당 시)"])

    # 3) 사업기획 자체점검표
    if i_check >= 0:
        bounds: list[tuple[str, int, int]] = []
        cursor = i_check + 1
        for attr, label in _CHECKLIST_LABELS:
            s, v = _find_label(lines, label, cursor, check_hi)
            if s < 0:
                continue
            bounds.append((attr, s, v))
            cursor = v
        for k, (attr, s, v) in enumerate(bounds):
            e = bounds[k + 1][1] if k + 1 < len(bounds) else check_hi
            setattr(rf, attr, _join(lines[v:e]))

    # 4) 유사중복 자체점검표 — '점검 내용' 이후만 취함
    if i_dup >= 0:
        s, v = _find_label(lines, "점검내용", i_dup + 1, dup_hi)
        if s >= 0:
            rf.유사중복_점검내용 = _join(lines[v:dup_hi])
        else:
            rf.유사중복_점검내용 = _join(lines[i_dup + 1 : dup_hi])
        rf.유사중복_점검내용 = _drop_boilerplate(rf.유사중복_점검내용)

    # 5) 첨부 사업설명서
    if i_ref2 >= 0:
        rf.사업설명서 = _join(lines[i_ref2:])

    return rf


def _strip_table_heads(text: str, heads: list[str]) -> str:
    keep = [l for l in text.splitlines() if _norm(l) not in {_norm(h) for h in heads}]
    return _join(keep)


_BOILERPLATE = (
    "공고정보자료집",
    "사업유사성 자체 점검내용 기재",
    "별도의 유사중복 검토를 실시한 경우",
    "필요 시 유사중복점검표 활용",
    "사업유사성이 없는 경우",
    "사업유사성이 있는 경우",
    "협의사업은 수출(판로지원) 사업으로",
    "유사중복성 완화계획 제시",
)


def _drop_boilerplate(text: str) -> str:
    """양식에 인쇄된 작성 안내문(예시 문장)을 제거한다."""
    keep = [l for l in text.splitlines() if not any(b in l for b in _BOILERPLATE)]
    return _join(keep)


def parse_request_text(text: str) -> RequestForm:
    lines = clean_lines(text)
    rf = parse_request_lines(lines)
    rf.raw_text = "\n".join(lines)
    return rf


def parse_request_file(path) -> RequestForm:
    return parse_request_text(extract_text(path))
