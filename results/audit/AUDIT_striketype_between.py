"""READ-ONLY GET-only. Hunt for a 'between' / 'less' market to learn whether
floor_strike is populated for the sign-inverting strike types."""
import sys, time, collections
sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
from kauth import get
CANDS = ["KXHIGHNY","KXHIGHCHI","KXHIGHMIA","KXBTCD","KXETHD","KXCPIYOY",
         "KXFEDDECISION","KXBTCMAXY","KXNASDAQ100Y","KXINXY","KXAAAY"]
found = collections.Counter(); ex = {}
for s in CANDS:
    st, b = get("/markets", {"series_ticker": s, "limit": "200"})
    if st != 200 or not isinstance(b, dict):
        print(f"{s:<16} HTTP {st}"); time.sleep(0.4); continue
    ms = b.get("markets") or []
    c = collections.Counter()
    for m in ms:
        k = (m.get("strike_type"),
             "floor=None" if m.get("floor_strike") is None else "floor=set",
             "cap=None" if m.get("cap_strike") is None else "cap=set")
        c[k] += 1; found[k] += 1; ex.setdefault(k, m.get("ticker"))
    print(f"{s:<16} n={len(ms):<4} " + "  ".join(f"{k}x{v}" for k, v in c.items()))
    time.sleep(0.4)
print("\nAGGREGATE")
for k, v in sorted(found.items(), key=lambda kv: -kv[1]):
    print(f"  {str(k[0]):<20} {k[1]:<11} {k[2]:<9} n={v:<6} eg {ex[k]}")
