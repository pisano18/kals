r"""Clean-room PAPER bot C -- the three designs the clean room DROPPED, run side by side on live data so they can be
compared with the live bot and with the ladder paper bot (research/cleanroom/locked_average_ladder_re_paper.py).

Built 2026-09-28 from the ladder paper bot's plumbing (WebSocket, auth headers for the market-data subscription, market
discovery, DOGE strike, settlement, heartbeat, logging).  NOTHING in this file can send an order: the only HTTP verb used
is GET via research/kauth.py's helpers, the WebSocket carries market-data subscriptions only, and the self-test scans
this file for any order endpoint or HTTP write verb and fails if one is found.

Settlement (as the ladder bot): settle = round_half_up(mean of the 60 index prints stamped close-60..close-1 s);
YES iff mean >= thr, thr = strike - 0.5 * 10**-round_digits.

Every second rel = -60..-1 of every up/down market, at close+rel+0.2 s once the print stamped close+rel is RECEIVED
(skipped if it has not arrived by +0.9 s), with all window prints present, three independent rules decide.  Each keeps
its own positions; tables are the designers' TRAIN fits, copied unchanged into bettor_paper_models.json.

  BETTOR (design-bettor/sim_bettor.py, holdout command defaults): taker, last 60 s.  z = (proj - thr)/sd with
    sd = v*sigma*sqrt(sum_j (j-k)^2)/60 over the future window prints, sigma = std of 1-s log returns of the last 120 s
    (>= 20 returns).  Needs |z| >= 4.  p_cal = TRAIN calibration table (remaining-prints bin x |z| bin).  Buys ONLY the
    favoured side, at each displayed ask q with 0.85 <= q <= 0.98 and p_cal - q - 0.07q(1-q) >= 0.005.  Size: dollars per
    market <= min(0.25 x Kelly, 10%) of a $1,000 bank, dollars per close (all coins) <= 25% of it ($250).  Whole contracts.
    Bank fixed at $1,000 (the refuter's no-compounding setting), so every day is comparable.
  FORECASTER (design-forecaster/sim.py, favourites holdout): taker, remaining prints r <= 30.  Model 'blendvr' with the
    TRAIN z-scale and TRAIN calibration map.  Buys EITHER side at a displayed ask q with 0.75 <= q <= 0.985 when
    p_side - q - 0.07q(1-q) >= 0.02; at most 100 contracts per side per market and 400 per close.
  CONTRARIAN (design-contrarian/sim.py, holdout: pmin 0.999, ladder 0.95/0.90/0.80 x 50, confirm 0.97): maker.  Side S is
    'locked' when the TRAIN quantile model gives P(S) >= 0.999; orders rest only while the market agrees (the latest trade
    print at least 0.3 s old -- one I could have reacted to -- is at most 3 s old and priced S >= 0.97).  Bids at 0.95/0.90/0.80, 50 each; a level's 50 resets when the locked side
    changes.  Orders go live 0.3 s after the decision and a cancel lands 0.3 s after it is decided.

Fill rules -- BOTH logged on every fill; every pnl is reported under both:
  taker 'real' (the refuters' rule): the order fills only for size STILL displayed at the same price 1.0 s after the
    decision (and never after the close), up to the size shown at the decision, minus what this rule already took there.
  taker 'opt': fills at the decision instant for the displayed size (minus what it already took at that level).
  maker 'real': a trade printed after the order's live time where the taker SOLD my side at or through my price fills
    me up to that trade's size; a trade AT my price first eats the size that was displayed ahead of me when I placed the
    order; one trade's size is spent level by level from the top (it never fills every rung at once); a bid that would
    cross the displayed ask gets nothing.
  maker 'opt': as real but nobody ahead of me, and a crossing bid takes the displayed ask (taker fee charged).
  Fees: taker 0.07 x n x p x (1-p) rounded UP to the cent per fill; maker 0.

Usage:
  python research/cleanroom/bettor_paper.py --selftest          # planted worlds only, then exit
  python research/cleanroom/bettor_paper.py --minutes 10080     # self-test, then live paper trading
Log: C:\kals-repo\results\cleanroom-bettor.jsonl (one JSON per line, UTC).  close_summary per quarter-hour.
"""
import argparse
import base64
import bisect
import ctypes
import json
import math
import os
import queue
import socket
import ssl
import struct
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP, ROUND_CEILING

NAME = "bettor"
LOG_PATH = r"C:\kals-repo\results\cleanroom-%s.jsonl" % NAME
MODELS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bettor_paper_models.json")
WS_HOST = "api.elections.kalshi.com"
WS_PATH = "/trade-api/ws/v2"

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

REL_FIRST = -60
DECIDE_OFFSET = 0.2
DECIDE_DEADLINE = 0.9
SETTLE_TIMEOUT_S = 1500
TAKER_FEE_RATE = Decimal("0.07")
BANK = 1000.0
STRATS = ("bettor", "forecaster", "contrarian")
FILLS = ("opt", "real")
SURVIVE_S = 1.0
# bettor
B_MIN_Z, B_MIN_PRICE, B_MAX_PRICE, B_THR = 4.0, 0.85, 0.98, 0.005
B_KELLY, B_MKT_CAP, B_CLOSE_CAP = 0.25, 0.10, 0.25
B_VOLWIN, B_MIN_RET = 120, 20
RB = [(0, 0), (1, 10), (11, 30), (31, 59), (60, 60)]
ZB = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 8, 10, 15, 20, 30, 1e9]
# forecaster
F_R_MAX, F_MIN_PRICE, F_MAX_PRICE, F_MIN_EDGE, F_MAX_SIDE, F_MAX_CLOSE = 30, 0.75, 0.985, 0.02, 100, 400
# contrarian
C_PMIN, C_LADDER, C_SIZE, C_CONFIRM, C_CONF_AGE, C_LAT = 0.999, (0.95, 0.90, 0.80), 50, 0.97, 3.0, 0.3
MAX_PRICE = {"bettor": B_MAX_PRICE, "forecaster": F_MAX_PRICE, "contrarian": max(C_LADDER)}


# ----------------------------------------------------------------------------------------------------------- helpers
def now_iso(t=None):
    return datetime.fromtimestamp(time.time() if t is None else t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def phi(z):
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def fee1(q):
    return 0.07 * q * (1.0 - q)


def taker_fee(n, price):
    raw = TAKER_FEE_RATE * Decimal(str(n)) * Decimal(str(price)) * (Decimal(1) - Decimal(str(price)))
    return float(raw.quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def rkey(r):
    for lo, hi in RB:
        if lo <= r <= hi:
            return "%d-%d" % (lo, hi)
    return "60-60"


def zkey(z):
    z = abs(z)
    for i in range(len(ZB) - 1):
        if ZB[i] <= z < ZB[i + 1]:
            return "%g-%g" % (ZB[i], ZB[i + 1])
    return "?"


def s_coef(t):
    """sum over future seconds i = t+1..-1 of (number of window prints stamped >= i)^2 (forecaster geometry)."""
    s = 0
    for i in range(t + 1, 0):
        c = -max(i, -60)
        if c > 0:
            s += c * c
    return s


def f_bucket(r):
    for a, b in [(0, 1), (2, 3), (4, 6), (7, 10), (11, 15), (16, 20), (21, 30), (31, 45), (46, 60), (61, 90), (91, 120), (121, 181)]:
        if a <= r <= b:
            return "%d-%d" % (a, b)
    return "121-181"


def f_map(conf, pts):
    if conf <= pts[0][0]:
        return conf
    for i in range(1, len(pts)):
        if conf <= pts[i][0]:
            x0, y0 = pts[i - 1]
            x1, y1 = pts[i]
            return y0 + (y1 - y0) * (conf - x0) / (x1 - x0) if x1 > x0 else y1
    return min(1.0, conf - (pts[-1][0] - pts[-1][1]))


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


class Tables:
    """The designers' TRAIN-fitted tables (extracted unchanged)."""

    def __init__(self, path=MODELS_PATH):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        self.bcal = d["bettor_calib"]
        fc = d["forecaster"]
        self.f_sigma = fc["coins"]
        self.f_vr = fc["vr"]
        self.f_zscale = fc["zscale"]
        self.f_cm = {b: [tuple(x) for x in v] for b, v in fc["calmap"].items()}
        ct = d["contrarian"]
        self.c_nq = ct["nq"]
        self.c_sd = ct["sd"]
        self.c_quant = {int(k): v for k, v in ct["quant"].items()}

    def b_lookup(self, r, z):
        return self.bcal.get("%s|%s" % (rkey(r), zkey(z)))

    def c_p_yes(self, coin, rel, proj, thr):
        s = self.c_sd.get("%s|%d" % (coin, rel))
        q = self.c_quant.get(rel)
        if s is None or q is None or proj <= 0 or s <= 0:
            return None
        z = (thr - proj) / proj / s
        return 1.0 - bisect.bisect_left(q, z) / self.c_nq

    def f_sig(self, coin, r, local):
        g = self.f_sigma.get(coin)
        if g is None:
            return None
        s = math.sqrt(0.5 * g * g + 0.5 * local * local) if local is not None else g
        k = "5" if r <= 7 else "10" if r <= 15 else "30" if r <= 45 else "60"
        vr = self.f_vr.get(coin, {}).get(k)
        if vr:
            s *= math.sqrt(max(0.7, vr))
        return s * self.f_zscale.get(f_bucket(r), 1.0)

    def f_calibrate(self, p, r):
        pts = self.f_cm.get(f_bucket(r))
        if not pts:
            return p
        conf = max(p, 1 - p)
        adj = f_map(conf, pts)
        return adj if p >= 0.5 else 1 - adj


# ------------------------------------------------------------------------------------------------------------ engine
class Market:
    def __init__(self, ticker, coin, close_s, strike, round_digits, strike_src):
        self.ticker = ticker
        self.coin = coin
        self.index_id = COINS[coin][1]
        self.close_s = close_s
        self.strike = strike
        self.rd = round_digits
        self.strike_src = strike_src
        self.thr = None
        self.thr_f = None
        if strike is not None:
            self.thr = strike - Decimal(1).scaleb(-round_digits) / 2
            self.thr_f = float(self.thr)
        self.next_rel = REL_FIRST
        self.done = False
        self.fills = []                           # {strat, fill, side, price, size, fee, ...}
        self.pending = []                         # taker 'real' orders waiting for the 1 s survival check
        self.taken = {}                           # (strat, fill, side, price_str) -> contracts taken at that level
        self.spent = {}                           # (strat, fill) -> dollars in this market (bettor)
        self.side_n = {}                          # (strat, fill, side) -> contracts (forecaster)
        self.c_orders = []                        # contrarian resting orders
        self.c_side = None
        self.c_filled = {}
        self.recent_trades = deque(maxlen=64)     # (ts_s, yes_price float) of the latest trade prints
        self.result = None
        self.expiration_value = None
        self.settle_asked_at = 0
        self.settled = False
        self.n_decisions = 0


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

    def asks(self, side):
        """Displayed asks for `side`, cheapest first: [(price Decimal, size float)] (ask = 1 - the other side's bid)."""
        lad = self.no if side == "yes" else self.yes
        return sorted((Decimal(1) - p, float(s)) for p, s in lad.items() if s > 0)

    def ask_size_at(self, side, price):
        lad = self.no if side == "yes" else self.yes
        return float(lad.get(Decimal(1) - price, Decimal(0)))

    def bid_size_at(self, side, price):
        lad = self.yes if side == "yes" else self.no
        return float(lad.get(price, Decimal(0)))

    def best_ask(self, side):
        a = self.asks(side)
        return a[0] if a else (None, 0.0)


class COrder:
    _n = 0

    def __init__(self, ticker, side, level, price, live_from, ahead, rem_opt, rem_real):
        COrder._n += 1
        self.id = COrder._n
        self.ticker = ticker
        self.side = side
        self.level = level
        self.price = price                        # float
        self.live_from = live_from
        self.live_to = None
        self.ahead = ahead
        self.rem = {"opt": rem_opt, "real": rem_real}


class Engine:
    """Everything the bot decides, with the clock injected so a planted world can drive it."""

    def __init__(self, log, now_fn, tables, strats=STRATS):
        self.log = log
        self.now = now_fn
        self.tb = tables
        self.strats = tuple(strats)
        self.prints = {}
        self.markets = {}
        self.books = {}
        self.pending_close_groups = {}
        self.close_spent = {}                     # (strat, fill, close_s) -> dollars (bettor) / contracts (forecaster)
        self.cum = {(s, f): 0.0 for s in STRATS for f in FILLS}
        self.n_gaps = 0
        self.lag_ms = deque(maxlen=2000)
        self.print_count = {}
        self.resync_wanted = False
        self.last_expiration = {}
        self.finished = set()
        self.n_skip = 0
        self.n_dec = 0

    # --- feed inputs -------------------------------------------------------------------------------------------------
    def on_print(self, index_id, stamp_ms, value_str, rx):
        stamp_s = stamp_ms // 1000
        d = self.prints.setdefault(index_id, {})
        try:
            d[stamp_s] = (float(value_str), value_str, rx)
        except ValueError:
            return
        self.print_count[index_id] = self.print_count.get(index_id, 0) + 1
        self.lag_ms.append(rx * 1000 - stamp_ms)
        if len(d) > 360:
            cutoff = stamp_s - 300
            for k in [k for k in d if k < cutoff]:
                del d[k]

    def on_snapshot(self, ticker, msg, seq, sid=None):
        if ticker in self.markets:
            self.books.setdefault(ticker, Book()).load(msg, seq, sid)

    def on_delta(self, ticker, msg, seq, sid=None):
        b = self.books.get(ticker)
        if b is not None:
            b.delta(msg["side"], msg["price_dollars"], msg["delta_fp"], seq, sid)

    def on_gap(self):
        self.n_gaps += 1
        for b in self.books.values():
            b.synced = False
        self.resync_wanted = True

    def on_trade(self, ticker, msg):
        m = self.markets.get(ticker)
        if m is None:
            return
        ts = msg["ts_ms"] / 1000.0
        yes_p = float(msg["yes_price_dollars"])
        cnt = float(msg["count_fp"])
        taker = msg["taker_side"]
        live = [o for o in m.c_orders if ts >= o.live_from and (o.live_to is None or ts < o.live_to)]
        left = {"opt": cnt, "real": cnt}
        for o in sorted(live, key=lambda x: -x.price):     # a sweep reaches the top rung first; its size is spent once
            if o.side == "yes":
                if taker != "no" or yes_p > o.price + 1e-9:
                    continue
                trade_p = yes_p
            else:
                if taker != "yes" or (1.0 - yes_p) > o.price + 1e-9:
                    continue
                trade_p = round(1.0 - yes_p, 4)
            f = {}
            f["opt"] = min(left["opt"], o.rem["opt"])
            if trade_p < o.price - 1e-9:
                f["real"] = min(left["real"], o.rem["real"])
            else:
                eat = min(left["real"], o.ahead)
                o.ahead -= eat
                left["real"] -= eat
                f["real"] = min(left["real"], o.rem["real"])
            for fm in FILLS:
                if f[fm] > 0:
                    o.rem[fm] -= f[fm]
                    left[fm] -= f[fm]
                    m.c_filled[(o.level, fm)] = m.c_filled.get((o.level, fm), 0.0) + f[fm]
                    self.add_fill(m, "contrarian", fm, o.side, o.price, f[fm], 0.0, kind="rest", order_id=o.id,
                                  trade_id=msg.get("trade_id"), ts_ms=msg["ts_ms"], print_price=trade_p,
                                  print_size=cnt, ahead_left=o.ahead)
        m.recent_trades.append((ts, yes_p))

    def add_fill(self, m, strat, fm, side, price, size, fee, **extra):
        rec = {"strat": strat, "fill": fm, "ticker": m.ticker, "side": side, "price": round(price, 4),
               "size": size, "fee": fee}
        rec.update(extra)
        m.fills.append(rec)
        self.log.write("fill", **rec)

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
        elif strike is not None and (m.strike != strike or m.strike_src != strike_src) and m.next_rel == REL_FIRST:
            m.strike, m.rd, m.strike_src = strike, round_digits, strike_src
            m.thr = strike - Decimal(1).scaleb(-round_digits) / 2
            m.thr_f = float(m.thr)
            self.log.write("market_update", ticker=ticker, strike=str(strike), strike_src=strike_src, thr=str(m.thr))
        return m

    def active_tickers(self, now):
        best = {}
        for m in self.markets.values():
            if m.close_s > now and (m.coin not in best or m.close_s < best[m.coin].close_s):
                best[m.coin] = m
        return sorted(x.ticker for x in best.values())

    # --- model pieces --------------------------------------------------------------------------------------------------
    def b_sigma(self, index_id, k):
        """bettor: std (mean removed) of 1-s log returns ending at stamps k-120..k, >= 20 returns."""
        d = self.prints.get(index_id, {})
        ks = [s for s in range(k - B_VOLWIN - 1, k + 1) if s in d]
        n, s1, s2 = 0, 0.0, 0.0
        for a, b in zip(ks, ks[1:]):
            if b < k - B_VOLWIN or d[a][0] <= 0 or d[b][0] <= 0:
                continue
            x = math.log(d[b][0] / d[a][0])
            n += 1
            s1 += x
            s2 += x * x
        if n < B_MIN_RET:
            return None
        return math.sqrt(max(s2 / n - (s1 / n) ** 2, 1e-14))

    def f_local_sigma(self, index_id, t):
        """forecaster: RMS of consecutive 1-s log returns over the last 120 s (>= 8), else None."""
        d = self.prints.get(index_id, {})
        acc, n = 0.0, 0
        for s in range(t, t - 121, -1):
            if s in d and (s - 1) in d and d[s][0] > 0 and d[s - 1][0] > 0 and s - 1 >= t - 120 - 1:
                x = math.log(d[s][0] / d[s - 1][0])
                acc += x * x
                n += 1
        if n < 8:
            return None
        return math.sqrt(acc / n)

    def exact_mean(self, m):
        d = self.prints.get(m.index_id, {})
        vals = [Decimal(d[s][1]) for s in range(m.close_s - 60, m.close_s) if s in d]
        if len(vals) != 60:
            return None
        return sum(vals) / Decimal(60)

    # --- decisions ---------------------------------------------------------------------------------------------------
    def tick(self):
        now = self.now()
        for m in list(self.markets.values()):
            self.resolve_pending(m, now)
            if m.done:
                continue
            if now >= m.close_s:
                self.c_cancel(m, m.close_s, "close", immediate=True)
                m.done = True
                continue
            while not m.done and m.next_rel <= -1:
                rel = m.next_rel
                if now < m.close_s + rel + DECIDE_OFFSET:
                    break
                stamp = m.close_s + rel
                pr = self.prints.get(m.index_id, {}).get(stamp)
                if pr is not None and pr[2] <= now:
                    self.decide(m, rel, pr, now)
                    m.next_rel += 1
                elif now > m.close_s + rel + DECIDE_DEADLINE:
                    self.n_skip += 1
                    self.c_cancel(m, now, "no_print")
                    self.log.write("decision", ticker=m.ticker, rel=rel, skipped="no_print")
                    m.next_rel += 1
                else:
                    break

    def decide(self, m, rel, pr, now):
        v, v_str, rx = pr
        d = self.prints.get(m.index_id, {})
        stamp = m.close_s + rel
        lo = m.close_s - 60
        got = [d[s][0] for s in range(lo, stamp + 1) if s in d]
        locked_n = len(got)
        missing = locked_n < stamp - lo + 1
        r = 60 - locked_n
        proj = (sum(got) + r * v) / 60.0
        m.n_decisions += 1
        self.n_dec += 1
        rec = {"ticker": m.ticker, "rel": rel, "lag_ms": round((rx - stamp) * 1000), "proj": round(proj, 8)}
        b = self.books.get(m.ticker)
        if m.thr is None or missing:
            rec["skipped"] = "no_strike" if m.thr is None else "missing_prints"
            self.c_cancel(m, now, rec["skipped"])
            self.log.write("decision", **rec)
            return
        exact_yes = None
        if rel == -1:
            em = self.exact_mean(m)
            if em is not None:
                exact_yes = em >= m.thr
        book_ok = b is not None and b.synced
        act = False
        if "bettor" in self.strats:
            out = self.bettor(m, rel, v, proj, r, exact_yes, b if book_ok else None, now)
            rec["b"] = out
            act = act or bool(out.get("n"))
        if "forecaster" in self.strats:
            out = self.forecaster(m, rel, v, proj, r, exact_yes, b if book_ok else None, now)
            rec["f"] = out
            act = act or bool(out.get("n"))
        if "contrarian" in self.strats:
            out = self.contrarian(m, rel, proj, b if book_ok else None, now)
            rec["c"] = out
            act = act or bool(out.get("n"))
        if not book_ok:
            rec["book"] = "unsynced"
        if act or rel % 10 == 0 or rel == -1:
            self.log.write("decision", **rec)

    # taker plumbing shared by bettor and forecaster ---------------------------------------------------------------------
    def take(self, m, strat, side, b, now, rel, levels_fn, extra):
        """levels_fn(fm, price_float) -> max contracts wanted at that price under fill rule fm (0 = stop/skip).
        opt fills now; real reserves and is checked 1 s later.  Returns number of fills/pendings created."""
        n = 0
        asks = b.asks(side)
        for fm in FILLS:
            for pD, disp in asks:
                q = float(pD)
                want = levels_fn(fm, q)
                if want is None:
                    break
                if want <= 0:
                    continue
                key = (strat, fm, side, str(pD))
                avail = disp - self.pend_at(m, key) - m.taken.get(key, 0.0)
                k = math.floor(min(want, avail) + 1e-9)
                if k < 1:
                    continue
                if fm == "opt":
                    m.taken[key] = m.taken.get(key, 0.0) + k
                    self.book_spend(m, strat, fm, side, q, k)
                    self.add_fill(m, strat, fm, side, q, k, taker_fee(k, q), kind="take", rel=rel, displayed=disp,
                                  **extra)
                else:
                    self.book_spend(m, strat, fm, side, q, k)
                    m.pending.append({"strat": strat, "side": side, "price": pD, "want": k, "t_dec": now, "rel": rel,
                                      "displayed": disp, "key": key, "extra": extra})
                    self.log.write("taker_order", strat=strat, ticker=m.ticker, side=side, price=str(pD), want=k,
                                   rel=rel, displayed=disp, check_at=round(now + SURVIVE_S, 3), **extra)
                n += 1
        return n

    def pend_at(self, m, key):
        return sum(p["want"] for p in m.pending if p["key"] == key)

    def book_spend(self, m, strat, fm, side, q, k):
        m.spent[(strat, fm)] = m.spent.get((strat, fm), 0.0) + k * q
        m.side_n[(strat, fm, side)] = m.side_n.get((strat, fm, side), 0.0) + k
        ck = (strat, fm, m.close_s)
        self.close_spent[ck] = self.close_spent.get(ck, 0.0) + (k * q if strat == "bettor" else k)

    def resolve_pending(self, m, now):
        if not m.pending:
            return
        keep = []
        for p in m.pending:
            due = p["t_dec"] + SURVIVE_S
            if now < due:
                keep.append(p)
                continue
            q = float(p["price"])
            self.book_spend(m, p["strat"], "real", p["side"], q, -p["want"])     # release the reservation
            b = self.books.get(m.ticker)
            why = None
            if due >= m.close_s:
                why, k, still = "closed", 0, None
            elif b is None or not b.synced:
                why, k, still = "book_unsynced", 0, None
            else:
                still = b.ask_size_at(p["side"], p["price"])
                k = math.floor(min(p["want"], p["displayed"], still - m.taken.get(p["key"], 0.0)) + 1e-9)
                if k < 1:
                    why, k = "gone", 0
            if k >= 1:
                m.taken[p["key"]] = m.taken.get(p["key"], 0.0) + k
                self.book_spend(m, p["strat"], "real", p["side"], q, k)
                self.add_fill(m, p["strat"], "real", p["side"], q, k, taker_fee(k, q), kind="take", rel=p["rel"],
                              displayed=p["displayed"], still_1s=still, want=p["want"], **p["extra"])
            else:
                self.log.write("taker_miss", strat=p["strat"], ticker=m.ticker, side=p["side"], price=str(p["price"]),
                               want=p["want"], rel=p["rel"], why=why, still_1s=still)
        m.pending = keep

    # BETTOR -------------------------------------------------------------------------------------------------------------
    def bettor(self, m, rel, v, proj, r, exact_yes, b, now):
        k = rel
        if exact_yes is not None:
            z = 50.0 if exact_yes else -50.0
            sig = None
        else:
            sig = self.b_sigma(m.index_id, m.close_s + k)
            if sig is None:
                return {"why": "no_sigma"}
            w = sum((j - k) ** 2 for j in range(max(k + 1, -60), 0))
            if w <= 0:
                z = 50.0 if proj >= m.thr_f else -50.0
            else:
                sd = v * sig * math.sqrt(w) / 60.0
                z = (proj - m.thr_f) / sd if sd > 0 else (50.0 if proj >= m.thr_f else -50.0)
                z = max(-99.0, min(99.0, z))
        out = {"z": round(z, 2), "r": r}
        if abs(z) < B_MIN_Z:
            out["why"] = "z"
            return out
        pc = self.tb.b_lookup(r, z)
        out["pc"] = pc
        if pc is None:
            out["why"] = "no_calib"
            return out
        if b is None:
            out["why"] = "book"
            return out
        side = "yes" if z >= 0 else "no"

        def want(fm, q):
            if q > B_MAX_PRICE:
                return None
            if q < B_MIN_PRICE:
                return 0
            c = q + fee1(q)
            if pc - c < B_THR:
                return 0
            fstar = (pc - c) / (1 - c) if c < 1 else 0.0
            target = min(B_KELLY * fstar, B_MKT_CAP) * BANK
            room = min(target - m.spent.get(("bettor", fm), 0.0),
                       B_CLOSE_CAP * BANK - self.close_spent.get(("bettor", fm, m.close_s), 0.0))
            if room <= 0.005:
                return 0
            return room / q

        out["side"] = side
        out["n"] = self.take(m, "bettor", side, b, now, rel, want, {"z": round(z, 2), "p_cal": pc})
        return out

    # FORECASTER ---------------------------------------------------------------------------------------------------------
    def forecaster(self, m, rel, v, proj, r, exact_yes, b, now):
        if r > F_R_MAX:
            return {"why": "r"}
        t = rel
        if exact_yes is not None:
            p = 1.0 if exact_yes else 0.0
        else:
            s = self.tb.f_sig(m.coin, r, self.f_local_sigma(m.index_id, m.close_s + t))
            if s is None:
                return {"why": "no_sigma"}
            sd = v * s * math.sqrt(s_coef(t)) / 60.0
            p = (1.0 if proj >= m.thr_f else 0.0) if sd <= 0 else 1.0 - phi((m.thr_f - proj) / sd)
        p = self.tb.f_calibrate(p, r)
        out = {"p": round(p, 6), "r": r, "n": 0}
        if b is None:
            out["why"] = "book"
            return out
        for side in ("yes", "no"):
            ps = p if side == "yes" else 1.0 - p

            def want(fm, q, ps=ps, side=side):
                if q > F_MAX_PRICE or q >= 1.0:
                    return None
                if q < F_MIN_PRICE:
                    return 0
                if ps - q - fee1(q) < F_MIN_EDGE:
                    return 0
                return min(F_MAX_SIDE - m.side_n.get(("forecaster", fm, side), 0.0),
                           F_MAX_CLOSE - self.close_spent.get(("forecaster", fm, m.close_s), 0.0))

            out["n"] += self.take(m, "forecaster", side, b, now, rel, want, {"p_side": round(ps, 6)})
        return out

    # CONTRARIAN ---------------------------------------------------------------------------------------------------------
    def contrarian(self, m, rel, proj, b, now):
        py = self.tb.c_p_yes(m.coin, rel, proj, m.thr_f)
        S = None
        if py is not None:
            S = "yes" if py >= C_PMIN else ("no" if 1 - py >= C_PMIN else None)
        out = {"p": py, "S": S}
        if S != m.c_side:
            self.c_cancel(m, now, "side_change")
            m.c_side = S
            m.c_filled = {}
        if S is None:
            return out
        lt = None                                 # the latest print I could have reacted to (>= 0.3 s old)
        for tr in reversed(m.recent_trades):
            if now - tr[0] >= C_LAT - 1e-9:
                lt = tr
                break
        conf = False
        if lt is not None:
            age = now - lt[0]
            s_price = lt[1] if S == "yes" else 1.0 - lt[1]
            conf = C_LAT <= age <= C_CONF_AGE and s_price >= C_CONFIRM - 1e-9
            out["last"] = [round(age, 2), round(s_price, 4)]
        out["conf"] = conf
        if not conf or b is None:
            self.c_cancel(m, now, "no_confirm" if not conf else "book")
            return out
        live = {o.level for o in m.c_orders if o.live_to is None and o.side == S}
        n = 0
        for lv in C_LADDER:
            if lv in live:
                continue
            rem = {fm: C_SIZE - m.c_filled.get((lv, fm), 0.0) for fm in FILLS}
            if rem["opt"] <= 0 and rem["real"] <= 0:
                continue
            ahead = b.bid_size_at(S, Decimal(str(lv)).quantize(Decimal("0.0001")))
            o = COrder(m.ticker, S, lv, lv, now + C_LAT, ahead, rem["opt"], rem["real"])
            m.c_orders.append(o)
            n += 1
            ask_p, ask_sz = b.best_ask(S)
            crossed = ask_p is not None and float(ask_p) <= lv + 1e-9 and ask_sz > 0
            self.log.write("order", strat="contrarian", ticker=m.ticker, order_id=o.id, side=S, price=lv,
                           rem_opt=rem["opt"], rem_real=rem["real"], live_from=round(o.live_from, 3), ahead=ahead,
                           rel=rel, crossed_ask=float(ask_p) if crossed else None)
            if crossed:
                qa = float(ask_p)
                k = min(ask_sz, o.rem["opt"])
                if k > 0:
                    o.rem["opt"] -= k
                    m.c_filled[(lv, "opt")] = m.c_filled.get((lv, "opt"), 0.0) + k
                    self.add_fill(m, "contrarian", "opt", S, qa, k, taker_fee(k, qa), kind="cross", order_id=o.id)
        out["n"] = n
        return out

    def c_cancel(self, m, now, why, immediate=False):
        n = 0
        for o in m.c_orders:
            if o.live_to is None:
                o.live_to = now if immediate else now + C_LAT
                n += 1
                self.log.write("cancel", strat="contrarian", ticker=m.ticker, order_id=o.id, side=o.side,
                               price=o.price, live_to=round(o.live_to, 3), rem_opt=o.rem["opt"],
                               rem_real=o.rem["real"], why=why)
        return n

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
                self.log.write("settle", ticker=ticker, result=None, timeout=True)
                self.finish_group(m)
            return
        m.result = result
        m.expiration_value = expiration_value
        m.settled = True
        if expiration_value is not None:
            try:
                self.last_expiration[m.coin] = (m.close_s, Decimal(str(expiration_value).replace(",", "")))
            except Exception:
                pass
        em = self.exact_mean(m)
        my_pred = None
        if em is not None:
            my_settle = em.quantize(Decimal(1).scaleb(-m.rd), rounding=ROUND_HALF_UP)
            my_pred = "yes" if (m.strike is not None and my_settle >= m.strike) else "no"
        m.book = {}
        for s in STRATS:
            for fm in FILLS:
                pnl, n, cost, fee = 0.0, 0.0, 0.0, 0.0
                for f in m.fills:
                    if f["strat"] != s or f["fill"] != fm:
                        continue
                    win = f["side"] == result
                    pnl += f["size"] * (1 - f["price"]) if win else -f["size"] * f["price"]
                    n += f["size"]
                    cost += f["size"] * f["price"]
                    fee += f["fee"]
                pnl -= fee
                m.book[(s, fm)] = (round(pnl, 4), n, round(cost, 4))
                self.cum[(s, fm)] += pnl
        rec = {"ticker": ticker, "coin": m.coin, "close_s": m.close_s, "result": result,
               "expiration_value": expiration_value, "my_pred": my_pred,
               "pred_match": (my_pred == result) if my_pred else None, "strike": str(m.strike), "n_fills": len(m.fills)}
        for (s, fm), (pnl, n, cost) in m.book.items():
            if n > 0:
                rec["%s_%s" % (s, fm)] = {"pnl": pnl, "contracts": n, "cost": cost}
        self.log.write("settle", **rec)
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
        for s in STRATS:
            for fm in FILLS:
                pnl = n = cost = 0.0
                traded, losers = [], []
                for x in ms:
                    bk = getattr(x, "book", {}).get((s, fm))
                    if bk and bk[1] > 0:
                        pnl += bk[0]
                        n += bk[1]
                        cost += bk[2]
                        traded.append(x.coin)
                        if bk[0] < 0:
                            losers.append(x.coin)
                summ["%s_%s" % (s, fm)] = {"pnl": round(pnl, 4), "contracts": n, "cost": round(cost, 2),
                                           "coins": traded, "losing": losers, "cum": round(self.cum[(s, fm)], 4)}
        self.log.write("close_summary", close_s=m.close_s, close=now_iso(m.close_s), markets=len(ms), **summ)
        for x in ms:
            self.finished.add(x.ticker)
            self.markets.pop(x.ticker, None)
            self.books.pop(x.ticker, None)
        for k in [k for k in self.close_spent if k[2] <= m.close_s]:
            del self.close_spent[k]
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


def run_live(minutes):
    sys.path.insert(0, r"C:\kals-repo\research")
    import kauth  # request-signing helpers only
    log = Logger(LOG_PATH)
    q = queue.Queue()
    eng = Engine(log, time.time, Tables())
    ws = WS(q, log, kauth.headers)
    ws.index_ids = [COINS[c][1] for c in COINS]
    rest = Rest(q, log, kauth.get)
    log.write("start", pid=os.getpid(), minutes=minutes, python=sys.version.split()[0], rss_mb=rss_mb(),
              log=LOG_PATH, coins=list(COINS), strats=list(STRATS), max_price=MAX_PRICE, bank=BANK)
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
            elif t == "market_lifecycle_v2":
                msg = obj["msg"]
                if msg.get("market_ticker") in eng.markets and msg.get("event_type") in ("determined", "metadata_updated"):
                    log.write("lifecycle", **{k: v for k, v in msg.items() if k != "additional_metadata"})
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
                      queue=q.qsize(), decisions=eng.n_dec, skipped=eng.n_skip,
                      cum={"%s_%s" % k: round(v, 4) for k, v in eng.cum.items()})
            print_rate = {}
            n_msgs = {}
            last_health = now
        time.sleep(0.02)
    ws.stop = True
    rest.stop = True
    log.write("stop", reason="minutes_elapsed")


# ---------------------------------------------------------------------------------------------------------- self-test
def selftest():
    """Planted worlds with known fills and money for each rule, plus empty worlds that must do nothing."""
    out = []

    def check(cond, what):
        if not cond:
            raise AssertionError("SELFTEST FAIL: " + what)
        out.append(what)

    tb = Tables()
    # helpers --------------------------------------------------------------------------------------------------------
    check(rkey(0) == "0-0" and rkey(5) == "1-10" and rkey(30) == "11-30" and rkey(59) == "31-59" and rkey(60) == "60-60", "rkey bins")
    check(zkey(4.2) == "4-5" and zkey(-50) == "30-1e+09" and zkey(3.99) == "3.5-4", "zkey bins")
    check(tb.b_lookup(59, 50.0) == 1.0 and abs(tb.b_lookup(60, 4.5) - 0.99206) < 1e-4, "bettor calibration table loaded (TRAIN values)")
    check(s_coef(-1) == 0 and s_coef(-2) == 1 and s_coef(-3) == 5 and s_coef(-61) == 73810, "forecaster S(t)")
    pts = [(0.55, 0.55), (0.95, 0.90)]
    check(abs(f_map(0.95, pts) - 0.90) < 1e-12 and abs(f_map(0.75, pts) - 0.725) < 1e-12 and abs(f_map(0.99, pts) - 0.94) < 1e-12, "forecaster calibration map")
    check(taker_fee(30, 0.95) == 0.10 and taker_fee(12, 0.95) == 0.04 and taker_fee(10, 0.97) == 0.03, "taker fee ceil to cent")
    check(tb.c_p_yes("BTC", -30, 101.005, 99.995) == 1.0 and tb.c_p_yes("BTC", -30, 99.0, 99.995) == 0.0, "contrarian quantile model: far above -> 1, far below -> 0")
    pmid = tb.c_p_yes("BTC", -30, 99.995, 99.995)
    check(0.2 < pmid < 0.8, "contrarian model at the strike is uncertain")

    C = 1_000_000

    def world(strats, yes_vals=("101.00", "101.01")):
        clock = [0.0]
        sink = []
        eng = Engine(Logger(None, sink), lambda: clock[0], tb, strats)
        eng.add_market("BTC-T", "BTC", C, Decimal("100.00"), 2, "planted")
        for s in range(C - 240, C + 1):
            eng.on_print("BRTI", s * 1000, yes_vals[s % 2], s + 0.1)
        return eng, sink, clock

    # BETTOR ---------------------------------------------------------------------------------------------------------
    eng, sink, clock = world(["bettor"])
    # YES asks: 0.95 x 30 (NO bid 0.05), 0.97 x 10 (NO bid 0.03), 0.99 x 500 (NO bid 0.01, above the 0.98 cap)
    eng.on_snapshot("BTC-T", {"no_dollars_fp": [["0.0500", "30.00"], ["0.0300", "10.00"], ["0.0100", "500.00"]],
                              "yes_dollars_fp": [["0.9000", "5.00"]]}, 1)
    clock[0] = C - 60 + 0.2
    eng.tick()
    d = [r for r in sink if r["ev"] == "decision"]
    check(len(d) == 1 and d[0]["rel"] == -60 and d[0]["b"]["side"] == "yes" and d[0]["b"]["z"] >= 4 and d[0]["b"]["r"] == 59,
          "bettor decides at rel -60: favoured YES, |z| >= 4, 59 prints to come")
    fo = [r for r in sink if r["ev"] == "fill" and r["fill"] == "opt"]
    check([(r["price"], r["size"]) for r in fo] == [(0.95, 30), (0.97, 10)], "bettor opt: takes 30 @0.95 and 10 @0.97 (displayed), not 0.99 (> 0.98)")
    to = [r for r in sink if r["ev"] == "taker_order"]
    check([(r["price"], r["want"]) for r in to] == [("0.9500", 30), ("0.9700", 10)], "bettor real: same two orders wait for the 1 s check")
    # half a second later the 0.95 level shrinks to 12 and the 0.97 level vanishes
    eng.on_delta("BTC-T", {"side": "no", "price_dollars": "0.0500", "delta_fp": "-18.00"}, 2)
    eng.on_delta("BTC-T", {"side": "no", "price_dollars": "0.0300", "delta_fp": "-10.00"}, 3)
    clock[0] = C - 59 + 0.2
    eng.tick()
    fr = [r for r in sink if r["ev"] == "fill" and r["fill"] == "real"]
    check([(r["price"], r["size"]) for r in fr] == [(0.95, 12)], "bettor real: only the 12 still displayed 1 s later fill")
    check(len([r for r in sink if r["ev"] == "taker_miss" and r["why"] == "gone"]) == 1, "bettor real: the vanished 0.97 level is logged as a miss")
    check(len([r for r in sink if r["ev"] == "fill"]) == 3, "no re-buy of a level already taken (level consumption)")
    # sizing cap: a deep 0.95 level is capped at the 10%-of-bank market stake ($100 total)
    engS, sinkS, clockS = world(["bettor"])
    engS.on_snapshot("BTC-T", {"no_dollars_fp": [["0.0500", "5000.00"]]}, 1)
    clockS[0] = C - 60 + 0.2
    engS.tick()
    fs = [r for r in sinkS if r["ev"] == "fill" and r["fill"] == "opt"]
    check(len(fs) == 1 and fs[0]["size"] == 105, "bettor stake cap: $100 / 0.95 -> 105 whole contracts")
    # close: all expire, settle YES
    for rel in range(-58, 0):
        clock[0] = C + rel + 0.2
        eng.tick()
    clock[0] = C + 5
    eng.tick()
    for m in eng.markets_needing_result(clock[0]):
        eng.on_result(m.ticker, "yes", "101.00", clock[0])
    st = [r for r in sink if r["ev"] == "settle"][0]
    check(abs(st["bettor_opt"]["pnl"] - (30 * 0.05 + 10 * 0.03 - 0.10 - 0.03)) < 1e-9, "bettor opt pnl 1.67 after fees")
    check(abs(st["bettor_real"]["pnl"] - (12 * 0.05 - 0.04)) < 1e-9, "bettor real pnl 0.56 after fees")
    cs = [r for r in sink if r["ev"] == "close_summary"]
    check(len(cs) == 1 and abs(cs[0]["bettor_opt"]["pnl"] - 1.67) < 1e-9 and abs(cs[0]["bettor_real"]["pnl"] - 0.56) < 1e-9
          and cs[0]["bettor_real"]["contracts"] == 12, "close_summary carries both fill rules")
    check(not eng.markets, "settled markets released")
    # a losing side costs the price paid
    engL, sinkL, clockL = world(["bettor"])
    engL.on_snapshot("BTC-T", {"no_dollars_fp": [["0.0500", "30.00"]]}, 1)
    clockL[0] = C - 60 + 0.2
    engL.tick()
    clockL[0] = C + 5
    engL.tick()
    engL.on_result("BTC-T", "no", "99", clockL[0])
    stL = [r for r in sinkL if r["ev"] == "settle"][0]
    check(abs(stL["bettor_opt"]["pnl"] - (-30 * 0.95 - 0.10)) < 1e-9, "losing bettor fill loses 30 x 0.95 + fee")

    # FORECASTER -----------------------------------------------------------------------------------------------------
    engF, sinkF, clockF = world(["forecaster"])
    engF.on_snapshot("BTC-T", {"no_dollars_fp": [["0.2000", "50.00"], ["0.0100", "500.00"]],
                               "yes_dollars_fp": [["0.0100", "40.00"]]}, 1)
    for rel in range(-60, -31):
        clockF[0] = C + rel + 0.2
        engF.tick()
    check(not [r for r in sinkF if r["ev"] in ("fill", "taker_order")], "forecaster idle while more than 30 prints remain")
    clockF[0] = C - 31 + 0.2
    engF.tick()
    df = [r for r in sinkF if r["ev"] == "decision" and r["rel"] == -31][0]
    check(df["f"]["r"] == 30 and df["f"]["p"] > 0.99, "forecaster active at r = 30 with calibrated p > 0.99")
    ff = [r for r in sinkF if r["ev"] == "fill" and r["fill"] == "opt"]
    check([(r["side"], r["price"], r["size"]) for r in ff] == [("yes", 0.8, 50)], "forecaster opt: 50 YES @0.80; 0.99 is above 0.985; NO @0.99 has no edge")
    engF.on_delta("BTC-T", {"side": "no", "price_dollars": "0.2000", "delta_fp": "-30.00"}, 2)
    clockF[0] = C - 30 + 0.2
    engF.tick()
    fr = [r for r in sinkF if r["ev"] == "fill" and r["fill"] == "real"]
    check([(r["price"], r["size"]) for r in fr] == [(0.8, 20)], "forecaster real: 20 still displayed after 1 s")
    # a fair world: price at the model -> nothing
    engFa, sinkFa, clockFa = world(["forecaster"])
    engFa.on_snapshot("BTC-T", {"no_dollars_fp": [["0.0020", "500.00"]]}, 1)
    clockFa[0] = C - 20 + 0.2
    for rel in range(-60, -19):
        clockFa[0] = C + rel + 0.2
        engFa.tick()
    check(not [r for r in sinkFa if r["ev"] in ("fill", "taker_order")], "forecaster: no edge at 0.998 -> nothing")

    # CONTRARIAN -----------------------------------------------------------------------------------------------------
    engC, sinkC, clockC = world(["contrarian"])
    engC.on_snapshot("BTC-T", {"yes_dollars_fp": [["0.9500", "20.00"]], "no_dollars_fp": [["0.0200", "100.00"]]}, 1)
    for rel in range(-60, -31):
        clockC[0] = C + rel + 0.2
        engC.tick()
    check(not [r for r in sinkC if r["ev"] == "order"], "contrarian: locked but no market confirmation -> no orders")
    engC.on_trade("BTC-T", {"ts_ms": (C - 31) * 1000, "yes_price_dollars": "0.9800", "count_fp": "5.00", "taker_side": "yes", "trade_id": "a"})
    clockC[0] = C - 30 + 0.2
    engC.tick()
    oc = [r for r in sinkC if r["ev"] == "order"]
    check([r["price"] for r in oc] == [0.95, 0.90, 0.80] and oc[0]["ahead"] == 20.0 and abs(oc[0]["live_from"] - (C - 29.5)) < 1e-6,
          "contrarian: confirmed -> bids 0.95/0.90/0.80, 20 ahead at 0.95, live 0.3 s later")
    engC.on_trade("BTC-T", {"ts_ms": (C - 30) * 1000 + 400, "yes_price_dollars": "0.9500", "count_fp": "99.00", "taker_side": "no", "trade_id": "early"})
    check(not [r for r in sinkC if r["ev"] == "fill"], "a trade before the order is live does not fill")
    engC.on_trade("BTC-T", {"ts_ms": (C - 29) * 1000 + 100, "yes_price_dollars": "0.9500", "count_fp": "30.00", "taker_side": "no", "trade_id": "b"})
    engC.on_trade("BTC-T", {"ts_ms": (C - 29) * 1000 + 150, "yes_price_dollars": "0.8500", "count_fp": "100.00", "taker_side": "no", "trade_id": "c"})
    fc = [(r["fill"], r["price"], r["size"]) for r in sinkC if r["ev"] == "fill"]
    check(fc == [("opt", 0.95, 30.0), ("real", 0.95, 10.0), ("opt", 0.95, 20.0), ("real", 0.95, 40.0),
                 ("opt", 0.9, 50.0), ("real", 0.9, 50.0)],
          "contrarian fills: queue ahead eaten first (real 10 of 30), one sweep spent rung by rung, 0.80 not reached")
    clockC[0] = C - 29 + 0.2
    engC.tick()
    check(any(r["ev"] == "cancel" and r["why"] == "no_confirm" and abs(r["live_to"] - (C - 28.5)) < 1e-6 for r in sinkC),
          "contrarian: last print at 0.85 < 0.97 -> cancel, landing 0.3 s later")
    for rel in range(-28, 0):
        clockC[0] = C + rel + 0.2
        engC.tick()
    clockC[0] = C + 5
    engC.tick()
    engC.on_result("BTC-T", "yes", "101.00", clockC[0])
    stC = [r for r in sinkC if r["ev"] == "settle"][0]
    check(abs(stC["contrarian_opt"]["pnl"] - (50 * 0.05 + 50 * 0.10)) < 1e-9 and abs(stC["contrarian_real"]["pnl"] - 7.5) < 1e-9,
          "contrarian pnl 7.50 under both rules, no maker fee")

    # EMPTY worlds ---------------------------------------------------------------------------------------------------
    clockE = [C - 100]
    sinkE = []
    engE = Engine(Logger(None, sinkE), lambda: clockE[0], tb)
    engE.add_market("E-T", "BTC", C, Decimal("100.00"), 2, "planted")
    for rel in range(-60, 1):
        clockE[0] = C + rel + 0.95
        engE.tick()
    check(not [r for r in sinkE if r["ev"] in ("order", "fill", "taker_order")], "empty world (no prints): nothing placed")
    check(len([r for r in sinkE if r["ev"] == "decision" and r.get("skipped")]) == 60, "empty world: 60 skipped seconds")
    engU, sinkU, clockU = world(STRATS, yes_vals=("99.994", "99.996"))   # index sitting on the rounding threshold
    engU.on_snapshot("BTC-T", {"no_dollars_fp": [["0.1000", "500.00"]], "yes_dollars_fp": [["0.8900", "500.00"]]}, 1)
    engU.on_trade("BTC-T", {"ts_ms": (C - 61) * 1000, "yes_price_dollars": "0.9800", "count_fp": "5.00", "taker_side": "yes", "trade_id": "u"})
    for rel in range(-60, -40):
        clockU[0] = C + rel + 0.2
        engU.tick()
    check(not [r for r in sinkU if r["ev"] in ("order", "fill", "taker_order")], "coin-flip world (index on the strike): no rule trades")
    # no code path can send an order
    src = open(__file__, encoding="utf-8").read()
    check(src.count("portfolio/" + "orders") == 0 and src.count("/port" + "folio") == 0, "no order endpoint in source")
    check(src.count("url" + "open") == 0 and src.count("PO" + "ST") == 0 and src.count("Req" + "uest(") == 0
          and src.count("create_" + "order") == 0 and src.count("DEL" + "ETE") == 0,
          "no HTTP write path in source (GET via kauth helpers only)")
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
