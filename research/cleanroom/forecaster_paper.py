r"""Clean-room PAPER bot B -- the three schools that were NOT chosen, run side by side on live data, never trading.

Built 2026-09-28 from the clean-room designs (results/CLEANROOM_2026-09-27.md section 1) with the plumbing of
research/cleanroom/locked_average_ladder_re_paper.py.  NOTHING in this file can send an order: the only HTTP verb used
is GET (research/kauth.py's get helper) and the WebSocket carries market-data subscriptions only.  The self-test scans
this file for any order endpoint or HTTP write verb and fails if one is present.

Settlement: settle = round_half_up(mean of the 60 CF Benchmarks prints stamped close-60 .. close-1, round_digits);
YES iff settle >= strike  <=>  mean >= thr = strike - 0.5*10**-round_digits.

Three strategies, each exactly as its designer froze it (parameters copied, not refit, into
research/cleanroom/forecaster_paper_params.json, all fit on TRAIN 2026-08-25..09-17):

  FC  forecaster (taker).  When 0..30 settlement prints are still to come, buy any displayed offer of side s priced
      0.75..0.985 when the calibrated model beats it by >= 0.02 after the taker fee:
      p_s - q - 0.07*q*(1-q) >= 0.02.  Model: design-forecaster/model.py kind 'blendvr', z-scaled, calibration map on
      (sigma = sqrt(0.5*global^2 + 0.5*local120^2) * sqrt(VR) * bucket scale).  Caps: 100 contracts per side per
      market, 400 per close.  Skips when the latest print is > 2 s stale or a window print is missing.  Max price 0.985.
  BT  bettor (taker).  In the last 60 s, buy the model's favoured side at any displayed offer priced 0.85..0.98 when
      |z| >= 4 and calibrated p - price - fee >= 0.005 (p from the design's TRAIN table by remaining-prints bin x |z|
      bin).  Stake per market = min(0.25 * Kelly, 10% of bank) with Kelly = (p - c)/(1 - c), c = price + fee; per close
      <= 25% of bank; paper bank starts at $1,000 and compounds at settlement (separately per fill rule).  Max price 0.98.
  CT  contrarian (maker).  In the last 60 s, when the empirical model says one side has >= 99.9% (the "locked" side)
      AND the market itself agrees (the last trade printed that side at >= 0.97 within the last 3 s), rest bids for
      that side at 0.95 / 0.90 / 0.80, 50 contracts each (per level per market, reset when the locked side changes).
      Makers pay no fee.  Max price 0.95.

Fill rules (both logged; the second is the one to believe -- the refuters' rule):
  Taker (FC, BT)
    opt  : the size displayed at the decision instant, at the displayed prices (the design's optimistic fill).
    real : an order limited at the worst qualifying price fills only against size STILL DISPLAYED at <= that price
           1.0 s after the decision (log carries the same-second size next to it).  Nothing if the market has closed.
  Maker (CT)
    opt  : the design's base rule, event by event: a trade whose taker SOLD my side at <= my bid, when the gate held
           as of 0.3 s earlier and the confirming print was 0.3-3 s old, fills me up to its size (the trade's size is
           spent best-price-first across levels -- fixes the design's "one dump fills every level" bug).
    real : an order goes live 0.3 s after the gate opens and stays live until 0.3 s after it closes (a real cancel
           is not instant); a trade fills it only if printed after the live time, THROUGH the bid (price < bid) up to
           its size, or AT the bid after the size displayed ahead of me at placement is used up.
  Taker fee 0.07*n*p*(1-p) rounded up to the cent per fill; maker fee 0.

Usage:
  python research/cleanroom/forecaster_paper.py --selftest          # planted worlds only, then exit
  python research/cleanroom/forecaster_paper.py --minutes 10080     # self-test, then live paper trading
Log: C:\kals-repo\results\cleanroom-forecaster.jsonl (one JSON per line, UTC); close_summary per quarter-hour.
"""
import argparse
import base64
import bisect
import ctypes
import json
import math
import os
import queue
import re
import socket
import ssl
import struct
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP, ROUND_CEILING

NAME = "forecaster"
LOG_PATH = r"C:\kals-repo\results\cleanroom-%s.jsonl" % NAME
PARAMS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "forecaster_paper_params.json")
WS_HOST = "api.elections.kalshi.com"
WS_PATH = "/trade-api/ws/v2"

# coin -> (series, index_id, default round_digits)
COINS = {
    "BTC": ("KXBTC15M", "BRTI", 2),
    "ETH": ("KXETH15M", "ETHUSD_RTI", 2),
    "SOL": ("KXSOL15M", "SOLUSD_RTI", 4),
    "XRP": ("KXXRP15M", "XRPUSD_RTI", 4),
    "DOGE": ("KXDOGE15M", "DOGEUSD_RTI", 7),
    "HYPE": ("KXHYPE15M", "HYPEUSD_RTI", 4),
    "BNB": ("KXBNB15M", "BNBUSD_RTI", 2),
    "ZEC": ("KXZEC15M", "ZECUSD_RTI", 4),
    "NEAR": ("KXNEAR15M", "NEARUSD_RTI", 4),
}
INDEX_TO_COIN = {v[1]: k for k, v in COINS.items()}
SERIES_TO_COIN = {v[0]: k for k, v in COINS.items()}

STRATS = ("fc", "bt", "ct")
MODELS = ("opt", "real")
# FC (design-forecaster, sim_test_fav_* parameters)
FC_MIN_EDGE = 0.02
FC_R_MIN, FC_R_MAX = 0, 30
FC_MIN_PRICE, FC_MAX_PRICE = Decimal("0.75"), Decimal("0.985")
FC_MAX_SIDE = Decimal(100)
FC_MAX_CLOSE = Decimal(400)
FC_LAG_S = 0.15
# BT (design-bettor, run_train_final parameters)
BT_THR = 0.005
BT_T_START = -60
BT_MAX_R = 60
BT_MIN_Z = 4.0
BT_MIN_PRICE, BT_MAX_PRICE = Decimal("0.85"), Decimal("0.98")
BT_KELLY = 0.25
BT_MKT_CAP = 0.10
BT_CLOSE_CAP = 0.25
BT_BANK0 = Decimal(1000)
BT_LAT = 0.15
BT_VOLWIN = 120
BT_RB = [(0, 0), (1, 10), (11, 30), (31, 59), (60, 60)]
BT_ZB = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 8, 10, 15, 20, 30, 1e9]
# CT (design-contrarian, table_v7 parameters)
CT_PMIN = 0.999
CT_LADDER = (Decimal("0.95"), Decimal("0.90"), Decimal("0.80"))
CT_SIZE = Decimal(50)
CT_T0 = -60
CT_LATENCY = 0.3
CT_CONFIRM = Decimal("0.97")
CT_CONF_AGE = 3.0

TAKER_DELAY = 1.0            # real taker fill: size still displayed this long after the decision
EVAL_MIN_GAP = 0.1           # taker re-evaluation on book changes at most every 100 ms per market
STALE_S = 2                  # latest print may lag the wall second by at most this many seconds
TAKER_FEE_RATE = Decimal("0.07")
SETTLE_TIMEOUT_S = 1500
REL_FIRST = -60


# ----------------------------------------------------------------------------------------------------------- helpers
def now_iso(t=None):
    return datetime.fromtimestamp(time.time() if t is None else t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def phi(z):
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def tick_at(price):
    """Tapered deci-cent tick: 0.001 below 0.10 and above 0.90, 0.01 between."""
    if price < Decimal("0.10") or price > Decimal("0.90"):
        return Decimal("0.001")
    return Decimal("0.01")


def floor_tick(x):
    d = Decimal(str(round(x, 6)))
    step = tick_at(d)
    q = (d / step).to_integral_value(rounding=ROUND_FLOOR) * step
    return q.quantize(Decimal("0.0001"))


def taker_fee(n, price):
    raw = TAKER_FEE_RATE * n * price * (Decimal(1) - price)
    return raw.quantize(Decimal("0.01"), rounding=ROUND_CEILING)


def rss_mb():
    try:
        class PMC(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        fn = ctypes.windll.psapi.GetProcessMemoryInfo
        fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
        if fn(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return round(pmc.WorkingSetSize / 1048576, 1)
    except Exception:
        pass
    return -1


def parse_close_time(s):
    return int(datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())


class Logger:
    def __init__(self, path=None, sink=None):
        self.path = path
        self.sink = sink
        self.fh = open(path, "a", encoding="utf-8") if path else None

    def write(self, ev, **kw):
        rec = {"t": now_iso(), "ev": ev}
        rec.update(kw)
        if self.sink is not None:
            self.sink.append(rec)
        if self.fh:
            self.fh.write(json.dumps(rec, default=str, separators=(",", ":")) + "\n")
            self.fh.flush()

class Book:
    def __init__(self):
        self.yes = {}
        self.no = {}
        self.synced = False
        self.snap_seq = -1
        self.sid = None

    def load(self, msg, seq, sid=None):
        self.yes = {Decimal(p): Decimal(s) for p, s in msg.get("yes_dollars_fp", []) or []}
        self.no = {Decimal(p): Decimal(s) for p, s in msg.get("no_dollars_fp", []) or []}
        self.yes = {p: s for p, s in self.yes.items() if s > 0}
        self.no = {p: s for p, s in self.no.items() if s > 0}
        self.synced = True
        self.snap_seq = seq
        self.sid = sid

    def delta(self, side, price, d, seq, sid=None):
        if not self.synced or seq <= self.snap_seq or sid != self.sid:
            return
        lad = self.yes if side == "yes" else self.no
        p = Decimal(price)
        s = lad.get(p, Decimal(0)) + Decimal(d)
        if s <= 0:
            lad.pop(p, None)
        else:
            lad[p] = s

    def best_bid(self, side):
        lad = self.yes if side == "yes" else self.no
        if not lad:
            return None, Decimal(0)
        p = max(lad)
        return p, lad[p]

    def best_ask(self, side):
        """Best ask for `side` = 1 - best bid of the other side, with that bid's size."""
        p, s = self.best_bid("no" if side == "yes" else "yes")
        if p is None:
            return None, Decimal(0)
        return Decimal(1) - p, s



# ------------------------------------------------------------------------------------------------ the three models
def fee_f(q):
    return 0.07 * q * (1.0 - q)


def floor_n(x):
    """Whole contracts, rounded down."""
    x = Decimal(x)
    if x <= 0:
        return Decimal(0)
    return x.to_integral_value(rounding=ROUND_FLOOR)


# FC: design-forecaster/fc_common.py + model.py, ported verbatim in substance
_S_CACHE = {}


def S_coef(t):
    """S(t) = sum_i c_i^2 over future seconds i in t+1..-1, c_i = #future prints stamped >= i (prints in [-60,-1])."""
    if t in _S_CACHE:
        return _S_CACHE[t]
    s = 0
    for i in range(t + 1, 0):
        c = 0 - max(i, -60)
        if c > 0:
            s += c * c
    _S_CACHE[t] = s
    return s


class SettleState:
    def __init__(self):
        self.locked_sum = 0.0
        self.locked_n = 0
        self.v = None
        self.t = None
        self.hist = []

    def add(self, rel, value):
        if rel > -1:
            return
        self.v = value
        self.t = rel
        if rel >= -60:
            self.locked_sum += value
            self.locked_n += 1
        self.hist.append((rel, value))
        if len(self.hist) > 400:
            self.hist = self.hist[-300:]

    def proj(self):
        r = 60 - self.locked_n
        return (self.locked_sum + r * self.v) / 60.0

    def sd(self, sigma):
        return self.v * sigma * math.sqrt(S_coef(self.t)) / 60.0

    def local_sigma(self, window):
        h = self.hist
        if len(h) < 8:
            return None
        acc = 0.0
        n = 0
        lo = h[-1][0] - window
        for i in range(len(h) - 1, 0, -1):
            r1, v1 = h[i]
            r0, v0 = h[i - 1]
            if r1 < lo:
                break
            if r1 - r0 == 1 and v0 > 0 and v1 > 0:
                x = math.log(v1 / v0)
                acc += x * x
                n += 1
        if n < 8:
            return None
        return math.sqrt(acc / n)


def prob_yes(proj, sd, strike, round_digits):
    thr = strike - 0.5 * (10.0 ** (-round_digits)) if round_digits is not None else strike
    if sd <= 0:
        return 1.0 if proj >= thr else 0.0
    return 1.0 - phi((thr - proj) / sd)


class FcModel:
    """design-forecaster Model(kind='blendvr', zscale=True, calmap=True)."""

    def __init__(self, p):
        self.p = p
        self.scale = {k.split("|")[1]: v["sd"] for k, v in p.get("zsum", {}).items() if k.split("|")[0] == "blendvr"}
        cm = {}
        for k, v in p.get("calc", {}).items():
            m, b, _e = k.split("|")
            if m == "blendvrs" and v["n"] >= 30:
                cm.setdefault(b, []).append((v["pred"], v["real"]))
        for b in cm:
            cm[b].sort()
        self.cm = cm or None

    @staticmethod
    def bucket(r):
        for a, b in [(0, 1), (2, 3), (4, 6), (7, 10), (11, 15), (16, 20), (21, 30), (31, 45), (46, 60), (61, 90),
                     (91, 120), (121, 181)]:
            if a <= r <= b:
                return "%d-%d" % (a, b)
        return "121-181"

    @staticmethod
    def remaining(st):
        return 60 - st.locked_n if st.t >= -60 else (-61 - st.t) + 60

    def sigma(self, coin, st):
        c = self.p["coins"].get(coin)
        if c is None:
            return None
        g = c["sigma"]
        r = self.remaining(st)
        l = st.local_sigma(120)
        s = math.sqrt(0.5 * g * g + 0.5 * l * l) if l is not None else g
        k = "5" if r <= 7 else "10" if r <= 15 else "30" if r <= 45 else "60"
        vr = self.p.get("vr", {}).get(coin, {}).get(k)
        if vr:
            s *= math.sqrt(max(0.7, vr))
        s *= self.scale.get(self.bucket(r), 1.0)
        return s

    def prob(self, coin, st, strike, round_digits):
        if st.v is None or st.t is None or st.t > -1:
            return None
        s = self.sigma(coin, st)
        if s is None:
            return None
        p = prob_yes(st.proj(), st.sd(s), strike, round_digits)
        if self.cm:
            pts = self.cm.get(self.bucket(self.remaining(st)))
            if pts:
                conf = max(p, 1 - p)
                adj = self._map(conf, pts)
                p = adj if p >= 0.5 else 1 - adj
        return p

    @staticmethod
    def _map(conf, pts):
        if conf <= pts[0][0]:
            return conf
        for i in range(1, len(pts)):
            if conf <= pts[i][0]:
                x0, y0 = pts[i - 1]
                x1, y1 = pts[i]
                return y0 + (y1 - y0) * (conf - x0) / (x1 - x0) if x1 > x0 else y1
        return min(1.0, conf - (pts[-1][0] - pts[-1][1]))


# BT: design-bettor/build_ds.py Model.state + fit_calib.lookup
def bt_rkey(r):
    for lo, hi in BT_RB:
        if lo <= r <= hi:
            return "%d-%d" % (lo, hi)
    return "60-60"


def bt_zkey(z):
    z = abs(z)
    for i in range(len(BT_ZB) - 1):
        if BT_ZB[i] <= z < BT_ZB[i + 1]:
            return "%g-%g" % (BT_ZB[i], BT_ZB[i + 1])
    return "?"


def bt_state(stamps, vals, close_s, K):
    """stamps/vals: this index's usable prints (ascending, absolute seconds).  -> (p_yes, r, z, sigma, proj) or None."""
    if not stamps:
        return None
    i = len(stamps) - 1
    k = stamps[i] - close_s
    v = vals[i]
    S = 0.0
    m = 0
    for j in range(bisect.bisect_left(stamps, close_s - 60), i + 1):
        if stamps[j] - close_s > -1:
            break
        S += vals[j]
        m += 1
    if m > 60:
        return None
    rr = 60 - m
    proj = (S + rr * v) / 60.0
    j1 = bisect.bisect_left(stamps, stamps[i] - BT_VOLWIN)
    n = 0
    s1 = s2 = 0.0
    for j in range(max(j1, 1), i + 1):
        if vals[j - 1] <= 0 or vals[j] <= 0:
            continue
        x = math.log(vals[j] / vals[j - 1])
        n += 1
        s1 += x
        s2 += x * x
    if n < 20:
        return None
    sigma = math.sqrt(max(s2 / n - (s1 / n) ** 2, 1e-14))
    w = 0.0
    for j in range(max(k + 1, -60), 0):
        w += (j - k) ** 2
    if w <= 0:
        z = 50.0 if proj >= K else -50.0
        return (1.0 if proj >= K else 0.0, 0, z, sigma, proj)
    sd = v * sigma * math.sqrt(w) / 60.0
    z = (proj - K) / sd
    return (phi(z), rr, max(-99.0, min(99.0, z)), sigma, proj)


# CT: design-contrarian/sim.py Model.p_yes
class CtModel:
    def __init__(self, p):
        self.sd = p["sd"]
        self.quant = {int(k): v for k, v in p["quant"].items()}
        self.nq = p["nq"]

    def p_yes(self, coin, rel, proj, thr):
        s = self.sd.get("%s|%d" % (coin, rel))
        q = self.quant.get(rel)
        if s is None or q is None or proj <= 0 or s <= 0:
            return None
        z = (thr - proj) / proj / s
        return 1.0 - bisect.bisect_left(q, z) / self.nq


def pstr(x):
    """Decimal price/size as a plain string without trailing zeros (0.9500 -> 0.95)."""
    return format(Decimal(x).normalize(), "f")


def asks_of(book, side):
    """Displayed offers to BUY `side`: ascending (price, size), price = 1 - the other side's bid."""
    lad = book.no if side == "yes" else book.yes
    return sorted((Decimal(1) - p, s) for p, s in lad.items() if s > 0)


# ------------------------------------------------------------------------------------------------------------ engine
class Market:
    def __init__(self, ticker, coin, close_s, strike, round_digits, strike_src):
        self.ticker = ticker
        self.coin = coin
        self.index_id = COINS[coin][1]
        self.close_s = close_s
        self.rd = round_digits
        self.set_strike(strike, strike_src)
        self.done = False
        self.settled = False
        self.result = None
        self.settle_asked_at = 0
        self.fills = []                           # every paper fill, all strategies and both fill rules
        self.pos = {}                             # (strat, model, side) -> contracts
        self.stake = {}                           # (strat, model) -> dollars paid in this market
        self.taken = {}                           # (strat, model, side, price) -> contracts taken from that offer
        self.pending = {}                         # (strat, side) -> real taker order waiting TAKER_DELAY
        self.state = None                         # model outputs for the latest usable print
        self.state_stamp = None
        self.last_eval = 0.0
        self.book_dirty = False
        self.n_decisions = 0
        # contrarian
        self.ct_state = {}                        # rel -> locked side or None, computed when that print arrived
        self.ct_last = None                       # (yes_price, ts_ms) of the last trade before the current ms
        self.ct_pend = None
        self.last_trade = None                    # (yes_price, ts_ms, rx) the most recent trade seen
        self.ct_opt_side = None
        self.ct_opt_rem = {}
        self.ct_real_gate = None
        self.ct_real_side = None
        self.ct_real_rem = {}
        self.ct_orders = []

    def set_strike(self, strike, src):
        self.strike = strike
        self.strike_src = src
        self.thr = self.thr_f = self.strike_f = None
        if strike is not None:
            self.thr = strike - Decimal(1).scaleb(-self.rd) / 2
            self.thr_f = float(self.thr)
            self.strike_f = float(strike)


class CtOrder:
    _n = 0

    def __init__(self, side, price, live_from, ahead):
        CtOrder._n += 1
        self.id = CtOrder._n
        self.side = side
        self.price = price
        self.live_from = live_from
        self.live_to = None
        self.ahead = ahead


class Engine:
    """Everything the bot decides, with the clock injected so a planted world can drive it."""

    def __init__(self, log, now_fn, params):
        self.log = log
        self.now = now_fn
        self.fc_model = FcModel(params["forecaster"])
        self.bt_table = params["bettor"]["table"]
        self.ct_model = CtModel(params["contrarian"])
        self.prints = {}
        self.markets = {}
        self.books = {}
        self.pending_close_groups = {}
        self.cum = {(s, m): Decimal(0) for s in STRATS for m in MODELS}
        self.bank = {m: BT_BANK0 for m in MODELS}
        self.close_n = {}                          # (strat, model, close_s) -> contracts (FC cap)
        self.close_stake = {}                      # (strat, model, close_s) -> dollars (BT cap)
        self.n_gaps = 0
        self.lag_ms = deque(maxlen=2000)
        self.resync_wanted = False
        self.last_expiration = {}
        self.finished = set()

    # --- feed inputs -------------------------------------------------------------------------------------------------
    def on_print(self, index_id, stamp_ms, value_str, rx):
        stamp_s = stamp_ms // 1000
        d = self.prints.setdefault(index_id, {})
        try:
            d[stamp_s] = (float(value_str), value_str, rx)
        except ValueError:
            return
        self.lag_ms.append(rx * 1000 - stamp_ms)
        if len(d) > 330:
            cutoff = stamp_s - 300
            for k in [k for k in d if k < cutoff]:
                del d[k]

    def on_snapshot(self, ticker, msg, seq, sid=None):
        if ticker in self.markets:
            self.books.setdefault(ticker, Book()).load(msg, seq, sid)
            self.markets[ticker].book_dirty = True

    def on_delta(self, ticker, msg, seq, sid=None):
        b = self.books.get(ticker)
        if b is not None:
            b.delta(msg["side"], msg["price_dollars"], msg["delta_fp"], seq, sid)
            m = self.markets.get(ticker)
            if m is not None:
                m.book_dirty = True

    def on_gap(self):
        self.n_gaps += 1
        for b in self.books.values():
            b.synced = False
        self.resync_wanted = True

    # --- market universe ---------------------------------------------------------------------------------------------
    def add_market(self, ticker, coin, close_s, strike, round_digits, strike_src):
        if ticker in self.finished or close_s <= self.now():
            return None
        m = self.markets.get(ticker)
        if m is None:
            m = Market(ticker, coin, close_s, strike, round_digits, strike_src)
            self.markets[ticker] = m
            self.books.setdefault(ticker, Book())
            self.pending_close_groups.setdefault(close_s, set()).add(ticker)
            self.log.write("market", ticker=ticker, coin=coin, close_s=close_s, strike=str(strike),
                           round_digits=round_digits, strike_src=strike_src, thr=str(m.thr))
        elif strike is not None and (m.strike != strike or m.strike_src != strike_src) and \
                self.now() < close_s + REL_FIRST - 1:
            m.rd = round_digits
            m.set_strike(strike, strike_src)
            self.log.write("market_update", ticker=ticker, strike=str(strike), strike_src=strike_src, thr=str(m.thr))
        return m

    def active_tickers(self, now):
        best = {}
        for m in self.markets.values():
            if m.close_s > now and (m.coin not in best or m.close_s < best[m.coin].close_s):
                best[m.coin] = m
        return sorted(x.ticker for x in best.values())

    # --- model state from the prints received so far -----------------------------------------------------------------
    def latest_stamp(self, m, now):
        d = self.prints.get(m.index_id, {})
        top = min(int(now), m.close_s - 1)
        for s in range(top, top - STALE_S - 3, -1):
            pr = d.get(s)
            if pr is not None and pr[2] <= now:
                return s
        return None

    def compute_state(self, m, s_last, now):
        d = self.prints.get(m.index_id, {})
        rel = s_last - m.close_s
        stamps = sorted(s for s in d if s <= s_last and s >= m.close_s - 300 and d[s][2] <= now)
        vals = [d[s][0] for s in stamps]
        out = {"rel": rel, "v": d[s_last][1]}
        # window completeness (all prints stamped close-60 .. s_last present)
        lo = m.close_s - 60
        exp_n = max(0, s_last - lo + 1)
        got_n = sum(1 for s in stamps if s >= lo)
        complete = got_n == exp_n
        out["locked_n"] = got_n
        out["complete"] = complete
        # FC
        fc_p = fc_r = None
        if m.strike_f is not None and complete:
            st = SettleState()
            for s, v in zip(stamps, vals):
                if s >= m.close_s - 240:
                    st.add(s - m.close_s, v)
            if st.t is not None:
                fc_r = FcModel.remaining(st)
                fc_p = self.fc_model.prob(m.coin, st, m.strike_f, m.rd)
        out["fc_p"] = fc_p
        out["fc_r"] = fc_r
        # BT
        bt = None
        if m.strike_f is not None:
            bt = bt_state(stamps, vals, m.close_s, m.strike_f)
        if bt is not None:
            p, r, z, sig, proj = bt
            e = self.bt_table.get("%s|%s" % (bt_rkey(r), bt_zkey(z)))
            out.update({"bt_z": round(z, 3), "bt_r": r, "bt_pc": e["p_cal"] if e else None})
        else:
            out.update({"bt_z": None, "bt_r": None, "bt_pc": None})
        # CT
        S = None
        ct_p = None
        if m.thr_f is not None and complete and -60 <= rel <= -1:
            k = -rel - 1
            locked = sum(v for s, v in zip(stamps, vals) if s >= lo)
            proj = (locked + k * vals[-1]) / 60.0
            ct_p = self.ct_model.p_yes(m.coin, rel, proj, m.thr_f)
            if ct_p is not None:
                S = "yes" if ct_p >= CT_PMIN else ("no" if 1 - ct_p >= CT_PMIN else None)
        out["ct_p"] = ct_p
        out["ct_side"] = S
        return out

    # --- clock -------------------------------------------------------------------------------------------------------
    def tick(self):
        now = self.now()
        for m in list(self.markets.values()):
            if m.done:
                continue
            self.resolve_pending(m, now)
            if now >= m.close_s:
                self.resolve_pending(m, now, force=True)
                for o in m.ct_orders:
                    if o.live_to is None or o.live_to > m.close_s:
                        o.live_to = m.close_s
                m.done = True
                continue
            if now < m.close_s + REL_FIRST:
                continue
            s_last = self.latest_stamp(m, now)
            new_state = False
            if s_last is not None and s_last != m.state_stamp and s_last >= m.close_s + REL_FIRST - 1:
                m.state = self.compute_state(m, s_last, now)
                m.state_stamp = s_last
                new_state = True
                rel = s_last - m.close_s
                if rel >= CT_T0:
                    m.ct_state[rel] = m.state["ct_side"]
                b = self.books.get(m.ticker)
                ya = asks_of(b, "yes")[:1] if b and b.synced else []
                na = asks_of(b, "no")[:1] if b and b.synced else []
                self.log.write("state", ticker=m.ticker, rel=rel, wall=round(now - m.close_s, 3),
                               lag=round(now - s_last, 3), v=m.state["v"], complete=m.state["complete"],
                               fc_p=m.state["fc_p"], fc_r=m.state["fc_r"], bt_z=m.state["bt_z"],
                               bt_r=m.state["bt_r"], bt_pc=m.state["bt_pc"], ct_p=m.state["ct_p"],
                               ct_side=m.state["ct_side"], book=bool(b and b.synced),
                               yes_ask=[str(x) for x in ya[0]] if ya else None,
                               no_ask=[str(x) for x in na[0]] if na else None)
            self.ct_update_real(m, now)
            if m.state is not None and (new_state or (m.book_dirty and now - m.last_eval >= EVAL_MIN_GAP)):
                m.book_dirty = False
                m.last_eval = now
                self.eval_takers(m, now)

    # --- takers (FC, BT) ---------------------------------------------------------------------------------------------
    def eval_takers(self, m, now):
        b = self.books.get(m.ticker)
        if b is None or not b.synced:
            return
        st = m.state
        rel_u = int(math.floor(now - FC_LAG_S)) - m.close_s
        if st["rel"] < rel_u - STALE_S:
            return
        for side in ("yes", "no"):
            asks = asks_of(b, side)
            if not asks:
                continue
            # FC
            if st["fc_p"] is not None and FC_R_MIN <= st["fc_r"] <= FC_R_MAX:
                ps = st["fc_p"] if side == "yes" else 1.0 - st["fc_p"]
                qual = [(q, s) for q, s in asks if FC_MIN_PRICE <= q <= FC_MAX_PRICE and q < 1
                        and ps - float(q) - fee_f(float(q)) >= FC_MIN_EDGE]
                if qual:
                    self.taker_decide(m, "fc", side, qual, ps, now)
            # BT
            t_dec = int(math.floor(now)) - m.close_s
            if st["bt_z"] is not None and st["bt_pc"] is not None and BT_T_START <= t_dec <= 0 and \
                    st["bt_r"] <= BT_MAX_R and abs(st["bt_z"]) >= BT_MIN_Z and (side == "yes") == (st["bt_z"] >= 0):
                pc = st["bt_pc"]
                qual = [(q, s) for q, s in asks if BT_MIN_PRICE <= q <= BT_MAX_PRICE
                        and pc - float(q) - fee_f(float(q)) >= BT_THR]
                if qual:
                    self.taker_decide(m, "bt", side, qual, pc, now)

    def room(self, m, strat, model, side, q, p):
        """Contracts this strategy may still buy at price q under its caps."""
        if strat == "fc":
            a = FC_MAX_SIDE - m.pos.get((strat, model, side), Decimal(0))
            c = FC_MAX_CLOSE - self.close_n.get((strat, model, m.close_s), Decimal(0))
            return floor_n(min(a, c))
        bank = self.bank[model]
        if bank <= 0:
            return Decimal(0)
        qf = float(q)
        c = qf + fee_f(qf)
        if c >= 1:
            return Decimal(0)
        fstar = (p - c) / (1 - c)
        frac = min(BT_KELLY * fstar, BT_MKT_CAP)
        target = Decimal(str(frac)) * bank
        have = m.stake.get((strat, model), Decimal(0))
        cl = Decimal(str(BT_CLOSE_CAP)) * bank - self.close_stake.get((strat, model, m.close_s), Decimal(0))
        dollars = min(target - have, cl)
        if dollars <= Decimal("0.005"):
            return Decimal(0)
        return floor_n(dollars / q)

    def book_fill(self, m, strat, model, side, price, n, kind, extra):
        fee = taker_fee(n, price)
        key = (strat, model, side)
        m.pos[key] = m.pos.get(key, Decimal(0)) + n
        m.stake[(strat, model)] = m.stake.get((strat, model), Decimal(0)) + n * price
        ck = (strat, model, m.close_s)
        self.close_n[ck] = self.close_n.get(ck, Decimal(0)) + n
        self.close_stake[ck] = self.close_stake.get(ck, Decimal(0)) + n * price
        tk = (strat, model, side, price)
        m.taken[tk] = m.taken.get(tk, Decimal(0)) + n
        f = {"ticker": m.ticker, "strat": strat, "model": model, "side": side, "kind": kind, "price": pstr(price),
             "size": str(n), "fee": str(fee)}
        f.update(extra)
        m.fills.append(f)
        self.log.write("fill", **f)

    def avail(self, m, strat, model, side, q, s):
        tk = (strat, model, side, q)
        t = m.taken.get(tk, Decimal(0))
        if t > s:
            t = s
            m.taken[tk] = t
        return s - t

    def taker_decide(self, m, strat, side, qual, p, now):
        # opt: take the displayed size now
        got = []
        for q, s in qual:
            n = min(self.avail(m, strat, "opt", side, q, s), self.room(m, strat, "opt", side, q, p))
            n = floor_n(n)
            if n <= 0:
                continue
            self.book_fill(m, strat, "opt", side, q, n, "taker",
                           {"decided": round(now, 3), "rel": round(now - m.close_s, 3), "p": p})
            got.append((pstr(q), str(n)))
        # real: send a limit order at the worst qualifying price; it fills against what is still there in 1 s
        want = Decimal(0)
        disp = Decimal(0)
        if (strat, side) not in m.pending:
            for q, s in qual:
                a = self.avail(m, strat, "real", side, q, s)
                r = self.room(m, strat, "real", side, q, p) - want
                disp += a
                want += floor_n(min(a, max(r, Decimal(0))))
            if want > 0:
                m.pending[(strat, side)] = {"due": now + TAKER_DELAY, "limit": qual[-1][0], "want": want,
                                            "decided": now, "disp": disp, "p": p}
        if got or want > 0:
            m.n_decisions += 1
            self.log.write("decision", ticker=m.ticker, strat=strat, side=side, rel=round(now - m.close_s, 3),
                           p=p, state_rel=m.state["rel"], offers=[[str(q), str(s)] for q, s in qual],
                           opt_took=got, real_order=({"limit": str(qual[-1][0]), "want": str(want)}
                                                     if want > 0 else None))

    def resolve_pending(self, m, now, force=False):
        for key in list(m.pending):
            pd = m.pending[key]
            if now < pd["due"] and not force:
                continue
            del m.pending[key]
            strat, side = key
            filled = []
            why = None
            b = self.books.get(m.ticker)
            if pd["due"] >= m.close_s:
                why = "market_closed"
            elif b is None or not b.synced:
                why = "book_unsynced"
            else:
                left = pd["want"]
                for q, s in asks_of(b, side):
                    if q > pd["limit"] or left <= 0:
                        break
                    n = floor_n(min(self.avail(m, strat, "real", side, q, s), left))
                    if strat == "fc":
                        n = min(n, self.room(m, strat, "real", side, q, pd["p"]))
                    else:
                        cl = Decimal(str(BT_CLOSE_CAP)) * self.bank["real"] - \
                            self.close_stake.get((strat, "real", m.close_s), Decimal(0))
                        n = min(n, floor_n(cl / q))
                    if n <= 0:
                        continue
                    self.book_fill(m, strat, "real", side, q, n, "taker",
                                   {"decided": round(pd["decided"], 3), "filled_at": round(now, 3),
                                    "rel": round(now - m.close_s, 3), "p": pd["p"],
                                    "same_second_displayed": pstr(pd["disp"]), "limit": str(pd["limit"])})
                    filled.append((pstr(q), str(n)))
                    left -= n
            self.log.write("taker_check", ticker=m.ticker, strat=strat, side=side, want=pstr(pd["want"]),
                           same_second_displayed=pstr(pd["disp"]), limit=str(pd["limit"]), filled=filled,
                           filled_n=pstr(sum((Decimal(x[1]) for x in filled), Decimal(0))), why=why,
                           delay=round(now - pd["decided"], 3))

    # --- contrarian maker (CT) ---------------------------------------------------------------------------------------
    def ct_gate(self, m, now):
        """Side whose bids should be resting now, or None."""
        rel_now = now - m.close_s
        if rel_now < CT_T0 or rel_now >= 0 or m.state is None:
            return None
        S = m.state["ct_side"]
        if S is None or m.state["rel"] < int(math.floor(now - FC_LAG_S)) - m.close_s - STALE_S:
            return None
        lt = m.last_trade
        if lt is None or now - lt[2] > CT_CONF_AGE:
            return None
        last_S = lt[0] if S == "yes" else Decimal(1) - lt[0]
        if last_S < CT_CONFIRM:
            return None
        return S

    def ct_update_real(self, m, now):
        g = self.ct_gate(m, now)
        if g == m.ct_real_gate:
            return
        for o in m.ct_orders:
            if o.live_to is None:
                o.live_to = now + CT_LATENCY
                self.log.write("ct_cancel", ticker=m.ticker, order_id=o.id, side=o.side, price=str(o.price),
                               live_from=round(o.live_from, 3), live_to=round(o.live_to, 3),
                               rel=round(now - m.close_s, 3))
        m.ct_real_gate = g
        if g is None:
            return
        if g != m.ct_real_side:
            m.ct_real_side = g
            m.ct_real_rem = {lv: CT_SIZE for lv in CT_LADDER}
        b = self.books.get(m.ticker)
        for lv in CT_LADDER:
            if m.ct_real_rem.get(lv, 0) <= 0:
                continue
            ahead = Decimal(0)
            if b is not None and b.synced:
                ahead = (b.yes if g == "yes" else b.no).get(lv, Decimal(0))
            o = CtOrder(g, lv, now + CT_LATENCY, ahead)
            m.ct_orders.append(o)
            self.log.write("ct_order", ticker=m.ticker, order_id=o.id, side=g, price=str(lv),
                           rem=str(m.ct_real_rem[lv]), live_from=round(o.live_from, 3), ahead=str(ahead),
                           rel=round(now - m.close_s, 3), book_synced=bool(b and b.synced))

    def on_trade(self, ticker, msg):
        m = self.markets.get(ticker)
        if m is None:
            return
        now = self.now()
        ts_ms = int(msg["ts_ms"])
        ts = ts_ms / 1000.0
        yp = Decimal(msg["yes_price_dollars"])
        cnt = Decimal(msg["count_fp"])
        taker = msg["taker_side"]
        # --- opt: the design's per-trade rule ---
        if m.ct_pend is not None and ts_ms != m.ct_pend[1]:
            m.ct_last = m.ct_pend
        m.ct_pend = (yp, ts_ms)
        t = int(math.floor(ts - m.close_s - CT_LATENCY))
        if CT_T0 <= t < 0:
            S = m.ct_state.get(t)
            if S != m.ct_opt_side:
                m.ct_opt_side = S
                m.ct_opt_rem = {lv: CT_SIZE for lv in CT_LADDER} if S else {}
            if S is not None and taker != S and m.ct_last is not None:
                age = (ts_ms - m.ct_last[1]) / 1000.0
                last_S = m.ct_last[0] if S == "yes" else Decimal(1) - m.ct_last[0]
                if CT_LATENCY <= age <= CT_CONF_AGE and last_S >= CT_CONFIRM:
                    price_S = yp if S == "yes" else Decimal(1) - yp
                    left = cnt
                    for lv in CT_LADDER:
                        if price_S > lv or left <= 0:
                            continue
                        f = min(m.ct_opt_rem.get(lv, Decimal(0)), left)
                        if f <= 0:
                            continue
                        m.ct_opt_rem[lv] -= f
                        left -= f
                        self.ct_fill(m, "opt", S, lv, f, msg, price_S, None)
        # --- real: resting orders with live windows and queue position ---
        left = cnt
        for lv in CT_LADDER:
            for o in m.ct_orders:
                if o.price != lv or left <= 0:
                    continue
                if ts < o.live_from or (o.live_to is not None and ts > o.live_to):
                    continue
                S = o.side
                if taker == S:
                    continue
                price_S = yp if S == "yes" else Decimal(1) - yp
                if price_S > lv:
                    continue
                if price_S == lv:
                    eat = min(left, o.ahead)
                    o.ahead -= eat
                    left -= eat
                f = min(left, m.ct_real_rem.get(lv, Decimal(0)))
                if f <= 0:
                    continue
                m.ct_real_rem[lv] -= f
                left -= f
                self.ct_fill(m, "real", S, lv, f, msg, price_S, o)
        m.last_trade = (yp, ts_ms, now)
        self.ct_update_real(m, now)

    def ct_fill(self, m, model, side, lv, f, msg, price_S, o):
        rec = {"ticker": m.ticker, "strat": "ct", "model": model, "side": side, "kind": "maker", "price": pstr(lv),
               "size": pstr(f), "fee": "0", "trade_id": msg.get("trade_id"), "ts_ms": msg["ts_ms"],
               "print_price": str(price_S), "print_size": str(msg["count_fp"]),
               "rel": round(int(msg["ts_ms"]) / 1000.0 - m.close_s, 3)}
        if o is not None:
            rec.update({"order_id": o.id, "ahead_left": str(o.ahead)})
        m.fills.append(rec)
        key = ("ct", model, side)
        m.pos[key] = m.pos.get(key, Decimal(0)) + f
        self.log.write("fill", **rec)

    # --- settlement --------------------------------------------------------------------------------------------------
    def markets_needing_result(self, now):
        return [m for m in self.markets.values()
                if m.done and not m.settled and now >= m.close_s + 3 and now - m.settle_asked_at >= 10]

    def on_result(self, ticker, result, expiration_value, now):
        m = self.markets.get(ticker)
        if m is None or m.settled:
            return
        if result not in ("yes", "no"):
            if now - m.close_s > SETTLE_TIMEOUT_S:
                m.settled = True
                m.pnl = {}
                self.log.write("settle", ticker=ticker, result=None, timeout=True)
                self.finish_group(m)
            return
        m.result = result
        m.settled = True
        if expiration_value is not None:
            try:
                self.last_expiration[m.coin] = (m.close_s, Decimal(str(expiration_value).replace(",", "")))
            except Exception:
                pass
        d = self.prints.get(m.index_id, {})
        vals = [Decimal(d[s][1]) for s in range(m.close_s - 60, m.close_s) if s in d]
        my_pred = None
        if len(vals) == 60 and m.thr is not None:
            my_pred = "yes" if sum(vals) / Decimal(60) >= m.thr else "no"
        pnl = {}
        for strat in STRATS:
            for model in MODELS:
                tot = n = fee = risk = Decimal(0)
                for f in m.fills:
                    if f["strat"] != strat or f["model"] != model:
                        continue
                    sz = Decimal(f["size"])
                    px = Decimal(f["price"])
                    tot += sz * (Decimal(1) - px) if f["side"] == result else -sz * px
                    n += sz
                    fee += Decimal(f["fee"])
                    risk += sz * px
                if n > 0:
                    pnl[(strat, model)] = {"pnl": (tot - fee).quantize(Decimal("0.0001")), "n": n,
                                           "fee": fee, "risk": risk.quantize(Decimal("0.01"))}
                    self.cum[(strat, model)] += pnl[(strat, model)]["pnl"]
                    if strat == "bt":
                        self.bank[model] += pnl[(strat, model)]["pnl"]
        m.pnl = pnl
        self.log.write("settle", ticker=ticker, coin=m.coin, close_s=m.close_s, result=result,
                       expiration_value=expiration_value, my_pred=my_pred,
                       pred_match=(my_pred == result) if my_pred else None, strike=str(m.strike),
                       strike_src=m.strike_src, n_fills=len(m.fills), n_decisions=m.n_decisions,
                       pnl={"%s_%s" % k: {kk: str(vv) for kk, vv in v.items()} for k, v in pnl.items()})
        self.finish_group(m)

    def finish_group(self, m):
        grp = self.pending_close_groups.get(m.close_s)
        if grp is None:
            return
        grp.discard(m.ticker)
        if grp:
            return
        del self.pending_close_groups[m.close_s]
        ms = [x for x in self.markets.values() if x.close_s == m.close_s]
        summ = {}
        for strat in STRATS:
            summ[strat] = {}
            for model in MODELS:
                rows = [(x, x.pnl[(strat, model)]) for x in ms if (strat, model) in getattr(x, "pnl", {})]
                summ[strat][model] = {
                    "pnl": str(sum((r["pnl"] for _, r in rows), Decimal(0))),
                    "contracts": str(sum((r["n"] for _, r in rows), Decimal(0))),
                    "at_risk": str(sum((r["risk"] for _, r in rows), Decimal(0))),
                    "markets": len(rows),
                    "losing_markets": sum(1 for _, r in rows if r["pnl"] < 0),
                    "cum": str(self.cum[(strat, model)])}
        self.log.write("close_summary", close_s=m.close_s, close=now_iso(m.close_s), markets=len(ms),
                       results={x.coin: x.result for x in ms}, fc=summ["fc"], bt=summ["bt"], ct=summ["ct"],
                       bt_bank={k: str(v) for k, v in self.bank.items()})
        for x in ms:
            self.finished.add(x.ticker)
            self.markets.pop(x.ticker, None)
            self.books.pop(x.ticker, None)
        for k in [k for k in self.close_n if k[2] == m.close_s]:
            del self.close_n[k]
        for k in [k for k in self.close_stake if k[2] == m.close_s]:
            del self.close_stake[k]
        if len(self.finished) > 2000:
            self.finished = set(list(self.finished)[-1000:])


# ------------------------------------------------------------------------------------------------------------ websocket
class WS:
    """Minimal RFC 6455 client (stdlib only).  Reader thread pushes (rx_time, obj) into `q`."""

    def __init__(self, q, log, headers_fn):
        self.q = q
        self.log = log
        self.headers_fn = headers_fn
        self.sock = None
        self.send_lock = threading.Lock()
        self.connected = False
        self.reconnects = -1
        self.next_id = 100
        self.sids = {}                            # channel -> sid
        self.market_sub_id = None                 # id of the current orderbook_delta+trade subscribe request
        self.market_tickers = []
        self.index_ids = []
        self.stop = False
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self):
        self.thread.start()

    def _connect(self):
        raw = socket.create_connection((WS_HOST, 443), timeout=15)
        s = ssl.create_default_context().wrap_socket(raw, server_hostname=WS_HOST)
        s.settimeout(30)
        key = base64.b64encode(os.urandom(16)).decode()
        lines = [f"GET {WS_PATH} HTTP/1.1", f"Host: {WS_HOST}", "Upgrade: websocket", "Connection: Upgrade",
                 f"Sec-WebSocket-Key: {key}", "Sec-WebSocket-Version: 13"]
        for k, v in self.headers_fn("GET", WS_PATH).items():
            lines.append(f"{k}: {v}")
        s.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            c = s.recv(4096)
            if not c:
                raise RuntimeError("closed during handshake")
            buf += c
        head, rest = buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise RuntimeError("handshake: " + head.decode(errors="replace")[:200])
        return s, rest

    def _send_frame(self, op, payload):
        mask = os.urandom(4)
        n = len(payload)
        hdr = bytes([0x80 | op])
        if n < 126:
            hdr += bytes([0x80 | n])
        elif n < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            hdr += bytes([0x80 | 127]) + struct.pack(">Q", n)
        masked = bytes(b ^ mask[i & 3] for i, b in enumerate(payload))
        with self.send_lock:
            if self.sock is None:
                raise RuntimeError("no socket")
            self.sock.sendall(hdr + mask + masked)

    def send_json(self, obj):
        try:
            self._send_frame(0x1, json.dumps(obj).encode())
            return True
        except Exception as e:
            self.log.write("ws_send_error", err=str(e)[:200])
            return False

    def subscribe(self, channels, **params):
        self.next_id += 1
        p = {"channels": channels}
        p.update(params)
        self.send_json({"id": self.next_id, "cmd": "subscribe", "params": p})
        return self.next_id

    def unsubscribe(self, sids):
        self.next_id += 1
        self.send_json({"id": self.next_id, "cmd": "unsubscribe", "params": {"sids": sids}})

    def set_markets(self, tickers):
        """(Re)subscribe orderbook_delta + trade to exactly `tickers` -- new snapshots follow."""
        self.market_tickers = list(tickers)
        if not self.connected:
            return
        old = [self.sids[c] for c in ("orderbook_delta", "trade") if c in self.sids]
        for c in ("orderbook_delta", "trade"):
            self.sids.pop(c, None)
        if old:
            self.unsubscribe(old)
        self.market_sub_id = None
        if self.market_tickers:
            self.market_sub_id = self.subscribe(["orderbook_delta", "trade"], market_tickers=self.market_tickers)
            self.log.write("ws_subscribe", markets=self.market_tickers, unsubscribed=old, sub_id=self.market_sub_id)

    def _on_connect(self):
        """Index + lifecycle only; the main loop subscribes the market channels through set_markets on _ws_up."""
        self.sids = {}
        self.market_sub_id = None
        self.subscribe(["cfbenchmarks_value"], index_ids=self.index_ids)
        self.subscribe(["market_lifecycle_v2"])

    def run(self):
        backoff = 1
        while not self.stop:
            try:
                s, rest = self._connect()
                with self.send_lock:
                    self.sock = s
                self.connected = True
                self.reconnects += 1
                self.log.write("ws_connected", reconnects=self.reconnects)
                self.q.put((time.time(), {"type": "_ws_up"}))
                self._on_connect()
                backoff = 1
                self._read_loop(s, rest)
            except Exception as e:
                self.log.write("ws_error", err=str(e)[:300])
            self.connected = False
            with self.send_lock:
                try:
                    if self.sock:
                        self.sock.close()
                except Exception:
                    pass
                self.sock = None
            self.q.put((time.time(), {"type": "_ws_down"}))
            if self.stop:
                break
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)

    def _read_loop(self, s, buf):
        def need(n):
            nonlocal buf
            while len(buf) < n:
                c = s.recv(262144)
                if not c:
                    raise RuntimeError("socket closed")
                buf += c
        frag = b""
        while not self.stop:
            need(2)
            b0, b1 = buf[0], buf[1]
            fin = b0 & 0x80
            op = b0 & 0x0F
            ln = b1 & 0x7F
            off = 2
            if ln == 126:
                need(4)
                ln = struct.unpack(">H", buf[2:4])[0]
                off = 4
            elif ln == 127:
                need(10)
                ln = struct.unpack(">Q", buf[2:10])[0]
                off = 10
            mask = None
            if b1 & 0x80:
                need(off + 4)
                mask = buf[off:off + 4]
                off += 4
            need(off + ln)
            payload = buf[off:off + ln]
            buf = buf[off + ln:]
            if mask:
                payload = bytes(b ^ mask[i & 3] for i, b in enumerate(payload))
            if op == 0x9:
                try:
                    self._send_frame(0xA, payload)
                except Exception:
                    pass
                continue
            if op == 0xA:
                continue
            if op == 0x8:
                raise RuntimeError("server close frame")
            if op in (0x1, 0x2, 0x0):
                frag += payload
                if not fin:
                    continue
                data, frag = frag, b""
                rx = time.time()
                try:
                    obj = json.loads(data)
                except Exception:
                    continue
                t = obj.get("type")
                if t == "subscribed":
                    ch, sid = obj["msg"]["channel"], obj["msg"]["sid"]
                    if ch in ("orderbook_delta", "trade") and obj.get("id") != self.market_sub_id:
                        self.unsubscribe([sid])       # a superseded request: drop it before it delivers anything
                        self.log.write("ws_unsub_stale", channel=ch, sid=sid, id=obj.get("id"))
                    else:
                        self.sids[ch] = sid
                self.q.put((rx, obj))


# ------------------------------------------------------------------------------------------------------------- REST
class Rest:
    """Background polling thread (GET only, public endpoints).  Results go into `q` as {"type": "_rest_*"}."""

    def __init__(self, q, log, get_fn):
        self.q = q
        self.log = log
        self.get = get_fn
        self.settle_jobs = queue.Queue()
        self.stop = False
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self):
        self.thread.start()

    def get_paced(self, path, params):
        """GET with a small gap between calls and one retry on 429 (a 10-call burst tripped the public rate limit)."""
        time.sleep(0.15)
        st, body = self.get(path, params, auth=False)
        if st == 429:
            time.sleep(1.5)
            st, body = self.get(path, params, auth=False)
        return st, body

    def poll_markets(self):
        out = []
        for coin, (series, _idx, _rd) in COINS.items():
            st, body = self.get_paced("/markets", {"series_ticker": series, "status": "open", "limit": 50})
            if st != 200 or not isinstance(body, dict):
                self.log.write("rest_error", path="/markets", series=series, status=st, body=str(body)[:200])
                continue
            for mk in body.get("markets", []):
                out.append((coin, mk))
        # DOGE: the previous market's expiration_value is the exact strike (floor_strike is truncated to 6 dp)
        st, body = self.get_paced("/markets", {"series_ticker": "KXDOGE15M", "status": "settled", "limit": 5})
        prev = []
        if st == 200 and isinstance(body, dict):
            prev = body.get("markets", [])
        self.q.put((time.time(), {"type": "_rest_markets", "markets": out, "doge_prev": prev}))

    def run(self):
        last_poll = 0
        while not self.stop:
            now = time.time()
            if now - last_poll >= 60:
                last_poll = now
                try:
                    self.poll_markets()
                except Exception as e:
                    self.log.write("rest_error", err=str(e)[:200])
            try:
                ticker = self.settle_jobs.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                st, body = self.get_paced("/markets/" + ticker, None)
                mk = body.get("market", {}) if st == 200 and isinstance(body, dict) else {}
                self.q.put((time.time(), {"type": "_rest_result", "ticker": ticker, "status": st,
                                          "result": mk.get("result"), "expiration_value": mk.get("expiration_value"),
                                          "mstatus": mk.get("status")}))
            except Exception as e:
                self.log.write("rest_error", ticker=ticker, err=str(e)[:200])
                self.q.put((time.time(), {"type": "_rest_result", "ticker": ticker, "status": -1,
                                          "result": None, "expiration_value": None, "mstatus": None}))


# -------------------------------------------------------------------------------------------------------------- live
def market_from_rest(coin, mk, doge_prev, last_expiration):
    ticker = mk["ticker"]
    close_s = parse_close_time(mk["close_time"])
    cs = mk.get("custom_strike") or {}
    rd = int(cs.get("round_digits") or COINS[coin][2])
    strike = None
    src = None
    if cs.get("floor_strike") not in (None, ""):
        strike = Decimal(str(cs["floor_strike"]))
        src = "custom_strike"
    elif mk.get("floor_strike") is not None:
        strike = Decimal(str(mk["floor_strike"]))
        src = "floor_strike"
    if coin == "DOGE":
        pe = last_expiration.get("DOGE")
        cand = None
        if pe and pe[0] == close_s - 900:
            cand = (pe[1], "prev_expiration_value")
        else:
            for p in doge_prev:
                try:
                    if parse_close_time(p["close_time"]) == close_s - 900 and p.get("expiration_value"):
                        cand = (Decimal(str(p["expiration_value"]).replace(",", "")), "prev_expiration_value")
                except Exception:
                    pass
        if cand is not None:
            if strike is not None and strike != cand[0]:
                src = "prev_expiration_value(custom_strike=%s)" % strike
            else:
                src = cand[1]
            strike = cand[0]
    return ticker, coin, close_s, strike, rd, src


# -------------------------------------------------------------------------------------------------------------- live
def load_params(path=PARAMS_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_live(minutes):
    sys.path.insert(0, r"C:\kals-repo\research")
    import kauth  # request-signing helpers only (headers for the WebSocket handshake, GET for market metadata)
    log = Logger(LOG_PATH)
    q = queue.Queue()
    eng = Engine(log, time.time, load_params())
    ws = WS(q, log, kauth.headers)
    ws.index_ids = [COINS[c][1] for c in COINS]
    rest = Rest(q, log, kauth.get)
    log.write("start", pid=os.getpid(), minutes=minutes, python=sys.version.split()[0], rss_mb=rss_mb(),
              log=LOG_PATH, coins=list(COINS), params=PARAMS_PATH,
              rules={"fc": "taker, 0-30 prints left, price 0.75-0.985, model - price - fee >= 0.02, 100/side/market, 400/close",
                     "bt": "taker, last 60 s, price 0.85-0.98, |z|>=4, cal p - price - fee >= 0.005, min(0.25 Kelly, 10% bank)/market, 25% bank/close, bank $1000",
                     "ct": "maker, last 60 s, bids 0.95/0.90/0.80 x50 when p>=0.999 and last trade >=0.97 within 3 s"})
    ws.start()
    rest.start()
    t_end = time.time() + minutes * 60
    last_health = time.time()
    last_active = None
    last_resync = 0
    seq_last = {}
    trade_gaps = 0
    n_msgs = {}
    print_rate = {}
    asked = set()
    while time.time() < t_end:
        drained = 0
        while drained < 5000:
            try:
                rx, obj = q.get_nowait()
            except queue.Empty:
                break
            drained += 1
            t = obj.get("type")
            n_msgs[t] = n_msgs.get(t, 0) + 1
            if t == "cfbenchmarks_value":
                msg = obj["msg"]
                try:
                    data = json.loads(msg["data"])
                    eng.on_print(msg["index_id"], int(data["time"]), data["value"], rx)
                    print_rate[msg["index_id"]] = print_rate.get(msg["index_id"], 0) + 1
                except Exception as e:
                    log.write("bad_print", err=str(e)[:100])
            elif t == "orderbook_delta":
                sid, seq = obj.get("sid"), obj.get("seq")
                exp = seq_last.get(sid)
                if exp is not None and seq != exp + 1:
                    eng.on_gap()
                    log.write("seq_gap", sid=sid, expected=exp + 1, got=seq)
                seq_last[sid] = seq
                eng.on_delta(obj["msg"]["market_ticker"], obj["msg"], seq, sid)
            elif t == "orderbook_snapshot":
                sid, seq = obj.get("sid"), obj.get("seq")
                seq_last[sid] = seq
                eng.on_snapshot(obj["msg"]["market_ticker"], obj["msg"], seq, sid)
            elif t == "trade":
                sid, seq = obj.get("sid"), obj.get("seq")
                exp = seq_last.get(sid)
                if exp is not None and seq != exp + 1:
                    trade_gaps += 1
                seq_last[sid] = seq
                try:
                    eng.on_trade(obj["msg"]["market_ticker"], obj["msg"])
                except Exception as e:
                    log.write("bad_trade", err=str(e)[:200])
            elif t == "_rest_markets":
                for coin, mk in obj["markets"]:
                    try:
                        args = market_from_rest(coin, mk, obj["doge_prev"], eng.last_expiration)
                        if args[2] - time.time() < 1800:
                            eng.add_market(*args)
                    except Exception as e:
                        log.write("bad_market", ticker=mk.get("ticker"), err=str(e)[:200])
            elif t == "_rest_result":
                eng.on_result(obj["ticker"], obj["result"], obj["expiration_value"], time.time())
                asked.discard(obj["ticker"])
            elif t == "_ws_up":
                seq_last = {}
                for b in eng.books.values():
                    b.synced = False
                last_active = None
            elif t == "_ws_down":
                for b in eng.books.values():
                    b.synced = False
            elif t == "error":
                log.write("ws_error_msg", msg=obj.get("msg"))
        now = time.time()
        try:
            eng.tick()
        except Exception as e:
            log.write("tick_error", err=repr(e)[:300])
        active = eng.active_tickers(now)
        if ws.connected and (active != last_active or (eng.resync_wanted and now - last_resync > 5)):
            eng.resync_wanted = False
            last_resync = now
            last_active = active
            ws.set_markets(active)
        for m in eng.markets_needing_result(now):
            if m.ticker not in asked:
                m.settle_asked_at = now
                asked.add(m.ticker)
                rest.settle_jobs.put(m.ticker)
        if now - last_health >= 60:
            lags = sorted(eng.lag_ms)

            def pct(p):
                return round(lags[min(len(lags) - 1, int(p * len(lags)))], 1) if lags else None
            log.write("health", ws=ws.connected, reconnects=max(ws.reconnects, 0), rss_mb=rss_mb(),
                      prints_per_s={k: round(v / (now - last_health), 2) for k, v in print_rate.items()},
                      lag_ms={"p50": pct(0.5), "p90": pct(0.9), "p99": pct(0.99), "n": len(lags)},
                      seq_gaps=eng.n_gaps, trade_seq_gaps=trade_gaps, msgs=n_msgs, markets=len(eng.markets),
                      active=active, books_synced=sum(1 for b in eng.books.values() if b.synced),
                      queue=q.qsize(), cum={"%s_%s" % k: str(v) for k, v in eng.cum.items()},
                      bt_bank={k: str(v) for k, v in eng.bank.items()})
            print_rate = {}
            n_msgs = {}
            last_health = now
        time.sleep(0.02)
    ws.stop = True
    rest.stop = True
    log.write("stop", reason="minutes_elapsed")


# ---------------------------------------------------------------------------------------------------------- self-test
def toy_params():
    table = {}
    for lo, hi in BT_RB:
        for i in range(len(BT_ZB) - 1):
            table["%d-%d|%g-%g" % (lo, hi, BT_ZB[i], BT_ZB[i + 1])] = {"p_cal": 0.995, "n_markets": 100}
    return {"forecaster": {"coins": {c: {"sigma": 1e-4} for c in COINS}, "vr": {}, "zsum": {}, "calc": {}},
            "bettor": {"table": table},
            "contrarian": {"sd": {"%s|%d" % (c, r): 1e-4 for c in COINS for r in range(-60, 0)},
                           "quant": {str(r): [-4 + 8 * i / 2000 for i in range(2001)] for r in range(-60, 0)},
                           "nq": 2001}}


def selftest():
    out = []

    def check(cond, what):
        if not cond:
            raise AssertionError("SELFTEST FAIL: " + what)
        out.append(what)

    # helpers and the models on their own
    check(taker_fee(Decimal(30), Decimal("0.95")) == Decimal("0.10"), "taker fee rounds up to the cent")
    check(S_coef(-1) == 0 and S_coef(-2) == 1 and S_coef(-3) == 5 and S_coef(-61) == 73810, "FC variance geometry S(t)")
    check(abs(prob_yes(100 - 0.005, 0.1, 100, 2) - 0.5) < 1e-9, "FC rounding threshold = strike - half a unit")
    check(bt_rkey(0) == "0-0" and bt_rkey(29) == "11-30" and bt_zkey(-4.2) == "4-5" and bt_zkey(99) == "30-1e+09",
          "BT calibration bins")
    real = load_params()
    fm = FcModel(real["forecaster"])
    check(fm.cm is not None and len(fm.scale) == 12, "real FC parameters load (calibration map + 12 scale buckets)")
    check(len(real["bettor"]["table"]) > 30 and real["contrarian"]["nq"] == 2001 and
          len(real["contrarian"]["quant"]) == 60, "real BT table and CT quantiles load")
    ctm = CtModel(toy_params()["contrarian"])
    check(ctm.p_yes("BTC", -30, 101.0, 99.995) == 1.0 and ctm.p_yes("BTC", -30, 99.0, 99.995) == 0.0,
          "CT empirical model: far above -> 1, far below -> 0")

    # planted world ---------------------------------------------------------------------------------------------
    clock = [0.0]
    sink = []
    eng = Engine(Logger(None, sink), lambda: clock[0], toy_params())
    C = 1_000_000
    clock[0] = C - 300
    eng.add_market("BTC-T", "BTC", C, Decimal("100.00"), 2, "planted")    # certain YES
    eng.add_market("ETH-T", "ETH", C, Decimal("100.00"), 2, "planted")    # certain NO
    eng.add_market("SOL-T", "SOL", C, Decimal("100.00"), 2, "planted")    # straddles the strike: nothing
    for s in range(C - 260, C + 1):
        rx = s + 0.1
        eng.on_print("BRTI", s * 1000, "101.00" if s % 2 else "101.01", rx)
        eng.on_print("ETHUSD_RTI", s * 1000, "99.00" if s % 2 else "99.01", rx)
        eng.on_print("SOLUSD_RTI", s * 1000, "99.999" if s % 2 else "100.001", rx)
    # no book yet: the last-60-s seconds before C-30 decide nothing
    for rel in range(-60, -30):
        clock[0] = C + rel + 0.2
        eng.tick()
    check(not [r for r in sink if r["ev"] in ("fill", "decision", "ct_order")], "no book -> no decisions")
    st = [r for r in sink if r["ev"] == "state" and r["ticker"] == "BTC-T"]
    check(len(st) == 30 and st[0]["rel"] == -60 and st[0]["ct_side"] == "yes" and st[0]["fc_r"] == 59,
          "state logged every second from rel -60; CT locked YES; FC 59 prints to come at rel -60")
    check([r for r in sink if r["ev"] == "state" and r["ticker"] == "SOL-T"][-1]["ct_side"] is None, "SOL not locked")
    clock[0] = C - 30.1
    # BTC: YES asks 0.95 x30, 0.97 x20, 0.985 x40 (edge too thin); YES bid 0.90 x20 (queue for CT)
    eng.on_snapshot("BTC-T", {"no_dollars_fp": [["0.0500", "30.00"], ["0.0300", "20.00"], ["0.0150", "40.00"]],
                              "yes_dollars_fp": [["0.9000", "20.00"]]}, 1)
    # ETH: NO asks 0.96 x500
    eng.on_snapshot("ETH-T", {"yes_dollars_fp": [["0.0400", "500.00"]]}, 2)
    eng.on_snapshot("SOL-T", {"yes_dollars_fp": [["0.5000", "100.00"]], "no_dollars_fp": [["0.4800", "100.00"]]}, 3)
    clock[0] = C - 30 + 0.2
    eng.tick()
    f_opt = [(r["ticker"], r["strat"], r["price"], r["size"]) for r in sink if r["ev"] == "fill" and r["model"] == "opt"]
    check(("BTC-T", "fc", "0.95", "30") in f_opt and ("BTC-T", "fc", "0.97", "20") in f_opt and
          not any(x[0] == "BTC-T" and x[2] == "0.985" for x in f_opt), "FC opt: 30@0.95 + 20@0.97, 0.985 refused (edge < 2c)")
    check(("ETH-T", "fc", "0.96", "100") in f_opt, "FC opt: capped at 100 per side per market")
    check(("BTC-T", "bt", "0.95", "30") in f_opt and ("BTC-T", "bt", "0.97", "20") in f_opt,
          "BT opt: both BTC offers inside 0.85-0.98")
    check(("ETH-T", "bt", "0.96", "104") in f_opt, "BT opt: 10% of the $1,000 bank at 0.96 = 104 contracts")
    check(not [r for r in sink if r["ev"] == "fill" and r["ticker"] == "SOL-T"], "SOL: nothing bought")
    check(not [r for r in sink if r["ev"] == "fill" and r["model"] == "real"], "real fills wait 1 s")
    pend = eng.markets["BTC-T"].pending
    check(pend[("fc", "yes")]["want"] == 50 and pend[("fc", "yes")]["limit"] == Decimal("0.97"),
          "real FC order: want 50 limited at 0.97")
    # 20 of the 0.95 offer vanish before our order could land
    clock[0] = C - 29.5
    eng.on_delta("BTC-T", {"side": "no", "price_dollars": "0.0500", "delta_fp": "-20.00"}, 4, None)
    clock[0] = C - 29 + 0.2
    eng.tick()
    f_real = [(r["ticker"], r["strat"], r["price"], r["size"]) for r in sink if r["ev"] == "fill" and r["model"] == "real"]
    check(("BTC-T", "fc", "0.95", "10") in f_real and ("BTC-T", "fc", "0.97", "20") in f_real,
          "FC real: only what was still displayed 1 s later (10@0.95 + 20@0.97)")
    check(("BTC-T", "bt", "0.95", "10") in f_real and ("ETH-T", "bt", "0.96", "104") in f_real and
          ("ETH-T", "fc", "0.96", "100") in f_real, "BT/ETH real fills")
    tc = [r for r in sink if r["ev"] == "taker_check" and r["ticker"] == "BTC-T" and r["strat"] == "fc"]
    check(len(tc) == 1 and tc[0]["same_second_displayed"] == "50" and tc[0]["filled_n"] == "30",
          "taker_check logs same-second size (50) next to the real fill (30)")
    # contrarian: confirm print, a dump, the confirming side breaks, a dump inside the cancel latency
    for rel in range(-28, -24):
        clock[0] = C + rel + 0.2
        eng.tick()
    clock[0] = C - 24.7
    eng.on_trade("BTC-T", {"ts_ms": int((C - 24.7) * 1000), "yes_price_dollars": "0.9800", "count_fp": "1.00",
                           "taker_side": "yes", "trade_id": "c1"})
    co = [r for r in sink if r["ev"] == "ct_order" and r["ticker"] == "BTC-T"]
    check(len(co) == 3 and [r["price"] for r in co] == ["0.95", "0.90", "0.80"] and co[1]["ahead"] == "20.00",
          "CT: market agrees (YES printed 0.98) -> bids 0.95/0.90/0.80, 20 ahead at 0.90")
    clock[0] = C - 24.0
    eng.on_trade("BTC-T", {"ts_ms": (C - 24) * 1000, "yes_price_dollars": "0.9300", "count_fp": "30.00",
                           "taker_side": "no", "trade_id": "d1"})
    cf = [(r["model"], r["price"], r["size"]) for r in sink if r["ev"] == "fill" and r["strat"] == "ct"]
    check(cf == [("opt", "0.95", "30"), ("real", "0.95", "30")], "CT dump at 0.93 fills the 0.95 bid (both rules)")
    check(any(r["ev"] == "ct_cancel" for r in sink), "CT: last print 0.93 < 0.97 -> cancel sent")
    clock[0] = C - 23.9
    eng.tick()
    clock[0] = C - 23.8
    eng.on_trade("BTC-T", {"ts_ms": int((C - 23.8) * 1000), "yes_price_dollars": "0.9000", "count_fp": "40.00",
                           "taker_side": "no", "trade_id": "d2"})
    cf = [(r["model"], r["price"], r["size"]) for r in sink if r["ev"] == "fill" and r["strat"] == "ct"]
    check(cf[2:] == [("real", "0.95", "20")],
          "CT dump inside the 0.3 s cancel: real fills 20 more at 0.95, 0.90 queue eats the rest; opt nothing")
    # finish the market
    for rel in range(-23, 0):
        clock[0] = C + rel + 0.2
        eng.tick()
    clock[0] = C + 0.5
    eng.tick()
    check(all(m.done for m in eng.markets.values()), "markets done at the close")
    clock[0] = C + 5
    check(len(eng.markets_needing_result(clock[0])) == 3, "three markets ask for a result")
    eng.on_result("BTC-T", "yes", "101.00", clock[0])
    eng.on_result("ETH-T", "no", "99.00", clock[0])
    eng.on_result("SOL-T", "yes", "100.00", clock[0])
    cs = [r for r in sink if r["ev"] == "close_summary"]
    check(len(cs) == 1, "one close summary")
    cs = cs[0]
    check(cs["fc"]["opt"]["pnl"] == "5.6800" and cs["fc"]["real"]["pnl"] == "4.7400",
          "FC pnl: opt 1.95+3.73=5.68, real 1.01+3.73=4.74")
    check(cs["bt"]["opt"]["pnl"] == "5.8300" and cs["bt"]["real"]["pnl"] == "4.8900",
          "BT pnl: opt 1.95+3.88=5.83, real 1.01+3.88=4.89")
    check(cs["ct"]["opt"]["pnl"] == "1.5000" and cs["ct"]["real"]["pnl"] == "2.5000",
          "CT pnl: opt 30x0.05=1.50, real 50x0.05=2.50")
    check(eng.bank["opt"] == Decimal("1005.8300") and eng.bank["real"] == Decimal("1004.8900"),
          "BT bank compounds at settlement")
    check(not eng.markets, "settled markets released")
    # a losing fill costs the price paid
    eng2 = Engine(Logger(None, []), lambda: 0, toy_params())
    m2 = eng2.add_market("L-T", "BTC", 10, Decimal("1"), 2, "planted")
    m2.fills.append({"strat": "fc", "model": "real", "side": "yes", "price": "0.9500", "size": "100", "fee": "0.34"})
    m2.done = True
    eng2.on_result("L-T", "no", "0", 20)
    check(eng2.cum[("fc", "real")] == Decimal("-95.34"), "losing fill: -95 paid - 0.34 fee")
    # empty worlds
    sinkE = []
    clk = [C - 100]
    engE = Engine(Logger(None, sinkE), lambda: clk[0], toy_params())
    engE.add_market("E-T", "BTC", C, Decimal("100.00"), 2, "planted")
    engE.on_snapshot("E-T", {"no_dollars_fp": [["0.0500", "30.00"]]}, 1)
    for rel in range(-60, 1):
        clk[0] = C + rel + 0.5
        engE.tick()
    check(not [r for r in sinkE if r["ev"] in ("fill", "decision", "ct_order")], "empty world (no prints): nothing")
    engE2 = Engine(Logger(None, sinkE), lambda: clk[0], toy_params())
    for s in range(C - 240, C + 1):
        engE2.on_print("BRTI", s * 1000, "101.00", s + 0.1)
    engE2.tick()
    engE2.on_trade("X-T", {"ts_ms": C * 1000, "yes_price_dollars": "0.5000", "count_fp": "1.00", "taker_side": "no"})
    check(not [r for r in sinkE if r["ev"] in ("fill", "decision", "ct_order")], "empty world (no market): nothing")
    # no code path can send an order
    src = open(__file__, encoding="utf-8").read()
    check(src.count("portfolio/" + "orders") == 0 and src.count("/port" + "folio") == 0, "no order endpoint in source")
    check(src.count("url" + "open") == 0 and src.count("PO" + "ST") == 0 and src.count("Req" + "uest(") == 0 and
          src.count("DEL" + "ETE") == 0 and src.count('"P' + 'UT"') == 0 and src.count("create_" + "order") == 0,
          "no HTTP write verb in source")
    uses = set(re.findall(r"kauth\.(\w+)", src))
    check(uses <= {"headers", "get", "py"}, "kauth used only for headers and GET: %s" % sorted(uses))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--minutes", type=float, default=10080)
    a = ap.parse_args()
    t0 = time.time()
    checks = selftest()
    msg = "SELFTEST PASS: %d checks in %.2fs" % (len(checks), time.time() - t0)
    print(msg, flush=True)
    if a.selftest:
        for c in checks:
            print("  ok:", c)
        return 0
    Logger(LOG_PATH).write("selftest", passed=True, checks=len(checks))
    run_live(a.minutes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
