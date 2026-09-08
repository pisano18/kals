#!/usr/bin/env python3
# VERSION: 2026-09-08-f6a
"""pinfeat_regime.py -- NEW FILE, READ-ONLY. FEATURE FAMILY 6: time, regime
and cross-asset conditions as predictors of pin's FLIP risk.

THE DECISION BEING CONDITIONED
  pin buys a near-certain binary in the last seconds of a 15 minute crypto
  market. Settlement is the mean of 60 one-second index prints over
  [close-60, close-1]. With r prints unpublished and locked sum L,
  mu = (L + r*spot)/60 and the model prices
      fair = Phi((mu - K_eff)/sd),  sd = sigma*sqrt(var_factor(r,[1.0])),
      K_eff = floor_strike - 0.5*10^-round_digits.
  Today the gate is fixed: fair >= 0.98 (buy YES) or <= 0.02 (buy NO).
  The per-trade floor is  fee + p_flip*price/(1-p_flip), so p_flip -- the
  probability the favoured side loses -- is the only free quantity. This file
  asks whether p_flip depends on conditions the model ignores.

THE DECISION CELL (declared before any number was looked at)
  For each settled market, scan tau = 20 down to 3 and take the FIRST tau at
  which the gate opens, i.e. the EARLIEST wall-clock second in pin's window.
  pin takes the earliest qualifying second, never the best one. side = yes if
  fair >= 0.98 else no. flip = 1 if that side lost. One decision per market,
  <= 9 per close; every significance figure clusters on CLOSE.

FEATURES (all declared up front, buckets fixed before measurement)
  a  hour of close, UTC and New York (ET = UTC-4); opportunities and flip rate
  b  day of week, weekend vs weekday
  c  market-wide vol regime: xvol(s) = mean over the 9 indices of
     sigma_i(s)/spot_i(s); regime = xvol(now) / trailing-24h mean of xvol on a
     60 s grid ending strictly before `now`. Own-index ratio reported beside it
     as the obvious confound.
  d  cross-asset: BRTI jump z = max |1 s BRTI diff| over the last 10 s divided
     by BRTI's trailing-300 s sigma, applied to ALT trades only; plus a
     whole-tape |diff| lead-lag cross-correlation BRTI(t) vs alt(t+k).
  e  round-number proximity of the strike, at 1% and 10% of price magnitude
  f  travel during the window (spot-K in bp), realised range over
     [close-900, now] against its own expectation, and strike crossings

NO PEEKING -- mechanically enforced, not asserted
  1. Every index second any feature reads is <= now = close - tau < close.
     --verify recomputes every feature for a random sample of decisions
     through an accessor that RAISES on any read at second >= close, and
     compares the guarded values to the fast path element by element.
  2. The predictive comparison is walk-forward on CLOSE: decisions are grouped
     by close in time order; a close is predicted from counters holding only
     strictly earlier closes, then folded in. The scorer tracks the highest
     close folded in and raises if it is >= the close being predicted.
  3. Two deliberate leaks are scored in the same tables so the reader can see
     what a leak looks like here: LEAK-IS (bucket rates fitted on the whole
     sample, including the row being scored) and LEAK-FUT (a feature read from
     index seconds AFTER the close). If an honest column scored like those it
     would be a leak.

SELF-TEST WORLDS
  W1 nothing planted: feature is noise. Walk-forward must not beat the
     constant model; LEAK-IS must appear to.
  W2 effect planted: bucket flip rates 1% / 8%. Walk-forward must find it.
  W3 clairvoyant feature (bucket == outcome): walk-forward log-loss must
     collapse. A harness that cannot see a planted leak is not evidence.
  W4 causality: the scorer must raise when fed a close out of order.
"""
import argparse
import array
import calendar
import glob
import gzip
import json
import math
import os
import pickle
import random
import sys
import time
import zlib
from collections import defaultdict
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)          # repo modules FIRST -- kals-work shadows
import idxload                                              # noqa: E402
from engine import var_factor, N_AVG                        # noqa: E402

ND = NormalDist()
SCRATCH = r"C:\Users\Joe\AppData\Local\Temp\kals-f6"
SETTLED = r"C:\Users\Joe\AppData\Local\Temp\kals-emp\settled.json"
TICKDIR = r"C:\kals\kalshi_data\ticker"

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
    "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
}
IDS = sorted(set(SERIES_TO_INDEX.values()))
PIN = 0.98
TAU_LO, TAU_HI = 3, 20
SIGMA_WIN = 300
SIGMA_MIN_DIFFS = 20
NAN = float("nan")


# ===========================================================================
# quote extraction from the ticker channel (streamed, one file at a time)
# ===========================================================================
def _tick_fields(line):
    i = line.find('"market_ticker":"')
    if i < 0:
        return None
    i += 17
    j = line.find('"', i)
    tk = line[i:j]

    def num(key):
        a = line.find(key, j)
        if a < 0:
            return None
        a += len(key)
        b = line.find('"', a)
        try:
            return float(line[a:b])
        except ValueError:
            return None
    bid = num('"yes_bid_dollars":"')
    ask = num('"yes_ask_dollars":"')
    bsz = num('"yes_bid_size_fp":"')
    asz = num('"yes_ask_size_fp":"')
    t = line.find('"ts":', j)
    if t < 0:
        return None
    u = t + 5
    w = u
    while w < len(line) and line[w].isdigit():
        w += 1
    try:
        ts = int(line[u:w])
    except ValueError:
        return None
    return tk, ts, bid, ask, bsz, asz


def extract_quotes(markets, out_path, verbose=True):
    """Ticker rows in [close-300, close] for every settled market.

    Streams one hour file at a time and keeps nothing else. Newest hour file
    of a live channel is a truncated gzip: EOFError, zlib.error and OSError
    are caught per file and whatever parsed is kept.
    """
    want = {m["ticker"]: m["close"] for m in markets}
    keep = defaultdict(list)
    files = sorted(glob.glob(os.path.join(TICKDIR, "2026*.jsonl.gz")))
    bad = []
    t0 = time.time()
    seen = 0
    for fi, f in enumerate(files):
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    if '"market_ticker":"KX' not in line:
                        continue
                    r = _tick_fields(line)
                    if r is None:
                        continue
                    tk, ts, bid, ask, bsz, asz = r
                    c = want.get(tk)
                    if c is None:
                        continue
                    if ts < c - 300 or ts > c:
                        continue
                    seen += 1
                    keep[tk].append((ts, bid, ask, bsz, asz))
        except (EOFError, zlib.error, OSError) as e:
            bad.append((os.path.basename(f), type(e).__name__))
        if verbose and fi % 40 == 0:
            print(f"    {fi+1}/{len(files)} {os.path.basename(f)} "
                  f"{seen:,} kept  {time.time()-t0:.0f}s", flush=True)
    for tk in keep:
        keep[tk].sort()
    if verbose:
        print(f"  ticker: {len(files)} files, {seen:,} quote rows for "
              f"{len(keep):,} markets in {time.time()-t0:.0f}s")
        if bad:
            print(f"  {len(bad)} damaged/live file(s): "
                  + ", ".join(f"{a} ({b})" for a, b in bad[:4]))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as fh:
        pickle.dump(dict(keep), fh, protocol=4)
    return dict(keep)


def load_markets():
    S = json.load(open(SETTLED, encoding="utf-8"))
    out = []
    for s, rows in S.items():
        if s not in SERIES_TO_INDEX:
            continue
        for r in rows:
            if r["result"] not in ("yes", "no"):
                continue
            out.append(dict(ticker=r["ticker"], series=s, close=int(r["close"]),
                            K=float(r["strike"]), rd=int(r["rd"]),
                            won=1 if r["result"] == "yes" else 0))
    out.sort(key=lambda m: (m["close"], m["series"]))
    return out


if __name__ == "__main__" and "--extract" in sys.argv:
    _mk = load_markets()
    print(f"  {len(_mk):,} settled markets")
    extract_quotes(_mk, os.path.join(SCRATCH, "quotes.pkl"))
    raise SystemExit(0)


# ===========================================================================
# per-index grid: spot, trailing sigma, 60 s relative-vol grid
# ===========================================================================
def sigma_array(v, n):
    """Trailing-300 s sample SD of consecutive 1 s diffs ending at each second.

    Identical construction to pincal/pinrun's sigma_from: at least 20 usable
    diffs, sample (n-1) denominator. Prefix sums so it is O(n)."""
    cn = array.array("i", [0]) * (n + 1)
    cs = array.array("d", [0.0]) * (n + 1)
    cq = array.array("d", [0.0]) * (n + 1)
    pn = 0
    ps = pq = 0.0
    for i in range(1, n):
        cn[i], cs[i], cq[i] = pn, ps, pq
        a, b = v[i - 1], v[i]
        if a == a and b == b:
            dd = b - a
            pn += 1
            ps += dd
            pq += dd * dd
    cn[n], cs[n], cq[n] = pn, ps, pq
    sig = array.array("d", [NAN]) * n
    for i in range(SIGMA_WIN, n):
        lo, hi = i - SIGMA_WIN + 1, i
        k = cn[hi + 1] - cn[lo]
        if k < SIGMA_MIN_DIFFS:
            continue
        s = cs[hi + 1] - cs[lo]
        q = cq[hi + 1] - cq[lo]
        var = (q - s * s / k) / (k - 1)
        if var > 0:
            sig[i] = math.sqrt(var)
    return sig


class Grid:
    """One index on a contiguous second grid, plus a 60 s relative-vol grid.

    rv[k] = sigma(base+60k) / value(base+60k), the per-second relative
    volatility, sampled once a minute. rvs/rvn are prefix sums over rv so a
    trailing mean is O(1). Everything the trailing mean touches is at second
    base+60k <= now-60, strictly before the decision second."""
    __slots__ = ("iid", "base", "n", "v", "sig", "nk", "rv", "rvs", "rvn")

    def __init__(self, dense, sig):
        self.iid, self.base, self.n = dense.iid, dense.base, dense.n
        self.v, self.sig = dense.v, sig
        self.nk = self.n // 60
        rv = array.array("d", [NAN]) * self.nk
        for k in range(self.nk):
            i = 60 * k
            g, x = sig[i], self.v[i]
            if g == g and x == x and x > 0:
                rv[k] = g / x
        self.rv = rv
        rvs = array.array("d", [0.0]) * (self.nk + 1)
        rvn = array.array("i", [0]) * (self.nk + 1)
        s = 0.0
        c = 0
        for k in range(self.nk):
            rvs[k], rvn[k] = s, c
            x = rv[k]
            if x == x:
                s += x
                c += 1
        rvs[self.nk], rvn[self.nk] = s, c
        self.rvs, self.rvn = rvs, rvn

    # --- O(1) reads -----------------------------------------------------
    def val(self, s):
        i = s - self.base
        if i < 0 or i >= self.n:
            return None
        x = self.v[i]
        return None if x != x else x

    def sigma(self, s):
        i = s - self.base
        if i < 0 or i >= self.n:
            return None
        x = self.sig[i]
        return None if x != x else x

    def span(self, a, b):
        lo = max(a - self.base, 0)
        hi = min(b - self.base, self.n - 1)
        if hi < lo:
            return [], b - a + 1
        got = [x for x in self.v[lo:hi + 1] if x == x]
        return got, b - a + 1

    def relvol(self, s):
        g, x = self.sigma(s), self.val(s)
        if g is None or x is None or x <= 0:
            return None
        return g / x

    def trail_relvol(self, now, hours=24):
        """Mean rv over the `hours` before `now`, on the 60 s grid.

        k_hi is the newest grid point whose second is <= now-60, so no second
        at or after `now` is ever read."""
        k_hi = (now - self.base) // 60 - 1
        k_lo = max(0, k_hi - 60 * hours + 1)
        if k_hi < k_lo or k_hi >= self.nk:
            return None, 0
        c = self.rvn[k_hi + 1] - self.rvn[k_lo]
        if c < 60:
            return None, c
        return (self.rvs[k_hi + 1] - self.rvs[k_lo]) / c, c


def build_grids(hours=None, verbose=True, use_cache=True):
    dense = idxload.load(IDS, hours=hours, verbose=verbose, use_cache=use_cache)
    any_d = dense[IDS[0]]
    key = f"grids_{any_d.base}_{any_d.n}.pkl"
    cp = os.path.join(SCRATCH, key)
    if use_cache and os.path.exists(cp):
        with open(cp, "rb") as fh:
            sigs = pickle.load(fh)
        if verbose:
            print(f"  sigma cache hit {key}")
    else:
        sigs = {}
        for iid in IDS:
            t0 = time.time()
            sigs[iid] = sigma_array(dense[iid].v, dense[iid].n)
            if verbose:
                print(f"    sigma {iid:<14} {time.time()-t0:.0f}s", flush=True)
        if use_cache:
            os.makedirs(SCRATCH, exist_ok=True)
            with open(cp, "wb") as fh:
                pickle.dump(sigs, fh, protocol=4)
    grids = {iid: Grid(dense[iid], sigs[iid]) for iid in IDS}
    del sigs
    return grids


class XVol:
    """Cross-sectional market-wide relative volatility on the 60 s grid."""

    def __init__(self, grids):
        g0 = grids[IDS[0]]
        self.base, self.nk = g0.base, g0.nk
        xv = array.array("d", [NAN]) * self.nk
        for k in range(self.nk):
            s = 0.0
            c = 0
            for iid in IDS:
                x = grids[iid].rv[k]
                if x == x:
                    s += x
                    c += 1
            if c >= 5:
                xv[k] = s / c
        self.xv = xv
        xs = array.array("d", [0.0]) * (self.nk + 1)
        xn = array.array("i", [0]) * (self.nk + 1)
        s = 0.0
        c = 0
        for k in range(self.nk):
            xs[k], xn[k] = s, c
            x = xv[k]
            if x == x:
                s += x
                c += 1
        xs[self.nk], xn[self.nk] = s, c
        self.xs, self.xn = xs, xn

    def trail(self, now, hours=24):
        k_hi = (now - self.base) // 60 - 1
        k_lo = max(0, k_hi - 60 * hours + 1)
        if k_hi < k_lo or k_hi >= self.nk:
            return None, 0
        c = self.xn[k_hi + 1] - self.xn[k_lo]
        if c < 60:
            return None, c
        return (self.xs[k_hi + 1] - self.xs[k_lo]) / c, c


def xvol_now(grids, now):
    """Cross-sectional mean relative vol at the decision second itself."""
    s = 0.0
    c = 0
    for iid in IDS:
        x = grids[iid].relvol(now)
        if x is not None:
            s += x
            c += 1
    if c < 5:
        return None, c
    return s / c, c

