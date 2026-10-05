"""ReviewOpinion → .hwpx 렌더러 (한컴오피스 OWPML).

외부 라이브러리 없이 zip + XML 문자열로 직접 생성한다.
- 스타일 정의(header.xml)는 실제 사전협의 문서의 것을 템플릿(assets/hwpx_header.xml)으로 재사용하고,
  이 렌더러가 쓰는 글자/문단/테두리 속성만 새 id 로 덧붙인다.
- 용지 설정(secPr)도 템플릿(assets/hwpx_secpr.xml)을 그대로 쓴다 (A4 세로, 여백 20mm).
- 본문(section0.xml)은 문단(hp:p)과 표(hp:tbl)만으로 구성한다.

HWPUNIT: 1pt = 100, 1mm ≈ 283.5. 본문 폭 = 59528 − 5669×2 = 48190.
"""

from __future__ import annotations

import datetime as _dt
import re
import zipfile
from importlib import resources
from pathlib import Path
from xml.sax.saxutils import escape

from .schema import AxisOpinion, Dash, ReviewOpinion

BODY_W = 48000          # 표 전체 폭 (HWPUNIT)
ROW_H = 1100            # 기본 행 높이
_NS = (
    'xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
    'xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
    'xmlns:hhs="http://www.hancom.co.kr/hwpml/2011/history" xmlns:hm="http://www.hancom.co.kr/hwpml/2011/master-page" '
    'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:opf="http://www.idpf.org/2007/opf/" xmlns:ooxmlchart="http://www.hancom.co.kr/hwpml/2016/ooxmlchart" '
    'xmlns:hwpunitchar="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar" xmlns:epub="http://www.idpf.org/2007/ops" '
    'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0"'
)
_XMLDECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'


# ---------------------------------------------------------------------------
# 스타일 정의 (header.xml 에 덧붙일 항목)
# ---------------------------------------------------------------------------

# 글자 속성: 이름 → (크기 pt×100, 굵게, 색)
CHAR = {
    "body": (1000, False, "#000000"),
    "bold": (1000, True, "#000000"),
    "note": (900, False, "#404040"),
    "title": (1500, True, "#000000"),
    "h1": (1200, True, "#000000"),
    "h2": (1100, True, "#000000"),
    "th": (900, True, "#000000"),
    "td": (900, False, "#000000"),
    "small": (800, False, "#000000"),
    "smallb": (800, True, "#000000"),
    "red": (900, False, "#C00000"),
    "arrow": (1600, True, "#000000"),
}
# 문단 속성: 이름 → (정렬, 첫줄 들여쓰기, 왼쪽 여백, 앞 간격, 뒤 간격, 줄간격%)
PARA = {
    "left": ("JUSTIFY", 0, 0, 0, 0, 150),
    "center": ("CENTER", 0, 0, 0, 0, 150),
    "title": ("CENTER", 0, 0, 0, 300, 150),
    "h1": ("LEFT", 0, 0, 500, 200, 150),
    "h2": ("LEFT", 0, 0, 300, 150, 150),
    "circle": ("JUSTIFY", -600, 900, 250, 50, 150),
    "dash": ("JUSTIFY", -450, 1700, 60, 60, 150),
    "star": ("JUSTIFY", -450, 2500, 20, 20, 140),
    "group": ("JUSTIFY", 0, 1100, 150, 50, 150),
    "remark": ("JUSTIFY", -450, 1700, 60, 60, 140),
    "cell": ("LEFT", 0, 0, 0, 0, 140),
    "cellc": ("CENTER", 0, 0, 0, 0, 140),
    "box": ("JUSTIFY", -450, 650, 20, 20, 140),
    "boxsub": ("JUSTIFY", -350, 1300, 10, 10, 140),
    "appendix": ("LEFT", 0, 0, 0, 0, 130),
}
# 테두리/배경: 이름 → (테두리 있음, 배경색 또는 None)
FILL = {
    "grid": (True, None),
    "th": (True, "#E8EEF7"),
    "label": (True, "#EDEDED"),
    "box": (True, "#F5F5F5"),
    "check": (True, "#FFF8E1"),
}


def _char_xml(cid: int, height: int, bold: bool, color: str) -> str:
    b = "<hh:bold/>" if bold else ""
    return (
        f'<hh:charPr id="{cid}" height="{height}" textColor="{color}" shadeColor="none" useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="1">'
        '<hh:fontRef hangul="1" latin="1" hanja="1" japanese="1" other="1" symbol="1" user="1"/>'
        '<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        '<hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        '<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        '<hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        f'{b}<hh:underline type="NONE" shape="SOLID" color="#000000"/><hh:strikeout shape="NONE" color="#000000"/>'
        '<hh:outline type="NONE"/><hh:shadow type="NONE" color="#C0C0C0" offsetX="10" offsetY="10"/></hh:charPr>'
    )


def _para_xml(pid: int, align: str, intent: int, left: int, prev: int, nxt: int, spacing: int) -> str:
    margin = (
        f'<hh:margin><hc:intent value="{intent}" unit="HWPUNIT"/><hc:left value="{left}" unit="HWPUNIT"/>'
        f'<hc:right value="0" unit="HWPUNIT"/><hc:prev value="{prev}" unit="HWPUNIT"/><hc:next value="{nxt}" unit="HWPUNIT"/></hh:margin>'
        f'<hh:lineSpacing type="PERCENT" value="{spacing}" unit="HWPUNIT"/>'
    )
    return (
        f'<hh:paraPr id="{pid}" tabPrIDRef="0" condense="0" fontLineHeight="0" snapToGrid="0" suppressLineNumbers="0" checked="0">'
        f'<hh:align horizontal="{align}" vertical="BASELINE"/><hh:heading type="NONE" idRef="0" level="0"/>'
        '<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="BREAK_WORD" widowOrphan="0" keepWithNext="0" keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>'
        '<hh:autoSpacing eAsianEng="0" eAsianNum="0"/>'
        f'<hp:switch><hp:case hp:required-namespace="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">{margin}</hp:case><hp:default>{margin}</hp:default></hp:switch>'
        '<hh:border borderFillIDRef="1" offsetLeft="0" offsetRight="0" offsetTop="0" offsetBottom="0" connect="0" ignoreMargin="0"/></hh:paraPr>'
    )


def _fill_xml(fid: int, border: bool, color: str | None) -> str:
    t = "SOLID" if border else "NONE"
    brush = f'<hc:fillBrush><hc:winBrush faceColor="{color}" hatchColor="#FF000000" alpha="0"/></hc:fillBrush>' if color else ""
    return (
        f'<hh:borderFill id="{fid}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
        '<hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
        f'<hh:leftBorder type="{t}" width="0.12 mm" color="#000000"/><hh:rightBorder type="{t}" width="0.12 mm" color="#000000"/>'
        f'<hh:topBorder type="{t}" width="0.12 mm" color="#000000"/><hh:bottomBorder type="{t}" width="0.12 mm" color="#000000"/>'
        f'<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>{brush}</hh:borderFill>'
    )


class _Styles:
    """템플릿 header.xml 에 렌더러용 스타일을 덧붙이고 이름→id 매핑을 보관한다."""

    def __init__(self, header_xml: str):
        self.char: dict[str, int] = {}
        self.para: dict[str, int] = {}
        self.fill: dict[str, int] = {}
        self.header = header_xml
        self._append("hh:charProperties", "hh:charPr", CHAR, self.char, _char_xml)
        self._append("hh:paraProperties", "hh:paraPr", PARA, self.para, _para_xml)
        self._append("hh:borderFills", "hh:borderFill", FILL, self.fill, _fill_xml)

    def _append(self, list_tag: str, item_tag: str, spec: dict, out: dict, maker):
        m = re.search(rf"<{list_tag} itemCnt=\"(\d+)\"", self.header)
        if not m:
            raise ValueError(f"템플릿 header.xml 에 {list_tag} 가 없습니다")
        count = int(m.group(1))
        ids = [int(x) for x in re.findall(rf"<{item_tag} id=\"(\d+)\"", self.header)]
        next_id = (max(ids) + 1) if ids else 0
        items = []
        for name, args in spec.items():
            out[name] = next_id
            items.append(maker(next_id, *args))
            next_id += 1
        self.header = self.header.replace(m.group(0), f'<{list_tag} itemCnt="{count + len(items)}"', 1)
        close = f"</{list_tag}>"
        idx = self.header.index(close)
        self.header = self.header[:idx] + "".join(items) + self.header[idx:]


# ---------------------------------------------------------------------------
# 본문 조립
# ---------------------------------------------------------------------------

class _Body:
    def __init__(self, st: _Styles):
        self.st = st
        self.parts: list[str] = []
        self._pid = 1
        self._oid = 1700000000
        self.plain: list[str] = []  # 미리보기 텍스트

    def _next_pid(self) -> int:
        self._pid += 1
        return self._pid

    def _next_oid(self) -> int:
        self._oid += 1
        return self._oid

    def p_xml(self, text: str, para: str = "left", char: str = "body", page_break: bool = False) -> str:
        runs = f'<hp:run charPrIDRef="{self.st.char[char]}"><hp:t>{escape(text)}</hp:t></hp:run>' if text else f'<hp:run charPrIDRef="{self.st.char[char]}"/>'
        return (
            f'<hp:p id="{self._next_pid()}" paraPrIDRef="{self.st.para[para]}" styleIDRef="0" pageBreak="{1 if page_break else 0}" columnBreak="0" merged="0">'
            f"{runs}</hp:p>"
        )

    def p(self, text: str, para: str = "left", char: str = "body", page_break: bool = False):
        self.parts.append(self.p_xml(text, para, char, page_break))
        if text:
            self.plain.append(text)

    def blank(self):
        self.p("")

    def _cell(self, lines: list[tuple[str, str, str]], col: int, row: int, width: int, height: int, fill: str, colspan: int = 1) -> str:
        paras = "".join(self.p_xml(t, pa, ch) for t, pa, ch in lines) or self.p_xml("", "cell", "td")
        return (
            f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="{self.st.fill[fill]}">'
            '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
            f"{paras}</hp:subList><hp:cellAddr colAddr=\"{col}\" rowAddr=\"{row}\"/><hp:cellSpan colSpan=\"{colspan}\" rowSpan=\"1\"/>"
            f'<hp:cellSz width="{width}" height="{height}"/><hp:cellMargin left="400" right="400" top="120" bottom="120"/></hp:tc>'
        )

    def table(self, rows: list[list[list[tuple[str, str, str]]]], widths: list[int], fills: list[list[str]], heights: list[int] | None = None):
        """rows[r][c] = 셀 안 문단 목록 [(text, para, char)]; fills[r][c] = 테두리/배경 이름."""
        ncol = len(widths)
        heights = heights or [ROW_H] * len(rows)
        trs = []
        for r, row in enumerate(rows):
            tcs = [self._cell(row[c] if c < len(row) else [], c, r, widths[c], heights[r], fills[r][c]) for c in range(ncol)]
            trs.append("<hp:tr>" + "".join(tcs) + "</hp:tr>")
        tbl = (
            f'<hp:tbl id="{self._next_oid()}" zOrder="{self._next_oid()}" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" '
            f'pageBreak="CELL" repeatHeader="1" rowCnt="{len(rows)}" colCnt="{ncol}" cellSpacing="0" borderFillIDRef="{self.st.fill["grid"]}" noAdjust="1">'
            f'<hp:sz width="{sum(widths)}" widthRelTo="ABSOLUTE" height="{sum(heights)}" heightRelTo="ABSOLUTE" protect="0"/>'
            '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
            '<hp:outMargin left="141" right="141" top="141" bottom="141"/><hp:inMargin left="400" right="400" top="120" bottom="120"/>'
            + "".join(trs) + "</hp:tbl>"
        )
        # 표는 문단 안의 run 에 들어간다
        self.parts.append(
            f'<hp:p id="{self._next_pid()}" paraPrIDRef="{self.st.para["left"]}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{self.st.char["body"]}">{tbl}</hp:run></hp:p>'
        )
        for row in rows:
            self.plain.append(" | ".join("/".join(t for t, _, _ in cell) for cell in row))

    # --- 고수준 요소 ---------------------------------------------------------

    @staticmethod
    def _lines(text: str, para: str, char: str) -> list[tuple[str, str, str]]:
        return [(l, para, char) for l in str(text).split("\n")] or [("", para, char)]

    def kv_table(self, rows: list[tuple[str, str]], label_w: int = 9000):
        body = [[self._lines(k, "cellc", "th"), self._lines(v, "cell", "td")] for k, v in rows]
        fills = [["label", "grid"] for _ in rows]
        self.table(body, [label_w, BODY_W - label_w], fills)

    def grid_table(self, header: list[str], rows: list[list[str]], first_w: int = 6000, char: str = "td", header_char: str = "th"):
        ncol = len(header)
        other = (BODY_W - first_w) // max(ncol - 1, 1)
        widths = [first_w] + [other] * (ncol - 1)
        widths[-1] += BODY_W - sum(widths)
        body = [[self._lines(h, "cellc", header_char) for h in header]]
        fills = [["th"] * ncol]
        for row in rows:
            cells = []
            for j in range(ncol):
                val = row[j] if j < len(row) else ""
                cells.append(self._lines(val, "cellc" if j == 0 else "cell", header_char if j == 0 else char))
            body.append(cells)
            fills.append(["label"] + ["grid"] * (ncol - 1))
        self.table(body, widths, fills)

    def box(self, lines: list[tuple[str, str, str]], fill: str, height: int):
        self.table([[lines]], [BODY_W], [[fill]], [height])

    def dash(self, d: Dash, para: str = "dash", star_para: str = "star"):
        label = f"({d.label}) " if d.label else ""
        self.p("- " + label + d.text, para, "body")
        for i, n in enumerate(d.notes):
            self.p(f"{'*' * (i + 1)} {n}", star_para, "note")

    def axis(self, ax: AxisOpinion):
        self.p("○ " + ax.headline, "circle", "bold")
        if ax.group_labels and ax.dash_groups:
            for label, group in zip(ax.group_labels, ax.dash_groups):
                self.p(label, "group", "bold")
                for d in group:
                    self.dash(d)
        for d in ax.dashes:
            self.dash(d)
        for r in ax.remarks:
            self.p("※ " + r, "remark", "note")


def build_section_xml(op: ReviewOpinion, st: _Styles, secpr_xml: str, appendix_text: str | None, draft_banner: bool) -> tuple[str, str]:
    b = _Body(st)

    # 첫 문단: 구역 설정 + 제목
    first = (
        f'<hp:p id="0" paraPrIDRef="{st.para["title"]}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{st.char["title"]}">{secpr_xml}<hp:ctrl><hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" sameSz="1" sameGap="0"/></hp:ctrl>'
        f"<hp:t>{escape('중소기업지원사업 사전협의 검토의견서')}</hp:t></hp:run></hp:p>"
    )
    b.parts.append(first)
    b.plain.append("중소기업지원사업 사전협의 검토의견서")
    if draft_banner:
        b.p("※ 자동 생성 초안 — 검토자 확인 후 발송", "center", "red")

    ov, ex, s = op.overview, op.extra_info, op.summary
    b.p("1. 협의신청사업 및 검토의견 개요", "h1", "h1")
    b.p("□ 협의신청사업 개요", "h2", "h2")
    b.kv_table([("1. 사업명", ov.사업명), ("2. 신청기관", ov.신청기관), ("3. 지원유형", ov.지원유형), ("4. 특이사항", ov.특이사항), ("5. 검토자", ov.검토자 or "")])
    b.p("□ 사업개요 추가정보", "h2", "h2")
    b.kv_table([("1-1. 근거법령", ex.근거법령), ("1-2. 상위정책", ex.상위정책), ("1-3. 사업목적", ex.사업목적), ("2-1. 지원대상", ex.지원대상),
                ("2-2. 지원내용", ex.지원내용), ("2-3. 지원규모", ex.지원규모), ("2-4. 전달체계", ex.전달체계), ("3-1. 연계사업", ex.연계사업)])
    b.p("□ 검토의견 요약", "h2", "h2")
    b.grid_table(["1. 종합의견", "2. 사업타당성", "3. 사업적합성", "4. 유사중복성"], [[s.종합의견, s.사업타당성, s.사업적합성, s.유사중복성]], first_w=BODY_W // 4, char="bold", header_char="th")
    b.p("※ 유사중복검토 사업(유사중복사업이 있을 경우에만 작성)", "left", "note")
    rows = [[p.부처, p.사업명, p.검토의견] for p in op.similar_programs] or [["-", "해당 없음", "-"]]
    b.grid_table(["부 처", "사업명", "검토의견"], rows, first_w=7000)

    # 2. 검토의견
    b.p("2. 검토의견", "h1", "h1", page_break=True)
    b.p("1. 종합의견", "h2", "h2")
    b.axis(op.validity)
    b.axis(op.suitability)
    cb = op.content_box
    lines: list[tuple[str, str, str]] = [("사업내용", "cellc", "bold"), ("▪ (지원대상) " + cb.지원대상, "box", "td"), ("▪ (추진내용) " + cb.추진내용, "box", "td")]
    lines += [("- " + x, "boxsub", "td") for x in cb.추진내용_세부]
    lines.append(("▪ (지원규모) " + cb.지원규모, "box", "td"))
    lines += [("- " + x, "boxsub", "td") for x in cb.지원규모_세부]
    lines.append(("▪ (수행기관) " + cb.수행기관, "box", "td"))
    b.blank()
    b.box(lines, "box", 600 * len(lines) + 400)
    b.p("⇩", "center", "arrow")
    b.box([("사업내용 점검", "cellc", "bold")] + [(l, "cellc", "td") for l in op.check_box.lines], "check", 600 * (len(op.check_box.lines) + 1) + 300)
    b.blank()
    b.axis(op.duplication)

    b.p("2. 개선의견", "h2", "h2")
    for imp in op.improvements:
        b.p("○ " + imp.headline, "circle", "bold")
        for d in imp.dashes:
            b.dash(d)

    b.blank()
    b.p("〈 사업간 비교표 〉", "center", "bold")
    b.grid_table(["구 분"] + op.comparison.columns, op.comparison.rows, first_w=5500, char="small", header_char="smallb")

    if op.similarity.candidates:
        b.blank()
        b.p("〈 참고 〉 유사도 분석 결과 (상위 후보)", "center", "bold")
        if op.similarity.method:
            b.p("- 분석 기준: " + op.similarity.method, "left", "note")
        srows = [[str(c.순위), c.사업명, c.부처_기관, f"{c.종합유사도:.1f}", f"{c.사업목적:.2f}", f"{c.지원내용:.2f}", f"{c.지원대상:.2f}", f"{c.전달체계:.2f}", c.비고] for c in op.similarity.candidates]
        b.grid_table(["순위", "기존사업 단위", "부처·기관", "종합", "목적", "내용", "대상", "체계", "비고"], srows, first_w=2800, char="small", header_char="smallb")
        for n in op.similarity.notes:
            b.p("※ " + n, "remark", "note")

    if op.reviewer_notes:
        b.p("[검토자 확인 메모] (발송 전 삭제)", "h2", "red", page_break=True)
        for n in op.reviewer_notes:
            b.p("- " + n, "dash", "red")

    if appendix_text:
        b.p("참고1. 협의요청서 (원문 추출)", "h1", "h1", page_break=True)
        for line in appendix_text.splitlines():
            if line.strip():
                b.p(line, "appendix", "note")

    sec = f'{_XMLDECL}<hs:sec {_NS}>' + "".join(b.parts) + "</hs:sec>"
    return sec, "\n".join(b.plain)


# ---------------------------------------------------------------------------
# 패키지(zip) 조립
# ---------------------------------------------------------------------------

def _asset(name: str) -> str:
    return (resources.files("review_draft") / "assets" / name).read_text(encoding="utf-8")


def _content_hpf(title: str) -> str:
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f'{_XMLDECL}<opf:package {_NS} version="" unique-identifier="" id="">'
        f"<opf:metadata><opf:title>{escape(title)}</opf:title><opf:language>ko</opf:language>"
        '<opf:meta name="creator" content="text">review-draft</opf:meta><opf:meta name="subject" content="text"/>'
        '<opf:meta name="description" content="text"/><opf:meta name="lastsaveby" content="text">review-draft</opf:meta>'
        f'<opf:meta name="CreatedDate" content="text">{now}</opf:meta><opf:meta name="ModifiedDate" content="text">{now}</opf:meta>'
        '<opf:meta name="keyword" content="text"/></opf:metadata>'
        '<opf:manifest><opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
        '<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>'
        '<opf:item id="settings" href="settings.xml" media-type="application/xml"/></opf:manifest>'
        '<opf:spine><opf:itemref idref="header"/><opf:itemref idref="section0" linear="yes"/></opf:spine></opf:package>'
    )


_VERSION = (
    f'{_XMLDECL}<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version" tagetApplication="WORDPROCESSOR" '
    'major="5" minor="0" micro="5" buildNumber="0" os="1" xmlVersion="1.4" application="Hancom Office Hangul" appVersion="9, 1, 1, 5656 WIN32LEWindows_Unknown_Version"/>'
)
_CONTAINER = (
    f'{_XMLDECL}<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container" xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf">'
    '<ocf:rootfiles><ocf:rootfile full-path="Contents/content.hpf" media-type="application/hwpml-package+xml"/>'
    '<ocf:rootfile full-path="Preview/PrvText.txt" media-type="text/plain"/></ocf:rootfiles></ocf:container>'
)
_MANIFEST = f'{_XMLDECL}<odf:manifest xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"/>'
_SETTINGS = (
    f'{_XMLDECL}<ha:HWPApplicationSetting xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0">'
    '<ha:CaretPosition listIDRef="0" paraIDRef="0" pos="0"/></ha:HWPApplicationSetting>'
)


def render_hwpx(op: ReviewOpinion, out_path: str | Path, *, appendix_text: str | None = None, draft_banner: bool = True) -> Path:
    st = _Styles(_asset("hwpx_header.xml"))
    section, preview = build_section_xml(op, st, _asset("hwpx_secpr.xml"), appendix_text, draft_banner)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(out), "w") as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
        for name, data in (
            ("version.xml", _VERSION),
            ("META-INF/container.xml", _CONTAINER),
            ("META-INF/manifest.xml", _MANIFEST),
            ("Contents/content.hpf", _content_hpf(f"{op.overview.사업명} 검토의견서")),
            ("Contents/header.xml", st.header),
            ("Contents/section0.xml", section),
            ("settings.xml", _SETTINGS),
            ("Preview/PrvText.txt", preview[:4000]),
        ):
            zf.writestr(name, data.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
    return out
