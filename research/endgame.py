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

STATUS: PART 1 EXACT AND VERIFIED. PART 2 NOW PASSES ITS SELF-TEST.

    Part 1 -- the variance table -- is derived, exact, and verified against
    the closed form. It stands on its own and is the reason this file exists.

    Part 2 failed for four months of calendar time on a defect that was
    entirely in the TEST WORLD, not the estimator. It is worth writing down
    because it is the third time in this project that a fixture, not an
    estimator, was the thing that was wrong.

    THE FIRST BUG -- a look-ahead in the strike.  The fixture drew

        strike = settle + gauss(0, 3.0)

    so the strike was a function of the FUTURE settlement value. That makes
    settle - strike = -eps ~ N(0, 3) independently of everything knowable at
    decision time, so the true probability of every market was 50% no matter
    what the tape had done. Measured directly: rows where the model said
    fair = 0.041 won 27.4% of the time and rows where it said 0.959 won 76%.
    A book pricing sqrt(tau) -- pulled toward 50c by a sigma 9.7x too large --
    was therefore CLOSER to the truth than the exact model, and fading it
    correctly lost 22.6c. The estimator was right and the world was lying.

    The fix is the rule the exchange actually uses and that every other
    fixture in this project already used: strike(N+1) == settle(N), i.e. the
    mean of the sixty prints ending at the open. It cannot see the future.

    THE SECOND BUG -- the tape overwrote itself.  Each window reset px = S0
    and wrote ticks over [close-900, close], and close(w) - 900 == close(w-1),
    so every window clobbered the previous window's final print with a value
    from a fresh random walk ~180 dollars away. settle had been computed from
    the ticks BEFORE the clobber; fair() read the ticks AFTER it. Extending
    the strike window to 60s made it worse -- 60 clobbered prints instead of
    one -- which is how it was found. The fixture is now ONE continuous tape
    with windows defined on top of it.

    WHAT THE REPAIRED TEST SHOWS

      book prices with    tau<=120   tau<=60   tau<=30   tau<=15
      exact                 silent    silent    silent    silent
      naive  sqrt(tau)     +3.24c    +7.93c   +11.02c   +12.11c
                          (t=2.0)   (t=4.9)   (t=6.5)   (t=6.4)
      claimed at entry      +1.91c    +5.82c   +12.40c   +14.39c

    Those two rows agree to between 0.8 and 1.3 standard errors in every cell,
    and THAT is the real assertion -- detection alone is cheap. A model that
    claims 5.8c and earns 7.9c is honest; the broken version claimed 1.8c and
    earned -22.6c.

    (Every figure above is printed by the self-test below. They are quoted
    here because a docstring carrying numbers no run produces is a lie that
    gets copied into handoff notes and then into decisions -- which is exactly
    what happened to the earlier version of this table.)

    THREE THINGS THE REPAIRED TEST TAUGHT THAT ARE WORTH KEEPING

    1. A book pricing sqrt(tau - 39.5) is INVISIBLE, and not because the
       estimator is weak. That approximation is exact above 60s and collapses
       to zero below ~40s, which drives its quotes to 0 or 1 -- outside the
       range the exchange can quote at all. Its error region censors itself
       out of the book. A mispricing you cannot be shown is not tradeable.

    2. A POOLED sigma manufactures edge. Give the book each window's own true
       sigma and scan with one pooled sigma per series -- our model is then
       wrong per-window in a mean-zero way, and the true edge is exactly
       zero. It claims +2.5c and realises -4.2c, an overclaim of 6.7c. This
       not hypothetical: it is how implied.py and every other stage estimates
       sigma. main() below therefore estimates sigma from each market's OWN
       path up to the start of the endgame, which is non-anticipating, and
       falls back to the pooled value only when that is too thin.

    3. Taking the LARGEST model-vs-market disagreement in a window is a
       look-ahead -- it finds where the MODEL is most wrong, not the market.
       `evaluate(rule="first")` -- the earliest second clearing the fee -- is
       the only rule of the two a live trader could follow.

    And one that was already paid for once: the first fixture clamped quotes
    to [1c, 99c] and then asserted the book was "correctly priced". It was
    not -- the exchange cannot quote below 1c, so where true fair goes to 0
    or 1, selling a 1c contract genuinely worth 0.1c is a 0.9c edge against a
    0.07c fee. Every assertion resting on that fixture was meaningless. That
    clamp effect is a candidate finding in its own right and still deserves
    its own measurement.

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


def outcome_of(m, strike=None):
    """Did this market settle YES? 1.0 / 0.0, or None if it cannot be told.

    THIS FUNCTION EXISTS BECAUSE OF A BUG THAT SHIPPED. evaluate() used to do

        won = 1.0 if m["settle"] else 0.0

    and `settle` is not the outcome. kalshi_fulltape.py writes

        "settle": float(expiration_value),        # the settled INDEX LEVEL
        "result": 1.0 if v >= k else 0.0          # the outcome

    guarded by `if k and v and c`, so on real data `settle` is ALWAYS a nonzero
    float and that truthiness test returned 1.0 for every market on the tape.
    Every yes-side trade booked a win and every no-side trade booked a loss, so
    the printed realised P&L was a pure function of the yes/no trade mix and
    carried no outcome information at all. The 2026-08-28 run reported
    -21c to -39c at t = -8 on that basis.

    The self-test could not see it: endgame's own fixture wrote
    `"settle": settle > strike`, a bool, which is a schema real data never has.
    replay.py and edge.py both write settle as a PRICE with a separate result,
    so this fixture was the only one in the repo that disagreed with the
    collector. calib.py has carried an outcome_of for the same reason since the
    day `result` turned out to be a float rather than a string.
    """
    r = m.get("result")
    if r is not None and not (isinstance(r, str) and not r.strip()):
        if isinstance(r, bool):
            return 1.0 if r else 0.0
        if isinstance(r, (int, float)):
            return 1.0 if float(r) >= 0.5 else 0.0
        t = str(r).strip().lower()
        if t in ("yes", "y", "true", "1", "1.0", "win"):
            return 1.0
        if t in ("no", "n", "false", "0", "0.0", "loss"):
            return 0.0
        return None
    st, k = m.get("settle"), strike if strike is not None else m.get("strike")
    if st is None or k is None:
        return None
    return 1.0 if float(st) >= float(k) else 0.0


def sane_or_die(trades, label=""):
    """Refuse to report a P&L whose outcomes are degenerate.

    A constant `won` is the signature of reading the wrong field, and it is
    exactly what shipped. Kalshi's 15-minute binaries are near coin flips, so a
    YES rate outside [0.05, 0.95] over hundreds of markets is a parsing bug,
    not a market.
    """
    if len(trades) < 20:
        return True
    rate = mean(t["won"] for t in trades)
    if 0.05 <= rate <= 0.95:
        return True
    print(f"\n  *** REFUSING TO REPORT {label}: the YES rate over "
          f"{len(trades)} settled markets is {rate:.3f}.")
    print("  *** That is a parsing failure, not a market. `settle` is the")
    print("  *** settled index LEVEL; the outcome is `result`. See")
    print("  *** outcome_of() above.")
    return False


# ===========================================================================
# SETTLEMENT ROUNDING -- bug 2, fixed 2026-09-08
# ===========================================================================
# Kalshi does not compare the raw 60-print mean to the strike. It rounds the
# mean to custom_strike.round_digits, writes that as `expiration_value`, and
# settles YES iff expiration_value >= floor_strike. So the threshold the model
# must price against is K - 0.5*10^-d, NOT K.
#
# Measured 2026-09-08 by GET /markets?series_ticker=...&status=settled and
# reading custom_strike.round_digits off the returned records:
#
#     KXBTC15M 2   KXETH15M 2   KXBNB15M 2
#     KXSOL15M 4   KXXRP15M 4   KXZEC15M 4   KXHYPE15M 4   KXNEAR15M 4
#     KXDOGE15M 7
#
# (KXBCH15M, KXADA15M and the rest returned zero settled markets, so they have
# no measured value and get none -- an unmeasured series is priced with no
# adjustment, which is the old behaviour, rather than with a guess.)
#
# THE CONFIRMED CASE: KXETH15M-26SEP071745-45, floor_strike 2492.82. The tape
# mean over [close-60, close-1] is 2492.815833; round(.,2) = 2492.82, Kalshi's
# expiration_value is 2492.82 and result is `yes`. An unrounded model prices
# that market at fair 0.017 -- i.e. it buys NO at 90c and loses 90.91c.
ROUND_DIGITS = {
    "KXBTC15M": 2, "KXETH15M": 2, "KXBNB15M": 2,
    "KXSOL15M": 4, "KXXRP15M": 4, "KXZEC15M": 4,
    "KXHYPE15M": 4, "KXNEAR15M": 4,
    "KXDOGE15M": 7,
}


def _decimals(x):
    """Decimal places in the shortest round-tripping form of x, or None."""
    try:
        s = repr(float(x))
    except (TypeError, ValueError):
        return None
    if "e" in s or "E" in s or "inf" in s or "nan" in s:
        return None
    return len(s.split(".")[1].rstrip("0")) if "." in s else 0


def infer_round_digits(markets, need=20, cap=8):
    """{series: round_digits} read off the settled records themselves.

    `settle` in fulltape/markets.json IS Kalshi's expiration_value, i.e. the
    already-rounded number, so the widest decimal expansion a series ever
    prints is its round_digits. This is preferred over the hardcoded table
    because it is measured on the same tape the backtest scores, and it
    cross-checks the table rather than trusting it.
    """
    seen = {}
    for m in markets.values():
        s = m.get("series")
        d = _decimals(m.get("settle"))
        if not s or d is None or d > cap:
            continue
        a, b = seen.get(s, (0, 0))
        seen[s] = (max(a, d), b + 1)
    return {s: d for s, (d, n) in seen.items() if n >= need}


def round_digits_map(markets, verbose=True):
    """The per-series round_digits the model will use, and where it came from.

    Inference wins where it exists; the measured table fills the rest; a
    series with neither gets no entry and is priced unrounded. Disagreements
    are printed rather than silently resolved.
    """
    inf = infer_round_digits(markets)
    out = dict(ROUND_DIGITS)
    out.update(inf)
    if verbose:
        for s in sorted(set(out) | set(ROUND_DIGITS) | set(inf)):
            tab, got = ROUND_DIGITS.get(s), inf.get(s)
            flag = ""
            if tab is not None and got is not None and tab != got:
                flag = "   *** DISAGREES with the API-measured table ***"
            print(f"    round_digits {s:<14} using {out.get(s)}   "
                  f"(tape {got}, api {tab}){flag}")
    return out


def settle_threshold(strike, round_digits):
    """The raw-mean level at or above which the market settles YES.

    round(x, d) >= K  <=>  x >= K - 0.5*10^-d. With round_digits unknown the
    threshold is the strike itself, which is the pre-2026-09-08 behaviour.
    """
    if round_digits is None:
        return float(strike)
    return float(strike) - 0.5 * (10.0 ** (-int(round_digits)))


def fair(ticks, close_s, now_s, strike, sigma, round_digits=None):
    """Model fair value with the locked prints already counted, or None.

    TWO CORRECTIONS, both measured on this tape on 2026-09-08:

      * the window is [close-60, close-1], so at tau seconds out there are
        tau-1 prints still unknown, not tau. partial() owns the mean; the
        VARIANCE has to be told the same thing or the two halves of this
        function disagree with each other. var_factor's argument is the
        number of unknown one-second increments, and settle_weights(tau-1)
        is exactly right in both regimes -- inside the window it is
        [tau-1..1], and before the window opens the extra flat weight of 60
        it drops is exactly the weight that is no longer there.

      * the settlement is rounded to the strike's precision before it is
        compared, so the threshold is K - 0.5*10^-d. See ROUND_DIGITS.
    """
    part = partial(ticks, close_s, now_s)
    if part is None:
        return None
    locked, r = part
    spot = ticks.get(now_s)
    if spot is None:
        return None
    mu = (locked + r * spot) / N_AVG
    k = settle_threshold(strike, round_digits)
    tau = close_s - now_s
    vf = var_factor(max(0, int(tau) - 1), [1.0])
    sd = sigma * math.sqrt(vf)
    if sd <= 0:
        # Nothing random is left: the outcome is already determined.
        return 1.0 if mu >= k else 0.0
    return ND.cdf((mu - k) / sd)


def scan(quotes, index, markets, series_to_index, sigma_by_series,
         tau_max=120, sigma_by_market=None, round_digits=None):
    """One row per (market, second) inside the endgame with a usable quote.

    `sigma_by_market` overrides the pooled per-series sigma where a market has
    its own non-anticipating estimate. The self-test measures what pooling
    costs: a book quoting each window's true sigma, scanned with one pooled
    sigma, yields a claimed +2.5c that realises -4.2c. Prefer the per-market
    value wherever there is enough tape to form one.
    """
    rows = []
    for tk, q in quotes.items():
        m = markets.get(tk)
        if not m:
            continue
        s = m.get("series") or tk.split("-")[0]
        ticks = index.get(series_to_index.get(s))
        strike, close_s = m.get("strike"), m.get("close")
        sig = (sigma_by_market or {}).get(tk) or sigma_by_series.get(s)
        if not ticks or not strike or not close_s or not sig:
            continue
        close_s = int(close_s)
        settle, result = m.get("settle"), m.get("result")
        # round_digits: the market's own field wins, then the per-series map.
        rd = m.get("round_digits")
        if rd is None and round_digits:
            rd = round_digits.get(s)
        for (t, bid, ask, _bs, _as) in q:
            tau = close_s - t
            if not (1 <= tau <= tau_max):
                continue
            f = fair(ticks, close_s, t, strike, sig, round_digits=rd)
            if f is None:
                continue
            mid = (bid + ask) / 2.0
            rows.append({"tk": tk, "series": s, "close": close_s, "tau": tau,
                         "fair": f, "mid": mid, "bid": bid, "ask": ask,
                         "settle": settle, "strike": strike,
                         "result": result, "rd": rd})
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
        if outcome_of(r, r.get("strike")) is None:
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
        # "tk" carried through so a taker-capacity measurement can ask how
        # many contracts were RESTING at the level this trade decides to
        # hit. Every dollar figure assumed 50 fill; without the ticker that
        # is uncheckable. Additive -- consumers read by key, not position.
        cur = {"edge": edge, "side": side, "entry": entry, "tau": r["tau"],
               "close": r["close"], "settle": r["settle"], "fair": f,
               "strike": r.get("strike"), "result": r.get("result"),
               "mid": r["mid"], "tk": r.get("tk")}
        prev = best.get(r["close"])
        if prev is None:
            best[r["close"]] = cur
        elif rule == "best" and edge > prev["edge"]:
            best[r["close"]] = cur
    out = []
    for b in best.values():
        won = outcome_of(b, b.get("strike"))
        if won is None:
            continue
        b = dict(b, won=won)
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


def redraw_null(trades, reps=2000, seed=20260827, using="fair",
                value=None):
    """Resettle every market from an assumed probability and re-score.

    `using="fair"`  -- the MODEL's probability. NOT a null. Its mean is the
                      claimed edge by construction, because E[won] = fair is
                      exactly what "claimed edge" means. It answers "is the
                      realised P&L consistent with my model being right?"
    `using="mid"`   -- the MARKET's probability. This IS the null: if the book
                      is right, E[won] = mid, and the strategy earns
                      100*(mid - entry) - fee, i.e. it pays the spread and the
                      fee and nothing else.

    The distinction was wrong until 2026-08-29 and the wrongness was in the
    direction that flatters: only the fair-band existed, it was printed under
    the heading "outcome-redraw null", and main() read a result INSIDE it as
    "nothing here". Inside the fair-band means the model is RIGHT. The two
    readings are opposites.
    """
    if not trades:
        return None
    rng = random.Random(seed)
    out = []
    for _ in range(reps):
        tot = 0.0
        for t in trades:
            p_ = t["fair"] if using == "fair" else t.get("mid", t["fair"])
            won = 1.0 if rng.random() < p_ else 0.0
            if t["side"] == "yes":
                tot += 100.0 * (won - t["entry"]) - fee_cents(t["entry"])
            else:
                tot += 100.0 * ((1.0 - won) - (1.0 - t["entry"])) \
                    - fee_cents(1.0 - t["entry"])
        out.append(tot / len(trades))
    out.sort()
    res = {"lo": out[int(0.025 * reps)], "hi": out[int(0.975 * reps)],
           "mean": mean(out)}
    # THE BAND IS DISCRETE. Every row in a pinned cell carries a model
    # probability at 0.98+ or 0.02-, so one simulated re-settlement differs
    # from the next by whole FLIPS and the per-trade mean moves in steps of
    # 100/n cents -- 0.2976c at n=336. Mass therefore piles onto a handful of
    # atoms, and `out[int(0.025*reps)]` can land in the middle of one holding
    # several percent. Comparing a realised value to that edge with `<` then
    # turns on floating-point dust: measured 2026-09-06, the tau<=20 floor
    # 0.5c cell sat ON the boundary atom and was flagged BELOW by -4.4e-15.
    # More reps cannot fix it; the discreteness is intrinsic, not sampling
    # error (identical at reps=2000 and reps=50000).
    #
    # `rank` is the mid-p percentile of `value` among the draws: strictly-
    # below plus half the ties. It is the well-defined thing to threshold.
    #
    # `atoms` is the EXACT distinct-value count -- keyed on the raw float, not
    # a rounded one, because rounding is itself the dust this guards against.
    # Measured on the real tau<=20 floor-0.5c cell (n=336, 2026-09-06):
    # fair 11 atoms in 2000 draws with 4.40% of the mass on the 2.5% cut;
    # mid  23 atoms with 2.65% on the 97.5% cut. Ten times the reps moves
    # those to 14 and 27 -- the discreteness is the estimator, not the sample.
    res["atoms"] = len(set(out))
    res["lo_mass"] = out.count(res["lo"]) / float(reps)
    res["hi_mass"] = out.count(res["hi"]) / float(reps)
    if value is not None:
        below = sum(1 for x in out if x < value - 1e-9)
        ties = sum(1 for x in out if abs(x - value) <= 1e-9)
        res["rank"] = (below + 0.5 * ties) / float(reps)
        res["ties"] = ties
    return res


# ===========================================================================
def analytic():
    print("=" * 78)
    print("PART 1  WHY THE LAST MINUTE -- the exact variance collapses")
    print("=" * 78)
    print("  Settlement averages the 60 one-second prints [close-60, close-1].")
    print("  With tau seconds left, 61-tau of them are LOCKED -- already")
    print("  printed, already on disk -- and tau-1 are still unknown.")
    print("  (Before 2026-09-08 this table said 60-tau locked and tau")
    print("  unknown: it counted the tick AT the close, which Kalshi's own")
    print("  window_end_ts_exclusive says is not in the settlement.)\n")
    print(f"  {'tau':>6}{'sd/sigma':>11}{'sqrt(tau)':>11}{'ratio':>8}"
          f"{'sqrt(t-39.5)':>14}{'ratio':>8}{'locked':>9}")
    for tau in (900, 400, 200, 120, 90, 60, 45, 30, 20, 10, 5, 2, 1):
        vf = var_factor(max(0, tau - 1), [1.0])       # tau-1 unknown prints
        sd = math.sqrt(vf)
        naive = math.sqrt(tau)
        lin = math.sqrt(max(tau - 39.5, 0.0))
        locked = max(0, min(N_AVG, N_AVG + 1 - tau))
        print(f"  {tau:>6}{sd:>11.4f}{naive:>11.4f}"
              f"{(naive/sd if sd > 0 else float('inf')):>8.3f}"
              f"{lin:>14.4f}{(lin/sd if sd > 0 else 0):>8.3f}"
              f"{locked:>9}")
    print("\n  A quote built on sqrt(tau) carries a sigma 1.7x too large at")
    print("  60s and 9.7x at 10s, which pins its price toward 50c exactly")
    print("  when the truth is going deterministic. sqrt(tau-39.5) is exact")
    print("  above 60s and then divides by approximately nothing.")


# ===========================================================================
def sigma_from(ticks, lo, hi, need=180):
    """Per-second sigma from the increments strictly inside [lo, hi), or None.

    TRUE (t, t+1) pairs only. Differencing consecutive PRESENT ticks across a
    gap measures a multi-second move and calls it a one-second one, which is
    how voltiming.py's estimator ran 16.5% high. `need` is a floor on the
    pairs actually found, not on the span asked for.
    """
    d = [ticks[s + 1] - ticks[s] for s in range(lo, hi)
         if s in ticks and s + 1 in ticks]
    return pstdev(d) if len(d) >= need else None


def mde(trades, alpha_t=3.0):
    """Smallest true edge this many trades could certify at |t| = alpha_t."""
    if len(trades) < 2:
        return float("inf")
    sd = pstdev([t["pnl"] for t in trades])
    return alpha_t * sd / math.sqrt(len(trades))


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

    # =====================================================================
    # 0a. BUG 1 -- THE SETTLEMENT WINDOW IS [close-60, close-1].
    #     Plant a wild tick AT the close (must be EXCLUDED from fair's mu)
    #     and one at close-60 (must be INCLUDED). Under the old window both
    #     verdicts came out backwards, and the sd at small tau was one
    #     unknown print too large.
    # =====================================================================
    print("\n  BUG 1 -- the settlement window. A tick stamped AT the close is")
    print("  outside the settlement; the tick at close-60 is inside it.")
    # The strike sits BETWEEN the flat mean (100) and the mean a counted
    # spike would produce (1100), so the two verdicts are opposite and each
    # half of the membership test actually bites.
    C0, K0 = 1_760_000_000, 500.0
    flat = {s: 100.0 for s in range(C0 - 300, C0 + 300)}
    spike_close = dict(flat)
    spike_close[C0] = 100.0 + 60_000.0        # would add +1000 to mu
    spike_lo = dict(flat)
    spike_lo[C0 - N_AVG] = 100.0 + 60_000.0
    f_close = fair(spike_close, C0, C0 - 1, K0, 1.0)
    f_lo = fair(spike_lo, C0, C0 - 1, K0, 1.0)
    f_flat = fair(flat, C0, C0 - 1, K0, 1.0)
    print(f"    fair at tau=1, strike {K0}: flat tape {f_flat}, "
          f"spike AT close {f_close}, spike at close-60 {f_lo}")
    if f_flat != 0.0:
        fails.append(f"a flat tape at 100 priced {f_flat} against a strike "
                     "of 500 -- the fixture is not what it says it is")
    if f_close != f_flat:
        fails.append(f"a tick stamped AT the close moved fair from {f_flat} "
                     f"to {f_close}; close is not in [close-60, close-1]")
    if f_lo != 1.0:
        fails.append(f"a +60000 tick at close-60 left fair at {f_lo}; the "
                     "close-60 print IS in the settlement window")
    # and the variance must agree with the mean about how much is left
    if fair(flat, C0, C0 - 1, 100.001, 1.0) != 0.0:
        fails.append("at tau=1 nothing is unknown (the last print is "
                     "close-1) but fair() still priced a random outcome")
    p1 = partial(flat, C0, C0 - 5)
    if p1 is None or p1[1] != 4:
        fails.append(f"at tau=5 partial reports {p1 and p1[1]} prints to "
                     "come; the truth is 4")
    sd5 = math.sqrt(var_factor(4, [1.0]))
    sd5_old = math.sqrt(var_factor(5, [1.0]))
    print(f"    sd/sigma at tau=5: {sd5:.5f} with 4 unknown prints, "
          f"{sd5_old:.5f} with the 5 the old code assumed "
          f"({sd5_old / sd5:.2f}x too wide)")
    if sd5_old <= sd5:
        fails.append("the old window's sd is not wider than the corrected "
                     "one, so this check is not pinning the variance half "
                     "of the window bug")

    # =====================================================================
    # 0b. BUG 2 -- THE SETTLEMENT IS ROUNDED BEFORE IT IS COMPARED.
    #     The real case, with the real numbers, from the real tape:
    #     KXETH15M-26SEP071745-45, floor_strike 2492.82, round_digits 2,
    #     tape mean over [close-60, close-1] = 2492.815833, Kalshi's
    #     expiration_value 2492.82, result YES.
    # =====================================================================
    print("\n  BUG 2 -- the settlement is rounded to the strike's precision")
    print("  before it is compared. KXETH15M-26SEP071745-45: strike 2492.82,")
    print("  tape mean 2492.815833, round_digits 2 -> Kalshi settled YES.")
    K_ETH, MU_ETH, D_ETH = 2492.82, 2492.8158333333334, 2
    if round(MU_ETH, D_ETH) < K_ETH:
        fails.append("the fixture's own arithmetic disagrees with Kalshi: "
                     f"round({MU_ETH}, {D_ETH}) is {round(MU_ETH, D_ETH)}, "
                     f"below the strike {K_ETH}, yet the market settled YES")
    thr = settle_threshold(K_ETH, D_ETH)
    print(f"    threshold: strike {K_ETH} -> {thr} "
          f"(= K - 0.5*10^-{D_ETH});  mean {MU_ETH} is "
          f"{'ABOVE' if MU_ETH >= thr else 'below'} it")
    if MU_ETH < thr:
        fails.append(f"settle_threshold({K_ETH}, {D_ETH}) = {thr} still sits "
                     f"above the mean {MU_ETH} that settled YES")
    if settle_threshold(K_ETH, None) != K_ETH:
        fails.append("settle_threshold with unknown round_digits must be the "
                     "strike itself, not a guess")
    # the same case priced end to end, on a tape that reproduces that mean
    eth = {s: MU_ETH for s in range(C0 - 300, C0 + 300)}
    f_round = fair(eth, C0, C0 - 1, K_ETH, 0.5, round_digits=D_ETH)
    f_raw = fair(eth, C0, C0 - 1, K_ETH, 0.5, round_digits=None)
    print(f"    fair at tau=1: rounded model {f_round}, unrounded {f_raw} "
          f"(the market settled YES, so 1.0 is right)")
    if f_round != 1.0:
        fails.append(f"the rounded model priced the confirmed ETH YES at "
                     f"{f_round}")
    if f_raw != 0.0:
        fails.append("the UNROUNDED model no longer gets this market wrong, "
                     "so this check has stopped pinning bug 2")
    # a strike far enough below the mean must be unaffected by rounding
    if fair(eth, C0, C0 - 1, K_ETH - 1.0, 0.5, round_digits=D_ETH) != 1.0 or \
       fair(eth, C0, C0 - 1, K_ETH + 1.0, 0.5, round_digits=D_ETH) != 0.0:
        fails.append("the rounding adjustment changed an outcome a whole "
                     "dollar away from the strike -- it is not a half-tick "
                     "correction any more")
    # the size of the correction is exactly half a tick, in both directions
    for d in (2, 4, 7):
        want = 0.5 * 10.0 ** (-d)
        got = 1000.0 - settle_threshold(1000.0, d)
        if abs(got - want) > 1e-12:
            fails.append(f"round_digits={d} shifted the threshold by {got}, "
                         f"not {want}")
    # the per-series map must read the collector's schema and not the table
    fake = {"A": {"series": "KXSOL15M", "settle": 103.3607},
            "B": {"series": "KXSOL15M", "settle": 103.4712}}
    fake.update({str(i): {"series": "KXSOL15M", "settle": 103.5}
                 for i in range(30)})
    inf = infer_round_digits(fake)
    print(f"    infer_round_digits on 32 KXSOL15M records: {inf}")
    if inf.get("KXSOL15M") != 4:
        fails.append(f"infer_round_digits read KXSOL15M as {inf.get('KXSOL15M')} "
                     "from settle values printed to 4 decimals")
    if infer_round_digits({"A": {"series": "KXNEW", "settle": 1.25}}):
        fails.append("infer_round_digits inferred a round_digits from a "
                     "single record; it must refuse a sample that small")

    SIG, S0, CLOSE = 6.0, 80000.0, 1_760_000_000
    S2I, POOLED = {"KXBTC15M": "BRTI"}, {"KXBTC15M": 6.0}

    def world(n, seed, model="exact", gap=0, sig_spread=0.0, span=130):
        """n consecutive 15-minute windows on ONE continuous index tape.

        Two properties are load-bearing and both were once wrong:

        * ONE TAPE. Windows are defined on top of a single random walk, not
          re-generated per window. The old fixture reset the price each
          window and wrote over the previous window's settlement prints, so
          `settle` was computed from a tape that `fair()` never saw.

        * THE STRIKE CANNOT SEE THE FUTURE. strike = mean of the sixty prints
          ending at the open, which is exactly `strike(N+1) == settle(N)` and
          exactly what every other fixture in this project uses. The old
          version drew `settle + noise`, which made the true probability of
          every market 50% and inverted the sign of the whole test.

        `sig_spread` gives each window its own true sigma, which the BOOK
        knows and the scan does not -- the mean-zero model error that a
        pooled sigma estimate produces in real life.
        """
        rng = random.Random(seed)
        quotes, index, markets = {}, {"BRTI": {}}, {}
        ticks = index["BRTI"]
        px, sig_of = S0, {}
        for w in range(-1, n):                       # -1 lays the first strike
            close_s = CLOSE + w * 900
            sw = SIG * math.exp(rng.gauss(0, sig_spread) - 0.5 * sig_spread ** 2) \
                if sig_spread else SIG
            sig_of[close_s] = sw
            for t in range(close_s - 900, close_s + 1):
                px += rng.gauss(0, sw)
                ticks[t] = px
        for w in range(n):
            close_s = CLOSE + w * 900
            open_s = close_s - 900
            tk = f"E{w:04d}"
            # THE WINDOW IS [close-60, close-1]. The close tick is NOT in it;
            # the close-60 tick IS. Same for the strike, which is the previous
            # window's settlement (strike(N+1) == settle(N)).
            settle = sum(ticks[t] for t in
                         range(close_s - N_AVG, close_s)) / N_AVG
            strike = sum(ticks[s] for s in
                         range(open_s - N_AVG, open_s)) / N_AVG
            # The COLLECTOR'S schema, deliberately: `settle` is the settled
            # index LEVEL and `result` is the outcome. This fixture used to
            # write `"settle": settle > strike` -- a bool -- and that single
            # disagreement with kalshi_fulltape.py hid a critical bug for as
            # long as the file existed: evaluate() read the truthiness of
            # `settle`, which is always True on real data, so every market
            # booked a YES win. A fixture whose schema differs from the
            # collector's tests nothing about the collector's data.
            markets[tk] = {"series": "KXBTC15M", "strike": strike,
                           "close": close_s, "settle": settle,
                           "result": 1.0 if settle >= strike else 0.0}
            book_sig = sig_of[close_s]
            ser = []
            for t in range(close_s - span, close_s):
                tau = close_s - t
                if gap and (t % gap == 0):
                    continue                          # a hole in the QUOTE tape
                part = partial(ticks, close_s, t)
                if part is None:
                    continue
                locked, r = part
                mu = (locked + r * ticks[t]) / N_AVG
                if model == "exact":
                    # tau-1 unknown prints remain, not tau -- the window ends
                    # at close-1. fair() prices the same thing.
                    sd = book_sig * math.sqrt(
                        var_factor(max(0, tau - 1), [1.0]))
                elif model == "naive":
                    sd = book_sig * math.sqrt(tau)        # the mistake
                else:
                    sd = book_sig * math.sqrt(max(tau - 39.5, 1e-9))
                p = ND.cdf((mu - strike) / sd) if sd > 0 else \
                    (1.0 if mu > strike else 0.0)
                # Skip seconds where the book's price is outside the range the
                # exchange can quote. The exchange cannot quote below 1c or
                # above 99c, so there the book is REALLY mispriced -- selling a
                # 1c contract worth 0.1c is a genuine 0.9c edge against a 0.07c
                # fee. That is a separate finding (see the CLAMP note in the
                # header), and leaving it in this fixture means "correctly
                # priced" is a lie and every assertion built on it is
                # meaningless. It cost a whole debugging pass to see that the
                # fixture, not the estimator, was the thing that was wrong.
                if not (0.02 <= p <= 0.98):
                    continue
                p = round(p * 100) / 100.0            # the 1c tick is real
                ser.append((t, max(p - 0.005, 0.0), min(p + 0.005, 1.0),
                            100.0, 100.0))
            quotes[tk] = ser
        return quotes, index, markets

    # =====================================================================
    # 1. DETECTION, and the honesty check that matters more than detection
    # =====================================================================
    print("\n  A book pricing the EXACT model must yield nothing at every tau")
    print("  cap. One pricing sqrt(tau) must be found -- and the CLAIMED edge")
    print("  at entry must match the REALISED P&L. A model that claims 5.8c")
    print("  and earns 7.9c is honest; the version this file shipped broken")
    print("  claimed 1.8c and earned -22.6c against the very same book.")
    N = 600
    worlds = {m: world(N, seed=5, model=m)
              for m in ("exact", "naive", "linear")}
    print(f"\n  {'book':>8}{'tau<=':>7}{'trades':>8}{'claimed':>10}"
          f"{'realised':>10}{'t':>7}{'MDE':>8}   verdict")
    got = {}
    for m in ("exact", "naive", "linear"):
        q, idx, mk = worlds[m]
        for tm in (120, 60, 30, 15):
            rows = scan(q, idx, mk, S2I, POOLED, tau_max=tm)
            tr = evaluate(rows)
            sm = summarise(tr, m)
            got[(m, tm)] = sm
            if not sm:
                print(f"  {m:>8}{tm:>7}{len(tr):>8}        --         --"
                      f"     --      --   silent")
                continue
            d = mde(tr)
            print(f"  {m:>8}{tm:>7}{sm['n']:>8}{sm['exp_edge']:>9.2f}c"
                  f"{sm['mean']:>9.2f}c{sm['t']:>7.1f}{d:>7.2f}c   "
                  + ("finds it" if sm["t"] > 3 else "nothing"))
        print()

    for tm in (120, 60, 30, 15):
        sm = got[("exact", tm)]
        if sm and abs(sm["t"]) > 3:
            fails.append(f"tau<={tm}: found {sm['mean']:.2f}c at t={sm['t']:.1f} "
                         "against a book pricing the EXACT model -- the "
                         "estimator is manufacturing it")
    for tm in (60, 30, 15):
        sm = got[("naive", tm)]
        if not sm or sm["t"] < 3:
            fails.append(f"tau<={tm}: missed a book pricing sqrt(tau), which "
                         "is wrong by 1.7x at 60s and 9.7x at 10s")
            continue
        # THE assertion. Detection alone is cheap; agreement is not.
        gap_ = abs(sm["exp_edge"] - sm["mean"])
        if gap_ > 3.0 * sm["se"]:
            fails.append(f"tau<={tm}: claimed {sm['exp_edge']:.2f}c but "
                         f"realised {sm['mean']:.2f}c -- {gap_:.2f}c apart, "
                         f"{gap_/sm['se']:.1f} standard errors. A model that "
                         "cannot predict its own P&L on a tape we built is "
                         "not going to predict it on Kalshi's.")

    print("  sqrt(tau-39.5) is INVISIBLE, and that is a finding rather than a")
    print("  weakness: it is exact above 60s and collapses to zero below 40s,")
    print("  so its quotes go to 0 or 1 -- outside what the exchange can quote")
    print("  at all. Its error region censors itself out of the book.")

    # =====================================================================
    # 1b. THE OUTCOME FIELD. This is the bug that shipped, and the reason
    #     this whole file's 2026-08-28 real-data table was meaningless.
    # =====================================================================
    print("\n  THE OUTCOME FIELD. kalshi_fulltape.py writes `settle` as the")
    print("  settled index LEVEL and `result` as the outcome, and guards")
    print("  `if k and v and c`, so settle is ALWAYS a nonzero float on real")
    print("  data. Reading its truthiness books EVERY market as a YES win.")
    coll = [{"strike": 80000.0, "settle": 79500.0, "result": 0.0},   # NO
            {"strike": 80000.0, "settle": 80500.0, "result": 1.0},   # YES
            {"strike": 80000.0, "settle": 79999.0, "result": 0.0},
            {"strike": 80000.0, "settle": 80000.0, "result": 1.0}]
    got = [outcome_of(m) for m in coll]
    old = [1.0 if m["settle"] else 0.0 for m in coll]      # what shipped
    print(f"    outcome_of on collector records : {got}")
    print(f"    the truthiness reading that shipped: {old}")
    if got != [0.0, 1.0, 0.0, 1.0]:
        fails.append(f"outcome_of misread the collector's schema: {got}")
    if old == got:
        fails.append("the broken reading and the correct one now agree, so "
                     "this check has stopped pinning anything")
    # and with `result` absent it must fall back to settle vs strike
    if [outcome_of({k: v for k, v in m.items() if k != "result"})
            for m in coll] != [0.0, 1.0, 0.0, 1.0]:
        fails.append("outcome_of could not fall back to settle >= strike when "
                     "`result` was absent")
    # the fixture must now carry the collector's schema, and the outcomes it
    # produces must not be degenerate
    q, idx, mk = world(400, seed=31, model="naive")
    if any(isinstance(m["settle"], bool) for m in mk.values()):
        fails.append("world() is still writing a bool into `settle` -- the "
                     "single schema disagreement that hid this bug")
    rows = scan(q, idx, mk, S2I, POOLED, tau_max=60)
    tr = evaluate(rows)
    rate = mean(t["won"] for t in tr) if tr else -1
    print(f"    fixture YES rate over {len(tr)} settled markets: {rate:.3f}")
    if not (0.05 <= rate <= 0.95):
        fails.append(f"the fixture's YES rate is {rate:.3f} -- degenerate, "
                     "which is the signature of reading the wrong field")
    # sane_or_die must refuse a degenerate set rather than print a number
    print("    sane_or_die on an all-YES set:", end=" ")
    if sane_or_die([{"won": 1.0}] * 50, "a deliberately degenerate set"):
        fails.append("sane_or_die accepted a set in which every market won")
    else:
        print("(refused, as it must)")

    # =====================================================================
    # 2. THE GAP TRAP
    # =====================================================================
    print("\n  THE GAP TRAP. settlewin.py exists because four copies of this")
    print("  calculation summed the ticks PRESENT and divided by the count")
    print("  that SHOULD be present, putting mu thousands of dollars off and")
    print("  pinning fair at 0 or 1. A missing index second must produce NO")
    print("  trade, never a confident one.")
    q, idx, mk = world(N, seed=9, model="exact")
    ticks = idx["BRTI"]
    holed = 0
    for tk, m in mk.items():
        c = int(m["close"])
        for t in range(c - 25, c - 15):               # punch a hole mid-window
            if t in ticks:
                del ticks[t]
                holed += 1
    rows = scan(q, idx, mk, S2I, POOLED)
    bad = [r for r in rows if r["tau"] <= 25 and r["fair"] in (0.0, 1.0)]
    tr = evaluate(rows)
    sm = summarise(tr, "holed")
    tail = (f"P&L {sm['mean']:.2f}c t={sm['t']:.1f}" if sm else "too few trades")
    print(f"  removed {holed} index seconds -> {len(rows):,} usable rows, "
          f"{len(bad)} pinned to 0/1, {tail}")
    if bad:
        fails.append(f"{len(bad)} rows inside the hole were priced at a "
                     "confident 0 or 1 -- partial() is dividing by the count "
                     "that should be there rather than refusing")
    # TWO-sided. A confident LOSS on a tape whose truth is zero is the same
    # failure as a confident gain, and the one-sided version of this check is
    # exactly how the selection bias below passed its first run.
    if sm and abs(sm["t"]) > 3:
        fails.append(f"a punched index tape produced {sm['mean']:.2f}c at "
                     f"t={sm['t']:.1f} against a true edge of zero")

    # =====================================================================
    # 3. WHAT A POOLED SIGMA COSTS -- the trap this file is most likely to
    #    fall into on real data, because every other stage pools
    # =====================================================================
    print("\n  POOLED SIGMA. The book prices each window with that window's")
    print("  OWN true sigma, so it is correct everywhere and the true edge is")
    print("  exactly zero. We scan with ONE pooled sigma per series -- which")
    print("  is what every other stage in this project does. Our model is now")
    print("  wrong per window in a mean-zero way, and mean-zero model error")
    print("  does NOT produce mean-zero P&L, because we only trade where the")
    print("  error points at a profit.")
    print(f"\n  {'sigma spread':>14}{'trades':>8}{'claimed':>10}{'realised':>10}"
          f"{'overclaim':>11}{'t':>7}")
    over = {}
    for spread in (0.0, 0.25):
        q, idx, mk = world(1200, seed=21, sig_spread=spread)
        rows = scan(q, idx, mk, S2I, POOLED, tau_max=60)
        tr = evaluate(rows)
        sm = summarise(tr, f"spread={spread}")
        over[spread] = sm
        if not sm:
            print(f"  {spread:>14.2f}{len(tr):>8}   too few")
            continue
        print(f"  {spread:>14.2f}{sm['n']:>8}{sm['exp_edge']:>9.2f}c"
              f"{sm['mean']:>9.2f}c{sm['exp_edge'] - sm['mean']:>10.2f}c"
              f"{sm['t']:>7.1f}")
    if over[0.0] and abs(over[0.0]["t"]) > 3:
        fails.append("a correctly-priced book with a single true sigma still "
                     f"paid {over[0.0]['mean']:.2f}c at t={over[0.0]['t']:.1f}")
    s25 = over[0.25]
    if not s25:
        fails.append("the pooled-sigma world produced no trades, so this "
                     "check has stopped pinning anything")
    else:
        if s25["exp_edge"] - s25["mean"] < 1.0:
            fails.append("a pooled sigma against per-window truth no longer "
                         "overclaims, so either the fixture or evaluate has "
                         "changed and this check is no longer live")
        if s25["t"] > 3:
            fails.append(f"pooled sigma EARNED {s25['mean']:.2f}c at "
                         f"t={s25['t']:.1f} against a true edge of zero")
    print("\n  That gap is why main() below estimates sigma from each market's")
    print("  own path up to the start of the endgame instead of pooling.")

    # =====================================================================
    # 3b. THE PER-MARKET SIGMA ESTIMATOR ITSELF
    #     main() rests on this and nothing else executes it. It must recover
    #     a planted per-window sigma, and it must REFUSE rather than guess
    #     when the tape it is handed is mostly holes.
    # =====================================================================
    print("\n  PER-MARKET SIGMA. main() prices each window off its own")
    print("  pre-endgame path. Plant a known sigma per window and check the")
    print("  estimator returns it -- and refuses a tape that is mostly gaps.")
    rng = random.Random(77)
    err, refused, n_est = [], 0, 0
    for planted in (2.0, 6.0, 25.0):
        for _ in range(40):
            tk_, px_ = {}, 1000.0
            for t in range(0, 800):
                px_ += rng.gauss(0, planted)
                tk_[t] = px_
            v = sigma_from(tk_, 0, 770)
            if v:
                n_est += 1
                err.append(v / planted - 1.0)
    # a tape with 90% of its seconds missing must give None, not a number
    holey = {t: 1000.0 + t for t in range(0, 800, 10)}
    if sigma_from(holey, 0, 770) is None:
        refused += 1
    # ... and one whose gaps are wide must not difference ACROSS them
    wide = {}
    px_ = 1000.0
    for t in range(0, 800):
        if 200 <= t < 600:
            continue
        px_ += rng.gauss(0, 5.0) * (20.0 if t == 600 else 1.0)
        wide[t] = px_
    vw = sigma_from(wide, 0, 770, need=100)
    print(f"    {n_est} estimates, mean relative error "
          f"{100*mean(err):+.2f}%, max |error| {100*max(abs(x) for x in err):.1f}%")
    print(f"    a tape with 90% of its seconds missing -> "
          f"{'refused' if refused else 'RETURNED A NUMBER'}")
    print(f"    a 400s hole -> {vw:.2f} (true 5.00; differencing across the")
    print("    hole would report the whole jump as one second)")
    if abs(mean(err)) > 0.05:
        fails.append(f"the per-market sigma estimator is off by "
                     f"{100*mean(err):+.1f}% against a planted sigma")
    if not refused:
        fails.append("sigma_from returned a number for a tape with 90% of "
                     "its seconds missing instead of refusing")
    if vw is None or abs(vw / 5.0 - 1.0) > 0.25:
        fails.append(f"sigma_from across a 400-second hole gave {vw}, not ~5 "
                     "-- it is differencing across the gap")

    # =====================================================================
    # 4. SELECTION, and 5. CLUSTERING
    # =====================================================================
    print("\n  SELECTION. Picking the LARGEST disagreement in each window is")
    print("  a look-ahead: it finds where the MODEL is most wrong, not the")
    print("  market. Same rows, same per-window-correct book, two rules.")
    q, idx, mk = world(1200, seed=21, sig_spread=0.25)
    rows_s = scan(q, idx, mk, S2I, POOLED, tau_max=60)
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
    if res["best"] and res["first"] and \
            res["best"]["exp_edge"] <= res["first"]["exp_edge"]:
        fails.append("the largest-disagreement rule no longer claims more "
                     "than the first-to-clear rule, so this check has stopped "
                     "pinning the selection effect")

    q, idx, mk = world(300, seed=13, model="naive")
    rows = scan(q, idx, mk, S2I, POOLED, tau_max=60)
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
    print("SELF-TEST PASSED -- silent against a correctly-priced book at every")
    print("tau cap, finds a sqrt(tau) book with claimed matching realised,")
    print("refuses a punched index tape, shows what a pooled sigma costs, and")
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
    if not markets:
        print(f"\n  *** NO SETTLED MARKETS at {os.path.abspath(a.out)} -- "
              "run fulltape or fix --out.")
        return
    index = load_index(a.data)

    # ---------------------------------------------------------------
    # sigma, per MARKET, from that market's own path BEFORE the endgame.
    #
    # The self-test above measures what the obvious alternative costs. Give
    # the book each window's own true sigma and scan with a single pooled
    # per-series sigma -- exactly what every other stage in this project does
    # -- and against a true edge of exactly zero the strategy claims +2.5c and
    # realises -4.2c. Mean-zero model error does not give mean-zero P&L,
    # because we only trade where the error happens to point at a profit.
    #
    # So sigma comes from increments strictly inside [open, close - 130], i.e.
    # entirely before the earliest second this file will ever trade. That is
    # non-anticipating for every decision made below. Where a window is too
    # thin for its own estimate we fall back to the pooled series value and
    # SAY SO, because those markets carry the bias the paragraph above
    # describes.
    # ---------------------------------------------------------------
    pooled = {}
    for s, iid in SERIES_TO_INDEX.items():
        ticks = index.get(iid) or {}
        ts = sorted(ticks)
        if len(ts) < 600:
            continue
        d = [ticks[ts[i + 1]] - ticks[ts[i]] for i in range(len(ts) - 1)
             if ts[i + 1] - ts[i] == 1]
        if len(d) > 300:
            pooled[s] = pstdev(d)
    if not pooled:
        # Names the FEED, not "index feed": chain.py legitimately prints
        # "[needs no index feed]" in a section heading on every successful
        # run, and a marker matching that would flag chain EMPTY forever.
        # markers.py caught the collision the moment the marker was added.
        print("\n  no cfbenchmarks_value -- fair value is not computable.")
        return

    per_market, n_own, n_pooled = {}, 0, 0
    for tk, m in markets.items():
        s = m.get("series") or tk.split("-")[0]
        ticks = index.get(SERIES_TO_INDEX.get(s))
        close_s = m.get("close")
        if not ticks or not close_s:
            continue
        v = sigma_from(ticks, int(close_s) - 900, int(close_s) - a.tau_max - 10)
        if v and v > 0:
            per_market[tk] = v
            n_own += 1
        elif s in pooled:
            n_pooled += 1

    print("\n  sigma per series (1-second, pooled over the whole tape) --")
    print("  used only as the fallback:")
    for s, v in sorted(pooled.items()):
        print(f"    {s:<16}{v:>12.4f}")
    tot = n_own + n_pooled
    frac = (100.0 * n_own / tot) if tot else 0.0
    print(f"\n  {n_own:,} of {tot:,} markets ({frac:.0f}%) priced with their "
          "OWN pre-endgame sigma;")
    print(f"  {n_pooled:,} fell back to the pooled value and carry the bias "
          "the self-test measures.")

    print("\n  settlement rounding (bug 2): the threshold is "
          "K - 0.5*10^-round_digits,")
    print("  not K. Per series, read off the settled records and cross-checked")
    print("  against the API-measured table:")
    rdmap = round_digits_map(markets)

    rows = scan(quotes, index, markets, SERIES_TO_INDEX, pooled,
                tau_max=a.tau_max, sigma_by_market=per_market,
                round_digits=rdmap)
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
    # Deliberately NOT phrased "a bucket with no quotes": go.py scans stage
    # output for loader-failure markers, one of which is /\bno quotes\b/, and
    # this sentence tripped it -- flagging a stage that had just printed 89,757
    # quote-seconds and a full P&L table as "EMPTY, do not read this". go.py's
    # own comment warns that a false EMPTY buries a real result; markers.py now
    # checks the rule that prevents it.
    print("\n  Read the quote-seconds column first. An edge in a bucket that")
    print("  nothing is quoted in is not an edge.")

    # -------------------------------------------------------------------
    # The self-test shows the edge against a wrong-sigma book grows as the
    # cap tightens (+3.2c at 120s -> +12.1c at 15s), so reporting one cap
    # would be choosing it after the fact. Report all four. Four looks means
    # |t| > 3 is p < 0.003 each, still under 0.05 family-wise, so the bar
    # does not move -- but a cell that clears 3 while its neighbours sit at
    # zero is noise, not a boundary.
    # -------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SETTLEMENT P&L  --  one trade per close, taking the book only when")
    print("the model says it is wrong by more than the fee")
    print("=" * 78)
    print(f"  {'tau<=':>7}{'trades':>8}{'YES rate':>10}{'claimed':>10}"
          f"{'realised':>10}{'t':>7}{'MDE':>8}"
          f"{'market-right null':>20}{'model band':>18}")
    any_row = False
    for tm in (a.tau_max, 60, 30, 15):
        sel = [r for r in rows if r["tau"] <= tm]
        trades = evaluate(sel)
        sm = summarise(trades, f"tau<={tm}")
        if not sm:
            print(f"  {tm:>7}{len(trades):>8}   fewer than 10 trades -- no "
                  "information either way")
            continue
        # The gate that would have caught the settle-as-price bug on sight.
        if not sane_or_die(trades, f"tau<={tm}"):
            continue
        any_row = True
        mk = redraw_null(trades, reps=800, using="mid")
        md = redraw_null(trades, reps=800, using="fair")
        print(f"  {tm:>7}{sm['n']:>8}"
              f"{mean(t['won'] for t in trades):>10.3f}"
              f"{sm['exp_edge']:>9.2f}c{sm['mean']:>9.2f}c"
              f"{sm['t']:>7.2f}{mde(trades):>7.2f}c"
              f"   [{mk['lo']:>5.2f},{mk['hi']:>5.2f}]c"
              f"   [{md['lo']:>5.2f},{md['hi']:>5.2f}]c")
    if not any_row:
        print("\n  Nothing qualifying at any cap. There is no endgame trade "
              "here to test.")
        return
    print("\n  READ THE YES-RATE COLUMN FIRST. It should sit near 0.5. This")
    print("  file once printed a whole P&L table in which every market had")
    print("  booked a YES win, because `settle` is the settled index LEVEL and")
    print("  the outcome is `result` -- see outcome_of(). A degenerate rate")
    print("  now refuses to print rather than printing a number.")
    print("\n  MARKET-RIGHT NULL is the null: what the strategy earns if the")
    print("  book's price is the true probability. It is NEGATIVE by")
    print("  construction -- you pay the spread and the fee. Beating it is the")
    print("  bar. MODEL BAND is not a null: it is centred on the claimed edge")
    print("  by construction, so a result inside it means the MODEL IS RIGHT.")
    print("  Those two readings are opposites and this file printed only the")
    print("  second one, labelled as the first, until 2026-08-29.")
    print("\n  Then read CLAIMED against REALISED, and MDE last: a cell whose")
    print("  true edge is below its MDE could not have been certified either")
    print("  way.")


if __name__ == "__main__":
    main()
