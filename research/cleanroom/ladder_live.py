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
SETTLE_RETRY_S = 60.0                            # v-ladder-settlemiss: a held market the engine gave up on is looked up at most this often
START_TRIES, START_BACKOFF_S = 5, 1.2            # v-ladder-start429: the start balance read = 1 try + 4 retries, 1.2 s apart
MARKET_CAP_X = 0                                 # --market-cap-x 2: at most 2 bids' worth in one market
CLOSE_CAP_X = 0                                  # --close-cap-x 5: at most 5 bids' worth across one close's markets
REPLACE_WAIT_RAILS = ("max_commit", "max_contracts", "market_cap", "close_cap")   # v-ladder-replace: rails that count the bid being replaced

# v-ladder-rail100 (2026-11-14; the operator allows the money change only if "you can track the result of each change vs
# if it never was implemented"): the money rail goes from 82% of the pot (--fit --commit-frac 0.82, live since 10-31) to
# 100% (--pot-per-contract 5.9756 --commit-frac 1.0: the same bid size, floor(pot / 5.9756) = floor(0.82 x pot / 4.90),
# so 6 bids of 98c a close fit instead of 5). NOTHING about what is placed changes here: each bid the rails admit is also
# checked against the OLD rail -- round(0.82 x the same pot, 2), as apply_size rounds MAX_COMMIT -- and the answer rides
# on its 'placed' record (over_82 true/false, old_limit = that 0.82 x pot figure) and on every 'live_fill' of it, so
# botdata/fixes.py (change O on the phone's /fixes) can price exactly the bids the old limit would have refused. The
# money the old rail sees is the OLD WORLD's: today's exposure less what the over-82 bids themselves rest, hold or have
# in a cancel (those bids never existed under 0.82). Counting them would mark a moved 97.9c -> 98c re-bid of one of the
# first five markets as over 82% once the 6th bid rests, and price the same extra bid twice. A MOVED bid is judged as
# the old world placed it: under 0.82 a move on a full rail WAITED for the old bid's cancel (v-ladder-replace) and was
# then placed, so the old bid(s) it replaces are left out of its own check (their fills stay counted); and while such a
# move, placed at once by the new rail, still has its old bid counted, the move itself is left out of the old world's
# money (under 0.82 it was still waiting) -- else every ordinary move with five bids resting would read over 82%.
RAIL100_OLD_FRAC = 0.82
COMMIT_POT = None                                # the pot MAX_COMMIT was last set from (apply_size(pot=)); None under --size

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
    global SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE, COMMIT_POT
    n = int(size)
    if not (1 <= n <= SIZE_MAX):
        raise SystemExit("--size %s is outside 1..%d" % (size, SIZE_MAX))
    SIZE = Decimal(n)
    MAX_CONTRACTS = 10 * n
    if pot is None:
        MAX_COMMIT = 12.00 * n
        DAY_STOP = -6.00 * n
        MAX_SUB_BALANCE = 25.00 + 12.00 * (n - 1)
        COMMIT_POT = None                        # v-ladder-rail100: a fixed rail is no share of a pot: no old 82% rail
    else:
        MAX_COMMIT = round(COMMIT_FRAC * float(pot), 2)
        MAX_SUB_BALANCE = None                   # the operator's order: no cap on what the subaccount may hold
        COMMIT_POT = float(pot)                  # v-ladder-rail100: old_limit() is 0.82 x this same pot


def old_limit():
    """v-ladder-rail100 (2026-11-14): the money rail the OLD --commit-frac 0.82 would have set from the pot the current
    rail came from -- round(0.82 x pot, 2), exactly as apply_size rounds MAX_COMMIT -- or None when the rail is not a
    share of a pot (a fixed --size: there the commit fraction never applied)."""
    if COMMIT_POT is None:
        return None
    return round(RAIL100_OLD_FRAC * float(COMMIT_POT), 2)


def size_for_pot(pot):
    """pot dollars -> contracts a bid: floor(pot / POT_PER_CONTRACT) (14 unless --pot-per-contract), clamped 1..SIZE_MAX.
    Under --fit: floor(COMMIT_FRAC * pot / (n_coins * rung prices)), so every rung of every coin fits at once."""
    if FIT:
        cs = coins_for_pot(pot)
        n = len(cs) if cs is not None else 9
        return max(1, min(SIZE_MAX, int(math.floor(COMMIT_FRAC * float(pot) / (n * rung_px_sum()) + 1e-9))))
    return max(1, min(SIZE_MAX, int(math.floor(float(pot) / POT_PER_CONTRACT + 1e-9))))


def read_pot(sender, sub, info=None):
    """The subaccount's pot in dollars: cash + the cost of what it holds (Kalshi's market_exposure, the cost basis
    of each open position), or None when either read is unreadable. The unit is READ, never inferred (hard rule 5,
    as the main bot's read_bank).
    A resting bid's collateral is not added: the size only ever changes when no bid rests, so that read is cash.

    v-ladder-bankread (2026-11-13): `balance_dollars` ALONE IS ENOUGH -- pin's read_bank rule from build 0925v
    (bankread, 11-07), copied. Before this BOTH `balance` (cents) and `balance_dollars` had to be present, so the day
    Kalshi drops the cents field (it has removed fields with a week's notice: liquidity 10-01, available_on_brokers
    09-10) every read is None, start_refusal / AutoSize.start raise SystemExit and no restart brings the ladder back
    (and a running one logs pot_unreadable every 60 s and never resizes). Its unit is in its name (a fixed-point
    DOLLAR string), so the cents field is a cross-check, not the source: NaN / inf / garbage dollars are refused; a
    cents value that is present must still read and agree to the cent (else refused, as before; the tolerance stays
    this file's 0.011, so 1c agrees and 2c is refused whatever the float rounding); `balance` alone is still
    refused -- dividing it by 100 would be inferring the unit.

    v-ladder-start429 (2026-11-13): `info` (an optional dict) is emptied at every call and, when the read fails, filled
    with the HTTP status, the path that failed and why, so AutoSize's 'pot_unreadable' record says WHICH read failed and
    HOW. Before, the record carried no field at all: the 18-95 a day were assumed to be 429s on the balance bucket (1 call
    a second, shared with pin and the phone) but the log could not show it, nor tell them from a real outage. The pot
    and every refusal are exactly as before."""
    if info is not None:
        info.clear()

    def bad(st, path, why):
        if info is not None:
            info.update(status=st, path=path, why=why)
        return None
    st, bal = sender("GET", "/portfolio/balance", None, {"subaccount": int(sub), "exchange_index": POOL})
    if st != 200 or not isinstance(bal, dict):
        return bad(st, "/portfolio/balance", "http %s" % st if st != 200 else "body is not an object")
    cents, dollars = bal.get("balance"), bal.get("balance_dollars")
    if dollars is None:
        return bad(st, "/portfolio/balance", "no balance_dollars")   # cents alone: refused (the unit would be inferred)
    try:
        cash = float(dollars)
    except (TypeError, ValueError):
        return bad(st, "/portfolio/balance", "balance_dollars unreadable")
    if cash != cash or abs(cash) == float("inf"):
        return bad(st, "/portfolio/balance", "balance_dollars not finite")   # NaN / inf dollars: unreadable
    if cents is not None:
        try:
            c = float(cents) / 100.0
        except (TypeError, ValueError):
            return bad(st, "/portfolio/balance", "balance (cents) unreadable")   # there but unreadable: refused
        if not abs(c - cash) <= 0.011:
            return bad(st, "/portfolio/balance", "cents and dollars disagree")   # present and disagreeing (or NaN): refused
    st2, pos = sender("GET", "/portfolio/positions", None,
                      {"subaccount": int(sub), "count_filter": "position", "settlement_status": "unsettled"})
    if st2 != 200 or not isinstance(pos, dict) or not isinstance(pos.get("market_positions"), list):
        return bad(st2, "/portfolio/positions", "http %s" % st2 if st2 != 200 else "no market_positions list")
    held = 0.0
    for x in pos["market_positions"]:
        if not isinstance(x, dict):
            return bad(st2, "/portfolio/positions", "a position is not an object")
        try:
            if x.get("market_exposure_dollars") is not None:
                held += abs(float(x["market_exposure_dollars"]))
            else:
                held += abs(float(x["market_exposure"])) / 100.0
        except Exception:
            return bad(st2, "/portfolio/positions", "a position's exposure is unreadable")
    return round(cash + held, 4)


def start_read_transient(st):
    """v-ladder-start429: a status worth another try at start -- 429 (the 1-a-second balance bucket pin and the phone
    share), a 5xx, or no HTTP answer at all (ordercli.send returns -1 on a timeout / dropped connection). Any other
    status (401 bad key, 400/404 bad subaccount) will not change in five seconds: refused at once, as before."""
    return st == 429 or not isinstance(st, int) or st < 0 or st >= 500


def read_start_balance(sender, sub, sleep=time.sleep):
    """v-ladder-start429 (2026-11-13): the subaccount balance read at start -> (dollars, the statuses seen).

    Before this, main made ONE read and raised SystemExit on any failure. Kalshi's /portfolio/balance bucket is 1 call a
    second shared with pin and the phone (the running ladder logs 18-95 'pot_unreadable' a day from it), so a 429 at the
    moment of a restart -- the 04:50 ET weekly one, or boot_all's after a crash -- made the ladder refuse to start, and
    nothing tried again until boot_all's next 10-minute check: ~10 minutes of closes missed for one busy second. Now a
    429, a 5xx or a dropped connection is tried again up to 4 more times, START_BACKOFF_S (1.2 s, past the bucket's
    1 s) apart, before refusing; the refusal names every status it saw. A 200 whose balance_dollars is missing or not a
    finite number, and any other status, are refused at once (another read would not change them); the unit is read,
    never inferred (hard rule 5), as before."""
    seen, st, bal = [], None, None
    for i in range(START_TRIES):
        if i:
            sleep(START_BACKOFF_S)
        try:
            st, bal = sender("GET", "/portfolio/balance", None, {"subaccount": int(sub), "exchange_index": POOL})
        except Exception as e:                  # ordercli.send returns -1 itself; a raise is treated the same way
            st, bal = -1, repr(e)
        seen.append(st)
        if st == 200:
            try:
                v = float(bal["balance_dollars"])
            except Exception:
                v = float("nan")
            if v == v and abs(v) != float("inf"):
                return v, seen
            raise SystemExit("subaccount balance unreadable (%s %s); refusing" % (st, str(bal)[:200]))
        if not start_read_transient(st):
            break
    raise SystemExit("subaccount balance unreadable (HTTP %s after %d read(s), statuses %s: %s); refusing"
                     % (st, len(seen), seen, str(bal)[:200]))


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

    def __init__(self, log, reader, now, flat, lock=None, on_apply=None, fail_info=None):
        self.log, self.reader, self.now, self.flat = log, reader, now, flat
        self.lock = lock if lock is not None else threading.Lock()
        self.on_apply = on_apply
        self.fail_info = fail_info  # v-ladder-start429: the dict read_pot(info=) fills -> status/path/why in 'pot_unreadable'
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
            self.log.write("pot_unreadable", **dict(self.fail_info or {}))   # v-ladder-start429: + status, path, why
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
        self.halt_day = None      # v-ladder-dayreset: the ET day the day stop fired on (the halt lasts that day only)
        self.results = {}         # v-ladder-settlemiss: ticker -> its settled result, so a late fill is booked at once
        self.ticker_close = {}    # v-ladder-settlemiss: ticker -> close_s of every market admitted live
        self.settle_asked = {}    # v-ladder-settlemiss: ticker -> when the poller last looked its result up itself
        self.settle_seen = {}     # v-ladder-settlemiss: ticker -> the last lookup's (status, result, market status)
        self.held82 = {}          # v-ladder-rail100: ticker -> the cost of the over-82 bids' fills inside held[ticker]
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

    @staticmethod
    def open_left(v):
        """v-ladder-partfill (2026-11-13): what a sending/resting bid still has open -- SIZE - filled, never below 0.
        Before this exposure() and market_contracts() counted every open bid at full SIZE, but on_fill() books a fill
        into held WITHOUT changing the bid's status, so a partly filled resting bid was counted TWICE: its filled
        contracts once as held and again inside SIZE (5-lot bid, 2 filled: 2 held + 5 = 7, not 5; a fully filled bid
        still marked resting: 5 + 5 = 10), and the contract/money rails and both caps could refuse bids that fit.
        A fully filled bid still marked resting counts 0 as an order (its contracts are all in held)."""
        return max(0.0, float(SIZE) - float(v["filled"]))

    def exposure(self):
        pend = self.pending()
        opn = self.open_orders()
        n = sum(self.open_left(v) for v in opn) + sum(h["n"] for h in self.held.values()) \
            + sum(float(SIZE) - v["filled"] for v in pend)
        c = sum(float(v["px"]) * self.open_left(v) for v in opn) + sum(h["cost"] for h in self.held.values()) \
            + sum(float(v["px"]) * (float(SIZE) - v["filled"]) for v in pend)
        return n, c

    def market_contracts(self, ticker):
        """Contracts resting (v-ladder-partfill: at SIZE - filled) + held + cancelling/limbo remainder in one market."""
        h = self.held.get(ticker)
        return (h["n"] if h else 0) + sum(self.open_left(v) for v in self.open_orders() if v["ticker"] == ticker) \
            + sum(float(SIZE) - v["filled"] for v in self.pending() if v["ticker"] == ticker)

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

    def counted_ids(self):
        """The paper ids exposure() counts: sending/resting, or a remainder in a cancel or in limbo (v-ladder-rail100)."""
        cnt = {id(v) for v in self.open_orders() + self.pending()}
        return [q for q, v in self.live.items() if id(v) in cnt]

    def exposure_82(self, skip=()):
        """v-ladder-rail100 (2026-11-14): the money the OLD 82% rail would have seen at this moment -- exposure()'s money
        less (1) what the over-82 bids themselves rest, hold or have in a cancel (under the old rail they never existed);
        (2) a moved bid the new rail placed AT ONCE while a bid it replaces is still counted (its 'waits_for'): under the
        old rail it was still waiting for that cancel (v-ladder-replace), so only the bid it replaces counted -- its
        resting remainder and any fill it got meanwhile are left out until then; (3) `skip`: the paper ids a bid being
        judged would have waited for (its own check: the old world placed it once they were gone, so it saw the money
        without their resting remainder; their fills stay counted, in held). Called under self.lock (sync)."""
        ids = self.counted_ids()
        idset, skip = set(ids), set(skip)
        c = sum(h["cost"] for h in self.held.values()) - sum(self.held82.values())
        for q in ids:
            v = self.live[q]
            if v.get("over_82"):
                continue
            if any(w in idset for w in v.get("waits_for") or ()):
                if v["ticker"] in self.held:        # its fills went into held (no result yet): the old world had none
                    c -= float(v["px"]) * float(v["filled"])
                continue
            if q in skip:
                continue
            c += float(v["px"]) * self.open_left(v)
        return c

    def replaced_ids(self, ticker, desired):
        """v-ladder-rail100: the paper ids a new bid on `ticker` would have WAITED for under the old rail (v-ladder-replace)
        -- the market's bids the engine no longer wants that are still counted (sending, resting, cancelling, limbo);
        over-82 ones left out (under the old rail they never existed, so nothing waited for them)."""
        return tuple(q for q in self.counted_ids() if self.live[q]["ticker"] == ticker and q not in desired
                     and not self.live[q].get("over_82"))

    def over_82(self, px, ticker=None, desired=None):
        """v-ladder-rail100 (2026-11-14): for a bid the rails have just ADMITTED -> (over_82, old_limit, waits_for):
        over_82 True when the OLD money rail, round(0.82 x the same pot, 2), would have refused it (the old world's money
        + this bid over it); old_limit is that 0.82 x pot figure (None under a fixed --size). A MOVED bid (`ticker` has
        bids the engine no longer wants, `desired` its wanted ids) that the old rail could not hold next to the bid it
        replaces is judged as the old world placed it -- once that bid's cancel landed (v-ladder-replace) -- so without
        that bid's resting remainder; waits_for then names the bid(s) it waited for (exposure_82 leaves the move out
        while they still count). Never True at a commit fraction of 0.82 or less: such a rail is the old one or
        tighter. It only labels the bid; nothing placed depends on it."""
        lim = old_limit()
        if lim is None or COMMIT_FRAC <= RAIL100_OLD_FRAC + 1e-12:
            return False, lim, ()
        add = float(px) * float(SIZE)
        if self.exposure_82() + add <= lim + 1e-9:
            return False, lim, ()                  # the old rail places it now, beside everything counted
        gone = self.replaced_ids(ticker, desired or {}) if ticker is not None else ()
        if not gone:
            return True, lim, ()                   # nothing to wait for: the old rail refused it for good
        if self.exposure_82(skip=gone) + add > lim + 1e-9:
            return True, lim, ()                   # even once the old bid was gone the old rail refused it
        return False, lim, gone                    # the old rail waited for `gone`, then placed it

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

    def day_turn(self, now):
        """v-ladder-dayreset (2026-11-13): a day stop lasts the rest of ITS OWN ET day, as the docstrings always said ("stop
        for the ET day"). Before this nothing ever cleared `halted`: on_result's new-day branch reset only day_pnl and
        AutoSize.consider only DAY_STOP, so after one bad day the ladder refused every market until its weekly restart --
        up to 7 days, ~$200-245 of bids missed each time. Now the first call on a LATER ET day than the halt's clears it,
        starts the new day at $0 realised (the day_pnl that tripped it was yesterday's) and logs a 'day_stop_reset' record.
        On the halt's own day it does nothing: the stop still holds until midnight ET. Called under self.lock, from
        sync() (every engine tick, ~50 a second) and from _book() (so a settle that lands before the first tick of the
        new day is booked into the new day, not stopped by yesterday's halt). AutoSize.consider still resets DAY_STOP to
        -20% of the new day's first pot at its first rescale, as before (it has no handle on the broker; sync() always
        runs first)."""
        if not self.halted or self.halt_day is None:
            return
        d = et_day(now)
        if d == self.halt_day:
            return                                  # the halt holds for the rest of its own ET day
        self.log.write("day_stop_reset", halt_day=self.halt_day, day=d, halt_day_pnl=round(self.day_pnl, 4),
                       day_stop=DAY_STOP)
        self.halted, self.halt_day = False, None
        self.day, self.day_pnl = d, 0.0

    # --- called after every engine tick ---
    def sync(self, eng):
        if not self.stopped and os.path.exists(STOP_FILE):
            self.stopped = True
            self.log.write("stop_file", path=STOP_FILE)
        with self.lock:
            if self.halted:
                self.day_turn(self.now())          # v-ladder-dayreset: a new ET day clears yesterday's day stop
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
                        self.ticker_close[m.ticker] = m.close_s    # v-ladder-settlemiss: when its settle is overdue
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
                    # v-ladder-rail100: would the old 82% rail have refused it? (a move: judged once its old bid is gone)
                    o82, lim82, waits = self.over_82(o.price, m.ticker, desired)
                    self.live[pid] = {"kid": None, "ticker": m.ticker, "side": o.side, "px": o.price,
                                      "status": "sending", "filled": 0, "over_82": o82, "old_limit": lim82,
                                      "waits_for": waits}
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
    def on_result(self, ticker, result, via="engine"):
        """A market's result (from the paper engine's settle read; v-ladder-settlemiss: or the poller's own look-up,
        via="lookup") -> book what is held there, release it, and remember the result for late fills."""
        if result not in ("yes", "no"):
            return      # not settled yet (09-29 13:15 ET NEAR: an empty result was booked as a loss; it had won).
            # v-ladder-settlemiss: the holding is no longer forgotten here when the engine gives up -- once the market is
            # P.SETTLE_TIMEOUT_S past its close, settle_lookups_once() (the poller) looks the result up itself.
        with self.lock:
            self.results[ticker] = result
            if len(self.results) > 4000:           # ~2 days of every coin's closes; a late fill comes within seconds
                for k in list(self.results)[:2000]:
                    del self.results[k]
            self.settle_asked.pop(ticker, None)
            self.settle_seen.pop(ticker, None)
            self.held82.pop(ticker, None)           # v-ladder-rail100: released with the holding it is part of
            h = self.held.pop(ticker, None)
            if not h or h["n"] <= 0:
                return
            self._book(ticker, result, h["side"], h["n"], h["cost"], via)

    def _book(self, ticker, result, side, n, cost, via):
        """Book `n` contracts bought for `cost` on `side` of a market that settled `result` into the ET day's realised
        P&L, write 'live_settle' and fire the day stop. Called under self.lock (on_result, and on_fill for a fill that
        lands after its market settled)."""
        now = self.now()
        self.day_turn(now)                      # v-ladder-dayreset: a settle on a new ET day is booked into that day
        pnl = (n - cost) if side == result else -cost
        d = et_day(now)
        if d != self.day:
            self.day, self.day_pnl = d, 0.0
        self.day_pnl += pnl
        self.log.write("live_settle", ticker=ticker, result=result, side=side, n=n,
                       cost=round(cost, 4), pnl=round(pnl, 4), day_pnl=round(self.day_pnl, 4), via=via)
        if self.day_pnl <= DAY_STOP and not self.halted:
            self.halted, self.halt_day = True, d   # v-ladder-dayreset: remember the day, so the next one clears it
            self.log.write("day_stop", day=d, day_pnl=round(self.day_pnl, 4))

    def on_fill(self, pid, new_filled):
        """v-ladder-settlemiss (2026-11-13): a fill the poller sees AFTER its market's result was booked (the poller lags
        when /portfolio/orders fails or is slow -- the same outages that delay settles) is booked AT ONCE against the
        remembered result ('live_settle' via="late_fill"). Before, it re-created self.held[ticker] after the settle had
        already popped it, and nothing would ever settle it again: flat() stayed False (no rescale, no DAY_STOP reset)
        and its cost sat in exposure() until the weekly restart."""
        with self.lock:
            v = self.live.get(pid)
            if v is None or new_filled <= v["filled"]:
                return
            delta = new_filled - v["filled"]
            v["filled"] = new_filled
            res = self.results.get(v["ticker"])
            if res is None:
                h = self.held.setdefault(v["ticker"], {"side": v["side"], "n": 0, "cost": 0.0})
                h["n"] += delta
                h["cost"] += delta * float(v["px"])
                if v.get("over_82"):                 # v-ladder-rail100: the old world never held these
                    self.held82[v["ticker"]] = self.held82.get(v["ticker"], 0.0) + delta * float(v["px"])
            self.log.write("live_fill", ticker=v["ticker"], paper_id=pid, kid=v["kid"], side=v["side"],
                           px=str(v["px"]), delta=delta, filled=new_filled,
                           over_82=bool(v.get("over_82")),     # v-ladder-rail100: carried from the bid's admission
                           **({"after_settle": res} if res is not None else {}))
            if res is not None:
                self._book(v["ticker"], res, v["side"], delta, delta * float(v["px"]), "late_fill")

    def settle_lookups_once(self):
        """v-ladder-settlemiss (2026-11-13): look up, ITSELF, the result of a market it still holds once the paper engine
        has given up on it -- at most one GET a call, each market at most once every SETTLE_RETRY_S (60 s), until Kalshi
        has a result; then on_result() books it into day_pnl and releases the holding. Returns the ticker asked, or None.

        Why: the engine (locked_average_ladder_re_paper.py) marks a market settled with result None SETTLE_TIMEOUT_S
        (1,500 s) after its close, and on_result() ignores a None result, so the holding was kept FOREVER. That happened
        to every coin at the Thursday 03:00 ET close on 6 Thursdays running (Kalshi's maintenance): flat() was never
        true again (auto-size frozen, DAY_STOP never reset) and the dead cost stayed in exposure() until the weekly
        restart, holding back 1-2 coins' bids. Overdue = held and now >= its close + P.SETTLE_TIMEOUT_S, so inside the
        engine's own 25-minute wait it asks nothing extra; a normal close never reaches this.

        Read path: GET /markets/{ticker} through self.send -- the signed reader this poller thread already uses for
        /portfolio/orders every 2 s and the pot every 60 s (ordercli.send; a signed /markets/{ticker} read is what
        `ordercli.py market` and pinrun already do). NOT the paper engine's Rest thread: that one is unsigned, lives
        inside run_live() with no handle from here, and the public budget per address is ~12-14 calls a minute, which
        its 60-s market poll (10 calls) already mostly uses. One GET a call keeps the poller's 2-s fill poll moving even
        if a read hangs to its 20-s timeout. A 'settle_lookup' record is written on the first look-up of a market and
        whenever what Kalshi answers changes (not every minute through a long outage)."""
        now = self.now()
        with self.lock:
            due = []
            for t, h in self.held.items():
                c = self.ticker_close.get(t)
                if h["n"] <= 0 or c is None or now < c + P.SETTLE_TIMEOUT_S:
                    continue
                last = self.settle_asked.get(t)
                if last is not None and now - last < SETTLE_RETRY_S:
                    continue
                due.append((-1.0 if last is None else last, c, t))   # never asked first, then the longest unasked
            if not due:
                return None
            t = min(due)[2]
            self.settle_asked[t] = now
        st, r = self.send("GET", "/markets/%s" % t, None, None)
        mk = r.get("market") if st == 200 and isinstance(r, dict) else None
        res = mk.get("result") if isinstance(mk, dict) else None
        sig = (st, res, mk.get("status") if isinstance(mk, dict) else None)
        with self.lock:                          # on_result (the main thread) pops settle_seen when the market settles
            changed = self.settle_seen.get(t) != sig
            if changed:
                self.settle_seen[t] = sig
                self.log.write("settle_lookup", ticker=t, status=st, result=res, mstatus=sig[2],
                               overdue_s=round(now - self.ticker_close[t], 1), resp=None if mk else str(r)[:200])
        if res in ("yes", "no"):
            self.on_result(t, res, via="lookup")
        return t

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
            # v-ladder-rail100: the old 82% rail's answer rides on the record, never in the body sent to Kalshi
            o82 = {"over_82": bool(v.get("over_82")), "old_limit": v.get("old_limit")}
            if self.dry:
                v["status"], v["kid"] = "resting", "dry-%d" % pid
                self.log.write("would_place", body=b, **o82)
                return
            self._throttle()
            st, r = self.send("POST", "/portfolio/events/orders", b, None)
            if st in (200, 201) and isinstance(r, dict):
                v["kid"] = (r.get("order") or r).get("order_id")
                v["status"] = "resting"
                self.log.write("placed", body=b, order_id=v["kid"], resp=str(r)[:200], **o82)
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
                if self.held:                     # v-ladder-settlemiss: a holding the engine gave up on is looked up here
                    self.settle_lookups_once()
            except Exception as e:
                self.log.write("settle_lookup_error", err=repr(e)[:300])
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
        # the pot reader: unit read, never inferred (hard rule 5), cost of holdings added, any unreadable piece -> None
        def pot_send(bal, pos, st=200, st2=200):
            return lambda m, p, b, q: (st, bal) if p == "/portfolio/balance" else (st2, pos)
        ck(read_pot(pot_send({"balance": 7000, "balance_dollars": "70.0000"},
                             {"market_positions": [{"ticker": "A", "position": 5, "market_exposure_dollars": "4.9000"},
                                                   {"ticker": "B", "position": -5, "market_exposure": 400}]}), 1) == 78.9,
           "pot = cash 70.00 + held 4.90 + 4.00 (cents field) = 78.90")
        # v-ladder-bankread (2026-11-13): pin's 0925v rule -- balance_dollars alone is enough; a cents value that is
        # present must read and agree to the cent; cents alone, garbage / NaN / inf dollars and a failed read are refused
        _e = {"market_positions": []}
        _h = {"market_positions": [{"ticker": "A", "position": 5, "market_exposure_dollars": "4.9000"}]}
        _bad =[read_pot(pot_send(b, _e), 1) for b in (
            {"balance": 700000, "balance_dollars": "70.0000"},      # disagree x100 (the cents-read-as-dollars shape)
            {"balance": 7050, "balance_dollars": "70.0000"},        # disagree by 50c
            {"balance": 7002, "balance_dollars": "70.0000"},        # disagree by 2c (one cent is the tolerance)
            {"balance": 7000},                                      # cents alone: /100 would be inferring the unit
            {"balance": "junk", "balance_dollars": "70.0000"},      # cents present but unreadable
            {"balance_dollars": "x"}, {"balance_dollars": "nan"}, {"balance": 7000, "balance_dollars": "nan"},
            {"balance_dollars": "inf"}, {"balance_dollars": "-inf"}, {"balance_dollars": None}, {}, "not a dict")]
        _bad.append(read_pot(pot_send({"balance": 7000, "balance_dollars": "70.0000"}, _e, st=500), 1))
        ck(read_pot(pot_send({"balance": 7000, "balance_dollars": "70.0000"}, _e), 1) == 70.0
           and read_pot(pot_send({"balance_dollars": "70.0000"}, _e), 1) == 70.0
           and read_pot(pot_send({"balance_dollars": "70.0000"}, _h), 1) == 74.9
           and read_pot(pot_send({"balance": 7001, "balance_dollars": "70.0000"}, _e), 1) == 70.0
           and start_refusal(None, read_pot(pot_send({"balance_dollars": "70.0000"}, _e), 1), True, True) is None
           and len(_bad) == 14 and all(x is None for x in _bad),
           "v-ladder-bankread: balance_dollars ALONE reads $70.00 (+ holdings $74.90) and --auto-size starts on it; both "
           "present and agreeing to the cent read the dollars; disagreeing (x100, 50c, 2c), cents alone, garbage cents, "
           "garbage / NaN / inf / missing dollars and a failed read are all refused (got %r)" % _bad)
        ck(read_pot(pot_send({"balance": 7000, "balance_dollars": "70.0000"}, {"nope": 1}), 1) is None
           and read_pot(pot_send({"balance": 7000, "balance_dollars": "70.0000"}, {"market_positions": []}, st2=500), 1) is None
           and read_pot(pot_send({"balance": 7000, "balance_dollars": "70.0000"},
                                 {"market_positions": [{"ticker": "A", "position": 1}]}), 1) is None,
           "pot: a missing/failed/unreadable positions read is None (never 'flat')")
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
        # v-ladder-partfill (2026-11-13): a RESTING bid that is partly filled counts SIZE - filled as an order (the filled
        # contracts are in held). Before, it counted held + SIZE: 2 of 5 filled -> 7 contracts / $6.86, not 5 / $4.90
        brp = Broker(log, 3, False, fake_send, lambda: now[0])
        mp = [_M("P1", 9100, [_O(91000, "yes", "0.98")])]
        brp.sync(_E(mp))
        while not brp.q.empty():
            brp.work_once(brp.q.get())
        brp.on_fill(91000, 2)                               # the poller books 2 of 5; on_fill leaves the bid 'resting'
        np_, cp_ = brp.exposure()
        ck(brp.live[91000]["status"] == "resting" and brp.held["P1"]["n"] == 2 and np_ == 5
           and abs(cp_ - 0.98 * 5) < 1e-9 and brp.market_contracts("P1") == 5,
           "partfill: a resting bid 2 of 5 filled = 2 held + 3 resting = 5 contracts, $4.90 (was 7, $6.86; got %s, %.2f)"
           % (np_, cp_))
        MARKET_CAP_X = 2
        mp[0].orders = mp[0].orders + [_O(91001, "yes", "0.98")]   # a 2nd bid on the market while the 1st still rests
        brp.sync(_E(mp))
        ck(brp.live[91001]["status"] == "sending",
           "partfill: market cap x2 -> 5 counted + a 2nd bid of 5 = 10 is placed (the double count made it 12: refused)")
        MARKET_CAP_X = 0
        brp.on_fill(91000, 5)                               # fully filled, still marked resting
        np_, cp_ = brp.exposure()
        ck(brp.live[91000]["status"] == "resting" and brp.open_left(brp.live[91000]) == 0 and np_ == 10
           and abs(cp_ - 0.98 * 10) < 1e-9 and brp.market_contracts("P1") == 10,
           "partfill: a fully filled bid still marked resting counts 0 as an order -> 5 held + the 2nd bid's 5 = 10 "
           "(was 15; got %s, %.2f)" % (np_, cp_))
    finally:
        SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE, MARKET_CAP_X, CLOSE_CAP_X = _sv
    # v-ladder-dayreset (2026-11-13): the day stop lasts its own ET day, then clears. Before, nothing cleared `halted`:
    # one bad day stopped the ladder until its weekly restart. Halt at 17:00 EST on 11-12; 23:59 EST (04:59Z 11-13) is
    # still 11-12 -> still halted, nothing placed; 00:00 EST 11-13 (05:00Z) -> cleared, 'day_stop_reset', bids again
    _sv = (SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE)
    try:
        apply_size(1)                                       # the penny rails: day stop -$6
        clkd = [_u(2026, 11, 12, 22, 0)]
        brd = Broker(log, 3, False, fake_send, lambda: clkd[0])
        brd.held["DR0"] = {"side": "yes", "n": 10, "cost": 9.8}
        brd.on_result("DR0", "no")                          # -$9.80 <= -$6: the day stop fires on ET day 11-12
        ck(brd.halted and sink[-1]["ev"] == "day_stop" and sink[-1]["day"] == "2026-11-12",
           "dayreset: a -$9.80 day halts on ET day 2026-11-12")
        clkd[0] = _u(2026, 11, 13, 4, 59)                   # 23:59 EST: still ET day 11-12
        brd.sync(_E([_M("DR1", clkd[0] + 30, [_O(99101, "yes", "0.98")])]))
        ck(brd.halted and not brd.live and brd.q.empty() and not any(r["ev"] == "day_stop_reset" for r in sink),
           "dayreset: the halt holds for the rest of its own ET day (23:59 EST: nothing placed, not reset)")
        n0 = len(sink)
        clkd[0] = _u(2026, 11, 13, 5, 0)                    # 00:00 EST: ET day 11-13
        brd.sync(_E([_M("DR2", clkd[0] + 900, [_O(99102, "yes", "0.98")])]))
        rs = [r for r in sink[n0:] if r["ev"] == "day_stop_reset"]
        ck(not brd.halted and brd.day_pnl == 0.0 and len(rs) == 1 and rs[0]["halt_day"] == "2026-11-12"
           and rs[0]["day"] == "2026-11-13" and rs[0]["halt_day_pnl"] == -9.8
           and brd.live.get(99102, {}).get("status") == "sending",
           "dayreset: the first tick of ET day 11-13 clears the halt ('day_stop_reset' logged once, day P&L back to $0) "
           "and the next market's bid is placed (before: halted until the weekly restart)")
        brd.sync(_E([_M("DR2", clkd[0] + 900, [_O(99102, "yes", "0.98")])]))
        ck(len([r for r in sink[n0:] if r["ev"] == "day_stop_reset"]) == 1, "dayreset: logged once, not every tick")
        brd.held["DR3"] = {"side": "yes", "n": 10, "cost": 9.8}
        brd.on_result("DR3", "no")
        ck(brd.halted and sink[-1]["ev"] == "day_stop" and sink[-1]["day"] == "2026-11-13",
           "dayreset: a second bad day halts again, on its own day")
        brd2 = Broker(log, 3, False, fake_send, lambda: clkd[0])   # a settle lands before any tick of the new day
        brd2.held["DR4"] = {"side": "yes", "n": 10, "cost": 9.8}
        clkd[0] = _u(2026, 11, 13, 22, 0)                   # 17:00 EST 11-13: halt
        brd2.on_result("DR4", "no")
        clkd[0] = _u(2026, 11, 14, 5, 1)                    # 00:01 EST 11-14: a win settles, no tick yet
        brd2.held["DR5"] = {"side": "yes", "n": 10, "cost": 9.8}
        brd2.on_result("DR5", "yes")
        ck(not brd2.halted and abs(brd2.day_pnl - 0.2) < 1e-9 and brd2.day == "2026-11-14",
           "dayreset: a settle on the next ET day clears yesterday's halt too and starts the day at +$0.20")
    finally:
        SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE = _sv
    # v-ladder-settlemiss (2026-11-13): the Thursday 03:00 ET shape -- Kalshi's maintenance, the engine's settle read
    # times out after 25 min (result None), and the holding used to be kept until the weekly restart. Now: nothing extra
    # inside the engine's wait; after it, GET /markets/{ticker} at most once a minute until a result; then booked and
    # released. And a fill the poller sees after its market settled is booked at once, not re-held.
    _sv = (SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE)
    try:
        apply_size(5)
        mkt = {"st": 503, "body": "service unavailable"}
        gets = []

        def send_s(method, path, body, query):
            if method == "GET" and path.startswith("/markets/"):
                gets.append(path)
                return mkt["st"], mkt["body"]
            return fake_send(method, path, body, query)
        cls = _u(2026, 11, 12, 8, 0)                        # Thursday 03:00 EST close
        clks = [cls - 20.0]
        brs = Broker(log, 1, False, send_s, lambda: clks[0])
        tks = "KXNEAR15M-26NOV120300-00"
        brs.sync(_E([_M(tks, cls, [_O(99200, "yes", "0.98")])]))
        while not brs.q.empty():
            brs.work_once(brs.q.get())
        brs.on_fill(99200, 5)                               # filled before the close
        brs.live[99200]["status"] = "cancelled"             # the paper order expired at the close; its cancel returned
        clks[0] = cls + 600
        brs.on_result(tks, None)                            # the engine: no result yet
        ck(brs.settle_lookups_once() is None and not gets and brs.held[tks]["n"] == 5,
           "settlemiss: inside the engine's 25-min settle wait the ladder asks nothing extra")
        n0 = len(sink)
        clks[0] = cls + P.SETTLE_TIMEOUT_S + 1
        brs.on_result(tks, None)                            # the engine's give-up: settled with result None
        brs.settle_lookups_once()                           # 503: maintenance
        clks[0] += 30
        brs.settle_lookups_once()                           # 30 s later: not asked again
        ck(gets == ["/markets/" + tks] and brs.held[tks]["n"] == 5 and not brs.flat()
           and [(r["ev"], r["status"]) for r in sink[n0:]] == [("settle_lookup", 503)],
           "settlemiss: past the engine's timeout the held market is looked up (GET /markets/{ticker}) at most once a "
           "minute; a 503 keeps it held (got %s)" % gets)
        clks[0] += 31
        mkt.update(st=200, body={"market": {"ticker": tks, "result": "", "status": "closed"}})
        brs.settle_lookups_once()
        clks[0] += 60
        brs.settle_lookups_once()                           # the same answer again: asked, not logged again
        ck(len(gets) == 3 and brs.held[tks]["n"] == 5
           and [r.get("status") for r in sink[n0:] if r["ev"] == "settle_lookup"] == [503, 200],
           "settlemiss: no result yet -> still held, asked again a minute later, logged only when the answer changes")
        clks[0] += 60
        mkt.update(st=200, body={"market": {"ticker": tks, "result": "yes", "status": "finalized"}})
        d0 = brs.day_pnl
        brs.settle_lookups_once()
        n_, c_ = brs.exposure()
        ck(len(gets) == 4 and tks not in brs.held and brs.flat() and n_ == 0 and c_ == 0
           and abs(brs.day_pnl - (d0 + 5 - 4.9)) < 1e-9
           and any(r["ev"] == "live_settle" and r["ticker"] == tks and r["via"] == "lookup" and r["pnl"] == 0.1
                   for r in sink[n0:]),
           "settlemiss: the result arrives -> +$0.10 booked into day_pnl ('live_settle' via=lookup), the holding "
           "released: flat, exposure 0 (before: held until the weekly restart)")
        clks[0] += 600
        ck(brs.settle_lookups_once() is None and len(gets) == 4, "settlemiss: settled -> never looked up again")
        tk2 = "KXZEC15M-26NOV120315-15"
        clks[0] = cls + 880
        brs.sync(_E([_M(tk2, cls + 900, [_O(99300, "yes", "0.98")])]))
        while not brs.q.empty():
            brs.work_once(brs.q.get())
        brs.on_fill(99300, 2)                               # 2 of 5 seen before the close
        brs.live[99300]["status"] = "cancelled"
        clks[0] = cls + 990
        brs.on_result(tk2, "no")                            # the engine settles it: the 2 held lose $1.96
        dl = brs.day_pnl
        brs.on_fill(99300, 5)                               # the poller (lagging) sees 3 more filled AFTER the settle
        ck(tk2 not in brs.held and brs.flat() and abs(brs.day_pnl - (dl - 3 * 0.98)) < 1e-9
           and any(r["ev"] == "live_settle" and r["ticker"] == tk2 and r["via"] == "late_fill" and r["n"] == 3
                   for r in sink[n0:]),
           "settlemiss: a fill seen after its market settled is booked at once (-$2.94, via=late_fill), not re-held "
           "(before: held forever, never flat)")
        tk3 = "KXDOGE15M-26NOV120330-30"
        clks[0] = cls + 1780
        brs.sync(_E([_M(tk3, cls + 1800, [_O(99400, "no", "0.98")])]))
        while not brs.q.empty():
            brs.work_once(brs.q.get())
        brs.live[99400]["status"] = "cancelled"
        clks[0] = cls + 1800 + P.SETTLE_TIMEOUT_S + 5        # the engine gave up with NOTHING held here...
        brs.on_result(tk3, None)
        brs.on_fill(99400, 5)                               # ...then a late fill shows up: held, and looked up itself
        mkt.update(st=200, body={"market": {"ticker": tk3, "result": "no", "status": "finalized"}})
        brs.settle_lookups_once()
        ck(gets[-1:] == ["/markets/" + tk3] and tk3 not in brs.held and brs.flat(),
           "settlemiss: a fill that lands after the engine gave up on an EMPTY market is still looked up and released")
    finally:
        SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE = _sv
    # v-ladder-start429 (2026-11-13): the start balance read retries a 429 / 5xx / no answer up to 4 more times, 1.2 s
    # apart (the bucket is 1 call a second, shared with pin and the phone); anything else is refused at once, as before.
    # And 'pot_unreadable' now says which read failed with what status.
    def seq_send(answers, calls):
        def f(method, path, body, query):
            calls.append((method, path, query))
            a_ = answers[min(len(calls), len(answers)) - 1]
            if isinstance(a_, Exception):
                raise a_
            return a_
        return f
    outs = []
    for answers in ([(429, "too many requests"), (429, "too many requests"), (200, {"balance_dollars": "70.0000"})],
                    [(-1, "timed out"), RuntimeError("reset"), (503, "busy"), (200, {"balance_dollars": "12.5"})],
                    [(429, "too many requests")],
                    [(401, "bad key")],
                    [(200, {"balance": 7000})],
                    [(200, {"balance_dollars": "nan"})]):
        calls, slept = [], []
        try:
            got = read_start_balance(seq_send(answers, calls), 1, sleep=slept.append)
        except SystemExit as e:
            got = "refused: %s" % e
        outs.append((got, len(calls), slept, calls[0]))
    ck(outs[0][:3] == ((70.0, [429, 429, 200]), 3, [1.2, 1.2])
       and outs[0][3] == ("GET", "/portfolio/balance", {"subaccount": 1, "exchange_index": POOL})
       and outs[1][:3] == ((12.5, [-1, -1, 503, 200]), 4, [1.2, 1.2, 1.2]),
       "start429: two 429s then a good read -> starts on $70.00 after 2 waits of 1.2 s; a timeout, a raise and a 503 "
       "are retried too (got %s)" % [o[:3] for o in outs[:2]])
    ck(str(outs[2][0]).startswith("refused") and "429" in outs[2][0] and outs[2][1:3] == (5, [1.2] * 4)
       and str(outs[3][0]).startswith("refused") and "401" in outs[3][0] and outs[3][1:3] == (1, [])
       and str(outs[4][0]).startswith("refused") and outs[4][1:3] == (1, [])
       and str(outs[5][0]).startswith("refused") and outs[5][1:3] == (1, []),
       "start429: 429 five times -> refused after 1 + 4 retries, naming the 429s; a 401, a 200 without "
       "balance_dollars and a NaN balance -> refused at once, no retry (got %s)" % [o[:3] for o in outs[2:]])
    fi = {}
    azs = AutoSize(log, lambda: read_pot(pot_send({"balance_dollars": "70.0000"}, _e, st=429), 1, info=fi),
                   lambda: 0.0, lambda: True, fail_info=fi)
    azs.tick()
    ck(sink[-1]["ev"] == "pot_unreadable" and sink[-1].get("status") == 429
       and sink[-1].get("path") == "/portfolio/balance",
       "start429: 'pot_unreadable' carries the HTTP status and the path (429 on /portfolio/balance; got %s)" % sink[-1])
    fi2 = {}
    r_pos = read_pot(pot_send({"balance_dollars": "70.0000"}, _e, st2=500), 1, info=fi2)
    pos_fail = dict(fi2)
    r_ok = read_pot(pot_send({"balance_dollars": "70.0000"}, _e), 1, info=fi2)
    ck(r_pos is None and pos_fail.get("status") == 500 and pos_fail.get("path") == "/portfolio/positions"
       and r_ok == 70.0 and fi2 == {},
       "start429: a failed positions read names its own path and status; a good read empties the info (no stale status)")
    # v-ladder-rail100 (2026-11-14): the old 82% rail's answer on every admitted bid. At 11-14's $1,338.6325 pot and
    # --pot-per-contract 5.9756 the bid is 224 contracts ($219.52 at 98c) under either rail; 0.82 x pot = $1,097.68
    # holds five ($1,097.60), 1.0 x pot = $1,338.63 holds six ($1,317.12), and a seventh ($1,536.64) is refused by both.
    global COMMIT_FRAC, COMMIT_POT
    _sv = (SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE, COMMIT_FRAC, COMMIT_POT, POT_PER_CONTRACT, FIT,
           COINS, MARKET_CAP_X, CLOSE_CAP_X, LIVE_LEVELS)
    try:
        FIT, COINS, MARKET_CAP_X, CLOSE_CAP_X, LIVE_LEVELS, POT_PER_CONTRACT = False, None, 2, 0, (0,), 5.9756
        pot100, bid = 1338.6325, 0.98 * 224
        tq = ["KXQ%d15M-26NOV141000-00" % i for i in range(7)]
        got82 = {}
        for frac in (1.0, 0.82):
            COMMIT_FRAC = frac
            apply_size(size_for_pot(pot100), pot=pot100)
            brq = Broker(log, 1, False, fake_send, lambda: now[0])
            mq = [_M(tq[i], 9900, [_O(99900 + i, "yes", "0.98")]) for i in range(7)]
            k0, s0 = len(sink), len(sent)
            brq.sync(_E(mq))                              # seven markets decided in one close, in order
            while not brq.q.empty():
                brq.work_once(brq.q.get())
            got82[frac] = (brq, mq, [r for r in sink[k0:] if r["ev"] == "placed"],
                           [r for r in sink[k0:] if r["ev"] == "rail_refused"], [s[2] for s in sent[s0:] if s[0] == "POST"])
            if frac == 1.0:
                brq_, mq_, pl, rf, bodies = got82[1.0]
                ck(int(SIZE) == 224 and MAX_COMMIT == 1338.63 and old_limit() == 1097.68,
                   "rail100: $1,338.6325 / 5.9756 -> 224 a bid, rail $1,338.63, the old 82%% rail $1,097.68 (got %s, %s, %s)"
                   % (SIZE, MAX_COMMIT, old_limit()))
                ck([r["over_82"] for r in pl] == [False] * 5 + [True] and all(r["old_limit"] == 1097.68 for r in pl)
                   and pl[5]["body"]["ticker"] == tq[5] and [r["why"] for r in rf] == ["max_commit"],
                   "rail100: commit_frac 1.0 places six bids -- the first five over_82 false, the 6th TRUE (old_limit "
                   "1097.68 on each) -- and refuses the 7th (got %s, refused %s)"
                   % ([r["over_82"] for r in pl], [r["why"] for r in rf]))
                ck(len(bodies) == 6 and not any("over_82" in b_ or "old_limit" in b_ for b_ in bodies)
                   and all(body_ok(b_, 1) for b_ in bodies),
                   "rail100: the answer rides on the record only -- the six bodies sent to Kalshi are unchanged")
                k1 = len(sink)
                brq.on_fill(99901, 224)                   # the 2nd market's bid fills whole (an old-world bid)
                brq.on_fill(99905, 100)                   # the 6th (over 82%) fills 100 of 224
                lf = [r for r in sink[k1:] if r["ev"] == "live_fill"]
                ck([(r["paper_id"], r["over_82"]) for r in lf] == [(99901, False), (99905, True)]
                   and abs(brq.held82.get(tq[5], 0) - 98.0) < 1e-9
                   and abs(brq.exposure()[1] - 6 * bid) < 1e-6 and abs(brq.exposure_82() - 5 * bid) < 1e-6,
                   "rail100: each live_fill carries its bid's over_82; the old world's money ($1,097.60 of today's "
                   "$1,317.12) leaves out the 6th bid's 100 held ($98.00) and 124 resting ($121.52) (got %s, %.2f, %.2f)"
                   % ([(r["paper_id"], r["over_82"]) for r in lf], brq.exposure()[1], brq.exposure_82()))
                # the paper engine MOVES the 1st market's bid (a new paper order) while the 6th still rests: once the old
                # bid's cancel lands the move is placed, and it is NOT over 82% -- under the old rail the 6th bid never
                # existed, so the moved bid is one of five ($1,097.60 with it); counting the 6th ($1,317.12) would mark it
                # and price the same extra bid twice
                mq[0].orders = [_O(99950, "yes", "0.98")]
                brq.sync(_E(mq))                          # the old bid still counted: the move waits (v-ladder-replace)
                while not brq.q.empty():
                    brq.work_once(brq.q.get())            # ...its cancel lands
                brq.sync(_E(mq))
                while not brq.q.empty():
                    brq.work_once(brq.q.get())
                v50 = brq.live.get(99950, {})
                ck(brq.live[99900]["status"] == "cancelled" and v50.get("status") == "resting"
                   and v50.get("over_82") is False and brq.live[99905]["over_82"] is True
                   and [r["over_82"] for r in sink[k1:] if r["ev"] == "placed"] == [False],
                   "rail100: a moved bid of the first five markets is placed with over_82 false; the 6th stays true "
                   "(got %s)" % v50)
                brq.on_result(tq[5], "yes")
                ck(tq[5] not in brq.held82 and tq[5] not in brq.held, "rail100: the settle releases the over-82 holding too")
        brq, mq, pl, rf, bodies = got82[0.82]
        ck(MAX_COMMIT == 1097.68 == old_limit() and len(pl) == 5 and not any(r["over_82"] for r in pl)
           and [r["why"] for r in rf] == ["max_commit", "max_commit"]
           and not any(v.get("over_82") for v in brq.live.values()),
           "rail100 NULL: commit_frac 0.82 places five, refuses the 6th and 7th, and nothing is ever over_82 (got %s, %s)"
           % ([r["over_82"] for r in pl], [r["why"] for r in rf]))
        mq[0].orders = [_O(99970, "yes", "0.98")]         # a move under 0.82 is never over 82% either
        for _k in range(2):
            brq.sync(_E(mq))
            while not brq.q.empty():
                brq.work_once(brq.q.get())
        ck(brq.live.get(99970, {}).get("status") == "resting" and not any(v.get("over_82") for v in brq.live.values()),
           "rail100 NULL: a moved bid under 0.82 is placed, not over 82%")
        # an ORDINARY move on the 1.0 rail (the 11-14 reviewer's probe): five bids rest (the 1st at 97.9c) and the engine
        # moves the 1st to 98c (a new paper order). The 1.0 rail has room, so the move is placed AT ONCE while the old
        # bid is still counted; under 0.82 the move waited for the old bid's cancel (v-ladder-replace) and was then
        # placed, so the old limit would NOT have refused it: over_82 false. A genuinely new 6th bid is over 82%.
        COMMIT_FRAC = 1.0
        apply_size(size_for_pot(pot100), pot=pot100)

        def five(tick):
            tk_ = ["KX%s%d15M-26NOV141015-15" % (tick, i) for i in range(6)]
            br_ = Broker(log, 1, False, fake_send, lambda: now[0])
            ms_ = [_M(tk_[0], 9930, [_O(99800, "yes", "0.979")])] + \
                [_M(tk_[i], 9930, [_O(99800 + i, "yes", "0.98")]) for i in range(1, 5)]
            br_.sync(_E(ms_))
            while not br_.q.empty():
                br_.work_once(br_.q.get())
            return br_, ms_, tk_
        brm, mm, tm = five("M")
        k3 = len(sink)
        mm[0].orders = [_O(99810, "yes", "0.98")]
        brm.sync(_E(mm))                                  # the move is admitted at once; the old bid's cancel is queued
        vm = dict(brm.live.get(99810, {}))
        win82, win_all = brm.exposure_82(), brm.exposure()[1]
        while not brm.q.empty():
            brm.work_once(brm.q.get())                    # ...the move rests, the old bid's cancel lands
        old5 = 0.979 * 224 + 4 * bid
        ck(vm.get("over_82") is False and vm.get("waits_for") == (99800,) and brm.live[99800]["status"] == "cancelled"
           and abs(win82 - old5) < 1e-6 and abs(win_all - (old5 + bid)) < 1e-6
           and abs(brm.exposure_82() - 5 * bid) < 1e-6
           and [r["over_82"] for r in sink[k3:] if r["ev"] == "placed"] == [False],
           "rail100: an ordinary move (97.9c -> 98c) with five bids resting is placed at once and is NOT over 82%% (the "
           "old rail waited for the old bid's cancel, then placed it); while that cancel is in flight the old world's "
           "money is the old bid + four ($%.2f), not the move too ($%.2f); after it, five bids (got %s, window %.2f / %.2f,"
           " after %.2f)" % (old5, old5 + bid, {k_: vm.get(k_) for k_ in ("over_82", "waits_for", "status")}, win82,
                            win_all, brm.exposure_82()))
        k4 = len(sink)
        mm.append(_M(tm[5], 9930, [_O(99815, "yes", "0.98")]))
        brm.sync(_E(mm))                                  # a genuinely new 6th market
        while not brm.q.empty():
            brm.work_once(brm.q.get())
        ck(brm.live.get(99815, {}).get("over_82") is True and brm.live[99815]["status"] == "resting"
           and [r["over_82"] for r in sink[k4:] if r["ev"] == "placed"] == [True],
           "rail100: after the move, a genuinely new 6th bid IS over 82%% (got %s)"
           % {k_: brm.live.get(99815, {}).get(k_) for k_ in ("over_82", "status")})
        # the window: market 2's bid fills whole, the 1st moves (placed at once, its old bid in its cancel), market 2
        # settles, and a NEW market's bid is judged before the old bid's cancel lands. The old world then held the old
        # 97.9c bid + markets 3-5 ($877.86): the new bid fits under $1,097.68, not over 82%. Counting the move as well
        # (it was still waiting under 0.82) would read $1,097.38 + $219.52 and mark it over.
        brw, mw, tw = five("W")
        brw.on_fill(99801, 224)
        mw[0].orders = [_O(99820, "yes", "0.98")]
        brw.sync(_E(mw))
        brw.on_result(tw[1], "yes")
        mw.append(_M(tw[5], 9930, [_O(99825, "yes", "0.98")]))
        brw.sync(_E(mw))                                  # the new market's bid, judged in the window
        v25 = dict(brw.live.get(99825, {}))
        while not brw.q.empty():
            brw.work_once(brw.q.get())
        ck(brw.live.get(99820, {}).get("over_82") is False and v25.get("over_82") is False
           and v25.get("waits_for") == () and brw.live[99800]["status"] == "cancelled"
           and abs(brw.exposure_82() - 5 * bid) < 1e-6,
           "rail100: a new market's bid judged while a move's old bid is still in its cancel sees the old world's money "
           "(the old bid, not the move as well): not over 82%% (got %s; after the cancel %.2f)"
           % ({k_: v25.get(k_) for k_ in ("over_82", "waits_for")}, brw.exposure_82()))
        COMMIT_FRAC = 0.70                                # the default: a tighter rail than 0.82 never is over it
        apply_size(size_for_pot(pot100), pot=pot100)
        brd7 = Broker(log, 1, False, fake_send, lambda: now[0])
        brd7.sync(_E([_M(tq[i], 9910, [_O(99980 + i, "yes", "0.98")]) for i in range(7)]))
        ck(not any(v.get("over_82") for v in brd7.live.values()) and old_limit() == 1097.68,
           "rail100 NULL: commit_frac 0.70 is never over 82%")
        COMMIT_FRAC = 1.0
        apply_size(5)                                     # a fixed --size: no pot, so no old 82% rail at all
        k2 = len(sink)
        brf = Broker(log, 1, True, fake_send, lambda: now[0])
        brf.sync(_E([_M(tq[0], 9920, [_O(99990, "yes", "0.98")])]))
        while not brf.q.empty():
            brf.work_once(brf.q.get())
        wp = [r for r in sink[k2:] if r["ev"] == "would_place"]
        ck(old_limit() is None and len(wp) == 1 and wp[0]["over_82"] is False and wp[0]["old_limit"] is None,
           "rail100 NULL: a fixed --size has no old 82%% rail (old_limit None, over_82 false; the dry run's would_place "
           "carries both): %s" % wp)
    finally:
        (SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE, COMMIT_FRAC, COMMIT_POT, POT_PER_CONTRACT, FIT,
         COINS, MARKET_CAP_X, CLOSE_CAP_X, LIVE_LEVELS) = _sv
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
    sub_bal, start_reads = read_start_balance(sender, a.subaccount)   # v-ladder-start429: 429/5xx/no answer retried
    pot = None
    pot_fail = {}                                  # v-ladder-start429: what the last failed pot read saw (status/path/why)
    for _try in range(5 if a.auto_size else 0):    # v-ladder-optc: the start read retries (429s right after maintenance)
        time.sleep(2.0)
        pot = read_pot(sender, a.subaccount, info=pot_fail)
        if pot is not None:
            break
    why = start_refusal(sub_bal, pot, a.live, a.auto_size)
    if why:
        raise SystemExit(why + (" (last read: %s)" % pot_fail if a.auto_size and pot_fail else "") + " -- refusing")
    if os.path.exists(STOP_FILE):
        raise SystemExit("stop file present: %s" % STOP_FILE)
    P.NAME, P.LOG_PATH = "ladder_live", LIVE_LOG
    olog = P.Logger(ORDER_LOG)
    br = Broker(olog, a.subaccount, a.dry_run, sender, time.time)
    auto = None
    if a.auto_size:
        br.sizer = AutoSize(olog, lambda: read_pot(sender, a.subaccount, info=pot_fail), time.time, br.flat, br.lock,
                            on_apply=lambda: setattr(P, "SIZE", SIZE), fail_info=pot_fail)
        br.sizer.start(pot)                        # sets SIZE and every rail from the pot; refuses under $10
        auto = {"pot_per_contract": POT_PER_CONTRACT, "size_max": SIZE_MAX, "reread_s": POT_REREAD_S,
                "day_stop_frac": DAY_STOP_FRAC, "commit_frac": COMMIT_FRAC}
    P.SIZE = SIZE
    # v-ladder-rail100 (2026-11-14): the start record carries its argv, so /fixes change O dates itself from the first
    # start on --commit-frac 1.0 (auto.commit_frac says the same under --auto-size; argv says it for any run)
    olog.write("start", pid=os.getpid(), subaccount=a.subaccount, live=a.live, sub_balance=sub_bal,
               start_reads=start_reads, auto_size=bool(a.auto_size), pot=pot, auto=auto, argv=list(sys.argv[1:]),
               old_limit=old_limit(),
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
