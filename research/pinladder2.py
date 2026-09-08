#!/usr/bin/env python3
# VERSION: 2026-09-08-pl2
"""pinladder2.py -- how much can we buy on ONE bet across ALL price levels?

MY FIRST ATTEMPT AT THIS WAS WRONG AND PRODUCED A FANTASY. It said $3,000 of
capital could earn $20,412 a day -- a 680% daily return. Two errors, both of
which flattered the answer:

  1. IT COUNTED BOTH SIDES OF THE BOOK AS PROFITABLE. The loop summed the yes
     ladder and the no ladder. In a decided market only ONE side wins; buying
     the other is a guaranteed loss. This is exactly the mirror error the
     operator's own falsification test was built to catch.
  2. IT PRICED COIN FLIPS AS NEAR-CERTAINTIES. The filter reached down to 51c
     and applied the 0.90% flip rate -- a rate that only holds for the
     near-certain end of the book -- to contracts that are genuine coin flips.

This version fixes both. It uses the INDEX to decide which side the model
favours, buys only that side, and prices every level with the same EV test the
live rule uses, so a level is only counted if it would actually be bought.

THE QUESTION: on one bet, buying at every price we can rather than only the
best, what is the cost and what is the expected profit?
"""
import argparse
import calendar
import glob
import gzip
import json
import math
import os
import sys
import time
import zlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor, N_AVG                        # noqa: E402
from pindata import Book, load_index, idx_feats, partial, eff_strike, \
    SERIES_TO_INDEX, ROUND_DIGITS                            # noqa: E402
from statistics import NormalDist                            # noqa: E402

ND = NormalDist()
DATA = r"C:\kals\kalshi_data"
FULLTAPE = r"C:\kals\fulltape\markets.json"
MEASURED_FLIP = 0.0090
EV_FLOOR = 0.003


def billed_fee(p, n=1):
    return math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000


def ev(price, flip=MEASURED_FLIP):
    return (1 - flip) * (1 - price) - flip * price - billed_fee(price, 1)


def selftest():
    print("SELF-TEST -- pinladder2")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    ck(ev(0.95) > 0 > ev(0.995),
       "the EV test rejects the dear end, which is what the first version "
       "failed to do")
    ck(ev(0.60) > ev(0.95),
       "a coin-flip price shows a LARGER EV under this formula -- which is "
       "exactly why the favoured side must be chosen by the MODEL, not by "
       "price alone")
    b = Book()
    b.snapshot({"yes_dollars": [["0.04", "100"], ["0.03", "50"], ["0.02", "20"]],
                "no_dollars": [["0.95", "10"]]}, 1000)
    # buying NO means hitting the yes bids: NO price = 1 - yes bid
    lv = sorted((round(1 - p, 4), s) for p, s in b.yes.items())
    ck(lv[0] == (0.96, 100.0),
       f"cheapest NO comes from the HIGHEST yes bid ({lv[0]})")
    ck([p for p, _ in lv] == [0.96, 0.97, 0.98],
       "and deeper levels are DEARER, not cheaper -- the ladder runs the "
       "wrong way from intuition")
    keep = [(p, s) for p, s in lv if ev(p) >= EV_FLOOR]
    ck(len(keep) < len(lv),
       f"the EV floor trims the dear end: {len(lv)} levels -> {len(keep)}")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=3)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")

    mk = {}
    for v in json.load(open(FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] in SERIES_TO_INDEX:
                mk[r["ticker"]] = r
    hi = max(float(r["close"]) for r in mk.values())
    idx, _ = load_index(400)
    snaps = {os.path.basename(f)[:11]: f for f in sorted(glob.glob(
        os.path.join(DATA, "orderbook_snapshot", "2026*.jsonl.gz")))}
    allf = sorted(glob.glob(os.path.join(DATA, "orderbook_delta",
                                         "2026*.jsonl.gz")))

    def hs(f):
        return calendar.timegm(time.strptime(os.path.basename(f)[:11],
                                             "%Y%m%dT%H"))

    bf = [f for f in allf if hs(f) + 3600 <= hi][-a.hours:]
    print(f"\n  replaying {[os.path.basename(f)[:11] for f in bf]}\n")

    best_rows, full_rows = [], []
    for f in bf:
        h0 = hs(f)
        want = {t: r for t, r in mk.items()
                if h0 - 900 <= float(r["close"]) <= h0 + 3600}
        if not want:
            continue
        books = {}
        sf = snaps.get(os.path.basename(f)[:11])
        if sf:
            try:
                with gzip.open(sf, "rt") as fh:
                    for line in fh:
                        if '"orderbook_snapshot"' not in line:
                            continue
                        try:
                            m = json.loads(line)["msg"]
                        except Exception:
                            continue
                        if m.get("market_ticker") in want:
                            books.setdefault(m["market_ticker"], Book()).snapshot(
                                m, int(m.get("ts_ms") or 0))
            except (EOFError, zlib.error, OSError):
                pass
        seen = set()
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    if '"orderbook_delta"' not in line:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                    except Exception:
                        continue
                    tk = m.get("market_ticker")
                    rec = want.get(tk)
                    if rec is None:
                        continue
                    ts = int(m.get("ts_ms") or 0)
                    bk = books.setdefault(tk, Book())
                    try:
                        bk.delta(str(m.get("side", "")).lower(),
                                 m.get("price_dollars", m.get("price")),
                                 m.get("delta_fp", m.get("delta")) or 0.0, ts)
                    except Exception:
                        continue
                    sec = ts // 1000
                    close_s = int(float(rec["close"]))
                    tau = close_s - sec
                    if not (3 <= tau <= 30):
                        continue
                    if (tk, sec) in seen:
                        continue
                    seen.add((tk, sec))
                    iid = SERIES_TO_INDEX[rec["series"]]
                    if iid not in idx:
                        continue
                    base, arr = idx[iid]
                    pa = partial(base, arr, close_s, sec)
                    if pa is None:
                        continue
                    locked, rr, _ = pa
                    if rr < 1:
                        continue
                    fe = idx_feats(base, arr, sec)
                    if fe is None or not fe["sigma"]:
                        continue
                    mu = (locked + rr * fe["spot"]) / N_AVG
                    K = eff_strike(rec["strike"], ROUND_DIGITS.get(rec["series"]))
                    req = (60.0 / rr) * (K - mu)
                    sd = fe["sigma"] * math.sqrt(var_factor(int(rr), [1.0])) * (60.0 / rr)
                    if sd <= 0:
                        continue
                    z = req / sd
                    pf = (1 - ND.cdf(z)) if req > 0 else ND.cdf(z)
                    if pf > 0.02:
                        continue          # THE MODEL MUST BE SURE
                    side_yes = req <= 0   # mu above the strike -> YES wins
                    # buying YES means hitting NO bids; buying NO means hitting
                    # YES bids. Price paid = 1 - (the bid we hit).
                    src = bk.no if side_yes else bk.yes
                    lv = sorted((round(1 - p, 4), s) for p, s in src.items()
                                if s >= 1)
                    lv = [(p, s) for p, s in lv if ev(p) >= EV_FLOOR]
                    if not lv:
                        continue
                    won = float(rec["result"]) >= 0.5
                    flip = (side_yes != won)
                    p0, s0 = lv[0]
                    best_rows.append((s0 * p0, s0 * ev(p0), s0, flip))
                    full_rows.append((sum(s * p for p, s in lv),
                                      sum(s * ev(p) for p, s in lv),
                                      sum(s for _, s in lv), flip, len(lv)))
        except (EOFError, zlib.error, OSError):
            pass
        books.clear()

    if not best_rows:
        print("  no qualifying moments")
        return

    def med(rows, i):
        b = sorted(r[i] for r in rows)
        return b[len(b) // 2]

    nflip = sum(1 for r in full_rows if r[3])
    print(f"  {len(full_rows):,} qualifying moments (model >=98% sure), "
          f"{nflip} on the losing side\n")
    print(f"  {'':<28}{'CONTRACTS':>11}{'COST':>11}{'EXP PROFIT':>13}{'RETURN':>9}")
    c1, p1, q1 = med(best_rows, 0), med(best_rows, 1), med(best_rows, 2)
    c2, p2, q2 = med(full_rows, 0), med(full_rows, 1), med(full_rows, 2)
    print(f"  {'best price only':<28}{q1:>11,.0f}${c1:>10,.2f}${p1:>12,.2f}"
          f"{100*p1/c1:>8.2f}%")
    print(f"  {'every level that clears EV':<28}{q2:>11,.0f}${c2:>10,.2f}"
          f"${p2:>12,.2f}{100*p2/c2:>8.2f}%")
    print(f"  {'levels used (median)':<28}{med(full_rows,4):>11,.0f}")
    print(f"\n  Sweeping buys {q2/max(q1,1):.1f}x the contracts, costs "
          f"{c2/max(c1,1e-9):.1f}x, earns {p2/max(p1,1e-9):.1f}x.")
    print(f"  Return per dollar {100*p1/c1:.2f}% -> {100*p2/c2:.2f}%.\n")
    for lab, cap in (("$38 (crypto shard)", 38.0), ("$100", 100.0),
                     ("$250", 250.0), ("$1,000", 1000.0)):
        fr = min(1.0, cap / c2)
        print(f"  {lab:<20} covers {100*fr:>5.1f}% of one sweep -> "
              f"${p2*fr:>6,.2f}/close, ~${p2*fr*33:>8,.2f}/day at 33 closes")
    print("\n  CAVEAT: one close consumes the book once. These are MEDIAN book")
    print("  states, and buying the whole ladder would move the price -- this")
    print("  assumes it does not, which flatters the sweep.")


if __name__ == "__main__":
    main()
