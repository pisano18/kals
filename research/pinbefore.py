#!/usr/bin/env python3
"""pinbefore.py -- what if we bought EARLIER than 30 seconds?

THE OPERATOR, 2026-09-16: "What if we bought before 30?"

It is the right question at exactly the right moment. We have just hit the
ceiling the whole compounding chart depends on: we ask the book for 90 contracts
and it hands back 67, because half of all offers hold fewer than 67. More time
before the close means more of the market still unpicked -- and measured on live
signals, the offer at 28-30 seconds is a median 105 contracts against 29 at
23-27. If the books keep getting deeper further out, this is the one idea that
attacks the actual constraint.

WHAT STOPS US TODAY is TAU_MAX = 30, and the comment in pinrun calls it a
measured wall: on moments the model called under 2% risk, zero flipped between 3
and 30 seconds, 25 of 7,302 flipped at 31-45, and 126 of 10,047 at 46-60 --
3.7x and 10.9x overconfident.

WHY IT IS WORTH RE-MEASURING RATHER THAN QUOTING. That table predates nine days
of index tape and it was computed at a 2% risk bar, while the live gate demands
0.5%. The question is not "is the model worse out there" -- it is -- but "is
there a confidence bar strict enough that the extra time pays for itself?"
Overconfidence is a MULTIPLIER, so demanding 3.7x more certainty at 31-45 should
land the real risk back where it is now. Whether enough moments survive that bar
is the thing nobody has counted.

THE ARITHMETIC THAT MAKES IT URGENT, from our own live record: 430 wins
averaging $1.59 and 21 losses averaging $14.74. ONE LOSS COSTS 9.3 WINS. So a
3.7x rise in the loss rate at an unchanged bar turns +$375 into roughly -$557.
There is no room to be casual about this.

INDEX ONLY. This never opens an order book, never replays a fill, never
computes P&L -- it reads the 1-per-second settlement index and the settled
strikes, exactly like pincalib, so nothing here is a backtest and nothing here
may be quoted as our loss rate (CLAUDE.md, 2026-09-10).

    python research/pinbefore.py --selftest
    python research/pinbefore.py
"""
import argparse
import collections
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")

N_AVG = 60
SIGMA_WIN = 300
BANDS = [(3, 11), (11, 21), (21, 31), (31, 46), (46, 61)]


def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def var_factor(tau):
    """Var(settle)/sigma^2 with tau seconds left, for a 60-print mean.

    Only the tau prints still to come carry risk; the 60-tau already recorded
    are on disk. Beyond 60 the whole window is ahead plus (tau-60) of drift."""
    if tau <= 0:
        return 0.0
    r = min(int(tau), N_AVG)
    base = r * (r + 1) * (2 * r + 1) / 6.0 / (N_AVG ** 2)
    return base + max(0.0, tau - N_AVG)


def fair(locked_sum, locked_n, spot, strike, tau, sigma):
    """P(settle > strike) the way pinrun computes it."""
    remaining = N_AVG - locked_n
    mu = (locked_sum + remaining * spot) / N_AVG
    sd = sigma * math.sqrt(var_factor(tau))
    if sd <= 0:
        return 1.0 if mu > strike else 0.0
    return norm_cdf((mu - strike) / sd)


def band_of(tau):
    for lo, hi in BANDS:
        if lo <= tau < hi:
            return (lo, hi)
    return None


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " + m) if c else ("FAIL: " + m))
        ok = ok and c

    ck(abs(var_factor(60) - 60 * 61 * 121 / 6.0 / 3600) < 1e-12,
       "at 60 seconds the whole window is ahead and nothing has drifted yet")
    ck(var_factor(90) > var_factor(60) > var_factor(30) > var_factor(10),
       "risk falls monotonically as the close approaches")
    ck(abs(var_factor(90) - (var_factor(60) + 30)) < 1e-9,
       "past 60 seconds each extra second adds a full second of drift -- which "
       "is exactly why the model degrades out there")
    ck(var_factor(0) == 0.0, "NULL: at the close there is nothing left to learn")
    ck(var_factor(30) / var_factor(10) > 6,
       "thirty seconds carries %.1fx the risk of ten" %
       (var_factor(30) / var_factor(10)))

    ck(abs(fair(0, 0, 100.0, 100.0, 30, 0.1) - 0.5) < 1e-9,
       "at the strike it is a coin flip whatever the volatility")
    hi = fair(0, 0, 101.0, 100.0, 30, 0.05)
    ck(hi > 0.999, "a dollar clear with small vol is near certain (%.5f)" % hi)
    ck(fair(59 * 110.0, 59, 100.0, 100.0, 1, 1.0) > 0.999,
       "and with 59 of 60 prints locked far above the strike it is settled -- "
       "the whole reason the pin works")
    ck(fair(0, 0, 101.0, 100.0, 30, 0.05)
       + fair(0, 0, 99.0, 100.0, 30, 0.05) == 1.0,
       "the two sides sum to exactly one")

    ck(band_of(30) == (21, 31) and band_of(31) == (31, 46),
       "THE BOUNDARY THAT MATTERS: 30 is inside today's window, 31 is outside")
    ck(band_of(2) is None and band_of(61) is None,
       "NULL: outside the measured range belongs to no band")
    print("pinbefore selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--data", default="C:/kals/kalshi_data")
    ap.add_argument("--out", default="C:/kals/fulltape")
    ap.add_argument("--bars", default="0.995,0.999,0.9987,0.9999")
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0

    import endgame
    import idxload
    import replay

    markets = replay.load_markets(a.out)
    if not markets:
        print("no markets.json under %s -- run kalshi_fulltape first" % a.out)
        return 0
    series_index = replay.SERIES_TO_INDEX
    need = sorted({series_index[m["series"]] for m in markets.values()
                   if m.get("series") in series_index})
    idx = idxload.load(need, verbose=False)
    print("\n%d settled markets, %d indices loaded" % (len(markets), len(idx)))

    bars = [float(x) for x in a.bars.split(",")]
    # per (band, bar): [n_moments, n_wrong]
    tally = collections.defaultdict(lambda: [0, 0])
    scored = 0
    for tk, m in markets.items():
        iid = series_index.get(m.get("series"))
        D = idx.get(iid) if iid else None
        if D is None:
            continue
        try:
            close = int(m["close"])
            strike = float(m["strike"])
        except (KeyError, TypeError, ValueError):
            continue
        # USE endgame.outcome_of, NOT float(m["result"]). `result` is the
        # string 'yes'/'no' here and `settle` is the index LEVEL, not the
        # outcome -- confusing the two once booked a YES win for every market,
        # which is why that function exists. float('yes') is what this file
        # tried first.
        out = endgame.outcome_of(m, strike)
        if out is None:
            continue
        yes_won = out >= 0.5
        # locked prints and sigma, walked backwards from the close
        vals = [D.get(s) for s in range(close - N_AVG, close)]
        if any(v is None for v in vals):
            continue
        sig = [D.get(s) for s in range(close - SIGMA_WIN, close)]
        sig = [x for x in sig if x is not None]
        if len(sig) < 120:
            continue
        diffs = [sig[i] - sig[i - 1] for i in range(1, len(sig))]
        mean = sum(diffs) / len(diffs)
        sigma = math.sqrt(sum((d - mean) ** 2 for d in diffs) / len(diffs))
        if sigma <= 0:
            continue
        scored += 1
        for tau in range(3, 61):
            b = band_of(tau)
            if not b:
                continue
            locked_n = max(0, N_AVG - tau)
            locked_sum = sum(vals[:locked_n]) if locked_n else 0.0
            spot = D.get(close - tau)
            if spot is None:
                continue
            p = fair(locked_sum, locked_n, spot, strike, tau, sigma)
            for bar in bars:
                if p >= bar:
                    t = tally[(b, bar)]
                    t[0] += 1
                    t[1] += (not yes_won)
                elif p <= 1 - bar:
                    t = tally[(b, bar)]
                    t[0] += 1
                    t[1] += yes_won

    print("scored %d closes\n" % scored)
    for bar in bars:
        claimed = 100 * (1 - bar)
        print("=== the model must be at least %.2f%% sure (claims %.2f%% risk) ==="
              % (100 * bar, claimed))
        print("  %-12s %10s %8s %10s %12s" % ("seconds left", "moments", "wrong",
                                              "real risk", "overconfident"))
        for b in BANDS:
            n, wrong = tally[(b, bar)]
            if not n:
                continue
            real = 100 * wrong / n
            print("  %-12s %10d %8d %9.3f%% %11s"
                  % ("%d-%d" % (b[0], b[1] - 1), n, wrong, real,
                     ("%.1fx" % (real / claimed)) if claimed else "-"))
        print()
    print("A band is usable if its real risk is no worse than what we accept")
    print("today (the 21-30 row at 99.5%). More moments there is the prize;")
    print("a worse real risk at any bar is the thing that would invert the P&L.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
