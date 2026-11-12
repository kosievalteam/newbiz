"""협의사업 2건의 직접 유사도 산출 — 기존 similarity_check 의 산식·가중치·인코딩을 그대로 호출한다.

기존 코드는 수정하지 않고 상수(AXES, RAW_W, W)와 인코딩 방식(normalize_embeddings=True 내적 = 코사인)만 가져다 쓴다.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, "/home/user/newbiz/similarity")
from similarity_check import AXES, RAW_W, W   # 기존 산식의 축과 가중치 그대로

prof = json.load(open(sys.argv[1], encoding="utf-8"))
A, B = prof["사업A_2026-053"], prof["사업B_2026-103"]

from sentence_transformers import SentenceTransformer
model = SentenceTransformer("BAAI/bge-m3", device="cpu")
enc = lambda xs: model.encode(xs, normalize_embeddings=True, batch_size=16, show_progress_bar=False)

def vec(spec):                       # 기존 main() 의 신규사업 축 인코딩과 동일: enc([spec[ax]])[0]
    return {ax: enc([spec[ax]])[0] for ax in AXES}

va = {u: vec(s) for u, s in A["units"].items()}
vb = {u: vec(s) for u, s in B["units"].items()}

rows = []
for ua, qa in va.items():
    for ub, qb in vb.items():
        per = {ax: float(qa[ax] @ qb[ax]) for ax in AXES}          # 코사인
        tot = sum(per[ax] * W[ax] for ax in AXES)                  # 기존 종합 산식
        rows.append({"A단위": ua, "B단위": ub,
                     **{f"{ax}_유사도": round(per[ax], 4) for ax in AXES},
                     **{f"{ax}_가중점수": round(per[ax] * W[ax], 2) for ax in AXES},
                     "종합유사도(0~100)": round(tot, 2)})
json.dump({"weights": {k: round(v, 2) for k, v in W.items()}, "raw_weights": RAW_W,
           "model": "BAAI/bge-m3", "rows": rows},
          open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 역검증: 기존 산출물의 점수를 이 모듈로 재현되는지 확인(기존 산식 불변 증명)
import pandas as pd
chk = sys.argv[3] if len(sys.argv) > 3 else None
if chk:
    d = pd.read_excel(chk, sheet_name="전체")
    r = d.iloc[0]
    qb = vb["전체"]
    rep = sum(float(enc([str(r[f"{ax}_텍스트"])])[0] @ qb[ax]) * W[ax] for ax in AXES)
    print(f"[역검증] 기존 xlsx 1위 종합유사도 {r['종합유사도(0~100)']:.2f} / 본 모듈 재계산 {rep:.2f} "
          f"(차이 {abs(rep - r['종합유사도(0~100)']):.5f})")

print(f"가중치 {({k: round(v,2) for k,v in W.items()})}  합 {sum(W.values()):.2f}")
for r in rows:
    print(f"  {r['A단위']:<18} x {r['B단위']:<4} 종합 {r['종합유사도(0~100)']:6.2f} | " +
          " ".join(f"{ax[:2]}{r[f'{ax}_유사도']:.3f}" for ax in AXES))
