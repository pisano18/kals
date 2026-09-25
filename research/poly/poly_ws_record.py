"""scan_poly_ws.py -- READ-ONLY WebSocket recorder for Polymarket US market
data (wss://api.polymarket.us/v1/ws/markets), authenticated with the operator's
existing read key exactly as C:\\kals\\poly_us.py signs a GET (Ed25519 over
timestamp+METHOD+path). Subscribes to full MARKET_DATA and TRADE for the live
and next BTC 15m windows and the live 1h window; re-subscribes every window.
Every frame is written with a local receive timestamp to a gzip jsonl.
No order endpoint is touched; this file contains no HTTP POST and no order
message. Stops on scan_poly_ws.stop.
"""
import asyncio, gzip, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"C:\kals")
import poly_us  # noqa: E402
import websockets  # noqa: E402

OUT = os.path.join(HERE, "scan_poly_ws.jsonl.gz")
LOG = os.path.join(HERE, "scan_poly_ws.log")
STOP = os.path.join(HERE, "scan_poly_ws.stop")
RUN_S = float(sys.argv[1]) if len(sys.argv) > 1 else 4 * 3600
URL = "wss://api.polymarket.us/v1/ws/markets"
PATH = "/v1/ws/markets"


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + msg + "\n")


def slugs(now):
    st15 = int(now) // 900 * 900
    st1h = int(now) // 3600 * 3600
    s = []
    for st in (st15, st15 + 900):
        s.append("cpc-btc-updown-15m-" + time.strftime("%Y-%m-%d-%H%Mz", time.gmtime(st)))
    s.append("cpc-btc-updown-1h-" + time.strftime("%Y-%m-%d-%H%Mz", time.gmtime(st1h)))
    return s


def auth_headers():
    creds = json.load(open(poly_us.CREDS))
    key_id = creds.get("key_id") or creds.get("apiKey") or creds.get("access_key") or creds.get("key")
    secret = creds.get("secret") or creds.get("private_key") or creds.get("secret_key")
    priv = poly_us.load_key(secret)
    return poly_us.headers(key_id, priv, "GET", PATH)


async def run():
    t_end = time.time() + RUN_S
    n = 0
    with gzip.open(OUT, "at", encoding="utf-8") as out:
        while time.time() < t_end and not os.path.exists(STOP):
            try:
                hdrs = auth_headers()
                async with websockets.connect(URL, additional_headers=hdrs, max_size=8_000_000, ping_interval=20) as ws:
                    log("connected")
                    done = set()   # slugs this connection already subscribed
                    while time.time() < t_end and not os.path.exists(STOP):
                        new = [s_ for s_ in slugs(time.time()) if s_ not in done]
                        if new:
                            # ONLY new slugs: a request that repeats one already
                            # subscribed is rejected whole (2026-09-25 fix)
                            for i, styp in enumerate(("SUBSCRIPTION_TYPE_MARKET_DATA", "SUBSCRIPTION_TYPE_TRADE")):
                                msg = {"subscribe": {"requestId": "sub-%d-%d" % (int(time.time()), i), "subscriptionType": styp,
                                                     "marketSlugs": new, "responsesDebounced": False}}
                                await ws.send(json.dumps(msg))
                            log("subscribed %s" % new)
                            done.update(new)
                        try:
                            frame = await asyncio.wait_for(ws.recv(), timeout=5)
                        except asyncio.TimeoutError:
                            continue
                        out.write(json.dumps({"rx": round(time.time(), 3), "f": frame if isinstance(frame, str) else "<binary>"},
                                             separators=(",", ":")) + "\n")
                        n += 1
                        if n % 200 == 0:
                            out.flush()
            except Exception as e:  # noqa: BLE001
                log("ws error: %s" % str(e)[:300])
                await asyncio.sleep(5)
    log("end frames=%d" % n)


if __name__ == "__main__":
    asyncio.run(run())
