#!/usr/bin/env python3
# VERSION: 2026-09-07-rc1
"""racecheck.py -- HOW LONG DOES A STALE QUOTE SURVIVE?

pin's own notes name this as its primary open risk, above everything else:

    "The backtest cannot test whether we win the race for a stale quote. In
     the backtest we always get it. In reality we are racing everyone else for
     the same mispriced quote, and the most mispriced quotes are the ones most
     worth racing for. Real fills will be worse than backtest fills by an
     unknown amount, and the amount is not bounded by anything measured so far."

It is measurable from tape, for nothing, BEFORE building any live system.

WHAT IT MEASURES
  pin buys a near-certain contract that somebody is still offering cheap. The
  operational question is: once such an offer appears, how long does it stay
  there? That is the window in which our order must arrive.

  This does NOT need the settlement model. A cheap offer on a contract that
  ends up settling YES is exactly the thing pin hunts, and settlement is known
  from the tape. So: find asks at <= PIN_ASK on markets that settled YES (and
  bids at >= 1-PIN_ASK on markets that settled NO), and measure the lifetime
  of that price level from the moment it appears until it is gone.

  Survival >> our round trip (~200-500 ms) means the race is winnable.
  Survival << that means pin cannot be executed and no amount of code helps.

MEMORY DISCIPLINE: one hour file at a time; two replays were OOM-killed on
this box and the collector outranks every analysis job.
"""
import argparse
import glob
import gc
import gzip
import json
import os
import statistics
import sys

DATA = r"C:\kals\kalshi_data"
PIN_ASK = 0.05          # an ask this cheap on a contract that settles YES
                        # is the "wrong side of near-certainty" pin targets


def settled_results(series_filter=None):
    """ticker -> 'yes'/'no', from the settlement tape."""
    sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
    from kauth import get
    out = {}
    for fam in (series_filter or ["KXBTC15M", "KXETH15M", "KXSOL15M",
                                  "KXXRP15M", "KXDOGE15M"]):
        st, b = get("/markets", {"series_ticker": fam, "status": "settled",
                                 "limit": "1000"})
        for m in (b or {}).get("markets", []):
            if m.get("result") in ("yes", "no"):
                out[m["ticker"]] = m["result"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=3)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        print("SELF-TEST")
        # a level that appears and vanishes must yield its lifetime
        ev = [(1000, 0.03, +50.0), (1400, 0.03, -50.0)]
        book, born, lives = {}, {}, []
        for ts, p, d in ev:
            was = book.get(p, 0.0)
            book[p] = was + d
            if was <= 0.005 < book[p]:
                born[p] = ts
            elif book[p] <= 0.005 and p in born:
                lives.append(ts - born.pop(p))
                book.pop(p, None)
        print(f"  level appears at 1000 ms, gone at 1400 -> lifetime {lives}")
        ok = lives == [400]
        print("SELF-TEST " + ("PASSED" if ok else "*** FAILED ***"))
        raise SystemExit(0 if ok else 1)

    res = settled_results()
    print(f"  {len(res)} settled markets known\n")

    files = sorted(glob.glob(os.path.join(DATA, "orderbook_delta",
                                          "202609*.jsonl.gz")))
    # the newest file is being written by the collector RIGHT NOW and is
    # a truncated gzip. Never read the live hour.
    files = files[:-1][-a.hours:]
    lifetimes, appearances, still_open = [], 0, 0
    for fp in files:
        stamp = os.path.basename(fp)[:11]
        book = {}          # (ticker, side, price) -> size
        born = {}          # (ticker, side, price) -> first ts_ms
        n = 0
        try:
          with gzip.open(fp, "rt") as fh:
            for line in fh:
                if '"orderbook_delta"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                m = d.get("msg") or {}
                tk = m.get("market_ticker")
                if tk not in res:
                    continue
                p = m.get("price_dollars", m.get("price"))
                ts = m.get("ts_ms")
                if p is None or ts is None:
                    continue
                p = round(float(p), 4)
                side = str(m.get("side", "")).lower()
                key = (tk, side, p)
                was = book.get(key, 0.0)
                book[key] = was + float(m.get("delta_fp") or 0.0)
                # is THIS the wrong side of near-certainty?
                # a YES bid at a low price on a market that settled NO is
                # someone paying real cents for a dead contract -- pin sells
                # it. Symmetrically for the no side.
                wrong = ((side == "yes" and res[tk] == "no" and p >= 1 - PIN_ASK)
                         or (side == "no" and res[tk] == "yes" and p >= 1 - PIN_ASK)
                         or (side == "yes" and res[tk] == "yes" and p <= PIN_ASK)
                         or (side == "no" and res[tk] == "no" and p <= PIN_ASK))
                if not wrong:
                    if book[key] <= 0.005:
                        book.pop(key, None)
                        born.pop(key, None)
                    continue
                if was <= 0.005 < book[key]:
                    born[key] = int(ts)
                    appearances += 1
                elif book[key] <= 0.005 and key in born:
                    lifetimes.append(int(ts) - born.pop(key))
                    book.pop(key, None)
                n += 1
        except EOFError:
            print(f"  {stamp}: truncated gzip, using what was read")
        still_open += len(born)
        print(f"  {stamp}: {n:,} relevant deltas, "
              f"{len(lifetimes):,} completed lifetimes so far")
        book.clear()
        born.clear()
        gc.collect()

    if not lifetimes:
        print("\n  no qualifying levels found -- widen PIN_ASK or add hours")
        return
    lt = sorted(lifetimes)
    N = len(lt)
    print(f"\n  {appearances:,} appearances, {N:,} completed lifetimes, "
          f"{still_open:,} still open at file end\n")
    print(f"  LIFETIME OF A MISPRICED QUOTE (milliseconds)")
    for q, lab in ((0.05, "p05"), (0.25, "p25"), (0.50, "MEDIAN"),
                   (0.75, "p75"), (0.95, "p95")):
        print(f"    {lab:<8}{lt[min(N-1, int(q*N))]:>10,} ms")
    print(f"    mean    {statistics.mean(lt):>10,.0f} ms")
    for rt in (100, 200, 500, 1000):
        win = sum(1 for x in lt if x > rt)
        print(f"    survives a {rt:>4} ms round trip: {100*win/N:>5.1f}%")
    print(f"\n  A 200-500 ms round trip is realistic for a REST order from")
    print(f"  this box. If the median lifetime is far above that, the race is")
    print(f"  winnable. If it is far below, pin cannot be executed at all and")
    print(f"  no amount of code fixes it.")


if __name__ == "__main__":
    main()
