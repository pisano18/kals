#!/usr/bin/env python3
# VERSION: 2026-08-25-r1
"""
settlement_math.py -- the exact fair-value model, derived and then VERIFIED.

Nothing here is trusted because it looks right. Every closed form is checked
three ways:
    1. brute-force exact weights on the covariance structure
    2. an independent closed-form expression
    3. Monte Carlo

WHY THIS FILE EXISTS

The Kalshi rules page (confirmed from the app, not inferred) says:

    "At the last minute before expiration, 60 RTI prices are collected. The
     official and final value is the average of these prices."

So settlement is the mean of SIXTY DISCRETE once-per-second prices, not a
continuous time-average. Everything downstream that used the continuous
integral is an approximation, and the approximation is worst exactly where we
want to trade -- the last few seconds, deep in the tails.

TIMELINE (integer seconds, tick k = the BRTI print at second k)

    k = 1..60      strike window   -> strike = mean(S_1 .. S_60)
    k = 60         market opens
    k = 901..960   settle window   -> settle = mean(S_901 .. S_960)
    k = 960        market closes

    close - open = 900s.  End of strike window -> start of settle window = 840s.

MODEL: S_k = S_0 + sigma * sum_{j<=k} Z_j, Z iid N(0,1). Driftless random walk,
which is the right null: BRTI is a martingale by construction (CF's own
methodology note -- it is built from order books, not trades).
"""

import argparse
import math
import random
from statistics import NormalDist

# Deliberately stdlib-only, like every other file here. numpy has no wheel for
# some Python versions (3.14 among them) and an import failure in THIS file
# gates the entire run, since go.py stops on any self-test failure.
ND = NormalDist()

OPEN_K, CLOSE_K = 60, 960
STRIKE_IDX = list(range(1, 61))          # S_1 .. S_60
SETTLE_IDX = list(range(901, 961))       # S_901 .. S_960
N_AVG = 60


# ---------------------------------------------------------------------------
# 1. Exact second moments from the covariance structure.  Cov(S_i,S_j)=s^2*min
# ---------------------------------------------------------------------------
def exact_var_linear(weights_by_index, sigma=1.0):
    """Var(sum_i c_i S_i) computed exactly. weights_by_index: {index: c}.

    Cov(S_i, S_j) = sigma^2 * min(i, j) for a driftless random walk, so this is
    c^T M c with M_ij = min(i,j). Written as a single pass over the sorted
    indices: for the k-th smallest index, min(i,j) = idx[k] over the whole
    remaining suffix, so the quadratic form collapses to a suffix-sum."""
    idx = sorted(weights_by_index)
    c = [weights_by_index[i] for i in idx]
    n = len(idx)
    suffix = [0.0] * (n + 1)
    for k in range(n - 1, -1, -1):
        suffix[k] = suffix[k + 1] + c[k]
    total = 0.0
    for k in range(n):
        # diagonal term plus twice the off-diagonal terms above it
        total += c[k] * idx[k] * (2.0 * suffix[k + 1] + c[k])
    return total * sigma ** 2


def unconditional_var_settle_minus_strike(sigma=1.0):
    w = {}
    for i in SETTLE_IDX:
        w[i] = w.get(i, 0.0) + 1.0 / N_AVG
    for i in STRIKE_IDX:
        w[i] = w.get(i, 0.0) - 1.0 / N_AVG
    return exact_var_linear(w, sigma)


# ---------------------------------------------------------------------------
# 2. Conditional law of `settle` given everything known at second t.
#    This is the object a live bot actually needs.
# ---------------------------------------------------------------------------
def future_weights(t):
    """w_j = how many not-yet-realized settle ticks the innovation at second j
    feeds into. Innovation Z_j moves every S_i for i >= j."""
    fut = [i for i in SETTLE_IDX if i > t]
    if not fut:
        return {}
    return {j: sum(1 for i in fut if i >= j) for j in range(t + 1, CLOSE_K + 1)}


def cond_var_bruteforce(t, sigma=1.0):
    w = future_weights(t)
    return sigma ** 2 * sum(v * v for v in w.values()) / N_AVG ** 2


def cond_var_closedform(t, sigma=1.0):
    """Closed form. Two regimes."""
    if t >= CLOSE_K:
        return 0.0
    if t >= SETTLE_IDX[0] - 1:                 # inside (or at the edge of) the
        r = CLOSE_K - t                        # averaging window: r ticks left
        return sigma ** 2 * r * (r + 1) * (2 * r + 1) / 6.0 / N_AVG ** 2
    # before the window opens
    n_full = (SETTLE_IDX[0]) - t               # seconds whose innovation hits all 60
    tail = sum(k * k for k in range(1, N_AVG))  # 1^2 .. 59^2
    return sigma ** 2 * (n_full * N_AVG ** 2 + tail) / N_AVG ** 2


def cond_mean(t, S, locked_sum=None):
    """E[settle | info at t]. S = current index level. Exact, no approximation."""
    locked = [i for i in SETTLE_IDX if i <= t]
    n_fut = N_AVG - len(locked)
    if locked_sum is None:
        locked_sum = 0.0
    return (locked_sum + n_fut * S) / N_AVG


def p_yes(t, S, strike, sigma, locked_sum=0.0):
    """P(settle >= strike | info at t). The whole model in one line."""
    v = cond_var_closedform(t, sigma)
    mu = cond_mean(t, S, locked_sum)
    if v <= 0:
        return 1.0 if mu >= strike else 0.0
    return 1.0 - ND.cdf((strike - mu) / math.sqrt(v))


# ---------------------------------------------------------------------------
# 3. The formulas currently written down in RUNBOOK.md, for comparison.
# ---------------------------------------------------------------------------
def runbook_var_before(tau, sigma=1.0):
    """RUNBOOK: 'Var = sigma^2 * (tau + 20) before the averaging window opens'"""
    return sigma ** 2 * (tau + 20)


def runbook_var_inside(r, sigma=1.0):
    """RUNBOOK: 'sigma^2 * r^3 / 10800 with r seconds remaining once inside'"""
    return sigma ** 2 * r ** 3 / 10800.0


# ---------------------------------------------------------------------------
def monte_carlo(t_list, n=40_000, sigma=1.0, seed=7):
    """Simulate and measure Var(settle | F_t), with no numpy.

    Only the seconds the test actually reads are simulated -- the strike window,
    the settle window, and the listed t values. Between them the walk jumps in
    one draw of variance (gap * sigma^2), which is exact for a random walk and
    about 7x less work than stepping every second."""
    rng = random.Random(seed)
    need = sorted(set(STRIKE_IDX) | set(SETTLE_IDX) | set(t_list) | {CLOSE_K})
    pos = {k: i for i, k in enumerate(need)}
    strike_at = [pos[i] for i in STRIKE_IDX]
    settle_at = [pos[i] for i in SETTLE_IDX]
    locked_at, nfut = {}, {}
    for t in t_list:
        li = [pos[i] for i in SETTLE_IDX if i <= t]
        locked_at[t] = li
        nfut[t] = N_AVG - len(li)

    diffs, resid = [], {t: [] for t in t_list}
    gaps = [need[0]] + [need[i] - need[i - 1] for i in range(1, len(need))]
    sds = [sigma * math.sqrt(g) for g in gaps]
    for _ in range(n):
        path, x = [], 0.0
        for sd in sds:
            x += rng.gauss(0.0, sd)
            path.append(x)
        settle = sum(path[i] for i in settle_at) / N_AVG
        strike = sum(path[i] for i in strike_at) / N_AVG
        diffs.append(settle - strike)
        for t in t_list:
            li = locked_at[t]
            ls = sum(path[i] for i in li) if li else 0.0
            mu = (ls + nfut[t] * path[pos[t]]) / N_AVG
            resid[t].append(settle - mu)

    def var(xs):
        m = sum(xs) / len(xs)
        return sum((v - m) ** 2 for v in xs) / (len(xs) - 1)

    out = {"uncond_var_diff": var(diffs)}
    for t in t_list:
        out[t] = var(resid[t])
    return out


def main():
    ap = argparse.ArgumentParser()
    # --selftest is accepted so this file matches every other gate in the
    # repo. go.py used to invoke it with no flag at all; main() printed the
    # word FAIL in its own output and then exited 0, so the gate could not
    # fail and the run proceeded on a broken model. Failures are now collected
    # and turned into a non-zero exit either way.
    ap.add_argument("--selftest", action="store_true")
    ap.parse_args()

    fails = []
    print("=" * 78)
    print("SETTLEMENT MATH  --  exact discrete model, triple-checked")
    print("=" * 78)

    # ---- A. unconditional Var(settle - strike): the sigma-calibration object
    v = unconditional_var_settle_minus_strike()
    print(f"\nA. Var(settle - strike), unconditional  = {v:.4f} * sigma^2")
    print(f"   PLAN.md / RUNBOOK.md claim            = 880 * sigma^2")
    print(f"   continuous-time approximation         = 880.0000 * sigma^2")
    print(f"   -> discrepancy {v - 880:+.4f} sigma^2 "
          f"({100*(v-880)/880:+.3f}%), from discreteness. Immaterial.")
    print("   This is the number used to back sigma out of realized "
          "(settle-strike).")
    if abs(v - 880) > 0.5:
        fails.append(f"Var(settle-strike) = {v:.4f}, not ~880 sigma^2")

    # ---- B. conditional variance: closed form vs brute force
    print("\nB. Var(settle | info at second t) -- closed form vs brute force")
    bad = 0
    for t in list(range(0, 960, 37)) + list(range(895, 960)):
        a, b = cond_var_closedform(t), cond_var_bruteforce(t)
        if abs(a - b) > 1e-9 * max(1.0, abs(b)):
            bad += 1
            print(f"   MISMATCH t={t}: closed {a:.6f} brute {b:.6f}")
    print(f"   checked {len(list(range(0,960,37)))+65} values of t, "
          f"{bad} mismatches.  {'PASS' if bad == 0 else '*** FAIL ***'}")
    if bad:
        fails.append(f"{bad} closed-form/brute-force variance mismatches")

    # ---- C. Monte Carlo
    tl = [60, 300, 600, 840, 899, 900, 910, 930, 950, 955, 957, 959]
    print("\nC. Monte Carlo check (40k paths, stdlib only)")
    mc = monte_carlo(tl)
    print(f"   uncond Var(settle-strike): MC {mc['uncond_var_diff']:.3f} "
          f"vs exact {v:.3f}   ({100*(mc['uncond_var_diff']/v-1):+.2f}%)")
    print(f"   {'t':>5}{'tau':>6}{'exact Var':>13}{'MC Var':>13}{'rel err':>10}")
    worst = 0.0
    for t in tl:
        e = cond_var_closedform(t)
        m = mc[t]
        rel = m / e - 1 if e > 0 else 0.0
        worst = max(worst, abs(rel))
        print(f"   {t:>5}{CLOSE_K-t:>6}{e:>13.4f}{m:>13.4f}{100*rel:>9.2f}%")
    print(f"   worst |rel err| = {100*worst:.2f}%  "
          f"({'PASS' if worst < 0.03 else '*** FAIL ***'} at 40k paths)")
    if worst >= 0.03:
        fails.append(f"Monte Carlo disagrees with the closed form by "
                     f"{100*worst:.2f}%")
    if abs(mc["uncond_var_diff"] / v - 1) > 0.05:
        fails.append("Monte Carlo unconditional variance is off by more "
                     f"than 5% ({100*(mc['uncond_var_diff']/v-1):+.2f}%)")

    # p_yes must be exactly a half when the conditional mean sits on the
    # strike, at every t, with and without a locked partial sum. If this ever
    # drifts, every price the engine quotes is shifted.
    half_bad = 0
    for t in (0, 300, 800, 899, 920, 950, 958):
        for S, drift in ((100.0, 0.0), (100.0, 3.0), (80_000.0, 0.0)):
            n_locked = len([i for i in SETTLE_IDX if i <= t])
            # the locked ticks sat at S+drift; the future ones sit at S
            ls = n_locked * (S + drift)
            k = cond_mean(t, S, locked_sum=ls)
            if abs(p_yes(t, S, k, 1.0, locked_sum=ls) - 0.5) > 1e-9:
                half_bad += 1
    print(f"   p_yes at the money = 0.5 exactly: "
          f"{'PASS' if half_bad == 0 else f'*** FAIL ({half_bad}) ***'}")
    if half_bad:
        fails.append(f"p_yes is not 0.5 at the money in {half_bad} cases")

    # ---- D. where RUNBOOK is wrong
    print("\n" + "=" * 78)
    print("D. THE RUNBOOK VARIANCE FORMULA IS WRONG BEFORE THE WINDOW")
    print("=" * 78)
    print("   RUNBOOK.md T5: 'Var = sigma^2 * (tau + 20) before the averaging")
    print("   window opens'.  With tau = seconds to CLOSE that is wrong; the")
    print("   exact answer is sigma^2 * (tau - 39.50).")
    print(f"\n   {'tau':>6}{'exact/sig^2':>14}{'RUNBOOK':>12}{'vol error':>12}")
    for tau in (900, 600, 300, 180, 120, 90, 61):
        t = CLOSE_K - tau
        e = cond_var_closedform(t)
        rb = runbook_var_before(tau)
        print(f"   {tau:>6}{e:>14.2f}{rb:>12.2f}{100*(math.sqrt(rb/e)-1):>11.1f}%")
    print("\n   At 120s to close the RUNBOOK formula overstates volatility by")
    print("   32%. It is off by a constant ~59.5 sigma^2, i.e. someone wrote")
    print("   tau for 'time to close' but derived it for 'time until the")
    print("   averaging window starts'. Both readings appear in the docs.")
    print("   Correct, unambiguous form:  Var = sigma^2 * (tau - 39.50),")
    print("   tau = seconds to close, valid for tau >= 60.")

    # ---- E. the discrete correction near expiry
    print("\n" + "=" * 78)
    print("E. THE CONTINUOUS APPROXIMATION FAILS EXACTLY WHERE WE'D TRADE")
    print("=" * 78)
    print("   Inside the window, RUNBOOK uses sigma^2 * r^3/10800 (the")
    print("   continuous integral). The truth for 60 discrete prices is")
    print("   sigma^2 * r(r+1)(2r+1)/21600.")
    print(f"\n   {'r':>4}{'exact/sig^2':>14}{'continuous':>13}{'vol understated by':>20}")
    for r in (60, 45, 30, 20, 15, 10, 7, 5, 3, 2, 1):
        t = CLOSE_K - r
        e = cond_var_closedform(t)
        c = runbook_var_inside(r)
        print(f"   {r:>4}{e:>14.5f}{c:>13.5f}{100*(math.sqrt(e/c)-1):>19.1f}%")
    print("\n   The continuous form UNDERSTATES residual vol, always. Too little")
    print("   vol -> probabilities pushed too far toward 0/1 -> the model")
    print("   OVERPRICES favourites. PLAN.md sec.2 tells us to buy 90-99c")
    print("   favourites in the last 30-120s. That is precisely the cell where")
    print("   this error is largest and in the losing direction.")
    print("   Note sec.10.3 flags fat tails as a second effect pushing the SAME")
    print("   way. Two independent reasons the v2 target cell is oversold.")

    # ---- F. what it costs you in cents
    print("\n" + "=" * 78)
    print("F. PRICE IMPACT, in cents, of using the continuous form inside")
    print("=" * 78)
    sigma = 5.92           # $/sqrt(s) at BTC ~78,788 per PLAN.md sec.1
    print(f"   sigma = {sigma} $/sqrt(s).  Index sitting d dollars above strike,")
    print("   nothing locked in yet (worst case, r ticks remain):")
    print(f"\n   {'r':>4}{'d=$5':>18}{'d=$15':>18}{'d=$40':>18}")
    print(f"   {'':>4}{'exact  cont':>18}{'exact  cont':>18}{'exact  cont':>18}")
    for r in (30, 20, 15, 10, 5, 3):
        t = CLOSE_K - r
        row = f"   {r:>4}"
        for d in (5.0, 15.0, 40.0):
            mu_minus_k = d * (r / N_AVG)      # only r of 60 ticks still move
            se = math.sqrt(cond_var_closedform(t, sigma))
            sc = math.sqrt(runbook_var_inside(r, sigma))
            pe = 1 - ND.cdf(-mu_minus_k / se) if se > 0 else 1.0
            pc = 1 - ND.cdf(-mu_minus_k / sc) if sc > 0 else 1.0
            row += f"{100*pe:>10.1f}{100*pc:>8.1f}"
        print(row)
    print("\n   Gaps of several cents at exactly the prices PLAN.md targets.")
    print("   Any model that used r^3/10800 was mispricing its own signal.")

    print("\n" + "=" * 78)
    if fails:
        print("*** SETTLEMENT MATH FAILED ***")
        for f in fails:
            print("   -", f)
        raise SystemExit(1)
    print("SETTLEMENT MATH PASSED -- closed form matches brute force exactly,")
    print("Monte Carlo agrees within tolerance, and p_yes is 0.5 at the money.")


if __name__ == "__main__":
    main()
