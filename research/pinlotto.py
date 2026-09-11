#!/usr/bin/env python3
# VERSION: 2026-09-11-lt1
"""pinlotto.py -- BUY THE SIDE THE MODEL CALLS IMPOSSIBLE.

THE IDEA, and it is the mirror of everything we have done so far.

Our whole strategy buys near-certainties. Its one proven weakness is that the
model's tail is TOO THIN: at the 0.98 boundary the favoured side flips
1.8-3.1% of the time, and live we have been wrong twice at 7 sigma where the
model claims about one in a billion. We have only ever used that fact
defensively -- to refuse trades.

But if the model understates the chance of the "impossible" outcome, then the
contract for that outcome is UNDERPRICED, and buying it is the same edge read
the other way round. And it is available exactly when nothing else is: when
the market asks 99.4c for the certain side, the impossible side is on offer
for around 0.6-1.5c. An expensive market is a cheap lottery.

The arithmetic is brutal in our favour when it works. A 1c ticket that wins
2% of the time returns 0.02*99 - 0.98*1 = +0.99c per contract, a 99% return
on risk. A 1c ticket that wins 0.5% of the time returns 0.005*99 - 0.995*1
= -0.5c. So EVERYTHING depends on the true flip rate at the price on offer,
which is the one number this file measures.

WHAT WOULD MAKE THIS AN ARTEFACT, checked below:
  * If the lottery side is only cheap when it is genuinely hopeless, the bands
    will show it: price and flip rate will move together and the edge
    vanishes. That is the honest null and it is the likely answer.
  * Fees are charged on the SAME quadratic, and at 1c the fee is tiny in
    absolute terms but large relative to the stake. Charged explicitly.
  * A replay hands us every resting offer. Fill rates on 1c offers are
    unmeasured and are probably worse than ours at the touch, because a 1c
    bid is the most crowded order on the book. Stated, not modelled.
  * Survivorship: markets without a settlement are dropped and counted.
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
import pinrun                                                # noqa: E402
import pindata                                               # noqa: E402
from pinsim import TapeIndex, load_ticks, book_view           # noqa: E402
from pincross import cp_interval                              # noqa: E402
from statistics import NormalDist                            # noqa: E402

ND = NormalDist()
DATA = r"C:\kals\kalshi_data"
FULLTAPE = r"C:\kals\fulltape\markets.json"


def billed_fee(price, count):
    return math.ceil(0.07 * count * price * (1 - price) * 10000 - 1e-9) / 10000


def ev_per_contract(p_win, price):
    """Dollars per contract for a ticket bought at `price` that wins with
    probability p_win. Fee is on the order, charged per contract here."""
    return p_win * (1 - price) - (1 - p_win) * price - billed_fee(price, 1)


def selftest():
    print("SELF-TEST -- pinlotto")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)
    ck(abs(billed_fee(0.16, 12.37) - 0.1164) < 1e-9,
       "the fee matches the real charge on the account's own history")
    e = ev_per_contract(0.02, 0.01)
    ck(0.008 < e < 0.010,
       f"a 1c ticket that wins 2% of the time is worth about +1c "
       f"({100*e:+.2f}c) -- the whole thesis in one number")
    e2 = ev_per_contract(0.005, 0.01)
    ck(e2 < 0,
       f"and the same ticket at a 0.5% win rate is negative ({100*e2:+.2f}c)")
    ck(ev_per_contract(0.02, 0.04) < 0 < ev_per_contract(0.02, 0.015),
       "at a 2% win rate the break-even price sits between 1.5c and 4c, so "
       "the PRICE is what decides it, not the odds alone")
    # a flat model: if price always equals the true probability there is no
    # edge anywhere, which is the null this measurement must be able to show
    flat = [ev_per_contract(p, p) for p in (0.005, 0.01, 0.02, 0.05)]
    ck(all(x < 0 for x in flat),
       "a fairly-priced lottery is a LOSS after fees at every price -- the "
       "null this test must be capable of returning")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=12)
    ap.add_argument("--end", default=None)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed")

    mk = {}
    for v in json.load(open(FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] in pindata.SERIES_TO_INDEX and \
                    r.get("result") is not None:
                mk[r["ticker"]] = r
    bfiles = sorted(glob.glob(os.path.join(
        DATA, "orderbook_delta", "2026*.jsonl.gz")))[:-1]
    if a.end:
        bfiles = [f for f in bfiles if os.path.basename(f)[:11] <= a.end]
    stamps = [os.path.basename(f)[:11] for f in bfiles[-a.hours:]]
    print(f"\n  {len(mk):,} settled markets, {len(stamps)} book hours")

    rows = []
    dropped = defaultdict(int)
    import calendar
    for stamp in stamps:
        hstart = calendar.timegm(time.strptime(stamp, "%Y%m%dT%H"))
        ticks = load_ticks(hstart - 400, hstart + 3700)
        if not ticks:
            continue
        idx = TapeIndex(sorted(ticks))
        pend = {k: list(v) for k, v in ticks.items()}
        books, seen = {}, set()
        sf = os.path.join(DATA, "orderbook_snapshot", f"{stamp}.jsonl.gz")
        if os.path.exists(sf):
            try:
                with gzip.open(sf, "rt") as fh:
                    for line in fh:
                        if '"orderbook_snapshot"' not in line:
                            continue
                        try:
                            d = json.loads(line); m = d["msg"]
                        except Exception:
                            continue
                        if m.get("market_ticker") in mk:
                            books.setdefault(m["market_ticker"],
                                             pindata.Book()).snapshot(
                                                 m, int(m.get("ts_ms") or 0))
            except (EOFError, zlib.error, OSError):
                pass
        last = None
        try:
            with gzip.open(os.path.join(DATA, "orderbook_delta",
                                        f"{stamp}.jsonl.gz"), "rt") as fh:
                for line in fh:
                    try:
                        d = json.loads(line); m = d["msg"]
                    except Exception:
                        continue
                    tk = m.get("market_ticker")
                    ts = int(m.get("ts_ms") or 0)
                    if not ts:
                        continue
                    if tk in mk:
                        try:
                            books.setdefault(tk, pindata.Book()).delta(
                                str(m.get("side", "")).lower(),
                                m.get("price_dollars", m.get("price")),
                                m.get("delta_fp", m.get("delta")) or 0.0, ts)
                        except Exception:
                            pass
                    sec = ts // 1000
                    if sec == last:
                        continue
                    last = sec
                    idx.now = sec
                    idx.feed_upto(pend, sec)
                    for tkk, bkk in books.items():
                        if tkk in seen:
                            continue
                        r = mk[tkk]
                        cs = int(float(r["close"]))
                        tau = cs - sec
                        if not (pinrun.TAU_MIN <= tau <= pinrun.TAU_MAX):
                            continue
                        iid = pindata.SERIES_TO_INDEX[r["series"]]
                        if iid not in idx.ticks:
                            continue
                        sg = idx.sigma(iid)
                        if not sg:
                            continue
                        dg = pindata.ROUND_DIGITS.get(r["series"])
                        fv = pinrun.fair(idx, iid, cs, sec,
                                         float(r["strike"]), sg, round_digits=dg)
                        if fv is None:
                            continue
                        b = book_view(bkk, ts)
                        if b["age_ms"] is None or b["age_ms"] > 2000:
                            continue
                        # the model's FAVOURED side, and the LOTTERY side
                        fav = "yes" if fv >= 0.5 else "no"
                        lot = "no" if fav == "yes" else "yes"
                        px = b.get(f"{lot}_ask")
                        size = b.get(f"{lot}_ask_size") or 0
                        if px is None or not (0 < px < 0.5) or size < 1:
                            dropped["no_lottery_offer"] += 1
                            continue
                        conf = fv if fav == "yes" else 1 - fv
                        if conf < 0.98:
                            dropped["model_not_confident"] += 1
                            continue
                        res = r["result"]
                        yes = (str(res).lower() == "yes") if \
                            isinstance(res, str) else float(res) >= 0.5
                        lot_won = (yes == (lot == "yes"))
                        seen.add(tkk)
                        rows.append(dict(
                            tk=tkk, close=cs, tau=tau, conf=conf,
                            sd=ND.inv_cdf(min(max(conf, 1e-12), 1 - 1e-12)),
                            px=px, size=size, won=lot_won))
        except (EOFError, zlib.error, OSError):
            pass
        print(f"    {stamp}  lottery moments {len(rows):,}", flush=True)

    if not rows:
        print(f"  loaded nothing -- {dict(dropped)}")
        return
    report(rows, dropped)


def report(rows, dropped):
    n = len(rows)
    w = sum(1 for r in rows if r["won"])
    closes = len({r["close"] for r in rows})
    print(f"\n  {'='*92}")
    print(f"  {n:,} lottery tickets on offer over {closes:,} closes "
          f"(one per market, the first second it qualified)")
    print(f"  the model called these IMPOSSIBLE; {w} of them ({100*w/n:.2f}%) "
          f"actually won")
    print(f"  {'='*92}")
    print(f"  {'price paid':>14}{'tickets':>9}{'closes':>8}{'won':>6}"
          f"{'win rate':>10}{'95% CI':>18}{'break-even':>12}{'EV/contract':>13}")
    for lo, hi in ((0.001, 0.01), (0.01, 0.02), (0.02, 0.04), (0.04, 0.08),
                   (0.08, 0.15), (0.15, 0.5)):
        sel = [r for r in rows if lo <= r["px"] < hi]
        if len(sel) < 5:
            continue
        k = sum(1 for r in sel if r["won"])
        cl = len({r["close"] for r in sel})
        a, b = cp_interval(k, len(sel))
        mp = sum(r["px"] for r in sel) / len(sel)
        p = k / len(sel)
        be = mp + billed_fee(mp, 1)
        print(f"  {100*lo:>5.1f}-{100*hi:<8.1f}{len(sel):>9}{cl:>8}{k:>6}"
              f"{100*p:>9.2f}%{'[' + f'{100*a:.2f}, {100*b:.2f}' + ']':>18}"
              f"{100*be:>11.2f}%{100*ev_per_contract(p, mp):>12.3f}c")
    print(f"\n  BY HOW CERTAIN THE MODEL WAS (the tail we know is too thin)")
    print(f"  {'model margin':>14}{'tickets':>9}{'won':>6}{'win rate':>10}"
          f"{'median price':>14}{'EV/contract':>13}")
    for lo, hi in ((2.05, 2.6), (2.6, 3.5), (3.5, 5.0), (5.0, 99)):
        sel = [r for r in rows if lo <= r["sd"] < hi]
        if len(sel) < 5:
            continue
        k = sum(1 for r in sel if r["won"])
        pxs = sorted(r["px"] for r in sel)
        mp = pxs[len(pxs) // 2]
        p = k / len(sel)
        print(f"  {lo:>5.2f}-{hi:<8.1f}{len(sel):>9}{k:>6}{100*p:>9.2f}%"
              f"{100*mp:>13.1f}c{100*ev_per_contract(p, mp):>12.3f}c")
    print(f"\n  dropped: {dict(dropped)}")
    print(f"\n  CAVEATS THAT TRAVEL WITH EVERY NUMBER ABOVE:")
    print(f"   * a replay hands us every resting offer. A 1c bid is the most "
          f"crowded order on\n     the book, so the real fill rate here is "
          f"probably far worse than our 65% at the touch.")
    print(f"   * one ticket per market, at the first qualifying second, so "
          f"this is not a\n     capacity estimate.")


if __name__ == "__main__":
    main()
