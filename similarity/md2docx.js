// 개조식 보고서(.md)를 Word(.docx)로 변환한다. 사용: npm install docx && node similarity/md2docx.js 입력.md 출력.docx
// □ ○ - * 위계별 들여쓰기·글자 크기, 마크다운 표를 Word 표로 변환. A4 세로, 여백 2cm, 맑은 고딕.
const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType, AlignmentType, HeadingLevel } = require("docx");
const [,, src, dst] = process.argv;
const lines = fs.readFileSync(src, "utf-8").split("\n");
const FONT = "맑은 고딕";
const clean = s => s.replace(/`([^`]*)`/g, "$1").replace(/\*\*([^*]+)\*\*/g, "$1");
const run = (t, o = {}) => new TextRun({ text: t, font: FONT, ...o });
const children = [];
const PAGE_W = 11906, MARGIN = 1134; const TW = PAGE_W - 2 * MARGIN; // A4, 2cm margins

function para(text, { size = 20, bold = false, left = 0, hanging = 0, before = 60, after = 60, color } = {}) {
  return new Paragraph({ spacing: { before, after, line: 300 }, indent: { left, hanging }, children: [run(text, { size, bold, color })] });
}
function flushTable(rows) {
  const n = rows[0].length;
  const texts = rows.map(r => r.map(clean));
  // column widths: proportional to max text length, bounded
  const maxLen = Array.from({ length: n }, (_, j) => Math.max(...texts.map(r => (r[j] || "").length), 2));
  const w = maxLen.map(l => Math.min(Math.max(l, 3), 40));
  const total = w.reduce((a, b) => a + b, 0);
  let widths = w.map(x => Math.round(TW * x / total));
  widths[widths.length - 1] += TW - widths.reduce((a, b) => a + b, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: "808080" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const trows = texts.map((r, i) => new TableRow({
    tableHeader: i === 0,
    children: r.map((c, j) => new TableCell({
      width: { size: widths[j], type: WidthType.DXA }, borders,
      shading: i === 0 ? { type: ShadingType.CLEAR, fill: "E7E6E6", color: "auto" } : undefined,
      margins: { top: 40, bottom: 40, left: 60, right: 60 },
      children: [new Paragraph({ alignment: (i === 0 || /^[\d.,~ ]+$/.test(c)) ? AlignmentType.CENTER : AlignmentType.LEFT, spacing: { before: 0, after: 0, line: 240 }, children: [run(c, { size: 16, bold: i === 0 })] })],
    })),
  }));
  children.push(new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: widths, rows: trows }));
  children.push(para("", { after: 40, before: 0 }));
}
let table = [];
for (const raw of lines) {
  const l = raw.replace(/\s+$/, "");
  if (/^\|/.test(l)) {
    if (/^\|\s*-+/.test(l)) continue;
    table.push(l.replace(/^\||\|$/g, "").split("|").map(s => s.trim()));
    continue;
  } else if (table.length) { flushTable(table); table = []; }
  if (!l.trim()) continue;
  let m;
  if ((m = l.match(/^# (.*)/))) children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 0, after: 240 }, children: [run(clean(m[1]), { size: 32, bold: true })] }));
  else if ((m = l.match(/^## (.*)/))) children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 360, after: 120 }, children: [run(clean(m[1]), { size: 26, bold: true, color: "1F3864" })] }));
  else if ((m = l.match(/^- (.*)/))) children.push(para("- " + clean(m[1]), { size: 18, left: 400, hanging: 200, before: 20, after: 20, color: "404040" }));
  else if ((m = l.match(/^□ (.*)/))) children.push(para("□ " + clean(m[1]), { size: 21, bold: true, left: 300, hanging: 300, before: 160, after: 80 }));
  else if ((m = l.match(/^ ○ (.*)/))) children.push(para("○ " + clean(m[1]), { size: 20, left: 640, hanging: 300, before: 100, after: 40 }));
  else if ((m = l.match(/^  - (.*)/))) children.push(para("- " + clean(m[1]), { size: 19, left: 920, hanging: 200, before: 20, after: 20 }));
  else if ((m = l.match(/^  \* (.*)/))) children.push(para("* " + clean(m[1]), { size: 18, left: 1140, hanging: 200, before: 20, after: 20, color: "404040" }));
  else children.push(para(clean(l), { size: 20 }));
}
if (table.length) flushTable(table);
const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: 20 } } } },
  sections: [{ properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } }, children }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(dst, b); console.log("saved", dst, b.length); });
