-- Pre-launch clean slate: run ONCE, just before launch, in the Supabase SQL editor.
-- It removes everything from testing so that every number on the site is real from day one:
--   * the "Actual attempts by humankind" counter goes back to 0,
--   * the Luckiest Shufflers leaderboard is emptied,
--   * the Time Travellers table is emptied (test purchases and rehearsals),
--   * the Wall of Hopeless Heroes is emptied.
-- After launch, never run this again: the counter and the boards are the story of the mission.
--
-- Step 1 (optional): look at what will be removed. Run these three lines on their own first.
--   select name, best, attempts, verified, hidden, achieved_at from public.leaderboard order by best desc;
--   select name, status, attempts, hidden, created_at from public.travellers order by created_at;
--   select name, dedication, approved, created_at from public.sponsors order by created_at;
--
-- Step 2: run everything below.

begin;
update public.shuffle_stats set attempts = 0, updated_at = now() where id = 1;
delete from public.leaderboard;
delete from public.travellers;     -- only test missions so far; a real buyer would show up in step 1
delete from public.sponsors;
commit;

-- The mission table (the winner) is left alone: it is empty, and it refuses changes anyway.
-- Afterwards, clear the site's data in every browser you tested with, or your old best and
-- shuffles come back from that browser: Chrome → the icon left of the address → Site settings →
-- Delete data (Safari: Settings → Privacy → Manage Website Data → theimpossibleshuffle.com → Remove).
