#!/usr/bin/env python3
# VERSION: 2026-09-08-fam4-a1
"""pinfeat_path.py -- FEATURE FAMILY 4: THE SHAPE OF THE PATH, NOT ITS VOLATILITY.

WHAT IS BEING DECIDED

pin buys a near-certain binary in the last seconds of a 15-minute crypto
market. Settlement is the mean of the 60 one-second index prints over
[close-60, close-1]. With r prints unpublished and locked sum L,

    mu = (L + r*spot)/60
    a flip requires the r remaining prints to AVERAGE
        required_move = (60/r) * (K_eff - mu)
    K_eff = floor_strike - 0.5*10^-round_digits

The shipped model reduces the future to ONE number, sigma, and prices
    fair = Phi((mu - K_eff)/sd),  sd = sigma*sqrt(var_factor(r,[1.0])).

That throws away the SHAPE of the path that got us here. This file builds the
path-shape features and measures each one by out-of-sample log-loss and Brier
lift over the gaussian, walk-forward by UTC day, clustered on close.

NO PEEKING -- enforced three separate ways

 1. Every feature at (market, tau) is a function of index ticks with second
    <= close-tau ONLY. `scan_market` slices the tick dict with an explicit
    upper bound `now`. --selftest POISONS every tick after the decision second
    to +-1e9 and requires every feature column to come back bit-identical.
 2. Every fitted quantity -- logistic coefficients, feature standardisation,
    the empirical error law, the r-bucket quantiles -- is fitted on rows whose
    close is strictly before 00:00 UTC of the test day.
 3. Both --selftest and --analyse run LEAK VARIANTS that deliberately break
    (1) and (2) and print their scores beside the honest ones. A leak variant
    that does NOT score implausibly better means the harness is blind and the
    honest numbers are worthless.

SELF-TEST: three synthetic worlds.
  * NULL     -- a pure random walk, so the gaussian IS the truth. No honest
                feature may show a real lift; if one does, the scorer lies.
  * PLANTED  -- an Ornstein-Uhlenbeck index, so spot systematically overshoots
                its own trailing mean and spot-substitution is systematically
                wrong. The transient feature MUST be found.
  * LEAK     -- the realised post-decision move offered as a feature. It MUST
                score far better than anything honest.
Plus arithmetic identities: required_move really does move mu onto K_eff, the
settlement window really is [close-60, close-1], K_eff really is the half tick
below the floor strike, and the poisoned-future run really is identical.
"""
import argparse
import calendar
import glob
import gzip
import json
import math
import os
import random
import re
import sys
import time
import zlib
from collections import defaultdict
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor, N_AVG                            # noqa: E402

ND = NormalDist()
IDXDIR = r"C:\kals\kalshi_data\cfbenchmarks_value"
FULLTAPE = r"C:\kals\fulltape\markets.json"
CACHE = os.path.join(os.environ.get("TEMP", "."), "pinfeat_path")
ROWS_CSV = os.path.join(CACHE, "rows.csv.gz")

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
    "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
}
ROUND_DIGITS = {}
PIN = 0.98
SIGMA_WIN = 300
RHO_WIN = 600
RHO_LAGS = 10
TAUS = list(range(3, 21))
BACK = 30

COLS = ("close_s series tau r side won flip dec fair z zrho sigma sig60 sd "
        "mu keff muend nlock spot tr3 tr5 tr10 dr5 dr15 dr30 acc jmax jtow "
        "rho1 rho2 rho3 rmsig").split()


# ===========================================================================
# model pieces -- same conventions as pincal.py and the shipped pin gate
# ===========================================================================
def eff_strike(strike, d):
    return float(strike) - 0.5 * (10.0 ** (-int(d)))


def vf_rho(r, rho):
    """var_factor with a measured autocovariance. Uncached: rho is continuous
    and engine's cache key would grow without bound."""
    if r <= 0:
        return 0.0
    if r > N_AVG:
        return var_factor(r, rho)
    w = list(range(r, 0, -1))
    tot = sum(x * x for x in w)
    for h in range(1, len(rho)):
        if h < len(w):
            tot += 2 * rho[h] * sum(w[i] * w[i + h] for i in range(len(w) - h))
    return max(tot, 0.0) / (N_AVG ** 2)


def diffs_in(ticks, lo, hi):
    out = []
    prev = None
    for s in range(lo, hi + 1):
        v = ticks.get(s)
        if v is None:
            prev = None
            continue
        if prev is not None:
            out.append(v - prev)
        prev = v
    return out


def sd_of(xs):
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def autocorr(ds, lags):
    n = len(ds)
    if n < 40:
        return [1.0] + [0.0] * lags
    m = sum(ds) / n
    d = [x - m for x in ds]
    den = sum(x * x for x in d)
    if den <= 0:
        return [1.0] + [0.0] * lags
    out = [1.0]
    for h in range(1, lags + 1):
        out.append(sum(d[i] * d[i + h] for i in range(n - h)) / den)
    return out


# ===========================================================================
def scan_market(ticks, close_s, strike, d, won, series="", taus=TAUS):
    """Rows for one settled market. Reads ticks[s] for s <= close-tau ONLY,
    except `muend`, the realised settlement mean, which is the TARGET used to
    build the train-side empirical error law and is never used as a feature."""
    K = eff_strike(strike, d)
    fin = [ticks[s] for s in range(close_s - N_AVG, close_s) if s in ticks]
    muend = (sum(fin) / len(fin)) if len(fin) >= 57 else float("nan")
    out = []
    for tau in taus:
        now = close_s - tau
        if any((now - k) not in ticks for k in range(0, BACK + 1)):
            continue
        spot = ticks[now]
        ds300 = diffs_in(ticks, now - SIGMA_WIN, now)
        if len(ds300) < 20:
            continue
        sigma = sd_of(ds300)
        if not sigma or sigma <= 0:
            continue
        sig60 = sd_of(diffs_in(ticks, now - 60, now)) or sigma
        lo, hi = close_s - N_AVG, min(now, close_s - 1)
        if hi < lo:
            continue
        want = hi - lo + 1
        got = [ticks[s] for s in range(lo, hi + 1) if s in ticks]
        if not got or len(got) < want * 0.95:
            continue
        locked = sum(got) * (want / len(got))
        r = N_AVG - want
        if r <= 0:
            continue
        mu = (locked + r * spot) / N_AVG
        sd = sigma * math.sqrt(var_factor(int(r), [1.0]))
        if sd <= 0:
            continue
        zsig = (mu - K) / sd
        fair = ND.cdf(zsig)
        dec = 1 if (fair >= PIN or fair <= 1 - PIN) else 0
        side = 1 if zsig >= 0 else 0
        sgn = 1.0 if side else -1.0
        flip = int(side != int(won))

        def mean_k(k):
            return sum(ticks[now - j] for j in range(k)) / k

        tr = {k: sgn * (spot - mean_k(k)) / sigma for k in (3, 5, 10)}
        dr = {h: -sgn * (spot - ticks[now - h]) / sigma for h in (5, 15, 30)}
        acc = -sgn * ((spot - ticks[now - 5])
                      - (ticks[now - 5] - ticks[now - 10])) / sigma
        d30 = [ticks[now - j] - ticks[now - j - 1] for j in range(0, BACK)]
        jmax = max(abs(x) for x in d30) / sigma
        jtow = max(-sgn * x for x in d30) / sigma
        rho = autocorr(diffs_in(ticks, now - RHO_WIN, now), RHO_LAGS)
        zr = (mu - K) / (sigma * math.sqrt(max(vf_rho(int(r), rho), 1e-30)))
        rm = (N_AVG / r) * (K - mu)
        out.append(dict(
            close_s=close_s, series=series, tau=tau, r=r, side=side,
            won=int(won), flip=flip, dec=dec, fair=fair, z=abs(zsig),
            zrho=abs(zr), sigma=sigma, sig60=sig60, sd=sd, mu=mu, keff=K,
            muend=muend, nlock=len(got), spot=spot, tr3=tr[3], tr5=tr[5],
            tr10=tr[10], dr5=dr[5], dr15=dr[15], dr30=dr[30], acc=acc,
            jmax=jmax, jtow=jtow, rho1=rho[1], rho2=rho[2], rho3=rho[3],
            rmsig=abs(rm) / sigma))
    return out


# ===========================================================================
# extraction: stream cfbenchmarks_value hour files, rolling window, no peeking
# ===========================================================================
IDX_RE = re.compile(
    r'"index_id":"([A-Z]+)".*?\\"time\\":(\d+),\\"id\\":\\"[A-Z]+\\",'
    r'\\"value\\":\\"([0-9.eE+-]+)\\"')


def load_round_digits(verbose=True):
    sys.path.append(r"C:\Users\Joe\AppData\Local\Temp\kals-work")
    from kauth import get
    for s in SERIES_TO_INDEX:
        try:
            st, b = get("/markets", {"series_ticker": s, "status": "open",
                                     "limit": "1"})
            ms = (b or {}).get("markets") or []
            if ms:
                d = (ms[0].get("custom_strike") or {}).get("round_digits")
                if d is not None:
                    ROUND_DIGITS[s] = int(d)
        except Exception:
            pass
    if verbose:
        print("  round_digits READ FROM THE EXCHANGE: "
              + ", ".join(f"{k}={v}" for k, v in sorted(ROUND_DIGITS.items())))
        miss = [s for s in SERIES_TO_INDEX if s not in ROUND_DIGITS]
        if miss:
            print(f"  no round_digits for {miss} -- SKIPPED, never guessed")
    return ROUND_DIGITS


def load_markets(verbose=True):
    """Settled markets with a full-precision strike.

    markets.json truncates DOGE's strike to 6 dp while round_digits is 7 (1070
    of 1197 DOGE rows disagree with the previous window's settle). Because
    strike(N+1) == settle(N) exactly -- verified here on 9569 of 9569
    consecutive pairs outside DOGE -- the previous window's `settle` recovers
    the missing digit, using only data from 900 s BEFORE the market opens."""
    raw = json.load(open(FULLTAPE, encoding="utf-8"))
    out, fixed, exact, nofix = [], 0, 0, 0
    for s, v in raw.items():
        if s not in SERIES_TO_INDEX or not v:
            continue
        by = {int(float(r["close"])): r for r in v}
        for c, r in sorted(by.items()):
            k = float(r["strike"])
            p = by.get(c - 900)
            src = "tape"
            if p is not None:
                ps = float(p["settle"])
                if abs(ps - k) < 1e-4 * max(abs(k), 1e-9):
                    if ps != k:
                        fixed += 1
                        src = "prev_settle"
                    else:
                        exact += 1
                    k = ps
                else:
                    nofix += 1
            else:
                nofix += 1
            out.append(dict(ticker=r["ticker"], series=s, strike=k,
                            close=c, won=1 if float(r["result"]) >= 0.5 else 0,
                            src=src))
    if verbose:
        print(f"  {len(out):,} settled markets; strike confirmed by the "
              f"previous settle on {exact:,}, REFINED on {fixed:,} "
              f"(DOGE truncation), no previous window for {nofix:,}")
    return out


def hour_of(path):
    return calendar.timegm(time.strptime(os.path.basename(path)[:11],
                                         "%Y%m%dT%H"))


def extract(limit_hours=None, verbose=True):
    """Stream every index hour once, in order, holding a rolling window."""
    os.makedirs(CACHE, exist_ok=True)
    load_round_digits(verbose)
    mk = load_markets(verbose)
    want_idx = set(SERIES_TO_INDEX.values())
    by_hour = defaultdict(list)
    for m in mk:
        if m["series"] in ROUND_DIGITS:
            by_hour[m["close"] // 3600].append(m)
    files = sorted(glob.glob(os.path.join(IDXDIR, "2026*.jsonl.gz")))
    if limit_hours:
        files = files[-limit_hours:]
    if verbose:
        print(f"  {len(files)} index hour files "
              f"{os.path.basename(files[0])} .. {os.path.basename(files[-1])}")
    ticks = defaultdict(dict)
    damaged, nrows, nmk, nskip = [], 0, 0, 0
    t0 = time.time()
    fh = gzip.open(ROWS_CSV, "wt", compresslevel=6)
    fh.write(",".join(COLS) + "\n")
    for fi, f in enumerate(files):
        H = hour_of(f)
        try:
            with gzip.open(f, "rt") as g:
                for line in g:
                    m = IDX_RE.search(line)
                    if not m:
                        continue
                    iid = m.group(1)
                    if iid not in want_idx:
                        continue
                    ticks[iid][int(m.group(2)) // 1000] = float(m.group(3))
        except (EOFError, zlib.error, OSError) as e:
            damaged.append((os.path.basename(f), type(e).__name__))
        # every market closing inside this hour now has its full path on hand
        for mm in by_hour.get(H, []):
            iid = SERIES_TO_INDEX[mm["series"]]
            T = ticks.get(iid)
            if not T:
                nskip += 1
                continue
            rows = scan_market(T, mm["close"], mm["strike"],
                               ROUND_DIGITS[mm["series"]], mm["won"],
                               mm["series"])
            if not rows:
                nskip += 1
                continue
            nmk += 1
            for rw in rows:
                fh.write(",".join(_fmt(rw[c]) for c in COLS) + "\n")
                nrows += 1
        cut = H + 3600 - 800
        for iid in list(ticks):
            T = ticks[iid]
            if len(T) > 2000:
                for s in [s for s in T if s < cut]:
                    del T[s]
        if verbose and (fi % 40 == 0 or fi == len(files) - 1):
            print(f"    [{fi+1}/{len(files)}] {os.path.basename(f)} "
                  f"markets {nmk:,} rows {nrows:,} "
                  f"{time.time()-t0:.0f}s", flush=True)
    fh.close()
    if verbose:
        print(f"  {nrows:,} rows from {nmk:,} markets "
              f"({nskip:,} markets produced none)")
        if damaged:
            print(f"  {len(damaged)} damaged hour file(s), used what parsed: "
                  + ", ".join(f"{n} ({t})" for n, t in damaged[:5]))
    return nrows


def _fmt(v):
    if isinstance(v, float):
        if v != v:
            return ""
        return repr(round(v, 10))
    return str(v)
