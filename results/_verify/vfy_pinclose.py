#!/usr/bin/env python3
"""vfy_pinclose.py -- ADVERSARIAL verification of research/pinclose.py.

Independent re-derivation, not a re-run. Checks, in order:
  1  LOOKAHEAD: recompute every entry-time feature (bps, cr300, model p) with
     the index array TRUNCATED to the decision second -- every later print
     deleted -- and require bit-identical values.
  2  TABLE 4 rebuilt from scratch (gate refusal counts / loser shares), plus
     the comparison pinclose did NOT print: refused-vs-KEPT loser rate, and
     what each gate does to the worst CLOSE.
  3  HEDGE-SIDE DEPTH, which pinclose reported as NOT MEASURED. When the model
     has SWITCHED sides, rows.jsonl's own price/size ARE the ask and the
     size on the side we would hedge INTO. That is measurable and is measured.
  4  trigger_tau's early return: how many entries have a blip-then-persistent
     crossing, i.e. how many the confirm rules silently never hedge.
  5  LEAD TIME to the CLOSE, per loser, for the recommended p>=50% trigger.
  6  JACKKNIFE: drop each loser in turn; does the p>=50% net survive?
  7  WINS TO RECOVER recomputed by hand at the real per-ORDER fee.

SELF-TEST plants a known answer for every estimator and requires nothing on a
null world. main() refuses real data unless it passes.
"""
import array
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


# --------------------------------------------------------------------------
def truncated_copy(base, arr, sec):
    """A copy of the index array with EVERY print after sec set to NaN."""
    out = array.array("d", arr)
    cut = sec - base + 1
    nan = float("nan")
    if cut < len(out):
        out[max(0, cut):] = array.array("d", [nan] * (len(out) - max(0, cut)))
    return out


def truncated_window(base, arr, sec, back=1000):
    """(base2, arr2) covering ONLY [sec-back, sec]. Everything after the
    decision second is physically absent, so any forward peek must fail."""
    i1 = sec - base
    i0 = max(0, i1 - back)
    if i1 < 0 or i1 >= len(arr):
        return None, None
    return base + i0, array.array("d", arr[i0:i1 + 1])


def feats(base, arr, row):
    """(bps, cr300, pf) at the row's own decision second, from arr alone."""
    K = PC.k_from_row(row)
    d = abs(row["spot"] - K)
    bps = 1e4 * d / row["spot"]
    rg = PC.realised_range(base, arr, row["sec"], 300)
    cr = (d / rg) if (rg and rg > 0) else None
    sg = PC.sigma_at(base, arr, row["sec"], 300)
    pf = PC.model_pflip(row["req"], sg, row["r"])
    return bps, cr, pf


def gate_split(ents, key, thresh):
    """refused/kept loser counts AND worst close on each side."""
    ref = [e for e in ents if e.get(key) is not None and e[key] < thresh]
    kep = [e for e in ents if not (e.get(key) is not None and e[key] < thresh)]

    def worst_close(rs):
        by = defaultdict(float)
        for e in rs:
            by[e["close"]] += PH.unhedged_pnl(e["price"], not e["flip"])
        return min(by.values()) if by else 0.0

    return {
        "ref_n": len(ref), "ref_l": sum(1 for e in ref if e["flip"]),
        "kep_n": len(kep), "kep_l": sum(1 for e in kep if e["flip"]),
        "kep_worst_close": worst_close(kep),
        "kep_pnl": sum(PH.unhedged_pnl(e["price"], not e["flip"])
                       for e in kep),
    }


def blip_count(paths, confirm):
    """Entries whose FIRST crossing fails confirmation but which DO have a
    later crossing that would pass it. trigger_tau returns None for these."""
    n = 0
    for p in paths:
        if PC.trigger_tau(p, confirm) is not None:
            continue
        for i in range(len(p)):
            if p[i][2] <= 0:
                nxt = p[i:i + confirm + 1]
                if len(nxt) >= confirm + 1 and all(q[2] <= 0 for q in nxt):
                    n += 1
                    break
    return n


def order_fee(p, n):
    return math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000


# --------------------------------------------------------------------------
def selftest():
    print("SELF-TEST -- vfy_pinclose")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # --- truncation must destroy the future and keep the past -------------
    a = array.array("d", [1.0, 2.0, 3.0, 4.0, 5.0])
    t = truncated_copy(0, a, 2)
    ck(list(t[:3]) == [1.0, 2.0, 3.0] and all(x != x for x in t[3:]),
       "truncation keeps every print up to and including the decision second "
       "and NaNs every later one")
    ck(PC.realised_range(0, a, 2, 3) == PC.realised_range(0, t, 2, 3) == 2.0,
       "a backward-looking range is unchanged by truncation (2.0)")
    fwd = array.array("d", [1.0, 1.0, 1.0, 9.0, 9.0])
    ck(PC.realised_range(0, fwd, 4, 5) == 8.0
       and PC.realised_range(0, truncated_copy(0, fwd, 2), 4, 5) is None,
       "PLANT: a range that DOES peek forward returns 8.0 on the full tape "
       "and None once the future is deleted -- so this test can fail")
    b2, w2 = truncated_window(0, a, 2, back=2)
    ck(b2 == 0 and list(w2) == [1.0, 2.0, 3.0]
       and PC.realised_range(b2, w2, 2, 3) == 2.0,
       "the windowed truncation is the same tape up to the decision second "
       "and physically has no later prints at all")
    b3, w3 = truncated_window(0, fwd, 2, back=4)
    ck(PC.realised_range(b3, w3, 4, 5) is None,
       "PLANT: the forward-peeking range is unmeasurable on the window, so "
       "the windowed test detects a peek exactly as the NaN test does")

    # --- gate split -------------------------------------------------------
    e = [{"price": .95, "flip": False, "k": 0.1, "close": 1},
         {"price": .95, "flip": True, "k": 0.1, "close": 2},
         {"price": .95, "flip": False, "k": 0.9, "close": 3},
         {"price": .95, "flip": True, "k": 0.9, "close": 4}]
    g = gate_split(e, "k", 0.5)
    ck(g["ref_n"] == 2 and g["ref_l"] == 1 and g["kep_l"] == 1,
       f"PLANT null gate: refuses 2 (1 loser), keeps 2 (1 loser) -- equal "
       f"rates ({g['ref_l']}/{g['ref_n']} vs {g['kep_l']}/{g['kep_n']})")
    e2 = [{"price": .95, "flip": True, "k": 0.1, "close": 1},
          {"price": .95, "flip": True, "k": 0.1, "close": 2},
          {"price": .95, "flip": False, "k": 0.9, "close": 3}]
    g2 = gate_split(e2, "k", 0.5)
    ck(g2["ref_l"] == 2 and g2["kep_l"] == 0 and g2["kep_worst_close"] > 0,
       "PLANT real gate: refuses both losers, and the kept worst close is a "
       "WIN -- the estimator can detect a gate that works")

    # --- blip counter -----------------------------------------------------
    blip = [(20, 1., 0.001, 0.), (19, 1., -0.001, 0.), (18, 1., 0.002, 0.),
            (17, 1., -0.003, 0.), (16, 1., -0.004, 0.), (15, 1., -0.005, 0.)]
    stay = [(20, 1., -0.001, 0.), (19, 1., -0.002, 0.), (18, 1., -0.003, 0.)]
    ck(PC.trigger_tau(blip, 1) is None,
       "PLANT: pinclose's trigger_tau returns None on a blip-then-persistent "
       "path even though a real crossing follows")
    ck(blip_count([blip], 1) == 1 and blip_count([stay], 1) == 0,
       f"the counter finds exactly that one path ({blip_count([blip], 1)}) "
       f"and NULL: zero on a clean crossing ({blip_count([stay], 1)})")

    # --- fee, per ORDER not per contract ----------------------------------
    ck(abs(order_fee(0.16, 12.37) - 0.1164) < 1e-9,
       f"the fee reproduces the operator's real charge exactly: 12.37 at 16c "
       f"= ${order_fee(0.16, 12.37):.6f}")
    tot = (0.962 * 20 + 0.956 * 20 + 0.73 * 19
           + order_fee(0.962, 20) + order_fee(0.956, 20) + order_fee(0.73, 19))
    ck(abs(tot - 52.60) < 0.005,
       f"PLANT tonight's three real fills: stake + per-ORDER fees = "
       f"${tot:.4f}, which is the reported -$52.60 to the cent")
    per_c = 59 * (0.88525 + PH.fee(0.88525))
    ck(abs(per_c - 52.60) > 0.03,
       f"and the per-CONTRACT fee model pinclose uses gives ${per_c:.4f} -- "
       f"6c different, so the two are distinguishable and the check is real")

    # --- jackknife --------------------------------------------------------
    vals = [10.0, 10.0, 10.0, 100.0]
    jk = [sum(vals) - v for v in vals]
    ck(min(jk) == 30.0 and max(jk) == 120.0,
       "jackknife arithmetic: dropping the 100 leaves 30, dropping a 10 "
       "leaves 120 -- concentration is visible")

    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


# --------------------------------------------------------------------------
def main():
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")
    print("\n" + "=" * 76)
    print("  ADVERSARIAL VERIFICATION OF pinclose.py")
    print("=" * 76)

    rows = []
    with open(ROWS, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                rows.append(json.loads(ln))
    print(f"  rows.jsonl: {len(rows):,} rows, "
          f"{len({(r['tk'], r['close']) for r in rows}):,} markets, "
          f"{len({r['close'] for r in rows})} closes")

    print("  loading index tape ...", flush=True)
    idx = PC.load_index(PC.index_files(), verbose=False)
    print(f"  {len(idx)} indices loaded")

    for r in rows:
        iid = PC.SERIES_TO_INDEX.get(r["sr"])
        if iid in idx:
            b, ar = idx[iid]
            PC.attach_cushion(r, b, ar)
        else:
            r["cr300"] = None
            r["bps"] = None
        r["pf"] = PC.model_pflip(r["req"], r.get("sig"), r["r"])

    # ---------------- 1. LOOKAHEAD -------------------------------------
    print("\n" + "-" * 76)
    print("  1. LOOKAHEAD -- later index prints deleted, features recomputed")
    print("-" * 76)
    rnd = random.Random(5)
    samp = rnd.sample(rows, 1200)
    nbad = nchk = 0
    worst = 0.0
    for r in samp:
        iid = PC.SERIES_TO_INDEX.get(r["sr"])
        if iid not in idx:
            continue
        b, ar = idx[iid]
        b2, tr = truncated_window(b, ar, r["sec"])
        if tr is None:
            continue
        f_full = feats(b, ar, r)
        f_cut = feats(b2, tr, r)
        nchk += 1
        for x, y in zip(f_full, f_cut):
            if (x is None) != (y is None):
                nbad += 1
                break
            if x is not None and abs(x - y) > 1e-12:
                worst = max(worst, abs(x - y))
                nbad += 1
                break
    print(f"  {nchk:,} sampled decision-seconds recomputed on a truncated tape")
    print(f"  features that CHANGED: {nbad}   (largest change {worst:.3e})")
    print("  VERDICT: " + ("NO LOOKAHEAD in bps, cr300 or model p"
                           if nbad == 0 else "*** LOOKAHEAD PRESENT ***"))

    # ---------------- build the two entry sets --------------------------
    bym = defaultdict(list)
    for r in rows:
        bym[(r["tk"], r["close"])].append(r)
    for k in bym:
        bym[k].sort(key=lambda x: -x["tau"])

    def entries(tl, th):
        out = []
        for k, seq in bym.items():
            for x in seq:
                if not (tl <= x["tau"] <= th):
                    continue
                if x["pf"] is None or x["pf"] > PC.PIN_P:
                    continue
                if x["price"] > PC.CEILING or PH.ev(x["price"]) < PC.EV_FLOOR:
                    continue
                out.append(x)
                break
        return out

    live = entries(3, 30)
    wide = entries(3, 200)
    print(f"\n  rebuilt independently: LIVE {len(live)} positions / "
          f"{len({e['close'] for e in live})} closes / "
          f"{sum(1 for e in live if e['flip'])} losers")
    print(f"                         WIDE {len(wide)} positions / "
          f"{len({e['close'] for e in wide})} closes / "
          f"{sum(1 for e in wide if e['flip'])} losers")

    # ---------------- 2. TABLE 4 ----------------------------------------
    print("\n" + "-" * 76)
    print("  2. TABLE 4 REBUILT -- and the comparison pinclose did not print")
    print("-" * 76)
    base_l = sum(1 for e in wide if e["flip"])
    base_pnl = sum(PH.unhedged_pnl(e["price"], not e["flip"]) for e in wide)
    bwc = defaultdict(float)
    for e in wide:
        bwc[e["close"]] += PH.unhedged_pnl(e["price"], not e["flip"])
    print(f"  base: {len(wide)} positions, {base_l} losers "
          f"({100*base_l/len(wide):.2f}%), total {100*base_pnl:+.1f}c, "
          f"worst close {100*min(bwc.values()):+.1f}c")
    print(f"  {'gate':>18}{'refused':>9}{'ref L':>7}{'ref rate':>10}"
          f"{'kept L':>8}{'kept rate':>11}{'kept total':>12}"
          f"{'kept worst close':>18}")
    for key, grid in (("cr300", (0.02, 0.05, 0.08, 0.12, 0.20, 0.35)),
                      ("bps", (1.0, 2.0, 4.0, 8.0, 15.0))):
        for t in grid:
            g = gate_split(wide, key, t)
            rr = ((100.0 * g["ref_l"] / g["ref_n"]) if g["ref_n"]
                  else float("nan"))
            kr = ((100.0 * g["kep_l"] / g["kep_n"]) if g["kep_n"]
                  else float("nan"))
            print(f"  {key + ' < ' + str(t):>18}{g['ref_n']:>9}{g['ref_l']:>7}"
                  f"{rr:>9.2f}%{g['kep_l']:>8}{kr:>10.2f}%"
                  f"{100*g['kep_pnl']:>11.1f}c"
                  f"{100*g['kep_worst_close']:>17.1f}c")

    # ---------------- 3. HEDGE-SIDE DEPTH -------------------------------
    print("\n" + "-" * 76)
    print("  3. HEDGE-SIDE DEPTH -- reported by pinclose as NOT MEASURED")
    print("-" * 76)
    print("  When the model has SWITCHED sides, rows.jsonl's own price/size")
    print("  ARE the ask and the size on the side we hedge INTO.")

    def trig_row(e, thresh):
        for x in bym[(e["tk"], e["close"])]:
            if x["tau"] >= e["tau"]:
                continue
            pf = x["pf"]
            if pf is None:
                continue
            if x["side_yes"] != e["side_yes"]:
                pf = 1.0 - pf
            if pf >= thresh:
                return x
        return None

    for lab, ents in (("WIDE losers", [e for e in wide if e["flip"]]),
                      ("LIVE false alarms", live)):
        got = []
        for e in ents:
            x = trig_row(e, 0.50)
            if x is None:
                continue
            switched = (x["side_yes"] != e["side_yes"])
            px = PH.hedge_price(x, e["side_yes"])
            sz = x["size"] if switched else None
            got.append((e, x, switched, px, sz))
        print(f"\n  {lab}: p>=50% fired on {len(got)} of {len(ents)}")
        if not got:
            continue
        print(f"  {'ticker':>26}{'entry tau':>10}{'trig tau':>9}"
              f"{'switched':>10}{'hedge px':>10}{'size at that px':>17}")
        for e, x, sw, px, sz in sorted(got, key=lambda t: t[1]["tau"],
                                       reverse=True)[:25]:
            print(f"  {e['tk'][-26:]:>26}{e['tau']:>10}{x['tau']:>9}"
                  f"{('yes' if sw else 'NO'):>10}{100*px:>9.1f}c"
                  f"{(('%.0f' % sz) if sz is not None else 'not in row'):>17}")
        sizes = [t[4] for t in got if t[4] is not None]
        if sizes:
            sizes.sort()
            print(f"  hedge-side touch size, n={len(sizes)} of {len(got)}: "
                  f"min {sizes[0]:.0f}, median {sizes[len(sizes)//2]:.0f}, "
                  f"max {sizes[-1]:.0f}")
            for want in (20, 59):
                ok = sum(1 for s in sizes if s >= want)
                print(f"    deep enough for {want:>2} contracts: {ok} of "
                      f"{len(sizes)} ({100.0*ok/len(sizes):.0f}%)")

    # ---------------- 4. trigger_tau blip bug ---------------------------
    print("\n" + "-" * 76)
    print("  4. trigger_tau EARLY RETURN -- confirm rules that never fire")
    print("-" * 76)
    for lab, ents in (("LIVE", live), ("WIDE", wide)):
        paths = [PC.walk_entry(idx, e) for e in ents]
        paths = [p for p in paths if p]
        for c in (1, 2, 3):
            n = blip_count(paths, c)
            fires = sum(1 for p in paths
                        if PC.trigger_tau(p, c) is not None)
            print(f"  {lab} confirm {c}s: fires on {fires} paths; {n} MORE "
                  f"paths have a blip then a genuine confirmed crossing that "
                  f"the early return silently drops")

    # ---------------- 5. LEAD TIME to the close -------------------------
    print("\n" + "-" * 76)
    print("  5. LEAD TIME of the recommended p>=50% trigger, TO THE CLOSE")
    print("-" * 76)
    lt = []
    for e in [x for x in wide if x["flip"]]:
        x = trig_row(e, 0.50)
        if x is not None:
            lt.append((e["tk"], e["tau"], x["tau"]))
    lt.sort(key=lambda t: t[2])
    print(f"  {'ticker':>26}{'entry tau':>10}{'trigger tau':>13}")
    for tk, et, tt in lt:
        print(f"  {tk[-26:]:>26}{et:>10}{tt:>13}")
    if lt:
        v = sorted(t[2] for t in lt)
        print(f"  trigger tau (= seconds left when we would act): min {v[0]}, "
              f"median {v[len(v)//2]}, max {v[-1]}")

    # ---------------- 6. JACKKNIFE --------------------------------------
    print("\n" + "-" * 76)
    print("  6. JACKKNIFE -- drop each loser in turn, does p>=50% survive?")
    print("-" * 76)

    def net_of(ents, thresh):
        tot = b = 0.0
        for e in ents:
            u = PH.unhedged_pnl(e["price"], not e["flip"])
            b += u
            x = trig_row(e, thresh)
            v = u
            if x is not None:
                q = PH.hedge_price(x, e["side_yes"])
                if 0.0 < q < 1.0:
                    v = PH.hedged_pnl(e["price"], q)
            tot += v
        return tot - b

    full = net_of(wide, 0.50)
    print(f"  full sample net: {100*full:+.1f}c on {len(wide)} positions")
    losers = [e for e in wide if e["flip"]]
    jk = []
    for drop in losers:
        sub = [e for e in wide if e is not drop]
        jk.append((net_of(sub, 0.50), drop["tk"]))
    jk.sort()
    for v, tk in jk:
        print(f"    drop {tk[-26:]:>26}: net {100*v:+.1f}c")
    print(f"  jackknife range {100*jk[0][0]:+.1f}c to {100*jk[-1][0]:+.1f}c; "
          f"{sum(1 for v, _ in jk if v <= 0)} of {len(jk)} single drops turn "
          f"the net non-positive")

    # ---------------- 7. WINS TO RECOVER --------------------------------
    print("\n" + "-" * 76)
    print("  7. WINS TO RECOVER, recomputed at the real per-ORDER fee")
    print("-" * 76)
    for lab, ents in (("LIVE", live), ("WIDE", wide)):
        w = [PH.unhedged_pnl(e["price"], True) for e in ents if not e["flip"]]
        mw = sum(w) / len(w)
        ls = [PH.unhedged_pnl(e["price"], False) for e in ents if e["flip"]]
        print(f"  {lab}: mean win {100*mw:.2f}c/contract "
              f"(median {100*sorted(w)[len(w)//2]:.2f}c)")
        if ls:
            print(f"        mean loss {100*sum(ls)/len(ls):.2f}c "
                  f"= {abs(sum(ls)/len(ls))/mw:.1f} wins; "
                  f"worst {100*min(ls):.2f}c = {abs(min(ls))/mw:.1f} wins")
    stake = 0.962 * 20 + 0.956 * 20 + 0.73 * 19
    fees = (order_fee(0.962, 20) + order_fee(0.956, 20)
            + order_fee(0.73, 19))
    print(f"  tonight, per ORDER: stake ${stake:.2f} + fees ${fees:.4f} "
          f"= ${stake+fees:.4f} lost")
    for lab, ask, sz in (("tau 17", 0.46, 60), ("tau 16", 0.48, 60),
                         ("tau 14", 0.84, 58)):
        n = min(59, sz)
        hedged = n * (1.0 - 0.88525 - ask) - order_fee(ask, n)
        unh = -(59 - n) * 0.88525
        tot = hedged + unh - fees
        print(f"  hedge {n} of 59 at {lab} ({100*ask:.0f}c): net ${tot:.2f} "
              f"vs ${-(stake+fees):.2f} unhedged; "
              f"extra capital needed ${n*ask:.2f}")
    print("\n  DONE.")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(0 if selftest() else 1)
    main()
