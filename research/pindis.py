#!/usr/bin/env python3
# VERSION: 2026-09-13-ds1
"""pindis.py -- DOES THE EXCHANGES DISAGREEING PREDICT A BLOW-UP?

THE OPERATOR, 2026-09-13: "tracking volume, volatility, or anything else you
can think of or that is available and seeing how that correlates to lumpiness
and large price swings."

WHAT IS NEW HERE. Everything this project has measured so far came from the
settlement index, which is ONE NUMBER PER SECOND. `feed_data/index_replica`
carries the bid and ask of every constituent exchange behind that number. When
Coinbase says BTC is 76,777 and Gemini says 76,795, the index publishes one
price and the eighteen-dollar disagreement is invisible in it. That
disagreement is information the index physically cannot contain, and no
analysis in this repository has ever looked at it.

WHY IT MIGHT MATTER. The settlement value is an average across venues. If the
venues are far apart, the average is being taken over a wider cloud, and the
next second's average is less predictable from this second's. That is a reason
to expect a relationship, stated BEFORE the measurement, which is the
difference between a hypothesis and a story fitted afterwards.

THE FOUR FEATURES, all read at T = close - 60, the instant the settlement
window opens, so the bot would have them with at least 30 seconds to spare:

    spread_rel    (max mid - min mid) / price, across venues
    wmid_gap      |weighted mid - median mid| / price
    n_ex          how many venues reported -- also a data-health measure
    quote_spread  mean bid-ask across venues / price; the closest thing to
                  LIQUIDITY available without opening Bitstamp's 7.8 GB

THE OUTCOME is `pinflood`'s: a close is a FLOOD when the model missed by more
than 3 of its own standard deviations. The scoring is `pinflood`'s too --
quintiles ranked WITHIN coin, lift with a by-close bootstrap, the MDE stated
before the estimate, and a time-split holdout. Nothing is reimplemented.

NO KALSHI ORDER BOOK, NO REPLAY, NO FILLS, NO P&L.
"""
import argparse
import math
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pincalib                                                # noqa: E402
import pinflood                                                # noqa: E402
import pinfeed                                                 # noqa: E402

KEYS = ("spread_rel", "wmid_gap", "n_ex", "quote_spread")
FLOOD_Z = 3.0
Z_TAU = 20
WINDOW = 60


def build(coin, dis, pub, z_tau=Z_TAU, say=print):
    """[(close, coin, features, |z|)] in pinflood's row shape."""
    rows = []
    if not pub:
        return rows
    lo, hi = min(pub), max(pub)
    c = lo - (lo % 900) + 900
    n_noz = n_nofeat = 0
    while c <= hi:
        r = pincalib.zscore(pub, c, z_tau)
        if r is None:
            n_noz += 1
            c += 900
            continue
        d = dis.get(c - WINDOW)
        if d is None:
            n_nofeat += 1
            c += 900
            continue
        f = {"spread_rel": d[0], "wmid_gap": d[1], "n_ex": d[2],
             "quote_spread": d[3]}
        rows.append((c, coin, f, abs(r[0])))
        c += 900
    if say:
        say("  %s: %d closes usable (%d had no z, %d had no venue snapshot at "
            "the window open)" % (coin, len(rows), n_noz, n_nofeat))
    return rows


def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    import random
    rnd = random.Random(11)

    # A world where disagreement CAUSES floods, and one where it does not.
    def world(n_closes, coupled, seed):
        """Disagreement at the window open, and a JUMP inside the window.

        THE FIRST VERSION OF THIS FIXTURE PLANTED THE WRONG THING and the
        self-test caught it. It raised volatility for the whole 900 seconds
        before a "wide" close -- but sigma is measured from exactly that
        stretch, so the ruler grew with it and z SHRANK. The estimator
        correctly reported an inverse relationship, which is the same
        mechanical effect pinflood found for rv_short, and nothing to do with
        what this file is trying to test.

        What has to be planted is a jump the RULER CANNOT SEE: the seconds
        before the window are ordinary, so sigma is ordinary, and the jump
        lands inside [close-60, close) where it moves the settlement without
        ever entering the volatility estimate.
        """
        rnd2 = random.Random(seed)
        pub = {}
        dis = {}
        v = 1000.0
        t0 = 1788700000 - (1788700000 % 900)
        for k in range(n_closes + 2):
            c = t0 + 900 * k
            wide = rnd2.random() < 0.3
            for s in range(c - 900, c):
                v += rnd2.gauss(0.0, 0.5)
                # THE JUMP MUST LAND AFTER THE DECISION, NOT MERELY INSIDE
                # THE WINDOW. The second fixture put it at c-30; with tau=20
                # the forecast is made at c-20, so the jump was already in
                # `locked`, already in `spot`, and already in sigma -- the
                # model saw all of it, z was unmoved, and the inflated sigma
                # made the wide arm look SAFER. c-10 is after the decision and
                # after the sigma window, which is the only place a jump can
                # actually hurt us.
                if wide and coupled and s == c - 10:
                    v += 40.0
                pub[s] = v
            dis[c - WINDOW] = ((0.004 if wide else 0.0005),
                               (0.002 if wide else 0.0002),
                               3.0 if wide else 4.0,
                               (0.001 if wide else 0.0001))
        return pub, dis

    pub, dis = world(400, True, 5)
    rows = build("T", dis, pub, say=None)
    ck(len(rows) > 200, "the coupled world yields %d rows" % len(rows))
    L, q = pinflood.lift(rows, "spread_rel", flood_z=FLOOD_Z)
    ck(L > 1.5,
       "when disagreement genuinely precedes the wild closes it is found "
       "(lift %.2fx, bottom %.2f%% vs top %.2f%%)"
       % (L, 100 * q[0][3], 100 * q[-1][3]))

    pub2, dis2 = world(400, False, 6)
    rows2 = build("T", dis2, pub2, say=None)
    L2, _q2 = pinflood.lift(rows2, "spread_rel", flood_z=FLOOD_Z)
    lo2, hi2 = pinflood.boot_lift(rows2, "spread_rel", flood_z=FLOOD_Z, b=400)
    ck(lo2 <= 1.0 <= hi2,
       "and in a world where the SAME disagreement pattern is present but "
       "uncoupled from the outcome, the interval covers 1.0 (%.2f [%.2f, "
       "%.2f]) -- the label alone cannot manufacture a result"
       % (L2, lo2, hi2))

    # no lookahead: the features are read at close-60 and nothing after it
    pub3 = dict(pub)
    c_test = sorted({r[0] for r in rows})[10]
    for s in range(c_test - WINDOW + 1, c_test + 1):
        pub3[s] = pub3.get(s, 1000.0) + 500.0
    r_before = [r for r in rows if r[0] == c_test][0]
    rows3 = build("T", dis, pub3, say=None)
    r_after = [r for r in rows3 if r[0] == c_test]
    ck(r_after and r_after[0][2] == r_before[2],
       "wrecking the settlement window changes NO feature -- every one is "
       "read at close-60")
    ck(r_after and r_after[0][3] != r_before[3],
       "while it does change the outcome, so the fixture is actually testing "
       "something")

    ck(pinflood.mde_lift(rows, FLOOD_Z) > 1.0,
       "the MDE is computable and above 1 (%.2fx)"
       % pinflood.mde_lift(rows, FLOOD_Z))
    print("pindis selftest: %d checks OK" % n[0])
    return 0


def report(rows, out_path, say=print, flood_z=FLOOD_Z, window=""):
    lines = []
    w = lines.append
    n = len(rows)
    closes = len({r[0] for r in rows})
    fl = sum(1 for r in rows if r[3] > flood_z)
    mde = pinflood.mde_lift(rows, flood_z)
    w("# RESULTS_disagree -- do the exchanges disagreeing predict a blow-up?")
    w("")
    w("*`research/pindis.py`, %s. %d coin-closes over %d closes, %s. From "
      "`feed_data/index_replica` -- the per-venue bids and asks BEHIND the "
      "settlement index, which the index itself cannot contain. No Kalshi "
      "order book, no replay, no fills, no P&L.*"
      % (time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), n, closes, window))
    w("")
    w("Floods: **%d of %d (%.2f%%)**. MDE, stated before the estimate: "
      "**%.2fx**. Anything under that is NO POWER, not NO EFFECT."
      % (fl, n, 100.0 * fl / max(1, n), mde))
    w("")
    w("| feature | bottom fifth floods | top fifth floods | lift | "
      "95% by-close | strength | beats MDE? |")
    w("|---|---|---|---|---|---|---|")
    scored = []
    for k in KEYS:
        L, q = pinflood.lift(rows, k, flood_z)
        if L != L or L <= 0 or len(q) < 5:
            continue
        lo, hi = pinflood.boot_lift(rows, k, flood_z)
        st = max(L, 1.0 / L)
        clear = (lo > 1.0 or hi < 1.0)
        scored.append((st, L, k, lo, hi))
        w("| `%s` | %.2f%% | %.2f%% | **%.2fx** | [%.2f, %.2f] | %.2fx | %s |"
          % (k, 100 * q[0][3], 100 * q[-1][3], L, lo, hi, st,
             "**yes**" if (clear and st >= mde) else "no"))
    w("")
    scored.sort(reverse=True)
    if scored:
        st, L, k, lo, hi = scored[0]
        w("Strongest: **`%s`**, lift %.2fx [%.2f, %.2f], strength %.2fx "
          "against an MDE of %.2fx. %s"
          % (k, L, lo, hi, st, mde,
             "**Clears the bar.**" if (st >= mde and (lo > 1 or hi < 1))
             else "**Does not clear the bar** -- no power, not no effect."))
    w("")
    w("## Holdout")
    w("")
    a, b = pinflood.split_time(rows)
    w("| feature | lift first 70% | lift last 30% | same direction? |")
    w("|---|---|---|---|")
    for _st, _L, k, _lo, _hi in scored:
        La, _ = pinflood.lift(a, k, flood_z)
        Lb, _ = pinflood.lift(b, k, flood_z)
        same = (La - 1.0) * (Lb - 1.0) > 0
        w("| `%s` | %.2fx | %.2fx | %s |"
          % (k, La, Lb, "yes" if same else "**no**"))
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
    ap.add_argument("--feed", default="C:/kals/feed_data")
    ap.add_argument("--data", default="C:/kals/kalshi_data")
    ap.add_argument("--coins", default="BTC,ETH,SOL,XRP")
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(HERE), "results", "RESULTS_disagree.md"))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    rows = []
    for coin in [c.strip() for c in a.coins.split(",") if c.strip()]:
        iid = pinfeed.COIN_TO_INDEX.get(coin)
        if not iid:
            print("  no published index known for %s, skipping" % coin)
            continue
        dis = pinfeed.load_disagree(a.feed, coin)
        if not dis:
            continue
        pub = pinfeed.load_published(a.data, iid)
        if not pub:
            continue
        rows.extend(build(coin, dis, pub))
        del dis, pub
    if not rows:
        print("pindis: no close had both a venue snapshot and a z-score -- "
              "nothing to analyse")
        return 0
    lo = min(r[0] for r in rows)
    hi = max(r[0] for r in rows)
    window = ("%s .. %s (%.1f days)"
              % (time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(lo)),
                 time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(hi)),
                 (hi - lo) / 86400.0))
    report(rows, a.out, window=window)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
