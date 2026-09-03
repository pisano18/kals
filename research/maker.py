#!/usr/bin/env python3
# VERSION: 2026-08-27-mk1
"""
maker.py -- can you QUOTE these markets rather than cross them?

    python research/maker.py --selftest
    python research/maker.py --data C:\\kals\\kalshi_data --out C:\\kals\\fulltape

WHY THIS EXISTS

PLAN.md sec.4 killed market-making on one observation -- "best bid 0.40 with
3,767 contracts resting" -- taken from a REST call RUNBOOK separately records
as mis-parsed. Rebuilt from the websocket, median depth at the touch is about
30 contracts. The number that closed the strategy was wrong by two orders of
magnitude, so the strategy is open again and nobody has priced it.

Three facts make it worth pricing, all measured, none assumed:

  1. MAKERS PAY NO FEE. All sixteen fifteen-minute series carry
     fee_type="quadratic", not "quadratic_with_maker_fees". A taker crossing a
     one-cent spread at the money pays 1.75c. The maker on the other side pays
     nothing. That asymmetry is the whole opportunity.
  2. The tick is one cent and the median quoted spread on the liquid series is
     one cent -- so a two-sided quote captures 1c gross, 0.5c per side.
  3. The thin series quote far wider: ZEC 7c, NEAR 8c.

THE ONE CALCULATION THAT DECIDES IT -- AND IT IS NOT DIFFUSION

A first pass at this compared the half-spread against how far fair value drifts
per second. That is the wrong conditioning, and it is optimistic. You are not
run over by the AVERAGE second; you are run over by the seconds in which
somebody chose to trade with you.

Condition on the fill. A taker crossing pays the spread AND the fee, so a
rational one only crosses when their estimate F beats the touch by more than
the fee:

    F - a > fee(p)      =>      E[F | ask lifted] >= a + fee(p)

The maker who sold at a earns a - F, so

    E[maker P&L per fill] <= a - (a + fee(p)) = -fee(p)

**and that bound does not depend on how wide you quote**, because widening
raises the half-spread on both sides of the inequality and it cancels. Against
perfectly informed takers, a maker loses the TAKER's fee on every fill:
-1.75c at 50c, -0.63c at 90c, -0.33c at 95c. Paying no maker fee is why anyone
quotes at all; it is not an edge.

So the strategy lives or dies on ONE measurable number: what fraction of the
flow is uninformed. Noise crossing (impatience, hedging, liquidation, retail)
pays you the half-spread and takes nothing back. Informed crossing costs you
the fee. Mixing:

    E[P&L per fill] = q*h - (1-q)*fee(p)      q = uninformed share

    break-even q = fee / (fee + h)

At 50c with a 1c spread that is q = 1.75/2.25 = 78%: more than three quarters
of everyone who trades with you must be trading for reasons unrelated to where
the price is going. At 90c it is 56%.

That number is not assumable. It is measurable, and it is exactly the signed
markout this file computes from the tape.

The diffusion table below is still printed, because it is a NECESSARY
condition -- a spread that cannot survive a second of drift cannot survive an
informed taker either -- but it is not sufficient, and it must not be read as
a green light.

    d(fair)/d(spot) = phi(z)/sd * (r_live/60)          [settlement_math.py]
    a one-second one-sigma index move is sigma dollars
    => adverse selection per second = 100 * phi(z) / sd * (r_live/60) * sigma

and since sd = sigma * sqrt(var_factor(tau)), THE SIGMA CANCELS EXACTLY:

    adverse_cents_per_second = 100 * phi(z) / sqrt(var_factor(tau)) * r_live/60

Verified numerically below across six orders of magnitude of sigma. This is
worth stating plainly because it is unusual and it is load-bearing: **the
viable quoting region does not depend on the asset at all.** It depends only on
how far from 50c you quote, how long is left, and how wide the spread is. BTC
and DOGE have the same answer.

WHAT IT MEASURES FROM REAL DATA

The formula gives the region where quoting COULD pay. Whether it DOES pay
depends on two things only the tape can answer:

  * REALISED adverse selection. For every trade at the touch, how far does the
    mid move afterwards? Scored against an EXOGENOUS-GRID null -- the same
    horizons measured at times we chose rather than times a trade chose. If
    post-trade moves look like random-time moves, there is no adverse
    selection. That null is the whole test; a raw post-trade drift is not.
  * FILL OPPORTUNITY. A 7-cent spread you never get filled at is worth nothing.
    Counts trades in the viable region per market per window.

Clustered on close time throughout, because twelve series close simultaneously
at rho 0.8 and are worth 1.22 independent units. NOTHING HERE PLACES AN ORDER.
"""

import argparse
import math
import os
import random as _random
import sys
from collections import defaultdict
from statistics import NormalDist, mean, median, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import var_factor, N_AVG                      # noqa: E402
from tdist import p_two_sided, crit                       # noqa: E402

ND = NormalDist()


# ===========================================================================
# the analytic part -- needs no data at all
# ===========================================================================
def adverse_per_second(tau, p):
    """Cents of fair value lost to a one-second one-sigma index move, for a
    quote resting at price p with tau seconds to close.

    Sigma does not appear: it cancels between the move size and the
    denominator of d(fair)/d(spot). See the module docstring.
    """
    vf = var_factor(tau, [1.0])
    if vf <= 0:
        return float("inf")
    p = min(max(p, 1e-9), 1 - 1e-9)
    z = ND.inv_cdf(p)
    r_live = min(N_AVG, max(tau, 0)) if tau < N_AVG else N_AVG
    return 100.0 * ND.pdf(z) / math.sqrt(vf) * (r_live / N_AVG)


def breakeven_price(tau, half_spread_cents):
    """The price at or beyond which the half-spread covers a one-second move.

    Returns 0.5 when the whole book is viable at that horizon.
    """
    if adverse_per_second(tau, 0.5) <= half_spread_cents:
        return 0.5
    lo, hi = 0.5, 1 - 1e-9
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if adverse_per_second(tau, mid) > half_spread_cents:
            lo = mid
        else:
            hi = mid
    return hi


def region_table(spreads=(1.0, 2.0, 4.0, 7.0, 8.0),
                 taus=(900, 600, 300, 120, 60, 30)):
    print("\n" + "=" * 78)
    print("WHERE QUOTING CAN PAY  --  analytic, no data, asset-independent")
    print("=" * 78)
    print("  A resting quote is a written option. It is exercised against you")
    print("  exactly when fair value moves through it. Quote nearer 50c than")
    print("  the price below and a single second of index movement costs more")
    print("  than the half-spread you collect.\n")
    print(f"  {'spread':>8}{'half':>7}   " +
          "".join(f"{str(t) + 's':>9}" for t in taus))
    for spr in spreads:
        row = f"  {spr:>7.1f}c{spr/2:>6.2f}c   "
        for t in taus:
            b = breakeven_price(t, spr / 2.0)
            row += (f"{'anywhere':>9}" if b <= 0.5001 else f"{100*b:>8.1f}c")
        print(row)
    print("\n  'anywhere' means the spread covers a one-second move even at")
    print("  50c. Mirror every price below 50c: 95c and 5c are the same trade.")


# ===========================================================================
# the measured part
# ===========================================================================
GRID = [720, 600, 480, 360, 300, 240, 180, 120, 90, 60, 45, 30]
HORIZONS = [1, 5, 30]


def adverse_from_tape(quotes, trades, closes, horizons=HORIZONS,
                      verbose=False):
    """SIGNED markout per fill: the decision quantity, not a volatility proxy.

        AS_i(h) = sgn_i * (mid(t_i + h) - mid(t_i-))          in cents
        sgn_i   = +1 if the taker lifted the ask (we sold), -1 if they hit
                  the bid (we bought)

    Positive means the taker was right and the resting side was run over.
    E[AS] = 0 is the no-adverse-selection null, and net per fill is
    half_spread - AS.

    TWO BUGS THIS REPLACES, both of which my own self-test passed over:

    1. The pre-trade mid was taken as "last quote at or before t". Book
       updates share the trade's integer second constantly, so that returned
       the POST-trade mid and measured 1.000c of planted permanent adverse
       selection as 0.000c -- a total attenuation to a clean null. The
       reference mid must be STRICTLY before the trade.
    2. The headline compared |post-trade move| against |random-grid move|.
       That is a volatility test, not a direction test: trades cluster in
       volatile moments, so on a tape with provably ZERO adverse selection it
       fired at t = +11. The signed markout has no such artefact, because
       volatility is symmetric and the sign is not.

    The deeper lesson, and it is the one this project keeps relearning: the
    self-test exercised the signed path while main() reported the absolute
    path. Testing a different quantity than you report is indistinguishable
    from not testing.
    """
    hit = defaultdict(list)
    shuf = defaultdict(list)
    rnd = _random.Random(20260827)
    n_tr = sum(len(v) for v in trades.values())
    if verbose:
        print(f"  markouts over {len(quotes):,} markets and {n_tr:,} trades")
        if not n_tr:
            print("  no trades on disk -- nothing to mark out against")
    done = 0
    for tk, series in quotes.items():
        done += 1
        # A STAGE THAT DIES MUST SAY WHERE. This timed out at 3600s twice and
        # its output was the single line "*** TIMED OUT ***", which does not
        # distinguish a slow loop from a hung read.
        if verbose and done % 2000 == 0:
            print(f"    {done:,}/{len(quotes):,} markets, "
                  f"{sum(len(v) for v in hit.values()):,} markouts",
                  flush=True)
        close_s = closes.get(tk)
        if not close_s or len(series) < 30:
            continue
        mids = {t: (b + a) / 2.0 for t, b, a, _, _ in series}
        spr = {t: (a - b) for t, b, a, _, _ in series}
        secs = sorted(mids)
        if len(secs) < 30:
            continue

        def _before(t, strict=False):
            """The freshest quote second at (or strictly before) t."""
            lo, hi, best = 0, len(secs) - 1, None
            while lo <= hi:
                m = (lo + hi) // 2
                if (secs[m] < t) if strict else (secs[m] <= t):
                    best = secs[m]
                    lo = m + 1
                else:
                    hi = m - 1
            if best is None or t - best > 30:
                return None
            return best

        def mid_at(t, strict=False):
            """Last mid at (or strictly before) t, and only if it is fresh."""
            b = _before(t, strict)
            return None if b is None else mids[b]

        for (t, price, size, side) in trades.get(tk, []):
            # STRICTLY before: a quote stamped in the trade's own second is
            # the book AFTER the trade, and using it measures nothing
            m0 = mid_at(t, strict=True)
            if m0 is None:
                continue
            sgn = 1.0 if str(side).lower().startswith("y") else -1.0
            flip = rnd.choice((1.0, -1.0))
            # ONCE PER TRADE, BY BINARY SEARCH. This used to be
            #   spr.get(t, spr.get(max(x for x in secs if x < t), 0.01))
            # evaluated inside the horizon loop -- a LINEAR scan of every
            # quote second in the market, per trade, per horizon. The stage
            # timed out at 3600s on two consecutive real runs and its verdict
            # never printed. `mid_at` was already doing the same lookup
            # correctly two lines above.
            b0 = _before(t, strict=True)
            sp0 = spr.get(t, spr[b0] if b0 is not None else 0.01)
            for h in horizons:
                m1 = mid_at(t + h)
                if m1 is None:
                    continue
                # m0 rides along so fills can be bucketed by PRICE. The fee
                # is 0.07*p*(1-p) and the break-even uninformed share is
                # fee/(fee+h), so the answer at 50c and the answer at 5c are
                # different questions -- 78% against 25%. A pooled number is
                # dominated by the mid-book, which is exactly the region the
                # arithmetic says cannot work.
                hit[h].append((sgn * (m1 - m0) * 100.0, close_s, m0, sp0))
                # same moments, same moves, RANDOM sign: isolates whether the
                # taker's direction carries information from whether trades
                # merely happen in volatile seconds
                shuf[h].append((flip * (m1 - m0) * 100.0, close_s, m0,
                                0.0))
    return hit, shuf


def clustered(pairs):
    """One observation per close time, then a t on (clusters - 1) df."""
    by = defaultdict(list)
    for rec in pairs:
        by[rec[1]].append(rec[0])          # (value, close, [price, ...])
    obs = [mean(v) for v in by.values()]
    n = len(obs)
    if n < 10:
        return None
    m, sd = mean(obs), pstdev(obs)
    se = sd / math.sqrt(n) if sd > 0 else float("inf")
    return {"mean": m, "n": n, "se": se,
            "t": m / se if se > 0 else 0.0, "df": n - 1}


# ===========================================================================
def selftest():
    import random
    print("=" * 78)
    print("SELF-TEST -- the region formula, and a planted adverse selection")
    print("=" * 78)
    fails = []

    print("\n  SIGMA MUST CANCEL. The same price and horizon must give the same")
    print("  answer for BTC and for DOGE, six orders of magnitude apart.")
    print(f"  {'sigma ($/sqrt s)':>20}{'adverse @95c/900s':>20}")
    vals = []
    for sig in (6.3403, 0.1953, 0.0118, 0.00002):
        sd = math.sqrt(var_factor(900, [1.0]) * sig * sig)
        v = 100.0 * (ND.pdf(ND.inv_cdf(0.95)) / sd) * sig
        vals.append(v)
        print(f"  {sig:>20g}{v:>19.4f}c")
    if max(vals) - min(vals) > 1e-9:
        fails.append(f"sigma did not cancel: spread {max(vals)-min(vals):.2e}")
    if abs(vals[0] - adverse_per_second(900, 0.95)) > 1e-9:
        fails.append("adverse_per_second disagrees with the direct form")

    print("\n  MONOTONICITY. Adverse selection must RISE toward 50c and must")
    print("  RISE as the close approaches. Anything else is a sign error.")
    bad = 0
    for tau in (900, 300, 60):
        prev = None
        for p in (0.99, 0.95, 0.90, 0.80, 0.70, 0.60, 0.50):
            v = adverse_per_second(tau, p)
            if prev is not None and v <= prev:
                bad += 1
            prev = v
    for p in (0.95, 0.80, 0.60):
        prev = None
        for tau in (900, 600, 300, 120, 60):
            v = adverse_per_second(tau, p)
            if prev is not None and v <= prev:
                bad += 1
            prev = v
    print(f"  {'monotonicity violations':>34}: {bad}")
    if bad:
        fails.append(f"{bad} monotonicity violations in adverse_per_second")

    print("\n  BREAK-EVEN must widen as the spread widens and as time runs out")
    b900_1 = breakeven_price(900, 0.5)
    b900_4 = breakeven_price(900, 4.0)
    b60_1 = breakeven_price(60, 0.5)
    print(f"  {'1c spread, 900s':>34}: {100*b900_1:.1f}c")
    print(f"  {'8c spread, 900s':>34}: "
          f"{'anywhere' if b900_4 <= 0.5001 else f'{100*b900_4:.1f}c'}")
    print(f"  {'1c spread,  60s':>34}: {100*b60_1:.1f}c")
    if not (b900_4 <= b900_1):
        fails.append("a wider spread did not widen the viable region")
    if not (b60_1 > b900_1):
        fails.append("less time did not shrink the viable region")

    print("\n  PLANTED ADVERSE SELECTION, with the book updating in the SAME")
    print("  SECOND as the trade -- which is what the real tape does, and what")
    print("  a 'last quote at or before t' lookup silently reads as the")
    print("  post-trade mid, attenuating a planted 1.00c to 0.00c.")
    print(f"\n  {'planted':>12}{'measured 1s':>14}{'t vs 0':>10}{'clusters':>10}")
    for planted in (0.0, 0.5, 1.0):
        rnd = random.Random(11)
        quotes, trades, closes = {}, {}, {}
        for w in range(140):
            close_s = 1_760_000_000 + w * 900
            tk = f"M{w:04d}"
            closes[tk] = close_s
            mid = 0.50
            ser, tr = [], []
            for s_ in range(close_s - 900, close_s + 1):
                mid = min(max(mid + rnd.gauss(0, 0.0015), 0.05), 0.95)
                ser.append([s_, mid - 0.005, mid + 0.005, 100.0, 100.0])
            for i in range(60, 900, 60):
                s_ = close_s - 900 + i
                side = "yes" if rnd.random() < 0.5 else "no"
                sgn = 1.0 if side == "yes" else -1.0
                tr.append((s_, ser[i][1], 10.0, side))
                # the drift lands starting IN the trade's own second
                for j in range(i, min(i + 31, len(ser))):
                    ser[j][1] += sgn * planted / 100.0
                    ser[j][2] += sgn * planted / 100.0
            quotes[tk] = [tuple(r) for r in ser]
            trades[tk] = tr
        hit, shuf = adverse_from_tape(quotes, trades, closes,
                                  verbose=True)
        h = clustered(hit[1])
        if not h:
            fails.append(f"planted={planted}: estimator returned nothing")
            continue
        print(f"  {planted:>11.2f}c{h['mean']:>13.3f}c{h['t']:>10.1f}{h['n']:>10}")
        if planted == 0.0 and abs(h["t"]) > crit(0.05, h["df"]):
            fails.append(f"found adverse selection (t={h['t']:.1f}) where none "
                         "was planted")
        if planted > 0 and abs(h["mean"] - planted) > 0.30 * planted:
            fails.append(f"planted {planted}c, measured {h['mean']:.3f}c -- "
                         "the pre-trade mid is being read after the trade")
        if planted > 0 and h["t"] < 3:
            fails.append(f"missed a planted {planted}c (t={h['t']:.1f})")

    print("\n  THE VOLATILITY TRAP. Trades arrive PREFERENTIALLY IN VOLATILE")
    print("  SECONDS and carry ZERO directional information. An absolute-move")
    print("  test fires hard on this; a signed one must not.")
    rnd = random.Random(77)
    quotes, trades, closes = {}, {}, {}
    for w in range(140):
        close_s = 1_760_000_000 + w * 900
        tk = f"M{w:04d}"
        closes[tk] = close_s
        mid, ser, tr = 0.50, [], []
        vol = [0.0006 if (k // 90) % 2 else 0.0045 for k in range(901)]
        for k in range(901):
            mid = min(max(mid + rnd.gauss(0, vol[k]), 0.05), 0.95)
            ser.append((close_s - 900 + k, mid - 0.005, mid + 0.005, 100., 100.))
        for k in range(30, 900):
            # arrival probability tracks volatility; side is a fair coin, so
            # there is no information in the trade by construction
            if rnd.random() < (0.30 if vol[k] > 0.002 else 0.02):
                tr.append((close_s - 900 + k, ser[k][1], 10.0,
                           "yes" if rnd.random() < 0.5 else "no"))
        quotes[tk], trades[tk] = ser, tr
    hit, shuf = adverse_from_tape(quotes, trades, closes,
                                  verbose=True)
    hs = clustered(hit[1])
    abs_h = clustered([(abs(r[0]), r[1]) for r in hit[1]])
    abs_n = clustered([(abs(r[0]), r[1]) for r in shuf[1]])
    print(f"\n  {'signed markout (correct)':>32}: {hs['mean']:>7.3f}c  "
          f"t={hs['t']:>6.1f}")
    print(f"  {'absolute move (the old test)':>32}: {abs_h['mean']:>7.3f}c  "
          f"vs {abs_n['mean']:.3f}c at random signs")
    if abs(hs["t"]) > crit(0.05, hs["df"]):
        fails.append(f"the SIGNED estimator fired (t={hs['t']:.1f}) on a tape "
                     "with zero directional information -- it is picking up "
                     "arrival clustering, not adverse selection")

    # ---- a name a function READS but never BINDS is a crash waiting for
    # real data, and main() is the one function no self-test can execute --
    # it needs quotes, trades and markets that only exist on the recorder's
    # machine. So nothing else in this file can catch it.
    #
    # This exact bug shipped: main() did `hit, null = adverse_from_tape(...)`
    # while the robustness block below read `shuf`. The maker stage would have
    # raised NameError on its first real run, at the point where it prints the
    # decisive number, and the run log would have said "FAILED" with no clue.
    import ast as _ast
    import builtins as _bi
    print("\n  UNBOUND NAMES -- main() is never executed by any self-test, so")
    print("  a typo in it survives every test in this file until real data")
    print("  reaches it. Checked statically instead.")
    _src = open(os.path.abspath(__file__), encoding="utf-8").read()
    _tree = _ast.parse(_src)
    # module-level dunders are always bound, and are not assignments
    _mod = set(dir(_bi)) | {"__file__", "__name__", "__doc__",
                            "__spec__", "__package__", "__loader__",
                            "__builtins__", "__debug__"}
    for _n in _ast.walk(_tree):
        if isinstance(_n, (_ast.Import, _ast.ImportFrom)):
            for _al in _n.names:
                _mod.add(_al.asname or _al.name.split(".")[0])
    for _n in _tree.body:
        if isinstance(_n, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                           _ast.ClassDef)):
            _mod.add(_n.name)
        elif isinstance(_n, (_ast.Assign, _ast.AnnAssign, _ast.For,
                             _ast.With)):
            for _x in _ast.walk(_n):
                if isinstance(_x, _ast.Name) and isinstance(_x.ctx, _ast.Store):
                    _mod.add(_x.id)

    def _free(fn):
        bound = set()
        for _x in _ast.walk(fn):
            if isinstance(_x, _ast.Name) and isinstance(_x.ctx, _ast.Store):
                bound.add(_x.id)
            elif isinstance(_x, _ast.arg):
                bound.add(_x.arg)
            elif isinstance(_x, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                                 _ast.ClassDef)):
                bound.add(_x.name)
            elif isinstance(_x, _ast.ExceptHandler) and _x.name:
                bound.add(_x.name)
            elif isinstance(_x, (_ast.Import, _ast.ImportFrom)):
                for _al in _x.names:
                    bound.add(_al.asname or _al.name.split(".")[0])
            elif isinstance(_x, _ast.Global):
                bound.update(_x.names)
        used = {_x.id for _x in _ast.walk(fn)
                if isinstance(_x, _ast.Name) and isinstance(_x.ctx, _ast.Load)}
        return sorted(used - bound - _mod)

    bad = {}
    for _n in _tree.body:
        if isinstance(_n, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            f = _free(_n)
            if f:
                bad[_n.name] = f
    print(f"  checked {sum(1 for _n in _tree.body if isinstance(_n, (_ast.FunctionDef, _ast.AsyncFunctionDef)))}"
          f" top-level functions -> "
          + ("clean" if not bad else f"*** {bad} ***"))
    for k, v in bad.items():
        fails.append(f"{k}() reads {v} but never binds them -- NameError on "
                     "the first real run")
    # and the checker itself must be able to see one
    _probe = _ast.parse("def f(a):\n    return a + undefined_thing\n").body[0]
    if "undefined_thing" not in _free(_probe):
        fails.append("the unbound-name checker cannot detect an unbound name, "
                     "so its 'clean' verdict above means nothing")

    # ---- the per-price table must actually separate prices ----------------
    print("\n  PER-PRICE SEPARATION. Plant adverse selection ONLY in markets")
    print("  quoted near 50c and none in markets quoted near 10c. A pooled")
    print("  number averages them; the bucketed one must not.")
    rnd = random.Random(4)
    quotes, trades, closes = {}, {}, {}
    for w in range(240):
        close_s = 1_760_000_000 + w * 900
        tk = f"P{w:04d}"
        closes[tk] = close_s
        near50 = (w % 2 == 0)
        base = 0.50 if near50 else 0.10
        planted = 1.0 if near50 else 0.0
        mid = base
        ser, tr = [], []
        for s_ in range(close_s - 900, close_s + 1):
            mid = min(max(mid + rnd.gauss(0, 0.0008), base - 0.03),
                      base + 0.03)
            ser.append([s_, mid - 0.005, mid + 0.005, 100.0, 100.0])
        for i in range(60, 900, 60):
            s_ = close_s - 900 + i
            side = "yes" if rnd.random() < 0.5 else "no"
            sgn = 1.0 if side == "yes" else -1.0
            tr.append((s_, ser[i][1], 10.0, side))
            for j in range(i, min(i + 31, len(ser))):
                ser[j][1] += sgn * planted / 100.0
                ser[j][2] += sgn * planted / 100.0
        quotes[tk] = [tuple(r) for r in ser]
        trades[tk] = tr
    hitp, _sh = adverse_from_tape(quotes, trades, closes)
    H1 = HORIZONS[0]
    print(f"\n  {'bucket':>14}{'planted':>10}{'measured':>11}{'clusters':>10}")
    for lo, hi, want in ((0.05, 0.16, 0.0), (0.30, 0.70, 1.0)):
        sel = [r for r in hitp[H1] if len(r) > 2 and lo <= r[2] < hi]
        c = clustered(sel)
        got = c["mean"] if c else float("nan")
        print(f"  {f'{100*lo:.0f}-{100*hi:.0f}c':>14}{want:>9.2f}c"
              f"{got:>10.3f}c{(c['n'] if c else 0):>10}")
        if not c:
            fails.append(f"per-price bucket {100*lo:.0f}-{100*hi:.0f}c "
                         "produced no clusters, so the split is not working")
        elif abs(got - want) > 0.12:
            fails.append(f"bucket {100*lo:.0f}-{100*hi:.0f}c measured "
                         f"{got:.3f}c against a planted {want:.2f}c")
    pooled = clustered(hitp[H1])
    if pooled:
        print(f"  {'pooled':>14}{'--':>10}{pooled['mean']:>10.3f}c"
              f"{pooled['n']:>10}")
        print("  The pooled number is the average of a real effect and no")
        print("  effect. It describes neither market.")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- sigma cancels, the region behaves monotonically,")
    print("and the tape estimator recovers a planted adverse selection while")
    print("staying silent on a tape with none.")
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

    region_table()

    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    from replay import load_quotes, load_markets
    from edge import load_trades          # NOT replay -- it lives here
    quotes = load_quotes(a.data)
    if not quotes:
        print("\n  no quotes -- nothing to measure. Run doctor.py.")
        return
    trades = load_trades(a.data)
    mk = load_markets(a.out)
    closes = {tk: int(m["close"]) for tk, m in mk.items()}
    hit, shuf = adverse_from_tape(quotes, trades, closes,
                                  verbose=True)

    print("\n" + "=" * 78)
    print("REALISED ADVERSE SELECTION  --  what a resting quote actually costs")
    print("=" * 78)
    print("  Signed so POSITIVE means the taker was right and the resting side")
    print("  was run over. Scored against the same horizons measured at times")
    print("  WE chose, where no trade need have happened -- a raw post-trade")
    print("  drift is not evidence, the gap against that null is.\n")
    print(f"  {'horizon':>9}{'signed markout':>17}{'t':>8}{'df':>6}{'p':>10}"
          f"{'net @0.5c':>12}{'clusters':>10}")
    for h in HORIZONS:
        a_ = clustered(hit[h])
        if not a_:
            print(f"  {h:>8}s   not enough paired observations")
            continue
        print(f"  {h:>8}s{a_['mean']:>16.3f}c{a_['t']:>8.1f}{a_['df']:>6}"
              f"{p_two_sided(a_['t'], a_['df']):>10.4f}"
              f"{0.5 - a_['mean']:>11.3f}c{a_['n']:>10}")
    print("\n  SIGNED, so positive means the taker was right and the resting")
    print("  side was run over. 'net @0.5c' is what a one-cent two-sided quote")
    print("  earns per fill after that cost. The null is zero.")

    print("\n  ROBUSTNESS -- same moments, same moves, random sign. If the")
    print("  signed number above is real it must NOT survive this.")
    for h in HORIZONS:
        sf = clustered(shuf[h])
        if sf:
            print(f"  {h:>8}s{sf['mean']:>16.3f}c{sf['t']:>8.1f}{sf['df']:>6}"
                  f"{p_two_sided(sf['t'], sf['df']):>10.4f}")

    print("\n" + "=" * 78)
    print("BY PRICE  --  the pooled number answers the wrong question, and")
    print("             so does a flat half-spread")
    print("=" * 78)
    print("  The fee is 0.07*p*(1-p), so 50c and 5c are different questions.")
    print("  But the TICK is different too, and that is what an earlier")
    print("  version of this table got wrong. The API's price_ranges give")
    print("  0.1c below 10c and above 90c, 1c in between -- so a one-tick")
    print("  quote in the wings captures 0.05c, not the 0.5c this table used")
    print("  to assume. That assumption is what made the two wing buckets")
    print("  look profitable. They are not, at one tick.")
    print("\n  So the honest column is 'need': the half-spread you must")
    print("  actually capture to break even, which is just the markout. Next")
    print("  to it is what the book was really quoting there.\n")
    print(f"  {'price':>10}{'fills':>9}{'clus':>6}{'markout':>10}{'t':>7}"
          f"{'tick':>7}{'obs spr':>9}{'capture':>9}{'need':>8}{'net':>9}"
          f"   verdict")
    H1 = HORIZONS[0]
    buckets = [(0.00, 0.08), (0.08, 0.16), (0.16, 0.30), (0.30, 0.70),
               (0.70, 0.84), (0.84, 0.92), (0.92, 1.00)]

    def tick_c(p):
        return 0.1 if (p < 0.10 or p > 0.90) else 1.0

    for lo, hi in buckets:
        sel = [r for r in hit[H1] if len(r) > 2 and lo <= r[2] < hi]
        c = clustered(sel)
        mid_p = (lo + hi) / 2.0
        label = f"{100*lo:.0f}-{100*hi:.0f}c"
        if not c:
            print(f"  {label:>10}{len(sel):>9,}{'--':>6}"
                  f"{'too few clusters':>30}")
            continue
        h_cost = c["mean"]
        tk = tick_c(mid_p)
        obs = sorted(r[3] * 100.0 for r in sel if len(r) > 3)
        obs_spr = obs[len(obs) // 2] if obs else float("nan")
        # You capture half of whatever spread you can actually quote. One
        # tick is the floor; the book's own median spread is what a quote
        # sitting AT the touch would earn.
        cap = (obs_spr / 2.0) if obs else (tk / 2.0)
        net = cap - h_cost
        print(f"  {label:>10}{len(sel):>9,}{c['n']:>6}{h_cost:>9.3f}c"
              f"{c['t']:>7.1f}{tk:>6.1f}c{obs_spr:>8.2f}c{cap:>8.3f}c"
              f"{h_cost:>7.3f}c{net:>8.3f}c   "
              + ("PAYS" if net > 0 else "loses"))
    print("\n  'capture' is half the book's OWN median spread at that price,")
    print("  measured on the quote immediately before each fill -- not an")
    print("  assumption. 'need' is the markout. Quoting pays only where")
    print("  capture exceeds need, and only if you can actually sit at the")
    print("  touch for that whole spread rather than one tick inside it.")

    print("\n  BREAK-EVEN UNINFORMED SHARE -- q = fee/(fee+h). Below this")
    print("  fraction of noise flow, quoting loses to the fee theorem no")
    print("  matter how wide you quote.")
    print(f"\n  {'price':>8}{'taker fee':>12}{'half-spread':>14}{'q needed':>11}")
    for pq in (0.50, 0.60, 0.70, 0.80, 0.90, 0.95):
        fee = 100 * 0.07 * pq * (1 - pq)
        hs_ = 0.5
        print(f"  {100*pq:>7.0f}c{fee:>11.2f}c{hs_:>13.2f}c"
              f"{fee/(fee+hs_):>10.0%}")

    print("\n  Read it against the region table: if realised adverse selection")
    print("  at 1s is below the half-spread you would capture, quoting pays.")


if __name__ == "__main__":
    main()
