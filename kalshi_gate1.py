#!/usr/bin/env python3
# VERSION: 2026-08-25-v1
"""
kalshi_gate1.py  --  THE GATE. Does our settlement reconstruction match Kalshi's?

    python kalshi_gate1.py --data ./kalshi_data

Everything downstream assumes we understand the contract. This proves it or
kills it. Run once a few hours of recording exist; run again before any model
work. Needs no API key (settled markets are public).

WHAT IT DOES
  1. Rebuilds each index's 1-second tick series from cfbenchmarks_value.
  2. For every market that CLOSED inside the recording window, computes
     mean(ticks in [close-60s, close]) -- the contract's stated settlement rule.
  3. Compares to Kalshi's own expiration_value, to the cent.
  4. Separately checks the PUBLISHED avg_60s_data at close against
     expiration_value. If that matches, we never need to reconstruct anything.
  5. Tests boundary conventions (inclusive/exclusive endpoints) because an
     off-by-one-second window is the most likely way to be subtly wrong.

PASS = median |error| under ~1 cent of index value.
FAIL = stop. Do not build a model on a contract you cannot reproduce.
"""

import argparse, glob, gzip, json, math, os
from collections import defaultdict
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    raise SystemExit("pip install requests")

BASE = "https://api.elections.kalshi.com/trade-api/v2"

# index_id -> series ticker
INDEX_TO_SERIES = {
    "BRTI": "KXBTC15M", "ETHUSD_RTI": "KXETH15M", "SOLUSD_RTI": "KXSOL15M",
    "XRPUSD_RTI": "KXXRP15M", "DOGEUSD_RTI": "KXDOGE15M",
    "BNBUSD_RTI": "KXBNB15M", "BCHUSD_RTI": "KXBCH15M",
    "ZECUSD_RTI": "KXZEC15M", "HYPEUSD_RTI": "KXHYPE15M",
    "NEARUSD_RTI": "KXNEAR15M", "ADAUSD_RTI": "KXADA15M",
    "TONUSD_RTI": "KXTON15M",
}
SERIES_TO_INDEX = {v: k for k, v in INDEX_TO_SERIES.items()}


def parse_ts(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s if s < 1e12 else s / 1000.0)
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def load_ticks(data_dir):
    """index_id -> sorted [(cf_time_sec, value, avg60_or_None)]"""
    acc = defaultdict(list)
    files = sorted(glob.glob(os.path.join(data_dir, "cfbenchmarks_value",
                                          "*.jsonl.gz")))
    print(f"  reading {len(files)} cfbenchmarks files...")
    for fp in files:
        try:
            with gzip.open(fp, "rt") as f:
                for line in f:
                    try:
                        m = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    d = m.get("msg") or {}
                    idx = d.get("index_id")
                    inner = d.get("data")
                    if isinstance(inner, str):
                        try:
                            inner = json.loads(inner)
                        except json.JSONDecodeError:
                            continue
                    if not idx or not isinstance(inner, dict):
                        continue
                    try:
                        t = float(inner["time"]) / 1000.0   # CF's own clock
                        v = float(inner["value"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    a = None
                    av = d.get("avg_60s_data")
                    if isinstance(av, dict):
                        try:
                            a = float(av.get("value"))
                        except (TypeError, ValueError):
                            a = None
                    acc[idx].append((t, v, a))
        except Exception:
            continue
    out = {}
    for k, v in acc.items():
        v.sort()
        # de-duplicate by second, keeping the last value for that second
        ded = {}
        for t, val, a in v:
            ded[int(round(t))] = (val, a)
        out[k] = ded
        span = (max(ded) - min(ded)) / 3600.0 if ded else 0
        print(f"    {k:>13}: {len(ded):>6,} unique seconds, span {span:.2f} h")
    return out


def fetch_settled(series, t_lo, t_hi):
    """Settled markets whose close_time falls in the recorded window."""
    sess = requests.Session()
    out, cursor = [], None
    for _ in range(12):
        p = {"series_ticker": series, "status": "settled", "limit": 200}
        if cursor:
            p["cursor"] = cursor
        try:
            r = sess.get(BASE + "/markets", params=p, timeout=30)
            if r.status_code != 200:
                break
            js = r.json()
        except Exception:
            break
        b = js.get("markets", [])
        if not b:
            break
        for m in b:
            c = parse_ts(m.get("close_time"))
            try:
                ev = float(m["expiration_value"])
                k = float(m.get("floor_strike") or m.get("strike"))
            except (KeyError, TypeError, ValueError):
                continue
            if c and t_lo <= c <= t_hi:
                out.append({"ticker": m["ticker"], "close": c,
                            "settle": ev, "strike": k})
        cursor = js.get("cursor")
        if not cursor:
            break
    return out


def window_mean(ded, lo, hi):
    """mean of ticks with second in [lo, hi]; returns (mean, count)"""
    vals = [ded[s][0] for s in range(int(lo), int(hi) + 1) if s in ded]
    return (sum(vals) / len(vals), len(vals)) if vals else (None, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    a = ap.parse_args()

    print("=" * 78); print("GATE 1  settlement reconstruction"); print("=" * 78)
    ticks = load_ticks(a.data)
    if not ticks:
        raise SystemExit("\n  No cfbenchmarks data. Nothing to check yet.")

    lo = min(min(d) for d in ticks.values() if d)
    hi = max(max(d) for d in ticks.values() if d)
    print(f"\n  recorded span: {datetime.fromtimestamp(lo, timezone.utc):%Y-%m-%d %H:%M} "
          f"-> {datetime.fromtimestamp(hi, timezone.utc):%H:%M} UTC "
          f"({(hi-lo)/3600:.2f} h)")

    # Four plausible boundary conventions. An off-by-one second is the most
    # likely way to be quietly wrong, so test them all and see which wins.
    CONVS = [("[close-60, close-1]", -60, -1),
             ("[close-59, close]", -59, 0),
             ("[close-60, close]", -60, 0),
             ("[close-61, close-2]", -61, -2)]

    results = defaultdict(list)
    pub_err, n_mkt = [], 0
    for idx, ded in ticks.items():
        series = INDEX_TO_SERIES.get(idx)
        if not series or not ded:
            continue
        mkts = fetch_settled(series, lo + 60, hi)
        if not mkts:
            continue
        n_mkt += len(mkts)
        print(f"  {series:>11}: {len(mkts)} settled markets inside the window")
        for m in mkts:
            c = int(round(m["close"]))
            for name, o1, o2 in CONVS:
                mu, cnt = window_mean(ded, c + o1, c + o2)
                if mu is not None and cnt >= 45:
                    results[name].append(abs(mu - m["settle"]) / m["settle"])
            # published rolling average nearest to close
            best = None
            for s in range(c, c - 4, -1):
                if s in ded and ded[s][1] is not None:
                    best = ded[s][1]; break
            if best is not None:
                pub_err.append(abs(best - m["settle"]) / m["settle"])

    if n_mkt == 0:
        print("\n  No settled markets closed inside the recorded span yet.")
        print("  Let the collector run a few more hours and re-run this.")
        return

    print(f"\n  {n_mkt} markets checked\n")
    print(f"  {'convention':>22}{'n':>6}{'median rel err':>16}{'p90':>12}{'max':>12}")
    best_name, best_med = None, 1e9
    for name, _, _ in CONVS:
        e = sorted(results.get(name) or [])
        if not e:
            continue
        med = e[len(e) // 2]
        print(f"  {name:>22}{len(e):>6}{med:>15.2e}{e[int(len(e)*.9)]:>12.2e}"
              f"{e[-1]:>12.2e}")
        if med < best_med:
            best_name, best_med = name, med

    if pub_err:
        pe = sorted(pub_err)
        print(f"\n  {'PUBLISHED avg_60s':>22}{len(pe):>6}"
              f"{pe[len(pe)//2]:>15.2e}{pe[int(len(pe)*.9)]:>12.2e}{pe[-1]:>12.2e}")
        print("  ^ if this matches, we can use Kalshi's own rolling average and")
        print("    never reconstruct the TWAP ourselves.")

    print(f"\n  BEST CONVENTION: {best_name}  (median rel err {best_med:.2e})")
    if best_med < 1e-5:
        print("  *** GATE 1 PASS *** settlement reproduced to ~1 part in 100,000.")
        print("  The contract is understood. Model work is now safe to start.")
    elif best_med < 1e-4:
        print("  MARGINAL. Close but not exact -- likely a boundary or rounding")
        print("  detail. Worth resolving before trusting tail probabilities,")
        print("  since those are most sensitive to small mean errors.")
    else:
        print("  *** GATE 1 FAIL *** stop. We do not reproduce settlement, so")
        print("  every probability downstream would be built on sand.")


if __name__ == "__main__":
    main()
