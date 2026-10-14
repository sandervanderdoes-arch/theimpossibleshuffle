"""Tests for the GPU shuffle, without a GPU.

    NUMBA_ENABLE_CUDASIM=1 python test_pf_cuda.py

1. The deck function compiled with numba.njit (same typed code the GPU runs) vs the Python reference.
2. The kernels in Numba's CUDA simulator: decks, best match, packing, tie-breaking.
3. Known answers shared with index.html's self-test and the database.
"""
import os
import random

import numpy as np

import pf_cuda as pc

KNOWN_R, KNOWN_S = bytes(range(32)), bytes(range(16))
KNOWN = {0: '5D 10H QD 8C 5H 3C 6D QC 4H 9S', 123456789: 'KS 8S 7D 9C JS 2S 7C 8D KH JD'}


def test_known_answers():
    for n, want in KNOWN.items():
        assert ' '.join(pc.CODES[c] for c in pc.deck_ref(KNOWN_R, KNOWN_S, n)[:10]) == want


def test_cpu_compiled_matches_reference():
    deck_fn = pc.pf_deck_cpu_factory()
    W, L, deck = np.zeros(64, np.uint64), np.zeros(8, np.uint64), np.zeros(52, np.uint8)
    rng = random.Random(52)
    for k in range(400):
        R, S = os.urandom(32), os.urandom(16)
        n = rng.choice([0, 1, 65535, 65536, 2**32 - 1, 2**32, 2**48 - 1, rng.randrange(2**48)])
        deck_fn(pc.words(R), pc.words(S), np.uint64(n), pc.SHA_K, pc.SHA_IV, W, L, deck)
        assert list(deck) == pc.deck_ref(R, S, n), (R.hex(), S.hex(), n)
    deck_fn(pc.words(KNOWN_R), pc.words(KNOWN_S), np.uint64(123456789), pc.SHA_K, pc.SHA_IV, W, L, deck)
    assert ' '.join(pc.CODES[c] for c in deck[:10]) == KNOWN[123456789]


def test_kernels_in_simulator():
    R, S = os.urandom(32), os.urandom(16)
    sh = pc.Shuffler(R, S, blocks=2, threads=32)
    start = 2**40 + 17
    decks = sh.decks(start, 40)
    for i in range(40):
        assert list(decks[i]) == pc.deck_ref(R, S, start + i)
    count = 300
    m, n = sh.run(start, count)
    ms = [pc.matches_ref(pc.deck_ref(R, S, start + i)) for i in range(count)]
    best = max(ms)
    assert m == best and n == start + ms.index(best), (m, n, best)   # earliest shuffle wins a tie


def test_packing():
    assert pc.unpack_best(0) == (0, -1)
    packed = (52 << 50) | ((1 << 48) - 1 - 12345)
    assert pc.unpack_best(packed) == (52, 12345)


if __name__ == '__main__':
    assert os.environ.get('NUMBA_ENABLE_CUDASIM') == '1', 'run with NUMBA_ENABLE_CUDASIM=1 (or on a GPU, remove this line)'
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok ', name)
