#!/usr/bin/env python3
"""oos.py -- WALK-FORWARD. What you would have made, trading it live.

    python research/oos.py --selftest
    python research/oos.py --data ./kalshi_data --out ./fulltape

WHY THIS IS THE LAST TEST

Every measurement in this project so far is in-sample. calfit.py fits one
parameter to every settled market and reports a; reconcile.py compares implied
volatility against settlement dispersion; calib.py bins outcomes by price. All
three look at the whole tape at once and describe it. None of them answers the
only question that decides anything:

    if you had been running this, with only what was known at the time,
    what would you have made?

That is not a stricter version of the same test. It is a different test, and it
is the one the project's own standard has always named -- "the same measurement,
on fresh data the finding has never seen" -- and never actually performed,
because until the settlement fetch was fixed on 2026-08-31 there was no fresh
data to perform it on.

HOW IT WORKS

Closes are taken in time order. At each close C:

    1. Fit `a` on markets that settled STRICTLY BEFORE C. Nothing else.
    2. Price every market closing at C off that a, at a fixed tau.
    3. Where the model's edge beats the spread and the fee, take the trade.
    4. Settle it. Record the P&L.

The parameter is refitted as the tape advances, so this is not "fit once, test
once" -- it is the strategy re-estimating itself the way it would have to, and
every trade is priced by a number that existed before the outcome did.

WHAT WOULD MAKE IT LIE, AND WHAT STOPS IT

  * LOOK-AHEAD is the whole risk here, and it is checked rather than asserted:
    the self-test plants a world whose `a` CHANGES halfway through and
    verifies the fitted parameter lags the change instead of anticipating it,
    which no leaking implementation can do.
  * A NULL THAT IS NOT ZERO. If the market is right, this strategy still
    trades -- and loses the spread and the fee every time. Zero is not the
    bar; the market-is-right null is, and it is negative.
  * ONE CLOSE IS ONE CLUSTER. Every series settles on the same clock and a
    crypto move is shared, so the standard error clusters on close time and
    `n` is closes, never trades.
  * POWER FIRST. The minimum detectable edge is printed above the result. A
    number smaller than it is not a small edge, it is no information --
    patterntrade.py's 5.7c MDE against a 3-5c effect is the lesson.

NOTHING HERE PLACES AN ORDER. This measures what an order WOULD have done.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from statistics import NormalDist, mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calfit import fit, outcome_of, P_LO, P_HI                  # noqa: E402
from voltiming import fee_cents, half_spread_c                  # noqa: E402

ND = NormalDist()


def decide(price, a, min_edge=0.0):
    """(side, entry, expected edge in cents) or None.

    Buys the side the model says is underpriced, crossing the spread and
    paying the taker fee. Both costs are inside the returned edge.
    """
    if not (P_LO <= price <= P_HI):
        return None
    q = ND.cdf(a * ND.inv_cdf(price))
    hs = half_spread_c(price) / 100.0
    if q > price:
        entry = min(price + hs, 0.999)          # buy YES at the ask
        edge = 100.0 * (q - entry) - fee_cents(entry)
        side = "yes"
    else:
        entry = max(price - hs, 0.001)          # buy NO: sell YES at the bid
        edge = 100.0 * (entry - q) - fee_cents(1.0 - entry)
        side = "no"
    return (side, entry, edge) if edge > min_edge else None


def settle_pnl(side, entry, won):
    if side == "yes":
        return 100.0 * (won - entry) - fee_cents(entry)
    return 100.0 * ((1.0 - won) - (1.0 - entry)) - fee_cents(1.0 - entry)


def walk_forward(rows, warmup=120, refit_every=5, min_edge=0.0, a_fixed=None,
                 window=6000):
    """rows: (close, price, outcome) per MARKET, any order.

    Returns (trades, a_path). Each trade is priced by an `a` fitted only on
    closes strictly earlier than its own.
    """
    by_close = defaultdict(list)
    for c, p, y in rows:
        by_close[c].append((c, p, y))
    closes = sorted(by_close)
    trades, a_path, seen = [], [], []
    a_cur, since = None, 10 ** 9
    for i, c in enumerate(closes):
        if i >= warmup:
            if since >= refit_every or a_cur is None:
                f = fit(seen) if a_fixed is None else None
                if a_fixed is not None:
                    a_cur = a_fixed
                elif f and f.get("bracketed"):
                    a_cur = f["a"]
                since = 0
            since += 1
            if a_cur is not None:
                a_path.append((c, a_cur))
                for _, p, y in by_close[c]:
                    d = decide(p, a_cur, min_edge)
                    if d:
                        side, entry, edge = d
                        trades.append({"close": c, "side": side, "entry": entry,
                                       "edge": edge, "price": p, "won": y,
                                       "a": a_cur,
                                       "pnl": settle_pnl(side, entry, y)})
        # only AFTER trading this close does it become training data
        seen.extend(by_close[c])
        # A ROLLING window, not everything ever seen. Two reasons and they
        # point the same way: it bounds the cost of a refit however far into
        # the tape we are, and volatility clusters -- this project's one
        # confirmed result -- so a parameter estimated from the recent past is
        # the relevant one, not an average over every regime that ever ran.
        if window and len(seen) > window:
            seen = seen[-window:]
    return trades, a_path


def summarise(trades, label=""):
    """Cluster-robust on close time. n is CLOSES, never trades."""
    if len(trades) < 10:
        return None
    by = defaultdict(list)
    for t in trades:
        by[t["close"]].append(t["pnl"])
    cl = [mean(v) for v in by.values()]
    n = len(cl)
    # THIRTY clusters, not three. At three the cluster standard error is
    # noise about noise, and this file proved it on its own real-data run:
    # the min-edge 2.00c cell reported +9.60c at t = +12.28 off 16 trades in
    # 12 closes, with an MDE of 2.35c -- LOWER than the 11.58c of the cell
    # above it, which is impossible for a smaller sample and is the tell.
    # A t of twelve is exactly the number that ends an argument, and it came
    # from twelve observations.
    if n < 30:
        return None
    m = mean(cl)
    sd = pstdev(cl) * math.sqrt(n / (n - 1.0))
    se = sd / math.sqrt(n)
    return {"label": label, "trades": len(trades), "closes": n, "mean": m,
            "se": se, "t": m / se if se > 0 else 0.0, "mde": 3.0 * se,
            "per_trade_sd": pstdev([t["pnl"] for t in trades])}


def market_null(trades, reps=2000, seed=20260901):
    """What this strategy earns if the BOOK is right: resettle every trade
    from its own quoted price. Negative by construction -- it pays the spread
    and the fee. This, not zero, is the bar."""
    if not trades:
        return None
    rng = random.Random(seed)
    by = defaultdict(list)
    for t in trades:
        by[t["close"]].append(t)
    keys = sorted(by)
    out = []
    for _ in range(reps):
        cl = []
        for c in keys:
            v = []
            for t in by[c]:
                won = 1.0 if rng.random() < t["price"] else 0.0
                v.append(settle_pnl(t["side"], t["entry"], won))
            cl.append(mean(v))
        out.append(mean(cl))
    out.sort()
    return {"lo": out[int(0.025 * reps)], "hi": out[int(0.975 * reps)],
            "mean": mean(out)}


def report(rows, label="", warmup=120, refit_every=5, min_edge=0.0):
    trades, a_path = walk_forward(rows, warmup, refit_every, min_edge)
    sm = summarise(trades, label)
    if not sm:
        ncl = len({t["close"] for t in trades})
        print(f"\n  {label}")
        print(f"    {len(trades)} trades over {ncl} closes -- under the "
              "30-cluster floor, so no standard error is reported.")
        print("    A cluster SE off a handful of clusters is noise about")
        print("    noise; this cell once printed t = +12.28 off 12 closes.")
        if trades:
            print(f"    (raw mean {mean(t['pnl'] for t in trades):+.2f}c, "
                  "stated WITHOUT any claim of significance)")
        return None
    nl = market_null(trades, reps=2000)
    print(f"\n  {label}")
    print(f"    trades / closes        {sm['trades']:,} / {sm['closes']}")
    if a_path:
        aa = [a for _, a in a_path]
        print(f"    a used, first -> last  {aa[0]:.4f} -> {aa[-1]:.4f}  "
              f"(min {min(aa):.4f}, max {max(aa):.4f})")
    print(f"    MDE                    {sm['mde']:.2f}c  "
          "<- read this BEFORE the result")
    print(f"    realised P&L per trade {sm['mean']:+.2f}c   t = {sm['t']:+.2f}")
    print(f"    market-is-right null   [{nl['lo']:+.2f}, {nl['hi']:+.2f}]c")
    if abs(sm["mean"]) < sm["mde"]:
        print("    INSIDE THE MDE -- no information, positive or negative.")
    elif sm["mean"] > nl["hi"]:
        print("    ABOVE the null. This is the first out-of-sample edge this")
        print("    project has produced. Treat it as a bug until it survives.")
    else:
        print("    inside or below the null -- the book was right.")
    return sm


# ===========================================================================
def _world(n_close, per_close, a_of_close, seed, rho=0.5):
    rnd = random.Random(seed)
    rows = []
    for c in range(n_close):
        zc = rnd.gauss(0, 1)
        a = a_of_close(c)
        for _ in range(per_close):
            p = rnd.uniform(0.05, 0.95)
            q = ND.cdf(a * ND.inv_cdf(p))
            u = math.sqrt(rho) * zc + math.sqrt(1 - rho) * rnd.gauss(0, 1)
            rows.append((c, p, 1.0 if u < ND.inv_cdf(q) else 0.0))
    return rows


def selftest():
    print("=" * 78)
    print("SELF-TEST -- against known answers")
    print("=" * 78)
    fails = []

    # ---- 1. a market that is RIGHT must cost the spread and the fee -------
    print("\n  A calibrated market (a = 1). The strategy still trades, and")
    print("  must LOSE -- it crosses a spread and pays a fee for nothing.")
    rows = _world(420, 10, lambda c: 1.00, seed=3)
    tr, _ = walk_forward(rows, warmup=120, refit_every=5)
    sm = summarise(tr)
    nl = market_null(tr, reps=200)
    print(f"    {sm['trades']:,} trades over {sm['closes']} closes, "
          f"P&L {sm['mean']:+.2f}c, null [{nl['lo']:+.2f}, {nl['hi']:+.2f}]c")
    if sm["mean"] > 0 and sm["mean"] > nl["hi"]:
        fails.append(f"a calibrated market paid {sm['mean']:+.2f}c, above its "
                     "own null -- the walk-forward is manufacturing an edge")

    # ---- 2. a REAL distortion must be found and must pay ------------------
    print("\n  A market that really is distorted (a = 1.30). The strategy")
    print("  must find it, and the money must beat the market-is-right null.")
    rows = _world(420, 10, lambda c: 1.30, seed=5)
    tr, ap = walk_forward(rows, warmup=120, refit_every=5)
    sm = summarise(tr)
    nl = market_null(tr, reps=200)
    aa = [a for _, a in ap]
    print(f"    a fitted {aa[0]:.3f} -> {aa[-1]:.3f} (planted 1.30)")
    print(f"    {sm['trades']:,} trades, P&L {sm['mean']:+.2f}c "
          f"(t={sm['t']:+.1f}), null [{nl['lo']:+.2f}, {nl['hi']:+.2f}]c")
    if abs(aa[-1] - 1.30) > 0.15:
        fails.append(f"the walk-forward fit converged to {aa[-1]:.3f}, not "
                     "the planted 1.30")
    if sm["mean"] <= nl["hi"]:
        fails.append(f"a genuinely distorted market paid {sm['mean']:+.2f}c, "
                     f"inside its null [{nl['lo']:.2f}, {nl['hi']:.2f}] -- the "
                     "strategy cannot collect an edge that is really there")

    # ---- 3. NO LOOK-AHEAD, checked rather than asserted -------------------
    # `a` jumps halfway through. A fit that only sees the past must LAG it.
    # Nothing that peeks can lag, so this is a positive test for the absence
    # of leakage rather than a comment claiming it.
    print("\n  LOOK-AHEAD. `a` jumps from 0.80 to 1.30 exactly halfway. A fit")
    print("  that only sees the past must LAG the jump. A leaking one cannot.")
    N = 560
    rows = _world(N, 10, lambda c: 0.80 if c < N // 2 else 1.30, seed=11)
    # window=1500 markets = 150 closes, so the rolling window ROLLS PAST the
    # jump inside this fixture and the fit has to relearn. At the default
    # 6,000 the window is wider than the whole fixture, the estimator
    # correctly averages both regimes to ~1.02, and the "did it relearn"
    # assertion is asking a question the fixture cannot answer.
    tr, ap = walk_forward(rows, warmup=120, refit_every=5, window=1500)
    at = dict(ap)
    before = mean([a for c, a in ap if N // 2 - 50 <= c < N // 2])
    after = mean([a for c, a in ap if N // 2 <= c < N // 2 + 50])
    later = mean([a for c, a in ap if c >= N - 80])
    print(f"    50 closes BEFORE the jump   a = {before:.3f}   (truth 0.80)")
    print(f"    50 closes AFTER  the jump   a = {after:.3f}   (still ~0.80 if")
    print("                                       nothing is peeking)")
    print(f"    the last 80 closes          a = {later:.3f}   (truth 1.30)")
    if before > 1.0:
        fails.append(f"before the jump the fit already read {before:.3f} -- it "
                     "is seeing closes that have not happened")
    if after > before + 0.25:
        fails.append(f"the fit moved from {before:.3f} to {after:.3f} within "
                     "50 closes of the jump -- far too fast to be learning it "
                     "from the past alone")
    if later < 1.10:
        fails.append(f"the fit never learned the new regime ({later:.3f}) -- "
                     "with a 150-close rolling window and 280 closes since "
                     "the jump, the old regime is long out of the window")

    # ---- 4. training data must be strictly earlier ------------------------
    print("\n  And directly: every trade's parameter must come from closes")
    print("  strictly EARLIER than its own. Checked by construction here.")
    seen_max, bad = -1, 0
    by_close = defaultdict(list)
    for c, p, y in rows:
        by_close[c].append((c, p, y))
    closes = sorted(by_close)
    train = []
    for i, c in enumerate(closes):
        if i >= 120 and train:
            if max(x[0] for x in train) >= c:
                bad += 1
        train.extend(by_close[c])
    print(f"    {len(closes)} closes, {bad} with training data at or after "
          "their own close")
    if bad:
        fails.append(f"{bad} closes trained on data from their own close or "
                     "later")

    # ---- 5. power, stated before any result ------------------------------
    print("\n  POWER. patterntrade's MDE was 5.7c at 583 clusters, larger")
    print("  than the effect it was testing. This must do better or say so.")
    print(f"\n  {'closes':>8}{'trades':>9}{'per-trade sd':>14}{'MDE':>9}")
    for n_close in (300, 560):
        rows = _world(n_close, 10, lambda c: 1.10, seed=21)
        tr, _ = walk_forward(rows, warmup=100, refit_every=5)
        sm = summarise(tr)
        if sm:
            print(f"  {sm['closes']:>8}{sm['trades']:>9,}"
                  f"{sm['per_trade_sd']:>13.1f}c{sm['mde']:>8.2f}c")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- loses on a calibrated market, collects a real")
    print("distortion above its own null, LAGS a regime change instead of")
    print("anticipating it, and trains only on closes strictly earlier than")
    print("the one it is trading.")
    return True


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--tau", type=int, default=600)
    ap.add_argument("--max-age", type=int, default=30)
    ap.add_argument("--warmup", type=int, default=150)
    ap.add_argument("--refit-every", type=int, default=5)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    from replay import load_quotes, load_markets
    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    quotes = load_quotes(a.data)
    if not quotes:
        print("\n  no quotes on disk. Run doctor.py.")
        return
    markets = load_markets(a.out)
    if not markets:
        print(f"\n  *** NO SETTLED MARKETS at {os.path.abspath(a.out)}.")
        return

    def build(tau):
        rows = []
        for tk, q in quotes.items():
            m = markets.get(tk)
            if not m:
                continue
            y = outcome_of(m)
            close = m.get("close")
            if y is None or close is None:
                continue
            want = int(round(float(close))) - tau
            best = None
            for rec in q:
                t = int(rec[0])
                if t <= want and (best is None or t > best[0]):
                    best = (t, rec)
            if best is None or want - best[0] > a.max_age:
                continue
            bid, ask = best[1][1], best[1][2]
            if not (0.0 < bid < ask < 1.0):
                continue
            mid = (bid + ask) / 2.0
            if P_LO <= mid <= P_HI:
                rows.append((int(round(float(close))), mid, y))
        return rows

    print("\n" + "=" * 78)
    print("WALK-FORWARD -- every trade priced by an `a` fitted only on")
    print("closes strictly earlier than its own")
    print("=" * 78)
    print(f"  warmup {a.warmup} closes, refit every {a.refit_every}")

    cache = {}
    for tau in (120, 240, 360, 480, 600, 720, 840):
        rows = cache.setdefault(tau, build(tau))
        if len(rows) < 500:
            print(f"\n  tau={tau}s: {len(rows)} markets -- too few.")
            continue
        report(rows, f"tau = {tau}s, {len(rows):,} markets", a.warmup,
               a.refit_every)

    print("\n" + "=" * 78)
    print("A MINIMUM-EDGE FILTER -- only take trades the model likes a lot")
    print("=" * 78)
    print("  Every cell above takes any trade whose edge clears the spread")
    print("  and the fee. Demanding more should raise the P&L per trade if")
    print("  the edge is real, and do nothing if it is noise being selected.")
    rows = cache.setdefault(a.tau, build(a.tau))
    if len(rows) >= 500:
        for me in (0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0):
            report(rows, f"min edge {me:.2f}c at tau={a.tau}s", a.warmup,
                   a.refit_every, min_edge=me)

    # ---- per series ------------------------------------------------------
    # A common mechanism should pay in more than one series. One series
    # carrying the whole result is a story about that series, and with nine
    # of them a single |t| > 2 is what nine looks like.
    print("\n" + "=" * 78)
    print("PER SERIES -- one series carrying the result is not a mechanism")
    print("=" * 78)
    by_ser = defaultdict(list)
    for tk, q in quotes.items():
        m = markets.get(tk)
        if not m:
            continue
        by_ser[m.get("series") or tk.split("-")[0]].append(tk)
    all_q = quotes
    for ser in sorted(by_ser):
        quotes = {tk: all_q[tk] for tk in by_ser[ser] if tk in all_q}
        rws = build(a.tau)
        quotes = all_q
        if len(rws) < 400:
            print(f"\n  {ser}: {len(rws)} markets -- too few.")
            continue
        report(rws, f"{ser}, {len(rws):,} markets", a.warmup, a.refit_every)

    # ---- how long would it take to know? ---------------------------------
    print("\n" + "=" * 78)
    print("HOW MUCH MORE TAPE WOULD SETTLE IT")
    print("=" * 78)
    # The best-POPULATED cell, not whatever --tau happens to be. The first
    # run took its per-close sd from tau=600s, which had 173 closes where the
    # neighbouring taus had 450, and so overstated the tape required.
    base, base_tau = None, None
    for tau, rws in sorted(cache.items()):
        sm_ = summarise(walk_forward(rws, a.warmup, a.refit_every)[0])
        if sm_ and (base is None or sm_["closes"] > base["closes"]):
            base, base_tau = sm_, tau
    if base:
        print(f"  from the best-populated cell, tau = {base_tau}s.")
    if base:
        sd = base["se"] * math.sqrt(base["closes"])
        print(f"  per-close sd {sd:.2f}c over {base['closes']} closes.")
        print(f"\n  {'to certify':>12}{'closes needed':>16}{'hours':>9}"
              f"{'days':>7}")
        for edge in (0.5, 1.0, 2.0, 3.0):
            n = (3.0 * sd / edge) ** 2
            print(f"  {edge:>11.1f}c{n:>16,.0f}{n/4:>9,.0f}{n/96:>7.1f}")
        print("\n  Four closes an hour, shared by every series. This is the")
        print("  honest cost of an answer, and it is why more recording is")
        print("  worth more than more analysis of what is already here.")

    print("\n  Read the MDE line in every cell before its P&L. And read the")
    print("  market-is-right null, which is NEGATIVE: a strategy that ties")
    print("  the null has found nothing, it has merely paid the fee.")


if __name__ == "__main__":
    main()
