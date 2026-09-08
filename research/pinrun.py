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
import bisect
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
EDGE_FLOOR = 0.003     # AFTER fee. 0.5c -> 0.3c per
                       # results/PREREG_pin_live_AMENDMENT_1.md, written
                       # 2026-09-08 08:20Z BEFORE the change went live.
                       # Out of sample the 0.3c floor gave 389 closes,
                       # +2.76c/contract, t=+5.6, 1 flip in 359 dear trades
                       # (headroom 2.1x); the 0.5c floor gave 354 closes,
                       # +2.51c, t=+4.1, 3 flips in 333 (headroom 1.3x).
                       # Better on every dimension measured. REVERTS to
                       # 0.005 if the live flip rate exceeds 1.0%.
SIZE = 1               # contracts we buy (--size; 0.01 = a penny test)
MIN_LEVEL = 1.0        # the RESTING level must hold this much regardless of
                       # our own size: a 0.01-contract order against a
                       # 0.02-contract dust level is not a real fill test
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

        CORRECTION 3, found in adversarial review 2026-09-08 and fixed here.
        A second whose print HAS NOT ARRIVED is a print still to come, not a
        locked print to be guessed at. The first version ended the window at
        min(now_s, close_s-1) and then scaled the observed sum by
        want/len(got) -- it substituted the WINDOW MEAN for every missing
        second, the most recent one included.

        Measured on this feed 2026-09-08 (20 Hz, 90 s, BRTI + ETHUSD_RTI):
        the print for the CURRENT second is absent in 321 of 3,570 samples =
        9.0%, so this fired often. The error it makes is exactly
        (mean of the prints held) - (the print missing), and its sd against
        the model's own residual sd is

            tau     3      4      5      6      8     10     15     20
            ratio 1.97x  1.17x  0.79x  0.58x  0.36x  0.25x  0.12x  0.07x

        -- at tau<=5 the guess is as big as everything the model still treats
        as random, and it is signed AGAINST the latest move, which is exactly
        when a stale quote appears. Same class of error as CORRECTION 1.

        So the locked window now ends at the newest print actually held, and
        every second after it is counted in `remaining` and modelled with
        spot -- which is what the model says to do. Interior gaps are filled
        from the NEAREST print held, never from the window mean.
        """
        with self.lock:
            d = self.ticks.get(iid)
            if not d:
                return None
            lo = close_s - N_AVG
            hi = min(now_s, close_s - 1)
            if hi < lo:
                return 0.0, N_AVG
            have = [s for s in range(lo, hi + 1) if s in d]
            if not have:
                return None
            hi = have[-1]                 # the newest print we actually hold
            want = hi - lo + 1
            got = {s: d[s] for s in have}
        if len(got) < want * 0.95:
            return None
        if len(got) == want:
            return sum(got.values()), N_AVG - want
        keys = sorted(got)
        total = 0.0
        for s in range(lo, hi + 1):
            v = got.get(s)
            if v is None:                 # interior gap: nearest print held
                i = bisect.bisect_left(keys, s)
                cand = [k for k in (keys[i] if i < len(keys) else None,
                                    keys[i - 1] if i > 0 else None)
                        if k is not None]
                v = got[min(cand, key=lambda k: (abs(k - s), k))]
            total += v
        return total, N_AVG - want

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
    """Edge in dollars per contract AFTER the taker fee at that price.

    THE FEE IS BILLED ON THE ORDER, NOT ON ONE CONTRACT, and it is ceilinged
    to $0.0001. At --size 0.01 that floor dominates: 0.07*0.01*0.99*0.01 =
    $0.0000069 bills as $0.0001, which is 1.00c PER CONTRACT against the
    0.07c the raw formula gives. Netting the one-contract fee here would let
    a penny run fire on a +0.6c "edge" that is really -0.33c.
    """
    gross = (f - price) if want == "yes" else ((1.0 - f) - price)
    return gross - billed_fee(price, SIZE) / float(SIZE)


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

    # --- CORRECTION 3: a print that has NOT ARRIVED is not a locked print ---
    # A steady uptrend with the newest print still in flight. The first
    # version ended the locked window at now_s and scaled the observed sum by
    # want/len(got) -- imputing the WINDOW MEAN for the missing second, which
    # on a trend sits far below the latest print. The model then buys the
    # wrong side at ~99c. This fixture fails if that ever comes back.
    idx5 = IndexWS(["R"])
    for s in range(C - 60, C - 3):          # up to close-4; close-3 in flight
        idx5.ticks["R"][s] = 1000.0 + 1.0 * (s - (C - 60))
    lockd, r5 = idx5.partial("R", C, C - 3)
    ck(r5 == 3 and abs(lockd - sum(idx5.ticks["R"].values())) < 1e-9,
       f"the locked window ends at the newest print HELD, not at now "
       f"(remaining {r5}, locked {lockd:.1f})")
    spot5 = idx5.ticks["R"][C - 4]
    mu_new = (lockd + r5 * spot5) / N_AVG
    got_old = [idx5.ticks["R"][s] for s in range(C - 60, C - 2)
               if s in idx5.ticks["R"]]
    want_old = (C - 3) - (C - 60) + 1
    mu_old = (sum(got_old) * (want_old / len(got_old)) + 2 * spot5) / N_AVG
    K5 = mu_new - 0.005
    f_new = fair(idx5, "R", C, C - 3, K5, 0.02)
    f_old = ND.cdf((mu_old - K5) / (0.02 * math.sqrt(var_factor(2, [1.0]))))
    ck(f_new >= PIN and f_old <= 1.0 - PIN,
       f"with the newest print in flight on a rising index the corrected "
       f"model says YES (fair {f_new:.4f}); mean-imputation said NO "
       f"(fair {f_old:.4f}) -- a wrong-side buy at ~99c")

    # an interior gap is filled from the NEAREST print, never the window mean
    idx7 = IndexWS(["H"])
    for s in range(C - 60, C):
        idx7.ticks["H"][s] = 100.0
    idx7.ticks["H"][C - 30] = 999.0
    del idx7.ticks["H"][C - 31]
    lk, rr = idx7.partial("H", C, C)
    ck(rr == 0 and abs(lk - 6899.0) < 1e-9,
       f"an interior gap takes the nearest print ({lk}, expected 6899.0; "
       f"the window-mean rule would say {6799.0 * 60 / 59:.1f})")

    # and a window missing more than 5% of its prints is refused outright
    idx6 = IndexWS(["G"])
    for s in range(C - 60, C - 3):
        if (s - (C - 60)) % 7:
            idx6.ticks["G"][s] = 100.0
    ck(idx6.partial("G", C, C - 3) is None,
       "partial refuses a window missing more than 5% of its prints")

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
    # THE FEE SCALES WITH THE ORDER, NOT WITH ONE CONTRACT. The $0.0001
    # ceiling dominates a penny order: it is 1.00c per contract at size 0.01.
    ck(abs(billed_fee(0.99, 0.01) - 0.0001) < 1e-12,
       f"the billed fee on 0.01 contracts is the $0.0001 floor "
       f"({billed_fee(0.99, 0.01)})")
    _saved_size = SIZE
    try:
        globals()["SIZE"] = 0.01
        e_penny = net_edge(0.999, 0.99, "yes")
        ck(abs(e_penny - (0.009 - 0.01)) < 1e-12,
           f"at --size 0.01 a 0.9c gross edge is NEGATIVE once the order's "
           f"own fee is charged ({100 * e_penny:+.3f}c), where the "
           f"one-contract fee would have called it +0.83c")
    finally:
        globals()["SIZE"] = _saved_size
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
        # the FORWARD bound: realised only moves after settlement, so the
        # advertised -$2.00 has to be checked against what is still open.
        pintake.LEDGER.update({"realised": 0.0, "committed": 0.0,
                               "halt": None, "positions": {}})
        s4 = risk_abort({"halted": False, "errors": 0, "open_cost": 1.20}, _A)
        ck(s4 and "loss bound" in s4,
           f"abort fires FORWARD: $1.20 open plus one more contract would "
           f"pass -$2.00 ({s4})")
        s5 = risk_abort({"halted": False, "errors": 0, "open_cost": 0.90}, _A)
        ck(s5 is None,
           f"$0.90 open still leaves room for one more contract ({s5})")
        s6 = risk_abort({"halted": False, "errors": 0, "order_errors": 2}, _A)
        ck(s6 and "ORDER path" in s6,
           f"abort fires on order-path errors, which the universe pass "
           f"cannot reset ({s6})")
    finally:
        pintake.LEDGER.clear()
        pintake.LEDGER.update(saved)

    # --- the stake cap must measure CONCURRENT risk, not lifetime turnover ---
    saved2 = dict(pintake.LEDGER)
    try:
        pintake.reset_ledger()
        pintake.LEDGER["committed"] = 0.97
        pintake.record_pnl(+0.03, note="settled win")
        pintake.LEDGER["committed"] = max(
            0.0, float(pintake.LEDGER["committed"]) - 0.97)
        ck(abs(pintake.LEDGER["committed"]) < 1e-9,
           f"a settled position releases its stake "
           f"(committed {pintake.LEDGER['committed']:.4f})")
        ck(abs(pintake.LEDGER["realised"] - 0.03) < 1e-9,
           "and its P&L is booked to realised, which the abort reads")
    finally:
        pintake.LEDGER.clear()
        pintake.LEDGER.update(saved2)

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

    # --- STRUCTURAL: the order carries the market's own exchange_index ---
    # Every open crypto 15M market reads exchange_index 2 (all 11 series,
    # checked live 2026-09-08). pintake.take() defaults the field to 0, so
    # without this the order is routed to a shard the market is not on.
    ck("exchange_index=exi" in src,
       "take() is called with the market's exchange_index, not the default 0")
    ck('int(m.get("exchange_index") or 0)' in src,
       "exchange_index is read from the market record in the universe pass")

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
    # FORWARD-LOOKING LOSS BOUND. `realised` only moves once a position has
    # SETTLED, so a realised-only abort always allows one more contract while
    # an unsettled one is open -- and it is inert entirely if the settlement
    # reader is failing. This bounds what the run can still lose: realised,
    # minus every open position going to zero, minus one more contract at up
    # to $1.00. With the default -$2.00 the run can never have more than
    # ~$1.99 at risk, whatever the settlement reader does.
    worst = float(led.get("realised", 0.0)) - float(state.get("open_cost", 0.0))
    if worst - 1.00 * float(SIZE) < a.loss_abort - 1e-9:
        return (f"loss bound: realised ${float(led.get('realised', 0.0)):+.2f} "
                f"with ${float(state.get('open_cost', 0.0)):.2f} still open; "
                f"one more contract could take this run past "
                f"${a.loss_abort:.2f}")
    if len(led.get("positions") or {}) >= a.max_positions:
        return (f"position cap: {len(led['positions'])} open "
                f">= {a.max_positions}")
    if state.get("order_errors", 0) >= 2:
        return f"{state['order_errors']} errors on the ORDER path"
    if state["errors"] >= 5:
        return f"{state['errors']} consecutive errors"
    return None


# ===========================================================================
def _fresh_near():
    return {"best": None, "n": 0, "decided": 0, "tradeable": 0,
            "no_offer": 0, "undecided": 0, "dust": 0}


def trade_loop(a, rec, book, idx, series_index):
    live = a.live
    fired = {}                 # close_s -> ticker we already fired on
    seen_markets = {}          # ticker -> (iid, close_s, strike, digits, exi)
    uni_at = 0.0
    watching = {}            # ticker -> close_s, so closed ones drop out
    open_pos = {}            # ticker -> (close_s, want, cost) awaiting settlement
    # NEAR MISSES. "nothing fired" is not information; "the best on offer was
    # 0.2c and we need 0.5c" is. Per close, keep the best net edge seen on
    # each side and report it when the close passes, so a quiet run can be
    # told apart from a blind one.
    near = {}                # close_s -> dict of the best look at that close
    reported = set()
    recon_at = {}            # ticker -> when the settlement was last polled
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
            # THROTTLE. This runs at the top of a 20 Hz loop and a market that
            # has closed but not finalised is NOT popped -- unthrottled that
            # is ~18,000 blocking GETs per unsettled position, which is both a
            # rate-limit suicide (the failure that blinded the REST paper run)
            # and a stall of the trading loop: kauth.get times out at 20 s.
            if time.time() < recon_at.get(tk, 0.0) + 15.0:
                continue
            recon_at[tk] = time.time()
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
            # the taker fee is charged on the way in and is part of realised
            # P&L; leaving it out flatters the number the loss abort reads.
            pnl = (float(SIZE) * ((1.0 - cost) if won else (-cost))
                   - billed_fee(cost, SIZE))
            pintake.record_pnl(pnl, note=f"{tk} {want} vs {res}")
            # RELEASE the stake. pintake's ledger only ever ADDS to
            # "committed" on a fill and never gives it back, but the field
            # means "dollars at risk RIGHT NOW" and a settled position is no
            # longer at risk -- the cash is back. Without this the $5 cap is a
            # cap on LIFETIME turnover (~5 bets at size 1) rather than on
            # concurrent exposure, and an overnight run halts on its own
            # success. pin holds for <60 s and closes are 15 min apart, so
            # concurrent exposure is one bet, not the night's turnover.
            pintake.LEDGER["committed"] = max(
                0.0, float(pintake.LEDGER.get("committed", 0.0)) - cost)
            pintake.LEDGER["positions"].pop(tk, None)
            open_pos.pop(tk, None)
            recon_at.pop(tk, None)
            state["settled"] = state.get("settled", 0) + 1
            state["wins"] = state.get("wins", 0) + int(won)
            rec("settled", ticker=tk, want=want, result=res, cost=round(cost, 4),
                pnl_c=round(100 * pnl, 2),
                realised=round(pintake.LEDGER["realised"], 4))
            print(f"  SETTLED {tk} {want} vs {res} -> {100 * pnl:+.2f}c "
                  f"(run realised ${pintake.LEDGER['realised']:+.4f})")
        # size x price, NOT price: at --size 0.01 the per-contract figure
        # overstates exposure 100x and the forward loss bound would halt the
        # run on its very first fill.
        state["open_cost"] = float(SIZE) * sum(c for (_, _, c)
                                               in open_pos.values())

    def report_closes(now_s):
        for cs in sorted(near):
            if cs > now_s or cs in reported:
                continue
            reported.add(cs)
            nb = near[cs]
            b = nb.get("best")
            if b is None:
                rec("close_summary", close=cs, looks=nb["n"],
                    decided=nb["decided"], undecided=nb["undecided"],
                    no_offer=nb["no_offer"], dust=nb["dust"],
                    fired=cs in fired, best=None,
                    why=("decided but NOBODY OFFERED the winning side"
                         if nb["no_offer"] else
                         "no market ever reached the 98% gate"))
                print(f"  close {time.strftime('%H:%M', time.gmtime(cs))}Z: "
                      f"{nb['n']} looks, {nb['decided']} decided, "
                      f"{nb['no_offer']} decided-but-nothing-offered, "
                      f"{nb['undecided']} undecided")
            else:
                rec("close_summary", close=cs, looks=nb["n"],
                    decided=nb["decided"], undecided=nb["undecided"],
                    no_offer=nb["no_offer"], dust=nb["dust"],
                    tradeable=nb["tradeable"], fired=cs in fired,
                    best_ticker=b["ticker"], best_want=b["want"],
                    best_edge_c=round(100 * b["edge"], 3),
                    best_price=round(b["price"], 4),
                    best_fair=round(b["fair"], 5), best_tau=b["tau"],
                    best_size=b["size"],
                    needed_c=round(100 * EDGE_FLOOR, 2))
                v = "FIRED" if cs in fired else "no trade"
                print(f"  close {time.strftime('%H:%M', time.gmtime(cs))}Z: "
                      f"{nb['n']} looks, best was {b['ticker'][:22]} "
                      f"{b['want'].upper()} @{b['price']:.4f} "
                      f"edge {100*b['edge']:+.2f}c "
                      f"(need +{100*EDGE_FLOOR:.1f}c) -> {v}")
            near.pop(cs, None)

    while time.time() < end:
        report_closes(int(time.time()) - 5)
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
                        cs_ = m.get("custom_strike") or {}
                        d = cs_.get("round_digits")
                        # THE STRIKE IS RETURNED TWICE AND THEY DIFFER.
                        # Top-level floor_strike is TRUNCATED to the display
                        # precision; custom_strike.floor_strike is exact.
                        # Live 2026-09-08: DOGE 0.08926 vs '0.0892605'. DOGE's
                        # round_digits is 7, so the rounding correction is
                        # 5e-8 while the truncation error is 5e-7 -- ten times
                        # larger than the effect it was meant to model. Use
                        # the exact field wherever the exchange gives it.
                        if cs_.get("floor_strike") is not None:
                            try:
                                sk = float(cs_["floor_strike"])
                            except (TypeError, ValueError):
                                pass
                        # EXCHANGE_INDEX IS NOT OPTIONAL. Checked live
                        # 2026-09-08 across all 11 series: every open crypto
                        # 15M market reads exchange_index 2, not 0. take()
                        # defaults it to 0, so every live order was going to
                        # be routed to the wrong shard -- rejected, or worse,
                        # created where _unrest's cancel (which reuses the
                        # same field) cannot find it. pintake.envtest already
                        # reads this field; pinrun did not.
                        fresh[m["ticker"]] = (iid, cs, float(sk),
                                              int(d) if d is not None else None,
                                              int(m.get("exchange_index") or 0))
                if fresh:
                    seen_markets = fresh
                    new = set(seen_markets) - set(watching)
                    if new:
                        book.subscribe(sorted(new))
                        rec("watch", n=len(watching) + len(new),
                            added=sorted(new))
                    for tk_, v_ in fresh.items():
                        watching[tk_] = v_[1]
                    # a subscription that only grows re-subscribes every dead
                    # market on each reconnect and walks into the server's
                    # "Subscription buffer overflow" (livebook error code 25).
                    gone = [t for t, c in watching.items() if c < now_s - 300]
                    if gone:
                        book.drop(gone)
                        for t in gone:
                            watching.pop(t, None)
                        rec("unwatch", n=len(watching), dropped=sorted(gone))
                state["errors"] = 0
            except Exception as e:                       # noqa: BLE001
                state["errors"] += 1
                rec("error", where="universe", err=str(e)[:200])

        for tk, (iid, close_s, strike, digits, exi) in list(seen_markets.items()):
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
                # WHY did this not produce a candidate? The two cases are very
                # different and conflating them hides the real constraint:
                #   undecided  -- fair never reached the gate; no edge existed
                #   no_offer   -- fair DID reach the gate but nobody was
                #                 offering the winning side. When an outcome
                #                 becomes obvious the losing side's bids
                #                 vanish, so there is nothing to buy. That is
                #                 a CAPACITY limit, not a signal limit.
                nb = near.setdefault(close_s, _fresh_near())
                nb["n"] += 1
                if f >= PIN or f <= 1.0 - PIN:
                    nb["decided"] += 1
                    nb["no_offer"] += 1
                else:
                    nb["undecided"] += 1
                continue
            if size < max(MIN_LEVEL, SIZE):   # dust is not a real fill
                continue
            e = net_edge(f, price, want)
            nb = near.setdefault(close_s, _fresh_near())
            nb["n"] += 1
            nb["decided"] += 1
            nb["tradeable"] += 1
            if size < max(MIN_LEVEL, SIZE):
                nb["dust"] += 1
            if nb["best"] is None or e > nb["best"]["edge"]:
                nb["best"] = {"ticker": tk, "want": want, "edge": e,
                              "price": price, "fair": f, "tau": tau,
                              "size": size}
            if e < EDGE_FLOOR:
                continue

            state["signals"] += 1
            sig = dict(ticker=tk, want=want, price=round(price, 4),
                       fair=round(f, 5), tau=tau, edge_c=round(100 * e, 3),
                       size=size, strike=strike, digits=digits, spot=spot,
                       sigma=round(sg, 6), book_age_ms=b["age_ms"],
                       index_age_s=round(iage, 2), exchange_index=exi)
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
                                       SIZE, close_s, exchange_index=exi)
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
                    # NOT state["errors"]: the universe block resets that to 0
                    # every 20 s, so an order path that threw on every fire
                    # could never reach the consecutive-errors abort.
                    state["order_errors"] = state.get("order_errors", 0) + 1
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
    ap.add_argument("--size", type=float, default=1.0,
                    help="contracts per take; 0.01 is about one cent, for "
                         "proving order/fill/settle/payout end to end")
    ap.add_argument("--max-positions", type=int, default=3,
                    help="halt after this many open positions")
    a = ap.parse_args()
    # The frozen rule is frozen. Widening it must be a code edit and a commit,
    # not a flag: pintake's own MAX_TAU is 90 s, so --tau-max 60 would have
    # been waved through by every rail below this line.
    if a.live:
        if a.tau_max > TAU_MAX:
            raise SystemExit(f"--tau-max {a.tau_max} exceeds the frozen rule's "
                             f"{TAU_MAX} s (PREREG_pin_live.md); refusing to go "
                             f"live outside the pre-registered cell")
        if not (-5.00 <= a.loss_abort < 0.0):
            raise SystemExit(f"--loss-abort {a.loss_abort} is outside "
                             f"[-5.00, 0.00); refusing")
        if a.max_positions > 3:
            raise SystemExit(f"--max-positions {a.max_positions} > 3; refusing")
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- nothing ran")

    globals()["TAU_MAX"] = a.tau_max
    globals()["SIZE"] = a.size
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
          f"loss abort ${a.loss_abort:.2f}  SIZE {a.size:g}")
    print(f"  log {logpath}")
    rec("start", mode=tag, tau_max=TAU_MAX, pin=PIN, edge_floor=EDGE_FLOOR,
        size=a.size, loss_abort=a.loss_abort, minutes=a.minutes)

    if a.live:
        arm(f"pinrun --live, size {a.size:g}, frozen rule tau<={TAU_MAX}, "
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
