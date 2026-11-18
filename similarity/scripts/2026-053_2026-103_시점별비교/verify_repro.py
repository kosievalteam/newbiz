"""수치 재현검증: (1) 기존 산식 불변 (2) 신규 산출물 자기정합성."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/newbiz/similarity")
from similarity_check import AXES, W
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("BAAI/bge-m3", device="cpu")
enc = lambda xs: m.encode(xs, normalize_embeddings=True, batch_size=16, show_progress_bar=False)
SP = Path("/tmp/claude-0/-home-user-newbiz/48a7be44-e66a-585f-9512-c54081407b97/scratchpad")
R = Path("/home/user/newbiz/similarity/results")
out = []

def repro(label, xlsx, sheet, profile_spec, rank=0):
    d = pd.read_excel(xlsx, sheet_name=sheet).sort_values("종합유사도(0~100)", ascending=False).reset_index(drop=True)
    r = d.iloc[rank]
    q = {ax: enc([profile_spec[ax]])[0] for ax in AXES}
    tot, per = 0.0, {}
    for ax in AXES:
        c = float(enc([str(r[f"{ax}_텍스트"])])[0] @ q[ax]); per[ax] = round(c, 4); tot += c * W[ax]
        
    out.append({"검증항목": label, "대상": str(r["공고이름"])[:50], "산출물 기록값": round(float(r["종합유사도(0~100)"]), 2),
                "본 검증 재계산": round(tot, 2), "절대차": round(abs(tot - float(r["종합유사도(0~100)"])), 5),
                "축별 재계산 코사인": json.dumps(per, ensure_ascii=False)})
    print(f"[{label}] {out[-1]['산출물 기록값']} vs {out[-1]['본 검증 재계산']} (차이 {out[-1]['절대차']})")

# (1) 기존 산식 불변: 기존 커밋된 B 프로필(미정제) + 기존 산출물 1위 → 완전 재현되어야 함
pb_old = json.load(open(R/"new_project_profile_사회적기업임팩트투자연계.json", encoding="utf-8"))["units"]["전체"]
repro("기존 산식 불변(기존 B 산출물 1위 재현)", SP/"case20/유사도_산출결과_사회적기업임팩트투자연계.xlsx", "전체", pb_old)
pa_old = json.load(open(R/"new_project_profile_사회연대경제기업성장지원.json", encoding="utf-8"))["units"]["전체"]
repro("기존 산식 불변(기존 A 산출물 1위 재현)", SP/"case19/유사도_산출결과_사회연대경제기업성장지원.xlsx", "전체", pa_old)

# (2) 신규 산출물 자기정합성: 이번 비교①·② 산출물의 1위·A행 재현
pc = json.load(open("profiles_clean_fn.json", encoding="utf-8"))
repro("비교① 1위 재현", "out_A/similarity_scores.xlsx", "전체", pc["사업A_2026-053"]["units"]["전체"])
repro("비교② 1위 재현", "out_B/similarity_scores.xlsx", "전체", pc["사업B_2026-103"]["units"]["전체"])
d = pd.read_excel("out_B/similarity_scores.xlsx", sheet_name="전체").sort_values("종합유사도(0~100)", ascending=False).reset_index(drop=True)
ra = int(d.index[d["공고이름"].str.startswith("2026-053")][0])
repro(f"비교② 사업A 행 재현({ra+1}위)", "out_B/similarity_scores.xlsx", "전체", pc["사업B_2026-103"]["units"]["전체"], rank=ra)
json.dump(out, open("verify_repro.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
