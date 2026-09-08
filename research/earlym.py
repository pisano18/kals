#!/usr/bin/env python3
# VERSION: 2026-09-08-em1
"""earlym.py -- M(index, tau): the largest move this index has ACTUALLY made.

THE QUANTITY, AND WHY IT IS NOT A VOLATILITY

With tau seconds to close, the settlement is the mean of 60 one-second
prints of which r are still unpublished. Those r prints sit at offsets
[a, b] from now, a = max(1, tau-60), b = tau-1. The market can only flip if
the MEAN OF THOSE r PRINTS lands the other side of the strike. So the
quantity that decides a flip is not sigma and not the price range -- it is

    g_tau(t) = | mean(v[t+a] .. v[t+b]) - v[t] |

the displacement of the future r-print average away from the spot you can
see right now. M(index, tau, window) is the MAXIMUM of that over a trailing
window. An arithmetic lock says: the move required to flip this market is
larger than anything this index has done at this horizon. It needs no
Gaussian, which is the whole point -- far from the close the Gaussian is
doing all the work and the tau<=60 probability cell is dead (+0.17c, t=+0.5).

NO-LOOKAHEAD, ENFORCED STRUCTURALLY
  M is stored per WHOLE UTC DAY. A close in day D may only read the daily
  maxima of days D-1, D-2, D-3. An anchor is dropped if t+b crosses its own
  day's end, so every value that feeds a day's maximum is stamped inside
  that day. There is therefore no arithmetic path from a close to its own
  day, let alone to its own future: the code cannot express one.

  earlyleak.py builds deliberately leaking variants of exactly this table
  and shows they score implausibly better.
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import earlyidx                                             # noqa: E402

CACHE = os.path.join(os.path.dirname(HERE), "early_cache")
DAY = 86400

TAUS = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 90, 105, 120]


def offsets(tau):
    """(a, b, r): the offsets of the still-unpublished settlement prints."""
    a = max(1, tau - 60)
    b = tau - 1
    return a, b, b - a + 1


def prep(vals):
    """forward-filled values, prefix sums, prefix observed-counts."""
    n = len(vals)
    F = vals[:]                       # array('d') copy
    P = [0.0] * (n + 1)
    C = [0] * (n + 1)
    last = 0.0
    for i in range(n):
        v = F[i]
        if v == 0.0:
            F[i] = last
            C[i + 1] = C[i]
        else:
            last = v
            C[i + 1] = C[i] + 1
        P[i + 1] = P[i] + F[i]
    return F, P, C


def daymax(T0, vals, taus=TAUS, verbose=True):
    """{tau: {day: max g_tau over anchors wholly inside that day}}"""
    F, P, C = prep(vals)
    n = len(vals)
    out = {}
    for tau in taus:
        a, b, r = offsets(tau)
        d = {}
        # an anchor may not reach past the end of its own UTC day
        for t in range(n - b - 1):
            if C[t + 1] - C[t] != 1:              # spot itself unobserved
                continue
            if C[t + b + 1] - C[t + a] != r:      # a gap inside the window
                continue
            abs_t = T0 + t
            day = abs_t // DAY
            if (abs_t + b) // DAY != day:         # crosses the day boundary
                continue
            g = (P[t + b + 1] - P[t + a]) / r - F[t]
            if g < 0:
                g = -g
            # a day with a valid anchor is RECORDED even if its max is 0.0,
            # so that "no entry" always means "no usable history" and never
            # "a quiet day". Conflating those would silently skip closes.
            if g > d.get(day, -1.0):
                d[day] = g
        out[tau] = d
    return out


def build(verbose=True):
    T0, idx = earlyidx.load()
    tab = {}
    for iid in sorted(idx):
        dm = daymax(T0, idx[iid], verbose=verbose)
        tab[iid] = {str(t): {str(k): v for k, v in dm[t].items()} for t in dm}
        if verbose:
            days = sorted(dm[60])
            print("  %-14s %d days   M(60) median %.6g   M(120) median %.6g"
                  % (iid, len(days),
                     sorted(dm[60].values())[len(days)//2],
                     sorted(dm[120].values())[len(dm[120])//2]))
    with open(os.path.join(CACHE, "mtab.json"), "w") as f:
        json.dump({"T0": T0, "taus": TAUS, "tab": tab}, f)
    if verbose:
        print("\n  wrote %s" % os.path.join(CACHE, "mtab.json"))
    return tab


def load():
    d = json.load(open(os.path.join(CACHE, "mtab.json")))
    tab = {}
    for iid, per in d["tab"].items():
        tab[iid] = {int(t): {int(k): v for k, v in m.items()}
                    for t, m in per.items()}
    return d["T0"], d["taus"], tab


def M_for(tab, iid, tau, close_s, back_days=3):
    """max of the daily maxima of the back_days WHOLE DAYS BEFORE close_s."""
    d0 = close_s // DAY
    per = tab.get(iid, {}).get(tau)
    if not per:
        return None, 0
    best, got = 0.0, 0
    for k in range(1, back_days + 1):
        v = per.get(d0 - k)
        if v is not None:
            best = max(best, v)
            got += 1
    return (best if got else None), got


def selftest():
    print("SELF-TEST -- earlym")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # 1. offsets reproduce the settlement window arithmetic
    ck(offsets(20) == (1, 19, 19), "tau=20 -> 19 prints still to come")
    ck(offsets(60) == (1, 59, 59), "tau=60 -> 59 prints still to come")
    ck(offsets(61) == (1, 60, 60), "tau=61 -> the full 60 are unpublished")
    ck(offsets(120) == (60, 119, 60), "tau=120 -> 60 prints, 60..119 s out")

    # 2. a PLANTED move must be found. Build a flat series with one ramp of
    #    known size and require M to equal it.
    import array
    n = 3 * DAY
    v = array.array("d", [100.0]) * n
    T0 = 0
    # a ramp on day 1: 60 prints at 100.5 starting at second 1000+1
    for k in range(1000 + 1, 1000 + 61):
        v[DAY + k] = 100.5
    dm = daymax(T0, v, taus=[61])
    got = dm[61].get(1, 0.0)
    ck(abs(got - 0.5) < 1e-9,
       "a planted 0.5 step in the next 60 prints is found exactly (%.6f)" % got)
    ck(dm[61].get(0, 0.0) < 1e-9,
       "and day 0, which contains no move, reports 0")

    # 3. NOTHING planted -> nothing found (the estimator must be able to fail)
    v2 = array.array("d", [100.0]) * n
    dm2 = daymax(T0, v2, taus=[61])
    ck(dm2[61] and max(dm2[61].values()) < 1e-9,
       "a flat world reports M = 0 on every day it has anchors for")

    # 4. an anchor may NOT reach across its own day boundary
    v3 = array.array("d", [100.0]) * n
    for k in range(DAY, DAY + 60):        # the move is entirely in day 1
        v3[k] = 101.0
    dm3 = daymax(T0, v3, taus=[61])
    ck(dm3[61].get(0, 0.0) < 1e-9,
       "day 0 cannot see a move that happens in day 1 (no boundary leak)")

    # 5. M_for reads only STRICTLY EARLIER days
    tab = {"X": {60: {10: 5.0, 11: 7.0, 12: 99.0}}}
    m, got = M_for(tab, "X", 60, 12 * DAY + 500, back_days=2)
    ck(m == 7.0 and got == 2,
       "a close in day 12 reads days 11 and 10 and NEVER day 12 (%s)" % m)

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    return not fails


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")
    print()
    build()
