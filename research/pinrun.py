#!/usr/bin/env python3
# VERSION: 2026-09-08-pr1
"""pinrun.py -- pin, live, event-driven. Paper by default; --live sends size 1.

THE THREE PARTS, EACH PROVEN SEPARATELY BEFORE BEING JOINED HERE:
  EYES   livebook.LiveBook -- orderbook_delta over WebSocket, 26 ms median,
         top-3 verified identical to REST on live books. The REST poll it
         replaces was rate-limited into blindness: a 45-minute paper run
         logged 0 signals and 202 of 211 skips were "no_book", while a tape
         replay of the same three hours found 39 qualifying episodes.
  BRAIN  fair() below -- the settlement model, with TWO measured corrections
         the backtest does not have (see CORRECTIONS).
  HANDS  pintake.take -- IOC limit at the seen price, post_only False, rails
         checked before any send, proven on demo with real demo cash.

THE FROZEN RULE (results/PREREG_pin_live.md, written before any live order):
  tau <= 20 s, fair >= 0.98 (buy YES) or <= 0.02 (buy NO), edge >= 0.5c AFTER
  the taker fee, one fire per close, size 1. TAU_MAX is 20 and not 60 because
  the tau<=60 cell is below its own MDE out of sample (+0.25c vs MDE 0.86c)
  and produced 3 of the 4 wrong-side fires in today's replay, all at tau 38-60
  against markets that were right.

CORRECTIONS TO THE BACKTEST'S MODEL, both measured on this tape today:

  1. THE SETTLEMENT WINDOW IS [close-60, close-1], NOT [close-59, close].
     Checked against Kalshi's own avg_60s_data and the strike identity
     strike(N+1) == settle(N) on 108 of 108 markets. BRTI 00:45Z: floor strike
     79199.01; mean[c-60..c-1] = 79199.0060; mean[c-59..c] = 79199.3023. The
     tick labelled `close` is NOT in the settlement; the tick at close-60 IS.
     settlewin.partial(), endgame.fair() and pin.py all carry the old window,
     so at tau seconds to close they treat tau prints as remaining when tau-1
     remain -- they drop a locked print and substitute spot for it. Harmless
     where |mu-K| >> sd, fatal at small tau: the error is 135% of the true sd
     at tau=5 and 7.6x it at tau=2.

  2. THE SETTLEMENT IS ROUNDED TO THE STRIKE'S PRECISION BEFORE COMPARISON.
     custom_strike.round_digits is 2 for BTC/ETH/BNB and 4 for the rest;
     Kalshi rounds the 60-print mean to that many digits, writes it as
     expiration_value, and settles YES iff expiration_value >= floor_strike.
     So the true threshold is K - 0.5*10^-d, not K. A market lands inside that
     band 2.46% of the time (266 of 10,796 settled markets; DOGE 19.8% of the
     time, BTC never), so it is worth pricing correctly.

     RETRACTION, and it matters. This correction was first reported -- by the
     replay that found it, and repeated by me to the operator -- as the thing
     that turns the replayed three hours from -79.2c into +7.7c, because the
     single loss (KXETH15M-26SEP071745-45, strike 2492.82, settle 2492.8158 ->
     rounds to 2492.82 -> YES) sits in the band. RECONSTRUCTING THAT MARKET
     TICK BY TICK SHOWS THAT IS FALSE. With BOTH corrections applied, fair at
     tau=5 is 0.0052 -- still under the 0.02 gate, so pin still buys NO at
     0.903 and still loses 90.91c:

         tau   old window      +window fix    +rounding fix     sd
          10     0.5085          0.5471          0.6049       0.0338
           6     0.0145          0.0133          0.0294       0.0153
           5     0.0025          0.0013          0.0052       0.0113
           4     0.2476          0.2286          0.4577       0.0078

     The actual cause of that loss is SPOT SUBSTITUTION: the index dipped to
     2492.60 at tau 5-6, the model extrapolated the dip across the remaining
     prints, and the index came back to 2493.08 by tau=3. Both corrections are
     right and stay; neither prevents that trade. The honest statement is that
     the replayed three hours are 7 wins of +0.56 to +4.76c against one loss of
     -90.91c that the corrections DO NOT remove, and that n=12 closes says
     nothing about the edge either way.

RAILS, and why each one exists:
  * the abort block is the FIRST statement in the loop, before any branch.
    Last night's quoter had its loss check after the order block, so every
    stand-down `continue` skipped it and the run passed its own limit while
    reporting healthy. A structural self-test below fails if that pattern
    reappears here.
  * ONE fire per close, keyed on close_s -- the unit the backtest measured.
    Without it this loop would re-fire every iteration for as long as a stale
    quote stands: ~70 orders in one window across nine coins.
  * the level must hold at least our size in NON-fractional contracts. The
    book carries 0.01-0.83 contract dust; 13 of 52 qualifying episodes today
    were dust, including a 25-second "11.39c edge" of 0.02 contracts.
  * book and index staleness gates. A silently dead WS connection keeps a
    populated book with suspect=False for up to ~40 s.
  * pintake owns the money rails (count, price, IOC, post_only, tau, stake
    ledger, halt). This file may not send except through take().
"""
import argparse
import asyncio
import calendar
import json
import math
import os
import sys
import threading
import time
from collections import defaultdict, deque
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor, N_AVG                        # noqa: E402
import livebook                                             # noqa: E402
import pintake                                              # noqa: E402

sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
from kauth import get                                       # noqa: E402

ND = NormalDist()
RESULTS = r"C:\kals-repo\results"

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXBCH15M": "BCHUSD_RTI",
    "KXZEC15M": "ZECUSD_RTI", "KXHYPE15M": "HYPEUSD_RTI",
    "KXNEAR15M": "NEARUSD_RTI", "KXADA15M": "ADAUSD_RTI",
}

# ---- the frozen rule -------------------------------------------------------
PIN = 0.98
TAU_MAX = 20
TAU_MIN = 3            # a one-second misalignment is fatal below this
EDGE_FLOOR = 0.005     # AFTER fee
SIZE = 1               # contracts
MAX_BOOK_AGE_MS = 2000
MAX_INDEX_AGE_S = 2
SIGMA_WIN = 300
SIGMA_STRESS = 1.0     # multiply sigma by this before deciding (>1 = humbler)

# Filled in by arm() only when --live is given. Empty in paper mode, so a
# take() call cannot even be constructed without an explicit arming step.
CREDS = {"base": None, "pk": None, "key_id": None}


def arm(reason):
    """Load the production credentials and arm pintake. --live only."""
    import ordercli
    import kauth
    CREDS["base"] = pintake.PROD_ELECTIONS
    CREDS["key_id"] = kauth.KEY_ID
    CREDS["pk"] = ordercli.load_key(pintake.PROD_KEY_FILE)
    pintake.arm_prod(reason)
    return CREDS


# ===========================================================================
# THE INDEX, over WebSocket. Not the collector's file: re-reading a growing
# gzip once a second cost more than a second by the end of an hour, which is
# most of the "no_fair" skips in the old paper log.
# ===========================================================================
class IndexWS:
    """1/sec CF Benchmarks prints on our own authenticated connection."""

    def __init__(self, index_ids, key_id=None, key_file=None):
        self.ids = list(index_ids)
        self.ticks = defaultdict(dict)      # index_id -> {epoch_sec: value}
        self.order = defaultdict(lambda: deque(maxlen=1200))
        self.last_rx = {}                   # index_id -> local ms of last tick
        self.lock = threading.RLock()
        self.stats = defaultdict(int)
        kid, kfile = livebook._default_key()
        self.key_id = key_id or kid
        self.key_file = key_file or kfile
        self._stop = threading.Event()
        self._thread = None

    # ---- ingest (shared by the live socket and the self-test) ----
    def on_frame(self, raw, rx_ms=None):
        rx_ms = rx_ms if rx_ms is not None else livebook.now_ms()
        try:
            d = raw if isinstance(raw, dict) else json.loads(raw)
        except Exception:
            self.stats["unparseable"] += 1
            return
        if d.get("type") != "cfbenchmarks_value":
            self.stats[str(d.get("type"))] += 1
            return
        m = d.get("msg") or {}
        iid = m.get("index_id")
        if not iid:
            return
        try:
            data = m.get("data")
            data = json.loads(data) if isinstance(data, str) else (data or {})
            val = float(data["value"])
            sec = int(data["time"]) // 1000
        except Exception:
            self.stats["bad_tick"] += 1
            return
        with self.lock:
            if sec not in self.ticks[iid]:
                q = self.order[iid]
                if len(q) == q.maxlen and q:
                    self.ticks[iid].pop(q[0], None)
                q.append(sec)
            self.ticks[iid][sec] = val
            self.last_rx[iid] = rx_ms
        self.stats["ticks"] += 1

    # ---- reads ----
    def spot(self, iid):
        """(second, value, age_seconds) of the newest tick, or (None,None,None)."""
        with self.lock:
            d = self.ticks.get(iid)
            if not d:
                return None, None, None
            s = max(d)
            return s, d[s], time.time() - s

    def sigma(self, iid):
        with self.lock:
            d = dict(self.ticks.get(iid) or {})
        if len(d) < 30:
            return None
        secs = sorted(d)[-SIGMA_WIN:]
        diffs = [d[secs[i]] - d[secs[i - 1]]
                 for i in range(1, len(secs)) if secs[i] - secs[i - 1] == 1]
        if len(diffs) < 20:
            return None
        mu = sum(diffs) / len(diffs)
        return math.sqrt(sum((x - mu) ** 2 for x in diffs) / (len(diffs) - 1))

    def partial(self, iid, close_s, now_s):
        """(locked sum, how many settle prints are still to come), or None.

        THE WINDOW IS [close-60, close-1]. See CORRECTIONS 1 in the module
        docstring: measured against Kalshi's avg_60s_data on 108/108 markets.
        """
        with self.lock:
            d = self.ticks.get(iid)
            if not d:
                return None
            lo = close_s - N_AVG
            hi = min(now_s, close_s - 1)
            if hi < lo:
                return 0.0, N_AVG
            want = hi - lo + 1
            got = [d[s] for s in range(lo, hi + 1) if s in d]
        if not got or len(got) < want * 0.95:
            return None
        return sum(got) * (want / len(got)), N_AVG - want

    # ---- socket ----
    async def _run(self):
        import websockets
        sign = livebook.make_signer(self.key_id, self.key_file)
        cid = 0
        backoff = 0.5
        while not self._stop.is_set():
            try:
                path = "/trade-api/ws/v2"
                async with websockets.connect(
                        livebook.WS_URL, additional_headers=sign("GET", path),
                        ping_interval=20, ping_timeout=20, close_timeout=1,
                        max_size=8 * 1024 * 1024) as ws:
                    cid += 1
                    await ws.send(json.dumps({
                        "id": cid, "cmd": "subscribe",
                        "params": {"channels": ["cfbenchmarks_value"],
                                   "index_ids": self.ids}}))
                    self.stats["connects"] += 1
                    backoff = 0.5
                    while not self._stop.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        self.on_frame(raw)
            except Exception as e:                      # noqa: BLE001
                self.stats["ws_error"] += 1
                self.stats["last_error"] = str(e)[:120]
                if self._stop.is_set():
                    return
                await asyncio.sleep(backoff)
                backoff = min(8.0, backoff * 2)

    def start(self):
        def runner():
            try:
                asyncio.run(self._run())
            except Exception:                           # noqa: BLE001
                pass
        self._thread = threading.Thread(target=runner, daemon=True,
                                        name="indexws")
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()


# ===========================================================================
def eff_strike(strike, round_digits):
    """The threshold the EXCHANGE actually applies.

    Kalshi rounds the 60-print mean to round_digits and settles YES iff that
    rounded value >= floor_strike. round(v, d) >= K is v >= K - 0.5*10^-d.
    CORRECTIONS 2: this is the only loss in today's replay.
    """
    if round_digits is None:
        return float(strike)
    return float(strike) - 0.5 * (10.0 ** (-int(round_digits)))


def fair(idx, iid, close_s, now_s, strike, sigma, round_digits=None):
    """P(settle >= effective strike) with the locked prints already counted."""
    part = idx.partial(iid, close_s, now_s)
    if part is None:
        return None
    locked, r = part
    _, spot, _ = idx.spot(iid)
    if spot is None:
        return None
    K = eff_strike(strike, round_digits)
    mu = (locked + r * spot) / N_AVG
    if r <= 0:
        return 1.0 if mu >= K else 0.0
    sd = sigma * math.sqrt(var_factor(int(r), [1.0]))
    if sd <= 0:
        return 1.0 if mu >= K else 0.0
    return ND.cdf((mu - K) / sd)


def billed_fee(price, count=1):
    """The fee Kalshi ACTUALLY charges, not the raw formula.

    Measured over the account's whole taker fill history (8 fills, 0.02 to
    54.99 contracts): fee_cost == ceil(0.07*count*p*(1-p) to the next $0.0001)
    every time. Not nearest-rounded (0.0003387 -> 0.0004 and 0.0003450 ->
    0.0004 both refute that) and NOT rounded up to a whole cent, which would
    have killed a 1-3c edge at size 1. Using the ceiling here keeps the edge
    test conservative rather than flattering by up to 0.0075c.
    """
    raw = pintake.expected_fee(price, count)
    return math.ceil(raw * 10000.0) / 10000.0


def net_edge(f, price, want):
    """Edge in dollars per contract AFTER the taker fee at that price."""
    gross = (f - price) if want == "yes" else ((1.0 - f) - price)
    return gross - billed_fee(price, 1)


# ===========================================================================
def selftest():
    print("SELF-TEST -- pinrun")
    fails = []

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    idx = IndexWS(["TEST"])
    C = 1_000_000

    # --- CORRECTION 1: the window is [close-60, close-1] ---
    # plant a wild value at `close` (must be EXCLUDED) and at close-60
    # (must be INCLUDED).
    for s in range(C - 60, C):
        idx.ticks["TEST"][s] = 100.0
    idx.ticks["TEST"][C - 60] = 0.0          # inside the window
    idx.ticks["TEST"][C] = 1e6               # outside it
    locked, r = idx.partial("TEST", C, C)
    ck(r == 0, f"all 60 prints locked at now=close (remaining {r})")
    ck(abs(locked - (59 * 100.0)) < 1e-6,
       f"locked sum excludes tick@close and includes tick@close-60 "
       f"({locked:.1f}, expected 5900.0)")
    f = fair(idx, "TEST", C, C, 50.0, 1.0)
    ck(abs(f - 1.0) < 1e-9, f"decided yes on the corrected window (fair {f})")

    # the OLD window would have given a wildly different mean -- prove it
    old_locked = sum(idx.ticks["TEST"][s] for s in range(C - 59, C + 1))
    ck(abs(old_locked - locked) > 1e5,
       "old and new windows genuinely differ on this fixture")

    # --- CORRECTION 2: rounding to the strike's precision ---
    # the real losing market: strike 2492.82, settle 2492.8158, d=2 -> YES
    ck(abs(eff_strike(2492.82, 2) - 2492.815) < 1e-9,
       "eff_strike(2492.82, d=2) == 2492.815")
    idx2 = IndexWS(["E"])
    for s in range(C - 60, C):
        idx2.ticks["E"][s] = 2492.8158
    f_round = fair(idx2, "E", C, C, 2492.82, 1.0, round_digits=2)
    f_raw = fair(idx2, "E", C, C, 2492.82, 1.0, round_digits=None)
    ck(f_round == 1.0, f"rounding-aware fair calls the real ETH market YES "
                       f"({f_round})")
    ck(f_raw == 0.0, f"the un-rounded model calls it NO ({f_raw}) -- the "
                     f"-90.91c loss")

    # --- fee-netted edge ---
    e = net_edge(0.995, 0.99, "yes")
    fee = billed_fee(0.99, 1)
    ck(abs(e - (0.005 - fee)) < 1e-12,
       f"net edge subtracts the taker fee ({100 * e:.3f}c at p=0.99)")
    # the BILLED fee is the ceiling to $0.0001, measured on real fills
    ck(abs(billed_fee(0.95, 1) - 0.0034) < 1e-12,
       f"billed fee at p=0.95 is $0.0034, not the raw $0.003325 "
       f"({billed_fee(0.95,1)})")
    ck(billed_fee(0.98, 1) >= pintake.expected_fee(0.98, 1),
       "the billed fee is never below the raw formula (conservative)")
    ck(net_edge(0.9999, 0.995, "yes") > 0 > net_edge(0.9999, 0.9999, "yes"),
       "edge sign behaves at the boundary")
    # a NO take: fair 0.001, buying NO at 0.99 -> gross 0.999-0.99 = 0.9c
    ck(abs(net_edge(0.001, 0.99, "no") -
           (0.009 - billed_fee(0.99, 1))) < 1e-12,
       "NO-side edge is (1-fair) - price - fee")
    # the order bodies for both sides, built by pintake, checked by hand
    by = pintake.build_take("T-00", "yes", 0.9910, 1)
    bn = pintake.build_take("T-15", "no", 0.9890, 1)
    ck(by["side"] == "bid" and by["price"] == "0.9910",
       f"YES take is a bid at the seen price ({by['side']} {by['price']})")
    ck(bn["side"] == "ask" and bn["price"] == "0.0110",
       f"NO take at 0.989 is an ask at 0.0110 = the yes bid we hit "
       f"({bn['side']} {bn['price']})")
    ck(abs(pintake.stake(bn) - 0.9890) < 1e-9,
       f"a NO take at 0.989 costs $0.989, not $0.011 "
       f"(${pintake.stake(bn):.4f})")
    ck(by["post_only"] is False and bn["post_only"] is False,
       "both bodies have post_only False -- pin must cross, never rest")
    ck(by["time_in_force"] in ("immediate_or_cancel", "fill_or_kill"),
       f"tif never rests ({by['time_in_force']})")

    # --- index staleness ---
    idx3 = IndexWS(["S"])
    idx3.ticks["S"][int(time.time()) - 30] = 1.0
    _, _, age = idx3.spot("S")
    ck(age is not None and age > 25, f"stale index reports its age ({age:.0f}s)")

    # --- the frame parser, on a real-shaped message ---
    idx4 = IndexWS(["BRTI"])
    idx4.on_frame(json.dumps({
        "type": "cfbenchmarks_value", "sid": 2, "seq": 1,
        "msg": {"index_id": "BRTI", "received_at": 1788818400025,
                "data": json.dumps({"type": "value", "time": 1788818400000,
                                    "id": "BRTI", "value": "79046.47"})}}))
    ck(idx4.ticks["BRTI"].get(1788818400) == 79046.47,
       "on_frame parses a real cfbenchmarks_value frame")
    idx4.on_frame("not json")
    idx4.on_frame(json.dumps({"type": "orderbook_delta", "msg": {}}))
    ck(idx4.stats["unparseable"] == 1 and idx4.stats["ticks"] == 1,
       "junk and off-channel frames are counted, not fatal")

    # --- THE ABORT READS KEYS THAT ACTUALLY EXIST ---
    # The first version read led["halted"] and led["stake"]; pintake's ledger
    # has "halt" and "committed". Both checks were silently dead. A safety
    # check that reads a missing key is not a safety check, so the key names
    # are asserted against the real ledger here.
    led = pintake._fresh_ledger()
    for k in ("halt", "realised", "committed", "positions"):
        ck(k in led, f"pintake ledger has the key the abort reads: {k!r}")
    src_all = open(os.path.abspath(__file__), encoding="utf-8").read()
    # anchor on the real definition: the same literal appears in this
    # test, and index() would otherwise find the test itself.
    marker = chr(10) + "def risk_abort" + "(state, a):"
    abort_src = src_all[src_all.index(marker):]
    abort_src = abort_src[:abort_src.index(chr(10) + "# ====")]
    import re as _re
    # strip the docstring first: it NAMES the wrong keys as the bug being
    # described, and scanning it would fail on the very explanation.
    code_only = _re.sub(r'"""[\s\S]*?"""', "", abort_src, count=1)
    read = set(_re.findall(r"led(?:\[|\.get\()[\"']([a-z_]+)[\"']", code_only))
    ck(read and read <= set(led),
       f"every ledger key the abort reads exists ({sorted(read)})")

    # and the abort actually fires on each condition
    class _A:
        loss_abort = -2.00
        max_positions = 2
    saved = dict(pintake.LEDGER)
    try:
        pintake.LEDGER.update(_fresh := {"halt": None, "realised": -3.0,
                                         "committed": 0.0, "positions": {}})
        fired_on_loss = risk_abort({"halted": False, "errors": 0}, _A)
        ck(fired_on_loss and "loss abort" in fired_on_loss,
           f"abort fires on realised -3.00 vs limit -2.00 ({fired_on_loss})")
        pintake.LEDGER.update({"realised": 0.0,
                               "committed": pintake.MAX_RUN_STAKE})
        s2 = risk_abort({"halted": False, "errors": 0}, _A)
        ck(s2 and "stake cap" in s2, f"abort fires at the stake cap ({s2})")
        pintake.LEDGER.update({"committed": 0.0, "halt": "unknown order state"})
        s3 = risk_abort({"halted": False, "errors": 0}, _A)
        ck(s3 and "halted" in s3, f"abort fires on a pintake halt ({s3})")
    finally:
        pintake.LEDGER.clear()
        pintake.LEDGER.update(saved)

    # --- STRUCTURAL: the abort must precede every branch in the loop ---
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src[src.index("def trade_loop("):]
    body = body[body.index("    while "):]
    i_abort = body.find("risk_abort(")
    i_cont = body.find("continue")
    ck(i_abort != -1 and (i_cont == -1 or i_abort < i_cont),
       "risk_abort() runs before the first `continue` in the loop")

    # --- STRUCTURAL: no send except through pintake.take ---
    # build the needles at runtime so this test does not match itself
    needles = ["ordercli" + ".send(", "url" + "open(", "http" + ".client"]
    hits = [n for n in needles if n in src]
    ck(not hits, f"no direct send path in this file (found {hits})")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ===========================================================================
def risk_abort(state, a):
    """FIRST statement in the loop. Never behind a branch.

    THE KEY NAMES ARE CHECKED BY A SELF-TEST. The first version of this
    function read led["halted"] and led["stake"], neither of which exists
    in pintake's ledger ("halt" and "committed" do), so both checks were
    dead -- the same shape of defect as last night's abort that sat behind
    a `continue`. A check that reads a missing key is not a check.
    """
    if state["halted"]:
        return "already halted"
    led = pintake.LEDGER
    if led.get("halt"):
        return f"pintake halted: {led['halt']}"
    if float(led.get("realised", 0.0)) <= a.loss_abort:
        return (f"loss abort: realised ${led['realised']:.2f} <= "
                f"${a.loss_abort:.2f}")
    if float(led.get("committed", 0.0)) >= pintake.MAX_RUN_STAKE:
        return f"stake cap reached: ${led['committed']:.2f} committed"
    if len(led.get("positions") or {}) >= a.max_positions:
        return (f"position cap: {len(led['positions'])} open "
                f">= {a.max_positions}")
    if state["errors"] >= 5:
        return f"{state['errors']} consecutive errors"
    return None


# ===========================================================================
def trade_loop(a, rec, book, idx, series_index):
    live = a.live
    fired = {}                 # close_s -> ticker we already fired on
    seen_markets = {}          # ticker -> (iid, close_s, strike, digits)
    uni_at = 0.0
    watching = set()
    open_pos = {}            # ticker -> (close_s, want, cost) awaiting settlement
    state = {"halted": False, "errors": 0, "signals": 0, "considered": 0}
    end = time.time() + a.minutes * 60


    def reconcile():
        """Book settled P&L so the loss abort is a REAL brake, not a nominal one.

        pin holds to settlement, which lands after the close. Without this the
        ledger's `realised` never moves and the only true bound on a run is the
        stake cap. Each closed position is looked up once; a market that has
        not finalised yet is left for the next pass.
        """
        for tk in list(open_pos):
            close_s, want, cost = open_pos[tk]
            if time.time() < close_s + 20:
                continue                      # not settled yet
            try:
                st, b = get("/markets/" + tk)
            except Exception:
                continue
            if st != 200 or not isinstance(b, dict):
                continue
            m = b.get("market") or {}
            if m.get("status") != "finalized":
                if time.time() > close_s + 900:
                    open_pos.pop(tk, None)    # give up rather than leak
                continue
            res = m.get("result")
            if res not in ("yes", "no"):
                open_pos.pop(tk, None)
                continue
            won = (res == want)
            pnl = (1.0 - cost) if won else (-cost)
            pintake.record_pnl(pnl, note=f"{tk} {want} vs {res}")
            open_pos.pop(tk, None)
            state["settled"] = state.get("settled", 0) + 1
            state["wins"] = state.get("wins", 0) + int(won)
            rec("settled", ticker=tk, want=want, result=res, cost=round(cost, 4),
                pnl_c=round(100 * pnl, 2),
                realised=round(pintake.LEDGER["realised"], 4))
            print(f"  SETTLED {tk} {want} vs {res} -> {100 * pnl:+.2f}c "
                  f"(run realised ${pintake.LEDGER['realised']:+.4f})")

    while time.time() < end:
        reconcile()
        stop = risk_abort(state, a)
        if stop:
            state["halted"] = True
            rec("halt", why=stop)
            print(f"  *** HALT: {stop}")
            break

        now = time.time()
        now_s = int(now)

        if now - uni_at > 20:
            uni_at = now
            try:
                fresh = {}
                for series, iid in series_index.items():
                    st, b = get("/markets", {"series_ticker": series,
                                             "status": "open", "limit": "4"})
                    if st != 200 or not isinstance(b, dict):
                        rec("skip", why=f"universe_http_{st}", series=series)
                        continue
                    for m in b.get("markets", []):
                        ct, sk = m.get("close_time"), m.get("floor_strike")
                        if not ct or sk is None:
                            continue
                        cs = calendar.timegm(time.strptime(
                            ct, "%Y-%m-%dT%H:%M:%SZ"))
                        if cs - now_s > 900 or cs < now_s:
                            continue
                        d = (m.get("custom_strike") or {}).get("round_digits")
                        fresh[m["ticker"]] = (iid, cs, float(sk),
                                              int(d) if d is not None else None)
                if fresh:
                    seen_markets = fresh
                    new = set(seen_markets) - watching
                    if new:
                        book.subscribe(sorted(new))
                        watching |= new
                        rec("watch", n=len(watching), added=sorted(new))
                state["errors"] = 0
            except Exception as e:                       # noqa: BLE001
                state["errors"] += 1
                rec("error", where="universe", err=str(e)[:200])

        for tk, (iid, close_s, strike, digits) in list(seen_markets.items()):
            tau = close_s - now_s
            if not (TAU_MIN <= tau <= TAU_MAX):
                continue
            if close_s in fired:
                continue
            try:
                b = book.best(tk)
            except Exception as e:                       # noqa: BLE001
                state["errors"] += 1
                rec("error", where="book", ticker=tk, err=str(e)[:200])
                continue
            if not b or b.get("suspect"):
                continue
            if b.get("age_ms") is None or b["age_ms"] > MAX_BOOK_AGE_MS:
                continue
            sec, spot, iage = idx.spot(iid)
            if spot is None or iage is None or iage > MAX_INDEX_AGE_S:
                continue
            sg = idx.sigma(iid)
            if sg is None:
                continue
            f = fair(idx, iid, close_s, now_s, strike, sg * SIGMA_STRESS,
                     round_digits=digits)
            if f is None:
                continue
            state["considered"] += 1

            want = price = size = None
            if f >= PIN:
                ya, ys = b.get("yes_ask"), b.get("yes_ask_size")
                if ya and ys and ya < 1.0:
                    want, price, size = "yes", ya, ys
            elif f <= 1.0 - PIN:
                na, ns = b.get("no_ask"), b.get("no_ask_size")
                if na and ns and na < 1.0:
                    want, price, size = "no", na, ns
            if want is None:
                continue
            if size < SIZE:                 # fractional dust is not a fill
                continue
            e = net_edge(f, price, want)
            if e < EDGE_FLOOR:
                continue

            state["signals"] += 1
            sig = dict(ticker=tk, want=want, price=round(price, 4),
                       fair=round(f, 5), tau=tau, edge_c=round(100 * e, 3),
                       size=size, strike=strike, digits=digits, spot=spot,
                       sigma=round(sg, 6), book_age_ms=b["age_ms"],
                       index_age_s=round(iage, 2))
            fired[close_s] = tk
            rec("signal", live=live, **sig)
            print(f"  SIGNAL {tk} tau={tau}s buy {want.upper()} @{price:.4f} "
                  f"fair {f:.4f} edge {100 * e:+.2f}c size {size:.2f}")

            if not live:
                open_pos[tk] = (close_s, want, price)
            if live:
                try:
                    out = pintake.take(CREDS["base"], CREDS["pk"],
                                       CREDS["key_id"], tk, want, price,
                                       SIZE, close_s)
                    rec("order", ticker=tk, **{k: v for k, v in out.items()
                                               if k != "raw"})
                    filled = float(out.get("filled") or 0)
                    if filled > 0:
                        px = out.get("exec_price")
                        cost = float(px) if px is not None else float(price)
                        open_pos[tk] = (close_s, want, cost)
                        state["fills"] = state.get("fills", 0) + 1
                    state["sent"] = state.get("sent", 0) + 1
                    print(f"    ORDER -> status {out.get('status')} "
                          f"filled {out.get('filled')} "
                          f"@ {out.get('exec_price')} fee {out.get('fee')}")
                except Exception as ex:                  # noqa: BLE001
                    state["errors"] += 1
                    rec("error", where="take", ticker=tk, err=str(ex)[:300])
                    print(f"    ORDER FAILED: {ex}")

        time.sleep(0.05)

    return state, fired


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--live", action="store_true",
                    help="send size-1 IOC takers. Default is paper.")
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--loss-abort", type=float, default=-2.00)
    ap.add_argument("--tau-max", type=int, default=TAU_MAX)
    ap.add_argument("--max-positions", type=int, default=3,
                    help="halt after this many open positions")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- nothing ran")

    globals()["TAU_MAX"] = a.tau_max
    runid = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    tag = "live" if a.live else "paper"
    logpath = os.path.join(RESULTS, f"pinrun-{tag}-{runid}.jsonl")

    def rec(kind, **kw):
        kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        kw["kind"] = kind
        try:
            with open(logpath, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(kw, default=str) + "\n")
        except Exception:
            pass

    print(f"  MODE {'LIVE size 1' if a.live else 'PAPER'}   "
          f"tau<={TAU_MAX}s  pin {PIN}  edge>={100 * EDGE_FLOOR:.1f}c net  "
          f"loss abort ${a.loss_abort:.2f}")
    print(f"  log {logpath}")
    rec("start", mode=tag, tau_max=TAU_MAX, pin=PIN, edge_floor=EDGE_FLOOR,
        size=SIZE, loss_abort=a.loss_abort, minutes=a.minutes)

    if a.live:
        arm(f"pinrun --live, size {SIZE}, frozen rule tau<={TAU_MAX}, "
            f"PREREG_pin_live.md")
        print(f"  ARMED: {CREDS['base']}  key {CREDS['key_id'][:8]}...  "
              f"stake cap ${pintake.MAX_RUN_STAKE:.2f}")
        rec("armed", base=CREDS["base"], stake_cap=pintake.MAX_RUN_STAKE)

    idx = IndexWS(sorted(set(SERIES_TO_INDEX.values()))).start()
    book = livebook.LiveBook()
    book.start()
    t0 = time.time()
    while time.time() - t0 < 25:
        if idx.stats.get("ticks", 0) > 10:
            break
        time.sleep(0.5)
    print(f"  index up: {idx.stats.get('ticks', 0)} ticks, "
          f"{len(idx.ticks)} feeds")
    rec("feeds", ticks=idx.stats.get("ticks", 0), feeds=sorted(idx.ticks))

    state = {}
    try:
        state, fired = trade_loop(a, rec, book, idx, SERIES_TO_INDEX)
    finally:
        rec("end", state=dict(state), ledger=dict(pintake.LEDGER),
            index_stats=dict(idx.stats))
        try:
            book.stop()
        except Exception:
            pass
        idx.stop()
    print(f"\n  {state.get('signals', 0)} signals, "
          f"{state.get('considered', 0)} evaluations")
    print(f"  ledger {dict(pintake.LEDGER)}")
    print(f"  log {logpath}")


if __name__ == "__main__":
    main()
