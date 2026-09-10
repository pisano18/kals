#!/usr/bin/env python3
# VERSION: 2026-09-10-pr1
"""pinrace.py -- ARE WE LOSING THE RACE, OR WINNING THE WRONG ONES?

The live bot loses 8.8% of the time; the tape's tradeable population loses
0.79%. The intervals do not overlap (research/pindisc.py, pintail.py). The
only thing the tape cannot see is THE RACE: in the backtest we always get the
resting offer; live we send an order and sometimes get nothing.

This file uses the only data that has the race in it -- our own live log.
Every order we sent is there with how much of it filled. For the ones that
did NOT fill, the market still settled, so we know what would have happened.

THE QUESTION: do the orders we FAIL to fill win more often than the ones we
fill? If yes, we are being filled selectively on the losers -- somebody
faster takes the good ones and leaves us the bad ones -- and the loss rate is
a property of the race, not of the model. That is a different fix entirely.

Units: attempts and closes. Many attempts share a close; every rate is quoted
with an exact interval and the close count beside it.
"""
import glob
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pincross import cp_interval                              # noqa: E402

RESULTS = r"C:\kals-repo\results"
FULLTAPE = r"C:\kals\fulltape\markets.json"


def selftest():
    print("SELF-TEST -- pinrace")
    ok = True
    lo, hi = cp_interval(2, 20)
    ok &= lo < 0.1 < hi
    print(("  ok   " if ok else "  FAIL ") + "interval machinery is live")
    print("SELF-TEST " + ("PASSED" if ok else "*** FAILED ***"))
    return ok


def main():
    if not selftest():
        raise SystemExit(1)
    mk = {}
    for v in json.load(open(FULLTAPE, encoding="utf-8")).values():
        for r in v:
            mk[r["ticker"]] = r

    attempts = []
    for f in sorted(glob.glob(os.path.join(RESULTS, "pinrun-live-*.jsonl"))):
        sig = {}
        for line in open(f, encoding="utf-8"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("kind") == "signal":
                sig[d["ticker"]] = d
            elif d.get("kind") == "order":
                s = sig.get(d["ticker"])
                if not s:
                    continue
                r = mk.get(d["ticker"])
                if r is None or r.get("result") is None:
                    continue
                # `result` is 'yes'/'no' on markets pulled after 09-06 and
                # 1.0/0.0 on the older ones; endgame.outcome_of handles both
                # and so must this
                res = r["result"]
                if isinstance(res, str):
                    if res.lower() not in ("yes", "no"):
                        continue
                    yes_won = res.lower() == "yes"
                else:
                    yes_won = float(res) >= 0.5
                won = (yes_won == (s["want"] == "yes"))
                filled = float(d.get("filled") or 0.0)
                attempts.append({
                    "ticker": d["ticker"], "close": int(float(r["close"])),
                    "want": s["want"], "bid": float(s["price"]),
                    "fair": float(s["fair"]), "tau": s["tau"],
                    "filled": filled,
                    "want_n": float(s.get("take_n") or d.get("count")
                                    or (d.get("body") or {}).get("count")
                                    or 1.0),
                    "exec": d.get("exec_price"),
                    "book_age_ms": s.get("book_age_ms"),
                    "latency_ms": d.get("latency_ms"),
                    "status": d.get("status_code"),
                    "won": won, "file": os.path.basename(f)})
    if not attempts:
        print("  loaded nothing")
        return
    print(f"\n  {len(attempts)} live order attempts with a known outcome, "
          f"over {len(set(a['close'] for a in attempts))} closes, "
          f"{len(set(a['ticker'] for a in attempts))} markets")

    def show(label, rows):
        if not rows:
            print(f"  {label:<44} --")
            return
        w = sum(1 for a in rows if a["won"])
        l = len(rows) - w
        lo, hi = cp_interval(l, len(rows))
        print(f"  {label:<44}{len(rows):>5} attempts "
              f"{len(set(a['close'] for a in rows)):>4} closes "
              f"{l:>3} lost  {100*l/len(rows):>6.2f}%  "
              f"[{100*lo:.2f}, {100*hi:.2f}]")

    full = [a for a in attempts if a["filled"] >= a["want_n"] - 1e-9]
    part = [a for a in attempts if 0 < a["filled"] < a["want_n"] - 1e-9]
    none = [a for a in attempts if a["filled"] <= 0]
    print()
    show("FILLED in full", full)
    show("PARTIAL fill", part)
    show("NOT filled (what would have happened)", none)
    show("all attempts", attempts)

    print("\n  same split, TODAY'S RULE ONLY (bid <= 98.0c):")
    cur = [a for a in attempts if a["bid"] <= 0.980 + 1e-9]
    show("FILLED (any amount)", [a for a in cur if a["filled"] > 0])
    show("NOT filled", [a for a in cur if a["filled"] <= 0])

    print("\n  losses, one per line:")
    for a in attempts:
        if not a["won"]:
            print(f"    {a['ticker']:<28} {a['want']:<3} bid {100*a['bid']:5.1f}c "
                  f"exec {a['exec']} filled {a['filled']:g}/{a['want_n']:g} "
                  f"tau {a['tau']:>2} fair {a['fair']:.4f} "
                  f"book_age {a['book_age_ms']}ms lat {a['latency_ms']}ms "
                  f"http {a['status']}")

    print("\n  unfilled attempts that WOULD HAVE LOST (the ones the race "
          "saved us from):")
    for a in none:
        if not a["won"]:
            print(f"    {a['ticker']:<28} {a['want']:<3} bid {100*a['bid']:5.1f}c "
                  f"tau {a['tau']:>2} fair {a['fair']:.4f} http {a['status']}")

    # book age and latency, filled winners vs filled losers
    fw = [a for a in attempts if a["filled"] > 0 and a["won"]]
    fl = [a for a in attempts if a["filled"] > 0 and not a["won"]]

    def med(rows, k):
        v = sorted(float(a[k]) for a in rows if a.get(k) is not None)
        return v[len(v) // 2] if v else float("nan")

    print(f"\n  filled winners: median book_age {med(fw,'book_age_ms'):.0f} ms, "
          f"latency {med(fw,'latency_ms'):.0f} ms, tau {med(fw,'tau'):.0f}, "
          f"bid {100*med(fw,'bid'):.1f}c  (n={len(fw)})")
    print(f"  filled losers:  median book_age {med(fl,'book_age_ms'):.0f} ms, "
          f"latency {med(fl,'latency_ms'):.0f} ms, tau {med(fl,'tau'):.0f}, "
          f"bid {100*med(fl,'bid'):.1f}c  (n={len(fl)})")


if __name__ == "__main__":
    main()
