"""READ-ONLY: census of BIT-IDENTICAL flat runs in each CF index over the whole
tape.  A flat run of length L lets pinrun's sigma() return exactly 0.0 only if
the process's whole tick history for that index is inside it -- i.e. only in
the first ~L seconds after a restart.  Counts runs >= 30 s (the sigma() floor)."""
import gzip, glob, json, sys
from collections import defaultdict
FILES = sorted(glob.glob(r"C:\kals\kalshi_data\cfbenchmarks_value\*.jsonl.gz"))
ticks = defaultdict(dict)
for f in FILES:
    try:
        with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                try: d = json.loads(ln)
                except Exception: continue
                m = d.get("msg") or {}
                iid = m.get("index_id")
                if not iid: continue
                data = m.get("data")
                try:
                    data = json.loads(data) if isinstance(data, str) else (data or {})
                    ticks[iid][int(data["time"]) // 1000] = float(data["value"])
                except Exception: continue
    except Exception: pass
TOT = 0
print(f"{'index':16s} {'secs':>9s} {'runs>=30s':>10s} {'runs>=60s':>10s} "
      f"{'sec in runs>=30':>16s} {'frac of tape':>13s} {'longest':>8s}")
grand = defaultdict(int)
for iid in sorted(ticks):
    d = ticks[iid]; secs = sorted(d); n = len(secs)
    vals = [d[s] for s in secs]
    runs = []
    run = 1
    for k in range(1, n):
        if secs[k]-secs[k-1] == 1 and vals[k] == vals[k-1]:
            run += 1
        else:
            if run >= 2: runs.append(run)
            run = 1
    if run >= 2: runs.append(run)
    r30 = [r for r in runs if r >= 30]
    r60 = [r for r in runs if r >= 60]
    sec30 = sum(r30)
    print(f"{iid:16s} {n:9d} {len(r30):10d} {len(r60):10d} {sec30:16d} "
          f"{sec30/max(1,n):12.6%} {max(runs or [0]):8d}")
    grand["n"] += n; grand["r30"] += len(r30); grand["sec30"] += sec30
print(f"\nALL INDICES: {grand['n']} index-seconds, {grand['r30']} flat runs >=30 s, "
      f"{grand['sec30']} seconds inside them = {grand['sec30']/max(1,grand['n']):.6%} of tape")
