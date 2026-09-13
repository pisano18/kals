#!/usr/bin/env python3
# VERSION: 2026-09-13-rl1
"""pinruler.py -- EVERY WAY OF MEASURING VOLATILITY, SCORED AGAINST THE TAPE.

THE OPERATOR, 2026-09-13: "do a deep dive into it and see if you can find any
new things methods or ways to improve it. Like changing the time length around,
adding more intervals, checking other data, calculating with the data
different, doing a combination of, and that's just my examples you should be
checking more than that... Make sure to test it extensively, accuracy above
all."

WHAT THIS IS FOR. `results/PREREG_ruler.md` established that the model's
biggest identified weakness is the RULER: sigma measured over the last 300
seconds. A quiet 300 seconds understates the next minute, the model's
uncertainty is too small, and it walks into a 96c ticket believing it is safe.
`max(300s, 3600s)` was deployed 2026-09-13 11:10Z because it was the best of
the six things tried. This file tries thirty-odd, properly.

HOW A RULER IS SCORED. Not by "fewer blow-ups" -- a ruler that simply returns a
huge number has none, and is useless. Three numbers together:

  CALIBRATION   sd(z) should be 1.000. Below 1 is timid, above 1 is
                overconfident. This is the honest target.
  SHAPE         kurtosis. SCALE-FREE: multiplying every sd by a constant cannot
                change it. So an improvement here CANNOT be bought with
                timidity, which makes it the one number that cannot be gamed.
  COST          how many decisions still clear the live gate, and how often
                those lose. A ruler that keeps nothing is not a fix.

The decisions are rebuilt from the index alone -- `strike(N+1) == settle(N)` is
exact (CLAUDE.md's settlement model), so the previous window's settlement IS
this window's strike. No order book, no replay, no fills, no P&L.

SPEED. A naive pass recomputes a 3600-second window at every one of ~650,000
decision points: 2.3 billion operations. Every moment-based estimator here is
instead read off PREFIX SUMS built once per series, so a window of any length
costs the same as a window of one second. That is what makes thirty estimators
affordable. The estimators that cannot be prefix-summed (median-based ones)
say so and are scored on a subsample, which is stated rather than hidden.
"""
import argparse
import json
import math
import os
import random
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pincalib                                                # noqa: E402
from engine import var_factor, N_AVG                           # noqa: E402

TAUS = (5, 10, 15, 20, 25, 30)
WINDOW = 60
PIN = 0.995
GATE_Z = pincalib.norm_ppf(PIN)
SUB = 1              # score every Nth close; 1 = all


# ---------------------------------------------------------------------------
# 1. PREFIX SUMS -- the reason this file can afford thirty estimators
# ---------------------------------------------------------------------------
class Series:
    """One index series with O(1) window statistics.

    Every array is indexed by (second - t0). A second whose predecessor is
    missing contributes NOTHING to any sum and is not counted -- gaps are
    skipped, never bridged, because bridging a four-second hole turns one long
    move into one enormous 'one-second' move and manufactures the very jumps
    this whole line of work is about.
    """

    __slots__ = ("t0", "t1", "val", "n", "c_n", "c_d", "c_d2", "c_abs",
                 "c_bp", "c_dn2", "c_up2", "c_d4")

    def __init__(self, ser):
        self.t0 = min(ser)
        self.t1 = max(ser)
        n = self.t1 - self.t0 + 1
        self.n = n
        self.val = ser
        c_n = [0] * (n + 1)
        c_d = [0.0] * (n + 1)
        c_d2 = [0.0] * (n + 1)
        c_abs = [0.0] * (n + 1)
        c_bp = [0.0] * (n + 1)
        c_dn2 = [0.0] * (n + 1)
        c_up2 = [0.0] * (n + 1)
        c_d4 = [0.0] * (n + 1)
        prev_d = None
        g = ser.get
        for i in range(n):
            t = self.t0 + i
            v = g(t)
            pv = g(t - 1)
            d = (v - pv) if (v is not None and pv is not None) else None
            c_n[i + 1] = c_n[i] + (1 if d is not None else 0)
            c_d[i + 1] = c_d[i] + (d if d is not None else 0.0)
            c_d2[i + 1] = c_d2[i] + (d * d if d is not None else 0.0)
            c_abs[i + 1] = c_abs[i] + (abs(d) if d is not None else 0.0)
            c_bp[i + 1] = c_bp[i] + (abs(d) * abs(prev_d)
                                     if (d is not None and prev_d is not None)
                                     else 0.0)
            c_dn2[i + 1] = c_dn2[i] + (d * d if (d is not None and d < 0)
                                       else 0.0)
            c_up2[i + 1] = c_up2[i] + (d * d if (d is not None and d > 0)
                                       else 0.0)
            c_d4[i + 1] = c_d4[i] + (d * d * d * d if d is not None else 0.0)
            prev_d = d
        self.c_n, self.c_d, self.c_d2 = c_n, c_d, c_d2
        self.c_abs, self.c_bp = c_abs, c_bp
        self.c_dn2, self.c_up2 = c_dn2, c_up2
        self.c_d4 = c_d4

    def _idx(self, t):
        return min(max(t - self.t0, 0), self.n)

    def win(self, t, w):
        """(count, sum d, sum d^2, sum |d|, sum bipower, sum dn^2, sum up^2)
        over the w seconds ending at t inclusive.

        THE WINDOW HOLDS w SECONDS AND THEREFORE AT MOST w-1 DIFFERENCES. The
        first second in it has no predecessor INSIDE the window, so its
        difference -- which straddles the edge -- must not be counted. Getting
        this wrong put 0.5144 where pincalib's straight loop gives 0.5152: a
        0.16% error, far too small to notice by eye on a real tape and more
        than enough to make every number in this file disagree with the file
        that produced the finding. The self-test demands bit-for-bit equality
        for exactly that reason.
        """
        b = self._idx(t) + 1
        a = self._idx(t - w + 2)
        if b <= a:
            return (0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        return (self.c_n[b] - self.c_n[a],
                self.c_d[b] - self.c_d[a],
                self.c_d2[b] - self.c_d2[a],
                self.c_abs[b] - self.c_abs[a],
                self.c_bp[b] - self.c_bp[a],
                self.c_dn2[b] - self.c_dn2[a],
                self.c_up2[b] - self.c_up2[a])

    def sd(self, t, w, minn=20):
        n, sd_, sd2, _a, _b, _dn, _up = self.win(t, w)
        if n < minn:
            return None
        m = sd_ / n
        v = (sd2 - n * m * m) / (n - 1) if n > 1 else 0.0
        return math.sqrt(v) if v > 0 else None

    def mad_like(self, t, w, minn=20):
        """mean|d| * sqrt(pi/2) -- an sd estimate that a single huge move moves
        far less than the square-based one does."""
        n, _s, _s2, sa, _b, _dn, _up = self.win(t, w)
        if n < minn:
            return None
        return (sa / n) * math.sqrt(math.pi / 2.0)

    def bipower(self, t, w, minn=20):
        """Bipower variation: sqrt(mean(|d_i| |d_{i-1}|) * pi/2).

        JUMP-ROBUST BY CONSTRUCTION. A single jump enters only two products
        rather than one giant square, so this estimates the CONTINUOUS part of
        volatility. Included because if the fix is really about jumps, a ruler
        that deliberately EXCLUDES them should do WORSE -- and that is a
        falsifiable prediction rather than another knob.
        """
        n, _s, _s2, _a, bp, _dn, _up = self.win(t, w)
        if n < minn or bp <= 0:
            return None
        return math.sqrt((bp / n) * (math.pi / 2.0))

    def quartic(self, t, w, minn=20):
        """(mean d^4)^(1/4) -- the jump-HEAVY counterpart to bipower.

        Bipower deliberately excludes jumps and, on this tape, is one of the
        WORST rulers tested: sd(z) 1.51 and a gated loss rate 53% above the
        300-second baseline. That is the falsifiable prediction of the jump
        story coming true. This is the opposite end of the same axis -- a
        fourth moment weights a single large move enormously -- so if the
        story is right this should be among the BEST. A ruler family where
        both ends behave as the mechanism predicts is evidence; one tuned knob
        is not.

        For a Gaussian, (E d^4)^(1/4) = 3^(1/4) * sigma, so the constant below
        makes it an unbiased sd estimate on jump-free data and the self-test
        checks exactly that.
        """
        b = self._idx(t) + 1
        a = self._idx(t - w + 2)
        if b <= a:
            return None
        cnt = self.c_n[b] - self.c_n[a]
        if cnt < minn:
            return None
        q = (self.c_d4[b] - self.c_d4[a]) / cnt
        if q <= 0:
            return None
        return (q ** 0.25) / (3.0 ** 0.25)

    def semi(self, t, w, side="down", minn=20):
        """Downside-only (or upside-only) deviation, scaled by sqrt(2).

        WE ONLY LOSE ON ONE SIDE. The model's claim is one-sided -- the settle
        lands above the strike -- so a ruler built from the moves that could
        hurt us is a different object from one built from all of them, and
        nobody here has ever tried it.
        """
        n, _s, _s2, _a, _b, dn, up = self.win(t, w)
        if n < minn:
            return None
        q = dn if side == "down" else up
        if q <= 0:
            return None
        return math.sqrt(2.0 * q / n)

    def ewma(self, t, halflife, span=None, minn=20):
        """Exponentially weighted sd. NOT prefix-summable, so it is computed
        over a truncated window of `span` seconds -- long enough that the
        dropped tail carries under 1% of the weight."""
        if span is None:
            span = int(halflife * 8)
        lam = 0.5 ** (1.0 / halflife)
        g = self.val.get
        num = 0.0
        den = 0.0
        cnt = 0
        w = 1.0
        for k in range(span):
            s = t - k
            v = g(s)
            pv = g(s - 1)
            if v is not None and pv is not None:
                d = v - pv
                num += w * d * d
                den += w
                cnt += 1
            w *= lam
        if cnt < minn or den <= 0:
            return None
        return math.sqrt(num / den)


# ---------------------------------------------------------------------------
# 2. THE ESTIMATORS
# ---------------------------------------------------------------------------
def make_rulers():
    """label -> f(Series, t) -> sigma or None. Order is report order."""
    R = {}

    def w_sd(w):
        return lambda S, t: S.sd(t, w)
    for w in (60, 120, 300, 600, 900, 1800, 3600):
        R["sd %ds" % w] = w_sd(w)

    def mx(ws):
        def f(S, t):
            vs = [S.sd(t, w) for w in ws]
            vs = [v for v in vs if v]
            return max(vs) if vs else None
        return f
    for ws in ((300, 900), (300, 1800), (300, 3600), (60, 3600),
               (300, 1800, 3600), (60, 300, 3600)):
        R["max" + str(ws)] = mx(ws)

    def blend(a, b, wa):
        def f(S, t):
            x, y = S.sd(t, a), S.sd(t, b)
            if not x or not y:
                return x or y
            return wa * x + (1.0 - wa) * y
        return f
    R["0.5*300+0.5*3600"] = blend(300, 3600, 0.5)
    R["0.3*300+0.7*3600"] = blend(300, 3600, 0.3)
    R["0.7*300+0.3*3600"] = blend(300, 3600, 0.7)

    def geo(a, b):
        def f(S, t):
            x, y = S.sd(t, a), S.sd(t, b)
            if not x or not y:
                return x or y
            return math.sqrt(x * y)
        return f
    R["geomean(300,3600)"] = geo(300, 3600)

    for hl in (60, 300, 900, 1800):
        R["ewma hl=%ds" % hl] = (lambda h: lambda S, t: S.ewma(t, h))(hl)

    def mx_ewma(hl, w):
        def f(S, t):
            a, b = S.ewma(t, hl), S.sd(t, w)
            if not a or not b:
                return a or b
            return max(a, b)
        return f
    R["max(ewma300, sd3600)"] = mx_ewma(300, 3600)

    for w in (300, 3600):
        R["mean|d| %ds" % w] = (lambda W: lambda S, t: S.mad_like(t, W))(w)
        R["bipower %ds" % w] = (lambda W: lambda S, t: S.bipower(t, W))(w)
    R["max(mean|d|300, mean|d|3600)"] = (
        lambda S, t: (lambda a, b: max(a, b) if (a and b) else (a or b))(
            S.mad_like(t, 300), S.mad_like(t, 3600)))

    for w in (300, 3600):
        R["downside %ds" % w] = (
            lambda W: lambda S, t: S.semi(t, W, "down"))(w)
    R["max(down300, down3600)"] = (
        lambda S, t: (lambda a, b: max(a, b) if (a and b) else (a or b))(
            S.semi(t, 300, "down"), S.semi(t, 3600, "down")))
    R["max(sd300, down3600)"] = (
        lambda S, t: (lambda a, b: max(a, b) if (a and b) else (a or b))(
            S.sd(t, 300), S.semi(t, 3600, "down")))

    # A HARD FLOOR rather than a longer window: never let the ruler read below
    # a fixed fraction of the day's own typical level. Different mechanism
    # from a max() of two windows and worth separating.
    def floored(w, long_w, frac):
        def f(S, t):
            a, b = S.sd(t, w), S.sd(t, long_w)
            if not a:
                return b
            if not b:
                return a
            return max(a, frac * b)
        return f
    for w in (300, 3600):
        R["quartic %ds" % w] = (lambda W: lambda S, t: S.quartic(t, W))(w)
    R["max(sd300, quartic3600)"] = (
        lambda S, t: (lambda a, b: max(a, b) if (a and b) else (a or b))(
            S.sd(t, 300), S.quartic(t, 3600)))
    R["max(quartic300, quartic3600)"] = (
        lambda S, t: (lambda a, b: max(a, b) if (a and b) else (a or b))(
            S.quartic(t, 300), S.quartic(t, 3600)))
    R["max(sd300, down1800)"] = (
        lambda S, t: (lambda a, b: max(a, b) if (a and b) else (a or b))(
            S.sd(t, 300), S.semi(t, 1800, "down")))
    # THE OPERATOR'S QUESTION, 2026-09-13: "are you sure that reading price
    # movement in the other direction doesn't help know when it may go sharply
    # in the bad direction?" It is a fair question and the answer was assumed
    # rather than measured. UP moves are now scored on their own and against
    # the down ones, so the asymmetry is a finding instead of a guess.
    for w in (300, 1800, 3600):
        R["upside %ds" % w] = (lambda W: lambda S, t: S.semi(t, W, "up"))(w)
    R["max(up300, up1800)"] = (
        lambda S, t: (lambda a, b: max(a, b) if (a and b) else (a or b))(
            S.semi(t, 300, "up"), S.semi(t, 1800, "up")))
    R["max(up1800, down1800)"] = (
        lambda S, t: (lambda a, b: max(a, b) if (a and b) else (a or b))(
            S.semi(t, 1800, "up"), S.semi(t, 1800, "down")))
    R["max(down300, down1800)"] = (
        lambda S, t: (lambda a, b: max(a, b) if (a and b) else (a or b))(
            S.semi(t, 300, "down"), S.semi(t, 1800, "down")))
    R["max(60, 1800)"] = mx((60, 1800))
    R["sd300 floored at 0.7*sd3600"] = floored(300, 3600, 0.7)
    R["sd300 floored at 1.3*sd3600"] = floored(300, 3600, 1.3)
    return R


# ---------------------------------------------------------------------------
# 3. SCORING
# ---------------------------------------------------------------------------
class Acc:
    """Streaming moments. THE REASON THIS IS NOT A LIST.

    Keeping every decision for every ruler is 33 x 650,000 tuples, which took
    this box from 5.3 GB free to 3.0 GB and still climbing. CLAUDE.md's
    resource protocol exists because an analysis job once OOM-killed the
    collector, and the tape is unreproducible while an analysis result is not.
    Everything the report needs -- sd, kurtosis, gate counts, tail counts --
    is a sum of powers, so nothing has to be stored at all.
    """

    __slots__ = ("n", "s1", "s2", "s3", "s4", "gate", "gate_loss", "tail")

    def __init__(self):
        self.n = 0
        self.s1 = self.s2 = self.s3 = self.s4 = 0.0
        self.gate = 0
        self.gate_loss = 0
        self.tail = 0

    def add(self, z, conf, won):
        self.n += 1
        z2 = z * z
        self.s1 += z
        self.s2 += z2
        self.s3 += z2 * z
        self.s4 += z2 * z2
        if conf >= PIN:
            self.gate += 1
            if not won:
                self.gate_loss += 1
        if z < -GATE_Z:
            self.tail += 1

    def stats(self):
        """(n, sd, kurtosis, gate n, gate loss rate, tail rate)."""
        n = self.n
        if n < 10:
            return None
        m = self.s1 / n
        var = (self.s2 - n * m * m) / (n - 1)
        sd = math.sqrt(var) if var > 0 else 0.0
        if sd <= 0:
            return n, 0.0, float("nan"), self.gate, float("nan"), 0.0
        # E[(z-m)^4] from raw power sums
        m4 = (self.s4 - 4 * m * self.s3 + 6 * m * m * self.s2
              - 4 * m ** 3 * self.s1 + n * m ** 4) / n
        k = m4 / (sd ** 4)
        gl = (self.gate_loss / self.gate) if self.gate else float("nan")
        return n, sd, k, self.gate, gl, self.tail / n


def decisions(index, rulers, taus=TAUS, sub=SUB, cut=None, say=print):
    """{label: (train Acc, holdout Acc)} -- nothing is retained per decision.

    One series at a time so the prefix arrays never all exist at once, and the
    index entry is dropped as soon as its series is done.
    """
    out = {lab: (Acc(), Acc()) for lab in rulers}
    items = sorted(index.items())
    for iid, ser in items:
        if not ser or len(ser) < 8000:
            continue
        S = Series(ser)
        settles = {}
        c = S.t0 - (S.t0 % 900) + 900
        while c <= S.t1:
            settles[c] = pincalib.settle_of(ser, c)
            c += 900
        c = S.t0 - (S.t0 % 900) + 900
        idx_close = 0
        n_dec = 0
        while c <= S.t1:
            idx_close += 1
            if sub > 1 and idx_close % sub:
                c += 900
                continue
            K = settles.get(c - 900)
            settle = settles.get(c)
            if K is None or settle is None:
                c += 900
                continue
            half = 1 if (cut is not None and c >= cut) else 0
            for tau in taus:
                now = c - tau
                spot = ser.get(now - 1)
                if spot is None:
                    continue
                locked = 0.0
                ok = True
                for sec in range(c - WINDOW, c - tau):
                    v = ser.get(sec)
                    if v is None:
                        ok = False
                        break
                    locked += v
                if not ok:
                    continue
                mu = (locked + tau * spot) / float(N_AVG)
                vf = math.sqrt(var_factor(int(tau), [1.0]))
                up = settle >= K
                for lab, f in rulers.items():
                    sg = f(S, now - 1)
                    if not sg:
                        continue
                    sd = sg * vf
                    if sd <= 0:
                        continue
                    zc = (mu - K) / sd
                    won = up if zc >= 0 else (not up)
                    out[lab][half].add((settle - mu) / sd,
                                       pincalib.norm_cdf(abs(zc)), won)
                n_dec += 1
            c += 900
        del S
        index[iid] = {}
        if say:
            say("    %-14s %d decisions" % (iid, n_dec))
    return out


def split(rows, frac=0.70):
    cs = sorted({r[0] for r in rows})
    if not cs:
        return [], []
    cut = cs[int(frac * len(cs))]
    return [r for r in rows if r[0] < cut], [r for r in rows if r[0] >= cut]


# ---------------------------------------------------------------------------
def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    rnd = random.Random(7)
    ser = {}
    v = 100.0
    for t in range(1000, 9000):
        v += rnd.gauss(0.0, 0.5)
        ser[t] = v
    S = Series(ser)

    direct = pincalib.sigma_window(ser, 8000, 300)
    fast = S.sd(8000, 300)
    ck(direct and fast and abs(direct - fast) < 1e-9,
       "the prefix-sum sd reproduces pincalib's straight loop EXACTLY "
       "(%.10f vs %.10f) -- the whole speed-up is worthless if it does not"
       % (fast, direct))
    ck(abs(S.sd(8000, 3600) - pincalib.sigma_window(ser, 8000, 3600)) < 1e-9,
       "and at an hour as well")

    # gaps must be skipped, not bridged
    g = dict(ser)
    for t in range(7000, 7010):
        del g[t]
    Sg = Series(g)
    ck(abs(Sg.sd(8000, 3600) - pincalib.sigma_window(g, 8000, 3600)) < 1e-9,
       "and with a ten-second hole in the window, still exactly")

    ck(S.sd(8000, 3600) > 0 and S.mad_like(8000, 3600) > 0,
       "mean|d| returns a positive estimate")
    ck(abs(S.mad_like(8000, 3600) / S.sd(8000, 3600) - 1.0) < 0.12,
       "and on Gaussian data it lands within 12%% of the sd it estimates "
       "(%.3f)" % (S.mad_like(8000, 3600) / S.sd(8000, 3600)))
    ck(abs(S.bipower(8000, 3600) / S.sd(8000, 3600) - 1.0) < 0.15,
       "bipower too, on data with no jumps in it (%.3f)"
       % (S.bipower(8000, 3600) / S.sd(8000, 3600)))
    ck(abs(S.semi(8000, 3600, "down") / S.sd(8000, 3600) - 1.0) < 0.15,
       "and the downside deviation, since a symmetric world has symmetric "
       "halves (%.3f)" % (S.semi(8000, 3600, "down") / S.sd(8000, 3600)))

    # bipower must IGNORE a jump that the plain sd swallows
    j = dict(ser)
    for t in range(5000, 9000):
        j[t] = j[t] + 200.0                       # one huge move at t=5000
    Sj = Series(j)
    r_sd = Sj.sd(8000, 3600) / S.sd(8000, 3600)
    r_bp = Sj.bipower(8000, 3600) / S.bipower(8000, 3600)
    ck(r_sd > r_bp,
       "one planted jump inflates the plain sd more than bipower (%.2fx vs "
       "%.2fx) -- which is what makes bipower a falsifiable test of the jump "
       "story rather than another knob" % (r_sd, r_bp))

    ck(abs(S.quartic(8000, 3600) / S.sd(8000, 3600) - 1.0) < 0.15,
       "the fourth-moment ruler is unbiased on jump-free Gaussian data "
       "(%.3f)" % (S.quartic(8000, 3600) / S.sd(8000, 3600)))
    r_q = Sj.quartic(8000, 3600) / S.quartic(8000, 3600)
    ck(r_q > r_sd > r_bp,
       "and one planted jump inflates it MORE than the plain sd, which in "
       "turn beats bipower (%.2fx > %.2fx > %.2fx). The three sit in that "
       "order by construction, so the family spans the jump axis rather than "
       "sampling one point on it" % (r_q, r_sd, r_bp))

    # downside must react to a one-sided world
    dn = {}
    v = 100.0
    for t in range(1000, 9000):
        step = rnd.gauss(0.0, 0.2)
        if rnd.random() < 0.02:
            step -= 3.0                            # drops only
        v += step
        dn[t] = v
    Sd = Series(dn)
    ck(Sd.semi(8000, 3600, "down") > Sd.semi(8000, 3600, "up"),
       "in a world where only the DOWN moves are large, the downside ruler "
       "reads larger than the upside one (%.4f vs %.4f)"
       % (Sd.semi(8000, 3600, "down"), Sd.semi(8000, 3600, "up")))

    ck(S.ewma(8000, 300) is not None
       and abs(S.ewma(8000, 300) / S.sd(8000, 300) - 1.0) < 0.35,
       "the EWMA is in the same ballpark as the window sd on flat data "
       "(%.3f)" % (S.ewma(8000, 300) / S.sd(8000, 300)))

    rulers = make_rulers()
    ck(len(rulers) >= 25, "%d rulers defined" % len(rulers))
    ck(all(callable(f) for f in rulers.values()), "all of them callable")
    ck(all(rulers[k](S, 8000) is None or rulers[k](S, 8000) > 0
           for k in rulers),
       "and every one returns a positive sigma or None on real-shaped data")

    # scoring: a ruler that is twice too wide must show sd(z) ~ 0.5
    zs = [random.gauss(0, 1) for _ in range(20000)]
    A1 = Acc()
    A2 = Acc()
    for z in zs:
        A1.add(z, 0.999, True)
        A2.add(z * 0.5, 0.999, True)
    s1 = A1.stats()
    s2 = A2.stats()
    ck(abs(s1[1] - 1.0) < 0.04,
       "the streaming accumulator reads sd(z)=1 on standard-normal z (%.3f)"
       % s1[1])
    ck(abs(s1[2] - 3.0) < 0.25,
       "and kurtosis 3 (%.2f)" % s1[2])
    ck(abs(s2[1] - 0.5) < 0.03,
       "0.5 when every z is halved -- a ruler twice too wide (%.3f)" % s2[1])
    ck(abs(s2[2] - s1[2]) < 1e-6,
       "while KURTOSIS is IDENTICAL (%.4f vs %.4f). That is the property that "
       "stops a timid ruler from buying a good score, and it must hold to "
       "machine precision, not approximately" % (s2[2], s1[2]))
    # stats() needs at least 10 observations, so the fixture has 10: four
    # losers and six winners, all of them inside the gate.
    Ag = Acc()
    for z in (-9.0, -9.0, -9.0, -9.0, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1):
        Ag.add(z, 0.999, z > -1.0)
    sg = Ag.stats()
    ck(sg[3] == 10 and abs(sg[4] - 0.4) < 1e-9,
       "and it counts the gated losses it is handed (%d gated, %.2f lost)"
       % (sg[3], sg[4]))
    Au = Acc()
    for z in (-9.0, 0.1):
        Au.add(z, 0.99, True)          # below PIN: must not enter the gate
    ck(Au.gate == 0,
       "a decision under the PIN never enters the gate count")
    print("pinruler selftest: %d checks OK" % n[0])
    return 0


# ---------------------------------------------------------------------------
def report(res, out_path, say=print, window=""):
    lines = []
    w = lines.append
    base = "sd 300s"

    def merged(lab):
        a, b = res[lab]
        m = Acc()
        for src in (a, b):
            m.n += src.n
            m.s1 += src.s1
            m.s2 += src.s2
            m.s3 += src.s3
            m.s4 += src.s4
            m.gate += src.gate
            m.gate_loss += src.gate_loss
            m.tail += src.tail
        return m.stats()

    b = merged(base) if base in res else None
    w("# RESULTS_ruler -- every way of measuring volatility, scored")
    w("")
    w("*`research/pinruler.py`, %s. %s. Decisions rebuilt from the settlement "
      "index alone using `strike(N+1) == settle(N)`; no order book, no replay, "
      "no fills, no P&L.*"
      % (time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), window))
    w("")
    w("`sd 300s` is what the bot used until 2026-09-13 11:10Z. "
      "`max(300, 3600)` is what it runs now.")
    w("")
    w("**How a ruler is scored.** `sd(z)` should be **1.000** -- below is "
      "timid, above is overconfident. **Kurtosis is scale-free**, so an "
      "improvement there cannot be bought by widening the ruler; it is the one "
      "number that cannot be gamed. `gate n` is how many decisions still clear "
      "the live PIN of 0.995 and `gate loss` how often those lose. A ruler "
      "wins only by improving BOTH shape and loss without giving up the gate.")
    w("")
    w("| ruler | sd(z) | kurtosis | gate n | vs base | gate loss | vs base |")
    w("|---|---|---|---|---|---|---|")
    rows = []
    for lab in res:
        sc = merged(lab)
        if sc is None:
            continue
        rows.append((lab, sc))
    rows.sort(key=lambda x: (abs(x[1][1] - 1.0), x[1][4]))
    for lab, sc in rows:
        n_, s_, k_, gn, gl, _tl = sc
        dn = (100.0 * (gn / b[3] - 1.0)) if (b and b[3]) else float("nan")
        dl = (100.0 * (gl / b[4] - 1.0)) if (b and b[4]) else float("nan")
        mark = lab in (base, "max(300, 3600)")
        nm = ("**`%s`**" % lab) if mark else ("`%s`" % lab)
        w("| %s | %.3f | %.1f | %d | %+.1f%% | %.4f%% | %+.1f%% |"
          % (nm, s_, k_, gn, dn, 100 * gl, dl))
    w("")
    w("## Holdout -- first 70% of closes against the last 30%")
    w("")
    w("A ruler that is better only in the half it was chosen on is not better.")
    w("")
    w("| ruler | sd(z) train | sd(z) holdout | kurt train | kurt holdout | "
      "gate loss train | holdout |")
    w("|---|---|---|---|---|---|---|")
    for lab, _sc in rows:
        a_, b_ = res[lab]
        sa, sb = a_.stats(), b_.stats()
        if not sa or not sb:
            continue
        w("| `%s` | %.3f | %.3f | %.1f | %.1f | %.4f%% | %.4f%% |"
          % (lab, sa[1], sb[1], sa[2], sb[2], 100 * sa[4], 100 * sb[4]))
    w("")
    txt = "\n".join(lines) + "\n"
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(txt)
    say(txt)
    return txt


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--sub", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(HERE), "results", "RESULTS_ruler.md"))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    import replay                                              # noqa: E402
    idx = replay.load_index(a.data, verbose=False)
    if not idx:
        print("pinruler: no cfbenchmarks_value on disk -- nothing to analyse")
        return 0
    rulers = make_rulers()
    print("  %d rulers over %d index series" % (len(rulers), len(idx)))
    t0 = time.time()
    lo = min(min(v) for v in idx.values() if v)
    hi = max(max(v) for v in idx.values() if v)
    cut = lo + int(0.70 * (hi - lo))
    cut -= cut % 900
    print("  holdout cut at %s"
          % time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(cut)))
    res = decisions(idx, rulers, sub=a.sub, cut=cut)
    tot = sum(v[0].n + v[1].n for v in res.values())
    if not tot:
        print("pinruler: no decision could be rebuilt -- nothing to analyse")
        return 0
    window = ("%d decisions per ruler, %s .. %s (%.1f days)"
              % (max(v[0].n + v[1].n for v in res.values()),
                 time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(lo)),
                 time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(hi)),
                 (hi - lo) / 86400.0))
    report(res, a.out, window=window)
    print("  %.0f s" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
