"""READ-ONLY: streaming gap census on the collector's cfbenchmarks tape."""
import gzip, json, glob, os, sys, collections
TAPE = r"C:\kals\kalshi_data\cfbenchmarks_value"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 48
files = sorted(glob.glob(os.path.join(TAPE, "*.jsonl.gz")))[-n:]
last = {}
gaps = collections.defaultdict(list)
cnt = collections.Counter()
bad = []
for fn in files:
    try:
        with gzip.open(fn, "rt", encoding="utf-8", errors="replace") as fh:
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
                    s = int(data["time"]) // 1000
                except Exception:
                    continue
                p = last.get(iid)
                if p is not None and s > p + 1:
                    gaps[iid].append((p, s - p - 1))
                if p is None or s > p:
                    last[iid] = s
                cnt[iid] += 1
    except Exception as e:
        bad.append((os.path.basename(fn), str(e)[:60]))
print(f"files {len(files)}: {os.path.basename(files[0])} .. {os.path.basename(files[-1])}")
for b in bad:
    print("  READ FAILED", b)
print(f"{'index':<14}{'prints':>10}{'gaps':>7}{'>=5s':>7}{'>=30s':>7}{'max':>7}{'lost_s':>9}")
allg = []
for iid in sorted(cnt):
    g = [x[1] for x in gaps[iid]]
    allg += g
    print(f"{iid:<14}{cnt[iid]:>10}{len(g):>7}"
          f"{sum(1 for x in g if x>=5):>7}{sum(1 for x in g if x>=30):>7}"
          f"{(max(g) if g else 0):>7}{sum(g):>9}")
# biggest gaps overall, with timestamps
import time
flat = sorted(((sz, iid, st) for iid, v in gaps.items() for st, sz in v),
              reverse=True)[:15]
print("\nlargest gaps:")
for sz, iid, st in flat:
    print(f"  {sz:>5}s  {iid:<14} after {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(st))}")
