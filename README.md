# The Impossible Shuffle

Humankind's most pointless mission: the whole internet shuffling one deck of cards until it matches the Holy Grail Sequence perfectly. The odds are 1 in 52! ≈ 8.07 × 10⁶⁷. We're trying anyway.

Live at **https://theimpossibleshuffle.com**

- One file, `index.html`: Tailwind Play CDN plus vanilla JavaScript, no build step. Open it straight from disk to play locally.
- Shuffles use `crypto.getRandomValues()` with rejection sampling and Fisher–Yates; the dev console runs a self-test on load.
- Test the win screen with `?rigged=1`.

## Hosting

Served by GitHub Pages from the `main` branch root. `CNAME` holds the custom domain and `.nojekyll` skips Jekyll processing.

## Mission sponsors ("Become a Mission Sponsor")

- The unit is the hand-shuffle year: a proper hand shuffle takes about 20 seconds (seven riffles, Bayer & Diaconis 1992), so one year of nonstop hand shuffling is 1,577,880 shuffles.
- Three Stripe Payment Links (`SITE.fund.tea`, `odds`, `patron` in `index.html`) sell the ranks Rookie, Captain and Commander: 1,000 / 10,000 / 100,000 years of shuffling for $1.92 / $8.07 / $52. Each link's "After payment" redirect goes to `https://theimpossibleshuffle.com/?thanks=tea` (or `odds`, `patron`), which assigns the years to that browser's station and unlocks the extras.
- The station (internally "Hyperdrive") really performs every shuffle: the same crypto Fisher–Yates in Web Workers on every processor core (roughly 0.5–0.7 million shuffles per second per core). Every shuffle counts toward stats, badges and the humankind counter. The credit only goes down as shuffles are done, so pausing or closing the tab loses nothing. No prize.
- The Certificate of Trying Anyway is drawn on a canvas and saved as an A4 PDF with jsPDF (loaded from cdnjs only when needed; falls back to a PNG).
- The Wall of Hopeless Heroes uses the `sponsors` table from `supabase/sponsors.sql`. Names arrive unapproved; approve them in the Supabase Table Editor.

## Leaderboard ("Luckiest Shufflers")

- Run `supabase/leaderboard.sql` once in the Supabase SQL editor. Until then the section stays hidden.
- Joining is opt-in: a player picks a name, and every new personal best is sent as the full 52-card deck. The database counts the matches itself, rejects scores that are implausible for the number of shuffles behind them (less than a 0.1% chance) and only lets the browser that created an entry update it.
- Ranking: best match first; on a tie, fewer tries (the shuffle number on which the best came up) wins, then whoever got there first. The file is safe to run again and upgrades an existing table.
- Names are unique (ignoring upper/lower case), and the date shown is when the best shuffle actually happened.
- "Share the top 3" draws a 1080×1350 image of the podium for Instagram.
- To remove an entry: Table Editor → `leaderboard` → set `hidden` to true.
