"""시점별 비교 + 직접 비교 보고그림. 기존 report_figure 의 글꼴·색·트리밍을 그대로 쓴다."""
import csv, json, subprocess, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, "/home/user/newbiz/similarity")
import report_figure as RF
from report_figure import esc, f1, font_face_css, trim

AX = ["사업목적", "지원내용", "지원대상", "전달체계"]
WT = {"사업목적": 21.05, "지원내용": 31.58, "지원대상": 31.58, "전달체계": 15.79}
NAV, RED, BLU, GRY = "#1c2b45", "#c0392b", "#2a78d6", "#8a8982"
ids = {r["공고이름"]: r["협의번호"] for r in csv.DictReader(open("candidates.csv", encoding="utf-8"))}
short = {r["공고이름"]: (r["공고이름"].split(" ", 1)[1] if " " in r["공고이름"] else r["공고이름"]) for r in
         csv.DictReader(open("candidates.csv", encoding="utf-8"))}
direct = {f'{r["A단위"]}|{r["B단위"]}': r for r in json.load(open("direct.json", encoding="utf-8"))["rows"]}
D = direct["전체|전체"]

def top(path, n=8):
    d = pd.read_excel(path, sheet_name="전체").sort_values("종합유사도(0~100)", ascending=False).reset_index(drop=True)
    out = []
    for i, r in d.head(n).iterrows():
        no = ids.get(r["공고이름"], "")
        out.append({"no": no, "부처": r["부처"].split("(")[0][:7],
                    "name": short.get(r["공고이름"], "")[:42],
                    "v": float(r["종합유사도(0~100)"]), "rank": i + 1})
    return out, len(d), float(d["종합유사도(0~100)"].mean())

tA, nA, mA = top("out_A/similarity_scores.xlsx")
tB, nB, mB = top("out_B/similarity_scores.xlsx")
dB = pd.read_excel("out_B/similarity_scores.xlsx", sheet_name="전체").sort_values("종합유사도(0~100)", ascending=False).reset_index(drop=True)
ia = int(dB.index[dB["공고이름"].str.startswith("2026-053")][0]); arow = dB.iloc[ia]
if not any(r["no"] == "2026-053" for r in tB):
    tB.append({"no": "2026-053", "부처": "중소벤처기업부", "name": short.get(arow["공고이름"], "")[:42],
               "v": float(arow["종합유사도(0~100)"]), "rank": ia + 1})

def bars(rows, lo, hi, hl=None):
    span = hi - lo
    out = []
    for r in rows:
        on = (hl is not None and r["no"] == hl)
        c = RED if on else (NAV if r["rank"] == 1 else BLU)
        pct = (r["v"] - lo) / span * 100
        out.append(f"""<div class="row{' hl' if on else ''}">
      <div class="rk">{r['rank']}</div>
      <div class="track"><div class="line" style="width:{pct:.2f}%;background:{c}"></div>
        <div class="dot" style="left:{pct:.2f}%;background:{c}"></div></div>
      <div class="rval" style="color:{c}">{f1(r['v'])}</div>
      <div class="rname"><b>{esc(r['name'])}</b><span>{esc(r['no'])} · {esc(r['부처'])}</span></div></div>""")
    ticks = "".join(f"<span>{lo + i * span / 4:.0f}</span>" for i in range(5))
    return "".join(out) + f'<div class="axis"><div class="ax">{ticks}</div></div>'

axrows = "".join(f"""<div class="arow">
   <div class="alab">{esc(ax)}<em>가중치 {WT[ax]}</em></div>
   <div class="track"><div class="line" style="width:{D[ax+'_유사도']*100:.1f}%;background:{NAV}"></div>
     <div class="dot" style="left:{D[ax+'_유사도']*100:.1f}%;background:{NAV}"></div></div>
   <div class="rval">{D[ax+'_유사도']:.3f}</div>
   <div class="awt">가중점수 {D[ax+'_가중점수']:.2f}</div></div>""" for ax in AX)

fn = [("기능A3 사업화자금", "기능A3_사업화자금"), ("전체(사업 단위)", "전체"),
      ("기능A1 성장보육·컨설팅", "기능A1_성장보육컨설팅"), ("기능A2 스케일업", "기능A2_스케일업프로그램")]
fnrows = "".join(f"""<div class="frow{' top' if i == 0 else ''}">
   <div class="flab">{esc(lab)}</div><div class="fbar"><em style="width:{(direct[k+'|전체']['종합유사도(0~100)']-60)/14*100:.1f}%;
     background:{RED if i == 0 else NAV}"></em></div>
   <div class="fval" style="color:{RED if i == 0 else NAV}">{f1(direct[k+'|전체']['종합유사도(0~100)'])}</div></div>"""
      for i, (lab, k) in enumerate(fn))

CARDS = [("제도상 포함관계", "같은 사회적기업이 두 사업의 대상요건을 동시에 충족할 수 있음",
          "A는 사회연대경제기본법(안)의 12개 조직유형 중 성장형 50개사, B는 민간 선투자를 받은 사회적기업 50개소. 사회적기업은 A의 대상유형에 포함되므로 제도상 포함관계가 성립"),
         ("자금 비목", "양측 모두 사업화·제품고도화 자금 보조 — 동일 비목 이중지원 여부는 자료로 판정 불가",
          "A 사업화자금 기업당 최대 2억원(자부담 20%), B 투자금 매칭 보조 기업당 1억원(자부담 없음). 요청서·부속자료에 정산 비목 세부가 없어 같은 활동에 중복 지급되는지는 확인되지 않음"),
         ("중복수혜 배제 규정", "두 사업 모두 요청서에서 확인되지 않음",
          "A·B의 '사업·제도 연계'란이 각각 서식 문구·공란. B 자체점검표의 중복지원 방지 서술은 지시서 2-2에 따라 근거에서 제외했으므로, 배제 규정의 존재를 인정할 근거가 없음(규정 미확인 ≠ 실제 이중지원 발생)")]
cards = "".join(f"""<div class="card"><div class="chead"><span class="tag">{esc(t)}</span><b>{esc(h)}</b></div>
   <p>{esc(b)}</p></div>""" for t, h, b in CARDS)

IMPS = [("확인된 유사성", f"정책목적 축 코사인 {D['사업목적_유사도']:.3f}, 전달체계 {D['전달체계_유사도']:.3f}로 가장 높고, 사업화자금 기능이 B 전체와 {f1(direct['기능A3_사업화자금|전체']['종합유사도(0~100)'])}로 네 단위 중 최고. 두 시점 후보군에서 1위는 모두 고용부 2026-036 사회적기업 창업지원으로, 사회적기업 사업화자금 영역의 후보 밀집이 확인됨"),
        ("인정 가능한 차별성", "B는 민간 선(先)투자 유치가 지원대상 요건 자체이고 자금 매칭만 제공. A는 선투자를 요건으로 두지 않고 성장성·사회성 평가로 선발해 보육·컨설팅·스케일업과 묶은 패키지를 제공하며 자부담 20%를 부과. 전달체계도 A는 권역별 민간 AC 위탁 선발, B는 진흥원 직접 집행"),
        ("추가 확인사항", "① 두 사업의 정산 비목과 선정 제한 규정 ② B의 투자금 매칭 비율(요청서 미기재) ③ A의 지원대상 상세란 미기재분 보완 ④ 실제 수혜기업 명부 대조. 이 자료 없이는 중복 가능성을 실제 중복 발생으로 단정할 수 없음")]
imps = "".join(f"""<div class="imp"><b>{esc(t)}</b><p>{esc(b)}</p></div>""" for t, b in IMPS)

html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
{font_face_css(RF.FONT_DIR)}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1680px;background:#fcfcfb;font-family:'Noto Sans KR',sans-serif;color:#0b0b0b;
 -webkit-font-smoothing:antialiased;padding:34px 40px 26px}}
.eyebrow{{font-size:15px;font-weight:500;color:#52514e;letter-spacing:-.01em}}
h1{{font-size:37px;font-weight:700;letter-spacing:-.035em;margin:9px 0 10px;line-height:1.17}}
.sub{{font-size:15.5px;color:#52514e;line-height:1.5;letter-spacing:-.012em;max-width:1500px}}
h2{{font-size:17px;font-weight:700;margin-bottom:12px;letter-spacing:-.02em}}
h2 em{{font-style:normal;font-weight:500;color:#6d6c66;font-size:13.5px;margin-left:8px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:24px}}
.panel{{border:1px solid #e3e2dd;border-radius:11px;padding:19px 21px;background:#fff}}
.row{{display:grid;grid-template-columns:26px 1fr 48px 300px;align-items:center;gap:11px;
 padding:8px 0;border-bottom:1px solid #f1f0ec}}
.row.hl{{background:#fdf3f1;border-radius:7px;padding:8px 7px;margin:2px -7px;border-bottom:0}}
.rk{{font-size:12px;color:#8a8982;text-align:right;font-variant-numeric:tabular-nums}}
.row.hl .rk{{color:{RED};font-weight:700}}
.track{{position:relative;height:13px}}
.track:before{{content:'';position:absolute;left:0;right:0;top:5.5px;height:2px;background:#eceae5}}
.line{{position:absolute;left:0;top:5.5px;height:2px;opacity:.5}}
.dot{{position:absolute;top:0;width:13px;height:13px;border-radius:50%;transform:translateX(-50%);box-shadow:0 0 0 2px #fff}}
.rval{{font-size:18.5px;font-weight:700;text-align:right;letter-spacing:-.02em;font-variant-numeric:tabular-nums}}
.rname{{font-size:12.5px;line-height:1.38}}
.rname b{{display:block;font-weight:500;letter-spacing:-.015em;word-break:keep-all}}
.rname span{{color:#6d6c66;font-size:11.5px}}
.axis{{display:grid;grid-template-columns:26px 1fr 48px 300px;gap:11px;margin-top:6px}}
.ax{{grid-column:2;display:flex;justify-content:space-between;font-size:11px;color:#8a8982;font-variant-numeric:tabular-nums}}
.foot{{font-size:11.5px;color:#8a8982;line-height:1.55;margin-top:11px}}
.foot b{{color:#3f3e3a;font-weight:500}}
.wide{{display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:24px}}
.arow{{display:grid;grid-template-columns:150px 1fr 56px 112px;align-items:center;gap:11px;
 padding:9px 0;border-bottom:1px solid #f1f0ec}}
.alab{{font-size:13.5px;font-weight:500;letter-spacing:-.02em}}
.alab em{{font-style:normal;display:block;font-size:11px;color:#8a8982;font-weight:400}}
.awt{{font-size:11.5px;color:#6d6c66;text-align:right;font-variant-numeric:tabular-nums}}
.tot{{display:flex;align-items:baseline;gap:11px;margin-top:14px;padding-top:13px;border-top:2px solid #1c2b45}}
.tot b{{font-size:14px;letter-spacing:-.02em}}
.tot strong{{font-size:30px;font-weight:700;color:{NAV};letter-spacing:-.03em;font-variant-numeric:tabular-nums}}
.tot span{{font-size:11.5px;color:#8a8982;line-height:1.45}}
.frow{{display:grid;grid-template-columns:168px 1fr 48px;align-items:center;gap:11px;padding:8px 0}}
.flab{{font-size:13px;letter-spacing:-.02em}}
.frow.top .flab{{font-weight:700}}
.fbar{{height:9px;background:#f1f0ec;border-radius:5px;overflow:hidden}}
.fbar em{{display:block;height:9px;border-radius:5px}}
.fval{{font-size:17px;font-weight:700;text-align:right;font-variant-numeric:tabular-nums;letter-spacing:-.02em}}
.card{{border:1px solid #e3e2dd;border-radius:11px;padding:15px 17px;background:#fff;margin-bottom:11px}}
.chead{{display:flex;align-items:center;gap:9px;margin-bottom:7px}}
.tag{{font-size:11px;font-weight:500;color:#2a78d6;background:#eaf2fc;border-radius:4px;padding:3px 8px;white-space:nowrap}}
.chead b{{font-size:14px;font-weight:700;letter-spacing:-.022em;word-break:keep-all}}
.card p{{font-size:12.5px;color:#3f3e3a;line-height:1.52;letter-spacing:-.012em}}
.note{{background:#f4f6f9;border-radius:9px;padding:13px 16px;font-size:12.5px;color:#3f3e3a;line-height:1.55;margin-top:14px}}
.note b{{color:#1f3a5f}}
.band{{background:{NAV};border-radius:11px;padding:19px 24px;margin-top:22px;color:#fff}}
.band h2{{color:#fff;margin-bottom:13px;font-size:16px}}
.imps{{display:grid;grid-template-columns:repeat(3,1fr);gap:26px}}
.imp b{{font-size:14px;font-weight:700;display:block;margin-bottom:5px;letter-spacing:-.02em}}
.imp p{{font-size:12.5px;color:#c9d2e0;line-height:1.52;letter-spacing:-.012em}}
.src{{font-size:11.5px;color:#8a8982;margin-top:15px;line-height:1.55}}
</style></head><body>
<div class="eyebrow">2026년 중소기업지원사업 사전협의 · 유사·중복성 검토 (협의번호 기준 시점별 누적 비교)</div>
<h1>사회적기업 사업화자금 영역에서 두 부처 신규사업이 겹친다 — 중기부 2026-053 ↔ 고용부 2026-103</h1>
<div class="sub">협의요청서와 그 부속자료만 입력으로 사용하고, 사업간 비교표·검토의견서·종합의견·요청기관의 유사중복 자체점검 판단은 전면 제외한 뒤 기존 분석 방법론(BAAI/bge-m3, 4개 축, 가중치 21.05·31.58·31.58·15.79)을 그대로 적용했다. 비교 대상은 사용자 지정에 따라 <b>협의번호의 숫자 부분</b>으로만 선정했고, 협의번호를 실제 접수일이나 시행시점으로 해석하지 않는다.</div>
<div class="grid">
 <div>
  <h2>① 비교 A — 중기부 2026-053 사회연대경제기업 성장지원<em>협의번호 ≤053, 자기 제외 {nA}건</em></h2>
  <div class="panel">{bars(tA, 50, 66)}
   <div class="foot">상위 8개. 후보 {nA}건 평균 <b>{f1(mA)}</b> · 1위 <b>고용부 2026-036 사회적기업 창업지원 {f1(tA[0]['v'])}</b><br>
    A의 기능별로 보면 <b>기능A3 사업화자금</b>이 2026-036과 <b>68.9</b>로 전 기능·전 후보 중 최고값 (기능A1 61.9 · 기능A2 58.0)</div></div></div>
 <div>
  <h2>② 비교 B — 고용부 2026-103 임팩트 투자연계<em>협의번호 ≤103, 자기 제외 {nB}건 (A 포함)</em></h2>
  <div class="panel">{bars(tB, 50, 70, hl="2026-053")}
   <div class="foot">상위 8개 + 사업 A. 후보 {nB}건 평균 <b>{f1(mB)}</b> · 1위 <b>고용부 2026-036 {f1(tB[0]['v'])}</b><br>
    <b>사업 A는 {ia + 1}위 / {nB}건, 종합 {f1(float(arow['종합유사도(0~100)']))}</b> (목적 {arow['사업목적_유사도']:.3f} · 내용 {arow['지원내용_유사도']:.3f} · 대상 {arow['지원대상_유사도']:.3f} · 전달 {arow['전달체계_유사도']:.3f}) — A는 요청서 접수 단계의 <b>선행 협의요청사업</b>이며 시행·확정 사업이 아니다</div></div></div>
</div>
<div class="wide">
 <div>
  <h2>③ A ↔ B 직접 비교<em>양측 모두 신규사업 프로필 경로 · 별도 산출</em></h2>
  <div class="panel">{axrows}
   <div class="tot"><b>종합유사도</b><strong>{f1(D['종합유사도(0~100)'])}</strong>
    <span>Σ 가중치 × 축별 코사인 (0~100)<br>5단계 등급·참고2 지표점수는 <b>미산출</b> — 코퍼스 내 z-점수로 정의된 규칙이어서 2건 비교에 적용 불가</span></div>
   <div style="margin-top:17px">{fnrows}</div>
   <div class="foot">기능 교차비교(60~74 구간). B는 기존 기능 분리 기준상 단일 기능이어서 A의 4단위 × B 전체로 산출.<br>
    <b>② 비교 B 안의 A 점수({f1(float(arow['종합유사도(0~100)']))})와 이 직접비교 점수({f1(D['종합유사도(0~100)'])})는 같은 척도가 아니다.</b> ②는 A가 후보 표의 한 행으로 들어가 요청서 란을 조립한 텍스트로, ③은 A·B 모두 축별 서술 프로필로 인코딩된다. 특히 A의 요청서 지원대상 상세란이 미기재여서 ②의 대상 축 {arow['지원대상_유사도']:.2f}는 자료 공백의 결과다</div></div></div>
 <div>
  <h2>④ 핵심 중복 쟁점</h2>
  {cards}
  <div class="note"><b>기준시점·모집단 한계</b> · 요청서와 HWP 메타데이터에 접수일·협의완료일이 없어 실제 접수 순서는 확인하지 못했다. 비교군은 제공된 자료에 요청서가 포함된 2026년 중앙부처 협의사업 91건(협의번호 2026-008~168)에서 협의번호로만 선정했고, 이 범위 밖 협의사업의 누락 가능성은 배제할 수 없다. 지원대상 상세란이 미기재인 사업은 비교 A 37건 중 7건, 비교 B 70건 중 11건(사업 A 포함)이다.</div></div>
</div>
<div class="band"><h2>⑤ 검토 요지</h2><div class="imps">{imps}</div></div>
<div class="src">※ 유사도는 검토 대상을 좁히는 선별 지표이며 중복 판정이 아님. 요청기관·검토자의 유사중복 판단은 산출과 해석 근거에서 제외함 | 자료: 2026년 중앙부처 사전협의 요청서 및 부속자료 91건(협의번호 2026-008~168) | 산식·가중치·분석축·전처리 불변, 기존 산출물 재현검증 5건 모두 절대차 0.005 이하</div>
</body></html>"""
Path("fig.html").write_text(html, encoding="utf-8")
out = Path("2026-053_2026-103_시점별_유사중복_비교_보고그림.png")
subprocess.run(["/opt/pw-browsers/chromium-1194/chrome-linux/chrome", "--headless", "--no-sandbox",
                "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                f"--screenshot={out}", "--window-size=1680,2050",
                "file://" + str(Path("fig.html").resolve())], check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
trim(out)
print("저장:", out, out.stat().st_size // 1024, "KB")
json.dump({"비교A": {"n": nA, "평균": round(mA, 2), "top": tA}, "비교B": {"n": nB, "평균": round(mB, 2), "top": tB,
           "A순위": ia + 1, "A점수": round(float(arow["종합유사도(0~100)"]), 2)},
           "직접": {k: v for k, v in direct.items()}}, open("figrows.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
