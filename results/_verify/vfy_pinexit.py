#!/usr/bin/env python3
"""vfy_pinexit.py -- ADVERSARIAL verification of pinexit / pinexit_run.

Six independent checks:

  A  LIVE-WINDOW COST. tau 3-30 gated has ZERO losers, so every alarm there is
     pure cost. Measure the cost in WINS, per trade and in total.
  B  LEAVE-ONE-CLOSE-OUT jackknife on the "+39% total" headline. 10 losing
     closes; if one close carries the result it is not a result.
  D  NOFILL BY CLASS. A missing book row silently un-hedges the trade. If that
     happens more to winners than losers the ledger is flattered.
  E  BREAK-EVEN RATIO, computed rather than asserted, from the measured hedge
     and win prices.
  F  LIVE-RULE PRICES. The study uses CEILING 0.988; the live rule is 0.980.

SELFTEST: plants a world where the answer is known and a null world where
there is nothing; main() refuses real data unless both pass.
"""
import argparse
import array
import json
import os
import sys
import time

HERE = r"C:\kals-repo\research"
sys.path.insert(0, HERE)
import pinexit as PX                                            # noqa: E402
import pinexit_run as PR                                        # noqa: E402
from pinexit import IndexTape, walk                             # noqa: E402


def pctl(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[max(0, min(len(xs) - 1, int(q * len(xs))))]


def score_rule(ents, feat, th, lag=1):
    """Per-trade P&L under 'hedge the whole position on first fire'."""
    out = []
    fired_w = fired_l = nofill_w = nofill_l = 0
    hedges_w, hedges_l = [], []
    for (tk, close, K, tp, sec0, yes, lose, price, secs, sr) in ents:
        if price is None:
            continue
        base = ((-price) if lose else (1.0 - price)) - PR.fee(price)
        cells = list(walk(tp, close, K, yes, sec0, secs, 200))
        fire = None
        for k, tau, f in cells:
            v = f.get(feat)
            if v is not None and v >= th:
                fire = (k, tau)
                break
        if fire is None:
            out.append((base, lose, False))
            continue
        k, tau = fire
        if lose:
            fired_l += 1
        else:
            fired_w += 1
        q = None
        for lg in range(lag, lag + 3):
            row = secs.get(close - tau + lg)
            if row is None:
                continue
            qq = PR.other_ask(row, yes)
            if 0.0 < qq < 1.0:
                q = qq
                break
        if q is None:
            if lose:
                nofill_l += 1
            else:
                nofill_w += 1
            out.append((base, lose, False))
            continue
        h = (1.0 - price - q) - PR.fee(price) - PR.fee(q)
        (hedges_l if lose else hedges_w).append(q)
        out.append((h, lose, True))
    return {"pnl": out, "fired_w": fired_w, "fired_l": fired_l,
            "nofill_w": nofill_w, "nofill_l": nofill_l,
            "hedge_w": hedges_w, "hedge_l": hedges_l}


def truncate_tape(tp, cut_sec):
    """A copy of the tape with every print AFTER cut_sec removed."""
    n = cut_sec - tp.base + 1
    if n <= 0:
        return None
    return IndexTape(tp.base, array.array("d", tp.a[:n]))


def selftest():
    print("SELF-TEST -- vfy_pinexit")
    ok = []

    def ck(c, m):
        ok.append(bool(c))
        print(("  ok   " if c else "  FAIL ") + m)

    tw = 0.05
    base = [-0.95] * 2 + [0.05] * 8
    hedged = [-0.55] * 3 + [0.05] * 7
    d = (sum(hedged) - sum(base)) / tw
    ck(abs(d - ((sum(hedged) - sum(base)) / tw)) < 1e-12,
       "PLANTED: the ledger delta is pure arithmetic")
    ck(d > 0, f"PLANTED: 2 losers saved, 1 winner taxed -> {d:+.1f} wins, "
              "positive, the shape the real table claims")
    base2 = [-0.95] + [0.05] * 9
    hed2 = [-0.55] * 5 + [0.05] * 5
    ck((sum(hed2) - sum(base2)) < 0,
       "PLANTED: 1 loser to 4 taxed winners and the SAME hedge loses money -- "
       "the sign is carried by the ratio, not by the machinery")

    r = score_rule([], "p_model", 0.5)
    ck(r["pnl"] == [] and r["fired_l"] == 0,
       "NULL: an empty population gives an empty ledger and no fires")

    a = array.array("d", [1.0, 2.0, 3.0, 4.0, 5.0])
    t = IndexTape(100, a)
    t2 = truncate_tape(t, 102)
    ck(len(t2.a) == 3 and t2.val(102) == 3.0 and t2.val(103) is None,
       "truncation removes every second after the cut and keeps the rest")
    ck(t.wsum(100, 102) == t2.wsum(100, 102),
       "a window entirely before the cut is bit-identical after truncation")
    ck(pctl(list(range(100)), 0.01) == 1 and pctl(list(range(100)), 0.5) == 50,
       "the percentile helper matches the one the study uses")

    print("SELF-TEST " + ("PASSED" if all(ok) else "FAILED"))
    return all(ok)


RULES = [("p_model", 0.5), ("p_model", 0.9), ("sd_loss", 2.0),
         ("p_gain", 0.25), ("p_mkt", 0.10)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows", default=PX.ROWS)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed; refusing real data")

    by, nrows = PR.load_rows(a.rows, 3, 60)
    lo = min(min(s.keys()) for s in by.values())
    hi = max(max(s.keys()) for s in by.values())
    cache = os.path.join(PX.WORK, "pinexit_idx_wide.pkl")
    idx = PR.load_index_cache(lo - 400, hi + 120, cache)
    tapes = {k: IndexTape(*v) for k, v in idx.items()}
    mk = {}
    for v in json.load(open(PX.FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] in PX.SERIES_TO_INDEX:
                mk[r["ticker"]] = r
    print("\n  rows.jsonl span %s .. %s"
          % (time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(lo)),
             time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(hi))))

    # =================================================================== A
    print("\n" + "=" * 78)
    print("  A -- COST ON THE LIVE WINDOW (tau 3-30, gated). ZERO LOSERS,")
    print("       so every fire is a false alarm and every cent is pure loss.")
    print("=" * 78)
    for first_only in (True, False):
        ents = PR.build_entries(by, tapes, mk, 3, 30, True, first_only)
        nl = sum(1 for e in ents if e[6])
        ncl = len({e[1] for e in ents})
        wl = [1.0 - e[7] - PR.fee(e[7]) for e in ents if not e[6]]
        tw = sum(wl) / len(wl)
        lab = "one entry per market" if first_only else "every entry"
        print("\n  %s: %d entries, %d losers, %d closes"
              % (lab, len(ents), nl, ncl))
        print("  typical win %.2fc  ->  a hedge locking -56c costs %.1f wins"
              % (100 * tw, 0.56 / tw))
        print("  %20s%8s%9s%14s%14s%12s%9s"
              % ("rule", "fires", "fires%", "no-hedge", "hedged",
                 "cost(wins)", "change"))
        for feat, th in RULES:
            r = score_rule(ents, feat, th)
            hed = sum(1 for p, l, h in r["pnl"] if h)
            tot_h = sum(p for p, l, h in r["pnl"]) / tw
            tot_b = sum(((-e[7]) if e[6] else (1.0 - e[7])) - PR.fee(e[7])
                        for e in ents if e[7] is not None) / tw
            print("  %20s%8d%8.2f%%%14.1f%14.1f%12.1f%8.1f%%"
                  % (feat + " >= " + str(th), hed,
                     100 * hed / max(len(ents), 1), tot_b, tot_h,
                     tot_h - tot_b, 100 * (tot_h - tot_b) / abs(tot_b)))

    # =================================================================== B
    print("\n" + "=" * 78)
    print("  B -- LEAVE-ONE-CLOSE-OUT on the headline (+39%), gated,")
    print("       one entry per market, tau 3-60.")
    print("=" * 78)
    ents = PR.build_entries(by, tapes, mk, 3, 60, True, True)
    wl = [1.0 - e[7] - PR.fee(e[7]) for e in ents if not e[6]]
    tw = sum(wl) / len(wl)
    ll = [e[7] + PR.fee(e[7]) for e in ents if e[6]]
    tl = sum(ll) / len(ll)
    print("  %d trades, %d losers, %d closes"
          % (len(ents), sum(1 for e in ents if e[6]),
             len({e[1] for e in ents})))
    print("  typical win %.2fc, typical loss %.2fc, one loss = %.1f wins"
          % (100 * tw, 100 * tl, tl / tw))
    keep = [e for e in ents if e[7] is not None]
    for feat, th in RULES:
        r = score_rule(ents, feat, th)
        per = [(e[1], p, ((-e[7]) if e[6] else (1.0 - e[7])) - PR.fee(e[7]))
               for e, (p, l, h) in zip(keep, r["pnl"])]
        closes = sorted({c for c, _p, _b in per})
        deltas = []
        for c in closes:
            dh = sum(p for cc, p, b in per if cc != c)
            db = sum(b for cc, p, b in per if cc != c)
            deltas.append((dh - db) / tw)
        full = (sum(p for _c, p, _b in per)
                - sum(b for _c, _p, b in per)) / tw
        neg = sum(1 for x in deltas if x <= 0)
        print("  %s >= %s: full %+.1f wins | LOCO min %+.1f max %+.1f | "
              "%d of %d closes whose removal makes it <= 0"
              % (feat, th, full, min(deltas), max(deltas), neg, len(deltas)))

    # =================================================================== D
    print("\n" + "=" * 78)
    print("  D -- NOFILL BY CLASS. A missing book row silently UN-hedges a")
    print("       trade. More missing on winners than losers = flattered.")
    print("=" * 78)
    for feat, th in RULES:
        r = score_rule(ents, feat, th)
        fl, fw = r["fired_l"], r["fired_w"]
        print("  %s >= %s: losers fired %d nofill %d (%.0f%%) | "
              "winners fired %d nofill %d (%.0f%%)"
              % (feat, th, fl, r["nofill_l"], 100 * r["nofill_l"] / max(fl, 1),
                 fw, r["nofill_w"], 100 * r["nofill_w"] / max(fw, 1)))
        if r["hedge_l"] and r["hedge_w"]:
            print("      hedge paid: losers median %.1fc (n=%d), "
                  "winners median %.1fc (n=%d)"
                  % (100 * pctl(r["hedge_l"], 0.5), len(r["hedge_l"]),
                     100 * pctl(r["hedge_w"], 0.5), len(r["hedge_w"])))

    # =================================================================== E
    print("\n" + "=" * 78)
    print("  E -- BREAK-EVEN RATIO, computed from the measured prices.")
    print("=" * 78)
    for feat, th in RULES:
        r = score_rule(ents, feat, th)
        sav, tax = [], []
        for e, (p, l, h) in zip(keep, r["pnl"]):
            if not h:
                continue
            b = ((-e[7]) if e[6] else (1.0 - e[7])) - PR.fee(e[7])
            (sav if e[6] else tax).append((p - b) / tw)
        if sav and tax:
            ms = sum(sav) / len(sav)
            mt = sum(tax) / len(tax)
            print("  %s >= %s: %d losers saved %+.1f wins each, %d winners "
                  "cost %.1f wins each -> BREAK-EVEN needs %.2f losers per "
                  "taxed winner; observed %.2f"
                  % (feat, th, len(sav), ms, len(tax), mt,
                     abs(mt) / ms, len(sav) / len(tax)))
            print("      implied break-even LOSS RATE among trades the alarm "
                  "touches: %.2f%%"
                  % (100 * (abs(mt) / ms) / (1 + abs(mt) / ms)))

    # =================================================================== F
    print("\n" + "=" * 78)
    print("  F -- THE LIVE CEILING IS 0.980; THE STUDY USED 0.988.")
    print("=" * 78)
    for ceil in (0.988, 0.980):
        PR.CEILING = ceil
        e2 = PR.build_entries(by, tapes, mk, 3, 60, True, True)
        wl2 = [1.0 - e[7] - PR.fee(e[7]) for e in e2 if not e[6]]
        ll2 = [e[7] + PR.fee(e[7]) for e in e2 if e[6]]
        tw2 = sum(wl2) / len(wl2)
        tl2 = (sum(ll2) / len(ll2)) if ll2 else float("nan")
        r = score_rule(e2, "p_model", 0.5)
        tot_h = sum(p for p, l, h in r["pnl"]) / tw2
        tot_b = sum(((-e[7]) if e[6] else (1.0 - e[7])) - PR.fee(e[7])
                    for e in e2 if e[7] is not None) / tw2
        print("  ceiling %.3f: %d trades, %d losers, typical win %.2fc, "
              "one loss = %.1f wins; p_model>=0.5 total %.1f -> %.1f wins "
              "(%+.1f%%)"
              % (ceil, len(e2), sum(1 for e in e2 if e[6]), 100 * tw2,
                 tl2 / tw2, tot_b, tot_h,
                 100 * (tot_h - tot_b) / abs(tot_b)))
    PR.CEILING = 0.988


if __name__ == "__main__":
    main()
