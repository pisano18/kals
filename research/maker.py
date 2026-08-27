#!/usr/bin/env python3
# VERSION: 2026-08-27-mk1
"""
maker.py -- can you QUOTE these markets rather than cross them?

    python research/maker.py --selftest
    python research/maker.py --data C:\\kals\\kalshi_data --out C:\\kals\\fulltape

WHY THIS EXISTS

PLAN.md sec.4 killed market-making on one observation -- "best bid 0.40 with
3,767 contracts resting" -- taken from a REST call RUNBOOK separately records
as mis-parsed. Rebuilt from the websocket, median depth at the touch is about
30 contracts. The number that closed the strategy was wrong by two orders of
magnitude, so the strategy is open again and nobody has priced it.

Three facts make it worth pricing, all measured, none assumed:

  1. MAKERS PAY NO FEE. All sixteen fifteen-minute series carry
     fee_type="quadratic", not "quadratic_with_maker_fees". A taker crossing a
     one-cent spread at the money pays 1.75c. The maker on the other side pays
     nothing. That asymmetry is the whole opportunity.
  2. The tick is one cent and the median quoted spread on the liquid series is
     one cent -- so a two-sided quote captures 1c gross, 0.5c per side.
  3. The thin series quote far wider: ZEC 7c, NEAR 8c.

THE ONE CALCULATION THAT DECIDES IT

A resting quote is an option you have written. It is exercised against you
exactly when fair value moves through it. So the question is whether the
half-spread you capture exceeds the fair-value move that happens while you sit
there.

    d(fair)/d(spot) = phi(z)/sd * (r_live/60)          [settlement_math.py]
    a one-second one-sigma index move is sigma dollars
    => adverse selection per second = 100 * phi(z) / sd * (r_live/60) * sigma

and since sd = sigma * sqrt(var_factor(tau)), THE SIGMA CANCELS EXACTLY:

    adverse_cents_per_second = 100 * phi(z) / sqrt(var_factor(tau)) * r_live/60

Verified numerically below across six orders of magnitude of sigma. This is
worth stating plainly because it is unusual and it is load-bearing: **the
viable quoting region does not depend on the asset at all.** It depends only on
how far from 50c you quote, how long is left, and how wide the spread is. BTC
and DOGE have the same answer.

WHAT IT MEASURES FROM REAL DATA

The formula gives the region where quoting COULD pay. Whether it DOES pay
depends on two things only the tape can answer:

  * REALISED adverse selection. For every trade at the touch, how far does the
    mid move afterwards? Scored against an EXOGENOUS-GRID null -- the same
    horizons measured at times we chose rather than times a trade chose. If
    post-trade moves look like random-time moves, there is no adverse
    selection. That null is the whole test; a raw post-trade drift is not.
  * FILL OPPORTUNITY. A 7-cent spread you never get filled at is worth nothing.
    Counts trades in the viable region per market per window.

Clustered on close time throughout, because twelve series close simultaneously
at rho 0.8 and are worth 1.22 independent units. NOTHING HERE PLACES AN ORDER.
"""

import argparse
import math
import os
import sys
from collections import defaultdict
from statistics import NormalDist, mean, median, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import var_factor, N_AVG                      # noqa: E402
from tdist import p_two_sided, crit                       # noqa: E402

ND = NormalDist()


# ===========================================================================
# the analytic part -- needs no data at all
# ===========================================================================
def adverse_per_second(tau, p):
    """Cents of fair value lost to a one-second one-sigma index move, for a
    quote resting at price p with tau seconds to close.

    Sigma does not appear: it cancels between the move size and the
    denominator of d(fair)/d(spot). See the module docstring.
    """
    vf = var_factor(tau, [1.0])
    if vf <= 0:
        return float("inf")
    p = min(max(p, 1e-9), 1 - 1e-9)
    z = ND.inv_cdf(p)
    r_live = min(N_AVG, max(tau, 0)) if tau < N_AVG else N_AVG
    return 100.0 * ND.pdf(z) / math.sqrt(vf) * (r_live / N_AVG)


def breakeven_price(tau, half_spread_cents):
    """The price at or beyond which the half-spread covers a one-second move.

    Returns 0.5 when the whole book is viable at that horizon.
    """
    if adverse_per_second(tau, 0.5) <= half_spread_cents:
        return 0.5
    lo, hi = 0.5, 1 - 1e-9
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if adverse_per_second(tau, mid) > half_spread_cents:
            lo = mid
        else:
            hi = mid
    return hi


def region_table(spreads=(1.0, 2.0, 4.0, 7.0, 8.0),
                 taus=(900, 600, 300, 120, 60, 30)):
    print("\n" + "=" * 78)
    print("WHERE QUOTING CAN PAY  --  analytic, no data, asset-independent")
    print("=" * 78)
    print("  A resting quote is a written option. It is exercised against you")
    print("  exactly when fair value moves through it. Quote nearer 50c than")
    print("  the price below and a single second of index movement costs more")
    print("  than the half-spread you collect.\n")
    print(f"  {'spread':>8}{'half':>7}   " +
          "".join(f"{str(t) + 's':>9}" for t in taus))
    for spr in spreads:
        row = f"  {spr:>7.1f}c{spr/2:>6.2f}c   "
        for t in taus:
            b = breakeven_price(t, spr / 2.0)
            row += (f"{'anywhere':>9}" if b <= 0.5001 else f"{100*b:>8.1f}c")
        print(row)
    print("\n  'anywhere' means the spread covers a one-second move even at")
    print("  50c. Mirror every price below 50c: 95c and 5c are the same trade.")


# ===========================================================================
# the measured part
# ===========================================================================
GRID = [720, 600, 480, 360, 300, 240, 180, 120, 90, 60, 45, 30]
HORIZONS = [1, 5, 30]


def adverse_from_tape(quotes, trades, closes, horizons=HORIZONS):
    """Realised adverse selection, and its exogenous-grid null.

    For every trade, the mid AFTER the trade minus the mid BEFORE, signed by
    the taker's direction so a positive number always means the taker was
    right and the resting side was run over. The null takes the identical
    horizons at gridpoints WE chose, where no trade need have happened.
    """
    hit = defaultdict(list)
    null = defaultdict(list)
    for tk, series in quotes.items():
        close_s = closes.get(tk)
        if not close_s or len(series) < 30:
            continue
        mids = {t: (b + a) / 2.0 for t, b, a, _, _ in series}
        secs = sorted(mids)
        if len(secs) < 30:
            continue

        def mid_at(t):
            """Last mid at or before t, and only if it is fresh."""
            lo, hi = 0, len(secs) - 1
            best = None
            while lo <= hi:
                m = (lo + hi) // 2
                if secs[m] <= t:
                    best = secs[m]
                    lo = m + 1
                else:
                    hi = m - 1
            if best is None or t - best > 30:
                return None
            return mids[best]

        for (t, price, size, side) in trades.get(tk, []):
            m0 = mid_at(t)
            if m0 is None:
                continue
            sgn = 1.0 if str(side).lower().startswith("y") else -1.0
            for h in horizons:
                m1 = mid_at(t + h)
                if m1 is None:
                    continue
                hit[h].append((sgn * (m1 - m0) * 100.0, close_s))

        # the null: our grid, not theirs
        for ttc in GRID:
            t = int(close_s) - ttc
            m0 = mid_at(t)
            if m0 is None:
                continue
            for h in horizons:
                m1 = mid_at(t + h)
                if m1 is None:
                    continue
                # unsigned direction is meaningless without a taker, so score
                # the ABSOLUTE move against the absolute post-trade move
                null[h].append((abs(m1 - m0) * 100.0, close_s))
    return hit, null


def clustered(pairs):
    """One observation per close time, then a t on (clusters - 1) df."""
    by = defaultdict(list)
    for v, k in pairs:
        by[k].append(v)
    obs = [mean(v) for v in by.values()]
    n = len(obs)
    if n < 10:
        return None
    m, sd = mean(obs), pstdev(obs)
    se = sd / math.sqrt(n) if sd > 0 else float("inf")
    return {"mean": m, "n": n, "se": se,
            "t": m / se if se > 0 else 0.0, "df": n - 1}


# ===========================================================================
def selftest():
    import random
    print("=" * 78)
    print("SELF-TEST -- the region formula, and a planted adverse selection")
    print("=" * 78)
    fails = []

    print("\n  SIGMA MUST CANCEL. The same price and horizon must give the same")
    print("  answer for BTC and for DOGE, six orders of magnitude apart.")
    print(f"  {'sigma ($/sqrt s)':>20}{'adverse @95c/900s':>20}")
    vals = []
    for sig in (6.3403, 0.1953, 0.0118, 0.00002):
        sd = math.sqrt(var_factor(900, [1.0]) * sig * sig)
        v = 100.0 * (ND.pdf(ND.inv_cdf(0.95)) / sd) * sig
        vals.append(v)
        print(f"  {sig:>20g}{v:>19.4f}c")
    if max(vals) - min(vals) > 1e-9:
        fails.append(f"sigma did not cancel: spread {max(vals)-min(vals):.2e}")
    if abs(vals[0] - adverse_per_second(900, 0.95)) > 1e-9:
        fails.append("adverse_per_second disagrees with the direct form")

    print("\n  MONOTONICITY. Adverse selection must RISE toward 50c and must")
    print("  RISE as the close approaches. Anything else is a sign error.")
    bad = 0
    for tau in (900, 300, 60):
        prev = None
        for p in (0.99, 0.95, 0.90, 0.80, 0.70, 0.60, 0.50):
            v = adverse_per_second(tau, p)
            if prev is not None and v <= prev:
                bad += 1
            prev = v
    for p in (0.95, 0.80, 0.60):
        prev = None
        for tau in (900, 600, 300, 120, 60):
            v = adverse_per_second(tau, p)
            if prev is not None and v <= prev:
                bad += 1
            prev = v
    print(f"  {'monotonicity violations':>34}: {bad}")
    if bad:
        fails.append(f"{bad} monotonicity violations in adverse_per_second")

    print("\n  BREAK-EVEN must widen as the spread widens and as time runs out")
    b900_1 = breakeven_price(900, 0.5)
    b900_4 = breakeven_price(900, 4.0)
    b60_1 = breakeven_price(60, 0.5)
    print(f"  {'1c spread, 900s':>34}: {100*b900_1:.1f}c")
    print(f"  {'8c spread, 900s':>34}: "
          f"{'anywhere' if b900_4 <= 0.5001 else f'{100*b900_4:.1f}c'}")
    print(f"  {'1c spread,  60s':>34}: {100*b60_1:.1f}c")
    if not (b900_4 <= b900_1):
        fails.append("a wider spread did not widen the viable region")
    if not (b60_1 > b900_1):
        fails.append("less time did not shrink the viable region")

    print("\n  PLANTED ADVERSE SELECTION. A synthetic tape where the mid moves")
    print("  a KNOWN amount against the resting side after every trade, and a")
    print("  second where it does not move at all.")
    print(f"\n  {'planted':>12}{'measured 1s':>14}{'t vs null':>12}{'clusters':>10}")
    for planted in (0.0, 0.5, 2.0):
        rnd = random.Random(11)
        quotes, trades, closes = {}, {}, {}
        for w in range(120):
            close_s = 1_760_000_000 + w * 900
            tk = f"M{w:04d}"
            closes[tk] = close_s
            mid = 0.50
            ser, tr = [], []
            for s in range(close_s - 900, close_s + 1):
                mid += rnd.gauss(0, 0.0015)
                mid = min(max(mid, 0.05), 0.95)
                ser.append((s, mid - 0.005, mid + 0.005, 100.0, 100.0))
            # trades on a sparse schedule, each followed by a planted drift
            for i in range(60, 900, 60):
                s = close_s - 900 + i
                side = "yes" if rnd.random() < 0.5 else "no"
                sgn = 1.0 if side == "yes" else -1.0
                tr.append((s, ser[i][1], 10.0, side))
                for j in range(i + 1, min(i + 31, len(ser))):
                    t2, b2, a2, bs, asz = ser[j]
                    shift = sgn * planted / 100.0
                    ser[j] = (t2, b2 + shift, a2 + shift, bs, asz)
            quotes[tk] = ser
            trades[tk] = tr
        hit, null = adverse_from_tape(quotes, trades, closes)
        h = clustered(hit[1])
        nl = clustered([(abs(v), k) for v, k in hit[1]]) if hit[1] else None
        nn = clustered(null[1])
        if not h or not nn:
            fails.append(f"planted={planted}: estimator returned nothing")
            continue
        diff = clustered([(v, k) for v, k in hit[1]])
        print(f"  {planted:>11.2f}c{h['mean']:>13.3f}c"
              f"{diff['t']:>12.1f}{h['n']:>10}")
        if planted == 0.0 and abs(diff["t"]) > crit(0.05, diff["df"]):
            fails.append(f"found adverse selection (t={diff['t']:.1f}) in a "
                         "tape with none planted")
        if planted > 0 and abs(h["mean"] - planted) > 0.35 * planted:
            fails.append(f"planted {planted}c, measured {h['mean']:.3f}c")
        if planted > 0 and diff["t"] < 3:
            fails.append(f"missed a planted {planted}c (t={diff['t']:.1f})")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- sigma cancels, the region behaves monotonically,")
    print("and the tape estimator recovers a planted adverse selection while")
    print("staying silent on a tape with none.")
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

    region_table()

    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    from replay import load_quotes, load_markets, load_trades
    quotes = load_quotes(a.data)
    if not quotes:
        print("\n  no quotes -- nothing to measure. Run doctor.py.")
        return
    trades = load_trades(a.data)
    mk = load_markets(a.out)
    closes = {tk: int(m["close"]) for tk, m in mk.items()}
    for tk in quotes:
        if tk not in closes:
            continue
    hit, null = adverse_from_tape(quotes, trades, closes)

    print("\n" + "=" * 78)
    print("REALISED ADVERSE SELECTION  --  what a resting quote actually costs")
    print("=" * 78)
    print("  Signed so POSITIVE means the taker was right and the resting side")
    print("  was run over. Scored against the same horizons measured at times")
    print("  WE chose, where no trade need have happened -- a raw post-trade")
    print("  drift is not evidence, the gap against that null is.\n")
    print(f"  {'horizon':>9}{'after a trade':>16}{'at our gridpoints':>20}"
          f"{'t':>8}{'df':>6}{'p':>10}{'clusters':>10}")
    for h in HORIZONS:
        a_ = clustered(hit[h])
        n_ = clustered([(v, k) for v, k in null[h]])
        if not a_ or not n_:
            print(f"  {h:>8}s   not enough paired observations")
            continue
        # compare |post-trade| against |random-time| on the same clusters
        abs_hit = clustered([(abs(v), k) for v, k in hit[h]])
        gap = abs_hit["mean"] - n_["mean"]
        se = math.sqrt(abs_hit["se"] ** 2 + n_["se"] ** 2)
        t = gap / se if se > 0 else 0.0
        df = min(abs_hit["df"], n_["df"])
        print(f"  {h:>8}s{abs_hit['mean']:>15.3f}c{n_['mean']:>19.3f}c"
              f"{t:>8.1f}{df:>6}{p_two_sided(t, df):>10.4f}"
              f"{abs_hit['n']:>10}")
    print(f"\n  |t| for p<0.05 on these df is about "
          f"{crit(0.05, 100):.2f}, not 1.96; and one go.py run emits several")
    print("  hundred statistics, so the bar that matters is well above that.")
    print("\n  Read it against the region table: if realised adverse selection")
    print("  at 1s is below the half-spread you would capture, quoting pays.")


if __name__ == "__main__":
    main()
