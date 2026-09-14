#!/usr/bin/env python3
# VERSION: 2026-09-14-e1
"""pinearly.py -- what price is on offer BEFORE the last 30 seconds, and would
a resting bid ever have been hit?

TWO OPERATOR QUESTIONS, ONE TAPE.

(1) 2026-09-14: "Think about buying before the 30 seconds for better deals,
    then hedging once we have our certainty if needed."

    The bot only looks in the last 30 seconds. Earlier, the outcome is less
    obvious to everyone, so the winning side should be CHEAPER -- and a
    cheaper entry survives a much higher loss rate. What it costs is accuracy:
    research/pinwarn.py, 19,034 closes rebuilt from the index, measures the
    model's own error rate at 0.17% when entry is capped at 30 seconds and
    0.52% when it may start at 55 -- THREE TIMES WORSE. So the question is
    purely whether the price falls faster than the accuracy does.

    THE HARD BOUNDARY, and it is not a tuning choice: the settlement window is
    SIXTY SECONDS. At tau=60 not one print is locked and the model's entire
    edge is zero. Anything earlier than that is a coin flip with extra steps.
    So the whole idea lives or dies in the 30-to-60 second band.

(2) "Does Kalshi allow you to post a buy order like 'will buy for 95c'?"

    It does -- pinrun deliberately never rests (time_in_force is
    immediate-or-cancel and post_only is forced False), so we only ever pay
    what is already on the screen. If the winning side's ask DROPS to 95c at
    some point in the final minute, a resting bid would plausibly have been
    filled there instead.

WHAT THIS CAN AND CANNOT SHOW. The `ticker` tape records what was QUOTED. A
quote is not a fill: we would have been racing for it, and CLAUDE.md rule 5
puts the gap between "an offer was sitting there" and "someone actively sold
it to us" at 31x. So every price here is the BEST case, and the resting-bid
number is weaker still -- it says the ask reached 95c, not that anyone would
have crossed to a bid of ours that was not there. It is a screen, not a proof.

THE SIDE MATTERS AND IS EASY TO GET BACKWARDS. Buying NO at price q is selling
YES at 1-q, so the NO ask is `1 - yes_bid`, NOT `1 - yes_ask`. Using the wrong
one makes the losing side look cheap and would invent an edge out of nothing.
"""
import argparse
import glob
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gzsalvage                                               # noqa: E402

SERIES = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
          "KXBNB15M", "KXHYPE15M", "KXNEAR15M", "KXZEC15M", "KXADA15M",
          "KXBCH15M", "KXTON15M")
WINDOW = 60
BANDS = ((0, 10), (10, 20), (20, 30), (30, 40), (40, 50), (50, 60))
REST_AT = 0.95


def win_ask(msg, result):
    """The ask on the side that WON, in dollars, or None.

    Buying NO at q is selling YES at 1-q, so the NO ask is 1 - yes_bid.
    """
    def f(k):
        v = msg.get(k)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    if result == "yes":
        a, sz = f("yes_ask_dollars"), f("yes_ask_size_fp")
    elif result == "no":
        b = f("yes_bid_dollars")
        a = None if b is None else 1.0 - b
        sz = f("yes_bid_size_fp")
    else:
        return None
    if a is None or a <= 0.0 or a >= 1.0:
        return None
    return (a, sz or 0.0)


def load_markets(path):
    """{ticker: (close_epoch, result)} for the series we trade."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    for ser, rows in (d or {}).items():
        if ser not in SERIES:
            continue
        for r in rows or []:
            res = r.get("result")
            cl = r.get("close")
            if res in ("yes", "no") and cl:
                out[r["ticker"]] = (int(float(cl)), res)
    return out


def scan(tick_dir, markets, say=print, limit=None):
    """{ticker: {band: best ask seen}} plus the best ask anywhere in the minute.

    One pass, streaming. The raw line is checked for the series prefix before
    any JSON parsing -- the tape is 879 MB and most of it is series we do not
    trade.
    """
    best = defaultdict(dict)
    anyb = {}
    files = sorted(glob.glob(os.path.join(tick_dir, "*.jsonl.gz")))
    if limit:
        files = files[-limit:]
    for i, p in enumerate(files):
        for line in gzsalvage.iter_lines(p):
            if "15M-" not in line:
                continue
            try:
                m = json.loads(line)
            except ValueError:
                continue
            msg = m.get("msg") or {}
            tk = msg.get("market_ticker")
            got = markets.get(tk)
            if not got:
                continue
            close_s, result = got
            try:
                ts = int(float(msg.get("ts")))
            except (TypeError, ValueError):
                continue
            tau = close_s - ts
            if not (0 < tau <= WINDOW):
                continue
            wa = win_ask(msg, result)
            if wa is None:
                continue
            ask, size = wa
            for lo, hi in BANDS:
                if lo < tau <= hi:
                    cur = best[tk].get((lo, hi))
                    if cur is None or ask < cur[0]:
                        best[tk][(lo, hi)] = (ask, size, tau)
                    break
            if tk not in anyb or ask < anyb[tk][0]:
                anyb[tk] = (ask, size, tau)
        if say and (i + 1) % 50 == 0:
            say("    %d/%d files, %d markets" % (i + 1, len(files), len(best)))
    return best, anyb


def report(best, anyb, say=print):
    lines = []
    w = lines.append
    w("  THE WINNING SIDE'S PRICE, BY HOW LONG BEFORE THE CLOSE")
    w("")
    w("  This is the cheapest the side that WON was ever offered at, in each")
    w("  band. The bot only looks at 0-30s today.")
    w("")
    w("  seconds out | markets | median cheapest | p25    | p75    | under 95c")
    w("  ------------|---------|-----------------|--------|--------|----------")
    for lo, hi in BANDS:
        v = sorted(b[(lo, hi)][0] for b in best.values() if (lo, hi) in b)
        if not v:
            continue
        u95 = sum(1 for x in v if x <= REST_AT)
        w("  %3d-%-3d s   | %7d | %14.1fc | %5.1fc | %5.1fc | %4d (%4.1f%%)"
          % (lo, hi, len(v), 100 * v[len(v) // 2], 100 * v[len(v) // 4],
             100 * v[3 * len(v) // 4], u95, 100.0 * u95 / len(v)))
    w("")
    v = sorted(x[0] for x in anyb.values())
    if v:
        u = sum(1 for x in v if x <= REST_AT)
        w("  ANYWHERE in the final minute: %d markets, median cheapest %.1fc, "
          "and %d (%.1f%%) touched %.0fc or better."
          % (len(v), 100 * v[len(v) // 2], u, 100.0 * u / len(v),
             100 * REST_AT))
    w("")
    w("  Every price here is a QUOTE, not a fill. We would have been racing")
    w("  for it, and the tape's population is not ours (CLAUDE.md rule 5).")
    w("  Treat all of it as the best case.")
    txt = "\n".join(lines)
    if say:
        say(txt)
    return txt


def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    # THE SIDE CONVERSION, which is the one thing that would invent an edge
    m = {"yes_ask_dollars": "0.97", "yes_bid_dollars": "0.93",
         "yes_ask_size_fp": "40", "yes_bid_size_fp": "25"}
    ck(win_ask(m, "yes") == (0.97, 40.0),
       "when YES wins, the price to pay is the YES ask (97c)")
    a, s = win_ask(m, "no")
    ck(abs(a - 0.07) < 1e-9 and s == 25.0,
       "when NO wins, the price to pay is 1 - the YES BID = 7c, not "
       "1 - the yes ask (3c). Using the ask would price the winning side "
       "BELOW the market and manufacture an edge out of the spread (%r)" % a)
    ck(win_ask(m, None) is None and win_ask(m, "") is None,
       "a market with no settlement on file is not scored")
    ck(win_ask({"yes_ask_dollars": "1.0"}, "yes") is None,
       "an ask at 100c is NOT a price -- there is no profit in it and it is "
       "how `no offer` is defined everywhere else in this project")
    ck(win_ask({"yes_ask_dollars": "0"}, "yes") is None,
       "and a zero ask is a broken quote, not a free contract")

    # the band assignment, at both edges
    mk = {"T": (1000, "yes")}
    rows = []
    for ts, ask in ((970, "0.90"), (961, "0.80"), (940, "0.99")):
        rows.append({"msg": {"market_ticker": "T", "ts": ts,
                             "yes_ask_dollars": ask, "yes_ask_size_fp": "5"}})
    best = defaultdict(dict)
    for r in rows:
        msg = r["msg"]
        tau = 1000 - msg["ts"]
        ask = float(msg["yes_ask_dollars"])
        for lo, hi in BANDS:
            if lo < tau <= hi:
                cur = best["T"].get((lo, hi))
                if cur is None or ask < cur[0]:
                    best["T"][(lo, hi)] = (ask, 5.0, tau)
                break
    ck((20, 30) in best["T"] and abs(best["T"][(20, 30)][0] - 0.90) < 1e-9,
       "a quote 30s out lands in the 20-30s band, at its edge")
    ck((30, 40) in best["T"] and abs(best["T"][(30, 40)][0] - 0.80) < 1e-9,
       "and one 39s out lands in 30-40s")
    ck(abs(best["T"][(50, 60)][0] - 0.99) < 1e-9,
       "and one 60s out lands in 50-60s -- the last band with any locked "
       "print at all")
    txt = report(best, {"T": (0.80, 5.0, 39)}, say=None)
    ck("QUOTE, not a fill" in txt,
       "and the report carries the caveat rather than leaving it in a "
       "docstring nobody opens")
    print("pinearly selftest: %d checks OK" % n[0])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--ticks", default="C:/kals/kalshi_data/ticker")
    ap.add_argument("--markets", default="C:/kals/fulltape/markets.json")
    ap.add_argument("--files", type=int, default=0,
                    help="only the newest N hourly files (0 = all)")
    ap.add_argument("--out", default=os.path.join(REPO, "results",
                                                  "RESULTS_early.md"))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_EARLY_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    mk = load_markets(a.markets)
    print("  %d settled markets on the series we trade" % len(mk))
    if not mk:
        print("pinearly: loaded nothing -- no settled market on file")
        return 0
    best, anyb = scan(a.ticks, mk, limit=(a.files or None))
    if not best:
        print("pinearly: loaded nothing -- no quote fell inside a close window")
        return 0
    txt = report(best, anyb)
    nl = chr(10)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("# RESULTS_early -- the winning side's price before the last "
                 "30 seconds" + nl + nl + "```" + nl + txt + nl + "```" + nl)
    print("  wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
