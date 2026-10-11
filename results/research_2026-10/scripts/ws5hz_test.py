"""Read-only: subscribe to Kalshi's cfbenchmarks_value AND cfbenchmarks_value_5hz for ~15 s and count
frames per index per channel, with the spread of inter-arrival gaps. Verifies the external-research claim
that the big five indices now stream at 5 Hz. No orders, nothing written outside this folder."""
import sys, json, asyncio, time, collections
sys.path.insert(0, r"C:\kals-repo\research")
import livebook

IDS = ["BRTI", "ETHUSD_RTI", "SOLUSD_RTI", "XRPUSD_RTI", "DOGEUSD_RTI", "ZECUSD_RTI", "BNBUSD_RTI", "HYPEUSD_RTI", "NEARUSD_RTI"]
SECS = float(sys.argv[1]) if len(sys.argv) > 1 else 15.0

async def main():
    import websockets
    kid, kfile = livebook._default_key()
    sign = livebook.make_signer(kid, kfile)
    path = "/trade-api/ws/v2"
    counts = collections.Counter(); times = collections.defaultdict(list); other = collections.Counter(); samples = {}
    async with websockets.connect(livebook.WS_URL, additional_headers=sign("GET", path), ping_interval=20, ping_timeout=20, max_size=8 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"id": 1, "cmd": "subscribe", "params": {"channels": ["cfbenchmarks_value"], "index_ids": IDS}}))
        await ws.send(json.dumps({"id": 2, "cmd": "subscribe", "params": {"channels": ["cfbenchmarks_value_5hz"], "index_ids": IDS}}))
        t0 = time.time()
        while time.time() - t0 < SECS:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
            except asyncio.TimeoutError:
                continue
            d = json.loads(raw); typ = d.get("type")
            if typ in ("cfbenchmarks_value", "cfbenchmarks_value_5hz"):
                m = d.get("msg") or {}; iid = m.get("index_id")
                counts[(typ, iid)] += 1; times[(typ, iid)].append(time.time())
                if (typ, iid) not in samples: samples[(typ, iid)] = raw[:300]
            else:
                other[typ] += 1; samples.setdefault(("other", typ), raw[:300])
    print("listened %.1f s; other frames: %s" % (SECS, dict(other)))
    for k in sorted(counts):
        ts = times[k]; gaps = sorted(b - a for a, b in zip(ts, ts[1:]))
        print("%-22s %-12s %4d frames = %.2f/s  gap median %.3f s  min %.3f" % (k[0], k[1], counts[k], counts[k] / SECS, gaps[len(gaps) // 2] if gaps else -1, gaps[0] if gaps else -1))
    for k, v in samples.items():
        print("sample", k, v)

asyncio.run(main())
