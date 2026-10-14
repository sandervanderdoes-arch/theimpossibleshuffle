"""The provably fair shuffle on a GPU (Numba CUDA), plus a plain-Python reference.

Same recipe as pfDeckInto() in index.html and pf_deck() in supabase/leaderboard.sql:

    H = SHA-256(rand (32 bytes) || seat (16 bytes) || n (6 bytes, big-endian))
    deck = [0, 1, ..., 51]                      # card c = suit * 13 + rank (S H D C; A 2 .. 10 J Q K)
    for i in 0..50: r = 52 - i; swap(deck[i], deck[i + H mod r]); H = H div r

Each GPU thread handles shuffle numbers n = start, start + 1, ... (grid-stride), counts the
matches against the Holy Grail, and keeps its best. One atomic max per thread at the end
publishes the block's best as a packed number: matches << 50 | (2^48 - 1 - n), so the
highest score wins and, on a tie, the earliest shuffle.

Test without a GPU: NUMBA_ENABLE_CUDASIM=1 python test_pf_cuda.py
"""
import hashlib

import numpy as np
from numba import cuda, uint8, uint64

SHA_K = np.array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
], dtype=np.uint32)
SHA_IV = np.array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19], dtype=np.uint32)

RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
CODES = [r + s for s in 'SHDC' for r in RANKS]
# The Holy Grail Sequence (must match GRAIL in index.html and grail() in the database).
GRAIL_CODES = ['5D', '2C', 'QD', 'JH', 'KH', '7H', 'KS', '3H', '10S', 'JD', 'JC', 'KD', '7S',
               '9S', '9H', '4H', 'AC', '3S', '8H', '2D', '10D', '5C', 'QH', 'QC', '4C', '9D',
               'AH', '3C', '10H', '3D', '9C', '6H', '6S', '8D', '5S', 'AD', '5H', 'KC', '10C',
               '4S', '6D', '4D', '8S', 'JS', 'QS', '7C', '2S', '2H', '7D', '6C', 'AS', '8C']
GRAIL = np.array([CODES.index(c) for c in GRAIL_CODES], dtype=np.uint8)
N_LIMIT = 1 << 48            # n is 6 bytes


# ---------------------------------------------------------------------------
# Reference (plain Python), used by the tests and to double-check every reported best.
# ---------------------------------------------------------------------------
def deck_ref(rand: bytes, seat: bytes, n: int) -> list:
    x = int.from_bytes(hashlib.sha256(rand + seat + n.to_bytes(6, 'big')).digest(), 'big')
    d = list(range(52))
    for i in range(51):
        r = 52 - i
        j = i + x % r
        x //= r
        d[i], d[j] = d[j], d[i]
    return d


def matches_ref(deck) -> int:
    return sum(1 for a, b in zip(deck, GRAIL) if a == b)


def words(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype='>u4').astype(np.uint32)


# ---------------------------------------------------------------------------
# GPU. The deck function is written once and compiled twice: as a CUDA device function, and
# with numba.njit on the CPU, so the tests exercise exactly the typed code the GPU runs.
# Everything is uint64 on purpose (Numba turns int64/uint64 mixes into floats).
# ---------------------------------------------------------------------------
U32 = np.uint64(0xFFFFFFFF)


def _make_deck(jit):
    @jit
    def rotr(x, k):
        return ((x >> np.uint64(k)) | (x << np.uint64(32 - k))) & U32

    @jit
    def pf_deck(R, S, n, K, IV, W, L, deck):
        """Writes the shuffle for recipe (R, S, n) into deck. W: 64, L: 8 (uint64 scratch)."""
        for i in range(8):
            W[i] = np.uint64(R[i])
        for i in range(4):
            W[8 + i] = np.uint64(S[i])
        W[12] = (n >> np.uint64(16)) & U32         # n as 6 big-endian bytes, then the 0x80 pad byte
        W[13] = ((n & np.uint64(0xFFFF)) << np.uint64(16)) | np.uint64(0x8000)
        W[14] = np.uint64(0)
        W[15] = np.uint64(432)                     # 54 bytes = 432 bits
        for i in range(16, 64):
            x = W[i - 15]
            y = W[i - 2]
            s0 = rotr(x, 7) ^ rotr(x, 18) ^ (x >> np.uint64(3))
            s1 = rotr(y, 17) ^ rotr(y, 19) ^ (y >> np.uint64(10))
            W[i] = (W[i - 16] + s0 + W[i - 7] + s1) & U32
        a = np.uint64(IV[0]); b = np.uint64(IV[1]); c = np.uint64(IV[2]); d = np.uint64(IV[3])
        e = np.uint64(IV[4]); f = np.uint64(IV[5]); g = np.uint64(IV[6]); h = np.uint64(IV[7])
        for i in range(64):
            S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)
            ch = (e & f) ^ ((e ^ U32) & g)
            t1 = (h + S1 + ch + np.uint64(K[i]) + W[i]) & U32
            S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)
            mj = (a & b) ^ (a & c) ^ (b & c)
            t2 = (S0 + mj) & U32
            h = g
            g = f
            f = e
            e = (d + t1) & U32
            d = c
            c = b
            b = a
            a = (t1 + t2) & U32
        L[0] = (a + np.uint64(IV[0])) & U32; L[1] = (b + np.uint64(IV[1])) & U32
        L[2] = (c + np.uint64(IV[2])) & U32; L[3] = (d + np.uint64(IV[3])) & U32
        L[4] = (e + np.uint64(IV[4])) & U32; L[5] = (f + np.uint64(IV[5])) & U32
        L[6] = (g + np.uint64(IV[6])) & U32; L[7] = (h + np.uint64(IV[7])) & U32
        for i in range(52):
            deck[i] = i
        top = 0
        # Three mixed-radix digits per long division: r(r-1)(r-2) < 2^21, so rem * 2^32 + limb fits 64 bits.
        for i in range(0, 51, 3):
            r = np.uint64(52 - i)
            P = r * (r - np.uint64(1)) * (r - np.uint64(2))
            rem = np.uint64(0)
            for k in range(top, 8):
                cur = (rem << np.uint64(32)) | L[k]
                q = cur // P
                rem = cur - q * P
                L[k] = q
            while top < 7 and L[top] == np.uint64(0):
                top += 1
            j = i + np.int64(rem % r)
            t = deck[i]; deck[i] = deck[j]; deck[j] = t
            rem = rem // r
            j = i + 1 + np.int64(rem % (r - np.uint64(1)))
            t = deck[i + 1]; deck[i + 1] = deck[j]; deck[j] = t
            j = i + 2 + np.int64(rem // (r - np.uint64(1)))
            t = deck[i + 2]; deck[i + 2] = deck[j]; deck[j] = t

    return pf_deck


pf_deck_dev = _make_deck(cuda.jit(device=True))


def pf_deck_cpu_factory():
    """The same deck function compiled for the CPU (tests only)."""
    from numba import njit
    return _make_deck(njit)


@cuda.jit
def shuffle_kernel(R, S, grail, K, IV, start, count, best_out):
    """Shuffles n = start .. start + count - 1; best_out[0] gets the packed best (atomic max)."""
    W = cuda.local.array(64, uint64)
    L = cuda.local.array(8, uint64)
    deck = cuda.local.array(52, uint8)
    G = cuda.shared.array(52, uint8)
    for p in range(cuda.threadIdx.x, 52, cuda.blockDim.x):
        G[p] = grail[p]
    cuda.syncthreads()
    i = uint64(cuda.grid(1))
    stride = uint64(cuda.gridsize(1))
    best = uint64(0)
    while i < count:
        n = start + i
        pf_deck_dev(R, S, n, K, IV, W, L, deck)
        m = uint64(0)
        for p in range(52):
            if deck[p] == G[p]:
                m += uint64(1)
        packed = (m << uint64(50)) | (uint64(N_LIMIT - 1) - n)
        if packed > best:
            best = packed
        i += stride
    if best > 0:
        cuda.atomic.max(best_out, 0, best)


@cuda.jit
def decks_kernel(R, S, K, IV, start, out):
    """Test helper: writes the decks for n = start .. start + len(out) - 1."""
    W = cuda.local.array(64, uint64)
    L = cuda.local.array(8, uint64)
    deck = cuda.local.array(52, uint8)
    i = cuda.grid(1)
    if i < out.shape[0]:
        pf_deck_dev(R, S, uint64(start + i), K, IV, W, L, deck)
        for p in range(52):
            out[i, p] = deck[p]


def unpack_best(packed: int):
    """(matches, n) from a packed best, or (0, -1) if nothing was recorded."""
    if not packed:
        return 0, -1
    return packed >> 50, (N_LIMIT - 1) - (packed & ((1 << 50) - 1))


class Shuffler:
    """Keeps the constants on the device and runs batches."""

    def __init__(self, rand: bytes, seat: bytes, blocks: int = 0, threads: int = 256):
        self.R = cuda.to_device(words(rand))
        self.S = cuda.to_device(words(seat))
        self.K = cuda.to_device(SHA_K)
        self.IV = cuda.to_device(SHA_IV)
        self.G = cuda.to_device(GRAIL)
        self.best = cuda.to_device(np.zeros(1, dtype=np.uint64))
        if not blocks:
            try:
                blocks = cuda.get_current_device().MULTIPROCESSOR_COUNT * 8
            except Exception:                       # simulator
                blocks = 2
        self.blocks, self.threads = blocks, threads

    def run(self, start: int, count: int):
        """Shuffles count recipes from start; returns (best matches, its n) for this batch."""
        self.best.copy_to_device(np.zeros(1, dtype=np.uint64))
        shuffle_kernel[self.blocks, self.threads](self.R, self.S, self.G, self.K, self.IV, np.uint64(start), np.uint64(count), self.best)
        cuda.synchronize()
        return unpack_best(int(self.best.copy_to_host()[0]))

    def decks(self, start: int, count: int) -> np.ndarray:
        out = cuda.to_device(np.zeros((count, 52), dtype=np.uint8))
        decks_kernel[(count + 63) // 64, 64](self.R, self.S, self.K, self.IV, np.uint64(start), out)
        cuda.synchronize()
        return out.copy_to_host()
