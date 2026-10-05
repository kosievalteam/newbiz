import xml.dom.minidom
import zipfile
from pathlib import Path

from review_draft.hwp import clean_lines, extract_hwpx
from review_draft.render_hwpx import render_hwpx
from review_draft.schema import ReviewOpinion

FIX = Path(__file__).parent / "fixtures" / "opinion_sample.json"


def test_render_hwpx_package_and_roundtrip(tmp_path):
    op = ReviewOpinion.model_validate_json(FIX.read_text(encoding="utf-8"))
    out = render_hwpx(op, tmp_path / "x.hwpx", appendix_text="원문 1행\n원문 2행")
    z = zipfile.ZipFile(out)
    infos = z.infolist()
    assert infos[0].filename == "mimetype" and infos[0].compress_type == zipfile.ZIP_STORED
    assert z.read("mimetype") == b"application/hwp+zip"
    names = {i.filename for i in infos}
    assert {"Contents/header.xml", "Contents/section0.xml", "Contents/content.hpf", "META-INF/container.xml", "settings.xml", "version.xml"} <= names
    for n in ("Contents/header.xml", "Contents/section0.xml", "Contents/content.hpf"):
        xml.dom.minidom.parseString(z.read(n))
    header = z.read("Contents/header.xml").decode("utf-8")
    section = z.read("Contents/section0.xml").decode("utf-8")
    # 본문이 참조하는 모든 스타일 id 가 header 에 정의되어 있어야 한다
    import re

    for attr, tag in (("charPrIDRef", "hh:charPr"), ("paraPrIDRef", "hh:paraPr"), ("borderFillIDRef", "hh:borderFill")):
        used = set(re.findall(rf'{attr}="(\d+)"', section))
        defined = set(re.findall(rf'<{tag} id="(\d+)"', header))
        assert used <= defined, f"{attr} 미정의: {used - defined}"
    text = "\n".join(clean_lines(extract_hwpx(out)))
    assert "○ (사업 적합성)" in text and "⇩" in text and "사업내용 점검" in text
    assert "〈 사업간 비교표 〉" in text and "참고1. 협의요청서" in text and "원문 2행" in text
    assert "(중복수혜 방지)" in text
