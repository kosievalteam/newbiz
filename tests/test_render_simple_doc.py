import zipfile

from review_draft.render_hwpx import render_simple_doc


def test_render_simple_doc(tmp_path):
    out = tmp_path / "doc.hwpx"
    blocks = [
        ("h1", "1. 제목"),
        ("p", "본문 문단"),
        ("ol", ["첫째", "둘째"]),
        ("code", "pip install x"),
        ("table", ["항목", "내용"], [["A", "a"], ["B", "b"]]),
        ("note", "참고"),
    ]
    render_simple_doc("안내문", blocks, out, byline="2026-10-06")
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert names[0] == "mimetype"
        sec = z.read("Contents/section0.xml").decode("utf-8")
    for s in ("안내문", "1. 제목", "본문 문단", "첫째", "pip install x", "항목", "참고"):
        assert s in sec
