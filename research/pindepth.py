#!/usr/bin/env python3
"""pindepth.py -- is a THIN offer a warning?

THE OPERATOR asked what the "depth thing" is, so here it is stated plainly: when
we buy, somebody is selling. If five hundred contracts are on offer that is a
crowd getting out. If eight are on offer it might be one person who knows
something we do not, and we are buying precisely what they want rid of.

An earlier look used OUR FILL SIZE as the proxy and found small fills lose more
often. That conflates two different things -- how much we wanted and how much
was there -- so it could not separate "thin book" from "small order". This uses
the offer size the bot recorded at the moment it decided (`size` on the signal
record), which is the book, not us.

THE BOT CURRENTLY IGNORES THIS ENTIRELY. It gates on price, on modelled
probability, on edge and on expected value. Nothing looks at how many are for
sale. If thin offers really are adversely selected, a depth gate cuts losses
without touching any of the deep trades that make the money -- more money AND
less loss, which is the only combination worth a live change.

DISCIPLINE. Clustered by close per hard rule 4, and split in time, because the
last two headline numbers in this project did not survive either test. Live
fills only, per the 2026-09-10 amendment.

    python research/pindepth.py --selftest
    python research/pindepth.py
"""
import argparse
import glob
import json
import sys

LIVE = r"C:\kals-repo\results\pinrun-live-*.jsonl"
BANDS = [(0, 10), (10, 25), (25, 60), (60, 150), (150, 1e9)]


def band_of(n):
    for lo, hi in BANDS:
        if lo <= n < hi:
            return (lo, hi)
    return None


def label(b):
    lo, hi = b
    return "%g+ on offer" % lo if hi > 1e8 else "%g to %g on offer" % (lo, hi)


def pair(rows):
    """[(offered, filled, pnl_c)] -- offered is the BOOK, not our order."""
    last, pend, out = {}, {}, []
    for r in rows:
        k, tk = r.get("kind"), r.get("ticker")
        if not tk:
            continue
        if k == "signal":
            s = r.get("size")
            if isinstance(s, (int, float)):
                last[tk] = float(s)
        elif k == "order" and (r.get("filled") or 0) > 0:
            if tk in last:
                pend.setdefault(tk, []).append((last[tk], float(r["filled"])))
        elif k == "settled":
            q = pend.get(tk)
            if q and isinstance(r.get("pnl_c"), (int, float)):
                off, n = q.pop(0)
                out.append((off, n, float(r["pnl_c"])))
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


def summarise(rows, bands=BANDS):
    d = {b: {"n": 0, "lost": 0, "pnl": 0.0, "c": 0.0} for b in bands}
    for off, n, p in rows:
        b = band_of(off)
        if not b:
            continue
        s = d[b]
        s["n"] += 1
        s["lost"] += p < 0
        s["pnl"] += p / 100.0          # pnl_c is the WHOLE trade, in cents
        s["c"] += n
    return d


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " + m) if c else ("FAIL: " + m))
        ok = ok and c

    ck(band_of(8) == (0, 10), "eight on offer is the thinnest band")
    ck(band_of(500) == (150, 1e9), "five hundred is the deepest")
    ck(band_of(-1) is None, "NULL: a negative offer belongs nowhere")

    rows = [{"kind": "signal", "ticker": "A", "size": 8},
            {"kind": "order", "ticker": "A", "filled": 8},
            {"kind": "settled", "ticker": "A", "pnl_c": -780.0},
            {"kind": "signal", "ticker": "B", "size": 400},
            {"kind": "order", "ticker": "B", "filled": 80},
            {"kind": "settled", "ticker": "B", "pnl_c": 150.0}]
    got = pair(rows)
    ck(len(got) == 2, "both trades pair up")
    ck(got[0][0] == 8 and got[1][0] == 400,
       "THE POINT: what is recorded is what was ON OFFER (8 and 400), not what "
       "we bought (8 and 80). The earlier look confused the two.")
    ck(got[1][1] == 80, "our own fill still travels alongside")
    ck(pair([{"kind": "order", "ticker": "C", "filled": 5},
             {"kind": "settled", "ticker": "C", "pnl_c": 1.0}]) == [],
       "NULL: a fill with no signal recorded is dropped, never scored against "
       "an assumed depth")

    d = summarise([(8, 8, -780.0), (400, 80, 150.0)])
    ck(abs(d[(0, 10)]["pnl"] + 7.80) < 1e-9,
       "pnl_c is the whole trade in cents: -780 becomes -$7.80, not -$624")
    print("pindepth selftest:", "OK" if ok else "FAILED")
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
        print("loaded nothing -- no completed live trades with a signal")
        return 0

    d = summarise(rows)
    print("\nLIVE TRADES (%d closes), split by HOW MANY WERE ON OFFER\n" % len(rows))
    print("  %-20s %7s %7s %9s %11s %12s"
          % ("on offer", "closes", "losses", "loss rate", "total $", "$ per close"))
    print("  " + "-" * 70)
    for b in BANDS:
        s = d[b]
        if not s["n"]:
            continue
        print("  %-20s %7d %7d %8.1f%% %11.2f %12.3f"
              % (label(b), s["n"], s["lost"], 100 * s["lost"] / s["n"],
                 s["pnl"], s["pnl"] / s["n"]))

    thin = [b for b in BANDS if b[1] <= 25]
    tn = sum(d[b]["n"] for b in thin)
    tl = sum(d[b]["lost"] for b in thin)
    tp = sum(d[b]["pnl"] for b in thin)
    deep = [b for b in BANDS if b[0] >= 60]
    dn = sum(d[b]["n"] for b in deep)
    dl = sum(d[b]["lost"] for b in deep)
    dp = sum(d[b]["pnl"] for b in deep)
    print()
    if tn and dn:
        print("  Under 25 on offer: %d closes, %d losses (%.1f%%), $%+.2f."
              % (tn, tl, 100 * tl / tn, tp))
        print("  Sixty or more:     %d closes, %d losses (%.1f%%), $%+.2f."
              % (dn, dl, 100 * dl / dn, dp))

    half = len(rows) // 2
    print("\n  HOLDOUT -- first half of our live history against the second:")
    print("  %-20s %20s %20s" % ("on offer", "earlier", "later"))
    print("  " + "-" * 62)
    for b in BANDS:
        cells = []
        for part in (rows[:half], rows[half:]):
            s = summarise(part)[b]
            cells.append((s["pnl"], s["n"], s["lost"]))
        if cells[0][1] or cells[1][1]:
            print("  %-20s %9.2f n=%-3d L=%-3d %9.2f n=%-3d L=%-3d"
                  % (label(b), cells[0][0], cells[0][1], cells[0][2],
                     cells[1][0], cells[1][1], cells[1][2]))
    print("\n  A band that only looks bad in one half is a story about a few")
    print("  closes, not a property of thin books. That test has killed two")
    print("  findings today already.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
