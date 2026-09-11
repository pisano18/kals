#!/usr/bin/env python3
# VERSION: 2026-09-11-st1
"""pinsettle.py -- refresh settlements WITHOUT pulling the trade tape.

WHY. kalshi_fulltape.py refreshes settlements by downloading every trade of
every market and holding them in memory. On 2026-09-11 it was killed by the
OS at market 600 of 1,200 with 3.5 million trades resident, while the
collector -- which outranks every job here -- was running. It also DUMPS only
what it fetched, so a smaller run would overwrite 14,161 markets of history
with a few thousand.

THIS FILE pulls only the market records (settled status, result, close, the
EXACT strike from custom_strike, round_digits, and expiration_value = the
settlement level) and MERGES them into fulltape/markets.json: new tickers are
added, existing ones gain a settle level if they lacked one, nothing is ever
removed. The old file is copied aside first and the new one is written
atomically. Memory: a few MB.

THE STRIKE TRAP, again: the top-level floor_strike is truncated to the
display precision (DOGE 0.084564 vs the real 0.0845648). custom_strike
.floor_strike is exact and is what is stored.
"""
import argparse
import json
import os
import shutil
import sys
import time
import calendar

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
FULLTAPE = r"C:\kals\fulltape\markets.json"
SERIES = ["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
          "KXBNB15M", "KXZEC15M", "KXHYPE15M", "KXNEAR15M", "KXADA15M",
          "KXBCH15M", "KXTON15M"]


def record(m):
    """One market record in fulltape's shape, or None if not settled."""
    if m.get("status") not in ("settled", "finalized"):
        return None
    res = m.get("result")
    if res not in ("yes", "no"):
        return None
    cs = m.get("custom_strike") or {}
    try:
        strike = float(cs.get("floor_strike") if cs.get("floor_strike")
                       is not None else m["floor_strike"])
    except Exception:
        return None
    out = {"ticker": m["ticker"], "series": m["ticker"].split("-")[0],
           "strike": strike,
           "close": float(calendar.timegm(time.strptime(
               m["close_time"], "%Y-%m-%dT%H:%M:%SZ"))),
           "result": res}
    ev = m.get("expiration_value")
    if ev not in (None, ""):
        try:
            out["settle"] = float(ev)
        except Exception:
            pass
    if cs.get("round_digits") is not None:
        try:
            out["round_digits"] = int(cs["round_digits"])
        except Exception:
            pass
    return out


def selftest():
    print("SELF-TEST -- pinsettle")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)
    m = {"ticker": "KXDOGE15M-26SEP110900-00", "status": "finalized",
         "result": "yes", "close_time": "2026-09-11T13:00:00Z",
         "floor_strike": 0.084564,
         "custom_strike": {"floor_strike": "0.0845648", "round_digits": "7"},
         "expiration_value": "0.0851030"}
    r = record(m)
    ck(r is not None and r["strike"] == 0.0845648,
       f"the EXACT strike is stored (0.0845648), not the truncated 0.084564")
    ck(r["settle"] == 0.085103 and r["round_digits"] == 7 and
       r["result"] == "yes" and r["series"] == "KXDOGE15M",
       "settle level, round_digits, result and series carried")
    ck(r["close"] == 1789131600.0, "close_time -> epoch, UTC")
    ck(record(dict(m, status="open")) is None, "an open market is skipped")
    ck(record(dict(m, result=None)) is None, "a market without a result is skipped")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    return not f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--pages", type=int, default=6,
                    help="max pages of 200 per series (newest first)")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")
    sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
    from kauth import get                                   # read-only GET
    d = json.load(open(FULLTAPE, encoding="utf-8"))
    have = {r["ticker"]: (k, i) for k, v in d.items() for i, r in enumerate(v)}
    before = len(have)
    added = updated = 0
    for s in SERIES:
        cursor = None
        for page in range(a.pages):
            p = {"series_ticker": s, "status": "settled", "limit": "200"}
            if cursor:
                p["cursor"] = cursor
            st, b = get("/markets", p)
            if st != 200 or not isinstance(b, dict):
                print(f"  {s}: HTTP {st}, stopping this series")
                break
            ms = b.get("markets", [])
            stop = False
            for m in ms:
                r = record(m)
                if r is None:
                    continue
                if r["ticker"] in have:
                    k, i = have[r["ticker"]]
                    old = d[k][i]
                    if "settle" in r and old.get("settle") is None:
                        old["settle"] = r["settle"]
                        updated += 1
                    if "round_digits" in r and old.get("round_digits") is None:
                        old["round_digits"] = r["round_digits"]
                    stop = True                    # reached known history
                    continue
                d.setdefault(s, []).append(r)
                have[r["ticker"]] = (s, len(d[s]) - 1)
                added += 1
            cursor = b.get("cursor")
            if stop or not cursor or not ms:
                break
        print(f"  {s}: done ({added} added so far)")
    shutil.copy2(FULLTAPE, FULLTAPE + ".bak")
    tmp = FULLTAPE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(tmp, FULLTAPE)
    ns = max(float(r["close"]) for v in d.values() for r in v
             if r.get("result") is not None)
    print(f"\n  markets {before:,} -> {len(have):,} (+{added}, {updated} gained "
          f"a settle level); newest settled close "
          f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(ns))}")
    print(f"  previous file kept at {FULLTAPE}.bak")


if __name__ == "__main__":
    main()
