-- Holy Grail cards on theimpossibleshuffle.com: a Commander can put their name on one card of the
-- Holy Grail deck. Only 52 exist, ever.
-- Run once in the Supabase SQL editor (same project as the live counter). Safe to run again.
--
-- Only the Time Traveller webhook on Modal deals cards (service role, after it has checked
-- Stripe's signature), so every name belongs to a real Commander payment. Names arrive
-- unapproved: approve them in the Table Editor (grail_cards → approved = true). To refuse a
-- name, edit it or delete the row (the card goes back into the deck).
-- card = 0..51 in the site's card order: suit × 13 + rank (♠ ♥ ♦ ♣, A 2 … 10 J Q K), so 0 = A♠, 51 = K♣.

create table if not exists public.grail_cards (
  card        smallint primary key check (card between 0 and 51),
  ticket      text not null unique,                    -- sha256 of the Stripe checkout id
  name        text not null check (char_length(btrim(name)) between 1 and 20),
  approved    boolean not null default false,
  created_at  timestamptz not null default now()
);

alter table public.grail_cards enable row level security;

drop policy if exists "Anyone can read approved grail cards" on public.grail_cards;
create policy "Anyone can read approved grail cards"
  on public.grail_cards for select
  to anon, authenticated
  using (approved = true);
-- No insert, update or delete policies: only the webhook (service role) and you can write.

revoke all on public.grail_cards from anon, authenticated;
grant select (card, name, created_at, approved) on public.grail_cards to anon, authenticated;

-- How many cards are still free (pending names count as taken).
create or replace function public.grail_cards_left()
returns int
language sql
stable
security definer
set search_path = public
as $$ select 52 - count(*)::int from public.grail_cards $$;

revoke all on function public.grail_cards_left() from public;
grant execute on function public.grail_cards_left() to anon, authenticated;

-- Deals one random free card to a Commander checkout. Stripe retries webhooks, so the same
-- ticket always gets the same card. Returns the card, or null when all 52 are gone.
create or replace function public.deal_grail_card(p_ticket text, p_name text)
returns smallint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_card smallint;
  v_name text := left(btrim(regexp_replace(coalesce(p_name, ''), '\s+', ' ', 'g')), 20);
begin
  if p_ticket is null or char_length(v_name) < 1 then return null; end if;
  select card into v_card from public.grail_cards where ticket = p_ticket;
  if found then return v_card; end if;
  for attempt in 1..5 loop
    select c into v_card
      from generate_series(0, 51) as c
      where c not in (select card from public.grail_cards)
      order by random() limit 1;
    if v_card is null then return null; end if;              -- sold out
    begin
      insert into public.grail_cards (card, ticket, name) values (v_card, p_ticket, v_name);
      return v_card;
    exception when unique_violation then
      select card into v_card from public.grail_cards where ticket = p_ticket;   -- a retry of the same payment
      if found then return v_card; end if;                   -- otherwise someone took that card first: deal again
    end;
  end loop;
  return null;
end;
$$;

revoke all on function public.deal_grail_card(text, text) from public, anon, authenticated;
grant execute on function public.deal_grail_card(text, text) to service_role;

-- The buyer's page asks which card it was dealt. It knows its own checkout id (from Stripe's
-- redirect), hashes it and asks with the hash: nobody can look up someone else's card.
create or replace function public.grail_card_for(p_ticket text)
returns table (card smallint, approved boolean)
language sql
stable
security definer
set search_path = public
as $$ select card, approved from public.grail_cards where ticket = p_ticket $$;

revoke all on function public.grail_card_for(text) from public;
grant execute on function public.grail_card_for(text) to anon, authenticated;

-- Optional: a push notification for every new name (to approve it). Put your ntfy topic in
-- the line marked ← (the same one as in wall-notify.sql) or leave this part as it is.
create extension if not exists pg_net with schema extensions;

create or replace function public.notify_new_grail_card()
returns trigger
language plpgsql
security definer
set search_path = public, extensions
as $$
begin
  if 'CHANGE-ME-to-a-long-random-topic' like 'CHANGE-ME%' then return new; end if;   -- ← your ntfy topic (both places)
  perform net.http_post(
    url := 'https://ntfy.sh',
    body := jsonb_build_object(
      'topic', 'CHANGE-ME-to-a-long-random-topic',
      'title', 'New name for a Holy Grail card',
      'message', new.name || E'\nApprove it in Supabase: Table Editor → grail_cards → approved = true.',
      'tags', jsonb_build_array('crown'),
      'click', 'https://supabase.com/dashboard/project/kinyyzyzdrpzxyxuwpdt/editor'
    )
  );
  return new;
exception when others then
  return new;                                                -- never block a card over a notification
end;
$$;

revoke all on function public.notify_new_grail_card() from public, anon, authenticated;

drop trigger if exists notify_new_grail_card on public.grail_cards;
create trigger notify_new_grail_card
  after insert on public.grail_cards
  for each row execute function public.notify_new_grail_card();
