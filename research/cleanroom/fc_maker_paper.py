#!/usr/bin/env python3
r"""fc_maker_paper.py -- PAPER ONLY: the RESTING-BID forecaster (virtual post-only bids) shadowed on the live feed.

Operator 2026-10-18: "Start resting bid paper test".  Spec: the fc synth of 2026-10-18 ~15:10Z, "Paper test 1:
resting-bid shadow"; fill rule = C:\kals-repo\.sweep\q-2026-10-18e\fc-maker\s4_sim.py (variant
p_fair_m07_r29_back_pull_nx_L100_C90 = skeptic C1_base), moved from the recorded tape onto the live WebSocket.

NOTHING IN THIS FILE CAN PLACE AN ORDER.  It has no order code: no order endpoint, no HTTP write verb, no signing of
anything but the market-data WebSocket handshake (research/kauth.headers) and public GETs of /markets (kauth.get,
unauthenticated).  Runtime guards: the WebSocket client refuses any command other than subscribe/unsubscribe on the
four market-data channels; the REST wrapper refuses any path outside /markets and paces calls >= 3 s apart.  The
self-test scans this file, bettor_paper.py and kauth.py for order endpoints / write verbs and checks the guards.

WHAT IT DOES (each arm is an independent virtual book of orders on the same feed)
  Feed: one WebSocket of its own (index prints for the 9 coins, orderbook_delta + trade for the 9 nearest 15-min
  markets, market_lifecycle_v2), with the v-fresh-book subscription-id fix (ids allocated under a lock and recorded
  BEFORE the request is sent, so a reconnect can never unsubscribe its own fresh book).  Settlement from GET
  /markets/<ticker> (bettor_paper.Rest).  Model = the live forecaster's P(YES) exactly as bettor_paper.Engine.forecaster
  computes it (blendvr sigma, TRAIN vr / z-scale / calibration from bettor_paper_models.json), every second.
  Rule (every arm): each second rel = -29..-1, once the print stamped close+rel is received (>= +0.2 s), a target is
  chosen from the book seen then: favourite side by the arm's probability p_side >= 0.55; price = floor_to_tick(p_side
  - margin), no bid when that is >= 90c (C90), at least one tick under the ask, none under 50c, none once the side holds
  23 contracts, none on the other side once a side filled (one side per market).  The order lands `land` seconds later
  (place / move = cancel + new at the back of the queue / cancel); post-only: refused if the ask is at or under it then.
    M300  model p, margin 7c, land 0.1 s after the decision (live 0.3 s after the print)        -- the candidate
    M500  the same, land 0.3 s after the decision (0.5 s after the print)                       -- slow landing
    NULL  the market's own mid as p, margin 0, land 0.1 s                                       -- no-model null
    M300raw  M300 without the day/run stops (context only, never in the bar)
  Guard 'pull': once live, if our side's best bid falls below the best bid we joined (or our price if lower), or the
  other side's best bid rises above its value at placement, the order is cancelled 250 ms later (fills in between count).
  FILLS ONLY ON REAL PRINTED TRADES: a trade where the taker SOLD our side AT our price first eats the size displayed
  ahead of us when we joined (cancels shrink 'ahead' only when the level drops below it -- cancels come from behind us
  first; applied 1.0 s after the book message so a trade's own book delta is never counted twice), the rest fills us;
  a trade BELOW our price fills us up to its size.  Cross fills off.  Receive time orders every event.
  Stops (arms M300 / M500 / NULL): realized P&L in an ET day (UTC-4, as the live bot) <= -$28.87 -> no new orders that
  ET day; since start (or the last simulated restart) <= -$45.24 -> run stop, halted for the rest of that ET day, then a
  simulated operator restart (run P&L reset; every run stop is counted).  P&L held to settlement, maker fee 0 (the
  0.0175 quadratic alt fee is logged beside it).
  Book health: a seq gap or a socket drop unsyncs every book and cancels every virtual order; a trade with no book
  message from 1 s before to 2 s after it marks the market STALE (orders cancelled, flagged, resubscribe <= every 10 s).

LOG  C:\kals-repo\results\fc-maker-paper.jsonl -- the only results path it writes.  Records: start, fill, mk (one per
  arm per market it bid on, at settlement), close (one per close: per-coin coverage and vol ratio, per arm P&L, cost,
  cash locked, writes per second rel -30..-1), day_stop / run_stop / run_restart, stale, unsync, health (5 min), stop,
  plus the feed's ws_* / *_error records.

USAGE
  python -u research\cleanroom\fc_maker_paper.py --selftest          # planted worlds + no-order proof, then exit
  python -u research\cleanroom\fc_maker_paper.py --minutes 21600     # self-test, then the paper run (15 days)
  python -u research\cleanroom\fc_maker_paper.py --read [--log PATH] [--asof ISO]   # the pre-registered read
  Stop: create C:\kals-repo\results\fc-maker-paper.stop (checked every 5 s).
"""
import argparse
import ctypes
import hashlib
import heapq
import json
import math
import os
import queue
import sys
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CLEANROOM = r"C:\kals-repo\research\cleanroom"
for _p in (CLEANROOM, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import bettor_paper as B          # noqa: E402  (model tables, Market/Engine plumbing, WS, Rest: market data only)

VERSION = "fc-maker-paper v1 2026-10-18"
LOG_PATH = r"C:\kals-repo\results\fc-maker-paper.jsonl"
STOP_FILE = r"C:\kals-repo\results\fc-maker-paper.stop"
KAUTH_DIR = r"C:\kals-repo\research"

CAP = 23                 # contracts per side per market (today's live 23 a side)
PMIN = 0.55              # favourite threshold
MINPX = 500              # no bid under 50c (prices in tenths of a cent: 1000 = $1)
CAP90 = 895              # C90: no bid when the model's price is 90c or more
REL0 = -29               # first decision second
REACT_S = 0.250          # guard cancel delay
PAIR_S = 1.0             # a level drop is applied to 'ahead' this long after its book message
STALE_PRE_S, STALE_POST_S = 1.0, 2.0
RESYNC_MIN_S = 10.0
HOLD_S = 0.03            # timers run this far behind the clock so earlier messages are always handled first
REST_GAP_S = 3.0         # >= 3 s between REST calls
DAY_STOP = -28.87
RUN_STOP = -45.24
# name, model, margin, land_s, stops
ARMS = (("M300", "p", 0.07, 0.100, True), ("M500", "p", 0.07, 0.300, True), ("NULL", "mid", 0.0, 0.100, True),
        ("M300raw", "p", 0.07, 0.100, False))
WS_CMDS = ("subscribe", "unsubscribe")
WS_CHANNELS = {"orderbook_delta", "trade", "cfbenchmarks_value", "market_lifecycle_v2"}

# ---- the pre-registered bar (written 2026-10-18 before any paper data exists; the read applies exactly this) ----------
BAR = {
    "read_due": "2026-10-29T12:00Z", "extend_to": "2026-11-02T12:00Z",
    "min_covered_days": 10, "min_calm_days": 3,
    "covered_close": ">= 7 of the 9 coins had a synced, non-stale book at >= 20 of the 29 decision seconds",
    "covered_day": ">= 87 of the ET day's 96 closes covered", "calm_day": "median rel -29 local/g vol ratio of the ET "
    "day's markets < 0.60",
    "per_day": "96 x (settled P&L after stops on covered closes, stale-flagged markets excluded) / covered closes",
    "pass": ["M300 >= +$10/day", "M300 return on money (P&L / cost of fills) >= 5%", "M500 >= +$5/day",
             "M300 - NULL >= $0/day", "M300 run stops <= 1 and longest dry spell (consecutive covered closes "
             "without an M300 fill, x 0.25 h) <= 8 h", "M300 order actions (place / cancel / move, a move counted "
             "once as one amend) <= 3/s summed over the 9 markets in >= 99% of the seconds of closes it wrote in "
             "(cancel + place counted separately is reported beside it)"],
    "kill": ["M300 total P&L <= $0", "M500 total P&L < $0", "M300 trails NULL by more than $5/day",
             "M300 run stops >= 2"],
    "unreliable_if": "stale-flagged markets hold > 10% of M300's filled markets",
    "on_pass": "operator decision on a small live probe (23 a side, run stop 0.33 x pot), live latency measured",
}


def et_day(cs):
    """ET day of a close (UTC-4 fixed, as forecaster_live.et_day), the close second itself belongs to the day before."""
    return (datetime.fromtimestamp(cs - 1, timezone.utc) - timedelta(hours=4)).strftime("%Y-%m-%d")


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mil(s):
    return int(round(float(s) * 1000))


def tick_floor(x):
    xi = int(math.floor(x + 1e-9))
    if xi >= 900 or xi < 100:
        return xi
    return (xi // 10) * 10


def tick_down(px):
    return px - (1 if (px > 900 or px <= 100) else 10)


def fee_alt(n, px):
    return math.ceil(0.0175 * n * (px / 1000.0) * (1 - px / 1000.0) * 100 - 1e-9) / 100.0


class FLog(B.Logger):
    """bettor_paper's logger, keeping only this bot's records and the feed's health records."""
    KEEP = {"start", "stop", "health", "fill", "mk", "close", "day_stop", "run_stop", "run_restart", "stale", "unsync",
            "selftest", "feed_stall", "seq_gap", "bad_market", "bad_trade", "bad_print"}

    def write(self, ev, **kw):
        if ev in self.KEEP or ev.startswith("ws_") or ev.endswith("_error"):
            B.Logger.write(self, ev, **kw)


# ------------------------------------------------------------------------------------------------- feed (market data)
class PaperWS(B.WS):
    """bettor_paper's WebSocket client with forecaster_live.FcWS's subscription-id fix, and a hard guard: only
    subscribe / unsubscribe on market-data channels can ever be sent."""

    def __init__(self, q, log, headers_fn):
        super().__init__(q, log, headers_fn)
        self._id_lock = threading.Lock()
        self._sub_conn = None

    def send_json(self, obj):
        if not isinstance(obj, dict) or obj.get("cmd") not in WS_CMDS:
            raise ValueError("paper: refused websocket command %r" % (obj.get("cmd") if isinstance(obj, dict) else obj))
        ch = (obj.get("params") or {}).get("channels")
        if ch is not None and not set(ch) <= WS_CHANNELS:
            raise ValueError("paper: refused websocket channels %r" % (ch,))
        return super().send_json(obj)

    def _new_id(self):
        with self._id_lock:
            self.next_id += 1
            return self.next_id

    def subscribe(self, channels, **params):
        i = self._new_id()
        p = {"channels": channels}
        p.update(params)
        self.send_json({"id": i, "cmd": "subscribe", "params": p})
        return i

    def unsubscribe(self, sids):
        self.send_json({"id": self._new_id(), "cmd": "unsubscribe", "params": {"sids": sids}})

    def set_markets(self, tickers):
        self.market_tickers = list(tickers)
        if not self.connected:
            return
        old = [self.sids[c] for c in ("orderbook_delta", "trade") if c in self.sids]
        for c in ("orderbook_delta", "trade"):
            self.sids.pop(c, None)
        if old:
            self.unsubscribe(old)
        with self._id_lock:
            self.market_sub_id = None
            i = None
            if self.market_tickers:
                self.next_id += 1
                i = self.market_sub_id = self.next_id
                self._sub_conn = self.reconnects
        if i is not None:
            self.send_json({"id": i, "cmd": "subscribe",
                            "params": {"channels": ["orderbook_delta", "trade"], "market_tickers": self.market_tickers}})
            self.log.write("ws_subscribe", markets=self.market_tickers, unsubscribed=old, sub_id=i)

    def _on_connect(self):
        with self._id_lock:
            self.sids = {}
            if self._sub_conn != self.reconnects:
                self.market_sub_id = None
        self.subscribe(["cfbenchmarks_value"], index_ids=self.index_ids)
        self.subscribe(["market_lifecycle_v2"])


def paced_get(get_fn, gap=None):
    """Public GET of /markets only, >= REST_GAP_S apart (Rest's thread is the only caller)."""
    last = [0.0]
    lock = threading.Lock()

    def get(path, params=None, auth=False):
        if not isinstance(path, str) or not path.startswith("/markets"):
            raise ValueError("paper: refused GET %r" % (path,))
        with lock:
            w = last[0] + (REST_GAP_S if gap is None else gap) - time.time()
            if w > 0:
                time.sleep(w)
            last[0] = time.time()
        return get_fn(path, params, auth=False)
    return get


# ---------------------------------------------------------------------------------------------- virtual order books
class MBook:
    """One market's book, bids per side in tenths of a cent (0 = YES bids, 1 = NO bids); ask(side) = 1000 - other bid."""
    __slots__ = ("L", "best", "synced", "snap_seq", "sid", "last_rx")

    def __init__(self):
        self.L = ({}, {})
        self.best = [0, 0]
        self.synced = False
        self.snap_seq = -1
        self.sid = None
        self.last_rx = 0.0

    def load(self, msg, seq, sid, rx):
        for i, k in ((0, "yes_dollars_fp"), (1, "no_dollars_fp")):
            d = self.L[i]
            d.clear()
            for p, s in msg.get(k) or []:
                q = float(s)
                if q > 0:
                    d[mil(p)] = q
            self.best[i] = max(d) if d else 0
        self.synced, self.snap_seq, self.sid, self.last_rx = True, seq, sid, rx

    def apply(self, sd, px, dq):
        d = self.L[sd]
        q = d.get(px, 0.0) + dq
        if q <= 1e-9:
            d.pop(px, None)
            if px == self.best[sd]:
                self.best[sd] = max(d) if d else 0
        else:
            d[px] = q
            if px > self.best[sd]:
                self.best[sd] = px

    def ask(self, sd):
        o = self.best[1 - sd]
        return 1000 - o if o > 0 else 1001


class Ord:
    __slots__ = ("side", "px", "rem", "ahead", "ps", "live", "jbb", "joth", "pull_at", "rel")


class AS:
    """One arm's state in one market."""
    __slots__ = ("pend", "pend_p", "ord", "filled", "fills", "lock", "writes", "places", "cancels", "pulls", "refused",
                 "max_resv", "first", "blocked", "cost")

    def __init__(self):
        self.pend = self.pend_p = self.ord = self.lock = self.first = None
        self.filled = [0.0, 0.0]
        self.fills = []
        self.writes = self.places = self.cancels = self.pulls = self.refused = 0
        self.max_resv = self.cost = 0.0
        self.blocked = False


class Arm:
    def __init__(self, name, model, margin, land, stops):
        self.name, self.model, self.m, self.land, self.stops = name, model, margin, land, stops
        self.day = {}
        self.run = 0.0
        self.cum = 0.0
        self.day_stopped = set()
        self.halt_day = None
        self.run_stops = 0

    def blocked(self, cs, log):
        if not self.stops:
            return False
        d = et_day(cs)
        if d in self.day_stopped:
            return True
        if self.halt_day is not None:
            if d <= self.halt_day:
                return True
            log.write("run_restart", arm=self.name, halted_day=self.halt_day, day=d, run_pnl=round(self.run, 4))
            self.halt_day = None
            self.run = 0.0
        return False

    def book(self, cs, pnl, log):
        self.cum += pnl
        if not self.stops:
            return
        d = et_day(cs)
        self.day[d] = self.day.get(d, 0.0) + pnl
        self.run += pnl
        if d not in self.day_stopped and self.day[d] <= DAY_STOP:
            self.day_stopped.add(d)
            log.write("day_stop", arm=self.name, day=d, close=iso(cs), day_pnl=round(self.day[d], 4))
        if self.halt_day is None and self.run <= RUN_STOP:
            self.run_stops += 1
            self.halt_day = d
            log.write("run_stop", arm=self.name, day=d, close=iso(cs), run_pnl=round(self.run, 4), n=self.run_stops)


def target(s, margin, p, bk):
    """s4_sim.target, 'fair' rule with C90: (side, price) or None."""
    if p is None:
        return None
    side, ps = (0, p) if p >= 0.5 else (1, 1.0 - p)
    if ps < PMIN:
        return None
    if s.lock is not None and side != s.lock:
        return None
    if s.filled[side] >= CAP - 1e-9:
        return None
    px = tick_floor((ps - margin) * 1000.0)
    if px > CAP90:
        return None
    ask = bk.ask(side)
    if px >= ask:
        px = tick_down(ask)
    if px < MINPX:
        return None
    return (side, px)


class Maker:
    """Every arm's virtual orders on every market; all times are receive / wall-clock seconds."""

    def __init__(self, log, arms=ARMS):
        self.log = log
        self.arms = [Arm(*a) for a in arms]
        self.books = {}
        self.st = {}
        self.mi = {}
        self.cl = {}
        self.timers = []
        self.tseq = 0
        self.wps = {}
        self.wpa = {}
        self.want_resync = False
        self.dec_lag = deque(maxlen=4000)
        self.n_stale = 0
        self.n_unsync = 0

    # --- bookkeeping --------------------------------------------------------------------------------------------------
    def market(self, tk, coin, cs):
        mi = self.mi.get(tk)
        if mi is None:
            mi = self.mi[tk] = {"coin": coin, "cs": cs, "ok": 0, "dec": 0, "ratio": None, "p29": None, "stale": 0,
                                "stale_now": False, "gap": 0, "trades": 0, "deltas": 0}
            self.books.setdefault(tk, MBook())
            c = self.cl.setdefault(cs, {"open": set(), "rows": {}, "arms": {}})
            c["open"].add(tk)
            self.at(cs, "close", tk)
        return mi

    def at(self, t, kind, *a):
        self.tseq += 1
        heapq.heappush(self.timers, (t, self.tseq, kind, a))

    def run_timers(self, t, strict):
        H = self.timers
        while H and (H[0][0] < t if strict else H[0][0] <= t):
            tt, _, kind, a = heapq.heappop(H)
            getattr(self, "_t_" + kind)(tt, *a)

    def write(self, arm, cs, s, t, action=True):
        """wps: every cancel and every place is one write; wpa: order ACTIONS (a move = one action, as one amend)."""
        s.writes += 1
        i = int(math.floor(t - cs)) + 30
        if not 0 <= i < 30:
            return
        for d, inc in ((self.wps, 1), (self.wpa, 1 if action else 0)):
            w = d.get((arm.name, cs))
            if w is None:
                w = d[(arm.name, cs)] = [0] * 30
            w[i] += inc

    def cancel(self, arm, tk, s, t, why):
        s.ord = None
        s.cancels += 1
        if why == "pull":
            s.pulls += 1
        self.write(arm, self.mi[tk]["cs"], s, t)

    def cancel_all(self, tk, t, why):
        for arm in self.arms:
            s = self.st.get((arm.name, tk))
            if s is not None and s.ord is not None:
                self.cancel(arm, tk, s, t, "pull")

    # --- decisions ----------------------------------------------------------------------------------------------------
    def on_decide(self, m, rel, p, now, ratio=None, skipped=False):
        tk = m.ticker
        mi = self.mi.get(tk) or self.market(tk, m.coin, m.close_s)
        bk = self.books[tk]
        ok = bk.synced and not mi["stale_now"]
        mi["dec"] += 1
        if ok and not skipped:
            mi["ok"] += 1
        if not skipped:
            self.dec_lag.append(now - (m.close_s + rel))
        if rel == REL0:
            mi["ratio"] = None if ratio is None else round(ratio, 4)
            mi["p29"] = None if p is None else round(p, 4)
        mid = None
        if ok and bk.best[0] > 0 and bk.best[1] > 0:
            mid = (bk.best[0] + 1000 - bk.best[1]) / 2000.0
        for arm in self.arms:
            s = self.st.get((arm.name, tk))
            if s is None:
                s = self.st[(arm.name, tk)] = AS()
            pr = p if arm.model == "p" else mid
            blk = arm.blocked(m.close_s, self.log)
            if blk:
                s.blocked = True
            s.pend = None if (not ok or blk or skipped) else target(s, arm.m, pr, bk)
            s.pend_p = pr
            self.at(now + arm.land, "land", arm, tk, rel)

    def _t_land(self, t, arm, tk, rel):
        s = self.st.get((arm.name, tk))
        mi = self.mi.get(tk)
        if s is None or mi is None or t >= mi["cs"]:
            return
        bk = self.books[tk]
        tg = s.pend
        o = s.ord
        moved = False
        if o is not None and (tg is None or (o.side, o.px) != tg):
            self.cancel(arm, tk, s, t, "move" if tg else "none")
            o = None
            moved = tg is not None
        if tg is None or o is not None or not bk.synced or mi["stale_now"]:
            return
        sd, px = tg
        if px >= bk.ask(sd):
            s.refused += 1                            # post-only would be refused: nothing rests
            return
        rem = CAP - s.filled[sd]
        if rem <= 1e-9:
            return
        o = Ord()
        o.side, o.px, o.rem, o.ahead = sd, px, rem, bk.L[sd].get(px, 0.0)
        o.ps = None if s.pend_p is None else round(s.pend_p if sd == 0 else 1.0 - s.pend_p, 4)
        o.live, o.jbb, o.joth, o.pull_at, o.rel = t, min(bk.best[sd], px), bk.best[1 - sd], None, rel
        s.ord = o
        s.places += 1
        self.write(arm, mi["cs"], s, t, action=not moved)
        if s.first is None:
            s.first = [sd, rel, o.ps, px]
        resv = rem * px / 1000.0 + s.cost
        if resv > s.max_resv:
            s.max_resv = resv

    def _t_pull(self, t, arm, tk, o):
        s = self.st.get((arm.name, tk))
        if s is not None and s.ord is o and o.pull_at == t and tk in self.mi:
            self.cancel(arm, tk, s, t, "pull")

    def _t_cap(self, t, arm, tk, o):
        s = self.st.get((arm.name, tk))
        bk = self.books.get(tk)
        if s is None or s.ord is not o or bk is None:
            return
        q = bk.L[o.side].get(o.px, 0.0)
        if o.ahead > q:
            o.ahead = q

    def _t_close(self, t, tk):
        for arm in self.arms:
            s = self.st.get((arm.name, tk))
            if s is not None:
                s.ord = None                          # expired at the close (no write)

    def _t_stalechk(self, t, tk, trade_rx):
        bk = self.books.get(tk)
        mi = self.mi.get(tk)
        if bk is None or mi is None or not bk.synced or bk.last_rx >= trade_rx - STALE_PRE_S:
            return
        mi["stale"] += 1
        mi["stale_now"] = True
        bk.synced = False
        self.n_stale += 1
        self.cancel_all(tk, t, "stale")
        self.want_resync = True
        self.log.write("stale", ticker=tk, trade_rx=round(trade_rx, 3), last_book_rx=round(bk.last_rx, 3),
                       to_close_s=round(mi["cs"] - t, 2))

    # --- feed ---------------------------------------------------------------------------------------------------------
    def on_snapshot(self, tk, msg, seq, sid, rx):
        bk = self.books.get(tk)
        mi = self.mi.get(tk)
        if bk is None or mi is None:
            return
        bk.load(msg, seq, sid, rx)
        mi["stale_now"] = False
        self.guard(tk, bk, rx)

    def on_delta(self, tk, msg, seq, sid, rx):
        bk = self.books.get(tk)
        if bk is None or not bk.synced or seq <= bk.snap_seq or sid != bk.sid:
            return
        mi = self.mi[tk]
        sd = 0 if msg["side"] == "yes" else 1
        px = mil(msg["price_dollars"])
        dq = float(msg["delta_fp"])
        b0 = bk.best[sd]
        bk.apply(sd, px, dq)
        bk.last_rx = rx
        mi["deltas"] += 1
        if rx >= mi["cs"]:
            return
        if dq < 0:
            for arm in self.arms:
                s = self.st.get((arm.name, tk))
                o = None if s is None else s.ord
                if o is not None and o.side == sd and o.px == px and o.live <= rx and o.ahead > bk.L[sd].get(px, 0.0):
                    self.at(rx + PAIR_S, "cap", arm, tk, o)
        if bk.best[sd] != b0:
            self.guard(tk, bk, rx)

    def guard(self, tk, bk, rx):
        for arm in self.arms:
            s = self.st.get((arm.name, tk))
            o = None if s is None else s.ord
            if o is None or o.pull_at is not None or o.live > rx:
                continue
            if bk.best[o.side] < o.jbb or bk.best[1 - o.side] > o.joth:
                o.pull_at = rx + REACT_S
                self.at(o.pull_at, "pull", arm, tk, o)

    def on_trade(self, tk, msg, rx):
        mi = self.mi.get(tk)
        if mi is None:
            return
        mi["trades"] += 1
        bk = self.books[tk]
        if bk.synced and bk.last_rx < rx - STALE_PRE_S:
            self.at(rx + STALE_POST_S, "stalechk", tk, rx)
        if rx >= mi["cs"]:
            return
        try:
            yp = mil(msg["yes_price_dollars"])
            cnt = float(msg["count_fp"])
            tsd = msg["taker_side"]
        except Exception:
            return
        if tsd == "no":
            sd, px = 0, yp                          # taker bought NO = sold YES into the YES bids
        elif tsd == "yes":
            sd, px = 1, 1000 - yp
        else:
            return
        for arm in self.arms:
            s = self.st.get((arm.name, tk))
            o = None if s is None else s.ord
            if o is None or o.side != sd or o.live > rx:
                continue
            if px == o.px:
                a = o.ahead if o.ahead < cnt else cnt
                o.ahead -= a
                self.fill(arm, tk, s, cnt - a, rx, "queue", msg)
            elif px < o.px:
                self.fill(arm, tk, s, cnt, rx, "through", msg)

    def fill(self, arm, tk, s, n, t, kind, msg):
        o = s.ord
        if n <= 1e-9:
            return
        if n > o.rem:
            n = o.rem
        o.rem -= n
        s.filled[o.side] += n
        s.lock = o.side
        s.cost += n * o.px / 1000.0
        cs = self.mi[tk]["cs"]
        s.fills.append([o.side, o.px, round(n, 2), round((t - cs) * 1000), kind, o.ps])
        self.log.write("fill", arm=arm.name, ticker=tk, side="yes" if o.side == 0 else "no", px=o.px, n=round(n, 2),
                       kind=kind, ms_to_close=round((t - cs) * 1000), live_ms=round((t - o.live) * 1000),
                       ahead_left=round(o.ahead, 2), ps=o.ps, trade_ts_ms=msg.get("ts_ms"), rx_ms=round(t * 1000))
        if o.rem <= 1e-9:
            s.ord = None

    def unsync_all(self, t, why):
        n = 0
        for tk, bk in self.books.items():
            if bk.synced:
                bk.synced = False
                n += 1
            mi = self.mi.get(tk)
            if mi is not None and mi["cs"] - 30 <= t < mi["cs"]:
                mi["gap"] += 1
            self.cancel_all(tk, t, why)
        self.n_unsync += 1
        self.log.write("unsync", why=why, books=n)

    # --- settlement ---------------------------------------------------------------------------------------------------
    def settle(self, tk, result, now):
        mi = self.mi.pop(tk, None)
        self.books.pop(tk, None)
        if mi is None:
            return
        cs = mi["cs"]
        c = self.cl.get(cs)
        for arm in self.arms:
            s = self.st.pop((arm.name, tk), None)
            if s is None:
                continue
            pnl = 0.0
            n = 0.0
            fa = 0.0
            for sd, px, k, ms, kind, ps in s.fills:
                won = (result == "yes") == (sd == 0)
                pnl += k * ((1000 - px) if won else -px) / 1000.0
                n += k
                fa += fee_alt(k, px)
            if result not in ("yes", "no"):
                pnl = None if n > 0 else 0.0
            if pnl:
                arm.book(cs, pnl, self.log)
            if c is not None:
                a = c["arms"].setdefault(arm.name, {"pnl": 0.0, "pnl_ok": 0.0, "cost": 0.0, "filled": [], "lost": 0,
                                                     "locked": 0.0, "bids": 0, "pulls": 0, "refused": 0})
                if pnl is not None:
                    a["pnl"] += pnl
                    if not mi["stale"]:
                        a["pnl_ok"] += pnl
                a["cost"] += s.cost
                a["locked"] += s.max_resv
                a["pulls"] += s.pulls
                a["refused"] += s.refused
                if s.places:
                    a["bids"] += 1
                if n > 0:
                    a["filled"].append(mi["coin"])
                    if pnl is not None and pnl < 0:
                        a["lost"] += 1
            if s.places or s.fills or s.refused:
                self.log.write("mk", arm=arm.name, ticker=tk, coin=mi["coin"], close=iso(cs), cs=cs, result=result,
                               n=round(n, 2), cost=round(s.cost, 4), pnl=None if pnl is None else round(pnl, 4),
                               fee_alt=round(fa, 2), fills=s.fills, first=s.first, writes=s.writes, places=s.places,
                               cancels=s.cancels, pulls=s.pulls, refused=s.refused, max_resv=round(s.max_resv, 2),
                               blocked=s.blocked, stale=mi["stale"], gap=mi["gap"], ratio=mi["ratio"], p29=mi["p29"])
        if c is None:
            return
        c["rows"][mi["coin"]] = [mi["ok"], mi["dec"], mi["ratio"], result, mi["stale"], mi["gap"], mi["trades"],
                                 mi["deltas"]]
        c["open"].discard(tk)
        if c["open"]:
            return
        del self.cl[cs]
        cov = sum(1 for r in c["rows"].values() if r[0] >= 20 and not r[4])
        arms = {}
        for arm in self.arms:
            a = c["arms"].get(arm.name) or {"pnl": 0.0, "pnl_ok": 0.0, "cost": 0.0, "filled": [], "lost": 0,
                                             "locked": 0.0, "bids": 0, "pulls": 0, "refused": 0}
            for k in ("pnl", "pnl_ok", "cost", "locked"):
                a[k] = round(a[k], 4)
            a["wps"] = self.wps.pop((arm.name, cs), [0] * 30)
            a["wpa"] = self.wpa.pop((arm.name, cs), [0] * 30)
            a["day_pnl"] = round(arm.day.get(et_day(cs), 0.0), 4)
            a["run_pnl"] = round(arm.run, 4)
            a["cum"] = round(arm.cum, 4)
            a["halted"] = bool(arm.stops and (et_day(cs) in arm.day_stopped or arm.halt_day is not None))
            arms[arm.name] = a
        self.log.write("close", close=iso(cs), cs=cs, et_day=et_day(cs), covered=cov >= 7, coins_ok=cov,
                       markets=c["rows"], arms=arms)


# ------------------------------------------------------------------------------------------------------------ engine
class MakerEngine(B.Engine):
    """bettor_paper's engine for prints / markets / settlement, no paper strategy of its own; each second from rel -29 it
    computes the live forecaster's probability and hands it to the Maker."""

    def __init__(self, log, now_fn, tables, mk):
        super().__init__(log, now_fn, tables, strats=())
        self.mk = mk

    def add_market(self, ticker, coin, close_s, strike, round_digits, strike_src):
        m = super().add_market(ticker, coin, close_s, strike, round_digits, strike_src)
        if m is not None:
            self.mk.market(m.ticker, m.coin, m.close_s)
        return m

    def model_p(self, m, rel, pr):
        """(P(YES), local/g ratio) exactly as bettor_paper.Engine.forecaster computes p (no r gate)."""
        v = pr[0]
        if m.thr is None:
            return None, None
        d = self.prints.get(m.index_id, {})
        stamp = m.close_s + rel
        lo = m.close_s - 60
        got = [d[s][0] for s in range(lo, stamp + 1) if s in d]
        if len(got) < stamp - lo + 1:
            return None, None
        r = 60 - len(got)
        proj = (sum(got) + r * v) / 60.0
        loc = self.f_local_sigma(m.index_id, stamp)
        g = self.tb.f_sigma.get(m.coin)
        ratio = (loc / g) if (loc is not None and g) else None
        if rel == -1:
            em = self.exact_mean(m)
            if em is None:
                return None, ratio
            p = 1.0 if em >= m.thr else 0.0
        else:
            s = self.tb.f_sig(m.coin, r, loc)
            if s is None:
                return None, ratio
            sd = v * s * math.sqrt(B.s_coef(rel)) / 60.0
            p = (1.0 if proj >= m.thr_f else 0.0) if sd <= 0 else 1.0 - B.phi((m.thr_f - proj) / sd)
        return self.tb.f_calibrate(p, r), ratio

    def tick(self):
        now = self.now()
        for m in list(self.markets.values()):
            if m.done:
                continue
            if now >= m.close_s:
                m.done = True
                continue
            if m.next_rel < REL0:
                m.next_rel = REL0
            while m.next_rel <= -1:
                rel = m.next_rel
                if now < m.close_s + rel + B.DECIDE_OFFSET:
                    break
                pr = self.prints.get(m.index_id, {}).get(m.close_s + rel)
                if pr is not None and pr[2] <= now:
                    p, ratio = self.model_p(m, rel, pr)
                    self.mk.on_decide(m, rel, p, now, ratio)
                    m.next_rel += 1
                elif now > m.close_s + rel + B.DECIDE_DEADLINE:
                    self.mk.on_decide(m, rel, None, now, None, skipped=True)
                    m.next_rel += 1
                else:
                    break

    def on_result(self, ticker, result, expiration_value, now):
        m = self.markets.get(ticker)
        was = m is not None and not m.settled
        super().on_result(ticker, result, expiration_value, now)
        if was and m.settled:
            self.mk.settle(ticker, result if result in ("yes", "no") else None, now)


# -------------------------------------------------------------------------------------------------------------- live
def src_sha():
    with open(os.path.abspath(__file__), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def run(minutes, log_path=LOG_PATH, health_s=300.0):
    try:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL
    except Exception:
        pass
    if os.path.exists(STOP_FILE):
        raise SystemExit("stop file present: %s" % STOP_FILE)
    if KAUTH_DIR not in sys.path:
        sys.path.insert(0, KAUTH_DIR)
    import kauth                                      # WebSocket handshake signature + public GET only
    log = FLog(log_path)
    q = queue.Queue()
    mk = Maker(log)
    eng = MakerEngine(log, time.time, B.Tables(), mk)
    ws = PaperWS(q, log, kauth.headers)
    ws.index_ids = [B.COINS[c][1] for c in B.COINS]
    rest = B.Rest(q, log, paced_get(kauth.get))
    log.write("start", pid=os.getpid(), version=VERSION, sha256=src_sha(), minutes=minutes,
              python=sys.version.split()[0], rss_mb=B.rss_mb(), arms=[list(a) for a in ARMS], cap=CAP, pmin=PMIN,
              minpx=MINPX, cap90=CAP90, rel0=REL0, react_s=REACT_S, pair_s=PAIR_S, day_stop=DAY_STOP,
              run_stop=RUN_STOP, rest_gap_s=REST_GAP_S, bar=BAR)
    ws.start()
    rest.start()
    t_end = time.time() + minutes * 60
    last_health = last_stopchk = time.time()
    cpu0 = time.process_time()
    last_active = None
    last_resync = 0.0
    seq_last = {}
    trade_gaps = 0
    n_msgs = {}
    asked = set()
    loop_lag = 0.0
    t_prev = last_rx = last_print = last_kick = time.time()
    final = False
    PRINT_STALL_S = 30.0
    while time.time() < t_end:
        drained = 0
        while drained < 5000:
            try:
                rx, obj = q.get_nowait()
            except queue.Empty:
                break
            drained += 1
            last_rx = rx
            if mk.timers:
                mk.run_timers(rx, True)
            t = obj.get("type")
            n_msgs[t] = n_msgs.get(t, 0) + 1
            try:
                if t == "orderbook_delta":
                    sid, seq = obj.get("sid"), obj.get("seq")
                    exp = seq_last.get(sid)
                    seq_last[sid] = seq
                    if exp is not None and seq != exp + 1:
                        log.write("seq_gap", sid=sid, expected=exp + 1, got=seq)
                        mk.unsync_all(rx, "seq_gap")
                        eng.resync_wanted = True
                    else:
                        mk.on_delta(obj["msg"]["market_ticker"], obj["msg"], seq, sid, rx)
                elif t == "trade":
                    sid, seq = obj.get("sid"), obj.get("seq")
                    exp = seq_last.get(sid)
                    if exp is not None and seq != exp + 1:
                        trade_gaps += 1
                    seq_last[sid] = seq
                    mk.on_trade(obj["msg"]["market_ticker"], obj["msg"], rx)
                elif t == "cfbenchmarks_value":
                    last_print = rx
                    msg = obj["msg"]
                    data = json.loads(msg["data"])
                    eng.on_print(msg["index_id"], int(data["time"]), data["value"], rx)
                elif t == "orderbook_snapshot":
                    sid, seq = obj.get("sid"), obj.get("seq")
                    seq_last[sid] = seq
                    mk.on_snapshot(obj["msg"]["market_ticker"], obj["msg"], seq, sid, rx)
                elif t == "_rest_markets":
                    for coin, mkt in obj["markets"]:
                        try:
                            args = B.market_from_rest(coin, mkt, obj["doge_prev"], eng.last_expiration)
                            if args[2] - time.time() < 1800:
                                eng.add_market(*args)
                        except Exception as e:
                            log.write("bad_market", ticker=mkt.get("ticker"), err=str(e)[:200])
                elif t == "_rest_result":
                    eng.on_result(obj["ticker"], obj["result"], obj["expiration_value"], time.time())
                    asked.discard(obj["ticker"])
                elif t == "_ws_up":
                    seq_last = {}
                    mk.unsync_all(rx, "ws_up")
                    last_active = None
                elif t == "_ws_down":
                    mk.unsync_all(rx, "ws_down")
                elif t == "error":
                    log.write("ws_error_msg", msg=obj.get("msg"))
            except Exception as e:
                log.write("msg_error", type=t, err=repr(e)[:300])
        now = time.time()
        loop_lag = max(loop_lag, now - t_prev)
        t_prev = now
        try:
            mk.run_timers(now - HOLD_S, False)
            eng.tick()
        except Exception as e:
            log.write("tick_error", err=repr(e)[:300])
        active = eng.active_tickers(now)
        resync = (eng.resync_wanted or mk.want_resync) and now - last_resync > RESYNC_MIN_S
        if ws.connected and (active != last_active or resync):
            if resync:
                eng.resync_wanted = mk.want_resync = False
                last_resync = now
            last_active = active
            ws.set_markets(active)
        for m in eng.markets_needing_result(now):
            if m.ticker not in asked:
                m.settle_asked_at = now
                asked.add(m.ticker)
                rest.settle_jobs.put(m.ticker)
        if now - last_stopchk >= 5:
            last_stopchk = now
            if os.path.exists(STOP_FILE):
                log.write("stop", reason="stop file")
                return 0
        if ws.connected and now - last_print > PRINT_STALL_S and now - last_kick > 60:
            last_kick = now                               # feed watchdog: no index print for 30 s -> reconnect
            log.write("feed_stall", print_age_s=round(now - last_print, 1), msg_age_s=round(now - last_rx, 1))
            try:
                sk = ws.sock
                if sk is not None:
                    sk.close()
            except Exception as e:
                log.write("feed_stall_error", err=repr(e)[:200])
        last_end = now >= t_end - 0.1 and not final
        if now - last_health >= health_s or last_end:
            final = final or last_end
            cpu = time.process_time()
            lags = sorted(mk.dec_lag)

            def pct(p):
                return round(1000 * lags[min(len(lags) - 1, int(p * len(lags)))]) if lags else None
            log.write("health", ws=ws.connected, reconnects=max(ws.reconnects, 0), rss_mb=B.rss_mb(),
                      cpu_pct=round(100 * (cpu - cpu0) / (now - last_health), 2), msgs=n_msgs, queue=q.qsize(),
                      markets=len(eng.markets), books_synced=sum(1 for b in mk.books.values() if b.synced),
                      decide_lag_ms={"p50": pct(0.5), "p99": pct(0.99), "n": len(lags)}, timers=len(mk.timers),
                      loop_lag_ms=round(1000 * loop_lag), trade_seq_gaps=trade_gaps, stale=mk.n_stale,
                      unsync=mk.n_unsync, cum={a.name: round(a.cum, 4) for a in mk.arms},
                      run_stops={a.name: a.run_stops for a in mk.arms}, last_msg_age_s=round(now - last_rx, 2),
                      reader_alive=ws.thread.is_alive(), rest_alive=rest.thread.is_alive(), sids=dict(ws.sids),
                      market_sub_id=ws.market_sub_id)
            cpu0, last_health, n_msgs, loop_lag = cpu, now, {}, 0.0
        time.sleep(0.02)
    ws.stop = True
    rest.stop = True
    log.write("stop", reason="minutes_elapsed")
    return 0


# -------------------------------------------------------------------------------------------------------------- read
def read_report(recs, asof=None):
    """The pre-registered read over the records of results/fc-maker-paper.jsonl."""
    closes = {}
    stops = {"run_stop": {}, "day_stop": {}}
    starts = []
    for r in recs:
        ev = r.get("ev")
        if ev == "close":
            closes[r["cs"]] = r
        elif ev in stops:
            stops[ev][r["arm"]] = stops[ev].get(r["arm"], 0) + 1
        elif ev == "start":
            starts.append(r.get("t"))
    if asof is None:
        asof = time.time()
    css = sorted(cs for cs in closes if cs <= asof)
    cov = [cs for cs in css if closes[cs]["covered"]]
    days = {}
    for cs in css:
        d = days.setdefault(et_day(cs), {"covered": 0, "ratios": []})
        if closes[cs]["covered"]:
            d["covered"] += 1
        d["ratios"] += [row[2] for row in closes[cs]["markets"].values() if row[2] is not None]
    cov_days, calm_days = [], []
    for d, v in sorted(days.items()):
        if v["covered"] >= 87:
            cov_days.append(d)
            rr = sorted(v["ratios"])
            if rr and rr[len(rr) // 2] < 0.60:
                calm_days.append(d)
    out = {"asof": iso(asof), "starts": starts, "closes": len(css), "covered_closes": len(cov),
           "covered_days": cov_days, "calm_days": calm_days, "arms": {}}
    n = max(1, len(cov))
    for arm in ("M300", "M500", "NULL", "M300raw"):
        pnl = cost = 0.0
        filled = lost = stale_mk = 0
        best = run_ = 0
        prev = None
        wsec = wbad = wbad_raw = wmax = 0
        for cs in cov:
            a = closes[cs]["arms"].get(arm)
            if a is None:
                continue
            pnl += a["pnl_ok"]
            cost += a["cost"]
            filled += len(a["filled"])
            lost += a["lost"]
            stale_mk += sum(1 for c in a["filled"] if (closes[cs]["markets"].get(c) or [0, 0, 0, 0, 0])[4])
            if prev is not None and cs - prev > 900:
                run_ = 0
            if a["filled"]:
                run_ = 0
            else:
                run_ += 1
                best = max(best, run_)
            prev = cs
            wa = a.get("wpa", a["wps"])
            if sum(wa):
                wsec += len(wa)
                wbad += sum(1 for x in wa if x > 3)
                wbad_raw += sum(1 for x in a["wps"] if x > 3)
                wmax = max(wmax, max(wa))
        out["arms"][arm] = {"pnl": round(pnl, 2), "per_day": round(96 * pnl / n, 2), "cost": round(cost, 2),
                            "roi_pct": round(100 * pnl / cost, 2) if cost else None, "filled_markets": filled,
                            "lost_markets": lost, "stale_filled_markets": stale_mk,
                            "run_stops": stops["run_stop"].get(arm, 0), "day_stops": stops["day_stop"].get(arm, 0),
                            "dry_h": round(best * 0.25, 2),
                            "writes_ok_share": round(1 - wbad / wsec, 4) if wsec else 1.0, "write_seconds": wsec,
                            "writes_ok_share_cancel_plus_place": round(1 - wbad_raw / wsec, 4) if wsec else 1.0,
                            "max_actions_per_s": wmax}
    A = out["arms"]
    m3, m5, nu = A["M300"], A["M500"], A["NULL"]
    diff = round(m3["per_day"] - nu["per_day"], 2)
    passes = [m3["per_day"] >= 10, (m3["roi_pct"] or 0) >= 5, m5["per_day"] >= 5, diff >= 0,
              m3["run_stops"] <= 1 and m3["dry_h"] <= 8, m3["writes_ok_share"] >= 0.99]
    kills = [m3["pnl"] <= 0, m5["pnl"] < 0, diff < -5, m3["run_stops"] >= 2]
    enough = len(cov_days) >= BAR["min_covered_days"] and len(calm_days) >= BAR["min_calm_days"]
    due = datetime.strptime(BAR["read_due"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc).timestamp()
    ext = datetime.strptime(BAR["extend_to"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc).timestamp()
    if asof < due:
        verdict = "EARLY (not due before %s; interim numbers only)" % BAR["read_due"]
    elif any(kills) and (enough or asof >= ext):
        verdict = "KILL"
    elif not enough and asof < ext:
        verdict = "EXTEND to %s (covered days %d/%d, calm %d/%d)" % (BAR["extend_to"], len(cov_days),
                                                                      BAR["min_covered_days"], len(calm_days),
                                                                      BAR["min_calm_days"])
    elif any(kills):
        verdict = "KILL"
    elif all(passes) and enough:
        verdict = "PASS -> operator decision on a small live probe"
    else:
        verdict = "NO PASS (no kill; no live probe)"
    out.update({"m300_minus_null_per_day": diff, "pass_checks": passes, "kill_checks": kills, "enough_data": enough,
                "unreliable": m3["filled_markets"] > 0 and m3["stale_filled_markets"] > 0.10 * m3["filled_markets"],
                "verdict": verdict})
    return out


def read_main(path, asof):
    recs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                recs.append(json.loads(line))
            except Exception:
                pass
    t = None
    if asof:
        t = datetime.strptime(asof, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc).timestamp()
    rep = read_report(recs, t)
    A = rep["arms"]
    print("fc-maker-paper read as of %s: %d closes, %d covered; covered ET days %d (calm %d)" % (
        rep["asof"], rep["closes"], rep["covered_closes"], len(rep["covered_days"]), len(rep["calm_days"])))
    for k, a in A.items():
        print("  %-8s $%8.2f  %+7.2f $/day  ROI %s%%  filled %d lost %d  run stops %d day stops %d  dry %.2f h  "
              "writes<=3/s %.2f%%" % (k, a["pnl"], a["per_day"], a["roi_pct"], a["filled_markets"], a["lost_markets"],
                                      a["run_stops"], a["day_stops"], a["dry_h"], 100 * a["writes_ok_share"]))
    print("  M300 - NULL %+.2f $/day | pass %s | kill %s | unreliable %s" % (
        rep["m300_minus_null_per_day"], rep["pass_checks"], rep["kill_checks"], rep["unreliable"]))
    print("VERDICT:", rep["verdict"])
    print(json.dumps(rep, separators=(",", ":")))
    return 0


# ---------------------------------------------------------------------------------------------------------- self-test
def selftest(verbose=False):
    fails = []
    n = [0]

    def check(c, what):
        n[0] += 1
        if not c:
            fails.append(what)

    # 1. no order code anywhere this process can run
    import re
    verbs = re.compile(r"\b(%s)\b" % "|".join(["PO" + "ST", "P" + "UT", "DEL" + "ETE", "PAT" + "CH"]))
    toks = ["portfolio/" + "orders", "/port" + "folio", "create_" + "order", "ord" + "ercli", "amend_" + "order",
            "batch_" + "create", "cancel_" + "order"]
    for path in (os.path.abspath(__file__), B.__file__, os.path.join(KAUTH_DIR, "kauth.py")):
        with open(path, encoding="utf-8") as f:
            src = f.read()
        for tk in toks:
            check(src.count(tk) == 0, "%s contains %r" % (os.path.basename(path), tk))
        check(not verbs.search(src), "%s contains an HTTP write verb" % os.path.basename(path))
    check(not ({"order" + "cli", "pintake", "forecaster_live", "fc_variants"} & set(sys.modules)), "order modules loaded")

    # 2. runtime guards: websocket commands, channels, REST paths; the subscription-id fix
    sink = []
    lg = B.Logger(sink=sink)
    ws = PaperWS(queue.Queue(), lg, lambda m, p: {})
    for bad in ({"id": 1, "cmd": "order", "params": {}}, {"id": 1, "cmd": "subscribe", "params": {"channels": ["fill"]}},
                {"id": 1, "cmd": "subscribe", "params": {"channels": ["orderbook_delta", "user_orders"]}}, "x"):
        try:
            ws.send_json(bad)
            check(False, "websocket guard let %r through" % (bad,))
        except ValueError:
            check(True, "")
        except Exception as e:
            check(False, "websocket guard crashed on %r: %r" % (bad, e))
    check(ws.send_json({"id": 2, "cmd": "subscribe", "params": {"channels": ["trade"]}}) is False,
          "allowed command reaches the (absent) socket")
    ws.connected = True
    ws.set_markets(["KXBTC15M-X"])
    sub = [r for r in sink if r["ev"] == "ws_subscribe"]
    check(len(sub) == 1 and sub[0]["sub_id"] == ws.market_sub_id and ws.market_sub_id is not None,
          "subscription id recorded before the request")
    g = paced_get(lambda p, q, auth=True: (200, {"path": p, "auth": auth}), gap=0)
    try:
        g("/port" + "folio/balance")
        check(False, "REST guard let a non-market path through")
    except ValueError:
        check(True, "")
    check(g("/markets", {"series_ticker": "KXBTC15M"}) == (200, {"path": "/markets", "auth": False}),
          "REST /markets unauthenticated")

    # 3. the model is bettor_paper's forecaster probability
    T0 = 1_800_000_000
    cs0 = T0 + 900
    clock = [cs0 - 20 + 0.25]
    tb = B.Tables()
    base = B.Engine(B.Logger(sink=[]), lambda: clock[0], tb, strats=("forecaster",))
    mk = Maker(B.Logger(sink=[]))
    me = MakerEngine(B.Logger(sink=[]), lambda: clock[0], tb, mk)
    for e in (base, me):
        e.add_market("KXBTC15M-T", "BTC", cs0, B.Decimal("100000.00"), 2, "custom_strike")
        for s in range(cs0 - 200, cs0 - 19):
            v = "%.2f" % (100000 + 30 * math.sin(s / 7.0) + 0.4 * (s - cs0 + 60))
            e.on_print("BRTI", s * 1000, v, s + 0.1)
    for rel in (-25, -20):
        m1, m2 = base.markets["KXBTC15M-T"], me.markets["KXBTC15M-T"]
        pr = me.prints["BRTI"][cs0 + rel]
        d = base.prints["BRTI"]
        got = [d[s][0] for s in range(cs0 - 60, cs0 + rel + 1)]
        r = 60 - len(got)
        proj = (sum(got) + r * pr[0]) / 60.0
        pb = base.forecaster(m1, rel, pr[0], proj, r, None, None, clock[0])["p"]
        pm, _ = me.model_p(m2, rel, pr)
        check(pm is not None and abs(pm - pb) < 1e-6, "model p %s != bettor_paper p %s at rel %d" % (pm, pb, rel))

    # 4. planted fill worlds
    def world(arms=(("T", "p", 0.07, 0.100, True),), yes=((850, 10),), no=((100, 50),), cs=cs0):
        lg_ = B.Logger(sink=[])
        mk_ = Maker(lg_, arms)
        tk = "KXBTC15M-W%d" % cs
        mk_.market(tk, "BTC", cs)
        snap = {"yes_dollars_fp": [["%.4f" % (p / 1000), str(q)] for p, q in yes],
                "no_dollars_fp": [["%.4f" % (p / 1000), str(q)] for p, q in no]}
        mk_.on_snapshot(tk, snap, 1, 7, cs - 40)

        class Mk:
            ticker, coin, close_s = tk, "BTC", cs
        return mk_, tk, Mk, lg_.sink

    def dec(mk_, M, rel, p, dt=0.2):
        t = M.close_s + rel + dt
        mk_.run_timers(t, True)
        mk_.on_decide(M, rel, p, t)
        return t

    def trade(mk_, tk, t, yes_px, cnt, taker):
        mk_.run_timers(t, True)
        mk_.on_trade(tk, {"yes_price_dollars": "%.4f" % (yes_px / 1000), "count_fp": str(cnt), "taker_side": taker,
                          "ts_ms": int(t * 1000)}, t)

    seqc = [10]

    def delta(mk_, tk, t, side, px, d):
        mk_.run_timers(t, True)
        seqc[0] += 1
        mk_.on_delta(tk, {"side": side, "price_dollars": "%.4f" % (px / 1000), "delta_fp": str(d)}, seqc[0], 7, t)

    def st(mk_, tk, arm="T"):
        return mk_.st[(arm, tk)]

    # A: front of the queue fills on a trade at our price; nothing before the order is live; through fill; cap 23
    mk_, tk, M, sk = world()
    t = dec(mk_, M, -29, 0.95)                               # cap 88c, ask 90c -> 88c
    trade(mk_, tk, t + 0.05, 880, 5, "no")                   # before it lands: no fill
    mk_.run_timers(t + 0.1, False)
    o = st(mk_, tk).ord
    check(o is not None and (o.side, o.px, o.ahead) == (0, 880, 0.0), "A: order 88c yes, nobody ahead")
    trade(mk_, tk, t + 0.15, 880, 5, "no")
    trade(mk_, tk, t + 0.16, 880, 5, "yes")                  # taker bought YES: hits NO bids, not ours
    trade(mk_, tk, t + 0.2, 870, 30, "no")                   # through
    s = st(mk_, tk)
    check([f[2] for f in s.fills] == [5, 18] and [f[4] for f in s.fills] == ["queue", "through"], "A: fills %s" % s.fills)
    check(s.filled[0] == 23 and s.ord is None, "A: 23 a side, then the order is gone")
    t2 = dec(mk_, M, -28, 0.95)
    mk_.run_timers(t2 + 0.2, False)
    check(st(mk_, tk).ord is None, "A: no order once the side is full")

    # B: queue ahead, trade-delta pairing (either order), cancels shrink ahead only below it
    mk_, tk, M, sk = world(yes=((880, 10), (850, 5)))
    t = dec(mk_, M, -29, 0.95)
    mk_.run_timers(t + 0.1, False)
    check(st(mk_, tk).ord.ahead == 10, "B: 10 ahead")
    trade(mk_, tk, t + 0.2, 880, 6, "no")                    # eats 6 of the 10 ahead
    delta(mk_, tk, t + 0.21, "yes", 880, -6)                 # its own book delta (after the trade)
    delta(mk_, tk, t + 0.40, "yes", 880, -3)                 # a trade's delta arriving BEFORE the trade
    trade(mk_, tk, t + 0.45, 880, 3, "no")
    mk_.run_timers(t + 1.6, False)
    s = st(mk_, tk)
    check(not s.fills and abs(s.ord.ahead - 1) < 1e-9, "B: ahead 1 and no fill (got %s, %s)" % (s.ord.ahead, s.fills))
    delta(mk_, tk, t + 1.7, "yes", 880, -1)                  # a cancel: the level drops to 0 < ahead
    trade(mk_, tk, t + 1.9, 880, 2, "no")                    # within PAIR_S: ahead still 1 -> fill 1
    mk_.run_timers(t + 2.8, False)
    check([f[2] for f in s.fills] == [1] and s.pulls == 1, "B: fills %s pulls %d" % (s.fills, s.pulls))

    # C: pull guard: our side's best bid falls below the one we joined -> cancelled 250 ms later, fills in between count
    mk_, tk, M, sk = world(yes=((870, 5),))
    t = dec(mk_, M, -29, 0.95)
    mk_.run_timers(t + 0.1, False)
    delta(mk_, tk, t + 0.3, "yes", 870, -5)
    trade(mk_, tk, t + 0.4, 860, 4, "no")
    trade(mk_, tk, t + 0.6, 860, 4, "no")
    s = st(mk_, tk)
    check([f[2] for f in s.fills] == [4] and s.pulls == 1 and s.ord is None, "C: pull (fills %s pulls %d)" % (s.fills, s.pulls))
    mk_, tk, M, sk = world()
    t = dec(mk_, M, -29, 0.95)
    mk_.run_timers(t + 0.1, False)
    delta(mk_, tk, t + 0.3, "no", 110, 5)                    # the other side's bid rises: pull
    mk_.run_timers(t + 0.56, False)
    check(st(mk_, tk).pulls == 1, "C: other-side guard")

    # D/E: no bids at 90c+, under 50c, or under a 55% favourite; F: post-only refusal at landing
    Y, N = ((850, 10),), ((100, 50),)
    for p, yes, no, want in ((0.975, Y, N, None), (0.965, Y, N, 890), (0.56, Y, N, None), (0.52, Y, N, None),
                             (0.30, Y, N, None), (0.10, N, Y, 830)):
        mk_, tk, M, sk = world(yes=yes, no=no)
        t = dec(mk_, M, -29, p)
        mk_.run_timers(t + 0.1, False)
        o = st(mk_, tk).ord
        check((o.px if o else None) == want, "D/E: p %.3f -> %s (want %s)" % (p, o.px if o else None, want))
    mk_, tk, M, sk = world()
    t = dec(mk_, M, -29, 0.95)
    delta(mk_, tk, t + 0.05, "no", 120, 5)                   # ask drops to 88c before landing
    mk_.run_timers(t + 0.1, False)
    check(st(mk_, tk).ord is None and st(mk_, tk).refused == 1, "F: post-only refused")

    # G: one side per market; H: a move is two writes, counted in its second
    mk_, tk, M, sk = world()
    t = dec(mk_, M, -29, 0.95)
    mk_.run_timers(t + 0.1, False)
    trade(mk_, tk, t + 0.2, 880, 2, "no")
    t2 = dec(mk_, M, -28, 0.05)
    mk_.run_timers(t2 + 0.1, False)
    check(st(mk_, tk).ord is None, "G: no bid on the other side after a fill")
    mk_, tk, M, sk = world()
    t = dec(mk_, M, -29, 0.95)
    t2 = dec(mk_, M, -28, 0.96)                              # 89c
    t3 = dec(mk_, M, -27, 0.96)                              # unchanged: no write
    mk_.run_timers(t3 + 0.2, False)
    s = st(mk_, tk)
    w = mk_.wps[("T", M.close_s)]
    wa = mk_.wpa[("T", M.close_s)]
    check(s.writes == 3 and s.ord.px == 890 and w[1] == 1 and w[2] == 2 and wa[1] == 1 and wa[2] == 1,
          "H: writes %d %s %s" % (s.writes, w, wa))

    # I: M300 and M500 land at different times; NULL bids the mid
    arms = (("M300", "p", 0.07, 0.100, True), ("M500", "p", 0.07, 0.300, True), ("NULL", "mid", 0.0, 0.100, True))
    mk_, tk, M, sk = world(arms=arms)
    t = dec(mk_, M, -29, 0.95)
    trade(mk_, tk, t + 0.2, 880, 3, "no")
    mk_.run_timers(t + 0.35, False)
    check([f[2] for f in st(mk_, tk, "M300").fills] == [3] and not st(mk_, tk, "M500").fills, "I: landing times")
    check(st(mk_, tk, "NULL").ord is not None and st(mk_, tk, "NULL").ord.px == 870, "I: NULL at mid 87.5c -> 87c")

    # J: stale book (a trade with no book message around it)
    mk_, tk, M, sk = world()
    t = dec(mk_, M, -29, 0.95)
    mk_.run_timers(t + 0.1, False)
    trade(mk_, tk, t + 0.5, 950, 1, "yes")
    mk_.run_timers(t + 2.6, False)
    check(mk_.mi[tk]["stale"] == 1 and st(mk_, tk).ord is None and mk_.want_resync, "J: stale market flagged")

    # K: settlement, P&L, day stop, run stop + restart, close record
    lgk = B.Logger(sink=[])
    mk_ = Maker(lgk, (("T", "p", 0.07, 0.100, True),))
    D0 = 1_792_000_800                                       # 2026-10-14 14:00Z
    for i, res in enumerate(("no", "no", "yes")):
        cs = D0 + 900 * i
        tk = "KXBTC15M-K%d" % i
        mk_.market(tk, "BTC", cs)
        mk_.on_snapshot(tk, {"yes_dollars_fp": [["0.8500", "10"]], "no_dollars_fp": [["0.1000", "50"]]}, 1, 7, cs - 40)

        class Mk:
            ticker, coin, close_s = tk, "BTC", cs
        t = dec(mk_, Mk, -29, 0.95)
        mk_.run_timers(t + 0.1, False)
        trade(mk_, tk, t + 0.2, 880, 23, "no")
        delta(mk_, tk, t + 0.21, "yes", 880, -23)
        mk_.run_timers(cs + 1, False)
        mk_.settle(tk, res, cs + 5)
    a = mk_.arms[0]
    mks = [r for r in lgk.sink if r["ev"] == "mk"]
    check([r["pnl"] for r in mks] == [-20.24, -20.24], "K: P&L %s" % [r["pnl"] for r in mks])
    check(any(r["ev"] == "day_stop" for r in lgk.sink) and len(mks) == 2, "K: day stop blocks the third close")
    cl = [r for r in lgk.sink if r["ev"] == "close"]
    check(len(cl) == 3 and cl[0]["arms"]["T"]["pnl"] == -20.24 and cl[2]["arms"]["T"]["halted"], "K: close records")
    a2 = Arm("R", "p", 0.07, 0.1, True)
    a2.book(D0, -50.0, lgk)
    check(a2.run_stops == 1 and a2.blocked(D0 + 900, lgk) and not a2.blocked(D0 + 86400, lgk) and a2.run == 0.0,
          "K: run stop halts the ET day, then a simulated restart")

    # 5. the read applies the bar
    recs = []
    c0 = 1_792_382_400                                       # 2026-10-19 04:00Z = 00:00 ET
    for i in range(12 * 96):
        cs = c0 + 900 * (i + 1)
        win = i % 4 == 0
        arms_ = {}
        for nm, pnl in (("M300", 0.5 if win else 0.0), ("M500", 0.25 if win else 0.0), ("NULL", 0.1 if win else 0.0),
                        ("M300raw", 0.5 if win else 0.0)):
            arms_[nm] = {"pnl": pnl, "pnl_ok": pnl, "cost": 4.0 if win else 0.0, "filled": ["BTC"] if win else [],
                         "lost": 0, "wps": [1] * 30 if win else [0] * 30}
        recs.append({"ev": "close", "cs": cs, "covered": True, "arms": arms_,
                     "markets": {"BTC": [29, 29, 0.5 if i < 4 * 96 else 0.9, "yes", 0, 0, 1, 1]}})
    rep = read_report(recs, c0 + 12 * 86400 + 3600)
    m3 = rep["arms"]["M300"]
    check(m3["per_day"] == 12.0 and m3["roi_pct"] == 12.5 and m3["dry_h"] == 0.75 and len(rep["calm_days"]) == 4,
          "read: %s" % json.dumps(m3))
    check(rep["verdict"].startswith("PASS"), "read verdict %s" % rep["verdict"])
    rep2 = read_report(recs[:5 * 96], c0 + 12 * 86400 + 3600)
    check(rep2["verdict"].startswith("EXTEND"), "read: too few days -> %s" % rep2["verdict"])

    ok = not fails
    if verbose or not ok:
        print("selftest: %d checks, %d failed" % (n[0], len(fails)))
        for f in fails:
            print("  FAIL:", f)
    return ok, n[0], fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--read", action="store_true")
    ap.add_argument("--log", default=LOG_PATH, help="the paper log (default results/fc-maker-paper.jsonl)")
    ap.add_argument("--asof", default=None, help="read as of YYYY-MM-DDTHH:MMZ (default now)")
    ap.add_argument("--minutes", type=float, default=21600)
    ap.add_argument("--health-s", type=float, default=300.0)
    a = ap.parse_args()
    if a.read:
        return read_main(a.log, a.asof)
    ok, n, fails = selftest(verbose=a.selftest)
    if a.selftest:
        print("SELFTEST", "PASSED" if ok else "FAILED", n, "checks; sha256", src_sha())
        return 0 if ok else 1
    if not ok:
        raise SystemExit("self-test failed; refusing to run")
    return run(a.minutes, a.log, a.health_s)


if __name__ == "__main__":
    sys.exit(main())
