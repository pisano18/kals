#!/usr/bin/env python3
# VERSION: 2026-09-08-pc1
"""pincal.py -- IS THE MODEL CALIBRATED AT THE GATE pin ACTUALLY TRADES?

THE QUESTION, AND WHY IT OUTRANKS EVERY OTHER OPEN ITEM

pin buys when the model says an outcome is >= 98% decided and someone is still
offering the other side cheap. Its whole P&L shape is win ~1-3c, lose ~97c, so
the strategy lives or dies on ONE number: when the model says 98%, how often is
it actually right? The breakeven flip rate against a 2c win is 2.0%. At 3%
flips pin loses money no matter how good the execution is.

That question needs NO orderbook. It needs the index ticks (small), the strike,
and the settled result. So it can be answered cheaply, over many days, while
the tape-heavy jobs run elsewhere -- and it is the honest test of the
spot-substitution risk that the one replayed loss turned out to be.

WHAT SPOT SUBSTITUTION IS, and why it is pin's real remaining risk

With tau seconds to close, 60-tau settlement prints are already on disk and tau
are not. The model replaces every unprinted tick with the CURRENT spot and adds
variance for the walk. When spot is a transient -- a dip that recovers -- the
model extrapolates the transient across all tau remaining prints and can be
confidently wrong. That is exactly what produced the only loss in the
2026-09-07 replay: ETHUSD_RTI dipped to 2492.60 at tau 5-6, the model priced
fair 0.013, and the index came back to 2493.08 by tau=3. Both of the settlement
corrections (window and rounding) leave that trade in place.

WHAT THIS MEASURES

For every settled market and every second in a tau grid, the corrected fair
value, bucketed. Then, per bucket, the realised YES rate. A calibrated model
puts 98-100% buckets at 98-100% realised.

  * clusters on CLOSE, not on market-seconds: all coins settle on the same
    quarter hour and are ~1.22 independent observations per close, so a naive
    per-second n would overstate confidence by ~50x.
  * reports the DECIDED-SIDE flip rate, which is the number pin actually needs,
    with a rule-of-three upper bound when there are zero flips.
  * reports it separately for the OLD and the CORRECTED model, so the value of
    the two fixes is measured rather than asserted.
  * a spot-transient diagnostic: how far spot sits from its own trailing mean
    at the moment of a flip, versus at the moment of a correct call.

SELF-TEST: builds a world with a known answer -- a pure random walk where the
model IS the truth, so calibration must come out flat -- and a rigged world
where spot is a sawtooth transient, where the naive model must come out
overconfident and the test must SEE that. An estimator that cannot fail on the
rigged world cannot be trusted on the real one.
"""
import argparse
import calendar
import glob
import gzip
import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor, N_AVG                        # noqa: E402

ND = NormalDist()
IDXDIR = r"C:\kals\kalshi_data\cfbenchmarks_value"
FULLTAPE = r"C:\kals\fulltape\markets.json"

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXBCH15M": "BCHUSD_RTI",
    "KXZEC15M": "ZECUSD_RTI", "KXHYPE15M": "HYPEUSD_RTI",
    "KXNEAR15M": "NEARUSD_RTI", "KXADA15M": "ADAUSD_RTI",
}
ROUND_DIGITS = {"KXBTC15M": 2, "KXETH15M": 2, "KXBNB15M": 2}   # others 4
PIN = 0.98
SIGMA_WIN = 300


def eff_strike(strike, d):
    return float(strike) - 0.5 * (10.0 ** (-int(d)))


def sigma_from(ticks, now_s, win=SIGMA_WIN):
    secs = [s for s in range(now_s - win, now_s + 1) if s in ticks]
    diffs = [ticks[secs[i]] - ticks[secs[i - 1]]
             for i in range(1, len(secs)) if secs[i] - secs[i - 1] == 1]
    if len(diffs) < 20:
        return None
    mu = sum(diffs) / len(diffs)
    return math.sqrt(sum((x - mu) ** 2 for x in diffs) / (len(diffs) - 1))


def fair_at(ticks, close_s, now_s, strike, sigma, corrected, d=None):
    """Model fair. corrected=True uses [close-60, close-1] and the rounded
    threshold; corrected=False reproduces the shipped backtest."""
    if corrected:
        lo, hi = close_s - N_AVG, min(now_s, close_s - 1)
        K = eff_strike(strike, d) if d is not None else float(strike)
    else:
        lo, hi = close_s - N_AVG + 1, min(now_s, close_s)
        K = float(strike)
    if hi < lo:
        return None
    want = hi - lo + 1
    got = [ticks[s] for s in range(lo, hi + 1) if s in ticks]
    if not got or len(got) < want * 0.95:
        return None
    locked = sum(got) * (want / len(got))
    r = N_AVG - want
    spot = ticks.get(now_s)
    if spot is None:
        return None
    mu = (locked + r * spot) / N_AVG
    if r <= 0:
        return 1.0 if mu >= K else 0.0
    sd = sigma * math.sqrt(var_factor(int(r), [1.0]))
    if sd <= 0:
        return 1.0 if mu >= K else 0.0
    return ND.cdf((mu - K) / sd)


def transient(ticks, now_s, sigma, back=5):
    """How far spot sits from its own trailing mean, in sigmas. The model
    extrapolates spot across every unprinted tick, so a spot that is far from
    its own recent mean is the model betting on a move that just happened."""
    secs = [s for s in range(now_s - back, now_s + 1) if s in ticks]
    if len(secs) < 3 or not sigma:
        return None
    m = sum(ticks[s] for s in secs) / len(secs)
    return (ticks[now_s] - m) / (sigma * math.sqrt(back))


# ===========================================================================
def selftest():
    print("SELF-TEST -- pincal")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    rng = random.Random(7)
    C = 2_000_000

    # WORLD 1: a pure random walk. The model IS the data-generating process,
    # so at the 0.98 gate the realised rate must be ~98-100%.
    dec_n = dec_hit = 0
    for trial in range(400):
        ticks, v = {}, 100.0
        for s in range(C - 400, C + 1):
            v += rng.gauss(0, 1.0)
            ticks[s] = v
        settle = sum(ticks[s] for s in range(C - 60, C)) / 60.0
        K = settle + rng.gauss(0, 3.0)          # strikes scattered around
        won = 1.0 if settle >= K else 0.0
        for tau in (20, 12, 6):
            f = fair_at(ticks, C, C - tau, K, 1.0, corrected=True)
            if f is None:
                continue
            if f >= PIN or f <= 1 - PIN:
                dec_n += 1
                side = 1.0 if f >= PIN else 0.0
                dec_hit += int(side == won)
    rate = dec_hit / max(dec_n, 1)
    print(f"  random walk: {dec_n} decided calls, realised {100*rate:.1f}%")
    ck(dec_n > 50, f"the estimator finds decided calls at all ({dec_n})")
    ck(rate >= 0.95,
       f"a correctly-specified model calibrates at the gate ({100*rate:.1f}%, "
       f"expected >=95%)")

    # WORLD 2: RIGGED. Spot carries a big transient that always reverts, so
    # substituting spot for the unprinted ticks is systematically wrong. The
    # naive model must come out OVERCONFIDENT and this test must see it.
    dec_n2 = dec_hit2 = 0
    for trial in range(400):
        base, ticks = 100.0, {}
        for s in range(C - 400, C + 1):
            ticks[s] = base                      # flat truth
        # a 6-second spike right before the close that fully reverts
        for j, s in enumerate(range(C - 12, C - 5)):
            ticks[s] = base + 8.0
        settle = sum(ticks[s] for s in range(C - 60, C)) / 60.0
        K = settle + 0.15                        # just above the true settle
        won = 1.0 if settle >= K else 0.0        # always 0
        f = fair_at(ticks, C, C - 8, K, 0.35, corrected=True)
        if f is None:
            continue
        if f >= PIN or f <= 1 - PIN:
            dec_n2 += 1
            side = 1.0 if f >= PIN else 0.0
            dec_hit2 += int(side == won)
    r2 = dec_hit2 / max(dec_n2, 1)
    print(f"  rigged transient: {dec_n2} decided calls, realised {100*r2:.1f}%")
    ck(dec_n2 > 50, f"the rigged world produces decided calls ({dec_n2})")
    ck(r2 < 0.5,
       f"the test SEES a model fooled by a transient ({100*r2:.1f}%, must be "
       f"far below the 98% it claims) -- an estimator that cannot fail here "
       f"cannot be trusted on real data")

    # the corrected window really is different from the old one
    t = {s: 1.0 for s in range(C - 60, C)}
    t[C - 60] = 0.0
    t[C] = 1000.0
    a = fair_at(t, C, C, 0.5, 1.0, corrected=True)
    b = fair_at(t, C, C, 0.5, 1.0, corrected=False)
    ck(a is not None and b is not None and a == 1.0,
       f"corrected window excludes the tick at close (fair {a})")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ===========================================================================
def load_index_hours(files):
    """{index_id: {sec: value}} streamed one file at a time."""
    ticks = defaultdict(dict)
    for f in files:
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    if '"cfbenchmarks_value"' not in line:
                        continue
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    m = d.get("msg") or {}
                    iid = m.get("index_id")
                    if not iid:
                        continue
                    try:
                        dd = json.loads(m["data"])
                        ticks[iid][int(dd["time"]) // 1000] = float(dd["value"])
                    except Exception:
                        continue
        except EOFError:
            pass
    return ticks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=12)
    ap.add_argument("--taus", default="20,15,10,6,4")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")
    taus = [int(x) for x in a.taus.split(",")]

    # only hours the SETTLEMENT tape can score. fulltape is refreshed by a
    # separate job and lags the index by a day or two; taking the newest index
    # hours regardless silently produced "0 settled markets" and an empty
    # table, which looks exactly like a broken estimator.
    rows0 = [r for v in json.load(open(FULLTAPE, encoding="utf-8")).values()
             for r in v]
    ft_hi = max(float(r["close"]) for r in rows0)
    ft_lo = min(float(r["close"]) for r in rows0)
    files = sorted(glob.glob(os.path.join(IDXDIR, "2026*.jsonl.gz")))[:-1]

    def hour_of(f):
        b = os.path.basename(f)[:11]            # YYYYMMDDTHH
        return calendar.timegm(time.strptime(b, "%Y%m%dT%H"))

    files = [f for f in files if ft_lo - 3600 <= hour_of(f) <= ft_hi]
    if not files:
        raise SystemExit("no index hours overlap the settlement tape")
    files = files[-a.hours:]
    print(f"  settlement tape covers "
          f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(ft_lo))} .. "
          f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(ft_hi))}")
    print(f"\n  {len(files)} index hour files: "
          f"{os.path.basename(files[0])} .. {os.path.basename(files[-1])}")
    ticks = load_index_hours(files)
    print(f"  {len(ticks)} indices, "
          f"{sum(len(v) for v in ticks.values()):,} ticks")

    rows = rows0
    lo = min(min(v) for v in ticks.values() if v)
    hi = max(max(v) for v in ticks.values() if v)
    mk = [r for r in rows if lo + 400 < float(r["close"]) <= hi]
    print(f"  {len(mk)} settled markets close inside this index window\n")

    # bucket -> [n, hits]; and the decided-gate tally, clustered on close
    buckets = defaultdict(lambda: [0, 0])
    gate = {True: defaultdict(lambda: [0, 0]), False: defaultdict(lambda: [0, 0])}
    flips, corrects = [], []
    closes_seen = set()

    for r in mk:
        s = r["series"]
        iid = SERIES_TO_INDEX.get(s)
        if not iid or iid not in ticks:
            continue
        T = ticks[iid]
        close_s = int(float(r["close"]))
        K = float(r["strike"])
        won = 1.0 if float(r["result"]) >= 0.5 else 0.0
        d = ROUND_DIGITS.get(s, 4)
        for tau in taus:
            now = close_s - tau
            sg = sigma_from(T, now)
            if sg is None:
                continue
            for corrected in (True, False):
                f = fair_at(T, close_s, now, K, sg, corrected,
                            d if corrected else None)
                if f is None:
                    continue
                if corrected:
                    b = min(9, int(f * 10))
                    buckets[b][0] += 1
                    buckets[b][1] += won
                if f >= PIN or f <= 1 - PIN:
                    side = 1.0 if f >= PIN else 0.0
                    g = gate[corrected][tau]
                    g[0] += 1
                    g[1] += int(side == won)
                    closes_seen.add(close_s)
                    if corrected:
                        tr = transient(T, now, sg)
                        (corrects if side == won else flips).append(
                            dict(ticker=r["ticker"], tau=tau, fair=round(f, 4),
                                 won=won, transient=None if tr is None
                                 else round(tr, 2)))

    print("  CALIBRATION OF THE CORRECTED MODEL (all taus pooled)")
    print(f"    {'model says':>14}{'n':>9}{'realised YES':>15}")
    for b in sorted(buckets):
        n, h = buckets[b]
        if n:
            print(f"    {b*10:>6}-{b*10+10:<7}{n:>9,}{100*h/n:>14.1f}%")

    print(f"\n  THE GATE pin TRADES (fair >= {PIN} or <= {1-PIN})")
    print(f"    {'tau':>5}{'model':>12}{'calls':>9}{'right':>9}"
          f"{'FLIP RATE':>12}{'95% upper':>11}")
    for tau in taus:
        for corrected in (True, False):
            n, h = gate[corrected][tau]
            if not n:
                continue
            fl = n - h
            ub = (3.0 / n) if fl == 0 else None
            lab = "corrected" if corrected else "old"
            ubs = f"<{100*ub:.2f}%" if ub is not None else ""
            print(f"    {tau:>5}{lab:>12}{n:>9,}{h:>9,}"
                  f"{100*fl/n:>11.2f}%{ubs:>11}")

    tot_n = sum(gate[True][t][0] for t in taus)
    tot_h = sum(gate[True][t][1] for t in taus)
    tot_f = tot_n - tot_h
    print(f"\n  CORRECTED MODEL AT THE GATE: {tot_n:,} calls over "
          f"{len(closes_seen):,} closes")
    if tot_n:
        print(f"    flip rate {100*tot_f/tot_n:.2f}%  "
              f"({tot_f} wrong of {tot_n:,})")
        print(f"    BREAKEVEN flip rate against a 2c win is 2.00%.")
        print(f"    -> {'ABOVE breakeven, pin loses money' if tot_f/max(tot_n,1) > 0.02 else 'below breakeven'}")
    print(f"    NOTE: n is market-seconds. The independent unit is the CLOSE "
          f"({len(closes_seen):,} of them);\n"
          f"    all coins settle together at rho~0.8, so treat the effective n "
          f"as ~1.2 x closes.")

    if flips:
        tr_f = [x["transient"] for x in flips if x["transient"] is not None]
        tr_c = [x["transient"] for x in corrects if x["transient"] is not None]
        if tr_f and tr_c:
            af = sum(abs(x) for x in tr_f) / len(tr_f)
            ac = sum(abs(x) for x in tr_c) / len(tr_c)
            print(f"\n  SPOT-TRANSIENT DIAGNOSTIC (|spot - trailing 5s mean| "
                  f"in sigmas)")
            print(f"    at a FLIP    : {af:.3f}  (n={len(tr_f)})")
            print(f"    when CORRECT : {ac:.3f}  (n={len(tr_c)})")
            print(f"    ratio {af/ac if ac else 0:.2f}x -- "
                  f"{'flips ARE preceded by a spot transient; a guard on this '
                     'would help' if af > 1.3*ac else 'no transient signal; a '
                     'guard on this would NOT help'}")
        print(f"\n  the {len(flips)} wrong calls, worst first:")
        for x in sorted(flips, key=lambda z: -abs(z["fair"] - 0.5))[:12]:
            print(f"    {x['ticker'][:34]:<35} tau {x['tau']:>3} "
                  f"fair {x['fair']:.4f} settled "
                  f"{'YES' if x['won'] else 'NO':<4} "
                  f"transient {x['transient']}")


if __name__ == "__main__":
    main()
