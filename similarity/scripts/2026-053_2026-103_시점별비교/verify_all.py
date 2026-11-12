"""PNG·DOCX(md)·XLSX 3자 수치 일치 및 지시서 8장 완료조건 점검."""
import json, re, csv
from pathlib import Path
import pandas as pd
ok, bad = 0, []
def chk(n, c, extra=""):
    global ok
    if c: ok += 1
    else: bad.append(f"{n} {extra}")

md = Path("2026-053_2026-103_시점별_유사중복_비교_검토보고서.md").read_text(encoding="utf-8")
html = Path("fig.html").read_text(encoding="utf-8")
X = pd.ExcelFile("2026-053_2026-103_시점별_유사중복_비교_산출결과.xlsx")
fr = json.load(open("figrows.json", encoding="utf-8"))
dj = json.load(open("direct.json", encoding="utf-8"))
D = {f'{r["A단위"]}|{r["B단위"]}': r for r in dj["rows"]}["전체|전체"]

# --- 1. 산출물 존재
for f, lo in (("2026-053_2026-103_시점별_유사중복_비교_보고그림.png", 300_000),
              ("2026-053_2026-103_시점별_유사중복_비교_검토보고서.docx", 15_000),
              ("2026-053_2026-103_시점별_유사중복_비교_산출결과.xlsx", 80_000)):
    chk(f"산출물 {f[-20:]}", Path(f).stat().st_size > lo)

# --- 2. 필수 시트 10종
need = ["기준시점_원천목록","A시점_전체순위","B시점_전체순위","B시점_A후보확인","AB_직접비교",
        "AB_축별유사도","AB_기능교차비교","객관적_원문근거","제외자료_오염검증","수치_재현검증"]
for s in need: chk(f"시트 {s}", s in X.sheet_names)

# --- 3. 후보군 건수 (3자 일치)
src = pd.read_excel(X, "기준시점_원천목록")
nA = int((src["비교①(A, 협의번호≤053) 포함"] == "포함").sum())
nB = int((src["비교②(B, 협의번호≤103) 포함"] == "포함").sum())
rA, rB = pd.read_excel(X, "A시점_전체순위"), pd.read_excel(X, "B시점_전체순위")
chk("비교① 37건 (원천목록=순위표=md=png)", nA == len(rA) == 37 and "37건" in md and "37건" in html, f"{nA}/{len(rA)}")
chk("비교② 70건 (원천목록=순위표=md=png)", nB == len(rB) == 70 and "70건" in md and "70건" in html, f"{nB}/{len(rB)}")
chk("원천목록 91행", len(src) == 91, str(len(src)))
chk("①⊂② 누적구조", set(src[src["비교①(A, 협의번호≤053) 포함"]=="포함"]["협의번호"]) <= set(src[src["비교②(B, 협의번호≤103) 포함"]=="포함"]["협의번호"]))
chk("A 자기제외", "2026-053" not in set(rA["협의번호"]))
chk("B 자기제외", "2026-103" not in set(rB["협의번호"]))
chk("B풀에 A 포함", "2026-053" in set(rB["협의번호"]))
chk("협의번호>103 전건 제외", all(int(n.split("-")[1]) <= 103 for n in set(rA["협의번호"]) | set(rB["협의번호"])))

# --- 4. 핵심 수치 3자 일치
def has(txt, *vals): return all(v in txt for v in vals)
a3 = rB[rB["협의번호"] == "2026-053"].iloc[0]
chk("A 순위 3위", int(a3["순위"]) == 3 == fr["비교B"]["A순위"] and "3위 / 70건" in md and "3위 / 70건" in html)
chk("A 점수 60.79/60.8", abs(float(a3["종합유사도(0~100)"]) - 60.79) < .005 and "60.79" in md and "60.8" in html)
chk("비교① 1위 63.25/63.3", abs(float(rA["종합유사도(0~100)"].max()) - 63.25) < .005 and "63.25" in md and "63.3" in html)
chk("비교② 1위 67.65/67.7", abs(float(rB["종합유사도(0~100)"].max()) - 67.65) < .005 and "67.65" in md and "67.7" in html)
chk("비교① 평균 55.85/55.9", abs(fr["비교A"]["평균"] - 55.85) < .005 and "55.85" in md and "55.9" in html)
chk("비교② 평균 55.36/55.4", abs(fr["비교B"]["평균"] - 55.36) < .005 and "55.36" in md and "55.4" in html)
xd = pd.read_excel(X, "AB_직접비교").iloc[0]
chk("직접 종합 68.08/68.1", abs(float(xd["종합유사도(0~100)"]) - 68.08) < .005 and "68.08" in md and "68.1" in html)
xf = pd.read_excel(X, "AB_기능교차비교")
a3v = float(xf[xf["A 기능단위"] == "기능A3_사업화자금"]["종합유사도(0~100)"].iloc[0])
chk("기능A3×B 71.71/71.7", abs(a3v - 71.71) < .005 and "71.71" in md and "71.7" in html)
xa = pd.read_excel(X, "AB_축별유사도")
for ax, v in (("사업목적", 0.753), ("지원내용", 0.645), ("지원대상", 0.632), ("전달체계", 0.753)):
    r = xa[xa["분석축"] == ax].iloc[0]
    chk(f"축 {ax} {v}", abs(float(r["A↔B 코사인"]) - v) < .0006 and f"{v}" in md and f"{v:.3f}" in html)
chk("A 대상축 0.3804/0.380/0.38", abs(float(a3["지원대상_유사도"]) - 0.3804) < .0001 and "0.3804" in md and "0.380" in html)

# --- 5. 미산출 표기
chk("등급 미산출 — xlsx", (xa["5단계 등급"] == "미산출").all() and xd["등급·참고2 지표점수"] == "미산출")
chk("등급 미산출 — md·png", "미산출" in md and "미산출" in html)

# --- 6. 제외·오염
cj = json.load(open("contam.json", encoding="utf-8"))
chk("후보 91건 오염 0", len(cj["후보"]) == 0, str(len(cj["후보"])))
chk("프로필 오염 0", len(cj["프로필"]) == 0, str(len(cj["프로필"])))
pc = json.load(open("profiles_clean_fn.json", encoding="utf-8"))
flat = " ".join(t for v in pc.values() for u in v["units"].values() for t in u.values())
for banned in ("업력 제한을 두지 않는", "중복지원을 방지할 계획", "대상을 특화", "차별성", "검토의견", "사업간 비교"):
    chk(f"금칙어 부재 '{banned}'", banned not in flat)
chk("오염검증 시트 15행", len(pd.read_excel(X, "제외자료_오염검증")) == 15)

# --- 7. 재현검증
vr = pd.read_excel(X, "수치_재현검증")
chk("재현검증 5건 전부 절대차≤0.005", len(vr) == 5 and (vr["절대차"] <= 0.005).all(), str(vr["절대차"].max()))
chk("재현검증 md 기재", all(s in md for s in ("70.12", "67.52", "0.00123", "0.00445")))

# --- 8. 지시서 완료조건 서술
for key, pat in (("자기 자신 제외 명시", r"자기 자신|자기 제외"),
                 ("A 협의상태 선행 협의요청사업", r"선행 협의요청사업"),
                 ("기존 시행사업과 구분", r"시행·확정(된)? (기존)?사업이? ?아니"),
                 ("미래정보 유입 없음", r"미래정보 유입"),
                 ("모집단 차이 설명", r"3,631"),
                 ("두 점수 경로 구분", r"같은 척도가 아니"),
                 ("중복 과장 금지", r"중복 판정이 아니"),
                 ("기존 산출물 보존", r"수정하지 않았다"),
                 ("접수일 미확인", r"접수일.{0,20}(없|확인하지 못)")):
    chk(f"서술 — {key}", re.search(pat, md) is not None)
chk("png 중복판정 아님 문구", "중복 판정이 아님" in html)
chk("png 선행 협의요청사업", "선행 협의요청사업" in html)

print(f"\n검증 {ok}/{ok + len(bad)} 통과")
for b in bad: print("  ✗", b)
