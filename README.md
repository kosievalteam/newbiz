# review-draft — 사전협의 검토의견서 초안 자동 생성

중소기업지원사업 **사전협의 요청서**(.hwp/.hwpx/.pdf)를 읽어, 정책평가팀이 회람하는
**검토의견서** 초안(.docx/.md/.json)을 자동으로 채워 주는 명령행 도구입니다.

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

## 설치

```bash
pip install -e .            # 기본 (hwp/hwpx)
pip install -e ".[pdf,dev]" # PDF 입력 + 테스트
export ANTHROPIC_API_KEY=sk-ant-...
```

Python 3.10 이상. HWP 추출은 `olefile` 만으로 동작하며 한컴오피스·hwp5proc 설치가 필요 없습니다.

## 사용법

```bash
# 1) 요청서 → 검토의견서 초안 (output/ 에 .json .md .docx 생성)
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
          ─▶ schema.py (ReviewOpinion 검증) ─▶ render_docx.py / render_md.py
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

## 유사·중복 후보 임베딩 분석 (`similarity/`)

협의사업의 사업목적·지원대상·지원내용·전달체계를 「중앙부처 지원사업 공고정보」 xlsx 의 기존사업과
BAAI/bge-m3 임베딩으로 비교해 유사·중복 검토 후보를 뽑습니다. 가중치는 「유사·중복사업 대상 선정 분석 지표(안)」
(20·30·30·15) 를 합 100 으로 정규화해 적용합니다.

```bash
pip install torch sentence-transformers openpyxl pandas
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
