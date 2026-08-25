#!/usr/bin/env python3
# VERSION: 2026-08-25-v1
"""
viability.py -- what is an edge actually WORTH, and when would you know?

    python research/viability.py
    python research/viability.py --edge 0.01 --price 0.90 --trades 30 --bankroll 5000

Every other tool here answers "is there an edge". This answers the question that
follows, which is the one that decides whether to deploy money:

    given an edge of this size, at this price, this often -- what is the Sharpe,
    what does a bad month look like, how much capital does it need, and how long
    before you could tell it apart from luck?

THE CORRECTION THAT MATTERS MOST

The obvious calculation is badly wrong here, and wrong in the dangerous
direction. A 1c edge at 90c has a per-trade Sharpe of 0.01/sqrt(0.09) = 0.033.
Thirty trades a day looks like 0.033*sqrt(30) = 0.18 daily, which annualises to
about 3.5. That would be an outstanding strategy.

But the twelve crypto series close SIMULTANEOUSLY and are ~0.8 correlated, so
thirty trades a day are not thirty independent bets. PLAN sec.5 puts twelve
correlated series at **1.22 effective independent units**. Thirty trades spread
across twelve series is closer to three independent bets per day, and the annual
Sharpe falls to about 1.1.

That is a factor of THREE, and it lands entirely on position sizing and on how
long a losing streak to expect. Getting it wrong is how a strategy that looked
like a machine turns into a drawdown nobody planned for.

WHAT THIS DELIBERATELY DOES NOT DO
It does not tell you whether an edge exists. It takes the edge as an assumption
and prices the consequences. Feed it a MEASURED edge from replay.py or
cross.py -- never a modelled one.
"""

import argparse
import math
import random
from statistics import NormalDist, mean, pstdev

ND = NormalDist()


def fee(p):
    """Kalshi quadratic taker fee, large-order limit."""
    return 0.07 * p * (1 - p)


def tick(p):
    return 0.001 if (p > 0.90 or p < 0.10) else 0.01


def effective_independent(n_trades, n_series=12, rho=0.8):
    """Trades spread across correlated, simultaneously-closing series.

    With n series of pairwise correlation rho, the variance of their average is
    (1 + (n-1)*rho)/n of a single one, so the effective independent count is
    n / (1 + (n-1)*rho). At n=12, rho=0.8 that is 1.22."""
    per_cluster = max(n_trades / max(n_series, 1), 1e-9)
    eff_series = n_series / (1.0 + (n_series - 1) * rho)
    return per_cluster * eff_series


def analyse(edge, price, trades_per_day, bankroll, kelly_frac, n_series, rho,
            pay_spread=True):
    q = price
    cost = fee(q) + (tick(q) if pay_spread else 0.0)
    net = edge - cost
    sd_trade = math.sqrt(q * (1 - q))

    eff_per_day = effective_independent(trades_per_day, n_series, rho)
    naive_per_day = trades_per_day

    def sharpe(n_per_day):
        if net <= 0:
            return 0.0
        return (net / sd_trade) * math.sqrt(n_per_day) * math.sqrt(365)

    sh_naive, sh_real = sharpe(naive_per_day), sharpe(eff_per_day)

    # Kelly must be sized on the CLUSTER, not the trade.
    #
    # The classical fraction (p-q)/(1-q) assumes independent bets. Here up to
    # `n_series` legs fire at the same instant on ~0.8-correlated underlyings,
    # so they are close to ONE bet at n_series times the stake, not n_series
    # separate ones. Sizing per-trade and letting them stack is what produced a
    # simulated median drawdown of 116% of bankroll -- i.e. ruin -- at what
    # looked like a conservative quarter-Kelly.
    f_full = max(net, 0.0) / (1.0 - q) if q < 1 else 0.0
    f_used = f_full * kelly_frac
    stake_cluster = f_used * bankroll          # the whole simultaneous cluster
    legs = max(min(trades_per_day, n_series), 1)
    contracts = int(stake_cluster / (q * legs)) if q > 0 else 0
    daily = contracts * net * trades_per_day
    return {"cost": cost, "net": net, "sd": sd_trade, "eff_per_day": eff_per_day,
            "sharpe_naive": sh_naive, "sharpe_real": sh_real,
            "f_full": f_full, "f_used": f_used, "contracts": contracts,
            "daily": daily}


def drawdown_sim(net, q, contracts, trades_per_day, n_series, rho, days=365,
                 reps=400, seed=1):
    """Simulate the equity path, with the correlation actually applied: within a
    close-time cluster the outcomes share a common factor, so the twelve legs
    win and lose together far more often than independence would suggest."""
    rnd = random.Random(seed)
    per_cluster = max(int(round(trades_per_day / max(n_series, 1))), 1)
    finals, maxdd, losing_months = [], [], 0
    for _ in range(reps):
        eq, peak, dd = 0.0, 0.0, 0.0
        month, m_start = 0, 0.0
        for d in range(days):
            for _c in range(per_cluster):
                # one common shock per cluster, then idiosyncratic per series
                common = rnd.gauss(0, math.sqrt(rho))
                for _s in range(n_series):
                    z = common + rnd.gauss(0, math.sqrt(1 - rho))
                    p_win = q + net
                    # map the correlated normal to the binary outcome
                    win = ND.cdf(z) < p_win
                    eq += contracts * ((1 - q) if win else -q)
                    eq -= contracts * 0.0     # net already includes cost
            peak = max(peak, eq)
            dd = max(dd, peak - eq)
            if (d + 1) % 30 == 0:
                if eq - m_start < 0:
                    losing_months += 1
                m_start = eq
                month += 1
        finals.append(eq)
        maxdd.append(dd)
    finals.sort(); maxdd.sort()
    n_months = max(days // 30, 1) * reps
    return {"median_year": finals[len(finals) // 2],
            "p05_year": finals[int(0.05 * len(finals))],
            "p95_year": finals[int(0.95 * len(finals))],
            "median_maxdd": maxdd[len(maxdd) // 2],
            "p95_maxdd": maxdd[int(0.95 * len(maxdd))],
            "losing_month_rate": losing_months / n_months}


def trades_to_significance(net, q, target_t=2.0, n_series=12, rho=0.8):
    """How many trades before the edge is distinguishable from zero, with the
    correlation penalty applied."""
    if net <= 0:
        return float("inf")
    sd = math.sqrt(q * (1 - q))
    n_eff = (target_t * sd / net) ** 2
    inflate = (1.0 + (n_series - 1) * rho) / 1.0
    return n_eff * inflate / n_series * n_series, n_eff


def hedge_table(S=78788.0, sigma=5.92, bps=3.0):
    """Can a Kalshi binary be delta-hedged with a crypto perp? No, and the
    margin is enormous rather than marginal.

    A $1-payout binary near the money has a huge delta w.r.t. the underlying,
    because the payoff is a step function: d(P)/d(S) = phi(z)/sd * (r_live/60),
    and sd collapses toward expiry. At 30s to close that is ~$1,600 of BTC
    exposure to hedge ONE contract that can never pay more than $1.

    Round-tripping that at 3bp -- about the best a retail perp account gets --
    costs multiples of any edge being hunted. This closes cross-venue delta
    hedging permanently and forces every strategy to be self-hedging (paired
    Kalshi legs) or deliberately unhedged and sized for it."""
    print("=" * 78)
    print("CAN YOU DELTA-HEDGE WITH A PERP?  (spoiler: no, by 1-2 orders)")
    print("=" * 78)
    print(f"  {'ttc':>6}{'sd($)':>10}{'d(P)/d(S)':>12}"
          f"{'$ BTC per contract':>21}{'round trip @3bp':>18}")
    for tau in (900, 300, 120, 60, 30):
        r_live = min(tau, 60)
        var = (tau - 39.4972) if tau >= 60 else \
            tau * (tau + 1) * (2 * tau + 1) / 6.0 / 3600.0
        sd = math.sqrt(var) * sigma
        dPdS = 0.3989422804 / sd * (r_live / 60.0)
        usd = dPdS * S
        cost = usd * bps / 10000.0 * 2
        print(f"  {tau:>6}{sd:>10.1f}{100*dPdS:>11.4f}c{usd:>20.2f}"
              f"{100*cost:>17.2f}c")
    print("\n  Against edges of 0.5-2c per contract, hedging costs 10.9c at")
    print("  900s and 98c at 30s. That is 5x to 200x the edge, at every")
    print("  maturity, for the cheapest perp fees a retail account can get.")
    print("\n  => CROSS-VENUE DELTA HEDGING IS PERMANENTLY UNECONOMIC HERE.")
    print("     Not 'depends on fees' -- off by one to two orders of magnitude.")
    print("     Consequence: every strategy must be SELF-HEDGING (paired Kalshi")
    print("     legs, e.g. the cross-sectional trade) or deliberately unhedged")
    print("     and sized for the full loss. There is no third option.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hedge", action="store_true",
                    help="price a perp delta hedge and close the question")
    ap.add_argument("--edge", type=float, default=None,
                    help="gross edge in dollars, e.g. 0.01 for one cent")
    ap.add_argument("--price", type=float, default=0.90)
    ap.add_argument("--trades", type=float, default=30)
    ap.add_argument("--bankroll", type=float, default=5000)
    ap.add_argument("--kelly", type=float, default=0.25)
    ap.add_argument("--series", type=int, default=12)
    ap.add_argument("--rho", type=float, default=0.8)
    a = ap.parse_args()

    print("=" * 78)
    print("WHAT AN EDGE IS WORTH")
    print("=" * 78)
    print("  Feed this a MEASURED edge, never a modelled one. It assumes the")
    print("  edge is real and prices the consequences.\n")

    if a.hedge:
        hedge_table()
        return

    if a.edge is None:
        print("  SURVEY -- net of the real quadratic fee and one tick of spread")
        print(f"  {'gross':>8}{'price':>8}{'cost':>8}{'net':>8}"
              f"{'Sharpe naive':>14}{'Sharpe real':>13}   verdict")
        for price in (0.50, 0.75, 0.90, 0.95):
            for edge in (0.005, 0.01, 0.02, 0.05):
                r = analyse(edge, price, a.trades, a.bankroll, a.kelly,
                            a.series, a.rho)
                v = ("dead" if r["net"] <= 0 else
                     "marginal" if r["sharpe_real"] < 0.7 else
                     "worth it" if r["sharpe_real"] < 1.5 else "strong")
                print(f"  {100*edge:>7.1f}c{100*price:>7.0f}c"
                      f"{100*r['cost']:>7.2f}c{100*r['net']:>+7.2f}c"
                      f"{r['sharpe_naive']:>14.2f}{r['sharpe_real']:>13.2f}"
                      f"   {v}")
            print()
        print("  Read the two Sharpe columns together. 'naive' treats every")
        print("  trade as independent. 'real' accounts for twelve series that")
        print("  close at the same instant and are ~0.8 correlated, which PLAN")
        print("  sec.5 puts at 1.22 effective independent units. The gap is")
        print("  roughly 3x and it is the difference between a machine and a")
        print("  drawdown you did not plan for.")
        print("\n  Note the whole 50c column: at 50c a 2c gross edge is barely")
        print("  alive once you pay 1.75c of fee plus a 1c tick. Cheap trading")
        print("  lives at 90-95c, which is exactly where PLAN sec.2 pointed --")
        print("  that part of v2 was right.")
        print("\n  Re-run with --edge to price one specific candidate, e.g.")
        print("    python research/viability.py --edge 0.01 --price 0.90")
        return

    r = analyse(a.edge, a.price, a.trades, a.bankroll, a.kelly, a.series, a.rho)
    print(f"  assumption: {100*a.edge:.2f}c gross edge at {100*a.price:.0f}c, "
          f"{a.trades:.0f} trades/day, ${a.bankroll:,.0f} bankroll")
    print(f"\n  cost per contract      {100*r['cost']:>8.2f}c   "
          f"(fee {100*fee(a.price):.2f}c + tick {100*tick(a.price):.2f}c)")
    print(f"  net edge               {100*r['net']:>+8.2f}c")
    if r["net"] <= 0:
        print("\n  *** The edge does not survive costs. Nothing else matters. ***")
        return
    print(f"  effective independent bets/day  {r['eff_per_day']:>6.2f}   "
          f"(vs {a.trades:.0f} nominal)")
    print(f"  annualised Sharpe      {r['sharpe_real']:>8.2f}   "
          f"(naive, wrongly, {r['sharpe_naive']:.2f})")
    legs = max(min(a.trades, a.series), 1)
    print(f"\n  Kelly stake fraction   {r['f_full']:>8.4f} full, "
          f"{r['f_used']:.4f} at {a.kelly:g}x")
    print(f"  sized on the CLUSTER, not the trade: up to {legs:.0f} legs fire")
    print(f"  together on ~{a.rho:g}-correlated underlyings, so they are close")
    print(f"  to one bet, not {legs:.0f} independent ones.")
    print(f"  position               {r['contracts']:>8,} contracts per leg "
          f"(${r['contracts']*a.price*legs:,.0f} at risk across the cluster)")
    print(f"  expected              ${r['daily']:>8,.2f} /day, "
          f"${r['daily']*365:,.0f} /year on ${a.bankroll:,.0f}")

    print("\n  SIMULATED YEAR (correlation applied WITHIN each close-time"
          " cluster)")
    d = drawdown_sim(r["net"], a.price, r["contracts"], a.trades, a.series,
                     a.rho)
    print(f"    median year          ${d['median_year']:>10,.0f}")
    print(f"    5th percentile year  ${d['p05_year']:>10,.0f}")
    print(f"    95th percentile      ${d['p95_year']:>10,.0f}")
    print(f"    median max drawdown  ${d['median_maxdd']:>10,.0f}   "
          f"({100*d['median_maxdd']/a.bankroll:.1f}% of bankroll)")
    print(f"    95th pct drawdown    ${d['p95_maxdd']:>10,.0f}   "
          f"({100*d['p95_maxdd']/a.bankroll:.1f}%)")
    print(f"    losing months        {100*d['losing_month_rate']:>10.0f}%")

    n_tot, n_eff = trades_to_significance(r["net"], a.price, 2.0, a.series,
                                          a.rho)
    days = n_tot / max(a.trades, 1e-9)
    print(f"\n  TIME TO KNOW IT IS REAL (t = 2)")
    print(f"    trades needed        {n_tot:>10,.0f}")
    print(f"    at {a.trades:.0f}/day            {days:>10,.0f} days")
    print("    That is how long you would be deploying money before the P&L")
    print("    itself could distinguish this edge from luck.")
    if days > 400:
        print("\n    *** READ THIS ONE TWICE. At this edge and this")
        print("    correlation you can NEVER validate the strategy from live")
        print("    P&L on any sane timescale. Which means the decision to")
        print("    deploy has to be made on measurement BEFORE trading -- the")
        print("    money will not tell you. That is the strongest argument")
        print("    for everything else in this repo. ***")

    print(f"\n  A {100*d['losing_month_rate']:.0f}% losing-month rate is the number")
    print("  that actually ends strategies. Decide now whether you would keep")
    print("  running this after two bad months in a row, because at this")
    print("  Sharpe that will happen.")


if __name__ == "__main__":
    main()
