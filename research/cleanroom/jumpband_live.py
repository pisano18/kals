#!/usr/bin/env python3
r"""jumpband_live.py -- the slow-coin JUMP-BAND buyer on the 15-minute crypto markets: PAPER arm and LIVE taker.

PURPOSE
  Run IDEA_LEDGER LS25 (VIABLE on a 42-day book replay, write-up in the jumpband scratch folder's VERDICT.md) as a
  paper bot: watch the index prints and the live order books, log every buy the rule WOULD make and what it would
  have earned, so the paper record can be judged against the replay (+6.6c a contract, about 11 buys a day, kill
  rule: under +3c a contract or a negative half on the first 150 buys). In PAPER mode it places NO orders.
  In LIVE mode (--live, approved 2026-10-30 for stage 1: 5 contracts a buy, subaccount 3, $50) the SAME decision
  sends ONE immediate-or-cancel limit buy through the order path copied from fxtake_live.py, the project's proven
  live taker.

THE RULE (definitions copied from scan.py / analyze.py of the replay; identical in paper and live)
  Markets  the 15-minute crypto series KXBNB15M, KXHYPE15M, KXZEC15M, KXNEAR15M (--series). The fast coins
           BTC/ETH/SOL/XRP/DOGE are added only with --fast-k 4: for them the trigger is k >= 4 and the band 70-95c.
  Index    Kalshi's websocket channel cfbenchmarks_value: one print a second per index. For each coin keep the
           trailing 300 one-second slots of print changes (a slot is empty when either second is missing, so a
           reconnect gap counts nothing); the sd is the sample sd over the valid changes, at least 150 of them,
           and excludes the current change.
  Trigger  a one-second print move of at least K x that sd (K = 2.0, --k) with 10 <= tau <= 60 s to the close,
           tau = close second - print second. Never inside the last 10 s, never beyond 60 s.
  Side     the side the jump favours: price up -> YES, price down -> NO (every 15M strike is a
           'greater_or_equal' line; settlement = mean of the 60 one-second prints before the close vs the strike).
           The projected settlement side is logged, not used (the replay found no gain in requiring it).
  Book     the live book is rebuilt from orderbook_snapshot + orderbook_delta (the ticker channel is throttled
           and misses half the asks, so it is NOT used). Act when the favoured side's best ask is in
           [--lo, --hi] = [0.70, 0.90]. Paper: a would-be IOC buy at the seen ask for everything offered at or
           below it, up to --max-contracts (100). Live: ONE IOC limit buy at the seen ask for
           min(floor(offered), --max-contracts) contracts. One buy per market, held to settlement.
  Fee      0.07 x price x (1 - price) per contract, rounded UP to the cent per order (the live fill books the
           fee Kalshi reports instead).
  Settle   paper: the result is computed from the 60 prints held AND confirmed from the market_lifecycle_v2
           'determined' message; both are logged, the lifecycle result wins when they differ. If no lifecycle
           message arrives within SETTLE_WAIT s of the close the computed result is booked and a later lifecycle
           message corrects it.
           live: Kalshi's market result, read with a signed GET /markets/<ticker> from 45 s after the close
           (fxtake_live's way); money = payout - cost - fees. The lifecycle result and the 60-print result are
           logged beside it for the audit, never booked.

MODES
  default  PAPER. The only secret needed is the key for the websocket handshake and the signed discovery GETs
           (research/kauth.py). Every would-be buy is logged as kind "paper_buy", every result as "paper_settle".
           Log results\jumpband-paper.jsonl, stop file results\jumpband-paper.stop.
  --live   LIVE. Needs --subaccount N (1..63; the primary account is refused) and the Kalshi key at
           C:\kals\kalshi.pem (fxtake_live.KEY_FILE); without either it refuses before anything connects.
           Same decisions as paper; where paper logs a paper buy, live sends ONE order (see THE ORDER).
           Log results\jumpband-live.jsonl, stop file results\jumpband-live.stop.
  --live --dry-run
           everything real (key, signed cash read, websockets, discovery, decisions) except sending: every order
           is logged as "would_order" with the exact body (and whether the pot could pay for it). Log
           results\jumpband-dryrun.jsonl, stop file results\jumpband-dryrun.stop.

THE ORDER (live; the mechanics are fxtake_live.py's, imported or copied verbatim)
  body     fxtake_live.order_body: ticker, side "bid" (buy YES at px) or "ask" (buy NO at px = sell YES at 1-px),
           count "%.2f", price "%.4f" (dollars, YES terms), time_in_force "immediate_or_cancel", post_only False,
           self_trade_prevention_type "taker_at_cross", client_order_id "jb-<ms>-<coin>", subaccount N,
           exchange_index = the MARKET's pool as read from its /markets row (never hardcoded; a market whose pool
           Kalshi did not give is not watched). IOC + post_only False = it takes what is offered at or under the
           limit and the rest is cancelled by the exchange: it never rests. An answer that says contracts are
           still live is cancelled and halts the bot (fxtake_live).
  rails    body_ok() before every send: the fields above exactly, count a whole number 1..--max-contracts
           <= LIVE_MAX_CONTRACTS (20, a code constant), price = the seen ask inside the series' band, subaccount
           >= 1, pool one of (0, 2). --max-cost (default $20.00 an order including the fee) refuses a dearer order.
           Live mode PINS the approved rule: --k, --lo, --hi, --fast-k and a series outside the four slow coins
           are refused unless --rule-override is given (and then logged in the start record).
  cash     the pot's cash per pool is read with fxtake_live.read_pool_cash at start, after every settle and every
           CASH_EVERY_S (5 min; within a minute after a no_cash skip). An order needs cash >= cost + fee or it is
           skipped and logged "no_cash" with the amounts; a fill lowers the local figure until the next read. The
           bot runs safely with an EMPTY pot and starts buying when money arrives (a pool that reads $0.00 or
           unreadable at start is said out loud: "pot_empty"). Money refusals (no_cash, max_cost, day_stop,
           halted) and a best level under one contract leave the market OPEN to a later jump; paper marks it
           bought, so the live and paper buy lists need not line up one for one (the replay's rule is per jump).
  books    the position is in the bot's books BEFORE the send: held[ticker] starts as an in-flight UNKNOWN order
           (qty 0, the body and client id kept) and "order_sent" is logged with the body; the answer then replaces
           it with the fill, or drops it on a 4xx / zero fill. Any error between the send and the booking (a log
           write, a bad answer) leaves the unknown position in place and halts: nothing the exchange filled can
           fall out of the books. The log never raises (a failed write goes to stderr and is counted in health).
  answer   pintake.normalise on the exchange's answer: fills, average price, fee. Kinds: "order" (every send,
           with the body and the raw answer), "fill" (contracts, price, fee, cost), "order_fail" (why: rejected
           = a 4xx, no_fill = the IOC missed, unreadable = halted until recover_unknown reads it back, resting =
           contracts still live, see below). The booked fee is the larger of Kalshi's reported average_fee_paid x
           fills and the cent-rounded formula (Kalshi charges the cent-rounded figure per order); both are logged.
  resting  an answer that says contracts are still live halts the bot; the order is cancelled (DELETE with the
           pot and pool) when an order_id came back, and WHATEVER the cancel answers the position stays UNKNOWN
           until recover_unknown reads the final record from the pot's order list (a record still resting is
           cancelled again, "cancel_retry"). So a failed cancel can never leave live contracts untracked.
  unknown  recover_unknown (every settle poll, from an executor thread) reads back every unknown order by client
           id from GET /portfolio/orders (min_ts back to the oldest unknown). An order the list never shows after
           UNKNOWN_MISSES (3) successful reads, once the market is UNKNOWN_CLOSE_GRACE_S (60 s) past its close, is
           written off ("recovered_none" + "settle_none" why unknown_written_off): it can add no exposure, and the
           bot can go flat so a stop file ends the run. The bot stays halted.
  stops    stop file results\jumpband-live.stop: no new orders, exit when flat (also honoured by the stop line).
           --stop-line (default -$25.00): the bot's own settled money since the first live record in its log,
           summed at start and kept running; at or under the line it logs "stop_line", writes the stop file and
           stands down for good (delete the file to resume). DAY_STOP -$15.00 settled in one ET day: no new
           orders for the rest of that day ("day_stop"); at start today's settles are summed from the log so a
           restart cannot trade past a day stop. A halt (unreadable answer, resting IOC) refuses new
           orders until the run is restarted. At the --minutes end the run stands down ("ending") and waits up to
           END_GRACE_S (10 min) for open positions to settle before exiting ("ending_open" names any left).
  restart  at start the live log is replayed (positions_from_log): every fill or recovered order with no later
           settle becomes a held live position again (polled for Kalshi's result), every order_sent with no
           answer booked becomes an unknown order (read back), every ordered market is marked bought, and
           today's settled money seeds the day stop. Logged as "restored".
  speed    the decision is made inside the websocket loop the instant the print is judged; the send itself runs on
           the bot's own order thread (one hand-off, well under a millisecond) so a slow or hung answer (ordercli's
           20 s timeout, another 20 s for a cancel) never freezes the stop-file watcher, settlement, the cash reads
           or the websocket keepalive. Round trip ~10-40 ms from the server; about one order every two hours.

FLAGS
  --series A,B,...      series to watch (default the four slow coins)
  --k 2.0               trigger size in trailing sds (slow coins)
  --lo 0.70 --hi 0.90   ask band for the slow coins
  --fast-k 4            also watch BTC/ETH/SOL/XRP/DOGE with k >= this and band 70-95c (off by default)
  --max-contracts N     cap per buy: paper default 100; live default 5, whole number, at most 20 (LIVE_MAX_CONTRACTS)
  --live                send real orders (needs --subaccount and the key)
  --subaccount N        the pot the live orders go to (1..63)
  --dry-run             with --live: everything but the send
  --max-cost 20.0       live: dollars an order may cost including the fee
  --stop-line -25.0     live: settled money that stands the bot down (negative dollars)
  --rule-override       live: allow --k / --lo / --hi / --fast-k / other series than the four slow coins
  --minutes 20160       run length (default 14 days)
  --log PATH            default by mode (see MODES)
  --selftest            offline self-test (fake prints, fake book, fake lifecycle, fake exchange, and run_live
                        itself on fake websocket and auth modules); exit 0 on PASS

LOG (JSON lines)  start, market, market_skipped, strike, ws_up, ws_down, ws_subscribe, ws_subscribed, ws_error,
  seq_gap, frame_error, trigger (every qualifying jump with the ask seen and the outcome; live: the refusal when
  the order path refused), paper_buy, paper_settle, lifecycle_late, settle_corrected, market_done, health (every
  5 min, with cash in live mode), stop_file, ending, exit;
  live adds restored, pot_empty, cash, cash_unreadable, order_skip, no_cash, max_cost, refused (day_stop / halted /
  no_pool), body_refused, would_order, order_sent, order, fill, order_fail, halt, cancelled, cancel_retry,
  recovered, recovered_none, place_error, lifecycle_result, settle, settle_none, day_stop, stop_line, stopping,
  stopped_flat, ending_open.

START ON THE SERVER (from C:\kals-repo; launch through WMI, never straight from an SSH shell):
    C:\Python314\python.exe research\cleanroom\jumpband_live.py --selftest
    C:\Python314\python.exe -u research\cleanroom\jumpband_live.py --minutes 20160                                   (paper)
    C:\Python314\python.exe -u research\cleanroom\jumpband_live.py --live --dry-run --subaccount 3 --max-contracts 5 --minutes 20
    C:\Python314\python.exe -u research\cleanroom\jumpband_live.py --live --subaccount 3 --max-contracts 5 --minutes 20160
"""
import argparse
import asyncio
import collections
import io
import json
import math
import os
import sys
import tempfile
import threading
import time
import types
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
# fxtake_live.py is the project's proven live taker; importing it runs nothing (constants and functions only).
from fxtake_live import order_body, read_pool_cash, et_day, POOLS, KEY_FILE, KEY_ID      # noqa: E402

SLOW = ("KXBNB15M", "KXHYPE15M", "KXZEC15M", "KXNEAR15M")
FAST = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M")
INDEX = {"KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI", "KXXRP15M": "XRPUSD_RTI",
         "KXDOGE15M": "DOGEUSD_RTI", "KXBNB15M": "BNBUSD_RTI", "KXHYPE15M": "HYPEUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
         "KXNEAR15M": "NEARUSD_RTI"}
ROUND_DIGITS = {"KXBTC15M": 2, "KXETH15M": 2, "KXSOL15M": 4, "KXXRP15M": 4, "KXDOGE15M": 7, "KXHYPE15M": 4,
                "KXBNB15M": 2, "KXZEC15M": 4, "KXNEAR15M": 4}          # fallback when Kalshi sends none
RESULTS = r"C:\kals-repo\results"
LOG = os.path.join(RESULTS, "jumpband-paper.jsonl")
PAPER_STOP_FILE = os.path.join(RESULTS, "jumpband-paper.stop")
LIVE_LOG = os.path.join(RESULTS, "jumpband-live.jsonl")
LIVE_STOP_FILE = os.path.join(RESULTS, "jumpband-live.stop")
DRY_LOG = os.path.join(RESULTS, "jumpband-dryrun.jsonl")
DRY_STOP_FILE = os.path.join(RESULTS, "jumpband-dryrun.stop")
STOP_FILE = PAPER_STOP_FILE          # the active mode's stop file; main() switches it for --live / --dry-run
WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
WS_PATH = "/trade-api/ws/v2"

K = 2.0
LO = 0.70
HI = 0.90
FAST_LO = 0.70
FAST_HI = 0.95
MAX_CONTRACTS = 100.0        # paper cap per would-be buy
TAU_LO = 10
TAU_HI = 60
SIGW = 300                   # trailing window, one slot per second
SIGMIN = 150                 # valid changes needed before the sd counts
MAX_LAG = 3.0                # a print older than this by the wall clock is not acted on (a replayed burst after a reconnect)
SETTLE_WAIT = 120.0          # seconds after the close before the computed result is booked without a lifecycle message
FORGET_S = 1200.0            # drop a market this long after its close
WATCH_AHEAD = 1200.0         # discover markets closing within this many seconds

# --- live rails (code constants; the flags may only tighten them) ---
LIVE_MAX_CONTRACTS = 20      # hard cap on contracts per live order, whatever --max-contracts says
LIVE_DEFAULT_CONTRACTS = 5   # stage 1 (operator, 2026-10-30): 5 contracts a buy in subaccount 3 with $50
MAX_COST = 20.0              # dollars an order may cost including the fee (--max-cost)
STOP_LINE = -25.0            # settled money since the first live record that stands the bot down (--stop-line)
DAY_STOP = -15.0             # settled money in one ET day that stops new orders for the rest of that day
CID_PREFIX = "jb-"
CRYPTO_POOL = 2              # the pool the 15M crypto markets have sat in (fxtake_live.POOL; read 10-27). ONLY the start-up
                             # pot_empty warning uses it: every order carries the pool read from its own market's row.
WRITES_PER_S = 2             # fxtake_live: the key is shared with the live bots
CASH_EVERY_S = 300.0         # re-read the pot's cash at least this often
CASH_RETRY_S = 60.0          # ... and within this long after a no_cash skip or a settle
SETTLE_AFTER_S = 45.0        # fxtake_live: ask Kalshi for the result from this long after the close
SETTLE_POLL_S = 15.0
SETTLE_TICK_S = 5.0          # the settle task's loop period (the self-test shortens it)
LATE_POLL_S = 300.0          # a position still open FORGET_S after its close is polled this often instead
END_GRACE_S = 600.0          # live: after the --minutes end, wait this long for open positions to settle before exiting
UNKNOWN_MISSES = 3           # successful order-list reads without the client id before an unknown order is written off ...
UNKNOWN_CLOSE_GRACE_S = 60.0  # ... and only once the market is this long past its close (an IOC there can add nothing)


# ---------------------------------------------------------------------------------------------------- helpers
def fee(n, px):
    """Kalshi taker fee in dollars for n contracts at px, rounded up to the cent per order (analyze.py)."""
    if n <= 0:
        return 0.0
    return math.ceil(0.07 * px * (1 - px) * n * 100 - 1e-9) / 100.0


def parse_iso(s):
    return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def rss_mb():
    try:
        import ctypes
        import ctypes.wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC(); pmc.cb = ctypes.sizeof(PMC)
        k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), wt.DWORD]
        if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return None
        return round(pmc.WorkingSetSize / 1e6, 1)
    except Exception:
        return None


def line_money_from_log(path):
    """fxtake_live.line_pnl_from_log, for this bot's log: settled money since the first live record = every 'settle'
    record's money, the LAST settle per ticker (a market a restart books twice counts once). Unreadable lines are
    skipped; a missing log is 0.0."""
    last = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if r.get("kind") == "settle":
                        last[r["ticker"]] = float(r["money"])
                except Exception:
                    continue
    except FileNotFoundError:
        return 0.0
    return round(sum(last.values()), 4)


def body_ok(b, sub, pool, px, n, max_contracts, lo, hi):
    """fxtake_live.body_ok, with this bot's rails: every order body must carry these, or it is not sent. The body's
    pool must be the MARKET's pool, one of POOLS; the count the whole number decided, 1..max_contracts, under the
    hard cap; the buy price exactly the seen ask, inside the series' band; a subaccount, never the primary account."""
    try:
        c = float(b["count"]); p = float(b["price"])
    except Exception:
        return False
    buy_px = p if b.get("side") == "bid" else round(1 - p, 4)
    return (b.get("side") in ("bid", "ask") and b.get("post_only") is False
            and b.get("time_in_force") == "immediate_or_cancel"
            and b.get("self_trade_prevention_type") == "taker_at_cross"
            and sub is not None and b.get("subaccount") == int(sub) and int(sub) >= 1
            and pool is not None and int(pool) in POOLS and b.get("exchange_index") == int(pool)
            and abs(c - float(n)) < 1e-9 and abs(c - round(c)) < 1e-9
            and 1 <= c <= float(max_contracts) <= LIVE_MAX_CONTRACTS
            and abs(buy_px - float(px)) < 1e-9 and lo - 1e-9 <= buy_px <= hi + 1e-9
            and str(b.get("client_order_id", "")).startswith(CID_PREFIX))


class Logger:
    """One JSON record a line, opened for append on every write (a hard kill loses nothing). NEVER raises: a write
    the disk refuses (full, locked) goes to stderr instead and is counted (failed / n_failed, reported in health),
    so a log problem can never unseat a position from the bot's books."""

    def __init__(self, path=None, sink=None, now=None):
        self.path, self.sink, self.now = path, sink, now
        self.lock = threading.Lock()
        self.failed = None
        self.n_failed = 0

    def write(self, kind, **kw):
        t = self.now() if self.now else time.time()
        rec = {"t": iso(t), "kind": kind}
        rec.update(kw)
        try:
            line = json.dumps(rec, default=str)
        except Exception as e:                                    # a value json cannot render even as str
            line = json.dumps({"t": iso(t), "kind": kind, "unserialisable": repr(e)[:200]})
        with self.lock:
            if self.sink is not None:
                self.sink.append(rec)
            if self.path:
                try:
                    with open(self.path, "a", encoding="utf-8") as fh:
                        fh.write(line + "\n")
                except Exception as e:
                    self.failed = "%s: %s" % (type(e).__name__, str(e)[:160])
                    self.n_failed += 1
                    try:
                        sys.stderr.write("LOG WRITE FAILED (%s): %s\n" % (self.failed, line))
                        sys.stderr.flush()
                    except Exception:
                        pass


# ---------------------------------------------------------------------------------------------------- the index sd
class Sigma:
    """scan.py's sig_series, kept live: one slot per second holding the one-second change (None when the second
    before is missing), the last SIGW slots; sd = sample sd over the valid changes, None under SIGMIN of them.
    Call sd() BEFORE push(): the sd a print is judged against ends at the second before it."""

    def __init__(self):
        self.q = collections.deque()
        self.s1 = self.s2 = 0.0
        self.n = 0
        self.last_sec = None
        self.last_v = None

    def sd(self):
        if self.n < SIGMIN:
            return None
        mu = self.s1 / self.n
        var = (self.s2 - self.n * mu * mu) / (self.n - 1)
        return math.sqrt(var) if var > 0 else None

    def _slot(self, d):
        self.q.append(d)
        if d is not None:
            self.s1 += d; self.s2 += d * d; self.n += 1
        if len(self.q) > SIGW:
            o = self.q.popleft()
            if o is not None:
                self.s1 -= o; self.s2 -= o * o; self.n -= 1

    def push(self, sec, v):
        """Returns the change from the second before (None after a gap), or the string 'dup' for an old print."""
        if self.last_sec is not None:
            if sec <= self.last_sec:
                return "dup"
            for _ in range(min(sec - self.last_sec - 1, SIGW)):     # the missing seconds hold nothing
                self._slot(None)
            d = (v - self.last_v) if sec == self.last_sec + 1 else None
        else:
            d = None
        self._slot(d)
        self.last_sec, self.last_v = sec, v
        return d


# ---------------------------------------------------------------------------------------------------- book
class Book:
    """Resting bids per side (fxtake_live.Book); the ask for a side is 1 - the other side's best bid."""

    def __init__(self):
        self.yes, self.no = {}, {}
        self.synced = False
        self.last_msg = None

    def snapshot(self, msg, t):
        self.yes, self.no = {}, {}
        for side, d in (("yes", self.yes), ("no", self.no)):
            for a, b in (msg.get(side + "_dollars_fp") or msg.get(side + "_dollars") or []):
                d[round(float(a), 4)] = float(b)
            for a, b in (msg.get(side) or []):                      # cents form, if ever sent
                d[round(float(a) / 100.0, 4)] = float(b)
        self.synced, self.last_msg = True, t

    def delta(self, msg, t):
        d = self.yes if msg.get("side") == "yes" else self.no
        px = round(float(msg["price_dollars"]), 4)
        d[px] = d.get(px, 0.0) + float(msg["delta_fp"])
        if d[px] <= 1e-9:
            d.pop(px, None)
        self.last_msg = t

    def best_bid(self, side):
        d = self.yes if side == "yes" else self.no
        return max(d) if d else None

    def asks(self, side):
        """[(ask px ascending, qty)] for buying `side`, from the other side's bids."""
        d = self.no if side == "yes" else self.yes
        return sorted((round(1 - p, 4), q) for p, q in d.items() if q > 1e-9)


# ---------------------------------------------------------------------------------------------------- the rule
class Trader:
    """Prints in, books in, buys and settles out. Pure except for the sender it is given (live); the clock is
    injected. Paper and live share every decision; they part in place()."""

    def __init__(self, log, live=False, now=time.time, k=K, lo=LO, hi=HI, max_contracts=None, fast_k=None,
                 sub=None, dry=False, sender=None, max_cost=MAX_COST, stop_line=STOP_LINE):
        if max_contracts is None:
            max_contracts = LIVE_DEFAULT_CONTRACTS if live else MAX_CONTRACTS
        self.log, self.live, self.now = log, live, now
        self.k, self.lo, self.hi, self.max_contracts, self.fast_k = float(k), float(lo), float(hi), float(max_contracts), fast_k
        self.sub = None if sub is None else int(sub)
        self.dry, self.send = bool(dry), sender
        self.max_cost = float(max_cost)
        self.stop_line = None if stop_line is None else float(stop_line)
        if live:                                                  # the rails hold without the CLI
            if self.sub is None or not (1 <= self.sub <= 63):
                raise SystemExit("live mode needs --subaccount N (1..63); the primary account is refused")
            if sender is None:
                raise SystemExit("live mode needs a signed sender (no Kalshi key loaded): refusing before anything connects")
            if self.max_contracts != int(self.max_contracts) or not (1 <= self.max_contracts <= LIVE_MAX_CONTRACTS):
                raise SystemExit("live --max-contracts must be a whole number 1..%d (LIVE_MAX_CONTRACTS)" % LIVE_MAX_CONTRACTS)
        self.markets = {}        # ticker -> {"close_s","series","index","strike","rd","strike_src","triggers","inband","done","pool"}
        self.books = {}          # ticker -> Book
        self.sig = {}            # index_id -> Sigma
        self.prints = {}         # index_id -> {sec: value} for the last ~8 minutes
        self.bought = set()      # one buy per market, ever (paper buy, live order or would-be order)
        self.held = {}           # ticker -> the position (paper or live)
        self.skipped = set()     # live: markets whose pool Kalshi did not give, logged once
        self.n_prints = collections.Counter()
        self.prints_since = now()
        self.n_triggers = self.n_buys = self.n_settled = self.n_lost = 0
        self.n_orders = self.n_fills = 0
        self.run_pnl = 0.0       # paper: paper money; live: settled money this run
        self.stopped = False
        # --- live money state (fxtake_live.Trader) ---
        self.pool_cash = None    # {pool: the pot's cash there}, read from Kalshi; None = not read
        self.cash_dirty = False  # a re-read is wanted (after a settle or a no_cash skip)
        self.day, self.day_money = None, 0.0
        self.line_money = None   # settled money since the first live record; only main() seeds it, so no test world
                                 # can ever write the real stop file
        self.halt_day = None
        self.halted = None
        self._w = []
        self.lock = threading.RLock()   # held, pool_cash and the counters are touched from the order thread and the loop
        self.dispatch = None            # live: run_live sets fn(callable, *args) that runs the send on the order thread;
                                        # None (tests, no loop) sends inline
        self.n_written_off = 0

    # --- rule parameters per series ---
    def rule_for(self, series):
        if series in FAST:
            return float(self.fast_k), FAST_LO, FAST_HI
        return self.k, self.lo, self.hi

    # --- markets ---
    def add_market(self, tk, series, close_s, strike=None, rd=None, strike_src=None, pool=None):
        m = self.markets.get(tk)
        if m is None:
            if series in FAST and self.fast_k is None:
                return
            if self.live and (pool is None or int(pool) not in POOLS):   # fxtake_live: a market whose pool Kalshi did not give is never traded
                if tk not in self.skipped:
                    self.skipped.add(tk)
                    self.log.write("market_skipped", ticker=tk, why="pool", exchange_index=pool)
                return
            m = {"close_s": float(close_s), "series": series, "index": INDEX.get(series), "strike": None, "rd": None,
                 "strike_src": None, "triggers": 0, "inband": 0, "done": False, "pool": None if pool is None else int(pool)}
            self.markets[tk] = m
            self.books[tk] = Book()
            self.log.write("market", ticker=tk, series=series, close_s=close_s, close=iso(close_s), rule=self.rule_for(series), pool=m["pool"])
        elif pool is not None and m.get("pool") is None:
            m["pool"] = int(pool)
        if strike is not None and (m["strike"] != float(strike) or m["rd"] != rd):
            m["strike"], m["rd"], m["strike_src"] = float(strike), rd, strike_src
            self.log.write("strike", ticker=tk, strike=m["strike"], round_digits=rd, src=strike_src)

    def on_snapshot(self, tk, msg, now):
        b = self.books.get(tk)
        if b is not None:
            b.snapshot(msg, now)

    def on_delta(self, tk, msg, now):
        b = self.books.get(tk)
        if b is not None and b.synced:
            b.delta(msg, now)

    def unsync(self):
        for b in self.books.values():
            b.synced = False

    # --- prints and the decision (identical in paper and live) ---
    def on_print(self, iid, sec, value, now, sending_ms=None):
        sg = self.sig.get(iid)
        if sg is None:
            sg = self.sig[iid] = Sigma()
        sd = sg.sd()                                              # over the changes ending at sec - 1
        d = sg.push(sec, value)
        if d == "dup":
            return
        pr = self.prints.get(iid)
        if pr is None:
            pr = self.prints[iid] = {}
        pr[sec] = value
        if len(pr) > 600:
            for s in [s for s in pr if s < sec - 480]:
                del pr[s]
        self.n_prints[iid] += 1
        if d is None or not sd:
            return
        dz = d / sd
        for tk, m in self.markets.items():
            if m["index"] != iid:
                continue
            tau = int(round(m["close_s"])) - sec
            if not (TAU_LO <= tau <= TAU_HI):
                continue
            k, lo, hi = self.rule_for(m["series"])
            if abs(dz) < k:
                continue
            m["triggers"] += 1
            self.n_triggers += 1
            side = "yes" if dz > 0 else "no"
            b = self.books.get(tk)
            ask, size = None, 0.0
            if b is not None and b.synced:
                asks = b.asks(side)
                if asks:
                    ask, size = asks[0]
            proj, pside = self.projection(m, pr, sec, value)
            rec = {"ticker": tk, "side": side, "tau": tau, "print_move_sd": round(dz, 3), "sigma": sd, "move": round(d, 8),
                   "value": value, "sec": sec, "lag_s": round(now - sec, 3), "k": k, "band": [lo, hi], "ask": ask,
                   "ask_size": size, "proj": proj, "pside": pside, "strike": m["strike"]}
            if tk in self.bought:
                why = "already_bought"
            elif b is None or not b.synced:
                why = "no_book"
            elif ask is None:
                why = "no_ask"
            elif now - sec > MAX_LAG:
                why = "stale_print"
            elif not (lo - 1e-9 <= ask <= hi + 1e-9):
                why = "out_of_band"
            elif self.stopped:
                why = "stopped"
            else:
                why = None
            if why is None or why == "stopped":
                m["inband"] += 1
            plan = None
            if why is None and self.live:                         # live: the order path's own refusal, if any, goes in the record
                plan = self.plan_live(tk, side, ask, size, rec, sending_ms)
            self.log.write("trigger", outcome=why or (plan["why"] if plan else None) or "buy", **rec)
            if why is not None:
                continue
            if not self.live:
                self.place(tk, side, ask, size, rec, sending_ms)
            elif plan["why"] is not None:
                self.log_refusal(plan)
            elif self.commit_live(plan):
                if self.dispatch is not None:
                    self.dispatch(self.send_live, plan)
                else:
                    self.send_live(plan)

    def projection(self, m, pr, sec, value):
        """scan.py's proj / pside: the settlement average if the index stayed here, and the side it gives."""
        if m["strike"] is None:
            return None, None
        C = int(round(m["close_s"]))
        locked = [pr.get(s) for s in range(C - 60, sec + 1)]
        locked = [x for x in locked if x is not None]
        if sec < C - 60:
            proj = value
        else:
            proj = (sum(locked) + (60 - len(locked)) * value) / 60.0
        rd = m["rd"]
        keff = m["strike"] - (0.5 * 10 ** (-rd) if rd is not None else 0.0)
        return round(proj, 8), ("yes" if proj >= keff else "no")

    def place(self, tk, side, ask, size, rec, sending_ms=None):
        """Paper: the would-be IOC at the seen ask for everything at or below it (= the best level), capped.
        Live: the same decision becomes ONE real IOC (place_live = plan_live + commit_live + send_live)."""
        if self.live:
            self.place_live(tk, side, ask, size, rec, sending_ms)
            return
        qty = round(min(size, self.max_contracts), 2)
        if qty <= 0:
            return
        cost = round(qty * ask, 4)
        f = fee(qty, ask)
        m = self.markets[tk]
        self.bought.add(tk)
        self.held[tk] = {"side": side, "qty": qty, "px": ask, "cost": cost, "fee": f, "close_s": m["close_s"],
                         "settled": False, "result": None, "pnl": None, "src": None}
        self.n_buys += 1
        self.log.write("paper_buy", ticker=tk, series=m["series"], side=side, tau=rec["tau"], print_move_sd=rec["print_move_sd"],
                       sigma=rec["sigma"], move=rec["move"], value=rec["value"], sec=rec["sec"], ask=ask, ask_size=size, qty=qty,
                       cost=cost, fee=f, lag_s=rec["lag_s"], sending_ts_ms=sending_ms, k=rec["k"], band=rec["band"],
                       strike=m["strike"], proj=rec["proj"], pside=rec["pside"])

    # --- the live order path (fxtake_live.Trader.place, for a jump-band buy) ---
    def _throttle(self):
        """fxtake_live.Trader._throttle: at most WRITES_PER_S order writes a second (the key is shared)."""
        now = time.time()
        self._w = [t for t in self._w if now - t < 1.0]
        if len(self._w) >= WRITES_PER_S:
            time.sleep(max(0.0, 1.0 - (now - self._w[0])))
        self._w.append(time.time())

    def place_live(self, tk, side, px, size, rec, sending_ms=None):
        """The whole live order path inline (tests, and any caller without a loop): plan, log a refusal or commit the
        order to the books and send it. Returns the refusal string, or None when an order was sent (or would be)."""
        p = self.plan_live(tk, side, px, size, rec, sending_ms)
        if p["why"] is not None:
            self.log_refusal(p)
            return p["why"]
        if self.commit_live(p):
            self.send_live(p)
        return None

    def plan_live(self, tk, side, px, size, rec, sending_ms=None):
        """Pure: the order the rule asks for and every refusal that needs no network. Nothing is logged or marked here.
        Returns {"why": None | refusal, "kind": the record kind for a refusal, "extra": its fields, "body", "cid", ...}."""
        m = self.markets[tk]
        now = self.now()
        n = int(min(math.floor(size + 1e-9), self.max_contracts))
        cost = round(n * px, 4)
        f = fee(n, px)
        need = round(cost + f, 4)
        pool = m.get("pool")
        with self.lock:
            cash = None if self.pool_cash is None else self.pool_cash.get(pool)
        base = {"ticker": tk, "series": m["series"], "side": side, "tau": rec["tau"], "print_move_sd": rec["print_move_sd"],
                "sigma": rec["sigma"], "move": rec["move"], "value": rec["value"], "sec": rec["sec"], "lag_s": rec["lag_s"],
                "k": rec["k"], "band": rec["band"], "strike": m["strike"], "proj": rec["proj"], "pside": rec["pside"],
                "ask": px, "ask_size": size, "qty": n, "cost": cost, "fee": f, "need": need, "cash": cash, "pool": pool,
                "max_cost": self.max_cost, "subaccount": self.sub}
        p = {"tk": tk, "side": side, "px": px, "size": size, "n": n, "cost": cost, "fee": f, "need": need, "pool": pool,
             "cash": cash, "base": base, "rec": rec, "sending_ms": sending_ms, "close_s": m["close_s"], "series": m["series"],
             "strike": m["strike"], "why": None, "kind": None, "extra": {}, "cid": None, "body": None, "t": now}
        if n < 1:
            p.update(why="under_one_contract", kind="order_skip")
            return p
        if pool is None or int(pool) not in POOLS:
            p.update(why="no_pool", kind="refused")
            return p
        if self.halted:
            p.update(why="halted", kind="refused", extra={"halt": self.halted})
            return p
        if self.halt_day == et_day(now):
            p.update(why="day_stop", kind="refused", extra={"day": self.halt_day, "day_money": round(self.day_money, 4)})
            return p
        if need > self.max_cost + 1e-9:
            p.update(why="max_cost", kind="max_cost")
            return p
        if not self.dry and (cash is None or cash < need - 1e-9):
            self.cash_dirty = True                                # ask for a fresh read: money may have arrived
            p.update(why="no_cash", kind="no_cash")
            return p
        cid = "%s%d-%s" % (CID_PREFIX, int(now * 1000), tk.split("-")[0][2:6].lower())
        k, lo, hi = self.rule_for(m["series"])
        b = order_body(tk, side, px, n, self.sub, cid, pool)       # fxtake_live's body, the market's own pool
        if not body_ok(b, self.sub, pool, px, n, self.max_contracts, lo, hi):
            p.update(why="body_refused", kind="body_refused", extra={"body": b})
            return p
        p.update(cid=cid, body=b)
        return p

    def log_refusal(self, p):
        """The refusal record for a plan that refused: the same kinds and fields as before (order_skip / refused carry
        why; max_cost, no_cash and body_refused carry the plan's base fields)."""
        kw = dict(p["extra"])
        kw.update(p["base"])
        if p["kind"] in ("order_skip", "refused"):
            self.log.write(p["kind"], why=p["why"], **kw)
        else:
            self.log.write(p["kind"], **kw)

    def commit_live(self, p):
        """On the loop thread, BEFORE the send: mark the market bought (never a second order here), count the order and,
        unless --dry-run, put the position in the books as an in-flight UNKNOWN order and log order_sent with the body.
        Returns True when send_live must follow (False for --dry-run, which logs would_order instead)."""
        tk, b, cid, pool = p["tk"], p["body"], p["cid"], p["pool"]
        self.bought.add(tk)
        self.n_orders += 1
        if self.dry:
            self.log.write("would_order", body=b, funded=(p["cash"] is not None and p["cash"] >= p["need"] - 1e-9),
                           sending_ts_ms=p["sending_ms"], **p["base"])
            return False
        with self.lock:
            self.held[tk] = {"side": p["side"], "qty": 0.0, "px": p["px"], "cost": 0.0, "fee": 0.0, "close_s": p["close_s"],
                             "settled": False, "result": None, "money": None, "src": None, "cid": cid, "sub": self.sub, "pool": pool,
                             "live": True, "unknown": True, "inflight": True, "body": b, "t_sent": p["t"], "misses": 0, "asked": p["n"]}
        self.log.write("order_sent", cid=cid, body=b, close_s=p["close_s"], sending_ts_ms=p["sending_ms"], **p["base"])
        return True

    def send_live(self, p):
        """On the order thread: the send, then the booking of the answer. Any exception in the booking leaves the
        in-flight unknown position in the books and halts the bot (recover_unknown then reads the order back)."""
        tk, cid = p["tk"], p["cid"]
        self._throttle()
        t0 = time.time()
        try:
            st, r = self.send("POST", "/portfolio/events/orders", p["body"], None)
        except Exception as e:
            st, r = -1, repr(e)[:300]
        try:
            self.book_answer(p, st, r, t0)
        except Exception as e:
            with self.lock:
                v = self.held.get(tk)
                booked = v is None or not v.get("inflight")       # popped (4xx / no fill) or booked: only the records failed
                if not booked:
                    v["inflight"] = False
                    v["unknown"] = True
                    self.halted = self.halted or "booking failed for %s: %s" % (cid, repr(e)[:160])
            if booked:
                self.log.write("book_error", ticker=tk, cid=cid, err=repr(e)[:200], note="the books are complete; a record after the booking failed")
            else:
                self.log.write("halt", why="booking failed for %s (the position is kept as unknown): %s" % (cid, repr(e)[:200]))

    def book_answer(self, p, st, r, t0):
        """pintake.normalise on the exchange's answer, then the BOOKS FIRST, under the lock, before any record is written
        or any second request made: a 4xx drops the in-flight position (nothing placed), an unreadable answer keeps it
        unknown and halts, contracts still live keep it unknown (and halt; the cancel follows), a fill replaces it, a
        zero fill drops it. Then the records, then the cancel for a resting order."""
        import pintake
        tk, cid, b, n, px, pool, side = p["tk"], p["cid"], p["body"], p["n"], p["px"], p["pool"], p["side"]
        out = pintake.normalise(st, r, b)
        filled = round(float(out["filled"] or 0), 2) if out["parsed"] else 0.0
        readable = pintake._readable(out)
        fpx = out["exec_price"] if out["exec_price"] is not None else px
        fee_rep = out["fee_total"]
        ff = self.book_fee(filled, fpx, fee_rep) if readable else 0.0
        fcost = round(filled * fpx, 4)
        oid = out.get("order_id")
        with self.lock:                                           # --- the books, complete before anything else ---
            v = self.held[tk]
            if st is not None and 400 <= st < 500:                 # rejected: nothing placed, the market stays decided
                outcome = "rejected"
                self.held.pop(tk, None)
            elif not readable:                                    # an order we cannot see: halt until it is read back
                outcome = "unreadable"
                v.update(inflight=False, unknown=True)
                self.halted = "unknown answer for %s (status %s)" % (cid, st)
            elif pintake._is_live(out):                           # an IOC must never rest: halt; UNKNOWN until the final record
                outcome = "resting"
                v.update(inflight=False, unknown=True, order_id=oid, qty=filled, px=fpx, cost=fcost, fee=ff, cancel_status=None)
                self.halted = "IOC came back resting: %s" % (oid or cid)
            elif filled > 0:
                outcome = "fill"
                v.update(qty=filled, px=fpx, cost=fcost, fee=ff, order_id=oid, inflight=False)
                v.pop("unknown", None)
                self.n_fills += 1
                if self.pool_cash is not None and self.pool_cash.get(pool) is not None:
                    self.pool_cash[pool] = round(self.pool_cash[pool] - fcost - ff, 4)      # until the next read
            else:
                outcome = "no_fill"
                self.held.pop(tk, None)
            cash = self.pool_cash.get(pool) if self.pool_cash else None
        # --- the records ---
        self.log.write("order", body=b, status=st, order_id=oid, filled=filled, remaining=out["remaining"],
                       exec_px=out["exec_price"], fee_total=fee_rep, rtt=round(time.time() - t0, 3), resp=str(r)[:300],
                       sending_ts_ms=p["sending_ms"], outcome=outcome, **p["base"])
        if outcome == "rejected":
            self.log.write("order_fail", why="rejected", ticker=tk, cid=cid, status=st, error=out.get("error"))
        elif outcome == "unreadable":
            self.log.write("order_fail", why="unreadable", ticker=tk, cid=cid, status=st)
            self.log.write("halt", why=self.halted)
        elif outcome == "resting":
            self.log.write("halt", why=self.halted)
            st2, r2 = None, None
            if oid:                                               # the cancel, after the books already say unknown
                try:
                    st2, r2 = self.send("DELETE", "/portfolio/events/orders/%s" % oid, None,
                                        {"subaccount": self.sub, "exchange_index": pool})
                except Exception as e:
                    st2, r2 = -1, repr(e)[:300]
                with self.lock:
                    v["cancel_status"] = st2
                self.log.write("cancelled", order_id=oid, status=st2, resp=str(r2)[:200], ok=(st2 is not None and 200 <= st2 < 300))
            self.log.write("order_fail", why="resting", ticker=tk, cid=cid, order_id=oid, filled=filled, remaining=out["remaining"],
                           cancel_status=st2, note="position kept unknown until recover_unknown reads the final record")
        elif outcome == "fill":
            rec = p["rec"]
            self.log.write("fill", ticker=tk, series=p["series"], side=side, qty=filled, price=fpx, cost=fcost, fee=ff,
                           fee_reported=None if fee_rep is None else round(fee_rep, 4), asked=n, cid=cid, order_id=oid,
                           cash=cash, pool=pool, close_s=p["close_s"], tau=rec["tau"], print_move_sd=rec["print_move_sd"],
                           strike=p["strike"], pside=rec["pside"])
        else:
            self.log.write("order_fail", why="no_fill", ticker=tk, cid=cid, status=st, asked=n, ask=px)

    @staticmethod
    def book_fee(filled, px, reported):
        """The fee booked on a fill: the larger of Kalshi's reported average_fee_paid x fills and the cent-rounded
        formula (Kalshi charges the cent-rounded figure per order; the reported average is to 4 dp and undercounts
        by up to a cent). Never books less than the formula."""
        formula = fee(filled, px)
        return round(max(formula, reported if reported is not None else 0.0), 4)

    def recover_unknown(self):
        """fxtake_live.Trader.recover_unknown, extended: read back every unknown order (not one still in flight) by
        client id from the pot's order list, min_ts back to the oldest unknown. A record no longer resting is booked
        from its fill_count / price / taker fees; a record still resting is cancelled again. An order the list never
        shows after UNKNOWN_MISSES successful reads, once the market is UNKNOWN_CLOSE_GRACE_S past its close, is
        written off: settled with no money, so the bot can go flat (it stays halted)."""
        with self.lock:
            unk = [(tk, v) for tk, v in self.held.items() if v.get("unknown") and not v.get("inflight")]
        if not unk:
            return
        import pintake
        now = self.now()
        oldest = min([v.get("t_sent") or time.time() for _, v in unk])
        min_ts = int(min(oldest - 60, time.time() - 3600))
        try:
            st, r = self.send("GET", "/portfolio/orders", None, {"subaccount": self.sub, "min_ts": min_ts, "limit": 200})
        except Exception as e:
            st, r = -1, repr(e)[:200]
        ok = st == 200 and isinstance(r, dict)
        rows = {x.get("client_order_id"): x for x in r.get("orders") or []} if ok else {}
        for tk, v in unk:
            x = rows.get(v["cid"])
            if x is None:
                if not ok:
                    continue
                with self.lock:
                    v["misses"] = v.get("misses", 0) + 1
                    due = v["misses"] >= UNKNOWN_MISSES and now >= v["close_s"] + UNKNOWN_CLOSE_GRACE_S
                    if due:
                        v.update(qty=0.0, cost=0.0, fee=0.0, settled=True, result=None, money=0.0, src="unknown_written_off", inflight=False)
                        v.pop("unknown", None)
                        self.n_written_off += 1
                if due:
                    self.log.write("recovered_none", ticker=tk, cid=v["cid"], misses=v["misses"],
                                   why="never in the order list after %d reads; market closed" % v["misses"])
                    self.log.write("settle_none", ticker=tk, result=None, cid=v["cid"], why="unknown_written_off")
                continue
            body = v.get("body") or order_body(tk, v["side"], v["px"], v.get("asked") or 1, self.sub, v["cid"], v.get("pool") or 0)
            out = pintake.normalise(200, x, body)
            if out["status"] == "resting":
                oid = x.get("order_id") or v.get("order_id")
                if oid:
                    try:
                        st2, r2 = self.send("DELETE", "/portfolio/events/orders/%s" % oid, None,
                                            {"subaccount": self.sub, "exchange_index": v.get("pool")})
                    except Exception as e:
                        st2, r2 = -1, repr(e)[:300]
                    self.log.write("cancel_retry", ticker=tk, cid=v["cid"], order_id=oid, status=st2, resp=str(r2)[:200])
                continue
            filled = round(float(out["filled"] or 0), 2)
            px = out["exec_price"] if out["exec_price"] is not None else v["px"]
            ff = self.book_fee(filled, px, out["fee_total"])
            with self.lock:
                v.update(qty=filled, px=px, cost=round(filled * px, 4), fee=ff, order_id=x.get("order_id") or v.get("order_id"), inflight=False)
                v.pop("unknown", None)
                if filled > 0:
                    self.n_fills += 1
            self.log.write("recovered", ticker=tk, cid=v["cid"], filled=filled, price=px, fee=ff,
                           fee_reported=None if out["fee_total"] is None else round(out["fee_total"], 4), record=str(x)[:300])

    # --- cash ---
    def update_cash(self, cash):
        """A fresh read of the pot ({pool: dollars}, None = unreadable in every pool). Logged when it changes."""
        with self.lock:
            was = None if self.pool_cash is None else dict(self.pool_cash)
            if cash is None:
                self.log.write("cash_unreadable", was=was)
                return
            self.cash_dirty = False
            if cash != self.pool_cash:
                self.log.write("cash", cash=dict(cash), was=was)
            self.pool_cash = dict(cash)

    def flat(self):
        """No live position open (settled or none); unknown and in-flight orders count as open."""
        with self.lock:
            return not any(v.get("live") and not v["settled"] for v in self.held.values())

    def open_positions(self):
        with self.lock:
            return sum(1 for v in self.held.values() if not v["settled"])

    # --- restart: the books from the bot's own log ---
    def restore(self, path):
        """Replay the live log at start (positions_from_log): fills and recovered orders with no later settle are held
        again (polled for Kalshi's result), orders sent without a booked answer are unknown again (read back), every
        ordered market is marked bought, and today's settled money seeds the day stop. Returns the summary logged."""
        info = positions_from_log(path)
        now = self.now()
        today = et_day(now)
        tickers = []
        with self.lock:
            for s in info["positions"]:
                tk = s["ticker"]
                self.held[tk] = {"side": s["side"], "qty": float(s["qty"]), "px": float(s["px"]), "cost": float(s["cost"]), "fee": float(s["fee"]),
                                 "close_s": float(s["close_s"]), "settled": False, "result": None, "money": None, "src": None, "cid": s.get("cid"),
                                 "sub": self.sub, "pool": s.get("pool"), "live": True, "order_id": s.get("order_id"), "restored": True}
                self.bought.add(tk)
                tickers.append(tk)
            for s in info["unknown"]:
                tk = s["ticker"]
                self.held[tk] = {"side": s["side"], "qty": 0.0, "px": float(s["px"]), "cost": 0.0, "fee": 0.0, "close_s": float(s["close_s"]),
                                 "settled": False, "result": None, "money": None, "src": None, "cid": s["cid"], "sub": self.sub, "pool": s.get("pool"),
                                 "live": True, "unknown": True, "inflight": False, "body": s.get("body"), "t_sent": s.get("t_sent") or now,
                                 "misses": 0, "asked": s.get("n"), "restored": True}
                self.bought.add(tk)
                tickers.append(tk)
            for tk in info["ordered"]:
                self.bought.add(tk)
            day_money = round(sum(m for t, m in info["settles"].values() if et_day(t) == today), 4)
            self.day, self.day_money = today, day_money
        summary = {"positions": len(info["positions"]), "unknown": len(info["unknown"]), "ordered": len(info["ordered"]),
                   "day": today, "day_money": day_money, "tickers": tickers}
        self.log.write("restored", **summary)
        if day_money <= DAY_STOP + 1e-9 and self.halt_day != today:
            self.halt_day = today
            self.log.write("day_stop", day=today, day_money=day_money, day_stop=DAY_STOP, restored=True)
        return summary

    # --- settlement (paper: the 60 prints and the lifecycle; live: Kalshi's REST result) ---
    def calc_result(self, tk):
        """(result, average, prints held) from the 60 one-second prints before the close; result None unless all
        60 are held and the strike is known. Rounding as scan.py: round(avg, rd) >= strike -> yes."""
        m = self.markets.get(tk)
        if m is None:
            return None, None, 0
        C = int(round(m["close_s"]))
        pr = self.prints.get(m["index"], {})
        xs = [pr.get(s) for s in range(C - 60, C)]
        have = [x for x in xs if x is not None]
        if not have:
            return None, None, 0
        avg = sum(have) / len(have)
        if len(have) < 60 or m["strike"] is None:
            return None, round(avg, 8), len(have)
        rd = m["rd"]
        r = round(avg, rd) if rd is not None else avg
        return ("yes" if r >= m["strike"] else "no"), round(avg, 8), len(have)

    def _book_settle(self, tk, result, calc, life, avg, n, src):
        v = self.held[tk]
        m = self.markets.get(tk, {})
        won = v["side"] == result
        pnl = (v["qty"] * (1 - v["px"]) - v["fee"]) if won else (-v["qty"] * v["px"] - v["fee"])
        pnl = round(pnl, 4)
        v.update(settled=True, result=result, pnl=pnl, src=src, won=won)
        self.run_pnl = round(self.run_pnl + pnl, 4)
        self.n_settled += 1
        self.n_lost += 0 if won else 1
        self.log.write("paper_settle", ticker=tk, side=v["side"], qty=v["qty"], price=v["px"], cost=v["cost"], fee=v["fee"],
                       result=result, result_calc=calc, result_lifecycle=life, agree=(None if calc is None or life is None else calc == life),
                       avg60=avg, n_prints=n, strike=m.get("strike"), round_digits=m.get("rd"), won=won, pnl=pnl,
                       run_pnl=self.run_pnl, src=src, settled=self.n_settled, lost=self.n_lost)

    def settle_live(self, tk, result, now=None):
        """fxtake_live.Trader.settle: book a live position from Kalshi's market result. money = payout - cost - fees."""
        with self.lock:
            v = self.held.get(tk)
            if v is None or v["settled"] or v.get("unknown") or not v.get("live"):
                return
            now = self.now() if now is None else now
            v["settled"] = True
            if v["qty"] <= 0:                                     # an order that never filled (read back as such)
                v.update(result=result, money=0.0, src="rest")
                self.log.write("settle_none", ticker=tk, result=result, cid=v.get("cid"))
                return
            won = v["side"] == result
            payout = float(v["qty"]) if won else 0.0
            money = round(payout - v["cost"] - v["fee"], 4)
            calc, avg, n = self.calc_result(tk)
            v.update(result=result, money=money, src="rest", won=won)
            self.run_pnl = round(self.run_pnl + money, 4)
            self.n_settled += 1
            self.n_lost += 0 if won else 1
            d = et_day(now)
            if d != self.day:
                self.day, self.day_money = d, 0.0
            self.day_money = round(self.day_money + money, 4)
            pool = v.get("pool")
            if self.pool_cash is not None and self.pool_cash.get(pool) is not None:
                self.pool_cash[pool] = round(self.pool_cash[pool] + payout, 4)          # until the next read
            self.cash_dirty = True
            if self.line_money is not None:
                self.line_money = round(self.line_money + money, 4)
            m = self.markets.get(tk, {})
            self.log.write("settle", ticker=tk, side=v["side"], qty=v["qty"], price=v["px"], cost=v["cost"], fee=v["fee"], result=result,
                           payout=payout, money=money, won=won, run_money=self.run_pnl, day_money=self.day_money, line_money=self.line_money,
                           cash=None if self.pool_cash is None else self.pool_cash.get(pool), result_calc=calc,
                           result_lifecycle=v.get("lifecycle_result"), avg60=avg, n_prints=n, strike=m.get("strike"),
                           settled=self.n_settled, lost=self.n_lost, cid=v.get("cid"), src="rest", restored=bool(v.get("restored")))
            if self.day_money <= DAY_STOP + 1e-9 and self.halt_day != d:
                self.halt_day = d
                self.log.write("day_stop", day=d, day_money=self.day_money, day_stop=DAY_STOP)
            if self.line_money is None:
                return
            if self.stop_line is not None and self.line_money <= self.stop_line + 1e-9 and not self.stopped:
                self.stand_down("stop line: $%.2f settled since the first live record is at or under $%.2f"
                                % (self.line_money, self.stop_line))

    def stand_down(self, why):
        """fxtake_live.Trader.stand_down: refuse every new order from now (the run exits once flat) and write the stop
        file, so neither a restart nor boot_all brings the bot back until a person deletes it."""
        self.stopped = True
        self.log.write("stop_line", line_money=self.line_money, stop_line=self.stop_line, path=STOP_FILE)
        try:
            with open(STOP_FILE, "w", encoding="utf-8") as f:
                f.write("%s -- written by jumpband_live %s. Delete this file to resume.\n"
                        % (why, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
        except Exception as e:
            self.log.write("stop_file_write_failed", err=str(e)[:200])

    def on_lifecycle(self, msg, now):
        tk = msg.get("market_ticker")
        if tk not in self.markets:
            return
        et = msg.get("event_type")
        if et == "metadata_updated" and msg.get("floor_strike") is not None:
            cs = msg.get("custom_strike") or {}
            rd = cs.get("round_digits")
            m = self.markets[tk]
            self.add_market(tk, m["series"], m["close_s"], float(msg["floor_strike"]),
                            int(rd) if rd is not None else ROUND_DIGITS.get(m["series"]), "lifecycle")
        elif et == "determined" and msg.get("result") in ("yes", "no"):
            life = msg["result"]
            v = self.held.get(tk)
            if v is None:
                return
            if v.get("live"):                                     # live: logged for the audit; Kalshi's REST result books
                v["lifecycle_result"] = life
                self.log.write("lifecycle_result", ticker=tk, result=life, booked=v["settled"], result_booked=v.get("result"),
                               agree=(v.get("result") == life) if v["settled"] else None)
                return
            calc, avg, n = self.calc_result(tk)
            if not v["settled"]:
                self._book_settle(tk, life, calc, life, avg, n, "lifecycle")
                return
            # already booked from the prints: confirm, and correct if Kalshi disagrees
            agree = v["result"] == life
            self.log.write("lifecycle_late", ticker=tk, result_lifecycle=life, result_booked=v["result"], agree=agree)
            if not agree:
                old = v["pnl"]
                won = v["side"] == life
                pnl = round((v["qty"] * (1 - v["px"]) - v["fee"]) if won else (-v["qty"] * v["px"] - v["fee"]), 4)
                self.run_pnl = round(self.run_pnl + pnl - old, 4)
                self.n_lost += (0 if won else 1) - (0 if v.get("won") else 1)
                v.update(result=life, pnl=pnl, src="lifecycle_corrected", won=won)
                self.log.write("settle_corrected", ticker=tk, result=life, pnl=pnl, old_pnl=old, run_pnl=self.run_pnl)

    def settle_due(self, now):
        """Paper: book from the prints when no lifecycle message came within SETTLE_WAIT of the close. Live positions
        wait for Kalshi's REST result (settle_live). Per-market summary once the close has passed; forget old markets."""
        with self.lock:                                           # the order thread may be inserting a position
            held_now = list(self.held.items())
        for tk, v in held_now:
            if v["settled"] or now < v["close_s"] + SETTLE_WAIT:
                continue
            if v.get("live"):
                if now >= v["close_s"] + FORGET_S and not v.get("pending_logged"):
                    v["pending_logged"] = True
                    self.log.write("settle_pending", ticker=tk, live=True, unknown=bool(v.get("unknown")), cid=v.get("cid"))
                continue
            calc, avg, n = self.calc_result(tk)
            if calc is not None:
                self._book_settle(tk, calc, calc, None, avg, n, "calc")
            elif now >= v["close_s"] + FORGET_S:
                v.update(settled=True, src="unsettled")
                self.log.write("unsettled", ticker=tk, n_prints=n, strike=self.markets.get(tk, {}).get("strike"))
            elif not v.get("pending_logged"):
                v["pending_logged"] = True
                self.log.write("settle_pending", ticker=tk, n_prints=n, strike=self.markets.get(tk, {}).get("strike"))
        for tk, m in list(self.markets.items()):
            if not m["done"] and now >= m["close_s"] + 2:
                m["done"] = True
                b = self.books.get(tk)
                self.log.write("market_done", ticker=tk, triggers=m["triggers"], inband=m["inband"], bought=tk in self.bought,
                               strike=m["strike"], book_synced=bool(b and b.synced))
            if m["close_s"] < now - FORGET_S and (tk not in self.held or self.held[tk]["settled"]):
                with self.lock:
                    self.markets.pop(tk, None); self.books.pop(tk, None); self.bought.discard(tk); self.held.pop(tk, None)
        with self.lock:                                           # restored positions have no market row: forgotten once settled
            for tk, v in list(self.held.items()):
                if tk not in self.markets and v["settled"] and v["close_s"] < now - FORGET_S:
                    self.held.pop(tk, None); self.bought.discard(tk)

    # --- stop and health ---
    def check_stop_file(self):
        if not self.stopped and os.path.exists(STOP_FILE):
            self.stopped = True
            self.log.write("stop_file", path=STOP_FILE)
        return self.stopped

    def health(self, **extra):
        now = self.now()
        el = max(now - self.prints_since, 1e-9)
        pps = {iid: round(n / el, 3) for iid, n in sorted(self.n_prints.items())}
        self.n_prints = collections.Counter(); self.prints_since = now
        sds = {iid: (None if s.sd() is None else round(s.sd(), 6)) for iid, s in sorted(self.sig.items())}
        with self.lock:
            money = ({"orders": self.n_orders, "fills": self.n_fills, "money": self.run_pnl, "day_money": round(self.day_money, 4),
                      "line_money": self.line_money, "cash": None if self.pool_cash is None else dict(self.pool_cash),
                      "subaccount": self.sub, "dry": self.dry,
                      "halted": self.halted, "halt_day": self.halt_day, "max_contracts": self.max_contracts, "max_cost": self.max_cost,
                      "stop_line": self.stop_line, "unknown": sum(1 for v in self.held.values() if v.get("unknown")),
                      "inflight": sum(1 for v in self.held.values() if v.get("inflight")), "written_off": self.n_written_off}
                     if self.live else {"paper_buys": self.n_buys, "paper_pnl": self.run_pnl})
            open_pos = sum(1 for v in self.held.values() if not v["settled"])
        self.log.write("health", live=self.live, markets=len(self.markets), books_synced=sum(1 for b in self.books.values() if b.synced),
                       prints_per_s=pps, sigma=sds, triggers=self.n_triggers,
                       open_positions=open_pos, settled=self.n_settled,
                       lost=self.n_lost, stopped=self.stopped, rss_mb=rss_mb(), log_failed=self.log.failed, log_failures=self.log.n_failed,
                       **money, **extra)


def positions_from_log(path):
    """Replay the bot's own live log for a restart. Per client id: order_sent -> an order in flight; fill or recovered
    (filled > 0) -> a known position; order_fail rejected / no_fill, recovered with 0 filled, recovered_none, settle or
    settle_none for its ticker -> done. Returns {"positions": [known positions still open], "unknown": [orders sent and
    never booked], "ordered": {every ticker with an order}, "settles": {ticker: (t, money) of the LAST settle},
    "closes": {ticker: close_s from its market record}}. A missing or unreadable log gives empty lists."""
    out = {"positions": [], "unknown": [], "ordered": set(), "settles": {}, "closes": {}}
    state = {}                      # cid -> {"status": sent | filled | gone, ...}
    by_tk = {}                      # ticker -> [cid]
    try:
        f = open(path, encoding="utf-8")
    except (FileNotFoundError, OSError):
        return out
    with f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            k = r.get("kind")
            tk = r.get("ticker")
            try:
                if k == "market" and tk:
                    out["closes"][tk] = float(r["close_s"])
                elif k == "order_sent" and r.get("cid"):
                    b = r.get("body") or {}
                    px = r.get("ask")
                    if px is None and b:
                        px = float(b["price"]) if b.get("side") == "bid" else round(1 - float(b["price"]), 4)
                    state[r["cid"]] = {"status": "sent", "cid": r["cid"], "ticker": tk, "side": r.get("side"), "px": px, "n": r.get("qty"),
                                       "pool": r.get("pool"), "body": b or None, "close_s": r.get("close_s"), "t_sent": parse_iso(r["t"]), "t": r["t"]}
                    by_tk.setdefault(tk, []).append(r["cid"])
                    out["ordered"].add(tk)
                elif k == "fill" and r.get("cid"):
                    s = state.setdefault(r["cid"], {"cid": r["cid"], "ticker": tk, "t": r["t"]})
                    s.update(status="filled", ticker=tk, side=r["side"], qty=float(r["qty"]), px=float(r["price"]), cost=float(r["cost"]),
                             fee=float(r["fee"]), pool=r.get("pool", s.get("pool")), close_s=r.get("close_s", s.get("close_s")),
                             order_id=r.get("order_id"))
                    if r["cid"] not in by_tk.setdefault(tk, []):
                        by_tk[tk].append(r["cid"])
                    out["ordered"].add(tk)
                elif k == "recovered" and r.get("cid") in state:
                    s = state[r["cid"]]
                    filled = float(r.get("filled") or 0)
                    if filled > 0:
                        px = float(r["price"]) if r.get("price") is not None else float(s.get("px") or 0)
                        s.update(status="filled", qty=filled, px=px, cost=round(filled * px, 4), fee=float(r.get("fee") or 0))
                    else:
                        s["status"] = "gone"
                elif k == "order_fail" and r.get("cid") in state and r.get("why") in ("rejected", "no_fill"):
                    state[r["cid"]]["status"] = "gone"
                elif k == "recovered_none" and r.get("cid") in state:
                    state[r["cid"]]["status"] = "gone"
                elif k in ("settle", "settle_none") and tk:
                    for cid in by_tk.get(tk, []):
                        state[cid]["status"] = "gone"
                    if k == "settle":
                        out["settles"][tk] = (parse_iso(r["t"]), float(r["money"]))
            except Exception:
                continue
    for s in state.values():
        if s.get("status") not in ("sent", "filled"):
            continue
        if s.get("close_s") is None:
            s["close_s"] = out["closes"].get(s["ticker"], (s.get("t_sent") or parse_iso(s["t"])) + 60.0)
        if s["status"] == "filled":
            out["positions"].append(s)
        else:
            out["unknown"].append(s)
    return out


# ---------------------------------------------------------------------------------------------------- frames
def handle_frame(tr, obj, now, ws_state, log):
    """One parsed websocket frame -> the trader. The live feed and the self-test both come through here."""
    t = obj.get("type")
    msg = obj.get("msg") or {}
    if t == "cfbenchmarks_value":
        try:
            data = msg.get("data")
            data = json.loads(data) if isinstance(data, str) else (data or {})
            tm = int(data["time"])
            if tm % 1000:
                return
            tr.on_print(msg["index_id"], tm // 1000, float(data["value"]), now, obj.get("sending_ts_ms"))
        except (KeyError, TypeError, ValueError) as e:
            log.write("bad_print", err=repr(e)[:120])
    elif t == "orderbook_delta":
        sid, seq = obj.get("sid"), obj.get("seq")
        exp = ws_state["seq"].get(sid)
        if exp is not None and seq is not None and seq != exp + 1:
            log.write("seq_gap", sid=sid, expected=exp + 1, got=seq)
            tr.unsync()
            ws_state["resync"] = True
        if seq is not None:
            ws_state["seq"][sid] = seq
        tr.on_delta(msg.get("market_ticker"), msg, now)
    elif t == "orderbook_snapshot":
        if obj.get("seq") is not None:
            ws_state["seq"][obj.get("sid")] = obj.get("seq")
        tr.on_snapshot(msg.get("market_ticker"), msg, now)
    elif t == "market_lifecycle_v2":
        tr.on_lifecycle(msg, now)
    elif t == "subscribed":
        ws_state["sids"][msg.get("sid")] = msg.get("channel")
        log.write("ws_subscribed", id=obj.get("id"), sid=msg.get("sid"), channel=msg.get("channel"))
    elif t == "error":
        log.write("ws_error", msg=str(obj)[:300])
        if msg.get("code") == 25:                                 # subscription buffer overflow: resubscribe everything
            tr.unsync()
            ws_state["resync"] = True


def new_ws_state():
    return {"ws": None, "next_id": 1, "sids": {}, "seq": {}, "subscribed": set(), "resync": False}


# ---------------------------------------------------------------------------------------------------- live plumbing
def market_from_rest(mk, series, doge_prev=None):
    """(ticker, close_s, strike, round_digits, src) from one /markets row. DOGE's floor_strike is truncated to 6 dp,
    so the previous market's expiration_value is the exact strike (bettor_paper.py)."""
    tk = mk["ticker"]
    close_s = parse_iso(mk["close_time"])
    cs = mk.get("custom_strike") or {}
    rd = cs.get("round_digits")
    rd = int(rd) if rd not in (None, "") else ROUND_DIGITS.get(series)
    strike, src = None, None
    if cs.get("floor_strike") not in (None, ""):
        strike, src = float(cs["floor_strike"]), "custom_strike"
    elif mk.get("floor_strike") is not None:
        strike, src = float(mk["floor_strike"]), "floor_strike"
    if series == "KXDOGE15M":
        for p in doge_prev or []:
            try:
                if parse_iso(p["close_time"]) == close_s - 900 and p.get("expiration_value"):
                    strike, src = float(str(p["expiration_value"]).replace(",", "")), "prev_expiration_value"
            except Exception:
                pass
    return tk, close_s, strike, rd, src


def pool_from_rest(mk):
    """fxtake_live.run_live.discover: the market's pool is its /markets row's exchange_index; None when not given."""
    pool = mk.get("exchange_index")
    try:
        return None if pool is None else int(pool)
    except (TypeError, ValueError):
        return None


async def watch_stop(tr, end, log, period=0.5, grace=None):
    """Ends the run when the stop file appears: paper at once; live once flat (no open live position). At `end` the
    run stands down ("ending": no new orders) and, live, waits up to `grace` s (END_GRACE_S) for the open positions
    to settle, then returns whatever is still open ("ending_open"; a restart re-adopts it from the log). The task
    returns, run_live cancels the rest."""
    if grace is None:
        grace = END_GRACE_S if tr.live else 0.0
    said = ending = False
    while True:
        now = time.time()
        if now >= end and not ending:
            ending = True
            tr.stopped = True
            log.write("ending", open_positions=tr.open_positions(), grace_s=grace)
        if tr.check_stop_file() or ending:
            if not said and not ending:
                said = True
                log.write("stopping", open_positions=tr.open_positions())
            if not tr.live or tr.flat():
                if tr.live:
                    log.write("stopped_flat")
                return
            if now >= end + grace:
                with tr.lock:
                    open_tk = [tk for tk, v in tr.held.items() if not v["settled"]]
                log.write("ending_open", open_positions=len(open_tk), tickers=open_tk, note="re-adopted from the log at the next start")
                return
        await asyncio.sleep(period)


async def run_live(tr, minutes, log, series, ws_mod=None, auth_mod=None, grace=None):
    """The run: discovery, the websocket feed, the stop watcher, settlement and health as tasks on one loop. Live
    sends run on the bot's own order thread (tr.dispatch). `ws_mod` / `auth_mod` replace the websockets and kauth
    modules (the self-test's fakes); `grace` overrides END_GRACE_S."""
    import concurrent.futures
    import importlib
    websockets = ws_mod if ws_mod is not None else importlib.import_module("websockets")
    kauth = auth_mod if auth_mod is not None else importlib.import_module("kauth")
    loop = asyncio.get_running_loop()
    end = time.time() + minutes * 60
    if grace is None:
        grace = END_GRACE_S if tr.live else 0.0
    hard_end = end + grace                                        # the watcher ends the run by then; the other tasks serve it
    tasks_end = hard_end + 60.0                                   # and run a little longer, so the WATCHER is the task that ends the run
    ws_state = new_ws_state()
    tr.ws_state = ws_state                                        # read by health and the self-test harness
    index_ids = sorted({INDEX[s] for s in series})
    order_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="jb-order")   # one sender: the
    order_tasks = set()                                                                                 # throttle is its own

    async def _order(fn, *args):
        try:
            await loop.run_in_executor(order_pool, fn, *args)
        except Exception as e:
            log.write("place_error", err=repr(e)[:300])

    def dispatch(fn, *args):
        t = loop.create_task(_order(fn, *args))
        order_tasks.add(t)
        t.add_done_callback(order_tasks.discard)

    if tr.live:
        tr.dispatch = dispatch

    def signed_get(path, params):
        st, d = kauth.get(path, params)
        if st == 429:
            time.sleep(3)
            st, d = kauth.get(path, params)
        return st, d

    async def discover():
        """Signed GET of the open markets per series, once a minute; markets closing within WATCH_AHEAD are watched,
        each with the pool Kalshi gives on its row. No new markets once the run is ending (it serves the open
        positions until hard_end; a task that returned early would end the run, asyncio.wait FIRST_COMPLETED)."""
        while time.time() < tasks_end:
            if time.time() >= end:
                await asyncio.sleep(5)
                continue
            doge_prev = []
            if "KXDOGE15M" in series:
                try:
                    st, d = await loop.run_in_executor(None, signed_get, "/markets", {"series_ticker": "KXDOGE15M", "status": "settled", "limit": 5})
                    doge_prev = (d.get("markets") or []) if st == 200 and isinstance(d, dict) else []
                except Exception as e:
                    log.write("discover_error", series="KXDOGE15M", err=repr(e)[:200])
            for s in series:
                try:
                    st, d = await loop.run_in_executor(None, signed_get, "/markets", {"series_ticker": s, "status": "open", "limit": 5})
                    if st != 200 or not isinstance(d, dict):
                        log.write("discover_error", series=s, status=st, err=str(d)[:120])
                        continue
                    for mk in d.get("markets") or []:
                        try:
                            tk, c, strike, rd, src = market_from_rest(mk, s, doge_prev)
                        except Exception as e:
                            log.write("bad_market", ticker=mk.get("ticker"), err=repr(e)[:160])
                            continue
                        if 0 < c - time.time() < WATCH_AHEAD:
                            tr.add_market(tk, s, c, strike, rd, src, pool_from_rest(mk))
                except Exception as e:
                    log.write("discover_error", series=s, err=repr(e)[:200])
                await asyncio.sleep(1.0)
            await asyncio.sleep(55)

    async def subscribe_new(ws):
        want = [tk for tk in list(tr.markets) if tk not in ws_state["subscribed"]]
        if not want:
            return
        i = ws_state["next_id"]; ws_state["next_id"] += 1
        await ws.send(json.dumps({"id": i, "cmd": "subscribe", "params": {"channels": ["orderbook_delta"], "market_tickers": want}}))
        ws_state["subscribed"].update(want)
        log.write("ws_subscribe", id=i, markets=want)

    async def resync(ws):
        """After a sequence gap or an overflow: drop every book subscription and take fresh snapshots."""
        sids = [sid for sid, ch in ws_state["sids"].items() if ch == "orderbook_delta"]
        if sids:
            i = ws_state["next_id"]; ws_state["next_id"] += 1
            await ws.send(json.dumps({"id": i, "cmd": "unsubscribe", "params": {"sids": sids}}))
            for sid in sids:
                ws_state["sids"].pop(sid, None); ws_state["seq"].pop(sid, None)
        ws_state["subscribed"] = set()
        ws_state["resync"] = False
        log.write("ws_resync", dropped_sids=sids)
        await subscribe_new(ws)

    async def feed():
        while time.time() < tasks_end:
            try:
                hdrs = kauth.headers("GET", WS_PATH)
                async with websockets.connect(WS_URL, additional_headers=hdrs, ping_interval=20, ping_timeout=20, max_size=2 ** 24) as ws:
                    ws_state["ws"] = ws
                    ws_state["subscribed"] = set(); ws_state["sids"] = {}; ws_state["seq"] = {}; ws_state["resync"] = False
                    tr.unsync()
                    log.write("ws_up")
                    i = ws_state["next_id"]; ws_state["next_id"] += 1
                    await ws.send(json.dumps({"id": i, "cmd": "subscribe", "params": {"channels": ["cfbenchmarks_value"], "index_ids": index_ids}}))
                    i = ws_state["next_id"]; ws_state["next_id"] += 1
                    await ws.send(json.dumps({"id": i, "cmd": "subscribe", "params": {"channels": ["market_lifecycle_v2"]}}))
                    await subscribe_new(ws)
                    last_sub = time.time()
                    while time.time() < tasks_end:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        except asyncio.TimeoutError:
                            raw = None
                        if ws_state["resync"]:
                            await resync(ws); last_sub = time.time()
                        elif time.time() - last_sub > 5:
                            await subscribe_new(ws); last_sub = time.time()
                        if raw is None:
                            continue
                        try:
                            obj = json.loads(raw)
                        except ValueError:
                            continue
                        if not isinstance(obj, dict):
                            log.write("frame_error", err="frame is not an object", raw=str(raw)[:200])
                            continue
                        try:
                            handle_frame(tr, obj, time.time(), ws_state, log)
                        except Exception as e:                   # one bad frame is logged, never a reconnect
                            log.write("frame_error", err=repr(e)[:200], raw=str(raw)[:200])
            except Exception as e:
                ws_state["ws"] = None
                log.write("ws_down", err=repr(e)[:200])
                tr.unsync()
                await asyncio.sleep(2)
        ws_state["ws"] = None

    async def settle():
        """Paper booking every SETTLE_TICK_S. Live: the pot's cash (every CASH_EVERY_S, sooner when asked), Kalshi's result
        for each open position from SETTLE_AFTER_S after its close (fxtake_live; a position still open FORGET_S after its
        close is asked every LATE_POLL_S instead), and the read-back of unknown orders."""
        last_cash = time.time()                                   # main() read the cash just before the start
        last_poll = 0.0
        while time.time() < tasks_end:
            now = time.time()
            tr.settle_due(now)
            if tr.live:
                settled_now = False
                if now - last_poll >= SETTLE_POLL_S:
                    last_poll = now
                    with tr.lock:
                        due = [(tk, v) for tk, v in tr.held.items()
                               if v.get("live") and not v["settled"] and not v.get("unknown") and now >= v["close_s"] + SETTLE_AFTER_S]
                    for tk, v in due:
                        if now >= v["close_s"] + FORGET_S and now - v.get("last_poll", 0.0) < LATE_POLL_S:
                            continue
                        v["last_poll"] = now
                        try:
                            st, d = await loop.run_in_executor(None, tr.send, "GET", "/markets/%s" % tk, None, None)
                            r = (d.get("market") or {}).get("result") if st == 200 and isinstance(d, dict) else None
                            if r in ("yes", "no"):
                                tr.settle_live(tk, r)
                                settled_now = True
                            elif st == 429:
                                await asyncio.sleep(3)
                        except Exception as e:
                            log.write("settle_error", ticker=tk, err=repr(e)[:200])
                    if not tr.dry:
                        try:
                            await loop.run_in_executor(None, tr.recover_unknown)
                        except Exception as e:
                            log.write("recover_error", err=repr(e)[:200])
                # the pot's cash: right after a settle (and again a minute later, the payout can land after the result),
                # within a minute of a no_cash skip, and every CASH_EVERY_S regardless
                if settled_now or (tr.cash_dirty and now - last_cash >= CASH_RETRY_S) or now - last_cash >= CASH_EVERY_S:
                    last_cash = now
                    try:
                        cash = await loop.run_in_executor(None, read_pool_cash, tr.send, tr.sub)
                        tr.update_cash(cash)
                    except Exception as e:
                        log.write("cash_error", err=repr(e)[:200])
                    if settled_now:
                        tr.cash_dirty = True
            await asyncio.sleep(SETTLE_TICK_S)

    async def health():
        while time.time() < tasks_end:
            await asyncio.sleep(300)
            tr.health(ws_up=ws_state["ws"] is not None, subscribed=len(ws_state["subscribed"]))

    async def decide():
        await watch_stop(tr, end, log, grace=grace)

    tasks = [asyncio.create_task(c()) for c in (discover, feed, decide, settle, health)]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        for t in done:
            if not t.cancelled() and t.exception():
                log.write("task_error", err=repr(t.exception())[:300])
        if order_tasks:                                           # an order in flight finishes its booking before the exit
            await asyncio.wait(list(order_tasks), timeout=45)
    finally:
        tr.dispatch = None
        order_pool.shutdown(wait=False)


# ---------------------------------------------------------------------------------------------------- arguments
def check_args(a):
    """Every refusal that needs no network, before anything connects. Returns {"series", "max_contracts", "log",
    "stop_file"} for the mode."""
    series = [s.strip() for s in a.series.split(",") if s.strip()]
    bad = [s for s in series if s not in INDEX]
    if bad:
        raise SystemExit("unknown series %s; known: %s" % (bad, sorted(INDEX)))
    if a.fast_k is not None:
        if a.fast_k < 4.0:
            raise SystemExit("--fast-k must be at least 4 (the replay backs the fast coins only at k >= 4)")
        series = series + [s for s in FAST if s not in series]
    elif any(s in FAST for s in series):
        raise SystemExit("fast coins (%s) need --fast-k 4" % ", ".join(s for s in series if s in FAST))
    if a.dry_run and not a.live:
        raise SystemExit("--dry-run goes with --live (paper mode is the default and needs neither)")
    if a.live:
        if a.subaccount is None:
            raise SystemExit("--live requires --subaccount N (1..63): the pot the orders go to; refusing before anything connects")
        if not (1 <= a.subaccount <= 63):
            raise SystemExit("--subaccount must be 1..63; the primary account (0) is refused")
        mc = LIVE_DEFAULT_CONTRACTS if a.max_contracts is None else a.max_contracts
        if mc != int(mc) or not (1 <= mc <= LIVE_MAX_CONTRACTS):
            raise SystemExit("--max-contracts %g refused: in live mode it must be a whole number 1..%d (LIVE_MAX_CONTRACTS, a code constant)"
                             % (mc, LIVE_MAX_CONTRACTS))
        mc = int(mc)
        if not (a.max_cost > 0):
            raise SystemExit("--max-cost must be positive dollars (default %.2f)" % MAX_COST)
        if a.stop_line is not None and a.stop_line >= 0:
            raise SystemExit("--stop-line must be negative dollars (default %.2f)" % STOP_LINE)
        if not getattr(a, "rule_override", False):                # live pins the approved rule
            off = []
            if a.fast_k is not None:
                off.append("--fast-k %g" % a.fast_k)
            if abs(a.k - K) > 1e-9:
                off.append("--k %g" % a.k)
            if abs(a.lo - LO) > 1e-9 or abs(a.hi - HI) > 1e-9:
                off.append("--lo %g --hi %g" % (a.lo, a.hi))
            odd = [s for s in series if s not in SLOW]
            if odd:
                off.append("--series %s" % ",".join(odd))
            if off:
                raise SystemExit("live mode pins the approved rule (k %.1f, band %.2f-%.2f, the slow coins %s): %s refused; "
                                 "--rule-override runs another rule with real money" % (K, LO, HI, ",".join(SLOW), "; ".join(off)))
    else:
        if a.subaccount is not None:
            raise SystemExit("--subaccount goes with --live")
        mc = MAX_CONTRACTS if a.max_contracts is None else a.max_contracts
    if not (0.5 <= a.lo < a.hi <= 0.99) or a.k < 1.0 or mc <= 0:
        raise SystemExit("0.5 <= --lo < --hi <= 0.99, --k >= 1, --max-contracts > 0")
    if a.live and a.dry_run:
        log, stop = DRY_LOG, DRY_STOP_FILE
    elif a.live:
        log, stop = LIVE_LOG, LIVE_STOP_FILE
    else:
        log, stop = LOG, PAPER_STOP_FILE
    return {"series": series, "max_contracts": mc, "log": a.log or log, "stop_file": stop}


# ---------------------------------------------------------------------------------------------------- selftest
def selftest():
    """A fake world through the live code path (handle_frame -> Trader): prints, books, lifecycle, stop file, and for
    live mode a fake exchange (no network, no keys): the exact body, the rails, the money."""
    fails = []
    n = [0]

    def ck(cond, what):
        n[0] += 1
        print(("  ok   " if cond else "  FAIL ") + what)
        if not cond:
            fails.append(what)

    IID = "BNBUSD_RTI"
    PATTERN = (0.10, -0.05, 0.03, -0.08, 0.06, -0.06)      # one-second changes; max 0.1 is about 1.4 sd, so no stray trigger

    def print_frame(sec, v, iid=IID):
        return {"type": "cfbenchmarks_value", "sid": 2, "seq": sec, "sending_ts_ms": sec * 1000 + 30,
                "msg": {"index_id": iid, "received_at": sec * 1000 + 25,
                        "data": json.dumps({"type": "value", "time": sec * 1000, "id": iid, "value": "%.6f" % v})}}

    def snap_frame(tk, yes_bids, no_bids, seq=1, sid=4):
        return {"type": "orderbook_snapshot", "sid": sid, "seq": seq,
                "msg": {"market_ticker": tk, "yes_dollars_fp": [["%.4f" % p, "%.2f" % q] for p, q in yes_bids],
                        "no_dollars_fp": [["%.4f" % p, "%.2f" % q] for p, q in no_bids]}}

    def delta_frame(tk, side, px, dq, seq, sid=4):
        return {"type": "orderbook_delta", "sid": sid, "seq": seq,
                "msg": {"market_ticker": tk, "price_dollars": "%.4f" % px, "delta_fp": "%.2f" % dq, "side": side, "ts_ms": 0}}

    def live_sender(fill=None, status=201, fee_c="0.0100", balance="50.00"):
        """A fake exchange that records every call. A POST is answered like Kalshi's real create-order 201 (top-level
        fields, fill_count / remaining_count, average_fill_price in YES terms, average_fee_paid per contract)."""
        calls = []

        def send(method, path, body, query):
            calls.append((method, path, body, query))
            if method == "POST":
                if status == -1:
                    return -1, "timeout"
                if status != 201:
                    return status, '{"error":{"code":"insufficient_balance","message":"no"}}'
                cnt = float(body["count"])
                f_ = cnt if fill is None else float(fill)
                r = {"order_id": "oid-%d" % len(calls), "client_order_id": body["client_order_id"], "fill_count": "%.2f" % f_,
                     "remaining_count": "0.00", "ts_ms": 1}
                if f_ > 0:
                    r["average_fill_price"] = body["price"]
                    r["average_fee_paid"] = fee_c
                return 201, r
            if path == "/portfolio/balance":
                return 200, {"balance_dollars": balance}
            if path == "/portfolio/orders":
                return 200, {"orders": list(send.orders)}
            return 200, {}
        send.calls = calls
        send.orders = []
        send.posts = lambda: [c for c in calls if c[0] == "POST"]
        return send

    class World:
        """One market on the BNB index, prints warmed up to the second before `s_jump`."""

        def __init__(self, tau, close=1793156400, live=False, k=K, lo=LO, hi=HI, base=745.30, strike=745.00,
                     yes_bids=((0.80, 50.0),), no_bids=((0.15, 40.0), (0.10, 100.0)), series="KXBNB15M", fast_k=None, gap_at=None,
                     sub=None, sender=None, dry=False, max_contracts=None, max_cost=MAX_COST, cash=None, pool=2, stop_line=STOP_LINE,
                     log_cls=Logger):
            self.sent = []
            self.T = [0.0]
            self.log = log_cls(sink=self.sent, now=lambda: self.T[0])
            self.tr = Trader(self.log, live=live, now=lambda: self.T[0], k=k, lo=lo, hi=hi, fast_k=fast_k, max_contracts=max_contracts,
                             sub=sub, dry=dry, sender=sender, max_cost=max_cost, stop_line=stop_line)
            if cash is not None:
                self.tr.pool_cash = dict(cash)
            self.ws = new_ws_state()
            self.C = close
            self.iid = INDEX[series]
            self.tk = "%s-26OCT272300-00" % series
            self.tr.add_market(self.tk, series, self.C, strike, 2, "test", pool)
            self.s_jump = self.C - tau
            self.v = base
            self.i = 0
            self.last_sec = None
            sec = self.s_jump - 400
            while sec < self.s_jump:
                if gap_at is not None and gap_at[0] <= sec < gap_at[1]:
                    sec += 1
                    continue
                self.feed(sec)
                sec += 1
            self.frame(snap_frame(self.tk, yes_bids, no_bids))

        def step(self):
            d = PATTERN[self.i % len(PATTERN)]; self.i += 1
            return d

        def frame(self, obj, lag=0.1):
            if obj["type"] == "cfbenchmarks_value":
                try:
                    self.T[0] = json.loads(obj["msg"]["data"])["time"] / 1000.0 + lag
                except (ValueError, KeyError, TypeError):
                    pass
            handle_frame(self.tr, obj, self.T[0], self.ws, self.log)

        def feed(self, sec, v=None, lag=0.1):
            """The next pattern print (or the given value) at second sec."""
            if v is None:
                if self.last_sec is not None and sec == self.last_sec + 1:
                    self.v = self.v + self.step()
                else:
                    self.v = self.v + self.step()        # after a gap the change is never counted anyway
            else:
                self.v = v
            self.last_sec = sec
            self.frame(print_frame(sec, self.v, self.iid), lag)

        def sd(self):
            return self.tr.sig[self.iid].sd()

        def jump(self, mult, lag=0.1, sec=None):
            sec = self.s_jump if sec is None else sec
            sd = self.sd()
            self.feed(sec, self.v + mult * sd, lag)
            return sd

        def recs(self, kind):
            return [r for r in self.sent if r["kind"] == kind]

    # (a) a 2.5-sd jump at tau 30, favoured YES ask 0.85 x 40 -> one paper_buy of 40 at 0.85, fee 1.43
    w = World(30)
    sd0 = w.tr.sig[IID].sd()
    ck(sd0 is not None and w.tr.sig[IID].n == SIGW, "warm-up: 300 valid one-second changes, sd %.5f" % (sd0 or 0))
    ck(w.tr.n_triggers == 0 and not w.recs("paper_buy"), "the warm-up pattern (max 1.4 sd) fires nothing")
    w.jump(2.5)
    buys = w.recs("paper_buy")
    ck(len(buys) == 1, "(a) one paper_buy")
    b = buys[0] if buys else {}
    ck(b.get("side") == "yes" and b.get("tau") == 30 and b.get("ask") == 0.85 and b.get("ask_size") == 40.0 and b.get("qty") == 40.0,
       "(a) YES, tau 30, ask 0.85 x 40, qty 40: %s" % {k_: b.get(k_) for k_ in ("side", "tau", "ask", "ask_size", "qty")})
    # fee = 0.07 x 0.85 x 0.15 = 0.008925 a contract; x 40 = 0.357, rounded up to the cent per order = 0.36
    # (the brief's "0.0357 x 40 = 1.428 -> 1.43" is the same formula with the decimal point one place off)
    FEE40 = fee(40, 0.85)
    ck(abs(b.get("cost", 0) - 34.0) < 1e-9 and abs(b.get("fee", 0) - 0.36) < 1e-9 and FEE40 == 0.36,
       "(a) cost 34.00, fee 0.07 x 0.85 x 0.15 x 40 = 0.357 rounded up to 0.36")
    ck(abs(b.get("print_move_sd", 0) - 2.5) < 1e-6 and abs(b.get("sigma", 0) - sd0) < 1e-12, "(a) the record carries dz 2.5 and the sd it was judged against")
    trig = w.recs("trigger")
    ck(len(trig) == 1 and trig[0]["outcome"] == "buy", "(a) exactly one trigger record, outcome buy")
    ck(b.get("pside") == "yes" and b.get("proj") is not None and b.get("strike") == 745.0, "(a) projected settlement side logged (yes, index above the strike)")
    # the NO side: price down -> buy NO at the NO ask (1 - best YES bid)
    wn = World(30, yes_bids=((0.15, 30.0),), no_bids=((0.60, 20.0),))
    wn.jump(-2.5)
    bn = wn.recs("paper_buy")
    ck(len(bn) == 1 and bn[0]["side"] == "no" and bn[0]["ask"] == 0.85 and bn[0]["qty"] == 30.0, "a 2.5-sd DROP buys NO at the NO ask 0.85 x 30")
    # cap: 250 offered -> 100
    wc = World(30, no_bids=((0.15, 250.0),))
    wc.jump(2.5)
    ck(wc.recs("paper_buy") and wc.recs("paper_buy")[0]["qty"] == 100.0 and wc.recs("paper_buy")[0]["ask_size"] == 250.0,
       "250 offered at the seen ask -> qty capped at 100")
    # below k: a 1.9-sd move fires nothing
    wk = World(30)
    wk.jump(1.9)
    ck(wk.tr.n_triggers == 0 and not wk.recs("paper_buy"), "a 1.9-sd move is not a trigger")
    # (b) tau 8 and tau 65
    w8 = World(8); w8.jump(2.5)
    ck(not w8.recs("paper_buy") and w8.tr.n_triggers == 0, "(b) the same jump at tau 8 -> no buy (inside the last 10 s)")
    w65 = World(65); w65.jump(2.5)
    ck(not w65.recs("paper_buy") and w65.tr.n_triggers == 0, "(b) the same jump at tau 65 -> no buy (beyond 60 s)")
    w10 = World(10); w10.jump(2.5)
    w60 = World(60); w60.jump(2.5)
    ck(len(w10.recs("paper_buy")) == 1 and len(w60.recs("paper_buy")) == 1, "the edges tau 10 and tau 60 are inside the window")
    # (c) ask 0.93 and ask 0.65
    w93 = World(30, no_bids=((0.07, 40.0),)); w93.jump(2.5)
    ck(not w93.recs("paper_buy") and w93.recs("trigger") and w93.recs("trigger")[0]["outcome"] == "out_of_band" and w93.recs("trigger")[0]["ask"] == 0.93,
       "(c) ask 0.93 -> no buy, trigger logged out_of_band with the ask seen")
    w65c = World(30, no_bids=((0.35, 40.0),)); w65c.jump(2.5)
    ck(not w65c.recs("paper_buy") and w65c.recs("trigger")[0]["outcome"] == "out_of_band" and w65c.recs("trigger")[0]["ask"] == 0.65,
       "(c) ask 0.65 -> no buy")
    w90 = World(30, no_bids=((0.10, 40.0),)); w90.jump(2.5)
    w70 = World(30, no_bids=((0.30, 40.0),)); w70.jump(2.5)
    ck(len(w90.recs("paper_buy")) == 1 and len(w70.recs("paper_buy")) == 1, "the band edges 0.70 and 0.90 are bought")
    # the book must come from snapshot + deltas: a delta that pulls the 85c level leaves the 90c level, out of band
    wd = World(30, no_bids=((0.15, 40.0), (0.05, 100.0)))
    wd.frame(delta_frame(wd.tk, "no", 0.15, -40.0, seq=2))
    wd.jump(2.5)
    td = wd.recs("trigger")[0] if wd.recs("trigger") else {}
    ck(not wd.recs("paper_buy") and td.get("outcome") == "out_of_band" and td.get("ask") == 0.95 and td.get("ask_size") == 100.0,
       "a delta pulling the 85c level leaves 95c x 100 as the best ask: out of band (the book is snapshot + deltas)")
    wd2 = World(30, no_bids=((0.15, 40.0),))
    wd2.frame(delta_frame(wd2.tk, "no", 0.15, 25.0, seq=2))
    wd2.jump(2.5)
    ck(wd2.recs("paper_buy") and wd2.recs("paper_buy")[0]["qty"] == 65.0, "a delta adding 25 at the 85c level -> 65 bought")
    # (d) a second qualifying jump in the same market -> no second buy
    for s in range(w.s_jump + 1, w.s_jump + 5):
        w.feed(s)
    w.jump(2.5, sec=w.s_jump + 5)
    ck(len(w.recs("paper_buy")) == 1 and w.tr.n_triggers == 2 and w.recs("trigger")[-1]["outcome"] == "already_bought",
       "(d) a second qualifying jump at tau 25 -> no second buy (already_bought)")
    # no book yet -> no buy
    wb = World(30)
    wb.tr.books[wb.tk] = Book()
    wb.jump(2.5)
    ck(not wb.recs("paper_buy") and wb.recs("trigger")[0]["outcome"] == "no_book", "no snapshot yet -> no buy (no_book)")
    # a print arriving 5 s late by the wall clock is not acted on
    wl = World(30)
    wl.jump(2.5, lag=5.0)
    ck(not wl.recs("paper_buy") and wl.recs("trigger")[0]["outcome"] == "stale_print", "a print 5 s old by the wall clock -> no buy (stale_print)")
    # (e) settlement from the 60 prints: YES bought, average above the strike -> qty x (1 - price) - fee
    we = World(30, base=745.30, strike=745.00)
    we.jump(2.5)
    for s in range(we.s_jump + 1, we.C):
        we.feed(s)
    we.T[0] = we.C + SETTLE_WAIT + 1
    we.tr.settle_due(we.T[0])
    st = we.recs("paper_settle")
    exp = 40 * (1 - 0.85) - FEE40
    ck(len(st) == 1 and st[0]["result"] == "yes" and st[0]["src"] == "calc" and st[0]["n_prints"] == 60 and abs(st[0]["pnl"] - exp) < 1e-9,
       "(e) YES bought, 60-print average above the strike -> win, pnl %.4f = 40 x 0.15 - 0.36" % (st[0]["pnl"] if st else 0))
    ck(st and st[0]["result_lifecycle"] is None and st[0]["result_calc"] == "yes" and abs(we.tr.run_pnl - exp) < 1e-9, "(e) booked from the prints (no lifecycle yet), run pnl %.4f" % we.tr.run_pnl)
    # ... and a lifecycle message arriving later confirms it (no second settle)
    we.frame({"type": "market_lifecycle_v2", "sid": 1, "seq": 1, "msg": {"market_ticker": we.tk, "event_type": "determined", "result": "yes", "determination_ts": we.C + 1}})
    ck(len(we.recs("paper_settle")) == 1 and we.recs("lifecycle_late") and we.recs("lifecycle_late")[0]["agree"] is True and not we.recs("settle_corrected"),
       "(e) a late lifecycle 'yes' confirms the booked result, nothing re-booked")
    # YES bought, average below the strike -> -qty x price - fee; settled by the lifecycle message when it arrives
    wf = World(30, base=744.00, strike=745.00)
    wf.jump(2.5)
    for s in range(wf.s_jump + 1, wf.C):
        wf.feed(s)
    wf.T[0] = wf.C + 1.2
    wf.frame({"type": "market_lifecycle_v2", "sid": 1, "seq": 1, "msg": {"market_ticker": wf.tk, "event_type": "determined", "result": "no", "determination_ts": wf.C + 1}})
    st = wf.recs("paper_settle")
    exp = -40 * 0.85 - FEE40
    ck(len(st) == 1 and st[0]["result"] == "no" and st[0]["src"] == "lifecycle" and st[0]["result_calc"] == "no" and st[0]["agree"] is True and abs(st[0]["pnl"] - exp) < 1e-9,
       "(e) YES bought, average below the strike, lifecycle 'no' -> loss, pnl %.4f = -40 x 0.85 - 0.36; calc and lifecycle agree" % (st[0]["pnl"] if st else 0))
    wf.tr.settle_due(wf.C + SETTLE_WAIT + 5)
    ck(len(wf.recs("paper_settle")) == 1 and wf.tr.n_settled == 1 and wf.tr.n_lost == 1, "(e) settle_due does not book it twice")
    # Kalshi disagrees with the computed result: the lifecycle wins and the pnl is corrected
    wg = World(30, base=745.30, strike=745.00)
    wg.jump(2.5)
    for s in range(wg.s_jump + 1, wg.C):
        wg.feed(s)
    wg.tr.settle_due(wg.C + SETTLE_WAIT + 1)
    wg.frame({"type": "market_lifecycle_v2", "sid": 1, "seq": 1, "msg": {"market_ticker": wg.tk, "event_type": "determined", "result": "no"}})
    ck(bool(wg.recs("settle_corrected")) and abs(wg.tr.run_pnl - (-40 * 0.85 - FEE40)) < 1e-9 and wg.tr.n_lost == 1 and wg.tr.n_settled == 1,
       "a later lifecycle result that disagrees corrects the booked pnl to the loss")
    # the strike can arrive from the lifecycle channel
    wm = World(30, strike=None)
    wm.frame({"type": "market_lifecycle_v2", "sid": 1, "seq": 1, "msg": {"market_ticker": wm.tk, "event_type": "metadata_updated", "floor_strike": 745.00,
                                                                           "custom_strike": {"round_digits": "2"}, "strike_type": "greater_or_equal"}})
    ck(wm.tr.markets[wm.tk]["strike"] == 745.0 and wm.tr.markets[wm.tk]["rd"] == 2 and wm.recs("strike")[-1]["src"] == "lifecycle",
       "metadata_updated sets the strike 745.00 with round_digits 2")
    # (f) the sd uses the trailing 300 one-second changes and ignores a gap
    wgap = World(30, gap_at=(1793156400 - 30 - 200, 1793156400 - 30 - 195))     # 5 missing seconds inside the window
    sg = wgap.tr.sig[IID]
    # expected: changes over the last 300 seconds where both seconds exist; the change across the gap does not count
    pr = wgap.tr.prints[IID]
    lo_s = wgap.s_jump - SIGW
    ds = [pr[s] - pr[s - 1] for s in range(lo_s, wgap.s_jump) if s in pr and (s - 1) in pr]
    mu = sum(ds) / len(ds); var = sum((x - mu) ** 2 for x in ds) / (len(ds) - 1)
    ck(sg.n == len(ds) == SIGW - 6 and abs(sg.sd() - math.sqrt(var)) < 1e-9,
       "(f) a 5-s gap: %d valid changes in the 300 slots (300 - 5 missing - 1 across the gap), sd %.6f matches a direct computation" % (sg.n, sg.sd()))
    ck(len(sg.q) == SIGW, "(f) the window is 300 slots by the clock, gap slots included")
    wgap2 = World(30, gap_at=(1793156400 - 30 - 100, 1793156400 - 30 - 95))
    wgap2.jump(5.0)                                   # control: a gap earlier in the window, the jump between consecutive seconds
    ck(wgap2.tr.n_triggers == 1, "(f) a 5-sd move between two consecutive seconds does trigger (control, gap earlier in the window)")
    wgap3 = World(30)
    wgap3.feed(wgap3.s_jump + 3, wgap3.v + wgap3.sd() * 5)    # seconds s_jump..s_jump+2 missing: a reconnect
    ck(wgap3.tr.n_triggers == 0 and wgap3.tr.sig[IID].q[-1] is None and wgap3.tr.sig[IID].n == SIGW - 4,
       "(f) a 5-sd move across a 3-s reconnect gap is not a change: no trigger, nothing added to the sd, 3 empty slots")
    sgm = Sigma()
    for s in range(100, 100 + SIGMIN):
        sgm.push(s, 1.0 + (s % 2) * 0.1)
    ck(sgm.sd() is None and (sgm.push(100 + SIGMIN, 1.0) is not None) and sgm.sd() is not None,
       "(f) the sd is None under 150 valid changes and appears at 150")
    ck(sgm.push(100, 5.0) == "dup" and sgm.n == SIGMIN, "(f) an old or repeated print is ignored")
    wpr = World(30)
    wpr.frame({"type": "cfbenchmarks_value", "sid": 2, "seq": 9, "msg": {"index_id": IID, "data": json.dumps({"time": (wpr.s_jump) * 1000 + 500, "value": "999"})}})
    ck(wpr.tr.sig[IID].last_sec == wpr.s_jump - 1 and wpr.tr.n_triggers == 0, "a print not on the whole second is skipped (scan.py: time % 1000)")
    wpr.frame({"type": "cfbenchmarks_value", "sid": 2, "seq": 10, "msg": {"index_id": IID, "data": "not json"}})
    ck(wpr.recs("bad_print"), "an unreadable print is logged, not fatal")
    # (g) --live without a subaccount or without a signed sender (no key) raises SystemExit before any order
    raised = None
    try:
        World(30, live=True)
    except SystemExit as e:
        raised = str(e)
    ck(raised is not None and "subaccount" in raised, "(g) --live without a subaccount: SystemExit before anything connects (%s)" % raised)
    raised = None
    try:
        World(30, live=True, sub=3)
    except SystemExit as e:
        raised = str(e)
    ck(raised is not None and "sender" in raised, "(g) --live without a signed sender (no key): SystemExit before anything connects")
    # (h) the stop file ends the run cleanly
    global STOP_FILE
    real = STOP_FILE
    STOP_FILE = os.path.join(tempfile.gettempdir(), "jumpband-selftest-%d.stop" % os.getpid())
    try:
        ws_ = World(30)
        ck(not ws_.tr.check_stop_file(), "(h) no stop file -> running")
        open(STOP_FILE, "w").close()
        t0 = time.time()
        asyncio.run(watch_stop(ws_.tr, time.time() + 30, ws_.log, period=0.05))
        ck(ws_.tr.stopped and time.time() - t0 < 5 and ws_.recs("stop_file") and ws_.recs("stopping"),
           "(h) the stop file: the watcher returns within a tick and logs stop_file + stopping (the run then ends)")
        ws_.jump(2.5)
        ck(not ws_.recs("paper_buy") and ws_.recs("trigger")[-1]["outcome"] == "stopped", "(h) after the stop a qualifying jump is logged, not bought")
    finally:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
        STOP_FILE = real
    # fast coins: off by default, on with --fast-k 4 at band 70-95c
    wfast = World(30, series="KXBTC15M")
    ck(wfast.tk not in wfast.tr.markets, "fast coins are not watched without --fast-k")
    wfast4 = World(30, series="KXBTC15M", fast_k=4.0, no_bids=((0.07, 40.0),))
    ck(wfast4.iid == "BRTI" and wfast4.tk in wfast4.tr.markets, "--fast-k 4: BTC is watched on the BRTI index")
    wfast4.jump(3.0)
    ck(wfast4.tr.n_triggers == 0, "--fast-k 4: a 3-sd BTC move is not a trigger")
    wfast4.jump(4.0, sec=wfast4.s_jump + 1)
    fb = wfast4.recs("paper_buy")
    ck(wfast4.tr.n_triggers == 1 and len(fb) == 1 and fb[0]["ask"] == 0.93 and fb[0]["k"] == 4.0 and fb[0]["band"] == [0.70, 0.95],
       "--fast-k 4: a 4-sd BTC move with the ask at 0.93 is bought (band 70-95c)")
    # health and market_done records
    we.tr.health(ws_up=False)
    h = we.recs("health")[-1]
    ck(h["paper_buys"] == 1 and h["settled"] == 1 and abs(h["paper_pnl"] - (40 * 0.15 - FEE40)) < 1e-9 and "prints_per_s" in h and h["markets"] == 1,
       "health: markets, books, prints per second, triggers, paper buys, paper pnl")
    md = we.recs("market_done")
    ck(len(md) == 1 and md[0]["bought"] is True and md[0]["triggers"] == 1, "market_done summary once the close has passed")
    we.tr.settle_due(we.C + FORGET_S + 1)
    ck(we.tk not in we.tr.markets and we.tk not in we.tr.books, "a settled market is forgotten 20 min after its close")
    # REST row -> market
    row = {"ticker": "KXBNB15M-26OCT272300-00", "close_time": "2026-10-28T03:00:00Z", "floor_strike": 744.5, "custom_strike": {"round_digits": "2"}}
    tk_, c_, k_, rd_, src_ = market_from_rest(row, "KXBNB15M")
    ck(c_ == 1793156400 and k_ == 744.5 and rd_ == 2 and src_ == "floor_strike", "a /markets row gives close 03:00Z, strike 744.5, round_digits 2")
    ck(fee(1, 0.85) == 0.01 and fee(100, 0.70) == 1.47 and fee(0, 0.8) == 0.0 and fee(100, 0.85) == 0.9 and fee(53, 0.83) == 0.53,
       "fee: 1 contract at 85c rounds up to 1c; 100 at 70c = 1.47; 100 at 85c = 0.90; 53 at 83c = 0.53")

    # ============================================================================== LIVE (offline: a fake exchange, no keys)
    print("  --- live order path (fake exchange, no network, no keys) ---")
    ck(LIVE_MAX_CONTRACTS == 20 and LIVE_DEFAULT_CONTRACTS == 5 and MAX_COST == 20.0 and STOP_LINE == -25.0 and DAY_STOP == -15.0,
       "(L0) the live constants ship as approved: hard cap 20, default 5 contracts, $20 an order, stop line -$25, day stop -$15")
    FEE5 = fee(5, 0.85)                                   # 0.07 x 0.85 x 0.15 x 5 = 0.0446 -> 0.05 (rounded up to the cent)
    ck(FEE5 == 0.05, "(L0) the fee on 5 contracts at 85c is 4.46c, charged as 5c; cost 4.25, need 4.30")
    # (L1) the exact body: the same jump as (a), live, cash $50 in pool 2, 5 contracts a buy
    snd = live_sender()
    wl1 = World(30, live=True, sub=3, sender=snd, cash={0: None, 2: 50.0})
    wl1.jump(2.5)
    posts = snd.posts()
    ck(len(posts) == 1 and posts[0][1] == "/portfolio/events/orders" and posts[0][3] is None, "(L1) one POST /portfolio/events/orders")
    b1 = posts[0][2] if posts else {}
    cid1 = b1.get("client_order_id", "")
    want = order_body(wl1.tk, "yes", 0.85, 5, 3, cid1, 2)                  # what fxtake_live sends for the same inputs
    ck(set(b1) == set(want) and all(b1.get(k_) == want[k_] for k_ in want),
       "(L1) the body matches fxtake_live.order_body field by field (%d fields)" % len(want))
    ck(b1.get("ticker") == wl1.tk and b1.get("side") == "bid" and b1.get("count") == "5.00" and b1.get("price") == "0.8500"
       and b1.get("time_in_force") == "immediate_or_cancel" and b1.get("self_trade_prevention_type") == "taker_at_cross"
       and b1.get("post_only") is False and cid1.startswith("jb-") and b1.get("subaccount") == 3 and b1.get("exchange_index") == 2,
       "(L1) YES at 85c: side bid, count 5.00, price 0.8500, IOC, taker_at_cross, post_only False, id jb-, subaccount 3, pool 2")
    ck({k_: v_ for k_, v_ in w.recs("trigger")[0].items() if k_ != "t"} == {k_: v_ for k_, v_ in wl1.recs("trigger")[0].items() if k_ != "t"}
       and not wl1.recs("paper_buy"),
       "(L1) live and paper judge the same jump identically: the trigger records are the same field for field; no paper_buy in live")
    o1 = wl1.recs("order"); f1 = wl1.recs("fill")
    ck(len(o1) == 1 and o1[0]["status"] == 201 and o1[0]["filled"] == 5.0 and o1[0]["body"] == b1 and o1[0]["order_id"] == "oid-1",
       "(L1) 'order' logs the body, the status, the fill count and the order id")
    ck(len(f1) == 1 and f1[0]["qty"] == 5.0 and f1[0]["price"] == 0.85 and abs(f1[0]["cost"] - 4.25) < 1e-9 and abs(f1[0]["fee"] - 0.05) < 1e-9,
       "(L1) 'fill': 5 at 0.85 = $4.25, fee $0.05 (from the exchange's average_fee_paid x fills)")
    v1 = wl1.tr.held.get(wl1.tk, {})
    ck(v1.get("live") is True and v1.get("qty") == 5.0 and abs(v1.get("cost", 0) - 4.25) < 1e-9 and v1.get("cid") == cid1 and wl1.tr.n_orders == 1 and wl1.tr.n_fills == 1,
       "(L1) the position is held live: 5 at 0.85, its client id kept")
    ck(abs(wl1.tr.pool_cash[2] - 45.70) < 1e-9, "(L4) cash after the fill: 50.00 - 4.25 - 0.05 = $45.70 (the local figure until the next read)")
    # the NO side: a drop -> buy NO at 85c = ask at YES 0.15
    sn = live_sender()
    wln = World(30, live=True, sub=3, sender=sn, cash={2: 50.0}, yes_bids=((0.15, 30.0),), no_bids=((0.60, 20.0),))
    wln.jump(-2.5)
    bn = sn.posts()[0][2] if sn.posts() else {}
    ck(bn and bn == order_body(wln.tk, "no", 0.85, 5, 3, bn["client_order_id"], 2) and bn["side"] == "ask" and bn["price"] == "0.1500" and bn["count"] == "5.00",
       "(L1) a NO buy at 85c (30 offered): side ask at YES 0.1500, count 5.00; matches fxtake_live.order_body")
    ck(wln.tr.held[wln.tk]["side"] == "no" and wln.recs("fill")[0]["price"] == 0.85 and abs(wln.tr.held[wln.tk]["cost"] - 4.25) < 1e-9,
       "(L1) the NO fill is booked at the NO price 0.85 (the exchange answers in YES terms, 0.15)")
    # (L2) the count cap: min(floor(offered), --max-contracts)
    s2 = live_sender(); w2 = World(30, live=True, sub=3, sender=s2, cash={2: 50.0}, max_contracts=20, no_bids=((0.15, 250.0),))
    w2.jump(2.5)
    ck(s2.posts() and s2.posts()[0][2]["count"] == "20.00", "(L2) 250 offered, --max-contracts 20 -> count 20.00 (the hard cap)")
    s3 = live_sender(); w3 = World(30, live=True, sub=3, sender=s3, cash={2: 50.0}, no_bids=((0.15, 3.7),))
    w3.jump(2.5)
    ck(s3.posts() and s3.posts()[0][2]["count"] == "3.00" and w3.recs("order")[0]["ask_size"] == 3.7, "(L2) 3.7 offered -> count 3.00 (the floor of the size, under the cap of 5)")
    s4 = live_sender(); w4 = World(30, live=True, sub=3, sender=s4, cash={2: 50.0}, no_bids=((0.15, 0.6),))
    w4.jump(2.5)
    ck(not s4.posts() and w4.recs("order_skip") and w4.recs("order_skip")[0]["why"] == "under_one_contract" and w4.tk not in w4.tr.bought,
       "(L2) 0.6 offered -> under one contract: nothing sent (order_skip), the market stays open to a later jump")
    # (L3) --max-cost refuses a dearer order
    s5 = live_sender(); w5 = World(30, live=True, sub=3, sender=s5, cash={2: 50.0}, max_cost=4.0)
    w5.jump(2.5)
    r5 = w5.recs("max_cost")
    ck(not s5.posts() and len(r5) == 1 and abs(r5[0]["need"] - 4.30) < 1e-9 and r5[0]["max_cost"] == 4.0 and w5.tk not in w5.tr.bought and w5.tr.n_orders == 0,
       "(L3) 5 x 0.85 + 0.05 fee = $4.30 over --max-cost 4.00: refused and logged max_cost, nothing sent")
    # (L4) no cash: the empty pot
    s6 = live_sender(); w6 = World(30, live=True, sub=3, sender=s6, cash={0: None, 2: 0.0})
    w6.jump(2.5)
    r6 = w6.recs("no_cash")
    ck(not s6.posts() and len(r6) == 1 and r6[0]["cash"] == 0.0 and abs(r6[0]["need"] - 4.30) < 1e-9 and abs(r6[0]["cost"] - 4.25) < 1e-9
       and abs(r6[0]["fee"] - 0.05) < 1e-9 and r6[0]["qty"] == 5 and w6.tr.cash_dirty,
       "(L4) an empty pot: no_cash logged with cost 4.25 + fee 0.05 = need 4.30 against cash 0.00; nothing sent; a cash re-read asked for")
    ck(w6.tk not in w6.tr.bought and w6.recs("trigger")[-1]["outcome"] == "no_cash" and w6.recs("trigger")[-1]["ask"] == 0.85,
       "(L4) a no_cash skip does not mark the market (money arriving later can still be used) and the trigger record says no_cash, not buy")
    w6.tr.update_cash({0: None, 2: 4.29})
    for s in range(w6.s_jump + 1, w6.s_jump + 3):
        w6.feed(s)
    w6.jump(2.5, sec=w6.s_jump + 3)
    ck(not s6.posts() and len(w6.recs("no_cash")) == 2 and w6.recs("no_cash")[-1]["cash"] == 4.29, "(L4) $4.29 is still 1c short of the $4.30 needed: no_cash again")
    w6.tr.update_cash({0: None, 2: 4.30})
    for s in range(w6.s_jump + 4, w6.s_jump + 6):
        w6.feed(s)
    w6.jump(2.5, sec=w6.s_jump + 6)
    ck(len(s6.posts()) == 1 and w6.recs("fill") and abs(w6.tr.pool_cash[2]) < 1e-9 and not w6.tr.cash_dirty,
       "(L4) $4.30 exactly covers cost + fee: bought on the next qualifying jump; local cash now $0.00")
    cr = w6.recs("cash")
    ck(len(cr) == 2 and cr[-1]["cash"] == {0: None, 2: 4.30} and cr[-1]["was"] == {0: None, 2: 4.29}, "(L4) every change of the pot is logged as 'cash' with the figure before it")
    w6.tr.update_cash(None)
    ck(w6.recs("cash_unreadable") and w6.tr.pool_cash == {0: None, 2: 0.0}, "(L4) an unreadable read is logged and keeps the last figure")
    # (L5) one order per market, ever
    for s in range(wl1.s_jump + 1, wl1.s_jump + 5):
        wl1.feed(s)
    wl1.jump(2.5, sec=wl1.s_jump + 5)
    ck(len(snd.posts()) == 1 and wl1.recs("trigger")[-1]["outcome"] == "already_bought" and wl1.tr.n_orders == 1,
       "(L5) a second qualifying jump in the same market: no second order (already_bought)")
    # (L8) settle money arithmetic with fees, from Kalshi's result
    wl1.T[0] = wl1.C + 60
    wl1.tr.settle_live(wl1.tk, "yes")
    st1 = wl1.recs("settle")
    ck(len(st1) == 1 and abs(st1[0]["money"] - 0.70) < 1e-9 and st1[0]["payout"] == 5.0 and abs(st1[0]["run_money"] - 0.70) < 1e-9
       and st1[0]["src"] == "rest" and "cash" in st1[0] and st1[0]["won"] is True,
       "(L8) a win: payout 5.00 - cost 4.25 - fee 0.05 = +$0.70; the record carries cumulative money and cash")
    ck(abs(wl1.tr.pool_cash[2] - 50.70) < 1e-9 and wl1.tr.cash_dirty and wl1.tr.n_settled == 1 and wl1.tr.n_lost == 0,
       "(L8) the payout is added to the local cash (45.70 + 5.00 = 50.70) and a re-read is asked for")
    wl1.tr.settle_live(wl1.tk, "no")
    ck(len(wl1.recs("settle")) == 1 and abs(wl1.tr.run_pnl - 0.70) < 1e-9, "(L8) a second result for a settled position books nothing")
    sl = live_sender(); wloss = World(30, live=True, sub=3, sender=sl, cash={2: 50.0}); wloss.jump(2.5)
    wloss.tr.settle_live(wloss.tk, "no")
    stl = wloss.recs("settle")
    ck(len(stl) == 1 and abs(stl[0]["money"] + 4.30) < 1e-9 and stl[0]["payout"] == 0.0 and stl[0]["won"] is False and wloss.tr.n_lost == 1
       and abs(stl[0]["day_money"] + 4.30) < 1e-9 and abs(wloss.tr.pool_cash[2] - 45.70) < 1e-9,
       "(L8) a loss: 0 - 4.25 - 0.05 = -$4.30; day money -4.30; cash stays 45.70")
    ck(wloss.tr.flat() and wl1.tr.flat() and wl1.tr.held[wl1.tk]["settled"] is True, "(L8) flat after the settle")
    # (L14) live positions are settled from Kalshi's result only: not from the 60 prints, not from the lifecycle message
    s14 = live_sender(); w14 = World(30, live=True, sub=3, sender=s14, cash={2: 50.0}, base=745.30, strike=745.00)
    w14.jump(2.5)
    for s in range(w14.s_jump + 1, w14.C):
        w14.feed(s)
    w14.T[0] = w14.C + SETTLE_WAIT + 1
    w14.tr.settle_due(w14.T[0])
    ck(not w14.recs("paper_settle") and not w14.recs("settle") and not w14.tr.held[w14.tk]["settled"] and not w14.tr.flat(),
       "(L14) live: the 60-print result books nothing (the position waits for Kalshi's REST result); not flat")
    w14.frame({"type": "market_lifecycle_v2", "sid": 1, "seq": 1, "msg": {"market_ticker": w14.tk, "event_type": "determined", "result": "yes"}})
    lr = w14.recs("lifecycle_result")
    ck(not w14.recs("settle") and len(lr) == 1 and lr[0]["result"] == "yes" and lr[0]["booked"] is False and not w14.tr.held[w14.tk]["settled"],
       "(L14) live: a lifecycle 'determined' is logged (lifecycle_result), not booked")
    w14.tr.settle_live(w14.tk, "yes")
    s14r = w14.recs("settle")
    ck(len(s14r) == 1 and s14r[0]["result_calc"] == "yes" and s14r[0]["result_lifecycle"] == "yes" and s14r[0]["n_prints"] == 60 and abs(s14r[0]["money"] - 0.70) < 1e-9,
       "(L14) the REST settle record carries the 60-print and lifecycle results beside Kalshi's (all yes) for the audit")
    md14 = w14.recs("market_done")
    ck(w14.tr.flat() and len(md14) == 1 and md14[0]["bought"] is True, "(L14) flat after the settle; market_done says bought")
    w14.tr.settle_due(w14.C + FORGET_S + 1)
    ck(w14.tk not in w14.tr.markets and w14.tk not in w14.tr.held, "(L14) a settled live market is forgotten 20 min after its close")
    # (L6) the live stop file: no new orders, exit when flat
    STOP_FILE = os.path.join(tempfile.gettempdir(), "jumpband-live-selftest-%d.stop" % os.getpid())
    try:
        s7 = live_sender(); w7 = World(30, live=True, sub=3, sender=s7, cash={2: 50.0})
        open(STOP_FILE, "w").close()
        w7.tr.check_stop_file()
        w7.jump(2.5)
        ck(not s7.posts() and w7.recs("trigger")[-1]["outcome"] == "stopped" and w7.recs("stop_file") and w7.tr.n_orders == 0,
           "(L6) the live stop file: a qualifying jump is logged 'stopped', nothing sent")
        s8 = live_sender(); w8l = World(30, live=True, sub=3, sender=s8, cash={2: 50.0}); w8l.jump(2.5)
        t0 = time.time()
        asyncio.run(watch_stop(w8l.tr, time.time() + 0.6, w8l.log, period=0.05, grace=0.0))
        ck(w8l.tr.stopped and time.time() - t0 >= 0.5 and w8l.recs("stopping") and not w8l.recs("stopped_flat") and w8l.recs("ending_open"),
           "(L6) with a live position open the watcher waits (stopping logged once, no stopped_flat) and at the end with no grace says ending_open")
        w8l.tr.settle_live(w8l.tk, "yes")
        t0 = time.time()
        asyncio.run(watch_stop(w8l.tr, time.time() + 30, w8l.log, period=0.05))
        ck(time.time() - t0 < 5 and len(w8l.recs("stopped_flat")) == 1,
           "(L6) flat: the watcher returns within a tick and logs stopped_flat (the run then ends)")
    finally:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
        STOP_FILE = real
    # (L7) the stop line writes the stop file
    STOP_FILE = os.path.join(tempfile.gettempdir(), "jumpband-live-selftest-line-%d.stop" % os.getpid())
    try:
        s9 = live_sender(); w9 = World(30, live=True, sub=3, sender=s9, cash={2: 50.0}, stop_line=-4.0)
        w9.tr.line_money = 0.0
        w9.jump(2.5)
        w9.tr.settle_live(w9.tk, "no")
        sl9 = w9.recs("stop_line")
        ck(w9.tr.stopped and os.path.exists(STOP_FILE) and len(sl9) == 1 and abs(sl9[0]["line_money"] + 4.30) < 1e-9 and sl9[0]["stop_line"] == -4.0
           and abs(w9.recs("settle")[0]["line_money"] + 4.30) < 1e-9,
           "(L7) stop line -$4.00: one loss of -$4.30 crosses it -> stop_line logged, the stop file written, stopped")
        with open(STOP_FILE, encoding="utf-8") as fh:
            txt = fh.read()
        ck("stop line" in txt and "jumpband_live" in txt, "(L7) the stop file says who wrote it and why")
        os.remove(STOP_FILE)
        s10 = live_sender(); w10l = World(30, live=True, sub=3, sender=s10, cash={2: 50.0}, stop_line=-4.31)
        w10l.tr.line_money = 0.0
        w10l.jump(2.5); w10l.tr.settle_live(w10l.tk, "no")
        ck(not w10l.tr.stopped and not os.path.exists(STOP_FILE) and not w10l.recs("stop_line") and abs(w10l.tr.line_money + 4.30) < 1e-9,
           "(L7) -$4.30 against a -$4.31 line: trades on")
        s11 = live_sender(); w11 = World(30, live=True, sub=3, sender=s11, cash={2: 50.0}, stop_line=-1.0)
        w11.jump(2.5); w11.tr.settle_live(w11.tk, "no")
        ck(w11.tr.line_money is None and not w11.tr.stopped and not os.path.exists(STOP_FILE),
           "(L7) a Trader main() did not seed (line_money None) never writes the stop file: a self-test cannot stand the real bot down")
    finally:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
        STOP_FILE = real
    # (L17) the stop line's sum from the log: the last settle per ticker, garbage and other kinds skipped, a missing log is 0
    tmpl = os.path.join(tempfile.gettempdir(), "jumpband-live-selftest-line-%d.jsonl" % os.getpid())
    with open(tmpl, "w", encoding="utf-8") as f:
        for t_, tk_, m_ in (("2026-10-30T10:00:00Z", "A-1", 0.70), ("2026-10-30T11:00:00Z", "B-1", -4.30),
                            ("2026-10-30T11:30:00Z", "B-1", -4.30), ("2026-10-30T12:00:00Z", "C-1", 0.70)):
            f.write(json.dumps({"t": t_, "kind": "settle", "ticker": tk_, "money": m_}) + "\n")
        f.write("not json\n")
        f.write(json.dumps({"t": "2026-10-30T13:00:00Z", "kind": "fill", "ticker": "D-1", "money": -50}) + "\n")
    try:
        ck(abs(line_money_from_log(tmpl) - (0.70 - 4.30 + 0.70)) < 1e-9 and line_money_from_log(tmpl + ".missing") == 0.0,
           "(L17) the log sum: each market once (B-1 booked twice counts once), garbage and non-settles skipped, missing log = 0 (%.2f)" % line_money_from_log(tmpl))
    finally:
        os.remove(tmpl)
    # (L12) the day stop: -$15 settled in one ET day stops new orders for the rest of that day
    s12 = live_sender(); w12 = World(30, live=True, sub=3, sender=s12, cash={2: 100.0})
    w12.jump(2.5); w12.tr.settle_live(w12.tk, "no")
    for i in range(3):
        tk12 = "KXBNB15M-TEST-%d" % i
        w12.tr.add_market(tk12, "KXBNB15M", w12.C + 900 * (i + 1), 745.0, 2, "test", 2)
        w12.tr.held[tk12] = {"side": "yes", "qty": 5.0, "px": 0.85, "cost": 4.25, "fee": 0.05, "close_s": w12.C + 900 * (i + 1), "settled": False,
                             "result": None, "money": None, "src": None, "cid": "jb-t-%d" % i, "sub": 3, "pool": 2, "live": True}
        if i == 1:
            ck(w12.tr.halt_day is None and abs(w12.tr.day_money + 8.60) < 1e-9, "(L12) two losses, -$8.60 on the day: no day stop yet")
        w12.tr.settle_live(tk12, "no")
    ds12 = w12.recs("day_stop")
    ck(w12.tr.halt_day == et_day(w12.T[0]) and len(ds12) == 1 and abs(ds12[0]["day_money"] + 17.20) < 1e-9 and abs(w12.tr.run_pnl + 17.20) < 1e-9,
       "(L12) four losses of -$4.30 = -$17.20 pass DAY_STOP -$15: day_stop logged once, for today's ET day")
    s12b = live_sender(); w12b = World(30, live=True, sub=3, sender=s12b, cash={2: 50.0})
    w12b.tr.halt_day = et_day(w12b.T[0])
    w12b.jump(2.5)
    ck(not s12b.posts() and w12b.recs("refused") and w12b.recs("refused")[0]["why"] == "day_stop" and w12b.tk not in w12b.tr.bought,
       "(L12) after the day stop a qualifying jump is refused (day_stop), nothing sent")
    w12b.tr.halt_day = "2000-01-01"
    for s in range(w12b.s_jump + 1, w12b.s_jump + 3):
        w12b.feed(s)
    w12b.jump(2.5, sec=w12b.s_jump + 3)
    ck(len(s12b.posts()) == 1, "(L12) a day stop from another ET day does not bind: bought")
    # (L11) the exchange's answers: a 4xx, an unreadable answer (halt + read-back), a missed IOC, a partial fill, a resting IOC
    s13 = live_sender(status=400); w13 = World(30, live=True, sub=3, sender=s13, cash={2: 50.0}); w13.jump(2.5)
    of13 = w13.recs("order_fail")
    ck(len(s13.posts()) == 1 and len(of13) == 1 and of13[0]["why"] == "rejected" and of13[0]["status"] == 400 and w13.tk not in w13.tr.held
       and w13.tr.halted is None and w13.tk in w13.tr.bought and w13.tr.flat(),
       "(L11) a 400: order_fail 'rejected', nothing held, not halted, the market counts as ordered (never a second order)")
    s15 = live_sender(status=-1); w15 = World(30, live=True, sub=3, sender=s15, cash={2: 50.0}); w15.jump(2.5)
    ck(w15.tr.halted and w15.tr.held[w15.tk].get("unknown") is True and w15.recs("order_fail")[0]["why"] == "unreadable" and w15.recs("halt") and not w15.tr.flat(),
       "(L11) an unreadable answer (request failed): halted, the position marked unknown (not flat), order_fail 'unreadable'")
    s16 = live_sender(); w16 = World(30, live=True, sub=3, sender=s16, cash={2: 50.0}); w16.tr.halted = "test halt"; w16.jump(2.5)
    ck(not s16.posts() and w16.recs("refused") and w16.recs("refused")[0]["why"] == "halted", "(L11) halted: a qualifying jump is refused, nothing sent")
    cid15 = w15.tr.held[w15.tk]["cid"]
    s15.orders.append({"client_order_id": cid15, "order_id": "o-r", "status": "executed", "fill_count_fp": "5.00", "remaining_count_fp": "0.00",
                       "yes_price_dollars": "0.8500", "taker_fees_dollars": "0.05"})
    w15.tr.recover_unknown()
    v15 = w15.tr.held[w15.tk]
    ck(not v15.get("unknown") and v15["qty"] == 5.0 and abs(v15["cost"] - 4.25) < 1e-9 and abs(v15["fee"] - 0.05) < 1e-9 and w15.recs("recovered")
       and any(c[0] == "GET" and c[1] == "/portfolio/orders" and c[3]["subaccount"] == 3 for c in s15.calls),
       "(L11) recover_unknown reads the order back from subaccount 3's order list: 5 filled at 0.85, fee 0.05; the position is known again")
    w15.tr.settle_live(w15.tk, "yes")
    ck(abs(w15.tr.run_pnl - 0.70) < 1e-9 and w15.tr.flat(), "(L11) ... and it settles like any other fill (+$0.70)")
    s17 = live_sender(fill=0); w17 = World(30, live=True, sub=3, sender=s17, cash={2: 50.0}); w17.jump(2.5)
    ck(len(s17.posts()) == 1 and w17.recs("order_fail")[0]["why"] == "no_fill" and w17.tk not in w17.tr.held and w17.tr.halted is None
       and w17.tr.n_fills == 0 and abs(w17.tr.pool_cash[2] - 50.0) < 1e-9,
       "(L11) an IOC that missed (fill 0.00, remaining 0.00): order_fail 'no_fill', nothing held, cash untouched, not halted")
    s18 = live_sender(fill=3); w18 = World(30, live=True, sub=3, sender=s18, cash={2: 50.0}); w18.jump(2.5)
    ck(w18.tr.held[w18.tk]["qty"] == 3.0 and abs(w18.tr.held[w18.tk]["cost"] - 2.55) < 1e-9 and w18.recs("fill")[0]["qty"] == 3.0 and w18.recs("fill")[0]["asked"] == 5,
       "(L11) a partial fill books what filled: 3 of 5 at 0.85 = $2.55")

    def resting_sender():
        calls = []

        def send(method, path, body, query):
            calls.append((method, path, body, query))
            if method == "POST":
                return 201, {"order_id": "oid-rest", "client_order_id": body["client_order_id"], "fill_count": "2.00", "remaining_count": "3.00",
                             "average_fill_price": body["price"], "average_fee_paid": "0.0100", "ts_ms": 1}
            if method == "DELETE":
                return 200, {"reduced_by": "3.00"}
            return 200, {}
        send.calls = calls
        return send
    s19 = resting_sender(); w19 = World(30, live=True, sub=3, sender=s19, cash={2: 50.0}); w19.jump(2.5)
    dels = [c for c in s19.calls if c[0] == "DELETE"]
    ck(w19.tr.halted and "resting" in w19.tr.halted and len(dels) == 1 and dels[0][1] == "/portfolio/events/orders/oid-rest"
       and dels[0][3] == {"subaccount": 3, "exchange_index": 2} and w19.recs("cancelled") and w19.tr.held[w19.tk]["qty"] == 2.0,
       "(L11) an IOC answered with 3 contracts still live: cancelled (DELETE with the pot and pool), halted, the 2 that filled are held")
    # (L10) --dry-run: everything but the send
    sd_ = live_sender(); wd_ = World(30, live=True, sub=3, sender=sd_, cash={0: None, 2: 0.0}, dry=True); wd_.jump(2.5)
    wo = wd_.recs("would_order")
    ck(not sd_.posts() and len(wo) == 1 and wo[0]["body"] == order_body(wd_.tk, "yes", 0.85, 5, 3, wo[0]["body"]["client_order_id"], 2)
       and wo[0]["funded"] is False and wo[0]["cash"] == 0.0 and abs(wo[0]["need"] - 4.30) < 1e-9 and wd_.tk in wd_.tr.bought and wd_.tr.n_orders == 1
       and not wd_.recs("no_cash") and not wd_.recs("order") and not wd_.tr.held,
       "(L10) --dry-run: would_order with the exact body and the cash it would need (funded false on an empty pot); nothing sent, nothing held")
    for s in range(wd_.s_jump + 1, wd_.s_jump + 3):
        wd_.feed(s)
    wd_.jump(2.5, sec=wd_.s_jump + 3)
    ck(len(wd_.recs("would_order")) == 1 and wd_.recs("trigger")[-1]["outcome"] == "already_bought", "(L10) --dry-run: one would-be order per market")
    sd2 = live_sender(); wd2_ = World(30, live=True, sub=3, sender=sd2, cash={2: 50.0}, dry=True); wd2_.jump(2.5)
    ck(wd2_.recs("would_order")[0]["funded"] is True and not sd2.posts(), "(L10) --dry-run with $50 in the pot: funded true, still nothing sent")
    # (L9) the command line: refusals before anything connects
    def args(**kw):
        d = dict(selftest=False, live=False, dry_run=False, subaccount=None, series=",".join(SLOW), k=K, lo=LO, hi=HI, fast_k=None,
                 max_contracts=None, max_cost=MAX_COST, stop_line=STOP_LINE, rule_override=False, minutes=20160.0, log=None)
        d.update(kw)
        return argparse.Namespace(**d)

    def refuses(**kw):
        try:
            check_args(args(**kw))
        except SystemExit as e:
            return str(e)
        return None
    r9 = refuses(live=True)
    ck(r9 is not None and "--subaccount" in r9, "(L9) --live without --subaccount refuses: '%s'" % r9)
    r9 = refuses(live=True, subaccount=3, max_contracts=50.0)
    ck(r9 is not None and "20" in r9 and "50" in r9, "(L9) --live --subaccount 3 --max-contracts 50 refuses (hard cap 20): '%s'" % r9)
    ck(refuses(live=True, subaccount=0) is not None and refuses(live=True, subaccount=64) is not None, "(L9) --subaccount 0 (the primary account) and 64 refuse")
    ck(refuses(live=True, subaccount=3, max_contracts=2.5) is not None and refuses(live=True, subaccount=3, max_contracts=0.0) is not None,
       "(L9) a fractional or zero live count refuses")
    ck(refuses(dry_run=True) is not None, "(L9) --dry-run without --live refuses")
    ck(refuses(subaccount=3) is not None, "(L9) --subaccount without --live refuses")
    ck(refuses(live=True, subaccount=3, stop_line=5.0) is not None and refuses(live=True, subaccount=3, max_cost=0.0) is not None,
       "(L9) a positive --stop-line or a zero --max-cost refuses")
    ok9 = check_args(args(live=True, subaccount=3))
    ck(ok9["max_contracts"] == 5 and ok9["log"] == LIVE_LOG and ok9["stop_file"] == LIVE_STOP_FILE and ok9["series"] == list(SLOW),
       "(L9) --live --subaccount 3: 5 contracts by default, the live log and the live stop file, the four slow coins")
    ck(check_args(args(live=True, subaccount=3, max_contracts=20.0))["max_contracts"] == 20, "(L9) --max-contracts 20 is allowed in live mode")
    okd = check_args(args(live=True, subaccount=3, dry_run=True))
    ck(okd["log"] == DRY_LOG and okd["stop_file"] == DRY_STOP_FILE, "(L9) --live --dry-run: its own log and stop file")
    okp = check_args(args())
    ck(okp["max_contracts"] == 100.0 and okp["log"] == LOG and okp["stop_file"] == PAPER_STOP_FILE, "(L9) paper: 100 contracts, the paper log and stop file")
    ck(check_args(args(log=r"C:\x\y.jsonl"))["log"] == r"C:\x\y.jsonl", "(L9) --log overrides the default")
    raised = None
    try:
        World(30, live=True, sub=3, sender=live_sender(), max_contracts=50)
    except SystemExit as e:
        raised = str(e)
    ck(raised is not None and "20" in raised, "(L9) the Trader itself refuses 50 contracts in live mode: the cap holds without the CLI")
    # (L15) body_ok, the rails before every send
    tkb = "KXBNB15M-26OCT272300-00"
    bb = order_body(tkb, "yes", 0.85, 5, 3, "jb-1-bnb", 2)
    ck(body_ok(bb, 3, 2, 0.85, 5, 5, LO, HI), "(L15) body_ok passes the real body")
    ck(not body_ok(dict(bb, subaccount=0), 0, 2, 0.85, 5, 5, LO, HI), "(L15) the primary account (subaccount 0) is refused")
    ck(not body_ok(dict(bb, exchange_index=1), 3, 1, 0.85, 5, 5, LO, HI), "(L15) pool 1 is never sent")
    ck(not body_ok(dict(bb, exchange_index=0), 3, 2, 0.85, 5, 5, LO, HI), "(L15) a body whose pool is not the market's (0 vs 2) is refused")
    ck(not body_ok(dict(bb, count="21.00"), 3, 2, 0.85, 21, 21, LO, HI), "(L15) 21 contracts refused (hard cap 20)")
    ck(not body_ok(dict(bb, count="6.00"), 3, 2, 0.85, 5, 5, LO, HI), "(L15) a count other than the one decided is refused")
    ck(not body_ok(dict(bb, count="2.50"), 3, 2, 0.85, 2.5, 5, LO, HI), "(L15) a fractional count is refused")
    ck(not body_ok(dict(bb, post_only=True), 3, 2, 0.85, 5, 5, LO, HI), "(L15) post_only (would rest) is refused")
    ck(not body_ok(dict(bb, time_in_force="good_till_canceled"), 3, 2, 0.85, 5, 5, LO, HI), "(L15) a resting order is refused")
    ck(not body_ok(dict(bb, self_trade_prevention_type="maker"), 3, 2, 0.85, 5, 5, LO, HI), "(L15) self-trade prevention other than taker_at_cross is refused")
    ck(not body_ok(dict(bb, price="0.9500"), 3, 2, 0.95, 5, 5, LO, HI), "(L15) a price outside the band 0.70-0.90 is refused")
    ck(not body_ok(dict(bb, price="0.8600"), 3, 2, 0.85, 5, 5, LO, HI), "(L15) a price other than the seen ask is refused")
    ck(not body_ok(dict(bb, client_order_id="fxt-1"), 3, 2, 0.85, 5, 5, LO, HI), "(L15) another bot's id prefix is refused")
    bbn = order_body(tkb, "no", 0.85, 5, 3, "jb-2-bnb", 2)
    ck(body_ok(bbn, 3, 2, 0.85, 5, 5, LO, HI) and not body_ok(bbn, 3, 2, 0.15, 5, 5, LO, HI), "(L15) a NO body is judged on the NO price 0.85 (ask at YES 0.15)")
    # (L16) the market's pool comes from Kalshi's row, never from a constant
    ck(pool_from_rest({"exchange_index": 2}) == 2 and pool_from_rest({"exchange_index": "0"}) == 0 and pool_from_rest({}) is None and pool_from_rest({"exchange_index": "x"}) is None,
       "(L16) the market's pool is read from its /markets row (exchange_index); missing or unreadable -> None")
    s20 = live_sender(); w20 = World(30, live=True, sub=3, sender=s20, cash={2: 50.0})
    w20.tr.add_market("KXBNB15M-NOPOOL-00", "KXBNB15M", w20.C + 900, 745.0, 2, "test")
    w20.tr.add_market("KXBNB15M-NOPOOL-00", "KXBNB15M", w20.C + 900, 745.0, 2, "test")
    ck("KXBNB15M-NOPOOL-00" not in w20.tr.markets and len(w20.recs("market_skipped")) == 1 and w20.recs("market_skipped")[0]["why"] == "pool",
       "(L16) live: a market whose pool Kalshi did not give is not watched (market_skipped, logged once), as fxtake does")
    ck(w20.tr.markets[w20.tk]["pool"] == 2 and w20.recs("market")[0]["pool"] == 2, "(L16) the watched market carries its pool 2 and its record says so")
    wp = World(30); wp.tr.add_market("KXBNB15M-NOPOOL-00", "KXBNB15M", wp.C + 900, 745.0, 2, "test")
    ck("KXBNB15M-NOPOOL-00" in wp.tr.markets, "(L16) paper: a market without a pool is still watched")
    # (L13) the live health record
    wl1.tr.health(ws_up=True)
    h1 = wl1.recs("health")[-1]
    ck(h1["live"] is True and h1["cash"] == wl1.tr.pool_cash and h1["orders"] == 1 and h1["fills"] == 1 and abs(h1["money"] - 0.70) < 1e-9
       and h1["subaccount"] == 3 and "day_money" in h1 and "line_money" in h1 and h1["max_contracts"] == 5.0 and h1["stop_line"] == STOP_LINE and "paper_pnl" not in h1,
       "(L13) the live health record carries cash, orders, fills, money, day and line money, subaccount, the caps")

    # ============================================================================== FIXES from the 2026-10-30 adversarial reviews
    print("  --- 10-30 review fixes: books before the log, the order thread, cancel failures, unknown write-off, restart ---")
    ck(END_GRACE_S == 600.0 and UNKNOWN_MISSES == 3 and UNKNOWN_CLOSE_GRACE_S == 60.0 and CRYPTO_POOL == 2,
       "(F0) end grace 10 min; an unknown order is written off after 3 empty reads once its market is 60 s closed; the warning pool is 2")
    # (F1) the log never raises
    bad_log = Logger(path=tempfile.gettempdir())                  # a directory: opening it for append fails on every OS
    err_fd, buf = sys.stderr, io.StringIO()
    sys.stderr = buf
    try:
        bad_log.write("probe", x=1)
    finally:
        sys.stderr = err_fd
    ck(bad_log.failed is not None and bad_log.n_failed == 1 and '"probe"' in buf.getvalue(),
       "(F1) a log write the disk refuses does not raise: counted (%s) and the record printed to stderr" % (bad_log.failed or "")[:40])
    wl1.log.failed, wl1.log.n_failed = "x", 2
    wl1.tr.health(ws_up=True)
    ck(wl1.recs("health")[-1]["log_failed"] == "x" and wl1.recs("health")[-1]["log_failures"] == 2 and "unknown" in wl1.recs("health")[-1],
       "(F1) health reports log failures, unknown and in-flight counts")
    wl1.log.failed, wl1.log.n_failed = None, 0
    # (F2) the position is in the books BEFORE the send
    seen = {}

    def peeking_sender():
        inner = live_sender()

        def send(method, path, body, query):
            if method == "POST":
                v_ = wf2.tr.held.get(wf2.tk)
                seen["held"] = None if v_ is None else dict(v_)
                seen["kinds"] = [r["kind"] for r in wf2.sent]
            return inner(method, path, body, query)
        send.calls, send.posts, send.orders = inner.calls, inner.posts, inner.orders
        return send
    sf2 = peeking_sender(); wf2 = World(30, live=True, sub=3, sender=sf2, cash={2: 50.0}); wf2.jump(2.5)
    h2 = seen.get("held") or {}
    ck(h2.get("unknown") is True and h2.get("inflight") is True and h2.get("qty") == 0.0 and h2.get("live") is True
       and h2.get("body") == sf2.posts()[0][2] and h2.get("cid") == sf2.posts()[0][2]["client_order_id"] and wf2.tk in wf2.tr.bought,
       "(F2) at the moment of the send the position is already in the books as an in-flight unknown order (qty 0, body and client id kept), the market marked bought")
    ck(seen.get("kinds", [""])[-1] == "order_sent" and wf2.recs("order_sent")[0]["body"] == sf2.posts()[0][2] and wf2.recs("order_sent")[0]["close_s"] == wf2.C,
       "(F2) 'order_sent' with the body and the market's close is logged before the send, 'order' after it")
    v2 = wf2.tr.held[wf2.tk]
    ck(not v2.get("unknown") and not v2.get("inflight") and v2["qty"] == 5.0 and not wf2.tr.flat()
       and [r["kind"] for r in wf2.sent[-4:]] == ["trigger", "order_sent", "order", "fill"],
       "(F2) the answer replaces it with the fill: known, 5 held; records trigger / order_sent / order / fill in that order")
    # (F3) an exception between the POST and the booking (the reviewers' P5 / logfail2: a log write that raises)

    class RaisingLogger(Logger):
        boom = None

        def write(self, kind, **kw):
            if kind == self.boom:
                raise OSError(28, "No space left on device")
            super().write(kind, **kw)
    sf3 = live_sender(); wf3 = World(30, live=True, sub=3, sender=sf3, cash={2: 50.0}, log_cls=RaisingLogger)
    wf3.log.boom = "order"
    wf3.jump(2.5)
    v3 = wf3.tr.held.get(wf3.tk, {})
    ck(len(sf3.posts()) == 1 and v3.get("qty") == 5.0 and not v3.get("unknown") and not v3.get("inflight") and wf3.tr.halted is None
       and not wf3.tr.flat() and wf3.recs("book_error") and wf3.tr.n_fills == 1 and abs(wf3.tr.pool_cash[2] - 45.70) < 1e-9 and not wf3.recs("order"),
       "(F3) the exchange fills 5 and the very next write after the answer raises: the fill is ALREADY in the books (5 held, cash 45.70), book_error logged, not halted")
    wf3.log.boom = None
    wf3.tr.settle_live(wf3.tk, "yes")
    ck(abs(wf3.tr.run_pnl - 0.70) < 1e-9 and wf3.tr.flat(), "(F3) ... and it settles +$0.70 like any other fill")
    import pintake as _pt
    _orig_norm = _pt.normalise

    def _boom(*a, **k):
        raise RuntimeError("normalise exploded")
    sf3b = live_sender(); wf3b = World(30, live=True, sub=3, sender=sf3b, cash={2: 50.0})
    _pt.normalise = _boom
    try:
        wf3b.jump(2.5)
    finally:
        _pt.normalise = _orig_norm
    v3b = wf3b.tr.held.get(wf3b.tk, {})
    ck(len(sf3b.posts()) == 1 and v3b.get("unknown") is True and not v3b.get("inflight") and wf3b.tr.halted and "booking failed" in wf3b.tr.halted
       and not wf3b.tr.flat() and wf3b.recs("halt") and wf3b.tr.n_fills == 0,
       "(F3) an exception INSIDE the booking (before the books are complete): the position stays as the in-flight unknown, halted, not flat")
    sf3b.orders.append({"client_order_id": v3b["cid"], "order_id": "o-f3", "status": "executed", "fill_count_fp": "5.00", "remaining_count_fp": "0.00",
                        "yes_price_dollars": "0.8500", "taker_fees_dollars": "0.05"})
    wf3b.tr.recover_unknown()
    wf3b.tr.settle_live(wf3b.tk, "yes")
    ck(wf3b.tr.held[wf3b.tk]["qty"] == 5.0 and abs(wf3b.tr.run_pnl - 0.70) < 1e-9 and wf3b.tr.flat() and wf3b.tr.n_fills == 1,
       "(F3) ... recover_unknown reads the 5 back from the order list and the settle books +$0.70: nothing fell out of the books")
    # (F4) the dispatcher: the loop thread decides and books, the send is handed off (run_live's order thread)
    queued = []
    sf4 = live_sender(); wf4 = World(30, live=True, sub=3, sender=sf4, cash={2: 50.0})
    wf4.tr.dispatch = lambda fn, *a: queued.append((fn, a))
    wf4.jump(2.5)
    v4 = wf4.tr.held.get(wf4.tk, {})
    ck(len(queued) == 1 and queued[0][0] == wf4.tr.send_live and not sf4.posts() and wf4.tk in wf4.tr.bought and v4.get("inflight") is True
       and wf4.recs("order_sent") and not wf4.recs("order") and wf4.tr.n_orders == 1 and not wf4.tr.flat(),
       "(F4) with a dispatcher the loop thread only decides, marks bought, books the in-flight unknown and logs order_sent; the send is handed off")
    for s in range(wf4.s_jump + 1, wf4.s_jump + 3):
        wf4.feed(s)
    wf4.jump(2.5, sec=wf4.s_jump + 3)
    ck(len(queued) == 1 and wf4.recs("trigger")[-1]["outcome"] == "already_bought", "(F4) a second jump while the order is still in flight: already_bought, nothing queued")
    wf4.tr.recover_unknown()
    ck(not any(c[0] == "GET" for c in sf4.calls), "(F4) recover_unknown leaves an order still in flight alone")
    fn4, a4 = queued[0]
    fn4(*a4)
    ck(len(sf4.posts()) == 1 and wf4.tr.held[wf4.tk]["qty"] == 5.0 and wf4.recs("fill") and not wf4.tr.held[wf4.tk].get("inflight"),
       "(F4) the handed-off send posts once and books the fill")
    # (F5) a resting IOC whose cancel fails (the reviewers' P2): the position stays UNKNOWN until the final record is read

    def resting_sender2(delete=(404, '{"error":{"code":"not_found"}}'), raise_delete=False, fee_c="0.0100"):
        calls = []

        def send(method, path, body, query):
            calls.append((method, path, body, query))
            if method == "POST":
                return 201, {"order_id": "oid-rest", "client_order_id": body["client_order_id"], "fill_count": "2.00", "remaining_count": "3.00",
                             "average_fill_price": body["price"], "average_fee_paid": fee_c, "ts_ms": 1}
            if method == "DELETE":
                if raise_delete:
                    raise RuntimeError("socket timeout")
                return delete
            if path == "/portfolio/orders":
                return 200, {"orders": list(send.orders)}
            return 200, {}
        send.calls, send.orders = calls, []
        return send
    sf5 = resting_sender2(); wf5 = World(30, live=True, sub=3, sender=sf5, cash={2: 50.0}); wf5.jump(2.5)
    v5 = wf5.tr.held[wf5.tk]; c5 = wf5.recs("cancelled")
    ck(wf5.tr.halted and "resting" in wf5.tr.halted and len(c5) == 1 and c5[0]["status"] == 404 and c5[0]["ok"] is False and v5.get("unknown") is True
       and v5["qty"] == 2.0 and v5.get("cancel_status") == 404 and not wf5.tr.flat() and wf5.recs("order_fail")[-1]["why"] == "resting"
       and sf5.calls[-1][0] == "DELETE" and sf5.calls[-1][3] == {"subaccount": 3, "exchange_index": 2},
       "(F5) an IOC answered 2 filled / 3 live whose DELETE answers 404: halted, the position stays UNKNOWN (2 known so far), not flat")
    wf5.tr.settle_live(wf5.tk, "yes")
    ck(not wf5.recs("settle") and not wf5.tr.flat(), "(F5) an unknown position is never settled from a market result")
    sf5.orders.append({"client_order_id": v5["cid"], "order_id": "oid-rest", "status": "executed", "fill_count_fp": "5.00", "remaining_count_fp": "0.00",
                       "yes_price_dollars": "0.8500", "taker_fees_dollars": "0.0446"})
    wf5.tr.recover_unknown()
    ck(not v5.get("unknown") and v5["qty"] == 5.0 and abs(v5["cost"] - 4.25) < 1e-9 and abs(v5["fee"] - 0.05) < 1e-9 and wf5.recs("recovered")
       and abs(wf5.recs("recovered")[0]["fee_reported"] - 0.0446) < 1e-9,
       "(F5) the final record says all 5 filled (the 3 landed before the cancel): re-booked as 5 at 0.85, the 4.46c fee booked as the 5c charged")
    wf5.tr.settle_live(wf5.tk, "yes")
    ck(abs(wf5.tr.run_pnl - 0.70) < 1e-9 and wf5.tr.flat() and wf5.tr.halted, "(F5) ... settles +$0.70 and the bot is flat; still halted")
    sf5b = resting_sender2(raise_delete=True); wf5b = World(30, live=True, sub=3, sender=sf5b, cash={2: 50.0}); wf5b.jump(2.5)
    v5b = wf5b.tr.held[wf5b.tk]
    ck(v5b.get("unknown") is True and v5b.get("cancel_status") == -1 and wf5b.recs("cancelled")[0]["status"] == -1 and not wf5b.tr.flat(),
       "(F5) a DELETE whose request fails (status -1): the position stays unknown, not flat")
    sf5b.orders.append({"client_order_id": v5b["cid"], "order_id": "oid-rest", "status": "resting", "fill_count_fp": "2.00", "remaining_count_fp": "3.00",
                        "yes_price_dollars": "0.8500"})
    wf5b.tr.recover_unknown()
    cr5 = wf5b.recs("cancel_retry")
    ck(v5b.get("unknown") is True and len(cr5) == 1 and cr5[0]["order_id"] == "oid-rest" and sf5b.calls[-1][0] == "DELETE" and not wf5b.tr.flat(),
       "(F5) a record still resting is cancelled again (cancel_retry) and stays unknown")
    # (F6) contracts still live but no order_id in the answer (the reviewers' P1)

    def noid_sender():
        calls = []

        def send(method, path, body, query):
            calls.append((method, path, body, query))
            if method == "POST":
                return 201, {"client_order_id": body["client_order_id"], "fill_count": "2.00", "remaining_count": "3.00",
                             "average_fill_price": body["price"], "average_fee_paid": "0.0100"}
            return 200, {"orders": []}
        send.calls = calls
        return send
    sf6 = noid_sender(); wf6 = World(30, live=True, sub=3, sender=sf6, cash={2: 50.0}); wf6.jump(2.5)
    ck(wf6.tr.halted and "resting" in wf6.tr.halted and not any(c[0] == "DELETE" for c in sf6.calls) and wf6.tr.held[wf6.tk].get("unknown") is True
       and not wf6.tr.flat() and wf6.recs("order_fail")[-1]["why"] == "resting",
       "(F6) contracts still live but no order_id: halted, no DELETE possible, the position is unknown until read back")
    # (F7) an unknown order the order list never shows (the reviewers' P4 / E): written off once the market is closed
    sf7 = live_sender(status=-1); wf7 = World(30, live=True, sub=3, sender=sf7, cash={2: 50.0}); wf7.jump(2.5)
    for _ in range(3):
        wf7.tr.recover_unknown()
    v7 = wf7.tr.held[wf7.tk]
    ck(v7.get("unknown") is True and v7["misses"] == 3 and not wf7.tr.flat() and not wf7.recs("recovered_none"),
       "(F7) 3 empty order-list reads before the close keep it unknown (the order could still be there)")
    wf7.tr.send = lambda m, p, b, q: (-1, "timeout")
    wf7.tr.recover_unknown()
    ck(v7["misses"] == 3, "(F7) a failed order-list read is not a miss")
    wf7.tr.send = sf7
    wf7.T[0] = wf7.C + UNKNOWN_CLOSE_GRACE_S - 1
    wf7.tr.recover_unknown()
    ck(v7.get("unknown") is True and v7["misses"] == 4, "(F7) 59 s after the close: still not written off")
    wf7.T[0] = wf7.C + UNKNOWN_CLOSE_GRACE_S + 1
    wf7.tr.recover_unknown()
    ck(not v7.get("unknown") and v7["settled"] and v7["money"] == 0.0 and wf7.recs("recovered_none") and wf7.recs("settle_none")[-1]["why"] == "unknown_written_off"
       and wf7.tr.flat() and wf7.tr.halted and wf7.tr.n_written_off == 1 and wf7.tr.run_pnl == 0.0,
       "(F7) 61 s after the close, 5 empty reads: written off (recovered_none + settle_none), flat so a stop file can end the run; still halted, no money booked")
    # (F8) restart: the books from the log (the reviewers' P7 and 'positions open at exit')
    tmp8 = os.path.join(tempfile.gettempdir(), "jumpband-live-selftest-restore-%d.jsonl" % os.getpid())
    T8 = 1793156400.0
    today8 = et_day(T8)

    def rec8(kind, dt, **kw):
        d = {"t": iso(T8 + dt), "kind": kind}
        d.update(kw)
        return json.dumps(d)
    bA = order_body("KXBNB15M-A", "yes", 0.85, 5, 3, "jb-a", 2)
    bB = order_body("KXZEC15M-B", "no", 0.80, 5, 3, "jb-b", 2)
    lines8 = [rec8("market", -3000, ticker="KXBNB15M-A", series="KXBNB15M", close_s=T8 - 1800, pool=2),
              rec8("order_sent", -1900, cid="jb-a", ticker="KXBNB15M-A", side="yes", ask=0.85, qty=5, pool=2, body=bA, close_s=T8 - 1800),
              rec8("order", -1899, cid="jb-a", ticker="KXBNB15M-A", status=201),
              rec8("fill", -1899, cid="jb-a", ticker="KXBNB15M-A", side="yes", qty=5.0, price=0.85, cost=4.25, fee=0.05, pool=2, close_s=T8 - 1800, order_id="o-a"),
              rec8("order_sent", -100, cid="jb-b", ticker="KXZEC15M-B", side="no", ask=0.80, qty=5, pool=2, body=bB, close_s=T8 - 70),
              rec8("order_sent", -8000, cid="jb-c", ticker="KXHYPE15M-C", side="yes", ask=0.85, qty=5, pool=2, body=bA, close_s=T8 - 7900),
              rec8("fill", -7999, cid="jb-c", ticker="KXHYPE15M-C", side="yes", qty=5.0, price=0.85, cost=4.25, fee=0.05, pool=2, close_s=T8 - 7900),
              rec8("settle", -7800, ticker="KXHYPE15M-C", money=-4.30, cid="jb-c"),
              rec8("order_sent", -6000, cid="jb-d", ticker="KXNEAR15M-D", side="yes", ask=0.85, qty=5, pool=2, body=bA, close_s=T8 - 5900),
              rec8("order_fail", -5999, cid="jb-d", ticker="KXNEAR15M-D", why="rejected", status=400),
              rec8("settle", -5000, ticker="KXBNB15M-E", money=-4.30, cid="jb-e"),
              rec8("settle", -4000, ticker="KXBNB15M-F", money=-4.30, cid="jb-f"),
              rec8("settle", -3000, ticker="KXBNB15M-G", money=-4.30, cid="jb-g"),
              rec8("settle", -2 * 86400, ticker="KXBNB15M-OLD", money=-9.00, cid="jb-old"),
              "garbage line"]
    with open(tmp8, "w", encoding="utf-8") as f:
        f.write("\n".join(lines8) + "\n")
    try:
        info8 = positions_from_log(tmp8)
        ck([p_["ticker"] for p_ in info8["positions"]] == ["KXBNB15M-A"] and [u["ticker"] for u in info8["unknown"]] == ["KXZEC15M-B"]
           and info8["ordered"] == {"KXBNB15M-A", "KXZEC15M-B", "KXHYPE15M-C", "KXNEAR15M-D"}
           and set(info8["settles"]) == {"KXHYPE15M-C", "KXBNB15M-E", "KXBNB15M-F", "KXBNB15M-G", "KXBNB15M-OLD"} and info8["closes"] == {"KXBNB15M-A": T8 - 1800},
           "(F8) the log replay: A filled and never settled = open position; B sent and never answered = unknown; C settled and D rejected = gone; 4 markets ordered")
        sf8 = live_sender(); wf8 = World(30, live=True, sub=3, sender=sf8, cash={2: 50.0})
        wf8.tr.restore(tmp8)
        vA = wf8.tr.held.get("KXBNB15M-A", {}); vB = wf8.tr.held.get("KXZEC15M-B", {})
        ck(vA.get("qty") == 5.0 and vA.get("px") == 0.85 and vA.get("live") and vA.get("restored") and vA.get("close_s") == T8 - 1800 and not vA.get("unknown")
           and vA.get("cid") == "jb-a",
           "(F8) restore: A is held again (5 at 0.85, its close and client id kept) so the settle task polls Kalshi for its result")
        ck(vB.get("unknown") is True and vB.get("body") == bB and vB.get("cid") == "jb-b" and not vB.get("inflight") and abs(vB.get("t_sent", 0) - (T8 - 100)) < 1
           and not wf8.tr.flat(),
           "(F8) restore: B is an unknown order again (body, client id and send time kept) so recover_unknown reads it back; not flat")
        ck({"KXBNB15M-A", "KXZEC15M-B", "KXHYPE15M-C", "KXNEAR15M-D"} <= wf8.tr.bought, "(F8) restore: every ordered market is marked bought (never a second order)")
        ck(abs(wf8.tr.day_money + 17.20) < 1e-9 and wf8.tr.halt_day == today8 and wf8.recs("day_stop") and wf8.recs("day_stop")[-1].get("restored") is True
           and wf8.recs("restored")[0]["positions"] == 1 and wf8.recs("restored")[0]["unknown"] == 1,
           "(F8) restore: today's four settles of -$4.30 = -$17.20 seed the day money and set the day stop (a settle two days ago is ignored); logged restored + day_stop")
        wf8.jump(2.5)
        ck(not sf8.posts() and wf8.recs("refused")[-1]["why"] == "day_stop" and wf8.recs("trigger")[-1]["outcome"] == "day_stop",
           "(F8) ... so the restarted bot refuses a new order today (day_stop), where before it traded again")
        wf8.tr.settle_live("KXBNB15M-A", "yes")
        sA = wf8.recs("settle")
        ck(len(sA) == 1 and abs(sA[0]["money"] - 0.70) < 1e-9 and sA[0]["restored"] is True and abs(wf8.tr.day_money + 16.50) < 1e-9,
           "(F8) the re-adopted position settles like any other (+$0.70, marked restored) and counts toward the day")
        sf8.orders.append({"client_order_id": "jb-b", "order_id": "o-b", "status": "executed", "fill_count_fp": "0.00", "remaining_count_fp": "0.00"})
        wf8.tr.recover_unknown()
        wf8.tr.settle_live("KXZEC15M-B", "no")
        ck(wf8.tr.flat() and wf8.recs("recovered")[-1]["filled"] == 0.0 and wf8.recs("settle_none"), "(F8) the unknown order read back as never filled: settle_none, flat")
        wf8.tr.settle_due(T8 + FORGET_S + 1)
        ck("KXBNB15M-A" not in wf8.tr.held and "KXZEC15M-B" not in wf8.tr.held, "(F8) settled restored positions are forgotten 20 min after their close")
        ck(positions_from_log(tmp8 + ".missing") == {"positions": [], "unknown": [], "ordered": set(), "settles": {}, "closes": {}}, "(F8) a missing log restores nothing")
        sf8d = live_sender(); wf8d = World(30, live=True, sub=3, sender=sf8d, cash={2: 50.0}, dry=True)
        ck(not wf8d.tr.held, "(F8) --dry-run holds nothing to restore")
    finally:
        os.remove(tmp8)
    # (F9) live pins the approved rule
    ck(refuses(live=True, subaccount=3, k=1.0) is not None and refuses(live=True, subaccount=3, lo=0.5) is not None and refuses(live=True, subaccount=3, hi=0.99) is not None
       and refuses(live=True, subaccount=3, fast_k=4.0) is not None and refuses(live=True, subaccount=3, series="KXBNB15M,KXBTC15M", fast_k=4.0) is not None,
       "(F9) live pins the approved rule: --k 1, --lo 0.5, --hi 0.99, --fast-k 4 and a fast coin are refused with real money: '%s'" % refuses(live=True, subaccount=3, k=1.0))
    ok9b = check_args(args(live=True, subaccount=3, k=1.0, fast_k=4.0, rule_override=True))
    ck(ok9b["max_contracts"] == 5 and "KXBTC15M" in ok9b["series"] and refuses(live=True, subaccount=3, series="KXBNB15M") is None and refuses(k=1.0) is None,
       "(F9) --rule-override allows another rule; a subset of the slow coins and paper's own flags need no override")
    # (F10) fee booking: the cent-rounded charge, never less than the formula
    sf11 = live_sender(fee_c="0.0089"); wf11 = World(30, live=True, sub=3, sender=sf11, cash={2: 50.0}); wf11.jump(2.5)
    f11 = wf11.recs("fill")[0]
    ck(abs(f11["fee"] - 0.05) < 1e-9 and abs(f11["fee_reported"] - 0.0445) < 1e-9 and abs(wf11.tr.pool_cash[2] - 45.70) < 1e-9 and f11["close_s"] == wf11.C and f11["pool"] == 2,
       "(F10) Kalshi reports 0.0089 a contract x 5 = 4.45c; the bot books the cent-rounded 5c it is charged, logs both, and the fill record carries close and pool")
    sf11b = live_sender(fee_c="0.0200"); wf11b = World(30, live=True, sub=3, sender=sf11b, cash={2: 50.0}); wf11b.jump(2.5)
    ck(abs(wf11b.recs("fill")[0]["fee"] - 0.10) < 1e-9 and Trader.book_fee(5, 0.85, None) == 0.05, "(F10) a reported fee above the formula (10c) is booked as reported; no report = the formula")
    # (F11) live trigger records name the order path's refusal
    i6 = [r["kind"] for r in w6.sent].index("no_cash")
    ck(w6.sent[i6 - 1]["kind"] == "trigger" and w6.sent[i6 - 1]["outcome"] == "no_cash", "(F11) the trigger record comes first and names the refusal; the no_cash record follows")
    ck(w5.recs("trigger")[-1]["outcome"] == "max_cost" and w16.recs("trigger")[-1]["outcome"] == "halted" and w12b.recs("trigger")[0]["outcome"] == "day_stop"
       and w4.recs("trigger")[-1]["outcome"] == "under_one_contract" and w13.recs("trigger")[-1]["outcome"] == "buy" and w.recs("trigger")[0]["outcome"] == "buy",
       "(F11) live trigger outcomes: max_cost, halted, day_stop, under_one_contract; a sent order (even one rejected) and paper say buy")
    # (F12) the end of the run waits for open positions
    sf12 = live_sender(); wf12 = World(30, live=True, sub=3, sender=sf12, cash={2: 50.0}); wf12.jump(2.5)

    async def end_grace():
        async def settle_later():
            await asyncio.sleep(0.4)
            wf12.tr.settle_live(wf12.tk, "yes")
        t_ = asyncio.ensure_future(settle_later())
        await watch_stop(wf12.tr, time.time() + 0.1, wf12.log, period=0.02, grace=5.0)
        await t_
    t0 = time.time()
    asyncio.run(end_grace())
    el12 = time.time() - t0
    ck(wf12.recs("ending") and wf12.recs("ending")[0]["open_positions"] == 1 and wf12.recs("stopped_flat") and 0.35 < el12 < 3 and wf12.tr.stopped and not wf12.recs("ending_open"),
       "(F12) at the --minutes end with a position open the run stands down (ending) and waits for the settle, then exits flat (%.2f s)" % el12)
    wp12 = World(30)
    t0 = time.time()
    asyncio.run(watch_stop(wp12.tr, time.time() + 0.1, wp12.log, period=0.02))
    ck(time.time() - t0 < 1 and wp12.recs("ending") and wp12.tr.stopped and not wp12.recs("stopped_flat"), "(F12) paper: the end is immediate")
    # (F13) the pot_empty warning
    ck(len(pot_warnings({0: None, 2: 0.0}, 3)) == 1 and pot_warnings({0: None, 2: 0.0}, 3)[0]["pool"] == 2 and not pot_warnings({0: 0.0, 2: 50.0}, 3)
       and pot_warnings({0: None, 2: None}, 3)[0]["cash"] is None and "no_cash" in pot_warnings(None, 3)[0]["msg"],
       "(F13) a pot that cannot pay in the crypto pool (2) is said out loud at start; pool 0 holding nothing is not news")
    # (F14) run_live itself, offline: fake websocket and auth modules, the order on its own thread, the live settle branch,
    #       malformed frames, a websocket drop, the end-of-run wait

    class FakeWS:
        def __init__(self, script):
            self.script, self.sent = list(script), []

        async def send(self, s):
            self.sent.append(json.loads(s))

        async def recv(self):
            if not self.script:
                await asyncio.sleep(3600)
            d_, item = self.script.pop(0)
            if d_:
                await asyncio.sleep(d_)
            if isinstance(item, BaseException):
                raise item
            return item() if callable(item) else item

    class FakeConnect:
        scripts, connects = [], 0

        def __init__(self, url, **kw):
            FakeConnect.kw = kw

        async def __aenter__(self):
            FakeConnect.connects += 1
            return FakeWS(FakeConnect.scripts.pop(0) if FakeConnect.scripts else [])

        async def __aexit__(self, *a):
            return False
    hz = {"hdr_ws": [], "get_calls": 0, "ws_at_jump": None}

    def fake_headers(m, p):
        hz["hdr_ws"].append(getattr(hz["tr"], "ws_state", {}).get("ws") is not None)
        return {}

    def fake_get(path, params=None):
        hz["get_calls"] += 1
        return 200, {"markets": []}
    fake_ws_mod = types.SimpleNamespace(connect=FakeConnect)
    fake_auth_mod = types.SimpleNamespace(headers=fake_headers, get=fake_get)
    now_i = int(time.time()); C13 = now_i + 30; TK13 = "KXBNB15M-HARNESS-00"
    v13 = [745.3]; script13 = []
    for i_, sec in enumerate(range(C13 - 431, C13 - 30)):
        v13[0] += PATTERN[i_ % len(PATTERN)]
        script13.append((0, json.dumps(print_frame(sec, v13[0]))))
    script13.append((0, json.dumps(snap_frame(TK13, ((0.80, 50.0),), ((0.15, 40.0),)))))

    def jump13():
        tr_ = hz["tr"]
        hz["ws_at_jump"] = tr_.ws_state.get("ws") is not None
        return json.dumps(print_frame(C13 - 30, v13[0] + 2.5 * tr_.sig[IID].sd()))
    script13 += [(0, jump13), (0, "[1,2,3]"),
                 (0, json.dumps({"type": "orderbook_delta", "sid": 4, "seq": 2, "msg": {"market_ticker": TK13, "side": "no", "delta_fp": "1"}})),
                 (0.1, ConnectionError("dropped"))]
    threads13 = set()

    def hsender(method, path, body, query):
        if method == "POST":
            threads13.add(threading.get_ident())
            time.sleep(0.5)                                       # a slow exchange: the loop must keep running meanwhile
            return 201, {"order_id": "oid-h", "client_order_id": body["client_order_id"], "fill_count": body["count"], "remaining_count": "0.00",
                         "average_fill_price": body["price"], "average_fee_paid": "0.0089", "ts_ms": 1}
        if path.startswith("/markets/"):
            return 200, {"market": {"ticker": path.split("/")[-1], "result": "yes"}}
        if path == "/portfolio/balance":
            return 200, {"balance_dollars": "50.70" if query.get("exchange_index") == 2 else "0.00"}
        if path == "/portfolio/orders":
            return 200, {"orders": []}
        return 200, {}
    sent13 = []; log13 = Logger(sink=sent13)
    tr13 = Trader(log13, live=True, sub=3, sender=hsender)
    tr13.pool_cash = {0: None, 2: 50.0}; tr13.line_money = 0.0
    tr13.add_market(TK13, "KXBNB15M", float(C13), 745.0, 2, "test", 2)
    hz["tr"] = tr13
    FakeConnect.scripts, FakeConnect.connects = [script13, []], 0
    global SETTLE_POLL_S, SETTLE_TICK_S, SETTLE_AFTER_S, CASH_RETRY_S
    saved13 = (SETTLE_POLL_S, SETTLE_TICK_S, SETTLE_AFTER_S, CASH_RETRY_S)
    SETTLE_POLL_S, SETTLE_TICK_S, SETTLE_AFTER_S, CASH_RETRY_S = 0.0, 0.05, -1000.0, 0.0
    STOP_FILE = os.path.join(tempfile.gettempdir(), "jumpband-harness-%d.stop" % os.getpid())
    t0 = time.time()
    try:
        asyncio.run(run_live(tr13, 0.05, log13, ["KXBNB15M"], ws_mod=fake_ws_mod, auth_mod=fake_auth_mod, grace=3.0))
    finally:
        SETTLE_POLL_S, SETTLE_TICK_S, SETTLE_AFTER_S, CASH_RETRY_S = saved13
        STOP_FILE = real
    el13 = time.time() - t0
    k13 = [r["kind"] for r in sent13]
    r13 = lambda kind: [r for r in sent13 if r["kind"] == kind]   # noqa: E731
    ck(len(r13("order")) == 1 and len(r13("fill")) == 1 and r13("fill")[0]["qty"] == 5.0 and r13("fill")[0]["price"] == 0.85 and tr13.n_orders == 1,
       "(F14) run_live offline: the warmed prints, the snapshot and a 2.5-sd jump send ONE order and book 5 at 0.85")
    ck(threads13 and threading.get_ident() not in threads13 and r13("order")[0]["rtt"] >= 0.45,
       "(F14) the POST ran on the order thread, not the loop thread (a 0.5 s exchange round trip)")
    ck(len(r13("frame_error")) == 2 and k13.index("frame_error") < k13.index("order") and k13.index("ws_down") < k13.index("order"),
       "(F14) the two malformed frames and the drop were handled WHILE the order was in flight: the loop was not blocked; a bad frame is frame_error, not a reconnect")
    ck(len(r13("ws_down")) == 1 and FakeConnect.connects == 2 and hz["hdr_ws"] == [False, False] and hz["ws_at_jump"] is True,
       "(F14) the drop reconnects once; ws_state says down while reconnecting (health would say ws_up False) and up while connected")
    ck(len(r13("settle")) == 1 and abs(r13("settle")[0]["money"] - 0.70) < 1e-9 and abs(tr13.line_money - 0.70) < 1e-9 and r13("cash")
       and r13("cash")[-1]["cash"] == {0: 0.0, 2: 50.70} and tr13.flat(),
       "(F14) the live settle branch: Kalshi's result books +$0.70, the pot is re-read ($50.70 in pool 2), flat")
    ck(r13("ending") and r13("stopped_flat") and not r13("ending_open") and not r13("task_error") and not r13("place_error") and 2.5 < el13 < 8
       and hz["get_calls"] >= 1 and tr13.dispatch is None and r13("order")[0]["outcome"] == "fill",
       "(F14) the run ends at --minutes flat (ending + stopped_flat), discovery ran, no task error; %.1f s" % el13)
    # (F15) run_live with a position Kalshi has not settled by the end: every task serves it through the grace, then ending_open

    def nsender(method, path, body, query):
        if path.startswith("/markets/"):
            return 200, {"market": {"ticker": path.split("/")[-1], "result": ""}}
        if path == "/portfolio/balance":
            return 200, {"balance_dollars": "45.70"}
        return 200, {"orders": []}
    sent15 = []; log15 = Logger(sink=sent15)
    tr15 = Trader(log15, live=True, sub=3, sender=nsender)
    tr15.pool_cash = {0: None, 2: 45.70}; tr15.line_money = 0.0
    c15 = time.time() - 100
    tr15.add_market("KXBNB15M-OPEN-00", "KXBNB15M", c15, 745.0, 2, "test", 2)
    tr15.held["KXBNB15M-OPEN-00"] = {"side": "yes", "qty": 5.0, "px": 0.85, "cost": 4.25, "fee": 0.05, "close_s": c15, "settled": False, "result": None,
                                     "money": None, "src": None, "cid": "jb-open", "sub": 3, "pool": 2, "live": True}
    hz["tr"] = tr15
    FakeConnect.scripts, FakeConnect.connects = [[]], 0
    SETTLE_POLL_S, SETTLE_TICK_S, SETTLE_AFTER_S, CASH_RETRY_S = 0.2, 0.05, -1000.0, 1000.0
    STOP_FILE = os.path.join(tempfile.gettempdir(), "jumpband-harness-%d.stop" % os.getpid())
    t0 = time.time()
    try:
        asyncio.run(run_live(tr15, 0.02, log15, ["KXBNB15M"], ws_mod=fake_ws_mod, auth_mod=fake_auth_mod, grace=1.5))
    finally:
        SETTLE_POLL_S, SETTLE_TICK_S, SETTLE_AFTER_S, CASH_RETRY_S = saved13
        STOP_FILE = real
    el15 = time.time() - t0
    k15 = [r["kind"] for r in sent15]
    polls15 = sum(1 for r in sent15 if r["kind"] == "settle_error")
    ck(2.6 <= el15 < 6 and "ending" in k15 and "ending_open" in k15 and "stopped_flat" not in k15 and not tr15.flat()
       and [r for r in sent15 if r["kind"] == "ending_open"][0]["tickers"] == ["KXBNB15M-OPEN-00"] and polls15 == 0,
       "(F15) a position Kalshi has not settled: the run stands down at 1.2 s, keeps polling through the 1.5 s grace, then exits saying ending_open (%.1f s; a restart re-adopts it)" % el15)
    print("SELFTEST", ("FAILED: %s" % fails) if fails else "PASSED", "(%d checks)" % n[0])
    return not fails


# ---------------------------------------------------------------------------------------------------- main
def main():
    global LOG, STOP_FILE
    ap = argparse.ArgumentParser(description="jump-band buyer on the 15-minute crypto markets: paper arm, or live with --live --subaccount N")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--live", action="store_true", help="send real orders (needs --subaccount N and the Kalshi key)")
    ap.add_argument("--subaccount", type=int, default=None, help="live: the pot the orders go to (1..63)")
    ap.add_argument("--dry-run", action="store_true", help="with --live: everything real except the send (logs would_order)")
    ap.add_argument("--series", default=",".join(SLOW), help="comma list (default %s)" % ",".join(SLOW))
    ap.add_argument("--k", type=float, default=K)
    ap.add_argument("--lo", type=float, default=LO)
    ap.add_argument("--hi", type=float, default=HI)
    ap.add_argument("--fast-k", type=float, default=None, help="also watch %s at k >= this, band %.2f-%.2f" % ("/".join(s[2:-3] for s in FAST), FAST_LO, FAST_HI))
    ap.add_argument("--max-contracts", type=float, default=None,
                    help="cap per buy: paper default %g; live default %d, whole number, at most %d" % (MAX_CONTRACTS, LIVE_DEFAULT_CONTRACTS, LIVE_MAX_CONTRACTS))
    ap.add_argument("--max-cost", type=float, default=MAX_COST, help="live: dollars an order may cost including the fee (default %.2f)" % MAX_COST)
    ap.add_argument("--stop-line", type=float, default=STOP_LINE, help="live: settled money that stands the bot down (default %.2f)" % STOP_LINE)
    ap.add_argument("--rule-override", action="store_true", help="live: allow --k/--lo/--hi/--fast-k/other series than the approved rule")
    ap.add_argument("--minutes", type=float, default=20160)
    ap.add_argument("--log", default=None, help="default by mode: %s / %s / %s" % (LOG, LIVE_LOG, DRY_LOG))
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    cfg = check_args(a)                                           # every refusal that needs no network, first
    if a.live and not os.path.exists(KEY_FILE):
        raise SystemExit("--live needs the Kalshi key at %s and it is not there: no key, no live run" % KEY_FILE)
    if not selftest():
        raise SystemExit("selftest failed; refusing to run")
    series, max_contracts = cfg["series"], cfg["max_contracts"]
    LOG, STOP_FILE = cfg["log"], cfg["stop_file"]
    if os.path.exists(STOP_FILE):
        raise SystemExit("stop file present: %s" % STOP_FILE)
    sender, cash, line = None, None, None
    if a.live:
        import ordercli                                           # fxtake_live.main: the signed REST sender
        try:
            pk = ordercli.load_key(KEY_FILE)
        except Exception as e:
            raise SystemExit("cannot load the Kalshi key %s: %r" % (KEY_FILE, e))

        def sender(method, path, body, query):
            return ordercli.send(ordercli.PROD, pk, KEY_ID, method, path, body=body, query=query)
        cash = read_pool_cash(sender, a.subaccount)
        if cash is None:
            raise SystemExit("subaccount %d balance unreadable in every pool; refusing" % a.subaccount)
        line = line_money_from_log(LOG)
        if a.stop_line is not None and line <= a.stop_line + 1e-9:
            with open(STOP_FILE, "w", encoding="utf-8") as f:
                f.write("stop line: $%.2f settled since the first live record is at or under $%.2f -- written at start. Delete to resume.\n"
                        % (line, a.stop_line))
            raise SystemExit("stop line: $%.2f settled since the first live record is at or under $%.2f; stop file written" % (line, a.stop_line))
    log = Logger(LOG)
    tr = Trader(log, live=a.live, k=a.k, lo=a.lo, hi=a.hi, max_contracts=max_contracts, fast_k=a.fast_k,
                sub=a.subaccount, dry=a.dry_run, sender=sender, max_cost=a.max_cost, stop_line=a.stop_line)
    restored = None
    if a.live:
        tr.pool_cash = cash
        tr.line_money = line
        if not a.dry_run:
            restored = tr.restore(LOG)                            # positions and unknown orders left by the last run; today's money
    log.write("start", pid=os.getpid(), live=a.live, paper=not a.live, dry=a.dry_run, subaccount=a.subaccount,
              max_contracts=max_contracts, live_max_contracts=LIVE_MAX_CONTRACTS, max_cost=a.max_cost if a.live else None,
              stop_line=a.stop_line if a.live else None, day_stop=DAY_STOP if a.live else None, cash=cash, line_money=line,
              series=series, index_ids=sorted({INDEX[s] for s in series}), k=a.k, lo=a.lo, hi=a.hi, fast_k=a.fast_k,
              rule_override=bool(a.rule_override) if a.live else None, restored=restored, end_grace_s=END_GRACE_S if a.live else None,
              fast_band=[FAST_LO, FAST_HI], tau=[TAU_LO, TAU_HI], sigma_window=SIGW, sigma_min=SIGMIN, max_lag_s=MAX_LAG,
              settle_wait_s=SETTLE_WAIT, cash_every_s=CASH_EVERY_S if a.live else None, minutes=a.minutes, log=LOG, stop_file=STOP_FILE,
              python=sys.version.split()[0], argv=sys.argv)
    mode = ("LIVE DRY-RUN" if a.dry_run else "LIVE") if a.live else "PAPER"
    extra = ("" if not a.live else ", subaccount %d, cash %s, max cost $%.2f, stop line $%.2f (settled so far $%.2f), day stop $%.2f"
             % (a.subaccount, ", ".join("pool %s $%s" % (p, "unreadable" if v is None else "%.2f" % v) for p, v in sorted(cash.items())),
                a.max_cost, a.stop_line, line, DAY_STOP))
    print("jumpband %s: %s, k %.1f, band %.2f-%.2f, fast-k %s, cap %g%s, %g minutes; log %s; stop file %s" % (
        mode, ",".join(series), a.k, a.lo, a.hi, a.fast_k, max_contracts, extra, a.minutes, LOG, STOP_FILE), flush=True)
    if a.live:
        for w in pot_warnings(cash, a.subaccount):
            log.write("pot_empty", **w)
            print("WARNING: " + w["msg"], flush=True)
        if restored and (restored["positions"] or restored["unknown"]):
            print("restored from the log: %d open position(s), %d unknown order(s): %s" % (restored["positions"], restored["unknown"],
                                                                                           ", ".join(restored["tickers"])), flush=True)
    try:
        asyncio.run(run_live(tr, a.minutes, log, series))
    finally:
        log.write("exit", triggers=tr.n_triggers, paper_buys=tr.n_buys, orders=tr.n_orders, fills=tr.n_fills, settled=tr.n_settled,
                  lost=tr.n_lost, money=tr.run_pnl, day_money=round(tr.day_money, 4), line_money=tr.line_money, cash=tr.pool_cash,
                  open_positions=tr.open_positions(), halted=tr.halted, stopped=tr.stopped, log_failures=log.n_failed)


def pot_warnings(cash, sub):
    """The loud line for a pot that cannot pay: the crypto pool (CRYPTO_POOL) reads unreadable or under one contract. The
    bot runs on and buys nothing until money arrives; pool 0 holding nothing is not news (no crypto market sits there)."""
    v = (cash or {}).get(CRYPTO_POOL)
    if v is not None and v >= 0.70:
        return []
    return [{"pool": CRYPTO_POOL, "subaccount": sub, "cash": v,
             "msg": "subaccount %s pool %s reads %s: every in-band jump will log no_cash until the pot is funded "
                    "(ordercli --sub-fund ... --sub-pool %d)" % (sub, CRYPTO_POOL, "unreadable" if v is None else "$%.2f" % v, CRYPTO_POOL)}]


if __name__ == "__main__":
    main()
