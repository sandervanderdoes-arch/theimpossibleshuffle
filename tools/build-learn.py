#!/usr/bin/env python3
"""Usage (from the repo root): python3 tools/build-learn.py .
Builds the explainer pages of theimpossibleshuffle.com: /math/, /52-factorial/, /same-deck-twice/,
/how-many-shuffles/ and /404.html. Plain static HTML (crawlable without JavaScript), shared learn.css."""
import json, os, re, sys
from math import comb, factorial
from fractions import Fraction

ROOT = sys.argv[1]
SITE = 'https://theimpossibleshuffle.com'
DATE = '2026-11-12'
idx = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
ANON = re.search(r"anonKey: '([^']+)'", idx).group(1)
SUPA = re.search(r"url: '(https://[a-z0-9]+\.supabase\.co)'", idx).group(1)
GRAIL = re.search(r"const GRAIL = \[(.*?)\];", idx, re.S).group(1)
GRAIL = re.findall(r"'([0-9JQKA]{1,2}[SHDC])'", GRAIL)
assert len(GRAIL) == 52, len(GRAIL)
N52 = factorial(52)
N52S = f'{N52:,}'.replace(',', ',<wbr>')

PAGES = {  # path: (short nav name)
    '/math/': 'The math',
    '/52-factorial/': '52! explained',
    '/same-deck-twice/': 'Same deck twice?',
    '/how-many-shuffles/': 'How many shuffles?',
}

ORG = {"@type": "Organization", "@id": f"{SITE}/#org", "name": "The Impossible Shuffle", "url": f"{SITE}/",
       "logo": {"@type": "ImageObject", "url": f"{SITE}/icon-512.png", "width": 512, "height": 512},
       "sameAs": ["https://www.instagram.com/theimpossibleshuffle/"]}


def esc(s):
    return s.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')


def head(path, title, desc, og_title, og_desc, img_alt, schema, robots='index, follow, max-image-preview:large'):
    url = SITE + path
    img = f"{SITE}/og{path.rstrip('/') or '/home'}.jpg" if path != '/404.html' else f'{SITE}/og-image.png'
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="{robots}">
{"" if robots == "noindex" else f'<link rel="canonical" href="{url}">'}
<meta name="theme-color" content="#03110a">
<meta property="og:type" content="article">
<meta property="og:site_name" content="The Impossible Shuffle">
<meta property="og:locale" content="en_US">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{esc(og_title)}">
<meta property="og:description" content="{esc(og_desc)}">
<meta property="og:image" content="{img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{esc(img_alt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(og_title)}">
<meta name="twitter:description" content="{esc(og_desc)}">
<meta name="twitter:image" content="{img}">
<meta name="twitter:image:alt" content="{esc(img_alt)}">
<link rel="icon" href="/favicon.ico" sizes="16x16 32x32 48x48">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bungee&display=swap" media="print" onload="this.media='all'">
<link rel="stylesheet" href="/learn.css">
<script type="application/ld+json">
{json.dumps(schema, ensure_ascii=False, indent=1)}
</script>
<script data-goatcounter="https://theimpossibleshuffle.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>
</head>
'''


def article_schema(path, headline, desc, crumb):
    url = SITE + path
    return {"@context": "https://schema.org", "@graph": [
        {"@type": "Article", "@id": url + "#article", "headline": headline, "description": desc,
         "image": f"{SITE}/og{path.rstrip('/')}.jpg", "datePublished": DATE, "dateModified": DATE,
         "inLanguage": "en", "mainEntityOfPage": url, "isPartOf": {"@id": f"{SITE}/#website"},
         "author": {"@id": f"{SITE}/#org"}, "publisher": {"@id": f"{SITE}/#org"},
         "about": [{"@type": "Thing", "name": "Factorial"}, {"@type": "Thing", "name": "Shuffling"}, {"@type": "Thing", "name": "Probability"}]},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "The Impossible Shuffle", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": "The Mathematics Behind the Madness", "item": f"{SITE}/math/"},
            {"@type": "ListItem", "position": 3, "name": crumb, "item": url}]},
        ORG]}


def top(path):
    nav = ''.join(f'<a href="{p}"{" aria-current=\"page\"" if p == path else ""}>{n}</a>' for p, n in PAGES.items() if p != '/math/')
    return f'''<body>
<a class="skip" href="#main">Skip to the article</a>
<div class="wrap">
<header class="top">
  <a class="brand" href="/">The Impossible Shuffle</a>
  <nav aria-label="The mathematics behind the madness">{nav}</nav>
</header>
'''


def crumbs(name):
    return f'<p class="crumbs"><a href="/">Home</a> › <a href="/math/">The math behind the madness</a> › {name}</p>\n'


def cta(slug, line):
    return f'''<aside class="cta" aria-label="Join the mission">
  <p>{line}</p>
  <a class="btn" href="/" data-goatcounter-click="learn-cta/{slug}">Shuffle the Impossible<small>Free · no sign-up · counted live</small></a>
</aside>
'''


def more(path):
    items = ''.join(f'<li><a href="{p}">{TITLES[p]}</a></li>' for p in TITLES if p != path)
    return f'<nav class="more" aria-label="More from the mathematics behind the madness"><p><b>Keep falling down the rabbit hole</b></p><ul>{items}</ul></nav>\n'


def foot():
    return f'''<footer class="foot">
  <p><a href="/">Play</a>·<a href="/math/">The math</a>·<a href="/52-factorial/">52!</a>·<a href="/same-deck-twice/">Same deck twice?</a>·<a href="/how-many-shuffles/">How many shuffles?</a>·<a href="https://www.instagram.com/theimpossibleshuffle/" rel="noopener me">Instagram</a></p>
  <p>The Impossible Shuffle · humankind's most pointless mission</p>
</footer>
</div>
'''


LIVE_JS = f'''<script>
/* The live worldwide total (the same public counter the game shows). Hidden if it can't be loaded. */
(function () {{
  var K = '{ANON}';
  fetch('{SUPA}/rest/v1/shuffle_stats?select=attempts&id=eq.1', {{ headers: {{ apikey: K, Authorization: 'Bearer ' + K }}, cache: 'no-store' }})
    .then(function (r) {{ return r.ok ? r.json() : Promise.reject(); }})
    .then(function (rows) {{
      var n = rows && rows[0] && Number(rows[0].attempts);
      if (!isFinite(n) || n <= 0) return;
      document.querySelectorAll('[data-live-total]').forEach(function (el) {{ el.textContent = n.toLocaleString('en-US'); }});
      document.querySelectorAll('[data-live]').forEach(function (el) {{ el.hidden = false; }});
    }}).catch(function () {{}});
}})();
</script>
'''

DEMO_JS = '''<script>
/* Shuffle a deck right here: crypto randomness + Fisher-Yates, compared with the real Holy Grail Sequence.
   Just for fun: these shuffles are not sent anywhere and don't count for the mission. */
(function () {
  var G = %s, SUIT = { S: '\\u2660', H: '\\u2665', D: '\\u2666', C: '\\u2663' }, n = 0, best = 0;
  var btn = document.getElementById('demoBtn'), deck = document.getElementById('demoDeck'), out = document.getElementById('demoOut');
  function rnd(k) { var a = new Uint32Array(1), lim = Math.floor(4294967296 / k) * k; do { crypto.getRandomValues(a); } while (a[0] >= lim); return a[0] %% k; }
  btn.addEventListener('click', function () {
    var d = G.slice(), hits = 0, html = '';
    for (var i = d.length - 1; i > 0; i--) { var j = rnd(i + 1), t = d[i]; d[i] = d[j]; d[j] = t; }
    for (i = 0; i < 52; i++) {
      var c = d[i], s = c.slice(-1), hit = c === G[i];
      if (hit) hits++;
      html += '<span class="' + (s === 'H' || s === 'D' ? 'red' : '') + (hit ? ' hit' : '') + '">' + c.slice(0, -1) + SUIT[s] + '</span>';
    }
    deck.innerHTML = html; deck.hidden = false; n++; best = Math.max(best, hits);
    out.innerHTML = '<b>' + hits + ' of 52</b> cards landed in their Holy Grail spot' + (hits ? ' (glowing).' : '.') +
      ' On average you get about 1. ' + (n > 1 ? 'Your best here: ' + best + '. ' : '') +
      'This exact order has almost certainly never existed before. <a href="/" data-goatcounter-click="learn-cta/demo">Make your shuffles count for humanity \\u2192</a>';
    btn.textContent = 'Shuffle again';
    if (window.goatcounter && window.goatcounter.count && n === 1) try { window.goatcounter.count({ path: 'event/learn-demo', title: 'learn-demo', event: true }); } catch (e) {}
  });
})();
</script>
''' % json.dumps(GRAIL)


TITLES = {
    '/52-factorial/': '52 Factorial: How Big Is 52! Really?',
    '/same-deck-twice/': 'Has Anyone Ever Shuffled the Same Deck Twice?',
    '/how-many-shuffles/': 'How Many Shuffles Does It Take to Randomize a Deck?',
}


def write(rel, html):
    p = os.path.join(ROOT, rel.strip('/'), 'index.html') if rel.endswith('/') else os.path.join(ROOT, rel.strip('/'))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8').write(html)
    print('wrote', p, len(html))


# ---------------------------------------------------------------- /52-factorial/
path = '/52-factorial/'
desc = ('52! is the number of ways to order a deck of cards: a 68-digit number, about 8 × 10⁶⁷. '
        'What it means, how to picture it, and a deck you can shuffle right here.')
html = head(path, '52 Factorial Explained: How Big Is 52! Really? | The Impossible Shuffle', desc,
            '52 Factorial: How Big Is 52! Really?',
            'There are 80,658,175,170,943,878,571,660,636,856,403,766,975,289,505,440,883,277,824,000,000,000,000 ways to order a deck of cards. Here is how to picture that.',
            '52! written out in full: a 68-digit number, about 8.07 × 10^67.',
            article_schema(path, TITLES[path], desc, '52 factorial'))
html += top(path) + '<main id="main">\n' + crumbs('52 factorial') + f'''<article>
<h1>52 Factorial: How Big Is 52! Really?</h1>
<p class="lede">Shuffle a deck of cards properly and you are almost certainly holding an order that no human has ever held before. The reason is one number: 52 factorial.</p>

<div class="answer">
  <p class="k">The short answer</p>
  <p><b>52! = 52 × 51 × 50 × … × 3 × 2 × 1</b>, which is</p>
  <p class="num">{N52S}</p>
  <p>That's a 68-digit number, about <b>8.07 × 10<sup>67</sup></b>: the number of different orders a standard 52-card deck can be in.</p>
</div>

<h2>Why 52 × 51 × 50 × …?</h2>
<p>Lay the cards down one at a time. You have 52 choices for the first card, 51 for the second, 50 for the third, and so on, until a single card is left for the last spot. Multiply all those choices together and you get 52!, said "52 factorial".</p>
<p>It starts small and then gets out of hand very quickly:</p>
<div class="tbl-wrap"><table class="tbl">
<thead><tr><th>Cards</th><th class="r">Possible orders</th></tr></thead>
<tbody>
<tr><td>3 cards (A, B, C)</td><td class="r">6</td></tr>
<tr><td>4 cards</td><td class="r">24</td></tr>
<tr><td>10 cards</td><td class="r">3,628,800</td></tr>
<tr><td>13 cards (one suit)</td><td class="r">6,227,020,800</td></tr>
<tr><td>20 cards</td><td class="r">2,432,902,008,176,640,000</td></tr>
<tr><td>52 cards (a full deck)</td><td class="r">≈ 8.07 × 10<sup>67</sup></td></tr>
</tbody></table></div>
<p>With three cards you can write every order down: ABC, ACB, BAC, BCA, CAB, CBA. With 52 cards, you can't. Not today, not ever.</p>

<h2>How to picture 52!</h2>
<p>Numbers this big stop meaning anything, so here are a few ways to make 52! hurt a bit more:</p>
<ul class="facts">
<li><b>More than the atoms on Earth.</b> Earth is made of roughly 1.3 × 10<sup>50</sup> atoms. 52! is about 600 quadrillion times bigger.</li>
<li><b>226 coin flips.</b> Guessing the exact order of a shuffled deck is about as likely as calling 226 coin flips in a row correctly.</li>
<li><b>The lottery, eight times.</b> Winning the Powerball jackpot (1 in 292,201,338) eight times in a row is still about 1.5 times more likely than one shuffle matching a deck you chose in advance.</li>
<li><b>Seconds.</b> 52! seconds is about 2.6 × 10<sup>60</sup> years. The universe is 13.8 billion years old. Scott Czepiel turned this into a famous thought experiment (walk around the equator, one step every billion years…): <a href="https://czep.net/weblog/52cards.html" rel="noopener">read it here</a>.</li>
<li><b>The fastest computers.</b> A supercomputer doing 2 × 10<sup>18</sup> operations per second, listing one deck per operation, would need about 10<sup>42</sup> years to list them all.</li>
</ul>

<h2>Is 52! bigger than the number of atoms in the universe?</h2>
<p>No, and this one gets mixed up a lot. The observable universe holds somewhere around 10<sup>78</sup> to 10<sup>82</sup> atoms, which is far more than 52! (about 10<sup>68</sup>). 52! beats the atoms on Earth by a mile, but not the whole universe. It's still the kind of number nobody will ever count to.</p>

<h2>What if everyone on Earth shuffled?</h2>
<p>Say all 8 billion people shuffled a deck once a second, starting at the Big Bang. By now that's about 3.5 × 10<sup>27</sup> shuffles, which covers roughly <b>4 × 10<sup>-41</sup></b> of all possible orders: a sliver too thin to write down sensibly.</p>
<p>And if the whole planet tried to hit one specific order, the expected wait would be around <b>3 × 10<sup>50</sup> years</b>, about 2 × 10<sup>40</sup> times the current age of the universe.</p>
<p>That, more or less, is <a href="/">what The Impossible Shuffle is doing</a>: one deck was shuffled once, and humanity is trying to shuffle that exact order again, together, one button press at a time.</p>

<h2>Try it: shuffle a deck right here</h2>
<div class="panel">
  <p>This deck is shuffled by your browser's cryptographic random generator (the Fisher–Yates method). Cards that glow sit in the same spot as in the Holy Grail Sequence, the one deck the whole mission is chasing.</p>
  <button type="button" id="demoBtn" class="btn2">Shuffle a deck</button>
  <div id="demoDeck" class="deck" role="group" aria-label="Your shuffled deck, top card first" hidden></div>
  <p id="demoOut" class="demo-out note" aria-live="polite">Your result appears here. Shuffles on this page are just for fun and don't count for the mission.</p>
</div>

<h2>More questions about 52!</h2>
<h3>How many digits does 52! have?</h3>
<p>68 digits. It ends in exactly 12 zeros, because the numbers 1 to 52 contain twelve factors of 5 (one each in 5, 10, 15 … 50, plus an extra one in 25 and 50), and each pairs with a 2 to make a 10.</p>
<h3>How do you calculate 52 factorial?</h3>
<p>Multiply 52 × 51 × 50 and keep going down to 1. A computer does it instantly (in Python: <code>math.factorial(52)</code>). For a quick estimate there's Stirling's approximation, n! ≈ √(2πn)·(n/e)<sup>n</sup>, which gives about 8.05 × 10<sup>67</sup>, only 0.16% off.</p>
<h3>What about a deck with jokers?</h3>
<p>Add two jokers and you have 54!, about 2.3 × 10<sup>71</sup> orders: some 2,900 times more than without them.</p>
<h3>So is every shuffled deck unique?</h3>
<p>Almost certainly, if it was shuffled well. Whether two shuffles in history ever matched is its own fun question: <a href="/same-deck-twice/">has anyone ever shuffled the same deck twice?</a></p>
</article>
''' + cta('52-factorial', 'Humanity is trying to beat 52! by hand. Well, by button. Every shuffle counts in the live worldwide total.') + more(path) + '</main>\n' + foot() + DEMO_JS + '</body>\n</html>\n'
write(path, html)

# ---------------------------------------------------------------- /same-deck-twice/
path = '/same-deck-twice/'


def Dn(m):
    d = [1, 0]
    for i in range(2, m + 1):
        d.append((i - 1) * (d[-1] + d[-2]))
    return d[m]


def fmt_odds(p):
    x = 1 / float(p)
    if x < 1000:
        return f'1 in {x:.1f}'.replace('.0 ', ' ') if x < 10 else f'1 in {round(x):,}'
    if x < 1e9:
        return f'1 in {round(x, -2 if x < 1e5 else -3):,.0f}'
    m, e = f'{x:.2e}'.split('e')
    return f'1 in {float(m):.1f} × 10<sup>{int(e)}</sup>'


rows = ''
for k, label in [(0, 'None'), (1, 'Exactly 1'), (2, 'Exactly 2'), (3, 'Exactly 3'), (5, 'Exactly 5'), (8, 'Exactly 8'), (10, 'Exactly 10'), (13, 'Exactly 13'), (20, 'Exactly 20'), (52, 'All 52')]:
    p = Fraction(comb(52, k) * Dn(52 - k), N52)
    pct = float(p) * 100
    pct_s = f'{pct:.1f}%' if pct >= 0.1 else ''
    rows += f'<tr><td>{label}</td><td class="r">{fmt_odds(p)}{" (" + pct_s + ")" if pct_s else ""}</td></tr>\n'

desc = ('Almost certainly not, if the deck was shuffled well. The real odds of two shuffles matching, '
        'when decks do repeat, and the live experiment trying to do it on purpose.')
html = head(path, 'Has a Deck Ever Been Shuffled the Same Way Twice? | The Impossible Shuffle', desc,
            'Has Anyone Ever Shuffled the Same Deck Twice?',
            'Even if every human who ever lived had shuffled once a minute for 80 years, the chance of a single repeat is about 1 in 7 × 10^30. So we are trying to do it on purpose.',
            'The question "Has anyone ever shuffled the same deck twice?" with the odds of a repeat.',
            article_schema(path, TITLES[path], desc, 'Same deck twice?'))
html += top(path) + '<main id="main">\n' + crumbs('Same deck twice?') + f'''<article>
<h1>Has Anyone Ever Shuffled the Same Deck Twice?</h1>
<p class="lede">Every time you shuffle a deck properly, you almost certainly create an order that has never existed before. But has a repeat <i>ever</i> happened, anywhere, in all of history?</p>

<div class="answer">
  <p class="k">The short answer</p>
  <p><b>Almost certainly not</b>, as long as the decks were properly shuffled. Even if every human who has ever lived (about 117 billion people) had shuffled a deck once a minute for 80 years, the chance that any two of those shuffles ever matched would be about <b>1 in 7 × 10<sup>30</sup></b>.</p>
</div>

<h2>The odds of two shuffles matching</h2>
<p>A deck of 52 cards can be in <a href="/52-factorial/">52! (52 factorial)</a> orders, about 8.07 × 10<sup>67</sup>. So the chance that one random shuffle matches one specific earlier deck is <b>1 in 52!</b>.</p>
<p>"Has it ever happened?" is a different question, though, because every shuffle in history gets compared with every other one. That's the famous <b>birthday problem</b>: in a room of just 23 people, two probably share a birthday. With N shuffles, the chance of at least one repeat is roughly N² ÷ (2 × 52!).</p>
<p>Plug in a generous history of shuffling, around 5 × 10<sup>18</sup> shuffles (every person ever, once a minute, for 80 years), and you get about 1 in 7 × 10<sup>30</sup>. To reach even a 50% chance of one repeat, humanity would need about <b>10<sup>34</sup> shuffles</b>. With all 8 billion people alive today shuffling once a second, that would take around 40 quadrillion years, roughly three million times the age of the universe.</p>

<h2>When decks really do repeat</h2>
<p>The math above assumes good, random shuffles. Real life cheats in a few ways:</p>
<ul class="facts">
<li><b>New decks.</b> A fresh deck comes in factory order, the same for everyone. Deal it without shuffling and you have "repeated" a deck millions of people have held.</li>
<li><b>Lazy shuffles.</b> One or two riffle shuffles leave lots of the old order in place. It takes about <a href="/how-many-shuffles/">seven riffle shuffles</a> to really mix a deck, and many card players stop well before that.</li>
<li><b>Perfect shuffles.</b> A magician's perfect "faro" shuffle splits the deck exactly in half and interleaves it card by card. It's not random at all: eight perfect out-shuffles bring a 52-card deck back to its starting order.</li>
<li><b>Bad computer shuffles.</b> In the late 1990s, researchers showed that an online poker site seeded its shuffle from the computer's clock, which left only a tiny fraction of the 52! possible decks reachable, few enough to predict the cards. <a href="https://www.scientificamerican.com/article/how-the-math-of-shuffling-cards-almost-brought-down-an-online-poker-empire/" rel="noopener">Scientific American tells the story.</a></li>
</ul>
<p>So identical decks do happen when the shuffle is weak. Two genuinely random shuffles matching? Not in this universe's lifetime.</p>

<h2>What are the odds of matching just some of the cards?</h2>
<p>Getting the whole deck right is hopeless, but matching a few cards happens all the time. On average, exactly <b>one card</b> lands in its original spot, no matter how big the deck is. And the chance of matching no cards at all is about 36.8%, which is 1/e (the number e = 2.718… shows up in the strangest places).</p>
<div class="tbl-wrap"><table class="tbl">
<caption class="note" style="caption-side:bottom;text-align:left;padding-top:.4rem">Chance that a random shuffle puts exactly this many cards in the same spot as a fixed target deck.</caption>
<thead><tr><th>Cards in the right spot</th><th class="r">Odds per shuffle</th></tr></thead>
<tbody>
{rows}</tbody></table></div>
<p>That's why the <a href="/#lbSection">Luckiest Shufflers board</a> on the game ranks people by their best partial match: 10 or 13 cards is already the luck of a lifetime. 52 is another matter.</p>

<h2>So we're trying to do it on purpose</h2>
<p>The Impossible Shuffle took one deck, shuffled it once and fixed that order forever: the <b>Holy Grail Sequence</b>. Since then, everyone who visits the site has been shuffling, trying to hit that exact order a second time. Every shuffle is <a href="/#verifyBox">provably fair</a> and counted in one shared, worldwide total.</p>
<p class="live" data-live hidden>Shuffles by humanity so far: <span data-live-total>…</span></p>
<p>Successful matches so far: none. If that ever changes, the front page turns into a monument and the Grail takes the winner's name. Mathematics is not worried.</p>
</article>
''' + cta('same-deck-twice', 'Mathematics says it will never happen. Add your shuffles anyway.') + more(path) + '</main>\n' + foot() + LIVE_JS + '</body>\n</html>\n'
write(path, html)

# ---------------------------------------------------------------- /how-many-shuffles/
path = '/how-many-shuffles/'
TV = {1: 1.000, 2: 1.000, 3: 1.000, 4: 1.000, 5: 0.924, 6: 0.614, 7: 0.334, 8: 0.167, 9: 0.085, 10: 0.043}
tvrows = ''.join(f'<tr><td>{k}</td><td class="r">{v:.3f}</td><td>{note}</td></tr>\n' for k, v, note in [
    (1, TV[1], 'Barely mixed'), (2, TV[2], ''), (3, TV[3], ''), (4, TV[4], 'Still easy to tell apart from random'),
    (5, TV[5], 'Order starts to break down'), (6, TV[6], ''), (7, TV[7], '<b>Close to random: the "seven shuffles" rule</b>'),
    (8, TV[8], ''), (9, TV[9], ''), (10, TV[10], 'Each extra shuffle roughly halves what is left')])
desc = ('Seven riffle shuffles mix a 52-card deck well; overhand shuffling takes thousands. '
        'The Bayer–Diaconis math, how computers shuffle, and how a shuffle can be provably fair.')
html = head(path, 'How Many Shuffles to Randomize a Deck of Cards? | The Impossible Shuffle', desc,
            'How Many Shuffles Does It Take to Randomize a Deck?',
            'Seven riffle shuffles. The famous Bayer–Diaconis result, why overhand shuffling is hopeless, and how computers do it properly.',
            'How many shuffles it takes to randomize a deck of cards: seven riffle shuffles.',
            article_schema(path, TITLES[path], desc, 'How many shuffles?'))
html += top(path) + '<main id="main">\n' + crumbs('How many shuffles?') + f'''<article>
<h1>How Many Shuffles Does It Take to Randomize a Deck?</h1>
<p class="lede">Most people give a deck two or three quick shuffles and call it random. Mathematics politely disagrees.</p>

<div class="answer">
  <p class="k">The short answer</p>
  <p><b>Seven riffle shuffles.</b> In 1992, mathematicians Dave Bayer and Persi Diaconis showed that a 52-card deck stays clearly out of order through the first five riffle shuffles and only gets close to random around the seventh. Overhand shuffling is far slower: it takes thousands of shuffles to mix a deck as well.</p>
</div>

<h2>The table that settled it</h2>
<p>Bayer and Diaconis measured how far a riffle-shuffled deck is from perfectly random, using a yardstick called <i>total variation distance</i>: 1 means the deck is still easy to tell apart from a random one, 0 means it's indistinguishable. Here are the numbers for a 52-card deck (we recomputed them from their formula):</p>
<div class="tbl-wrap"><table class="tbl">
<thead><tr><th>Riffle shuffles</th><th class="r">Distance from random</th><th></th></tr></thead>
<tbody>
{tvrows}</tbody></table></div>
<p>Nothing much happens for four shuffles, then the distance collapses. That sudden drop is known as the <b>cutoff phenomenon</b>, and it's why "seven" became the rule of thumb.</p>

<h2>Why riffles work and overhand shuffles don't</h2>
<p>A riffle shuffle cuts the deck in two and interleaves the halves, so every card can move a long way. After one riffle, though, the deck is made of just two "rising sequences": the cards from each half still appear in their old order relative to each other. Each riffle at most doubles the number of these sequences, and a well-mixed deck has around 26 of them. Magicians use leftover rising sequences for card tricks, which is a good reason to shuffle seven times before playing anyone who owns a top hat.</p>
<p>An overhand shuffle only slides small packets of cards from one hand to the other. Cards near each other tend to stay near each other, so it takes thousands of overhand shuffles to reach the same level of mixing. "Washing" the cards (smooshing them around on the table) also works well, if you keep at it for long enough.</p>

<h2>How computers shuffle: Fisher–Yates</h2>
<p>Computers don't riffle. The standard method is the <b>Fisher–Yates shuffle</b>: start at the last card, swap it with a randomly chosen card at or above it, move one card up, repeat. With a good random number generator, every one of the 52! orders is exactly equally likely, in one pass.</p>
<p>Two classic ways to get it wrong:</p>
<ul class="facts">
<li><b>The naive swap.</b> Swapping each card with <i>any</i> card in the deck (instead of only the ones not yet placed) looks fine but makes some orders more likely than others.</li>
<li><b>A tiny seed.</b> To be able to produce every deck, the random source needs at least 226 bits, because 2<sup>226</sup> is just above 52!. A generator seeded with 32 bits can only ever produce about 4.3 billion different decks, a fraction of roughly 5 × 10<sup>-59</sup> of them all. That's how the online poker shuffle mentioned in <a href="/same-deck-twice/">our same-deck-twice article</a> was cracked.</li>
</ul>

<h2>How The Impossible Shuffle shuffles</h2>
<p>On <a href="/">The Impossible Shuffle</a>, every shuffle is cooked from three public ingredients: the randomness of a <a href="https://www.drand.love/" rel="noopener">drand</a> round (published every 30 seconds by the League of Entropy, so nobody can know it in advance), the player's seat and a shuffle number. They go through SHA-256, and the 256-bit result drives Fisher–Yates. Since 2<sup>256</sup> is far bigger than 52!, every deck is possible, and the leftover bias is about 1 in 1.4 billion: too small to ever notice.</p>
<p>Best of all, anyone can <a href="/#verifyBox">replay any shuffle</a> and get the exact same deck. So if somebody ever does hit the Holy Grail, the whole world can check it.</p>
</article>
''' + cta('how-many-shuffles', 'Seven shuffles mix a deck. Matching the Holy Grail takes about 8 × 10⁶⁷. Humanity has started.') + more(path) + '</main>\n' + foot() + '</body>\n</html>\n'
write(path, html)

# ---------------------------------------------------------------- /math/ (hub)
path = '/math/'
desc = ('Why shuffling the same deck twice is (almost) impossible: 52 factorial, the odds of a repeat and how many '
        'shuffles a deck needs. Short, accurate and slightly unhinged.')
hub_schema = {"@context": "https://schema.org", "@graph": [
    {"@type": "CollectionPage", "@id": f"{SITE}/math/#page", "url": f"{SITE}/math/", "name": "The Mathematics Behind the Madness",
     "description": desc, "inLanguage": "en", "isPartOf": {"@id": f"{SITE}/#website"}, "publisher": {"@id": f"{SITE}/#org"},
     "hasPart": [{"@type": "Article", "headline": t, "url": SITE + p} for p, t in TITLES.items()]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "The Impossible Shuffle", "item": f"{SITE}/"},
        {"@type": "ListItem", "position": 2, "name": "The Mathematics Behind the Madness", "item": f"{SITE}/math/"}]},
    ORG]}
html = head(path, 'The Mathematics Behind the Madness | The Impossible Shuffle', desc,
            'The Mathematics Behind the Madness',
            'One deck, shuffled once. Humanity trying to shuffle it again. Here is the math that says we never will.',
            'The Mathematics Behind the Madness: 52 factorial and the odds of shuffling the same deck twice.', hub_schema)
html += top(path) + '<main id="main">\n' + '<p class="crumbs"><a href="/">Home</a> › The math behind the madness</p>\n' + f'''<h1>The Mathematics Behind the Madness</h1>
<p class="lede">A deck of 52 cards was shuffled once. Humanity is trying to shuffle that exact order again. Here's why that is the most hopeless mission on the internet, with the numbers to prove it.</p>

<div class="answer">
  <p class="k">The mission in numbers</p>
  <p>Possible orders of a deck: <b>52! ≈ 8.07 × 10<sup>67</sup></b></p>
  <p>Chance that one shuffle matches the Holy Grail: <b>1 in 52!</b></p>
  <p>Cards that land in their Grail spot, on average: <b>1</b></p>
  <p class="live" data-live hidden>Shuffles by humanity so far: <span data-live-total>…</span></p>
</div>

<div class="cards">
  <a class="card" href="/52-factorial/"><b>52 Factorial: How Big Is 52! Really?</b><span>The 68-digit number behind every shuffle, in coin flips, lottery wins and lifetimes of the universe. With a deck to shuffle.</span></a>
  <a class="card" href="/same-deck-twice/"><b>Has Anyone Ever Shuffled the Same Deck Twice?</b><span>The birthday problem, real repeats (new decks, lazy shuffles, a hacked poker site) and the odds of matching a few cards.</span></a>
  <a class="card" href="/how-many-shuffles/"><b>How Many Shuffles to Randomize a Deck?</b><span>Why seven riffle shuffles is the magic number, why overhand shuffling is hopeless and how computers do it right.</span></a>
  <a class="card" href="/#verifyBox"><b>Provably Fair: Check Any Shuffle</b><span>Every shuffle on the site has a public recipe. Replay anyone's shuffle and get the exact same deck.</span></a>
</div>

<h2>Why bother?</h2>
<p>Because "the odds are 1 in 8 × 10<sup>67</sup>" is impossible to feel until you've pressed the button a few hundred times and watched mathematics win every single round. The Impossible Shuffle is a joke, a probability experiment and a shared counter for all of humankind. It is also, technically, a game.</p>
''' + cta('math', 'Enough reading. The Holy Grail won\'t shuffle itself.') + '</main>\n' + foot() + LIVE_JS + '</body>\n</html>\n'
write(path, html)

# ---------------------------------------------------------------- /404.html
html = head('/404.html', 'Page Not Found | The Impossible Shuffle', 'This page has been shuffled out of existence.',
            'Page not found', 'This page has been shuffled out of existence.', 'The Impossible Shuffle',
            {"@context": "https://schema.org", "@type": "WebPage", "name": "Page not found"}, robots='noindex')
html += '''<body>
<div class="wrap">
<header class="top"><a class="brand" href="/">The Impossible Shuffle</a></header>
<main id="main" style="text-align:center;padding:3rem 0">
<h1>404: page shuffled out of existence</h1>
<p class="lede">The odds of finding this page were 1 in 52!. You found nothing. Mathematics remains undefeated.</p>
<p style="margin:2rem 0"><a class="btn" href="/">Shuffle the Impossible<small>Back to the mission</small></a></p>
<p><a href="/math/">Or read the mathematics behind the madness</a></p>
</main>
</div>
</body>
</html>
'''
write('/404.html', html)
