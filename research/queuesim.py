#!/usr/bin/env python3
# VERSION: 2026-09-06-q1
"""
queuesim.py -- the queue-position simulator. How many fills does a quote
resting at the touch ACTUALLY get?

    python research/queuesim.py --selftest
    python research/queuesim.py --data C:\\kals\\kalshi_data --out C:\\kals\\fulltape

WHY THIS FILE IS NAMED queuesim AND NOT queue

`queue` is a standard-library module and `research/` goes first on sys.path in
every stage, so `research/queue.py` shadows it for the whole process. That is
not hypothetical: `research/compression.py` killed 14 of 16 stages on Python
3.14 while passing every self-test on 3.11, which is why `shadow.py` exists.
The stub was written, `shadow.py ..` was run, and it printed

    *** research\\queue.py shadows the stdlib module `queue` on THIS Python
    (3.14).

and exited 1. The file is therefore `queuesim.py`.

WHAT IS BEING DECIDED

`informed.py` measures +0.48c per FILL for a maker resting at the touch, held
to settlement, on 17.1M at-touch fills over 1,071 closes. Nobody has measured
how many fills a resting quote GETS. The operator's kill criterion is

    expected fills/day x $0.005 >= $50/day at a size the depth measurement
    shows is actually fillable

so $50/day at half a cent needs ~10,000 FILLED CONTRACTS A DAY. That is the
number to beat and it is a big one. Anything that clears it is to be treated
as a measurement bug until proven otherwise.

THE MODEL, AND EVERY ASSUMPTION IN IT

1. We rest S contracts at the touch on one side. Both sides are simulated
   separately; a two-sided quoter gets the sum.

2. QUEUE POSITION. Orders already at that price are ahead of us. When we post
   (or re-post) we join the BACK: `ahead` = the whole size displayed at that
   price. We never assume a better position than last.

3. THE CLOCK IS ONE SECOND, and the reference book is STRICTLY EARLIER.
   The book state governing second `t` is the state at the END of second
   `t-1`. That is the same strictly-before rule `informed.py` uses, and it is
   the rule that stops a quote stamped inside the trade's own second (the book
   AFTER the trade) being read as the book before it -- the bug that measured
   a planted 1.000c as 0.000c in maker.py.

4. A TAKER CONSUMES FRONT-FIRST. A trade of V contracts at our price fills us
   min(S_remaining, max(0, V - ahead)) and leaves ahead = max(0, ahead - V).

5. SWEEPS PRINT PER LEVEL (settled 2026-09-06 on 12M trades at true ts_ms:
   96.6% of same-instant multi-price groups are single-sided monotone ladders
   over consecutive seq, against a size-matched adjacent control at 15.3%).
   So the touch leg of a sweep is its own print at its own price and counts as
   a fill at the touch. No de-duplication is applied here, and per the
   contradiction flagged in CLAUDE.md that is correct for a MAKER-FILL
   statistic and wrong for a taker-decision one.

6. CANCELS ARE THE ONE GENUINELY UNKNOWABLE PIECE. The tape shows the level
   shrinking; it does not show whether the cancelled orders were in front of
   us or behind. Three policies are run and all three are reported:
       behind   cancels come from BEHIND us -- ahead unchanged  (pessimistic)
       prorata  cancels are spread over the level               (HEADLINE)
       front    cancels come from IN FRONT of us -- ahead falls (optimistic)
   `ahead` is capped at the displayed size under every policy, because more
   cannot be in front of us than exists.

7. AFTER A COMPLETE FILL WE DO NOT RE-POST INSIDE THE SAME SECOND. We rejoin
   at the back of the queue at the next second boundary. That is a one-second
   re-quote latency and it is deliberately conservative.

8. WHAT THIS CANNOT SEE, stated because it moves the answer:
   * Our own S contracts are not in the tape's book, so we add depth that
     would in reality have pushed somebody else's fill onto us or ours onto
     them. At S=500 against a median touch of tens of contracts this is no
     longer a small perturbation and the result is an UPPER bound there.
   * The reference book second is the collector's LOCAL RECEIVE second
     (`_rx_ms`), the same clock `flow.py` mined on, and HANDOFF records that
     whole-second stamps make the reference quote a median 1.75s old in truth.
     A sub-second queue race is not decidable on this tape.
   * Latency, cancel/repost round trips, exchange priority rules beyond
     price-time, and whether Kalshi would let us rest this size are all
     outside the tape.

THE INPUT IS THE CACHED BOOK, AND IT IS NOT REBUILT

Top of book with sizes comes from `flow_cache/*.v4.csv.gz`, which `flow.py`
mined from orderbook_snapshot + orderbook_delta + ticker in seq order with
stale books quarantined. A cold rebuild is ~100 minutes and 22 GB of deltas;
this stage never triggers one. It reads the days that are cached and says
which days are missing.

THE SELF-TEST IS THE DELIVERABLE

  (a) a planted fill rate in a synthetic book, checked for EXACT equality, so
      the estimator fails if it is too high or too low;
  (b) a book where our quote is always last in queue and the incoming volume
      never exceeds the size resting ahead -- must return zero fills under
      all three cancel policies;
  (c) a book where our quote is never at the touch (prints inside the spread,
      prints outside it, and a side with no touch at all) -- must return zero;
  (d) a sign-scrambled companion for the signed measure (the money), which
      must come out inside its own MDE;
  plus a MUTATION check: the same planted world run through a deliberately
  broken estimator that ignores the queue, asserting that check (a) REJECTS
  it. A test that cannot fail is not a test.

NOTHING HERE PLACES AN ORDER.
"""

import argparse
import bisect
import glob
import gzip
import json
import math
import os
import random
import sys
from array import array
from collections import defaultdict
from statistics import mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tdist import crit as _tcrit                            # noqa: E402
from gzsalvage import iter_lines as salvage_lines          # noqa: E402
from endgame import outcome_of                             # noqa: E402

SIZES = (1, 10, 50, 100, 500)
POLICIES = ("behind", "prorata", "front")
HEADLINE_POLICY = "prorata"
MAKER_CENTS = 0.48          # informed.py, at-touch, held to settlement
NEAR_C = 6                  # keep trades within this many cents of the touch
BOOT = 20000
BOOT_SEED = 20260906
THRESHOLD = 50.0            # the operator's $/day kill criterion
HEAD_SIZE = 50              # the reference size the diagnostics quote
# THE PRICE GRID IS TAPERED and the cached book is not. engine.tick_at is
# 0.1c below 10c and above 90c, 1c between -- but flow.py stores top of book
# as int(round(dollars*100)), so in the deci-cent zone 0.9950 and 0.9990 both
# land on 100 and a print 0.4c away from the touch reads as AT the touch.
# The headline is therefore the exact-grid zone, and the deci-cent zone is
# reported separately as what it is: not decidable from this cache.
ZONE = (10, 90)

BID, ASK = 0, 1


def t_crit(df):
    return _tcrit(0.05, df)


# ===========================================================================
# THE SIMULATOR -- pure, no I/O, so the self-test drives the same code path
# ===========================================================================
def simulate_side(states, trades, sizes=SIZES, policy=HEADLINE_POLICY,
                  ignore_queue=False, recycle=True):
    """Fills for a quote resting at the touch on ONE side of ONE market.

    states  [(sec, price_c or None, size)] ascending, one row per second,
            the book at the END of that second.
    trades  [(sec, ms, price_c, size)] ascending, already restricted to the
            side being simulated. `sec` is the second the trade arrived IN,
            so it is matched against the state at the end of `sec - 1`.
    returns (fills, diag) where fills is {S: [(sec, price_c, qty, ahead)]}.

    `ignore_queue=True` is the deliberately broken estimator the mutation
    check in the self-test must reject: it credits every trade in full.
    """
    fills = {S: [] for S in sizes}
    pos = {S: [None, 0.0, 0.0, 0] for S in sizes}  # price, ahead, rem, requeue
    d = {"sec_pairs": 0, "sec_touch": 0, "sec_held": 0, "sec_traded": 0,
         "vol_at_price": 0.0, "sec_gap": 0, "ahead": [],
         "ahead_at_trade": [], "trade_size_at_price": []}
    ref = sizes[0]
    n, m = len(states), len(trades)
    ti = 0
    for i in range(1, n):
        s_prev, p_prev, d_prev = states[i - 1]
        s_cur, p_cur, d_cur = states[i]
        while ti < m and trades[ti][0] < s_cur:
            ti += 1
        tj = ti
        while tj < m and trades[tj][0] == s_cur:
            tj += 1
        d["sec_pairs"] += 1
        contiguous = (s_prev + 1 == s_cur)
        if not contiguous:
            d["sec_gap"] += 1
        if p_prev is not None:
            d["sec_touch"] += 1
        usable = contiguous and p_prev is not None and d_prev > 0
        if not usable:
            for S in sizes:
                pos[S][0] = None
                pos[S][1] = 0.0
                pos[S][2] = 0.0
                pos[S][3] = 0
            ti = tj
            continue
        if (i & 31) == 0:
            # subsampled: the touch-size distribution needs a few hundred
            # thousand draws, not six and a half million floats in a list.
            d["ahead"].append(d_prev)

        vol = 0.0
        traded_here = False
        for k in range(ti, tj):
            if trades[k][2] == p_prev:
                vol += trades[k][3]
                traded_here = True
        if traded_here:
            d["sec_traded"] += 1
            d["vol_at_price"] += vol
        if p_cur == p_prev:
            d["sec_held"] += 1

        for S in sizes:
            st = pos[S]
            if st[0] != p_prev or st[2] <= 1e-12:
                st[0] = p_prev
                st[1] = d_prev
                st[2] = float(S)
                st[3] = 0
            elif st[3]:
                # NO-CAMP: we were filled last second, so we go to the BACK
                # of the queue with what is left of the order rather than
                # keeping the front position the fill handed us.
                st[1] = d_prev
                st[3] = 0
            elif st[1] > d_prev:
                st[1] = d_prev
            if traded_here:
                first = (S == ref)
                for k in range(ti, tj):
                    tp, tsz = trades[k][2], trades[k][3]
                    if tp != p_prev:
                        continue
                    if first:
                        d["ahead_at_trade"].append(st[1])
                        d["trade_size_at_price"].append(tsz)
                    if ignore_queue:
                        f = min(st[2], tsz)
                    else:
                        f = min(st[2], max(0.0, tsz - st[1]))
                        st[1] = max(0.0, st[1] - tsz)
                    if f > 1e-12:
                        fills[S].append((s_cur, tp, f, st[1], tsz))
                        st[2] -= f
                        if not recycle:
                            # THE STRICT BOUND. Once a taker has cleared the
                            # queue we sit at the FRONT, and at 40+ prints a
                            # second on a busy market a one-second clock hands
                            # us that front position for far longer than a
                            # real maker would hold it against sub-100ms
                            # competitors. recycle=False forbids camping: any
                            # fill ends our participation for that second and
                            # we rejoin at the BACK next second with WHAT IS
                            # LEFT of the order, never topped back up to S.
                            st[3] = 1
                            break
                    if st[2] <= 1e-12:
                        break
            # --- boundary: reconcile to the state at the end of this second
            if p_cur != p_prev:
                continue                    # re-posts on the next iteration
            after = d_prev - vol
            if after < 0.0:
                after = 0.0
            change = d_cur - after
            if change < 0.0:
                if policy == "front":
                    st[1] = max(0.0, st[1] + change)
                elif policy == "prorata":
                    st[1] = (st[1] * (d_cur / after)) if after > 0 else 0.0
            if st[1] > d_cur:
                st[1] = d_cur
        ti = tj
    return fills, d


# ===========================================================================
# statistics
# ===========================================================================
def boot_ci(vals, per_day, reps=BOOT, seed=BOOT_SEED):
    """Percentile bootstrap over CLOSES. No normal-theory SE: the money
    distribution here is nothing like a normal one and pin died on exactly
    that point."""
    rng = random.Random(seed)
    n = len(vals)
    if n == 0:
        return None
    ms = []
    rr = rng.randrange
    for _ in range(reps):
        s = 0.0
        for _ in range(n):
            s += vals[rr(n)]
        ms.append(s / n)
    ms.sort()
    lo, hi = ms[int(0.025 * reps)], ms[int(0.975 * reps)]
    return {"mean": mean(vals), "lo": lo, "hi": hi, "n": n,
            "day": mean(vals) * per_day,
            "day_lo": lo * per_day, "day_hi": hi * per_day}


def verdict(b, threshold=THRESHOLD):
    if b is None:
        return "NO DATA"
    if b["day_lo"] >= threshold:
        return "PASS"
    if b["day_hi"] < threshold:
        return "MISS"
    return "INCONCLUSIVE"


def clustered(by_close):
    """Equal-weight close-time clusters, exactly as informed.Cell.stat."""
    cl = [s / n for s, n in by_close.values() if n > 0]
    G = len(cl)
    ntr = sum(n for _, n in by_close.values())
    if G < 30:
        return {"G": G, "n": ntr, "mean": mean(cl) if cl else None,
                "t": None, "mde": None}
    mu = mean(cl)
    sd = pstdev(cl) * math.sqrt(G / (G - 1.0))
    se = sd / math.sqrt(G)
    return {"G": G, "n": ntr, "mean": mu,
            "t": (mu / se if se > 0 else 0.0), "mde": t_crit(G - 1) * se}


def quantiles(v, fracs=(0.10, 0.50, 0.90)):
    if not v:
        return [None] * len(fracs)
    w = sorted(v)
    return [w[min(len(w) - 1, int(f * len(w)))] for f in fracs]


# ===========================================================================
# THE SELF-TEST -- this is the deliverable
# ===========================================================================
def _alt_states(n, price_a=50, price_b=49, size=20.0, t0=1000):
    """A book whose touch price alternates every second, so a resting quote
    is re-posted at the BACK of the queue every second. That makes the fill
    per event a closed form: min(S, max(0, V - size))."""
    return [(t0 + i, (price_a if i % 2 == 0 else price_b), float(size))
            for i in range(n)]


def _events_on(states, every, vol):
    """One trade every `every` seconds, at the price we are actually resting
    at during that second -- the touch at the END of the previous second."""
    out = []
    for i in range(1, len(states)):
        if states[i][0] % every == 0:
            out.append((states[i][0], 0, states[i - 1][1], float(vol)))
    return out


def _total(fills):
    return {S: sum(f[2] for f in v) for S, v in fills.items()}


def selftest(verbose=True):
    ok = True

    def check(label, cond, detail=""):
        nonlocal ok
        if not cond:
            ok = False
        if verbose:
            tag = "ok" if cond else "FAIL"
            extra = ("   " + detail) if detail else ""
            print("    [%s] %s%s" % (tag, label, extra))
        return cond

    if verbose:
        print("=" * 78)
        print("QUEUE SIMULATOR SELF-TEST")
        print("=" * 78)

    # ------------------------------------------------------------------
    # (a) A PLANTED FILL RATE, CHECKED FOR EXACT EQUALITY IN BOTH
    #     DIRECTIONS. The world is built so the answer is closed form: the
    #     touch price alternates every second, so we always join the back of
    #     a queue of D, and one trade of V arrives every tenth second,
    #     filling us exactly min(S, max(0, V - D)).
    # ------------------------------------------------------------------
    if verbose:
        print("\n  (a) a KNOWN fill rate planted in a synthetic book")
    for (D, V) in ((20.0, 25.0), (20.0, 200.0), (200.0, 40.0)):
        st = _alt_states(2000, size=D)
        tr = _events_on(st, 10, V)
        n_ev = len(tr)
        want = {S: n_ev * min(float(S), max(0.0, V - D)) for S in SIZES}
        for pol in POLICIES:
            got = _total(simulate_side(st, tr, policy=pol)[0])
            check("D=%5.0f V=%5.0f policy=%-7s %d events" % (D, V, pol, n_ev),
                  all(abs(got[S] - want[S]) < 1e-9 for S in SIZES),
                  "want %s got %s" % ([want[S] for S in SIZES],
                                      [round(got[S], 6) for S in SIZES]))

    # The same worlds must also refuse to over-credit: a fill can never
    # exceed the volume that actually printed at our price.
    st = _alt_states(2000, size=20.0)
    tr = _events_on(st, 10, 25.0)
    f, dg = simulate_side(st, tr)
    tot = _total(f)
    check("no fill exceeds the volume printed at our price",
          all(tot[S] <= dg["vol_at_price"] + 1e-9 for S in SIZES),
          "volume %.0f vs max fills %.0f" % (dg["vol_at_price"],
                                             max(tot.values())))
    check("fills are non-decreasing in S",
          all(tot[SIZES[i]] <= tot[SIZES[i + 1]] + 1e-9
              for i in range(len(SIZES) - 1)))

    # THE MUTATION CHECK. A test that cannot fail is not a test: run the same
    # planted world through an estimator that ignores the queue entirely and
    # assert check (a) REJECTS it.
    bad = _total(simulate_side(st, tr, ignore_queue=True)[0])
    want = {S: len(tr) * min(float(S), 25.0 - 20.0) for S in SIZES}
    check("MUTATION: a queue-ignoring estimator is REJECTED by (a)",
          any(abs(bad[S] - want[S]) > 1e-9 for S in SIZES),
          "broken gives %s, true %s" % ([round(bad[S], 1) for S in SIZES],
                                        [want[S] for S in SIZES]))

    # ------------------------------------------------------------------
    # (b) ALWAYS LAST IN QUEUE, and the incoming volume NEVER exceeds the
    #     size resting ahead. Zero fills, under every cancel policy.
    # ------------------------------------------------------------------
    if verbose:
        print("\n  (b) always last in queue, volume < size ahead -> zero")
    st = _alt_states(2000, size=1000.0)
    tr = _events_on(st, 1, 900.0)
    dg = None
    for pol in POLICIES:
        f, dg = simulate_side(st, tr, policy=pol)
        t = _total(f)
        check("policy=%-7s zero fills on %d trades" % (pol, len(tr)),
              all(v == 0.0 for v in t.values()),
              "volume seen %s contracts, fills %s"
              % (format(dg["vol_at_price"], ",.0f"),
                 [round(t[S], 6) for S in SIZES]))
    check("the zero is not that it never saw the trades",
          dg["vol_at_price"] > 1.0e6,
          "%s contracts of volume at our price"
          % format(dg["vol_at_price"], ",.0f"))

    # ------------------------------------------------------------------
    # (c) NEVER AT THE TOUCH. Prints inside the spread, prints outside it,
    #     and a side with no touch at all. Nothing may be credited.
    # ------------------------------------------------------------------
    if verbose:
        print("\n  (c) our quote was never at the touch -> zero")
    st = [(1000 + i, 40, 100.0) for i in range(2000)]
    tr = [(1000 + i, 0, [45, 30, 70, 55, 41, 39][i % 6], 500.0)
          for i in range(1, 2000)]
    f, dg = simulate_side(st, tr)
    t = _total(f)
    check("prints at 45/30/70/55/41/39 against a touch of 40",
          all(v == 0.0 for v in t.values()),
          "fills %s" % [round(t[S], 6) for S in SIZES])
    st_none = [(1000 + i, None, 0.0) for i in range(2000)]
    tr2 = [(1000 + i, 0, 50, 500.0) for i in range(1, 2000)]
    t = _total(simulate_side(st_none, tr2)[0])
    check("a side with no touch at all",
          all(v == 0.0 for v in t.values()))
    # a hole in the second grid must DROP the position, not carry it
    st_gap = [(1000, 50, 20.0), (1001, 50, 20.0), (2000, 50, 20.0),
              (2001, 50, 20.0)]
    tr3 = [(2000, 0, 50, 10000.0)]
    f, dg = simulate_side(st_gap, tr3)
    check("a hole in the second grid drops the position",
          all(v == 0.0 for v in _total(f).values()),
          "%d gap(s) seen" % dg["sec_gap"])

    # ------------------------------------------------------------------
    # (d) THE SIGN-SCRAMBLED COMPANION for the signed measure (the money).
    #     A planted +40c per fill must be found; the same fills with random
    #     signs must land inside their own MDE of zero.
    # ------------------------------------------------------------------
    if verbose:
        print("\n  (d) sign-scrambled control on the money")
    rnd = random.Random(11)
    real, shuf = defaultdict(lambda: [0.0, 0]), defaultdict(lambda: [0.0, 0])
    for mkt in range(80):
        st = _alt_states(400, size=20.0, t0=1000 + mkt * 10000)
        tr = _events_on(st, 10, 25.0)
        f, _ = simulate_side(st, tr)
        close = 1000 + mkt * 10000 + 400
        for (_s, _p, q, _a, _v) in f[50]:
            # planted: we sold YES at 40c into a market that settles NO, so
            # the maker makes exactly +40c per contract.
            pnl = 40.0
            real[close][0] += pnl * q
            real[close][1] += q
            sg = rnd.choice((1.0, -1.0))
            shuf[close][0] += sg * pnl * q
            shuf[close][1] += q
    r, s = clustered(real), clustered(shuf)
    check("planted +40.000c per contract is recovered",
          r["mean"] is not None and abs(r["mean"] - 40.0) < 1e-9,
          "got %+.6fc on G=%d" % (r["mean"], r["G"]))
    check("sign-scrambled control is inside its own MDE",
          s["mde"] is not None and abs(s["mean"]) < s["mde"],
          "%+.3fc vs MDE %.3fc on G=%d" % (s["mean"], s["mde"], s["G"]))

    # THE STRICT BOUND MUST BE A BOUND. recycle=False forbids camping at the
    # front of the queue after a partial fill, so it can never find MORE.
    st = _alt_states(2000, price_a=50, price_b=50, size=1000.0)
    tr = _events_on(st, 2, 1100.0)
    loose = _total(simulate_side(st, tr)[0])
    strict = _total(simulate_side(st, tr, recycle=False)[0])
    check("the strict (no queue-camping) bound is a bound",
          all(strict[S] <= loose[S] + 1e-9 for S in SIZES)
          and any(strict[S] < loose[S] - 1e-9 for S in SIZES),
          "loose %s strict %s" % ([round(loose[S]) for S in SIZES],
                                  [round(strict[S]) for S in SIZES]))

    # A placebo on the FILL COUNT itself: move our quote one cent off the
    # touch and the same tape must stop filling us.
    st = _alt_states(2000, size=20.0)
    tr = _events_on(st, 10, 25.0)
    st_off = [(s, (None if p is None else p + 1), d) for (s, p, d) in st]
    t_off = _total(simulate_side(st_off, tr)[0])
    t_on = _total(simulate_side(st, tr)[0])
    check("quoting 1c off the touch collapses the fills",
          sum(t_off.values()) == 0.0 and sum(t_on.values()) > 0.0,
          "on-touch %.0f vs off-touch %.0f"
          % (sum(t_on.values()), sum(t_off.values())))

    # ------------------------------------------------------------------
    # bootstrap plumbing: an interval that straddles the threshold must be
    # INCONCLUSIVE, never PASS. That rule killed pin and it is checked here
    # rather than trusted.
    # ------------------------------------------------------------------
    if verbose:
        print("\n  bootstrap / verdict plumbing")
    b = boot_ci([1.0] * 200, 50.0, reps=2000)
    check("a degenerate sample gives a degenerate interval",
          abs(b["day"] - 50.0) < 1e-9 and abs(b["day_lo"] - 50.0) < 1e-9)
    wide = boot_ci([0.0, 4.0] * 100, 25.0, reps=4000)
    check("an interval straddling $50 reads INCONCLUSIVE",
          verdict(wide) == "INCONCLUSIVE",
          "[%.0f, %.0f] -> %s" % (wide["day_lo"], wide["day_hi"],
                                  verdict(wide)))
    low = boot_ci([0.1] * 200, 50.0, reps=2000)
    check("an interval wholly below $50 reads MISS",
          verdict(low) == "MISS")

    if verbose:
        print("\n" + ("  SELF-TEST PASSED" if ok else "  SELF-TEST FAILED"))
    return ok


# ===========================================================================
# LOADING -- the cached book, then the trades. Nothing is rebuilt.
# ===========================================================================
SENT = -1                       # sentinel price for a second with no touch


def load_book(cache_dir, days=None, verbose=True):
    """ticker -> (sec0, bid_c, ask_c, bid_sz, ask_sz) offset-indexed by
    (second - sec0).

    Each 15-minute market has exactly one window, so the per-ticker arrays are
    ~870 entries and a lookup is O(1) arithmetic rather than a bisect over
    6.5 million rows. Prices stay small ints; sizes are float32.
    """
    paths = sorted(glob.glob(os.path.join(cache_dir, "*.v4.csv.gz")))
    if days:
        paths = [p for p in paths if os.path.basename(p)[:8] in days]
    raw = {}
    n = 0
    src = defaultdict(int)
    for fp in paths:
        with gzip.open(fp, "rt", encoding="utf-8") as f:
            if not f.readline().startswith("ticker,"):
                continue
            for line in f:
                p = line.rstrip("\n").split(",")
                if len(p) != 11:
                    continue
                try:
                    sec = int(p[1])
                    bc, ac = int(p[2]), int(p[3])
                    bs, as_ = float(p[4]), float(p[5])
                except ValueError:
                    continue
                r = raw.get(p[0])
                if r is None:
                    r = raw[p[0]] = (array("i"), array("h"), array("h"),
                                     array("f"), array("f"))
                r[0].append(sec)
                r[1].append(bc)
                r[2].append(ac)
                r[3].append(bs)
                r[4].append(as_)
                src[p[10].strip()] += 1
                n += 1
    book = {}
    truncated = 0
    for tk, r in raw.items():
        s = r[0]
        sec0, sec1 = min(s), max(s)
        span = sec1 - sec0 + 1
        if span > 4000:      # a ticker should hold ONE 15-minute window
            span = 4000
            truncated += 1
        bc = array("h", [SENT]) * span
        ac = array("h", [SENT]) * span
        bs = array("f", [0.0]) * span
        as_ = array("f", [0.0]) * span
        for i in range(len(s)):
            o = s[i] - sec0
            if 0 <= o < span:
                bc[o] = r[1][i]
                ac[o] = r[2][i]
                bs[o] = r[3][i]
                as_[o] = r[4][i]
        book[tk] = (sec0, bc, ac, bs, as_)
    if verbose:
        print("  book: %s market-seconds over %s markets from %d cached day(s)"
              % (format(n, ","), format(len(book), ","), len(paths)))
        print("        top of book from the rebuilt delta book %s, "
              "from the ticker channel %s"
              % (format(src.get("B", 0), ","), format(src.get("T", 0), ",")))
        if truncated:
            print("        %d ticker(s) spanned more than 4000s and were "
                  "truncated" % truncated)
    return book


def cached_days(cache_dir):
    return sorted({os.path.basename(p)[:8]
                   for p in glob.glob(os.path.join(cache_dir, "*.v4.csv.gz"))})


def load_trades(data_dir, book, days, near=NEAR_C, verbose=True, cap=None):
    """ticker -> [bid-side arrays, ask-side arrays], each (sec, ms, price, sz).

    taker_side "no"  consumed a resting YES BID  -> fills a maker's bid
    taker_side "yes" consumed a resting YES ASK  -> fills a maker's ask
    exactly as informed.py signs it (sgn=+1 for a yes taker, touch = the ask).

    The second is the collector's LOCAL RECEIVE second, because that is the
    clock flow.py mined the book on. Mixing Kalshi's exchange stamp with the
    receive stamp would put trades in the wrong second some of the time.

    Only trades within `near` cents of the touch are kept. That is a bounded
    superset of what can ever fill us and it keeps the off-touch placebo
    runnable; the count discarded is printed.
    """
    keep = {}
    stat = defaultdict(int)
    files = sorted(glob.glob(os.path.join(data_dir, "trade", "*.jsonl.gz")))
    files = [f for f in files if os.path.basename(f)[:8] in days]
    stop = False
    for fp in files:
        if stop:
            break
        # salvage_lines, not gzip.open: the collector appends a second gzip
        # member after a restart inside the hour and a plain reader then
        # recovers ZERO lines from that file with "invalid block type".
        for line in salvage_lines(fp):
            try:
                m = json.loads(line)
            except Exception:
                stat["unparsed"] += 1
                continue
            d = m.get("msg") or {}
            tk = d.get("market_ticker") or d.get("ticker")
            b = book.get(tk)
            if b is None:
                stat["no_book_for_ticker"] += 1
                continue
            rx = m.get("_rx_ms")
            if not isinstance(rx, (int, float)):
                rx = d.get("ts_ms")
            if not isinstance(rx, (int, float)):
                stat["no_timestamp"] += 1
                continue
            sec = int(rx // 1000)
            ms = int(rx - sec * 1000)
            pv = d.get("yes_price_dollars")
            try:
                if pv is not None:
                    pf = float(pv) * 100.0
                else:
                    pf = float(d.get("yes_price"))
            except (TypeError, ValueError):
                stat["bad_price"] += 1
                continue
            pc = int(round(pf))
            if abs(pf - pc) > 1e-6:
                stat["subcent_price"] += 1
            sv = d.get("count_fp")
            if sv is None:
                sv = d.get("count")
            try:
                sz = float(sv)
            except (TypeError, ValueError):
                stat["bad_size"] += 1
                continue
            side = str(d.get("taker_side", "")).lower()
            if side.startswith("y"):
                k = ASK
            elif side.startswith("n"):
                k = BID
            else:
                stat["no_taker_side"] += 1
                continue
            sec0, bc, ac, _bs, _as = b
            o = (sec - 1) - sec0
            if not (0 <= o < len(bc)):
                stat["outside_book_window"] += 1
                continue
            touch = ac[o] if k == ASK else bc[o]
            if touch == SENT:
                stat["no_touch_that_second"] += 1
                continue
            stat["in_window"] += 1
            stat["vol_in_window"] += sz
            inzone = ZONE[0] <= touch <= ZONE[1]
            if pc == touch:
                stat["at_touch"] += 1
                stat["vol_at_touch"] += sz
                if inzone:
                    stat["vol_at_touch_zone"] += sz
                else:
                    stat["vol_at_touch_deci"] += sz
            if abs(pc - touch) > near:
                stat["far_from_touch"] += 1
                continue
            e = keep.get(tk)
            if e is None:
                e = keep[tk] = [[array("i"), array("h"), array("h"),
                                 array("f")],
                                [array("i"), array("h"), array("h"),
                                 array("f")]]
            a = e[k]
            a[0].append(sec)
            a[1].append(ms)
            a[2].append(pc)
            a[3].append(sz)
            stat["kept"] += 1
            if cap and stat["kept"] >= cap:
                stop = True
                break
    if verbose:
        iw = max(1, stat["in_window"])
        print("  trades: %d file(s) over the cached days" % len(files))
        print("          %s inside a book window; %s exactly at the touch "
              "(%.1f%%); %s kept within %dc"
              % (format(stat["in_window"], ","), format(stat["at_touch"], ","),
                 100.0 * stat["at_touch"] / iw, format(stat["kept"], ","),
                 near))
        print("          contracts: %s in a window, %s at the touch (%.1f%%)"
              % (format(int(stat["vol_in_window"]), ","),
                 format(int(stat["vol_at_touch"]), ","),
                 100.0 * stat["vol_at_touch"] / max(1.0,
                                                    stat["vol_in_window"])))
        print("          dropped: outside a window %s, no touch that second "
              "%s, more than %dc out %s, ticker absent from the book %s"
              % (format(stat["outside_book_window"], ","),
                 format(stat["no_touch_that_second"], ","), near,
                 format(stat["far_from_touch"], ","),
                 format(stat["no_book_for_ticker"], ",")))
        print("          sub-cent print prices (rounded to the book grid): %s"
              % format(stat["subcent_price"], ","))
        vz, vd = stat["vol_at_touch_zone"], stat["vol_at_touch_deci"]
        print("          at-touch contracts by tick zone: %s on the exact 1c"
              " grid (%dc-%dc), %s in the 0.1c zone (%.1f%%)"
              % (format(int(vz), ","), ZONE[0], ZONE[1], format(int(vd), ","),
                 100.0 * vd / max(1.0, vz + vd)))
        print("          the 0.1c zone is EXCLUDED from the headline: the")
        print("          cached book rounds those prices to whole cents, so a")
        print("          print up to 0.5c away would read as at the touch.")
    return keep, stat


# ===========================================================================
# THE RUN
# ===========================================================================
def run(book, trades, markets, sizes=SIZES, policy=HEADLINE_POLICY,
        offset=0, verbose=True, seed=BOOT_SEED, collect=True, zone=ZONE,
        recycle=True):
    """Simulate every market, both sides, at every size.

    `offset` moves our quote that many cents INSIDE the book, away from the
    touch. It is the placebo for requirement (c) on real data: a quote that is
    never at the touch must not be filled.
    """
    rng = random.Random(seed)
    fills = {S: defaultdict(float) for S in sizes}     # close -> contracts
    money = {S: defaultdict(float) for S in sizes}     # close -> dollars
    shuf = {S: defaultdict(float) for S in sizes}      # close -> dollars
    percontract = {S: defaultdict(lambda: [0.0, 0.0]) for S in sizes}
    side_fills = {S: {BID: 0.0, ASK: 0.0} for S in sizes}
    touch_sizes = array("f")
    ahead_at_trade = array("f")
    trade_size_at_price = array("f")
    fill_trade_size = array("f")
    net_per_market = array("f")          # signed position left at settlement
    notional_per_close = defaultdict(float)
    diag = defaultdict(float)
    closes = set()
    for tk, (sec0, bc, ac, bs, as_) in book.items():
        m = markets.get(tk)
        if not m:
            diag["market_without_settlement"] += 1
            continue
        close, res = m.get("close"), outcome_of(m)
        if close is None or res is None:
            diag["market_without_settlement"] += 1
            continue
        try:
            Y = 100.0 * float(res)
            close = int(close)
        except (TypeError, ValueError):
            diag["market_without_settlement"] += 1
            continue
        tr = trades.get(tk)
        diag["markets"] += 1
        closes.add(close)
        mkt_net = {BID: 0.0, ASK: 0.0}
        for k in (BID, ASK):
            pc_arr = bc if k == BID else ac
            sz_arr = bs if k == BID else as_
            off = offset if k == BID else -offset
            states = []
            ap = states.append
            zlo, zhi = zone if zone else (-1, 1000)
            for o in range(len(pc_arr)):
                p = pc_arr[o]
                if p == SENT:
                    ap((sec0 + o, None, 0.0))
                elif not (zlo <= p <= zhi):
                    diag["sec_outside_zone"] += 1
                    ap((sec0 + o, None, 0.0))
                else:
                    ap((sec0 + o, p - off, sz_arr[o]))
            tl = []
            if tr is not None:
                a = tr[k]
                for i in range(len(a[0])):
                    tl.append((a[0][i], a[1][i], a[2][i], a[3][i]))
                tl.sort()
            f, dg = simulate_side(states, tl, sizes=sizes, policy=policy,
                                  recycle=recycle)
            for key in ("sec_pairs", "sec_touch", "sec_held", "sec_traded",
                        "sec_gap", "vol_at_price"):
                diag[key] += dg[key]
            if collect:
                for v in dg["ahead"]:
                    touch_sizes.append(v)
                for v in dg["ahead_at_trade"]:
                    ahead_at_trade.append(v)
                for v in dg["trade_size_at_price"]:
                    trade_size_at_price.append(v)
            for S in sizes:
                fs, ms_, sh = fills[S], money[S], shuf[S]
                pcs = percontract[S]
                for (_s, p, q, _ah, tsz) in f[S]:
                    pnl = (Y - p) if k == BID else (p - Y)
                    fs[close] += q
                    ms_[close] += pnl * q / 100.0
                    sh[close] += rng.choice((1.0, -1.0)) * pnl * q / 100.0
                    c = pcs[close]
                    c[0] += pnl * q
                    c[1] += q
                    side_fills[S][k] += q
                    if S == HEAD_SIZE:
                        mkt_net[k] += q
                        notional_per_close[close] += p * q / 100.0
                        if collect:
                            fill_trade_size.append(tsz)
        net_per_market.append(mkt_net[BID] - mkt_net[ASK])
    return {"net_per_market": net_per_market,
            "notional_per_close": notional_per_close,
            "fills": fills, "money": money, "shuf": shuf,
            "percontract": percontract, "side_fills": side_fills,
            "touch_sizes": touch_sizes, "ahead_at_trade": ahead_at_trade,
            "trade_size_at_price": trade_size_at_price,
            "fill_trade_size": fill_trade_size,
            "closes": closes, "diag": diag}


# ===========================================================================
# THE NUMBER PLAN.md KILLED THIS STRATEGY ON
# ===========================================================================
def plan_check(cache_dir, days=None, verbose=True):
    """PLAN.md sec.4 went taker-only on one observation: "best bid 0.40 with
    3,767 contracts resting". RUNBOOK separately records that the REST
    endpoint it came from returns levels ASCENDING and truncates from the
    BOTTOM, hiding top of book. Here is the same quantity off the websocket
    stream, for every market-second we have, with the 40c slice called out.
    """
    at40, alltouch = array("f"), array("f")
    n = 0
    over = 0
    paths = sorted(glob.glob(os.path.join(cache_dir, "*.v4.csv.gz")))
    if days:
        paths = [p for p in paths if os.path.basename(p)[:8] in days]
    for fp in paths:
        with gzip.open(fp, "rt", encoding="utf-8") as f:
            if not f.readline().startswith("ticker,"):
                continue
            for line in f:
                p = line.rstrip("\n").split(",")
                if len(p) != 11:
                    continue
                try:
                    bc = int(p[2])
                    bs, as_ = float(p[4]), float(p[5])
                except ValueError:
                    continue
                n += 1
                alltouch.append(bs)
                alltouch.append(as_)
                if bs >= 3767.0 or as_ >= 3767.0:
                    over += 1
                if bc == 40:
                    at40.append(bs)
    q = quantiles(alltouch, (0.10, 0.25, 0.50, 0.75, 0.90, 0.99, 0.999))
    q40 = quantiles(at40, (0.10, 0.50, 0.90, 0.99, 0.999))
    if verbose:
        print("\n" + "=" * 78)
        print("PLAN.md's KILL NUMBER, RE-MEASURED: \"best bid 0.40 with 3,767")
        print("contracts resting\"")
        print("=" * 78)
        print("  %s market-seconds, %s touch observations (both sides)"
              % (format(n, ","), format(len(alltouch), ",")))
        print("  contracts AT the touch   p10 %.0f  p25 %.0f  MEDIAN %.0f  "
              "p75 %.0f  p90 %.0f  p99 %.0f  p99.9 %.0f  max %.0f"
              % (q[0], q[1], q[2], q[3], q[4], q[5], q[6],
                 max(alltouch) if alltouch else 0.0))
        if at40:
            print("  the 40c slice: %s seconds with a best bid of exactly 40c"
                  % format(len(at40), ","))
            print("    bid size there  p10 %.0f  MEDIAN %.0f  p90 %.0f  "
                  "p99 %.0f  p99.9 %.0f  max %.0f"
                  % (q40[0], q40[1], q40[2], q40[3], q40[4], max(at40)))
        print("  market-seconds with 3,767+ resting on EITHER touch: %s "
              "(%.3f%% of %s)"
              % (format(over, ","), 100.0 * over / max(1, n), format(n, ",")))
    return {"n": n, "q": q, "q40": q40, "over": over,
            "max": max(alltouch) if alltouch else 0.0,
            "n40": len(at40)}


# ===========================================================================
def _closes_per_day(closes):
    if len(closes) < 2:
        return 0.0
    span = (max(closes) - min(closes)) / 86400.0
    return (len(closes) / span) if span > 0 else 0.0


def _report(res, cpd, sizes, tag, boot_reps=BOOT):
    """Per-size table: contracts filled, $/day at the informed rate, and
    $/day realised against the actual settlements with a bootstrap CI."""
    closes = sorted(res["closes"])
    rows = []
    for S in sizes:
        fpc = [res["fills"][S].get(c, 0.0) for c in closes]
        mpc = [res["money"][S].get(c, 0.0) for c in closes]
        spc = [res["shuf"][S].get(c, 0.0) for c in closes]
        tot_f = sum(fpc)
        fills_day = (tot_f / len(closes)) * cpd if closes else 0.0
        implied = fills_day * MAKER_CENTS / 100.0
        b = boot_ci(mpc, cpd, reps=boot_reps)
        bs = boot_ci(spc, cpd, reps=boot_reps)
        pc = clustered(res["percontract"][S])
        rows.append({"S": S, "fills": tot_f, "fills_day": fills_day,
                     "implied_day": implied, "boot": b, "shuf": bs,
                     "percontract": pc,
                     "bid": res["side_fills"][S][BID],
                     "ask": res["side_fills"][S][ASK],
                     "money_per_close": mpc})
    print("\n" + "=" * 78)
    print("FILLS AND MONEY  --  %s" % tag)
    print("=" * 78)
    print("  %s closes over the cached tape, %.1f closes/day"
          % (format(len(closes), ","), cpd))
    print("  %-5s %13s %12s %11s %11s %24s  %s"
          % ("S", "contracts", "contracts", "$/day at", "$/day",
             "95%% bootstrap", "verdict"))
    print("  %-5s %13s %12s %11s %11s %24s"
          % ("", "filled", "/day", "+0.48c", "realised", "on realised"))
    for r in rows:
        b = r["boot"]
        print("  %-5d %13s %12s %11.0f %11.0f   [%+8.0f, %+8.0f]   %s"
              % (r["S"], format(int(r["fills"]), ","),
                 format(int(r["fills_day"]), ","), r["implied_day"],
                 b["day"], b["day_lo"], b["day_hi"], verdict(b)))
    print("\n  realised P&L per FILLED CONTRACT, clustered on close time")
    print("  (informed.py measures +0.48c per at-touch fill; this is the same")
    print("   quantity restricted to the fills our queue position wins)")
    print("  %-5s %10s %8s %9s %8s   %s"
          % ("S", "cents", "t", "MDE", "closes", "sign-scrambled $/day"))
    for r in rows:
        pc, bs = r["percontract"], r["shuf"]
        t = "     n/a" if pc["t"] is None else "%8.2f" % pc["t"]
        mde = "      n/a" if pc["mde"] is None else "%9.3f" % pc["mde"]
        mu = "       n/a" if pc["mean"] is None else "%+10.3f" % pc["mean"]
        print("  %-5d %10s %s %s %8d   %+8.0f  [%+7.0f, %+7.0f]"
              % (r["S"], mu, t, mde, pc["G"], bs["day"], bs["day_lo"],
                 bs["day_hi"]))
    print("\n  where the fills come from (contracts, %s)" % tag)
    for r in rows:
        tot = r["bid"] + r["ask"]
        print("    S=%-4d bid side %13s   ask side %13s   bid share %.1f%%"
              % (r["S"], format(int(r["bid"]), ","),
                 format(int(r["ask"]), ","),
                 100.0 * r["bid"] / max(1.0, tot)))
    return rows


def _concentration(rows, cpd):
    print("\n" + "=" * 78)
    print("CONCENTRATION  --  pin died partly on this, so it is checked here")
    print("=" * 78)
    print("  %-5s %10s %8s %8s %8s   %s"
          % ("S", "$/day", "top 5", "top 10", "top 25", "$/day dropping the"
             " top 10 / top 25"))
    for r in rows:
        v = sorted(r["money_per_close"], reverse=True)
        tot = sum(v)
        if abs(tot) < 1e-12:
            continue
        d10 = mean(v[10:]) * cpd if len(v) > 10 else 0.0
        d25 = mean(v[25:]) * cpd if len(v) > 25 else 0.0
        print("  %-5d %10.0f %7.0f%% %7.0f%% %7.0f%%   %+8.0f / %+8.0f"
              % (r["S"], mean(v) * cpd, 100.0 * sum(v[:5]) / tot,
                 100.0 * sum(v[:10]) / tot, 100.0 * sum(v[:25]) / tot,
                 d10, d25))
    print("\n  the same for FILL VOLUME rather than money")
    return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--cache", default=None,
                    help="flow_cache directory (default: <repo>/flow_cache)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--quick", action="store_true",
                    help="fewer bootstrap reps and no policy bounds")
    ap.add_argument("--days", type=int, default=0,
                    help="use only the first N cached days")
    ap.add_argument("--trade-cap", type=int, default=0)
    ap.add_argument("--near", type=int, default=NEAR_C)
    a = ap.parse_args()

    if a.selftest:
        return 0 if selftest() else 1
    if not os.environ.get("KALS_SELFTESTED"):
        if not selftest(verbose=False):
            print("  self-test FAILED -- refusing to touch real data")
            return 1
        print("  self-test passed")

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache = a.cache or os.path.join(root, "flow_cache")
    days = cached_days(cache)
    if a.days:
        days = days[:a.days]
    print("=" * 78)
    print("QUEUE-POSITION SIMULATOR")
    print("=" * 78)
    print("  cached book days: %s" % (", ".join(days) if days else "none"))
    have = set(days)
    ob = sorted({os.path.basename(p)[:8] for p in
                 glob.glob(os.path.join(a.data, "orderbook_delta",
                                        "*.jsonl.gz"))})
    missing = [d for d in ob if d not in have]
    if missing:
        print("  days of tape with NO cached book: %s" % ", ".join(missing))
        print("  they are excluded. flow.py is ~100 min on a cold cache and")
        print("  this stage does not trigger one.")

    from replay import load_markets                       # noqa: E402
    markets = load_markets(a.out)
    print("  settlements: %s markets in markets.json" % format(len(markets),
                                                               ","))
    if not markets:
        print("  the settlement pull is empty -- run kalshi_fulltape.py first")
        return 1

    pc = plan_check(cache, days=set(days))

    print("\nloading ...")
    book = load_book(cache, days=set(days))
    trades, tstat = load_trades(a.data, book, set(days), near=a.near,
                                cap=(a.trade_cap or None))
    if not book:
        print("  the cached book holds nothing -- flow.py has not run here")
        return 1

    reps = 4000 if a.quick else BOOT
    print("\nsimulating (policy=%s) ..." % HEADLINE_POLICY)
    res = run(book, trades, markets, policy=HEADLINE_POLICY)
    d = res["diag"]
    cpd = _closes_per_day(res["closes"])
    print("  %s markets simulated over %s closes"
          % (format(int(d["markets"]), ","), format(len(res["closes"]), ",")))
    print("  %s market-second pairs, %s with a touch on the side quoted "
          "(%.1f%%)"
          % (format(int(d["sec_pairs"]), ","), format(int(d["sec_touch"]), ","),
             100.0 * d["sec_touch"] / max(1.0, d["sec_pairs"])))
    print("  the touch price HELD from one second to the next %.1f%% of the "
          "time" % (100.0 * d["sec_held"] / max(1.0, d["sec_pairs"])))
    print("  a trade printed at our exact resting price in %s of those "
          "seconds (%.2f%%)"
          % (format(int(d["sec_traded"]), ","),
             100.0 * d["sec_traded"] / max(1.0, d["sec_pairs"])))
    print("  contracts printed at our price over the whole tape: %s"
          % format(int(d["vol_at_price"]), ","))
    print("  seconds skipped for a hole in the grid: %s"
          % format(int(d["sec_gap"]), ","))
    print("  seconds NOT quoted because the touch sat in the 0.1c tick zone "
          "(below %dc or above %dc): %s (%.1f%% of pairs)"
          % (ZONE[0], ZONE[1], format(int(d["sec_outside_zone"]), ","),
             100.0 * d["sec_outside_zone"] / max(1.0, d["sec_pairs"])))

    qa = quantiles(res["ahead_at_trade"], (0.10, 0.25, 0.50, 0.75, 0.90))
    qt = quantiles(res["touch_sizes"], (0.10, 0.25, 0.50, 0.75, 0.90))
    print("\n  QUEUE AHEAD OF US when a trade arrives at our price "
          "(%s draws)" % format(len(res["ahead_at_trade"]), ","))
    print("    contracts  p10 %.0f   p25 %.0f   MEDIAN %.0f   p75 %.0f   "
          "p90 %.0f" % tuple(qa))
    print("  SIZE RESTING AT THE TOUCH when we post (%s draws, subsampled)"
          % format(len(res["touch_sizes"]), ","))
    print("    contracts  p10 %.0f   p25 %.0f   MEDIAN %.0f   p75 %.0f   "
          "p90 %.0f" % tuple(qt))
    qs = quantiles(res["trade_size_at_price"], (0.10, 0.50, 0.90, 0.99))
    qf = quantiles(res["fill_trade_size"], (0.10, 0.50, 0.90, 0.99))
    print("  TRADE SIZE at our price, all prints  p10 %.0f  median %.0f  "
          "p90 %.0f  p99 %.0f" % tuple(qs))
    print("  TRADE SIZE of the prints that FILL us (S=%d)  p10 %.0f  "
          "median %.0f  p90 %.0f  p99 %.0f" % ((HEAD_SIZE,) + tuple(qf)))
    print("  If the second line is much larger than the first, our fills are")
    print("  selected toward BIG takers and +0.48c per fill is the wrong")
    print("  price for them. The realised per-contract column below settles")
    print("  it against the actual outcomes rather than by argument.")

    nets = [abs(x) for x in res["net_per_market"]]
    qn = quantiles(nets, (0.50, 0.90, 0.99))
    print()
    print("  INVENTORY, which the fill count alone hides. At S=%d the net"
          % HEAD_SIZE)
    print("  position left on the book at settlement, per market, is")
    print("    |net| contracts  median %.0f  p90 %.0f  p99 %.0f  max %.0f"
          % (qn[0] or 0, qn[1] or 0, qn[2] or 0, max(nets) if nets else 0))
    ncl = sorted(res["notional_per_close"].values())
    if ncl:
        print("  cash turned over per close (sum of price x size, S=%d):"
              % HEAD_SIZE)
        print("    $ median %s  p90 %s  max %s"
              % (format(int(ncl[len(ncl) // 2]), ","),
                 format(int(ncl[int(0.9 * len(ncl))]), ","),
                 format(int(ncl[-1]), ",")))
    rows = _report(res, cpd, SIZES, "policy=%s, at the touch"
                   % HEADLINE_POLICY, boot_reps=reps)
    _concentration(rows, cpd)
    for r in rows:
        v = sorted([res["fills"][r["S"]].get(c, 0.0)
                    for c in res["closes"]], reverse=True)
        tot = sum(v)
        if tot <= 0:
            continue
        print("    S=%-4d top 5 %.0f%%   top 10 %.0f%%   top 25 %.0f%%"
              % (r["S"], 100.0 * sum(v[:5]) / tot, 100.0 * sum(v[:10]) / tot,
                 100.0 * sum(v[:25]) / tot))

    # ---- the same measurement with the deci-cent zone put back --------
    print()
    print("=" * 78)
    print("THE SAME RUN WITH THE 0.1c TICK ZONE PUT BACK IN")
    print("=" * 78)
    print("  Reported because leaving it out is a choice, not a fact. In this")
    print("  zone the cached book rounds the price to a whole cent, so these")
    print("  fills include prints up to 0.5c away from the true touch and the")
    print("  fill count is an OVERSTATEMENT of unknown size.")
    res_all = run(book, trades, markets, policy=HEADLINE_POLICY, zone=None,
                  collect=False)
    cpd_all = _closes_per_day(res_all["closes"])
    for S in SIZES:
        mpc = [res_all["money"][S].get(c, 0.0) for c in sorted(res_all["closes"])]
        fpc = sum(res_all["fills"][S].values())
        base_f = sum(res["fills"][S].values())
        print("    S=%-4d contracts %14s (exact grid %14s)   $/day %+9.0f"
              % (S, format(int(fpc), ","), format(int(base_f), ","),
                 mean(mpc) * cpd_all if mpc else 0.0))
    del res_all

    # ---- the off-touch placebo, on real data --------------------------
    print("\n" + "=" * 78)
    print("PLACEBO ON REAL DATA -- a quote that is never at the touch")
    print("=" * 78)
    for off in (1, 2, 5):
        rp = run(book, trades, markets, policy=HEADLINE_POLICY, offset=off,
                 collect=False)
        base = sum(res["fills"][HEAD_SIZE].values())
        got = sum(rp["fills"][HEAD_SIZE].values())
        print("  quoting %dc inside the touch, S=%d: %s contracts "
              "against %s at the touch  (%.2f%%)"
              % (off, HEAD_SIZE, format(int(got), ","), format(int(base), ","),
                 100.0 * got / max(1.0, base)))
        del rp

    # ---- the cancel-policy bounds -------------------------------------
    if not a.quick:
        print("\n" + "=" * 78)
        print("THE CANCEL ASSUMPTION, BOUNDED BOTH WAYS")
        print("=" * 78)
        print("  The tape shows a level shrinking; it never says whether the")
        print("  cancelled orders were in front of us or behind. `behind` is")
        print("  the pessimistic bound, `front` the optimistic one, and the")
        print("  headline `prorata` sits between them by construction.")
        print("  %-8s %14s %14s %14s"
              % ("policy", "S=10 $/day", "S=50 $/day", "S=100 $/day"))
        for pol in POLICIES:
            if pol == HEADLINE_POLICY:
                rr = res
            else:
                rr = run(book, trades, markets, policy=pol, collect=False)
            out = []
            for S in (10, 50, 100):
                mpc = [rr["money"][S].get(c, 0.0) for c in sorted(rr["closes"])]
                out.append(mean(mpc) * cpd if mpc else 0.0)
            print("  %-8s %14.0f %14.0f %14.0f"
                  % (pol, out[0], out[1], out[2]))
            if rr is not res:
                del rr

    # ---- the verdict ---------------------------------------------------
    print("\n" + "=" * 78)
    print("VERDICT AGAINST THE KILL CRITERION: net +$%.0f/day after fees at a"
          % THRESHOLD)
    print("size the depth measurement shows is actually fillable")
    print("=" * 78)
    print("  Makers pay no fee, so gross and net are the same number here.")
    for r in rows:
        b = r["boot"]
        print("  S=%-4d  %s   realised $%.0f/day, 95%% [%+.0f, %+.0f]"
              % (r["S"], verdict(b), b["day"], b["day_lo"], b["day_hi"]))
    print("\n  Fillable size: the median queue ahead of us when a trade")
    print("  arrives is %.0f contracts and the median trade at our price is"
          % (qa[2] if qa[2] is not None else 0.0))
    print("  %.0f contracts, so anything beyond that is resting behind a"
          % (qs[1] if qs[1] is not None else 0.0))
    print("  queue this tape says is rarely cleared.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
