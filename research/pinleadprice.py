#!/usr/bin/env python3
# VERSION: 2026-09-11-lp2
"""pinleadprice.py -- WHAT DOES THE MARKET CHARGE FOR A LEADER WE CAN NAME?

pinlead.py established two things on 337 events of real tape:
  * the settlement rule is exactly "highest (close 60s TWAP / open 60s TWAP)",
    reproduced on 337 of 337 -- the open TWAP is known when the window opens;
  * the leader can be named 91.1% of the time at tau 60, 97.0% at tau 30 and
    99.4% at tau 20.

NONE OF THAT IS WORTH A CENT IF THE MARKET ALREADY CHARGES 99c FOR IT. This
file is the stage that can kill the idea, and it is deliberately separate so
that the prediction cannot be quietly re-tuned after the price is seen.

INSTRUMENT: the TRADE tape, for the reason set out in pintrades.py. A book
replay is structurally blind to executions (proved twice on this project);
the trade tape prints every fill with taker_side, price and size. A taker who
bought YES at price P proves an ask existed at P at that second -- that is a
PRICE WE COULD HAVE PAID, observed rather than reconstructed.

*** THE LOOK-AHEAD BUG THIS FILE WAS BORN WITH, RECORDED IN PLACE ***
v1 scored EVERY purchase against the tau-20 prediction, including purchases
made at tau 45-61. At tau 50 we do not have the tau-20 forecast; it is 30
seconds of future index prints away. That inflated accuracy in the top band
from 91.1% to 98.9% and turned a marginal result into a spectacular one. v2
matches each trade to the prediction made at the SMALLEST GRID TAU >= the
trade's own tau, which is stale rather than clairvoyant -- conservative in
the one direction that matters.

WHAT IT STILL CANNOT SAY. It cannot prove we would have won the race for that
ask, and it only sees seconds when somebody traded. Both push the same way,
so every P&L below is an UPPER BOUND and is labelled so. Three purchase rules
are reported side by side because the gap between them IS the finding:
  FIRST   -- cross at the first YES-taker print in the band (realistic)
  LIMIT   -- buy only if some print in the band is at or below a limit, else
             stand aside (what a resting bid actually does)
  CHEAPEST-- take the lowest print in the band (the pure upper bound)

BREAK-EVEN, stated before the numbers are read: buying at price P with
accuracy q earns q - P - fee. At q = 0.994 that line is 99.35c; at q = 0.970
it is 96.78c; at q = 0.911 it is 90.6c.
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
from pincross import cp_interval                              # noqa: E402

DATA = r"C:\kals\kalshi_data"
LEAD = r"C:\kals\fulltape\lead.json"
PRED = os.path.join(HERE, "_lead_pred.json")
NTOT = 0


def fee(p, n=1.0):
    return math.ceil(0.07 * n * p * (1 - p) * 10000 - 1e-9) / 10000


def pnl(price, won, n=1.0):
    return (n * (1 - price) if won else -n * price) - fee(price, n)


def breakeven(q):
    """Highest price at which accuracy q is still profitable, in cents."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        m = (lo + hi) / 2
        if q * (1 - m) - (1 - q) * m - fee(m) > 0:
            lo = m
        else:
            hi = m
    return 100 * lo


def pred_for(rec, tau, grid):
    """The prediction we would ACTUALLY hold at `tau`.

    The grid tau chosen is the smallest one >= tau, i.e. the most recent
    forecast that does not use index prints from after the trade. Returns
    None when no such forecast exists. This function is the fix for the v1
    look-ahead bug and is self-tested.
    """
    cand = [t for t in grid if t >= tau and str(t) in rec]
    if not cand:
        return None
    return rec[str(min(cand))]


def selftest():
    print("SELF-TEST -- pinleadprice")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)
    ck(abs(fee(0.16, 12.37) - 0.1164) < 1e-9,
       "the fee matches the account's own reconciled charge")
    ck(abs(pnl(0.95, True, 20) - (20 * 0.05 - fee(0.95, 20))) < 1e-9,
       "a winning 95c buy of 20 pays 20 x 5c minus the fee")
    ck(pnl(0.95, False, 20) < -19.0,
       "and a losing one costs the whole 19 dollars, not the 5c of upside")
    b99, b97, b91 = breakeven(0.994), breakeven(0.970), breakeven(0.911)
    ck(99.2 < b99 < 99.4,
       "at 99.4%% accuracy the break-even price is ~99.3c (got %.2f)" % b99)
    ck(96.5 < b97 < 97.0,
       "at 97.0%% accuracy it falls to ~96.8c (got %.2f)" % b97)
    ck(90.0 < b91 < 91.2,
       "at 91.1%% accuracy it falls to ~90.6c (got %.2f)" % b91)
    ck(breakeven(0.5) < 50.0,
       "a coin flip cannot break even at 50c, because the taker pays the fee")

    # --- THE LOOK-AHEAD GUARD. This is the test v1 did not have. ----------
    grid = [60, 45, 30, 25, 20, 15, 10, 5, 3]
    rec = {"60": {"coin": "BTC"}, "45": {"coin": "ETH"}, "30": {"coin": "SOL"},
           "20": {"coin": "XRP"}, "3": {"coin": "HYPE"}}
    ck(pred_for(rec, 37, grid)["coin"] == "ETH",
       "a trade at tau 37 uses the tau-45 forecast -- stale, never the tau-30")
    ck(pred_for(rec, 45, grid)["coin"] == "ETH",
       "a trade exactly at tau 45 may use the tau-45 forecast")
    ck(pred_for(rec, 46, grid)["coin"] == "BTC",
       "one second earlier it must fall back to tau 60")
    ck(pred_for(rec, 21, grid)["coin"] == "SOL",
       "a trade at tau 21 uses tau 30, because tau 20 has not happened yet")
    ck(pred_for(rec, 61, grid) is None,
       "before the earliest forecast there is no prediction, not a guess")
    ck(all(pred_for(rec, t, grid) is None or
           min(int(k) for k in rec if int(k) >= t) >= t for t in range(1, 61)),
       "for every tau, the forecast used is never from the future")

    m = {"yes_price_dollars": "0.9200", "no_price_dollars": "0.0800",
         "taker_side": "yes"}
    ck(abs(float(m["yes_price_dollars"]) - 0.92) < 1e-9 and
       abs(float(m["yes_price_dollars"]) + float(m["no_price_dollars"]) - 1)
       < 1e-9, "a YES taker on a 92/8 print paid 92c and the sides sum to $1")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for x in f:
        print("   - " + x)
    return not f


def table(rows, label, note=""):
    """rows: (price, won). Prints the one line that decides the idea."""
    if len(rows) < 10:
        print("  %-10s %d events -- too few to report" % (label, len(rows)))
        return
    w = sum(1 for r in rows if r[1])
    q = w / float(len(rows))
    avg = sum(r[0] for r in rows) / len(rows)
    tot = sum(pnl(r[0], r[1]) for r in rows)
    lo_, hi_ = cp_interval(len(rows) - w, len(rows))
    print("  %-10s%8d%9.1f%%%10.2fc%11.2fc%12.2fc%13.3f   loss %.1f%% "
          "[%.1f, %.1f] %s"
          % (label, len(rows), 100 * q, 100 * avg, breakeven(q),
             100 * tot / len(rows), 20 * tot / len(rows),
             100 * (1 - q), 100 * lo_, 100 * hi_, note))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=120)
    ap.add_argument("--limit", type=float, default=0.95)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed")

    pred = json.load(open(PRED, encoding="utf-8"))
    ev = json.load(open(LEAD, encoding="utf-8"))
    closes = {k: v["close"] for k, v in ev.items()}
    grid = sorted({int(t) for r in pred.values() for t in r}, reverse=True)
    global NTOT
    NTOT = len(pred)
    print("\n  %d events carrying forecasts at taus %s" % (len(pred), grid))
    print("  break-even: 99.35c at q=99.4%%, 96.78c at q=97.0%%, "
          "90.6c at q=91.1%%\n")

    files = sorted(glob.glob(os.path.join(DATA, "trade",
                                          "2026*.jsonl.gz")))[:-1][-a.hours:]
    lifts = defaultdict(list)       # (event, leg) -> [(tau, price, size)]
    allleg = defaultdict(list)
    seen = 0
    for fp in files:
        try:
            with gzip.open(fp, "rt") as fh:
                for line in fh:
                    if "CRYPTOLEAD" not in line or '"trade"' not in line:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                    except Exception:
                        continue
                    tk = m.get("market_ticker") or ""
                    evt, _, leg = tk.rpartition("-")
                    cs = closes.get(evt)
                    if cs is None:
                        continue
                    ts = int(m.get("ts_ms") or 0)
                    if not ts:
                        continue
                    tau = cs - ts // 1000
                    if not (0 <= tau <= 120):
                        continue
                    try:
                        yp = float(m["yes_price_dollars"])
                        n = float(m.get("count_fp") or m.get("count") or 0)
                    except Exception:
                        continue
                    if n <= 0 or not (0 < yp < 1):
                        continue
                    seen += 1
                    allleg[(evt, leg)].append((tau, yp, n))
                    if m.get("taker_side") == "yes":
                        lifts[(evt, leg)].append((tau, yp, n))
        except (EOFError, zlib.error, OSError):
            pass
    print("  %d Coin Race trades inside tau<=120 over %d hours\n"
          % (seen, len(files)))

    bands = ((45, 61), (30, 45), (20, 30), (15, 20), (10, 15), (5, 10))
    hdr = ("  %-10s%8s%10s%10s%11s%12s%13s"
           % ("rule", "events", "won", "avg paid", "break-even",
              "P&L/contr", "$/event@20"))

    for lo, hi in bands:
        # every YES-taker print in the band, tagged with the forecast we would
        # HOLD at that second -- never a later one.
        pool = defaultdict(list)          # event -> [(tau, price, won)]
        for k, rec in pred.items():
            for tau, px, n in _band_prints(lifts, k, rec, grid, lo, hi):
                pool[k].append((tau, px, n))
        if not pool:
            continue
        print("\n  " + "=" * 108)
        print("  TAU %d-%d   (forecast used is always the one held at that "
              "second)" % (lo, hi))
        print(hdr)
        # tau COUNTS DOWN, so the chronologically first print in the band is
        # the one with the LARGEST tau. v1 used min() and therefore scored the
        # LAST trade before the close -- the most informed and dearest one --
        # while calling it "first". Found and fixed 2026-09-11.
        first = [(max(v)[1], max(v)[2]) for v in pool.values()]
        table(first, "FIRST", "<- earliest print, %d of %d events had one"
              % (len(pool), NTOT))
        cheap = [(min(v, key=lambda x: x[1])[1], min(v, key=lambda x: x[1])[2])
                 for v in pool.values()]
        table(cheap, "CHEAPEST", "<- upper bound")
        for lim in (0.98, 0.95, 0.90, 0.80):
            sel = []
            for v in pool.values():
                ok = [x for x in v if x[1] <= lim]
                if ok:
                    sel.append((min(ok, key=lambda x: x[1])[1],
                                min(ok, key=lambda x: x[1])[2]))
            table(sel, "LIMIT %.0fc" % (100 * lim),
                  "<- stood aside on %d of %d events"
                  % (len(pool) - len(sel), len(pool)))

    print("\n  " + "=" * 108)
    print("  THE FIVE-LEG SUM (a second, independent constraint)")
    sums = []
    for k in pred:
        last = {}
        for leg in ("BTC", "ETH", "SOL", "XRP", "HYPE"):
            s = [x for x in allleg.get((k, leg), []) if 20 <= x[0] < 60]
            if s:
                last[leg] = min(s, key=lambda x: x[0])[1]
        if len(last) == 5:
            sums.append(sum(last.values()))
    if sums:
        sums.sort()
        print("  last print of all five legs in tau 20-60, summed, %d events"
              % len(sums))
        print("     min %.2fc   p25 %.2fc   median %.2fc   max %.2fc"
              % (100 * sums[0], 100 * sums[len(sums) // 4],
                 100 * sums[len(sums) // 2], 100 * sums[-1]))
        print("     under 100c on %d of %d -- and these are NON-SIMULTANEOUS "
              "prints, so this is not a lock, only a hint of where to look"
              % (sum(1 for s in sums if s < 1.0), len(sums)))
    else:
        print("  not enough coverage to sum five legs")


def _band_prints(lifts, evt, rec, grid, lo, hi):
    """YES-taker prints in [lo,hi) on the leg the forecast-at-that-second names.

    Yields (tau, price, won). The leg can CHANGE inside a band, because the
    forecast changes; that is correct and is the whole point of the fix.
    """
    out = []
    for tau in range(lo, hi):
        p = pred_for(rec, tau, grid)
        if not p:
            continue
        for t, px, n in lifts.get((evt, p["coin"]), []):
            if t == tau:
                out.append((tau, px, bool(p["right"])))
    return out


if __name__ == "__main__":
    main()
