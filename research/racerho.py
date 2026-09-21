#!/usr/bin/env python3
"""racerho.py -- the correlation the Coin Race book is implying, against the
correlation that actually turns up.

`IDEAS.md` B1 has called this "HIGHEST UNEXPLORED VALUE" since the beginning
of the project and it was blocked on data: the collector did not subscribe to
the series. It has now recorded 26 days of it. This is that test.

THE MECHANISM, and why it needs no view on which coin wins.

A race is decided by the GAP between five coins, not by any coin's move. So
the leg prices are a function of how tightly the coins move TOGETHER:

    rho -> 1   every coin moves as one, the gap barely moves, whoever leads
               now almost certainly wins, and the leader is worth nearly 100c
    rho -> 0   the coins wander independently, the gap moves freely, a small
               lead is fragile, and the leader is worth much less

The lead itself we can see, and each coin's own volatility we can measure.
That leaves ONE unknown between the observable state and the quoted price:
the correlation. Invert the price for it. That number is the market's opinion
about correlation, and correlation is materially harder to price than
volatility -- it is where relative-performance products are most often wrong
in every market where anybody has looked.

WHAT WE ARE ALREADY DOING WITHOUT NAMING IT. `pinracefair` prices each leg
from the TRAILING REALISED covariance. So every time it says a leg is
mispriced, it is implicitly saying the book's implied correlation is wrong.
This file makes that explicit, which buys three things a raw edge number
cannot: whether the book's error is a persistent BIAS (tradeable, stable) or
race-by-race noise; which direction it runs; and a check on our own model,
because an implied correlation outside [-0.25, 1] is the book telling us our
volatilities are wrong rather than its correlation.

THE INVERSION. Equicorrelation -- one rho, each coin its own sigma:

    C_ii = sigma_i^2 ,   C_ij = rho * sigma_i * sigma_j

P(leader wins) is strictly increasing in rho, so a bisection is exact and
needs no optimiser. The market's probabilities come from the five mid prices
NORMALISED to sum to one: the five asks sum to a median $1.16 and the five
bids to $1.00, so the raw quotes carry the spread and must be de-vigged
before anything is inverted from them.

SCORING USES THE FUTURE ON PURPOSE, AND ONLY FOR SCORING. The comparison is
implied rho at tau against the correlation that then ACTUALLY happened over
the remaining tau seconds. That is forward-looking by construction and is
never fed to a decision -- decisions read only prints at or before close-tau.

    python research/racerho.py --selftest
    python research/racerho.py --hours 600
"""
import argparse
import collections
import datetime as dt
import glob
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")

import racebook                                                # noqa: E402

COINS = racebook.COINS
TAUS = (10, 20, 30, 45, 60, 90, 120, 180, 300)
RHO_LO, RHO_HI = -0.24, 0.999           # -1/(n-1) is the floor for n=5
MAXAGE = 30


# --------------------------------------------------------------- the maths
def equicorr(sigmas, rho):
    """5x5 covariance with one shared correlation and per-coin volatilities."""
    n = len(sigmas)
    return [[(sigmas[i] * sigmas[j] * (1.0 if i == j else rho))
             for j in range(n)] for i in range(n)]


def p_leader(F, rnow, sigmas, rho, k, lead_i):
    """P(coin `lead_i` wins) under one shared correlation."""
    pr = F.win_probs(rnow, equicorr(sigmas, rho), k)[1.0]
    return pr[lead_i]


def implied_rho(F, rnow, sigmas, k, lead_i, target, tol=2e-3, iters=40):
    """The single correlation at which the model reproduces `target`, the
    market's (de-vigged) probability for coin `lead_i`.

    P(leader) rises monotonically with rho -- when the coins move as one, a
    lead cannot be overturned -- so bisection is exact. Returns None when the
    target lies outside what ANY correlation can produce, which is itself a
    result: the book is then disagreeing with our volatilities, not with our
    correlation."""
    lo, hi = RHO_LO, RHO_HI
    p_lo = p_leader(F, rnow, sigmas, lo, k, lead_i)
    p_hi = p_leader(F, rnow, sigmas, hi, k, lead_i)
    if target < p_lo - tol or target > p_hi + tol:
        return None
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if p_leader(F, rnow, sigmas, mid, k, lead_i) < target:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-4:
            break
    return 0.5 * (lo + hi)


def avg_pairwise_rho(cov):
    """Mean off-diagonal correlation of a covariance matrix, or None."""
    n = len(cov)
    sd = [math.sqrt(cov[i][i]) if cov[i][i] > 0 else 0.0 for i in range(n)]
    vals = []
    for i in range(n):
        for j in range(i + 1, n):
            if sd[i] <= 0 or sd[j] <= 0:
                continue
            vals.append(max(-1.0, min(1.0, cov[i][j] / (sd[i] * sd[j]))))
    return (sum(vals) / len(vals)) if vals else None


def devig(mids):
    """Five quotes -> probabilities summing to one.

    The five asks sum to a median $1.16 and the five bids to $1.00, so a raw
    quote is not a probability. Returns None if nothing usable is quoted."""
    tot = sum(mids)
    if tot <= 0:
        return None
    return [m / tot for m in mids]


def mid_of(q):
    """Mid price of one leg's top of book, or None when one side is missing.

    A missing side is NOT zero: an empty yes-ask prints 1.0000 with size 0,
    and reading that as a dollar offer would manufacture a probability out of
    a market with no sellers."""
    if q is None:
        return None
    bid, ask, bsz, asz = q
    has_b = bsz > 0 and 0.0 < bid < 1.0
    has_a = asz > 0 and 0.0 < ask < 1.0
    if has_b and has_a:
        return 0.5 * (bid + ask)
    if has_a:
        return ask
    if has_b:
        return bid
    return None


# -------------------------------------------------------------- self-test
def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    import pinracefair as F

    s = [1e-4] * 5
    c = equicorr(s, 0.5)
    ck(all(abs(c[i][i] - 1e-8) < 1e-20 for i in range(5)),
       "equicorr puts sigma^2 on the diagonal")
    ck(abs(c[0][1] - 0.5e-8) < 1e-20 and c[0][1] == c[1][0],
       "and rho*sigma_i*sigma_j off it, symmetrically")
    ck(abs(avg_pairwise_rho(c) - 0.5) < 1e-9,
       "and reading the correlation back out returns 0.5")
    ck(avg_pairwise_rho([[0.0] * 5 for _ in range(5)]) is None,
       "a degenerate matrix returns None rather than a fake correlation")

    # MONOTONICITY -- the whole bisection rests on it
    rnow = [3e-4, 0.0, -1e-4, -2e-4, -3e-4]          # coin 0 leads
    ps = [p_leader(F, rnow, s, r, 400.0, 0) for r in (0.0, 0.3, 0.6, 0.9)]
    ck(all(ps[i] < ps[i + 1] for i in range(3)),
       "P(leader) RISES with correlation: %s -- coins that move as one cannot "
       "overturn a lead" % [round(p, 3) for p in ps])

    # RECOVERY -- plant a rho, price with it, invert, get it back
    for planted in (0.2, 0.55, 0.85):
        tgt = p_leader(F, rnow, s, planted, 400.0, 0)
        got = implied_rho(F, rnow, s, 400.0, 0, tgt)
        ck(got is not None and abs(got - planted) < 0.06,
           "PLANTED rho %.2f prices the leader at %.3f and inverts back to "
           "%.3f" % (planted, tgt, got if got is not None else float("nan")))

    # OUT OF RANGE -- a target no correlation can produce must be refused
    ck(implied_rho(F, rnow, s, 400.0, 0, 0.999999) is None,
       "a leader probability above what rho=1 gives is REFUSED, not clamped -- "
       "that is the book disagreeing with our volatilities, not our correlation")
    ck(implied_rho(F, rnow, s, 400.0, 0, 0.0001) is None,
       "and so is one below what the lowest correlation gives")

    # NULL -- level pegging carries no correlation information either way
    flat = [0.0] * 5
    a = p_leader(F, flat, s, 0.1, 400.0, 0)
    b = p_leader(F, flat, s, 0.9, 400.0, 0)
    ck(abs(a - 0.2) < 0.03 and abs(b - 0.2) < 0.03,
       "NULL: five coins level on points are each 1-in-5 at ANY correlation "
       "(%.3f vs %.3f) -- with no lead there is nothing to imply" % (a, b))

    ck(devig([0.9, 0.05, 0.05, 0.05, 0.05]) is not None
       and abs(sum(devig([0.9, 0.05, 0.05, 0.05, 0.05])) - 1.0) < 1e-12,
       "de-vigging five quotes returns probabilities summing to one")
    ck(devig([0.0] * 5) is None, "and nothing quoted returns None")
    ck(abs(devig([0.6, 0.6, 0.0, 0.0, 0.0])[0] - 0.5) < 1e-12,
       "two equal quotes de-vig to a half each")

    ck(abs(mid_of((0.90, 0.94, 10, 10)) - 0.92) < 1e-9,
       "a two-sided leg mids correctly (0.5*(0.90+0.94) is 0.91999... in "
       "binary, so this is compared with a tolerance and never with ==)")
    ck(mid_of((0.0, 1.0, 0, 0)) is None,
       "an empty book (bid 0 size 0, ask 1 size 0) has no mid, not 0.5")
    ck(mid_of((0.0, 0.03, 0, 40)) == 0.03,
       "a one-sided leg uses the side that exists")
    ck(mid_of(None) is None, "and a leg with no quote at all has no mid")

    if not racebook.selftest():
        ck(False, "racebook (the shared reader) self-test")
    print("racerho selftest:", "OK" if ok else "FAILED")
    return ok


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=racebook.DATA)
    ap.add_argument("--hours", type=int, default=600)
    ap.add_argument("--ruler", default="3600")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if not selftest():
        return 1
    if a.selftest:
        return 0

    files = sorted(glob.glob(os.path.join(a.data, "ticker", "*.jsonl.gz")))
    if a.hours:
        files = files[-a.hours:]
    if not files:
        print("loaded nothing -- no ticker files")
        return 0
    cand, got = racebook.parse_rate(files)
    print("\n%d ticker files; parser check %d/%d" % (len(files), got, cand))
    if cand and got < 0.95 * cand:
        print("REFUSING TO REPORT -- ticker wire format moved")
        return 1

    by_race = collections.defaultdict(list)
    for k, fp in enumerate(files):
        for r in racebook.cached_hour(fp):
            by_race[r[1]].append(r)
        if (k + 1) % 150 == 0:
            print("  ... %d/%d files read" % (k + 1, len(files)), flush=True)
    races = []
    for stamp, rows in by_race.items():
        c = racebook.close_of(stamp)
        if c is None or len({r[2] for r in rows}) < len(COINS):
            continue
        races.append((c, stamp, rows))
    races.sort()
    del by_race
    print("  %d races with all five legs quoting" % len(races))

    import idxload
    import pinracefair as F
    import pinracemodel as M
    idx = idxload.load(sorted(set(M.COINS.values())), verbose=False)
    if not idx or idx.get("BRTI") is None:
        print("loaded nothing -- no index on disk")
        return 0

    iids = [M.COINS[c] for c in COINS]
    rows = []          # (close, tau, implied, trail, fwd, lead_coin, mkt_p, won)
    refused = collections.Counter()
    done = 0
    for close, stamp, rrows in races:
        rets0 = M.returns_at(idx, close, 0)
        if len(rets0) < len(COINS):
            continue
        winner = max(rets0, key=rets0.get)
        ser = F.RaceSeries(idx, close)
        st = {t: f for t, f in racebook.scan_race(rrows, close, tau_lo=min(TAUS),
                                                  tau_hi=max(TAUS),
                                                  max_age=MAXAGE)}
        for tau in TAUS:
            fresh = st.get(tau)
            if not fresh or len(fresh) < len(COINS):
                refused["no_book"] += 1
                continue
            mids = [mid_of(fresh.get(c)) for c in COINS]
            if any(m is None for m in mids):
                refused["one_sided"] += 1
                continue
            probs = devig(mids)
            rets = M.returns_at(idx, close, tau)
            if len(rets) < len(COINS):
                refused["no_index"] += 1
                continue
            # the DECISION-SIDE covariance: trailing only, never the future
            cov = F.pick_cov(ser, close - tau, a.ruler)
            if cov is None:
                refused["no_cov"] += 1
                continue
            sig = [math.sqrt(cov[i][i]) if cov[i][i] > 0 else 0.0
                   for i in range(len(COINS))]
            if min(sig) <= 0:
                refused["flat_coin"] += 1
                continue
            rnow = [math.log(rets[c]) for c in COINS]
            lead_i = max(range(len(COINS)), key=lambda i: rnow[i])
            k = F.var_factor(tau)
            imp = implied_rho(F, rnow, sig, k, lead_i, probs[lead_i])
            if imp is None:
                refused["outside_any_rho"] += 1
                continue
            trail = avg_pairwise_rho(cov)
            # SCORING ONLY, and deliberately forward: what the correlation
            # actually turned out to be over the seconds still to come.
            fcov, fcover = ser.cov(close, tau)
            fwd = avg_pairwise_rho(fcov) if fcov is not None and fcover >= 0.8 \
                else None
            rows.append((close, tau, imp, trail, fwd, COINS[lead_i],
                         probs[lead_i], COINS[lead_i] == winner))
        done += 1
        if done % 100 == 0:
            print("  ... %d/%d races" % (done, len(races)), flush=True)

    if len(rows) < 100:
        print("loaded nothing -- only %d usable race-moments (%s)"
              % (len(rows), dict(refused)))
        return 0
    days = (rows[-1][0] - rows[0][0]) / 86400.0
    print("\n%d race-moments across %d races, %.1f days. Refused: %s"
          % (len(rows), len({r[0] for r in rows}), days, dict(refused)))

    def q(v, p):
        v = sorted(v)
        return v[max(0, min(len(v) - 1, int(p * (len(v) - 1) + 0.5)))]

    print("\n## 1. WHAT THE BOOK IMPLIES, AGAINST WHAT HAPPENED")
    print("'trailing' is the correlation our model used to price. 'forward' is")
    print("the correlation that actually turned up over the seconds still to")
    print("come -- the one the contract was really about.")
    print("  %5s %7s %8s %8s %8s %8s %10s %10s"
          % ("tau", "n", "implied", "trailing", "forward", "imp-fwd",
             "imp p05", "imp p95"))
    for tau in TAUS:
        sel = [r for r in rows if r[1] == tau and r[4] is not None]
        if len(sel) < 30:
            continue
        imp = [r[2] for r in sel]
        tr = [r[3] for r in sel if r[3] is not None]
        fw = [r[4] for r in sel]
        gap = [r[2] - r[4] for r in sel]
        print("  %5d %7d %8.3f %8.3f %8.3f %+8.3f %10.3f %10.3f"
              % (tau, len(sel), q(imp, 0.5), q(tr, 0.5) if tr else float("nan"),
                 q(fw, 0.5), sum(gap) / len(gap), q(imp, 0.05), q(imp, 0.95)))

    print("\n## 2. IS THE BOOK'S CORRELATION BIASED, OR JUST NOISY?")
    print("A persistent gap is a stable edge. A gap that averages to nothing")
    print("but swings wildly is race-by-race noise and not worth trading.")
    print("  %5s %7s %10s %10s %10s %9s"
          % ("tau", "n", "mean gap", "sd of gap", "t-stat", "share > 0"))
    for tau in TAUS:
        sel = [r[2] - r[4] for r in rows if r[1] == tau and r[4] is not None]
        if len(sel) < 30:
            continue
        m = sum(sel) / len(sel)
        var = sum((x - m) ** 2 for x in sel) / max(1, len(sel) - 1)
        sd = math.sqrt(var)
        # clustered by close: n is races at this tau, not moments
        nraces = len({r[0] for r in rows if r[1] == tau and r[4] is not None})
        t = m / (sd / math.sqrt(nraces)) if sd > 0 and nraces else float("nan")
        print("  %5d %7d %+10.3f %10.3f %10.2f %8.0f%%"
              % (tau, nraces, m, sd, t, 100.0 * sum(1 for x in sel if x > 0)
                 / len(sel)))
    print("  (t is clustered by close, so n is races, not moments -- twelve")
    print("   crypto markets on one quarter hour are ~1.22 independent bets.)")

    print("\n## 3. DOES THE GAP PREDICT THE LEADER'S OUTCOME?")
    print("If the book implies MORE correlation than turns up, it has priced")
    print("the lead as safer than it was, so the leader should win LESS often")
    print("than its own price claimed. This is the tradeable form.")
    print("  %-22s %6s %8s %10s %10s %10s"
          % ("implied minus trailing", "n", "races", "claimed", "actual",
             "gap"))
    for lo, hi, lab in ((-9, -0.10, "book much LOWER"),
                        (-0.10, -0.02, "book lower"),
                        (-0.02, 0.02, "about right"),
                        (0.02, 0.10, "book higher"),
                        (0.10, 9, "book much HIGHER")):
        sel = [r for r in rows if r[3] is not None
               and lo <= (r[2] - r[3]) < hi]
        if len(sel) < 30:
            continue
        claimed = sum(r[6] for r in sel) / len(sel)
        actual = sum(1 for r in sel if r[7]) / float(len(sel))
        print("  %-22s %6d %8d %9.1f%% %9.1f%% %+9.1f%%"
              % (lab, len(sel), len({r[0] for r in sel}), 100 * claimed,
                 100 * actual, 100 * (actual - claimed)))
    print("  'claimed' is the book's own de-vigged probability for the leader.")
    print("  A negative gap means the leader won less often than the book said.")

    print("\n## 4. THE SAME, SPLIT BY TIME TO CLOSE")
    print("  %-22s %6s %8s %9s %9s"
          % ("tau band / bucket", "n", "races", "claimed", "actual"))
    for tlo, thi in ((10, 30), (45, 90), (120, 300)):
        for lo, hi, lab in ((-9, -0.02, "book lower"),
                            (-0.02, 0.02, "about right"),
                            (0.02, 9, "book higher")):
            sel = [r for r in rows if tlo <= r[1] <= thi and r[3] is not None
                   and lo <= (r[2] - r[3]) < hi]
            if len(sel) < 30:
                continue
            print("  %-22s %6d %8d %8.1f%% %8.1f%%"
                  % ("tau %d-%d %s" % (tlo, thi, lab), len(sel),
                     len({r[0] for r in sel}),
                     100 * sum(r[6] for r in sel) / len(sel),
                     100.0 * sum(1 for r in sel if r[7]) / len(sel)))

    print("\n## 5. HOW OFTEN IS THE BOOK OUTSIDE ANY CORRELATION AT ALL?")
    tot = sum(refused.values()) + len(rows)
    print("  %d of %d moments (%.1f%%) priced the leader outside what ANY"
          % (refused["outside_any_rho"], tot,
             100.0 * refused["outside_any_rho"] / tot if tot else 0))
    print("  correlation can produce. That is the book disagreeing with our")
    print("  VOLATILITIES rather than our correlation, and it is a check on us")
    print("  as much as on it.")

    print("\nEvery price here is a quote that existed. Nothing in this file is")
    print("a fill, a fill rate, or our loss rate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
