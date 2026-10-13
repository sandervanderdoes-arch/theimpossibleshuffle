-- Wall of Futility on theimpossibleshuffle.com.
-- Run once in the Supabase SQL editor (same project as the live counter).
--
-- Visitors (the anon role) can submit a name, which arrives unapproved, and
-- can only read rows you have approved. To approve one: Table Editor →
-- sponsors → set "approved" to true. To remove one: delete the row.

create table if not exists public.sponsors (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  name        text not null check (char_length(btrim(name)) between 1 and 40),
  dedication  text check (dedication is null or char_length(dedication) <= 80),
  approved    boolean not null default false
);

alter table public.sponsors enable row level security;

drop policy if exists "Anyone can read approved sponsors" on public.sponsors;
create policy "Anyone can read approved sponsors"
  on public.sponsors for select
  to anon, authenticated
  using (approved = true);

drop policy if exists "Anyone can submit an unapproved name" on public.sponsors;
create policy "Anyone can submit an unapproved name"
  on public.sponsors for insert
  to anon, authenticated
  with check (approved = false);
-- No update or delete policies: only you (in the dashboard) can approve or remove rows.

grant select (name, dedication, created_at) on public.sponsors to anon, authenticated;
grant insert (name, dedication) on public.sponsors to anon, authenticated;
