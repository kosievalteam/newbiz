"""사용법: python validate.py <chunk_dir> <start_id> <end_id> → 청크 JSON 파싱, 행 수/ID 연속성 검사"""
import json, sys, glob
d, s, e = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
ids = []
for f in sorted(glob.glob(f"{d}/chunk_*.json")):
    try:
        rows = json.load(open(f, encoding="utf-8"))
    except Exception as ex:
        print("PARSE_ERROR", f, ex); continue
    if not isinstance(rows, list): print("NOT_LIST", f); continue
    for r in rows:
        if "id" not in r: print("NO_ID", f); break
        ids.append(int(r["id"]))
ids = sorted(set(ids))
print("files", len(glob.glob(f"{d}/chunk_*.json")), "rows", len(ids), "min", ids[:1], "max", ids[-1:])
print("in_range", sum(s <= i <= e for i in ids))
