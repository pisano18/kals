#!/usr/bin/env python3
"""forecaster_live.py -- the clean-room FORECASTER on its REALISTIC fill rule, LIVE, scaled down, in a SUBACCOUNT.

Operator 2026-09-29 ~00:5xZ: "I want clean room forecaster realistic fills. Exactly how it worked to get the 15%
return just scaled down."

WHAT IT DOES
  Runs bettor_paper.py's engine unchanged, forecaster rule only (remaining prints r <= 30; model 'blendvr' with the
  TRAIN z-scale and calibration map; buys EITHER side at a displayed ask 0.75-0.985 when p_side - q - fee >= 0.02; at
  most 100 contracts per side per market and 400 per close, paper). The paper's 'real' fill rule books a fill only for
  size STILL displayed at the same price 1.0 s after the decision. This file sends a real order at exactly that moment:
  each paper 'real' fill of k contracts at q becomes one immediate-or-cancel limit buy at q for the proportional
  increment round_half_up(SCALE x paper contracts so far on that side) minus what earlier paper fills already asked for.
  A live miss is NOT retried (the paper does not retry a filled level either); the gap is the live fill rate, measured.
  Both sides of one market may be bought, as the paper does (its one loss on 09-28, XRP 16:15Z, was exactly that).

WHY A SUBACCOUNT
  pinrun's v-safety2 adopts and hedges any position in its series held in subaccount 0 that it did not book. In a
  subaccount these contracts are invisible to it (see ladder_live.py for the documented facts).
  self_trade_prevention_type=taker_at_cross: a would-be self-trade cancels THIS order, never a resting one.

HARD RAILS (code, not flags; SCALE = 1/20 of the paper's size)
  <= 5 contracts per side per market (paper 100), <= 20 per close (paper 400), <= 5 per order; price 75-98.5c for the
  side bought; <= 20 contracts / $22 held + in flight; never within 0.5 s of the close or on a trigger older than 1.5 s;
  realized <= -$12 in an ET day halts to the next ET day; <= -$20 since start halts until restarted; an IOC that comes
  back resting is cancelled and halts; an unreadable answer halts until the order record is read back; refuses to
  start above $35 in the subaccount (funded $25 + its profit); stop file results/forecaster-live.stop; <= 3 order writes a second (shared key).
  --scale k multiplies every one of those by k/0.05 (v-forecaster-scale).

--auto-scale (v-sub-autosize, 2026-10-02; operator: "Set no limits on the sub accounts ... I want each account running
  just like the main pin"): the scale is the subaccount's own POT -- cash + the cost of what it holds -- divided by 630
  ($63 -> 0.10, what --scale 0.10 ran; $126 -> 0.20; $630 -> 1.0 = the paper's size; clamped 0.02..1.0), read at start
  and re-read every 60 s like the main bot's autosize, APPLIED ONLY WHEN NOTHING IS HELD OR IN FLIGHT (a live position
  is never resized), each change logged as a 'rescale' record. Stops are a share of the pot, the main bot's shape:
  day stop -20% of the pot at the day's first rescale, run stop -33% of the pot at start, held + in flight <= 70% of
  the pot. NO start-balance cap in this mode (the operator's order); the $10 floor and the primary-account refusal stay.
  WHAT THE GATES BLOCK: every size cap (per side, per close, held, committed, crash guard) applies to a forecaster BET
  on either side; a HEDGE (the paper's hedge_p insurance, extra hedge=True -- no live variant has it today) is exempt
  from all of them (operator rule 09-19: a gate must never block a hedge) and keeps only the per-order body rail, the
  price rail and the stop/halt states.

v-fresh-book (2026-10-18; operator: "Fix the frozen order book"). The order-book feed went silent three times while
  the socket looked healthy and the bot kept deciding on the frozen book (10-11 03:09Z ~6 min; 10-13 15:45Z ~15 min,
  bot book 37-42c while the market traded 99.9c; 10-16 07:35Z ~10 min, one real order ETH 22 at 07:44Z, 0 filled).
  Causes, from results/forecaster-live.jsonl: (1) 10-11 and 10-13: bettor_paper.WS.subscribe reads next_id after the
  send, so on a reconnect the reader thread's own subscribes (_on_connect) interleaved with the main loop's market
  subscribe: the request went out as id 1368 (382) but was recorded as 1369 (383), its reply looked superseded, and
  the bot unsubscribed its OWN fresh subscription right after the 9 snapshots loaded ("ws_unsub_stale", both
  channels). (2) 10-16: Kalshi sent error code 25 "Subscription buffer overflow" and dropped the orderbook_delta
  subscription (trades kept arriving); nothing resubscribed until the next quarter-hour.
  FcWS (installed as bettor_paper.WS in THIS process only -- the paper bots keep theirs) allocates ids under a lock,
  records the market request id BEFORE sending it, and a reconnect no longer wipes a market request already sent on
  the new connection. BookWatch sees every feed message on the main loop and marks a market's book STALE -- unsynced,
  so neither the in-process paper nor this broker trades it (broker refusal why=stale_book) -- until a fresh snapshot
  arrives, and asks for a resubscribe (at most every 10 s), when: Kalshi sends error code 25 or unsubscribes the live
  orderbook_delta sid (all books); a trade in that market has no book message for it from 1 s before to 2 s after it
  (that market); the market subscription is unconfirmed 5 s after it was sent (all books), or a subscribed market
  got no snapshot from it 5 s after it was confirmed (that market); no book message on ANY subscribed market for 15 s
  while index prints still arrive (all books: the 10-11 / 10-13 shape, where trades went silent too). A quiet book
  with no trades is never stale on its own. Why 15 s: of 24,170 health minutes 09-29..10-18 with the socket up,
  markets active and prints arriving, the only minutes with <= 300 book messages were the four known freezes (32
  minutes); the 1st percentile is 9,242 a minute. Why 1 s / 2 s for a trade: on 6 recorder-tape hours (10-13 14/16Z,
  10-16 06Z, 10-18 05-07Z) every one of 1,247,924 trades had a book message for its market within 1 s either side
  (worst 0.68 s). Every rule counts its seconds on the feed's own receive clock (the
  latest message seen), so a main loop running behind its queue never makes a false 'stale'. Seq gaps and reconnects
  were already handled (bettor_paper unsyncs every book and resubscribes; the snapshots re-sync them).
  --no-book-watch restores the stock client and turns the watch off.

v-resend-dropped (2026-10-18, --resend-dropped, DEFAULT OFF). When the paper wants more contracts on a side while an
  earlier live order for it is still in flight, the extra is refused (why=in_flight) and was never re-sent. With the
  flag the latest such trigger is remembered and, once the in-flight order is answered, re-sent ONCE for the deficit
  at the trigger's price through every gate again at that moment: the broker's (stops, price band, the fresh-book
  gate, crash guard on the best ask then, every cap, the writer's late/stale rules) and the paper's own entry gates on
  the model's LATEST decision for that market (edge >= min_edge at that price after the fee, p floor, the race gate),
  plus two more: the trigger is at most STALE_S (1.5 s) old and the book still shows an ask at or under that price.
  Re-sent orders and their refusals carry resend=true. With the flag off nothing here runs (no hook, no state).

    python research/cleanroom/forecaster_live.py --selftest
    python research/cleanroom/forecaster_live.py --subaccount 2 --dry-run --minutes 30
    python research/cleanroom/forecaster_live.py --subaccount 2 --live --minutes 10080
    python research/cleanroom/forecaster_live.py --subaccount 2 --live --auto-scale --variant race1_98 --crash-gap 0.10
"""
import argparse
import json
import math
import os
import queue
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import bettor_paper as B                        # noqa: E402
import fc_variants as FV                        # noqa: E402  (--variant: the loss-cutting gates)
import pintake                                  # noqa: E402  (normalise / _readable / _is_live: pure parsers)

LIVE_LOG = r"C:\kals-repo\results\forecaster-live.jsonl"
ORDER_LOG = r"C:\kals-repo\results\forecaster-live-orders.jsonl"
STOP_FILE = r"C:\kals-repo\results\forecaster-live.stop"
KEY_FILE = r"C:\kals\kalshi.pem"
KEY_ID = "5163259c-ecb0-4966-9053-0d2776cf061e"

SCALE = Decimal("0.05")                         # live contracts per paper contract
MAX_PER_SIDE = 5                                # paper F_MAX_SIDE 100 x SCALE
MAX_PER_CLOSE = 20                              # paper F_MAX_CLOSE 400 x SCALE
MAX_ORDER = 5
MAX_HELD = 20
MAX_COMMIT = 22.00
MIN_PX, MAX_PX = 0.75, 0.985                    # paper F_MIN_PRICE, F_MAX_PRICE
DAY_STOP = -12.00
RUN_STOP = -20.00
MAX_SUB_BALANCE = 35.00                         # start rail: funded $25 + room for its own profit (was 25.00 to 09-29)
LATE_S = 0.5
STALE_S = 1.5
WRITES_PER_S = 3.0
POOL = 2
CID_PREFIX = "fc-"
BROKER = None
# v-crash-guard (2026-09-30): the live IOC fills far BELOW the price the 1-s check saw when the offer is collapsing
# (5 such fills in the first 2 days: 3 lost, -$3.05; the 17 ordinary fills: 0 lost, +$7.94). If, when the order is
# triggered, the engine's own best ask on our side is already more than CRASH_GAP under the price we are about to
# pay, the collapse is visible -- skip. None = off. Every order logs the best ask at the trigger either way.
CRASH_GAP = None
# v-fresh-book (2026-10-18): see the docstring. WATCH is this process's BookWatch (None = off, as in the self-test worlds).
BOOK_TRADE_GAP_S = 2.0                          # a trade with no book message for its market this long after it
BOOK_PRE_S = 1.0                                # a book message this soon BEFORE a trade counts as that trade's delta
BOOK_ALL_SILENT_S = 15.0                        # no book message on any subscribed market this long (prints still live)
PRINT_LIVE_S = 5.0                              # "index prints still arrive": the last one is at most this old
SUB_CONFIRM_S = 5.0                             # a market subscription unconfirmed this long after it was sent
RESYNC_MIN_S = 10.0                             # at most one watch-asked resubscribe per this many seconds
WATCH = None
# v-resend-dropped (2026-10-18): --resend-dropped; False = today's behaviour exactly
RESEND = False


# v-sub-autosize (2026-10-02): --auto-scale. The pot is the subaccount's cash + the cost of what it holds.
POT_DIVISOR = 630.0                             # scale = pot / 630: $63 -> 0.10 (today's size), $126 -> 0.20
SCALE_MIN, SCALE_MAX = 0.02, 1.0                # 1.0 = the paper's own size; apply_scale's ceiling for --scale too
POT_FLOOR = 10.0                                # refuse to start under this pot (the lower sanity floor)
POT_REREAD_S = 60.0                             # the main bot's autosize cadence
DAY_STOP_FRAC, RUN_STOP_FRAC, COMMIT_FRAC = 0.20, 0.33, 0.70


def apply_scale(scale, pot=None):
    """v-forecaster-scale (2026-09-30, operator: "increase clean room forecaster"): every size rail is the 1/20 rail
    times scale/0.05 -- per side, per close, per order, held, committed, day stop, run stop and the start balance --
    so a bigger scale can never outgrow its own limits. 0.05 reproduces the v-forecaster-live numbers exactly.
    v-sub-autosize: with `pot` (--auto-scale) the contract rails still come from the scale, but the money rail is
    70% of the pot, there is no start cap, and the stops are left to AutoScale (day stop / run stop from the pot)."""
    global SCALE, MAX_PER_SIDE, MAX_PER_CLOSE, MAX_ORDER, MAX_HELD, MAX_COMMIT, DAY_STOP, RUN_STOP, MAX_SUB_BALANCE
    k = float(scale) / 0.05
    if not (0.01 <= float(scale) <= SCALE_MAX):
        raise SystemExit("--scale %s is outside 0.01..%s" % (scale, SCALE_MAX))
    SCALE = Decimal(str(scale))
    MAX_PER_SIDE = int(round(100 * float(scale)))
    MAX_PER_CLOSE = int(round(400 * float(scale)))
    MAX_ORDER = MAX_PER_SIDE
    MAX_HELD = MAX_PER_CLOSE
    if pot is None:
        MAX_COMMIT = round(22.00 * k, 2)
        DAY_STOP = round(-12.00 * k, 2)
        RUN_STOP = round(-20.00 * k, 2)
        MAX_SUB_BALANCE = round(35.00 * k, 2)
    else:
        MAX_COMMIT = round(COMMIT_FRAC * float(pot), 2)
        MAX_SUB_BALANCE = None                  # the operator's order: no cap on what the subaccount may hold


def scale_for_pot(pot):
    """pot dollars -> the live scale: pot / 630, clamped 0.02..1.0, 4 decimals (so a cent of fees never rescales)."""
    return min(SCALE_MAX, max(SCALE_MIN, round(float(pot) / POT_DIVISOR, 4)))


def read_pot(sender, sub):
    """The subaccount's pot in dollars: cash + the cost of what it holds (Kalshi's market_exposure, the cost basis
    of each open position), or None when either read is unreadable. The unit is READ, never inferred (hard rule 5,
    as the main bot's read_bank): `balance` (cents) and `balance_dollars` must both be present and agree to a cent."""
    st, bal = sender("GET", "/portfolio/balance", None, {"subaccount": int(sub), "exchange_index": POOL})
    try:
        cash = float(bal["balance_dollars"])
        cents = float(bal["balance"])
    except Exception:
        return None
    if st != 200 or abs(cents / 100.0 - cash) > 0.011:
        return None
    st2, pos = sender("GET", "/portfolio/positions", None,
                      {"subaccount": int(sub), "count_filter": "position", "settlement_status": "unsettled"})
    if st2 != 200 or not isinstance(pos, dict) or not isinstance(pos.get("market_positions"), list):
        return None
    held = 0.0
    for x in pos["market_positions"]:
        if not isinstance(x, dict):
            return None
        try:
            if x.get("market_exposure_dollars") is not None:
                held += abs(float(x["market_exposure_dollars"]))
            else:
                held += abs(float(x["market_exposure"])) / 100.0
        except Exception:
            return None
    return round(cash + held, 4)


def start_refusal(sub_bal, pot, live, auto):
    """The start checks, as a function so the self-test drives them. Fixed --scale keeps the old balance cap
    (MAX_SUB_BALANCE + 5c of fee residue) and the $5 live floor; --auto-scale has NO cap (the operator's order),
    only the $10 pot floor. Returns the reason to refuse, or None."""
    if auto:
        if pot is None:
            return "--auto-scale: the pot is unreadable"
        if float(pot) < POT_FLOOR:
            return "--auto-scale: pot $%.2f is under the $%.0f floor" % (float(pot), POT_FLOOR)
        return None
    if sub_bal is None:
        return "subaccount balance unreadable"
    if sub_bal > MAX_SUB_BALANCE + 0.05:              # fees leave sub-cent residue (25.0042 after a $2.02 sweep)
        return "subaccount holds $%.2f > $%.2f" % (sub_bal, MAX_SUB_BALANCE)
    if live and sub_bal < 5.0:
        return "subaccount holds $%.2f; fund it first (ordercli --sub-fund)" % sub_bal
    return None


class AutoScale:
    """--auto-scale: the pot-driven sizing. `reader()` -> pot dollars or None; `flat()` -> nothing held or in flight
    (called under `lock`). tick() reads at most every POT_REREAD_S; consider() changes the scale (and MAX_COMMIT) only
    when flat, sets the day stop at the day's first applied rescale, and writes a 'rescale' record on every change.
    The run stop is set once, at start(), from the pot then. Nothing here moves a stop or a rail while a position
    is open -- the main bot's rule 4 ("ONLY WHEN FLAT")."""

    def __init__(self, log, reader, now, flat, lock=None):
        self.log, self.reader, self.now, self.flat = log, reader, now, flat
        self.lock = lock if lock is not None else threading.Lock()
        self.pot = self.scale = self.day = self.pot_start = self.last_read = None
        self.waiting = False
        self.reads = 0

    def start(self, pot):
        global DAY_STOP, RUN_STOP
        if pot is None or float(pot) < POT_FLOOR:
            raise SystemExit("--auto-scale: pot %s is unreadable or under the $%.0f floor; refusing" % (pot, POT_FLOOR))
        self.pot_start = float(pot)
        self.scale = scale_for_pot(pot)
        apply_scale(self.scale, pot=pot)
        RUN_STOP = round(-RUN_STOP_FRAC * float(pot), 2)
        DAY_STOP = round(-DAY_STOP_FRAC * float(pot), 2)
        self.pot, self.day, self.last_read = float(pot), et_day(self.now()), self.now()
        return self.scale

    def rails(self):
        return {"scale": str(SCALE), "per_side": MAX_PER_SIDE, "per_close": MAX_PER_CLOSE, "per_order": MAX_ORDER,
                "max_held": MAX_HELD, "max_commit": MAX_COMMIT, "day_stop": DAY_STOP, "run_stop": RUN_STOP}

    def consider(self, pot, now):
        """Apply `pot` if it changes anything and nothing is open. Returns True when a rescale was applied."""
        global DAY_STOP
        new = scale_for_pot(pot)
        d = et_day(now)
        if new == self.scale and d == self.day:
            return False
        if not self.flat():
            if not self.waiting:
                self.waiting = True
                self.log.write("rescale_wait", old=self.scale, new=new, pot=round(float(pot), 4), why="position open")
            return False
        old, old_rails = self.scale, self.rails()
        apply_scale(new, pot=pot)
        if d != self.day:
            DAY_STOP = round(-DAY_STOP_FRAC * float(pot), 2)
            self.day = d
        self.scale, self.pot, self.waiting = new, float(pot), False
        self.log.write("rescale", old=old, new=new, pot=round(float(pot), 4), old_rails=old_rails, rails=self.rails())
        return True

    def tick(self):
        now = self.now()
        if self.last_read is not None and now - self.last_read < POT_REREAD_S:
            return None
        self.last_read = now
        pot = self.reader()
        self.reads += 1
        if pot is None:
            self.log.write("pot_unreadable")
            return None
        with self.lock:
            return self.consider(pot, now)


_ET_ZONE = None


def et_offset_s(t):
    """Seconds to add to a UTC epoch for the Eastern wall clock: -14400 (EDT) or -18000 (EST). v-etclock (10-23): was a
    fixed -4 h; US daylight time ends 2026-11-01 06:00Z, after which the old key turned the day at 23:00 ET (day_pnl and
    DAY_STOP reset an hour early, the 23:00-24:00 hour booked to the next day). zoneinfo America/New_York first (needs
    the tzdata package on Windows -- absent here 2026-10-23), else the US rule: 2nd Sunday of March 07:00Z .. 1st Sunday
    of November 06:00Z."""
    global _ET_ZONE
    if _ET_ZONE is None:
        try:
            from zoneinfo import ZoneInfo
            _ET_ZONE = ZoneInfo("America/New_York")
        except Exception:
            _ET_ZONE = False
    if _ET_ZONE:
        return int(datetime.fromtimestamp(t, _ET_ZONE).utcoffset().total_seconds())
    y = datetime.fromtimestamp(t, timezone.utc).year
    mar = datetime(y, 3, 8, 7, tzinfo=timezone.utc)
    mar += timedelta(days=(6 - mar.weekday()) % 7)
    nov = datetime(y, 11, 1, 6, tzinfo=timezone.utc)
    nov += timedelta(days=(6 - nov.weekday()) % 7)
    return -14400 if mar.timestamp() <= t < nov.timestamp() else -18000


def et_day(t):
    return datetime.fromtimestamp(t + et_offset_s(t), timezone.utc).strftime("%Y-%m-%d")


def fee(n, px):
    return math.ceil(0.07 * n * px * (1 - px) * 100 - 1e-9) / 100.0


def scaled(paper_n):
    return int((Decimal(str(paper_n)) * SCALE + Decimal("0.5")).to_integral_value(rounding="ROUND_FLOOR"))


def order_body(ticker, side, px, n, sub, cid):
    """side 'yes' = buy YES at px (bid px); side 'no' = buy NO at px (= sell YES: ask at 1-px). IOC, can cross."""
    px = Decimal(str(px)).quantize(Decimal("0.0001"))
    s, p = ("bid", px) if side == "yes" else ("ask", Decimal(1) - px)
    return {"ticker": ticker, "side": s, "count": "%.2f" % n, "price": "%.4f" % p,
            "time_in_force": "immediate_or_cancel", "self_trade_prevention_type": "taker_at_cross",
            "post_only": False, "client_order_id": cid, "subaccount": int(sub), "exchange_index": POOL}


def body_ok(b, sub):
    """Every order body must carry these, or it is not sent."""
    try:
        yes_px = float(b["price"])
        n = float(b["count"])
    except Exception:
        return False
    want_px = yes_px if b.get("side") == "bid" else 1.0 - yes_px
    return (b.get("side") in ("bid", "ask") and b.get("post_only") is False
            and b.get("time_in_force") == "immediate_or_cancel"
            and b.get("self_trade_prevention_type") == "taker_at_cross"
            and b.get("subaccount") == int(sub) and int(sub) >= 1 and b.get("exchange_index") == POOL
            and n == int(n) and 1 <= n <= MAX_ORDER and str(b.get("client_order_id", "")).startswith(CID_PREFIX)
            and MIN_PX - 1e-9 <= want_px <= MAX_PX + 1e-9)


class BookWatch:
    """v-fresh-book: the stale-book detector. observe() sees every feed message on the main loop just BEFORE run_live
    dispatches it (FcWS wraps the queue's get_nowait); scan() runs at the top of every engine tick; fresh() is the
    broker's gate. A stale market's book is marked unsynced -- bettor_paper's own do-not-trade state, the one a seq gap
    uses -- so the paper makes no decision on it and resolves no 1-s survivor on it; the resubscribe's snapshot for that
    market makes it fresh again. Everything here runs on the main loop thread and is O(markets) per tick."""

    def __init__(self, log=None):
        self.log = log
        self.eng = None
        self.ws = None
        self.last_book = {}            # ticker -> rx of its last book message (delta or snapshot)
        self.snap_sid = {}             # ticker -> sid of its last snapshot
        self.nosnap_done = None        # the confirmed request id the no-snapshot rule already fired for
        self.pend_trade = {}           # ticker -> rx of the first trade NOT matched by a book message of that market
        self.stale = {}                # ticker -> {"why": rule, "since": t}
        self.last_any_book = None
        self.last_print = None
        self.sub_ok = (None, None, None)   # (request id, rx, sid) of the confirmed orderbook_delta subscription
        self.sub_wait = None           # [request id, first seen unconfirmed, flagged]
        self.silent_ref = None         # the reference time an all-silent flag was raised for (once per episode)
        self.last_resync = None
        self.last_rx = None            # the MESSAGE clock: latest receive time seen. Every rule measures its seconds
        self.n = {}                    # on it, so a main loop running behind its queue never makes a false 'stale'

    def _write(self, ev, **kw):
        if self.log is not None:
            self.log.write(ev, **kw)

    def observe(self, rx, obj):
        if self.last_rx is None or rx > self.last_rx:
            self.last_rx = rx
        t = obj.get("type")
        if t == "orderbook_delta" or t == "orderbook_snapshot":
            tk = (obj.get("msg") or {}).get("market_ticker")
            self.last_book[tk] = rx
            self.last_any_book = rx
            self.pend_trade.pop(tk, None)
            if t == "orderbook_snapshot":
                self.snap_sid[tk] = obj.get("sid")
            if t == "orderbook_snapshot" and tk in self.stale and obj.get("sid") == self.sub_ok[2]:
                s = self.stale.pop(tk)             # a snapshot of the CONFIRMED live subscription: fresh again
                self._write("book_fresh", ticker=tk, why=s["why"], stale_s=round(rx - s["since"], 3))
        elif t == "trade":
            tk = (obj.get("msg") or {}).get("market_ticker")
            lb = self.last_book.get(tk)
            if tk not in self.pend_trade and (lb is None or rx - lb > BOOK_PRE_S):
                self.pend_trade[tk] = rx
        elif t == "cfbenchmarks_value":
            self.last_print = rx
        elif t == "subscribed":
            m = obj.get("msg") or {}
            if m.get("channel") == "orderbook_delta" and self.ws is not None and obj.get("id") == self.ws.market_sub_id:
                self.sub_ok = (obj.get("id"), rx, m.get("sid"))
        elif t == "error":
            m = obj.get("msg") or {}
            if m.get("code") == 25:                       # "Subscription buffer overflow" (10-16 07:35:41Z)
                self.flag_all("ws_error_25", rx, detail=m)
        elif t == "unsubscribed":
            sid = obj.get("sid")
            if sid is not None and self.ws is not None and sid == self.ws.sids.get("orderbook_delta"):
                self.flag_all("server_unsubscribed", rx, detail={"sid": sid})   # Kalshi dropped the LIVE book sid
        elif t in ("_ws_up", "_ws_down"):
            self.pend_trade.clear()
            self.sub_ok, self.sub_wait, self.silent_ref = (None, None, None), None, None

    def scan(self, now):
        ws = self.ws
        if ws is None or not ws.connected or self.last_rx is None:
            return
        m = self.last_rx                                  # rule clock (see last_rx); `now` only paces resubscribes
        subs = set(ws.market_tickers or ())
        for tk in [tk for tk in self.stale if tk not in subs]:
            del self.stale[tk]                            # no longer subscribed (its market closed): nothing to wait for
        for tk in self.stale:                             # a snapshot of an UNconfirmed subscription re-synced it:
            b = self.eng.books.get(tk) if self.eng is not None else None
            if b is not None and b.synced:                # keep it out of the paper's decisions too
                b.synced = False
        mid = ws.market_sub_id
        if mid is not None and self.sub_ok[0] != mid:
            if self.sub_wait is None or self.sub_wait[0] != mid:
                self.sub_wait = [mid, now, False]
            elif not self.sub_wait[2] and m - self.sub_wait[1] > SUB_CONFIRM_S:
                self.sub_wait[2] = True
                self.flag_all("subscription_unconfirmed", now, detail={"sub_id": mid})
        if (mid is not None and self.sub_ok[0] == mid and m - self.sub_ok[1] > SUB_CONFIRM_S
                and self.nosnap_done != mid):
            self.nosnap_done = mid                        # once per subscription: a subscribed market with no snapshot
            for tk in sorted(subs):                       # from it 5 s after it was confirmed
                if self.snap_sid.get(tk) != self.sub_ok[2] and tk not in self.stale:
                    self.flag(tk, "no_snapshot", now, detail={"sub_id": mid})
        for tk, t0 in list(self.pend_trade.items()):
            if m - t0 > BOOK_TRADE_GAP_S and tk not in self.stale and tk in subs:
                self.flag(tk, "trade_without_book", now, detail={"trade_rx": round(t0, 3)})
        if (mid is not None and self.sub_ok[0] == mid and self.last_print is not None
                and m - self.last_print <= PRINT_LIVE_S):
            ref = max(self.last_any_book or 0.0, self.sub_ok[1] or 0.0)
            if m - ref > BOOK_ALL_SILENT_S and self.silent_ref != ref:
                self.silent_ref = ref
                self.flag_all("all_books_silent", now, detail={"silent_s": round(m - ref, 1)})
        if self.stale and (self.last_resync is None or now - self.last_resync >= RESYNC_MIN_S):
            self.resync(now, "still_stale")              # a resubscribe that did not bring the snapshot: ask again

    def fresh(self, tk, now):
        if tk in self.stale:
            return False
        t0 = self.pend_trade.get(tk)
        return t0 is None or (self.last_rx if self.last_rx is not None else now) - t0 <= BOOK_TRADE_GAP_S

    def _mark(self, tk, why, now):
        self.n[why] = self.n.get(why, 0) + 1
        self.stale.setdefault(tk, {"why": why, "since": now})
        b = self.eng.books.get(tk) if self.eng is not None else None
        if b is not None:
            b.synced = False

    def flag(self, tk, why, now, detail=None):
        self._mark(tk, why, now)
        self._write("book_stale", why=why, tickers=[tk], detail=detail)
        self.resync(now, why)

    def flag_all(self, why, now, detail=None):
        tks = set(self.ws.market_tickers or ()) if self.ws is not None else set()
        if self.eng is not None:
            tks.update(tk for tk, b in self.eng.books.items() if b.synced)
        tks = sorted(tk for tk in tks if tk not in self.stale)
        for tk in tks:
            self._mark(tk, why, now)
        self._write("book_stale", why=why, tickers=tks, detail=detail)
        self.resync(now, why)

    def resync(self, now, why):
        """Ask run_live for a resubscribe (eng.resync_wanted: its own seq-gap path, which sends new snapshots)."""
        if self.eng is None or (self.last_resync is not None and now - self.last_resync < RESYNC_MIN_S):
            return
        self.last_resync = now
        self.eng.resync_wanted = True
        self._write("book_resync", why=why, stale=sorted(self.stale))


class FcWS(B.WS):
    """v-fresh-book: bettor_paper's websocket client with the subscription-id race closed (see the docstring), and the
    queue the main loop drains wrapped so BookWatch sees each message first. main() installs it as B.WS for THIS process
    only. The reader thread (_read_loop) and the reconnect loop (run) are bettor_paper's, unchanged."""

    def __init__(self, q, log, headers_fn):
        super().__init__(q, log, headers_fn)
        self._id_lock = threading.Lock()
        self._sub_conn = None                     # self.reconnects when the current market request was sent
        w = WATCH
        if w is not None:
            w.ws = self
            get = q.get_nowait

            def get_nowait():
                item = get()
                try:
                    w.observe(item[0], item[1])
                except Exception as e:           # the watch must never stop the feed
                    log.write("watch_error", err=repr(e)[:200])
                return item
            q.get_nowait = get_nowait

    def _new_id(self):
        with self._id_lock:
            self.next_id += 1
            return self.next_id

    def subscribe(self, channels, **params):
        i = self._new_id()                        # bettor_paper re-read next_id after the send: the 10-13 race
        p = {"channels": channels}
        p.update(params)
        self.send_json({"id": i, "cmd": "subscribe", "params": p})
        return i

    def unsubscribe(self, sids):
        self.send_json({"id": self._new_id(), "cmd": "unsubscribe", "params": {"sids": sids}})

    def set_markets(self, tickers):
        """As bettor_paper's, except the request id is allocated and recorded BEFORE the request is sent."""
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
        """As bettor_paper's, except a market request the main loop already sent on THIS connection is kept: run()
        queues _ws_up before calling this, so the main loop's set_markets can come first (it never reads a reply
        before this returns: the reader thread is the one running this)."""
        with self._id_lock:
            self.sids = {}
            if self._sub_conn != self.reconnects:
                self.market_sub_id = None
        self.subscribe(["cfbenchmarks_value"], index_ids=self.index_ids)
        self.subscribe(["market_lifecycle_v2"])


class Broker:
    def __init__(self, log, sub, dry, sender, now):
        self.log, self.sub, self.dry, self.send, self.now = log, int(sub), dry, sender, now
        self.q = queue.Queue()
        self.pos = {}             # (ticker, side) -> {"close_s", "paper", "asked", "inflight", "px_inflight", "n", "cost", "fee"}
        self.close_asked = {}     # close_s -> contracts asked for (sent or in flight)
        self.orders = {}          # cid -> order state
        self.day, self.day_pnl, self.run_pnl = None, 0.0, 0.0
        self.halt_day = None
        self.halted = None
        self.stopped = False
        self.lock = threading.Lock()
        self._w = []
        self.sizer = None         # AutoScale under --auto-scale; its tick runs on the poller thread
        self.due = set()          # --resend-dropped: (ticker, side) whose in-flight order was answered with a drop left

    def exposure(self):
        n = sum(v["n"] + v["inflight"] for v in self.pos.values())
        c = sum(v["cost"] + v["inflight"] * v["px_inflight"] for v in self.pos.values())
        return n, c

    def flat(self):
        """Nothing held, nothing in flight, nothing queued: the only state in which a rail may change."""
        n, c = self.exposure()
        return n == 0 and c == 0 and self.q.empty()

    def stop_reason(self, now):
        if self.stopped:
            return "stopped"
        if self.halted:
            return "halted"
        if self.halt_day == et_day(now):
            return "day_stop"
        return None

    # --- called when the paper forecaster books a 'real' fill (size still shown 1 s after its decision) ---
    def want(self, ticker, close_s, side, px, paper_k, rel=None, p_side=None, best_ask=None, hedge=False, resend=None):
        """A paper 'real' fill -> at most one live IOC for the proportional increment. `hedge` (the paper's hedge_p
        insurance on the OTHER side of a held market) skips the crash guard and every size/money cap -- per close,
        held, committed -- a gate must never block a hedge; it keeps the per-side mirror, the per-order body rail,
        the price rail and the stop/halt states. A plain opposite-side BET (the paper buying both sides on its own
        rule) is not a hedge and is capped like any other order.
        v-fresh-book: a bet on a book BookWatch holds stale is refused (why=stale_book; a hedge is exempt, as above).
        v-resend-dropped: `resend` is the remembered in-flight drop being re-sent (paper_k 0, best_ask read now)."""
        now = self.now()
        with self.lock:
            v = self.pos.setdefault((ticker, side), {"close_s": close_s, "paper": 0.0, "asked": 0, "inflight": 0,
                                                     "px_inflight": 0.0, "n": 0, "cost": 0.0, "fee": 0.0})
            v["paper"] += paper_k
            inc = min(scaled(v["paper"]), MAX_PER_SIDE) - v["asked"]
            if inc <= 0:
                return 0
            why = self.stop_reason(now)
            if not why and not (MIN_PX - 1e-9 <= px <= MAX_PX + 1e-9):
                why = "price"
            if not why and not hedge and WATCH is not None and not WATCH.fresh(ticker, now):
                why = "stale_book"
            if not why and resend is not None:
                if now - resend["t"] > STALE_S + 1e-9:
                    why = "resend_stale"                  # never on a trigger older than STALE_S
                elif best_ask is None or best_ask > px + 1e-9:
                    why = "resend_gone"                   # no ask at or under the trigger's price is shown any more
                elif resend.get("gate"):
                    why = resend["gate"]                  # the paper's own entry gate fails on its latest decision
            if not why and not hedge and CRASH_GAP is not None and best_ask is not None and best_ask < px - CRASH_GAP - 1e-9:
                why = "crash"
            if not why and v["inflight"]:
                why = "in_flight"
                if RESEND and resend is None:             # remember the latest drop; re-sent once the order is answered
                    v["drop"] = {"t": now, "px": px, "rel": rel, "p_side": p_side, "hedge": bool(hedge)}
            if not why and hedge:
                inc = min(inc, MAX_ORDER)
            elif not why:
                inc = min(inc, MAX_ORDER, MAX_PER_CLOSE - self.close_asked.get(close_s, 0))
                n, c = self.exposure()
                inc = min(inc, MAX_HELD - n, int((MAX_COMMIT - c) / px + 1e-9))
                if inc <= 0:
                    why = "cap"
            if why:
                # 2026-10-02 (crash-guard read): a refusal carries the best ask it saw, so the next read has a
                # floor for "how far under the price the offer had collapsed" instead of a typical 11c.
                self.log.write("refused", ticker=ticker, side=side, px=px, paper_k=paper_k, rel=rel, why=why,
                               best_ask=best_ask, **({"hedge": True} if hedge else {}),
                               **({"resend": True} if resend is not None else {}))
                return 0
            v.pop("drop", None)                           # this order asks for the whole deficit: nothing left to re-send
            self.due.discard((ticker, side))
            v["asked"] += inc
            v["inflight"] = inc
            v["px_inflight"] = px
            self.close_asked[close_s] = self.close_asked.get(close_s, 0) + inc
            cid = "%s%d-%d" % (CID_PREFIX, int(now * 1000), len(self.orders))
            self.orders[cid] = {"ticker": ticker, "side": side, "px": px, "n": inc, "status": "queued", "kid": None,
                                "t_dec": resend["t"] if resend is not None else now, "close_s": close_s, "rel": rel,
                                "p_side": p_side, "paper_k": paper_k, "best_ask": best_ask, "hedge": bool(hedge),
                                "resend": resend is not None}
            self.q.put(("place", cid))
            return inc

    def resend_pass(self, eng):
        """--resend-dropped (main loop, top of each engine tick): re-send each remembered in-flight drop whose earlier
        order has been answered, once, through want() -- every gate again, the best ask read from the engine now and
        the paper's entry gates re-checked on its latest decision (paper_gate)."""
        if not self.due:
            return 0
        with self.lock:
            keys, self.due = list(self.due), set()
            jobs = []
            for k in keys:
                v = self.pos.get(k)
                if v is None or v["inflight"] or not v.get("drop"):
                    continue
                jobs.append((k, v["close_s"], v.pop("drop")))
        n = 0
        for (tk, side), close_s, d in jobs:
            b = eng.books.get(tk)
            ba = None
            if b is not None and b.synced:
                bp, _ = b.best_ask(side)
                ba = None if bp is None else round(float(bp), 4)
            gate = None if d["hedge"] else paper_gate(eng, tk, side, d["px"])
            n += self.want(tk, close_s, side, d["px"], 0.0, d["rel"], d["p_side"], best_ask=ba, hedge=d["hedge"],
                           resend=dict(d, gate=gate))
        return n

    def check_stop_file(self):
        if not self.stopped and os.path.exists(STOP_FILE):
            self.stopped = True
            self.log.write("stop_file", path=STOP_FILE)

    # --- fills and results ---
    def _book_fill(self, cid, filled, exec_px, fee_total):
        o = self.orders[cid]
        v = self.pos.get((o["ticker"], o["side"]))
        if v is None:
            self.log.write("fill_after_settle", cid=cid, ticker=o["ticker"], n=filled)
            return
        v["inflight"] = 0
        if v.get("drop"):
            self.due.add((o["ticker"], o["side"]))    # --resend-dropped: answered with a drop left -> resend_pass
        if filled > 0:
            px = exec_px if exec_px is not None else o["px"]
            v["n"] += filled
            v["cost"] += filled * px
            f = fee_total if fee_total is not None else fee(filled, px)
            v["fee"] += f
            self.log.write("live_fill", ticker=o["ticker"], cid=cid, kid=o["kid"], side=o["side"], px=px,
                           asked_px=o["px"], n=filled, asked_n=o["n"], fee=round(f, 4), rel=o["rel"])

    def on_result(self, ticker, result):
        with self.lock:
            sides = [(k, self.pos.pop(k)) for k in [k for k in self.pos if k[0] == ticker]]
            held = [(k, v) for k, v in sides if v["n"] > 0]
            if not held:
                return
            pnl = sum((v["n"] - v["cost"] if k[1] == result else -v["cost"]) - v["fee"] for k, v in held)
            d = et_day(self.now())
            if d != self.day:
                self.day, self.day_pnl = d, 0.0
            self.day_pnl += pnl
            self.run_pnl += pnl
            self.log.write("live_settle", ticker=ticker, result=result,
                           held={k[1]: {"n": v["n"], "cost": round(v["cost"], 4), "fee": round(v["fee"], 4),
                                        "paper": v["paper"]} for k, v in held},
                           pnl=round(pnl, 4), day_pnl=round(self.day_pnl, 4), run_pnl=round(self.run_pnl, 4))
            if self.day_pnl <= DAY_STOP + 1e-9 and self.halt_day != d:
                self.halt_day = d
                self.log.write("day_stop", day=d, day_pnl=round(self.day_pnl, 4))
            if self.run_pnl <= RUN_STOP + 1e-9 and not self.halted:
                self.halted = "run_stop %.2f" % self.run_pnl
                self.log.write("run_stop", run_pnl=round(self.run_pnl, 4))

    def restore_day(self, path, now):
        """v-fc-dayrestore (2026-10-26): the ET day's realized result survives a restart. day_pnl started at $0 in
        every new process, so a restart (a deploy, a crash, a reboot) forgot the day's losses and handed the bot a
        second day stop (10-26: -$19.83 by 03:15 ET would have been forgotten). It is rebuilt from today's
        live_settle rows in the order log, and the day stop re-armed if they already reach it. Returns (rows, $)."""
        d = et_day(now)
        tot, n = 0.0, 0
        try:
            fh = open(path, encoding="utf-8")
        except OSError:
            return 0, 0.0
        with fh:
            for line in fh:
                if '"live_settle"' not in line:
                    continue
                try:
                    r = json.loads(line)
                    t = datetime.strptime(r["t"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
                except (ValueError, KeyError, TypeError):
                    continue
                if r.get("ev") == "live_settle" and et_day(t) == d:
                    tot += float(r.get("pnl") or 0.0)
                    n += 1
        with self.lock:
            self.day, self.day_pnl = d, tot
            if tot <= DAY_STOP + 1e-9:
                self.halt_day = d
        return n, tot

    def forget_closed(self, close_s):
        """Drop what a finished close cannot need (nothing held, nothing in flight)."""
        with self.lock:
            for k in [k for k, v in self.pos.items() if v["close_s"] <= close_s and v["n"] <= 0 and not v["inflight"]]:
                del self.pos[k]
            for c in [c for c in self.close_asked if c <= close_s]:
                del self.close_asked[c]

    # --- the one writer thread ---
    def _throttle(self):
        now = time.time()
        self._w = [t for t in self._w if now - t < 1.0]
        if len(self._w) >= WRITES_PER_S:
            time.sleep(max(0.0, 1.0 - (now - self._w[0])))
        self._w.append(time.time())

    def _release(self, o):
        v = self.pos.get((o["ticker"], o["side"]))
        if v is not None:
            v["inflight"] = 0
            if v.get("drop"):
                self.due.add((o["ticker"], o["side"]))

    def work_once(self, item):
        kind, cid = item
        o = self.orders.get(cid)
        if o is None or kind != "place":
            return
        now = self.now()
        late = "late" if now > o["close_s"] - LATE_S else ("stale" if now - o["t_dec"] > STALE_S else None)
        if late or self.stopped:
            o["status"] = "dropped"
            with self.lock:
                self._release(o)
            self.log.write("dropped", ticker=o["ticker"], cid=cid, why=late or "stopped", age=round(now - o["t_dec"], 3))
            return
        b = order_body(o["ticker"], o["side"], o["px"], o["n"], self.sub, cid)
        if not body_ok(b, self.sub):
            o["status"] = "refused"
            with self.lock:
                self._release(o)
            self.log.write("body_refused", body=b)
            return
        if self.dry:
            o["status"] = "dry"
            with self.lock:
                self._release(o)
            self.log.write("would_place", body=b, age=round(now - o["t_dec"], 3), paper_k=o["paper_k"])
            return
        self._throttle()
        t_send = time.time()
        try:
            st, r = self.send("POST", "/portfolio/events/orders", b, None)
        except Exception as e:
            st, r = -1, repr(e)[:300]
        out = pintake.normalise(st, r, b)
        o["kid"] = out.get("order_id")
        self.log.write("placed", body=b, status=st, order_id=o["kid"], filled=out["filled"],
                       remaining=out["remaining"], exec_px=out["exec_price"], fee_total=out["fee_total"],
                       paper_k=o["paper_k"], best_ask_at_trigger=o.get("best_ask"), hedge=o.get("hedge", False),
                       age=round(t_send - o["t_dec"], 3), rtt=round(time.time() - t_send, 3),
                       resp=str(r)[:300], **({"resend": True} if o.get("resend") else {}))
        with self.lock:
            if st is not None and 400 <= st < 500:
                o["status"] = "rejected"
                self._release(o)
                return
            if not pintake._readable(out):
                o["status"] = "unknown"
                self.halted = "unknown answer for %s (status %s)" % (cid, st)
                self.log.write("halt", why=self.halted)
                return
            if pintake._is_live(out):
                o["status"] = "rested"
                self.halted = "IOC came back resting: %s" % o["kid"]
                self.log.write("halt", why=self.halted)
            else:
                o["status"] = "done"
            self._book_fill(cid, round(float(out["filled"] or 0), 2), out["exec_price"], out["fee_total"])
        if o["status"] == "rested" and o["kid"]:
            st2, r2 = self.send("DELETE", "/portfolio/events/orders/%s" % o["kid"], None,
                                {"subaccount": self.sub, "exchange_index": POOL})
            self.log.write("cancelled", order_id=o["kid"], status=st2, resp=str(r2)[:200])

    def run_writer(self):
        while True:
            item = self.q.get()
            try:
                self.work_once(item)
            except Exception as e:
                self.log.write("writer_error", err=repr(e)[:300])

    def poll_unknown_once(self):
        """Read back the record of any order whose answer was unreadable; book its fill from the record."""
        unk = [c for c, o in self.orders.items() if o["status"] == "unknown"]
        if not unk:
            return
        st, r = self.send("GET", "/portfolio/orders", None,
                          {"subaccount": self.sub, "min_ts": int(time.time()) - 3600, "limit": 500})
        if st != 200 or not isinstance(r, dict):
            return
        rows = {x.get("client_order_id"): x for x in r.get("orders") or []}
        for cid in unk:
            x = rows.get(cid)
            if x is None:
                continue
            o = self.orders[cid]
            out = pintake.normalise(200, x, order_body(o["ticker"], o["side"], o["px"], o["n"], self.sub, cid))
            if out["status"] == "resting":
                continue
            with self.lock:
                o["kid"], o["status"] = out.get("order_id"), "recovered"
                self._book_fill(cid, round(float(out["filled"] or 0), 2), out["exec_price"], out["fee_total"])
            self.log.write("recovered", cid=cid, record=str(x)[:300])

    def run_poller(self):
        while True:
            try:
                if not self.dry:
                    self.poll_unknown_once()
            except Exception as e:
                self.log.write("poll_error", err=repr(e)[:300])
            try:
                if self.sizer is not None:        # --auto-scale: the 60-s pot re-read (dry run included)
                    self.sizer.tick()
            except Exception as e:
                self.log.write("sizer_error", err=repr(e)[:300])
            time.sleep(3.0)


# ---------------------------------------------------------------------------------------------------- engine hooks
_orig = {}


def install_hooks():
    """Mirror each paper 'real' forecaster fill into BROKER.want(); tell BROKER each settle. Idempotent."""
    if _orig:
        return
    _orig["add_fill"], _orig["on_result"], _orig["tick"] = B.Engine.add_fill, B.Engine.on_result, B.Engine.tick

    def add_fill(self, m, strat, fm, side, price, size, fee_, **extra):
        _orig["add_fill"](self, m, strat, fm, side, price, size, fee_, **extra)
        if BROKER is not None and strat == "forecaster" and fm == "real" and extra.get("kind") == "take":
            _bk = self.books.get(m.ticker)
            _ba = None
            if _bk is not None:
                _bp, _ = _bk.best_ask(side)
                _ba = None if _bp is None else round(float(_bp), 4)
            BROKER.want(m.ticker, m.close_s, side, round(float(price), 4), float(size), extra.get("rel"),
                        extra.get("p_side"), best_ask=_ba, hedge=bool(extra.get("hedge")))

    def on_result(self, ticker, result, ev, now):
        _orig["on_result"](self, ticker, result, ev, now)
        if BROKER is not None and result in ("yes", "no"):
            BROKER.on_result(ticker, result)

    def tick(self):
        if WATCH is not None and WATCH.eng is self:       # v-fresh-book: stale books are unsynced BEFORE deciding
            try:
                WATCH.scan(self.now())
            except Exception as e:                        # the watch must never stop the paper or the broker
                self.log.write("watch_error", err=repr(e)[:200])
        if BROKER is not None and RESEND and BROKER.due:  # v-resend-dropped
            try:
                BROKER.resend_pass(self)
            except Exception as e:
                self.log.write("resend_error", err=repr(e)[:200])
        open_closes = {m.close_s for m in self.markets.values() if not m.done}
        _orig["tick"](self)
        if BROKER is not None:
            BROKER.check_stop_file()
            still = {m.close_s for m in self.markets.values() if not m.done}
            for c in sorted(open_closes - still):
                BROKER.forget_closed(c)
    B.Engine.add_fill, B.Engine.on_result, B.Engine.tick = add_fill, on_result, tick


_orig_fc = {}


def install_resend_hook():
    """--resend-dropped only: remember each market's LATEST forecaster decision (rel, p yes, index value) on the engine
    (engine._fc_last) so a re-send can re-check the paper's entry gates on it. A pass-through: the decision itself is
    untouched. Installed by wire() only when the flag is on (so the default process is today's code path). Idempotent."""
    if _orig_fc:
        return
    _orig_fc["forecaster"] = FV.VEngine.forecaster

    def forecaster(self, m, rel, v, proj, r, exact_yes, b, now):
        out = _orig_fc["forecaster"](self, m, rel, v, proj, r, exact_yes, b, now)
        if isinstance(out, dict) and out.get("p") is not None:
            last = self.__dict__.setdefault("_fc_last", {})
            last[m.ticker] = (rel, float(out["p"]), float(v))
        return out
    FV.VEngine.forecaster = forecaster


def paper_gate(eng, ticker, side, px):
    """--resend-dropped: the paper's entry gates (fc_variants.VEngine.forecaster E5-E7) for buying `side` at `px` NOW,
    on the engine's latest decision for that market. None = every gate passes, else the refusal reason."""
    m = getattr(eng, "markets", {}).get(ticker)
    if m is None or m.done or eng.now() >= m.close_s:
        return "resend_closed"
    last = getattr(eng, "_fc_last", {}).get(ticker)
    if last is None:
        return "resend_model"                     # no model decision for this market yet (cannot re-check: refuse)
    rel, p, v = last
    P = getattr(eng, "P", None) or FV.DEFAULTS
    ps = p if side == "yes" else 1.0 - p
    if ps < P["min_p"] or px > P["max_price"] or px < P["min_price"] or ps - px - B.fee1(px) < P["min_edge"] - 1e-12:
        return "resend_edge"
    if P.get("race_x") is not None and m.thr_f is not None:
        bk = getattr(eng, "prints", {}).get(m.index_id, {}).get(m.close_s + rel - 5)
        if bk is not None:
            gap_now = abs(v - m.thr_f)
            toward5 = (gap_now - abs(bk[0] - m.thr_f)) / max(gap_now, 1e-12)
            if toward5 < -P["race_x"] and ps < P["race_p"]:
                return "resend_race"
    return None


# ---------------------------------------------------------------------------------------------------- self-test
def selftest():
    global STOP_FILE, BROKER, MAX_HELD, MAX_COMMIT, SCALE, MAX_PER_SIDE, MAX_PER_CLOSE, MAX_ORDER, DAY_STOP, RUN_STOP, MAX_SUB_BALANCE
    global CRASH_GAP, WATCH, RESEND
    _cg = CRASH_GAP
    fails, sink = [], []
    log = B.Logger(None, sink)
    sent = []
    mode = {"v": "fill", "fill": None}

    def fake_send(method, path, body, query):
        sent.append((method, path, body, query))
        if method == "POST":
            k = "K%d" % len(sent)
            n = body["count"] if mode["fill"] is None else "%.2f" % mode["fill"]
            if mode["v"] == "fill":
                return 201, {"order_id": k, "client_order_id": body["client_order_id"], "fill_count": n,
                             "remaining_count": "0.00", "average_fill_price": body["price"],
                             "average_fee_paid": "0.0100"}
            if mode["v"] == "miss":
                return 201, {"order_id": k, "fill_count": "0.00", "remaining_count": "0.00"}
            if mode["v"] == "rest":
                return 201, {"order_id": k, "fill_count": "0.00", "remaining_count": body["count"]}
            if mode["v"] == "garbled":
                return 201, {"order_id": k}
            if mode["v"] == "reject":
                return 400, '{"error": {"code": "insufficient_balance"}}'
        if method == "GET":
            return 200, {"orders": []}
        return 200, {}
    ck = lambda ok, m: None if ok else fails.append(m)

    def run(br):
        while not br.q.empty():
            br.work_once(br.q.get())
    # bodies
    b1 = order_body("KXBTC15M-X", "yes", 0.80, 5, 2, "fc-1")
    b2 = order_body("KXBTC15M-X", "no", 0.76, 3, 2, "fc-2")
    ck(b1["side"] == "bid" and b1["price"] == "0.8000" and b1["count"] == "5.00", "YES maps to a bid at the ask, 5")
    ck(b2["side"] == "ask" and b2["price"] == "0.2400", "NO maps to an ask at 1-px")
    ck(body_ok(b1, 2) and body_ok(b2, 2) and body_ok(order_body("T", "yes", 0.985, 1, 2, "fc-x"), 2), "legal bodies pass (incl. 98.5c)")
    ck(not body_ok(dict(b1, time_in_force="good_till_canceled"), 2), "a resting order is refused")
    ck(not body_ok(dict(b1, post_only=True), 2), "post_only (would rest) is refused")
    ck(not body_ok(dict(b1, subaccount=0), 2) and not body_ok(order_body("T", "yes", 0.8, 1, 0, "fc-x"), 0), "subaccount 0 refused")
    ck(not body_ok(order_body("T", "yes", 0.8, 6, 2, "fc-x"), 2) and not body_ok(dict(b1, count="0.00"), 2)
       and not body_ok(dict(b1, count="2.50"), 2), "6, 0 and fractional contracts are refused")
    ck(not body_ok(order_body("T", "yes", 0.99, 1, 2, "fc-x"), 2) and not body_ok(order_body("T", "no", 0.74, 1, 2, "fc-x"), 2),
       "prices outside 75-98.5c are refused")
    ck(not body_ok(dict(b1, self_trade_prevention_type="maker"), 2), "maker self-trade mode refused")
    ck(not body_ok(dict(b1, client_order_id="bet-1"), 2), "a foreign client id prefix is refused")
    ck(fee(5, 0.80) == 0.06 and fee(1, 0.95) == 0.01, "taker fee rounds up to the cent")
    _saved = (SCALE, MAX_PER_SIDE, MAX_PER_CLOSE, MAX_ORDER, MAX_HELD, MAX_COMMIT, DAY_STOP, RUN_STOP, MAX_SUB_BALANCE)
    apply_scale(0.05)
    ck((SCALE, MAX_PER_SIDE, MAX_PER_CLOSE, MAX_ORDER, MAX_HELD, MAX_COMMIT, DAY_STOP, RUN_STOP, MAX_SUB_BALANCE)
       == (Decimal("0.05"), 5, 20, 5, 20, 22.0, -12.0, -20.0, 35.0), "--scale 0.05 reproduces the 1/20 rails exactly")
    apply_scale(0.10)
    ck((MAX_PER_SIDE, MAX_PER_CLOSE, MAX_ORDER, MAX_HELD, MAX_COMMIT, DAY_STOP, RUN_STOP, MAX_SUB_BALANCE)
       == (10, 40, 10, 40, 44.0, -24.0, -40.0, 70.0) and scaled(100) == 10 and scaled(77) == 8,
       "--scale 0.10 doubles every rail with the size (10 a side, 40 a close, $44 held, -$24 day, -$40 run)")
    ck(body_ok(order_body("T", "yes", 0.8, 10, 2, "fc-x"), 2) and not body_ok(order_body("T", "yes", 0.8, 11, 2, "fc-x"), 2),
       "--scale 0.10: 10 contracts an order pass, 11 are refused")
    (SCALE, MAX_PER_SIDE, MAX_PER_CLOSE, MAX_ORDER, MAX_HELD, MAX_COMMIT, DAY_STOP, RUN_STOP, MAX_SUB_BALANCE) = _saved
    # v-sub-autosize: --auto-scale. NULL first: fixed --scale 0.10 is today's rails exactly and the start cap applies.
    try:
        apply_scale(0.10)
        ck((MAX_PER_SIDE, MAX_PER_CLOSE, MAX_ORDER, MAX_HELD, MAX_COMMIT, DAY_STOP, RUN_STOP, MAX_SUB_BALANCE)
           == (10, 40, 10, 40, 44.0, -24.0, -40.0, 70.0), "NULL: --scale 0.10 without --auto-scale is today's rails exactly")
        ck(start_refusal(70.06, None, True, False) and start_refusal(70.04, None, True, False) is None
           and start_refusal(4.99, None, True, False) and start_refusal(4.99, None, False, False) is None
           and start_refusal(None, None, True, False),
           "NULL: without --auto-scale the $70 start cap, the $5 live floor and the unreadable-balance refusal still apply")
        apply_scale(0.30)
        ck(MAX_PER_SIDE == 30 and MAX_SUB_BALANCE == 210.0, "--scale ceiling raised: 0.30 is accepted (rails x6)")
        apply_scale(1.0)
        ck((MAX_PER_SIDE, MAX_PER_CLOSE) == (100, 400), "--scale 1.0 = the paper's own size (100 a side, 400 a close)")
        try:
            apply_scale(1.01)
            ck(False, "--scale 1.01 must be refused")
        except SystemExit:
            pass
        ck([scale_for_pot(p) for p in (63, 126, 630, 5, 10000, 63.01, 31.5)] == [0.1, 0.2, 1.0, 0.02, 1.0, 0.1, 0.05],
           "scale = pot/630: $63 -> 0.10, $126 -> 0.20, $630 -> 1.0, clamped 0.02..1.0, a cent of fees never moves it")
        ck(start_refusal(None, 500.0, True, True) is None and start_refusal(None, 10.0, True, True) is None,
           "--auto-scale: NO upper start cap ($500 starts)")
        ck(start_refusal(None, 9.99, True, True) and start_refusal(None, None, True, True),
           "--auto-scale: the $10 floor and the unreadable-pot refusal stay")
        # the pot reader: unit read from both fields (hard rule 5), cost of holdings added, any unreadable piece -> None
        def pot_send(bal, pos, st=200, st2=200):
            return lambda m, p, b, q: (st, bal) if p == "/portfolio/balance" else (st2, pos)
        ck(read_pot(pot_send({"balance": 6300, "balance_dollars": "63.0000"},
                             {"market_positions": [{"ticker": "A", "position": 10, "market_exposure_dollars": "9.8000"},
                                                   {"ticker": "B", "position": -5, "market_exposure": 400}]}), 2) == 76.8,
           "pot = cash 63.00 + held 9.80 + 4.00 (cents field) = 76.80")
        ck(read_pot(pot_send({"balance": 6300, "balance_dollars": "63.0000"}, {"market_positions": []}), 2) == 63.0
           and read_pot(pot_send({"balance": 630000, "balance_dollars": "63.0000"}, {"market_positions": []}), 2) is None
           and read_pot(pot_send({"balance_dollars": "63.0000"}, {"market_positions": []}), 2) is None
           and read_pot(pot_send({"balance": 6300, "balance_dollars": "63.0000"}, {"nope": 1}), 2) is None
           and read_pot(pot_send({"balance": 6300, "balance_dollars": "63.0000"}, {"market_positions": []}, st2=500), 2) is None
           and read_pot(pot_send({"balance": 6300, "balance_dollars": "63.0000"},
                                 {"market_positions": [{"ticker": "A", "position": 1}]}), 2) is None,
           "pot: cents and dollars must agree, both present; a missing/failed/unreadable positions read is None (never 'flat')")
        # the sizer: rails at the three example pots, stops as a share of the pot, the clamp, no start cap
        clk = [1_790_000_000.0]
        flat = [True]
        reads = []
        for pot, want in ((63.0, (0.1, 10, 40, 44.1, -12.6, -20.79)), (126.0, (0.2, 20, 80, 88.2, -25.2, -41.58)),
                          (630.0, (1.0, 100, 400, 441.0, -126.0, -207.9)), (5000.0, (1.0, 100, 400, 3500.0, -1000.0, -1650.0)),
                          (10.0, (0.02, 2, 8, 7.0, -2.0, -3.3))):
            az = AutoScale(log, lambda: None, lambda: clk[0], lambda: flat[0])
            az.start(pot)
            got = (az.scale, MAX_PER_SIDE, MAX_PER_CLOSE, MAX_COMMIT, DAY_STOP, RUN_STOP)
            ck(got == want and MAX_ORDER == MAX_PER_SIDE and MAX_HELD == MAX_PER_CLOSE and MAX_SUB_BALANCE is None,
               "auto-scale at pot $%.0f: (scale, side, close, commit 70%%, day -20%%, run -33%%) = %s, want %s" % (pot, got, want))
        for bad in (9.99, None):
            try:
                AutoScale(log, lambda: None, lambda: clk[0], lambda: True).start(bad)
                ck(False, "auto-scale start at pot %s must refuse" % bad)
            except SystemExit:
                pass
        # cadence: one read per 60 s, not more; an unreadable pot changes nothing
        pots = [63.0]
        az = AutoScale(log, lambda: (reads.append(1), pots[0])[1], lambda: clk[0], lambda: flat[0])
        az.start(63.0)
        n0 = len(sink)
        for dt in (3, 30, 59):
            clk[0] = 1_790_000_000.0 + dt
            az.tick()
        ck(len(reads) == 0, "no re-read inside 60 s of the start read")
        clk[0] = 1_790_000_000.0 + 60
        ck(az.tick() is False and len(reads) == 1 and len(sink) == n0, "re-read at 60 s; same pot -> nothing changes, no record")
        pots[0] = None
        clk[0] += 60
        az.tick()
        ck(len(reads) == 2 and sink[-1]["ev"] == "pot_unreadable" and az.scale == 0.1 and MAX_COMMIT == 44.1,
           "an unreadable pot is logged and changes nothing")
        # not applied while something is open; applied once flat; the day stop moves only at the day's first rescale
        pots[0] = 126.0
        flat[0] = False
        clk[0] += 60
        ck(az.tick() is False and az.scale == 0.1 and MAX_PER_SIDE == 10 and MAX_COMMIT == 44.1 and DAY_STOP == -12.6
           and sink[-1]["ev"] == "rescale_wait" and sink[-1]["new"] == 0.2,
           "pot $126 while a position is open: NOT applied (rescale_wait logged), rails unchanged")
        clk[0] += 60
        az.tick()
        ck(len([r for r in sink if r["ev"] == "rescale_wait"]) == 1, "the wait is logged once, not every minute")
        flat[0] = True
        clk[0] += 60
        ck(az.tick() is True and az.scale == 0.2 and (MAX_PER_SIDE, MAX_PER_CLOSE, MAX_COMMIT) == (20, 80, 88.2)
           and DAY_STOP == -12.6 and RUN_STOP == -20.79 and sink[-1]["ev"] == "rescale"
           and (sink[-1]["old"], sink[-1]["new"], sink[-1]["pot"]) == (0.1, 0.2, 126.0)
           and sink[-1]["old_rails"]["per_side"] == 10 and sink[-1]["rails"]["per_side"] == 20,
           "once flat: applied -- scale 0.2, 20 a side, $88.20 committed; day stop (same day) and run stop unchanged; 'rescale' logged")
        clk[0] += 86400
        ck(az.tick() is True and DAY_STOP == -25.2 and RUN_STOP == -20.79 and az.scale == 0.2,
           "the next ET day: day stop re-set to -20% of that day's first pot (-$25.20); run stop fixed at start")
        # driven through a real Broker: its own books say when it is flat
        mode["v"], mode["fill"] = "fill", None
        apply_scale(0.10, pot=63.0)
        brz = Broker(log, 2, False, fake_send, lambda: clk[0])
        pots[0] = 63.0
        az2 = AutoScale(log, lambda: pots[0], lambda: clk[0], brz.flat, brz.lock)
        az2.start(63.0)
        brz.sizer = az2
        ck(brz.flat(), "a fresh broker is flat")
        brz.want("AZ", clk[0] + 30, "yes", 0.80, 100)
        ck(not brz.flat(), "an order in flight is not flat")
        run(brz)
        ck(brz.pos[("AZ", "yes")]["n"] == 10 and not brz.flat(), "10 held (scale 0.10) is not flat")
        pots[0] = 126.0
        clk[0] += 60
        ck(az2.tick() is False and MAX_PER_SIDE == 10, "the broker holds 10: a pot of $126 is NOT applied")
        brz.on_result("AZ", "yes")
        clk[0] += 60
        ck(brz.flat() and az2.tick() is True and MAX_PER_SIDE == 20 and az2.scale == 0.2,
           "settled -> flat -> the next read applies scale 0.2")
        ck(brz.want("AZ2", clk[0] + 30, "yes", 0.80, 100) == 20, "the next paper 100 asks for 20 live at scale 0.2")
        run(brz)
        # a hedge is never blocked by the caps: close full, held full, money full, crash guard on -> still sent
        apply_scale(0.05)
        brh = Broker(log, 2, False, fake_send, lambda: clk[0])
        ck(brh.want("HG", clk[0] + 30, "yes", 0.98, 100) == 5, "5 YES held at 98c")
        run(brh)
        MAX_HELD, MAX_COMMIT, MAX_PER_CLOSE = 5, 4.9, 5
        ck(brh.want("HG2", clk[0] + 30, "no", 0.80, 100) == 0 and sink[-1]["ev"] == "refused" and sink[-1]["why"] == "cap",
           "a plain opposite-side BET with every cap full is refused (why=cap)")
        CRASH_GAP = 0.10
        try:
            ck(brh.want("HG", clk[0] + 30, "no", 0.985, 100, best_ask=0.50, hedge=True) == 5,
               "the HEDGE of the 5 YES (NO at 98.5c) is sent with the close, held and money caps full AND the crash guard on")
        finally:
            CRASH_GAP = _cg
        run(brh)
        pl = [r for r in sink if r["ev"] == "placed"][-1]
        ck(pl["hedge"] is True and pl["body"]["count"] == "5.00" and pl["body"]["side"] == "ask"
           and brh.pos[("HG", "no")]["n"] == 5, "the hedge order is placed (NO 5 at 98.5c), marked hedge=true, and held")
        ck(not body_ok(order_body("T", "yes", 0.8, 6, 2, "fc-x"), 2), "a hedge still cannot exceed the per-order body rail")
    finally:
        (SCALE, MAX_PER_SIDE, MAX_PER_CLOSE, MAX_ORDER, MAX_HELD, MAX_COMMIT, DAY_STOP, RUN_STOP, MAX_SUB_BALANCE) = _saved
        CRASH_GAP = _cg
    ck([scaled(x) for x in (100, 77, 98, 10, 9, 7, 3, 1, 200)] == [5, 4, 5, 1, 0, 0, 0, 0, 10], "proportional scale 1/20, half up")
    # proportional mirroring, increments, caps
    now = [1000.0]
    br = Broker(log, 2, False, fake_send, lambda: now[0])
    ck(br.want("A", 1030, "yes", 0.80, 77) == 4, "paper 77 -> 4 live")
    run(br)
    ck(br.want("A", 1030, "yes", 0.81, 23) == 1, "paper +23 (100 total) -> 1 more live")
    run(br)
    ck(br.want("A", 1030, "yes", 0.82, 100) == 0, "the 5-per-side cap holds (paper 200)")
    ck(br.pos[("A", "yes")]["n"] == 5 and abs(br.pos[("A", "yes")]["cost"] - (4 * 0.80 + 0.81)) < 1e-9, "held 5 at the paper's prices")
    ck(br.want("A", 1030, "no", 0.76, 100) == 5, "the other side is mirrored too (as the paper)")
    run(br)
    ck(br.want("B", 1030, "yes", 0.90, 3) == 0 and br.want("B", 1030, "yes", 0.90, 6) == 0, "paper 3 then 9 -> nothing yet")
    ck(br.want("B", 1030, "yes", 0.90, 1) == 1, "paper 10 -> 1")
    run(br)
    ck(br.want("C", 1030, "yes", 0.74, 100) == 0 and br.want("C2", 1030, "no", 0.99, 100) == 0, "74c and 99c refused")
    brc = Broker(log, 2, False, fake_send, lambda: now[0])
    try:
        CRASH_GAP = None
        ck(brc.want("CG0", 7030, "yes", 0.80, 100, best_ask=0.40) == 5, "crash guard OFF: a collapsed best ask does not refuse")
        run(brc)
        CRASH_GAP = 0.10
        ck(brc.want("CG1", 7930, "yes", 0.80, 100, best_ask=0.60) == 0
           and any(r["ev"] == "refused" and r["why"] == "crash" for r in sink),
           "crash guard 10c: best ask 60c under an 80c order -> skipped (why=crash)")
        ck(any(r["ev"] == "refused" and r["why"] == "crash" and r.get("best_ask") == 0.60 for r in sink),
           "a crash refusal records the best ask it saw (0.60), so the collapse size has a floor in the read")
        ck(brc.want("CG2", 8830, "yes", 0.80, 100, best_ask=0.75) == 5, "crash guard 10c: best ask 75c (5c under) -> sent")
        run(brc)
        ck(brc.want("CG3", 9730, "yes", 0.80, 100, best_ask=None) == 5, "crash guard: an unknown best ask never refuses")
        run(brc)
    finally:
        CRASH_GAP = _cg
    ck(any(r["ev"] == "placed" and r.get("best_ask_at_trigger") == 0.75 for r in sink), "every placed order logs the best ask at the trigger")
    # a miss is not retried; the next paper fill asks only for its own increment
    mode["v"] = "miss"
    br2 = Broker(log, 2, False, fake_send, lambda: now[0])
    ck(br2.want("M", 1030, "yes", 0.80, 60) == 3, "paper 60 -> 3")
    run(br2)
    ck(br2.pos[("M", "yes")]["n"] == 0 and br2.want("M", 1030, "yes", 0.80, 40) == 2, "a miss is not retried: paper +40 -> 2 only")
    # partial fill
    mode["v"], mode["fill"] = "fill", 2
    br3 = Broker(log, 2, False, fake_send, lambda: now[0])
    br3.want("P", 1030, "no", 0.85, 100)
    run(br3)
    ck(br3.pos[("P", "no")]["n"] == 2, "a partial fill (2 of 5) is held as 2")
    mode["fill"] = None
    # per-close cap 20 and the held/commit caps
    saved = (MAX_HELD, MAX_COMMIT)
    MAX_HELD, MAX_COMMIT = 100, 100.0          # isolate the per-close cap from the held caps
    try:
        br4 = Broker(log, 2, False, fake_send, lambda: now[0])
        got = [br4.want("K%d" % i, 1030, "yes", 0.80, 100) for i in range(6)]
        run(br4)
    finally:
        MAX_HELD, MAX_COMMIT = saved
    ck(sum(got) == 20 and got[4] == 0, "at most 20 contracts per close (%s)" % got)
    br5 = Broker(log, 2, False, fake_send, lambda: now[0])
    got = [br5.want("H%d" % i, 1030 + 900 * i, "yes", 0.98, 100) for i in range(6)]
    run(br5)
    n, c = br5.exposure()
    ck(n == MAX_HELD and c <= MAX_COMMIT + 1e-9 and sum(got) == MAX_HELD,
       "20 held across closes caps it before $22 does (%s, %d, %.2f)" % (got, n, c))
    # late / stale drop
    n0 = len(sent)
    br6 = Broker(log, 2, False, fake_send, lambda: now[0])
    br6.want("D", 1030, "yes", 0.80, 100)
    now[0] = 1029.6
    run(br6)
    br6.want("E", 2000, "yes", 0.80, 100)
    now[0] = 1031.2
    run(br6)
    ck(len(sent) == n0 and len([r for r in sink if r["ev"] == "dropped"]) == 2, "late (<0.5 s to close) and stale (>1.5 s) are dropped")
    # settle arithmetic incl. both sides, day stop, next-day reset, run stop
    br7 = Broker(log, 2, False, fake_send, lambda: now[0])
    now[0] = 1_790_000_000.0
    br7.want("W", now[0] + 30, "yes", 0.80, 100)
    br7.want("X", now[0] + 30, "yes", 0.76, 100)
    br7.want("X", now[0] + 30, "no", 0.78, 100)
    run(br7)
    br7.on_result("W", "yes")
    br7.on_result("X", "yes")
    st = [r for r in sink if r["ev"] == "live_settle"]
    ck(abs(st[-2]["pnl"] - (5 - 4.0 - 0.05)) < 1e-9, "win: 5 x (1 - 0.80) - 5c fee = +0.95")
    ck(abs(st[-1]["pnl"] - (5 - 3.8 - 3.9 - 0.10)) < 1e-9, "both sides bought: -2.80 (the paper's XRP 16:15Z shape)")
    br7.day_pnl = -10.0
    br7.want("L", now[0] + 30, "yes", 0.85, 100)
    run(br7)
    br7.on_result("L", "no")
    ck(br7.halt_day == et_day(now[0]) and br7.want("Y", now[0] + 30, "yes", 0.8, 100) == 0, "-$12 in an ET day halts")
    # v-etclock: the ET day turns at 04:00Z in summer and 05:00Z in winter; US daylight time ends 2026-11-01 06:00Z
    _u = lambda *a: datetime(*a, tzinfo=timezone.utc).timestamp()
    ck(et_day(_u(2026, 10, 20, 3, 59)) == "2026-10-19" and et_day(_u(2026, 10, 20, 4, 0)) == "2026-10-20"
       and et_day(_u(2026, 11, 2, 4, 30)) == "2026-11-01" and et_day(_u(2026, 11, 2, 5, 0)) == "2026-11-02"
       and et_offset_s(_u(2026, 11, 1, 5, 59)) == -14400 and et_offset_s(_u(2026, 11, 1, 6, 0)) == -18000,
       "v-etclock: 04:30Z on Nov 2 is still ET day 2026-11-01 (23:30 EST); the day turns at 05:00Z once DST ends")
    now[0] += 86400
    ck(br7.want("Y2", now[0] + 30, "yes", 0.8, 100) == 5, "the next ET day trades again")
    run(br7)
    br7.run_pnl = -17.0
    br7.on_result("Y2", "no")
    now[0] += 86400
    ck(br7.halted and br7.want("Z", now[0] + 30, "yes", 0.8, 100) == 0, "-$20 since start halts until restart")
    # v-fc-dayrestore (10-26): a restart rebuilds the ET day's realized result from the order log's live_settle rows
    with tempfile.TemporaryDirectory() as _td:
        _p = os.path.join(_td, "orders.jsonl")
        _t0 = _u(2026, 10, 26, 7, 15, 16)                         # 03:15 ET Mon Oct 26
        with open(_p, "w", encoding="utf-8") as _fh:
            for _t, _ev, _v in ((_t0 - 86400, "live_settle", -50.0), (_t0 - 3600, "live_settle", 2.5),
                                (_t0, "live_settle", -9.0), (_t0 + 60, "live_fill", -99.0)):
                _fh.write(json.dumps({"t": datetime.fromtimestamp(_t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                                      "ev": _ev, "pnl": _v}) + "\n")
            _fh.write("not json\n")
        b10 = Broker(log, 2, False, fake_send, lambda: _t0 + 120)
        ck(b10.restore_day(_p, _t0 + 120) == (2, -6.5) and b10.day == "2026-10-26" and b10.day_pnl == -6.5
           and b10.halt_day is None,
           "restart: today's two settles (+2.50, -9.00) rebuilt, yesterday's -$50 and a fill row left out: day -$6.50")
        b10.on_result("nothing-held", "yes")
        ck(b10.day_pnl == -6.5, "a result for nothing held changes nothing")
        _ds = DAY_STOP
        try:
            globals()["DAY_STOP"] = -5.0
            b11 = Broker(log, 2, False, fake_send, lambda: _t0 + 120)
            b11.restore_day(_p, _t0 + 120)
            ck(b11.halt_day == "2026-10-26" and b11.want("Q", _t0 + 150, "yes", 0.8, 100) == 0,
               "restart past the day stop: halted for the rest of the ET day, no buy")
        finally:
            globals()["DAY_STOP"] = _ds
        ck(Broker(log, 2, False, fake_send, lambda: _t0).restore_day(os.path.join(_td, "none.jsonl"), _t0) == (0, 0.0),
           "restart with no order log: day $0 (as before)")
    # resting IOC / garbled / 4xx
    for m_, halts, dels in (("rest", True, 1), ("garbled", True, 0), ("reject", False, 0)):
        mode["v"] = m_
        b8 = Broker(log, 2, False, fake_send, lambda: 1000.0)
        n_del = len([s for s in sent if s[0] == "DELETE"])
        b8.want("R", 1030, "yes", 0.80, 100)
        run(b8)
        ck(bool(b8.halted) == halts and len([s for s in sent if s[0] == "DELETE"]) - n_del == dels,
           "%s: halts=%s, cancels=%d" % (m_, halts, dels))
        ck(b8.pos[("R", "yes")]["inflight"] == (5 if m_ == "garbled" else 0), "%s: in-flight kept only when unknown" % m_)
    mode["v"] = "fill"
    # stop file, dry run
    b9 = Broker(log, 2, False, fake_send, lambda: 1000.0)
    real = STOP_FILE                               # 2026-10-18: a temp file, never a file beside the live logs
    STOP_FILE = os.path.join(tempfile.gettempdir(), "forecaster-live-selftest-%d.flag" % os.getpid())
    open(STOP_FILE, "w").close()
    try:
        b9.check_stop_file()
    finally:
        os.remove(STOP_FILE)
        STOP_FILE = real
    ck(b9.stopped and b9.want("S", 1030, "yes", 0.8, 100) == 0, "the stop file refuses every order")
    n1 = len(sent)
    b10 = Broker(log, 2, True, fake_send, lambda: 1000.0)
    b10.want("D1", 1030, "yes", 0.8, 100)
    run(b10)
    ck(len(sent) == n1 and any(r["ev"] == "would_place" for r in sink), "dry run sends nothing")
    # driven world (bettor_paper's planted forecaster world): the paper's REAL fill, not its opt fill, reaches the broker
    install_hooks()
    C = 1_000_000
    clock = [0.0]
    esink = []
    eng = B.Engine(B.Logger(None, esink), lambda: clock[0], B.Tables(), ["forecaster"])
    eng.add_market("BTC-T", "BTC", C, Decimal("100.00"), 2, "planted")
    for s in range(C - 240, C + 1):
        eng.on_print("BRTI", s * 1000, ("101.00", "101.01")[s % 2], s + 0.1)
    eng.on_snapshot("BTC-T", {"no_dollars_fp": [["0.2000", "50.00"], ["0.0100", "500.00"]],
                              "yes_dollars_fp": [["0.0100", "40.00"]]}, 1)
    b11 = Broker(log, 2, False, fake_send, lambda: clock[0])
    BROKER = b11
    try:
        for rel in range(-60, -30):
            clock[0] = C + rel + 0.2
            eng.tick()
        ck(b11.q.empty(), "paper opt fill at 0.80 (rel -31) sends NOTHING -- only the 1-s survivor may")
        eng.on_delta("BTC-T", {"side": "no", "price_dollars": "0.2000", "delta_fp": "-30.00"}, 2)
        clock[0] = C - 30 + 0.2
        eng.tick()
        ck(b11.q.qsize() == 1, "paper real fill (20 still shown after 1 s) queues one live order")
        run(b11)
        last = [s for s in sent if s[0] == "POST"][-1][2]
        ck(last["side"] == "bid" and last["price"] == "0.8000" and last["count"] == "1.00" and last["subaccount"] == 2,
           "live order: YES bid at 0.80 for round(20/20) = 1, subaccount 2")
        for rel in range(-29, 0):
            clock[0] = C + rel + 0.2
            eng.tick()
        clock[0] = C + 5
        eng.tick()
        eng.on_result("BTC-T", "yes", "101.00", clock[0])
        ls = [r for r in sink if r["ev"] == "live_settle" and r["ticker"] == "BTC-T"]
        ck(len(ls) == 1 and abs(ls[0]["pnl"] - 0.19) < 1e-9, "settle books +0.19 (1 x 0.20 - 1c fee)")
        # empty worlds: index on the strike with a fair book; and a certain side with no book
        eng2 = B.Engine(B.Logger(None, esink), lambda: clock[0], B.Tables(), ["forecaster"])
        clock[0] = 2 * C - 100
        eng2.add_market("E-T", "BTC", 2 * C, Decimal("100.00"), 2, "planted")
        for s in range(2 * C - 240, 2 * C + 1):
            eng2.on_print("BRTI", s * 1000, ("99.994", "99.996")[s % 2], s + 0.1)
        eng2.on_snapshot("E-T", {"no_dollars_fp": [["0.2000", "500.00"]], "yes_dollars_fp": [["0.2000", "500.00"]]}, 1)
        for rel in range(-30, -20):
            clock[0] = 2 * C + rel + 0.2
            eng2.tick()
        ck(b11.q.empty(), "coin-flip world (index on the strike, 80c both sides): nothing sent")
        eng3 = B.Engine(B.Logger(None, esink), lambda: clock[0], B.Tables(), ["forecaster"])
        clock[0] = 3 * C - 100
        eng3.add_market("N-T", "BTC", 3 * C, Decimal("100.00"), 2, "planted")
        for s in range(3 * C - 240, 3 * C + 1):
            eng3.on_print("BRTI", s * 1000, ("101.00", "101.01")[s % 2], s + 0.1)
        for rel in range(-60, 0):
            clock[0] = 3 * C + rel + 0.2
            eng3.tick()
        ck(b11.q.empty(), "no book: nothing sent")
        # the --variant path: a VEngine (race05_98) in the planted world sends the same single order as base
        engV = FV.VEngine(B.Logger(None, esink), lambda: clock[0], B.Tables(), FV.VARIANTS["race05_98"], "race05_98")
        clock[0] = 4 * C - 100
        engV.add_market("V-T", "BTC", 4 * C, Decimal("100.00"), 2, "planted")
        for s in range(4 * C - 240, 4 * C + 1):
            engV.on_print("BRTI", s * 1000, ("101.00", "101.01")[s % 2], s + 0.1)
        engV.on_snapshot("V-T", {"no_dollars_fp": [["0.2000", "50.00"], ["0.0100", "500.00"]],
                                 "yes_dollars_fp": [["0.0100", "40.00"]]}, 1)
        b12 = Broker(log, 2, False, fake_send, lambda: clock[0])
        BROKER = b12
        for rel in range(-60, -30):
            clock[0] = 4 * C + rel + 0.2
            engV.tick()
        engV.on_delta("V-T", {"side": "no", "price_dollars": "0.2000", "delta_fp": "-30.00"}, 2)
        clock[0] = 4 * C - 30 + 0.2
        engV.tick()
        ck(b12.q.qsize() == 1, "--variant race05_98: the 1-s survivor queues one live order, as base")
    finally:
        BROKER = None
    selftest_fresh_book(ck, log, sink, fake_send, run, mode)
    selftest_resend(ck, log, sink, sent, fake_send, run, mode)
    # the only write endpoints in this file: create order, and cancel of an IOC that rested
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src[:src.index("\ndef selftest" + "():")]
    ck(body.count('"POST"') == 1 and body.count('"DELETE"') == 1 and "/portfolio/subaccounts" not in body
       and "intra_exchange" not in body, "working code: one POST (create order), one DELETE (cancel), no money movement")
    # 2026-10-02: Kalshi filled 0.01 of a 5-contract IOC (NEAR 13:14Z); int(round(x)) booked it as 0, so the
    # bot's own day/run money (its stops) could drift from Kalshi's on fractional fills. Book the fraction.
    ck("int(round(out[\"filled\"" not in body and body.count("round(float(out[\"filled\"] or 0), 2)") == 2,
       "fractional fills are booked as fractions (0.01 stays 0.01), never rounded to whole contracts")
    print("forecaster_live self-test " + ("PASSED" if not fails else "FAILED: " + "; ".join(fails)))
    return not fails


class _StubWS:
    """The four attributes of the websocket client BookWatch reads, for the self-test worlds."""

    def __init__(self, sub_id, sid, tickers):
        self.connected, self.market_sub_id, self.sids, self.market_tickers = True, sub_id, {"orderbook_delta": sid}, tickers


def selftest_fresh_book(ck, log, sink, fake_send, run, mode):
    """v-fresh-book: the subscription-id race, every BookWatch rule, and two driven worlds (frozen book refuses and
    resubscribes; a quiet book still trades)."""
    global WATCH, BROKER
    w0, b0 = WATCH, BROKER
    try:
        # (1) the 10-11 / 10-13 race: the fake send runs the reader thread's _on_connect in the middle of the main
        # loop's market subscribe, the interleave of 10-13 15:45:42Z (request sent as 1368, recorded as 1369)
        def race(cls):
            w = cls(queue.Queue(), B.Logger(None, sink), lambda m, p: {})
            w.connected, w.reconnects, w.next_id = True, 86, 1366
            out, hit, at_send = [], [False], []

            def send_json(obj):
                out.append(obj)
                if not hit[0] and "market_tickers" in obj.get("params", {}):
                    hit[0] = True
                    at_send.append(w.market_sub_id)     # what a reply read by the reader thread right now compares to
                    w._on_connect()
                return True
            w.send_json = send_json
            w.set_markets(["KXBTC15M-T", "KXETH15M-T"])
            return w, [o for o in out if "market_tickers" in o.get("params", {})][0], out, at_send[0]
        WATCH = None
        w, req, out, seen = race(B.WS)
        ck(req["id"] != w.market_sub_id and seen is None, "NULL: the stock client sends the market request as %s but "
           "records %s, and nothing while it is in flight (the 10-13 race: its reply then looks superseded and is "
           "unsubscribed)" % (req["id"], w.market_sub_id))
        w, req, out, seen = race(FcWS)
        ck(req["id"] == w.market_sub_id == seen and len({o["id"] for o in out}) == len(out),
           "FcWS: the market request id is recorded BEFORE it is sent and stays (%s); every request id is unique" % req["id"])
        w.reconnects += 1
        w._on_connect()
        ck(w.market_sub_id is None and w.sids == {}, "FcWS: a reconnect still clears a request of the OLD connection")
        # (2) the queue wrapper: each message comes back unchanged, after the watch saw it
        WATCH = BookWatch(B.Logger(None, sink))
        q1 = queue.Queue()
        w1 = FcWS(q1, B.Logger(None, sink), lambda m, p: {})
        item = (5.0, {"type": "cfbenchmarks_value", "msg": {}})
        q1.put(item)
        ck(q1.get_nowait() is item and WATCH.last_print == 5.0 and WATCH.ws is w1,
           "FcWS: the main loop's queue hands back each message unchanged, after BookWatch saw it")

        # (3) the rules, on a stub client and a real engine's books
        def world():
            wt = BookWatch(B.Logger(None, sink))
            e = B.Engine(B.Logger(None, []), lambda: 0.0, B.Tables(), ["forecaster"])
            for tk in ("A", "Q"):
                e.books[tk] = B.Book()
                e.books[tk].load({"no_dollars_fp": [["0.2000", "50.00"]]}, 1, 7)
            wt.eng, wt.ws = e, _StubWS(10, 7, ["A", "Q"])
            wt.observe(100.0, {"type": "subscribed", "id": 10, "msg": {"channel": "orderbook_delta", "sid": 7}})
            for tk in ("A", "Q"):
                wt.observe(100.1, {"type": "orderbook_snapshot", "sid": 7, "msg": {"market_ticker": tk}})
            return wt, e
        tr = lambda tk: {"type": "trade", "msg": {"market_ticker": tk}}
        dl = lambda tk: {"type": "orderbook_delta", "sid": 7, "msg": {"market_ticker": tk}}
        pr = {"type": "cfbenchmarks_value", "msg": {}}

        def at(w_, t):                                  # an index print at t (the message clock moves), then scan
            w_.observe(t, pr)
            w_.scan(t)
        wt, e = world()
        for t in range(101, 159):                       # 58 s: prints live, A deltas, Q quiet (no trade, no delta)
            wt.observe(float(t), pr)
            wt.observe(t + 0.5, dl("A"))
            wt.scan(t + 0.6)
        ck(not wt.stale and e.books["Q"].synced and wt.fresh("Q", 158.6) and not e.resync_wanted,
           "a QUIET book (no trade, no delta for 58 s) while others move is not stale")
        wt.observe(159.2, dl("A"))
        wt.observe(160.0, tr("A"))                      # A: a delta 0.8 s BEFORE the trade = that trade's delta
        wt.observe(161.0, tr("Q"))                      # Q: its delta comes 1.5 s AFTER the trade
        at(wt, 162.4)
        ck(not wt.stale and wt.fresh("Q", 162.4), "a trade 1.4 s old without its book message yet: not stale")
        wt.observe(162.5, dl("Q"))
        at(wt, 166.0)
        ck(not wt.stale, "a trade with its book message 0.8 s before or 1.5 s after is matched (not stale)")
        wt.observe(170.0, tr("Q"))                      # a trade and NO book message after it
        wt.scan(190.0)
        ck(not wt.stale, "trade without a book message but NO later message seen yet (main loop behind): not stale")
        at(wt, 171.9)
        ck(not wt.stale and wt.fresh("Q", 171.9), "trade without a book message: not stale before 2 s")
        at(wt, 172.1)
        ck(list(wt.stale) == ["Q"] and not e.books["Q"].synced and e.books["A"].synced and e.resync_wanted
           and not wt.fresh("Q", 172.1) and wt.fresh("A", 172.1) and sink[-1]["ev"] == "book_resync",
           "trade + no book message for 2 s: THAT market stale (book unsynced), the other untouched, resubscribe asked")
        e.resync_wanted = False
        e.books["Q"].load({"no_dollars_fp": [["0.2000", "50.00"]]}, 1, 99)
        wt.observe(173.5, {"type": "orderbook_snapshot", "sid": 99, "msg": {"market_ticker": "Q"}})
        wt.scan(173.6)
        ck("Q" in wt.stale and not e.books["Q"].synced,
           "a snapshot of an UNconfirmed subscription (sid 99) does not make it fresh (re-unsynced before deciding)")
        wt.scan(176.0)
        ck(not e.resync_wanted, "one resubscribe per 10 s at most")
        wt.scan(183.2)
        ck(e.resync_wanted and sink[-1]["ev"] == "book_resync" and sink[-1]["why"] == "still_stale",
           "still stale 10 s after the last resubscribe: asked again")
        wt.ws.market_sub_id = 12
        wt.observe(183.5, {"type": "subscribed", "id": 12, "msg": {"channel": "orderbook_delta", "sid": 8}})
        wt.observe(183.6, {"type": "orderbook_snapshot", "sid": 8, "msg": {"market_ticker": "Q"}})
        ck(not wt.stale and sink[-1]["ev"] == "book_fresh" and sink[-1]["ticker"] == "Q",
           "the confirmed resubscribe's snapshot makes it fresh again (book_fresh logged)")
        wt.observe(185.1, tr("Q"))                      # deltas still dead: a trade 1.5 s after that snapshot ...
        at(wt, 187.0)
        ck(not wt.stale, "... not stale 1.9 s after the trade")
        at(wt, 187.2)
        ck(list(wt.stale) == ["Q"], "a snapshot 1.5 s BEFORE a trade is not that trade's book message: stale again "
           "2 s after it (deltas dead after a resubscribe, the 10-16 07:35Z shape if Kalshi kept failing)")
        wt, e = world()
        wt.ws.market_tickers = ["A", "Q", "N"]          # N subscribed, its snapshot never comes
        at(wt, 104.9)
        ck(not wt.stale, "a subscribed market without its snapshot: not flagged within 5 s of the confirmation")
        at(wt, 105.2)
        ck(list(wt.stale) == ["N"] and e.resync_wanted, "no snapshot 5 s after the confirmation: that market stale, "
           "resubscribe asked (A and Q, snapshotted, untouched)")
        wt, e = world()
        wt.observe(120.0, {"type": "error", "msg": {"code": 25, "msg": "Subscription buffer overflow"}})
        ck(sorted(wt.stale) == ["A", "Q"] and not e.books["A"].synced and e.resync_wanted,
           "error code 25 (10-16 07:35:41Z): every book stale at once, resubscribe asked")
        wt, e = world()
        wt.observe(120.0, {"type": "unsubscribed", "sid": 3})
        ck(not wt.stale, "an 'unsubscribed' for an old sid (our own resubscribe) changes nothing")
        wt.observe(120.1, {"type": "unsubscribed", "sid": 7})
        ck(sorted(wt.stale) == ["A", "Q"], "Kalshi unsubscribing the LIVE orderbook sid: every book stale")
        wt, e = world()
        wt.ws.market_sub_id = 11                        # a request whose reply never matches (the 10-13 outcome)
        at(wt, 130.0)
        at(wt, 134.9)
        ck(not wt.stale, "an unconfirmed subscription: not stale within 5 s")
        at(wt, 135.1)
        ck(sorted(wt.stale) == ["A", "Q"] and e.resync_wanted, "unconfirmed 5 s after it was sent: every book stale")
        wt, e = world()
        wt.observe(115.0, pr)
        wt.scan(115.1)
        ck(not wt.stale and not e.resync_wanted, "all books AND trades silent 14.9 s: not yet")
        wt.observe(115.5, pr)
        wt.scan(115.6)
        ck(sorted(wt.stale) == ["A", "Q"] and e.resync_wanted and not e.books["Q"].synced,
           "the 10-11 / 10-13 shape: no book message and no trade on ANY market for 15 s while index prints arrive "
           "-> every book stale, resubscribe asked")
        wt, e = world()
        wt.observe(105.0, pr)
        wt.scan(170.0)
        ck(not wt.stale, "the whole socket quiet (no prints either): left to bettor_paper's reconnect, not flagged")
        wt, e = world()
        wt.observe(105.0, pr)
        wt.observe(125.0, {"type": "market_lifecycle_v2", "msg": {}})
        wt.scan(125.1)
        ck(not wt.stale, "books silent 25 s but index prints stopped 20 s ago too: not the frozen-book shape, not flagged")
        wt, e = world()
        wt.observe(120.0, {"type": "error", "msg": {"code": 25}})
        wt.ws.market_tickers, wt.ws.market_sub_id = ["A2", "Q2"], 13   # the quarter-hour rolled while stale
        wt.scan(121.0)
        ck(not wt.stale, "a stale market that is no longer subscribed is forgotten (no endless resubscribes)")

        # (4) driven worlds: the real engine + hooks + broker (the planted forecaster world of the tests above)
        def driven(frozen):
            global WATCH, BROKER
            install_hooks()
            C = 5_000_000 if frozen else 6_000_000
            clk = [C - 100.0]
            en = B.Engine(B.Logger(None, []), lambda: clk[0], B.Tables(), ["forecaster"])
            WATCH = BookWatch(B.Logger(None, sink))
            WATCH.eng, WATCH.ws = en, _StubWS(20, 9, ["F-T", "G-T"])
            br = Broker(log, 2, False, fake_send, lambda: clk[0])
            BROKER = br
            en.add_market("F-T", "BTC", C, Decimal("100.00"), 2, "planted")
            for s in range(C - 240, C + 1):
                en.on_print("BRTI", s * 1000, ("101.00", "101.01")[s % 2], s + 0.1)
            book = {"no_dollars_fp": [["0.2000", "50.00"], ["0.0100", "500.00"]], "yes_dollars_fp": [["0.0100", "40.00"]]}
            WATCH.observe(C - 100.0, {"type": "subscribed", "id": 20, "msg": {"channel": "orderbook_delta", "sid": 9}})
            for tk in ("F-T", "G-T"):
                WATCH.observe(C - 100.0, {"type": "orderbook_snapshot", "sid": 9, "msg": {"market_ticker": tk}})
            en.on_snapshot("F-T", book, 1, 9)
            resub = []
            for k in range(int((C - 100) * 10), int((C - 15) * 10)):
                clk[0] = k / 10.0
                t = clk[0]
                if k % 10 == 0:                         # index prints, and ANOTHER market's book moving every second
                    WATCH.observe(t, {"type": "cfbenchmarks_value", "msg": {}})
                    WATCH.observe(t, {"type": "orderbook_delta", "sid": 9, "msg": {"market_ticker": "G-T"}})
                if frozen and abs(t - (C - 38.0)) < 1e-6:
                    WATCH.observe(t, {"type": "trade", "msg": {"market_ticker": "F-T"}})     # no book message follows
                en.tick()
                if en.resync_wanted and not resub:       # what run_live does: resubscribe; the new snapshots follow
                    en.resync_wanted = False
                    resub.append(t)
                    WATCH.ws.market_sub_id = 21
                if resub and abs(t - (C - 24.0)) < 1e-6:
                    WATCH.observe(t, {"type": "subscribed", "id": 21, "msg": {"channel": "orderbook_delta", "sid": 10}})
                    for tk in ("F-T", "G-T"):
                        WATCH.observe(t, {"type": "orderbook_snapshot", "sid": 10, "msg": {"market_ticker": tk}})
                    en.on_snapshot("F-T", book, 1, 10)
                if frozen and abs(t - (C - 30.5)) < 1e-6:
                    ck(br.want("F-T", C, "yes", 0.80, 100) == 0 and sink[-1]["why"] == "stale_book",
                       "FROZEN world: a direct broker order on the stale book is refused (why=stale_book)")
            return br, resub, en, C
        mode["v"], mode["fill"] = "fill", None
        br, resub, en, C = driven(False)
        o = list(br.orders.values())
        ck(br.q.qsize() == 1 and len(o) == 1 and o[0]["rel"] == -31 and not resub and not WATCH.stale,
           "QUIET world: its book silent 85 s, no trade -> the rel -31 survivor still queues one live order, no resubscribe")
        run(br)
        br, resub, en, C = driven(True)
        st = [r for r in sink if r["ev"] == "book_stale" and r["tickers"] == ["F-T"]]
        ck(st and st[-1]["why"] == "trade_without_book" and resub and abs(resub[0] - (C - 35.0)) < 0.25,
           "FROZEN world: trade at close-38 s, then >2 s of messages with no book message for it -> stale at "
           "close-35 s, resubscribe asked (%s)" % resub)
        ck(any(r["ev"] == "book_fresh" and r["ticker"] == "F-T" for r in sink) and not WATCH.stale,
           "FROZEN world: the resubscribe's snapshot (close-24 s) makes it fresh")
        o = list(br.orders.values())
        ck(len(o) == 1 and (o[0]["rel"] or -99) >= -24, "FROZEN world: no decision on the stale book (rel -31..-25 see it "
           "unsynced); the first live order comes after the fresh snapshot (%s)" % [(x["rel"], x["n"]) for x in o])
        run(br)

        # (5) a watch that breaks must never stop trading: its error is logged and the paper + broker go on as stock
        class _Boom(BookWatch):
            def scan(self, now):
                raise RuntimeError("planted watch failure")
        install_hooks()
        C2 = 8_000_000
        clk2 = [C2 - 40.0]
        esink2 = []
        en2 = B.Engine(B.Logger(None, esink2), lambda: clk2[0], B.Tables(), ["forecaster"])
        WATCH = _Boom(B.Logger(None, sink))
        WATCH.eng = en2
        br2 = Broker(log, 2, False, fake_send, lambda: clk2[0])
        BROKER = br2
        en2.add_market("Z-T", "BTC", C2, Decimal("100.00"), 2, "planted")
        for s in range(C2 - 240, C2 + 1):
            en2.on_print("BRTI", s * 1000, ("101.00", "101.01")[s % 2], s + 0.1)
        en2.on_snapshot("Z-T", {"no_dollars_fp": [["0.2000", "50.00"], ["0.0100", "500.00"]]}, 1)
        for rel in range(-40, -29):
            clk2[0] = C2 + rel + 0.2
            en2.tick()
        ck(br2.q.qsize() == 1 and any(r["ev"] == "watch_error" for r in esink2),
           "a BookWatch.scan that raises is logged (watch_error) and the paper + broker still trade, as stock")
        run(br2)
    finally:
        WATCH, BROKER = w0, b0


def selftest_resend(ck, log, sink, sent, fake_send, run, mode):
    """v-resend-dropped: OFF is today's behaviour exactly; ON re-sends once, only through every gate."""
    global RESEND, CRASH_GAP, WATCH, MAX_HELD
    saved = (RESEND, CRASH_GAP, WATCH, SCALE, MAX_PER_SIDE, MAX_PER_CLOSE, MAX_ORDER, MAX_HELD, MAX_COMMIT, DAY_STOP,
             RUN_STOP, MAX_SUB_BALANCE)

    class _Eng:
        """What resend_pass / paper_gate read from the engine: books, markets, the latest decision, prints, P."""

        def __init__(self, ask, clk, p_yes=0.90, v=100.50, back=None, decided=True, closed=False):
            b = B.Book()
            b.load({"no_dollars_fp": [["%.4f" % (1 - ask), "100.00"]]}, 1)
            self.books = {"R-T": b}
            m = B.Market("R-T", "BTC", 3030, Decimal("100.00"), 2, "planted")      # thr 99.995
            m.done = closed
            self.markets = {"R-T": m}
            self.P = dict(FV.DEFAULTS, **FV.VARIANTS["race1_98_r28"])
            self._fc_last = {"R-T": (-29, p_yes, v)} if decided else {}
            self.prints = {"BRTI": {} if back is None else {3030 - 29 - 5: (back, str(back), 0.0)}}
            self.now = lambda: clk[0]

    def world(on, ask=0.82, age=0.2, crash=None, held=None, stale=False, refill=False, **eng_kw):
        global RESEND, CRASH_GAP, WATCH, MAX_HELD
        RESEND, CRASH_GAP, WATCH = on, crash, None
        apply_scale(0.10)                               # 10 a side
        if held is not None:
            MAX_HELD = held
        clk = [3000.0]
        br = Broker(log, 2, False, fake_send, lambda: clk[0])
        n0 = len([s for s in sent if s[0] == "POST"])
        a = br.want("R-T", 3030, "yes", 0.80, 60)
        b = br.want("R-T", 3030, "yes", 0.82, 40)      # the paper's next level, while the first order is in flight
        run(br)
        if refill:
            br.want("R-T", 3030, "yes", 0.83, 5)
        if stale:
            WATCH = BookWatch(B.Logger(None, sink))
            WATCH.stale["R-T"] = {"why": "test", "since": clk[0]}
        clk[0] += age
        n = br.resend_pass(_Eng(ask, clk, **eng_kw))
        run(br)
        n2 = br.resend_pass(_Eng(ask, clk, **eng_kw))
        posts = [s[2] for s in sent if s[0] == "POST"][n0:]
        return a, b, n, n2, posts, br
    try:
        mode["v"], mode["fill"] = "fill", None
        a, b, n, n2, posts, br = world(False)
        ck((a, b, n, n2, len(posts)) == (6, 0, 0, 0, 1) and not br.due and "drop" not in br.pos[("R-T", "yes")],
           "NULL --resend-dropped OFF: the in-flight drop is refused and never re-sent (today's behaviour exactly)")
        a, b, n, n2, posts, br = world(True)
        pl = [r for r in sink if r["ev"] == "placed"][-1]
        ck((a, b, n, n2, len(posts)) == (6, 0, 4, 0, 2) and posts[1]["count"] == "4.00" and posts[1]["price"] == "0.8200"
           and pl.get("resend") is True and br.pos[("R-T", "yes")]["n"] == 10,
           "ON: once the first order is answered, the 4-contract deficit is re-sent ONCE at the trigger's 82c")
        rs = [o for o in br.orders.values() if o.get("resend")]
        ck(len(rs) == 1 and rs[0]["t_dec"] == 3000.0,
           "ON: the re-send carries the DROPPED trigger's time (writer's 1.5-s stale rule counts from it)")
        for kw, why, msg in ((dict(ask=0.60, crash=0.10), "crash", "the best ask collapsed 22c under the price: crash"),
                             (dict(ask=0.90), "resend_gone", "no ask at or under 82c any more: resend_gone"),
                             (dict(age=1.6), "resend_stale", "the trigger is 1.6 s old (> STALE_S): resend_stale"),
                             (dict(held=6), "cap", "the held cap is full: cap"),
                             (dict(stale=True), "stale_book", "the book is held stale: stale_book"),
                             (dict(p_yes=0.84), "resend_edge",
                              "the model's latest p 0.84 leaves < 2c edge at 82c after the fee: resend_edge"),
                             (dict(back=101.5), "resend_race",
                              "the index raced toward the strike (gap 1.5 -> 0.5 in 5 s, p 0.90 < 0.98): resend_race"),
                             (dict(decided=False), "resend_model", "no model decision to re-check: resend_model"),
                             (dict(closed=True), "resend_closed", "the market is done: resend_closed")):
            a, b, n, n2, posts, br = world(True, **kw)
            rf = [r for r in sink if r["ev"] == "refused"][-1]
            ck(n == 0 and len(posts) == 1 and rf["why"] == why and rf.get("resend") is True, "ON, gate re-checked: " + msg)
        a, b, n, n2, posts, br = world(True, refill=True)
        ck(n == 0 and len(posts) == 2 and posts[1]["count"] == "4.00" and posts[1]["price"] == "0.8300",
           "ON: a new paper fill after the answer asks for the whole deficit itself; nothing is re-sent twice")
        # the decision hook the paper-gate re-check reads: a pass-through (same decisions), removed again after
        # the test so a process started WITHOUT --resend-dropped never runs it
        def planted(C):
            esink = []
            clk = [C - 100.0]
            e = FV.VEngine(B.Logger(None, esink), lambda: clk[0], B.Tables(), FV.VARIANTS["race1_98_r28"], "race1_98_r28")
            e.add_market("H-T", "BTC", C, Decimal("100.00"), 2, "planted")
            for s in range(C - 240, C + 1):
                e.on_print("BRTI", s * 1000, ("101.00", "101.01")[s % 2], s + 0.1)
            e.on_snapshot("H-T", {"no_dollars_fp": [["0.2000", "50.00"], ["0.0100", "500.00"]]}, 1)
            for rel in range(-60, -19):
                clk[0] = C + rel + 0.2
                e.tick()
            return e, [{k: v for k, v in r.items() if k != "t"} for r in esink]
        hooked0 = bool(_orig_fc)
        e0, d0 = planted(7_000_000)
        install_resend_hook()
        try:
            e1, d1 = planted(7_000_000)
        finally:
            if not hooked0:
                FV.VEngine.forecaster = _orig_fc.pop("forecaster")
        last = getattr(e1, "_fc_last", {}).get("H-T")
        ck(d0 == d1 and any(r["ev"] == "taker_order" for r in d1) and last is not None and last[0] == -20
           and last[1] > 0.99 and not hasattr(e0, "_fc_last") and (hooked0 or not _orig_fc),
           "resend hook: decisions identical with and without it, the latest decision (rel -20, p %s) recorded, "
           "and it is removed after the test" % (None if last is None else round(last[1], 4)))
    finally:
        RESEND, CRASH_GAP, WATCH = saved[:3]
        _restore_rails(saved[3:])


def _restore_rails(r):
    global SCALE, MAX_PER_SIDE, MAX_PER_CLOSE, MAX_ORDER, MAX_HELD, MAX_COMMIT, DAY_STOP, RUN_STOP, MAX_SUB_BALANCE
    SCALE, MAX_PER_SIDE, MAX_PER_CLOSE, MAX_ORDER, MAX_HELD, MAX_COMMIT, DAY_STOP, RUN_STOP, MAX_SUB_BALANCE = r


# ---------------------------------------------------------------------------------------------------- main
def wire(br, olog, variant, book_watch=True):
    """What main() changes in bettor_paper before run_live, as one function (the offline replay calls it too):
    the paper->broker hooks, the stop-file exit, the --variant engine, and (v-fresh-book) FcWS + the BookWatch."""
    global BROKER, WATCH
    install_hooks()
    if RESEND:
        install_resend_hook()                      # --resend-dropped only (the paper-gate re-check needs it)
    BROKER = br
    orig_tick = B.Engine.tick

    def tick(self):
        orig_tick(self)
        if br.stopped and br.q.empty():
            olog.write("exit", why="stop file")
            os._exit(0)
    B.Engine.tick = tick
    params = FV.VARIANTS[variant]
    WATCH = BookWatch() if book_watch else None
    if book_watch:
        B.WS = FcWS                                # this process only: run_live builds its client from B.WS

    def make_engine(log, now_fn, tables, strats=None):
        e = FV.VEngine(log, now_fn, tables, params, variant)
        if WATCH is not None:
            WATCH.eng, WATCH.log = e, log          # stale/fresh/resync records go to the engine log, beside ws_*
        return e
    B.Engine = make_engine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--subaccount", type=int)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--minutes", type=float, default=10080)
    ap.add_argument("--variant", default="base", help="fc_variants.VARIANTS name; base = the paper forecaster exactly")
    ap.add_argument("--scale", type=float, default=0.05, help="live contracts per paper contract (default 0.05 = 1/20)")
    ap.add_argument("--auto-scale", action="store_true",
                    help="v-sub-autosize: scale = the subaccount's pot / 630 (clamped 0.02..1.0), re-read every 60 s and "
                         "applied only when flat; stops -20%% day / -33%% run / 70%% committed of the pot; no start cap. "
                         "--scale is ignored with it.")
    ap.add_argument("--crash-gap", type=float, default=None,
                    help="skip an order when the best ask at the trigger is more than this under its price (off by default)")
    ap.add_argument("--resend-dropped", action="store_true",
                    help="v-resend-dropped: re-send an in-flight drop once its order is answered, every gate re-checked (off by default)")
    ap.add_argument("--no-book-watch", action="store_true",
                    help="v-fresh-book OFF: the stock websocket client and no stale-book gate (the pre-10-18 behaviour)")
    a = ap.parse_args()
    if a.variant not in FV.VARIANTS:
        raise SystemExit("unknown --variant %s" % a.variant)
    B.selftest()                                   # raises on failure
    if not selftest():
        raise SystemExit("self-test failed; refusing to run")
    if a.selftest:
        return 0
    if not a.subaccount or a.subaccount < 1:
        raise SystemExit("--subaccount N (1..63) is required; the primary account is refused")
    if not a.auto_scale:
        apply_scale(a.scale)
    global CRASH_GAP, RESEND
    CRASH_GAP = a.crash_gap
    RESEND = bool(a.resend_dropped)
    if a.live == a.dry_run:
        raise SystemExit("choose exactly one of --live / --dry-run")
    import ordercli
    pk = ordercli.load_key(KEY_FILE)

    def sender(method, path, body, query):
        return ordercli.send(ordercli.PROD, pk, KEY_ID, method, path, body=body, query=query)
    st, bal = sender("GET", "/portfolio/balance", None, {"subaccount": a.subaccount, "exchange_index": POOL})
    try:
        sub_bal = float(bal["balance_dollars"])
    except Exception:
        raise SystemExit("subaccount balance unreadable (%s %s); refusing" % (st, str(bal)[:200]))
    pot = None
    for _try in range(5 if a.auto_scale else 0):    # v-fc-startretry (10-23): the start read retries 429s (the 00:40Z relaunch
        pot = read_pot(sender, a.subaccount)         # refused on one unreadable read, as the ladder did on 10-22)
        if pot is not None:
            break
        time.sleep(2.0)
    why = start_refusal(sub_bal, pot, a.live, a.auto_scale)
    if why:
        raise SystemExit(why + "; refusing")
    if os.path.exists(STOP_FILE):
        raise SystemExit("stop file present: %s" % STOP_FILE)
    B.NAME, B.LOG_PATH, B.STRATS = "forecaster_live", LIVE_LOG, ("forecaster",)
    orig_init = B.Engine.__init__

    def init(self, log, now_fn, tables, strats=("forecaster",)):
        orig_init(self, log, now_fn, tables, ("forecaster",))
    B.Engine.__init__ = init
    olog = B.Logger(ORDER_LOG)
    br = Broker(olog, a.subaccount, a.dry_run, sender, time.time)
    auto = None
    if a.auto_scale:
        br.sizer = AutoScale(olog, lambda: read_pot(sender, a.subaccount), time.time, br.flat, br.lock)
        br.sizer.start(pot)                        # sets SCALE and every rail from the pot; refuses under $10
        auto = {"pot_divisor": POT_DIVISOR, "scale_min": SCALE_MIN, "scale_max": SCALE_MAX, "reread_s": POT_REREAD_S,
                "day_stop_frac": DAY_STOP_FRAC, "run_stop_frac": RUN_STOP_FRAC, "commit_frac": COMMIT_FRAC}
    day_n, day_pnl = br.restore_day(ORDER_LOG, time.time())      # v-fc-dayrestore: after the day stop is set
    if br.halt_day is not None:
        olog.write("day_stop", day=br.halt_day, day_pnl=round(day_pnl, 4), restored=True)
    olog.write("start", pid=os.getpid(), subaccount=a.subaccount, live=a.live, sub_balance=sub_bal,
               day_restored={"settles": day_n, "day_pnl": round(day_pnl, 4)},
               variant=a.variant, variant_params=FV.VARIANTS[a.variant], crash_gap=CRASH_GAP,
               auto_scale=bool(a.auto_scale), pot=pot, auto=auto,
               rails={"scale": str(SCALE), "per_side": MAX_PER_SIDE, "per_close": MAX_PER_CLOSE, "per_order": MAX_ORDER,
                      "max_held": MAX_HELD, "max_commit": MAX_COMMIT, "px": [MIN_PX, MAX_PX], "day_stop": DAY_STOP,
                      "run_stop": RUN_STOP, "start_cap": MAX_SUB_BALANCE, "late_s": LATE_S, "stale_s": STALE_S,
                      "writes_per_s": WRITES_PER_S},
               resend_dropped=RESEND, book_watch=not a.no_book_watch,
               watch={"trade_gap_s": BOOK_TRADE_GAP_S, "pre_s": BOOK_PRE_S, "all_silent_s": BOOK_ALL_SILENT_S,
                      "print_live_s": PRINT_LIVE_S, "sub_confirm_s": SUB_CONFIRM_S, "resync_min_s": RESYNC_MIN_S})
    threading.Thread(target=br.run_writer, daemon=True).start()
    threading.Thread(target=br.run_poller, daemon=True).start()
    wire(br, olog, a.variant, book_watch=not a.no_book_watch)
    B.Logger(LIVE_LOG).write("selftest", passed=True, checks=0, variant=a.variant)
    B.run_live(a.minutes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
