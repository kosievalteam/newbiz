"""ReviewOpinion → Markdown 렌더러 (빠른 검토·diff 용)."""

from __future__ import annotations

from .schema import AxisOpinion, Dash, ReviewOpinion


def _dash(d: Dash, indent="   ") -> list[str]:
    label = f"({d.label}) " if d.label else ""
    out = [f"{indent}- {label}{d.text}"]
    for i, n in enumerate(d.notes):
        out.append(f"{indent}  {'*' * (i + 1)} {n}")
    return out


def _axis(ax: AxisOpinion) -> list[str]:
    out = [f"○ {ax.headline}"]
    if ax.group_labels and ax.dash_groups:
        for label, group in zip(ax.group_labels, ax.dash_groups):
            out.append(f"  {label}")
            for d in group:
                out += _dash(d, indent="     ")
    for d in ax.dashes:
        out += _dash(d)
    for r in ax.remarks:
        out.append(f"   ※ {r}")
    return out


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    esc = lambda s: str(s).replace("|", "\\|").replace("\n", "<br>")
    out = ["| " + " | ".join(esc(h) for h in header) + " |", "|" + "---|" * len(header)]
    for r in rows:
        r = list(r) + [""] * (len(header) - len(r))
        out.append("| " + " | ".join(esc(c) for c in r[: len(header)]) + " |")
    return out


def render_md(op: ReviewOpinion) -> str:
    L: list[str] = []
    ov, ex, s = op.overview, op.extra_info, op.summary
    L += ["# 중소기업지원사업 사전협의 검토의견서", "", "## 1. 협의신청사업 및 검토의견 개요", "", "### □ 협의신청사업 개요", ""]
    L += _table(["항목", "내용"], [["1. 사업명", ov.사업명], ["2. 신청기관", ov.신청기관], ["3. 지원유형", ov.지원유형], ["4. 특이사항", ov.특이사항], ["5. 검토자", ov.검토자]])
    L += ["", "### □ 사업개요 추가정보", ""]
    L += _table(["항목", "내용"], [["1-1. 근거법령", ex.근거법령], ["1-2. 상위정책", ex.상위정책], ["1-3. 사업목적", ex.사업목적], ["2-1. 지원대상", ex.지원대상], ["2-2. 지원내용", ex.지원내용], ["2-3. 지원규모", ex.지원규모], ["2-4. 전달체계", ex.전달체계], ["3-1. 연계사업", ex.연계사업]])
    L += ["", "### □ 검토의견 요약", ""]
    L += _table(["1. 종합의견", "2. 사업타당성", "3. 사업적합성", "4. 유사중복성"], [[s.종합의견, s.사업타당성, s.사업적합성, s.유사중복성]])
    L += ["", "### ※ 유사중복검토 사업", ""]
    L += _table(["부처", "사업명", "검토의견"], [[p.부처, p.사업명, p.검토의견] for p in op.similar_programs] or [["-", "해당 없음", "-"]])
    L += ["", "## 2. 검토의견", "", "### 1. 종합의견", ""]
    L += _axis(op.validity) + [""]
    L += _axis(op.suitability) + [""]
    cb = op.content_box
    L += ["> **사업내용**", f"> ▪ (지원대상) {cb.지원대상}", f"> ▪ (추진내용) {cb.추진내용}"]
    L += [f">   - {x}" for x in cb.추진내용_세부]
    L += [f"> ▪ (지원규모) {cb.지원규모}"]
    L += [f">   - {x}" for x in cb.지원규모_세부]
    L += [f"> ▪ (수행기관) {cb.수행기관}", ">", "> ⇩", ">", "> **사업내용 점검**"]
    L += [f"> {x}" for x in op.check_box.lines]
    L += [""]
    L += _axis(op.duplication) + ["", "### 2. 개선의견", ""]
    for imp in op.improvements:
        L.append(f"○ {imp.headline}")
        for d in imp.dashes:
            L += _dash(d)
    L += ["", "### 〈 사업간 비교표 〉", ""]
    L += _table(["구 분"] + op.comparison.columns, op.comparison.rows)
    if op.similarity.candidates:
        L += ["", "### 〈 참고 〉 유사도 분석 결과 (상위 후보)", ""]
        if op.similarity.method:
            L.append(f"- 분석 기준: {op.similarity.method}")
        L.append("")
        L += _table(["순위", "기존사업 단위", "부처·기관", "종합 유사도", "사업목적", "지원내용", "지원대상", "전달체계", "비고"],
                    [[c.순위, c.사업명, c.부처_기관, f"{c.종합유사도:.1f}", f"{c.사업목적:.2f}", f"{c.지원내용:.2f}", f"{c.지원대상:.2f}", f"{c.전달체계:.2f}", c.비고] for c in op.similarity.candidates])
        L += [f"- ※ {n}" for n in op.similarity.notes]
    if op.reviewer_notes:
        L += ["", "### [검토자 확인 메모]", ""] + [f"- {n}" for n in op.reviewer_notes]
    return "\n".join(L) + "\n"
