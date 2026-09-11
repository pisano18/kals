#!/usr/bin/env python3
# VERSION: 2026-09-11-tt1
"""pintrades.py -- MEASURE THE DISCOUNT QUESTION ON TRADES THAT ACTUALLY HAPPENED.

WHY THIS EXISTS, and it is an admission.

For two days every loss-rate answer has come from replaying the ORDER BOOK,
and that replay is structurally blind to the trades we care about. Proven
twice: the 82c XRP fill we actually took does not appear anywhere in the
reconstructed book, and big-discount moments show up in 0.7% of replayed
markets against 7.8% of our live fills -- eleven times rarer. At the live
gate the book replay says we lose 0.11% of the time and live says 3.4%, with
non-overlapping intervals. The book replay describes a world where offers sit
waiting; ours is a world where someone pushes an offer at us.

THE TRADE TAPE HAS NO SUCH BLIND SPOT. Every execution is printed with the
price, the size, the timestamp and -- decisively -- `taker_side`, which says
who crossed. A taker buying the near-certain side at a discount IS the
population we have been arguing about, and there are millions of them.

SO: for every trade in the final seconds of a crypto 15M market, compute what
our model believed at that second, how big a discount the taker got, and
whether the taker's side won. No book, no reconstruction, no fill assumption.

WHAT THIS STILL CANNOT TELL US:
  * whether WE would have won that race -- these are other people's fills.
  * fees: takers pay the quadratic; the taker P&L below charges it.
  * a trade is one print of a possibly-swept ladder (see the sweep_shape work
    in CLAUDE.md), so counts are per print, and the n reported is prints AND
    closes, never treated as independent.
"""
import argparse
import glob
import gzip
import json
import math
import os
import sys
import time
import calendar
import zlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinrun                                                # noqa: E402
import pindata                                               # noqa: E402
from pinsim import TapeIndex, load_ticks                      # noqa: E402
from pincross import cp_interval                              # noqa: E402

DATA = r"C:\kals\kalshi_data"
FULLTAPE = r"C:\kals\fulltape\markets.json"


def fee(p, n=1.0):
    return math.ceil(0.07 * n * p * (1 - p) * 10000 - 1e-9) / 10000


def taker_pnl(price, won, n=1.0):
    return (n * (1 - price) if won else -n * price) - fee(price, n)


def selftest():
    print("SELF-TEST -- pintrades")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)
    ck(abs(fee(0.16, 12.37) - 0.1164) < 1e-9,
       "the fee matches the account's own reconciled charge")
    ck(abs(taker_pnl(0.46, True, 20) - (20 * 0.54 - fee(0.46, 20))) < 1e-9,
       "a winning 46c taker fill of 20 pays 20 x 54c minus the fee")
    ck(taker_pnl(0.46, False, 20) < -9.2,
       "and a losing one costs the full stake plus the fee")
    # the taker's side and price must be read together or every sign flips
    m = {"yes_price_dollars": "0.6500", "no_price_dollars": "0.3500",
         "taker_side": "no"}
    px = float(m["no_price_dollars"] if m["taker_side"] == "no"
               else m["yes_price_dollars"])
    ck(abs(px - 0.35) < 1e-9,
       "a NO taker on a 65/35 print paid 35c, not 65c")
    ck(abs(float(m["yes_price_dollars"]) + float(m["no_price_dollars"]) - 1.0)
       < 1e-9, "and the two sides of a print sum to a dollar")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for x in f:
        print("   - " + x)
    return not f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=12)
    ap.add_argument("--end", default=None)
    ap.add_argument("--conf", type=float, default=0.995)
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
    files = sorted(glob.glob(os.path.join(DATA, "trade", "2026*.jsonl.gz")))[:-1]
    if a.end:
        files = [f for f in files if os.path.basename(f)[:11] <= a.end]
    files = files[-a.hours:]
    print(f"\n  {len(mk):,} settled markets, {len(files)} hours of trade tape\n")

    rows = []
    skipped = defaultdict(int)
    for fp in files:
        stamp = os.path.basename(fp)[:11]
        h0 = calendar.timegm(time.strptime(stamp, "%Y%m%dT%H"))
        ticks = load_ticks(h0 - 400, h0 + 3700)
        if not ticks:
            continue
        idx = TapeIndex(sorted(ticks))
        pend = {k: list(v) for k, v in ticks.items()}
        last = None
        try:
            with gzip.open(fp, "rt") as fh:
                for line in fh:
                    if '"trade"' not in line or '15M' not in line:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                    except Exception:
                        continue
                    tk = m.get("market_ticker")
                    r = mk.get(tk)
                    if r is None:
                        continue
                    ts = int(m.get("ts_ms") or 0)
                    if not ts:
                        continue
                    sec = ts // 1000
                    cs = int(float(r["close"]))
                    tau = cs - sec
                    if not (pinrun.TAU_MIN <= tau <= pinrun.TAU_MAX):
                        continue
                    if sec != last:
                        last = sec
                        idx.now = sec
                        idx.feed_upto(pend, sec)
                    iid = pindata.SERIES_TO_INDEX[r["series"]]
                    if iid not in idx.ticks:
                        continue
                    sg = idx.sigma(iid)
                    if not sg:
                        skipped["no_sigma"] += 1
                        continue
                    fv = pinrun.fair(idx, iid, cs, sec, float(r["strike"]), sg,
                                     round_digits=pindata.ROUND_DIGITS.get(
                                         r["series"]))
                    if fv is None:
                        skipped["no_fair"] += 1
                        continue
                    side = m.get("taker_side")
                    if side not in ("yes", "no"):
                        skipped["no_taker_side"] += 1
                        continue
                    try:
                        px = float(m["no_price_dollars"] if side == "no"
                                   else m["yes_price_dollars"])
                        n = float(m.get("count_fp") or m.get("count") or 0)
                    except Exception:
                        continue
                    if n <= 0 or not (0 < px < 1):
                        continue
                    conf = fv if side == "yes" else 1 - fv
                    if conf < a.conf:
                        skipped["model_not_confident"] += 1
                        continue
                    res = r["result"]
                    yes = (str(res).lower() == "yes") if isinstance(res, str) \
                        else float(res) >= 0.5
                    won = (yes == (side == "yes"))
                    rows.append((100 * (conf - px), px, n, won, cs, tau, tk))
        except (EOFError, zlib.error, OSError):
            pass
        print(f"    {stamp}  qualifying trades {len(rows):,}", flush=True)

    if not rows:
        print(f"  loaded nothing -- {dict(skipped)}")
        return
    report(rows, skipped, a.conf)


def report(rows, skipped, conf):
    n = len(rows)
    cl = len({r[4] for r in rows})
    L = [r for r in rows if not r[3]]
    print(f"\n  {'='*96}")
    print(f"  {n:,} trades where the taker bought a side our model called "
          f">= {100*conf:.1f}% certain, over {cl:,} closes")
    print(f"  {len(L):,} of them LOST ({100*len(L)/n:.2f}%) -- these are real "
          f"fills somebody actually got, not reconstructed offers")
    print(f"  {'='*96}")
    print(f"  {'discount':>12}{'trades':>9}{'closes':>8}{'contracts':>12}"
          f"{'lost':>7}{'loss rate':>11}{'95% CI':>18}{'taker P&L/contract':>20}")
    for lo, hi in ((-99, 0), (0, 2), (2, 5), (5, 10), (10, 15), (15, 25),
                   (25, 50), (50, 100)):
        sel = [r for r in rows if lo <= r[0] < hi]
        if len(sel) < 5:
            continue
        k = sum(1 for r in sel if not r[3])
        c = len({r[4] for r in sel})
        ct = sum(r[2] for r in sel)
        a_, b_ = cp_interval(k, len(sel))
        pnl = sum(taker_pnl(r[1], r[3], r[2]) for r in sel)
        print(f"  {lo:>5}-{hi:<6}{len(sel):>9,}{c:>8,}{ct:>12,.0f}{k:>7,}"
              f"{100*k/len(sel):>10.2f}%"
              f"{'[' + f'{100*a_:.2f}, {100*b_:.2f}' + ']':>18}"
              f"{100*pnl/max(1e-9, ct):>19.2f}c")
    big = [r for r in rows if r[0] >= 15]
    if big:
        k = sum(1 for r in big if not r[3])
        ct = sum(r[2] for r in big)
        pnl = sum(taker_pnl(r[1], r[3], r[2]) for r in big)
        a_, b_ = cp_interval(k, len(big))
        print(f"\n  THE BAND WE REFUSE (>= 15c discount): {len(big):,} trades "
              f"over {len({r[4] for r in big}):,} closes, {ct:,.0f} contracts")
        print(f"    lost {k:,} = {100*k/len(big):.2f}% [{100*a_:.2f}, "
              f"{100*b_:.2f}]   taker P&L {100*pnl/max(1e-9,ct):+.2f}c per "
              f"contract  (total ${pnl:+,.2f})")
    print(f"\n  skipped: {dict(skipped)}")
    print(f"  NOTE: these are OTHER PEOPLE'S fills. They say what the trade is "
          f"worth to whoever\n  wins the race, not whether we would win it.")


if __name__ == "__main__":
    main()
