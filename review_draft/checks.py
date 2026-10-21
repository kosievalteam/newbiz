"""검토의견서 JSON 의 개조식 논리 정합성·표현 자동 점검.

생성 결과(모델 또는 사람이 쓴 JSON)를 발송 전에 기계적으로 걸러낼 수 있는 항목만 다룬다.
헤드라인–dash 라벨 대응, 요약표–헤드라인 결론 대응, 권고↔개선의견 대응, 각주 표시, 금칙 표현 등.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import AxisOpinion, ReviewOpinion

# 평가축별 헤드라인에 등장하는 영역 단어와, 그에 대응해야 하는 dash 라벨 키워드
_AREAS = {
    "validity": {"법적근거": ["법적근거"], "상위정책": ["상위정책"], "정책수요": ["정책수요"], "성과지표": ["사업성과", "성과지표"]},
    "suitability": {"지원내용": ["지원내용", "사업내용"], "지원대상": ["지원대상"], "지원규모": ["지원규모", "사업규모"], "수행체계": ["수행체계", "수행기관"]},
    "duplication": {"사업목적": ["사업목적"], "지원대상": ["지원대상"], "지원내용": ["지원내용"], "지원방식": ["지원방식"]},
}
_EXEMPT_LABELS = {"사업성격", "사업 성격", "성격", "근거", "법적근거·상위정책", "법적근거·상위정책"}

_FORBIDDEN = {
    "미흡함": "보완이 요구됨", "한계가 있음": "보완이 요구됨", "확인할 수 없": "자료 보강이 요구됨",
    "판단할 수 없": "자료 보강이 요구됨", "마중물": "초기 재원·핵심 동력", "양호한": "적정한 수준",
    "우수하다고 평가": "인정됨", "필요성 제시": "필요성 인정", "시장실패": "민간투자 위축 가능성",
    "산업통상자원부": "산업통상부(’25.10. 개편)", "특허청": "지식재산처(’25.10. 개편)",
}
# 정도만 흐리는 유사성 표현: 겹치는 축(사업목적·지원대상·지원내용·지원방식)이나 영역을 적시해야 한다
_VAGUE_SIMILARITY = re.compile(r"(일부|부분적으로|부분적인|다소|어느 정도|약간)\s*(유사|중첩|중복|겹치)")
_OLD_YEAR = re.compile(r"[‘']\d{2}년")  # 왼쪽 따옴표·일반 따옴표 연도 표기
_SENT_MAX = 78  # 한 문장(한 줄) 최대 글자 수. 본문 모든 줄에 적용


@dataclass
class Finding:
    level: str  # "error" | "warn"
    where: str
    message: str

    def __str__(self) -> str:
        tag = "오류" if self.level == "error" else "주의"
        return f"[{tag}] {self.where}: {self.message}"


def _all_dashes(ax: AxisOpinion):
    out = list(ax.dashes)
    for g in ax.dash_groups:
        out.extend(g)
    return out


def _axis_checks(name: str, title: str, ax: AxisOpinion, verdict: str, findings: list[Finding]):
    head = ax.headline.replace(" ", "")
    is_recommend = "권고" in head
    if is_recommend and verdict != "권고":
        findings.append(Finding("error", title, "헤드라인은 ‘권고안 제시’인데 요약표는 ‘동의’"))
    if not is_recommend and verdict == "권고":
        findings.append(Finding("error", title, "요약표는 ‘권고’인데 헤드라인에 ‘권고안 제시’가 없음"))
    if "동의" not in head and "권고" not in head:
        findings.append(Finding("error", title, "헤드라인에 결론(“원안 동의” / “권고안 제시”)이 없음"))

    dashes = _all_dashes(ax)
    labels = [d.label.replace(" ", "") for d in dashes if d.label]
    areas = _AREAS[name]
    # 헤드라인 영역 → dash 라벨
    for area, keys in areas.items():
        if area in head and not any(any(k in l for k in keys) for l in labels):
            findings.append(Finding("error", title, f"헤드라인에 ‘{area}’이(가) 있으나 대응하는 dash 라벨이 없음"))
    # dash 라벨 → 헤드라인 영역
    for l in labels:
        if l in _EXEMPT_LABELS:
            continue
        matched = [area for area, keys in areas.items() if any(k in l for k in keys)]
        if matched and not any(area in head for area in matched):
            findings.append(Finding("warn", title, f"dash 라벨 ‘({l})’이 헤드라인의 평가 영역에 없음"))
        if not matched and name != "duplication":
            findings.append(Finding("warn", title, f"표준 라벨이 아닌 dash 라벨 ‘({l})’"))
    if ax.group_labels and len(ax.group_labels) != len(ax.dash_groups):
        findings.append(Finding("error", title, "group_labels 와 dash_groups 의 개수가 다름"))
    if not dashes:
        findings.append(Finding("error", title, "dash 항목이 없음"))
    # 각주 표시(*) 와 notes 개수
    for d in dashes:
        stars = len(re.findall(r"(?<![*(])\*+(?!\))", d.text))
        if stars and len(d.notes) < stars:
            findings.append(Finding("warn", f"{title} ({d.label})", f"본문에 각주 표시 {stars}개, 각주 {len(d.notes)}개"))
        if not stars and d.notes and name != "duplication":
            findings.append(Finding("warn", f"{title} ({d.label})", "각주는 있으나 본문에 * 표시가 없음"))
        if d.text.rstrip().endswith(("다.", "음.", "함.", ".")):
            findings.append(Finding("warn", f"{title} ({d.label})", "dash 끝에 마침표 사용 (개조식 무종결 원칙)"))


def _text_checks(op: ReviewOpinion, findings: list[Finding]):
    def walk(obj, path):
        if isinstance(obj, str):
            for bad, good in _FORBIDDEN.items():
                if bad in obj:
                    findings.append(Finding("warn", path, f"회피 표현 ‘{bad}’ → ‘{good}’"))
            if _OLD_YEAR.search(obj):
                findings.append(Finding("warn", path, "연도 표기는 오른쪽 작은따옴표(’27년) 사용"))
            m = _VAGUE_SIMILARITY.search(obj)
            if m:
                findings.append(Finding("warn", path, f"정도만 흐리는 표현 ‘{m.group(0)}’ → 겹치는 축(사업목적·지원대상·지원내용·지원방식)이나 영역을 적시"))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if k == "reviewer_notes":
                    continue
                walk(v, f"{path}.{k}" if path else k)

    walk(op.model_dump(), "")


def check_opinion(op: ReviewOpinion) -> list[Finding]:
    f: list[Finding] = []
    s = op.summary
    axes = [("validity", "사업 타당성", op.validity, s.사업타당성), ("suitability", "사업 적합성", op.suitability, s.사업적합성),
            ("duplication", "유사·중복성", op.duplication, s.유사중복성)]
    for name, title, ax, verdict in axes:
        _axis_checks(name, title, ax, verdict, f)

    any_rec = any(v == "권고" for v in (s.사업타당성, s.사업적합성, s.유사중복성))
    if any_rec and s.종합의견 != "권고":
        f.append(Finding("error", "검토의견 요약", "세부 평가축에 ‘권고’가 있으면 종합의견도 ‘권고’"))
    if not any_rec and s.종합의견 != "동의":
        f.append(Finding("error", "검토의견 요약", "세 평가축 모두 ‘동의’이면 종합의견도 ‘동의’"))

    imp_text = " ".join(i.headline + " " + " ".join(d.text for d in i.dashes) for i in op.improvements)
    if any_rec and (not op.improvements or "해당없음" in imp_text.replace(" ", "")):
        f.append(Finding("error", "개선의견", "권고 항목이 있는데 개선의견이 비어 있거나 ‘해당 없음’"))
    if not any_rec and op.improvements and "해당없음" not in imp_text.replace(" ", ""):
        f.append(Finding("warn", "개선의견", "모두 동의인데 개선의견이 있음 (‘해당 없음’ 또는 요약표 재확인)"))
    if s.유사중복성 == "권고" and "중복" not in imp_text:
        f.append(Finding("warn", "개선의견", "유사·중복성 권고인데 개선의견에 중복수혜 방지 항목이 없음"))
    if s.유사중복성 == "권고" and not op.similar_programs:
        f.append(Finding("warn", "유사중복검토 사업", "유사·중복성 권고인데 유사중복검토 사업 표가 비어 있음"))

    # 사업 적합성은 지원대상·지원내용·지원규모·수행체계를 모두 검토한다
    suit_labels = [d.label.replace(" ", "") for d in _all_dashes(op.suitability) if d.label]
    for area, keys in _AREAS["suitability"].items():
        if not any(any(k in l for k in keys) for l in suit_labels):
            f.append(Finding("error", "사업 적합성", f"‘{area}’ dash 가 없음 (지원대상·지원내용·지원규모·수행체계는 모두 검토)"))
        if area not in op.suitability.headline.replace(" ", ""):
            f.append(Finding("error", "사업 적합성", f"헤드라인에 ‘{area}’ 영역이 없음 (네 영역의 판단을 모두 적시)"))
    cb = " ".join(op.check_box.lines).replace(" ", "")
    for area, keys in _AREAS["suitability"].items():
        if not any(k in cb for k in keys):
            f.append(Finding("error", "사업내용 점검", f"점검 박스에 ‘{area}’ 판정이 없음"))
    if s.사업적합성 == "권고" and "권고" not in cb:
        f.append(Finding("error", "사업내용 점검", "사업 적합성 권고인데 점검 박스에 ‘권고안 제시’가 없음"))
    if s.사업적합성 == "동의" and "권고" in cb:
        f.append(Finding("error", "사업내용 점검", "사업 적합성 동의인데 점검 박스에 ‘권고안 제시’가 있음"))

    tables = op.comparison_tables()
    for ti, t in enumerate(tables):
        ncol = len(t.columns) + 1
        where = "사업간 비교표" + (f"[{ti + 1}]" if len(tables) > 1 else "")
        for i, row in enumerate(t.rows):
            if len(row) != ncol:
                f.append(Finding("error", where, f"{i + 1}번째 행의 칸 수({len(row)})가 열 수({ncol})와 다름"))
    _comparison_coverage(op, f)
    if not op.overview.검토자:
        f.append(Finding("warn", "개요", "검토자 미기재"))
    if "/" not in op.overview.사업명:
        f.append(Finding("warn", "개요", "사업명에 요청사유(‘/ 세부사업 신설’ 등)가 없음"))

    _text_checks(op, f)
    _length_checks(op, f)
    return f


def _cited_programs(op: ReviewOpinion) -> list[str]:
    """본문에 언급된 기존사업명: ※ 유사중복검토 사업 표 + 유사·중복성 각주의 '(사업명, 부처)' 표기."""
    names: list[str] = []
    for sp in op.similar_programs:
        names += _leaf_names(sp.사업명)
    for d in _all_dashes(op.duplication):
        for n in d.notes:
            for line in str(n).split("\n"):
                line = line.strip()
                if not line.startswith("("):
                    continue
                depth, end = 0, -1
                for i, ch in enumerate(line):
                    depth += (ch == "(") - (ch == ")")
                    if depth == 0:
                        end = i
                        break
                if end < 0:
                    continue
                inner = line[1:end]
                if ", " not in inner:
                    continue
                names += _leaf_names(inner.rsplit(", ", 1)[0])
    out: list[str] = []
    for n in names:
        if n and n not in out:
            out.append(n)
    return out


def _leaf_names(path: str) -> list[str]:
    """'세부 > 내역 > 내내역(비고)' 또는 'A·B' 에서 비교표 열과 대조할 이름들."""
    leaf = path.split(">")[-1]
    leaf = re.sub(r"\([^()]*\)", "", leaf)  # 괄호 비고 제거
    leaf = re.sub(r"\s*(등|및)\s*$", "", leaf.strip())
    parts = [re.sub(r"\s+", "", x) for x in leaf.split("·") if x.strip()]
    # 사업명이 아닌 수치·연도 표기(예: '’26년 72백만원')는 제외
    return [x for x in parts if len(x) >= 4 and not re.search(r"백만원|[’']\d\d년|^\d|%", x)]


def _comparison_coverage(op: ReviewOpinion, findings: list[Finding]):
    """본문(유사중복검토 사업 표, 유사·중복성 각주)에 언급한 기존사업은 모두 비교표의 열에 있어야 한다."""
    cols = " ".join(c for t in op.comparison_tables() for c in t.columns).replace(" ", "")
    cols_norm = cols.replace("사업", "")
    for name in _cited_programs(op):
        key = name.replace("사업", "")
        if key and key not in cols_norm:
            findings.append(Finding("error", "사업간 비교표", f"본문에 언급한 기존사업 ‘{name}’이(가) 비교표 열에 없음"))


def _length_checks(op: ReviewOpinion, findings: list[Finding]):
    """본문에 출력되는 모든 줄(헤드라인·dash·각주·비고·박스·표 셀)은 한 줄 _SENT_MAX 자를 넘지 않는다."""
    skip = {"reviewer_notes", "similarity"}

    def walk(obj, path):
        if isinstance(obj, str):
            for line in obj.split("\n"):
                if len(line) > _SENT_MAX:
                    findings.append(Finding("error", path, f"한 줄 {len(line)}자 (최대 {_SENT_MAX}자): {line[:30]}…"))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if k in skip:
                    continue
                walk(v, f"{path}.{k}" if path else k)

    walk(op.model_dump(), "")
