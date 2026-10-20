-- Hall of Firsts for theimpossibleshuffle.com. Run once in the Supabase SQL editor, after
-- leaderboard.sql and honors.sql. Safe to run again.
--
-- Rungs: 8, 10, 12, 15 and 20 matching cards in one shuffle. The first human to reach a rung
-- keeps it forever, even when somebody else goes higher later. Scores count from the moment they
-- land on the Luckiest Shufflers board or a Time Traveller's mission, so joining the board is how
-- you claim one. Honorary only: no prizes, nothing of value.
--
-- Every crossing is recorded (one row per rung per player), so a hidden entry simply hands the
-- rung to the next one in line, and unhiding gives it back.

create table if not exists public.firsts (
  id           bigserial primary key,
  rung         int not null check (rung in (8, 10, 12, 15, 20)),
  lb_player    uuid,                                   -- leaderboard.player_id
  tt_ticket    text,                                   -- travellers.ticket
  achieved_at  timestamptz not null default now(),
  check ((lb_player is null) <> (tt_ticket is null))
);
create unique index if not exists firsts_lb_key on public.firsts (rung, lb_player) where lb_player is not null;
create unique index if not exists firsts_tt_key on public.firsts (rung, tt_ticket) where tt_ticket is not null;

alter table public.firsts enable row level security;
revoke all on public.firsts from anon, authenticated;
-- No policies: visitors only see the hall through hall_of_firsts(), which never returns ids.

-- Leaderboard: record every rung a new best crosses. Never blocks a score.
create or replace function public.firsts_from_leaderboard()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.firsts (rung, lb_player, achieved_at)
  select r, new.player_id, new.achieved_at from unnest(array[8, 10, 12, 15, 20]) r where new.best >= r
  on conflict do nothing;
  return new;
exception when others then
  return new;
end;
$$;
drop trigger if exists firsts_leaderboard on public.leaderboard;
create trigger firsts_leaderboard
  after insert or update of best on public.leaderboard
  for each row execute function public.firsts_from_leaderboard();

-- Time Travellers: the same, at the moment their GPUs report the better shuffle.
create or replace function public.firsts_from_travellers()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.firsts (rung, tt_ticket, achieved_at)
  select r, new.ticket, now() from unnest(array[8, 10, 12, 15, 20]) r where new.best >= r
  on conflict do nothing;
  return new;
exception when others then
  return new;
end;
$$;
drop trigger if exists firsts_travellers on public.travellers;
create trigger firsts_travellers
  after insert or update of best on public.travellers
  for each row execute function public.firsts_from_travellers();

-- Scores that are already there when this file runs.
insert into public.firsts (rung, lb_player, achieved_at)
select r, l.player_id, l.achieved_at from public.leaderboard l cross join unnest(array[8, 10, 12, 15, 20]) r where l.best >= r
on conflict do nothing;
insert into public.firsts (rung, tt_ticket, achieved_at)
select r, t.ticket, coalesce(t.finished_at, t.updated_at, t.created_at) from public.travellers t cross join unnest(array[8, 10, 12, 15, 20]) r where t.best >= r
on conflict do nothing;

-- The hall: per rung, the earliest visible claimant (hidden entries and failed missions don't count).
create or replace function public.hall_of_firsts()
returns json
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(json_agg(h order by h.rung), '[]'::json) from (
    select distinct on (f.rung)
           f.rung,
           coalesce(l.name, t.name) as name,
           f.achieved_at as at,
           case when f.tt_ticket is not null then 'traveller' else 'shuffler' end as kind,
           coalesce(l.verified, true) as verified
      from public.firsts f
      left join public.leaderboard l on l.player_id = f.lb_player and not l.hidden
      left join public.travellers t on t.ticket = f.tt_ticket and not t.hidden and t.status <> 'failed'
     where l.player_id is not null or t.ticket is not null
     order by f.rung, f.achieved_at, f.id
  ) h;
$$;
revoke all on function public.hall_of_firsts() from public;
grant execute on function public.hall_of_firsts() to anon, authenticated;
revoke all on function public.firsts_from_leaderboard() from public, anon, authenticated;
revoke all on function public.firsts_from_travellers() from public, anon, authenticated;
