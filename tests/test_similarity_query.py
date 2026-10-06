import json

import pytest

from review_draft import similarity_query as sq


def test_pool_and_normalize():
    assert sq._pool([3.0, 4.0]) == [3.0, 4.0]
    assert sq._pool([[3.0, 4.0], [0.0, 1.0]]) == [3.0, 4.0]  # 토큰별 → CLS
    assert sq._pool([[[3.0, 4.0], [1.0, 0.0]]]) == [3.0, 4.0]
    v = sq._normalize([3.0, 4.0])
    assert abs(v[0] - 0.6) < 1e-9 and abs(v[1] - 0.8) < 1e-9


def test_run_builds_top10(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    calls = []

    def fake_post(url, headers, payload, timeout=180):
        calls.append((url, payload))
        if url.endswith("biz_embedding_stats"):
            return [{"n": 3631, "years": [2025, 2026], "model": "BAAI/bge-m3", "updated_at": "x"}]
        assert url.endswith("/rest/v1/rpc/match_biz")
        assert set(payload) >= {"q_purpose", "q_content", "q_target", "q_delivery", "k", "w_purpose"}
        assert abs(payload["w_content"] - 31.5789) < 1e-3
        return [
            {"unit_key": "biz:1", "unit_type": "내역사업", "year": 2026, "dept": "금융위원회", "agency": "센터", "title": "2026년 핀테크 지원 사업 > A",
             "sebu": "핀테크 지원 사업", "nae": "A", "naenae": None, "method": "보조", "scale": "100", "linked": "",
             "sim_purpose": 0.7, "sim_content": 0.72, "sim_target": 0.74, "sim_delivery": 0.81, "total": 73.65,
             "purpose_text": "p", "content_text": "c", "target_text": "t", "delivery_text": "d"},
        ]

    monkeypatch.setattr(sq, "_post", fake_post)
    monkeypatch.setattr(sq, "embed", lambda texts, how="auto": [[1.0] + [0.0] * 1023 for _ in texts])
    profile = {"사업명": "x", "units": {"전체": {"사업목적": "a", "지원내용": "b", "지원대상": "c", "전달체계": "d"}}}
    p = sq.run(profile, tmp_path, k=5)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["n_existing"] == 3631 and data["model"] == "BAAI/bge-m3"
    row = data["top"]["전체"][0]
    assert row["순위"] == 1 and row["종합유사도(0~100)"] == 73.65 and row["사업목적_유사도"] == 0.7
    # similar-top 로더와 호환
    from review_draft.similarity_io import load_similarity

    rep = load_similarity(p)
    assert rep.candidates[0].사업명.startswith("핀테크 지원 사업 > A")


def test_embed_requires_means(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        sq.embed_hf(["x"], token=None)


def test_embed_defaults_to_local_and_reports_missing_package(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "t")  # 토큰이 있어도 기본 경로는 로컬
    monkeypatch.setattr(sq, "local_available", lambda: False)
    with pytest.raises(RuntimeError, match="sentence-transformers"):
        sq.embed(["x"])
    called = []
    monkeypatch.setattr(sq, "local_available", lambda: True)
    monkeypatch.setattr(sq, "embed_local", lambda texts: called.append(texts) or [[1.0]])
    assert sq.embed(["x"]) == [[1.0]] and called == [["x"]]


def test_post_retries_on_statement_timeout(monkeypatch):
    import io
    import urllib.error

    calls = []

    def fake_urlopen(req, timeout=0):
        calls.append(req.full_url)
        if len(calls) < 3:
            raise urllib.error.HTTPError(req.full_url, 500, "err", {}, io.BytesIO(b'{"code":"57014","message":"canceling statement due to statement timeout"}'))

        class R:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"[1]"

        return R()

    monkeypatch.setattr(sq.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(sq.time, "sleep", lambda s: None)
    assert sq._post("https://x/rest/v1/rpc/match_biz", {}, {}) == [1] and len(calls) == 3

    calls.clear()

    def bad(req, timeout=0):
        calls.append(1)
        raise urllib.error.HTTPError(req.full_url, 401, "u", {}, io.BytesIO(b"Unauthorized"))

    monkeypatch.setattr(sq.urllib.request, "urlopen", bad)
    with pytest.raises(RuntimeError, match="HTTP 401"):
        sq._post("https://x/rest/v1/rpc/match_biz", {}, {})
    assert len(calls) == 1
