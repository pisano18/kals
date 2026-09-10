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


def montecarlo(bank, f, p, closes_day, per_close=1.2, days=60, trials=4000,
               seed=17, brake_closes=LOSS_CLOSES, run_days=3):
    """THE SAME MODEL WITH THE LOSSES ACTUALLY IN IT.

    simulate() spends the AVERAGE every day and therefore never has a bad
    week. The operator caught that. What it misses is not the mean -- the
    mean is right -- but everything else: how long the bad case takes, how
    deep it digs, and how often the brake stops the run.

    LOSSES ARE DRAWN PER CLOSE, NOT PER FILL. Twelve series settle on the
    same second and a close can hold MAX_PER_CLOSE buys; when a close loses,
    every fill on it loses together. Drawing per fill would understate the
    swings by roughly the square root of the fills per close, and this
    project has already paid for that mistake once (three fills on one NEAR
    market spent the whole 3-loss budget on a single event).

    THE BRAKE IS MODELLED because it is real: `losing_closes` is a set that
    accumulates over a whole --minutes 4320 run, so `brake_closes` losing
    closes inside `run_days` halts the bot until a human restarts it. Here a
    halt costs the REST OF THAT DAY, which is optimistic -- a real halt lasts
    until the operator looks.
    """
    import random
    rng = random.Random(seed)
    win_amt, lose_amt = (1.0 - p) - fee(p), p + fee(p)
    hit = {r: [] for r in RUNGS}
    ends, halts, drawdowns, ruined = [], [], [], 0
    for t in range(trials):
        b = bank
        peak = b
        dd = 0.0
        nhalt = 0
        seen = set()
        lc, runday = 0, 0
        for d in range(days):
            r = rung_for(b, p)
            if r == 0:
                ruined += 1
                break
            if r not in seen:
                seen.add(r)
                hit[r].append(d)
            if runday >= run_days:
                runday, lc = 0, 0          # a fresh run resets the counter
            runday += 1
            n = 0
            while n < closes_day:
                n += 1
                if rng.random() < f:
                    b -= r * per_close * lose_amt
                    lc += 1
                    if lc >= brake_closes:
                        nhalt += 1
                        break              # halted: rest of the day is lost
                else:
                    b += r * per_close * win_amt
            peak = max(peak, b)
            dd = max(dd, peak - b)
        ends.append(b)
        halts.append(nhalt)
        drawdowns.append(dd)
    ends.sort()
    drawdowns.sort()

    def pct(v, q):
        return v[min(len(v) - 1, int(q * len(v)))]
    out = {"ends": ends, "p10": pct(ends, 0.10), "p50": pct(ends, 0.50),
           "p90": pct(ends, 0.90), "mean_halts": sum(halts) / trials,
           "dd50": pct(drawdowns, 0.50), "dd90": pct(drawdowns, 0.90),
           "dd_max": drawdowns[-1], "ruined": ruined / trials,
           "worse": sum(1 for e in ends if e < bank) / trials, "hit": {}}
    for r in RUNGS:
        v = sorted(hit[r])
        if v:
            out["hit"][r] = (pct(v, 0.10), pct(v, 0.50), pct(v, 0.90),
                             len(v) / trials)
    return out


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

    # --- the Monte Carlo must agree with the smooth model on the MEAN and
    # --- disagree with it on everything else, or it is not adding anything
    mc = montecarlo(140.24, 0.0051, 0.97, 42, days=6, trials=1500, seed=2)
    sm, _ = simulate(140.24, 0.0051, 0.97, 42 * 1.2, days=6)
    smooth_end = simulate(140.24, 0.0051, 0.97, 42 * 1.2, days=6)[1]
    ck(abs(mc["p50"] - smooth_end) / smooth_end < 0.25,
       f"the random model's median lands near the smooth model "
       f"(${mc['p50']:.0f} vs ${smooth_end:.0f})")
    ck(mc["p10"] < mc["p50"] < mc["p90"] and mc["p90"] - mc["p10"] > 20,
       f"and it spreads, which the smooth model cannot "
       f"(p10 ${mc['p10']:.0f} .. p90 ${mc['p90']:.0f})")
    ck(mc["dd90"] > 0,
       f"it produces real drawdowns (90th pct ${mc['dd90']:.0f})")
    # a per-close loss must cost more than a per-fill loss would
    a = montecarlo(140.24, 0.0051, 0.97, 42, per_close=1.0, days=20,
                   trials=800, seed=5)
    b_ = montecarlo(140.24, 0.0051, 0.97, 42, per_close=2.0, days=20,
                    trials=800, seed=5)
    ck(b_["dd90"] > a["dd90"],
       f"two fills per losing close hurts more than one "
       f"(${b_['dd90']:.0f} vs ${a['dd90']:.0f} at the 90th pct)")
    # and a hopeless world must ruin people
    bad = montecarlo(140.24, 0.25, 0.97, 42, days=40, trials=400, seed=9)
    ck(bad["worse"] > 0.9,
       f"a 25% loss rate leaves almost everyone poorer "
       f"({100*bad['worse']:.0f}%)")
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

    # ---- the same thing WITH LOSSES ACTUALLY HAPPENING ----------------
    cpd = n / 1.2
    mc = montecarlo(bank, f, p, cpd, days=40, trials=6000)
    print(f"\n  {'='*74}")
    print(f"  NOW WITH REAL LOSSES: {cpd:.0f} closes/day, 1.2 fills each, "
          f"6,000 runs of 40 days.")
    print(f"  A losing CLOSE loses every fill on it -- that is how the brake "
          f"counts, and how\n  the NEAR close actually cost us three fills "
          f"at once.")
    print(f"  {'='*74}")
    print(f"  {'size':>6}{'unlucky (p10)':>16}{'typical':>10}"
          f"{'lucky (p90)':>14}{'reached within 40d':>21}")
    for r in RUNGS:
        if r not in mc["hit"]:
            continue
        lo, md, hi, frac = mc["hit"][r]
        print(f"  {r:>6}{'day ' + str(hi):>16}{'day ' + str(md):>10}"
              f"{'day ' + str(lo):>14}{100*frac:>20.1f}%")
    print(f"\n  bank after 40 days:  unlucky ${mc['p10']:,.0f}   "
          f"typical ${mc['p50']:,.0f}   lucky ${mc['p90']:,.0f}")
    print(f"  worst dip along the way: typical ${mc['dd50']:,.0f}, "
          f"1-in-10 ${mc['dd90']:,.0f}, worst seen ${mc['dd_max']:,.0f}")
    print(f"  chance of ending 40 days POORER than you started: "
          f"{100*mc['worse']:.1f}%")
    print(f"  times the 3-losing-close brake halts you: "
          f"{mc['mean_halts']:.2f} in 40 days "
          f"(each one needs a human to restart)")

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
