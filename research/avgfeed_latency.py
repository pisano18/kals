"""Leak-check on the --strict-rx gate itself.

--strict-rx admits a message when _rx_ms <= (close-tau)*1000.  If the
collector's clock ran BEHIND the exchange's index clock, a message stamped
`now+k` could carry an _rx_ms at or before now*1000 and the strict gate would
admit a FUTURE print -- a leak introduced by the very mechanism meant to
prevent one.  So: measure min(_rx_ms - time) over the tape.  If it is
positive everywhere, the strict gate cannot admit a future-stamped message.
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from avgfeed import read_hour                    # noqa: E402

files = sorted(glob.glob("C:/kals/kalshi_data/cfbenchmarks_value/*.jsonl.gz"))
lat = []
neg = 0
n = 0
worst = None
for fn in files:
    for (iid, sec, raw, avv, ws, we, lv, rx, lws) in read_hour(fn):
        if rx is None:
            continue
        d = rx - sec * 1000
        n += 1
        lat.append(d)
        if d <= 0:
            neg += 1
            if worst is None or d < worst[0]:
                worst = (d, iid, sec, fn)
lat.sort()
print(f"messages with a receipt clock: {n}")
print(f"  min(_rx_ms - time*1000) = {lat[0]} ms")
print(f"  p01={lat[int(n*0.01)]}  p50={lat[n//2]}  p95={lat[int(n*0.95)]}  "
      f"p99={lat[int(n*0.99)]}  max={lat[-1]} ms")
print(f"  messages received AT OR BEFORE their own exchange timestamp: "
      f"{neg} ({100.0*neg/n:.4f}%)")
if worst:
    print(f"  worst: {worst[0]} ms  {worst[1]} sec={worst[2]}")
print()
if neg == 0:
    print("  PASS -- receipt always strictly follows the exchange timestamp,")
    print("  so the strict gate can never admit a future-stamped print.")
else:
    print("  FAIL -- clock skew exists; the strict gate could admit a print")
    print("  stamped after the decision instant.  Quantify before trusting it.")
