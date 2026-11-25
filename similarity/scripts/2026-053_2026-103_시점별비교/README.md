# 2026-053 ↔ 2026-103 시점별 누적 비교 · 직접 비교 재현 스크립트

세션 작업 폴더에서 실행한 스크립트 원본이다. 상대경로(`candidates.csv`, `out_A/`, `out_B/`,
`direct.json` 등)를 쓰므로 **한 폴더에 모아 두고 그 폴더에서 실행**해야 한다.
`verify_repro.py` 는 절대경로를 포함하므로 재실행 시 경로를 환경에 맞게 고친다.

실행 순서

1. `python3 ../../extract_requests.py <요청서 txt 폴더> candidates.csv extract_log.csv`
   — 검토의견서 91건에서 협의요청서 구간만 추출(사업간 비교표·검토의견·자체점검 판단 전면 차단)
2. 협의번호로 `pool_A_le053.csv`(≤053, 자기 제외 37건), `pool_B_le103.csv`(≤103, 자기 제외·053 포함 70건) 분할
3. `python3 ../../similarity_check.py --extra <pool> --profile <prof> --out <dir> --top 20`
   — **무수정 호출**. 산식·가중치·분석축·전처리 불변
4. `python3 ../../direct_compare.py profiles_clean_fn.json direct.json` — A↔B 직접 비교
5. `python3 build_xlsx.py` → 산출결과 XLSX(14시트)
6. `python3 figure.py` → 보고그림 PNG
7. `python3 verify_repro.py` → 기존 산출물 재현검증, `python3 verify_all.py` → PNG·DOCX·XLSX 3자 일치 검증

산출물은 `similarity/results/` 와 `similarity/results/figures/` 에 있다.
