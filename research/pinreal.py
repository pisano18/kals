#!/usr/bin/env python3
"""pinreal.py -- what does this actually top out at, using only contracts that
really exist?

THE OPERATOR, 2026-09-15: "do it realistically like don't just pretend there's
more contracts than there is ... Go again and make it what's completely
absolutely grounded in reality."

He is right that the earlier projection cheated. It grew size and multiplied by
a fixed contracts-per-size number, which at day 22 wanted 158,787 contracts a
day out of a market that only offers about 220,000 -- and past that it simply
asked for contracts that do not exist.

WHAT THIS DOES INSTEAD. It replays every close in the ladder cache and SPENDS
against the real book, at each candidate size:

  * the close's contract budget is MAX_PER_CLOSE x SIZE, exactly as live
  * it walks the close's buyable moments in time order
  * at each moment it takes min(SIZE, what is on the ladder under the ceiling,
    what is left of the budget) -- so supply, not arithmetic, is the limit
  * it pays the real VWAP down that ladder, so a bigger bite costs more
  * it applies the measured live fill rate, because we lose some races

That gives contracts-per-close and cents-per-contract AT EACH SIZE from real
books. Multiply by the closes we really buy on per day and the answer stops
being a straight line.

SOURCE: results/pinlevels_rows.jsonl -- 13,984 gate-passing moments over 738
closes, each with the ask ladder it saw. Tape, and used only for what the tape
is valid for: what the market offered. No loss rate is taken from it.

WHAT IT STILL CANNOT SEE, and both cut the same way:
  * whether the book REFILLS after we eat it every close, every day. It refills
    today because nobody eats it.
  * whether taking more means taking the INFORMED sells we currently skip.
    RESULTS_select measured the counterparty as 26x more wrong when they
    actively sell to us. Our break-even loss rate is about 9% and we run at 4%.
So every number here is an OPTIMISTIC ceiling.

    python research/pinreal.py --selftest
    python research/pinreal.py
"""
import collections
import json
import os
import sys

CEILING = 0.98
MAX_PER_CLOSE = 2          # the live contract budget is this x SIZE
FILL_RATE = 0.91           # measured live: 63 of 69 orders filled
CLOSES_PER_DAY = 38        # measured: closes we actually bought on, recent mean
BANK_BRAKE = 5.88
ROWS = os.path.join("results", "pinlevels_rows.jsonl")
SIZES = (25, 50, 100, 150, 250, 400, 600, 900, 1400, 2000, 3000, 4500, 6000)


def fee(p):
    return 0.07 * p * (1.0 - p)


def walk(ladder, want, ceiling=CEILING):
    """(contracts, cost) available on this ladder at or under the ceiling."""
    n = c = 0.0
    for px, sz in ladder or ():
        px = float(px)
        if px > ceiling + 1e-9:
            break
        n += float(sz)
        c += float(sz) * px
    return n, c


MAX_PER_MARKET = 2         # the live cap on fills per market per close


def spend_close(moments, size, max_per_close=MAX_PER_CLOSE, ceiling=CEILING):
    """Spend a close's budget against its real moments, in time order.

    THE BOOK DEPLETES. The moments inside one close are snapshots of LARGELY
    THE SAME RESTING ORDERS, about a second apart. The first version of this
    function walked them and added up what each one showed, which quietly
    bought the same contracts several times over -- at size 3000 it claimed
    3,554 contracts a close from a book whose deepest single moment holds a
    median of 2,322. That is the exact error this file exists to avoid.

    So: what we have already taken from a market is removed from every later
    view of it. A later moment only contributes the depth that EXCEEDS what we
    already bought, which is the honest reading of "the same orders, seen
    again". The per-market fill cap applies too, as it does live.

    Returns (contracts, dollars_paid, gross_dollars_of_edge).
    """
    budget = max_per_close * size
    taken = collections.defaultdict(float)     # per market, already bought
    fills = collections.Counter()
    got = paid = edge = 0.0
    for m in moments:
        if budget <= 0:
            break
        tk = m.get("ticker")
        if fills[tk] >= MAX_PER_MARKET:
            continue
        want = min(size, budget)
        skip = taken[tk]              # these contracts are gone -- we took them
        seen = avail = 0.0
        cost = 0.0
        for px, sz in m["ladder"] or ():
            px = float(px)
            if px > ceiling + 1e-9:
                break
            sz = float(sz)
            # walk past the part of this ladder we have already bought
            if seen + sz <= skip:
                seen += sz
                continue
            usable = seen + sz - max(seen, skip)
            seen += sz
            take = min(usable, want - avail)
            if take <= 0:
                continue
            avail += take
            cost += take * px
            if avail >= want:
                break
        if avail <= 0:
            continue
        vwap = cost / avail
        f = m["fair"]
        gross = ((f - vwap) if m["want"] == "yes" else ((1.0 - f) - vwap))
        got += avail
        paid += cost
        edge += avail * (gross - fee(vwap))
        budget -= avail
        taken[tk] += avail
        fills[tk] += 1
    return got, paid, edge


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    # one moment, 100 contracts at 95c, fair 1.0 (a certain YES)
    mom = [{"ladder": [[0.95, 100.0]], "fair": 1.0, "want": "yes"}]
    g, p, e = spend_close(mom, 50)
    ck(g == 50.0 and abs(p - 50 * 0.95) < 1e-9,
       "a size-50 order takes 50 of the 100 available and pays 95c for them")
    g, p, e = spend_close(mom, 500)
    ck(g == 100.0,
       "a size-500 order takes only the 100 that EXIST -- supply is the limit, "
       "not the order size. This is the whole point of the file")
    # budget: two moments, size 50 -> budget 100, both fully taken
    two = mom * 3
    g, _, _ = spend_close(two, 50)
    ck(g == 100.0,
       "the close budget is 2 x size, so three 100-lots yield 100, not 300")
    # a deeper ladder costs more per contract
    deep = [{"ladder": [[0.90, 10.0], [0.96, 1000.0]], "fair": 1.0, "want": "yes"}]
    _, p10, _ = spend_close(deep, 10)
    _, p100, _ = spend_close(deep, 100)
    ck(abs(p10 / 10 - 0.90) < 1e-9 and (p100 / 100) > 0.95,
       "10 contracts pay 90.0c; 100 must reach into the 96c level and pay "
       "%.1fc -- a bigger bite really does cost more" % (100 * p100 / 100))
    # THE DEPLETION RULE -- the same book seen twice is not twice the book
    same = [{"ticker": "T", "ladder": [[0.95, 100.0]], "fair": 1.0, "want": "yes"},
            {"ticker": "T", "ladder": [[0.95, 100.0]], "fair": 1.0, "want": "yes"}]
    g, _, _ = spend_close(same, 100)
    ck(g == 100.0,
       "the SAME 100 contracts seen at two moments yields 100, not 200 -- "
       "moments inside a close are the same resting orders a second apart")
    grew = [{"ticker": "T", "ladder": [[0.95, 100.0]], "fair": 1.0, "want": "yes"},
            {"ticker": "T", "ladder": [[0.95, 150.0]], "fair": 1.0, "want": "yes"}]
    g, _, _ = spend_close(grew, 100)
    ck(g == 150.0,
       "but a book that GREW from 100 to 150 yields 150 -- genuinely new "
       "depth still counts")
    diff = [{"ticker": "A", "ladder": [[0.95, 100.0]], "fair": 1.0, "want": "yes"},
            {"ticker": "B", "ladder": [[0.95, 100.0]], "fair": 1.0, "want": "yes"}]
    g, _, _ = spend_close(diff, 100)
    ck(g == 200.0,
       "and two DIFFERENT markets are two different books -- depletion is "
       "per market, not global")
    many = [{"ticker": "T", "ladder": [[0.95, 1000.0]], "fair": 1.0, "want": "yes"}] * 5
    g, _, _ = spend_close(many, 50)
    ck(g == 100.0,
       "the per-market fill cap still binds: 5 chances at one market yields "
       "2 fills of 50, not 5")
    # NULL: nothing under the ceiling
    none = [{"ladder": [[0.99, 500.0]], "fair": 1.0, "want": "yes"}]
    ck(spend_close(none, 100) == (0.0, 0.0, 0.0),
       "NULL: a ladder entirely above the ceiling yields nothing at all")
    ck(spend_close([], 100) == (0.0, 0.0, 0.0), "and no moments yields nothing")
    # edge sign
    bad = [{"ladder": [[0.95, 100.0]], "fair": 0.5, "want": "yes"}]
    _, _, e = spend_close(bad, 50)
    ck(e < 0, "a coin flip bought at 95c produces NEGATIVE edge, not positive")
    print("pinreal selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0
    if not os.path.exists(ROWS):
        print("loaded nothing -- %s missing" % ROWS)
        return 0
    byclose = collections.defaultdict(list)
    for line in open(ROWS, encoding="utf-8"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("kind") != "row" or d.get("verdict") != "trade":
            continue
        if d.get("price", 1.0) > CEILING + 1e-9 or not d.get("ladder"):
            continue
        byclose[d["cs"]].append(d)
    for cs in byclose:
        byclose[cs].sort(key=lambda r: -r["tau"])      # time order
    if not byclose:
        print("loaded nothing -- no gate-passing moments with a ladder")
        return 0

    print("\n%d closes of real book, spent against the live contract budget "
          "(%d x size)." % (len(byclose), MAX_PER_CLOSE))
    print("Fill rate %.0f%% applied. %d closes bought per day (measured).\n"
          % (100 * FILL_RATE, CLOSES_PER_DAY))
    print("  %6s %11s %10s %11s %10s %12s %13s"
          % ("size", "budget", "got/close", "% of budget", "c/contract",
             "$/day", "bank needed"))
    print("  " + "-" * 82)
    best = (0.0, None)
    prev = None
    for s in SIZES:
        tot_c = tot_e = 0.0
        for cs, ms in byclose.items():
            g, p, e = spend_close(ms, s)
            tot_c += g
            tot_e += e
        n = len(byclose)
        per_close = tot_c / n * FILL_RATE
        cpc = (tot_e / tot_c * 100) if tot_c else 0.0
        daily = per_close * CLOSES_PER_DAY * cpc / 100.0
        bank = s * BANK_BRAKE
        flag = ""
        if prev is not None and daily < prev * 1.02:
            flag = "  <== growth has stopped"
        if daily > best[0]:
            best = (daily, s)
        print("  %6d %11.0f %10.0f %10.0f%% %9.2fc %11s %12s%s"
              % (s, MAX_PER_CLOSE * s, per_close,
                 100 * per_close / (MAX_PER_CLOSE * s), cpc,
                 "$%.0f" % daily, "$%s" % "{:,.0f}".format(bank), flag))
        prev = daily
    print("\n  PEAK: $%.0f a day at size %d, needing a bank of $%s."
          % (best[0], best[1], "{:,.0f}".format(best[1] * BANK_BRAKE)))
    print("  Past that the budget grows and the book does not fill it, so the")
    print("  extra size buys nothing and the worse average price costs money.")
    print("\n  AND THIS IS STILL OPTIMISTIC. It assumes the book refills after we")
    print("  eat it every close every day -- it refills now because nobody eats")
    print("  it -- and that taking more does not mean taking the informed sells")
    print("  we currently skip, which RESULTS_select measured as 26x more wrong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
