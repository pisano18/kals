#!/usr/bin/env python3
"""cdcalive.py -- when is there actually a market to trade?

The claim I made to the operator this morning, off one or two samples per
close, was "the book goes empty about 40 seconds before every close". The
recorder was only revisiting a contract every 48 seconds at the time, so that
claim had almost no support. It now samples every 3 seconds, so the question
can be answered properly and across every contract rather than four.

WHAT IT MEASURES. For each snapshot, how far it sits from the close, and
whether there was anything on each side. Aggregated into buckets, that gives
the honest shape of the trading day: the fraction of looks at which a side was
quotable, and the depth when it was.

WHY IT DECIDES THE STRATEGY. The pin works in the last 30 seconds because the
settlement average is nearly locked. If no market exists there, that edge is
unreachable on this venue whatever else is true, and the tradeable window is
whatever earlier band still has two sides and size.

READ-ONLY.

    python research/cdcalive.py --selftest
    python research/cdcalive.py
"""
import argparse
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import cdcedge                                               # noqa: E402

BUCKETS = [(0, 15), (15, 30), (30, 45), (45, 60), (60, 90), (90, 120),
           (120, 180), (180, 300), (300, 420)]


def bucket_of(tau):
    for lo, hi in BUCKETS:
        if lo <= tau < hi:
            return (lo, hi)
    return None


def side_depth(bk, key):
    rows = bk.get(key) or []
    if not rows:
        return 0.0
    try:
        return sum(float(r[1]) for r in rows)
    except (TypeError, ValueError, IndexError):
        return 0.0


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " + m) if c else ("FAIL: " + m))
        ok = ok and c

    ck(bucket_of(0) == (0, 15) and bucket_of(14.9) == (0, 15),
       "the first bucket holds the last fifteen seconds")
    ck(bucket_of(30) == (30, 45),
       "and the boundary belongs to the bucket above, not below")
    ck(bucket_of(500) is None and bucket_of(-1) is None,
       "NULL: outside the watched window belongs to no bucket")
    bk = {"bids": [["0.4", "10"], ["0.3", "5"]], "asks": []}
    ck(side_depth(bk, "bids") == 15.0, "depth sums every level on a side")
    ck(side_depth(bk, "asks") == 0.0,
       "NULL: an absent side is zero depth, which is what 'no market' means")
    ck(side_depth({"bids": [["x", "y"]]}, "bids") == 0.0,
       "NULL: unparseable sizes count as no depth rather than crashing")
    print("cdcalive selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0

    insts = cdcedge.load_instruments()
    books = cdcedge.load_books()
    if not books:
        print("loaded nothing -- no CDNA tape yet")
        return 0

    stats = {b: {"n": 0, "bid": 0, "ask": 0, "both": 0, "depth": []}
             for b in BUCKETS}
    closes = set()
    for sym, snaps in books.items():
        r = insts.get(sym) or {}
        att = (r.get("event_details") or {}).get("attributes") or {}
        close = cdcedge.parse_close(att.get("CLOSE_TIME"))
        if not close:
            continue
        for ts, bk in snaps:
            if not ts:
                continue
            b = bucket_of(close - ts / 1000.0)
            if not b:
                continue
            s = stats[b]
            s["n"] += 1
            closes.add((sym, close))
            db, da = side_depth(bk, "bids"), side_depth(bk, "asks")
            s["bid"] += db > 0
            s["ask"] += da > 0
            if db > 0 and da > 0:
                s["both"] += 1
                s["depth"].append(min(db, da))

    print("\nHow often is there a market, by seconds left to close?")
    print("(%d closes, %d snapshots)\n" % (len(closes), sum(s["n"] for s in stats.values())))
    print("  %-14s %8s %9s %9s %11s %12s"
          % ("seconds left", "looks", "bid side", "ask side", "both sides", "median size"))
    print("  " + "-" * 68)
    for b in BUCKETS:
        s = stats[b]
        if not s["n"]:
            continue
        med = statistics.median(s["depth"]) if s["depth"] else 0
        print("  %-14s %8d %8.0f%% %8.0f%% %10.0f%% %12s"
              % ("%d to %d" % b, s["n"], 100 * s["bid"] / s["n"],
                 100 * s["ask"] / s["n"], 100 * s["both"] / s["n"],
                 ("%.0f" % med) if med else "-"))

    late = sum(stats[b]["both"] for b in BUCKETS if b[1] <= 45)
    late_n = sum(stats[b]["n"] for b in BUCKETS if b[1] <= 45)
    early = sum(stats[b]["both"] for b in BUCKETS if b[0] >= 120)
    early_n = sum(stats[b]["n"] for b in BUCKETS if b[0] >= 120)
    print()
    if late_n:
        print("  Inside the last 45 seconds -- the window the pin needs -- both")
        print("  sides were quoted on %d of %d looks (%.0f%%)."
              % (late, late_n, 100 * late / late_n))
    if early_n:
        print("  Two minutes or more out, both sides were quoted on %d of %d"
              " looks (%.0f%%)." % (early, early_n, 100 * early / early_n))
    if late_n and early_n and late / late_n < 0.2 <= early / early_n:
        print("\n  So the market really does shut before the close. The pin")
        print("  cannot be run here. Any strategy has to live further out,")
        print("  where the settlement average is NOT yet locked and the bet is")
        print("  a forecast rather than a near-certainty.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
