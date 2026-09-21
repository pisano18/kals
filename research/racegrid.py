#!/usr/bin/env python3
"""racegrid.py -- price every Coin Race second ONCE, then sweep every rule.

WHY THIS EXISTS. `raceclose.py --fair` re-ran the Monte Carlo for every rule
variant it reported: 927 races x 60 seconds x 1,000 draws, twenty times over.
One table row took four minutes. Everything a rule needs from a race-second is
the same five probabilities and the same five top-of-book quotes, so this file
computes that grid once, caches it to disk, and then answers any number of
rules instantly.

THE GRID. For every race and every second tau in [1, TAU_HI]:

    p[coin]                 pinracefair's probability, built ONLY from index
                            prints at or before second close-tau
    (bid, ask, bsz, asz)    top of book per leg, carried forward, refused
                            once stale
    winner                  recomputed from the index, never read from a
                            settlement file

A RULE is then a pure function of that grid, so a sweep over price floors,
edge bars, tau bands, sides and position caps costs nothing.

THE LAG CONTROL IS BUILT IN AND IS NOT OPTIONAL. A trade or a quote stamped
inside second S matched to a forecast built through second S can see a
fraction of a second of the future. On this product that fraction is worth
everything: at lag 0 the best-looking rule in the file makes +12c a contract
and at lag 2 the same rule LOSES. The grid is therefore built at several lags
and every table names its own.

    python research/racegrid.py --selftest
    python research/racegrid.py --hours 600
"""
import argparse
import collections
import datetime as dt
import glob
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")

import racebook                                                # noqa: E402

COINS = racebook.COINS
TAU_HI = 60
MAXAGE = 30
GRIDDIR = os.path.join(REPO, "flow_cache", "racegrid")


# ----------------------------------------------------------------- the grid
def build_grid(races, M, F, idx, ruler="3600", kappa=1.0, tau_hi=TAU_HI,
               progress=None):
    """[(close, winner, {tau: (probs, quotes)})] -- the whole surface, once."""
    out = []
    for k, (close, stamp, rows) in enumerate(races):
        rets = M.returns_at(idx, close, 0)
        if len(rets) < len(COINS):
            continue
        winner = max(rets, key=rets.get)
        st = racebook.scan_race(rows, close, tau_lo=1, tau_hi=tau_hi,
                                max_age=MAXAGE)
        ser = None
        per = {}
        for tau, fresh in st:
            if not fresh:
                continue
            if ser is None:
                ser = F.RaceSeries(idx, close)
            pr, _ = F.fair_at(idx, ser, close, tau, ruler, (kappa,))
            if pr is None:
                continue
            per[tau] = (pr[kappa], fresh)
        if per:
            out.append((close, winner, per))
        if progress and (k + 1) % 100 == 0:
            print("  ... %d/%d races priced" % (k + 1, len(races)), flush=True)
    return out


def save_grid(grid, path):
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt") as fh:
        for close, winner, per in grid:
            fh.write(json.dumps([close, winner,
                                 {str(t): [p, {c: list(q) for c, q in f.items()}]
                                  for t, (p, f) in per.items()}]) + "\n")
    os.replace(tmp, path)


def load_grid(path):
    out = []
    with gzip.open(path, "rt") as fh:
        for line in fh:
            close, winner, per = json.loads(line)
            out.append((close, winner,
                        {int(t): (p, {c: tuple(q) for c, q in f.items()})
                         for t, (p, f) in per.items()}))
    return out


# ------------------------------------------------------------------ a rule
def run_rule(grid, tau_lo=1, tau_hi=TAU_HI, min_price=0.0, max_price=0.99,
             min_edge=0.0, cap=1e9, sides=("yes", "no"), lag=0):
    """One position per race, taken at the EARLIEST qualifying second.

    Earliest, not best: taking the last chance before the close is the most
    informed and the cheapest print, and reaching for it is how this product
    was first over-measured. `lag` prices the decision with a forecast that
    many seconds stale."""
    bets = []
    for close, winner, per in grid:
        for tau in range(tau_hi, tau_lo - 1, -1):
            cell = per.get(tau)
            if cell is None:
                continue
            src = per.get(tau + lag) if lag else cell
            if src is None:
                continue
            p, _ = src
            _, fresh = cell
            best = None
            for coin in COINS:
                q = fresh.get(coin)
                if q is None:
                    continue
                bid, ask, bsz, asz = q
                if "yes" in sides and min_price <= ask <= max_price and asz >= 1:
                    e = p[coin] - ask - racebook.order_fee(1, ask)
                    if best is None or e > best[0]:
                        best = (e, coin, "yes", ask, asz)
                if "no" in sides and bsz >= 1 and 0.0 < bid < 1.0:
                    np_ = round(1.0 - bid, 4)
                    if min_price <= np_ <= max_price:
                        e = (1.0 - p[coin]) - np_ - racebook.order_fee(1, np_)
                        if best is None or e > best[0]:
                            best = (e, coin, "no", np_, bsz)
            if best is None or best[0] < min_edge:
                continue
            e, coin, side, price, avail = best
            n = min(avail, cap)
            if n < 1:
                continue
            won = (coin == winner) if side == "yes" else (coin != winner)
            pnl = n * ((1.0 - price) if won else -price) \
                - racebook.order_fee(n, price)
            bets.append((close, tau, coin, side, price, n, won, pnl, 100 * e))
            break                      # ONE POSITION PER RACE. Never relax.
    return bets


def line(bets, label, days):
    if not bets:
        print("  %-34s %6s" % (label, "-"))
        return
    cts = sum(b[5] for b in bets)
    pnl = sum(b[7] for b in bets)
    bad = sum(1 for b in bets if not b[6])
    paid = sum(b[4] * b[5] for b in bets) / cts
    print("  %-34s %6d %6d %6.1f%% %8.0f %7.1fc %+8.2fc %+9.2f %+8.2f"
          % (label, len(bets), bad, 100.0 * bad / len(bets), cts, 100 * paid,
             100 * pnl / cts, pnl, pnl / days if days else 0))


HEAD = ("  %-34s %6s %6s %7s %8s %7s %9s %10s %9s"
        % ("rule", "races", "bad", "bad %", "contr", "paid", "c/contract",
           "total $", "$/day"))


# -------------------------------------------------------------- self-test
def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    # a hand-built grid, so the rule engine is tested without any index at all
    def cell(pb, quotes):
        return (pb, quotes)

    flat = {c: (0.0, 1.0, 0.0, 0.0) for c in COINS}
    g = []
    # race A: BTC certain, offered at 93c size 40 at tau 30..1
    q = dict(flat)
    q["BTC"] = (0.90, 0.93, 20.0, 40.0)
    pa = {c: (0.995 if c == "BTC" else 0.00125) for c in COINS}
    g.append((1000, "BTC", {t: cell(pa, q) for t in range(1, 31)}))
    # race B: identical book, but ETH wins -- the same rule must lose here
    g.append((2000, "ETH", {t: cell(pa, q) for t in range(1, 31)}))

    b = run_rule(g, cap=1e9, sides=("yes",))
    ck(len(b) == 2, "one position per race, two races, two bets (%d)" % len(b))
    ck(all(x[1] == 30 for x in b),
       "each taken at the EARLIEST qualifying second, tau 30")
    ck(b[0][6] and not b[1][6],
       "the race BTC wins is scored a win and the race ETH wins is scored a loss")
    exp = 40 * 0.07 - racebook.order_fee(40, 0.93)
    ck(abs(b[0][7] - exp) < 1e-12,
       "40 contracts at 93c on a winner = $%.2f after fee" % exp)
    ck(abs(b[1][7] + (40 * 0.93 + racebook.order_fee(40, 0.93))) < 1e-12,
       "and the loser costs the full 93c plus the fee, never netted")
    ck(sum(x[7] for x in b) < 0,
       "NULL-ISH: one win and one loss at 93c is NET NEGATIVE ($%.2f) -- a 93c "
       "bet needs far better than 50%%" % sum(x[7] for x in b))

    ck(run_rule(g, min_price=0.95, sides=("yes",)) == [],
       "a 95c price floor refuses a 93c offer")
    ck(run_rule(g, max_price=0.90, sides=("yes",)) == [],
       "a 90c ceiling refuses it too")
    ck(run_rule(g, min_edge=0.50, sides=("yes",)) == [],
       "NULL: demand 50c of edge and nothing anywhere qualifies")
    ck(len(run_rule(g, tau_lo=1, tau_hi=5, sides=("yes",))) == 2
       and run_rule(g, tau_lo=1, tau_hi=5, sides=("yes",))[0][1] == 5,
       "a narrower tau band still fires, at the earliest second in THAT band")
    ck(run_rule(g, tau_lo=40, tau_hi=60, sides=("yes",)) == [],
       "a band the grid does not cover fires nothing")
    b2 = run_rule(g, cap=10, sides=("yes",))
    ck(all(x[5] == 10 for x in b2), "the position cap binds at 10 contracts")

    # the NO side, and the fact that four of five legs lose
    qn = {c: (0.00, 1.0, 0.0, 0.0) for c in COINS}
    qn["ETH"] = (0.04, 0.06, 30.0, 30.0)          # 4c bid -> NO at 96c
    gn = [(3000, "BTC", {t: cell(pa, qn) for t in range(1, 31)})]
    bn = run_rule(gn, sides=("no",))
    ck(len(bn) == 1 and bn[0][3] == "no" and bn[0][2] == "ETH" and bn[0][6],
       "a 4c bid on a beaten leg is bought as NO at 96c and wins")
    ck(abs(bn[0][4] - 0.96) < 1e-9 and bn[0][5] == 30,
       "at 1 - the yes bid, for the yes-bid size")
    ck(run_rule(gn, sides=("yes",)) == [],
       "and with the NO side switched off that race is not traded at all")
    gn2 = [(3000, "ETH", {t: cell(pa, qn) for t in range(1, 31)})]
    ck(not run_rule(gn2, sides=("no",))[0][6],
       "buying NO on the coin that WINS is scored a loss")

    # the lag control must actually change the decision
    g3 = []
    per = {}
    for t in range(1, 31):
        pp = {c: (0.99 if c == "BTC" else 0.0025) for c in COINS} if t <= 10 \
            else {c: (0.10 if c == "BTC" else 0.225) for c in COINS}
        per[t] = cell(pp, q)
    g3.append((4000, "BTC", per))
    ck(run_rule(g3, tau_lo=1, tau_hi=10, min_edge=0.04, sides=("yes",), lag=0),
       "at lag 0 the fresh forecast (99%) clears a 4c bar at 93c")
    ck(run_rule(g3, tau_lo=1, tau_hi=10, min_edge=0.04, sides=("yes",), lag=15)
       == [],
       "and a 15 s stale forecast (10%) does not -- the lag control bites")

    # round trip through disk
    import tempfile
    fd, tp = tempfile.mkstemp(suffix=".jsonl.gz")
    os.close(fd)
    try:
        save_grid(g, tp)
        back = load_grid(tp)
        ck(run_rule(back, sides=("yes",)) == run_rule(g, sides=("yes",)),
           "the grid round-trips through disk to identical decisions")
    finally:
        os.remove(tp)

    print("racegrid selftest:", "OK" if ok else "FAILED")
    return ok


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=racebook.DATA)
    ap.add_argument("--hours", type=int, default=600)
    ap.add_argument("--ruler", default="3600")
    ap.add_argument("--kappa", type=float, default=1.0)
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if not selftest():
        return 1
    if a.selftest:
        return 0

    os.makedirs(GRIDDIR, exist_ok=True)
    gp = os.path.join(GRIDDIR, "grid_%s_%.2f_%d.jsonl.gz"
                      % (a.ruler, a.kappa, a.hours))
    if os.path.exists(gp) and not a.rebuild:
        print("\nreusing the priced grid at %s" % gp)
        grid = load_grid(gp)
    else:
        files = sorted(glob.glob(os.path.join(a.data, "ticker", "*.jsonl.gz")))
        if a.hours:
            files = files[-a.hours:]
        if not files:
            print("loaded nothing -- no ticker files")
            return 0
        cand, got = racebook.parse_rate(files)
        print("\n%d ticker files; parser check %d/%d" % (len(files), got, cand))
        if cand and got < 0.95 * cand:
            print("REFUSING TO REPORT -- ticker wire format moved")
            return 1
        by_race = collections.defaultdict(list)
        for k, fp in enumerate(files):
            for r in racebook.cached_hour(fp):
                by_race[r[1]].append(r)
            if (k + 1) % 150 == 0:
                print("  ... %d/%d files read" % (k + 1, len(files)), flush=True)
        races = []
        for stamp, rows in by_race.items():
            c = racebook.close_of(stamp)
            if c is None or len({r[2] for r in rows}) < len(COINS):
                continue
            races.append((c, stamp, rows))
        races.sort()
        del by_race
        print("  %d races with all five legs quoting" % len(races))
        import idxload
        import pinracefair as F
        import pinracemodel as M
        idx = idxload.load(sorted(set(M.COINS.values())), verbose=False)
        if not idx or idx.get("BRTI") is None:
            print("loaded nothing -- no index on disk")
            return 0
        grid = build_grid(races, M, F, idx, ruler=a.ruler, kappa=a.kappa,
                          progress=True)
        del races, idx
        save_grid(grid, gp)
        print("  grid saved: %s" % gp)

    if len(grid) < 50:
        print("loaded nothing -- only %d priced races" % len(grid))
        return 0
    days = (grid[-1][0] - grid[0][0]) / 86400.0
    print("  %d priced races, %.1f days, %s .. %s"
          % (len(grid), days,
             dt.datetime.utcfromtimestamp(grid[0][0]).strftime("%m-%d"),
             dt.datetime.utcfromtimestamp(grid[-1][0]).strftime("%m-%d")))

    print("\n## THE PRICE FLOOR IS THE STRATEGY  (forecast staled 2s, uncapped)")
    print("Same forecast, same book, same one-position-per-race rule. The only")
    print("difference is how cheap a leg it is allowed to buy.")
    print(HEAD)
    for floor in (0.0, 0.50, 0.80, 0.90, 0.95):
        for edge in (0.0, 0.02):
            line(run_rule(grid, min_price=floor, min_edge=edge, lag=2),
                 "price >= %.0fc, edge >= %.0fc" % (100 * floor, 100 * edge),
                 days)
        print("  %s" % ("-" * 104))

    print("\n## AND THE SAME AT LAG 0 -- the contaminated version, for contrast")
    print(HEAD)
    for floor in (0.0, 0.90):
        for edge in (0.0, 0.02):
            line(run_rule(grid, min_price=floor, min_edge=edge, lag=0),
                 "price >= %.0fc, edge >= %.0fc" % (100 * floor, 100 * edge),
                 days)
    print("  A floor-free rule that gains at lag 0 and loses at lag 2 was never")
    print("  a rule. A rule whose two columns agree is reading settled facts.")

    print("\n## TIME BAND, at the 90c floor (lag 2, uncapped)")
    print(HEAD)
    for tl, th in ((1, 15), (1, 20), (1, 30), (1, 45), (1, 60), (16, 30),
                   (31, 60)):
        line(run_rule(grid, tau_lo=tl, tau_hi=th, min_price=0.90, lag=2),
             "tau %d-%d" % (tl, th), days)

    print("\n## WHICH SIDE  (tau 1-60, 90c floor, lag 2, uncapped)")
    print(HEAD)
    for s, lab in ((("yes",), "buy YES on the leader only"),
                   (("no",), "buy NO on a beaten leg only"),
                   (("yes", "no"), "whichever is better")):
        line(run_rule(grid, min_price=0.90, sides=s, lag=2), lab, days)

    print("\n## AT A SIZE THE BOOK CAN ABSORB  (tau 1-60, 90c floor, lag 2)")
    print(HEAD)
    for cap in (10, 20, 50, 100, 250, 1e9):
        line(run_rule(grid, min_price=0.90, cap=cap, lag=2),
             "cap %s contracts" % ("none" if cap > 1e8 else int(cap)), days)

    best = run_rule(grid, min_price=0.90, cap=50, lag=2)
    print("\n## WHAT IT BUYS  (tau 1-60, 90c floor, cap 50, lag 2)")
    print("  %-14s %7s %7s %9s %10s" % ("price paid", "races", "bad",
                                        "contracts", "$"))
    for lo, hi in ((0.90, 0.93), (0.93, 0.95), (0.95, 0.97), (0.97, 0.99),
                   (0.99, 1.01)):
        s = [b for b in best if lo <= b[4] < hi]
        if not s:
            continue
        print("  %-14s %7d %7d %9.0f %+10.2f"
              % ("%.0f-%.0fc" % (100 * lo, 100 * hi), len(s),
                 sum(1 for b in s if not b[6]), sum(b[5] for b in s),
                 sum(b[7] for b in s)))

    print("\n## BY DAY  (tau 1-60, 90c floor, cap 50, lag 2)")
    per = collections.defaultdict(lambda: [0, 0, 0.0])
    for b in best:
        d = dt.datetime.utcfromtimestamp(b[0]).strftime("%Y-%m-%d")
        per[d][0] += 1
        per[d][1] += (0 if b[6] else 1)
        per[d][2] += b[7]
    print("  %-12s %7s %7s %10s" % ("UTC day", "races", "bad", "$"))
    for d in sorted(per):
        v = per[d]
        print("  %-12s %7d %7d %+10.2f" % (d, v[0], v[1], v[2]))

    bad = [b for b in best if not b[6]]
    print("\n## EVERY LOSS  (tau 1-60, 90c floor, cap 50, lag 2): %d of %d races"
          % (len(bad), len(best)))
    for b in sorted(bad, key=lambda x: x[7])[:25]:
        print("    %s tau %2d  %s %s at %.0fc x %.0f  edge %+.1fc  $%.2f"
              % (dt.datetime.utcfromtimestamp(b[0]).strftime("%m-%d %H:%MZ"),
                 b[1], b[2], b[3], 100 * b[4], b[5], b[8], b[7]))

    print("\nCEILING, NOT A FILL RATE. Every purchase lifts an offer that was")
    print("resting. Whether it would be ours, and whether the ones we win are")
    print("the bad ones, only our own fills can say.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
