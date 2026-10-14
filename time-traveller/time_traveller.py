"""Time Traveller missions for theimpossibleshuffle.com, on Modal (https://modal.com).

    Stripe Payment Link ($500)
      └─ checkout.session.completed ──▶ stripe_webhook (this app; checks Stripe's signature)
                                          ├─ travellers row in Supabase (service role, server side only)
                                          └─ run_mission.spawn()
                                               └─ shuffle_on_gpu × 8 (one H100 each, in parallel)
                                                    ├─ self-check: GPU decks == Python reference
                                                    ├─ provably fair shuffles, its own slice of n
                                                    └─ traveller_progress() every few seconds

The browser never decides anything about a Time Traveller: it only reads the travellers table.
Every best shuffle is double-checked on the CPU here, and rebuilt again by the database.

Commands (see README.md):
    modal deploy time_traveller.py                     # the webhook URL for Stripe
    modal run time_traveller.py::benchmark             # one H100 for 60 s: real speed and cost
    modal run time_traveller.py::dry_run --name "Test" --shuffles 1e11   # a small mission, no Stripe
"""
import hashlib
import json
import os
import re
import secrets
import time

import modal

APP_NAME = 'impossible-shuffle-time-traveller'
GPUS = int(os.environ.get('TT_GPUS', '8'))
HAND_YEAR = 1_577_880                              # shuffles in a year of nonstop hand shuffling (20 s each)
TARGET = 66_000_000 * HAND_YEAR                    # 66 million years: from the asteroid to today (104,140,080,000,000)
MAX_SECONDS = int(os.environ.get('TT_MAX_SECONDS', str(5 * 3600)))   # hard stop per GPU, whatever happens
REPORT_EVERY = 4.0                                 # seconds between progress reports per GPU
DRAND_CHAIN = '8990e7a9aaed2ffed73dbd7092123d6f289930540d7651336225dc172e51b2ce'
DRAND_HOSTS = ['https://api.drand.sh', 'https://api2.drand.sh', 'https://api3.drand.sh', 'https://drand.cloudflare.com']

app = modal.App(APP_NAME)
secret = modal.Secret.from_name('impossible-shuffle')   # STRIPE_*, SUPABASE_* (see README.md)
web_image = modal.Image.debian_slim(python_version='3.12').pip_install('stripe>=10', 'requests', 'fastapi[standard]')
gpu_image = (
    modal.Image.from_registry('nvidia/cuda:12.6.3-devel-ubuntu24.04', add_python='3.12')
    .pip_install('numba-cuda[cu12]', 'numpy<2.4', 'requests')
    .add_local_python_source('pf_cuda')
)


# ---------------------------------------------------------------------------
# Supabase (service role: only ever on this server)
# ---------------------------------------------------------------------------
def _sb(path, body, prefer=None):
    import requests
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    headers = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    if prefer:
        headers['Prefer'] = prefer
    for attempt in range(5):
        try:
            r = requests.post(f"{os.environ['SUPABASE_URL']}/rest/v1/{path}", json=body, headers=headers, timeout=20)
            if r.status_code < 500:
                if r.status_code >= 400:
                    raise RuntimeError(f'Supabase {path}: {r.status_code} {r.text[:300]}')
                return r.json() if r.text else None
        except (requests.ConnectionError, requests.Timeout):
            pass
        time.sleep(2 ** attempt)
    raise RuntimeError(f'Supabase {path}: unreachable')


def progress(ticket, delta=0, rate=None, best=None, status=None):
    """traveller_progress(): adds shuffles (to the traveller and humankind), and a better shuffle's recipe."""
    rnd, rand, seat, n = best if best else (None, None, None, None)
    return _sb('rpc/traveller_progress', {'p_ticket': ticket, 'p_delta': int(delta), 'p_rate': rate, 'p_round': rnd,
                                          'p_rand': rand, 'p_seat': seat, 'p_n': n, 'p_status': status})


def drand_latest():
    """(randomness, round) of the latest drand round; local randomness and round 0 if no relay answers."""
    import requests
    for host in DRAND_HOSTS:
        try:
            j = requests.get(f'{host}/{DRAND_CHAIN}/public/latest', timeout=6).json()
            if isinstance(j.get('round'), int) and re.fullmatch(r'[0-9a-f]{64}', j.get('randomness', '')):
                return bytes.fromhex(j['randomness']), j['round']
        except Exception:
            continue
    return secrets.token_bytes(32), 0


def clean_name(raw):
    name = re.sub(r'\s+', ' ', (raw or '')).strip()
    name = re.sub(r"[^\w .'-]", '', name)[:40].strip()
    return name if len(name) >= 2 else 'Anonymous Time Traveller'


# ---------------------------------------------------------------------------
# Stripe → mission
# ---------------------------------------------------------------------------
@app.function(image=web_image, secrets=[secret])
@modal.fastapi_endpoint(method='POST')
async def stripe_webhook(request: 'fastapi.Request'):  # noqa: F821
    import stripe
    from fastapi.responses import JSONResponse
    payload = await request.body()
    try:
        stripe.Webhook.construct_event(payload, request.headers.get('stripe-signature', ''), os.environ['STRIPE_WEBHOOK_SECRET'])
    except Exception:
        return JSONResponse({'error': 'bad signature'}, status_code=400)
    event = json.loads(payload)                          # signature checked: now read it as plain JSON
    if event['type'] not in ('checkout.session.completed', 'checkout.session.async_payment_succeeded'):
        return {'ok': True, 'ignored': event['type']}
    cs = event['data']['object']
    if cs.get('payment_status') != 'paid':
        return {'ok': True, 'waiting': 'payment not settled yet'}
    link = os.environ.get('TT_PAYMENT_LINK_ID')          # plink_… of the Time Traveller link (other links are ignored)
    if link and cs.get('payment_link') != link:
        return {'ok': True, 'ignored': 'another payment link'}
    if (cs.get('amount_total') or 0) < int(os.environ.get('TT_PRICE_CENTS', '50000')):
        return {'ok': True, 'ignored': 'amount'}
    name = next((f.get('text', {}).get('value') for f in (cs.get('custom_fields') or []) if f.get('type') == 'text'), None)
    ticket = hashlib.sha256(cs['id'].encode()).hexdigest()
    created = _sb('travellers?on_conflict=ticket', {'ticket': ticket, 'name': clean_name(name), 'target': TARGET, 'gpus': GPUS},
                  prefer='return=representation,resolution=ignore-duplicates')
    if created:                                          # Stripe retries webhooks: only the first one launches GPUs
        run_mission.spawn(ticket)
    return {'ok': True, 'launched': bool(created)}


@app.function(image=web_image, secrets=[secret], timeout=MAX_SECONDS + 1800)
def run_mission(ticket: str, target: int = TARGET):
    rand, rnd = drand_latest()
    seat = hashlib.sha256(b'time-traveller:' + ticket.encode()).digest()[:16]
    per = -(-target // GPUS)
    jobs = [(ticket, rand.hex(), rnd, seat.hex(), g * per, max(0, min(per, target - g * per))) for g in range(GPUS)]
    done, failures = 0, 0
    for res in shuffle_on_gpu.map(jobs, return_exceptions=True):
        if isinstance(res, Exception):
            failures += 1
            print('GPU worker failed:', repr(res))
        else:
            done += res['done']
    progress(ticket, 0, 0.0, status='done' if done > 0 else 'failed')
    print(f'mission {ticket[:12]}…: {done:,} shuffles, {failures} failed GPU workers')
    return done


@app.function(image=gpu_image, gpu='H100', secrets=[secret], timeout=MAX_SECONDS + 900)
def shuffle_on_gpu(job):
    import pf_cuda as pc
    ticket, rand_hex, rnd, seat_hex, start, count = job
    if count <= 0:
        return {'done': 0, 'best': 0}
    rand, seat = bytes.fromhex(rand_hex), bytes.fromhex(seat_hex)
    sh = pc.Shuffler(rand, seat)
    # Before shuffling for anyone: this GPU must produce exactly the reference decks.
    decks = sh.decks(start, 256)
    for i in range(256):
        if list(decks[i]) != pc.deck_ref(rand, seat, start + i):
            raise RuntimeError(f'GPU self-check failed at n={start + i}')
    best_m, done, pending, batch = 0, 0, 0, 1 << 26
    t0 = last = time.time()
    while done < count and time.time() - t0 < MAX_SECONDS:
        k = min(batch, count - done)
        tb = time.time()
        m, n = sh.run(start + done, k)
        dt = time.time() - tb
        done += k
        pending += k
        batch = int(min(1 << 34, max(1 << 24, k / max(dt, 1e-3))))   # about one second per launch
        best = None
        if m > best_m:
            if pc.matches_ref(pc.deck_ref(rand, seat, n)) != m:      # trust, but verify
                raise RuntimeError(f'GPU best does not replay: n={n}')
            best_m, best = m, (rnd, rand_hex, seat_hex, n)
        now = time.time()
        if best or now - last >= REPORT_EVERY:
            res = progress(ticket, pending, pending / max(now - last, 1e-3) * GPUS, best)   # rate shown for the whole mission
            pending, last = 0, now
            if res and res.get('mission'):
                print('The mission is accomplished. Standing down.')
                break
    if pending:
        progress(ticket, pending)
    return {'done': done, 'best': best_m}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@app.function(image=gpu_image, gpu='H100', timeout=900)
def benchmark_gpu(seconds: int = 60):
    import pf_cuda as pc
    rand, seat = secrets.token_bytes(32), secrets.token_bytes(16)
    sh = pc.Shuffler(rand, seat)
    decks = sh.decks(0, 256)
    assert all(list(decks[i]) == pc.deck_ref(rand, seat, i) for i in range(256)), 'self-check failed'
    sh.run(0, 1 << 22)                                   # warm up (compile)
    done, batch, t0 = 0, 1 << 26, time.time()
    while time.time() - t0 < seconds:
        tb = time.time()
        sh.run((1 << 22) + done, batch)
        done += batch
        batch = int(min(1 << 34, max(1 << 24, batch / max(time.time() - tb, 1e-3))))
    return done / (time.time() - t0)


@app.local_entrypoint()
def benchmark(seconds: int = 60, gpu_dollars_per_hour: float = 3.95):
    rate = benchmark_gpu.remote(seconds)
    total = rate * GPUS
    hours = TARGET / total / 3600
    print(f'One H100: {rate:,.0f} shuffles/s. Eight: {total:,.0f}/s.')
    print(f'A mission ({TARGET:,} shuffles) takes {hours:.2f} h on {GPUS} GPUs ≈ ${hours * GPUS * gpu_dollars_per_hour:,.0f} of GPU time.')
    print(f"Put TT.rate = {total:.3g} in index.html so the card's speed is the measured one.")


@app.local_entrypoint()
def dry_run(name: str = 'Test Traveller', shuffles: float = 1e11):
    """A small mission without Stripe (shows up on the site's Time Travellers board; hide it afterwards)."""
    import requests  # noqa: F401  (needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in your shell)
    session = 'cs_test_dryrun_' + secrets.token_hex(8)
    ticket = hashlib.sha256(session.encode()).hexdigest()
    _sb('travellers', {'ticket': ticket, 'name': clean_name(name), 'target': int(shuffles), 'gpus': GPUS}, prefer='return=minimal')
    print(f'Watch it live: https://theimpossibleshuffle.com/?traveller={session}')
    run_mission.remote(ticket, int(shuffles))
