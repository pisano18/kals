"""READ-ONLY GET-only. The series most likely to be ADDED to SERIES_TO_INDEX
next -- would a mis-shaped strike_type slip past pinrun's floor_strike guard?"""
import sys, time, collections
sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
from kauth import get
CANDS = ["KXCRYPTOLEAD15M","KXCRYPTOCOMP15M","KXINX15M","KXNDQ15M",
         "KXTON15M","KXGOLD15M"]
for s in CANDS:
    st, b = get("/markets", {"series_ticker": s, "limit": "50"})
    if st != 200 or not isinstance(b, dict):
        print(f"{s:<18} HTTP {st} {str(b)[:120]}"); time.sleep(0.4); continue
    ms = b.get("markets") or []
    if not ms:
        print(f"{s:<18} no markets returned"); time.sleep(0.4); continue
    c = collections.Counter()
    for m in ms:
        c[(m.get("strike_type"),
           "floor=None" if m.get("floor_strike") is None else "floor=set",
           "cap=None" if m.get("cap_strike") is None else "cap=set",
           m.get("market_type"))] += 1
    print(f"{s:<18} n={len(ms):<3} " + "  ".join(f"{k}x{v}" for k, v in c.items()))
    print(f"{'':18} eg {ms[0].get('ticker')}  title={str(ms[0].get('title'))[:60]}")
    time.sleep(0.4)
