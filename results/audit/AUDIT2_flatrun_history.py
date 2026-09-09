"""READ-ONLY: over the WHOLE tape, how long does a CF index value ever stay
frozen, and how dense are consecutive-second prints inside sigma()'s window?
Both are needed for sigma() to be able to return exactly 0.0."""
import gzip, glob, json, os, sys
from collections import defaultdict
PAT = r"C:\kals\kalshi_data\cfbenchmarks_value\*.jsonl.gz"
FILES = sorted(glob.glob(PAT))
ticks = defaultdict(dict)
bad = 0
for f in FILES:
    try:
        with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                m = d.get("msg") or {}
                iid = m.get("index_id")
                if not iid:
                    continue
                data = m.get("data")
                try:
                    data = json.loads(data) if isinstance(data, str) else (data or {})
                    ticks[iid][int(data["time"]) // 1000] = float(data["value"])
                except Exception:
                    continue
    except Exception:
        bad += 1
print(f"files {len(FILES)}  truncated/unreadable {bad}  indices {len(ticks)}")
print(f"{'index':16s} {'secs':>9s} {'span_h':>8s} {'longest flat run':>17s} "
      f"{'min diffs/300win':>17s} {'wins diffs<50':>14s} {'sigma==0 possible':>18s}")
for iid in sorted(ticks):
    d = ticks[iid]; secs = sorted(d); n = len(secs)
    vals = [d[s] for s in secs]
    run = best = 1
    for k in range(1, n):
        if secs[k]-secs[k-1] == 1 and vals[k] == vals[k-1]:
            run += 1; best = max(best, run)
        else:
            run = 1
    # sliding count of consecutive-second pairs inside the last-300-held window
    ok = [1 if (k >= 1 and secs[k]-secs[k-1] == 1) else 0 for k in range(n)]
    c = sum(ok[1:min(300, n)])
    mind = None; low = 0; win = 0
    for j in range(300, n+1):
        if j > 300:
            c += ok[j-1] - ok[j-300+0] if False else 0
        # recompute correctly: pairs k in [j-299, j-1]
        if j == 300:
            c = sum(ok[1:300])
        else:
            c += ok[j-1] - ok[j-300]
        win += 1
        if c < 20: continue
        if mind is None or c < mind: mind = c
        if c < 50: low += 1
    span = (secs[-1]-secs[0])/3600.0
    poss = "YES" if best >= 21 and (mind is not None and mind <= best) else "no"
    print(f"{iid:16s} {n:9d} {span:8.1f} {best:17d} {str(mind):>17s} {low:14d} {poss:>18s}")
