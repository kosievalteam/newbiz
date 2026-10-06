"""신규 협의사업 ↔ 기존사업 유사도 검색 (Supabase pgvector + bge-m3).

흐름: 4개 축 서술(프로필) → 임베딩(로컬 sentence-transformers bge-m3, 기본) → RPC match_biz → 상위 k 후보 (top10.json 형식).
출력 형식은 similarity_check.py 의 top10.json 과 같아 `review-draft similar-top` 으로 그대로 읽을 수 있다.

필요한 환경변수
  SUPABASE_URL, SUPABASE_ANON_KEY          : 검색 RPC 호출 (anon 키로 충분, 코퍼스 직접 조회는 불가)
  HF_TOKEN (선택, --embed hf 일 때만)       : Hugging Face Inference API 토큰. 기본 경로는 로컬 모델이며 토큰이 필요 없다.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

AXES = ["사업목적", "지원내용", "지원대상", "전달체계"]
AXIS_KEY = {"사업목적": "purpose", "지원내용": "content", "지원대상": "target", "전달체계": "delivery"}
RAW_W = {"사업목적": 20, "지원내용": 30, "지원대상": 30, "전달체계": 15}
W = {k: v / sum(RAW_W.values()) * 100 for k, v in RAW_W.items()}
MODEL = "BAAI/bge-m3"
MAX_SEQ = 512  # 코퍼스 임베딩(embed_corpus.py --max-seq 512)과 동일하게 맞춘다
_LOCAL_MODEL = None
HF_URL = "https://router.huggingface.co/hf-inference/models/BAAI/bge-m3/pipeline/feature-extraction"


def _post(url: str, headers: dict, payload, timeout: int = 180, retries: int = 3):
    """POST JSON. DB 캐시가 식어 있으면 첫 질의가 statement timeout(57014, HTTP 500)으로 끝나므로 같은 요청을 몇 번 더 보낸다."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code in (500, 503, 504) and attempt < retries and ("57014" in body or "timeout" in body.lower()):
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"HTTP {e.code} {url.rsplit('/', 1)[-1]}: {body[:200]}") from e


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


def local_available() -> bool:
    """sentence-transformers(및 torch)가 설치되어 있는지."""
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


def _local_model():
    global _LOCAL_MODEL
    if _LOCAL_MODEL is None:
        from sentence_transformers import SentenceTransformer  # 선택 의존성

        m = SentenceTransformer(MODEL, device="cpu")
        m.max_seq_length = MAX_SEQ
        _LOCAL_MODEL = m
    return _LOCAL_MODEL


def embed_local(texts: list[str]) -> list[list[float]]:
    """로컬 bge-m3 (첫 실행 시 huggingface.co 에서 모델 약 2.2GB 를 내려받아 캐시한다)."""
    model = _local_model()
    return [list(map(float, v)) for v in model.encode(texts, normalize_embeddings=True, batch_size=4, show_progress_bar=False)]


INSTALL_HINT = "pip install sentence-transformers  (GPU 없는 PC 는 먼저 pip install torch --index-url https://download.pytorch.org/whl/cpu)"


def embed(texts: list[str], how: str = "auto") -> list[list[float]]:
    """기본(auto)은 로컬 sentence-transformers. 'hf' 를 명시한 경우에만 Hugging Face Inference API 를 쓴다."""
    if how == "hf":
        return embed_hf(texts)
    if not local_available():
        raise RuntimeError(f"sentence-transformers 가 설치되어 있지 않습니다. 설치: {INSTALL_HINT}")
    return embed_local(texts)


def stats() -> dict:
    """Supabase 연결·키 확인: 적재된 기존사업 수, 연도, 모델, 갱신 시각."""
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_ANON_KEY")
    if not (url and key):
        raise RuntimeError("SUPABASE_URL, SUPABASE_ANON_KEY 가 필요합니다")
    rows = _post(f"{url.rstrip('/')}/rest/v1/rpc/biz_embedding_stats", {"apikey": key, "Authorization": f"Bearer {key}"}, {})
    return rows[0] if isinstance(rows, list) and rows else {}


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
    try:
        st = stats()
    except Exception:  # noqa: BLE001
        st = {}
    top = {}
    for unit, spec in profile["units"].items():
        texts = [spec[ax] for ax in AXES]
        vecs = dict(zip(AXES, embed(texts, how)))
        top[unit] = to_top_rows(match(vecs, k=k, years=years))
    n = st.get("n")
    result = {"weights": W, "model": MODEL, "n_existing": n, "source": "supabase:match_biz", "top": top}
    (out / "top10.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return out / "top10.json"
