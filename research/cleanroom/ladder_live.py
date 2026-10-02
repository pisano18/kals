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
SIZE_MAX = 100                                   # --size / --auto-size ceiling (was 20)
POT_PER_CONTRACT = 14.0                          # size = floor(pot / 14): $70 -> 5 (today's size), $140 -> 10
POT_FLOOR = 10.0                                 # refuse to start under this pot (the lower sanity floor)
POT_REREAD_S = 60.0                              # the main bot's autosize cadence
DAY_STOP_FRAC, COMMIT_FRAC = 0.20, 0.70


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
    """pot dollars -> contracts a bid: floor(pot / 14), clamped 1..SIZE_MAX."""
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
        apply_size(n, pot=pot)
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


MAX_LIVE_PER_CLOSE = 9                           # v-ladder-top (09-29): every coin (was 3 -- the first 3 markets to lock
                                                 # took the slots and never filled; all 20 paper fills were in later ones)
LIVE_LEVELS = (0,)                               # v-ladder-top: mirror only the top rung (model-2c): 16 of 20 paper fills
WRITES_PER_S = 3.0
POOL = 2
CID_PREFIX = "lad-"


def et_day(t):
    return (datetime.fromtimestamp(t, timezone.utc) - timedelta(hours=4)).strftime("%Y-%m-%d")


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
        self.held = {}            # ticker -> {"side", "n", "cost"}
        self.day, self.day_pnl = None, 0.0
        self.halted = self.stopped = False
        self.lock = threading.Lock()
        self._w = []
        self.sizer = None         # AutoSize under --auto-size; its tick runs on the poller thread

    # --- exposure and rails ---
    def open_orders(self):
        return [v for v in self.live.values() if v["status"] in ("sending", "resting")]

    def flat(self):
        """Nothing held, no bid sending/resting/cancelling, nothing queued: the only state in which the size may change."""
        return (not any(h["n"] > 0 for h in self.held.values()) and not self.open_orders()
                and not any(v["status"] == "cancelling" for v in self.live.values()) and self.q.empty())

    def exposure(self):
        n = len(self.open_orders()) * float(SIZE) + sum(h["n"] for h in self.held.values())
        c = sum(float(v["px"]) * float(SIZE) for v in self.open_orders()) + sum(h["cost"] for h in self.held.values())
        return n, c

    def rails_refusal(self, px):
        if self.stopped:
            return "stopped"
        if self.halted:
            return "day_stop"
        n, c = self.exposure()
        if n + float(SIZE) > MAX_CONTRACTS + 1e-9:
            return "max_contracts"
        if c + float(px) * float(SIZE) > MAX_COMMIT + 1e-9:
            return "max_commit"
        return None

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
                live_set = self.live_markets.setdefault(m.close_s, set())
                if m.ticker not in live_set:
                    if desired and len(live_set) < MAX_LIVE_PER_CLOSE and not (self.halted or self.stopped):
                        live_set.add(m.ticker)
                        self.log.write("live_market", ticker=m.ticker, close_s=m.close_s)
                    else:
                        continue
                for pid, o in desired.items():
                    if pid in self.live or m.done or self.halted or self.stopped:
                        continue
                    why = self.rails_refusal(o.price)
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
            apply_size(101)
            ck(False, "--size 101 must be refused")
        except SystemExit:
            pass
        ck([size_for_pot(p) for p in (70, 140, 13, 28, 69.99, 5000, 1400, 9)] == [5, 10, 1, 2, 4, 100, 100, 1],
           "size = floor(pot/14): $70 -> 5, $140 -> 10, $69.99 -> 4, floor 1, cap 100")
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
                          (5000.0, (100, 1000, 3500.0, -1000.0))):
            az = AutoSize(log, lambda: None, lambda: clk[0], lambda: flat[0], on_apply=lambda: applied.append(int(SIZE)))
            az.start(pot)
            got = (az.size, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP)
            ck(got == want and SIZE == Decimal(want[0]) and MAX_SUB_BALANCE is None,
               "auto-size at pot $%.0f: (size, contracts, commit 70%%, day -20%%) = %s, want %s" % (pot, got, want))
        ck(applied == [5, 10, 1, 100], "on_apply runs with each applied size (main keeps the paper engine's SIZE in step)")
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
    a = ap.parse_args()
    if not selftest() or not P.selftest():
        raise SystemExit("self-test failed; refusing to run")
    if a.selftest:
        return 0
    if not a.subaccount or a.subaccount < 1:
        raise SystemExit("--subaccount N (1..63) is required; the primary account is refused")
    if not a.auto_size:
        apply_size(a.size)
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
    pot = read_pot(sender, a.subaccount) if a.auto_size else None
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
                      "live_levels": list(LIVE_LEVELS), "writes_per_s": WRITES_PER_S})
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
