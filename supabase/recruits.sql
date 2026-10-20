-- Recruits and humans for theimpossibleshuffle.com. Run once in the Supabase SQL editor,
-- after live-counter.sql. Safe to run again.
--
-- * "N humans have joined the mission": every browser that shuffles at least once joins once.
-- * Recruiting: every browser has a random recruit code (10 letters and digits, no personal data).
--   Links people share carry it as ?r=code. A newcomer who arrives through such a link and shuffles
--   counts as that code's recruit, once. Their shuffles are added to the recruiter's tally.
-- * Titles (Recruitment Officer at 1 recruit, up to Minister of Recruitment at 100) are honorary:
--   no prizes, nothing of value.
-- Visitors can't read this table directly: only the functions below, which never return ids.
-- Like the shuffle counter, this counts browsers, not passports: someone who clears their
-- browser can join twice. It's a mission, not an election.

create table if not exists public.humans (
  player_id    uuid primary key,
  code         text not null unique check (code ~ '^[a-z0-9]{8,16}$'),
  recruited_by text check (recruited_by is null or recruited_by ~ '^[a-z0-9]{8,16}$'),
  shuffles     bigint not null default 0 check (shuffles >= 0),
  joined_at    timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index if not exists humans_recruited_by_idx on public.humans (recruited_by) where recruited_by is not null;

alter table public.humans enable row level security;
revoke all on public.humans from anon, authenticated;
-- No policies: nobody reads or writes this table except through the functions below.

alter table public.shuffle_stats add column if not exists humans bigint not null default 0;
-- shuffle_stats is already readable by everyone (live-counter.sql), so the new number shows up too.

-- A browser joins the mission (once). p_by: the recruit code from the link it arrived through.
create or replace function public.join_mission(p_player uuid, p_code text, p_by text default null)
returns json
language plpgsql
security definer
set search_path = public
as $$
declare
  by_code text := lower(nullif(btrim(coalesce(p_by, '')), ''));
  total bigint;
begin
  if p_player is null or p_code is null or p_code !~ '^[a-z0-9]{8,16}$' then raise exception 'bad request'; end if;
  if by_code is not null and (by_code !~ '^[a-z0-9]{8,16}$' or by_code = p_code
                              or not exists (select 1 from public.humans where code = by_code)) then
    by_code := null;                          -- unknown or own code: joined, but nobody's recruit
  end if;
  begin
    insert into public.humans (player_id, code, recruited_by) values (p_player, p_code, by_code);
  exception
    when unique_violation then
      if exists (select 1 from public.humans where player_id = p_player) then
        return json_build_object('humans', (select humans from public.shuffle_stats where id = 1), 'new', false);
      end if;
      raise exception 'code taken';           -- another browser has this code: the page picks a new one
  end;
  update public.shuffle_stats set humans = humans + 1, updated_at = now() where id = 1 returning humans into total;
  return json_build_object('humans', total, 'new', true);
end;
$$;

-- A recruit reports its own total shuffles now and then. It can only go up, and by at most what a
-- fast station could plausibly do since the last report (3 million a second, at least 5 million).
create or replace function public.recruit_progress(p_player uuid, p_total bigint)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_player is null or p_total is null or p_total < 0 then return; end if;
  update public.humans
     set shuffles = least(greatest(shuffles, p_total),
                          shuffles + greatest(5000000, (extract(epoch from now() - updated_at) * 3000000)::bigint)),
         updated_at = now()
   where player_id = p_player and recruited_by is not null;
end;
$$;

-- A recruiter's tally: how many recruits, and how many shuffles they have made so far.
create or replace function public.my_recruits(p_code text)
returns json
language sql
stable
security definer
set search_path = public
as $$
  select json_build_object('recruits', count(*), 'shuffles', coalesce(sum(shuffles), 0))
    from public.humans
   where recruited_by = lower(p_code) and p_code ~ '^[a-z0-9]{8,16}$';
$$;

revoke all on function public.join_mission(uuid, text, text) from public;
revoke all on function public.recruit_progress(uuid, bigint) from public;
revoke all on function public.my_recruits(text) from public;
grant execute on function public.join_mission(uuid, text, text) to anon, authenticated;
grant execute on function public.recruit_progress(uuid, bigint) to anon, authenticated;
grant execute on function public.my_recruits(text) to anon, authenticated;
