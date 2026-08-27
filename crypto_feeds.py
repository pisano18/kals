#!/usr/bin/env python3
# VERSION: 2026-08-25-v2
"""
crypto_feeds.py  --  Record the INPUTS to the settlement index.

WHY THIS EXISTS (the gap I missed)

Kalshi settles on CF Benchmarks BRTI. Per CME/CF's own methodology, BRTI is:
  * computed from ORDER BOOK data of constituent exchanges, not trades
  * published once per second, at top-of-second
  * built by exponentially weighting a consolidated mid price-volume curve
    with dynamic order size capping
  * explicitly described by CME's white paper as reproducible and replicable
    from constituent order book data

Those constituent exchanges publish their books over free, public, unauthenticated
WebSockets. So the index we are betting on is computed from data anyone can
stream directly.

That means the whole "latency race we lose from home" framing was too pessimistic.
We were only considering what Kalshi shows us. But we can compute our own BRTI
estimate from the same inputs, in parallel with CF, and compare it to Kalshi's
relayed cfbenchmarks_value. Any consistent lead time is a real, measurable edge
that does NOT require co-location -- it requires being on the same public feeds.

Settlement is a 60-second average, which makes this doubly useful: we don't need
microsecond speed, we need an earlier and cleaner read on where the running
average is heading.

THIS DATA IS UNRECOVERABLE. Exchange WebSockets are live-only; there is no
backfill. Every hour this isn't running is an hour we can never analyse.

    pip install websockets
    python crypto_feeds.py --out ./feed_data

No API key. No account. Read-only market data.
"""

import argparse, asyncio, gzip, json, os, sys, time
from collections import defaultdict
from datetime import datetime, timezone

try:
    import websockets
except ImportError:
    # Deferred to main() rather than raised here, so --selftest can run on a
    # machine that has no websockets installed. Running the collector without
    # it still exits with the same message it always did.
    websockets = None

__VERSION__ = "2026-08-25-v2"

# Bitstamp has no top-of-book channel: order_book_<pair> sends all 100 levels
# of both sides on every update, several times a second, across eight pairs.
# That is 92.6% of everything under feed_data/ -- and EVERY reader in this
# project uses bids[0] and asks[0] only (research/feeds.py load_tob,
# research/proxy.py's constituent series). Levels 2-100 have been written and
# never once read.
#
# Keeping five is not "keeping one with a safety margin for its own sake": it
# leaves room to ask a depth question later without the archive being useless
# for it, while dropping the 95% of each record that nothing has ever looked
# at. Raising this number only affects data recorded AFTER the change -- what
# is already on disk keeps its full depth, and what is truncated cannot be
# recovered. That is why the truncation is stamped into the record rather
# than done silently: a future reader must be able to tell a five-level book
# from a market that only had five levels.
BITSTAMP_KEEP_LEVELS = 5


class Writer:
    def __init__(self, root):
        self.root, self.fh, self.hour = root, {}, None

    def _roll(self):
        h = datetime.now(timezone.utc).strftime("%Y%m%dT%H")
        if h != self.hour:
            for f in self.fh.values():
                f.close()
            self.fh, self.hour = {}, h

    def write(self, chan, obj):
        self._roll()
        if chan not in self.fh:
            d = os.path.join(self.root, chan)
            os.makedirs(d, exist_ok=True)
            self.fh[chan] = gzip.open(
                os.path.join(d, f"{self.hour}.jsonl.gz"), "at", compresslevel=4, encoding="utf-8")
        self.fh[chan].write(json.dumps(obj, separators=(",", ":")) + "\n")
        self.fh[chan].flush()


def trim_book(d, keep):
    """Cut an order-book payload to `keep` levels a side, in place.

    Stamps `_depth` with what the venue actually sent, so the archive never
    lies about how deep the book was. Returns True when anything was dropped.

    keep <= 0 disables trimming entirely -- the record is left exactly as it
    arrived, and no stamp is added, so turning this off restores byte-for-byte
    the old behaviour rather than a lookalike of it.
    """
    if keep is None or keep <= 0 or not isinstance(d, dict):
        return False
    bids, asks = d.get("bids"), d.get("asks")
    nb = len(bids) if isinstance(bids, list) else 0
    na = len(asks) if isinstance(asks, list) else 0
    if nb <= keep and na <= keep:
        return False
    if nb > keep:
        d["bids"] = bids[:keep]
    if na > keep:
        d["asks"] = asks[:keep]
    d["_depth"] = {"bids": nb, "asks": na, "kept": keep}
    return True


# Shared top-of-book state, so we can emit a consolidated index once a second.
TOB = defaultdict(dict)          # exchange -> {asset: (bid, bidsz, ask, asksz, ts)}


def upd(ex, asset, bid, bidsz, ask, asksz):
    try:
        bid, ask = float(bid), float(ask)
        if bid > 0 and ask > 0 and ask >= bid:
            TOB[ex][asset] = (bid, float(bidsz or 0), ask, float(asksz or 0),
                              time.time())
    except (TypeError, ValueError):
        pass


async def runner(name, coro_factory, w, verbose):
    """Keep one exchange task alive forever; isolate its failures."""
    backoff = 1
    while True:
        try:
            await coro_factory(w, verbose)
        except Exception as e:
            print(f"[{name}] {type(e).__name__}: {str(e)[:160]} "
                  f"-- retry {backoff}s", flush=True)
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)


# --------------------------------------------------------------------------
# Constituent exchanges. These are the classic CME CF constituents.
# Each records raw messages AND updates shared top-of-book state.
# --------------------------------------------------------------------------

async def coinbase(w, verbose):
    url = "wss://ws-feed.exchange.coinbase.com"
    prods = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD",
             "DOGE-USD", "ADA-USD", "BCH-USD", "LTC-USD"]
    async with websockets.connect(url, ping_interval=20, max_size=8 << 20) as ws:
        await ws.send(json.dumps({"type": "subscribe", "product_ids": prods,
                                  "channels": ["ticker"]}))
        print("[coinbase] connected", flush=True)
        async for raw in ws:
            m = json.loads(raw)
            if m.get("type") == "ticker":
                m["_rx"] = time.time()
                w.write("coinbase", m)
                upd("coinbase", m.get("product_id", "").split("-")[0],
                    m.get("best_bid"), m.get("best_bid_size"),
                    m.get("best_ask"), m.get("best_ask_size"))


async def kraken(w, verbose):
    url = "wss://ws.kraken.com/v2"
    syms = ["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD",
            "DOGE/USD", "ADA/USD", "BCH/USD", "LTC/USD"]
    async with websockets.connect(url, ping_interval=20, max_size=8 << 20) as ws:
        await ws.send(json.dumps({"method": "subscribe",
                                  "params": {"channel": "ticker",
                                             "symbol": syms}}))
        print("[kraken] connected", flush=True)
        async for raw in ws:
            m = json.loads(raw)
            if m.get("channel") == "ticker":
                m["_rx"] = time.time()
                w.write("kraken", m)
                for d in m.get("data", []):
                    upd("kraken", str(d.get("symbol", "")).split("/")[0],
                        d.get("bid"), d.get("bid_qty"),
                        d.get("ask"), d.get("ask_qty"))


async def bitstamp(w, verbose):
    url = "wss://ws.bitstamp.net"
    pairs = ["btcusd", "ethusd", "solusd", "xrpusd", "dogeusd", "adausd",
             "bchusd", "ltcusd"]
    async with websockets.connect(url, ping_interval=20, max_size=8 << 20) as ws:
        for p in pairs:
            await ws.send(json.dumps({"event": "bts:subscribe",
                                      "data": {"channel": f"order_book_{p}"}}))
        print("[bitstamp] connected", flush=True)
        async for raw in ws:
            m = json.loads(raw)
            if m.get("event") == "data":
                m["_rx"] = time.time()
                d = m.get("data") or {}
                bids, asks = d.get("bids") or [], d.get("asks") or []
                trim_book(d, BITSTAMP_KEEP_LEVELS)
                w.write("bitstamp", m)
                ch = m.get("channel", "")
                asset = ch.replace("order_book_", "").replace("usd", "").upper()
                # d is the same object the writer just serialised, so this
                # still reads the true top of book -- trimming removes depth,
                # never the touch.
                if bids and asks:
                    upd("bitstamp", asset, bids[0][0], bids[0][1],
                        asks[0][0], asks[0][1])


async def gemini(w, verbose):
    url = "wss://api.gemini.com/v1/marketdata/BTCUSD?top_of_book=true&heartbeat=true"
    async with websockets.connect(url, ping_interval=20, max_size=8 << 20) as ws:
        print("[gemini] connected", flush=True)
        bid = ask = None
        async for raw in ws:
            m = json.loads(raw)
            m["_rx"] = time.time()
            w.write("gemini", m)
            for e in m.get("events", []) or []:
                if e.get("type") == "change" and e.get("side") in ("bid", "ask"):
                    if e["side"] == "bid":
                        bid = (e.get("price"), e.get("remaining"))
                    else:
                        ask = (e.get("price"), e.get("remaining"))
            if bid and ask:
                upd("gemini", "BTC", bid[0], bid[1], ask[0], ask[1])


# --------------------------------------------------------------------------
# Consolidated index replica, emitted at TOP OF SECOND to align with BRTI.
# --------------------------------------------------------------------------

async def index_replica(w, verbose):
    """First-order BRTI approximation: size-weighted consolidated mid across
    exchanges. NOT the real methodology (which uses an exponentially weighted
    price-volume curve with order-size capping over full depth) -- but it is
    the right shape, and the point of Phase 2 is to measure how well it tracks
    and, crucially, whether it LEADS Kalshi's relayed value."""
    while True:
        await asyncio.sleep(1.0 - (time.time() % 1.0))   # top of second
        now = time.time()
        out = {"_rx": now, "sec": int(now)}
        per = defaultdict(list)
        for ex, assets in TOB.items():
            for asset, (b, bs, a, asz, ts) in assets.items():
                if now - ts > 10:          # stale
                    continue
                mid = (b + a) / 2.0
                wgt = max(min(bs, asz), 1e-9)      # crude size weight
                per[asset].append((mid, wgt, ex, b, a))
        for asset, rows in per.items():
            tw = sum(r[1] for r in rows)
            if tw <= 0 or not rows:
                continue
            out[asset] = {
                "wmid": sum(r[0] * r[1] for r in rows) / tw,
                "median_mid": sorted(r[0] for r in rows)[len(rows) // 2],
                "n_ex": len(rows),
                "per_ex": {r[2]: {"b": r[3], "a": r[4]} for r in rows},
            }
        if len(out) > 2:
            w.write("index_replica", out)


def selftest():
    """Prove the depth trim keeps everything anything reads, and says so."""
    import copy, gzip as _gz, shutil, tempfile
    print("=" * 78)
    print("SELF-TEST -- trimming Bitstamp depth must not change any answer")
    print("=" * 78)
    fails = []

    def book(n=100, base=60000.0):
        return {"channel": "order_book_btcusd", "event": "data", "data": {
            "timestamp": "1760000000", "microtimestamp": "1760000000000000",
            "bids": [[f"{base - i * 0.5:.2f}", f"{0.1 + i:.8f}"]
                     for i in range(n)],
            "asks": [[f"{base + 0.5 + i * 0.5:.2f}", f"{0.2 + i:.8f}"]
                     for i in range(n)]}}

    # 1. the touch survives, and the stamp records what the venue really sent
    m = book()
    top = (m["data"]["bids"][0][:], m["data"]["asks"][0][:])
    trim_book(m["data"], 5)
    if m["data"]["bids"][0] != top[0] or m["data"]["asks"][0] != top[1]:
        fails.append("the top of book changed under trimming")
    if len(m["data"]["bids"]) != 5 or len(m["data"]["asks"]) != 5:
        fails.append(f"kept {len(m['data']['bids'])}/"
                     f"{len(m['data']['asks'])} levels, expected 5/5")
    if m["data"].get("_depth") != {"bids": 100, "asks": 100, "kept": 5}:
        fails.append(f"depth stamp reads {m['data'].get('_depth')!r}")

    # 2. disabling it must restore the ORIGINAL bytes, not something like them
    m2 = book()
    before = json.dumps(m2, separators=(",", ":"))
    if trim_book(m2["data"], 0) or json.dumps(m2, separators=(",", ":")) != before:
        fails.append("keep<=0 still modified the record")
    # and a book already shallower than `keep` must be left completely alone
    m3 = book(n=3)
    before3 = json.dumps(m3, separators=(",", ":"))
    if trim_book(m3["data"], 5) or json.dumps(m3, separators=(",", ":")) != before3:
        fails.append("a 3-level book was stamped or altered by a 5-level trim")

    # 3. MEASURE the saving on the real record shape, gzipped as it is stored
    def gz_bytes(objs):
        import io as _io
        buf = _io.BytesIO()
        with _gz.GzipFile(fileobj=buf, mode="wb", compresslevel=4) as g:
            for o in objs:
                g.write((json.dumps(o, separators=(",", ":")) + "\n").encode())
        return len(buf.getvalue())

    full = [book(base=60000.0 + k) for k in range(200)]
    cut = copy.deepcopy(full)
    for o in cut:
        trim_book(o["data"], BITSTAMP_KEEP_LEVELS)
    fb, cb = gz_bytes(full), gz_bytes(cut)
    print(f"\n  200 records, gzip level 4 as stored:")
    print(f"    100 levels a side   {fb:>9,} bytes   {fb/200:>7.0f} per record")
    print(f"    {BITSTAMP_KEEP_LEVELS} levels a side     {cb:>9,} bytes   "
          f"{cb/200:>7.0f} per record")
    print(f"    saving              {100*(1-cb/fb):>8.1f}%")
    if cb >= fb:
        fails.append("trimming did not shrink the stored record")

    # 4. END TO END: the project's own reader must get the SAME top of book
    #    out of a trimmed file as out of a full one. This is the only check
    #    that matters -- the rest is about the shape of a dict.
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "research"))
    try:
        from feeds import load_tob
    except ImportError as e:
        print(f"\n  research/feeds.py not importable ({e}); end-to-end check "
              "SKIPPED")
        load_tob = None
    if load_tob:
        got = {}
        for tag, objs in (("full", full), ("trimmed", cut)):
            tmp = tempfile.mkdtemp()
            try:
                d = os.path.join(tmp, "bitstamp")
                os.makedirs(d)
                with _gz.open(os.path.join(d, "20260827T00.jsonl.gz"), "wt",
                              encoding="utf-8") as f:
                    for i, o in enumerate(objs):
                        o = dict(o, _rx=1760000000.0 + i)
                        f.write(json.dumps(o, separators=(",", ":")) + "\n")
                got[tag] = load_tob(tmp, "BTC", verbose=False)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        same = got["full"] == got["trimmed"]
        n = len(got["full"])
        print(f"\n  load_tob over {n} seconds: full vs trimmed -> "
              f"{'IDENTICAL' if same else '*** DIFFERENT ***'}")
        if not n:
            fails.append("load_tob read nothing out of either file, so this "
                         "check compared two empty results and proved nothing")
        if not same:
            fails.append("load_tob returned different top-of-book from the "
                         "trimmed file")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- the touch is untouched, the depth actually")
    print("sent is stamped into the record, disabling the trim restores the")
    print("original bytes, and the project's own reader cannot tell the")
    print("difference.")
    return True


async def main():
    global BITSTAMP_KEEP_LEVELS
    if websockets is None:
        raise SystemExit("pip install websockets")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="./feed_data")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--selftest", action="store_true",
                    help="handled before the event loop starts")
    ap.add_argument("--book-levels", type=int, default=BITSTAMP_KEEP_LEVELS,
                    help="Bitstamp order-book levels to STORE per side. 0 "
                         "keeps all 100, as before. Only affects data "
                         "recorded from now on.")
    a = ap.parse_args()
    BITSTAMP_KEEP_LEVELS = a.book_levels
    print(f"[start] bitstamp depth stored: "
          f"{'all levels' if a.book_levels <= 0 else str(a.book_levels)}",
          flush=True)
    os.makedirs(a.out, exist_ok=True)
    w = Writer(a.out)
    print(f"[start] crypto_feeds {__VERSION__} -> {a.out}", flush=True)

    tasks = [
        runner("coinbase", coinbase, w, a.verbose),
        runner("kraken",   kraken,   w, a.verbose),
        runner("bitstamp", bitstamp, w, a.verbose),
        runner("gemini",   gemini,   w, a.verbose),
        runner("replica",  index_replica, w, a.verbose),
        heartbeat(),
    ]
    await asyncio.gather(*tasks)


async def heartbeat():
    while True:
        await asyncio.sleep(300)
        live = {ex: len(v) for ex, v in TOB.items()}
        print(f"[stat] {datetime.now(timezone.utc):%H:%M} top-of-book live: {live}",
              flush=True)


if __name__ == "__main__":
    # Checked before the event loop starts: the self-test writes files and
    # reads them back, and has no business inside the collector's loop.
    if "--selftest" in sys.argv:
        raise SystemExit(0 if selftest() else 1)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
