#!/usr/bin/env python3
"""IMPROVEMENT 4 -- Kalshi publishes its own rolling 60s mean; use it.

WHAT THIS MEASURES
------------------
Every `cfbenchmarks_value` message carries, alongside the raw 1-second index
print, an `avg_60s_data` object:

    "avg_60s_data": {"value": "79422.76683333", "window_size": 60,
                     "window_start_ts_ms": t-60000,
                     "window_end_ts_exclusive": t}

Confirmed against the tape: it is a TRUE ROLLING mean over the 60 prints at
seconds [t-60, t-1], republished every second, NOT a snapshot of the last
settlement window.  `last_60s_windowed_average_15min` appears ONLY on the
quarter-hour message and its VALUE equals the rolling mean one second LATER
-- window [t-59, t] -- even though its own declared bounds say [t-60, t).
That declared/actual mismatch is measured here, not assumed.

Because settlement is the mean of the prints at [close-60, close-1], the
message stamped exactly `time == close` carries the settlement value itself.
That is a post-hoc check, never an input to a decision.

THE IDENTITY THAT MAKES THIS USEFUL BEFORE THE CLOSE
----------------------------------------------------
At decision time `now = close - tau` the newest message we hold is at t*.
Its avg60 covers [t*-60, t*-1].  The locked part of the settlement window is
[close-60, t*].  Those overlap in all but the oldest seconds, so

    LOCKED_exch = 60*avg60(t*) - sum(raw[t*-60 .. close-61]) + raw(t*)

is EXACT and depends on only tau+1 raw prints of our own, against the
58..41 that the direct reconstruction needs at tau in [3,20].  One intact
message repairs up to 60 dropped ones behind it, because the exchange has
already summed them.

BASELINE (frozen, not re-tuned here) -- research/pinrun.py:
    locked window [close-60, min(now, close-1)], truncated to the newest
    print actually held; interior gaps filled from the NEAREST print held;
    REFUSE if fewer than 95% of the window seconds are present.
    research/pincal.py instead RESCALES: sum(got) * (want/len(got)).
    mu = (locked + r*spot)/60 ; sd = sigma*sqrt(var_factor(r,[1.0]))
    K_eff = floor_strike - 0.5*10^-round_digits
    fair >= 0.98 buy YES, <= 0.02 buy NO, tau in [3,20], one trade per close.

NO LOOKAHEAD
------------
The decision instant at tau is defined as the RECEIPT of the index print
stamped `close - tau`.  Every estimator sees only messages whose exchange
`time` is <= that second, and the run AUDITS that definition against the
collector's own receipt clock: it counts decision points at which a message
stamped LATER than the decision second had already been received by then.
That count must be 0, otherwise indexing by `time` would be smuggling the
future in.  The receipt-latency distribution is printed alongside.

Ground truth -- the settlement and the true locked sum -- is derived from the
message stamped at `close`, which is strictly after every decision instant,
and it is computed only AFTER each estimator has already answered.  No
estimator reads it, and nothing in this file is fitted: the identity has no
free parameters, sigma is the shipped trailing-300s estimator, and the gate
thresholds (0.98/0.02, tau in [3,20]) are the frozen baseline, copied, not
re-tuned.  The exact strike comes from strike(N+1)==settle(N), i.e. from the
PREVIOUS close, which is 15 minutes old when the market opens.

`--leak` scores two deliberately peeking variants beside the honest ones:
`leak_settle` reads the exchange's mean at the close itself, and `leak5`
reads the rolling mean 5 seconds into the future.  If the honest rows ever
matched their scores, the honest rows would be leaking too.

SELF-TEST
---------
Plants a world where avg60 is exactly consistent with the raws, then punches
gaps: the exchange estimator must stay EXACT while the direct reconstruction
must break, and in a gap-free world both must be exact and the improvement
must measure as zero.  A leaking variant must be caught scoring impossibly
well.
"""
import argparse
import bisect
import glob
import gzip
import json
import math
import os
import random
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from engine import var_factor, N_AVG          # noqa: E402
from replay import SERIES_TO_INDEX            # noqa: E402
import gzsalvage                              # noqa: E402

SIGMA_WIN = 300
PIN_HI = 0.98
PIN_LO = 0.02
TAU_LO, TAU_HI = 3, 20
COVERAGE = 0.95

# round_digits.  Supplied by the operator as READ from custom_strike, and
# independently corroborated from the decimal places actually present in the
# fulltape settle values (max observed == the value used).
ROUND_DIGITS = {
    "KXBTC15M": 2, "KXETH15M": 2, "KXBNB15M": 2,
    "KXSOL15M": 4, "KXXRP15M": 4, "KXZEC15M": 4,
    "KXHYPE15M": 4, "KXNEAR15M": 4,
    "KXDOGE15M": 7,
}


def phi(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


# ------------------------------------------------------------------ loaders
def _keep_second(sec):
    """Only seconds within 330 s before a quarter-hour close are needed."""
    return ((-sec) % 900) <= 330


def read_hour(path, keep=_keep_second):
    """Return [(iid, sec, raw, avg60, ws, we, l15, rx_ms), ...] for one hour.

    The newest file of a live channel is a truncated gzip; EOFError and
    zlib.error both mean 'stop here and keep what was parsed'.
    """
    out = []
    if True:
        # gzsalvage, not gzip.open: the collector appends a second gzip
        # member after a mid-hour restart and a plain reader then recovers
        # ZERO lines from the whole hour.  Counting those hours as 'gaps'
        # would have made this whole measurement an artefact of the reader.
        try:
            lines = gzsalvage.iter_lines(path)
        except (EOFError, zlib.error, OSError):
            return out
        try:
            for line in lines:
                    i = line.find('"received_at":')
                    if i < 0:
                        continue
                    j = i + 14
                    k = j
                    while k < len(line) and line[k].isdigit():
                        k += 1
                    if k == j:
                        continue
                    sec0 = int(line[j:k]) // 1000
                    if not (keep(sec0) or keep(sec0 - 1) or keep(sec0 + 1)):
                        continue
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    m = d.get("msg") or {}
                    iid = m.get("index_id")
                    if not iid:
                        continue
                    try:
                        inner = json.loads(m.get("data") or "null")
                    except ValueError:
                        continue
                    if not inner or inner.get("value") is None:
                        continue
                    t = inner.get("time")
                    if t is None:
                        continue
                    sec = int(t) // 1000
                    if not keep(sec):
                        continue
                    a = m.get("avg_60s_data") or {}
                    l = m.get("last_60s_windowed_average_15min") or {}
                    try:
                        raw = float(inner["value"])
                    except (TypeError, ValueError):
                        continue
                    av = a.get("value")
                    try:
                        av = float(av) if av is not None else None
                    except (TypeError, ValueError):
                        av = None
                    lv = l.get("value")
                    try:
                        lv = float(lv) if lv is not None else None
                    except (TypeError, ValueError):
                        lv = None
                    lws = l.get("window_size")
                    out.append((iid, sec, raw, av,
                                a.get("window_start_ts_ms"),
                                a.get("window_end_ts_exclusive"),
                                lv, d.get("_rx_ms"), lws))
        except (EOFError, zlib.error, OSError):
            pass
    return out


def load_markets(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    ms = []
    for series, lst in d.items():
        if series not in SERIES_TO_INDEX or series not in ROUND_DIGITS:
            continue
        for m in lst:
            c = m.get("close")
            if c is None or m.get("result") is None or m.get("settle") is None:
                continue
            ms.append({"series": series, "close": int(c),
                       "strike": m.get("strike"), "settle": float(m["settle"]),
                       "result": float(m["result"]),
                       "ticker": m.get("ticker")})
    ms.sort(key=lambda x: (x["close"], x["series"]))
    return ms


def exact_strikes(markets):
    """strike(N+1) == settle(N) exactly.  fulltape `strike` is truncated to
    the display precision, `settle` is not, so recover the exact strike from
    the PREVIOUS close in the same series -- data that is 15 minutes old at
    the moment the market opens, so this is causal."""
    by = {}
    for m in markets:
        by.setdefault(m["series"], {})[m["close"]] = m
    agree = tot = 0
    for m in markets:
        prev = by[m["series"]].get(m["close"] - 900)
        m["strike_exact"] = None
        if prev is not None:
            m["strike_exact"] = prev["settle"]
            if m["strike"] is not None:
                tot += 1
                d = ROUND_DIGITS[m["series"]]
                if abs(round(prev["settle"], d) - round(float(m["strike"]), d)) \
                        <= 1.5 * (10.0 ** -d):
                    agree += 1
    return agree, tot


# --------------------------------------------------------------- estimators
def sigma_from(ticks, now_s, win=SIGMA_WIN):
    secs = [s for s in range(now_s - win, now_s + 1) if s in ticks]
    diffs = [ticks[secs[i]] - ticks[secs[i - 1]]
             for i in range(1, len(secs)) if secs[i] - secs[i - 1] == 1]
    if len(diffs) < 20:
        return None
    mu = sum(diffs) / len(diffs)
    return math.sqrt(sum((x - mu) ** 2 for x in diffs) / (len(diffs) - 1))


def locked_direct(ticks, close_s, now_s, mode="nearest"):
    """The shipped reconstruction.  mode='nearest' is pinrun.py, mode='scale'
    is pincal.py.  Returns (locked, r, t_star, want, got_n) or None."""
    lo = close_s - N_AVG
    hi = min(now_s, close_s - 1)
    if hi < lo:
        return None
    have = [s for s in range(lo, hi + 1) if s in ticks]
    if not have:
        return None
    t_star = have[-1]
    want = t_star - lo + 1
    got = {s: ticks[s] for s in have}
    if len(got) < want * COVERAGE:
        return None
    r = N_AVG - want
    if len(got) == want:
        return sum(got.values()), r, t_star, want, len(got)
    if mode == "scale":
        return sum(got.values()) * (want / len(got)), r, t_star, want, len(got)
    keys = sorted(got)
    total = 0.0
    for s in range(lo, t_star + 1):
        v = got.get(s)
        if v is None:
            i = bisect.bisect_left(keys, s)
            cand = [k for k in (keys[i] if i < len(keys) else None,
                                keys[i - 1] if i > 0 else None)
                    if k is not None]
            v = got[min(cand, key=lambda k: (abs(k - s), k))]
        total += v
    return total, r, t_star, want, len(got)


def locked_exchange(ticks, avgs, close_s, now_s):
    """LOCKED_exch = 60*avg60(t*) - sum(raw[t*-60 .. close-61]) + raw(t*).

    Needs only the tau*+1 raw prints from BEFORE the settlement window plus
    the print at t* itself.  Returns (locked, r, t_star, n_raw) or None."""
    lo = close_s - N_AVG
    hi = min(now_s, close_s - 1)
    if hi < lo:
        return None
    have = [s for s in range(lo, hi + 1) if s in ticks and avgs.get(s) is not None]
    if not have:
        return None
    t_star = have[-1]
    pre = list(range(t_star - N_AVG, lo))
    if any(s not in ticks for s in pre):
        return None
    locked = N_AVG * avgs[t_star] - sum(ticks[s] for s in pre) + ticks[t_star]
    want = t_star - lo + 1
    return locked, N_AVG - want, t_star, len(pre) + 1


def locked_l15(ticks, l15, close_s, now_s):
    """THE DIRECT READ.  last_60s_windowed_average_15min at second t is the
    exchange own running mean of the prints at [close-59, t], with
    window_size counting 1..60 through the final minute.  (Its DECLARED
    bounds are shifted one second early -- measured, see M0 -- so the value,
    not the bounds, is what is used, and the shape is verified per point
    rather than assumed.)

    The settlement window is [close-60, close-1], one second earlier, so

        LOCKED = raw(close-60) + window_size * value

    needs exactly ONE raw print of our own.  Returns (locked, r, t_star, 1).
    """
    lo = close_s - N_AVG
    hi = min(now_s, close_s - 1)
    if hi < lo or lo not in ticks:
        return None
    have = [x for x in range(lo + 1, hi + 1) if x in l15]
    if not have:
        return None
    t_star = have[-1]
    v, ws = l15[t_star]
    if v is None or ws is None:
        return None
    if int(ws) != t_star - lo:
        return None
    locked = ticks[lo] + int(ws) * v
    want = t_star - lo + 1
    return locked, N_AVG - want, t_star, 1


def locked_best(ticks, avgs, l15, close_s, now_s):
    """The deployable cascade: the exchange partial average if it is there,
    else the rolling-mean identity, else the shipped reconstruction."""
    v = locked_l15(ticks, l15, close_s, now_s)
    if v is not None:
        return v
    v = locked_exchange(ticks, avgs, close_s, now_s)
    if v is not None:
        return v
    return locked_direct(ticks, close_s, now_s, "nearest")


def true_locked(ticks, avgs, close_s, t_star):
    """Ground truth, computed only AFTER a decision is recorded: the
    exchange's own settlement sum minus the prints unpublished at t*."""
    if avgs.get(close_s) is None:
        return None
    tail = list(range(t_star + 1, close_s))
    if any(s not in ticks for s in tail):
        return None
    return N_AVG * avgs[close_s] - sum(ticks[s] for s in tail)


def eff_strike(strike, d):
    return float(strike) - 0.5 * (10.0 ** (-int(d)))


def fair_from(locked, r, spot, K, sigma):
    mu = (locked + r * spot) / N_AVG
    if r <= 0:
        return 1.0 if mu >= K else 0.0
    sd = sigma * math.sqrt(var_factor(int(r), [1.0]))
    if sd <= 0:
        return 1.0 if mu >= K else 0.0
    return phi((mu - K) / sd)


def decision(f):
    """The frozen pin gate.  +1 buy YES, -1 buy NO, 0 stand aside."""
    if f is None:
        return 0
    if f >= PIN_HI:
        return 1
    if f <= PIN_LO:
        return -1
    return 0


# ------------------------------------------------------------------- stats
def summarise(xs):
    if not xs:
        return dict(n=0)
    s = sorted(xs)
    n = len(s)
    return dict(n=n, mean=sum(s) / n, p50=s[n // 2],
                p95=s[min(n - 1, int(n * 0.95))],
                p99=s[min(n - 1, int(n * 0.99))], mx=s[-1])


def fmt(d):
    if not d.get("n"):
        return "n=0"
    return (f"n={d['n']:6d} mean={d['mean']:.3e} p50={d['p50']:.3e} "
            f"p95={d['p95']:.3e} p99={d['p99']:.3e} max={d['mx']:.3e}")


# ---------------------------------------------------------------- self-test
def _plant(close_s, n_pre=400, seed=7, drop=()):
    """A world where avg60 is EXACTLY the mean of the 60 raw prints before
    it.  `drop` removes raw prints from OUR copy only -- the exchange's avg60
    still contains them, which is the whole point of the improvement."""
    rnd = random.Random(seed)
    truth = {}
    v = 100.0
    for s in range(close_s - n_pre, close_s + 1):
        v += rnd.gauss(0.0, 0.05)
        truth[s] = v
    avgs_true = {}
    for s in range(close_s - n_pre + N_AVG, close_s + 1):
        avgs_true[s] = sum(truth[s - N_AVG + i] for i in range(N_AVG)) / N_AVG
    ticks = {s: x for s, x in truth.items() if s not in drop}
    avgs = {s: a for s, a in avgs_true.items() if s not in drop}
    return truth, ticks, avgs, avgs_true


def selftest():
    ok = True

    def ck(cond, msg):
        nonlocal ok
        print(("  PASS  " if cond else "  FAIL  ") + msg)
        if not cond:
            ok = False

    C = 1788782400
    truth, ticks, avgs, avgs_true = _plant(C)

    # settlement identity: avg60 at the close IS the mean of [close-60,close-1]
    direct60 = sum(truth[s] for s in range(C - N_AVG, C)) / N_AVG
    ck(abs(avgs_true[C] - direct60) < 1e-9,
       f"planted avg60(close) == mean of prints [close-60, close-1] "
       f"({avgs_true[C]:.9f} vs {direct60:.9f})")

    # ---- clean world: direct and exchange must BOTH be exact, improvement 0
    worst_d = worst_e = 0.0
    for tau in range(TAU_LO, TAU_HI + 1):
        now = C - tau
        T = true_locked(ticks, avgs, C, now)
        dd = locked_direct(ticks, C, now)
        ee = locked_exchange(ticks, avgs, C, now)
        ck(T is not None and dd is not None and ee is not None,
           f"clean world tau={tau}: all three defined") if tau == TAU_LO else None
        worst_d = max(worst_d, abs(dd[0] - T))
        worst_e = max(worst_e, abs(ee[0] - T))
    ck(worst_d < 1e-6,
       f"NULL: gap-free tape, direct reconstruction is exact (max err {worst_d:.2e})")
    ck(worst_e < 1e-6,
       f"NULL: gap-free tape, exchange identity is exact (max err {worst_e:.2e})")
    ck(abs(worst_e - worst_d) < 1e-6,
       "NULL: with nothing planted the improvement measures as ZERO")

    # ---- gapped world: raw prints missing INSIDE the settlement window.
    # Only TWO, so that the 95% coverage rule still ACCEPTS and the direct
    # reconstruction produces a wrong answer rather than refusing -- that
    # silent-wrong case is the one this improvement is about.
    gaps = (C - 50, C - 30)
    truth2, ticks2, avgs2, avgs_true2 = _plant(C, drop=gaps)
    ee_err, dd_err, sc_err = [], [], []
    n_dd = n_ee = 0
    for tau in range(TAU_LO, TAU_HI + 1):
        now = C - tau
        dd = locked_direct(ticks2, C, now, "nearest")
        sc = locked_direct(ticks2, C, now, "scale")
        # the exchange kept publishing avg60 through the dropout
        ee = locked_exchange(ticks2, avgs_true2, C, now)

        def truth_at(t_star):
            # the true sum of prints [close-60, t_star]
            return sum(truth2[s] for s in range(C - N_AVG, t_star + 1))

        if dd:
            n_dd += 1
            dd_err.append(abs(dd[0] - truth_at(dd[2])))
        if sc:
            sc_err.append(abs(sc[0] - truth_at(sc[2])))
        if ee:
            n_ee += 1
            ee_err.append(abs(ee[0] - truth_at(ee[2])))
    ck(n_ee == TAU_HI - TAU_LO + 1 and ee_err and max(ee_err) < 1e-6,
       f"PLANTED: with 2 window prints dropped the exchange identity is still "
       f"EXACT ({n_ee} taus, max err "
       f"{max(ee_err) if ee_err else float('nan'):.2e})")
    ck(n_dd == TAU_HI - TAU_LO + 1,
       f"PLANTED: the 95% rule still ACCEPTS at 2 gaps ({n_dd} taus), so the "
       f"direct reconstruction answers rather than refusing")
    ck(dd_err and max(dd_err) > 1e-3,
       f"PLANTED: the nearest-fill reconstruction is SILENTLY WRONG on those "
       f"gaps (max err {max(dd_err) if dd_err else 0:.3e})")
    ck(sc_err and max(sc_err) > 1e-3,
       f"PLANTED: the rescale reconstruction is SILENTLY WRONG too "
       f"(max err {max(sc_err) if sc_err else 0:.3e})")
    ck(ee_err and dd_err and max(ee_err) < max(dd_err),
       "PLANTED: exchange strictly beats direct when prints are dropped")

    # ---- the exchange PARTIAL average (l15).  Planted world: the running
    # mean of [close-59, t] with window_size counting up.  It must recover
    # the locked sum from ONE raw print even when the window is full of
    # holes, and it must refuse when that one print, or the shape, is wrong.
    def make_l15(tr, close_s, size_bug=False):
        d = {}
        run = 0.0
        for k, t in enumerate(range(close_s - N_AVG + 1, close_s + 1)):
            run += tr[t]
            ws = k + 1
            d[t] = (run / ws, (ws + 1) if size_bug else ws)
        return d

    holes = tuple(C - 59 + k for k in range(0, 55, 2))   # 28 prints gone
    truth4, ticks4, avgs4, avgs_true4 = _plant(C, drop=holes)
    l15_4 = make_l15(truth4, C)
    n_ok, worst = 0, 0.0
    for tau in range(TAU_LO, TAU_HI + 1):
        v = locked_l15(ticks4, l15_4, C, C - tau)
        if v is None:
            continue
        n_ok += 1
        want = sum(truth4[x] for x in range(C - N_AVG, v[2] + 1))
        worst = max(worst, abs(v[0] - want))
    ck(n_ok == TAU_HI - TAU_LO + 1 and worst < 1e-6,
       f"PLANTED: with 28 of 60 window prints dropped the exchange PARTIAL "
       f"average still recovers the locked sum EXACTLY ({n_ok} taus, max err "
       f"{worst:.2e}) from one raw print")
    ck(locked_direct(ticks4, C, C - 3) is None,
       "PLANTED: the shipped reconstruction REFUSES that same tape "
       "(95% rule), so l15 buys coverage the direct path cannot get")

    ticks5 = dict(ticks4)
    ticks5.pop(C - N_AVG, None)
    ck(locked_l15(ticks5, l15_4, C, C - 3) is None,
       "REFUSAL: l15 path returns None when the single raw print at "
       "close-60 is missing, rather than guessing it")
    l15_bug = make_l15(truth4, C, size_bug=True)
    ck(locked_l15(ticks4, l15_bug, C, C - 3) is None,
       "REFUSAL: l15 path returns None when window_size does not match the "
       "second it is stamped with -- the shape is verified, not assumed")

    # r must be counted from the locked span, not from window_size
    v = locked_l15(ticks4, l15_4, C, C - 10)
    ck(v is not None and v[1] == N_AVG - (v[2] - (C - N_AVG) + 1),
       f"l15 path reports the right number of UNPUBLISHED prints "
       f"(r={v[1] if v else None} at t*={v[2] if v else None})")

    # ---- the estimator must NOT fabricate an answer when its own inputs are gone
    ticks3 = dict(ticks)
    for s in range(C - 20 - N_AVG, C - 60):
        ticks3.pop(s, None)
    ck(locked_exchange(ticks3, avgs, C, C - 20) is None,
       "REFUSAL: exchange identity returns None when a pre-window raw print "
       "it needs is missing, rather than guessing")

    # ---- 95% coverage rule: it must actually refuse somewhere
    heavy = tuple(C - 60 + k for k in range(0, 40, 2))
    _, ticksH, avgsH, _ = _plant(C, drop=heavy)
    ck(locked_direct(ticksH, C, C - 3) is None,
       "REFUSAL: the 95% coverage rule rejects a half-empty window")

    # ---- LEAK DETECTOR
    # A variant that reads avg60 from AFTER the decision instant must score
    # impossibly well.  If it does not, the leak harness itself is broken and
    # the honest numbers cannot be trusted either.
    rnd = random.Random(11)
    jumped = dict(truth)
    for s in range(C - 10, C + 1):          # a big move planted AFTER tau=10
        jumped[s] = jumped[s] + 5.0
    avgs_j = {}
    for s in range(C - 300, C + 1):
        avgs_j[s] = sum(jumped[s - N_AVG + i] for i in range(N_AVG)) / N_AVG
    now = C - 10
    T = N_AVG * avgs_j[C] - sum(jumped[s] for s in range(now + 1, C))
    honest = locked_exchange(jumped, avgs_j, C, now)
    leak = N_AVG * avgs_j[C]                # peeks at the settlement itself
    settle_true = avgs_j[C]
    honest_mu = (honest[0] + honest[1] * jumped[now]) / N_AVG
    leak_mu = leak / N_AVG
    ck(abs(leak_mu - settle_true) < 1e-9,
       f"LEAK harness works: the peeking variant reproduces the settlement "
       f"to {abs(leak_mu - settle_true):.2e}")
    ck(abs(honest_mu - settle_true) > 1e-3,
       f"LEAK detector fires: the honest estimator does NOT know the planted "
       f"future move (miss {abs(honest_mu - settle_true):.4f}), the peeking "
       f"one does -- so a leak would be visible as an implausible score")
    ck(abs(leak_mu - settle_true) < abs(honest_mu - settle_true),
       "LEAK detector fires: peeking scores strictly better, as it must")

    print("SELFTEST " + ("PASSED" if ok else "FAILED"))
    return ok


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="C:/kals/kalshi_data")
    ap.add_argument("--out", default="C:/kals/fulltape")
    ap.add_argument("--hours", type=int, default=0,
                    help="limit to the newest N hour files (0 = all)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--strict-rx", action="store_true",
                    help="a message is visible at the decision instant ONLY "
                         "if the collector had already received it "
                         "(_rx_ms <= (close-tau)*1000).  Strictly harsher "
                         "than indexing by exchange time.")
    ap.add_argument("--leak", action="store_true",
                    help="also score deliberately peeking variants")
    a = ap.parse_args()

    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1":
        if not selftest():
            print("self-test failed -- refusing to touch real data")
            sys.exit(1)
        print()

    markets = load_markets(os.path.join(a.out, "markets.json"))
    agree, tot = exact_strikes(markets)
    print(f"markets with settlement: {len(markets)}")
    print(f"exact strike recovered from strike(N+1)==settle(N) for "
          f"{sum(1 for m in markets if m['strike_exact'] is not None)}; "
          f"agrees with fulltape truncated strike on {agree}/{tot}")

    files = sorted(glob.glob(os.path.join(a.data, "cfbenchmarks_value",
                                          "*.jsonl.gz")))
    if a.hours:
        files = files[-a.hours:]
    print(f"index hour files: {len(files)}  "
          f"({os.path.basename(files[0])} .. {os.path.basename(files[-1])})")

    by_close = {}
    for m in markets:
        by_close.setdefault(m["close"], []).append(m)

    # rolling two-hour buffers
    ticks = {}     # iid -> {sec: raw}
    avgs = {}      # iid -> {sec: avg60}
    l15v = {}      # iid -> {sec: (value, window_size)}
    meta = {}      # iid -> {sec: (ws, we, l15, rx_ms)}
    done = set()

    # ---- accumulators
    m1 = dict(n=0, avg_eq=0, l15_eq=0, raw_eq=0, avg_have=0, l15_have=0,
              raw_have=0, l15_shift_eq=0, l15_shift_have=0)
    m1_absdiff = {"avg": [], "l15": [], "raw60": []}
    gapstat = {}
    err = {}
    avail = {}
    dec = {}
    leakstat = {}
    win_meta = dict(n=0, ok=0, size_ok=0, l15_seen_offgrid=0, l15_seen_grid=0,
                    grid_msgs=0, offgrid_msgs=0, l15_n=0, l15_shape_ok=0,
                    l15_bounds_claim_t60=0)
    causal = dict(pts=0, have_rx=0, violations=0, lat=[])
    fairgap = {}
    misshist = {}
    staleness = []

    TAUS = list(range(TAU_LO, TAU_HI + 1))
    for t in TAUS:
        for k in ("direct", "scale", "exch", "l15", "best"):
            err[(k, t)] = []
            avail[(k, t)] = [0, 0]
        gapstat[t] = dict(n=0, full=0, gapped=0, refused=0, missing=[],
                          exch_ok=0, exch_no=0)
        fairgap[t] = []
        misshist[t] = {}
    for k in ("direct", "scale", "exch", "l15", "best",
              "leak_settle", "leak5"):
        dec[k] = dict(n=0, yes=0, no=0, flat=0, win=0, loss=0)

    flips = []
    processed = 0

    def process_hour(h0):
        nonlocal processed
        for C in sorted(c for c in by_close if h0 <= c < h0 + 3600):
            if C in done:
                continue
            done.add(C)
            for m in by_close[C]:
                iid = SERIES_TO_INDEX[m["series"]]
                tk = ticks.get(iid)
                av = avgs.get(iid)
                if not tk or not av:
                    continue
                run_close(m, C, tk, av, meta.get(iid, {}),
                          l15v.get(iid, {}))
                processed += 1

    def run_close(m, C, tk, av, mt, lv15):
        d = ROUND_DIGITS[m["series"]]
        band = 0.5 * (10.0 ** -d)
        # the threshold the EXCHANGE applies: it rounds the 60-print
        # mean to round_digits (HALF-UP -- verified 8738/8738) and
        # settles YES iff that >= floor_strike, so the continuous
        # threshold is floor_strike - 0.5*10^-d.  Same correction as
        # pinrun.eff_strike; without it a rounding tie is miscalled.
        K = (None if m["strike_exact"] is None
             else eff_strike(m["strike_exact"], d))
        # ---------- M1: what IS the settlement?  (post-hoc only)
        m1["n"] += 1
        a_close = av.get(C)
        if a_close is not None:
            m1["avg_have"] += 1
            m1_absdiff["avg"].append(abs(a_close - m["settle"]))
            if abs(round(a_close, d) - m["settle"]) <= 0.51 * (10.0 ** -d):
                m1["avg_eq"] += 1
        l15 = (mt.get(C) or (None, None, None, None))[2]
        if l15 is not None:
            m1["l15_have"] += 1
            m1_absdiff["l15"].append(abs(l15 - m["settle"]))
            if abs(round(l15, d) - m["settle"]) <= 0.51 * (10.0 ** -d):
                m1["l15_eq"] += 1
        if all(s in tk for s in range(C - N_AVG, C)):
            r60 = sum(tk[s] for s in range(C - N_AVG, C)) / N_AVG
            m1["raw_have"] += 1
            m1_absdiff["raw60"].append(abs(r60 - m["settle"]))
            if abs(round(r60, d) - m["settle"]) <= 0.51 * (10.0 ** -d):
                m1["raw_eq"] += 1
        # the shifted window [close-59, close], i.e. what l15's VALUE equals
        a_shift = av.get(C + 1)
        if a_shift is not None:
            m1["l15_shift_have"] += 1
            if l15 is not None and abs(a_shift - l15) < 1e-8:
                m1["l15_shift_eq"] += 1

        if K is None:
            return
        # ---------- M2/M3/M4 at each tau
        per_tau = {}
        for tau in TAUS:
            now = C - tau
            # ---- CAUSAL AUDIT.  The decision instant is the RECEIPT of
            # the print stamped `now`.  Nothing stamped later may have
            # been received by then, or indexing by exchange `time`
            # would smuggle the future in.
            rx_now = (mt.get(now) or (None, None, None, None))[3]
            causal['pts'] += 1
            if rx_now is not None:
                causal['have_rx'] += 1
                causal['lat'].append(rx_now - now * 1000)
                for s2 in range(now + 1, C + 1):
                    r2 = (mt.get(s2) or (None, None, None, None))[3]
                    if r2 is not None and r2 <= rx_now:
                        causal['violations'] += 1
                        break
            g = gapstat[tau]
            g["n"] += 1
            lo = C - N_AVG
            hi = min(now, C - 1)
            present = [s for s in range(lo, hi + 1) if s in tk]
            want_span = hi - lo + 1
            if len(present) == want_span:
                g["full"] += 1
            else:
                g["gapped"] += 1
                nmiss = want_span - len(present)
                g["missing"].append(nmiss)
                b = (nmiss if nmiss <= 3 else
                     (4 if nmiss <= 10 else (5 if nmiss < want_span else 6)))
                misshist[tau][b] = misshist[tau].get(b, 0) + 1

            # ---- STRICT RECEIPT GATE.  Under --strict-rx a message counts
            # as available only if the collector had ALREADY RECEIVED it by
            # the decision instant.  p95 receipt latency is ~1.8 s, so the
            # print stamped `now` is frequently not there yet; indexing by
            # exchange `time` alone quietly assumes zero-latency delivery.
            vtk, vav, vl15 = tk, av, lv15
            if a.strict_rx:
                cut = now * 1000
                vis = set()
                for s3, mm in mt.items():
                    if mm[3] is not None and mm[3] <= cut:
                        vis.add(s3)
                    elif mm[3] is None and s3 <= now:
                        vis.add(s3)          # no clock: fall back to time
                vtk = {k3: v3 for k3, v3 in tk.items() if k3 in vis}
                vav = {k3: v3 for k3, v3 in av.items() if k3 in vis}
                vl15 = {k3: v3 for k3, v3 in lv15.items() if k3 in vis}
                newest = max(vtk) if vtk else None
                if newest is not None:
                    staleness.append(now - newest)
            dd = locked_direct(vtk, C, now, "nearest")
            sc = locked_direct(vtk, C, now, "scale")
            ee = locked_exchange(vtk, vav, C, now)
            ll = locked_l15(vtk, vl15, C, now)
            bb = locked_best(vtk, vav, vl15, C, now)
            if dd is None:
                g["refused"] += 1
            if ee is None:
                g["exch_no"] += 1
            else:
                g["exch_ok"] += 1
            for k, v in (("direct", dd), ("scale", sc), ("exch", ee),
                         ("l15", ll), ("best", bb)):
                avail[(k, tau)][1] += 1
                if v is not None:
                    avail[(k, tau)][0] += 1

            sigma = sigma_from(vtk, now)
            spot = None
            # spot = newest print at or before now (pinrun's idx.spot)
            for s in range(now, now - 30, -1):
                if s in vtk:
                    spot = vtk[s]
                    break
            # ---- ground truth, computed AFTER the estimators above
            t_star = dd[2] if dd else (ee[2] if ee else
                                       (ll[2] if ll else None))
            T = true_locked(tk, av, C, t_star) if t_star is not None else None
            for k, v in (("direct", dd), ("scale", sc), ("exch", ee),
                         ("l15", ll), ("best", bb)):
                if v is None or T is None or v[2] != t_star:
                    continue
                err[(k, tau)].append(abs(v[0] - T) / N_AVG / band)
            per_tau[tau] = (dd, sc, ee, sigma, spot, T, ll, bb)
            if dd is not None and ee is not None and sigma and spot is not None:
                fd = fair_from(dd[0], dd[1], spot, K, sigma)
                fe = fair_from((bb or ee)[0], (bb or ee)[1], spot, K, sigma)
                fairgap[tau].append(abs(fe - fd))

        # ---------- M4: the frozen pin gate, one trade per close, earliest
        #             tau in [3,20] that fires (pinrun takes the first chance)
        for k in ("direct", "scale", "exch", "l15", "best",
                  "leak_settle", "leak5"):
            fired = 0
            for tau in sorted(TAUS, reverse=True):
                dd, sc, ee, sigma, spot, T, ll, bb = per_tau[tau]
                if sigma is None or spot is None:
                    continue
                if k == "direct":
                    v = dd
                elif k == "scale":
                    v = sc
                elif k == "exch":
                    v = ee
                elif k == "l15":
                    v = ll
                elif k == "best":
                    v = bb
                elif k == "leak_settle":
                    if av.get(C) is None or ee is None:
                        continue
                    v = (N_AVG * av[C], 0, ee[2], 0)
                else:                       # leak5: 5 seconds of the future
                    now = C - tau
                    f5 = min(now + 5, C - 1)
                    if av.get(f5) is None:
                        continue
                    v2 = locked_exchange(tk, av, C, f5)
                    if v2 is None:
                        continue
                    v = v2
                if v is None:
                    continue
                f = fair_from(v[0], v[1], spot, K, sigma)
                s = decision(f)
                if s:
                    dec[k]["n"] += 1
                    dec[k]["yes" if s > 0 else "no"] += 1
                    won = (m["result"] >= 0.5) if s > 0 else (m["result"] < 0.5)
                    dec[k]["win" if won else "loss"] += 1
                    fired = s
                    break
            if not fired:
                dec[k]["flat"] += 1
            per_tau.setdefault("_sig", {})[k] = fired

        sig = per_tau.get("_sig", {})
        if sig.get("direct") != sig.get("best"):
            flips.append((m["ticker"], sig.get("direct"), sig.get("best"),
                          m["result"]))

    prev_h = None
    for fn in files:
        rows = read_hour(fn)
        for (iid, sec, raw, avv, ws, we, lv, rx, lws) in rows:
            ticks.setdefault(iid, {})[sec] = raw
            if avv is not None:
                avgs.setdefault(iid, {})[sec] = avv
            if lv is not None and lws is not None:
                l15v.setdefault(iid, {})[sec] = (lv, lws)
                win_meta["l15_n"] += 1
                # shape: value covers [close-59, sec] and
                # window_size == sec - (close-60).  VERIFIED, not assumed.
                nxt = sec + ((-sec) % 900)
                if int(lws) == sec - (nxt - N_AVG):
                    win_meta["l15_shape_ok"] += 1
                if ws == sec * 1000 - 60000 and we == sec * 1000:
                    win_meta["l15_bounds_claim_t60"] += 1
            meta.setdefault(iid, {})[sec] = (ws, we, lv, rx)
            # window-shape audit
            if sec % 900 == 0:
                win_meta["grid_msgs"] += 1
                if lv is not None:
                    win_meta["l15_seen_grid"] += 1
            else:
                win_meta["offgrid_msgs"] += 1
                if lv is not None:
                    win_meta["l15_seen_offgrid"] += 1
            if avv is not None:
                win_meta["n"] += 1
                if ws == sec * 1000 - 60000 and we == sec * 1000:
                    win_meta["ok"] += 1
        base = os.path.basename(fn)[:11]     # YYYYMMDDTHH
        try:
            import datetime as _dt
            h0 = int(_dt.datetime.strptime(base, "%Y%m%dT%H")
                     .replace(tzinfo=_dt.timezone.utc).timestamp())
        except ValueError:
            continue
        if prev_h is not None:
            process_hour(prev_h)
        prev_h = h0
        cut = h0 - 4000
        for dd_ in (ticks, avgs, meta, l15v):
            for iid in dd_:
                for s in [s for s in dd_[iid] if s < cut]:
                    del dd_[iid][s]
    if prev_h is not None:
        process_hour(prev_h)

    # ------------------------------------------------------------- report
    print()
    print("=" * 74)
    print("M0  FEED SHAPE")
    print("=" * 74)
    print(f"  messages with avg_60s_data                 : {win_meta['n']}")
    print(f"  whose declared window is exactly [t-60, t) : {win_meta['ok']} "
          f"({100.0*win_meta['ok']/max(1,win_meta['n']):.4f}%)")
    print(f"  last_60s_windowed_average_15min present on quarter-hour msgs : "
          f"{win_meta['l15_seen_grid']}/{win_meta['grid_msgs']}")
    print(f"  ... on every other second                                    : "
          f"{win_meta['l15_seen_offgrid']}/{win_meta['offgrid_msgs']}")
    print(f"  l15 VALUE equals the rolling mean one second later "
          f"(window [t-59, t]) : {m1['l15_shift_eq']}/{m1['l15_shift_have']}")
    print(f"  messages carrying last_60s_windowed_average_15min : "
          f"{win_meta['l15_n']}")
    print(f"    window_size == sec-(close-60), i.e. a running PARTIAL mean "
          f"of [close-59, sec] : {win_meta['l15_shape_ok']}/{win_meta['l15_n']}")
    print(f"    ... while its DECLARED bounds claim [t-60, t)     : "
          f"{win_meta['l15_bounds_claim_t60']}/{win_meta['l15_n']}"
          f"   <-- declared bounds wrong by one second")

    lat = sorted(causal["lat"])
    print()
    print("  CAUSAL AUDIT (no-lookahead enforcement)")
    print(f"    decision points examined                    : {causal['pts']}")
    print(f"    with a collector receipt clock (_rx_ms)     : {causal['have_rx']}")
    if lat:
        print(f"    receipt latency ms  p50 {lat[len(lat)//2]}  "
              f"p95 {lat[int(len(lat)*0.95)]}  max {lat[-1]}")
    print(f"    points where a message stamped LATER than the decision")
    print(f"    instant had already been received by it     : "
          f"{causal['violations']}   <-- must be 0")
    print()
    print("=" * 74)
    print("M1  WHICH NUMBER IS THE SETTLEMENT?  (post-hoc, never an input)")
    print("=" * 74)
    print(f"  settled markets examined: {m1['n']}")
    for k, lbl in (("avg", "exchange avg_60s_data at t==close  [close-60,close-1]"),
                   ("l15", "last_60s_windowed_average_15min    [close-59,close]"),
                   ("raw60", "our own mean of 60 raw prints      [close-60,close-1]")):
        have = m1[{"avg": "avg_have", "l15": "l15_have",
                   "raw60": "raw_have"}[k]]
        eq = m1[{"avg": "avg_eq", "l15": "l15_eq", "raw60": "raw_eq"}[k]]
        s = summarise(m1_absdiff[k])
        print(f"  {lbl}")
        print(f"      available {have:5d}   rounds to the settle value "
              f"{eq}/{have} ({100.0*eq/max(1,have):.2f}%)")
        print(f"      |value - settle| : {fmt(s)}")

    print()
    print("=" * 74)
    print("M2  LOCKED-SUM ERROR, in units of the HALF ROUNDING BAND")
    print("    (error in mu = locked/60, divided by 0.5*10^-round_digits;")
    print("     1.0 means the error alone can flip which side of K_eff we")
    print("     think the settlement lands on)")
    print("=" * 74)
    print(f"  {'tau':>4} {'estimator':>8} {'n':>7} {'mean':>10} {'p50':>10} "
          f"{'p95':>10} {'p99':>10} {'max':>11}  {'>=1 band':>9}")
    for tau in TAUS:
        if tau not in (3, 5, 8, 10, 15, 20):
            continue
        for k in ("direct", "scale", "exch", "l15", "best"):
            xs = err[(k, tau)]
            s = summarise(xs)
            big = sum(1 for x in xs if x >= 1.0)
            if not s["n"]:
                print(f"  {tau:>4} {k:>8}      n=0")
                continue
            print(f"  {tau:>4} {k:>8} {s['n']:>7} {s['mean']:>10.3e} "
                  f"{s['p50']:>10.3e} {s['p95']:>10.3e} {s['p99']:>10.3e} "
                  f"{s['mx']:>11.3e}  {big:>4} "
                  f"({100.0*big/s['n']:.3f}%)")

    print()
    print("=" * 74)
    print("M3  GAPS, AND WHAT THE 95% RULE DOES WITH THEM")
    print("=" * 74)
    print(f"  {'tau':>4} {'decisions':>10} {'window full':>13} "
          f"{'gapped':>10} {'95% refused':>12} {'exch usable':>12} "
          f"{'med missing':>12}")
    for tau in TAUS:
        g = gapstat[tau]
        if not g["n"]:
            continue
        miss = sorted(g["missing"])
        med = miss[len(miss) // 2] if miss else 0
        print(f"  {tau:>4} {g['n']:>10} "
              f"{g['full']:>7} ({100.0*g['full']/g['n']:5.2f}%) "
              f"{g['gapped']:>9} "
              f"{g['refused']:>7} ({100.0*g['refused']/g['n']:5.3f}%) "
              f"{g['exch_ok']:>7} ({100.0*g['exch_ok']/g['n']:5.2f}%) "
              f"{med:>12}")

    print()
    print("  |fair_best - fair_direct| on the SAME close and tau "
          "(both defined)")
    for tau in TAUS:
        xs = fairgap[tau]
        if not xs:
            continue
        s_ = summarise(xs)
        nz = sum(1 for x in xs if x > 1e-9)
        big = sum(1 for x in xs if x > 0.005)
        print(f"    tau={tau:>2} n={s_['n']:>6} nonzero={nz:>6} "
              f"({100.0*nz/s_['n']:6.3f}%) >0.5c={big:>5} "
              f"mean={s_['mean']:.3e} p99={s_['p99']:.3e} max={s_['mx']:.3e}")
    print()
    print("  COVERAGE -- how often each estimator can answer at all")
    print(f"    {'tau':>4} " + " ".join(f"{k:>18}" for k in
                                        ("direct", "scale", "exch",
                                         "l15", "best")))
    for tau in (3, 5, 8, 10, 15, 20):
        cells = []
        for k in ("direct", "scale", "exch", "l15", "best"):
            ok, tot = avail[(k, tau)]
            cells.append(f"{ok:>7}/{tot:<6} {100.0*ok/max(1,tot):5.2f}%")
        print(f"    {tau:>4} " + " ".join(cells))

    print()
    print("  SHAPE OF THE GAPS (how many window seconds are missing when")
    print("  the window is not full) -- this decides whether the exchange")
    print("  average can repair anything at all")
    lbl = {1: "1 missing", 2: "2 missing", 3: "3 missing",
           4: "4-10 missing", 5: "11..almost all", 6: "THE WHOLE WINDOW"}
    for tau in (3, 10, 20):
        h = misshist[tau]
        tot = sum(h.values())
        if not tot:
            continue
        print(f"    tau={tau:>2}  gapped={tot}")
        for b in sorted(h):
            print(f"        {lbl[b]:>18} : {h[b]:>6} "
                  f"({100.0*h[b]/tot:5.2f}% of gapped)")
    if staleness:
        st = sorted(staleness)
        print()
        print("  STALENESS under --strict-rx: age in seconds of the newest")
        print("  index print the collector had actually received")
        print(f"    n={len(st)} mean={sum(st)/len(st):.3f}s "
              f"p50={st[len(st)//2]}s p95={st[int(len(st)*0.95)]}s "
              f"p99={st[int(len(st)*0.99)]}s max={st[-1]}s")

    print()
    print("=" * 74)
    print("M4  DOES IT CHANGE A TRADE DECISION?  (frozen pin gate, one per")
    print("    close, earliest firing tau in [3,20])")
    print("=" * 74)
    keys = ["direct", "scale", "exch", "l15", "best"] + (
        ["leak_settle", "leak5"] if a.leak else [])
    print(f"  {'variant':>13} {'fired':>7} {'yes':>6} {'no':>6} "
          f"{'win':>6} {'loss':>6} {'win rate':>9}")
    for k in keys:
        v = dec[k]
        if not v["n"]:
            print(f"  {k:>13}   fired 0")
            continue
        print(f"  {k:>13} {v['n']:>7} {v['yes']:>6} {v['no']:>6} "
              f"{v['win']:>6} {v['loss']:>6} "
              f"{100.0*v['win']/v['n']:>8.3f}%")
    print()
    print(f"  closes where direct and BEST disagree on the signal: "
          f"{len(flips)} of {processed}")
    for t_, sd_, se_, r_ in flips[:25]:
        print(f"      {t_:<28} direct={sd_:+d} exch={se_:+d} result={r_:.0f}")
    if a.leak:
        print()
        print("  LEAK CHECK -- these two variants read data from AFTER the")
        print("  decision instant.  A win rate near 100% is the expected")
        print("  signature; if the honest rows matched them, the honest")
        print("  numbers would be leaking too.")


if __name__ == "__main__":
    main()
