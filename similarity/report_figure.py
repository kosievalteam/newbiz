"""유사·중복 검토 결과 1장 보고용 그림(PNG) 생성기.

산출 xlsx 에서 수치를 읽고 서술(헤드라인·유형 카드·시사점)은 spec JSON 에서 받아
A3 가로 1장짜리 보고용 그림을 만든다. 렌더링은 Chromium(headless) 으로 한다.

    python similarity/report_figure.py --xlsx 산출결과.xlsx --spec figure_spec.json --out 그림.png

spec JSON 구조는 similarity/figure_spec.example.json 참고.
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

# dataviz 스킬 검증 통과 색(light, surface #fcfcfb): 범주 2색 + '해당 없음' 중립색
CAT = {
    "중첩": ("#eb6834", "대상 중첩 검토 필요"),
    "유사": ("#2a78d6", "대상 유사, 지원수단 상이"),
    "없음": ("#8a8982", "겹치는 기존사업 없음"),
}
FONT_DIR = Path(__file__).with_name("assets") / "fonts"


def font_face_css(font_dir: Path) -> str:
    out = []
    for w in (400, 500, 700):
        for sub in ("korean", "latin"):
            f = font_dir / f"noto-sans-kr-{sub}-{w}-normal.woff2"
            if not f.exists():
                continue
            b64 = base64.b64encode(f.read_bytes()).decode()
            out.append(
                "@font-face{font-family:'Noto Sans KR';font-style:normal;font-weight:%d;"
                "font-display:block;src:url(data:font/woff2;base64,%s) format('woff2')}" % (w, b64))
    return "\n".join(out)


def trim(png: Path, pad: int = 26) -> None:
    """캔버스 아래쪽 배경 여백을 잘라 내용 높이에 맞춘다(여백 pad 만 남김)."""
    from PIL import Image
    im = Image.open(png).convert("RGB")
    w, h = im.size
    bg = im.getpixel((2, h - 2))
    last = 0
    for y in range(h - 1, -1, -1):
        row = im.crop((0, y, w, y + 1)).getcolors(w) or []
        if any(c != bg for _, c in row):
            last = y
            break
    im.crop((0, 0, w, min(h, last + pad * 2))).save(png)


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def collect_rows(xlsx: Path, spec: dict) -> list[dict]:
    """내역 시트가 있으면 내역별 1위, 없으면 전체 상위 N 을 행으로 만든다."""
    x = pd.ExcelFile(xlsx)
    notes = spec.get("행주석", {})
    rows = []
    unit_sheets = [s for s in x.sheet_names if s.startswith("내역")]
    if unit_sheets:
        for sh in unit_sheets:
            d = pd.read_excel(x, sh)
            r = d.iloc[0]
            label = sh.split("_", 1)[1] if "_" in sh else sh
            n = notes.get(label, {})
            rows.append({"label": label, "value": float(r["종합유사도(0~100)"]),
                         "name": n.get("이름", str(r["공고이름"])),
                         "desc": n.get("설명", f"{r['부처']} · {str(r.get('시행방법', '')) or '기존사업'}"),
                         "cat": n.get("분류", "유사")})
    else:
        d = pd.read_excel(x, "전체")
        for _, r in d.head(int(spec.get("행수", 7))).iterrows():
            key = str(r["공고이름"])
            n = notes.get(key, {})
            rows.append({"label": n.get("축약", key[:22]), "value": float(r["종합유사도(0~100)"]),
                         "name": n.get("이름", key), "desc": n.get("설명", f"{r['부처']} · {r.get('시행방법','')}"),
                         "cat": n.get("분류", "유사")})
    rows.sort(key=lambda z: -z["value"])
    return rows


def build_html(spec: dict, rows: list[dict], stats: dict, font_dir: Path) -> str:
    vals = [r["value"] for r in rows]
    import math
    lo = spec.get("축최소") or (math.floor(min(vals)) - 1)
    hi = spec.get("축최대") or (lo + math.ceil((math.ceil(max(vals)) + 1 - lo) / 4) * 4)
    span = max(hi - lo, 4)
    ticks = [lo + i * (span // 4) for i in range(5)]

    bars = []
    for r in rows:
        color = CAT[r["cat"]][0]
        pct = (r["value"] - lo) / span * 100
        bars.append(f"""
        <div class="row">
          <div class="rlabel">{esc(r['label'])}</div>
          <div class="track">
            <div class="line" style="width:{pct:.2f}%;background:{color}"></div>
            <div class="dot" style="left:{pct:.2f}%;background:{color}"></div>
          </div>
          <div class="rval" style="color:{color}">{r['value']:.1f}</div>
          <div class="rname"><b>{esc(r['name'])}</b><span>{esc(r['desc'])}</span></div>
        </div>""")

    used = []
    for k in ("중첩", "유사", "없음"):
        if any(r["cat"] == k for r in rows):
            used.append(f'<i class="lg"><em style="background:{CAT[k][0]}"></em>{esc(CAT[k][1])}</i>')

    cards = "".join(f"""
      <div class="card">
        <div class="chead"><span class="tag">{esc(c['태그'])}</span><b>{esc(c['제목'])}</b></div>
        <p>{esc(c['본문'])}</p>
        <div class="cnum">{esc(c.get('수치',''))}</div>
      </div>""" for c in spec["유형카드"])

    note = spec.get("비고")
    note_html = f'<div class="note"><b>{esc(note["제목"])}</b> · {esc(note["본문"])}</div>' if note else ""

    imps = "".join(f"""
      <div class="imp"><b>{esc(i['제목'])}</b><p>{esc(i['본문'])}</p></div>""" for i in spec["시사점"])

    canvas = spec.get("세로", 950)
    lw = spec.get("라벨폭", 104)
    nw = spec.get("설명폭", 300)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
{font_face_css(font_dir)}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1680px;min-height:{canvas}px;background:#fcfcfb;font-family:'Noto Sans KR',sans-serif;
 color:#0b0b0b;-webkit-font-smoothing:antialiased;padding:34px 40px 26px}}
.eyebrow{{font-size:15px;font-weight:500;color:#52514e;letter-spacing:-.01em}}
h1{{font-size:38px;font-weight:700;letter-spacing:-.035em;margin:9px 0 10px;line-height:1.18}}
.sub{{font-size:16px;color:#52514e;line-height:1.5;letter-spacing:-.012em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:24px}}
h2{{font-size:17px;font-weight:700;margin-bottom:13px;letter-spacing:-.02em}}
.panel{{border:1px solid #e3e2dd;border-radius:11px;padding:19px 21px;background:#fff}}
.legend{{display:flex;gap:17px;margin-bottom:15px;font-size:12.5px;color:#52514e}}
.lg{{display:flex;align-items:center;gap:6px;font-style:normal}}
.lg em{{width:9px;height:9px;border-radius:50%;display:block}}
.row{{display:grid;grid-template-columns:{lw}px 1fr 50px {nw}px;align-items:center;gap:11px;
 padding:9px 0;border-bottom:1px solid #f1f0ec}}
.row:last-child{{border-bottom:0}}
.rlabel{{font-size:14px;font-weight:500;letter-spacing:-.025em;word-break:keep-all}}
.track{{position:relative;height:13px}}
.track:before{{content:'';position:absolute;left:0;right:0;top:5.5px;height:2px;background:#eceae5}}
.line{{position:absolute;left:0;top:5.5px;height:2px;opacity:.5}}
.dot{{position:absolute;top:0;width:13px;height:13px;border-radius:50%;transform:translateX(-50%);
 box-shadow:0 0 0 2px #fff}}
.rval{{font-size:19px;font-weight:700;text-align:right;letter-spacing:-.02em;font-variant-numeric:tabular-nums}}
.rname{{font-size:12.5px;line-height:1.4}}
.rname b{{display:block;font-weight:500;letter-spacing:-.015em}}
.rname span{{color:#6d6c66;font-size:11.5px}}
.axis{{display:grid;grid-template-columns:{lw}px 1fr 50px {nw}px;gap:11px;margin-top:5px}}
.ax{{grid-column:2;display:flex;justify-content:space-between;font-size:11px;color:#8a8982;
 font-variant-numeric:tabular-nums}}
.foot{{font-size:11.5px;color:#8a8982;line-height:1.55;margin-top:11px}}
.card{{border:1px solid #e3e2dd;border-radius:11px;padding:15px 17px;background:#fff;margin-bottom:11px}}
.chead{{display:flex;align-items:center;gap:9px;margin-bottom:7px}}
.tag{{font-size:11px;font-weight:500;color:#2a78d6;background:#eaf2fc;border-radius:4px;padding:3px 8px}}
.chead b{{font-size:14.5px;font-weight:700;letter-spacing:-.022em}}
.card p{{font-size:13px;color:#3f3e3a;line-height:1.52;letter-spacing:-.012em}}
.cnum{{font-size:12px;color:#6d6c66;margin-top:7px;font-variant-numeric:tabular-nums}}
.note{{background:#f4f6f9;border-radius:9px;padding:12px 15px;font-size:12.5px;color:#3f3e3a;line-height:1.5}}
.note b{{color:#1f3a5f}}
.band{{background:#1c2b45;border-radius:11px;padding:19px 24px;margin-top:22px;color:#fff}}
.band h2{{color:#fff;margin-bottom:13px;font-size:16px}}
.imps{{display:grid;grid-template-columns:repeat(3,1fr);gap:26px}}
.imp b{{font-size:14px;font-weight:700;display:block;margin-bottom:5px;letter-spacing:-.02em}}
.imp p{{font-size:12.5px;color:#c9d2e0;line-height:1.52;letter-spacing:-.012em}}
.src{{font-size:11.5px;color:#8a8982;margin-top:15px;line-height:1.5}}
</style></head><body>
<div class="eyebrow">{esc(spec['머리말'])}</div>
<h1>{esc(spec['헤드라인'])}</h1>
<div class="sub">{esc(spec['부제'])}</div>
<div class="grid">
 <div>
  <h2>① {esc(spec['좌측제목'])}</h2>
  <div class="panel">
   <div class="legend">{''.join(used)}</div>
   {''.join(bars)}
   <div class="axis"><div class="ax">{''.join(f'<span>{t:.0f}</span>' for t in ticks)}</div></div>
   <div class="foot">{esc(spec['차트주석'])}<br>기존사업 {stats['n']:,}개 단위 전체 평균 {stats['mean']:.1f} · 전체 1위는 {esc(stats['top'])} {stats['topv']:.1f}</div>
  </div>
 </div>
 <div>
  <h2>② {esc(spec['우측제목'])}</h2>
  {cards}
  {note_html}
 </div>
</div>
<div class="band"><h2>③ 정책 시사점</h2><div class="imps">{imps}</div></div>
<div class="src">※ 유사도는 검토 대상을 좁히는 선별 지표이며 중복 판정이 아님 | 자료: {esc(spec['자료'])}</div>
</body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--font-dir", default=str(FONT_DIR), help="Noto Sans KR woff2 폴더(없으면 시스템 글꼴 사용)")
    ap.add_argument("--chrome", default="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
                    help="headless 렌더링에 쓸 Chromium 실행 파일")
    a = ap.parse_args()

    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    xlsx = Path(a.xlsx)
    rows = collect_rows(xlsx, spec)
    whole = pd.read_excel(xlsx, "전체")
    s = whole["종합유사도(0~100)"]
    stats = {"n": len(whole), "mean": float(s.mean()),
             "top": str(whole.iloc[0]["공고이름"]), "topv": float(s.max())}

    html = build_html(spec, rows, stats, Path(a.font_dir))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / "figure.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run([a.chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                        "--hide-scrollbars", "--force-device-scale-factor=2",
                        "--default-background-color=FCFCFBFF",
                        f"--screenshot={out}", f"--window-size=1680,{spec.get('세로', 1400)}",
                        page.as_uri()], check=True, capture_output=True)
    trim(out, pad=int(spec.get("아래여백", 26)))
    print(f"저장 {out} ({out.stat().st_size // 1024}KB), 행 {len(rows)}개")


if __name__ == "__main__":
    main()
