-- A push notification (and optionally an email) for every new name on the Wall of Hopeless Heroes.
-- Run once in the Supabase SQL editor, after sponsors.sql. Safe to run again.
--
-- Uses ntfy (https://ntfy.sh): free, no account. Install the ntfy app (iPhone or Android),
-- tap "+" and subscribe to the topic below. Anyone who knows the topic name can read it,
-- so keep it long and random (the names are public on the Wall anyway once you approve them).
-- The request goes out through Supabase's pg_net extension, after the name is saved, so a
-- notification problem can never stop someone from submitting.

create extension if not exists pg_net with schema extensions;

create or replace function public.notify_new_sponsor()
returns trigger
language plpgsql
security definer
set search_path = public, extensions
as $$
begin
  perform net.http_post(
    url := 'https://ntfy.sh',
    body := jsonb_build_object(
      'topic', 'CHANGE-ME-to-a-long-random-topic',            -- ← your ntfy topic
      -- 'email', 'you@example.com',                         -- ← optional: also send it by email (remove the -- )
      'title', 'New name for the Wall of Hopeless Heroes',
      'message', new.name || coalesce(' · ' || new.dedication, '')
                 || E'\nApprove it in Supabase: Table Editor → sponsors → approved = true.',
      'tags', jsonb_build_array('classical_building'),
      'click', 'https://supabase.com/dashboard/project/kinyyzyzdrpzxyxuwpdt/editor'
    )
  );
  return new;
exception when others then
  return new;                                                -- never block a name over a notification
end;
$$;

revoke all on function public.notify_new_sponsor() from public, anon, authenticated;

drop trigger if exists notify_new_sponsor on public.sponsors;
create trigger notify_new_sponsor
  after insert on public.sponsors
  for each row execute function public.notify_new_sponsor();
