"""READ-ONLY: show the longest bit-identical flat runs in SOLUSD_RTI and
NEARUSD_RTI, second by second, so the census number can be checked by hand."""
import gzip, glob, json
from collections import defaultdict
FILES = sorted(glob.glob(r"C:\kals\kalshi_data\cfbenchmarks_value\20260908T*.jsonl.gz"))
ticks = defaultdict(dict)
for f in FILES:
    try:
        with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                try: d = json.loads(ln)
                except Exception: continue
                m = d.get("msg") or {}
                iid = m.get("index_id")
                if iid not in ("SOLUSD_RTI", "NEARUSD_RTI", "BRTI"): continue
                data = m.get("data")
                try:
                    data = json.loads(data) if isinstance(data, str) else (data or {})
                    ticks[iid][int(data["time"]) // 1000] = float(data["value"])
                except Exception: continue
    except Exception: pass
import time
for iid in ("SOLUSD_RTI", "NEARUSD_RTI", "BRTI"):
    d = ticks[iid]; secs = sorted(d); vals = [d[s] for s in secs]
    runs = []; run = 1; start = 0
    for k in range(1, len(secs)):
        if secs[k]-secs[k-1] == 1 and vals[k] == vals[k-1]:
            run += 1
        else:
            if run >= 2: runs.append((run, secs[start]))
            run = 1; start = k
    if run >= 2: runs.append((run, secs[start]))
    runs.sort(reverse=True)
    print(f"\n{iid}: {len(secs)} secs today, top 5 flat runs "
          f"{[r[0] for r in runs[:5]]}")
    if not runs: continue
    L, s0 = runs[0]
    print(f"  longest run {L}s starting {time.strftime('%H:%M:%SZ', time.gmtime(s0))} "
          f"value {d[s0]!r}")
    for s in range(s0 - 3, s0 + min(L, 6) + 3):
        if s in d:
            print(f"    {time.strftime('%H:%M:%SZ', time.gmtime(s))}  {d[s]!r}")
    print("    ...")
    for s in range(s0 + L - 3, s0 + L + 4):
        if s in d:
            print(f"    {time.strftime('%H:%M:%SZ', time.gmtime(s))}  {d[s]!r}")
    # how many distinct values does this index ever take today?
    print(f"  distinct values today: {len(set(d.values()))} over {len(secs)} seconds")
