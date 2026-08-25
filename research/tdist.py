#!/usr/bin/env python3
# VERSION: 2026-08-25-td1
"""
tdist.py -- Student-t, because stdlib has none and a clustered standard error
is not a z.

    python research/tdist.py --selftest

WHY THIS FILE EXISTS

Several estimators here build their standard error from a SMALL number of
groups: feeds.py and leadlag.py from ~20 blocks, leadlag.py and cross.py and
edge.py from however many close-time clusters exist. That statistic is a t on
(groups - 1) degrees of freedom, not a z, and the difference is not academic at
the thresholds this project uses:

      |t|      p, normal      p, t(19)      ratio
      2.0        0.0455        0.0598        1.3x
      3.0        0.0027        0.0074        2.7x
      4.0        0.0001        0.0008        13x

So a "4-sigma" result off twenty blocks is thirteen times more likely to be
noise than it reads. Combined with the several hundred statistics one go.py run
emits, that is the difference between a lead and a finding.

Implementation is the regularized incomplete beta by continued fraction
(Numerical Recipes), inverted by bisection. --selftest checks it against
published quantile tables to four decimals.
"""

import argparse
import math
from statistics import NormalDist

ND = NormalDist()


def _betacf(a, b, x, itmax=200, eps=3e-14):
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def betainc(a, b, x):
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lb = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
          + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lb) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lb) * _betacf(b, a, 1.0 - x) / b


def student_t_cdf(t, df):
    if df <= 0:
        return float("nan")
    x = df / (df + t * t)
    p = 0.5 * betainc(df / 2.0, 0.5, x)
    return 1.0 - p if t > 0 else p


def student_t_ppf(p, df):
    """Two-sided-friendly inverse CDF by bisection. Falls back to the normal
    for large df, where they agree to well past any decimal that matters."""
    if df > 3000:
        return ND.inv_cdf(p)
    # The bracket has to be grown, not fixed: t(1) at 0.999 is 318, which a
    # hard [-300, 300] silently clamps to 300 and returns a quantile that is
    # 6e-5 wrong. Small df have very long tails.
    lo, hi = -1.0, 1.0
    while student_t_cdf(hi, df) < p and hi < 1e12:
        hi *= 4.0
    while student_t_cdf(lo, df) > p and lo > -1e12:
        lo *= 4.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if student_t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def p_two_sided(t, df):
    """Two-sided p-value for a t statistic on df degrees of freedom."""
    if df is None or df <= 0:
        return 2 * (1 - ND.cdf(abs(t)))
    return 2 * (1 - student_t_cdf(abs(t), df))


def crit(alpha, df):
    """Two-sided critical value; falls back to the normal without a df."""
    if df is None or df <= 0:
        return ND.inv_cdf(1 - alpha / 2.0)
    return student_t_ppf(1 - alpha / 2.0, df)


TABLE = [
    # (p, df, published quantile)
    (0.975, 1, 12.7062), (0.975, 2, 4.3027), (0.975, 5, 2.5706),
    (0.975, 10, 2.2281), (0.975, 19, 2.0930), (0.975, 30, 2.0423),
    (0.975, 120, 1.9799), (0.995, 5, 4.0321), (0.995, 20, 2.8453),
    (0.95, 30, 1.6973), (0.99, 10, 2.7638), (0.999, 15, 3.7328),
]


def selftest():
    print("=" * 78)
    print("SELF-TEST -- Student-t against published tables")
    print("=" * 78)
    fails = []
    print(f"  {'quantile':>18}{'computed':>12}{'published':>12}{'err':>12}")
    for p, df, want in TABLE:
        got = student_t_ppf(p, df)
        print(f"  {'t(%d) @ %.3f' % (df, p):>18}{got:>12.4f}{want:>12.4f}"
              f"{got - want:>+12.2e}")
        if abs(got - want) > 5e-4:
            fails.append(f"t({df}) @ {p} = {got:.4f}, published {want}")

    print("\n  CDF and PPF must invert each other")
    worst = 0.0
    for df in (1, 3, 7, 19, 50, 400):
        for p in (0.6, 0.75, 0.9, 0.975, 0.999):
            q = student_t_ppf(p, df)
            worst = max(worst, abs(student_t_cdf(q, df) - p))
    print(f"  {'worst round-trip error':>34}{worst:>12.2e}")
    if worst > 1e-6:
        fails.append(f"cdf(ppf(p)) off by {worst:.2e}")

    print("\n  Large df must converge to the normal")
    d = abs(student_t_ppf(0.975, 5000) - ND.inv_cdf(0.975))
    print(f"  {'t(5000) vs z at 0.975':>34}{d:>12.2e}")
    if d > 1e-3:
        fails.append(f"t(5000) differs from z by {d:.2e}")

    print("\n  WHAT IT COSTS TO USE z INSTEAD")
    print(f"  {'|t|':>8}{'p, normal':>14}{'p, t(19)':>14}{'ratio':>10}")
    for t in (2.0, 2.5, 3.0, 3.5, 4.0):
        pn = 2 * (1 - ND.cdf(t))
        pt = p_two_sided(t, 19)
        print(f"  {t:>8.1f}{pn:>14.5f}{pt:>14.5f}{pt/pn:>10.1f}x")
        if pt < pn:
            fails.append(f"t({19}) p-value at |t|={t} came out SMALLER than "
                         "the normal, which is backwards")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- matches published tables to four decimals, the")
    print("CDF and PPF invert, and it converges to the normal at large df.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.parse_args()
    raise SystemExit(0 if selftest() else 1)


if __name__ == "__main__":
    main()
