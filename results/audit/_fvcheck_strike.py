"""READ-ONLY audit probe: strike/round_digits/exchange_index as the API really
returns them, plus local-clock skew against Kalshi's own Date header.
No writes, no orders. GET only."""
import json, sys, time, urllib.request, os
sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
sys.path.insert(0, r"C:\kals-repo\research")
from kauth import get, headers, BASE, PREFIX

# ---- 1. clock skew vs the exchange -------------------------------------
import email.utils
skews = []
for _ in range(3):
    path = PREFIX + "/exchange/status"
    req = urllib.request.Request(BASE + path, method="GET")
    for k, v in headers("GET", path).items():
        req.add_header(k, v)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=20) as r:
        t1 = time.time()
        dh = r.headers.get("Date")
    srv = email.utils.parsedate_to_datetime(dh).timestamp()
    mid = (t0 + t1) / 2.0
    skews.append((mid - srv, t1 - t0))
    time.sleep(0.4)
print("CLOCK: local_mid - server_Date (s), rtt (s)")
for s, rtt in skews:
    print(f"   {s:+.3f}   rtt {rtt:.3f}")
print("   (Date header is whole-second, so |skew| < ~1.5s is indistinguishable "
      "from zero; anything beyond that is real.)")

# ---- 2. strike fields, per series --------------------------------------
SER = ["KXBTC15M","KXETH15M","KXSOL15M","KXXRP15M","KXDOGE15M","KXBNB15M",
       "KXBCH15M","KXZEC15M","KXHYPE15M","KXNEAR15M","KXADA15M"]
print("\nSTRIKE FIELDS (open markets)")
print(f"{'series':<12} {'top floor_strike':>20} {'custom.floor_strike':>22} "
      f"{'rd':>4} {'rd type':>8} {'exi':>4} {'delta(top-custom)':>20}")
t0 = time.time()
for s in SER:
    st, b = get("/markets", {"series_ticker": s, "status": "open", "limit": "4"})
    if st != 200 or not isinstance(b, dict):
        print(f"{s:<12} HTTP {st}")
        continue
    ms = b.get("markets") or []
    if not ms:
        print(f"{s:<12} no open markets")
        continue
    m = ms[0]
    cs = m.get("custom_strike") or {}
    top = m.get("floor_strike")
    cust = cs.get("floor_strike")
    rd = cs.get("round_digits")
    d = None
    if top is not None and cust is not None:
        try:
            d = float(top) - float(cust)
        except Exception:
            d = None
    print(f"{s:<12} {str(top):>20} {str(cust):>22} {str(rd):>4} "
          f"{type(rd).__name__:>8} {str(m.get('exchange_index')):>4} "
          f"{('%+.3e' % d) if d is not None else 'n/a':>20}")
print(f"\n11 GETs took {time.time()-t0:.2f}s total "
      f"({(time.time()-t0)/11*1000:.0f} ms each) -- this is the same call the "
      f"live universe pass makes every 20 s, in the same order.")
