# Time Traveller: eight H100s, 66 million years, one deck

The $500 tier on theimpossibleshuffle.com. A buyer's mission shuffles
**104,140,080,000,000** provably fair decks (66 million years of nonstop hand
shuffling at 20 seconds a shuffle) on eight NVIDIA H100 GPUs rented from
[Modal](https://modal.com). They watch it live on the site; their best shuffle goes on
the Time Travellers board, and if one of their shuffles is the Holy Grail, the mission
is accomplished, forever.

```
Stripe Payment Link ──▶ webhook (Modal, checks Stripe's signature)
                          ├─ travellers row in Supabase (service role key, server only)
                          └─ 8 × H100, each: self-check → shuffle its slice → report every 4 s
browser (?traveller=cs_…) ──reads──▶ travellers row (public, read-only)
```

Files:

- `pf_cuda.py`: the provably fair shuffle as a CUDA C kernel run through CuPy (same recipe as
  `pfDeckInto()` in `index.html` and `pf_deck()` in `supabase/leaderboard.sql`).
- `time_traveller.py`: the Modal app (webhook, mission, GPU workers, benchmark, dry run).
- `test_pf_cuda.py`: tests without a GPU (`python test_pf_cuda.py`): compiles the kernel's C source with
  g++/clang++ and checks it card for card against the Python reference, and compiles it for the H100 if
  NVRTC is installed.

## Honest numbers

Measured with `benchmark` (October 2026): **2.6 billion shuffles a second per H100**, so
21 billion a second on eight. A mission takes **about 1 hour 23 minutes** and about **$43** of
GPU time at Modal's ~$3.95 per H100-hour. The card says exactly that (`TT.rate = 2.1e10` in
`index.html`). The mission always does the full 104 trillion shuffles, however long that takes
(capped at `TT_MAX_SECONDS`, 5 hours per GPU by default), so a slower GPU costs you more, never
the buyer. Run the benchmark again after changing the kernel and update `TT.rate`.

Each GPU worker first recomputes 256 decks and compares them with the plain-Python
reference; if a single card differs, it refuses to shuffle (the mission shows as failed,
and you refund). Every new best is recomputed on the CPU before it is reported, and the
database rebuilds it a third time before it believes it.

## Set up

1. **Database.** Run `supabase/leaderboard.sql` (v4) and then `supabase/honors.sql` in
   the Supabase SQL editor.
2. **Modal.** `pip install modal`, `modal setup`, then create the secret:
   ```
   modal secret create impossible-shuffle \
     SUPABASE_URL=https://kinyyzyzdrpzxyxuwpdt.supabase.co \
     SUPABASE_SERVICE_ROLE_KEY=… \
     STRIPE_WEBHOOK_SECRET=whsec_… \
     TT_PAYMENT_LINK_ID=plink_… \
     TT_PRICE_CENTS=50000
   ```
   The service role key lives only here (Supabase → Project Settings → API). Never put it
   in `index.html`.
3. **Benchmark** (about $0.10): `modal run time_traveller.py::benchmark`. It prints the
   real speed, how long a mission takes and what it costs. Put the eight-GPU speed in
   `index.html` as `TT.rate`.
4. **Deploy:** `modal deploy time_traveller.py`. Note the URL of `stripe_webhook`.
5. **Stripe.**
   - Payment Link: "Time Traveller mission", $500, one-time. Add a custom text field
     "Name on the Time Travellers board" (required, up to 40 characters).
   - After payment: redirect to
     `https://theimpossibleshuffle.com/?traveller={CHECKOUT_SESSION_ID}` (type it
     exactly like that; Stripe fills in the id).
   - Developers → Webhooks → add endpoint: the `stripe_webhook` URL, events
     `checkout.session.completed` and `checkout.session.async_payment_succeeded`. Copy
     the signing secret into the Modal secret (`STRIPE_WEBHOOK_SECRET`).
   - Put the Payment Link's `plink_…` id in `TT_PAYMENT_LINK_ID` (other links are ignored).
6. **Site.** Put the Payment Link URL in `SITE.fund.traveller` in `index.html`. While it's
   empty, the card says "Launch window opening soon".
7. **Rehearsal** (runs partly on your computer: `pip install requests` first): `modal run time_traveller.py::dry_run --name "Test" --shuffles 1e11`
   runs a small mission without Stripe and prints the page to watch it on. Hide the test
   row afterwards (Table Editor → travellers → `hidden` = true). Then buy one yourself
   with a Stripe test-mode link.
8. **Sponsor moments** (optional): run `supabase/sponsor-events.sql`. The same webhook then also
   records every Rookie, Captain and Commander purchase (rank and time only) for the REAL lines
   in the site's jokes bar. Stripe already sends those checkouts to this webhook; redeploy after
   pulling (`modal deploy time_traveller.py`).
9. **Notifications** (optional, recommended): put your ntfy topic in
   `supabase/traveller-notify.sql` and run it in the SQL editor. Your phone then pings when someone
   boards, when their mission is done (tap it: the deck designer opens with them picked) and if a
   mission fails (refund them in Stripe).

## Notes

- Webhooks are retried by Stripe; only the first one launches GPUs (the ticket is unique).
- The ticket is SHA-256 of the Checkout session id, so the public table never shows
  session ids. The buyer's browser hashes the id from its URL to find its own row.
- To remove someone from the board: Table Editor → travellers → `hidden` = true.
- No prize: the honor is the prize (see the Honors section on the site).
