#!/usr/bin/env python3
# VERSION: 2026-09-08-ps1
"""pinstress.py -- run the PROPOSED live configuration through the whole
historical tape, chronologically, with a real account balance, and find out
what would have happened.

THE OPERATOR'S QUESTION, VERBATIM: "are you certain you are being very careful
and that getting you to 150 will not be a massive flop and lose my money, have
you extensively tested it in historic data? Can you prove that" and "What you
plan to do with the 150 do exactly that with the history data and see what
would've happened".

THE HONEST ANSWER STARTS WITH A PROBLEM. **There are ZERO losing trades in the
eligible sample.** A straight replay therefore returns 100% wins and proves
NOTHING -- realised P&L in a zero-flip world is a monotone increasing function
of contracts bought, so it would rank "bet more" first every time and it would
be meaningless. Anyone quoting such a replay as evidence is quoting an artefact.

SO THIS FILE INJECTS THE LOSSES. It replays the real closes, in real
chronological order, with the real prices and the real depth, and draws the
outcome from an assumed flip rate. It then sweeps that rate from the measured
0.90% up to 20%, which is 22x worse than anything observed, and reports what
the account does.

TWO THINGS MAKE IT CONSERVATIVE RATHER THAN FLATTERING:

1. FLIPS ARE DRAWN PER CLOSE, NOT PER TRADE. All twelve crypto series settle on
   the same quarter hour at rho ~ 0.8, so a bad print is a bad print for every
   market at once. Drawing independently per trade would diversify a risk that
   is NOT diversified in reality and would understate the drawdown badly. The
   independent draw is reported alongside ONLY to show how much that assumption
   is worth.

2. THE BALANCE IS REAL AND IT BINDS. You cannot buy 40 contracts with $12. The
   simulation refuses trades it cannot afford and reports ruin honestly, and
   the loss abort halts the run exactly as the live code does.

WHAT THIS CANNOT PROVE. It cannot prove the 0.90% flip rate is right -- that
number comes from 3 flips in 333 trades OUT OF SAMPLE, under an older rule.
Three events is a thin foundation and its exact one-sided 95% upper bound is
2.31%. What this file CAN do is show what happens if that number is wrong, and
by how much it would have to be wrong before the account is in trouble.
"""
import argparse
import json
import math
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor                                # noqa: E402
from statistics import NormalDist                            # noqa: E402

ND = NormalDist()
MEASURED_FLIP = 0.0090
EXACT_UPPER = 0.0231          # one-sided 95% Clopper-Pearson on 3 in 333
EV_FLOOR = 0.003
IMPROVE = 0.005
CEILING = 0.988
MIN_FRAC = 0.50
PIN_P = 0.02


def fee(p, n=1):
    return math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000


def ev(p, flip=MEASURED_FLIP):
    return (1 - flip) * (1 - p) - flip * p - fee(p)


def model_pflip(r):
    rr, sg = r["r"], r.get("sig")
    if not sg or rr < 1:
        return None
    sd = sg * math.sqrt(var_factor(int(rr), [1.0])) * (60.0 / rr)
    if sd <= 0:
        return 0.0 if r["req"] <= 0 else 1.0
    z = r["req"] / sd
    return (1 - ND.cdf(z)) if r["req"] > 0 else ND.cdf(z)


def simulate(byclose, size, cap, start_cash, flip_rate, loss_abort,
             rng, correlated=True, hedge_cut=0.0, hedge_cost=0.0):
    """hedge_cut: fraction of a LOSS recovered by buying the other side once
    the model turns against us. hedge_cost: what that insurance costs on every
    position that would have WON anyway, as a fraction of the stake. Both are
    MEASURED in research/pinhedge.py, not assumed:
      trigger p(lose) >= 50%  ->  loss severity cut 34.7%, and in the live
      tau 3-30 window the false alarms cost 55.7c over 165 positions.""" 
    """One path. Returns the full account history and how it ended."""
    cash = float(start_cash)
    peak = cash
    worst_dd = 0.0
    realised = 0.0
    trades = losses = 0
    halted = None
    for cs in sorted(byclose):
        if halted:
            break
        seq = byclose[cs]
        # ONE shock for the whole close: twelve series settle together.
        bad_close = (rng.random() < flip_rate) if correlated else None
        best = None
        n = 0
        for x in seq:
            if n >= cap:
                break
            offer = float(x.get("size") or 0)
            take = min(float(size), offer)
            if take < max(1.0, MIN_FRAC * float(size)):
                continue
            if best is not None and x["price"] >= best - IMPROVE:
                continue
            cost = take * x["price"] + fee(x["price"], take)
            if cost > cash:                      # THE BALANCE BINDS
                continue
            lost = bad_close if correlated else (rng.random() < flip_rate)
            cash -= cost
            trades += 1
            if lost:
                losses += 1
                back = hedge_cut * cost           # the hedge returns part of it
                cash += back
                realised -= (cost - back)
            else:
                prem = hedge_cost * cost          # insurance we did not need
                cash += take - prem
                realised += take - cost - prem
            best = x["price"] if best is None else min(best, x["price"])
            n += 1
            peak = max(peak, cash)
            worst_dd = max(worst_dd, peak - cash)
            if realised <= loss_abort:
                halted = f"loss abort at ${realised:.2f}"
                break
    return dict(cash=cash, realised=realised, trades=trades, losses=losses,
                worst_dd=worst_dd, halted=halted)


def selftest():
    print("SELF-TEST -- pinstress")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # a planted world: one close, one 100-contract offer at 90c
    world = {1: [{"price": 0.90, "size": 100.0, "r": 10, "sig": 1e-9,
                  "req": -99.0, "tau": 10}]}
    r0 = random.Random(1)
    d = simulate(world, 10, 2, 100.0, 0.0, -50.0, r0)
    ck(d["trades"] == 1 and d["losses"] == 0,
       "with flip rate 0 the planted trade WINS")
    ck(abs(d["cash"] - (100.0 - 9.0 - fee(0.90, 10) + 10.0)) < 1e-9,
       f"and the cash is exactly stake out, payout in (${d['cash']:.4f})")
    d = simulate(world, 10, 2, 100.0, 1.0, -50.0, random.Random(1))
    ck(d["losses"] == 1 and d["cash"] < 100.0,
       "with flip rate 1 the SAME trade LOSES and cash falls -- the injector "
       "actually injects, which a null-only test would never show")
    ck(abs(d["cash"] - (100.0 - 9.0 - fee(0.90, 10))) < 1e-9,
       "and a loss forfeits the whole stake plus the fee")

    # THE BALANCE MUST BIND
    d = simulate(world, 10, 2, 5.00, 0.0, -50.0, random.Random(1))
    ck(d["trades"] == 0,
       "a $5 account cannot buy $9 of contracts -- the balance BINDS and the "
       "trade is refused, not silently allowed")

    # THE ABORT MUST ENGAGE
    many = {i: [{"price": 0.90, "size": 100.0, "r": 10, "sig": 1e-9,
                 "req": -99.0, "tau": 10}] for i in range(50)}
    d = simulate(many, 10, 1, 10000.0, 1.0, -30.0, random.Random(1))
    ck(d["halted"] is not None and d["realised"] <= -30.0,
       f"a losing world HALTS at the loss abort ({d['halted']})")
    ck(d["trades"] <= 5,
       f"and it halts EARLY, after {d['trades']} trades, not after all 50")

    # correlation must matter, and in the direction claimed
    # BOTH rows must actually TRADE, so the second is 2c cheaper -- the
    # improve rule needs 0.5c. The first version of this fixture priced both
    # at 90c, so the second was refused and there was nothing to correlate;
    # the test then compared a one-trade close against itself and failed
    # loudly, which is exactly what it should do.
    wide = {i: [{"price": 0.90 - 0.02 * j, "size": 100.0, "r": 10,
                 "sig": 1e-9, "req": -99.0, "tau": 10 - j} for j in range(2)]
            for i in range(200)}
    dd_c = [simulate(wide, 10, 2, 500.0, 0.10, -1e9, random.Random(s),
                     correlated=True)["worst_dd"] for s in range(40)]
    dd_i = [simulate(wide, 10, 2, 500.0, 0.10, -1e9, random.Random(s),
                     correlated=False)["worst_dd"] for s in range(40)]
    mc, mi = sum(dd_c) / len(dd_c), sum(dd_i) / len(dd_i)
    ck(mc > mi,
       f"a CORRELATED close draws a deeper drawdown than an independent one "
       f"(${mc:.2f} vs ${mi:.2f}) -- which is why the correlated draw is the "
       f"one reported")

    # the null: no eligible rows means no trades and no claim
    ck(simulate({}, 10, 2, 150.0, 0.05, -30.0, random.Random(1))["trades"] == 0,
       "an EMPTY world produces zero trades and cannot manufacture a result")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows", default=r"C:\kals-repo\results\pindata\rows.jsonl")
    ap.add_argument("--cash", type=float, default=150.0)
    ap.add_argument("--size", type=float, default=40.0)
    ap.add_argument("--cap", type=int, default=2)
    ap.add_argument("--paths", type=int, default=4000)
    ap.add_argument("--hedge-cut", type=float, default=0.0,
                    help="fraction of a loss recovered by hedging (pinhedge "
                         "measures 0.347 at a 50%% trigger)")
    ap.add_argument("--hedge-cost", type=float, default=0.0,
                    help="premium paid on winners, as a fraction of stake "
                         "(pinhedge measures 0.0037 in the live window)")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    rows = []
    with open(a.rows, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass
    elig = []
    for r in rows:
        if not (3 <= r["tau"] <= 30):
            continue
        pf = model_pflip(r)
        if pf is None or pf > PIN_P:
            continue
        if r["price"] > CEILING or ev(r["price"]) < EV_FLOOR:
            continue
        elig.append(r)
    byc = defaultdict(list)
    for r in elig:
        byc[r["close"]].append(r)
    for c in byc:
        byc[c].sort(key=lambda x: -x["tau"])

    abort = -1.5 * a.size * a.cap * 1.00
    print(f"\n  THE PROPOSED CONFIGURATION, RUN ON REAL HISTORY")
    print(f"  {'starting cash':<26}${a.cash:,.2f}")
    print(f"  {'size / buys per close':<26}{a.size:g} contracts, cap {a.cap}")
    print(f"  {'loss abort':<26}${abort:,.2f}")
    print(f"  {'closes in the tape':<26}{len(byc)}")
    print(f"  {'eligible moments':<26}{len(elig):,}")
    print(f"  {'LOSING TRADES IN THE TAPE':<26}0   <-- why losses must be injected\n")

    print(f"  {'flip rate':>12}{'median end':>13}{'worst path':>12}"
          f"{'median DD':>12}{'worst DD':>11}{'% ending down':>15}{'% ruined':>10}")
    for rate, lab in ((MEASURED_FLIP, "0.90% measured"),
                      (EXACT_UPPER, "2.31% bound"),
                      (0.05, "5.00%"), (0.10, "10.00%"),
                      (0.20, "20.00%")):
        ends, dds, halts = [], [], 0
        for s in range(a.paths):
            d = simulate(byc, a.size, a.cap, a.cash, rate, abort,
                         random.Random(s), correlated=True,
                         hedge_cut=a.hedge_cut, hedge_cost=a.hedge_cost)
            ends.append(d["cash"])
            dds.append(d["worst_dd"])
            halts += int(bool(d["halted"]))
        ends.sort()
        dds.sort()
        down = sum(1 for e in ends if e < a.cash) / len(ends)
        print(f"  {lab:>12}${ends[len(ends)//2]:>11,.2f}${ends[0]:>10,.2f}"
              f"${dds[len(dds)//2]:>10,.2f}${dds[-1]:>9,.2f}"
              f"{100*down:>14.1f}%{100*halts/a.paths:>9.1f}%")

    print(f"\n  'ruined' = the loss abort halted the run. 'DD' = the deepest")
    print(f"  peak-to-trough fall in the account along the path.")
    print(f"  Flips are drawn PER CLOSE, so one bad print takes every open")
    print(f"  position at that close together -- the conservative assumption.\n")

    # the single worst thing that can happen first
    print("  THE FIRST TRADE IS A LOSS -- what does that cost?")
    first = sorted(byc)[0]
    x = byc[first][0]
    take = min(a.size, float(x.get("size") or 0))
    cost = take * x["price"] + fee(x["price"], take)
    print(f"     first eligible trade: {take:g} contracts at "
          f"{100*x['price']:.1f}c = ${cost:.2f}")
    print(f"     losing it leaves ${a.cash - cost:,.2f} of ${a.cash:,.2f}, "
          f"a {100*cost/a.cash:.1f}% drawdown")
    print(f"     it takes {cost/max(take*(1-x['price'])-fee(x['price'],take),1e-9):.0f} "
          f"ordinary wins to earn it back\n")


if __name__ == "__main__":
    main()
