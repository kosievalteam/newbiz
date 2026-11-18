# -*- coding: utf-8 -*-
"""경북 식품산업과 신규 협의사업 4건 상호 직접비교 산출물.
기존 2026-053↔2026-103 직접비교 산출물(7개 시트)의 구조·열 이름·열 순서를 그대로 쓰고,
비교 대상이 1쌍 → 6쌍이므로 '비교쌍' 열만 선두에 추가한다. 산식·가중치·점수는 direct_compare.py 산출값 그대로."""
import json, sys
sys.path.insert(0, ".")
import pandas as pd
from data_cond import COR, COND
from data_dup import DUP
from data_log import LOG
from decimal import Decimal, ROUND_HALF_UP

AX = ["사업목적", "지원내용", "지원대상", "전달체계"]
RAW_W = {"사업목적": 20, "지원내용": 30, "지원대상": 30, "전달체계": 15}
W = {k: v / sum(RAW_W.values()) * 100 for k, v in RAW_W.items()}
CODE = ["276", "277", "278", "0279"]
NAME = {"276": "2026-276 식품창업 스타트업 챌린지", "277": "2026-277 식품창업기업 스케일업 지원",
        "278": "2026-278 식품 스타트업 투자브릿지 지원", "0279": "2026-0279 식품창업 글로벌 브랜드 육성"}
SHORT = {"276": "2026-276", "277": "2026-277", "278": "2026-278", "0279": "2026-0279"}
PAIRS = [("276","277"),("276","278"),("276","0279"),("277","278"),("277","0279"),("278","0279")]
PROF = {c: json.load(open(f"../case{n}/profile.json", encoding="utf-8")) for c, n in
        [("276",36),("277",37),("278",38),("0279",39)]}
R = {}
for a, b in PAIRS:
    R[(a,b)] = {(r["A단위"], r["B단위"]): r for r in
                json.load(open(f"직접비교_2026-{a}_2026-{b}.json", encoding="utf-8"))["rows"]}
def q(x, n): return float(Decimal(repr(float(x))).quantize(Decimal("1." + "0"*n), rounding=ROUND_HALF_UP))
def pl(a, b): return f"{SHORT[a]} ↔ {SHORT[b]}"

# 1) 종합비교표 (추가 시트)
rows = []
for a, b in PAIRS:
    r = R[(a,b)][("전체","전체")]
    best = max(R[(a,b)].values(), key=lambda z: z["종합유사도(0~100)"])
    rows.append({"비교쌍": pl(a,b), "사업A": NAME[a], "사업B": NAME[b],
                 "전체×전체 종합 유사도(0~100)": q(r["종합유사도(0~100)"],2),
                 **{f"{ax} 코사인": q(r[ax+"_유사도"],4) for ax in AX},
                 "최고 기능 조합": f'{best["A단위"]} × {best["B단위"]}',
                 "최고 기능 조합 유사도": q(best["종합유사도(0~100)"],2),
                 "전체쌍 대비 증감": q(best["종합유사도(0~100)"] - r["종합유사도(0~100)"],2)})
sheet_summary = pd.DataFrame(rows).sort_values("전체×전체 종합 유사도(0~100)", ascending=False)
mat = pd.DataFrame(index=[SHORT[c] for c in CODE], columns=[SHORT[c] for c in CODE], dtype=object)
for c in CODE: mat.loc[SHORT[c], SHORT[c]] = "—"
for a, b in PAIRS:
    v = q(R[(a,b)][("전체","전체")]["종합유사도(0~100)"], 2)
    mat.loc[SHORT[a], SHORT[b]] = v; mat.loc[SHORT[b], SHORT[a]] = v
mat = mat.reset_index().rename(columns={"index": "전체×전체 종합 유사도"})

# 2) 전체_직접유사도
rows = []
for a, b in PAIRS:
    r = R[(a,b)][("전체","전체")]
    rows += [{"비교쌍": pl(a,b), "항목": "비교쌍", "값": f"사업A {SHORT[a]} 전체 ↔ 사업B {SHORT[b]} 전체"},
             {"비교쌍": pl(a,b), "항목": "종합 유사도(0~100)", "값": q(r["종합유사도(0~100)"],2)},
             {"비교쌍": pl(a,b), "항목": "산식", "값": "Σ(정규화 가중치 × 축별 코사인 유사도)"},
             {"비교쌍": pl(a,b), "항목": "가중치 합", "값": 100},
             {"비교쌍": pl(a,b), "항목": "대칭성", "값": "대칭(네 사업 모두 신규사업 축 서술을 그대로 인코딩 → 코사인은 대칭). 전치 실증 완료"},
             {"비교쌍": pl(a,b), "항목": "A 코퍼스 최고점(참고)", "값": COR[a]},
             {"비교쌍": pl(a,b), "항목": "B 코퍼스 최고점(참고)", "값": COR[b]},
             {"비교쌍": pl(a,b), "항목": "5단계 등급·지표(안) 환산점수", "값": "미산출 — 코퍼스 내 z-점수로 정의되므로 4건 상호비교에서는 평균·표준편차가 성립하지 않음"},
             {"비교쌍": pl(a,b), "항목": "단위 조합 수", "값": len(R[(a,b)])}]
sheet_total = pd.DataFrame(rows)

# 3) 분석축별_유사도
rows = []
for a, b in PAIRS:
    r = R[(a,b)][("전체","전체")]; tot = r["종합유사도(0~100)"]
    for ax in AX:
        wp = r[ax+"_유사도"] * W[ax]
        rows.append({"비교쌍": pl(a,b), "분석축": ax, "참고2 원가중치": RAW_W[ax],
                     "정규화 가중치(합100)": q(W[ax],2), "코사인 유사도": q(r[ax+"_유사도"],4),
                     "가중점수": q(wp,2), "종합 기여율(%)": q(wp/tot*100,1)})
sheet_axis = pd.DataFrame(rows)

# 4) 기능별_교차유사도
rows = []
for a, b in PAIRS:
    base = R[(a,b)][("전체","전체")]["종합유사도(0~100)"]
    for (ua, ub), r in R[(a,b)].items():
        rows.append({"비교쌍": pl(a,b), "A 단위": ua, "B 단위": ub,
                     "종합 유사도(0~100)": q(r["종합유사도(0~100)"],2),
                     **{f"{ax} 코사인": q(r[ax+"_유사도"],4) for ax in AX},
                     "전체쌍 대비 증감": q(r["종합유사도(0~100)"] - base,2)})
sheet_cross = pd.DataFrame(rows)

# 5) 원문_비교근거
rows = []
for c in CODE:
    for u, spec in PROF[c]["units"].items():
        for ax in AX:
            rows.append({"사업": NAME[c], "단위": u, "분석축": ax, "임베딩에 투입한 축 서술(원자료 기반)": spec[ax]})
sheet_src = pd.DataFrame(rows)

sheet_cond = pd.DataFrame(COND)
sheet_dup = pd.DataFrame(DUP)
sheet_log = pd.DataFrame(LOG)

OUT = "경상북도_신규사업4건_유사도_직접비교.xlsx"
with pd.ExcelWriter(OUT, engine="openpyxl") as w:
    sheet_summary.to_excel(w, sheet_name="종합비교표", index=False)
    mat.to_excel(w, sheet_name="종합비교표_매트릭스", index=False)
    sheet_total.to_excel(w, sheet_name="전체_직접유사도", index=False)
    sheet_axis.to_excel(w, sheet_name="분석축별_유사도", index=False)
    sheet_cross.to_excel(w, sheet_name="기능별_교차유사도", index=False)
    sheet_src.to_excel(w, sheet_name="원문_비교근거", index=False)
    sheet_cond.to_excel(w, sheet_name="지원조건_비교", index=False)
    sheet_dup.to_excel(w, sheet_name="실질적_중복검토", index=False)
    sheet_log.to_excel(w, sheet_name="검증_로그", index=False)
print("저장", OUT)
for n, d in [("종합비교표", sheet_summary), ("전체_직접유사도", sheet_total), ("분석축별_유사도", sheet_axis),
             ("기능별_교차유사도", sheet_cross), ("원문_비교근거", sheet_src), ("지원조건_비교", sheet_cond),
             ("실질적_중복검토", sheet_dup), ("검증_로그", sheet_log)]:
    print(f"  {n}: {d.shape}")
