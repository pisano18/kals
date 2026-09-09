"""READ-ONLY: does pinrun.IndexWS.sigma() ever return exactly 0.0 on the real
feed, and how close does it get?  Replicates sigma() EXACTLY (window = last 300
HELD seconds, needs >=30 held ticks and >=20 consecutive-second diffs) and
steps it once per held second of tape, per index.  O(n) sliding window."""
import gzip, glob, json, math, os, sys
from collections import defaultdict, Counter
sys.path.insert(0, r"C:\kals-repo\research")
from engine import var_factor

SIGMA_WIN = 300
PAT = sys.argv[1] if len(sys.argv) > 1 else r"C:\kals\kalshi_data\cfbenchmarks_value\2026090[78]T*.jsonl.gz"
FILES = sorted(glob.glob(PAT))
ticks = defaultdict(dict)
lines = 0
for f in FILES:
    try:
        with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                lines += 1
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
    except Exception as e:
        print(f"  READ FAIL {os.path.basename(f)}: {e}")

print(f"files {len(FILES)}  lines {lines}  indices {len(ticks)}")
hdr = (f"{'index':16s} {'secs':>8s} {'windows':>9s} {'sigma==0':>9s} "
       f"{'sigma<1e-9':>10s} {'min sigma>0':>12s} {'longest flat run':>17s}")
print(hdr)
rows = []
for iid in sorted(ticks):
    d = ticks[iid]
    secs = sorted(d)
    n = len(secs)
    vals = [d[s] for s in secs]
    # pair k: between secs[k-1] and secs[k]; valid iff gap == 1
    pair = [None]*n
    for k in range(1, n):
        if secs[k]-secs[k-1] == 1:
            pair[k] = vals[k]-vals[k-1]
    # longest run of consecutive seconds with IDENTICAL value
    run = best = 1
    for k in range(1, n):
        if pair[k] == 0.0:
            run += 1; best = max(best, run)
        else:
            run = 1
    cnt = Counter(); c = 0; s1 = 0.0; s2 = 0.0
    zero = tot = tiny = 0
    minpos = None
    def add(k):
        global c, s1, s2
        v = pair[k]
        if v is None: return
        cnt[v] += 1; c += 1; s1 += v; s2 += v*v
    def rem(k):
        global c, s1, s2
        v = pair[k]
        if v is None: return
        cnt[v] -= 1
        if cnt[v] == 0: del cnt[v]
        c -= 1; s1 -= v; s2 -= v*v
    for k in range(1, min(SIGMA_WIN, n)):
        add(k)
    for j in range(SIGMA_WIN, n+1):
        if j > SIGMA_WIN:
            add(j-1); rem(j-SIGMA_WIN)
        if c < 20:
            continue
        tot += 1
        if len(cnt) == 1:
            zero += 1
            continue
        mu = s1/c
        var = max(0.0, (s2 - c*mu*mu)/(c-1))
        v = math.sqrt(var)
        if v <= 0.0:
            zero += 1
        else:
            if v < 1e-9: tiny += 1
            if minpos is None or v < minpos: minpos = v
    print(f"{iid:16s} {n:8d} {tot:9d} {zero:9d} {tiny:10d} "
          f"{(f'{minpos:.4g}' if minpos is not None else 'n/a'):>12s} {best:17d}")
    rows.append((iid, minpos, zero, tot))
print()
print("SMALLEST OBSERVED sigma -> model sd, and fair() at |mu-K| = 1 tick of that index:")
for iid, mp, z, t in rows:
    if mp is None: continue
    sd30 = mp*math.sqrt(var_factor(29, [1.0]))
    sd3 = mp*math.sqrt(var_factor(2, [1.0]))
    print(f"  {iid:16s} sigma={mp:.4g}  sd(tau=30,r=29)={sd30:.4g}  sd(tau=3,r=2)={sd3:.4g}")
