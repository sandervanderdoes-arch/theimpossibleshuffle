-- Global leaderboard ("Luckiest Shufflers") for theimpossibleshuffle.com. Version 4 (provably fair).
-- Run once in the Supabase SQL editor (same project as the live counter).
--
-- Each browser gets a random player id and a secret. Scores only come in
-- through submit_best(), which:
--   * takes the shuffle's public recipe (drand round + randomness, seat, n),
--     not a deck: it recomputes the deck itself with pf_deck() and counts the
--     matches (provably fair, v4; the browser cannot just claim a deck),
--   * checks the seat belongs to this player (its first 8 bytes are
--     SHA-256('seat:' || secret)), so nobody can submit someone else's shuffle,
--   * rejects scores that are implausible for the number of shuffles behind
--     them (less than a 0.1% chance),
--   * only lets the browser that created a row update it (secret hash).
-- Visitors can read names and scores, never ids or secrets.
-- Ranking: best match first; on a tie, fewer tries (shuffles needed to reach it) wins,
-- then whoever got there first.
-- To remove someone: Table Editor -> leaderboard -> set "hidden" to true.
-- Names are unique (ignoring case), and the date is when the best shuffle actually happened.
-- Safe to run again: it updates an existing leaderboard without losing entries.
-- Entries from before v4 stay, marked verified = false (their decks can't be recomputed).
-- After this file, run honors.sql (the mission and the Time Travellers).

create extension if not exists pgcrypto with schema extensions;

create table if not exists public.leaderboard (
  player_id    uuid primary key,
  secret_hash  text not null,
  name         text not null check (char_length(name) between 2 and 20),
  best         int  not null check (best between 0 and 52),
  deck         text not null,
  shuffles     bigint not null default 0 check (shuffles >= 0),
  achieved_at  timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  hidden       boolean not null default false
);
-- Tries: the shuffle number at which the best was reached (added in v2).
alter table public.leaderboard add column if not exists attempts bigint not null default 0 check (attempts >= 0);
update public.leaderboard set attempts = shuffles where attempts = 0;
drop index if exists public.leaderboard_rank_idx;
-- Provably fair recipe of the best shuffle (added in v4).
alter table public.leaderboard drop constraint if exists leaderboard_best_check;
alter table public.leaderboard add constraint leaderboard_best_check check (best between 0 and 52);
alter table public.leaderboard add column if not exists verified boolean not null default false;
alter table public.leaderboard add column if not exists pf_round bigint;
alter table public.leaderboard add column if not exists pf_rand text;
alter table public.leaderboard add column if not exists pf_seat text;
alter table public.leaderboard add column if not exists pf_n bigint;
create index leaderboard_rank_idx on public.leaderboard (best desc, attempts asc, achieved_at asc) where not hidden;
-- Names are unique (ignoring upper/lower case). Older duplicates get a short suffix first (added in v3).
update public.leaderboard l
   set name = left(l.name, 15) || ' ' || substr(l.player_id::text, 1, 4)
 where exists (select 1 from public.leaderboard o
                where lower(o.name) = lower(l.name) and o.player_id <> l.player_id
                  and (o.achieved_at, o.player_id) < (l.achieved_at, l.player_id));
create unique index if not exists leaderboard_name_key on public.leaderboard (lower(name));

alter table public.leaderboard enable row level security;

drop policy if exists "Anyone can read the visible leaderboard" on public.leaderboard;
create policy "Anyone can read the visible leaderboard"
  on public.leaderboard for select
  to anon, authenticated
  using (not hidden);
-- No insert, update or delete policies: changes only happen inside submit_best().

revoke all on public.leaderboard from anon, authenticated;
grant select (name, best, attempts, shuffles, achieved_at, verified, pf_round, pf_rand, pf_seat, pf_n) on public.leaderboard to anon, authenticated;

-- ---------------------------------------------------------------------------
-- Provably fair shuffles (v4). Must match pfDeckInto() in index.html and the
-- Time Traveller GPU kernel. Cards are coded suit * 13 + rank (suits S H D C,
-- ranks A 2 … 10 J Q K); the deck starts in that order.
--   H = SHA-256(rand (32 bytes) ‖ seat (16 bytes) ‖ n (6 bytes, big-endian))
--   for i in 0..50: r = 52 - i; swap(deck[i], deck[i + H mod r]); H = H div r
-- ---------------------------------------------------------------------------
create or replace function public.grail()
returns text[] language sql immutable as $$
  -- The Holy Grail Sequence (must match GRAIL in index.html).
  select array['5D','2C','QD','JH','KH','7H','KS','3H','10S','JD','JC','KD','7S',
    '9S','9H','4H','AC','3S','8H','2D','10D','5C','QH','QC','4C','9D',
    'AH','3C','10H','3D','9C','6H','6S','8D','5S','AD','5H','KC','10C',
    '4S','6D','4D','8S','JS','QS','7C','2S','2H','7D','6C','AS','8C']
$$;

create or replace function public.pf_deck(p_rand bytea, p_seat bytea, p_n bigint)
returns text[]
language plpgsql
immutable
set search_path = public, extensions
as $$
declare
  codes constant text[] := array['AS','2S','3S','4S','5S','6S','7S','8S','9S','10S','JS','QS','KS',
    'AH','2H','3H','4H','5H','6H','7H','8H','9H','10H','JH','QH','KH',
    'AD','2D','3D','4D','5D','6D','7D','8D','9D','10D','JD','QD','KD',
    'AC','2C','3C','4C','5C','6C','7C','8C','9C','10C','JC','QC','KC'];
  h bytea;
  x numeric := 0;
  d text[] := codes;
  j int;
  t text;
begin
  if p_rand is null or p_seat is null or length(p_rand) <> 32 or length(p_seat) <> 16
     or p_n is null or p_n < 0 or p_n >= 281474976710656 then
    raise exception 'bad recipe';
  end if;
  h := digest(p_rand || p_seat || substring(int8send(p_n) from 3 for 6), 'sha256');
  for k in 0..31 loop x := x * 256 + get_byte(h, k); end loop;
  for i in 1..51 loop
    j := i + (x % (53 - i))::int;
    x := div(x, 53 - i);
    t := d[i]; d[i] := d[j]; d[j] := t;
  end loop;
  return d;
end;
$$;

-- Hex recipe parts → bytes ('bad recipe' on anything odd).
create or replace function public.pf_bytes(p_hex text, p_len int)
returns bytea language plpgsql immutable as $$
begin
  if p_hex is null or p_hex !~ '^[0-9a-f]+$' or char_length(p_hex) <> p_len * 2 then raise exception 'bad recipe'; end if;
  return decode(p_hex, 'hex');
end;
$$;

-- Does this seat belong to the player with this secret? (first 8 bytes = SHA-256('seat:' || secret))
create or replace function public.pf_seat_ok(p_seat text, p_secret text)
returns boolean language sql immutable set search_path = public, extensions as $$
  select left(p_seat, 16) = left(encode(digest('seat:' || p_secret, 'sha256'), 'hex'), 16)
$$;

create or replace function public.pf_matches(p_deck text[])
returns int language sql immutable as $$
  select count(*)::int from generate_series(1, 52) i where p_deck[i] = (public.grail())[i]
$$;

-- Anyone can replay a shuffle from its recipe (the site does this in the browser too).
create or replace function public.replay_shuffle(p_rand text, p_seat text, p_n bigint)
returns json language plpgsql immutable set search_path = public, extensions as $$
declare d text[] := public.pf_deck(public.pf_bytes(p_rand, 32), public.pf_bytes(p_seat, 16), p_n);
begin
  return json_build_object('deck', d, 'matches', public.pf_matches(d));
end;
$$;

drop function if exists public.submit_best(uuid, text, text, text, bigint);
drop function if exists public.submit_best(uuid, text, text, text, bigint, bigint);
drop function if exists public.submit_best(uuid, text, text, text, bigint, bigint, timestamptz);
drop function if exists public.submit_best(uuid, text, text, bigint, text, text, bigint, bigint, bigint, timestamptz);
drop function if exists public.leaderboard_rank(int);
drop function if exists public.leaderboard_rank(int, uuid);
drop function if exists public.leaderboard_rank(int, uuid, bigint);

-- Where a score ranks, in the same order as the list.
-- With p_player: that player's own position. Without (or when that player has no visible entry):
-- where a new score would land today, counting it as a newcomer.
create function public.leaderboard_rank(p_best int, p_player uuid default null, p_attempts bigint default null)
returns json
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  me public.leaderboard%rowtype;
  r bigint;
  n bigint;
begin
  select count(*) into n from public.leaderboard where not hidden;
  if p_player is not null then
    select * into me from public.leaderboard where player_id = p_player and not hidden;
  end if;
  if me.player_id is not null then
    select 1 + count(*) into r from public.leaderboard
     where not hidden and (best > me.best
       or (best = me.best and (attempts < me.attempts or (attempts = me.attempts and achieved_at < me.achieved_at))));
  else
    select 1 + count(*) into r from public.leaderboard
     where not hidden and (best > p_best or (best = p_best and attempts <= coalesce(p_attempts, 9223372036854775807)));
    n := n + 1;   -- counting the newcomer
  end if;
  -- listed: is this player's own entry visible on the board? (false when it was deleted or hidden,
  -- so a browser that thinks it joined can find out and hand its score in again)
  return json_build_object('rank', r, 'players', n, 'listed', me.player_id is not null);
end;
$$;

-- v4: the browser sends the recipe of its best shuffle, never the deck.
-- p_rand null: only the name (and total shuffles) change, for players whose best is from before v4.
-- p_achieved_at: when the best shuffle actually happened (from the browser, kept within sane bounds
-- and never before the drand round it used).
create function public.submit_best(p_player uuid, p_secret text, p_name text,
                                   p_round bigint, p_rand text, p_seat text, p_n bigint,
                                   p_shuffles bigint, p_attempts bigint, p_achieved_at timestamptz default null)
returns json
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  -- Fewest shuffles for which k matches has at least a 0.1% chance (index = k + 1).
  min_shuffles constant bigint[] := array[1,1,1,1,1,1,2,13,98,889,8975,99525,1202486,15723821,
    221246156,3333321482,53539970116,913308626133,16490001918235,314173419120674,6299103079051605];
  cards text[];
  m int := 0;
  clean_name text := btrim(regexp_replace(coalesce(p_name, ''), '\s+', ' ', 'g'));
  h text;
  row_ public.leaderboard%rowtype;
  when_ timestamptz;
  round_at timestamptz;
begin
  if p_player is null or p_secret is null or char_length(p_secret) < 16 or char_length(p_secret) > 128 then
    raise exception 'bad player';
  end if;
  if char_length(clean_name) < 2 or char_length(clean_name) > 20 or clean_name !~ '^[[:alnum:] _.''-]+$' then
    raise exception 'bad name';
  end if;
  if exists (select 1 from public.leaderboard where lower(name) = lower(clean_name) and player_id <> p_player) then
    raise exception 'name taken';
  end if;
  h := encode(digest(p_secret, 'sha256'), 'hex');
  select * into row_ from public.leaderboard where player_id = p_player;
  if found and row_.secret_hash <> h then
    raise exception 'bad player';
  end if;

  if p_rand is null then                                   -- rename only
    if not found then raise exception 'no shuffle'; end if;
    update public.leaderboard
       set name = clean_name, shuffles = greatest(shuffles, coalesce(p_shuffles, 0)), updated_at = now()
     where player_id = p_player;
    return public.leaderboard_rank(row_.best, p_player);
  end if;

  if not public.pf_seat_ok(p_seat, p_secret) then raise exception 'bad seat'; end if;
  cards := public.pf_deck(public.pf_bytes(p_rand, 32), public.pf_bytes(p_seat, 16), p_n);
  m := public.pf_matches(cards);
  -- p_attempts: the shuffle on which this deck came up, so it can't exceed the total.
  if p_attempts is null or p_attempts < 1 or p_attempts > coalesce(p_shuffles, 0)
     or (m <= 20 and p_attempts < min_shuffles[m + 1])
     or (m between 21 and 51 and p_attempts < min_shuffles[21]) then
    raise exception 'implausible';
  end if;
  -- drand's default chain: round 1 at 2020-07-22 21:17:30 UTC, then one every 30 s (round 0: no beacon).
  if p_round is null or p_round < 0 then raise exception 'bad recipe'; end if;
  round_at := to_timestamp(1595431050 + greatest(p_round - 1, 0) * 30);
  if p_round > 0 and round_at > now() + interval '2 minutes' then raise exception 'bad recipe'; end if;
  when_ := least(now(), greatest(coalesce(p_achieved_at, now()), timestamptz '2025-01-01', case when p_round > 0 then round_at end));

  if not found then
    insert into public.leaderboard (player_id, secret_hash, name, best, deck, shuffles, attempts, achieved_at,
                                    verified, pf_round, pf_rand, pf_seat, pf_n)
    values (p_player, h, clean_name, m, array_to_string(cards, ','), p_shuffles, p_attempts, when_,
            true, p_round, p_rand, p_seat, p_n);
  elsif m > row_.best then
    update public.leaderboard
       set name = clean_name, best = m, deck = array_to_string(cards, ','), shuffles = p_shuffles, attempts = p_attempts,
           achieved_at = when_, updated_at = now(), verified = true, pf_round = p_round, pf_rand = p_rand, pf_seat = p_seat, pf_n = p_n
     where player_id = p_player;
  else
    update public.leaderboard
       set name = clean_name, shuffles = greatest(shuffles, p_shuffles), updated_at = now()
     where player_id = p_player;
  end if;
  return public.leaderboard_rank(greatest(m, coalesce(row_.best, 0)), p_player);
exception when unique_violation then
  raise exception 'name taken';
end;
$$;

revoke all on function public.submit_best(uuid, text, text, bigint, text, text, bigint, bigint, bigint, timestamptz) from public;
revoke all on function public.leaderboard_rank(int, uuid, bigint) from public;
grant execute on function public.submit_best(uuid, text, text, bigint, text, text, bigint, bigint, bigint, timestamptz) to anon, authenticated;
grant execute on function public.replay_shuffle(text, text, bigint) to anon, authenticated;
grant execute on function public.leaderboard_rank(int, uuid, bigint) to anon, authenticated;
