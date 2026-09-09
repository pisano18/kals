"""READ-ONLY: locate the long flat runs and ask whether they are a STUCK FEED
(value frozen, timestamps advancing -- the loss case) or a genuinely quiet
index (value really did not move -- the model is then correct and there is no
loss).  Prints the run, its neighbourhood, and the wall-clock receipt times."""
import gzip, json, glob, time
from collections import defaultdict

FILES = sorted(glob.glob(r"C:\kals\kalshi_data\cfbenchmarks_value\20260908T*.jsonl.gz"))
ticks = defaultdict(dict)
rx = defaultdict(dict)      # index -> sec -> collector receipt ts (if present)
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
        iid = m.get("index_id")
        if not iid:
            continue
        data = m.get("data")
        try:
            data = json.loads(data) if isinstance(data, str) else (data or {})
            s = int(data["time"]) // 1000
            ticks[iid][s] = float(data["value"])
            for k in ("ts", "ts_ms", "recv_ts", "rx_ms", "t"):
                if k in d:
                    rx[iid][s] = (k, d[k]); break
        except Exception:
            continue

for iid in ("SOLUSD_RTI", "NEARUSD_RTI"):
    d = ticks[iid]; secs = sorted(d)
    runs = []
    st = secs[0]
    for i in range(1, len(secs)):
        if secs[i] - secs[i-1] == 1 and d[secs[i]] == d[secs[i-1]]:
            continue
        if secs[i-1] - st + 1 >= 20:
            runs.append((st, secs[i-1]))
        st = secs[i]
    if secs[-1] - st + 1 >= 20:
        runs.append((st, secs[-1]))
    print(f"\n{iid}: flat runs >=20 s -> {len(runs)}")
    for a, b in runs:
        n = b - a + 1
        pre = [d.get(a - k) for k in (5, 3, 1)]
        post = [d.get(b + k) for k in (1, 3, 5, 30, 60)]
        print(f"  {n:3d} s  {time.strftime('%H:%M:%S', time.gmtime(a))}Z"
              f" -> {time.strftime('%H:%M:%S', time.gmtime(b))}Z"
              f"  value {d[a]!r}")
        print(f"        before {pre}   after {post}")
        print(f"        rx key sample {rx[iid].get(a)}  {rx[iid].get(b)}")
