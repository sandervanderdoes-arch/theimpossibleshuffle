-- Live counter for "Actual attempts by humankind" on theimpossibleshuffle.com.
-- Run once in the Supabase SQL editor.
--
-- Visitors (the anon role) can read the total and add to it, but only through
-- add_attempts(), which accepts 1 to 5,000,000 shuffles per call. Nobody can
-- set, lower or delete the number from the website.

create table if not exists public.shuffle_stats (
  id          int primary key default 1 check (id = 1),   -- exactly one row
  attempts    bigint not null default 0,
  updated_at  timestamptz not null default now()
);

insert into public.shuffle_stats (id) values (1) on conflict (id) do nothing;

alter table public.shuffle_stats enable row level security;

drop policy if exists "Anyone can read the counter" on public.shuffle_stats;
create policy "Anyone can read the counter"
  on public.shuffle_stats for select
  to anon, authenticated
  using (true);
-- No insert, update or delete policies: changes only happen inside add_attempts().

create or replace function public.add_attempts(delta bigint)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  total bigint;
begin
  if delta is null or delta < 1 or delta > 5000000 then
    raise exception 'delta must be between 1 and 5000000';
  end if;
  update shuffle_stats
     set attempts = attempts + delta, updated_at = now()
   where id = 1
  returning attempts into total;
  return total;
end;
$$;

revoke all on function public.add_attempts(bigint) from public;
grant execute on function public.add_attempts(bigint) to anon, authenticated;
