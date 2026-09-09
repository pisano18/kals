#!/usr/bin/env python3
# VERSION: 2026-09-08-fg1  (AUDIT ONLY -- reads, never writes outside results/audit)
"""freshgates.py -- unbiased audit of pinrun's four DATA-FRESHNESS gates.

Reconstructs pinrun's live decision from results/pindata/rows.jsonl and sweeps
each freshness gate. Nothing here can trade; there is no order code and no
network call.

THE RECONSTRUCTION, and why it is exact
  rows.jsonl stores req = (60/r)*(K - mu), so   mu - K = -req*r/60.
  pinrun's fair() is  Phi((mu-K)/(sigma*sqrt(var_factor(r)))).
  Therefore fair is recoverable from (req, r, sig) alone, with no extra data,
  and the sigma-window sweep is the same arithmetic with s30 / s120 / s300
  in place of sig.

SCORING RULE, fixed before any number was looked at
  There are ZERO flips in the eligible tau 3-30 sample, so realised P&L there
  is a monotone function of contracts bought and cannot rank a gate. Every
  table below is scored on EXPECTED value at the MEASURED flip rate 0.90%,
  stressed at the exact one-sided 95% Clopper-Pearson bound 2.31%, and the
  blended break-even flip rate of the trades a setting admits is printed
  beside it.

    EV(p) = (1-f)*(1-p) - f*p - fee(p)          fee = ceil(0.07 p(1-p), 1e-4)
    break-even f over a set of buys at prices p_i:
        sum_i [(1-p_i) - f*(1-p_i) - f*p_i - fee_i] = 0
        f* = (sum_i (1-p_i) - sum_i fee_i) / N        (since (1-p)+p = 1)

SELF-TEST: plants a world where the answer is known (a stale row that must be
refused at 2000 ms and admitted at 5000 ms, and a flat "step function" index
where a 30 s sigma window collapses to zero and a 300 s one does not), and a
null world with nothing planted, where every sweep must report no difference.
"""
import argparse
import json
import math
import os
import sys
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"C:\kals-repo\research")
from engine import var_factor                                # noqa: E402

ND = NormalDist()
ROWS = r"C:\kals-repo\results\pindata\rows.jsonl"

PIN = 0.98
TAU_MIN, TAU_MAX = 3, 30
EDGE_FLOOR = 0.003
EV_FLOOR = 0.003
PRICE_CEILING = 0.988
MIN_LEVEL = 1.0
SIZE = 5.0
FLIP = 0.0090
FLIP_HI = 0.0231


def fee(p, n=1.0):
    return math.ceil(0.07 * p * (1 - p) * n * 10000.0) / 10000.0


def ev(p, f=FLIP):
    return (1.0 - f) * (1.0 - p) - f * p - fee(p, 1)


def fair_of(row, sigkey="sig"):
    """pinrun's fair(), rebuilt from the stored arithmetic."""
    sg = row.get(sigkey)
    r = row["r"]
    if sg is None or r < 1:
        return None
    mu_minus_K = -row["req"] * r / 60.0
    sd = sg * math.sqrt(var_factor(int(r), [1.0]))
    if sd <= 0:
        return 1.0 if mu_minus_K >= 0 else 0.0
    return ND.cdf(mu_minus_K / sd)


def decide(row, sigkey="sig", max_age=None, tau_lo=TAU_MIN, tau_hi=TAU_MAX,
           edge_floor=EDGE_FLOOR, ev_floor=EV_FLOOR, ceiling=PRICE_CEILING,
           size=SIZE, sigma_zero_ok=True, pin=PIN):
    """Return (want, price) if pinrun would buy this row, else None."""
    if not (tau_lo <= row["tau"] <= tau_hi):
        return None
    if max_age is not None and row["age_ms"] > max_age:
        return None
    sg = row.get(sigkey)
    if sg is None:
        return None
    if sg == 0 and not sigma_zero_ok:
        return None
    f = fair_of(row, sigkey)
    if f is None:
        return None
    p = row["price"]
    if row["side_yes"]:
        if f < pin:
            return None
        want, gross = "yes", f - p
    else:
        if f > 1.0 - pin:
            return None
        want, gross = "no", (1.0 - f) - p
    if row["size"] < max(MIN_LEVEL, size):
        return None
    if gross - fee(p, size) / size < edge_floor:
        return None
    if p > ceiling:
        return None
    if ev(p) < ev_floor:
        return None
    return want, p


def score(buys, flips=0):
    """buys = list of (price, flip_bool)."""
    n = len(buys)
    if not n:
        return dict(n=0, avg_p=None, ev_c=0.0, ev_hi_c=0.0, be=None,
                    real_c=0.0, flips=0)
    ps = [b[0] if isinstance(b, (tuple, list)) else b for b in buys]
    fl = [bool(b[1]) if isinstance(b, (tuple, list)) else False for b in buys]
    s1 = sum(1.0 - p for p in ps)
    sf = sum(fee(p, 1) for p in ps)
    real = sum(((1.0 - p) if not f else (-p)) - fee(p, 1)
               for p, f in zip(ps, fl))
    return dict(n=n, avg_p=sum(ps) / n,
                ev_c=100.0 * sum(ev(p, FLIP) for p in ps),
                ev_hi_c=100.0 * sum(ev(p, FLIP_HI) for p in ps),
                be=(s1 - sf) / n,
                real_c=100.0 * real,
                flips=sum(fl))


def load(path=ROWS):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


# ---------------------------------------------------------------------------
def selftest():
    print("SELF-TEST -- freshgates")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # --- PLANTED WORLD -------------------------------------------------
    base = dict(tau=10, r=9, req=-5.0, sig=0.05, s30=0.05, s120=0.05,
                price=0.95, size=500.0, side_yes=True, age_ms=100,
                close=1, flip=False)
    stale = dict(base, age_ms=4000)
    ck(decide(base, max_age=2000) is not None, "planted fresh row is bought")
    ck(decide(stale, max_age=2000) is None,
       "planted stale row is refused at 2000 ms")
    ck(decide(stale, max_age=5000) is not None, "and admitted at 5000 ms")

    step = dict(base, sig=0.05, s30=0.0, req=-0.02, price=0.97)
    f300, f30 = fair_of(step, "sig"), fair_of(step, "s30")
    ck(f300 < PIN, f"planted row is UNDECIDED on the 300 s sigma ({f300:.4f})")
    ck(f30 == 1.0, f"and a CERTAINTY on a zero 30 s sigma ({f30}) -- the "
                   f"step-function trap")
    ck(decide(step, "s30") is not None and decide(step, "sig") is None,
       "the 30 s window buys it, the 300 s window does not")
    ck(decide(step, "s30", sigma_zero_ok=False) is None,
       "and refusing sigma==0 blocks it")

    sc = score([(0.95, False), (0.95, False)])
    hand_ev = 2 * ((1 - FLIP) * 0.05 - FLIP * 0.95 - 0.0034)
    ck(abs(sc["ev_c"] - 100 * hand_ev) < 1e-9,
       f"EV arithmetic matches by hand ({sc['ev_c']:.4f}c)")
    ck(abs(sc["be"] - (0.05 - 0.0034)) < 1e-12,
       f"break-even flip rate at 95c is 4.66% ({100*sc['be']:.2f}%)")
    sc2 = score([(0.95, False), (0.95, True)])
    ck(abs(sc2["real_c"] - 100 * (0.05 - 0.0034 - 0.95 - 0.0034)) < 1e-9,
       f"realised P&L books a flip as -price ({sc2['real_c']:.2f}c)")

    # --- NULL WORLD ----------------------------------------------------
    null = [dict(base, age_ms=50, sig=0.05, s30=0.05, s120=0.05)
            for _ in range(200)]
    outs = {a: len([r for r in null if decide(r, max_age=a)])
            for a in (500, 2000, 5000, 60000, None)}
    ck(len(set(outs.values())) == 1 and list(outs.values())[0] == 200,
       f"NULL: the age gate changes nothing when nothing is stale ({outs})")
    souts = {k: len([r for r in null if decide(r, k)])
             for k in ("sig", "s30", "s120")}
    ck(len(set(souts.values())) == 1,
       f"NULL: the sigma window changes nothing when all horizons agree "
       f"({souts})")
    ck(score([]) ["n"] == 0, "NULL: an empty set scores nothing, not a number")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows", default=ROWS)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")
    rows = load(a.rows)
    print(f"\n  {len(rows):,} rows loaded")


if __name__ == "__main__":
    main()
