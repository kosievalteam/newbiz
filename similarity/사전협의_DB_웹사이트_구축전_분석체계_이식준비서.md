# 사전협의 DB·웹사이트 구축 전 분석체계 이식 준비서

- 작성일: 2026-11-23
- 목적: 향후 **별도 웹사이트 형태의 사전협의 DB**를 구축할 때, 현재 Claude Code에서 운용 중인 유사·중복 분석체계를 **변경 없이** 적용해 결과물 3종(DOCX·PNG·XLSX)을 생성·조회·다운로드할 수 있도록 사전 정리
- 범위: **조사·정리 전용.** DB 구축·웹사이트 개발·코드 수정·분석 재실행을 하지 않았고, 기존 파일을 읽기 전용으로만 확인함
- 선행 문서: `similarity/사전협의_유사중복_분석방법론_재현성_명세서.md`(2026-11-23, 커밋 `dbf9f75`). 산식·실행경로 감사 결과는 그 문서에 있고, 본 문서는 **이식 가능성**에 초점을 둠
- 표기: **[확인]** 코드·산출물로 직접 확인 / **[추론]** 코드상 따라 나오나 실행 미확인 / **[확인필요]** 확인 불가, 임의 판단하지 않음

---

## 0. 먼저 알아야 할 다섯 가지

**(1) 산식 부분은 이미 이식 가능한 상태다.** 종합 유사도는 `similarity/similarity_check.py`의 상수 4개와 20줄 남짓한 계산으로 전부 결정되고, 산출물만으로 역산해 재현을 확인했다(기존 xlsx 1,222행 최대 오차 0.0079, 직접비교 57행 전부 통과).

**(2) 웹 서비스용 벡터 검색 경로가 이미 한 벌 만들어져 있다.** `embed_corpus.py` → `load_embeddings.py` → Supabase `public.biz_embedding`(4개 축 `vector(1024)`, HNSW 코사인 인덱스) → RPC `match_biz` → `review_draft/similarity_query.py`. README에 운영 절차까지 적혀 있다. **웹사이트는 이것을 처음부터 만들 필요가 없다.** 다만 아래 (3)(4)의 제약이 있다.

**(3) 그 경로는 결과물 3종을 다 만들지 못한다.** `match_biz`는 **상위 k건만** 돌려주므로 코퍼스 전체 분포(평균·표준편차·p99·평균+2σ)와 **5단계 등급·지표(안) 환산점수를 산출할 수 없다.** 현재 보고서 §2 "(분포)" 항목과 xlsx의 등급 열이 바로 이 값들이다. **전수 점수가 필요하면 전수 계산 경로를 따로 둬야 한다.**

**(4) 결과물 3종 중 사람이 쓰는 부분이 실질적으로 가장 크다.** XLSX는 전부 코드가 만들지만, **PNG의 모든 문장**(헤드라인·부제·행 설명·유형카드 3개·시사점 3개·비고)과 **DOCX의 본문 전체**는 Claude가 작성한다. 그리고 그 앞단의 **4개 축 프로필 작성**과 **기능 단위 분리**도 코드가 아니라 Claude가 한다. **웹사이트가 "신규 분석"을 제공하려면 LLM 실행환경이 반드시 필요하다**(§6).

**(5) 지금 컨테이너에서 즉시 실행되지 않는 것들이 있다.** torch·sentence-transformers·olefile 미설치, bge-m3 모델 캐시 없음, `docx` npm 패키지 없음, `report_figure.py`의 Chromium 기본 경로가 깨져 있음(`chromium-1194/chrome-linux` → 실제는 `chromium-1243/chrome-linux64`). 모두 환경 문제이고 산식과 무관하지만, **이식 체크리스트에 그대로 들어가야 한다.**

---

## 1. 기존 유사도 분석 파이프라인

### 1.1 전체 흐름

```
[입력]  협의요청서(.hwp/.hwpx/.pdf) + (선택) 사업설명자료
          │
          ① 텍스트 추출            ← 코드
          ▼
       원문 평문
          │
          ② 4개 축 프로필 작성      ← ★ Claude (코드 없음)
          ▼
   new_project_profile_<사업명>.json
       { units: { "전체": {4개 축}, "기능N_…": {4개 축} } }
          │
          ③ 유사도 전수 산출        ← 코드 (bge-m3 + 코사인 + 가중합 + z등급)
          ▼  similarity_check.py
   out/similarity_scores.xlsx  +  out/top10.json
          │
          ④ 메타데이터 병합         ← 코드 (단, 현재 저장소에 없음)
          ▼
   유사도_산출결과_<사업명>.xlsx                       ◀── 결과물 ③ XLSX
          │
     ┌────┴───────────────────────────┐
     │                                 │
     ⑤ 보고서 작성 ← ★ Claude          ⑥ 그림 명세 작성 ← ★ Claude
     ▼                                 ▼
 유사중복_검토_<사업명>.md         figures/figure_spec_<사업명>.json
     │                                 │
     ⑦ DOCX 변환 ← 코드               ⑧ PNG 렌더 ← 코드
     ▼                                 ▼
 유사중복_검토_<사업명>.docx        figures/보고그림_<사업명>.png
   ◀── 결과물 ① DOCX                   ◀── 결과물 ② PNG
     │
     ⑨ 수치 정합 검증 ← 코드(Claude가 매번 작성하는 verify.py)
```

### 1.2 산식 (변경 금지) **[확인]**

축 $ax \in \{$사업목적, 지원내용, 지원대상, 전달체계$\}$에 대해

$$\mathrm{cos}^{ax} = \frac{f(t^{ax})}{\lVert f(t^{ax})\rVert_2}\cdot\frac{f(s^{ax})}{\lVert f(s^{ax})\rVert_2}, \qquad S = \sum_{ax} W_{ax}\,\mathrm{cos}^{ax}$$

| 축 | 지표(안) 배점 | $W_{ax}$ | 정확값 |
|---|---|---|---|
| 사업목적 | 20 | 21.05 | 21.0526315789474 |
| 지원내용 | 30 | 31.58 | 31.5789473684211 |
| 지원대상 | 30 | 31.58 | 31.5789473684211 |
| 전달체계 | 15 | 15.79 | 15.7894736842105 |
| **합** | 95 | **100.00** | 100.0 |

등급: 축별 코사인의 **코퍼스 내 z-점수**(모표준편차 ddof=0)를 경계 0/1/2/3으로 5단계(상이·낮음·보통·높음·동일)로 나누고, 지표(안) 점수열을 축 가중치 비율로 환산한다. **코퍼스 상대 기준이므로 비교 풀이 바뀌면 같은 사업의 등급이 바뀐다.**

모델: `BAAI/bge-m3`, CPU, `normalize_embeddings=True`(→ 내적 = 코사인), `batch_size=16`, 1024차원. 프롬프트 접두어·전처리·난수 시드 없음.

### 1.3 자동 계산과 Claude 수행의 경계 **[확인]**

| 단계 | 수행 | 결정론적? |
|---|---|---|
| ① 텍스트 추출 | 코드 | 예 |
| **② 4개 축 프로필 작성** | **Claude** | **아니오** |
| **② 기능 단위 분리** | **Claude** | **아니오** |
| ③ 임베딩·코사인·가중합·등급·순위 | 코드 | 예(환경 고정 시) |
| ④ 메타 병합 | 코드 | 예 |
| **⑤ 보고서 본문** | **Claude** | **아니오** |
| **⑥ 그림 명세 문장** | **Claude** | **아니오** |
| ⑦ DOCX 변환 | 코드 | 예 |
| ⑧ PNG 렌더 | 코드 | 예(브라우저 버전 고정 시) |
| ⑨ 수치 검증 | 코드(Claude 작성) | 예 |

> "AI가 유사도 점수를 매긴다"는 표현은 정확하지 않다. **점수는 전적으로 수식이 정한다.** Claude가 정하는 것은 **수식에 넣는 입력 문장(②)**과 **나온 점수의 해석(⑤⑥)**이다.

---

## 2. 필수 코드·스킬·설정·템플릿 목록

### 2.1 핵심 실행 코드

| 경로 | 역할 | 의존 | 확보 |
|---|---|---|---|
| `similarity/similarity_check.py` | **파이프라인 본체.** 상수(AXES/RAW_W/W/GRADE_RATIO/Z_CUTS/DELIVERY_KW), 코퍼스 로더 3종, 축 텍스트 조립, 임베딩·코사인·가중합·등급, xlsx/json 출력 | numpy, pandas, openpyxl, sentence-transformers, torch, `biz_units.py` | **있음** |
| `similarity/biz_units.py` | 내역·내내역 단위 구성, 공고명 3단계 퍼지 매핑(Dice 2-gram) | pandas | **있음** |
| `similarity/direct_compare.py` | **협의사업 간 직접 비교.** `similarity_check`의 상수·인코딩을 import해 재사용 | sentence-transformers, pandas | **있음** |
| `similarity/report_figure.py` | **PNG 생성.** xlsx+spec → HTML → Chromium 스크린샷 → PIL 여백 제거 | pandas, PIL, Chromium | **있음** |
| `similarity/direct_figure.py` | 직접 비교용 PNG(=`report_figure`를 import해 하단 문장만 교체) | 위와 동일 | **있음** |
| `similarity/md2docx.js` | **DOCX 생성(스킬 규정 도구).** 개조식 위계·표를 Word로 변환 | Node + npm `docx` | **코드 있음 / 패키지 없음** |
| `similarity/embed_corpus.py` | 코퍼스 임베딩 → `.npz` + `corpus_meta.json` | sentence-transformers, numpy, openpyxl | **있음** |
| `similarity/load_embeddings.py` | `.npz` → Supabase `biz_embedding` 적재(RPC `upsert_biz_embedding`) | numpy, urllib | **있음** |
| `review_draft/similarity_query.py` | **pgvector 검색 클라이언트.** 프로필 → 임베딩 → RPC `match_biz` → `top10.json` | urllib, (sentence-transformers 선택) | **있음** |
| `review_draft/similarity_io.py` | 유사도 산출물(xlsx/top10.json) 읽기 | pandas | **있음** |
| `.claude/skills/.../scripts/extract_text.py` | **HWP 5.x / HWPX / PDF 텍스트 추출.** 외부 바이너리 불필요 | olefile, zlib | **있음** |
| `.claude/skills/.../scripts/validate_chunks.py` | 추출 청크 JSON 행 수·ID 연속성 검증 | — | **있음** |
| `similarity/biz_export.sql` | Supabase 추출 질의 4종(열 별칭 고정) | — | **있음** |

### 2.2 스킬·참고문서

| 경로 | 역할 | 확보 |
|---|---|---|
| `.claude/skills/sme-similarity-review/SKILL.md` | 절차 전체(Step 0~6), 산출 기준 요약, 함정 | **있음** |
| `references/methodology.md` | 축 텍스트 구성표, 가중치·등급 근거, 단위 규칙, 공고 매핑 3단계, 해석 기준 | **있음** |
| `references/profile_guide.md` | **4개 축 프로필 작성 규칙**(축별 넣을 것/뺄 것, 출처 우선순위, 150~400자, 기존사업명 금지) | **있음** |
| `references/report_template.md` | **보고서 틀과 문체 규칙**, 작성 후 점검 체크리스트 7항목 | **있음** |
| `references/data_sources.md` | xlsx 스키마, Supabase 테이블 구조, 추출 절차 | **있음** |
| `assets/new_project_profile.example.json` | 프로필 예시(전체 + 내역 2개) | **있음** |
| `evals/evals.json` | 스킬 평가 케이스 | **있음** |

### 2.3 자산·설정

| 경로 | 역할 | 확보 |
|---|---|---|
| `.claude/skills/.../assets/fonts/*.woff2` (6종) | Noto Sans KR 400/500/700 × 한글/라틴. **PNG에 임베드**되므로 서버에 한글 글꼴이 없어도 동일 렌더링 | **있음** |
| `similarity/assets/fonts/` | 위와 동일 사본 | **있음** |
| `similarity/requirements.txt` | 실행 패키지(하한만 지정) | **있음** |
| `pyproject.toml` `[similarity]` extra | torch·sentence-transformers·openpyxl·pandas | **있음** |

### 2.4 기존 분석 사례(이식 검증용 기준자료) **[확인]**

| 자산 | 건수 | 비고 |
|---|---|---|
| `similarity/results/유사중복_검토_*.md` | 44 | 보고서 원본 |
| `similarity/results/*.docx` | 44 | **md2docx.js 31건 / pandoc 13건**(§3.2) |
| `similarity/results/figures/*.png` | 42 | |
| `similarity/results/figures/figure_spec_*.json` | 42 | 그림 명세 |
| `similarity/results/유사도_산출결과_*.xlsx` | 40 | **4개 축 입력 텍스트 포함** |
| `similarity/results/new_project_profile_*.json` | 39 | |
| `similarity/results/직접비교_*.json` | 6 | 협의사업 간 비교 |
| `similarity/scripts/<케이스>/verify.py` | 4 | 수치 검증 스크립트 |

### 2.5 **확보되지 않은 자산** **[확인]**

| 자산 | 상태 | 영향 | 복구 |
|---|---|---|---|
| `corpus_3631_v2.csv` | **소실**(스크래치패드 전용, 미커밋) | 최근 분석의 실제 비교 코퍼스 | **가능** — 커밋된 xlsx 40건의 `행`+4개 축 `_텍스트` 열로 복원 |
| `v2030_전체_메타.xlsx` | **소실** | 단위·연도·세부사업명 등 메타 | **가능** — 같은 방법 |
| `finalize.py`(메타 병합) | **소실**, 문서화 없음 | 결과물 ③ XLSX의 최종 형태를 만드는 단계 | 재작성 필요. 조인 키는 `행`의 숫자 접미사 **[확인]** |
| `match_biz` / `upsert_biz_embedding` / `biz_embedding_stats` SQL 정의 | 저장소에 **없음** | 가중합이 SQL 안에 있음 | DB에서 `pg_get_functiondef`로 추출 필요 **[확인필요]** |
| bge-m3 모델 가중치 | 캐시 없음, revision 미고정 | **재현성 최대 위험** | 재다운로드 + revision 고정 필요 |
| 원문 `.hwp/.hwpx` | 미커밋(`.gitignore`) | 입력 원본 | 담당 부서 보유분 |

### 2.6 현재 환경 **[확인]**

| 항목 | 상태 |
|---|---|
| Python 3.13.18 / numpy 2.5.3 / pandas 3.0.5 / openpyxl 3.1.5 / Pillow 12.3.0 | **있음** |
| **torch / sentence-transformers / olefile** | **없음** |
| Node 22.23.5 / npm 10.9.9 | **있음** |
| **npm `docx`** | **없음** (md2docx.js 실행 불가) |
| pandoc 3.1.3 | 있음 |
| Chromium | `/opt/pw-browsers/chromium-1243/chrome-linux64/chrome` |
| `report_figure.py` 기본 `--chrome` | `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` → **현재 경로와 불일치. `--chrome` 명시 필요** |
| `requirements.txt`가 적은 검증 환경 | Python 3.11 / torch 2.14 / sentence-transformers 6.1 / pandas 3.0 / numpy 2.4 |

---

## 3. 기존 결과물 3종 생성 절차

### 3.1 XLSX — `유사도_산출결과_<사업명>.xlsx`

**생성 코드**: `similarity_check.py` → (메타 병합 `finalize.py`)

**시트 구성** **[확인]**

| 시트 | 내용 |
|---|---|
| `가중치` | 분석항목·참고2 원가중치·정규화 가중치(합100)·5단계 배점 (4행) |
| `전체` | 전 단위 순위표. **42열** |
| `<기능 단위>` | 프로필 `units`의 각 키마다 1시트(시트명 31자 절단) |
| `공고매핑` | 공고이름·매칭 공고명·내역사업·유사도 |

**`전체` 시트 열 순서** **[확인]**
```
순위 | 단위 | 연도 | 세부사업명 | 내역사업명 | 내내역명 | 부처 | 기관 | 공고이름 | 시행방법 | 규모 | 연계공고 |
행 | 출처 | 대분류 | 중분류 | 대상유형 | 업종 | 신규/기존 | 공고링크 |
(사업목적|지원내용|지원대상|전달체계) × (_유사도 | _가중점수 | _등급 | _지표점수) |
종합유사도(0~100) | 참고2지표점수(0~100) |
사업목적_텍스트 | 지원내용_텍스트 | 지원대상_텍스트 | 전달체계_텍스트
```

**반올림 규칙** **[확인]** — 이식 시 그대로 지켜야 한다

| 값 | 규칙 |
|---|---|
| `*_유사도` | 원값을 4자리 반올림해 저장 |
| `*_가중점수` | **원값** × W를 2자리 반올림 |
| `*_지표점수` | 1자리 |
| `종합유사도` | **원값** 합을 2자리 — 저장된 4자리 유사도로 역산하면 최대 0.01 오차 |
| `참고2지표점수` | **원값** 합을 1자리 — 축별 지표점수 합과 최대 0.2 차이 |

> **주의 1**: 정렬은 **2자리 반올림 값**으로 하고 pandas 기본 불안정 정렬을 쓴다. 2026-0319에서 1,222행 중 **734행(60%)이 동점**이었고 동점군 내부 순서가 원본 순서를 보존하지 않았다. **동점 구간 순위는 산술적 의미가 없다.**
> **주의 2**: 최근 분석의 `공고매핑` 시트는 **해당 분석에서 재계산된 것이 아니라 과거 산출물에서 복제**된 것이다(케이스 3건 733행 md5 동일). 웹사이트에서는 **생성 시점과 출처를 명시**해야 한다.

### 3.2 DOCX — `유사중복_검토_<사업명>.docx`

**생성 코드**: `similarity/md2docx.js` (스킬 규정) 또는 `pandoc` (최근 운용)

**현황 — 두 도구가 섞여 있다** **[확인]**

| 생성 도구 | 건수 | 판별 근거 | 서식 |
|---|---|---|---|
| `md2docx.js` | **31** | `word/styles.xml`에 pandoc 전용 스타일 없음, 본문에 `맑은 고딕` | A4 세로, 여백 2cm, 맑은 고딕, 위계별 들여쓰기·크기 지정 |
| `pandoc` | **13** | `FirstParagraph`·`BodyText`·`Compact`·`SourceCode` 스타일 존재, 맑은 고딕 미사용 | pandoc 기본 서식 |

pandoc 생성분 13건: `전북전통시장혹서기환경개선`, `경북식품창업스타트업챌린지`, `경북식품창업스케일업`, `경북식품스타트업투자브릿지`, `경북식품창업글로벌브랜드`, `경상북도_신규사업4건_직접비교`, `부산블록체인허브운영`, `전북스마트제조혁신`, `전북반도체소부장RD`, `전북AI기술활성화`, `부산대학스타트업공동RD`, `부산원전마중물RD`, `2026-053_2026-103_시점별비교`

**`md2docx.js`가 요구하는 입력 형식(하드 계약)** **[확인]**

| 마크다운 | 변환 | 크기/들여쓰기 |
|---|---|---|
| `# ` | 가운데 정렬 제목 | 32, bold |
| `## ` | HEADING_2 | 26, bold, `#1F3864` |
| `□ ` (행 머리) | 1수준 | 21, bold, left 300 |
| ` ○ ` (**앞 공백 1칸**) | 2수준 | 20, left 640 |
| `  - ` (**앞 공백 2칸**) | 3수준 | 19, left 920 |
| `  * ` (**앞 공백 2칸**) | 4수준 | 18, left 1140, `#404040` |
| `- ` (머리글 직후 메타) | 메타 줄 | 18, left 400, `#404040` |
| `\|…\|` | Word 표(머리행 음영 `E7E6E6`, 테두리 `808080`, 숫자열 가운데 정렬) | 16 |
| `` `code` ``, `**bold**` | 기호 제거 후 평문 | — |

> **앞 공백 개수가 위계를 결정한다.** 웹사이트에서 보고서를 저장·재생성할 때 이 공백이 보존되지 않으면 DOCX 위계가 무너진다.

**이식 시 결정 사항**: DOCX 생성기를 `md2docx.js`로 통일할지, pandoc으로 통일할지를 **정해야 한다**. 기존 44건이 섞여 있으므로 어느 쪽을 택하든 **기존 산출물의 서식이 두 종류라는 사실을 DB에 기록**해야 한다.

### 3.3 PNG — `figures/보고그림_<사업명>.png`

**생성 코드**: `similarity/report_figure.py`

```bash
python3 similarity/report_figure.py \
  --xlsx 유사도_산출결과_<사업명>.xlsx \
  --spec figures/figure_spec_<사업명>.json \
  --out  figures/보고그림_<사업명>.png \
  --chrome /opt/pw-browsers/chromium-1243/chrome-linux64/chrome   # ← 기본값이 깨져 있어 명시 필요
```

**처리 흐름** **[확인]**
1. `collect_rows()` — `행기준`이 `"전체"`면 `전체` 시트 상위 `행수`행, 아니면 `내역*` 시트별 1위
2. `build_html()` — Noto Sans KR woff2 6종을 **base64로 HTML에 임베드**, 축 눈금 `축최소`/`축최대`(없으면 자동)
3. `whole = pd.read_excel(xlsx, "전체")`에서 **n·평균·1위 사업명·최댓값을 코드가 직접 계산**(spec에 쓰지 않음)
4. Chromium `--headless=new --force-device-scale-factor=2 --window-size=1680,<세로>` 스크린샷
5. `trim()` — PIL로 아래 여백 제거(`아래여백`, 기본 26px)

**`figure_spec_*.json` 스키마** **[확인]** (42개 파일 전수 집계)

| 키 | 필수 | 형 | 내용 |
|---|---|---|---|
| `머리말` | 42/42 | str | 상단 작은 제목 |
| `헤드라인` | 42/42 | str | 큰 제목 |
| `부제` | 42/42 | str | 2~3문장 요약 |
| `좌측제목` / `우측제목` | 42/42 | str | ①②번 블록 제목 |
| `차트주석` | 42/42 | str | 차트 하단 주석 |
| `자료` | 42/42 | str | 출처 |
| `행주석` | 42/42 | dict | **키 = xlsx `공고이름` 열 값 그대로**, 값 = `{축약, 이름, 설명, 분류}` |
| `유형카드` | 42/42 | list | **정확히 3개**, 각 `{태그, 제목, 본문, 수치}` |
| `시사점` | 42/42 | list | **정확히 3개**, 각 `{제목, 본문}` |
| `비고` | 42/42 | dict | `{제목, 본문}` |
| `라벨폭` / `설명폭` | 42/42 | int | px |
| `분류라벨` | 40/42 | dict | 범례 문구 덮어쓰기 |
| `행수` | 39/42 | int | `행기준="전체"`일 때 행 수(기본 7) |
| `행기준` | 38/42 | str | `"전체"`면 전체 상위 N |
| `축최소` / `축최대` | 32/42 | num | 축 범위 고정 |
| `세로` | 23/42 | int | 창 높이(기본 950 / 렌더 1400) |
| `아래여백` | 0/42 | int | trim 패딩(기본 26) |

**행 분류는 3종뿐** **[확인]** — 다른 값을 쓰면 `KeyError`로 실패

| 분류 | 색 | 기본 범례 |
|---|---|---|
| `중첩` | `#eb6834` (주황) | 대상 중첩 검토 필요 |
| `유사` | `#2a78d6` (파랑) | 대상 유사, 지원수단 상이 |
| `없음` | `#8a8982` (회색) | 겹치는 기존사업 없음 |

### 3.4 파일명 규칙 **[확인]**

```
유사중복_검토_<사업 약칭>.md / .docx
figures/보고그림_<사업 약칭>.png
figures/figure_spec_<사업 약칭>.json
유사도_산출결과_<사업 약칭>.xlsx
new_project_profile_<사업 약칭>.json
```
**`<사업 약칭>`은 Claude가 정하며 규칙이 코드화되어 있지 않다.** 협의번호가 파일명에 들어가지 않는다 → DB에서는 협의번호를 1차 키로 두고 약칭을 별도 열로 관리해야 한다(§4).

---

## 4. 향후 DB에 필요한 데이터 구조 (제안)

> **전제**: 현재 사전협의 DB는 **없다.** 아래는 구축 시 필요한 항목·연결 구조 제안이다. 단, **기존사업 임베딩 저장소**(Supabase `public.biz_embedding`)는 README상 구축되어 있다고 기술되어 있으나 **본 조사 세션에서는 접속 확인이 불가**했다. **[확인필요]**

### 4.1 설계 원칙

**4개 축 입력 텍스트를 1급 저장 대상으로 삼는다.** 유사도는 원자료가 아니라 **축 텍스트에서만** 결정된다. 원문을 보존해도 축 텍스트 작성 규칙이 달라지면 점수가 재현되지 않는다. 반대로 축 텍스트를 바이트 단위로 보존하면 모델·산식이 같은 한 점수가 재현된다.

### 4.2 표 구조 제안

**① `consult`(협의사업 기본정보)**

| 열 | 설명 | 필수 |
|---|---|---|
| `consult_no` | 협의번호(2026-0319). **1차 키** | ● |
| `year` | 협의 연도 | ● |
| `gov_type` | `중앙부처` / `지자체` | ● |
| `dept` / `division` | 신청기관 / 신청부서 | ● |
| `program_name` | 사업명(정책/단위/세부) | ● |
| `short_name` | 산출물 파일명에 쓰인 약칭 | ● |
| `request_type` | 세부사업 신설 / 내역 신설 / 사업내용 변경 / 연례반복 | ● |
| `budget_year`, `budget_amount`, `funding_mix` | '27년 요구예산·재원 구성 | ● |
| `executing_agency` | 수행기관 | ● |
| `legal_basis` | 근거 법령·조례 | ○ |
| `region` | 지자체 사업일 때 시도명(`--region` 값) | ● |
| *담당자 성명·연락처* | **저장하지 않거나 접근 분리.** 현행 운영 규칙상 프로필·보고서에 넣지 않음 | — |

**② `consult_document`(요청서·부속자료)**

`doc_id`, `consult_no`, `doc_type`(요청서/사업기획 자체점검표/유사중복 자체점검표/사업설명서), `filename`, `sha256`, `storage_path`, `extracted_text`, `extractor`(도구명+버전), `extracted_at`
> 원문은 **내부 스토리지**에만 둔다. 체크박스 표식은 추출에서 유실되므로 **"체크 항목은 분석에 반영되지 않음"을 문서 단위로 기록**해야 한다.

**③ `analysis_unit`(전체·기능 단위 + 4개 축 입력 텍스트) — 가장 중요**

| 열 | 설명 | 필수 |
|---|---|---|
| `unit_id` | 1차 키 | ● |
| `consult_no` | ①의 외래키 | ● |
| `unit_name` | 프로필 `units` 키(`전체`, `기능1 …`). **31자 제한** | ● |
| `unit_order` | 시트 순서 | ● |
| `unit_role` | `전체` / `기능` | ● |
| **`purpose_text`** | 사업목적 축 입력 **(완성형, 가공 금지)** | ● |
| **`content_text`** | 지원내용 축 입력 | ● |
| **`target_text`** | 지원대상 축 입력 | ● |
| **`delivery_text`** | 전달체계 축 입력 | ● |
| **`axis_build_path`** | **`profile`(원문 그대로) / `axis_texts`(템플릿 조립)** | ● |
| `split_basis` | 기능 분리 근거(예: 기업지원내역 비목) | ● |
| `authored_by` | `claude` / `human` | ● |
| `profile_json` | 프로필 원본 전체 | ● |

> **`axis_build_path`를 반드시 저장한다.** 기존사업은 `axis_texts()`가 `(정책목적: …)`, `(대상유형: …, 업종: …)`, `주관부처 … → 수행기관 …` 같은 고정 문구를 붙여 조립하지만, 협의사업 프로필은 가공 없이 그대로 인코딩된다. **두 경로의 점수는 같은 척도가 아니다**(§7.3).

**④ `corpus_unit`(기존사업 비교 풀)**

`unit_key`(현 `행`, **전역 유일**), `snapshot_id`, `source_kind`(공고정보/biz_내역/biz_내내역/extra), 4개 축 텍스트, 메타(`단위`·`연도`·`부처`·`기관`·`공고이름`·`세부사업명`·`내역사업명`·`내내역명`·`시행방법`·`규모`·`연계공고`·`대분류`·`중분류`·`대상유형`·`업종`), `axis_build_path`
> `unit_key` 유일성은 **필수**다. `similarity_check.py`가 `행` 값으로 축 텍스트를 역매핑하므로 중복 시 조용히 잘못된 텍스트가 붙는다.

**⑤ `corpus_snapshot`(비교 풀 스냅샷)**

`snapshot_id`, `built_at`, `unit_count`, `source_desc`, `region_filter`, `years`, `build_command`, `checksum`
> 코퍼스가 바뀌면 **등급·p99·평균이 전부 달라진다.** 스냅샷 고정 없이는 과거 분석을 재현할 수 없다.

**⑥ `embedding`**

`unit_key` 또는 `unit_id`, `axis`, `vector`(1024, **L2 정규화 완료**), `model`(`BAAI/bge-m3`), **`model_revision`**, **`max_seq_length`**, `text_md5`, `embedded_at`
> `model_revision`과 `max_seq_length`는 **현재 어디에도 저장되지 않는다. 반드시 추가해야 한다.** `embed_corpus.py`는 `max_seq`를 512로 덮어쓰는데 `similarity_check.py`는 모델 기본값(8192)을 쓴다 — 긴 축 텍스트에서 다른 벡터가 나온다. 산출물에 1,633자 `지원내용_텍스트`가 실재한다. **[확인]**

**⑦ `similarity_score`**

`run_id`, `unit_id`(협의사업 단위), `unit_key`(기존사업 단위), 축별 `sim`·`weighted`·`grade`·`indicator_score`, `total`, `indicator_total`, `rank`, `tie_group`
> `rank`는 **2자리 반올림 후 정렬** 결과임을 기록하고, 동점군을 `tie_group`으로 표시한다.

**⑧ `analysis_run`(실행 이력)**

`run_id`, `consult_no`, `snapshot_id`, `run_at`, `code_commit`, `model`+`model_revision`, `max_seq_length`, `RAW_W` 값, `region`, `top_n`, 라이브러리 버전(python/torch/sentence-transformers/numpy/pandas), `command_line`, `log_path`

**⑨ `deliverable`(결과물 3종 연결)**

`deliverable_id`, `run_id`, `kind`(`docx`/`png`/`xlsx`/`md`/`profile_json`/`figure_spec`), `filename`, `sha256`, `storage_path`, `generated_by`(`md2docx.js` / `pandoc` / `report_figure.py` / `similarity_check.py`), `generator_version`, `generated_at`
> **`generated_by`를 저장해야 한다.** 기존 DOCX 44건이 두 도구로 나뉘어 있다(§3.2).

**⑩ `report_section`(보고서 서술) — 선택이나 권장**

`run_id`, `section`(1~4), `level`(□/○/-/*), `order`, `text`, `authored_by`
> 보고서를 평문 .md로만 두면 웹 조회·검색이 어렵다. 다만 **DOCX 변환은 앞 공백 규칙에 의존**하므로 재조립 시 위계를 정확히 복원해야 한다.

### 4.3 연결 구조

```
consult (협의번호)
  ├─1:N─ consult_document
  ├─1:N─ analysis_unit ──1:N── embedding
  └─1:N─ analysis_run ──┬─1:N─ similarity_score ──N:1── corpus_unit ──N:1── corpus_snapshot
                        ├─1:N─ deliverable
                        └─1:N─ report_section
```

---

## 5. Claude Code와 독립적으로 실행 가능한 기능

아래는 **LLM 없이 서버 코드만으로** 제공할 수 있다. **[확인]**

| 기능 | 근거 코드 | 비고 |
|---|---|---|
| **기존 산출물 조회·다운로드** | — | DB·스토리지만 있으면 됨. **가장 먼저 제공 가능** |
| 협의번호·부처·연도·사업명 검색, 후보 표 열람, 축별 점수·등급 조회 | `similarity_io.py` | |
| 원문 텍스트 추출(.hwp/.hwpx/.pdf) | `extract_text.py` | olefile만 필요. 외부 전송 없음 |
| **4개 축 텍스트 임베딩** | `similarity_check.py` L251–253 / `similarity_query.py` `embed_local` | **로컬 bge-m3**. 외부 전송 없음 |
| **코사인·가중합·순위 산출** | `similarity_check.py` L292–306 | 전수 계산 |
| 5단계 등급·지표(안) 환산점수 | `grade()` L189–191 | **코퍼스 전체 필요** |
| 지역 필터 | L270–282 | |
| 벡터 top-k 검색 | `similarity_query.py` + RPC `match_biz` | **등급·분포 산출 불가**(§7.4) |
| XLSX 생성 | `similarity_check.py` L316–327 | |
| **PNG 렌더링** | `report_figure.py` | 입력 spec만 주어지면 완전 자동. 글꼴 임베드 |
| **DOCX 변환** | `md2docx.js` 또는 pandoc | .md만 주어지면 완전 자동 |
| 수치 정합 검증 | 케이스별 `verify.py` | 공통 라이브러리로 일반화 필요 |
| 코퍼스 임베딩 구축·적재 | `embed_corpus.py`, `load_embeddings.py` | 반기 1회 배치 |

**→ "기존 분석 결과 조회·다운로드"와 "저장된 프로필로 유사도 재산출 + XLSX·PNG·DOCX 재생성"은 LLM 없이 전부 가능하다.**

---

## 6. 별도 AI 실행환경이 필요한 기능

아래는 **코드에 구현이 없고 Claude가 수행한다.** 웹사이트가 "신규 분석"을 제공하려면 LLM 실행환경이 필요하다. **[확인]**

| # | 기능 | 현재 수행 | 대체 불가 이유 |
|---|---|---|---|
| **1** | **4개 축 프로필 작성** | Claude | 요청서 원문 → 축별 150~400자 서술. 코드 없음. **점수를 직접 좌우하는 입력** |
| **2** | **기능 단위 분리** | Claude | 요청서의 기업지원 비목을 보고 `전체`/`기능N` 구성을 정함. 규칙은 산문(`profile_guide.md`)으로만 존재 |
| **3** | **보고서 본문 작성** | Claude | 분포 해석, 후보 유형 묶음, 자체점검표 대조, 유의사항. `report_template.md`가 틀만 제공 |
| **4** | **그림 명세 문장 작성** | Claude | 헤드라인·부제·행 설명·유형카드 3개·시사점 3개·비고. spec의 **모든 텍스트** |
| **5** | 분포 통계 산출·서술 | Claude | 평균·σ·p99·평균+2σ를 **코드가 계산하지 않는다**. xlsx를 읽어 Claude가 계산 |
| **6** | 검증 스크립트 작성 | Claude | 케이스마다 `verify.py`를 새로 작성 |
| **7** | 사업 약칭 결정 | Claude | 파일명 규칙이 코드화되어 있지 않음 |

### 6.1 기관 내부 운영 전제에서의 선택지

> 기관 승인 내부 서버·접근권한을 전제로 하면, **원문·프로필·보고서가 외부로 나가는 경로를 차단**해야 한다.

| 방식 | 외부 전송 | 비고 |
|---|---|---|
| (A) **분석은 사람이 수행, 웹은 저장·조회만** | 없음 | 가장 안전. 현재 운용과 동일. **1단계 권장** |
| (B) 내부망 LLM(온프레미스) | 없음 | ①~⑦ 전부 자동화 가능. 모델 품질 검증 필요 **[확인필요]** |
| (C) 기관 승인 외부 LLM API | **있음** | 선례 존재: `review_draft/generator.py`가 `anthropic` SDK로 검토의견서 초안을 생성(model·max_tokens·effort 지정). **승인 필요** |
| (D) 하이브리드 — ②③④만 사람, 나머지 자동 | 없음 | 현실적. 웹에서 프로필·보고서·spec을 **편집·저장**하고 나머지를 자동 실행 |

### 6.2 임베딩 수단 선택 — **주의** **[확인]**

`review_draft/similarity_query.py`는 임베딩 백엔드가 둘이다.

| 백엔드 | 경로 | 외부 전송 | 비고 |
|---|---|---|---|
| `embed_local` (L59–63) | 로컬 sentence-transformers | **없음** | `similarity_check.py`와 동일 방식 |
| `embed_hf` (L48–56) | Hugging Face Inference API | **있음 — 축 텍스트가 외부로 나감** | 기관 내부자료 정책상 부적합 |

또한 `embed_hf`는 응답을 `_pool()`로 직접 CLS 풀링한다(L37–45). **이것이 sentence-transformers의 풀링과 완전히 같은 벡터를 내는지 확인되지 않았다.** **[확인필요]** → **내부 서버에서는 `--embed local`로 고정할 것을 권고한다.**

---

## 7. 동일 방법론 적용 및 검증 조건

### 7.1 변경하지 않아야 하는 것 **[확인]**

| 구성요소 | 값 | 위치 |
|---|---|---|
| 분석축 | 사업목적·지원내용·지원대상·전달체계 (순서 포함) | `similarity_check.py` L32 |
| 원 가중치 | 20 / 30 / 30 / 15 | L33 |
| 정규화 가중치 | 21.0526…/31.5789…/31.5789…/15.7894… (합 100) | L34 |
| 등급 배점비·등급명·z 경계 | `GRADE_RATIO`, `GRADE_NAME`, `Z_CUTS=[0,1,2,3]` | L36–43 |
| 지원방식 키워드 28쌍 | `DELIVERY_KW` | L45–52 |
| 기존사업 축 조립 | `axis_texts()`, `delivery_text()` | L165–186 |
| 모델·정규화·배치 | bge-m3, CPU, `normalize_embeddings=True`, batch 16 | L251–253 |
| 종합 산식 | $\sum W_{ax}\cos_{ax}$ (추가항·보정항 없음) | L301 |
| 공고 매핑 3단계·임계 0.6 | `biz_units.py` L281–294 | |
| 내내역 상속 규칙 | 목적·대상·전달체계는 부모 내역에서 상속 | `biz_units.py` L241–252 |
| 그림 3색 | `#eb6834` / `#2a78d6` / `#8a8982` | `report_figure.py` L23–27 |
| 보고서 4개 장 구조·문체 | `report_template.md` | |

### 7.2 반드시 고정·기록해야 하는 실행조건

| 항목 | 현재 | 조치 |
|---|---|---|
| **모델 revision** | 미고정 | `revision` 인자 추가 후 기록. **산식 아닌 환경 고정이므로 방법론 변경 아님** |
| **`max_seq_length`** | `similarity_check.py` 무제한 / `embed_corpus.py` 512 | **하나로 결정하고 기록** |
| 라이브러리 버전 | `>=` 하한만 | `==` 핀 고정 |
| Chromium 경로·버전 | 기본값이 현재 환경과 불일치 | `--chrome` 명시 + 버전 기록 |
| DOCX 생성기 | md2docx.js / pandoc 혼재 | 하나로 결정, 기존 44건의 생성기를 DB에 기록 |
| 코퍼스 스냅샷 | 미기록·소실 | `snapshot_id`로 고정 |
| 정렬 동점 | 불안정 정렬 | `kind="stable"` + 2차 키(`unit_key`). **점수 불변이므로 방법론 변경 아님** |

### 7.3 **척도 혼용 금지** **[확인]**

| 조합 | 사례 | 설명 |
|---|---|---|
| **P × T** | 기존 개별 분석 40건 | 협의사업 프로필(원문) × 기존사업(템플릿 조립) |
| **P × P** | 직접비교 6건 | 협의사업끼리 |

**두 조합의 점수는 같은 척도가 아니다.** 축 텍스트 서식이 다르므로 절대값 수준이 다르다. 한 표에 섞거나 "협의사업 간 70점 > 기존사업 대비 65점" 식으로 비교해서는 안 된다. **웹사이트에서는 두 결과를 화면·API·DB에서 분리하고 `axis_build_path`로 구분 표시해야 한다.**

### 7.4 **벡터 검색 경로의 기능 한계** **[확인]**

`match_biz` RPC는 상위 k건만 반환한다. 따라서 이 경로만으로는 다음을 **산출할 수 없다**.

| 산출물 요소 | 전수 계산 | match_biz |
|---|---|---|
| 상위 k 후보·축별 유사도·종합 유사도 | ○ | ○ |
| **코퍼스 평균·표준편차·최댓값·최솟값** | ○ | **×** |
| **p99 기준선·평균+2σ 초과 건수** | ○ | **×** |
| **5단계 등급·지표(안) 환산점수** | ○ | **×** (z-점수에 전체 분포 필요) |
| **전체 순위표 xlsx** | ○ | **×** |
| 지역별 평균 비교 | ○ | **×** |

**→ 보고서 §2 "(분포)" 항목과 xlsx 등급 열을 유지하려면 전수 계산 경로가 반드시 필요하다.** 벡터 검색은 "빠른 후보 조회"용으로만 쓰고, 정식 산출물 생성은 전수 경로로 하는 **이중 구조**를 권고한다.

### 7.5 산식 중복 선언 — 드리프트 위험 **[확인]**

$W$가 현재 **세 곳**에 있다.

| 위치 | 형태 |
|---|---|
| `similarity/similarity_check.py` L33–34 | **원본** |
| `similarity/direct_compare.py` L8 | `from similarity_check import …` — **정상(import)** |
| `review_draft/similarity_query.py` L18–21 | **literal 재선언** |
| Supabase RPC `match_biz` | 파라미터로 전달받아 **SQL 내부에서 가중합** (정의가 저장소에 없음) **[확인필요]** |

**→ `similarity_query.py`는 `similarity_check`에서 import하도록 바꾸는 것이 안전하다**(값은 동일하므로 산식 변경 아님). SQL 함수 정의는 추출해 저장소에 보존해야 한다.

### 7.6 검증 절차 — 테스트 A~F

| 테스트 | 내용 | 합격 기준 | 현재 실측 |
|---|---|---|---|
| **A. 산식 불변** | 산출물의 4자리 축 유사도로 $\sum W\cos$ 역산 | 최대 오차 **≤ 0.01** | 기존 xlsx 1,222행 최대 0.0079 / 직접비교 57행 전부 통과 **[확인]** |
| **B. 대칭성** | $\mathbf{S}$ vs $\mathbf{S}^{\top}$ | **= 0** | 과거 4건 비교에서 0 실측 **[확인]** |
| **C. 역검증** | 기존 xlsx의 `*_텍스트`를 재인코딩해 기존 종합유사도 재현 | 차이 **≤ 0.05** | 미실시(모델 없음) **[확인필요]** |
| **D. 결정성** | 같은 입력 2회 실행 | 전 쌍 완전 일치 | 미실시 |
| **E. 순위 안정성** | 코퍼스 행 순서를 섞어 재실행 | 점수·순위 불변 | **현재 코드로는 불합격 예상**(동점 60%) **[확인]** |
| **F. 척도 분리** | P×P와 P×T가 섞이지 않았는지 | 산출물·화면에서 분리 | — |

**추가 — 결과물 3종 동일성 테스트**

| 테스트 | 내용 | 합격 기준 |
|---|---|---|
| **G. XLSX 구조** | 시트 구성·42열 순서·반올림 규칙 | 기존 산출물과 열 단위 일치 |
| **H. PNG 재현** | 같은 xlsx+spec으로 재렌더 | 픽셀 동일(동일 Chromium·글꼴). 다르면 **버전 차이**로 기록 |
| **I. DOCX 서식** | 같은 .md를 변환 | 선택한 생성기 기준으로 위계·표가 기존과 동일 |

**차이 발생 시 원인 구분** **[확인]**

| 증상 | 원인 |
|---|---|
| 전반적으로 조금씩 다름 | 모델 revision 변경 |
| 긴 텍스트 단위만 다름 | `max_seq_length` 차이 |
| 소수점 끝자리만 다름 | 라이브러리·BLAS 버전 |
| 점수 같은데 순위가 다름 | 동점 + 불안정 정렬 |
| 특정 단위만 사라짐/추가됨 | 비교 풀 구성(`--region`, 목적 공란 제외, 중복 제거) |
| 축 하나만 크게 다름 | `axis_build_path` 불일치 |
| 전체가 크게 다름 | 프로필 축 서술 변경 |

---

## 8. 향후 웹사이트 개발 시 활용할 기존 자산

### 8.1 그대로 재사용 (수정 불필요)

| 자산 | 웹사이트에서의 역할 |
|---|---|
| `similarity_check.py` 상수·함수 | **산식 단일 출처.** `from similarity_check import AXES, RAW_W, W, axis_texts, delivery_text, grade` |
| `biz_units.py` | 코퍼스 구축 배치 |
| `report_figure.py` | PNG 생성 서비스(`--chrome` 경로만 환경변수화) |
| `md2docx.js` | DOCX 생성 서비스(Node 런타임) |
| `extract_text.py` | 업로드 문서 파싱 |
| `embed_corpus.py` / `load_embeddings.py` | 코퍼스 임베딩 배치 |
| `similarity_io.py` | 산출물 조회 계층 |
| `assets/fonts/*.woff2` | PNG 글꼴(서버 글꼴 설치 불필요) |
| `biz_export.sql` | 원천 추출 질의 |

### 8.2 설계 참고로 활용

| 자산 | 활용 |
|---|---|
| `similarity_query.py` | **웹 API 설계의 기성 참조 구현.** top-k 검색 → `top10.json` 포맷 |
| README "신규 사업마다 유사도 검색하기" | 배치/온라인 분리 운영 모델 |
| `review_draft/generator.py` | **프로그램적 LLM 호출 선례**(anthropic SDK, model·max_tokens·effort, `max_tokens` 초과 시 오류 처리) |
| `review_draft/cli.py` | CLI 옵션 설계(`--similarity`, `--similarity-unit`, `--consult-no` 등) |
| `plugins/sme-review-drafter/` | 플러그인 배포 구조 |

### 8.3 **규격 문서로 활용 — 가장 가치 있는 자산**

| 문서 | 웹사이트에서의 역할 |
|---|---|
| **`references/profile_guide.md`** | 프로필 **입력 폼의 필드 설명·검증 규칙**(축별 넣을 것/뺄 것, 150~400자, 기존사업명 금지) |
| **`references/report_template.md`** | 보고서 **편집기의 구조 템플릿 + 저장 전 체크리스트 7항목** |
| `references/methodology.md` | 산출 기준 도움말 |
| `references/data_sources.md` | 코퍼스 갱신 운영 매뉴얼 |
| `figure_spec_*.json` 42건 | 그림 명세 **입력 폼 스키마와 예시** |
| `유사중복_검토_*.md` 44건 | 보고서 **서술 품질 기준·예시** |
| 케이스별 `verify.py` 4건 | 검증 라이브러리의 **원형** |

### 8.4 기준자료(골든 세트)

커밋된 산출물 40~44건은 **이식 검증의 정답지**다. 웹사이트가 같은 프로필·같은 코퍼스로 같은 값을 내는지 대조할 수 있다. 특히 **xlsx 40건에 4개 축 입력 텍스트가 전부 보존**되어 있어, 소실된 코퍼스를 복원하는 원천이기도 하다(§9).

---

## 9. 추가 확보·확인이 필요한 사항

### 9.1 확보 필요

| # | 항목 | 상태 | 조치 |
|---|---|---|---|
| 1 | **코퍼스 `corpus_3631_v2.csv`** | 소실 | 커밋된 xlsx 40건을 `행` 기준 합집합해 복원. **xlsx 1건에는 `--region` 적용 후 단위만 있으므로 여러 케이스를 합쳐야 전체 3,631단위가 됨** |
| 2 | **메타표 `v2030_전체_메타.xlsx`** | 소실 | 같은 방법 |
| 3 | **`finalize.py`** | 소실·미문서화 | 재작성. 조인 키는 `행`의 숫자 접미사 |
| 4 | **`match_biz`·`upsert_biz_embedding`·`biz_embedding_stats` SQL** | 저장소에 없음 | `pg_get_functiondef`로 추출해 저장소에 보존 |
| 5 | **bge-m3 모델 + revision** | 캐시 없음, 미고정 | 내부 미러에 고정 사본 보관 |
| 6 | **torch·sentence-transformers·olefile** | 미설치 | 핀 고정 설치 |
| 7 | **npm `docx`** | 미설치 | `md2docx.js`를 쓸 경우 필요 |
| 8 | 원문 `.hwp/.hwpx` 아카이브 | 미커밋 | 내부 스토리지에 협의번호 기준 보관 |
| 9 | 과거 실행 로그 | 없음 | 이후 `analysis_run`에 기록 |

### 9.2 확인 필요 (임의 판단하지 않음) **[확인필요]**

| # | 항목 | 왜 중요한가 |
|---|---|---|
| 1 | **Supabase `biz_embedding` 현재 적재 상태·스키마** | 본 세션에 DB 연결 없음. 적재 건수·모델·적재 시점 미상 |
| 2 | **`match_biz`의 가중합 구현이 파이썬과 동일한지** | 가중치를 파라미터로 받지만 내부 식이 같은지 미확인 |
| 3 | **`embed_hf`의 CLS 풀링이 sentence-transformers와 동일 벡터를 내는지** | 다르면 웹 검색 결과가 전수 계산과 어긋남 |
| 4 | **`embed_corpus.py --max-seq 512`가 실제 적재에 쓰였는지** | 쓰였다면 DB 벡터와 `similarity_check.py` 벡터가 다름 |
| 5 | `corpus_3631_v2.csv`의 원 생성 절차 | `--level naeyeok` 산출물 정리로 **보이나** 확증 불가 |
| 6 | DOCX 생성기 통일 방침 | 기존 44건이 두 종류 |
| 7 | 담당자 개인정보의 DB 저장 범위·접근권한 | 현 운영은 산출물에서 제외 |
| 8 | 2024·2025년 협의사업 원문 보유 여부 | 확대 단계의 전제 |
| 9 | 내부망 LLM 가용성 또는 외부 API 승인 여부 | §6의 방식 선택을 좌우 |
| 10 | 기관 내부 서버의 CPU·메모리·디스크 | 전수 임베딩 CPU 4코어 기준 3,631단위 × 4축 ≈ 1시간 |

---

## 10. 단계적 구축 순서

> 원칙: **먼저 보존, 다음 조회, 그 다음 자동화.** 각 단계는 앞 단계가 검증을 통과해야 넘어간다.

### 0단계 — 자산 보존 (선행, LLM 불필요)
1. 커밋된 xlsx 40건에서 **코퍼스·메타 복원** → `corpus_snapshot`으로 고정
2. `finalize.py` 재작성·커밋
3. Supabase RPC 3종 SQL 추출·보존
4. 라이브러리 `==` 핀 고정, bge-m3 **revision 고정**, 내부 미러 확보
5. 기존 산출물 44/42/40건을 **골든 세트**로 등록(생성 도구·생성 시점 포함)
- **완료 기준**: 테스트 A 통과, 코퍼스 단위 수가 과거 분석과 일치

### 1단계 — 2026년 중앙부처 사전협의 DB 구축 (조회 전용)
1. §4 표 ①~⑨ 생성
2. 2026년 중앙부처 협의건의 **프로필·축 텍스트·점수·산출물 3종 적재**
3. 웹: **검색·열람·다운로드만** 제공(신규 분석 없음)
- **완료 기준**: 임의 10건을 골라 화면 수치와 원본 xlsx가 일치

### 2단계 — 저장된 입력으로 재산출 (LLM 불필요)
1. 내부 서버에 전수 계산 엔진 배치(`similarity_check.py` 재사용)
2. 저장된 프로필 + 고정 스냅샷으로 **재산출 → XLSX·PNG·DOCX 재생성**
3. 골든 세트와 대조
- **완료 기준**: 테스트 A·C·D·G·H·I 통과. 불일치는 §7.6 표로 원인 분류

### 3단계 — 협의사업 간 유사도 (P×P, LLM 불필요)
1. `direct_compare.py` 방식으로 2026년 중앙부처 협의사업 **전수 쌍** 산출
2. 대칭이므로 $M(M-1)/2$ 쌍(기능 단위 포함)
3. **P×T 결과와 분리 저장·분리 표시**
4. 등급·환산점수는 **모집단을 명시하거나 산출하지 않음**
- **완료 기준**: 테스트 B·F 통과

### 4단계 — 신규 분석 자동화 (LLM 필요)
1. §6.1에서 방식 결정(A~D)
2. 최소 구성: 웹에서 **프로필·보고서·그림 명세를 사람이 편집·저장**하고 나머지는 자동(방식 D)
3. 입력 폼 검증은 `profile_guide.md`, 저장 전 점검은 `report_template.md` 체크리스트 7항목을 그대로 사용
- **완료 기준**: 사람이 만든 기존 산출물과 품질·형식이 같은 결과가 나옴

### 5단계 — 2024~2026년 전체 확대
1. 연도별 원문 확보 → 추출 → 프로필 작성(가장 큰 비용)
2. 연도별 코퍼스 스냅샷 분리 보관
3. **연도 간 점수를 직접 비교하지 않는다**(코퍼스가 다르면 등급·분포가 다름). 비교가 필요하면 **같은 스냅샷으로 재산출**
- **완료 기준**: 연도별 스냅샷이 고정되고, 교차 비교 시 재산출 경로가 동작

### 단계별 LLM 필요 여부

| 단계 | LLM | 외부 전송 |
|---|---|---|
| 0 자산 보존 | 불필요 | 모델 다운로드만 |
| 1 DB·조회 | 불필요 | 없음 |
| 2 재산출 | 불필요 | 없음 |
| 3 사업 간 비교 | 불필요 | 없음 |
| **4 신규 분석** | **필요** | 방식에 따라 다름(§6.1) |
| 5 확대 | 4단계와 동일 | 동일 |

---

## 부록 A. 본 조사에서 새로 확인한 사항 (2026-11-23)

| 항목 | 결과 |
|---|---|
| DOCX 생성기 분포 | **md2docx.js 31건 / pandoc 13건** (styles.xml의 pandoc 전용 스타일·맑은 고딕 사용 여부로 판별) |
| figure_spec 스키마 | 42개 전수 집계. 필수 13키, 선택 7키. **유형카드 정확히 3개**(태그·제목·본문·수치), **시사점 3개**(제목·본문), 비고 1개(제목·본문), 행주석 319건(이름·설명·분류 필수, 축약 308건) |
| 그림 행 분류 | `중첩`/`유사`/`없음` 3종만 유효 |
| Chromium 기본 경로 | `report_figure.py` L220 = `chromium-1194/chrome-linux/chrome` ↔ 실제 `chromium-1243/chrome-linux64/chrome` → **기본값 깨짐** |
| 벡터 검색 경로 | `embed_corpus.py` → `load_embeddings.py` → `biz_embedding` → `match_biz` → `similarity_query.py` **구축되어 있음**(README 문서화) |
| `similarity_query.py` | `W`를 import하지 않고 **재선언**(L18–21). 임베딩 백엔드 2종(로컬/HF API) |
| `match_biz` | 가중합이 **SQL 내부**. 정의가 저장소에 없음 |
| top-k 검색의 한계 | 분포·등급·환산점수 산출 불가 |
| 프로그램적 LLM 호출 선례 | `review_draft/generator.py` (anthropic SDK) |
| 글꼴 | woff2 6종 저장소 보유 → PNG 재현에 서버 글꼴 불필요 |
| 현재 런타임 | Node 22.23.5 / npm 10.9.9 / pandoc 3.1.3 / Pillow 12.3.0 **있음**, torch·ST·olefile·npm docx **없음** |

## 부록 B. 즉시 착수 가능한 일 (승인 필요, 본 조사에서는 미실행)

1. 커밋된 xlsx 40건에서 **코퍼스·메타 복원** — 가장 시급. 지금 복원하지 않으면 과거 분석의 비교 풀을 영구히 잃는다
2. `finalize.py` 재작성·커밋
3. Supabase RPC 3종 SQL 추출·보존
4. `requirements.txt`를 `==` 핀으로 전환, bge-m3 revision 고정 방안 수립
5. `similarity_query.py`가 `similarity_check`의 `W`를 import하도록 정비(값 동일, 산식 변경 아님)
6. `report_figure.py`의 Chromium 경로를 환경변수로 받도록 정비(렌더링 결과 불변)
7. DOCX 생성기 통일 방침 결정 및 기존 44건의 생성기 이력 기록
8. 정렬에 `kind="stable"` + 2차 키 적용 검토(점수 불변, 순위 재현성만 확보)

---

*본 문서는 읽기 전용 조사 결과다. DB 구축·웹사이트 개발·코드 수정·분석 재실행을 하지 않았고 기존 파일을 변경하지 않았다. 확인하지 못한 사항은 §9.2에 그대로 남겨 두었으며 추정으로 채우지 않았다.*
