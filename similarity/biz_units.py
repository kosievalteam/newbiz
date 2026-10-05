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


def load_struct(path: Path) -> dict[tuple, list[dict]]:
    """(yr, 소관, 세부) → [{seq, lvl, item, bud}] 차례순. 레벨3·4 항목에 부모 레벨2 항목명(parent)을 붙인다."""
    by: dict[tuple, list[dict]] = {}
    for r in _load_rows(path):
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


def load_gonggo_map(dirs: list[Path]) -> dict[tuple[int, str], tuple[str, str, str]]:
    """(연도, 정규화 공고명) → (소관, 세부사업명, 내역사업명)"""
    m: dict[tuple[int, str], tuple[str, str, str]] = {}
    for d in dirs:
        for r in _load_rows(d):
            if r.get("nae") and r.get("name"):
                m.setdefault((int(r["yr"]), norm(r["name"])), (r["gwan"], r["sebu"], r["nae"]))
    return m


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


def build_units(biz: pd.DataFrame, struct_dir: Path | None, parents_dir: Path | None,
                gonggo_dirs: list[Path], ann_df: pd.DataFrame | None) -> pd.DataFrame:
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
        gmap = load_gonggo_map(gonggo_dirs)
        key_of = {}
        for i, r in df.iterrows():
            key_of.setdefault((r["연도"], norm(r["부처"]), norm(r["세부사업명"]), norm(r["내역사업명"])), []).append(i)
        add: dict[int, list[dict]] = {}
        unmapped = 0
        for _, a in ann_df.iterrows():
            name = a["공고이름"]
            yr = 2026 if name.startswith("2026") else 2025 if name.startswith("2025") else 2026
            hit = gmap.get((yr, norm(name))) or gmap.get((2025 if yr == 2026 else 2026, norm(name)))
            if not hit:
                unmapped += 1
                continue
            gwan, sebu, nae = hit
            cands = key_of.get((yr, norm(gwan), norm(sebu), norm(nae))) or key_of.get((2025 if yr == 2026 else 2026, norm(gwan), norm(sebu), norm(nae)))
            if not cands:
                unmapped += 1
                continue
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
    return df.reset_index(drop=True)
