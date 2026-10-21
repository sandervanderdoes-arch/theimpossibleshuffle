# The Impossible Shuffle

Humankind's most impossible mission: the whole internet shuffling one deck of cards until it matches the Holy Grail Sequence perfectly. The odds are 1 in 52! ≈ 8.07 × 10⁶⁷. We're trying anyway.

Live at **https://theimpossibleshuffle.com**

- One file, `index.html`: Tailwind Play CDN plus vanilla JavaScript, no build step. Open it straight from disk to play locally.
- Every shuffle is provably fair (see below); the dev console runs a self-test on load.
- Test the win screen with `?rigged=1`.

## Hosting

Served by GitHub Pages from the `main` branch root. `CNAME` holds the custom domain and `.nojekyll` skips Jekyll processing.

## Mission sponsors ("Become a Mission Sponsor")

- The unit is the hand-shuffle year: a proper hand shuffle takes about 20 seconds (seven riffles, Bayer & Diaconis 1992), so one year of nonstop hand shuffling is 1,577,880 shuffles.
- Three Stripe Payment Links (`SITE.fund.tea`, `odds`, `patron` in `index.html`) sell the ranks Rookie, Captain and Commander: 1,000 / 10,000 / 100,000 years of shuffling for $1.92 / $8.07 / $52. Each link's "After payment" redirect goes to `https://theimpossibleshuffle.com/?thanks=tea` (or `odds`, `patron`), which assigns the years to that browser's station and unlocks the extras.
- The station (internally "Hyperdrive") really performs every shuffle: the same provably fair recipe in Web Workers on every processor core (roughly 0.4–0.8 million shuffles per second per core). Every shuffle counts toward stats, badges and the humankind counter. The credit only goes down as shuffles are done, so pausing or closing the tab loses nothing. No prize.
- The Certificate of Trying Anyway is drawn on a canvas and saved as an A4 PDF with jsPDF (loaded from cdnjs only when needed; falls back to a PNG).
- **Test-fire:** anyone can run the station for 10 seconds for free, once per browser (a test drive, not a free station; the result stays on show) (`tfStart` in `index.html`). Same workers and recipe as a paid station; the shuffles count for humanity and the visitor's stats, never against paid years. It also measures the device's real speed, so the tier cards' "Station shift" estimates use it.
- **Sponsor moments in the jokes bar:** `supabase/sponsor-events.sql` creates `sponsor_events` (rank and time only, no names). Only the Modal webhook writes to it, after checking Stripe's signature, so every "REAL · A new Captain joined the mission 2 hours ago" line is a real payment. The rank comes from the amount ($1.92 / $8.07 / $52). Hide a test purchase with `hidden` = true. Without the table the site simply shows no sponsor lines.
- The Wall of Hopeless Heroes uses the `sponsors` table from `supabase/sponsors.sql`. Names arrive unapproved; approve them in the Supabase Table Editor. `supabase/wall-notify.sql` (optional) sends you a push notification through ntfy for every new name.

## Leaderboard ("Luckiest Shufflers")

- Run `supabase/leaderboard.sql` once in the Supabase SQL editor. Until then the section stays hidden.
- Joining is opt-in: a player picks a name, and every new personal best is sent as its recipe (v4). The database rebuilds the deck from the recipe, counts the matches itself, checks the seat belongs to that player, rejects scores that are implausible for the number of shuffles behind them (less than a 0.1% chance) and only lets the browser that created an entry update it.
- Ranking: best match first; on a tie, fewer tries (the shuffle number on which the best came up) wins, then whoever got there first. The file is safe to run again and upgrades an existing table.
- Names are unique (ignoring upper/lower case), and the date shown is when the best shuffle actually happened.
- "Share the top 3" draws a 1080×1350 image of the podium for Instagram.
- To remove an entry: Table Editor → `leaderboard` → set `hidden` to true.

## Provably fair shuffles

Each shuffle has a public recipe: the randomness of a [drand](https://www.drand.love/) round (published every 30 seconds by the League of Entropy; unknowable in advance), a 16-byte seat (its first 8 bytes are SHA-256('seat:' + the browser's leaderboard secret), so nobody can hand in someone else's shuffles) and a number n (0, 1, 2, … within that round).

    H = SHA-256(randomness ‖ seat ‖ n as 6 bytes, big-endian)
    deck = A♠ 2♠ … K♠ A♥ … K♥ A♦ … K♦ A♣ … K♣
    for i in 0..50: r = 52 − i; swap(deck[i], deck[i + H mod r]); H = H div r

The same recipe gives the same deck everywhere: in the page (`pfDeckInto`), in the database (`pf_deck`, `replay_shuffle`) and on the Time Traveller GPUs (`time-traveller/pf_cuda.py`). Known answers are checked in all three. Faking a winning shuffle means trying recipes until one works, which is just shuffling. If no drand relay answers, the page uses local randomness and calls it round 0. Anyone can replay any shuffle in the "Provably fair: check any shuffle yourself" box (the ✓ buttons on the leaderboards fill it in).

## The honors ("What if somebody actually does it?")

- Run `supabase/honors.sql` after `leaderboard.sql`.
- A real 52/52 asks the database to rebuild the shuffle from its recipe (`claim_mission`). If it is the Grail, the single `mission` row is created and the winner names it once (`set_mission_name`). A trigger refuses every later update, delete or truncate, even from the dashboard: one mission, one winner, no reset, no Season 2.
- While that row exists the site is a monument: the plaque in the hero, "The {Name} Sequence", progress at 100%, sponsorships closed, and the winner's Certificate of Doing the Impossible.
- The winning recipe is kept in the browser until the database has answered, so a dropped connection can't cost anyone the win.
- No money and no prizes: the honor is the prize.

## Time Traveller ($500, eight H100 GPUs)

See `time-traveller/README.md`: the Modal app that takes Stripe's webhook, runs 104 trillion shuffles on eight rented H100s and writes progress to the `travellers` table, the separate Time Travellers board, and the buyer's live mission panel (`?traveller={CHECKOUT_SESSION_ID}`). The card stays "Launch window opening soon" until `SITE.fund.traveller` has a Payment Link.

## Share previews ("I got 6/52")

`b/<score>/index.html` and `b/<score>.jpg` exist for scores 0–20 and 52. A brag shared from the
site links to `theimpossibleshuffle.com/b/<score>/`, so the link unfurls (X, WhatsApp, iMessage,
Slack, Facebook) with that score; people who click it land on the site. Higher scores fall back to
the homepage. The images and pages are generated from the same design as `og-image.png`.

## Hall of Firsts

- Run `supabase/firsts.sql` once (after `leaderboard.sql` and `honors.sql`). Until then the strip stays hidden.
- Every rung from 12 to 20 out of 52. The first human to reach a rung on the leaderboard (or a
  Time Traveller's mission) keeps it forever. Triggers record every crossing, so hiding an entry
  hands the rung to the next one in line. Honorary only.

## Recruits and humans

- Run `supabase/recruits.sql` once (after `live-counter.sql`). Until then the recruit panel still
  shares links, but nobody gets credit and the "humans have joined" line stays hidden.
- Every browser gets a random recruit code (no personal data). Shared links carry it as `?r=code`
  (the brag pages in `b/` pass it on). A newcomer who arrives through it and shuffles counts as that
  code's recruit, once; their shuffles add to the recruiter's tally.
- Titles: Recruitment Officer (1 recruit), Sergeant (3), Captain (10), Admiral (25), Minister of
  Recruitment (100). Honorary only.
- It counts browsers, not people, like the shuffle counter.

## Launch day

Run `supabase/prelaunch-reset.sql` once, just before launch: it sets the humankind counter back to
0 and empties the leaderboard, the Time Travellers and the Wall of Hopeless Heroes, so every number
on the site is real from day one. Then clear the site's data in the browsers you tested with.
Never run it after launch.
