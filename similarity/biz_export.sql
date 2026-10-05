-- kosievalteam.github.io/biz_info 의 내역사업 자료(Supabase public.biz) 를
-- similarity_check.py --biz 입력(JSON 배열)으로 내보내는 질의.
-- 로그인 권한이 있는 계정으로 Supabase SQL Editor 또는 MCP execute_sql 에서 실행하고,
-- 결과 JSON 배열을 파일(예: biz_2025_2026.json)로 저장한다. 자료는 로그인 전용이므로 저장소에 올리지 않는다.
select id, year yr, gubun gb, 소관 gwan, 세부사업명 sebu, 내역사업명 nae, 내역예산 nbud, 세부예산 sbud,
       left(내역목적, 600) npur,
       case when 세부목적 is distinct from 내역목적 then left(세부목적, 600) end spur,
       left(수혜대상, 300) tgt, 세부지원 meth, 지원규모 scale, left(세부추진기관, 150) org,
       지원분야대분류 big, 지원분야중분류 mid, 지원분야소분류 small, 지원산업 ind, 세부분야 sfield, 내역분야 nfield,
       left(공고지원내용, 400) gonggo, left(세부내용, 400) cont, left(내역산출근거, 300) calc, left(근거법령, 120) law, 예산서키 key
from public.biz
where year in (2025, 2026)
order by id;
