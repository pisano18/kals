"""READ-ONLY adversarial re-check of the sigma==0 finding.

The original audit tested only the STEADY-STATE window (300 held ticks).
pinrun.IndexWS.sigma() also fires with as few as 30 held ticks / 20 diffs --
the regime for the first ~5 minutes after every process start, and strictly
EASIER to zero out.  sigma()==0 iff every consecutive-second diff in the
window is identical, i.e. the held prints form an exact arithmetic
progression.  Measure per index over a full day of tape.
"""
import gzip, json, glob, sys, math
from collections import defaultdict

FILES = sorted(glob.glob(r"C:\kals\kalshi_data\cfbenchmarks_value\20260908T*.jsonl.gz"))
ticks = defaultdict(dict)
for f in FILES:
    lines = []
    try:
        with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
            lines = list(fh)
    except EOFError:
        print(f"  (skipped in-progress file {f[-22:]}: truncated gzip)")
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

print(f"  files {len(FILES)}  indices {len(ticks)}")
print(f"  {'index':14s} {'ticks':>8s} {'span_s':>8s} {'gaps':>6s} "
      f"{'AP_run':>7s} {'flat_run':>9s} {'min_sig_30':>11s} {'min_sig_300':>12s}")

for iid in sorted(ticks):
    d = ticks[iid]
    secs = sorted(d)
    span = secs[-1] - secs[0] + 1
    gaps = sum(1 for i in range(1, len(secs)) if secs[i] - secs[i-1] != 1)
    ap = best_ap = 1
    flat = best_flat = 1
    for i in range(1, len(secs)):
        if secs[i] - secs[i-1] != 1:
            ap = flat = 1
            continue
        dv = d[secs[i]] - d[secs[i-1]]
        if ap >= 2 and secs[i-1] - secs[i-2] == 1 and \
           (d[secs[i-1]] - d[secs[i-2]]) == dv:
            ap += 1
        else:
            ap = 2
        best_ap = max(best_ap, ap)
        flat = flat + 1 if dv == 0.0 else 1
        best_flat = max(best_flat, flat)

    def min_sigma(W):
        lo = None
        for j in range(W, len(secs) + 1):
            win = secs[j-W:j]
            diffs = [d[win[k]] - d[win[k-1]] for k in range(1, len(win))
                     if win[k] - win[k-1] == 1]
            if len(diffs) < 20:
                continue
            mu = sum(diffs) / len(diffs)
            v = math.sqrt(sum((x-mu)**2 for x in diffs) / (len(diffs)-1))
            if lo is None or v < lo:
                lo = v
        return lo

    m30, m300 = min_sigma(30), min_sigma(300)
    print(f"  {iid:14s} {len(secs):8d} {span:8d} {gaps:6d} {best_ap:7d} "
          f"{best_flat:9d} {(f'{m30:.3g}' if m30 is not None else 'n/a'):>11s} "
          f"{(f'{m300:.3g}' if m300 is not None else 'n/a'):>12s}")
print()
print("  sigma()==0 needs len(ticks)>=30, >=20 consecutive-second diffs, and")
print("  EVERY such diff identical.  With zero gaps that is an exact")
print("  arithmetic-progression run of >=30 consecutive seconds.")
