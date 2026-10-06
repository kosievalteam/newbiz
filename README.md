# review-draft — 사전협의 검토의견서 초안 자동 생성

중소기업지원사업 **사전협의 요청서**(.hwp/.hwpx/.pdf)를 읽어, 정책평가팀이 회람하는
**검토의견서** 초안(.hwpx/.md/.json, 선택 .docx)을 자동으로 채워 주는 명령행 도구입니다.

- 입력: 별지 1 사전협의 요청서 + 사업기획 자체점검표 + 유사중복 자체점검표 (+ 사업설명서)
- 출력: 샘플 검토의견서와 동일한 지면 구성
  1. 협의신청사업 및 검토의견 개요 (개요표 · 추가정보표 · 검토의견 요약표 · 유사중복검토 사업표)
  2. 검토의견 — 1. 종합의견 (○ 사업 타당성 / ○ 사업 적합성 + 사업내용 박스 ⇩ 점검 박스 / ○ 유사‧중복성), 2. 개선의견
  3. 〈사업간 비교표〉
  4. (선택) 참고1. 협의요청서 원문
- 생성 엔진: Claude API (기본 `claude-opus-5-5`, structured outputs 로 스키마 고정)
- 문체·위계·판단어휘는 패키지에 내장된 **익명화된 실제 검토의견서 예시 6건**(`review_draft/prompts/exemplars/`)과
  작성 규칙(`review_draft/prompts/system.md`)을 few-shot 으로 투입해 맞춥니다.

> 생성물은 **초안**입니다. 기존 유사사업의 예산·지원규모 등 모델이 기억에 의존해 쓴 수치는 `[확인 필요]` 로 표시되고,
> 검토자가 확인할 사항이 `reviewer_notes` 와 docx 마지막 장 **[검토자 확인 메모]** 에 정리됩니다. 발송 전 반드시 확인하세요.

## 작업 흐름 (4단계)

| 단계 | 할 일 | 명령 |
|---|---|---|
| ① 자료 검토 | 협의요청서·사업설명서 등 참고자료 업로드·추출·파싱 | `review-draft parse 요청서.hwpx`, `review-draft extract 설명서.hwpx` |
| ② 유사도 검사 | 신규사업 4개 축 서술(프로필 JSON) ↔ Supabase 에 적재된 기존사업 임베딩(내역·내내역 단위, bge-m3) 벡터 검색, **상위 10개 후보 제시** | `review-draft similar 프로필.json` (또는 기존 산출물 `review-draft similar-top 파일.xlsx`) |
| ③ 유사·중복성 검토 | **상위 3개** 후보를 비교 대상으로 사업목적·대상·내용·방식 대조, 예산·규모는 예산서·공고문(Supabase `public.biz`)으로 확인 | (검토·작성) |
| ④ 초안 작성 | 검토의견 JSON → 정합성 점검 → .hwpx/.md(+.docx) (〈참고〉 유사도 분석 결과 표 포함) | `review-draft draft 요청서.hwpx --context 설명서.hwpx --similarity 산출물.xlsx` 또는 JSON 작성 후 `check`·`render --similarity` |

## 설치

```bash
pip install -e .            # 기본 (hwp/hwpx)
pip install -e ".[pdf,dev]" # PDF 입력 + 테스트
export ANTHROPIC_API_KEY=sk-ant-...
```

Python 3.10 이상. HWP 추출은 `olefile` 만으로 동작하며 한컴오피스·hwp5proc 설치가 필요 없습니다.

## 사용법

```bash
# 1) 요청서 → 검토의견서 초안 (output/ 에 .json .md .hwpx 생성, --docx 를 붙이면 .docx 도)
review-draft draft 요청서.hwp --consult-no 2026-190 --reviewer "홍길동 선임연구원"

# 기존 유사사업 공고문 등 참고자료를 함께 넣으면 비교표·유사중복 판단의 정확도가 올라갑니다
review-draft draft 요청서.hwp --context 공고_민관협력OI.txt --context 공고_디딤돌.pdf --with-appendix

# 2) JSON 을 손으로 고친 뒤 다시 출력
review-draft render output/요청서.json --name 요청서_v2

# 3) 추출·파싱 결과만 확인 (모델 호출 없음)
review-draft extract 요청서.hwp
review-draft parse 요청서.hwp

# 4) 기존 검토의견서를 작성 예시로 추가 (개인정보 자동 마스킹)
review-draft exemplar 2026-1xx_검토의견서.hwp -o my_exemplars/
review-draft draft 요청서.hwp --exemplar-dir my_exemplars/
```

주요 옵션

| 옵션 | 설명 |
|---|---|
| `--consult-no`, `--reviewer` | 개요표의 협의번호·검토자 |
| `--context FILE` | 참고자료 (여러 번 지정 가능) |
| `--exemplar-dir DIR` | 내장 예시 대신 사용할 예시 폴더 |
| `--model`, `--effort`, `--max-tokens` | 모델·추론 강도(기본 high)·출력 상한 |
| `--no-fallback` | 서버측 refusal fallback 끄기 |
| `--with-appendix` | docx 끝에 요청서 원문 첨부 |

환경변수 `REVIEW_DRAFT_MODEL` 로 기본 모델을 바꿀 수 있습니다.

## 동작 원리

```
요청서.hwp ─▶ hwp.py (텍스트 추출) ─▶ request_parser.py (항목별 구간 분리)
          ─▶ generator.py (작성 규칙 + 예시 6건 + 요청서 → Claude, JSON 스키마 강제)
          ─▶ schema.py (ReviewOpinion 검증) ─▶ render_hwpx.py / render_md.py (/ render_docx.py)
```

- `request_parser.py` 는 별지 1 의 라벨(신청기관·사업명·사업개요…)과 자체점검표의 두 줄 라벨(추진/근거, 지원/규모…)을
  앵커로 구간을 나눕니다. 체크박스 상태는 HWP 추출 과정에서 유실될 수 있어 선택지 목록은 그대로 두고 서술 내용만 근거로 삼도록
  프롬프트에서 지시합니다.
- `schema.py` 의 `ReviewOpinion` 이 생성·렌더링의 단일 스키마입니다. 항목을 추가하려면 이 모델과 두 렌더러만 고치면 됩니다.
- 예시 블록에는 prompt caching 을 적용해 반복 호출 비용을 줄입니다.

## 검토의견서 작성 규칙 (요약)

- ○ 헤드라인: 「(평가축) 평가 영역 + 결론, “원안 동의” / “권고안 제시”」. 헤드라인의 영역과 dash 라벨 1:1 대응.
- dash: 「(라벨) 사실 압축 + 판단어휘」. 박스의 사실을 반복하지 않고 검토자의 판단으로 끝맺음 (…인정 / …적절 / …필요).
- \* 각주: 법령 조문·상위정책명·기존사업 지원내용 등 구체 정보.
- 사업 적합성 아래 「사업내용 박스 ⇩ 사업내용 점검 박스」.
- 권고로 판단한 항목은 모두 「2. 개선의견」에 1:1 로 나타나야 함.
- 표기: ’27년, 백만원, 「법령명」 조문, ’25.10. 정부조직 개편 반영 부처명.

전체 규칙은 `review_draft/prompts/system.md` 참고.

## 테스트

```bash
pytest -q
```

API 호출 없이 추출·파싱·스키마·렌더링·요청 구성을 검증합니다 (가짜 클라이언트 사용).

## 저장소에 올리지 않는 것

`samples/`, `output/`, `*.hwp`, `*.docx` 는 `.gitignore` 로 제외됩니다. 원본 검토의견서·요청서에는 담당자 성명·연락처가 포함되므로
예시로 추가할 때는 반드시 `review-draft exemplar` 를 거쳐 마스킹된 결과를 확인하세요.

## 알려진 제약

- 중앙부처용 **검토결과서**(협의번호·검토사항·개선사항 표 형식, 예: 2026-168)는 지면 구성이 달라 아직 지원하지 않습니다.
  JSON 은 동일하게 생성되므로 `render_docx.py` 에 레이아웃을 추가하면 됩니다.
- 암호화된 HWP, HWP 3.x 이하는 읽지 못합니다.
- 기존 유사사업 정보는 모델 지식에 의존합니다. `--context` 로 최신 공고 자료를 넣는 것을 권장합니다.

## 다른 사람과 공유하기

세 가지 방법이 있으며, 대상에 따라 고르면 됩니다.

| 대상 | 방법 | 만드는 명령 |
|---|---|---|
| Claude 를 쓰는 동료 (코딩 불필요) | **Claude 스킬** `sme-review-drafter.skill` 을 전달. 받은 사람이 Claude 에서 스킬을 저장하면 요청서 파일을 올리고 "검토의견서 초안 작성해 줘" 라고만 하면 됨. API 키 없이 대화 중인 Claude 가 직접 작성·점검·렌더링 | `python scripts/build_skill.py` → `dist/sme-review-drafter.skill` |
| Python 을 쓰는 동료 | **설치 패키지(wheel)** 전달 후 `pip install review_draft-0.1.0-py3-none-any.whl`, `ANTHROPIC_API_KEY` 설정, `review-draft draft 요청서.hwpx` | `pip wheel . -w dist --no-deps` |
| 함께 개발할 사람 | **GitHub 저장소** 접근 권한 부여 (`git clone` 후 `pip install -e ".[dev]"`) | — |

스킬 패키지에는 패키지 소스, 작성 규칙, 익명화된 예시 6건, 정합성 점검기, JSON 템플릿이 모두 들어 있습니다.
예시에 새 검토의견서를 추가하려면 `review-draft exemplar 파일.hwp -o review_draft/prompts/exemplars/` 로 변환한 뒤 다시 빌드합니다.
## 팀 배포: Claude Code 플러그인

이 저장소는 그 자체가 플러그인 마켓플레이스(`.claude-plugin/marketplace.json`, 이름 `kosieval-tools`)이며,
`plugins/sme-review-drafter/` 가 플러그인입니다(스킬 + `/sme-review-drafter:review-draft` 명령).

팀원 설치 (Claude Code 터미널에서). 준비물·설정값·문제 해결을 포함한 안내문은 Notion 「검토의견서 초안 작성 플러그인 설치 안내」
(https://app.notion.com/p/3f1378aa37898175a0d7cdec60723027)에 있습니다.

```bash
claude plugin marketplace add kosievalteam/newbiz          # 기본 브랜치 기준. 특정 브랜치/태그는 kosievalteam/newbiz@<ref>
claude plugin install sme-review-drafter@kosieval-tools \
  --config supabase_url=https://<ref>.supabase.co --config supabase_anon_key=<anon 키>   # 설정값은 팀 Notion 안내문 참고
pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install sentence-transformers   # 유사도 검색용 로컬 임베딩(한 번만)
# 사용: 요청서를 올리고 "검토의견서 초안 작성해 줘" 또는
/sme-review-drafter:review-draft 요청서.hwpx 사업설명서.hwpx --similarity 유사도_산출결과.xlsx --consult-no 2026-190
```

저장소 접근 권한이 있어야 하며(비공개 저장소), 설치 후 `claude plugin update` 로 갱신합니다.
배포 전 점검: `python scripts/build_skill.py` (스킬 → `plugins/…/skills/` 동기화) → `claude plugin validate .` → 커밋·푸시.
로컬 테스트는 `claude --plugin-dir plugins/sme-review-drafter`.

## 신규 사업마다 유사도 검색하기 (Supabase 벡터 검색)

팀원이 torch·모델 없이도 신규 사업마다 유사도 검사를 할 수 있도록, 기존사업 임베딩을 Supabase(pgvector) 에 한 번 적재해 두고
검색 때는 신규 사업의 4개 축 서술만 임베딩합니다.

```
[분석 담당자, 반기 1회]  embed_corpus.py (bge-m3, 로컬) ─▶ load_embeddings.py ─▶ Supabase public.biz_embedding
[팀원, 사업마다]        프로필 JSON ─▶ review-draft similar ─▶ (로컬 sentence-transformers 로 임베딩) ─▶ RPC match_biz ─▶ top10.json
```

팀원 환경변수(플러그인 설정에서 입력): `SUPABASE_URL`, `SUPABASE_ANON_KEY`(검색 RPC 전용, 코퍼스 직접 조회 불가).
임베딩은 로컬 `sentence-transformers`(bge-m3, 첫 실행 때 약 2.2GB 다운로드)로 하며, `--embed hf` + `HF_TOKEN` 으로 Hugging Face Inference API 를 쓸 수도 있다(미검증).
연결·설치 확인: `review-draft similar-check`.

```bash
# 팀원: 프로필(4개 축 서술) → 상위 10개
review-draft similar similarity/new_project_profile.json -o output/similarity --years 2026
review-draft similar-top output/similarity/top10.json --unit 내역1_금융AI실증매칭

# 분석 담당자: 코퍼스 임베딩 적재 (similarity_check.py 산출물의 '전체' 시트가 입력)
pip install -e ".[similarity]"
python similarity/embed_corpus.py --xlsx similarity/results/유사도_산출결과_청년금융혁신.xlsx --out output/embeddings
export SUPABASE_URL=… SUPABASE_ANON_KEY=… BIZ_EMBED_LOAD_TOKEN=…   # 적재 토큰은 관리자에게
python similarity/load_embeddings.py --dir output/embeddings
```

DB 객체: 표 `biz_embedding`(4개 축 vector(1024), HNSW 코사인 인덱스, RLS 로 직접 조회 차단), RPC `match_biz`(가중합 상위 k),
`biz_embedding_stats`, `upsert_biz_embedding`(적재 토큰 검사). 가중치는 지표(안) 20·30·30·15 를 합 100 으로 정규화한 값과 동일합니다.

## 유사·중복 후보 임베딩 분석 (`similarity/`, 분석 담당자용 전체 재산출)

협의사업의 사업목적·지원대상·지원내용·전달체계를 「중앙부처 지원사업 공고정보」 xlsx 의 기존사업과
BAAI/bge-m3 임베딩으로 비교해 유사·중복 검토 후보를 뽑습니다. 가중치는 「유사·중복사업 대상 선정 분석 지표(안)」
(20·30·30·15) 를 합 100 으로 정규화해 적용합니다.

```bash
# torch 설치 (둘 중 하나)
pip install -e ".[similarity]"                                   # PyPI 기본 wheel (CUDA 포함, 약 3GB) — GPU 없는 PC/서버에서도 동작
pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install sentence-transformers openpyxl pandas
#   ↑ CPU 전용 wheel(약 200MB). Claude Code 클라우드 환경에서는 download.pytorch.org 가 기본 네트워크 정책에 막혀 있으므로
#     환경 설정(세션 제목줄의 클라우드 환경 메뉴 → Edit → Network access)에서 Custom 으로 바꾸고 Allowed domains 에
#     download.pytorch.org 를 추가하거나, 위의 PyPI 설치를 사용한다. 모델(BAAI/bge-m3, 약 2.2GB)은 huggingface.co 에서 받는다.
export HF_HUB_DISABLE_XET=1   # Hugging Face Xet 다운로드가 막힌 환경일 때
python similarity/similarity_check.py --xlsx "2026년 중앙부처 지원사업 공고정보.xlsx" \
    --profile similarity/new_project_profile.json --out output/similarity --top 10
# kosievalteam.github.io/biz_info 의 2025·2026년 내역사업(Supabase public.biz) 을 합치려면
# similarity/biz_export.sql 로 내보낸 JSON 을 --biz 로 지정합니다 (자료는 로그인 전용이므로 저장소에 올리지 않음)
python similarity/similarity_check.py --xlsx 공고정보.xlsx --biz biz_2025_2026.json --out output/similarity
# 그 밖의 추가 표(공고이름·목적·내용·대상 열 필수)는 --extra 파일.csv 로 합칩니다

# 기존사업을 내역·내내역사업 단위로 비교하고 공고정보는 보강 자료로만 쓰려면 (biz_struct·gonggo 추출 JSON 필요)
python similarity/similarity_check.py --level naeyeok --xlsx 공고정보.xlsx --biz biz_2025_2026.json \
    --struct struct2025/ --struct struct2026/ --parents-full parents_full/ --gonggo gonggo2025/ --gonggo gonggo2026/ \
    --out output/similarity
```

`--level naeyeok` 에서는 예산 구조표(biz_struct) 레벨3·4 항목을 내내역 단위로 만들고(부모 내역사업의 목적·대상·전달체계 상속),
공고정보는 공고명↔내역사업 매핑표(gonggo)·세부사업명·사업명 대조로 해당 단위에 ①목적·②내용·③대상·④규모를 덧붙입니다.
매핑 결과는 결과 xlsx 의 「공고매핑」 시트에서 확인할 수 있습니다.

- `similarity/new_project_profile.json` : 협의사업 4개 축 서술(전체·내역사업 단위). 새 협의사업은 이 파일을 바꿔 재사용
- `similarity/results/` : 「청년 금융혁신 창업·일자리 확대 지원」 분석 결과(개조식 보고서 .md, 전체 순위 .xlsx)

## 스킬: 유사·중복 후보 분석 (`.claude/skills/sme-similarity-review/`)

위 `similarity/` 파이프라인을 Claude 스킬로 묶은 것입니다. 요청서 텍스트 추출 → 4개 축 프로필 작성 → 기존사업을
내역·내내역사업 단위로 구성(공고정보는 보강) → bge-m3 임베딩·지표(안) 가중합 → 후보 10개와 개조식 보고서 작성까지의
절차와 함정, 자료 추출 방법을 담고 있습니다. 스크립트는 `similarity/` 와 같은 코드이며, 바꿀 때는 두 곳을 함께 고칩니다.
