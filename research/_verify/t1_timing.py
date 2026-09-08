"""Independent re-derivation of the timing claim, from raw files only.
Read-only. Streams one hour at a time."""
import gzip, json, glob, os, sys, statistics as st
from collections import Counter, defaultdict

IDX = r"C:\kals\kalshi_data\cfbenchmarks_value"
REP = r"C:\kals\feed_data\index_replica"
OBD = r"C:\kals\kalshi_data\orderbook_delta"

def lines(p):
    try:
        with gzip.open(p, "rt") as f:
            for l in f:
                yield l
    except (OSError, EOFError, Exception):
        return

def safe_lines(p):
    try:
        f = gzip.open(p, "rt")
    except OSError:
        return
    try:
        for l in f:
            yield l
    except (EOFError, Exception):
        return
    finally:
        try: f.close()
        except Exception: pass

def pct(xs, ps):
    xs = sorted(xs)
    return {p: xs[min(len(xs)-1, int(len(xs)*p/100))] for p in ps}

stems = sorted(os.path.basename(x).split(".")[0]
               for x in glob.glob(os.path.join(IDX, "*.jsonl.gz")))
# drop the newest (live truncated) hour
stems = [s for s in stems if s < stems[-1]]
sample = sys.argv[1:] or [stems[10], stems[len(stems)//2], stems[-2]]
print("hours sampled:", sample, "  (of", len(stems), "complete hours)")

for stem in sample:
    print("="*78)
    print("HOUR", stem)
    # --- index: BRTI only ---
    idx_rx = {}          # sec -> rx_ms
    idx_val = {}
    cf_lat = []
    times = []
    n_all = 0
    dupes = 0
    for l in safe_lines(os.path.join(IDX, stem + ".jsonl.gz")):
        try:
            m = json.loads(l)
        except Exception:
            continue
        n_all += 1
        msg = m.get("msg") or {}
        if msg.get("index_id") != "BRTI":
            continue
        try:
            d = json.loads(msg["data"])
            tms = int(d["time"]); val = float(d["value"])
        except Exception:
            continue
        rx = m.get("_rx_ms")
        if rx is None: continue
        sec = tms//1000
        if sec in idx_rx: dupes += 1
        idx_rx[sec] = float(rx)
        idx_val[sec] = val
        cf_lat.append(float(rx) - tms)
        times.append(tms)
    times.sort()
    gaps_ms = Counter(times[i+1]-times[i] for i in range(len(times)-1))
    print(f"  BRTI prints {len(idx_rx):,}  (all-index records {n_all:,}) dup-sec {dupes}")
    print(f"  CF `time` spacing between consecutive prints (ms): "
          f"{sorted(gaps_ms.items(), key=lambda kv:-kv[1])[:4]}")
    print(f"  CF time%1000 distinct values: {sorted(Counter(t%1000 for t in times).items())[:6]}")
    q = pct(cf_lat, [1,5,25,50,75,95,99])
    print(f"  CF stamp -> our _rx_ms (ms): p1 {q[1]:.0f} p5 {q[5]:.0f} p25 {q[25]:.0f} "
          f"MED {q[50]:.0f} p75 {q[75]:.0f} p95 {q[95]:.0f} p99 {q[99]:.0f}  min {min(cf_lat):.0f}")

    # --- replica ---
    rep_rx = {}
    rep_lat = []
    nex = Counter()
    for l in safe_lines(os.path.join(REP, stem + ".jsonl.gz")):
        try:
            m = json.loads(l)
        except Exception:
            continue
        sec = m.get("sec"); rx = m.get("_rx")
        if sec is None or rx is None: continue
        b = m.get("BTC")
        if not isinstance(b, dict) or b.get("wmid") is None: continue
        rep_rx[int(sec)] = float(rx)*1000.0
        rep_lat.append((float(rx)-int(sec))*1000.0)
        nex[int(b.get("n_ex",0))] += 1
    q = pct(rep_lat, [1,25,50,75,95,99])
    print(f"  replica BTC seconds {len(rep_rx):,}  top-of-sec -> stamp (ms): "
          f"p1 {q[1]:.1f} p25 {q[25]:.1f} MED {q[50]:.1f} p75 {q[75]:.1f} p95 {q[95]:.1f} p99 {q[99]:.1f}")
    print(f"  n_ex distribution: {dict(sorted(nex.items()))}")

    # --- the gap, same second ---
    g = [idx_rx[s]-rep_rx[s] for s in idx_rx if s in rep_rx]
    q = pct(g, [1,5,25,50,75,95,99])
    neg = sum(1 for x in g if x <= 0)
    print(f"  GAP index_rx - replica_rx, n={len(g):,}: p1 {q[1]:.0f} p5 {q[5]:.0f} p25 {q[25]:.0f} "
          f"MED {q[50]:.0f} p75 {q[75]:.0f} p95 {q[95]:.0f} p99 {q[99]:.0f}   replica-not-first: {neg}")

    # --- ARTEFACT TEST: is CF lag inflated by OUR OWN collector load? ---
    load = Counter()
    try:
        for l in safe_lines(os.path.join(OBD, stem + ".jsonl.gz")):
            i = l.find('"_rx_ms":')
            if i < 0: continue
            j = l.find('}', i)
            try:
                load[int(l[i+9:i+9+13])//1000] += 1
            except Exception:
                continue
    except Exception as e:
        print("  (orderbook_delta unavailable:", e, ")")
    if load:
        buckets = defaultdict(list)
        for s, rx in idx_rx.items():
            n = load.get(s, 0)
            lat = rx - s*1000.0     # CF time == top of second (checked above)
            if n == 0: b = "0"
            elif n <= 5: b = "1-5"
            elif n <= 20: b = "6-20"
            elif n <= 50: b = "21-50"
            elif n <= 150: b = "51-150"
            else: b = ">150"
            buckets[b].append(lat)
        print("  ARTEFACT TEST -- CF index latency vs OUR collector's orderbook_delta load in the same second:")
        print("    deltas/sec      n    med lat   p95 lat")
        for b in ["0","1-5","6-20","21-50","51-150",">150"]:
            v = buckets.get(b)
            if not v: continue
            vq = pct(v,[50,95])
            print(f"    {b:>10} {len(v):>7,}  {vq[50]:>8.0f}  {vq[95]:>8.0f}")
