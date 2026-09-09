#!/usr/bin/env python3
# VERSION: 2026-09-09-pdraw1
"""pindraw.py -- the hedge, re-run against DRAWDOWN instead of expected value.

WHY THIS FILE EXISTS AND WHY IT IS NOT pinhedge.py AGAIN

`pinhedge.py` asked "does hedging make more money?" and answered no. The
operator's objective is a different one, in his words:

    "losing small amounts of money (maybe 1-5 wins worth) a bit more frequently
     is better than one huge loss that takes tens to a hundred wins to earn
     back."

That is a DRAWDOWN objective, not an expected-value one. A rule that is
EV-neutral, or slightly EV-negative, can be correct under it. So every number
here is reported twice: in cents, and in WINS TO RECOVER -- loss divided by the
mean profit of a winning close in the same sample. A typical win is a few cents
per contract and a typical loss is most of a dollar, so one loss costs tens of
wins, and that ratio is the entire problem.

THREE THINGS THE EARLIER STUDY GOT WRONG OR NEVER TRIED, ALL FIXED HERE

1. PARTIAL HEDGES. pinhedge treated the hedge as all-or-nothing and rejected it
   because only 6 of 12 were deep enough for 20 contracts. Hedging 10 of 20
   still halves the loss on those 10. Here the hedge takes whatever depth
   exists, retries every remaining second, and the achieved fill fraction is
   reported.

2. THE OBJECTIVE. Worst single close, 5th and 1st percentile of the per-close
   P&L, and total profit -- for every trigger, in cents and in wins.

3. TRIGGERS THAT DO NOT USE THE MODEL. The model is the thing that was wrong on
   the losing close (it said 1.81%). So the headline trigger here is
   SPOT vs K_eff: once the index is on the wrong side of the effective strike,
   the bet is losing RIGHT NOW, and no probability estimate is involved.

THE DATA SOURCE IS NEW, AND IT IS BETTER FOR THIS QUESTION

Earlier hedge work used `results/pindata/rows.jsonl`, which is 44 hours of
order-book replay and carries the touch on ONE side (the model-favoured one).
The side we must BUY to hedge is the other one, so its depth could only be
bounded, never measured, and IDEAS_LOG #32 says so explicitly.

The `ticker` channel carries `yes_bid_dollars`, `yes_ask_dollars`,
`yes_bid_size_fp` and `yes_ask_size_fp` on every update, which is the touch AND
the touch size on BOTH sides. On a Kalshi binary the YES bid book IS the NO ask
book, so:

    buy YES: pay yes_ask,       up to yes_ask_size contracts
    buy NO : pay 1 - yes_bid,   up to yes_bid_size contracts

That is exactly the quantity a hedge study needs, it covers the whole 12-day
tape instead of 44 hours, and it costs ~0.3 s per hour-file to read instead of
~85 MB of order-book deltas. `--control-rows` scores it against the order-book
replay on the overlapping hours so the substitution is checked, not assumed.

WHAT IS STILL NOT MEASURED, STATED UP FRONT

* THE RACE FOR THE HEDGE. The backtest gives us the quote. In life we would be
  racing for it, and the hedge asks us to buy the side that is now WINNING --
  the harder side to buy, and the one IDEAS_LOG #29 found is often not offered
  at all. Every saving here is an upper bound.
* Depth is the TOUCH only. Deeper levels exist, so the achievable hedge size is
  a LOWER bound. These two errors point in opposite directions and neither is
  quantified here.
"""
import argparse
import array
import glob
import gzip
import json
import math
import os
import random
import sys
import time
import zlib
import calendar
from collections import defaultdict
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor, N_AVG                          # noqa: E402

ND = NormalDist()
DATA = r"C:\kals\kalshi_data"
FULLTAPE = r"C:\kals\fulltape\markets.json"
OUT = r"C:\kals-repo\results\pindraw"

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
    "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
}
ROUND_DIGITS = {"KXBTC15M": 2, "KXETH15M": 2, "KXBNB15M": 2,
                "KXSOL15M": 4, "KXXRP15M": 4, "KXZEC15M": 4,
                "KXHYPE15M": 4, "KXNEAR15M": 4, "KXDOGE15M": 7}

# ---- the live rule, copied from pinrun.py (2026-09-09 configuration) -------
PIN = 0.98
TAU_MIN, TAU_MAX = 3, 30
EDGE_FLOOR = 0.003
EV_FLOOR = 0.003
PRICE_CEILING = 0.988
MEASURED_FLIP = 0.0090
IMPROVE_BY = 0.005
MIN_LEVEL = 1.0
MIN_FILL_FRAC = 0.50
MAX_PER_CLOSE = 2
MAX_ATTEMPTS_PER_CLOSE = 8
SIGMA_WIN = 300
PANEL_TAU = 120          # seconds before close we model
MAX_QUOTE_AGE_MS = 10000
# WHY NOT 2000, WHICH IS WHAT pinrun USES. pinrun's MAX_BOOK_AGE_MS is a
# CONNECTION-HEALTH gate on a delta stream that ticks constantly. The `ticker`
# channel only publishes when the touch actually CHANGES, so a 5-second-old
# ticker message means "nothing has happened", not "we have lost the feed".
# Applying 2000 ms here would discard valid quotes; --max-quote-age-ms runs the
# sensitivity, and the age distribution is printed either way.


def billed_fee(p, n=1.0):
    """What Kalshi actually charges: ceil(0.07*p*(1-p)*n) to the next $0.0001."""
    return math.ceil(0.07 * float(p) * (1.0 - float(p)) * float(n) * 10000.0) \
        / 10000.0


def expected_value(price, flip=MEASURED_FLIP):
    p = float(price)
    return (1.0 - flip) * (1.0 - p) - flip * p - billed_fee(p, 1)


def eff_strike(strike, d):
    return float(strike) - 0.5 * (10.0 ** (-int(d))) if d is not None \
        else float(strike)


# ===========================================================================
# P&L ARITHMETIC.  Every hedge number in this file comes through here.
# ===========================================================================
def leg_pnl(n, entry_px, won, hedges=()):
    """Dollars for one position of `n` contracts bought at `entry_px`.

    `hedges` is a list of (qty, price) fills on the OPPOSITE side. On a Kalshi
    binary exactly one side pays $1.00, so h hedged contracts pay $1.00 when we
    LOSE and nothing when we win -- a hedge is not insurance that refunds a
    premium, it is a second bet that only pays if the first one fails.

        win :  n*(1 - entry) - sum(q*px) - fees
        lose: -n*entry       + sum(q*(1 - px)) - fees
    """
    n = float(n)
    fees = billed_fee(entry_px, n)
    hq = 0.0
    for q, px in hedges:
        fees += billed_fee(px, q)
        hq += float(q) * float(px)
    hn = sum(float(q) for q, _ in hedges)
    if won:
        return n * (1.0 - float(entry_px)) - hq - fees
    return -n * float(entry_px) + hn - hq - fees


# ===========================================================================
# INDEX: values + prefix sums so sigma and the locked window are O(1)
# ===========================================================================
class Index:
    """One index's per-second tape with the prefix sums every query needs."""

    __slots__ = ("base", "val", "pc", "ps", "dc", "ds", "dq")

    def __init__(self, base, val):
        self.base = base
        self.val = val
        n = len(val)
        pc = array.array("i", [0] * (n + 1))
        ps = array.array("d", [0.0] * (n + 1))
        dc = array.array("i", [0] * (n + 1))
        ds = array.array("d", [0.0] * (n + 1))
        dq = array.array("d", [0.0] * (n + 1))
        prev = float("nan")
        for i in range(n):
            v = val[i]
            ok = v == v
            pc[i + 1] = pc[i] + (1 if ok else 0)
            ps[i + 1] = ps[i] + (v if ok else 0.0)
            d = (v - prev) if (ok and prev == prev) else None
            dc[i + 1] = dc[i] + (1 if d is not None else 0)
            ds[i + 1] = ds[i] + (d if d is not None else 0.0)
            dq[i + 1] = dq[i] + (d * d if d is not None else 0.0)
            if ok:
                prev = v
        self.pc, self.ps, self.dc, self.ds, self.dq = pc, ps, dc, ds, dq

    def at(self, sec):
        i = sec - self.base
        if i < 0 or i >= len(self.val):
            return None
        v = self.val[i]
        return v if v == v else None

    def spot(self, sec, back=5):
        """Newest print at or before `sec`, within `back` seconds."""
        for s in range(sec, sec - back - 1, -1):
            v = self.at(s)
            if v is not None:
                return v, sec - s
        return None, None

    def sigma(self, sec, win=SIGMA_WIN):
        """Sample sd of consecutive 1-second increments over the last `win` s."""
        i = sec - self.base
        if i < win or i >= len(self.val):
            return None
        a, b = i - win + 1, i + 1
        n = self.dc[b] - self.dc[a]
        if n < 20:
            return None
        s = self.ds[b] - self.ds[a]
        q = self.dq[b] - self.dq[a]
        var = (q - s * s / n) / (n - 1)
        return math.sqrt(var) if var > 0 else 0.0

    def partial(self, close_s, now_s):
        """(locked sum, prints still to come) over [close-60, close-1].

        Matches pinrun.IndexState.partial: the locked window ends at the newest
        print actually held, and every second after it is `remaining`.
        """
        lo = close_s - N_AVG
        hi = min(now_s, close_s - 1)
        if hi < lo:
            return 0.0, N_AVG
        i0, i1 = lo - self.base, hi - self.base
        if i0 < 0 or i1 >= len(self.val):
            return None
        while i1 >= i0 and not (self.val[i1] == self.val[i1]):
            i1 -= 1
        if i1 < i0:
            return None
        want = i1 - i0 + 1
        got = self.pc[i1 + 1] - self.pc[i0]
        if got < want * 0.95:
            return None
        tot = self.ps[i1 + 1] - self.ps[i0]
        if got < want:                       # interior gaps: nearest print
            miss = 0.0
            for i in range(i0, i1 + 1):
                if not (self.val[i] == self.val[i]):
                    lft = rgt = None
                    for j in range(i - 1, i0 - 1, -1):
                        if self.val[j] == self.val[j]:
                            lft = j
                            break
                    for j in range(i + 1, i1 + 1):
                        if self.val[j] == self.val[j]:
                            rgt = j
                            break
                    c = [x for x in (lft, rgt) if x is not None]
                    k = min(c, key=lambda x: (abs(x - i), x))
                    miss += self.val[k]
            tot += miss
        return tot, N_AVG - want

    def settle(self, close_s):
        """The settlement average from the tape: mean of [close-60, close-1]."""
        p = self.partial(close_s, close_s - 1)
        if p is None or p[1] != 0:
            return None
        return p[0] / N_AVG


def hour_epoch(path):
    b = os.path.basename(path)[:11]               # 20260904T12
    return calendar.timegm(time.strptime(b, "%Y%m%dT%H"))


def pick_files(channel, lo_s, hi_s, hours=0):
    """Hour-files whose hour overlaps [lo_s, hi_s]; the newest `hours` of them.

    The live tape runs days past the newest SETTLED market, so taking "the last
    N hours" of the tape can select a window with no outcomes in it at all --
    which is exactly what the first run of this file did, and it reported zero
    closes rather than pretending. Bound by the settlement range instead.
    """
    fs = sorted(glob.glob(os.path.join(DATA, channel, "2026*.jsonl.gz")))[:-1]
    fs = [f for f in fs if hour_epoch(f) + 3600 > lo_s and hour_epoch(f) < hi_s]
    return fs[-hours:] if hours else fs


def load_index(files, verbose=True):
    if not files:
        return {}, []

    t0 = hour_epoch(files[0])
    t1 = hour_epoch(files[-1]) + 3600
    span = t1 - t0
    raw = {}
    for k, f in enumerate(files):
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    if '"cfbenchmarks_value"' not in line:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                        dd = json.loads(m["data"])
                        iid = m["index_id"]
                        s = int(dd["time"]) // 1000
                    except Exception:
                        continue
                    if iid not in SERIES_TO_INDEX.values():
                        continue
                    i = s - t0
                    if i < 0 or i >= span:
                        continue
                    a = raw.get(iid)
                    if a is None:
                        a = raw[iid] = array.array("d", [float("nan")] * span)
                    a[i] = float(dd["value"])
        except (EOFError, zlib.error, OSError):
            pass
        if verbose and (k + 1) % 50 == 0:
            print(f"    index {k+1}/{len(files)}", flush=True)
    out = {}
    for iid, a in raw.items():
        out[iid] = Index(t0, a)
    raw.clear()
    return out, files


# ===========================================================================
# TICKER: the touch and its size on BOTH sides
# ===========================================================================
def parse_ticker_line(line):
    try:
        m = json.loads(line)["msg"]
    except Exception:
        return None
    tk = m.get("market_ticker")
    if not tk:
        return None
    try:
        ts = int(m.get("ts_ms") or 0)
        yb = float(m.get("yes_bid_dollars"))
        ya = float(m.get("yes_ask_dollars"))
        ybs = float(m.get("yes_bid_size_fp") or 0.0)
        yas = float(m.get("yes_ask_size_fp") or 0.0)
    except (TypeError, ValueError):
        return None
    return tk, ts, yb, ya, ybs, yas


class Quotes:
    """Per-second carry-forward of the touch, over [close-PANEL_TAU, close-1]."""

    __slots__ = ("lo", "yb", "ya", "ybs", "yas", "age", "n_msg")

    def __init__(self, close_s, msgs, span=PANEL_TAU):
        self.lo = close_s - span
        n = span
        nan = float("nan")
        self.yb = [nan] * n
        self.ya = [nan] * n
        self.ybs = [0.0] * n
        self.yas = [0.0] * n
        self.age = [None] * n
        self.n_msg = len(msgs)
        msgs = sorted(msgs, key=lambda x: x[0])
        j = 0
        cur = None
        for i in range(n):
            sec = self.lo + i
            while j < len(msgs) and msgs[j][0] // 1000 <= sec:
                cur = msgs[j]
                j += 1
            if cur is None:
                continue
            self.yb[i] = cur[1]
            self.ya[i] = cur[2]
            self.ybs[i] = cur[3]
            self.yas[i] = cur[4]
            self.age[i] = sec * 1000 + 999 - cur[0]

    def get(self, sec):
        i = sec - self.lo
        if i < 0 or i >= len(self.yb):
            return None
        if not (self.yb[i] == self.yb[i]):
            return None
        return (self.yb[i], self.ya[i], self.ybs[i], self.yas[i], self.age[i])


# ===========================================================================
# THE PANEL: one row per (market, second)
# ===========================================================================
def build_panel(mk, ix, qs, span=PANEL_TAU):
    """[(tau, spot, mu, K, fair, sigma, yb, ya, ybs, yas, age)] newest last."""
    close_s = mk["close_s"]
    K = mk["K"]
    out = []
    for tau in range(span, 0, -1):
        sec = close_s - tau
        spot, sage = ix.spot(sec)
        if spot is None or sage is None or sage > 2:
            continue
        sg = ix.sigma(sec)
        if sg is None:
            continue
        p = ix.partial(close_s, sec)
        if p is None:
            continue
        locked, r = p
        mu = (locked + r * spot) / N_AVG
        if r <= 0:
            fair = 1.0 if mu >= K else 0.0
        else:
            sd = sg * math.sqrt(var_factor(int(r), [1.0]))
            fair = (1.0 if mu >= K else 0.0) if sd <= 0 \
                else ND.cdf((mu - K) / sd)
        q = qs.get(sec) if qs is not None else None
        yb, ya, ybs, yas, age = q if q else (None, None, 0.0, 0.0, None)
        out.append((tau, spot, mu, K, fair, sg, yb, ya, ybs, yas, age))
    return out


# ===========================================================================
# ENTRY: the live rule, reproduced
# ===========================================================================
def entries_for_close(panels, size, cap=MAX_PER_CLOSE, tau_max=None):
    """panels: {ticker: (mk, rows)}. Returns the buys the live rule would make.

    The live loop scans every market ~20x a second and takes the first moment
    that clears every gate, capped at `cap` fills per CLOSE with each later buy
    at least IMPROVE_BY cheaper. Reproduced here on a 1-second grid; ties inside
    one second go to the larger edge.
    """
    tmax = TAU_MAX if tau_max is None else int(tau_max)
    ev_list = []
    for tk, (mk, rows) in panels.items():
        for row in rows:
            tau, spot, mu, K, fair, sg, yb, ya, ybs, yas, age = row
            if not (TAU_MIN <= tau <= tmax):
                continue
            if yb is None or age is None or age > MAX_QUOTE_AGE_MS:
                continue
            if fair >= PIN:
                want, price, avail = "yes", ya, yas
            elif fair <= 1.0 - PIN:
                want, price, avail = "no", round(1.0 - yb, 4), ybs
            else:
                continue
            if price is None or not (0.0 < price < 1.0) or avail <= 0:
                continue
            take = min(float(size), float(avail))
            if take < max(MIN_LEVEL, MIN_FILL_FRAC * float(size)):
                continue
            gross = (fair - price) if want == "yes" else ((1.0 - fair) - price)
            edge = gross - billed_fee(price, size) / float(size)
            if edge < EDGE_FLOOR:
                continue
            if price > PRICE_CEILING:
                continue
            if expected_value(price) < EV_FLOOR:
                continue
            ev_list.append((tau, -edge, tk, want, price, take, fair, row))
    ev_list.sort(key=lambda x: (-x[0], x[1]))       # earliest second first
    buys = []
    best = None
    tries = 0
    for tau, negedge, tk, want, price, take, fair, row in ev_list:
        if len(buys) >= cap or tries >= MAX_ATTEMPTS_PER_CLOSE:
            break
        if best is not None and price >= best - IMPROVE_BY:
            continue
        tries += 1
        best = price if best is None else min(best, price)
        buys.append({"tk": tk, "tau": tau, "want": want, "price": price,
                     "n": take, "fair": fair, "edge": -negedge})
    return buys


# ===========================================================================
# TRIGGERS.  A trigger is fired(row, pos) -> bool, evaluated every second after
# entry. None of the first four uses a probability model.
# ===========================================================================
def make_triggers():
    """name -> (fn(row, pos) -> bool, one-line description)."""
    T = {}

    def spot_wrong(row, pos):
        tau, spot, mu, K = row[0], row[1], row[2], row[3]
        return (spot < K) if pos["want"] == "yes" else (spot >= K)

    T["SPOT_CROSS"] = (spot_wrong,
                       "the index itself is on the wrong side of K_eff")

    for d in (2, 3, 5):
        def f(row, pos, d=d):
            return pos["_wrong_run"] >= d
        T[f"SPOT_CROSS_HOLD{d}"] = (
            f, f"the index has been on the wrong side for {d} seconds running")

    def mu_wrong(row, pos):
        mu, K = row[2], row[3]
        return (mu < K) if pos["want"] == "yes" else (mu >= K)

    T["MU_CROSS"] = (mu_wrong,
                     "the projected settlement (locked prints + spot) has "
                     "crossed K_eff -- arithmetic, no probability")

    for d in (2, 3):
        def f(row, pos, d=d):
            return pos["_mu_run"] >= d
        T[f"MU_CROSS_HOLD{d}"] = (
            f, f"the projected settlement has been the wrong side of K_eff "
               f"for {d} seconds running")

    def both_wrong(row, pos):
        return mu_wrong(row, pos) and spot_wrong(row, pos)
    T["MU_AND_SPOT"] = (both_wrong,
                        "the projected settlement AND the index are both on "
                        "the wrong side")

    for drop in (0.05, 0.15, 0.30):
        def f(row, pos, drop=drop):
            m = pos["_mkt"]
            return m is not None and m <= pos["price"] - drop
        T[f"PRICE_DROP{int(100*drop)}"] = (
            f, f"the market's bid for our side has fallen {100*drop:.0f}c "
               f"below what we paid")

    def mkt_below(row, pos):
        m, f = pos["_mkt"], row[4]
        fv = f if pos["want"] == "yes" else 1.0 - f
        return m is not None and m < fv - 0.10
    T["MKT_UNDER_US"] = (mkt_below,
                         "the market's implied chance for our side is 10c "
                         "below our model's")

    for tau_n, xs in ((10, 0.5), (10, 1.0), (20, 1.0)):
        def f(row, pos, tau_n=tau_n, xs=xs):
            tau, spot, mu, K, fair, sg = row[0], row[1], row[2], row[3], \
                row[4], row[5]
            return tau <= tau_n and sg > 0 and abs(spot - K) < xs * sg * \
                math.sqrt(max(int(round(tau)), 1))
        T[f"NEARLINE_T{tau_n}_S{int(10*xs)}"] = (
            f, f"at tau<={tau_n}s the index is within {xs:g} sigma*sqrt(tau) "
               f"of K_eff")

    for c in (0.10, 0.50, 0.90):
        def f(row, pos, c=c):
            fair = row[4]
            pl = (1.0 - fair) if pos["want"] == "yes" else fair
            return pl >= c
        T[f"MODEL_P{int(100*c)}"] = (
            f, f"the MODEL's chance we lose has reached {100*c:.0f}% "
               f"(the earlier study's rule, for comparison)")
    return T


# ===========================================================================
# HEDGE SIMULATION
# ===========================================================================
def run_hedge(pos, rows, trig, size_frac=1.0, retry=True, max_px=None):
    """Walk the seconds after entry; fire once; buy what depth allows.

    `max_px` is the operator's original idea taken literally -- "buy the 5 cent
    other side". Above that price the hedge is refused, because a hedge at 90c
    on a 95c entry does not cap a loss, it CONFIRMS one: it locks -85c against
    an unhedged -95c. The refusal is recorded, not hidden: a firing with no fill
    still counts as a firing.

    Returns (hedges, fired_tau, want_n). `hedges` is [(qty, price)].
    """
    want_n = float(pos["n"]) * float(size_frac)
    got = 0.0
    hedges = []
    fired = None
    pos["_wrong_run"] = 0
    pos["_mu_run"] = 0
    for row in rows:
        tau, spot, mu, K, fair, sg, yb, ya, ybs, yas, age = row
        if tau >= pos["tau"]:
            continue
        if tau < 1:
            break
        wrong = (spot < K) if pos["want"] == "yes" else (spot >= K)
        pos["_wrong_run"] = pos["_wrong_run"] + 1 if wrong else 0
        mwrong = (mu < K) if pos["want"] == "yes" else (mu >= K)
        pos["_mu_run"] = pos.get("_mu_run", 0) + 1 if mwrong else 0
        if yb is None or age is None or age > MAX_QUOTE_AGE_MS:
            pos["_mkt"] = None
        else:
            pos["_mkt"] = yb if pos["want"] == "yes" else round(1.0 - ya, 4)
        if fired is None:
            if not trig(row, pos):
                continue
            fired = tau
        # fired: buy the OPPOSITE side at the touch, as much as is there
        if yb is None or age is None or age > MAX_QUOTE_AGE_MS:
            if not retry:
                break
            continue
        if pos["want"] == "yes":
            px, avail = round(1.0 - yb, 4), ybs        # buy NO
        else:
            px, avail = ya, yas                        # buy YES
        if max_px is not None and px is not None and px > max_px + 1e-12:
            if not retry:
                break
            continue
        if px is not None and 0.0 < px < 1.0 and avail > 0:
            q = min(want_n - got, float(avail))
            if q > 1e-9:
                hedges.append((q, px))
                got += q
        if got >= want_n - 1e-9 or not retry:
            break
    return hedges, fired, want_n


# ===========================================================================
# METRICS
# ===========================================================================
def pct(vals, p):
    if not vals:
        return None
    v = sorted(vals)
    k = (len(v) - 1) * (p / 100.0)
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return v[lo] if lo == hi else v[lo] + (v[hi] - v[lo]) * (k - lo)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def summarise(per_close, win_unit):
    """per_close: {close_s: pnl}. Returns the operator's dashboard."""
    v = list(per_close.values())
    if not v:
        return None
    tot = sum(v)
    losses = [-x for x in v if x < 0]
    worst = -min(v) if min(v) < 0 else 0.0
    return {
        "closes": len(v), "total": tot, "n_loss": len(losses),
        "worst": worst, "p95": (pct(v, 5.0) or 0.0), "p99": (pct(v, 1.0) or 0.0),
        "worst_w": worst / win_unit if win_unit > 0 else float("nan"),
        "p95_w": -(pct(v, 5.0) or 0.0) / win_unit if win_unit > 0 else 0.0,
        "p99_w": -(pct(v, 1.0) or 0.0) / win_unit if win_unit > 0 else 0.0,
        "mean_loss": sum(losses) / len(losses) if losses else 0.0,
    }


# ===========================================================================
# SELF-TEST
# ===========================================================================
def _mk_index(base, vals):
    return Index(base, array.array("d", vals))


def selftest():
    print("SELF-TEST -- pindraw")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # ---- 1. the P&L arithmetic, which everything else is divided by --------
    ck(abs(leg_pnl(1, 0.95, True) - (0.05 - billed_fee(0.95, 1))) < 1e-12,
       "an unhedged win pays 1 - price, minus the fee")
    ck(abs(leg_pnl(1, 0.95, False) - (-0.95 - billed_fee(0.95, 1))) < 1e-12,
       "an unhedged loss costs the whole price, plus the fee")
    full = leg_pnl(1, 0.95, False, [(1, 0.03)])
    ck(abs(full - (1 - 0.95 - 0.03 - billed_fee(0.95, 1) -
                   billed_fee(0.03, 1))) < 1e-12,
       f"hedging ALL of a 95c position at 3c locks +{100*full:.2f}c whatever "
       f"happens")
    ck(abs(leg_pnl(1, 0.95, True, [(1, 0.03)]) - full) < 1e-12,
       "and the hedged outcome is IDENTICAL on a win and a loss -- that "
       "identity is what makes a full hedge a certainty, not a bet")
    half = leg_pnl(20, 0.95, False, [(10, 0.03)])
    none = leg_pnl(20, 0.95, False)
    ck(abs(half - (none + 10 * (1 - 0.03) - billed_fee(0.03, 10))) < 1e-9,
       f"a PARTIAL hedge of 10 of 20 recovers "
       f"{100*(half-none):.1f}c of a {100*none:.1f}c loss -- the thing the "
       f"earlier study never measured")
    ck(none < half < 0,
       "half-hedging a loser is better than not hedging and still a loss")
    ck(leg_pnl(20, 0.95, True, [(10, 0.90)]) < leg_pnl(20, 0.95, True),
       "and on a WINNER the same hedge is pure cost -- a 90c hedge that "
       "expires worthless is the false alarm this study has to price")

    # ---- 2. the index maths -----------------------------------------------
    ix = _mk_index(1000, [100.0] * 700)
    ck(ix.sigma(1600) == 0.0, "a dead-flat index has zero volatility")
    saw = [100.0 + (i % 2) * 0.2 for i in range(700)]
    ix2 = _mk_index(1000, saw)
    s = ix2.sigma(1600)
    ck(s is not None and 0.15 < s < 0.25,
       f"a +/-0.2 sawtooth gives sigma ~0.2 ({s:.4f})")
    p = ix.partial(1600, 1590)
    ck(p is not None and p[1] == 9,
       f"at tau=10 there are 9 prints still to come ({p[1] if p else None})")
    ck(abs(ix.settle(1600) - 100.0) < 1e-12,
       "settlement is the mean of the 60 prints in [close-60, close-1]")
    # a market whose index steps up by 1.0 at close-30 settles halfway
    step = [100.0] * 700
    for i in range(1600 - 1000 - 30, 700):
        step[i] = 101.0
    ix3 = _mk_index(1000, step)
    ck(abs(ix3.settle(1600) - 100.5) < 1e-9,
       f"a +1.0 step 30s before close settles at 100.5 "
       f"({ix3.settle(1600):.4f}) -- the locked half still counts")

    # ---- 3. quote plumbing ------------------------------------------------
    q = Quotes(1600, [(1599 * 1000, 0.5, 0.6, 1.0, 1.0)], span=4)
    ck(q.get(1596) is None,
       "a second BEFORE the first quote arrived has no quote, and is not "
       "back-filled from a later one")
    ck(q.get(1599) is not None, "and the second it arrives does")
    q2 = Quotes(1600, [((1596) * 1000 + 250, 0.94, 0.96, 30.0, 12.0)], span=4)
    g = q2.get(1597)
    ck(g is not None and g[0] == 0.94 and g[3] == 12.0,
       "a quote is carried forward to later seconds")
    ck(g is not None and 700 < g[4] < 1800,
       f"and its age is measured, not assumed ({g[4] if g else None} ms)")

    # ---- 4. THE ESTIMATOR ON A PLANTED WORLD ------------------------------
    # 40 positions bought at 95c. In 10 of them the index crosses K at tau 20
    # and NEVER comes back, so the crossing is a perfect loss signal, and the
    # other side is on offer at 20c in size. SPOT_CROSS must (a) fire on all
    # ten, (b) fire on none of the thirty winners, (c) cut the worst close.
    T = make_triggers()
    trig = T["SPOT_CROSS"][0]
    planted = []
    for i in range(40):
        lose = i < 10
        rows = []
        for tau in range(30, 0, -1):
            spot = 99.0 if (lose and tau <= 20) else 101.0
            rows.append((tau, spot, spot, 100.0, 0.02 if lose and tau <= 20
                         else 0.995, 0.5, 0.80, 0.82, 500.0, 500.0, 100))
        planted.append(({"tk": f"P{i}", "tau": 30, "want": "yes",
                         "price": 0.95, "n": 20.0}, rows, not lose))
    fired = sum(1 for pos, rows, won in planted
                if run_hedge(dict(pos), rows, trig)[1] is not None)
    ck(fired == 10, f"planted world: the crossing trigger fires on exactly the "
                    f"10 losers ({fired})")
    nh = {}
    hh = {}
    for i, (pos, rows, won) in enumerate(planted):
        nh[i] = leg_pnl(pos["n"], pos["price"], won)
        h, _, _ = run_hedge(dict(pos), rows, trig)
        hh[i] = leg_pnl(pos["n"], pos["price"], won, h)
    wu = sum(x for x in nh.values() if x > 0) / \
        max(1, sum(1 for x in nh.values() if x > 0))
    a, b = summarise(nh, wu), summarise(hh, wu)
    ck(b["worst"] < a["worst"],
       f"planted world: the worst close falls from ${a['worst']:.2f} to "
       f"${b['worst']:.2f}")
    ck(b["worst_w"] < a["worst_w"] and a["worst_w"] > 5,
       f"and in the operator's unit from {a['worst_w']:.1f} wins to "
       f"{b['worst_w']:.1f} wins to recover")
    ck(abs(b["total"] - a["total"]) > 1e-6 and b["total"] > a["total"],
       "on a world where the signal is perfect the hedge also makes money, "
       "so a rule that shows NO improvement here is broken")

    # ---- 5. THE SAME ESTIMATOR ON A NULL WORLD ----------------------------
    # Crossings happen just as often, but they carry NO information: the
    # outcome is laid out so that P(lose | crossed) == P(lose | not crossed)
    # EXACTLY, and the hedge is quoted at its fair 25c. Nothing is random, so
    # this is a fact about the estimator and not a coin flip that happened to
    # land well. Two things must then be true:
    #   (a) the crossing must not look predictive, and
    #   (b) the hedge must lose EXACTLY the fees -- a fairly-priced hedge on an
    #       uninformative trigger is a fee-generating machine and nothing else.
    null_nh, null_hh = {}, {}
    cross_loss = cross_n = nocross_loss = nocross_n = 0
    hedge_fees = 0.0
    for i in range(400):
        crossed = (i % 4 == 0)                  # 100 of 400
        won = not ((i // 4) % 4 == 0)           # 100 of 400 lose, independent
        rows = []
        for tau in range(30, 0, -1):
            spot = 99.0 if (crossed and tau <= 20) else 101.0
            # yes_bid 0.75 => the NO we would buy costs exactly 25c, which is
            # the true chance of losing. A fair price is what makes this a null.
            rows.append((tau, spot, spot, 100.0, 0.5, 0.5,
                         0.75, 0.77, 500.0, 500.0, 100))
        pos = {"tk": f"N{i}", "tau": 30, "want": "yes", "price": 0.95,
               "n": 20.0}
        null_nh[i] = leg_pnl(20.0, 0.95, won)
        h, ft, _ = run_hedge(dict(pos), rows, trig)
        null_hh[i] = leg_pnl(20.0, 0.95, won, h)
        if ft is not None:
            cross_n += 1
            cross_loss += 0 if won else 1
            hedge_fees += sum(billed_fee(px, q) for q, px in h)
        else:
            nocross_n += 1
            nocross_loss += 0 if won else 1
    pc = cross_loss / max(cross_n, 1)
    pn = nocross_loss / max(nocross_n, 1)
    lo, hi = wilson(cross_loss, cross_n)
    ck(abs(pc - pn) < 1e-12 and lo <= pn <= hi,
       f"null world: P(lose | crossing) {pc:.3f} == P(lose | no crossing) "
       f"{pn:.3f} exactly, CI [{lo:.3f}, {hi:.3f}] -- the estimator finds "
       f"NOTHING where nothing is planted")
    diff = sum(null_hh.values()) - sum(null_nh.values())
    ck(abs(diff + hedge_fees) < 1e-6 and diff < 0,
       f"and a FAIRLY PRICED hedge on that useless trigger costs exactly the "
       f"fees (${diff:.4f} vs -${hedge_fees:.4f}) -- no more, no less")
    ck(cross_n == 100,
       f"the null fires on 100 of 400 positions ({cross_n}), so the test has "
       f"something to be wrong about")

    # ---- 6. entry rule ----------------------------------------------------
    def _row(tau, fair, ya, yas):
        return (tau, 100.0, 100.0, 99.0, fair, 0.1, ya - 0.01, ya, 50.0, yas,
                100)
    good = {"A": ({"tk": "A"}, [_row(20, 0.995, 0.95, 50.0)])}
    b = entries_for_close(good, 20)
    ck(len(b) == 1 and b[0]["price"] == 0.95,
       f"the live rule buys a 95c offer the model calls 99.5% ({b})")
    dear = {"A": ({"tk": "A"}, [_row(20, 0.9999, 0.995, 50.0)])}
    ck(entries_for_close(dear, 20) == [],
       "and refuses 99.5c, which is past the price ceiling AND negative EV")
    late = {"A": ({"tk": "A"}, [_row(45, 0.995, 0.95, 50.0)])}
    ck(entries_for_close(late, 20) == [],
       "and refuses tau=45, outside the frozen window")
    thin = {"A": ({"tk": "A"}, [_row(20, 0.995, 0.95, 3.0)])}
    ck(entries_for_close(thin, 20) == [],
       "and refuses a 3-contract offer at size 20 (below MIN_FILL_FRAC)")
    two = {"A": ({"tk": "A"}, [_row(20, 0.995, 0.95, 50.0),
                               _row(15, 0.995, 0.90, 50.0),
                               _row(10, 0.995, 0.899, 50.0)])}
    bb = entries_for_close(two, 20)
    ck(len(bb) == 2 and abs(bb[1]["price"] - 0.90) < 1e-9,
       f"scale-in takes the second buy only when it is IMPROVE_BY cheaper "
       f"({[round(x['price'],4) for x in bb]})")

    # ---- 7. partial-depth hedging, the headline fix -----------------------
    rows = [(t, 99.0, 99.0, 100.0, 0.02, 0.5, 0.80, 0.82, 7.0, 7.0, 100)
            for t in range(29, 0, -1)]
    pos = {"tk": "X", "tau": 30, "want": "yes", "price": 0.95, "n": 20.0}
    h, ft, wn = run_hedge(dict(pos), rows, trig, retry=False)
    ck(sum(q for q, _ in h) == 7.0,
       f"with only 7 contracts at the touch a single shot hedges 7 of 20 "
       f"({sum(q for q, _ in h)}) -- the all-or-nothing rule scored this as "
       f"ZERO and threw the position away")
    h2, _, _ = run_hedge(dict(pos), rows, trig, retry=True)
    ck(sum(q for q, _ in h2) == 20.0,
       f"and retrying each remaining second completes it "
       f"({sum(q for q, _ in h2)})")
    ck(leg_pnl(20, 0.95, False, h) > leg_pnl(20, 0.95, False),
       "a 7-of-20 hedge still beats no hedge on a loser")

    # ---- 8. the PRICE CAP, which is the operator's idea taken literally ---
    dear = [(t, 99.0, 99.0, 100.0, 0.02, 0.5, 0.10, 0.90, 500.0, 500.0, 100)
            for t in range(29, 0, -1)]
    posd = {"tk": "D", "tau": 30, "want": "yes", "price": 0.95, "n": 20.0}
    h9, ft9, _ = run_hedge(dict(posd), dear, trig, max_px=0.25)
    ck(ft9 is not None and h9 == [],
       f"the trigger FIRES but a 90c hedge is refused under a 25c cap "
       f"(fired at tau {ft9}, {len(h9)} fills) -- a refusal is still a firing "
       f"and must be counted as one")
    h10, _, _ = run_hedge(dict(posd), dear, trig, max_px=0.95)
    ck(sum(q for q, _ in h10) == 20.0,
       "and the same hedge is taken when the cap allows it")
    cheapr = [(t, 99.0, 99.0, 100.0, 0.02, 0.5, 0.85, 0.15, 500.0, 500.0, 100)
              for t in range(29, 0, -1)]
    h11, _, _ = run_hedge(dict(posd), cheapr, trig, max_px=0.25)
    ck(abs(leg_pnl(20, 0.95, False, h11) - (-20 * 0.95 + 20 * (1 - 0.15)
                                            - billed_fee(0.95, 20)
                                            - billed_fee(0.15, 20))) < 1e-9,
       f"a 15c hedge under a 25c cap turns a -$19.07 loss into "
       f"${leg_pnl(20, 0.95, False, h11):.2f}")

    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


# ===========================================================================
def load_markets():
    mk = []
    for v in json.load(open(FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] not in SERIES_TO_INDEX:
                continue
            d = ROUND_DIGITS.get(r["series"])
            mk.append({"tk": r["ticker"], "sr": r["series"],
                       "close_s": int(float(r["close"])),
                       "strike": float(r["strike"]),
                       "K": eff_strike(r["strike"], d),
                       "won_yes": float(r["result"]) >= 0.5})
    return mk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=0, help="0 = all available")
    ap.add_argument("--size", type=float, default=20.0)
    ap.add_argument("--tau-wide", type=int, default=90,
                    help="entry window for the POWERED sample")
    ap.add_argument("--cap", type=int, default=MAX_PER_CLOSE,
                    help="buys per close (live is 2; it was 3 on the losing "
                         "close)")
    ap.add_argument("--max-quote-age-ms", type=int, default=MAX_QUOTE_AGE_MS)
    ap.add_argument("--control-rows",
                    default=r"C:\kals-repo\results\pindata\rows.jsonl",
                    help="order-book replay to score the ticker touch against")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    globals()["MAX_QUOTE_AGE_MS"] = int(a.max_quote_age_ms)
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    os.makedirs(a.out, exist_ok=True)
    t_start = time.time()
    mks = load_markets()
    bt = {}
    for m in mks:
        bt[m["tk"]] = m
    lo_s = min(m["close_s"] for m in mks) - 400
    hi_s = max(m["close_s"] for m in mks)
    print(f"\n  {len(mks):,} settled markets on the 9 crypto series, closes "
          f"{time.strftime('%Y-%m-%d %H:%MZ', time.gmtime(lo_s))} -> "
          f"{time.strftime('%Y-%m-%d %H:%MZ', time.gmtime(hi_s))}")
    tfiles = pick_files("ticker", lo_s, hi_s, a.hours)
    if not tfiles:
        raise SystemExit("no ticker files overlap the settled range")
    lo_s = max(lo_s, hour_epoch(tfiles[0]))
    print("  loading index ...", flush=True)
    idx, ifiles = load_index(pick_files("cfbenchmarks_value",
                                        lo_s - 400, hi_s))
    print(f"  {len(idx)} indices from {len(ifiles)} hour-files "
          f"({time.time()-t_start:.0f}s)")
    print(f"  {len(tfiles)} ticker hour-files\n", flush=True)

    SER = tuple(SERIES_TO_INDEX)
    buf = defaultdict(list)
    by_close = defaultdict(list)
    for m in mks:
        by_close[m["close_s"]].append(m)

    # ---- the two samples we will carry -----------------------------------
    positions = {"LIVE": [], "WIDE": []}
    stageA = {"n": 0, "cross": 0, "cross_lose": 0, "nocross": 0,
              "nocross_lose": 0, "byt": defaultdict(lambda: [0, 0]),
              "run": defaultdict(lambda: [0, 0]), "mucross": 0,
              "mucross_lose": 0, "recross": 0, "closes": set(),
              "gt5": [0, 0], "stuck": [0, 0]}
    skipped = defaultdict(int)
    quote_ages = []

    # the ORDER-BOOK replay, used only as a control on the ticker touch
    ctrl_want = {}
    if a.control_rows and os.path.exists(a.control_rows):
        with open(a.control_rows, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                ctrl_want[(r["tk"], r["sec"])] = (r["price"],
                                                  bool(r["side_yes"]))
        print(f"  control: {len(ctrl_want):,} order-book cells loaded")
    ctrl = [0, 0, [], 0]          # n, agree, |diff|, absent

    def finalise(close_s):
        rows_of = {}
        for m in by_close.get(close_s, ()):
            ix = idx.get(SERIES_TO_INDEX[m["sr"]])
            if ix is None:
                skipped["no_index"] += 1
                continue
            msgs = buf.pop(m["tk"], None)
            qs = Quotes(close_s, msgs, PANEL_TAU) if msgs else None
            rows = build_panel(m, ix, qs, PANEL_TAU)
            if not rows:
                skipped["no_panel"] += 1
                continue
            rows_of[m["tk"]] = (m, rows)
            # ---------- STAGE A: crossings, book-free --------------------
            held = None
            for r in rows:
                if TAU_MIN <= r[0] <= TAU_MAX:
                    if r[4] >= PIN:
                        held = "yes"
                        break
                    if r[4] <= 1.0 - PIN:
                        held = "no"
                        break
            if held is None:
                continue
            lose = (held == "yes") != m["won_yes"]
            stageA["n"] += 1
            stageA["closes"].add(close_s)
            first_cross = None
            run = 0
            mucross = False
            for r in rows:
                if r[0] > TAU_MAX or r[0] < 1:
                    continue
                wrong = (r[1] < r[3]) if held == "yes" else (r[1] >= r[3])
                if wrong and first_cross is None:
                    first_cross = r[0]
                run = run + 1 if wrong else 0
                if held == "yes":
                    mucross = mucross or (r[2] < r[3])
                else:
                    mucross = mucross or (r[2] >= r[3])
            if first_cross is None:
                stageA["nocross"] += 1
                stageA["nocross_lose"] += 1 if lose else 0
            else:
                stageA["cross"] += 1
                stageA["cross_lose"] += 1 if lose else 0
                b = 5 if first_cross <= 5 else (10 if first_cross <= 10 else
                                                (20 if first_cross <= 20
                                                 else 30))
                stageA["byt"][b][0] += 1
                stageA["byt"][b][1] += 1 if lose else 0
                if first_cross > 5:
                    stageA["gt5"][0] += 1
                    stageA["gt5"][1] += 1 if lose else 0
                rb = 0 if run == 0 else (1 if run <= 2 else
                                         (3 if run <= 5 else
                                          (6 if run <= 10 else 11)))
                stageA["run"][rb][0] += 1
                stageA["run"][rb][1] += 1 if lose else 0
                if run >= 1:
                    stageA["stuck"][0] += 1
                    stageA["stuck"][1] += 1 if lose else 0
                else:
                    stageA["recross"] += 1
            if mucross:
                stageA["mucross"] += 1
                stageA["mucross_lose"] += 1 if lose else 0
        if not rows_of:
            return
        for tk, (m, rows) in rows_of.items():
            for row in rows:
                if row[0] == 20 and row[10] is not None:
                    quote_ages.append(row[10])
                if ctrl_want:
                    key = (tk, close_s - row[0])
                    c = ctrl_want.get(key)
                    if c is not None:
                        want_yes = c[1]
                        if row[6] is None:
                            ctrl[3] += 1
                        else:
                            mine = row[7] if want_yes else \
                                round(1.0 - row[6], 4)
                            ctrl[0] += 1
                            if abs(mine - c[0]) < 0.0011:
                                ctrl[1] += 1
                            ctrl[2].append(abs(mine - c[0]))
        for tag, tmax in (("LIVE", TAU_MAX), ("WIDE", a.tau_wide)):
            buys = entries_for_close(rows_of, a.size, cap=a.cap,
                                     tau_max=tmax)
            for b in buys:
                m, rows = rows_of[b["tk"]]
                b["close_s"] = close_s
                b["won"] = (b["want"] == "yes") == m["won_yes"]
                b["sr"] = m["sr"]
                b["rows"] = rows
                positions[tag].append(b)

    t_first = calendar.timegm(time.strptime(
        os.path.basename(tfiles[0])[:11], "%Y%m%dT%H"))
    pend = [c for c in sorted(by_close) if c > t_first]
    print(f"  {len(pend):,} closes inside the tape window")
    pi = 0
    for k, tf in enumerate(tfiles):
        hb = os.path.basename(tf)[:11]
        hstart = calendar.timegm(time.strptime(hb, "%Y%m%dT%H"))
        try:
            with gzip.open(tf, "rt") as fh:
                for line in fh:
                    if '"ticker"' not in line:
                        continue
                    hit = False
                    for s in SER:
                        if s in line:
                            hit = True
                            break
                    if not hit:
                        continue
                    p = parse_ticker_line(line)
                    if p is None:
                        continue
                    tk, ts, yb, ya, ybs, yas = p
                    m = bt.get(tk)
                    if m is None:
                        continue
                    sec = ts // 1000
                    if not (m["close_s"] - PANEL_TAU <= sec < m["close_s"]):
                        continue
                    buf[tk].append((ts, yb, ya, ybs, yas))
        except (EOFError, zlib.error, OSError):
            skipped["ticker_file"] += 1
        cutoff = hstart + 3600
        while pi < len(pend) and pend[pi] <= cutoff:
            finalise(pend[pi])
            pi += 1
        if (k + 1) % 25 == 0:
            print(f"    ticker {k+1}/{len(tfiles)}  "
                  f"positions live={len(positions['LIVE'])} "
                  f"wide={len(positions['WIDE'])}  "
                  f"{time.time()-t_start:.0f}s", flush=True)
    while pi < len(pend):
        finalise(pend[pi])
        pi += 1

    print(f"\n  panel built in {time.time()-t_start:.0f}s; "
          f"skipped {dict(skipped)}")
    control = (ctrl[0], ctrl[1], (pct(ctrl[2], 50) or 0.0), ctrl[3],
               (pct(ctrl[2], 90) or 0.0), (pct(ctrl[2], 99) or 0.0)) \
        if ctrl[0] else None
    sA = {k: (dict(v) if isinstance(v, dict) else
              (sorted(v) if isinstance(v, set) else v))
          for k, v in stageA.items()}
    try:
        import pickle
        with open(os.path.join(a.out, "state.pkl"), "wb") as fh:
            pickle.dump({"positions": positions, "stageA": sA,
                         "ages": quote_ages, "control": control,
                         "cap": a.cap, "size": a.size,
                         "tau_wide": a.tau_wide}, fh, 2)
    except Exception as e:                                   # noqa: BLE001
        print(f"  (state not cached: {e})")
    report(positions, stageA, quote_ages, a, control)


# ===========================================================================
def score_trigger(ps, fn, win_unit, frac=1.0):
    """Everything the operator asked for, for one trigger, in one pass."""
    ph = defaultdict(float)
    fired = fa = saves = nofill = 0
    facost = 0.0
    savegain = 0.0
    fillnum = filldenom = 0.0
    prices = []
    lead = []
    for p in ps:
        h, ft, wn = run_hedge(dict(p), p["rows"], fn, size_frac=frac)
        v = leg_pnl(p["n"], p["price"], p["won"], h)
        ph[p["close_s"]] += v
        if ft is None:
            continue
        fired += 1
        lead.append(ft)
        fillnum += sum(q for q, _ in h)
        filldenom += wn
        if not h:
            nofill += 1
        else:
            prices.append(sum(q * px for q, px in h) / sum(q for q, _ in h))
        base_v = leg_pnl(p["n"], p["price"], p["won"])
        if p["won"]:
            fa += 1
            facost += base_v - v
        else:
            saves += 1
            savegain += v - base_v
    s = summarise(ph, win_unit)
    s.update(fired=fired, fa=fa, saves=saves, nofill=nofill, facost=facost,
             savegain=savegain,
             fill=fillnum / filldenom if filldenom else 0.0,
             px=pct(prices, 50) if prices else float("nan"),
             lead=pct(lead, 50) if lead else float("nan"),
             fa_each_w=(facost / fa / win_unit) if fa and win_unit > 0 else 0.0,
             save_each_w=(savegain / saves / win_unit)
             if saves and win_unit > 0 else 0.0)
    return s, ph


def report(positions, sA, ages, a, control=None):
    out = []

    def P(s=""):
        print(s)
        out.append(s)

    P("\n" + "=" * 78)
    P("STAGE A -- THE CROSSING, MEASURED WITHOUT THE BOOK AND WITHOUT PRICES")
    P("=" * 78)
    P(f"\n  Population: every settled market where the model reached "
      f"{PIN:.0%} on some second")
    P(f"  in tau {TAU_MIN}-{TAU_MAX}, whether or not anything was on offer. "
      f"n = {sA['n']:,} markets over")
    P(f"  {len(sA['closes']):,} closes. This stage uses no prices at all, so "
      f"the book cannot select it.")
    if sA["n"]:
        c, cl = sA["cross"], sA["cross_lose"]
        nc, ncl = sA["nocross"], sA["nocross_lose"]
        lo, hi = wilson(cl, c)
        lo2, hi2 = wilson(ncl, nc)
        P(f"\n  {'':<46}{'n':>7}{'lost':>6}{'P(lose)':>10}{'95% CI':>19}")
        P(f"  {'index NEVER crossed K_eff after entry':<46}{nc:>7}{ncl:>6}"
          f"{ncl/max(nc,1):>10.4f}    [{lo2:.4f}, {hi2:.4f}]")
        P(f"  {'index crossed K_eff at least once':<46}{c:>7}{cl:>6}"
          f"{cl/max(c,1):>10.4f}    [{lo:.4f}, {hi:.4f}]")
        if nc and c and ncl:
            r = (cl / c) / (ncl / nc)
            P(f"\n  A crossing multiplies the chance of losing by {r:,.1f}x.")
        elif c and not ncl:
            P(f"\n  EVERY loss in this sample was preceded by a crossing: "
              f"{cl} of {cl + ncl}.")
        P(f"\n  THE OPERATOR'S QUESTION -- 'how often is a crossing at "
          f"tau > 5 followed by")
        P(f"  settlement on that same (wrong) side?'")
        n5, l5 = sA["gt5"]
        lo5, hi5 = wilson(l5, n5)
        P(f"    crossings first seen at tau > 5s: {n5:,}; settled on the "
          f"crossed side {l5:,} times")
        P(f"    = {l5/max(n5,1):.4f}  [95% CI {lo5:.4f}, {hi5:.4f}]")
        ns, ls_ = sA["stuck"]
        los, his = wilson(ls_, ns)
        P(f"    and if it was STILL on the wrong side at the last second: "
          f"{ns:,} cases, settled")
        P(f"    on that side {ls_:,} times = {ls_/max(ns,1):.4f}  "
          f"[{los:.4f}, {his:.4f}]")
        P(f"\n  FIRST CROSSING, BY WHEN IT HAPPENS")
        P(f"  {'':<46}{'n':>7}{'lost':>6}{'P(lose)':>10}{'95% CI':>19}")
        for b in (5, 10, 20, 30):
            n_, l_ = sA["byt"][b]
            if not n_:
                continue
            lo3, hi3 = wilson(l_, n_)
            lab = {5: "first crossing at tau <= 5s",
                   10: "first crossing at tau 6-10s",
                   20: "first crossing at tau 11-20s",
                   30: "first crossing at tau 21-30s"}[b]
            P(f"  {lab:<46}{n_:>7}{l_:>6}{l_/n_:>10.4f}"
              f"    [{lo3:.4f}, {hi3:.4f}]")
        P(f"\n  HOW LONG THE INDEX IS STILL ON THE WRONG SIDE AT THE CLOSE")
        P(f"  {'':<46}{'n':>7}{'lost':>6}{'P(lose)':>10}{'95% CI':>19}")
        for k in sorted(sA["run"]):
            n_, l_ = sA["run"][k]
            if not n_:
                continue
            lo6, hi6 = wilson(l_, n_)
            lab = {0: "crossed, but came back before the close",
                   1: "still wrong for the last 1-2s",
                   3: "still wrong for the last 3-5s",
                   6: "still wrong for the last 6-10s",
                   11: "still wrong for the last 11s or more"}.get(k, str(k))
            P(f"  {lab:<46}{n_:>7}{l_:>6}{l_/n_:>10.4f}"
              f"    [{lo6:.4f}, {hi6:.4f}]")
        mc, mcl = sA["mucross"], sA["mucross_lose"]
        lo4, hi4 = wilson(mcl, mc)
        P(f"\n  For comparison, the PROJECTED SETTLEMENT (locked prints + "
          f"spot) crossing K_eff:")
        P(f"  {mc:,} markets, {mcl} lost, P(lose) = {mcl/max(mc,1):.4f} "
          f"[{lo4:.4f}, {hi4:.4f}].")
    if ages:
        P(f"\n  Ticker-quote staleness at tau=20, carried forward from the "
          f"last update:")
        P(f"  median {pct(ages,50):,.0f} ms, p90 {pct(ages,90):,.0f} ms, "
          f"p99 {pct(ages,99):,.0f} ms, over {len(ages):,} markets.")
        P(f"  Gate used here: {MAX_QUOTE_AGE_MS:,} ms.")
    if control:
        n, agree, dev, absent, d90, d99 = control
        P(f"\n  CONTROL -- the ticker touch against the ORDER-BOOK replay "
          f"(results/pindata/rows.jsonl):")
        P(f"  {n:,} (market, second) cells present in both. Same price to "
          f"0.1c on {agree:,} = "
          f"{100.0*agree/max(n,1):.2f}%;")
        P(f"  median absolute difference {100*dev:.3f}c, p90 {100*d90:.3f}c, "
          f"p99 {100*d99:.3f}c. "
          f"{absent:,} order-book cells had no ticker quote at all.")
        P(f"  The order-book replay is DELTA-ONLY (its snapshot reads the "
          f"wrong keys -- SKIM open")
        P(f"  item 5), so a disagreement is not automatically the ticker "
          f"channel's fault.")

    for tag in ("LIVE", "WIDE"):
        ps = positions[tag]
        P("\n" + "=" * 78)
        P(f"STAGE B -- {tag} WINDOW: what a hedge does to the loss "
          f"distribution")
        P("=" * 78)
        if not ps:
            P("  no positions -- nothing to report, and nothing is estimated.")
            continue
        wide = tag == "WIDE"
        P(f"\n  Entry rule: the LIVE frozen rule (pin {PIN}, edge >= "
          f"{100*EDGE_FLOOR:.1f}c, EV >= {100*EV_FLOOR:.1f}c, ceiling "
          f"{100*PRICE_CEILING:.1f}c,")
        P(f"  cap {a.cap} buys/close, size {a.size:g}) over tau {TAU_MIN}-"
          f"{a.tau_wide if wide else TAU_MAX}s.")
        if wide:
            P(f"  THE WIDE WINDOW IS NOT THE STRATEGY. tau 31-90 is measured "
              f"3.7-10.9x overconfident")
            P(f"  and is not traded. It is here because the live window "
              f"contains too few losses to")
            P(f"  describe a loss tail at all, and a hedge study with no "
              f"losses can only measure cost.")
        closes = sorted({p["close_s"] for p in ps})
        losers = [p for p in ps if not p["won"]]
        lclose = sorted({p["close_s"] for p in losers})
        base = defaultdict(float)
        for p in ps:
            base[p["close_s"]] += leg_pnl(p["n"], p["price"], p["won"])
        wins = [v for v in base.values() if v > 0]
        win_unit = sum(wins) / len(wins) if wins else float("nan")
        b0 = summarise(base, win_unit)
        P(f"\n  {len(ps):,} buys over {len(closes):,} CLOSES; "
          f"{len(losers)} losing buys over {len(lclose)} losing closes "
          f"({100.0*len(lclose)/len(closes):.2f}% of closes).")
        P(f"  ONE WIN = ${win_unit:.4f} -- the mean profit of a profitable "
          f"close, unhedged, at size {a.size:g}.")
        P(f"  Unhedged total ${b0['total']:.2f}; worst close "
          f"-${b0['worst']:.2f} = {b0['worst_w']:.1f} WINS TO RECOVER.")
        P(f"\n  MDE, STATED BEFORE THE ESTIMATES: this sample holds "
          f"{len(lclose)} losing closes. The worst-close")
        P(f"  column is ONE observation and carries no interval.")
        if lclose:
            P(f"  A severity reduction smaller than about "
              f"{100*1.96/math.sqrt(len(lclose)):.0f}% of a loss standard "
              f"deviation could not be")
            P(f"  distinguished from noise at this n.")
        if len(lclose) < 30:
            P(f"  *** {len(lclose)} losing closes is BELOW the 30-cluster "
              f"floor. Nothing in this block is a")
            P(f"  significance claim; it is a description of the losses this "
              f"tape actually contains.")
        T = make_triggers()
        P(f"\n  {'trigger':<20}{'total$':>8}{'worst$':>8}{'worst':>7}"
          f"{'p5$':>7}{'p1$':>7}{'fire':>5}{'FA':>5}{'FA$each':>8}"
          f"{'FAw':>6}{'FA%prof':>8}{'save$':>8}{'FA/sv':>6}{'fill':>6}"
          f"{'hedge':>7}{'lead':>6}")
        P(f"  {'':<20}{'':>8}{'':>8}{'wins':>7}{'':>7}{'':>7}{'':>5}{'':>5}"
          f"{'':>8}{'each':>6}{'':>8}{'':>8}{'ratio':>6}{'frac':>6}"
          f"{'px':>7}{'s':>6}")
        P(f"  {'NO HEDGE':<20}{b0['total']:>8.2f}{-b0['worst']:>8.2f}"
          f"{b0['worst_w']:>7.1f}{b0['p95']:>7.2f}{b0['p99']:>7.2f}"
          f"{'-':>5}{'-':>5}{'-':>8}{'-':>6}{'-':>8}{'-':>8}{'-':>6}"
          f"{'-':>6}{'-':>7}{'-':>6}")
        rows_md = []
        for name in sorted(T):
            fn, desc = T[name]
            s, _ = score_trigger(ps, fn, win_unit)
            fap = 100.0 * s["facost"] / b0["total"] if b0["total"] else 0.0
            P(f"  {name:<20}{s['total']:>8.2f}{-s['worst']:>8.2f}"
              f"{s['worst_w']:>7.1f}{s['p95']:>7.2f}{s['p99']:>7.2f}"
              f"{s['fired']:>5}{s['fa']:>5}"
              f"{(s['facost']/s['fa'] if s['fa'] else 0):>8.2f}"
              f"{s['fa_each_w']:>6.1f}{fap:>8.1f}"
              f"{s['savegain']:>8.2f}"
              f"{(s['fa']/s['saves'] if s['saves'] else float('nan')):>6.1f}"
              f"{s['fill']:>6.2f}{s['px']:>7.3f}"
              f"{s['lead']:>6.0f}")
            rows_md.append((name, desc, s, fap))
        P(f"\n  COLUMNS. 'worst wins' is the worst single close in WINS TO "
          f"RECOVER -- the operator's")
        P(f"  unit. 'FA' counts false alarms: firings on positions that went "
          f"on to WIN. 'FA$each'")
        P(f"  and 'FAw each' are what ONE false alarm costs, in dollars and "
          f"in wins; the operator")
        P(f"  said 1-5 wins is an acceptable price, so that column is the "
          f"test he set. 'save$' is")
        P(f"  the total rescued on positions that lost. 'fill frac' is how "
          f"much of the position the")
        P(f"  touch actually let us hedge. 'hedge px' is the median price "
          f"paid for the other side.")
        P(f"  'lead s' is the median seconds between the trigger firing and "
          f"the close.")
        P(f"  'FA/sv ratio' is WINNING TRADES SPOILED PER LOSS CAUGHT -- the "
          f"same currency as the")
        P(f"  entry gates, which cost 22-44 winners per loss avoided.")

        pick = [n for n in ("SPOT_CROSS", "SPOT_CROSS_HOLD2",
                            "SPOT_CROSS_HOLD5", "MU_CROSS", "MU_CROSS_HOLD2",
                            "MU_AND_SPOT", "MODEL_P90") if n in T]
        P(f"\n  PARTIAL HEDGING BY CHOICE, not by depth: hedge only a "
          f"FRACTION of the position.")
        P(f"  {'trigger':<20}{'frac':>6}{'total$':>9}{'worst$':>9}"
          f"{'worst wins':>12}{'FA%prof':>9}")
        for name in pick:
            for fr in (0.25, 0.50, 1.00):
                s, _ = score_trigger(ps, T[name][0], win_unit, frac=fr)
                fap = 100.0 * s["facost"] / b0["total"] if b0["total"] else 0.0
                P(f"  {name:<20}{fr:>6.2f}{s['total']:>9.2f}"
                  f"{-s['worst']:>9.2f}{s['worst_w']:>12.1f}{fap:>9.1f}")

        P(f"\n  THE LOSS TAIL IN WINS TO RECOVER -- how many closes cost more "
          f"than N wins")
        P(f"  {'trigger':<20}{'>1 win':>8}{'>5':>6}{'>10':>6}{'>20':>6}"
          f"{'>40':>6}{'worst':>8}")

        def tail(ph):
            v = [-x / win_unit for x in ph.values() if x < 0]
            return ([sum(1 for x in v if x > k) for k in (1, 5, 10, 20, 40)],
                    (max(v) if v else 0.0))
        t0, w0 = tail(base)
        P(f"  {'NO HEDGE':<20}{t0[0]:>8}{t0[1]:>6}{t0[2]:>6}{t0[3]:>6}"
          f"{t0[4]:>6}{w0:>8.1f}")
        for name in pick:
            _, ph = score_trigger(ps, T[name][0], win_unit)
            tt, ww = tail(ph)
            P(f"  {name:<20}{tt[0]:>8}{tt[1]:>6}{tt[2]:>6}{tt[3]:>6}"
              f"{tt[4]:>6}{ww:>8.1f}")

        P(f"\n  What each trigger means:")
        for name, desc, *_ in rows_md:
            P(f"    {name:<20} {desc}")

        if losers:
            P(f"\n  EVERY LOSING BUY IN THIS SAMPLE (first 40), and what "
              f"SPOT_CROSS would have done:")
            P(f"  {'ticker':<28}{'tau':>4}{'paid':>7}{'lost$':>8}"
              f"{'fired':>7}{'hedge px':>9}{'hedged':>8}{'saved$':>8}")
            fn = T["SPOT_CROSS"][0]
            for p in sorted(losers, key=lambda x: x["close_s"])[:40]:
                h, ft, wn = run_hedge(dict(p), p["rows"], fn)
                v = leg_pnl(p["n"], p["price"], False, h)
                b_ = leg_pnl(p["n"], p["price"], False)
                hq = sum(q for q, _ in h)
                px = (sum(q * x for q, x in h) / hq) if hq else float("nan")
                P(f"  {p['tk'][:28]:<28}{p['tau']:>4}{p['price']:>7.3f}"
                  f"{b_:>8.2f}{(ft if ft else 0):>7}{px:>9.3f}"
                  f"{hq:>8.1f}{v-b_:>8.2f}")

    path = os.path.join(a.out, "REPORT.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("```\n" + "\n".join(out) + "\n```\n")
    print(f"\n  written -> {path}")


if __name__ == "__main__":
    main()
