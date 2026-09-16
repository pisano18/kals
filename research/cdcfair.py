#!/usr/bin/env python3
"""cdcfair.py -- would a strategy have made money on Crypto.com's binaries?

THE OPERATOR, 2026-09-16: "Do start recording and seeing if your strategy or a
strategy would work if you could bet."

The pin does not transfer: `cdcbook.py` showed their book goes EMPTY about 40
seconds before every close, and the pin lives in the last 30. But the book is
deep before that -- 1,000 to 4,250 contracts on a side against the ~50 we get
filled on Kalshi -- and `cdcchain.py` showed our CF Benchmarks feed reproduces
their published settlements to about 2 basis points on BTC, ETH, SOL and XRP.

So the question becomes: at 60 to 400 seconds out, do they quote a price our
feed says is wrong, by more than the spread?

FAIR VALUE. Settlement is the mean of the last 60 seconds of the index. With
tau seconds left and tau >= 60, none of those prints exist yet: the window
starts in m = tau - 60 seconds. Under independent per-second increments of
variance s2,

    Var(settle) = s2 * ( m + sum_{i,j<=60} min(i,j) / 60^2 )
                = s2 * ( tau - 60 + 20.5028 )

and fair = Phi((spot - strike)/sd). The constant is exact:
60*61*121/6/3600 = 20.5028. Below 60 seconds part of the window is locked and
the locked prints are used directly, which is the same arithmetic the pin uses
on Kalshi.

WHAT IT REPORTS, AND WHAT IT REFUSES TO REPORT. Every quote where our fair
value beats their price by more than a threshold is recorded as a bet, and
then SETTLED against what the index actually did. That is a hypothetical fill
at a price we saw quoted, so it is an upper bound on what we would have made
and it is labelled as such: we would not have been given every contract at the
top of book, and a market maker who is about to be picked off cancels.

The outcome comes from OUR index standing in for theirs, so a contract whose
settlement margin is inside the feed disagreement is not scored at all --
`--min-margin` is that filter and it defaults to 5 basis points, twice the
median disagreement measured by cdcchain.py.

READ-ONLY.

    python research/cdcfair.py --selftest
    python research/cdcfair.py
"""
import argparse
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import cdcedge                                               # noqa: E402

N_AVG = 60
# sum_{i,j<=60} min(i,j) / 60^2 -- the variance of a 60-print mean of a walk,
# in units of one second's variance
MEAN_FACTOR = N_AVG * (N_AVG + 1) * (2 * N_AVG + 1) / 6.0 / (N_AVG ** 2)


def phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def var_units(tau, locked_n=0):
    """Var(settle)/s2 with tau seconds to close.

    tau >= 60: the whole window is ahead, after m = tau - 60 seconds of drift.
    tau <  60: locked_n prints are already on disk and contribute nothing."""
    if tau >= N_AVG:
        return (tau - N_AVG) + MEAN_FACTOR
    r = N_AVG - locked_n if locked_n else int(max(tau, 0))
    return r * (r + 1) * (2 * r + 1) / 6.0 / (N_AVG ** 2)


def fair_value(spot, strike, tau, sigma, locked_sum=0.0, locked_n=0):
    """P(settle > strike). sigma is the per-second standard deviation."""
    v = var_units(tau, locked_n)
    sd = sigma * math.sqrt(v) if v > 0 else 0.0
    remaining = N_AVG - locked_n
    centre = (locked_sum + remaining * spot) / N_AVG if locked_n else spot
    if sd <= 0:
        return 1.0 if centre > strike else 0.0
    return phi((centre - strike) / sd)


def per_second_sigma(D, close, lookback=1800):
    """Standard deviation of one-second index changes, in price units."""
    vals = []
    prev = None
    for s in range(close - lookback, close):
        v = D.get(s)
        if v is not None and prev is not None:
            vals.append(v - prev)
        if v is not None:
            prev = v
    if len(vals) < 120:
        return None
    return statistics.pstdev(vals)


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " + m) if c else ("FAIL: " + m))
        ok = ok and c

    ck(abs(MEAN_FACTOR - 20.5028) < 1e-3,
       "the 60-print mean carries %.4f seconds of variance, not 60 and not 1 "
       "-- the whole collapse is in that number" % MEAN_FACTOR)
    ck(var_units(600) > var_units(120) > var_units(60),
       "variance falls as the close approaches")
    ck(abs(var_units(60) - MEAN_FACTOR) < 1e-9,
       "and at exactly 60 seconds the drift term vanishes")
    ck(var_units(10) < var_units(60) / 50,
       "ten seconds out it is %.0fx smaller than at sixty -- this is the pin"
       % (var_units(60) / max(var_units(10), 1e-12)))

    ck(abs(fair_value(100.0, 100.0, 300, 0.05) - 0.5) < 1e-9,
       "at the strike the fair value is exactly a half, whatever the vol")
    # THE FIRST VERSION OF THIS TEST ASSERTED > 0.99 AT sigma=0.05 AND FAILED.
    # The code was right and the expectation was wrong: five minutes out, a
    # 0.05/second walk has an 0.81 standard deviation at the close, so being a
    # dollar ahead is 1.24 sd and worth 0.89, not 0.99. Keeping the arithmetic
    # here because that is the whole reason this venue is hard -- at 300
    # seconds nothing is settled, and only the last minute collapses.
    ck(abs(fair_value(101.0, 100.0, 300, 0.05) - 0.8924) < 1e-3,
       "a dollar ahead at 300 s and 0.05/s vol is 1.24 sd, worth 0.89")
    hi = fair_value(101.0, 100.0, 300, 0.01)
    ck(hi > 0.99, "cut the vol fivefold and the same dollar is near certain "
                  "(%.4f)" % hi)
    ck(fair_value(99.0, 100.0, 300, 0.01) < 0.01,
       "and a dollar below is near hopeless -- the two sum to one")
    ck(abs(fair_value(101.0, 100.0, 300, 0.05)
           + fair_value(99.0, 100.0, 300, 0.05) - 1.0) < 1e-9,
       "exactly: YES at +1 and YES at -1 sum to 1.0")
    ck(fair_value(100.5, 100.0, 300, 5.0) < fair_value(100.5, 100.0, 300, 0.05),
       "NULL: raising the volatility drags a winning side back toward a half")

    # locked prints: 59 of 60 already recorded well above the strike
    f = fair_value(100.0, 100.0, 1, 1.0, locked_sum=59 * 110.0, locked_n=59)
    ck(f > 0.999, "with 59 of 60 prints locked far above the strike the answer "
                  "is settled (%.5f), which is exactly why the pin works" % f)

    class D:
        def __init__(self, v):
            self.v = v

        def get(self, s):
            return self.v.get(s)

    flat = D({s: 100.0 for s in range(0, 2000)})
    ck(per_second_sigma(flat, 2000) == 0.0, "a flat index has zero volatility")
    ck(per_second_sigma(D({1: 1.0}), 2000) is None,
       "NULL: too few prints returns nothing rather than a fake zero")
    print("cdcfair selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--edge", type=float, default=0.05,
                    help="minimum edge in dollars per contract to bet")
    ap.add_argument("--min-margin", type=float, default=5.0,
                    help="skip closes settling within this many basis points "
                         "of the strike -- our feed is not theirs")
    ap.add_argument("--max-tau", type=float, default=400.0)
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0

    insts = cdcedge.load_instruments()
    books = cdcedge.load_books()
    if not insts or not books:
        print("loaded nothing -- no CDNA tape yet")
        return 0
    idx = cdcedge.idxload.load(sorted({cdcedge.COIN_INDEX[r["base_ccy"]]
                                       for r in insts.values()
                                       if r.get("base_ccy") in cdcedge.COIN_INDEX}),
                               verbose=False)

    bets, skipped_margin, quotes = [], 0, 0
    for sym, snaps in books.items():
        r = insts.get(sym) or {}
        att = (r.get("event_details") or {}).get("attributes") or {}
        coin = r.get("base_ccy")
        iid = cdcedge.COIN_INDEX.get(coin)
        close = cdcedge.parse_close(att.get("CLOSE_TIME"))
        try:
            strike = float(att.get("STRIKE_PRICE"))
        except (TypeError, ValueError):
            continue
        if not iid or not close or iid not in idx:
            continue
        D = idx[iid]
        if close > (D.base + D.n) - 2:
            continue
        settle = cdcedge.settle_mean(D, close)
        if settle is None:
            continue
        margin_bp = 1e4 * abs(settle - strike) / strike
        yes_won = cdcedge.outcome(settle, strike, att.get("STRIKE_OPERATOR", ">"))
        if margin_bp < a.min_margin:
            skipped_margin += 1
            continue
        sigma = per_second_sigma(D, close)
        if not sigma:
            continue
        for ts, bk in snaps:
            if not ts:
                continue
            tau = close - ts / 1000.0
            if tau <= 0 or tau > a.max_tau:
                continue
            spot = D.get(int(ts / 1000))
            if spot is None:
                continue
            locked_n = max(0, int(N_AVG - tau)) if tau < N_AVG else 0
            locked_sum = 0.0
            if locked_n:
                got = [D.get(s) for s in range(close - N_AVG, close - N_AVG + locked_n)]
                if any(g is None for g in got):
                    continue
                locked_sum = sum(got)
            fair = fair_value(spot, strike, tau, sigma, locked_sum, locked_n)
            bids, asks = bk.get("bids") or [], bk.get("asks") or []
            quotes += 1
            if asks:
                ask = float(asks[0][0])
                if fair - ask >= a.edge:
                    bets.append((sym, coin, tau, "YES", ask, fair,
                                 (1.0 if yes_won else 0.0) - ask,
                                 float(asks[0][1]), close))
            if bids:
                bid = float(bids[0][0])
                if bid - fair >= a.edge:
                    bets.append((sym, coin, tau, "NO", round(1 - bid, 4), 1 - fair,
                                 (0.0 if yes_won else 1.0) - (1 - bid),
                                 float(bids[0][1]), close))

    print("\n%d quotes priced; %d closes skipped as too close to call "
          "(under %.0f bp)" % (quotes, skipped_margin, a.min_margin))
    if not bets:
        print("\nNo quote was mispriced by %.0f cents or more. Their pricing "
              "agrees with ours." % (100 * a.edge))
        return 0

    print("\n%-26s %-5s %6s %5s %7s %7s %8s %8s"
          % ("contract", "coin", "t-left", "side", "paid", "fair", "P&L", "size"))
    print("  " + "-" * 82)
    for sym, coin, tau, side, paid, fair, pnl, size, _ in sorted(bets, key=lambda b: -b[2])[:30]:
        print("%-26s %-5s %5.0fs %5s %7.2f %7.2f %+8.2f %8.0f"
              % (sym.replace("NX.F.OPT.", "")[:26], coin, tau, side, paid,
                 fair, pnl, size))

    won = sum(1 for b in bets if b[6] > 0)
    tot = sum(b[6] for b in bets)
    print("\n  %d bets, %d won, %d lost." % (len(bets), won, len(bets) - won))
    print("  Total profit at one contract each: $%+.2f  (average %+.1f cents "
          "a contract)" % (tot, 100 * tot / len(bets)))

    # HARD RULE 4: CLUSTER BY CLOSE. Nine of those "bets" can be the same
    # contract re-quoted nine times three seconds apart. They share one
    # settlement, so counting them as nine independent wins inflates both the
    # hit rate and any interval built on it. One number per close.
    per = {}
    for sym, coin, tau, side, paid, fair, pnl, size, close in bets:
        per.setdefault(sym, []).append(pnl)
    means = [sum(v) / len(v) for v in per.values()]
    cwon = sum(1 for m in means if m > 0)
    print("\n  CLUSTERED BY CLOSE, which is the only count that means anything:")
    print("  %d closes, %d profitable, %d not. Average per close %+.1f cents."
          % (len(means), cwon, len(means) - cwon,
             100 * sum(means) / len(means)))
    # sign test against a fair coin: how surprising is cwon of len(means)?
    n, k = len(means), cwon
    p = sum(math.comb(n, i) for i in range(k, n + 1)) / (2.0 ** n)
    print("  If the venue were priced correctly and we were guessing, %d or"
          % k)
    print("  more profitable closes out of %d happens with probability %.4g."
          % (n, p))
    if p > 0.05:
        print("  That is NOT significant. This is a promising shape, not a result.")
    else:
        print("  The direction is unlikely to be chance. The SIZE of the edge")
        print("  is still an upper bound for the fill reason below.")
    mins = sorted(means)[:3]
    print("  Worst three closes: %s"
          % ", ".join("%+.0fc" % (100 * m) for m in mins))

    # WHAT FEE KILLS IT. This is the single most decision-relevant number we
    # can produce without trading access. CDNA's fee schedule is unknown and
    # Nadex historically billed a FLAT amount per contract at trade and again
    # at settlement -- flat in notional, which on a contract that pays at most
    # one dollar is enormous. Kalshi charges 0.07*p*(1-p), about a fifth of a
    # cent on a 97c contract. If the break-even fee here is below whatever
    # CDNA charges, no amount of access or engineering makes this work, and
    # that is worth knowing before anyone builds an order client.
    def clustered(fee):
        d = {}
        for sym, coin, tau, side, paid, fair, pnl, size, close in bets:
            d.setdefault(sym, []).append(pnl - fee)
        m = [sum(v) / len(v) for v in d.values()]
        return sum(m) / len(m), sum(1 for x in m if x > 0), len(m)

    print("\n  BREAK-EVEN FEE -- charged per contract, once each way:")
    print("  %-14s %14s %14s" % ("fee/contract", "cents per close", "closes ahead"))
    print("  " + "-" * 46)
    breakeven = None
    for cents in (0, 1, 2, 3, 4, 5, 6, 8, 10):
        avg, wins, n = clustered(2 * cents / 100.0)
        print("  %-14s %13.1fc %10d of %d"
              % ("%dc" % cents, 100 * avg, wins, n))
        if breakeven is None and avg <= 0:
            breakeven = cents
    if breakeven:
        print("\n  The edge dies at about %dc a contract each way." % breakeven)
    else:
        print("\n  Still positive at 10c a contract each way.")
    print("  For scale, Kalshi charges us about 0.2c on a 97c contract.")

    # HOLDOUT. CLAUDE.md: no threshold is deployed from a replay without a
    # split. Closes are ordered by time and cut in half; the edge threshold is
    # chosen on the first half and scored on the second, which it has not seen.
    order = sorted({(c, s) for s, _, _, _, _, _, _, _, c in bets})
    if len(order) >= 20:
        cut = order[len(order) // 2][0]
        print("\n  HOLDOUT, first half of the day against the second:")
        print("  %-10s %18s %18s" % ("min edge", "early (cents/close)",
                                     "late (cents/close)"))
        print("  " + "-" * 50)
        for thr in (0.03, 0.05, 0.08, 0.12, 0.20):
            halves = []
            for early in (True, False):
                d = {}
                for sym, coin, tau, side, paid, fair, pnl, size, close in bets:
                    if abs(fair - paid) < thr:
                        continue
                    if (close < cut) != early:
                        continue
                    d.setdefault(sym, []).append(pnl)
                m = [sum(v) / len(v) for v in d.values()]
                halves.append((100 * sum(m) / len(m), len(m)) if m else (0.0, 0))
            print("  %-10s %12.1fc n=%-4d %12.1fc n=%-4d"
                  % ("%.0fc" % (100 * thr), halves[0][0], halves[0][1],
                     halves[1][0], halves[1][1]))
        print("  A threshold that only works in one half is a fitted number,")
        print("  not an edge.")
    print("\n  THIS IS AN UPPER BOUND, not a forecast. Every bet is a fill at a")
    print("  price we merely SAW quoted; a maker about to be picked off cancels,")
    print("  and hard rule: our live loss rate has run 31x the tape's before.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
