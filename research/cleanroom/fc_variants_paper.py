#!/usr/bin/env python3
r"""fc_variants_paper.py -- PAPER: the clean-room forecaster and its loss-cutting variants side by side on the live feed.

Operator 2026-09-29: "start working on methods that keep its great earning potential but minimizes losses and test
them on the side as a paper to that. See if your version would've out earned or earned less or saved any losses."

One WebSocket feed (bettor_paper's WS/Rest, GET and market-data subscriptions only), one shared order book and index
store, and one fc_variants.VEngine per variant (each with its own positions, caps and fills). 'base' is the forecaster
exactly as bettor_paper.py runs it, so base here must match cleanroom-bettor.jsonl's forecaster market for market --
that is the check that the side-by-side plumbing is sound. Every number is PAPER (the displayed-offer population,
priced with the 1-s survival rule); only forecaster_live.py's real orders say what WE get.

NOTHING here can send an order: the self-test scans this file for order endpoints and write verbs.

    python research/cleanroom/fc_variants_paper.py --selftest
    python research/cleanroom/fc_variants_paper.py --variants base,one_side,... --minutes 10080
Log: C:\kals-repo\results\fcvar-paper.jsonl (fills, taker orders/misses, settles, close summaries per variant: field v).
"""
import argparse
import json
import os
import queue
import sys
import time
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import bettor_paper as B                        # noqa: E402
import fc_variants as FV                        # noqa: E402

LOG_PATH = r"C:\kals-repo\results\fcvar-paper.jsonl"
DEFAULT_VARIANTS = ("base,race05_98,race1_98,race05_98_hedge40,hedge40,stable2,stable3,stable3_hedge40,"
                    "stable2_race05_98_hedge40,stable3_race05_98_hedge40,p95,r20,flow_ok,survive2")
DROP = {"decision", "market", "market_update", "ws_subscribe"}


class VLogger(B.Logger):
    """Tags every record with the variant name; drops the per-second decision stream (16 engines x 9 markets)."""

    def __init__(self, name, path=None, sink=None, fh=None):
        super().__init__(None, sink)
        self.name = name
        self.fh = fh

    def write(self, ev, **kw):
        if ev in DROP:
            return
        kw["v"] = self.name
        super().write(ev, **kw)


def make_engines(names, now_fn, tables, fh=None, sink=None):
    """Engines share ONE book store, ONE index store and ONE best-ask clock -- market data, not strategy state."""
    books, prints, best = {}, {}, {}
    engines = []
    for n in names:
        e = FV.VEngine(VLogger(n, fh=fh, sink=sink), now_fn, tables, FV.VARIANTS[n], n)
        e.books, e.prints, e.best = books, prints, best
        engines.append(e)
    return engines


class Fanout:
    """Feed events: market data goes through the first engine once (shared stores); strategy events go to every one."""

    def __init__(self, engines):
        self.e = engines
        self.lead = engines[0]

    def on_print(self, *a):
        self.lead.on_print(*a)

    def on_snapshot(self, ticker, msg, seq, sid=None):
        if any(ticker in e.markets for e in self.e):
            self.lead.books.setdefault(ticker, B.Book()).load(msg, seq, sid)
            self.lead._mark_best(ticker)

    def on_delta(self, ticker, msg, seq, sid=None):
        self.lead.on_delta(ticker, msg, seq, sid)

    def on_gap(self):
        self.lead.on_gap()

    def on_trade(self, ticker, msg):
        for e in self.e:
            e.on_trade(ticker, msg)

    def add_market(self, *a):
        for e in self.e:
            e.add_market(*a)

    def tick(self):
        for e in self.e:
            e.tick()

    def on_result(self, ticker, result, ev, now):
        for e in self.e:
            e.on_result(ticker, result, ev, now)


def run_live(names, minutes, log_path=LOG_PATH):
    sys.path.insert(0, r"C:\kals-repo\research")
    import kauth  # request-signing helpers only (GET + WebSocket auth)
    fh = open(log_path, "a", encoding="utf-8")
    log = VLogger("_", fh=fh)
    q = queue.Queue()
    engines = make_engines(names, time.time, B.Tables(), fh=fh)
    fan = Fanout(engines)
    lead = fan.lead
    ws = B.WS(q, log, kauth.headers)
    ws.index_ids = [B.COINS[c][1] for c in B.COINS]
    rest = B.Rest(q, log, kauth.get)
    log.write("start", pid=os.getpid(), minutes=minutes, variants=names,
              params={n: FV.VARIANTS[n] for n in names})
    ws.start()
    rest.start()
    t_end = time.time() + minutes * 60
    last_health = time.time()
    last_active = None
    last_resync = 0
    seq_last = {}
    asked = set()
    tick_max, drain_max = 0.0, 0
    while time.time() < t_end:
        drained = 0
        while drained < 5000:
            try:
                rx, obj = q.get_nowait()
            except queue.Empty:
                break
            drained += 1
            t = obj.get("type")
            if t == "cfbenchmarks_value":
                msg = obj["msg"]
                try:
                    data = json.loads(msg["data"])
                    fan.on_print(msg["index_id"], int(data["time"]), data["value"], rx)
                except Exception as e:
                    log.write("bad_print", err=str(e)[:100])
            elif t == "orderbook_delta":
                sid, seq = obj.get("sid"), obj.get("seq")
                exp = seq_last.get(sid)
                if exp is not None and seq != exp + 1:
                    fan.on_gap()
                    log.write("seq_gap", sid=sid, expected=exp + 1, got=seq)
                seq_last[sid] = seq
                fan.on_delta(obj["msg"]["market_ticker"], obj["msg"], seq, sid)
            elif t == "orderbook_snapshot":
                sid, seq = obj.get("sid"), obj.get("seq")
                seq_last[sid] = seq
                fan.on_snapshot(obj["msg"]["market_ticker"], obj["msg"], seq, sid)
            elif t == "trade":
                sid, seq = obj.get("sid"), obj.get("seq")
                seq_last[sid] = seq
                try:
                    fan.on_trade(obj["msg"]["market_ticker"], obj["msg"])
                except Exception as e:
                    log.write("bad_trade", err=str(e)[:200])
            elif t == "_rest_markets":
                for coin, mk in obj["markets"]:
                    try:
                        args = B.market_from_rest(coin, mk, obj["doge_prev"], lead.last_expiration)
                        if args[2] - time.time() < 1800:
                            fan.add_market(*args)
                    except Exception as e:
                        log.write("bad_market", ticker=mk.get("ticker"), err=str(e)[:200])
            elif t == "_rest_result":
                fan.on_result(obj["ticker"], obj["result"], obj["expiration_value"], time.time())
                asked.discard(obj["ticker"])
            elif t == "_ws_up":
                seq_last = {}
                for b in lead.books.values():
                    b.synced = False
                last_active = None
            elif t == "_ws_down":
                for b in lead.books.values():
                    b.synced = False
            elif t == "error":
                log.write("ws_error_msg", msg=obj.get("msg"))
        now = time.time()
        t_tick = time.perf_counter()
        try:
            fan.tick()
        except Exception as e:
            log.write("tick_error", err=repr(e)[:300])
        tick_max = max(tick_max, time.perf_counter() - t_tick)
        drain_max = max(drain_max, drained)
        active = lead.active_tickers(now)
        if ws.connected and (active != last_active or (lead.resync_wanted and now - last_resync > 5)):
            lead.resync_wanted = False
            last_resync = now
            last_active = active
            ws.set_markets(active)
        for m in lead.markets_needing_result(now):
            if m.ticker not in asked:
                m.settle_asked_at = now
                asked.add(m.ticker)
                rest.settle_jobs.put(m.ticker)
        if now - last_health >= 60:
            log.write("health", ws=ws.connected, reconnects=max(ws.reconnects, 0), rss_mb=B.rss_mb(),
                      markets=len(lead.markets), books_synced=sum(1 for b in lead.books.values() if b.synced),
                      queue=q.qsize(), tick_max_ms=round(1000 * tick_max, 1), drain_max=drain_max,
                      check_late_max_ms=round(1000 * max(getattr(e, "late_max", 0.0) for e in engines), 1),
                      cum={e.name: round(e.cum[("forecaster", "real")], 2) for e in engines})
            tick_max, drain_max = 0.0, 0
            for e in engines:
                e.late_max = 0.0
            last_health = now
        time.sleep(0.02)
    ws.stop = True
    rest.stop = True
    log.write("stop", reason="minutes_elapsed")


def selftest():
    fails = []
    ck = lambda ok, msg: None if ok else fails.append(msg)
    tb = B.Tables()
    C = 1_000_000
    book = {"no_dollars_fp": [["0.2000", "50.00"], ["0.0100", "500.00"]], "yes_dollars_fp": [["0.0100", "40.00"]]}
    dl = {"side": "no", "price_dollars": "0.2000", "delta_fp": "-30.00"}

    def drive(names, shared):
        clock = [C - 200.0]
        sink = []
        if shared:
            engs = make_engines(names, lambda: clock[0], tb, sink=sink)
            fan = Fanout(engs)
        else:
            engs = [FV.VEngine(VLogger(n, sink=sink), lambda: clock[0], tb, FV.VARIANTS[n], n) for n in names]
            fan = None
        for e in engs:
            e.add_market("BTC-T", "BTC", C, Decimal("100.00"), 2, "planted")
        for s in range(C - 240, C + 1):
            if shared:
                fan.on_print("BRTI", s * 1000, ("101.00", "101.01")[s % 2], s + 0.1)
            else:
                for e in engs:
                    e.on_print("BRTI", s * 1000, ("101.00", "101.01")[s % 2], s + 0.1)
        if shared:
            fan.on_snapshot("BTC-T", book, 1)
        else:
            for e in engs:
                e.on_snapshot("BTC-T", book, 1)
        for rel in range(-60, 0):
            clock[0] = C + rel + 0.2
            if rel == -30:
                if shared:
                    fan.on_delta("BTC-T", dl, 2)
                else:
                    for e in engs:
                        e.on_delta("BTC-T", dl, 2)
            for e in engs:
                e.tick()
        clock[0] = C + 5
        for e in engs:
            e.tick()
            e.on_result("BTC-T", "yes", "101.00", clock[0])
        return sorted((r["v"], r["fill"], r["side"], r["price"], r["size"]) for r in sink if r["ev"] == "fill")

    names = ["base", "floor85", "survive2", "r20"]
    a, b = drive(names, True), drive(names, False)
    ck(a == b and a, "shared book/index stores give the same fills as independent engines (%d fills)" % len(a))
    ck(any(x[0] == "base" for x in a) and not any(x[0] == "floor85" for x in a), "variants differ where they should")
    ck(sum(1 for x in a if x[0] == "base" and x[1] == "real") == 1, "the shared delta is applied once (base real fill = 20, not 0)")
    ck(all(v in FV.VARIANTS for v in DEFAULT_VARIANTS.split(",")), "every default variant is defined")
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    ck(src.count("portfolio/" + "orders") == 0 and src.count("/port" + "folio") == 0 and src.count("PO" + "ST") == 0
       and src.count("DEL" + "ETE") == 0 and src.count("url" + "open") == 0, "no order endpoint or write verb in source")
    print("fc_variants_paper self-test " + ("PASSED" if not fails else "FAILED: " + "; ".join(fails)))
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--variants", default=DEFAULT_VARIANTS)
    ap.add_argument("--minutes", type=float, default=10080)
    ap.add_argument("--log", default=LOG_PATH, help="a second side-by-side run writes its own log")
    a = ap.parse_args()
    B.selftest()
    if not (FV.selftest() and selftest()):
        raise SystemExit("self-test failed; refusing to run")
    if a.selftest:
        return 0
    names = a.variants.split(",")
    if names[0] != "base" or any(n not in FV.VARIANTS for n in names):
        raise SystemExit("variants must start with base and be defined in fc_variants.VARIANTS")
    run_live(names, a.minutes, a.log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
