#!/usr/bin/env python3
# VERSION: 2026-09-03-i1
"""
informed.py -- the taker's trade is the signal. Who is informed, and when?

    python research/informed.py --selftest
    python research/informed.py --data ./kalshi_data --out ./fulltape

WHY THIS EXISTS

The strongest clean measurement this project has produced is maker.py's
signed markout: a taker's fill moves the mid +0.612c in the taker's direction
within one second (t = 54.4 on 798 close clusters), and the drift GROWS with
horizon. The people crossing the spread know something.

maker.py pooled that number, and the pooled verdict is settled: resting loses
-0.36c to -0.75c per fill in every price bucket. But a pooled mean is an
average over informed flow and noise flow, and nobody has asked WHICH trades
carry the information, or how far it drifts. Two strategies live or die on
the conditional structure, and this stage measures both from one joint pass:

  FOLLOW    if the informed tail is identifiable BEFORE the fact -- large
            trades, bursts, late in the window -- then copying those trades
            at the touch and holding to settlement pays if their drift
            exceeds the taker cost (spread + 0.07*p*(1-p)). The pooled drift
            at 1s is 0.612c against ~2.3c of cost; the tail is the question.

  QUOTE     the maker's loss is the same number with the sign flipped. A
            maker cannot pick which fills to take, but CAN pick when and
            where to stand: prevailing spread, time-to-close, and whether
            recent flow already leans against the quote are all observable
            before the fill. A cell where E[maker P&L | fill] > 0 exists or
            it does not; pooled numbers cannot say.

EVERY CONDITION IS MEASURABLE AT THE TIME. m0 and the spread come from the
quote STRICTLY before the trade (a quote stamped in the trade's own second is
the book AFTER the trade -- maker.py measured a planted 1.000c as 0.000c that
way). The burst is summed over trades strictly earlier. Nothing in any bucket
key is measured after the trade it buckets.

THE MEASURES, per trade, all in cents per contract:

  markout(h)   sgn * (mid(t+h) - m0)          the information, mid terms
  markout(S)   sgn * (100*Y - m0)             the information, settled terms
  follow(S)    copy the taker at the touch, pay the taker fee, hold to
               settlement: 100*Y - a0 - fee(a0) when the taker bought,
               b0 - 100*Y - fee(b0) when they sold
  maker(S)     the resting side's actual fill held to settlement:
               -sgn * (100*Y - trade_price), NO fee -- makers pay none

THE CONTROLS

  * random-sign: every measure recomputed with sgn replaced by a coin flip.
    Volatility is symmetric and the sign is not; a signed effect that
    survives sign randomisation is an artefact. maker.py once watched an
    absolute-move version fire at t = +11 on a tape with provably zero
    adverse selection.
  * cluster-robust on close time, n is CLOSES, and the MDE prints first.
  * MANY CELLS ARE LOOKED AT. The header prints the count and the |t| a
    single cell needs to survive the family. One cell in forty at |t| = 2
    is expected under the null; pattern 13 in BIASES.md exists because this
    project has been burned by exactly that.

THE HEADLINE CELL IS PRE-REGISTERED. "Spread >= 2c, flow quiet or leaning
against the taker, tau > 180s" was written into this file before it ever saw
real data. Whatever that cell says, it is the one reading that does not pay
the multiple-looks tax.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from statistics import mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import fee_per_contract                        # noqa: E402
from tdist import crit as _tcrit                           # noqa: E402
from tdist import p_two_sided                              # noqa: E402

# THE HORIZON CURVE, and it is the point of this list rather than a detail.
# maker.py measured the resting side's markout at 1s/5s/30s and got
# 0.612/0.624/0.657c, concluded making loses against a 0.5c capture, and the
# project recorded that as closed. This file measured the SAME quantity to
# SETTLEMENT and got 0.38c -- which, against the trade-weighted 0.63c
# half-spread, is positive. Both cannot be the maker's cost. Either impact
# peaks and decays, in which case a maker who HOLDS never pays the peak, or
# one of the two numbers is wrong. A curve settles it; an argument does not.
HORIZONS = (1, 5, 30, 120, 300)
FRESH = 30                  # a quote older than this is not a quote
BURST_W = 10                # seconds of prior flow that define the lean
SIZE_CUTS = (5.0, 20.0, 100.0)     # contracts; stated, not fitted
TAU_CUTS = (60, 180, 420)          # seconds to close
SPREAD_CUTS = (1.5, 2.5, 4.5)      # cents; 1c tick makes these clean bins
PRICE_CUTS = (0.08, 0.30, 0.70, 0.92)


def t_crit(df):
    return _tcrit(0.05, df)


# ===========================================================================
# per-close aggregation -- the whole tape never lives in RAM per cell
# ===========================================================================
class Cell:
    """One (table, bucket) cell: per-close sums for every measure.

    27.7 million trades cannot be kept as per-trade records per cell on a
    16 GB machine. Cluster-robust inference only needs per-CLOSE means, so
    each cell holds close -> [sum, n] per measure and nothing else.
    """
    MEASURES = tuple(f"mk{h}" for h in HORIZONS) + \
        ("mkS", "follow", "maker", "shufS")

    def __init__(self):
        self.by = {m: defaultdict(lambda: [0.0, 0]) for m in self.MEASURES}

    def add(self, close, **vals):
        for m, v in vals.items():
            if v is None:
                continue
            s = self.by[m][close]
            s[0] += v
            s[1] += 1

    def stat(self, measure):
        """Equal-weight close-time clusters, exactly as maker.clustered."""
        cl = [(s / n) for s, n in self.by[measure].values() if n > 0]
        G = len(cl)
        ntr = sum(n for _, n in self.by[measure].values())
        if G < 30:
            # pattern 17: a cluster SE off a handful of clusters produced
            # t = +12.28 off 12 closes once. Below the floor the mean is
            # shown and no significance is claimed.
            return {"G": G, "n": ntr,
                    "mean": mean(cl) if cl else None, "t": None, "mde": None}
        mu = mean(cl)
        sd = pstdev(cl) * math.sqrt(G / (G - 1.0))
        se = sd / math.sqrt(G)
        return {"G": G, "n": ntr, "mean": mu,
                "t": (mu / se if se > 0 else 0.0),
                "mde": t_crit(G - 1) * se}


# ===========================================================================
def bucket_of(cuts, v):
    for i, c in enumerate(cuts):
        if v < c:
            return i
    return len(cuts)


def _iter_trade_events(data_dir, cap=4_000_000, exact=True):
    """(ticker, instant_ms, seq, yes_price_dollars, taker_side) off the tape.

    NOT via edge.load_trades. That loader goes through schema.json, which
    pins the trade timestamp to `msg.ts` -- an integer SECOND. Grouping by a
    whole second pools every unrelated trade on that ticker in that second
    and calls the pile one burst. `msg.ts_ms` carries the true instant and is
    present on 100% of the trade messages on disk; this diagnostic is the one
    consumer that needs it, so it reads it here rather than moving the
    timestamp every other stage is calibrated against.

    exact=False reproduces the whole-second grouping deliberately, so the two
    can be printed side by side.
    """
    from edge import read_jsonl_gz
    n = 0
    for m in read_jsonl_gz(os.path.join(data_dir, "trade", "*.jsonl.gz")):
        d = m.get("msg") or {}
        tk = d.get("market_ticker") or d.get("ticker")
        if not tk:
            continue
        if d.get("yes_price_dollars") is not None:
            p, scale = d.get("yes_price_dollars"), 1.0
        else:
            p, scale = d.get("yes_price"), 100.0
        if p is None:
            continue
        ts_ms, ts = d.get("ts_ms"), d.get("ts")
        t = ts_ms if (exact and ts_ms is not None) else \
            (None if ts is None else int(ts) * 1000)
        if t is None:
            continue
        try:
            p = float(p) / scale
        except (TypeError, ValueError):
            continue
        yield (tk, int(t), m.get("seq"), p,
               str(d.get("taker_side", "")).lower())
        n += 1
        if n >= cap:
            return


def sweep_stats(events):
    """Group trades by (ticker, instant) and describe the SHAPE of the groups.

    The share of multi-price groups is not evidence of anything on its own.
    At whole-second resolution unrelated trades pile into one group and that
    share inflates without a single sweep being involved -- which is exactly
    how "59.0% of same-instant groups, median 8 legs" was produced.

    What separates a swept book from a coincidence does not involve the clock
    at all. A sweep's legs are ONE taker side walking CONSECUTIVE price levels
    away from the touch, printed back to back. Independent trades that merely
    share a timestamp scatter: mixed sides, non-monotone prices, other
    tickers' prints interleaved in the sequence numbers. So the fraction of
    multi-price groups that are single-sided AND monotone is decisive at any
    resolution, and the timestamp is only corroboration.
    """
    groups = defaultdict(list)
    n = 0
    for (tk, t, seq, p, side) in events:
        groups[(tk, t)].append((seq, p, side))
        n += 1
    multi = [v for v in groups.values() if len(v) > 1]
    mpx = [v for v in multi if len(set(round(x[1], 6) for x in v)) > 1]
    one_side = mono = sided_mono = dir_ok = contig = 0
    for v in mpx:
        v = sorted(v, key=lambda x: (x[0] if x[0] is not None else 0))
        px = [x[1] for x in v]
        sides = set(x[2] for x in v if x[2])
        up = all(b >= a for a, b in zip(px, px[1:]))
        down = all(b <= a for a, b in zip(px, px[1:]))
        single = len(sides) == 1
        if single:
            one_side += 1
        if up or down:
            mono += 1
        if single and (up or down):
            sided_mono += 1
            # a YES taker eats ascending asks; a NO taker walks the yes
            # price DOWN. Either is a book being swept; a mismatch is not.
            s = next(iter(sides))
            if (s == "yes" and up) or (s == "no" and down):
                dir_ok += 1
        sq = [x[0] for x in v if x[0] is not None]
        if len(sq) == len(v) and sq and (max(sq) - min(sq) + 1) == len(sq):
            contig += 1
    return {"trades": n, "groups": len(groups),
            "single": len(groups) - len(multi),
            "multi_same_px": len(multi) - len(mpx), "multi_px": len(mpx),
            "one_side": one_side, "mono": mono, "sided_mono": sided_mono,
            "dir_ok": dir_ok, "contig": contig,
            "legs": sorted(len(v) for v in mpx)}


def adjacent_control(events, sizes, seed=20260906):
    """THE NULL for the shape test: trades adjacent in time, NOT simultaneous.

    Takes runs of consecutive trades on one ticker, drawn to the same length
    distribution as the real multi-price groups, and discards any run whose
    members all share an instant. If the shape test is measuring "a book
    being walked" it must go quiet here; if it stays high, it is measuring
    nothing more than that a busy book trends, and the sweep claim dies with
    it. Each run is relabelled to its own synthetic instant so the identical
    grouping code scores it.
    """
    rnd = random.Random(seed)
    buf = defaultdict(list)
    want = {}
    gid = 0
    if not sizes:
        return
    for (tk, t, seq, p, side) in events:
        if tk not in want:
            want[tk] = sizes[rnd.randrange(len(sizes))]
        buf[tk].append((t, seq, p, side))
        if len(buf[tk]) >= want[tk]:
            grp = buf[tk]
            if len(set(x[0] for x in grp)) > 1:      # not simultaneous
                gid += 1
                for (t_, seq_, p_, side_) in grp:
                    yield (tk, -gid, seq_, p_, side_)
            buf[tk] = []
            want[tk] = sizes[rnd.randrange(len(sizes))]


def sweep_verdict(s):
    """PER-LEVEL is claimed off the SHAPE of the groups, never off a count."""
    m = s["multi_px"]
    return (m > 1000 and s["sided_mono"] >= 0.90 * m
            and s["contig"] >= 0.90 * m and s["dir_ok"] >= 0.80 * m)


def _pct(a, b):
    return 100.0 * a / max(1, b)


def sweep_shape(data_dir, verbose=True, cap=10_000_000):
    """Does Kalshi report a sweep as ONE print, or one print PER LEVEL?

    THE ENTIRE MAKER VERDICT TURNS ON THIS AND NOTHING ELSE.

    A maker resting at the touch is filled at the touch by any taker order
    that reaches it -- including the first leg of a sweep that goes on to eat
    three levels above. Whether that fill is already counted depends on how
    the exchange prints it:

      PER LEVEL   the touch leg is its own print and lands in `at-touch`,
                  so the at-touch P&L (+0.48c) already includes sweep legs
                  and stands as measured.
      ONE PRINT   the sweep appears once at its average price, out in the
                  -out buckets, and the touch leg is INVISIBLE. A touch
                  maker eats it at the touch price, and the volume-weighted
                  result is about -0.42c. Negative.

    The first version counted trades sharing a timestamp and took that
    timestamp from edge.load_trades, which reads `msg.ts` -- an integer
    SECOND (verified on disk: ts == floor(ts_ms/1000) on 4,168,479 of
    4,168,479 trades). So "same instant" meant "same second", and the 59.0%
    it reported is what a busy book produces from independent trades alone.

    The count is now a description. The claim rests on the shape of the
    groups -- single-sided AND monotone, walking the taker's own direction,
    over consecutive exchange seq -- which does not reference the clock, is
    reported at BOTH resolutions, and is scored against a null of trades
    that are adjacent in time but not simultaneous.
    """
    ms = sweep_stats(_iter_trade_events(data_dir, cap, exact=True))
    sec = sweep_stats(_iter_trade_events(data_dir, cap, exact=False))
    ctl = sweep_stats(adjacent_control(
        _iter_trade_events(data_dir, cap, exact=True), ms["legs"]))
    if not verbose:
        return ms, sec, ctl
    print("\n" + "=" * 78)
    print("HOW A SWEEP IS PRINTED -- the fact the maker verdict rests on")
    print("=" * 78)
    print(f"  {ms['trades']:,} trades\n")
    hdr = f"  {'':<34}{'ts_ms':>14}{'whole second':>14}{'CONTROL':>14}"
    print(hdr)
    print(f"  {'':<34}{'(true instant)':>14}{'(msg.ts)':>14}"
          f"{'(adjacent)':>14}")
    print("  " + "-" * 74)
    rows = [("groups", "groups", None), ("trades per group", None, "tpg"),
            ("multi-price groups", "multi_px", None)]
    print(f"  {'groups':<34}{ms['groups']:>14,}{sec['groups']:>14,}"
          f"{ctl['groups']:>14,}")
    print(f"  {'trades per group':<34}"
          f"{ms['trades'] / max(1, ms['groups']):>14.2f}"
          f"{sec['trades'] / max(1, sec['groups']):>14.2f}"
          f"{ctl['trades'] / max(1, ctl['groups']):>14.2f}")
    print(f"  {'multi-price groups':<34}{ms['multi_px']:>14,}"
          f"{sec['multi_px']:>14,}{ctl['multi_px']:>14,}")
    print(f"  {'  as % of all groups':<34}"
          f"{_pct(ms['multi_px'], ms['groups']):>13.1f}%"
          f"{_pct(sec['multi_px'], sec['groups']):>13.1f}%"
          f"{_pct(ctl['multi_px'], ctl['groups']):>13.1f}%")
    print("\n  SHAPE of those multi-price groups -- no clock involved:")
    for lbl, k in (("single-sided", "one_side"),
                   ("monotone price ladder", "mono"),
                   ("single-sided AND monotone", "sided_mono"),
                   ("  ...and walking taker's way", "dir_ok"),
                   ("consecutive exchange seq", "contig")):
        print(f"  {lbl:<34}"
              f"{_pct(ms[k], ms['multi_px']):>13.1f}%"
              f"{_pct(sec[k], sec['multi_px']):>13.1f}%"
              f"{_pct(ctl[k], ctl['multi_px']):>13.1f}%")
    if ms["legs"]:
        lg = ms["legs"]
        print(f"\n  legs per multi-price group (ts_ms): median "
              f"{lg[len(lg) // 2]}, max {lg[-1]}")
    print()
    if sweep_verdict(ms):
        print("  PER LEVEL. Same-instant multi-price prints are one-sided")
        print("  monotone ladders over consecutive seq -- a book being")
        print("  walked. The control, built from trades that are merely")
        print("  adjacent, does not have that shape, so the test is reading")
        print("  sweep structure and not just a trending book. The touch leg")
        print("  of a sweep is its own print, is already inside `at-touch`,")
        print("  and the at-touch maker P&L stands as measured.")
    else:
        print("  NOT ESTABLISHED. The multi-price groups do not have the")
        print("  shape of a swept book, so the touch leg may be hidden in")
        print("  the -out buckets and the at-touch figure would then be an")
        print("  overstatement. The maker verdict cannot be read.")
    return ms, sec, ctl


def measure(quotes, trades, markets, outcome, verbose=False,
            assert_strict=False):
    """One pass over every trade -> cell aggregates.

    Returns ({table: {bucket: Cell}}, n_used, n_skipped, size_seen).
    `assert_strict` verifies, per trade, that the reference quote really is
    STRICTLY earlier -- the self-test runs it on a world where every trade
    shares a second with a quote, so a non-strict lookup cannot hide.
    """
    import bisect
    tables = defaultdict(lambda: defaultdict(Cell))
    rnd = random.Random(20260903)
    n_used = n_skipped = 0
    done = 0
    size_seen = defaultdict(int)

    for tk, tlist in trades.items():
        done += 1
        if verbose and done % 2000 == 0:
            print(f"    {done:,} markets through, {n_used:,} trades used",
                  flush=True)
        m = markets.get(tk)
        q = quotes.get(tk)
        if not m or not q or len(q) < 10:
            continue
        y = outcome(m)
        close = m.get("close")
        if y is None or close is None:
            continue
        close = int(round(float(close)))
        Y = 100.0 * y

        secs = [r[0] for r in q]
        mids = [(r[1] + r[2]) * 50.0 for r in q]      # cents
        bids = [r[1] * 100.0 for r in q]
        asks = [r[2] * 100.0 for r in q]

        def before(t, strict):
            """Index of the freshest quote at (or strictly before) t."""
            i = bisect.bisect_left(secs, t) if strict else \
                bisect.bisect_right(secs, t)
            i -= 1
            if i < 0 or t - secs[i] > FRESH:
                return None
            return i

        # ONE filtered array; everything below indexes only it. The first
        # draft filtered into parallel arrays and then indexed the
        # unfiltered list -- off by one for every trade after the first
        # missing taker_side, which is a bucketing scramble no output
        # would ever confess to.
        T = []
        for (t, p_, sz, side) in tlist:
            side = str(side)
            if not side or side[0] not in ("y", "n"):
                n_skipped += 1
                continue
            try:
                T.append((float(t), float(p_) * 100.0, float(sz),
                          1.0 if side[0] == "y" else -1.0))
            except (TypeError, ValueError):
                n_skipped += 1
        if not T:
            continue
        ts = [r[0] for r in T]
        pref = [0.0]
        for (_t, _p, sz, g) in T:
            pref.append(pref[-1] + g * sz)

        for i, (t, price_c, sz, sgn) in enumerate(T):
            tau = close - t
            if not (0 < tau <= 900):
                continue
            j0 = before(t, strict=True)
            if j0 is None:
                n_skipped += 1
                continue
            if assert_strict and not (secs[j0] < t):
                raise AssertionError(
                    f"reference quote at {secs[j0]} is not strictly before "
                    f"the trade at {t} -- this is the exact bug that "
                    "measured a planted 1.000c as 0.000c in maker.py")
            m0, b0, a0 = mids[j0], bids[j0], asks[j0]
            sp0 = a0 - b0
            if not (0 < b0 < a0 < 100):
                n_skipped += 1
                continue

            lo_i = bisect.bisect_left(ts, t - BURST_W)
            burst = pref[i] - pref[lo_i]      # strictly earlier trades only

            mk = {}
            for h in HORIZONS:
                jh = before(t + h, strict=False)
                mk[h] = None if jh is None else sgn * (mids[jh] - m0)
            mkS = sgn * (Y - m0)
            follow = (Y - a0 - 100.0 * fee_per_contract(a0 / 100.0)
                      if sgn > 0 else
                      b0 - Y - 100.0 * fee_per_contract(b0 / 100.0))
            maker = -sgn * (Y - price_c)
            flip = rnd.choice((1.0, -1.0))
            shufS = flip * (Y - m0)

            vals = {f"mk{h}": mk.get(h) for h in HORIZONS}
            vals.update(mkS=mkS, follow=follow, maker=maker, shufS=shufS)
            n_used += 1
            size_seen[bucket_of(SIZE_CUTS, sz)] += 1

            # HOW FAR FROM THE TOUCH DID THIS PRINT? The maker measure
            # averages over every fill in the book, and a fill 3c from the
            # mid pays the maker 3c -- but only a maker QUOTING 3c out gets
            # it, and they are filled far less often. maker.py assumed every
            # fill lands at the touch of a median-width book (capture 0.50c);
            # this file measured where trades ACTUALLY printed (0.73c) and
            # flipped the verdict on that difference alone. Which of the two
            # is right depends entirely on whether the money is at the touch
            # or out in the ladder, so split it and look.
            touch = a0 if sgn > 0 else b0
            beyond = sgn * (price_c - touch)
            # `beyond < 0` means the print landed INSIDE the reference quote
            # -- a buy below the recorded ask. No maker at that touch was
            # filled there; the quote had already moved and ours is stale.
            # The first version tested `beyond <= 0.05` and swept all of it
            # into "at-touch", which is why that bucket reported a NEGATIVE
            # half-spread of -0.19c: a maker who captures less than nothing
            # is not a maker, it is a stale reference. Its own bucket now,
            # so it can be counted rather than silently mixed in.
            dep = ("inside-stale" if beyond < -0.05 else
                   "at-touch" if beyond <= 0.05 else
                   "0-1c-out" if beyond <= 1.0 else
                   "1-3c-out" if beyond <= 3.0 else "3c+-out")
            age = t - secs[j0]
            fresh2 = age <= 2.0

            agree = ("agree" if sgn * burst > 0.5 else
                     "against" if sgn * burst < -0.5 else "quiet")
            keys = [
                ("ALL", "all"),
                ("tau", f"{bucket_of(TAU_CUTS, tau)}"),
                ("size", f"{bucket_of(SIZE_CUTS, sz)}"),
                ("burst", agree),
                ("spread", f"{bucket_of(SPREAD_CUTS, sp0)}"),
                ("price", f"{bucket_of(PRICE_CUTS, m0 / 100.0)}"),
                ("filldepth", dep),
            ]
            # The same split again, restricted to a reference quote at most
            # two seconds old. If `at-touch` and `at-touch(fresh)` disagree,
            # the difference IS the staleness and no argument is needed.
            if fresh2:
                keys.append(("filldepth2s", dep))
            # the pre-registered headline cell, written before real data
            if sp0 >= 2.0 and agree in ("quiet", "against") and tau > 180:
                keys.append(("HEADLINE", "spread>=2c & not-with-flow & "
                                         "tau>180s"))
            # the informed-tail cell for FOLLOW, also pre-registered:
            # big trade, with the flow, late in the window
            if sz >= SIZE_CUTS[-1] and agree == "agree" and tau <= 180:
                keys.append(("TAIL", "size>=100 & with-flow & tau<=180s"))
            for tb, bk in keys:
                tables[tb][bk].add(close, **vals)
    return tables, n_used, n_skipped, dict(size_seen)


# ===========================================================================
BUCKET_NAMES = {
    "tau": {"0": "0-60s", "1": "60-180s", "2": "180-420s", "3": "420-900s"},
    "size": {"0": "<5", "1": "5-20", "2": "20-100", "3": ">=100"},
    "spread": {"0": "1c", "1": "2c", "2": "3-4c", "3": ">=5c"},
    "price": {"0": "<8c", "1": "8-30c", "2": "30-70c", "3": "70-92c",
              "4": ">=92c"},
}


def show_curve(tables, keys=(("ALL", "all"),
                            ("filldepth2s", "at-touch"),
                            ("filldepth", "at-touch"),
                            ("filldepth", "inside-stale"),
                            ("filldepth", "1-3c-out"), ("spread", "0"),
                            ("spread", "3"), ("price", "2"))):
    """Markout against horizon, and the maker's net at each one.

    THE WHOLE MAKER QUESTION IS ON THIS TABLE. `net` is the trade-weighted
    half-spread captured minus the markout at that horizon -- what a maker
    keeps if they unwind after h seconds. If markout rises to 30s and then
    falls by settlement, a maker who holds to expiry never pays the peak and
    maker.py's short-horizon verdict was measuring an exit nobody has to take.
    """
    print("\n" + "=" * 78)
    print("THE IMPACT CURVE -- what the resting side pays, by how long they")
    print("hold. maker.py stopped at 30s; settlement is a different number.")
    print("=" * 78)
    hs = list(HORIZONS)
    hdr = f"  {'cell':<22}{'half-spread':>12}"
    for h in hs:
        hdr += f"{str(h) + 's':>9}"
    hdr += f"{'settle':>9}"
    print(hdr)
    for tb, bk in keys:
        if tb not in tables or bk not in tables[tb]:
            continue
        cell = tables[tb][bk]
        mkS = cell.stat("mkS")["mean"]
        mkr = cell.stat("maker")["mean"]
        if mkS is None or mkr is None:
            continue
        half = mkr + mkS      # maker = half_spread - mkS, exactly
        name = BUCKET_NAMES.get(tb, {}).get(bk, f"{tb}/{bk}")
        row = f"  {name:<22}{half:>11.2f}c"
        for h in hs:
            v = cell.stat(f"mk{h}")["mean"]
            row += f"{v:>8.2f}c" if v is not None else f"{'--':>9}"
        row += f"{mkS:>8.2f}c"
        print(row)
        net = f"  {'  -> maker net':<22}{'':>12}"
        for h in hs:
            v = cell.stat(f"mk{h}")["mean"]
            net += f"{half - v:>8.2f}c" if v is not None else f"{'--':>9}"
        net += f"{half - mkS:>8.2f}c"
        print(net)
    print("\n  half-spread is derived, not assumed: maker = half - mkS holds")
    print("  exactly by construction, so half = maker + mkS.")
    print("  A NEGATIVE half-spread is impossible for a real maker and means")
    print("  the reference quote was stale -- see inside-stale, and prefer")
    print("  the 2s-fresh at-touch row over the pooled one wherever they")
    print("  disagree.")
    print("  READ THE at-touch ROW FIRST. That is the only line a maker")
    print("  resting at the best bid or offer can actually collect. If the")
    print("  positive number lives in the -out rows, the money is spread")
    print("  along a ladder that fills rarely, and the pooled figure is an")
    print("  average nobody can trade.")
    print("  A positive `net` at settlement with a negative one at 30s means")
    print("  the impact is temporary and the maker who holds does not pay it.")


def show_tables(tables, measures=("mkS", "follow", "maker", "shufS")):
    ncells = sum(len(v) for v in tables.values())
    bon = 0.05 / max(1, ncells * len(measures))
    # normal-approx family threshold, printed so no cell can pose alone
    import statistics as _st
    z = _st.NormalDist().inv_cdf(1 - bon / 2)
    print(f"\n  {ncells} cells x {len(measures)} measures are about to be")
    print(f"  looked at. A single cell needs |t| > {z:.1f} to survive the")
    print("  family at 5%. The pre-registered HEADLINE and TAIL cells are")
    print("  the only readings that pay no multiple-looks tax.")
    order = ["ALL", "HEADLINE", "TAIL", "filldepth", "filldepth2s",
             "burst", "size", "spread", "tau", "price"]
    for tb in order:
        if tb not in tables:
            continue
        print(f"\n  {tb}")
        hdr = f"    {'bucket':>28}{'trades':>12}{'closes':>8}"
        for ms in measures:
            hdr += f"{ms:>10}{'t':>7}"
        print(hdr)
        for bk in sorted(tables[tb]):
            cell = tables[tb][bk]
            name = BUCKET_NAMES.get(tb, {}).get(bk, bk)
            st0 = cell.stat("mkS")
            row = f"    {name:>28}{st0['n']:>12,}{st0['G']:>8,}"
            for ms in measures:
                st = cell.stat(ms)
                if st["mean"] is None:
                    row += f"{'--':>10}{'':>7}"
                elif st["t"] is None:
                    row += f"{st['mean']:>9.2f}c{'  <30cl':>7}"
                else:
                    row += f"{st['mean']:>9.2f}c{st['t']:>7.1f}"
            print(row)
    print("\n  mkS    = signed drift, trade to settlement (information)")
    print("  follow = copy the taker at the touch, pay the fee, hold")
    print("  maker  = the resting side's fill held to settlement, no fee")
    print("  shufS  = the same drift under a coin-flip sign: must be ~0")


# ===========================================================================
def _bridge_world(n_mkt, informed_q=0.0, seed=1, spread_c=2.0,
                  per_mkt_trades=25, informed_big=True, vol_cluster=False):
    """A martingale world with an optional informed fraction.

    The mid is a bridge to the outcome plus noise, so the price is a
    legitimate martingale-ish process. Noise trades draw a coin-flip side;
    informed trades (fraction q) side with sign(Y - mid) and, when
    informed_big, trade 200 lots against the noise's 2 -- so the SIZE table
    must separate them or the estimator is blind.
    """
    rnd = random.Random(seed)
    quotes, trades, markets = {}, {}, {}
    base = 1767225600
    for k in range(n_mkt):
        close = base + 900 * (k + 1)
        tk = f"KXTEST-{k}"
        Y = 1.0 if rnd.random() < 0.5 else 0.0
        mid = 50.0
        ql, tl = [], []
        t0 = close - 900
        for s in range(900):
            left = 900 - s
            drift = (100.0 * Y - mid) / left
            shock = 3.0 if (vol_cluster and (s // 60) % 2) else 0.8
            mid = min(97.0, max(3.0, mid + drift + rnd.gauss(0, shock)))
            b, a = mid - spread_c / 2.0, mid + spread_c / 2.0
            ql.append((t0 + s, b / 100.0, a / 100.0, 50.0, 50.0))
            if rnd.random() < per_mkt_trades / 900.0:
                inf = rnd.random() < informed_q
                if inf:
                    sgn = 1.0 if (100.0 * Y - mid) > 0 else -1.0
                    sz = 200.0 if informed_big else 2.0
                else:
                    sgn = rnd.choice((1.0, -1.0))
                    sz = 2.0
                px = (a if sgn > 0 else b) / 100.0
                side = "yes" if sgn > 0 else "no"
                tl.append((t0 + s + 0.5, px, sz, side))
        quotes[tk] = ql
        trades[tk] = tl
        markets[tk] = {"ticker": tk, "close": close, "result": Y}
    return quotes, trades, markets


def selftest():
    print("=" * 78)
    print("SELF-TEST -- against known answers")
    print("=" * 78)
    fails = []

    def outcome(m):
        return m.get("result")

    # ---- 1. a world with NO information: every cell must be silent -------
    print("\n  A martingale world, coin-flip takers. Every signed measure")
    print("  must sit inside its MDE, in every cell, at settlement horizon")
    print("  included.")
    q, t, mk = _bridge_world(400, informed_q=0.0, seed=3)
    tb, used, skip, _ = measure(q, t, mk, outcome)
    st = tb["ALL"]["all"].stat("mkS")
    sh = tb["ALL"]["all"].stat("shufS")
    print(f"    {used:,} trades, {st['G']} closes: "
          f"mkS {st['mean']:+.2f}c (t={st['t']:+.1f}), "
          f"shuffle {sh['mean']:+.2f}c (t={sh['t']:+.1f})")
    if abs(st["t"]) > 3.0:
        fails.append(f"zero-information world read mkS t={st['t']:+.1f} -- "
                     "the estimator manufactures information")
    bad = 0
    for tbl in tb.values():
        for cell in tbl.values():
            cs = cell.stat("mkS")
            if cs["t"] is not None and abs(cs["t"]) > 4.0:
                bad += 1
    if bad:
        fails.append(f"{bad} cells fired |t|>4 on a world with nothing in it")

    # ---- 2. a planted informed tail must be found WHERE it was planted ---
    print("\n  20% of trades are informed and trade 100x the size. The size")
    print("  table must separate them; the pooled number must dilute them.")
    q, t, mk = _bridge_world(400, informed_q=0.20, seed=5)
    tb2, used2, _, _ = measure(q, t, mk, outcome)
    big = tb2["size"]["3"].stat("mkS")
    small = tb2["size"]["0"].stat("mkS")
    pool = tb2["ALL"]["all"].stat("mkS")
    print(f"    size>=100: mkS {big['mean']:+.2f}c (t={big['t']:+.1f}, "
          f"G={big['G']})")
    print(f"    size<5:    mkS {small['mean']:+.2f}c (t={small['t']:+.1f})")
    print(f"    pooled:    mkS {pool['mean']:+.2f}c")
    if big["t"] is None or big["t"] < 5 or big["mean"] < 3.0:
        fails.append("the informed tail was planted at size>=100 and the "
                     "size table cannot see it")
    if small["t"] is not None and small["t"] > 4.0:
        fails.append("the noise bucket reads informed -- buckets are "
                     "bleeding into each other")
    fol = tb2["size"]["3"].stat("follow")
    print(f"    follow (size>=100): {fol['mean']:+.2f}c (t={fol['t']:+.1f})"
          f" -- planted edge minus spread & fee")
    if fol["mean"] is None or fol["mean"] < 1.0:
        fails.append("copying planted informed traders does not pay in the "
                     "fixture -- the follow arithmetic is wrong")
    mkr = tb2["size"]["3"].stat("maker")
    if mkr["mean"] is None or mkr["mean"] > -3.0:
        fails.append("the maker measure fails to show the resting side "
                     "being run over by planted informed flow")

    # ---- 3. the volatility trap that once fired at t=+11 -----------------
    print("\n  Volatility clusters, still zero information. The SIGNED")
    print("  measure must stay silent -- an absolute-move measure fires")
    print("  here, which is the maker.py trap.")
    q, t, mk = _bridge_world(400, informed_q=0.0, seed=7, vol_cluster=True)
    tb3, _, _, _ = measure(q, t, mk, outcome)
    st3 = tb3["ALL"]["all"].stat("mkS")
    print(f"    mkS {st3['mean']:+.2f}c (t={st3['t']:+.1f})")
    if abs(st3["t"]) > 3.0:
        fails.append(f"volatility clustering alone produced t={st3['t']:+.1f}")

    # ---- 4. no look-ahead, checked by CONSTRUCTION not by symptom --------
    print("\n  Every trade is aligned to land exactly ON a quote second,")
    print("  and the lookup must still hand back a quote STRICTLY earlier.")
    print("  A non-strict lookup returns the same-second quote and the")
    print("  assertion inside measure() fires.")
    q4, t4, mk4 = _bridge_world(60, informed_q=1.0, seed=9)
    t4s = {tk: [(float(int(t_)), p_, sz, sd) for (t_, p_, sz, sd) in v]
           for tk, v in t4.items()}
    try:
        measure(q4, t4s, mk4, outcome, assert_strict=True)
        print("    strictly-before holds for every trade")
    except AssertionError as e:
        fails.append(str(e))
    # ---- 5. the sweep diagnostic must not be fooled by a whole second ----
    print("\n  A tape with NO sweeps -- unrelated one-off trades scattered")
    print("  through each second at different prices. Pooling them into")
    print("  whole seconds inflates the multi-price COUNT enormously,")
    print("  which is what the first version read PER LEVEL off. Neither")
    print("  grouping may return PER LEVEL: there are no sweeps to find.")
    rnd5 = random.Random(11)
    flat = []
    for k in range(4000):
        base = 1767225600000 + k * 1000
        for j in range(6):          # 6 unrelated trades inside one second
            flat.append((f"KXTEST-{k % 50}", base + rnd5.randrange(1000),
                         len(flat), round(rnd5.uniform(0.20, 0.80), 2),
                         rnd5.choice(("yes", "no"))))
    s_ms = sweep_stats(flat)
    s_sec = sweep_stats([(tk, (t // 1000) * 1000, q, p, sd)
                         for (tk, t, q, p, sd) in flat])
    print(f"    true instant: {s_ms['multi_px']:,} multi-price groups, "
          f"verdict {'PER LEVEL' if sweep_verdict(s_ms) else 'not established'}")
    print(f"    whole second: {s_sec['multi_px']:,} multi-price groups, "
          f"verdict {'PER LEVEL' if sweep_verdict(s_sec) else 'not established'}")
    if sweep_verdict(s_ms):
        fails.append("sweep_shape read PER LEVEL off a tape containing no "
                     "sweeps at all")
    if sweep_verdict(s_sec):
        fails.append("pooling a sweepless tape into whole seconds still "
                     "reads PER LEVEL -- the count is being trusted again")
    if s_sec["multi_px"] <= 4 * s_ms["multi_px"]:
        fails.append("the whole-second fixture did not actually pool -- "
                     "test 5 is not testing anything")

    # ---- 6. a real sweep must still be FOUND ----------------------------
    print("\n  And a tape that is nothing but sweeps must read PER LEVEL:")
    print("  one taker walking three to five levels, per-level prints.")
    swept = []
    seq = 0
    for k in range(4000):
        t = 1767225600000 + k * 1000 + rnd5.randrange(1000)
        side = rnd5.choice(("yes", "no"))
        px = rnd5.uniform(0.30, 0.70)
        for j in range(rnd5.randrange(3, 6)):
            step = 0.01 * j * (1 if side == "yes" else -1)
            swept.append((f"KXTEST-{k % 50}", t, seq, round(px + step, 4),
                          side))
            seq += 1
        seq += rnd5.randrange(1, 4)     # gap BETWEEN sweeps, not inside one
    s_sw = sweep_stats(swept)
    print(f"    {s_sw['multi_px']:,} multi-price groups, "
          f"single-sided AND monotone "
          f"{100.0 * s_sw['sided_mono'] / max(1, s_sw['multi_px']):.0f}%, "
          f"seq-contiguous "
          f"{100.0 * s_sw['contig'] / max(1, s_sw['multi_px']):.0f}%, "
          f"verdict {'PER LEVEL' if sweep_verdict(s_sw) else 'not established'}")
    if not sweep_verdict(s_sw):
        fails.append("sweep_shape cannot recognise a tape made entirely of "
                     "per-level sweeps")

    # ---- 7. the control must not contain a single simultaneous group ----
    print("\n  The shape test's null is groups of ADJACENT trades. If it")
    print("  ever emits a genuinely simultaneous group it is scoring real")
    print("  sweeps as its own control and would validate anything.")
    seen, bad7 = 0, 0
    byg = defaultdict(list)
    for (tk, gid, q, p, sd) in adjacent_control(swept, s_sw["legs"]):
        byg[(tk, gid)].append(q)
    real = {}
    for (tk, t, q, p, sd) in swept:
        real[q] = t
    for k, qs in byg.items():
        seen += 1
        if len(set(real[q] for q in qs)) == 1:
            bad7 += 1
    print(f"    {seen:,} control groups, {bad7} of them simultaneous")
    if seen < 100:
        fails.append("the shape-test control produced almost no groups -- "
                     "it is not a null, it is empty")
    if bad7:
        fails.append(f"{bad7} control groups are genuinely simultaneous -- "
                     "the null contains the thing it is controlling for")

    print()
    if fails:
        print("=" * 78)
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   - " + f)
        print("=" * 78)
        return False
    print("=" * 78)
    print("SELF-TEST PASSED -- silent on nothing, finds a planted tail in")
    print("the right bucket, immune to volatility clustering, anchored")
    print("strictly before the trade, and reads the sweep convention off")
    print("the shape of the prints rather than off a pooled second.")
    print("=" * 78)
    return True


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    from replay import load_quotes, load_markets
    from edge import load_trades
    from endgame import outcome_of
    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    quotes = load_quotes(a.data)
    if not quotes:
        print("\n  no quotes -- nothing to analyse")
        return
    trades = load_trades(a.data)
    if not trades:
        print("\n  no trades on disk -- nothing to analyse")
        return
    markets = load_markets(a.out)
    if not markets:
        print("\n  *** NO SETTLED MARKETS -- nothing to analyse")
        return
    print(f"  {sum(len(v) for v in trades.values()):,} trades, "
          f"{len(quotes):,} markets with quotes, "
          f"{len(markets):,} with settlements")
    sweep_shape(a.data)
    tables, used, skipped, sizes = measure(quotes, trades, markets,
                                           outcome_of, verbose=True)
    print(f"\n  {used:,} trades measured, {skipped:,} skipped "
          f"(no fresh pre-trade quote, no side, bad fields)")
    print(f"  size distribution across buckets: {sizes}")
    print("\n" + "=" * 78)
    print("WHO IS INFORMED -- signed drift to settlement, by condition")
    print("=" * 78)
    show_curve(tables)
    show_tables(tables)
    print("\n  READ IT IN THIS ORDER: shufS must be ~0 everywhere or stop.")
    print("  Then HEADLINE (can a maker stand anywhere?) and TAIL (does")
    print("  copying the big with-flow late trades clear the fee?). Only")
    print("  then browse -- anything else must clear the family threshold.")


if __name__ == "__main__":
    main()
