#!/usr/bin/env python3
# VERSION: 2026-09-08-pr2
"""pinrest2.py -- resting, tested FAIRLY this time.

WHY THIS REPLACES pinrest.py

The first comparison filled a resting order only when the best visible offer
was ALREADY at or below our price -- which means we would simply have taken it.
That simulates resting as a strictly worse version of taking, so of course it
lost. It was not a test of the idea.

A resting order really fills when an AGGRESSIVE COUNTERPARTY CROSSES to our
price. That is visible in the trade tape: every print carries a yes price. So:

  buying YES at p   = a bid at yes price p.   Filled when a seller prints at
                      yes price <= p.
  buying NO  at q   = an ask at yes price 1-q. Filled when a buyer prints at
                      yes price >= 1-q.

This version reads those prints and fills accordingly, which is the honest
test. It also keeps the pessimistic queue rule -- we join the BACK of the queue
and are filled only by volume beyond the depth already resting -- because
resting is the option under test and should not be flattered.

WHAT ELSE THE FIRST VERSION GOT WRONG
  * it rested at a CONSTANT price all the way to the close. The threshold
    should move every second as the outcome becomes more certain, which is the
    operator's whole point. Here the resting price tracks the model.
  * it never considered resting on the side the model favours BEFORE the
    market has moved there -- i.e. posting early and being filled later.
"""
import argparse
import glob
import gzip
import json
import math
import os
import sys
import zlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor                                # noqa: E402
from statistics import NormalDist                            # noqa: E402

ND = NormalDist()
DATA = r"C:\kals\kalshi_data"
ROWS = r"C:\kals-repo\results\pindata\rows.jsonl"
MEASURED_FLIP = 0.0090
EV_FLOOR = 0.003


def billed_fee(p, n=1):
    return math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000


def ev_taker(price, flip=MEASURED_FLIP):
    return (1 - flip) * (1 - price) - flip * price - billed_fee(price, 1)


def ev_maker(price, flip=MEASURED_FLIP):
    """Same, minus nothing: a maker pays no fee on these series."""
    return (1 - flip) * (1 - price) - flip * price


def model_p_flip(row):
    r = row["r"]
    sg = row.get("sig")
    if not sg or r < 1:
        return None
    sd = sg * math.sqrt(var_factor(int(r), [1.0])) * (60.0 / r)
    if sd <= 0:
        return 0.0 if row["req"] <= 0 else 1.0
    z = row["req"] / sd
    return (1 - ND.cdf(z)) if row["req"] > 0 else ND.cdf(z)


def max_maker_price(pf, floor=EV_FLOOR):
    """Highest price a MAKER can pay and still clear the EV floor."""
    return 1.0 - pf - floor


def selftest():
    print("SELF-TEST -- pinrest2")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    ck(ev_maker(0.97) > ev_taker(0.97),
       f"a maker keeps the fee: {100*ev_maker(0.97):.2f}c vs "
       f"{100*ev_taker(0.97):.2f}c at 97c")
    ck(abs(max_maker_price(0.001, 0.0) - 0.999) < 1e-12,
       "at 0.1% risk a maker can pay up to 99.9c")
    ck(max_maker_price(0.05) < max_maker_price(0.005),
       "riskier -> lower resting price")
    # fill logic, both sides
    ck(fills_yes(post=0.95, trade_px=0.94), "a YES bid at 95c fills on a 94c print")
    ck(not fills_yes(post=0.95, trade_px=0.96),
       "and does NOT fill on a 96c print")
    ck(fills_no(post_no=0.95, trade_px=0.06),
       "a NO bid at 95c (ask at 5c) fills on a 6c print")
    ck(not fills_no(post_no=0.95, trade_px=0.04),
       "and does NOT fill on a 4c print")
    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


def fills_yes(post, trade_px):
    """A resting YES bid at `post` fills when someone sells at or below it."""
    return trade_px <= post + 1e-9


def fills_no(post_no, trade_px):
    """Buying NO at post_no = an ask at yes price 1-post_no; fills when a
    buyer lifts at or above that."""
    return trade_px >= (1.0 - post_no) - 1e-9


def load_trade_prints(hours, tickers):
    """{(ticker, sec): [(yes_price, count), ...]}"""
    files = sorted(glob.glob(os.path.join(
        DATA, "trade", "2026*.jsonl.gz")))[:-1][-hours:]
    out = defaultdict(list)
    for f in files:
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    if '"trade"' not in line:
                        continue
                    try:
                        d = json.loads(line)
                        m = d["msg"]
                    except Exception:
                        continue
                    tk = m.get("market_ticker")
                    if tk not in tickers:
                        continue
                    ts, yp = m.get("ts_ms"), m.get("yes_price_dollars")
                    if ts is None or yp is None:
                        continue
                    try:
                        out[(tk, int(ts) // 1000)].append(
                            (float(yp),
                             float(m.get("count_fp") or m.get("count") or 0)))
                    except Exception:
                        continue
        except (EOFError, zlib.error, OSError):
            pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=96)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")

    rows = []
    with open(ROWS, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass
    rows = [r for r in rows if 3 <= r["tau"] <= 20]
    tickers = {r["tk"] for r in rows}
    print(f"\n  {len(rows):,} rows at tau 3-20, {len(tickers):,} markets")
    prints = load_trade_prints(a.hours, tickers)
    print(f"  {len(prints):,} (market, second) cells carry trade prints\n")

    take = {"n": 0, "flips": 0, "pnl": 0.0}
    rest = defaultdict(lambda: {"n": 0, "flips": 0, "pnl": 0.0})
    seen_t, seen_r = set(), defaultdict(set)
    OFFS = [0.0, 0.005, 0.01, 0.02, 0.03]

    for r in sorted(rows, key=lambda x: x["sec"]):
        cl, price, flip = r["close"], r["price"], bool(r["flip"])
        pf = model_p_flip(r)
        if pf is None or pf > 0.02:
            continue

        # ---- TAKE: the live rule ----
        if cl not in seen_t and ev_taker(price) >= EV_FLOOR:
            seen_t.add(cl)
            take["n"] += 1
            take["flips"] += flip
            take["pnl"] += ((-price if flip else (1 - price))
                            - billed_fee(price, 1))

        # ---- REST: post at the model's own max, and BELOW it ----
        cap = max_maker_price(pf)
        pr = prints.get((r["tk"], r["sec"]), ())
        if not pr:
            continue
        for off in OFFS:
            post = round(min(cap, price) - off, 4)
            if post <= 0.5 or post >= 1.0:
                continue
            key = f"-{100*off:.1f}c"
            if cl in seen_r[key]:
                continue
            if ev_maker(post) < EV_FLOOR:
                continue
            # would a counterparty have crossed to us this second?
            hit = 0.0
            for tpx, cnt in pr:
                ok = (fills_yes(post, tpx) if r["side_yes"]
                      else fills_no(post, tpx))
                if ok:
                    hit += cnt
            if hit <= 0:
                continue
            got = max(0.0, min(1.0, hit - r["size"]))   # back of the queue
            if got <= 0:
                continue
            seen_r[key].add(cl)
            d = rest[key]
            d["n"] += 1
            d["flips"] += flip
            d["pnl"] += got * (-post if flip else (1 - post))

    print(f"  {'strategy':<30}{'trades':>8}{'losses':>8}{'loss%':>8}"
          f"{'total':>11}{'c/trade':>10}")
    n = take["n"]
    print(f"  {'TAKE (live rule)':<30}{n:>8,}{take['flips']:>8}"
          f"{(take['flips']/n if n else 0):>7.1%}{100*take['pnl']:>10.1f}c"
          f"{(100*take['pnl']/n if n else 0):>9.2f}c")
    for off in OFFS:
        key = f"-{100*off:.1f}c"
        d = rest[key]
        n2 = d["n"]
        if not n2:
            continue
        print(f"  {'REST at cap ' + key:<30}{n2:>8,}{d['flips']:>8}"
              f"{d['flips']/n2:>7.1%}{100*d['pnl']:>10.1f}c"
              f"{100*d['pnl']/n2:>9.2f}c")
    best = max((rest[f'-{100*o:.1f}c']['pnl'] for o in OFFS), default=0.0)
    print(f"\n  TAKE total {100*take['pnl']:.1f}c   best REST total "
          f"{100*best:.1f}c   ->  "
          f"{'RESTING WINS' if best > take['pnl'] else 'TAKING WINS'}")
    print("\n  Fills now come from ACTUAL TRADE PRINTS crossing to our price,")
    print("  not from the offer already being there. Queue rule still")
    print("  pessimistic: back of the queue, filled only beyond resting depth.")


if __name__ == "__main__":
    main()
