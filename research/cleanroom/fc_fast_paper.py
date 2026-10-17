#!/usr/bin/env python3
r"""fc_fast_paper.py -- PAPER: the live clean-room forecaster's rule (control) beside a FAST variant, on ONE feed.

Built 2026-10-17 from the strategy hunt's lose-less lead A (results/STRATEGY_HUNT_2026-10-15.md, "Lose-less leads",
A): the live forecaster decides DECIDE_OFFSET = 0.2 s after each index print's second and only sends once the paper's
cautious fill rule has booked a fill (the offer must still be shown SURVIVE_S = 1.0 s after the decision), so its
orders reach Kalshi ~1.26 s after the print. On its own paper engine 09-29..10-16 the contracts lost by waiting were
+3.21c winners (an upper bound). This file measures, side by side, what deciding at the print would have done.

NOTHING here can send an order: GET-only public REST through research/kauth.py's helper (auth=False), one WebSocket
whose only authenticated step is the handshake (market-data channels only), and the self-test scans this file for
order endpoints, write verbs and imports of the live-order modules and fails if one is found. --live is refused.

THE TWO ARMS (each its own positions, caps and fills; one shared book, index store and best-ask clock)
  ctrl  the live forecaster's paper engine EXACTLY: fc_variants.VEngine with VARIANTS["race1_98_r28"] (what boot_all.ps1
        runs: --variant race1_98_r28 --crash-gap 0.10), bettor_paper.Engine.tick unchanged (decide 0.2 s after the
        print's second, skip after 0.9 s), the 1.0-s survival rule. It must reproduce forecaster-live.jsonl's paper
        'real' fills (checked by --read, see VALIDITY). Its live order would be sent when the paper books the 1-s
        survivor, so the live broker's two refusals are applied AT THAT MOMENT: crash guard (best ask on our side
        more than 0.10 under the price; forecaster_live.Broker.want) and late (later than 0.5 s before the close;
        forecaster_live LATE_S). A refused fill still uses the paper caps, as in live.
  fast  the same rule, prices, caps (100 a side, 400 a close), race gate and crash guard, but it DECIDES WHEN THE
        PRINT ARRIVES (offset 0: on the WebSocket message itself, with the book as of that message) and counts a fill
        only if the offer is still displayed 75 ms after the decision. A print received before its own second by the
        local clock (about 2 in 100) is decided AT that second, with the book as it was then. Both instants -- the
        decision and the 75-ms check -- are resolved on message arrival times: the book "at instant T" is the book
        before the first message received after T, so neither depends on this loop's 20-ms sleep (changed 2026-10-17
        before any run, review finding 5: an early print used to be decided on the next loop pass, stamped 20 ms
        back but reading the book as of the pass). A fast live order would be sent at the decision, so its crash
        guard and late rule are applied at the DECISION instant (using the book at the 75-ms check would use
        information a live sender does not have, and flatter the fast arm).
  Every decision where either arm ordered is logged once as a 'pair' record with both arms' decision time, print
  lag, model p, best asks, orders, fills (instant 'opt' and survival 'real') and misses.

PRE-REGISTERED BAR (quoted verbatim from the build spec, written 2026-10-17 before any data):
  "read after >= 200 fast-variant paper fills over >= 100 closes (~7-10 days); PASS if the fast variant is >= +2.0c a
  contract better after fee than the control on the same decisions AND both halves positive; KILL if it is <= 0
  better. Paper cannot see who we lose to; a PASS is a reason to ask the operator about a live change, not a switch."

HOW --read APPLIES IT (fixed here, before any data):
  - a "fast-variant paper fill" = one fast-arm 'real' fill record (one price level at one decision) that a fast live
    order would have sent (sendable: not crash, not late), on a settled market.
  - a "close" = a distinct quarter-hour close with at least one such fill.
  - "a contract better after fee" = D = (fast arm's sendable after-fee pnl / its sendable contracts) minus the same for
    ctrl, in cents, over every settled market in the log. Both arms run in one process on the same prints, the same
    markets and the same book: these are "the same decisions".
  - "both halves positive": the settled closes with a sendable fill in either arm, in time order, split at the middle
    (first floor(n/2) closes, then the rest); D computed in each half; each must be > 0 (> 1e-9c, the same float
    tolerance as the KILL test, so a half that is 0 up to rounding is not "positive").
  - PASS = counts met AND D >= +2.0c AND both halves' D > 0.  KILL = counts met AND D <= 0.  Counts met and anything
    else = NO PASS (neither; not a reason to change live).  Counts not met = NOT READY (no verdict, not a trend).
  - VALIDITY: the control must reproduce the live forecaster's paper fills. On markets both logs ran and settled:
    (1) of the market-sides (ticker, side) where forecaster-live.jsonl's paper booked a 'real' fill, >= 90 in 100
    also have a ctrl 'real' fill, and >= 90 in 100 of ctrl's market-sides are live's; (2) total 'real' contracts on
    those markets within 10% of each other; (3) forecaster-live-orders.jsonl's latest start is still variant
    race1_98_r28 with crash_gap 0.1. Otherwise --read prints CONTROL DOES NOT REPRODUCE LIVE and gives no verdict.
    FAIL-CLOSED: if forecaster-live.jsonl or forecaster-live-orders.jsonl is missing (e.g. archived during the run),
    the check counts as failed -- no verdict -- never as skipped (review finding 1, fixed before any run).
    The exact (ticker, second, side, price) match is printed beside it, not used. WHY NOT EXACT (changed 2026-10-17
    before any run, from a first draft that required >= 90 in 100 exact keys): the 1-s rule reserves an order's
    full size until its check, the check of second s and the decision of second s+1 land in the same loop tick, and
    which runs first is loop timing -- two processes cannot draw it the same way. A one-hour replay (tape
    2026-10-15 12Z, recorder receive times, plumbing only) had live and this control buy the same 3 market-sides,
    100 contracts each, while only 4 of live's 36 exact (second, price) fills matched.
  Printed beside the bar, never instead of it: raw paper fills (no crash/late filter), the instant-fill upper bound
  (opt), the strict-matched subset (decisions where both arms filled the same side), the result without decisions on
  late prints (print received > 0.3 s after its second), and dollars per day at paper size.

WHAT WOULD MAKE A PASS AN ARTEFACT (check these before believing one)
  1. Our own feed lag: the 75-ms check sees the book through THIS process's WebSocket. If our feed is late, an offer
     we still "see" may already be gone at the exchange. --read reports the result without late-print decisions.
  2. Speed: a live fast order must reach Kalshi within ~75 ms of the print; today's live orders open a fresh connection
     each time (~100 ms) and wait for the 1-s rule. A live version needs one kept-open connection.
  3. Queue: paper cannot see whether we would be first to the offer at +75 ms, nor who sells to us (on our own live
     fills the people who sell to us know more -- STRATEGY_HUNT D). A PASS is a reason to ask, not a switch.
  4. Not modelled in either arm: live's proportional scaling (scale x paper size, refused paper counts carried to the
     next order on that side) and its in-flight refusal of a second price level filled at the same check
     (forecaster-live-orders.jsonl 09-29..10-17: 166 'in_flight' refusals beside 181 orders placed).

NETWORK / MEMORY: one WebSocket (the same subscription as forecaster_live: 9 index feeds, the 9 nearest markets'
order books and trades, market lifecycle). Settlement from the WebSocket 'determined' event (forecaster-live.jsonl
10-11..10-17: 4,185 of 4,248 settled markets had one, 0 disagreed with REST); a public REST GET only when no
'determined' arrived 100 s after the close. Market discovery is polled only for a coin that lacks its next market
(or DOGE's exact strike), every 30 s while needed, and never in the 90 s after a quarter-hour or the minute before
one (when the live bots discover; the 10-17 smoke drew one 429 at 04:45:16Z before this rule). Every REST call is
>= 2.0 s after the previous one; a 429 waits 10 s. Measured on the 3-minute smoke (10-17 04:42-04:45Z): 54.5 MB
working set, ~340 KB/s received on the WebSocket (uncompressed, the same subscription as forecaster_live), 10 REST
calls at start. Working set capped at 140 MB (clean stop above it).

    python research/cleanroom/fc_fast_paper.py --selftest
    python research/cleanroom/fc_fast_paper.py --minutes 20160            (results\start_fc_fast.ps1 does this)
    python research/cleanroom/fc_fast_paper.py --read                     (the bar read; read-only)
Log: C:\kals-repo\results\fc-fast-paper.jsonl (UTC; field v = ctrl / fast / _).  Stop: results\fc-fast-paper.stop.
"""
import argparse
import contextlib
import ctypes
import hashlib
import inspect
import io
import json
import math
import os
import queue
import sys
import tempfile
import textwrap
import time
from collections import deque
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import bettor_paper as B                        # noqa: E402  (engine, book, WS, REST plumbing; read-only use)
import fc_variants as FV                        # noqa: E402  (the live variant's gates; read-only use)

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
RESULTS = os.path.join(REPO, "results")
LOG_PATH = os.path.join(RESULTS, "fc-fast-paper.jsonl")
STOP_FILE = os.path.join(RESULTS, "fc-fast-paper.stop")
LIVE_LOG = os.path.join(RESULTS, "forecaster-live.jsonl")
LIVE_ORDER_LOG = os.path.join(RESULTS, "forecaster-live-orders.jsonl")
BOOT_ALL = os.path.join(REPO, "boot_all.ps1")
FORECASTER_LIVE_SRC = os.path.join(HERE, "forecaster_live.py")

LIVE_VARIANT = "race1_98_r28"                   # boot_all.ps1: forecaster_live --variant race1_98_r28
CRASH_GAP = 0.10                                # boot_all.ps1: --crash-gap 0.10 (forecaster_live.Broker.want)
LATE_S = 0.5                                    # forecaster_live.LATE_S (writer drops an order this close to the close)
FAST_OFFSET = 0.0
FAST_SURVIVE_S = 0.075
SAFETY_S = 0.02                                 # loop-end fast clock lags wall time by this (frames still being parsed)
RSS_CAP_MB = 140.0
REST_MIN_GAP_S = 2.0
REST_429_BACKOFF_S = 10.0
DISCOVER_EVERY_S = 30.0
DISCOVER_WINDOW = (90, 840)                     # seconds into each quarter-hour when discovery may run: never at the
                                                # boundary, when the live bots discover (smoke 10-17 04:45:16Z: a 429)
WS_SETTLE_AFTER_S = 3.0
REST_SETTLE_AFTER_S = 100.0                     # past the boundary's REST crowd (DISCOVER_WINDOW)
REST_SETTLE_REASK_S = 30.0
LATE_PRINT_S = 0.3                              # --read: a decision on a print received > 0.3 s after its second

# bar constants (see the docstring; --read uses exactly these)
BAR_MIN_FILLS, BAR_MIN_CLOSES, BAR_PASS_C, VALID_MATCH, VALID_CONTRACTS = 200, 100, 2.0, 0.90, 0.10
BAR_TEXT = ("read after >= 200 fast-variant paper fills over >= 100 closes (~7-10 days); PASS if the fast variant is "
            ">= +2.0c a contract better after fee than the control on the same decisions AND both halves positive; "
            "KILL if it is <= 0 better. Paper cannot see who we lose to; a PASS is a reason to ask the operator about "
            "a live change, not a switch.")

CTRL_ARM = {"name": "ctrl", "variant": LIVE_VARIANT, "params": {}, "engine": "control",
            "offset": B.DECIDE_OFFSET, "send_at": "check", "event": False}
FAST_ARM = {"name": "fast", "variant": LIVE_VARIANT, "params": {"survive_s": FAST_SURVIVE_S}, "engine": "fast",
            "offset": FAST_OFFSET, "send_at": "decision", "event": True}


# ------------------------------------------------------------------------------------------------------------ logging
class TagLogger(B.Logger):
    """Tags each record with the arm (field v); passes every write to `tap` first (the pairer); drops `drop`."""

    def __init__(self, name, fh=None, sink=None, tap=None, drop=()):
        super().__init__(None, sink)
        self.name = name
        self.fh = fh
        self.tap = tap
        self.drop = set(drop)

    def write(self, ev, **kw):
        if self.tap is not None:
            self.tap(self.name, ev, kw)
        if ev in self.drop:
            return
        kw["v"] = self.name
        super().write(ev, **kw)


# ------------------------------------------------------------------------------------------------------------ engines
class Observed(FV.VEngine):
    """fc_variants.VEngine, OBSERVED only: records each decision's time, print lag, best asks and model output, and
    tags each 'real' fill with what the live broker would do at this arm's send moment. No decision or fill changes
    (the self-test drives a plain VEngine through the same worlds and compares every fill)."""

    def __init__(self, log, now_fn, tables, params, name, send_at):
        super().__init__(log, now_fn, tables, params, name)
        self.send_at = send_at
        self.dec = {}                             # (ticker, rel) -> decision info

    def decide(self, m, rel, pr, now):
        b = self.books.get(m.ticker)
        best = {}
        if b is not None and b.synced:
            for side in ("yes", "no"):
                bp, bs = b.best_ask(side)
                best[side] = None if bp is None else [round(float(bp), 4), bs]
        stamp = m.close_s + rel
        self.dec[(m.ticker, rel)] = {"t": round(now, 4), "lag": round(now - stamp, 4),
                                     "rx_lag": round(pr[2] - stamp, 4), "best": best}
        super().decide(m, rel, pr, now)

    def forecaster(self, m, rel, v, proj, r, exact_yes, b, now):
        out = super().forecaster(m, rel, v, proj, r, exact_yes, b, now)
        d = self.dec.get((m.ticker, rel))
        if d is not None:
            d.update({"p": out.get("p"), "r": r, "n": out.get("n", 0), "why": out.get("why")})
        return out

    def send_flags(self, m, side, price, extra):
        d = self.dec.get((m.ticker, extra.get("rel")), {})
        if self.send_at == "check":               # forecaster_live: the broker is called when the paper books the fill
            t_send = self.now()
            bk = self.books.get(m.ticker)
            bp = None
            if bk is not None:
                x, _ = bk.best_ask(side)
                bp = None if x is None else round(float(x), 4)
        else:                                     # a fast live order is sent at the decision
            t_send = d.get("t")
            x = (d.get("best") or {}).get(side)
            bp = None if x is None else x[0]
        px = round(float(price), 4)
        crash = (not extra.get("hedge")) and bp is not None and bp < px - CRASH_GAP - 1e-9
        late = t_send is None or t_send > m.close_s - LATE_S
        return {"t_dec": d.get("t"), "t_send": None if t_send is None else round(t_send, 4), "rx_lag": d.get("rx_lag"),
                "best_ask_send": bp, "crash": bool(crash), "late": bool(late), "sendable": not crash and not late,
                "survive_s": self.P["survive_s"], "send_at": self.send_at}

    def add_fill(self, m, strat, fm, side, price, size, fee, **extra):
        if strat == "forecaster" and fm == "real" and extra.get("kind") == "take":
            extra.update(self.send_flags(m, side, price, extra))
        super().add_fill(m, strat, fm, side, price, size, fee, **extra)

    def finish_group(self, m):
        super().finish_group(m)
        live = set(self.markets)
        for k in [k for k in self.dec if k[0] not in live]:
            del self.dec[k]

    def next_due(self):
        s = self.P["survive_s"]
        return min((p["t_dec"] + s for m in self.markets.values() for p in m.pending), default=math.inf)

    def next_decision_due(self):
        """The instant this arm's next decision (or no-print skip) falls due on a market whose print is ALREADY in:
        its second + offset, or the print's arrival if later. That covers a print received before its own second by
        the local clock (live paper 10-09..10-15: about 2 in 100 decisions, up to 284 ms early); a print received
        after it is decided on its own message. The Runner ticks at exactly this instant, so the decision reads the
        book as it was then, never a message that arrived after it (added 2026-10-17 on review finding 5)."""
        off = getattr(self, "offset", B.DECIDE_OFFSET)
        dl = getattr(self, "deadline", B.DECIDE_DEADLINE)
        t = math.inf
        for m in self.markets.values():
            if m.done or m.next_rel > -1:
                continue
            stamp = m.close_s + m.next_rel
            pr = self.prints.get(m.index_id, {}).get(stamp)
            t = min(t, max(stamp + off, pr[2]) if pr is not None else stamp + dl + 1e-6)
        return t

    def resolve_due(self, now):
        for m in list(self.markets.values()):
            self.resolve_pending(m, now)


class FastEngine(Observed):
    """Observed with its own decision offset and deadline. tick() is bettor_paper.Engine.tick verbatim with
    DECIDE_OFFSET -> self.offset and DECIDE_DEADLINE -> self.deadline (the self-test compares the two sources)."""

    def __init__(self, log, now_fn, tables, params, name, send_at, offset, deadline=B.DECIDE_DEADLINE):
        super().__init__(log, now_fn, tables, params, name, send_at)
        self.offset = offset
        self.deadline = deadline

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
                if now < m.close_s + rel + self.offset:
                    break
                stamp = m.close_s + rel
                pr = self.prints.get(m.index_id, {}).get(stamp)
                if pr is not None and pr[2] <= now:
                    self.decide(m, rel, pr, now)
                    m.next_rel += 1
                elif now > m.close_s + rel + self.deadline:
                    self.n_skip += 1
                    self.c_cancel(m, now, "no_print")
                    self.log.write("decision", ticker=m.ticker, rel=rel, skipped="no_print")
                    m.next_rel += 1
                else:
                    break


def fill_pnl(f, result):
    """After-fee dollars of one fill record at settlement."""
    win = f["side"] == result
    return (f["size"] * (1 - f["price"]) if win else -f["size"] * f["price"]) - f["fee"]


def summarize(fills, result):
    out = {}
    for key, pick in (("raw", lambda f: f["fill"] == "real"), ("send", lambda f: f["fill"] == "real" and f.get("sendable")),
                      ("opt", lambda f: f["fill"] == "opt")):
        sel = [f for f in fills if f.get("strat") == "forecaster" and pick(f)]
        out[key] = {"fills": len(sel), "contracts": sum(f["size"] for f in sel),
                    "pnl": round(sum(fill_pnl(f, result) for f in sel), 4)}
    return out


# ------------------------------------------------------------------------------------------------------------ pairing
class Pairer:
    """One 'pair' record per decision (ticker, second) where either arm ordered or filled, written once both arms are
    past that second and have resolved every order they placed there."""

    def __init__(self, log):
        self.log = log
        self.names = []
        self.close_of = lambda t: None
        self.open = {}
        self.n_written = 0

    def _get(self, kw):
        key = (kw["ticker"], kw["rel"])
        pr = self.open.get(key)
        if pr is None:
            pr = {"close_s": self.close_of(kw["ticker"])}
            for n in self.names:
                pr[n] = {"orders": [], "real": [], "miss": [], "opt": [], "open": 0}
            self.open[key] = pr
        return pr

    def tap(self, name, ev, kw):
        if ev not in ("taker_order", "fill", "taker_miss") or kw.get("strat") != "forecaster" or name not in self.names:
            return
        if kw.get("rel") is None or kw.get("ticker") is None:
            return
        e = self._get(kw)[name]
        if ev == "taker_order":
            e["orders"].append([kw["side"], kw["price"], kw["want"], kw.get("displayed")])
            e["open"] += 1
        elif ev == "fill" and kw.get("fill") == "opt":
            e["opt"].append([kw["side"], kw["price"], kw["size"], kw["fee"]])
        elif ev == "fill":
            e["real"].append([kw["side"], kw["price"], kw["size"], kw["fee"], kw.get("sendable"), kw.get("crash"),
                              kw.get("late")])
            e["open"] -= 1
        else:
            e["miss"].append([kw["side"], kw["price"], kw["want"], kw.get("why")])
            e["open"] -= 1

    @staticmethod
    def past(e, key):
        m = e.markets.get(key[0])
        return m is None or m.done or m.next_rel > key[1]

    def flush(self, engines):
        for key in list(self.open):
            pr = self.open[key]
            if all(self.past(e, key) and pr[e.name]["open"] <= 0 for e in engines):
                rec = {"ticker": key[0], "rel": key[1], "close_s": pr["close_s"]}
                for e in engines:
                    x = dict(pr[e.name])
                    x.pop("open")
                    x["dec"] = getattr(e, "dec", {}).get(key)
                    rec[e.name] = x
                self.log.write("pair", **rec)
                self.n_written += 1
                del self.open[key]


# ------------------------------------------------------------------------------------------------------------ runner
class Runner:
    """Feed events in (rx, obj) order with feed(); call loop_end(now) once per main-loop pass (after the drain)."""

    def __init__(self, tables, ctrl_clock, fh=None, sink=None, arms=None):
        arms = arms or (CTRL_ARM, FAST_ARM)
        self.log = TagLogger("_", fh=fh, sink=sink)
        self.pairer = Pairer(self.log)
        self.ctrl_clock = ctrl_clock
        self.t_fast = -math.inf
        self.fast_hw = -math.inf
        self.next_due = math.inf
        self.n_clock_back = 0
        self.n_due_stuck = 0
        self.ws_results = {}
        self.ws_up_seen = False
        self.seq_last = {}
        self.cum_send = {a["name"]: 0.0 for a in arms}
        self.n_results = 0
        books, prints, best = {}, {}, {}
        self.engines = []
        for i, arm in enumerate(arms):
            clk = (lambda: self.t_fast) if arm["event"] else ctrl_clock
            drop = ("decision", "ws_subscribe") if i == 0 else ("decision", "market", "market_update", "ws_subscribe")
            lg = TagLogger(arm["name"], fh=fh, sink=sink, tap=self.pairer.tap, drop=drop)
            params = dict(FV.VARIANTS[arm["variant"]])
            params.update(arm["params"])
            if arm["engine"] == "plain":
                e = FV.VEngine(lg, clk, tables, params, arm["name"])
            elif arm["engine"] == "control":
                e = Observed(lg, clk, tables, params, arm["name"], arm["send_at"])
            else:
                e = FastEngine(lg, clk, tables, params, arm["name"], arm["send_at"], arm["offset"])
            e.arm = arm
            e.books, e.prints, e.best = books, prints, best
            self.engines.append(e)
        self.lead = self.engines[0]
        self.event_engines = [e for e in self.engines if e.arm["event"]]
        self.pairer.names = [e.name for e in self.engines]
        self.pairer.close_of = lambda t: getattr(self.lead.markets.get(t), "close_s", None)

    # --- market universe / settlement -------------------------------------------------------------------------------
    def add_market(self, *args):
        """Every arm gets the market only if the lead (control, wall clock) accepts it, so a stale fast clock can
        never hold a market (and its whole close group) that the control refused as already closed."""
        if self.lead.add_market(*args) is None:
            return None
        for e in self.engines[1:]:
            e.add_market(*args)
        return True

    def apply_result(self, ticker, result, ev, now, src):
        m0 = self.lead.markets.get(ticker)
        if m0 is None or m0.settled:
            return
        if result in ("yes", "no"):
            rec = {"ticker": ticker, "close_s": m0.close_s, "coin": m0.coin, "result": result, "src": src}
            for e in self.engines:
                m = e.markets.get(ticker)
                rec[e.name] = summarize(m.fills if m is not None else [], result)
                self.cum_send[e.name] += rec[e.name]["send"]["pnl"]
            self.log.write("result", **rec)
            self.n_results += 1
        for e in self.engines:
            e.on_result(ticker, result, ev, now)

    def settle_due(self, now):
        for tk, res in list(self.ws_results.items()):
            m = self.lead.markets.get(tk)
            if m is None or m.settled:
                del self.ws_results[tk]
            elif m.done and now >= m.close_s + WS_SETTLE_AFTER_S:
                self.apply_result(tk, res, None, now, "ws")
                del self.ws_results[tk]

    def rest_settle_wanted(self, now, asked_at):
        """Done markets with no 'determined' event REST_SETTLE_AFTER_S after the close (re-asked every 30 s)."""
        return [m.ticker for m in self.lead.markets.values()
                if m.done and not m.settled and m.ticker not in self.ws_results
                and now >= m.close_s + REST_SETTLE_AFTER_S and now - asked_at.get(m.ticker, -1e18) >= REST_SETTLE_REASK_S]

    def discovery_need(self, now):
        """Coins whose next market is unknown, has no strike yet, or (DOGE) lacks the exact previous-settle strike
        while its window has not started."""
        need = []
        for coin in B.COINS:
            ms = [m for m in self.lead.markets.values() if m.coin == coin and m.close_s > now]
            if not ms:
                need.append(coin)
            elif any(m.strike is None and m.next_rel == B.REL_FIRST for m in ms):
                need.append(coin)
            elif coin == "DOGE" and any(m.next_rel == B.REL_FIRST
                                        and not str(m.strike_src or "").startswith("prev_expiration_value") for m in ms):
                need.append(coin)
        return need

    # --- feed ------------------------------------------------------------------------------------------------------
    def _due(self):
        self.next_due = min((min(e.next_due(), e.next_decision_due()) for e in self.event_engines), default=math.inf)

    def _advance(self, t):
        """Move the fast clock through every instant due at or before t -- a 75-ms check, or a decision on a print
        that is already in -- in time order, ticking the fast arms AT that instant. Called before a message received
        at t is applied (and by loop_end), so each check and decision sees the book as it was at its own instant."""
        last = None
        while self.next_due <= t:
            d = self.next_due
            if last is not None and d <= last:    # a due instant that a tick did not consume: never spin on it
                self.n_due_stuck += 1
                break
            last = d
            self.t_fast = max(self.t_fast, d)
            for e in self.event_engines:
                e.tick()
            self._due()

    def feed(self, rx, obj):
        t = obj.get("type")
        if self.event_engines:
            if rx < self.fast_hw - 1e-9:
                self.n_clock_back += 1
            self.fast_hw = max(self.fast_hw, rx)
            self._advance(rx)                     # checks / decisions due before this message: book as of then
        self._dispatch(rx, obj, t)
        if self.event_engines and t == "cfbenchmarks_value":
            self.t_fast = rx                      # decide on the print, with the book as of its arrival
            for e in self.event_engines:
                e.tick()
            self._due()

    def on_gap(self):
        self.lead.on_gap()

    def _dispatch(self, rx, obj, t):
        lead = self.lead
        if t == "cfbenchmarks_value":
            msg = obj["msg"]
            try:
                data = json.loads(msg["data"])
                lead.on_print(msg["index_id"], int(data["time"]), data["value"], rx)
            except Exception as e:
                self.log.write("bad_print", err=str(e)[:100])
        elif t == "orderbook_delta":
            sid, seq = obj.get("sid"), obj.get("seq")
            exp = self.seq_last.get(sid)
            if exp is not None and seq != exp + 1:
                self.on_gap()
                self.log.write("seq_gap", sid=sid, expected=exp + 1, got=seq)
            self.seq_last[sid] = seq
            lead.on_delta(obj["msg"]["market_ticker"], obj["msg"], seq, sid)
        elif t == "orderbook_snapshot":
            sid, seq = obj.get("sid"), obj.get("seq")
            self.seq_last[sid] = seq
            tk = obj["msg"]["market_ticker"]
            if any(tk in e.markets for e in self.engines):
                lead.books.setdefault(tk, B.Book()).load(obj["msg"], seq, sid)
                lead._mark_best(tk)
        elif t == "trade":
            sid, seq = obj.get("sid"), obj.get("seq")
            self.seq_last[sid] = seq
            try:
                for e in self.engines:
                    e.on_trade(obj["msg"]["market_ticker"], obj["msg"])
            except Exception as e:
                self.log.write("bad_trade", err=str(e)[:200])
        elif t == "market_lifecycle_v2":
            msg = obj.get("msg") or {}
            tk = msg.get("market_ticker")
            if tk in lead.markets and msg.get("event_type") in ("determined", "metadata_updated"):
                self.log.write("lifecycle", **{k: v for k, v in msg.items() if k != "additional_metadata"})
                if msg.get("event_type") == "determined" and msg.get("result") in ("yes", "no"):
                    self.ws_results[tk] = msg["result"]
        elif t == "_rest_markets":
            for coin, mk in obj["markets"]:
                try:
                    args = B.market_from_rest(coin, mk, obj["doge_prev"], lead.last_expiration)
                    if args[2] - rx < 1800:
                        self.add_market(*args)
                except Exception as e:
                    self.log.write("bad_market", ticker=mk.get("ticker"), err=str(e)[:200])
        elif t == "_rest_result":
            tk, res = obj["ticker"], obj.get("result")
            m = lead.markets.get(tk)
            if m is not None and not m.settled:
                if res in ("yes", "no") and m.done:
                    self.apply_result(tk, res, obj.get("expiration_value"), rx, "rest")
                elif res not in ("yes", "no"):
                    for e in self.engines:            # lets bettor_paper's settle timeout fire
                        e.on_result(tk, res, obj.get("expiration_value"), rx)
        elif t == "_ws_up":
            self.seq_last = {}
            for b in lead.books.values():
                b.synced = False
            self.ws_up_seen = True
        elif t == "_ws_down":
            for b in lead.books.values():
                b.synced = False
        elif t == "error":
            self.log.write("ws_error_msg", msg=obj.get("msg"))

    def loop_end(self, now):
        if self.event_engines:
            self._advance(now - SAFETY_S)
            self.t_fast = max(self.t_fast, now - SAFETY_S)
        for e in self.engines:
            e.tick()
        self._due()
        self.settle_due(now)
        self.pairer.flush(self.engines)


# ------------------------------------------------------------------------------------------------------------ network
class CountingWS(B.WS):
    """bettor_paper.WS unchanged, plus a count of bytes received (for the health record)."""
    rx_bytes = 0

    def _read_loop(self, s, buf):
        outer = self

        class Counted:
            def recv(self, n):
                c = s.recv(n)
                outer.rx_bytes += len(c)
                return c
        return super()._read_loop(Counted(), buf)


class PacedRest(B.Rest):
    """Public GETs only: >= REST_MIN_GAP_S between any two calls, REST_429_BACKOFF_S after a 429 (the per-IP limit is
    shared with the live bots' market discovery). Discovery only for the coins the main loop asks for."""

    def __init__(self, q, log, get_fn, sleep_fn=time.sleep, time_fn=time.time):
        super().__init__(q, log, get_fn)
        self.sleep_fn, self.clock = sleep_fn, time_fn
        self.last_call = -1e18
        self.n_calls = 0
        self.n_429 = 0
        self.discover_jobs = queue.Queue()
        self.discover_pending = False

    def _one(self, path, params):
        wait = self.last_call + REST_MIN_GAP_S - self.clock()
        if wait > 0:
            self.sleep_fn(wait)
        st, body = self.get(path, params, auth=False)
        self.last_call = self.clock()
        self.n_calls += 1
        return st, body

    def get_paced(self, path, params):
        st, body = self._one(path, params)
        if st == 429:
            self.n_429 += 1
            self.log.write("rest_429", path=path)
            self.sleep_fn(REST_429_BACKOFF_S)
            st, body = self._one(path, params)
            if st == 429:
                self.n_429 += 1
                self.log.write("rest_429", path=path, retry=True)
                self.sleep_fn(REST_429_BACKOFF_S)
        return st, body

    def poll_coins(self, coins):
        out = []
        for coin in coins:
            series = B.COINS[coin][0]
            st, body = self.get_paced("/markets", {"series_ticker": series, "status": "open", "limit": 50})
            if st != 200 or not isinstance(body, dict):
                self.log.write("rest_error", path="/markets", series=series, status=st, body=str(body)[:200])
                continue
            for mk in body.get("markets", []):
                out.append((coin, mk))
        prev = []
        if "DOGE" in coins:                       # the previous DOGE market's expiration_value is the exact strike
            st, body = self.get_paced("/markets", {"series_ticker": "KXDOGE15M", "status": "settled", "limit": 5})
            if st == 200 and isinstance(body, dict):
                prev = body.get("markets", [])
        self.q.put((self.clock(), {"type": "_rest_markets", "markets": out, "doge_prev": prev}))

    def run(self):
        while not self.stop:
            try:
                coins = self.discover_jobs.get_nowait()
            except queue.Empty:
                coins = None
            if coins:
                try:
                    self.poll_coins(coins)
                except Exception as e:
                    self.log.write("rest_error", err=str(e)[:200])
                self.discover_pending = False
                continue
            try:
                ticker = self.settle_jobs.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                st, body = self.get_paced("/markets/" + ticker, None)
                mk = body.get("market", {}) if st == 200 and isinstance(body, dict) else {}
                self.q.put((self.clock(), {"type": "_rest_result", "ticker": ticker, "status": st,
                                           "result": mk.get("result"), "expiration_value": mk.get("expiration_value")}))
            except Exception as e:
                self.log.write("rest_error", ticker=ticker, err=str(e)[:200])


# ------------------------------------------------------------------------------------------------------------ process
def sha12(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


def pid_alive(pid):
    if pid <= 0:
        return False
    try:
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, int(pid))       # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == 259               # STILL_ACTIVE
    except Exception:
        return False


def take_lock(path):
    """Write our pid to `path`; refuse (return the holder's pid) if a live process already holds it."""
    try:
        with open(path, encoding="utf-8") as f:
            held = int((f.read().strip() or "0"))
    except (OSError, ValueError):
        held = 0
    if held and held != os.getpid() and pid_alive(held):
        return held
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    return None


def drop_lock(path):
    try:
        with open(path, encoding="utf-8") as f:
            mine = f.read().strip() == str(os.getpid())
        if mine:
            os.remove(path)
    except OSError:
        pass


def stop_requested(path):
    return os.path.exists(path)


def discovery_allowed(now):
    """Market discovery only from 90 s after a quarter-hour to 60 s before the next (the live bots' discovery and
    trading crowd the shared per-IP REST limit at the boundary). The forecaster trades only the last 29 s, so a
    market found 13.5 min before its close is in time."""
    return DISCOVER_WINDOW[0] <= (now % 900) <= DISCOVER_WINDOW[1]


def run_live(minutes, log_path, stop_path, start_rec):
    import kauth  # GET + WebSocket handshake signing only
    fh = open(log_path, "a", encoding="utf-8")
    runner = Runner(B.Tables(), time.time, fh=fh)
    log = runner.log
    lead = runner.lead
    q = queue.Queue()
    ws = CountingWS(q, log, kauth.headers)
    ws.index_ids = [B.COINS[c][1] for c in B.COINS]
    rest = PacedRest(q, log, kauth.get)
    log.write("selftest", passed=True, checks=start_rec.get("selftest_checks"))
    log.write("start", pid=os.getpid(), rss_mb=B.rss_mb(), **start_rec)
    ws.start()
    rest.start()
    t_end = time.time() + minutes * 60
    last_health = time.time()
    last_disc = 0.0
    last_stop_chk = 0.0
    last_active = None
    last_resync = 0.0
    asked_at = {}
    tick_max, drain_max, bytes0 = 0.0, 0, 0
    reason = "minutes_elapsed"
    while time.time() < t_end:
        drained = 0
        while drained < 5000:
            try:
                rx, obj = q.get_nowait()
            except queue.Empty:
                break
            drained += 1
            try:
                runner.feed(rx, obj)
            except Exception as e:
                log.write("feed_error", type=obj.get("type"), err=repr(e)[:300])
        now = time.time()
        t0 = time.perf_counter()
        try:
            runner.loop_end(now)
        except Exception as e:
            log.write("tick_error", err=repr(e)[:300])
        tick_max = max(tick_max, time.perf_counter() - t0)
        drain_max = max(drain_max, drained)
        if runner.ws_up_seen:
            runner.ws_up_seen = False
            last_active = None
        active = lead.active_tickers(now)
        if ws.connected and (active != last_active or (lead.resync_wanted and now - last_resync > 5)):
            lead.resync_wanted = False
            last_resync = now
            last_active = active
            ws.set_markets(active)
        if now - last_disc >= DISCOVER_EVERY_S and not rest.discover_pending and discovery_allowed(now):
            last_disc = now
            need = runner.discovery_need(now)
            if need:
                rest.discover_pending = True
                rest.discover_jobs.put(tuple(need))
        for tk in runner.rest_settle_wanted(now, asked_at):
            asked_at[tk] = now
            rest.settle_jobs.put(tk)
        for tk in [k for k in asked_at if k not in lead.markets]:
            del asked_at[tk]
        if now - last_stop_chk >= 1.0:
            last_stop_chk = now
            if stop_requested(stop_path):
                reason = "stop_file"
                break
        if now - last_health >= 60:
            rss = B.rss_mb()
            lags = sorted(lead.lag_ms)

            def pct(p):
                return round(lags[min(len(lags) - 1, int(p * len(lags)))], 1) if lags else None
            el = max(now - last_health, 1.0)
            log.write("health", ws=ws.connected, reconnects=max(ws.reconnects, 0), rss_mb=rss,
                      rx_kb_s=round((ws.rx_bytes - bytes0) / 1024.0 / el, 1), markets=len(lead.markets),
                      books_synced=sum(1 for b in lead.books.values() if b.synced), queue=q.qsize(),
                      tick_max_ms=round(1000 * tick_max, 1), drain_max=drain_max,
                      lag_ms={"p50": pct(0.5), "p90": pct(0.9), "p99": pct(0.99), "n": len(lags)},
                      rest_calls=rest.n_calls, rest_429=rest.n_429, clock_back=runner.n_clock_back,
                      due_stuck=runner.n_due_stuck,
                      seq_gaps=lead.n_gaps, pairs=runner.pairer.n_written, results=runner.n_results,
                      check_late_ms={e.name: round(1000 * getattr(e, "late_max", 0.0), 1) for e in runner.engines},
                      cum_raw={e.name: round(e.cum[("forecaster", "real")], 2) for e in runner.engines},
                      cum_send={k: round(v, 2) for k, v in runner.cum_send.items()})
            bytes0 = ws.rx_bytes
            tick_max, drain_max = 0.0, 0
            for e in runner.engines:
                e.late_max = 0.0
            last_health = now
            if rss > RSS_CAP_MB:
                reason = "rss_cap %.1f MB" % rss
                break
        time.sleep(0.02)
    ws.stop = True
    rest.stop = True
    log.write("stop", reason=reason, rest_calls=rest.n_calls, rest_429=rest.n_429, results=runner.n_results,
              pairs=runner.pairer.n_written, cum_send={k: round(v, 2) for k, v in runner.cum_send.items()})
    fh.flush()
    return reason


# ------------------------------------------------------------------------------------------------------------ read
def _lines(src):
    if isinstance(src, str):
        with open(src, encoding="utf-8", errors="replace") as f:
            for ln in f:
                yield ln
    else:
        for ln in src:
            yield ln


def _cpc(pnl, n):
    return None if n <= 0 else 100.0 * pnl / n


def read_log(src):
    """Apply the pre-registered bar to an fc-fast-paper log (path or iterable of lines). Returns a dict."""
    results, fills, pairs, starts, markets = {}, [], [], [], set()
    for ln in _lines(src):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        ev = r.get("ev")
        if ev == "result" and r.get("result") in ("yes", "no"):
            results[r["ticker"]] = (r["result"], r["close_s"])
        elif ev == "fill" and r.get("strat") == "forecaster" and r.get("v") in ("ctrl", "fast"):
            fills.append(r)
        elif ev == "pair":
            pairs.append(r)
        elif ev == "start":
            starts.append(r)
        elif ev == "market" and r.get("v") == "ctrl":
            markets.add(r["ticker"])
    arms = ("ctrl", "fast")
    agg = {a: {k: {"pnl": 0.0, "n": 0.0, "fills": 0} for k in ("send", "raw", "opt", "send_fresh")} for a in arms}
    by_close = {}
    fast_send_closes = set()
    n_fast_send = 0
    for f in fills:
        res = results.get(f["ticker"])
        if res is None:
            continue
        result, close_s = res
        a = f["v"]
        p = fill_pnl(f, result)
        kinds = []
        if f["fill"] == "opt":
            kinds.append("opt")
        elif f["fill"] == "real":
            kinds.append("raw")
            if f.get("sendable"):
                kinds.append("send")
                rl = f.get("rx_lag")
                if rl is not None and rl <= LATE_PRINT_S:
                    kinds.append("send_fresh")
                c = by_close.setdefault(close_s, {x: [0.0, 0.0] for x in arms})
                c[a][0] += p
                c[a][1] += f["size"]
                if a == "fast":
                    n_fast_send += 1
                    fast_send_closes.add(close_s)
        for k in kinds:
            agg[a][k]["pnl"] += p
            agg[a][k]["n"] += f["size"]
            agg[a][k]["fills"] += 1
    out = {"settled_markets": len(results), "fast_send_fills": n_fast_send, "fast_send_closes": len(fast_send_closes)}
    for a in arms:
        for k in agg[a]:
            agg[a][k]["cpc"] = _cpc(agg[a][k]["pnl"], agg[a][k]["n"])
            agg[a][k]["pnl"] = round(agg[a][k]["pnl"], 4)
    out["arms"] = agg

    def diff(x, y):
        return None if x is None or y is None else x - y
    out["D"] = diff(agg["fast"]["send"]["cpc"], agg["ctrl"]["send"]["cpc"])
    out["D_raw"] = diff(agg["fast"]["raw"]["cpc"], agg["ctrl"]["raw"]["cpc"])
    out["D_fresh"] = diff(agg["fast"]["send_fresh"]["cpc"], agg["ctrl"]["send_fresh"]["cpc"])
    closes = sorted(by_close)
    h = len(closes) // 2
    halves = []
    for part in (closes[:h], closes[h:]):
        s = {a: [sum(by_close[c][a][0] for c in part), sum(by_close[c][a][1] for c in part)] for a in arms}
        halves.append({"closes": len(part), "from": part[0] if part else None, "to": part[-1] if part else None,
                       "D": diff(_cpc(*s["fast"]), _cpc(*s["ctrl"])),
                       "fast_cpc": _cpc(*s["fast"]), "ctrl_cpc": _cpc(*s["ctrl"])})
    out["halves"] = halves
    # strict-matched subset: decisions where both arms filled the same side (sendable), from the pair records
    m_p = {a: [0.0, 0.0] for a in arms}
    for pr in pairs:
        res = results.get(pr["ticker"])
        if res is None:
            continue
        for side in ("yes", "no"):
            got = {a: [x for x in (pr.get(a) or {}).get("real", []) if x[0] == side and x[4]] for a in arms}
            if all(got[a] for a in arms):
                for a in arms:
                    for x in got[a]:
                        m_p[a][0] += fill_pnl({"side": x[0], "price": x[1], "size": x[2], "fee": x[3]}, res[0])
                        m_p[a][1] += x[2]
    out["D_matched"] = diff(_cpc(*m_p["fast"]), _cpc(*m_p["ctrl"]))
    out["matched_contracts"] = {a: m_p[a][1] for a in arms}
    if closes:
        days = max((closes[-1] - closes[0]) / 86400.0, 1.0 / 96)
        out["days"] = round(days, 2)
        out["usd_per_day_paper"] = {a: round(agg[a]["send"]["pnl"] / days, 2) for a in arms}
    ready = n_fast_send >= BAR_MIN_FILLS and len(fast_send_closes) >= BAR_MIN_CLOSES
    D = out["D"]
    if not ready:
        v = "NOT READY"
    elif D is None:
        v = "NO PASS"
    elif D <= 0 + 1e-9:
        v = "KILL"
    elif D >= BAR_PASS_C - 1e-9 and all(x["D"] is not None and x["D"] > 0 + 1e-9 for x in halves):
        v = "PASS"
    else:
        v = "NO PASS"
    out["verdict"] = v
    out["ctrl_markets"] = markets
    out["settled_tickers"] = set(results)
    ck = {}
    for f in fills:
        if f["v"] == "ctrl" and f["fill"] == "real":
            k = (f["ticker"], f["rel"], f["side"], round(f["price"], 4))
            ck[k] = ck.get(k, 0.0) + f["size"]
    out["ctrl_real_keys"] = ck                    # (ticker, second, side, price) -> contracts
    out["starts"] = len(starts)
    return out


def check_control(ctrl_markets, ctrl_keys, ctrl_settled, live_src, live_orders_src):
    """Does ctrl reproduce forecaster-live.jsonl's paper 'real' fills on markets both logged and settled? Judged at
    the market-side level (see VALIDITY in the docstring); the exact (ticker, second, side, price) match is reported
    beside it. ctrl_keys: {(ticker, second, side, price): contracts} (a set counts each key as 1 contract).
    FAIL-CLOSED (2026-10-17, review finding 1): a missing live log or live order log (None, or a path that does not
    exist), or an order log whose latest start is not race1_98_r28 / crash gap 0.10, is INVALID -- never 'unchecked'."""
    def absent(src):
        return src is None or (isinstance(src, str) and not os.path.exists(src))
    miss = [nm for nm, s in (("forecaster-live.jsonl", live_src), ("forecaster-live-orders.jsonl", live_orders_src))
            if absent(s)]
    if miss:
        return {"valid": False, "why": "missing " + " and ".join(miss), "live_variant_ok": None}
    if not isinstance(ctrl_keys, dict):
        ctrl_keys = {k: 1.0 for k in ctrl_keys}
    live_markets, live_settled, live_keys = set(), set(), {}
    for ln in _lines(live_src):
        if '"ev":"fill"' not in ln and '"ev":"market"' not in ln and '"ev":"settle"' not in ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:
            continue
        ev = r.get("ev")
        if ev == "market":
            live_markets.add(r["ticker"])
        elif ev == "settle" and r.get("result") in ("yes", "no"):
            live_settled.add(r["ticker"])
        elif ev == "fill" and r.get("strat") == "forecaster" and r.get("fill") == "real":
            k = (r["ticker"], r["rel"], r["side"], round(r["price"], 4))
            live_keys[k] = live_keys.get(k, 0.0) + float(r.get("size", 1.0))
    both = (set(ctrl_markets) & live_markets) & (set(ctrl_settled) & live_settled)
    lk = {k: v for k, v in live_keys.items() if k[0] in both}
    ck = {k: v for k, v in ctrl_keys.items() if k[0] in both}

    def sides(d):
        out_ = {}
        for k, v in d.items():
            out_[(k[0], k[2])] = out_.get((k[0], k[2]), 0.0) + v
        return out_
    ls, cs = sides(lk), sides(ck)
    sb = set(ls) & set(cs)
    nl, nc = sum(ls.values()), sum(cs.values())
    out = {"markets_both": len(both), "live_sides": len(ls), "ctrl_sides": len(cs), "sides_matched": len(sb),
           "live_sides_in_ctrl": None if not ls else len(sb) / len(ls),
           "ctrl_sides_in_live": None if not cs else len(sb) / len(cs),
           "live_contracts": nl, "ctrl_contracts": nc,
           "exact_live_in_ctrl": None if not lk else len(set(lk) & set(ck)) / len(lk),
           "exact_ctrl_in_live": None if not ck else len(set(lk) & set(ck)) / len(ck)}
    last = None
    for ln in _lines(live_orders_src):
        if '"ev":"start"' in ln:
            try:
                last = json.loads(ln)
            except Exception:
                pass
    variant_ok = (last is not None and last.get("variant") == LIVE_VARIANT
                  and last.get("crash_gap") is not None and abs(float(last["crash_gap"]) - CRASH_GAP) < 1e-9)
    out["live_variant_ok"] = variant_ok
    why = []
    if not ls:
        why.append("live paper has no real fill on a market both logs settled")
    if not cs:
        why.append("control has no real fill on a market both logs settled")
    if ls and cs and out["live_sides_in_ctrl"] < VALID_MATCH:
        why.append("live market-sides found in control %.3f < %.2f" % (out["live_sides_in_ctrl"], VALID_MATCH))
    if ls and cs and out["ctrl_sides_in_live"] < VALID_MATCH:
        why.append("control market-sides found in live %.3f < %.2f" % (out["ctrl_sides_in_live"], VALID_MATCH))
    if abs(nl - nc) > VALID_CONTRACTS * max(nl, nc):
        why.append("contracts live %.0f vs control %.0f differ by more than %d in 100"
                   % (nl, nc, round(100 * VALID_CONTRACTS)))
    if variant_ok is not True:
        why.append("forecaster-live-orders.jsonl's latest start is not %s with crash gap %.2f" % (LIVE_VARIANT, CRASH_GAP))
    out["valid"] = not why
    out["why"] = "; ".join(why) if why else None
    return out


def print_read(rd, cc):
    def c(x):
        return "n/a" if x is None else "%+.2fc" % x
    print("fc-fast paper read. Bar (pre-registered, verbatim): \"%s\"" % BAR_TEXT)
    print("settled markets %d; fast sendable fills %d over %d closes (need %d over %d)"
          % (rd["settled_markets"], rd["fast_send_fills"], rd["fast_send_closes"], BAR_MIN_FILLS, BAR_MIN_CLOSES))
    for a in ("ctrl", "fast"):
        x = rd["arms"][a]
        print("  %-4s sendable %6d fills %9.0f contracts %10.2f $ = %s a contract | raw %s on %.0f | instant(opt) %s on %.0f"
              % (a, x["send"]["fills"], x["send"]["n"], x["send"]["pnl"], c(x["send"]["cpc"]), c(x["raw"]["cpc"]),
                 x["raw"]["n"], c(x["opt"]["cpc"]), x["opt"]["n"]))
    print("D (fast - ctrl, a contract after fee, sendable) = %s; halves %s / %s"
          % (c(rd["D"]), c(rd["halves"][0]["D"]), c(rd["halves"][1]["D"])))
    print("beside the bar: raw D %s; fresh-print-only D %s; strict-matched D %s on %s contracts; paper $/day %s over %s days"
          % (c(rd["D_raw"]), c(rd["D_fresh"]), c(rd["D_matched"]), rd["matched_contracts"], rd.get("usd_per_day_paper"),
             rd.get("days")))
    if cc is not None:
        print("control vs live paper: %s" % {k: (round(v, 3) if isinstance(v, float) else v) for k, v in cc.items()})
    verdict = rd["verdict"]
    if verdict != "NOT READY" and (cc is None or cc.get("valid") is not True):   # fail-closed: no check = no verdict
        why = "no control check was run" if cc is None else (cc.get("why") or "control check failed")
        verdict = "CONTROL DOES NOT REPRODUCE LIVE (%s) -- no verdict (would have been %s)" % (why, verdict)
    print("VERDICT: " + verdict)
    return verdict


def read_main(log_path, live_log=LIVE_LOG, live_orders=LIVE_ORDER_LOG):
    """--read. The control check ALWAYS runs; a missing live log or order log makes it invalid (no verdict)."""
    if not os.path.exists(log_path):
        print("VERDICT: NOT READY (no log at %s; the paper run has not started)" % log_path)
        return "NOT READY"
    rd = read_log(log_path)
    cc = check_control(rd["ctrl_markets"], rd["ctrl_real_keys"], rd["settled_tickers"], live_log, live_orders)
    return print_read(rd, cc)


# ------------------------------------------------------------------------------------------------------------ selftest
def selftest():
    """Planted worlds through the Runner's own dispatch (WebSocket-shaped messages, a simulated clock), a NULL, empty
    worlds, the reader on planted logs, REST pacing, discovery, locks, a source scan, and live-config drift checks.
    Returns (ok, passed checks, failed checks); an exception inside is a failure, never a pass."""
    fails, okc = [], []

    def ck(ok, msg):
        (okc if ok else fails).append(msg)
    try:
        _selftest_body(ck)
    except Exception as e:
        import traceback
        fails.append("self-test raised %r at %s" % (e, traceback.format_exc().strip().splitlines()[-3][:160]))
    if fails:
        print("fc_fast_paper self-test FAILED (%d of %d):" % (len(fails), len(fails) + len(okc)))
        for f in fails:
            print("  FAIL:", f)
    else:
        print("fc_fast_paper self-test PASSED: %d checks" % len(okc))
    return not fails, okc, fails


def _selftest_body(ck):
    tb = B.Tables()
    C = 1_000_000

    def pmsg(s, val):
        return {"type": "cfbenchmarks_value", "msg": {"index_id": "BRTI", "data": json.dumps({"time": s * 1000, "value": val})}}

    def delta(side, price, d):
        return {"type": "orderbook_delta", "msg": {"market_ticker": "BTC-T", "side": side, "price_dollars": price,
                                                   "delta_fp": d}}

    def sim(arms, book, events=(), vals=("101.00", "101.01"), lag=0.05, loop_dt=0.02, result="yes", t0=-65.0, t1=5.0,
            strike="100.00", determined=True, deliver=0.0):
        """deliver: each message reaches the main loop this long after its receive stamp (frames still in flight)."""
        clock = [C - 200.0]
        sink = []
        rn = Runner(tb, lambda: clock[0], sink=sink, arms=arms)
        rn.add_market("BTC-T", "BTC", C, Decimal(strike), 2, "planted")
        msgs = []
        for s in range(C - 240, C + 1):
            v = vals[s % 2] if isinstance(vals, tuple) else vals(s)
            lg = lag if not callable(lag) else lag(s - C)
            msgs.append((s + lg, 0, pmsg(s, v)))
        msgs.append((C - 199.0, 1, {"type": "orderbook_snapshot", "msg": dict(book, market_ticker="BTC-T")}))
        for k, (at, ob) in enumerate(events):
            msgs.append((C + at, 2 + k, ob))
        if determined:
            msgs.append((C + 1.0, 10 ** 6, {"type": "market_lifecycle_v2", "msg": {
                "market_ticker": "BTC-T", "event_type": "determined", "result": result, "settlement_value": "1"}}))
        msgs.sort(key=lambda x: (x[0], x[1]))
        seqs = {}
        for _, _, ob in msgs:                     # consecutive seqs per channel, as the exchange sends them
            if ob["type"] in ("orderbook_snapshot", "orderbook_delta"):
                ob["sid"] = 1
            elif ob["type"] == "trade":
                ob["sid"] = 2
            if "sid" in ob:                       # an event carrying _skip=k plants a k-message sequence gap
                seqs[ob["sid"]] = seqs.get(ob["sid"], 0) + 1 + ob.pop("_skip", 0)
                ob["seq"] = seqs[ob["sid"]]
        i = 0
        steps = int(round((t1 - t0) / loop_dt))
        for k in range(0, steps + 1):
            t = C + t0 + k * loop_dt
            while i < len(msgs) and msgs[i][0] + deliver <= t:
                clock[0] = msgs[i][0]
                rn.feed(msgs[i][0], msgs[i][2])
                i += 1
            clock[0] = t
            rn.loop_end(t)
        return rn, sink

    def fills(sink, v, fm="real"):
        return [(r["side"], r["price"], r["size"], r["rel"]) for r in sink
                if r["ev"] == "fill" and r.get("v") == v and r["fill"] == fm]

    def flags(sink, v):
        return [(r["side"], r["price"], r["size"], r["rel"], r["sendable"], r["crash"], r["late"]) for r in sink
                if r["ev"] == "fill" and r.get("v") == v and r["fill"] == "real"]
    book = {"no_dollars_fp": [["0.2000", "50.00"], ["0.0100", "500.00"]], "yes_dollars_fp": [["0.0100", "40.00"]]}
    NULL_ARM = dict(FAST_ARM, name="fast", params={}, offset=B.DECIDE_OFFSET, send_at="check", event=False)
    PLAIN = dict(CTRL_ARM, name="plain", engine="plain")

    # 0. the copied tick is bettor_paper.Engine.tick with the two constants made attributes
    src_b = textwrap.dedent(inspect.getsource(B.Engine.tick)).replace("DECIDE_OFFSET", "self.offset").replace(
        "DECIDE_DEADLINE", "self.deadline")
    src_f = textwrap.dedent(inspect.getsource(FastEngine.tick))
    ck(src_b.strip() == src_f.strip(), "FastEngine.tick is bettor_paper.Engine.tick verbatim (offset/deadline as attributes)")

    # world 3 (used by several checks): the 80c offer survives the fast 75-ms check and the control's decision, but is
    # taken 0.6 s after the print -- before the control's 1-s check
    gone06 = [(-29 + 0.65, delta("no", "0.2000", "-50.00"))]
    bookn = {"no_dollars_fp": [["0.0100", "500.00"]], "yes_dollars_fp": [["0.0100", "40.00"]]}

    def null_worlds():                            # fresh event lists each call (sim stamps sid/seq on them)
        return {"steady book": (book, [], 0.05),
                "offer gone at +0.65 s": (book, [(-29 + 0.65, delta("no", "0.2000", "-50.00"))], 0.05),
                "collapse at +0.5 s": (book, [(-29 + 0.5, delta("no", "0.4000", "5.00"))], 0.05),
                "late prints, offer at -1.6 s": (bookn, [(-1.6, delta("no", "0.2000", "50.00"))], 0.6)}
    # NULL 0: Observed (the control arm) == a plain fc_variants.VEngine(race1_98_r28), fill for fill
    # NULL 1: the fast arm with the control's settings (offset 0.2, survive 1.0, send at the check, loop-driven)
    #         must log identical fills AND identical send flags
    n0 = n1 = 0
    ok0 = ok1 = True
    kinds = set()
    for wname, (bk, evs, lg) in null_worlds().items():
        rn, sk = sim((PLAIN, CTRL_ARM), bk, evs, lag=lg)
        same0 = (fills(sk, "plain") == fills(sk, "ctrl") and fills(sk, "plain", "opt") == fills(sk, "ctrl", "opt"))
        ok0 = ok0 and same0
        n0 += len(fills(sk, "ctrl")) + len(fills(sk, "ctrl", "opt"))
        rn, sk = sim((CTRL_ARM, NULL_ARM), bk, evs, lag=lg)
        same1 = flags(sk, "ctrl") == flags(sk, "fast") and fills(sk, "ctrl", "opt") == fills(sk, "fast", "opt")
        ok1 = ok1 and same1
        n1 += len(flags(sk, "ctrl"))
        kinds |= {("sendable" if x[4] else "crash" if x[5] else "late") for x in flags(sk, "ctrl")}
        if not (same0 and same1):
            ck(False, "NULL in '%s': %s / %s" % (wname, flags(sk, "ctrl"), flags(sk, "fast")))
    ck(ok0 and n0 >= 4, "NULL 0: the observed control = a plain VEngine(race1_98_r28), fill for fill, in 4 worlds "
       "(%d fills compared)" % n0)
    ck(ok1 and n1 >= 3 and kinds == {"sendable", "crash", "late"},
       "NULL 1: fast settings = control settings -> identical real fills and send flags in 4 worlds (%d real fills "
       "compared, covering %s)" % (n1, sorted(kinds)))
    rn, sk = sim((CTRL_ARM, FAST_ARM), book, gone06)
    ck(not fills(sk, "ctrl"), "world 3 control: the offer is gone at the 1-s check -> no real fill")
    # world 3 with the real fast settings: fast fills 50 @0.80 at rel -29, control misses
    rn, sk = sim((CTRL_ARM, FAST_ARM), book, gone06)
    ck(fills(sk, "fast") == [("yes", 0.8, 50, -29)] and not fills(sk, "ctrl"),
       "world 3: fast books 50 @0.80 (still shown 75 ms after the print), control misses at 1 s (%s)" % fills(sk, "fast"))
    ck(any(r["ev"] == "taker_miss" and r.get("v") == "ctrl" and r["why"] == "gone" and r["rel"] == -29 for r in sk),
       "world 3: the control's miss is logged why=gone")
    frs = [r for r in sk if r["ev"] == "fill" and r.get("v") == "fast" and r["fill"] == "real"]
    fr = frs[0] if frs else {"t_dec": -1e18}
    ck(abs(fr["t_dec"] - (C - 29 + 0.05)) < 1e-6 and fr.get("sendable") and fr.get("survive_s") == FAST_SURVIVE_S
       and fr.get("send_at") == "decision",
       "fast decides on the print's arrival (rel -29 + 50 ms), survive 75 ms, sendable (t_dec %.3f)" % (fr["t_dec"] - C))
    cr = [r for r in sk if r["ev"] == "taker_order" and r.get("v") == "ctrl" and r["rel"] == -29]
    ck(len(cr) == 1, "world 3: the control did decide and order at rel -29 (0.2 s after the second)")
    res = [r for r in sk if r["ev"] == "result"]
    ck(len(res) == 1 and res[0]["src"] == "ws" and res[0]["fast"]["send"]["contracts"] == 50
       and abs(res[0]["fast"]["send"]["pnl"] - (50 * 0.2 - 0.56)) < 1e-9 and res[0]["ctrl"]["raw"]["contracts"] == 0,
       "world 3 settles from the WS 'determined' event: fast +9.44 on 50, control 0 contracts")
    pr = [r for r in sk if r["ev"] == "pair" and r["rel"] == -29]
    ck(len(pr) == 1 and pr[0]["fast"]["real"] and pr[0]["ctrl"]["miss"] and pr[0]["ctrl"]["dec"]["p"] > 0.99
       and abs(pr[0]["ctrl"]["dec"]["lag"] - 0.2) < 0.021 and abs(pr[0]["fast"]["dec"]["lag"] - 0.05) < 1e-6,
       "world 3: one pair record carries both arms (fast fill, control miss, both decision times and p)")
    ck(sum(1 for r in sk if r["ev"] == "pair") == 1, "world 3: exactly one pair (only rel -29 had orders)")

    # world 1: the offer is taken 0.15 s after the second -- after the fast check (0.125), before the control decides
    rn, sk = sim((CTRL_ARM, FAST_ARM), book, [(-29 + 0.15, delta("no", "0.2000", "-50.00"))])
    ck(fills(sk, "fast") == [("yes", 0.8, 50, -29)] and not fills(sk, "ctrl")
       and not any(r["ev"] == "taker_order" and r.get("v") == "ctrl" for r in sk),
       "world 1: offer gone at +0.15 s -> fast fills 50, the control never sees it (no order)")
    # check precision: gone 70 ms after the decision -> fast miss; gone 80 ms after -> fast fill; with a 50-ms loop
    for dt, want, nm in ((0.070, [], "miss"), (0.080, [("yes", 0.8, 50, -29)], "fill")):
        rn, sk = sim((CTRL_ARM, FAST_ARM), book, [(-29 + 0.05 + dt, delta("no", "0.2000", "-50.00"))], loop_dt=0.05)
        ck(fills(sk, "fast") == want, "75-ms check is exact on message time (50-ms loop): gone at +%d ms -> %s (%s)"
           % (round(dt * 1000), nm, fills(sk, "fast")))
    # the offer is taken 3 ms after the print arrives, inside the same 20-ms loop pass: the fast arm decided on the
    # print message itself (it saw the offer, ordered) and misses at its check; deciding on the pass would never order
    rn, sk = sim((CTRL_ARM, FAST_ARM), book, [(-29 + 0.053, delta("no", "0.2000", "-50.00"))])
    fo = [r for r in sk if r["ev"] == "taker_order" and r.get("v") == "fast" and r["rel"] == -29]
    fm_ = [r for r in sk if r["ev"] == "taker_miss" and r.get("v") == "fast" and r["rel"] == -29]
    ck(len(fo) == 1 and len(fm_) == 1 and fm_[0]["why"] == "gone" and not fills(sk, "fast"),
       "offer taken 3 ms after the print, same loop pass: fast decided on the print (ordered 50), then missed at 75 ms "
       "(orders %d, misses %s)" % (len(fo), [r["why"] for r in fm_]))
    # frames still in flight: every message reaches the loop 15 ms after its receive stamp (10-ms loop). The offer is
    # taken 2 ms before the fast 75-ms check; a loop pass lands just after the check, before that message is drained.
    # The fast clock runs SAFETY_S (20 ms) behind the loop, so the check waits for the message -> a miss. A clock run
    # at the loop's own time would judge the check on the stale book and book a fill that never existed.
    rn, sk = sim((CTRL_ARM, FAST_ARM), book, [(-29 + 0.125 - 0.002, delta("no", "0.2000", "-50.00"))], loop_dt=0.01,
                 deliver=0.015)
    fm_ = [r for r in sk if r["ev"] == "taker_miss" and r.get("v") == "fast" and r["rel"] == -29]
    ck(not fills(sk, "fast") and len(fm_) == 1 and fm_[0]["why"] == "gone",
       "frames in flight (15 ms): the fast check is not judged before a message stamped before it has been applied "
       "(fills %s, misses %s)" % (fills(sk, "fast"), [r["why"] for r in fm_]))
    # early prints (received 0.1 s BEFORE their own second by the local clock; review finding 5). The fast arm must
    # decide at the second exactly, with the book as it was then, not on the next 50-ms loop with a later book.
    rn, sk = sim((CTRL_ARM, FAST_ARM), book, [(-29 + 0.01, delta("no", "0.2000", "-50.00"))], lag=-0.1, loop_dt=0.05)
    fo = [r for r in sk if r["ev"] == "taker_order" and r.get("v") == "fast" and r["rel"] == -29]
    fm_ = [r for r in sk if r["ev"] == "taker_miss" and r.get("v") == "fast" and r["rel"] == -29]
    pr = [r for r in sk if r["ev"] == "pair" and r["rel"] == -29]
    ck(len(fo) == 1 and len(fm_) == 1 and fm_[0]["why"] == "gone" and not fills(sk, "fast")
       and len(pr) == 1 and abs(pr[0]["fast"]["dec"]["t"] - (C - 29)) < 1e-6,
       "early print, offer taken 10 ms after the second: fast decides AT the second (sees the offer), orders, and "
       "misses at its 75-ms check (orders %d, misses %s)" % (len(fo), [r["why"] for r in fm_]))
    rn, sk = sim((CTRL_ARM, FAST_ARM), bookn, [(-29 + 0.01, delta("no", "0.2000", "50.00"))], lag=-0.1, loop_dt=0.05)
    ck(fills(sk, "fast") == [("yes", 0.8, 50, -28)] and fills(sk, "ctrl") == [("yes", 0.8, 50, -29)],
       "early print, offer appears 10 ms after the second: fast's -29 decision cannot see it (buys at -28); the "
       "control, deciding at +0.2 s, buys at -29 (%s / %s)" % (fills(sk, "fast"), fills(sk, "ctrl")))
    # feed faults (review finding 4): a sequence gap, then a WebSocket drop, each before a fresh snapshot at -10.5 s
    snap = {"type": "orderbook_snapshot", "msg": dict(book, market_ticker="BTC-T")}
    rn, sk = sim((CTRL_ARM, FAST_ARM), book, [(-35.0, dict(delta("yes", "0.0100", "1.00"), _skip=1)),
                                              (-10.5, json.loads(json.dumps(snap)))])
    orel = sorted({(r.get("v"), r["rel"]) for r in sk if r["ev"] == "taker_order"})
    ck(sum(1 for r in sk if r["ev"] == "seq_gap") == 1 and rn.lead.n_gaps == 1 and rn.lead.resync_wanted
       and orel == [("ctrl", -10), ("fast", -10)]
       and fills(sk, "fast") == [("yes", 0.8, 50, -10)] and fills(sk, "ctrl") == [("yes", 0.8, 50, -10)],
       "sequence gap at -35 s: books unsynced, resync asked, no order by either arm until the fresh snapshot "
       "(orders at %s)" % orel)
    rn, sk = sim((CTRL_ARM, FAST_ARM), book, [(-28.5, {"type": "_ws_down"}), (-20.0, {"type": "_ws_up"}),
                                              (-10.5, json.loads(json.dumps(snap)))])
    cm = [r for r in sk if r["ev"] == "taker_miss" and r.get("v") == "ctrl" and r["rel"] == -29]
    orel = sorted({(r.get("v"), r["rel"]) for r in sk if r["ev"] == "taker_order"})
    ck(fills(sk, "fast") == [("yes", 0.8, 50, -29)] and len(cm) == 1 and cm[0]["why"] == "book_unsynced"
       and orel == [("ctrl", -29), ("ctrl", -10), ("fast", -29)] and fills(sk, "ctrl") == [("yes", 0.8, 50, -10)]
       and rn.ws_up_seen,
       "WebSocket drop at -28.5 s: control's pending -29 order misses (book unsynced), nothing is ordered on the "
       "dead or reconnected-but-unsnapshotted book, and buying resumes after the fresh snapshot (orders %s, ctrl miss %s)"
       % (orel, [r["why"] for r in cm]))
    # crash guard: a YES ask at 60c (below the 75c floor, nobody buys it) is on the book from the start
    bookc = {"no_dollars_fp": [["0.2000", "50.00"], ["0.4000", "5.00"]], "yes_dollars_fp": [["0.0100", "40.00"]]}
    rn, sk = sim((CTRL_ARM, FAST_ARM), bookc)
    fc, cc_ = flags(sk, "fast"), flags(sk, "ctrl")
    ck(fc and cc_ and all(x[5] and not x[4] for x in fc + cc_),
       "crash: best ask 60c under an 80c buy -> both arms' real fills flagged crash, not sendable (%s / %s)" % (fc, cc_))
    res = [r for r in sk if r["ev"] == "result"]
    ck(len(res) == 1 and all(res[0][a]["raw"]["contracts"] == 50 and res[0][a]["send"]["contracts"] == 0
                             and res[0][a]["send"]["pnl"] == 0 for a in ("ctrl", "fast")),
       "crash: the result record counts the refused fills as raw (50) and not as sendable (0)")
    ck(rn.engines[0].close_spent is not rn.engines[1].close_spent and rn.engines[0].markets is not rn.engines[1].markets
       and rn.engines[0].books is rn.engines[1].books,
       "each arm has its own positions and close caps; only the book is shared")
    rn2 = Runner(tb, lambda: C + 10.0, sink=[])
    ck(rn2.add_market("OLD-T", "BTC", C, Decimal("100"), 2, "planted") is None
       and not any("OLD-T" in e.markets for e in rn2.engines),
       "a market the control refuses as already closed is given to no arm (the fast clock may be stale)")
    # the collapse appears 0.5 s after the print: control's 1-s trigger sees it, the fast decision did not
    rn, sk = sim((CTRL_ARM, FAST_ARM), book, [(-29 + 0.5, delta("no", "0.4000", "5.00"))])
    fc, cc_ = flags(sk, "fast"), flags(sk, "ctrl")
    ck(fc == [("yes", 0.8, 50, -29, True, False, False)] and cc_ == [("yes", 0.8, 50, -29, False, True, False)],
       "crash after the decision: control flagged at its 1-s trigger, fast (sent at the decision) not (%s / %s)" % (fc, cc_))
    # the collapse lands between the fast decision (+50 ms) and its 75-ms check (+125 ms): a fast live order was
    # already sent, so the guard (which may only use what the sender saw) must NOT refuse it
    rn, sk = sim((CTRL_ARM, FAST_ARM), book, [(-29 + 0.10, delta("no", "0.4000", "5.00"))])
    fc, cc_ = flags(sk, "fast"), flags(sk, "ctrl")
    ck(fc == [("yes", 0.8, 50, -29, True, False, False)] and cc_ == [("yes", 0.8, 50, -29, False, True, False)],
       "collapse between the fast decision and its check: fast not refused (no future information), control refused "
       "(%s / %s)" % (fc, cc_))
    # late rule. Control: offer appears at -1.6 s, prints 0.6 s late -> control check at -0.4 s > close-0.5 -> late
    rn, sk = sim((CTRL_ARM, FAST_ARM), bookn, [(-1.6, delta("no", "0.2000", "50.00"))], lag=0.6)
    fc, cc_ = flags(sk, "fast"), flags(sk, "ctrl")
    ck(fc == [("yes", 0.8, 50, -2, True, False, False)] and cc_ == [("yes", 0.8, 50, -2, False, False, True)],
       "late: control's 1-s trigger at close-0.4 s is late; fast sent at close-1.4 s is not (%s / %s)" % (fc, cc_))
    rn, sk = sim((CTRL_ARM, FAST_ARM), bookn, [(-0.6, delta("no", "0.2000", "50.00"))], lag=0.6)
    fc, cc_ = flags(sk, "fast"), flags(sk, "ctrl")
    ck(fc == [("yes", 0.8, 50, -1, False, False, True)] and cc_ == []
       and any(r["ev"] == "taker_miss" and r.get("v") == "ctrl" and r["why"] == "closed" for r in sk),
       "late: fast decision at close-0.4 s is flagged late; control's check falls after the close (%s / %s)" % (fc, cc_))
    # NULL 2 (nothing planted): a steady book -> both arms make the same fills; the read finds D = 0 exactly
    rn, sk = sim((CTRL_ARM, FAST_ARM), book)
    ck(flags(sk, "ctrl") == flags(sk, "fast") and flags(sk, "fast"),
       "NULL 2: steady book -> fast and control fill the same (%s)" % flags(sk, "fast"))
    rd = read_log(json.dumps(r, default=str) for r in sk)
    ck(rd["D"] is not None and abs(rd["D"]) < 1e-9 and rd["verdict"] == "NOT READY",
       "NULL 2: the read gives D = 0.00c and NOT READY (D %s)" % rd["D"])
    # empty worlds
    rn, sk = sim((CTRL_ARM, FAST_ARM), {"no_dollars_fp": [], "yes_dollars_fp": []})
    ck(not [r for r in sk if r["ev"] in ("fill", "taker_order")], "empty book: neither arm does anything")
    rn, sk = sim((CTRL_ARM, FAST_ARM), {"no_dollars_fp": [["0.2000", "500.00"]], "yes_dollars_fp": [["0.2000", "500.00"]]},
                 vals=("99.994", "99.996"))
    ck(not [r for r in sk if r["ev"] in ("fill", "taker_order") and r["rel"] < -1],
       "coin-flip world (index on the strike, 80c both sides): no order while the outcome is open")
    ck(all(r["side"] == "yes" for r in sk if r["ev"] == "fill" and r["rel"] == -1),
       "coin-flip world, last second: the exact 60-print mean (99.995 = the threshold) is certain YES; only YES is bought")
    rn, sk = sim((CTRL_ARM, FAST_ARM), book, determined=False)
    ck(not [r for r in sk if r["ev"] == "result"] and rn.rest_settle_wanted(C + 100.0, {}) == ["BTC-T"]
       and rn.rest_settle_wanted(C + 99.0, {}) == [],
       "no 'determined' event: no result is invented; REST is asked only from close+100 s")
    rn.feed(C + 101, {"type": "_rest_result", "ticker": "BTC-T", "result": "no", "expiration_value": "99"})
    rr = [r for r in sk if r["ev"] == "result"]
    ck(len(rr) == 1 and rr[0]["src"] == "rest" and rr[0]["result"] == "no" and rr[0]["fast"]["send"]["pnl"] < 0,
       "REST fallback settles it (a NO result loses the YES bought)")
    # the 'determined' event is applied only once the market is done and 3 s past the close
    rn, sk = sim((CTRL_ARM, FAST_ARM), book, t1=2.5)
    ck(not [r for r in sk if r["ev"] == "result"] and "BTC-T" in rn.ws_results, "determined at close+1 s waits until close+3 s")
    rn.loop_end(C + 3.0)
    ck(len([r for r in sk if r["ev"] == "result"]) == 1 and not rn.lead.markets, "... and settles then, releasing the market")
    # discovery
    rn = Runner(tb, lambda: C - 500.0, sink=[])
    ck(set(rn.discovery_need(C - 500.0)) == set(B.COINS), "no markets: every coin needs discovery")
    rn.add_market("BTC-X", "BTC", C, Decimal("100"), 2, "custom_strike")
    rn.add_market("DOGE-X", "DOGE", C, Decimal("0.2"), 7, "custom_strike")
    n1 = rn.discovery_need(C - 500.0)
    rn.add_market("DOGE-X", "DOGE", C, Decimal("0.2000001"), 7, "prev_expiration_value")
    n2 = rn.discovery_need(C - 500.0)
    ck("BTC" not in n1 and "DOGE" in n1 and "DOGE" not in n2 and "ETH" in n2 and len(n2) == 7
       and rn.lead.markets["DOGE-X"].strike == Decimal("0.2000001"),
       "discovery: known BTC skipped; DOGE re-polled until its exact previous-settle strike lands")
    ck("BTC" in rn.discovery_need(C + 1.0), "after the close the next BTC market is needed")
    q0 = 1_792_210_500                            # a quarter-hour boundary (2026-10-17 04:15Z)
    ck([discovery_allowed(q0 + s) for s in (0, 30, 89, 90, 450, 840, 841, 899)]
       == [False, False, False, True, True, True, False, False],
       "discovery never runs in the 90 s after a quarter-hour or the last minute before one")
    # REST pacing: >= 2 s between calls, 10 s after a 429
    clk = [0.0]
    calls = []

    def fake_get(path, params, auth=True):
        calls.append((clk[0], path, auth))
        return (429, "rate") if len(calls) == 2 else (200, {"markets": []})
    rs = PacedRest(queue.Queue(), B.Logger(None, []), fake_get, sleep_fn=lambda s: clk.__setitem__(0, clk[0] + s),
                   time_fn=lambda: clk[0])
    rs.poll_coins(["BTC", "ETH", "DOGE"])
    gaps = [b[0] - a[0] for a, b in zip(calls, calls[1:])]
    # the bars are the LITERAL hard limits (1 call / 2 s, 10 s after a 429), never this file's own constants
    # (review finding 3: comparing with REST_MIN_GAP_S itself let 1.0 s / 3 s pass)
    ck(len(calls) == 5 and all(g >= 2.0 - 1e-9 for g in gaps) and gaps[1] >= 10.0 - 1e-9
       and not any(c[2] for c in calls) and rs.n_429 == 1,
       "REST: 3 coins + DOGE's settled list = 5 public GETs >= 2.0 s apart, the 429 retried after >= 10.0 s, never "
       "authenticated (gaps %s)" % gaps)
    ck(REST_MIN_GAP_S >= 2.0 and REST_429_BACKOFF_S >= 10.0 and DISCOVER_EVERY_S >= 30.0 and REST_SETTLE_AFTER_S >= 90.0
       and REST_SETTLE_REASK_S >= 30.0 and RSS_CAP_MB <= 150.0,
       "limits (literal): REST >= 2.0 s apart, 429 wait >= 10.0 s, discovery >= 30 s apart, REST settle >= close+90 s "
       "and re-asked >= 30 s apart, memory cap <= 150 MB")
    ck((CRASH_GAP, LATE_S, FAST_OFFSET, FAST_SURVIVE_S, LATE_PRINT_S) == (0.10, 0.5, 0.0, 0.075, 0.3),
       "the spec's arm constants (literal): crash gap 0.10, late 0.5 s, fast offset 0, fast survival 75 ms, late print 0.3 s")
    # lock + stop file
    tmp = tempfile.mkdtemp(prefix="fcfast_st_")
    lk = os.path.join(tmp, "x.lock")
    with open(lk, "w") as f:
        f.write("0")
    ck(take_lock(lk) is None, "a lock held by no live process is taken")
    with open(lk, "w") as f:
        f.write(str(os.getppid() if hasattr(os, "getppid") else 4))
    held = take_lock(lk)
    ck(held is not None or not pid_alive(os.getppid()), "a lock held by a live process refuses a second run")
    with open(lk, "w") as f:
        f.write(str(os.getpid()))
    drop_lock(lk)
    ck(not os.path.exists(lk), "our own lock is removed at exit")
    sp = os.path.join(tmp, "x.stop")
    no_stop = not stop_requested(sp)
    open(sp, "w").close()
    ck(no_stop and stop_requested(sp), "the stop file is seen when present, not before")
    os.remove(sp)
    try:
        os.rmdir(tmp)
    except OSError:
        pass
    ck(B.rss_mb() > 0, "the working-set reader works here (the 140 MB cap can fire)")

    # the reader on planted logs ------------------------------------------------------------------------------------
    def planted(n_closes, fast_px, ctrl_px, fast_px2=None, ctrl_px2=None, extra_bad=True, fast_n=lambda i: 2):
        out = []
        for i in range(n_closes):
            cs = C + 900 * i
            tk = "T%d" % i
            second = i >= n_closes // 2
            fp = fast_px2 if (second and fast_px2 is not None) else fast_px
            cp = ctrl_px2 if (second and ctrl_px2 is not None) else ctrl_px
            out.append({"ev": "market", "v": "ctrl", "ticker": tk})
            out.append({"ev": "result", "ticker": tk, "close_s": cs, "result": "yes"})
            for j in range(fast_n(i)):
                out.append({"ev": "fill", "v": "fast", "strat": "forecaster", "fill": "real", "ticker": tk, "rel": -10 - j,
                            "side": "yes", "price": fp, "size": 100, "fee": 0.0, "sendable": True, "rx_lag": 0.05})
            out.append({"ev": "fill", "v": "ctrl", "strat": "forecaster", "fill": "real", "ticker": tk, "rel": -10,
                        "side": "yes", "price": cp, "size": 100, "fee": 0.0, "sendable": True, "rx_lag": 0.05})
            if extra_bad:                         # must be ignored: crash-refused, and an unsettled market
                out.append({"ev": "fill", "v": "fast", "strat": "forecaster", "fill": "real", "ticker": tk, "rel": -5,
                            "side": "no", "price": 0.9, "size": 100, "fee": 0.0, "sendable": False, "crash": True})
                out.append({"ev": "fill", "v": "fast", "strat": "forecaster", "fill": "real", "ticker": "U%d" % i,
                            "rel": -5, "side": "no", "price": 0.9, "size": 100, "fee": 0.0, "sendable": True})
        return [json.dumps(x) for x in out]
    r1 = read_log(planted(120, 0.97, 0.99))
    ck(r1["verdict"] == "PASS" and abs(r1["D"] - 2.0) < 1e-6 and r1["fast_send_fills"] == 240 and r1["fast_send_closes"] == 120,
       "reader: fast +3c vs control +1c on 240 fills / 120 closes -> D +2.00c, PASS at the boundary (%s, %s)"
       % (r1["verdict"], r1["D"]))
    r2 = read_log(planted(120, 0.99, 0.97))
    ck(r2["verdict"] == "KILL" and abs(r2["D"] + 2.0) < 1e-6, "reader: D -2.00c -> KILL")
    r3 = read_log(planted(120, 0.98, 0.99))
    ck(r3["verdict"] == "NO PASS" and abs(r3["D"] - 1.0) < 1e-6, "reader: D +1.00c -> NO PASS (neither)")
    r4 = read_log(planted(120, 0.90, 0.99, fast_px2=0.99, ctrl_px2=0.97))
    ck(r4["verdict"] == "NO PASS" and r4["D"] >= 2.0 and r4["halves"][0]["D"] > 0 and r4["halves"][1]["D"] < 0,
       "reader: D %+.2fc overall but the second half is %+.2fc -> NO PASS" % (r4["D"], r4["halves"][1]["D"]))
    r5 = read_log(planted(60, 0.97, 0.99))
    ck(r5["verdict"] == "NOT READY" and r5["fast_send_fills"] == 120, "reader: 120 fills over 60 closes -> NOT READY")
    r6 = read_log([])
    ck(r6["verdict"] == "NOT READY" and r6["D"] is None and r6["fast_send_fills"] == 0, "reader: empty log -> NOT READY, no crash")
    # every number in the bar, at its boundary (review finding 2: each of 200 / 100 / +2.0c / 0c could be edited and
    # the old planted reads still passed). Literal numbers here, never the BAR_* constants.
    rb = {"199 fills / 120 closes": read_log(planted(120, 0.97, 0.99, fast_n=lambda i: 2 if i < 79 else 1)),
          "240 fills / 99 closes": read_log(planted(99, 0.97, 0.99, fast_n=lambda i: 3 if i < 42 else 2)),
          "200 fills / 100 closes": read_log(planted(100, 0.97, 0.99))}
    ck([(x["fast_send_fills"], x["fast_send_closes"], x["verdict"]) for x in rb.values()]
       == [(199, 120, "NOT READY"), (240, 99, "NOT READY"), (200, 100, "PASS")],
       "reader counts (literal): 199 fills over 120 closes and 240 over 99 -> NOT READY; exactly 200 over 100 -> a "
       "verdict (%s)" % {k: x["verdict"] for k, x in rb.items()})
    rd_ = {"+1.99c": read_log(planted(120, 0.9701, 0.99)), "+0.50c": read_log(planted(120, 0.985, 0.99)),
           "0.00c": read_log(planted(120, 0.99, 0.99)), "-0.50c": read_log(planted(120, 0.995, 0.99))}
    want_d = {"+1.99c": (1.99, "NO PASS"), "+0.50c": (0.50, "NO PASS"), "0.00c": (0.0, "KILL"), "-0.50c": (-0.50, "KILL")}
    ck(all(abs(rd_[k]["D"] - want_d[k][0]) < 1e-6 and rd_[k]["verdict"] == want_d[k][1] for k in want_d),
       "reader D (literal): +1.99c -> NO PASS (PASS needs +2.0c), +0.50c -> NO PASS, 0.00c and -0.50c -> KILL (%s)"
       % {k: (round(x["D"], 4), x["verdict"]) for k, x in rd_.items()})
    r7 = read_log(planted(120, 0.95, 0.99, fast_px2=0.99, ctrl_px2=0.99))
    ck(r7["D"] >= 2.0 - 1e-9 and abs(r7["halves"][1]["D"]) < 1e-9 and r7["halves"][0]["D"] > 2.0
       and r7["verdict"] == "NO PASS",
       "reader: D +2.00c overall but the second half is exactly 0 -> NO PASS (both halves must be positive) (%s)"
       % r7["verdict"])
    # control-vs-live validity check on planted logs
    def J(x):                                     # the live logs are written compact (bettor_paper.Logger)
        return json.dumps(x, separators=(",", ":"))
    ctrl_keys = {("M%d" % i, -10, "yes", 0.8) for i in range(10)}
    live = ([J({"ev": "market", "ticker": "M%d" % i}) for i in range(10)]
            + [J({"ev": "settle", "ticker": "M%d" % i, "result": "yes"}) for i in range(10)]
            + [J({"ev": "fill", "strat": "forecaster", "fill": "real", "ticker": "M%d" % i, "rel": -10,
                  "side": "yes", "price": 0.8}) for i in range(10)])
    orders = [J({"ev": "start", "variant": LIVE_VARIANT, "crash_gap": 0.1})]
    cc1 = check_control({"M%d" % i for i in range(10)}, ctrl_keys, {"M%d" % i for i in range(10)}, live, orders)
    ctrl8 = {k for k in ctrl_keys if k[0] not in ("M0", "M1")}
    cc2 = check_control({"M%d" % i for i in range(10)}, ctrl8, {"M%d" % i for i in range(10)}, live, orders)
    cc3 = check_control({"M%d" % i for i in range(10)}, ctrl_keys, {"M%d" % i for i in range(10)}, live,
                        [J({"ev": "start", "variant": "base", "crash_gap": None})])
    ck(cc1["valid"] and cc1["live_sides_in_ctrl"] == 1.0 and not cc2["valid"]
       and abs(cc2["live_sides_in_ctrl"] - 0.8) < 1e-9 and not cc3["valid"],
       "validity: 10/10 market-sides -> valid; 8/10 -> CONTROL DOES NOT REPRODUCE LIVE; a changed live variant -> invalid")
    jit = {("M%d" % i, -9, "yes", 0.81): 1.0 for i in range(10)}      # same market-sides, other second and price
    cc4 = check_control({"M%d" % i for i in range(10)}, jit, {"M%d" % i for i in range(10)}, live, orders)
    few = {("M%d" % i, -10, "yes", 0.8): 0.7 for i in range(10)}      # same keys, 30% fewer contracts
    cc5 = check_control({"M%d" % i for i in range(10)}, few, {"M%d" % i for i in range(10)}, live, orders)
    ck(cc4["valid"] and cc4["exact_live_in_ctrl"] == 0.0 and not cc5["valid"] and cc5["exact_live_in_ctrl"] == 1.0,
       "validity: other seconds/prices on the same market-sides (loop timing) -> valid; 30 in 100 fewer contracts -> invalid")
    # validity boundaries (literal 90 in 100 and 10 in 100; review finding 2: cc2 was rejected by contracts only)
    M100 = {"M%d" % i for i in range(100)}
    live100 = ([J({"ev": "market", "ticker": t}) for t in sorted(M100)]
               + [J({"ev": "settle", "ticker": t, "result": "yes"}) for t in sorted(M100)]
               + [J({"ev": "fill", "strat": "forecaster", "fill": "real", "ticker": t, "rel": -10, "side": "yes",
                     "price": 0.8}) for t in sorted(M100)])

    def sides_ctrl(n_off, yes_c=1.0, no_c=1.0):   # live has YES on M0..M99; control matches all but n_off of them
        d = {("M%d" % i, -10, "yes", 0.8): yes_c for i in range(n_off, 100)}
        d.update({("M%d" % i, -10, "no", 0.2): no_c for i in range(n_off)})
        return d
    vb = {"85 of 100 sides, equal contracts": check_control(M100, sides_ctrl(15), M100, live100, orders),
          "90 of 100 sides, equal contracts": check_control(M100, sides_ctrl(10), M100, live100, orders),
          "contracts 11 in 100 short": check_control(M100, sides_ctrl(0, 0.89), M100, live100, orders),
          "contracts 9 in 100 short": check_control(M100, sides_ctrl(0, 0.91), M100, live100, orders)}
    extra = {("M%d" % i, -10, "yes", 0.8): 0.9 for i in range(100)}
    extra.update({("M%d" % i, -10, "no", 0.2): 0.6 for i in range(15)})
    vb["all live sides + 15 control-only sides"] = check_control(M100, extra, M100, live100, orders)
    vb["crash gap 0.20 in the order log"] = check_control(M100, sides_ctrl(0), M100, live100,
                                                          [J({"ev": "start", "variant": LIVE_VARIANT, "crash_gap": 0.2})])
    vb["order log with no start record"] = check_control(M100, sides_ctrl(0), M100, live100,
                                                         [J({"ev": "order", "ticker": "M1"})])
    ck([x["valid"] for x in vb.values()] == [False, True, False, True, False, False, False]
       and abs(vb["85 of 100 sides, equal contracts"]["live_sides_in_ctrl"] - 0.85) < 1e-9
       and vb["85 of 100 sides, equal contracts"]["live_contracts"] == vb["85 of 100 sides, equal contracts"]["ctrl_contracts"]
       and abs(vb["all live sides + 15 control-only sides"]["ctrl_sides_in_live"] - 100 / 115.0) < 1e-9,
       "validity (literal): 85 of 100 market-sides with equal contracts -> invalid, 90 of 100 -> valid; 11 in 100 "
       "fewer contracts -> invalid, 9 -> valid; 15 control-only sides -> invalid; crash gap 0.20 or no start record "
       "in the order log -> invalid (%s)"
       % {k: x["valid"] for k, x in vb.items()})
    # fail-closed (review finding 1): no live log / no order log -> invalid, never 'unchecked'
    cm1 = check_control(M100, sides_ctrl(0), M100, None, orders)
    cm2 = check_control(M100, sides_ctrl(0), M100, live100, None)
    cm3 = check_control(M100, sides_ctrl(0), M100, os.path.join(tempfile.gettempdir(), "fcfast_no_such_%d.jsonl"
                                                                % os.getpid()), orders)
    ck(not cm1["valid"] and not cm2["valid"] and not cm3["valid"] and "missing" in (cm2["why"] or ""),
       "validity: a missing live log or live order log -> invalid (%s / %s)" % (cm1["why"], cm2["why"]))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        vn = print_read(r1, None)
        vi = print_read(r1, cm2)
        vr = print_read(r5, None)
    ck(vn.startswith("CONTROL DOES NOT REPRODUCE LIVE") and vi.startswith("CONTROL DOES NOT REPRODUCE LIVE")
       and vr == "NOT READY",
       "print_read: a PASS with no control check, or a failed one, prints no verdict; NOT READY stays NOT READY")
    # ... and the --read entry point itself, on files: a planted PASS read with all logs, then each live log removed
    tmp2 = tempfile.mkdtemp(prefix="fcfast_rd_")
    try:
        pl = os.path.join(tmp2, "paper.jsonl")
        lv = os.path.join(tmp2, "live.jsonl")
        od = os.path.join(tmp2, "orders.jsonl")
        with open(pl, "w", encoding="utf-8") as f:
            f.write("\n".join(planted(120, 0.97, 0.99)) + "\n")
        with open(lv, "w", encoding="utf-8") as f:
            for i in range(120):
                f.write(J({"ev": "market", "ticker": "T%d" % i}) + "\n")
                f.write(J({"ev": "settle", "ticker": "T%d" % i, "result": "yes"}) + "\n")
                f.write(J({"ev": "fill", "strat": "forecaster", "fill": "real", "ticker": "T%d" % i, "rel": -10,
                           "side": "yes", "price": 0.99, "size": 100}) + "\n")
        with open(od, "w", encoding="utf-8") as f:
            f.write(orders[0] + "\n")
        with contextlib.redirect_stdout(io.StringIO()):
            v_all = read_main(pl, lv, od)
            os.remove(od)
            v_no_orders = read_main(pl, lv, od)
            os.remove(lv)
            v_no_live = read_main(pl, lv, od)
            v_no_log = read_main(os.path.join(tmp2, "absent.jsonl"), lv, od)
    finally:
        for fn in ("paper.jsonl", "live.jsonl", "orders.jsonl"):
            try:
                os.remove(os.path.join(tmp2, fn))
            except OSError:
                pass
        try:
            os.rmdir(tmp2)
        except OSError:
            pass
    ck(v_all == "PASS" and v_no_orders.startswith("CONTROL DOES NOT REPRODUCE LIVE")
       and v_no_live.startswith("CONTROL DOES NOT REPRODUCE LIVE") and v_no_log == "NOT READY",
       "--read on files: planted PASS with both live logs -> PASS; order log removed -> no verdict; live log removed "
       "-> no verdict; no paper log -> NOT READY (%s | %s | %s)" % (v_all, v_no_orders[:40], v_no_live[:40]))

    # live-config drift: the control is only the live rule while these hold
    try:
        boot = open(BOOT_ALL, encoding="utf-8", errors="replace").read()
        line = [ln for ln in boot.splitlines() if "forecaster_live.py" in ln and '"--live"' in ln]
        ck(len(line) == 1 and '"--variant", "%s"' % LIVE_VARIANT in line[0] and '"--crash-gap", "0.10"' in line[0],
           "boot_all.ps1 still runs forecaster_live --variant %s --crash-gap 0.10" % LIVE_VARIANT)
    except OSError as e:
        ck(False, "boot_all.ps1 unreadable: %s" % e)
    try:
        fl = open(FORECASTER_LIVE_SRC, encoding="utf-8").read()
        ck("\nLATE_S = 0.5\n" in fl and "best_ask < px - CRASH_GAP - 1e-9" in fl
           and 'late = "late" if now > o["close_s"] - LATE_S' in fl,
           "forecaster_live.py: LATE_S 0.5 and the crash test are as copied here")
    except OSError as e:
        ck(False, "forecaster_live.py unreadable: %s" % e)
    ck(FV.VARIANTS.get(LIVE_VARIANT) == {"race_x": 1.0, "race_p": 0.98, "r_max": 28}
       and B.DECIDE_OFFSET == 0.2 and B.SURVIVE_S == 1.0 and B.DECIDE_DEADLINE == 0.9
       and (B.F_MIN_PRICE, B.F_MAX_PRICE, B.F_MIN_EDGE, B.F_MAX_SIDE, B.F_MAX_CLOSE) == (0.75, 0.985, 0.02, 100, 400),
       "the live variant's parameters and bettor_paper's timing/caps are the ones this file assumes")
    # nothing here can send an order
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    bad = ["portfolio/" + "orders", "/port" + "folio", "PO" + "ST", "DEL" + "ETE", "url" + "open", "Req" + "uest(",
           "create_" + "order", "load_" + "quotes", "import " + "ordercli", "import " + "forecaster_live",
           "import " + "pintake", "import " + "replay"]
    ck(not [b for b in bad if b in src],
       "no order endpoint, write verb, live-order import or 2-3 GB tape loader in source (%s)" % [b for b in bad if b in src])


# ------------------------------------------------------------------------------------------------------------ main
def main():
    if any(a == "--live" or a.startswith("--live=") for a in sys.argv[1:]):
        raise SystemExit("REFUSING: this is a paper runner; --live is not accepted")
    ap = argparse.ArgumentParser(description="PAPER: live forecaster rule vs a fast-decision variant, one feed")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--read", action="store_true", help="apply the pre-registered bar to the log (read-only)")
    ap.add_argument("--minutes", type=float, default=20160)
    ap.add_argument("--log", default=LOG_PATH)
    ap.add_argument("--stop-file", default=STOP_FILE)
    a = ap.parse_args()
    t0 = time.time()
    B.selftest()                                  # raises on failure
    if not FV.selftest():
        raise SystemExit("fc_variants self-test failed; refusing to run")
    ok, okc, fails = selftest()
    if not ok:
        raise SystemExit("self-test failed; refusing to run")
    print("all self-tests passed in %.1fs" % (time.time() - t0), flush=True)
    if a.selftest:
        for c in okc:
            print("  ok:", c)
        return 0
    if a.read:
        read_main(a.log)
        return 0
    if os.path.exists(a.stop_file):
        raise SystemExit("stop file present: %s (remove it to start)" % a.stop_file)
    lock = a.log + ".lock"
    held = take_lock(lock)
    if held:
        raise SystemExit("already running: pid %s holds %s" % (held, lock))
    try:
        start = {"code_sha12": sha12(os.path.abspath(__file__)), "bettor_paper_sha12": sha12(B.__file__),
                 "fc_variants_sha12": sha12(FV.__file__), "args": vars(a), "python": sys.version.split()[0],
                 "arms": [CTRL_ARM, FAST_ARM], "variant_params": FV.VARIANTS[LIVE_VARIANT], "crash_gap": CRASH_GAP,
                 "late_s": LATE_S, "selftest_checks": len(okc), "bar": BAR_TEXT, "log": a.log, "stop_file": a.stop_file,
                 "rest": {"min_gap_s": REST_MIN_GAP_S, "backoff_429_s": REST_429_BACKOFF_S,
                          "discover_every_s": DISCOVER_EVERY_S, "discover_window_s": list(DISCOVER_WINDOW),
                          "settle_after_s": REST_SETTLE_AFTER_S},
                 "rss_cap_mb": RSS_CAP_MB}
        run_live(a.minutes, a.log, a.stop_file, start)
    finally:
        drop_lock(lock)
    return 0


if __name__ == "__main__":
    sys.exit(main())
