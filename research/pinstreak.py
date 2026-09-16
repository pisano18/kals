#!/usr/bin/env python3
"""pinstreak.py -- bursts and droughts. Do the buys clump, and does a quiet
stretch tell us anything about the next one?

THE OPERATOR, 2026-09-15: "the idea is like how right now we haven't had a
contract in 3 hours but other times we get like 3 buys an hour."

That is a different question from the hour of the day (pinwhen.py answered that
one: the clock is a proxy for how calm the market is). This one asks about the
SHAPE of the arrivals:

  1. DO THEY CLUMP? Compare buys-per-hour against the flattest possible world --
     a coin flip per close at our own average rate. If the real spread is wider,
     the chances genuinely arrive in bunches. The measure is the index of
     dispersion, variance / mean: 1.0 is perfectly random, above 1 is clumped.
  2. DOES A DROUGHT PREDICT A DROUGHT? P(this close buys | the last one did)
     against P(this close buys | the last k did not). If those are the same
     number, a dry spell says nothing about the next fifteen minutes and there
     is nothing to wait for.
  3. HOW LONG IS A NORMAL DRY SPELL? The distribution of gaps between buys, so
     a live drought can be read against it -- which is the practical use: at
     what point is a silence long enough to suspect the BOT rather than the
     market.

Every count is per 15-minute CLOSE (hard rule 4), from the live bot's own close
summaries, with closes inside a known outage dropped (results/DOWNTIME.json) so
our downtime never reads as a quiet market.

    python research/pinstreak.py --selftest
    python research/pinstreak.py
"""
import collections
import datetime as dt
import glob
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import downtime                                              # noqa: E402

CLOSE = 900
OUT = os.path.join(REPO, "results", "STREAKS.md")


def dispersion(counts):
    """variance / mean of counts per period. 1.0 is a random (Poisson) world,
    above 1 means the events clump, below 1 means they are spread out."""
    counts = list(counts)
    if len(counts) < 2:
        return None
    m = sum(counts) / float(len(counts))
    if m <= 0:
        return None
    v = sum((c - m) ** 2 for c in counts) / (len(counts) - 1)
    return v / m


def dispersion_p(counts, base_rate, per_period, n_shuffle=2000, seed=99):
    """How unusual that clumping is, against worlds built by flipping a coin at
    our own rate for every close. No Poisson assumption: the null world is
    simulated with the same number of periods and closes per period."""
    obs = dispersion(counts)
    if obs is None:
        return None, None
    rng = random.Random(seed)
    worse = 0
    for _ in range(n_shuffle):
        sim = [sum(1 for _ in range(per_period) if rng.random() < base_rate)
               for _ in counts]
        d = dispersion(sim)
        if d is not None and d >= obs:
            worse += 1
    return obs, (worse + 1) / float(n_shuffle + 1)


def gaps_between(flags):
    """Lengths of the dry runs between buys, in closes. [1,0,0,1] -> [2]."""
    out, run, seen = [], 0, False
    for f in flags:
        if f:
            if seen:
                out.append(run)
            seen, run = True, 0
        elif seen:
            run += 1
    return out


def after_run(flags, k):
    """P(this close buys | the k closes before it all did not)."""
    hit = n = 0
    for i in range(k, len(flags)):
        if any(flags[i - j - 1] for j in range(k)):
            continue
        n += 1
        hit += 1 if flags[i] else 0
    return (hit / float(n) if n else None), n


def after_hit(flags):
    """P(this close buys | the one before it did)."""
    hit = n = 0
    for i in range(1, len(flags)):
        if flags[i - 1]:
            n += 1
            hit += 1 if flags[i] else 0
    return (hit / float(n) if n else None), n


def quantile(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def load(spans):
    """[(close_epoch, fired)] in time order, outages dropped."""
    rows = {}
    for p in sorted(glob.glob(os.path.join(REPO, "results", "pinrun-live-*.jsonl"))):
        for line in open(p, encoding="utf-8", errors="ignore"):
            if '"close_summary"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            cs = d.get("close")
            if cs and downtime.lost_seconds(cs - 30, cs, spans) == 0:
                rows[cs] = bool(d.get("fired"))
    return sorted(rows.items())


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    ck(abs(dispersion([2, 2, 2, 2]) - 0.0) < 1e-12,
       "counts that never vary have zero spread")
    ck(dispersion([0, 0, 8, 0, 0, 8]) > 3,
       "and all-or-nothing counts are strongly clumped (%.1f)"
       % dispersion([0, 0, 8, 0, 0, 8]))
    ck(dispersion([1]) is None and dispersion([0, 0]) is None,
       "NULL: one period, or no events at all, has no clumping to measure")

    rng = random.Random(5)
    flat = [sum(1 for _ in range(4) if rng.random() < 0.5) for _ in range(400)]
    d, p = dispersion_p(flat, 0.5, 4, 400, seed=11)
    ck(0.3 < d < 0.8 and p > 0.05,
       "NULL: a world built from fair coin flips reads as random (%.2f, p %.2f). "
       "Note it is 0.5, not 1.0: with only 4 closes in an hour the count is "
       "bounded, so the honest baseline is the SIMULATED world, never the "
       "textbook 1.0" % (d, p))
    clumped = [8 if i % 4 == 0 else 0 for i in range(400)]
    d2, p2 = dispersion_p(clumped, 0.5, 4, 400, seed=12)
    ck(d2 > 2 and p2 < 0.01,
       "while planted bursts are caught (%.1f, p %.3f)" % (d2, p2))

    ck(gaps_between([1, 0, 0, 1, 1, 0, 1]) == [2, 0, 1],
       "dry runs between buys are counted in closes, back-to-back buys are 0")
    ck(gaps_between([0, 0, 0]) == [] and gaps_between([1]) == [],
       "NULL: no buys, or only one, leaves no completed gap")
    f = [1, 1, 0, 0, 0, 1, 0, 0, 0, 0]
    r1, n1 = after_hit(f)
    ck(abs(r1 - 1 / 3.0) < 1e-12 and n1 == 3,
       "after a buy, the next close bought 1 of 3 times in the fixture")
    r2, n2 = after_run(f, 3)
    ck(r2 is not None and n2 >= 1,
       "and the chance after three dry closes is measured on %d such moments" % n2)
    ck(after_run([0, 0], 5) == (None, 0),
       "NULL: a dry run longer than the data reports nothing, not zero")
    ck(quantile([1, 2, 3, 4, 100], 0.5) == 3 and quantile([], 0.9) is None,
       "quantiles pick the middle, and nothing from nothing")
    print("pinstreak selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0
    spans = downtime.load()
    rows = load(spans)
    if len(rows) < 100:
        print("loaded nothing -- only %d closes on file" % len(rows))
        return 0
    flags = [1 if f else 0 for _, f in rows]
    base = sum(flags) / float(len(flags))
    lines = []
    w = lines.append
    w("# STREAKS -- do the chances come in bunches?\n")
    w("`research/pinstreak.py`, %d closes, %d of them bought on (%.1f%%).\n"
      % (len(rows), sum(flags), 100 * base))

    # per hour and per day
    per_hour = collections.Counter()
    per_day = collections.Counter()
    for (cs, f) in rows:
        e = dt.datetime.fromtimestamp(cs + downtime.et_offset(cs), dt.timezone.utc)
        if f:
            per_hour[e.strftime("%Y-%m-%d %H")] += 1
            per_day[e.strftime("%Y-%m-%d")] += 1
        per_hour.setdefault(e.strftime("%Y-%m-%d %H"), 0)
        per_day.setdefault(e.strftime("%Y-%m-%d"), 0)
    counts = [per_hour[k] for k in sorted(per_hour)]
    d, p = dispersion_p(counts, base, 4)
    rng0 = random.Random(7)
    null_d = [dispersion([sum(1 for _ in range(4) if rng0.random() < base)
                          for _ in counts]) for _ in range(400)]
    null_d = [x for x in null_d if x is not None]
    null_mid = sorted(null_d)[len(null_d) // 2] if null_d else float("nan")
    w("## Do they clump?\n")
    w("| | |")
    w("|---|---|")
    w("| hours on record | %d |" % len(counts))
    w("| busiest hour | %d buys |" % max(counts))
    w("| hours with none | %d (%.0f%%) |"
      % (sum(1 for c in counts if c == 0),
         100.0 * sum(1 for c in counts if c == 0) / len(counts)))
    w("| clumping, ours | **%.2f** |" % d)
    w("| clumping, a coin-flip world at our rate | %.2f |" % null_mid)
    w("| p against a coin-flip world | %.3f |" % p)
    w("")
    if p < 0.05 and d > null_mid:
        w("**They clump, mildly.** Our hours vary more than a coin flip at the "
          "same rate would: %.2f against %.2f, p %.3f. The comparison is with "
          "that simulated world, not the textbook 1.0 -- with only four closes "
          "in an hour a random world already sits near %.2f."
          % (d, null_mid, p, null_mid))
    else:
        w("**They do not clump.** The bunching is what a coin flip at our own "
          "rate produces anyway, so a busy hour predicts nothing: %.2f against "
          "%.2f, p %.3f." % (d, null_mid, p))
    w("")

    # persistence
    w("## Does a dry spell predict another?\n")
    w("| situation | chance the next close buys | moments |")
    w("|---|---|---|")
    r, n = after_hit(flags)
    w("| right after a buy | %.0f%% | %d |" % (100 * r, n))
    for k in (1, 2, 4, 8, 12):
        r, n = after_run(flags, k)
        if r is not None and n >= 20:
            w("| after %d dry closes (%s) | %.0f%% | %d |"
              % (k, "%.0fh" % (k * 0.25) if k >= 4 else "%dm" % (k * 15), 100 * r, n))
    w("| the plain average | %.0f%% | %d |" % (100 * base, len(flags)))
    w("")

    # droughts
    g = gaps_between(flags)
    w("## How long is a normal dry spell?\n")
    if g:
        w("| dry spell | closes | in hours |")
        w("|---|---|---|")
        for q, nm in ((0.5, "typical (half are shorter)"), (0.9, "9 in 10 are shorter"),
                      (0.95, "19 in 20 are shorter"), (0.99, "99 in 100 are shorter")):
            v = quantile(g, q)
            w("| %s | %d | %.1f h |" % (nm, v, v * 0.25))
        w("| the longest we have seen | %d | %.1f h |" % (max(g), max(g) * 0.25))
        w("")
        w("So a silence past **%.1f hours** is longer than 19 in 20 normal ones "
          "-- past that, check the bot before blaming the market." % (quantile(g, 0.95) * 0.25))
    import time as _t
    last_buy = max((cs for cs, f in rows if f), default=None)
    if last_buy and g:
        dry = int((_t.time() - last_buy) // CLOSE)
        longer = sum(1 for x in g if x >= dry)
        w("")
        w("**Right now:** %.1f hours since the last buy (%d closes). %d of the "
          "%d dry spells on record were at least this long (%.0f%%)."
          % ((_t.time() - last_buy) / 3600.0, dry, longer, len(g),
             100.0 * longer / len(g)))
    w("")
    w("## Buys per day")
    w("")
    w("| day (ET) | buys |")
    w("|---|---|")
    for k in sorted(per_day):
        w("| %s | %d |" % (k, per_day[k]))
    open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("\nwrote %s" % os.path.basename(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
