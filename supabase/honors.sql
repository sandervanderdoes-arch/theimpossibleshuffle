-- The mission and the Time Travellers on theimpossibleshuffle.com.
-- Run once in the Supabase SQL editor, after leaderboard.sql (v4) and live-counter.sql.
-- Safe to run again.
--
-- mission: one row, ever. It appears the moment somebody's shuffle matches the
--   Holy Grail Sequence, card for card. The database recomputes that shuffle from
--   its public recipe before it believes it. After that the row can never be
--   changed or deleted (a trigger refuses, even for you), except that the winner
--   may put their name on it once. No reset, no new target, no Season 2.
-- travellers: the Time Traveller missions (eight H100 GPUs each). Only the server
--   (service role, from the Modal app in /time-traveller) writes here; everyone
--   can read names and results.

-- ---------------------------------------------------------------------------
-- The mission
-- ---------------------------------------------------------------------------
create table if not exists public.mission (
  id           int primary key default 1 check (id = 1),     -- exactly one row, ever
  winner_name  text check (winner_name is null or char_length(winner_name) between 2 and 40),
  player_id    uuid,                                          -- private
  source       text not null check (source in ('browser', 'traveller')),
  pf_round     bigint not null,
  pf_rand      text not null,
  pf_seat      text not null,
  pf_n         bigint not null,
  attempts     bigint,                                        -- the winner's own shuffle count
  humankind    bigint,                                        -- humankind's total at that moment
  claimed_at   timestamptz not null default now(),
  named_at     timestamptz
);

alter table public.mission enable row level security;
drop policy if exists "Anyone can read the mission" on public.mission;
create policy "Anyone can read the mission" on public.mission for select to anon, authenticated using (true);
revoke all on public.mission from anon, authenticated;
grant select (id, winner_name, source, pf_round, pf_rand, pf_seat, pf_n, attempts, humankind, claimed_at, named_at)
  on public.mission to anon, authenticated;

-- Eternal: no update (except naming the winner once) and no delete, for anyone.
create or replace function public.mission_is_forever()
returns trigger language plpgsql as $$
begin
  if tg_op = 'DELETE' then raise exception 'The mission is accomplished. That is forever.'; end if;
  if old.winner_name is null and new.winner_name is not null
     and (new.id, new.player_id, new.source, new.pf_round, new.pf_rand, new.pf_seat, new.pf_n, new.attempts, new.humankind, new.claimed_at)
         is not distinct from
         (old.id, old.player_id, old.source, old.pf_round, old.pf_rand, old.pf_seat, old.pf_n, old.attempts, old.humankind, old.claimed_at) then
    return new;
  end if;
  raise exception 'The mission is accomplished. That is forever.';
end;
$$;
drop trigger if exists mission_is_forever on public.mission;
create trigger mission_is_forever before update or delete on public.mission
  for each row execute function public.mission_is_forever();
-- (truncate too)
create or replace function public.mission_no_truncate()
returns trigger language plpgsql as $$ begin raise exception 'The mission is accomplished. That is forever.'; end; $$;
drop trigger if exists mission_no_truncate on public.mission;
create trigger mission_no_truncate before truncate on public.mission
  for each statement execute function public.mission_no_truncate();

drop function if exists public.claim_mission(uuid, text, text, bigint, text, text, bigint, bigint);
drop function if exists public.set_mission_name(uuid, text, text);

-- Called by a browser whose shuffle matched all 52 cards. Returns the mission row
-- ({won: true} for the winner; {won: false} if somebody else got there first).
create function public.claim_mission(p_player uuid, p_secret text, p_name text,
                                     p_round bigint, p_rand text, p_seat text, p_n bigint, p_attempts bigint)
returns json
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  cards text[];
  clean_name text := nullif(btrim(regexp_replace(coalesce(p_name, ''), '\s+', ' ', 'g')), '');
  m public.mission%rowtype;
begin
  select * into m from public.mission where id = 1;
  if found then
    return json_build_object('won', m.player_id is not distinct from p_player and p_player is not null, 'winner_name', m.winner_name);
  end if;
  if p_player is null or p_secret is null or char_length(p_secret) < 16 then raise exception 'bad player'; end if;
  if not public.pf_seat_ok(p_seat, p_secret) then raise exception 'bad seat'; end if;
  cards := public.pf_deck(public.pf_bytes(p_rand, 32), public.pf_bytes(p_seat, 16), p_n);
  if cards is distinct from public.grail() then raise exception 'not the grail'; end if;
  if clean_name is not null and (char_length(clean_name) not between 2 and 40 or clean_name !~ '^[[:alnum:] _.''-]+$') then
    clean_name := null;
  end if;
  insert into public.mission (winner_name, player_id, source, pf_round, pf_rand, pf_seat, pf_n, attempts, humankind, named_at)
  values (clean_name, p_player, 'browser', coalesce(p_round, 0), p_rand, p_seat, p_n, p_attempts,
          (select attempts from public.shuffle_stats where id = 1), case when clean_name is not null then now() end)
  on conflict (id) do nothing;
  select * into m from public.mission where id = 1;
  return json_build_object('won', m.player_id = p_player, 'winner_name', m.winner_name);
end;
$$;

-- The winner names the mission (and the Grail) once. Final.
create function public.set_mission_name(p_player uuid, p_secret text, p_name text)
returns json
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  clean_name text := btrim(regexp_replace(coalesce(p_name, ''), '\s+', ' ', 'g'));
  m public.mission%rowtype;
begin
  select * into m from public.mission where id = 1;
  if not found or m.player_id is distinct from p_player or m.source <> 'browser'
     or not public.pf_seat_ok(m.pf_seat, p_secret) then
    raise exception 'not the winner';
  end if;
  if m.winner_name is not null then return json_build_object('winner_name', m.winner_name); end if;
  if char_length(clean_name) not between 2 and 40 or clean_name !~ '^[[:alnum:] _.''-]+$' then raise exception 'bad name'; end if;
  update public.mission set winner_name = clean_name, named_at = now() where id = 1;
  return json_build_object('winner_name', clean_name);
end;
$$;

revoke all on function public.claim_mission(uuid, text, text, bigint, text, text, bigint, bigint) from public;
revoke all on function public.set_mission_name(uuid, text, text) from public;
grant execute on function public.claim_mission(uuid, text, text, bigint, text, text, bigint, bigint) to anon, authenticated;
grant execute on function public.set_mission_name(uuid, text, text) to anon, authenticated;

-- ---------------------------------------------------------------------------
-- Time Travellers (written by the server only)
-- ---------------------------------------------------------------------------
create table if not exists public.travellers (
  ticket       text primary key check (ticket ~ '^[0-9a-f]{64}$'),   -- SHA-256 of the Stripe Checkout session id
  name         text not null check (char_length(name) between 2 and 40),
  status       text not null default 'boarding' check (status in ('boarding', 'running', 'done', 'failed')),
  gpus         int not null default 8,
  target       bigint not null default 0,          -- planned shuffles (for the progress bar)
  attempts     bigint not null default 0,          -- shuffles done so far
  rate         double precision not null default 0, -- shuffles per second, right now
  best         int not null default 0 check (best between 0 and 52),
  best_round   bigint,
  best_rand    text,
  best_seat    text,
  best_n       bigint,
  created_at   timestamptz not null default now(),
  started_at   timestamptz,
  finished_at  timestamptz,
  updated_at   timestamptz not null default now(),
  hidden       boolean not null default false
);
create index if not exists travellers_board_idx on public.travellers (best desc, attempts desc, created_at asc) where not hidden;

alter table public.travellers enable row level security;
drop policy if exists "Anyone can read the travellers" on public.travellers;
create policy "Anyone can read the travellers" on public.travellers for select to anon, authenticated using (not hidden);
revoke all on public.travellers from anon, authenticated;
grant select (ticket, name, status, gpus, target, attempts, rate, best, best_round, best_rand, best_seat, best_n,
              created_at, started_at, finished_at, updated_at) on public.travellers to anon, authenticated;
-- No insert/update policies: only the service role (which bypasses RLS) writes, through the functions below.

drop function if exists public.traveller_progress(text, bigint, double precision, bigint, text, text, bigint, text);
drop function if exists public.add_attempts_trusted(bigint);

-- Humankind's counter, for big trusted batches (no 5,000,000 cap). Server only.
create function public.add_attempts_trusted(delta bigint)
returns bigint language plpgsql security definer set search_path = public as $$
declare total bigint;
begin
  if delta is null or delta < 1 then raise exception 'delta must be positive'; end if;
  update shuffle_stats set attempts = attempts + delta, updated_at = now() where id = 1 returning attempts into total;
  return total;
end;
$$;

-- One progress report from one GPU: adds its new shuffles (to the traveller and to humankind),
-- and, when it brings a better shuffle, recomputes that shuffle from its recipe before believing it.
-- If that shuffle is the Holy Grail itself, the mission is accomplished, forever.
create function public.traveller_progress(p_ticket text, p_delta bigint, p_rate double precision,
                                          p_round bigint, p_rand text, p_seat text, p_n bigint, p_status text default null)
returns json
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  t public.travellers%rowtype;
  cards text[];
  m int;
begin
  select * into t from public.travellers where ticket = p_ticket for update;
  if not found then raise exception 'no such traveller'; end if;
  if coalesce(p_delta, 0) > 0 then
    perform public.add_attempts_trusted(p_delta);
    update public.travellers set attempts = attempts + p_delta where ticket = p_ticket;
  end if;
  if p_rand is not null then
    cards := public.pf_deck(public.pf_bytes(p_rand, 32), public.pf_bytes(p_seat, 16), p_n);
    m := public.pf_matches(cards);
    if m > t.best then
      update public.travellers set best = m, best_round = p_round, best_rand = p_rand, best_seat = p_seat, best_n = p_n
       where ticket = p_ticket;
    end if;
    if m = 52 then
      insert into public.mission (winner_name, source, pf_round, pf_rand, pf_seat, pf_n, attempts, humankind, named_at)
      values (t.name, 'traveller', coalesce(p_round, 0), p_rand, p_seat, p_n, t.attempts + coalesce(p_delta, 0),
              (select attempts from public.shuffle_stats where id = 1), now())
      on conflict (id) do nothing;
    end if;
  end if;
  update public.travellers
     set rate = coalesce(p_rate, rate),
         status = coalesce(p_status, case when status = 'boarding' then 'running' else status end),
         started_at = coalesce(started_at, now()),
         finished_at = case when p_status in ('done', 'failed') then now() else finished_at end,
         updated_at = now()
   where ticket = p_ticket
  returning * into t;
  return json_build_object('attempts', t.attempts, 'best', t.best, 'mission', exists (select 1 from public.mission));
end;
$$;

revoke all on function public.add_attempts_trusted(bigint) from public, anon, authenticated;
revoke all on function public.traveller_progress(text, bigint, double precision, bigint, text, text, bigint, text) from public, anon, authenticated;
grant execute on function public.add_attempts_trusted(bigint) to service_role;
grant execute on function public.traveller_progress(text, bigint, double precision, bigint, text, text, bigint, text) to service_role;
