#!/usr/bin/env python3
"""ladder_live.py -- the clean-room locked-average LADDER, LIVE at penny size, in a Kalshi SUBACCOUNT.

Operator 2026-09-28: "I'm giving you the go ahead for that live testing. Build the penny ladder."

WHAT IT DOES
  Runs the paper ladder's decision engine unchanged (locked_average_ladder_re_paper.py: in the last
  30 s, once the 60-second settlement average has decided a side past its jump floor, rest bids at
  model-2c / -5c / -15c), and mirrors those resting bids as REAL post_only orders of ONE contract
  each, in a subaccount, on at most 3 markets per quarter-hour. The paper engine's own paper fills
  are still logged (results/ladder-live.jsonl) so live and paper fills can be compared order by order.

WHY A SUBACCOUNT
  The live bot (research/pinrun.py) reads GET /portfolio/positions with no subaccount parameter,
  which Kalshi documents as "Defaults to 0" (the primary account), and its v-safety2 check ADOPTS AND
  HEDGES any position in its series that it did not book. In a subaccount the ladder's fills are
  invisible to it. pinrun's GET /portfolio/orders (no subaccount = all subaccounts) looks rows up by
  its own exact client_order_id ("pin-..."), so the ladder's "lad-..." rows are never mistaken for its
  own. Self-trade: every ladder order carries self_trade_prevention_type=maker, and so does pinrun's,
  so an order of one that would match the other cancels the resting one instead of trading.

HARD RAILS (code, not flags)
  1 contract per order; at most 10 contracts resting + held; at most $12 committed (resting at price +
  held at cost); stop for the ET day after -$6 realized; at most 3 markets a quarter-hour; post_only
  always; refuse to start if the subaccount holds more than $25 or its balance is unreadable; stop file
  results/ladder-live.stop cancels everything and exits; at most 3 order writes a second (the live bot
  shares this API key's rate limit). --size n multiplies the contract/money rails by n (v-ladder-size).

--auto-size (v-sub-autosize, 2026-10-02; operator: "Set no limits on the sub accounts ... I want each account running
  just like the main pin"): the bid size is the subaccount's own POT -- cash + the cost of what it holds -- divided by
  $14, floored ($70 -> 5, what --size 5 runs; $140 -> 10; clamped 1..100), read at start and re-read every 60 s like
  the main bot's autosize, APPLIED ONLY WHEN NOTHING IS HELD AND NO BID RESTS (a live position or a resting bid is
  never resized), each change logged as a 'rescale' record. Day stop -20% of the pot at the day's first rescale;
  resting + held <= 70% of the pot; contracts <= 10 x size as before. NO start-balance cap in this mode (the operator's
  order); the $10 floor and the primary-account refusal stay.

    python research/cleanroom/ladder_live.py --selftest
    python research/cleanroom/ladder_live.py --subaccount N --dry-run --minutes 30
    python research/cleanroom/ladder_live.py --subaccount N --live --minutes 10080
    python research/cleanroom/ladder_live.py --subaccount 1 --live --auto-size --minutes 10080
"""
import argparse
import json
import math
import os
import queue
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import locked_average_ladder_re_paper as P      # noqa: E402

LIVE_LOG = r"C:\kals-repo\results\ladder-live.jsonl"
ORDER_LOG = r"C:\kals-repo\results\ladder-live-orders.jsonl"
STOP_FILE = r"C:\kals-repo\results\ladder-live.stop"
KEY_FILE = r"C:\kals\kalshi.pem"
KEY_ID = "5163259c-ecb0-4966-9053-0d2776cf061e"

SIZE = Decimal("1")
MAX_CONTRACTS = 10
MAX_COMMIT = 12.00
DAY_STOP = -6.00
MAX_SUB_BALANCE = 25.00


# v-sub-autosize (2026-10-02): --auto-size. The pot is the subaccount's cash + the cost of what it holds.
SIZE_MAX = 1000000                               # --size / --auto-size ceiling: effectively none (operator 10-22 "Just remove the 100 contracts cap"; was 100, before that 20)
POT_PER_CONTRACT = 14.0                          # size = floor(pot / 14): $70 -> 5 (today's size), $140 -> 10
POT_FLOOR = 10.0                                 # refuse to start under this pot (the lower sanity floor)
POT_REREAD_S = 60.0                              # the main bot's autosize cadence
DAY_STOP_FRAC, COMMIT_FRAC = 0.20, 0.70

# v-ladder-caps (IDEA_LEDGER F23, 2026-10-03): per-market and per-quarter-hour caps as multiples of the bid size
# (contracts resting + held). 0 = off (the default; the rails above are then exactly as before).
LIMBO_S = 60.0                                   # v-ladder-limbo: a failed cancel's remainder counts at most this long
MARKET_CAP_X = 0                                 # --market-cap-x 2: at most 2 bids' worth in one market
CLOSE_CAP_X = 0                                  # --close-cap-x 5: at most 5 bids' worth across one close's markets
REPLACE_WAIT_RAILS = ("max_commit", "max_contracts", "market_cap", "close_cap")   # v-ladder-replace: rails that count the bid being replaced

# v-ladder-optc (2026-10-22, operator: "Okay option c"): --coins limits which 15-minute series the ladder bids on
# (None = every coin, as before); --pot-per-contract sets the size divisor (default 14 = as before). Option C =
# NEAR/ZEC/DOGE/HYPE/XRP, pot / 7.8 a bid (9/5 of today's size: the same resting money on 5 coins instead of 9),
# --market-cap-x 1 (one bid a market). The clean-room paper ladder keeps watching all 9 coins (the shadow).
COINS = None

# v-ladder-fit (2026-10-23, operator: "Figure out the most profitable safest way to run ladder ... Make sure it grows with
# bank"): --fit sizes each bid so that EVERY rung of EVERY coin can rest at once inside the money rail:
#   size = floor(COMMIT_FRAC * pot / (n_coins * sum of the rung prices))      (5 coins, 98c+95c: pot * 0.7 / 9.65)
# so the 95c bids are never held back (the 25-day replay: $11.90/day vs $11.27 for pot/7.8 at $643, worst market
# $87 vs $158, same ceiling) and the size follows the bank on every rescale. --big-coins-above POT adds the four big
# coins (BTC ETH SOL BNB) once the pot reaches POT (the replay crosses over near $2,500) -- the coin set is re-derived
# at every rescale, with the size, so both grow with the bank.
FIT = False
BIG_COINS_ABOVE = 0.0
COINS_BASE = None                                # the --coins set; COINS is derived from it (and the pot) under --fit
TOP5 = frozenset(("KXNEAR15M", "KXZEC15M", "KXDOGE15M", "KXHYPE15M", "KXXRP15M"))


def coins_for_pot(pot):
    """The coin set for this pot: the --coins set, or every coin once the pot reaches --big-coins-above."""
    if BIG_COINS_ABOVE > 0 and pot is not None and float(pot) >= BIG_COINS_ABOVE:
        return None
    return COINS_BASE


def rung_px_sum():
    """Dollars a contract across the live rungs (98c + 95c = 1.93), from the engine's LEVELS."""
    return sum(1.0 - P.LEVELS[l] for l in LIVE_LEVELS)


def apply_size(size, pot=None):
    """v-ladder-size (2026-09-30, operator: "increase ladder"): contracts per bid, with every rail scaled by it --
    10 contracts / $12 committed / -$6 day stop per contract of size; start balance $25 + $12 per extra contract.
    v-sub-autosize: with `pot` (--auto-size) the contract rail still comes from the size, but the money rail is 70%
    of the pot, there is no start cap, and the day stop is left to AutoSize (-20% of the day's first pot)."""
    global SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE
    n = int(size)
    if not (1 <= n <= SIZE_MAX):
        raise SystemExit("--size %s is outside 1..%d" % (size, SIZE_MAX))
    SIZE = Decimal(n)
    MAX_CONTRACTS = 10 * n
    if pot is None:
        MAX_COMMIT = 12.00 * n
        DAY_STOP = -6.00 * n
        MAX_SUB_BALANCE = 25.00 + 12.00 * (n - 1)
    else:
        MAX_COMMIT = round(COMMIT_FRAC * float(pot), 2)
        MAX_SUB_BALANCE = None                   # the operator's order: no cap on what the subaccount may hold


def size_for_pot(pot):
    """pot dollars -> contracts a bid: floor(pot / POT_PER_CONTRACT) (14 unless --pot-per-contract), clamped 1..SIZE_MAX.
    Under --fit: floor(COMMIT_FRAC * pot / (n_coins * rung prices)), so every rung of every coin fits at once."""
    if FIT:
        cs = coins_for_pot(pot)
        n = len(cs) if cs is not None else 9
        return max(1, min(SIZE_MAX, int(math.floor(COMMIT_FRAC * float(pot) / (n * rung_px_sum()) + 1e-9))))
    return max(1, min(SIZE_MAX, int(math.floor(float(pot) / POT_PER_CONTRACT + 1e-9))))


def read_pot(sender, sub):
    """The subaccount's pot in dollars: cash + the cost of what it holds (Kalshi's market_exposure, the cost basis
    of each open position), or None when either read is unreadable. The unit is READ, never inferred (hard rule 5,
    as the main bot's read_bank): `balance` (cents) and `balance_dollars` must both be present and agree to a cent.
    A resting bid's collateral is not added: the size only ever changes when no bid rests, so that read is cash."""
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
    """The start checks, as a function so the self-test drives them. Fixed --size keeps the old balance cap and the
    $3 live floor; --auto-size has NO cap (the operator's order), only the $10 pot floor. The reason, or None."""
    if auto:
        if pot is None:
            return "--auto-size: the pot is unreadable"
        if float(pot) < POT_FLOOR:
            return "--auto-size: pot $%.2f is under the $%.0f floor" % (float(pot), POT_FLOOR)
        return None
    if sub_bal is None:
        return "subaccount balance unreadable"
    if sub_bal > MAX_SUB_BALANCE:
        return "subaccount holds $%.2f > $%.2f; this is a penny test" % (sub_bal, MAX_SUB_BALANCE)
    if live and sub_bal < 3.0:
        return "subaccount holds $%.2f; fund it first (ordercli --sub-fund)" % sub_bal
    return None


class AutoSize:
    """--auto-size: the pot-driven bid size. `reader()` -> pot dollars or None; `flat()` -> nothing held, no bid
    resting or queued (called under `lock`); `on_apply()` after every applied size (main keeps the paper engine's
    P.SIZE in step). tick() reads at most every POT_REREAD_S; consider() changes the size (and MAX_COMMIT) only when
    flat, sets the day stop at the day's first applied rescale, and writes a 'rescale' record on every change."""

    def __init__(self, log, reader, now, flat, lock=None, on_apply=None):
        self.log, self.reader, self.now, self.flat = log, reader, now, flat
        self.lock = lock if lock is not None else threading.Lock()
        self.on_apply = on_apply
        self.pot = self.size = self.day = self.last_read = None
        self.waiting = False
        self.reads = 0

    def _apply(self, n, pot):
        global COINS
        apply_size(n, pot=pot)
        if FIT:
            COINS = coins_for_pot(pot)              # v-ladder-fit: the coin set follows the pot with the size
        if self.on_apply is not None:
            self.on_apply()

    def start(self, pot):
        global DAY_STOP
        if pot is None or float(pot) < POT_FLOOR:
            raise SystemExit("--auto-size: pot %s is unreadable or under the $%.0f floor; refusing" % (pot, POT_FLOOR))
        self.size = size_for_pot(pot)
        self._apply(self.size, pot)
        DAY_STOP = round(-DAY_STOP_FRAC * float(pot), 2)
        self.pot, self.day, self.last_read = float(pot), et_day(self.now()), self.now()
        return self.size

    def rails(self):
        return {"size": int(SIZE), "max_contracts": MAX_CONTRACTS, "max_commit": MAX_COMMIT, "day_stop": DAY_STOP}

    def consider(self, pot, now):
        """Apply `pot` if it changes anything and nothing is open. Returns True when a rescale was applied."""
        global DAY_STOP
        new = size_for_pot(pot)
        d = et_day(now)
        if new == self.size and d == self.day:
            return False
        if not self.flat():
            if not self.waiting:
                self.waiting = True
                self.log.write("rescale_wait", old=self.size, new=new, pot=round(float(pot), 4), why="held or resting")
            return False
        old, old_rails = self.size, self.rails()
        self._apply(new, pot)
        if d != self.day:
            DAY_STOP = round(-DAY_STOP_FRAC * float(pot), 2)
            self.day = d
        self.size, self.pot, self.waiting = new, float(pot), False
        self.log.write("rescale", old=old, new=new, pot=round(float(pot), 4), old_rails=old_rails, rails=self.rails(),
                       coins=sorted(COINS) if COINS is not None else None)
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


MAX_LIVE_PER_CLOSE = 9                           # v-ladder-top (09-29): every coin (was 3 -- the first 3 markets to lock
                                                 # took the slots and never filled; all 20 paper fills were in later ones)
LIVE_LEVELS = (0,)                               # v-ladder-top: mirror only the top rung (model-2c): 16 of 20 paper fills
WRITES_PER_S = 3.0
POOL = 2
CID_PREFIX = "lad-"


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


def order_body(ticker, side, px, sub, cid):
    """side 'yes' = buy YES at px (bid px); side 'no' = buy NO at px (= sell YES: ask at 1-px)."""
    px = Decimal(str(px))
    s, p = ("bid", px) if side == "yes" else ("ask", Decimal(1) - px)
    return {"ticker": ticker, "side": s, "count": "%.2f" % SIZE, "price": "%.4f" % p,
            "time_in_force": "good_till_canceled", "self_trade_prevention_type": "maker",
            "post_only": True, "client_order_id": cid, "subaccount": int(sub), "exchange_index": POOL}


def body_ok(b, sub):
    """Every order body must carry these, or it is not sent."""
    return (b.get("post_only") is True and b.get("subaccount") == int(sub) and int(sub) >= 1
            and b.get("exchange_index") == POOL and b.get("count") == "%.2f" % SIZE
            and b.get("self_trade_prevention_type") == "maker"
            and b.get("time_in_force") == "good_till_canceled"
            and str(b.get("client_order_id", "")).startswith(CID_PREFIX)
            and 0 < float(b["price"]) < 1)


class Broker:
    def __init__(self, log, sub, dry, sender, now):
        self.log, self.sub, self.dry, self.send, self.now = log, int(sub), dry, sender, now
        self.q = queue.Queue()
        self.live = {}            # paper order id -> {kid, ticker, side, px, status, filled}
        self.live_markets = {}    # close_s -> set(tickers)
        self.deferred = set()      # v-ladder-reserve: extra bids held back (logged once each)
        self.replace_wait = set()  # v-ladder-replace: moved bids waiting for the old bid's cancel (logged once each)
        self.held = {}            # ticker -> {"side", "n", "cost"}
        self.day, self.day_pnl = None, 0.0
        self.halted = self.stopped = False
        self.lock = threading.Lock()
        self._w = []
        self.sizer = None         # AutoSize under --auto-size; its tick runs on the poller thread

    # --- exposure and rails ---
    def open_orders(self):
        return [v for v in self.live.values() if v["status"] in ("sending", "resting")]

    def limbo(self):
        """v-ladder-limbo (2026-10-03): a bid whose cancel FAILED (404 = it had already filled) is counted at its unfilled
        remainder until the fill poller has seen it finished (executed/canceled) or LIMBO_S has passed. Before this, a
        bid that filled just before its cancel counted as neither resting nor held for 0.4-2.8 s, the window in which
        NEAR's 1-s bursts of re-bids land: the contract/money rails and flat() (the auto-size gate) were blind there."""
        t = self.now()
        return [v for v in self.live.values() if v["status"] == "cancel_failed" and not v.get("terminal")
                and t < v.get("limbo_until", 0) and v["filled"] < float(SIZE)]

    def in_cancel(self):
        """v-ladder-capfix (2026-10-07): a bid whose cancel is IN FLIGHT (status 'cancelling') is counted at its unfilled
        remainder, exactly as limbo() counts a failed cancel. Before this it was counted by neither open_orders()
        (sending/resting) nor limbo() (cancel_failed): 10-06 13:44:58Z KXZEC15M bid 8593 filled at :58.08, its cancel
        was in flight until :58.255, and a third bid decided at :58.215 passed the x2 market cap -> 15 held against 10.
        It drops out when the cancel returns (-> cancelled, or -> cancel_failed and limbo() takes over: never both),
        when the poller books its fill (remainder 0, the contracts are in held), or when the poller sees it finished."""
        return [v for v in self.live.values() if v["status"] == "cancelling" and not v.get("terminal")
                and v["filled"] < float(SIZE)]

    def pending(self):
        """Bids not resting but possibly still live on Kalshi: limbo (failed cancel) + in_cancel (cancel in flight).
        The two are disjoint by status. Each counts at SIZE - filled."""
        return self.limbo() + self.in_cancel()

    def flat(self):
        """Nothing held, no bid sending/resting/cancelling/in limbo, nothing queued: the only state in which the size may change."""
        return (not any(h["n"] > 0 for h in self.held.values()) and not self.open_orders() and not self.limbo()
                and not any(v["status"] == "cancelling" for v in self.live.values()) and self.q.empty())

    def exposure(self):
        pend = self.pending()
        n = len(self.open_orders()) * float(SIZE) + sum(h["n"] for h in self.held.values())             + sum(float(SIZE) - v["filled"] for v in pend)
        c = sum(float(v["px"]) * float(SIZE) for v in self.open_orders()) + sum(h["cost"] for h in self.held.values())             + sum(float(v["px"]) * (float(SIZE) - v["filled"]) for v in pend)
        return n, c

    def market_contracts(self, ticker):
        """Contracts resting + held + cancelling/limbo remainder in one market."""
        h = self.held.get(ticker)
        return (h["n"] if h else 0) + sum(float(SIZE) for v in self.open_orders() if v["ticker"] == ticker)             + sum(float(SIZE) - v["filled"] for v in self.pending() if v["ticker"] == ticker)

    def replacing(self, ticker, desired):
        """True when a bid on `ticker` that the paper engine no longer wants (being replaced) still counts against the
        rails: resting, sending, cancelling or in limbo."""
        counted = self.open_orders() + self.pending()
        return any(v["ticker"] == ticker and q not in desired and any(v is c for c in counted)
                   for q, v in self.live.items())

    def rails_refusal(self, px, ticker=None, close_s=None):
        if self.stopped:
            return "stopped"
        if self.halted:
            return "day_stop"
        n, c = self.exposure()
        if n + float(SIZE) > MAX_CONTRACTS + 1e-9:
            return "max_contracts"
        if c + float(px) * float(SIZE) > MAX_COMMIT + 1e-9:
            return "max_commit"
        if MARKET_CAP_X and ticker is not None and                 self.market_contracts(ticker) + float(SIZE) > MARKET_CAP_X * float(SIZE) + 1e-9:
            return "market_cap"
        if CLOSE_CAP_X and close_s is not None and                 sum(self.market_contracts(t) for t in self.live_markets.get(close_s, ())) + float(SIZE)                 > CLOSE_CAP_X * float(SIZE) + 1e-9:
            return "close_cap"
        return None

    def reserve_short(self, o, ticker, live_set):
        """v-ladder-reserve (2026-10-22): C+ must never cost Option C a bid. A market's FIRST top-rung (98c) bid is
        privileged; any extra bid (the 95c rung, or a second 98c bid) is placed only if the money committed after it
        still leaves one first 98c bid (SIZE x 0.98) for every --coins market of this close not yet decided.
        True = hold this extra bid back for now."""
        if len(LIVE_LEVELS) < 2:
            return False                           # only in C+ mode (--levels 0,1); Option C is exactly as before
        first = getattr(o, "level", 0) == 0 and self.market_contracts(ticker) <= 1e-9
        if first:
            return False
        ncoins = len(COINS) if COINS is not None else 9
        reserve = 0.98 * float(SIZE) * max(0, ncoins - len(live_set))
        _n, c = self.exposure()
        return c + float(o.price) * float(SIZE) + reserve > MAX_COMMIT + 1e-9

    # --- called after every engine tick ---
    def sync(self, eng):
        if not self.stopped and os.path.exists(STOP_FILE):
            self.stopped = True
            self.log.write("stop_file", path=STOP_FILE)
        with self.lock:
            present = set()
            for m in list(eng.markets.values()):
                present.add(m.ticker)
                desired = {o.id: o for o in m.orders if o.live_to is None and getattr(o, "level", 0) in LIVE_LEVELS}
                if COINS is not None and m.ticker.split("-")[0] not in COINS:
                    desired = {}                   # v-ladder-optc: a coin outside --coins is never admitted
                live_set = self.live_markets.setdefault(m.close_s, set())
                if m.ticker not in live_set:
                    if desired and len(live_set) < MAX_LIVE_PER_CLOSE and not (self.halted or self.stopped):
                        live_set.add(m.ticker)
                        self.log.write("live_market", ticker=m.ticker, close_s=m.close_s)
                    else:
                        continue
                for pid, o in sorted(desired.items(), key=lambda kv: getattr(kv[1], "level", 0)):
                    if pid in self.live or m.done or self.halted or self.stopped:
                        continue
                    if self.reserve_short(o, m.ticker, live_set):
                        if pid not in self.deferred:
                            self.deferred.add(pid)
                            self.log.write("deferred", ticker=m.ticker, paper_id=pid, px=str(o.price),
                                           why="reserve: room kept for the first 98c bid of coins not yet decided")
                        continue                    # not marked: it is tried again next tick, when room may exist
                    why = self.rails_refusal(o.price, m.ticker, m.close_s)
                    if why in REPLACE_WAIT_RAILS and self.replacing(m.ticker, desired):
                        # v-ladder-replace (2026-10-31): the paper engine MOVED this market's bid (97.9c -> 98c is a new
                        # paper order); the old bid is still counted until its cancel lands, so the rails refused the new
                        # one for good and the old one was then cancelled: the market had NO bid (11 times 10-30, 21 on
                        # 10-29). Wait instead: tried again every tick, placed once the old bid's money is free. The rails
                        # are never exceeded.
                        if pid not in self.replace_wait:
                            self.replace_wait.add(pid)
                            self.log.write("deferred", ticker=m.ticker, paper_id=pid, px=str(o.price),
                                           why="replace: waits for the old bid's cancel (%s)" % why)
                        continue
                    if why:
                        self.live[pid] = {"kid": None, "ticker": m.ticker, "side": o.side, "px": o.price,
                                          "status": "refused", "filled": 0}
                        self.log.write("rail_refused", ticker=m.ticker, paper_id=pid, px=str(o.price), why=why)
                        continue
                    self.live[pid] = {"kid": None, "ticker": m.ticker, "side": o.side, "px": o.price,
                                      "status": "sending", "filled": 0}
                    self.q.put(("place", pid))
                for pid, v in self.live.items():
                    if v["ticker"] == m.ticker and v["status"] == "resting" and \
                            (pid not in desired or m.done or self.halted or self.stopped):
                        v["status"] = "cancelling"
                        self.q.put(("cancel", pid))
            for pid, v in self.live.items():
                if v["ticker"] not in present and v["status"] == "resting":
                    v["status"] = "cancelling"
                    self.q.put(("cancel", pid))

    # --- results ---
    def on_result(self, ticker, result):
        if result not in ("yes", "no"):
            return      # not settled yet (09-29 13:15 ET NEAR: an empty result was booked as a loss; it had won)
        with self.lock:
            h = self.held.pop(ticker, None)
            if not h or h["n"] <= 0:
                return
            pnl = (h["n"] - h["cost"]) if h["side"] == result else -h["cost"]
            d = et_day(self.now())
            if d != self.day:
                self.day, self.day_pnl = d, 0.0
            self.day_pnl += pnl
            self.log.write("live_settle", ticker=ticker, result=result, side=h["side"], n=h["n"],
                           cost=round(h["cost"], 4), pnl=round(pnl, 4), day_pnl=round(self.day_pnl, 4))
            if self.day_pnl <= DAY_STOP and not self.halted:
                self.halted = True
                self.log.write("day_stop", day=d, day_pnl=round(self.day_pnl, 4))

    def on_fill(self, pid, new_filled):
        with self.lock:
            v = self.live.get(pid)
            if v is None or new_filled <= v["filled"]:
                return
            delta = new_filled - v["filled"]
            v["filled"] = new_filled
            h = self.held.setdefault(v["ticker"], {"side": v["side"], "n": 0, "cost": 0.0})
            h["n"] += delta
            h["cost"] += delta * float(v["px"])
            self.log.write("live_fill", ticker=v["ticker"], paper_id=pid, kid=v["kid"], side=v["side"],
                           px=str(v["px"]), delta=delta, filled=new_filled)

    # --- the one writer thread ---
    def _throttle(self):
        now = time.time()
        self._w = [t for t in self._w if now - t < 1.0]
        if len(self._w) >= WRITES_PER_S:
            time.sleep(max(0.0, 1.0 - (now - self._w[0])))
        self._w.append(time.time())

    def work_once(self, item):
        kind, pid = item
        v = self.live.get(pid)
        if v is None:
            return
        if kind == "place":
            cid = "%s%d-%d" % (CID_PREFIX, int(time.time()), pid)
            b = order_body(v["ticker"], v["side"], v["px"], self.sub, cid)
            if not body_ok(b, self.sub):
                v["status"] = "refused"
                self.log.write("body_refused", body=b)
                return
            if self.dry:
                v["status"], v["kid"] = "resting", "dry-%d" % pid
                self.log.write("would_place", body=b)
                return
            self._throttle()
            st, r = self.send("POST", "/portfolio/events/orders", b, None)
            if st in (200, 201) and isinstance(r, dict):
                v["kid"] = (r.get("order") or r).get("order_id")
                v["status"] = "resting"
                self.log.write("placed", body=b, order_id=v["kid"], resp=str(r)[:200])
                try:
                    f = int(float((r.get("order") or r).get("fill_count") or 0))
                    if f:
                        self.on_fill(pid, f)
                except Exception:
                    pass
            else:
                v["status"] = "rejected"
                self.log.write("rejected", body=b, status=st, resp=str(r)[:300])
        elif kind == "cancel":
            if self.dry or not v.get("kid"):
                v["status"] = "cancelled"
                self.log.write("would_cancel" if self.dry else "cancel_skip", paper_id=pid)
                return
            self._throttle()
            st, r = self.send("DELETE", "/portfolio/events/orders/%s" % v["kid"], None,
                              {"subaccount": self.sub, "exchange_index": POOL})
            v["status"] = "cancelled" if st in (200, 201) else "cancel_failed"
            if v["status"] == "cancel_failed":
                v["limbo_until"] = self.now() + LIMBO_S
            self.log.write("cancelled", order_id=v["kid"], status=st, resp=str(r)[:200])

    def run_writer(self):
        while True:
            item = self.q.get()
            try:
                self.work_once(item)
            except Exception as e:
                self.log.write("writer_error", err=repr(e)[:300])

    def poll_fills_once(self):
        st, r = self.send("GET", "/portfolio/orders", None,
                          {"subaccount": self.sub, "min_ts": int(time.time()) - 1800, "limit": 500})
        if st != 200 or not isinstance(r, dict):
            return False
        by_kid = {v["kid"]: pid for pid, v in self.live.items() if v.get("kid")}
        for o in r.get("orders") or []:
            pid = by_kid.get(o.get("order_id"))
            if pid is None:
                continue
            try:
                self.on_fill(pid, int(float(o.get("fill_count_fp") or o.get("fill_count") or 0)))
            except Exception:
                pass
            if o.get("status") in ("executed", "canceled", "cancelled"):
                self.live[pid]["terminal"] = True      # v-ladder-limbo: finished on Kalshi -> its fills are all booked
        return True

    def run_poller(self):
        while True:
            try:
                if not self.dry and self.live:
                    self.poll_fills_once()
            except Exception as e:
                self.log.write("poll_error", err=repr(e)[:300])
            try:
                if self.sizer is not None:        # --auto-size: the 60-s pot re-read (dry run included)
                    self.sizer.tick()
            except Exception as e:
                self.log.write("sizer_error", err=repr(e)[:300])
            time.sleep(2.0)


# ---------------------------------------------------------------------------------------------------- self-test
class _M:
    def __init__(self, ticker, close_s, orders, done=False):
        self.ticker, self.close_s, self.orders, self.done = ticker, close_s, orders, done


class _O:
    def __init__(self, i, side, price, live_to=None, level=0):
        self.id, self.side, self.price, self.live_to = i, side, Decimal(str(price)), live_to
        self.level = level


class _E:
    def __init__(self, ms):
        self.markets = {m.ticker: m for m in ms}


def selftest():
    global STOP_FILE, SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE
    fails, sink = [], []
    log = P.Logger(sink=sink)
    sent = []

    def fake_send(method, path, body, query):
        sent.append((method, path, body, query))
        if method == "POST":
            return 201, {"order_id": "K%d" % len(sent), "fill_count": "0"}
        if method == "GET":
            return 200, {"orders": []}
        return 200, {}
    ck = lambda ok, m: None if ok else fails.append(m)
    # order bodies
    b1 = order_body("KXBTC15M-X", "yes", "0.978", 3, "lad-1")
    b2 = order_body("KXBTC15M-X", "no", "0.95", 3, "lad-2")
    ck(b1["side"] == "bid" and b1["price"] == "0.9780", "YES maps to bid at px")
    ck(b2["side"] == "ask" and b2["price"] == "0.0500", "NO maps to ask at 1-px")
    ck(body_ok(b1, 3) and body_ok(b2, 3), "legal bodies pass")
    ck(not body_ok(dict(b1, post_only=False), 3), "post_only stripped is refused")
    ck(not body_ok(dict(b1, subaccount=0), 3) and not body_ok(order_body("T", "yes", "0.9", 0, "lad-x"), 0),
       "the primary account (subaccount 0) is refused")
    ck(not body_ok(dict(b1, count="2.00"), 3), "2 contracts is refused")
    ck(not body_ok(dict(b1, exchange_index=0), 3), "wrong pool is refused")
    # sync places desired, caps 3 markets per close
    now = [1000.0]
    br = Broker(log, 3, False, fake_send, lambda: now[0])
    ms = [_M("T%d" % i, 2000, [_O(10 * i + j, "yes", "0.95", level=j) for j in range(3)]) for i in range(5)]
    br.sync(_E(ms))
    while not br.q.empty():
        br.work_once(br.q.get())
    placed = [s for s in sent if s[0] == "POST"]
    ck(len(br.live_markets[2000]) == 5, "v-ladder-top: every market with a top-rung order goes live (got %d)" % len(br.live_markets[2000]))
    ck(len(placed) == 5, "v-ladder-top: only the top rung (level 0) is mirrored: 5 markets x 1 (got %d)" % len(placed))
    ck(all(body_ok(p[2], 3) for p in placed), "every sent body carries subaccount + post_only")
    # rails: a 4th close's orders would exceed 10 contracts
    ms2 = ms + [_M("U%d" % i, 2900, [_O(100 + 10 * i + j, "yes", "0.95") for j in range(3)]) for i in range(2)]
    br.sync(_E(ms2))
    refused = [r for r in sink if r["ev"] == "rail_refused"]
    ck(any(r["why"] in ("max_contracts", "max_commit") for r in refused), "the 10-contract / $12 rail refuses")
    n, c = br.exposure()
    ck(n <= MAX_CONTRACTS and c <= MAX_COMMIT + 1e-9, "exposure within rails (%d, %.2f)" % (n, c))
    # a disqualified order is cancelled
    while not br.q.empty():
        br.work_once(br.q.get())
    ms[0].orders[0].live_to = 1001.0
    br.sync(_E(ms2))
    while not br.q.empty():
        br.work_once(br.q.get())
    ck(any(s[0] == "DELETE" and s[3]["subaccount"] == 3 for s in sent), "a cancelled paper order cancels live, in the subaccount")
    # a fill, then a losing settle -> day stop at -$6
    pid = next(p for p, v in br.live.items() if v["status"] == "resting")
    br.on_fill(pid, 1)
    ck(br.held and list(br.held.values())[0]["n"] == 1, "a fill is held")
    br.on_result(br.live[pid]["ticker"], "")
    ck(br.held and list(br.held.values())[0]["n"] == 1, "an empty (unsettled) result books nothing and keeps the holding")
    br.day_pnl = -5.5
    br.day = et_day(now[0])
    br.on_result(br.live[pid]["ticker"], "no")
    ck(br.halted, "a realized day at or below -$6 halts")
    # v-etclock: the ET day turns at 04:00Z in summer and 05:00Z in winter; US daylight time ends 2026-11-01 06:00Z
    _u = lambda *a: datetime(*a, tzinfo=timezone.utc).timestamp()
    ck(et_day(_u(2026, 10, 20, 3, 59)) == "2026-10-19" and et_day(_u(2026, 10, 20, 4, 0)) == "2026-10-20"
       and et_day(_u(2026, 11, 2, 4, 30)) == "2026-11-01" and et_day(_u(2026, 11, 2, 5, 0)) == "2026-11-02"
       and et_offset_s(_u(2026, 11, 1, 5, 59)) == -14400 and et_offset_s(_u(2026, 11, 1, 6, 0)) == -18000,
       "v-etclock: 04:30Z on Nov 2 is still ET day 2026-11-01 (23:30 EST); the day turns at 05:00Z once DST ends")
    before = len([s for s in sent if s[0] == "POST"])
    ms3 = [_M("V1", 3800, [_O(900, "yes", "0.95")])]
    br.sync(_E(ms3))
    while not br.q.empty():
        br.work_once(br.q.get())
    ck(len([s for s in sent if s[0] == "POST"]) == before, "no new order after the day stop")
    # stop file cancels everything
    br2 = Broker(log, 3, False, fake_send, lambda: now[0])
    ms4 = [_M("W1", 4700, [_O(1000 + j, "no", "0.97") for j in range(3)])]
    br2.sync(_E(ms4))
    while not br2.q.empty():
        br2.work_once(br2.q.get())
    open(STOP_FILE + ".selftest", "w").close()
    real = STOP_FILE
    STOP_FILE = STOP_FILE + ".selftest"
    try:
        br2.sync(_E(ms4))
        while not br2.q.empty():
            br2.work_once(br2.q.get())
    finally:
        STOP_FILE = real
        os.remove(real + ".selftest")
    ck(br2.stopped and not br2.open_orders(), "the stop file cancels every resting order")
    # empty world places nothing
    br3 = Broker(log, 3, False, fake_send, lambda: now[0])
    br3.sync(_E([]))
    ck(br3.q.empty() and not br3.live, "an empty world places nothing")
    # dry run never sends
    n_sent = len(sent)
    br4 = Broker(log, 3, True, fake_send, lambda: now[0])
    br4.sync(_E([_M("D1", 5600, [_O(2000, "yes", "0.95")])]))
    while not br4.q.empty():
        br4.work_once(br4.q.get())
    ck(len(sent) == n_sent and any(r["ev"] == "would_place" for r in sink), "dry run sends nothing")
    # v-ladder-replace: a moved bid (97.9c -> 98c) on a full rail waits for the old bid's cancel, then is placed
    _sv = (MAX_CONTRACTS, MAX_COMMIT)
    try:
        MAX_COMMIT = 0.99 * float(SIZE)                  # room for exactly one bid
        brR = Broker(log, 3, False, fake_send, lambda: now[0])
        mR = _M("R1", 7000, [_O(7001, "yes", "0.979")])
        brR.sync(_E([mR]))
        while not brR.q.empty():
            brR.work_once(brR.q.get())
        mR.orders = [_O(7001, "yes", "0.979", live_to=now[0]), _O(7002, "yes", "0.98")]
        nref = len([r for r in sink if r["ev"] == "rail_refused"])
        brR.sync(_E([mR]))
        ck(len([r for r in sink if r["ev"] == "rail_refused"]) == nref and 7002 not in brR.live
           and any(r["ev"] == "deferred" and r.get("paper_id") == 7002 and r["why"].startswith("replace")
                   for r in sink), "v-ladder-replace: the moved bid is not refused for good while the old one is counted")
        while not brR.q.empty():
            brR.work_once(brR.q.get())
        ck(brR.live[7001]["status"] == "cancelled", "v-ladder-replace: the old bid is cancelled")
        brR.sync(_E([mR]))
        while not brR.q.empty():
            brR.work_once(brR.q.get())
        n_, c_ = brR.exposure()
        ck(brR.live.get(7002, {}).get("status") == "resting" and sent[-1][2]["price"] == "0.9800"
           and c_ <= MAX_COMMIT + 1e-9, "v-ladder-replace: once the old bid is gone the 98c bid rests, inside the rail")
        mR2 = _M("R2", 7000, [_O(7101, "yes", "0.98")])
        brR.sync(_E([mR, mR2]))
        ck(brR.live.get(7101, {}).get("status") == "refused", "v-ladder-replace: a NEW market on a full rail is still refused")
    finally:
        MAX_CONTRACTS, MAX_COMMIT = _sv
    # the only write endpoints in this file are create/cancel order
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src[:src.index("# ----" + "-" * 20)]
    ck(body.count('"POST"') == 1 and '"/portfolio/subaccounts' not in body and "intra_exchange" not in body,
       "the working code has exactly one POST (create order) and no money movement")
    # v-ladder-size: size 5 -> 5-contract bodies, rails x5, and exposure counted in CONTRACTS
    _sv = (SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE)
    try:
        apply_size(1)
        ck((SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE) == (Decimal(1), 10, 12.0, -6.0, 25.0),
           "--size 1 reproduces the penny rails exactly")
        apply_size(5)
        ck((MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE) == (50, 60.0, -30.0, 73.0), "--size 5 scales every rail x5")
        b5 = order_body("KXBTC15M-X", "yes", "0.98", 3, "lad-5")
        ck(b5["count"] == "5.00" and body_ok(b5, 3) and not body_ok(dict(b5, count="1.00"), 3), "--size 5 sends 5-contract bids only")
        br5 = Broker(log, 3, False, fake_send, lambda: now[0])
        br5.sync(_E([_M("S%d" % i, 9000 + 900 * i, [_O(5000 + i, "yes", "0.98")]) for i in range(12)]))
        n5, c5 = br5.exposure()
        ck(n5 == 50 and c5 <= MAX_COMMIT + 1e-9, "--size 5: exposure counts contracts -- 10 bids of 5 = 50, the 11th refused (%s, %.2f)" % (n5, c5))
    finally:
        SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE = _sv
    # v-sub-autosize: --auto-size. NULL first: fixed --size 5 is today's rails exactly and the start cap applies.
    _sv = (SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE)
    try:
        apply_size(5)
        ck((SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE) == (Decimal(5), 50, 60.0, -30.0, 73.0),
           "NULL: --size 5 without --auto-size is today's rails exactly")
        ck(start_refusal(73.01, None, True, False) and start_refusal(73.0, None, True, False) is None
           and start_refusal(2.99, None, True, False) and start_refusal(2.99, None, False, False) is None
           and start_refusal(None, None, True, False),
           "NULL: without --auto-size the $73 start cap, the $3 live floor and the unreadable-balance refusal still apply")
        apply_size(21)
        ck(MAX_CONTRACTS == 210 and MAX_SUB_BALANCE == 265.0, "--size ceiling raised: 21 is accepted (rails x21)")
        apply_size(100)
        ck(MAX_CONTRACTS == 1000 and body_ok(order_body("T", "yes", "0.98", 3, "lad-x"), 3), "--size 100 accepted")
        try:
            apply_size(SIZE_MAX + 1)
            ck(False, "--size above SIZE_MAX must be refused")
        except SystemExit:
            pass
        ck([size_for_pot(p) for p in (70, 140, 13, 28, 69.99, 5000, 1400, 9)] == [5, 10, 1, 2, 4, 357, 100, 1],
           "size = floor(pot/14): $70 -> 5, $140 -> 10, $69.99 -> 4, floor 1, $5000 -> 357 (no 100 cap)")
        ck(start_refusal(None, 500.0, True, True) is None and start_refusal(None, 10.0, True, True) is None,
           "--auto-size: NO upper start cap ($500 starts)")
        ck(start_refusal(None, 9.99, True, True) and start_refusal(None, None, True, True),
           "--auto-size: the $10 floor and the unreadable-pot refusal stay")
        # the pot reader: unit read from both fields (hard rule 5), cost of holdings added, any unreadable piece -> None
        def pot_send(bal, pos, st=200, st2=200):
            return lambda m, p, b, q: (st, bal) if p == "/portfolio/balance" else (st2, pos)
        ck(read_pot(pot_send({"balance": 7000, "balance_dollars": "70.0000"},
                             {"market_positions": [{"ticker": "A", "position": 5, "market_exposure_dollars": "4.9000"},
                                                   {"ticker": "B", "position": -5, "market_exposure": 400}]}), 1) == 78.9,
           "pot = cash 70.00 + held 4.90 + 4.00 (cents field) = 78.90")
        ck(read_pot(pot_send({"balance": 7000, "balance_dollars": "70.0000"}, {"market_positions": []}), 1) == 70.0
           and read_pot(pot_send({"balance": 700000, "balance_dollars": "70.0000"}, {"market_positions": []}), 1) is None
           and read_pot(pot_send({"balance_dollars": "70.0000"}, {"market_positions": []}), 1) is None
           and read_pot(pot_send({"balance": 7000, "balance_dollars": "70.0000"}, {"nope": 1}), 1) is None
           and read_pot(pot_send({"balance": 7000, "balance_dollars": "70.0000"}, {"market_positions": []}, st2=500), 1) is None
           and read_pot(pot_send({"balance": 7000, "balance_dollars": "70.0000"},
                                 {"market_positions": [{"ticker": "A", "position": 1}]}), 1) is None,
           "pot: cents and dollars must agree, both present; a missing/failed/unreadable positions read is None (never 'flat')")
        # the sizer: rails at the example pots, stops as a share of the pot, the clamp, no start cap
        clk = [1_790_000_000.0]
        flat = [True]
        applied, reads = [], []
        for pot, want in ((70.0, (5, 50, 49.0, -14.0)), (140.0, (10, 100, 98.0, -28.0)), (13.0, (1, 10, 9.1, -2.6)),
                          (5000.0, (357, 3570, 3500.0, -1000.0))):
            az = AutoSize(log, lambda: None, lambda: clk[0], lambda: flat[0], on_apply=lambda: applied.append(int(SIZE)))
            az.start(pot)
            got = (az.size, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP)
            ck(got == want and SIZE == Decimal(want[0]) and MAX_SUB_BALANCE is None,
               "auto-size at pot $%.0f: (size, contracts, commit 70%%, day -20%%) = %s, want %s" % (pot, got, want))
        ck(applied == [5, 10, 1, 357], "on_apply runs with each applied size (main keeps the paper engine's SIZE in step)")
        for bad in (9.99, None):
            try:
                AutoSize(log, lambda: None, lambda: clk[0], lambda: True).start(bad)
                ck(False, "auto-size start at pot %s must refuse" % bad)
            except SystemExit:
                pass
        # cadence: one read per 60 s, not more; an unreadable pot changes nothing
        pots = [70.0]
        az = AutoSize(log, lambda: (reads.append(1), pots[0])[1], lambda: clk[0], lambda: flat[0])
        az.start(70.0)
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
        ck(len(reads) == 2 and sink[-1]["ev"] == "pot_unreadable" and az.size == 5 and MAX_COMMIT == 49.0,
           "an unreadable pot is logged and changes nothing")
        pots[0] = 70.5
        clk[0] += 60
        ck(az.tick() is False and len(sink) == n0 + 1, "a pot change that leaves floor(pot/14) alone changes nothing")
        # driven through a real Broker: a queued/resting/cancelling bid blocks, a holding blocks, flat applies
        apply_size(5, pot=70.0)
        brz = Broker(log, 3, False, fake_send, lambda: clk[0])
        pots[0] = 70.0
        az2 = AutoSize(log, lambda: pots[0], lambda: clk[0], brz.flat, brz.lock)
        az2.start(70.0)
        brz.sizer = az2
        ck(brz.flat(), "a fresh broker is flat")
        msz = [_M("Z1", clk[0] + 30, [_O(8000, "yes", "0.98")])]
        brz.sync(_E(msz))
        ck(not brz.flat(), "a bid queued (sending) is not flat")
        while not brz.q.empty():
            brz.work_once(brz.q.get())
        ck(brz.live[8000]["status"] == "resting" and not brz.flat(), "a resting bid is not flat")
        pots[0] = 140.0
        clk[0] += 60
        ck(az2.tick() is False and SIZE == Decimal(5) and MAX_COMMIT == 49.0 and sink[-1]["ev"] == "rescale_wait"
           and sink[-1]["new"] == 10, "pot $140 with a bid resting: NOT applied (rescale_wait logged), rails unchanged")
        msz[0].orders[0].live_to = clk[0]
        brz.sync(_E(msz))
        ck(not brz.flat(), "a cancel in progress is not flat")
        while not brz.q.empty():
            brz.work_once(brz.q.get())
        ck(brz.flat(), "cancelled -> flat")
        clk[0] += 60
        ck(az2.tick() is True and SIZE == Decimal(10) and (MAX_CONTRACTS, MAX_COMMIT, DAY_STOP) == (100, 98.0, -14.0)
           and sink[-1]["ev"] == "rescale" and (sink[-1]["old"], sink[-1]["new"], sink[-1]["pot"]) == (5, 10, 140.0)
           and sink[-1]["old_rails"]["size"] == 5 and sink[-1]["rails"]["size"] == 10,
           "once flat: applied -- size 10, 100 contracts, $98 committed; day stop (same day) unchanged; 'rescale' logged")
        ck(len([r for r in sink if r["ev"] == "rescale_wait"]) == 1, "the wait is logged once, not every minute")
        ms2 = [_M("Z2", clk[0] + 30, [_O(8001, "yes", "0.98")])]
        brz.sync(_E(ms2))
        while not brz.q.empty():
            brz.work_once(brz.q.get())
        ck(sent[-1][0] == "POST" and sent[-1][2]["count"] == "10.00", "the next bid is 10 contracts")
        brz.on_fill(8001, 10)
        brz.live[8001]["status"] = "cancelled"       # as after the paper order is consumed and its cancel returns
        ck(not brz.flat() and brz.held["Z2"]["n"] == 10, "10 held (no bid resting) is not flat")
        pots[0] = 70.0
        clk[0] += 60
        ck(az2.tick() is False and SIZE == Decimal(10), "pot $70 while 10 are held: NOT applied")
        brz.on_result("Z2", "yes")
        ck(brz.flat(), "settled -> flat")
        clk[0] += 60
        ck(az2.tick() is True and SIZE == Decimal(5) and MAX_COMMIT == 49.0 and DAY_STOP == -14.0,
           "settled -> the next read puts the size back to 5 ($49 committed); day stop still the day's first")
        clk[0] += 86400
        pots[0] = 140.0
        ck(az2.tick() is True and DAY_STOP == -28.0 and SIZE == Decimal(10),
           "the next ET day: day stop re-set to -20% of that day's first pot (-$28)")
    finally:
        SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE = _sv
    # v-ladder-optc: NULL first (COINS None -> both coins admitted), then --coins admits only the listed series;
    # the size divisor: $643.47 / 7.8 -> 82, / 14 -> 45 (as before)
    global COINS, POT_PER_CONTRACT
    _svc = (COINS, POT_PER_CONTRACT)
    try:
        for coins, want in ((None, {"KXNEAR15M-26OCT221200-00", "KXBTC15M-26OCT221200-00"}),
                            (frozenset({"KXNEAR15M", "KXZEC15M"}), {"KXNEAR15M-26OCT221200-00"})):
            COINS = coins
            bco = Broker(log, 3, False, fake_send, lambda: now[0])
            bco.sync(_E([_M("KXNEAR15M-26OCT221200-00", 9500, [_O(95000, "yes", "0.98")]),
                         _M("KXBTC15M-26OCT221200-00", 9500, [_O(95001, "no", "0.98")])]))
            got = {v["ticker"] for v in bco.live.values() if v["status"] == "sending"}
            ck(got == want, "optc: coins %s -> bids on %s (got %s)" % (sorted(coins) if coins else "all", sorted(want), sorted(got)))
        COINS = frozenset({"KXNEAR15M"})
        bco2 = Broker(log, 3, False, fake_send, lambda: now[0])
        bco2.sync(_E([_M("KXBTC15M-26OCT221215-15", 9600, [_O(96000, "yes", "0.98")])]))
        ck(not bco2.live_markets.get(9600), "optc: an excluded coin never takes a live-market slot")
        POT_PER_CONTRACT = 7.8
        ck(size_for_pot(643.47) == 82 and size_for_pot(93.47) == 11 and size_for_pot(2000) == 256 and size_for_pot(20000) == 2564,
           "optc: pot / 7.8 -> 82 at $643.47, 11 at $93.47, 256 at $2,000, 2,564 at $20,000 (no 100 cap)")
        POT_PER_CONTRACT = 14.0
        ck(size_for_pot(643.47) == 45 and size_for_pot(93.47) == 6, "optc NULL: pot / 14 -> 45 and 6 as before")
        # v-ladder-fit: size = floor(0.7 * pot / (coins * rung prices)); the coin set and the size follow the pot
        global FIT, BIG_COINS_ABOVE, COINS_BASE, LIVE_LEVELS
        _svf = (FIT, BIG_COINS_ABOVE, COINS_BASE, LIVE_LEVELS, COINS)
        try:
            FIT, BIG_COINS_ABOVE, COINS_BASE, LIVE_LEVELS = True, 0.0, TOP5, (0, 1)
            ck(size_for_pot(643.47) == 46 and size_for_pot(93.47) == 6 and size_for_pot(2499) == 181,
               "fit: 5 coins 98c+95c at 70%% -> 46 at $643.47 (46 x 9.65 = $444 of $450), 6 at $93.47, 181 at $2,499 (got %s)"
               % [size_for_pot(p) for p in (643.47, 93.47, 2499)])
            LIVE_LEVELS = (0,)
            ck(size_for_pot(643.47) == 91, "fit: 98c only -> 91 at $643.47 (91 x 4.90 = $446)")
            LIVE_LEVELS = (0, 1)
            BIG_COINS_ABOVE = 2500.0
            ck(coins_for_pot(2499) == TOP5 and coins_for_pot(2500) is None and size_for_pot(2499) == 181 and size_for_pot(3000) == 120,
               "fit: --big-coins-above 2500 -> 5 coins / 181 at $2,499, every coin / 120 at $3,000 (9 x 1.93 x 120 = $2,084 of $2,100)")
            applied = []
            clk = [0.0]
            azf = AutoSize(log, lambda: None, lambda: clk[0], lambda: True, on_apply=lambda: applied.append((int(SIZE), sorted(COINS) if COINS else "all")))
            azf.start(643.47)
            clk[0] += 61.0
            azf.consider(3000.0, clk[0])
            ck(applied == [(46, sorted(TOP5)), (120, "all")],
               "fit: a rescale from $643 to $3,000 switches the size 46 -> 120 AND the coins 5 -> all (got %s)" % applied)
            ck(COINS is None and MAX_COMMIT == 2100.0, "fit: after the rescale COINS is every coin and the money rail is 70%% of $3,000")
        finally:
            FIT, BIG_COINS_ABOVE, COINS_BASE, LIVE_LEVELS, COINS = _svf
            apply_size(5)
        # v-ladder-cplus: --levels 0,1 mirrors the 98c AND the 95c rung (never the 85c one); default 0 = top only
        _svl = LIVE_LEVELS                       # (global LIVE_LEVELS is declared in the fit block above)
        try:
            COINS = None
            for lv, want in (((0,), 1), ((0, 1), 2)):
                LIVE_LEVELS = lv
                bcp = Broker(log, 3, False, fake_send, lambda: now[0])
                bcp.sync(_E([_M("KXNEAR15M-26OCT221230-30", 9700, [_O(97000 + j, "yes", ("0.98", "0.95", "0.85")[j], level=j)
                                                                   for j in range(3)])]))
                got = sorted(v["px"] for v in bcp.live.values() if v["status"] == "sending")
                ck(len(got) == want and "0.85" not in [str(x) for x in got],
                   "cplus: levels %s -> %d bid(s) a market, never the 85c rung (got %s)" % (list(lv), want, got))
            # v-ladder-reserve: at $643.47 (size 82, $450.43 committable) the 95c rung never takes the money a later
            # coin's first 98c bid needs; with plenty of money (NULL) both rungs go up at once
            _svs = (SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE)
            try:
                LIVE_LEVELS, COINS = (0, 1), frozenset(("KXNEAR15M", "KXZEC15M", "KXDOGE15M", "KXHYPE15M", "KXXRP15M"))
                for pot, want_first, want_all in ((643.47, ["0.98"], ["0.98"] * 5), (5000.0, ["0.95", "0.98"], None)):
                    apply_size(82, pot=pot)
                    brr = Broker(log, 3, False, fake_send, lambda: now[0])
                    cs = sorted(COINS)
                    mk = lambda i: _M("%s-26OCT221300-00" % cs[i], 9800, [_O(98000 + 10 * i, "yes", "0.98", level=0),
                                                                         _O(98001 + 10 * i, "yes", "0.95", level=1)])
                    brr.sync(_E([mk(0)]))
                    got = sorted(str(v["px"]) for v in brr.live.values() if v["status"] == "sending")
                    ck(got == want_first, "reserve: pot $%.0f, first coin decided -> bids %s (got %s)" % (pot, want_first, got))
                    if want_all:
                        brr.sync(_E([mk(i) for i in range(5)]))
                        got = sorted(str(v["px"]) for v in brr.live.values() if v["status"] == "sending")
                        ck(got == want_all and not any(v["status"] == "refused" for v in brr.live.values()),
                           "reserve: all 5 coins decided -> every coin gets its 98c bid, none refused (got %s)" % got)
            finally:
                SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE = _svs
        finally:
            LIVE_LEVELS = _svl
    finally:
        COINS, POT_PER_CONTRACT = _svc
    # v-ladder-caps (F23): NULL first -- caps off places exactly what it did before; then 2x per market, 5x per close
    global MARKET_CAP_X, CLOSE_CAP_X
    _sv = (SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE, MARKET_CAP_X, CLOSE_CAP_X)
    try:
        apply_size(5)

        def world(n_mk, close_s):
            return [_M("C%d-%d" % (close_s, i), close_s, [_O(close_s * 10 + i, "yes", "0.98")]) for i in range(n_mk)]
        for mx, cx, want in ((0, 0, 7), (2, 5, 5), (0, 3, 3)):
            MARKET_CAP_X, CLOSE_CAP_X = mx, cx
            brc = Broker(log, 3, False, fake_send, lambda: now[0])
            brc.sync(_E(world(7, 7000 + mx + cx)))
            got = len([v for v in brc.live.values() if v["status"] == "sending"])
            ck(got == want, "caps market x%d / close x%d: 7 markets in one close -> %d bids placed (got %d)" % (mx, cx, want, got))
        ck(any(r["ev"] == "rail_refused" and r["why"] == "close_cap" for r in sink), "the close cap logs why=close_cap")
        MARKET_CAP_X, CLOSE_CAP_X = 2, 0
        brm = Broker(log, 3, False, fake_send, lambda: now[0])
        mm = [_M("M1", 7700, [_O(77000, "yes", "0.98")])]
        brm.sync(_E(mm))
        while not brm.q.empty():
            brm.work_once(brm.q.get())
        brm.on_fill(77000, 5)                         # first bid filled, a re-bid comes
        brm.live[77000]["status"] = "cancelled"
        mm[0].orders = [_O(77001, "yes", "0.98")]
        brm.sync(_E(mm))
        ck(brm.live[77001]["status"] == "sending", "market cap x2: 5 held + a 2nd bid of 5 = 10 is allowed")
        while not brm.q.empty():
            brm.work_once(brm.q.get())
        brm.on_fill(77001, 5)
        brm.live[77001]["status"] = "cancelled"
        mm[0].orders = [_O(77002, "yes", "0.98")]
        brm.sync(_E(mm))
        ck(brm.live[77002]["status"] == "refused" and sink[-1]["why"] == "market_cap",
           "market cap x2: 10 held -> the 3rd bid is refused with why=market_cap")
        ck(brm.market_contracts("M1") == 10 and brm.market_contracts("nope") == 0, "market_contracts counts held + resting")
        # v-ladder-limbo: the 10-03 shape -- a bid fills, its cancel 404s, the poller has not seen the fill yet
        clkl = [5000.0]

        def send404(method, path, body, query):
            if method == "DELETE":
                return 404, {"error": "not_found"}
            return fake_send(method, path, body, query)
        brl = Broker(log, 3, False, send404, lambda: clkl[0])
        ml = [_M("L1", 7800, [_O(78000, "yes", "0.98")])]
        brl.sync(_E(ml))
        while not brl.q.empty():
            brl.work_once(brl.q.get())
        ml[0].orders = [_O(78001, "yes", "0.98")]          # paper consumed 78000 (filled); a re-bid one second later
        brl.sync(_E(ml))
        while not brl.q.empty():                            # places 78001; the cancel of 78000 -> 404
            brl.work_once(brl.q.get())
        ck(brl.live[78000]["status"] == "cancel_failed" and brl.exposure()[0] == 10 and not brl.flat()
           and brl.market_contracts("L1") == 10,
           "a 404 cancel keeps its 5 counted (5 limbo + the 5 re-bid = 10) and the broker is NOT flat")
        mm2 = [_M("L1", 7800, [_O(78002, "yes", "0.98")])]
        brl.sync(_E(mm2))
        ck(brl.live.get(78002, {}).get("status") in (None, "refused") and brl.market_contracts("L1") <= 10,
           "market cap x2 sees the limbo bid: a 3rd bid is not placed (v-ladder-replace: it waits, rails re-checked)")
        brl.on_fill(78000, 5)
        ck(not brl.limbo() and brl.held["L1"]["n"] == 5, "once the poller books the fill the limbo remainder is 0 (no double count)")
        brl2 = Broker(log, 3, False, send404, lambda: clkl[0])
        brl2.sync(_E([_M("L2", 7900, [_O(79000, "yes", "0.98")])]))
        while not brl2.q.empty():
            brl2.work_once(brl2.q.get())
        brl2.live[79000]["status"] = "cancelling"
        brl2.work_once(("cancel", 79000))
        ck(brl2.limbo(), "a failed cancel with nothing filled is in limbo")
        brl2.live[79000]["terminal"] = True
        ck(not brl2.limbo() and brl2.flat(), "the poller saw it finished (canceled) -> out of limbo, flat")
        brl2.live[79000]["terminal"] = False
        clkl[0] += LIMBO_S + 1
        ck(not brl2.limbo() and brl2.flat(), "limbo expires after LIMBO_S, so a vanished order can never wedge the rails")
        # v-ladder-capfix: the 10-06 KXZEC15M shape -- 5 held, bid A resting, paper consumes A (cancel queued, in flight),
        # a re-bid on the same market is decided on a LATER tick before A's cancel has returned
        MARKET_CAP_X, CLOSE_CAP_X = 2, 0
        brz = Broker(log, 3, False, fake_send, lambda: now[0])
        brz.held["Z1"] = {"side": "yes", "n": 5, "cost": 4.9}
        mz = [_M("Z1", 8600, [_O(86000, "yes", "0.98")])]
        brz.sync(_E(mz))
        while not brz.q.empty():
            brz.work_once(brz.q.get())                      # A (86000) resting: 5 held + 5 resting = 10
        mz[0].orders = []                                   # paper consumed A -> its cancel is queued, NOT yet sent
        brz.sync(_E(mz))
        ck(brz.live[86000]["status"] == "cancelling" and brz.market_contracts("Z1") == 10
           and brz.exposure()[0] == 10 and abs(brz.exposure()[1] - (4.9 + 0.98 * 5)) < 1e-9,
           "capfix: a cancelling bid counts at its remainder (5 held + 5 cancelling = 10 contracts, $9.80)")
        mz[0].orders = [_O(86001, "yes", "0.98")]           # the re-bid arrives before the cancel completes
        brz.sync(_E(mz))
        ck(86001 not in brz.live and sink[-1].get("ev") == "deferred" and "market_cap" in sink[-1].get("why", ""),
           "capfix + v-ladder-replace: a re-bid while A's cancel is in flight is NOT placed (it waits on market_cap)")
        brz.on_fill(86000, 5)                               # Kalshi had filled A; the poller books it mid-cancel
        ck(brz.market_contracts("Z1") == 10 and brz.exposure()[0] == 10 and not brz.in_cancel(),
           "capfix: once A's fill is booked mid-cancel its remainder is 0 -> held 10, no double count")
        brz.sync(_E(mz))
        ck(brz.live[86001]["status"] == "refused" and sink[-1].get("why") == "market_cap",
           "capfix: A had filled -> the re-bid is refused with why=market_cap (was 15), never placed")
        brz2 = Broker(log, 3, False, fake_send, lambda: now[0])
        mz2 = [_M("Z2", 8700, [_O(87000, "yes", "0.98")])]
        brz2.sync(_E(mz2))
        while not brz2.q.empty():
            brz2.work_once(brz2.q.get())
        brz2.on_fill(87000, 2)                              # A partly filled (2 of 5) before the paper consumed it
        mz2[0].orders = []
        brz2.sync(_E(mz2))
        ck(brz2.market_contracts("Z2") == 5 and brz2.exposure()[0] == 5,
           "capfix: a partly filled cancelling bid counts SIZE - filled (2 held + 3 remainder = 5)")
        brz2.work_once(brz2.q.get())                        # the cancel returns 200 -> cancelled
        ck(brz2.live[87000]["status"] == "cancelled" and not brz2.pending() and brz2.market_contracts("Z2") == 2
           and brz2.exposure()[0] == 2,
           "capfix: once the cancel completes the remainder drops out (2 held only)")
        brz2.live[87000]["status"] = "cancelling"           # a cancel the poller has seen finished on Kalshi
        brz2.live[87000]["terminal"] = True
        ck(not brz2.in_cancel() and brz2.market_contracts("Z2") == 2, "capfix: a terminal cancelling bid is not counted")
        brz2.live[87000]["status"] = "cancelled"
        brz2.live[87000]["terminal"] = False
        mz2[0].orders = [_O(87001, "yes", "0.98")]
        brz2.sync(_E(mz2))
        ck(brz2.live[87001]["status"] == "sending", "capfix: after the cancel completed a re-bid (2 + 5 <= 10) is placed")
        brz3 = Broker(log, 3, False, send404, lambda: now[0])   # cancelling -> cancel_failed: counted once, not twice
        mz3 = [_M("Z3", 8800, [_O(88000, "yes", "0.98")])]
        brz3.sync(_E(mz3))
        while not brz3.q.empty():
            brz3.work_once(brz3.q.get())
        mz3[0].orders = []
        brz3.sync(_E(mz3))
        c_in = brz3.market_contracts("Z3")
        brz3.work_once(brz3.q.get())                        # DELETE 404 -> cancel_failed, limbo takes over
        ck(c_in == 5 and brz3.live[88000]["status"] == "cancel_failed" and len(brz3.pending()) == 1
           and brz3.market_contracts("Z3") == 5 and brz3.exposure()[0] == 5,
           "capfix: cancelling -> cancel_failed hands the remainder to limbo once (5 before, 5 after, never 10)")
        # NULL: with nothing cancelling the counts are the pre-fix formula exactly, and with the cap off the re-bid places
        brn = Broker(log, 3, False, fake_send, lambda: now[0])
        brn.held["N1"] = {"side": "yes", "n": 5, "cost": 4.9}
        brn.sync(_E([_M("N1", 8900, [_O(89000, "yes", "0.98")]), _M("N2", 8900, [_O(89001, "yes", "0.97")])]))
        while not brn.q.empty():
            brn.work_once(brn.q.get())
        oldn = len(brn.open_orders()) * float(SIZE) + sum(h["n"] for h in brn.held.values()) \
            + sum(float(SIZE) - v["filled"] for v in brn.limbo())
        oldmc = 5 + sum(float(SIZE) for v in brn.open_orders() if v["ticker"] == "N1")
        ck(not brn.in_cancel() and brn.exposure()[0] == oldn == 15 and brn.market_contracts("N1") == oldmc == 10,
           "capfix NULL: nothing cancelling -> exposure and market_contracts equal the pre-fix formula")
        MARKET_CAP_X = 0
        brz4 = Broker(log, 3, False, fake_send, lambda: now[0])
        brz4.held["Z4"] = {"side": "yes", "n": 5, "cost": 4.9}
        mz4 = [_M("Z4", 9000, [_O(90000, "yes", "0.98")])]
        brz4.sync(_E(mz4))
        while not brz4.q.empty():
            brz4.work_once(brz4.q.get())
        mz4[0].orders = []
        brz4.sync(_E(mz4))
        mz4[0].orders = [_O(90001, "yes", "0.98")]
        brz4.sync(_E(mz4))
        ck(brz4.live[90001]["status"] == "sending", "capfix NULL: market cap off -> the same re-bid is placed as before")
    finally:
        SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE, MARKET_CAP_X, CLOSE_CAP_X = _sv
    print("ladder_live self-test " + ("PASSED" if not fails else "FAILED: " + "; ".join(fails)))
    return not fails


# ---------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--subaccount", type=int)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--minutes", type=float, default=10080)
    ap.add_argument("--size", type=int, default=1, help="contracts per bid (default 1); every rail scales with it")
    ap.add_argument("--auto-size", action="store_true",
                    help="v-sub-autosize: size = floor(the subaccount's pot / 14) (1..100), re-read every 60 s and applied "
                         "only when nothing is held and no bid rests; day stop -20%% / 70%% committed of the pot; no start "
                         "cap. --size is ignored with it.")
    ap.add_argument("--market-cap-x", type=float, default=0,
                    help="v-ladder-caps (F23): at most this many bids' worth (x size) resting+held in one market; 0 = off")
    ap.add_argument("--close-cap-x", type=float, default=0,
                    help="v-ladder-caps (F23): at most this many bids' worth across one quarter-hour's markets; 0 = off")
    ap.add_argument("--coins", default="",
                    help="v-ladder-optc: comma list of 15-minute series to bid on (e.g. KXNEAR15M,KXZEC15M); empty = all")
    ap.add_argument("--levels", default="0",
                    help="v-ladder-cplus: paper rungs to mirror live: 0 = the model-2c bid (98c, default), 0,1 = also "
                         "the model-5c bid (95c). Pair 0,1 with --market-cap-x 2 (one bid of each a market)")
    ap.add_argument("--pot-per-contract", type=float, default=14.0,
                    help="v-ladder-optc: --auto-size bid = floor(pot / this) (default 14 = unchanged)")
    ap.add_argument("--fit", action="store_true",
                    help="v-ladder-fit: size each bid so every rung of every coin fits in the money rail at once "
                         "(floor(commit_frac x pot / (coins x rung prices))); replaces --pot-per-contract")
    ap.add_argument("--big-coins-above", type=float, default=0.0,
                    help="v-ladder-fit: with --fit, bid on every coin (adds BTC ETH SOL BNB) once the pot reaches this many "
                         "dollars (the replay crosses over near 2500); 0 = never")
    ap.add_argument("--rung1-offset", type=float, default=0.05,
                    help="v-ladder-rung97 (candidate, 10-23 tape study): the second rung's distance under the model price "
                         "(default 0.05 = the paper's 95c rung; 0.03 = a 97c rung). Only the live engine's LEVELS change; "
                         "the paper shadow keeps 0.05")
    ap.add_argument("--commit-frac", type=float, default=0.70,
                    help="v-ladder-fit: share of the pot that may rest in bids + be held (default 0.70 = unchanged). "
                         "1.0 with --pot-per-contract 10 lets every rung of every coin rest at once at $643")
    a = ap.parse_args()
    global COINS, POT_PER_CONTRACT, COMMIT_FRAC
    coins = None
    if a.coins.strip():
        coins = frozenset(x.strip().upper() for x in a.coins.split(",") if x.strip())
        if not all(c.startswith("KX") and c.endswith("15M") for c in coins):
            raise SystemExit("--coins takes 15-minute series like KXNEAR15M; got %s" % sorted(coins))
    if not (4.0 <= a.pot_per_contract <= 100.0):
        raise SystemExit("--pot-per-contract %s is outside 4..100" % a.pot_per_contract)
    if not (0.5 <= a.commit_frac <= 1.0):
        raise SystemExit("--commit-frac %s is outside 0.5..1.0" % a.commit_frac)
    if not (0.021 <= a.rung1_offset <= 0.149):
        raise SystemExit("--rung1-offset %s is outside 0.021..0.149 (must sit between the 98c and 85c rungs)" % a.rung1_offset)
    if a.big_coins_above and not a.fit:
        raise SystemExit("--big-coins-above needs --fit")
    if a.big_coins_above and not (500.0 <= a.big_coins_above <= 1000000.0):
        raise SystemExit("--big-coins-above %s is outside 500..1000000" % a.big_coins_above)
    if a.fit and not a.auto_size:
        raise SystemExit("--fit needs --auto-size")
    if not selftest() or not P.selftest():
        raise SystemExit("self-test failed; refusing to run")
    COINS, POT_PER_CONTRACT = coins, float(a.pot_per_contract)      # set after the self-test (it assumes the defaults)
    COMMIT_FRAC = float(a.commit_frac)                               # v-ladder-fit: likewise (apply_size reads it at each rescale)
    if abs(a.rung1_offset - 0.05) > 1e-9:                            # v-ladder-rung97: the engine reads LEVELS at every decision
        P.LEVELS = (P.LEVELS[0], float(a.rung1_offset), P.LEVELS[2])
    global FIT, BIG_COINS_ABOVE, COINS_BASE
    FIT, BIG_COINS_ABOVE, COINS_BASE = bool(a.fit), float(a.big_coins_above), coins
    if FIT:
        COINS = coins_for_pot(None)                                  # the start pot is read below; AutoSize.start re-derives
    global LIVE_LEVELS
    lv = tuple(sorted({int(x) for x in a.levels.split(",") if x.strip()}))
    if not lv or not set(lv) <= {0, 1}:
        raise SystemExit("--levels takes 0 or 0,1; got %s" % a.levels)
    LIVE_LEVELS = lv
    if a.selftest:
        n643 = size_for_pot(643.47)
        rung_px = {0: 1.0 - P.LEVELS[0], 1: 1.0 - P.LEVELS[1]}
        need = n643 * (len(COINS) if COINS else 9) * sum(rung_px[l] for l in LIVE_LEVELS)
        print("argv: coins %s, %s -> $643.47 bids %d, levels %s (rungs %s), market_cap_x %s, commit_frac %s "
              "(every rung of every coin at once = $%.0f vs $%.0f allowed: %s)" % (
                  sorted(COINS) if COINS else "all",
                  "fit (big coins above $%.0f)" % BIG_COINS_ABOVE if FIT else "pot_per_contract %s" % POT_PER_CONTRACT,
                  n643, list(LIVE_LEVELS), " ".join("%dc" % round(100 * rung_px[l]) for l in LIVE_LEVELS), a.market_cap_x,
                  COMMIT_FRAC, need, COMMIT_FRAC * 643.47, "all fit" if need <= COMMIT_FRAC * 643.47 else "NOT all fit"))
        if FIT:
            for p in (643.47, 1000, 2000, 2499, 2500, 3000, 5000):
                cs = coins_for_pot(p)
                print("   fit at $%5.0f: %d coins, %d a bid" % (p, len(cs) if cs else 9, size_for_pot(p)))
    if a.selftest:
        return 0
    if not a.subaccount or a.subaccount < 1:
        raise SystemExit("--subaccount N (1..63) is required; the primary account is refused")
    if not a.auto_size:
        apply_size(a.size)
    global MARKET_CAP_X, CLOSE_CAP_X
    MARKET_CAP_X, CLOSE_CAP_X = a.market_cap_x, a.close_cap_x
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
    for _try in range(5 if a.auto_size else 0):    # v-ladder-optc: the start read retries (429s right after maintenance)
        time.sleep(2.0)
        pot = read_pot(sender, a.subaccount)
        if pot is not None:
            break
    why = start_refusal(sub_bal, pot, a.live, a.auto_size)
    if why:
        raise SystemExit(why + " -- refusing")
    if os.path.exists(STOP_FILE):
        raise SystemExit("stop file present: %s" % STOP_FILE)
    P.NAME, P.LOG_PATH = "ladder_live", LIVE_LOG
    olog = P.Logger(ORDER_LOG)
    br = Broker(olog, a.subaccount, a.dry_run, sender, time.time)
    auto = None
    if a.auto_size:
        br.sizer = AutoSize(olog, lambda: read_pot(sender, a.subaccount), time.time, br.flat, br.lock,
                            on_apply=lambda: setattr(P, "SIZE", SIZE))
        br.sizer.start(pot)                        # sets SIZE and every rail from the pot; refuses under $10
        auto = {"pot_per_contract": POT_PER_CONTRACT, "size_max": SIZE_MAX, "reread_s": POT_REREAD_S,
                "day_stop_frac": DAY_STOP_FRAC, "commit_frac": COMMIT_FRAC}
    P.SIZE = SIZE
    olog.write("start", pid=os.getpid(), subaccount=a.subaccount, live=a.live, sub_balance=sub_bal,
               auto_size=bool(a.auto_size), pot=pot, auto=auto,
               rails={"size": int(SIZE), "max_contracts": MAX_CONTRACTS, "max_commit": MAX_COMMIT, "day_stop": DAY_STOP,
                      "start_cap": MAX_SUB_BALANCE, "max_live_per_close": MAX_LIVE_PER_CLOSE,
                      "live_levels": list(LIVE_LEVELS), "levels_offsets": list(P.LEVELS), "writes_per_s": WRITES_PER_S,
                      "fit": FIT, "big_coins_above": BIG_COINS_ABOVE,
                      "market_cap_x": MARKET_CAP_X, "close_cap_x": CLOSE_CAP_X,
                      "coins": sorted(COINS) if COINS is not None else None, "pot_per_contract": POT_PER_CONTRACT})
    threading.Thread(target=br.run_writer, daemon=True).start()
    threading.Thread(target=br.run_poller, daemon=True).start()
    orig_tick, orig_res = P.Engine.tick, P.Engine.on_result

    def tick(self):
        orig_tick(self)
        br.sync(self)
        if br.stopped and not br.open_orders() and br.q.empty():
            olog.write("exit", why="stop file")
            os._exit(0)

    def on_result(self, ticker, result, ev, now):
        orig_res(self, ticker, result, ev, now)
        br.on_result(ticker, result)
    P.Engine.tick, P.Engine.on_result = tick, on_result
    P.Logger(LIVE_LOG).write("selftest", passed=True, checks=0)
    P.run_live(a.minutes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
