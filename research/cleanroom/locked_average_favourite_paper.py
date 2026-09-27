#!/usr/bin/env python
"""Clean-room PAPER bot: "Locked-average favourite" ladder.

Built from the public market rules and the recorded tape only (2026-09-27, clean room).
NO ORDER IS EVER SENT.  There is no code path that POSTs anything: the only network
calls are a WebSocket subscribe for market data and public GETs of market metadata.

Design (rule as specified by the selector, not refit here)
----------------------------------------------------------
Each KX<COIN>15M market settles YES iff round_half_up(mean of the 60 CF Benchmarks
prints stamped close-60 .. close-1, round_digits) >= strike.  With rel = -30 .. -1
seconds to the close, the prints stamped close-60 .. close+rel are already fixed
("locked"); k = (-rel) - 1 prints are still to come.  Model:
    proj = (locked_sum + k * v) / 60                (index stays where it is)
    sd   = v * sigma * sqrt(k(k+1)(2k+1)/6) / 60    (sigma = RMS 1-s log return)
    p    = Phi((proj - thr) / sd),  thr = K - 0.5 * 10^-round_digits
Lead floor: |proj - thr| / v >= 0.25 * MAXERR(rel) (TRAIN maxima of the projection
error, interpolated).  If p >= 0.999 rest YES bids at p-0.02, p-0.05, p-0.15 (tick
rounded down), 100 contracts each; if p <= 0.001 the same on the NO side with 1-p.
Otherwise no orders.  Decisions are taken at wall time close+rel+0.2 s once the print
stamped close+rel has been RECEIVED (usable time = receive time on this box); if it
has not arrived by +0.9 s the second is skipped and all orders cancelled.

Fill models (paper), both logged on every fill
----------------------------------------------
Resting bid at price q on side S:
  opt : a trade whose taker SOLD my side (taker_side == other side) at a price <= q,
        printed at or after my order's live_from, fills me up to the trade's size
        (my orders are consumed best-price-first across the trade's size).
  pess: same trades, but a trade AT my price first has to eat the size that was
        displayed at my price on my side when I placed the order (queue ahead of me);
        a trade strictly below my price fills me in full (I would have been the best bid).
If my bid crosses the displayed ask at placement, both models take the displayed size
at the ask (a taker fill, taker fee 0.07 * n * P * (1-P) rounded up to the cent).
Maker fills pay no fee when the series' fee_type is "quadratic" (read from
GET /series/<S> at startup); if a series reports "quadratic_with_maker_fees" the maker
fee is taken as 0.0175 * n * P * (1-P) and the heartbeat says so.
Counterparty: whoever sells the (nearly) settled side at 85-98c in the last 30 s --
a holder of the losing side salvaging, or a market order that walks the book.  They
trade with me because my bid is the best displayed price at that moment.

Log: one JSON line per decision, order, fill, settle, close-summary and 60-s heartbeat
in C:/kals-repo/results/cleanroom-locked_average_favourite.jsonl (UTC).
Run:  python locked_average_favourite_paper.py --minutes 10080   (self-test runs first)
      python locked_average_favourite_paper.py --selftest          (self-test only)
"""
import argparse
import base64
import collections
import ctypes
import gzip
import json
import math
import os
import queue
import random
import select
import socket
import ssl
import struct
import sys
import threading
import time
import traceback
import urllib.request
import urllib.error

NAME = "locked_average_favourite"
REPO = r"C:\kals-repo"
LOG_PATH = os.path.join(REPO, "results", "cleanroom-%s.jsonl" % NAME)
REST_BASE = "https://api.elections.kalshi.com/trade-api/v2"
WS_HOSTS = ["api.elections.kalshi.com", "external-api-ws.kalshi.com"]
WS_PATH = "/trade-api/ws/v2"

COINS = {  # series -> index id, round digits
    "KXBTC15M": ("BRTI", 2), "KXETH15M": ("ETHUSD_RTI", 2), "KXBNB15M": ("BNBUSD_RTI", 2),
    "KXSOL15M": ("SOLUSD_RTI", 4), "KXXRP15M": ("XRPUSD_RTI", 4), "KXHYPE15M": ("HYPEUSD_RTI", 4),
    "KXZEC15M": ("ZECUSD_RTI", 4), "KXNEAR15M": ("NEARUSD_RTI", 4), "KXDOGE15M": ("DOGEUSD_RTI", 7),
}
INDEX_IDS = sorted({v[0] for v in COINS.values()})

# TRAIN maxima of |proj - settle| / v by rel (given; not refit)
MAXERR = [(-30, 84.8e-4), (-20, 21.5e-4), (-15, 13.6e-4), (-10, 6.2e-4), (-7, 3.5e-4),
          (-5, 2.3e-4), (-3, 1.0e-4), (-2, 0.5e-4), (-1, 0.0)]
FLOOR_FRAC = 0.25
P_HI = 0.999
LEVELS = [0.02, 0.05, 0.15]
LEVEL_SIZE = 100.0
REL_FIRST, REL_LAST = -30, -1
DECIDE_OFFSET = 0.2
DECIDE_DEADLINE = 0.9
FEED_STALE_S = 2.0
SIGMA_N = 180
KEEP_PRINTS_S = 240
TAKER_FEE = 0.07
MAKER_FEE_WITH = 0.0175


def maxerr(rel):
    if rel <= MAXERR[0][0]:
        return MAXERR[0][1]
    for (r0, e0), (r1, e1) in zip(MAXERR, MAXERR[1:]):
        if r0 <= rel <= r1:
            return e0 + (e1 - e0) * (rel - r0) / (r1 - r0)
    return MAXERR[-1][1]


def phi(z):
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def tick_down_m(x):
    """Round a price in dollars DOWN to the tapered tick; returns integer thousandths."""
    m = int(math.floor(x * 1000.0 + 1e-9))
    if 100 <= m <= 900:
        m -= m % 10
    return max(m, 1)


def fee_dollars(rate, n, price):
    """Kalshi quadratic fee: rate * n * P * (1-P), rounded UP to the cent."""
    if rate <= 0 or n <= 0:
        return 0.0
    return math.ceil(rate * n * price * (1.0 - price) * 100.0 - 1e-9) / 100.0


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
        h = ctypes.c_void_p(k32.GetCurrentProcess())
        if not k32.K32GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
            return -1.0
        return round(pmc.WorkingSetSize / 1048576.0, 1)
    except Exception:
        return -1.0


def iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ts)) + ("%.3fZ" % (ts % 1))[1:]


def parse_iso(s):
    # "2026-09-27T13:30:00Z"
    t = time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    import calendar
    return calendar.timegm(t)


# ----------------------------------------------------------------------------- engine
class Book:
    __slots__ = ("yes", "no", "synced", "seq", "last_ts_ms")

    def __init__(self):
        self.yes = {}   # price_m -> size (YES bids)
        self.no = {}    # price_m -> size (NO bids)
        self.synced = False
        self.seq = None
        self.last_ts_ms = 0

    def best(self, side):
        d = self.yes if side == "yes" else self.no
        if not d:
            return None, 0.0
        p = max(d)
        return p, d[p]

    def best_ask_m(self, side):
        """Best ask on `side` = 1 - best bid on the other side. Returns (price_m, size)."""
        p, sz = self.best("no" if side == "yes" else "yes")
        if p is None:
            return None, 0.0
        return 1000 - p, sz


class Order:
    __slots__ = ("oid", "ticker", "side", "price_m", "level", "size", "filled_opt", "filled_pess",
                 "ahead", "live_from", "live_to", "best_bid_at_place", "seqgap_at_place")

    def __init__(self, oid, ticker, side, price_m, level, size, ahead, now, best_bid, seqgap):
        self.oid = oid
        self.ticker = ticker
        self.side = side
        self.price_m = price_m
        self.level = level
        self.size = size
        self.filled_opt = 0.0
        self.filled_pess = 0.0
        self.ahead = ahead
        self.live_from = now
        self.live_to = None
        self.best_bid_at_place = best_bid
        self.seqgap_at_place = seqgap

    @property
    def price(self):
        return self.price_m / 1000.0


class Market:
    def __init__(self, ticker, series, close_ts, strike, rd, strike_src):
        self.ticker = ticker
        self.series = series
        self.index_id = COINS[series][0]
        self.close_ts = int(close_ts)
        self.strike = float(strike)
        self.rd = int(rd)
        self.thr = self.strike - 0.5 * 10.0 ** (-self.rd)
        self.strike_src = strike_src
        self.book = Book()
        self.orders = []          # live orders
        self.dead_orders = []
        self.fills = []           # dicts
        self.level_filled = {"yes": [0.0] * len(LEVELS), "no": [0.0] * len(LEVELS)}
        self.decided = set()      # rel values already handled
        self.pending_rel = None
        self.settled = False
        self.result = None
        self.expiration_value = None
        self.n_decisions = 0
        self.n_orders = 0
        self.last_p = None
        self.settle_poll_due = self.close_ts + 5
        self.exp_tries = 0


class Engine:
    """All state and all rules. Fed by on_message() and tick(); the clock is injected."""

    def __init__(self, logf, clock=time.time, maker_fee_rate=0.0):
        self.logf = logf
        self.clock = clock
        self.maker_fee_rate = maker_fee_rate
        self.prints = {i: {} for i in INDEX_IDS}          # index -> stamp_s -> (value, rx)
        self.print_order = {i: collections.deque() for i in INDEX_IDS}
        self.last_rx = {i: 0.0 for i in INDEX_IDS}
        self.lag_samples = collections.deque(maxlen=2000)
        self.prints_count = collections.Counter()
        self.markets = {}                                  # ticker -> Market
        self.seq = {}                                      # sid -> last seq
        self.sid_channel = {}                              # sid -> channel
        self.seq_gaps = 0
        self.seq_gap_flag = False                          # set on gap, cleared on resync
        self.reconnects = 0
        self.next_oid = 1
        self.resubscribe_needed = False
        self.close_summaries_done = set()
        self.last_heartbeat = 0.0
        self.n_msgs = 0
        self.wants_settle = []                             # tickers whose settlement should be fetched
        self.fee_types = {}

    # ---- logging
    def log(self, ev, **kw):
        rec = {"t": iso(self.clock()), "ev": ev}
        rec.update(kw)
        self.logf.write(json.dumps(rec, separators=(",", ":")) + "\n")
        self.logf.flush()

    # ---- market metadata (from REST)
    def add_market(self, m):
        tk = m.get("ticker", "")
        series = tk.split("-")[0]
        if series not in COINS or tk in self.markets:
            return False
        try:
            close_ts = parse_iso(m["close_time"])
        except Exception:
            return False
        cs = m.get("custom_strike") or {}
        rd = int(cs.get("round_digits", COINS[series][1]))
        if cs.get("floor_strike") not in (None, ""):
            strike, src = cs["floor_strike"], "custom_strike.floor_strike"
        elif m.get("floor_strike") not in (None, ""):
            strike, src = m["floor_strike"], "floor_strike"
        else:
            return False
        mk = Market(tk, series, close_ts, strike, rd, src)
        self.markets[tk] = mk
        self.resubscribe_needed = True
        self.log("market", ticker=tk, close=iso(close_ts), strike=repr(mk.strike), rd=rd, thr=repr(mk.thr),
                 strike_src=src, floor_strike=m.get("floor_strike"))
        return True

    def tracked_tickers(self, now=None):
        now = self.clock() if now is None else now
        return sorted(t for t, m in self.markets.items() if m.close_ts + 1 > now)

    # ---- messages
    def on_message(self, obj, rx):
        self.n_msgs += 1
        typ = obj.get("type")
        sid = obj.get("sid")
        seq = obj.get("seq")
        if sid is not None and seq is not None:
            last = self.seq.get(sid)
            if last is not None and seq != last + 1 and typ != "orderbook_snapshot":
                self.seq_gaps += 1
                if typ in ("orderbook_delta", "orderbook_snapshot"):
                    self.seq_gap_flag = True
                    for m in self.markets.values():
                        m.book.synced = False
                    self.resubscribe_needed = True
                self.log("seq_gap", sid=sid, channel=typ, expected=last + 1, got=seq)
            self.seq[sid] = seq
        msg = obj.get("msg") or {}
        if typ == "cfbenchmarks_value":
            self.on_index(msg, rx)
        elif typ == "orderbook_snapshot":
            self.on_snapshot(msg, obj.get("seq"))
        elif typ == "orderbook_delta":
            self.on_delta(msg)
        elif typ == "trade":
            self.on_trade(msg, rx)
        elif typ == "market_lifecycle_v2":
            self.on_lifecycle(msg)
        elif typ == "subscribed":
            self.sid_channel[msg.get("sid")] = msg.get("channel")
            self.log("subscribed", channel=msg.get("channel"), sid=msg.get("sid"), id=obj.get("id"))
        elif typ == "error":
            self.log("ws_error", id=obj.get("id"), msg=msg)

    def on_index(self, msg, rx):
        iid = msg.get("index_id")
        if iid not in self.prints:
            return
        try:
            d = json.loads(msg["data"])
            stamp_ms = int(d["time"])
            v = float(d["value"])
        except Exception:
            return
        stamp = stamp_ms // 1000
        if stamp in self.prints[iid]:
            return
        self.prints[iid][stamp] = (v, rx)
        self.print_order[iid].append(stamp)
        self.last_rx[iid] = rx
        self.prints_count[iid] += 1
        self.lag_samples.append(rx - stamp_ms / 1000.0)
        cutoff = stamp - KEEP_PRINTS_S
        q = self.print_order[iid]
        while q and q[0] < cutoff:
            self.prints[iid].pop(q.popleft(), None)

    def sigma(self, iid):
        q = self.print_order[iid]
        if len(q) < 3:
            return None
        stamps = list(q)[-SIGMA_N:]
        pr = self.prints[iid]
        acc, n = 0.0, 0
        for a, b in zip(stamps, stamps[1:]):
            va, vb = pr[a][0], pr[b][0]
            if va > 0 and vb > 0:
                r = math.log(vb / va)
                acc += r * r
                n += 1
        if n < 2:
            return None
        return math.sqrt(acc / n)

    def on_snapshot(self, msg, seq):
        tk = msg.get("market_ticker")
        m = self.markets.get(tk)
        if m is None:
            return
        b = m.book
        b.yes = {tick_down_m(float(p)): float(s) for p, s in msg.get("yes_dollars_fp", [])}
        b.no = {tick_down_m(float(p)): float(s) for p, s in msg.get("no_dollars_fp", [])}
        b.seq = seq
        b.synced = True

    def on_delta(self, msg):
        m = self.markets.get(msg.get("market_ticker"))
        if m is None:
            return
        b = m.book
        try:
            pm = tick_down_m(float(msg["price_dollars"]))
            d = float(msg["delta_fp"])
            side = msg["side"]
        except Exception:
            return
        ladder = b.yes if side == "yes" else b.no
        nv = ladder.get(pm, 0.0) + d
        if nv <= 1e-9:
            ladder.pop(pm, None)
        else:
            ladder[pm] = nv
        b.last_ts_ms = int(msg.get("ts_ms") or 0)

    def on_lifecycle(self, msg):
        tk = msg.get("market_ticker")
        et = msg.get("event_type")
        m = self.markets.get(tk)
        if m is None:
            return
        if et == "determined" and msg.get("result") in ("yes", "no"):
            self.settle(m, msg.get("result"), None, "lifecycle")
            m.settle_poll_due = self.clock() + 30.0    # REST carries expiration_value only later; tick() fetches it

    def on_trade(self, msg, rx):
        m = self.markets.get(msg.get("market_ticker"))
        if m is None or not m.orders:
            return
        try:
            taker = msg["taker_side"]
            yes_p = float(msg["yes_price_dollars"])
            cnt = float(msg["count_fp"])
            ts_ms = int(msg.get("ts_ms") or (float(msg.get("ts", 0)) * 1000))
        except Exception:
            return
        ts = ts_ms / 1000.0
        my_side = "yes" if taker == "no" else "no"        # taker sold my side -> hit my bids
        trade_p_m = tick_down_m(yes_p if my_side == "yes" else 1.0 - yes_p + 1e-9)
        cands = sorted((o for o in m.orders if o.side == my_side and o.live_from <= ts
                        and trade_p_m <= o.price_m), key=lambda o: -o.price_m)
        rem_opt = cnt
        rem_pess = cnt
        for o in cands:
            room_opt = o.size - o.filled_opt
            room_pess = o.size - o.filled_pess
            f_opt = min(room_opt, rem_opt)
            if trade_p_m < o.price_m:
                f_pess = min(room_pess, rem_pess)
            else:
                ate = min(o.ahead, rem_pess)
                o.ahead -= ate
                f_pess = min(room_pess, rem_pess - ate)
            f_opt = max(f_opt, 0.0)
            f_pess = max(f_pess, 0.0)
            if f_opt <= 0 and f_pess <= 0:
                continue
            o.filled_opt += f_opt
            o.filled_pess += f_pess
            rem_opt -= f_opt
            rem_pess -= f_pess
            m.level_filled[o.side][o.level] += f_opt
            bb, bsz = m.book.best(o.side)
            fill = {"oid": o.oid, "ticker": m.ticker, "side": o.side, "price": o.price, "level": o.level,
                    "trade_id": msg.get("trade_id"), "ts_ms": ts_ms, "trade_price": trade_p_m / 1000.0,
                    "trade_size": cnt, "n_opt": round(f_opt, 2), "n_pess": round(f_pess, 2),
                    "fee_opt": fee_dollars(self.maker_fee_rate, f_opt, o.price),
                    "fee_pess": fee_dollars(self.maker_fee_rate, f_pess, o.price),
                    "taker": False, "book_best_bid": None if bb is None else bb / 1000.0,
                    "book_best_size": bsz, "ahead_left": round(o.ahead, 2),
                    "seq_gap": self.seq_gap_flag or o.seqgap_at_place, "rx_lag": round(rx - ts, 3)}
            m.fills.append(fill)
            self.log("fill", **fill)
            if rem_opt <= 0 and rem_pess <= 0:
                break
        for o in list(m.orders):
            if o.filled_opt >= o.size - 1e-9 and o.filled_pess >= o.size - 1e-9:
                self.cancel(m, o, "filled")

    # ---- orders (paper)
    def place(self, m, side, price_m, level, now):
        already = m.level_filled[side][level]
        size = LEVEL_SIZE - already
        if size <= 0:
            return None
        ahead = (m.book.yes if side == "yes" else m.book.no).get(price_m, 0.0)
        bb, _ = m.book.best(side)
        o = Order(self.next_oid, m.ticker, side, price_m, level, size, ahead, now,
                  None if bb is None else bb / 1000.0, self.seq_gap_flag or not m.book.synced)
        self.next_oid += 1
        m.orders.append(o)
        m.n_orders += 1
        self.log("order", oid=o.oid, ticker=m.ticker, side=side, price=o.price, level=level, size=size,
                 live_from=iso(now), ahead=ahead, best_bid=o.best_bid_at_place, book_synced=m.book.synced)
        # crossing the displayed ask -> immediate taker fill up to displayed size (both models)
        ask_m, ask_sz = m.book.best_ask_m(side)
        if m.book.synced and ask_m is not None and ask_m <= price_m and ask_sz > 0:
            n = min(size, ask_sz)
            price = ask_m / 1000.0
            o.filled_opt += n
            o.filled_pess += n
            m.level_filled[side][level] += n
            # the displayed size I took is gone from the paper book (no double-taking on a reprice)
            other = m.book.no if side == "yes" else m.book.yes
            left = other.get(1000 - ask_m, 0.0) - n
            if left <= 1e-9:
                other.pop(1000 - ask_m, None)
            else:
                other[1000 - ask_m] = left
            fill = {"oid": o.oid, "ticker": m.ticker, "side": side, "price": price, "level": level,
                    "trade_id": None, "ts_ms": int(now * 1000), "trade_price": price, "trade_size": ask_sz,
                    "n_opt": round(n, 2), "n_pess": round(n, 2),
                    "fee_opt": fee_dollars(TAKER_FEE, n, price), "fee_pess": fee_dollars(TAKER_FEE, n, price),
                    "taker": True, "book_best_bid": o.best_bid_at_place, "book_best_size": None,
                    "ahead_left": 0.0, "seq_gap": self.seq_gap_flag, "rx_lag": None}
            m.fills.append(fill)
            self.log("fill", **fill)
            if o.filled_opt >= o.size - 1e-9:
                self.cancel(m, o, "filled_taker")
        return o

    def cancel(self, m, o, why):
        if o in m.orders:
            m.orders.remove(o)
        o.live_to = self.clock()
        m.dead_orders.append(o)
        self.log("cancel", oid=o.oid, ticker=m.ticker, side=o.side, price=o.price, why=why,
                 live_from=iso(o.live_from), live_to=iso(o.live_to),
                 filled_opt=round(o.filled_opt, 2), filled_pess=round(o.filled_pess, 2))

    def cancel_all(self, m, why):
        for o in list(m.orders):
            self.cancel(m, o, why)

    # ---- the decision
    def decide(self, m, rel, now):
        pr = self.prints[m.index_id]
        c = m.close_ts
        stamp = c + rel
        used = pr.get(stamp)
        locked_sum, locked_n, missing = 0.0, 0, False
        for s in range(c - 60, stamp + 1):
            x = pr.get(s)
            if x is None:
                missing = True
            else:
                locked_sum += x[0]
                locked_n += 1
        v = used[0]
        k = (-rel) - 1
        sig = self.sigma(m.index_id)
        # k == 60 - locked_n unless prints are missing; then the unknown prints are also filled with v
        proj = (locked_sum + (60 - locked_n) * v) / 60.0
        if sig is None:
            sd = None
            p = None
        else:
            sd = v * sig * math.sqrt(k * (k + 1) * (2 * k + 1) / 6.0) / 60.0
            if sd > 0:
                p = phi((proj - m.thr) / sd)
            else:
                p = 1.0 if proj >= m.thr else 0.0
        floor_need = FLOOR_FRAC * maxerr(rel)
        lead = abs(proj - m.thr) / v if v else 0.0
        floor_ok = lead >= floor_need
        stale = (now - self.last_rx[m.index_id]) > FEED_STALE_S
        side = None
        if p is not None and not missing and floor_ok and not stale:
            if p >= P_HI:
                side, base = "yes", p
            elif p <= 1.0 - P_HI:
                side, base = "no", 1.0 - p
        desired = {}
        if side:
            for lvl, off in enumerate(LEVELS):
                desired[(side, tick_down_m(base - off))] = lvl
        placed, cancelled = [], []
        for o in list(m.orders):
            if (o.side, o.price_m) not in desired:
                self.cancel(m, o, "reprice" if side else "no_signal")
                cancelled.append(o.oid)
        have = {(o.side, o.price_m) for o in m.orders}
        for (s, pm), lvl in desired.items():
            if (s, pm) not in have:
                o = self.place(m, s, pm, lvl, now)
                if o:
                    placed.append(o.oid)
        m.n_decisions += 1
        m.last_p = p
        self.log("decision", ticker=m.ticker, rel=rel, wall=iso(now), stamp=stamp, rx=iso(used[1]),
                 locked_n=locked_n, missing=missing, v=v, proj=round(proj, 8), thr=m.thr,
                 sd=None if sd is None else round(sd, 8), sigma=None if sig is None else round(sig, 8),
                 p=None if p is None else round(p, 6), lead=round(lead, 7), floor_need=round(floor_need, 7),
                 floor_ok=floor_ok, stale=stale, side=side, placed=placed, cancelled=cancelled,
                 book_synced=m.book.synced)

    def tick(self, now=None):
        now = self.clock() if now is None else now
        for m in list(self.markets.values()):
            c = m.close_ts
            if now < c + REL_FIRST + DECIDE_OFFSET:
                continue
            if now >= c:
                if m.orders:
                    self.cancel_all(m, "close")
                if not m.settled and now >= c + 1200:
                    m.settled = True
                    self.log("settle_timeout", ticker=m.ticker, n_fills=len(m.fills))
                if not m.settled and now >= m.settle_poll_due and m.ticker not in self.wants_settle:
                    self.wants_settle.append(m.ticker)
                    m.settle_poll_due = now + 15.0
                elif (m.settled and m.expiration_value is None and m.exp_tries < 6
                      and now >= m.settle_poll_due and m.ticker not in self.wants_settle):
                    self.wants_settle.append(m.ticker)
                    m.exp_tries += 1
                    m.settle_poll_due = now + 30.0
                if m.settled and now >= c + 1800:
                    self.markets.pop(m.ticker, None)
                continue
            rel = int(math.floor(now - c))                  # -30 .. -1
            if rel < REL_FIRST or rel > REL_LAST or rel in m.decided:
                continue
            if now < c + rel + DECIDE_OFFSET:
                continue
            if (c + rel) in self.prints[m.index_id]:
                m.decided.add(rel)
                try:
                    self.decide(m, rel, now)
                except Exception as e:
                    self.log("decide_error", ticker=m.ticker, rel=rel, err=repr(e), tb=traceback.format_exc()[-800:])
            elif now >= c + rel + DECIDE_DEADLINE:
                m.decided.add(rel)
                self.cancel_all(m, "print_late")
                self.log("decision", ticker=m.ticker, rel=rel, wall=iso(now), stamp=c + rel, rx=None,
                         skipped=True, reason="print_not_received_by_deadline", side=None,
                         placed=[], cancelled=[])
        if now - self.last_heartbeat >= 60.0:
            self.heartbeat(now)

    # ---- settlement
    def settle(self, m, result, expiration_value, src):
        if m.settled:
            return
        m.settled = True
        m.result = result
        m.expiration_value = expiration_value
        if m.ticker in self.wants_settle:
            self.wants_settle.remove(m.ticker)
        self.cancel_all(m, "settled")
        pnl = {"opt": 0.0, "pess": 0.0}
        n = {"opt": 0.0, "pess": 0.0}
        cost = {"opt": 0.0, "pess": 0.0}
        for f in m.fills:
            for mdl in ("opt", "pess"):
                k = f["n_" + mdl]
                if k <= 0:
                    continue
                pay = k if f["side"] == result else 0.0
                pnl[mdl] += pay - k * f["price"] - f["fee_" + mdl]
                n[mdl] += k
                cost[mdl] += k * f["price"] + f["fee_" + mdl]
        self.log("settle", ticker=m.ticker, result=result, expiration_value=expiration_value, src=src,
                 last_p=m.last_p, n_decisions=m.n_decisions, n_orders=m.n_orders, n_fills=len(m.fills),
                 contracts={k: round(v, 2) for k, v in n.items()}, at_risk={k: round(v, 2) for k, v in cost.items()},
                 pnl={k: round(v, 2) for k, v in pnl.items()})
        m.pnl = pnl
        m.n_contracts = n
        m.at_risk = cost
        self.maybe_close_summary(m.close_ts)

    def maybe_close_summary(self, close_ts):
        group = [x for x in self.markets.values() if x.close_ts == close_ts]
        if close_ts in self.close_summaries_done or not group or not all(x.settled for x in group):
            return
        self.close_summaries_done.add(close_ts)
        traded = [x.series for x in group if x.fills]
        agg = {}
        for mdl in ("opt", "pess"):
            agg[mdl] = {"contracts": round(sum(x.n_contracts[mdl] for x in group), 2),
                        "at_risk": round(sum(x.at_risk[mdl] for x in group), 2),
                        "pnl": round(sum(x.pnl[mdl] for x in group), 2)}
        self.log("close_summary", close=iso(close_ts), n_markets=len(group), coins_traded=traded, **agg)

    def heartbeat(self, now):
        self.last_heartbeat = now
        lags = sorted(self.lag_samples)
        def pct(q):
            if not lags:
                return None
            return round(lags[min(len(lags) - 1, int(q * len(lags)))], 3)
        span = 60.0
        pps = {i: round(self.prints_count[i] / span, 2) for i in INDEX_IDS}
        self.prints_count.clear()
        self.lag_samples.clear()
        live_orders = sum(len(m.orders) for m in self.markets.values())
        self.log("health", prints_per_s=pps, lag_p50=pct(0.5), lag_p90=pct(0.9), lag_p99=pct(0.99),
                 seq_gaps=self.seq_gaps, reconnects=self.reconnects, rss_mb=rss_mb(), msgs=self.n_msgs,
                 markets=len(self.markets), tracked=len(self.tracked_tickers(now)), live_orders=live_orders,
                 books_synced=sum(1 for m in self.markets.values() if m.book.synced),
                 maker_fee_rate=self.maker_fee_rate, fee_types=self.fee_types)


# ----------------------------------------------------------------------------- websocket (stdlib)
class WS:
    def __init__(self, host, path, headers):
        self.host, self.path, self.headers = host, path, headers
        self.sock = None
        self.buf = bytearray()
        self.frag = bytearray()

    def connect(self):
        raw = socket.create_connection((self.host, 443), timeout=10)
        ctx = ssl.create_default_context()
        s = ctx.wrap_socket(raw, server_hostname=self.host)
        key = base64.b64encode(os.urandom(16)).decode()
        lines = ["GET %s HTTP/1.1" % self.path, "Host: %s" % self.host, "Upgrade: websocket",
                 "Connection: Upgrade", "Sec-WebSocket-Key: %s" % key, "Sec-WebSocket-Version: 13"]
        for k, v in self.headers.items():
            lines.append("%s: %s" % (k, v))
        s.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = s.recv(4096)
            if not chunk:
                raise ConnectionError("handshake: connection closed")
            resp += chunk
        head, _, rest = resp.partition(b"\r\n\r\n")
        status = head.split(b"\r\n", 1)[0].decode(errors="replace")
        if " 101 " not in status:
            raise ConnectionError("handshake: %s | %s" % (status, head[:300].decode(errors="replace")))
        self.buf = bytearray(rest)
        s.settimeout(0.0)
        self.sock = s

    def send_text(self, text):
        self._send_frame(0x1, text.encode())

    def _send_frame(self, opcode, payload):
        mask = os.urandom(4)
        n = len(payload)
        hdr = bytearray([0x80 | opcode])
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126)
            hdr += struct.pack(">H", n)
        else:
            hdr.append(0x80 | 127)
            hdr += struct.pack(">Q", n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        data = bytes(hdr) + mask + masked
        self.sock.setblocking(True)
        try:
            self.sock.sendall(data)
        finally:
            self.sock.settimeout(0.0)

    def fileno(self):
        return self.sock.fileno()

    def pending(self):
        try:
            return self.sock.pending()
        except Exception:
            return 0

    def recv_into_buf(self):
        """Returns False when the peer closed."""
        try:
            data = self.sock.recv(262144)
        except (ssl.SSLWantReadError, BlockingIOError):
            return True
        if not data:
            return False
        self.buf += data
        return True

    def frames(self):
        """Yield (opcode, payload bytes) for every complete frame in the buffer."""
        b = self.buf
        while True:
            if len(b) < 2:
                return
            fin = b[0] & 0x80
            op = b[0] & 0x0F
            masked = b[1] & 0x80
            ln = b[1] & 0x7F
            i = 2
            if ln == 126:
                if len(b) < 4:
                    return
                ln = struct.unpack(">H", bytes(b[2:4]))[0]
                i = 4
            elif ln == 127:
                if len(b) < 10:
                    return
                ln = struct.unpack(">Q", bytes(b[2:10]))[0]
                i = 10
            if masked:
                i += 4
            if len(b) < i + ln:
                return
            payload = bytes(b[i:i + ln])
            if masked:
                mk = bytes(b[i - 4:i])
                payload = bytes(x ^ mk[j % 4] for j, x in enumerate(payload))
            del b[:i + ln]
            if op in (0x0, 0x1, 0x2):
                self.frag += payload
                if fin:
                    out = bytes(self.frag)
                    self.frag = bytearray()
                    yield (0x1, out)
            elif op == 0x9:
                self._send_frame(0xA, payload)
            elif op == 0x8:
                yield (0x8, payload)
            # 0xA pong: ignore

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None


# ----------------------------------------------------------------------------- REST (public GETs only)
def rest_get(path, params=None, timeout=10):
    q = ""
    if params:
        q = "?" + "&".join("%s=%s" % (k, v) for k, v in params.items())
    req = urllib.request.Request(REST_BASE + path + q, method="GET",
                                 headers={"Accept": "application/json", "User-Agent": "cleanroom-paper/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def rest_thread(outq, inq, stop):
    """Polls open markets every 60 s and settlements on request. Puts ("markets", [..]) / ("settle", ticker, obj)."""
    last_poll = 0.0
    while not stop.is_set():
        now = time.time()
        if now - last_poll >= 60.0:
            last_poll = now
            found = []
            for series in COINS:
                try:
                    r = rest_get("/markets", {"series_ticker": series, "status": "open", "limit": 20})
                    found.extend(r.get("markets", []))
                except Exception as e:
                    outq.put(("error", "poll %s: %r" % (series, e)))
            outq.put(("markets", found))
        try:
            item = inq.get(timeout=1.0)
        except queue.Empty:
            continue
        if item is None:
            break
        tk = item
        try:
            r = rest_get("/markets/%s" % tk)
            outq.put(("settle", tk, r.get("market", {})))
        except Exception as e:
            outq.put(("error", "settle %s: %r" % (tk, e)))
        time.sleep(0.35)                     # nine markets settle in the same second: stay under the rate limit


# ----------------------------------------------------------------------------- runner
def auth_headers():
    sys.path.insert(0, os.path.join(REPO, "research"))
    import kauth  # only its request-signing helper is used
    return kauth.headers("GET", WS_PATH)


def series_fee_types():
    out = {}
    for s in COINS:
        try:
            r = rest_get("/series/%s" % s)
            out[s] = r.get("series", {}).get("fee_type")
        except Exception as e:
            out[s] = "error:%r" % e
    return out


def run_live(minutes):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logf = open(LOG_PATH, "a", encoding="utf-8")
    fee_types = series_fee_types()
    maker_rate = MAKER_FEE_WITH if any(ft == "quadratic_with_maker_fees" for ft in fee_types.values()) else 0.0
    eng = Engine(logf, maker_fee_rate=maker_rate)
    eng.fee_types = fee_types
    eng.log("start", pid=os.getpid(), minutes=minutes, fee_types=fee_types, maker_fee_rate=maker_rate,
            rss_mb=rss_mb(), index_ids=INDEX_IDS, argv=sys.argv)
    stop = threading.Event()
    outq, inq = queue.Queue(), queue.Queue()
    th = threading.Thread(target=rest_thread, args=(outq, inq, stop), daemon=True)
    th.start()
    deadline = time.time() + minutes * 60.0
    ws = None
    host_i = 0
    next_id = 1
    market_sids = []
    backoff = 1.0

    def subscribe(ws_, channels, params, tag):
        nonlocal next_id
        cmd = {"id": next_id, "cmd": "subscribe", "params": dict(params, channels=channels)}
        next_id += 1
        ws_.send_text(json.dumps(cmd))
        eng.log("ws_send", id=cmd["id"], cmd="subscribe", channels=channels, tag=tag,
                n_tickers=len(params.get("market_tickers", [])))
        return cmd["id"]

    def unsubscribe(ws_, sids):
        nonlocal next_id
        if not sids:
            return
        cmd = {"id": next_id, "cmd": "unsubscribe", "params": {"sids": sids}}
        next_id += 1
        ws_.send_text(json.dumps(cmd))
        eng.log("ws_send", id=cmd["id"], cmd="unsubscribe", sids=sids)

    pending_ids = {}   # id -> tag

    def connect():
        nonlocal ws, host_i, market_sids
        host = WS_HOSTS[host_i % len(WS_HOSTS)]
        host_i += 1
        w = WS(host, WS_PATH, auth_headers())
        w.connect()
        eng.log("ws_connected", host=host)
        eng.seq.clear()
        pending_ids[subscribe(w, ["cfbenchmarks_value"], {"index_ids": INDEX_IDS}, "index")] = "index"
        pending_ids[subscribe(w, ["market_lifecycle_v2"], {}, "life")] = "life"
        market_sids = []
        for m in eng.markets.values():
            m.book.synced = False
        eng.resubscribe_needed = True
        ws = w

    def resubscribe_markets(w):
        nonlocal market_sids
        tks = eng.tracked_tickers()
        unsubscribe(w, market_sids)
        market_sids = []
        eng.seq_gap_flag = False
        if tks:
            pending_ids[subscribe(w, ["orderbook_delta"], {"market_tickers": tks}, "book")] = "book"
            pending_ids[subscribe(w, ["trade"], {"market_tickers": tks}, "trade")] = "trade"
        eng.resubscribe_needed = False

    while time.time() < deadline:
        try:
            if ws is None:
                connect()
                backoff = 1.0
            # REST results
            while True:
                try:
                    item = outq.get_nowait()
                except queue.Empty:
                    break
                if item[0] == "markets":
                    for m in item[1]:
                        eng.add_market(m)
                elif item[0] == "settle":
                    tk, mobj = item[1], item[2]
                    m = eng.markets.get(tk)
                    if m and m.settled:
                        ev = mobj.get("expiration_value")
                        if ev not in (None, ""):
                            m.expiration_value = ev
                            eng.log("expiration", ticker=tk, result=mobj.get("result"), expiration_value=ev,
                                    agrees=(mobj.get("result") == m.result), tries=m.exp_tries)
                        elif m.exp_tries >= 6:
                            eng.log("expiration", ticker=tk, result=mobj.get("result"), expiration_value=None,
                                    agrees=None, tries=m.exp_tries)
                    elif m and mobj.get("result") in ("yes", "no"):
                        eng.settle(m, mobj["result"], mobj.get("expiration_value"), "rest")
                    elif m:
                        m.settle_poll_due = time.time() + 15.0
                        if tk in eng.wants_settle:
                            eng.wants_settle.remove(tk)
                elif item[0] == "error":
                    eng.log("rest_error", err=item[1])
            if eng.resubscribe_needed:
                resubscribe_markets(ws)
            for tk in list(eng.wants_settle):
                inq.put(tk)
                eng.wants_settle.remove(tk)
                eng.markets[tk].settle_poll_due = time.time() + 15.0
            # socket
            timeout = 0.05
            if ws.pending() <= 0:
                r, _, _ = select.select([ws], [], [], timeout)
                if not r:
                    eng.tick()
                    continue
            if not ws.recv_into_buf():
                raise ConnectionError("peer closed")
            rx = time.time()
            for op, payload in ws.frames():
                if op == 0x8:
                    raise ConnectionError("close frame %r" % payload[:64])
                try:
                    obj = json.loads(payload)
                except Exception:
                    continue
                if obj.get("type") == "subscribed":
                    tag = pending_ids.pop(obj.get("id"), None)
                    sid = (obj.get("msg") or {}).get("sid")
                    if tag in ("book", "trade") and sid is not None:
                        market_sids.append(sid)
                elif obj.get("type") == "error":
                    tag = pending_ids.pop(obj.get("id"), None)
                    eng.log("ws_error", id=obj.get("id"), tag=tag, msg=obj.get("msg"))
                    if tag in ("book", "trade"):
                        eng.resubscribe_needed = True
                eng.on_message(obj, rx)
            eng.tick()
        except KeyboardInterrupt:
            break
        except Exception as e:
            eng.log("ws_drop", err=repr(e), tb=traceback.format_exc()[-600:])
            if ws is not None:
                ws.close()
            ws = None
            eng.reconnects += 1
            for m in eng.markets.values():
                eng.cancel_all(m, "disconnect")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
    stop.set()
    inq.put(None)
    eng.log("stop", reason="deadline" if time.time() >= deadline else "interrupt", rss_mb=rss_mb())
    if ws is not None:
        ws.close()
    logf.close()


# ----------------------------------------------------------------------------- self-test
class FakeClock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def _idx_msg(iid, stamp_s, value):
    return {"type": "cfbenchmarks_value", "sid": 1, "seq": stamp_s,
            "msg": {"index_id": iid, "received_at": stamp_s * 1000 + 40,
                    "data": json.dumps({"type": "value", "time": stamp_s * 1000, "id": iid, "value": "%.7f" % value})}}


def _feed_print(eng, clk, iid, stamp, value):
    clk.t = stamp + 0.1
    eng.on_message(_idx_msg(iid, stamp, value), clk.t)


def _run_world(strike, slope, book_no_bid=("0.0100", "10.00"), yes_bids=(("0.9700", "50.00"),),
               trades=(), start_rel=-300, with_prints=True, drop_stamp=None, vfn=None):
    """Drive the engine through one BTC market. Returns (engine, market, log lines)."""
    import io
    buf = io.StringIO()
    close = 1_800_000_000
    clk = FakeClock(close - 400)
    eng = Engine(buf, clock=clk)
    eng.add_market({"ticker": "KXBTC15M-TEST-00", "close_time": iso(close)[:19] + "Z",
                    "custom_strike": {"floor_strike": "%.2f" % strike, "round_digits": "2"}, "floor_strike": strike})
    m = eng.markets["KXBTC15M-TEST-00"]
    snap = {"type": "orderbook_snapshot", "sid": 2, "seq": 1,
            "msg": {"market_ticker": m.ticker, "yes_dollars_fp": [list(x) for x in yes_bids],
                    "no_dollars_fp": [list(book_no_bid)]}}
    eng.on_message(snap, clk.t)
    trades = sorted(trades)
    ti = 0
    for rel in range(start_rel, 1):
        stamp = close + rel
        v = vfn(rel) if vfn else 100.0 + slope * (rel - start_rel)
        if with_prints and stamp != drop_stamp:
            _feed_print(eng, clk, "BRTI", stamp, v)
        # decision instants inside this second
        for frac in (0.2, 0.5, 0.95):
            clk.t = stamp + frac
            while ti < len(trades) and close + trades[ti][0] <= clk.t:
                t_rel, side, yes_p, cnt = trades[ti]
                ti += 1
                eng.on_message({"type": "trade", "sid": 3, "seq": ti,
                                "msg": {"trade_id": "t%d" % ti, "market_ticker": m.ticker, "taker_side": side,
                                        "yes_price_dollars": "%.4f" % yes_p, "no_price_dollars": "%.4f" % (1 - yes_p),
                                        "count_fp": "%.2f" % cnt, "ts_ms": int((close + t_rel) * 1000)}}, clk.t)
            eng.tick(clk.t)
    return eng, m, buf


def selftest():
    # --- pieces
    assert tick_down_m(0.9795) == 979 and tick_down_m(0.955) == 955 and tick_down_m(0.849) == 840
    assert tick_down_m(0.9) == 900 and tick_down_m(0.1) == 100 and tick_down_m(0.0995) == 99
    assert abs(maxerr(-25) - (84.8e-4 + 21.5e-4) / 2) < 1e-12 and maxerr(-1) == 0.0 and maxerr(-40) == 84.8e-4
    assert abs(phi(0) - 0.5) < 1e-12 and phi(10) > 0.999999
    assert fee_dollars(0.07, 100, 0.5) == 1.75 and fee_dollars(0.0, 100, 0.5) == 0.0
    assert fee_dollars(0.07, 1, 0.97) == 0.01
    # websocket frame codec round trip (server->client unmasked, client masked)
    w = WS.__new__(WS)
    w.buf = bytearray()
    w.frag = bytearray()
    payload = json.dumps({"x": "y" * 300}).encode()
    w.buf += bytes([0x81, 126]) + struct.pack(">H", len(payload)) + payload
    w.buf += bytes([0x81, 3]) + b"abc"
    got = list(w.frames())
    assert got == [(0x1, payload), (0x1, b"abc")], got
    # msg.data is a JSON string inside JSON
    e0 = Engine(open(os.devnull, "w"), clock=FakeClock(0))
    e0.on_message(_idx_msg("BRTI", 123, 84443.14), 123.1)
    assert e0.prints["BRTI"][123][0] == 84443.14

    # --- empty world: no prints -> nothing placed, decisions skipped as print_late
    eng, m, buf = _run_world(strike=99.0, slope=0.0, with_prints=False)
    lines = [json.loads(x) for x in buf.getvalue().splitlines()]
    assert not any(l["ev"] in ("order", "fill") for l in lines), "empty world placed an order"
    skipped = [l for l in lines if l["ev"] == "decision"]
    assert len(skipped) == 30 and all(l.get("skipped") for l in skipped), len(skipped)

    # --- coin-flip world: a wobbling index on its strike -> p in the middle while prints remain, no orders
    eng, m, buf = _run_world(strike=100.0, slope=0.0, vfn=lambda rel: 100.0 + 0.2 * math.sin(rel / 3.0))
    lines = [json.loads(x) for x in buf.getvalue().splitlines()]
    decs = [l for l in lines if l["ev"] == "decision"]
    assert len(decs) == 30
    assert all(l["locked_n"] == l["rel"] + 61 and not l["missing"] for l in decs), decs[0]
    assert decs[0]["rel"] == -30 and decs[-1]["rel"] == -1
    early = [l for l in decs if l["rel"] <= -15]
    assert all(0.001 < l["p"] < 0.999 and l["side"] is None for l in early), [(l["rel"], l["p"]) for l in early]
    assert decs[-1]["p"] in (0.0, 1.0)      # at rel -1 all 60 prints are in: the outcome is known

    # --- planted YES world: index ~100+, strike 99 -> p = 1, floor passes; trades fill the ladder
    trades = [(-20.0, "no", 0.980, 30.0),    # at my top level: opt 30, pess 30 (nothing ahead at 0.980)
              (-15.0, "no", 0.950, 200.0),   # through 0.98 (70 left) and at 0.95 (100)
              (-25.0, "yes", 0.990, 40.0),   # taker BOUGHT yes: does not hit my bids
              (-10.0, "no", 0.960, 5.0)]     # below 0.98 but 0.98 level is full; above 0.95 -> no fill
    eng, m, buf = _run_world(strike=99.0, slope=0.001, trades=trades)
    lines = [json.loads(x) for x in buf.getvalue().splitlines()]
    decs = [l for l in lines if l["ev"] == "decision"]
    assert all(l["side"] == "yes" and l["p"] == 1.0 and l["floor_ok"] for l in decs), decs[0]
    orders = [l for l in lines if l["ev"] == "order"]
    assert [o["price"] for o in orders[:3]] == [0.98, 0.95, 0.85], orders[:3]
    assert len(orders) == 3, [o["price"] for o in orders]   # same prices every second -> no churn
    fills = [l for l in lines if l["ev"] == "fill"]
    assert [(f["price"], f["n_opt"], f["n_pess"]) for f in fills] == [(0.98, 30.0, 30.0), (0.98, 70.0, 70.0),
                                                                    (0.95, 100.0, 100.0)], fills
    eng.settle(m, "yes", "100.30", "test")
    st = [json.loads(x) for x in buf.getvalue().splitlines() if '"settle"' in x][-1]
    assert st["pnl"] == {"opt": 7.0, "pess": 7.0}, st
    assert st["contracts"] == {"opt": 200.0, "pess": 200.0}
    cs = [json.loads(x) for x in buf.getvalue().splitlines() if '"close_summary"' in x]
    assert len(cs) == 1 and cs[0]["opt"]["pnl"] == 7.0 and cs[0]["pess"]["pnl"] == 7.0, cs
    assert cs[0]["coins_traded"] == ["KXBTC15M"] and cs[0]["opt"]["at_risk"] == 193.0, cs

    # --- queue-ahead: 60 displayed at 0.980 when I place; trade of 100 at 0.980 -> opt 100, pess 40
    eng, m, buf = _run_world(strike=99.0, slope=0.001, yes_bids=(("0.9800", "60.00"),),
                             trades=[(-20.0, "no", 0.980, 100.0)])
    fills = [json.loads(x) for x in buf.getvalue().splitlines() if '"fill"' in x]
    assert [(f["n_opt"], f["n_pess"]) for f in fills] == [(100.0, 40.0)], fills
    eng.settle(m, "no", "98.00", "test")   # planted loss: opt -98, pess -39.2
    st = [json.loads(x) for x in buf.getvalue().splitlines() if '"settle"' in x][-1]
    assert st["pnl"] == {"opt": -98.0, "pess": -39.2}, st

    # --- crossing ask: NO bid displayed at 0.030 (YES ask 0.97, size 25) -> taker fill 25 at 0.97 with fee
    eng, m, buf = _run_world(strike=99.0, slope=0.001, book_no_bid=("0.0300", "25.00"))
    fills = [json.loads(x) for x in buf.getvalue().splitlines() if '"fill"' in x]
    assert fills and fills[0]["taker"] and fills[0]["price"] == 0.97 and fills[0]["n_opt"] == 25.0, fills[:1]
    assert fills[0]["fee_opt"] == fee_dollars(0.07, 25, 0.97) > 0

    # --- planted NO world: strike 101, index ~100 -> p = 0, NO ladder; a taker buying YES at 0.02 hits my NO bid at 0.98
    eng, m, buf = _run_world(strike=101.0, slope=-0.001, yes_bids=(("0.0100", "50.00"),),
                             trades=[(-12.0, "yes", 0.020, 10.0)])
    lines = [json.loads(x) for x in buf.getvalue().splitlines()]
    orders = [l for l in lines if l["ev"] == "order"]
    assert [(o["side"], o["price"]) for o in orders[:3]] == [("no", 0.98), ("no", 0.95), ("no", 0.85)], orders[:3]
    fills = [l for l in lines if l["ev"] == "fill"]
    assert fills and fills[0]["side"] == "no" and fills[0]["n_opt"] == 10.0, fills

    # --- floor: strike so close that the lead floor fails at -30 but passes near the end
    eng, m, buf = _run_world(strike=100.31, slope=0.001)   # index 100.0 -> 100.3; thr 100.305
    decs = [json.loads(x) for x in buf.getvalue().splitlines() if '"decision"' in x]
    assert any(not d["floor_ok"] for d in decs) and any(d["side"] for d in decs), [(d["rel"], d["floor_ok"], d["p"]) for d in decs]
    assert all(d["side"] is None for d in decs if not d["floor_ok"])

    # --- a missing print inside the window -> missing flag, no orders
    eng, m, buf = _run_world(strike=99.0, slope=0.001, drop_stamp=1_800_000_000 - 45)
    decs = [json.loads(x) for x in buf.getvalue().splitlines() if '"decision"' in x]
    assert all(d["missing"] and d["side"] is None for d in decs), decs[0]

    # --- seq gap on the book channel marks books unsynced and asks for a resubscribe
    e1 = Engine(open(os.devnull, "w"), clock=FakeClock(0))
    e1.add_market({"ticker": "KXETH15M-TEST-00", "close_time": "2026-01-01T00:00:00Z",
                   "custom_strike": {"floor_strike": "1.00", "round_digits": "2"}})
    e1.resubscribe_needed = False
    e1.on_message({"type": "orderbook_snapshot", "sid": 7, "seq": 10, "msg": {"market_ticker": "KXETH15M-TEST-00"}}, 0)
    e1.on_message({"type": "orderbook_delta", "sid": 7, "seq": 11, "msg": {"market_ticker": "KXETH15M-TEST-00",
                   "price_dollars": "0.5000", "delta_fp": "3.00", "side": "yes"}}, 0)
    assert e1.markets["KXETH15M-TEST-00"].book.yes == {500: 3.0} and not e1.resubscribe_needed
    e1.on_message({"type": "orderbook_delta", "sid": 7, "seq": 13, "msg": {"market_ticker": "KXETH15M-TEST-00",
                   "price_dollars": "0.5000", "delta_fp": "-3.00", "side": "yes"}}, 0)
    assert e1.seq_gaps == 1 and e1.resubscribe_needed and not e1.markets["KXETH15M-TEST-00"].book.synced
    # no POST anywhere in this file
    src = open(__file__, encoding="utf-8").read()
    assert ("portfolio/" + "orders") not in src
    assert ("method=" + '"POST"') not in src and ("urlopen(req, " + "data") not in src
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--minutes", type=float, default=10080)
    a = ap.parse_args()
    t0 = time.time()
    selftest()
    print("selftest OK (%.2fs)" % (time.time() - t0), flush=True)
    if a.selftest:
        return
    run_live(a.minutes)


if __name__ == "__main__":
    main()
