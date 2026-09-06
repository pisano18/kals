#!/usr/bin/env python3
# VERSION: 2026-09-04-p1
"""
pin.py -- the pinned endgame: harvesting quotes the settlement math has
already overtaken.

    python research/pin.py --selftest
    python research/pin.py --data ./kalshi_data --out ./fulltape

THE CELL, AND WHY IT IS DIFFERENT FROM endgame.py's VERDICT

Settlement is the mean of 60 one-second prints and with tau seconds left,
60 - tau of them are LOCKED on our own disk. endgame.py's Part 1 shows the
exact consequence: at tau = 20 the remaining uncertainty is a small fraction
of what sqrt(tau) pretends, and by tau = 10 the sd/sigma ratio is 0.327/1.86
of naive -- fair value has almost stopped depending on any volatility
estimate. That is the one region where OUR model can be more right than a
lazy quote without knowing anything the tape does not contain.

endgame.py already swept "trade when |fair - mid| clears a floor" across the
whole last 120 seconds and found everything inside a 3.3-5.1c MDE. This is a
DIFFERENT cell with a different power profile: only seconds where the model
says the outcome is effectively decided (fair >= 0.98 or <= 0.02), and only
against a quote on the WRONG SIDE of that near-certainty -- an ask still
selling a near-won contract cheap, a bid still paying real cents for a
near-dead one. Four of the strategy panel's twenty-one candidates were this
one idea wearing different clothes, and it is the highest-confidence family
on the list precisely because the edge does not require anyone to be wrong
about anything difficult -- only slow.

THE HAZARD IS THE TAIL, so it is priced, printed, and controlled:

  * a pinned trade wins ~1-3c and loses ~97c. The claimed edge already nets
    the model's own flip probability; whether the model's flip probability
    is HONEST is exactly what the fair-band vs realised comparison decides.
    A realised P&L below the fair band means OUR sigma was too small in the
    tail, not that the market was slow. The self-test manufactures that
    exact failure and requires the report to catch it.
  * one trade per CLOSE (endgame.evaluate keys on close time), so n is
    close-time clusters by construction and a BTC crash that flips five
    series at once cannot masquerade as five losses' worth of independence
    -- or five wins'.
  * the earliest qualifying second is taken, never the best one -- taking
    the maximum disagreement in a window is a look-ahead endgame.py
    measured at -49.5c on a zero-edge tape.
  * the market-is-right null (outcomes redrawn at the MID) is printed next
    to the realised number, with the MDE, before anything is believed.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from statistics import NormalDist, mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import var_factor, N_AVG, fee_per_contract     # noqa: E402
from settlewin import partial                               # noqa: E402
from tdist import crit as _tcrit                            # noqa: E402
from endgame import (scan, evaluate, summarise, redraw_null,  # noqa: E402
                     mde, fee_cents, outcome_of, sigma_from)

ND = NormalDist()


def t_crit(df):
    return _tcrit(0.05, df)
PIN = 0.98                  # fair beyond this (or below 1-PIN) is "decided"
TAU_MAX = 60                # the sigma-proof region; also swept at 20
FLOORS = (0.3, 0.5, 1.0, 2.0)      # cents of fee-netted edge required


def pinned_rows(rows, pin=PIN):
    return [r for r in rows if r["fair"] >= pin or r["fair"] <= 1.0 - pin]


# ===========================================================================
# OUT OF SAMPLE -- the answer to "BELOW the fair band"
# ===========================================================================
def refair(f, k):
    """Fair value recomputed with sigma scaled by k, exactly and cheaply.

    fair = Phi(z) with z = (mu - K)/sd and sd proportional to sigma, so
    scaling sigma by k sends z -> z/k. No rescan of the tape is needed to
    ask "what would this have looked like with a less confident model?"
    """
    f = min(1.0 - 1e-12, max(1e-12, float(f)))
    return ND.cdf(ND.inv_cdf(f) / k)


def _stated(t, k):
    """The probability the model assigns to the side this trade took."""
    f = refair(t["fair"], k)
    return f if t["side"] == "yes" else 1.0 - f


def _happened(t):
    w = t.get("won")
    if w is None:
        return None
    return w if t["side"] == "yes" else 1.0 - w


def fit_k(trades, lo=0.30, hi=8.0, iters=60):
    """The sigma multiplier that makes the model's confidence match reality.

    THE FIRST REAL RUN FLAGGED EVERY CELL "BELOW the fair band": the model
    claimed +2.51c and delivered +1.70c at tau<=20, and claimed +12.01c
    against +4.73c at the 2c floor. That is a model too sure of itself, and
    the bias grows with the size of the disagreement -- exactly the shape of
    selecting on our own error rather than on the market's.

    An overconfident model is not necessarily a worthless one. If the ONLY
    fault is that sigma is too small, one number fixes it, and that number
    can be fitted on closes strictly earlier than the one being traded. Then
    the question stops being "is our model right" and becomes "does what is
    left, out of sample, still beat the market-is-right null".

    Fitted by matching the mean stated probability of the taken side to the
    rate at which that side actually won. Monotone in k, so bisection.
    """
    ts = [t for t in trades if _happened(t) is not None]
    if len(ts) < 30:
        return None
    hit = mean(_happened(t) for t in ts)

    def gap(k):
        return mean(_stated(t, k) for t in ts) - hit

    glo, ghi = gap(lo), gap(hi)
    if glo * ghi > 0:
        # the calibration cannot be reached inside the bracket -- refuse to
        # extrapolate rather than returning an endpoint that looks fitted
        return None
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if gap(mid) * glo > 0:
            lo, glo = mid, gap(mid)
        else:
            hi = mid
    return 0.5 * (lo + hi)


def walk_forward(rows, floor=0.5, pin=PIN, warmup=150, refit_every=10):
    """Every trade priced by a k fitted on closes strictly EARLIER than its own.

    Returns (trades, k_path). A close becomes training data only AFTER it has
    been traded, which is the whole point; oos.py's self-test proves the same
    construction lags a planted regime change instead of anticipating it.
    """
    by_close = defaultdict(list)
    for r in rows:
        by_close[r["close"]].append(r)
    closes = sorted(by_close)
    seen, out, kpath = [], [], []
    k_cur, since = 1.0, 10 ** 9
    for i, c in enumerate(closes):
        if i >= warmup:
            if since >= refit_every:
                kk = fit_k(seen)
                if kk is not None:
                    k_cur = kk
                since = 0
            since += 1
            sub = [dict(r, fair=refair(r["fair"], k_cur)) for r in by_close[c]]
            tr = evaluate(pinned_rows(sub, pin), edge_floor=floor,
                          rule="first")
            # EVERY post-warmup close, not only the ones that traded. Recording
            # k only when a trade fired made a WORKING recalibration look
            # broken: once k rose enough to stop the trading, no further k was
            # ever recorded, so the path read "1.00 -> 1.00" while the fit was
            # actually at 4x and correctly refusing to trade.
            kpath.append((c, k_cur))
            out.extend(tr)
        # TRAINING POPULATION IS FIXED AT k=1 on purpose: conditioning the
        # training set on the current k would let today's estimate choose
        # which of yesterday's trades it is judged against.
        seen.extend(evaluate(pinned_rows(by_close[c], pin),
                             edge_floor=floor, rule="first"))
    return out, kpath


def flips(trades):
    """Trades where the near-certain side lost -- the tail, enumerated."""
    out = []
    for t in trades:
        won = t.get("won")
        if won is None:
            continue
        if (t["side"] == "yes" and won < 0.5) or \
           (t["side"] == "no" and won > 0.5):
            out.append(t)
    return out


def block(trades, label, reps=2000):
    """One (tau, floor) cell: MDE first, then the number, then both bands."""
    if not trades:
        print(f"    {label:<26} no trades qualified")
        return
    sm = summarise(trades, label)
    if sm is None:
        print(f"    {label:<26} {len(trades)} trades -- too few to score, "
              f"raw mean {mean(t['pnl'] for t in trades):+.2f}c")
        return
    fl = flips(trades)
    md = mde(trades)
    nm = redraw_null(trades, reps=reps, using="mid", value=sm["mean"])
    nf = redraw_null(trades, reps=reps, using="fair", value=sm["mean"])
    # RANK, NOT THE EDGE. The fair band is discrete (see redraw_null): the
    # 2.5% cut can fall inside an atom carrying several percent of the mass,
    # and `sm["mean"] < nf["lo"]` then decides on floating-point noise. The
    # mid-p rank is the same test where the band is smooth and is defined
    # where it is not. TIED is printed rather than resolved, because a cell
    # sitting on the boundary atom is neither below the band nor inside it.
    # BOTH halves of this verdict run on a discrete band, and only one of
    # them was guarded until 2026-09-06. Measured on the real tau<=20
    # floor-0.5c cell: the fair band holds 11 atoms in 2000 draws (4.40% of
    # the mass sitting on the 2.5% cut) and the MID band holds 23 atoms with
    # 2.65% on the 97.5% cut. The mid half happened to clear by +2.08c so
    # nothing flipped -- but "happened to" is not a guard, so the
    # market-is-right test is now the mid band's own mid-p rank too.
    rank = nf.get("rank")
    rank_m = nm.get("rank")
    below = rank is not None and rank < 0.025
    beats = (rank_m > 0.975) if rank_m is not None else (sm["mean"] > nm["hi"])
    tied = (rank is not None and not below
            and nf["ties"] > 0 and abs(sm["mean"] - nf["lo"]) < 1e-6)
    tied_m = (rank_m is not None and nm["ties"] > 0
              and abs(sm["mean"] - nm["hi"]) < 1e-6)
    verdict = ""
    if beats and not below:
        verdict = "  <-- beats the market-is-right null"
        if tied:
            verdict += " (fair band TIED at the edge)"
        if tied_m:
            verdict += " (mid band TIED at the edge)"
    elif below:
        verdict = "  <-- BELOW the fair band: OUR tail probability is wrong"
    elif tied_m:
        verdict = "  <-- mid band TIED: realised sits ON the boundary atom"
    elif tied:
        verdict = "  <-- fair band TIED: realised sits ON the boundary atom"
    # WHAT THESE TRADES ACTUALLY ARE. The first real run reported +2.29c
    # with 18 flips in 316, and the walk-forward reported +2.27c with 70 in
    # 270 -- nearly identical money from a completely different bet, and the
    # only way to see it was to solve for the entry price by hand afterwards.
    # A near-certainty bought at 92c that wins 94% of the time and a coin
    # flip bought at 70c that wins 74% are not the same strategy, and the
    # report must not make them look like one.
    # SPLIT THE MIXTURE. The first version printed one mean entry and one
    # mean win, and the pair was arithmetically impossible for a binary --
    # win minus loss must be 100c per trade, and it printed +3.7 and -2.2.
    # The trades are two opposite populations: DEAR ones bought near 96c
    # (win +4c, lose -96c) and CHEAP ones bought near 2c (win +98c, lose
    # -2c). Averaging them gives 74.9c, a price at which nothing was ever
    # bought. Each side is separately zero-EV if the market is right, so
    # both must be shown or neither means anything.
    flset = {id(t) for t in fl}
    cost = [(100.0 * t["entry"] if t["side"] == "yes"
             else 100.0 * (1.0 - t["entry"]), t) for t in trades]
    dear = [(c, t) for c, t in cost if c >= 50.0]
    cheap = [(c, t) for c, t in cost if c < 50.0]

    def leg(rows):
        if not rows:
            return None
        w = sum(1 for _, t in rows if id(t) not in flset)
        return (len(rows), mean(c for c, _ in rows),
                100.0 * w / len(rows), mean(t["pnl"] for _, t in rows))

    dl, cl = leg(dear), leg(cheap)
    wr = 100.0 * (1.0 - len(fl) / len(trades))
    print(f"    {label:<26} n={sm['n']:>4} closes  MDE {md:>5.2f}c  "
          f"claimed {sm['exp_edge']:+.2f}c  realised {sm['mean']:+.2f}c "
          f"(t={sm['t']:+.1f})")
    def fmt(nm, L):
        if L is None:
            return f"{nm} none"
        return (f"{nm} n={L[0]} paid {L[1]:.0f}c won {L[2]:.0f}% "
                f"P&L {L[3]:+.2f}c")
    print(f"    {'':<26} overall won {wr:.1f}% "
          f"(model said >={100 * PIN:.0f}%)   "
          f"{fmt('DEAR', dl)}   {fmt('CHEAP', cl)}")
    # PRICE THE LOSS THAT HAS NOT HAPPENED YET. The dear leg won 260 of 260
    # on the 2026-09-06 tape, so its downside is entirely unobserved -- and
    # a single flip at a 96c entry costs 33 winners. Picking up pennies in
    # front of a roller is exactly the shape that looks best right up until
    # it does not, so the breakeven flip rate is printed next to the rule-of
    # -three upper bound on the rate actually seen. Headroom between those
    # two is the whole margin of safety, and it must be stated, not felt.
    if dl and dl[0] >= 20:
        n_d, paid, wr_d, pnl_d = dl
        fl_d = sum(1 for _, t in dear if id(t) in flset)
        lose = -paid - 100.0 * fee_per_contract(paid / 100.0)
        be = pnl_d / (pnl_d - lose) if pnl_d > lose else float("nan")
        ub = 100.0 * (3.0 + fl_d) / n_d       # rule of three, extended
        print(f"    {'':<26} DEAR tail: {fl_d} flips in {n_d}"
              f"  -> 95% upper bound {ub:.2f}%"
              f"  breakeven {100 * be:.2f}%"
              f"  headroom {100 * be / ub if ub else 0:.1f}x")
    print(f"    {'':<26} mid-null [{nm['lo']:+.2f},{nm['hi']:+.2f}]"
          f"  fair-band [{nf['lo']:+.2f},{nf['hi']:+.2f}]{verdict}")
    # PRINT THE DISCRETENESS. A band whose 2.5% cut sits inside an atom
    # holding several percent of the mass is not a 2.5% cut, and the reader
    # cannot see that from the interval alone.
    print(f"    {'':<26} band atoms: mid {nm['atoms']:,}/{reps:,} "
          f"(cuts hold {100*nm['lo_mass']:.1f}%/{100*nm['hi_mass']:.1f}%)"
          f"   fair {nf['atoms']:,}/{reps:,} "
          f"(cuts hold {100*nf['lo_mass']:.1f}%/{100*nf['hi_mass']:.1f}%)"
          f"   ranks mid {100*rank_m:.1f}% fair {100*rank:.1f}%")


def run_cells(rows, reps=2000):
    pr = pinned_rows(rows)
    print(f"\n  {len(rows):,} endgame quote-seconds, {len(pr):,} of them "
          f"pinned (fair beyond {PIN:.2f})")
    for tau_max in (20, TAU_MAX):
        sub = [r for r in pr if r["tau"] <= tau_max]
        print(f"\n  tau <= {tau_max}s")
        for floor in FLOORS:
            block(evaluate(sub, edge_floor=floor, rule="first"),
                  f"edge floor {floor:.1f}c", reps=reps)


# ===========================================================================
# THE PORTFOLIO -- every coin, every close, and what that really buys
# ===========================================================================
def evaluate_markets(rows, edge_floor=0.0, rule="first"):
    """One trade per MARKET, not one per close.

    Every table above this takes a single trade per close time, which is a
    STATISTICAL rule and not a trading limit: the twelve crypto series all
    settle on the quarter hour, so twelve markets share every close, and
    counting them as twelve observations would be counting one crypto move
    twelve times. IDEAS.md B2 puts the price on that -- rho ~ 0.8 gives
    **1.22 effective independent units per close, not 12**.

    A live book has no such rule. It can hold all twelve. So this evaluates
    every market, and `portfolio()` then sums within a close and clusters on
    the close -- which keeps n honest while letting the money be real.

    Each market belongs to exactly one close (strike(N+1) == settle(N), one
    strike per window), so calling the per-close evaluator once per ticker
    yields exactly one trade per market and reuses the audited rule rather
    than restating it.
    """
    by_tk = defaultdict(list)
    for r in rows:
        by_tk[r["tk"]].append(r)
    out = []
    for tk, rs in by_tk.items():
        for t in evaluate(rs, edge_floor=edge_floor, rule=rule):
            out.append(dict(t, tk=tk))
    return out


def portfolio(trades, label="", contracts=50):
    """P&L per CLOSE, summed over every coin traded at that close.

    n stays the number of closes, so the correlation is handled by
    construction rather than by an assumption. What changes is that a close
    now earns the SUM over its markets, which is what a live book would
    take -- and loses the sum too, which is the entire point: twelve
    correlated coins are twelve times the money AND twelve times the loss on
    the close that goes wrong. That is leverage, not diversification, and
    the worst-close column is where it shows.
    """
    if len(trades) < 30:
        return None
    byc = defaultdict(list)
    for t in trades:
        byc[t["close"]].append(t)
    per = [sum(x["pnl"] for x in v) for v in byc.values()]
    wide = [len(v) for v in byc.values()]
    span_days = (max(byc) - min(byc)) / 86400.0
    G = len(per)
    mu, sd = mean(per), pstdev(per) * math.sqrt(G / (G - 1.0))
    se = sd / math.sqrt(G)
    worst = min(per)
    return {"label": label, "G": G, "trades": len(trades), "sd": sd,
            "per_close": mu, "t": mu / se if se > 0 else 0.0,
            "mde": t_crit(G - 1) * se, "width": mean(wide),
            "maxwidth": max(wide), "worst": worst,
            # $/day MUST use the rate this cell actually FIRES at, not the
            # 96-close grid. Two errors lived in `mu * 96`: the strategy does
            # not trade every close (tau<=20 fires 37.2/day), and available
            # closes ran 63.3/day in the measured window anyway. Measured
            # 2026-09-06, it overstated the four published portfolio figures
            # by 1.73x to 3.91x. worst_day is unaffected -- it is per close.
            "fired_per_day": G / max(span_days, 1e-9),
            "day": mu * (G / max(span_days, 1e-9)) * contracts / 100.0,
            "worst_day": worst * contracts / 100.0}


def run_portfolio(rows, floors=(0.5,), contracts=50):
    print("\n" + "=" * 78)
    print("EVERY COIN AT ONCE -- the same rule run across all twelve series,")
    print("summed within each close. n is still CLOSES, because twelve coins")
    print("settling on the same tick are not twelve independent bets.")
    print("=" * 78)
    print("  IDEAS.md B2: twelve series at rho ~ 0.8 give 1.22 effective")
    print("  independent units per close, not 12. So this multiplies the")
    print("  MONEY by the number of coins and the RISK by very nearly the")
    print("  same factor. It is leverage. Read the worst-close column as the")
    print("  price of it.\n")
    for tau_max in (20, TAU_MAX):
        sub = [r for r in rows if r["tau"] <= tau_max]
        for floor in floors:
            tr, _kp = walk_forward(sub, floor=floor)
            # the same out-of-sample rule, but keeping every market
            trm = _walk_markets(sub, floor=floor)
            p1 = portfolio(tr, "one per close", contracts)
            pa = portfolio(trm, "every market", contracts)
            print(f"  tau <= {tau_max}s, floor {floor:.1f}c")
            for pp in (p1, pa):
                if pp is None:
                    continue
                print(f"    {pp['label']:<16} {pp['trades']:>5} trades over "
                      f"{pp['G']:>4} closes ({pp['width']:.1f} coins/close, "
                      f"max {pp['maxwidth']})")
                print(f"    {'':<16} per close {pp['per_close']:+7.2f}c  "
                      f"t={pp['t']:+5.1f}  MDE {pp['mde']:.2f}c   "
                      f"WORST close {pp['worst']:+8.1f}c")
                print(f"    {'':<16} at {contracts} contracts: "
                      f"${pp['day']:+.0f}/day   worst single close "
                      f"${pp['worst_day']:+.2f}")


def _walk_markets(rows, floor=0.5, pin=PIN, warmup=150, refit_every=10):
    """walk_forward, but keeping EVERY market at each close."""
    by_close = defaultdict(list)
    for r in rows:
        by_close[r["close"]].append(r)
    closes = sorted(by_close)
    seen, out = [], []
    k_cur, since = 1.0, 10 ** 9
    for i, c in enumerate(closes):
        if i >= warmup:
            if since >= refit_every:
                kk = fit_k(seen)
                if kk is not None:
                    k_cur = kk
                since = 0
            since += 1
            sub = [dict(r, fair=refair(r["fair"], k_cur))
                   for r in by_close[c]]
            out.extend(evaluate_markets(pinned_rows(sub, pin),
                                        edge_floor=floor, rule="first"))
        seen.extend(evaluate(pinned_rows(by_close[c], pin),
                             edge_floor=floor, rule="first"))
    return out


def run_oos(rows, reps=2000):
    """The in-sample table above looked at eight cells and every one of them
    was flagged overconfident. This is the same question asked once, out of
    sample, with the confidence fitted only on the past."""
    print("\n" + "=" * 78)
    print("OUT OF SAMPLE -- sigma recalibrated on closes strictly earlier")
    print("than the one being traded, so 'our model is overconfident' stops")
    print("being an excuse and becomes a fitted number")
    print("=" * 78)
    for tau_max in (20, TAU_MAX):
        sub = [r for r in rows if r["tau"] <= tau_max]
        print(f"\n  tau <= {tau_max}s")
        for floor in FLOORS:
            tr, kp = walk_forward(sub, floor=floor)
            ks = [k for _, k in kp]
            lab = f"edge floor {floor:.1f}c"
            if ks:
                lab += f"  k {ks[0]:.2f}->{ks[-1]:.2f}"
            block(tr, lab, reps=reps)


# ===========================================================================
def _world(n_mkt, sigma_true, sigma_fed=None, book="stale", seed=1,
           step=900, coins=1, rho=0.85):
    """One series, one continuous index, consecutive 15-minute windows.

    book="stale":  the last 90 seconds quote frozen at the tau=90 fair +-1c.
                   Whatever the index does after that, the book sleeps
                   through -- the lazy quote this stage hunts.
    book="honest": every second re-quotes TRUE fair +-1c (computed with the
                   TRUE sigma). Nothing to harvest but the spread.
    """
    rnd = random.Random(seed)
    base = 1767225600
    end = base + n_mkt * step + 5
    # COINS SHARE CLOSE TIMES AND A COMMON SHOCK. Every crypto series on
    # Kalshi settles on the quarter hour, and at rho ~ 0.8 twelve of them
    # carry about 1.22 independent bets between them. A fixture with one
    # market per close cannot show that, so it cannot test the portfolio
    # view at all -- which is exactly how an undefined name reached a commit
    # inside that code path.
    idx = {}
    for c in range(coins):
        idx[f"IDX{c}"] = {}
    px = {f"IDX{c}": 79000.0 for c in range(coins)}
    t = base - 200
    while t <= end:
        common = rnd.gauss(0, sigma_true)
        for c in range(coins):
            own = rnd.gauss(0, sigma_true)
            px[f"IDX{c}"] += (math.sqrt(rho) * common +
                              math.sqrt(1.0 - rho) * own)
            idx[f"IDX{c}"][t] = px[f"IDX{c}"]
        t += 1
    quotes, markets = {}, {}
    sigs = {f"KXT{c}": (sigma_fed if sigma_fed is not None else sigma_true)
            for c in range(coins)}
    s2i = {f"KXT{c}": f"IDX{c}" for c in range(coins)}

    def true_fair(ticks, close_s, now_s, strike):
        p = partial(ticks, close_s, now_s)
        if p is None:
            return None
        locked, r = p
        mu = (locked + r * ticks[now_s]) / N_AVG
        sd = sigma_true * math.sqrt(var_factor(int(close_s - now_s), [1.0]))
        if sd <= 0:
            return 1.0 if mu > strike else 0.0
        return ND.cdf((mu - strike) / sd)

    for k in range(n_mkt):
      for c in range(coins):
        ticks = idx[f"IDX{c}"]
        open_s = base + k * step
        close_s = open_s + step
        tk = f"KXT{c}-{k}"
        strike = ticks[open_s]          # 50/50 at the open
        ql = []
        frozen = None
        for s in range(close_s - 90, close_s):
            f = true_fair(ticks, close_s, s, strike)
            if f is None:
                continue
            if book == "stale":
                if frozen is None:
                    frozen = f
                f_q = frozen
            else:
                f_q = f
            bid = min(0.989, max(0.001, f_q - 0.01))
            ask = min(0.999, max(0.011, f_q + 0.01))
            ql.append((s, bid, ask, 50.0, 50.0))
        settle = mean(ticks[s] for s in range(close_s - N_AVG + 1,
                                              close_s + 1))
        quotes[tk] = ql
        markets[tk] = {"ticker": tk, "series": f"KXT{c}", "strike": strike,
                       "close": close_s, "settle": settle,
                       "result": 1.0 if settle >= strike else 0.0}
    return quotes, idx, markets, s2i, sigs


def selftest():
    print("=" * 78)
    print("SELF-TEST -- against known answers")
    print("=" * 78)
    fails = []

    # ---- 1. a sleeping book must be harvested, and honestly --------------
    print("\n  A book that freezes 90 seconds out while the index decides")
    print("  the outcome. The harvest must collect, the realised mean must")
    print("  sit inside its own fair band and above the market-is-right")
    print("  null.")
    q, ix, mk, s2i, sigs = _world(300, sigma_true=8.0, book="stale", seed=3)
    rows = scan(q, ix, mk, s2i, sigs, tau_max=TAU_MAX)
    tr = evaluate(pinned_rows(rows), edge_floor=0.5, rule="first")
    sm = summarise(tr)
    nm = redraw_null(tr, reps=500, using="mid", value=sm["mean"])
    nf = redraw_null(tr, reps=500, using="fair", value=sm["mean"])
    # RANKS, NOT RAW BAND EDGES. Both bands are discrete -- block() says why
    # and section 4 below proves the raw comparison is ulp-fragile on this
    # very fixture -- so every assertion here thresholds the mid-p rank.
    print(f"    {sm['n']} closes, claimed {sm['exp_edge']:+.2f}c, "
          f"realised {sm['mean']:+.2f}c, mid-null hi {nm['hi']:+.2f}c "
          f"(rank {100*nm['rank']:.1f}%, {nm['atoms']} atoms), "
          f"fair band [{nf['lo']:+.2f},{nf['hi']:+.2f}] "
          f"(rank {100*nf['rank']:.1f}%, {nf['atoms']} atoms)")
    if sm["n"] < 100:
        fails.append(f"only {sm['n']} closes harvested from 300 sleeping "
                     "markets -- the filter is throwing the cell away")
    if not nm["rank"] > 0.975:
        fails.append("a frozen book was not beaten -- the one world where "
                     f"this must collect (mid-null rank {100*nm['rank']:.1f}%)")
    if not (0.025 <= nf["rank"] <= 0.975):
        fails.append(f"realised {sm['mean']:+.2f}c sits outside its own "
                     f"fair band (rank {100*nf['rank']:.1f}%) -- the "
                     "claimed edge is dishonest about the flip probability")

    # ---- 2. an honest book must yield (nearly) nothing -------------------
    print("\n  The same world, but the book re-quotes true fair every")
    print("  second. Nothing to harvest but the spread and the fee.")
    q2, ix2, mk2, s2i2, sigs2 = _world(300, sigma_true=8.0, book="honest",
                                       seed=5)
    rows2 = scan(q2, ix2, mk2, s2i2, sigs2, tau_max=TAU_MAX)
    tr2 = evaluate(pinned_rows(rows2), edge_floor=0.5, rule="first")
    print(f"    trades against the honest book: {len(tr2)}")
    if len(tr2) > 15:
        sm2 = summarise(tr2)
        nm2 = redraw_null(tr2, reps=500, using="mid", value=sm2["mean"])
        if sm2 and nm2 and nm2["rank"] > 0.975:
            fails.append(f"the harvest claims {sm2['mean']:+.2f}c against a "
                         "book that is never wrong (mid-null rank "
                         f"{100*nm2['rank']:.1f}%)")

    # ---- 3. the tail-risk trap: OUR sigma too small ----------------------
    print("\n  The model is fed a sigma 4x too SMALL, so it calls outcomes")
    print("  decided while they are still coin-adjacent. The report must")
    print("  land BELOW the fair band -- the flag that says the model, not")
    print("  the market, is wrong.")
    q3, ix3, mk3, s2i3, sigs3 = _world(300, sigma_true=8.0, sigma_fed=2.0,
                                       book="honest", seed=7)
    rows3 = scan(q3, ix3, mk3, s2i3, sigs3, tau_max=TAU_MAX)
    tr3 = evaluate(pinned_rows(rows3), edge_floor=0.5, rule="first")
    if len(tr3) < 30:
        fails.append("the overconfident model produced almost no phantom "
                     "trades -- the trap fixture is not a trap")
    else:
        tr_in3 = tr3
        sm3 = summarise(tr3)
        nf3 = redraw_null(tr3, reps=500, using="fair", value=sm3["mean"])
        print(f"    {sm3['n']} closes, claimed {sm3['exp_edge']:+.2f}c, "
              f"realised {sm3['mean']:+.2f}c, fair band "
              f"[{nf3['lo']:+.2f},{nf3['hi']:+.2f}] "
              f"(rank {100*nf3['rank']:.1f}%, {nf3['atoms']} atoms)")
        if not nf3["rank"] < 0.025:
            fails.append("an overconfident model's phantom edge was NOT "
                         "flagged: realised sits inside the fair band it "
                         f"should have fallen out of (rank "
                         f"{100*nf3['rank']:.1f}%)")

    # ---- 3b. the walk-forward must LEARN the overconfidence --------------
    print("\n  Same overconfident world, but sigma now recalibrated on")
    print("  closes strictly EARLIER than the one being traded. The fitted")
    print("  k must climb toward the 4x it was lied to by, and the money")
    print("  must stop being negative.")
    tr3b, kp = walk_forward(rows3, floor=0.5, warmup=60, refit_every=5)
    ks = [k for _, k in kp]
    print(f"    k fitted {ks[0]:.2f} -> {ks[-1]:.2f} (truth 4.00); "
          f"trades {len(tr_in3)} in-sample -> {len(tr3b)} out of sample")
    if not ks:
        fails.append("the walk-forward evaluated no closes at all")
    else:
        if ks[-1] < 2.0:
            fails.append(f"the walk-forward never learned the model was "
                         f"overconfident: k ended at {ks[-1]:.2f} against a "
                         "planted 4.00")
        # The RIGHT response to a model that cannot tell certainty from noise
        # is to stop claiming certainty -- so the trade count must collapse.
        # A recalibration that kept trading at the same rate would not have
        # learned anything.
        if len(tr3b) >= 0.5 * len(tr_in3):
            fails.append(f"recalibration barely reduced the trading "
                         f"({len(tr_in3)} -> {len(tr3b)}); an overconfident "
                         "model must stop calling outcomes decided")
        if tr3b:
            m3b = mean(t["pnl"] for t in tr3b)
            tot_in = sm3["mean"] * len(tr_in3)
            tot_oos = m3b * len(tr3b)
            print(f"    mean {sm3['mean']:+.2f}c on {len(tr_in3)} -> "
                  f"{m3b:+.2f}c on {len(tr3b)}")
            print(f"    TOTAL damage {tot_in:+.0f}c -> {tot_oos:+.0f}c")
            # TOTAL, not the mean. A single flip is -95c, so the mean over 13
            # trades and the mean over 96 are not the same statistic -- the
            # first version of this assertion compared them and failed a
            # recalibration that had just cut the losses by two thirds. What
            # a working recalibration buys is FEWER BAD TRADES, and the money
            # lost is what measures that.
            if tot_oos < tot_in:
                fails.append(f"recalibrating lost MORE in total "
                             f"({tot_in:+.0f}c -> {tot_oos:+.0f}c)")

    # ---- 3c. it must NOT break the honest world --------------------------
    print("\n  And on the world where the model was told the truth, the")
    print("  recalibration must find k near 1 and leave the harvest alone.")
    trh, kph = walk_forward(rows, floor=0.5, warmup=60, refit_every=5)
    ksh = [k for _, k in kph]
    if ksh:
        smh = summarise(trh)
        print(f"    k {ksh[0]:.2f} -> {ksh[-1]:.2f} (truth 1.00), "
              f"{len(trh)} trades, realised "
              f"{smh['mean'] if smh else float('nan'):+.2f}c")
        if ksh[-1] > 2.5:
            fails.append(f"on a correctly-specified model the fit inflated "
                         f"sigma to {ksh[-1]:.2f}x and threw the edge away")
        if smh and smh["mean"] < 0:
            fails.append("recalibration turned a real harvest negative")
    else:
        fails.append("the walk-forward took no trades on the honest world")

    # ---- 3d. the portfolio path must run, and must show the correlation --
    # This exists because `t_crit` reached a commit UNDEFINED: nothing in the
    # self-test ever called run_portfolio, so the whole branch was unproven
    # code shipped next to proven code. A path with no test is not tested by
    # the tests beside it.
    print("\n  Every market at every close, not one per close. Twelve")
    print("  correlated coins are twelve times the money AND twelve times")
    print("  the loss on the close that goes wrong.")
    qm, ixm, mkm, s2im, sigm = _world(200, sigma_true=8.0, book="stale",
                                      seed=17, coins=6, rho=0.85)
    rowsm = scan(qm, ixm, mkm, s2im, sigm, tau_max=TAU_MAX)
    trm = _walk_markets(rowsm, floor=0.5, warmup=60, refit_every=5)
    p1 = portfolio(walk_forward(rowsm, floor=0.5, warmup=60,
                                refit_every=5)[0], "one per close")
    pa = portfolio(trm, "every market")
    if pa is None:
        fails.append("the portfolio path produced nothing on a world that "
                     "harvests -- it is untested code")
    else:
        print(f"    one/close  {p1['trades'] if p1 else 0} trades, per close "
              f"{p1['per_close'] if p1 else 0:+.2f}c")
        print(f"    every mkt  {pa['trades']} trades over {pa['G']} closes "
              f"({pa['width']:.1f}/close), per close {pa['per_close']:+.2f}c, "
              f"worst {pa['worst']:+.1f}c")
        if pa["trades"] < (p1["trades"] if p1 else 0):
            fails.append("taking every market produced FEWER trades than "
                         "taking one per close")
        if pa["width"] < 2.0:
            fails.append(f"six coins share every close in this fixture but "
                         f"the portfolio view found only {pa['width']:.1f} "
                         "per close -- it is not seeing the other markets")
        # THE WHOLE POINT, AND IT IS A TESTABLE CLAIM. If the coins were
        # independent, holding w of them would scale the per-close spread by
        # sqrt(w). Because they are correlated it scales by nearly w. That
        # difference is the entire distinction between diversification and
        # leverage, and asserting it is what stops this table being a
        # comforting sentence with nothing behind it.
        if p1 and p1["sd"] > 0:
            ratio = pa["sd"] / p1["sd"]
            indep = math.sqrt(pa["width"])
            print(f"    spread per close scales {ratio:.1f}x on "
                  f"{pa['width']:.1f} coins  (independent would be "
                  f"{indep:.1f}x)")
            if ratio < indep * 1.25:
                fails.append(f"per-close spread scaled only {ratio:.1f}x on "
                             f"{pa['width']:.1f} correlated coins, barely "
                             f"above the {indep:.1f}x of independence -- the "
                             "fixture is not correlated, so the leverage "
                             "warning this table gives is untested")

    # ---- 4. the flip is priced into the claim ----------------------------
    print("\n  In the harvested world the claimed edge must already net the")
    print("  flip probability: |claimed - realised| within the fair band's")
    print("  own width (checked in test 1). Flip accounting:")
    fl = flips(tr)
    print(f"    {len(fl)} flips in {len(tr)} trades "
          f"({100.0 * len(fl) / max(1, len(tr)):.1f}%); "
          f"model said <= {100 * (1 - PIN):.0f}% per trade")
    if len(fl) > (1 - PIN) * len(tr) * 3 + 5:
        fails.append(f"{len(fl)} flips in {len(tr)} trades -- far beyond "
                     "the model's stated tail; fair is overconfident even "
                     "with the TRUE sigma")

    # ==================================================================
    # MUTATION GUARDS. Added 2026-09-06 after mutation testing planted 9
    # deliberately wrong estimators and this self-test caught only 3. Each
    # block fails against one named survivor. CLAUDE.md: "the self-test is
    # the deliverable; the estimator is the easy part."
    # ==================================================================

    # M1 -- SURVIVOR: "fee_cents returns 0.0" and "fee removed on the YES
    # leg". pin's edge is fee-NETTED, so a silent zero fee inflates every
    # number in the report and nothing complained.
    print("\n  MUTATION GUARD 1 -- fees must exist, at 0.07*p*(1-p), and")
    print("  must actually reach the realised P&L.")
    f50, f96 = fee_cents(0.50), fee_cents(0.96)
    print(f"    fee_cents(0.50) = {f50:.4f}c   fee_cents(0.96) = {f96:.4f}c")
    if abs(f50 - 0.07 * 0.50 * 0.50 * 100.0) > 1e-9:
        fails.append(f"fee_cents(0.50) is {f50:.4f}c, not "
                     f"{0.07*0.25*100:.4f}c -- the fee curve is wrong")
    if abs(f96 - 0.07 * 0.96 * 0.04 * 100.0) > 1e-9:
        fails.append(f"fee_cents(0.96) is {f96:.4f}c -- not 0.07*p*(1-p)")
    gross = mean(100.0 * (t["won"] - t["entry"]) if t["side"] == "yes"
                 else 100.0 * ((1.0 - t["won"]) - (1.0 - t["entry"]))
                 for t in tr)
    net = mean(t["pnl"] for t in tr)
    print(f"    fixture gross {gross:+.3f}c   net {net:+.3f}c   "
          f"fee drag {gross - net:+.4f}c")
    if gross - net < 1e-6:
        fails.append("realised P&L shows NO fee drag -- pnl is gross, so "
                     "every edge in the report is overstated by the fee")

    # M2 -- SURVIVOR: "sd scaled by 0.25", i.e. the MDE understated 4x, so an
    # underpowered cell prints as decisive. CLAUDE.md: "no effect and no
    # power are different results."
    print("\n  MUTATION GUARD 2 -- the MDE must equal 3*sd/sqrt(n) by hand.")
    sd_h = pstdev([t["pnl"] for t in tr])
    hand = 3.0 * sd_h / math.sqrt(len(tr))
    got = mde(tr)
    print(f"    n={len(tr)}  sd={sd_h:.3f}c  by hand {hand:.4f}c  "
          f"mde() {got:.4f}c")
    if abs(hand - got) > 1e-6:
        fails.append(f"mde() reports {got:.4f}c but 3*sd/sqrt(n) is "
                     f"{hand:.4f}c -- the power arithmetic is wrong")

    # M3 -- SURVIVOR: "null band widened to infinity". A band nothing can
    # fall outside is decorative, and every verdict in block() reads it.
    print("\n  MUTATION GUARD 3 -- the null must be a band, not the real line.")
    nbg = redraw_null(tr, reps=400, using="mid")
    wg = nbg["hi"] - nbg["lo"]
    print(f"    mid-null [{nbg['lo']:+.2f}, {nbg['hi']:+.2f}]  width {wg:.2f}c")
    if not (0.0 < wg < 60.0):
        fails.append(f"mid-null width is {wg:.1f}c -- a null nothing can "
                     "fall outside is not a null")

    # M4 -- SURVIVOR, AND THE MOST IMPORTANT ONE: "walk_forward replaced by
    # in-sample evaluate". The out-of-sample property IS the result, and
    # nothing tested it. The property is exactly testable with no randomness:
    # the k applied at close i must depend only on closes STRICTLY earlier,
    # so truncating the input at close i must leave that k bit-identical.
    #
    # A previous attempt at this scrambled future outcomes and compared the
    # first 20 refits -- but with warmup=60 and refit_every=5 the later
    # refits legitimately consume the scrambled region, and the test reported
    # LOOK-AHEAD against correct code. Truncation has no such ambiguity.
    print("\n  MUTATION GUARD 4 -- walk_forward must not see the future.")
    ftr, fkp = walk_forward(rows3, floor=0.5, warmup=60, refit_every=5)
    kmap_g = {c: k for c, k in fkp}
    cl_g = sorted({r["close"] for r in rows3})
    badg = testedg = 0
    for idxg in range(65, min(len(cl_g), 240), 20):
        cig = cl_g[idxg]
        if cig not in kmap_g:
            continue
        _tg, kpg = walk_forward([r for r in rows3 if r["close"] <= cig],
                                floor=0.5, warmup=60, refit_every=5)
        kmg = {c: k for c, k in kpg}
        if cig not in kmg:
            continue
        testedg += 1
        if abs(kmg[cig] - kmap_g[cig]) > 1e-12:
            badg += 1
    print(f"    truncation test: {testedg} closes checked, {badg} whose "
          f"refitted k moved when only FUTURE closes were removed")
    if testedg == 0:
        fails.append("the walk-forward truncation guard checked nothing -- "
                     "it is not guarding anything")
    if badg:
        fails.append(f"LOOK-AHEAD: {badg} of {testedg} refitted k values "
                     "changed when only future closes were removed")

    print()
    if fails:
        print("=" * 78)
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   - " + f)
        print("=" * 78)
        return False
    print("=" * 78)
    print("SELF-TEST PASSED -- collects from a sleeping book, stays silent")
    print("against an honest one, and flags its own overconfidence instead")
    print("of billing it as edge.")
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

    from replay import load_quotes, load_markets, load_index, SERIES_TO_INDEX
    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    quotes = load_quotes(a.data)
    if not quotes:
        print("\n  no quotes -- nothing to analyse")
        return
    markets = load_markets(a.out)
    if not markets:
        print("\n  *** NO SETTLED MARKETS -- nothing to analyse")
        return
    index = load_index(a.data)
    if not index:
        print("\n  no cfbenchmarks_value -- nothing to analyse")
        return

    # sigma per MARKET from the window strictly before the endgame, falling
    # back to a pooled per-series value. In this cell sigma barely matters --
    # that is the premise -- and the self-test's trap fixture is the check
    # that "barely" is not quietly "not at all".
    sigma_by_market, pooled_acc = {}, defaultdict(list)
    for tk, m in markets.items():
        s = m.get("series") or tk.split("-")[0]
        ticks = index.get(SERIES_TO_INDEX.get(s))
        close = m.get("close")
        if not ticks or not close:
            continue
        sg = sigma_from(ticks, int(close) - 900, int(close) - TAU_MAX - 10)
        if sg:
            sigma_by_market[tk] = sg
            pooled_acc[s].append(sg)
    pooled = {s: sorted(v)[len(v) // 2] for s, v in pooled_acc.items() if v}
    print(f"  per-market sigma for {len(sigma_by_market):,} markets, "
          f"pooled fallback for {len(pooled)} series")

    rows = scan(quotes, index, markets, SERIES_TO_INDEX, pooled,
                tau_max=TAU_MAX, sigma_by_market=sigma_by_market)
    if not rows:
        print("\n  nothing to analyse -- no endgame quote-seconds survived")
        return
    print("\n" + "=" * 78)
    print("THE PINNED ENDGAME -- quotes on the wrong side of a decided")
    print("outcome, taken at the earliest qualifying second, one per close")
    print("=" * 78)
    run_cells(rows)
    run_oos(rows)
    run_portfolio(rows)
    print("\n  Read the flags, not the means. 'Below the fair band' says our")
    print("  tail probability was wrong and the edge was fiction. Only a")
    print("  cell that beats the mid-null while staying inside its fair")
    print("  band is a strategy.")


if __name__ == "__main__":
    main()
