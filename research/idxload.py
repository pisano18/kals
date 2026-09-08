#!/usr/bin/env python3
# VERSION: 2026-09-08-idx1
"""idxload.py -- NEW FILE. Dense, cached loader for cfbenchmarks_value.

Why a new loader rather than pincal.load_index_hours: that one builds a
{index_id: {second: value}} dict, which for 14 days x 9 indices is ~12M dict
entries (>1.5 GB) and cannot be sliced by second in O(1). This one builds one
array('d') per index over a contiguous second grid with NaN in the gaps, which
is 9 MB per index and indexes in O(1). Nothing else changes: the same lines are
read and the same (time, value) pairs come out.

Truncation discipline: the newest hour file of a live channel is a gzip still
being written. EOFError, zlib.error and OSError are all caught per file and the
partial content is kept, as everything else in this repo does.

Parsing is by string search rather than json.loads -- 12.8M lines is ~2 minutes
of json.loads and ~25 s this way. verify_parse() below checks the fast path
against json.loads on a real file, line for line, and is run by --selftest.
"""
import array
import calendar
import glob
import gzip
import json
import math
import os
import pickle
import sys
import time
import zlib

IDXDIR = r"C:\kals\kalshi_data\cfbenchmarks_value"
CACHE = r"C:\Users\Joe\AppData\Local\Temp\kals-emp"
NAN = float("nan")


def _fast_fields(line):
    """(index_id, sec, value) or None. Mirrors json.loads(line) exactly for
    the cfbenchmarks_value shape; verified line-for-line by verify_parse()."""
    i = line.find('"index_id":"')
    if i < 0:
        return None
    i += 12
    j = line.find('"', i)
    iid = line[i:j]
    t = line.find('\\"time\\":', j)
    if t < 0:
        return None
    t += 9
    u = line.find(',', t)
    v = line.find('\\"value\\":\\"', u)
    if v < 0:
        return None
    v += 12
    w = line.find('\\"', v)
    try:
        return iid, int(line[t:u]) // 1000, float(line[v:w])
    except ValueError:
        return None


def verify_parse(path, limit=200000):
    """Fast path vs json.loads on a real file. Returns (checked, mismatches)."""
    n = bad = 0
    with gzip.open(path, "rt") as fh:
        for line in fh:
            if '"cfbenchmarks_value"' not in line:
                continue
            f = _fast_fields(line)
            d = json.loads(line)
            m = d.get("msg") or {}
            dd = json.loads(m["data"])
            slow = (m["index_id"], int(dd["time"]) // 1000, float(dd["value"]))
            n += 1
            if f != slow:
                bad += 1
                if bad < 4:
                    print(f"    MISMATCH fast={f} slow={slow}")
            if n >= limit:
                break
    return n, bad


def hour_of(path):
    return calendar.timegm(time.strptime(os.path.basename(path)[:11],
                                         "%Y%m%dT%H"))


class Dense:
    """One index on a contiguous second grid. v[s] is NaN where no print."""
    __slots__ = ("iid", "base", "n", "v", "hi_used")

    def __init__(self, iid, base, n):
        self.iid, self.base, self.n = iid, base, n
        self.v = array.array("d", [NAN]) * n
        self.hi_used = -1                     # no-lookahead watermark

    def get(self, s):
        i = s - self.base
        if i < 0 or i >= self.n:
            return None
        if s > self.hi_used:
            self.hi_used = s
        x = self.v[i]
        return None if x != x else x

    def span(self, a, b):
        """values in [a, b] that exist, and how many seconds were asked for."""
        if b > self.hi_used:
            self.hi_used = b
        lo = max(a - self.base, 0)
        hi = min(b - self.base, self.n - 1)
        if hi < lo:
            return [], b - a + 1
        got = [x for x in self.v[lo:hi + 1] if x == x]
        return got, b - a + 1


def load(indices, hours=None, verbose=True, use_cache=True):
    """{iid: Dense}. `hours` limits to the newest N hour files."""
    files = sorted(glob.glob(os.path.join(IDXDIR, "2026*.jsonl.gz")))
    if hours:
        files = files[-hours:]
    if not files:
        raise SystemExit("no index files")
    key = f"idx_{len(files)}_{os.path.basename(files[0])}_" \
          f"{os.path.basename(files[-1])}_{'-'.join(sorted(indices))}.pkl"
    cp = os.path.join(CACHE, key)
    if use_cache and os.path.exists(cp):
        if verbose:
            print(f"  index cache hit {os.path.basename(cp)}")
        with open(cp, "rb") as fh:
            return pickle.load(fh)
    base = hour_of(files[0])
    n = hour_of(files[-1]) + 3600 - base
    want = set(indices)
    out = {i: Dense(i, base, n) for i in indices}
    bad = []
    kept = 0
    for f in files:
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    if '"cfbenchmarks_value"' not in line:
                        continue
                    r = _fast_fields(line)
                    if r is None:
                        continue
                    iid, sec, val = r
                    if iid not in want:
                        continue
                    d = out[iid]
                    k = sec - base
                    if 0 <= k < n:
                        d.v[k] = val
                        kept += 1
        except (EOFError, zlib.error, OSError) as e:
            bad.append((os.path.basename(f), type(e).__name__))
    if verbose:
        print(f"  {len(files)} hour files "
              f"{os.path.basename(files[0])} .. {os.path.basename(files[-1])}")
        if bad:
            print(f"  {len(bad)} damaged/live file(s), kept what parsed: "
                  + ", ".join(f"{a} ({b})" for a, b in bad[:4]))
        for i in indices:
            d = out[i]
            c = sum(1 for x in d.v if x == x)
            print(f"    {i:<14} {c:>9,} prints over {n:,} s "
                  f"({100.0*c/n:.1f}% coverage)")
    for d in out.values():
        d.hi_used = -1
    if use_cache:
        os.makedirs(CACHE, exist_ok=True)
        with open(cp, "wb") as fh:
            pickle.dump(out, fh, protocol=4)
        if verbose:
            print(f"  cached -> {cp}")
    return out


def selftest():
    print("SELF-TEST -- idxload")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    files = sorted(glob.glob(os.path.join(IDXDIR, "2026*.jsonl.gz")))
    ck(len(files) > 10, f"index files present ({len(files)})")
    if files:
        n, badn = verify_parse(files[len(files) // 2])
        ck(n > 1000 and badn == 0,
           f"fast parse == json.loads on {n:,} real lines ({badn} mismatches)")
    d = Dense("X", 1000, 10)
    d.v[3] = 5.0
    ck(d.get(1003) == 5.0 and d.get(1004) is None, "Dense get/gap")
    got, want = d.span(1000, 1009)
    ck(got == [5.0] and want == 10, "Dense span reports asked-for length")
    ck(d.hi_used == 1009, "watermark records the highest second touched")
    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    return not fails


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(0 if selftest() else 1)
    ii = ["BRTI", "ETHUSD_RTI", "SOLUSD_RTI"]
    t0 = time.time()
    load(ii, hours=6)
    print(f"  {time.time()-t0:.1f}s")
