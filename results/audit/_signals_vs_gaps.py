"""READ-ONLY: did any REAL live signal fall inside a post-gap stale-sigma window?"""
import json, glob, time, calendar, gzip, os, sys
sys.path.insert(0, r"C:\kals-repo\research")
import gzsalvage

TAPE = r"C:\kals\kalshi_data\cfbenchmarks_value"
def epoch(t): return calendar.timegm(time.strptime(t, "%Y-%m-%dT%H:%M:%SZ"))

sigs = []
for fn in sorted(glob.glob(r"C:\kals-repo\results\pinrun-live-*.jsonl")):
    for ln in open(fn, encoding="utf-8"):
        try: d = json.loads(ln)
        except Exception: continue
        if d.get("kind") == "signal": sigs.append(d)
print(f"live signals: {len(sigs)}  "
      f"{sigs[0]['t']} .. {sigs[-1]['t']}")
lo = epoch(sigs[0]["t"]) - 3600
hi = epoch(sigs[-1]["t"]) + 3600

# BRTI second census over the signal span, via gzsalvage (handles broken files)
secs = set()
files = sorted(glob.glob(os.path.join(TAPE, "*.jsonl.gz")))[-40:]
for fn in files:
    for ln in gzsalvage.iter_lines(fn):
        try: d = json.loads(ln)
        except Exception: continue
        m = d.get("msg") or {}
        if m.get("index_id") != "BRTI": continue
        data = m.get("data")
        try:
            data = json.loads(data) if isinstance(data, str) else (data or {})
            s = int(data["time"]) // 1000
        except Exception: continue
        if lo <= s <= hi: secs.add(s)
s = sorted(secs)
print(f"BRTI seconds in span: {len(s)}  "
      f"({time.strftime('%m-%dT%H:%M:%SZ', time.gmtime(s[0]))} .. "
      f"{time.strftime('%m-%dT%H:%M:%SZ', time.gmtime(s[-1]))})")
gaps = [(s[i-1], s[i]-s[i-1]-1) for i in range(1, len(s)) if s[i]-s[i-1] > 1]
print("gaps in the signal span:")
for a, g in gaps:
    print(f"   {g:>5}s ending {time.strftime('%m-%dT%H:%M:%SZ', time.gmtime(a+g+1))}")
hits = 0
for d in sigs:
    ts = epoch(d["t"])
    for a, g in gaps:
        end = a + g + 1
        if end <= ts <= end + 300:
            hits += 1
            print(f"   *** SIGNAL {d['ticker']} at {d['t']} is "
                  f"{ts-end}s after a {g}s gap")
print(f"\nsignals inside a 300 s post-gap window: {hits} of {len(sigs)}")
