"""신규 협의사업 ↔ 기존사업 유사도 검색 (Supabase pgvector + bge-m3).

흐름: 4개 축 서술(프로필) → 임베딩(HF 추론 API 또는 로컬 bge-m3) → RPC match_biz → 상위 k 후보 (top10.json 형식).
출력 형식은 similarity_check.py 의 top10.json 과 같아 `review-draft similar-top` 으로 그대로 읽을 수 있다.

필요한 환경변수
  SUPABASE_URL, SUPABASE_ANON_KEY          : 검색 RPC 호출 (anon 키로 충분, 코퍼스 직접 조회는 불가)
  HF_TOKEN (임베딩 방식 hf 일 때)           : Hugging Face Inference API 토큰
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

AXES = ["사업목적", "지원내용", "지원대상", "전달체계"]
AXIS_KEY = {"사업목적": "purpose", "지원내용": "content", "지원대상": "target", "전달체계": "delivery"}
RAW_W = {"사업목적": 20, "지원내용": 30, "지원대상": 30, "전달체계": 15}
W = {k: v / sum(RAW_W.values()) * 100 for k, v in RAW_W.items()}
MODEL = "BAAI/bge-m3"
HF_URL = "https://router.huggingface.co/hf-inference/models/BAAI/bge-m3/pipeline/feature-extraction"


def _post(url: str, headers: dict, payload, timeout: int = 180):
    req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _normalize(v: list[float]) -> list[float]:
    s = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / s for x in v]


def _pool(out) -> list[float]:
    """HF feature-extraction 응답을 문장 벡터로 정리한다 (풀링된 1차원이면 그대로, 토큰별이면 CLS=첫 토큰)."""
    if isinstance(out, list) and out and isinstance(out[0], (int, float)):
        return [float(x) for x in out]
    if isinstance(out, list) and out and isinstance(out[0], list):
        if out and isinstance(out[0][0], (int, float)):
            return [float(x) for x in out[0]]  # [tokens][dim] → CLS 토큰 (bge 계열은 CLS 풀링)
        return _pool(out[0])
    raise ValueError(f"임베딩 응답 형식을 해석할 수 없습니다: {str(out)[:120]}")


def embed_hf(texts: list[str], token: str | None = None) -> list[list[float]]:
    token = token or os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN 이 필요합니다 (Hugging Face Inference API). 또는 --embed local 로 로컬 모델을 사용하세요.")
    out = []
    for t in texts:
        res = _post(HF_URL, {"Authorization": f"Bearer {token}"}, {"inputs": t, "options": {"wait_for_model": True}})
        out.append(_normalize(_pool(res)))
    return out


def embed_local(texts: list[str]) -> list[list[float]]:
    from sentence_transformers import SentenceTransformer  # 선택 의존성

    model = SentenceTransformer(MODEL, device="cpu")
    return [list(map(float, v)) for v in model.encode(texts, normalize_embeddings=True, batch_size=4, show_progress_bar=False)]


def embed(texts: list[str], how: str = "auto") -> list[list[float]]:
    if how == "hf":
        return embed_hf(texts)
    if how == "local":
        return embed_local(texts)
    if os.environ.get("HF_TOKEN"):
        return embed_hf(texts)
    try:
        return embed_local(texts)
    except ImportError as e:
        raise RuntimeError("임베딩 수단이 없습니다. HF_TOKEN 을 설정하거나 sentence-transformers 를 설치하세요.") from e


def match(vectors: dict[str, list[float]], k: int = 10, years: list[int] | None = None) -> list[dict]:
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_ANON_KEY")
    if not (url and key):
        raise RuntimeError("SUPABASE_URL, SUPABASE_ANON_KEY 가 필요합니다")
    payload = {f"q_{AXIS_KEY[ax]}": vectors[ax] for ax in AXES}
    payload.update({"k": k, "w_purpose": W["사업목적"], "w_content": W["지원내용"], "w_target": W["지원대상"], "w_delivery": W["전달체계"], "p_years": years})
    return _post(f"{url.rstrip('/')}/rest/v1/rpc/match_biz", {"apikey": key, "Authorization": f"Bearer {key}"}, payload)


def to_top_rows(rows: list[dict]) -> list[dict]:
    out = []
    for i, r in enumerate(rows, 1):
        out.append({
            "순위": i, "행": r["unit_key"], "출처": r.get("unit_type"), "부처": r.get("dept"), "기관": r.get("agency"), "공고이름": r.get("title"),
            "단위": r.get("unit_type"), "연도": r.get("year"), "세부사업명": r.get("sebu"), "내역사업명": r.get("nae"), "내내역명": r.get("naenae"),
            "시행방법": r.get("method"), "규모": r.get("scale"), "연계공고": r.get("linked"),
            "사업목적_유사도": round(r["sim_purpose"], 4), "지원내용_유사도": round(r["sim_content"], 4),
            "지원대상_유사도": round(r["sim_target"], 4), "전달체계_유사도": round(r["sim_delivery"], 4),
            "종합유사도(0~100)": round(r["total"], 2),
            "사업목적_텍스트": r.get("purpose_text"), "지원내용_텍스트": r.get("content_text"), "지원대상_텍스트": r.get("target_text"), "전달체계_텍스트": r.get("delivery_text"),
        })
    return out


def run(profile: dict, out_dir: str | Path, *, k: int = 10, how: str = "auto", years: list[int] | None = None) -> Path:
    """profile = {"사업명":…, "units": {"전체": {"사업목적":…, "지원내용":…, "지원대상":…, "전달체계":…}, …}}"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stats = None
    try:
        stats = _post(f"{os.environ['SUPABASE_URL'].rstrip('/')}/rest/v1/rpc/biz_embedding_stats", {"apikey": os.environ["SUPABASE_ANON_KEY"], "Authorization": f"Bearer {os.environ['SUPABASE_ANON_KEY']}"}, {})
    except Exception:  # noqa: BLE001
        pass
    top = {}
    for unit, spec in profile["units"].items():
        texts = [spec[ax] for ax in AXES]
        vecs = dict(zip(AXES, embed(texts, how)))
        top[unit] = to_top_rows(match(vecs, k=k, years=years))
    n = (stats[0]["n"] if isinstance(stats, list) and stats else None)
    result = {"weights": W, "model": MODEL, "n_existing": n, "source": "supabase:match_biz", "top": top}
    (out / "top10.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return out / "top10.json"
