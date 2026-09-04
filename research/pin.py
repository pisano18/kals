#!/usr/bin/env python3
# VERSION: 2026-09-04-p1
"""
pin.py -- the pinned endgame: harvesting quotes the settlement math has
already overtaken.

    python research/pin.py --selftest
    python research/pin.py --data ./kalshi_data --out ./fulltape

THE CELL, AND WHY IT IS DIFFERENT FROM endgame.py's VERDICT

Settlement is the mean of 60 one-second prints and with tau seconds left,
60 - tau of them are LOCKED on our own disk. endgame.py's Part 1 shows the
exact consequence: at tau = 20 the remaining uncertainty is a small fraction
of what sqrt(tau) pretends, and by tau = 10 the sd/sigma ratio is 0.327/1.86
of naive -- fair value has almost stopped depending on any volatility
estimate. That is the one region where OUR model can be more right than a
lazy quote without knowing anything the tape does not contain.

endgame.py already swept "trade when |fair - mid| clears a floor" across the
whole last 120 seconds and found everything inside a 3.3-5.1c MDE. This is a
DIFFERENT cell with a different power profile: only seconds where the model
says the outcome is effectively decided (fair >= 0.98 or <= 0.02), and only
against a quote on the WRONG SIDE of that near-certainty -- an ask still
selling a near-won contract cheap, a bid still paying real cents for a
near-dead one. Four of the strategy panel's twenty-one candidates were this
one idea wearing different clothes, and it is the highest-confidence family
on the list precisely because the edge does not require anyone to be wrong
about anything difficult -- only slow.

THE HAZARD IS THE TAIL, so it is priced, printed, and controlled:

  * a pinned trade wins ~1-3c and loses ~97c. The claimed edge already nets
    the model's own flip probability; whether the model's flip probability
    is HONEST is exactly what the fair-band vs realised comparison decides.
    A realised P&L below the fair band means OUR sigma was too small in the
    tail, not that the market was slow. The self-test manufactures that
    exact failure and requires the report to catch it.
  * one trade per CLOSE (endgame.evaluate keys on close time), so n is
    close-time clusters by construction and a BTC crash that flips five
    series at once cannot masquerade as five losses' worth of independence
    -- or five wins'.
  * the earliest qualifying second is taken, never the best one -- taking
    the maximum disagreement in a window is a look-ahead endgame.py
    measured at -49.5c on a zero-edge tape.
  * the market-is-right null (outcomes redrawn at the MID) is printed next
    to the realised number, with the MDE, before anything is believed.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from statistics import NormalDist, mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import var_factor, N_AVG                        # noqa: E402
from settlewin import partial                               # noqa: E402
from endgame import (scan, evaluate, summarise, redraw_null,  # noqa: E402
                     mde, fee_cents, outcome_of, sigma_from)

ND = NormalDist()
PIN = 0.98                  # fair beyond this (or below 1-PIN) is "decided"
TAU_MAX = 60                # the sigma-proof region; also swept at 20
FLOORS = (0.3, 0.5, 1.0, 2.0)      # cents of fee-netted edge required


def pinned_rows(rows, pin=PIN):
    return [r for r in rows if r["fair"] >= pin or r["fair"] <= 1.0 - pin]


def flips(trades):
    """Trades where the near-certain side lost -- the tail, enumerated."""
    out = []
    for t in trades:
        won = t.get("won")
        if won is None:
            continue
        if (t["side"] == "yes" and won < 0.5) or \
           (t["side"] == "no" and won > 0.5):
            out.append(t)
    return out


def block(trades, label, reps=2000):
    """One (tau, floor) cell: MDE first, then the number, then both bands."""
    if not trades:
        print(f"    {label:<26} no trades qualified")
        return
    sm = summarise(trades, label)
    if sm is None:
        print(f"    {label:<26} {len(trades)} trades -- too few to score, "
              f"raw mean {mean(t['pnl'] for t in trades):+.2f}c")
        return
    fl = flips(trades)
    md = mde(trades)
    nm = redraw_null(trades, reps=reps, using="mid")
    nf = redraw_null(trades, reps=reps, using="fair")
    verdict = ""
    if sm["mean"] > nm["hi"] and sm["mean"] >= nf["lo"]:
        verdict = "  <-- beats the market-is-right null"
    elif sm["mean"] < nf["lo"]:
        verdict = "  <-- BELOW the fair band: OUR tail probability is wrong"
    print(f"    {label:<26} n={sm['n']:>4} closes  MDE {md:>5.2f}c  "
          f"claimed {sm['exp_edge']:+.2f}c  realised {sm['mean']:+.2f}c "
          f"(t={sm['t']:+.1f})")
    print(f"    {'':<26} flips {len(fl)}/{sm['n']}"
          f"  worst {min(t['pnl'] for t in trades):+.1f}c"
          f"  mid-null [{nm['lo']:+.2f},{nm['hi']:+.2f}]"
          f"  fair-band [{nf['lo']:+.2f},{nf['hi']:+.2f}]{verdict}")


def run_cells(rows, reps=2000):
    pr = pinned_rows(rows)
    print(f"\n  {len(rows):,} endgame quote-seconds, {len(pr):,} of them "
          f"pinned (fair beyond {PIN:.2f})")
    for tau_max in (20, TAU_MAX):
        sub = [r for r in pr if r["tau"] <= tau_max]
        print(f"\n  tau <= {tau_max}s")
        for floor in FLOORS:
            block(evaluate(sub, edge_floor=floor, rule="first"),
                  f"edge floor {floor:.1f}c", reps=reps)


# ===========================================================================
def _world(n_mkt, sigma_true, sigma_fed=None, book="stale", seed=1,
           step=900):
    """One series, one continuous index, consecutive 15-minute windows.

    book="stale":  the last 90 seconds quote frozen at the tau=90 fair +-1c.
                   Whatever the index does after that, the book sleeps
                   through -- the lazy quote this stage hunts.
    book="honest": every second re-quotes TRUE fair +-1c (computed with the
                   TRUE sigma). Nothing to harvest but the spread.
    """
    rnd = random.Random(seed)
    ticks = {}
    quotes, markets = {}, {}
    base = 1767225600
    px = 79000.0
    t = base - 200
    end = base + n_mkt * step + 5
    while t <= end:
        px += rnd.gauss(0, sigma_true)
        ticks[t] = px
        t += 1
    sigs = {"KXTEST": (sigma_fed if sigma_fed is not None else sigma_true)}

    def true_fair(close_s, now_s, strike):
        p = partial(ticks, close_s, now_s)
        if p is None:
            return None
        locked, r = p
        mu = (locked + r * ticks[now_s]) / N_AVG
        sd = sigma_true * math.sqrt(var_factor(int(close_s - now_s), [1.0]))
        if sd <= 0:
            return 1.0 if mu > strike else 0.0
        return ND.cdf((mu - strike) / sd)

    for k in range(n_mkt):
        open_s = base + k * step
        close_s = open_s + step
        tk = f"KXTEST-{k}"
        strike = ticks[open_s]          # 50/50 at the open
        ql = []
        frozen = None
        for s in range(close_s - 90, close_s):
            f = true_fair(close_s, s, strike)
            if f is None:
                continue
            if book == "stale":
                if frozen is None:
                    frozen = f
                f_q = frozen
            else:
                f_q = f
            bid = min(0.989, max(0.001, f_q - 0.01))
            ask = min(0.999, max(0.011, f_q + 0.01))
            ql.append((s, bid, ask, 50.0, 50.0))
        settle = mean(ticks[s] for s in range(close_s - N_AVG + 1,
                                              close_s + 1))
        quotes[tk] = ql
        markets[tk] = {"ticker": tk, "series": "KXTEST", "strike": strike,
                       "close": close_s, "settle": settle,
                       "result": 1.0 if settle >= strike else 0.0}
    return quotes, {"IDX": ticks}, markets, {"KXTEST": "IDX"}, sigs


def selftest():
    print("=" * 78)
    print("SELF-TEST -- against known answers")
    print("=" * 78)
    fails = []

    # ---- 1. a sleeping book must be harvested, and honestly --------------
    print("\n  A book that freezes 90 seconds out while the index decides")
    print("  the outcome. The harvest must collect, the realised mean must")
    print("  sit inside its own fair band and above the market-is-right")
    print("  null.")
    q, ix, mk, s2i, sigs = _world(300, sigma_true=8.0, book="stale", seed=3)
    rows = scan(q, ix, mk, s2i, sigs, tau_max=TAU_MAX)
    tr = evaluate(pinned_rows(rows), edge_floor=0.5, rule="first")
    sm = summarise(tr)
    nm = redraw_null(tr, reps=500, using="mid")
    nf = redraw_null(tr, reps=500, using="fair")
    print(f"    {sm['n']} closes, claimed {sm['exp_edge']:+.2f}c, "
          f"realised {sm['mean']:+.2f}c, mid-null hi {nm['hi']:+.2f}c, "
          f"fair band [{nf['lo']:+.2f},{nf['hi']:+.2f}]")
    if sm["n"] < 100:
        fails.append(f"only {sm['n']} closes harvested from 300 sleeping "
                     "markets -- the filter is throwing the cell away")
    if sm["mean"] <= nm["hi"]:
        fails.append("a frozen book was not beaten -- the one world where "
                     "this must collect")
    if not (nf["lo"] <= sm["mean"] <= nf["hi"]):
        fails.append(f"realised {sm['mean']:+.2f}c sits outside its own "
                     f"fair band [{nf['lo']:+.2f},{nf['hi']:+.2f}] -- the "
                     "claimed edge is dishonest about the flip probability")

    # ---- 2. an honest book must yield (nearly) nothing -------------------
    print("\n  The same world, but the book re-quotes true fair every")
    print("  second. Nothing to harvest but the spread and the fee.")
    q2, ix2, mk2, s2i2, sigs2 = _world(300, sigma_true=8.0, book="honest",
                                       seed=5)
    rows2 = scan(q2, ix2, mk2, s2i2, sigs2, tau_max=TAU_MAX)
    tr2 = evaluate(pinned_rows(rows2), edge_floor=0.5, rule="first")
    print(f"    trades against the honest book: {len(tr2)}")
    if len(tr2) > 15:
        sm2 = summarise(tr2)
        nm2 = redraw_null(tr2, reps=500, using="mid")
        if sm2 and nm2 and sm2["mean"] > nm2["hi"]:
            fails.append(f"the harvest claims {sm2['mean']:+.2f}c against a "
                         "book that is never wrong")

    # ---- 3. the tail-risk trap: OUR sigma too small ----------------------
    print("\n  The model is fed a sigma 4x too SMALL, so it calls outcomes")
    print("  decided while they are still coin-adjacent. The report must")
    print("  land BELOW the fair band -- the flag that says the model, not")
    print("  the market, is wrong.")
    q3, ix3, mk3, s2i3, sigs3 = _world(300, sigma_true=8.0, sigma_fed=2.0,
                                       book="honest", seed=7)
    rows3 = scan(q3, ix3, mk3, s2i3, sigs3, tau_max=TAU_MAX)
    tr3 = evaluate(pinned_rows(rows3), edge_floor=0.5, rule="first")
    if len(tr3) < 30:
        fails.append("the overconfident model produced almost no phantom "
                     "trades -- the trap fixture is not a trap")
    else:
        sm3 = summarise(tr3)
        nf3 = redraw_null(tr3, reps=500, using="fair")
        print(f"    {sm3['n']} closes, claimed {sm3['exp_edge']:+.2f}c, "
              f"realised {sm3['mean']:+.2f}c, fair band "
              f"[{nf3['lo']:+.2f},{nf3['hi']:+.2f}]")
        if sm3["mean"] >= nf3["lo"]:
            fails.append("an overconfident model's phantom edge was NOT "
                         "flagged: realised sits inside the fair band it "
                         "should have fallen out of")

    # ---- 4. the flip is priced into the claim ----------------------------
    print("\n  In the harvested world the claimed edge must already net the")
    print("  flip probability: |claimed - realised| within the fair band's")
    print("  own width (checked in test 1). Flip accounting:")
    fl = flips(tr)
    print(f"    {len(fl)} flips in {len(tr)} trades "
          f"({100.0 * len(fl) / max(1, len(tr)):.1f}%); "
          f"model said <= {100 * (1 - PIN):.0f}% per trade")
    if len(fl) > (1 - PIN) * len(tr) * 3 + 5:
        fails.append(f"{len(fl)} flips in {len(tr)} trades -- far beyond "
                     "the model's stated tail; fair is overconfident even "
                     "with the TRUE sigma")

    print()
    if fails:
        print("=" * 78)
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   - " + f)
        print("=" * 78)
        return False
    print("=" * 78)
    print("SELF-TEST PASSED -- collects from a sleeping book, stays silent")
    print("against an honest one, and flags its own overconfidence instead")
    print("of billing it as edge.")
    print("=" * 78)
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

    from replay import load_quotes, load_markets, load_index, SERIES_TO_INDEX
    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    quotes = load_quotes(a.data)
    if not quotes:
        print("\n  no quotes -- nothing to analyse")
        return
    markets = load_markets(a.out)
    if not markets:
        print("\n  *** NO SETTLED MARKETS -- nothing to analyse")
        return
    index = load_index(a.data)
    if not index:
        print("\n  no cfbenchmarks_value -- nothing to analyse")
        return

    # sigma per MARKET from the window strictly before the endgame, falling
    # back to a pooled per-series value. In this cell sigma barely matters --
    # that is the premise -- and the self-test's trap fixture is the check
    # that "barely" is not quietly "not at all".
    sigma_by_market, pooled_acc = {}, defaultdict(list)
    for tk, m in markets.items():
        s = m.get("series") or tk.split("-")[0]
        ticks = index.get(SERIES_TO_INDEX.get(s))
        close = m.get("close")
        if not ticks or not close:
            continue
        sg = sigma_from(ticks, int(close) - 900, int(close) - TAU_MAX - 10)
        if sg:
            sigma_by_market[tk] = sg
            pooled_acc[s].append(sg)
    pooled = {s: sorted(v)[len(v) // 2] for s, v in pooled_acc.items() if v}
    print(f"  per-market sigma for {len(sigma_by_market):,} markets, "
          f"pooled fallback for {len(pooled)} series")

    rows = scan(quotes, index, markets, SERIES_TO_INDEX, pooled,
                tau_max=TAU_MAX, sigma_by_market=sigma_by_market)
    if not rows:
        print("\n  nothing to analyse -- no endgame quote-seconds survived")
        return
    print("\n" + "=" * 78)
    print("THE PINNED ENDGAME -- quotes on the wrong side of a decided")
    print("outcome, taken at the earliest qualifying second, one per close")
    print("=" * 78)
    run_cells(rows)
    print("\n  Read the flags, not the means. 'Below the fair band' says our")
    print("  tail probability was wrong and the edge was fiction. Only a")
    print("  cell that beats the mid-null while staying inside its fair")
    print("  band is a strategy.")


if __name__ == "__main__":
    main()
