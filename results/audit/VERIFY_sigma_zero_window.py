"""READ-ONLY: how big is the exposure window for sigma()==0, and how far below
typical does a NEAR-zero sigma go?  Live semantics: W = min(300, len(ticks)),
so W<300 only during the first 300 s after a process start (ticks are never
cleared and the deque holds 1200 s)."""
import gzip, json, glob, math, statistics
from collections import defaultdict

FILES = sorted(glob.glob(r"C:\kals\kalshi_data\cfbenchmarks_value\20260908T*.jsonl.gz"))
ticks = defaultdict(dict)
for f in FILES:
    try:
        with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
            lines = list(fh)
    except EOFError:
        continue
    for ln in lines:
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

DAY = 61200
print(f"  {'index':14s} {'runs>=30s':>10s} {'max_run':>8s} {'start_secs':>11s} "
      f"{'P(start hits)':>14s} {'med_sig300':>11s} {'min_sig300':>11s} {'ratio':>7s}")
for iid in sorted(ticks):
    d = ticks[iid]; secs = sorted(d)
    runs, st = [], secs[0]
    for i in range(1, len(secs)):
        if secs[i] - secs[i-1] == 1 and d[secs[i]] == d[secs[i-1]]:
            continue
        runs.append(secs[i-1] - st + 1); st = secs[i]
    runs.append(secs[-1] - st + 1)
    long_runs = [r for r in runs if r >= 30]
    # a process start at t0 gives sigma()==0 at 30 ticks iff the flat run
    # covers [t0, t0+29]; so each run of length L offers L-29 start seconds.
    start_secs = sum(r - 29 for r in long_runs)
    sig = []
    for j in range(300, len(secs) + 1, 30):
        win = secs[j-300:j]
        dif = [d[win[k]] - d[win[k-1]] for k in range(1, len(win))
               if win[k] - win[k-1] == 1]
        if len(dif) < 20:
            continue
        mu = sum(dif)/len(dif)
        sig.append(math.sqrt(sum((x-mu)**2 for x in dif)/(len(dif)-1)))
    med = statistics.median(sig) if sig else float("nan")
    mn = min(sig) if sig else float("nan")
    print(f"  {iid:14s} {len(long_runs):10d} {max(runs):8d} {start_secs:11d} "
          f"{start_secs/DAY:14.5%} {med:11.4g} {mn:11.4g} {med/mn if mn else 0:7.1f}x")
