"""similarity_check.py 산출물에 코퍼스 메타데이터를 병합해 기존 산출물과 동일한 형식의 xlsx 를 만든다.
조인 키는 '행'. 열 순서는 기존 산출물(참조 xlsx)을 그대로 따른다. 기존 파일은 변경하지 않는다.
사용: finalize.py <scores.xlsx> <meta.csv> <참조 xlsx> <출력 xlsx>
"""
import sys, pandas as pd, openpyxl
src, metap, ref, out = sys.argv[1:5]
xl = pd.ExcelFile(src)
meta = pd.read_csv(metap).fillna("")
meta["행"] = meta["행"].astype(str)
refcols = [str(c) for c in next(openpyxl.load_workbook(ref, read_only=True)["전체"].iter_rows(values_only=True))]

sheets = {}
for sh in xl.sheet_names:
    d = xl.parse(sh)
    if sh == "가중치":
        sheets[sh] = d; continue
    d["행"] = d["행"].astype(str)
    m = meta[meta["행"].isin(set(d["행"]))]
    d = d.merge(m, on="행", how="left", suffixes=("", "_m"))
    for c in ("단위", "연도", "세부사업명", "내역사업명", "내내역명", "연계공고"):
        if c in d.columns:
            d[c] = d[c].fillna("")
    if "연도" in d.columns:
        d["연도"] = pd.to_numeric(d["연도"], errors="coerce").astype("Int64")
    missing = [c for c in refcols if c not in d.columns]
    if missing:
        raise SystemExit(f"[{sh}] 참조 열 누락: {missing}")
    sheets[sh] = d[refcols]

# 공고매핑: 이번 실행(--extra 경로)에서는 생성되지 않으므로 참조 산출물의 표를 그대로 옮긴다(출처는 보고서에 명시)
ann = None
wb = openpyxl.load_workbook(ref, read_only=True)
if "공고매핑" in wb.sheetnames:
    rows = list(wb["공고매핑"].iter_rows(values_only=True))
    ann = pd.DataFrame(rows[1:], columns=[str(c) for c in rows[0]])

with pd.ExcelWriter(out, engine="openpyxl") as xw:
    sheets.pop("가중치").to_excel(xw, sheet_name="가중치", index=False)
    for sh, d in sheets.items():
        d.to_excel(xw, sheet_name=sh[:31], index=False)
    if ann is not None:
        ann.to_excel(xw, sheet_name="공고매핑", index=False)
print(f"저장 {out}: 시트 {['가중치'] + list(sheets) + (['공고매핑'] if ann is not None else [])}, 공고매핑 {0 if ann is None else len(ann)}행")
