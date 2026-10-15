-- Push notifications for Time Travellers, on your phone through ntfy (like wall-notify.sql):
--   🚀 someone boards (a $500 sale; their mission is launching),
--   🏁 their mission is done: tap the notification to open the deck designer with them already picked,
--   ⚠️ their mission failed (refund them in Stripe).
-- Run once in the Supabase SQL editor, after honors.sql. Safe to run again.
-- Put your own ntfy topic below (the same one as the Wall of Hopeless Heroes is fine).
-- The request goes out through pg_net after the change is saved, so a notification problem can
-- never stop a mission.

create extension if not exists pg_net with schema extensions;

create or replace function public.notify_traveller()
returns trigger
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  topic constant text := 'CHANGE-ME-to-a-long-random-topic';   -- ← your ntfy topic
  no int;
  nr text;
  msg jsonb;
begin
  -- Their Time Traveller number: boarding order, as on the board and the merch (failed and hidden rows don't count).
  select count(*) into no from public.travellers
   where created_at <= new.created_at and status <> 'failed' and not hidden;
  nr := 'No. ' || lpad(greatest(no, 1)::text, 3, '0');

  if tg_op = 'INSERT' then
    msg := jsonb_build_object(
      'title', 'New Time Traveller: ' || new.name,
      'message', nr || ' just boarded. Eight GPUs are launching now; the mission takes about 1.5 hours.'
                 || E'\nTheir deck ships to the address in the Stripe payment (tap to open Stripe).',
      'tags', jsonb_build_array('rocket'),
      'click', 'https://dashboard.stripe.com/payments');
  elsif new.status = 'done' then
    msg := jsonb_build_object(
      'title', 'Mission complete: ' || new.name,
      'message', nr || ' · best shuffle ' || new.best || '/52 out of ' || to_char(new.attempts, 'FM999,999,999,999,999') || '.'
                 || E'\nTap to open the deck designer with them picked, download the deck ZIP and order it.',
      'tags', jsonb_build_array('checkered_flag'),
      'click', 'https://theimpossibleshuffle.com/merch/time-traveller/designer.html?t=' || new.ticket);
  elsif new.status = 'failed' then
    msg := jsonb_build_object(
      'title', 'Mission failed: ' || new.name,
      'message', nr || ' · ' || to_char(new.attempts, 'FM999,999,999,999,999') || ' shuffles done. Check the Modal logs, and refund them in Stripe.',
      'tags', jsonb_build_array('warning'),
      'priority', 4,
      'click', 'https://modal.com/apps');
  else
    return new;
  end if;

  perform net.http_post(url := 'https://ntfy.sh', body := msg || jsonb_build_object('topic', topic));
  return new;
exception when others then
  return new;                                                -- never block a mission over a notification
end;
$$;

revoke all on function public.notify_traveller() from public, anon, authenticated;

drop trigger if exists notify_traveller_boarded on public.travellers;
create trigger notify_traveller_boarded
  after insert on public.travellers
  for each row execute function public.notify_traveller();

drop trigger if exists notify_traveller_status on public.travellers;
create trigger notify_traveller_status
  after update of status on public.travellers
  for each row when (old.status is distinct from new.status and new.status in ('done', 'failed'))
  execute function public.notify_traveller();
