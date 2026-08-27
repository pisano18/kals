#!/usr/bin/env python3
"""endgame.py -- the LAST sixty seconds. The mirror of openwindow.py.

    python research/endgame.py --selftest
    python research/endgame.py --data ./kalshi_data --out ./fulltape

WHY THIS REGION AND NOT ANOTHER

Settlement is the mean of sixty discrete one-second index prints ending at the
close. So with tau seconds left, sixty minus tau of those prints have ALREADY
HAPPENED. They are locked, we recorded them, and they cannot change. Only the
remaining tau are random.

That makes the exact variance collapse in a way no smooth approximation
follows:

      tau     sd/sigma    naive sqrt(tau)   ratio     sqrt(tau-39.5)   ratio
      900      29.334        30.000         1.023        29.334        1.000
      200      12.669        14.142         1.116        12.669        1.000
       60       4.528         7.746         1.711         4.528        1.000
       30       1.621         5.477         3.380         0.000        0.000
       10       0.327         3.162         9.670         0.000        0.000
        1       0.017         1.000        60.000         0.000        0.002

Two things fall out of that table:

1. `sqrt(tau - 39.5)` is exact to four decimals above 60s and then collapses
   to zero, while the truth does not. Anyone using it inside the last minute
   is dividing by approximately nothing.
2. Naive `sqrt(tau)` is 1.7x too large at 60s, 3.4x at 30s, 9.7x at 10s. A
   quote built on it carries a sigma that wrong, which pins its price far too
   close to 50c exactly when the truth is going deterministic.

So the endgame is the one region where a pricing-model error is both LARGE and
UNAMBIGUOUS -- and where fair value barely depends on sigma at all, because
most of the answer is already locked in prints we have on disk. That makes
this close to the only measurement in this project that does not rest on a
volatility estimate.

WHY IT MIGHT STILL BE NOTHING

It is also the most obvious place to look, which is a reason to expect it to
be efficient, and liquidity thins into the close so there may be nothing to
trade against. Both are measured here rather than assumed: the report gives
quote availability per tau bucket before it gives any edge.

STATUS: NOT FINISHED. ITS SELF-TEST FAILS AND IT IS NOT WIRED INTO go.py.

    Part 1 -- the variance table -- is derived, exact, and verified against
    the closed form. It stands on its own and is the reason this file exists.

    Part 2 does not yet work. The self-test currently reports:

      * a correctly-priced book yields ZERO qualifying trades  (right)
      * a punched index tape yields zero                        (right)
      * a book pricing sqrt(tau-39.5) is found, +19.6c t=6.6    (right)
      * a book pricing sqrt(tau) is found at |t| = 7.7 but the
        strategy LOSES 22.6c against it                         (WRONG)

    The last line is a real defect, not a tolerance to widen. If our model is
    right and the book's is wrong, we must make money; losing means the
    fixture, the entry rule, or both are still wrong. Do not use any number
    from part 2, and do not register this stage, until that row is positive.

    Two things were already learned the expensive way and are worth keeping
    whatever happens to the rest:

    1. Taking the LARGEST model-vs-market disagreement in a window is a
       look-ahead. It finds where the MODEL is most wrong, not the market. On
       a tape whose true edge was zero it produced 16 trades claiming 0.29c
       and realising -49.5c at t = -3.3. `evaluate(rule="first")` -- the
       earliest second clearing the fee -- is the only rule of the two a live
       trader could follow.

    2. The first fixture clamped quotes to [1c, 99c] and then asserted that
       the book was "correctly priced". It was not: the exchange cannot quote
       below 1c, so in the endgame -- where true fair goes to 0 or 1 --
       selling a 1c contract genuinely worth 0.1c is a 0.9c edge against a
       0.07c fee. Every assertion resting on that fixture was meaningless, and
       a whole debugging pass went into the estimator before the fixture
       turned out to be the thing that was wrong. That clamp effect is itself
       a candidate finding and deserves its own measurement.

NOTHING HERE PLACES AN ORDER.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from statistics import NormalDist, mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import var_factor, N_AVG                        # noqa: E402
from settlewin import partial                               # noqa: E402
from tdist import p_two_sided                               # noqa: E402

ND = NormalDist()
FEE_K = 0.07
TAUS = [(1, 5), (5, 10), (10, 20), (20, 30), (30, 45), (45, 60), (60, 120)]


def fee_cents(p):
    p = min(max(p, 0.0), 1.0)
    return 100.0 * FEE_K * p * (1.0 - p)


def fair(ticks, close_s, now_s, strike, sigma):
    """Model fair value with the locked prints already counted, or None."""
    part = partial(ticks, close_s, now_s)
    if part is None:
        return None
    locked, r = part
    spot = ticks.get(now_s)
    if spot is None:
        return None
    mu = (locked + r * spot) / N_AVG
    tau = close_s - now_s
    vf = var_factor(int(tau), [1.0])
    sd = sigma * math.sqrt(vf)
    if sd <= 0:
        # Nothing random is left: the outcome is already determined.
        return 1.0 if mu > strike else 0.0
    return ND.cdf((mu - strike) / sd)


def scan(quotes, index, markets, series_to_index, sigma_by_series,
         tau_max=120, edge_floor=0.0):
    """One row per (market, second) inside the endgame with a usable quote."""
    rows = []
    for tk, q in quotes.items():
        m = markets.get(tk)
        if not m:
            continue
        s = m.get("series") or tk.split("-")[0]
        ticks = index.get(series_to_index.get(s))
        strike, close_s = m.get("strike"), m.get("close")
        sig = sigma_by_series.get(s)
        if not ticks or not strike or not close_s or not sig:
            continue
        close_s = int(close_s)
        settle = m.get("settle")
        for (t, bid, ask, _bs, _as) in q:
            tau = close_s - t
            if not (1 <= tau <= tau_max):
                continue
            f = fair(ticks, close_s, t, strike, sig)
            if f is None:
                continue
            mid = (bid + ask) / 2.0
            rows.append({"tk": tk, "series": s, "close": close_s, "tau": tau,
                         "fair": f, "mid": mid, "bid": bid, "ask": ask,
                         "settle": settle, "strike": strike})
    return rows


def evaluate(rows, edge_floor=0.0, rule="first"):
    """Settlement P&L, one trade per market, taking the book only when the
    model says it is wrong by more than the fee.

    One per market is not a convenience. Every fill inside a single window
    settles on the SAME outcome, so a hundred fills there carry the
    information of one -- and reporting them as a hundred is the fastest way
    to manufacture significance in this project.

    WHICH one per market is the part that took a failed self-test to get
    right. `rule="best"` takes the largest disagreement in the window, which
    is what I wrote first. It is a look-ahead: across 19,000 quote-seconds
    where model and market agree to 0.25c on average, the maximum
    disagreement is not where the MARKET is most wrong, it is where the MODEL
    is. On a tape whose true edge is exactly zero it produced 16 trades
    claiming 0.29c and realising -49.5c, at t = -3.3.

    `rule="first"` takes the earliest second at which the edge clears the fee
    -- which is also the only one of the two a live trader could follow,
    since it needs no knowledge of quotes that have not happened yet.
    """
    best = {}
    for r in sorted(rows, key=lambda x: (x["close"], -x["tau"])):
        if r["settle"] is None:
            continue
        f, bid, ask = r["fair"], r["bid"], r["ask"]
        buy = 100.0 * f - 100.0 * ask - fee_cents(ask)
        sell = 100.0 * bid - 100.0 * f - fee_cents(1.0 - bid)
        if buy >= sell:
            edge, side, entry = buy, "yes", ask
        else:
            edge, side, entry = sell, "no", bid
        if edge <= edge_floor:
            continue
        cur = {"edge": edge, "side": side, "entry": entry, "tau": r["tau"],
               "close": r["close"], "settle": r["settle"], "fair": f}
        prev = best.get(r["close"])
        if prev is None:
            best[r["close"]] = cur
        elif rule == "best" and edge > prev["edge"]:
            best[r["close"]] = cur
    out = []
    for b in best.values():
        won = 1.0 if b["settle"] else 0.0
        if b["side"] == "yes":
            pnl = 100.0 * (won - b["entry"]) - fee_cents(b["entry"])
        else:
            pnl = 100.0 * ((1.0 - won) - (1.0 - b["entry"])) \
                - fee_cents(1.0 - b["entry"])
        out.append(dict(b, pnl=pnl))
    return out


def summarise(trades, label=""):
    if len(trades) < 10:
        return None
    p = [t["pnl"] for t in trades]
    m, sd = mean(p), pstdev(p)
    se = sd / math.sqrt(len(p)) if sd > 0 else float("inf")
    return {"label": label, "n": len(p), "mean": m, "se": se,
            "t": m / se if se > 0 else 0.0, "df": len(p) - 1,
            "exp_edge": mean(t["edge"] for t in trades)}


def redraw_null(trades, reps=2000, seed=20260827):
    """Outcome-redraw: keep every trade, resettle each market by its OWN model
    probability. If the model is calibrated this has mean zero, and anything
    the strategy earns above it is not coming from the model being confident.
    """
    if not trades:
        return None
    rng = random.Random(seed)
    out = []
    for _ in range(reps):
        tot = 0.0
        for t in trades:
            won = 1.0 if rng.random() < t["fair"] else 0.0
            if t["side"] == "yes":
                tot += 100.0 * (won - t["entry"]) - fee_cents(t["entry"])
            else:
                tot += 100.0 * ((1.0 - won) - (1.0 - t["entry"])) \
                    - fee_cents(1.0 - t["entry"])
        out.append(tot / len(trades))
    out.sort()
    return {"lo": out[int(0.025 * reps)], "hi": out[int(0.975 * reps)],
            "mean": mean(out)}


# ===========================================================================
def analytic():
    print("=" * 78)
    print("PART 1  WHY THE LAST MINUTE -- the exact variance collapses")
    print("=" * 78)
    print("  Settlement averages 60 one-second prints. With tau left, 60-tau")
    print("  of them are LOCKED -- already printed, already recorded.\n")
    print(f"  {'tau':>6}{'sd/sigma':>11}{'sqrt(tau)':>11}{'ratio':>8}"
          f"{'sqrt(t-39.5)':>14}{'ratio':>8}{'locked':>9}")
    for tau in (900, 400, 200, 120, 90, 60, 45, 30, 20, 10, 5, 2, 1):
        vf = var_factor(tau, [1.0])
        sd = math.sqrt(vf)
        naive = math.sqrt(tau)
        lin = math.sqrt(max(tau - 39.5, 0.0))
        locked = max(0, N_AVG - tau)
        print(f"  {tau:>6}{sd:>11.4f}{naive:>11.4f}{naive/sd:>8.3f}"
              f"{lin:>14.4f}{(lin/sd if sd > 0 else 0):>8.3f}"
              f"{locked:>9}")
    print("\n  A quote built on sqrt(tau) carries a sigma 1.7x too large at")
    print("  60s and 9.7x at 10s, which pins its price toward 50c exactly")
    print("  when the truth is going deterministic. sqrt(tau-39.5) is exact")
    print("  above 60s and then divides by approximately nothing.")


# ===========================================================================
def selftest():
    print("=" * 78)
    print("SELF-TEST -- against known answers")
    print("=" * 78)
    fails = []
    analytic()

    # ---- the ratios above must be the closed form, not a table I typed
    for tau, want in ((60, 4.5280), (30, 1.6206), (10, 0.3270)):
        got = math.sqrt(var_factor(tau, [1.0]))
        if abs(got - want) > 5e-4:
            fails.append(f"sd/sigma at tau={tau} is {got:.4f}, not {want}")

    SIG, S0, CLOSE = 6.0, 80000.0, 1_760_000_000

    def world(n, seed, model="exact", gap=0, quote_noise=0.0):
        """n markets, each with a full index tape and a book that prices with
        `model`. The TRUE settlement is computed from the same tape, so the
        only thing that varies is what the book believes."""
        rng = random.Random(seed)
        quotes, index, markets = {}, {"BRTI": {}}, {}
        ticks = index["BRTI"]
        for w in range(n):
            close_s = CLOSE + w * 900
            tk = f"E{w:04d}"
            px = S0
            for t in range(close_s - 900, close_s + 1):
                px += rng.gauss(0, SIG)
                ticks[t] = px
            seg = [ticks[t] for t in range(close_s - N_AVG + 1, close_s + 1)]
            settle = sum(seg) / N_AVG
            # strike offset so the endgame is genuinely in doubt sometimes
            strike = settle + rng.gauss(0, 3.0)
            markets[tk] = {"series": "KXBTC15M", "strike": strike,
                           "close": close_s, "settle": settle > strike}
            ser = []
            for t in range(close_s - 130, close_s):
                tau = close_s - t
                if gap and (t % gap == 0):
                    continue                      # a hole in the QUOTE tape
                part = partial(ticks, close_s, t)
                if part is None:
                    continue
                locked, r = part
                mu = (locked + r * ticks[t]) / N_AVG
                if model == "exact":
                    sd = SIG * math.sqrt(var_factor(tau, [1.0]))
                elif model == "naive":
                    sd = SIG * math.sqrt(tau)     # the mistake
                else:
                    sd = SIG * math.sqrt(max(tau - 39.5, 1e-9))
                p = ND.cdf((mu - strike) / sd) if sd > 0 else \
                    (1.0 if mu > strike else 0.0)
                # Skip seconds where the truth is outside the quotable range.
                # The exchange cannot quote below 1c or above 99c, so there
                # the book is REALLY mispriced -- selling a 1c contract worth
                # 0.1c is a genuine 0.9c edge against a 0.07c fee. That is a
                # separate finding (see the CLAMP block below), and leaving it
                # in this fixture means "correctly priced" is a lie and every
                # assertion built on it is meaningless. It cost a whole
                # debugging pass to see that the fixture, not the estimator,
                # was the thing that was wrong.
                if not (0.02 <= p <= 0.98):
                    continue
                p = min(max(p + rng.gauss(0, quote_noise), 0.01), 0.99)
                p = round(p * 100) / 100.0        # the 1c tick is real
                ser.append((t, max(p - 0.005, 0.0), min(p + 0.005, 1.0),
                            100.0, 100.0))
            quotes[tk] = ser
        return quotes, index, markets

    print("\n  A book pricing the EXACT model must yield nothing. One pricing")
    print("  sqrt(tau), or sqrt(tau-39.5) inside the last minute, must be")
    print("  visibly wrong -- and the size is the point, not just the sign.")
    print(f"\n  {'book prices with':>22}{'trades':>8}{'mean P&L':>11}"
          f"{'t':>7}{'null 95%':>20}   verdict")
    got = {}
    for model in ("exact", "naive", "linear"):
        q, idx, mk = world(300, seed=5, model=model)
        rows = scan(q, idx, mk, {"KXBTC15M": "BRTI"}, {"KXBTC15M": SIG})
        tr = evaluate(rows)
        sm = summarise(tr, model)
        nl = redraw_null(tr, reps=600)
        got[model] = sm
        if not sm:
            print(f"  {model:>22}{len(tr):>8}   too few trades")
            continue
        print(f"  {model:>22}{sm['n']:>8}{sm['mean']:>10.2f}c{sm['t']:>7.1f}"
              f"   [{nl['lo']:>6.2f},{nl['hi']:>6.2f}]   "
              + ("finds it" if sm["t"] > 3 else "nothing"))
    if got["exact"] and got["exact"]["t"] > 3:
        fails.append(f"found an edge of {got['exact']['mean']:.2f}c against a "
                     "book pricing the EXACT model -- the estimator is "
                     "manufacturing it")
    for m in ("naive", "linear"):
        if not got[m] or got[m]["t"] < 3:
            fails.append(f"missed a book pricing with {m} scaling, which is "
                         "wrong by up to 9.7x inside the last ten seconds")

    # ---- the bug settlewin.py was written to kill must stay dead ----------
    print("\n  THE GAP TRAP. settlewin.py exists because four copies of this")
    print("  calculation summed the ticks PRESENT and divided by the count")
    print("  that SHOULD be present, putting mu thousands of dollars off and")
    print("  pinning fair at 0 or 1. A missing index second must produce NO")
    print("  trade, never a confident one.")
    q, idx, mk = world(200, seed=9, model="exact")
    ticks = idx["BRTI"]
    holed = 0
    for tk, m in mk.items():
        c = int(m["close"])
        for t in range(c - 25, c - 15):           # punch a hole mid-window
            if t in ticks:
                del ticks[t]
                holed += 1
    rows = scan(q, idx, mk, {"KXBTC15M": "BRTI"}, {"KXBTC15M": SIG})
    bad = [r for r in rows if r["tau"] <= 25 and (r["fair"] in (0.0, 1.0))]
    tr = evaluate(rows)
    sm = summarise(tr, "holed")
    print(f"  removed {holed} index seconds -> {len(rows)} usable rows, "
          f"{len(bad)} pinned to 0/1, "
          f"P&L {sm['mean']:.2f}c t={sm['t']:.1f}" if sm else
          f"  removed {holed} index seconds -> {len(rows)} usable rows, "
          f"too few trades")
    # TWO-sided. A confident LOSS on a tape whose truth is zero is the same
    # failure as a confident gain, and the one-sided version of this check is
    # exactly how the selection bias above passed its first run.
    if sm and abs(sm["t"]) > 3:
        fails.append(f"a punched index tape produced {sm['mean']:.2f}c at "
                     f"t={sm['t']:.1f} against a true edge of zero")

    # ---- the selection trap, pinned rather than merely avoided -----------
    print("\n  SELECTION. Picking the LARGEST disagreement in each window is")
    print("  a look-ahead: it finds where the MODEL is most wrong, not the")
    print("  market. Same rows, same correctly-priced book, two rules.")
    q, idx, mk = world(300, seed=21, model="exact")
    rows_s = scan(q, idx, mk, {"KXBTC15M": "BRTI"}, {"KXBTC15M": SIG})
    print(f"\n  {'rule':>28}{'trades':>8}{'claimed':>10}{'realised':>11}"
          f"{'t':>7}")
    res = {}
    for rule, label in (("first", "first to clear the fee"),
                        ("best", "largest disagreement")):
        tr_ = evaluate(rows_s, rule=rule)
        sm_ = summarise(tr_, rule)
        res[rule] = sm_
        if sm_:
            print(f"  {label:>28}{sm_['n']:>8}{sm_['exp_edge']:>9.2f}c"
                  f"{sm_['mean']:>10.2f}c{sm_['t']:>7.1f}")
        else:
            print(f"  {label:>28}{len(tr_):>8}   too few")
    if res["first"] and abs(res["first"]["t"]) > 3:
        fails.append(f"the first-to-clear rule found {res['first']['mean']:.2f}c "
                     f"at t={res['first']['t']:.1f} against a correctly-priced "
                     "book")
    if res["best"] and abs(res["best"]["t"]) <= 3:
        fails.append("the largest-disagreement rule no longer shows the "
                     "selection bias, so this check has stopped pinning "
                     "anything -- either the fixture changed or evaluate did")

    # ---- one trade per market, not per fill ------------------------------
    q, idx, mk = world(120, seed=13, model="naive")
    rows = scan(q, idx, mk, {"KXBTC15M": "BRTI"}, {"KXBTC15M": SIG})
    tr = evaluate(rows)
    closes = {t["close"] for t in tr}
    print(f"\n  clustering: {len(rows):,} quote-seconds -> {len(tr)} trades "
          f"over {len(closes)} distinct closes")
    if len(tr) != len(closes):
        fails.append(f"{len(tr)} trades over {len(closes)} closes -- every "
                     "fill in one window settles on the SAME outcome, so more "
                     "than one per close is fake n")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- silent against a correctly-priced book, finds")
    print("both wrong scalings, refuses to trade a punched index tape, and")
    print("counts one trade per close rather than one per fill.")
    return True


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--tau-max", type=int, default=120)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    analytic()
    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    from replay import (load_quotes, load_markets, load_index,
                        SERIES_TO_INDEX)       # NOT engine -- it lives here
    quotes = load_quotes(a.data)
    if not quotes:
        print("\n  no quotes -- nothing to measure. Run doctor.py.")
        return
    markets = load_markets(a.out)
    index = load_index(a.data)

    # sigma per series from the index itself, over the recorded span
    sig = {}
    for s, iid in SERIES_TO_INDEX.items():
        ticks = index.get(iid) or {}
        ts = sorted(ticks)
        if len(ts) < 600:
            continue
        d = [ticks[ts[i + 1]] - ticks[ts[i]] for i in range(len(ts) - 1)
             if ts[i + 1] - ts[i] == 1]
        if len(d) > 300:
            sig[s] = pstdev(d)
    if not sig:
        print("\n  no index feed -- fair value is not computable.")
        return
    print(f"\n  sigma per series (1-second, from our own index tape):")
    for s, v in sorted(sig.items()):
        print(f"    {s:<16}{v:>12.4f}")

    rows = scan(quotes, index, markets, SERIES_TO_INDEX, sig,
                tau_max=a.tau_max)
    print(f"\n  {len(rows):,} quote-seconds inside tau <= {a.tau_max}")
    if not rows:
        print("  Nothing quoted in the endgame. That is itself the finding:")
        print("  there is no book to trade against in the last two minutes.")
        return

    print(f"\n  {'tau':>10}{'quote-secs':>12}{'markets':>9}"
          f"{'mean|fair-mid|':>16}{'median spread':>15}")
    for lo, hi in TAUS:
        sel = [r for r in rows if lo <= r["tau"] < hi]
        if not sel:
            print(f"  {f'{lo}-{hi}s':>10}{0:>12}")
            continue
        mk = len({r["close"] for r in sel})
        gap = mean(abs(r["fair"] - r["mid"]) for r in sel) * 100.0
        sp = sorted((r["ask"] - r["bid"]) * 100.0 for r in sel)
        print(f"  {f'{lo}-{hi}s':>10}{len(sel):>12,}{mk:>9}{gap:>15.2f}c"
              f"{sp[len(sp)//2]:>14.2f}c")
    print("\n  Read the quote-seconds column first. An edge in a bucket with")
    print("  no quotes is not an edge.")

    trades = evaluate(rows)
    sm = summarise(trades, "endgame")
    print("\n" + "=" * 78)
    print("SETTLEMENT P&L  --  one trade per close, taking the book only when")
    print("the model says it is wrong by more than the fee")
    print("=" * 78)
    if not sm:
        print("  fewer than 10 qualifying trades -- no information either way.")
        return
    nl = redraw_null(trades)
    print(f"  trades (= distinct closes)   {sm['n']}")
    print(f"  mean expected edge at entry  {sm['exp_edge']:.2f}c")
    print(f"  mean realised P&L            {sm['mean']:.2f}c")
    print(f"  t / p                        {sm['t']:.2f} / "
          f"{p_two_sided(abs(sm['t']), sm['df']):.4f}")
    print(f"  outcome-redraw null 95%      [{nl['lo']:.2f}, {nl['hi']:.2f}]c")
    inside = nl["lo"] <= sm["mean"] <= nl["hi"]
    print(f"\n  {'INSIDE the null -- nothing here' if inside else 'OUTSIDE the null'}")
    print("  Expected edge far above realised P&L means the model is")
    print("  confident and wrong, which is worse than no edge at all.")


if __name__ == "__main__":
    main()
