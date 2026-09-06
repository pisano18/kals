#!/usr/bin/env python3
"""patterntrade.py -- trade the one calibration pattern that survived.

    (Named compression.py until 2026-08-28. Python 3.14 added a stdlib PACKAGE
    called `compression`, and research/ is first on sys.path in every stage, so
    `import gzip` -- which does `from compression._common import _streams` on
    3.14 -- resolved to this file instead. Every stage that reads compressed
    data died on import, on the user's machine only, because the container
    this was developed in runs 3.11 where gzip imports `_compression` and the
    name does not exist. shadow.py now checks for this at gate time.)

THE PATTERN. calib.py priced the same markets three ways -- trade prints, the
book mid at trade times, and the mid on a FIXED tau grid that ignores when
trades happened. Most of D-FINAL's cells died in that gauntlet. What survived
is a smooth, monotone shape in the 480-900s band: outcomes come out MORE
extreme than prices. 25c realises ~20c, 40c realises ~34c, 80c realises ~82c,
90c realises ~94c. Prices are squashed toward 50c early in the window.

Three independent measurements agree with it:
  - calib's grid column (the only sample not chosen by the market),
  - implied.py's term structure: implied/realised ~1.02 at 300-900s against
    0.86-0.88 at 30-120s -- too much vol priced early is the same thing as
    prices squashed toward 50 early,
  - openwindow.py: fair value at the open is NOT 50c (mean |fair-50| 4.75c),
    and a book slow to leave 50 is compressed by construction.

THE TRADE, exactly as a robot would have to do it: at the FIRST grid second
in the 480-900s band where the mid sits in the band edges (0.20-0.45 or
0.55-0.80), buy the side AWAY from 50c, crossing the spread at mid + half a
tick, paying the real taker fee, holding to settlement. One trade per market,
maximum, because every fill in a market settles on the same outcome.

This file answers one question: after the spread and the fee, is the
compression worth money? Its self-test plants a KNOWN compression in a world
whose fair book is an exact martingale posterior, and must recover the edge
there and NOTHING on the fair world.

NOTHING HERE PLACES AN ORDER.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from statistics import NormalDist, mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calib import outcome_of, _mid_index, _mid_at                 # noqa: E402
from tdist import p_two_sided                                      # noqa: E402

ND = NormalDist()
FEE_K = 0.07
GRID_STEP = 15
TAU_LO, TAU_HI = 480, 900
BANDS = ((0.20, 0.45), (0.55, 0.80))
HALF_SPREAD = 0.005          # the liquid series quote 1c wide in this range


def fee_cents(p):
    p = min(max(p, 0.0), 1.0)
    return 100.0 * FEE_K * p * (1.0 - p)


def decide(mid):
    """Which side, if any, the compression trade takes at this mid."""
    for lo, hi in BANDS:
        if lo <= mid <= hi:
            return "yes" if mid > 0.5 else "no"
    return None


def run_trades(quotes, markets):
    """One trade per market at the first qualifying grid second."""
    trades = []
    for tk, q in quotes.items():
        m = markets.get(tk)
        won = outcome_of(m) if m else None
        if won is None:
            continue
        close_s = int(round(float(m["close"])))
        secs, mids = _mid_index(q)
        if len(secs) < 5:
            continue
        for tau in range(TAU_HI, TAU_LO - 1, -GRID_STEP):
            mid = _mid_at(secs, mids, close_s - tau)
            if mid is None:
                continue
            side = decide(mid)
            if side is None:
                continue
            if side == "yes":
                entry = mid + HALF_SPREAD
                pnl = 100.0 * (won - entry) - fee_cents(entry)
            else:
                entry = (1.0 - mid) + HALF_SPREAD
                pnl = 100.0 * ((1.0 - won) - entry) - fee_cents(entry)
            trades.append({"tk": tk, "close": close_s, "tau": tau,
                           "mid": mid, "side": side, "entry": entry,
                           "won": won, "pnl": pnl})
            break                                  # one per market
    return trades


def summarise(trades):
    if len(trades) < 30:
        return None
    by = defaultdict(list)
    for t in trades:
        by[t["close"]].append(t["pnl"])
    obs = [mean(v) for v in by.values()]
    m, sd = mean(obs), pstdev(obs)
    se = sd / math.sqrt(len(obs)) if sd > 0 else float("inf")
    return {"n_trades": len(trades), "n_clusters": len(obs), "mean": m,
            "se": se, "t": m / se if se > 0 else 0.0, "df": len(obs) - 1}


def redraw_null(trades, reps=2000, seed=20260828, value=None):
    """Resettle every trade by ITS OWN entry-implied probability: the null is
    'the market's price was right'. What the strategy earns above this band is
    what the compression is actually worth."""
    rng = random.Random(seed)
    out = []
    for _ in range(reps):
        by = defaultdict(list)
        for t in trades:
            p_yes = t["mid"]
            won = 1.0 if rng.random() < p_yes else 0.0
            if t["side"] == "yes":
                pnl = 100.0 * (won - t["entry"]) - fee_cents(t["entry"])
            else:
                pnl = 100.0 * ((1.0 - won) - t["entry"]) - fee_cents(t["entry"])
            by[t["close"]].append(pnl)
        out.append(mean([mean(v) for v in by.values()]))
    out.sort()
    res = {"lo": out[int(0.025 * reps)], "hi": out[int(0.975 * reps)]}
    # TIE-AWARENESS. A resampled band is only smooth if the assumed
    # probabilities are spread out. Where they pile up near 0 or 1 the
    # simulated mean moves in whole-flip steps of 100/n cents, mass collects
    # on a few atoms, and `lo <= mean <= hi` gets decided by floating-point
    # dust on a boundary. That is not hypothetical: pin.py's headline flag
    # was firing on a difference of -4.4e-15 (found 2026-09-06). This null
    # resettles at the MARKET's mid, which is mid-range for the compression
    # trade, so it should stay smooth -- `atoms` is reported so that stops
    # being an assumption. `rank` is the mid-p percentile of `value`:
    # strictly-below plus half the ties.
    res["atoms"] = len({round(x, 9) for x in out})
    if value is not None:
        below = sum(1 for x in out if x < value - 1e-9)
        ties = sum(1 for x in out if abs(x - value) <= 1e-9)
        res["rank"] = (below + 0.5 * ties) / float(reps)
        res["ties"] = ties
    return res


# ===========================================================================
def _world(n, seed, squash=0.0):
    """Brownian posterior world. The fair mid is the EXACT posterior
    Phi(x / sd_remaining); the quoted mid is squashed toward 50c by `squash`.
    squash=0 is a perfectly fair book and must earn nothing but fees."""
    rng = random.Random(seed)
    quotes, markets = {}, {}
    SIG = 1.0
    for w in range(n):
        close_s = 1_760_000_000 + w * 900
        tk = f"Z{w:04d}"
        x, q = 0.0, []
        for tau in range(900, 0, -1):
            t = close_s - tau
            x += rng.gauss(0, SIG)
            fair = ND.cdf(x / (SIG * math.sqrt(tau)))
            mid = 0.5 + (1.0 - squash) * (fair - 0.5)
            mid = round(mid / 0.01) * 0.01                  # the tick is real
            q.append((t, max(mid - HALF_SPREAD, 0.0),
                      min(mid + HALF_SPREAD, 1.0), 100.0, 100.0))
        markets[tk] = {"ticker": tk, "close": close_s, "strike": 1.0,
                       "result": 1.0 if x > 0 else 0.0}
        quotes[tk] = q
    return quotes, markets


def _expected_edge(squash, seed=99, n=40000):
    """Monte-Carlo the planted per-trade edge for the assertion, using the
    same decision rule, so the self-test target is derived rather than
    hand-waved."""
    rng = random.Random(seed)
    tot, cnt = 0.0, 0
    for _ in range(n):
        # a market at a random grid point in the band: draw the posterior
        tau = rng.choice(range(TAU_LO, TAU_HI + 1, GRID_STEP))
        x = rng.gauss(0, math.sqrt(900 - tau))
        fair = ND.cdf(x / math.sqrt(tau))
        mid = round((0.5 + (1 - squash) * (fair - 0.5)) / 0.01) * 0.01
        side = decide(mid)
        if side is None:
            continue
        if side == "yes":
            entry = mid + HALF_SPREAD
            pnl = 100.0 * (fair - entry) - fee_cents(entry)
        else:
            entry = (1.0 - mid) + HALF_SPREAD
            pnl = 100.0 * ((1.0 - fair) - entry) - fee_cents(entry)
        tot += pnl
        cnt += 1
    return tot / max(cnt, 1)


def selftest():
    print("=" * 78)
    print("SELF-TEST -- the strategy must find a planted compression and")
    print("must NOT make money on an exactly-fair book")
    print("=" * 78)
    fails = []
    print(f"\n  {'world':>22}{'trades':>8}{'clusters':>10}{'P&L/trade':>11}"
          f"{'t':>7}{'null 95%':>20}{'expected':>10}")
    for name, squash in (("fair (squash=0)", 0.0), ("squash 7%", 0.07),
                         ("squash 15%", 0.15)):
        q, mk = _world(1500, seed=31 + int(squash * 100), squash=squash)
        tr = run_trades(q, mk)
        sm = summarise(tr)
        if not sm:
            fails.append(f"{name}: too few trades")
            continue
        nl = redraw_null(tr, reps=400)
        exp = _expected_edge(squash)
        print(f"  {name:>22}{sm['n_trades']:>8,}{sm['n_clusters']:>10,}"
              f"{sm['mean']:>10.2f}c{sm['t']:>7.1f}"
              f"   [{nl['lo']:>6.2f},{nl['hi']:>6.2f}]{exp:>9.2f}c")
        if squash == 0.0:
            # a fair book must pay roughly minus costs, inside its own null
            if sm["mean"] > 0 and sm["t"] > 2:
                fails.append(f"made {sm['mean']:.2f}c (t={sm['t']:.1f}) on a "
                             "fair book -- the harness is inventing an edge")
            if not (nl["lo"] - 0.35 <= sm["mean"] <= nl["hi"] + 0.35):
                fails.append(f"fair-book P&L {sm['mean']:.2f}c sits outside "
                             f"its own null [{nl['lo']:.2f},{nl['hi']:.2f}]")
        else:
            if abs(sm["mean"] - exp) > max(3.5 * sm["se"], 0.45):
                fails.append(f"{name}: realised {sm['mean']:.2f}c vs derived "
                             f"expectation {exp:.2f}c -- the harness does not "
                             "measure what it plants")
            # NO t>3 detection assertion, deliberately. The first version had
            # one and it failed -- correctly. A binary settled at ~30c has a
            # per-trade sd of ~46c, so even a PROFITABLE compression nets
            # tenths of a cent against tens of cents of noise: detecting
            # +0.5c at 80% power needs ~76,000 markets, and the real tape has
            # 3,600. The harness's job is therefore to measure WITHOUT bias
            # (the derived-expectation check above) and to say the power
            # limit out loud, not to pretend settlement P&L can certify a
            # small edge. That certification, if it ever comes, comes from
            # the calibration curve and the implied-vs-settle ratio, which
            # get thousands of observations per hour instead of four.

    # one per market, enforced
    q, mk = _world(200, seed=7, squash=0.15)
    tr = run_trades(q, mk)
    if len(tr) != len({t['tk'] for t in tr}):
        fails.append("more than one trade in a single market")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- nothing earned on a fair book, the planted")
    print("compression recovered at its derived size, one trade per market.")
    return True


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    from replay import load_quotes, load_markets
    quotes = load_quotes(a.data)
    markets = load_markets(a.out)
    if not markets:
        print(f"\n  *** NO SETTLED MARKETS at {os.path.abspath(a.out)} -- "
              "run fulltape or fix --out.")
        return
    trades = run_trades(quotes, markets)
    sm = summarise(trades)
    print("\n" + "=" * 78)
    print("THE COMPRESSION TRADE -- 480-900s, buy the side away from 50c")
    print("=" * 78)
    if not sm:
        print(f"  only {len(trades)} qualifying trades -- nothing to report.")
        return
    mde = 3.0 * 46.0 / math.sqrt(max(sm["n_clusters"], 1))
    print(f"  POWER: per-trade sd is ~46c, so at {sm['n_clusters']:,} clusters")
    print(f"  the minimum detectable edge is ~{mde:.1f}c. Any smaller result,")
    print("  positive or negative, is NO INFORMATION -- read the calibration")
    print("  curve and the reconcile ratio instead; they carry the power.")
    nl = redraw_null(trades, value=sm["mean"])
    per_side = defaultdict(list)
    for t in trades:
        per_side[t["side"]].append(t["pnl"])
    print(f"  trades                      {sm['n_trades']:,}  "
          f"(yes {len(per_side['yes']):,} / no {len(per_side['no']):,})")
    print(f"  close-time clusters         {sm['n_clusters']:,}")
    print(f"  mean P&L per trade          {sm['mean']:+.2f}c")
    print(f"  t / p                       {sm['t']:.2f} / "
          f"{p_two_sided(abs(sm['t']), sm['df']):.4f}")
    print(f"  market-is-right null 95%    [{nl['lo']:+.2f}, {nl['hi']:+.2f}]c"
          f"   ({nl['atoms']:,} distinct draws)")
    # the rank, not the edge -- see redraw_null on why a boundary comparison
    # is unsafe when the band is discrete
    inside = 0.025 <= nl["rank"] <= 0.975
    tied = nl["ties"] > 0 and (abs(sm["mean"] - nl["lo"]) < 1e-6
                               or abs(sm["mean"] - nl["hi"]) < 1e-6)
    print(f"\n  {'INSIDE the null -- the compression is not worth money' if inside else 'OUTSIDE the null'}"
          f"   (rank {100 * nl['rank']:.1f}%"
          f"{', TIED on a boundary atom' if tied else ''})")
    print("  Fees and the crossed spread are already in every number above.")
    by_bucket = defaultdict(list)
    for t in trades:
        by_bucket[round(t['mid'], 1)].append(t["pnl"])
    print(f"\n  {'entry mid':>11}{'trades':>8}{'mean P&L':>11}")
    for b in sorted(by_bucket):
        v = by_bucket[b]
        if len(v) >= 20:
            print(f"  {100*b:>10.0f}c{len(v):>8,}{mean(v):>10.2f}c")


if __name__ == "__main__":
    main()
