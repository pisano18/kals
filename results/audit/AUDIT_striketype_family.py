"""READ-ONLY GET-only. Every market the 11 traded series have EVER exposed via
/markets (all statuses, paged): does the family ever produce a shape that
passes pinrun's `floor_strike is None` guard but is not greater_or_equal?"""
import sys, time, collections
sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
from kauth import get
SER = ["KXBTC15M","KXETH15M","KXSOL15M","KXXRP15M","KXDOGE15M","KXBNB15M",
       "KXBCH15M","KXZEC15M","KXHYPE15M","KXNEAR15M","KXADA15M"]
allc = collections.Counter(); ex = {}
for s in SER:
    cur = ""; pages = 0; n = 0; c = collections.Counter()
    while pages < 4:
        p = {"series_ticker": s, "limit": "1000"}
        if cur: p["cursor"] = cur
        st, b = get("/markets", p)
        if st != 200 or not isinstance(b, dict):
            print(f"{s:<12} HTTP {st}"); break
        ms = b.get("markets") or []
        for m in ms:
            n += 1
            k = (m.get("strike_type"),
                 "floor=None" if m.get("floor_strike") is None else "floor=set",
                 "cap=None" if m.get("cap_strike") is None else "cap=set")
            c[k] += 1; allc[k] += 1; ex.setdefault(k, (s, m.get("ticker"), m.get("status")))
        pages += 1
        nc = b.get("cursor") or ""
        if not nc or not ms: break
        cur = nc; time.sleep(0.3)
    print(f"{s:<12} n={n:<5} " + "  ".join(f"{k}x{v}" for k, v in c.items()))
    time.sleep(0.3)
print("\nAGGREGATE over the traded family")
for k, v in sorted(allc.items(), key=lambda kv: -kv[1]):
    print(f"  {str(k[0]):<20} {k[1]:<11} {k[2]:<9} n={v:<6} eg {ex[k]}")
danger = sum(v for k, v in allc.items()
             if k[1] == "floor=set" and (k[0] != "greater_or_equal" or k[2] != "cap=None"))
print(f"\nSHAPES THAT PASS pinrun's guard BUT ARE NOT greater_or_equal/uncapped: {danger}")
