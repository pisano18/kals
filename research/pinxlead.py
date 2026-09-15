#!/usr/bin/env python3
"""pinxlead.py -- does one coin's settlement index move BEFORE another's?

WHY. The hedge is the one thing that reliably cuts a loss, and its value is in
its SPEED: on the tape's 25 losing markets, hedging at the first crack instead
of one tier later is worth a mean 16.7c per rescued contract. Twelve coins
settle on the same second at rho ~0.8. If BTC's index cracks a second or two
before HYPE's, a HYPE position could be hedged on BTC's crack -- before HYPE's
own belief has moved -- and get that earlier price. IDEAS_LOG #19 and
FACTOR_PROGRAMME #22 both name this; nobody has measured it.

SOURCE. `cfbenchmarks_value` -- the 1-per-second settlement index, via
idxload's dense arrays. Index only: no order book, no replay, no fills, no
P&L. This asks what the INDEX did, which is what the tape is valid for.

TWO TESTS.
  1. LEAD-LAG. In the final 60 s of every close, correlate alt X's one-second
     return at t with BTC's at t-k for k = -5..+5. A POSITIVE peak lag means
     X follows BTC by k seconds. One correlation per close, aggregated across
     closes (hard rule 4).
  2. WARNING. At every second where X JUMPS (|return| > 3 sd of its own last
     300 s), what had BTC done in the 3 s before? Against BTC's behaviour at
     random non-jump seconds. If BTC has usually already moved, it is a
     warning; if not, X's jump is news to BTC too.

SELF-TEST plants X = BTC delayed 2 s + noise (peak must be +2), X independent
of BTC (peak ~0, r ~0, CI covers 0), and X == BTC (peak 0, r = 1).

    python research/pinxlead.py --selftest
    python research/pinxlead.py                # all closes on disk
    python research/pinxlead.py --hours 120    # newest 120 hour-files
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import idxload                                            # noqa: E402

COINS = {
    "BRTI": "BTC", "ETHUSD_RTI": "ETH", "SOLUSD_RTI": "SOL",
    "XRPUSD_RTI": "XRP", "DOGEUSD_RTI": "DOGE", "BNBUSD_RTI": "BNB",
    "ZECUSD_RTI": "ZEC", "HYPEUSD_RTI": "HYPE", "NEARUSD_RTI": "NEAR",
}
LEADER = "BRTI"
LAGS = list(range(-5, 6))
WIN = 60            # the settlement window
MIN_PTS = 45        # returns needed in a window to score it


def returns(d, a, b):
    """{second: log return} for seconds in [a, b] where both prints exist."""
    out = {}
    prev = d.get(a - 1)
    for s in range(a, b + 1):
        v = d.get(s)
        if v is not None and prev is not None and v > 0 and prev > 0:
            out[s] = math.log(v / prev)
        prev = v
    return out


def corr(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def lag_corrs(r_lead, r_x, a, b):
    """corr(r_x[t], r_lead[t-k]) for each k, over t in [a, b]. None if thin."""
    out = {}
    for k in LAGS:
        xs, ys = [], []
        for t in range(a, b + 1):
            if t in r_x and (t - k) in r_lead:
                xs.append(r_lead[t - k])
                ys.append(r_x[t])
        if len(xs) < MIN_PTS:
            return None
        c = corr(xs, ys)
        if c is None:
            return None
        out[k] = c
    return out


def closes_in(dense):
    """Every 15-minute close boundary the grid covers."""
    lo = dense.base
    hi = dense.base + dense.n - 1
    first = (lo // 900 + 1) * 900
    return list(range(first, hi + 1, 900))


def boot_mean(vals, n=2000, seed=3):
    rnd = random.Random(seed)
    k = len(vals)
    if k < 2:
        return (0.0, 0.0)
    ms = sorted(sum(vals[rnd.randrange(k)] for _ in range(k)) / k for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n)]


def leadlag(idx, closes, lead=LEADER):
    """{coin: {k: [corr per close]}}"""
    res = {}
    L = idx.get(lead)
    if L is None:
        return res
    for iid, D in idx.items():
        if iid == lead:
            continue
        per = {k: [] for k in LAGS}
        for c in closes:
            a, b = c - WIN, c - 1
            rl = returns(L, a - 6, b)
            rx = returns(D, a, b)
            lc = lag_corrs(rl, rx, a, b)
            if lc is None:
                continue
            for k in LAGS:
                per[k].append(lc[k])
        res[iid] = per
    return res


def warning(idx, closes, lead=LEADER, before=3, z=3.0, seed=11):
    """At each alt jump in a settlement window: BTC's cumulative return over
    the `before` seconds prior, in units of BTC's own sd. Versus the same
    quantity at random non-jump seconds in the same windows."""
    rnd = random.Random(seed)
    L = idx.get(lead)
    out = {}
    if L is None:
        return out
    for iid, D in idx.items():
        if iid == lead:
            continue
        jumps, base = [], []
        for c in closes:
            a, b = c - WIN, c - 1
            rx = returns(D, a - 300, b)
            rl = returns(L, a - 300, b)
            hist = [rx[s] for s in range(a - 300, a) if s in rx]
            histl = [rl[s] for s in range(a - 300, a) if s in rl]
            if len(hist) < 200 or len(histl) < 200:
                continue
            sdx = math.sqrt(sum(v * v for v in hist) / len(hist))
            sdl = math.sqrt(sum(v * v for v in histl) / len(histl))
            if sdx <= 0 or sdl <= 0:
                continue

            def btc_before(t):
                vals = [rl.get(t - i) for i in range(1, before + 1)]
                if any(v is None for v in vals):
                    return None
                return sum(vals) / (sdl * math.sqrt(before))

            for t in range(a, b + 1):
                r = rx.get(t)
                if r is None:
                    continue
                if abs(r) > z * sdx:
                    bb = btc_before(t)
                    if bb is not None:
                        # signed the SAME way as X's jump
                        jumps.append(bb * (1 if r > 0 else -1))
            # baseline: 3 random non-jump seconds per window
            cand = [t for t in range(a, b + 1)
                    if t in rx and abs(rx[t]) <= z * sdx]
            for t in rnd.sample(cand, min(3, len(cand))):
                bb = btc_before(t)
                if bb is not None:
                    base.append(abs(bb))
        out[iid] = (jumps, base)
    return out


# ---------------------------------------------------------------------------
def _fake(iid, base, n, vals):
    d = idxload.Dense(iid, base, n)
    for i, v in enumerate(vals):
        d.v[i] = v
    return d


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    rnd = random.Random(1)
    base = 1_789_000_000 - (1_789_000_000 % 900)
    n = 900 * 30 + 400                        # thirty closes
    # a leader: random walk
    lead = [100.0]
    for _ in range(n - 1):
        lead.append(lead[-1] * math.exp(rnd.gauss(0, 2e-4)))
    # X delayed 2 s + small noise; Y independent; Z identical
    x = [lead[max(0, i - 2)] * math.exp(rnd.gauss(0, 5e-5)) for i in range(n)]
    y = [100.0]
    for _ in range(n - 1):
        y.append(y[-1] * math.exp(rnd.gauss(0, 2e-4)))
    idx = {"BRTI": _fake("BRTI", base, n, lead),
           "XUSD_RTI": _fake("X", base, n, x),
           "YUSD_RTI": _fake("Y", base, n, y),
           "ZUSD_RTI": _fake("Z", base, n, list(lead))}
    closes = closes_in(idx["BRTI"])
    res = leadlag(idx, closes)
    mean = {iid: {k: sum(v) / len(v) for k, v in per.items() if v}
            for iid, per in res.items()}
    px = max(mean["XUSD_RTI"], key=mean["XUSD_RTI"].get)
    ck(px == 2, "PLANTED: X delayed 2 s behind BTC -> peak lag recovered at +%d" % px)
    pz = max(mean["ZUSD_RTI"], key=mean["ZUSD_RTI"].get)
    ck(pz == 0 and mean["ZUSD_RTI"][0] > 0.99,
       "identical series -> peak at 0 with r = %.3f" % mean["ZUSD_RTI"][0])
    # NULL. Do NOT pick the largest |r| and then test it -- the maximum of
    # eleven noisy correlations excludes zero even when nothing is there, and
    # the first version of this test failed on exactly that. The claim that
    # matters is "no lead at the lags a hedge could act on", so test the
    # PRE-SPECIFIED lags +1 and +2, and require |r| small everywhere.
    big = max(abs(mean["YUSD_RTI"][k]) for k in LAGS)
    lo1, hi1 = boot_mean(res["YUSD_RTI"][1])
    lo2, hi2 = boot_mean(res["YUSD_RTI"][2])
    ck(big < 0.15 and lo1 <= 0 <= hi1 and lo2 <= 0 <= hi2,
       "NULL: an independent coin shows no lead (largest |r| over all lags = %.3f; "
       "the +1 and +2 intervals both cover 0)" % big)
    # and X's off-peak lags must not also look like leads
    ck(all(mean["XUSD_RTI"][k] < 0.5 for k in LAGS if k != 2),
       "a planted +2 lead does NOT smear onto neighbouring lags")
    print("pinxlead selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0
    hours = None
    if "--hours" in sys.argv:
        hours = int(sys.argv[sys.argv.index("--hours") + 1])
    idx = idxload.load(list(COINS), hours=hours, verbose=True)
    idx = {k: v for k, v in idx.items() if v is not None and v.n > 0}
    if LEADER not in idx:
        print("loaded nothing -- no BTC index on disk")
        return 0
    closes = closes_in(idx[LEADER])
    print("\n%d close windows on the grid\n" % len(closes))

    print("1. LEAD-LAG in the final 60 s: corr(alt return at t, BTC return at t-k)")
    print("   positive peak = the alt FOLLOWS BTC by k seconds. One r per close, mean over closes.\n")
    print("   %-5s %6s %s %10s" % ("coin", "closes", " ".join("%6s" % ("k=%+d" % k) for k in LAGS), "peak"))
    res = leadlag(idx, closes)
    for iid, per in sorted(res.items(), key=lambda kv: COINS.get(kv[0], kv[0])):
        if not per[0]:
            continue
        mean = {k: sum(v) / len(v) for k, v in per.items()}
        pk = max(mean, key=mean.get)
        lo, hi = boot_mean(per[pk])
        flag = ""
        if pk > 0 and lo > mean[0] * 0.0 and lo > 0.05:
            flag = "  <-- BTC leads?"
        print("   %-5s %6d %s %+3d (r=%.3f, 95%% [%.3f,%.3f])%s"
              % (COINS.get(iid, iid), len(per[0]),
                 " ".join("%+6.3f" % mean[k] for k in LAGS), pk, mean[pk], lo, hi, flag))

    print("\n2. WARNING: when an alt JUMPS (>3 sd in one second), had BTC already moved?")
    print("   BTC's move over the 3 s before, in BTC sd units, signed like the jump.")
    print("   Compare to |BTC move| before random calm seconds.\n")
    print("   %-5s %6s %12s %12s %14s" % ("coin", "jumps", "BTC before", "calm base", "share >= +1sd"))
    w = warning(idx, closes)
    for iid, (jumps, base) in sorted(w.items(), key=lambda kv: COINS.get(kv[0], kv[0])):
        if len(jumps) < 10 or len(base) < 10:
            continue
        mj = sum(jumps) / len(jumps)
        mb = sum(base) / len(base)
        sh = sum(1 for j in jumps if j >= 1.0) / len(jumps)
        shb = sum(1 for b in base if b >= 1.0) / len(base)
        print("   %-5s %6d %+11.2f %12.2f %7.0f%% vs %3.0f%%"
              % (COINS.get(iid, iid), len(jumps), mj, mb, 100 * sh, 100 * shb))
    print("\n   'BTC before' near 0 with the share matching baseline means the alt's jump")
    print("   was news to BTC too -- no warning to be had. A share well above baseline")
    print("   means BTC usually moved first, and a cross-coin hedge trigger has something")
    print("   to work with. Either way this is the index alone, not a trading result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
