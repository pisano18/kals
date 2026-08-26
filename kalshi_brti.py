#!/usr/bin/env python3
# VERSION: 2026-08-25-v1
"""
kalshi_brti.py  --  Get the REAL index prices behind every settled window.

    python kalshi_brti.py --out ./fulltape --key-id XXX --key-file kalshi.pem

WHY THIS IS THE UNLOCK

Until now the backtest only saw CONTRACT prices. That is like betting on a
horse race where you can see the odds board but not the horses. The contract
is a function of BRTI, and without BRTI every strategy is reduced to reading
the odds board.

With the index path for each window we can compute, at every single second:
  * exact distance from strike, in dollars and in sigma
  * realized volatility inside the window, updating live
  * a true fair value P(settle >= strike) using the confirmed settlement rule
  * the gap between that fair value and what the contract is trading at
  * LEAD-LAG between BRTI and the contract price

That last one is the big one. If the contract price lags BRTI by even a
second, that is a mechanical edge requiring no forecasting whatsoever -- you
already know where the contract is going. It is also the single most likely
place for an edge to survive, because it is a plumbing artefact rather than a
pricing opinion.

ENDPOINT DISCOVERY
Kalshi's changelog confirms GET /trade-api/v2/cfbenchmarks/* serves historical
index values, and GET /trade-api/v2/live_data/events/{event_ticker} serves
crypto price charts. Neither sub-path is publicly documented, so this script
probes candidates, prints the raw response of whichever works, and only then
bulk-pulls. Same approach that cracked the websocket channel.

OUTPUT: brti.json  ->  {market_ticker: [[unix_sec, value], ...]}
Normalized here so the backtest never has to care what the API looked like.
"""

import argparse, base64, json, math, os, sys, time
from collections import defaultdict
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    raise SystemExit("pip install requests cryptography")

BASE = "https://api.elections.kalshi.com/trade-api/v2"
PATH_PREFIX = "/trade-api/v2"

SERIES_INDEX = {"KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI",
                "KXSOL15M": "SOLUSD_RTI", "KXXRP15M": "XRPUSD_RTI",
                "KXDOGE15M": "DOGEUSD_RTI", "KXBNB15M": "BNBUSD_RTI",
                "KXBCH15M": "BCHUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
                "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI"}


def make_signer(key_id, key_file):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    pk = serialization.load_pem_private_key(open(key_file, "rb").read(), password=None)
    def sign(method, path):
        ts = str(int(time.time() * 1000))
        sig = pk.sign((ts + method.upper() + path).encode(),
                      padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                  salt_length=padding.PSS.DIGEST_LENGTH),
                      hashes.SHA256())
        return {"KALSHI-ACCESS-KEY": key_id,
                "KALSHI-ACCESS-TIMESTAMP": ts,
                "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode()}
    return sign


class API:
    def __init__(self, sign=None):
        self.sign, self.s = sign, requests.Session()
    def get(self, path, **params):
        h = {"Accept": "application/json"}
        if self.sign:
            h.update(self.sign("GET", PATH_PREFIX + path))
        r = self.s.get(BASE + path, params=params or None, headers=h, timeout=30)
        return r


def parse_ts(s):
    if isinstance(s, (int, float)):
        return float(s if s < 1e12 else s / 1000.0)
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def extract_series(obj):
    """Pull [(ts_sec, value)] out of whatever shape came back. Handles the
    common encodings: list of dicts, list of pairs, dict of lists."""
    out = []

    def val(d, keys):
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return None

    def walk(o):
        if isinstance(o, list):
            for item in o:
                if isinstance(item, dict):
                    t = val(item, ["ts", "time", "timestamp", "t",
                                   "ts_ms", "end_period_ts"])
                    v = val(item, ["value", "price", "v", "close", "index_value"])
                    if t is not None and v is not None:
                        tt, vv = parse_ts(t), None
                        try: vv = float(v)
                        except (TypeError, ValueError): vv = None
                        if tt and vv: out.append((tt, vv))
                    else:
                        walk(item)
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    tt, vv = parse_ts(item[0]), None
                    try: vv = float(item[1])
                    except (TypeError, ValueError): vv = None
                    if tt and vv: out.append((tt, vv))
        elif isinstance(o, dict):
            for v in o.values():
                if isinstance(v, (list, dict)):
                    walk(v)
    walk(obj)
    out.sort()
    return out


def discover(api, index_id, t_from, t_to, event_ticker=None):
    """Probe candidate endpoints. Returns (path, param_builder) or None."""
    print("=" * 78); print("ENDPOINT DISCOVERY"); print("=" * 78)

    cands = []
    if event_ticker:
        cands += [(f"/live_data/events/{event_ticker}", lambda a, b: {}),
                  (f"/live_data/events/{event_ticker}",
                   lambda a, b: {"from": int(a * 1000), "to": int(b * 1000)}),
                  (f"/live_data/events/{event_ticker}",
                   lambda a, b: {"last_sec": int(b - a)})]
    for p in ["/cfbenchmarks/values", "/cfbenchmarks/history",
              "/cfbenchmarks/index_values", "/cfbenchmarks/v1/values",
              f"/cfbenchmarks/indices/{index_id}/values",
              f"/cfbenchmarks/{index_id}/values", f"/cfbenchmarks/{index_id}"]:
        cands += [
            (p, lambda a, b: {"index_id": index_id,
                              "from": int(a * 1000), "to": int(b * 1000)}),
            (p, lambda a, b: {"index_ids": index_id,
                              "start_ts": int(a), "end_ts": int(b)}),
            (p, lambda a, b: {"id": index_id, "from": int(a), "to": int(b)}),
            (p, lambda a, b: {"last_sec": int(b - a), "index_id": index_id}),
        ]

    seen = set()
    for path, build in cands:
        params = build(t_from, t_to)
        key = (path, tuple(sorted(params)))
        if key in seen: continue
        seen.add(key)
        try:
            r = api.get(path, **params)
        except Exception as e:
            print(f"  {path} {list(params)}: {type(e).__name__}"); continue
        if r.status_code != 200:
            print(f"  {path} {list(params)}: HTTP {r.status_code} "
                  f"{r.text[:110]}")
            continue
        try:
            js = r.json()
        except ValueError:
            print(f"  {path}: 200 but not JSON"); continue
        pts = extract_series(js)
        print(f"  {path} {list(params)}: HTTP 200, {len(pts)} points extracted")
        if len(pts) >= 10:
            print(f"\n  *** WORKING: {path} with {list(params)} ***")
            print(f"  raw sample: {json.dumps(js)[:500]}")
            print(f"  first 3 points: {pts[:3]}")
            span = pts[-1][0] - pts[0][0]
            print(f"  span {span/60:.1f} min, "
                  f"cadence ~{span/max(len(pts)-1,1):.2f} s/point")
            return path, build
        elif pts:
            print(f"    (only {len(pts)} points -- keeping looking)")
    print("\n  NOTHING WORKED. Paste this output back; the response bodies")
    print("  above usually name the required parameter, which is how the")
    print("  websocket channel got solved.")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--key-id"); ap.add_argument("--key-file")
    ap.add_argument("--markets", type=int, default=450)
    ap.add_argument("--discover-only", action="store_true")
    a = ap.parse_args()

    sign = make_signer(a.key_id, a.key_file) if (a.key_id and a.key_file) else None
    api = API(sign)
    print(f"auth: {'yes' if sign else 'NO (may be required)'}")

    markets = json.load(open(os.path.join(a.out, "markets.json"), encoding="utf-8"))
    allm = sorted([m for ms in markets.values() for m in ms],
                  key=lambda x: x["close"], reverse=True)[:a.markets]
    print(f"markets to cover: {len(allm)}")

    probe = allm[0]
    ev = probe["ticker"].rsplit("-", 1)[0]
    idx_id = SERIES_INDEX.get(probe["series"], "BRTI")
    found = discover(api, idx_id, probe["close"] - 960, probe["close"] + 60, ev)
    if not found or a.discover_only:
        return
    path_tmpl, build = found
    uses_event = "/live_data/events/" in path_tmpl

    print("\n" + "=" * 78); print("BULK PULL"); print("=" * 78)
    out, fails = {}, 0
    for i, m in enumerate(allm):
        idx_id = SERIES_INDEX.get(m["series"], "BRTI")
        lo, hi = m["close"] - 960, m["close"] + 30
        path = (f"/live_data/events/{m['ticker'].rsplit('-',1)[0]}"
                if uses_event else path_tmpl)
        params = build(lo, hi)
        for k in ("index_id", "index_ids", "id"):
            if k in params: params[k] = idx_id
        try:
            r = api.get(path, **params)
            pts = extract_series(r.json()) if r.status_code == 200 else []
        except Exception:
            pts = []
        pts = [(t, v) for t, v in pts if lo <= t <= hi]
        if len(pts) >= 200:
            out[m["ticker"]] = [[t, v] for t, v in pts]
        else:
            fails += 1
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(allm)}  ok={len(out)} thin/failed={fails}",
                  flush=True)
        time.sleep(0.08)

    fp = os.path.join(a.out, "brti.json")
    json.dump(out, open(fp, "w", encoding="utf-8"))
    print(f"\n  saved {len(out)} markets to {fp}")
    if out:
        k = next(iter(out))
        pts = out[k]
        print(f"  sample {k}: {len(pts)} points, "
              f"{pts[-1][0]-pts[0][0]:.0f}s span")
        m = next(mm for mm in allm if mm["ticker"] == k)
        tail = [v for t, v in pts if m["close"] - 60 <= t <= m["close"]]
        if len(tail) >= 45:
            rec = sum(tail) / len(tail)
            err = abs(rec - m["settle"]) / m["settle"]
            print(f"\n  SETTLEMENT SPOT-CHECK on {k}:")
            print(f"    reconstructed 60s avg : {rec:.4f}  ({len(tail)} ticks)")
            print(f"    Kalshi expiration_value: {m['settle']:.4f}")
            print(f"    relative error         : {err:.2e}")
            print("    " + ("MATCH -- the data is real and aligned."
                            if err < 1e-4 else
                            "MISMATCH -- check timestamp units/timezone before use."))


if __name__ == "__main__":
    main()
