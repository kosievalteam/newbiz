-- kosievalteam.github.io/biz_info 의 자료(Supabase 프로젝트 ryrhtvaeutqejdekpari, 로그인 전용)를
-- similarity_check.py 입력(JSON 배열)으로 내보내는 질의 모음.
-- 결과 JSON 은 로그인 전용 자료이므로 저장소에 올리지 않는다. 열 별칭은 바꾸지 말 것(스크립트가 그대로 읽는다).
-- MCP execute_sql 로 뽑을 때는 id 범위를 나눠(where id > LAST_ID ... order by id limit N) 청크 파일로 저장한다.
--   → references/data_sources.md 의 추출 절차 참고.

-- (1) 내역사업 (--biz) : public.biz, 2025·2026년
select id, year yr, gubun gb, 소관 gwan, 세부사업명 sebu, 내역사업명 nae, 내역예산 nbud, 세부예산 sbud,
       left(내역목적, 600) npur,
       case when 세부목적 is distinct from 내역목적 then left(세부목적, 600) end spur,
       left(수혜대상, 300) tgt, 세부지원 meth, 지원규모 scale, left(세부추진기관, 150) org,
       지원분야대분류 big, 지원분야중분류 mid, 지원분야소분류 small, 지원산업 ind, 세부분야 sfield, 내역분야 nfield,
       left(공고지원내용, 400) gonggo, left(세부내용, 400) cont, left(내역산출근거, 300) calc, left(근거법령, 120) law, 예산서키 key
from public.biz
where year in (2025, 2026)
order by id;

-- (2) 예산 구조표 (--struct) : public.biz_struct, 레벨2=내역사업, 레벨3·4=내내역
select id, year yr, 소관 gwan, 세부사업명 sebu, 차례 seq, 레벨 lvl, 항목명 item, 예산 bud
from public.biz_struct
where year in (2025, 2026) and 레벨 >= 2
order by id;

-- (3) 내내역 보유 내역사업의 전체 텍스트 (--parents-full)
with p as (select distinct year, 소관, 세부사업명 from public.biz_struct where 레벨 >= 3 and year in (2025, 2026))
select b.id, b.year yr, b.소관 gwan, b.세부사업명 sebu, b.내역사업명 nae,
       b.내역목적 npur_full, b.세부목적 spur_full, b.내역산출근거 calc_full, b.공고지원내용 gonggo_full, b.수혜대상 tgt_full
from public.biz b join p on p.year = b.year and p.소관 = b.소관 and p.세부사업명 = b.세부사업명
order by b.id;

-- (4) 공고명 ↔ 내역사업 매핑 (--gonggo) : public.gonggo
select id, year yr, 소관 gwan, 세부사업명 sebu, 내역사업명 nae, 공고명 name, 수행기관 org, 매핑출처 src
from public.gonggo
where year in (2025, 2026) and 내역사업명 is not null
order by id;
