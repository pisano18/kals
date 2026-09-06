#!/usr/bin/env python3
# VERSION: 2026-08-25-v4  (verify with: python <file> --version-check)
"""
kalshi_collector.py  --  Phase 1. Record everything, trade nothing.

Runs 24/7. Read-only. It cannot place an order; there is no order code in it.

    pip install websockets requests cryptography
    python kalshi_collector.py --key-id XXX --key-file kalshi.pem --out ./data

WHAT IT RECORDS  (one gzipped JSONL file per hour per channel)
  cfbenchmarks_value  1/sec BRTI ticks  <- the settlement input. Most important.
  orderbook_delta     full book evolution, seq-checked
  trade               every print, with aggressor side
  ticker              top-of-book summary
  market_lifecycle_v2 market creation + floor_strike stamping

WHY EACH MATTERS
  Without the BRTI feed you cannot reconstruct the settlement TWAP, so you
  cannot score any model offline. Without seq-checked book deltas you cannot
  know whether a resting order would have filled. Those two together are the
  entire difference between a real backtest and a fantasy.

DISK: roughly 40-80 MB/day gzipped for all crypto series. ~2 GB/month.

CAVEAT: written without live API access to test against. The subscribe
payloads follow the documented shapes but expect to adjust a channel name or
param. Run with --verbose for the first hour and watch for error frames.
"""

import argparse, asyncio, base64, gzip, json, os, signal, sys, time
from collections import defaultdict
from datetime import datetime, timezone

try:
    import requests, websockets
except ImportError:
    sys.exit("pip install websockets requests cryptography")

REST_PROD = "https://api.elections.kalshi.com/trade-api/v2"
WS_PROD   = "wss://api.elections.kalshi.com/trade-api/ws/v2"
WS_PATH   = "/trade-api/ws/v2"

# CONFIRMED live 2026-08-25 by recon. 14 series, not 7. KXLTC15M does not exist.
CRYPTO_15M = ["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
              "KXBNB15M", "KXADA15M", "KXBCH15M", "KXZEC15M", "KXHYPE15M",
              "KXNEAR15M", "KXTON15M",
              # 2026-09-03: the Coin Race relative-performance series, added
              # to the DEFAULT. They price the CORRELATION between coins, not
              # a single coin's volatility -- the one quantity in this market
              # family nobody has shown to be well priced, and IDEAS.md B1
              # has flagged it as the highest unexplored value since the
              # start. everything.py once patched run_all.ps1 to add them
              # via --series and it never took effect, because the watchdog
              # runs the collector from C:\kals, not from the repo. Putting
              # them in the default means a plain file copy is the whole
              # deployment. Recording is ticker-agnostic; if the series is
              # missing, discover() gets a non-200 and skips it. Analysis of
              # this tape needs DAYS of it, so every day this is not
              # deployed is a day of the only untested idea lost.
              "KXCRYPTOLEAD15M", "KXCRYPTOCOMP15M",
              # 2026-09-06: the COMMODITY 15-minute families. These are the
              # markets Kalshi's Liquidity Incentive Program actually pays
              # for -- GET /incentive_programs returns a per-market, per-
              # window reward pool for these and for Coin Race, and NONE for
              # the twelve crypto up/down series this project has spent
              # weeks on. Being paid to rest an order does not require the
              # market to be wrong about anything, which makes it the most
              # reliable money found here so far.
              #
              # All five verified live 2026-09-06: GET /series/<ticker>
              # returns frequency "fifteen_min", category "Commodities", and
              # each has settled markets. They trade roughly 18:00-23:45 ET,
              # so they show zero OPEN markets during the day -- that is the
              # session, not a bad ticker.
              #
              # Recording is ticker-agnostic and discover() skips a non-200
              # silently, so a wrong name costs nothing but also warns
              # nothing: verify with research/newseries.py after deploying.
              "KXGOLD15M", "KXSILVER15M", "KXWTI15M", "KXNATGAS15M",
              "KXCOPPER15M"]


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


class Writer:
    """Hourly-rotated gzip JSONL, one stream per channel. Crash-tolerant:
    flushes on every write so a power cut costs you at most the last line."""
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
            # encoding is explicit on BOTH ends of this contract: the readers
            # in research/ run as children of go.py with PYTHONUTF8=1, while
            # this recorder runs standalone under the watchdog with the
            # machine's locale encoding. It round-trips today only because
            # json.dumps defaults to ensure_ascii=True -- which is a property
            # of the payload, not a guarantee anyone wrote down.
            self.fh[chan] = gzip.open(
                os.path.join(d, f"{self.hour}.jsonl.gz"), "at",
                compresslevel=4, encoding="utf-8")
        try:
            self.fh[chan].write(json.dumps(obj, separators=(",", ":")) + "\n")
            self.fh[chan].flush()
        except (OSError, ValueError):
            # A failed write or flush -- disk full, antivirus lock, a closed
            # handle -- used to leave a dead file object in self.fh forever.
            # The process stayed alive, so the watchdog never restarted it and
            # recording stopped silently. Drop the handle and reopen next time.
            try:
                self.fh.pop(chan).close()
            except Exception:
                self.fh.pop(chan, None)
            raise

    def close(self):
        for f in self.fh.values():
            f.close()


class Collector:
    def __init__(self, args):
        self.a = args
        self.sign = make_signer(args.key_id, args.key_file)
        self.w = Writer(args.out)
        self.seq = {}                 # sid -> last seq seen
        self.tracked = set()          # market tickers currently subscribed
        self.stats = defaultdict(int)
        self.cmd_id = 0
        self.stop = False

    # ---------------- market discovery ----------------
    def discover(self):
        """Poll REST for open 15-min crypto markets. Cheap: a handful of reads
        per minute against a 200 tok/s budget."""
        out = []
        s = requests.Session()
        for series in self.a.series:
            try:
                r = s.get(f"{REST_PROD}/events",
                          params={"series_ticker": series, "status": "open",
                                  "with_nested_markets": "true", "limit": 10},
                          timeout=15)
                if r.status_code != 200:
                    continue
                for ev in r.json().get("events", []):
                    for m in ev.get("markets", []):
                        if m.get("ticker"):
                            out.append(m["ticker"])
            except Exception as e:
                if self.a.verbose:
                    print(f"[discover] {series}: {e}", flush=True)
        return out

    # NOTE from recon: the REST orderbook returns price levels ASCENDING and
    # `depth` truncates from the BOTTOM, so a small depth hides top-of-book.
    # The WebSocket orderbook_snapshot/delta stream is the only reliable source
    # of the full book -- which is why this collector uses it and not REST.


    # ---------------- channel negotiation ----------------
    # Diagnosis: bare `cfbenchmarks_value` returns {"type":"subscribed"} but
    # delivers NOTHING. Passing params returned code 24 "Index IDs required",
    # so the channel needs index IDs under a param name we have to discover.
    # Same story for pyth_value: code 28 "Underlying tickers required".
    #
    # "subscribed" is NOT success. Only a DATA frame is success. So we try
    # combinations and keep whichever actually delivers data.
    CFB_IDS = ["BRTI", "ETHUSD_RTI", "SOLUSD_RTI", "XRPUSD_RTI", "ADAUSD_RTI",
               "DOGEUSD_RTI", "BNBUSD_RTI", "BCHUSD_RTI", "ZECUSD_RTI",
               "HYPEUSD_RTI", "NEARUSD_RTI", "TONUSD_RTI", "BTCUSD_RTI"]
    PYTH_UND = ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "BCH",
                "ZEC", "HYPE", "NEAR", "TON"]

    async def negotiate(self, ws, channel, param_names, values, want_type):
        """Try param names until a DATA frame arrives. Returns the working
        params dict, or None. Any non-matching frames seen while probing are
        written to disk rather than discarded."""
        for pname in param_names:
            self.cmd_id += 1
            params = {"channels": [channel], pname: values}
            try:
                await ws.send(json.dumps({"id": self.cmd_id, "cmd": "subscribe",
                                          "params": params}))
            except Exception as e:
                print(f"[neg] {channel}/{pname} send failed: {e}", flush=True)
                continue
            deadline = time.time() + 5
            got_sub = False
            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.5)
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    return None
                try:
                    m = json.loads(raw)
                except Exception:
                    continue
                t = m.get("type")
                if t == "error":
                    code = (m.get("msg") or {}).get("code")
                    txt = (m.get("msg") or {}).get("msg", "")
                    print(f"[neg] {channel}/{pname}: error {code} {txt}", flush=True)
                    break
                if t == "subscribed":
                    got_sub = True
                    continue
                if t == want_type or (want_type is None and t not in
                                      ("subscribed", "ok", "error")):
                    print(f"[neg] {channel}: DATA via '{pname}' -- locked in",
                          flush=True)
                    self.handle(raw)
                    return params
                self.handle(raw)          # keep whatever else showed up
            if got_sub:
                print(f"[neg] {channel}/{pname}: subscribed but no data in 5s",
                      flush=True)
        print(f"[neg] {channel}: NO WORKING PARAM FOUND", flush=True)
        return None

    # ---------------- websocket ----------------
    def _next_id(self):
        self.cmd_id += 1
        return self.cmd_id

    async def sub(self, ws, channels, tickers=None):
        p = {"channels": channels}
        if tickers:
            p["market_tickers"] = tickers
        await ws.send(json.dumps({"id": self._next_id(),
                                  "cmd": "subscribe", "params": p}))

    async def run(self):
        backoff = 1
        while not self.stop:
            try:
                hdrs = self.sign("GET", WS_PATH)
                async with websockets.connect(
                        self.a.ws, additional_headers=hdrs,
                        ping_interval=20, ping_timeout=20,
                        max_size=8 * 1024 * 1024) as ws:
                    print("[ws] connected", flush=True)
                    backoff = 1
                    await self.sub(ws, ["market_lifecycle_v2"])

                    # THE critical feed. Negotiate rather than assume.
                    cfb = await self.negotiate(
                        ws, "cfbenchmarks_value",
                        ["index_ids", "indexIds", "index_id", "ids",
                         "indices", "index_tickers", "index_codes"],
                        self.CFB_IDS, "cfbenchmarks_value")
                    if cfb is None:
                        print("[ws] *** cfbenchmarks_value NOT FLOWING. GATE 1 "
                              "cannot run without it. Everything else keeps "
                              "recording; report this. ***", flush=True)
                    await self.negotiate(
                        ws, "pyth_value",
                        ["underlying_tickers", "underlyings", "tickers",
                         "underlying_ticker", "symbols"],
                        self.PYTH_UND, "pyth_value")
                    asyncio.create_task(self.refresher(ws))
                    async for raw in ws:
                        self.handle(raw)
            except Exception as e:
                print(f"[ws] {type(e).__name__}: {e} -- retry in {backoff}s",
                      flush=True)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def refresher(self, ws):
        """Every 30s, subscribe to any newly-opened window. New KXBTC15M
        markets appear every 15 minutes, so this must not sleep long."""
        while not self.stop:
            try:
                live = set(self.discover())
                new = live - self.tracked
                if new:
                    await self.sub(ws, ["orderbook_delta", "trade", "ticker"],
                                   sorted(new))
                    self.tracked |= new
                    print(f"[sub] +{len(new)} markets "
                          f"(tracking {len(self.tracked)})", flush=True)
                if len(self.tracked) > 400:
                    self.tracked = live      # let closed ones age out
            except Exception as e:
                print("[refresh]", e, flush=True)
            await asyncio.sleep(30)

    def handle(self, raw):
        try:
            m = json.loads(raw)
        except Exception:
            return
        t = m.get("type", "unknown")
        self.stats[t] += 1
        m["_rx_ms"] = int(time.time() * 1000)   # local receive time, for latency

        if t == "orderbook_delta":
            # Kalshi puts `seq` at the TOP level of the frame, not inside `msg`;
            # the emitted schema.json resolves it there. Reading msg.seq returned
            # None for every message, so gaps were counted over ZERO pairs and the
            # prober printed "Clean. A book reconstructed from these deltas is
            # trustworthy" about a channel that was, in the same run, 100%
            # unparseable. A green light computed from n=0 is worse than none.
            _d = m.get("msg") or {}
            sid, sq = m.get("sid"), m.get("seq", _d.get("seq"))
            if sid is not None and sq is not None:
                prev = self.seq.get(sid)
                if prev is not None and sq != prev + 1:
                    # GAP. The book is now wrong. Flag it loudly -- silently
                    # applying deltas across a gap is how backtests lie.
                    m["_seq_gap"] = {"expected": prev + 1, "got": sq}
                    self.stats["SEQ_GAPS"] += 1
                self.seq[sid] = sq
        if t == "error":
            print("[ws error]", raw[:400], flush=True)

        self.w.write(t, m)

    async def heartbeat(self):
        while not self.stop:
            await asyncio.sleep(300)
            s = dict(self.stats)
            print(f"[stat] {datetime.now(timezone.utc):%H:%M} "
                  f"tracking={len(self.tracked)} {s}", flush=True)
            self.stats.clear()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-id", required=True)
    ap.add_argument("--key-file", required=True)
    ap.add_argument("--out", default="./kalshi_data")
    ap.add_argument("--ws", default=WS_PROD)
    ap.add_argument("--series", nargs="*", default=CRYPTO_15M)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    c = Collector(a)
    loop = asyncio.get_running_loop()
    signal_handlers_installed = False
    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(s, lambda: setattr(c, "stop", True))
            signal_handlers_installed = True
        except NotImplementedError:
            pass          # Windows -- handled below
    # On Windows loop.add_signal_handler raises NotImplementedError and the
    # loop above swallows it, so Ctrl+C propagated straight out of the gather
    # below and c.w.close() NEVER RAN. The gzip files then had no trailer --
    # survivable on its own, but the next restart inside the same UTC hour
    # appended a second member behind an untrailered first one, and a reader
    # hitting that gets `zlib.error: invalid block type` and discards the file.
    # Measured on a faithful reproduction: 0 of 10 records recovered.
    # research/gzsalvage.py reads what is already on disk; this stops more of
    # it being written.
    if not signal_handlers_installed:
        try:
            signal.signal(signal.SIGINT, lambda *_: setattr(c, "stop", True))
            signal.signal(signal.SIGTERM, lambda *_: setattr(c, "stop", True))
        except (ValueError, OSError, AttributeError):
            pass
    print(f"[start] out={a.out} series={a.series}", flush=True)
    try:
        await asyncio.gather(c.run(), c.heartbeat())
    finally:
        # try/finally, not a trailing statement: this has to run on Ctrl+C,
        # on an exception, and on a clean exit alike.
        c.w.close()



# --- version marker; `findstr VERSION <file>` on Windows to confirm ---
__VERSION__ = "2026-08-25-v4"

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass                  # the writer is closed in main()'s finally
