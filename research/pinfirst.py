#!/usr/bin/env python3
# VERSION: 2026-09-10-pf1
"""pinfirst.py -- THE BOT BUYS AT THE CROSSING. MEASURE THE CROSSING.

WHAT THE TAU=15 RUN OF pintail.py SHOWED. The model gate (fair >= 0.98) flips
0.04% of the time over 8,951 markets -- and all four flips sit within 4 sd of
the boundary, while 8,525 markets deeper than 6 sd never flip. Live, 38% of
our fills sit in the thinnest band (2.05-2.30 sd) that holds 0.5% of that
gate population. The backtest's own tradeable population is ALSO 38% in that
band. We are not buying the gate population; we are buying its edge.

WHY. pinrun fires at the FIRST second the gate opens. At that second the
margin is, by construction, ~2.05 sd -- the boundary. The flip rate we live
with is therefore the flip rate AT THE CROSSING, not the average over every
market the model would ever call. A backtest that scores all gated markets
at one tau is diluted ~40x by deep markets nobody ever sells us at <= 98c.

THIS FILE measures the crossing population directly. For every settled market
and every candidate gate level, walk tau from 30 down to 3 and find the FIRST
second the favoured side's margin reaches the level. Record the margin, the
tau, and whether that side lost. Then:

  * the flip rate at each gate level, n as markets AND closes, exact CI
  * how many markets ever reach that level inside the window (the volume
    cost of raising the bar) and how late they do it
  * a fit/holdout split over CLOSES, because a level chosen after seeing the
    flips is a fit until it is re-measured on closes it never saw
  * expected profit per 100 markets, with the price at each margin band
    taken from the backtest's tradeable population (stated, not fitted)

NO LOOKAHEAD: the margin at each second uses only prints at or before it and
the sigma of the 300 seconds before it. The outcome enters once, at the end.
"""
import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor                                # noqa: E402
from statistics import NormalDist                            # noqa: E402
import pintail                                               # noqa: E402
from pintail import (window_state, sigma_at, ROUND_DIGITS,   # noqa: E402
                     SERIES_TO_INDEX, FULLTAPE)
from pincross import cp_interval, load_index_window          # noqa: E402

ND = NormalDist()
TAU_LO, TAU_HI = 3, 30
LEVELS = [0.980, 0.985, 0.990, 0.995, 0.998, 0.999]
# median price paid in the backtest's tradeable population, by margin band
# (research/pindata_fixed, 254 markets). An ASSUMPTION for the $ column, and
# it flatters deep markets if anything: at 6+ sd the true offer is usually
# above the 98c ceiling, i.e. there is no trade at all.
PRICE_BY_M = [(2.30, 0.955), (2.60, 0.960), (3.00, 0.963), (4.00, 0.970),
              (6.00, 0.975), (1e9, 0.975)]


def price_for(m):
    for hi, p in PRICE_BY_M:
        if m < hi:
            return p
    return 0.975


def ev(f, p, size=20.0):
    fee = math.ceil(0.07 * size * p * (1 - p) * 10000 - 1e-9) / 10000 / size
    return (1 - f) * (1 - p) - f * p - fee


def crossings(arr, base, close_s, K):
    """For each level, (tau, margin, fav_yes) at the FIRST second it is met,
    walking tau from TAU_HI down to TAU_LO. None if never met."""
    out = {lv: None for lv in LEVELS}
    zs = {lv: ND.inv_cdf(lv) for lv in LEVELS}
    pending = set(LEVELS)
    for tau in range(TAU_HI, TAU_LO - 1, -1):
        sec = close_s - tau
        lk, r, cov, spot = window_state(arr, base, close_s, sec)
        if spot is None or r < 1 or cov < 0.95:
            continue
        sg = sigma_at(arr, base, sec)
        if not sg or sg <= 0:
            continue
        mu = (lk + r * spot) / 60.0
        sd = sg * math.sqrt(var_factor(int(r), [1.0]))
        if sd <= 0:
            continue
        m = (mu - K) / sd
        for lv in list(pending):
            if abs(m) >= zs[lv]:
                out[lv] = (tau, abs(m), m >= 0)
                pending.discard(lv)
        if not pending:
            break
    return out


def selftest():
    import array
    import random
    print("SELF-TEST -- pinfirst")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # a market that drifts steadily away from the strike: the crossing for a
    # deeper level must come LATER (smaller tau) than for a shallower one
    rng = random.Random(5)
    base, close_s = 0, 2000
    arr = array.array("d", [0.0] * 2100)
    # THE FIRST FIXTURE WAS WRONG, NOT THE CODE: a 0.004/s drift starting
    # inside the settlement window left mu within noise of K at tau=30, so
    # the sign at the crossing was a coin flip. Plant a move that no honest
    # estimator could read two ways.
    p = 100.0
    for i in range(2100):
        p += rng.gauss(0, 0.02) + (0.02 if i > 1900 else 0.0)
        arr[i] = p
    K = arr[1900] + 0.10
    cx = crossings(arr, base, close_s, K)
    ck(cx[0.980] is not None, "the 0.98 level is reached inside the window")
    if cx[0.980] and cx[0.999]:
        ck(cx[0.999][0] <= cx[0.980][0],
           f"0.999 is reached no earlier than 0.98 (tau {cx[0.999][0]} vs "
           f"{cx[0.980][0]})")
        ck(cx[0.999][1] >= cx[0.980][1] >= ND.inv_cdf(0.98),
           "margins at the crossings are ordered and at least the level")
    ck(cx[0.980] is not None and cx[0.980][2] is True,
       "the favoured side is YES when the index sits above the strike")
    # a market that never leaves the strike never crosses anything
    flat = array.array("d", [100.0 + rng.gauss(0, 0.02) for _ in range(2100)])
    cf = crossings(flat, base, close_s, 100.0)
    ck(all(v is None for v in cf.values()),
       "a market pinned on its strike crosses no level")
    ck(price_for(2.1) == 0.955 and price_for(7.0) == 0.975,
       "the price assumption table reads by band")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    return not f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")

    mk = []
    for v in json.load(open(FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] in SERIES_TO_INDEX and r.get("settle") is not None:
                mk.append(r)
    mk.sort(key=lambda r: r["close"])
    prev_settle = {(r["series"], int(r["close"])): float(r["settle"])
                   for r in mk}
    print(f"\n  {len(mk):,} settled markets")
    lo_sec, hi_sec = int(mk[0]["close"]) - 400, int(mk[-1]["close"])
    t0 = time.time()
    idx, nf, kept, _ = load_index_window(lo_sec, hi_sec)
    print(f"  {len(idx)} feeds, {kept:,} prints ({time.time()-t0:.0f}s)")

    print(f"  walking tau {TAU_HI}->{TAU_LO} on every market ...")
    t0 = time.time()
    obs = []
    for r in mk:
        iid = SERIES_TO_INDEX[r["series"]]
        if iid not in idx:
            continue
        base, arr = idx[iid]
        cs = int(r["close"])
        ps = prev_settle.get((r["series"], cs - 900))
        K = (ps if ps is not None else float(r["strike"])) \
            - 0.5 * 10.0 ** (-ROUND_DIGITS[r["series"]])
        cx = crossings(arr, base, cs, K)
        yes_won = float(r["settle"]) >= K
        rec = {"close": cs, "sr": r["series"]}
        for lv, v in cx.items():
            rec[lv] = None if v is None else (v[0], v[1], v[2] != yes_won)
        obs.append(rec)
    print(f"  {len(obs):,} markets walked ({time.time()-t0:.0f}s)")

    closes_all = sorted(set(o["close"] for o in obs))
    cut = closes_all[int(0.70 * len(closes_all))]

    def table(rows, label):
        print(f"\n  {label}")
        print(f"  {'gate':>7}{'reach it':>10}{'closes':>8}{'flips':>7}"
              f"{'flip rate':>11}{'95% CI':>17}{'med tau':>9}{'$/100':>8}")
        for lv in LEVELS:
            hit = [o[lv] for o in rows if o[lv] is not None]
            if not hit:
                continue
            fl = sum(1 for h in hit if h[2])
            cl = len(set(o["close"] for o in rows if o[lv] is not None))
            lo, hi = cp_interval(fl, len(hit))
            taus = sorted(h[0] for h in hit)
            fr = fl / len(hit)
            # dollars per 100 markets in the population: reach × ev at the
            # price its margin band would have cost
            dollars = 0.0
            for h in hit:
                dollars += ev(fr, price_for(h[1])) * 100
            dollars = dollars / len(rows) * 100
            print(f"  {lv:>7.3f}{len(hit):>10}{cl:>8}{fl:>7}{100*fr:>10.2f}%"
                  f"{'[' + f'{100*lo:.2f}, {100*hi:.2f}' + ']':>17}"
                  f"{taus[len(taus)//2]:>9}{dollars:>8.1f}")

    table(obs, f"ALL {len(obs):,} markets -- flip rate AT THE FIRST CROSSING "
               f"of each gate level, tau {TAU_HI}->{TAU_LO}")
    fit = [o for o in obs if o["close"] < cut]
    hold = [o for o in obs if o["close"] >= cut]
    table(fit, f"FIT: {len(fit):,} markets before "
               f"{time.strftime('%m-%d %H:%MZ', time.gmtime(cut))}")
    table(hold, f"HOLDOUT: {len(hold):,} markets after it -- the only "
                f"column that is not a fit")
    print("\n  '$/100' = expected cents per 100 markets in the population, "
          "at the flip rate shown and the\n  price its margin band fetched "
          "in the backtest (stated assumption, see PRICE_BY_M).")

    # THE LIKE-FOR-LIKE COMPARISON WITH LIVE. Live fills sit 38% in the
    # 2.05-2.30 band at fill time. What does that band flip at on tape?
    for lv in (0.980, 0.990):
        hit = [(o, o[lv]) for o in obs if o[lv] is not None]
        print(f"\n  AT THE {lv:.3f} CROSSING, BY MARGIN AT THAT SECOND "
              f"(the band live fills actually occupy)")
        print(f"  {'margin':>12}{'markets':>9}{'closes':>8}{'flips':>7}"
              f"{'rate':>8}{'95% CI':>18}{'tau<30':>8}")
        edges = [2.05, 2.30, 2.60, 3.00, 4.00, 6.00, 1e9]
        for a_, b_ in zip(edges, edges[1:]):
            sel = [(o, h) for o, h in hit if a_ <= h[1] < b_]
            if not sel:
                continue
            fl = sum(1 for o, h in sel if h[2])
            cl = len(set(o["close"] for o, h in sel))
            inside = sum(1 for o, h in sel if h[0] < TAU_HI)
            lo, hi = cp_interval(fl, len(sel))
            print(f"  {a_:>5.2f}-{b_:<6.3g}{len(sel):>9}{cl:>8}{fl:>7}"
                  f"{100*fl/len(sel):>7.2f}%"
                  f"{'[' + f'{100*lo:.2f}, {100*hi:.2f}' + ']':>18}"
                  f"{inside:>8}")
        ins = [(o, h) for o, h in hit if h[0] < TAU_HI]
        fl = sum(1 for o, h in ins if h[2])
        lo, hi = cp_interval(fl, len(ins)) if ins else (0, 0)
        print(f"  crossings INSIDE the window (tau < {TAU_HI}), all margins: "
              f"{len(ins)} markets, {fl} flips, {100*fl/max(1,len(ins)):.2f}% "
              f"[{100*lo:.2f}, {100*hi:.2f}]")

    # FIT / HOLDOUT on the bands, because a flip rate chosen per band after
    # seeing the flips is a fit until it survives closes it never saw.
    print(f"\n  BANDS AT THE 0.980 CROSSING, FIT vs HOLDOUT (split at "
          f"{time.strftime('%m-%d %H:%MZ', time.gmtime(cut))})")
    print(f"  {'margin':>12}{'FIT n':>7}{'flips':>6}{'rate':>8}"
          f"{'HOLD n':>8}{'flips':>6}{'rate':>8}{'HOLD 95% CI':>18}")
    for a_, b_ in ((2.05, 2.6), (2.6, 4.0), (4.0, 1e9)):
        fh = [o[0.980] for o in fit if o[0.980] and a_ <= o[0.980][1] < b_]
        hh = [o[0.980] for o in hold if o[0.980] and a_ <= o[0.980][1] < b_]
        ff = sum(1 for h in fh if h[2])
        hf = sum(1 for h in hh if h[2])
        lo, hi = cp_interval(hf, len(hh)) if hh else (0, 0)
        print(f"  {a_:>5.2f}-{b_:<6.3g}{len(fh):>7}{ff:>6}"
              f"{100*ff/max(1,len(fh)):>7.2f}%{len(hh):>8}{hf:>6}"
              f"{100*hf/max(1,len(hh)):>7.2f}%"
              f"{'[' + f'{100*lo:.2f}, {100*hi:.2f}' + ']':>18}")

    # where the flips at 0.98 sit: margin at the crossing, and tau
    print(f"\n  the flips at the 0.98 crossing:")
    for o in obs:
        h = o[0.980]
        if h and h[2]:
            print(f"    {o['sr']:<10} close {time.strftime('%m-%d %H:%M', time.gmtime(o['close']))}"
                  f"  tau {h[0]:>2}  margin {h[1]:.2f} sd")


if __name__ == "__main__":
    main()
