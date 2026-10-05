"""embed_corpus.py 산출물(.npz + meta.json)을 Supabase public.biz_embedding 에 적재한다.

서비스 키 없이 RPC upsert_biz_embedding(p_token, p_rows) 로 올린다 (토큰은 DB 의 biz_embedding_load_token 과 대조).
사용
  export SUPABASE_URL=https://<ref>.supabase.co SUPABASE_ANON_KEY=... BIZ_EMBED_LOAD_TOKEN=...
  python similarity/load_embeddings.py --dir output/embeddings [--batch 50]
  (--dir 에는 corpus_meta.json 과 corpus_embeddings.npz 또는 corpus_embeddings_f16.npz 를 둔다)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

FIELDS = {"행": "unit_key", "단위": "unit_type", "연도": "year", "부처": "dept", "기관": "agency", "공고이름": "title", "세부사업명": "sebu",
          "내역사업명": "nae", "내내역명": "naenae", "시행방법": "method", "규모": "scale", "연계공고": "linked", "대분류": "big", "중분류": "mid",
          "purpose": "purpose_text", "content": "content_text", "target": "target_text", "delivery": "delivery_text"}


def rpc(url: str, key: str, name: str, payload: dict, timeout: int = 120):
    req = urllib.request.Request(
        f"{url.rstrip('/')}/rest/v1/rpc/{name}", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=representation"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8")
    return json.loads(body) if body else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="output/embeddings")
    ap.add_argument("--batch", type=int, default=40)
    ap.add_argument("--start", type=int, default=0, help="재개용: 이 인덱스부터")
    ap.add_argument("--model", default="BAAI/bge-m3")
    a = ap.parse_args()
    url, key, token = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_ANON_KEY"), os.environ.get("BIZ_EMBED_LOAD_TOKEN")
    if not (url and key and token):
        sys.exit("SUPABASE_URL, SUPABASE_ANON_KEY, BIZ_EMBED_LOAD_TOKEN 환경변수가 필요합니다")

    import numpy as np

    d = Path(a.dir)
    meta = json.loads((d / "corpus_meta.json").read_text(encoding="utf-8"))
    npz = d / "corpus_embeddings.npz"
    if not npz.exists():
        npz = d / "corpus_embeddings_f16.npz"  # 전달용 float16 판 (코사인 오차 1e-4 이하)
    emb = np.load(npz)
    n = len(meta)
    assert all(emb[k].shape[0] == n for k in ("purpose", "content", "target", "delivery")), "메타와 임베딩 건수 불일치"
    vec = lambda arr: "[" + ",".join(f"{x:.6f}" for x in arr.tolist()) + "]"
    done = 0
    t0 = time.time()
    for i in range(a.start, n, a.batch):
        rows = []
        for j in range(i, min(i + a.batch, n)):
            m = meta[j]
            r = {FIELDS[k]: m.get(k, "") for k in FIELDS if k in m}
            r["year"] = int(float(m["연도"])) if str(m.get("연도", "")).strip() else None
            r.update({"purpose_vec": vec(emb["purpose"][j]), "content_vec": vec(emb["content"][j]), "target_vec": vec(emb["target"][j]),
                      "delivery_vec": vec(emb["delivery"][j]), "model": a.model})
            rows.append(r)
        for attempt in range(4):
            try:
                rpc(url, key, "upsert_biz_embedding", {"p_token": token, "p_rows": rows})
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 3:
                    raise
                print(f"재시도 {attempt + 1}: {e}", file=sys.stderr)
                time.sleep(2 ** attempt)
        done += len(rows)
        print(f"{done}/{n - a.start} ({time.time() - t0:.0f}s)", flush=True)
    stats = rpc(url, key, "biz_embedding_stats", {})
    print("적재 완료:", stats)


if __name__ == "__main__":
    main()
