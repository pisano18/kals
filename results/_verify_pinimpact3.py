"""Why did the matched refill control return nan for BUY_WINNER?

Quiet windows exist at tau 3-30 (44-63% of market-seconds), so that is not the
reason.  The control also needs the SAME stratum as the sweep: same taker side,
tau bucket 3-30, and a base cost in the same 5c bucket -- which for BUY_WINNER
is 95-100c.  So the question is whether a quiet market-second at tau 3-30 ever
has the near-certain side QUOTED at all.
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, r"C:\kals-repo\research")
from pinimpact import (read_trades, read_ticker, close_of, hour_files,
                       quiet_window, cost_at, stratum_of, event_delta,
                       DATA, HORIZONS)                     # noqa: E402
import glob                                                # noqa: E402

tickby = {os.path.basename(p)[:11]: p for p in sorted(glob.glob(
    os.path.join(DATA, "ticker", "2026*.jsonl.gz")))}

n_ctl = defaultdict(int)      # (tau bucket, price bucket) -> control obs
n_sw = defaultdict(int)       # same, for sweeps
quoted = [0, 0]               # [quiet tau-3-30 rows, of which cost >= 95c]

for tf in hour_files("trade", 12):
    stamp = os.path.basename(tf)[:11]
    if stamp not in tickby:
        continue
    top = defaultdict(list)
    for row in read_ticker(tickby[stamp]):
        top[row[0]].append(row)
    for v in top.values():
        v.sort(key=lambda r: r[1])
    traded = defaultdict(set)
    groups = defaultdict(list)
    for tk, ts, side, cost, q in read_trades(tf):
        traded[tk].add(ts // 1000)
        groups[(tk, ts)].append((side, cost, q))

    for tk, rows in top.items():
        tr = traded.get(tk, set())
        for r in rows:
            ts = r[1]
            sec = ts // 1000
            tau = close_of(ts) - ts / 1000.0
            if not (3 <= tau <= 30):
                continue
            if sec in tr or (sec - 1) in tr:
                continue
            if not quiet_window(tr, sec, 1):
                continue
            for side in ("yes", "no"):
                ed = event_delta(rows, ts, side, 1)
                if ed is None:
                    continue
                base = ed[0]
                quoted[0] += 1
                if base >= 95.0:
                    quoted[1] += 1
                st = stratum_of(side, tau, base)
                if st:
                    n_ctl[st[2]] += 1

    for (tk, ts), prints in groups.items():
        tau = close_of(ts) - ts / 1000.0
        if not (3 <= tau <= 30):
            continue
        rows = top.get(tk)
        if not rows:
            continue
        side = prints[0][0]
        ed = event_delta(rows, ts, side, 1)
        if ed is None:
            continue
        st = stratum_of(side, tau, ed[0])
        if st:
            n_sw[st[2]] += 1

print(f"\n  quiet tau-3-30 control observations with a quoted cost: "
      f"{quoted[0]:,}")
print(f"  of which the cost is >= 95c (the BUY_WINNER stratum): "
      f"{quoted[1]:,}  ({100.0*quoted[1]/max(quoted[0],1):.3f}%)")
print(f"\n  {'5c price bucket':>16} {'control obs':>14} {'sweep obs':>12}")
for b in sorted(set(n_ctl) | set(n_sw)):
    print(f"  {b:>16} {n_ctl.get(b, 0):>14,} {n_sw.get(b, 0):>12,}")
