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

import argparse, asyncio, gzip, json, os, time
from collections import defaultdict
from datetime import datetime, timezone

try:
    import websockets
except ImportError:
    raise SystemExit("pip install websockets")

__VERSION__ = "2026-08-25-v2"


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
                w.write("bitstamp", m)
                ch = m.get("channel", "")
                asset = ch.replace("order_book_", "").replace("usd", "").upper()
                d = m.get("data", {})
                bids, asks = d.get("bids") or [], d.get("asks") or []
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


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="./feed_data")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
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
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
