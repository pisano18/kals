#!/usr/bin/env python3
"""bettor_live.py -- the clean-room BETTOR, LIVE at 1 contract a market, in Kalshi SUBACCOUNT 2.

Operator 2026-09-28: "I want to run clean room bettor but at a tiny size."

WHAT IT DOES
  Runs bettor_paper.py's engine unchanged, bettor rule only (last 60 s; |z| >= 4; TRAIN calibration; buys the
  favoured side at a displayed ask 85-98c with calibrated edge >= 0.5c after the fee). The paper engine keeps its own
  $1,000-bank paper book (results/bettor-live.jsonl). Each time that paper book takes a displayed ask under the
  decision-instant rule ('opt'), this file sends ONE real contract: a limit buy at exactly that ask,
  immediate-or-cancel, in the subaccount. It fills now or never rests. A miss may be retried on a later paper take of
  the same market (at most 3 sends a market); once 1 contract is held in a market, that market is done.

  The paper bettor's two fill rules disagree (2026-09-28: 'opt' 11 markets -$54.02, one NEAR loss at ~85c; 'real' --
  size still shown 1 s later -- 3 markets +$9.30). A live IOC lands a few hundred ms after the decision, between the
  two. Whether it gets the offers that lose is the question this answers, at a cost of cents.

WHY A SUBACCOUNT
  pinrun's v-safety2 adopts and hedges any position in its series held in subaccount 0 that it did not book. In a
  subaccount the bettor's contracts are invisible to it (see ladder_live.py for the documented facts).
  self_trade_prevention_type=taker_at_cross: if this order would ever trade against our own resting order, THIS
  order is cancelled, never the other one.

HARD RAILS (code, not flags)
  1 contract per order; at most 1 held per market; at most 3 sends per market; at most 9 contracts held unsettled
  and $10 committed (in flight + held at cost); price 85-98c for the side bought; never within 0.5 s of the close
  and never a decision older than 1.5 s; realized <= -$5 in an ET day halts until the next ET day; realized <= -$8
  since start halts until restarted; an IOC that comes back resting is cancelled and halts; an unreadable answer
  halts until the order record is read back; refuse to start if the subaccount holds more than $25 or its balance
  is unreadable; stop file results/bettor-live.stop halts and exits; at most 3 order writes a second (shared key).

    python research/cleanroom/bettor_live.py --selftest
    python research/cleanroom/bettor_live.py --subaccount 2 --dry-run --minutes 30
    python research/cleanroom/bettor_live.py --subaccount 2 --live --minutes 10080
"""
import argparse
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
import bettor_paper as B                        # noqa: E402
import pintake                                  # noqa: E402  (normalise / _readable / _is_live: pure parsers)

LIVE_LOG = r"C:\kals-repo\results\bettor-live.jsonl"
ORDER_LOG = r"C:\kals-repo\results\bettor-live-orders.jsonl"
STOP_FILE = r"C:\kals-repo\results\bettor-live.stop"
KEY_FILE = r"C:\kals\kalshi.pem"
KEY_ID = "5163259c-ecb0-4966-9053-0d2776cf061e"

SIZE = 1
MAX_PER_MARKET = 1
MAX_SENDS_PER_MARKET = 3
MAX_HELD = 9
MAX_COMMIT = 10.00
MIN_PX, MAX_PX = 0.85, 0.98
DAY_STOP = -5.00
RUN_STOP = -8.00
MAX_SUB_BALANCE = 25.00
LATE_S = 0.5
STALE_S = 1.5
WRITES_PER_S = 3.0
POOL = 2
CID_PREFIX = "bet-"
BROKER = None


def et_day(t):
    return (datetime.fromtimestamp(t, timezone.utc) - timedelta(hours=4)).strftime("%Y-%m-%d")


def fee1(px):
    return math.ceil(0.07 * px * (1 - px) * 100 - 1e-9) / 100.0


def order_body(ticker, side, px, sub, cid):
    """side 'yes' = buy YES at px (bid px); side 'no' = buy NO at px (= sell YES: ask at 1-px). IOC, can cross."""
    px = Decimal(str(px)).quantize(Decimal("0.0001"))
    s, p = ("bid", px) if side == "yes" else ("ask", Decimal(1) - px)
    return {"ticker": ticker, "side": s, "count": "%.2f" % SIZE, "price": "%.4f" % p,
            "time_in_force": "immediate_or_cancel", "self_trade_prevention_type": "taker_at_cross",
            "post_only": False, "client_order_id": cid, "subaccount": int(sub), "exchange_index": POOL}


def body_ok(b, sub):
    """Every order body must carry these, or it is not sent."""
    try:
        yes_px = float(b["price"])
    except Exception:
        return False
    want_px = yes_px if b.get("side") == "bid" else 1.0 - yes_px
    return (b.get("side") in ("bid", "ask") and b.get("post_only") is False
            and b.get("time_in_force") == "immediate_or_cancel"
            and b.get("self_trade_prevention_type") == "taker_at_cross"
            and b.get("subaccount") == int(sub) and int(sub) >= 1 and b.get("exchange_index") == POOL
            and b.get("count") == "%.2f" % SIZE and str(b.get("client_order_id", "")).startswith(CID_PREFIX)
            and MIN_PX - 1e-9 <= want_px <= MAX_PX + 1e-9)


class Broker:
    def __init__(self, log, sub, dry, sender, now):
        self.log, self.sub, self.dry, self.send, self.now = log, int(sub), dry, sender, now
        self.q = queue.Queue()
        self.mk = {}              # ticker -> {"close_s", "side", "sends", "inflight", "n", "cost", "fee"}
        self.orders = {}          # cid -> {"ticker", "side", "px", "status", "kid"}
        self.day, self.day_pnl, self.run_pnl = None, 0.0, 0.0
        self.halt_day = None      # ET day halted by the day stop
        self.halted = None        # reason, until restart (run stop, rested IOC, unknown answer)
        self.stopped = False
        self.lock = threading.Lock()
        self._w = []

    # --- exposure and rails ---
    def exposure(self):
        n = sum(v["n"] + v["inflight"] for v in self.mk.values())
        c = sum(v["cost"] + v["inflight"] * v.get("px_inflight", 0.0) for v in self.mk.values())
        return n, c

    def refusal(self, ticker, px, now):
        if self.stopped:
            return "stopped"
        if self.halted:
            return "halted"
        if self.halt_day == et_day(now):
            return "day_stop"
        v = self.mk.get(ticker)
        if v and v["n"] >= MAX_PER_MARKET:
            return "market_held"
        if v and v["inflight"]:
            return "in_flight"
        if v and v["sends"] >= MAX_SENDS_PER_MARKET:
            return "max_sends"
        if not (MIN_PX - 1e-9 <= px <= MAX_PX + 1e-9):
            return "price"
        n, c = self.exposure()
        if n + SIZE > MAX_HELD:
            return "max_held"
        if c + SIZE * px > MAX_COMMIT + 1e-9:
            return "max_commit"
        return None

    # --- called when the paper bettor takes a displayed ask ('opt') ---
    def want(self, ticker, close_s, side, px, rel=None, z=None, p_cal=None):
        now = self.now()
        with self.lock:
            v = self.mk.get(ticker)
            if v and v["side"] != side:
                why = "side_flip"
            else:
                why = self.refusal(ticker, px, now)
            if why:
                if why not in ("market_held", "in_flight"):
                    self.log.write("refused", ticker=ticker, side=side, px=px, rel=rel, why=why)
                return False
            v = self.mk.setdefault(ticker, {"close_s": close_s, "side": side, "sends": 0, "inflight": 0,
                                            "n": 0, "cost": 0.0, "fee": 0.0})
            v["sends"] += 1
            v["inflight"] = SIZE
            v["px_inflight"] = px
            cid = "%s%d-%d" % (CID_PREFIX, int(now * 1000), len(self.orders))
            self.orders[cid] = {"ticker": ticker, "side": side, "px": px, "status": "queued", "kid": None,
                                "t_dec": now, "close_s": close_s, "rel": rel, "z": z, "p_cal": p_cal}
            self.q.put(("place", cid))
            return True

    def check_stop_file(self):
        if not self.stopped and os.path.exists(STOP_FILE):
            self.stopped = True
            self.log.write("stop_file", path=STOP_FILE)

    # --- fills and results ---
    def _book_fill(self, cid, filled, exec_px, fee_total):
        o = self.orders[cid]
        v = self.mk.get(o["ticker"])
        if v is None:
            self.log.write("fill_after_settle", cid=cid, ticker=o["ticker"], n=filled)
            return
        v["inflight"] = 0
        if filled > 0:
            px = exec_px if exec_px is not None else o["px"]
            v["n"] += filled
            v["cost"] += filled * px
            v["fee"] += fee_total if fee_total is not None else filled * fee1(px)
            self.log.write("live_fill", ticker=o["ticker"], cid=cid, kid=o["kid"], side=o["side"], px=px,
                           asked_px=o["px"], n=filled, fee=round(v["fee"], 4), rel=o["rel"])

    def on_result(self, ticker, result):
        with self.lock:
            v = self.mk.pop(ticker, None)
            if not v or v["n"] <= 0:
                return
            pnl = (v["n"] - v["cost"] if v["side"] == result else -v["cost"]) - v["fee"]
            d = et_day(self.now())
            if d != self.day:
                self.day, self.day_pnl = d, 0.0
            self.day_pnl += pnl
            self.run_pnl += pnl
            self.log.write("live_settle", ticker=ticker, result=result, side=v["side"], n=v["n"],
                           cost=round(v["cost"], 4), fee=round(v["fee"], 4), pnl=round(pnl, 4),
                           day_pnl=round(self.day_pnl, 4), run_pnl=round(self.run_pnl, 4))
            if self.day_pnl <= DAY_STOP + 1e-9 and self.halt_day != d:
                self.halt_day = d
                self.log.write("day_stop", day=d, day_pnl=round(self.day_pnl, 4))
            if self.run_pnl <= RUN_STOP + 1e-9 and not self.halted:
                self.halted = "run_stop %.2f" % self.run_pnl
                self.log.write("run_stop", run_pnl=round(self.run_pnl, 4))

    def forget_unfilled(self, ticker):
        """A market that closed with nothing held carries no money; drop it (a settle would never be booked)."""
        with self.lock:
            v = self.mk.get(ticker)
            if v and v["n"] <= 0 and not v["inflight"]:
                self.mk.pop(ticker, None)

    # --- the one writer thread ---
    def _throttle(self):
        now = time.time()
        self._w = [t for t in self._w if now - t < 1.0]
        if len(self._w) >= WRITES_PER_S:
            time.sleep(max(0.0, 1.0 - (now - self._w[0])))
        self._w.append(time.time())

    def work_once(self, item):
        kind, cid = item
        o = self.orders.get(cid)
        if o is None:
            return
        v = self.mk.get(o["ticker"])
        if kind != "place" or v is None:
            return
        now = self.now()
        late = "late" if now > o["close_s"] - LATE_S else ("stale" if now - o["t_dec"] > STALE_S else None)
        if late or self.stopped:
            o["status"] = "dropped"
            with self.lock:
                v["inflight"] = 0
            self.log.write("dropped", ticker=o["ticker"], cid=cid, why=late or "stopped", age=round(now - o["t_dec"], 3))
            return
        b = order_body(o["ticker"], o["side"], o["px"], self.sub, cid)
        if not body_ok(b, self.sub):
            o["status"] = "refused"
            with self.lock:
                v["inflight"] = 0
            self.log.write("body_refused", body=b)
            return
        if self.dry:
            o["status"] = "dry"
            with self.lock:
                v["inflight"] = 0
            self.log.write("would_place", body=b, age=round(now - o["t_dec"], 3))
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
                       age=round(t_send - o["t_dec"], 3), rtt=round(time.time() - t_send, 3), resp=str(r)[:300])
        with self.lock:
            if st is not None and 400 <= st < 500:
                o["status"] = "rejected"
                v["inflight"] = 0
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
            self._book_fill(cid, int(round(out["filled"])), out["exec_price"], out["fee_total"])
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
            out = pintake.normalise(200, x, order_body(o["ticker"], o["side"], o["px"], self.sub, cid))
            if out["status"] == "resting":
                continue
            with self.lock:
                o["kid"], o["status"] = out.get("order_id"), "recovered"
                self._book_fill(cid, int(round(out["filled"] or 0)), out["exec_price"], out["fee_total"])
            self.log.write("recovered", cid=cid, record=str(x)[:300])

    def run_poller(self):
        while True:
            try:
                if not self.dry:
                    self.poll_unknown_once()
            except Exception as e:
                self.log.write("poll_error", err=repr(e)[:300])
            time.sleep(3.0)


# ---------------------------------------------------------------------------------------------------- engine hooks
_orig = {}


def install_hooks():
    """Mirror each paper 'opt' take into BROKER.want(); tell BROKER each settle. Idempotent."""
    if _orig:
        return
    _orig["add_fill"], _orig["on_result"], _orig["tick"] = B.Engine.add_fill, B.Engine.on_result, B.Engine.tick

    def add_fill(self, m, strat, fm, side, price, size, fee, **extra):
        _orig["add_fill"](self, m, strat, fm, side, price, size, fee, **extra)
        if BROKER is not None and strat == "bettor" and fm == "opt" and extra.get("kind") == "take":
            BROKER.want(m.ticker, m.close_s, side, round(float(price), 4), extra.get("rel"), extra.get("z"),
                        extra.get("p_cal"))

    def on_result(self, ticker, result, ev, now):
        _orig["on_result"](self, ticker, result, ev, now)
        if BROKER is not None and result in ("yes", "no"):
            BROKER.on_result(ticker, result)

    def tick(self):
        closed = [t for t, m in self.markets.items() if not m.done]
        _orig["tick"](self)
        if BROKER is not None:
            BROKER.check_stop_file()
            for t in closed:
                m = self.markets.get(t)
                if m is not None and m.done:
                    BROKER.forget_unfilled(t)
    B.Engine.add_fill, B.Engine.on_result, B.Engine.tick = add_fill, on_result, tick


# ---------------------------------------------------------------------------------------------------- self-test
def selftest():
    global STOP_FILE, BROKER
    fails, sink = [], []
    log = B.Logger(None, sink)
    sent = []
    fill_mode = {"v": "fill"}

    def fake_send(method, path, body, query):
        sent.append((method, path, body, query))
        if method == "POST":
            k = "K%d" % len(sent)
            mode = fill_mode["v"]
            if mode == "fill":
                return 201, {"order_id": k, "client_order_id": body["client_order_id"], "fill_count": "1.00",
                             "remaining_count": "0.00", "average_fill_price": body["price"],
                             "average_fee_paid": "0.0100"}
            if mode == "miss":
                return 201, {"order_id": k, "fill_count": "0.00", "remaining_count": "0.00"}
            if mode == "rest":
                return 201, {"order_id": k, "fill_count": "0.00", "remaining_count": "1.00"}
            if mode == "garbled":
                return 201, {"order_id": k}
            if mode == "reject":
                return 400, '{"error": {"code": "insufficient_balance"}}'
        if method == "GET":
            return 200, {"orders": []}
        return 200, {}
    ck = lambda ok, m: None if ok else fails.append(m)
    # bodies
    b1 = order_body("KXBTC15M-X", "yes", 0.95, 2, "bet-1")
    b2 = order_body("KXBTC15M-X", "no", 0.97, 2, "bet-2")
    ck(b1["side"] == "bid" and b1["price"] == "0.9500", "YES maps to a bid at the ask")
    ck(b2["side"] == "ask" and b2["price"] == "0.0300", "NO maps to an ask at 1-px")
    ck(body_ok(b1, 2) and body_ok(b2, 2), "legal bodies pass")
    ck(not body_ok(dict(b1, time_in_force="good_till_canceled"), 2), "a resting order is refused")
    ck(not body_ok(dict(b1, post_only=True), 2), "post_only (would rest) is refused")
    ck(not body_ok(dict(b1, subaccount=0), 2) and not body_ok(order_body("T", "yes", 0.95, 0, "bet-x"), 0),
       "the primary account (subaccount 0) is refused")
    ck(not body_ok(dict(b1, count="2.00"), 2), "2 contracts is refused")
    ck(not body_ok(order_body("T", "yes", 0.99, 2, "bet-x"), 2) and not body_ok(order_body("T", "no", 0.80, 2, "bet-x"), 2),
       "prices outside 85-98c are refused")
    ck(not body_ok(dict(b1, self_trade_prevention_type="maker"), 2), "maker self-trade mode (cancels OUR resting order) refused")
    ck(fee1(0.95) == 0.01 and fee1(0.85) == 0.01, "taker fee on 1 contract rounds up to 1c")
    # one contract per market; a miss may be retried up to 3 sends
    now = [1000.0]
    br = Broker(log, 2, False, fake_send, lambda: now[0])
    ck(br.want("A", 1030, "yes", 0.95) is True, "first want queues")
    ck(br.want("A", 1030, "yes", 0.95) is False, "a second want while in flight is ignored")
    br.work_once(br.q.get())
    ck(br.mk["A"]["n"] == 1 and abs(br.mk["A"]["cost"] - 0.95) < 1e-9, "filled 1 at 0.95")
    ck(br.want("A", 1030, "yes", 0.96) is False, "a held market is never bought again")
    fill_mode["v"] = "miss"
    for i in range(4):
        if br.want("B", 1030, "no", 0.97):
            br.work_once(br.q.get())
    ck(br.mk["B"]["sends"] == 3 and br.mk["B"]["n"] == 0, "a missing market is sent at most 3 times")
    ck(any(r["ev"] == "refused" and r["why"] == "max_sends" for r in sink), "the 4th send is refused")
    ck(br.want("C", 1030, "no", 0.84) is False, "84c is refused")
    # late / stale decisions are dropped, never sent
    n0 = len(sent)
    br.want("D", 1030, "yes", 0.95)
    now[0] = 1029.6
    br.work_once(br.q.get())
    br.want("E", 2000, "yes", 0.95)
    now[0] = 1031.2
    br.work_once(br.q.get())
    ck(len(sent) == n0 and len([r for r in sink if r["ev"] == "dropped"]) == 2, "late (<0.5 s to close) and stale (>1.5 s) are dropped")
    # the 9-contract / $10 rails
    fill_mode["v"] = "fill"
    br2 = Broker(log, 2, False, fake_send, lambda: now[0])
    for i in range(12):
        if br2.want("M%d" % i, 5000, "yes", 0.98):
            br2.work_once(br2.q.get())
    n, c = br2.exposure()
    ck(n == 9 and c <= MAX_COMMIT + 1e-9, "never more than 9 contracts / $10 held (%d, %.2f)" % (n, c))
    # settle: win and loss arithmetic, day stop, next-day reset, run stop
    br3 = Broker(log, 2, False, fake_send, lambda: now[0])
    now[0] = 1_790_000_000.0
    for t in ("W", "L"):
        br3.want(t, now[0] + 30, "yes", 0.95)
        br3.work_once(br3.q.get())
    br3.on_result("W", "yes")
    br3.on_result("L", "no")
    st = [r for r in sink if r["ev"] == "live_settle"]
    ck(abs(st[-2]["pnl"] - 0.04) < 1e-9 and abs(st[-1]["pnl"] - (-0.96)) < 1e-9, "win +0.04, loss -0.96 after the 1c fee")
    br3.day_pnl = -4.5
    br3.want("L2", now[0] + 30, "yes", 0.95)
    br3.work_once(br3.q.get())
    br3.on_result("L2", "no")
    ck(br3.halt_day == et_day(now[0]) and br3.want("X", now[0] + 30, "yes", 0.95) is False, "-$5 in an ET day halts new orders")
    now[0] += 86400
    ck(br3.want("Y", now[0] + 30, "yes", 0.95) is True, "the next ET day trades again")
    br3.work_once(br3.q.get())
    br3.run_pnl = -7.5
    br3.on_result("Y", "no")
    now[0] += 86400
    ck(br3.halted and br3.want("Z", now[0] + 30, "yes", 0.95) is False, "-$8 since start halts until restart")
    # a resting IOC is cancelled and halts; a garbled answer halts; a 4xx is just a rejection
    for mode, halts, dels in (("rest", True, 1), ("garbled", True, 0), ("reject", False, 0)):
        fill_mode["v"] = mode
        b4 = Broker(log, 2, False, fake_send, lambda: 1000.0)
        n_del = len([s for s in sent if s[0] == "DELETE"])
        b4.want("R", 1030, "yes", 0.95)
        b4.work_once(b4.q.get())
        ck(bool(b4.halted) == halts and len([s for s in sent if s[0] == "DELETE"]) - n_del == dels,
           "%s: halts=%s, cancels=%d" % (mode, halts, dels))
        ck(b4.mk["R"]["inflight"] == (1 if mode == "garbled" else 0), "%s: in-flight kept only when unknown" % mode)
    # stop file halts
    b5 = Broker(log, 2, False, fake_send, lambda: 1000.0)
    open(STOP_FILE + ".selftest", "w").close()
    real = STOP_FILE
    STOP_FILE = STOP_FILE + ".selftest"
    try:
        b5.check_stop_file()
    finally:
        STOP_FILE = real
        os.remove(real + ".selftest")
    ck(b5.stopped and b5.want("S", 1030, "yes", 0.95) is False, "the stop file refuses every order")
    # dry run never sends
    n1 = len(sent)
    b6 = Broker(log, 2, True, fake_send, lambda: 1000.0)
    b6.want("D1", 1030, "yes", 0.95)
    b6.work_once(b6.q.get())
    ck(len(sent) == n1 and any(r["ev"] == "would_place" for r in sink), "dry run sends nothing")
    # driven world: the paper engine's own decision reaches the broker (bettor_paper's planted BTC world)
    fill_mode["v"] = "fill"
    install_hooks()
    C = 1_000_000
    clock = [0.0]
    esink = []
    eng = B.Engine(B.Logger(None, esink), lambda: clock[0], B.Tables(), ["bettor"])
    eng.add_market("BTC-T", "BTC", C, Decimal("100.00"), 2, "planted")
    for s in range(C - 240, C + 1):
        eng.on_print("BRTI", s * 1000, ("101.00", "101.01")[s % 2], s + 0.1)
    eng.on_snapshot("BTC-T", {"no_dollars_fp": [["0.0500", "30.00"], ["0.0300", "10.00"], ["0.0100", "500.00"]]}, 1)
    b7 = Broker(log, 2, False, fake_send, lambda: clock[0])
    BROKER = b7
    try:
        clock[0] = C - 60 + 0.2
        eng.tick()
        ck(b7.q.qsize() == 1, "the paper take at 0.95 (and 0.97) queues exactly ONE live order (got %d)" % b7.q.qsize())
        b7.work_once(b7.q.get())
        last = [s for s in sent if s[0] == "POST"][-1][2]
        ck(last["side"] == "bid" and last["price"] == "0.9500" and last["ticker"] == "BTC-T" and last["subaccount"] == 2,
           "the live order is a YES bid at the lowest displayed ask, 0.95, in subaccount 2")
        for rel in range(-59, 0):
            clock[0] = C + rel + 0.2
            eng.tick()
        ck(b7.q.empty(), "no second order in a held market")
        clock[0] = C + 5
        eng.tick()
        eng.on_result("BTC-T", "yes", "101.00", clock[0])
        ls = [r for r in sink if r["ev"] == "live_settle" and r["ticker"] == "BTC-T"]
        ck(len(ls) == 1 and abs(ls[0]["pnl"] - 0.04) < 1e-9, "the settle books +0.04 on the live contract")
        # empty world: prints on the strike, nothing sent
        eng2 = B.Engine(B.Logger(None, esink), lambda: clock[0], B.Tables(), ["bettor"])
        clock[0] = 2 * C - 100
        eng2.add_market("E-T", "BTC", 2 * C, Decimal("100.00"), 2, "planted")
        for s in range(2 * C - 240, 2 * C + 1):
            eng2.on_print("BRTI", s * 1000, ("99.994", "99.996")[s % 2], s + 0.1)
        eng2.on_snapshot("E-T", {"no_dollars_fp": [["0.1000", "500.00"]], "yes_dollars_fp": [["0.8900", "500.00"]]}, 1)
        for rel in range(-60, -40):             # (bettor_paper's own window; by rel -1 the average is decided)
            clock[0] = 2 * C + rel + 0.2
            eng2.tick()
        ck(b7.q.empty(), "coin-flip world (index on the strike): nothing sent")
        # no book at all: a certain side and nothing to buy -> nothing sent
        eng3 = B.Engine(B.Logger(None, esink), lambda: clock[0], B.Tables(), ["bettor"])
        clock[0] = 3 * C - 100
        eng3.add_market("N-T", "BTC", 3 * C, Decimal("100.00"), 2, "planted")
        for s in range(3 * C - 240, 3 * C + 1):
            eng3.on_print("BRTI", s * 1000, ("101.00", "101.01")[s % 2], s + 0.1)
        for rel in range(-60, 0):
            clock[0] = 3 * C + rel + 0.2
            eng3.tick()
        ck(b7.q.empty(), "no book: nothing sent")
    finally:
        BROKER = None
    # the only write endpoints in this file: create order, and cancel of an IOC that rested
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src[:src.index("\ndef selftest" + "():")]
    ck(body.count('"POST"') == 1 and body.count('"DELETE"') == 1 and "/portfolio/subaccounts" not in body
       and "intra_exchange" not in body, "working code: one POST (create order), one DELETE (cancel), no money movement")
    print("bettor_live self-test " + ("PASSED" if not fails else "FAILED: " + "; ".join(fails)))
    return not fails


# ---------------------------------------------------------------------------------------------------- main
def main():
    global BROKER
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--subaccount", type=int)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--minutes", type=float, default=10080)
    a = ap.parse_args()
    B.selftest()                                   # raises on failure
    if not selftest():
        raise SystemExit("self-test failed; refusing to run")
    if a.selftest:
        return 0
    if not a.subaccount or a.subaccount < 1:
        raise SystemExit("--subaccount N (1..63) is required; the primary account is refused")
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
    if sub_bal > MAX_SUB_BALANCE:
        raise SystemExit("subaccount holds $%.2f > $%.2f; this is a penny test -- refusing" % (sub_bal, MAX_SUB_BALANCE))
    if a.live and sub_bal < 3.0:
        raise SystemExit("subaccount holds $%.2f; fund it first (ordercli --sub-fund)" % sub_bal)
    if os.path.exists(STOP_FILE):
        raise SystemExit("stop file present: %s" % STOP_FILE)
    B.NAME, B.LOG_PATH, B.STRATS = "bettor_live", LIVE_LOG, ("bettor",)
    orig_init = B.Engine.__init__

    def init(self, log, now_fn, tables, strats=("bettor",)):
        orig_init(self, log, now_fn, tables, ("bettor",))
    B.Engine.__init__ = init
    olog = B.Logger(ORDER_LOG)
    br = Broker(olog, a.subaccount, a.dry_run, sender, time.time)
    olog.write("start", pid=os.getpid(), subaccount=a.subaccount, live=a.live, sub_balance=sub_bal,
               rails={"size": SIZE, "per_market": MAX_PER_MARKET, "sends_per_market": MAX_SENDS_PER_MARKET,
                      "max_held": MAX_HELD, "max_commit": MAX_COMMIT, "px": [MIN_PX, MAX_PX], "day_stop": DAY_STOP,
                      "run_stop": RUN_STOP, "late_s": LATE_S, "stale_s": STALE_S, "writes_per_s": WRITES_PER_S})
    threading.Thread(target=br.run_writer, daemon=True).start()
    threading.Thread(target=br.run_poller, daemon=True).start()
    install_hooks()
    BROKER = br
    orig_tick = B.Engine.tick

    def tick(self):
        orig_tick(self)
        if br.stopped and br.q.empty():
            olog.write("exit", why="stop file")
            os._exit(0)
    B.Engine.tick = tick
    B.Logger(LIVE_LOG).write("selftest", passed=True, checks=0)
    B.run_live(a.minutes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
