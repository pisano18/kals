#!/usr/bin/env python3
# VERSION: 2026-09-08-ep1
"""earlypull.py -- READ-ONLY settlement pull with FULL strike precision.

fulltape/markets.json stops at 2026-09-06 and its `strike` is a truncated
float. The arithmetic lock is a comparison of a required index move against
the distance to the strike, so a truncated strike is a corrupted input --
and round_digits (2 for BTC/ETH/BNB, 7 for DOGE) sets the effective strike
K_eff = floor_strike - 0.5*10^-d. Both are read from custom_strike here and
never assumed.

GET only, via kauth. Writes ONE new file: early_cache/settled.json.
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "early_cache", "settled.json")
SERIES = ["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
          "KXBNB15M", "KXBCH15M", "KXZEC15M", "KXHYPE15M", "KXNEAR15M",
          "KXADA15M"]
sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
from kauth import get                                       # noqa: E402


def main():
    out = {}
    for s in SERIES:
        cur, n, pages = "", 0, 0
        while True:
            p = {"series_ticker": s, "status": "settled", "limit": "1000"}
            if cur:
                p["cursor"] = cur
            st, b = get("/markets", p)
            if st != 200 or not isinstance(b, dict):
                print(f"  {s}: HTTP {st} {str(b)[:120]}")
                break
            ms = b.get("markets") or []
            for m in ms:
                cs = m.get("custom_strike") or {}
                fs = cs.get("floor_strike")
                if fs is None:
                    fs = m.get("floor_strike")
                out[m["ticker"]] = {
                    "series": s,
                    "result": m.get("result"),
                    "close_ts": m.get("close_time"),
                    "floor_strike": fs,
                    "round_digits": cs.get("round_digits"),
                    "expiration_value": m.get("expiration_value"),
                }
            n += len(ms)
            pages += 1
            cur = b.get("cursor") or ""
            if not cur or not ms or pages > 60:
                break
            time.sleep(0.12)
        print(f"  {s}: {n} settled markets, {pages} pages")
    with open(OUT, "w") as f:
        json.dump(out, f)
    print(f"\n  wrote {len(out):,} markets -> {OUT}")
    # what precision did we actually get?
    rd = {}
    for t, m in out.items():
        rd.setdefault(m["series"], set()).add(m["round_digits"])
    for s in sorted(rd):
        print(f"    {s:<12} round_digits {sorted(x for x in rd[s] if x is not None)}")


if __name__ == "__main__":
    main()
