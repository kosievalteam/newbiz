"""HWP 5.x / HWPX 텍스트 추출기.

외부 바이너리(hwp5proc) 없이 olefile + zlib 만으로 HWP 5.x 본문 텍스트를 추출한다.
표 셀 경계는 ``[CELL]`` 마커로, 표 시작은 ``[TABLE]`` 마커로 남겨 두어
후속 파서가 셀 단위로 값을 읽을 수 있게 한다.
"""

from __future__ import annotations

import re
import struct
import zipfile
import zlib
from pathlib import Path

HWPTAG_PARA_TEXT = 67
HWPTAG_TABLE = 71
HWPTAG_LIST_HEADER = 72

# 8 WCHAR 길이를 갖는 확장/인라인 제어문자 (HWP 5.0 스펙 §4.2.2)
_EXTENDED_CTRL = {1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23}
_INLINE_CTRL = {4, 5, 6, 7, 8, 9, 19, 20}


def _records(data: bytes):
    pos = 0
    n = len(data)
    while pos + 4 <= n:
        hdr = struct.unpack("<I", data[pos : pos + 4])[0]
        tag = hdr & 0x3FF
        level = (hdr >> 10) & 0x3FF
        size = (hdr >> 20) & 0xFFF
        pos += 4
        if size == 0xFFF:
            size = struct.unpack("<I", data[pos : pos + 4])[0]
            pos += 4
        yield tag, level, data[pos : pos + size]
        pos += size


def _para_text(payload: bytes) -> str:
    out: list[str] = []
    i = 0
    n = len(payload) // 2
    while i < n:
        c = struct.unpack("<H", payload[2 * i : 2 * i + 2])[0]
        if c < 32:
            if c in (10, 13):
                out.append("\n")
            elif c in _EXTENDED_CTRL or c in _INLINE_CTRL:
                if c == 9:
                    out.append("\t")
                i += 7  # 제어문자 본체 + 7 WCHAR
        else:
            out.append(chr(c))
        i += 1
    return "".join(out)


def extract_hwp(path: str | Path, markers: bool = True) -> str:
    """HWP 5.x 파일에서 본문 텍스트를 추출한다."""
    import olefile  # 지연 import: hwpx 만 쓰는 환경 배려

    ole = olefile.OleFileIO(str(path))
    try:
        header = ole.openstream("FileHeader").read()
        flags = struct.unpack("<I", header[36:40])[0]
        compressed = bool(flags & 0x1)
        if flags & 0x2:
            raise ValueError("암호화된 HWP 파일은 지원하지 않습니다: %s" % path)
        sections = sorted(
            (e for e in ole.listdir() if e[0] == "BodyText"),
            key=lambda e: int(re.sub(r"\D", "", e[1]) or 0),
        )
        lines: list[str] = []
        for entry in sections:
            data = ole.openstream(entry).read()
            if compressed:
                data = zlib.decompress(data, -15)
            for tag, _level, payload in _records(data):
                if tag == HWPTAG_PARA_TEXT:
                    lines.append(_para_text(payload))
                elif markers and tag == HWPTAG_TABLE:
                    lines.append("[TABLE]")
                elif markers and tag == HWPTAG_LIST_HEADER:
                    lines.append("[CELL]")
        return "\n".join(lines)
    finally:
        ole.close()


def extract_hwpx(path: str | Path, markers: bool = True) -> str:
    """HWPX(OWPML zip) 파일에서 본문 텍스트를 추출한다."""
    lines: list[str] = []
    with zipfile.ZipFile(str(path)) as zf:
        names = sorted(n for n in zf.namelist() if re.match(r"Contents/section\d+\.xml", n))
        for name in names:
            xml = zf.read(name).decode("utf-8", errors="replace")
            # 문단(<hp:p>) 단위로 분리한 뒤 <hp:t> 텍스트를 합친다
            for para in re.split(r"<hp:p\b", xml)[1:]:
                if markers and "<hp:tbl" in para:
                    lines.append("[TABLE]")
                if markers and "<hp:tc" in para:
                    lines.append("[CELL]")
                texts = re.findall(r"<hp:t[^>]*>([^<]*)</hp:t>", para)
                lines.append(_unescape("".join(texts)))
    return "\n".join(lines)


def _unescape(s: str) -> str:
    return (
        s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&")
    )


def extract_pdf(path: str | Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("PDF 입력을 읽으려면 `pip install pypdf` 가 필요합니다.") from e
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def extract_text(path: str | Path, markers: bool = True) -> str:
    """확장자에 따라 적절한 추출기를 호출한다 (.hwp/.hwpx/.pdf/.txt/.md)."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".hwp":
        text = extract_hwp(p, markers=markers)
    elif ext == ".hwpx":
        text = extract_hwpx(p, markers=markers)
    elif ext == ".pdf":
        text = extract_pdf(p)
    elif ext in {".txt", ".md"}:
        text = p.read_text(encoding="utf-8")
    else:
        raise ValueError("지원하지 않는 형식입니다: %s" % ext)
    # 서로게이트 등 인코딩 불가 문자는 제거
    return text.encode("utf-8", errors="ignore").decode("utf-8")


def clean_lines(text: str, keep_markers: bool = False) -> list[str]:
    """빈 줄과 표 마커를 제거한 줄 목록을 돌려준다."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if not keep_markers and s in ("[TABLE]", "[CELL]"):
            continue
        out.append(s)
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="hwp/hwpx/pdf/txt 본문 텍스트를 추출해 표준출력 또는 파일로 저장한다.")
    ap.add_argument("path")
    ap.add_argument("-o", "--out", help="저장할 텍스트 파일 경로(생략 시 표준출력)")
    ap.add_argument("--markers", action="store_true", help="표 경계 마커([TABLE]/[CELL]) 유지")
    a = ap.parse_args()
    txt = extract_text(a.path, markers=a.markers)
    if a.out:
        Path(a.out).write_text(txt, encoding="utf-8")
        print(f"{a.out}: {len(txt)}자")
    else:
        print(txt)
