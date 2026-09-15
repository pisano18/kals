#!/usr/bin/env python3
"""pinbooktrend.py -- the KALSHI order book, day by day: is it getting deeper
or thinner, how high could the size cap go, and does our own buying move it?

NOT TO BE CONFUSED WITH `pinbook.py`, which asks whether the SOURCE EXCHANGE
books (feed_data/bitstamp) warn of a jump. This file is about the Kalshi book
we actually trade against, and it is a trend tracker rather than a study.

THE OPERATOR, 2026-09-15: "start tracking the order books and measuring and
trend within them ... Both for trends and to see how it changes if and when I
bet. Also to get an idea of how high the cap will go."

SOURCE, and why it is cheap. Every close the bot already writes a
`close_summary` carrying a depth curve: how many contracts were on offer at
every moment it could have bought, and how many of those moments would still
fill an order of 1, 5, ... 2000 contracts. That is 96 closes a day, free, and
it runs back to 2026-09-08. Nothing here re-walks the book tape.

THREE QUESTIONS, THREE SECTIONS.

  1. TREND  -- is the book deeper or thinner than it was? Per ET day.
  2. CAP    -- the largest size that still fills at most moments. This is the
               number behind "how high can the cap go", measured per day so it
               can be watched rather than assumed.
  3. IMPACT -- does our own buying thin the book behind us?

WHAT IT CANNOT SAY. The depth curve before 2026-09-15 samples the TOUCH -- the
contracts at the single best price. Since the sweep (AMENDMENT 35) the bot buys
down the ladder, so the touch understates what we can fill. AMENDMENT 44 added
a per-market LADDER sample and extended the curve past 250; days without it are
marked, and the two are never mixed in one column.

    python research/pinbooktrend.py --selftest
    python research/pinbooktrend.py
    python research/pinbooktrend.py --days 3
"""
import collections
import datetime
import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZES = (25, 50, 125, 250, 500, 750, 1000, 2000)
FILL_BAR = 0.50          # "most moments" = this share of buyable moments


def et(t):
    return datetime.datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S") - datetime.timedelta(hours=4)


def cap_at(kept, bar=FILL_BAR):
    """Largest logged size still fillable at `bar` of the moments on offer.

    `kept` maps size -> moments that could fill it. Returns (size, share) or
    (None, None). Reads only sizes the log actually carries, so a curve that
    stops at 250 can never be reported as though it measured 2000."""
    if not kept:
        return None, None
    base = kept.get("1")
    if not base:
        return None, None
    for s in sorted((int(k) for k in kept), reverse=True):
        share = kept[str(s)] / float(base)
        if share >= bar:
            return s, share
    return None, None


def load():
    out = []
    for p in sorted(glob.glob(os.path.join(REPO, "results", "pinrun-live-*.jsonl"))):
        for line in open(p, encoding="utf-8"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("kind") == "close_summary" and d.get("depth"):
                out.append(d)
    out.sort(key=lambda d: d["t"])
    return out


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    k = {"1": 100, "250": 80, "500": 50, "1000": 10}
    s, sh = cap_at(k, 0.50)
    ck(s == 500 and abs(sh - 0.50) < 1e-9,
       "with half the moments holding 500, the cap reads 500")
    ck(cap_at(k, 0.75)[0] == 250,
       "at a stricter 75% bar the same book only supports 250")
    ck(cap_at(k, 0.05)[0] == 1000,
       "and at a loose 5% bar it reads 1000 -- the bar is the whole judgement")
    ck(cap_at({"1": 100, "250": 90}, 0.50)[0] == 250,
       "a curve that only goes to 250 reports AT MOST 250 -- an old log must "
       "never look like it measured a size it never recorded")
    ck(cap_at({"1": 0}, 0.5) == (None, None) and cap_at({}, 0.5) == (None, None)
       and cap_at(None, 0.5) == (None, None),
       "NULL: an empty or missing curve reports nothing, never a zero that "
       "would read as 'the book supports one contract'")
    thin = {"1": 100, "250": 10, "500": 2}
    deep = {"1": 100, "250": 90, "500": 80}
    ck(cap_at(deep, 0.5)[0] > cap_at(thin, 0.5)[0],
       "a deeper book reports a larger cap than a thinner one")
    print("pinbooktrend selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0
    limit = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else None

    rows = load()
    if not rows:
        print("loaded nothing -- no close summaries with a depth curve")
        return 0
    byday = collections.defaultdict(list)
    for d in rows:
        byday[et(d["t"]).strftime("%Y-%m-%d")].append(d)
    days = sorted(byday)
    if limit:
        days = days[-limit:]

    print("\n  1. IS THE BOOK GETTING DEEPER OR THINNER?\n")
    print("  Contracts on offer at the moments we could have bought, per ET day.")
    print("  'touch' is the best price only. 'ladder' is everything up to our 98c")
    print("  ceiling and exists from 2026-09-15 (AMENDMENT 44).\n")
    # NO "TOTAL OFFERED" COLUMN. The obvious one -- summing depth["total"]
    # across a day -- counts the SAME resting order once per look, thousands of
    # times a close, and produced a headline 1.5 BILLION contracts for 09-14.
    # It measures how often we looked, not how much was there. Medians of
    # per-close medians do not have that problem.
    print("  %-11s %7s %9s %10s %10s %10s %11s" %
          ("day", "closes", "moments", "touch med", "touch p75", "touch max",
           "ladder med"))
    print("  " + "-" * 76)
    for d in days:
        rs = byday[d]
        med = sorted(r["depth"]["median"] for r in rs)
        p75 = sorted(r["depth"]["p75"] for r in rs)
        mx = sorted(r["depth"]["max"] for r in rs)
        lad = sorted(r["ladder"]["median"] for r in rs if r.get("ladder"))
        print("  %-11s %7d %9d %10.0f %10.0f %10.0f %11s" %
              (d, len(rs), sum(r["depth"]["n"] for r in rs),
               med[len(med) // 2], p75[len(p75) // 2], mx[len(mx) // 2],
               ("%.0f" % lad[len(lad) // 2]) if lad else "-"))

    print("\n  2. HOW HIGH COULD THE CAP GO?\n")
    print("  Share of buyable moments that could fill an order of each size.")
    print("  CAP is the largest size still fillable at %.0f%% of them.\n" % (100 * FILL_BAR))
    hdr = "  %-11s" % "day" + "".join("%7s" % s for s in SIZES) + "%8s %11s" % ("CAP", "logged to")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for d in days:
        agg = collections.Counter()
        for r in byday[d]:
            for k, v in r["depth"]["kept"].items():
                agg[int(k)] += v
        base = agg.get(1) or 1
        cells = "".join(("%6.0f%%" % (100 * agg[s] / base)) if s in agg else "%7s" % "-"
                        for s in SIZES)
        cap, _ = cap_at({str(k): v for k, v in agg.items()})
        print("  %-11s%s%8s %11s" % (d, cells, ("%d" % cap) if cap else "-",
                                     max(agg) if agg else "-"))
    print("\n  A '-' means that day's log never recorded that size, not that the book")
    print("  could not fill it. The curve only reaches past 250 from 2026-09-15, so")
    print("  earlier CAP figures are a FLOOR, not a measurement.")

    print("\n  3. DOES OUR BUYING MOVE THE BOOK?\n")
    fired = [d for d in rows if d.get("fired")]
    notf = [d for d in rows if not d.get("fired")]
    print("  %-14s %8s %13s %12s %12s" %
          ("", "closes", "touch median", "touch p75", "touch max"))
    for lab, g in (("we bought", fired), ("we passed", notf)):
        if not g:
            continue
        m = sorted(x["depth"]["median"] for x in g)
        p = sorted(x["depth"]["p75"] for x in g)
        mx = sorted(x["depth"]["max"] for x in g)
        print("  %-14s %8d %13.0f %12.0f %12.0f" %
              (lab, len(g), m[len(m) // 2], p[len(p) // 2], mx[len(mx) // 2]))
    print("\n  A close we bought on is DEEPER, not thinner -- we buy where there is")
    print("  something to buy. That is SELECTION, not impact, and it is why this")
    print("  section cannot yet answer the question. True impact needs the book at")
    print("  the second AFTER our fill. AMENDMENT 36 stores the 8 levels at every")
    print("  signal, so a before/after on one market becomes measurable once two")
    print("  signals land on the same market in one close often enough to count.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
