#!/usr/bin/env python3
# VERSION: 2026-09-08-pr1
"""pinrest.py -- RACE FOR IT versus SIT AT MY PRICE. Which wins more?

THE OPERATOR'S IDEA, and it is a different strategy rather than a different
phrasing:

  REACTIVE (what runs today): watch the book; when an offer appears, decide
  whether that price is acceptable, and race to take it. We are the TAKER, so
  we pay 0.07*p*(1-p), and we only win the races we are fast enough for --
  measured median opportunity life is 163 ms against a ~140 ms round trip.

  PROACTIVE (this): compute, every second, the highest price still worth
  paying, and REST A BID THERE. Anyone who sells into it fills us. We are the
  MAKER, so on these series we pay NO FEE AT ALL, and there is no race to lose.

The test is identical arithmetic -- "price <= threshold" either way -- but the
economics are not:
  fee            taker 0.1-0.3c   vs   maker ZERO (quadratic fee type, verified)
  race           win about half   vs   none to lose
  opportunities  quotes we catch  vs   anyone who sells at our price, any time

THE OBJECTION, and why it may be weaker here than usual. Resting normally means
being filled exactly when you are wrong; that is adverse selection and it cost
this project $24.14 on 2026-09-07. But the settlement input here is a PUBLISHED
index. There is no private information about where it settles -- only how fast
somebody computes. So a seller hitting our bid is either someone who has not
done the arithmetic (good for us) or someone faster (bad). That is a SPEED
disadvantage, not an information one, and it is far more survivable.

That is a theory. This measures it.

QUEUE MODEL, deliberately pessimistic. We assume we join the BACK of the queue
at our price and are filled only by the part of a trade's volume that exceeds
the depth already resting at that level. If the reported size at our price is
S when we post, a trade of volume V at or through our price fills us only
V - S contracts. Anything less pessimistic would flatter resting, which is the
option under test.
"""
import argparse
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

DATA = r"C:\kals\kalshi_data"
ROWS = r"C:\kals-repo\results\pindata\rows.jsonl"


def billed_fee(p, n=1):
    return math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000


def threshold_price(p_flip, margin=0.003):
    """The highest price still worth paying, given the flip chance.

    EV = (1-f)(1-p) - f*p - fee >= margin.  Ignoring the fee (which is zero
    when resting) this is p <= 1 - f - margin. The taker case subtracts the
    fee too, which is why the taker threshold is strictly lower.
    """
    return 1.0 - p_flip - margin


def selftest():
    print("SELF-TEST -- pinrest")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    ck(abs(threshold_price(0.009, 0.0) - 0.991) < 1e-12,
       "with a 0.90% flip chance the highest sane price is 99.1c")
    ck(threshold_price(0.05) < threshold_price(0.005),
       "a riskier trade lowers the price we will pay")
    # the maker/taker difference, at a price where it matters
    p = 0.97
    ck(billed_fee(p) > 0, f"a taker pays {100*billed_fee(p):.2f}c at {100*p:.0f}c")
    ck(billed_fee(p) / (1 - p) > 0.05,
       f"which is {100*billed_fee(p)/(1-p):.0f}% of the whole 3c gross edge -- "
       f"resting keeps it")

    # queue model: pessimistic by construction
    ck(fill_qty(volume=10.0, ahead=8.0, want=5.0) == 2.0,
       "a trade of 10 against 8 resting ahead fills 2 of the 5 we wanted")
    ck(fill_qty(volume=10.0, ahead=8.0) == 1.0,
       "and at size 1 it fills our 1, never more than we asked for")
    ck(fill_qty(volume=5.0, ahead=8.0) == 0.0,
       "a trade smaller than the queue ahead fills nothing")
    ck(fill_qty(volume=100.0, ahead=0.0, want=1.0) == 1.0,
       "we never take more than we asked for")
    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


def fill_qty(volume, ahead, want=1.0):
    """How much of `want` a trade of `volume` fills when `ahead` rests first."""
    return max(0.0, min(want, volume - ahead))


# ---------------------------------------------------------------------------
def load_trades(hours, tickers):
    """{(ticker, second): total volume} from the trade channel."""
    files = sorted(glob.glob(os.path.join(
        DATA, "trade", "2026*.jsonl.gz")))[:-1][-hours:]
    out = defaultdict(float)
    px = defaultdict(list)
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
                    ts = m.get("ts_ms")
                    if ts is None:
                        continue
                    sec = int(ts) // 1000
                    try:
                        cnt = float(m.get("count_fp") or m.get("count") or 0)
                    except Exception:
                        continue
                    out[(tk, sec)] += cnt
                    yp = m.get("yes_price_dollars")
                    if yp is not None:
                        try:
                            px[(tk, sec)].append(float(yp))
                        except Exception:
                            pass
        except (EOFError, zlib.error, OSError):
            pass
    return out, px


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=96)
    ap.add_argument("--flip", type=float, default=0.0090,
                    help="flip rate used for the threshold; the constant is a "
                         "placeholder until the per-trade model lands")
    ap.add_argument("--margin", type=float, default=0.003)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")
    if not os.path.exists(ROWS):
        raise SystemExit(f"no dataset yet at {ROWS} -- run pindata.py first")

    rows = []
    with open(ROWS, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass
    print(f"\n  {len(rows):,} available-trade rows")
    tickers = {r["tk"] for r in rows}
    print(f"  {len(tickers):,} markets; loading trade tape ...")
    vol, _px = load_trades(a.hours, tickers)
    print(f"  {len(vol):,} (market, second) cells with trades\n")

    thr = threshold_price(a.flip, a.margin)
    print(f"  threshold price at flip={100*a.flip:.2f}%, margin="
          f"{100*a.margin:.1f}c  ->  pay no more than {100*thr:.2f}c\n")

    # THE LIVE RULE, not a looser one. The first version of this test traded
    # anything under the threshold at any tau up to 90 s, and produced flip
    # rates of 8-10% -- ten times the 0.90% the real rule sees -- because it
    # was scoring a completely different strategy. Filter to what actually
    # runs: tau in [3,20] and the model decided.
    import math as _m
    from engine import var_factor as _vf
    from statistics import NormalDist as _ND
    _nd = _ND()

    def decided(row):
        r_ = row["r"]
        sg = row.get("sig")
        if not sg or r_ < 1:
            return None
        sd = sg * _m.sqrt(_vf(int(r_), [1.0])) * (60.0 / r_)
        if sd <= 0:
            return 1.0 if row["req"] <= 0 else 0.0
        # P(the move required to flip does NOT happen)
        z = row["req"] / sd
        pf = (1 - _nd.cdf(z)) if row["req"] > 0 else _nd.cdf(z)
        return pf

    rows = [x for x in rows if 3 <= x["tau"] <= 20]
    keep = []
    for x in rows:
        pf = decided(x)
        if pf is None or pf > 0.02:      # model must be >=98% sure
            continue
        x["pf"] = pf
        keep.append(x)
    rows = keep
    print(f"  after the LIVE rule filter (tau 3-20, model >=98% sure): "
          f"{len(rows):,} rows\n")

    take = {"n": 0, "pnl": 0.0, "flips": 0, "fees": 0.0}
    rest = {"n": 0, "pnl": 0.0, "flips": 0, "qty": 0.0}
    # one trade per close for both, matching the live rule
    seen_take, seen_rest = set(), set()
    LADDER = [0.0, 0.005, 0.01, 0.02, 0.03, 0.05]
    ladder = {f"rest@-{100*o:.1f}c": {"n": 0, "pnl": 0.0, "flips": 0}
              for o in LADDER}
    seen_ladder = {k: set() for k in ladder}

    for r in sorted(rows, key=lambda x: x["sec"]):
        cl = r["close"]
        price = r["price"]
        flip = bool(r["flip"])
        # ---- REACTIVE: the offer is there; is it under our threshold? ----
        if cl not in seen_take and price <= thr:
            seen_take.add(cl)
            fee = billed_fee(price, 1)
            take["n"] += 1
            take["fees"] += fee
            take["flips"] += flip
            take["pnl"] += (-price if flip else (1 - price)) - fee
        # ---- PROACTIVE: rest BELOW the threshold, at a ladder of prices.
        # Resting AT the threshold means offering the most we would ever pay,
        # which is the worst possible resting price; the whole point of being
        # the maker is to name a BETTER price and wait.
        v = vol.get((r["tk"], r["sec"]), 0.0)
        for off in LADDER:
            post = round(thr - off, 4)
            if post <= 0.5:
                continue
            key = f"rest@-{100*off:.1f}c"
            if cl in seen_ladder[key]:
                continue
            # we are only hit if the market actually traded at or through our
            # price; the row's own offer price is the best available, so a
            # trade can reach us only if it printed at or below where we sit
            if v <= 0 or price > post:
                continue
            got = fill_qty(v, r["size"], want=1.0)
            if got <= 0:
                continue
            seen_ladder[key].add(cl)
            d_ = ladder[key]
            d_["n"] += 1
            d_["flips"] += flip
            d_["pnl"] += got * (-post if flip else (1 - post))

    print(f"  {'strategy':<26}{'trades':>8}{'flips':>7}{'flip%':>8}"
          f"{'total':>10}{'c/trade':>10}{'fees':>9}")
    allrows = [("REACTIVE  race to take", take, take["fees"])]
    for o in LADDER:
        k = f"rest@-{100*o:.1f}c"
        allrows.append((f"REST at {100*(thr-o):.1f}c", ladder[k], 0.0))
    for name, d, fee in allrows:
        n = d["n"]
        if not n:
            print(f"  {name:<26}{0:>8}")
            continue
        print(f"  {name:<26}{n:>8,}{d['flips']:>7}{d['flips']/n:>7.2%}"
              f"{100*d['pnl']:>9.1f}c{100*d['pnl']/n:>9.2f}c"
              f"{100*fee:>8.1f}c")
    if take["n"] and rest["n"]:
        print(f"\n  resting traded {rest['n']/take['n']:.2f}x as often "
              f"and saved {100*take['fees']:.1f}c of fees")
    print("\n  CAVEATS: the queue model assumes we join the BACK of the queue "
          "and are\n  filled only by volume exceeding the depth already there "
          "-- deliberately\n  pessimistic, because resting is the option under "
          "test. The flip rate here\n  is a CONSTANT placeholder; the per-trade "
          "probability replaces it next.")


if __name__ == "__main__":
    main()
