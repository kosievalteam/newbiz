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


def test_is_central_and_in_scope():
    for dept in ("중소벤처기업부", "농림축산식품부", "방송미디어통신위원회", "지식재산처", "조달청", "국무조정실"):
        assert sq.is_central(dept)
    # 지자체는 지역 약칭 또는 기관명으로 적재된다 — '…도청/시청' 을 부처로 오인하지 않는다
    for dept in ("경남", "충남", "서울", "제주특별자치도", "경상남도청", "창원시청", "부산광역시"):
        assert not sq.is_central(dept)
    # scope 가 없으면 전체 비교
    assert sq.in_scope("충남", None) and sq.in_scope("중소벤처기업부", None)
    # 지자체 scope: 중앙부처 전부처 + 동일 지자체만
    assert sq.in_scope("중소벤처기업부", "경남")
    assert sq.in_scope("경남", "경남")
    assert not sq.in_scope("충남", "경남")
    # 중앙부처 신청사업: 지자체 전부 제외
    assert sq.in_scope("고용노동부", sq.SCOPE_CENTRAL_ONLY)
    assert not sq.in_scope("경남", sq.SCOPE_CENTRAL_ONLY)


def test_apply_scope_trims_after_filtering():
    rows = [{"dept": d} for d in ("충남", "경남", "경북", "중소벤처기업부", "강원", "고용노동부")]
    kept, excluded = sq.apply_scope(rows, "경남", k=2)
    assert [r["dept"] for r in kept] == ["경남", "중소벤처기업부"]
    assert excluded == 3  # 충남·경북·강원
    kept, excluded = sq.apply_scope(rows, None, k=2)
    assert [r["dept"] for r in kept] == ["충남", "경남"] and excluded == 0


def _fake_corpus(depts):
    def fake_post(url, headers, payload, timeout=180):
        if url.endswith("biz_embedding_stats"):
            return [{"n": 3631, "years": [2025, 2026], "model": "BAAI/bge-m3", "updated_at": "x"}]
        assert payload["p_years"] == [2025, 2026], "p_years 를 null 로 보내면 RPC 가 timeout 된다"
        return [{"unit_key": f"biz:{i}", "unit_type": "내역사업", "year": 2026, "dept": d, "agency": "기관",
                 "title": f"t{i}", "sebu": f"사업{i}", "nae": None, "naenae": None, "method": "보조",
                 "scale": "1", "linked": "", "sim_purpose": 0.5, "sim_content": 0.5, "sim_target": 0.5,
                 "sim_delivery": 0.5, "total": 60 - i, "purpose_text": "p", "content_text": "c",
                 "target_text": "t", "delivery_text": "d"} for i, d in enumerate(depts)]
    return fake_post


def test_run_applies_scope_and_explicit_years(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setattr(sq, "_post", _fake_corpus(["충남", "경남", "경북", "중소벤처기업부"]))
    monkeypatch.setattr(sq, "embed", lambda texts, how="auto": [[1.0] + [0.0] * 1023 for _ in texts])
    profile = {"사업명": "x", "검토범위": {"동일지자체": "경남"},
               "units": {"전체": {"사업목적": "a", "지원내용": "b", "지원대상": "c", "전달체계": "d"}}}
    data = json.loads(sq.run(profile, tmp_path, k=10).read_text(encoding="utf-8"))
    assert data["scope"] == "경남" and data["years"] == [2025, 2026]
    assert [r["부처"] for r in data["top"]["전체"]] == ["경남", "중소벤처기업부"]
    assert data["scope_excluded"]["전체"] == 2
    # 순위는 범위 적용 후 다시 매긴다
    assert [r["순위"] for r in data["top"]["전체"]] == [1, 2]
    # 〈참고〉 표 유의사항에 검토범위가 들어간다
    from review_draft.similarity_io import load_similarity

    rep = load_similarity(tmp_path / "top10.json")
    assert any("동일 지자체(경남)" in n and "2개 제외" in n for n in rep.notes)


def test_match_retries_on_statement_timeout(monkeypatch):
    import urllib.error

    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setattr(sq.time, "sleep", lambda s: None)
    calls = []

    class _Body:
        def read(self):
            return b'{"code":"57014","message":"canceling statement due to statement timeout"}'

        def close(self):
            pass

    def flaky(url, headers, payload, timeout=180):
        calls.append(payload["k"])
        if len(calls) == 1:
            raise urllib.error.HTTPError(url, 500, "Internal Server Error", {}, _Body())
        return [{"unit_key": "biz:1"}]

    monkeypatch.setattr(sq, "_post", flaky)
    vecs = {ax: [1.0] for ax in sq.AXES}
    assert sq.match(vecs, k=80) == [{"unit_key": "biz:1"}]
    assert calls == [80, 80]  # 한 번 실패 후 재시도


def test_match_does_not_retry_other_errors(monkeypatch):
    import urllib.error

    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    calls = []

    class _Body:
        def read(self):
            return b'{"code":"22000","message":"different vector dimensions 1024 and 2"}'

        def close(self):
            pass

    def bad_dim(url, headers, payload, timeout=180):
        calls.append(1)
        raise urllib.error.HTTPError(url, 400, "Bad Request", {}, _Body())

    monkeypatch.setattr(sq, "_post", bad_dim)
    with pytest.raises(urllib.error.HTTPError):
        sq.match({ax: [1.0] for ax in sq.AXES}, k=10)
    assert len(calls) == 1  # 차원 오류는 재시도하지 않는다
