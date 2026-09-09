#!/usr/bin/env python3
# VERSION: 2026-09-08-sc1
"""pinscale.py -- did the SCALE-IN RULE lose the money, or did CONCENTRATION?

THE HYPOTHESIS UNDER TEST, AND IT IS MINE, NOT THE OPERATOR'S
=============================================================
After the first live loss (KXNEAR15M, close 1788914700, three NO buys at
96.2c, 95.6c and 73.0c on ONE market, -$52.60) I wrote that the lesson was
"the scale-in rule reads a collapsing price as a discount and buys more".
That is a hypothesis. This file tries to REFUTE it.

If it is right, later buys must lose MORE OFTEN than first buys. If the loss
rate is flat in buy index, the rule is exonerated on entry quality and the
damage must have come from somewhere else -- most obviously that all three
fills were the SAME MARKET, so they could not fail to lose together.

THE POPULATION, AND WHY IT IS NOT THE LIVE ONE
==============================================
The live window is tau 3-30 s. In `results/pindata/rows.jsonl` that window,
after the live gates, contains 1,196 available trades over 83 closes and
**ZERO flips**. A zero-flip sample cannot answer a question about losses:
every "loss rate by X" is 0/n and every cap sweep is monotone in how many
contracts it buys. So the WIDE window is used: tau 3-60 s, same gates.

  * `rows.jsonl` stops at tau 60 BY CONSTRUCTION, not by truncation. With more
    than 60 s to run, none of the 60 settlement prints is locked yet, so
    `pindata.partial()` returns None. The brief's "tau up to 200" is the
    argument default in `pindata.py`; the data can never exceed 60.
  * tau 31-60 is a HARDER world than the live one -- the model is measured
    3.7x overconfident at 31-45 s and 10.9x at 46-60 s -- so flip rates here
    (~3%) are ~4x the live 0.90%. This is a STRESS population, not a forecast.
    Every rate below is a wide-window rate and is labelled as one.

WHAT DECIDES A CAP, AND WHY THE EXISTING ANSWER IS SUSPECT
==========================================================
Cap 3 went live on the strength of `pinstress.py`: "size 20 cap 3 earns 12%
more than cap 2 and is ruined a third as often." Read that file's `simulate()`:
it draws ONE Bernoulli per close at a FIXED rate and applies it to every buy in
the close. Two consequences follow as arithmetic, not opinion:

  1. The flip probability is IDENTICAL for every buy, so a later buy -- which
     the improve rule forces to be CHEAPER -- always has strictly higher EV.
     **Under that model a higher cap cannot lose. The conclusion was in the
     assumption.** This file's self-test proves that monotonicity.
  2. Every buy in a close is PERFECTLY correlated, so 3 buys on 3 tickers and
     3 buys on 1 ticker are indistinguishable. Tonight's loss was the second
     shape. The model that authorised cap 3 is blind to the exact thing that
     happened.

So both assumptions are measured here against the tape and the cap sweep is
re-run with the measured correlation instead of the assumed one.

n IS CLOSES. Per hard rule 4, every rate is aggregated to one observation per
close time before any test, and no significance is claimed below 30 clusters.
The MDE is printed BEFORE each estimate.

INPUTS  results/pindata/rows.jsonl (read-only)
OUTPUT  stdout; --out writes a copy.
Nothing under C:\\kals is read or written by this file.
"""
import argparse
import json
import math
import os
import random
import sys
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from engine import var_factor                                   # noqa: E402

ROWS = os.path.join(os.path.dirname(HERE), "results", "pindata", "rows.jsonl")

# ---- the live gate, copied from pinrun.py so this file stands alone --------
TAU_MIN = 3
TAU_LIVE_MAX = 30         # pinrun TAU_MAX
TAU_WIDE_MAX = 60         # the widest rows.jsonl can physically hold
PFLIP_MAX = 0.02          # pinrun: fair >= 0.98 (yes) or <= 0.02 (no)
EV_FLOOR = 0.003          # dollars per contract at MEASURED_FLIP
PRICE_CEILING = 0.988     # pinrun PRICE_CEILING
IMPROVE_BY = 0.005        # a later buy must be at least this much cheaper
MEASURED_FLIP = 0.0090    # 3 flips in 333 dear trades
FLIP_UPPER = 0.0231       # exact one-sided 95% Clopper-Pearson on 3 in 333
MIN_FILL_FRAC = 0.50
MIN_LEVEL = 1.0
BANK = 154.33
LOSS_ABORT = -90.0
LOSS_COUNT_ABORT = 3
MIN_CLUSTERS = 30         # hard rule: no significance claim below this


# ===========================================================================
# ARITHMETIC  (identical to pinrun/pinsize; re-derived here so this file
# stands alone, and the self-test pins each one to a hand-checked number)
# ===========================================================================
def billed_fee(p, n=1.0):
    """Kalshi taker fee, billed on the ORDER and ceilinged to $0.0001."""
    return math.ceil(0.07 * float(p) * (1.0 - float(p)) * float(n) * 10000.0) / 10000.0


def ev_per_contract(p, f):
    """Expected dollars per contract BEFORE fee at flip rate f.  Zero at p=1-f."""
    p = float(p)
    return (1.0 - f) * (1.0 - p) - f * p


def ev_order(p, n, f):
    return float(n) * ev_per_contract(p, f) - billed_fee(p, n)


def realised_order(p, n, flipped):
    gross = float(n) * ((-float(p)) if flipped else (1.0 - float(p)))
    return gross - billed_fee(p, n)


def _phi(z):
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def move_sd(sigma, r):
    """SD of the mean of the r unpublished prints, on required_move's scale."""
    if r <= 0 or sigma <= 0:
        return 0.0
    return float(sigma) * math.sqrt(var_factor(int(r), [1.0])) * (60.0 / float(r))


def p_flip_model(row):
    """The model's own probability that the favoured side flips."""
    sd = move_sd(row["sig"], row["r"])
    if sd <= 0.0:
        return 0.0
    return _phi(-abs(row["req"]) / sd)


def cp_upper(k, n, conf=0.95):
    """Exact one-sided Clopper-Pearson upper bound on a binomial rate."""
    if n <= 0:
        return 1.0
    if k >= n:
        return 1.0

    def tail(p):
        tot = 0.0
        for i in range(k + 1):
            tot += math.comb(n, i) * (p ** i) * ((1.0 - p) ** (n - i))
        return tot
    lo, hi = k / float(n), 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if tail(mid) > 1.0 - conf:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def two_prop_z(k1, n1, k2, n2):
    """One-sided z for p2 > p1, pooled variance.  None if degenerate."""
    if n1 <= 0 or n2 <= 0:
        return None
    p1, p2 = k1 / float(n1), k2 / float(n2)
    pp = (k1 + k2) / float(n1 + n2)
    se = math.sqrt(pp * (1.0 - pp) * (1.0 / n1 + 1.0 / n2))
    if se <= 0.0:
        return None
    return (p2 - p1) / se


def _z_for_alpha(alpha):
    lo, hi = 0.0, 8.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if 1.0 - _phi(mid) > alpha:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def mde_two_prop(n1, n2, p0, alpha=0.05, power=0.80, draws=4000, seed=11):
    """Smallest ABSOLUTE rise in rate (from p0 to p0+d) in group 2 that a
    one-sided two-proportion test detects `power` of the time.  Simulated
    rather than closed-form because the counts here are tiny and the normal
    approximation is exactly what would flatter them.  Returns None if even
    d = 1-p0 cannot reach the required power."""
    rng = random.Random(seed)
    zc = _z_for_alpha(alpha)

    def pwr(d):
        p2 = min(1.0, p0 + d)
        hit = 0
        for _ in range(draws):
            k1 = sum(1 for _ in range(n1) if rng.random() < p0)
            k2 = sum(1 for _ in range(n2) if rng.random() < p2)
            z = two_prop_z(k1, n1, k2, n2)
            if z is not None and z >= zc:
                hit += 1
        return hit / float(draws)

    if pwr(1.0 - p0) < power:
        return None
    lo, hi = 0.0, 1.0 - p0
    for _ in range(14):
        mid = 0.5 * (lo + hi)
        if pwr(mid) >= power:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


# ===========================================================================
# LOAD
# ===========================================================================
def eligible(path=ROWS, tau_max=TAU_WIDE_MAX, verbose=True):
    """Every moment pinrun's gates would have let through, grouped by close."""
    seen = 0
    kept, cut = [], Counter()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            seen += 1
            try:
                d = json.loads(line)
            except Exception:                                   # noqa: BLE001
                cut["unparsed"] += 1
                continue
            if not (TAU_MIN <= d["tau"] <= tau_max):
                cut["tau"] += 1
                continue
            if p_flip_model(d) > PFLIP_MAX:
                cut["p_flip"] += 1
                continue
            if float(d["price"]) > PRICE_CEILING:
                cut["ceiling"] += 1
                continue
            e = ev_per_contract(d["price"], MEASURED_FLIP) - billed_fee(d["price"])
            if e < EV_FLOOR:
                cut["ev"] += 1
                continue
            kept.append(d)
    kept.sort(key=lambda d: (d["close"], d["sec"], d["tk"]))
    closes = defaultdict(list)
    for d in kept:
        closes[d["close"]].append(d)
    if verbose:
        print(f"  read {seen:,} rows from {path}")
        print(f"  gate  tau {TAU_MIN}-{tau_max}s               dropped {cut['tau']:,}")
        print(f"  gate  model p_flip <= {PFLIP_MAX}       dropped {cut['p_flip']:,}")
        print(f"  gate  price <= {PRICE_CEILING}           dropped {cut['ceiling']:,}")
        print(f"  gate  EV >= {100*EV_FLOOR:.1f}c @ {100*MEASURED_FLIP:.2f}%    "
              f"dropped {cut['ev']:,}")
        print(f"  ELIGIBLE {len(kept):,} available trades over {len(closes)} closes")
    return dict(closes)


# ===========================================================================
# THE REPLAY -- pinrun's rule, exactly
# ===========================================================================
def replay(closes, cap, size=1.0, one_per_ticker=False, improve=IMPROVE_BY):
    """Walk each close in time order and apply the live scale-in rule.

    pinrun keys `fired` by CLOSE, not by ticker, so `prev["best"]` is the
    cheapest price paid ANYWHERE in that close.  A second buy on a DIFFERENT
    market -- and even on the OTHER SIDE of the same market -- must still be
    IMPROVE_BY below it.  That is reproduced here rather than corrected,
    because reproducing the live rule is the whole point.

    `one_per_ticker` is the counterfactual: same rule, but at most one buy per
    market per close.
    """
    buys = []
    for cs in sorted(closes):
        best = None
        n = 0
        used = set()
        for row in closes[cs]:
            if n >= cap:
                break
            if one_per_ticker and row["tk"] in used:
                continue
            price = float(row["price"])
            if best is not None and price >= best - improve:
                continue
            avail = float(row["size"])
            take = min(float(size), avail)
            if take < max(MIN_LEVEL, MIN_FILL_FRAC * float(size)):
                continue
            buys.append(dict(close=cs, idx=n + 1, tk=row["tk"],
                             sr=row.get("sr", ""), price=price, n=take,
                             flip=bool(row["flip"]), tau=int(row["tau"]),
                             side_yes=bool(row.get("side_yes", True)),
                             pmodel=p_flip_model(row),
                             improve=(0.0 if best is None else best - price)))
            used.add(row["tk"])
            best = price if best is None else min(best, price)
            n += 1
    return buys


def by_close(buys):
    d = defaultdict(list)
    for b in buys:
        d[b["close"]].append(b)
    return dict(d)


def close_pnl(bs, realised=True, flip_rate=None):
    if realised:
        return sum(realised_order(b["price"], b["n"], b["flip"]) for b in bs)
    return sum(ev_order(b["price"], b["n"], flip_rate) for b in bs)


# ===========================================================================
# CORRELATION MODEL -- measured, not assumed
# ===========================================================================
def coflip_structure(closes):
    """For each (close, ticker) take the FIRST eligible offer -- the one the
    rule would actually buy -- and measure how often two DIFFERENT tickers in
    the same close both lose.  This is the number `pinstress.simulate()`
    assumes is 1.0."""
    first = {}
    for cs, rows in closes.items():
        for d in rows:
            k = (cs, d["tk"])
            if k not in first:
                first[k] = bool(d["flip"])
    per_close = defaultdict(list)
    for (cs, tk), fl in first.items():
        per_close[cs].append(fl)
    tot = sum(len(v) for v in per_close.values())
    nfl = sum(1 for v in per_close.values() for x in v if x)
    pairs = both = disc = 0
    for v in per_close.values():
        for i in range(len(v)):
            for j in range(i + 1, len(v)):
                pairs += 1
                if v[i] and v[j]:
                    both += 1
                elif v[i] != v[j]:
                    disc += 1
    cond = (2.0 * both / (2.0 * both + disc)) if (2 * both + disc) else float("nan")
    return dict(ticker_closes=tot, flips=nfl,
                marginal=(nfl / tot if tot else float("nan")),
                pairs=pairs, both=both, discordant=disc, cond_coflip=cond,
                per_close=dict(per_close))


def inject(buys_by_close, flip_rate, cond_coflip, rng):
    """Draw outcomes with the MEASURED within-close correlation.

    Two-parameter mixture: with probability q the close is 'shocked' and each
    distinct TICKER in it flips independently with probability a; otherwise
    nothing flips.  Then

        marginal per ticker      = q*a          = flip_rate
        P(partner flips | flips) = q*a^2/(q*a)  = a = cond_coflip

    so a = cond_coflip and q = flip_rate/a.  cond_coflip = 1.0 reproduces
    pinstress exactly (one shock, everything in the close flips together).
    Buys on the SAME ticker share that ticker's draw -- unless they are on
    OPPOSITE sides, in which case exactly one of them loses, always.
    """
    a = float(cond_coflip)
    if a <= 0.0:
        a = 1e-9
    q = min(1.0, float(flip_rate) / a)
    out = {}
    for cs, bs in buys_by_close.items():
        shocked = rng.random() < q
        tk_flip = {}
        first_side = {}
        for b in bs:
            if b["tk"] not in tk_flip:
                tk_flip[b["tk"]] = shocked and (rng.random() < a)
                first_side[b["tk"]] = b["side_yes"]
        res = []
        for b in bs:
            base = tk_flip[b["tk"]]
            res.append(base if b["side_yes"] == first_side[b["tk"]]
                       else (not base))
        out[cs] = res
    return out


def run_account(buys_by_close, draws, flip_rate, cond_coflip, bank=BANK,
                abort=LOSS_ABORT, loss_count=LOSS_COUNT_ABORT, seed=7):
    """Chronological account walk with the live brakes.  Returns the
    distribution of final realised P&L and the ruin/halt rates."""
    rng = random.Random(seed)
    order = sorted(buys_by_close)
    fin, halts, ruins, worsts = [], 0, 0, []
    for _ in range(draws):
        outc = inject(buys_by_close, flip_rate, cond_coflip, rng)
        cash = float(bank)
        realised = 0.0
        losses = 0
        halted = False
        worst = 0.0
        for cs in order:
            if halted:
                break
            bs = buys_by_close[cs]
            fl = outc[cs]
            got = 0.0
            for b, lost in zip(bs, fl):
                cost = b["n"] * b["price"] + billed_fee(b["price"], b["n"])
                if cost > cash:
                    continue
                cash -= cost
                if lost:
                    losses += 1
                    got -= cost
                    realised -= cost
                else:
                    cash += b["n"]
                    got += b["n"] - cost
                    realised += b["n"] - cost
                if realised <= abort or losses >= loss_count:
                    halted = True
                    break
            worst = min(worst, got)
        fin.append(realised)
        worsts.append(worst)
        if halted:
            halts += 1
        if cash < 1.0:
            ruins += 1
    fin.sort()
    return dict(median=fin[len(fin) // 2], mean=sum(fin) / len(fin),
                p05=fin[int(0.05 * len(fin))], p95=fin[int(0.95 * len(fin))],
                halt=halts / float(draws), ruin=ruins / float(draws),
                worst_close=sum(worsts) / len(worsts),
                worst_close_min=min(worsts))


def boot_diff(a_vals, b_vals, draws=4000, seed=3):
    """Cluster bootstrap on the difference of two per-close rate vectors."""
    rng = random.Random(seed)
    out = []
    na, nb = len(a_vals), len(b_vals)
    if na == 0 or nb == 0:
        return float("nan"), float("nan")
    for _ in range(draws):
        aa = sum(a_vals[rng.randrange(na)] for _ in range(na)) / na
        bb = sum(b_vals[rng.randrange(nb)] for _ in range(nb)) / nb
        out.append(bb - aa)
    out.sort()
    return out[int(0.025 * draws)], out[int(0.975 * draws)]


# ===========================================================================
# SELF-TEST -- plant a known answer, and find NOTHING in a null world
# ===========================================================================
def _row(price=0.95, size=100.0, flip=False, close=1000, sec=0, tk="A",
         sig=1.0, r=10, req=-40.0, tau=10, side_yes=True):
    return {"tk": tk, "sr": "S", "close": close, "sec": sec, "tau": tau,
            "r": r, "price": price, "size": size, "req": req, "sig": sig,
            "flip": flip, "side_yes": side_yes}


def selftest():
    print("SELF-TEST -- pinscale")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # ---- arithmetic, pinned to hand-checked numbers -----------------------
    ck(abs(billed_fee(0.16, 12.37) - 0.1164) < 1e-9,
       "fee matches the operator's real charge (12.37 @ 0.16 -> $0.1164)")
    ck(abs(ev_per_contract(0.991, 0.009)) < 1e-12,
       "EV is exactly zero at price = 1 - flip rate")
    ck(realised_order(0.95, 20, True) < -18.9,
       "a 20-lot at 95c that flips loses the whole $19 stake plus fee")
    ck(abs(cp_upper(3, 333) - 0.0231) < 0.0005,
       f"Clopper-Pearson 3/333 -> 2.31% ({100*cp_upper(3,333):.2f}%)")

    # ---- the replay reproduces pinrun's rule ------------------------------
    cl = {1: [_row(price=0.96, sec=1), _row(price=0.958, sec=2),
              _row(price=0.95, sec=3), _row(price=0.90, sec=4)]}
    b = replay(cl, cap=4)
    ck([round(x["price"], 3) for x in b] == [0.96, 0.95, 0.90],
       f"improve rule skips 95.8c (only 0.2c better) and takes 96/95/90 "
       f"({[round(x['price'], 3) for x in b]})")
    ck([x["idx"] for x in b] == [1, 2, 3], "buy index counts 1,2,3")
    ck(len(replay(cl, cap=2)) == 2, "cap 2 stops after two buys")
    ck(abs(b[1]["improve"] - 0.01) < 1e-9,
       "the recorded improvement is measured from the BEST price so far")

    # ---- one-per-ticker refuses a repeat, allows a different market -------
    cl2 = {1: [_row(price=0.96, sec=1, tk="A"), _row(price=0.94, sec=2, tk="A"),
               _row(price=0.92, sec=3, tk="B")]}
    ck([x["tk"] for x in replay(cl2, 3)] == ["A", "A", "B"],
       "the LIVE rule happily buys the same market twice")
    ck([x["tk"] for x in replay(cl2, 3, one_per_ticker=True)] == ["A", "B"],
       "one-per-ticker refuses the repeat and keeps the other market")

    # ---- the opposite-side trap the live rule can walk into ---------------
    cl3 = {1: [_row(price=0.96, sec=1, tk="A", side_yes=True),
               _row(price=0.80, sec=2, tk="A", side_yes=False)]}
    bb = replay(cl3, 2)
    ck(len(bb) == 2 and bb[0]["side_yes"] != bb[1]["side_yes"],
       "the live rule will buy BOTH sides of one market if the price 'improves'")
    ck(bb[0]["price"] + bb[1]["price"] > 1.0,
       f"and both sides cost {100*(bb[0]['price']+bb[1]['price']):.0f}c for a "
       f"$1.00 payout -- a locked loss, by arithmetic")

    # ---- PLANT: later buys really are worse.  The test must SEE it. -------
    planted = {}
    rng = random.Random(101)
    for i in range(240):
        lose_late = rng.random() < 0.40
        planted[i] = [_row(price=0.96, sec=1, tk=f"T{i}a", close=i, flip=False),
                      _row(price=0.90, sec=2, tk=f"T{i}b", close=i,
                           flip=lose_late)]
    pb = by_close(replay(planted, 2))
    a1 = [1.0 if any(x["flip"] for x in v if x["idx"] == 1) else 0.0
          for v in pb.values()]
    a2 = [1.0 if any(x["flip"] for x in v if x["idx"] >= 2) else 0.0
          for v in pb.values() if any(x["idx"] >= 2 for x in v)]
    z = two_prop_z(int(sum(a1)), len(a1), int(sum(a2)), len(a2))
    ck(z is not None and z > 3.0,
       f"PLANTED 40% late-buy loss rate is detected (z = {z:.1f})")
    lo, hi = boot_diff(a1, a2)
    ck(lo > 0.0, f"and its bootstrap CI excludes zero ([{lo:+.3f},{hi:+.3f}])")

    # ---- NULL: same rate at both indices.  The test must find NOTHING. ----
    fp = 0
    trials = 150
    for s in range(trials):
        nul = {}
        rg = random.Random(900 + s)
        for i in range(240):
            nul[i] = [_row(price=0.96, sec=1, tk=f"N{i}a", close=i,
                           flip=rg.random() < 0.05),
                      _row(price=0.90, sec=2, tk=f"N{i}b", close=i,
                           flip=rg.random() < 0.05)]
        nb = by_close(replay(nul, 2))
        n1 = [1.0 if any(x["flip"] for x in v if x["idx"] == 1) else 0.0
              for v in nb.values()]
        n2 = [1.0 if any(x["flip"] for x in v if x["idx"] >= 2) else 0.0
              for v in nb.values() if any(x["idx"] >= 2 for x in v)]
        zz = two_prop_z(int(sum(n1)), len(n1), int(sum(n2)), len(n2))
        if zz is not None and zz >= 1.645:
            fp += 1
    ck(fp <= 0.11 * trials,
       f"NULL world (no index effect) fires {fp}/{trials} = "
       f"{100.0*fp/trials:.1f}% of the time at a nominal alpha of 5% -- the "
       f"test is not manufacturing an effect")

    # ---- the MDE is honest about tiny samples ----------------------------
    small = mde_two_prop(118, 94, 0.034, draws=600, seed=5)
    big = mde_two_prop(5000, 5000, 0.034, draws=600, seed=5)
    ck(small is not None and big is not None and small > 3.0 * big,
       f"MDE shrinks with n (118v94: {100*small:.1f}pp, 5000v5000: "
       f"{100*big:.1f}pp)")

    # ---- pinstress's model CANNOT penalise a higher cap.  Prove it. ------
    mono = {}
    for i in range(60):
        mono[i] = [_row(price=0.96, sec=1, tk=f"M{i}a", close=i),
                   _row(price=0.94, sec=2, tk=f"M{i}b", close=i),
                   _row(price=0.92, sec=3, tk=f"M{i}c", close=i)]
    evs = []
    for cap in (1, 2, 3):
        bs = replay(mono, cap, size=20.0)
        evs.append(sum(ev_order(x["price"], x["n"], MEASURED_FLIP) for x in bs))
    ck(evs[0] < evs[1] < evs[2],
       f"under a uniform per-close flip rate, EV rises with every cap "
       f"({evs[0]:.1f} < {evs[1]:.1f} < {evs[2]:.1f}) -- the cap sweep that "
       f"authorised cap 3 could not have come out any other way")

    # ---- correlation: same ticker is strictly worse than spread ----------
    rgs = random.Random(4)
    conc = {i: [_row(price=0.95, sec=1, tk="X", close=i),
                _row(price=0.94, sec=2, tk="X", close=i),
                _row(price=0.93, sec=3, tk="X", close=i)] for i in range(400)}
    spre = {i: [_row(price=0.95, sec=1, tk="X", close=i),
                _row(price=0.94, sec=2, tk="Y", close=i),
                _row(price=0.93, sec=3, tk="Z", close=i)] for i in range(400)}

    def _sd(bc):
        o = inject(bc, 0.05, 0.05, rgs)
        v = [sum(realised_order(b["price"], b["n"], f)
                 for b, f in zip(bc[cs], o[cs])) for cs in bc]
        m = sum(v) / len(v)
        return math.sqrt(sum((x - m) ** 2 for x in v) / len(v)), min(v)
    sc, wc = _sd(by_close(replay(conc, 3, size=20.0)))
    ss, ws = _sd(by_close(replay(spre, 3, size=20.0)))
    ck(sc > 1.4 * ss,
       f"3 buys on ONE market swing far wider than 3 on three "
       f"(sd ${sc:.2f} vs ${ss:.2f})")
    ck(wc < ws, f"and its worst close is worse (${wc:.2f} vs ${ws:.2f})")

    # ---- inject() honours its own calibration ---------------------------
    rg2 = random.Random(21)
    bc = by_close(replay({i: [_row(price=0.95, sec=1, tk="P", close=i),
                              _row(price=0.94, sec=2, tk="Q", close=i)]
                          for i in range(4000)}, 2, size=1.0))
    tot = flips = both = one = 0
    for _ in range(3):
        o = inject(bc, 0.06, 0.30, rg2)
        for cs in bc:
            f = o[cs]
            tot += len(f)
            flips += sum(1 for x in f if x)
            if f[0] and f[1]:
                both += 1
            elif f[0] != f[1]:
                one += 1
    marg = flips / tot
    cond = 2.0 * both / (2.0 * both + one) if (2 * both + one) else 0.0
    ck(abs(marg - 0.06) < 0.008, f"injected marginal rate is 6% ({100*marg:.2f}%)")
    ck(abs(cond - 0.30) < 0.05,
       f"injected co-flip is the 30% asked for ({100*cond:.1f}%)")

    # ---- a NULL WORLD for the whole concentration claim ------------------
    # if outcomes are drawn INDEPENDENTLY per buy, one-per-market must buy
    # nothing at all in variance terms.
    rg3 = random.Random(33)
    same = by_close(replay(conc, 3, size=20.0))
    v_ind = []
    for cs in same:
        v_ind.append(sum(realised_order(b["price"], b["n"], rg3.random() < 0.05)
                         for b in same[cs]))
    m = sum(v_ind) / len(v_ind)
    sd_ind = math.sqrt(sum((x - m) ** 2 for x in v_ind) / len(v_ind))
    ck(sd_ind < sc,
       f"NULL: with INDEPENDENT outcomes the same three same-market buys have "
       f"a smaller spread (${sd_ind:.2f} < ${sc:.2f}) -- the variance result "
       f"is the correlation, not the count")

    # ---- the loss-COUNT brake binds, and a null where it cannot ---------
    brake_world = {i: [_row(price=0.90, sec=1, tk="B", close=i),
                       _row(price=0.89, sec=2, tk="B", close=i),
                       _row(price=0.88, sec=3, tk="B", close=i)]
                   for i in range(200)}
    bw = by_close(replay(brake_world, 3, size=20.0))
    on = run_account(bw, 400, 0.05, 1.0, loss_count=3, seed=8)
    off = run_account(bw, 400, 0.05, 1.0, loss_count=10 ** 9, seed=8)
    ck(on["halt"] > 0.5 and off["halt"] < on["halt"],
       f"the 3-loss brake fires when 3 same-market buys lose together "
       f"({100*on['halt']:.0f}% halted) and far less without it "
       f"({100*off['halt']:.0f}%)")
    calm = {i: [_row(price=0.90, sec=1, tk="C", close=i)] for i in range(200)}
    cw = by_close(replay(calm, 1, size=20.0))
    ck(run_account(cw, 300, 0.0, 1.0, loss_count=3, seed=9)["halt"] == 0.0,
       "NULL: with a zero flip rate no brake ever fires")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ===========================================================================
# REPORT
# ===========================================================================
def _rate(k, n):
    return (100.0 * k / n) if n else float("nan")


def report(path=ROWS, draws=3000, size=20.0):
    out = []

    def P(s=""):
        print(s)
        out.append(s)

    P("=" * 78)
    P("pinscale -- is the SCALE-IN RULE the problem, or is CONCENTRATION?")
    P("=" * 78)
    P()
    P("THE HYPOTHESIS: 'the scale-in rule reads a collapsing price as a")
    P("discount and buys more.'  If true, LATER buys lose more often than")
    P("FIRST buys.  Everything below tries to refute that.")
    P()

    P("-" * 78)
    P("POPULATION")
    P("-" * 78)
    live = eligible(path, TAU_LIVE_MAX, verbose=False)
    lb = replay(live, 3, size=size)
    P(f"  LIVE window tau {TAU_MIN}-{TAU_LIVE_MAX}s: "
      f"{sum(len(v) for v in live.values()):,} available trades, "
      f"{len(live)} closes,")
    P(f"    {sum(1 for b in lb if b['flip'])} flips among {len(lb)} buys.")
    P("    ZERO flips -> every loss-rate question is 0/n here.  Unusable.")
    P()
    P(f"  WIDE window tau {TAU_MIN}-{TAU_WIDE_MAX}s (used for everything below):")
    closes = eligible(path, TAU_WIDE_MAX, verbose=True)
    P("    rows.jsonl CANNOT hold tau > 60: with more than 60s to run no")
    P("    settlement print is locked yet and pindata.partial() returns None.")
    P("    'tau up to 200' is pindata's argument default, not the data.")
    P("    tau 31-60 is a HARDER world -- the model is 3.7x overconfident at")
    P("    31-45s and 10.9x at 46-60s -- so rates here are ~4x live.  This is")
    P("    a STRESS population.  No number below is a live forecast.")
    P()

    buys3 = replay(closes, 3, size=size)
    bc3 = by_close(buys3)

    # ---------------- Q1 -------------------------------------------------
    P("=" * 78)
    P("Q1  LOSS RATE BY BUY INDEX -- does the scale-in rule buy worse trades?")
    P("=" * 78)
    idx_n, idx_f = Counter(), Counter()
    idx_cl = defaultdict(set)
    idx_px = defaultdict(list)
    for b in replay(closes, 4, size=size):
        idx_n[b["idx"]] += 1
        idx_f[b["idx"]] += 1 if b["flip"] else 0
        idx_cl[b["idx"]].add(b["close"])
        idx_px[b["idx"]].append(b["price"])
    a1 = [1.0 if any(x["flip"] for x in v if x["idx"] == 1) else 0.0
          for v in bc3.values()]
    a2 = [1.0 if any(x["flip"] for x in v if x["idx"] >= 2) else 0.0
          for v in bc3.values() if any(x["idx"] >= 2 for x in v)]
    n1, n2 = len(a1), len(a2)
    p0 = sum(a1) / n1 if n1 else 0.0
    mde = mde_two_prop(n1, n2, max(p0, 0.005), draws=1500, seed=17)
    P()
    P("  MDE FIRST, before any estimate.  Comparing 'the first buy lost' over")
    P(f"  {n1} closes with 'any later buy lost' over {n2} closes, at a base")
    P(f"  rate of {100*p0:.2f}%, one-sided alpha 0.05, 80% power:")
    if mde is None:
        P("    MDE: NOT REACHABLE at any effect size.  No power at all.")
    else:
        P(f"    MDE = {100*mde:+.1f} percentage points "
          f"({100*p0:.1f}% -> {100*(p0+mde):.1f}%, a "
          f"{(p0+mde)/max(p0, 1e-9):.1f}x rise).")
        P("    ANYTHING SMALLER IS INVISIBLE HERE.  A doubling of the")
        P("    later-buy loss rate would NOT be detected by this sample.")
    P()
    P("  buy index   buys   flips   loss rate   closes   95% upper   mean price")
    for i in sorted(idx_n):
        P(f"      {i}      {idx_n[i]:5d}   {idx_f[i]:5d}    "
          f"{_rate(idx_f[i], idx_n[i]):6.2f}%   {len(idx_cl[i]):5d}     "
          f"{100*cp_upper(idx_f[i], idx_n[i]):6.2f}%      "
          f"{100*sum(idx_px[i])/len(idx_px[i]):6.2f}c")
    P()
    P("  Clustered by close, ONE observation per close (hard rule 4):")
    P(f"    first buy lost           {int(sum(a1)):3d} / {n1:3d} closes = "
      f"{100*sum(a1)/n1:.2f}%")
    P(f"    ANY later buy lost       {int(sum(a2)):3d} / {n2:3d} closes = "
      f"{100*sum(a2)/n2 if n2 else float('nan'):.2f}%")
    z = two_prop_z(int(sum(a1)), n1, int(sum(a2)), n2)
    lo, hi = boot_diff(a1, a2)
    P(f"    difference               {100*(sum(a2)/n2 - sum(a1)/n1):+.2f} pp"
      f"   z = {z:+.2f}   cluster bootstrap 95% CI "
      f"[{100*lo:+.2f}, {100*hi:+.2f}] pp")
    P()
    both_cl = [v for v in bc3.values() if any(x["idx"] >= 2 for x in v)]
    f_first = sum(1 for v in both_cl if any(x["flip"] for x in v if x["idx"] == 1))
    f_late = sum(1 for v in both_cl if any(x["flip"] for x in v if x["idx"] >= 2))
    P("  MATCHED, on the SAME closes -- this separates 'later buys are worse'")
    P("  from 'closes that produce later buys are worse closes':")
    P(f"    of the {len(both_cl)} closes that produced a later buy,")
    P(f"      the FIRST buy lost on {f_first}; a LATER buy lost on {f_late}.")
    P()
    if n1 >= MIN_CLUSTERS and n2 >= MIN_CLUSTERS:
        if z is not None and z >= 1.645:
            P("  VERDICT: later buys DO lose more often.  Hypothesis SUPPORTED.")
        else:
            P("  VERDICT: NO DETECTABLE DIFFERENCE.  My hypothesis is NOT")
            P("  supported by this tape.  Given the MDE above that is 'no")
            P("  evidence', not 'no effect' -- a real effect smaller than the")
            P("  MDE would look exactly like this.")
    else:
        P(f"  VERDICT WITHHELD: below the {MIN_CLUSTERS}-cluster floor.")
    P()

    # ---------------- Q2 -------------------------------------------------
    P("=" * 78)
    P("Q2  CONDITIONAL ON THE PRICE DROP THAT QUALIFIED THE BUY")
    P("=" * 78)
    P("  Tonight's third buy came after a 22.6c drop (95.6c -> 73.0c).  Is a")
    P("  big drop more dangerous than a small one?")
    P()

    def bucket(x):
        c = 100.0 * x
        if c < 1.0:
            return "0.5-1c"
        if c < 3.0:
            return "1-3c"
        if c < 10.0:
            return "3-10c"
        return "10c+"

    order = ["0.5-1c", "1-3c", "3-10c", "10c+"]
    bn, bf = Counter(), Counter()
    bcl = defaultdict(set)
    bpr, bmk = defaultdict(list), defaultdict(list)
    for b in replay(closes, 4, size=size):
        if b["idx"] == 1:
            continue
        k = bucket(b["improve"])
        bn[k] += 1
        bf[k] += 1 if b["flip"] else 0
        bcl[k].add(b["close"])
        bpr[k].append(b["price"])
        if b["pmodel"] > 0:
            bmk[k].append((1.0 - b["price"]) / b["pmodel"])
    P("  drop bucket    buys  flips   loss rate   closes   mean price   "
      "median market/model")
    for k in order:
        s = sorted(bmk[k])
        mm = s[len(s) // 2] if s else float("nan")
        mp = (100 * sum(bpr[k]) / len(bpr[k])) if bpr[k] else float("nan")
        P(f"  {k:>10s}  {bn[k]:6d} {bf[k]:6d}   {_rate(bf[k], bn[k]):7.2f}%   "
          f"{len(bcl[k]):6d}    {mp:7.2f}c   {mm:15,.0f}x")
    P()
    P("  'market/model' is how many times the MARKET's implied chance we lose")
    P("  (1 - price) exceeds the MODEL's.  The MEDIAN is shown because the")
    P("  model's p_flip runs to 1e-60 on a dead-flat index, so the mean of the")
    P("  ratio is meaningless.  Tonight's third buy was 73.0c with a model")
    P("  p(lose) of 0.23%, so the market said 27.0% -- a ratio of 117x.")
    P()
    small_cl = set(c for k in ("0.5-1c", "1-3c") for c in bcl[k])
    big_cl = set(c for k in ("3-10c", "10c+") for c in bcl[k])
    ks = sum(bf[k] for k in ("0.5-1c", "1-3c"))
    ns = sum(bn[k] for k in ("0.5-1c", "1-3c"))
    kb = sum(bf[k] for k in ("3-10c", "10c+"))
    nb2 = sum(bn[k] for k in ("3-10c", "10c+"))
    P(f"  Pooled: small drops (<3c) {_rate(ks, ns):.2f}% of {ns} buys over "
      f"{len(small_cl)} closes;")
    P(f"          big drops (>=3c) {_rate(kb, nb2):.2f}% of {nb2} buys over "
      f"{len(big_cl)} closes.")
    zz = two_prop_z(ks, ns, kb, nb2)
    if min(len(small_cl), len(big_cl)) < MIN_CLUSTERS:
        P(f"  BELOW the {MIN_CLUSTERS}-cluster floor in an arm -- descriptive "
          f"only, no significance claimed.")
    elif zz is not None:
        P(f"  one-sided z (big > small) = {zz:+.2f}"
          f"{'  -- not significant' if zz < 1.645 else '  -- SIGNIFICANT'}")
    P("  With 4 buckets, the multiple-looks threshold for alpha 0.05 is")
    P("  |z| >= 2.24 (Bonferroni), not 1.64.")
    P()

    # ---------------- Q3 -------------------------------------------------
    P("=" * 78)
    P("Q3  THE CORRELATION THAT ACTUALLY HURT US")
    P("=" * 78)
    multi = [v for v in bc3.values() if len(v) >= 2]
    onetk = [v for v in multi if len(set(x["tk"] for x in v)) == 1]
    modal = Counter(max(Counter(x["tk"] for x in v).values())
                    for v in bc3.values())
    P(f"  closes with >= 2 buys (cap 3):            {len(multi)}")
    P(f"  ... all buys on ONE market, as tonight:   {len(onetk)}"
      f"  ({_rate(len(onetk), len(multi)):.1f}%)")
    P(f"  most buys landing on a single market:     "
      f"{dict(sorted(modal.items()))}")
    P()
    opp = [(v, i, j) for v in bc3.values()
           for i in range(len(v)) for j in range(i + 1, len(v))
           if v[i]["tk"] == v[j]["tk"] and v[i]["side_yes"] != v[j]["side_yes"]]
    P("  *** A DEFECT THE RULE ALLOWS, FOUND WHILE MEASURING THIS ***")
    P(f"  Times the rule bought BOTH SIDES of the SAME market in one close: "
      f"{len(opp)}")
    if opp:
        P("  pinrun keys `fired` by CLOSE, so the improve test compares a raw")
        P("  price against the cheapest paid anywhere in that close -- across")
        P("  markets AND across sides.  Every eligible price is above 50c, so")
        P("  YES + NO on one market always costs MORE than the $1.00 it pays.")
        for v, i, j in opp[:8]:
            aa, bb = v[i], v[j]
            cost = aa["price"] + bb["price"]
            P(f"    {aa['tk']}  {'YES' if aa['side_yes'] else 'NO':>3s} @"
              f"{100*aa['price']:.1f}c then "
              f"{'YES' if bb['side_yes'] else 'NO':>3s} @{100*bb['price']:.1f}c"
              f"  = {100*cost:.1f}c for $1.00  -> locked "
              f"-{100*(cost-1.0):.1f}c/contract")
    P()
    co = coflip_structure(closes)
    P("  HOW CORRELATED ARE TWO BUYS IN THE SAME CLOSE, REALLY?")
    P("  (first eligible offer per market per close -- the one we would buy)")
    P(f"    market-closes measured           {co['ticker_closes']}")
    P(f"    marginal loss rate               {100*co['marginal']:.2f}%")
    P(f"    cross-market pairs in a close    {co['pairs']}")
    P(f"    both lost                        {co['both']}")
    P(f"    exactly one lost                 {co['discordant']}")
    P(f"    P(the OTHER market also loses | this one loses) = "
      f"{100*co['cond_coflip']:.1f}%")
    P("    SAME market, same side:          100.0%, by definition")
    P()
    P("  pinstress.simulate() assumes that number is 100% for every pair in a")
    P(f"  close.  Measured, it is {100*co['cond_coflip']:.1f}% across markets "
      f"and 100% within one.")
    P("  So the model that authorised cap 3 CANNOT TELL tonight's shape (3")
    P("  buys, 1 market) apart from the ordinary shape (3 buys, 3 markets).")
    P()
    P("  THE COUNTERFACTUAL RULE: up to 3 buys per close, AT MOST ONE PER")
    P(f"  MARKET, improve rule unchanged.  Size {size:g} contracts.")
    P()
    hdr = ("  rule                     buys  closes   realised    worst   "
           "sd/close    E@0.90%    E@2.31%")
    P(hdr)

    def line(tag, bs):
        b = by_close(bs)
        r = [close_pnl(v) for v in b.values()]
        m = sum(r) / len(r)
        sd = math.sqrt(sum((x - m) ** 2 for x in r) / len(r))
        e09 = sum(close_pnl(v, False, MEASURED_FLIP) for v in b.values())
        e23 = sum(close_pnl(v, False, FLIP_UPPER) for v in b.values())
        P(f"  {tag:<22s} {len(bs):5d}  {len(b):5d}  ${sum(r):9.2f}  "
          f"${min(r):7.2f}  ${sd:8.2f}  ${e09:9.2f}  ${e23:9.2f}")
        return dict(real=sum(r), worst=min(r), sd=sd, e09=e09, e23=e23,
                    buys=len(bs))

    a_live = line("LIVE cap3 (any mkt)", replay(closes, 3, size=size))
    a_1tk = line("cap3, 1 per market", replay(closes, 3, size=size,
                                              one_per_ticker=True))
    line("LIVE cap2 (any mkt)", replay(closes, 2, size=size))
    P()
    P(f"  One-per-market gives up {100*(1-a_1tk['e09']/a_live['e09']):.1f}% of "
      f"expected profit at 0.90% and "
      f"{100*(1-a_1tk['e23']/a_live['e23']):.1f}% at 2.31%,")
    P(f"  and buys a worst close of ${a_1tk['worst']:.2f} instead of "
      f"${a_live['worst']:.2f} and a per-close sd of ${a_1tk['sd']:.2f} "
      f"instead of ${a_live['sd']:.2f}.")
    P()

    # ---------------- Q4 -------------------------------------------------
    P("=" * 78)
    P("Q4  THE CAP SWEEP, RE-RUN WHERE LOSSES EXIST")
    P("=" * 78)
    P("  The decision to deploy cap 3 came from a sweep on the tau 3-30")
    P("  window, which has ZERO flips, with losses injected at a rate that is")
    P("  the same for every buy.  Under that model a later (and therefore")
    P("  cheaper) buy has strictly higher EV, so a higher cap CANNOT lose.")
    P("  The self-test proves that monotonicity.  Here the same sweep runs on")
    P("  real flips, and then on injected flips with the MEASURED correlation.")
    P()
    P(hdr)
    for cap in (1, 2, 3, 4):
        line(f"cap{cap}", replay(closes, cap, size=size))
    P()
    P(f"  ACCOUNT SIMULATION.  Bank ${BANK:.2f}, size {size:g}, brakes: "
      f"-${abs(LOSS_ABORT):.0f} realised and {LOSS_COUNT_ABORT} losing trades.")
    P(f"  {draws:,} draws per cell.  Two correlation models:")
    P("    ASSUMED  co-flip 100%   -- what pinstress used")
    P(f"    MEASURED co-flip {100*co['cond_coflip']:.1f}% across markets, "
      f"100% within one -- what the tape says")
    P()
    for rate, tag in ((MEASURED_FLIP, "0.90% (measured)"),
                      (FLIP_UPPER, "2.31% (95% upper bound)")):
        P(f"  flip rate {tag}")
        P("    model      cap   median $    mean $    5th %ile   halted   "
          "ruined   mean worst close")
        for model, cc in (("ASSUMED ", 1.0), ("MEASURED", co["cond_coflip"])):
            for cap in (1, 2, 3, 4):
                bcx = by_close(replay(closes, cap, size=size))
                r = run_account(bcx, draws, rate, cc, seed=1000 + cap)
                P(f"    {model}   {cap}    ${r['median']:8.2f}  "
                  f"${r['mean']:8.2f}   ${r['p05']:8.2f}   "
                  f"{100*r['halt']:5.1f}%   {100*r['ruin']:5.1f}%   "
                  f"${r['worst_close']:7.2f}")
        P()
    P("  And the same account walk for the one-per-market variant at the")
    P("  measured correlation, which is the only place the rules can differ:")
    P("    rule                     median $   5th %ile   halted   "
      "mean worst close")
    for rate, tag in ((MEASURED_FLIP, "0.90%"), (FLIP_UPPER, "2.31%")):
        for flag, nm in ((False, "any market "), (True, "1 per market")):
            bcx = by_close(replay(closes, 3, size=size, one_per_ticker=flag))
            r = run_account(bcx, draws, rate, co["cond_coflip"], seed=55)
            P(f"    cap3 {nm} @{tag}   ${r['median']:8.2f}  "
              f"${r['p05']:8.2f}   {100*r['halt']:5.1f}%   "
              f"${r['worst_close']:7.2f}")
    P()

    # ---------------- Q5 -------------------------------------------------
    P("=" * 78)
    P("Q5  WHY THE CAP RANKING MOVED: THE 3-LOSS BRAKE AND CAP 3 WERE NEVER")
    P("    TESTED TOGETHER")
    P("=" * 78)
    P("  pinstress.simulate() halts on DOLLARS only (`realised <= loss_abort`).")
    P("  The loss-COUNT brake -- 3 losing trades, then stop -- was written")
    P("  into LOSS_PLAN.md and deployed AFTER that sweep ran.  Ablation on one")
    P("  population, so only the brake and the correlation change:")
    P()
    P("    brakes           correlation   cap   median $   5th %ile   halted")
    for lc, lct in ((10 ** 9, "$ only    "), (LOSS_COUNT_ABORT, "$ + 3 losses")):
        for cc, ct in (("ASSUMED ", 1.0), ("MEASURED", co["cond_coflip"])):
            for cap in (2, 3):
                bcx = by_close(replay(closes, cap, size=size))
                r = run_account(bcx, draws, MEASURED_FLIP, ct,
                                loss_count=lc, seed=1000 + cap)
                P(f"    {lct}     {cc}      {cap}   ${r['median']:8.2f}  "
                  f"${r['p05']:8.2f}   {100*r['halt']:5.1f}%")
    P()
    P("  With pinstress's brakes, cap 3 beats cap 2 -- this file REPRODUCES")
    P("  the number cap 3 was deployed on.  Add the brake that is actually")
    P("  live and the ranking reverses ON THIS POPULATION.")
    P()
    P("  *** AND NOW THE CHECK THAT NARROWS THAT CLAIM.  The wide window")
    P("  admits ~2x the buys per close, so it halts far more often than the")
    P("  live window would.  The SAME ablation on the tau 3-30 buy structure")
    P("  -- the population cap 3 was actually decided on, with losses injected")
    P("  so the zero-flip problem does not bite: ***")
    P()
    lw = eligible(path, TAU_LIVE_MAX, verbose=False)
    for cap in (1, 2, 3, 4):
        bb = by_close(replay(lw, cap, size=size))
        conc = sum(1 for v in bb.values()
                   if len(v) > 1 and len(set(x["tk"] for x in v)) == 1)
        P(f"    live-window cap {cap}: {sum(len(v) for v in bb.values())} buys "
          f"over {len(bb)} closes, at most {max(len(v) for v in bb.values())} "
          f"in a close, {conc} all-one-market")
    P()
    P("    brakes           correlation   cap   median $   5th %ile   halted")
    for lc, lct in ((10 ** 9, "$ only    "), (LOSS_COUNT_ABORT, "$ + 3 losses")):
        for cc, ct in (("ASSUMED ", 1.0), ("MEASURED", co["cond_coflip"])):
            for cap in (2, 3):
                bcx = by_close(replay(lw, cap, size=size))
                r = run_account(bcx, draws, MEASURED_FLIP, ct,
                                loss_count=lc, seed=1000 + cap)
                P(f"    {lct}     {cc}      {cap}   ${r['median']:8.2f}  "
                  f"${r['p05']:8.2f}   {100*r['halt']:5.1f}%")
    P()
    P("  ON THE LIVE WINDOW CAP 3 STILL WINS THE MEDIAN, brake or no brake.")
    P("  So cap 3 is NOT refuted, and I am not going to say it is.  What the")
    P("  brake costs cap 3 is TAIL and UPTIME, not median profit.  The wide-")
    P("  window reversal above is driven by trade COUNT, not by cap 3 being")
    P("  a worse rule, and quoting it as 'cap 3 is wrong' would be an error.")
    P()
    P("  THE MECHANISM.  The brake counts TRADES; the unit of information is a")
    P("  CLOSE.  How many losing TRADES one losing CLOSE delivers:")
    for tag, bs in (("LIVE cap3 (any market)", replay(closes, 3, size=size)),
                    ("cap3, 1 per market", replay(closes, 3, size=size,
                                                  one_per_ticker=True))):
        d = Counter(sum(1 for x in v if x["flip"])
                    for v in by_close(bs).values() if any(x["flip"] for x in v))
        P(f"    {tag:<24s} {dict(sorted(d.items()))}")
    P()
    for cap in (1, 2, 3, 4):
        bb = by_close(replay(closes, cap, size=size))
        conc = sum(1 for v in bb.values()
                   if len(v) > 1 and len(set(x["tk"] for x in v)) == 1)
        P(f"    cap {cap}: at most {max(len(v) for v in bb.values())} losing "
          f"trades from one close; {conc} closes put every buy on one market")
    P()
    P("  LOSS_PLAN.md calls three losses 'roughly a 1% event' at the 0.90%")
    P("  rate.  That arithmetic treats three losing TRADES as three")
    P("  independent draws.  Under cap 3 with same-market repeats they can be")
    P("  ONE draw, which is what happened live: three fills on KXNEAR15M,")
    P("  three losing trades, the whole brake budget spent by a single close.")
    P()
    P("  THE COST OF ONE-PER-MARKET, in trades:")
    a3 = replay(closes, 3, size=size)
    b3 = replay(closes, 3, size=size, one_per_ticker=True)
    ka = set((x["close"], x["tk"], x["price"], x["tau"]) for x in a3)
    kb = set((x["close"], x["tk"], x["price"], x["tau"]) for x in b3)
    ref = [x for x in a3 if (x["close"], x["tk"], x["price"], x["tau"]) not in kb]
    add = [x for x in b3 if (x["close"], x["tk"], x["price"], x["tau"]) not in ka]
    nl_ref = sum(1 for x in ref if x["flip"])
    nl_add = sum(1 for x in add if x["flip"])
    avoided = nl_ref - nl_add
    P(f"    refused {len(ref)} buys ({nl_ref} of them losers); admitted "
      f"{len(add)} replacements ({nl_add} losers).")
    P(f"    net {len(ref)-nl_ref-(len(add)-nl_add)} WINNING trades given up "
      f"for {avoided} losses avoided"
      + (f" = {(len(ref)-nl_ref-(len(add)-nl_add))/avoided:.0f} winners "
         f"refused per loss avoided." if avoided > 0 else "."))
    P(f"    profit destroyed: E@0.90% ${a_live['e09']:.2f} -> "
      f"${a_1tk['e09']:.2f} = -${a_live['e09']-a_1tk['e09']:.2f} over "
      f"{len(bc3)} closes = -${(a_live['e09']-a_1tk['e09'])/len(bc3):.3f}"
      f" per close.")
    P()
    P("  AND WHERE THAT BENEFIT ACTUALLY COMES FROM -- it is the brake, not")
    P("  better trades.  With the loss-count brake switched OFF the two rules")
    P("  are within a few percent of each other:")
    for flag, nm in ((False, "any market "), (True, "1 per market")):
        bcx = by_close(replay(closes, 3, size=size, one_per_ticker=flag))
        off = run_account(bcx, draws, MEASURED_FLIP, co["cond_coflip"],
                          loss_count=10 ** 9, seed=55)
        on = run_account(bcx, draws, MEASURED_FLIP, co["cond_coflip"],
                         loss_count=LOSS_COUNT_ABORT, seed=55)
        P(f"    cap3 {nm}  brake OFF median ${off['median']:8.2f} "
          f"(halt {100*off['halt']:4.1f}%)  |  brake ON median "
          f"${on['median']:8.2f} (halt {100*on['halt']:4.1f}%)")
    P("  One-per-market's median is UNCHANGED by the brake, because it can")
    P("  never spend more than one unit of the brake budget on one close.")
    P()
    P("  TONIGHT AGAINST THIS SAMPLE.  The five worst closes in the 118:")
    _w = sorted(close_pnl(v) for v in bc3.values())[:5]
    P(f"    {['$%.2f' % x for x in _w]}")
    P("    tonight, live: -$52.60.  Worse than every close in the sample, and")
    P(f"    88% of the ${1.00*size*3:.0f} modelled worst case for one close.")
    P()
    P("=" * 78)
    P("WHAT THIS DOES NOT MEASURE")
    P("=" * 78)
    P("  * tau 31-60 is not the live window.  Rates here are ~4x live and the")
    P("    RANKING of rules is what transfers, not the levels.")
    P("  * Only a handful of closes in this sample contain any loss at all, so")
    P("    every loss-rate comparison is underpowered by the MDE printed above.")
    P("  * pindata.Book.snapshot() reads yes_dollars/no_dollars where the tape")
    P("    carries yes_dollars_fp/no_dollars_fp, so the replayed books are")
    P("    delta-only and seeded empty.  That REMOVES offers, so this file")
    P("    sees fewer buying opportunities than really existed; it cannot")
    P("    invent one.  Conservative for opportunity count; whether it biases")
    P("    the loss RATE either way is NOT known and is not claimed here.")
    P("  * The race is not modelled.  26% of live orders fill nothing.")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows", default=ROWS)
    ap.add_argument("--draws", type=int, default=3000)
    ap.add_argument("--size", type=float, default=20.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")
    print()
    txt = report(a.rows, a.draws, a.size)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt + "\n")
        print(f"\n  written to {a.out}")


if __name__ == "__main__":
    main()
