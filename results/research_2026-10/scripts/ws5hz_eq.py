"""Read-only: do the 5 Hz channel's top-of-second prints (time % 1000 == 0) equal the 1 Hz channel's prints
for the same index and second? If yes, a bot can run on the 5 Hz channel alone and keep the 1 Hz series
(the settlement input) as the subset of :000 prints. Listens ~20 s."""
import sys, json, asyncio, time, collections
sys.path.insert(0, r"C:\kals-repo\research")
import livebook
IDS = ["BRTI", "ETHUSD_RTI", "SOLUSD_RTI", "XRPUSD_RTI", "DOGEUSD_RTI", "ZECUSD_RTI", "BNBUSD_RTI", "HYPEUSD_RTI", "NEARUSD_RTI"]
SECS = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0

async def main():
    import websockets
    kid, kfile = livebook._default_key(); sign = livebook.make_signer(kid, kfile)
    one, five = {}, {}; offs = collections.defaultdict(list)
    async with websockets.connect(livebook.WS_URL, additional_headers=sign("GET", "/trade-api/ws/v2"), ping_interval=20, ping_timeout=20, max_size=8 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"id": 1, "cmd": "subscribe", "params": {"channels": ["cfbenchmarks_value"], "index_ids": IDS}}))
        await ws.send(json.dumps({"id": 2, "cmd": "subscribe", "params": {"channels": ["cfbenchmarks_value_5hz"], "index_ids": IDS}}))
        t0 = time.time()
        while time.time() - t0 < SECS:
            try: raw = await asyncio.wait_for(ws.recv(), timeout=5)
            except asyncio.TimeoutError: continue
            d = json.loads(raw); typ = d.get("type"); m = d.get("msg") or {}
            if typ not in ("cfbenchmarks_value", "cfbenchmarks_value_5hz"): continue
            data = m.get("data"); data = json.loads(data) if isinstance(data, str) else data
            iid, t, v = m["index_id"], int(data["time"]), float(data["value"])
            (one if typ == "cfbenchmarks_value" else five)[(iid, t)] = v
            offs[typ].append(time.time() * 1000 - t)      # local receipt minus print time
    agree = disagree = missing = 0; bad = []
    for k, v in one.items():
        if k in five:
            if abs(five[k] - v) < 1e-9: agree += 1
            else: disagree += 1; bad.append((k, v, five[k]))
        else: missing += 1
    print("1 Hz prints %d; same (index, second) on 5 Hz: equal %d, different %d, absent on 5 Hz %d" % (len(one), agree, disagree, missing))
    for b in bad[:8]: print("  differs:", b)
    sub = sum(1 for (iid, t) in five if t % 1000)
    print("5 Hz prints %d, of which sub-second %d" % (len(five), sub))
    for typ, xs in offs.items():
        xs.sort(); print("%-22s receipt lag ms: median %.0f  p90 %.0f  n %d" % (typ, xs[len(xs) // 2], xs[int(0.9 * len(xs))], len(xs)))
asyncio.run(main())
