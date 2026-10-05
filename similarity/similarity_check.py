"""신규 협의사업 ↔ 기존 지원사업 유사·중복성 임베딩 분석.

입력
  - 기존사업: 「2026년 중앙부처 지원사업 공고정보」 xlsx (사업개요 열의 ①목적/②내용/③대상/④규모 구조)
             + (선택) kosievalteam.github.io/biz_info 의 2025·2026년 내역사업 자료(--biz, Supabase public.biz 추출 JSON)
  - 신규사업: new_project_profile.json (사업목적·지원대상·지원내용·전달체계 4개 축 서술, 전체/내역사업 단위)
방법
  - 축별 텍스트를 BAAI/bge-m3 로 임베딩 → 코사인 유사도
  - 가중치: 「유사·중복사업 대상 선정 분석 지표(안)」 20/30/30/15 를 합 100 으로 정규화
    (사업목적 21.05, 지원내용 31.58, 지원대상 31.58, 전달체계 15.79)
  - 종합 유사도(0~100) = Σ 가중치 × 축별 코사인 유사도
  - 참고2 5단계 등급(상이/낮음/보통/높음/동일)은 코퍼스 내 축별 z-점수로 매핑한 참고치
출력
  - <out>/similarity_scores.xlsx : 단위별 전체 순위표 + 가중치 시트
  - <out>/top10.json              : 전체 단위 상위 10개 (보고서 작성용)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import openpyxl
import pandas as pd

AXES = ["사업목적", "지원내용", "지원대상", "전달체계"]
RAW_W = {"사업목적": 20, "지원내용": 30, "지원대상": 30, "전달체계": 15}      # 참고2 원 가중치(합 95)
W = {k: v / sum(RAW_W.values()) * 100 for k, v in RAW_W.items()}           # 합 100 정규화
# 참고2 5단계 배점(상이→동일) 을 축 가중치 대비 비율로 환산
GRADE_RATIO = {
    "사업목적": [0, 5 / 20, 10 / 20, 15 / 20, 1.0],
    "지원내용": [0, 6 / 30, 14 / 30, 22 / 30, 1.0],
    "지원대상": [0, 6 / 30, 14 / 30, 22 / 30, 1.0],
    "전달체계": [0, 3 / 15, 7 / 15, 11 / 15, 1.0],
}
GRADE_NAME = ["상이", "낮음", "보통", "높음", "동일"]
Z_CUTS = [0.0, 1.0, 2.0, 3.0]  # z < 0 상이, 0~1 낮음, 1~2 보통, 2~3 높음, ≥3 동일

DELIVERY_KW = [
    ("바우처", "바우처"), ("보조금", "보조금"), ("출연", "출연"), ("융자", "융자"), ("대출", "융자"),
    ("보증", "보증"), ("투자", "투자"), ("펀드", "투자"), ("교육", "교육과정 운영"), ("훈련", "교육과정 운영"),
    ("인턴", "인턴십"), ("채용", "채용연계"), ("취업", "채용연계"), ("실증", "실증·테스트"), ("테스트", "실증·테스트"),
    ("PoC", "실증·테스트"), ("매칭", "매칭"), ("컨설팅", "컨설팅"), ("멘토", "멘토링"), ("공모", "공모 선정"),
    ("선정", "공모 선정"), ("자격", "자격취득 지원"), ("응시료", "자격취득 지원"), ("위탁", "위탁운영"),
    ("플랫폼", "플랫폼 운영"), ("인건비", "인건비 지원"), ("장려금", "장려금"), ("지원금", "지원금"),
]


def load_existing(xlsx: Path) -> pd.DataFrame:
    ws = openpyxl.load_workbook(xlsx, read_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    hdr = rows[1]
    markers = [("목적", r"①\s*목적\s*[:：]?"), ("내용", r"②\s*내용\s*[:：]?"),
               ("대상", r"③\s*대상\s*[:：]?"), ("규모", r"④\s*규모\s*[:：]?"), ("설명", r"⑤\s*설명\s*[:：]?")]
    recs = []
    for idx, r in enumerate(rows[3:], start=4):
        if not r[7]:
            continue
        d = dict(zip(hdr, r))
        ov = d.get("사업개요") or ""
        found = sorted((m.start(), m.end(), k) for k, p in markers if (m := re.search(p, ov)))
        rec = {k: (str(d[k]).strip() if d[k] is not None else "") for k in hdr if k != "사업개요"}
        rec["행"] = idx
        for i, (s, e, k) in enumerate(found):
            end = found[i + 1][0] if i + 1 < len(found) else len(ov)
            rec[k] = re.sub(r"\s+", " ", ov[e:end]).strip()
        for k, _ in markers:
            rec.setdefault(k, "")
        m2 = re.search(r"【사업개요】\s*(.*?)\n", ov)
        rec["개요라인"] = m2.group(1).strip() if m2 else ""
        recs.append(rec)
    return pd.DataFrame(recs)


EXTRA_COLS = ["부처", "기관", "공고이름", "목적", "내용", "대상", "규모", "설명", "대분류", "중분류",
              "대상유형", "업종", "정책목적", "신규/기존", "공고링크"]


def load_extra(path: Path) -> pd.DataFrame:
    """내역사업 목록 등 추가 기존사업 표를 같은 스키마로 읽는다 (csv/xlsx, 열 이름 기준)."""
    raw = pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path)
    missing = [c for c in ("공고이름", "목적", "내용", "대상") if c not in raw.columns]
    if missing:
        raise SystemExit(f"{path}: 필수 열 누락 {missing}")
    df = pd.DataFrame({c: raw[c].fillna("").astype(str).str.strip() if c in raw.columns else "" for c in EXTRA_COLS})
    df["행"] = [f"{path.name}:{i + 2}" for i in range(len(df))]
    df["개요라인"] = ""
    return df


BIZ_METHOD = {"직접": "직접수행", "출연": "기관출연", "보조": "기관보조(국고보조금)", "융자": "융자", "위탁": "외주용역·위탁",
              "민간경상보조": "민간경상보조", "민간자본보조": "민간자본보조", "출자": "출자"}


def load_biz(path: Path, years: tuple[int, ...] = (2025, 2026), dedupe: bool = True) -> pd.DataFrame:
    """kosievalteam.github.io/biz_info 의 내역사업 자료(Supabase public.biz 추출 JSON/JSONL)를 공통 스키마로 읽는다.

    열 별칭: id, yr, gb(구분), gwan(소관), sebu(세부사업명), nae(내역사업명), nbud(내역예산), sbud(세부예산),
    npur(내역목적), spur(세부목적, 내역목적과 다를 때만), tgt(수혜대상), meth(세부지원), scale(지원규모), org(세부추진기관),
    big/mid/small(지원분야 대·중·소분류), ind(지원산업), sfield/nfield(세부·내역분야), gonggo(공고지원내용),
    cont(세부내용), calc(내역산출근거), law(근거법령), key(예산서키)
    """
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
    raw = pd.DataFrame(rows)
    raw = raw[raw["yr"].astype(int).isin(years)].copy()
    raw = raw.drop_duplicates("id")
    g = lambda c: raw[c].fillna("").astype(str).str.strip() if c in raw.columns else pd.Series([""] * len(raw), index=raw.index)
    purpose = g("npur").where(g("npur") != "", g("spur"))
    keep = purpose != ""
    raw, purpose = raw[keep], purpose[keep]
    g = lambda c: raw[c].fillna("").astype(str).str.strip() if c in raw.columns else pd.Series([""] * len(raw), index=raw.index)
    sebu, nae = g("sebu"), g("nae")
    suffix = pd.Series(" > ", index=raw.index) + nae
    suffix[(nae == "") | (nae == sebu)] = ""
    name = raw["yr"].astype(str) + "년 " + sebu + suffix
    content = (purpose.where(g("spur") == "", g("spur") + " / (내역) " + purpose)
               + g("gonggo").map(lambda x: f" [공고 지원내용] {x}" if x else "")
               + g("cont").map(lambda x: f" [세부내용] {x}" if x else "")
               + g("calc").map(lambda x: f" [산출근거] {x}" if x else ""))
    def _won(x: str, label: str) -> str:
        if not x:
            return ""
        try:
            return f"{label} {float(x):,.0f}백만원"
        except ValueError:
            return f"{label} {x}"
    scale = g("scale").map(lambda x: _won(x, "지원규모")).where(g("scale") != "", g("nbud").map(lambda x: _won(x, "내역예산")))
    meth = g("meth").map(lambda m: ";".join(BIZ_METHOD.get(t.strip(), t.strip()) for t in m.split(";") if t.strip()))
    df = pd.DataFrame({
        "부처": g("gwan"), "기관": g("org"), "공고이름": name, "목적": purpose, "내용": content.str.strip(),
        "대상": g("tgt"), "규모": scale, "설명": g("law").map(lambda x: f"근거법령 {x}" if x else ""),
        "대분류": g("big").where(g("big") != "", g("nfield").where(g("nfield") != "", g("sfield"))),
        "중분류": g("mid"), "대상유형": "", "업종": g("ind"), "정책목적": "", "신규/기존": g("gb") + " 내역사업",
        "공고링크": "https://kosievalteam.github.io/biz_info/  (예산서키: " + g("key") + ")",
        "행": "biz:" + raw["id"].astype(str), "개요라인": "",
        "시행방법": meth, "연도": raw["yr"].astype(int), "세부사업명": sebu, "내역사업명": nae,
    })
    if dedupe:  # 동일 (구분, 소관, 세부, 내역) 사업은 최신 연도 1건만 남긴다 (공백·기호 차이는 무시)
        norm = lambda col: df[col].str.replace(r"[\s·ㆍ‧\-_()\[\]]+", "", regex=True).str.lower()
        df["_k"] = df["신규/기존"] + "|" + norm("부처") + "|" + norm("세부사업명") + "|" + norm("내역사업명")
        df = df.sort_values("연도", ascending=False).drop_duplicates("_k").sort_values("행").drop(columns="_k")
    return df.reset_index(drop=True)


def delivery_text(r: pd.Series) -> str:
    org = r["기관"] or ""
    explicit = r.get("시행방법", "") if isinstance(r.get("시행방법", ""), str) else ""
    if explicit:
        method = f"수행기관 {org or '미상'}, 시행방법 {explicit}"
    else:
        method = "직접수행" if org == "직접수행" else f"수행기관 {org}(기관보조·위탁)"
    blob = " ".join([r["내용"], r["규모"], r["설명"]])
    kws = []
    for pat, label in DELIVERY_KW:
        if pat.lower() in blob.lower() and label not in kws:
            kws.append(label)
    return f"주관부처 {r['부처']} → {method}. 지원유형 {r['대분류']}/{r['중분류']}. 지원방식: {', '.join(kws) or '미상'}. 규모: {r['규모']}"


def axis_texts(df: pd.DataFrame) -> dict[str, list[str]]:
    return {
        "사업목적": [f"{r['목적']} (정책목적: {r['정책목적'] or r['대분류']})" for _, r in df.iterrows()],
        "지원내용": [f"{r['내용']} {('규모: ' + r['규모']) if r['규모'] else ''} {r['설명']}".strip() for _, r in df.iterrows()],
        "지원대상": [f"{r['대상']} (대상유형: {r['대상유형']}, 업종: {r['업종']})" for _, r in df.iterrows()],
        "전달체계": [delivery_text(r) for _, r in df.iterrows()],
    }


def grade(z: float, axis: str) -> tuple[str, float]:
    lvl = sum(z >= c for c in Z_CUTS)
    return GRADE_NAME[lvl], GRADE_RATIO[axis][lvl] * W[axis]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--profile", default=str(Path(__file__).with_name("new_project_profile.json")))
    ap.add_argument("--out", default="output/similarity")
    ap.add_argument("--model", default="BAAI/bge-m3")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--biz", default=None,
                    help="biz_info 내역사업 추출 JSON 파일 또는 폴더(Supabase public.biz, 열 별칭은 load_biz 참고)")
    ap.add_argument("--biz-years", default="2025,2026")
    ap.add_argument("--level", choices=["announcement", "naeyeok"], default="announcement",
                    help="naeyeok: 기존사업 단위를 내역·내내역사업으로 구성하고 공고정보는 보강 자료로만 사용")
    ap.add_argument("--struct", action="append", default=[], help="biz_struct 추출 JSON 폴더(레벨>=2), 여러 번 지정 가능")
    ap.add_argument("--parents-full", default=None, help="내내역 보유 내역사업의 전체 텍스트 JSON 폴더")
    ap.add_argument("--gonggo", action="append", default=[], help="gonggo 추출 JSON 폴더(공고명↔내역사업 매핑)")
    ap.add_argument("--extra", action="append", default=[],
                    help="추가 기존사업 표(csv/xlsx). 필수 열: 공고이름, 목적, 내용, 대상 / 선택 열: 부처, 기관, 규모, 설명, 대분류, 중분류, 대상유형, 업종, 정책목적, 신규/기존, 공고링크")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    df = load_existing(Path(a.xlsx))
    df["신규/기존"] = "공고 " + df["신규/기존"].fillna("").astype(str)
    df["출처"] = "공고정보"
    if a.level == "naeyeok":
        if not a.biz:
            raise SystemExit("--level naeyeok 에는 --biz 가 필요합니다")
        from biz_units import build_units
        biz = load_biz(Path(a.biz), tuple(int(y) for y in a.biz_years.split(",")))
        units = build_units(biz, [Path(d) for d in a.struct] or None,
                            Path(a.parents_full) if a.parents_full else None,
                            [Path(g) for g in a.gonggo], df)
        units["출처"] = units["단위"]
        print(f"내역사업 {len(biz)}건 → 내역·내내역 단위 {len(units)}건 "
              f"({units['단위'].value_counts().to_dict()}), 공고 매핑 {units.attrs.get('ann_mapped')}건/미매핑 {units.attrs.get('ann_unmapped')}건")
        df = units
    elif a.biz:
        biz = load_biz(Path(a.biz), tuple(int(y) for y in a.biz_years.split(",")))
        biz["출처"] = "내역사업"
        print(f"내역사업 {len(biz)}건 병합 (연도 {a.biz_years}, 중복 사업은 최신 연도만)")
        df = pd.concat([df, biz], ignore_index=True)
    for extra in a.extra:
        ex = load_extra(Path(extra)); ex["출처"] = Path(extra).name
        df = pd.concat([df, ex], ignore_index=True)
    df = df.fillna("")
    prof = json.load(open(a.profile, encoding="utf-8"))
    print(f"기존사업 {len(df)}건, 신규사업 단위 {list(prof['units'])}")

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(a.model, device="cpu")
    enc = lambda xs: model.encode(xs, normalize_embeddings=True, batch_size=16, show_progress_bar=False)

    texts = axis_texts(df)
    emb = {ax: enc(texts[ax]) for ax in AXES}

    sheets: dict[str, pd.DataFrame] = {}
    summary = {}
    for unit, spec in prof["units"].items():
        cols = ["행", "출처", "부처", "기관", "공고이름", "대분류", "중분류", "대상유형", "업종", "신규/기존", "공고링크"]
        cols += [c for c in ("단위", "연도", "세부사업명", "내역사업명", "내내역명", "시행방법", "규모", "연계공고") if c in df.columns]
        res = df[cols].copy()
        total = np.zeros(len(df))
        gtotal = np.zeros(len(df))
        for ax in AXES:
            q = enc([spec[ax]])[0]
            sim = emb[ax] @ q
            z = (sim - sim.mean()) / sim.std()
            res[f"{ax}_유사도"] = np.round(sim, 4)
            res[f"{ax}_가중점수"] = np.round(sim * W[ax], 2)
            gr = [grade(float(v), ax) for v in z]
            res[f"{ax}_등급"] = [g for g, _ in gr]
            res[f"{ax}_지표점수"] = [round(p, 1) for _, p in gr]
            total += sim * W[ax]
            gtotal += np.array([p for _, p in gr])
        res["종합유사도(0~100)"] = np.round(total, 2)
        res["참고2지표점수(0~100)"] = np.round(gtotal, 1)
        res = res.sort_values("종합유사도(0~100)", ascending=False).reset_index(drop=True)
        res.insert(0, "순위", res.index + 1)
        for ax in AXES:
            res[f"{ax}_텍스트"] = [texts[ax][df.index[df["행"] == h][0]] for h in res["행"]]
        sheets[unit] = res
        summary[unit] = res.head(a.top).to_dict(orient="records")
        print(f"\n[{unit}] 상위 {a.top}")
        for _, r in res.head(a.top).iterrows():
            print(f"  {r['순위']:>2} {r['종합유사도(0~100)']:6.2f} | {r['부처']}({r['기관']}) {r['공고이름']}  "
                  f"목적{r['사업목적_유사도']:.2f} 내용{r['지원내용_유사도']:.2f} 대상{r['지원대상_유사도']:.2f} 전달{r['전달체계_유사도']:.2f}")

    wdf = pd.DataFrame({"분석항목": AXES, "참고2 원가중치": [RAW_W[a_] for a_ in AXES],
                        "정규화 가중치(합100)": [round(W[a_], 2) for a_ in AXES],
                        "5단계 배점(상이/낮음/보통/높음/동일)": [
                            "/".join(str(round(r * W[a_], 1)) for r in GRADE_RATIO[a_]) for a_ in AXES]})
    with pd.ExcelWriter(out / "similarity_scores.xlsx", engine="openpyxl") as xw:
        wdf.to_excel(xw, sheet_name="가중치", index=False)
        for unit, res in sheets.items():
            res.to_excel(xw, sheet_name=unit[:31], index=False)
    json.dump({"weights": W, "model": a.model, "n_existing": int(len(df)), "top": summary},
              open(out / "top10.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(f"\n저장: {out / 'similarity_scores.xlsx'}")


if __name__ == "__main__":
    main()
