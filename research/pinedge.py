#!/usr/bin/env python3
"""pinedge.py -- are our THIN trades actually making money?

THE OPERATOR, 2026-09-16. He asked what the 705 edge_floor refusals were, I
looked, and the answer reframed the question. Those refusals were not
uncertain bets: in half the bot was 99%+ sure of yes, in the other half 99%+
sure of no. What it refused was the PRICE -- less than 0.3 cents of profit per
contract after fees.

EDGE_FLOOR is 0.003, a third of a cent. These trades happen at 97 to 99 cents,
so a loss costs about 97. At a fifth of a cent a win you need roughly four
hundred wins to pay for one loss, and we lose about one close in forty. That
arithmetic says the floor may be too LOW, not too high -- and if the thin
trades are net negative, RAISING it earns more and loses less at the same
time, which is both of his priorities in one change.

WHAT IT DOES. Joins each live signal (which carries `edge_c`, the edge in
cents the bot computed at the moment it decided) to the fill it produced and
the settlement that followed, then reports profit by how thin the edge was.

SOURCE: LIVE FILLS ONLY, per the 2026-09-10 amendment. Never the tape, never
the replay.

    python research/pinedge.py --selftest
    python research/pinedge.py
"""
import argparse
import glob
import json
import os
import sys

LIVE = r"C:\kals-repo\results\pinrun-live-*.jsonl"
BANDS = [(0.0, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 4.0), (4.0, 1e9)]


def band_of(e):
    for lo, hi in BANDS:
        if lo <= e < hi:
            return (lo, hi)
    return None


def label(b):
    lo, hi = b
    return "%.1f+ cents" % lo if hi > 1e8 else "%.1f to %.1f cents" % (lo, hi)


def split_halves(rows):
    """Earlier half of the trades against the later half, in order.

    CLAUDE.md: no threshold is deployed from one look at one sample. A band
    that loses money in both halves is a finding; one that loses in a single
    half is a story about four bad closes."""
    half = len(rows) // 2
    return rows[:half], rows[half:]


def pair(rows):
    """[(edge_c, filled, pnl_c)] by walking one log in order.

    A signal is remembered per ticker, attached to the next FILLED order on
    that ticker, and closed out by the next settlement on it. Anything that
    does not complete the chain is dropped rather than guessed at."""
    last_sig, pending, out = {}, {}, []
    for r in rows:
        k, tk = r.get("kind"), r.get("ticker")
        if not tk:
            continue
        if k == "signal":
            last_sig[tk] = r.get("edge_c")
        elif k == "order" and (r.get("filled") or 0) > 0:
            if tk in last_sig and last_sig[tk] is not None:
                pending.setdefault(tk, []).append((last_sig[tk],
                                                   float(r["filled"])))
        elif k == "settled":
            q = pending.get(tk)
            if q:
                e, n = q.pop(0)
                p = r.get("pnl_c")
                if isinstance(p, (int, float)):
                    out.append((float(e), n, float(p)))
    return out


def load():
    out = []
    for fp in sorted(glob.glob(LIVE)):
        rows = []
        for line in open(fp, encoding="utf-8", errors="replace"):
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
        out.extend(pair(rows))
    return out


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " + m) if c else ("FAIL: " + m))
        ok = ok and c

    ck(band_of(0.3) == (0.0, 0.5), "a third of a cent is the thinnest band")
    ck(band_of(9.0) == (4.0, 1e9), "and a fat edge lands in the open band")
    ck(band_of(-1) is None, "NULL: a negative edge belongs to no band")

    rows = [{"kind": "signal", "ticker": "A", "edge_c": 0.4},
            {"kind": "order", "ticker": "A", "filled": 10},
            {"kind": "settled", "ticker": "A", "pnl_c": -97.0},
            {"kind": "signal", "ticker": "B", "edge_c": 3.0},
            {"kind": "order", "ticker": "B", "filled": 0},
            {"kind": "settled", "ticker": "B", "pnl_c": 5.0}]
    got = pair(rows)
    ck(len(got) == 1, "an UNFILLED order produces no row -- a signal we never "
                      "took is not a trade we made")
    ck(got[0] == (0.4, 10.0, -97.0), "the edge, the size and the outcome "
                                     "travel together")
    ck(pair([{"kind": "settled", "ticker": "C", "pnl_c": 1.0}]) == [],
       "NULL: a settlement with no matching fill is dropped, never counted "
       "against an imagined trade")
    ck(pair([{"kind": "signal", "ticker": "D", "edge_c": None},
             {"kind": "order", "ticker": "D", "filled": 5},
             {"kind": "settled", "ticker": "D", "pnl_c": 1.0}]) == [],
       "NULL: a signal with no edge recorded is dropped rather than read as "
       "an edge of zero")
    print("pinedge selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0
    rows = load()
    if not rows:
        print("loaded nothing -- no completed live trades found")
        return 0

    stats = {b: {"n": 0, "lost": 0, "c": 0.0, "pnl": 0.0} for b in BANDS}
    for e, n, p in rows:
        b = band_of(e)
        if not b:
            continue
        s = stats[b]
        s["n"] += 1
        s["lost"] += p < 0
        s["c"] += n
        # pnl_c IS THE WHOLE TRADE IN CENTS, NOT CENTS PER CONTRACT. The first
        # version multiplied by the fill size and reported $19,554 of profit on
        # a $511 bank, which is impossible on its face and is why the rule is
        # to reconcile a good-looking number by hand before believing it.
        # Checked against the log directly: a settled record with pnl_c 38.89
        # moves `realised` by exactly 0.3889.
        s["pnl"] += p / 100.0
    print("\nLIVE TRADES ONLY (%d closes). The floor is 0.3 cents.\n" % len(rows))
    print("  %-18s %7s %7s %11s %13s %12s"
          % ("edge at entry", "closes", "losses", "contracts", "total $", "$ per close"))
    print("  " + "-" * 74)
    for b in BANDS:
        s = stats[b]
        if not s["n"]:
            continue
        print("  %-18s %7d %7d %11.0f %11.2f %12.3f"
              % (label(b), s["n"], s["lost"], s["c"], s["pnl"],
                 s["pnl"] / s["n"]))

    early, late = split_halves(rows)
    print("\n  HOLDOUT -- the same bands, first half of our live history "
          "against the second:")
    print("  %-18s %18s %18s" % ("edge at entry", "earlier", "later"))
    print("  " + "-" * 56)
    for b in BANDS:
        cells = []
        for part in (early, late):
            got = [p for e, n, p in part if band_of(e) == b]
            cells.append((sum(got) / 100.0, len(got)))
        if cells[0][1] or cells[1][1]:
            print("  %-18s %11.2f n=%-4d %11.2f n=%-4d"
                  % (label(b), cells[0][0], cells[0][1],
                     cells[1][0], cells[1][1]))

    thin = stats[BANDS[0]]
    rest = {"n": 0, "pnl": 0.0, "lost": 0}
    for b in BANDS[1:]:
        for k in rest:
            rest[k] += stats[b][k]
    print()
    if thin["n"]:
        print("  Thinnest band (under half a cent): %d closes, %d losses, "
              "$%+.2f total." % (thin["n"], thin["lost"], thin["pnl"]))
        print("  Everything else: %d closes, %d losses, $%+.2f total."
              % (rest["n"], rest["lost"], rest["pnl"]))
    if thin["n"] < 30:
        print("\n  UNDER THIRTY CLOSES IN THE THIN BAND. That is below the")
        print("  floor this project uses for claiming anything, so this is a")
        print("  direction to watch, not a change to deploy. Raising a live")
        print("  threshold on it would be exactly the tuning-on-noise that")
        print("  the pre-registration rule exists to prevent.")
    elif thin["pnl"] < 0:
        print("\n  The thin band LOSES money over %d closes. Raising EDGE_FLOOR"
              % thin["n"])
        print("  would earn more and lose less at once. Pre-register the bar")
        print("  before changing it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
