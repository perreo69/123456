
-- Deployment prerequisite: current shared state has no existing finance sections or price fields.
-- New financial data is isolated from the existing staff-readable company JSON.
create schema erp_finance_private;
revoke all on schema erp_finance_private from public,anon,authenticated;
grant usage on schema erp_finance_private to authenticated;
create table erp_finance_private.permissions(user_id uuid primary key references auth.users(id) on delete cascade, rights jsonb not null, updated_at timestamptz not null default now());
create table erp_finance_private.state(id integer primary key check(id=1), body jsonb not null default '{}'::jsonb);
insert into erp_finance_private.state(id) values(1);
alter table erp_finance_private.permissions enable row level security;
alter table erp_finance_private.state enable row level security;
revoke all on all tables in schema erp_finance_private from public,anon,authenticated;
create function erp_finance_private.defaults() returns jsonb language sql immutable set search_path='' as $$
select '{"buy_read":true,"buy_write":true,"sale_read":true,"sale_write":true,"inventory_read":true,"profit_read":true,"ledger_read":true,"balance_read":true}'::jsonb
$$;
create function erp_finance_private.rights(u uuid) returns jsonb language sql stable security definer set search_path='' as $$
select case when s.is_admin then erp_finance_private.defaults() else erp_finance_private.defaults()||coalesce(p.rights,'{}'::jsonb) end from public.erp_staff s left join erp_finance_private.permissions p on p.user_id=s.user_id where s.user_id=u
$$;
create function erp_finance_private.allowed(r jsonb,g text,w boolean default false) returns boolean language sql immutable set search_path='' as $$
select coalesce(case g
when 'buy_prices' then (r->>'buy_read')::boolean and (not w or (r->>'buy_write')::boolean)
when 'sale_prices' then (r->>'sale_read')::boolean and (not w or (r->>'sale_write')::boolean)
when 'buy_docs' then (r->>'ledger_read')::boolean and (r->>'buy_read')::boolean and (not w or (r->>'buy_write')::boolean)
when 'sale_docs' then (r->>'ledger_read')::boolean and (r->>'sale_read')::boolean and (not w or (r->>'sale_write')::boolean)
when 'buy_balance' then (r->>'balance_read')::boolean and (r->>'buy_read')::boolean and (not w or (r->>'buy_write')::boolean)
when 'sale_balance' then (r->>'balance_read')::boolean and (r->>'sale_read')::boolean and (not w or (r->>'sale_write')::boolean)
else false end,false)
$$;
create function erp_finance_private.clean_company(b jsonb) returns boolean language sql immutable set search_path='' as $$
select not (b ?| array['발주관리','주문관리','매입관리','매출관리','거래명세서','매입정산','매출정산','미수금','미지급금','__finance','__financeRights'])
and not exists(select 1 from jsonb_each(b) e cross join lateral jsonb_array_elements(case when jsonb_typeof(e.value)='array' then e.value else '[]'::jsonb end) x where x ?| array['매입단가','매출단가','매입금액','매출금액','재고단가','재고금액','매입원가','매출총이익','단가','금액','정산금액','잔액'])
$$;
do $$ begin if exists(select 1 from public.erp_next_company_state where id=1 and not erp_finance_private.clean_company(body)) then raise exception 'legacy finance data needs migration; stop';end if;end $$;
create function erp_finance_private.guard_company() returns trigger language plpgsql security definer set search_path='' as $$
begin if not erp_finance_private.clean_company(new.body) then raise exception 'finance data must use protected ERP API' using errcode='42501'; end if;return new;end $$;
create trigger erp_finance_guard before update of body or insert on public.erp_next_company_state for each row execute function erp_finance_private.guard_company();
create function erp_finance_private.load() returns jsonb language plpgsql security definer set search_path='' as $$
declare v_rights jsonb:=erp_finance_private.rights(auth.uid()); v_result jsonb;
begin
 if v_rights is null then raise exception 'staff required' using errcode='42501';end if;
 -- One snapshot for both shared and financial rows.
 select jsonb_build_object('revision',c.revision,'body',c.body,'finance',coalesce((select jsonb_object_agg(g.key,g.value) from jsonb_each(f.body) g where erp_finance_private.allowed(v_rights,g.key)), '{}'::jsonb),'rights',v_rights) into v_result from public.erp_next_company_state c cross join erp_finance_private.state f where c.id=1 and f.id=1;
 return v_result;
end $$;
create function erp_finance_private.validate(g text,v jsonb,c jsonb) returns boolean language plpgsql immutable set search_path='' as $$
declare x record; sec text; permitted text[];
begin
 if jsonb_typeof(v)<>'object' then return false;end if;
 if g in ('buy_prices','sale_prices') then
  sec:=case g when 'buy_prices' then '입고입력' else '출고입력' end;
  for x in select * from jsonb_each(v) loop
   if x.key !~ '^[1-9][0-9]{0,15}$' or jsonb_typeof(x.value) not in ('number','null') or (jsonb_typeof(x.value)='number' and (x.value::text !~ '^(0|[1-9][0-9]{0,9})$' or x.value::text::numeric>1000000000)) then return false;end if;
   if not exists(select 1 from jsonb_array_elements(coalesce(c->sec,'[]'::jsonb)) z where z->>'_seq'=x.key) then return false;end if;
  end loop;
 else
  permitted:=case g when 'buy_docs' then array['발주관리','매입관리'] when 'sale_docs' then array['주문관리','매출관리','거래명세서'] when 'buy_balance' then array['매입정산'] when 'sale_balance' then array['매출정산'] else array[]::text[] end;
  for x in select * from jsonb_each(v) loop
   if not x.key=any(permitted) or jsonb_typeof(x.value)<>'array' or exists(select 1 from jsonb_array_elements(x.value) z where jsonb_typeof(z)<>'object') then return false;end if;
  end loop;
 end if;return true;
end $$;
create function erp_finance_private.save(pr bigint,pp bigint,c jsonb,p jsonb,f jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare r jsonb:=erp_finance_private.rights(auth.uid()); oldf jsonb; nextf jsonb; x record; result jsonb; base jsonb;
begin
 if r is null then raise exception 'staff required' using errcode='42501';end if;
 if f is not null and (c is null or jsonb_typeof(f)<>'object' or octet_length(f::text)>5000000) then raise exception 'invalid finance save';end if;
 if c is not null and not erp_finance_private.clean_company(c) then raise exception 'unprotected finance data';end if;
 -- Serialize company and finance writes with the existing revision guard.
 if c is not null then perform 1 from public.erp_next_company_state where id=1 for update;end if;
 if f is not null then
  select body into oldf from erp_finance_private.state where id=1 for update;
  nextf:=oldf;
  for x in select * from jsonb_each(f) loop
   if not erp_finance_private.allowed(r,x.key,false) or not erp_finance_private.validate(x.key,x.value,c) then raise exception 'invalid finance group' using errcode='42501';end if;
   if x.value is distinct from coalesce(oldf->x.key,'{}'::jsonb) then
    if not erp_finance_private.allowed(r,x.key,true) then raise exception 'finance write forbidden' using errcode='42501';end if;
    nextf:=jsonb_set(nextf,array[x.key],x.value,true);
   end if;
  end loop;
 end if;
 result:=erp_next_internal.save_state(pr,pp,c,p);
 if f is not null then update erp_finance_private.state set body=nextf where id=1;end if;
 return result;
end $$;
create function erp_finance_private.manage(a text,p jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=auth.uid(); target uuid; r jsonb; o jsonb;
begin
 if not exists(select 1 from public.erp_staff where user_id=u and is_admin) then raise exception 'administrator required' using errcode='42501';end if;
 if a='list' then
  select coalesce(jsonb_agg(jsonb_build_object('id',s.user_id,'name',s.display_name,'admin',s.is_admin,'rights',erp_finance_private.rights(s.user_id)) order by s.is_admin desc,s.display_name,s.user_id),'[]'::jsonb) into o from public.erp_staff s;return o;
 elsif a='set' then
  target:=(p->>'id')::uuid;r:=p->'rights';
  if not exists(select 1 from public.erp_staff where user_id=target and not is_admin) or jsonb_typeof(r)<>'object' or (r- array['buy_read','buy_write','sale_read','sale_write','inventory_read','profit_read','ledger_read','balance_read'])<>'{}'::jsonb or exists(select 1 from jsonb_each(r) where jsonb_typeof(value)<>'boolean') then raise exception 'invalid staff permissions';end if;
  -- Acquire the company lock before changing permissions; stale sessions must reload.
  perform 1 from public.erp_next_company_state where id=1 for update;
  insert into erp_finance_private.permissions(user_id,rights) values(target,erp_finance_private.defaults()||r) on conflict(user_id) do update set rights=excluded.rights,updated_at=now();
  update public.erp_next_company_state set revision=revision+1,updated_at=now() where id=1;
  return jsonb_build_object('ok',true);
 end if;raise exception 'invalid action';
end $$;
revoke all on all functions in schema erp_finance_private from public,anon,authenticated;
grant execute on function erp_finance_private.load(),erp_finance_private.save(bigint,bigint,jsonb,jsonb,jsonb),erp_finance_private.manage(text,jsonb) to authenticated;
create function public.erp_next_finance_load() returns jsonb language sql security invoker set search_path='' as $$select erp_finance_private.load()$$;
create function public.erp_next_finance_save(p_revision bigint,p_personal_revision bigint,p_company jsonb,p_personal jsonb,p_finance jsonb) returns jsonb language sql security invoker set search_path='' as $$select erp_finance_private.save(p_revision,p_personal_revision,p_company,p_personal,p_finance)$$;
create function public.erp_next_finance_manage(p_action text,p_payload jsonb default '{}'::jsonb) returns jsonb language sql security invoker set search_path='' as $$select erp_finance_private.manage(p_action,p_payload)$$;
revoke all on function public.erp_next_finance_load(),public.erp_next_finance_save(bigint,bigint,jsonb,jsonb,jsonb),public.erp_next_finance_manage(text,jsonb) from public,anon,authenticated;
grant execute on function public.erp_next_finance_load(),public.erp_next_finance_save(bigint,bigint,jsonb,jsonb,jsonb),public.erp_next_finance_manage(text,jsonb) to authenticated;
