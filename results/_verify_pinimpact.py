"""Artefact check for pinimpact (d1): does the orderbook_delta channel report
a sweep BEFORE or AFTER the trade channel does?

If the book deltas that remove the liquidity carry a ts_ms EARLIER than the
trade print, then the "pre-sweep displayed book" pinimpact walks is already
depleted, and the measured fade of ~0.00c would be an artefact of scoring the
sweep against its own aftermath.

Method: for every trade print, the resting order it consumed sits on the
OPPOSITE book at price (100 - taker cost).  Find negative deltas on exactly
that (market, side, price) and report the signed time difference to the
nearest one.
"""
import bisect
import os
import sys
from collections import defaultdict

sys.path.insert(0, r"C:\kals-repo\research")
from pinimpact import read_trades, read_deltas       # noqa: E402

HOUR = sys.argv[1] if len(sys.argv) > 1 else "20260908T19"
SER = ("KXBTC15M",)
D = r"C:\kals\kalshi_data"

neg = defaultdict(list)
for tk, ts, side, pc, dq in read_deltas(
        os.path.join(D, "orderbook_delta", HOUR + ".jsonl.gz"), SER):
    if dq < 0:
        neg[(tk, side, round(pc, 4))].append(ts)
for v in neg.values():
    v.sort()
print(f"  {sum(len(v) for v in neg.values()):,} negative deltas on "
      f"{len(neg):,} (market, side, price) keys")

diffs = []
nokey = 0
tot = 0
for tk, ts, side, cost, q in read_trades(
        os.path.join(D, "trade", HOUR + ".jsonl.gz"), SER):
    tot += 1
    dside = "no" if side == "yes" else "yes"
    key = (tk, dside, round(100.0 - cost, 4))
    v = neg.get(key)
    if not v:
        nokey += 1
        continue
    i = bisect.bisect_left(v, ts)
    best = None
    for j in (i - 1, i):
        if 0 <= j < len(v):
            d = v[j] - ts
            if best is None or abs(d) < abs(best):
                best = d
    if best is not None:
        diffs.append(best)

diffs.sort()
n = len(diffs)
print(f"  {tot:,} trade prints, {nokey:,} with no matching book level, "
      f"{n:,} matched")
if n:
    def q(p):
        return diffs[min(n - 1, int(p * n))]
    print(f"  signed ms from the trade print to the nearest matching "
          f"negative delta (delta - trade):")
    print(f"    p01 {q(0.01):>7}   p10 {q(0.10):>7}   median {q(0.5):>7}   "
          f"p90 {q(0.90):>7}   p99 {q(0.99):>7}")
    print(f"    exactly 0 ms       {sum(1 for d in diffs if d == 0):>9,}  "
          f"{100.0*sum(1 for d in diffs if d == 0)/n:>6.2f}%")
    print(f"    delta STRICTLY BEFORE the trade  "
          f"{sum(1 for d in diffs if d < 0):>9,}  "
          f"{100.0*sum(1 for d in diffs if d < 0)/n:>6.2f}%")
    print(f"    delta at or after the trade      "
          f"{sum(1 for d in diffs if d >= 0):>9,}  "
          f"{100.0*sum(1 for d in diffs if d >= 0)/n:>6.2f}%")
    print()
    print("  A large 'strictly before' share would mean the replayed book is")
    print("  already eaten when the sweep is scored, and the ~0.00c fade in")
    print("  (d1) would be an artefact.  A share at or after means the book")
    print("  pinimpact walks is genuinely the pre-sweep book.")
