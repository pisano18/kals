#!/usr/bin/env python3
"""Driver: every table for the price/size gate review. READ ONLY.

Imports AUDIT_pricesize_gates_20260908 (self-tested) and prints the sweeps.
"""
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import AUDIT_pricesize_gates_20260908 as A                 # noqa: E402

G = A


def hdr(s):
    print("\n" + "=" * 78)
    print(s)
    print("=" * 78)


def main():
    if not A.selftest():
        raise SystemExit("self-test failed")
    rows = A.load()
    closes = {r["close"] for r in rows}
    hdr("SAMPLE")
    print(f"rows                {len(rows):,}")
    print(f"distinct closes     {len(closes):,}")
    print(f"distinct markets    {len({r['tk'] for r in rows}):,}")
    print(f"rows with no model  {sum(1 for r in rows if r['_conf'] is None):,}")
    elig = [r for r in rows if A.TAU_MIN <= r["tau"] <= A.TAU_MAX]
    print(f"tau 3-30 rows       {len(elig):,} over "
          f"{len({r['close'] for r in elig}):,} closes")
    print(f"tau 3-30 flips      {sum(1 for r in elig if r['flip'])}")
    print(f"all-tau flips       {sum(1 for r in rows if r['flip'])} over "
          f"{len({r['close'] for r in rows if r['flip']})} closes")

    # ---------------------------------------------------------------- PIN
    hdr("GATE 1 -- PIN sweep (everything else at live v9 values)")
    print(f"{'PIN':>7} {'closes':>7} {'buys':>6} {'avgP':>7} "
          f"{'EV c/ct':>8} {'EV c/close':>11} {'EVstr c/ct':>11} "
          f"{'BE flip':>8} {'head':>6} {'real c/ct':>10} {'flips':>6}")
    base = None
    for pin in (0.90, 0.95, 0.97, 0.98, 0.99, 0.995, 0.999):
        o = A.walk(rows, pin=pin)
        s = A.score(o["buys"])
        if not s["buys"]:
            print(f"{pin:>7} {'0':>7}")
            continue
        if pin == 0.98:
            base = s
        print(f"{pin:>7} {s['closes']:>7} {s['buys']:>6} "
              f"{100*s['avg_price']:>6.2f}c {s['ev_c_per_contract']:>7.3f} "
              f"{s['ev_c_per_close']:>10.2f} "
              f"{s['ev_c_stress_per_contract']:>10.3f} "
              f"{100*s['blended_breakeven_flip']:>7.2f}% "
              f"{s['headroom_vs_ub']:>5.2f}x {s['realised_c_per_contract']:>9.3f} "
              f"{s['flips']:>6}")

    # what the PIN gate actually refuses: first-binding counts
    hdr("GATE 1 -- what PIN refuses that nothing else would")
    for pin in (0.95, 0.97, 0.98, 0.99, 0.995):
        on = A.walk(rows, pin=pin)
        # rows that pass everything EXCEPT pin, at this pin
        loose = A.walk(rows, pin=0.5)
        s_on, s_loose = A.score(on["buys"]), A.score(loose["buys"])
        print(f"PIN {pin}: {s_on['buys']:>4} buys of the {s_loose['buys']:>4} "
              f"that a PIN of 0.50 would take "
              f"({100.0*s_on['buys']/max(1,s_loose['buys']):.1f}%)")

    # --- calibration: what IS "98% sure"? measured where flips exist ---
    hdr("GATE 1 -- CALIBRATION: what the model's confidence is really worth")
    print("Empirical flip rate by MODEL-IMPLIED risk (1-conf), all tau 2-200.")
    print("Clustered n reported as CLOSES as well as moments.\n")
    bands = [(0.0, 1e-6), (1e-6, 1e-4), (1e-4, 1e-3), (1e-3, 5e-3),
             (5e-3, 0.02), (0.02, 0.05), (0.05, 0.20), (0.20, 1.01)]
    print(f"{'model risk 1-conf':>22} {'moments':>9} {'closes':>7} "
          f"{'flips':>6} {'flip closes':>12} {'emp rate':>9} {'ratio':>8}")
    for lo, hi in bands:
        sel = [r for r in rows
               if r["_conf"] is not None and lo <= (1 - r["_conf"]) < hi]
        if not sel:
            continue
        fl = [r for r in sel if r["flip"]]
        mid = sum(1 - r["_conf"] for r in sel) / len(sel)
        emp = len(fl) / len(sel)
        ratio = (emp / mid) if mid > 0 else float("inf")
        print(f"{lo:>10.0e}-{hi:<10.0e} {len(sel):>9,} "
              f"{len({r['close'] for r in sel}):>7} {len(fl):>6} "
              f"{len({r['close'] for r in fl}):>12} {100*emp:>8.3f}% "
              f"{ratio:>7.1f}x")
    print("\nSame, restricted to tau 3-30 (the live window):")
    print(f"{'model risk 1-conf':>22} {'moments':>9} {'closes':>7} "
          f"{'flips':>6} {'emp rate':>9}")
    for lo, hi in bands:
        sel = [r for r in elig
               if r["_conf"] is not None and lo <= (1 - r["_conf"]) < hi]
        if not sel:
            continue
        fl = [r for r in sel if r["flip"]]
        print(f"{lo:>10.0e}-{hi:<10.0e} {len(sel):>9,} "
              f"{len({r['close'] for r in sel}):>7} {len(fl):>6} "
              f"{100*len(fl)/len(sel):>8.3f}%")

    print("\nFlip rate ABOVE vs BELOW the 0.98 line, by tau band:")
    print(f"{'tau band':>10} {'conf>=0.98 n':>13} {'flips':>6} {'rate':>8}   "
          f"{'0.95<=conf<0.98 n':>18} {'flips':>6} {'rate':>8}")
    for lo, hi in ((3, 30), (31, 45), (46, 60), (61, 120), (121, 200)):
        a1 = [r for r in rows if lo <= r["tau"] <= hi
              and r["_conf"] is not None and r["_conf"] >= 0.98]
        a2 = [r for r in rows if lo <= r["tau"] <= hi
              and r["_conf"] is not None and 0.95 <= r["_conf"] < 0.98]
        f1 = sum(1 for r in a1 if r["flip"])
        f2 = sum(1 for r in a2 if r["flip"])
        print(f"{lo:>4}-{hi:<5} {len(a1):>13,} {f1:>6} "
              f"{100*f1/max(1,len(a1)):>7.3f}%   {len(a2):>18,} {f2:>6} "
              f"{100*f2/max(1,len(a2)):>7.3f}%")

    # ------------------------------------------------- EDGE / EV redundancy
    hdr("GATE 2 -- EDGE_FLOOR vs EV_FLOOR: does each bind on its own?")
    on = A.walk(rows)
    no_edge = A.walk(rows, use_edge=False)
    no_ev = A.walk(rows, use_ev=False)
    neither = A.walk(rows, use_edge=False, use_ev=False)
    for tag, o in (("both (LIVE)", on), ("EDGE removed", no_edge),
                   ("EV removed", no_ev), ("both removed", neither)):
        s = A.score(o["buys"])
        print(f"{tag:<14} buys {s['buys']:>4}  closes {s['closes']:>4}  "
              f"avgP {100*s.get('avg_price',0):.2f}c  "
              f"EV/ct {s.get('ev_c_per_contract',0):+.3f}c  "
              f"EV total ${s.get('ev_total_dollars',0):+.2f}  "
              f"BE flip {100*s.get('blended_breakeven_flip',0):.2f}%")
    print("\nFirst-binding refusal counts under the LIVE rule "
          "(pinrun's own order):")
    for k, v in sorted(on["ref"].items(), key=lambda kv: -kv[1]):
        print(f"   {k:<16} {v:>10,}")

    # a moment-level census over the rows that reach the two floors
    hdr("GATE 2 -- moment-level census: which floor binds where")
    reach = []
    for r in rows:
        if not (A.TAU_MIN <= r["tau"] <= A.TAU_MAX):
            continue
        c = r["_conf"]
        if c is None or c < A.PIN or r["size"] < max(A.MIN_LEVEL, A.SIZE):
            continue
        e = A.net_edge(c, r["price"])
        ev = A.expected_value(r["price"])
        reach.append((r, e, ev))
    n = len(reach)
    both_ok = sum(1 for _, e, ev in reach if e >= A.EDGE_FLOOR and ev >= A.EV_FLOOR)
    edge_only = sum(1 for _, e, ev in reach if e < A.EDGE_FLOOR and ev >= A.EV_FLOOR)
    ev_only = sum(1 for _, e, ev in reach if e >= A.EDGE_FLOOR and ev < A.EV_FLOOR)
    both_bind = sum(1 for _, e, ev in reach if e < A.EDGE_FLOOR and ev < A.EV_FLOOR)
    print(f"moments reaching the two floors (tau3-30, conf>=0.98, size>=5): "
          f"{n:,} over {len({r['close'] for r,_,_ in reach}):,} closes")
    print(f"   pass both                       {both_ok:>8,}  "
          f"{100*both_ok/max(1,n):.1f}%")
    print(f"   ONLY EDGE refuses (EV would pass){edge_only:>8,}  "
          f"{100*edge_only/max(1,n):.1f}%   <- EDGE is not redundant")
    print(f"   ONLY EV refuses (EDGE would pass){ev_only:>8,}  "
          f"{100*ev_only/max(1,n):.1f}%   <- EV is not redundant")
    print(f"   both refuse                     {both_bind:>8,}  "
          f"{100*both_bind/max(1,n):.1f}%")
    ex_e = [r for r, e, ev in reach if e < A.EDGE_FLOOR and ev >= A.EV_FLOOR]
    ex_v = [r for r, e, ev in reach if e >= A.EDGE_FLOOR and ev < A.EV_FLOOR]
    if ex_e:
        r = min(ex_e, key=lambda x: x["price"])
        print(f"\n   EDGE-only example: {r['tk'][:26]} p={100*r['price']:.1f}c "
              f"conf={r['_conf']:.5f} edge={100*A.net_edge(r['_conf'],r['price']):+.3f}c "
              f"EV={100*A.expected_value(r['price']):+.3f}c")
    if ex_v:
        r = max(ex_v, key=lambda x: x["_conf"])
        print(f"   EV-only   example: {r['tk'][:26]} p={100*r['price']:.1f}c "
              f"conf={r['_conf']:.5f} edge={100*A.net_edge(r['_conf'],r['price']):+.3f}c "
              f"EV={100*A.expected_value(r['price']):+.3f}c")

    # floor sweeps
    hdr("GATE 2 -- sweeping each floor separately")
    print("EDGE_FLOOR sweep (EV_FLOOR held at 0.003):")
    print(f"{'edge c':>8} {'closes':>7} {'buys':>6} {'avgP':>7} {'EV c/ct':>8} "
          f"{'EV c/close':>11} {'BE flip':>8} {'real c/ct':>10}")
    for ef in (0.000, 0.001, 0.002, 0.003, 0.005, 0.010, 0.020):
        s = A.score(A.walk(rows, edge_floor=ef)["buys"])
        if not s["buys"]:
            print(f"{100*ef:>7.1f}c {'0':>7}")
            continue
        print(f"{100*ef:>7.1f}c {s['closes']:>7} {s['buys']:>6} "
              f"{100*s['avg_price']:>6.2f}c {s['ev_c_per_contract']:>7.3f} "
              f"{s['ev_c_per_close']:>10.2f} "
              f"{100*s['blended_breakeven_flip']:>7.2f}% "
              f"{s['realised_c_per_contract']:>9.3f}")
    print("\nEV_FLOOR sweep (EDGE_FLOOR held at 0.003):")
    print(f"{'ev c':>8} {'closes':>7} {'buys':>6} {'avgP':>7} {'EV c/ct':>8} "
          f"{'EV c/close':>11} {'BE flip':>8} {'real c/ct':>10}")
    for vf in (-0.010, 0.000, 0.001, 0.003, 0.005, 0.010, 0.020):
        s = A.score(A.walk(rows, ev_floor=vf)["buys"])
        if not s["buys"]:
            print(f"{100*vf:>7.1f}c {'0':>7}")
            continue
        print(f"{100*vf:>7.1f}c {s['closes']:>7} {s['buys']:>6} "
              f"{100*s['avg_price']:>6.2f}c {s['ev_c_per_contract']:>7.3f} "
              f"{s['ev_c_per_close']:>10.2f} "
              f"{100*s['blended_breakeven_flip']:>7.2f}% "
              f"{s['realised_c_per_contract']:>9.3f}")

    # --------------------------------------------------------- PRICE CEILING
    hdr("GATE 3 -- PRICE_CEILING: is it ever the binding rule?")
    # algebra first
    print("Algebra: EV(p) >= EV_FLOOR  <=>  (1-p) >= EV_FLOOR + flip + fee(p)")
    for p in (0.9860, 0.9870, 0.9871, 0.9872, 0.9875, 0.9880, 0.9885, 0.9890):
        ev = A.expected_value(p)
        print(f"   p={100*p:7.2f}c  fee={10000*A.billed_fee(p):5.1f}bp  "
              f"EV={100*ev:+7.4f}c  "
              f"{'PASS' if ev >= A.EV_FLOOR else 'FAIL'} EV_FLOOR   "
              f"{'PASS' if p <= A.PRICE_CEILING else 'FAIL'} PRICE_CEILING")
    n_between = sum(1 for r in rows
                    if A.PRICE_CEILING >= r["price"] > 0.987
                    and A.expected_value(r["price"]) >= A.EV_FLOOR)
    print(f"\nrows in the band where the ceiling is looser than the EV gate "
          f"(price in (0.987, 0.988] AND EV>=floor): {n_between}")
    print("prices actually seen in (0.9870, 0.9880]:",
          sorted({r["price"] for r in rows
                  if 0.9870 < r["price"] <= 0.9880}))
    for tag, o in (("ceiling ON (LIVE)", A.walk(rows)),
                   ("ceiling REMOVED", A.walk(rows, use_ceiling=False))):
        s = A.score(o["buys"])
        print(f"{tag:<20} buys {s['buys']:>4} closes {s['closes']:>4} "
              f"avgP {100*s['avg_price']:.2f}c EV/ct {s['ev_c_per_contract']:+.3f}c "
              f"ceiling-refusals {o['ref'].get('ceiling',0)} "
              f"ev-refusals {o['ref'].get('ev',0)}")
    print("\nWhat if MEASURED_FLIP moves and the constant does not?")
    print(f"{'flip':>7} {'EV-implied ceiling':>20} {'PRICE_CEILING':>15} "
          f"{'which binds':>14}")
    for f in (0.0000, 0.0045, 0.0090, 0.0180, 0.0231, 0.0300):
        # highest tick price p (0.1c grid) with EV(p, f) >= EV_FLOOR
        best = None
        p = 0.5
        while p <= 0.9995:
            if (1 - p) - f - A.billed_fee(p) >= A.EV_FLOOR - 1e-12:
                best = p
            p = round(p + 0.001, 4)
        which = ("EV" if (best is not None and best <= A.PRICE_CEILING)
                 else "PRICE_CEILING")
        print(f"{100*f:>6.2f}% {100*best:>19.1f}c {100*A.PRICE_CEILING:>14.1f}c "
              f"{which:>14}")

    # ------------------------------------------------------------- SIZE gate
    hdr("GATE 4 -- SIZE: opportunities retained as we scale")
    print("Backtest (rows.jsonl), full live rule, SIZE varied:")
    print(f"{'SIZE':>6} {'closes':>7} {'buys':>6} {'contracts':>10} "
          f"{'EV $ total':>11} {'EV c/ct':>8} {'size-refusals':>14} "
          f"{'closes kept':>12}")
    b5 = None
    for sz in (1, 3, 5, 8, 10, 15, 25, 50, 75, 100, 125, 200):
        o = A.walk(rows, size_req=float(sz))
        s = A.score(o["buys"], size_req=float(sz))
        if sz == 5:
            b5 = s
        if not s["buys"]:
            print(f"{sz:>6} {0:>7}")
            continue
        print(f"{sz:>6} {s['closes']:>7} {s['buys']:>6} "
              f"{sz*s['buys']:>10,} {s['ev_total_dollars']:>10.2f} "
              f"{s['ev_c_per_contract']:>7.3f} "
              f"{o['ref'].get('size',0):>14,} "
              f"{100.0*s['closes']/max(1,b5['closes']) if b5 else 0:>11.1f}%")

    print("\nThe same, as the operator asked it -- moments that pass every "
          "other gate,\nthen how many survive the size test at each SIZE:")
    pool = []
    for r in rows:
        if not (A.TAU_MIN <= r["tau"] <= A.TAU_MAX):
            continue
        c = r["_conf"]
        if c is None or c < A.PIN:
            continue
        if A.net_edge(c, r["price"]) < A.EDGE_FLOOR:
            continue
        if r["price"] > A.PRICE_CEILING:
            continue
        if A.expected_value(r["price"]) < A.EV_FLOOR:
            continue
        pool.append(r)
    pc = len({r["close"] for r in pool})
    print(f"pool: {len(pool):,} qualifying moments over {pc} closes "
          f"(no size test applied)")
    print(f"{'SIZE':>6} {'moments kept':>13} {'% of moments':>13} "
          f"{'closes kept':>12} {'% of closes':>12}")
    for sz in (1, 3, 5, 8, 10, 15, 25, 50, 75, 100, 125, 200, 400):
        keep = [r for r in pool if r["size"] >= max(A.MIN_LEVEL, sz)]
        print(f"{sz:>6} {len(keep):>13,} {100.0*len(keep)/max(1,len(pool)):>12.1f}% "
              f"{len({r['close'] for r in keep}):>12} "
              f"{100.0*len({r['close'] for r in keep})/max(1,pc):>11.1f}%")
    if pool:
        ss = sorted(r["size"] for r in pool)
        def q(p):
            return ss[min(len(ss) - 1, int(p * len(ss)))]
        print(f"\nresting size at the touch on qualifying moments: "
              f"min {ss[0]:.2f}  p10 {q(0.10):.1f}  p25 {q(0.25):.1f}  "
              f"median {q(0.50):.1f}  p75 {q(0.75):.1f}  p90 {q(0.90):.1f}  "
              f"max {ss[-1]:.1f}")

    # MIN_LEVEL: does it ever bind?
    hdr("GATE 4b -- MIN_LEVEL=1.0: does it ever bind at SIZE 5?")
    print("MIN_LEVEL only enters as max(MIN_LEVEL, SIZE); at SIZE>=1 it is "
          "arithmetically inert.")
    print(f"rows.jsonl cannot see sub-1.0 levels at all: pindata drops "
          f"size<1 at build time (pindata.py line 'size < 1').")
    print(f"min size in rows.jsonl: {min(r['size'] for r in rows):.3f}")

    # ------------------------------------------------------ LIVE log evidence
    hdr("LIVE LOGS -- 17 signals, 32 close summaries")
    import glob
    sig, cs = [], []
    for f in sorted(glob.glob(r"C:\kals-repo\results\pinrun-live-*.jsonl")):
        for line in open(f, encoding="utf-8"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("kind") == "signal":
                sig.append(d)
            elif d.get("kind") == "close_summary":
                cs.append(d)
    print(f"{len(sig)} signals, {len(cs)} close summaries")
    print(f"\n{'gate':<28}{'signals refused if applied':>28}")
    for tag, fn in (
            ("PIN 0.95", lambda d: not (max(d["fair"], 1 - d["fair"]) >= 0.95)),
            ("PIN 0.97", lambda d: not (max(d["fair"], 1 - d["fair"]) >= 0.97)),
            ("PIN 0.98 (LIVE)", lambda d: not (max(d["fair"], 1 - d["fair"]) >= 0.98)),
            ("PIN 0.99", lambda d: not (max(d["fair"], 1 - d["fair"]) >= 0.99)),
            ("PIN 0.995", lambda d: not (max(d["fair"], 1 - d["fair"]) >= 0.995)),
            ("EDGE_FLOOR 0.3c (LIVE)", lambda d: d["edge_c"] < 0.3),
            ("EDGE_FLOOR 0.5c", lambda d: d["edge_c"] < 0.5),
            ("EV_FLOOR 0.3c (LIVE)", lambda d: A.expected_value(d["price"]) < 0.003),
            ("PRICE_CEILING 0.988 (LIVE)", lambda d: d["price"] > 0.988),
            ("PRICE_CEILING 0.96", lambda d: d["price"] > 0.96),
            ("size>=5 (LIVE)", lambda d: d["size"] < 5),
            ("size>=10", lambda d: d["size"] < 10),
            ("size>=15", lambda d: d["size"] < 15),
            ("size>=25", lambda d: d["size"] < 25),
            ("size>=50", lambda d: d["size"] < 50),
            ("size>=125", lambda d: d["size"] < 125),
            ("size>=200", lambda d: d["size"] < 200)):
        k = sum(1 for d in sig if fn(d))
        print(f"{tag:<28}{k:>13} of {len(sig)}   "
              f"({100.0*k/max(1,len(sig)):.0f}%)")
    print("\nLive signal prices, sorted:",
          [round(100 * d["price"], 1) for d in sorted(sig, key=lambda x: x["price"])])
    print("Live signal sizes,  sorted:",
          [round(d["size"], 1) for d in sorted(sig, key=lambda x: x["size"])])
    print("Live signal model confidences (on the side bought), sorted:")
    print("  ", [round(max(d["fair"], 1 - d["fair"]), 5)
                 for d in sorted(sig, key=lambda x: max(x["fair"], 1 - x["fair"]))])
    ev = [A.expected_value(d["price"]) for d in sig]
    be = [A.breakeven_flip(d["price"]) for d in sig]
    print(f"\nLIVE blended: avg price {100*sum(d['price'] for d in sig)/len(sig):.2f}c, "
          f"EV/contract {100*sum(ev)/len(ev):+.3f}c, "
          f"blended break-even flip {100*sum(be)/len(be):.2f}% "
          f"(headroom {sum(be)/len(be)/A.FLIP_UB:.2f}x vs the 2.31% bound)")

    # close-summary evidence on best-available prices
    hdr("LIVE close summaries -- what the ceiling and size gates refused")
    tot_over = sum(d.get("over_ceiling", 0) for d in cs)
    tot_negev = sum(d.get("neg_ev", 0) for d in cs)
    tot_dust = sum(d.get("dust", 0) for d in cs)
    print(f"over_ceiling refusals logged  {tot_over}   "
          f"(only 2 closes carry the counter; it was added 2026-09-08 17:00Z)")
    print(f"neg_ev refusals logged        {tot_negev}")
    print(f"dust (size<max(1,SIZE))       {tot_dust}")
    print(f"closes with a tradeable moment {sum(1 for d in cs if d.get('tradeable'))}"
          f" of {len(cs)}")
    print(f"closes that fired              {sum(1 for d in cs if d.get('fired'))}")
    print(f"closes with best price > 98.8c {sum(1 for d in cs if (d.get('best_price') or 0) > 0.988)}")
    print("\nCloses whose BEST look was refused, and by which gate:")
    for d in sorted(cs, key=lambda x: x["close"]):
        if d.get("fired") or d.get("best_price") is None:
            continue
        p, e = d["best_price"], d["best_edge_c"] / 100.0
        why = []
        if e < A.EDGE_FLOOR:
            why.append(f"edge {100*e:.2f}c<0.3c")
        if p > A.PRICE_CEILING:
            why.append(f"price {100*p:.1f}c>98.8c")
        if A.expected_value(p) < A.EV_FLOOR:
            why.append(f"EV {100*A.expected_value(p):+.2f}c<0.3c")
        if d.get("best_size", 1e9) < 5:
            why.append(f"size {d['best_size']}<5")
        print(f"   {d['t']}  {d.get('best_ticker','')[:24]:<24} "
              f"p={100*p:6.2f}c edge={d['best_edge_c']:+6.3f}c "
              f"size={d.get('best_size')}  -> {', '.join(why) or 'UNEXPLAINED'}")


if __name__ == "__main__":
    main()
