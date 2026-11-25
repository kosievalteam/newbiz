"""커밋된 산출물 xlsx 에서 소실된 비교 코퍼스(corpus_3631_v2.csv)를 복원한다.

similarity_check.axis_texts() 가 산출한 4개 축 텍스트를 역산해 load_extra() 입력 스키마로 되돌리고,
복원 결과에 axis_texts() 를 다시 적용해 원본 축 텍스트와 바이트 단위로 일치하는지 검증한다.
기존 파일은 전혀 변경하지 않는다.
"""
import sys, re, pandas as pd
sys.path.insert(0, "/home/user/newbiz/similarity")
from similarity_check import axis_texts, EXTRA_COLS   # 기존 조립 규칙 그대로

SRC, OUT = sys.argv[1], sys.argv[2]
d = pd.read_excel(SRC, "전체").fillna("")
for c in d.columns:
    if d[c].dtype == object:
        d[c] = d[c].astype(str).replace("nan", "")

rows = []
for _, r in d.iterrows():
    pur_t, con_t, tgt_t, dlv_t = (str(r[f"{a}_텍스트"]) for a in ("사업목적", "지원내용", "지원대상", "전달체계"))
    scale = str(r["규모"]).strip()

    # 사업목적 = f"{목적} (정책목적: {정책목적 or 대분류})"
    m = re.search(r" \(정책목적: (.*)\)$", pur_t, re.S)
    purpose, pol = (pur_t[: m.start()], m.group(1)) if m else (pur_t, "")

    # 지원대상 = f"{대상} (대상유형: {대상유형}, 업종: {업종})"
    m = re.search(r" \(대상유형: (.*), 업종: (.*)\)$", tgt_t, re.S)
    target, tgt_type, ind = (tgt_t[: m.start()], m.group(1), m.group(2)) if m else (tgt_t, "", "")

    # 지원내용 = f"{내용} {'규모: '+규모 if 규모 else ''} {설명}".strip()
    content, desc = con_t, ""
    if scale:
        tok = f" 규모: {scale}"
        i = con_t.rfind(tok)
        if i >= 0:
            content, rest = con_t[:i], con_t[i + len(tok):]
            desc = rest.strip()

    rec = {c: "" for c in EXTRA_COLS}
    rec.update({
        "부처": str(r["부처"]), "기관": str(r["기관"]), "공고이름": str(r["공고이름"]),
        "목적": purpose, "내용": content, "대상": target, "규모": scale, "설명": desc,
        "대분류": str(r["대분류"]), "중분류": str(r["중분류"]), "대상유형": tgt_type, "업종": ind,
        "정책목적": pol if pol != str(r["대분류"]) else "", "신규/기존": str(r["신규/기존"]),
        "공고링크": str(r["공고링크"]), "시행방법": str(r["시행방법"]),
    })
    rec["_행"] = str(r["행"]); rec["_단위"] = str(r.get("단위", "")); rec["_연도"] = r.get("연도", "")
    rec["_세부사업명"] = str(r.get("세부사업명", "")); rec["_내역사업명"] = str(r.get("내역사업명", ""))
    rec["_내내역명"] = str(r.get("내내역명", "")); rec["_연계공고"] = str(r.get("연계공고", ""))
    rows.append(rec)

# 원본 CSV 행 순서(행 열의 숫자 접미사) 복원
out = pd.DataFrame(rows)
out["_n"] = out["_행"].str.extract(r":(\d+)$").astype(int)
out = out.sort_values("_n").reset_index(drop=True)

# --- 검증: 복원본에 axis_texts() 를 다시 적용해 원본과 대조 ---
chk = out[EXTRA_COLS].copy()
got = axis_texts(chk)
orig = {a: out["_행"].map(dict(zip(d["행"].astype(str), d[f"{a}_텍스트"].astype(str)))).tolist()
        for a in ("사업목적", "지원내용", "지원대상", "전달체계")}
ok = True
for a in ("사업목적", "지원내용", "지원대상", "전달체계"):
    bad = [i for i, (x, y) in enumerate(zip(got[a], orig[a])) if x != y]
    print(f"  {a}: 일치 {len(got[a]) - len(bad)}/{len(got[a])}" + (f"  불일치 {len(bad)}건 예시행={out.at[bad[0],'_행']}" if bad else ""))
    if bad:
        ok = False
        print("    원본:", repr(orig[a][bad[0]])[:200]); print("    복원:", repr(got[a][bad[0]])[:200])
out[EXTRA_COLS].to_csv(OUT, index=False)
meta = out[["_행", "_단위", "_연도", "_세부사업명", "_내역사업명", "_내내역명", "_연계공고"]]
meta.columns = [c[1:] for c in meta.columns]
meta.to_csv(OUT.replace(".csv", "_메타.csv"), index=False)
print(f"저장 {OUT} ({len(out)}행) / 메타 {OUT.replace('.csv','_메타.csv')}")
print("검증:", "통과 — 축 텍스트 4종 전부 원본과 바이트 일치" if ok else "불일치 있음")
sys.exit(0 if ok else 1)
