# -*- coding: utf-8 -*-
"""direct_figure.py 와 동일한 HTML(=report_figure.build_html + 하단 문장 치환)을 만들고,
렌더링만 report_figure.py 가 쓰는 chrome 인자(--headless=new)로 수행한다.
기존 파일은 수정하지 않으며 그림 내용·배치·수치는 direct_figure.py 결과와 동일하다."""
import json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/home/user/newbiz/similarity")
import report_figure as RF

spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
rows_src = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
out = Path(sys.argv[3])
notes = spec["행주석"]
rows = [{"label": notes[k]["축약"], "value": v, "name": notes[k]["이름"],
         "desc": notes[k]["설명"], "cat": notes[k]["분류"]} for k, v in rows_src["rows"].items()]
rows.sort(key=lambda z: -z["value"])
stats = rows_src["stats"]
html = RF.build_html(spec, rows, stats, RF.FONT_DIR)
old = (f"기존사업 {stats['n']:,}개 단위 전체 평균 {RF.f1(stats['mean'])} · "
       f"전체 1위는 {RF.esc(stats['top'])} {RF.f1(stats['topv'])}")
assert old in html, "하단 문장 치환 실패"
html = html.replace(old, RF.esc(rows_src["foot"]))
with tempfile.TemporaryDirectory() as td:
    h = Path(td) / "f.html"; h.write_text(html, encoding="utf-8")
    subprocess.run(["/opt/pw-browsers/chromium-1194/chrome-linux/chrome", "--headless=new",
                    "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                    "--force-device-scale-factor=2", "--default-background-color=FCFCFBFF",
                    f"--screenshot={out}", f"--window-size=1680,{spec.get('세로', 1400)}",
                    h.as_uri()], check=True, capture_output=True)
RF.trim(out, int(spec.get("아래여백", 26)))
print(f"저장 {out} ({out.stat().st_size // 1024}KB), 행 {len(rows)}개")
