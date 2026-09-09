"""READ-ONLY. GET only. No orders, no writes outside stdout.

Two questions the strike_type finding turns on:
 1. LIVE: what strike_type / cap_strike do the 11 SERIES_TO_INDEX series
    actually return right now, over EVERY open market (not just [0])?
 2. CONVENTION: platform-wide, when strike_type is NOT greater_or_equal,
    is floor_strike None?  pinrun's universe pass already does
    `if not ct or sk is None: continue`, so if 'less'/'less_or_equal'
    markets carry floor_strike None that guard already blocks the
    sign-inverting case and the finding cannot invert a sign.
"""
import sys, time, collections
sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
from kauth import get

SER = ["KXBTC15M","KXETH15M","KXSOL15M","KXXRP15M","KXDOGE15M","KXBNB15M",
       "KXBCH15M","KXZEC15M","KXHYPE15M","KXNEAR15M","KXADA15M"]

print("=== 1. LIVE, all open markets in the traded universe ===")
tot = 0
bad = 0
for s in SER:
    st, b = get("/markets", {"series_ticker": s, "status": "open", "limit": "20"})
    if st != 200 or not isinstance(b, dict):
        print(f"{s:<12} HTTP {st}")
        time.sleep(0.6); continue
    ms = b.get("markets") or []
    if not ms:
        print(f"{s:<12} no open markets")
        time.sleep(0.6); continue
    c = collections.Counter()
    for m in ms:
        tot += 1
        key = (m.get("strike_type"), m.get("cap_strike"),
               m.get("market_type"), m.get("floor_strike") is None)
        c[key] += 1
        if m.get("strike_type") != "greater_or_equal" or m.get("cap_strike") is not None:
            bad += 1
    print(f"{s:<12} n={len(ms):<3} " +
          "  ".join(f"{k}x{v}" for k, v in c.items()))
    time.sleep(0.6)
print(f"  TOTAL open markets in universe: {tot}; not greater_or_equal or capped: {bad}")

print()
print("=== 2. CONVENTION: platform-wide open markets, strike_type vs fields ===")
seen = collections.Counter()
cur = ""
pages = 0
while pages < 6:
    p = {"status": "open", "limit": "1000"}
    if cur:
        p["cursor"] = cur
    st, b = get("/markets", p)
    if st != 200 or not isinstance(b, dict):
        print("  HTTP", st); break
    ms = b.get("markets") or []
    for m in ms:
        seen[(m.get("strike_type"),
              "floor=None" if m.get("floor_strike") is None else "floor=set",
              "cap=None" if m.get("cap_strike") is None else "cap=set")] += 1
    pages += 1
    cur = b.get("cursor") or ""
    if not cur or not ms:
        break
    time.sleep(0.6)
print(f"  pages fetched: {pages}, markets: {sum(seen.values())}")
for k, v in sorted(seen.items(), key=lambda kv: -kv[1]):
    print(f"    {str(k[0]):<22} {k[1]:<12} {k[2]:<10} n={v}")
