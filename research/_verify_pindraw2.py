#!/usr/bin/env python3
"""_verify_pindraw2.py -- the controls pindraw.py did not run.

THE MISSING NULL. pindraw's null world prices the hedge at its FAIR value (25c
on a 25% chance) and shows a useless trigger then costs exactly the fees. That
is the right null for an EV question. It is the WRONG null for the recommended
rule, which refuses any hedge dearer than 10c: a hedge bought below fair value
improves the tail no matter what fires it. The control that settles it is a
trigger that carries no information at all -- fire on EVERY position, one second
after entry -- under the same 10c cap. If that matches SPOT_CROSS, the crossing
is contributing nothing and the result is "cheap insurance", not "a signal".

Also here:
  * fill depth split by whether the PROJECTED settlement had actually crossed,
    which is the only slice that speaks to IDEAS_LOG #29;
  * a close-level bootstrap of the WORST-CLOSE statistic, which the headline
    reports as a point with no interval.
"""
import argparse
import os
import pickle
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pindraw as PD                                          # noqa: E402
from _verify_pindraw import run_hedge_traced, win_unit, stats  # noqa: E402

STATE = r"C:\kals-repo\results\pindraw\state.pkl"


def always(row, pos):
    """A trigger with no information in it whatsoever."""
    return True


def never(row, pos):
    return False


def selftest():
    print("SELF-TEST -- _verify_pindraw2")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # PLANTED: a world where the crossing IS the signal and the hedge is only
    # offered cheap on the crossers. ALWAYS must then do strictly worse than
    # SPOT_CROSS, because it buys the same insurance on the winners too.
    SC = PD.make_triggers()["SPOT_CROSS"][0]
    ph_a, ph_s = {}, {}
    for i in range(40):
        lose = i < 10
        rows = [(t, 99.0 if (lose and t <= 20) else 101.0,
                 99.0 if (lose and t <= 20) else 101.0, 100.0,
                 0.02 if (lose and t <= 20) else 0.995, 0.5,
                 0.92, 0.94, 500.0, 500.0, 100) for t in range(29, 0, -1)]
        pos = {"tk": "P%d" % i, "close_s": i, "tau": 30, "want": "yes",
               "price": 0.95, "n": 20.0}
        for fn, dst in ((always, ph_a), (SC, ph_s)):
            h = run_hedge_traced(dict(pos), rows, fn, max_px=0.10)[0]
            dst[i] = PD.leg_pnl(20.0, 0.95, not lose, h)
    ck(sum(ph_s.values()) > sum(ph_a.values()),
       "planted: when the crossing IS the signal, SPOT_CROSS beats the "
       "information-free ALWAYS control ($%.2f vs $%.2f)"
       % (sum(ph_s.values()), sum(ph_a.values())))
    # NULL: every position crosses, so the trigger carries no information and
    # the two must be identical to the cent.
    ph_a, ph_s = {}, {}
    for i in range(40):
        lose = i < 10
        rows = [(t, 99.0, 99.0, 100.0, 0.5, 0.5, 0.92, 0.94, 500.0, 500.0,
                 100) for t in range(29, 0, -1)]
        pos = {"tk": "N%d" % i, "close_s": i, "tau": 30, "want": "yes",
               "price": 0.95, "n": 20.0}
        for fn, dst in ((always, ph_a), (SC, ph_s)):
            h = run_hedge_traced(dict(pos), rows, fn, max_px=0.10)[0]
            dst[i] = PD.leg_pnl(20.0, 0.95, not lose, h)
    ck(abs(sum(ph_s.values()) - sum(ph_a.values())) < 1e-9,
       "NULL: when everything crosses, the control and the trigger agree "
       "exactly ($%.4f) -- the comparison measures selectivity and nothing "
       "else" % sum(ph_s.values()))
    ck(run_hedge_traced({"tau": 30, "want": "yes", "price": 0.95, "n": 20.0},
                        [(t, 99.0, 99.0, 100.0, 0.5, 0.5, 0.92, 0.94, 5.0,
                          5.0, 100) for t in range(29, 0, -1)],
                        never, max_px=0.10)[0] == [],
       "NULL: a trigger that never fires buys nothing")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


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
    wu, wu_med, base = win_unit(ps)
    b0 = stats(base, wu)

    print("\n== A. THE MISSING CONTROL: an information-free trigger, same cap ==")
    print("   %-34s %9s %9s %7s %7s %7s"
          % ("rule", "total$", "worst$", "worstW", "losing", "hedged"))
    print("   %-34s %9.2f %9.2f %7.1f %7d %7s"
          % ("NO HEDGE", b0["total"], b0["worst"], b0["worst_w"],
             b0["nloss"], "-"))
    for lbl, fn, cap in (("SPOT_CROSS, cap 10c", SC, 0.10),
                         ("ALWAYS (no information), cap 10c", always, 0.10),
                         ("SPOT_CROSS, cap 5c", SC, 0.05),
                         ("ALWAYS (no information), cap 5c", always, 0.05),
                         ("SPOT_CROSS, cap 25c", SC, 0.25),
                         ("ALWAYS (no information), cap 25c", always, 0.25)):
        ph = defaultdict(float)
        nl = 0
        for p in ps:
            h = run_hedge_traced(dict(p), p["rows"], fn, max_px=cap)[0]
            if h and not p["won"]:
                nl += 1
            ph[p["close_s"]] += PD.leg_pnl(p["n"], p["price"], p["won"], h)
        s = stats(ph, wu)
        print("   %-34s %9.2f %9.2f %7.1f %7d %7d"
              % (lbl, s["total"], s["worst"], s["worst_w"], s["nloss"], nl))

    print("\n== B. WHAT SIDE ARE WE BUYING? (uncapped SPOT_CROSS) ==")
    dep_ok, dep_wrong = [], []
    n_ok = n_wrong = 0
    px_ok, px_wrong = [], []
    for p in ps:
        h, ft, wn, tr = run_hedge_traced(dict(p), p["rows"], SC)
        for (tau, px, q, age, mwrong) in tr:
            if mwrong:
                n_wrong += 1
                px_wrong.append(px)
                dep_wrong.append(q)
            else:
                n_ok += 1
                px_ok.append(px)
                dep_ok.append(q)
    print("   fills while the projected settlement was STILL ON OUR SIDE "
          "(market thinks we win):")
    print("     n=%d  median price %.3f  median qty %.1f"
          % (n_ok, PD.pct(px_ok, 50), PD.pct(dep_ok, 50)))
    print("   fills while the projected settlement had CROSSED (real danger, "
          "IDEAS_LOG #29 territory):")
    if n_wrong:
        print("     n=%d  median price %.3f  median qty %.1f"
              % (n_wrong, PD.pct(px_wrong, 50), PD.pct(dep_wrong, 50)))
    else:
        print("     n=0")

    print("\n== C. BOOTSTRAP THE WORST CLOSE (2,000 resamples of CLOSES) ==")
    capped = defaultdict(float)
    for p in ps:
        h = run_hedge_traced(dict(p), p["rows"], SC, max_px=0.10)[0]
        capped[p["close_s"]] += PD.leg_pnl(p["n"], p["price"], p["won"], h)
    keys = sorted(base)
    rnd = random.Random(11)
    d = []
    wb, wc = [], []
    for _ in range(2000):
        idx = [rnd.randrange(len(keys)) for _ in range(len(keys))]
        w0 = -min(base[keys[i]] for i in idx)
        w1 = -min(capped[keys[i]] for i in idx)
        wb.append(w0)
        wc.append(w1)
        d.append(w1 - w0)
    d.sort()
    wb.sort()
    wc.sort()
    print("   unhedged worst close: median $%.2f  95%% [%.2f, %.2f]"
          % (wb[1000], wb[50], wb[1949]))
    print("   capped   worst close: median $%.2f  95%% [%.2f, %.2f]"
          % (wc[1000], wc[50], wc[1949]))
    print("   difference (capped - unhedged): median $%.2f  95%% [%.2f, %.2f]"
          % (d[1000], d[50], d[1949]))
    print("   share of resamples where the hedge did NOT improve the worst "
          "close: %.1f%%" % (100.0 * sum(1 for x in d if x >= -1e-9) / len(d)))


if __name__ == "__main__":
    main()
