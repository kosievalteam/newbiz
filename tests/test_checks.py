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
    d["suitability"]["headline"] = "(사업 적합성) 지원대상·지원내용·지원규모·사업수행체계 측면 적절, “원안 동의”"
    assert any("지원대상" in e.message for e in _errors(d))


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
