#!/usr/bin/env python3
"""_verify_pindraw.py -- ADVERSARIAL verification of pindraw/pindrawq/pindrawcase.

Read-only. Loads results/pindraw/state.pkl and re-derives every headline number
with its own arithmetic, then attacks the four things the headline rests on:

  1. LOOKAHEAD -- delete every row after the decision second and confirm the
     trigger fires at the same tau and the fill takes the same price.
  2. STALENESS / EXECUTABILITY -- what is the AGE of the quote that prices each
     hedge fill?  A 10c fill priced off a quote from 6 seconds ago is not a
     trade anyone could have made in the second the index crossed.
  3. OVERFIT -- drop the biggest one and two losing closes and re-read the tail.
  4. WIN UNIT -- the operator's unit is 2-5c per contract; check what
     "one win" actually is and how the headline moves under alternatives.
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


# --------------------------------------------------------------------------
def run_hedge_traced(pos, rows, trig, size_frac=1.0, retry=True, max_px=None,
                     max_age=None):
    """pindraw.run_hedge, but records (tau, px, qty, quote_age) per fill.

    `max_age` additionally refuses a fill whose quote is older than that many
    ms -- the freshness test pindraw does not run on the hedge leg.
    """
    want_n = float(pos["n"]) * float(size_frac)
    got = 0.0
    hedges, trace = [], []
    fired = None
    pos["_wrong_run"] = 0
    pos["_mu_run"] = 0
    for row in rows:
        tau, spot, mu, K, fair, sg, yb, ya, ybs, yas, age = row
        if tau >= pos["tau"]:
            continue
        if tau < 1:
            break
        wrong = (spot < K) if pos["want"] == "yes" else (spot >= K)
        pos["_wrong_run"] = pos["_wrong_run"] + 1 if wrong else 0
        mwrong = (mu < K) if pos["want"] == "yes" else (mu >= K)
        pos["_mu_run"] = pos.get("_mu_run", 0) + 1 if mwrong else 0
        if yb is None or age is None or age > PD.MAX_QUOTE_AGE_MS:
            pos["_mkt"] = None
        else:
            pos["_mkt"] = yb if pos["want"] == "yes" else round(1.0 - ya, 4)
        if fired is None:
            if not trig(row, pos):
                continue
            fired = tau
        if yb is None or age is None or age > PD.MAX_QUOTE_AGE_MS:
            if not retry:
                break
            continue
        if max_age is not None and age > max_age:
            if not retry:
                break
            continue
        if pos["want"] == "yes":
            px, avail = round(1.0 - yb, 4), ybs
        else:
            px, avail = ya, yas
        if max_px is not None and px is not None and px > max_px + 1e-12:
            if not retry:
                break
            continue
        if px is not None and 0.0 < px < 1.0 and avail > 0:
            q = min(want_n - got, float(avail))
            if q > 1e-9:
                hedges.append((q, px))
                trace.append((tau, px, q, age, mwrong))
                got += q
        if got >= want_n - 1e-9 or not retry:
            break
    return hedges, fired, want_n, trace


def per_close(ps, fn=None, **kw):
    ph = defaultdict(float)
    for p in ps:
        if fn is None:
            h = ()
        else:
            h = run_hedge_traced(dict(p), p["rows"], fn, **kw)[0]
        ph[p["close_s"]] += PD.leg_pnl(p["n"], p["price"], p["won"], h)
    return ph


def stats(ph, wu):
    v = list(ph.values())
    worst = -min(v) if min(v) < 0 else 0.0
    return dict(total=sum(v), worst=worst, worst_w=worst / wu,
                nloss=sum(1 for x in v if x < 0),
                p99=-(PD.pct(v, 1.0) or 0.0),
                p99_w=-(PD.pct(v, 1.0) or 0.0) / wu)


def win_unit(ps):
    b = defaultdict(float)
    for p in ps:
        b[p["close_s"]] += PD.leg_pnl(p["n"], p["price"], p["won"])
    w = [v for v in b.values() if v > 0]
    return (sum(w) / len(w) if w else float("nan"), PD.pct(w, 50), b)


# --------------------------------------------------------------------------
def selftest():
    print("SELF-TEST -- _verify_pindraw")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    trig = PD.make_triggers()["SPOT_CROSS"][0]
    # PLANTED: a cheap fresh hedge exists at tau 20 only; a max_age gate of
    # 1500 ms must keep it and a gate of 500 ms must refuse it.
    rows = []
    for t in range(29, 0, -1):
        age = 1000 if t == 20 else 30000
        rows.append((t, 99.0, 99.0, 100.0, 0.02, 0.5, 0.90, 0.08,
                     500.0, 500.0, age))
    pos = {"tk": "X", "tau": 30, "want": "yes", "price": 0.95, "n": 20.0}
    h, ft, wn, tr = run_hedge_traced(dict(pos), rows, trig, max_px=0.10,
                                     max_age=1500)
    ck(ft == 29 and len(tr) == 1 and tr[0][0] == 20 and tr[0][3] == 1000,
       "planted: with a 1500 ms freshness gate the only fresh quote (tau 20) "
       "is the one taken (%s)" % (tr,))
    h2, _, _, tr2 = run_hedge_traced(dict(pos), rows, trig, max_px=0.10,
                                     max_age=500)
    ck(h2 == [] and tr2 == [],
       "NULL: tighten the gate past every quote and NOTHING is bought -- the "
       "gate is doing the work, not the trigger")
    h3, _, _, tr3 = run_hedge_traced(dict(pos), rows, trig, max_px=0.10)
    ref = PD.run_hedge(dict(pos), rows, trig, max_px=0.10)[0]
    ck(sum(q for q, _ in h3) == 20.0 and
       abs(PD.leg_pnl(20, .95, False, h3)
           - PD.leg_pnl(20, .95, False, ref)) < 1e-12,
       "and with no freshness gate this reproduces pindraw.run_hedge exactly")
    # NULL: a world with no crossing must produce no firing and no fills
    flat = [(t, 101.0, 101.0, 100.0, 0.99, 0.5, 0.90, 0.08, 500.0, 500.0, 100)
            for t in range(29, 0, -1)]
    h4, ft4, _, tr4 = run_hedge_traced(dict(pos), flat, trig, max_px=0.10)
    ck(ft4 is None and h4 == [] and tr4 == [],
       "NULL: no crossing, no firing, no fill, nothing invented")
    # stats/win-unit arithmetic
    ph = {1: 2.0, 2: 2.0, 3: -10.0}
    s = stats(ph, 2.0)
    ck(abs(s["total"] + 6.0) < 1e-9 and abs(s["worst"] - 10.0) < 1e-9
       and abs(s["worst_w"] - 5.0) < 1e-9,
       "a -$10 close against a $2 win is 5.0 wins to recover (%.1f)"
       % s["worst_w"])
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--state", default=STATE)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    st = pickle.load(open(a.state, "rb"))
    T = PD.make_triggers()
    SC = T["SPOT_CROSS"][0]
    ps = st["positions"]["LIVE"]
    print("\n  LIVE positions %d  size=%s cap=%s"
          % (len(ps), st["size"], st["cap"]))

    wu, wu_med, base = win_unit(ps)
    b0 = stats(base, wu)
    print("  win unit mean $%.4f  median $%.4f" % (wu, wu_med))
    print("  unhedged total $%.2f worst $%.2f = %.1f wins  losing closes %d"
          % (b0["total"], b0["worst"], b0["worst_w"], b0["nloss"]))

    # ---- 1. REPRODUCE the headline rows ----------------------------------
    print("\n== 1. REPRODUCTION ==")
    for lbl, kw in (("cap10c full", dict(max_px=0.10)),
                    ("cap10c half", dict(max_px=0.10, size_frac=0.5)),
                    ("cap25c half", dict(max_px=0.25, size_frac=0.5)),
                    ("uncapped   ", dict())):
        s = stats(per_close(ps, SC, **kw), wu)
        print("  SPOT_CROSS %s: total $%.2f  worst $%.2f = %.1f w  "
              "p99 %.2f w  losing closes %d"
              % (lbl, s["total"], s["worst"], s["worst_w"], s["p99_w"],
                 s["nloss"]))

    # ---- 2. LOOKAHEAD ----------------------------------------------------
    print("\n== 2. LOOKAHEAD: truncate every row after the decision second ==")
    bad = 0
    checked = 0
    for p in ps:
        h, ft, wn, tr = run_hedge_traced(dict(p), p["rows"], SC, max_px=0.10)
        if ft is None:
            continue
        checked += 1
        cut = [r for r in p["rows"] if r[0] >= ft]
        h2, ft2, _, tr2 = run_hedge_traced(dict(p), cut, SC, max_px=0.10)
        if ft2 != ft:
            bad += 1
        elif tr and tr2 and tr[0][:2] != tr2[0][:2]:
            bad += 1
    print("  %d firings; disagreements after truncation: %d" % (checked, bad))

    # ---- 3. STALENESS of the quote that prices each hedge fill ------------
    print("\n== 3. STALENESS AT THE HEDGE FILL (cap 10c, full size) ==")
    ages, fill_tau, fire_tau, gaps = [], [], [], []
    mu_ok = 0
    nfill = 0
    for p in ps:
        h, ft, wn, tr = run_hedge_traced(dict(p), p["rows"], SC, max_px=0.10)
        if ft is None or not tr:
            continue
        nfill += 1
        for (tau, px, q, age, mwrong) in tr:
            ages.append(age)
            fill_tau.append(tau)
            gaps.append(ft - tau)
            if not mwrong:
                mu_ok += 1
        fire_tau.append(ft)
    print("  %d positions got a capped hedge; %d fills" % (nfill, len(ages)))
    for lbl, v in (("quote age ms", ages), ("fill tau s", fill_tau),
                   ("fire->fill gap s", gaps), ("fire tau s", fire_tau)):
        print("    %-18s median %9.0f  p75 %9.0f  p90 %9.0f  max %9.0f"
              % (lbl, PD.pct(v, 50), PD.pct(v, 75), PD.pct(v, 90), max(v)))
    print("  fills taken while the PROJECTED settlement was still on OUR "
          "side: %d of %d" % (mu_ok, len(ages)))
    stale = sum(1 for x in ages if x > 2000)
    print("  fills priced off a quote OLDER THAN 2 s (pinrun's own live "
          "gate): %d of %d = %.1f%%"
          % (stale, len(ages), 100.0 * stale / max(len(ages), 1)))

    print("\n  the same rule with a FRESHNESS gate on the hedge leg:")
    for g in (None, 5000, 2000, 1000):
        s = stats(per_close(ps, SC, max_px=0.10, max_age=g), wu)
        caught = sum(1 for p in ps if not p["won"] and
                     run_hedge_traced(dict(p), p["rows"], SC, max_px=0.10,
                                      max_age=g)[0])
        print("    max_age %5s ms : total $%7.2f  worst $%6.2f = %4.1f w  "
              "losing closes %3d  losers hedged %d"
              % (str(g), s["total"], s["worst"], s["worst_w"], s["nloss"],
                 caught))

    # ---- 4. OVERFIT: drop the biggest losing closes ----------------------
    print("\n== 4. OVERFIT: drop the biggest unhedged losing closes ==")
    order = sorted(base, key=lambda c: base[c])
    for k in (0, 1, 2, 3):
        drop = set(order[:k])
        sub = [p for p in ps if p["close_s"] not in drop]
        wu2, _, b2 = win_unit(sub)
        s0 = stats(b2, wu2)
        s1 = stats(per_close(sub, SC, max_px=0.10), wu2)
        print("  drop %d: unhedged worst $%.2f (%.1f w) -> capped $%.2f "
              "(%.1f w); cost $%.2f"
              % (k, s0["worst"], s0["worst_w"], s1["worst"], s1["worst_w"],
                 s1["total"] - s0["total"]))

    # ---- 5. THE POPULATION WE ACTUALLY TRADE ----------------------------
    print("\n== 5. COST ON THE PRICES THE LIVE RULE ACTUALLY PAYS ==")
    for lo, hi, lbl in ((0.90, 1.01, ">=90c"), (0.95, 1.01, ">=95c")):
        sub = [p for p in ps if lo <= p["price"] < hi]
        wu2, wmed, b2 = win_unit(sub)
        s0 = stats(b2, wu2)
        s1 = stats(per_close(sub, SC, max_px=0.10), wu2)
        nl = sum(1 for p in sub if not p["won"])
        print("  %s: %d buys, %d closes, %d losing buys, one win $%.4f "
              "(median $%.4f)" % (lbl, len(sub), len(b2), nl, wu2, wmed))
        print("      unhedged $%.2f worst $%.2f = %.1f w   capped10c $%.2f "
              "worst $%.2f = %.1f w  cost $%.2f (%+.1f%%)"
              % (s0["total"], s0["worst"], s0["worst_w"], s1["total"],
                 s1["worst"], s1["worst_w"], s1["total"] - s0["total"],
                 100 * (s1["total"] - s0["total"]) / s0["total"]))

    # ---- 6. WIN UNIT ----------------------------------------------------
    print("\n== 6. THE OPERATOR'S UNIT ==")
    wins = [v for v in base.values() if v > 0]
    cents = []
    for p in ps:
        if p["won"]:
            cents.append(100.0 * PD.leg_pnl(p["n"], p["price"], True) / p["n"])
    print("  per-CONTRACT cents on a winning buy: median %.2fc  mean %.2fc  "
          "p90 %.2fc" % (PD.pct(cents, 50), sum(cents) / len(cents),
                         PD.pct(cents, 90)))
    print("  per-CLOSE profit: mean $%.4f  median $%.4f" % (wu, wu_med))
    print("  worst close -$%.2f = %.1f wins at the MEAN win, %.1f wins at "
          "the MEDIAN win" % (b0["worst"], b0["worst"] / wu,
                              b0["worst"] / wu_med))

    # ---- 7. RACE HAIRCUT -------------------------------------------------
    print("\n== 7. IF THE HEDGE LOSES THE RACE AS OFTEN AS THE ENTRY (26%) ==")
    for seed in (1, 2, 3, 4, 5):
        rnd = random.Random(seed)
        ph = defaultdict(float)
        for p in ps:
            h, ft, wn, tr = run_hedge_traced(dict(p), p["rows"], SC,
                                             max_px=0.10)
            h = [x for x in h if rnd.random() > 0.26]
            ph[p["close_s"]] += PD.leg_pnl(p["n"], p["price"], p["won"], h)
        s = stats(ph, wu)
        print("    seed %d: total $%.2f  worst $%.2f = %.1f w"
              % (seed, s["total"], s["worst"], s["worst_w"]))

    # ---- 8. what the capped hedge actually is ---------------------------
    print("\n== 8. WHAT THE CAPPED RULE IS BUYING ==")
    fired = filled = lose_fired = lose_filled = 0
    for p in ps:
        h, ft, wn, tr = run_hedge_traced(dict(p), p["rows"], SC, max_px=0.10)
        if ft is not None:
            fired += 1
            if not p["won"]:
                lose_fired += 1
        if h:
            filled += 1
            if not p["won"]:
                lose_filled += 1
    nlose = sum(1 for p in ps if not p["won"])
    print("  fires on %d of %d buys; fills on %d. Of the %d losing buys: "
          "fired %d, filled %d." % (fired, len(ps), filled, nlose,
                                    lose_fired, lose_filled))


if __name__ == "__main__":
    main()
