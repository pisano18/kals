#!/usr/bin/env python3
"""pinarb.py -- the five legs of a Coin Race must sum to exactly $1. Do they?

THE OPERATOR, 2026-09-15: "that's why we need other strategies going. Continue
that branch of research and testing."

THE IDEA, and why it is different in kind from everything else here. A Coin
Race has five legs and EXACTLY ONE pays $1. So:

    buy all five YES legs   -> you are paid $1, always, whoever wins
    buy all five NO legs    -> you are paid $4, always, since four legs lose

If the five YES asks sum to less than $1 after fees, that is money with **no
opinion about crypto in it at all** -- no forecast, no model, no edge to decay.
It does not care whether our index is right. The pin cannot say that about a
single trade it makes.

RESULTS_coinrace noticed this once ("the five legs summed 87c once in 26
events") and could not settle it, because it looked at TRADE PRINTS, which
happen at different moments. A sum built from prices seconds apart is not a
basket you could have bought. This file uses the `ticker` channel, which
publishes a leg's top of book every time it changes, and only counts a moment
when ALL FIVE legs are fresh together.

WHAT IT REPORTS, and the three things that would make it a mirage:
  STALENESS  a leg that has not updated in a minute may not be there. Every
             result is broken out by how fresh the slowest leg was.
  SIZE       the basket is limited by the THINNEST leg. One leg offering 3
             contracts caps the whole thing at 3.
  ALL-OR-NOTHING  five fills are needed. Four fills and a miss leaves an open
             position, which is the risk this strategy actually carries.

READ-ONLY. Recorded tape, no orders.

    python research/pinarb.py --selftest
    python research/pinarb.py --hours 72
"""
import argparse
import collections
import glob
import gzip
import json
import math
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
DATA = r"C:\kals\kalshi_data"
COINS = ("BTC", "ETH", "SOL", "XRP", "HYPE")
FRESH = (1, 5, 30, 300)          # seconds the slowest leg may be stale


def fee(p, n=1.0):
    """Kalshi's taker fee, rounded up to the cent-hundredth."""
    return math.ceil(0.07 * n * p * (1 - p) * 10000 - 1e-9) / 10000


def basket_long(asks):
    """(cost, fee) of buying one of each YES leg. Pays exactly $1."""
    return sum(asks), sum(fee(p) for p in asks)


def basket_short(bids):
    """(cost, fee) of buying one NO on every leg. Pays exactly $4.

    Buying NO at (1 - yes_bid) is the same trade as selling YES at the bid."""
    nos = [1.0 - b for b in bids]
    return sum(nos), sum(fee(p) for p in nos)


def edge_long(asks):
    c, f = basket_long(asks)
    return 1.0 - c - f


def edge_short(bids):
    c, f = basket_short(bids)
    return 4.0 - c - f


def scan_files(files, on_row):
    """Feed every CRYPTOLEAD ticker message to `on_row`, tolerating the
    truncated gzip of an hour still being written."""
    n = 0
    for fp in files:
        try:
            with gzip.open(fp, "rt") as fh:
                for line in fh:
                    if "CRYPTOLEAD" not in line or '"ticker"' not in line:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                    except Exception:                        # noqa: BLE001
                        continue
                    n += 1
                    on_row(m)
        except (EOFError, zlib.error, OSError):
            continue
    return n


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    ck(abs(fee(0.20) - 0.0112) < 1e-9, "a 20c leg costs 1.12c to take")
    ck(fee(0.01) < fee(0.5), "and the fee is tiny at the ends, largest at 50c")

    # a perfectly priced race: the five legs sum to exactly a dollar
    even = [0.20] * 5
    ck(abs(sum(even) - 1.0) < 1e-12 and edge_long(even) < 0,
       "five legs at 20c sum to exactly $1, so after fees the basket LOSES "
       "%.1fc -- fair pricing is not an opportunity" % (-100 * edge_long(even)))
    cheap = [0.18, 0.18, 0.18, 0.18, 0.18]
    ck(edge_long(cheap) > 0,
       "five legs at 18c sum to 90c and the basket makes %.1fc for certain"
       % (100 * edge_long(cheap)))
    dear = [0.30, 0.25, 0.25, 0.20, 0.15]
    ck(edge_long(dear) < 0, "and a sum of $1.15 is a guaranteed loss")

    # the NO side, which is the same trade seen from the other end
    ck(edge_short([0.25] * 5) > 0,
       "if the five BIDS sum to $1.25 then buying five NOs makes %.1fc: four "
       "of them pay out, always" % (100 * edge_short([0.25] * 5)))
    ck(edge_short([0.20] * 5) < 0,
       "and bids summing to exactly $1 leave nothing after fees")
    ck(abs(basket_short([0.0] * 5)[0] - 5.0) < 1e-12,
       "with no bids at all, five NOs cost the full $5 to win $4 -- the "
       "arithmetic cannot be fooled into calling an empty book an opportunity")

    # NULL: a real, tight race book is NOT an opportunity
    real = [0.68, 0.22, 0.06, 0.03, 0.02]          # sums to 1.01
    ck(edge_long(real) < 0,
       "NULL: a plausible live book summing to $1.01 shows no edge (%.2fc)"
       % (100 * edge_long(real)))
    ck(edge_long([0.0] * 5) > 0.9,
       "and a free basket would be caught -- the test can find one when it "
       "is there")
    print("pinarb selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=72)
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0

    files = sorted(glob.glob(os.path.join(DATA, "ticker", "2026*.jsonl.gz")))[-a.hours:]
    if not files:
        print("loaded nothing -- no ticker files")
        return 0

    # per event: {coin: (yes_bid, yes_bid_size, yes_ask, yes_ask_size, ts_ms)}
    book = collections.defaultdict(dict)
    best = {}                     # event -> best long edge seen (edge, size, stale, ts)
    best_s = {}
    hits = collections.Counter()
    real_moments = []            # every leg fresh, and a whole contract on each
    hit_events = collections.defaultdict(set)
    sizes = collections.defaultdict(list)
    seen_events = set()

    def on_row(m):
        tk = m.get("market_ticker") or ""
        evt, _, coin = tk.rpartition("-")
        if coin not in COINS:
            return
        try:
            ts = int(m.get("ts_ms") or 0)
            yb = float(m.get("yes_bid_dollars") or 0)
            ya = float(m.get("yes_ask_dollars") or 0)
            ybs = float(m.get("yes_bid_size_fp") or 0)
            yas = float(m.get("yes_ask_size_fp") or 0)
        except (TypeError, ValueError):
            return
        seen_events.add(evt)
        book[evt][coin] = (yb, ybs, ya, yas, ts)
        legs = book[evt]
        if len(legs) < 5:
            return
        stale = (ts - min(v[4] for v in legs.values())) / 1000.0
        # LONG: buy every YES. Needs a real offer with size on all five.
        asks = [legs[c][2] for c in COINS]
        asz = [legs[c][3] for c in COINS]
        if all(0 < p < 1 for p in asks) and all(s > 0 for s in asz):
            e = edge_long(asks)
            if e > 0:
                for f in FRESH:
                    if stale <= f:
                        hits[("long", f)] += 1
                        hit_events[("long", f)].add(evt)
                        sizes[("long", f)].append(min(asz))
                        break
                if evt not in best or e > best[evt][0]:
                    best[evt] = (e, min(asz), stale, ts)
                if stale <= 1.0 and min(asz) >= 1.0:
                    real_moments.append(("long", evt, e, min(asz), list(asks)))
        # SHORT: buy every NO, i.e. sell every YES at its bid.
        bids = [legs[c][0] for c in COINS]
        bsz = [legs[c][1] for c in COINS]
        if all(0 < p < 1 for p in bids) and all(s > 0 for s in bsz):
            e = edge_short(bids)
            if e > 0:
                for f in FRESH:
                    if stale <= f:
                        hits[("short", f)] += 1
                        hit_events[("short", f)].add(evt)
                        sizes[("short", f)].append(min(bsz))
                        break
                if evt not in best_s or e > best_s[evt][0]:
                    best_s[evt] = (e, min(bsz), stale, ts)
                if stale <= 1.0 and min(bsz) >= 1.0:
                    real_moments.append(("short", evt, e, min(bsz), list(bids)))

    n = scan_files(files, on_row)
    print("\n%d Coin Race ticker updates over %d hours, %d races"
          % (n, len(files), len(seen_events)))
    if not n:
        print("loaded nothing -- no race ticker messages in those files")
        return 0

    print("\nMOMENTS WHERE THE FIVE LEGS DID NOT SUM TO $1")
    print("  %-7s %-22s %8s %8s %10s %12s"
          % ("basket", "all legs fresh within", "moments", "races", "med size", "med profit"))
    any_hit = False
    for side, payout in (("long", "buy 5 YES, paid $1"), ("short", "buy 5 NO, paid $4")):
        for f in FRESH:
            k = (side, f)
            if not hits[k]:
                continue
            any_hit = True
            sz = sorted(sizes[k])
            med = sz[len(sz) // 2]
            print("  %-7s %-22s %8d %8d %10.0f %12s"
                  % (side, "%d s" % f, hits[k], len(hit_events[k]), med, "see below"))
    if not any_hit:
        print("  NONE. Not one moment in %d races had the five legs priced so a "
              "basket paid." % len(seen_events))
        print("\n  That is the honest answer: the market keeps the five legs "
              "summed to a dollar,")
        print("  which is what a market with any attention on it should do.")
        return 0

    print("\n  ONLY WHAT WAS ACTUALLY BUYABLE -- every leg fresh within one second")
    print("  and at least one whole contract on the thinnest leg:")
    if not real_moments:
        print("    NONE. Every apparent chance was a stale quote or a fraction")
        print("    of a contract.")
    else:
        byrace = {}
        for side, evt, e, sz, px in real_moments:
            k = (side, evt)
            if k not in byrace or e > byrace[k][0]:
                byrace[k] = (e, sz, px)
        print("    %-6s %-13s %9s %7s   %s"
              % ("basket", "race", "profit", "size", "the five prices"))
        tot = 0.0
        for (side, evt), (e, sz, px) in sorted(byrace.items(), key=lambda kv: -kv[1][0]):
            tot += e * min(sz, 100)
            print("    %-6s %-13s %8.2fc %7.0f   %s"
                  % (side, evt[-12:], 100 * e, sz,
                     " ".join("%.2f" % x for x in px)))
        print("    %d chances over %d races -- at the sizes shown (capped at 100 "
              "a leg) that is $%.2f in total." % (len(byrace), len(seen_events), tot))

    for label, store in (("LONG (buy all five YES)", best),
                         ("SHORT (buy all five NO)", best_s)):
        if not store:
            continue
        rows = sorted(store.items(), key=lambda kv: -kv[1][0])[:10]
        print("\n  BEST %s -- the ten fattest moments" % label)
        print("    %-30s %10s %8s %8s" % ("race", "profit", "size", "stale"))
        for evt, (e, sz, stale, ts) in rows:
            print("    %-30s %9.2fc %8.0f %7.1fs" % (evt[-12:], 100 * e, sz, stale))
        tot = sum(v[0] * v[1] for v in store.values())
        print("    total if every one were filled at its size: $%.2f over %d races"
              % (tot, len(store)))
    print("\n  A basket needs ALL FIVE fills. Four fills and a miss leaves an "
          "open position,")
    print("  which is the real risk here -- not the arithmetic.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
