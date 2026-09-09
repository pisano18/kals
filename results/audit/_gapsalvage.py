"""READ-ONLY: re-read the unreadable hour with gzsalvage and re-time the gap."""
import sys, os, json, time
sys.path.insert(0, r"C:\kals-repo\research")
import gzsalvage
fn = r"C:\kals\kalshi_data\cfbenchmarks_value\20260906T14.jsonl.gz"
st = {}
secs = []
for ln in gzsalvage.iter_lines(fn, st):
    try: d = json.loads(ln)
    except Exception: continue
    m = d.get("msg") or {}
    if m.get("index_id") != "BRTI": continue
    data = m.get("data")
    try:
        data = json.loads(data) if isinstance(data,str) else (data or {})
        secs.append(int(data["time"])//1000)
    except Exception: continue
secs = sorted(set(secs))
print("gzsalvage stats:", st)
print("BRTI seconds recovered:", len(secs))
if secs:
    print("span:", time.strftime('%H:%M:%SZ', time.gmtime(secs[0])), "->",
          time.strftime('%H:%M:%SZ', time.gmtime(secs[-1])))
    gaps = [(secs[i-1], secs[i]-secs[i-1]-1) for i in range(1,len(secs))
            if secs[i]-secs[i-1] > 1]
    print("gaps inside this hour:")
    for a,g in gaps:
        print(f"   {g:>5}s after {time.strftime('%H:%M:%SZ', time.gmtime(a))}")
