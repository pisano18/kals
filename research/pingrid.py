#!/usr/bin/env python3
r"""pingrid.py -- what buyers of near-certainties actually lose, by series, by
seconds-to-close and by price, from the trade tape. Plus the reversal screen.

THE OPERATOR, 2026-09-17: "Take that information and run with it. There MUST
be something actionable ... Is it possible different commodities need
different strategies? ... Hopefully we can do earlier bets on commodities too
... if confidence flips soon enough instead of just hedging, overbuy the new
winning side?" And: "verify everything for yourself and give no bias to a way
of thinking or idea because I said it."

WHAT THIS IS. One walk of the trade tape, one grid. For every trade in the
last TAU_MAX seconds of a settled 15-minute market, on the crypto series AND
the five commodity series, it records who the TAKER bought (yes/no), what they
paid, how many seconds were left, and whether that side went on to win. Then
it tabulates, per series and per (seconds-left band x price band):

    trades, contracts, share that bought the LOSING side, and the expected
    value per contract at that loss rate and that mean price.

That is the whole question "how early, and how cheap, can a buyer of a
near-certainty go before the price stops paying for the losses" -- answered
by the market's own record rather than by a model. It is what decided the
commodities method (results/RESULTS_commodities.md) and it is run here across
a wider grid and on the crypto series too.

THE REVERSAL SCREEN. On a market where the side priced as the favourite at
FAV_TAU seconds out went on to LOSE -- a late flip -- what did buyers of the
eventual WINNER pay in the final seconds, and how often was that trade right?
If, once a flip is under way, the new winner is buyable well under 90c and
wins nearly always, then "overbuy the new side" has a population to stand on;
if those buyers lose often, the flip is mostly noise and the hedge-only rule
is right. Rule 5 caveat as everywhere: what the market did.

RULE 5. Everything here is a TAPE population -- trades that happened. Our
own population ("we took a resting offer") differed from it by 31x on the
crypto markets. Nothing below is our loss rate; every number is a screen that
can KILL an idea, and none can prove one.

    python research/pingrid.py --selftest
    python research/pingrid.py            # walks the tape hours the settlements cover; caches
"""
import argparse
import calendar
import collections
import glob
import gzip
import json
import os
import statistics as st
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinflat                                                   # noqa: E402

REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
TAPE = r"C:\kals\kalshi_data\trade"
# The RECENT settlements only (last ~5 days, 500 per crypto series + 300 per
# commodity series). The older crypto file back to 08/24 would triple the walk
# and the row count (every taker buy at 80c+ within 180 s is kept, losers
# included) on a machine that has already killed two jobs for memory. Five
# days is enough for a screen; extend deliberately, not by default.
SETTLE_FILES = [r"C:\kals\fulltape_recent\markets.json",
                r"C:\kals\fulltape_candle\markets.json"]
CACHE = os.path.join(RESULTS, "pingrid_cache.json")

TAU_MAX = 180
# half-open [lo, hi): 0-5 s is (0, 6), and so on. Printed as lo..hi-1.
TAU_BANDS = [(0, 6), (6, 16), (16, 31), (31, 46), (46, 61), (61, 91), (91, 121), (121, 181)]
PX_BANDS = [(0.80, 0.90), (0.90, 0.95), (0.95, 0.98), (0.98, 0.99)]


def tau_label(tb):
    return "%d-%d s" % (tb[0], tb[1] - 1)
FAV_TAU = 60          # the side trading >= 90c here is "the favourite"
WOBBLE_TAU = 30       # the wobble is measured inside the last 30 s
WOBBLE_BANDS = [(0.90, 1.01), (0.80, 0.90), (0.70, 0.80), (0.50, 0.70), (0.0, 0.50)]
CRYPTO = {"KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBNB15M",
          "KXZEC15M", "KXHYPE15M", "KXNEAR15M", "KXADA15M", "KXBCH15M", "KXTON15M"}


def outcome_of(m):
    r = m.get("result")
    if isinstance(r, str):
        return 1.0 if r.strip().lower() in ("yes", "y", "1", "true") else 0.0
    try:
        return float(r)
    except (TypeError, ValueError):
        return None


def load_settlements(paths=SETTLE_FILES):
    out = {}
    for p in paths:
        try:
            with open(p, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        for lst in data.values():
            for m in lst:
                o = outcome_of(m)
                if o is not None and m.get("ticker"):
                    out[m["ticker"]] = o
    return out


def fee(p):
    return 0.07 * p * (1.0 - p)


def band_of(v, bands):
    """Half-open [lo, hi) except the LAST band, which is closed. The first
    version used closed bands throughout, so a trade at exactly 95c matched
    both 90-95 and 95-98 and landed in whichever came first -- the self-test
    caught it (3 planted trades in one cell came out as 2 and 1)."""
    for i, (lo, hi) in enumerate(bands):
        last = i == len(bands) - 1
        if lo <= v < hi or (last and v == hi):
            return (lo, hi)
    return None


def scan_trade(msg, settled, tau_max=TAU_MAX):
    """One tape trade -> a row, or None. Keeps EVERY taker buy in the last
    tau_max seconds at 80c+, on either side, won or lost -- the grid needs
    the losers."""
    tk = msg.get("market_ticker")
    if not tk or "15M-" not in tk:
        return None
    won_yes = settled.get(tk)
    if won_yes is None:
        return None
    close = pinflat.close_epoch(tk)
    if close is None:
        return None
    try:
        ts = int(msg["ts"])
        yes_px = float(msg["yes_price_dollars"])
        n = float(msg.get("count_fp") or 0)
    except (KeyError, TypeError, ValueError):
        return None
    tau = close - ts
    if not (0 <= tau <= tau_max):
        return None
    side = msg.get("taker_side")
    if side not in ("yes", "no"):
        return None
    paid = yes_px if side == "yes" else 1.0 - yes_px
    # 50c floor, not 80c: the GRID only tabulates 80c+ (band_of returns None
    # below that), but the REVERSAL screen needs the new side's cheap buys at
    # 50-90c after a flip. The first version floored at 80c and the self-test's
    # planted 75c new-side buy came back None.
    if paid < 0.50:
        return None
    took_winner = (side == "yes" and won_yes >= 0.5) or (side == "no" and won_yes < 0.5)
    return {"tk": tk, "ser": tk.split("-")[0], "close": close, "tau": tau,
            "paid": round(paid, 4), "n": n, "won": bool(took_winner), "side": side}


class Acc:
    """Aggregate IN PLACE. The first walk kept every row -- 2.5 million dicts
    for five days -- and was heading for the memory kill this machine has
    already dealt out twice today. The grid needs only counts per cell, and the
    reversal screen needs rows only for the ~5% of markets that flipped; both
    are known at scan time because the settlement is. So: cells, plus a small
    per-market state, plus the late rows of flip markets only."""

    def __init__(self):
        self.grid = collections.defaultdict(lambda: [0, 0, 0.0, 0.0, 0.0])   # (ser, tb, pb) -> ...
        self.fav = {}                   # tk -> (side, fav_won)  decided from trades near FAV_TAU
        self.late = collections.defaultdict(list)   # tk -> late rows (kept only while unknown or flipped)
        self.markets = collections.Counter()
        # THE WOBBLE: for every market WITH a favourite, the lowest price the
        # favourite's side traded at inside the last WOBBLE_TAU seconds, and
        # when. One tuple per market. The reversal question is then honest:
        # "when the favourite traded down to X, how often did it end up
        # losing?" -- conditioned on what a trader could SEE, not on the
        # outcome. The first screen kept rows only for markets whose
        # favourite LOST, so every new-side buyer in it was right by
        # construction, and it printed 0.0% everywhere. That was leakage.
        self.wob = {}                   # tk -> (min_fav_price, tau_at_min)

    def add(self, r):
        tb = band_of(r["tau"], TAU_BANDS)
        pb = band_of(r["paid"], PX_BANDS)
        if tb is not None and pb is not None:
            c = self.grid[(r["ser"], tb, pb)]
            c[0] += 1
            c[1] += (not r["won"])
            c[2] += r["n"]
            c[3] += 0 if r["won"] else r["n"]
            c[4] += r["paid"]
        tk = r["tk"]
        if tk not in self.fav and abs(r["tau"] - FAV_TAU) <= 15 and r["paid"] >= 0.90:
            fav_won = r["won"]              # this buyer bought the favourite; did it win?
            self.fav[tk] = (r["side"], fav_won)
            self.markets[r["ser"], "markets"] += 1
            if not fav_won:
                self.markets[r["ser"], "flips"] += 1
            else:
                self.late.pop(tk, None)     # favourite won: nothing to keep
        f0 = self.fav.get(tk)
        if f0 is not None and r["tau"] <= WOBBLE_TAU:
            # price of the FAVOURITE's side implied by this trade: a buyer of
            # the favourite paid `paid`; a buyer of the other side at p implies
            # the favourite at 1 - p.
            fav_px = r["paid"] if r["side"] == f0[0] else 1.0 - r["paid"]
            cur = self.wob.get(tk)
            if cur is None or fav_px < cur[0]:
                self.wob[tk] = (round(fav_px, 4), r["tau"])
        if r["tau"] <= FAV_TAU:
            f = self.fav.get(tk)
            # Keep late rows only for a KNOWN flip, or while the favourite is
            # still decidable (trades within the +-15 s window around FAV_TAU
            # arrive before the later ones, per market). A market that never
            # gets a favourite -- an uncertain one, most of them -- must not
            # keep its rows for ever: that is a leak the size of the tape.
            if (f is not None and not f[1]) or (f is None and r["tau"] >= FAV_TAU - 15):
                self.late[tk].append((r["tau"], r["paid"], r["n"], r["won"], r["side"]))
            elif f is None:
                self.late.pop(tk, None)     # never got a favourite: drop what was held

    def to_json(self):
        return {"grid": [[k[0], list(k[1]), list(k[2]), v] for k, v in self.grid.items()],
                "fav": {tk: list(v) for tk, v in self.fav.items()},
                "late": {tk: v for tk, v in self.late.items() if tk in self.fav and not self.fav[tk][1]},
                "wob": {tk: list(v) for tk, v in self.wob.items()},
                "markets": [[k[0], k[1], v] for k, v in self.markets.items()]}

    @classmethod
    def from_json(cls, d):
        a = cls()
        for ser, tb, pb, v in d.get("grid", []):
            a.grid[(ser, tuple(tb), tuple(pb))] = v
        a.fav = {tk: tuple(v) for tk, v in d.get("fav", {}).items()}
        a.late = collections.defaultdict(list, {tk: [tuple(x) for x in v] for tk, v in d.get("late", {}).items()})
        a.wob = {tk: tuple(v) for tk, v in d.get("wob", {}).items()}
        for ser, k, v in d.get("markets", []):
            a.markets[ser, k] = v
        return a


def wobble(acc):
    """{series: {wobble_band: [markets, favourite_lost]}}: of the markets whose
    favourite traded DOWN to that band inside the last WOBBLE_TAU seconds, how
    many ended with the favourite losing. Conditioned on the visible price,
    never on the outcome."""
    out = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for tk, (side, fav_won) in acc.fav.items():
        w = acc.wob.get(tk)
        if w is None:
            continue
        b = band_of(w[0], WOBBLE_BANDS[::-1])          # ascending for band_of
        if b is None:
            continue
        c = out[tk.split("-")[0]][b]
        c[0] += 1
        c[1] += (not fav_won)
    return out


def walk(files, settled, acc, on_progress=None, every=25):
    bad, done = 0, []
    for f in files:
        try:
            with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if "15M-" not in line:
                        continue
                    try:
                        msg = json.loads(line)["msg"]
                    except (ValueError, KeyError):
                        continue
                    r = scan_trade(msg, settled)
                    if r:
                        acc.add(r)
        except (EOFError, zlib.error, OSError):
            bad += 1
        done.append(f)
        if on_progress and len(done) % every == 0:
            on_progress(done, acc, bad)
    if on_progress and done:
        on_progress(done, acc, bad)
    return acc, bad


def grid(acc):
    """{series: {(tau_band, px_band): [trades, lost, contracts, lost_contracts, sum_paid]}}"""
    g = collections.defaultdict(dict)
    for (ser, tb, pb), v in acc.grid.items():
        g[ser][(tb, pb)] = v
    return g


def cell_ev(c):
    """EV per contract at the cell's own loss rate and mean price."""
    if not c[0]:
        return None
    q = c[1] / c[0]
    p = c[4] / c[0]
    return (1 - q) * (1 - p) - q * p - fee(p)


def reversal(acc):
    """Late flips: the favourite at FAV_TAU lost. What did buyers of the NEW
    side (the eventual winner) pay afterwards, by seconds left, and how often
    were they right?"""
    out = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0.0, 0.0]))
    for tk, (fav, fav_won) in acc.fav.items():
        if fav_won:
            continue
        ser = tk.split("-")[0]
        for tau, paid, n, won, side in acc.late.get(tk, []):
            if side == fav:
                continue                    # still buying the old favourite
            tb = band_of(tau, TAU_BANDS)
            if tb is None:
                continue
            pb = "<70c" if paid < 0.70 else ("70-90c" if paid < 0.90 else "90c+")
            c = out[ser][(tb, pb)]
            c[0] += 1
            c[1] += (not won)
            c[2] += n
            c[3] += paid
    return acc.markets, out


def report(acc, out=sys.stdout):
    p = lambda s: print(s, file=out)                              # noqa: E731
    g = grid(acc)
    p("BUYERS OF THE PRICED-IN SIDE, BY SECONDS LEFT AND PRICE PAID -- TAPE POPULATION (rule 5)")
    p("  cell = trades / % that bought the LOSING side / EV per contract at that rate. Blank = under 30 trades.")
    for ser in sorted(g, key=lambda s: (s not in CRYPTO, s)):
        p("")
        p("  %s" % ser)
        p("    seconds left | " + " | ".join("%-22s" % ("%.0f-%.0fc" % (100 * a, 100 * b)) for a, b in PX_BANDS))
        for tb in TAU_BANDS:
            cells = []
            for pb in PX_BANDS:
                c = g[ser].get((tb, pb))
                if not c or c[0] < 30:
                    cells.append("%-22s" % "")
                    continue
                cells.append("%-22s" % ("%5d %5.1f%% %+5.2fc" % (c[0], 100 * c[1] / c[0], 100 * cell_ev(c))))
            p("    %-11s   | " % tau_label(tb) + " | ".join(cells))
    # where the volume sits by tau, per series, at 90-98c (the pool we compete for)
    p("")
    p("WHERE THE 90-98c BUYING HAPPENS, share of contracts by seconds left (which windows matter)")
    for ser in sorted(g, key=lambda s: (s not in CRYPTO, s)):
        tot = collections.Counter()
        for (tb, pb), c in g[ser].items():
            if pb in ((0.90, 0.95), (0.95, 0.98)):
                tot[tb] += c[2]
        s = sum(tot.values())
        if s < 1000:
            continue
        p("  %-12s " % ser + "  ".join("%s %3.0f%%" % (tau_label(tb), 100 * tot[tb] / s) for tb in TAU_BANDS))
    wb = wobble(acc)
    p("")
    p("THE REVERSAL SCREEN, done honestly: markets with a favourite (>=90c at %ds), bucketed by the LOWEST price" % FAV_TAU)
    p("  the favourite traded at inside the last %ds. Of those, how many ended with the favourite LOSING." % WOBBLE_TAU)
    p("  This is what a trader could SEE at the time. A wobble to 50-70c that flips 80%% of the time is a buy of the")
    p("  new side at ~30-50c; one that flips 30%% of the time is the hedge-only rule being right.")
    p("")
    p("  %-12s | " % "series" + " | ".join("%-16s" % ("fav fell to %.0f-%.0fc" % (100 * lo, 100 * min(hi, 1.0))) for lo, hi in WOBBLE_BANDS))
    for ser in sorted(wb, key=lambda s: (s not in CRYPTO, s)):
        cells = []
        for b in WOBBLE_BANDS:
            c = wb[ser].get(b)
            if not c or c[0] < 5:
                cells.append("%-16s" % ("%d mkts" % (c[0] if c else 0)))
            else:
                cells.append("%-16s" % ("%4d mkts %3.0f%% lost" % (c[0], 100 * c[1] / c[0])))
        p("  %-12s | " % ser + " | ".join(cells))
    tot = collections.defaultdict(lambda: [0, 0])
    for ser in wb:
        if ser in CRYPTO:
            for b, c in wb[ser].items():
                tot[b][0] += c[0]
                tot[b][1] += c[1]
    p("  %-12s | " % "ALL CRYPTO" + " | ".join("%-16s" % (("%4d mkts %3.0f%% lost" % (tot[b][0], 100 * tot[b][1] / tot[b][0])) if tot[b][0] else "") for b in WOBBLE_BANDS))
    flips, _rv = reversal(acc)
    p("")
    p("  Flip rate overall (favourite at %ds lost): " % FAV_TAU + ", ".join(
        "%s %.1f%%" % (s, 100 * flips[s, "flips"] / max(1, flips[s, "markets"])) for s in sorted({k[0] for k in flips}) if flips[s, "markets"]))


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pingrid selftest: FAILED -- " + msg)

    tk = "KXBTC15M-26SEP161000-00"
    close = calendar.timegm((2026, 9, 16, 14, 0, 0))
    settled = {tk: 1.0}

    def tr(side, yes_px, tau, n=10.0, ticker=tk):
        return {"market_ticker": ticker, "ts": close - tau, "taker_side": side,
                "yes_price_dollars": yes_px, "count_fp": n}
    r = scan_trade(tr("yes", 0.95, 20), settled)
    ck(r and r["won"] and r["paid"] == 0.95 and r["tau"] == 20, "a YES buyer at 95c on a YES market: kept, won")
    r = scan_trade(tr("no", 0.05, 20), settled)
    ck(r and not r["won"] and r["paid"] == 0.95, "a NO buyer at 95c on a YES market: kept, LOST -- the grid needs losers")
    ck(scan_trade(tr("yes", 0.40, 20), settled) is None, "NULL: 40c is kept by nobody")
    r = scan_trade(tr("yes", 0.75, 20), settled)
    ck(r is not None and band_of(r["paid"], PX_BANDS) is None,
       "a 75c buy is scanned (the reversal screen needs it) but sits in no GRID cell")
    ck(scan_trade(tr("yes", 0.95, 200), settled) is None, "NULL: 200 s is beyond the window")
    ck(scan_trade(tr("yes", 0.95, 20, ticker="KXETH15M-26SEP161000-00"), settled) is None,
       "NULL: no settlement on file -> skipped, not guessed")
    ck(band_of(20, TAU_BANDS) == (16, 31) and band_of(0.96, PX_BANDS) == (0.95, 0.98) and band_of(0.995, PX_BANDS) is None,
       "bands place 20 s in 16-30 and 96c in 95-98; 99.5c falls outside every price band")
    ck(band_of(0.95, PX_BANDS) == (0.95, 0.98) and band_of(0.90, PX_BANDS) == (0.90, 0.95)
       and band_of(0.99, PX_BANDS) == (0.98, 0.99) and band_of(5, TAU_BANDS) == (0, 6) and band_of(6, TAU_BANDS) == (6, 16)
       and tau_label((0, 6)) == "0-5 s" and band_of(180, TAU_BANDS) == (121, 181),
       "a boundary value belongs to ONE band: 95c to 95-98, 90c to 90-95, 99c to the closed last band, 5 s to 0-5, 6 s to 6-15")
    acc = Acc()
    for r in (scan_trade(tr("yes", 0.95, 20), settled), scan_trade(tr("no", 0.05, 20), settled),
              scan_trade(tr("yes", 0.96, 25, n=30), settled)):
        acc.add(r)
    c = grid(acc)["KXBTC15M"][((16, 31), (0.95, 0.98))]
    ck(c[0] == 3 and c[1] == 1 and c[2] == 50.0 and c[3] == 10.0, "grid: 3 trades, 1 lost, 50 contracts of which 10 lost")
    ev = cell_ev(c)
    q, pm = 1 / 3, (0.95 + 0.95 + 0.96) / 3
    ck(abs(ev - ((1 - q) * (1 - pm) - q * pm - fee(pm))) < 1e-12, "cell EV = (1-q)(1-p) - q p - fee, at the cell's own mean price")
    ck(cell_ev([0, 0, 0, 0, 0]) is None, "NULL: an empty cell has no EV")
    # reversal: favourite YES at 60 s, market settled NO, late NO buyers were right
    tk2 = "KXSOL15M-26SEP161000-00"
    s2 = {tk2: 0.0}
    acc2 = Acc()
    for r in (scan_trade(tr("yes", 0.95, 60, ticker=tk2), s2),      # favourite YES, lost
              scan_trade(tr("no", 0.25, 20, ticker=tk2), s2),       # new side at 75c, won
              scan_trade(tr("no", 0.08, 5, ticker=tk2), s2)):       # new side at 92c, won
        acc2.add(r)
    flips, rv = reversal(acc2)
    ck(flips["KXSOL15M", "flips"] == 1 and flips["KXSOL15M", "markets"] == 1, "one market, one flip")
    ck(rv["KXSOL15M"][((16, 31), "70-90c")][0] == 1 and rv["KXSOL15M"][((16, 31), "70-90c")][1] == 0,
       "the new-side buyer at 75c with 20 s left is recorded as RIGHT")
    ck(rv["KXSOL15M"][((0, 6), "90c+")][0] == 1, "...and the 92c buyer at 5 s in the 90c+ bucket")
    acc3 = Acc()
    acc3.add(scan_trade(tr("yes", 0.95, 60, ticker=tk), settled))
    acc3.add(scan_trade(tr("yes", 0.97, 10, ticker=tk), settled))
    flips3, rv3 = reversal(acc3)
    ck(flips3["KXBTC15M", "flips"] == 0 and not rv3 and tk not in acc3.late,
       "NULL: the favourite WON -> no flip, no rows, and its late rows are NOT kept in memory")
    # THE LEAK: a market that never gets a favourite must not keep rows
    tk5 = "KXDOGE15M-26SEP161000-00"
    acc5 = Acc()
    acc5.add(scan_trade(tr("yes", 0.60, 50, ticker=tk5), {tk5: 1.0}))   # in the decision window, no favourite yet
    acc5.add(scan_trade(tr("yes", 0.62, 20, ticker=tk5), {tk5: 1.0}))   # past it, still no favourite
    ck(tk5 not in acc5.late and tk5 not in acc5.fav,
       "a market with no favourite at 60 s keeps NO late rows -- most markets are like this")
    # THE WOBBLE: what the favourite traded down to, conditioned on the visible price
    acc6 = Acc()
    # both on the SAME close as tr()'s timestamps: a ticker on a later close
    # would put every planted trade 900 s out and scan_trade would drop it
    tk6 = "KXXRP15M-26SEP161000-00"; tk7 = "KXETH15M-26SEP161000-00"
    s6 = {tk6: 0.0, tk7: 1.0}
    acc6.add(scan_trade(tr("yes", 0.95, 60, ticker=tk6), s6))   # favourite YES...
    acc6.add(scan_trade(tr("no", 0.45, 20, ticker=tk6), s6))    # ...someone buys NO at 45c: favourite implied 55c
    acc6.add(scan_trade(tr("yes", 0.95, 60, ticker=tk7), s6))   # favourite YES, holds
    acc6.add(scan_trade(tr("yes", 0.97, 10, ticker=tk7), s6))   # traded UP, min stays 95c
    ck(acc6.wob[tk6] == (0.55, 20) and acc6.wob[tk7] == (0.95, 60) or acc6.wob[tk7][0] == 0.95,
       "the wobble is the LOWEST price the favourite's side implied inside the window, from either side's trades")
    wb = wobble(acc6)
    ck(wb["KXXRP15M"][(0.50, 0.70)] == [1, 1] and wb["KXXRP15M"][(0.90, 1.01)] == [1, 0],
       "wobble to 50-70c: 1 market, favourite lost; stayed at 90c+: 1 market, favourite won -- conditioned on the price, not the outcome")
    # the accumulator survives a round trip through the cache
    acc4 = Acc.from_json(json.loads(json.dumps(acc6.to_json())))
    ck(wobble(acc4) == wobble(acc6) and grid(acc4) == grid(acc6) and acc4.fav == acc6.fav,
       "the cache round-trip preserves the grid, the favourites and the wobbles")
    print("pingrid selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--out", default=os.path.join(RESULTS, "RESULTS_grid.md"))
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    settled = load_settlements()
    closes = [pinflat.close_epoch(t) for t in settled]
    closes = [c for c in closes if c]
    lo, hi = min(closes), max(closes)
    print("settlements: %d markets, closes %s .. %s" % (
        len(settled), time.strftime("%m/%d %H:%MZ", time.gmtime(lo)), time.strftime("%m/%d %H:%MZ", time.gmtime(hi))))
    cache = {"hours": {}, "acc": None}
    if not a.rebuild:
        try:
            with open(CACHE, encoding="utf-8") as fh:
                cache = json.load(fh)
        except (OSError, ValueError):
            pass
    acc = Acc.from_json(cache["acc"]) if cache.get("acc") else Acc()

    def fhour(f):
        return calendar.timegm(time.strptime(os.path.basename(f)[:11], "%Y%m%dT%H"))
    files = [f for f in sorted(glob.glob(os.path.join(TAPE, "*.jsonl.gz")))
             if lo - 4 * 3600 <= fhour(f) <= hi + 3600]
    todo = [f for f in files if os.path.basename(f) not in cache["hours"]]
    print("tape hours in range %d, cached %d, to walk %d" % (len(files), len(files) - len(todo), len(todo)), flush=True)
    if todo:
        t0 = time.time()

        def checkpoint(done, acc_, bad):
            cache["acc"] = acc_.to_json()
            for f in done:
                cache["hours"][os.path.basename(f)] = 1
            tmp = CACHE + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(cache, fh)
                os.replace(tmp, CACHE)
            except OSError:
                return
            print("  ... %d/%d hours, %d cells, %d flip markets, %.0f s" % (
                len(done), len(todo), len(acc_.grid), sum(v for (s, k), v in acc_.markets.items() if k == "flips"),
                time.time() - t0), flush=True)
        walk(todo, settled, acc, on_progress=checkpoint)
    if not acc.grid:
        print("loaded nothing")
        return 0
    report(acc)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("# RESULTS -- the grid: who loses buying near-certainties, by seconds left and price; and the reversal screen\n\n")
        fh.write("Rebuilt %s from `research/pingrid.py`. TAPE population (rule 5): what the market did, never our loss rate.\n\n```\n"
                 % time.strftime("%Y-%m-%d %H:%MZ", time.gmtime()))
        report(acc, out=fh)
        fh.write("```\n")
    print("\nwrote %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
