#!/usr/bin/env python3
"""pinsmall.py -- are small fills worse than large ones?

THE OPERATOR, 2026-09-16: "the pin bot is only doing really small trades and
one lost a few cents what's up with that".

The mechanics are not a mystery. Autosize wants 85-86 contracts on a $511
bank, and it got exactly that four times today. The small fills are small
because the BOOK was small: AMENDMENT 28 set --min-fill-frac 0, so a thin
offer is taken rather than skipped, and one of those was a single contract at
97.7c that went wrong and had to be hedged.

The question his observation raises is the one worth answering: A SINGLE
CONTRACT OFFERED AT 97.7c IS NOT THE SAME EVENT AS EIGHTY-FIVE OFFERED AT
97.7c. If the tiny offers are systematically the ones someone is dumping
because they know something, then min-fill-frac 0 is buying adverse selection
at a size too small to pay for itself, and there should be a floor.

SOURCE: LIVE FILLS ONLY. Per the 2026-09-10 amendment, a loss rate never comes
from the tape or the replay. This reads results/pinrun-live-*.jsonl and nothing
else, pairs each filled order with its settlement, and reports by fill size.

    python research/pinsmall.py --selftest
    python research/pinsmall.py
"""
import argparse
import glob
import json
import os
import sys

LIVE = r"C:\kals-repo\results\pinrun-live-*.jsonl"
BUCKETS = [(0, 2), (2, 10), (10, 30), (30, 60), (60, 1e9)]


def bucket_of(n):
    for lo, hi in BUCKETS:
        if lo <= n < hi:
            return (lo, hi)
    return None


def label(b):
    lo, hi = b
    return "%g+" % lo if hi > 1e8 else "%g to %g" % (lo, hi)


def load(pattern=LIVE):
    """[(ticker, filled, entry_price, realised_delta)] from live logs only."""
    out = []
    for fp in sorted(glob.glob(pattern)):
        rows = []
        for line in open(fp, encoding="utf-8", errors="replace"):
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
        fills = {}
        for r in rows:
            if r.get("kind") == "order" and (r.get("filled") or 0) > 0:
                fills.setdefault(r.get("ticker"), []).append(r)
        prev = None
        for r in rows:
            if r.get("kind") != "settled":
                continue
            cur = r.get("realised")
            if cur is None:
                continue
            delta = cur if prev is None else cur - prev
            prev = cur
            got = fills.get(r.get("ticker"))
            if not got:
                continue
            o = got.pop(0)
            out.append((r.get("ticker"), float(o.get("filled") or 0),
                        o.get("exec_yes_price"), delta))
    return out


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " + m) if c else ("FAIL: " + m))
        ok = ok and c

    ck(bucket_of(1) == (0, 2), "a single contract lands in the smallest bucket")
    ck(bucket_of(85) == (60, 1e9), "and a full-size fill in the largest")
    ck(bucket_of(-1) is None, "NULL: a negative fill belongs nowhere")
    ck(label((60, 1e9)) == "60+", "the open bucket is labelled as open")

    # THE DELTA RULE IS THE ONE THAT HAS BITTEN BEFORE. `realised` is a RUNNING
    # TOTAL. On 2026-09-15 summing running totals produced a reported
    # "+$731.74 overnight" when the truth was +$88.36. Differencing is the
    # whole correctness of this file, so it is tested directly.
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), "pinrun-live-test.jsonl")
    with open(p, "w", encoding="utf-8") as fh:
        for o in ({"kind": "order", "ticker": "A", "filled": 5,
                   "exec_yes_price": 0.97},
                  {"kind": "order", "ticker": "B", "filled": 80,
                   "exec_yes_price": 0.96},
                  {"kind": "settled", "ticker": "A", "realised": 1.00},
                  {"kind": "settled", "ticker": "B", "realised": 3.50}):
            fh.write(json.dumps(o) + "\n")
    got = load(p)
    ck(len(got) == 2, "both closes are paired with their fills")
    ck(abs(got[0][3] - 1.00) < 1e-9 and abs(got[1][3] - 2.50) < 1e-9,
       "the second close earns 2.50, not 3.50 -- realised is a RUNNING TOTAL "
       "and differencing it is the whole point")
    ck(got[1][1] == 80, "fill size travels with the close")
    print("pinsmall selftest:", "OK" if ok else "FAILED")
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
        print("loaded nothing -- no live fills found")
        return 0
    stats = {b: {"n": 0, "lost": 0, "pnl": 0.0, "con": 0.0} for b in BUCKETS}
    for tk, n, px, d in rows:
        b = bucket_of(n)
        if not b:
            continue
        s = stats[b]
        s["n"] += 1
        s["lost"] += d < 0
        s["pnl"] += d
        s["con"] += n
    print("\nLIVE FILLS ONLY (%d closes). Never the tape -- see the "
          "2026-09-10 amendment.\n" % len(rows))
    print("  %-12s %7s %7s %12s %14s %13s"
          % ("fill size", "closes", "losses", "total $", "$ per close", "cents/contract"))
    print("  " + "-" * 70)
    for b in BUCKETS:
        s = stats[b]
        if not s["n"]:
            continue
        print("  %-12s %7d %7d %12.2f %14.3f %13s"
              % (label(b), s["n"], s["lost"], s["pnl"], s["pnl"] / s["n"],
                 ("%.2f" % (100 * s["pnl"] / s["con"])) if s["con"] else "-"))
    small = sum(stats[b]["n"] for b in BUCKETS if b[1] <= 10)
    smalll = sum(stats[b]["lost"] for b in BUCKETS if b[1] <= 10)
    big = sum(stats[b]["n"] for b in BUCKETS if b[0] >= 30)
    bigl = sum(stats[b]["lost"] for b in BUCKETS if b[0] >= 30)
    print()
    if small and big:
        print("  Under 10 contracts: %d of %d closes lost (%.0f%%)."
              % (smalll, small, 100 * smalll / small))
        print("  Thirty or more:     %d of %d closes lost (%.0f%%)."
              % (bigl, big, 100 * bigl / big))
    if small < 12 or big < 12:
        print("\n  NOT ENOUGH YET. Under a dozen closes in a bucket cannot")
        print("  separate a real difference from noise, and our floor for")
        print("  claiming anything is 30 clusters. This is a monitor, not a")
        print("  verdict, until the counts grow.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
