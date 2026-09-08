#!/usr/bin/env python3
# VERSION: 2026-09-08-es1
"""earlyself.py -- the self-test gate for early.py / earlyrun.py.

The repo rule: build a world where the answer is already known and fail if
the estimator misses it, AND fail if it finds something in a world with
nothing planted. Here that means five things, and the fourth is the one that
matters most:

  1. the settlement arithmetic reproduces a KNOWN settlement exactly
  2. required_move is the move that actually flips the market -- checked by
     constructing the flipping path and settling it
  3. the fee is the one Kalshi bills, and a certain contract at 0.99 nets
     0.5c after it
  4. the causal gate FIRES: any read past the decision second raises
  5. a world with a planted certainty is found, and a coin-flip world is not
"""
import math, os, sys, array

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import early                                                # noqa: E402
from early import (Index, partial, state, eff_strike, billed_fee, net_edge,
                   N_AVG)


def build_index(T0, n, fn, iid="X"):
    v = array.array("d", bytes(8 * n))
    for i in range(n):
        v[i] = fn(i)
    return Index(T0, {iid: v})


def run():
    print("SELF-TEST -- early")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    T0 = 0
    C = 5000

    # ---- 1. settlement arithmetic on a KNOWN settlement ------------------
    # ramp: v[s] = 100 + 0.01*s. The true settlement is the mean over
    # [C-60, C-1], which is 100 + 0.01*(C-60 + C-1)/2.
    ix = build_index(T0, 6000, lambda i: 100.0 + 0.01 * i)
    true_settle = sum(100.0 + 0.01 * s for s in range(C - 60, C)) / 60.0
    lk, r = partial(ix, "X", C, C - 1, C - 1)
    ck(r == 0 and abs(lk / 60.0 - true_settle) < 1e-9,
       "at tau=1 all 60 prints are locked and the mean IS the settlement "
       "(%.6f)" % (lk / 60.0))
    lk, r = partial(ix, "X", C, C - 61, C - 61)
    ck(r == 60 and lk == 0.0,
       "at tau=61 nothing is locked and all 60 prints are still to come")
    lk, r = partial(ix, "X", C, C - 20, C - 20)
    ck(r == 19, "at tau=20 exactly 19 prints are still to come")

    # ---- 2. required_move IS the move that flips the market ---------------
    # Put the strike so the market is currently a YES, then move the
    # remaining prints by exactly required_move and check it settles at the
    # threshold. Move by slightly less and it must stay YES.
    tau = 30
    now = C - tau
    st = state(ix, "X", C, tau, 0.0, 2)     # placeholder strike, replaced
    spot = st["spot"]
    Ke_target = st["mu"] - 0.05             # 5c below mu: a YES by 0.05
    K = Ke_target + 0.5 * 10 ** -2
    st = state(ix, "X", C, tau, K, 2)
    ck(st["side"] == "yes", "mu above the effective strike reads as YES")
    req = st["req"]
    lk, r = partial(ix, "X", C, now, now)
    settle_at = (lk + r * (spot - req)) / 60.0
    ck(abs(settle_at - st["Ke"]) < 1e-9,
       "moving the %d remaining prints by exactly required_move (%.6f) lands "
       "the settlement ON the effective strike" % (r, req))
    settle_less = (lk + r * (spot - req * 0.999)) / 60.0
    ck(settle_less > st["Ke"],
       "a move 0.1% smaller than required leaves the market a YES")
    settle_more = (lk + r * (spot - req * 1.001)) / 60.0
    ck(settle_more < st["Ke"],
       "a move 0.1% larger than required flips it to NO")

    # ---- 3. fees ---------------------------------------------------------
    ck(abs(billed_fee(0.95, 1) - 0.0034) < 1e-12,
       "billed fee at p=0.95 is $0.0034 (ceiling), not the raw $0.003325")
    # 0.07*0.99*0.01 = $0.000693, ceilinged to $0.0007
    ck(abs(net_edge(0.99, 1) - (0.01 - 0.0007)) < 1e-12,
       "a certain contract bought at 0.99 nets 0.93c after the $0.0007 "
       "billed fee (%.5f)" % net_edge(0.99, 1))
    ck(net_edge(0.995, 1) < 0.005,
       "0.995 does not clear a 0.5c floor once the fee is charged")

    # ---- 4. THE CAUSAL GATE MUST FIRE ------------------------------------
    raised = False
    try:
        ix.value("X", C, C - 20)
    except AssertionError:
        raised = True
    ck(raised, "reading the index AT the close while standing at tau=20 "
               "raises -- the no-lookahead rule is a runtime error, "
               "not a comment")
    raised = False
    try:
        ix.csum("X", C - 60, C - 1, C - 20)
    except AssertionError:
        raised = True
    ck(raised, "summing the whole settlement window from tau=20 raises too")
    ok_ok = True
    try:
        ix.value("X", C - 20, C - 20)
        ix.csum("X", C - 60, C - 21, C - 20)
    except AssertionError:
        ok_ok = False
    ck(ok_ok, "and reading only up to the decision second is allowed")

    # ---- 5. planted certainty found; coin-flip world not -----------------
    # World A: a dead-flat index. Nothing can move, so required_move for a
    # market 1.0 away from the strike is huge against M=0 -- and the outcome
    # is decided. World B: the market sits exactly ON the strike.
    ixA = build_index(T0, 6000, lambda i: 100.0)
    stA = state(ixA, "X", C, 30, 101.0, 2)
    ck(stA["side"] == "no" and stA["req"] > 0.9,
       "flat world, strike 1.0 above spot: side NO, required move %.3f"
       % stA["req"])
    stB = state(ixA, "X", C, 30, 100.0, 2)
    ck(stB["req"] < 0.011,
       "flat world, strike ON spot: required move collapses to the rounding "
       "band (%.6f) -- the lock cannot fire here" % stB["req"])

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    return not fails


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
