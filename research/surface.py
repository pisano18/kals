#!/usr/bin/env python3
"""surface.py -- WHERE a volatility mispricing is worth crossing the spread
for, and where it is not. Arithmetic only. No data, no tape, no estimator.

    python research/surface.py --selftest
    python research/surface.py --ratio 0.895

WHAT THIS IS FOR

This project has a candidate finding and no map from the finding to a trade.
implied.py and reconcile.py measure

    r = implied sigma / true sigma

and the recorded window puts it at 0.895 overall, with BNB at 0.725 [0.640,
0.814] and three other series' confidence intervals also excluding 1. Suppose
that survives on fresh data. Then what? Which contract, at what price, at how
many seconds to close, and for how much?

Nothing in this repository answers that, and the answer does not need data --
it needs the arithmetic done once, honestly, with the real fee and the real
tick. That is this file. It is deliberately separate from the measurement, so a
change in the estimate never quietly changes the rule.

THE MECHANISM, IN ONE LINE

If the market's sigma is too LOW, its prices are too CONFIDENT: too close to 0
and 1. So the cheap side is always the one below 50c, and you buy it.

Precisely: the market quoting mid price m believes z_m = Phi^-1(m), so it
believes mu - K = z_m * sigma_impl * sqrt(var_factor(tau)). The true z uses the
true sigma, so

    z_true = z_m * (sigma_impl / sigma_true) = z_m * r

and true fair value is Phi(z_m * r). With r < 1 that is closer to 50c than the
market's own price, at every price and every tau. The var_factor cancels
completely, so THE EDGE DOES NOT DEPEND ON TAU AT ALL. That is not an
approximation; it falls out of the inversion. What depends on tau is only
whether anything is quoted there, which is a data question this file does not
pretend to answer.

WHAT IT COSTS TO COLLECT IT

Two things, and both are largest exactly where the edge is largest in
percentage terms:

  * the taker fee, 0.07 * p * (1-p), quadratic and maximal at 50c (1.75c)
  * half the spread on a one-tick-wide book -- and the tick is TAPERED:
    0.1c below 10c and above 90c, 1c in between

The fee falling into the wings and the tick falling into the wings are
independent facts, and together they move the break-even a very long way from
where a flat-tick, flat-fee reading would put it.

WHAT COMES OUT

At r = 0.895 the gross edge is roughly flat in the wings and the cost collapses,
so the net is positive below about 30c and negative above it. That is a
different rule from "trade the biggest mispricing", and it is the opposite of
where the volume is.

WHAT THIS FILE IS NOT

It is not evidence that r < 1. That is implied.py, reconcile.py and term.py, and
the standard for acting on it is the same measurement below 1 on fresh data the
finding has never seen. This file only says what a given r would be worth IF it
is real, so that the answer is already written down when the data arrives and
nobody gets to choose the rule after seeing the result.

It also assumes the market's mu is right and only its sigma is wrong. If the
market is also wrong about mu, none of this applies -- and every measurement in
this project so far says the book leads the index rather than lagging it, so
assuming we can beat it on mu would be unsupported.

NOTHING HERE PLACES AN ORDER.
"""

import argparse
import math
import os
import random
import sys
from statistics import NormalDist, mean, median, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from voltiming import tick_cents, half_spread_c, fee_cents      # noqa: E402

ND = NormalDist()

# Longest a quote may be carried forward on the exogenous grid, matching
# implied.collect().
CARRY_MAX = 30

PRICES = [0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.13, 0.16, 0.20, 0.25,
          0.30, 0.35, 0.40, 0.45, 0.50]
RATIOS = [0.999, 0.95, 0.925, 0.895, 0.85, 0.80, 0.725]


def true_fair(m, r):
    """True probability when the market quotes mid `m` believing a sigma that
    is `r` times the truth. tau cancels; see the header."""
    if not (0.0 < m < 1.0):
        return None
    return ND.cdf(ND.inv_cdf(m) * r)


def gross_cents(m, r):
    """Cents of edge before costs, buying the cheap side at mid `m`.

    Stated for m <= 0.5, where the cheap side is YES. By the symmetry of the
    normal, buying NO at mid 1-m is worth exactly the same, so the table below
    is a table for both.
    """
    f = true_fair(m, r)
    return None if f is None else 100.0 * (f - m)


def cost_cents(m, hs=None):
    """Half-spread plus taker fee, paying the ask.

    `hs` defaults to half the tightest quotable spread -- the BEST case, a
    one-tick book. Pass the observed half-spread instead wherever it is known:
    a 1c spread at 5c is ten ticks, not one, and that single substitution
    moves the net at 5c from +1.66c to +1.21c. The availability table below
    does exactly that.
    """
    if hs is None:
        hs = half_spread_c(m)
    ask = min(m + hs / 100.0, 0.999)
    return hs + fee_cents(ask), hs, fee_cents(ask)


def net_cents(m, r, hs=None):
    g = gross_cents(m, r)
    if g is None:
        return None
    c, _, _ = cost_cents(m, hs)
    return g - c


def kelly(m, r, hs=None):
    """Full-Kelly stake as a fraction of bankroll, buying at the ask.

    A binary bought at price a pays 1 and costs a, so the odds are (1-a)/a and
    f* = (q - a) / (1 - a). Full Kelly is not a recommendation -- it is the
    point past which growth turns negative, and the useful number is some small
    fraction of it. It is here to show scale: a 1c edge at 5c is a far bigger
    Kelly than a 1c edge at 45c, and the cents table alone hides that.
    """
    q = true_fair(m, r)
    if q is None:
        return None
    a = min(m + (half_spread_c(m) if hs is None else hs) / 100.0, 0.999)
    # The fee is paid whatever the outcome, so it is part of the cost of the
    # contract, not a haircut on the winnings. The effective price is a + fee.
    # Omitting it printed a POSITIVE stake on rows whose own NET column said
    # the trade loses: at r=0.895 the 30c row read NET -0.04c and Kelly +2.1%.
    # Full Kelly is the point past which growth turns negative, so a positive
    # number there is not a small overstatement, it is the wrong side of zero.
    a_eff = a + fee_cents(a) / 100.0
    if a_eff >= 1.0 or a_eff <= 0.0:
        return None
    return (q - a_eff) / (1.0 - a_eff)


def breakeven_ratio(m, lo=0.5, hi=1.0, tol=1e-6):
    """The largest r at which price m still just breaks even. Bisection on a
    function that is monotone in r: smaller r means a more overconfident
    market, hence more edge."""
    if net_cents(m, lo) is None or net_cents(m, lo) <= 0:
        return None                       # never pays, even at r = 0.5
    if net_cents(m, hi) > 0:
        return hi
    while hi - lo > tol:
        mid = (lo + hi) / 2.0
        if net_cents(m, mid) > 0:
            lo = mid
        else:
            hi = mid
    return lo


# ===========================================================================
def table(ratio):
    print("=" * 78)
    print(f"THE MAP AT r = implied/true sigma = {ratio:.3f}")
    print("=" * 78)
    print("  Buying the cheap side (YES below 50c, or equivalently NO above")
    print("  it) at the ask, on a one-tick-wide book, paying the taker fee.")
    print(f"\n  {'mid':>6}{'true fair':>11}{'gross':>9}{'tick':>8}"
          f"{'half-sp':>9}{'fee':>8}{'NET':>9}{'Kelly':>9}{'edge/cost':>11}")
    best = None
    for m in PRICES:
        g = gross_cents(m, ratio)
        c, hs, fe = cost_cents(m)
        n = g - c
        k = kelly(m, ratio)
        ratio_ec = (g / c) if c > 0 else float("inf")
        flag = ""
        if n > 0 and (best is None or n > best[1]):
            best = (m, n)
        print(f"  {100*m:>5.0f}c{100*true_fair(m, ratio):>10.2f}c{g:>8.2f}c"
              f"{tick_cents(m):>7.1f}c{hs:>8.2f}c{fe:>7.2f}c{n:>8.2f}c"
              f"{100*k:>8.1f}%{ratio_ec:>10.2f}x{flag}")
    print("\n  A positive NET is a trade that pays after everything the")
    print("  exchange charges. Read edge/cost too: 1.10x is a rounding error")
    print("  away from zero and 5x is not.")
    if best:
        print(f"\n  Best cell: {100*best[0]:.0f}c at {best[1]:+.2f}c net.")
    else:
        print(f"\n  NOTHING pays at r = {ratio:.3f}. The mispricing is real "
              "and still not worth crossing for.")
    return best


def breakevens():
    print("\n" + "=" * 78)
    print("HOW WRONG THE MARKET HAS TO BE, BY PRICE")
    print("=" * 78)
    print("  The largest implied/true ratio at which each price still breaks")
    print("  even. Closer to 1.000 means a SMALLER mispricing suffices, which")
    print("  means the trade is easier to justify, not harder.")
    print(f"\n  {'mid':>6}{'break-even r':>15}{'i.e. sigma error':>19}"
          f"{'cost to cross':>16}")
    for m in PRICES:
        b = breakeven_ratio(m)
        c, _, _ = cost_cents(m)
        if b is None:
            print(f"  {100*m:>5.0f}c{'never':>15}{'--':>19}{c:>15.2f}c")
            continue
        print(f"  {100*m:>5.0f}c{b:>15.3f}{100*(1.0-b):>17.1f}%"
              f"{c:>15.2f}c")
    print("\n  This column is the one to argue about. It says nothing about")
    print("  whether the market IS wrong -- only how wrong it would have to be")
    print("  before the wrongness pays for the fee and the spread.")


def grid():
    print("\n" + "=" * 78)
    print("NET CENTS -- the whole surface")
    print("=" * 78)
    print(f"\n  {'mid':>6}" + "".join(f"{f'r={r:.3f}':>10}" for r in RATIOS))
    for m in PRICES:
        cells = []
        for r in RATIOS:
            n = net_cents(m, r)
            cells.append(f"{n:>+9.2f} " if n is not None else f"{'--':>10}")
        print(f"  {100*m:>5.0f}c" + "".join(cells))
    print("\n  r = 0.999 is the no-mispricing column and every cell in it must")
    print("  be negative: with the market right, crossing a spread and paying")
    print("  a fee is a guaranteed loss. If any cell there is positive this")
    print("  file has an arithmetic bug, and the self-test checks it.")


# ===========================================================================
WING_BUCKETS = [(0.005, 0.02), (0.02, 0.04), (0.04, 0.06), (0.06, 0.08),
                (0.08, 0.10), (0.10, 0.13), (0.13, 0.16), (0.16, 0.20),
                (0.20, 0.25), (0.25, 0.30), (0.30, 0.40), (0.40, 0.50)]


def availability(quotes, ratio):
    """Where is anything actually QUOTED, and at what spread?

    The map above says the best cells are at 5-7c, and it gets there by
    assuming a one-tick book -- 0.1c below 10c. That is a floor on the cost of
    crossing, not a measurement. If the wings are quoted 1c wide, the tick
    taper buys nothing and every cell below 10c loses most of its advantage.
    If they are not quoted at all, the best cells do not exist.

    So this recomputes the net using the OBSERVED median spread per bucket.
    It needs quotes only -- no settlements, no index, no realised sigma -- so
    it runs on however many hours are on disk.
    """
    # ONE PREVAILING QUOTE PER SECOND, not one row per message.
    #
    # The ticker channel is publish-on-change. A tight, competitive book
    # republishes orders of magnitude more often than a dead wide one, so a
    # median taken over raw messages is dragged toward the tightest book in
    # the bucket -- and the whole point of this table is the WIDE ones.
    # Measured on a fixture: two markets in the 4-6c bucket over the same
    # 1,000 seconds, one 1c wide firing 10 messages a second and one 6c wide
    # firing one every ten seconds. Over messages the median spread is 1.00c
    # and the bucket reads +1.19c, "this pays". Over a per-second grid it is
    # 6c and reads -1.47c. A sign flip on this file's central deliverable.
    #
    # implied.collect() has built exactly this grid since the occupation-time
    # fix, for exactly this reason. This is the same bias in a new file.
    per_sec = {}
    for ticker, q in quotes.items():
        last = {}
        for rec in q:
            bid, ask = rec[1], rec[2]
            if 0.0 < bid < ask < 1.0:
                last[int(rec[0])] = (bid, ask)
        if not last:
            continue
        secs = sorted(last)
        grid, cur, j = [], None, 0
        for t in range(secs[0], secs[-1] + 1):
            while j < len(secs) and secs[j] <= t:
                cur = (secs[j], last[secs[j]])
                j += 1
            if cur is not None and t - cur[0] <= CARRY_MAX:
                grid.append(cur[1])
        per_sec[ticker] = grid

    rows = []
    for lo, hi in WING_BUCKETS:
        n, sp, by_mkt = 0, [], {}
        for ticker, grid in per_sec.items():
            mine = []
            for bid, ask in grid:
                mid = (bid + ask) / 2.0
                if lo <= min(mid, 1.0 - mid) < hi:
                    mine.append(ask - bid)
            if mine:
                n += len(mine)
                sp.extend(mine)
                by_mkt[ticker] = median(mine)
        m = (lo + hi) / 2.0
        if not n:
            rows.append({"band": (lo, hi), "n": 0, "markets": 0,
                         "spread": None, "mkt_spread": None,
                         "net": None, "mkt_net": None,
                         "best": net_cents(m, ratio)})
            continue
        med = median(sp)
        # ...and the same thing again with ONE observation per market, which
        # is the project's own clustering rule. Where the two disagree, the
        # bucket is a few markets pretending to be many.
        mmed = median(list(by_mkt.values()))
        rows.append({"band": (lo, hi), "n": n, "markets": len(by_mkt),
                     "spread": med, "mkt_spread": mmed,
                     "net": net_cents(m, ratio, hs=100.0 * med / 2.0),
                     "mkt_net": net_cents(m, ratio, hs=100.0 * mmed / 2.0),
                     "best": net_cents(m, ratio)})
    return rows


def availability_table(rows, ratio):
    print("\n" + "=" * 78)
    print("IS THE MAP REACHABLE? -- observed quotes, observed spreads")
    print("=" * 78)
    print("  The map above assumed a one-tick book. This uses the spread")
    print("  actually resting there, on an EXOGENOUS one-second grid -- one")
    print("  prevailing quote per second, not one row per message. A tight")
    print("  book republishes far more often than a wide one, so a median")
    print("  over messages is dragged toward the tightest book in the bucket,")
    print("  which is the opposite of what this table is for.")
    print(f"\n  {'cheap side':>11}{'quote-secs':>11}{'mkts':>6}"
          f"{'spread':>9}{'ticks':>6}{'@1 tick':>9}{'NET grid':>10}"
          f"{'per-mkt sp':>11}{'NET/mkt':>9}")
    reach = None
    for r_ in rows:
        lo, hi = r_["band"]
        lbl = f"{100*lo:.0f}-{100*hi:.0f}c"
        m = (lo + hi) / 2.0
        if not r_["n"]:
            # The 'at one tick' column exists to answer "what would this
            # bucket be worth if it WERE quoted", so printing 0.00c for the
            # unquoted buckets -- the only ones the question is about --
            # answers the wrong question with a fabricated number.
            print(f"  {lbl:>11}{0:>11}{'--':>6}{'--':>9}{'--':>6}"
                  f"{r_['best']:>8.2f}c{'never quoted':>10}"
                  f"{'--':>11}{'--':>9}")
            continue
        ticks = 100.0 * r_["spread"] / tick_cents(m)
        # The PER-MARKET net is the one to act on: it is the project's own
        # clustering rule, one observation per market.
        if r_["mkt_net"] is not None and (reach is None
                                          or r_["mkt_net"] > reach[1]):
            reach = (lbl, r_["mkt_net"], r_["n"], r_["markets"])
        print(f"  {lbl:>11}{r_['n']:>11,}{r_['markets']:>6}"
              f"{100*r_['spread']:>8.2f}c{ticks:>6.1f}"
              f"{r_['best']:>8.2f}c{r_['net']:>9.2f}c"
              f"{100*r_['mkt_spread']:>10.2f}c{r_['mkt_net']:>8.2f}c")
    print("\n  'ticks' is the observed spread over the tightest the exchange")
    print("  allows there. A 1c spread at 5c is TEN ticks and the whole")
    print("  advantage of the tapered tick is gone.")
    print("\n  NET grid weights every second the quote stood. NET/mkt takes")
    print("  one median per market and then the median of those. Where they")
    print("  disagree the bucket is a few markets pretending to be many, and")
    print("  NET/mkt is the honest one.")
    if reach:
        print(f"\n  Best REACHABLE cell at r={ratio:.3f}, per market: "
              f"{reach[0]} at {reach[1]:+.2f}c net, over {reach[2]:,} "
              f"quote-seconds in {reach[3]:,} markets.")
        if reach[1] <= 0:
            print("  That is not positive. On the spreads actually quoted,")
            print("  this mispricing does not pay anywhere.")
    else:
        print("\n  Nothing quoted in any wing bucket. The map is unreachable")
        print("  on this tape, and that is the finding.")
    print("\n  Read quote-seconds and mkts before reading any net. A bucket")
    print("  with 400 quote-seconds in 3 markets is one accident.")


# ===========================================================================
def _simulate(m_lo, m_hi, r, n_win, seed, sig=6.0, step=5):
    """One continuous tape, windows on top of it, settlement as the exchange
    computes it. Returns (close, entry mid, realised P&L, tau, EXPECTED P&L)
    per window, where the expected P&L uses the true conditional probability
    at entry and therefore carries no outcome noise at all.

    The strike is the mean of the sixty prints ending at the OPEN -- which is
    `strike(N+1) == settle(N)`, the rule the exchange uses, and the rule that
    cannot see the future. endgame.py shipped broken for months on a fixture
    that drew the strike from the settlement value instead, so this is written
    out rather than assumed.
    """
    from engine import var_factor, N_AVG
    from settlewin import partial
    rng = random.Random(seed)
    T0 = 1_760_000_000
    px, ticks = 80_000.0, {}
    for k in range(N_AVG + n_win * 900 + 2):
        px += rng.gauss(0, sig)
        ticks[T0 + k] = px
    sig_impl = r * sig
    out = []
    for w in range(n_win):
        open_s = T0 + N_AVG + w * 900
        close_s = open_s + 900
        if close_s not in ticks:
            break
        strike = sum(ticks[s] for s in
                     range(open_s - N_AVG + 1, open_s + 1)) / N_AVG
        settle = sum(ticks[s] for s in
                     range(close_s - N_AVG + 1, close_s + 1)) / N_AVG
        won = 1.0 if settle > strike else 0.0
        for t in range(open_s, close_s, step):
            pt = partial(ticks, close_s, t)
            if pt is None:
                continue
            locked, rem = pt
            mu = (locked + rem * ticks[t]) / N_AVG
            sd = sig_impl * math.sqrt(var_factor(close_s - t, [1.0]))
            if sd <= 0:
                continue
            mid = ND.cdf((mu - strike) / sd)
            cheap = mid if mid <= 0.5 else 1.0 - mid
            if not (m_lo <= cheap <= m_hi):
                continue
            hs = half_spread_c(cheap)
            ask = cheap + hs / 100.0
            w_ = won if mid <= 0.5 else 1.0 - won
            # The TRUE conditional probability of the side we bought, from
            # the tape and the true sigma. Costs nothing to compute and
            # carries no outcome noise, which is what makes the arithmetic
            # check below able to see a missing fee.
            sd_true = sig * math.sqrt(var_factor(close_s - t, [1.0]))
            p_yes = ND.cdf((mu - strike) / sd_true)
            q = p_yes if mid <= 0.5 else 1.0 - p_yes
            out.append((close_s, cheap,
                        100.0 * (w_ - ask) - fee_cents(ask), close_s - t,
                        100.0 * (q - ask) - fee_cents(ask)))
            break                      # ONE trade per window. Every fill in a
                                       # window settles on the same outcome.
    return out


# ===========================================================================
def selftest():
    print("=" * 78)
    print("SELF-TEST -- against known answers")
    print("=" * 78)
    fails = []

    # --- 1. the tapered tick is the API's, not a guess --------------------
    print("\n  The tick, from the API's price_ranges:")
    for p, want in ((0.02, 0.1), (0.05, 0.1), (0.099, 0.1), (0.10, 1.0),
                    (0.50, 1.0), (0.899, 1.0), (0.95, 0.1)):
        got = tick_cents(p)
        print(f"    {100*p:>6.1f}c -> {got:>4.1f}c")
        if abs(got - want) > 1e-9:
            fails.append(f"tick at {p} is {got}, not {want}")

    # --- 2. the fee is the published quadratic ----------------------------
    print("\n  The fee, 0.07 * p * (1-p), in cents:")
    for p, want in ((0.50, 1.75), (0.16, 0.9408), (0.10, 0.63), (0.05, 0.3325),
                    (0.02, 0.1372)):
        got = fee_cents(p)
        print(f"    {100*p:>6.1f}c -> {got:>6.4f}c")
        if abs(got - want) > 1e-4:
            fails.append(f"fee at {p} is {got:.4f}, not {want}")

    # --- 3. r = 1 must pay nothing, anywhere ------------------------------
    print("\n  With the market exactly right (r = 1) every cell must lose:")
    worst = None
    for m in PRICES:
        n = net_cents(m, 1.0)
        if n is None:
            continue
        if worst is None or n > worst[1]:
            worst = (m, n)
        if n > 0:
            fails.append(f"r=1 pays {n:+.3f}c at {100*m:.0f}c -- free money "
                         "from a market that is not wrong")
    print(f"    best cell at r=1: {100*worst[0]:.0f}c at {worst[1]:+.3f}c "
          "(must be negative)")

    # --- 4. THE BIG ONE: settle real contracts and check the P&L ----------
    # Everything above is arithmetic about arithmetic. This builds a real
    # 900-second tape, settles on the mean of the last sixty prints exactly as
    # the exchange does, has the market quote through the exact variance
    # formula with a sigma that is r times the truth, buys the cheap side at
    # the ask, pays the fee, and holds to settlement.
    #
    # It tests the two claims that the arithmetic checks cannot reach: that
    # the 60-print averaging really does make settle-given-now Gaussian with
    # variance sigma^2 * var_factor(tau), and that TAU CANCELS -- the mean tau
    # column below moves by a factor of two across cells while the analytic
    # net, which contains no tau at all, still matches.
    print("\n  SIMULATION. Real 900s windows, real 60-print settlement, the")
    print("  market quoting r times the true sigma. One trade per window, at")
    print("  the first second the cheap side lands in the bucket -- so no")
    print("  quote from later in the window can influence the entry.")
    print(f"\n  {'bucket':>10}{'r':>7}{'trades':>8}{'analytic':>11}"
          f"{'simulated':>11}{'se':>7}{'t(diff)':>9}{'mean tau':>10}")
    N_WIN = 6000
    for (lo, hi), r in (((0.14, 0.18), 0.895), ((0.04, 0.06), 0.895),
                        ((0.33, 0.37), 0.85), ((0.14, 0.18), 0.999)):
        tr = _simulate(lo, hi, r, n_win=N_WIN, seed=11)
        if len(tr) < 100:
            fails.append(f"the {100*lo:.0f}-{100*hi:.0f}c bucket produced "
                         f"{len(tr)} trades -- nothing was tested there")
            continue
        pn = [x[2] for x in tr]
        mm = mean(x[1] for x in tr)
        ana = net_cents(mm, r)
        se = pstdev(pn) / math.sqrt(len(pn))
        t = (mean(pn) - ana) / se if se > 0 else 0.0
        print(f"  {f'{100*lo:.0f}-{100*hi:.0f}c':>10}{r:>7.3f}{len(pn):>8}"
              f"{ana:>10.3f}c{mean(pn):>10.3f}c{se:>7.3f}{t:>9.2f}"
              f"{mean(x[3] for x in tr):>10.0f}")
        if abs(t) > 3.5:
            fails.append(f"simulated P&L in {100*lo:.0f}-{100*hi:.0f}c at "
                         f"r={r} is {mean(pn):.3f}c against an analytic "
                         f"{ana:.3f}c -- {t:.1f} standard errors apart")
        if r > 0.99 and mean(pn) > 0:
            fails.append(f"a market that is RIGHT paid {mean(pn):+.3f}c in "
                         f"the {100*lo:.0f}-{100*hi:.0f}c bucket")
    print(f"\n  Resolution: about {0.5:.1f}c per cell at {N_WIN:,} windows.")
    print("  This catches a sign error, a missing cost, or a tau dependence.")
    print("  It would NOT catch a 0.2c error, and nothing here claims it does.")

    # --- 4a. THE ARITHMETIC, with the outcome noise removed ---------------
    # The settled simulation above has a per-cell se of about 0.5c, so its MDE
    # is ~1.8c -- larger than every analytic net in the table and larger than
    # the fee at every price tested. Deleting the entire taker fee from
    # cost_cents left the whole self-test PASSING. A check that cannot see the
    # cost it exists to verify is decoration.
    #
    # So: same simulated trades, same entries, but score each one by its TRUE
    # conditional probability instead of a coin flip. That has zero outcome
    # variance, so any disagreement with the analytic net is arithmetic.
    print("\n  THE SAME TRADES, SCORED WITHOUT OUTCOME NOISE. Every entry")
    print("  above, valued at its true conditional probability rather than a")
    print("  settled coin flip. Nothing here is statistics: a gap is a bug in")
    print("  the arithmetic, and the tolerance is 0.05c rather than 1.8c.")
    print(f"\n  {'bucket':>10}{'r':>7}{'trades':>8}{'analytic':>11}"
          f"{'exact':>10}{'gap':>9}")
    for (lo, hi), r in (((0.14, 0.18), 0.895), ((0.04, 0.06), 0.895),
                        ((0.33, 0.37), 0.85), ((0.14, 0.18), 0.999)):
        tr = _simulate(lo, hi, r, n_win=N_WIN, seed=11)
        if len(tr) < 100:
            continue
        mm = mean(x[1] for x in tr)
        ana = net_cents(mm, r)
        exact = mean(x[4] for x in tr)
        print(f"  {f'{100*lo:.0f}-{100*hi:.0f}c':>10}{r:>7.3f}{len(tr):>8}"
              f"{ana:>10.3f}c{exact:>9.3f}c{exact - ana:>+8.3f}c")
        if abs(exact - ana) > 0.05:
            fails.append(f"analytic net {ana:.3f}c in {100*lo:.0f}-"
                         f"{100*hi:.0f}c at r={r} but the exact pathwise "
                         f"value is {exact:.3f}c -- {exact-ana:+.3f}c apart, "
                         "which is arithmetic, not noise")

    # --- 4b. the availability table must use the OBSERVED spread ----------
    print("\n  AVAILABILITY. Feed it a book quoted one tick wide and a book")
    print("  quoted ten ticks wide at the same prices. The net must fall,")
    print("  because a wide spread costs what it costs whatever the tick is.")
    def _book(width):
        q = {}
        for i in range(40):
            recs = []
            for k, m in enumerate((0.05, 0.07, 0.12, 0.22)):
                recs.append((1000 + k, m - width / 2.0, m + width / 2.0,
                             100, 100))
            q[f"T{i}"] = recs
        return q
    tight = availability(_book(0.001), 0.895)
    wide = availability(_book(0.010), 0.895)
    print(f"\n  {'cheap side':>12}{'1-tick net':>13}{'10-tick net':>14}")
    for a_, b_ in zip(tight, wide):
        if a_["n"] and b_["n"]:
            lo, hi = a_["band"]
            print(f"  {f'{100*lo:.0f}-{100*hi:.0f}c':>12}"
                  f"{a_['net']:>12.2f}c{b_['net']:>13.2f}c")
            if b_["net"] >= a_["net"]:
                fails.append(f"a ten-tick spread in {100*lo:.0f}-{100*hi:.0f}c "
                             "was not costlier than a one-tick one -- the "
                             "observed spread is being ignored")
    if not any(x["n"] for x in tight):
        fails.append("the availability table found no quotes in a book that "
                     "quotes 4 prices in 40 markets")
    # a bucket nothing quotes must report never-quoted, not a number
    empty = [x for x in tight if not x["n"]]
    if not empty:
        fails.append("every bucket reported quotes, including ones the "
                     "fixture never quoted in")

    # --- 5. the NO side must be worth exactly the same --------------------
    print("\n  Symmetry: buying NO at mid 1-m must be worth what buying YES")
    print("  at m is worth. If it is not, one of the two is mis-stated.")
    for m in (0.05, 0.16, 0.30):
        a = gross_cents(m, 0.895)
        # buying NO at mid (1-m) means paying (1-(1-m)) = m for the NO side,
        # whose true probability is 1 - true_fair(1-m).
        b = 100.0 * ((1.0 - true_fair(1.0 - m, 0.895)) - m)
        print(f"    YES at {100*m:>4.0f}c: {a:>7.3f}c    "
              f"NO at {100*(1-m):>4.0f}c: {b:>7.3f}c")
        if abs(a - b) > 1e-9:
            fails.append(f"YES at {m} is worth {a:.4f}c but NO at {1-m} is "
                         f"worth {b:.4f}c")

    # --- 6. break-even must invert net_cents ------------------------------
    print("\n  The break-even r must actually be the zero of the net:")
    ok = True
    for m in (0.05, 0.16, 0.30, 0.45):
        b = breakeven_ratio(m)
        if b is None:
            print(f"    {100*m:>4.0f}c: never pays")
            continue
        below, above = net_cents(m, b - 1e-3), net_cents(m, b + 1e-3)
        print(f"    {100*m:>4.0f}c: r*={b:.4f}  net just below {below:+.4f}c, "
              f"just above {above:+.4f}c")
        if not (below > 0 >= above):
            ok = False
            fails.append(f"break-even at {m} is r={b:.4f} but the net does "
                         "not change sign across it")
    if ok:
        print("    (sign changes at every break-even, as it must)")

    # --- 7. monotone in r -------------------------------------------------
    for m in (0.05, 0.20, 0.45):
        vals = [net_cents(m, r) for r in (0.99, 0.95, 0.90, 0.85, 0.80)]
        if any(b <= a for a, b in zip(vals, vals[1:])):
            fails.append(f"net at {m} is not increasing as r falls: {vals}")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- tick and fee match the API, a market that is")
    print("right pays nothing anywhere, the analytic edge matches a settled")
    print("simulation to inside its CI, the two sides are symmetric, and the")
    print("break-even really is where the net changes sign.")
    return True


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ratio", type=float, default=0.895,
                    help="implied/true sigma. 0.895 is the recorded window's "
                         "median; 0.725 is BNB's point estimate.")
    ap.add_argument("--data", default="./kalshi_data",
                    help="if quotes are found here, the map is re-costed with "
                         "the spreads actually quoted")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed")
    print()
    table(a.ratio)
    breakevens()
    grid()

    # The map above is a floor on cost. If there are quotes on disk, replace
    # the assumed one-tick spread with the one actually resting there. This
    # needs quotes ONLY -- no settlements, no index -- so it runs on any tape.
    try:
        from replay import load_quotes
        quotes = load_quotes(a.data)
    except Exception as e:
        quotes = None
        # Wording matters here: go.py scans stage output for loader-failure
        # markers and /\bno quotes\b/ is one of them. The MAP above needs no
        # data and is a real result, so tripping that marker would flag this
        # whole stage EMPTY and tell the reader to discard it. markers.py
        # checks this.
        print(f"\n  (availability skipped: {type(e).__name__}: {e})")
    if quotes:
        availability_table(availability(quotes, a.ratio), a.ratio)
    else:
        print("\n" + "=" * 78)
        print("  NOTHING QUOTED ON DISK, so every cost above is the best")
        print("  case: a one-tick book. Point --data at kalshi_data to")
        print("  re-cost the map with the spreads actually quoted. Until")
        print("  then the 5-7c cells are a hypothesis about liquidity, not a")
        print("  measurement of it.")
        print("=" * 78)
    print("\n" + "=" * 78)
    print("READ THIS BEFORE READING ANYTHING ABOVE")
    print("=" * 78)
    print("  Every number here is conditional on r being real. It is not")
    print("  evidence for r. The three things that would have to hold before")
    print("  any of it is actionable:")
    print("   1. implied/settle below 1 on FRESH data the finding has never")
    print("      seen -- not the window it was found in.")
    print("   2. quotes actually resting in the wings at a spread near the")
    print("      tick. The map assumes a one-tick book, which is a FLOOR on")
    print("      the cost and not a measurement -- ZEC quotes 7c and NEAR 8c")
    print("      and neither is tradeable at any tick. The availability table")
    print("      re-costs every cell with the spread actually quoted; read it")
    print("      instead of the map wherever it has data.")
    print("   3. the market wrong about SIGMA and right about MU. If it is")
    print("      also wrong about mu, the sign of all of this is unknown.")


if __name__ == "__main__":
    main()
