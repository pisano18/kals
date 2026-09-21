#!/usr/bin/env python3
"""raceclose.py -- the last twenty seconds of a Coin Race, and what is resting
there.

WHY THIS BAND AND NOT THE ONE WE TRADE. `racemaker.py` split seven days of
Coin Race trades by time to close and the answer was not subtle:

    tau 1-15s   every taker who bought a leg at 85c+ won.  2,109 contracts,
                100.0%, +2c to +13c a contract after fees.
    tau 16-30s  the same purchase lost 13.8c a contract.  Win rate 81%.

The live race arm trades tau <= 30, which straddles both. The 16-30 band is
where a photo finish is still resolving: a leg quoted 94c there won 64% of the
time. Inside 15 seconds the index has already decided -- 59 of the 60
settlement prints are on disk at tau 1 -- and the quote has not caught up.

So this file asks one question: HOW MUCH IS RESTING IN THAT WINDOW? The trade
tape only shows what somebody else took. The ticker shows the offer itself,
with its size, whether or not anyone lifted it. That is the capacity of the
trade, and capacity is the only thing that decides whether this is $2 a day or
$60 a day.

NO LOOK-AHEAD. The leg bought at tau is the leg the MODEL calls the leader
using only prints at or before second close-tau -- never the settled winner.
Scoring uses the winner; choosing never does. The first version of the Coin
Race measurement scored every purchase against a tau-20 forecast and turned
89.4% into 98.9%.

WHAT THIS IS NOT. An offer that was resting is not a fill. This project has
already proved the gap is not small: at the pin gate the tape said 0.11% loss
and our own fills said 3.4%, a 31x difference, because "an offer was sitting
there" and "someone sold it to us" are different populations. Everything here
is a CEILING and is labelled as one. Our loss rate comes from our fills.

    python research/raceclose.py --selftest
    python research/raceclose.py --hours 240
"""
import argparse
import collections
import datetime as dt
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")

import racebook                                                # noqa: E402

COINS = racebook.COINS
WINDOW = racebook.WINDOW
MAXAGE = 30


def leader_at(M, idx, close, tau):
    """(coin, lead_bp) the model calls the leader at `tau`, or (None, None).

    Reads only prints at or before close - tau: M.returns_at imputes the
    prints still to come at the newest one, exactly as pin does."""
    rets = M.returns_at(idx, close, tau)
    if len(rets) < len(COINS):
        return None, None
    order = sorted(rets.items(), key=lambda kv: kv[1], reverse=True)
    lead = (order[0][1] - order[1][1]) * 1e4
    return order[0][0], lead


def buy_at(fresh, coin, max_price, cap):
    """(price, contracts) we could lift on `coin`, or None.

    `fresh` is racebook's per-second top of book. An ask of 1.0000 with size
    zero is the empty-book print, not a dollar offer."""
    q = fresh.get(coin)
    if q is None:
        return None
    _bid, ask, _bsz, asz = q
    if not (0.0 < ask <= max_price) or asz <= 0:
        return None
    n = min(asz, cap)
    if n < 1:
        return None
    return ask, n


def simulate(races, M, idx, tau_lo, tau_hi, max_price, cap, min_lead_bp=0.0):
    """One buy per race: the first second, counting DOWN from tau_hi, where the
    model's leader is offered at or below `max_price`.

    Counting down means the earliest chance inside the band, which is the one
    we would actually get -- taking the LAST one before the close is the
    cheapest and most informed print and is how this product was first
    over-measured (`min()` where `max()` was meant)."""
    out = []
    for close, stamp, rows in races:
        st = racebook.scan_race(rows, close, tau_lo=tau_lo, tau_hi=tau_hi,
                                max_age=MAXAGE)
        by_tau = {t: f for t, f in st}
        rets = M.returns_at(idx, close, 0)
        if len(rets) < len(COINS):
            continue
        winner = max(rets, key=rets.get)
        for tau in range(tau_hi, tau_lo - 1, -1):
            fresh = by_tau.get(tau)
            if not fresh:
                continue
            coin, lead = leader_at(M, idx, close, tau)
            if coin is None or lead < min_lead_bp:
                continue
            got = buy_at(fresh, coin, max_price, cap)
            if got is None:
                continue
            price, n = got
            won = (coin == winner)
            pnl = n * ((1.0 - price) if won else -price) \
                - racebook.order_fee(n, price)
            out.append((close, stamp, tau, coin, price, n, won, pnl, lead))
            break
    return out


def simulate_fair(races, M, F, idx, tau_lo, tau_hi, cap, min_edge,
                  ruler="3600", kappa=1.0, max_price=0.99, lag=0):
    """THE WHOLE STRATEGY, with the forecast as the only gate.

    No price floor, no tau band inside the window, no "leader" rule. At each
    second, every leg that is OFFERED is priced against `pinracefair`'s
    probability, and the best one is bought if

        fair - ask - fee  >=  min_edge

    ONE POSITION PER RACE, always. That single rule is what 2026-09-15 cost:
    the old arm took up to 17 legs in one race and bought YES and NO on the
    same ticker as the lead flipped, locking in $1,306 of loss before any
    race was decided. At most one leg can win, so a second position in the
    same race is not diversification, it is a guaranteed loser.

    `lag` stales the forecast, the look-ahead control."""
    out = []
    ser_cache, fcache = {}, {}

    def fair(close, tau):
        k = (close, tau)
        if k not in fcache:
            if close not in ser_cache:
                ser_cache.clear()
                fcache.clear()
                ser_cache[close] = F.RaceSeries(idx, close)
            pr, _ = F.fair_at(idx, ser_cache[close], close, tau, ruler, (kappa,))
            fcache[k] = pr[kappa] if pr else None
        return fcache[k]

    for close, stamp, rows in races:
        rets = M.returns_at(idx, close, 0)
        if len(rets) < len(COINS):
            continue
        winner = max(rets, key=rets.get)
        st = racebook.scan_race(rows, close, tau_lo=tau_lo, tau_hi=tau_hi,
                                max_age=MAXAGE)
        by_tau = {t: f for t, f in st}
        for tau in range(tau_hi, tau_lo - 1, -1):
            fresh = by_tau.get(tau)
            if not fresh:
                continue
            p = fair(close, max(tau + lag, 1))
            if p is None:
                continue
            best = None
            for coin in COINS:
                q = fresh.get(coin)
                if q is None:
                    continue
                ask, asz = q[1], q[3]
                if not (0.0 < ask <= max_price) or asz < 1:
                    continue
                edge = p[coin] - ask - racebook.order_fee(1, ask)
                if best is None or edge > best[0]:
                    best = (edge, coin, ask, asz)
            if best is None or best[0] < min_edge:
                continue
            _edge, coin, ask, asz = best
            n = min(asz, cap)
            if n < 1:
                continue
            won = (coin == winner)
            pnl = n * ((1.0 - ask) if won else -ask) \
                - racebook.order_fee(n, ask)
            out.append((close, stamp, tau, coin, ask, n, won, pnl,
                        100.0 * _edge))
            break                       # ONE POSITION PER RACE. Never relax.
    return out


def report(bets, label, days):
    if not bets:
        print("  %-30s %8s" % (label, "none"))
        return
    n = len(bets)
    cts = sum(b[5] for b in bets)
    won = sum(1 for b in bets if b[6])
    pnl = sum(b[7] for b in bets)
    avgp = sum(b[4] * b[5] for b in bets) / cts
    print("  %-30s %6d %7.0f %7d %7.1fc %+8.2fc %+9.2f %+8.2f"
          % (label, n, cts, n - won, 100 * avgp, 100 * pnl / cts, pnl,
             pnl / days if days else 0))


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    ck(buy_at({"BTC": (0.9, 0.95, 10, 40)}, "BTC", 0.98, 100) == (0.95, 40),
       "a 95c offer of 40 under a 98c cap and a 100 cap lifts 40 at 95c")
    ck(buy_at({"BTC": (0.9, 0.95, 10, 40)}, "BTC", 0.98, 25) == (0.95, 25),
       "and the position cap binds when it is the smaller")
    ck(buy_at({"BTC": (0.9, 0.99, 10, 40)}, "BTC", 0.98, 100) is None,
       "an offer above the price cap is refused")
    ck(buy_at({"BTC": (0.9, 1.0, 10, 0)}, "BTC", 1.0, 100) is None,
       "ask 1.0000 with size 0 -- the empty book -- is not an offer")
    ck(buy_at({"BTC": (0.9, 0.95, 10, 0.4)}, "BTC", 0.98, 100) is None,
       "a sub-contract offer is refused rather than rounded up")
    ck(buy_at({}, "BTC", 0.98, 100) is None, "a leg with no quote at all is refused")
    ck(racebook.order_fee(1, 0.80) > 0,
       "a purchase at 80c is charged a fee, so an 'edge' never ignores it")

    # a planted race, end to end, with a KNOWN answer
    import idxload
    import pinracemodel as M
    stamp = "26SEP210100"
    close = racebook.close_of(stamp)
    idx = {}
    for name, iid in M.COINS.items():
        D = idxload.Dense(iid, close - WINDOW - M.N_AVG - 10, WINDOW + 200)
        for s in range(close - WINDOW - M.N_AVG - 10, close + 100):
            # every coin flat at 100 except BTC, which rises through the window
            lvl = 100.0
            if name == "BTC" and s >= close - WINDOW:
                lvl = 100.0 + 0.5 * min(1.0, (s - (close - WINDOW)) / float(WINDOW))
            D.v[s - D.base] = lvl
        D.hi_used = -1
        idx[iid] = D
    coin, lead = leader_at(M, idx, close, 10)
    ck(coin == "BTC" and lead > 0,
       "PLANTED: the one coin that rose is named the leader at tau 10 (%s, %.1fbp)"
       % (coin, lead if lead else -1))
    rows = []
    for sec in range(close - 60, close):
        for c in COINS:
            b, a = (0.90, 0.95) if c == "BTC" else (0.00, 0.02)
            rows.append((sec * 1000, stamp, c, b, a, 30.0, 30.0))
    bets = simulate([(close, stamp, rows)], M, idx, 1, 15, 0.98, 100)
    ck(len(bets) == 1 and bets[0][6] and bets[0][2] == 15,
       "one buy per race, taken at the EARLIEST second in the band (tau %s), "
       "and it wins" % (bets[0][2] if bets else "-"))
    ck(abs(bets[0][7] - (30 * 0.05 - racebook.order_fee(30, 0.95))) < 1e-12,
       "30 contracts at 95c on a winner pays 30*5c less fee = $%.2f" % bets[0][7])

    # NULL: the offer is above the cap everywhere -> no bet at all
    rows2 = [(r[0], r[1], r[2], r[3], 0.995 if r[2] == "BTC" else r[4], r[5], r[6])
             for r in rows]
    ck(simulate([(close, stamp, rows2)], M, idx, 1, 15, 0.98, 100) == [],
       "NULL: with the leader offered at 99.5c and a 98c cap, nothing is bought")

    # a LOSING world: the leader at tau is not the winner
    idx2 = {}
    for name, iid in M.COINS.items():
        D = idxload.Dense(iid, close - WINDOW - M.N_AVG - 10, WINDOW + 200)
        for s in range(close - WINDOW - M.N_AVG - 10, close + 100):
            lvl = 100.0
            if name == "BTC" and s >= close - WINDOW:
                lvl = 100.3
            if name == "ETH" and s >= close - 8:
                lvl = 140.0                       # ETH explodes in the last 8 s
            D.v[s - D.base] = lvl
        D.hi_used = -1
        idx2[iid] = D
    b2 = simulate([(close, stamp, rows)], M, idx2, 1, 15, 0.98, 100)
    ck(len(b2) == 1 and not b2[0][6] and b2[0][7] < 0,
       "a leader that is overtaken after the purchase is scored as a LOSS "
       "($%.2f) -- the estimator can lose" % (b2[0][7] if b2 else 0))
    ck(abs(b2[0][7] + (30 * 0.95 + racebook.order_fee(30, 0.95))) < 1e-12,
       "and the loss is the full price plus the fee, never netted")

    # ---- simulate_fair: the one-position-per-race rule is the whole point ---
    import pinracefair as F
    close2 = close + 20 * WINDOW
    idx3 = {}
    rng = __import__("random").Random(11)
    for name, iid in M.COINS.items():
        lo = close2 - WINDOW - M.N_AVG - 4000
        D = idxload.Dense(iid, lo, WINDOW + 4200)
        lvl = 100.0
        for s in range(lo, close2 + 100):
            lvl *= 1.0 + rng.gauss(0, 1e-5)
            if name == "BTC" and s >= close2 - WINDOW:
                lvl *= 1.00002                    # BTC drifts clearly ahead
            D.v[s - D.base] = lvl
        D.hi_used = -1
        idx3[iid] = D
    rows3 = []
    for sec in range(close2 - 90, close2):
        for c in COINS:
            b, a = (0.80, 0.85) if c == "BTC" else (0.00, 0.03)
            rows3.append((sec * 1000, stamp, c, b, a, 50.0, 50.0))
    r3 = [(close2, stamp, rows3)]
    bets3 = simulate_fair(r3, M, F, idx3, 1, 60, 100, 0.0)
    ck(len(bets3) == 1,
       "ONE POSITION PER RACE: 60 qualifying seconds x 5 legs produce exactly "
       "one bet (%d)" % len(bets3))
    ck(bets3 and bets3[0][3] == "BTC" and bets3[0][6],
       "and it is the leg the forecast likes, and it wins")
    ck(simulate_fair(r3, M, F, idx3, 1, 60, 100, 0.99) == [],
       "NULL: demand 99c of edge and nothing is ever bought")
    ck(simulate_fair(r3, M, F, idx3, 1, 60, 100, 0.0, max_price=0.02) == [],
       "a price ceiling below every offer buys nothing")
    dear = [(r[0], r[1], r[2], r[3], 0.999, r[5], r[6]) for r in rows3]
    ck(simulate_fair([(close2, stamp, dear)], M, F, idx3, 1, 60, 100, 0.0) == [],
       "with every leg offered at 99.9c there is no edge anywhere and it "
       "stands aside rather than buying the least-bad")

    if not racebook.selftest():
        ck(False, "racebook (the shared reader) self-test")
    print("raceclose selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=racebook.DATA)
    ap.add_argument("--hours", type=int, default=0)
    ap.add_argument("--cap", type=float, default=1e9,
                    help="contracts per race (1e9 = whatever is resting)")
    ap.add_argument("--fair", action="store_true",
                    help="run the forecast-gated strategy (slow)")
    ap.add_argument("--ruler", default="3600")
    ap.add_argument("--kappa", type=float, default=1.0)
    ap.add_argument("--lag", type=int, default=0,
                    help="stale the forecast N seconds -- the look-ahead control")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if not selftest():
        return 1
    if a.selftest:
        return 0

    files = sorted(glob.glob(os.path.join(a.data, "ticker", "*.jsonl.gz")))
    if a.hours:
        files = files[-a.hours:]
    if not files:
        print("loaded nothing -- no ticker files")
        return 0
    cand, got = racebook.parse_rate(files)
    print("\n%d ticker files; parser check %d/%d (%.1f%%)"
          % (len(files), got, cand, 100.0 * got / cand if cand else 0))
    if cand and got < 0.95 * cand:
        print("REFUSING TO REPORT -- ticker wire format moved")
        return 1

    by_race = collections.defaultdict(list)
    for k, fp in enumerate(files):
        for r in racebook.cached_hour(fp):
            by_race[r[1]].append(r)
        if (k + 1) % 100 == 0:
            print("  ... %d/%d files" % (k + 1, len(files)), flush=True)
    races = []
    for stamp, rows in by_race.items():
        c = racebook.close_of(stamp)
        if c is None or len({r[2] for r in rows}) < len(COINS):
            continue
        races.append((c, stamp, rows))
    races.sort()
    if len(races) < 30:
        print("loaded nothing -- %d complete races" % len(races))
        return 0

    import idxload
    import pinracemodel as M
    idx = idxload.load(sorted(set(M.COINS.values())), verbose=False)
    if not idx or idx.get("BRTI") is None:
        print("loaded nothing -- no index on disk")
        return 0
    lo = min(r[0] for r in races)
    races = [r for r in races if M.returns_at(idx, r[0], 0)]
    if not races:
        print("loaded nothing -- no race has index coverage")
        return 0
    days = (races[-1][0] - races[0][0]) / 86400.0
    print("  %d races with all five legs quoting AND index coverage, %.1f days"
          % (len(races), days))
    del lo

    print("\n## WHAT IS RESTING ON THE LEADER, BY SECOND")
    print("The model's leader at that second (no look-ahead), and the offer")
    print("sitting on it. 'offered' counts races where an ask existed at all.")
    print("  %5s %8s %9s %9s %9s %9s %9s"
          % ("tau", "races", "offered", "med ask", "med size", "p90 size", "ask<98c"))
    for tau in (1, 2, 3, 5, 8, 10, 12, 15, 20, 25, 30, 45, 60):
        n = off = cheap = 0
        asks, sizes = [], []
        for close, stamp, rows in races:
            st = racebook.scan_race(rows, close, tau_lo=tau, tau_hi=tau,
                                    max_age=MAXAGE)
            if not st:
                continue
            fresh = st[0][1]
            coin, _lead = leader_at(M, idx, close, tau)
            if coin is None:
                continue
            n += 1
            q = fresh.get(coin)
            if q and q[3] > 0 and 0 < q[1] < 1.0:
                off += 1
                asks.append(q[1])
                sizes.append(q[3])
                if q[1] <= 0.98:
                    cheap += 1
        if not n:
            continue

        def q(v, p):
            if not v:
                return float("nan")
            v = sorted(v)
            return v[max(0, min(len(v) - 1, int(p * (len(v) - 1) + 0.5)))]
        print("  %5d %8d %8d%% %8.1fc %9.0f %9.0f %8d%%"
              % (tau, n, int(100.0 * off / n), 100 * q(asks, 0.5), q(sizes, 0.5),
                 q(sizes, 0.9), int(100.0 * cheap / n)))

    print("\n## BUYING THE LEADER, ONE PER RACE, SCORED ON THE REAL WINNER")
    print("  %-30s %6s %7s %7s %8s %9s %10s %9s"
          % ("rule", "races", "contr", "losses", "avg paid", "c/contract",
             "total $", "$/day"))
    for tau_lo, tau_hi in ((1, 15), (1, 20), (1, 10), (16, 30), (1, 30)):
        for mp in (0.97, 0.98):
            bets = simulate(races, M, idx, tau_lo, tau_hi, mp, a.cap)
            report(bets, "tau %d-%d, ask <= %.0fc" % (tau_lo, tau_hi, 100 * mp),
                   days)
        print("  %s" % ("-" * 96))

    print("\n## THE MINIMUM LEAD FILTER -- the one thing every loss had in common")
    print("A lead of 0.2 basis points at tau 15 is a photo finish, not a lead.")
    print("Stand aside unless the model's leader is ahead by at least:")
    print("  %-30s %6s %7s %7s %8s %9s %10s %9s"
          % ("rule", "races", "contr", "losses", "avg paid", "c/contract",
             "total $", "$/day"))
    for tau_lo, tau_hi in ((1, 15), (1, 20), (1, 30)):
        for lead in (0.0, 0.5, 1.0, 2.0, 4.0):
            bets = simulate(races, M, idx, tau_lo, tau_hi, 0.98, a.cap,
                            min_lead_bp=lead)
            report(bets, "tau %d-%d, lead >= %.1fbp" % (tau_lo, tau_hi, lead), days)
        print("  %s" % ("-" * 96))

    print("\n## AND AT A SIZE THE BOOK CAN ACTUALLY ABSORB  (lead >= 1bp)")
    print("  %-30s %6s %7s %7s %8s %9s %10s %9s"
          % ("rule", "races", "contr", "losses", "avg paid", "c/contract",
             "total $", "$/day"))
    for tau_lo, tau_hi in ((1, 15), (1, 20), (1, 30)):
        for cap in (20, 50, 100):
            bets = simulate(races, M, idx, tau_lo, tau_hi, 0.98, cap,
                            min_lead_bp=1.0)
            report(bets, "tau %d-%d, cap %d" % (tau_lo, tau_hi, cap), days)
        print("  %s" % ("-" * 96))

    print("\n## THE SAME RULE AT A REAL POSITION SIZE  (tau 1-15, ask <= 98c)")
    print("  %-30s %6s %7s %7s %8s %9s %10s %9s"
          % ("cap per race", "races", "contr", "losses", "avg paid",
             "c/contract", "total $", "$/day"))
    for cap in (10, 20, 50, 100, 200):
        bets = simulate(races, M, idx, 1, 15, 0.98, cap)
        report(bets, "%d contracts" % cap, days)

    print("\n## THE LOSSES, EVERY ONE  (tau 1-20, ask <= 98c, uncapped, no lead filter)")
    bets = simulate(races, M, idx, 1, 20, 0.98, a.cap)
    losses = [b for b in bets if not b[6]]
    print("  %d losing races of %d" % (len(losses), len(bets)))
    for b in sorted(losses, key=lambda x: x[7])[:25]:
        print("    %s  tau %2d  %s at %.0fc x %.0f  lead %.2fbp  $%.2f"
              % (dt.datetime.utcfromtimestamp(b[0]).strftime("%m-%d %H:%MZ"),
                 b[2], b[3], 100 * b[4], b[5], b[8], b[7]))

    print("\n## BY DAY  (tau 1-15, ask <= 98c, cap 50)")
    per = collections.defaultdict(lambda: [0, 0, 0.0])
    for b in simulate(races, M, idx, 1, 15, 0.98, 50):
        d = dt.datetime.utcfromtimestamp(b[0]).strftime("%Y-%m-%d")
        per[d][0] += 1
        per[d][1] += (0 if b[6] else 1)
        per[d][2] += b[7]
    print("  %-12s %8s %8s %10s" % ("UTC day", "races", "losses", "$"))
    for d in sorted(per):
        v = per[d]
        print("  %-12s %8d %8d %+10.2f" % (d, v[0], v[1], v[2]))

    print("\n## IS THE BIG OFFER THE BAD OFFER?  (tau 1-20, ask <= 98c)")
    print("Eight of the thirteen losses above were on 120-contract offers. If a")
    print("maker's size is biggest exactly when they are about to be wrong, then")
    print("every uncapped number in this file is fantasy and the real capacity")
    print("is the median 10-16 lot. This is the test.")
    allb = simulate(races, M, idx, 1, 20, 0.98, 1e9)
    print("  %-16s %7s %8s %9s %10s %11s"
          % ("offer size", "races", "losses", "loss %", "contracts", "c/contract"))
    for lo, hi in ((1, 5), (5, 15), (15, 40), (40, 100), (100, 150), (150, 1e9)):
        s = [b for b in allb if lo <= b[5] < hi]
        if not s:
            continue
        cts = sum(b[5] for b in s)
        bad = sum(1 for b in s if not b[6])
        pnl = sum(b[7] for b in s)
        print("  %-16s %7d %8d %8.1f%% %10.0f %10.2fc"
              % ("%d-%s" % (lo, "+" if hi > 1e8 else int(hi)), len(s), bad,
                 100.0 * bad / len(s), cts, 100 * pnl / cts if cts else 0))
    print("  If loss %% climbs with size, the book is not offering us capacity --")
    print("  it is offering us the trades it wants to be out of.")

    if a.fair:
        import pinracefair as F
        print("\n## THE FORECAST AS THE ONLY GATE, ONE POSITION PER RACE")
        print("No price floor, no leader rule. Buy the leg whose probability")
        print("beats its ask by the most, if that beats the bar. Ruler %s, "
              "fat-tail %.2f, forecast staled %ds." % (a.ruler, a.kappa, a.lag))
        print("  %-30s %6s %7s %7s %8s %9s %10s %9s"
              % ("rule", "races", "contr", "losses", "avg paid", "c/contract",
                 "total $", "$/day"))
        for tau_hi in (15, 30, 60):
            for me in (0.00, 0.02, 0.05, 0.10):
                bets = simulate_fair(races, M, F, idx, 1, tau_hi, a.cap, me,
                                     ruler=a.ruler, kappa=a.kappa, lag=a.lag)
                report(bets, "tau<=%d, edge >= %.0fc" % (tau_hi, 100 * me), days)
            print("  %s" % ("-" * 96))
        print("\n## THE SAME, AT A SIZE THE BOOK CAN ABSORB (tau<=30, edge>=2c)")
        print("  %-30s %6s %7s %7s %8s %9s %10s %9s"
              % ("cap", "races", "contr", "losses", "avg paid", "c/contract",
                 "total $", "$/day"))
        for cap in (10, 20, 50, 100):
            bets = simulate_fair(races, M, F, idx, 1, 30, cap, 0.02,
                                 ruler=a.ruler, kappa=a.kappa, lag=a.lag)
            report(bets, "%d contracts" % cap, days)
        bets = simulate_fair(races, M, F, idx, 1, 30, 50, 0.02,
                             ruler=a.ruler, kappa=a.kappa, lag=a.lag)
        print("\n## WHAT IT BUYS  (tau<=30, edge>=2c, cap 50) -- by price paid")
        print("  %-14s %7s %8s %8s %10s" % ("price", "races", "losses",
                                            "contracts", "$"))
        for lo, hi in ((0.0, 0.3), (0.3, 0.6), (0.6, 0.8), (0.8, 0.9),
                       (0.9, 0.95), (0.95, 1.0)):
            s = [b for b in bets if lo <= b[4] < hi]
            if not s:
                continue
            print("  %-14s %7d %8d %8.0f %+10.2f"
                  % ("%.0f-%.0fc" % (100 * lo, 100 * hi), len(s),
                     sum(1 for b in s if not b[6]), sum(b[5] for b in s),
                     sum(b[7] for b in s)))
        print("\n## AND BY DAY  (tau<=30, edge>=2c, cap 50)")
        per = collections.defaultdict(lambda: [0, 0, 0.0])
        for b in bets:
            d = dt.datetime.utcfromtimestamp(b[0]).strftime("%Y-%m-%d")
            per[d][0] += 1
            per[d][1] += (0 if b[6] else 1)
            per[d][2] += b[7]
        print("  %-12s %8s %8s %10s" % ("UTC day", "races", "losses", "$"))
        for d in sorted(per):
            v = per[d]
            print("  %-12s %8d %8d %+10.2f" % (d, v[0], v[1], v[2]))
        print("\n## EVERY LOSS  (tau<=30, edge>=2c, cap 50)")
        for b in sorted([x for x in bets if not x[6]], key=lambda x: x[7])[:25]:
            print("    %s  tau %2d  %s at %.0fc x %.0f  model edge %+.1fc  $%.2f"
                  % (dt.datetime.utcfromtimestamp(b[0]).strftime("%m-%d %H:%MZ"),
                     b[2], b[3], 100 * b[4], b[5], b[8], b[7]))

    print("\nCEILING, NOT A FILL RATE. Every purchase here lifts an offer that")
    print("was resting; whether it would be ours, and whether the ones we win")
    print("are the bad ones, only our own fills can say.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
