r"""Clean-room PAPER bot C -- the three DROPPED schools run side by side on the live feed: contrarian, bettor, forecaster.

Built 2026-09-28 from the ladder paper bot's plumbing (locked_average_ladder_re_paper.py: WebSocket, market discovery,
settlement, logging).  NOTHING in this file can send an order: the only HTTP verb is GET via research/kauth.py's helpers,
the WebSocket is used for market-data subscriptions only, and the self-test scans this file for any order endpoint or
write verb and fails if one is present.  Every fill below is imaginary.

Settlement rule (clean-room digest, verified on the tape):
  settle = round_half_up(mean of the 60 CF Benchmarks RTI prints stamped close-60 .. close-1 s, round_digits)
  YES iff mean >= thr, thr = strike - 0.5 * 10**-round_digits   (DOGE strike = previous market's expiration_value)

The three rules, parameters exactly as each design froze them (fitted parameters copied UNCHANGED from the design
folders into contrarian_paper_params.json, TRAIN 2026-08-25..09-17 fits):

  CONTRARIAN ("locked-side liquidity provider", design v7).  Every second rel = -60..-1, when the print stamped
  close+rel arrives: proj = (sum of window prints so far + (60 - their count) * latest) / 60; P(YES) from the design's
  empirical model (per-coin sd of (settle-proj)/proj at that second, pooled empirical z quantiles; p = 1 - i/2001).
  Locked side S = YES if P >= 0.999, NO if P(NO) >= 0.999.  Rest bids for S at 0.95 / 0.90 / 0.80, 50 contracts each
  (50 per level per locked episode), ONLY while the market agrees: the last trade print showed S at >= 0.97 within the
  last 3 s.  Maker, no fee, hold to settlement.  Highest price paid: 95c.

  BETTOR ("near-certain corner with Kelly caps").  In the last 60 s: z = (proj - thr) / sd, sd from the market's own
  120-s realised vol (random walk to each remaining print); if |z| >= 4, the favoured side's calibrated win rate p_cal
  (the design's TRAIN table by remaining-prints bin x |z| bin) beats ask + taker fee by >= 0.5c, and the ask is 85-98c:
  buy as a taker.  Stake per market min(0.25 x Kelly, 10% of bank), per close <= 25% of bank, bank $1,000 compounding
  on the REALISTIC fills.  Highest price paid: 98c + fee (98.14c).

  FORECASTER ("locked-average favourites").  When 30 or fewer settlement prints remain: calibrated model P (blended
  global/120-s vol x per-coin variance ratio x per-bucket z-scale, then the TRAIN calibration map); buy side s as a
  taker at any ask 75-98.5c where P(s) - ask - 0.07*ask*(1-ask) >= 2c.  Caps 100 contracts per side per market, 400
  per close.  Highest price paid: 98.5c + fee (98.6c).

Fill models -- BOTH logged on every fill, money summed separately in every settle / close_summary:
  opt  (the design's own, kind):
       maker -- a trade printed after decision+0.3 s in which the taker SOLD my side at <= my bid fills me up to its
                size; orders exist exactly while the rule says (instant cancel); no queue.  (One print's size is spent
                across ladder levels -- the design double-counted it; fixed.)
       taker -- the size displayed at the decision instant (the same-second fill).
  real (the refuters' rule):
       maker -- an order is live from decision+0.3 s until 0.3 s after the decision to cancel (a real cancel is not
                instant); a trade at my price first eats the size that was displayed ahead of me when I placed it; a
                trade strictly through my price fills me up to its size.
       taker -- only size still displayed 1 s after the decision (book at t+1 s, net of what this strategy already
                assumed it took); the stricter "never dipped below" count over [t, t+1 s] is logged as contracts_strict.
  Taker fee = 0.07 x n x p x (1-p) rounded up to the cent per leg; maker fee 0 (unverified assumption, as in the designs).

Usage:
  python research/cleanroom/contrarian_paper.py --selftest
  python research/cleanroom/contrarian_paper.py --minutes 10080
Log: C:\kals-repo\results\cleanroom-contrarian.jsonl (one JSON per line, UTC).  Records carry "strat" where relevant.
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

NAME = "contrarian"
LOG_PATH = r"C:\kals-repo\results\cleanroom-%s.jsonl" % NAME
PARAMS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contrarian_paper_params.json")
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

STRATS = ("contrarian", "bettor", "forecaster")
FILLM = ("opt", "real")
REL_FIRST = -60
DECIDE_DEADLINE = 0.9
TAKER_FEE_RATE = Decimal("0.07")
SETTLE_TIMEOUT_S = 1500

# contrarian (design v7: --confirm 0.97 --pmin 0.999 --ladder 0.95,0.90,0.80 --size 50 --t0 -60 --latency 0.3)
C_PMIN = 0.999
C_LADDER = (Decimal("0.95"), Decimal("0.90"), Decimal("0.80"))
C_SIZE = Decimal("50.00")
C_CONFIRM = 0.97
C_CONF_AGE = 3.0
C_LAT = 0.3
REAL_PLACE_LAT = 0.3
REAL_CANCEL_LAT = 0.3
# bettor (sim_bettor.py defaults = the chosen strategy)
B_MIN_Z = 4.0
B_MIN_PRICE = 0.85
B_MAX_PRICE = 0.98
B_THR = 0.005
B_KELLY = 0.25
B_MKT_CAP = 0.10
B_CLOSE_CAP = 0.25
B_BANK0 = 1000.0
B_MAX_R = 60
B_VOLWIN = 120
B_MIN_RET = 20
B_RB = [(0, 0), (1, 10), (11, 30), (31, 59), (60, 60)]
B_ZB = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 8, 10, 15, 20, 30, 1e9]
# forecaster (holdout command: --min-edge 0.02 --r-max 30 --min-price 0.75 --max-price 0.985, 100/side/market, 400/close)
F_R_MAX = 30
F_MIN_PRICE = 0.75
F_MAX_PRICE = 0.985
F_MIN_EDGE = 0.02
F_MAX_SIDE = 100
F_MAX_CLOSE = 400
F_LAG = 0.15
TAKER_SURVIVE_S = 1.0


# ----------------------------------------------------------------------------------------------------------- helpers
def now_iso(t=None):
    return datetime.fromtimestamp(time.time() if t is None else t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def phi(z):
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def fee_f(q):
    return 0.07 * q * (1.0 - q)


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


# ------------------------------------------------------------------------------------------------------------ models
class ContrModel:
    """design-contrarian/sim.py Model.p_yes, unchanged."""

    def __init__(self, P):
        self.sd = P["sd"]
        self.quant = {int(k): v for k, v in P["quant"].items()}
        self.nq = P["nq"]

    def p_yes(self, coin, rel, proj, strike):
        s = self.sd.get("%s|%d" % (coin, rel))
        q = self.quant.get(rel)
        if s is None or q is None or proj <= 0 or s <= 0:
            return None
        z = (strike - proj) / proj / s
        i = bisect.bisect_left(q, z)
        return 1.0 - i / self.nq


def b_rkey(r):
    for lo, hi in B_RB:
        if lo <= r <= hi:
            return "%d-%d" % (lo, hi)
    return "60-60"


def b_zkey(z):
    z = abs(z)
    for i in range(len(B_ZB) - 1):
        if B_ZB[i] <= z < B_ZB[i + 1]:
            return "%g-%g" % (B_ZB[i], B_ZB[i + 1])
    return "?"


class BettorModel:
    """design-bettor fit_calib.lookup over the TRAIN calibration table."""

    def __init__(self, P):
        self.table = P["table"]

    def lookup(self, r, z):
        return self.table.get("%s|%s" % (b_rkey(r), b_zkey(z)))


_S_CACHE = {}


def s_coef(t):
    """design-forecaster fc_common.S_coef."""
    if t in _S_CACHE:
        return _S_CACHE[t]
    s = 0
    for i in range(t + 1, 0):
        c = 0 - max(i, -60)
        if c > 0:
            s += c * c
    _S_CACHE[t] = s
    return s


class FcModel:
    """design-forecaster model.Model(kind='blendvr', zscale=True, calmap=True)."""

    def __init__(self, P):
        self.g = P["coins"]
        self.vr = P["vr"]
        self.scale = P["zscale"]
        self.cm = {}
        for k, (pred, real, n) in P["calc"].items():
            _m, b, _e = k.split("|")
            if n >= 30:
                self.cm.setdefault(b, []).append((pred, real))
        for b in self.cm:
            self.cm[b].sort()

    @staticmethod
    def bucket(r):
        for a, b in [(0, 1), (2, 3), (4, 6), (7, 10), (11, 15), (16, 20), (21, 30), (31, 45), (46, 60), (61, 90),
                     (91, 120), (121, 181)]:
            if a <= r <= b:
                return "%d-%d" % (a, b)
        return "121-181"

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

    def prob(self, coin, t, v, locked_sum, locked_n, local_sig, thr):
        """P(YES) knowing every print stamped <= t (t = seconds rel close, <= -1)."""
        g = self.g.get(coin)
        if g is None or v is None or t is None or t > -1:
            return None, None
        r = 60 - locked_n if t >= -60 else (-61 - t) + 60
        s = math.sqrt(0.5 * g * g + 0.5 * local_sig * local_sig) if local_sig is not None else g
        k = "5" if r <= 7 else "10" if r <= 15 else "30" if r <= 45 else "60"
        vr = self.vr.get(coin, {}).get(k)
        if vr:
            s *= math.sqrt(max(0.7, vr))
        s *= self.scale.get(self.bucket(r), 1.0)
        proj = (locked_sum + (60 - locked_n) * v) / 60.0
        sd = v * s * math.sqrt(s_coef(t)) / 60.0
        if sd <= 0:
            p = 1.0 if proj >= thr else 0.0
        else:
            p = 1.0 - phi((thr - proj) / sd)
        pts = self.cm.get(self.bucket(r))
        if pts:
            conf = max(p, 1 - p)
            adj = self._map(conf, pts)
            p = adj if p >= 0.5 else 1 - adj
        return p, r


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
        self.result = None
        self.settled = False
        self.settle_asked_at = 0
        self.n_decisions = 0
        self.fills = []                           # every strategy; each fill has "strat"
        # trade prints: design's "last print before this millisecond" (opt) and the newest print received (real)
        self.tp_last = None
        self.tp_pend = None
        self.tp_recv = None
        # contrarian
        self.c_side = {}                          # rel -> "yes"/"no"/None
        self.c_latest = None
        self.c_cur_opt = None
        self.c_rem_opt = {}
        self.c_ep_side = None
        self.c_rem_real = {}
        self.orders = []
        self.n_orders = 0
        # takers
        self.pending = {}                         # strat -> take
        self.consumed = {}                        # (strat, side, Decimal price) -> contracts assumed taken
        self.tcost = {"bettor": 0.0, "forecaster": 0.0}   # $ committed (real fills + pending)
        self.tn = {"bettor": {"yes": 0, "no": 0}, "forecaster": {"yes": 0, "no": 0}}
        self.bstate = (None, None)
        self.fstate = (None, None)


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
        """Offers for `side`, cheapest first: (price, size), price = 1 - the other side's bid."""
        other = self.no if side == "yes" else self.yes
        return sorted(((Decimal(1) - p, s) for p, s in other.items()), key=lambda x: x[0])


class Order:
    _n = 0

    def __init__(self, ticker, side, level, price, live_from, ahead):
        Order._n += 1
        self.id = Order._n
        self.ticker = ticker
        self.side = side
        self.level = level
        self.price = price
        self.live_from = live_from
        self.live_to = None
        self.ahead = ahead


class Engine:
    """Everything the bot decides, with the clock injected so a planted world can drive it."""

    def __init__(self, log, now_fn, params):
        self.log = log
        self.now = now_fn
        self.cm = ContrModel(params["contrarian"])
        self.bm = BettorModel(params["bettor"])
        self.fm = FcModel(params["forecaster"])
        self.prints = {}
        self.markets = {}
        self.books = {}
        self.pending_close_groups = {}
        self.cum = {s: {"opt": Decimal(0), "real": Decimal(0)} for s in STRATS}
        self.bank = {"opt": B_BANK0, "real": B_BANK0}
        self.close_tot = {"bettor": {}, "forecaster": {}}
        self.n_gaps = 0
        self.lag_ms = deque(maxlen=2000)
        self.print_count = {}
        self.max_stamp = {}
        self.resync_wanted = False
        self.last_expiration = {}
        self.finished = set()
        self.take_n = 0
        self.counts = {"orders": 0, "cancels": 0, "fills_opt": 0, "fills_real": 0, "takes": 0, "take_real_zero": 0}

    # --- feed inputs -------------------------------------------------------------------------------------------------
    def on_print(self, index_id, stamp_ms, value_str, rx):
        stamp_s = stamp_ms // 1000
        d = self.prints.setdefault(index_id, {})
        try:
            d[stamp_s] = (float(value_str), value_str, rx)
        except ValueError:
            return
        self.print_count[index_id] = self.print_count.get(index_id, 0) + 1
        if stamp_s > self.max_stamp.get(index_id, -1):
            self.max_stamp[index_id] = stamp_s
        self.lag_ms.append(rx * 1000 - stamp_ms)
        if len(d) > 300:
            cutoff = stamp_s - 240
            for k in [k for k in d if k < cutoff]:
                del d[k]

    def on_snapshot(self, ticker, msg, seq, sid=None):
        if ticker in self.markets:
            self.books.setdefault(ticker, Book()).load(msg, seq, sid)
            self.track_pending(self.markets[ticker], self.now())

    def on_delta(self, ticker, msg, seq, sid=None):
        b = self.books.get(ticker)
        if b is not None:
            b.delta(msg["side"], msg["price_dollars"], msg["delta_fp"], seq, sid)
            m = self.markets.get(ticker)
            if m is not None and m.pending:
                self.track_pending(m, self.now())

    def on_gap(self):
        self.n_gaps += 1
        for b in self.books.values():
            b.synced = False
        self.resync_wanted = True

    def on_trade(self, ticker, msg, rx):
        m = self.markets.get(ticker)
        if m is None:
            return
        try:
            ts_ms = int(msg["ts_ms"])
            yp = Decimal(msg["yes_price_dollars"])
            cnt = Decimal(msg["count_fp"])
            taker = msg["taker_side"]
        except Exception:
            return
        if m.tp_pend is not None and ts_ms != m.tp_pend[0]:
            m.tp_last = m.tp_pend
        m.tp_pend = (ts_ms, yp)
        if ts_ms / 1000.0 < m.close_s and taker in ("yes", "no"):
            self.contr_opt_trade(m, ts_ms, yp, cnt, taker, msg.get("trade_id"))
            self.contr_real_trade(m, ts_ms, yp, cnt, taker, msg.get("trade_id"))
        m.tp_recv = (ts_ms, yp, rx)
        self.contr_update_real(m, rx)

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

    def window_state(self, m, upto_stamp):
        d = self.prints.get(m.index_id, {})
        lo = m.close_s - 60
        got = [d[s] for s in range(lo, upto_stamp + 1) if s in d]
        return got, upto_stamp - lo + 1

    def exact_mean(self, m):
        d = self.prints.get(m.index_id, {})
        vals = [Decimal(d[s][1]) for s in range(m.close_s - 60, m.close_s) if s in d]
        if len(vals) != 60:
            return None
        return sum(vals) / Decimal(60)

    # --- model states ------------------------------------------------------------------------------------------------
    def latest_stamp(self, m):
        d = self.prints.get(m.index_id, {})
        now = self.now()
        mx = self.max_stamp.get(m.index_id)
        if mx is not None and mx <= m.close_s - 1 and d.get(mx, (0, 0, now + 1))[2] <= now:
            return mx                              # live fast path: the newest print is already received
        best = None
        for s, x in d.items():
            if s <= m.close_s - 1 and x[2] <= now and (best is None or s > best):
                best = s
        return best

    def bettor_state(self, m):
        """design-bettor build_ds.Model.state on the prints received so far -> dict or None."""
        k = self.latest_stamp(m)
        if k is None or m.thr_f is None:
            return None
        if m.bstate[0] == k:
            return m.bstate[1]
        d = self.prints.get(m.index_id, {})
        ks = sorted(s for s in d if s <= k)
        v = d[k][0]
        rel_k = k - m.close_s
        S = 0.0
        n_w = 0
        for s in ks:
            if m.close_s - 60 <= s <= m.close_s - 1:
                S += d[s][0]
                n_w += 1
        st = None
        if n_w <= 60:
            rr = 60 - n_w
            proj = (S + rr * v) / 60.0
            j1 = bisect.bisect_left(ks, k - B_VOLWIN)
            n = 0
            s1 = s2 = 0.0
            for j in range(max(j1, 1), len(ks)):
                a, b = d[ks[j - 1]][0], d[ks[j]][0]
                if a <= 0 or b <= 0:
                    continue
                x = math.log(b / a)
                n += 1
                s1 += x
                s2 += x * x
            if n >= B_MIN_RET:
                sigma = math.sqrt(max(s2 / n - (s1 / n) ** 2, 1e-14))
                w = sum((j - rel_k) ** 2 for j in range(max(rel_k + 1, -60), 0))
                if w <= 0:
                    z = 50.0 if proj >= m.thr_f else -50.0
                    st = {"p": 1.0 if proj >= m.thr_f else 0.0, "r": 0, "z": z, "sigma": sigma, "k": rel_k}
                else:
                    sd = v * sigma * math.sqrt(w) / 60.0
                    z = (proj - m.thr_f) / sd
                    st = {"p": phi(z), "r": rr, "z": max(-99.0, min(99.0, z)), "sigma": sigma, "k": rel_k}
        m.bstate = (k, st)
        return st

    def fc_state(self, m):
        """design-forecaster SettleState + Model.prob on the prints received so far -> dict or None."""
        k = self.latest_stamp(m)
        if k is None or m.thr_f is None:
            return None
        if m.fstate[0] == k:
            return m.fstate[1]
        d = self.prints.get(m.index_id, {})
        t = k - m.close_s
        v = d[k][0]
        locked = [d[s][0] for s in range(m.close_s - 60, k + 1) if s in d]
        st = None
        if not (t >= -60 and len(locked) != t + 61):
            # local sigma: consecutive-stamp 1-s log returns whose later stamp is in [t-120, t]
            acc = 0.0
            n = 0
            for s in range(k - 120, k + 1):
                if s in d and (s - 1) in d and d[s][0] > 0 and d[s - 1][0] > 0:
                    x = math.log(d[s][0] / d[s - 1][0])
                    acc += x * x
                    n += 1
            nh = sum(1 for s in d if s <= k)
            loc = math.sqrt(acc / n) if (n >= 8 and nh >= 8) else None
            p, r = self.fm.prob(m.coin, t, v, sum(locked), len(locked), loc, m.thr_f)
            if p is not None:
                st = {"p": p, "r": r, "t": t, "local_sigma": loc}
        m.fstate = (k, st)
        return st

    # --- decisions ---------------------------------------------------------------------------------------------------
    def tick(self):
        now = self.now()
        for m in list(self.markets.values()):
            if m.done:
                continue
            if now >= m.close_s:
                for strat in list(m.pending):
                    if now >= m.pending[strat]["t0"] + TAKER_SURVIVE_S:
                        self.resolve_take(m, strat, now)
                if not m.pending:
                    self.expire_orders(m, m.close_s, "close")
                    m.done = True
                continue
            while not m.done and m.next_rel <= -1:
                rel = m.next_rel
                if now < m.close_s + rel:
                    break
                stamp = m.close_s + rel
                pr = self.prints.get(m.index_id, {}).get(stamp)
                if pr is not None and pr[2] <= now:
                    self.decide(m, rel, pr, now)
                    m.next_rel += 1
                elif now > m.close_s + rel + DECIDE_DEADLINE:
                    m.c_side[rel] = None
                    m.c_latest = None
                    self.contr_update_real(m, now)
                    self.log.write("decision", ticker=m.ticker, rel=rel, wall=round(now, 3), skipped="no_print")
                    m.next_rel += 1
                else:
                    break
            if m.close_s - now <= -REL_FIRST:
                self.contr_update_real(m, now)
                for strat in list(m.pending):
                    if now >= m.pending[strat]["t0"] + TAKER_SURVIVE_S:
                        self.resolve_take(m, strat, now)
                self.evaluate_takers(m, now)

    def decide(self, m, rel, pr, now):
        v, v_str, rx = pr
        stamp = m.close_s + rel
        got, expected = self.window_state(m, stamp)
        missing = len(got) < expected
        proj = (sum(x[0] for x in got) + (60 - len(got)) * v) / 60.0
        S = None
        pc = None
        if m.thr_f is not None and not missing:
            pc = self.cm.p_yes(m.coin, rel, proj, m.thr_f)
            if pc is not None:
                if pc >= C_PMIN:
                    S = "yes"
                elif 1 - pc >= C_PMIN:
                    S = "no"
        m.c_side[rel] = S
        m.c_latest = S
        m.n_decisions += 1
        self.contr_update_real(m, now)
        bs = self.bettor_state(m)
        fs = self.fc_state(m)
        rec = {"ticker": m.ticker, "rel": rel, "wall": round(now, 3), "rx": round(rx, 3), "v": v_str,
               "proj": round(proj, 10), "missing": missing, "c_p": pc, "c_side": S}
        if bs:
            rec.update({"b_z": round(bs["z"], 3), "b_r": bs["r"],
                        "b_pcal": self.bm.lookup(bs["r"], bs["z"])})
        if fs:
            rec.update({"f_p": fs["p"], "f_r": fs["r"]})
        tr = m.tp_recv
        if tr:
            rec["last_trade_yes"] = str(tr[1])
            rec["last_trade_age"] = round(now - tr[0] / 1000.0, 3)
        rec["live_orders"] = sum(1 for o in m.orders if o.live_to is None)
        self.log.write("decision", **rec)
        self.evaluate_takers(m, now)

    # --- contrarian: opt (design) ------------------------------------------------------------------------------------
    def contr_opt_trade(self, m, ts_ms, yp, cnt, taker, trade_id):
        rel_tr = ts_ms / 1000.0 - m.close_s
        t = math.floor(rel_tr - C_LAT)
        if t < REL_FIRST or t >= 0 or t not in m.c_side:
            return
        S = m.c_side[t]
        if S != m.c_cur_opt:
            m.c_cur_opt = S
            m.c_rem_opt = {i: C_SIZE for i in range(len(C_LADDER))} if S else {}
        if S is None or taker == S:
            return
        lp = m.tp_last
        if lp is None:
            return
        age = (ts_ms - lp[0]) / 1000.0
        if age > C_CONF_AGE or age < C_LAT:
            return
        last_S = lp[1] if S == "yes" else Decimal(1) - lp[1]
        if float(last_S) < C_CONFIRM - 1e-9:
            return
        pS = yp if S == "yes" else Decimal(1) - yp
        left = cnt
        for i, lv in enumerate(C_LADDER):
            if left <= 0:
                break
            if pS > lv:
                continue
            f = min(m.c_rem_opt.get(i, Decimal(0)), left)
            if f <= 0:
                continue
            m.c_rem_opt[i] -= f
            left -= f
            self.add_fill(m, {"strat": "contrarian", "ticker": m.ticker, "kind": "rest", "model": "opt", "level": i,
                              "side": S, "my_price": str(lv), "size_opt": str(f), "size_real": "0", "fee_opt": "0",
                              "fee_real": "0", "trade_id": trade_id, "ts_ms": ts_ms, "print_price": str(pS),
                              "print_size": str(cnt), "confirm_yes": str(lp[1]), "confirm_age": round(age, 3)})

    # --- contrarian: real (refuters) ---------------------------------------------------------------------------------
    def contr_real_trade(self, m, ts_ms, yp, cnt, taker, trade_id):
        ts = ts_ms / 1000.0
        X = "yes" if taker == "no" else "no"
        pX = yp if X == "yes" else Decimal(1) - yp
        left = cnt
        live = [o for o in m.orders if o.side == X and o.live_from <= ts and (o.live_to is None or ts < o.live_to)]
        live.sort(key=lambda o: -o.price)
        for o in live:
            if left <= 0:
                break
            if pX > o.price:
                continue
            rem = m.c_rem_real.get(o.level, Decimal(0)) if o.side == m.c_ep_side else Decimal(0)
            at_price = pX == o.price
            if at_price:
                eat = min(left, o.ahead)
                o.ahead -= eat
                left -= eat
            f = min(rem, left)
            if f <= 0:
                continue
            m.c_rem_real[o.level] = rem - f
            left -= f
            self.add_fill(m, {"strat": "contrarian", "ticker": m.ticker, "kind": "rest", "model": "real",
                              "level": o.level, "order_id": o.id, "side": X, "my_price": str(o.price),
                              "size_opt": "0", "size_real": str(f), "fee_opt": "0", "fee_real": "0",
                              "trade_id": trade_id, "ts_ms": ts_ms, "print_price": str(pX), "print_size": str(cnt),
                              "at_price": at_price, "ahead_left": str(o.ahead),
                              "cancel_pending": o.live_to is not None})

    def contr_update_real(self, m, now):
        if m.done or now >= m.close_s:
            return
        S = m.c_latest
        tr = m.tp_recv
        want = None
        if S is not None and tr is not None and now - tr[0] / 1000.0 <= C_CONF_AGE:
            s_price = tr[1] if S == "yes" else Decimal(1) - tr[1]
            if float(s_price) >= C_CONFIRM - 1e-9:
                want = S
        if S is not None and S != m.c_ep_side:
            m.c_ep_side = S
            m.c_rem_real = {i: C_SIZE for i in range(len(C_LADDER))}
        for o in m.orders:
            if o.live_to is None and o.side != want:
                o.live_to = now + REAL_CANCEL_LAT
                self.counts["cancels"] += 1
                self.log.write("cancel", strat="contrarian", ticker=m.ticker, order_id=o.id, level=o.level,
                               side=o.side, price=str(o.price), live_from=round(o.live_from, 3),
                               live_to=round(o.live_to, 3), why="no_lock" if S is None else
                               ("side_flip" if o.side != S else "market_disagrees"))
        if want is None or any(o.live_to is None and o.side == want for o in m.orders):
            return
        b = self.books.get(m.ticker)
        for i, lv in enumerate(C_LADDER):
            if m.c_rem_real.get(i, Decimal(0)) <= 0:
                continue
            ahead = Decimal(0)
            if b is not None and b.synced:
                ahead = (b.yes if want == "yes" else b.no).get(lv, Decimal(0))
            o = Order(m.ticker, want, i, lv, now + REAL_PLACE_LAT, ahead)
            m.orders.append(o)
            m.n_orders += 1
            self.counts["orders"] += 1
            self.log.write("order", strat="contrarian", ticker=m.ticker, order_id=o.id, level=i, side=want,
                           price=str(lv), size=str(m.c_rem_real[i]), live_from=round(o.live_from, 3),
                           ahead=str(ahead), book_synced=bool(b and b.synced),
                           confirm_yes=str(tr[1]), confirm_age=round(now - tr[0] / 1000.0, 3))

    def expire_orders(self, m, t, why):
        for o in m.orders:
            if o.live_to is None or o.live_to > t:
                o.live_to = t

    # --- takers (bettor, forecaster) ---------------------------------------------------------------------------------
    def avail(self, m, strat, side, q, size):
        key = (strat, side, q)
        c = m.consumed.get(key)
        if c is not None and c > size:
            m.consumed[key] = size
            c = size
        return size - (c or Decimal(0))

    def evaluate_takers(self, m, now):
        rel_now = now - m.close_s
        if rel_now >= 0 or rel_now < REL_FIRST:
            return
        b = self.books.get(m.ticker)
        if b is None or not b.synced:
            return
        if m.consumed:
            present = {"yes": {q for q, _ in b.asks("yes")}, "no": {q for q, _ in b.asks("no")}}
            for key in [k for k in m.consumed if k[2] not in present[k[1]]]:
                del m.consumed[key]
        if "bettor" not in m.pending:
            self.eval_bettor(m, b, now)
        if "forecaster" not in m.pending:
            self.eval_forecaster(m, b, now)

    def eval_bettor(self, m, b, now):
        st = self.bettor_state(m)
        if st is None or st["r"] > B_MAX_R or abs(st["z"]) < B_MIN_Z:
            return
        side = "yes" if st["z"] >= 0 else "no"
        pc = self.bm.lookup(st["r"], st["z"])
        if pc is None:
            return
        B = self.bank["real"]
        if B <= 0:
            return
        have = m.tcost["bettor"]
        cs = self.close_tot["bettor"].get(m.close_s, 0.0)
        legs = []
        for q, size in b.asks(side):
            qf = float(q)
            if qf > B_MAX_PRICE + 1e-9:
                break
            if qf < B_MIN_PRICE - 1e-9:
                continue
            c = qf + fee_f(qf)
            if pc - c < B_THR:
                break
            a = self.avail(m, "bettor", side, q, size)
            if a <= 0:
                continue
            fstar = (pc - c) / (1 - c) if c < 1 else 0.0
            target = min(B_KELLY * fstar, B_MKT_CAP) * B
            room = min(target - have, B_CLOSE_CAP * B - cs)
            if room <= 0.005:
                continue
            k = int(min(float(a), room / qf))
            if k < 1:
                continue
            legs.append((q, Decimal(k)))
            have += k * qf
            cs += k * qf
        if legs:
            self.new_take(m, "bettor", side, legs, now, {"z": round(st["z"], 3), "r": st["r"], "p_cal": pc,
                                                          "bank_real": round(B, 2)})

    def eval_forecaster(self, m, b, now):
        st = self.fc_state(m)
        if st is None:
            return
        rel_u = math.floor(now - F_LAG) - m.close_s
        if st["t"] < rel_u - 2 or not (0 <= st["r"] <= F_R_MAX):
            return
        cl = self.close_tot["forecaster"].get(m.close_s, 0)
        for side in ("yes", "no"):
            ps = st["p"] if side == "yes" else 1.0 - st["p"]
            room_side = F_MAX_SIDE - m.tn["forecaster"][side]
            legs = []
            for q, size in b.asks(side):
                qf = float(q)
                if qf > F_MAX_PRICE + 1e-9:
                    break
                if qf < F_MIN_PRICE - 1e-9 or qf >= 1.0:
                    continue
                if ps - qf - fee_f(qf) < F_MIN_EDGE:
                    break
                a = self.avail(m, "forecaster", side, q, size)
                if a <= 0:
                    continue
                k = int(min(float(a), room_side, F_MAX_CLOSE - cl))
                if k < 1:
                    break
                legs.append((q, Decimal(k)))
                room_side -= k
                cl += k
            if legs:
                self.new_take(m, "forecaster", side, legs, now, {"p": st["p"], "r": st["r"], "t_print": st["t"]})
                return

    def new_take(self, m, strat, side, legs, now, why):
        self.take_n += 1
        k = sum(x[1] for x in legs)
        cost = sum(float(q) * float(n) for q, n in legs)
        tk = {"id": self.take_n, "strat": strat, "side": side, "legs": legs, "k": k, "qmax": max(q for q, _ in legs),
              "t0": now, "min_surv": k, "unsynced": False, "cost": cost}
        m.pending[strat] = tk
        for q, n in legs:
            key = (strat, side, q)
            m.consumed[key] = m.consumed.get(key, Decimal(0)) + n
        m.tcost[strat] += cost
        m.tn[strat][side] += int(k)
        ct = self.close_tot[strat]
        ct[m.close_s] = ct.get(m.close_s, 0) + (cost if strat == "bettor" else int(k))
        self.counts["takes"] += 1
        self.track_pending(m, now)
        self.log.write("take", strat=strat, ticker=m.ticker, take_id=tk["id"], side=side, rel=round(now - m.close_s, 3),
                       legs=[[str(q), str(n)] for q, n in legs], contracts=str(k), cost=round(cost, 2), **why)

    def surv_of(self, m, strat, tk, b):
        """Contracts still offered at <= the take's limit, net of what this strategy already assumed it took."""
        own = {q: n for q, n in tk["legs"]}
        surv = Decimal(0)
        for q, size in b.asks(tk["side"]):
            if q > tk["qmax"]:
                break
            c = m.consumed.get((strat, tk["side"], q), Decimal(0)) - own.get(q, Decimal(0))
            surv += max(Decimal(0), size - max(Decimal(0), c))
        return surv

    def track_pending(self, m, now):
        if not m.pending or now >= m.close_s:
            return
        b = self.books.get(m.ticker)
        for strat, tk in m.pending.items():
            if now > tk["t0"] + TAKER_SURVIVE_S:
                continue
            if b is None or not b.synced:
                tk["unsynced"] = True
                tk["min_surv"] = Decimal(0)
                tk["last_surv"] = Decimal(0)
                continue
            surv = self.surv_of(m, strat, tk, b)
            tk["last_surv"] = surv
            if surv < tk["min_surv"]:
                tk["min_surv"] = surv

    def resolve_take(self, m, strat, now):
        """real = what is still displayed 1 s after the decision (the refuters' rule); the stricter 'never dipped
        below' count (minimum displayed at any instant in that second) is logged next to it as contracts_strict."""
        tk = m.pending.pop(strat)
        b = self.books.get(m.ticker)
        if now < m.close_s and b is not None and b.synced and not tk["unsynced"]:
            s1 = self.surv_of(m, strat, tk, b)
            s1_src = "book_at_resolve"
        else:
            s1 = tk.get("last_surv", Decimal(0))
            s1_src = "last_seen_before_close" if not tk["unsynced"] else "unsynced"
        real_left = min(tk["k"], s1)
        tot_real = real_left
        cost_real = 0.0
        for q, n in tk["legs"]:
            r = min(n, real_left)
            real_left -= r
            cost_real += float(q) * float(r)
            self.add_fill(m, {"strat": strat, "ticker": m.ticker, "kind": "take", "model": "both",
                              "take_id": tk["id"], "side": tk["side"], "my_price": str(q), "size_opt": str(n),
                              "size_real": str(r), "fee_opt": str(taker_fee(n, q)), "fee_real": str(taker_fee(r, q))})
        # sizing follows the realistic world: give back what did not fill
        m.tcost[strat] -= tk["cost"] - cost_real
        m.tn[strat][tk["side"]] -= int(tk["k"] - tot_real)
        ct = self.close_tot[strat]
        ct[m.close_s] = ct.get(m.close_s, 0) - ((tk["cost"] - cost_real) if strat == "bettor" else int(tk["k"] - tot_real))
        if tot_real <= 0:
            self.counts["take_real_zero"] += 1
        self.log.write("take_result", strat=strat, ticker=m.ticker, take_id=tk["id"], side=tk["side"],
                       contracts_opt=str(tk["k"]), contracts_real=str(tot_real),
                       contracts_strict=str(min(tk["k"], tk["min_surv"])), surv_src=s1_src,
                       unsynced=tk["unsynced"], resolved_rel=round(now - m.close_s, 3))

    def add_fill(self, m, fill):
        m.fills.append(fill)
        if Decimal(fill["size_opt"]) > 0:
            self.counts["fills_opt"] += 1
        if Decimal(fill["size_real"]) > 0:
            self.counts["fills_real"] += 1
        self.log.write("fill", **fill)

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
        em = self.exact_mean(m)
        my_settle = my_pred = None
        if em is not None:
            my_settle = em.quantize(Decimal(1).scaleb(-m.rd), rounding=ROUND_HALF_UP)
            my_pred = "yes" if (m.strike is not None and my_settle >= m.strike) else "no"
        pnl = {s: {} for s in STRATS}
        ctr = {s: {} for s in STRATS}
        risk = {s: {} for s in STRATS}
        for s in STRATS:
            for model in FILLM:
                tot = n = fee = rk = Decimal(0)
                for f in m.fills:
                    if f["strat"] != s:
                        continue
                    sz = Decimal(f["size_" + model])
                    if sz <= 0:
                        continue
                    px = Decimal(f["my_price"])
                    tot += sz * (Decimal(1) - px) if f["side"] == result else -sz * px
                    n += sz
                    rk += sz * px
                    fee += Decimal(f["fee_" + model])
                pnl[s][model] = (tot - fee).quantize(Decimal("0.0001"))
                ctr[s][model] = n
                risk[s][model] = rk
                self.cum[s][model] += pnl[s][model]
        for model in FILLM:
            self.bank[model] += float(pnl["bettor"][model])
        m.pnl, m.ctr, m.risk = pnl, ctr, risk
        self.log.write("settle", ticker=ticker, coin=m.coin, close_s=m.close_s, result=result,
                       expiration_value=expiration_value, my_settle=str(my_settle) if my_settle is not None else None,
                       my_pred=my_pred, pred_match=(my_pred == result) if my_pred else None, strike=str(m.strike),
                       strike_src=m.strike_src, n_fills=len(m.fills), n_decisions=m.n_decisions, n_orders=m.n_orders,
                       pnl={s: {k: str(v) for k, v in pnl[s].items()} for s in STRATS},
                       contracts={s: {k: str(v) for k, v in ctr[s].items()} for s in STRATS})
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
        per = {}
        tot = {"opt": Decimal(0), "real": Decimal(0)}
        for s in STRATS:
            e = {}
            for model in FILLM:
                p = sum((getattr(x, "pnl", {}).get(s, {}).get(model, Decimal(0)) for x in ms), Decimal(0))
                n = sum((getattr(x, "ctr", {}).get(s, {}).get(model, Decimal(0)) for x in ms), Decimal(0))
                rk = sum((getattr(x, "risk", {}).get(s, {}).get(model, Decimal(0)) for x in ms), Decimal(0))
                lose = sum(1 for x in ms if getattr(x, "pnl", {}).get(s, {}).get(model, Decimal(0)) < 0)
                e[model] = {"pnl": str(p), "contracts": str(n), "at_risk": str(rk.quantize(Decimal("0.01"))),
                            "losing_markets": lose, "cum": str(self.cum[s][model])}
                tot[model] += p
            e["coins"] = sorted({x.coin for x in ms if any(f["strat"] == s for f in x.fills)})
            per[s] = e
        self.log.write("close_summary", close_s=m.close_s, close=now_iso(m.close_s), markets=len(ms),
                       pnl_opt=str(tot["opt"]), pnl_real=str(tot["real"]), strats=per,
                       bettor_bank={k: round(v, 2) for k, v in self.bank.items()})
        for s in ("bettor", "forecaster"):
            self.close_tot[s].pop(m.close_s, None)
        for x in ms:
            self.finished.add(x.ticker)
            self.markets.pop(x.ticker, None)
            self.books.pop(x.ticker, None)
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
def load_params():
    with open(PARAMS_PATH, encoding="utf-8") as f:
        return json.load(f)


def run_live(minutes):
    sys.path.insert(0, r"C:\kals-repo\research")
    import kauth  # request-signing helpers only (GET)
    log = Logger(LOG_PATH)
    q = queue.Queue()
    eng = Engine(log, time.time, load_params())
    ws = WS(q, log, kauth.headers)
    ws.index_ids = [COINS[c][1] for c in COINS]
    rest = Rest(q, log, kauth.get)
    log.write("start", pid=os.getpid(), minutes=minutes, python=sys.version.split()[0], rss_mb=rss_mb(),
              log=LOG_PATH, coins=list(COINS), strats=list(STRATS), params=PARAMS_PATH,
              rule_version="v2: taker real = displayed 1 s after the decision; strict (never dipped) logged beside it")
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
            try:
                if t == "cfbenchmarks_value":
                    msg = obj["msg"]
                    data = json.loads(msg["data"])
                    eng.on_print(msg["index_id"], int(data["time"]), data["value"], rx)
                    print_rate[msg["index_id"]] = print_rate.get(msg["index_id"], 0) + 1
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
                    eng.on_trade(obj["msg"]["market_ticker"], obj["msg"], rx)
                elif t == "market_lifecycle_v2":
                    msg = obj["msg"]
                    if msg.get("market_ticker") in eng.markets and msg.get("event_type") in ("determined",):
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
            except Exception as e:
                log.write("handler_error", type=t, err=repr(e)[:300])
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
                      queue=q.qsize(), counts=eng.counts,
                      cum={s: {k: str(v) for k, v in eng.cum[s].items()} for s in STRATS},
                      bettor_bank={k: round(v, 2) for k, v in eng.bank.items()})
            print_rate = {}
            n_msgs = {}
            last_health = now
        time.sleep(0.02)
    ws.stop = True
    rest.stop = True
    log.write("stop", reason="minutes_elapsed")


# ---------------------------------------------------------------------------------------------------------- self-test
def selftest():
    """Planted worlds with known fills and money for each strategy and fill model, plus empty worlds."""
    out = []

    def check(cond, what):
        if not cond:
            raise AssertionError("SELFTEST FAIL: " + what)
        out.append(what)

    P = load_params()
    # model pieces --------------------------------------------------------------------------------------------------
    toy = ContrModel({"sd": {"BTC|-30": 1e-4}, "quant": {"-30": [-4 + 8 * i / 2000 for i in range(2001)]}, "nq": 2001})
    check(toy.p_yes("BTC", -30, 100.0, 99.9) == 1.0 and toy.p_yes("BTC", -30, 100.0, 100.1) == 0.0,
          "contrarian model: far above -> P(YES)=1, far below -> 0")
    check(abs(toy.p_yes("BTC", -30, 100.0, 100.0) - (1 - 1000 / 2001)) < 1e-12, "contrarian model: at the strike -> ~0.5")
    check(toy.p_yes("ETH", -30, 100.0, 99.9) is None, "contrarian model: unknown coin -> no decision")
    check(s_coef(-1) == 0 and s_coef(-2) == 1 and s_coef(-3) == 5 and s_coef(-61) == 73810, "forecaster S(t)")
    check(b_rkey(0) == "0-0" and b_rkey(45) == "31-59" and b_zkey(-4.2) == "4-5" and b_zkey(50) == "30-1e+09",
          "bettor bins")
    check(abs(FcModel._map(0.95, [(0.55, 0.55), (0.95, 0.90)]) - 0.90) < 1e-12, "forecaster calibration map")
    check(taker_fee(Decimal(20), Decimal("0.90")) == Decimal("0.13"), "taker fee rounds up to the cent")
    check(len(P["contrarian"]["sd"]) >= 9 * 60 and P["contrarian"]["nq"] == 2001, "contrarian TRAIN model loaded")

    # planted world -------------------------------------------------------------------------------------------------
    clock = [0.0]
    sink = []
    eng = Engine(Logger(None, sink), lambda: clock[0], P)
    C = 1_000_000
    eng.add_market("BTC-T", "BTC", C, Decimal("100.00"), 2, "planted")    # certain YES
    eng.add_market("ETH-T", "ETH", C, Decimal("100.00"), 2, "planted")    # certain NO, no book
    for s in range(C - 240, C + 1):
        eng.on_print("BRTI", s * 1000, "101.00" if s % 2 else "101.01", s + 0.1)
        eng.on_print("ETHUSD_RTI", s * 1000, "99.00" if s % 2 else "99.01", s + 0.1)
    # BTC book: YES bid 10 @0.80 (queue ahead of my 0.80 rung); NO bid 20 @0.10 = a YES offer 20 @0.90
    eng.on_snapshot("BTC-T", {"yes_dollars_fp": [["0.8000", "10.00"]], "no_dollars_fp": [["0.1000", "20.00"]]}, 1)
    check(eng.books["BTC-T"].asks("yes") == [(Decimal("0.9000"), Decimal("20.00"))], "YES offer = 1 - NO bid")
    clock[0] = C - 60 + 0.2
    eng.tick()
    d60 = [r for r in sink if r["ev"] == "decision" and r["rel"] == -60]
    check(len(d60) == 2, "both markets decided at rel -60")
    check([r for r in d60 if r["ticker"] == "BTC-T"][0]["c_side"] == "yes"
          and [r for r in d60 if r["ticker"] == "ETH-T"][0]["c_side"] == "no", "contrarian locked sides YES / NO")
    tk = [r for r in sink if r["ev"] == "take"]
    check(len(tk) == 1 and tk[0]["strat"] == "bettor" and tk[0]["legs"] == [["0.9000", "20"]],
          "bettor takes the displayed 20 @0.90 (stake cap $100 not binding)")
    check(not [r for r in sink if r["ev"] == "order"], "contrarian: locked but the market has not agreed -> no bids")
    clock[0] = C - 59.5                                                   # the offer vanishes half a second later
    eng.on_delta("BTC-T", {"side": "no", "price_dollars": "0.1000", "delta_fp": "-20.00"}, 2)
    clock[0] = C - 59 + 0.3
    eng.tick()
    tr = [r for r in sink if r["ev"] == "take_result"]
    check(len(tr) == 1 and tr[0]["contracts_opt"] == "20" and tr[0]["contracts_real"] == "0",
          "taker: gone within 1 s -> realistic 0, same-second 20")
    clock[0] = C - 50
    eng.on_delta("BTC-T", {"side": "no", "price_dollars": "0.0500", "delta_fp": "30.00"}, 3)   # YES offer 30 @0.95
    clock[0] = C - 50 + 0.2
    eng.tick()
    tk = [r for r in sink if r["ev"] == "take"]
    check(len(tk) == 2 and tk[1]["legs"] == [["0.9500", "30"]] and tk[1]["strat"] == "bettor", "bettor takes 30 @0.95")
    for rel in range(-49, -40):
        clock[0] = C + rel + 0.25
        eng.tick()
    tr = [r for r in sink if r["ev"] == "take_result"]
    check(len(tr) == 2 and tr[1]["contracts_real"] == "30", "taker: still displayed after 1 s -> realistic 30")
    check(len([r for r in sink if r["ev"] == "take"]) == 2, "an offer already taken is not taken twice")
    # contrarian: the market confirms (YES printed 0.98), then two dumps 0.2 s apart
    clock[0] = C - 39.95
    eng.on_trade("BTC-T", {"ts_ms": (C - 40) * 1000, "yes_price_dollars": "0.9800", "count_fp": "5.00",
                           "taker_side": "yes", "trade_id": "c"}, C - 39.95)
    od = [r for r in sink if r["ev"] == "order"]
    check([r["price"] for r in od] == ["0.95", "0.90", "0.80"] and all(r["side"] == "yes" for r in od),
          "contrarian: market agrees -> YES bids 0.95/0.90/0.80")
    check(od[2]["ahead"] == "10.00" and abs(od[0]["live_from"] - (C - 39.65)) < 1e-6, "queue ahead recorded, live 0.3 s later")
    clock[0] = C - 39.8
    eng.tick()                                                            # decides rel -40
    clock[0] = C - 39.45
    eng.on_trade("BTC-T", {"ts_ms": (C - 40) * 1000 + 500, "yes_price_dollars": "0.8500", "count_fp": "30.00",
                           "taker_side": "no", "trade_id": "d1"}, C - 39.45)
    cx = [r for r in sink if r["ev"] == "cancel"]
    check(len(cx) == 3 and all(abs(r["live_to"] - (C - 39.15)) < 1e-6 for r in cx),
          "dump print -> market no longer agrees -> cancel, effective 0.3 s later")
    clock[0] = C - 39.25
    eng.on_trade("BTC-T", {"ts_ms": (C - 40) * 1000 + 700, "yes_price_dollars": "0.8000", "count_fp": "100.00",
                           "taker_side": "no", "trade_id": "d2"}, C - 39.25)
    cf = [r for r in sink if r["ev"] == "fill" and r["strat"] == "contrarian"]
    opt = [(r["my_price"], r["size_opt"]) for r in cf if r["model"] == "opt"]
    real = [(r["my_price"], r["size_real"]) for r in cf if r["model"] == "real"]
    check(opt == [("0.95", "30.00")], "opt (design): first dump fills 30 @0.95; second not confirmed (last print 0.85)")
    check(real == [("0.95", "30.00"), ("0.95", "20.00"), ("0.90", "50.00"), ("0.80", "20.00")],
          "real: cancel still in flight -> second dump fills all rungs; 0.80 rung waits behind 10 ahead")
    # a trade before an order is live does not fill (fresh engine)
    s2 = []
    e2 = Engine(Logger(None, s2), lambda: clock[0], P)
    m2 = e2.add_market("X-T", "BTC", C, Decimal("100.00"), 2, "planted")
    m2.c_latest = "yes"
    m2.c_side[-40] = "yes"
    e2.on_trade("X-T", {"ts_ms": (C - 40) * 1000, "yes_price_dollars": "0.9800", "count_fp": "5.00",
                        "taker_side": "yes"}, C - 39.95)
    e2.on_trade("X-T", {"ts_ms": (C - 40) * 1000 + 150, "yes_price_dollars": "0.5000", "count_fp": "99.00",
                        "taker_side": "no"}, C - 39.8)
    check(not [r for r in s2 if r["ev"] == "fill" and r["model"] == "real"], "real: no fill before the order is live")
    # a flicker: the offer vanishes for an instant and is back before 1 s -> real counts it, strict does not
    s4 = []
    clock4 = [C - 60 + 0.2]
    e4 = Engine(Logger(None, s4), lambda: clock4[0], P)
    e4.add_market("F-T", "BTC", C, Decimal("100.00"), 2, "planted")
    for s in range(C - 240, C + 1):
        e4.on_print("BRTI", s * 1000, "101.00" if s % 2 else "101.01", s + 0.1)
    e4.on_snapshot("F-T", {"no_dollars_fp": [["0.1000", "20.00"]]}, 1)
    e4.tick()
    clock4[0] = C - 59.5
    e4.on_delta("F-T", {"side": "no", "price_dollars": "0.1000", "delta_fp": "-20.00"}, 2)
    e4.on_delta("F-T", {"side": "no", "price_dollars": "0.1000", "delta_fp": "20.00"}, 3)
    clock4[0] = C - 59 + 0.3
    e4.tick()
    t4 = [r for r in s4 if r["ev"] == "take_result"]
    check(len(t4) == 1 and t4[0]["contracts_real"] == "20" and t4[0]["contracts_strict"] == "0",
          "taker flicker: back within 1 s -> realistic 20, strict 0")
    # walk to the close: the forecaster buys the YES offer at r = 30
    for rel in range(-39, 0):
        clock[0] = C + rel + 0.25
        eng.tick()
    fk = [r for r in sink if r["ev"] == "take" and r["strat"] == "forecaster"]
    check(len(fk) == 1 and fk[0]["legs"] == [["0.9500", "30"]] and fk[0]["r"] == 30,
          "forecaster buys 30 @0.95 once 30 prints remain (its own allowance, separate from the bettor's)")
    check(not [r for r in sink if r["ev"] == "take" and r["strat"] == "forecaster" and r["r"] > 30],
          "forecaster never trades with more than 30 prints to come")
    n_dec = len([r for r in sink if r["ev"] == "decision" and r["ticker"] == "BTC-T"])
    check(n_dec == 60, "60 decision seconds per market")
    clock[0] = C + 1.5
    eng.tick()
    clock[0] = C + 5
    check(len(eng.markets_needing_result(clock[0])) == 2, "both markets ask for a result after the close")
    eng.on_result("BTC-T", "yes", "101.01", clock[0])
    eng.on_result("ETH-T", "no", "99.01", clock[0])
    st = {r["ticker"]: r for r in sink if r["ev"] == "settle"}
    pb = st["BTC-T"]["pnl"]
    check(pb["contrarian"] == {"opt": "1.5000", "real": "11.5000"}, "contrarian money: opt 30x5c, real 50x5c+50x10c+20x20c")
    check(pb["bettor"] == {"opt": "3.2700", "real": "1.4000"}, "bettor money: opt 20x10c-13c + 30x5c-10c, real 30x5c-10c")
    check(pb["forecaster"] == {"opt": "1.4000", "real": "1.4000"}, "forecaster money 30x5c-10c fee")
    check(st["BTC-T"]["my_settle"] == "101.01" and st["BTC-T"]["pred_match"] is True, "settlement mean rounded half-up")
    cs = [r for r in sink if r["ev"] == "close_summary"]
    check(len(cs) == 1 and cs[0]["pnl_opt"] == "6.1700" and cs[0]["pnl_real"] == "14.3000",
          "close summary: both fill models summed over strategies")
    check(abs(eng.bank["real"] - 1001.40) < 1e-9, "bettor bank compounds on realistic money")
    check(not eng.markets, "settled markets released")
    # losing side
    e3 = Engine(Logger(None, []), lambda: 0, P)
    m3 = e3.add_market("L-T", "BTC", 10, Decimal("1"), 2, "planted")
    m3.fills.append({"strat": "contrarian", "side": "yes", "my_price": "0.95", "size_opt": "50", "size_real": "20",
                     "fee_opt": "0", "fee_real": "0"})
    m3.done = True
    e3.on_result("L-T", "no", "0", 20)
    check(e3.cum["contrarian"]["opt"] == Decimal("-47.5") and e3.cum["contrarian"]["real"] == Decimal("-19"),
          "a losing fill costs the price paid")
    # empty worlds
    sE = []
    clock[0] = C - 100
    eE = Engine(Logger(None, sE), lambda: clock[0], P)
    eE.add_market("E-T", "BTC", C, Decimal("100.00"), 2, "planted")
    for rel in range(-60, 1):
        clock[0] = C + rel + 0.95
        eE.tick()
    check(not [r for r in sE if r["ev"] in ("order", "fill", "take")], "empty world (no prints): nothing placed")
    eE2 = Engine(Logger(None, sE), lambda: clock[0], P)
    for s in range(C - 240, C + 1):
        eE2.on_print("BRTI", s * 1000, "101.00", s + 0.1)
    eE2.tick()
    eE2.on_trade("E-T", {"ts_ms": C * 1000, "yes_price_dollars": "0.5000", "count_fp": "1.00", "taker_side": "no"}, C)
    check(not [r for r in sE if r["ev"] in ("order", "fill", "take")], "empty world (no market): nothing placed")
    # no code path can send an order
    src = open(__file__, encoding="utf-8").read()
    check(src.count("portfolio/" + "orders") == 0 and src.count("/port" + "folio") == 0, "no order endpoint in source")
    check(src.count("url" + "open") == 0 and src.count("PO" + "ST") == 0 and src.count("Req" + "uest(") == 0
          and src.count("DEL" + "ETE") == 0 and src.count("PU" + "T ") == 0 and src.count("create_" + "order") == 0,
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
