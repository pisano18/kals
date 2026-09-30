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
  shares this API key's rate limit).

    python research/cleanroom/ladder_live.py --selftest
    python research/cleanroom/ladder_live.py --subaccount N --dry-run --minutes 30
    python research/cleanroom/ladder_live.py --subaccount N --live --minutes 10080
"""
import argparse
import json
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


def apply_size(size):
    """v-ladder-size (2026-09-30, operator: "increase ladder"): contracts per bid, with every rail scaled by it --
    10 contracts / $12 committed / -$6 day stop per contract of size; start balance $25 + $12 per extra contract."""
    global SIZE, MAX_CONTRACTS, MAX_COMMIT, DAY_STOP, MAX_SUB_BALANCE
    n = int(size)
    if not (1 <= n <= 20):
        raise SystemExit("--size %s is outside 1..20" % size)
    SIZE = Decimal(n)
    MAX_CONTRACTS = 10 * n
    MAX_COMMIT = 12.00 * n
    DAY_STOP = -6.00 * n
    MAX_SUB_BALANCE = 25.00 + 12.00 * (n - 1)
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

    # --- exposure and rails ---
    def open_orders(self):
        return [v for v in self.live.values() if v["status"] in ("sending", "resting")]

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
    a = ap.parse_args()
    if not selftest() or not P.selftest():
        raise SystemExit("self-test failed; refusing to run")
    if a.selftest:
        return 0
    if not a.subaccount or a.subaccount < 1:
        raise SystemExit("--subaccount N (1..63) is required; the primary account is refused")
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
    if sub_bal > MAX_SUB_BALANCE:
        raise SystemExit("subaccount holds $%.2f > $%.2f; this is a penny test -- refusing" % (sub_bal, MAX_SUB_BALANCE))
    if a.live and sub_bal < 3.0:
        raise SystemExit("subaccount holds $%.2f; fund it first (ordercli --sub-fund)" % sub_bal)
    if os.path.exists(STOP_FILE):
        raise SystemExit("stop file present: %s" % STOP_FILE)
    P.NAME, P.LOG_PATH, P.SIZE = "ladder_live", LIVE_LOG, SIZE
    olog = P.Logger(ORDER_LOG)
    br = Broker(olog, a.subaccount, a.dry_run, sender, time.time)
    olog.write("start", pid=os.getpid(), subaccount=a.subaccount, live=a.live, sub_balance=sub_bal,
               rails={"size": int(SIZE), "max_contracts": MAX_CONTRACTS, "max_commit": MAX_COMMIT, "day_stop": DAY_STOP,
                      "max_live_per_close": MAX_LIVE_PER_CLOSE, "live_levels": list(LIVE_LEVELS),
                      "writes_per_s": WRITES_PER_S})
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
