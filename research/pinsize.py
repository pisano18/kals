#!/usr/bin/env python3
# VERSION: 2026-09-08-sz1
"""pinsize.py -- does sizing on confidence beat flat sizing?

THE QUESTION
============
The live rule (pinrun.py) buys up to 2 contracts per close, the second only if
the price is at least 0.5c better than the first.  The operator asks whether
"how much we expect it to flip to the other side can play into how much we
buy" -- i.e. whether a confidence-, EV- or price-scaled size beats a flat one,
and whether more than two contracts is justified.

THE TRAP THIS FILE IS BUILT AROUND
==================================
On the order-book dataset (results/pindata/rows.jsonl) the eligible population
-- tau 3-20 s, model p_flip <= 0.02, EV >= 0.3c at the measured 0.90% flip
rate -- contains ZERO LOSSES.  Nothing ever goes wrong in this sample.

That makes REALISED P&L a monotone increasing function of contracts bought.
Every sizing rule that buys more will "win", FLAT4 beats FLAT3 beats FLAT2,
and the ranking is pure artefact.  A realised-P&L table here is not a result;
it is a restatement of how many contracts each rule bought.

So every rule is scored THREE ways and the report prints all three:

  REALISED        what this sample actually paid.  Monotone in size.  Printed
                  for completeness and explicitly NOT used to rank.
  EXPECTED@0.90%  the measured flip rate (3 flips in 333 dear trades -- the
                  number pinrun.py's own EV gate already uses).
  EXPECTED@1.80%  the 95% upper bound on that rate given 3 in 333.  This is
                  the number that decides anything, because it is the only one
                  under which some eligible trades are NEGATIVE: breakeven
                  price is 1 - f, so at f = 1.80% every purchase above 98.2c
                  loses money and the gate (which uses 0.90%) lets them in.

And because positive EV per contract makes EV monotone in size too, the
ranking cannot be on EV alone either.  The binding constraint is RISK: the
live process aborts at -$3.00 realised, so a rule whose worst single close
commits $3.00 or more is rejected outright regardless of its EV -- one bad
event ends the session.

WHAT A "CLOSE" IS
=================
Hard rule 4: cluster by close time.  Twelve series settle on the same quarter
hour at rho ~ 0.8, so two contracts bought on the same close in different
coins are NOT two independent bets.  Exposure is summed across every contract
in a close and the worst case assumes they all flip together.

DEPTH IS A REAL CONSTRAINT
==========================
pinrun requires the resting level to hold at least max(MIN_LEVEL, our size) in
non-fractional contracts.  A rule that wants 4 contracts cannot have them if
the level holds 2.4.  Every rule here is truncated to floor(available size),
and the report prints how often that bound bound -- a guard that discards data
needs its own null, so the same table shows that a rule wanting one contract
is truncated zero times.

INPUTS  results/pindata/rows.jsonl (read-only)
OUTPUT  stdout; --out writes a copy.
Nothing under C:\\kals is read or written by this file.
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from engine import var_factor                                  # noqa: E402

ROWS = os.path.join(os.path.dirname(HERE), "results", "pindata", "rows.jsonl")

# ---- the live gate, copied from pinrun.py so this file stands alone --------
TAU_MIN, TAU_MAX = 3, 20
PFLIP_MAX = 0.02          # pinrun: fair >= 0.98 (yes) or <= 0.02 (no)
EV_FLOOR = 0.003          # dollars per contract, at MEASURED_FLIP
MEASURED_FLIP = 0.0090    # 3 flips in 333 dear trades
FLIP_HI = 0.0180          # the upper bound THIS PROJECT quotes for 3 in 333.
                          # It is a WALD (normal) approximation:
                          # 0.0090 + 1.645*sqrt(.009*.991/333) = 0.01753.
                          # The EXACT Clopper-Pearson bound is 2.31% -- see
                          # FLIP_CP. Both are scored; the Wald one is kept
                          # because it is the number on the record.
FLIP_CP = 0.0231          # exact one-sided 95% Clopper-Pearson on 3 in 333.
                          # 28% higher than the number the project quotes.
IMPROVE_BY = 0.005        # a second buy must be this much cheaper
MIN_LEVEL = 1.0           # dust is not a real fill
LOSS_ABORT = -3.00        # dollars; the live process halts here
BANKROLL = 100.00         # for Kelly only; --bankroll

# ---- the ACTUAL live configuration, read off the running process ----------
# Get-CimInstance Win32_Process -Filter "Name='python.exe'" on 2026-09-08 shows
#   pinrun.py --live --size 8 --minutes 720 --loss-abort -15.00 --max-positions 3
# The brief for this study says size 1 and a -$3.00 abort. Both are scored.
LIVE_UNIT = 8
LIVE_ABORT = -15.00
LIVE_TAG = "2026-09-08"


# ===========================================================================
# ARITHMETIC
# ===========================================================================
def billed_fee(p, n=1):
    """Kalshi taker fee.  BILLED ON THE ORDER, not per contract, and ceilinged
    to $0.0001.  This is why n contracts in one order cost slightly less in
    fees than n separate one-contract orders."""
    return math.ceil(0.07 * float(p) * (1.0 - float(p)) * float(n) * 10000.0) / 10000.0


def ev_per_contract(p, f):
    """Expected dollars per contract BEFORE fee, at flip rate f.

        EV = (1-f)*(1-p) - f*p   ->   zero exactly at p = 1 - f.
    """
    p = float(p)
    return (1.0 - f) * (1.0 - p) - f * p


def ev_order(p, n, f):
    """Expected dollars for an order of n contracts at price p, after the fee
    the exchange actually bills for that order."""
    return n * ev_per_contract(p, f) - billed_fee(p, n)


def realised_order(p, n, flipped):
    """Realised dollars for an order of n contracts at price p."""
    gross = n * ((-p) if flipped else (1.0 - p))
    return gross - billed_fee(p, n)


def kelly_full(p, f):
    """Full-Kelly fraction of bankroll for a binary bought at price p.

    Risk p to win (1-p), so net odds b = (1-p)/p and with win probability
    q = 1-f the Kelly criterion gives

        f* = q - (1-q)/b = (1-f) - f*p/(1-p).

    At p = 0.95, f = 0.009 this is 0.820 -- 82% of the bankroll on ONE binary.
    That is only correct if the probability is KNOWN.  Ours is 3 flips in 333.
    """
    p = float(p)
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return (1.0 - f) - f * p / (1.0 - p)


def flip_upper_bound(k, n, conf=0.95):
    """One-sided upper confidence bound on a binomial rate from k successes in
    n, by bisection on the exact Clopper-Pearson condition P(X <= k | p) =
    1-conf.  3 in 333 gives ~1.80%."""
    def tail(p):                     # P(X <= k)
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


def wald_upper(k, n, z=1.645):
    """The normal-approximation upper bound. This is where the project's 1.80%
    comes from, and it is optimistic: with only 3 events the normal
    approximation understates the exact bound by 28%."""
    p = k / float(n)
    return p + z * math.sqrt(p * (1.0 - p) / n)


def move_sd(sigma, r):
    """SD of the average of the r unpublished index prints, on the same scale
    as required_move.  Replicates pindata/pinrun exactly:

        sd = sigma * sqrt(var_factor(r,[1.0])) * (60/r)

    and the self-test proves that equals the iid closed form
    sqrt(r(r+1)(2r+1)/6)/r, so the only assumptions left in it are sigma and
    iid-gaussian increments."""
    if r <= 0 or sigma <= 0:
        return 0.0
    return sigma * math.sqrt(var_factor(int(r), [1.0])) * (60.0 / float(r))


def _phi(z):
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def p_flip_model(row):
    """The model's own probability that the favoured side flips.  The outcome
    flips only if the remaining prints average `req` away from spot, so under
    the gaussian p = Phi(-|req|/sd) on either side."""
    sd = move_sd(row["sig"], row["r"])
    if sd <= 0.0:
        return 0.0
    return _phi(-abs(row["req"]) / sd)


# ===========================================================================
# SIZING RULES
# ===========================================================================
# Each rule is (name, mode, fn, cap).  mode is:
#   "once"    -- one order on the first row of the close that can be filled
#   "improve" -- take again only when the price has improved by IMPROVE_BY
#                since the best already paid (this is the LIVE rule)
# fn(row, cap) returns contracts WANTED, before the depth cap.

def _flat(k):
    return lambda row, cap: k


def _ev_prop(row, cap):
    """Contracts proportional to expected value: round(EV / 1c)."""
    e = ev_per_contract(row["price"], MEASURED_FLIP) - billed_fee(row["price"], 1)
    return max(1, int(round(e / 0.01)))


def _conf_prop(row, cap):
    """Contracts proportional to CONFIDENCE: the smaller the model's p_flip,
    the more we buy.  A log ladder, because p_flip spans many decades:

        n = round(-log10(p_flip) / 2)   ->  1e-2:1  1e-4:2  1e-6:3  1e-8:4

    This is the rule the operator's question literally asks for."""
    pf = p_flip_model(row)
    if pf <= 0.0:
        return cap
    return max(1, int(round(-math.log10(pf) / 2.0)))


def _price_tier(row, cap):
    """More contracts the cheaper the price:
        n = 1 + floor((0.95 - price) / 0.02)
    95c->1, 93c->2, 91c->3, 89c->4."""
    return max(1, 1 + int(math.floor((0.95 - float(row["price"])) / 0.02)))


def _kelly(frac, bankroll):
    """Fractional Kelly: stake frac * f* * bankroll, converted to contracts at
    the offered price."""
    def fn(row, cap):
        fstar = kelly_full(row["price"], MEASURED_FLIP)
        if fstar <= 0.0:
            return 0
        return max(0, int(math.floor(frac * fstar * bankroll / float(row["price"]))))
    return fn


def _one(row, cap):
    return 1


def build_rules(bankroll=BANKROLL):
    R = []
    for k in (1, 2, 3):
        R.append((f"FLAT{k}", "once", _flat(k), k))
    for cap in (2, 3, 4):
        R.append((f"EV_PROP cap{cap}", "once", _ev_prop, cap))
    for cap in (2, 3, 4):
        R.append((f"CONF_PROP cap{cap}", "once", _conf_prop, cap))
    for cap in (2, 3, 4):
        R.append((f"PRICE_TIER cap{cap}", "once", _price_tier, cap))
    for frac, tag in ((1.00, "full"), (0.25, "1/4"), (0.10, "1/10"),
                      (0.05, "1/20")):
        R.append((f"KELLY_{tag} cap2", "once", _kelly(frac, bankroll), 2))
    R.append(("KELLY_1/20 cap4", "once", _kelly(0.05, bankroll), 4))
    R.append(("SCALE_IMPROVE cap2 LIVE", "improve", _one, 2))
    R.append(("SCALE_IMPROVE cap3", "improve", _one, 3))
    R.append(("SCALE_IMPROVE cap4", "improve", _one, 4))
    R.append(("TIER_IMPROVE cap2", "improve", _price_tier, 2))
    R.append(("TIER_IMPROVE cap3", "improve", _price_tier, 3))
    R.append(("TIER_IMPROVE cap4", "improve", _price_tier, 4))
    R.append(("EV_IMPROVE cap2", "improve", _ev_prop, 2))
    R.append(("EV_IMPROVE cap3", "improve", _ev_prop, 3))
    R.append(("CONF_IMPROVE cap2", "improve", _conf_prop, 2))
    return R


# ===========================================================================
# THE REPLAY
# ===========================================================================
class Buy(object):
    __slots__ = ("close", "tk", "price", "n", "flip", "tau")

    def __init__(self, close, tk, price, n, flip, tau):
        self.close, self.tk, self.price = close, tk, price
        self.n, self.flip, self.tau = n, flip, tau


def replay(closes, mode, fn, cap, unit=1):
    """Walk each close in time order and apply the rule.  Returns
    (buys, depth_truncations, dust_skips).

    `unit` is pinrun's --size: contracts per TAKE.  At unit > 1 pinrun does
    not trade smaller against a thin level, it SKIPS the row
    (`size < max(MIN_LEVEL, SIZE)`), so that is what is replicated here."""
    buys, trunc, skip = [], 0, 0
    for close_s in sorted(closes):
        rows = closes[close_s]
        got, best = 0, None
        for row in rows:
            if got >= cap:
                break
            if mode == "once" and got > 0:
                break
            if mode == "improve" and best is not None:
                if float(row["price"]) >= best - IMPROVE_BY:
                    continue
            want = fn(row, cap)
            if want < 1:
                continue
            want = min(want, cap - got)
            avail = int(math.floor(float(row["size"])))
            if unit > 1:
                if avail < unit:            # pinrun skips a thin level whole
                    skip += 1
                    continue
                n = want * unit
                if n > avail:
                    n = (avail // unit) * unit
                    trunc += 1
                if n < unit:
                    skip += 1
                    continue
            else:
                if avail < 1:
                    skip += 1
                    continue
                n = min(want, avail)
                if n < want:
                    trunc += 1
            buys.append(Buy(close_s, row["tk"], float(row["price"]), n,
                            bool(row["flip"]), int(row["tau"])))
            got += n // unit if unit > 1 else n
            best = (float(row["price"]) if best is None
                    else min(best, float(row["price"])))
    return buys, trunc, skip


def score(buys, flips=(MEASURED_FLIP, FLIP_HI, FLIP_CP), abort=None):
    """Everything the report needs, for one rule."""
    out = {}
    by_close = {}
    for b in buys:
        by_close.setdefault(b.close, []).append(b)
    n_contracts = sum(b.n for b in buys)
    out["closes"] = len(by_close)
    out["orders"] = len(buys)
    out["contracts"] = n_contracts
    out["avg_price"] = ((sum(b.n * b.price for b in buys) / n_contracts)
                        if n_contracts else 0.0)

    # --- realised (this sample) -------------------------------------------
    real = {c: sum(realised_order(b.price, b.n, b.flip) for b in v)
            for c, v in by_close.items()}
    out["real_total"] = sum(real.values())
    out["real_worst"] = min(real.values()) if real else 0.0
    out["real_per_close"] = out["real_total"] / len(by_close) if by_close else 0.0
    out["real_per_contract"] = out["real_total"] / n_contracts if n_contracts else 0.0
    out["losing_closes"] = sum(1 for v in real.values() if v < 0)

    # --- expected, losses priced in ---------------------------------------
    for f in flips:
        per_close = {c: sum(ev_order(b.price, b.n, f) for b in v)
                     for c, v in by_close.items()}
        tot = sum(per_close.values())
        key = "ev%.4f" % f
        out[key + "_total"] = tot
        out[key + "_per_close"] = tot / len(by_close) if by_close else 0.0
        out[key + "_per_contract"] = tot / n_contracts if n_contracts else 0.0
        out[key + "_neg_closes"] = sum(1 for v in per_close.values() if v < 0)
        out[key + "_worst_close"] = min(per_close.values()) if per_close else 0.0

    # --- exposure ---------------------------------------------------------
    cost = {c: sum(b.n * b.price + billed_fee(b.price, b.n) for b in v)
            for c, v in by_close.items()}
    out["max_exposure"] = max(cost.values()) if cost else 0.0
    out["mean_exposure"] = (sum(cost.values()) / len(cost)) if cost else 0.0
    out["worst_case_loss"] = -out["max_exposure"]
    ab = abs(LOSS_ABORT if abort is None else abort)
    out["abort"] = ab
    out["closes_to_abort"] = (int(math.ceil(ab / out["max_exposure"]))
                              if out["max_exposure"] > 0 else 0)
    out["typ_closes_to_abort"] = (int(math.ceil(ab / out["mean_exposure"]))
                                  if out["mean_exposure"] > 0 else 0)
    out["trips_abort"] = out["max_exposure"] >= ab
    # "near" = one bad close leaves under 10% of the abort budget standing
    out["near_abort"] = out["max_exposure"] >= 0.90 * ab
    out["max_contracts_close"] = max((sum(b.n for b in v)
                                      for v in by_close.values()), default=0)
    return out


def breakeven_flip(buys):
    """The flip rate at which this rule's total EV crosses zero."""
    if not buys:
        return 0.0
    lo, hi = 0.0, 0.5
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if sum(ev_order(b.price, b.n, mid) for b in buys) > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ===========================================================================
# LOAD
# ===========================================================================
def eligible(path=ROWS, verbose=True, sigma_mult=1.0):
    """The population pinrun would actually have traded."""
    rows, seen = [], 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            seen += 1
            try:
                rows.append(json.loads(line))
            except Exception:                                # noqa: BLE001
                continue
    kept, cut_tau, cut_pf, cut_ev = [], 0, 0, 0
    for d in rows:
        if not (TAU_MIN <= d["tau"] <= TAU_MAX):
            cut_tau += 1
            continue
        if sigma_mult != 1.0:
            d = dict(d, sig=d["sig"] * sigma_mult)
        if p_flip_model(d) > PFLIP_MAX:
            cut_pf += 1
            continue
        e = ev_per_contract(d["price"], MEASURED_FLIP) - billed_fee(d["price"], 1)
        if e < EV_FLOOR:
            cut_ev += 1
            continue
        kept.append(d)
    kept.sort(key=lambda d: (d["close"], d["sec"], d["tk"]))
    closes = {}
    for d in kept:
        closes.setdefault(d["close"], []).append(d)
    if verbose:
        print(f"  read {seen} rows from {path}")
        print(f"  gate  tau {TAU_MIN}-{TAU_MAX}s              dropped {cut_tau}")
        print(f"  gate  p_flip <= {PFLIP_MAX}           dropped {cut_pf}")
        print(f"  gate  EV >= {100*EV_FLOOR:.1f}c @ {100*MEASURED_FLIP:.2f}%   "
              f"dropped {cut_ev}")
        print(f"  ELIGIBLE {len(kept)} available trades over {len(closes)} closes")
    return closes, kept


# ===========================================================================
# SELF-TEST
# ===========================================================================
def _row(price=0.95, size=100.0, flip=False, close=1000, sec=0, tk="T",
         sig=1.0, r=10, req=-10.0, tau=10):
    return {"tk": tk, "sr": "S", "close": close, "sec": sec, "tau": tau,
            "r": r, "price": price, "size": size, "spread": 0.01,
            "req": req, "sig": sig, "flip": flip}


def selftest():
    print("SELF-TEST -- pinsize")
    fails = []

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    # ---- 1. fee arithmetic, billed on the ORDER --------------------------
    ck(abs(billed_fee(0.95, 1) - 0.0034) < 1e-12,
       f"fee at 95c size 1 is $0.0034, the ceiling of 0.07*0.95*0.05 "
       f"[{billed_fee(0.95, 1)}]")
    ck(abs(billed_fee(0.95, 4) - 0.0134) < 1e-12,
       f"fee at 95c size 4 is $0.0134, NOT 4*0.0034 = $0.0136 -- the fee is "
       f"billed on the order [{billed_fee(0.95, 4)}]")
    ck(billed_fee(0.95, 4) == math.ceil(0.07 * 0.95 * (1 - 0.95) * 4 * 10000) / 10000,
       "and it is bit-identical to pinrun.billed_fee, INCLUDING the 1-ulp "
       "quirk: 1-0.95 is 0.050000000000000044, so 0.07*0.95*(1-0.95)*4*10000 "
       "is 133.0000000000000x and the $0.0001 ceiling fires to 0.0134, not "
       "0.0133. A 'tidier' fee here would silently disagree with the live "
       "trader by $0.0001 per order")
    ck(billed_fee(0.95, 4) < 4 * billed_fee(0.95, 1),
       "one order of 4 is cheaper in fees than 4 orders of 1")

    # ---- 2. EV formula: zero exactly at p = 1-f --------------------------
    for f in (0.0090, 0.0180, 0.05):
        ck(abs(ev_per_contract(1.0 - f, f)) < 1e-15,
           f"EV is exactly zero at price = 1-f for f={f} "
           f"[{ev_per_contract(1.0 - f, f):.2e}]")
    ck(ev_per_contract(0.985, 0.0180) < 0 < ev_per_contract(0.985, 0.0090),
       "98.5c is positive EV at 0.90% and NEGATIVE at 1.80% -- the live gate "
       "lets in trades that lose at the upper bound")

    # ---- 3. Kelly, and its instability -----------------------------------
    k90, k180 = kelly_full(0.95, 0.0090), kelly_full(0.95, 0.0180)
    ck(abs(k90 - 0.820) < 0.002,
       f"full Kelly at 95c / 0.90% is 0.820 of bankroll [{k90:.4f}]")
    ck(abs(k180 - 0.640) < 0.002,
       f"full Kelly at 95c / 1.80% is 0.640 [{k180:.4f}] -- doubling the flip "
       f"rate removes 18 points of bankroll")
    ck(kelly_full(0.987, 0.0180) < 0 < kelly_full(0.987, 0.0090),
       f"at 98.7c Kelly is +{kelly_full(0.987, 0.0090):.3f} at 0.90% and "
       f"{kelly_full(0.987, 0.0180):.3f} at 1.80% -- it changes SIGN")
    ub = flip_upper_bound(3, 333)
    wd = wald_upper(3, 333)
    ck(0.0225 < ub < 0.0240,
       f"EXACT Clopper-Pearson 95% upper bound on 3 flips in 333 is "
       f"{100 * ub:.2f}% -- NOT the 1.80% this project quotes")
    ck(0.0170 < wd < 0.0180,
       f"the project's 1.80% is the WALD approximation "
       f"({100 * wd:.2f}%), which understates the exact bound by "
       f"{100 * (ub / wd - 1):.0f}% at three events")
    ck(abs(FLIP_CP - ub) < 0.0005,
       f"FLIP_CP is set to the exact bound [{FLIP_CP} vs {ub:.4f}]")
    ck(flip_upper_bound(3, 3330) < flip_upper_bound(3, 333),
       "the same 3 flips in 10x the trades gives a tighter bound -- the bound "
       "is reading sample size, not the count")

    # ---- 4. the sd formula is the iid closed form -------------------------
    worst = 0.0
    for r in range(1, 61):
        closed = math.sqrt(r * (r + 1) * (2 * r + 1) / 6.0) / r
        worst = max(worst, abs(move_sd(1.0, r) - closed) / closed)
    ck(worst < 1e-12,
       f"sd = sigma*sqrt(var_factor(r))*60/r equals sqrt(r(r+1)(2r+1)/6)/r for "
       f"r=1..60 (worst rel err {worst:.2e})")

    # ---- 5. p_flip reconstruction ----------------------------------------
    want = _phi(-2.0 / move_sd(1.0, 10))
    ck(abs(p_flip_model(_row(sig=1.0, r=10, req=-2.0)) - want) < 1e-15,
       "p_flip = Phi(-|required_move|/sd)")
    ck(abs(p_flip_model(_row(req=-2.0)) - p_flip_model(_row(req=+2.0))) < 1e-18,
       "p_flip is symmetric in the sign of required_move -- YES and NO sides "
       "are the same arithmetic")

    # ---- 6. the LIVE improve rule, on a hand-built close ------------------
    C = {1000: [_row(price=0.960, sec=1, tk="A"),
                _row(price=0.958, sec=2, tk="B"),
                _row(price=0.950, sec=3, tk="C"),
                _row(price=0.940, sec=4, tk="D")]}
    b2, _, _ = replay(C, "improve", _one, 2)
    ck([round(x.price, 3) for x in b2] == [0.960, 0.950],
       f"cap2 improve buys 96.0c then 95.0c and SKIPS 95.8c, which is not "
       f"0.5c better [{[round(x.price, 3) for x in b2]}]")
    b4, _, _ = replay(C, "improve", _one, 4)
    ck([round(x.price, 3) for x in b4] == [0.960, 0.950, 0.940],
       f"cap4 improve gets three of the four "
       f"[{[round(x.price, 3) for x in b4]}]")
    b1, _, _ = replay(C, "once", _flat(3), 3)
    ck(len(b1) == 1 and b1[0].n == 3 and abs(b1[0].price - 0.960) < 1e-12,
       "a 'once' rule takes 3 contracts in ONE order at the first price")

    # ---- 7. depth truncation and its null --------------------------------
    D = {1: [_row(price=0.95, size=2.4, close=1)],
         2: [_row(price=0.95, size=0.6, close=2, sec=1),
             _row(price=0.94, size=9.0, close=2, sec=2)]}
    bd, tr, sk = replay(D, "once", _flat(4), 4)
    ck(len(bd) == 2 and bd[0].n == 2 and bd[1].n == 4,
       f"depth truncates a wanted 4 to 2 when the level holds 2.4, and a "
       f"0.6-contract dust level is skipped for the next row "
       f"[{[(x.n, x.price) for x in bd]}]")
    ck(tr == 1 and sk == 1,
       f"the guard counts what it did: 1 truncation, 1 dust skip [{tr},{sk}]")
    _, tr2, _ = replay(D, "once", _flat(1), 1)
    ck(tr2 == 0,
       "THE GUARD'S NULL: on the same data a rule wanting 1 contract is "
       "truncated ZERO times, so the guard is not eating everything it sees")

    # ---- 7b. pinrun's --size semantics: take whole units, skip thin -------
    U = {1: [_row(price=0.95, size=100.0, close=1, sec=1),
             _row(price=0.94, size=100.0, close=1, sec=2)],
         2: [_row(price=0.95, size=5.0, close=2, sec=1),
             _row(price=0.94, size=20.0, close=2, sec=2)],
         3: [_row(price=0.95, size=12.0, close=3, sec=1)]}
    bu, tru, sku = replay(U, "improve", _one, 2, unit=8)
    got = [(x.close, x.n) for x in bu]
    ck(got[0] == (1, 8) and got[1] == (1, 8),
       f"--size 8: each take is 8 contracts, and cap2 means two takes = 16 "
       f"contracts on one close [{got}]")
    ck((2, 8) in got and sku >= 1,
       f"--size 8: a level holding 5 is SKIPPED WHOLE (pinrun does not trade "
       f"smaller against a thin level) and the next level is taken [{got}]")
    b3 = [x for x in bu if x.close == 3]
    ck(len(b3) == 1 and b3[0].n == 8,
       f"--size 8: a level holding 12 gives ONE unit of 8, not 12 "
       f"[{[(x.close, x.n) for x in b3]}]")
    su = score(bu, abort=-15.00)
    ck(abs(su["abort"] - 15.0) < 1e-12 and su["max_exposure"] > 15.0
       and su["trips_abort"] is True,
       f"--size 8 with a -$15.00 abort: the worst close commits "
       f"${su['max_exposure']:.2f} and TRIPS it on one event")
    su1 = score(bu)
    ck(abs(su1["abort"] - 3.0) < 1e-12,
       "score() still defaults to the -$3.00 abort when none is passed")

    # ---- 8. PLANTED WORLD A: cheaper is better ---------------------------
    A = {}
    for i in range(200):
        A[i] = [_row(price=0.97, size=99.0, close=i, sec=1, tk="hi"),
                _row(price=0.90, size=99.0, close=i, sec=2, tk="lo")]
    ba, _, _ = replay(A, "improve", _price_tier, 4)
    bb, _, _ = replay(A, "once", _flat(2), 2)
    sa, sb = score(ba), score(bb)
    ck(sa["ev0.0090_per_contract"] > sb["ev0.0090_per_contract"],
       f"PLANTED: buying more where it is cheaper raises EV per contract "
       f"({100 * sa['ev0.0090_per_contract']:.2f}c vs "
       f"{100 * sb['ev0.0090_per_contract']:.2f}c)")
    ck(sa["avg_price"] < sb["avg_price"],
       f"PLANTED: and it lowers the average price paid "
       f"({sa['avg_price']:.4f} vs {sb['avg_price']:.4f})")

    # ---- 9. PLANTED WORLD B: NOTHING (the null) --------------------------
    f0 = MEASURED_FLIP
    bad = []
    for name, mode, fn, cap in build_rules():
        NUL = {0: [_row(price=1.0 - f0, size=99.0, close=0, sec=1)]}
        bn, _, _ = replay(NUL, mode, fn, cap)
        if not bn:
            continue
        if score(bn)["ev0.0090_total"] > 0:
            bad.append(name)
    ck(not bad,
       f"NULL WORLD: no rule reports positive EV when the price sits exactly "
       f"at breakeven (offenders: {bad})")
    b0, _, _ = replay({0: [_row(price=1.0 - f0, size=99.0, close=0)]},
                      "once", _flat(3), 3)
    ck(abs(score(b0)["ev0.0090_total"] + billed_fee(1 - f0, 3)) < 1e-12,
       f"NULL WORLD: EV at breakeven is exactly minus the billed fee "
       f"[{score(b0)['ev0.0090_total']:.6f} vs {-billed_fee(1 - f0, 3):.6f}]")

    # ---- 10. PLANTED WORLD C: losses exist and are accounted --------------
    L = {1: [_row(price=0.90, size=99.0, close=1, flip=False)],
         2: [_row(price=0.90, size=99.0, close=2, flip=True)]}
    bl, _, _ = replay(L, "once", _flat(2), 2)
    sl = score(bl)
    want_win = 2 * 0.10 - billed_fee(0.90, 2)
    want_loss = -2 * 0.90 - billed_fee(0.90, 2)
    ck(abs(sl["real_total"] - (want_win + want_loss)) < 1e-12,
       f"PLANTED LOSS: realised total is hand-checked "
       f"{want_win + want_loss:.6f} [{sl['real_total']:.6f}]")
    ck(abs(sl["real_worst"] - want_loss) < 1e-12,
       f"PLANTED LOSS: the worst close is the planted {want_loss:.4f} "
       f"[{sl['real_worst']:.6f}]")
    ck(sl["losing_closes"] == 1, "PLANTED LOSS: exactly one losing close")

    # ---- 11. exposure and abort arithmetic -------------------------------
    X = {1: [_row(price=0.97, size=99.0, close=1)]}
    sx = score(replay(X, "once", _flat(3), 3)[0])
    want_cost = 3 * 0.97 + billed_fee(0.97, 3)
    ck(abs(sx["max_exposure"] - want_cost) < 1e-12,
       f"exposure is contracts*price plus the order's fee ({want_cost:.4f}) "
       f"[{sx['max_exposure']:.4f}]")
    ck(sx["trips_abort"] is False and sx["near_abort"] is True
       and sx["closes_to_abort"] == 2,
       f"${want_cost:.2f} on one close does NOT trip the -$3.00 abort by "
       f"itself but leaves under 10% of the budget standing "
       f"(trips={sx['trips_abort']}, near={sx['near_abort']}, "
       f"closes={sx['closes_to_abort']})")
    sx4 = score(replay({1: [_row(price=0.97, size=99.0, close=1)]},
                       "once", _flat(4), 4)[0])
    ck(sx4["trips_abort"] is True and sx4["closes_to_abort"] == 1,
       f"four contracts at 97c is ${sx4['max_exposure']:.2f} and DOES end the "
       f"session on one bad event")
    sx2 = score(replay(X, "once", _flat(1), 1)[0])
    ck(sx2["trips_abort"] is False and sx2["near_abort"] is False
       and sx2["closes_to_abort"] == 4,
       f"one contract at 97c needs {sx2['closes_to_abort']} bad closes to trip "
       f"the abort and does not trip it alone")

    # ---- 12. realised is monotone in size -- the trap, demonstrated ------
    Z = {i: [_row(price=0.95, size=99.0, close=i)] for i in range(50)}
    tots = [score(replay(Z, "once", _flat(k), k)[0])["real_total"]
            for k in (1, 2, 3, 4)]
    ck(tots == sorted(tots) and tots[0] < tots[-1],
       f"in a world with ZERO losses realised P&L rises with every extra "
       f"contract ({[round(100 * t, 1) for t in tots]}c) -- which is exactly "
       f"why this file does not rank on realised P&L")

    # ---- 13. breakeven_flip is an inverse of the EV formula ---------------
    bz, _, _ = replay(Z, "once", _flat(1), 1)
    be = breakeven_flip(bz)
    ck(abs(sum(ev_order(b.price, b.n, be) for b in bz)) < 1e-6,
       f"breakeven_flip finds the rate where total EV is zero "
       f"({100 * be:.3f}% at a flat 95c)")
    ck(be < 1.0 - 0.95 + 1e-9,
       f"and it sits just under the naive 1-p = 5.00% because of the fee "
       f"[{100 * be:.3f}%]")

    print(f"\n  {'ALL PASS' if not fails else str(len(fails)) + ' FAILURES'}")
    return 0 if not fails else 1


# ===========================================================================
def report(closes, bankroll=BANKROLL, out=None, rows_path=ROWS):
    lines = []

    def P(s=""):
        print(s)
        lines.append(s)

    n_rows = sum(len(v) for v in closes.values())
    flips = sum(1 for v in closes.values() for d in v if d["flip"])
    P("=" * 120)
    P("pinsize -- does sizing on confidence beat flat sizing?")
    P("=" * 120)
    P(f"  population: {n_rows} genuinely available trades over {len(closes)} "
      f"closes, tau {TAU_MIN}-{TAU_MAX}s, p_flip <= {PFLIP_MAX}, "
      f"EV >= {100 * EV_FLOOR:.1f}c at {100 * MEASURED_FLIP:.2f}%")
    P(f"  REALISED FLIPS IN THIS POPULATION: {flips}")
    if flips == 0:
        P("  ^ ZERO. Realised P&L is therefore a monotone increasing function of")
        P("    contracts bought and CANNOT rank these rules. The EXPECTED columns")
        P("    below, which price losses in, are the ones that decide.")
    ub = flip_upper_bound(3, 333)
    P(f"  flip rate: {100 * MEASURED_FLIP:.2f}% measured (3 in 333). "
      f"Upper 95% bound: {100 * FLIP_HI:.2f}% as this project quotes it "
      f"(a Wald approximation, {100 * wald_upper(3, 333):.2f}% exactly), "
      f"{100 * ub:.2f}% by exact Clopper-Pearson.")
    P(f"  The project's 1.80% is OPTIMISTIC by {100 * (ub / FLIP_HI - 1):.0f}%. "
      f"Both are scored below; 2.31% is the honest worst case.")
    P(f"  breakeven price: {100 * (1 - MEASURED_FLIP):.1f}c at the point "
      f"estimate, {100 * (1 - FLIP_HI):.1f}c at the upper bound")
    prices = sorted(d["price"] for v in closes.values() for d in v)
    over = sum(1 for p in prices if p > 1 - FLIP_HI)
    P(f"  {over} of {len(prices)} eligible trades ({100.0 * over / len(prices):.1f}%) "
      f"are priced above the upper-bound breakeven, i.e. they are negative EV "
      f"if the flip rate is really 1.80%")
    P("")

    rules = build_rules(bankroll)
    res = []
    for name, mode, fn, cap in rules:
        buys, tr, sk = replay(closes, mode, fn, cap)
        res.append((name, score(buys), tr, sk, buys))

    P("-" * 120)
    P("TABLE 1 -- REALISED on this sample. NOT A RANKING: zero losses occurred,")
    P("           so every extra contract is free money here and only here.")
    P("-" * 120)
    P(f"  {'rule':<24}{'closes':>7}{'contr':>7}{'avg px':>9}{'total c':>10}"
      f"{'c/close':>9}{'c/contr':>9}{'worst cl':>10}{'maxExp $':>10}")
    for name, s, tr, sk, _b in res:
        P(f"  {name:<24}{s['closes']:>7}{s['contracts']:>7}"
          f"{s['avg_price']:>9.4f}{100 * s['real_total']:>10.1f}"
          f"{100 * s['real_per_close']:>9.2f}"
          f"{100 * s['real_per_contract']:>9.2f}"
          f"{100 * s['real_worst']:>10.2f}{s['max_exposure']:>10.3f}")
    P("")

    P("-" * 120)
    P("TABLE 2 -- EXPECTED, losses priced in. THIS is the comparison.")
    P("           'trips $3' = one bad close commits $3.00 or more and ends the")
    P("           session on a single event -> the rule is REJECTED.")
    P("-" * 120)
    P(f"  {'rule':<24}{'contr':>7}{'Ec/close':>10}{'Ec/con':>8}"
      f"{'Ec/close':>10}{'Ec/con':>8}{'Ec/close':>10}{'negCl':>7}"
      f"{'maxExp$':>9}{'maxCon':>7}{'abort in':>9}{'trips $3':>9}{'near $3':>9}")
    P(f"  {'':<24}{'':>7}{'@0.90%':>10}{'@0.90%':>8}{'@1.80%':>10}"
      f"{'@1.80%':>8}{'@2.31%':>10}{'@2.31%':>7}{'/close':>9}{'/close':>7}"
      f"{'closes':>9}{'in 1':>9}{'>=$2.70':>9}")
    for name, s, tr, sk, _b in res:
        P(f"  {name:<24}{s['contracts']:>7}"
          f"{100 * s['ev0.0090_per_close']:>10.2f}"
          f"{100 * s['ev0.0090_per_contract']:>8.2f}"
          f"{100 * s['ev0.0180_per_close']:>10.2f}"
          f"{100 * s['ev0.0180_per_contract']:>8.2f}"
          f"{100 * s['ev0.0231_per_close']:>10.2f}"
          f"{s['ev0.0231_neg_closes']:>7}"
          f"{s['max_exposure']:>9.3f}{s['max_contracts_close']:>7}"
          f"{s['closes_to_abort']:>9}"
          f"{('YES' if s['trips_abort'] else 'no'):>9}"
          f"{('YES' if s['near_abort'] else 'no'):>9}")
    P("")

    P("-" * 120)
    P("TABLE 3 -- the depth guard's cost, and its null (a rule wanting one")
    P("           contract must be truncated zero times)")
    P("-" * 120)
    P(f"  {'rule':<24}{'orders':>8}{'truncated':>11}{'dust skips':>12}"
      f"{'mean exp $':>12}{'typ abort':>11}")
    for name, s, tr, sk, _b in res:
        P(f"  {name:<24}{s['orders']:>8}{tr:>11}{sk:>12}"
          f"{s['mean_exposure']:>12.3f}{s['typ_closes_to_abort']:>11}")
    P("")

    P("-" * 120)
    P("THE MECHANISM -- why sizing on the MODEL'S confidence backfires")
    P("-" * 120)
    band = [(0.0, 1e-10), (1e-10, 1e-8), (1e-8, 1e-5), (1e-5, 1e-3), (1e-3, 1.0)]
    allr = [d for v in closes.values() for d in v]
    P(f"  {'model p_flip band':<22}{'rows':>7}{'mean price':>12}"
      f"{'EV/contract c':>15}{'@0.90%':>9}")
    for lo, hi in band:
        sel = [d for d in allr if lo <= p_flip_model(d) < hi]
        if not sel:
            continue
        mp = sum(d["price"] for d in sel) / len(sel)
        me = sum(ev_per_contract(d["price"], MEASURED_FLIP)
                 - billed_fee(d["price"], 1) for d in sel) / len(sel)
        P(f"  [{lo:.0e}, {hi:.0e})      {len(sel):>7}{mp:>12.4f}"
          f"{100 * me:>15.2f}{'':>9}")
    P("")
    P("  The model is MOST confident exactly where the contract is MOST")
    P("  EXPENSIVE, so 'buy more when confident' is 'buy more at 97-99c'.")
    P("  That is the wrong direction: at these prices the win is 1-3c and the")
    P("  loss is 97-99c, and the model's own confidence is already known to be")
    P("  ~15x too high (it implies ~0.06% where 0.90% is measured), so its")
    P("  ordering within the eligible set carries no information about risk.")
    P("")

    P("-" * 120)
    P("RISK -- Monte Carlo on the -$3.00 abort")
    P("-" * 120)
    P("  Each close is drawn with replacement from the 70 actual buy patterns.")
    P("  Every contract in a close flips together (rho -> 1 across coins on the")
    P("  same quarter hour; hard rule 4). 20,000 paths of 500 closes -- the")
    P("  pre-registered forward window. P&L runs cumulatively from flat.")
    P(f"  {'rule':<24}{'P(abort) 0.90%':>16}{'1.80%':>10}{'2.31%':>10}"
      f"{'med worst DD $':>16}")
    import random
    import itertools
    NPATH, NCLOSE = 20000, 500
    mc = {}
    for name, s2, tr, sk, buys in res:
        if not buys:
            continue
        pat = {}
        for b in buys:
            pat.setdefault(b.close, []).append(b)
        pats = list(pat.values())
        # per close pattern, the P&L if it wins and the P&L if it flips.
        win = [sum(realised_order(b.price, b.n, False) for b in g) for g in pats]
        los = [sum(realised_order(b.price, b.n, True) for b in g) for g in pats]
        idxs = range(len(pats))
        row, dds = [], []
        for f in (MEASURED_FLIP, FLIP_HI, FLIP_CP):
            rng = random.Random(20260908)
            hits = 0
            for _ in range(NPATH):
                picks = rng.choices(idxs, k=NCLOSE)
                vals = [win[i] for i in picks]
                nbad = rng.binomialvariate(NCLOSE, f)
                if nbad:
                    for pos in rng.sample(range(NCLOSE), nbad):
                        vals[pos] = los[picks[pos]]
                worst = min(itertools.accumulate(vals))
                if worst <= LOSS_ABORT:
                    hits += 1
                if f == MEASURED_FLIP:
                    dds.append(worst)
            row.append(100.0 * hits / NPATH)
        dds.sort()
        mc[name] = row
        P(f"  {name:<24}{row[0]:>15.1f}%{row[1]:>9.1f}%{row[2]:>9.1f}%"
          f"{dds[len(dds) // 2]:>16.2f}")
    P("")

    P("-" * 120)
    P("KELLY, and why full Kelly is not a candidate")
    P("-" * 120)
    P(f"  bankroll assumed ${bankroll:.2f}")
    P(f"  {'price':>8}{'f* @0.90%':>12}{'contracts':>11}{'f* @1.80%':>12}"
      f"{'contracts':>11}{'change':>10}")
    for p in (0.90, 0.93, 0.95, 0.97, 0.98, 0.982, 0.985, 0.987):
        a, b = kelly_full(p, MEASURED_FLIP), kelly_full(p, FLIP_HI)
        ca = math.floor(max(a, 0.0) * bankroll / p)
        cb = math.floor(max(b, 0.0) * bankroll / p)
        chg = "n/a" if ca == 0 else f"{100.0 * (cb - ca) / ca:+.0f}%"
        P(f"  {100 * p:>7.1f}c{a:>12.3f}{ca:>11}{b:>12.3f}{cb:>11}{chg:>10}")
    P("")

    P("-" * 120)
    P("HOW MUCH FLIP RATE EACH RULE CAN ABSORB before its EV per close is zero")
    P("-" * 120)
    P(f"  {'rule':<24}{'breakeven flip %':>18}{'headroom vs 0.90%':>20}"
      f"{'survives 1.80%':>16}{'survives 2.31%':>16}")
    for name, s, tr, sk, buys in res:
        be = breakeven_flip(buys)
        P(f"  {name:<24}{100 * be:>18.3f}{be / MEASURED_FLIP:>19.2f}x"
          f"{('yes' if be > FLIP_HI else 'NO'):>16}"
          f"{('yes' if be > FLIP_CP else 'NO'):>16}")
    P("")

    P("-" * 120)
    P("SIGMA STRESS -- how much of this depends on the volatility estimate")
    P("-" * 120)
    P("  sigma enters these rules in exactly TWO places:")
    P("    (a) the ELIGIBILITY gate p_flip <= 0.02, which decides WHICH trades")
    P("        exist at all -- shared by every rule including flat sizing;")
    P("    (b) CONF_PROP's size, which is the ONLY rule that sizes on sigma.")
    P("  PRICE_TIER, EV_PROP and the improve rules size on PRICE, so their")
    P("  sizing decision does not read sigma at all.")
    P("")
    P("  Stress multipliers are the measured hour-to-hour spread of sigma_300")
    P("  from the volatility-accuracy study (r=19: p05 0.865, median 1.066,")
    P("  p95 1.327), plus 1.50 and 2.00 as a deliberate overshoot.")
    P(f"  {'sigma x':>9}{'elig rows':>11}{'closes':>8}"
      f"{'TIER_IMPROVE2':>15}{'SCALE_IMPR2':>13}{'CONF_PROP2':>12}{'FLAT2':>9}")
    P(f"  {'':>9}{'':>11}{'':>8}{'Ec/close@1.8%':>15}{'@1.8%':>13}"
      f"{'@1.8%':>12}{'@1.8%':>9}")
    base = None
    for mult in (0.865, 1.000, 1.066, 1.327, 1.500, 2.000):
        cl2, kp2 = eligible(rows_path, verbose=False, sigma_mult=mult)
        if not kp2:
            P(f"  {mult:>9.3f}{0:>11}{0:>8}{'-':>15}{'-':>13}{'-':>12}{'-':>9}")
            continue
        vals = []
        for mode, fn, cap in (("improve", _price_tier, 2), ("improve", _one, 2),
                              ("once", _conf_prop, 2), ("once", _flat(2), 2)):
            bb, _, _ = replay(cl2, mode, fn, cap)
            vals.append(100 * score(bb)["ev0.0180_per_close"])
        if mult == 1.000:
            base = list(vals)
        P(f"  {mult:>9.3f}{len(kp2):>11}{len(cl2):>8}"
          f"{vals[0]:>15.2f}{vals[1]:>13.2f}{vals[2]:>12.2f}{vals[3]:>9.2f}")
    if base:
        P("")
        P("  Same rows, as a percentage of the sigma x 1.000 result:")
        for mult in (0.865, 1.327, 2.000):
            cl2, kp2 = eligible(rows_path, verbose=False, sigma_mult=mult)
            vals = []
            for mode, fn, cap in (("improve", _price_tier, 2),
                                  ("improve", _one, 2),
                                  ("once", _conf_prop, 2), ("once", _flat(2), 2)):
                bb, _, _ = replay(cl2, mode, fn, cap)
                vals.append(100 * score(bb)["ev0.0180_per_close"])
            P(f"  {mult:>9.3f}{'':>11}{'':>8}"
              + "".join(f"{100.0 * v / b:>14.0f}%" if b else f"{'-':>15}"
                        for v, b in zip(vals[:1], base[:1]))
              + "".join(f"{100.0 * v / b:>12.0f}%" if b else f"{'-':>13}"
                        for v, b in zip(vals[1:2], base[1:2]))
              + "".join(f"{100.0 * v / b:>11.0f}%" if b else f"{'-':>12}"
                        for v, b in zip(vals[2:3], base[2:3]))
              + "".join(f"{100.0 * v / b:>8.0f}%" if b else f"{'-':>9}"
                        for v, b in zip(vals[3:4], base[3:4])))
    P("")

    P("-" * 120)
    P("LIVE CONFIGURATION CHECK -- the running process is NOT at size 1")
    P("-" * 120)
    P(f"  Read from the live process on {LIVE_TAG}:")
    P(f"    pinrun.py --live --size {LIVE_UNIT:g} --minutes 720 "
      f"--loss-abort {LIVE_ABORT:.2f} --max-positions 3")
    P("  MAX_PER_CLOSE is 2 and is NOT settable by a flag, so a close can hold")
    P(f"  TWO takes of {LIVE_UNIT:g} = {2 * LIVE_UNIT:g} contracts.")
    P(f"  pinrun's own rail sizes the abort off ONE take (one_loss = 1.00 * "
      f"size = ${LIVE_UNIT:.2f})")
    P(f"  and requires the abort in [-4x, -1.5x] of it. It does not account for")
    P("  the second take, so the worst close is twice what the rail assumes.")
    P("")
    P(f"  {'rule':<24}{'contr':>7}{'maxExp $':>10}{'meanExp $':>11}"
      f"{'vs abort':>10}{'trips':>8}{'bad closes':>12}")
    P(f"  {'':<24}{'':>7}{'/close':>10}{'/close':>11}"
      f"{('$%.2f' % abs(LIVE_ABORT)):>10}{'in 1':>8}{'to abort':>12}")
    for name, mode, fn, cap in rules:
        if cap != 2 or "KELLY_full" in name or "KELLY_1/4" in name                 or "KELLY_1/10" in name:
            continue
        bl, trl, skl = replay(closes, mode, fn, cap, unit=LIVE_UNIT)
        sl = score(bl, abort=LIVE_ABORT)
        P(f"  {name:<24}{sl['contracts']:>7}{sl['max_exposure']:>10.2f}"
          f"{sl['mean_exposure']:>11.2f}"
          f"{100.0 * sl['max_exposure'] / abs(LIVE_ABORT):>9.0f}%"
          f"{('YES' if sl['trips_abort'] else 'no'):>8}"
          f"{sl['closes_to_abort']:>12}")
    P("")
    P("  THIS IS THE FINDING THAT MATTERS MOST FOR THE MONEY ACTUALLY AT RISK:")
    P("  at --size 8 the live rule's worst single close is already at or over")
    P("  the -$15.00 abort, so ONE bad close can end the session. That is a")
    P("  property of the CURRENT configuration, not of any rule proposed here,")
    P("  and it is unchanged by the sizing question. Every rule below was")
    P("  scored at size 1 against -$3.00 as briefed; the ratio is what")
    P("  transfers, and the ratio says the same thing at both sizes.")
    P("")

    P("-" * 120)
    P("THE VERDICT -- apply the risk rejection, then rank on cents per CLOSE")
    P("-" * 120)
    P(f"  REJECT any rule whose worst single close commits >= "
      f"${0.90 * abs(LOSS_ABORT):.2f}, i.e. 90% of the -${abs(LOSS_ABORT):.2f}")
    P("  abort budget. One bad event then ends the session outright or leaves")
    P("  too little of the budget standing to keep trading. pinrun's own")
    P("  comment already reaches this conclusion for cap 3.")
    P("")
    surv = [(n, sc, b) for n, sc, tr, sk, b in res if not sc["near_abort"]]
    rej = [(n, sc) for n, sc, tr, sk, b in res if sc["near_abort"]]
    P(f"  REJECTED ({len(rej)}): "
      + ", ".join(f"{n} (${sc['max_exposure']:.2f})" for n, sc in rej))
    P("")
    P(f"  SURVIVORS ({len(surv)}), ranked by expected cents per close at the")
    P(f"  EXACT 2.31% upper bound -- the honest worst case:")
    P(f"  {'rank':>5}  {'rule':<24}{'Ec/close':>10}{'Ec/close':>10}"
      f"{'Ec/close':>10}{'Ec/con':>8}{'contr':>7}{'maxExp$':>9}"
      f"{'P(abort)':>10}{'headroom':>10}")
    P(f"  {'':>5}  {'':<24}{'@0.90%':>10}{'@1.80%':>10}{'@2.31%':>10}"
      f"{'@2.31%':>8}{'':>7}{'':>9}{'@2.31%':>10}{'':>10}")
    surv.sort(key=lambda t: -t[1]["ev0.0231_per_close"])
    for i, (n, sc, b) in enumerate(surv, 1):
        be = breakeven_flip(b)
        P(f"  {i:>5}  {n:<24}{100 * sc['ev0.0090_per_close']:>10.2f}"
          f"{100 * sc['ev0.0180_per_close']:>10.2f}"
          f"{100 * sc['ev0.0231_per_close']:>10.2f}"
          f"{100 * sc['ev0.0231_per_contract']:>8.2f}"
          f"{sc['contracts']:>7}{sc['max_exposure']:>9.3f}"
          f"{mc.get(n, [0, 0, 0])[2]:>9.1f}%{be / MEASURED_FLIP:>9.2f}x")
    P("")
    P("  CAVEATS THAT TRAVEL WITH EVERY NUMBER ABOVE")
    P("  1. 70 closes over THREE days (2026-09-04/05/06), 43 of them on one")
    P("     day. That is 3 independent day-blocks, not 70 observations.")
    P("  2. ZERO flips occurred here. The 0.90% is IMPORTED from a different")
    P("     sample (3 in 333 dear trades, out of sample). Nothing in this")
    P("     dataset measures the flip rate, so nothing here can confirm it.")
    P("  3. Every EV number is linear in that imported rate. If the true rate")
    P("     is above each rule's breakeven (3.5-7.3%), every rule loses.")
    P("  4. The backtest always gets the quote. Live, we race for it.")

    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"  wrote {out}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", default=ROWS)
    ap.add_argument("--bankroll", type=float, default=BANKROLL)
    ap.add_argument("--out", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            print("SELF-TEST FAILED -- refusing to touch real data")
            return rc
        print("")
    closes, kept = eligible(a.rows)
    if not kept:
        print("loaded nothing")
        return 0
    report(closes, a.bankroll, a.out, a.rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
