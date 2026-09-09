"""READ-ONLY: can pinrun's sigma() return 0 (or near-0) on the real feed?

fair() does:   sd = sigma * sqrt(var_factor(r,[1.0]));  if sd <= 0: return
1.0 or 0.0  -- infinite confidence. sigma() returns 0.0, not None, when the
last 300 one-second index prints never change. This walks the real tape and
counts the 300-second windows where that happens, per index.
"""
import gzip, json, math, os, sys, glob
from collections import defaultdict
sys.path.insert(0, r"C:\kals-repo\research")
from engine import var_factor

FILES = sorted(glob.glob(r"C:\kals\kalshi_data\cfbenchmarks_value\20260908T1[4-6].jsonl.gz"))
ticks = defaultdict(dict)
for f in FILES:
    with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            try:
                d = json.loads(ln)
            except Exception:
                continue
            m = d.get("msg") or {}
            if not m.get("index_id"):
                continue
            data = m.get("data")
            try:
                data = json.loads(data) if isinstance(data, str) else (data or {})
                ticks[m["index_id"]][int(data["time"]) // 1000] = float(data["value"])
            except Exception:
                continue
print(f"  files {len(FILES)}   indices {len(ticks)}")
print(f"  {'index':14s} {'ticks':>7s} {'zero-sigma wins':>16s} {'min sigma>0':>12s} "
      f"{'max identical run':>18s}")
for iid in sorted(ticks):
    d = ticks[iid]
    secs = sorted(d)
    zero = 0
    total = 0
    minpos = None
    run = best_run = 1
    for i in range(1, len(secs)):
        if secs[i] - secs[i-1] == 1 and d[secs[i]] == d[secs[i-1]]:
            run += 1
            best_run = max(best_run, run)
        else:
            run = 1
    for j in range(300, len(secs)):
        win = secs[j-300:j]
        diffs = [d[win[k]] - d[win[k-1]] for k in range(1, len(win))
                 if win[k] - win[k-1] == 1]
        if len(diffs) < 20:
            continue
        total += 1
        mu = sum(diffs)/len(diffs)
        v = math.sqrt(sum((x-mu)**2 for x in diffs)/(len(diffs)-1))
        if v <= 0:
            zero += 1
        elif minpos is None or v < minpos:
            minpos = v
    print(f"  {iid:14s} {len(secs):7d} {zero:8d}/{total:<7d} "
          f"{(f'{minpos:.3g}' if minpos else 'n/a'):>12s} {best_run:18d}")

print()
print("  what a zero sigma does to fair():")
sd = 0.0
print(f"    sd = 0 -> fair() returns {1.0 if 1 else 0} or 0.0 with NO gate "
      f"between it and the trade (pinrun.fair, 'if sd <= 0').")
print("  and what a TINY sigma does at tau=30 (r=29 prints left):")
for s in (1e-9, 1e-6, 1e-4, 1e-2):
    print(f"    sigma={s:9.0e} -> sd={s*math.sqrt(var_factor(29,[1.0])):.3e}")
