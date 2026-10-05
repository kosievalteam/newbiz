"""기존사업을 내역사업·내내역사업 단위로 구성한다.

입력(모두 kosievalteam.github.io/biz_info 의 Supabase 추출 JSON, biz_export.sql 참고)
  - biz_json      : public.biz 2025·2026 행 (내역사업 단위, 열 별칭은 similarity_check.load_biz 참고)
  - struct_dir    : public.biz_struct 레벨>=2 행 {id, yr, gwan, sebu, seq, lvl, item, bud}
                    레벨2 = 내역사업, 레벨3·4 = 내내역(내내내역). 차례(seq) 순으로 직전 레벨2 항목이 부모
  - parents_dir   : 내내역이 있는 세부사업의 biz 행 전체 텍스트 {id, npur_full, spur_full, calc_full, gonggo_full, tgt_full}
  - gonggo_dirs   : public.gonggo 행 {id, yr, gwan, sebu, nae, name, org, src} — 공고명 ↔ 내역사업 매핑
  - ann_df        : 「중앙부처 지원사업 공고정보」 xlsx 파싱 결과 (similarity_check.load_existing)

규칙
  - 기본 단위는 내역사업. 내내역(레벨3)이 있는 내역사업은 내내역 단위로 대체하고 부모 행은 제거.
    레벨4 항목은 레벨3 부모의 내용에 덧붙인다.
  - 내내역 단위의 사업목적·지원대상·전달체계는 부모 내역사업 서술을 상속하고, 지원내용은
    「(내내역) 항목명·예산 + 부모 산출근거 중 해당 항목 문장 + 부모 내역 서술」로 구성.
  - 공고정보는 단위가 아니라 보강 자료: gonggo 매핑으로 연결된 내역사업(및 그 내내역)에
    ①목적·②내용·③대상·④규모를 덧붙인다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

_PUNCT = re.compile(r"[\s·ㆍ‧\-_()\[\]「」『』‘’'\"․,.:;/+&※*]+")


def norm(s: str) -> str:
    return _PUNCT.sub("", str(s or "")).lower()


def _load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    files = sorted(path.glob("**/*.json*")) if path.is_dir() else [path]
    for f in files:
        txt = f.read_text(encoding="utf-8").strip()
        if not txt:
            continue
        if f.suffix == ".jsonl":
            rows += [json.loads(l) for l in txt.splitlines() if l.strip()]
        else:
            data = json.loads(txt)
            rows += data if isinstance(data, list) else [data]
    return rows


def _won(x) -> str:
    try:
        return f"{float(x):,.0f}백만원"
    except (TypeError, ValueError):
        return str(x) if x else ""


def load_struct(path: Path | list[Path]) -> dict[tuple, list[dict]]:
    """(yr, 소관, 세부) → [{seq, lvl, item, bud}] 차례순. 레벨3·4 항목에 부모 레벨2 항목명(parent)을 붙인다."""
    by: dict[tuple, list[dict]] = {}
    for p in (path if isinstance(path, list) else [path]):
        for r in _load_rows(p):
            by.setdefault((int(r["yr"]), r["gwan"], r["sebu"]), []).append(r)
    for key, items in by.items():
        items.sort(key=lambda r: int(r["seq"]))
        p2 = p3 = None
        for it in items:
            lvl = int(it["lvl"])
            if lvl == 2:
                p2, p3 = it["item"], None
                it["parent"] = None
            elif lvl == 3:
                p3 = it["item"]
                it["parent"] = p2
            else:
                it["parent"], it["parent3"] = p2, p3
    return by


_NOISE = re.compile(r"(공고|공모|모집|안내|신청|접수|추가|재공고|참여\s*기업|참여\s*기관|교육생|운영사|수혜\s*기업|수행\s*기관|대상\s*기업|지원\s*기업|"
                    r"\d+차|상반기|하반기|제\d+회|사업$|지원사업$|지원$)")


def clean_title(name: str) -> str:
    """공고명을 비교용으로 정리: [지역] 접두어·연도·'모집 공고' 류 꼬리말 제거 후 정규화."""
    t = re.sub(r"^\s*\[[^\]]*\]\s*", "", str(name or ""))
    t = re.sub(r"(19|20)\d{2}\s*년(도)?", " ", t)
    t = re.sub(r"\(\s*(공고|모집)[^)]*\)", " ", t)
    prev = None
    while prev != t:
        prev, t = t, _NOISE.sub(" ", t).strip()
    return norm(t)


def _bigrams(s: str) -> set[str]:
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}


def dice(a: str, b: str) -> float:
    x, y = _bigrams(a), _bigrams(b)
    return 2 * len(x & y) / (len(x) + len(y)) if x and y else 0.0


def ministry_match(abbr: str, full: str) -> bool:
    """'중기부' ↔ '중소벤처기업부' 처럼 약칭이 정식 명칭의 부분수열이면 참."""
    a, f = norm(abbr), norm(full)
    if not a or not f:
        return True
    if a in f or f in a:
        return True
    it = iter(f)
    return all(ch in it for ch in a)


def load_gonggo_rows(dirs: list[Path]) -> list[dict]:
    """공고 매핑표 행 목록(연도·소관·세부·내역·정리된 공고명)."""
    out = []
    for d in dirs:
        for r in _load_rows(d):
            if r.get("nae") and r.get("name"):
                out.append({"yr": int(r["yr"]), "gwan": r["gwan"], "sebu": r["sebu"], "nae": r["nae"],
                            "name": r["name"], "title": clean_title(r["name"])})
    return out


def match_announcement(ann_name: str, ann_gwan: str, rows: list[dict], threshold: float = 0.5) -> tuple[dict | None, float]:
    """xlsx 공고명을 gonggo 공고명과 글자 2-gram Dice 계수로 대조해 가장 비슷한 행을 돌려준다(연도·부처 일치 우선)."""
    yr = 2026 if str(ann_name).startswith("2026") else 2025 if str(ann_name).startswith("2025") else 2026
    t = clean_title(ann_name)
    best, best_s = None, 0.0
    for r in rows:
        if not ministry_match(ann_gwan, r["gwan"]):
            continue
        sc = dice(t, r["title"]) + (0.05 if r["yr"] == yr else 0.0)
        if sc > best_s:
            best, best_s = r, sc
    return (best, best_s) if best_s >= threshold else (None, best_s)


def _calc_lines_for(calc: str, item: str) -> str:
    """산출근거 문장 중 내내역 항목명을 언급하는 줄만 추린다."""
    if not calc:
        return ""
    key = norm(item)
    keys = {key} | {k for k in re.split(r"[·ㆍ‧,/및\s]+", item) if len(norm(k)) >= 2 and norm(k) in key}
    out = []
    for line in re.split(r"[\n]+|(?=[□○ㅇ◦▪①-⑳])", calc):
        ln = norm(line)
        if key and key in ln or any(len(k) >= 3 and norm(k) in ln for k in keys):
            out.append(line.strip())
    return " ".join(out)[:600]


_STOP = {"지원", "사업", "운영", "기타", "및", "등", "확대", "강화", "육성", "활성화", "프로그램", "2025년", "2026년", "년"}


def _tokens(text: str, exclude: set[str] = frozenset()) -> set[str]:
    toks = {norm(t) for t in re.split(r"[\s·ㆍ‧(),/\[\]>]+", str(text or ""))}
    return {t for t in toks if len(t) >= 2 and t not in _STOP and t not in exclude}


def _tokens_overlap(ann_name: str, child: str, parent_names: str) -> bool:
    """공고명 어절과 내내역명 어절이 서로 포함 관계이면 참. 세부·내역사업명에 든 어절은 제외."""
    shared = _tokens(parent_names)
    a = _tokens(re.sub(r"^\d{4}년\s*", "", ann_name), shared)
    c = _tokens(child)
    return any(x in y or y in x for x in a for y in c)


def match_by_sebu(ann_name: str, ann_gwan: str, df: pd.DataFrame, sebu_groups: dict, head_threshold: float = 0.8) -> tuple[list[int], float]:
    """공고명 머리(괄호 앞)가 세부사업명과 거의 같으면, 괄호 안 어절이 내역·내내역 서술에 나타나는 단위를 고른다."""
    raw = re.sub(r"^\s*(19|20)\d{2}\s*년(도)?\s*", "", str(ann_name or ""))
    head = clean_title(re.split(r"[(\[]", raw, 1)[0])
    paren = " ".join(re.findall(r"[(\[]([^)\]]*)[)\]]", raw))
    if len(head) < 3:
        return [], 0.0
    best_key, best_s = None, 0.0
    for (gwan, sebu_t), idxs in sebu_groups.items():
        if not ministry_match(ann_gwan, gwan):
            continue
        sc = dice(head, sebu_t)
        if sc > best_s:
            best_key, best_s = (gwan, sebu_t), sc
    if best_s < head_threshold:
        return [], best_s
    idxs = sebu_groups[best_key]
    if len(idxs) == 1 or not paren:
        return idxs, best_s
    toks = _tokens(paren, _tokens(best_key[1]))
    if not toks:
        return idxs, best_s
    scored = []
    for i in idxs:  # 사업명 > 목적 > 내용 순으로 가중
        nm = norm(f"{df.at[i, '내역사업명']} {df.at[i, '내내역명']}")
        pur = norm(str(df.at[i, "목적"]))
        body = norm(str(df.at[i, "내용"])[:500])
        scored.append((sum(3 * (t in nm) + 2 * (t in pur) + (t in body) for t in toks), i))
    top = max(sc for sc, _ in scored)
    return ([i for sc, i in scored if sc == top] if top > 0 else idxs), best_s


def match_unit_name(ann_name: str, ann_gwan: str, unit_names: list[tuple], threshold: float = 0.5) -> tuple[int | None, float]:
    """공고명을 기존사업 단위명(세부+내역+내내역 / 내역+내내역)과 직접 대조한다."""
    t = clean_title(ann_name)
    best, best_s = None, 0.0
    for i, gwan, full_name, short_name in unit_names:
        if not ministry_match(ann_gwan, gwan):
            continue
        sc = max(dice(t, full_name), dice(t, short_name))
        if sc > best_s:
            best, best_s = i, sc
    return (best, best_s) if best_s >= threshold else (None, best_s)


def build_units(biz: pd.DataFrame, struct_dir: Path | list[Path] | None, parents_dir: Path | None,
                gonggo_dirs: list[Path], ann_df: pd.DataFrame | None, threshold: float = 0.55) -> pd.DataFrame:
    """similarity_check.load_biz 결과(내역사업 단위)를 내역·내내역 단위로 확장하고 공고정보로 보강한다."""
    df = biz.copy()
    df["단위"] = "내역사업"
    df["내내역명"] = ""
    df["연계공고"] = ""
    df["연도"] = df["연도"].astype(int)

    full: dict[tuple, dict] = {}
    if parents_dir:
        for r in _load_rows(parents_dir):
            full[(int(r["yr"]), r["gwan"], r["sebu"], r["nae"] or "")] = r

    # --- 내내역 확장 ---
    if struct_dir:
        struct = load_struct(struct_dir)
        new_rows, drop_idx = [], []
        for idx, r in df.iterrows():
            key = (r["연도"], r["부처"], r["세부사업명"])
            items = struct.get(key)
            if not items:
                continue
            children = [it for it in items if int(it["lvl"]) == 3 and norm(it.get("parent")) == norm(r["내역사업명"])]
            if not children:
                continue
            fr = full.get((r["연도"], r["부처"], r["세부사업명"], r["내역사업명"]), {})
            calc = fr.get("calc_full") or ""
            purpose = fr.get("npur_full") or fr.get("spur_full") or r["목적"]
            target = fr.get("tgt_full") or r["대상"]
            for ch in children:
                grand = [it for it in items if int(it["lvl"]) >= 4 and norm(it.get("parent3")) == norm(ch["item"])]
                sub = ("; 세부항목: " + ", ".join(f"{g['item']}({_won(g['bud'])})" for g in grand)) if grand else ""
                lines = _calc_lines_for(calc, ch["item"])
                nr = r.copy()
                nr["단위"] = "내내역사업"
                nr["내내역명"] = ch["item"]
                nr["공고이름"] = f"{r['공고이름']} > {ch['item']}"
                nr["목적"] = purpose
                nr["대상"] = target
                nr["규모"] = f"내내역예산 {_won(ch['bud'])}" if ch.get("bud") else r["규모"]
                nr["내용"] = (f"(내내역) {ch['item']}" + (f", 예산 {_won(ch['bud'])}" if ch.get("bud") else "") + sub
                              + (f" [산출근거] {lines}" if lines else "")
                              + f" [내역사업 {r['내역사업명']}] {purpose}"
                              + (f" [공고 지원내용] {fr['gonggo_full']}" if fr.get("gonggo_full") else ""))
                nr["행"] = f"{r['행']}/s{ch['id']}"
                new_rows.append(nr)
            drop_idx.append(idx)
        if new_rows:
            df = pd.concat([df.drop(index=drop_idx), pd.DataFrame(new_rows)], ignore_index=True)

    # --- 공고정보 보강 ---
    if ann_df is not None and gonggo_dirs:
        grows = load_gonggo_rows(gonggo_dirs)
        sebu_groups: dict[tuple[str, str], list[int]] = {}
        for i in df.index:
            sebu_groups.setdefault((df.at[i, "부처"], clean_title(df.at[i, "세부사업명"])), []).append(i)
        unit_names = [(i, df.at[i, "부처"], clean_title(f"{df.at[i, '세부사업명']} {df.at[i, '내역사업명']} {df.at[i, '내내역명']}"),
                       clean_title(f"{df.at[i, '내역사업명']} {df.at[i, '내내역명']}")) for i in df.index]
        key_of = {}
        for i, r in df.iterrows():
            key_of.setdefault((r["연도"], norm(r["부처"]), norm(r["세부사업명"]), norm(r["내역사업명"])), []).append(i)
        add: dict[int, list[dict]] = {}
        unmapped = 0
        mapping_log = []
        for _, a in ann_df.iterrows():
            name = a["공고이름"]
            yr = 2026 if name.startswith("2026") else 2025 if name.startswith("2025") else 2026
            hit, score = match_announcement(name, a.get("부처", ""), grows, threshold)
            cands = None
            if hit:
                gwan, sebu, nae = hit["gwan"], hit["sebu"], hit["nae"]
                cands = key_of.get((yr, norm(gwan), norm(sebu), norm(nae))) or key_of.get((2025 if yr == 2026 else 2026, norm(gwan), norm(sebu), norm(nae)))
                how = hit["name"]
            if not cands:  # 2단계: 공고명 머리(괄호 앞)가 세부사업명과 같으면 괄호 안 어절로 내역·내내역을 고른다
                cands2, score2 = match_by_sebu(name, a.get("부처", ""), df, sebu_groups)
                if cands2:
                    cands, how, score = cands2, "(세부사업명+괄호 어절 매칭)", score2
            if not cands:  # 3단계: 세부·내역·내내역 사업명과 직접 대조
                hit2, score2 = match_unit_name(name, a.get("부처", ""), unit_names, threshold)
                if hit2 is not None:
                    cands, how, score = [hit2], "(사업명 직접 매칭)", score2
            if not cands:
                unmapped += 1
                mapping_log.append((name, "", "", round(max(score, 0), 2)))
                continue
            mapping_log.append((name, how, df.at[cands[0], "공고이름"], round(score, 2)))
            # 내내역이 여러 개면 공고명과 항목명의 어절이 겹치는 것에 우선 배정, 없으면 모두에 배정
            tgt = [i for i in cands if df.at[i, "내내역명"] and _tokens_overlap(name, df.at[i, "내내역명"], sebu + " " + nae)]
            for i in (tgt or cands):
                add.setdefault(i, []).append(a)
        for i, anns in add.items():
            names = "; ".join(a["공고이름"] for a in anns)
            df.at[i, "연계공고"] = names
            df.at[i, "목적"] = df.at[i, "목적"] + " " + " ".join(f"[공고 목적] {a['목적']}" for a in anns if a["목적"])
            df.at[i, "내용"] = df.at[i, "내용"] + " " + " ".join(
                f"[공고 {a['공고이름']}] {a['내용']}" + (f" 규모: {a['규모']}" if a["규모"] else "") for a in anns)
            df.at[i, "대상"] = df.at[i, "대상"] + " " + " ".join(f"[공고 대상] {a['대상']}" for a in anns if a["대상"])
        df.attrs["ann_mapped"] = len(ann_df) - unmapped
        df.attrs["ann_unmapped"] = unmapped
        df.attrs["mapping_log"] = pd.DataFrame(mapping_log, columns=["공고이름", "매칭 공고명", "내역사업", "유사도"])
    return df.reset_index(drop=True)
