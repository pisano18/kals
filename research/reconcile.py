#!/usr/bin/env python3
"""reconcile.py -- three estimators disagree about volatility. Find the liar.

THE DISPUTE, with each party's real-data testimony:

  sigma_settle (from settlements, gap-free):   implied/realised = 0.844
                                               -> market UNDERPRICES vol
  implied.py  (pooled 6-94c inversions):       ratios 0.85-1.27, median 0.93
                                               -> roughly fair, slight under
  voltiming   (median ATM inversion/window):   levels all NEGATIVE
                                               -> market OVERPRICES vol

They cannot all be right, and every volatility conclusion in this project --
including a potential ~2c/contract trade -- hangs on which one is.

THE SUSPECT. The inversion is sigma = (mu - K) / (z(p) * sqrt(vf)).  Near 50c,
z(p) -> 0, so the estimate divides by nearly nothing: a half-cent of tick
rounding moves implied sigma by tens of percent.  And the error is CONVEX
(sigma ~ 1/z), so symmetric price noise biases recovered sigma UP -- Jensen,
not bad luck.  voltiming inverts quotes at tau 300-900s, where the price sits
nearest 50c; implied.py pools everything from 6c to 94c.  implied.py's own
smile table shows the 45-55c bucket at 1.166x against 0.94-0.98 neighbours,
which is exactly what upward-biased ATM inversions look like.

THE METHOD. Build a synthetic world where sigma is KNOWN and the book quotes
the model's own fair value, honestly, rounded to the real 1c tick. Run the
PROJECT'S OWN CODE -- implied.implied_sigma, engine.var_factor -- over it,
banded by |z|.  Any recovered/true ratio different from 1.000 is the
pipeline's own bias, measured, with no market and no feed to blame.

NOTHING HERE PLACES AN ORDER.
"""

import argparse
import math
import os
import random
import sys
from statistics import NormalDist, mean, median, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import var_factor, N_AVG                          # noqa: E402
from implied import implied_sigma                             # noqa: E402

ND = NormalDist()
WINDOW = 900


# ===========================================================================
def make_world(n_win, sigma, seed, tails="gauss", cluster=0.0):
    """Per-second index path plus settlements. Truth is `sigma`, exactly.

    tails="fat" draws innovations from a scaled t(4); cluster>0 mixes a
    high-vol regime.  Both keep the UNCONDITIONAL per-second sd equal to
    `sigma`, so the planted answer never moves.
    """
    rng = random.Random(seed)
    n_sec = n_win * WINDOW + 120
    ticks, x = {}, 80000.0
    hi = False
    for t in range(n_sec):
        s = sigma
        if cluster > 0:
            if rng.random() < 0.002:
                hi = not hi
            # 0.5*1.3^2 + 0.5*0.557^2 = 1.000. The first version used
            # (1.6, 0.74), whose mean square is 1.55 -- so the 'cluster' world
            # was 24% wilder than its label and every estimator said so.
            s = sigma * (1.3 if hi else 0.5568)
        if tails == "fat":
            # t(4) = Z / sqrt(chi2_4 / 4); chi2_4/4 IS gamma(2, 0.5) (mean 1).
            # The first version divided by another 2 inside the sqrt, which
            # made the world sqrt(2) wilder than the planted sigma -- and all
            # three estimators dutifully reported ~1.41. The estimators were
            # right; the fixture was lying. Var(t_4) = 2, so /sqrt(2) at the
            # end restores unit variance.
            z = rng.gauss(0, 1) / math.sqrt(max(rng.gammavariate(2.0, 0.5), 1e-9))
            step = s * z / math.sqrt(2.0)
        else:
            step = rng.gauss(0, s)
        x += step
        ticks[t] = x
    settles, closes = [], []
    for w in range(1, n_win):
        c = w * WINDOW
        settles.append(mean(ticks[c - i] for i in range(N_AVG)))
        closes.append(c)
    return ticks, closes, settles


def observe(ticks, coverage, seed, burst=False):
    """The feed's view: drop seconds. burst=True drops in runs, like real
    transport gaps, rather than independently."""
    rng = random.Random(seed)
    out = {}
    dropping = False
    for t in sorted(ticks):
        if burst:
            if dropping:
                if rng.random() < 0.25:
                    dropping = False
            else:
                if rng.random() < 0.25 * (1 - coverage) / max(coverage, 1e-9):
                    dropping = True
            if not dropping:
                out[t] = ticks[t]
        else:
            if rng.random() < coverage:
                out[t] = ticks[t]
    return out


# ===========================================================================
# the three realised-sigma estimators, as the project defines them
# ===========================================================================
def sig_pairs(ticks):
    secs = sorted(ticks)
    d = [ticks[b] - ticks[a] for a, b in zip(secs, secs[1:]) if b - a == 1]
    return pstdev(d) if len(d) > 200 else None


def sig_gapspan(ticks):
    secs = sorted(ticks)
    d = [ticks[b] - ticks[a] for a, b in zip(secs, secs[1:])]
    return pstdev(d) if len(d) > 200 else None


def sig_settle(settles):
    d = [b - a for a, b in zip(settles, settles[1:])]
    if len(d) < 60:
        return None
    m = mean(d)
    return math.sqrt(sum((x - m) ** 2 for x in d) / len(d) / (2 * WINDOW - 20))


# NOTE the constant: consecutive windows -> Var = (900-20)sigma^2 = 880sigma^2.
# sig_settle above is written for the general k=1 case via (2W-20)... which is
# WRONG: 2*900-20 = 1780 != 880. Deliberately left for one selftest cycle?
# No -- fixed immediately below; the selftest asserts the CORRECT constant and
# would catch any regression here.
def sig_settle_correct(settles):
    d = [b - a for a, b in zip(settles, settles[1:])]
    if len(d) < 60:
        return None
    m = mean(d)
    return math.sqrt(sum((x - m) ** 2 for x in d) / len(d) / 880.0)


# ===========================================================================
# the inversion pipeline, banded by |z|
# ===========================================================================
def quote_and_invert(ticks, closes, settles, sigma, tick_c=0.01,
                     taus=range(60, 900, 15), zbands=None):
    """An HONEST book: fair value from the true model and true sigma, rounded
    to the tick. Invert every quote with the project's implied_sigma and
    report recovered sigma by |z| band."""
    if zbands is None:
        zbands = [(0.0, 0.1), (0.1, 0.25), (0.25, 0.5), (0.5, 1.0),
                  (1.0, 1.5), (1.5, 2.0)]
    prev = dict(zip(closes, settles))
    out = {b: [] for b in zbands}
    strikes = {}
    for i in range(1, len(closes)):
        strikes[closes[i]] = settles[i - 1]      # strike(N+1) == settle(N)
    for c, K in strikes.items():
        for tau in taus:
            t = c - tau
            if t not in ticks:
                continue
            spot = ticks[t]
            vf = var_factor(int(tau), [1.0])
            if vf <= 0:
                continue
            sd = sigma * math.sqrt(vf)
            z_true = (spot - K) / sd
            p_fair = ND.cdf(z_true)
            p_mkt = round(p_fair / tick_c) * tick_c     # the tick is real
            iv = implied_sigma(p_mkt, spot, K, int(tau))
            if iv is None:
                continue
            az = abs(z_true)
            for lo, hi in zbands:
                if lo <= az < hi:
                    out[(lo, hi)].append(iv / sigma)
                    break
    return out


# ===========================================================================
def selftest():
    print("=" * 78)
    print("SELF-TEST / REFEREE -- every pipeline against a KNOWN sigma")
    print("=" * 78)
    fails = []
    SIG = 6.0
    N = 500

    # ---- 0. the settle constant itself -----------------------------------
    t_, c_, s_ = make_world(2000, SIG, seed=1)
    wrong = sig_settle(s_)
    right = sig_settle_correct(s_)
    print(f"\n0. THE CONSTANT. Var(settle diff) = 880 sigma^2, not 1780.")
    print(f"   with 1780: {wrong:.3f}   with 880: {right:.3f}   truth: {SIG}")
    if abs(right - SIG) / SIG > 0.05:
        fails.append(f"sig_settle_correct read {right:.3f} against {SIG}")
    if abs(wrong - SIG) / SIG < 0.05:
        fails.append("the deliberately wrong constant also recovered sigma -- "
                     "this check distinguishes nothing")

    # ---- 1. realised estimators under gaps -------------------------------
    print(f"\n1. REALISED SIGMA under feed gaps (truth {SIG}), 500 windows")
    print(f"   {'world':>28}{'pairs-1s':>10}{'gapspan':>10}{'settle':>9}")
    for name, cov, burst, tails, cl in (
            ("full coverage", 1.0, False, "gauss", 0.0),
            ("74% random gaps", 0.74, False, "gauss", 0.0),
            ("74% BURST gaps", 0.74, True, "gauss", 0.0),
            ("74% bursts + fat tails", 0.74, True, "fat", 0.0),
            ("74% bursts + vol cluster", 0.74, True, "gauss", 0.7)):
        ticks, closes, settles = make_world(N, SIG, seed=11, tails=tails,
                                            cluster=cl)
        obs = observe(ticks, cov, seed=7, burst=burst)
        p, g, st = sig_pairs(obs), sig_gapspan(obs), sig_settle_correct(settles)
        print(f"   {name:>28}{p/SIG:>10.3f}{g/SIG:>10.3f}{st/SIG:>9.3f}")
        if name == "full coverage" and abs(p / SIG - 1) > 0.03:
            fails.append(f"pairs estimator off at full coverage: {p/SIG:.3f}")
        if abs(st / SIG - 1) > 0.06:
            fails.append(f"settle sigma off in world '{name}': {st/SIG:.3f}")
        if "random gaps" in name and abs(g / SIG - 1) < 0.10:
            fails.append("gap-spanning was NOT inflated under random gaps -- "
                         "the fixture no longer demonstrates the known bias")

    # ---- 2. THE INVERSION, by |z| ----------------------------------------
    print(f"\n2. THE INVERSION against an HONEST tick-rounded book.")
    print("   The book quotes the true model with the true sigma, rounded to")
    print("   1c. Anything but 1.000 below is the PIPELINE's own bias.")
    ticks, closes, settles = make_world(800, SIG, seed=23)
    bands = quote_and_invert(ticks, closes, settles, SIG)
    print(f"\n   {'|z| band':>14}{'n':>8}{'mean iv/true':>14}{'median':>9}")
    atm_mean = atm_med = wing_med = None
    for (lo, hi), vals in bands.items():
        if not vals:
            continue
        mn, md = mean(vals), median(vals)
        print(f"   {f'{lo:.2f}-{hi:.2f}':>14}{len(vals):>8,}{mn:>14.3f}{md:>9.3f}")
        if hi <= 0.11:
            atm_mean, atm_med = mn, md
        if lo >= 0.5 and wing_med is None:
            wing_med = md
    if atm_mean is None or wing_med is None:
        fails.append("inversion bands missing data")
    else:
        # The theory this file was WRITTEN to demonstrate -- convexity bias
        # in near-ATM inversions -- turned out to be FALSE: the pipeline
        # recovers sigma to 0.3% even at |z| < 0.1, because exact-ATM rounds
        # are rejected by the inversion and the median tames the rest. The
        # assertion now pins the exoneration instead, so if the inversion
        # ever DOES develop an ATM bias, this fires.
        if abs(atm_mean - 1.0) > 0.05:
            fails.append(f"near-ATM inversion mean drifted to {atm_mean:.3f} "
                         "-- the inversion's clean bill of health is gone")
        if abs(wing_med - 1.0) > 0.04:
            fails.append(f"|z|>0.5 median inversion reads {wing_med:.3f}; the "
                         "well-conditioned band should recover the truth")

    # ---- 3. the voltiming aggregation: Jensen, not mispricing ------------
    print(f"\n3. VOLTIMING'S LEVEL. It averages LOG(realised/implied) across")
    print("   windows. When window-to-window volatility disperses -- which is")
    print("   what vol clustering MEANS -- E[log rv] < log E[rv] by half the")
    print("   variance of log rv. A market pricing expected vol EXACTLY")
    print("   right therefore shows a NEGATIVE mean log level. Constant-vol")
    print("   world first (must be ~0), then a clustered world priced by an")
    print("   oracle who knows each window's expected vol (must go negative")
    print("   with NO mispricing anywhere).")

    def volt_level(ticks_all, obs, closes, settles, sig_of_window):
        strikes = {closes[i]: settles[i - 1] for i in range(1, len(closes))}
        lvls = []
        for c, K in strikes.items():
            sw = sig_of_window(c)
            ivs = []
            for tau in range(300, 900, 15):
                t = c - tau
                if t not in ticks_all:
                    continue
                vf = var_factor(int(tau), [1.0])
                sd = sw * math.sqrt(vf)
                p_mkt = round(ND.cdf((ticks_all[t] - K) / sd) / 0.01) * 0.01
                iv = implied_sigma(p_mkt, ticks_all[t], K, int(tau))
                if iv is not None:
                    ivs.append(iv)
            if len(ivs) < 10:
                continue
            seg = [obs[t + 1] - obs[t] for t in range(c - 900, c)
                   if t in obs and (t + 1) in obs]
            if len(seg) < 120:
                continue
            lvls.append(math.log(pstdev(seg) / median(ivs)))
        return mean(lvls), len(lvls)

    ticks, closes, settles = make_world(800, SIG, seed=23)
    obs = observe(ticks, 0.74, seed=3, burst=True)
    lv_const, n1 = volt_level(ticks, obs, closes, settles, lambda c: SIG)
    print(f"\n   constant vol, fair book:   level {lv_const:+.3f}  ({n1} windows)")

    # a clustered world where each window's TRUE expected sigma is known and
    # the book prices with exactly that -- zero mispricing by construction
    rng = random.Random(41)
    n_win = 800
    win_sig = []
    cur = SIG
    for _ in range(n_win + 1):
        cur = SIG * math.exp(0.75 * math.log(max(cur / SIG, 1e-6)) +
                             rng.gauss(0, 0.35))
        win_sig.append(cur)
    ticks2, x = {}, 80000.0
    for t in range(n_win * WINDOW + 120):
        x += rng.gauss(0, win_sig[t // WINDOW])
        ticks2[t] = x
    closes2 = [w * WINDOW for w in range(1, n_win)]
    settles2 = [mean(ticks2[c - i] for i in range(N_AVG)) for c in closes2]
    obs2 = observe(ticks2, 0.74, seed=5, burst=True)
    lv_clus, n2 = volt_level(ticks2, obs2, closes2, settles2,
                             lambda c: win_sig[c // WINDOW])
    disp = pstdev([math.log(v) for v in win_sig])
    print(f"   clustered vol, ORACLE book (tracks each window): "
          f"level {lv_clus:+.3f}  ({n2} windows)")

    # The decisive third panel. A book that quotes ONE static sigma, chosen
    # so it is exactly variance-fair on average: sqrt(E[sigma_w^2]). Zero
    # aggregate mispricing -- yet the log-level must come out around
    # -Var(log sigma_w)/2, because implied no longer moves with the windows.
    # The first version of this section only had the oracle panel, measured
    # -0.006, and nearly concluded Jensen was a dead end: when the book
    # TRACKS window vol the dispersion cancels. Jensen bites exactly to the
    # extent the market does NOT track -- and voltiming's own real-data
    # slopes (~0) say the market does not track the forecastable part.
    static_sig = math.sqrt(mean(v * v for v in win_sig))
    lv_stat, n3 = volt_level(ticks2, obs2, closes2, settles2,
                             lambda c: static_sig)
    print(f"   clustered vol, STATIC variance-fair book: level {lv_stat:+.3f}"
          f"  ({n3} windows)")
    # The full gap for a VARIANCE-fair static book is -Var(log sigma), not
    # -Var/2: half from E[log] vs log E[], and another half because the
    # variance-fair quote sqrt(E[sigma^2]) is the QUADRATIC mean, itself
    # Var/2 above the arithmetic mean in log terms. The first version
    # predicted -Var/2, measured -0.310 against -0.143, and the referee
    # caught the missing half.
    print(f"   log-vol dispersion {disp:.2f} -> predicted gap -Var(log) = "
          f"{-disp * disp:+.3f}")
    print("\n   Real-data voltiming levels were -0.02 (BNB) to -0.39 (HYPE),")
    print("   most negative exactly where vol dispersion is wildest. A")
    print("   negative LOG level is what a variance-fair but non-tracking")
    print("   market looks like. It is NOT evidence of overpricing, and the")
    print("   level column must never again be read as a premium.")
    if abs(lv_const) > 0.03:
        fails.append(f"constant-vol level is {lv_const:+.3f}, not ~0")
    if abs(lv_clus) > 0.05:
        fails.append(f"oracle-book level is {lv_clus:+.3f}; a tracking book "
                     "should show ~0")
    want = -disp * disp
    if not (want - 0.08 <= lv_stat <= want + 0.08):
        fails.append(f"static-fair book level {lv_stat:+.3f} does not match "
                     f"the Jensen prediction {want:+.3f} -- the explanation "
                     "still does not reproduce")
    if lv_stat > -0.05:
        fails.append(f"static-fair book level {lv_stat:+.3f} is not clearly "
                     "negative -- Jensen not demonstrated")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- the referee reproduces every claimed bias on")
    print("a world where the truth is planted, using the project's own code.")
    return True


# ===========================================================================
def real_data(data_dir, out_dir):
    """THE canonical vol measurement, under the referee's rules.

    realised: sigma_settle from markets.json settle diffs -- gap-free,
              measured at exactly the horizon the contract settles on,
              over exactly the recorded closes.
    implied:  the project's own inversion, restricted to 0.5 <= |z| <= 2.0
              (the referee shows the pipeline is clean everywhere, but this
              band has the most information per quote), aggregated as
              ROOT-MEAN-SQUARE so the comparison is in variance terms and
              Jensen has nothing to grab.
    """
    from replay import load_quotes, load_markets, load_index, SERIES_TO_INDEX
    from implied import collect
    from collections import defaultdict

    quotes = load_quotes(data_dir)
    markets = load_markets(out_dir)
    if not markets:
        print(f"\n  *** NO SETTLED MARKETS at {os.path.abspath(out_dir)} -- "
              "run fulltape or fix --out.")
        return
    index = load_index(data_dir)
    rows = collect(index, quotes, markets, SERIES_TO_INDEX, ttc_max=900)
    print(f"\n  {len(rows):,} invertible quote-seconds")
    band = [r for r in rows if 0.5 <= abs(r.get("z", 0.0)) <= 2.0]
    print(f"  {len(band):,} in the 0.5 <= |z| <= 2.0 band")

    # implied, RMS per (series, close) then per series
    per = defaultdict(lambda: defaultdict(list))
    for r in band:
        per[r["series"]][r["close"]].append(r["iv"])
    # sigma_settle per series over the closes the tape actually spans
    span_lo = min((min(c for c, _ in v.items()) for v in per.values()
                   if v), default=None)
    if span_lo is None:
        print("  nothing in band; cannot measure.")
        return
    print(f"\n  {'series':>11}{'closes':>8}{'settle wins':>12}{'sig_settle':>12}"
          f"{'implied RMS':>12}{'ratio':>8}{'95% CI':>18}")
    import random as _rnd
    verdicts = []
    sig_by_series = {}
    for ser in sorted(per):
        # settlement sigma over this series' recorded closes
        setts = {}
        for tk, m in markets.items():
            if (m.get("series") or tk.split("-")[0]) != ser:
                continue
            try:
                c = int(round(float(m["close"])))
                setts[c] = float(m["settle"])
            except (KeyError, TypeError, ValueError):
                continue
        # THE SAME WINDOW ON BOTH SIDES. The numerator (implied RMS) can only
        # be measured where we have quotes; the denominator can be measured
        # wherever Kalshi has settled a market. Once the settlement fetch was
        # widened from 3,600 markets to 10,798 the two stopped covering the
        # same period -- 1,198 settlements spanning ~300 hours against 580
        # close-time clusters from the ~164 hours actually recorded -- and
        # every ratio fell hard: BNB 0.715 -> 0.524, XRP 0.810 -> 0.481,
        # DOGE 0.747 -> 0.502. A ratio of 0.48 says the market underprices
        # volatility by more than two to one, which on a liquid exchange over
        # 580 closes is not a finding, it is a mismatch.
        #
        # Volatility clusters -- this project's one confirmed result -- so a
        # denominator drawn from a different and longer stretch of tape is a
        # different number, not a better one.
        lo_c = min(clus_c := sorted(per[ser])) if per[ser] else None
        hi_c = max(clus_c) if per[ser] else None
        times = sorted(setts)
        if lo_c is not None:
            times = [t for t in times if lo_c - WINDOW <= t <= hi_c + WINDOW]
        d = [setts[b] - setts[a] for a, b in zip(times, times[1:])
             if b - a == WINDOW]
        if len(d) < 60:
            print(f"  {ser:>11}   too few consecutive settles ({len(d)})")
            continue
        m0 = mean(d)
        sig_st = math.sqrt(sum((x - m0) ** 2 for x in d) / len(d) / 880.0)
        span_h = (times[-1] - times[0]) / 3600.0 if len(times) > 1 else 0.0
        all_h = ((max(setts) - min(setts)) / 3600.0) if len(setts) > 1 else 0.0
        if all_h > span_h * 1.05:
            print(f"  {ser:>11}   settle sigma restricted to the quoted span: "
                  f"{span_h:.0f}h of {all_h:.0f}h available, {len(d)} pairs")

        clus = per[ser]
        # Per-close MEDIAN iv first (a bad quote cannot own a cluster), then
        # RMS across closes with the top and bottom 2% of clusters
        # winsorised. ETH's real-data run produced ratio 1.399 with a CI of
        # [0.64, 2.27]: a handful of extreme inversions dominated a plain
        # RMS, because squaring hands the wildest observation the microphone.
        # Winsorising (clip, not drop -- the catalogue's pattern 14) keeps
        # the variance comparison honest without letting one quote decide it.
        ivs_by_close = {c: median(vals) for c, vals in clus.items() if vals}
        n_bad = sum(1 for v in ivs_by_close.values() if v <= 0)
        if n_bad:
            print(f"  {ser:>11}   ({n_bad} nonpositive cluster medians "
                  "dropped -- signed-iv noise)")
        ivs_by_close = {c: v for c, v in ivs_by_close.items() if v > 0}
        if len(ivs_by_close) < 30:
            print(f"  {ser:>11}   too few clusters ({len(ivs_by_close)})")
            continue
        ranked = sorted(ivs_by_close.values())
        lo_w = ranked[max(0, int(0.02 * len(ranked)))]
        hi_w = ranked[min(len(ranked) - 1, int(0.98 * len(ranked)))]
        vals = [min(max(v, lo_w), hi_w) for v in ranked]
        iv_rms = math.sqrt(mean(v * v for v in vals))
        ratio = iv_rms / sig_st
        # cluster bootstrap on the implied side + gaussian SE on the settle
        # side, combined in quadrature on the log
        rng = _rnd.Random(17)
        boots = []
        for _ in range(500):
            pick = [vals[rng.randrange(len(vals))] for _ in vals]
            boots.append(math.sqrt(mean(v * v for v in pick)) / sig_st)
        boots.sort()
        lo_b, hi_b = boots[12], boots[487]
        se_settle = ratio / math.sqrt(2 * len(d))
        lo = lo_b - 1.96 * se_settle
        hi = hi_b + 1.96 * se_settle
        verdicts.append(ratio)
        sig_by_series[ser] = sig_st
        print(f"  {ser:>11}{len(vals):>8}{len(d) + 1:>12}{sig_st:>12.4g}"
              f"{iv_rms:>12.4g}{ratio:>8.3f}   [{lo:>5.3f}, {hi:>5.3f}]")
    # ---- per-tau bands: WHERE in the window does the gap live? ----------
    print(f"\n  {'tau band':>12}", "".join(f"{s_[2:5]:>7}" for s_ in sorted(per)))
    for tlo, thi in ((60, 180), (180, 300), (300, 600), (600, 900)):
        row = f"  {f'{tlo}-{thi}s':>12}"
        for ser in sorted(per):
            sel = defaultdict(list)
            for r in band:
                if r["series"] == ser and tlo <= r["tau"] < thi:
                    sel[r["close"]].append(r["iv"])
            if len(sel) < 30:
                row += f"{'--':>7}"
                continue
            ranked = sorted(x for x in (median(v) for v in sel.values())
                            if x > 0)
            if len(ranked) < 30:
                row += f"{'--':>7}"
                continue
            lo_w = ranked[max(0, int(0.02 * len(ranked)))]
            hi_w = ranked[min(len(ranked) - 1, int(0.98 * len(ranked)))]
            vv = [min(max(x, lo_w), hi_w) for x in ranked]
            st = sig_by_series.get(ser)
            row += (f"{math.sqrt(mean(x * x for x in vv)) / st:>7.2f}"
                    if st else f"{'--':>7}")
        print(row)
    print("  (implied/settle per tau band; the term structure of the gap)")

    if verdicts:
        med = sorted(verdicts)[len(verdicts) // 2]
        print(f"\n  median implied/settle ratio: {med:.3f}")
        print("  CAUTION: the series share one vol regime -- the level is one")
        print("  draw, not nine. Below 1 in most series AND clearly below 1")
        print("  on fresh data is the standard before anything is traded.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")
    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    real_data(a.data, a.out)


if __name__ == "__main__":
    main()
