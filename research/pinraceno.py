#!/usr/bin/env python3
"""pinraceno.py -- THE FOUR LEGS NOBODY HAS EVER PRICED.

FIRST SENTENCE, PER THE 2026-09-10 AMENDMENT: every number in this file comes
from the TAPE, so the loss rates below are the rate at which offers that were
SITTING THERE went on to lose. They are NOT our loss rate and must never be
quoted as one. On the up/down markets the same two populations differ by 31x,
because ours is "somebody actively sold it to us" and this one is not.

THE QUESTION. A Coin Race has five legs and exactly one wins. Every race file
this project has written -- pinlead, pinleadprice, pinracetest -- priced the
LEADER'S YES and nothing else. pinracetest then ran seven live races and sent
zero orders, because the leader's YES is almost never under a 95c cap.

Nobody has ever looked at the other four. A coin fifteen basis points behind
with eight seconds left is a flatter bet than the leader is, there are four of
them per race instead of one, and the way to hold it is to BUY ITS NO.

THE INSTRUMENT is the trade tape, for the reason established in pintrades: a
NO-taker print at yes-price p proves a NO offer existed at (1 - p) that second.
A book replay is structurally blind to executions; this is not.

THE FORECAST is pinracemodel's gap table, which reproduces Kalshi's own
settled winner on 761 of 761 races. HALF THE RACES BUILD THE TABLE AND THE
OTHER HALF ARE SCORED ON IT, split by date, because every entry filter this
project has ever found on the up/down markets reversed on a holdout.

NO LOOK-AHEAD: the gap used to price a print at tau seconds out is computed
from index prints at or before that second.

    python research/pinraceno.py --selftest
    python research/pinraceno.py --hours 240
"""
import argparse
import collections
import glob
import gzip
import json
import math
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import idxload                                               # noqa: E402
import pinracemodel as M                                     # noqa: E402

DATA = r"C:\kals\kalshi_data"
TRUTH = M.TRUTH
CEILING = 0.98
BANDS = ((45, 61), (30, 45), (20, 30), (15, 20), (10, 15), (5, 10), (2, 5))


def fee(p):
    return math.ceil(0.07 * p * (1 - p) * 10000 - 1e-9) / 10000


def pnl(price, won):
    """Dollars per contract on a binary bought at `price`."""
    return (1.0 - price if won else -price) - fee(price)


def breakeven(q):
    """The price at which a q-accurate bet is exactly flat, in cents.

    Solves q - p - 0.07p(1-p) = 0 for p. Quoted next to every accuracy, so a
    good-looking win rate can never be read without the price that bought it."""
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if q - mid - 0.07 * mid * (1 - mid) > 0:
            lo = mid
        else:
            hi = mid
    return 100 * lo


def cp_interval(k, n):
    """Clopper-Pearson 95% interval on k of n, by bisection on the beta tail."""
    if n == 0:
        return 0.0, 1.0

    def tail(p, m):
        # P(X >= m) for X ~ Bin(n, p)
        s = 0.0
        for i in range(m, n + 1):
            s += math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
        return s

    lo, hi = 0.0, 1.0
    if k > 0:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = (a + b) / 2
            if tail(m, k) < 0.025:
                a = m
            else:
                b = m
        lo = a
    if k < n:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = (a + b) / 2
            if (1 - tail(m, k + 1)) > 0.025:
                a = m
            else:
                b = m
        hi = a
    return lo, hi


def build_table(idx, races, taus):
    """The gap table, from a specific list of races and nothing else."""
    t = collections.defaultdict(lambda: collections.defaultdict(
        lambda: {"n": 0, "won": 0}))
    for _stamp, close, won in races:
        for tau in taus:
            g = M.gaps(M.returns_at(idx, close, tau))
            if len(g) < 5:
                continue
            for coin, gap in g.items():
                cell = t[str(tau)][str(M.bucket(gap * 1e4))]
                cell["n"] += 1
                if coin == won:
                    cell["won"] += 1
    return {k: {b: dict(v) for b, v in bs.items()} for k, bs in t.items()}


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    ck(abs(fee(0.97) - 0.0021) < 1e-9,
       "97c costs 0.21c to take, rounded up as the exchange bills it")
    ck(abs(pnl(0.97, True) - (0.03 - 0.0021)) < 1e-9,
       "a 97c winner pays 3c less the fee")
    ck(abs(pnl(0.97, False) - (-0.97 - 0.0021)) < 1e-9,
       "and a 97c LOSER costs the whole 97c plus the fee -- the fee is paid "
       "either way, which is what makes an expensive binary unforgiving")
    ck(pnl(0.97, True) * 32 < abs(pnl(0.97, False)),
       "so 32 wins at 97c do not cover one loss: %.2fc against %.2fc"
       % (100 * 32 * pnl(0.97, True), 100 * abs(pnl(0.97, False))))
    b = breakeven(0.99)
    ck(98.0 < b < 99.0,
       "a 99%%-accurate bet breaks even at %.2fc, NOT at 99c -- the fee eats "
       "the difference" % b)
    ck(breakeven(0.97) < 97.0 and breakeven(0.80) < 80.0,
       "and break-even is below the accuracy at every level")
    lo, hi = cp_interval(0, 100)
    ck(lo == 0.0 and 0.02 < hi < 0.05,
       "0 losses in 100 has an upper bound of %.1f%%, not zero" % (100 * hi))
    lo, hi = cp_interval(5, 100)
    ck(lo < 0.05 < hi and hi > 0.10,
       "5 in 100 brackets the point estimate, upper %.1f%%" % (100 * hi))
    ck(cp_interval(0, 0) == (0.0, 1.0),
       "NULL: no observations is the whole interval, never a point")

    # the table builder must see only the races it is handed
    base = 7_000_000 - (7_000_000 % M.WINDOW)
    close = base + 2 * M.WINDOW

    def mk(iid, o, c):
        D = idxload.Dense(iid, close - M.WINDOW - 200, M.WINDOW + 400)
        for s in range(close - M.WINDOW - 200, close + 100):
            D.v[s - D.base] = o if s < close - M.N_AVG else c
        return D

    idx = {"BRTI": mk("BRTI", 100.0, 102.0), "ETHUSD_RTI": mk("E", 100.0, 101.0),
           "SOLUSD_RTI": mk("S", 100.0, 100.5), "XRPUSD_RTI": mk("X", 100.0, 100.2),
           "HYPEUSD_RTI": mk("H", 100.0, 100.1)}
    t = build_table(idx, [("s", close, "BTC")], [10])
    tot = sum(c["n"] for c in t["10"].values())
    ck(tot == 5, "one race contributes exactly 5 legs, not 1 and not 25")
    ck(sum(c["won"] for c in t["10"].values()) == 1,
       "and exactly one of those five is marked a winner")
    ck(build_table(idx, [], [10]) == {},
       "NULL: no races builds an empty table, which p_win reads as None -- "
       "stand aside -- rather than as a coin flip or as certainty")
    ck(M.p_win({}, 12, -5.0) is None,
       "and None is what the scorer skips on, so a leg the table has never "
       "seen contributes nothing at any price. Before this it was worth 50c, "
       "which at a 21c ask read as a 29c edge and was most of the result")
    print("pinraceno selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=240)
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0
    if not os.path.exists(TRUTH):
        print("loaded nothing -- %s missing" % TRUTH)
        return 0

    truth = json.load(open(TRUTH, encoding="utf-8"))
    idx = idxload.load(sorted(M.COINS.values()), verbose=False)
    D = idx.get("BRTI")
    if D is None:
        print("loaded nothing -- no index on disk")
        return 0
    races = []
    for stamp, legs in truth.items():
        c = M.close_of(stamp)
        if c is None or c < D.base or c > D.base + D.n:
            continue
        w = [k for k, v in legs.items() if v == "yes"]
        if len(w) == 1:
            races.append((stamp, c, w[0]))
    races.sort(key=lambda r: r[1])
    if len(races) < 100:
        print("loaded nothing -- only %d scorable races" % len(races))
        return 0

    # ---- THE SPLIT, by time, before any price is looked at -------------
    cut = races[len(races) // 2][1]
    early = [r for r in races if r[1] < cut]
    late = [r for r in races if r[1] >= cut]
    taus = sorted({t for lo, hi in BANDS for t in (lo, hi)} | set(M.TAUS))
    tbl = build_table(idx, early, taus)
    winner = {c: w for _s, c, w in races}
    print("\n  %d races: %d build the table, %d are scored on it."
          % (len(races), len(early), len(late)))
    print("  The split is by TIME and was fixed before any price was read.\n")

    # ---- the tape ------------------------------------------------------
    files = sorted(glob.glob(os.path.join(DATA, "trade", "2026*.jsonl.gz")))
    files = files[:-1][-a.hours:]
    late_closes = {c for _s, c, _w in late}
    prints = []          # (close, coin, tau, no_price, size, taker)
    seen = 0
    for fp in files:
        try:
            with gzip.open(fp, "rt") as fh:
                for line in fh:
                    if "CRYPTOLEAD" not in line or '"trade"' not in line:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                    except Exception:                        # noqa: BLE001
                        continue
                    tk = m.get("market_ticker") or ""
                    _evt, _, leg = tk.rpartition("-")
                    if leg not in M.COINS:
                        continue
                    ts = int(m.get("ts_ms") or 0)
                    if not ts:
                        continue
                    sec = ts // 1000
                    # the close is the next quarter hour at or after the print
                    cs = ((sec + M.WINDOW - 1) // M.WINDOW) * M.WINDOW
                    if cs not in late_closes:
                        continue
                    tau = cs - sec
                    if not (2 <= tau <= 61):
                        continue
                    try:
                        yp = float(m["yes_price_dollars"])
                        n = float(m.get("count_fp") or m.get("count") or 0)
                    except Exception:                        # noqa: BLE001
                        continue
                    if n <= 0 or not (0 < yp < 1):
                        continue
                    seen += 1
                    prints.append((cs, leg, tau, round(1.0 - yp, 4), n,
                                   m.get("taker_side")))
        except (EOFError, zlib.error, OSError):
            pass
    if not prints:
        print("loaded nothing -- no Coin Race trades in the scored half")
        return 0
    tk = collections.Counter(p[5] for p in prints)
    print("  %d Coin Race prints inside tau 2-61 over %d hours of tape"
          % (seen, len(files)))
    print("  taker side: %s\n" % dict(tk))

    # ---- score ---------------------------------------------------------
    # For each print, what was the leg's gap AT THAT SECOND, and what did the
    # forecast say the NO was worth? Only prints where a NO-TAKER lifted an
    # offer count, because only those prove a NO offer existed at that price.
    gapcache = {}

    def gap_of(cs, tau):
        """The gap at the trade's OWN second. Never a snapped one.

        v1 looked the gap up at the nearest table tau, which for a print at
        tau 54 meant reading the index four seconds into its future. On the
        2026-09-12 15:15 race BTC LED by 3.09bp at tau 54 and TRAILED by
        2.26bp at tau 50, so the snapped read scored the market's correct 94c
        quote as a howler and handed us a fake 16x winner. The same look-ahead
        in its first form inflated RESULTS_coinrace from a true 89.4% to a
        reported 98.9%."""
        key = (cs, tau)
        if key not in gapcache:
            gapcache[key] = M.gaps(M.returns_at(idx, cs, tau))
        return gapcache[key]

    print("  %-9s%8s%8s%10s%11s%11s%12s   %s"
          % ("tau band", "legs", "races", "avg paid", "won", "break-even",
             "c/contract", "lost (TAPE, not ours)"))
    print("  " + "-" * 104)
    grand = []
    for lo, hi in BANDS:
        rows = []
        byrace = collections.defaultdict(list)
        for cs, coin, tau, nop, n, side in prints:
            if not (lo <= tau < hi) or side != "no":
                continue
            if nop <= 0 or nop > CEILING + 1e-9:
                continue
            g = gap_of(cs, tau)
            if coin not in g:
                continue
            if g[coin] >= 0:
                continue                      # this leg is the LEADER, not a NO
            pw = M.p_win(tbl, tau, g[coin] * 1e4)
            if pw is None:
                continue     # the table has never seen this gap at this tau
            worth = 1.0 - pw
            if worth - nop - fee(nop) < 0.02:
                continue                      # the same 2c floor the arm uses
            byrace[(cs, coin)].append((tau, nop, n, worth))
        for (cs, coin), v in byrace.items():
            tau, nop, n, worth = max(v)       # earliest print in the band
            rows.append((nop, coin != winner.get(cs), cs))
        if len(rows) < 10:
            print("  %-9s%8d   -- too few to report" % ("%d-%d" % (lo, hi), len(rows)))
            continue
        w = sum(1 for r in rows if r[1])
        q = w / float(len(rows))
        avg = sum(r[0] for r in rows) / len(rows)
        tot = sum(pnl(r[0], r[1]) for r in rows)
        lo_, hi_ = cp_interval(len(rows) - w, len(rows))
        grand.extend(rows)
        print("  %-9s%8d%8d%9.2fc%10.1f%%%10.2fc%11.2fc   %.1f%% [%.1f, %.1f]"
              % ("%d-%d" % (lo, hi), len(rows), len({r[2] for r in rows}),
                 100 * avg, 100 * q, breakeven(q), 100 * tot / len(rows),
                 100 * (1 - q), 100 * lo_, 100 * hi_))
    if grand:
        w = sum(1 for r in grand if r[1])
        tot = sum(pnl(r[0], r[1]) for r in grand)
        lo_, hi_ = cp_interval(len(grand) - w, len(grand))
        print("  " + "-" * 104)
        print("  %-9s%8d%8d%9.2fc%10.1f%%%10.2fc%11.2fc   %.1f%% [%.1f, %.1f]"
              % ("ALL", len(grand), len({r[2] for r in grand}),
                 100 * sum(r[0] for r in grand) / len(grand),
                 100 * w / len(grand), breakeven(w / float(len(grand))),
                 100 * tot / len(grand), 100 * (1 - w / float(len(grand))),
                 100 * lo_, 100 * hi_))

    # ---- BY PRICE, because the cheap-leg cliff is this product's known
    # failure mode. RESULTS_coinrace: a <=80c limit on the leader's YES looked
    # like +10.11c a contract and lost 35.1% of its bets. If the NO side's
    # money is all in the cheap band, it is the same trap wearing a hat.
    print("\n  BY PRICE PAID, all tau bands pooled:")
    print("  %-11s%8s%8s%10s%11s%12s   %s"
          % ("price", "legs", "races", "avg paid", "won", "c/contract",
             "lost (TAPE, not ours)"))
    print("  " + "-" * 92)
    for plo, phi in ((0.0, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 0.93),
                     (0.93, 0.99)):
        sub = [r for r in grand if plo <= r[0] < phi]
        if len(sub) < 10:
            print("  %-11s%8d   -- too few to report"
                  % ("%.0f-%.0fc" % (100 * plo, 100 * phi), len(sub)))
            continue
        w = sum(1 for r in sub if r[1])
        tot = sum(pnl(r[0], r[1]) for r in sub)
        lo_, hi_ = cp_interval(len(sub) - w, len(sub))
        print("  %-11s%8d%8d%9.2fc%10.1f%%%11.2fc   %.1f%% [%.1f, %.1f]"
              % ("%.0f-%.0fc" % (100 * plo, 100 * phi), len(sub),
                 len({r[2] for r in sub}),
                 100 * sum(r[0] for r in sub) / len(sub), 100 * w / len(sub),
                 100 * tot / len(sub), 100 * (1 - w / float(len(sub))),
                 100 * lo_, 100 * hi_))

    # ---- the control: what the YES side looked like on the same tape ---
    print("\n  CONTROL -- the leader's YES on the same races and the same tape,")
    print("  which is what every earlier race file measured:")
    yrows = collections.defaultdict(list)
    for cs, coin, tau, nop, n, side in prints:
        if side != "yes" or not (5 <= tau <= 30):
            continue
        yp = round(1.0 - nop, 4)
        if yp <= 0 or yp > CEILING + 1e-9:
            continue
        g = gap_of(cs, tau)
        if coin not in g or g[coin] <= 0:
            continue
        pl = M.p_lose(tbl, tau, g[coin] * 1e4)
        if pl is None:
            continue
        worth = 1.0 - pl
        if worth - yp - fee(yp) < 0.02:
            continue
        yrows[(cs, coin)].append((tau, yp))
    yr = [(max(v)[1], coin == winner.get(cs)) for (cs, coin), v in yrows.items()]
    if len(yr) >= 10:
        w = sum(1 for r in yr if r[1])
        tot = sum(pnl(r[0], r[1]) for r in yr)
        lo_, hi_ = cp_interval(len(yr) - w, len(yr))
        print("  %-9s%8d%8s%9.2fc%10.1f%%%10.2fc%11.2fc   %.1f%% [%.1f, %.1f]"
              % ("yes 5-30", len(yr), "-",
                 100 * sum(r[0] for r in yr) / len(yr), 100 * w / len(yr),
                 breakeven(w / float(len(yr))), 100 * tot / len(yr),
                 100 * (1 - w / float(len(yr))), 100 * lo_, 100 * hi_))
    else:
        print("  only %d leader-YES prints cleared the same 2c floor" % len(yr))

    print("\n  Every loss rate above is the rate at which an offer SITTING ON")
    print("  THE BOOK went on to lose. It is not our loss rate and cannot be")
    print("  read as one -- on the up/down markets the two differ by 31x. The")
    print("  paper arm running now is what produces the forward number.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
