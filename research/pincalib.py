#!/usr/bin/env python3
# VERSION: 2026-09-13-cal1
"""pincalib.py -- IS THE MODEL'S UNCERTAINTY RIGHT, AND WHEN DID IT STOP BEING?

THE OPERATOR, 2026-09-13: "figuring out why we lose MORE now" and "Stop
trusting that stupid backtest it's never been accurate about anything."

Both are honoured by the same design decision. THIS FILE TOUCHES NO BACKTEST.
It never opens the order book, never replays a decision, never computes a fill,
never computes P&L. It reads the 1-per-second settlement index and nothing
else. Every number below is arithmetic on prints that actually happened.

WHAT IS MEASURED. With `tau` seconds left the model's point forecast of the
settlement value is

    mu = (locked + tau * spot) / 60

-- the prints already recorded, plus the current spot held flat for the
seconds still to come. Its claimed uncertainty is

    sd = sigma * sqrt(var_factor(tau))

with sigma the standard deviation of 1-second index changes over the trailing
300 seconds, exactly as `pinrun.IndexWS.sigma` computes it. Then

    z = (settle - mu) / sd

is how many of its own standard deviations the model missed by. IF THE MODEL IS
RIGHT, z IS STANDARD NORMAL. That claim is falsifiable on the index alone and
needs no market, no counterparty and no trade.

WHY THIS IS THE RIGHT QUESTION RIGHT NOW. Measured 2026-09-13: the model's
stated confidence barely moved between the first 70% of closes and the last
30% (0.99851 -> 0.99837) while its realised error went from 12.5x its own
claim to 28.2x. The other side did not change -- same contest rate, same
speed, more depth. So the deterioration is in the model, and a model's error
lives in exactly one place: the width of the distribution it assumes.

WHAT IT CANNOT SAY. Nothing here is our loss rate and nothing here may be
quoted as one (CLAUDE.md 2026-09-10, rule 5). This is a statement about the
INDEX and the MODEL, which is precisely what rule 5 leaves the tape valid for.
Whether we lose money depends on who sells to us, and that is not in this file.

THE ONE ASSUMPTION, STATED. `mu` holds spot flat for the remaining seconds.
That is the model's own assumption, not an approximation introduced here -- if
it is wrong, this file is measuring exactly the thing that is wrong, which is
the point.
"""
import argparse
import math
import os
import random
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor, N_AVG                          # noqa: E402

TAUS = (5, 10, 15, 20, 25, 30)
SIGMA_WIN = 300          # pinrun.SIGMA_WIN, and the self-test asserts it
MIN_DIFFS = 20           # pinrun refuses a sigma on fewer
WINDOW = 60              # the settlement window, [close-60, close-1]
# The confidence levels the live gate actually operates at. PIN is 0.995 and
# the mean stated confidence on traded candidates is ~0.9985, so these are the
# tails that decide whether we win, not decorative round numbers.
LEVELS = (0.99, 0.995, 0.9985, 0.999, 0.9999)


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p):
    """Inverse normal by bisection. Exact enough at these tails and it cannot
    be wrong in a way that flatters the model, which a rational approximation
    silently can."""
    lo, hi = -12.0, 12.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
def sigma_at(series, t):
    """sd of 1-second changes over the trailing SIGMA_WIN seconds ending at t.

    A COPY OF pinrun.IndexWS.sigma's ARITHMETIC, deliberately: that method
    reads a live dict under a lock and cannot be driven from a tape. The
    self-test plants a series with a known sd and requires this to recover it,
    and asserts SIGMA_WIN and MIN_DIFFS still match pinrun's constants, so a
    drift in either is caught rather than assumed away.
    """
    secs = [s for s in range(t - SIGMA_WIN + 1, t + 1) if s in series]
    if len(secs) < 30:
        return None
    diffs = [series[secs[i]] - series[secs[i - 1]]
             for i in range(1, len(secs)) if secs[i] - secs[i - 1] == 1]
    if len(diffs) < MIN_DIFFS:
        return None
    mu = sum(diffs) / len(diffs)
    return math.sqrt(sum((x - mu) ** 2 for x in diffs) / (len(diffs) - 1))


def settle_of(series, close_s):
    """The settlement value: mean of the 60 prints in [close-60, close-1].

    Returns None unless ALL SIXTY are present. A settlement averaged over 57
    prints is a different number from the one the exchange settles on, and
    filling the gaps with the window mean is the exact bug pinrun's CORRECTION
    3 was written for.
    """
    vals = []
    for s in range(close_s - WINDOW, close_s):
        v = series.get(s)
        if v is None:
            return None
        vals.append(v)
    return sum(vals) / float(WINDOW)


def zscore(series, close_s, tau):
    """(z, sd, mu, settle) -- how many of its own sds the model missed by.

    `locked` is the prints in [close-60, close-tau-1]; `tau` prints remain and
    the model holds spot flat across them. That split is pinrun.partial's, and
    a print that has not arrived counts as still to come rather than being
    guessed at.
    """
    settle = settle_of(series, close_s)
    if settle is None:
        return None
    now = close_s - tau
    spot = series.get(now - 1)
    if spot is None:
        return None
    locked = 0.0
    for s in range(close_s - WINDOW, close_s - tau):
        v = series.get(s)
        if v is None:
            return None
        locked += v
    sg = sigma_at(series, now - 1)
    if sg is None or sg <= 0:
        return None
    mu = (locked + tau * spot) / float(N_AVG)
    sd = sg * math.sqrt(var_factor(int(tau), [1.0]))
    if sd <= 0:
        return None
    return (settle - mu) / sd, sd, mu, settle


def collect(index, taus=TAUS, say=print):
    """[(index_id, close_s, tau, z)] over every complete close on the tape."""
    out = []
    skipped = defaultdict(int)
    for iid, series in index.items():
        if not series:
            continue
        lo, hi = min(series), max(series)
        c = lo - (lo % 900) + 900
        while c <= hi:
            for tau in taus:
                r = zscore(series, c, tau)
                if r is None:
                    skipped[tau] += 1
                else:
                    out.append((iid, c, tau, r[0]))
            c += 900
    if say:
        say("  z-scores: %d usable, %d (close, tau) cells incomplete"
            % (len(out), sum(skipped.values())))
    return out


# ---------------------------------------------------------------------------
def tail_table(rows, levels=LEVELS):
    """For each confidence the gate uses: promised failure rate vs realised.

    One-sided, because the model's claim IS one-sided -- it says the settle
    will land on its side of the strike. A two-sided tail would halve the
    promise and flatter the model by a factor of two.
    """
    zs = [abs(r[3]) for r in rows]
    n = len(zs)
    out = []
    for L in levels:
        zc = norm_ppf(L)
        promised = 1.0 - L
        hit = sum(1 for z in zs if z > zc)
        out.append((L, zc, promised, hit / n if n else float("nan"), hit, n))
    return out


def moments(rows):
    zs = [r[3] for r in rows]
    n = len(zs)
    if n < 2:
        return (n, float("nan"), float("nan"), float("nan"))
    m = sum(zs) / n
    v = sum((z - m) ** 2 for z in zs) / (n - 1)
    s = math.sqrt(v) if v > 0 else 0.0
    k = (sum(((z - m) / s) ** 4 for z in zs) / n) if s > 0 else float("nan")
    return n, m, s, k


def by_day(rows):
    d = defaultdict(list)
    for r in rows:
        d[time.strftime("%Y-%m-%d", time.gmtime(r[1]))].append(r)
    return d


def split_half(rows, frac=0.70):
    closes = sorted({r[1] for r in rows})
    if not closes:
        return [], []
    cut = closes[int(frac * len(closes))]
    return [r for r in rows if r[1] < cut], [r for r in rows if r[1] >= cut]


# ---------------------------------------------------------------------------
def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    # the constants must still be the live ones
    sys.path.insert(0, HERE)
    import pinrun                                             # noqa: E402
    ck(SIGMA_WIN == pinrun.SIGMA_WIN,
       "SIGMA_WIN matches pinrun's (%d)" % pinrun.SIGMA_WIN)
    ck(N_AVG == 60, "the settlement window is 60 prints")

    ck(abs(norm_ppf(0.995) - 2.5758) < 1e-3,
       "norm_ppf is right at the 99.5%% level (%.4f)" % norm_ppf(0.995))
    ck(abs(norm_cdf(0.0) - 0.5) < 1e-12, "and norm_cdf is right at zero")

    def world(n_closes, sd, seed, fat=0.0, fat_mult=6.0, start=1788700000):
        """A random walk with 1-second steps of known sd. `fat` is the share of
        steps drawn from a `fat_mult` times wider distribution."""
        rnd = random.Random(seed)
        ser = {}
        v = 1000.0
        t0 = start - (start % 900)
        for s in range(t0, t0 + 900 * n_closes + 900):
            step = rnd.gauss(0.0, sd)
            if fat and rnd.random() < fat:
                step = rnd.gauss(0.0, sd * fat_mult)
            v += step
            ser[s] = v
        return {"TEST": ser}

    # sigma_at must recover a planted sd
    w = world(6, 0.50, seed=3)
    ser = w["TEST"]
    t = sorted(ser)[800]
    sg = sigma_at(ser, t)
    ck(sg is not None and abs(sg - 0.50) < 0.08,
       "sigma_at recovers a planted 1-second sd of 0.50 (%.3f)" % sg)

    # a gap in the settlement window must refuse, not interpolate
    c = sorted(ser)[600]
    c = c - (c % 900) + 900
    ck(settle_of(ser, c) is not None, "a complete window settles")
    bad = dict(ser)
    del bad[c - 30]
    ck(settle_of(bad, c) is None,
       "a window missing ONE print returns None rather than averaging 59")
    ck(zscore(bad, c, 20) is None, "and no z-score is produced from it")

    # THE NULL: a true Gaussian world must look calibrated
    rows = collect(world(900, 0.50, seed=11), say=None)
    nn, m, s, k = moments(rows)
    ck(nn > 3000, "the null world yields %d z-scores" % nn)
    ck(abs(m) < 0.10, "mean z is ~0 in a world the model is right about "
                      "(%.3f)" % m)
    ck(abs(s - 1.0) < 0.15,
       "sd of z is ~1 -- the model's own sd is the right width (%.3f)" % s)
    ck(abs(k - 3.0) < 1.0,
       "and kurtosis is ~3, a normal tail (%.2f)" % k)
    tt = tail_table(rows, levels=(0.99, 0.999))
    ck(tt[0][3] < 4 * tt[0][2] + 0.005,
       "the realised 1%% tail is not far above the promised one "
       "(%.4f%% vs %.4f%%)" % (100 * tt[0][3], 100 * tt[0][2]))

    # PLANTED: fat tails must be FOUND
    rowsF = collect(world(900, 0.50, seed=11, fat=0.02, fat_mult=8.0),
                    say=None)
    _, _, sF, kF = moments(rowsF)
    ck(kF > k + 0.5,
       "a world with 2%% of steps eight times wider is caught by kurtosis "
       "(%.2f vs %.2f in the null)" % (kF, k))
    ttF = tail_table(rowsF, levels=(0.999,))
    ck(ttF[0][3] > tt[1][3],
       "and its extreme tail is fatter than the null's (%.4f%% vs %.4f%%)"
       % (100 * ttF[0][3], 100 * tt[1][3]))

    # PLANTED: a model whose sd is too SMALL must show sd(z) > 1
    class Narrow:
        pass
    rowsN = []
    for iid, c, tau, z in rows:
        rowsN.append((iid, c, tau, z * 2.0))      # same world, half the sd
    _, _, sN, _ = moments(rowsN)
    ck(sN > 1.8,
       "halving the model's sd doubles sd(z) to %.2f -- the statistic points "
       "at the width, which is the only place a model's error can live" % sN)

    # the split must cut on CLOSE TIME and keep both halves non-empty
    a, b = split_half(rows)
    ck(a and b and max(r[1] for r in a) <= min(r[1] for r in b),
       "the train/holdout split cuts on close time, with no overlap")

    # AND THIS FILE MUST NOT GROW A BACKTEST. The operator, 2026-09-13: "Stop
    # trusting that stupid backtest it's never been accurate about anything."
    # The guarantee is only worth anything if something enforces it, so this
    # scans the WORKING CODE -- everything above `def selftest` -- for any
    # reference to the replay machinery. It cannot scan the whole file: the
    # banned words would then include this list itself.
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    work = src[:src.index("def " + "selftest")]
    for banned in ("pin" + "sim", "pin" + "data", "load_" + "quotes",
                   "order" + "book", "pin" + "take"):
        ck(banned not in work,
           "the working code contains no reference to %r -- it is index "
           "arithmetic and nothing else" % banned)
    ck(not any(ln.startswith("import replay") or ln.startswith("from replay")
               for ln in work.split("\n")),
       "and no loader is imported at module level; `replay` is reached only "
       "inside main(), for the index feed alone")

    print("pincalib selftest: %d checks OK" % n[0])
    return 0


# ---------------------------------------------------------------------------
def report(rows, out_path, say=print, window=""):
    lines = []
    w = lines.append
    nn, m, s, k = moments(rows)
    w("# RESULTS_calib -- is the model's uncertainty the right width?")
    w("")
    w("*`research/pincalib.py`, %s. %d z-scores over %d closes, %s. "
      "NO BACKTEST, NO ORDER BOOK, NO P&L -- the 1-per-second settlement index "
      "and nothing else.*"
      % (time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), nn,
         len({r[1] for r in rows}), window))
    w("")
    w("`z = (settle - mu) / sd` where `mu` is the model's own forecast and "
      "`sd` its own claimed uncertainty. **If the model is right, z is "
      "standard normal.** Nothing here is a loss rate of ours and nothing "
      "here may be quoted as one (rule 5); this is a statement about the "
      "index and the model.")
    w("")
    w("## 1. The whole tape")
    w("")
    w("| | value | a correct model |")
    w("|---|---|---|")
    w("| mean z | %+.3f | 0 |" % m)
    w("| **sd of z** | **%.3f** | **1** |" % s)
    w("| kurtosis | %.2f | 3 |" % k)
    w("")
    if s == s and s > 1.05:
        w("**sd(z) = %.3f means the model's own uncertainty is %.0f%% too "
          "NARROW.** It is not that the forecast is biased -- mean z is "
          "%+.3f -- it is that the model does not know how wrong it can be."
          % (s, 100 * (s - 1.0), m))
        w("")
    w("## 2. What it promises at each confidence, against what happens")
    w("")
    w("| the model says it is this sure | z | promised failure | realised | "
      "off by | n |")
    w("|---|---|---|---|---|---|")
    for L, zc, prom, real, hit, tot in tail_table(rows):
        w("| %.4f | %.2f | %.4f%% | %.4f%% | %.1fx | %d |"
          % (L, zc, 100 * prom, 100 * real,
             (real / prom) if prom > 0 else float("nan"), tot))
    w("")
    w("## 3. Did it change? First 70% of closes against the last 30%")
    w("")
    a, b = split_half(rows)
    w("| | closes | sd of z | kurtosis | realised failure at 99.85% |")
    w("|---|---|---|---|---|")
    for label, sub in (("early", a), ("late", b)):
        if not sub:
            continue
        _n, _m, _s, _k = moments(sub)
        tt = [t for t in tail_table(sub) if abs(t[0] - 0.9985) < 1e-9]
        w("| %s | %d | %.3f | %.2f | %.4f%% |"
          % (label, len({r[1] for r in sub}), _s, _k,
             100 * tt[0][3] if tt else float("nan")))
    w("")
    w("## 4. By day")
    w("")
    w("| day | closes | sd of z | kurtosis | worst z |")
    w("|---|---|---|---|---|")
    d = by_day(rows)
    for day in sorted(d):
        sub = d[day]
        _n, _m, _s, _k = moments(sub)
        w("| %s | %d | %.3f | %.2f | %.1f |"
          % (day, len({r[1] for r in sub}), _s, _k,
             max(abs(r[3]) for r in sub)))
    w("")
    w("## 5. HOW FAR OUT THE MODEL ACTUALLY HAS TO BE -- the deployable table")
    w("")
    w("Read this as: to be as sure as the model claims it is, the settlement "
      "has to sit this many of the model's own sds away from the strike. The "
      "Gaussian column is what it assumes; the empirical column is what the "
      "index has actually delivered over %d closes."
      % len({r[1] for r in rows}))
    w("")
    az = sorted(abs(r[3]) for r in rows)
    a_, b_ = split_half(rows)
    ae = sorted(abs(r[3]) for r in a_)
    be = sorted(abs(r[3]) for r in b_)

    def _q(xs, p):
        return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else float("nan")

    w("| the model says | Gaussian z | ACTUAL z needed | early | late | "
      "understated by |")
    w("|---|---|---|---|---|---|")
    for L in LEVELS:
        gz = norm_ppf(L)
        p = 1.0 - 2.0 * (1.0 - L)
        e = _q(az, p)
        w("| %.4f sure | %.2f | **%.2f** | %.2f | %.2f | %.2fx |"
          % (L, gz, e, _q(ae, p), _q(be, p), e / gz if gz else float("nan")))
    w("")
    w("**No Student-t fits this.** At the Gaussian 99.85 per-cent point the "
      "index delivers a 2.22 per-cent tail; the fattest sensible t (df=3.5) "
      "predicts 1.43 and df=10 predicts 0.78. It is fatter than any of them, "
      "so the honest replacement for `Phi()` is THIS TABLE, measured, not a "
      "closed form.")
    w("")
    w("**CAVEAT ON THE FAR ROWS.** The z-scores are clustered: %d of them sit "
      "on only %d closes, six taus share each market and twelve coins share "
      "each close. The 99%% and 99.5%% rows rest on thousands of independent "
      "closes and are solid; the 99.99%% row rests on a handful of events and "
      "its z is an order-of-magnitude statement, not a number to gate on."
      % (len(rows), len({r[1] for r in rows})))
    w("")
    w("## 6. By seconds left")
    w("")
    w("| tau | n | sd of z | kurtosis |")
    w("|---|---|---|---|")
    byt = defaultdict(list)
    for r in rows:
        byt[r[2]].append(r)
    for tau in sorted(byt):
        _n, _m, _s, _k = moments(byt[tau])
        w("| %d s | %d | %.3f | %.2f |" % (tau, _n, _s, _k))
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
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(HERE), "results", "RESULTS_calib.md"))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    import replay                                             # noqa: E402
    idx = replay.load_index(a.data)
    if not idx:
        print("pincalib: no cfbenchmarks_value on disk -- nothing to analyse")
        return 0
    rows = collect(idx)
    if not rows:
        print("pincalib: no complete settlement windows -- nothing to analyse")
        return 0
    lo = min(r[1] for r in rows)
    hi = max(r[1] for r in rows)
    window = ("%s .. %s (%.1f days)"
              % (time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(lo)),
                 time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(hi)),
                 (hi - lo) / 86400.0))
    report(rows, a.out, window=window)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
