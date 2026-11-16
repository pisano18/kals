#!/usr/bin/env python3
# VERSION: 2026-11-16-a2
"""
altfeed_rec.py -- zero-money recorder of the exchange prices behind the four slow indices.

    python -I -u research/altfeed_rec.py --self-test
    python -I -u research/altfeed_rec.py --out C:\\kals-altfeed --until 2027-01-15T00:00Z

WHY (the operator, 11-15, after ZEC 8:30 PM ET -$165: "wouldn't the fastest possible feed on all bots be best? ... also
test that and remember to bring it back up once there's data to read")

Kalshi relays CF Benchmarks' index at 5 Hz for BTC ETH SOL XRP DOGE only. ZECUSD_RTI, BNBUSD_RTI, NEARUSD_RTI and
HYPEUSD_RTI come once a second, so pin sees a jump on those coins up to a second after the exchanges that make the index
(ZEC 11-15: Kalshi's book moved at tau 29, pin's print at tau 28). Deep dive 2 (11-09) found an exchange-fed hedge
alarm DEAD on the five fast coins once false fires count, but had no exchange tape at all for these four, which hold
21 of its 39 flips. This records that tape, so the read (READS_DUE late: altfeed-read) can price an exchange-fed alarm
against pin's real hedges, using pin's own per-second pintraj rows for the settlement prints and the hedge-side ask.

WHAT IT RECORDS: every top-of-book change and every trade, per exchange and coin, stamped with this machine's receive
time `rx` (the same clock as pin's logs on the server) and the exchange's own time `x` where it sends one. One gzip
file per exchange, hour and start: <out>\\<exchange>\\<YYYYMMDDTHH>_<start epoch>.jsonl.gz (a new name for every start,
so a killed recorder's unfinished file is never appended to; read_rows() reads one up to where it stopped). Rows:
    {"rx": 1794792571.123, "c": "ZEC", "k": "b", "b": 889.41, "bs": 3.2, "a": 889.52, "as": 1.1, "x": 1794792571.101}
    {"rx": 1794792571.130, "c": "ZEC", "k": "t", "p": 889.50, "q": 0.4, "s": "buy", "x": 1794792571.118}
k = "b" (best bid/ask changed) or "t" (a trade). Public unauthenticated feeds only. No Kalshi call of any kind.

SAFETY ON THE LIVE BOX (pin trades on the same 2-core server):
  * below-normal process priority, so pin always wins the CPU;
  * stops itself at --until, when <out> passes --max-gb, or when free disk falls under --min-free-gb;
  * a file <out>\\altfeed.stop (or results\\altfeed.stop) makes it exit at the next check (every 5 s);
  * status every 60 s in <out>\\status.json (per exchange and coin: rows, last rx, connects, errors).
"""

import argparse, asyncio, gzip, json, os, shutil, sys, time
from datetime import datetime, timezone

try:
    import websockets
except ImportError:                     # the self-test runs without it
    websockets = None

__VERSION__ = "2026-11-16-a2"
COINS = ("ZEC", "BNB", "NEAR", "HYPE")


def _ssl_ctx():
    """certifi's roots when it is installed (a2: the server's SYSTEM account lacks the issuers of Coinbase's, Kraken's and
    Crypto.com's certificates in the Windows store, so every connect failed CERTIFICATE_VERIFY_FAILED), else the default."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


SSL_CTX = _ssl_ctx()
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# exchange -> {coin: the exchange's own symbol}. Only pairs that exist on the venue are listed; a venue that lists a
# coin under a quote other than USD says so in its symbol. Filled from CF's constituent list for these indices.
VENUES = {
    "coinbase": {"ZEC": "ZEC-USD", "NEAR": "NEAR-USD", "BNB": "BNB-USD", "HYPE": "HYPE-USD"},
    "kraken": {"ZEC": "ZEC/USD", "NEAR": "NEAR/USD", "BNB": "BNB/USD", "HYPE": "HYPE/USD"},
    "bitstamp": {"NEAR": "nearusd"},
    "gemini": {"ZEC": "ZECUSD"},
    "cryptocom": {"ZEC": "ZEC_USD", "NEAR": "NEAR_USD", "BNB": "BNB_USD", "HYPE": "HYPE_USD"},
}


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v


def iso_epoch(s):
    s = s.strip().upper().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            pass
    raise ValueError("not an ISO UTC time: %r" % s)


class Writer:
    """One gzip per exchange and hour, named for this start; rows flushed at most once a second (a crash loses under a
    second, and the file reads back up to the last flush)."""

    def __init__(self, root, tag=None):
        self.root, self.fh, self.hour, self.last_flush = root, {}, None, 0.0
        self.bytes_hint = 0
        self.tag = str(int(time.time())) if tag is None else str(tag)

    def _roll(self, now):
        h = datetime.fromtimestamp(now, timezone.utc).strftime("%Y%m%dT%H")
        if h != self.hour:
            self.close()
            self.hour = h

    def write(self, ex, row, now=None):
        now = time.time() if now is None else now
        self._roll(now)
        f = self.fh.get(ex)
        if f is None:
            d = os.path.join(self.root, ex)
            os.makedirs(d, exist_ok=True)
            f = self.fh[ex] = gzip.open(os.path.join(d, "%s_%s.jsonl.gz" % (self.hour, self.tag)), "at",
                                        compresslevel=5, encoding="utf-8")
        s = json.dumps(row, separators=(",", ":"))
        f.write(s + "\n")
        self.bytes_hint += len(s) + 1
        if now - self.last_flush >= 1.0:
            self.flush()
            self.last_flush = now

    def flush(self):
        for f in self.fh.values():
            try:
                f.flush()
            except (OSError, ValueError):
                pass

    def close(self):
        for f in self.fh.values():
            try:
                f.close()
            except (OSError, ValueError):
                pass
        self.fh = {}


def read_rows(path):
    """Every row of one tape file, a killed recorder's unfinished one included (it stops at the last whole line)."""
    out = []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as g:
            for line in g:
                if line.endswith("\n"):
                    out.append(json.loads(line))
    except (EOFError, OSError, ValueError):
        pass
    return out


class Tape:
    """Keeps each (exchange, coin)'s best bid/ask and writes a row only when it changes; counts for the status file.
    A change of PRICE is always written. A change of size alone (Kraken's bbo ticker sends ~80 a second on ZEC) is
    written at most once per SIZE_ONLY_S per (exchange, coin), and the next price change carries the newest sizes."""

    SIZE_ONLY_S = 0.25

    def __init__(self, w):
        self.w, self.top, self.stats, self.wrote = w, {}, {}, {}

    def _st(self, ex, coin):
        return self.stats.setdefault(ex, {}).setdefault(coin, {"book": 0, "trade": 0, "size_skipped": 0,
                                                               "last_rx": None})

    def book(self, ex, coin, bid, bs, ask, asz, x=None, rx=None):
        rx = time.time() if rx is None else rx
        bid, bs, ask, asz = _f(bid), _f(bs), _f(ask), _f(asz)
        if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
            return False
        key = (ex, coin)
        cur = (bid, bs, ask, asz)
        old = self.top.get(key)
        if old == cur:
            return False
        if old is not None and old[0] == bid and old[2] == ask and rx - self.wrote.get(key, 0.0) < self.SIZE_ONLY_S:
            self.top[key] = cur
            self._st(ex, coin)["size_skipped"] += 1
            return False
        self.top[key] = cur
        self.wrote[key] = rx
        row = {"rx": round(rx, 4), "c": coin, "k": "b", "b": bid, "bs": bs, "a": ask, "as": asz}
        if x is not None:
            row["x"] = x
        self.w.write(ex, row, rx)
        st = self._st(ex, coin)
        st["book"] += 1
        st["last_rx"] = round(rx, 3)
        return True

    def trade(self, ex, coin, p, q, side=None, x=None, rx=None):
        rx = time.time() if rx is None else rx
        p, q = _f(p), _f(q)
        if p is None or p <= 0:
            return False
        row = {"rx": round(rx, 4), "c": coin, "k": "t", "p": p, "q": q}
        if side:
            row["s"] = str(side).lower()
        if x is not None:
            row["x"] = x
        self.w.write(ex, row, rx)
        st = self._st(ex, coin)
        st["trade"] += 1
        st["last_rx"] = round(rx, 3)
        return True


def iso_x(s):
    """An exchange's ISO-8601 time ('2026-11-16T01:29:31.118234Z') as epoch seconds, or None."""
    if not s:
        return None
    try:
        s = str(s).replace("Z", "+00:00")
        if "." in s:                                    # fromisoformat wants 6 fraction digits at most
            head, rest = s.split(".", 1)
            digits = rest[:len(rest) - len(rest.lstrip("0123456789"))]
            s = head + "." + digits[:6].ljust(6, "0") + rest[len(digits):]
        return round(datetime.fromisoformat(s).timestamp(), 6)
    except (ValueError, TypeError):
        return None


class L2:
    """A minimal price-level book (Coinbase level2_batch, Crypto.com deltas): enough to know the best bid and ask."""

    def __init__(self):
        self.bids, self.asks = {}, {}

    def snapshot(self, bids, asks):
        self.bids = {float(p): float(q) for p, q, *_ in bids if float(q) > 0}
        self.asks = {float(p): float(q) for p, q, *_ in asks if float(q) > 0}

    def change(self, side, p, q):
        book = self.bids if side in ("buy", "bid", "b") else self.asks
        p, q = float(p), float(q)
        if q <= 0:
            book.pop(p, None)
        else:
            book[p] = q

    def best(self):
        if not self.bids or not self.asks:
            return None
        b = max(self.bids)
        a = min(self.asks)
        return b, self.bids[b], a, self.asks[a]


# ---- venues: each parses its own messages into tape.book / tape.trade; parse_* are pure (the self-test feeds them) --

def parse_coinbase(m, tape, books, sym2coin, rx):
    t = m.get("type")
    coin = sym2coin.get(m.get("product_id"))
    if coin is None:
        return
    if t == "snapshot":
        b = books.setdefault(coin, L2())
        b.snapshot(m.get("bids") or [], m.get("asks") or [])
    elif t == "l2update":
        b = books.setdefault(coin, L2())
        for side, p, q in m.get("changes") or []:
            b.change(side, p, q)
    elif t == "match" or t == "last_match":
        tape.trade("coinbase", coin, m.get("price"), m.get("size"), m.get("side"), iso_x(m.get("time")), rx)
        return
    else:
        return
    top = books[coin].best()
    if top:
        tape.book("coinbase", coin, *top, x=iso_x(m.get("time")), rx=rx)


def parse_kraken(m, tape, sym2coin, rx):
    ch = m.get("channel")
    if ch == "ticker":
        for d in m.get("data") or []:
            coin = sym2coin.get(d.get("symbol"))
            if coin:
                tape.book("kraken", coin, d.get("bid"), d.get("bid_qty"), d.get("ask"), d.get("ask_qty"), None, rx)
    elif ch == "trade":
        for d in m.get("data") or []:
            coin = sym2coin.get(d.get("symbol"))
            if coin:
                tape.trade("kraken", coin, d.get("price"), d.get("qty"), d.get("side"), iso_x(d.get("timestamp")), rx)


def parse_bitstamp(m, tape, sym2coin, rx):
    if m.get("event") not in ("data", "trade"):
        return
    ch = m.get("channel") or ""
    d = m.get("data") or {}
    if ch.startswith("order_book_"):
        coin = sym2coin.get(ch[len("order_book_"):])
        bids, asks = d.get("bids") or [], d.get("asks") or []
        if coin and bids and asks:
            x = _f(d.get("microtimestamp"))
            tape.book("bitstamp", coin, bids[0][0], bids[0][1], asks[0][0], asks[0][1],
                      round(x / 1e6, 6) if x else None, rx)
    elif ch.startswith("live_trades_"):
        coin = sym2coin.get(ch[len("live_trades_"):])
        if coin:
            x = _f(d.get("microtimestamp"))
            tape.trade("bitstamp", coin, d.get("price"), d.get("amount"),
                       {0: "buy", 1: "sell"}.get(d.get("type")), round(x / 1e6, 6) if x else None, rx)


def parse_gemini(m, tape, coin, state, rx):
    if m.get("type") != "update":
        return
    x = _f(m.get("timestampms"))
    x = round(x / 1e3, 3) if x else None
    for e in m.get("events") or []:
        if e.get("type") == "change" and e.get("side") in ("bid", "ask"):
            state[e["side"]] = (e.get("price"), e.get("remaining"))
        elif e.get("type") == "trade":
            tape.trade("gemini", coin, e.get("price"), e.get("amount"), e.get("makerSide") and
                       {"bid": "sell", "ask": "buy"}.get(e.get("makerSide")), x, rx)
    if state.get("bid") and state.get("ask"):
        tape.book("gemini", coin, state["bid"][0], state["bid"][1], state["ask"][0], state["ask"][1], x, rx)


def parse_cryptocom(m, tape, sym2coin, rx):
    r = m.get("result") or {}
    ch = r.get("channel") or ""
    coin = sym2coin.get(r.get("instrument_name"))
    if coin is None:
        return
    for d in r.get("data") or []:
        if ch.startswith("book"):
            bids, asks = d.get("bids") or [], d.get("asks") or []
            if bids and asks:
                x = _f(d.get("t"))
                tape.book("cryptocom", coin, bids[0][0], bids[0][1], asks[0][0], asks[0][1],
                          round(x / 1e3, 3) if x else None, rx)
        elif ch.startswith("trade"):
            x = _f(d.get("t"))
            tape.trade("cryptocom", coin, d.get("p"), d.get("q"), d.get("s"), round(x / 1e3, 3) if x else None, rx)


# ---- the sockets ----

async def run_coinbase(tape, syms, stats):
    s2c = {v: k for k, v in syms.items()}
    books = {}
    async with websockets.connect("wss://ws-feed.exchange.coinbase.com", ssl=SSL_CTX, ping_interval=20, max_size=16 << 20) as ws:
        await ws.send(json.dumps({"type": "subscribe", "product_ids": list(s2c),
                                  "channels": ["level2_batch", "matches"]}))
        stats["connects"] += 1
        async for raw in ws:
            m = json.loads(raw)
            if m.get("type") == "error":
                raise RuntimeError("coinbase: %s" % (m.get("reason") or m.get("message")))
            parse_coinbase(m, tape, books, s2c, time.time())


async def run_kraken(tape, syms, stats):
    s2c = {v: k for k, v in syms.items()}
    async with websockets.connect("wss://ws.kraken.com/v2", ssl=SSL_CTX, ping_interval=20, max_size=8 << 20) as ws:
        await ws.send(json.dumps({"method": "subscribe", "params": {"channel": "ticker", "symbol": list(s2c),
                                                                    "event_trigger": "bbo"}}))
        await ws.send(json.dumps({"method": "subscribe", "params": {"channel": "trade", "symbol": list(s2c)}}))
        stats["connects"] += 1
        async for raw in ws:
            m = json.loads(raw)
            if m.get("method") == "subscribe" and m.get("success") is False:
                stats["notes"].append("kraken refused %s" % str(m.get("error"))[:80])
                continue
            parse_kraken(m, tape, s2c, time.time())


async def run_bitstamp(tape, syms, stats):
    s2c = {v: k for k, v in syms.items()}
    async with websockets.connect("wss://ws.bitstamp.net", ssl=SSL_CTX, ping_interval=20, max_size=8 << 20) as ws:
        for p in s2c:
            for ch in ("order_book_", "live_trades_"):
                await ws.send(json.dumps({"event": "bts:subscribe", "data": {"channel": ch + p}}))
        stats["connects"] += 1
        async for raw in ws:
            m = json.loads(raw)
            if m.get("event") == "bts:request_reconnect":
                raise RuntimeError("bitstamp asked for a reconnect")
            parse_bitstamp(m, tape, s2c, time.time())


async def run_gemini_one(tape, coin, sym, stats):
    url = "wss://api.gemini.com/v1/marketdata/%s?top_of_book=true&trades=true&heartbeat=true" % sym
    state = {}
    async with websockets.connect(url, ssl=SSL_CTX, ping_interval=20, max_size=8 << 20) as ws:
        stats["connects"] += 1
        async for raw in ws:
            parse_gemini(json.loads(raw), tape, coin, state, time.time())


async def run_cryptocom(tape, syms, stats):
    s2c = {v: k for k, v in syms.items()}
    async with websockets.connect("wss://stream.crypto.com/exchange/v1/market", ssl=SSL_CTX, ping_interval=None,
                                  max_size=8 << 20) as ws:
        await asyncio.sleep(1.0)        # the venue asks for a pause after connecting before the first request
        chans = ["book.%s.10" % s for s in s2c] + ["trade.%s" % s for s in s2c]
        await ws.send(json.dumps({"id": 1, "method": "subscribe", "params": {"channels": chans},
                                  "nonce": int(time.time() * 1000)}))
        stats["connects"] += 1
        async for raw in ws:
            m = json.loads(raw)
            if m.get("method") == "public/heartbeat":
                await ws.send(json.dumps({"id": m.get("id"), "method": "public/respond-heartbeat"}))
                continue
            parse_cryptocom(m, tape, s2c, time.time())


async def keep(name, factory, stats, stop):
    """One venue alive until `stop`; its failures stay its own."""
    backoff = 1.0
    while not stop.is_set():
        t0 = time.time()
        try:
            await factory()
        except Exception as e:                                  # noqa: BLE001
            stats["errors"] += 1
            stats["last_error"] = "%s: %s" % (type(e).__name__, str(e)[:160])
        if stop.is_set():
            return
        if time.time() - t0 > 60:
            backoff = 1.0                                       # it ran a while: a fresh failure starts the ladder over
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60.0)


def dir_bytes(root):
    n = 0
    for d, _s, fs in os.walk(root):
        for f in fs:
            try:
                n += os.path.getsize(os.path.join(d, f))
            except OSError:
                pass
    return n


def stop_reason(out, until, max_gb, min_free_gb, now=None, used=None, free=None):
    now = time.time() if now is None else now
    if until and now >= until:
        return "until"
    for p in (os.path.join(out, "altfeed.stop"), os.path.join(REPO, "results", "altfeed.stop")):
        if os.path.exists(p):
            return "stop file %s" % p
    used = dir_bytes(out) if used is None else used
    if used > max_gb * 1e9:
        return "out is %.2f GB > %.2f GB" % (used / 1e9, max_gb)
    if free is None:
        try:
            free = shutil.disk_usage(out).free
        except OSError:
            free = None
    if free is not None and free < min_free_gb * 1e9:
        return "free disk %.1f GB < %.1f GB" % (free / 1e9, min_free_gb)
    return None


def low_priority():
    if os.name != "nt":
        try:
            os.nice(10)
        except (OSError, AttributeError):
            pass
        return "nice 10"
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)       # BELOW_NORMAL_PRIORITY_CLASS
        return "below normal"
    except Exception as e:                                      # noqa: BLE001
        return "priority unchanged (%s)" % e


async def main_async(a):
    until = iso_epoch(a.until) if a.until else None
    os.makedirs(a.out, exist_ok=True)
    why = stop_reason(a.out, until, a.max_gb, a.min_free_gb)
    if why:
        print("[altfeed] not starting: %s" % why, flush=True)
        return 0
    prio = low_priority()
    w = Writer(a.out)
    tape = Tape(w)
    stop = asyncio.Event()
    vstats = {}
    tasks = []
    for ex, syms in VENUES.items():
        syms = {c: s for c, s in syms.items() if c in COINS}
        if not syms or (a.only and ex not in a.only):
            continue
        st = vstats[ex] = {"connects": 0, "errors": 0, "last_error": None, "notes": [], "symbols": syms}
        if ex == "coinbase":
            tasks.append(keep(ex, lambda s=syms, st=st: run_coinbase(tape, s, st), st, stop))
        elif ex == "kraken":
            tasks.append(keep(ex, lambda s=syms, st=st: run_kraken(tape, s, st), st, stop))
        elif ex == "bitstamp":
            tasks.append(keep(ex, lambda s=syms, st=st: run_bitstamp(tape, s, st), st, stop))
        elif ex == "gemini":
            for c, s in syms.items():
                tasks.append(keep(ex, lambda c=c, s=s, st=st: run_gemini_one(tape, c, s, st), st, stop))
        elif ex == "cryptocom":
            tasks.append(keep(ex, lambda s=syms, st=st: run_cryptocom(tape, s, st), st, stop))
    started = time.time()
    print("[altfeed] %s -> %s, until %s, %s, venues %s" % (__VERSION__, a.out, a.until, prio, sorted(vstats)),
          flush=True)

    async def guard():
        last_status = 0.0
        used = dir_bytes(a.out)
        while not stop.is_set():
            await asyncio.sleep(5)
            now = time.time()
            why = stop_reason(a.out, until, a.max_gb, a.min_free_gb, now, used + w.bytes_hint // 4)
            if now - last_status >= 60 or why:
                w.flush()
                used = dir_bytes(a.out)
                w.bytes_hint = 0
                last_status = now
                status = {"version": __VERSION__, "t": datetime.fromtimestamp(now, timezone.utc).isoformat(),
                          "started": datetime.fromtimestamp(started, timezone.utc).isoformat(), "until": a.until,
                          "pid": os.getpid(), "priority": prio, "out_bytes": used, "stopping": why,
                          "venues": vstats, "rows": tape.stats}
                tmp = os.path.join(a.out, "status.json.tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(status, f, indent=1)
                os.replace(tmp, os.path.join(a.out, "status.json"))
            if why:
                print("[altfeed] stopping: %s" % why, flush=True)
                stop.set()
                return

    runs = [asyncio.ensure_future(t) for t in tasks]
    await guard()
    for r in runs:
        r.cancel()
    await asyncio.gather(*runs, return_exceptions=True)
    w.close()
    return 0


def self_test():
    import tempfile
    fails = []

    def check(name, got, want):
        ok = got == want
        print("%s  %s: %r" % ("PASS" if ok else "FAIL", name, got))
        if not ok:
            fails.append(name)

    tmp = tempfile.mkdtemp()
    try:
        w = Writer(tmp)
        tape = Tape(w)
        rx = 1794792571.25
        # Coinbase: snapshot -> best, a change that moves the touch -> a row, a no-op -> no row, a match -> trade
        books = {}
        s2c = {"ZEC-USD": "ZEC"}
        parse_coinbase({"type": "snapshot", "product_id": "ZEC-USD", "bids": [["889.40", "2"], ["889.30", "5"]],
                        "asks": [["889.50", "1"], ["889.60", "4"]]}, tape, books, s2c, rx)
        parse_coinbase({"type": "l2update", "product_id": "ZEC-USD", "time": "2026-11-16T01:29:31.118234Z",
                        "changes": [["sell", "889.50", "0"]]}, tape, books, s2c, rx + 0.1)
        parse_coinbase({"type": "l2update", "product_id": "ZEC-USD", "changes": [["buy", "889.10", "1"]]},
                       tape, books, s2c, rx + 0.2)
        parse_coinbase({"type": "match", "product_id": "ZEC-USD", "price": "889.55", "size": "0.4", "side": "sell",
                        "time": "2026-11-16T01:29:31.2Z"}, tape, books, s2c, rx + 0.3)
        parse_coinbase({"type": "match", "product_id": "BTC-USD", "price": "1", "size": "1"}, tape, books, s2c, rx)
        check("coinbase book rows (snapshot + touch change, the deep change ignored)",
              tape.stats["coinbase"]["ZEC"]["book"], 2)
        check("coinbase best ask after the 889.50 level is pulled", tape.top[("coinbase", "ZEC")][2], 889.6)
        check("coinbase trade rows (a foreign product ignored)", tape.stats["coinbase"]["ZEC"]["trade"], 1)
        check("coinbase exchange time parsed", iso_x("2026-11-16T01:29:31.118234Z"), 1794792571.118234)
        # Kraken ticker (bbo) + trade
        parse_kraken({"channel": "ticker", "data": [{"symbol": "ZEC/USD", "bid": 889.4, "bid_qty": 1, "ask": 889.5,
                                                     "ask_qty": 2}]}, tape, {"ZEC/USD": "ZEC"}, rx)
        parse_kraken({"channel": "trade", "data": [{"symbol": "ZEC/USD", "price": 889.5, "qty": 0.1, "side": "buy",
                                                    "timestamp": "2026-11-16T01:29:31.100000Z"}]},
                     tape, {"ZEC/USD": "ZEC"}, rx)
        check("kraken rows", (tape.stats["kraken"]["ZEC"]["book"], tape.stats["kraken"]["ZEC"]["trade"]), (1, 1))
        # Bitstamp
        parse_bitstamp({"event": "data", "channel": "order_book_nearusd",
                        "data": {"bids": [["2.101", "50"]], "asks": [["2.105", "40"]],
                                 "microtimestamp": "1794792571100000"}}, tape, {"nearusd": "NEAR"}, rx)
        parse_bitstamp({"event": "trade", "channel": "live_trades_nearusd",
                        "data": {"price": 2.104, "amount": 3, "type": 1, "microtimestamp": "1794792571200000"}},
                       tape, {"nearusd": "NEAR"}, rx)
        check("bitstamp rows", (tape.stats["bitstamp"]["NEAR"]["book"], tape.stats["bitstamp"]["NEAR"]["trade"]),
              (1, 1))
        # Gemini top_of_book
        st = {}
        parse_gemini({"type": "update", "timestampms": 1794792571100, "events": [
            {"type": "change", "side": "bid", "price": "889.3", "remaining": "1"},
            {"type": "change", "side": "ask", "price": "889.6", "remaining": "2"},
            {"type": "trade", "price": "889.6", "amount": "0.2", "makerSide": "ask"}]}, tape, "ZEC", st, rx)
        check("gemini rows", (tape.stats["gemini"]["ZEC"]["book"], tape.stats["gemini"]["ZEC"]["trade"]), (1, 1))
        # Crypto.com
        parse_cryptocom({"result": {"channel": "book", "instrument_name": "HYPE_USD", "data": [
            {"bids": [["31.10", "5", "1"]], "asks": [["31.12", "7", "1"]], "t": 1794792571100}]}},
            tape, {"HYPE_USD": "HYPE"}, rx)
        parse_cryptocom({"result": {"channel": "trade", "instrument_name": "HYPE_USD", "data": [
            {"p": "31.11", "q": "2", "s": "BUY", "t": 1794792571150}]}}, tape, {"HYPE_USD": "HYPE"}, rx)
        check("crypto.com rows", (tape.stats["cryptocom"]["HYPE"]["book"], tape.stats["cryptocom"]["HYPE"]["trade"]),
              (1, 1))
        # a size-only change inside SIZE_ONLY_S is held back; one after it is written; a price change always is
        k0 = tape.stats["kraken"]["ZEC"]["book"]
        tape.book("kraken", "ZEC", 889.4, 1.5, 889.5, 2, None, rx + 0.1)
        tape.book("kraken", "ZEC", 889.4, 1.5, 889.6, 2, None, rx + 0.15)
        tape.book("kraken", "ZEC", 889.4, 1.7, 889.6, 2, None, rx + 0.2)
        tape.book("kraken", "ZEC", 889.4, 1.9, 889.6, 2, None, rx + 0.5)
        check("size-only throttle: 2 held, the price change and the late size change written",
              (tape.stats["kraken"]["ZEC"]["book"] - k0, tape.stats["kraken"]["ZEC"]["size_skipped"]), (2, 2))
        # a crossed or empty book writes nothing
        check("crossed book refused", tape.book("kraken", "BNB", 10, 1, 9, 1, None, rx), False)
        w.close()
        # the files read back, one row each as counted
        n = 0
        for d, _s, fs in os.walk(tmp):
            for f in fs:
                if f.endswith(".jsonl.gz"):
                    n += len(read_rows(os.path.join(d, f)))
        want = sum(v["book"] + v["trade"] for ex in tape.stats.values() for v in ex.values())
        check("rows on disk == rows counted", n, want)
        # a killed recorder: flushed rows read back, the unfinished tail is dropped, and a restart never appends to it
        w2 = Writer(tmp, tag="111")
        for i in range(5):
            w2.write("kraken", {"rx": i}, now=1794792571.0 + i)
        w2.flush()
        w2.fh["kraken"].buffer.fileobj.flush()         # gzip's own buffers are flushed; push the OS file too
        p2 = os.path.join(tmp, "kraken", "20261116T01_111.jsonl.gz")
        cut = os.path.join(tmp, "killed.jsonl.gz")
        shutil.copyfile(p2, cut)                       # the bytes on disk before any close: no end-of-stream marker
        w2.close()
        check("a killed file reads back its flushed rows", len(read_rows(cut)), 5)
        w3 = Writer(tmp, tag="222")
        w3.write("kraken", {"rx": 9}, now=1794792575.0)
        w3.close()
        names = sorted(f for f in os.listdir(os.path.join(tmp, "kraken")) if f.split("_")[-1] in (
            "111.jsonl.gz", "222.jsonl.gz"))
        check("a restart in the same hour writes its own file", names,
              ["20261116T01_111.jsonl.gz", "20261116T01_222.jsonl.gz"])
        # stop rules
        check("stop at --until", stop_reason(tmp, 100.0, 5, 1, now=200.0, used=0, free=10e9), "until")
        check("stop over --max-gb", (stop_reason(tmp, None, 1.0, 1, now=0, used=2e9, free=10e9) or "")[:6],
              "out is")
        check("stop under --min-free-gb", (stop_reason(tmp, None, 5, 8, now=0, used=0, free=7e9) or "")[:9],
              "free disk")
        open(os.path.join(tmp, "altfeed.stop"), "w").close()
        check("stop file", (stop_reason(tmp, None, 5, 1, now=0, used=0, free=10e9) or "")[:9], "stop file")
        check("running when nothing says stop", stop_reason(tempfile.mkdtemp(), None, 5, 1, now=0, used=0,
                                                            free=10e9), None)
        check("until parse", iso_epoch("2027-01-15T00:00Z"), 1799971200.0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SELF-TEST %s (%d failed)" % ("PASSED" if not fails else "FAILED", len(fails)))
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=r"C:\kals-altfeed")
    ap.add_argument("--until", default="2027-01-15T00:00Z", help="UTC; the recorder stops itself then")
    ap.add_argument("--max-gb", type=float, default=10.0)
    ap.add_argument("--min-free-gb", type=float, default=10.0)
    ap.add_argument("--only", nargs="*", help="venues to run (default: all in VENUES)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return 0 if self_test() else 1
    if websockets is None:
        print("pip install websockets", flush=True)
        return 2
    return asyncio.run(main_async(a))


if __name__ == "__main__":
    sys.exit(main())
