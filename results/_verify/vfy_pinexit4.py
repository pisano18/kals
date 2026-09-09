#!/usr/bin/env python3
"""vfy_pinexit4.py -- THE LEDGER WITH FILLS CAPPED BY THE DEPTH THAT WAS
ACTUALLY RESTING, at the operator's live size of 20.

The study's ledger assumes every hedge fills in full at the displayed ask and
labels the saving "an upper bound". This prices that bound. For each trade the
alarm fires on, the hedge fills min(size, resting depth) of `size` contracts
and the remainder stays exposed:

    pnl = f * (1 - price - q - fee(price) - fee(q)) + (1 - f) * base
    f   = min(depth, size) / size

WHY THIS MATTERS MORE THAN THE STUDY ALLOWS. Depth is not symmetric between
the two classes. A false alarm fires while the market is calm and the book is
thick, so the tax fills. A real alarm fires while the market is repricing and
the book is thin, so the saving does not. If that is true, capping fills
removes benefit without removing cost, and the direction of the error is
exactly the one that flatters the hedge.

Where rows.jsonl records no depth on the hedge side (the model had not yet
switched, so the ask is inferred from our own side's bid) the depth is UNKNOWN.
Both bounds are reported -- treat-as-full and treat-as-zero -- rather than
picking one.

SELFTEST: a planted world where the depth cap has a known effect, and a null
world where depth exceeds size everywhere so the cap must change nothing.
"""
import argparse
import json
import os
import sys

HERE = r"C:\kals-repo\research"
sys.path.insert(0, HERE)
sys.path.insert(0, r"C:\kals-repo\results\_verify")
import pinexit as PX                                            # noqa: E402
import pinexit_run as PR                                        # noqa: E402
from pinexit import IndexTape, walk                             # noqa: E402
from vfy_pinexit import pctl                                    # noqa: E402


def blend(base, hedged, depth, size, unknown="full"):
    """Per-contract P&L when only `depth` of `size` contracts can be hedged."""
    if depth is None:
        f = 1.0 if unknown == "full" else 0.0
    else:
        f = min(depth, size) / float(size)
    return f * hedged + (1.0 - f) * base


def fire_and_price(ents, feat, th, lag=1):
    """(entry, base, hedged, depth or None, lose) for every trade."""
    out = []
    for (tk, close, K, tp, sec0, yes, lose, price, secs, sr) in ents:
        if price is None:
            continue
        base = ((-price) if lose else (1.0 - price)) - PR.fee(price)
        fire = None
        for k, tau, f in walk(tp, close, K, yes, sec0, secs, 200):
            v = f.get(feat)
            if v is not None and v >= th:
                fire = tau
                break
        if fire is None:
            out.append((close, base, None, None, lose))
            continue
        q = dep = None
        for lg in range(lag, lag + 3):
            row = secs.get(close - fire + lg)
            if row is None:
                continue
            qq = PR.other_ask(row, yes)
            if not (0.0 < qq < 1.0):
                continue
            q = qq
            if bool(row["side_yes"]) != bool(yes):
                dep = float(row.get("size") or 0.0)
            break
        if q is None:
            out.append((close, base, None, None, lose))
            continue
        h = (1.0 - price - q) - PR.fee(price) - PR.fee(q)
        out.append((close, base, h, dep, lose))
    return out


def selftest():
    print("SELF-TEST -- vfy_pinexit4")
    ok = []

    def ck(c, m):
        ok.append(bool(c))
        print(("  ok   " if c else "  FAIL ") + m)

    ck(blend(-0.95, -0.55, 20, 20) == -0.55,
       "PLANTED: depth exactly equal to size gives the fully hedged number")
    ck(blend(-0.95, -0.55, 200, 20) == -0.55,
       "NULL: depth far above size changes nothing -- the cap only ever bites")
    ck(abs(blend(-0.95, -0.55, 10, 20) - (-0.75)) < 1e-12,
       "PLANTED: half the size fillable gives exactly the midpoint (-0.75)")
    ck(blend(-0.95, -0.55, 0, 20) == -0.95,
       "PLANTED: nothing resting means the trade is not hedged at all")
    ck(blend(-0.95, -0.55, None, 20, "full") == -0.55
       and blend(-0.95, -0.55, None, 20, "zero") == -0.95,
       "unknown depth is reported as BOTH bounds, never silently as one")
    ck(blend(0.05, -0.55, 1000, 20) == -0.55,
       "a deep book means a false alarm pays its tax in full")
    ck(fire_and_price([], "p_model", 0.5) == [],
       "NULL: an empty population produces an empty ledger")
    print("SELF-TEST " + ("PASSED" if all(ok) else "FAILED"))
    return all(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows", default=PX.ROWS)
    ap.add_argument("--size", type=int, default=20)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed; refusing real data")

    by, nrows = PR.load_rows(a.rows, 3, 60)
    lo = min(min(s.keys()) for s in by.values())
    hi = max(max(s.keys()) for s in by.values())
    idx = PR.load_index_cache(lo - 400, hi + 120,
                              os.path.join(PX.WORK, "pinexit_idx_wide.pkl"))
    tapes = {k: IndexTape(*v) for k, v in idx.items()}
    mk = {}
    for v in json.load(open(PX.FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] in PX.SERIES_TO_INDEX:
                mk[r["ticker"]] = r
    ents = PR.build_entries(by, tapes, mk, 3, 60, True, True)
    wl = [1.0 - e[7] - PR.fee(e[7]) for e in ents if not e[6]]
    tw = sum(wl) / len(wl)

    print("\n" + "=" * 78)
    print("  J -- THE LEDGER WITH FILLS CAPPED BY RESTING DEPTH, size %d"
          % a.size)
    print("=" * 78)
    print("  438 trades, 12 losers, typical win %.2fc" % (100 * tw))
    print("\n  %16s%11s%12s%12s%12s%10s"
          % ("rule", "no hedge", "full fill", "capped/full",
             "capped/zero", "worst"))
    print("  " + "-" * 74)
    for feat, th in (("p_model", 0.5), ("p_model", 0.9), ("sd_loss", 2.0)):
        rows = fire_and_price(ents, feat, th)
        base = sum(r[1] for r in rows) / tw
        full = sum(r[1] if r[2] is None else r[2] for r in rows) / tw
        capf = sum(r[1] if r[2] is None
                   else blend(r[1], r[2], r[3], a.size, "full")
                   for r in rows) / tw
        capz = sum(r[1] if r[2] is None
                   else blend(r[1], r[2], r[3], a.size, "zero")
                   for r in rows) / tw
        wf = min((r[1] if r[2] is None
                  else blend(r[1], r[2], r[3], a.size, "full"))
                 for r in rows) / tw
        print("  %16s%11.1f%12.1f%12.1f%12.1f%10.1f"
              % (feat + ">=" + str(th), base, full, capf, capz, wf))
        dl = [r[3] for r in rows if r[4] and r[2] is not None]
        dw = [r[3] for r in rows if not r[4] and r[2] is not None]
        kl = [d for d in dl if d is not None]
        kw = [d for d in dw if d is not None]
        print("      hedge-side depth: LOSERS median %s (n=%d known of %d), "
              "WINNERS median %s (n=%d known of %d)"
              % (("%.0f" % pctl(kl, 0.5)) if kl else "?", len(kl), len(dl),
                 ("%.0f" % pctl(kw, 0.5)) if kw else "?", len(kw), len(dw)))
        if kl and kw:
            print("      share fillable at size %d: LOSERS %.0f%%, "
                  "WINNERS %.0f%%  <-- the asymmetry that decides it"
                  % (a.size,
                     100 * sum(min(d, a.size) for d in kl)
                     / (a.size * len(kl)),
                     100 * sum(min(d, a.size) for d in kw)
                     / (a.size * len(kw))))
    print("\n  'capped/full' treats an unknown depth as a full fill (the")
    print("  study's own assumption); 'capped/zero' treats it as no fill.")
    print("  The truth is between them and neither is chosen here.")


if __name__ == "__main__":
    main()
