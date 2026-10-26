#!/usr/bin/env python3
r"""fxtake_live.py -- the FX / commodity 15-minute TAKER, penny size, in a Kalshi SUBACCOUNT.

Operator 2026-10-25: "Keep working on commodity find whatever works even if it's new then start a live penny test
once it's discovered."

WHAT IT DOES
  Watches the order books of the 13 FX / commodity 15-minute series (KXWTI15M, KXBRENT15M, KXNATGAS15M, KXGOLD15M,
  KXSILVER15M, KXCOPPER15M, KXPLATINUM15M, KXPALLADIUM15M, KXEURUSD15M, KXGBPUSD15M, KXUSDJPY15M, KXAUDUSD15M,
  KXUSDCAD15M). In the last ENTRY_FROM..ENTRY_TO seconds of a market (default 30..15), when one side's best BID is
  already >= FAV (0.98) and that side is OFFERED at <= CAP (0.99), it buys SIZE contracts of that side with ONE
  immediate-or-cancel limit at CAP. One order per market, ever. Nothing is held past the close; Kalshi settles.
  Why this rule (results/IDEA_LEDGER.md LS09/LS10, .sweep/q-2026-10-25-fx/fx_book.py on the 10-23 tape): with the
  bid >= 98c the favourite lost 0 of 425 markets at T-30; the offers that remain are stale 1c lottery bids on the
  other side (= 99c asks) and market-maker asks at 99.8-99.9c, almost all within 30 s of the bid reaching 98c.
  Buying 95-97.9c favourites LOST money (4 flips in 97). Fee: Kalshi's quadratic 0.07 x p x (1-p), rounded UP to the
  cent per order, so 1 contract at 99c earns nothing; SIZE 10 earns 9c a market and risks $9.90.

WHY A SUBACCOUNT
  The main pin bot (pinrun.py) adopts and hedges positions in ITS series in subaccount 0 that it did not book; these
  series are not its, but a subaccount keeps the pots separate for botstats and the money reads. exchange_index 2:
  these series are in pool 2 like the crypto 15M markets (GET /series/KXGOLD15M -> exchange_index 2).

HARD RAILS (code, not flags unless said)
  SIZE contracts per order (--size, default 10, max 50); ONE order per market; <= MAX_PER_CLOSE orders a quarter-hour;
  held + in flight <= MAX_HELD dollars; stop for the ET day after DAY_STOP realized; limit price exactly CAP, inside
  0.98..0.99; immediate_or_cancel, post_only False, self_trade_prevention taker_at_cross; subaccount >= 1 and
  exchange_index 2 on every body; no order inside LATE_S of the close; no order on a book without a snapshot or
  older than STALE_S since its last message when a trade printed; <= WRITES_PER_S order writes a second (the key is
  shared with the live bots); stop file results/fxtake-live.stop stops new orders and exits when flat; refuses to
  start if the subaccount balance is unreadable or the stop file is present.

    python research/cleanroom/fxtake_live.py --selftest
    python research/cleanroom/fxtake_live.py --subaccount N --dry-run --minutes 120
    python research/cleanroom/fxtake_live.py --subaccount N --live --minutes 10080
"""
import argparse
import asyncio
import json
import math
import os
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

SERIES = ("KXWTI15M", "KXBRENT15M", "KXNATGAS15M", "KXGOLD15M", "KXSILVER15M", "KXCOPPER15M", "KXPLATINUM15M",
          "KXPALLADIUM15M", "KXEURUSD15M", "KXGBPUSD15M", "KXUSDJPY15M", "KXAUDUSD15M", "KXUSDCAD15M")
RESULTS = r"C:\kals-repo\results"
LOG = os.path.join(RESULTS, "fxtake-live-orders.jsonl")
STOP_FILE = os.path.join(RESULTS, "fxtake-live.stop")
KEY_FILE = r"C:\kals\kalshi.pem"
KEY_ID = "5163259c-ecb0-4966-9053-0d2776cf061e"
REST = "https://api.elections.kalshi.com/trade-api/v2"
WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
WS_PATH = "/trade-api/ws/v2"
POOL = 2                     # commodities: exchange_index 2 (with the crypto markets)
POOLS = (0, 2)               # the FX pairs are exchange_index 0 ('Financials'): each market's pool is READ from Kalshi at
                             # discovery and sent on its order; an order in the wrong pool answers 404 market_not_found (10-25 18:00 ET)
CID_PREFIX = "fxt-"

SIZE = 10
SIZE_MAX = 50
FAV = 0.98
CAP = 0.99
ENTRY_FROM = 30.0
ENTRY_TO = 15.0
LATE_S = 1.0
STALE_S = 5.0
MAX_PER_CLOSE = 6           # per POOL (pot) and close: 10-25 the FX pairs got their own pot (subaccount 4, pool 0) so they
MAX_HELD = 70.0             # never crowd out a commodity buy; both caps count each pot on its own
DAY_STOP = -25.0
WRITES_PER_S = 2


# ---------------------------------------------------------------------------------------------------- time
def et_offset_s(t):
    """US Eastern offset for epoch t: EDT (-4 h) from the 2nd Sunday of March 07:00Z to the 1st Sunday of
    November 06:00Z, else EST (-5 h)."""
    y = datetime.fromtimestamp(t, timezone.utc).year
    mar = datetime(y, 3, 1, tzinfo=timezone.utc)
    second_sun = mar + timedelta(days=(6 - mar.weekday()) % 7 + 7)
    nov = datetime(y, 11, 1, tzinfo=timezone.utc)
    first_sun = nov + timedelta(days=(6 - nov.weekday()) % 7)
    start = second_sun.replace(hour=7).timestamp()
    end = first_sun.replace(hour=6).timestamp()
    return -4 * 3600 if start <= t < end else -5 * 3600


def et_day(t):
    return datetime.fromtimestamp(t + et_offset_s(t), timezone.utc).strftime("%Y-%m-%d")


def parse_iso(s):
    return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()


def fee(n, px):
    return math.ceil(0.07 * px * (1 - px) * n * 100 - 1e-9) / 100.0


# ---------------------------------------------------------------------------------------------------- log
class Logger:
    def __init__(self, path=None, sink=None):
        self.path, self.sink = path, sink
        self.lock = threading.Lock()

    def write(self, kind, **kw):
        rec = {"t": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "kind": kind}
        rec.update(kw)
        line = json.dumps(rec, default=str)
        with self.lock:
            if self.sink is not None:
                self.sink.append(rec)
            if self.path:
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")


# ---------------------------------------------------------------------------------------------------- book
class Book:
    """Resting bids per side; the ask for a side is 1 - the other side's best bid."""

    def __init__(self):
        self.yes, self.no = {}, {}
        self.synced = False
        self.last_msg = None
        self.last_trade = None

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
        """[(ask px asc, qty)] for buying `side`, from the other side's bids."""
        d = self.no if side == "yes" else self.yes
        return sorted((round(1 - p, 4), q) for p, q in d.items() if q > 1e-9)

    def fresh(self, now):
        if not self.synced or self.last_msg is None:
            return False
        if self.last_trade is not None and self.last_trade > self.last_msg + STALE_S:
            return False                                             # a trade printed, the book never moved: stale feed
        return True


# ---------------------------------------------------------------------------------------------------- rule
def pick(book, now):
    """The side to buy, its best bid, best ask and the offered contracts at <= CAP, or None."""
    if not book.fresh(now):
        return None
    for side in ("yes", "no"):
        bb = book.best_bid(side)
        if bb is None or bb < FAV - 1e-9:
            continue
        asks = [(p, q) for p, q in book.asks(side) if p <= CAP + 1e-9]
        if not asks:
            return None
        return {"side": side, "bid": bb, "ask": asks[0][0], "offered": round(sum(q for _, q in asks), 2)}
    return None


def order_body(ticker, side, px, n, sub, cid, pool=POOL):
    """side 'yes' = buy YES at px (bid px); side 'no' = buy NO at px (= sell YES: ask at 1-px). IOC, never rests.
    `pool` is the market's own exchange_index, read from Kalshi."""
    s, p = ("bid", px) if side == "yes" else ("ask", round(1 - px, 4))
    return {"ticker": ticker, "side": s, "count": "%.2f" % n, "price": "%.4f" % p,
            "time_in_force": "immediate_or_cancel", "self_trade_prevention_type": "taker_at_cross",
            "post_only": False, "client_order_id": cid, "subaccount": int(sub), "exchange_index": int(pool)}


def body_ok(b, sub, pool=POOL):
    """Every order body must carry these, or it is not sent. The body's pool must be the MARKET's pool, one of POOLS."""
    try:
        n = float(b["count"]); p = float(b["price"])
    except Exception:
        return False
    yes_px = p if b.get("side") == "bid" else round(1 - p, 4)
    return (b.get("side") in ("bid", "ask") and b.get("post_only") is False
            and b.get("time_in_force") == "immediate_or_cancel"
            and b.get("self_trade_prevention_type") == "taker_at_cross"
            and b.get("subaccount") == int(sub) and int(sub) >= 1
            and int(pool) in POOLS and b.get("exchange_index") == int(pool)
            and 0 < n <= SIZE <= SIZE_MAX and abs(yes_px - CAP) < 1e-9 and 0.98 - 1e-9 <= yes_px <= 0.99 + 1e-9
            and str(b.get("client_order_id", "")).startswith(CID_PREFIX))


class Trader:
    """Decisions and money state. Pure except for the sender it is given."""

    def __init__(self, log, sub, dry, sender, now=time.time, subs=None):
        self.log, self.sub, self.dry, self.send, self.now = log, int(sub), dry, sender, now
        # {pool: subaccount}: a Kalshi subaccount lives in ONE pool, so each pot trades its own pool's markets
        # (10-25: commodities = pool 2 in subaccount 5, FX pairs = pool 0 in subaccount 4). Default: one sub everywhere.
        self.subs = {int(p): int(s) for p, s in (subs or {p: sub for p in POOLS}).items()}
        self.markets = {}          # ticker -> {"close_s", "series", "pool"}
        self.pool_cash = None      # {pool: the subaccount's cash there}, read from Kalshi (live); None = not tracked (tests, dry)
        self.books = {}            # ticker -> Book
        self.ordered = set()       # tickers with an order sent (or would-be, dry)
        self.held = {}             # ticker -> {"side", "n", "cost", "fee", "close_s", "settled": bool}
        self.inflight = {}         # ticker -> dollars committed by an unanswered order
        self.per_close = {}        # (close_s, pool) -> orders sent
        self.day, self.day_pnl, self.run_pnl = None, 0.0, 0.0
        self.halt_day = None
        self.halted = None
        self.stopped = False
        self.lock = threading.Lock()
        self._w = []

    # --- state ---
    def pool_of(self, tk):
        return int(self.markets.get(tk, {}).get("pool", POOL))

    def sub_for(self, pool):
        return self.subs.get(int(pool), self.sub)

    def committed(self, pool=None):
        """Dollars at risk (held, unsettled, plus in flight); one pot's only when `pool` is given."""
        ok = (lambda tk: True) if pool is None else (lambda tk: self.pool_of(tk) == int(pool))
        return (sum(v["cost"] for tk, v in self.held.items() if not v["settled"] and ok(tk))
                + sum(x for tk, x in self.inflight.items() if ok(tk)))

    def flat(self):
        return not self.inflight and not any(not v["settled"] for v in self.held.values())

    def check_stop_file(self):
        if not self.stopped and os.path.exists(STOP_FILE):
            self.stopped = True
            self.log.write("stop_file", path=STOP_FILE)

    def stop_reason(self, now):
        if self.stopped:
            return "stopped"
        if self.halted:
            return "halted"
        if self.halt_day == et_day(now):
            return "day_stop"
        return None

    # --- the rule ---
    def decide(self, now):
        """Orders to send now: [(ticker, side, n, pick)]. One per market; every cap applied here."""
        out = []
        with self.lock:
            for tk, m in sorted(self.markets.items(), key=lambda kv: kv[1]["close_s"]):
                tau = m["close_s"] - now
                if tk in self.ordered:
                    continue
                b = self.books.get(tk)
                if tau < ENTRY_TO:                                    # the window closed with no order: say what the book showed
                    self.ordered.add(tk)
                    self.log.write("no_order", ticker=tk, tau=round(tau, 2), synced=bool(b and b.synced), fresh=bool(b and b.fresh(now)),
                                   yes_bid=b.best_bid("yes") if b else None, no_bid=b.best_bid("no") if b else None,
                                   yes_ask=(b.asks("yes") or [(None, 0)])[0][0] if b else None, no_ask=(b.asks("no") or [(None, 0)])[0][0] if b else None)
                    continue
                if b is None or tau > ENTRY_FROM or tau < LATE_S:
                    continue
                p = pick(b, now)
                if p is None:
                    continue
                why = self.stop_reason(now)
                if not why and self.pool_cash is not None:
                    cash = self.pool_cash.get(m.get("pool", POOL))
                    if cash is None or cash < SIZE * CAP - 1e-9:
                        why = "unfunded_pool"                         # no cash in this market's pool: an order would be refused
                pk = (m["close_s"], int(m.get("pool", POOL)))
                if not why and self.per_close.get(pk, 0) >= MAX_PER_CLOSE:
                    why = "per_close"
                if not why and self.committed(pk[1]) + SIZE * CAP > MAX_HELD + 1e-9:
                    why = "held"
                self.ordered.add(tk)                                  # one decision per market, refused or not
                if why:
                    self.log.write("refused", ticker=tk, why=why, tau=round(tau, 2), pool=m.get("pool", POOL), **p)
                    continue
                self.per_close[pk] = self.per_close.get(pk, 0) + 1
                self.inflight[tk] = SIZE * CAP
                out.append((tk, p["side"], SIZE, dict(p, tau=round(tau, 2), pool=m.get("pool", POOL))))
        return out

    # --- sending ---
    def _throttle(self):
        now = time.time()
        self._w = [t for t in self._w if now - t < 1.0]
        if len(self._w) >= WRITES_PER_S:
            time.sleep(max(0.0, 1.0 - (now - self._w[0])))
        self._w.append(time.time())

    def place(self, tk, side, n, p):
        """Blocking: build, rail-check, send (or log a would-be order), book the fill."""
        cid = "%s%d-%s" % (CID_PREFIX, int(self.now() * 1000), tk.split("-")[0][2:6].lower())
        pool = self.pool_of(tk)
        sub = self.sub_for(pool)                                      # the pot that lives in this market's pool
        b = order_body(tk, side, CAP, n, sub, cid, pool)
        close_s = self.markets.get(tk, {}).get("close_s", 0)
        if not body_ok(b, sub, pool):
            with self.lock:
                self.inflight.pop(tk, None)
            self.log.write("body_refused", body=b)
            return
        if self.now() > close_s - LATE_S:
            with self.lock:
                self.inflight.pop(tk, None)
            self.log.write("dropped", ticker=tk, why="late")
            return
        if self.dry:
            with self.lock:
                self.inflight.pop(tk, None)
            self.log.write("would_place", body=b, **p)
            return
        import pintake
        self._throttle()
        t0 = time.time()
        try:
            st, r = self.send("POST", "/portfolio/events/orders", b, None)
        except Exception as e:
            st, r = -1, repr(e)[:300]
        out = pintake.normalise(st, r, b)
        filled = round(float(out["filled"] or 0), 2) if out["parsed"] else 0.0
        self.log.write("placed", body=b, status=st, order_id=out.get("order_id"), filled=filled,
                       remaining=out["remaining"], exec_px=out["exec_price"], fee_total=out["fee_total"],
                       rtt=round(time.time() - t0, 3), resp=str(r)[:300], **p)
        with self.lock:
            self.inflight.pop(tk, None)
            if st is not None and 400 <= st < 500:
                return
            if not pintake._readable(out):
                self.halted = "unknown answer for %s (status %s)" % (cid, st)
                self.log.write("halt", why=self.halted)
                self.held[tk] = {"side": side, "n": 0.0, "cost": 0.0, "fee": 0.0, "close_s": close_s, "settled": False,
                                 "cid": cid, "unknown": True, "sub": sub}
                return
            if pintake._is_live(out) and out.get("order_id"):
                self.halted = "IOC came back resting: %s" % out["order_id"]
                self.log.write("halt", why=self.halted)
                st2, r2 = self.send("DELETE", "/portfolio/events/orders/%s" % out["order_id"], None,
                                    {"subaccount": sub, "exchange_index": pool})
                self.log.write("cancelled", order_id=out["order_id"], status=st2, resp=str(r2)[:200])
            if filled > 0:
                px = out["exec_price"] if out["exec_price"] is not None else CAP
                f = out["fee_total"] if out["fee_total"] is not None else fee(filled, px)
                self.held[tk] = {"side": side, "n": filled, "cost": filled * px, "fee": f, "close_s": close_s,
                                 "settled": False, "cid": cid, "sub": sub}
                self.log.write("fill", ticker=tk, side=side, n=filled, px=px, fee=round(f, 4), cid=cid)

    def recover_unknown(self):
        """Read back any order whose answer was unreadable, from the subaccount's order list."""
        unk = [tk for tk, v in self.held.items() if v.get("unknown")]
        if not unk:
            return
        import pintake
        rows = {}
        for s in sorted({int(self.held[tk].get("sub", self.sub)) for tk in unk}):     # each pot's own order list
            st, r = self.send("GET", "/portfolio/orders", None,
                              {"subaccount": s, "min_ts": int(time.time()) - 3600, "limit": 200})
            if st == 200 and isinstance(r, dict):
                rows.update({x.get("client_order_id"): x for x in r.get("orders") or []})
        for tk in unk:
            v = self.held[tk]
            x = rows.get(v["cid"])
            if x is None:
                continue
            out = pintake.normalise(200, x, order_body(tk, v["side"], CAP, SIZE, v.get("sub", self.sub), v["cid"], self.pool_of(tk)))
            if out["status"] == "resting":
                continue
            with self.lock:
                filled = round(float(out["filled"] or 0), 2)
                px = out["exec_price"] if out["exec_price"] is not None else CAP
                v.update(n=filled, cost=filled * px, fee=out["fee_total"] if out["fee_total"] is not None else fee(filled, px))
                v.pop("unknown", None)
            self.log.write("recovered", ticker=tk, cid=v["cid"], filled=filled, record=str(x)[:300])

    # --- results ---
    def settle(self, tk, result):
        with self.lock:
            v = self.held.get(tk)
            if v is None or v["settled"] or v.get("unknown"):
                return
            v["settled"] = True
            if v["n"] <= 0:
                return
            pnl = (v["n"] - v["cost"] if v["side"] == result else -v["cost"]) - v["fee"]
            d = et_day(self.now())
            if d != self.day:
                self.day, self.day_pnl = d, 0.0
            self.day_pnl += pnl
            self.run_pnl += pnl
            self.log.write("settle", ticker=tk, result=result, side=v["side"], n=v["n"], cost=round(v["cost"], 4),
                           fee=round(v["fee"], 4), pnl=round(pnl, 4), day_pnl=round(self.day_pnl, 4), run_pnl=round(self.run_pnl, 4))
            if self.day_pnl <= DAY_STOP + 1e-9 and self.halt_day != d:
                self.halt_day = d
                self.log.write("day_stop", day=d, day_pnl=round(self.day_pnl, 4))

    def forget(self, now):
        """Drop markets closed more than 20 min ago that hold nothing."""
        with self.lock:
            for tk in [tk for tk, m in self.markets.items() if m["close_s"] < now - 1200]:
                if tk not in self.held or self.held[tk]["settled"]:
                    self.markets.pop(tk, None); self.books.pop(tk, None); self.ordered.discard(tk)
                    self.held.pop(tk, None)
            for c in [c for c in self.per_close if c[0] < now - 1200]:
                del self.per_close[c]


# ---------------------------------------------------------------------------------------------------- live plumbing
def read_pool_cash(sender, subs):
    """{pool: balance_dollars} of each pool's pot (`subs` = {pool: subaccount}, or one subaccount for every pool); an
    unreadable pool is None (its markets are then refused as unfunded_pool, never guessed). None only when EVERY pool is."""
    if not isinstance(subs, dict):
        subs = {p: subs for p in POOLS}
    out = {}
    for pool in POOLS:
        out[pool] = None
        for _try in range(4):                       # the key is shared with the live bots: a 429 is retried, never read as $0
            try:
                st, bal = sender("GET", "/portfolio/balance", None, {"subaccount": int(subs.get(pool)), "exchange_index": pool})
            except Exception:
                st, bal = -1, None
            if st == 429:
                time.sleep(1.5)
                continue
            try:
                out[pool] = float(bal["balance_dollars"]) if st == 200 else None
            except Exception:
                out[pool] = None
            break
    return out if any(v is not None for v in out.values()) else None


def rest_get(path, params=None):
    q = "" if not params else "?" + "&".join("%s=%s" % (k, v) for k, v in params.items())
    req = urllib.request.Request(REST + path + q, method="GET", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read().decode() or "{}")


async def run_live(tr, minutes, log):
    import websockets
    import kauth
    loop = asyncio.get_running_loop()
    end = time.time() + minutes * 60
    ws_state = {"ws": None, "next_id": 1, "sids": {}, "subscribed": set()}

    async def discover():
        """Signed GETs (the unsigned ones hit 429 within a minute), one series a second, a 429 waits 3 s."""
        while time.time() < end:
            for s in SERIES:
                try:
                    st, d = await loop.run_in_executor(None, tr.send, "GET", "/markets", None, {"series_ticker": s, "status": "open", "limit": 5})
                    if st == 429:
                        await asyncio.sleep(3)
                        st, d = await loop.run_in_executor(None, tr.send, "GET", "/markets", None, {"series_ticker": s, "status": "open", "limit": 5})
                    if st != 200 or not isinstance(d, dict):
                        log.write("discover_error", series=s, status=st, err=str(d)[:120])
                    for m in (d.get("markets") or []) if st == 200 and isinstance(d, dict) else []:
                        tk = m.get("ticker"); ct = m.get("close_time"); pool = m.get("exchange_index")
                        if not tk or not ct:
                            continue
                        c = parse_iso(ct)
                        if 0 < c - time.time() < 1200 and tk not in tr.markets:
                            if pool is None or int(pool) not in POOLS:
                                log.write("market_skipped", ticker=tk, why="pool", exchange_index=pool)
                                continue
                            with tr.lock:
                                tr.markets[tk] = {"close_s": c, "series": s, "pool": int(pool)}
                                tr.books[tk] = Book()
                            log.write("market", ticker=tk, close_s=c, pool=int(pool))
                except Exception as e:
                    log.write("discover_error", series=s, err=repr(e)[:200])
                await asyncio.sleep(1.0)
            tr.forget(time.time())
            await asyncio.sleep(45)

    async def subscribe_new(ws):
        want = [tk for tk in list(tr.markets) if tk not in ws_state["subscribed"]]
        if not want:
            return
        i = ws_state["next_id"]; ws_state["next_id"] += 1
        await ws.send(json.dumps({"id": i, "cmd": "subscribe", "params": {"channels": ["orderbook_delta", "trade"], "market_tickers": want}}))
        ws_state["subscribed"].update(want)
        log.write("ws_subscribe", id=i, markets=want)

    async def feed():
        while time.time() < end:
            try:
                hdrs = kauth.headers("GET", WS_PATH)
                async with websockets.connect(WS_URL, additional_headers=hdrs, ping_interval=20, ping_timeout=20, max_size=2 ** 24) as ws:
                    ws_state["ws"] = ws; ws_state["subscribed"] = set()
                    for b in tr.books.values():
                        b.synced = False
                    log.write("ws_up")
                    await subscribe_new(ws)
                    last_sub = time.time()
                    while time.time() < end:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        except asyncio.TimeoutError:
                            raw = None
                        if time.time() - last_sub > 5:
                            await subscribe_new(ws); last_sub = time.time()
                        if raw is None:
                            continue
                        now = time.time()
                        m = json.loads(raw)
                        t = m.get("type"); msg = m.get("msg") or {}
                        if t == "orderbook_snapshot":
                            b = tr.books.get(msg.get("market_ticker"))
                            if b is not None:
                                b.snapshot(msg, now)
                        elif t == "orderbook_delta":
                            b = tr.books.get(msg.get("market_ticker"))
                            if b is not None and b.synced:
                                b.delta(msg, now)
                        elif t == "trade":
                            b = tr.books.get(msg.get("market_ticker"))
                            if b is not None:
                                b.last_trade = now
                        elif t == "error":
                            log.write("ws_error", msg=str(m)[:300])
                            if (msg.get("code") == 25):              # subscription buffer overflow: resubscribe all
                                ws_state["subscribed"] = set()
                                for b in tr.books.values():
                                    b.synced = False
                        elif t == "subscribed":
                            log.write("ws_subscribed", sid=msg.get("sid"), channel=msg.get("channel"))
            except Exception as e:
                log.write("ws_down", err=repr(e)[:200])
                await asyncio.sleep(2)
        ws_state["ws"] = None

    async def decide():
        while time.time() < end:
            tr.check_stop_file()
            now = time.time()
            for tk, side, n, p in tr.decide(now):
                await loop.run_in_executor(None, tr.place, tk, side, n, p)
            if tr.stopped and tr.flat():
                log.write("stopped_flat")
                return
            await asyncio.sleep(0.2)

    async def settle():
        tick = 0
        while time.time() < end:
            now = time.time()
            tick += 1
            if not tr.dry and tick % 4 == 1:                          # the subaccount's cash in each pool, once a minute
                cash = await loop.run_in_executor(None, read_pool_cash, tr.send, tr.subs)
                if cash is not None:
                    tr.pool_cash = cash
            for tk, v in list(tr.held.items()):
                if v["settled"] or v.get("unknown") or now < v["close_s"] + 45:
                    continue
                try:
                    st, d = await loop.run_in_executor(None, tr.send, "GET", "/markets/%s" % tk, None, None)
                    r = (d.get("market") or {}).get("result") if st == 200 and isinstance(d, dict) else None
                    if r in ("yes", "no"):
                        tr.settle(tk, r)
                except Exception as e:
                    log.write("settle_error", ticker=tk, err=repr(e)[:200])
            if not tr.dry:
                try:
                    await loop.run_in_executor(None, tr.recover_unknown)
                except Exception as e:
                    log.write("recover_error", err=repr(e)[:200])
            await asyncio.sleep(15)

    async def health():
        while time.time() < end:
            await asyncio.sleep(300)
            n_books = sum(1 for b in tr.books.values() if b.synced)
            log.write("health", markets=len(tr.markets), books_synced=n_books, held=len([v for v in tr.held.values() if not v["settled"]]),
                      day_pnl=round(tr.day_pnl, 4), run_pnl=round(tr.run_pnl, 4), halted=tr.halted, stopped=tr.stopped,
                      ws_up=ws_state["ws"] is not None)

    tasks = [asyncio.create_task(c()) for c in (discover, feed, decide, settle, health)]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    for t in done:
        if t.exception():
            log.write("task_error", err=repr(t.exception())[:300])


# ---------------------------------------------------------------------------------------------------- selftest
def selftest():
    global STOP_FILE
    fails = []

    def ck(cond, what):
        print(("  ok   " if cond else "  FAIL ") + what)
        if not cond:
            fails.append(what)

    b1 = order_body("KXGOLD15M-26OCT261015-15", "yes", 0.99, 10, 4, "fxt-1-gold")
    ck(body_ok(b1, 4), "a yes buy: bid 0.99, IOC, taker_at_cross, post_only False, sub 4, pool 2")
    b2 = order_body("KXGOLD15M-26OCT261015-15", "no", 0.99, 10, 4, "fxt-2-gold")
    ck(b2["side"] == "ask" and b2["price"] == "0.0100" and body_ok(b2, 4), "a no buy at 0.99 = ask at YES 0.01")
    ck(not body_ok(dict(b1, subaccount=0), 0), "the primary account (subaccount 0) is refused")
    ck(not body_ok(dict(b1, post_only=True), 4), "post_only (would rest) is refused")
    ck(not body_ok(dict(b1, time_in_force="good_till_canceled"), 4), "a resting order is refused")
    ck(not body_ok(dict(b1, price="0.9950"), 4), "a price other than CAP is refused")
    ck(not body_ok(dict(b1, count="51.00"), 4), "count above SIZE is refused")
    ck(not body_ok(dict(b1, exchange_index=0), 4), "a body whose pool is not the market's (0 vs 2) is refused")
    b0 = order_body("KXEURUSD15M-26OCT261015-30", "yes", 0.99, 10, 4, "fxt-3-euru", pool=0)
    ck(b0["exchange_index"] == 0 and body_ok(b0, 4, 0) and not body_ok(b0, 4, 2) and not body_ok(dict(b0, exchange_index=1), 4, 1),
       "an FX pair's order carries its own pool 0 and passes for pool 0 only; pool 1 is never sent")
    ck(not body_ok(dict(b1, client_order_id="pin-1"), 4), "another bot's id prefix is refused")
    # book + rule
    bk = Book(); now = 1000.0
    bk.snapshot({"yes_dollars_fp": [["0.9800", "500.00"], ["0.5000", "75.00"]], "no_dollars_fp": [["0.0100", "6000.00"], ["0.0050", "100.00"]]}, now)
    p = pick(bk, now)
    ck(p and p["side"] == "yes" and p["ask"] == 0.99 and p["offered"] == 6000.0, "yes bid 98c with a 1c no bid -> buy yes at 99c, 6000 offered: %s" % p)
    bk.delta({"side": "no", "price_dollars": "0.0100", "delta_fp": "-6000.00"}, now + 1)
    ck(pick(bk, now + 1) is None, "the 1c lottery bid gone (only 0.5c left = 99.5c ask) -> nothing to buy")
    bk2 = Book(); bk2.snapshot({"yes_dollars_fp": [["0.0300", "10.00"]], "no_dollars_fp": [["0.9900", "200.00"]]}, now)
    p2 = pick(bk2, now)
    ck(p2 and p2["side"] == "no" and p2["ask"] == 0.97 and p2["offered"] == 10.0, "no bid 99c with a 3c yes bid -> buy no at the 97c ask: %s" % p2)
    bk3 = Book(); bk3.snapshot({"yes_dollars_fp": [["0.9700", "100.00"]], "no_dollars_fp": [["0.0100", "100.00"]]}, now)
    ck(pick(bk3, now) is None, "a 97c favourite is not bought")
    bk4 = Book(); bk4.snapshot({"yes_dollars_fp": [["0.9800", "100.00"]], "no_dollars_fp": [["0.0100", "100.00"]]}, now)
    bk4.last_trade = now + 10
    ck(pick(bk4, now + 10) is None, "a book with a trade 10 s after its last message is stale -> nothing")
    ck(pick(Book(), now) is None, "no snapshot yet -> nothing")
    # trader decisions and caps
    sent = []
    log = Logger(sink=sent)
    tr = Trader(log, 4, False, lambda *a: (201, {"order": {"order_id": "k1", "status": "executed", "fill_count": "10.00", "remaining_count": "0.00"}}), now=lambda: T[0])
    T = [now]
    close = now + 20
    for i in range(8):
        tk = "KXS%d15M-26OCT261015-15" % i
        tr.markets[tk] = {"close_s": close, "series": "KXS%d15M" % i}
        b = Book(); b.snapshot({"yes_dollars_fp": [["0.9800", "100.00"]], "no_dollars_fp": [["0.0100", "100.00"]]}, now)
        tr.books[tk] = b
    dec = tr.decide(now)
    ck(len(dec) == MAX_PER_CLOSE and all(tk in tr.ordered for tk in tr.markets), "8 ready markets -> %d orders (MAX_PER_CLOSE) and every market decided once" % len(dec))
    ck(sum(1 for r in sent if r["kind"] == "refused" and r["why"] in ("per_close", "held")) == 2, "the two extra are refused (per_close / held caps): %s" % [r.get("why") for r in sent if r["kind"] == "refused"])
    ck(tr.decide(now) == [], "a second look sends nothing (one order per market)")
    trp = Trader(log, 4, False, lambda *a: (201, {}), now=lambda: T[0])
    trp.pool_cash = {0: 0.0, 2: 100.0}
    for tk, pool in (("P-0", 0), ("P-2", 2)):
        trp.markets[tk] = {"close_s": close, "series": "P", "pool": pool}; trp.books[tk] = tr.books["KXS015M-26OCT261015-15"]
    dp = trp.decide(now)
    ck([d[0] for d in dp] == ["P-2"] and dp[0][3]["pool"] == 2 and any(r["kind"] == "refused" and r["why"] == "unfunded_pool" and r["ticker"] == "P-0" for r in sent),
       "an FX market whose pool holds no cash is refused (unfunded_pool); the commodity market in the funded pool is bought with pool 2 on its order")
    # two pots: commodities (pool 2) in subaccount 5, FX pairs (pool 0) in subaccount 4; each pot has its own per-close cap
    got = []
    def rec(m, p, b, q):
        got.append((m, p, b, q))
        if m == "GET":
            return 200, {"balance_dollars": "60.00" if q["subaccount"] == 4 else "120.00"}
        return 201, {"order": {"order_id": "k2", "status": "executed", "fill_count": "10.00", "remaining_count": "0.00",
                               "average_fill_price": "0.9900" if b["side"] == "bid" else "0.0100"}}
    trs = Trader(log, 5, False, rec, now=lambda: T[0], subs={2: 5, 0: 4})
    cash2 = read_pool_cash(rec, trs.subs)
    ck(cash2 == {0: 60.0, 2: 120.0} and [(q["subaccount"], q["exchange_index"]) for _, _, _, q in got] == [(4, 0), (5, 2)],
       "each pool's cash is read from its own pot: pool 0 = subaccount 4 $60, pool 2 = subaccount 5 $120: %s" % cash2)
    trs.pool_cash = cash2; got.clear()
    for i in range(7):
        trs.markets["C%d-1" % i] = {"close_s": close, "series": "C", "pool": 2}; trs.books["C%d-1" % i] = tr.books["KXS015M-26OCT261015-15"]
    for i in range(5):
        trs.markets["F%d-1" % i] = {"close_s": close, "series": "F", "pool": 0}; trs.books["F%d-1" % i] = tr.books["KXS015M-26OCT261015-15"]
    ds = trs.decide(now)
    ck(sum(1 for d in ds if d[3]["pool"] == 2) == MAX_PER_CLOSE and sum(1 for d in ds if d[3]["pool"] == 0) == 5,
       "7 commodity + 5 FX markets ready -> 6 commodity orders (that pot's cap) and all 5 FX orders (their own pot's cap)")
    for tk, side, n, p in ds:
        trs.place(tk, side, n, p)
    subs_sent = {(b["ticker"][0], b["subaccount"], b["exchange_index"]) for m, _, b, _ in got if m == "POST"}
    ck(subs_sent == {("C", 5, 2), ("F", 4, 0)} and all(v.get("sub") == (4 if tk.startswith("F") else 5) for tk, v in trs.held.items()),
       "commodity orders carry subaccount 5 / pool 2, FX orders subaccount 4 / pool 0: %s" % sorted(subs_sent))
    ck(not body_ok(order_body("F0-1", "yes", 0.99, 10, 0, "fxt-9-f", pool=0), 0, 0), "an FX order for the primary account is refused")
    tr2 = Trader(log, 4, False, lambda *a: (201, {}), now=lambda: T[0])
    tr2.markets["X-1"] = {"close_s": now + 40, "series": "X"}; tr2.books["X-1"] = tr.books["KXS015M-26OCT261015-15"]
    ck(tr2.decide(now) == [], "40 s before the close is outside the 30..15 s window")
    T[0] = now + 20
    d2 = tr2.decide(now + 20)
    ck(len(d2) == 1 and d2[0][1] == "yes" and d2[0][2] == SIZE, "20 s before the close -> one yes order of SIZE")
    # place + fill + settle + day stop
    def filled_at_cap(m, p, b, q):
        """The exchange's answer to a full IOC fill: the average price is in YES terms (0.99 for a bid, 0.01 for an ask)."""
        return 201, {"order": {"order_id": "k9", "status": "executed", "fill_count": "10.00", "remaining_count": "0.00",
                               "average_fill_price": "0.9900" if b["side"] == "bid" else "0.0100"}}
    tr3 = Trader(log, 4, False, filled_at_cap, now=lambda: T[0])
    tr3.markets["M-1"] = {"close_s": now + 100, "series": "M"}
    tr3.inflight["M-1"] = SIZE * CAP
    tr3.place("M-1", "yes", SIZE, {"bid": 0.98, "ask": 0.99, "offered": 50.0, "tau": 20})
    v = tr3.held.get("M-1")
    ck(v is not None and v["n"] == 10 and abs(v["cost"] - 9.9) < 1e-6 and not tr3.inflight, "a filled IOC is held: 10 at 0.99, nothing in flight: %s" % v)
    ck(any(r["kind"] == "placed" and r["body"]["client_order_id"].startswith("fxt-") for r in sent), "the placed record carries the body")
    tr3.settle("M-1", "yes")
    ck(abs(tr3.run_pnl - (10 - 9.9 - fee(10, 0.99))) < 1e-6, "a win books 10c less the 1c fee: %.4f" % tr3.run_pnl)
    tr3.markets["M-2"] = {"close_s": now + 100, "series": "M"}; tr3.inflight["M-2"] = SIZE * CAP
    tr3.place("M-2", "no", SIZE, {"bid": 0.98, "ask": 0.99, "offered": 50.0, "tau": 20})
    tr3.settle("M-2", "yes")
    ck(tr3.halt_day is None and tr3.run_pnl < -9.8, "one loss (-$9.91) does not stop the day: %.2f" % tr3.run_pnl)
    for i in range(3):
        tk = "M-%d" % (3 + i); tr3.markets[tk] = {"close_s": now + 100, "series": "M"}; tr3.inflight[tk] = SIZE * CAP
        tr3.place(tk, "no", SIZE, {"bid": 0.98, "ask": 0.99, "offered": 50.0, "tau": 20}); tr3.settle(tk, "yes")
    ck(tr3.halt_day == et_day(T[0]) and tr3.stop_reason(T[0]) == "day_stop", "three more losses pass -$25 -> day stop")
    # a dry run never calls the sender
    calls = []
    tr4 = Trader(log, 4, True, lambda *a: calls.append(a) or (201, {}), now=lambda: T[0])
    tr4.markets["D-1"] = {"close_s": now + 100, "series": "D"}; tr4.inflight["D-1"] = SIZE * CAP
    tr4.place("D-1", "yes", SIZE, {"bid": 0.98, "ask": 0.99, "offered": 50.0, "tau": 20})
    ck(not calls and any(r["kind"] == "would_place" for r in sent) and not tr4.inflight, "--dry-run logs would_place and sends nothing")
    # a 4xx answer books nothing; an unreadable answer halts
    tr5 = Trader(log, 4, False, lambda *a: (400, '{"error":{"code":"bad"}}'), now=lambda: T[0])
    tr5.markets["E-1"] = {"close_s": now + 100, "series": "E"}; tr5.inflight["E-1"] = SIZE * CAP
    tr5.place("E-1", "yes", SIZE, {"bid": 0.98, "ask": 0.99, "offered": 50.0, "tau": 20})
    ck("E-1" not in tr5.held and tr5.halted is None and not tr5.inflight, "a 400 books nothing and does not halt")
    tr6 = Trader(log, 4, False, lambda *a: (-1, "timeout"), now=lambda: T[0])
    tr6.markets["F-1"] = {"close_s": now + 100, "series": "F"}; tr6.inflight["F-1"] = SIZE * CAP
    tr6.place("F-1", "yes", SIZE, {"bid": 0.98, "ask": 0.99, "offered": 50.0, "tau": 20})
    ck(tr6.halted and tr6.held.get("F-1", {}).get("unknown") and tr6.stop_reason(T[0]) == "halted", "an unreadable answer halts and marks the order unknown")
    # stop file
    real = STOP_FILE
    STOP_FILE = os.path.join(tempfile.gettempdir(), "fxtake-live-selftest-%d.flag" % os.getpid())
    open(STOP_FILE, "w").close()
    try:
        tr7 = Trader(log, 4, False, lambda *a: (201, {}), now=lambda: T[0])
        tr7.check_stop_file()
        tr7.markets["G-1"] = {"close_s": T[0] + 20, "series": "G"}; tr7.books["G-1"] = tr.books["KXS015M-26OCT261015-15"]
        ck(tr7.stopped and tr7.decide(T[0]) == [] and any(r["kind"] == "refused" and r["why"] == "stopped" for r in sent), "the stop file refuses new orders")
    finally:
        os.remove(STOP_FILE)
        STOP_FILE = real
    ck(et_day(1792800000) == "2026-10-23" and et_offset_s(1792800000) == -4 * 3600 and et_offset_s(1793600000) == -5 * 3600,
       "ET day and the Nov 1 2026 clock change")
    ck(fee(10, 0.99) == 0.01 and fee(1, 0.99) == 0.01 and fee(200, 0.99) == 0.14, "fee rounds up to the cent per order")
    print("SELFTEST", "FAILED: %s" % fails if fails else "PASSED")
    return not fails


# ---------------------------------------------------------------------------------------------------- main
def main():
    global SIZE, ENTRY_FROM, ENTRY_TO
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--subaccount", type=int, help="the pot for the commodity markets (pool 2)")
    ap.add_argument("--fx-subaccount", type=int, help="the pot for the FX pairs (pool 0); default: --subaccount (10-25: 4)")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--minutes", type=float, default=10080)
    ap.add_argument("--size", type=int, default=SIZE, help="contracts per order (default %d, max %d)" % (SIZE, SIZE_MAX))
    ap.add_argument("--from", dest="entry_from", type=float, default=ENTRY_FROM, help="earliest entry, seconds before the close (5..60)")
    ap.add_argument("--to", dest="entry_to", type=float, default=ENTRY_TO, help="latest entry, seconds before the close (5..60)")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not (1 <= a.size <= SIZE_MAX) or not (5 <= a.entry_to < a.entry_from <= 60):
        raise SystemExit("--size 1..%d and 5 <= --to < --from <= 60" % SIZE_MAX)
    SIZE, ENTRY_FROM, ENTRY_TO = a.size, a.entry_from, a.entry_to
    if not selftest():
        raise SystemExit("selftest failed; refusing to run")
    if not a.subaccount or a.subaccount < 1:
        raise SystemExit("--subaccount N (1..63) is required; the primary account is refused")
    if a.fx_subaccount is not None and not (1 <= a.fx_subaccount <= 63):
        raise SystemExit("--fx-subaccount N must be 1..63; the primary account is refused")
    subs = {2: a.subaccount, 0: a.fx_subaccount if a.fx_subaccount is not None else a.subaccount}
    if a.live == a.dry_run:
        raise SystemExit("choose exactly one of --live / --dry-run")
    if os.path.exists(STOP_FILE):
        raise SystemExit("stop file present: %s" % STOP_FILE)
    import ordercli
    pk = ordercli.load_key(KEY_FILE)

    def sender(method, path, body, query):
        return ordercli.send(ordercli.PROD, pk, KEY_ID, method, path, body=body, query=query)
    cash = read_pool_cash(sender, subs)
    if cash is None:
        raise SystemExit("subaccount balance unreadable in every pool; refusing")
    sub_bal = sum(v for v in cash.values() if v is not None)
    if a.live and max(v for v in cash.values() if v is not None) < SIZE * CAP:
        raise SystemExit("subaccount holds %s, under one order ($%.2f) in every pool; fund it first (ordercli --sub-fund [--sub-pool 0])" % (cash, SIZE * CAP))
    log = Logger(LOG)
    tr = Trader(log, a.subaccount, a.dry_run, sender, subs=subs)
    if a.live:
        tr.pool_cash = cash
    log.write("start", pid=os.getpid(), subaccount=a.subaccount, subs={str(p): s for p, s in sorted(subs.items())}, live=a.live, dry=a.dry_run,
              sub_balance=sub_bal, pool_cash=cash, size=SIZE, fav=FAV, cap=CAP,
              entry_from=ENTRY_FROM, entry_to=ENTRY_TO, max_per_close=MAX_PER_CLOSE, max_held=MAX_HELD, day_stop=DAY_STOP,
              minutes=a.minutes, series=list(SERIES), argv=sys.argv)
    print("fxtake %s: subaccount %d (%s), size %d, window T-%g..T-%g s, %g minutes; log %s" % (
        "LIVE" if a.live else "dry run", a.subaccount,
        ", ".join("pool %d = subaccount %d %s" % (k, subs[k], "unreadable" if v is None else "$%.2f" % v) for k, v in sorted(cash.items())),
        SIZE, ENTRY_FROM, ENTRY_TO, a.minutes, LOG), flush=True)
    try:
        asyncio.run(run_live(tr, a.minutes, log))
    finally:
        log.write("exit", run_pnl=round(tr.run_pnl, 4), held=len([v for v in tr.held.values() if not v["settled"]]), halted=tr.halted, stopped=tr.stopped)


if __name__ == "__main__":
    main()
