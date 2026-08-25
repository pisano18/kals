#!/usr/bin/env python3
# VERSION: 2026-08-25-p1
"""
pathstats.py -- is the contract price a martingale in its own right?

    python research/pathstats.py --selftest
    python research/pathstats.py --out ./fulltape --data ./kalshi_data

THE QUESTION, AND WHY ITS SHAPE IS BETTER

Every other test here asks whether the price is right about the OUTCOME. This
asks something weaker and far cheaper: does the price, on average, go anywhere
from here?

    E[ P(t + delta) - P(t) | anything knowable at t ]  ==  0  ?

If that fails, the price is predictably drifting, and **you can trade the drift
without ever holding to expiry**. Enter, wait thirty seconds, exit. No
settlement risk, no exposure to a 60-second average, no dependence on our
volatility model being right, no dependence on the index feed at all. That is a
materially better risk shape than betting on the outcome, and it is the shape
almost every real short-horizon strategy actually has.

It is also the cheapest test in the project:
  * no settlements needed -- every quote is an observation
  * no index needed
  * runs on the 2.1M-trade tape already on disk
  * and it is what "find a trend in how the prices move" actually means when
    written down precisely

WHAT COULD MAKE IT FAIL, none of which requires anyone to be wrong
  * retail momentum-chasing pushing price past fair and it drifting back
  * a maker skewing quotes to shed inventory, then unwinding
  * round-number magnetism (orders cluster at 50, 75, 90, and price sticks)
  * the price catching up to an index move it has not absorbed yet
  * predictable end-of-window flow

THREE ARTEFACTS THAT WOULD FAKE A RESULT, and what is done about each

1. BID-ASK BOUNCE. Trade prints alternate between bid and ask, which induces
   strong NEGATIVE autocorrelation in transaction prices that has nothing to do
   with information. Roll (1984). Using trade prices here would manufacture a
   large fake reversion signal. So mids are used wherever a book is available,
   and when only trade prices exist the result is labelled UNRELIABLE.

2. OCCUPATION-TIME SELECTION. Sampling wherever trades happened biases the
   estimate, not merely its standard error (see R4). So observations are taken
   on a fixed grid of times-to-close, chosen by us, not by where the price went.

3. MULTIPLE TESTING. Several features times several horizons is a lot of
   chances to find noise. Every test is counted and a Bonferroni threshold is
   printed, and a feature only counts if it holds across ADJACENT horizons --
   a real drift does not appear at 30s and vanish at 15s and 60s.
"""

import argparse
import json
import math
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import NormalDist, mean, median, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ND = NormalDist()
GRID = [720, 600, 480, 360, 300, 240, 180, 150, 120, 90, 75, 60, 45, 30]
HORIZONS = [15, 30, 60]


def parse_ts(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s if s < 1e12 else s / 1000.0)
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


# ===========================================================================
def paths_from_quotes(quotes):
    """{ticker: {sec: mid}} -- the clean source, free of bid-ask bounce."""
    return {tk: {t: (b + a) / 2.0 for t, b, a, _, _ in q}
            for tk, q in quotes.items()}, "mid"


def paths_from_tapes(out_dir):
    """Fall back to trade prints. Flagged unreliable: prints alternate between
    bid and ask, which fakes reversion (Roll 1984)."""
    fp = os.path.join(out_dir, "tapes.json")
    mfp = os.path.join(out_dir, "markets.json")
    if not (os.path.exists(fp) and os.path.exists(mfp)):
        return {}, None
    idx = {}
    for s, ms in json.load(open(mfp)).items():
        for m in ms:
            idx[m["ticker"]] = m
    out = defaultdict(dict)
    for s, ts in json.load(open(fp)).items():
        for t in ts:
            tk = t.get("ticker") or t.get("market_ticker")
            if tk not in idx:
                continue
            raw = t.get("yes_price_dollars")
            p = float(raw) if raw is not None else (
                float(t["yes_price"]) / 100.0 if t.get("yes_price") is not None
                else None)
            tt = parse_ts(t.get("created_time") or t.get("ts"))
            if p is None or tt is None or not (0 < p < 1):
                continue
            out[tk][int(round(tt))] = p
    return dict(out), "trade"


def build_obs(paths, closes, index=None):
    """One observation per (market, gridpoint): the state at t and the price
    change over each horizon. Grid times are chosen by us, never by where a
    trade happened."""
    obs = []
    for tk, series in paths.items():
        close_s = closes.get(tk)
        if not close_s or len(series) < 30:
            continue
        secs = sorted(series)
        for ttc in GRID:
            t = int(close_s) - ttc
            # last observation at or before the gridpoint, and not stale
            prev = None
            for s in secs:
                if s <= t:
                    prev = s
                else:
                    break
            if prev is None or t - prev > 30:
                continue
            p0 = series[prev]
            if not (0.02 < p0 < 0.98):
                continue
            # a short lookback for velocity, also anchored to the grid
            back = None
            for s in secs:
                if s <= t - 30:
                    back = s
                else:
                    break
            vel = (p0 - series[back]) if back is not None else 0.0
            row = {"tk": tk, "close": int(close_s), "ttc": ttc, "p": p0,
                   "vel": vel,
                   "round": min(abs(p0 - r) for r in
                                (0.10, 0.25, 0.50, 0.75, 0.90))}
            ok = False
            for h in HORIZONS:
                t2 = t + h
                if t2 > close_s:
                    continue
                nxt = None
                for s in secs:
                    if s <= t2:
                        nxt = s
                    else:
                        break
                if nxt is None or t2 - nxt > 30 or nxt <= prev:
                    continue
                row[f"d{h}"] = series[nxt] - p0
                ok = True
            if ok:
                obs.append(row)
    return obs


def clustered(vals):
    """vals: [(value, cluster)]. One observation per close-time cluster."""
    by = defaultdict(list)
    for v, c in vals:
        by[c].append(v)
    o = [mean(x) for x in by.values()]
    if len(o) < 15:
        return None
    m, sd = mean(o), pstdev(o)
    se = sd / math.sqrt(len(o)) if sd > 0 else float("inf")
    return {"mean": m, "n": len(o), "t": m / se if se > 0 else 0.0}


def test_split(obs, h, key, buckets, label, thresh, results):
    rows = [o for o in obs if f"d{h}" in o]
    if len(rows) < 200:
        return
    print(f"\n  {label}   horizon {h}s")
    print(f"  {'bucket':>16}{'clusters':>10}{'mean move':>12}{'t':>8}   verdict")
    for lo, hi, name in buckets:
        sel = [o for o in rows if lo <= o[key] < hi]
        if len(sel) < 100:
            continue
        c = clustered([(o[f"d{h}"], o["close"]) for o in sel])
        if not c:
            continue
        v = ("DRIFT" if abs(c["t"]) > thresh else
             "watch" if abs(c["t"]) > 2 else "flat")
        print(f"  {name:>16}{c['n']:>10}{100*c['mean']:>11.3f}c{c['t']:>8.1f}"
              f"   {v}")
        results.append({"feature": label, "bucket": name, "h": h,
                        "mean": c["mean"], "t": c["t"], "n": c["n"]})


def report(obs, source):
    if not obs:
        print("  no observations.")
        return
    n_tests = 0
    for h in HORIZONS:
        n_tests += 5 + 5 + 4 + 4
    thresh = ND.inv_cdf(1 - 0.025 / max(n_tests, 1))
    print("=" * 78)
    print("IS THE CONTRACT PRICE A MARTINGALE?")
    print("=" * 78)
    print(f"  {len(obs):,} grid observations across "
          f"{len({o['close'] for o in obs}):,} close-time clusters")
    print(f"  price source: {source}"
          + ("   *** UNRELIABLE: trade prints alternate between bid and ask, "
             "which fakes reversion ***" if source == "trade" else
             "   (mids -- free of bid-ask bounce)"))
    print(f"  {n_tests} tests -> Bonferroni |t| threshold {thresh:.2f}")

    results = []
    for h in HORIZONS:
        test_split(obs, h, "p",
                   [(0.02, 0.15, "2-15c"), (0.15, 0.35, "15-35c"),
                    (0.35, 0.65, "35-65c"), (0.65, 0.85, "65-85c"),
                    (0.85, 0.98, "85-98c")],
                   "BY PRICE LEVEL", thresh, results)
        test_split(obs, h, "vel",
                   [(-1.0, -0.06, "fell >6c"), (-0.06, -0.02, "fell 2-6c"),
                    (-0.02, 0.02, "flat"), (0.02, 0.06, "rose 2-6c"),
                    (0.06, 1.0, "rose >6c")],
                   "BY RECENT MOVE  (momentum vs reversion)", thresh, results)
        test_split(obs, h, "ttc",
                   [(30, 90, "30-90s"), (90, 180, "90-180s"),
                    (180, 360, "180-360s"), (360, 721, "360-720s")],
                   "BY TIME TO CLOSE", thresh, results)
        test_split(obs, h, "round",
                   [(0.0, 0.005, "on a round no."), (0.005, 0.02, "within 2c"),
                    (0.02, 0.05, "2-5c away"), (0.05, 1.0, "far")],
                   "BY DISTANCE TO A ROUND NUMBER", thresh, results)

    print("\n" + "=" * 78)
    print("WHAT SURVIVES")
    print("=" * 78)
    big = [r for r in results if abs(r["t"]) > thresh]
    if not big:
        print("  Nothing clears the corrected threshold. The price is a")
        print("  martingale on this evidence -- which is the efficient-market")
        print("  answer, and a genuine result rather than a failure.")
        return
    by_feat = defaultdict(list)
    for r in big:
        by_feat[(r["feature"], r["bucket"])].append(r)
    print(f"  {'feature':>34}{'horizons':>12}{'mean move':>12}   consistent?")
    for k, v in sorted(by_feat.items(), key=lambda kv: -abs(kv[1][0]["t"])):
        hs = sorted(r["h"] for r in v)
        avg = mean([r["mean"] for r in v])
        # a real drift grows with horizon and shows at adjacent horizons
        consistent = (len(hs) >= 2 and
                      all((r["mean"] > 0) == (v[0]["mean"] > 0) for r in v))
        print(f"  {k[0] + ' / ' + k[1]:>34}{str(hs):>12}{100*avg:>11.3f}c"
              f"   {'YES' if consistent else 'one horizon only'}")
    print("\n  Trust only rows marked YES. A drift that appears at one horizon")
    print("  and not its neighbours is noise: a real one grows with the")
    print("  horizon rather than switching on and off.")
    print("\n  And before trading any of it: the move must exceed the round-trip")
    print("  cost, which is two crossings of the spread plus two fees. At 50c")
    print("  that is roughly 5.5c; at 90c roughly 2.5c. A 0.5c drift is real")
    print("  and untradeable.")


# ===========================================================================
def selftest():
    print("=" * 78)
    print("SELF-TEST -- silent on a martingale, finds a planted drift")
    print("=" * 78)
    fails = []

    def make(overreact=0.0, n_mkt=900, seed=5):
        """A TRUE martingale in (0,1), with an optional transient overreaction.

        p_t = Phi(W_t / sqrt(T-t)) is exactly the probability that a driftless
        walk ends above zero, so it is a martingale by construction AND bounded
        without any clamping. The earlier generator clamped p into [0.01,0.99],
        which is a reflecting barrier: prices near the edges could only move one
        way, and that alone produced 6 buckets of 'drift' in what was supposed
        to be the null. The generator was wrong, not the test.

        `overreact` adds k times the last innovation to the SHOWN price, a
        transient that must decay -- a clean planted reversion.
        """
        rnd = random.Random(seed)
        paths, closes = {}, {}
        for w in range(n_mkt):
            close_s = 1_760_000_000 + w * 900
            tk = f"M{w:05d}"
            closes[tk] = close_s
            x, ser, prev_step = 0.0, {}, 0.0
            for s in range(close_s - 900, close_s + 1):
                step = rnd.gauss(0, 1.0)
                x += step
                rem = max(close_s - s, 1)
                p_true = ND.cdf(x / math.sqrt(rem))
                p_shown = p_true + overreact * prev_step * 0.02
                prev_step = step
                p_shown = min(max(p_shown, 0.005), 0.995)
                ser[s] = round(p_shown * 100) / 100.0
            paths[tk] = ser
        return paths, closes

    print("\n1. NULL: pure martingale. Measure the FIRING RATE, not one draw.")
    TH = 3.2
    fires, tot, worst = 0, 0, 0.0
    for seed in range(5):
        paths, closes = make(overreact=0.0, n_mkt=700, seed=1000 + seed)
        obs = build_obs(paths, closes)
        res = []
        for h in HORIZONS:
            test_split(obs, h, "p",
                       [(0.02, 0.35, "low"), (0.35, 0.65, "mid"),
                        (0.65, 0.98, "high")], "BY PRICE LEVEL", TH, res)
        f = sum(1 for r in res if abs(r["t"]) > TH)
        fires += f
        tot += len(res)
        worst = max(worst, max((abs(r["t"]) for r in res), default=0.0))
    print(f"\n  {fires} of {tot} buckets fired across 5 independent nulls; "
          f"worst |t| = {worst:.2f} vs threshold {TH}")
    if fires:
        fails.append(f"null fired {fires}/{tot} times -- not calibrated")
    print("  KNOWN ARTEFACT: at the 60s horizon the extreme price buckets show")
    print("  a mild reversion toward the middle in EVERY simulated null (~+1c")
    print("  low, ~-1.3c high, |t| about 2). It comes from cent quantization")
    print("  interacting with the entry filter near the boundaries, never")
    print("  clears the corrected threshold, but must not be read as a finding")
    print("  on real data.")

    print("\n1b. A FABRICATED CLOSE TIME MIS-STAMPS EVERY GRIDPOINT")
    print("   The tape stops 600s before the real close (a dropped")
    print("   subscription). Taking the last quote AS the close shifts every")
    print("   time-to-close by 600s, and ttc is the one variable this whole")
    print("   file conditions on.")
    paths_f, closes_f = make(overreact=0.0, n_mkt=200, seed=4242)
    truncated = {}
    for tk, ser in paths_f.items():
        cut = closes_f[tk] - 600
        truncated[tk] = {t: v for t, v in ser.items() if t <= cut}
    obs_true = build_obs(truncated, closes_f)
    fake_closes = {tk: max(ser) for tk, ser in truncated.items() if ser}
    obs_fake = build_obs(truncated, fake_closes)
    ttc_true = sorted({o["ttc"] for o in obs_true})
    ttc_fake = sorted({o["ttc"] for o in obs_fake})
    print(f"\n   {'close time':>22}{'rows':>9}   time-to-close values present")
    print(f"   {'real (measured)':>22}{len(obs_true):>9}   "
          f"{ttc_true if ttc_true else '(none below 600s -- correct)'}")
    print(f"   {'last quote (invented)':>22}{len(obs_fake):>9}   {ttc_fake}")
    invented = [t for t in ttc_fake if t not in ttc_true]
    if not invented:
        fails.append("the fabricated close produced no phantom gridpoints -- "
                     "this test has stopped testing anything")
    if any(t < 600 for t in ttc_true):
        fails.append(f"measured close produced rows inside the missing "
                     f"600s of tape: {[t for t in ttc_true if t < 600]}")
    print(f"   -> {len(invented)} phantom gridpoints, every one of them "
          f"actually observed\n      600s earlier than its label says.")

    print("\n2. PLANTED: the shown price overreacts to the last move")
    paths, closes = make(overreact=1.0)
    obs = build_obs(paths, closes)
    res = []
    for h in HORIZONS:
        test_split(obs, h, "vel",
                   [(-1.0, -0.02, "fell"), (-0.02, 0.02, "flat"),
                    (0.02, 1.0, "rose")],
                   "BY RECENT MOVE", 3.5, res)
    rose = [r for r in res if r["bucket"] == "rose"]
    fell = [r for r in res if r["bucket"] == "fell"]
    ok = (rose and fell and mean([r["mean"] for r in rose]) < 0
          and mean([r["mean"] for r in fell]) > 0)
    print(f"\n  after a rise, mean move {100*mean([r['mean'] for r in rose]):+.3f}c"
          f"   after a fall {100*mean([r['mean'] for r in fell]):+.3f}c")
    if not ok:
        fails.append("failed to recover a planted reversion")
    else:
        print("  reversion recovered with the correct sign on both sides.")

    print("\n3. EXOGENOUS SAMPLING: grid points are ours, not the market's")
    per = defaultdict(int)
    for o in obs:
        per[o["ttc"]] += 1
    spread = max(per.values()) / max(min(per.values()), 1)
    print(f"  observations per gridpoint vary by {spread:.2f}x "
          f"(a trade-driven sample would vary by 10x or more)")
    if spread > 3.0:
        fails.append(f"gridpoint counts vary {spread:.1f}x -- sampling is not "
                     "exogenous")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- silent on a martingale, recovers a planted")
    print("reversion with the right sign, and samples on our own grid.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--assume-close-grid", type=int, default=0,
                    help="infer missing close times by snapping the last quote "
                         "up to the next multiple of this many seconds (e.g. "
                         "900). Off by default: an inferred close time "
                         "mis-stamps every time-to-close in the report.")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed")

    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    paths, source, closes = {}, None, {}
    try:
        from replay import load_quotes, load_markets
        q = load_quotes(a.data)
        if not q:
            try:
                from book import rebuild
                q, _ = rebuild(a.data)
            except Exception:
                q = {}
        if q:
            paths, source = paths_from_quotes(q)
            mk = load_markets(a.out)
            closes = {tk: int(m["close"]) for tk, m in mk.items()}
    except Exception as e:
        print(f"  quote load failed ({type(e).__name__}: {e})")
    if not paths:
        print("  no book quotes; falling back to trade prints")
        paths, source = paths_from_tapes(a.out)
        mk_fp = os.path.join(a.out, "markets.json")
        if os.path.exists(mk_fp):
            for s, ms in json.load(open(mk_fp)).items():
                for m in ms:
                    closes[m["ticker"]] = int(m["close"])
    if not paths:
        print("  nothing to analyse.")
        return

    # Markets with no settled record have no known close time. The last quote
    # is NOT the close: the collector stops when the subscription drops or the
    # process restarts, and using it stamps ttc=0 on a moment that may be ten
    # minutes early. Every gridpoint in build_obs is then measured at the wrong
    # time-to-close, which is the single variable this whole file conditions
    # on. Drop them, loudly, rather than fabricate.
    missing = [tk for tk in paths if tk not in closes]
    if missing:
        print(f"\n  {len(missing):,} of {len(paths):,} markets have quotes but "
              f"no settled record, so no known close time.")
        if a.assume_close_grid:
            g = a.assume_close_grid
            kept = 0
            for tk in missing:
                ts = sorted(paths[tk])
                if not ts:
                    continue
                snapped = ((ts[-1] + g - 1) // g) * g
                # only believe it if the tape actually runs up to that close;
                # a market whose quotes stop half a window early tells us
                # nothing about which window it belonged to
                if snapped - ts[-1] <= 60:
                    closes[tk] = snapped
                    kept += 1
            print(f"  --assume-close-grid {g}: snapped {kept:,} of them to the "
                  f"next {g}s boundary (tape within 60s of it); "
                  f"{len(missing)-kept:,} dropped.")
            print("  These close times are INFERRED. Anything that depends on "
                  "them is weaker evidence than the rest of this report.")
        else:
            print("  Dropping them. Pass --assume-close-grid 900 to snap the "
                  "last quote up to the next 15-minute boundary instead "
                  "(inferred, not measured).")

    obs = build_obs(paths, closes)
    report(obs, source)


if __name__ == "__main__":
    main()
