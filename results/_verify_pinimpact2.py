"""Two gaps left open by the pinimpact run, closed here.

1. close_of() was checked against fulltape on the NEWEST 3 hours and agreed on
   ZERO prints -- not because it is wrong but because fulltape stops at
   2026-09-06 08:30 UTC and every one of those 453,083 prints is newer.  Check
   it on hours fulltape actually covers.

2. The matched refill control returned nan for the BUY_WINNER population, i.e.
   NO POWER, not "no effect".  Measure why: what share of market-seconds in the
   last 30 s of a decided market have a 16-second window with no trade at all?
"""
import glob
import os
import sys
from collections import defaultdict

sys.path.insert(0, r"C:\kals-repo\research")
from pinimpact import (read_trades, close_of, load_settled, hour_files,
                       quiet_window, HORIZONS)             # noqa: E402

res, closes = load_settled()
print(f"  fulltape knows {len(closes):,} crypto markets, close range "
      f"{min(closes.values())} .. {max(closes.values())}")

# ---- 1. close_of() on hours fulltape covers ------------------------------
allf = sorted(glob.glob(os.path.join(r"C:\kals\kalshi_data", "trade",
                                     "2026*.jsonl.gz")))
hi = max(closes.values())
old = [f for f in allf
       if os.path.basename(f)[:11] <= "20260906T06"][-6:]
print(f"\n  1. close_of() vs fulltape on {len(old)} hour files fulltape "
      f"covers:")
agree = dis = unk = 0
bad = []
for tf in old:
    for tk, ts, _s, _c, _q in read_trades(tf):
        a = closes.get(tk)
        if a is None:
            unk += 1
        elif a == close_of(ts):
            agree += 1
        else:
            dis += 1
            if len(bad) < 3:
                bad.append((tk, ts, a, close_of(ts)))
tot = agree + dis
print(f"     agrees {agree:,}   disagrees {dis:,}   "
      f"({100.0*agree/tot if tot else float('nan'):.4f}% agreement)   "
      f"ticker unknown to fulltape {unk:,}")
for b in bad:
    print(f"     MISMATCH {b}")

# ---- 2. why the BUY_WINNER control is empty -------------------------------
print(f"\n  2. can a no-trade control window even exist at tau 3-30?")
hours = hour_files("trade", 24)
per_tau = defaultdict(lambda: [0, 0, 0, 0])   # tau bucket -> [secs, q1, q5, q15]
for tf in hours:
    traded = defaultdict(set)
    for tk, ts, _s, _c, _q in read_trades(tf):
        traded[tk].add(ts // 1000)
    for tk, tr in traded.items():
        if not tr:
            continue
        close = close_of(max(tr) * 1000)
        for sec in range(close - 900, close):
            tau = close - sec
            key = "3-30" if 3 <= tau <= 30 else (
                "31-90" if tau <= 90 else "91-900")
            row = per_tau[key]
            row[0] += 1
            for i, h in enumerate(HORIZONS):
                if quiet_window(tr, sec, h):
                    row[i + 1] += 1
print(f"     {'tau':>8} {'market-seconds':>16} "
      + "".join(f"{'quiet h=' + str(h):>14}" for h in HORIZONS))
for key in ("3-30", "31-90", "91-900"):
    r = per_tau.get(key)
    if not r:
        continue
    print(f"     {key:>8} {r[0]:>16,} "
          + "".join(f"{100.0*r[i+1]/r[0]:>13.2f}%" for i in range(3)))
print()
print("     A near-zero 'quiet' share at tau 3-30 means the matched control")
print("     CANNOT be built there: the market trades every second.  That is")
print("     no power, not no effect, and the (b) BUY_WINNER row must be read")
print("     as a RAW change that still contains the drift toward settlement.")
