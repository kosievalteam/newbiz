---
description: 사전협의 요청서(+사업설명서, 유사도 산출물)로 검토의견서 초안을 4단계로 작성한다
argument-hint: <요청서.hwpx> [사업설명서.hwpx …] [--similarity 산출물.xlsx] [--consult-no 2026-000] [--reviewer "홍길동 선임연구원"]
---

사전협의 검토의견서 초안을 작성한다. 반드시 `sme-review-drafter` 스킬(SKILL.md)의 절차를 따른다.

입력: $ARGUMENTS

진행 순서
1. 자료 검토 — 첫 번째 파일을 협의요청서로, 나머지 .hwp/.hwpx/.pdf 를 사업설명서 등 참고자료로 간주하고 `scripts/rd.py parse` / `extract` 로 읽는다. 요청서와 설명서의 수치가 다르면 메모한다.
2. 유사도 후보 10개 — `--similarity` 로 지정된 산출물(또는 저장소 `similarity/results/`, `output/similarity/` 의 xlsx·top10.json)이 있으면 `scripts/rd.py similar-top` 으로 상위 10개 표를 사용자에게 제시한다. 산출물이 없으면 SKILL.md 2-1 의 (b) 절차대로 분석 가능 여부를 확인하고, 불가하면 모델 지식으로 대신하되 그 사실을 명시한다.
3. 상위 3개 유사·중복성 검토 — 상위 3개를 비교 대상으로 사업목적·지원대상·지원내용·지원방식을 대조하고 비교표를 만든다. 확인되지 않은 수치는 `[확인 필요]`.
4. 초안 작성 — 검토의견 JSON 작성 → `scripts/rd.py check` 로 오류 0건까지 수정 → `scripts/rd.py render … --appendix 요청서` 로 .hwpx/.md 생성(Word 가 필요하면 `--docx` 추가). 결과 파일 경로, 평가축별 결론과 핵심 권고 사유, 발송 전 확인 사항(reviewer_notes)을 보고한다.

`--consult-no`, `--reviewer` 가 주어지면 개요표의 협의번호·검토자에 반영한다.
