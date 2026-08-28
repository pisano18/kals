#!/usr/bin/env python3
"""calib.py -- is the calibration edge real, or is it which side traded?

WHAT PROMPTED THIS

`kalshi_fulltape.py`'s D-FINAL table, on 3,600 settled markets and 8.5 million
trades, found eight surviving cells and one coherent pattern in the 480-900s
window:

      480-900s  0.55   realized 0.520   edge -2.9c  t=-3.0  n=2644
      480-900s  0.60   realized 0.566   edge -3.3c  t=-3.3  n=2419
      480-900s  0.65   realized 0.608   edge -4.1c  t=-3.9  n=2169
      480-900s  0.70   realized 0.659   edge -3.8c  t=-3.5  n=1844
      480-900s  0.75   realized 0.708   edge -4.0c  t=-3.5  n=1551
      480-900s  0.10   realized 0.148   edge +4.3c  t=+3.3  n= 711

Five adjacent buckets, same sign, smooth. That is far more interesting than
any single t-statistic, and it is worth 3-4c a contract if it is real.

ITS OWN REPORT SAYS WHY IT MIGHT NOT BE

    "STILL NOT TRADEABLE ON THIS EVIDENCE: prints sit at bid or ask, so a
     taker-side gap is the spread."

A trade PRINT is not a price, it is a price plus a side. Someone lifting the
ask at 0.65 prints 0.65 when the mid was 0.645. If buyers dominate the
0.55-0.75 range, every print there is half a spread too high, realized comes
in below it, and you get exactly this table out of a perfectly efficient
market. The observed gaps are 2.9-4.1c against a 1c spread, so half-spread
alone does not cover it -- but nothing rules out a mix of that and a wider
effective spread when the book is thin.

There is a SECOND selection effect in the same table. Sampling at trade times
means sampling when somebody chose to trade, which is not a random moment: it
is disproportionately a volatile one. That is the occupation-time bias, and it
has produced fake findings in this project before.

WHAT THIS FILE DOES

Runs the identical calibration three ways on the same markets:

    print   price = the trade print            (reproduces D-FINAL)
    mid     price = the book mid at the same second, from OUR ticker channel
    grid    price = the book mid on a FIXED tau grid, ignoring when trades
                    happened at all

If `print` shows the pattern and `mid` does not, it was the side. If `mid`
shows it and `grid` does not, it was when trades happen. If all three show it,
it is in the book, and the next question is whether it survives the spread.

NOTHING HERE PLACES AN ORDER.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from statistics import NormalDist, mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tdist import p_two_sided                                  # noqa: E402

ND = NormalDist()
BUCKETS = [i / 20.0 for i in range(21)]          # 0.00 .. 1.00 by 5c
TAU_BANDS = ((0, 60), (60, 180), (180, 480), (480, 900))
GRID_STEP = 30                                   # seconds between grid points


def bucket_of(p):
    return min(BUCKETS, key=lambda b: abs(b - p))


def band_of(tau):
    for lo, hi in TAU_BANDS:
        if lo <= tau < hi:
            return (lo, hi)
    return None


# ===========================================================================
def outcome_of(m):
    """1.0 / 0.0 / None from a market's settled result.

    fulltape and replay both write `result` as a FLOAT (1.0 or 0.0); the API
    itself uses the strings "yes"/"no". The first version of this file tested
    `str(result).lower() in ("yes","true","1")`, which turns 1.0 into "1.0"
    and matches nothing -- so every one of 3,600 settled markets read as a
    loss, every realized rate came out 0.000, and every t was -1.6 million.

    A number that absurd is easy to catch. A subtler parse failure is not,
    which is why sane_or_die below refuses to print a table whose overall
    outcome rate is impossible rather than trusting this function.
    """
    r = m.get("result")
    if r is None:
        return None
    if isinstance(r, bool):
        return 1.0 if r else 0.0
    if isinstance(r, (int, float)):
        return 1.0 if float(r) >= 0.5 else 0.0
    t = str(r).strip().lower()
    if t in ("yes", "true", "1", "1.0", "y"):
        return 1.0
    if t in ("no", "false", "0", "0.0", "n"):
        return 0.0
    return None


def sane_or_die(rows, label=""):
    """A calibration table is only meaningful if outcomes look like outcomes.

    Across every bucket and band, YES should resolve somewhere near half the
    time -- the buckets span 0 to 1 and the sample is dominated by the middle.
    A rate of 0.000 or 1.000 is not a market discovery, it is a field that did
    not parse, and printing a t of -1.6 million as though it were a finding is
    worse than printing nothing.
    """
    if not rows:
        return True
    rate = sum(r[4] for r in rows) / len(rows)
    if 0.05 <= rate <= 0.95:
        return True
    print(f"\n  *** REFUSING TO REPORT {label}: the overall YES rate across "
          f"{len(rows):,} observations is {rate:.3f}.")
    print("  That is not a market, it is an outcome field that did not parse.")
    print("  Check markets.json: `result` is written as a float 1.0/0.0 by")
    print("  fulltape and as \"yes\"/\"no\" by the API.")
    return False


def rows_from_prints(quotes, trades, markets):
    """One row per trade: the print price, its market, its tau band."""
    out = []
    for tk, tr in trades.items():
        m = markets.get(tk)
        won = outcome_of(m) if m else None
        if won is None:
            continue
        close_s = int(m["close"])
        for (t, price, _size, _side) in tr:
            b = band_of(close_s - t)
            if b is None or not (0.0 < price < 1.0):
                continue
            out.append((b, bucket_of(price), price, tk, won))
    return out


def _mid_index(q):
    """(sorted seconds, {sec: mid}) for one market's quote series."""
    mids = {}
    for rec in q:
        t, bid, ask = rec[0], rec[1], rec[2]
        if bid is None or ask is None or not (0.0 <= bid <= ask <= 1.0):
            continue
        mids[t] = (bid + ask) / 2.0
    return sorted(mids), mids


def _mid_at(secs, mids, t, max_stale=30):
    """Last mid at or before t, and only if it is fresh."""
    lo, hi, best = 0, len(secs) - 1, None
    while lo <= hi:
        m = (lo + hi) // 2
        if secs[m] <= t:
            best = secs[m]
            lo = m + 1
        else:
            hi = m - 1
    if best is None or t - best > max_stale:
        return None
    return mids[best]


def rows_from_mids(quotes, trades, markets):
    """Same trades, same instants -- but priced at the BOOK MID.

    Isolates the taker side and nothing else: identical sample of moments,
    identical markets, only the price definition changes.
    """
    out = []
    for tk, tr in trades.items():
        m = markets.get(tk)
        won = outcome_of(m) if m else None
        if won is None or tk not in quotes:
            continue
        close_s = int(m["close"])
        secs, mids = _mid_index(quotes[tk])
        if len(secs) < 5:
            continue
        for (t, _price, _size, _side) in tr:
            b = band_of(close_s - t)
            if b is None:
                continue
            mid = _mid_at(secs, mids, t)
            if mid is None or not (0.0 < mid < 1.0):
                continue
            out.append((b, bucket_of(mid), mid, tk, won))
    return out


def rows_from_grid(quotes, markets, step=GRID_STEP):
    """The book mid on a FIXED tau grid, ignoring when trades happened.

    Trades cluster in volatile seconds. Sampling at trade times therefore
    samples volatile moments, which is the occupation-time bias -- the sample
    is chosen by the same process that moves the price. A grid fixed in
    advance cannot do that.
    """
    out = []
    for tk, q in quotes.items():
        m = markets.get(tk)
        won = outcome_of(m) if m else None
        if won is None:
            continue
        close_s = int(m["close"])
        secs, mids = _mid_index(q)
        if len(secs) < 5:
            continue
        for tau in range(step, 900 + 1, step):
            b = band_of(tau)
            if b is None:
                continue
            mid = _mid_at(secs, mids, close_s - tau)
            if mid is None or not (0.0 < mid < 1.0):
                continue
            out.append((b, bucket_of(mid), mid, tk, won))
    return out


# ===========================================================================
def calibrate(rows, min_markets=30):
    """realized-minus-price per (band, bucket), ONE observation per market.

    A market settles once. Fifty quote-seconds inside it that all land in the
    same bucket carry the information of one, and counting them as fifty is
    the fastest way to manufacture a t-statistic in this project.
    """
    per = defaultdict(lambda: defaultdict(list))
    for band, buck, price, tk, won in rows:
        per[(band, buck)][tk].append((price, won))
    out = {}
    for key, by_tk in per.items():
        # One observation per market: its MEAN price in this bucket and its
        # single outcome. A market settles once; fifty quote-seconds inside it
        # carry the information of one.
        obs = [(mean(x[0] for x in v), v[0][1]) for v in by_tk.values()]
        n = len(obs)
        if n < min_markets:
            continue
        q = mean(w for _pr, w in obs)
        # The AVERAGE ACTUAL PRICE, not the bucket centre. This is what
        # D-FINAL reports and it is the only version that can see a
        # half-spread effect at all: bucketing to 5c centres absorbs a 0.5c
        # side bias completely, and an estimator that cannot see the
        # alternative explanation cannot rule it out.
        price = mean(pr for pr, _w in obs)
        se = math.sqrt(max(q * (1 - q), 1e-12) / n)
        out[key] = {"n": n, "price": price, "realized": q,
                    "edge": q - price, "se": se,
                    "t": (q - price) / se if se > 0 else 0.0}
    return out


def print_table(tab, label, only_band=None):
    print(f"\n  {label}")
    print(f"  {'band':>12}{'bucket':>8}{'avg px':>9}{'markets':>9}"
          f"{'realized':>10}{'edge':>9}{'t':>7}")
    for (band, buck), r in sorted(tab.items()):
        if only_band and band != only_band:
            continue
        print(f"  {f'{band[0]}-{band[1]}s':>12}{100*buck:>7.0f}c"
              f"{r['price']:>9.4f}{r['n']:>9,}"
              f"{r['realized']:>10.3f}{100*r['edge']:>8.1f}c{r['t']:>7.1f}")


def compare(tabs, band, buckets):
    """The whole point: the same cells, priced three ways, side by side."""
    print(f"\n  {'price':>7}" + "".join(f"{k:>22}" for k in tabs))
    for b in buckets:
        row = f"  {100*b:>6.0f}c"
        for k in tabs:
            r = tabs[k].get((band, b))
            row += (f"{100*r['edge']:>14.1f}c t={r['t']:>4.1f}" if r
                    else f"{'--':>22}")
        print(row)


# ===========================================================================
def selftest():
    print("=" * 78)
    print("SELF-TEST -- can this tell a real mispricing from a trading side?")
    print("=" * 78)
    fails = []

    def world(n, seed, true_p=0.65, mid=0.65, buy_share=1.0, vol_bias=0.0):
        """n markets quoted at `mid`, settling at `true_p`.

        buy_share  fraction of trades that LIFT THE ASK. 1.0 means every print
                   is half a spread above the mid, which is what a one-sided
                   flow looks like on the tape.
        vol_bias   makes trade COUNT depend on the outcome, so trade-time
                   sampling over-weights one kind of market. That is the
                   occupation-time bias, in the smallest form that shows it.
        """
        rng = random.Random(seed)
        quotes, trades, markets = {}, {}, {}
        for w in range(n):
            close_s = 1_760_000_000 + w * 900
            tk = f"C{w:04d}"
            won = rng.random() < true_p
            markets[tk] = {"ticker": tk, "close": close_s,
                           "result": "yes" if won else "no", "strike": 1.0}
            q, tr = [], []
            for tau in range(900, 0, -1):
                t = close_s - tau
                q.append((t, mid - 0.005, mid + 0.005, 100.0, 100.0))
            ntr = 40 + (60 if (won and vol_bias) else 0)
            for _ in range(ntr):
                tau = rng.randrange(1, 900)
                t = close_s - tau
                if rng.random() < buy_share:
                    tr.append((t, mid + 0.005, 10.0, "yes"))
                else:
                    tr.append((t, mid - 0.005, 10.0, "no"))
            quotes[tk], trades[tk] = q, tr
        return quotes, trades, markets

    # ---- 1. an efficient book, but every print lifts the ask --------------
    print("\n1. AN EFFICIENT BOOK WITH ONE-SIDED FLOW. The mid is exactly")
    print("   right; every print is half a spread above it. Sampling noise on")
    print("   an outcome rate is ~1c either way, so the test is not 'is the")
    print("   mid edge zero' -- it is whether PRINT and MID differ by exactly")
    print("   the half-spread, on identical moments and identical markets.")
    band = (480, 900)
    q, tr, mk = world(3000, seed=3, true_p=0.65, mid=0.65, buy_share=1.0)
    one = {"print": calibrate(rows_from_prints(q, tr, mk)).get((band, 0.65)),
           "mid": calibrate(rows_from_mids(q, tr, mk)).get((band, 0.65)),
           "grid": calibrate(rows_from_grid(q, mk)).get((band, 0.65))}
    print(f"\n  {'source':>10}{'avg px':>9}{'markets':>9}{'realized':>10}"
          f"{'edge':>9}{'t':>7}")
    for k, r in one.items():
        if not r:
            fails.append(f"{k} produced no 0.65 cell")
            continue
        print(f"  {k:>10}{r['price']:>9.4f}{r['n']:>9,}{r['realized']:>10.3f}"
              f"{100*r['edge']:>8.1f}c{r['t']:>7.1f}")
    if one["print"] and one["mid"]:
        gap = 100 * (one["mid"]["edge"] - one["print"]["edge"])
        print(f"\n  mid edge minus print edge: {gap:>5.2f}c   "
              f"(the half-spread is 0.50c)")
        if abs(gap - 0.5) > 0.12:
            fails.append(f"one-sided flow moved the edge by {gap:.2f}c, not "
                         "the 0.50c half-spread -- either the fixture or the "
                         "price definition is wrong")

    # ---- 1b. balanced flow must move it by nothing -----------------------
    q, tr, mk = world(3000, seed=5, true_p=0.65, mid=0.65, buy_share=0.5)
    bp = calibrate(rows_from_prints(q, tr, mk)).get((band, 0.65))
    bm = calibrate(rows_from_mids(q, tr, mk)).get((band, 0.65))
    if bp and bm:
        gap2 = 100 * (bm["edge"] - bp["edge"])
        print(f"  balanced flow, same comparison:  {gap2:>5.2f}c   "
              "(must be ~0)")
        if abs(gap2) > 0.12:
            fails.append(f"balanced flow still moved the edge by {gap2:.2f}c")

    # ---- 2. a genuinely mispriced book -----------------------------------
    print("\n2. A GENUINELY MISPRICED BOOK, balanced flow. Mid says 0.65,")
    print("   truth is 0.58. ALL THREE must find it, or the estimator is")
    print("   blind to the thing we are actually hunting.")
    q, tr, mk = world(3000, seed=11, true_p=0.58, mid=0.65, buy_share=0.5)
    got = {"print": calibrate(rows_from_prints(q, tr, mk)).get((band, 0.65)),
           "mid": calibrate(rows_from_mids(q, tr, mk)).get((band, 0.65)),
           "grid": calibrate(rows_from_grid(q, mk)).get((band, 0.65))}
    print(f"\n  {'source':>10}{'markets':>9}{'realized':>10}{'edge':>9}{'t':>7}")
    for k, r in got.items():
        if not r:
            fails.append(f"{k} found no cell on a mispriced book")
            continue
        print(f"  {k:>10}{r['n']:>9,}{r['realized']:>10.3f}"
              f"{100*r['edge']:>8.1f}c{r['t']:>7.1f}")
        if abs(r["edge"] - (0.58 - 0.65)) > 0.020:
            fails.append(f"{k} measured {100*r['edge']:.1f}c against a "
                         "planted -7.0c")

    # ---- 3. occupation-time bias -----------------------------------------
    print("\n3. OCCUPATION TIME. Trade COUNT depends on the outcome, so")
    print("   trade-time sampling over-weights one kind of market. The grid")
    print("   is fixed in advance and cannot. Same efficient book, so the")
    print("   truthful answer is ZERO edge.")
    q, tr, mk = world(3000, seed=21, true_p=0.65, mid=0.65, buy_share=0.5,
                      vol_bias=1.0)
    got = {"mid (trade times)": calibrate(rows_from_mids(q, tr, mk)).get(
               (band, 0.65)),
           "grid (fixed taus)": calibrate(rows_from_grid(q, mk)).get(
               (band, 0.65))}
    print(f"\n  {'source':>20}{'markets':>9}{'realized':>10}{'edge':>9}"
          f"{'t':>7}")
    for k, r in got.items():
        if not r:
            continue
        print(f"  {k:>20}{r['n']:>9,}{r['realized']:>10.3f}"
              f"{100*r['edge']:>8.1f}c{r['t']:>7.1f}")
    # Both should be near zero HERE, because one-per-market clustering
    # already defuses this particular bias -- and that is worth asserting,
    # because it is the reason the clustering rule exists.
    for k, r in got.items():
        if r and abs(r["edge"]) > 0.015:
            fails.append(f"{k} showed {100*r['edge']:.1f}c on an efficient "
                         "book; one-per-market clustering should have "
                         "defused the trade-count bias")

    # ---- 4. the grid column has to EARN its place ------------------------
    print("\n4. WHERE THE GRID ACTUALLY DIFFERS. Sections 1-3 all hold the")
    print("   mid constant, so 'grid' and 'mid' are identical by")
    print("   construction there and prove nothing about the grid. The real")
    print("   case: the mid MOVES, and trades happen only when it is extreme.")
    print("   Trade-time sampling then reports a market at its extremes; the")
    print("   grid reports where it actually spent its time.")

    def moving(n, seed):
        """An HONEST moving book: the mid is the true posterior at every
        instant, so it is a martingale and calibration must find nothing.

        The first version of this fixture random-walked the mid and CLIPPED
        it to [0.03, 0.97]. A reflecting boundary is not a martingale -- a mid
        at 5c gets pushed up, so it wins more than 5% of the time -- and the
        calibration duly fired at |t| = 6.4 with an 18c 'edge' at 10c. That
        was the fixture lying, not the estimator failing, and it would have
        been read as 'the grid column is untrustworthy'.

        Built the real way instead: a Brownian path, the outcome is its sign
        at close, and the mid is Phi(x / sd_remaining). That is the exact
        posterior, it lives in (0,1) with no boundary, and it is a martingale
        by construction. Trades fire only when the mid is extreme, which is
        the whole point of the section.
        """
        rng = random.Random(seed)
        quotes, trades, markets = {}, {}, {}
        SIG = 1.0
        for w in range(n):
            close_s = 1_760_000_000 + w * 900
            tk = f"M{w:04d}"
            x, q, tr = 0.0, [], []
            for tau in range(900, 0, -1):
                t = close_s - tau
                x += rng.gauss(0, SIG)
                mid = ND.cdf(x / (SIG * math.sqrt(tau)))
                q.append((t, max(mid - 0.005, 0.0), min(mid + 0.005, 1.0),
                          100.0, 100.0))
                if abs(mid - 0.50) > 0.15 and rng.random() < 0.25:
                    tr.append((t, mid, 10.0, "yes"))
            won = x > 0.0                      # the path's own sign at close
            markets[tk] = {"ticker": tk, "close": close_s,
                           "result": "yes" if won else "no", "strike": 1.0}
            quotes[tk], trades[tk] = q, tr
        return quotes, trades, markets

    q, tr, mk = moving(2500, seed=31)
    t_md = calibrate(rows_from_mids(q, tr, mk), min_markets=40)
    t_gr = calibrate(rows_from_grid(q, mk), min_markets=40)
    print(f"\n  {'bucket':>8}{'mid cells':>28}{'grid cells':>28}")
    print(f"  {'':>8}{'mkts':>10}{'edge':>9}{'t':>9}"
          f"{'mkts':>10}{'edge':>9}{'t':>9}")
    worst_md = worst_gr = 0.0
    for b in (0.10, 0.20, 0.30, 0.50, 0.70, 0.80, 0.90):
        rm = t_md.get(((480, 900), b))
        rg = t_gr.get(((480, 900), b))
        row = f"  {100*b:>7.0f}c"
        for r in (rm, rg):
            row += (f"{r['n']:>10,}{100*r['edge']:>8.1f}c{r['t']:>9.1f}"
                    if r else f"{'--':>28}")
        print(row)
        if rm:
            worst_md = max(worst_md, abs(rm["t"]))
        if rg:
            worst_gr = max(worst_gr, abs(rg["t"]))
    print(f"\n  worst |t| -- mid at trade times {worst_md:.1f}, "
          f"grid {worst_gr:.1f}")
    print("  The book is honest by construction, so BOTH should be quiet.")
    print("  If only the grid is quiet, trade-time sampling is the bias and")
    print("  the grid column is the one to read.")
    if worst_gr > 3.5:
        fails.append(f"the GRID column fired at |t|={worst_gr:.1f} on a book "
                     "that is the exact posterior at every instant -- the "
                     "column this file tells you to trust is not trustworthy")
    if worst_md > 3.5:
        fails.append(f"the MID column fired at |t|={worst_md:.1f} on an exact "
                     "posterior; trade-time sampling is biased and the grid "
                     "column is the only one to read")

    # ---- 5. the outcome field, and the gate that catches it -------------
    print("\n5. THE OUTCOME FIELD. fulltape writes `result` as a FLOAT")
    print("   1.0/0.0; the API uses \"yes\"/\"no\". Testing")
    print("   str(result).lower() in (\"yes\",\"true\",\"1\") turns 1.0 into")
    print("   \"1.0\" and matches nothing, so all 3,600 settled markets read")
    print("   as losses and every t came out at -1.6 million.")
    CASES = [("float 1.0/0.0", 1.0, 1.0), ("float 0.0", 0.0, 0.0),
             ("int 1", 1, 1.0), ("string yes", "yes", 1.0),
             ("string no", "no", 0.0), ("string YES", "YES", 1.0),
             ("bool True", True, 1.0), ("string 1.0", "1.0", 1.0),
             ("missing", None, None), ("garbage", "pending", None)]
    print(f"\n  {'stored as':>18}{'value':>10}{'parsed':>10}{'want':>10}")
    for name, val, want in CASES:
        m = {} if val is None else {"result": val}
        got = outcome_of(m)
        print(f"  {name:>18}{str(val):>10}{str(got):>10}{str(want):>10}"
              + ("" if got == want else "   *** WRONG ***"))
        if got != want:
            fails.append(f"outcome_of({val!r}) gave {got!r}, expected {want!r}")

    # and the gate must refuse a table built from a broken parse
    print("\n   The gate: a table whose overall YES rate is impossible must")
    print("   be REFUSED, not printed. It is the backstop for the next parse")
    print("   bug, which will not be this one.")
    good = [((480, 900), 0.5, 0.5, f"T{i}", float(i % 2)) for i in range(200)]
    broken = [((480, 900), 0.5, 0.5, f"T{i}", 0.0) for i in range(200)]
    if not sane_or_die(good, "a healthy table"):
        fails.append("the gate rejected a table with a 50% YES rate")
    if sane_or_die(broken, "an all-zero table"):
        fails.append("the gate ACCEPTED a table where nothing ever resolved "
                     "yes -- it would have passed the -1.6 million t through")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- a one-sided tape shows a gap on prints and")
    print("none on mids, a real mispricing shows on all three, and")
    print("one-per-market clustering defuses the trade-count bias.")
    return True


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    from replay import load_quotes, load_markets
    from edge import load_trades
    quotes = load_quotes(a.data)
    markets = load_markets(a.out)
    trades = load_trades(a.data)
    print(f"\n  {len(quotes):,} quoted markets, {len(markets):,} settled, "
          f"{sum(len(v) for v in trades.values()):,} trades")
    if not quotes or not markets:
        print("  nothing to measure.")
        return

    raw = {"print": rows_from_prints(quotes, trades, markets),
           "mid": rows_from_mids(quotes, trades, markets),
           "grid": rows_from_grid(quotes, markets)}
    if not all(sane_or_die(v, k) for k, v in raw.items()):
        return
    tabs = {k: calibrate(v) for k, v in raw.items()}
    for k, t in tabs.items():
        print(f"  {k:>6}: {len(t)} cells with enough markets")

    print("\n" + "=" * 78)
    print("THE EIGHT CELLS, PRICED THREE WAYS")
    print("=" * 78)
    print("  D-FINAL found these on trade prints. If the pattern is the")
    print("  taker side it dies in the 'mid' column; if it is when trades")
    print("  happen it dies in 'grid'; if it survives both it is in the book.")
    compare(tabs, (480, 900), [0.10, 0.55, 0.60, 0.65, 0.70, 0.75])
    print("\n  and the two cells from the other bands:")
    compare(tabs, (180, 480), [0.65])
    compare(tabs, (60, 180), [0.95])

    for k, t in tabs.items():
        print_table(t, f"FULL TABLE -- {k}", only_band=(480, 900))

    print("\n  A cell is only worth acting on if it survives in 'grid', which")
    print("  is the only column whose sample was not chosen by the market.")


if __name__ == "__main__":
    main()
