#!/usr/bin/env python3
# VERSION: 2026-09-13-fl1
"""pinflood.py -- CAN WE SEE FLOOD SEASON COMING?

THE OPERATOR'S THEORY, 2026-09-13, verbatim: "A method I've theorized for
managing 'the rain around flood season' is tracking volume, volatility, or
anything else you can think of or that is available and seeing how that
correlates to lumpiness and large price swings... just one example is
everything seems to follow btc."

THE PROBLEM IT ADDRESSES. `results/RESULTS_calib.md`: the model's error is not
width, it is SHAPE. sd(z) is 1.151 -- only 15% too narrow -- while kurtosis is
132 against a normal's 3. The index makes jumps a Gaussian says are impossible,
and a jump is the only thing that can turn a 96c ticket into zero. Scaling
volatility does not help (measured: k=1.25 keeps 44% of candidates and makes
them worse) because it stretches the body, where the model is nearly right.

So the question is not "how wide is the distribution" but **"is a jump likely
in the next fifteen minutes, and can we tell before the window opens?"** If it
is predictable at all, the answer is to stand aside, not to re-price.

NO LOOKAHEAD, BY CONSTRUCTION. Every predictor is computed at T = close - 60,
which is the instant the settlement window OPENS. The bot decides between 30
and 3 seconds before the close, so anything available at T is available to it
with at least 30 seconds to spare. `--selftest` plants a world where the
outcome is known only after T and requires every predictor to be blind to it.

WHAT IS PREDICTED. |z| for that close, where z is the model's own miss in units
of its own claimed sd (`pincalib.zscore`). A close is a FLOOD if |z| exceeds
the threshold; 3.0 is the headline because the Gaussian calls that a 1-in-740
event and it actually happens about 1 in 50.

THE UNIT IS A CLOSE, NOT A COIN-CLOSE. Twelve series settle on the same second
at rho ~0.8 (hard rule 4). Every rate here is reported per close and per
coin-close, and the intervals are bootstrapped by resampling CLOSES.

INDEX FEED ONLY. No order book, no replay, no fills, no P&L. Step 2 of the
operator's plan -- the 11 GB of constituent exchange books in feed_data -- is
deliberately NOT in this file: it costs an order of magnitude more to read and
is only worth it if the cheap predictors here show nothing.
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

WINDOW = 60              # the settlement window, [close-60, close)
FLOOD_Z = 3.0            # the headline threshold
Z_TAU = 20               # the tau whose z labels the close; 20s is mid-gate
SHORT = 300              # "the last five minutes"
LONG = 3600              # "the last hour"
BTC = "BRTI"             # the BTC index id, resolved at load if named else


def _diffs(series, t0, t1):
    """1-second changes inside [t0, t1], skipping gaps. Gaps are SKIPPED, not
    bridged: bridging a 4-second hole makes one 4-second move look like one
    1-second move, which manufactures exactly the jumps this file hunts."""
    out = []
    prev_s = None
    prev_v = None
    for s in range(t0, t1 + 1):
        v = series.get(s)
        if v is None:
            prev_s, prev_v = None, None
            continue
        if prev_s is not None and s - prev_s == 1:
            out.append(v - prev_v)
        prev_s, prev_v = s, v
    return out


def _sd(xs):
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / (n - 1)
    return math.sqrt(v) if v > 0 else 0.0


def _kurt(xs):
    n = len(xs)
    if n < 4:
        return None
    m = sum(xs) / n
    s = _sd(xs)
    if not s:
        return None
    return sum(((x - m) / s) ** 4 for x in xs) / n


def features(series, close_s, btc_series=None):
    """Everything knowable at T = close - 60. None if the history is too thin.

    Returned as a plain dict so the scorer never has to know the order, which
    is how a feature once got compared against the wrong column in this repo's
    ancestor scripts.
    """
    T = close_s - WINDOW
    spot = series.get(T)
    if spot is None or spot <= 0:
        return None
    d_short = _diffs(series, T - SHORT, T)
    d_long = _diffs(series, T - LONG, T)
    if len(d_short) < 60 or len(d_long) < 600:
        return None
    rv_s = _sd(d_short)
    rv_l = _sd(d_long)
    if not rv_s or not rv_l:
        return None
    big = sum(1 for x in d_long if abs(x) > 4.0 * rv_l)
    mx = max(abs(x) for x in d_long) / rv_l
    f = {
        # how choppy, in units of the price itself, so coins are comparable
        "rv_short": rv_s / spot,
        "rv_long": rv_l / spot,
        # is it heating up? the ratio is the operator's "rain before the flood"
        "rv_ratio": rv_s / rv_l,
        # LUMPINESS ITSELF: the fourth moment of the last hour's moves
        "kurt_long": _kurt(d_long) or 0.0,
        # how many one-second moves already broke four sigma this hour
        "jumps_long": float(big),
        # and how big the biggest one was
        "max_move": mx,
        "hour": float(time.gmtime(close_s).tm_hour),
    }
    if btc_series is not None:
        bd = _diffs(btc_series, T - LONG, T)
        bsd = _sd(bd)
        bspot = btc_series.get(T)
        if bd and bsd and bspot:
            f["btc_kurt"] = _kurt(bd) or 0.0
            f["btc_jumps"] = float(sum(1 for x in bd if abs(x) > 4.0 * bsd))
            f["btc_rv"] = bsd / bspot
            f["btc_max_move"] = max(abs(x) for x in bd) / bsd
    return f


def build(index, z_tau=Z_TAU, say=print):
    """[(close, iid, features, |z|)] -- one row per coin per close.

    The label and the features are computed from the SAME series but at
    disjoint times: features end at close-60, the label starts there.
    """
    btc = None
    for k in index:
        if BTC in k.upper():
            btc = index[k]
            break
    rows = []
    n_nofeat = n_noz = 0
    for iid, series in index.items():
        if not series:
            continue
        lo, hi = min(series), max(series)
        c = lo - (lo % 900) + 900
        while c <= hi:
            r = pincalib.zscore(series, c, z_tau)
            if r is None:
                n_noz += 1
                c += 900
                continue
            f = features(series, c, btc_series=btc)
            if f is None:
                n_nofeat += 1
                c += 900
                continue
            rows.append((c, iid, f, abs(r[0])))
            c += 900
    # the two PREVIOUS-close features, added once the rows exist
    by_coin = defaultdict(list)
    for r in rows:
        by_coin[r[1]].append(r)
    for iid in by_coin:
        by_coin[iid].sort()
    worst_prev = {}
    by_close = defaultdict(list)
    for r in rows:
        by_close[r[0]].append(r[3])
    closes_sorted = sorted(by_close)
    for i, c in enumerate(closes_sorted):
        worst_prev[c] = (max(by_close[closes_sorted[i - 1]])
                         if i > 0 else None)
    for iid, lst in by_coin.items():
        prev = None
        prev_c = None
        for (c, _i, f, z) in lst:
            f["prev_z"] = prev if (prev is not None
                                   and prev_c is not None
                                   and c - prev_c == 900) else 0.0
            wp = worst_prev.get(c)
            f["prev_worst_any"] = wp if wp is not None else 0.0
            prev, prev_c = z, c
    if say:
        say("  rows: %d coin-closes over %d closes (%d had no z, %d had too "
            "little history)" % (len(rows), len({r[0] for r in rows}),
                                 n_noz, n_nofeat))
    return rows


# ---------------------------------------------------------------------------
def quintiles(rows, key, flood_z=FLOOD_Z, k=5):
    """(quintile index, n, floods, rate, median feature) ranked WITHIN coin.

    Ranking within coin is not a nicety. Raw volatility scales with the coin's
    price -- bucketing on it sorts by coin, which is the exact trap that made
    'low volatility is dangerous' look true earlier today when it was really
    'cheap coins are dangerous'.
    """
    by_coin = defaultdict(list)
    for r in rows:
        if key in r[2]:
            by_coin[r[1]].append(r)
    buckets = defaultdict(list)
    for iid, lst in by_coin.items():
        lst = sorted(lst, key=lambda r: r[2][key])
        n = len(lst)
        if n < k:
            continue
        for i, r in enumerate(lst):
            buckets[min(k - 1, int(k * i / n))].append(r)
    out = []
    for q in sorted(buckets):
        sub = buckets[q]
        fl = sum(1 for r in sub if r[3] > flood_z)
        vals = sorted(r[2][key] for r in sub)
        out.append((q, len(sub), fl, fl / len(sub) if sub else float("nan"),
                    vals[len(vals) // 2]))
    return out


def lift(rows, key, flood_z=FLOOD_Z, k=5):
    """Top quintile flood rate divided by bottom quintile. 1.0 is no signal.

    HALDANE-CORRECTED (+0.5 to each count, +1 to each denominator). A raw ratio
    is undefined whenever the bottom quintile happens to hold zero floods --
    which is not a failure of the predictor, it is the STRONGEST possible
    result for it, and returning nan there would silently discard exactly the
    signals worth finding. The correction costs a little conservatism at large
    counts and makes the statistic defined everywhere; the bootstrap interval
    uses the same statistic, so the interval and the point estimate agree.
    """
    q = quintiles(rows, key, flood_z, k)
    if len(q) < k:
        return float("nan"), q
    top = (q[-1][2] + 0.5) / (q[-1][1] + 1.0)
    bot = (q[0][2] + 0.5) / (q[0][1] + 1.0)
    if bot <= 0:
        return float("nan"), q
    return top / bot, q


def boot_lift(rows, key, flood_z=FLOOD_Z, k=5, b=2000, seed=20260913):
    """By-CLOSE bootstrap interval on the lift. Resamples closes, not rows,
    because twelve coins share a close at rho ~0.8."""
    by_close = defaultdict(list)
    for r in rows:
        by_close[r[0]].append(r)
    cells = list(by_close.values())
    if not cells:
        return float("nan"), float("nan")
    rnd = random.Random(seed)
    outs = []
    for _ in range(b):
        draw = []
        for _j in range(len(cells)):
            draw.extend(cells[rnd.randrange(len(cells))])
        L, _q = lift(draw, key, flood_z, k)
        if L == L:
            outs.append(L)
    if not outs:
        return float("nan"), float("nan")
    outs.sort()
    return (outs[int(0.025 * len(outs))],
            outs[min(len(outs) - 1, int(0.975 * len(outs)))])


def mde_lift(rows, flood_z=FLOOD_Z, k=5):
    """Smallest lift detectable at alpha=0.05, 80% power, on CLOSE-deflated n.

    Stated before any estimate. 'No effect' and 'no power' are different
    results and this file must not conflate them.
    """
    n = len(rows)
    closes = len({r[0] for r in rows})
    if not n or not closes:
        return float("nan")
    p = sum(1 for r in rows if r[3] > flood_z) / n
    per_arm_eff = (closes / float(k)) if k else 0.0
    if per_arm_eff <= 0 or p <= 0:
        return float("nan")
    se = math.sqrt(2.0 * p * (1.0 - p) / per_arm_eff)
    return 1.0 + (1.96 + 0.8416) * se / p


def split_time(rows, frac=0.70):
    closes = sorted({r[0] for r in rows})
    if not closes:
        return [], []
    cut = closes[int(frac * len(closes))]
    return [r for r in rows if r[0] < cut], [r for r in rows if r[0] >= cut]


KEYS = ("rv_short", "rv_long", "rv_ratio", "kurt_long", "jumps_long",
        "max_move", "prev_z", "prev_worst_any", "btc_kurt", "btc_jumps",
        "btc_rv", "btc_max_move", "hour")


# ---------------------------------------------------------------------------
def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    # -- gaps must not become jumps -----------------------------------------
    # flat at 100 to t=1039; ten seconds MISSING; back at 100 for t=1050;
    # one real +5 move at t=1051; flat at 105 thereafter. A reader that
    # bridged the hole would see the whole drift across it as one move.
    ser = {}
    for t in range(1000, 1040):
        ser[t] = 100.0
    for t in range(1050, 1051):
        ser[t] = 100.0
    for t in range(1051, 1100):
        ser[t] = 105.0
    d = _diffs(ser, 1000, 1099)
    ck(all(abs(x) < 1e-9 or abs(x - 5.0) < 1e-9 for x in d),
       "a hole in the feed is SKIPPED, never bridged -- bridging would turn "
       "one long gap into one enormous 'one-second' move")
    ck(sum(1 for x in d if abs(x) > 1e-9) == 1,
       "and exactly the one real move survives (%d non-zero of %d)"
       % (sum(1 for x in d if abs(x) > 1e-9), len(d)))
    # 1000..1039 is 40 points = 39 diffs; the hole yields none; 1050..1099 is
    # 50 points = 49 diffs. 88 in total, and the ten-second hole contributes 0.
    ck(len(d) == 39 + 49,
       "and the diffs either side of the hole are counted, the hole is not "
       "(%d)" % len(d))

    # -- the label and the features must not overlap in time ----------------
    def world(n_closes, sd, seed, jumpy_from=None, jump_sd_mult=15.0,
              start=1788700000):
        rnd = random.Random(seed)
        ser = {}
        v = 1000.0
        t0 = start - (start % 900)
        end = t0 + 900 * n_closes + 900
        for s in range(t0 - LONG - 10, end):
            close_idx = (s - t0) // 900
            hot = jumpy_from is not None and close_idx >= jumpy_from
            step = rnd.gauss(0.0, sd * (jump_sd_mult if (hot and
                                                         rnd.random() < 0.02)
                                        else 1.0))
            v += step
            ser[s] = v
        return {"TEST": ser}

    w = world(40, 0.5, seed=5)["TEST"]
    c = (min(w) + LONG + 900)
    c = c - (c % 900) + 900
    f1 = features(w, c)
    w2 = dict(w)
    # Wreck everything STRICTLY AFTER T = close-60. T itself is the instant
    # the features are taken at and is legitimately theirs; everything after
    # it belongs to the label alone.
    for s in range(c - WINDOW + 1, c + 1):
        w2[s] = w2.get(s, 1000.0) + 500.0
    f2 = features(w2, c)
    ck(f1 is not None and f2 is not None, "features compute on both worlds")
    ck(all(abs(f1[k] - f2[k]) < 1e-9 for k in f1 if k in f2),
       "NO LOOKAHEAD: moving the price by 500 inside the settlement window "
       "changes not one feature -- every one ends at close-60")

    # -- THE PLANTED EFFECT: volatility that predicts floods must be found ---
    idx = {}
    rnd = random.Random(9)
    for i in range(6):
        # half the coins go jumpy in the second half of the sample
        idx["C%d" % i] = world(200, 0.5, seed=100 + i,
                               jumpy_from=(100 if i % 2 == 0 else None),
                               start=1788700000)["TEST"]
    rows = build(idx, say=None)
    ck(len(rows) > 500, "the planted world yields %d rows" % len(rows))
    L, q = lift(rows, "kurt_long", flood_z=3.0)
    ck(L > 1.5,
       "lumpiness in the PREVIOUS hour predicts floods in the next quarter "
       "hour when that is planted (top/bottom quintile lift %.2fx)" % L)
    ck(q[-1][3] > q[0][3],
       "and the top quintile floods more often than the bottom (%.3f vs "
       "%.3f)" % (q[-1][3], q[0][3]))

    # -- THE NULL: nothing planted, nothing found ---------------------------
    idx0 = {"C%d" % i: world(200, 0.5, seed=300 + i)["TEST"] for i in range(6)}
    rows0 = build(idx0, say=None)
    L0, _ = lift(rows0, "kurt_long", flood_z=2.5)
    lo0, hi0 = boot_lift(rows0, "kurt_long", flood_z=2.5, b=400)
    ck(lo0 <= 1.0 <= hi0 or L0 != L0,
       "a world with nothing planted returns an interval covering 1.0 "
       "(%.2f [%.2f, %.2f])" % (L0, lo0, hi0))

    # -- the MDE must be real arithmetic ------------------------------------
    # HOLD THE FLOOD RATE FIXED and vary only the number of closes. Slicing a
    # real row list changes p as well as n, and the MDE depends on both -- the
    # first version of this check compared two different p's and failed for a
    # reason that had nothing to do with the formula.
    def fake(n_closes, p=0.02):
        out = []
        for i in range(n_closes):
            for j in range(6):
                z = 99.0 if ((i * 6 + j) % int(1 / p) == 0) else 0.1
                out.append((1788700000 + 900 * i, "C%d" % j, {}, z))
        return out
    m_small = mde_lift(fake(100))
    m_big = mde_lift(fake(1000))
    ck(m_small > m_big > 1.0,
       "at a FIXED flood rate the detectable lift shrinks with more closes "
       "(%.2fx on 100 closes vs %.2fx on 1000)" % (m_small, m_big))

    # -- quintiles must rank WITHIN coin ------------------------------------
    mixed = {"CHEAP": world(120, 0.001, seed=11)["TEST"],
             "DEAR": world(120, 5.0, seed=12)["TEST"]}
    rm = build(mixed, say=None)
    qq = quintiles(rm, "rv_long")
    coins_per_bucket = []
    by = defaultdict(set)
    for r in rm:
        by[r[1]].add(r[0])
    ck(len(qq) == 5, "five quintiles")
    ck(all(b[1] > 0 for b in qq),
       "and every one is populated even when two coins differ 5000x in "
       "volatility -- because the rank is taken WITHIN coin")

    # -- the time split must not overlap ------------------------------------
    a, b = split_time(rows0)
    ck(a and b and max(r[0] for r in a) <= min(r[0] for r in b),
       "the holdout split cuts on close time with no overlap")

    print("pinflood selftest: %d checks OK" % n[0])
    return 0


# ---------------------------------------------------------------------------
def report(rows, out_path, say=print, window="", flood_z=FLOOD_Z):
    lines = []
    w = lines.append
    n = len(rows)
    closes = len({r[0] for r in rows})
    floods = sum(1 for r in rows if r[3] > flood_z)
    flood_closes = len({r[0] for r in rows if r[3] > flood_z})
    mde = mde_lift(rows, flood_z)

    w("# RESULTS_flood -- can we see a jump coming?")
    w("")
    w("*`research/pinflood.py`, %s. %d coin-closes over %d closes, %s. "
      "Index feed only -- no order book, no replay, no fills, no P&L. Every "
      "predictor is computed at close-60s, the instant the settlement window "
      "opens, so the bot would have it with at least 30 seconds to spare.*"
      % (time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), n, closes, window))
    w("")
    w("A **flood** is a close where the model missed by more than %.1f of its "
      "own standard deviations. A Gaussian calls that a 1-in-%d event; here "
      "it happens on **%d of %d coin-closes (%.2f%%)** and touches **%d of "
      "%d closes (%.1f%%)**."
      % (flood_z, int(round(1.0 / max(1e-12, 1 - pincalib.norm_cdf(flood_z)))),
         floods, n, 100.0 * floods / max(1, n), flood_closes, closes,
         100.0 * flood_closes / max(1, closes)))
    w("")
    w("## 0. Power, before any estimate")
    w("")
    w("Resampling by CLOSE (twelve coins share one, hard rule 4), the "
      "smallest top-vs-bottom-quintile lift this design can call at "
      "alpha=0.05 with 80%% power is **%.2fx**. Anything under that is NO "
      "POWER, not NO EFFECT." % mde)
    w("")
    w("## 1. Every predictor, ranked within coin")
    w("")
    w("A lift BELOW 1 is not a weak signal, it is a signal pointing the other "
      "way: 0.25x means the BOTTOM fifth floods four times as often as the "
      "top. Strength is therefore `max(lift, 1/lift)`, and the first version "
      "of this table ranked on the raw lift and so buried its own strongest "
      "result at the bottom of the list.")
    w("")
    w("| predictor | bottom fifth floods | top fifth floods | lift | "
      "95% by-close interval | strength | beats MDE? |")
    w("|---|---|---|---|---|---|---|")
    scored = []
    for k in KEYS:
        L, q = lift(rows, k, flood_z)
        if L != L or len(q) < 5 or L <= 0:
            continue
        lo, hi = boot_lift(rows, k, flood_z)
        strength = max(L, 1.0 / L)
        clear = (lo > 1.0 or hi < 1.0)
        scored.append((strength, L, k, q, lo, hi))
        w("| `%s` | %.2f%% | %.2f%% | **%.2fx** | [%.2f, %.2f] | %.2fx | %s |"
          % (k, 100 * q[0][3], 100 * q[-1][3], L, lo, hi, strength,
             "**yes**" if (clear and strength >= mde) else "no"))
    w("")
    scored.sort(reverse=True)
    if scored:
        best = scored[0]
        w("Strongest: **`%s`** -- lift %.2fx [%.2f, %.2f], strength %.2fx, "
          "against an MDE of %.2fx."
          % (best[2], best[1], best[4], best[5], best[0], mde))
    w("")
    w("## 2. The strongest predictor, quintile by quintile")
    w("")
    if scored:
        k = scored[0][2]
        w("| fifth of `%s` | coin-closes | floods | flood rate | median value |"
          % k)
        w("|---|---|---|---|---|")
        for q, nn, fl, rate, med in scored[0][3]:
            w("| %d (low to high) | %d | %d | %.2f%% | %.4g |"
              % (q + 1, nn, fl, 100 * rate, med))
    w("")
    w("## 3. Holdout -- fitted on the first 70% of closes, checked on the last 30%")
    w("")
    a, b = split_time(rows)
    w("| predictor | lift, first 70% | lift, last 30% | holds? |")
    w("|---|---|---|---|")
    for _st, L, k, _q, _lo, _hi in scored[:6]:
        La, _ = lift(a, k, flood_z)
        Lb, _ = lift(b, k, flood_z)
        same_side = ((La - 1.0) * (Lb - 1.0) > 0
                     and max(La, 1 / La) > 1.2 and max(Lb, 1 / Lb) > 1.2)
        w("| `%s` | %.2fx | %.2fx | %s |"
          % (k, La, Lb, "yes" if same_side else "**no**"))
    w("")
    w("## 4. What standing aside would cost")
    w("")
    if scored:
        _st, L, k, q, _lo, _hi = scored[0]
        # Skip the DANGEROUS end, which is the bottom fifth when the lift is
        # below 1. Skipping the top fifth of an inverse predictor would throw
        # away the safest closes, which is the opposite of the intention and
        # is exactly the error the ranking fix above was made to prevent.
        dangerous = q[0] if L < 1.0 else q[-1]
        end = "BOTTOM" if L < 1.0 else "TOP"
        tot_rows = sum(x[1] for x in q)
        tot_fl = sum(x[2] for x in q)
        w("Skipping the **%s fifth of `%s`** -- the dangerous end:" % (end, k))
        w("")
        w("- **%.1f%% of coin-closes** skipped."
          % (100.0 * dangerous[1] / max(1, tot_rows)))
        w("- They carry **%d of %d floods**, %.1f%% of them."
          % (dangerous[2], tot_fl, 100.0 * dangerous[2] / max(1, tot_fl)))
        w("- Flood rate on what is left: **%.2f%%**, against %.2f%% today -- "
          "a %.0f%% reduction."
          % (100.0 * (tot_fl - dangerous[2]) / max(1, tot_rows - dangerous[1]),
             100.0 * tot_fl / max(1, tot_rows),
             100.0 * (1.0 - ((tot_fl - dangerous[2])
                             / max(1, tot_rows - dangerous[1]))
                      / max(1e-12, tot_fl / max(1, tot_rows)))))
    w("")
    w("**Nothing here is deployed, and nothing here is a loss rate of ours.** "
      "A flood is a property of the index, not of our fills; whether skipping "
      "floods saves US money depends on whether we would have traded those "
      "closes at all, which this file does not know.")
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
    ap.add_argument("--flood-z", type=float, default=FLOOD_Z)
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(HERE), "results", "RESULTS_flood.md"))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    import replay                                              # noqa: E402
    idx = replay.load_index(a.data)
    if not idx:
        print("pinflood: no cfbenchmarks_value on disk -- nothing to analyse")
        return 0
    rows = build(idx)
    if not rows:
        print("pinflood: no close had both a z-score and an hour of prior "
              "history -- nothing to analyse")
        return 0
    lo = min(r[0] for r in rows)
    hi = max(r[0] for r in rows)
    window = ("%s .. %s (%.1f days)"
              % (time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(lo)),
                 time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(hi)),
                 (hi - lo) / 86400.0))
    report(rows, a.out, window=window, flood_z=a.flood_z)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
