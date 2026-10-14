"""Tests for the GPU shuffle, without a GPU.

    python test_pf_cuda.py

1. The kernel's C source (the exact arithmetic the GPU runs) compiled with the system C++
   compiler, against the Python reference: thousands of recipes, edge-case shuffle numbers.
2. Known answers shared with index.html's self-test and the database.
3. If NVIDIA's NVRTC is installed (pip install nvidia-cuda-nvrtc-cu12 cuda-python), the
   kernel is also compiled for the H100 (compute_90), so a typo can't reach a paid mission.
"""
import os
import random
import shutil
import subprocess
import tempfile

import pf_cuda as pc

KNOWN_R, KNOWN_S = bytes(range(32)), bytes(range(16))
KNOWN = {0: '5D 10H QD 8C 5H 3C 6D QC 4H 9S', 123456789: 'KS 8S 7D 9C JS 2S 7C 8D KH JD'}

HARNESS = r'''
#include <cstdio>
int main() {
  unsigned p[24]; unsigned long long n; unsigned cnt; unsigned char d[52];
  while (true) {
    for (int i = 0; i < 24; i++) if (scanf("%x", &p[i]) != 1) return 0;
    if (scanf("%llu %u", &n, &cnt) != 2) return 1;
    for (unsigned k = 0; k < cnt; k++) {
      unsigned m = pf_deck(p, n + k, d);
      printf("%u", m);
      for (int i = 0; i < 52; i++) printf(" %u", d[i]);
      printf("\n");
    }
  }
}
'''


def cpu_binary():
    cxx = shutil.which('g++') or shutil.which('clang++')
    assert cxx, 'needs a C++ compiler (g++ or clang++)'
    tmp = tempfile.mkdtemp()
    src, exe = os.path.join(tmp, 'pf.cpp'), os.path.join(tmp, 'pf')
    with open(src, 'w') as f:
        f.write(pc.KERNEL_SRC + HARNESS)
    subprocess.run([cxx, '-O2', '-o', exe, src], check=True)
    return exe


def run_cpu(exe, jobs):
    """jobs: [(rand, seat, n, count)] → list of (matches, deck) per shuffle, in order."""
    lines = []
    for rand, seat, n, cnt in jobs:
        lines.append(' '.join(f'{w:x}' for w in pc.params_for(rand, seat)) + f' {n} {cnt}')
    out = subprocess.run([exe], input='\n'.join(lines) + '\n', capture_output=True, text=True, check=True).stdout
    rows = [list(map(int, ln.split())) for ln in out.strip().splitlines()]
    return [(r[0], r[1:]) for r in rows]


def test_known_answers():
    for n, want in KNOWN.items():
        assert ' '.join(pc.CODES[c] for c in pc.deck_ref(KNOWN_R, KNOWN_S, n)[:10]) == want


def test_kernel_source_matches_reference():
    exe = cpu_binary()
    rng = random.Random(52)
    jobs, expect = [], []
    for k in range(1500):
        R, S = os.urandom(32), os.urandom(16)
        n = rng.choice([0, 1, 65535, 65536, 2**32 - 1, 2**32, 2**47, 2**48 - 3, rng.randrange(2**48 - 2)])
        jobs.append((R, S, n, 2))
        expect += [pc.deck_ref(R, S, n), pc.deck_ref(R, S, n + 1)]
    jobs.append((KNOWN_R, KNOWN_S, 123456789, 1))
    expect.append(pc.deck_ref(KNOWN_R, KNOWN_S, 123456789))
    got = run_cpu(exe, jobs)
    assert len(got) == len(expect)
    for (m, deck), want in zip(got, expect):
        assert deck == want
        assert m == pc.matches_ref(want)
    assert ' '.join(pc.CODES[c] for c in got[-1][1][:10]) == KNOWN[123456789]
    # a long run from one recipe, as the GPU does it (and its best, earliest on a tie)
    R, S = os.urandom(32), os.urandom(16)
    run = run_cpu(exe, [(R, S, 10**12, 20000)])
    ms = [m for m, _ in run]
    assert len(ms) == 20000
    for i in range(0, 20000, 97):
        assert run[i][1] == pc.deck_ref(R, S, 10**12 + i)
    best = max(ms)
    n_best = 10**12 + ms.index(best)
    packed = max((m << 50) | ((1 << 48) - 1 - (10**12 + i)) for i, m in enumerate(ms))
    assert pc.unpack_best(packed) == (best, n_best)
    assert pc.matches_ref(pc.deck_ref(R, S, n_best)) == best


def test_compiles_for_h100():
    try:
        from cuda.bindings import nvrtc
    except ImportError:
        print('   (skipped: no NVRTC here)')
        return
    err, prog = nvrtc.nvrtcCreateProgram(pc.KERNEL_SRC.encode(), b'pf.cu', 0, [], [])
    assert err == nvrtc.nvrtcResult.NVRTC_SUCCESS
    err, = nvrtc.nvrtcCompileProgram(prog, 2, [b'--gpu-architecture=compute_90', b'--std=c++14'])
    if err != nvrtc.nvrtcResult.NVRTC_SUCCESS:
        _, size = nvrtc.nvrtcGetProgramLogSize(prog)
        log = b' ' * size
        nvrtc.nvrtcGetProgramLog(prog, log)
        raise AssertionError(log.decode())
    _, size = nvrtc.nvrtcGetPTXSize(prog)
    ptx = b' ' * size
    nvrtc.nvrtcGetPTX(prog, ptx)
    ptx = ptx.decode()
    assert '.entry shuffle_kernel' in ptx and '.entry decks_kernel' in ptx
    assert 'div.u64' not in ptx and 'rem.u64' not in ptx, 'a real 64-bit division slipped in'
    with open(os.path.join(tempfile.gettempdir(), 'pf_cuda.ptx'), 'w') as f:
        f.write(ptx)


def test_packing():
    assert pc.unpack_best(0) == (0, -1)
    assert pc.unpack_best((52 << 50) | ((1 << 48) - 1 - 12345)) == (52, 12345)


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok ', name)
