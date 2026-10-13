-- Global leaderboard ("Luckiest Shufflers") for theimpossibleshuffle.com.
-- Run once in the Supabase SQL editor (same project as the live counter).
--
-- Each browser gets a random player id and a secret. Scores only come in
-- through submit_best(), which:
--   * checks the deck is a real 52-card deck and counts the matches itself
--     (the browser cannot just claim a number),
--   * rejects scores that are implausible for the number of shuffles behind
--     them (less than a 0.1% chance) and anything above 20 matches,
--   * only lets the browser that created a row update it (secret hash).
-- Visitors can read names and scores, never ids or secrets.
-- To remove someone: Table Editor -> leaderboard -> set "hidden" to true.

create extension if not exists pgcrypto with schema extensions;

create table if not exists public.leaderboard (
  player_id    uuid primary key,
  secret_hash  text not null,
  name         text not null check (char_length(name) between 2 and 20),
  best         int  not null check (best between 0 and 20),
  deck         text not null,
  shuffles     bigint not null default 0 check (shuffles >= 0),
  achieved_at  timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  hidden       boolean not null default false
);
create index if not exists leaderboard_rank_idx on public.leaderboard (best desc, achieved_at asc) where not hidden;

alter table public.leaderboard enable row level security;

drop policy if exists "Anyone can read the visible leaderboard" on public.leaderboard;
create policy "Anyone can read the visible leaderboard"
  on public.leaderboard for select
  to anon, authenticated
  using (not hidden);
-- No insert, update or delete policies: changes only happen inside submit_best().

revoke all on public.leaderboard from anon, authenticated;
grant select (name, best, shuffles, achieved_at) on public.leaderboard to anon, authenticated;

create or replace function public.submit_best(p_player uuid, p_secret text, p_name text, p_deck text, p_shuffles bigint)
returns json
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  -- The Holy Grail Sequence (must match GRAIL in index.html).
  grail constant text[] := array['5D','2C','QD','JH','KH','7H','KS','3H','10S','JD','JC','KD','7S',
    '9S','9H','4H','AC','3S','8H','2D','10D','5C','QH','QC','4C','9D',
    'AH','3C','10H','3D','9C','6H','6S','8D','5S','AD','5H','KC','10C',
    '4S','6D','4D','8S','JS','QS','7C','2S','2H','7D','6C','AS','8C'];
  -- Fewest shuffles for which k matches has at least a 0.1% chance (index = k + 1).
  min_shuffles constant bigint[] := array[1,1,1,1,1,1,2,13,98,889,8975,99525,1202486,15723821,
    221246156,3333321482,53539970116,913308626133,16490001918235,314173419120674,6299103079051605];
  cards text[];
  m int := 0;
  clean_name text := btrim(regexp_replace(coalesce(p_name, ''), '\s+', ' ', 'g'));
  h text;
  row_ public.leaderboard%rowtype;
begin
  if p_player is null or p_secret is null or char_length(p_secret) < 16 or char_length(p_secret) > 128 then
    raise exception 'bad player';
  end if;
  if char_length(clean_name) < 2 or char_length(clean_name) > 20 or clean_name !~ '^[[:alnum:] _.''-]+$' then
    raise exception 'bad name';
  end if;
  cards := string_to_array(coalesce(p_deck, ''), ',');
  if array_length(cards, 1) is distinct from 52
     or (select count(distinct c) from unnest(cards) c) <> 52
     or exists (select 1 from unnest(cards) c where not c = any(grail)) then
    raise exception 'bad deck';
  end if;
  for i in 1..52 loop
    if cards[i] = grail[i] then m := m + 1; end if;
  end loop;
  if m > 20 or coalesce(p_shuffles, 0) < min_shuffles[m + 1] then
    raise exception 'implausible';
  end if;

  h := encode(digest(p_secret, 'sha256'), 'hex');
  select * into row_ from public.leaderboard where player_id = p_player;
  if not found then
    insert into public.leaderboard (player_id, secret_hash, name, best, deck, shuffles)
    values (p_player, h, clean_name, m, p_deck, p_shuffles);
  elsif row_.secret_hash <> h then
    raise exception 'bad player';
  elsif m > row_.best then
    update public.leaderboard
       set name = clean_name, best = m, deck = p_deck, shuffles = p_shuffles, achieved_at = now(), updated_at = now()
     where player_id = p_player;
  else
    update public.leaderboard
       set name = clean_name, shuffles = greatest(shuffles, p_shuffles), updated_at = now()
     where player_id = p_player;
  end if;
  return public.leaderboard_rank(greatest(m, coalesce(row_.best, 0)), p_player);
end;
$$;

-- Where a score ranks, in the same order as the list (best first, ties go to whoever got there first).
-- With p_player: that player's own position. Without: where a new score of p_best would land today.
create or replace function public.leaderboard_rank(p_best int, p_player uuid default null)
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
     where not hidden and (best > me.best or (best = me.best and achieved_at < me.achieved_at));
  else
    select 1 + count(*) into r from public.leaderboard where not hidden and best >= p_best;
    n := n + 1;   -- counting the newcomer
  end if;
  return json_build_object('rank', r, 'players', n);
end;
$$;

revoke all on function public.submit_best(uuid, text, text, text, bigint) from public;
revoke all on function public.leaderboard_rank(int, uuid) from public;
grant execute on function public.submit_best(uuid, text, text, text, bigint) to anon, authenticated;
grant execute on function public.leaderboard_rank(int, uuid) to anon, authenticated;
