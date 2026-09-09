#!/usr/bin/env python3
# VERSION: 2026-09-09-pdq1
"""pindrawq.py -- follow-up queries on the cached pindraw state.

pindraw.py writes `results/pindraw/state.pkl` (every simulated position with its
full per-second panel) so the four questions below can be asked without a second
7-minute tape pass. All the arithmetic is pindraw's; this file only slices.

WHAT IT ANSWERS, AND WHY EACH ONE WAS NEEDED AFTER READING THE FIRST RUN

1. THE FLIP RATE DOES NOT MATCH THE LIVE ONE. The reconstruction lost 15 of 639
   buys = 2.35%, against the 0.90% measured live and the 2.31% one-sided upper
   bound. If that gap is real the hedge is being priced against the wrong loss
   frequency. Six of the fifteen losers were bought BELOW 40c, which the live
   rule can reach but which is not the population MEASURED_FLIP describes
   ("3 flips in 333 DEAR trades"). Split by price and see.

2. THE HEDGE CREATES ITS OWN LARGE LOSSES. In the first run SPOT_CROSS's worst
   close was -$22.22 while the loss it was insuring against was -$37.50 -- and
   the -$22.22 close is not in the loser list at all. It is a WINNER that was
   hedged expensively. A study that reports only "worst loss fell" while
   silently manufacturing new ones is lying by omission, so the worst
   false-alarm close is reported on its own line.

3. THE DEAR SUBSET IS THE REAL POPULATION. Re-run the headline table on entries
   at 90c and above, which is what the live runner actually buys.

4. AN INTERVAL ON THE COST. The worst close is one observation, but the total
   profit given up is a mean and can be bootstrapped over closes.
"""
import argparse
import math
import os
import pickle
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pindraw as PD                                          # noqa: E402

STATE = r"C:\kals-repo\results\pindraw\state.pkl"


def bucket_flip(ps, edges=(0.0, 0.5, 0.8, 0.9, 0.95, 1.01)):
    out = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        sel = [p for p in ps if lo <= p["price"] < hi]
        n = len(sel)
        k = sum(1 for p in sel if not p["won"])
        out.append((lo, hi, n, k, PD.wilson(k, n)))
    return out


def hedge_detail(ps, fn, win_unit, max_px=None, frac=1.0):
    """Per-close hedged P&L plus the two numbers the first run hid."""
    ph = defaultdict(float)
    pb = defaultdict(float)
    fa_cost = defaultdict(float)
    for p in ps:
        h, ft, wn = PD.run_hedge(dict(p), p["rows"], fn,
                                 size_frac=frac, max_px=max_px)
        v = PD.leg_pnl(p["n"], p["price"], p["won"], h)
        b = PD.leg_pnl(p["n"], p["price"], p["won"])
        ph[p["close_s"]] += v
        pb[p["close_s"]] += b
        if ft is not None and p["won"]:
            fa_cost[p["close_s"]] += b - v
    # a close that WOULD have made money and instead lost it
    manufactured = [(-ph[c]) for c in ph if pb[c] > 0 and ph[c] < 0]
    return ph, pb, fa_cost, manufactured


def boot_ci(vals, base, n=2000, seed=7):
    """95% CI on (sum(vals) - sum(base)) resampling CLOSES, not trades."""
    rnd = random.Random(seed)
    keys = list(vals)
    d = [vals[k] - base[k] for k in keys]
    m = len(d)
    if m < 2:
        return (float("nan"), float("nan"))
    outs = []
    for _ in range(n):
        outs.append(sum(d[rnd.randrange(m)] for _ in range(m)))
    outs.sort()
    return outs[int(0.025 * n)], outs[int(0.975 * n)]


def selftest():
    print("SELF-TEST -- pindrawq")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    ck(PD.selftest(), "pindraw's self-test passes; every number here is its "
                      "arithmetic")

    # bucketing: 100 dear positions with 1 loss, 100 cheap ones with 20
    ps = ([{"price": 0.95, "won": i > 0} for i in range(100)] +
          [{"price": 0.30, "won": i >= 20} for i in range(100)])
    b = bucket_flip(ps)
    dear = [x for x in b if x[0] == 0.95][0]
    cheap = [x for x in b if x[0] == 0.0][0]
    ck(dear[2] == 100 and dear[3] == 1,
       f"planted: the dear bucket holds 100 buys and 1 loss ({dear[2]}, "
       f"{dear[3]})")
    ck(cheap[2] == 100 and cheap[3] == 20,
       f"and the cheap bucket 100 buys and 20 losses ({cheap[2]}, {cheap[3]})")
    ck(dear[4][1] < cheap[4][0],
       f"their 95% intervals do not overlap ({dear[4][1]:.3f} < "
       f"{cheap[4][0]:.3f}), so pooling them would hide a real difference")
    flat = [{"price": 0.30 + 0.005 * i, "won": (i % 10) != 0}
            for i in range(200)]
    bf = bucket_flip(flat)
    rates = [x[3] / x[2] for x in bf if x[2] >= 20]
    ck(len(rates) >= 2 and max(rates) - min(rates) < 0.10,
       f"NULL: with the loss rate the same everywhere, the buckets agree "
       f"({[round(r, 3) for r in rates]}) -- the split invents nothing")

    # manufactured losses: a winner hedged at 60c must show up as one
    rows = [(t, 99.0, 99.0, 100.0, 0.5, 0.5, 0.40, 0.60, 500.0, 500.0, 100)
            for t in range(29, 0, -1)]
    pos = [{"tk": "W", "close_s": 1, "tau": 30, "want": "yes", "price": 0.95,
            "n": 20.0, "won": True, "rows": rows}]
    _, _, _, man = hedge_detail(pos, PD.make_triggers()["SPOT_CROSS"][0], 1.0)
    ck(len(man) == 1 and man[0] > 10,
       f"planted: a WINNER hedged at 60c is reported as a manufactured loss "
       f"of ${man[0] if man else 0:.2f}")
    rows2 = [(t, 101.0, 101.0, 100.0, 0.99, 0.5, 0.40, 0.60, 500.0, 500.0, 100)
             for t in range(29, 0, -1)]
    pos2 = [{"tk": "W", "close_s": 1, "tau": 30, "want": "yes",
             "price": 0.95, "n": 20.0, "won": True, "rows": rows2}]
    _, _, _, man2 = hedge_detail(pos2, PD.make_triggers()["SPOT_CROSS"][0], 1.0)
    ck(man2 == [],
       "NULL: a winner the trigger never fires on manufactures nothing")

    a = {1: 1.0, 2: 1.0, 3: 1.0}
    lo, hi = boot_ci(a, {1: 0.0, 2: 0.0, 3: 0.0}, n=500)
    ck(abs(lo - 3.0) < 1e-9 and abs(hi - 3.0) < 1e-9,
       f"bootstrap on a constant difference has zero width "
       f"([{lo:.2f}, {hi:.2f}])")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--state", default=STATE)
    ap.add_argument("--min-price", type=float, default=0.90)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    st = pickle.load(open(a.state, "rb"))
    T = PD.make_triggers()
    out = []

    def P(s=""):
        print(s)
        out.append(s)

    for tag in ("LIVE", "WIDE"):
        ps = st["positions"][tag]
        if not ps:
            continue
        P("\n" + "=" * 78)
        P(f"{tag} WINDOW -- follow-ups")
        P("=" * 78)

        P(f"\n  1. FLIP RATE BY WHAT WE PAID. MEASURED_FLIP = 0.90% was "
          f"measured on DEAR trades")
        P(f"     only ('3 flips in 333'), so pooling every price against it "
          f"is the wrong comparison.")
        P(f"  {'price paid':<18}{'buys':>7}{'lost':>6}{'flip rate':>11}"
          f"{'95% CI':>20}")
        for lo, hi, n, k, (cl, ch) in bucket_flip(ps):
            if not n:
                continue
            P(f"  {f'{100*lo:.0f}c - {100*hi:.0f}c':<18}{n:>7}{k:>6}"
              f"{k/n:>11.4f}     [{cl:.4f}, {ch:.4f}]")
        ages = []
        for p in ps:
            for r in p["rows"]:
                if r[0] == p["tau"]:
                    ages.append((p["price"], r[10] if r[10] is not None else -1))
                    break
        cheap = [x[1] for x in ages if x[0] < 0.5 and x[1] >= 0]
        dear = [x[1] for x in ages if x[0] >= a.min_price and x[1] >= 0]
        if cheap and dear:
            P(f"\n     Quote age at entry: below 50c, median "
              f"{PD.pct(cheap,50):,.0f} ms over {len(cheap)} buys; at "
              f"{100*a.min_price:.0f}c+,")
            P(f"     median {PD.pct(dear,50):,.0f} ms over {len(dear)}. A "
              f"much staler quote on the cheap ones would")
            P(f"     mean they are a replay artefact rather than a trade "
              f"anyone could have had.")

        sub = [p for p in ps if p["price"] >= a.min_price]
        for name, sel in (("ALL PRICES", ps),
                          (f"{100*a.min_price:.0f}c AND DEARER", sub)):
            if not sel:
                continue
            base = defaultdict(float)
            for p in sel:
                base[p["close_s"]] += PD.leg_pnl(p["n"], p["price"], p["won"])
            wins = [v for v in base.values() if v > 0]
            wu = sum(wins) / len(wins) if wins else float("nan")
            nlose = sum(1 for v in base.values() if v < 0)
            P(f"\n  2/3. {name}: {len(sel):,} buys, {len(base):,} closes, "
              f"{nlose} losing closes,")
            P(f"       one win = ${wu:.4f}, total ${sum(base.values()):.2f}, "
              f"worst -${-min(base.values()):.2f} "
              f"= {-min(base.values())/wu:.1f} wins.")
            P(f"  {'trigger':<20}{'total$':>9}{'cost$':>8}{'95% CI on cost':>22}"
              f"{'worst$':>9}{'wins':>7}{'made':>6}{'worstFA$':>10}")
            for tname in ("SPOT_CROSS", "SPOT_CROSS_HOLD2", "MU_CROSS",
                          "MU_CROSS_HOLD2", "MODEL_P90"):
                if tname not in T:
                    continue
                ph, pb, fac, man = hedge_detail(sel, T[tname][0], wu)
                lo, hi = boot_ci(ph, pb)
                tot = sum(ph.values())
                worst = -min(ph.values()) if ph else 0.0
                P(f"  {tname:<20}{tot:>9.2f}{tot-sum(pb.values()):>8.2f}"
                  f"   [{lo:>8.2f}, {hi:>8.2f}]{-worst:>9.2f}"
                  f"{worst/wu:>7.1f}{len(man):>6}"
                  f"{(max(man) if man else 0.0):>10.2f}")
            P(f"       'cost$' is profit given up, with a 95% bootstrap "
              f"interval resampling CLOSES.")
            P(f"       'made' counts closes the hedge turned from a PROFIT "
              f"into a LOSS; 'worstFA$' is")
            P(f"       the biggest single loss the hedge itself manufactured.")

            P("")
            P(f"  4. THE OPERATOR'S IDEA TAKEN LITERALLY -- refuse the "
              f"hedge when the other side")
            P(f"     is dear. A hedge at 90c does not cap a loss, it confirms "
              f"one.")
            P(f"  {'trigger':<18}{'cap':>6}{'frac':>6}{'total$':>9}"
              f"{'cost$':>8}{'worst$':>9}{'wins':>7}{'made':>6}"
              f"{'worstFA$':>10}{'caught':>8}")
            for tname in ("SPOT_CROSS", "MU_CROSS"):
                for cap in (0.10, 0.25, 0.50, None):
                    for fr in (1.0, 0.5):
                        ph, pb, fac, man = hedge_detail(
                            sel, T[tname][0], wu, max_px=cap, frac=fr)
                        caught = sum(
                            1 for q in sel if not q["won"] and
                            PD.run_hedge(dict(q), q["rows"], T[tname][0],
                                         size_frac=fr, max_px=cap)[0])
                        tot = sum(ph.values())
                        worst = -min(ph.values()) if ph else 0.0
                        P(f"  {tname:<18}"
                          f"{('none' if cap is None else f'{100*cap:.0f}c'):>6}"
                          f"{fr:>6.2f}{tot:>9.2f}"
                          f"{tot-sum(pb.values()):>8.2f}{-worst:>9.2f}"
                          f"{worst/wu:>7.1f}{len(man):>6}"
                          f"{(max(man) if man else 0.0):>10.2f}"
                          f"{caught:>8}")
            P(f"       'caught' is how many LOSING buys actually got a hedge "
              f"under that cap.")

    path = os.path.join(os.path.dirname(a.state), "FOLLOWUP.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("```\n" + "\n".join(out) + "\n```\n")
    print(f"\n  written -> {path}")


if __name__ == "__main__":
    main()
