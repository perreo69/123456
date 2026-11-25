-- ============================================================================
--  미르스타푸드 ERP · v54 변경이력(audit_logs)
--  ---------------------------------------------------------------------------
--  Supabase SQL Editor 에 이 파일 전체를 붙여 넣고 한 번 실행하면 끝입니다.
--  (https://supabase.com/dashboard/project/gzufnyglmvgzqltepock/sql/new)
--
--  · 재고조정 · 정보수정(품명·육류·업체·브랜드·원산지·단가·입고일·소비기한·
--    보관 위치·사용/미사용) · 삭제(입출고 취소 등)를 한 줄씩 쌓습니다.
--  · 이 표가 없어도 앱은 그대로 돌아가고, 「변경이력」 화면은 기존
--    tx_logs · fp_logs 의 「[재고조정]」 기록만 보여 줍니다.
--  · 여러 번 실행해도 안전합니다(이미 있으면 그대로 둡니다).
-- ============================================================================

create table if not exists public.audit_logs (
  id           bigserial primary key,
  created_at   timestamptz not null default now(),
  action_type  text not null default '',   -- '재고조정' · '정보수정' · '삭제'
  target_type  text not null default '',   -- '원료육' · '완제품' · '소스' · '향신료' · '야채' · '부자재' · '기타' · '회계'
  target_id    text not null default '',   -- 'lot:12' · 'fplot:3' · 'prod:0000000896' · 'tx:987' · 'tx:987|lot:12'
  product_name text not null default '',   -- 품목명(또는 전표 내용)
  summary      text not null default '',   -- 「변경 내용」 — 전 → 후를 한 줄로
  before_val   text not null default '',   -- 변경 전 값
  after_val    text not null default '',   -- 변경 후 값
  reason       text not null default '',   -- 사유(사용자가 적은 것)
  actor_email  text not null default '',   -- 수정자 이메일
  actor_name   text not null default ''    -- 수정자 이름
);

comment on table public.audit_logs is 'v54 — ERP 수정·삭제 변경이력(장부). 앱이 한 줄씩 덧붙인다.';

create index if not exists audit_logs_created_at_idx on public.audit_logs (created_at desc);
create index if not exists audit_logs_action_type_idx on public.audit_logs (action_type, created_at desc);
create index if not exists audit_logs_product_name_idx on public.audit_logs (product_name);

-- RLS — 로그인한 사용자만 읽고 쓸 수 있다. 기록은 덧붙이기만 하고 고치거나 지우지 않는다.
alter table public.audit_logs enable row level security;

drop policy if exists "audit_logs_select_authenticated" on public.audit_logs;
create policy "audit_logs_select_authenticated"
  on public.audit_logs for select
  to authenticated
  using (true);

drop policy if exists "audit_logs_insert_authenticated" on public.audit_logs;
create policy "audit_logs_insert_authenticated"
  on public.audit_logs for insert
  to authenticated
  with check (true);

grant select, insert on public.audit_logs to authenticated;
grant usage, select on sequence public.audit_logs_id_seq to authenticated;

-- 확인: 방금 만든 표가 보이면 성공입니다.
select count(*) as audit_rows from public.audit_logs;
