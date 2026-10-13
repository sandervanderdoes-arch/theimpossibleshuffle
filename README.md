# The Impossible Shuffle

Humankind's ultimate exercise in futility: the whole internet shuffling one deck of cards until it matches the Holy Grail Sequence perfectly. The odds are 1 in 52! ≈ 8.07 × 10⁶⁷. We're trying anyway.

Live at **https://theimpossibleshuffle.com**

- One file, `index.html`: Tailwind Play CDN plus vanilla JavaScript, no build step. Open it straight from disk to play locally.
- Shuffles use `crypto.getRandomValues()` with rejection sampling and Fisher–Yates; the dev console runs a self-test on load.
- Test the win screen with `?rigged=1`.

## Hosting

Served by GitHub Pages from the `main` branch root. `CNAME` holds the custom domain and `.nojekyll` skips Jekyll processing.

## Mission sponsors ("Are you impatient?")

- Three Stripe Payment Links (`SITE.fund.tea`, `odds`, `patron` in `index.html`) sell a 1,000,000 / 500,000,000 / 1,000,000,000-year time skip plus extras. Each link's "After payment" redirect goes to `https://theimpossibleshuffle.com/?thanks=tea` (or `odds`, `patron`), which unlocks the extras in that browser.
- A time skip is drawn from the exact odds: a match with probability N / 52!, and the best match from the real distribution of the maximum. It never touches the humankind counter and has no prize.
- The Certificate of Futility is drawn on a canvas and saved as an A4 PDF with jsPDF (loaded from cdnjs only when needed; falls back to a PNG).
- The Wall of Futility uses the `sponsors` table from `supabase/sponsors.sql`. Names arrive unapproved; approve them in the Supabase Table Editor.
