#!/usr/bin/env python3
# VERSION: 2026-09-07-lb1
"""livebook.py -- a real-time Kalshi order book over the WebSocket, for a TAKER.

WHY THIS EXISTS
  pin takes quotes that survive a median ~660 ms. REST polling at 1 Hz across
  9-12 markets got rate-limited and blind, so it cannot win that race. The
  WebSocket `orderbook_delta` channel pushes a full `orderbook_snapshot` on
  subscribe and then every level change, so a local book is current to within
  network latency. This module keeps that book, on its own connection, with
  the same key the collector uses. It never writes anything anywhere.

PROTOCOL -- learned from C:\\kals\\kalshi_collector.py and the tape, not guessed
  auth      RSA-PSS(SHA256, salt=digest len) over  ts_ms + "GET" + "/trade-api/ws/v2"
            headers KALSHI-ACCESS-KEY / -TIMESTAMP / -SIGNATURE, sent as
            additional_headers on wss://api.elections.kalshi.com/trade-api/ws/v2
  subscribe {"id":N,"cmd":"subscribe","params":{"channels":["orderbook_delta"],
             "market_tickers":[...]}}
            -> {"type":"subscribed","id":N,"msg":{"channel":"orderbook_delta","sid":S}}
            A REPEAT subscribe on an already-open channel with new tickers is
            merged into the SAME sid and answered with
            {"type":"ok","id":N,"sid":S,"seq":q,"msg":{"market_tickers":[added]}}
            (seen on disk in kalshi_data/ok/). That is what the collector does
            every 30 s. update_subscription/add_markets is tried first here and
            falls back to that.
  frames    top level: type, sid, seq, msg.  `seq` is per SID, shared by every
            ticker on the subscription, and control frames (ok, snapshot) also
            consume seq numbers -- so the gap check is per sid over ALL frames.
  snapshot  msg: market_ticker, market_id, yes_dollars_fp, no_dollars_fp
            each [[price_str, size_str], ...]; NO ts_ms. A brand-new market's
            snapshot carries no level arrays at all (empty book).
  delta     msg: market_ticker, market_id, price_dollars ("0.9990"), delta_fp
            ("-0.67"), side ("yes"|"no"), ts (ISO), ts_ms (int).
  units     prices are DOLLARS as 4-dp strings; sizes are contracts as 2-dp
            strings and can be fractional. Book keys here are round(float, 4).
  book      "yes" levels are YES bids at p; "no" levels are NO bids at q.
            best YES ask = 1 - best NO bid; best NO ask = 1 - best YES bid.

USAGE
  lb = LiveBook(); lb.start(["KXBTC15M-26SEP072100-00"]); ...; lb.best(tk)
  python livebook.py --selftest          synthetic frames through the live path
  python livebook.py --smoke 20          live 20 s, then REST side-by-side
"""
import argparse
import asyncio
import base64
import json
import logging
import os
import statistics
import sys
import threading
import time
from collections import defaultdict

WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
WS_PATH = "/trade-api/ws/v2"
CHANNEL = "orderbook_delta"

log = logging.getLogger("livebook")


# --------------------------------------------------------------------------
# auth -- identical to kalshi_collector.make_signer
# --------------------------------------------------------------------------
def make_signer(key_id, key_file):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    with open(key_file, "rb") as f:
        pk = serialization.load_pem_private_key(f.read(), password=None)

    def sign(method, path):
        ts = str(int(time.time() * 1000))
        sig = pk.sign(
            (ts + method.upper() + path).encode(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256())
        return {"KALSHI-ACCESS-KEY": key_id,
                "KALSHI-ACCESS-TIMESTAMP": ts,
                "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode()}
    return sign


def _default_key():
    """Key id / file the collector uses. kauth.py (the REST helper) carries
    both; fall back to env vars so the module imports without it."""
    kid = os.environ.get("KALSHI_KEY_ID")
    kf = os.environ.get("KALSHI_KEY_FILE")
    if kid and kf:
        return kid, kf
    try:
        sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
        import kauth                                   # noqa: E402
        return kauth.KEY_ID, kauth.KEY_FILE
    except Exception:
        return kid, kf


def px(v):
    """Price key: float rounded to 4 dp. '0.9990', '0.999', 0.999 all -> 0.999."""
    return round(float(v), 4)


def now_ms():
    return int(time.time() * 1000)


# --------------------------------------------------------------------------
# the book
# --------------------------------------------------------------------------
class LiveBook:
    def __init__(self, key_id=None, key_file=None, url=WS_URL,
                 prefer_update_subscription=True):
        if key_id is None or key_file is None:
            kid, kf = _default_key()
            key_id = key_id or kid
            key_file = key_file or kf
        self.key_id, self.key_file, self.url = key_id, key_file, url
        self.prefer_update = prefer_update_subscription
        self.lock = threading.RLock()
        # ticker -> {"yes": {px: size}, "no": {px: size}}
        self.books = {}
        # ticker -> dict(rx_ms, ts_ms, seq, sid, suspect, snapshots, deltas)
        self.meta = {}
        self.wanted = set()          # tickers we want subscribed
        self.subscribed = set()      # tickers the server has acked
        self.sid = None              # sid of our orderbook_delta subscription
        self.sid_seq = {}            # sid -> last seq seen on that sid
        self.stats = defaultdict(int)
        self.gaps = []               # (wall_ms, sid, expected, got)
        self.frames = []             # last control frames, for the smoke test
        self.latency_ms = []         # rx_ms - ts_ms, deltas only
        self.max_latency_keep = 20000
        self._pending = []           # tickers queued from another thread
        self._cmd_id = 0
        self._pending_cmds = {}      # id -> ("subscribe"|"update", tickers)
        self._loop = None
        self._wake = None
        self._ws = None
        self._thread = None
        self._stop = False
        self._resync = False
        self._watch = {}             # ticker -> [(rx_ms, top3 yes, top3 no)]
        self.connected = threading.Event()

    def watch(self, tk, on=True, n=3):
        """Record the top-n trajectory of a ticker on every applied delta
        (for comparing against a REST read taken while the book moves)."""
        with self.lock:
            if on:
                self._watch[tk] = []
                self._watch_n = n
                if tk in self.books:
                    self._record(tk, now_ms())
            else:
                return self._watch.pop(tk, [])

    def _record(self, tk, rx_ms):
        b = self.books[tk]
        n = getattr(self, "_watch_n", 3)
        self._watch[tk].append((rx_ms,
                                sorted(b["yes"].items(), reverse=True)[:n],
                                sorted(b["no"].items(), reverse=True)[:n]))

    # ---------------- pure book mechanics (self-tested) ----------------
    def _ensure(self, tk):
        if tk not in self.books:
            self.books[tk] = {"yes": {}, "no": {}}
            self.meta[tk] = {"rx_ms": None, "ts_ms": None, "seq": None,
                             "sid": None, "suspect": False, "await_snapshot": False,
                             "snapshots": 0, "deltas": 0, "ooo": 0}

    def _on_connect(self):
        """Reset for a fresh connection: new sid, new seq stream, and every
        existing book is suspect AND must not take a delta until its snapshot
        on THIS connection arrives (the old book plus a new-connection delta
        is not a book). Returns the tickers to subscribe. Sync so the
        self-test can drive it."""
        self.sid = None
        self.sid_seq.clear()
        self._pending_cmds.clear()
        self._resync = False
        with self.lock:
            self.subscribed.clear()
            self._pending.clear()
            for m in self.meta.values():
                m["suspect"] = True
                m["await_snapshot"] = True
            return sorted(self.wanted)

    def apply_snapshot(self, msg, sid, seq, rx_ms):
        """A snapshot REPLACES the book for that ticker."""
        tk = msg.get("market_ticker")
        if not tk:
            self.stats["snapshot_no_ticker"] += 1
            return
        book = {"yes": {}, "no": {}}
        for side, key in (("yes", "yes_dollars_fp"), ("no", "no_dollars_fp")):
            for lv in msg.get(key) or []:
                try:
                    p, s = px(lv[0]), round(float(lv[1]), 2)
                except (TypeError, ValueError, IndexError):
                    self.stats["bad_level"] += 1
                    continue
                if s > 0:
                    book[side][p] = s
        with self.lock:
            self._ensure(tk)
            self.books[tk] = book
            m = self.meta[tk]
            m.update(rx_ms=rx_ms, seq=seq, sid=sid, suspect=False,
                     await_snapshot=False)
            m["snapshots"] += 1
            self.subscribed.add(tk)
        self.stats["snapshots_applied"] += 1

    def apply_delta(self, msg, sid, seq, rx_ms):
        """ADD delta_fp to the level; delete it at <= 0. Rejects a delta whose
        seq is not ahead of the last one applied to this ticker on this sid
        (a replay / out-of-order frame) without touching the book."""
        tk = msg.get("market_ticker")
        side = msg.get("side")
        if not tk or side not in ("yes", "no"):
            self.stats["delta_malformed"] += 1
            return False
        try:
            p = px(msg["price_dollars"])
            d = round(float(msg["delta_fp"]), 2)
        except (KeyError, TypeError, ValueError):
            self.stats["delta_malformed"] += 1
            return False
        with self.lock:
            if tk not in self.books or self.meta[tk]["await_snapshot"]:
                # a delta before any snapshot -- or before this CONNECTION's
                # snapshot: we cannot know the level's true size, so do not
                # build a phantom book from it, and do not patch a stale one.
                self.stats["delta_before_snapshot"] += 1
                return False
            m = self.meta[tk]
            if (seq is not None and m["seq"] is not None and m["sid"] == sid
                    and seq <= m["seq"]):
                m["ooo"] += 1
                self.stats["delta_out_of_order"] += 1
                log.warning("out-of-order delta %s seq %s <= last %s -- ignored",
                            tk, seq, m["seq"])
                return False
            lv = self.books[tk][side]
            new = round(lv.get(p, 0.0) + d, 2)
            if new <= 0:
                lv.pop(p, None)
                if new < 0:
                    self.stats["delta_below_zero"] += 1
            else:
                lv[p] = new
            m.update(rx_ms=rx_ms, seq=seq, sid=sid)
            if tk in self._watch:
                self._record(tk, rx_ms)
            ts = msg.get("ts_ms")
            if ts is not None:
                try:
                    ts = int(ts)
                    m["ts_ms"] = ts
                    self.latency_ms.append(rx_ms - ts)
                    if len(self.latency_ms) > self.max_latency_keep:
                        del self.latency_ms[: len(self.latency_ms) // 2]
                except (TypeError, ValueError):
                    # the level is already updated; a bad timestamp must not
                    # raise past the counters below
                    self.stats["bad_ts_ms"] += 1
            m["deltas"] += 1
        self.stats["deltas_applied"] += 1
        return True

    def _check_seq(self, sid, seq):
        """Per-sid gap check over EVERY frame that carries sid+seq."""
        if sid is None or seq is None:
            return
        prev = self.sid_seq.get(sid)
        if prev is not None and seq != prev + 1:
            self.stats["seq_gaps"] += 1
            self.gaps.append((now_ms(), sid, prev + 1, seq))
            log.error("SEQ GAP sid=%s expected %s got %s -- books on this sid "
                      "are suspect until a fresh snapshot", sid, prev + 1, seq)
            with self.lock:
                for tk, m in self.meta.items():
                    if m["sid"] == sid:
                        m["suspect"] = True
            self._resync = True
            self._poke()          # reconnect now, not at the next 0.5 s tick
        self.sid_seq[sid] = seq

    def on_frame(self, raw, rx_ms=None):
        """The one entry point for every WebSocket frame, live or synthetic."""
        rx_ms = now_ms() if rx_ms is None else rx_ms
        try:
            m = json.loads(raw)
        except Exception:
            self.stats["unparseable"] += 1
            return
        t = m.get("type", "unknown")
        self.stats[t] += 1
        sid, seq = m.get("sid"), m.get("seq")
        self._check_seq(sid, seq)
        msg = m.get("msg") or {}
        if t == "orderbook_snapshot":
            self.apply_snapshot(msg, sid, seq, rx_ms)
        elif t == "orderbook_delta":
            self.apply_delta(msg, sid, seq, rx_ms)
        elif t == "subscribed":
            if msg.get("channel") == CHANNEL:
                self.sid = msg.get("sid")
            self._ack(m.get("id"))
            self._keep(m, rx_ms)
        elif t == "ok":
            self._ack(m.get("id"))
            self._keep(m, rx_ms)
        elif t == "error":
            log.error("ws error frame: %s", raw[:400])
            self._keep(m, rx_ms)
            cid = m.get("id")
            kind, tks = self._pending_cmds.pop(cid, (None, None))
            if kind == "update":
                # update_subscription refused -> mirror the collector
                self.stats["update_subscription_refused"] += 1
                self.prefer_update = False
                self._queue_send_subscribe(tks)
            elif kind == "subscribe":
                self.stats["subscribe_refused"] += 1
            elif sid is not None and sid == self.sid:
                # e.g. code 25 "Subscription buffer overflow" -- the server
                # dropped our stream; reconnect for fresh snapshots.
                self._resync = True
                self._poke()
        else:
            self._keep(m, rx_ms)

    def _ack(self, cid):
        kind, tks = self._pending_cmds.pop(cid, (None, None))
        if tks:
            with self.lock:
                self.subscribed |= set(tks)
            self.stats[f"ack_{kind}"] += 1

    def _keep(self, m, rx_ms):
        m = dict(m)
        m["_rx_ms"] = rx_ms
        self.frames.append(m)
        if len(self.frames) > 200:
            del self.frames[:100]

    # ---------------- reads ----------------
    def best(self, tk):
        """Top of book, or None if no snapshot has arrived for the ticker.
        A side with no levels reports None for its four fields."""
        with self.lock:
            b = self.books.get(tk)
            if b is None:
                return None
            m = self.meta[tk]
            yb = max(b["yes"]) if b["yes"] else None
            nb = max(b["no"]) if b["no"] else None
            ybs = b["yes"][yb] if yb is not None else None
            nbs = b["no"][nb] if nb is not None else None
            rx = m["rx_ms"]
            return {
                "yes_bid": yb, "yes_bid_size": ybs,
                "yes_ask": round(1.0 - nb, 4) if nb is not None else None,
                "yes_ask_size": nbs,
                "no_bid": nb, "no_bid_size": nbs,
                "no_ask": round(1.0 - yb, 4) if yb is not None else None,
                "no_ask_size": ybs,
                "age_ms": (now_ms() - rx) if rx is not None else None,
                "ts_ms": m["ts_ms"],
                "seq": m["seq"], "suspect": m["suspect"],
                "levels": (len(b["yes"]), len(b["no"])),
            }

    def depth(self, tk, side, n=3):
        """Top n (price, size) on one side, best first."""
        with self.lock:
            b = self.books.get(tk)
            if b is None:
                return None
            return sorted(b[side].items(), reverse=True)[:n]

    def median_latency_ms(self):
        with self.lock:
            return statistics.median(self.latency_ms) if self.latency_ms else None

    # ---------------- subscription control (thread-safe) ----------------
    def start(self, tickers=()):
        with self.lock:
            self.wanted |= set(tickers)
        if self._thread and self._thread.is_alive():
            self.subscribe(tickers)
            return self
        self._stop = False
        self._thread = threading.Thread(target=self._thread_main,
                                        name="livebook-ws", daemon=True)
        self._thread.start()
        return self

    def subscribe(self, tickers):
        """Add markets to the running subscription from any thread."""
        new = [t for t in tickers if t]
        if not new:
            return
        with self.lock:
            self.wanted |= set(new)
            self._pending.extend(new)
        self._poke()

    def drop(self, tickers):
        """Forget closed markets so a reconnect does not re-subscribe them.
        (Probed live 2026-09-07: a closed or bogus ticker in a batch is
        accepted with `ok` and does not poison the live ones -- this is
        hygiene, not a safety requirement.)"""
        with self.lock:
            for tk in tickers:
                self.wanted.discard(tk)
                self.subscribed.discard(tk)
                self.books.pop(tk, None)
                self.meta.pop(tk, None)
                self._watch.pop(tk, None)

    def resync(self):
        """Force a reconnect (fresh snapshots for every wanted ticker)."""
        self._resync = True
        self._poke()

    def stop(self):
        self._stop = True
        self._poke()

    def _poke(self):
        loop, wake = self._loop, self._wake
        if loop is not None and wake is not None:
            try:
                loop.call_soon_threadsafe(wake.set)
            except RuntimeError:
                pass

    # ---------------- the connection thread ----------------
    def _thread_main(self):
        while not self._stop:
            try:
                asyncio.run(self._run())
            except Exception as e:                       # never die silently
                log.exception("ws thread crashed: %r -- restarting", e)
                self.stats["thread_restarts"] += 1
                time.sleep(2)

    def _next_id(self):
        self._cmd_id += 1
        return self._cmd_id

    def _queue_send_subscribe(self, tks):
        """Called from on_frame (loop thread) -- re-issue as plain subscribe."""
        with self.lock:
            self._pending.extend(tks or [])
        self._poke()

    async def _send_subscribe(self, ws, tks):
        cid = self._next_id()
        cmd = {"id": cid, "cmd": "subscribe",
               "params": {"channels": [CHANNEL], "market_tickers": sorted(tks)}}
        self._pending_cmds[cid] = ("subscribe", list(tks))
        await ws.send(json.dumps(cmd))
        self.stats["sent_subscribe"] += 1
        self.last_cmd = cmd
        return cmd

    async def _send_update(self, ws, tks):
        cid = self._next_id()
        cmd = {"id": cid, "cmd": "update_subscription",
               "params": {"sids": [self.sid], "market_tickers": sorted(tks),
                          "action": "add_markets"}}
        self._pending_cmds[cid] = ("update", list(tks))
        await ws.send(json.dumps(cmd))
        self.stats["sent_update_subscription"] += 1
        self.last_cmd = cmd
        return cmd

    async def _add(self, ws, tks):
        tks = [t for t in tks if t]
        if not tks:
            return
        if self.sid is not None and self.prefer_update:
            await self._send_update(ws, tks)
        else:
            await self._send_subscribe(ws, tks)

    async def _run(self):
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        import websockets
        sign = make_signer(self.key_id, self.key_file)
        backoff = 1
        while not self._stop:
            self.connected.clear()
            try:
                hdrs = sign("GET", WS_PATH)
                async with websockets.connect(
                        self.url, additional_headers=hdrs,
                        ping_interval=20, ping_timeout=20,
                        # default close_timeout is 10 s and the server does not
                        # answer the close frame promptly: a gap-resync sat
                        # blind for 10.0 s (measured) before this was set.
                        close_timeout=1,
                        max_size=8 * 1024 * 1024) as ws:
                    self._ws = ws
                    self.stats["connects"] += 1
                    log.info("connected (%d)", self.stats["connects"])
                    backoff = 1
                    # fresh connection: new sid, new seq stream, old books
                    # suspect and frozen until their new snapshot
                    want = self._on_connect()
                    if want:
                        await self._send_subscribe(ws, want)
                    self.connected.set()
                    reader = asyncio.create_task(self._reader(ws))
                    try:
                        while not self._stop and not reader.done():
                            try:
                                await asyncio.wait_for(self._wake.wait(), 0.5)
                            except asyncio.TimeoutError:
                                pass
                            self._wake.clear()
                            with self.lock:
                                pend = list(dict.fromkeys(self._pending))
                                self._pending.clear()
                            if pend:
                                await self._add(ws, pend)
                            if self._resync:
                                log.warning("resync requested -- reconnecting "
                                            "for fresh snapshots")
                                self.stats["resyncs"] += 1
                                break
                        if reader.done() and not self._stop:
                            exc = reader.exception()
                            if exc:
                                raise exc
                    finally:
                        reader.cancel()
                        try:
                            await reader
                        except (asyncio.CancelledError, Exception):
                            pass
                    if self._stop:
                        return
            except Exception as e:
                self.stats["disconnects"] += 1
                log.warning("%s: %s -- retry in %ss", type(e).__name__, e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
            finally:
                self._ws = None
                self.connected.clear()

    async def _reader(self, ws):
        async for raw in ws:
            try:
                self.on_frame(raw, now_ms())
            except Exception as e:                       # one bad frame != death
                self.stats["frame_exceptions"] += 1
                log.exception("frame handler error: %r", e)


# --------------------------------------------------------------------------
# self-test: synthetic frames through on_frame -- the same code the live path runs
# --------------------------------------------------------------------------
def selftest():
    lb = LiveBook(key_id="x", key_file="x")
    T = "KXTEST15M-00"
    frames = []

    def f(obj):
        return json.dumps(obj)

    # 1) subscribed ack, then a snapshot with prices as 4-dp strings
    lb.on_frame(f({"type": "subscribed", "id": 1,
                   "msg": {"channel": "orderbook_delta", "sid": 7}}), 1000)
    assert lb.sid == 7, lb.sid
    lb.on_frame(f({"type": "orderbook_snapshot", "sid": 7, "seq": 100,
                   "msg": {"market_ticker": T, "market_id": "m",
                           "yes_dollars_fp": [["0.0100", "500.00"],
                                              ["0.9700", "40.00"],
                                              ["0.9990", "0.67"]],
                           "no_dollars_fp": [["0.0010", "1000.00"],
                                             ["0.0200", "12.50"]]}}), 1001)
    b = lb.best(T)
    assert b is not None
    assert b["yes_bid"] == 0.999 and b["yes_bid_size"] == 0.67, b
    assert b["no_bid"] == 0.02 and b["no_bid_size"] == 12.5, b
    assert b["yes_ask"] == 0.98 and b["yes_ask_size"] == 12.5, b
    assert b["no_ask"] == 0.001 and b["no_ask_size"] == 0.67, b
    assert b["levels"] == (3, 2) and b["suspect"] is False, b
    print("  snapshot: yes_bid 0.999x0.67  no_bid 0.02x12.5  yes_ask 0.98  ok")

    # 2) delta RAISING a level -- and the delta writes "0.999" not "0.9990":
    #    the key must be the same float, or this creates a phantom level.
    lb.on_frame(f({"type": "orderbook_delta", "sid": 7, "seq": 101,
                   "msg": {"market_ticker": T, "price_dollars": "0.999",
                           "delta_fp": "10.00", "side": "yes",
                           "ts_ms": 5000}}), 5040)
    assert lb.books[T]["yes"][0.999] == 10.67, lb.books[T]
    assert len(lb.books[T]["yes"]) == 3, lb.books[T]
    assert lb.best(T)["ts_ms"] == 5000 and lb.latency_ms == [40]
    print("  delta raise: 0.67 + 10.00 = 10.67 at one key, no phantom  ok")

    # 3) delta ZEROING a level -- must delete it, and best() moves down
    lb.on_frame(f({"type": "orderbook_delta", "sid": 7, "seq": 102,
                   "msg": {"market_ticker": T, "price_dollars": "0.9990",
                           "delta_fp": "-10.67", "side": "yes",
                           "ts_ms": 5001}}), 5041)
    assert 0.999 not in lb.books[T]["yes"], lb.books[T]
    b = lb.best(T)
    assert b["yes_bid"] == 0.97 and b["yes_bid_size"] == 40.0, b
    assert b["no_ask"] == 0.03, b
    print("  delta zero: 0.999 deleted, yes_bid falls to 0.97x40  ok")

    # 4) delta on a price NOT in the book -- creates it (no side: new best)
    lb.on_frame(f({"type": "orderbook_delta", "sid": 7, "seq": 103,
                   "msg": {"market_ticker": T, "price_dollars": "0.0250",
                           "delta_fp": "3.00", "side": "no",
                           "ts_ms": 5002}}), 5042)
    b = lb.best(T)
    assert lb.books[T]["no"][0.025] == 3.0
    assert b["no_bid"] == 0.025 and b["yes_ask"] == 0.975 and b["yes_ask_size"] == 3.0, b
    print("  delta new level: no 0.025x3 created, yes_ask = 1-0.025 = 0.975  ok")

    # 5) OUT-OF-ORDER seq (a replay of 101) -- must be flagged, must not apply
    before = json.dumps(lb.books[T], sort_keys=True)
    ooo_before = lb.stats["delta_out_of_order"]
    lb.on_frame(f({"type": "orderbook_delta", "sid": 7, "seq": 101,
                   "msg": {"market_ticker": T, "price_dollars": "0.9700",
                           "delta_fp": "999.00", "side": "yes",
                           "ts_ms": 5003}}), 5043)
    assert lb.stats["delta_out_of_order"] == ooo_before + 1
    assert json.dumps(lb.books[T], sort_keys=True) == before, "book corrupted"
    assert lb.best(T)["yes_bid_size"] == 40.0
    # that replay also broke the per-sid sequence, so a gap is logged and the
    # book is marked suspect
    assert lb.stats["seq_gaps"] == 1 and lb.best(T)["suspect"] is True
    print("  out-of-order seq 101 after 103: flagged, ignored, book intact, "
          "gap logged, suspect=True  ok")

    # 6) a fresh snapshot clears suspect and REPLACES (old levels vanish)
    lb.sid_seq[7] = 200                     # pretend the stream is healthy again
    lb.on_frame(f({"type": "orderbook_snapshot", "sid": 7, "seq": 201,
                   "msg": {"market_ticker": T, "market_id": "m",
                           "yes_dollars_fp": [["0.5000", "1.00"]]}}), 6000)
    b = lb.best(T)
    assert b["suspect"] is False and b["levels"] == (1, 0), b
    assert b["yes_bid"] == 0.5 and b["no_ask"] == 0.5
    assert b["no_bid"] is None and b["yes_ask"] is None and b["yes_ask_size"] is None
    print("  re-snapshot: replaces book, clears suspect, missing side -> None  ok")

    # 7) negative controls: unknown ticker -> None; delta before snapshot ignored
    assert lb.best("KXNOPE") is None
    lb.on_frame(f({"type": "orderbook_delta", "sid": 7, "seq": 202,
                   "msg": {"market_ticker": "KXNOPE", "price_dollars": "0.5",
                           "delta_fp": "1.00", "side": "yes", "ts_ms": 1}}), 6001)
    assert lb.best("KXNOPE") is None and lb.stats["delta_before_snapshot"] == 1
    # an empty-book snapshot (brand-new market) is a book with all-None fields
    lb.on_frame(f({"type": "orderbook_snapshot", "sid": 7, "seq": 203,
                   "msg": {"market_ticker": "KXNEW", "market_id": "z"}}), 6002)
    b = lb.best("KXNEW")
    assert b is not None and b["yes_bid"] is None and b["no_bid"] is None
    # a clean consecutive stream logs no further gap
    assert lb.stats["seq_gaps"] == 1
    # garbage and error frames do not raise
    lb.on_frame("not json", 6003)
    # the gap in step 5 already set _resync; clear it, or this assertion
    # would pass without the error handler doing anything (it did, once).
    lb._resync = False
    lb.on_frame(f({"type": "error", "sid": 7, "seq": 204,
                   "msg": {"code": 25, "msg": "Subscription buffer overflow"}}), 6004)
    assert lb._resync is True, "code-25 error on our sid must force a resync"
    # an error on some OTHER sid does not
    lb._resync = False
    lb.on_frame(f({"type": "error", "sid": 99,
                   "msg": {"code": 25, "msg": "Subscription buffer overflow"}}), 6004)
    assert lb._resync is False
    print("  controls: unknown ticker None, delta-before-snapshot ignored, "
          "empty snapshot -> all-None, junk frame survives  ok")

    # 8) update_subscription refused by the server -> the same tickers are
    #    re-queued as a plain `subscribe` (what the collector does) and the
    #    client stops preferring update_subscription. Never triggered live
    #    (update_subscription worked), so it has to be exercised here.
    lb.prefer_update = True
    lb._pending_cmds[99] = ("update", ["KXFALLBACK"])
    lb.on_frame(f({"type": "error", "id": 99,
                   "msg": {"code": 6, "msg": "unknown command"}}), 6005)
    assert lb.prefer_update is False and lb._pending == ["KXFALLBACK"], lb._pending
    assert lb.stats["update_subscription_refused"] == 1
    # 9) drop() forgets a market entirely
    lb.wanted.add("KXNEW")
    lb.drop(["KXNEW"])
    assert lb.best("KXNEW") is None and "KXNEW" not in lb.wanted
    # a plain subscribe refused by the server is counted, not retried blindly
    lb._pending_cmds[98] = ("subscribe", ["KXREFUSED"])
    lb.on_frame(f({"type": "error", "id": 98,
                   "msg": {"code": 28, "msg": "Underlying tickers required"}}), 6006)
    assert lb.stats["subscribe_refused"] == 1 and "KXREFUSED" not in lb.subscribed
    print("  fallback: refused update_subscription re-queued as subscribe; "
          "refused subscribe counted; drop() forgets a market  ok")

    # 10) RECONNECT: the old book survives but is suspect and FROZEN -- a
    #     delta on the new connection (seq restarts, same sid number as the
    #     server does) must NOT be applied to it until its fresh snapshot.
    #     Before this guard the old book took new-connection deltas whenever
    #     the sid differed, and only the seq check saved the same-sid case.
    lb.wanted.add(T)
    want = lb._on_connect()
    assert want == [T] and lb.sid is None and lb.sid_seq == {} and lb._resync is False
    assert lb.best(T)["suspect"] is True and lb.best(T)["yes_bid"] == 0.5
    lb.on_frame(f({"type": "subscribed", "id": 4,
                   "msg": {"channel": "orderbook_delta", "sid": 7}}), 7000)
    for sid_new in (7, 8):                    # same sid number, and a new one
        dbs = lb.stats["delta_before_snapshot"]
        lb.on_frame(f({"type": "orderbook_delta", "sid": sid_new, "seq": 2,
                       "msg": {"market_ticker": T, "price_dollars": "0.5000",
                               "delta_fp": "999.00", "side": "yes",
                               "ts_ms": 7000}}), 7001)
        assert lb.stats["delta_before_snapshot"] == dbs + 1, dict(lb.stats)
        assert lb.books[T]["yes"] == {0.5: 1.0}, "stale book took a delta"
    lb.sid_seq.clear()                        # (sid 8 above is not our stream)
    lb.on_frame(f({"type": "orderbook_snapshot", "sid": 7, "seq": 3,
                   "msg": {"market_ticker": T, "market_id": "m",
                           "yes_dollars_fp": [["0.5000", "2.00"]]}}), 7002)
    b = lb.best(T)
    assert b["suspect"] is False and b["yes_bid_size"] == 2.0, b
    lb.on_frame(f({"type": "orderbook_delta", "sid": 7, "seq": 4,
                   "msg": {"market_ticker": T, "price_dollars": "0.5000",
                           "delta_fp": "1.00", "side": "yes", "ts_ms": 7003}}), 7003)
    assert lb.best(T)["yes_bid_size"] == 3.0, "delta after the new snapshot must apply"
    # a non-numeric ts_ms must not raise past the level update
    lb.on_frame(f({"type": "orderbook_delta", "sid": 7, "seq": 5,
                   "msg": {"market_ticker": T, "price_dollars": "0.5000",
                           "delta_fp": "1.00", "side": "yes", "ts_ms": "junk"}}), 7004)
    assert lb.best(T)["yes_bid_size"] == 4.0 and lb.stats["bad_ts_ms"] == 1
    assert lb.meta[T]["deltas"] == 5, lb.meta[T]     # 3 from steps 2-4, +2 here
    print("  reconnect: old book frozen+suspect until this connection's "
          "snapshot (same sid and new sid); bad ts_ms survives  ok")

    # 11) a seq gap wakes the connection loop immediately (via _poke) -- use a
    #     stand-in loop so the call is observable without a socket
    class _Loop:
        calls = 0
        def call_soon_threadsafe(self, fn):
            _Loop.calls += 1; fn()
    class _Wake:
        set_n = 0
        def set(self):
            _Wake.set_n += 1
    lb._loop, lb._wake = _Loop(), _Wake()
    lb._resync = False
    lb.on_frame(f({"type": "orderbook_delta", "sid": 7, "seq": 9,   # 6 expected
                   "msg": {"market_ticker": T, "price_dollars": "0.5000",
                           "delta_fp": "1.00", "side": "yes", "ts_ms": 7005}}), 7005)
    assert lb.stats["seq_gaps"] == 2 and lb._resync is True and _Wake.set_n == 1
    assert lb.best(T)["suspect"] is True and lb.best(T)["yes_bid_size"] == 5.0
    print("  seq gap: resync flagged AND loop woken at once; gap frame still "
          "applied to the (now suspect) book  ok")
    print(f"  stats: {dict(lb.stats)}")
    print("SELF-TEST PASSED")
    return 0


# --------------------------------------------------------------------------
# smoke: live, read-only, on its own connection
# --------------------------------------------------------------------------
def smoke(seconds, series=("KXBTC15M", "KXETH15M")):
    sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
    from kauth import get

    t0 = time.time()
    found = {}
    for s in series:
        st, body = get("/markets", {"series_ticker": s, "status": "open",
                                    "limit": "2"})
        mk = (body.get("markets") or []) if isinstance(body, dict) else []
        print(f"GET /markets series={s} status=open -> {st}: "
              f"{[(m['ticker'], m.get('close_time')) for m in mk]}")
        if mk:
            # the soonest close is the live window
            mk.sort(key=lambda m: m.get("close_time") or "")
            found[s] = mk[0]["ticker"]
    if not found:
        print("SMOKE FAILED: no open markets found")
        return 2
    first = [found[series[0]]] if series[0] in found else [next(iter(found.values()))]
    later = [t for t in found.values() if t not in first]

    lb = LiveBook()
    lb.start(first)
    print(f"[{time.time()-t0:5.1f}s] start({first})")
    if not lb.connected.wait(15):
        print("SMOKE FAILED: no connection in 15 s;", dict(lb.stats))
        return 2
    print(f"[{time.time()-t0:5.1f}s] connected; sent {lb.last_cmd}")
    snap_seen_at = {}
    end = time.time() + seconds
    added = False
    add_at = time.time() + 5
    while time.time() < end:
        time.sleep(0.05)
        for tk in first + later:
            if tk not in snap_seen_at and lb.best(tk) is not None:
                snap_seen_at[tk] = time.time() - t0
                print(f"[{snap_seen_at[tk]:5.1f}s] first snapshot for {tk}: "
                      f"{lb.best(tk)}")
        if not added and later and time.time() >= add_at:
            lb.subscribe(later)
            added = True
            print(f"[{time.time()-t0:5.1f}s] subscribe({later}) after connect")
    if added:
        time.sleep(0.5)
        print(f"[{time.time()-t0:5.1f}s] add command sent: "
              f"{getattr(lb, 'last_cmd', None)}")
        for fr in lb.frames:
            if fr.get("type") in ("ok", "subscribed", "error"):
                print(f"    control frame: {json.dumps(fr)[:300]}")
        for tk in later:
            print(f"    snapshot for {tk} after subscribe(): "
                  f"{'YES at +%.1fs' % snap_seen_at[tk] if tk in snap_seen_at else 'NO'}")

    print(f"\n[{time.time()-t0:5.1f}s] message counts by type: "
          f"{ {k: v for k, v in sorted(lb.stats.items())} }")
    print(f"seq gaps: {lb.gaps}")
    lat = lb.median_latency_ms()
    print(f"median (rx wall ms - ts_ms) over {len(lb.latency_ms)} deltas: {lat} ms")
    per = {tk: lb.best(tk) for tk in first + later}
    for tk, b in per.items():
        print(f"best({tk}) = {b}")

    # REST side-by-side. The book takes hundreds of deltas a second, so a REST
    # read is one instant somewhere inside the call: the WS book AGREES if it
    # passed through exactly that top-3 state (price AND size, both sides) at
    # some instant during the call window. Two endpoints alone are too strict
    # -- on the first live run REST sat between the before and after reads.
    agree_all = True
    for tk in first + later:
        ws_before = lb.best(tk)
        lb.watch(tk)                              # start recording trajectory
        t_req = now_ms()
        st, ob = get("/markets/" + tk + "/orderbook", {"depth": "3"})
        t_rsp = now_ms()
        traj = lb.watch(tk, on=False)             # [(rx_ms, top3 yes, top3 no)]
        ws_after = lb.best(tk)
        o = (ob or {}).get("orderbook_fp") or {} if isinstance(ob, dict) else {}
        r_yes = [(px(p), round(float(s), 2)) for p, s in (o.get("yes_dollars") or [])]
        r_no = [(px(p), round(float(s), 2)) for p, s in (o.get("no_dollars") or [])]
        r_yes.sort(reverse=True)
        r_no.sort(reverse=True)
        print(f"\n--- {tk}: REST GET /markets/{tk}/orderbook?depth=3 -> {st} "
              f"({t_rsp - t_req} ms round trip; WS book changed {max(len(traj)-1, 0)} "
              f"times during it)")
        first_state = traj[0] if traj else None
        last_state = traj[-1] if traj else None
        print(f"  REST top3 yes bids : {r_yes}")
        print(f"  WS   top3 yes bids : at request {first_state[1] if first_state else None}")
        print(f"                       at response {last_state[1] if last_state else None}")
        print(f"  REST top3 no  bids : {r_no}")
        print(f"  WS   top3 no  bids : at request {first_state[2] if first_state else None}")
        print(f"                       at response {last_state[2] if last_state else None}")
        if ws_before is None or not traj:
            print(f"  DISAGREE: no WS book for {tk}")
            agree_all = False
            continue
        rest_yb = r_yes[0][0] if r_yes else None
        rest_nb = r_no[0][0] if r_no else None
        print(f"  REST best: yes_bid {rest_yb} yes_ask "
              f"{round(1-rest_nb,4) if rest_nb is not None else None}"
              f" | WS best now: yes_bid {ws_after['yes_bid']} yes_ask {ws_after['yes_ask']}"
              f" age {ws_after['age_ms']} ms suspect={ws_after['suspect']}")
        hits = [i for i, (_, y, n) in enumerate(traj) if y == r_yes and n == r_no]
        if hits:
            i = hits[0]
            print(f"  AGREE: WS book passed through exactly the REST top-3 state "
                  f"(price+size, both sides) at +{traj[i][0] - t_req} ms into the "
                  f"call (state {i+1} of {len(traj)})")
        else:
            # how close did it get? count matching (price,size) cells
            def score(y, n):
                return sum(a == b for a, b in zip(y, r_yes)) + \
                       sum(a == b for a, b in zip(n, r_no))
            best_i = max(range(len(traj)), key=lambda i: score(traj[i][1], traj[i][2]))
            sc = score(traj[best_i][1], traj[best_i][2])
            top_ok = (bool(r_yes) and traj[best_i][1][:1] == r_yes[:1] and
                      bool(r_no) and traj[best_i][2][:1] == r_no[:1])
            print(f"  DISAGREE: no WS state during the call equals REST; closest "
                  f"matches {sc} of {len(r_yes)+len(r_no)} (price,size) cells; "
                  f"top level price+size both sides {'matched' if top_ok else 'did NOT match'}")
            agree_all = False
    print(f"\nOVERALL: {'AGREE' if agree_all else 'DISAGREE'} on top-3 book vs REST")

    # resync probe: re-subscribe a ticker that is already subscribed -- does the
    # server send a fresh snapshot, and does it duplicate the delta stream?
    probe = first[0]
    snaps0 = lb.meta[probe]["snapshots"]
    ooo0 = lb.stats["delta_out_of_order"]
    sids0 = set(lb.sid_seq)
    n_frames0 = len(lb.frames)
    lb.prefer_update = False           # plain subscribe, as the collector does
    lb.subscribe([probe])
    time.sleep(4)
    print(f"\nresync probe: re-`subscribe` of already-subscribed {probe}: "
          f"{getattr(lb, 'last_cmd', None)}")
    for fr in lb.frames[n_frames0:]:
        print(f"    reply frame: {json.dumps(fr)[:300]}")
    print(f"    snapshots for {probe}: {snaps0} -> {lb.meta[probe]['snapshots']}; "
          f"out-of-order deltas: {ooo0} -> {lb.stats['delta_out_of_order']}; "
          f"sids seen: {sids0} -> {set(lb.sid_seq)}; gaps {len(lb.gaps)}")
    # reconnect probe: this is the gap-recovery path (a seq gap sets _resync),
    # so it has to be shown working live -- connects 1 -> 2, and a fresh
    # snapshot for every wanted ticker on the new connection.
    conn0 = lb.stats["connects"]
    snaps = {tk: lb.meta[tk]["snapshots"] for tk in first + later}
    tr = time.time()
    lb.resync()
    deadline = time.time() + 10
    while time.time() < deadline:
        if (lb.stats["connects"] == conn0 + 1
                and all(lb.meta[tk]["snapshots"] > snaps[tk] for tk in snaps)):
            break
        time.sleep(0.05)
    print(f"\nreconnect probe: resync() -> connects {conn0} -> {lb.stats['connects']}, "
          f"resyncs {lb.stats['resyncs']}, took {time.time()-tr:.2f}s; "
          f"snapshots per ticker: "
          f"{ {tk: (snaps[tk], lb.meta[tk]['snapshots']) for tk in snaps} }; "
          f"sids seen {set(lb.sid_seq)}; suspect now "
          f"{ {tk: lb.best(tk)['suspect'] for tk in snaps} }")
    lb.stop()
    time.sleep(1)
    print(f"final stats: {dict(sorted(lb.stats.items()))}")
    print("SMOKE DONE")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--smoke", type=float, metavar="SECONDS")
    ap.add_argument("-v", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.v else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stderr)
    if a.selftest:
        return selftest()
    if a.smoke:
        return smoke(a.smoke)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
