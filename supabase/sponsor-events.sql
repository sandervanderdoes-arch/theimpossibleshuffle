-- Sponsor moments for the "REAL" items in the jokes bar on theimpossibleshuffle.com.
-- Run once in the Supabase SQL editor (same project as the live counter).
--
-- Only the Time Traveller webhook on Modal writes here (service role, after it has
-- checked Stripe's signature), so every row is a real, paid Rookie, Captain or
-- Commander. No names, emails or amounts: just the rank and the time.
-- Visitors can read the rank and time, nothing else.

create table if not exists public.sponsor_events (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  ticket      text not null unique,                 -- sha256 of the Stripe checkout id (Stripe retries webhooks)
  rank        text not null check (rank in ('Rookie', 'Captain', 'Commander')),
  hidden      boolean not null default false        -- set to true to hide a test purchase
);

alter table public.sponsor_events enable row level security;

drop policy if exists "Anyone can read visible sponsor events" on public.sponsor_events;
create policy "Anyone can read visible sponsor events"
  on public.sponsor_events for select
  to anon, authenticated
  using (hidden = false);
-- No insert, update or delete policies: only the webhook (service role) and you can write.

revoke all on public.sponsor_events from anon, authenticated;
grant select (rank, created_at, hidden) on public.sponsor_events to anon, authenticated;
