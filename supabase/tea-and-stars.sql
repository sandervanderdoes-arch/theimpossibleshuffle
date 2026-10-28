-- The Professor's Tea Fund and rank stars on the world ranking (theimpossibleshuffle.com).
-- Run once in the Supabase SQL editor (same project), after sponsor-events.sql, leaderboard.sql and honors.sql.
-- Safe to run again.
--
-- 1. tea_fund(): how many stations were sponsored, per rank. No names, no amounts, test purchases (hidden) left out.
--    The page turns it into cups of tea (Rookie 1, Captain 4, Commander 25, Time Traveller 100).
-- 2. Rank stars: when someone buys, the page passes their (private) leaderboard player id to Stripe as
--    client_reference_id. The Modal webhook checks Stripe's signature and calls grant_stars(), so stars only
--    ever come from real payments. Visitors see names and stars through leaderboard_stars(), never player ids.

-- ---------------------------------------------------------------------------
-- 1. The Professor's Tea Fund
-- ---------------------------------------------------------------------------
create or replace function public.tea_fund()
returns json
language sql
stable
security definer
set search_path = public
as $$
  select json_build_object(
    'rookie',    (select count(*) from public.sponsor_events where not hidden and rank = 'Rookie'),
    'captain',   (select count(*) from public.sponsor_events where not hidden and rank = 'Captain'),
    'commander', (select count(*) from public.sponsor_events where not hidden and rank = 'Commander'),
    'traveller', (select count(*) from public.travellers where not hidden and status <> 'failed'));
$$;
revoke all on function public.tea_fund() from public;
grant execute on function public.tea_fund() to anon, authenticated;

-- ---------------------------------------------------------------------------
-- 2. Rank stars: 1 Rookie, 2 Captain, 3 Commander, 4 Time Traveller. A player keeps their highest.
-- ---------------------------------------------------------------------------
create table if not exists public.sponsor_stars (
  player_id   uuid primary key,
  stars       smallint not null check (stars between 1 and 4),
  updated_at  timestamptz not null default now()
);
alter table public.sponsor_stars enable row level security;
revoke all on public.sponsor_stars from anon, authenticated;
-- No policies: only the webhook (service role, through grant_stars) writes, and nobody reads player ids.

create or replace function public.grant_stars(p_player uuid, p_stars int)
returns void
language sql
security definer
set search_path = public
as $$
  insert into public.sponsor_stars (player_id, stars) values (p_player, least(greatest(p_stars, 1), 4))
  on conflict (player_id) do update set stars = greatest(public.sponsor_stars.stars, excluded.stars), updated_at = now();
$$;
revoke all on function public.grant_stars(uuid, int) from public, anon, authenticated;
grant execute on function public.grant_stars(uuid, int) to service_role;

-- Names and stars of sponsors on the visible world ranking (names are unique there).
create or replace function public.leaderboard_stars()
returns table (name text, stars smallint)
language sql
stable
security definer
set search_path = public
as $$
  select l.name, s.stars from public.leaderboard l join public.sponsor_stars s using (player_id) where not l.hidden;
$$;
revoke all on function public.leaderboard_stars() from public;
grant execute on function public.leaderboard_stars() to anon, authenticated;
