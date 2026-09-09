"""READ-ONLY GET-only. Platform-wide strike_type -> field convention.
Question: when strike_type is a SIGN-INVERTING one (less / less_or_equal /
between), is floor_strike None?  pinrun already skips floor_strike None."""
import sys, time, collections
sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
from kauth import get

seen = collections.Counter()
ex = {}
cur = ""
pages = 0
seen_cursors = set()
while pages < 25:
    p = {"status": "open", "limit": "1000"}
    if cur:
        p["cursor"] = cur
    st, b = get("/markets", p)
    if st != 200 or not isinstance(b, dict):
        print("  HTTP", st, str(b)[:200]); break
    ms = b.get("markets") or []
    for m in ms:
        k = (m.get("strike_type"),
             "floor=None" if m.get("floor_strike") is None else "floor=set",
             "cap=None" if m.get("cap_strike") is None else "cap=set")
        seen[k] += 1
        ex.setdefault(k, m.get("ticker"))
    pages += 1
    nc = b.get("cursor") or ""
    if not nc or nc in seen_cursors or not ms:
        break
    seen_cursors.add(nc)
    cur = nc
    time.sleep(0.35)
print(f"pages {pages}  markets {sum(seen.values())}")
for k, v in sorted(seen.items(), key=lambda kv: -kv[1]):
    print(f"  {str(k[0]):<20} {k[1]:<11} {k[2]:<9} n={v:<6} eg {ex[k]}")
