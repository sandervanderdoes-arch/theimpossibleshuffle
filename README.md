# The Impossible Shuffle

Humankind's ultimate exercise in futility: the whole internet shuffling one deck of cards until it matches the Holy Grail Sequence perfectly. The odds are 1 in 52! ≈ 8.07 × 10⁶⁷. We're trying anyway.

Live at **https://theimpossibleshuffle.com**

- One file, `index.html`: Tailwind Play CDN plus vanilla JavaScript, no build step. Open it straight from disk to play locally.
- Shuffles use `crypto.getRandomValues()` with rejection sampling and Fisher–Yates; the dev console runs a self-test on load.
- Test the win screen with `?rigged=1`.

## Hosting

Served by GitHub Pages from the `main` branch root. `CNAME` holds the custom domain and `.nojekyll` skips Jekyll processing.
