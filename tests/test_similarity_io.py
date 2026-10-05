import json

from review_draft.similarity_io import load_similarity, report_to_prompt_text


def _top10(tmp_path):
    rows = [{"순위": i, "공고이름": f"2026년 사업{i} > 내역{i}", "부처": "중기부", "기관": "창진원", "단위": "내역사업", "연도": 2026,
             "종합유사도(0~100)": 70 - i, "사업목적_유사도": 0.7, "지원내용_유사도": 0.6, "지원대상_유사도": 0.65, "전달체계_유사도": 0.5}
            for i in range(1, 11)]
    p = tmp_path / "top10.json"
    p.write_text(json.dumps({"weights": {"사업목적": 21.05}, "model": "bge-m3", "n_existing": 3631, "top": {"전체": rows}}, ensure_ascii=False), encoding="utf-8")
    return p


def test_load_json(tmp_path):
    rep = load_similarity(_top10(tmp_path))
    assert len(rep.candidates) == 10
    assert rep.candidates[0].사업명 == "사업1 > 내역1 (2026)"
    assert rep.candidates[0].비고.startswith("비교표 반영") and rep.candidates[3].비고 == ""
    assert "3,631" in rep.method and "bge-m3" in rep.method


def test_load_xlsx(tmp_path):
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.title = "가중치"
    ws = wb.create_sheet("전체")
    ws.append(["순위", "부처", "기관", "공고이름", "단위", "연도", "사업목적_유사도", "지원내용_유사도", "지원대상_유사도", "전달체계_유사도", "종합유사도(0~100)"])
    for i in range(1, 13):
        ws.append([i, "금융위", "센터", f"2026년 핀테크{i}", "내역사업", 2026, 0.7, 0.7, 0.7, 0.8, 80 - i])
    p = tmp_path / "s.xlsx"
    wb.save(p)
    rep = load_similarity(p, top=5)
    assert [c.순위 for c in rep.candidates] == [1, 2, 3, 4, 5]
    assert rep.candidates[0].종합유사도 == 79


def test_prompt_text(tmp_path):
    txt = report_to_prompt_text(load_similarity(_top10(tmp_path)))
    assert "| 1 |" in txt and "상위 3개" in txt
