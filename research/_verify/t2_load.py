"""Independent load: BRTI index + BTC replica (wmid AND coinbase mid), whole tape.
Writes a compact cache so later tests do not re-read 700 MB. Read-only on C:\kals."""
import gzip, json, glob, os, calendar, array, math, sys

IDX = r"C:\kals\kalshi_data\cfbenchmarks_value"
REP = r"C:\kals\feed_data\index_replica"
CACHE = r"C:\Users\Joe\AppData\Local\Temp\verify_btc_cache.bin"

def stems():
    s = set()
    for d in (IDX, REP):
        for f in glob.glob(os.path.join(d, "*.jsonl.gz")):
            s.add(os.path.basename(f).split(".")[0])
    return sorted(s)

def ep(st):
    return calendar.timegm((int(st[0:4]),int(st[4:6]),int(st[6:8]),int(st[9:11]),0,0,0,0,0))

def safe(p):
    try:
        f = gzip.open(p, "rt")
    except OSError:
        return
    try:
        for l in f:
            yield l
    except Exception:
        return
    finally:
        try: f.close()
        except Exception: pass

S = stems()
t0 = ep(S[0]); t1 = ep(S[-1]) + 3600
n = t1 - t0 + 2
NAN = float("nan")
idx = array.array("d", [NAN])*n
rep = array.array("d", [NAN])*n
cbm = array.array("d", [NAN])*n
print(f"{len(S)} hours {S[0]}..{S[-1]}  span {n:,}s", flush=True)
ni = nr = nc = 0
for h, st in enumerate(S):
    for l in safe(os.path.join(IDX, st + ".jsonl.gz")):
        if '"BRTI"' not in l:
            continue
        try:
            m = json.loads(l)
            msg = m["msg"]
            if msg.get("index_id") != "BRTI": continue
            d = json.loads(msg["data"])
            sec = int(d["time"])//1000
            i = sec - t0
            if 0 <= i < n:
                idx[i] = float(d["value"]); ni += 1
        except Exception:
            continue
    for l in safe(os.path.join(REP, st + ".jsonl.gz")):
        try:
            m = json.loads(l)
            sec = m.get("sec")
            b = m.get("BTC")
            if sec is None or not isinstance(b, dict): continue
            i = int(sec) - t0
            if not (0 <= i < n): continue
            w = b.get("wmid")
            if w is not None:
                rep[i] = float(w); nr += 1
            pe = b.get("per_ex") or {}
            cb = pe.get("coinbase")
            if cb:
                cbm[i] = (float(cb["b"]) + float(cb["a"]))/2.0; nc += 1
        except Exception:
            continue
    if h % 40 == 0:
        print(f"  {h}/{len(S)} idx={ni:,} rep={nr:,}", flush=True)
print(f"DONE idx={ni:,} rep_wmid={nr:,} rep_cb={nc:,}")
with open(CACHE, "wb") as f:
    f.write(t0.to_bytes(8,"little")); f.write(n.to_bytes(8,"little"))
    idx.tofile(f); rep.tofile(f); cbm.tofile(f)
print("cache:", CACHE, os.path.getsize(CACHE)//1024//1024, "MB")
