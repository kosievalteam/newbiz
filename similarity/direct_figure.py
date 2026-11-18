"""직접 비교 보고그림 — 기존 report_figure 의 디자인·렌더링을 그대로 호출하고
하단 자동 문장 한 줄만 비교쌍 문맥에 맞게 바꿔 출력한다(기존 파일은 수정하지 않음)."""
import json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/home/user/newbiz/similarity")
import report_figure as RF     # 기존 그림 생성기

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
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["/opt/pw-browsers/chromium-1194/chrome-linux/chrome", "--headless", "--no-sandbox",
                    "--hide-scrollbars", "--force-device-scale-factor=2", "--window-size=1680,1200",
                    f"--screenshot={out}", h.as_uri()], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
RF.trim(out, 24)
print(f"저장 {out} ({out.stat().st_size // 1024}KB), 행 {len(rows)}개")
