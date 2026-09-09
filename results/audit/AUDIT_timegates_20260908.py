#!/usr/bin/env python3
"""AUDIT_timegates_20260908.py -- unbiased review of pinrun's TIME and REPEAT gates.

Gates reviewed:  TAU_MIN / TAU_MAX, MAX_PER_CLOSE, IMPROVE_BY, and the
close_summary "same ticker" dedupe.

READ-ONLY. Places no order, touches no collector file, edits no live source.

SCORING RULE (from the brief, not re-derived here):
  There are ZERO flips in the eligible tau 3-30 sample, so realised P&L there
  is a monotone function of contracts bought and cannot rank two rules.
  Everything is therefore scored on EXPECTED value at the measured flip rate
  f = 0.90%, and stressed at the exact one-sided 95% Clopper-Pearson upper
  bound f = 2.31%.

  EV(price) = (1-f)*(1-p) - f*p - fee(p)
  Blended break-even flip rate for a set of buys at prices p_i:
      (1-f)(1-p) - f*p = (1-p) - f, so
      f* = mean(1-p) - mean(fee).
  Checked in selftest().

--selftest plants a known answer and requires a null world to return nothing.
"""
import json
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"C:\kals-repo\research")
from engine import var_factor, N_AVG                    # noqa: E402
from statistics import NormalDist                       # noqa: E402

ND = NormalDist()
ROWS = r"C:\kals-repo\results\pindata\rows.jsonl"

# live configuration, 2026-09-08 v9, pid 3997812
PIN = 0.98
TAU_MIN, TAU_MAX = 3, 30
EDGE_FLOOR = 0.003
EV_FLOOR = 0.003
PRICE_CEILING = 0.988
MAX_PER_CLOSE = 2
IMPROVE_BY = 0.005
MIN_LEVEL = 1.0
SIZE = 5.0
F_MEAS = 0.0090
F_UPPER = 0.0231


def billed_fee(p, n=1.0):
    return math.ceil(0.07 * p * (1 - p) * n * 10000.0) / 10000.0


def net_edge(pflip, price, size=SIZE):
    return (1.0 - pflip) - price - billed_fee(price, size) / float(size)


def ev(price, f=F_MEAS):
    return (1.0 - f) * (1.0 - price) - f * price - billed_fee(price, 1.0)


def breakeven_flip(prices):
    """f* such that summed EV over these buys is zero. One contract each."""
    if not prices:
        return None
    tot_win = sum(1.0 - p for p in prices)
    tot_fee = sum(billed_fee(p, 1.0) for p in prices)
    return (tot_win - tot_fee) / len(prices)


def pflip_of(row):
    """p(the favoured side loses) under the model, from the stored columns."""
    r = int(row["r"])
    if r <= 0:
        return 0.0
    sd = float(row["sig"]) * math.sqrt(var_factor(r, [1.0]))
    z = -(float(row["req"]) * r / 60.0)
    if sd <= 0:
        return 0.0 if z >= 0 else 1.0
    return ND.cdf(-abs(z / sd))


# ---------------------------------------------------------------------------
def eligible(row, tau_min, tau_max, size=SIZE, ceiling=PRICE_CEILING,
             edge_floor=EDGE_FLOOR, ev_floor=EV_FLOOR):
    """Every pinrun gate EXCEPT the per-close cap and the improve rule."""
    if not (tau_min <= row["tau"] <= tau_max):
        return None
    if row["size"] < max(MIN_LEVEL, size):
        return None
    pf = row.get("pf")
    if pf is None:
        pf = pflip_of(row)
    if pf > 1.0 - PIN:
        return None
    p = row["price"]
    if net_edge(pf, p, size) < edge_floor:
        return None
    if p > ceiling:
        return None
    if ev(p) < ev_floor:
        return None
    return pf


def simulate(rows, tau_min, tau_max, cap, improve, size=SIZE,
             ceiling=PRICE_CEILING, edge_floor=EDGE_FLOOR, ev_floor=EV_FLOOR):
    """Replay pinrun's loop. `fired` is keyed on CLOSE, exactly as live:
    the cap is shared across every coin settling at that quarter hour."""
    fired = {}
    buys = []
    for row in sorted(rows, key=lambda r: (r["sec"], r["tk"])):
        cs = row["close"]
        prev = fired.get(cs)
        if prev is not None and prev["n"] >= cap:
            continue
        pf = eligible(row, tau_min, tau_max, size, ceiling, edge_floor, ev_floor)
        if pf is None:
            continue
        p = row["price"]
        if prev is not None and p >= prev["best"] - improve:
            continue
        if prev is None:
            fired[cs] = {"n": 1, "best": p}
        else:
            prev["n"] += 1
            prev["best"] = min(prev["best"], p)
        buys.append(row)
    return {"buys": len(buys), "closes": len(fired), "rows": buys,
            "fired": fired}


def score(buys, size=SIZE):
    """Everything the brief asks for, per contract and per close."""
    if not buys:
        return None
    prices = [b["price"] for b in buys]
    flips = sum(1 for b in buys if b["flip"])
    fee = sum(billed_fee(b["price"], size) / size for b in buys)
    realised = sum(((1.0 - b["price"]) if not b["flip"] else -b["price"])
                   for b in buys) - fee
    ev_m = sum(ev(p, F_MEAS) for p in prices)
    ev_u = sum(ev(p, F_UPPER) for p in prices)
    closes = len(set(b["close"] for b in buys))
    be = breakeven_flip(prices)
    return {
        "buys": len(buys), "closes": closes,
        "mean_price": sum(prices) / len(prices),
        "flips": flips,
        "realised_c_per_contract": 100 * realised / len(buys),
        "realised_c_per_close": 100 * realised / closes,
        "ev_c_per_contract": 100 * ev_m / len(buys),
        "ev_c_per_close": 100 * ev_m / closes,
        "ev231_c_per_close": 100 * ev_u / closes,
        "be_flip": be,
        "headroom_vs_meas": be / F_MEAS,
        "headroom_vs_upper": be / F_UPPER,
    }


# ---------------------------------------------------------------------------
def selftest():
    print("SELF-TEST -- AUDIT_timegates")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    ck(abs(breakeven_flip([0.95]) - (0.05 - billed_fee(0.95))) < 1e-12,
       "break-even flip at 95c is (1-p) minus the fee")
    ck(abs(ev(1.0 - F_MEAS - billed_fee(1.0 - F_MEAS))) < 2e-4,
       "EV is ~zero at p = 1 - f - fee")
    b = breakeven_flip([0.99, 0.93])
    ck(0.03 < b < 0.045, "blended break-even of 99c and 93c is ~4%% (%.4f)" % b)

    # pflip_of: plant a world where the answer is known.
    sd1 = math.sqrt(var_factor(1, [1.0]))
    row = {"r": 1, "sig": 1.0, "req": -(2.0 * sd1) * 60.0 / 1.0}
    ck(abs(pflip_of(row) - ND.cdf(-2.0)) < 1e-9,
       "planted a 2-sigma moment; estimator returns %.5f (expected %.5f)"
       % (pflip_of(row), ND.cdf(-2.0)))
    # NULL WORLD
    row0 = {"r": 5, "sig": 1.0, "req": 0.0}
    ck(abs(pflip_of(row0) - 0.5) < 1e-12,
       "a moment on the strike is 50/50 -- nothing found where nothing is")
    ck(net_edge(0.5, 0.97) < 0,
       "and a 50/50 moment offered at 97c has negative edge")

    null = [{"tk": "A", "close": 100, "sec": 100 - t, "tau": t,
             "r": max(t - 1, 1), "sig": 1.0, "req": 0.0, "price": 0.97,
             "size": 500.0, "flip": False} for t in range(30, 2, -1)]
    res = simulate(null, 3, 30, 2, 0.005)
    ck(res["buys"] == 0, "null world -> no buys (%d)" % res["buys"])

    good = []
    for n in null:
        r_ = max(n["tau"] - 1, 1)
        req = -(6.0 * math.sqrt(var_factor(r_, [1.0]))) * 60.0 / r_
        g = dict(n)
        g["req"] = req
        g["price"] = 0.93
        good.append(g)
    res2 = simulate(good, 3, 30, 2, 0.005)
    ck(res2["buys"] == 1,
       "planted world fires, improve rule stops the 2nd buy at the same "
       "price (%d)" % res2["buys"])
    good2 = [dict(g) for g in good]
    for i, g in enumerate(good2):
        g["price"] = round(0.97 - 0.002 * i, 4)
    res3 = simulate(good2, 3, 30, 2, 0.005)
    ck(res3["buys"] == 2,
       "a steadily improving price fires exactly MAX_PER_CLOSE times (%d)"
       % res3["buys"])
    sc = score(good2[:2])
    ck(sc is not None and sc["flips"] == 0 and sc["ev_c_per_contract"] > 0,
       "score() runs and a cheap planted buy is positive EV")
    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


def load():
    rows = []
    with open(ROWS, encoding="utf-8") as fh:
        for line in fh:
            rows.append(json.loads(line))
    return rows


def hdr(s):
    print("\n" + "=" * 78 + "\n" + s + "\n" + "=" * 78)


def main():
    if "--selftest" in sys.argv:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")
    rows = load()
    print("\n  %d rows loaded" % len(rows))
    print("  tau range in file: %d .. %d"
          % (min(r["tau"] for r in rows), max(r["tau"] for r in rows)))
    print("  distinct closes:   %d" % len(set(r["close"] for r in rows)))
    print("  distinct markets:  %d" % len(set(r["tk"] for r in rows)))

    for r in rows:
        r["pf"] = pflip_of(r)

    # ---------------------------------------------------------------
    hdr("GATE 1a -- WHAT LIVES AT SMALL TAU (the TAU_MIN=3 question)")
    print("%4s %7s %3s %10s %6s %16s %7s %7s"
          % ("tau", "rows", "r", "model<=2%", "flips", "elig(all gates)",
             "closes", "eflips"))
    for t in range(2, 13):
        sub = [r for r in rows if r["tau"] == t]
        dec = [r for r in sub if r["pf"] <= 0.02]
        el = [r for r in sub if eligible(r, 2, 60) is not None]
        print("%4d %7d %3d %10d %6d %16d %7d %7d"
              % (t, len(sub), t - 1, len(dec),
                 sum(1 for r in dec if r["flip"]), len(el),
                 len(set(r["close"] for r in el)),
                 sum(1 for r in el if r["flip"])))

    hdr("GATE 1b -- TAU_MAX. Calibration by horizon, model-confident moments")
    print("%8s %9s %7s %6s %9s %8s %7s"
          % ("bucket", "moments", "closes", "flips", "realised", "model",
             "ratio"))
    for lo, hi in ((3, 10), (11, 20), (21, 30), (31, 45), (46, 60),
                   (61, 90), (91, 200)):
        sub = [r for r in rows if lo <= r["tau"] <= hi and r["pf"] <= 0.02]
        if not sub:
            continue
        fl = sum(1 for r in sub if r["flip"])
        mod = sum(r["pf"] for r in sub) / len(sub)
        real = fl / len(sub)
        ratio = (real / mod) if mod > 0 else float("nan")
        print("%3d-%-4d %9d %7d %6d %8.3f%% %7.3f%% %6.1fx"
              % (lo, hi, len(sub), len(set(r["close"] for r in sub)), fl,
                 100 * real, 100 * mod, ratio))

    hdr("GATE 1c -- SWEEP TAU_MAX, full live rule (cap 2, improve 0.5c)")
    print("%8s %6s %7s %7s %6s %17s %17s %8s %6s"
          % ("tau_max", "buys", "closes", "meanP", "flips",
             "EV c/close@0.90%", "EV c/close@2.31%", "BE flip", "head"))
    for tm in (20, 25, 30, 35, 45, 60):
        s = simulate(rows, TAU_MIN, tm, MAX_PER_CLOSE, IMPROVE_BY)
        sc = score(s["rows"])
        if sc is None:
            continue
        print("%8d %6d %7d %6.2fc %6d %16.3fc %16.3fc %7.3f%% %5.2fx"
              % (tm, sc["buys"], sc["closes"], 100 * sc["mean_price"],
                 sc["flips"], sc["ev_c_per_close"], sc["ev231_c_per_close"],
                 100 * sc["be_flip"], sc["headroom_vs_upper"]))

    print("\n  SAME SWEEP, each tau band scored at ITS OWN measured flip rate.")
    print("  A naive sweep credits tau 31-60 with a 0.90% rate it does not have.")
    band_f = {}
    for lo, hi in ((3, 10), (11, 20), (21, 30), (31, 45), (46, 60)):
        sub = [r for r in rows if lo <= r["tau"] <= hi and r["pf"] <= 0.02]
        fl = sum(1 for r in sub if r["flip"])
        band_f[(lo, hi)] = ((fl / len(sub)) if fl
                            else (1 - 0.05 ** (1.0 / len(sub))))
        print("    tau %2d-%-2d: n=%6d flips=%3d -> f used %.3f%%%s"
              % (lo, hi, len(sub), fl, 100 * band_f[(lo, hi)],
                 "  (observed)" if fl else "  (95% bound, 0 observed)"))

    def f_for_tau(t):
        for (lo, hi), f in band_f.items():
            if lo <= t <= hi:
                return f
        return 0.05

    print("\n%8s %6s %7s %29s %17s"
          % ("tau_max", "buys", "closes", "EV c/close, band-calibrated",
             "vs pooled 0.90%"))
    for tm in (20, 25, 30, 35, 45, 60):
        s = simulate(rows, TAU_MIN, tm, MAX_PER_CLOSE, IMPROVE_BY)
        bs = s["rows"]
        if not bs:
            continue
        cl = len(set(b["close"] for b in bs))
        band_ev = sum((1 - f_for_tau(b["tau"])) * (1 - b["price"])
                      - f_for_tau(b["tau"]) * b["price"]
                      - billed_fee(b["price"], 1.0) for b in bs)
        pooled = sum(ev(b["price"], F_MEAS) for b in bs)
        print("%8d %6d %7d %28.3fc %16.3fc"
              % (tm, len(bs), cl, 100 * band_ev / cl, 100 * pooled / cl))

    hdr("GATE 1d -- TAU_MIN sweep, full live rule (tau_max 30)")
    print("%8s %6s %7s %7s %6s %17s %8s"
          % ("tau_min", "buys", "closes", "meanP", "flips",
             "EV c/close@0.90%", "BE flip"))
    for tn in (2, 3, 4, 5, 6, 8, 10):
        s = simulate(rows, tn, TAU_MAX, MAX_PER_CLOSE, IMPROVE_BY)
        sc = score(s["rows"])
        if sc is None:
            continue
        print("%8d %6d %7d %6.2fc %6d %16.3fc %7.3f%%"
              % (tn, sc["buys"], sc["closes"], 100 * sc["mean_price"],
                 sc["flips"], sc["ev_c_per_close"], 100 * sc["be_flip"]))
    s2 = simulate(rows, 2, TAU_MAX, MAX_PER_CLOSE, IMPROVE_BY)
    s3 = simulate(rows, 3, TAU_MAX, MAX_PER_CLOSE, IMPROVE_BY)
    k3 = set((b["tk"], b["sec"]) for b in s3["rows"])
    extra = [b for b in s2["rows"] if (b["tk"], b["sec"]) not in k3]
    mp = (100 * sum(b["price"] for b in extra) / len(extra)) if extra else 0.0
    print("\n  what tau 2 alone adds: %d extra buys over %d closes; "
          "%d flips; mean price %.2fc"
          % (len(extra), len(set(b["close"] for b in extra)),
             sum(1 for b in extra if b["flip"]), mp))

    # ---------------------------------------------------------------
    hdr("GATE 2 -- MAX_PER_CLOSE sweep (tau 3-30, improve 0.5c)")
    print("%4s %6s %7s %8s %7s %6s %17s %10s %8s %8s %13s"
          % ("cap", "buys", "closes", "b/close", "meanP", "flips",
             "EV c/close@0.90%", "EV@2.31%", "BE flip", "maxExp$",
             "abort -21 ok"))
    for cap in (1, 2, 3, 4, 6):
        s = simulate(rows, TAU_MIN, TAU_MAX, cap, IMPROVE_BY)
        sc = score(s["rows"])
        if sc is None:
            continue
        per = defaultdict(list)
        for b in s["rows"]:
            per[b["close"]].append(b["price"])
        worst = max(sum(v) for v in per.values()) * SIZE
        cap_worst = 1.00 * SIZE * cap
        lo_a, hi_a = -4.0 * cap_worst, -1.5 * cap_worst
        ok = "yes" if lo_a <= -21.00 <= hi_a else ("NO %.0f..%.0f"
                                                   % (lo_a, hi_a))
        print("%4d %6d %7d %8.2f %6.2fc %6d %16.3fc %9.3fc %7.3f%% %8.2f %13s"
              % (cap, sc["buys"], sc["closes"], sc["buys"] / sc["closes"],
                 100 * sc["mean_price"], sc["flips"], sc["ev_c_per_close"],
                 sc["ev231_c_per_close"], 100 * sc["be_flip"], worst, ok))

    print("\n  distribution of buys per fired close, at each cap:")
    for cap in (1, 2, 3, 4, 6):
        s = simulate(rows, TAU_MIN, TAU_MAX, cap, IMPROVE_BY)
        d = defaultdict(int)
        for cs, v in s["fired"].items():
            d[v["n"]] += 1
        print("    cap %d: " % cap
              + "  ".join("%d buys x%d" % (k, d[k]) for k in sorted(d)))

    print("\n  how often does a follow-on buy land on the SAME ticker?")
    s = simulate(rows, TAU_MIN, TAU_MAX, 6, IMPROVE_BY)
    per = defaultdict(list)
    for b in s["rows"]:
        per[b["close"]].append(b)
    same = tot = 0
    for cs, v in per.items():
        for i in range(1, len(v)):
            tot += 1
            if v[i]["tk"] == v[0]["tk"]:
                same += 1
    print("    %d of %d follow-on buys are the same ticker as the first "
          "(%.1f%%)" % (same, tot, 100 * same / max(tot, 1)))

    # ---------------------------------------------------------------
    hdr("GATE 3 -- IMPROVE_BY sweep (tau 3-30, cap 2)")
    print("%8s %6s %7s %7s %14s %6s %17s %10s %8s %8s"
          % ("improve", "buys", "closes", "meanP", "2nd-buy meanP", "flips",
             "EV c/close@0.90%", "EV@2.31%", "BE flip", "maxExp$"))
    for imp in (0.0, 0.001, 0.002, 0.005, 0.01, 0.02):
        s = simulate(rows, TAU_MIN, TAU_MAX, MAX_PER_CLOSE, imp)
        sc = score(s["rows"])
        if sc is None:
            continue
        per = defaultdict(list)
        for b in s["rows"]:
            per[b["close"]].append(b)
        seconds = [v[i]["price"] for v in per.values()
                   for i in range(1, len(v))]
        worst = max(sum(x["price"] for x in v) for v in per.values()) * SIZE
        m2 = (100 * sum(seconds) / len(seconds)) if seconds else float("nan")
        print("%8.3f %6d %7d %6.2fc %13.2fc %6d %16.3fc %9.3fc %7.3f%% %8.2f"
              % (imp, sc["buys"], sc["closes"], 100 * sc["mean_price"], m2,
                 sc["flips"], sc["ev_c_per_close"], sc["ev231_c_per_close"],
                 100 * sc["be_flip"], worst))

    print("\n  DIRECTION TEST: is a follow-on buy dearer or cheaper than the "
          "first?")
    for imp in (0.0, 0.002, 0.005, 0.01):
        s = simulate(rows, TAU_MIN, TAU_MAX, MAX_PER_CLOSE, imp)
        per = defaultdict(list)
        for b in s["rows"]:
            per[b["close"]].append(b)
        worse = better = same_ = 0
        for v in per.values():
            for i in range(1, len(v)):
                if v[i]["price"] > v[0]["price"]:
                    worse += 1
                elif v[i]["price"] < v[0]["price"]:
                    better += 1
                else:
                    same_ += 1
        print("    improve %.3f: 2nd buy cheaper %d, same %d, DEARER %d"
              % (imp, better, same_, worse))

    # ---------------------------------------------------------------
    hdr("JOINT -- cap x improve, EV c/close at the measured 0.90%")
    caps = (1, 2, 3, 4)
    imps = (0.0, 0.002, 0.005, 0.01)
    print("        " + "".join("%12s" % ("imp=%.3f" % i) for i in imps))
    for cap in caps:
        line = "  cap %d" % cap
        for imp in imps:
            s = simulate(rows, TAU_MIN, TAU_MAX, cap, imp)
            sc = score(s["rows"])
            line += "%11.2fc" % (sc["ev_c_per_close"] if sc else 0)
        print(line)
    print("\n  same grid, stressed at the 2.31% upper bound:")
    print("        " + "".join("%12s" % ("imp=%.3f" % i) for i in imps))
    for cap in caps:
        line = "  cap %d" % cap
        for imp in imps:
            s = simulate(rows, TAU_MIN, TAU_MAX, cap, imp)
            sc = score(s["rows"])
            line += "%11.2fc" % (sc["ev231_c_per_close"] if sc else 0)
        print(line)


if __name__ == "__main__":
    main()
