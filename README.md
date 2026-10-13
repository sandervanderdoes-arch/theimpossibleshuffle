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
- Three Stripe Payment Links (`SITE.fund.tea`, `odds`, `patron` in `index.html`) sell the ranks Cadet, Captain and Commander: 1,000 / 10,000 / 100,000 years of shuffling for $1.92 / $8.07 / $52. Each link's "After payment" redirect goes to `https://theimpossibleshuffle.com/?thanks=tea` (or `odds`, `patron`), which assigns the years to that browser's station and unlocks the extras.
- The station (internally "Hyperdrive") really performs every shuffle: the same crypto Fisher–Yates in Web Workers on every processor core (roughly 0.5–0.7 million shuffles per second per core). Every shuffle counts toward stats, badges and the humankind counter. The credit only goes down as shuffles are done, so pausing or closing the tab loses nothing. No prize.
- The Certificate of Trying Anyway is drawn on a canvas and saved as an A4 PDF with jsPDF (loaded from cdnjs only when needed; falls back to a PNG).
- The Wall of Hopeless Heroes uses the `sponsors` table from `supabase/sponsors.sql`. Names arrive unapproved; approve them in the Supabase Table Editor.
