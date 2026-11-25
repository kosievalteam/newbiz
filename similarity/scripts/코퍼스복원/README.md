# 비교 코퍼스·메타표 복원과 산출물 마무리

컨테이너가 재생성되면 스크래치패드에만 있던 비교 코퍼스(`corpus_3631_v2.csv`)·메타표·메타 병합
스크립트가 사라진다. 이 폴더의 두 스크립트로 **커밋된 산출물에서 그대로 되살린다.**
기존 코드·산출물은 변경하지 않는다.

## 1. 코퍼스 복원

```bash
python3 -I restore_corpus.py \
  ../../results/유사도_산출결과_벤처기업경쟁력강화.xlsx \
  <작업폴더>/corpus_3631_v2.csv
```

- 입력은 **지역 필터를 적용하지 않은 3,631단위 산출물**이어야 한다
  (`벤처기업경쟁력강화`, `사회연대경제기업성장지원`, `사회적기업임팩트투자연계` 중 하나.
  `청년금융혁신`은 `행` 접두어가 `biz:` 라 행 번호 복원이 불가하다).
- `similarity_check.axis_texts()` 의 조립 규칙을 역산해 `load_extra()` 입력 스키마로 되돌린 뒤,
  **복원본에 같은 조립 규칙을 다시 적용해 원본 축 텍스트와 바이트 단위로 대조**한다.
  4개 축 전부 일치해야 종료 코드 0이다(2026-11-25 실행 기준 3,631/3,631 × 4축 일치).
- `corpus_3631_v2_메타.csv`(행·단위·연도·세부사업명·내역사업명·내내역명·연계공고)가 함께 만들어진다.
- **복원한 CSV 는 biz_info 파생 자료이므로 저장소에 커밋하지 않는다.** 필요할 때마다 다시 만든다.

## 2. 산출물 마무리(메타 병합)

`--extra` 경로로 돌린 `similarity_check.py` 산출물에는 단위·연도·세부사업명 등이 없다.

```bash
python3 -I finalize.py \
  out/similarity_scores.xlsx  <작업폴더>/corpus_3631_v2_메타.csv \
  ../../results/유사도_산출결과_전북AI기술활성화.xlsx \
  유사도_산출결과_<사업명>.xlsx
```

- 조인 키는 `행`. 열 순서는 참조 산출물의 `전체` 시트를 그대로 따른다.
- `공고매핑` 시트는 `--extra` 경로에서 생성되지 않으므로 **참조 산출물의 표를 옮긴다.**
  이번 실행의 매핑 결과가 아니므로 **보고서에 출처를 밝힌다.**

## 3. 실행 환경

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install sentence-transformers olefile
export HF_HUB_DISABLE_XET=1 LANG=C.UTF-8 LC_ALL=C.UTF-8   # LANG 미설정 시 --region 한글 인자가 깨진다
npm install --no-save docx                                 # md2docx.js 용
```

`report_figure.py` 의 `--chrome` 기본값은 컨테이너마다 달라지므로 실제 경로를 확인해 넘긴다
(`ls -d /opt/pw-browsers/chromium-*/`).
