#!/usr/bin/env python3
# VERSION: 2026-09-08-ed1
"""empdiag.py -- NEW FILE, READ-ONLY. WHY does the empirical estimator beat the
Gaussian? Shape, or scale, or autocorrelation?

This matters because the three have different fixes and only one of them needs
an empirical distribution at all:

  SCALE  the trailing-300 s sigma is simply too small for the next few seconds.
         Then the standardised move z = m_r / (sigma*sqrt(S_r)/r) has SD > 1,
         and the fix is a multiplier on sd -- one number, not a distribution.
  AUTOCORRELATION  1 s index increments are not independent. var_factor already
         takes a rho vector and pin passes rho = [1.0], i.e. white noise. If the
         increments are positively autocorrelated the model's sd is too small
         for a reason that has nothing to do with fat tails, and the fix is to
         pass the measured rho.
  SHAPE  z is genuinely leptokurtic: even after matching the SD, the 2-3 sigma
         region carries more mass than a Gaussian. Only this one needs the
         empirical CDF.

So the table below prints, for each index and each r, the realised tail of z
next to TWO nulls: a standard Gaussian, and a Gaussian rescaled to z's own
measured SD. The gap to the first is the total error; the gap to the second is
the part a single sd multiplier CANNOT fix.

THIS FILE IS A DESCRIPTION OF THE WHOLE SAMPLE AND IS NOT USED TO SET ANY
PARAMETER. Nothing in empfair.py or empscore.py reads it. It exists so the
report can say which mechanism is operating instead of guessing; using it to
choose a threshold would be exactly the lookahead the task forbids.
"""
import argparse
import math
import os
import sys
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import idxload                                              # noqa: E402
from empfair import IndexModel, SERIES_TO_INDEX, S_r        # noqa: E402
from engine import var_factor                               # noqa: E402

ND = NormalDist()
ZS = (2.0537489106318225,   # Gaussian tail 0.02   -- pin's gate
      2.5758293035489004,   # 0.005
      3.090232306167813)    # 0.001


def acf(v, n, lags=4):
    """Autocorrelation of consecutive-second increments, whole tape."""
    ds = []
    for i in range(1, n):
        a, b = v[i - 1], v[i]
        if a == a and b == b:
            ds.append(b - a)
        else:
            ds.append(None)
    clean = [x for x in ds if x is not None]
    m = sum(clean) / len(clean)
    var = sum((x - m) ** 2 for x in clean) / len(clean)
    out = [1.0]
    for h in range(1, lags):
        s = k = 0
        for i in range(len(ds) - h):
            a, b = ds[i], ds[i + h]
            if a is not None and b is not None:
                s += (a - m) * (b - m)
                k += 1
        out.append(s / k / var if k and var else 0.0)
    return out, len(clean), math.sqrt(var)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rs", default="2,4,9,19")
    a = ap.parse_args()
    rs = [int(x) for x in a.rs.split(",")]
    ids = sorted(set(SERIES_TO_INDEX.values()))
    dense = idxload.load(ids, verbose=False)

    print("\n  1-SECOND INCREMENT AUTOCORRELATION (whole tape)")
    print(f"    {'index':<14}{'diffs':>11}{'sigma_1s':>12}{'rho1':>9}"
          f"{'rho2':>9}{'rho3':>9}{'sd inflation r=19':>20}")
    rhos = {}
    for iid in ids:
        d = dense[iid]
        r_, k, sg = acf(d.v, d.n)
        rhos[iid] = r_
        infl = math.sqrt(var_factor(19, r_) / var_factor(19, [1.0]))
        print(f"    {iid:<14}{k:>11,}{sg:>12.5f}{r_[1]:>9.4f}{r_[2]:>9.4f}"
              f"{r_[3]:>9.4f}{infl:>19.3f}x")

    print("\n  IS IT SHAPE OR SCALE? tail of the standardised move z")
    print("    z is m_r / (sigma_300 * sqrt(S_r) / r): the model's OWN sd. A")
    print("    correctly specified model has SD(z)=1 and Gaussian tails.")
    print(f"    {'index':<13}{'r':>3}{'n':>10}{'mean':>8}{'SD':>7}"
          f"{'exkurt':>8}{'  |':>3}{'P(z>2.05)':>10}{'gauss':>8}"
          f"{'rescaled':>10}{'  |':>3}{'P(z>2.58)':>10}{'gauss':>8}"
          f"{'rescaled':>10}")
    for iid in ids:
        im = IndexModel(dense[iid], rs)
        for r in rs:
            zz = []
            for h in im.hz[r]:
                zz.extend(h)
            n = len(zz)
            if n < 1000:
                continue
            m = sum(zz) / n
            v2 = sum((x - m) ** 2 for x in zz) / (n - 1)
            sd = math.sqrt(v2)
            k4 = sum((x - m) ** 4 for x in zz) / n / (v2 * v2) - 3.0
            row = f"    {iid:<13}{r:>3}{n:>10,}{m:>8.3f}{sd:>7.3f}{k4:>8.2f}"
            for z in ZS[:2]:
                c = sum(1 for x in zz if x >= z) / n
                g = 1 - ND.cdf(z)
                gs = 1 - ND.cdf(z / sd)         # Gaussian rescaled to SD(z)
                row += f"{'  |':>3}{100*c:>9.3f}%{100*g:>7.3f}%{100*gs:>9.3f}%"
            print(row)
        del im


if __name__ == "__main__":
    main()
