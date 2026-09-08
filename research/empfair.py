#!/usr/bin/env python3
# VERSION: 2026-09-08-ef1
"""empfair.py -- NEW FILE, READ-ONLY. Replace the bell curve with the index's
own move distribution, and measure which one is calibrated at pin's gate.

THE CLAIM UNDER TEST
  pin prices fair = Phi((mu - K_eff)/sd). Phi is a Gaussian. Crypto 1-second
  index increments are not Gaussian, so at the 0.98 gate -- which lives 2+
  sigma into the tail -- the Gaussian can be systematically overconfident, and
  overconfidence is exactly what kills a strategy whose loss is 40x its win.

THE ESTIMATOR
  With r prints unpublished the settlement is
      settle = (locked_sum + sum of the next r prints) / 60
  so YES requires
      mean(next r prints) - spot  >=  required_move = (60/r) * (K_eff - mu).
  The Gaussian answers P(.) with Phi. This file answers it with the empirical
  frequency, over a trailing window OF THAT INDEX ONLY, with which the r-print
  forward average actually exceeded that move -- signed, because a move the
  wrong way is harmless.

  Two forms, both reported:
    RAW   frequency of  m_r(t) = mean(v[t+1..t+r]) - v[t]  >= required_move
          in raw price units. Carries the trailing window's own volatility.
    STD   frequency of  z(t) = m_r(t) / scale_r(t)  >=  required_move/scale_r(now),
          where scale_r = sigma_trailing300 * sqrt(sum_{k<=r} k^2) / r is
          exactly the Gaussian's own sd for m_r. STD therefore holds the scale
          fixed at the model's own and changes ONLY THE SHAPE of the
          distribution -- it is the clean like-for-like replacement of Phi.

NO PEEKING -- the discipline, mechanically enforced, not asserted
  1. The trailing empirical distribution is built from WHOLE CLOCK HOURS that
     ended strictly before the decision second. _assert_causal recomputes the
     highest index second any anchor could have touched, (h_end+1)*3600-1+r,
     and raises if it is not < the decision second. It runs on every single
     query, real and synthetic.
  2. sigma is the trailing-300 s SD ending at the decision second, the same one
     pincal/pinrun use; verified against pincal.sigma_from itself in selftest.
  3. Nothing is fitted. There is no free parameter to fit: the window length is
     declared up front (24 h primary, 6 h and 72 h reported beside it, all
     three always printed so that none can be picked after the fact).
  4. Two deliberately LEAKING variants are computed alongside -- LEAK_SPOT uses
     the last settlement print as spot, LEAK_VOL uses the volatility of the
     next 60 s -- so the report can show what a leak looks like in these very
     tables. If the honest estimator scored like those, it would be a leak.

SELF-TEST
  W1 Gaussian world: the model IS the truth. Both estimators must calibrate,
     and empirical/Gaussian tail ratio must be ~1. An estimator that finds fat
     tails in a Gaussian world is broken.
  W2 Vol-clustering world, same unconditional sd: sigma alternates every 90 s
     between 0.4x and 2.0x, so the trailing-300 s sigma is right on average and
     wrong every second. The Gaussian must come out OVERCONFIDENT at the gate
     and the empirical must be closer to the realised rate. If the harness
     cannot see a planted fat tail it cannot report its absence.
  W3 causality: a query whose trailing window reaches past the decision second
     must raise.
  W4 leak detector: in the Gaussian world LEAK_SPOT must score implausibly
     better than the honest model. A harness that cannot catch a planted leak
     is not evidence against an unplanted one.
"""
import argparse
import array
import bisect
import math
import os
import random
import sys
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import idxload                                              # noqa: E402
from engine import var_factor, N_AVG                        # noqa: E402

ND = NormalDist()
SCRATCH = r"C:\Users\Joe\AppData\Local\Temp\kals-emp"
SETTLED = os.path.join(SCRATCH, "settled.json")

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
    "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
}

PIN = 0.98
SIGMA_WIN = 300
SIGMA_MIN_DIFFS = 20
WINDOWS_H = (6, 24, 72)          # DECLARED UP FRONT, all three always printed
W_PRIMARY = 24
MIN_ANCHORS = 2000
NAN = float("nan")


def S_r(r):
    return r * (r + 1) * (2 * r + 1) / 6.0


def eff_strike(K, d):
    return float(K) - 0.5 * (10.0 ** (-int(d)))


class CausalError(Exception):
    pass


# ===========================================================================
class IndexModel:
    """Everything derived from one index, on a contiguous second grid.

    sig[i]  trailing-300 s sample SD of consecutive 1 s diffs ending at second
            base+i, NaN when fewer than 20 usable diffs -- pincal.sigma_from.
    hz[r][h], hm[r][h]  ASCENDING float32 arrays of the standardised and raw
            r-print forward moves anchored in clock hour h.
    """

    def __init__(self, dense, rs, verbose=False):
        self.d = dense
        self.base, self.n, self.v = dense.base, dense.n, dense.v
        self.rs = sorted(set(rs))
        self._sigma()
        self._hourly(verbose)

    # ---- sigma ----------------------------------------------------------
    def _sigma(self):
        v, n = self.v, self.n
        cn = array.array("i", [0]) * (n + 1)
        cs = array.array("d", [0.0]) * (n + 1)
        cq = array.array("d", [0.0]) * (n + 1)
        pn = 0
        ps = pq = 0.0
        for i in range(1, n):
            cn[i], cs[i], cq[i] = pn, ps, pq
            a, b = v[i - 1], v[i]
            if a == a and b == b:
                dd = b - a
                pn += 1
                ps += dd
                pq += dd * dd
        cn[n], cs[n], cq[n] = pn, ps, pq
        # window of diffs indexed (i-SIGMA_WIN+1 .. i) inclusive
        sig = array.array("d", [NAN]) * n
        for i in range(SIGMA_WIN, n):
            lo, hi = i - SIGMA_WIN + 1, i
            k = cn[hi + 1] - cn[lo]
            if k < SIGMA_MIN_DIFFS:
                continue
            s = cs[hi + 1] - cs[lo]
            q = cq[hi + 1] - cq[lo]
            var = (q - s * s / k) / (k - 1)
            if var > 0:
                sig[i] = math.sqrt(var)
        self.sig = sig

    # ---- hourly empirical distributions ---------------------------------
    def _hourly(self, verbose):
        v, n, sig = self.v, self.n, self.sig
        cs = array.array("d", [0.0]) * (n + 1)
        cn = array.array("i", [0]) * (n + 1)
        s = 0.0
        k = 0
        for i in range(n):
            cs[i] = s
            cn[i] = k
            x = v[i]
            if x == x:
                s += x
                k += 1
        cs[n], cn[n] = s, k
        self.nh = n // 3600
        self.hz, self.hm = {}, {}
        for r in self.rs:
            sc = math.sqrt(S_r(r)) / r
            zs = [[] for _ in range(self.nh)]
            ms = [[] for _ in range(self.nh)]
            for i in range(n - r):
                a = v[i]
                if a != a:
                    continue
                if cn[i + 1 + r] - cn[i + 1] != r:      # gap in the forward run
                    continue
                m = (cs[i + 1 + r] - cs[i + 1]) / r - a
                h = i // 3600
                if h < self.nh:
                    ms[h].append(m)
                    g = sig[i]
                    if g == g and g > 0:
                        zs[h].append(m / (g * sc))
            self.hm[r] = [array.array("f", sorted(x)) for x in ms]
            self.hz[r] = [array.array("f", sorted(x)) for x in zs]
            if verbose:
                tot = sum(len(x) for x in self.hz[r])
                print(f"      r={r:<3} {tot:>9,} standardised anchors")
        del cs, cn

    # ---- causal query ---------------------------------------------------
    def _assert_causal(self, h_lo, h_hi, r, now_s):
        """The highest index second ANY anchor in hours [h_lo, h_hi] can read
        is (h_hi+1)*3600 - 1 + r. It must be strictly before the decision
        second. Raised, not warned: a silent leak is the failure mode here."""
        top = self.base + (h_hi + 1) * 3600 - 1 + r
        if top >= now_s:
            raise CausalError(
                f"trailing window hours [{h_lo},{h_hi}] with r={r} could read "
                f"second {top} >= decision second {now_s}")

    def tail(self, r, now_s, thresh, hours, std, shift_h=0):
        """P(forward r-print move >= thresh) from whole hours before now_s.

        shift_h > 0 slides the window FORWARD past the decision second. It is
        a DELIBERATE LEAK, used only by the LEAK_EMP control, and it is the
        one path that skips _assert_causal -- see leak_emp() below."""
        # The last usable whole hour is the newest h with
        #   base + (h+1)*3600 - 1 + r  <=  now_s - 1
        # i.e. every second any of its anchors can read is strictly before the
        # decision second. Usually that is hour(now)-1; when now_s sits within
        # r seconds of an hour boundary it is one hour earlier still.
        h_hi = ((now_s - self.base - r) // 3600) - 1 + shift_h
        h_lo = max(0, h_hi - hours + 1)
        if h_hi < h_lo or h_hi >= self.nh:
            return None, 0
        if shift_h:
            if h_hi <= ((now_s - self.base - r) // 3600) - 1:
                raise CausalError("shift_h must move the window forward")
        else:
            self._assert_causal(h_lo, h_hi, r, now_s)
        tab = self.hz[r] if std else self.hm[r]
        cnt = tot = 0
        for h in range(h_lo, h_hi + 1):
            a = tab[h]
            if not a:
                continue
            tot += len(a)
            cnt += len(a) - bisect.bisect_left(a, thresh)
        if tot < MIN_ANCHORS:
            return None, tot
        return cnt / tot, tot

    # ---- pricing --------------------------------------------------------
    def state(self, close_s, tau, leak=None):
        """mu, sd, sigma, r at the decision second -- everything the pricing
        needs that does NOT depend on the strike. Split out so the self-test
        can place synthetic strikes exactly at the gate."""
        now = close_s - tau
        lo, hi = close_s - N_AVG, min(now, close_s - 1)
        if hi < lo:
            return None
        got, want = self.d.span(lo, hi)
        if not got or len(got) < want * 0.95:
            return None
        locked = sum(got) * (want / len(got))
        r = N_AVG - want
        if r <= 0:
            return None
        i = now - self.base
        if i < 0 or i >= self.n:
            return None
        spot = self.v[i]
        if spot != spot:
            return None
        sg = self.sig[i]
        if sg != sg or sg <= 0:
            return None
        if leak == "spot":                  # DELIBERATE LEAK, positive control
            j = close_s - 1 - self.base
            if 0 <= j < self.n:
                x = self.v[j]
                if x == x:
                    spot = x
        if leak == "vol":                   # DELIBERATE LEAK, positive control
            j = now + 60 - self.base
            if 0 <= j < self.n and self.sig[j] == self.sig[j]:
                sg = self.sig[j]
        mu = (locked + r * spot) / N_AVG
        sd = sg * math.sqrt(var_factor(int(r), [1.0]))
        if sd <= 0:
            return None
        return dict(now=now, r=r, mu=mu, sigma=sg, sd=sd, spot=spot)

    def price(self, close_s, tau, K, rd, leak=None, st=None):
        """One (market, tau) row, or None if the tape cannot support it."""
        if st is None:
            st = self.state(close_s, tau, leak=leak)
        if st is None:
            return None
        r, mu, sg, sd, now = st["r"], st["mu"], st["sigma"], st["sd"], st["now"]
        K_eff = eff_strike(K, rd)
        fair_g = ND.cdf((mu - K_eff) / sd)
        req = (N_AVG / r) * (K_eff - mu)
        scale = sg * math.sqrt(S_r(r)) / r
        z0 = req / scale
        out = dict(r=r, mu=mu, sigma=sg, sd=sd, req=req, z0=z0, fair_g=fair_g)
        if leak:
            return out
        for W in WINDOWS_H:
            p, nn = self.tail(r, now, z0, W, std=True)
            out["std%d" % W] = p
            out["nstd%d" % W] = nn
        p, nn = self.tail(r, now, req, W_PRIMARY, std=False)
        out["raw%d" % W_PRIMARY] = p
        out["nraw%d" % W_PRIMARY] = nn
        # LEAK_EMP: the identical estimator with its trailing window slid so it
        # ENDS AFTER the close, i.e. it contains this market's own settlement
        # window. It is the positive control for THIS estimator: if the honest
        # column above were quietly reading the future, the two would agree.
        sh = ((close_s + 3600 - self.base) // 3600) - \
             (((now - self.base - r) // 3600) - 1)
        p, nn = self.tail(r, now, z0, W_PRIMARY, std=True, shift_h=sh)
        out["leakemp"] = p
        return out


# ===========================================================================
def _synth(kind, seed, hours=40, sigma=1.0):
    """A synthetic Dense with a known increment law, for the self-test.

    'gauss'  constant-sigma Gaussian walk. The model IS the truth here, so
             this is the NOTHING-PLANTED control.
    'volclu' identical unconditional variance, but sigma alternates every 90 s
             between 0.4x and 2.0x. The trailing-300 s sigma spans ~3.3 blocks
             and so converges to the blend regardless of the current block:
             the model's scale is right on average and wrong every second.
             That makes the standardised move distribution a fat mixture, and
             it is the realistic version of this failure -- volatility
             clustering faster than the sigma window, not exotic increments.
    """
    rng = random.Random(seed)
    n = hours * 3600
    d = idxload.Dense("SYN", 0, n)
    x = 1000.0
    blend = math.sqrt((0.4 ** 2 + 2.0 ** 2) / 2.0)
    for i in range(n):
        if kind == "gauss":
            s = sigma
        else:
            s = sigma * (0.4 if (i // 90) % 2 == 0 else 2.0) / blend
        x += rng.gauss(0.0, s)
        d.v[i] = x
    return d


def _world(kind, seed, rs, taus, sigma=1.0, leak=None, hours=40, ntest=4000,
           model=None, band=(0.980, 0.9975)):
    """Price synthetic closes in a known world; return decided-gate tallies.

    Strikes are placed so the HONEST Gaussian fair lands uniformly inside
    [band], i.e. right at the gate where the two estimators can disagree.
    Scattering strikes at random instead puts every call at fair 0.99999,
    where nothing discriminates -- the first version of this test did that and
    measured a 100% realised rate in every world, including a leaking one.
    """
    im = model
    if im is None:
        im = IndexModel(_synth(kind, seed, hours=hours, sigma=sigma), rs)
    d = im.d
    rng = random.Random(seed + 1)
    tal = dict(gn=0, gh=0, en=0, eh=0, gsum=0.0, esum=0.0, ratio=[], model=im)
    start = 30 * 3600
    for _ in range(ntest):
        close_s = rng.randrange(start, d.n - 120)
        tau = rng.choice(taus)
        honest = im.state(close_s, tau)
        if honest is None:
            continue
        f = rng.uniform(*band)
        if rng.random() < 0.5:
            f = 1.0 - f
        K = honest["mu"] - honest["sd"] * ND.inv_cdf(f)
        settle = sum(d.v[close_s - 60:close_s]) / 60.0
        won = 1.0 if settle >= K else 0.0
        st = im.state(close_s, tau, leak=leak) if leak else honest
        o = im.price(close_s, tau, K, 12, leak=leak, st=st)  # rd=12 -> K_eff~K
        if o is None:
            continue
        fg = o["fair_g"]
        if fg >= PIN or fg <= 1 - PIN:
            side = 1.0 if fg >= PIN else 0.0
            tal["gn"] += 1
            tal["gh"] += int(side == won)
            tal["gsum"] += fg if side else 1 - fg
            fe = o.get("std%d" % W_PRIMARY)
            if fe is not None:
                tal["esum"] += fe if side else 1 - fe
                tal["en"] += 1
                tal["eh"] += int(side == won)
                pg = (1 - fg) if side else fg
                pe = (1 - fe) if side else fe
                if pg > 0:
                    tal["ratio"].append(pe / pg)
    return tal


def selftest():
    print("SELF-TEST -- empfair")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # ---- sigma must equal pincal.sigma_from, the shipped definition ------
    rng = random.Random(11)
    d = idxload.Dense("T", 0, 6000)
    ticks = {}
    x = 50.0
    for i in range(6000):
        if rng.random() < 0.06:
            continue                              # gaps, like the real tape
        x += rng.gauss(0, 0.7)
        d.v[i] = x
        ticks[i] = x
    im = IndexModel(d, [3])
    import pincal
    worst = 0.0
    checked = 0
    for now in range(1000, 6000, 37):
        a = pincal.sigma_from(ticks, now)
        b = im.sig[now]
        if a is None:
            continue
        checked += 1
        worst = max(worst, abs(a - b) / a)
    ck(checked > 80 and worst < 1e-9,
       "sigma == pincal.sigma_from on %d seconds (worst rel. diff %.2e)"
       % (checked, worst))

    # ---- W3 causality ----------------------------------------------------
    try:
        im._assert_causal(0, (im.n // 3600) - 1, 3, im.base + 3600)
        ck(False, "a trailing window reaching past the decision second raises")
    except CausalError:
        ck(True, "a trailing window reaching past the decision second raises")

    rs = [2, 4, 9, 14, 19]
    taus = [3, 5, 10, 15, 20]

    # ---- W1 Gaussian world ----------------------------------------------
    g = _world("gauss", 5, rs, taus)
    gmodel = g["model"]
    gr = g["gh"] / max(g["gn"], 1)
    mr = sorted(g["ratio"])[len(g["ratio"]) // 2] if g["ratio"] else 0
    print("  W1 gaussian : %d gate calls, Gaussian realised %.2f%% "
          "(claimed %.2f%%), empirical claimed %.2f%%, "
          "median emp/gauss tail ratio %.2fx"
          % (g["gn"], 100 * gr, 100 * g["gsum"] / max(g["gn"], 1),
             100 * g["esum"] / max(g["en"], 1), mr))
    ck(g["gn"] > 120, "the harness produces gate calls at all (%d)" % g["gn"])
    ck(abs(gr - g["gsum"] / max(g["gn"], 1)) < 0.010,
       "a correct model calibrates in its own world (claimed %.2f%%, realised "
       "%.2f%%)" % (100 * g["gsum"] / max(g["gn"], 1), 100 * gr))
    ck(0.55 < mr < 1.9,
       "NOTHING PLANTED: empirical finds no material fat tail in a Gaussian "
       "world (ratio %.2fx, must be near 1)" % mr)

    # ---- W2 vol-clustering world ----------------------------------------
    t = _world("volclu", 5, rs, taus)
    tgr = t["gh"] / max(t["gn"], 1)
    tgc = t["gsum"] / max(t["gn"], 1)
    tec = t["esum"] / max(t["en"], 1)
    tmr = sorted(t["ratio"])[len(t["ratio"]) // 2] if t["ratio"] else 0
    print("  W2 vol-clus : %d gate calls, realised %.2f%%, Gaussian claimed "
          "%.2f%%, empirical claimed %.2f%%, median emp/gauss tail ratio %.2fx"
          % (t["gn"], 100 * tgr, 100 * tgc, 100 * tec, tmr))
    ck(t["gn"] > 400, "the vol-clustering world produces gate calls (%d)"
       % t["gn"])
    ck(tgc - tgr > 0.004,
       "PLANTED: the Gaussian IS overconfident when volatility clusters "
       "faster than its sigma window (claims %.2f%%, realises %.2f%%)"
       % (100 * tgc, 100 * tgr))
    ck(tec < tgc and abs(tec - tgr) < abs(tgc - tgr),
       "the empirical estimator is CLOSER to the realised rate (%.2f%% vs "
       "Gaussian %.2f%%, realised %.2f%%)" % (100 * tec, 100 * tgc, 100 * tgr))
    ck(tmr > 1.25,
       "the tail ratio SEES the planted fat tail (%.2fx, must be >1.25)" % tmr)

    # ---- W4 leak detector ------------------------------------------------
    lk = _world("gauss", 5, rs, taus, leak="spot", model=gmodel)
    lr = lk["gh"] / max(lk["gn"], 1)
    print("  W4 LEAK_SPOT in the Gaussian world: %d gate calls, realised "
          "%.2f%% vs honest %.2f%%" % (lk["gn"], 100 * lr, 100 * gr))
    ck((1 - lr) < 0.5 * (1 - gr),
       "a planted leak scores implausibly better and the harness SEES it "
       "(%.2f%% vs %.2f%%) -- a harness that cannot catch a planted leak is "
       "not evidence against an unplanted one" % (100 * lr, 100 * gr))

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a, _ = ap.parse_known_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    raise SystemExit("run empscore.py; this module is the estimator + selftest")
