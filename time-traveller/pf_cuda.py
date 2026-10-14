"""The provably fair shuffle on a GPU (CUDA C through CuPy), plus a plain-Python reference.

Same recipe as pfDeckInto() in index.html and pf_deck() in supabase/leaderboard.sql:

    H = SHA-256(rand (32 bytes) || seat (16 bytes) || n (6 bytes, big-endian))
    deck = [0, 1, ..., 51]                      # card c = suit * 13 + rank (S H D C; A 2 .. 10 J Q K)
    for i in 0..50: r = 52 - i; swap(deck[i], deck[i + H mod r]); H = H div r

Speed tricks (none of them change a single card):
  * 32-bit arithmetic only for SHA-256 (rotations are single funnel-shift instructions).
  * Midstate: the first 12 SHA-256 rounds only see rand and seat, which are the same for
    every shuffle in a mission, so they are computed once on the host.
  * The 51 mixed-radix digits come out three at a time (H mod r(r-1)(r-2)), fully unrolled,
    so every division is by a compile-time constant (a multiply, not a real division), and
    limbs that are provably zero by then are skipped.
  * Position i never changes after step i, so matches are counted on the fly against the
    Holy Grail baked in as constants.

Each GPU thread handles shuffle numbers start, start + 1, ... (grid-stride) and keeps its
best as matches << 50 | (2^48 - 1 - n); one atomicMax per thread publishes it, so the
highest score wins and, on a tie, the earliest shuffle.

The same C source compiles with an ordinary C++ compiler (test_pf_cuda.py does that), so
the exact arithmetic the GPU runs is tested against the Python reference without a GPU.
"""
import hashlib

import numpy as np

SHA_K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]
SHA_IV = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]
MIDSTATE_ROUNDS = 12                               # rounds 0..11 only use message words 0..11 (rand, seat)

RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
CODES = [r + s for s in 'SHDC' for r in RANKS]
# The Holy Grail Sequence (must match GRAIL in index.html and grail() in the database).
GRAIL_CODES = ['5D', '2C', 'QD', 'JH', 'KH', '7H', 'KS', '3H', '10S', 'JD', 'JC', 'KD', '7S',
               '9S', '9H', '4H', 'AC', '3S', '8H', '2D', '10D', '5C', 'QH', 'QC', '4C', '9D',
               'AH', '3C', '10H', '3D', '9C', '6H', '6S', '8D', '5S', 'AD', '5H', 'KC', '10C',
               '4S', '6D', '4D', '8S', 'JS', 'QS', '7C', '2S', '2H', '7D', '6C', 'AS', '8C']
GRAIL = [CODES.index(c) for c in GRAIL_CODES]
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


def words(b: bytes) -> list:
    return [int.from_bytes(b[i:i + 4], 'big') for i in range(0, len(b), 4)]


def unpack_best(packed: int):
    """(matches, n) from a packed best, or (0, -1) if nothing was recorded."""
    if not packed:
        return 0, -1
    return packed >> 50, (N_LIMIT - 1) - (packed & ((1 << 50) - 1))


# ---------------------------------------------------------------------------
# Host-side precomputation: the midstate and the constant message words.
# ---------------------------------------------------------------------------
def _rotr(x, k):
    return ((x >> k) | (x << (32 - k))) & 0xFFFFFFFF


def params_for(rand: bytes, seat: bytes) -> np.ndarray:
    """uint32[24]: SHA-256 state after rounds 0..11, then message words 0..15 (12 and 13 depend on n)."""
    assert len(rand) == 32 and len(seat) == 16
    w = words(rand) + words(seat) + [0, 0, 0, 432]
    a, b, c, d, e, f, g, h = SHA_IV
    for i in range(MIDSTATE_ROUNDS):
        s1 = _rotr(e, 6) ^ _rotr(e, 11) ^ _rotr(e, 25)
        t1 = (h + s1 + ((e & f) ^ (~e & g)) + SHA_K[i] + w[i]) & 0xFFFFFFFF
        s0 = _rotr(a, 2) ^ _rotr(a, 13) ^ _rotr(a, 22)
        t2 = (s0 + ((a & b) ^ (a & c) ^ (b & c))) & 0xFFFFFFFF
        h, g, f, e, d, c, b, a = g, f, e, (d + t1) & 0xFFFFFFFF, c, b, a, (t1 + t2) & 0xFFFFFFFF
    return np.array([a, b, c, d, e, f, g, h] + w, dtype=np.uint32)


# ---------------------------------------------------------------------------
# The CUDA C source, generated once (so every divisor and Grail card is a constant).
# ---------------------------------------------------------------------------
def _digit_code() -> str:
    lines, maxv = [], (1 << 256) - 1
    for i in range(0, 51, 3):
        r = 52 - i
        P = r * (r - 1) * (r - 2)
        first = 8 - (maxv.bit_length() + 31) // 32       # limbs above this one are zero by now
        lines.append(f'  {{ /* digits {i}..{i + 2}: H mod {r}*{r - 1}*{r - 2} */ u64 rem = 0, cur, q;')
        for k in range(first, 8):
            lines.append(f'    cur = (rem << 32) | L{k}; q = cur / {P}ULL; rem = cur - q * {P}ULL; L{k} = (u32)q;')
        lines.append(f'    u32 x = (u32)rem, j, t;')
        lines.append(f'    j = {i} + x % {r}u; t = d[{i}]; d[{i}] = d[j]; d[j] = t; m += (d[{i}] == {GRAIL[i]});')
        lines.append(f'    x /= {r}u; j = {i + 1} + x % {r - 1}u; t = d[{i + 1}]; d[{i + 1}] = d[j]; d[j] = t; m += (d[{i + 1}] == {GRAIL[i + 1]});')
        lines.append(f'    j = {i + 2} + x / {r - 1}u; t = d[{i + 2}]; d[{i + 2}] = d[j]; d[j] = t; m += (d[{i + 2}] == {GRAIL[i + 2]}); }}')
        maxv //= P
    lines.append(f'  m += (d[51] == {GRAIL[51]});')
    return '\n'.join(lines)


def _sha_code() -> str:
    k = ', '.join(f'0x{x:08x}u' for x in SHA_K)
    iv = ', '.join(f'0x{x:08x}u' for x in SHA_IV)
    return f'#define SHA_K_LIST {k}\n#define SHA_IV_LIST {iv}\n'


KERNEL_SRC = r'''
typedef unsigned int u32;
typedef unsigned long long u64;
typedef unsigned char u8;
#ifdef __CUDACC__
#define DEV __device__ __forceinline__
#define ROTR(x, k) __funnelshift_r((x), (x), (k))
#define UNROLL _Pragma("unroll")
#else
#define DEV static inline
#define ROTR(x, k) (((x) >> (k)) | ((x) << (32 - (k))))
#define UNROLL
#endif
''' + _sha_code() + r'''
/* Writes the deck for shuffle n into d and returns its matches with the Holy Grail.
   p: params_for() = midstate (8 words) then message words 0..15. */
DEV u32 pf_deck(const u32 *p, u64 n, u8 *d) {
  const u32 K[64] = { SHA_K_LIST };
  const u32 IV[8] = { SHA_IV_LIST };
  u32 W[64];
  UNROLL for (int i = 0; i < 16; i++) W[i] = p[8 + i];
  W[12] = (u32)(n >> 16);                       /* n as 6 big-endian bytes, then the 0x80 pad byte */
  W[13] = ((u32)(n & 0xFFFFu) << 16) | 0x8000u;
  UNROLL for (int i = 16; i < 64; i++) {
    u32 x = W[i - 15], y = W[i - 2];
    W[i] = W[i - 16] + (ROTR(x, 7) ^ ROTR(x, 18) ^ (x >> 3)) + W[i - 7] + (ROTR(y, 17) ^ ROTR(y, 19) ^ (y >> 10));
  }
  u32 a = p[0], b = p[1], c = p[2], e = p[4], f = p[5], g = p[6], h = p[7], dd = p[3];
  UNROLL for (int i = 12; i < 64; i++) {        /* rounds 0..11 are in the midstate */
    u32 t1 = h + (ROTR(e, 6) ^ ROTR(e, 11) ^ ROTR(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + W[i];
    u32 t2 = (ROTR(a, 2) ^ ROTR(a, 13) ^ ROTR(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
    h = g; g = f; f = e; e = dd + t1; dd = c; c = b; b = a; a = t1 + t2;
  }
  u32 L0 = a + IV[0], L1 = b + IV[1], L2 = c + IV[2], L3 = dd + IV[3];
  u32 L4 = e + IV[4], L5 = f + IV[5], L6 = g + IV[6], L7 = h + IV[7];
  UNROLL for (int i = 0; i < 52; i++) d[i] = (u8)i;
  u32 m = 0;
''' + _digit_code() + r'''
  return m;
}

#ifdef __CUDACC__
extern "C" __global__ void shuffle_kernel(const u32 *__restrict__ params, u64 start, u64 count, u64 *best_out) {
  u32 p[24];
  UNROLL for (int i = 0; i < 24; i++) p[i] = params[i];
  u8 d[52];
  u64 best = 0;
  for (u64 i = (u64)blockIdx.x * blockDim.x + threadIdx.x; i < count; i += (u64)gridDim.x * blockDim.x) {
    u64 n = start + i;
    u64 packed = ((u64)pf_deck(p, n, d) << 50) | ((1ULL << 48) - 1 - n);
    if (packed > best) best = packed;
  }
  if (best) atomicMax(best_out, best);
}

extern "C" __global__ void decks_kernel(const u32 *__restrict__ params, u64 start, u32 count, u8 *out) {
  u32 i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= count) return;
  u32 p[24];
  UNROLL for (int k = 0; k < 24; k++) p[k] = params[k];
  u8 d[52];
  pf_deck(p, start + i, d);
  for (int k = 0; k < 52; k++) out[(u64)i * 52 + k] = d[k];
}
#endif
'''


class Shuffler:
    """Compiles the kernel once (CuPy + NVRTC) and runs batches of shuffles for one rand + seat."""

    def __init__(self, rand: bytes, seat: bytes, blocks: int = 0, threads: int = 256):
        import cupy as cp
        self.cp = cp
        self.params = cp.asarray(params_for(rand, seat))
        mod = cp.RawModule(code=KERNEL_SRC, options=('--std=c++14',))
        self.k_shuffle = mod.get_function('shuffle_kernel')
        self.k_decks = mod.get_function('decks_kernel')
        self.best = cp.zeros(1, dtype=cp.uint64)
        self.sms = cp.cuda.Device().attributes['MultiProcessorCount']
        self.blocks, self.threads = blocks or self.sms * 16, threads

    def run(self, start: int, count: int):
        """Shuffles count recipes from start; returns (best matches, its n) for this batch."""
        cp = self.cp
        self.best.fill(0)
        self.k_shuffle((self.blocks,), (self.threads,), (self.params, np.uint64(start), np.uint64(count), self.best))
        cp.cuda.Device().synchronize()
        return unpack_best(int(self.best.get()[0]))

    def decks(self, start: int, count: int) -> np.ndarray:
        cp = self.cp
        out = cp.zeros(count * 52, dtype=cp.uint8)
        self.k_decks(((count + 127) // 128,), (128,), (self.params, np.uint64(start), np.uint32(count), out))
        cp.cuda.Device().synchronize()
        return out.get().reshape(count, 52)

    def tune(self, seconds_each: float = 1.0) -> float:
        """Tries a few launch shapes and keeps the fastest; returns its rate (shuffles a second)."""
        import time
        best = (0.0, self.blocks, self.threads)
        self.run(0, 1 << 22)                                   # compile and warm up
        for threads in (128, 256, 512):
            for per_sm in (4, 8, 16, 32):
                self.blocks, self.threads = self.sms * per_sm, threads
                count, t0 = 1 << 26, time.time()
                done = 0
                while time.time() - t0 < seconds_each:
                    self.run(done, count)
                    done += count
                rate = done / (time.time() - t0)
                if rate > best[0]:
                    best = (rate, self.blocks, self.threads)
        _, self.blocks, self.threads = best
        return best[0]
