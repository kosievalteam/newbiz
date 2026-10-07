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
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

AXES = ["사업목적", "지원내용", "지원대상", "전달체계"]
AXIS_KEY = {"사업목적": "purpose", "지원내용": "content", "지원대상": "target", "전달체계": "delivery"}
RAW_W = {"사업목적": 20, "지원내용": 30, "지원대상": 30, "전달체계": 15}
W = {k: v / sum(RAW_W.values()) * 100 for k, v in RAW_W.items()}
MODEL = "BAAI/bge-m3"
# 검토범위: 지자체 사업은 동일 지자체만, 중앙부처 사업은 전부처를 비교한다.
# 코퍼스의 dept 는 중앙부처는 '중소벤처기업부'·'방송미디어통신위원회'처럼 정식 명칭,
# 지자체는 '경남'·'서울'처럼 지역 약칭으로 적재되어 있다.
_CENTRAL_SUFFIX = re.compile(r"(부|처|청|실|위원회)$")
# '경상남도청'·'창원시청' 처럼 지자체가 기관명으로 적힌 경우를 중앙부처로 오인하지 않는다
_LOCAL_SUFFIX = re.compile(r"(도청|시청|군청|구청|특별자치도|특별시|광역시|자치구)$")
SCOPE_CENTRAL_ONLY = "중앙부처"  # scope 로 주면 지자체 사업을 모두 제외한다
_OVERFETCH = 8  # 범위 필터로 걸러지는 만큼 넉넉히 받아 온다
_MAX_FETCH = 200
_PG_TIMEOUT = "57014"  # postgres statement timeout — 콜드 스타트나 큰 k 에서 간헐적으로 발생
_RETRY_WAITS = (2, 5)
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


def is_central(dept: str | None) -> bool:
    """중앙부처(…부·처·청·실·위원회) 여부. 지자체는 '경남'처럼 지역 약칭으로 적재되므로 False."""
    dept = (dept or "").strip()
    if _LOCAL_SUFFIX.search(dept):
        return False
    return bool(_CENTRAL_SUFFIX.search(dept))


def in_scope(dept: str | None, scope: str | None) -> bool:
    """검토범위 판정. scope 가 None 이면 필터하지 않는다(전체 비교).

    scope 가 지자체명이면 중앙부처 전부처 + 해당 지자체만, SCOPE_CENTRAL_ONLY 면 중앙부처만 남긴다.
    """
    if not scope:
        return True
    dept = (dept or "").strip()
    if is_central(dept):
        return True
    if scope == SCOPE_CENTRAL_ONLY:
        return False
    return dept == scope.strip()


def apply_scope(rows: list[dict], scope: str | None, k: int) -> tuple[list[dict], int]:
    """검토범위를 적용하고 상위 k 개로 자른다. (남은 행, 제외된 행 수) 를 돌려준다."""
    kept = [r for r in rows if in_scope(r.get("dept"), scope)]
    return kept[:k], len(rows) - len(kept)


def _is_statement_timeout(err: Exception) -> bool:
    """RPC 가 statement timeout 으로 500 을 돌려준 경우인지 본다."""
    if not isinstance(err, urllib.error.HTTPError) or err.code != 500:
        return False
    try:
        return json.loads(err.read().decode("utf-8")).get("code") == _PG_TIMEOUT
    except Exception:  # noqa: BLE001 — 본문을 못 읽으면 timeout 여부를 단정하지 않는다
        return False


def match(vectors: dict[str, list[float]], k: int = 10, years: list[int] | None = None) -> list[dict]:
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_ANON_KEY")
    if not (url and key):
        raise RuntimeError("SUPABASE_URL, SUPABASE_ANON_KEY 가 필요합니다")
    payload = {f"q_{AXIS_KEY[ax]}": vectors[ax] for ax in AXES}
    payload.update({"k": k, "w_purpose": W["사업목적"], "w_content": W["지원내용"], "w_target": W["지원대상"], "w_delivery": W["전달체계"], "p_years": years})
    endpoint = f"{url.rstrip('/')}/rest/v1/rpc/match_biz"
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    for wait in (*_RETRY_WAITS, None):
        try:
            return _post(endpoint, headers, payload)
        except Exception as e:  # noqa: BLE001
            if wait is None or not _is_statement_timeout(e):
                raise
            time.sleep(wait)
    raise AssertionError("unreachable")


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


def run(profile: dict, out_dir: str | Path, *, k: int = 10, how: str = "auto", years: list[int] | None = None, scope: str | None = None) -> Path:
    """profile = {"사업명":…, "검토범위": {"동일지자체": "경남"}, "units": {"전체": {"사업목적":…, …}, …}}

    scope 는 검토범위(동일 지자체명 또는 SCOPE_CENTRAL_ONLY). 생략하면 프로필의
    `검토범위.동일지자체` 를 쓰고, 그것도 없으면 범위를 제한하지 않는다.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    scope = scope or (profile.get("검토범위") or {}).get("동일지자체") or None
    stats = None
    try:
        stats = _post(f"{os.environ['SUPABASE_URL'].rstrip('/')}/rest/v1/rpc/biz_embedding_stats", {"apikey": os.environ["SUPABASE_ANON_KEY"], "Authorization": f"Bearer {os.environ['SUPABASE_ANON_KEY']}"}, {})
    except Exception:  # noqa: BLE001
        pass
    # p_years 를 null 로 보내면 RPC 가 전체 스캔 계획을 타 statement timeout(500) 이 나므로
    # 연도를 지정하지 않았으면 코퍼스에 적재된 연도를 명시해 보낸다.
    if years is None and isinstance(stats, list) and stats and stats[0].get("years"):
        years = [int(y) for y in stats[0]["years"]]
    fetch = min(max(k * _OVERFETCH, k), _MAX_FETCH) if scope else k
    top, excluded = {}, {}
    for unit, spec in profile["units"].items():
        texts = [spec[ax] for ax in AXES]
        vecs = dict(zip(AXES, embed(texts, how)))
        rows, n_out = apply_scope(match(vecs, k=fetch, years=years), scope, k)
        top[unit] = to_top_rows(rows)
        excluded[unit] = n_out
    n = (stats[0]["n"] if isinstance(stats, list) and stats else None)
    result = {"weights": W, "model": MODEL, "n_existing": n, "source": "supabase:match_biz",
              "scope": scope, "scope_excluded": excluded if scope else {}, "years": years, "top": top}
    (out / "top10.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return out / "top10.json"
