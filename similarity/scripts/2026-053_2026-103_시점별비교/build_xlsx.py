import json, csv
from pathlib import Path
import pandas as pd, numpy as np
AX = ["사업목적", "지원내용", "지원대상", "전달체계"]
W = {"사업목적": 21.05, "지원내용": 31.58, "지원대상": 31.58, "전달체계": 15.79}
ids = {r["공고이름"]: r["협의번호"] for r in csv.DictReader(open("candidates.csv", encoding="utf-8"))}
blank = set(json.load(open("blank_target.json", encoding="utf-8")))
direct = json.load(open("direct.json", encoding="utf-8"))
rows = {f'{r["A단위"]}|{r["B단위"]}': r for r in direct["rows"]}
OUT = Path("2026-053_2026-103_시점별_유사중복_비교_산출결과.xlsx")

def rank(path, sheet):
    d = pd.read_excel(path, sheet_name=sheet).sort_values("종합유사도(0~100)", ascending=False).reset_index(drop=True)
    d = d.drop(columns=[c for c in ("순위",) if c in d.columns])
    d.insert(0, "순위", d.index + 1)
    d.insert(1, "협의번호", d["공고이름"].map(ids))
    d.insert(2, "지원대상란 기재", np.where(d["협의번호"].isin(blank), "미기재(서식 문구만)", "기재"))
    return d.drop(columns=[c for c in d.columns if c in ("행", "출처", "공고링크", "신규/기존", "대분류", "중분류", "대상유형", "업종")])

sh = {}
sh["기준시점_원천목록"] = pd.DataFrame(json.load(open("sheet_source.json", encoding="utf-8")))
sh["A시점_전체순위"] = rank("out_A/similarity_scores.xlsx", "전체")
for u in ("기능A1_성장보육컨설팅", "기능A2_스케일업프로그램", "기능A3_사업화자금"):
    sh[f"A시점_{u}"] = rank("out_A/similarity_scores.xlsx", u)
sh["B시점_전체순위"] = rank("out_B/similarity_scores.xlsx", "전체")

b = sh["B시점_전체순위"]; a = b[b["협의번호"] == "2026-053"].iloc[0]
sh["B시점_A후보확인"] = pd.DataFrame([
    {"항목": "후보 포함 여부", "값": "포함", "근거·설명": "협의번호 2026-053 ≤ 2026-103 → 비교② 누적 후보군에 포함"},
    {"항목": "후보군 규모", "값": f"{len(b)}건", "근거·설명": "협의번호 ≤103 중앙부처 협의요청사업에서 B 자신 제외"},
    {"항목": "사업 A의 순위", "값": f"{int(a['순위'])}위 / {len(b)}건", "근거·설명": "비교② 종합유사도 내림차순"},
    {"항목": "사업 A의 종합유사도", "값": f"{a['종합유사도(0~100)']:.2f}", "근거·설명": "Σ 가중치 × 축별 코사인 (기존 산식)"},
    *[{"항목": f"축별 코사인 — {ax}", "값": f"{a[ax+'_유사도']:.4f}",
       "근거·설명": f"가중점수 {a[ax+'_가중점수']:.2f} (가중치 {W[ax]}) / 등급 {a[ax+'_등급']} / 지표점수 {a[ax+'_지표점수']}"} for ax in AX],
    {"항목": "참고2 지표점수", "값": f"{a['참고2지표점수(0~100)']:.1f}",
     "근거·설명": "비교② 후보군(70건) 코퍼스 내 축별 z-점수 기반 — 코퍼스가 다르면 값이 달라지는 참고치"},
    {"항목": "A의 산식 입력 경로", "값": "기존사업 경로",
     "근거·설명": "A는 후보 표의 한 행으로 들어가 axis_texts()가 목적·내용·규모·대상유형·업종·전달체계를 조립한 텍스트로 인코딩됨"},
    {"항목": "B의 산식 입력 경로", "값": "신규사업 경로",
     "근거·설명": "B는 질의 프로필로서 축별 서술을 enc([spec[ax]]) 로 그대로 인코딩됨"},
    {"항목": "경로 비대칭 영향", "값": "직접비교 점수와 동일 척도 아님",
     "근거·설명": "비교② 내 A 점수(요청서 란 기준 조립 텍스트)와 A↔B 직접비교 점수(양쪽 모두 신규사업 프로필 서술)는 입력 텍스트 구성이 달라 서로 대체 불가"},
    {"항목": "A의 지원대상 축 한계", "값": "요청서 지원대상 상세란 미기재",
     "근거·설명": "A 요청서의 '※ 지원대상 상세 기재'가 서식 문구 그대로여서 지원대상 축 입력이 공란 → 해당 축 코사인 0.3804(상이)는 자료 미기재의 결과이며 실제 대상 상이성의 측정값으로 읽을 수 없음"},
    {"항목": "협의 상태 표기", "값": "선행 협의요청사업(요청서 접수 단계)",
     "근거·설명": "A는 2027년 예산 신설을 요청한 사전협의 요청사업으로, 시행·확정된 기존사업이 아님"},
])

dr = []
for k, lab in (("전체|전체", "A 전체 ↔ B 전체"),):
    r = rows[k]
    dr.append({"비교단위": lab, **{f"{ax}_코사인": r[f"{ax}_유사도"] for ax in AX},
               **{f"{ax}_가중점수": r[f"{ax}_가중점수"] for ax in AX},
               "종합유사도(0~100)": r["종합유사도(0~100)"], "등급·참고2 지표점수": "미산출"})
sh["AB_직접비교"] = pd.DataFrame(dr)
sh["AB_축별유사도"] = pd.DataFrame([
    {"분석축": ax, "가중치(합100)": W[ax], "원 가중치(참고2)": {"사업목적":20,"지원내용":30,"지원대상":30,"전달체계":15}[ax],
     "A↔B 코사인": rows["전체|전체"][f"{ax}_유사도"], "가중점수": rows["전체|전체"][f"{ax}_가중점수"],
     "5단계 등급": "미산출", "미산출 사유": "등급·지표점수는 코퍼스 내 축별 z-점수로 정의 — 2건 비교에는 기존 정의를 적용할 수 없음"} for ax in AX
] + [{"분석축": "종합", "가중치(합100)": 100.0, "원 가중치(참고2)": 95,
      "A↔B 코사인": "", "가중점수": rows["전체|전체"]["종합유사도(0~100)"], "5단계 등급": "미산출", "미산출 사유": "상동"}])
sh["AB_기능교차비교"] = pd.DataFrame([
    {"A 기능단위": r["A단위"], "B 기능단위": r["B단위"] + " (B는 기존 기능 분리 기준상 단일 기능)",
     **{f"{ax}_코사인": r[f"{ax}_유사도"] for ax in AX},
     "종합유사도(0~100)": r["종합유사도(0~100)"]} for r in direct["rows"]])

sh["객관적_원문근거"] = pd.DataFrame(json.load(open("sheet_evidence.json", encoding="utf-8")))
sh["제외자료_오염검증"] = pd.DataFrame(json.load(open("sheet_contam.json", encoding="utf-8")))
sh["수치_재현검증"] = pd.DataFrame(json.load(open("verify_repro.json", encoding="utf-8")))
sh["가중치·방법론"] = pd.DataFrame([
    {"항목": "임베딩 모델", "값": "BAAI/bge-m3 (CPU, normalize_embeddings=True → 내적 = 코사인)"},
    {"항목": "분석축", "값": " / ".join(AX)},
    {"항목": "가중치", "값": "참고2 원 가중치 20·30·30·15(합 95)를 합 100으로 정규화 → 21.05·31.58·31.58·15.79"},
    {"항목": "종합유사도", "값": "Σ 가중치 × 축별 코사인 (0~100)"},
    {"항목": "코드", "값": "similarity/similarity_check.py (무수정) + direct_compare.py(상수·인코딩 재사용)"},
    {"항목": "변경한 것", "값": "입력자료 출처 제한(요청서·부속자료) 및 협의번호 기준 후보군 구성뿐 — 산식·가중치·축·전처리·정규화 불변"},
])
with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
    for name, df in sh.items():
        df.to_excel(xw, sheet_name=name[:31], index=False)
print(f"{OUT} / {len(sh)}시트")
for n, d in sh.items(): print(f"  - {n}: {len(d)}행 × {len(d.columns)}열")
