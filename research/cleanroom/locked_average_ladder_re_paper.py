r"""Clean-room PAPER bot A -- "Locked-average ladder" (rest bids on the already-decided side in the last 30 s).

Built 2026-09-27 from the public Kalshi API/WebSocket docs and the recorded tape only.  NOTHING in this file can send an
order: there is no code path that writes to the exchange (the only HTTP verb used is GET, via research/kauth.py's helpers,
and the WebSocket is used for market-data subscriptions only).

Settlement rule used (derived from rules_primary/rules_secondary and verified on the tape by the clean-room digest):
  settle = round_half_up(mean of the 60 CF Benchmarks RTI prints stamped close-60 .. close-1 s, round_digits)
  YES iff settle >= strike           (strike_type greater_or_equal)
  => YES iff mean >= thr, thr = strike - 0.5 * 10**-round_digits            (exact decimal comparison)

Decision rule, per market, every second rel = -30..-1, at wall time close+rel+0.2 s once the print stamped close+rel has
been RECEIVED (skip the second and cancel if it has not arrived by +0.9 s):
  k = -rel-1 prints still to come, proj = (locked_sum + k*v)/60, sd = v*sigma*sqrt(k(k+1)(2k+1)/6)/60,
  p = Phi((proj-thr)/sd); lead floor |proj-thr|/v >= 0.25*MAXERR(rel).  No orders if missing prints, floor fails, or
  0.001 < p < 0.999.  p >= 0.999: YES bids at p-0.02, p-0.05, p-0.15 (rounded DOWN to the tick), 100 contracts each;
  p <= 0.001: NO bids at (1-p)-0.02, -0.05, -0.15.

Fill models (both logged on every fill):
  opt  : a resting bid at price b is filled by every trade printed after its live_from where the TAKER sold my side
         (taker_side == the other side) at a price <= b, up to that trade's size; fill price = b (a resting order fills at
         its own price).  A bid that crosses the displayed best ask is filled immediately at the ask up to its DISPLAYED
         size (taker fee charged).
  pess : as opt, but a trade AT my price first consumes the size that was displayed ahead of me at my price when I
         placed the order (queue position), and a crossing bid gets nothing (the displayed ask may be gone by the time an
         order arrives).
  Counterparty: a taker selling the losing side into the last 30 s (or a taker buying my side's complement); makers pay
  no fee on this series family under the assumption below.
Fee assumption (public fee schedule could not be fetched at build time, HTTP 429): taker fee = 0.07 * n * p * (1-p)
rounded UP to the cent per fill, maker fee = 0.  Only crossing fills carry a fee; the fee is logged separately.

Usage:
  python research/cleanroom/locked_average_ladder_re_paper.py --selftest          # planted world only, then exit
  python research/cleanroom/locked_average_ladder_re_paper.py --minutes 10080     # self-test, then live paper trading
Log: C:\kals-repo\results\cleanroom-locked_average_ladder_re.jsonl (one JSON per line, UTC).
"""
import argparse
import base64
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

NAME = "locked_average_ladder_re"
LOG_PATH = r"C:\kals-repo\results\cleanroom-%s.jsonl" % NAME
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

MAXERR = [(-30, 84.8e-4), (-20, 21.5e-4), (-15, 13.6e-4), (-10, 6.2e-4), (-7, 3.5e-4), (-5, 2.3e-4),
          (-3, 1.0e-4), (-2, 0.5e-4), (-1, 0.0)]
FLOOR_FRAC = 0.25
P_HI = 0.999
P_LO = 0.001
LEVELS = (0.02, 0.05, 0.15)
SIZE = Decimal("100")
SIGMA_N = 180
SIGMA_MIN_RETURNS = 30
REL_FIRST = -30
DECIDE_OFFSET = 0.2
DECIDE_DEADLINE = 0.9
TAKER_FEE_RATE = Decimal("0.07")
SETTLE_TIMEOUT_S = 1500


# ----------------------------------------------------------------------------------------------------------- helpers
def now_iso(t=None):
    return datetime.fromtimestamp(time.time() if t is None else t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def phi(z):
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def maxerr(rel):
    if rel <= MAXERR[0][0]:
        return MAXERR[0][1]
    if rel >= MAXERR[-1][0]:
        return MAXERR[-1][1]
    for (r0, e0), (r1, e1) in zip(MAXERR, MAXERR[1:]):
        if r0 <= rel <= r1:
            return e0 + (e1 - e0) * (rel - r0) / (r1 - r0)
    return MAXERR[-1][1]


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


# ------------------------------------------------------------------------------------------------------------ engine
class Market:
    def __init__(self, ticker, coin, close_s, strike, round_digits, strike_src):
        self.ticker = ticker
        self.coin = coin
        self.index_id = COINS[coin][1]
        self.close_s = close_s
        self.strike = strike                      # Decimal or None
        self.rd = round_digits
        self.strike_src = strike_src
        self.thr = None
        self.thr_f = None
        if strike is not None:
            self.thr = strike - Decimal(1).scaleb(-round_digits) / 2
            self.thr_f = float(self.thr)
        self.next_rel = REL_FIRST
        self.done = False
        self.orders = []                          # live orders
        self.fills = []
        self.result = None
        self.expiration_value = None
        self.settle_asked_at = 0
        self.settled = False
        self.n_decisions = 0
        self.n_orders = 0


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


class Order:
    _n = 0

    def __init__(self, ticker, side, level, price, size, live_from, ahead):
        Order._n += 1
        self.id = Order._n
        self.ticker = ticker
        self.side = side
        self.level = level
        self.price = price
        self.size = size
        self.live_from = live_from
        self.live_to = None
        self.ahead = ahead                        # displayed size ahead of me at my price when placed (pess model)
        self.rem_opt = size
        self.rem_pess = size


class Engine:
    """Everything the bot decides, with the clock injected so a planted world can drive it."""

    def __init__(self, log, now_fn):
        self.log = log
        self.now = now_fn
        self.prints = {}                          # index_id -> {stamp_s: (value_f, value_str, rx)}
        self.markets = {}                         # ticker -> Market
        self.books = {}                           # ticker -> Book
        self.pending_close_groups = {}            # close_s -> set(tickers)
        self.cum_pnl = {"opt": Decimal(0), "pess": Decimal(0)}
        self.n_gaps = 0
        self.lag_ms = deque(maxlen=2000)
        self.print_count = {}
        self.resync_wanted = False
        self.last_expiration = {}                 # coin -> (close_s, Decimal expiration_value)
        self.finished = set()                     # tickers already settled and released (never re-added)

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
        if len(d) > 300:
            cutoff = stamp_s - 240
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
        if m is None or not m.orders:
            return
        ts = msg["ts_ms"] / 1000.0
        yes_p = Decimal(msg["yes_price_dollars"])
        no_p = Decimal(1) - yes_p
        cnt = Decimal(msg["count_fp"])
        taker = msg["taker_side"]
        for o in m.orders:
            if o.live_to is not None or ts < o.live_from:
                continue
            if o.side == "yes":
                if taker != "no" or yes_p > o.price:
                    continue
                trade_p = yes_p
            else:
                if taker != "yes" or no_p > o.price:
                    continue
                trade_p = no_p
            f_opt = min(cnt, o.rem_opt)
            if trade_p < o.price:
                f_pess = min(cnt, o.rem_pess)
            else:
                eat = min(cnt, o.ahead)
                o.ahead -= eat
                f_pess = min(cnt - eat, o.rem_pess)
            if f_opt <= 0 and f_pess <= 0:
                continue
            o.rem_opt -= f_opt
            o.rem_pess -= f_pess
            b = self.books.get(ticker)
            bb = b.best_bid(o.side) if b else (None, Decimal(0))
            fill = {"ticker": ticker, "order_id": o.id, "level": o.level, "side": o.side, "kind": "rest",
                    "trade_id": msg.get("trade_id"), "ts_ms": msg["ts_ms"], "print_price": str(trade_p),
                    "print_size": str(cnt), "my_price": str(o.price), "size_opt": str(f_opt), "size_pess": str(f_pess),
                    "fee_opt": "0", "fee_pess": "0", "ahead_left": str(o.ahead),
                    "book_best_bid": str(bb[0]) if bb[0] is not None else None, "book_best_size": str(bb[1]),
                    "book_synced": bool(b and b.synced), "seq_gap_flag": bool(b and not b.synced)}
            m.fills.append(fill)
            self.log.write("fill", **fill)
            if o.rem_opt <= 0 and o.rem_pess <= 0:
                o.live_to = ts

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
        """The next-to-close market of each coin (what we subscribe to)."""
        best = {}
        for m in self.markets.values():
            if m.close_s > now and (m.coin not in best or m.close_s < best[m.coin].close_s):
                best[m.coin] = m
        return sorted(x.ticker for x in best.values())

    # --- settlement maths --------------------------------------------------------------------------------------------
    def sigma(self, index_id, upto_stamp):
        d = self.prints.get(index_id, {})
        ks = sorted(k for k in d if k <= upto_stamp)[-(SIGMA_N + 1):]
        acc, n = 0.0, 0
        for a, b in zip(ks, ks[1:]):
            if b - a == 1 and d[a][0] > 0 and d[b][0] > 0:
                r = math.log(d[b][0] / d[a][0])
                acc += r * r
                n += 1
        if n < SIGMA_MIN_RETURNS:
            return None, n
        return math.sqrt(acc / n), n

    def window_state(self, m, upto_stamp):
        d = self.prints.get(m.index_id, {})
        lo = m.close_s - 60
        got = [d[s] for s in range(lo, upto_stamp + 1) if s in d]
        expected = upto_stamp - lo + 1
        return got, expected

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
            if m.done:
                continue
            if now >= m.close_s:
                self.expire_orders(m, m.close_s, "close")
                m.done = True
                continue
            while not m.done and m.next_rel <= -1:
                rel = m.next_rel
                t_dec = m.close_s + rel + DECIDE_OFFSET
                if now < t_dec:
                    break
                stamp = m.close_s + rel
                pr = self.prints.get(m.index_id, {}).get(stamp)
                if pr is not None and pr[2] <= now:
                    self.decide(m, rel, pr, now)
                    m.next_rel += 1
                elif now > m.close_s + rel + DECIDE_DEADLINE:
                    self.cancel_all(m, now, "no_print")
                    self.log.write("decision", ticker=m.ticker, rel=rel, wall=round(now, 3), skipped="no_print",
                                   orders=0)
                    m.next_rel += 1
                else:
                    break

    def decide(self, m, rel, pr, now):
        v, v_str, rx = pr
        k = -rel - 1
        stamp = m.close_s + rel
        got, expected = self.window_state(m, stamp)
        locked_n = len(got)
        missing = locked_n < expected
        locked_sum = sum(x[0] for x in got)
        proj = (locked_sum + k * v) / 60.0
        sig, nret = self.sigma(m.index_id, stamp)
        rec = {"ticker": m.ticker, "rel": rel, "wall": round(now, 3), "stamp": stamp, "rx": round(rx, 3),
               "locked_n": locked_n, "missing": missing, "v": v_str, "proj": proj, "thr": str(m.thr), "sigma": sig,
               "n_ret": nret, "k": k}
        p = None
        sd = None
        floor_ok = False
        reason = None
        if m.thr is None:
            reason = "no_strike"
        elif missing:
            reason = "missing_prints"
        elif sig is None:
            reason = "no_sigma"
        else:
            if k == 0:
                em = self.exact_mean(m)
                if em is None:
                    reason = "missing_prints"
                else:
                    p = 1.0 if em >= m.thr else 0.0
                    sd = 0.0
                    rec["exact_mean"] = str(em)
            else:
                sd = v * sig * math.sqrt(k * (k + 1) * (2 * k + 1) / 6.0) / 60.0
                if sd <= 0:
                    p = 1.0 if proj >= m.thr_f else 0.0
                else:
                    p = phi((proj - m.thr_f) / sd)
            if reason is None:
                floor_ok = abs(proj - m.thr_f) / v >= FLOOR_FRAC * maxerr(rel)
                if not floor_ok:
                    reason = "floor"
                elif P_LO < p < P_HI:
                    reason = "p_mid"
        rec.update({"sd": sd, "p": p, "floor_ok": floor_ok, "reason": reason})
        m.n_decisions += 1
        if reason is not None:
            n_c = self.cancel_all(m, now, reason)
            rec.update({"orders": 0, "cancelled": n_c})
            self.log.write("decision", **rec)
            return
        if p >= P_HI:
            side, base = "yes", p
        else:
            side, base = "no", 1.0 - p
        wanted = []
        for i, off in enumerate(LEVELS):
            px = floor_tick(base - off)
            if px <= 0:
                continue
            wanted.append((i, px))
        placed, kept, cancelled = self.reconcile(m, side, wanted, now)
        rec.update({"side": side, "orders": len(wanted), "placed": placed, "kept": kept, "cancelled": cancelled})
        self.log.write("decision", **rec)

    def reconcile(self, m, side, wanted, now):
        keep = set()
        placed = kept = cancelled = 0
        live = [o for o in m.orders if o.live_to is None]
        for o in live:
            match = [w for w in wanted if w[0] == o.level and w[1] == o.price and o.side == side]
            if match:
                keep.add(o.id)
                kept += 1
            else:
                o.live_to = now
                cancelled += 1
                self.log.write("cancel", ticker=m.ticker, order_id=o.id, level=o.level, side=o.side,
                               price=str(o.price), live_from=round(o.live_from, 3), live_to=round(now, 3),
                               rem_opt=str(o.rem_opt), rem_pess=str(o.rem_pess), why="repriced")
        have = {(o.level, o.price) for o in m.orders if o.id in keep}
        b = self.books.get(m.ticker)
        for lvl, px in wanted:
            if (lvl, px) in have:
                continue
            ahead = Decimal(0)
            crossed = None
            if b is not None and b.synced:
                lad = b.yes if side == "yes" else b.no
                ahead = lad.get(px, Decimal(0))
                ask_p, ask_sz = b.best_ask(side)
                if ask_p is not None and px >= ask_p and ask_sz > 0:
                    crossed = (ask_p, ask_sz)
            o = Order(m.ticker, side, lvl, px, SIZE, now, ahead)
            m.orders.append(o)
            m.n_orders += 1
            placed += 1
            self.log.write("order", ticker=m.ticker, order_id=o.id, level=lvl, side=side, price=str(px),
                           size=str(SIZE), live_from=round(now, 3), ahead=str(ahead),
                           book_synced=bool(b and b.synced),
                           crossed_ask=str(crossed[0]) if crossed else None,
                           crossed_size=str(crossed[1]) if crossed else None)
            if crossed:
                ask_p, ask_sz = crossed
                f_opt = min(ask_sz, o.rem_opt)
                o.rem_opt -= f_opt
                fee = taker_fee(f_opt, ask_p)
                fill = {"ticker": m.ticker, "order_id": o.id, "level": lvl, "side": side, "kind": "cross",
                        "trade_id": None, "ts_ms": int(now * 1000), "print_price": str(ask_p),
                        "print_size": str(ask_sz), "my_price": str(ask_p), "size_opt": str(f_opt), "size_pess": "0",
                        "fee_opt": str(fee), "fee_pess": "0", "ahead_left": str(o.ahead),
                        "book_best_bid": None, "book_best_size": None, "book_synced": True, "seq_gap_flag": False}
                m.fills.append(fill)
                self.log.write("fill", **fill)
        return placed, kept, cancelled

    def cancel_all(self, m, now, why):
        n = 0
        for o in m.orders:
            if o.live_to is None:
                o.live_to = now
                n += 1
                self.log.write("cancel", ticker=m.ticker, order_id=o.id, level=o.level, side=o.side,
                               price=str(o.price), live_from=round(o.live_from, 3), live_to=round(now, 3),
                               rem_opt=str(o.rem_opt), rem_pess=str(o.rem_pess), why=why)
        return n

    def expire_orders(self, m, t, why):
        for o in m.orders:
            if o.live_to is None:
                o.live_to = t
                self.log.write("cancel", ticker=m.ticker, order_id=o.id, level=o.level, side=o.side,
                               price=str(o.price), live_from=round(o.live_from, 3), live_to=t,
                               rem_opt=str(o.rem_opt), rem_pess=str(o.rem_pess), why=why)

    # --- settlement --------------------------------------------------------------------------------------------------
    def markets_needing_result(self, now):
        out = []
        for m in self.markets.values():
            if m.done and not m.settled and now >= m.close_s + 3 and now - m.settle_asked_at >= 10:
                out.append(m)
        return out

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
        my_settle = None
        my_pred = None
        if em is not None:
            my_settle = em.quantize(Decimal(1).scaleb(-m.rd), rounding=ROUND_HALF_UP)
            my_pred = "yes" if (m.strike is not None and my_settle >= m.strike) else "no"
        pnl = {}
        contracts = {}
        fees = {}
        for model in ("opt", "pess"):
            tot, n, fee = Decimal(0), Decimal(0), Decimal(0)
            for f in m.fills:
                sz = Decimal(f["size_" + model])
                if sz <= 0:
                    continue
                px = Decimal(f["my_price"])
                win = f["side"] == result
                tot += sz * (Decimal(1) - px) if win else -sz * px
                n += sz
                fee += Decimal(f["fee_" + model])
            pnl[model] = (tot - fee).quantize(Decimal("0.0001"))
            contracts[model] = n.quantize(Decimal("0.01"))
            fees[model] = fee.quantize(Decimal("0.01"))
            self.cum_pnl[model] += pnl[model]
        self.log.write("settle", ticker=ticker, coin=m.coin, close_s=m.close_s, result=result,
                       expiration_value=expiration_value, my_settle=str(my_settle) if my_settle is not None else None,
                       my_pred=my_pred, pred_match=(my_pred == result) if my_pred else None, strike=str(m.strike),
                       strike_src=m.strike_src, pnl_opt=str(pnl["opt"]), pnl_pess=str(pnl["pess"]),
                       contracts_opt=str(contracts["opt"]), contracts_pess=str(contracts["pess"]),
                       fee_opt=str(fees["opt"]), fee_pess=str(fees["pess"]), n_fills=len(m.fills),
                       n_decisions=m.n_decisions, n_orders=m.n_orders,
                       cum_pnl_opt=str(self.cum_pnl["opt"]), cum_pnl_pess=str(self.cum_pnl["pess"]))
        m.pnl = pnl
        m.contracts = contracts
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
        traded = sorted({x.coin for x in ms if x.fills})
        tot = {"opt": Decimal(0), "pess": Decimal(0)}
        n = {"opt": Decimal(0), "pess": Decimal(0)}
        risk = {"opt": Decimal(0), "pess": Decimal(0)}
        for x in ms:
            for model in ("opt", "pess"):
                tot[model] += getattr(x, "pnl", {}).get(model, Decimal(0))
                n[model] += getattr(x, "contracts", {}).get(model, Decimal(0))
                for f in x.fills:
                    risk[model] += Decimal(f["size_" + model]) * Decimal(f["my_price"])
        for model in ("opt", "pess"):
            risk[model] = risk[model].quantize(Decimal("0.01"))
        self.log.write("close_summary", close_s=m.close_s, close=now_iso(m.close_s), markets=len(ms),
                       coins_traded=traded, contracts_opt=str(n["opt"]), contracts_pess=str(n["pess"]),
                       at_risk_opt=str(risk["opt"]), at_risk_pess=str(risk["pess"]), pnl_opt=str(tot["opt"]),
                       pnl_pess=str(tot["pess"]), cum_pnl_opt=str(self.cum_pnl["opt"]),
                       cum_pnl_pess=str(self.cum_pnl["pess"]))
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


def run_live(minutes):
    sys.path.insert(0, r"C:\kals-repo\research")
    import kauth  # request-signing helpers only
    log = Logger(LOG_PATH)
    q = queue.Queue()
    eng = Engine(log, time.time)
    ws = WS(q, log, kauth.headers)
    ws.index_ids = [COINS[c][1] for c in COINS]
    rest = Rest(q, log, kauth.get)
    log.write("start", pid=os.getpid(), minutes=minutes, python=sys.version.split()[0], rss_mb=rss_mb(),
              log=LOG_PATH, coins=list(COINS))
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
                eng.on_trade(obj["msg"]["market_ticker"], obj["msg"])
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
        eng.tick()
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
                      queue=q.qsize(), cum_pnl_opt=str(eng.cum_pnl["opt"]), cum_pnl_pess=str(eng.cum_pnl["pess"]))
            print_rate = {}
            n_msgs = {}
            last_health = now
        time.sleep(0.02)
    ws.stop = True
    rest.stop = True
    log.write("stop", reason="minutes_elapsed")


# ---------------------------------------------------------------------------------------------------------- self-test
def selftest():
    """Planted world with known fills and pnl, plus an empty world that must place nothing."""
    out = []

    def check(cond, what):
        if not cond:
            raise AssertionError("SELFTEST FAIL: " + what)
        out.append(what)

    # tick / rounding helpers
    check(floor_tick(0.98) == Decimal("0.9800"), "floor_tick 0.98")
    check(floor_tick(0.949) == Decimal("0.9490"), "floor_tick 0.949 (deci-cent above 0.90)")
    check(floor_tick(0.849) == Decimal("0.8400"), "floor_tick 0.849 -> 0.84 (cent tick)")
    check(floor_tick(0.0955) == Decimal("0.0950"), "floor_tick 0.0955 -> 0.095")
    check(abs(maxerr(-25) - (84.8e-4 + 21.5e-4) / 2) < 1e-12, "maxerr interpolation")
    check(taker_fee(Decimal(5), Decimal("0.97")) == Decimal("0.02"), "taker fee ceil to cent")
    check(abs(phi(0) - 0.5) < 1e-12 and phi(64) == 1.0, "phi")

    # planted world -----------------------------------------------------------------------------------------------
    clock = [0.0]
    sink = []
    log = Logger(None, sink)
    eng = Engine(log, lambda: clock[0])
    C = 1_000_000                                   # close
    # BTC: index alternates 101.00 / 101.01 (sigma ~1e-4), strike 100.00 -> certain YES
    eng.add_market("BTC-T", "BTC", C, Decimal("100.00"), 2, "planted")
    # ETH: index 99.0 / 99.01, strike 100.00 -> certain NO
    eng.add_market("ETH-T", "ETH", C, Decimal("100.00"), 2, "planted")
    # SOL: certain YES but the print at close-30 is missing until close-29 (skip, then missing flag)
    eng.add_market("SOL-T", "SOL", C, Decimal("100.00"), 2, "planted")
    # XRP: certain YES with a displayed YES ask at 0.970 (crossing case)
    eng.add_market("XRP-T", "XRP", C, Decimal("100.00"), 2, "planted")
    # DOGE: p in the middle (index straddles strike) -> no orders
    eng.add_market("DOGE-T", "DOGE", C, Decimal("100.0000000"), 7, "planted")
    check(eng.markets["BTC-T"].thr == Decimal("99.995"), "thr = strike - half ulp")
    check(eng.markets["DOGE-T"].thr == Decimal("99.99999995"), "thr for 7 dp")
    for s in range(C - 240, C + 1):
        rx = s + 0.1
        eng.on_print("BRTI", s * 1000, "101.00" if s % 2 else "101.01", rx)
        eng.on_print("ETHUSD_RTI", s * 1000, "99.00" if s % 2 else "99.01", rx)
        if s != C - 30:
            eng.on_print("SOLUSD_RTI", s * 1000, "101.00" if s % 2 else "101.01", rx)
        eng.on_print("XRPUSD_RTI", s * 1000, "101.00" if s % 2 else "101.01", rx)
        eng.on_print("DOGEUSD_RTI", s * 1000, "99.9999" if s % 2 else "100.0001", rx)
    sig, n = eng.sigma("BRTI", C - 30)
    check(n == 180 and abs(sig - abs(math.log(101.01 / 101.00))) < 1e-9, "sigma = RMS of 180 1-s log returns")
    # books: BTC has 30 displayed ahead at 0.980 and a YES ask at 0.99; XRP has a YES ask at 0.970 size 5
    eng.on_snapshot("BTC-T", {"yes_dollars_fp": [["0.9800", "30.00"]], "no_dollars_fp": [["0.0100", "50.00"]]}, 1)
    eng.on_snapshot("ETH-T", {"yes_dollars_fp": [["0.0100", "10.00"]]}, 2)
    eng.on_snapshot("XRP-T", {"no_dollars_fp": [["0.0300", "5.00"]]}, 3)
    eng.on_delta("BTC-T", {"side": "yes", "price_dollars": "0.9800", "delta_fp": "10.00"}, 4)   # ahead now 40
    eng.on_delta("BTC-T", {"side": "yes", "price_dollars": "0.9800", "delta_fp": "-10.00"}, 5)  # back to 30
    eng.on_delta("BTC-T", {"side": "yes", "price_dollars": "0.9800", "delta_fp": "-10.00"}, 1)  # stale seq ignored
    check(eng.books["BTC-T"].yes[Decimal("0.98")] == Decimal(30), "book deltas applied, stale seq ignored")
    check(eng.books["BTC-T"].best_ask("yes") == (Decimal("0.99"), Decimal(50)), "best YES ask = 1 - best NO bid")

    # rel = -30 decision at close-30+0.2
    clock[0] = C - 30 + 0.2
    eng.tick()
    d = [r for r in sink if r["ev"] == "decision"]
    check(len(d) == 4, "four markets decided at rel -30 (SOL waits for its print)")
    btc = [r for r in d if r["ticker"] == "BTC-T"][0]
    check(btc["p"] == 1.0 and btc["floor_ok"] and btc["orders"] == 3 and btc["side"] == "yes", "BTC certain YES -> 3 YES bids")
    check(btc["locked_n"] == 31 and btc["k"] == 29 and not btc["missing"], "window: 31 locked, 29 to come")
    ob = [r for r in sink if r["ev"] == "order" and r["ticker"] == "BTC-T"]
    check([r["price"] for r in ob] == ["0.9800", "0.9500", "0.8500"], "BTC ladder prices 0.98/0.95/0.85")
    check(Decimal(ob[0]["ahead"]) == 30, "size ahead of me recorded from the book")
    eth = [r for r in d if r["ticker"] == "ETH-T"][0]
    check(eth["p"] == 0.0 and eth["side"] == "no" and eth["orders"] == 3, "ETH certain NO -> 3 NO bids")
    doge = [r for r in d if r["ticker"] == "DOGE-T"][0]
    check(doge["reason"] == "floor" and doge["orders"] == 0 and doge["p"] is not None, "DOGE straddling the strike -> lead floor fails, no orders")
    # p_mid: a projection 1.5 sd above thr with the floor passed -> no orders
    z = (btc["proj"] - float(Decimal(btc["thr"]))) / btc["sd"]
    check(z > 10, "planted BTC lead is many sd")
    check(P_LO < phi(1.5) < P_HI, "p_mid band")
    xf = [r for r in sink if r["ev"] == "fill" and r["ticker"] == "XRP-T"]
    check(len(xf) == 1 and xf[0]["kind"] == "cross" and xf[0]["size_opt"] == "5.00" and xf[0]["size_pess"] == "0"
          and xf[0]["my_price"] == "0.9700" and xf[0]["fee_opt"] == "0.02",
          "XRP crossing fill: displayed size at the displayed ask, fee charged, pess 0")
    check(not any(r["ev"] == "decision" and r["ticker"] == "SOL-T" for r in sink), "SOL not decided before its print")
    # SOL: print for close-30 never arrives -> skipped at +0.9
    clock[0] = C - 30 + 0.95
    eng.tick()
    sd = [r for r in sink if r["ev"] == "decision" and r["ticker"] == "SOL-T"]
    check(len(sd) == 1 and sd[0].get("skipped") == "no_print", "SOL second skipped when the print is late")
    # trades for BTC at rel -25: 40 @0.980 sold to YES bids (ahead 30 -> pess 10), 20 @0.970 (through), 500 taker-bought (no)
    trade_before = {"ts_ms": (C - 31) * 1000, "yes_price_dollars": "0.9800", "count_fp": "999.00", "taker_side": "no", "trade_id": "t0"}
    eng.on_trade("BTC-T", trade_before)
    check(not [r for r in sink if r["ev"] == "fill" and r["ticker"] == "BTC-T"], "trade before live_from does not fill")
    eng.on_trade("BTC-T", {"ts_ms": (C - 25) * 1000 + 500, "yes_price_dollars": "0.9800", "count_fp": "40.00", "taker_side": "no", "trade_id": "t1"})
    eng.on_trade("BTC-T", {"ts_ms": (C - 25) * 1000 + 600, "yes_price_dollars": "0.9700", "count_fp": "20.00", "taker_side": "no", "trade_id": "t2"})
    eng.on_trade("BTC-T", {"ts_ms": (C - 25) * 1000 + 700, "yes_price_dollars": "0.9850", "count_fp": "500.00", "taker_side": "yes", "trade_id": "t3"})
    bf = [r for r in sink if r["ev"] == "fill" and r["ticker"] == "BTC-T"]
    check([(r["size_opt"], r["size_pess"]) for r in bf] == [("40.00", "10.00"), ("20.00", "20.00")],
          "BTC fills: opt 40+20, pess 10+20 (queue ahead consumed first)")
    check(all(r["level"] == 0 and r["my_price"] == "0.9800" for r in bf), "only the top rung (0.98) was reached")
    # ETH NO bid at 0.980: taker buys YES at 0.020 = sells NO at 0.980, 10 contracts, nothing ahead
    eng.on_trade("ETH-T", {"ts_ms": (C - 20) * 1000, "yes_price_dollars": "0.0200", "count_fp": "10.00", "taker_side": "yes", "trade_id": "t4"})
    ef = [r for r in sink if r["ev"] == "fill" and r["ticker"] == "ETH-T"]
    check(len(ef) == 1 and ef[0]["side"] == "no" and ef[0]["size_opt"] == "10.00" and ef[0]["size_pess"] == "10.00", "ETH NO fill both models")
    # walk the remaining seconds: orders at the same price are kept (live_from unchanged), rel -1 uses the exact mean
    for rel in range(-29, 0):
        clock[0] = C + rel + 0.2
        eng.tick()
    btc_orders = [r for r in sink if r["ev"] == "order" and r["ticker"] == "BTC-T"]
    check(len(btc_orders) == 3, "BTC orders kept across seconds (no cancel/replace at the same price)")
    last = [r for r in sink if r["ev"] == "decision" and r["ticker"] == "BTC-T"][-1]
    check(last["rel"] == -1 and last["k"] == 0 and last["p"] == 1.0 and "exact_mean" in last, "rel -1: exact decimal mean")
    n_dec = len([r for r in sink if r["ev"] == "decision" and r["ticker"] == "BTC-T"])
    check(n_dec == 30, "30 decision seconds per market")
    # close: orders expire, then results
    clock[0] = C + 0.5
    eng.tick()
    check(all(o.live_to == C for o in eng.markets["BTC-T"].orders), "orders expire at the close")
    clock[0] = C + 5
    need = eng.markets_needing_result(clock[0])
    check(len(need) == 5, "all five markets ask for a result after the close")
    for tk, res in (("BTC-T", "yes"), ("ETH-T", "no"), ("SOL-T", "yes"), ("XRP-T", "yes"), ("DOGE-T", "yes")):
        eng.on_result(tk, res, "101.00", clock[0])
    st = {r["ticker"]: r for r in sink if r["ev"] == "settle"}
    check(st["BTC-T"]["pnl_opt"] == "1.2000" and st["BTC-T"]["pnl_pess"] == "0.6000", "BTC pnl: opt 60x0.02=1.20, pess 30x0.02=0.60")
    check(st["BTC-T"]["my_settle"] == "101.01" and st["BTC-T"]["pred_match"] is True, "settlement mean rounded half-up")
    check(st["ETH-T"]["pnl_opt"] == "0.2000" and st["ETH-T"]["pnl_pess"] == "0.2000", "ETH NO pnl 10x0.02")
    check(st["XRP-T"]["pnl_opt"] == "0.1300" and Decimal(st["XRP-T"]["pnl_pess"]) == 0, "XRP crossing pnl 5x0.03-0.02 fee, pess 0")
    cs = [r for r in sink if r["ev"] == "close_summary"]
    check(len(cs) == 1 and cs[0]["pnl_opt"] == "1.5300" and cs[0]["pnl_pess"] == "0.8000" and cs[0]["coins_traded"] == ["BTC", "ETH", "XRP"],
          "close summary sums the three traded coins")
    check(not eng.markets, "settled markets released from memory")
    check(eng.add_market("BTC-T", "BTC", C, Decimal("100.00"), 2, "planted") is None and "BTC-T" not in eng.markets,
          "a settled market is never re-added")
    check(eng.add_market("P-T", "BTC", int(clock[0]) - 1, Decimal("100.00"), 2, "planted") is None, "a past close is never added")
    # losing side pnl: a YES fill that settles NO loses the price paid
    eng2 = Engine(Logger(None, []), lambda: 0)
    m2 = eng2.add_market("L-T", "BTC", 10, Decimal("1"), 2, "planted")
    m2.fills.append({"side": "yes", "my_price": "0.9800", "size_opt": "100", "size_pess": "50", "fee_opt": "0", "fee_pess": "0"})
    m2.done = True
    eng2.on_result("L-T", "no", "0", 20)
    check(eng2.cum_pnl["opt"] == Decimal("-98") and eng2.cum_pnl["pess"] == Decimal("-49"), "losing fill costs the price paid (100x0.98, 50x0.98)")
    # rounding tie: mean exactly on a .5 rounds UP onto the strike -> YES
    eng3 = Engine(Logger(None, []), lambda: 0)
    m3 = eng3.add_market("R-T", "BTC", 100, Decimal("100.00"), 2, "planted")
    for s in range(40, 100):
        eng3.on_print("BRTI", s * 1000, "99.995", s + 0.1)
    check(eng3.exact_mean(m3) == Decimal("99.995") and eng3.exact_mean(m3) >= m3.thr, "tie 99.995 counts as YES (half-up)")

    # empty worlds ----------------------------------------------------------------------------------------------------
    sinkE = []
    clock[0] = C - 100
    engE = Engine(Logger(None, sinkE), lambda: clock[0])
    engE.add_market("E-T", "BTC", C, Decimal("100.00"), 2, "planted")     # market, no prints
    for rel in range(-30, 1):
        clock[0] = C + rel + 0.95
        engE.tick()
    check(not [r for r in sinkE if r["ev"] in ("order", "fill")], "empty world (no prints): nothing placed")
    check(len([r for r in sinkE if r["ev"] == "decision" and r.get("skipped")]) == 30, "empty world: 30 skipped seconds")
    engE2 = Engine(Logger(None, sinkE), lambda: clock[0])                 # prints, no market
    for s in range(C - 240, C + 1):
        engE2.on_print("BRTI", s * 1000, "101.00", s + 0.1)
    engE2.tick()
    engE2.on_trade("E-T", {"ts_ms": C * 1000, "yes_price_dollars": "0.5000", "count_fp": "1.00", "taker_side": "no", "trade_id": "x"})
    check(not [r for r in sinkE if r["ev"] in ("order", "fill")], "empty world (no market): nothing placed")
    # no code path can send an order
    src = open(__file__, encoding="utf-8").read()
    check(src.count("portfolio/" + "orders") == 0, "no order endpoint in source")
    check(src.count("url" + "open") == 0 and src.count("PO" + "ST") == 0 and src.count("Req" + "uest(") == 0,
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
