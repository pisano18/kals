#!/usr/bin/env python3
"""vfy_pinclose2.py -- second adversarial pass on research/pinclose.py.

The headline rests on ONE number: the within-z pooled cushion effect,
+0.092 pp, 95% CI [-0.051, +0.255]. This file attacks that number where it is
weakest and then prices the answer.

  A  POWER OF THE POOLING. pinclose weights each z band by
     n_lo*n_hi/(n_lo+n_hi). Two bands (z 6-10 and z 10+) contain ZERO flipped
     markets on BOTH sides, contribute exactly zero to the numerator, and
     carry ~61% of the weight. That is unbiased but it throws power away. Re-
     estimate on the bands that actually contain events and see whether the
     effect escapes zero there.
  B  PRICE THE UPPER BOUND. Even taken at the top of its CI, what is the
     cushion worth in cents per contract, against the measured cost of the
     cheapest gate that would exploit it?
  C  DEPTH-CAPPED HEDGE. Pass 1 measured the hedge-side touch size (median 60,
     6 of the 12 losers under 60). Re-score the recommended p>=50% rule with
     the fill capped at that size and at the live size of 20.
  D  TRIGGER-TO-FILL LATENCY. pinclose's model triggers fire on the per-second
     INDEX walk and then take the first BOOK row at tau <= trigger. How many
     seconds pass, and how much does the price move in between?

SELF-TEST plants a known answer for each and returns nothing on a null world.
"""
import json
import math
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, r"C:\kals-repo\research")
import pinclose as PC                                        # noqa: E402
import pinhedge as PH                                        # noqa: E402

ROWS = r"C:\kals-repo\results\pindata\rows.jsonl"
FULLTAPE = r"C:\kals\fulltape\markets.json"


# --------------------------------------------------------------------------
def band_of(z, bands):
    for i, (a, b) in enumerate(bands):
        if a <= z < b:
            return i
    return None


def collapse(rows, key, lo_max, hi_min, bands):
    """{close: [(band, side, flipped)]} with one entry per market/band/side."""
    per = {}
    for r in rows:
        v = r.get(key)
        z = r.get("z")
        if v is None or z is None:
            continue
        bd = band_of(z, bands)
        if bd is None:
            continue
        side = 0 if v < lo_max else (1 if v >= hi_min else None)
        if side is None:
            continue
        per.setdefault((r["tk"], r["close"], bd, side),
                       (r["close"], bd, side, bool(r["flip"])))
    bycl = defaultdict(list)
    for (_, cl, bd, side), (_, _, _, fl) in per.items():
        bycl[cl].append((bd, side, fl))
    return bycl


def tabulate(items, nb):
    t = [[0, 0, 0, 0] for _ in range(nb)]
    for bd, side, fl in items:
        if side == 0:
            t[bd][0] += 1
            t[bd][1] += 1 if fl else 0
        else:
            t[bd][2] += 1
            t[bd][3] += 1 if fl else 0
    return t


def pooled(t, keep=None):
    """Sample-size-weighted mean of (rate_lo - rate_hi). keep = band indices."""
    num = den = 0.0
    for i, (nl, kl, nh, kh) in enumerate(t):
        if keep is not None and i not in keep:
            continue
        if nl == 0 or nh == 0:
            continue
        w = (nl * nh) / float(nl + nh)
        num += w * (kl / nl - kh / nh)
        den += w
    return (num / den) if den else None


def boot_ci(bycl, nb, keep, nboot=1500, seed=17):
    rnd = random.Random(seed)
    cls = list(bycl)
    d = []
    for _ in range(nboot):
        items = []
        for _ in range(len(cls)):
            items.extend(bycl[cls[rnd.randrange(len(cls))]])
        v = pooled(tabulate(items, nb), keep)
        if v is not None:
            d.append(v)
    d.sort()
    return d[int(0.025 * len(d))], d[int(0.975 * len(d))], len(cls)


# --------------------------------------------------------------------------
def selftest():
    print("SELF-TEST -- vfy_pinclose2")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    B = ((2.0, 3.0), (3.0, 4.0), (4.0, 1e9))

    # PLANT: a real +5 pp effect that lives ONLY in band 0, plus two dead
    # bands with huge n and zero events. Full pooling must dilute it; the
    # restricted pooling must recover it.
    rows = []
    for i in range(200):
        rows.append({"tk": f"a{i}", "close": i % 40, "z": 2.5, "c": 0.01,
                     "flip": i < 12})                      # 6.0%
    for i in range(200):
        rows.append({"tk": f"b{i}", "close": i % 40, "z": 2.5, "c": 0.9,
                     "flip": i < 2})                       # 1.0%
    for i in range(4000):
        rows.append({"tk": f"c{i}", "close": i % 40, "z": 5.0, "c": 0.01,
                     "flip": False})
    for i in range(4000):
        rows.append({"tk": f"d{i}", "close": i % 40, "z": 5.0, "c": 0.9,
                     "flip": False})
    by = collapse(rows, "c", 0.1, 0.5, B)
    allit = [x for v in by.values() for x in v]
    T = tabulate(allit, 3)
    full = pooled(T)
    rest = pooled(T, keep={0})
    ck(abs(rest - 0.05) < 1e-9,
       f"PLANT +5.0 pp inside the only band with events: restricted pooling "
       f"returns {100*rest:+.3f} pp")
    ck(full is not None and full < 0.5 * rest,
       f"and the full pooling DILUTES it to {100*full:+.3f} pp because two "
       f"dead bands carry most of the weight -- which is the criticism")
    lo, hi, ncl = boot_ci(by, 3, {0}, nboot=300, seed=3)
    ck(lo > 0,
       f"the restricted bootstrap CI [{100*lo:+.3f}, {100*hi:+.3f}] pp "
       f"excludes zero on a planted effect")

    # NULL: identical rates everywhere. Both poolings must be zero.
    rows2 = []
    for i in range(400):
        rows2.append({"tk": f"e{i}", "close": i % 40, "z": 2.5, "c": 0.01,
                      "flip": i < 8})
    for i in range(400):
        rows2.append({"tk": f"f{i}", "close": i % 40, "z": 2.5, "c": 0.9,
                      "flip": i < 8})
    by2 = collapse(rows2, "c", 0.1, 0.5, B)
    T2 = tabulate([x for v in by2.values() for x in v], 3)
    ck(abs(pooled(T2)) < 1e-12 and abs(pooled(T2, keep={0})) < 1e-12,
       "NULL world, identical rates in both strata: both poolings return "
       "exactly zero, not a fabricated effect")
    lo2, hi2, _ = boot_ci(by2, 3, {0}, nboot=300, seed=4)
    ck(lo2 <= 0 <= hi2,
       f"and the NULL bootstrap CI [{100*lo2:+.3f}, {100*hi2:+.3f}] pp "
       f"contains zero")

    # --- depth cap arithmetic -------------------------------------------
    full20 = PH.hedged_pnl(0.95, 0.50, 20)
    unh20 = PH.unhedged_pnl(0.95, False, 20)
    ck(abs(cap_pnl(0.95, 0.50, 20, 20) - full20) < 1e-9,
       f"PLANT: a hedge with enough depth is exactly the full hedged P&L "
       f"({100*cap_pnl(0.95, 0.50, 20, 20):.2f}c vs {100*full20:.2f}c)")
    part = cap_pnl(0.95, 0.50, 20, 5)
    ck(unh20 < part < full20,
       f"PLANT partial fill (5 of 20): {100*part:.1f}c sits strictly between "
       f"unhedged {100*unh20:.1f}c and fully hedged {100*full20:.1f}c")
    ck(abs(cap_pnl(0.95, 0.50, 20, 0) - unh20) < 1e-9,
       f"NULL: zero depth leaves the position exactly unhedged "
       f"({100*cap_pnl(0.95, 0.50, 20, 0):.2f}c vs {100*unh20:.2f}c)")
    ck(abs(PH.hedged_pnl(0.95, 0.50, 20) - 20 * PH.hedged_pnl(0.95, 0.50))
       > 1e-9,
       "and the per-ORDER fee ceiling means n x the per-contract number is "
       "NOT the n-contract number -- which is why this fixture had to be "
       "rewritten after it failed")

    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


def cap_pnl(entry, hedge, n, depth):
    """P&L on n contracts when only `depth` of them can be hedged.

    The ENTRY fee is charged once on the whole n (one order), the hedge fee
    once on the h that fill. Splitting the entry fee across two legs would
    double-count the per-order ceiling.
    """
    h = min(n, max(0.0, depth))
    u = n - h
    return (h * (1.0 - entry - hedge) - u * entry
            - PH.fee(entry, n) - (PH.fee(hedge, h) if h > 0 else 0.0))


# --------------------------------------------------------------------------
def main():
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")
    print("\n" + "=" * 76)
    print("  PASS 2 -- POWER OF THE CONTROL, AND WHAT IT IS WORTH")
    print("=" * 76)

    print("  loading index tape ...", flush=True)
    idx = PC.load_index(PC.index_files(), verbose=False)
    mk_all = json.load(open(FULLTAPE, encoding="utf-8"))
    markets = [r for v in mk_all.values() for r in v
               if r["series"] in PC.SERIES_TO_INDEX]
    print(f"  {len(markets):,} settled markets; building the exogenous grid ...",
          flush=True)
    ip = PC.build_index_pop(idx, markets, (5, 10, 15, 20, 25, 30, 40, 50, 60),
                            verbose=False)
    ipc = [r for r in ip if r["pf"] <= PC.PIN_P]
    print(f"  {len(ip):,} rows -> {len(ipc):,} model-confident, "
          f"{len({(r['tk'], r['close']) for r in ipc}):,} markets, "
          f"{len({r['close'] for r in ipc})} closes")

    B = ((2.0, 3.0), (3.0, 4.0), (4.0, 6.0), (6.0, 10.0), (10.0, 1e9))
    print("\n" + "-" * 76)
    print("  A. POWER OF THE POOLING -- weights, and the bands that carry them")
    print("-" * 76)
    for key, lo_max, hi_min in (("bps", 5.0, 10.0), ("cr300", 0.10, 0.20)):
        by = collapse(ipc, key, lo_max, hi_min, B)
        T = tabulate([x for v in by.values() for x in v], len(B))
        wts = []
        for nl, kl, nh, kh in T:
            wts.append((nl * nh) / float(nl + nh) if nl and nh else 0.0)
        tw = sum(wts)
        print(f"\n  {key}: low < {lo_max}, high >= {hi_min}")
        print(f"  {'z band':>12}{'lo n':>8}{'lo k':>6}{'hi n':>8}{'hi k':>6}"
              f"{'weight':>10}{'% of weight':>13}{'diff pp':>10}")
        live_bands = set()
        for i, (nl, kl, nh, kh) in enumerate(T):
            if nl == 0 or nh == 0:
                continue
            d = 100.0 * (kl / nl - kh / nh)
            if kl + kh > 0:
                live_bands.add(i)
            lab = f"{B[i][0]:g}-{B[i][1]:g}" if B[i][1] < 1e8 \
                else f"{B[i][0]:g}+"
            print(f"  {lab:>12}{nl:>8,}{kl:>6}{nh:>8,}{kh:>6}"
                  f"{wts[i]:>10.0f}{100*wts[i]/tw:>12.1f}%{d:>10.3f}")
        dead_w = sum(w for i, w in enumerate(wts) if i not in live_bands)
        print(f"  bands with ZERO flipped markets on both sides carry "
              f"{100*dead_w/tw:.1f}% of the weight and contribute 0.000 pp")
        full = pooled(T)
        rest = pooled(T, keep=live_bands)
        lo1, hi1, ncl = boot_ci(by, len(B), None)
        lo2, hi2, _ = boot_ci(by, len(B), live_bands)
        print(f"  ALL bands      : {100*full:+.3f} pp  95% CI "
              f"[{100*lo1:+.3f}, {100*hi1:+.3f}] pp on {ncl} closes"
              + ("  EXCLUDES ZERO" if (lo1 > 0 or hi1 < 0) else "  spans 0"))
        print(f"  bands with events only ({sorted(live_bands)}): "
              f"{100*rest:+.3f} pp  95% CI [{100*lo2:+.3f}, {100*hi2:+.3f}] pp"
              + ("  EXCLUDES ZERO" if (lo2 > 0 or hi2 < 0) else "  spans 0"))

        # ---- B. price the upper bound -------------------------------
        print("\n  B. WHAT IT IS WORTH. A flip swings the outcome by exactly")
        print("     $1.00 per contract, so an extra flip rate of d costs 100*d")
        print("     cents of EV. Mean win in the live window is 5.08c.")
        for nm, v in (("point (all bands)", full), ("upper 95% (all)", hi1),
                      ("point (live bands)", rest),
                      ("upper 95% (live bands)", hi2)):
            print(f"    {nm:>24}: {100*v:+.3f} pp  ->  {100*v:+.3f}c per "
                  f"contract  = {100*v/5.08:+.1%} of one mean win")

    # ---------------- C and D need the book population -----------------
    rows = []
    with open(ROWS, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                rows.append(json.loads(ln))
    for r in rows:
        iid = PC.SERIES_TO_INDEX.get(r["sr"])
        if iid in idx:
            b, ar = idx[iid]
            PC.attach_cushion(r, b, ar)
        r["pf"] = PC.model_pflip(r["req"], r.get("sig"), r["r"])
    bym = defaultdict(list)
    for r in rows:
        bym[(r["tk"], r["close"])].append(r)
    for k in bym:
        bym[k].sort(key=lambda x: -x["tau"])
    wide = []
    for k, seq in bym.items():
        for x in seq:
            if not (3 <= x["tau"] <= 200):
                continue
            if x["pf"] is None or x["pf"] > PC.PIN_P:
                continue
            if x["price"] > PC.CEILING or PH.ev(x["price"]) < PC.EV_FLOOR:
                continue
            wide.append(x)
            break

    print("\n" + "-" * 76)
    print("  C. DEPTH-CAPPED HEDGE at the MEASURED hedge-side touch size")
    print("-" * 76)

    def walk_trigger(e, thresh):
        """pinclose's own rule: fire on the per-second INDEX walk."""
        for tau, spot, sc, pf in PC.walk_entry(idx, e):
            if pf is not None and pf >= thresh:
                return tau
        return None

    def book_row_at(e, trig):
        cand = [x for x in bym[(e["tk"], e["close"])] if x["tau"] <= trig]
        cand.sort(key=lambda x: -x["tau"])
        for x in cand:
            q = PH.hedge_price(x, e["side_yes"])
            if 0.0 < q < 1.0:
                return x, q
        return None, None

    for size in (20, 59):
        tot_u = tot_f = tot_c = 0.0
        lag = []
        for e in wide:
            u = PH.unhedged_pnl(e["price"], not e["flip"], size)
            tot_u += u
            t = walk_trigger(e, 0.50)
            if t is None:
                tot_f += u
                tot_c += u
                continue
            x, q = book_row_at(e, t)
            if x is None:
                tot_f += u
                tot_c += u
                continue
            lag.append(t - x["tau"])
            tot_f += PH.hedged_pnl(e["price"], q, size)
            dep = x["size"] if x["side_yes"] != e["side_yes"] else float("inf")
            tot_c += cap_pnl(e["price"], q, size, dep)
        print(f"  size {size:>2}: unhedged {100*tot_u:>9.1f}c | "
              f"hedged, UNLIMITED depth {100*tot_f:>9.1f}c "
              f"(net {100*(tot_f-tot_u):+.1f}c) | "
              f"hedged, MEASURED depth {100*tot_c:>9.1f}c "
              f"(net {100*(tot_c-tot_u):+.1f}c)")
    if lag:
        lag.sort()
        print(f"\n  D. TRIGGER-TO-FILL LAG: the index walk fires at tau T, the "
              f"first usable book row is {lag[0]}-{lag[-1]} s later "
              f"(median {lag[len(lag)//2]} s, n={len(lag)})")
        print(f"     fires where the book row is >= 3 s later: "
              f"{sum(1 for v in lag if v >= 3)} of {len(lag)}")
    print("\n  DONE.")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(0 if selftest() else 1)
    main()
