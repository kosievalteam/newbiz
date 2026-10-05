from pathlib import Path

from review_draft.request_parser import parse_request_text, redact_contacts

FIX = Path(__file__).parent / "fixtures" / "request_sample.txt"


def test_parse_sections():
    rf = parse_request_text(FIX.read_text(encoding="utf-8"))
    assert rf.신청기관 == "부산광역시"
    assert rf.신청부서 == "연구개발과"
    assert "세부사업 신설" in rf.요청사유
    assert rf.사업명.startswith("(세부사업)")
    assert "과학기술진흥 조례" in rf.추진근거
    assert "BIRD" in rf.추진사유
    assert "매출액 증대" in rf.성과지표
    assert "700백만원" in rf.지원규모
    assert "기술보증기금" in rf.시행방법
    assert "벤치마킹" in rf.사업제도연계
    assert "지역전용" in rf.유사중복_점검내용
    assert "공고정보자료집" not in rf.유사중복_점검내용  # 양식 안내문 제거
    assert rf.사업설명서.startswith("참고2")
    assert not rf.is_empty()


def test_prompt_text_contains_headings():
    rf = parse_request_text(FIX.read_text(encoding="utf-8"))
    t = rf.to_prompt_text(max_attachment_chars=100)
    assert "# 사전협의 요청서" in t and "## 지원규모" in t and "(이하 생략)" in t


def test_redact():
    s = "담당 홍길동 02-123-4567 hong@seoul.go.kr / 051-888-6765"
    r = redact_contacts(s)
    assert "4567" not in r and "@" not in r and "6765" not in r


def test_empty_text():
    assert parse_request_text("아무 내용 없음").is_empty()
