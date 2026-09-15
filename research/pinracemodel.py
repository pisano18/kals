#!/usr/bin/env python3
"""pinracemodel.py -- the Coin Race forecast, VALIDATED against Kalshi's own
settled results before anything is allowed to trade on it.

THE OPERATOR, 2026-09-15: "you can absolutely start on a coin race paper arm.
Just make sure it's completely accurate."

So this file is the accuracy half, in three stages, each of which must pass
before the next means anything:

  1. SETTLEMENT   -- recompute the winner of every settled race from the index
                     tape alone and check it against Kalshi's own `result`.
                     If this is not ~100% nothing below matters.
  2. THE TABLE    -- for every coin at every tau, how often did a coin with
                     this GAP to the field actually win?
  3. CALIBRATION  -- when it says 95%, is it right 95% of the time?

THE SETTLEMENT RULE, from RESULTS_coinrace (773/773): the winner is the coin
with the highest

    (mean of the 60 one-second prints over [close-60, close-1])
  / (mean of the 60 one-second prints over [open-60,  open-1])

The denominator is fixed the moment the window opens. Only the numerator is
unresolved, and it is the same quantity `pin` already forecasts -- with r
prints still to come, the running mean is (locked_sum + r*spot)/60.

WHY PER COIN AND NOT PER LEADER. There are five legs in a race and FOUR OF
THEM LOSE. A "who leads" model prices one contract; the interesting surface is
the other four, where the question is "can this coin still win" and the answer
is usually a much flatter no than the leader's yes. So every coin gets a
signed GAP -- its return minus the best OTHER coin's return. The leader's gap
is positive, everyone else's is negative, and P(win | gap, tau) is one curve
covering both sides of every leg.

WHY AN EMPIRICAL TABLE AND NOT A FORMULA. Two coins' remaining prints are
correlated, so the GAP between them moves far less than either coin does.
Modelling that would need a covariance this project has never measured well.
The table measures the quantity we actually need -- how often a gap this size
at this tau was closed -- with no distributional assumption at all.

AND EVERY CELL IS READ AS ITS 95% UPPER BOUND, never its point estimate. Most
cells are 0 wins out of 120 races. That is not zero risk; it is "at most about
2.5%". A runner told 0% would price a leg at a dollar and size as though it
could not lose.

INDEX ONLY. No order book, no fills, no P&L.

    python research/pinracemodel.py --selftest
    python research/pinracemodel.py            # validate + build the table
"""
import bisect
import collections
import datetime as dt
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import idxload                                                 # noqa: E402

COINS = {"BTC": "BRTI", "ETH": "ETHUSD_RTI", "SOL": "SOLUSD_RTI",
         "XRP": "XRPUSD_RTI", "HYPE": "HYPEUSD_RTI"}
N_AVG = 60
WINDOW = 900
TRUTH = os.path.join(REPO, "results", "race_truth.json")
TABLE = os.path.join(REPO, "results", "race_gaptable.json")

# GAP buckets, in basis points of return (1bp = 0.0001 = 0.01%). Signed:
# positive is leading the field by that much, negative is trailing it.
# RESULTS_coinrace measured the winning margin at p05 0.5bp, median 6.5bp,
# p75 13bp -- races are tight -- so the buckets are fine near zero.
EDGES_BP = [-60.0, -30.0, -15.0, -8.0, -4.0, -2.0, -1.0, -0.5, 0.0,
            0.5, 1.0, 2.0, 4.0, 8.0, 15.0, 30.0, 60.0]
TAUS = [3, 5, 8, 12, 17, 25, 35, 50, 60, 90, 150]
MIN_CELL = 20            # races below which a cell is refused, not read


def twap(d, a, b, min_frac=0.95):
    """Mean of the prints in [a, b]; None if more than 5% are missing.

    A window that is mostly missing must not be guessed at, and a dropped
    second must not shrink the mean -- so this averages what exists and
    refuses when too little does."""
    got = [v for v in (d.get(s) for s in range(a, b + 1)) if v is not None]
    want = b - a + 1
    if not got or len(got) < want * min_frac:
        return None
    return sum(got) / len(got)


def returns_at(idx, close, tau):
    """{coin: projected return} at `tau` seconds out.

    locked_sum is the prints already inside the settlement window; the r still
    to come are imputed at the newest print, which is exactly what pin does."""
    out = {}
    for name, iid in COINS.items():
        d = idx.get(iid)
        if d is None:
            continue
        den = twap(d, close - WINDOW - N_AVG, close - WINDOW - 1)
        if not den:
            continue
        lo = close - N_AVG
        hi = min(close - tau, close - 1)
        if hi < lo:
            # the settlement window has not opened yet: nothing is locked
            locked, r, spot = 0.0, N_AVG, None
            for s in range(close - tau - 5, close - tau + 1):
                v = d.get(s)
                if v is not None:
                    spot = v
            if spot is None:
                continue
        else:
            got = [v for v in (d.get(s) for s in range(lo, hi + 1)) if v is not None]
            want = hi - lo + 1
            if not got or len(got) < want * 0.95:
                continue
            locked = sum(got) * (want / len(got))
            r = N_AVG - want
            spot = got[-1]
        out[name] = ((locked + r * spot) / N_AVG) / den
    return out


def gaps(rets):
    """{coin: signed gap to the FIELD}, in return units.

    A coin's gap is its return minus the best OTHER coin's return -- so the
    leader's is positive (its margin over second place) and everyone else's is
    negative (how far behind the leader they are). One number, both sides."""
    if len(rets) < 2:
        return {}
    order = sorted(rets.items(), key=lambda kv: -kv[1])
    best, second = order[0][1], order[1][1]
    out = {}
    for i, (c, v) in enumerate(order):
        out[c] = (v - second) if i == 0 else (v - best)
    return out


def bucket(gap_bp):
    """Index of the gap bucket. Bucket 0 is everything below the first edge,
    the last is everything above the last edge."""
    return bisect.bisect_right(EDGES_BP, gap_bp)


def bucket_label(i):
    if i == 0:
        return "<%g" % EDGES_BP[0]
    if i >= len(EDGES_BP):
        return "%+g<" % EDGES_BP[-1]
    return "%+g" % EDGES_BP[i - 1]


def nearest_tau(tau):
    return min(TAUS, key=lambda t: abs(t - tau))


def upper95(k, n):
    """The 95% UPPER bound on a rate of k out of n, not the point estimate.

    THIS IS THE MOST IMPORTANT FUNCTION IN THE FILE. Most cells of the table
    read 0 wins out of 120 races, and a runner that believes "0%" will price a
    leg at a dollar and size as though it cannot lose. 0 out of 120 is not zero
    risk; it is "at most about 2.5%, we have not seen enough races to say
    better." The rule of three gives 3/n for a zero cell, Wilson's upper bound
    handles the rest.

    So every probability this file reports is PESSIMISTIC by construction, and
    it gets less pessimistic only as races accumulate."""
    if n <= 0:
        return 1.0
    if k <= 0:
        return min(1.0, 3.0 / n)
    z = 1.96
    ph = k / float(n)
    den = 1.0 + z * z / n
    cen = ph + z * z / (2 * n)
    rad = z * math.sqrt(ph * (1 - ph) / n + z * z / (4.0 * n * n))
    return min(1.0, (cen + rad) / den)


def _read(table, tau, gap_bp, field):
    """Walk to a populated cell and return (k, n) for `field`.

    A thin cell falls back TOWARD ZERO GAP -- toward a coin closer to the lead,
    which wins more often and is overtaken more often. Both directions of that
    fallback are pessimistic for the bet being priced, which is the point.
    With nothing populated at all it returns None."""
    t = nearest_tau(tau)
    b = bucket(gap_bp)
    zero = bucket(0.0)
    step = 1 if b < zero else -1
    bb = b
    while 0 <= bb <= len(EDGES_BP):
        c = (table.get(str(t)) or {}).get(str(bb))
        if c and c["n"] >= MIN_CELL:
            n = float(c["n"])
            return ((c["won"] if field == "won" else n - c["won"]), n)
        if bb == zero:
            break
        bb += step
    return None


def p_win(table, tau, gap_bp, point=False):
    """P(this coin wins the race) given its gap and the seconds left.

    Returns the 95% UPPER bound by default; `point=True` gives the raw measured
    rate and is for printing the table, never for sizing.

    This is the number for buying a trailer's NO: an upper bound on its win
    chance is a lower bound on ours, which is conservative directly. For a
    leader's YES use p_lose, which bounds the tail that can actually hurt."""
    kn = _read(table, tau, gap_bp, "won")
    if kn is None:
        return 0.5
    k, n = kn
    return (k / n) if point else upper95(k, n)


def p_lose(table, tau, gap_bp, point=False):
    """P(this coin does NOT win) -- bounded from the side that can hurt a YES.

    For a leader we need the chance it gets overtaken, and that chance must be
    bounded ABOVE. So this counts the losses directly and bounds those, rather
    than taking 1 - p_win, which would bound the comfortable tail and leave the
    dangerous one open."""
    kn = _read(table, tau, gap_bp, "lost")
    if kn is None:
        return 0.5
    k, n = kn
    return (k / n) if point else upper95(k, n)


def close_of(stamp):
    """26SEP150000 -> epoch seconds. The stamp block is EASTERN, the same
    convention every Kalshi crypto ticker uses; reading it as UTC puts every
    race four hours from its own close and scores the wrong second."""
    try:
        day = dt.datetime.strptime(stamp[:7], "%y%b%d")
        hh, mi = int(stamp[7:9]), int(stamp[9:11])
        return int((day.replace(hour=hh, minute=mi)
                    - dt.datetime(1970, 1, 1)).total_seconds()) + 4 * 3600
    except (ValueError, IndexError):
        return None


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    base = 7_000_000 - (7_000_000 % WINDOW)
    close = base + 2 * WINDOW

    def mk(iid, open_lvl, close_lvl):
        D = idxload.Dense(iid, close - WINDOW - 200, WINDOW + 400)
        for s in range(close - WINDOW - 200, close + 100):
            D.v[s - D.base] = open_lvl if s < close - N_AVG else close_lvl
        return D

    idx = {"BRTI": mk("BRTI", 100.0, 102.0),        # +2%
           "ETHUSD_RTI": mk("ETH", 50.0, 50.5)}     # +1%
    r = returns_at(idx, close, 1)
    ck(abs(r["BTC"] - 1.02) < 1e-9 and abs(r["ETH"] - 1.01) < 1e-9,
       "returns are close TWAP over open TWAP: BTC +2%%, ETH +1%%")
    g = gaps(r)
    ck(abs(g["BTC"] - 0.01) < 1e-9 and abs(g["ETH"] + 0.01) < 1e-9,
       "BTC's gap is +1%% and ETH's is -1%% -- and LEVEL is irrelevant, a $50 "
       "coin and a $100 coin are compared on return alone")
    idx2 = {"BRTI": mk("BRTI", 100.0, 102.0 * 1.05),
            "ETHUSD_RTI": mk("ETH", 50.0, 50.5 * 1.05)}
    g2 = gaps(returns_at(idx2, close, 1))
    ck(g2["BTC"] > 0 and abs(g2["BTC"] - 0.01 * 1.05) < 1e-6,
       "a 5%% move in BOTH coins leaves the same coin ahead -- the whole "
       "reason the race diversifies against the pin")
    # three coins: the gap is to the FIELD, not to the bottom
    g3 = gaps({"A": 1.05, "B": 1.04, "C": 1.00})
    ck(abs(g3["A"] - 0.01) < 1e-9 and abs(g3["B"] + 0.01) < 1e-9
       and abs(g3["C"] + 0.05) < 1e-9,
       "with three coins the leader's gap is over SECOND (+1%%), and each "
       "trailer's is to the LEADER (-1%%, -5%%) -- not to each other")
    ck(sum(1 for v in g3.values() if v > 0) == 1,
       "exactly one coin has a positive gap, because exactly one can win")
    ck(gaps({"A": 1.0}) == {} and gaps({}) == {},
       "NULL: one coin is not a race and yields no gaps at all")

    # ---- buckets -------------------------------------------------------
    ck(bucket(-999.0) == 0 and bucket(999.0) == len(EDGES_BP),
       "a runaway lead and a hopeless trail land in the end buckets")
    ck(bucket(-0.2) < bucket(0.2),
       "a coin 0.2bp behind buckets strictly below one 0.2bp ahead")
    ck(all(bucket(EDGES_BP[i]) <= bucket(EDGES_BP[i + 1])
           for i in range(len(EDGES_BP) - 1)), "and buckets are monotone")
    ck(nearest_tau(4) == 3 and nearest_tau(30) in (25, 35),
       "an arbitrary tau snaps to the nearest measured one")

    # ---- the zero cell, which is most of this table --------------------
    ck(0.02 < upper95(0, 120) < 0.03,
       "0 wins out of 120 races reads as %.1f%%, NOT zero -- the rule of "
       "three. A runner told 0%% prices the leg at a dollar and sizes as "
       "though it cannot lose" % (100 * upper95(0, 120)))
    ck(upper95(0, 1200) < upper95(0, 120),
       "ten times the races cuts the bound from %.2f%% to %.2f%% -- the "
       "pessimism relaxes only as evidence arrives"
       % (100 * upper95(0, 120), 100 * upper95(0, 1200)))
    ck(0.07 < upper95(7, 100) < 0.15,
       "a non-zero cell of 7-in-100 reads as %.1f%%, not 7.0%%"
       % (100 * upper95(7, 100)))
    ck(upper95(0, 0) == 1.0 and upper95(50, 50) == 1.0,
       "no races at all is 100%% risk, and 50 of 50 is 100%%")
    ck(all(upper95(k, n) >= k / float(n)
           for n in (25, 60, 400) for k in range(0, n, 7)),
       "and the bound is never BELOW the measured rate, anywhere")

    # ---- reading the table ---------------------------------------------
    ck(p_win({}, 10, 30.0) == 0.5 and p_lose({}, 10, 30.0) == 0.5,
       "NULL: an empty table returns 0.5 both ways, never 0 -- a cell with no "
       "data must not license a bet")
    thin = {"12": {str(bucket(30.0)): {"n": 3, "won": 3}}}
    ck(p_win(thin, 12, 30.0) == 0.5,
       "and a cell with 3 races is ignored rather than read as certainty")
    zero = {"12": {str(bucket(-30.0)): {"n": 120, "won": 0}}}
    ck(p_win(zero, 12, -30.0) == upper95(0, 120)
       and p_win(zero, 12, -30.0, point=True) == 0.0,
       "a coin 30bp behind that won 0 of 120 reads as %.1f%% by default, and "
       "only point=True shows the raw zero, which is for the printed table"
       % (100 * upper95(0, 120)))
    full = {"12": {str(bucket(30.0)): {"n": 120, "won": 120}}}
    ck(p_lose(full, 12, 30.0) == upper95(0, 120) and p_win(full, 12, 30.0) > 0.99,
       "and a leader that won 120 of 120 is NOT certain -- its loss chance "
       "reads %.1f%%, bounded from the side that can hurt a YES"
       % (100 * p_lose(full, 12, 30.0)))
    ck(p_lose(full, 12, 30.0) > 1.0 - p_win(full, 12, 30.0),
       "p_lose is deliberately NOT 1 - p_win: taking one from the other would "
       "bound the comfortable tail and leave the dangerous one unbounded")

    # ---- the fallback direction, which is easy to get backwards --------
    fb = {"12": {str(bucket(-4.0)): {"n": 200, "won": 20},
                 str(bucket(-8.0)): {"n": 200, "won": 4},
                 str(bucket(-30.0)): {"n": 3, "won": 0}}}
    ck(abs(p_win(fb, 12, -30.0, point=True) - 0.02) < 1e-9,
       "a thin far-behind cell falls back TOWARD zero gap, to a coin closer "
       "to the lead, which wins MORE often (2.0%%) -- so the fallback is "
       "pessimistic. Falling the other way would have read 0%% off 3 races")
    fb2 = {"12": {str(bucket(4.0)): {"n": 200, "won": 180},
                  str(bucket(30.0)): {"n": 3, "won": 3}}}
    ck(abs(p_lose(fb2, 12, 30.0, point=True) - 0.10) < 1e-9,
       "and a thin runaway-lead cell falls back to a NARROWER lead, which is "
       "overtaken more often (10.0%%), never to the 3-race certainty")

    ck(twap({}, 0, 10) is None and twap({0: 1.0}, 0, 59) is None,
       "NULL: a missing or mostly-empty window is refused, never averaged")
    got = dt.datetime.utcfromtimestamp(close_of("26SEP150000")).strftime("%Y-%m-%d %H:%MZ")
    ck(got == "2026-09-15 04:00Z",
       "and 26SEP15 00:00 is the EASTERN midnight close = %s" % got)
    ck(close_of("rubbish") is None, "rubbish is refused, not guessed at")
    print("pinracemodel selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0
    if not os.path.exists(TRUTH):
        print("loaded nothing -- %s missing" % TRUTH)
        return 0
    truth = json.load(open(TRUTH, encoding="utf-8"))
    idx = idxload.load(sorted(COINS.values()), verbose=False)
    D = idx.get("BRTI")
    if D is None:
        print("loaded nothing -- no index on disk")
        return 0

    races = []
    for stamp, legs in truth.items():
        c = close_of(stamp)
        if c is None or c < D.base or c > D.base + D.n:
            continue
        winners = [k for k, v in legs.items() if v == "yes"]
        if len(winners) != 1:
            continue
        races.append((stamp, c, winners[0]))
    if not races:
        print("loaded nothing -- no overlap between settled races and the tape")
        return 0

    # ---- 1. SETTLEMENT -------------------------------------------------
    agree = tested = 0
    misses = []
    for stamp, c, won in races:
        r = returns_at(idx, c, 1)
        if len(r) < 5:
            continue
        tested += 1
        got = max(r.items(), key=lambda kv: kv[1])[0]
        if got == won:
            agree += 1
        elif len(misses) < 6:
            misses.append((stamp, won, got, r))
    print("\n1. SETTLEMENT -- our reconstruction vs Kalshi's own result")
    print("   %d of %d races reproduced = %.2f%%"
          % (agree, tested, 100.0 * agree / max(1, tested)))
    for st, want, got, r in misses:
        print("     %s Kalshi says %-4s we say %-4s  %s"
              % (st, want, got, {k: round(v, 6) for k, v in sorted(r.items())}))
    if not tested or agree / tested < 0.98:
        print("\n   *** BELOW 98%. Nothing below is trustworthy and nothing")
        print("   should trade on it until this is understood. ***")
        return 1

    # ---- 2. THE TABLE --------------------------------------------------
    table = collections.defaultdict(lambda: collections.defaultdict(
        lambda: {"n": 0, "won": 0}))
    for stamp, c, won in races:
        for t in TAUS:
            g = gaps(returns_at(idx, c, t))
            if len(g) < 5:
                continue
            for coin, gap in g.items():
                cell = table[str(t)][str(bucket(gap * 1e4))]
                cell["n"] += 1
                if coin == won:
                    cell["won"] += 1
    out = {t: {b: dict(v) for b, v in bs.items()} for t, bs in table.items()}
    json.dump(out, open(TABLE, "w"), indent=0)
    print("\n2. P(THIS COIN WINS), by how far ahead or behind it is and how")
    print("   many seconds are left. %d races x 5 legs. -> %s\n"
          % (len(races), os.path.basename(TABLE)))
    cols = [b for b in range(len(EDGES_BP) + 1)
            if any((out.get(str(t), {}).get(str(b)) or {}).get("n", 0) >= MIN_CELL
                   for t in TAUS)]
    print("   gap to the field, in basis points of return (1bp = 0.01%)")
    print("   %4s" % "tau" + "".join("%10s" % bucket_label(b) for b in cols))
    for t in TAUS:
        row = "   %4d" % t
        for b in cols:
            c = out.get(str(t), {}).get(str(b))
            if c and c["n"] >= MIN_CELL:
                row += "%9.1f%%" % (100.0 * c["won"] / c["n"])
            else:
                row += "%10s" % "-"
        print(row)
    print("\n   Read a column as 'this coin is N basis points ahead of (+) or")
    print("   behind (-) the best other coin'. A '-' cell has under %d races"
          % MIN_CELL)
    print("   and is refused; the lookup falls back TOWARD zero gap, which")
    print("   wins more often, so the fallback never flatters a bet.")
    print("\n   THOSE ARE RAW RATES. What a runner would use is the 95% bound")
    print("   on each -- a 0.0%% cell of 120 races reads as %.1f%%, because"
          % (100 * upper95(0, 120)))
    print("   that is what 0-of-120 honestly supports:\n")
    print("   %5s %10s %10s %10s" % ("tau", "gap", "P(win)", "P(lose)"))
    for t in (5, 12, 25, 60):
        for gbp in (-15.0, -4.0, 4.0, 15.0):
            print("   %5d %8.1fbp %9.2f%% %9.2f%%"
                  % (t, gbp, 100 * p_win(out, t, gbp), 100 * p_lose(out, t, gbp)))

    # ---- 3. CALIBRATION ------------------------------------------------
    print("\n3. CALIBRATION -- when it claims this, how often is it right?")
    print("   Scored on the NO side, because four legs in five are a NO and")
    print("   that is where the contracts are.")
    print("   %10s %8s %10s %10s" % ("claimed", "legs", "actual", "gap"))
    buckets = [(0.99, 1.01), (0.97, 0.99), (0.95, 0.97), (0.90, 0.95),
               (0.80, 0.90), (0.60, 0.80), (0.0, 0.60)]
    agg = collections.defaultdict(lambda: [0, 0])
    for stamp, c, won in races:
        for t in (5, 8, 12, 17, 25):
            g = gaps(returns_at(idx, c, t))
            if len(g) < 5:
                continue
            for coin, gap in g.items():
                if gap > 0:
                    continue          # the leader is the YES side, scored apart
                claim = 1.0 - p_win(out, t, gap * 1e4)
                for lo, hi in buckets:
                    if lo <= claim < hi:
                        agg[(lo, hi)][0] += 1
                        if coin != won:
                            agg[(lo, hi)][1] += 1
                        break
    for lo, hi in buckets:
        n, w = agg[(lo, hi)]
        if n < 10:
            continue
        mid = (lo + min(hi, 1.0)) / 2
        print("   %9.1f%% %8d %9.2f%% %9.1fpp"
              % (100 * mid, n, 100.0 * w / n, 100.0 * (w / n - mid)))
    print("\n   A POSITIVE gap column means it beats its own claim, which is")
    print("   the safe direction and is what the 95% bounds are for.")
    print("   THE TABLE IS FITTED ON THESE SAME RACES, so this is in-sample")
    print("   and flatters itself. It is a sanity check, not evidence. The")
    print("   paper arm is what tests it forward.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
