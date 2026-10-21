import json
from pathlib import Path

from review_draft.checks import check_opinion
from review_draft.schema import ReviewOpinion

FIX = Path(__file__).parent / "fixtures" / "opinion_sample.json"


def _load():
    return json.loads(FIX.read_text(encoding="utf-8"))


def _errors(d):
    return [f for f in check_opinion(ReviewOpinion.model_validate(d)) if f.level == "error"]


def test_sample_has_no_errors():
    assert _errors(_load()) == []


def test_summary_headline_mismatch():
    d = _load()
    d["summary"]["사업타당성"] = "동의"
    assert any("권고안 제시" in e.message for e in _errors(d))


def test_overall_verdict_rule():
    d = _load()
    d["summary"]["종합의견"] = "동의"
    assert any("종합의견" in e.message for e in _errors(d))


def test_headline_area_without_dash():
    d = _load()
    d["validity"]["headline"] = "(사업 타당성) 법적근거·상위정책 및 정책수요 측면 타당, “원안 동의”"
    d["validity"]["dashes"] = [x for x in d["validity"]["dashes"] if "상위정책" not in x["label"]]
    assert any("상위정책" in e.message for e in _errors(d))


def test_recommend_requires_improvements():
    d = _load()
    d["improvements"] = [{"headline": "해당 없음", "dashes": []}]
    assert any("개선의견" in e.where for e in _errors(d))


def test_comparison_column_count():
    d = _load()
    d["comparison"]["rows"][0] = ["사업부서", "하나만"]
    assert any("비교표" in e.where for e in _errors(d))


def test_forbidden_expression_warns():
    d = _load()
    d["validity"]["dashes"][2]["text"] += " 다만 성과관리가 미흡함"
    w = [f for f in check_opinion(ReviewOpinion.model_validate(d)) if "미흡함" in f.message]
    assert w and w[0].level == "warn"


def test_vague_similarity_expression_is_flagged():
    d = _load()
    d["duplication"]["dashes"][0]["text"] = "본 사업과 기존사업은 일부 유사성 확인"
    msgs = [f.message for f in check_opinion(ReviewOpinion.model_validate(d)) if f.level == "warn"]
    assert any("일부 유사" in m and "축" in m for m in msgs)


def test_suitability_requires_all_four_areas():
    d = _load()
    d["suitability"]["dashes"] = [x for x in d["suitability"]["dashes"] if x["label"] != "지원대상"]
    msgs = [f.message for f in _errors(d)]
    assert any("‘지원대상’ dash 가 없음" in m for m in msgs)
    d = _load()
    d["check_box"]["lines"] = ["지원내용, 지원규모, 수행기관 : (원안 동의)"]
    msgs = [f.message for f in _errors(d)]
    assert any("‘지원대상’ 판정이 없음" in m for m in msgs)


def test_cited_program_must_appear_in_comparison():
    d = _load()
    d["similar_programs"].append({"부처": "중기부", "사업명": "산학협력인력양성 > 중소기업특성화고인력양성", "검토의견": "x"})
    msgs = [f.message for f in _errors(d)]
    assert any("중소기업특성화고인력양성" in m and "비교표" in m for m in msgs)
    d = _load()
    assert not any("비교표 열에 없음" in f.message for f in _errors(d))


def test_multiple_comparison_tables_render(tmp_path):
    from review_draft.render_md import render_md

    d = _load()
    d["comparisons"] = [
        {"title": "표1", "columns": d["comparison"]["columns"], "rows": d["comparison"]["rows"]},
        {"title": "표2", "columns": ["(신규사업) A", "(기존) B"], "rows": [["사업부서", "a", "b"]]},
    ]
    md = render_md(ReviewOpinion.model_validate(d))
    assert "**표1**" in md and "**표2**" in md and "(기존) B" in md
