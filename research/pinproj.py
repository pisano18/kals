#!/usr/bin/env python3
# VERSION: 2026-09-10-pp1
"""pinproj.py -- WHAT THE MONEY DOES FROM HERE, under AMENDMENT 9.

Every earlier projection was built on the 0.98 gate. That gate is gone
(2026-09-10, PIN 0.98 -> 0.995), and it moved all three inputs at once:

    fill rate   2.7/h -> 2.1/h   measured, 7 fills over 3.3h -- THIN
    price paid  ~0.955 -> 0.970  we now buy deeper, deeper costs more
    loss rate   ~2%  -> ~0.5%    the 2.6-4 sd band on 594 tape markets

Two of those make us poorer per trade and one makes us richer. Which wins is
arithmetic, and this file does it rather than guessing.

THE SIZE LADDER IS SET BY THE BRAKE, NOT BY OPTIMISM. The bot halts after 3
losing CLOSES, and a close can hold MAX_PER_CLOSE buys, so the most it can
lose before a human looks is

    max drawdown = 3 * MAX_PER_CLOSE * size * price

Size may rise only when the bank covers that. Anything looser is betting the
account on the brake never firing, which is the one thing we know it does.

WHAT IS MEASURED AND WHAT IS ASSUMED, stated because the difference is the
whole value of the number:
  MEASURED  loss rate by margin band (research/pinfirst.py, 10,796 markets,
            fit/holdout); price paid (live fills); depth ceiling 125.
  THIN      fill rate -- 7 fills is not a rate. Reported with a range, and
            the sensitivity table exists because of it.
  ASSUMED   that the fill rate holds as size grows. Market impact says it
            roughly does to 125 (10.2-11.3x of a naive 12.5x) but nobody has
            measured it at the 0.995 gate, where the book is thinner.
"""
import argparse
import json
import math
import sys
from statistics import NormalDist

ND = NormalDist()
MAX_PER_CLOSE = 2
LOSS_CLOSES = 3          # the brake
DEPTH_CAP = 125          # median resting size at the touch
RUNGS = [20, 25, 30, 40, 50, 65, 80, 100, 125]


def fee(p, n=1.0):
    return math.ceil(0.07 * n * p * (1 - p) * 10000 - 1e-9) / 10000


def ev_contract(f, p):
    """Dollars per contract: win (1-p), lose p, minus the taker fee."""
    return (1.0 - f) * (1.0 - p) - f * p - fee(p)


def max_size(bank, p):
    """Largest size whose worst permitted drawdown the bank still covers."""
    per = LOSS_CLOSES * MAX_PER_CLOSE * p
    return min(DEPTH_CAP, bank / per) if per > 0 else 0.0


def rung_for(bank, p):
    ok = [r for r in RUNGS if r <= max_size(bank, p) + 1e-9]
    return ok[-1] if ok else 0


def simulate(bank, f, p, fills_day, days=400, sweep=None):
    """Day by day: earn at the current rung, raise the rung when funded."""
    out = []
    seen = set()
    for d in range(1, days + 1):
        r = rung_for(bank, p)
        if r == 0:
            break
        if r not in seen:
            seen.add(r)
            out.append((d - 1, r, bank, fills_day * r * ev_contract(f, p)))
        bank += fills_day * r * ev_contract(f, p)
        if sweep and bank > sweep and r >= DEPTH_CAP:
            bank = sweep
    return out, bank


def selftest():
    print("SELF-TEST -- pinproj")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # the fee, against a charge reconciled on the real account
    ck(abs(fee(0.16, 12.37) - 0.1164) < 1e-9,
       "the fee matches the real charge (12.37 lots at 16c -> $0.1164)")
    # EV sign flips exactly at breakeven
    p = 0.96
    be = None
    for i in range(1, 100000):
        f = i / 1e6
        if ev_contract(f, p) < 0:
            be = f
            break
    ck(be is not None and abs(be - (1 - p - fee(p)) / 1.0) < 2e-4,
       f"EV crosses zero at the arithmetic breakeven ({100*be:.2f}% at {p})")
    ck(ev_contract(0.005, 0.97) > 0 > ev_contract(0.05, 0.97),
       "0.5% loss rate at 97c is profitable, 5% is not")
    # the ladder must be funded, not optimistic
    ck(abs(max_size(140.24, 0.97) - 140.24 / (3 * 2 * 0.97)) < 1e-9,
       "max size is bank / (3 losing closes x 2 buys x price)")
    ck(rung_for(140.24, 0.97) == 20,
       f"$140 at 97c funds size 20, not 25 (max "
       f"{max_size(140.24, 0.97):.1f})")
    ck(max_size(1e9, 0.97) == DEPTH_CAP,
       "and an infinite bank still stops at the depth ceiling of 125")
    # a losing world must not compound
    out, end = simulate(140.24, 0.05, 0.97, 50, days=60)
    ck(end < 140.24, f"a 5% loss rate shrinks the bank (${end:.2f})")
    # a winning world reaches the cap and stops there
    out, end = simulate(140.24, 0.005, 0.97, 50, days=400)
    ck(out[-1][1] == DEPTH_CAP,
       f"a 0.5% loss rate reaches the 125 cap (last rung {out[-1][1]})")
    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--bank", type=float, default=140.24)
    ap.add_argument("--fills-day", type=float, default=50.0)
    ap.add_argument("--price", type=float, default=0.970)
    ap.add_argument("--loss", type=float, default=0.0051)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")

    f, p, n, bank = a.loss, a.price, a.fills_day, a.bank
    e = ev_contract(f, p)
    print(f"\n  {'='*74}")
    print(f"  INPUTS  bank ${bank:.2f} | loss {100*f:.2f}% | price "
          f"{100*p:.1f}c | {n:.0f} fills/day | cap {DEPTH_CAP}")
    print(f"  EV per contract {100*e:+.3f}c | wins to recover one loss "
          f"{(p + fee(p)) / ((1 - p) - fee(p)):.1f}")
    print(f"  {'='*74}")

    out, end = simulate(bank, f, p, n)
    print(f"\n  DAYS TO EACH SIZE, and the income when you get there")
    print(f"  {'size':>6}{'day':>6}{'bank at that day':>19}{'$/day there':>13}"
          f"{'$/month there':>15}")
    for d, r, b, daily in out:
        print(f"  {r:>6}{d:>6}{'$' + f'{b:,.2f}':>19}"
              f"{'$' + f'{daily:,.2f}':>13}{'$' + f'{30*daily:,.0f}':>15}")
    cap = [o for o in out if o[1] == DEPTH_CAP]
    if cap:
        d, r, b, daily = cap[0]
        print(f"\n  CEILING: size {DEPTH_CAP} on day {d}, "
              f"${daily:,.2f}/day = ${30*daily:,.0f}/month = "
              f"${365*daily:,.0f}/year.")
        print(f"  It does NOT compound past here -- the book is only so deep. "
              f"Everything above\n  ~${LOSS_CLOSES*MAX_PER_CLOSE*DEPTH_CAP*p:,.0f} "
              f"of float earns nothing and is still exposed. Sweep it.")

    print(f"\n  IF THE INPUTS ARE WRONG -- days to the {DEPTH_CAP} cap, and "
          f"$/day once there")
    print(f"  rows: loss rate. columns: average price paid.")
    print(f"  {'':>8}", end="")
    prices = [0.950, 0.960, 0.970, 0.975, 0.980]
    for pp in prices:
        print(f"{100*pp:>13.1f}c", end="")
    print()
    for ff in (0.001, 0.0051, 0.010, 0.020, 0.030, 0.050):
        print(f"  {100*ff:>6.2f}%", end="")
        for pp in prices:
            o, _ = simulate(bank, ff, pp, n, days=2000)
            top = [x for x in o if x[1] == DEPTH_CAP]
            if not top:
                ee = ev_contract(ff, pp)
                print(f"{'never' if ee <= 0 else '>2000d':>14}", end="")
            else:
                print(f"{str(top[0][0]) + 'd $' + f'{top[0][3]:,.0f}':>14}",
                      end="")
        print()
    print(f"\n  'never' = negative EV; the bank shrinks and no size is ever "
          f"funded.")
    print(f"  breakeven loss rate: "
          + ", ".join(f"{100*pp:.1f}c -> {100*(1-pp-fee(pp)):.2f}%"
                      for pp in prices))

    print(f"\n  IF THE FILL RATE IS WRONG (loss {100*f:.2f}%, price "
          f"{100*p:.1f}c)")
    print(f"  {'fills/day':>11}{'day to cap':>13}{'$/day at cap':>15}")
    for nn in (20, 35, 50, 65, 80):
        o, _ = simulate(bank, f, p, nn, days=2000)
        top = [x for x in o if x[1] == DEPTH_CAP]
        print(f"  {nn:>11}{(str(top[0][0]) + 'd') if top else '>2000d':>13}"
              f"{'$' + f'{top[0][3]:,.2f}' if top else '--':>15}")


if __name__ == "__main__":
    main()
