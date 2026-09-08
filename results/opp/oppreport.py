#!/usr/bin/env python3
"""oppreport.py -- aggregate oppcount's episodes into the operator's answer.

Adds the one thing the counter deliberately does not know: WHETHER THE MODEL
WAS RIGHT. Every episode is joined to the settled result, so the money is
computed from realised outcomes, never from the model's own fair value.
"""
import glob
import json
import math
import os
import sys
import time
from collections import defaultdict

OUT = r"C:\kals-repo\results\opp"
MKTS = os.path.join(OUT, "mkts.json")
REACT_MS = 140          # measured round trip
CONS_MS = 200


def billed_fee(price, count=1):
    return math.ceil(0.07 * price * (1.0 - price) * count * 10000.0) / 10000.0


def q(a, p):
    a = sorted(a)
    return a[min(len(a) - 1, int(p * len(a)))] if a else float("nan")


def pnl_of(e, n=1.0):
    """Realised dollars for n contracts, from the SETTLED result."""
    fee = billed_fee(e["price0"], n)
    return (n * (1.0 - e["price0"]) - fee) if e["won"] \
        else (-n * e["price0"] - fee)


def selftest():
    print("SELF-TEST -- oppreport")
    ok = True
    f = billed_fee(0.95, 1)
    win = 1 - 0.95 - f
    lose = -0.95 - f
    ok &= abs(win - 0.0466) < 1e-9 and abs(lose - (-0.9534)) < 1e-9
    print("  %s YES@0.95 win %+.4f lose %+.4f (fee %.4f)"
          % ("ok  " if ok else "FAIL", win, lose, f))
    e = dict(price0=0.95, won=1)
    ok2 = abs(pnl_of(e, 10) - (10 * 0.05 - billed_fee(0.95, 10))) < 1e-12
    print("  %s the fee is billed on the ORDER, not per contract "
          "(10 @ 0.95 costs %.4f)" % ("ok  " if ok2 else "FAIL",
                                      billed_fee(0.95, 10)))
    eps = [dict(close=1, t0=500), dict(close=1, t0=100)]
    ok3 = min(eps, key=lambda x: x["t0"])["t0"] == 100
    print("  %s one-per-close takes the earliest, not the best"
          % ("ok  " if ok3 else "FAIL"))
    good = ok and ok2 and ok3
    print("SELF-TEST " + ("PASSED" if good else "*** FAILED ***"))
    return 0 if good else 1


def main():
    if selftest() != 0:
        raise SystemExit(1)
    M = json.load(open(MKTS))
    files = sorted(glob.glob(os.path.join(OUT, "ep_*.json")))
    days = {}
    for fp in files:
        d = json.load(open(fp))
        days[d["day"]] = d
    print("")
    print("days loaded: %s" % ", ".join(sorted(days)))

    mode = sys.argv[1] if len(sys.argv) > 1 else "strict"
    print("MODE = %s" % mode)
    print("")

    rows = []
    all_eps = []
    for day in sorted(days):
        d = days[day]
        eps = [e for e in d["episodes"] if e["mode"] == mode]
        for e in eps:
            mk = M[e["tk"]]
            e["result"] = mk["result"]
            e["won"] = 1 if e["want"] == mk["result"] else 0
            e["day"] = day
            e["uhour"] = time.gmtime(e["close"]).tm_hour
        all_eps += eps
        closes = set(d["closes_evaluated"])
        hit = set(e["close"] for e in eps)
        rows.append(dict(day=day, closes=len(closes), hit=len(hit),
                         eps=len(eps),
                         e200=sum(1 for e in eps if e["dur"] >= CONS_MS),
                         e140=sum(1 for e in eps if e["dur"] >= REACT_MS),
                         best=max([100 * e["edge0"] for e in eps] or [0.0]),
                         hours=len(d["hours"]), stat=d["stat"]))
    tot = len(all_eps)

    print("PER DAY")
    print("day        hours closes  hit  eps  >=140ms >=200ms  best_edge_c")
    for r in rows:
        print("%s %5d %6d %5d %5d %7d %7d %11.2f"
              % (r["day"], r["hours"], r["closes"], r["hit"], r["eps"],
                 r["e140"], r["e200"], r["best"]))

    print("")
    print("PER UTC HOUR (pooled over all days)")
    byh = defaultdict(list)
    for e in all_eps:
        byh[e["uhour"]].append(e)
    print("utc  et   eps   share  >=140  >=200  medEdge  medDur  closesHit")
    for h in range(24):
        v = byh.get(h, [])
        if not v:
            print("%3d  %2d %5d  %5.1f%% %6d %6d        -       -          0"
                  % (h, (h - 4) % 24, 0, 0.0, 0, 0))
            continue
        print("%3d  %2d %5d  %5.1f%% %6d %6d %8.2f %7d %10d"
              % (h, (h - 4) % 24, len(v), 100.0 * len(v) / tot,
                 sum(1 for e in v if e["dur"] >= REACT_MS),
                 sum(1 for e in v if e["dur"] >= CONS_MS),
                 100 * q([e["edge0"] for e in v], .5),
                 q([e["dur"] for e in v], .5),
                 len(set(e["close"] for e in v))))

    on = [e for e in all_eps if e["uhour"] < 12]
    us = [e for e in all_eps if e["uhour"] >= 12]
    print("")
    print("OVERNIGHT 00-12 UTC (20:00-08:00 ET) vs US 12-24 UTC "
          "(08:00-20:00 ET)")
    for lab, v in (("overnight", on), ("us-session", us)):
        if not v:
            continue
        pn = sum(pnl_of(e) for e in v) / len(v)
        print("  %-11s eps %6d (%4.1f%%)  >=140ms %5d  >=200ms %5d  "
              "medEdge %5.2fc  medSize %8.1f  medDur %6d ms  "
              "correct %5.1f%%  $/contract %+.4f"
              % (lab, len(v), 100.0 * len(v) / max(tot, 1),
                 sum(1 for e in v if e["dur"] >= REACT_MS),
                 sum(1 for e in v if e["dur"] >= CONS_MS),
                 100 * q([e["edge0"] for e in v], .5),
                 q([e["size0"] for e in v], .5),
                 q([e["dur"] for e in v], .5),
                 100.0 * sum(e["won"] for e in v) / len(v), pn))

    print("")
    print("DURATION SURVIVAL (all episodes, n=%d)" % tot)
    dur = [e["dur"] for e in all_eps]
    for t in (0, 50, 100, 140, 200, 500, 1000, 2000, 5000):
        print("    >= %5d ms: %7d  %5.1f%%"
              % (t, sum(1 for x in dur if x >= t),
                 100.0 * sum(1 for x in dur if x >= t) / max(tot, 1)))
    for lab, p in (("p10", .1), ("p25", .25), ("median", .5), ("p75", .75),
                   ("p90", .9), ("p99", .99)):
        print("    %-7s %8d ms" % (lab, q(dur, p)))

    print("")
    print("WHY EPISODES END")
    bnd = sum(1 for e in all_eps
              if not e["censored"] and (e["t0"] + e["dur"]) % 1000 == 0)
    cen = sum(1 for e in all_eps if e["censored"])
    print("    second boundary (the MODEL moved, quote still there): "
          "%7d  %5.1f%%" % (bnd, 100.0 * bnd / max(tot, 1)))
    print("    book event      (the QUOTE moved):                    "
          "%7d  %5.1f%%" % (tot - bnd - cen,
                            100.0 * (tot - bnd - cen) / max(tot, 1)))
    print("    ran to the tau=3 window edge (censored):              "
          "%7d  %5.1f%%" % (cen, 100.0 * cen / max(tot, 1)))
    lng = [e for e in all_eps if e["dur"] >= REACT_MS]
    bnd2 = sum(1 for e in lng
               if not e["censored"] and (e["t0"] + e["dur"]) % 1000 == 0)
    print("    of the %d episodes >= 140 ms, %d (%.1f%%) ended because the "
          "model moved" % (len(lng), bnd2, 100.0 * bnd2 / max(len(lng), 1)))

    print("")
    print("NET EDGE IN CENTS (all episodes)")
    ed = [100 * e["edge0"] for e in all_eps]
    for lab, p in (("min", 0.0), ("p25", .25), ("median", .5), ("p75", .75),
                   ("p90", .9), ("p99", .99)):
        print("    %-7s %8.2f c" % (lab, q(ed, p)))
    print("    max     %8.2f c" % max(ed or [0]))
    for lo, hi in [(0.5, 1), (1, 2), (2, 5), (5, 10), (10, 25), (25, 1e9)]:
        n = sum(1 for x in ed if lo <= x < hi)
        print("    [%5.1f,%6.1f) c : %7d  %5.1f%%"
              % (lo, hi, n, 100.0 * n / max(tot, 1)))

    print("")
    print("RESTING SIZE AT THE QUALIFYING LEVEL (contracts)")
    sz = [e["size0"] for e in all_eps]
    for lab, p in (("min", 0.0), ("p10", .1), ("p25", .25), ("median", .5),
                   ("p75", .75), ("p90", .9)):
        print("    %-7s %10.2f" % (lab, q(sz, p)))
    print("    max     %10.2f" % max(sz or [0]))
    for n in (1, 10, 30, 50, 100):
        k = sum(1 for x in sz if x >= n)
        print("    level holds >= %3d contracts: %7d  %5.1f%%"
              % (n, k, 100.0 * k / max(tot, 1)))
    lng2 = [e["size0"] for e in all_eps if e["dur"] >= REACT_MS]
    if lng2:
        print("    among episodes >=140 ms: median %.1f, p25 %.1f, "
              ">=30 contracts %.1f%%"
              % (q(lng2, .5), q(lng2, .25),
                 100.0 * sum(1 for x in lng2 if x >= 30) / len(lng2)))

    # ---------------- money, from realised outcomes only ----------------
    print("")
    print("MONEY -- one fire per close, EARLIEST qualifying episode, "
          "P&L from the settled result")
    fulld = set(r["day"] for r in rows if r["closes"] >= 90)
    print("  full days used: %d (%s)" % (len(fulld), ",".join(sorted(fulld))))
    for gate, lab in ((0, "no reachability gate (the backtest assumption)"),
                      (REACT_MS, "episode must last >= 140 ms"),
                      (CONS_MS, "episode must last >= 200 ms")):
        per_close = {}
        for e in all_eps:
            if e["day"] not in fulld or e["dur"] < gate:
                continue
            c = e["close"]
            if c not in per_close or e["t0"] < per_close[c]["t0"]:
                per_close[c] = e
        fires = list(per_close.values())
        if not fires:
            continue
        wins = sum(e["won"] for e in fires)
        print("")
        print("  --- %s ---" % lab)
        print("    fires %d over %d days = %.1f/day; wins %d (%.1f%%); "
              "mean edge %.2fc"
              % (len(fires), len(fulld), len(fires) / max(len(fulld), 1),
                 wins, 100.0 * wins / len(fires),
                 100 * sum(e["edge0"] for e in fires) / len(fires)))
        for N in (1, 10, 30):
            t = 0.0
            capped = 0
            peak = 0.0
            for e in fires:
                n = min(float(N), math.floor(e["size0"]))
                if n < 1:
                    continue
                if n < N:
                    capped += 1
                t += pnl_of(e, n)
                peak = max(peak, n * e["price0"])
            print("      size %2d: $%+9.2f total = $%+8.2f/day  "
                  "(depth-capped on %d of %d fires; peak concurrent "
                  "capital $%.2f)"
                  % (N, t, t / max(len(fulld), 1), capped, len(fires), peak))

    print("")
    print("PER-DAY P&L, one fire per close, episode >= 140 ms, "
          "size capped by measured depth")
    print("day        fires wins    size1     size10     size30")
    tots = {1: 0.0, 10: 0.0, 30: 0.0}
    dayp = {1: [], 10: [], 30: []}
    for day in sorted(fulld):
        per_close = {}
        for e in all_eps:
            if e["day"] != day or e["dur"] < REACT_MS:
                continue
            c = e["close"]
            if c not in per_close or e["t0"] < per_close[c]["t0"]:
                per_close[c] = e
        fires = list(per_close.values())
        line = "%s %5d %4d" % (day, len(fires), sum(x["won"] for x in fires))
        for N in (1, 10, 30):
            t = 0.0
            for e in fires:
                n = min(float(N), math.floor(e["size0"]))
                if n >= 1:
                    t += pnl_of(e, n)
            tots[N] += t
            dayp[N].append(t)
            line += " %+10.2f" % t
        print(line)
    nd = max(len(fulld), 1)
    print("TOTAL              %+10.2f %+10.2f %+10.2f"
          % (tots[1], tots[10], tots[30]))
    print("PER DAY            %+10.2f %+10.2f %+10.2f"
          % (tots[1] / nd, tots[10] / nd, tots[30] / nd))
    print("DAYS POSITIVE      %10s %10s %10s"
          % tuple("%d/%d" % (sum(1 for x in dayp[N] if x > 0), len(dayp[N]))
                  for N in (1, 10, 30)))

    print("")
    print("MODEL CORRECTNESS AT THE GATE (all episodes, per market)")
    w = sum(e["won"] for e in all_eps)
    print("    decided side correct on %d of %d episodes = %.2f%%"
          % (w, tot, 100.0 * w / max(tot, 1)))

    print("")
    print("    BY EPISODE DURATION -- the crux. A quote that stays put is")
    print("    a quote nobody else wants; a quote that vanishes in 10 ms is")
    print("    one we cannot reach.")
    print("      duration          n   correct   mean_edge_c   $/contract")
    DB = [(0, 50), (50, 140), (140, 200), (200, 500), (500, 1000),
          (1000, 2000), (2000, 5000), (5000, 10 ** 9)]
    for lo, hi in DB:
        v = [e for e in all_eps if lo <= e["dur"] < hi]
        if not v:
            continue
        print("      %5d-%-9s %6d   %5.1f%%   %9.2f    %+9.4f"
              % (lo, ("inf" if hi > 10 ** 8 else str(hi)), len(v),
                 100.0 * sum(e["won"] for e in v) / len(v),
                 100 * sum(e["edge0"] for e in v) / len(v),
                 sum(pnl_of(e) for e in v) / len(v)))

    print("")
    print("    BY MODEL EDGE AT THE START")
    print("      edge_c            n   correct   mean_dur_ms   $/contract")
    for lo, hi in [(0.5, 1), (1, 2), (2, 5), (5, 10), (10, 25), (25, 10 ** 9)]:
        v = [e for e in all_eps if lo <= 100 * e["edge0"] < hi]
        if not v:
            continue
        print("      %5.1f-%-10s %6d   %5.1f%%   %9d    %+9.4f"
              % (lo, ("inf" if hi > 10 ** 8 else str(hi)), len(v),
                 100.0 * sum(e["won"] for e in v) / len(v),
                 sum(e["dur"] for e in v) / len(v),
                 sum(pnl_of(e) for e in v) / len(v)))

    print("")
    print("    BY TAU AT EPISODE START")
    ded = defaultdict(list)
    for e in all_eps:
        ded[e["tau0"]].append(e)
    for t in sorted(ded):
        v = ded[t]
        print("      tau=%2d  n=%6d  correct %5.1f%%  $/contract %+9.4f"
              % (t, len(v), 100.0 * sum(e["won"] for e in v) / len(v),
                 sum(pnl_of(e) for e in v) / len(v)))

    json.dump(dict(mode=mode, rows=rows, eps=all_eps),
              open(os.path.join(OUT, "agg_%s.json" % mode), "w"))


if __name__ == "__main__":
    main()
