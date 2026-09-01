#!/usr/bin/env python3
# VERSION: 2026-08-25-v9
"""
kalshi_fulltape.py  --  Remove the truncation bias and settle D properly.

    pip install requests
    python kalshi_fulltape.py --data ./kalshi_data --out ./fulltape \\
        --series KXBTC15M KXETH15M KXSOL15M --markets 150

WHY

kalshi_recheck exposed the real problem, and it was not clustering. Trades per
market by time bucket came out at 5.9 / 32.3 / 82.7 / 76.8, totalling exactly
198 -- the limit=200 cap. We were reading each market's LAST 200 prints only.
In the first seven minutes of a window we saw ~6 trades per market; in the
final minute ~77.

So the early-window buckets are populated ONLY by markets sparse enough that
early trades survived inside the last-200 window. Those are illiquid markets,
selected on having stopped trading later -- which is what happens when price
runs to resolution. Selection toward markets that trended, then measuring
whether they trended.

The tell: bias magnitude tracks truncation severity exactly. The 0-60s bucket
is the least truncated and every cell from 0.35 to 1.00 read EFFICIENT (max
|t| = 1.9). The heavily truncated buckets showed +12 to +15c "edges". Edges
appear precisely where selection is worst.

THE FIX: paginate each market's tape to exhaustion. Fewer markets, complete
tapes. Then the same market-clustered calibration, plus a truncation
diagnostic that proves the bias is gone.

Also does per-series tails (pooling 9 series whose kurtosis ranges 25 to 153
was itself wrong) and a crash-safe feed check (gzip files being written by the
live collector raise EOFError on read).
"""

import argparse, glob, gzip, json, math, os, time, zlib
import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "research"))
from gzsalvage import iter_lines as salvage_lines   # noqa: E402
from collections import defaultdict
from datetime import datetime, timezone
from statistics import NormalDist, mean, median, pstdev

ND = NormalDist()
BASE = "https://api.elections.kalshi.com/trade-api/v2"

try:
    import requests
except ImportError:
    raise SystemExit("pip install requests")


def parse_ts(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s if s < 1e12 else s / 1000.0)
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


# ==========================================================================
def feed_check(data_dir):
    """Crash-safe. The collector holds the current hour's .gz open and flushing,
    so reading it mid-write raises EOFError. Count what we can and move on."""
    print("=" * 78); print("FEED CHECK"); print("=" * 78)
    for chan in ["cfbenchmarks_value", "pyth_value", "orderbook_delta",
                 "ticker", "trade"]:
        files = sorted(glob.glob(os.path.join(data_dir, chan, "*.jsonl.gz")))
        n, first, partial = 0, None, 0
        for fp in files:
            try:
                for line in salvage_lines(fp):
                        n += 1
                        if first is None and line.strip():
                            first = line.strip()[:280]
            except (OSError, EOFError, zlib.error, gzip.BadGzipFile):
                partial += 1   # EOFError, zlib.error, OSError -- all mean
                               # 'file is mid-write', all are fine
        tag = "OK" if n else "*** EMPTY ***"
        print(f"  {chan:<20}{len(files):>3} files  {n:>10,} msgs  "
              f"({partial} still writing)  {tag}")
        if chan == "cfbenchmarks_value" and first:
            print(f"    sample: {first}")

    # ------------------------------------------------------------------
    # The sample message revealed that Kalshi publishes avg_60s_data: the
    # RUNNING 60-SECOND AVERAGE -- i.e. the settlement quantity itself --
    # already computed, with window_size and window_start_ts_ms.
    # Plus three timestamps (CF `time`, Kalshi `received_at`, our `_rx_ms`)
    # which let us measure the whole latency chain.
    # ------------------------------------------------------------------
    print("\n  --- cfbenchmarks detail ---")
    ids = defaultdict(int)
    lat_cf, lat_us, wsz, have_avg = [], [], [], 0
    tmin, tmax = None, None
    for fp in sorted(glob.glob(os.path.join(data_dir, "cfbenchmarks_value",
                                            "*.jsonl.gz"))):
        try:
            for line in salvage_lines(fp):
                    try:
                        m = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    d = m.get("msg") or {}
                    idx = str(d.get("index_id", "?"))
                    ids[idx] += 1
                    inner = d.get("data")
                    if isinstance(inner, str):
                        try:
                            inner = json.loads(inner)   # nested JSON STRING
                        except json.JSONDecodeError:
                            inner = {}
                    ct = (inner or {}).get("time")
                    ra = d.get("received_at")
                    rx = m.get("_rx_ms")
                    if ct and ra:
                        lat_cf.append(ra - ct)
                        if tmin is None or ct < tmin:
                            tmin = ct
                        if tmax is None or ct > tmax:
                            tmax = ct
                    if ra and rx:
                        lat_us.append(rx - ra)
                    a = d.get("avg_60s_data")
                    if a:
                        have_avg += 1
                        try:
                            wsz.append(int(a.get("window_size", 0)))
                        except (TypeError, ValueError):
                            pass
        except Exception:
            continue

    if ids:
        span_h = ((tmax - tmin) / 3600000.0) if (tmin and tmax) else 0
        print(f"  span {span_h:.2f} h across {len(ids)} indices")
        print(f"  {'index':>14}{'msgs':>9}{'per hour':>11}   (1/sec = 3600)")
        for k, v in sorted(ids.items(), key=lambda x: -x[1]):
            rate = v / span_h if span_h > 0 else 0
            flag = "" if rate > 3000 else "  <-- GAPPY"
            print(f"  {k:>14}{v:>9,}{rate:>11,.0f}{flag}")
        print(f"\n  avg_60s_data present on {100*have_avg/sum(ids.values()):.1f}% "
              f"of messages")
        if wsz:
            wsz.sort()
            print(f"  window_size: min {wsz[0]}  median {wsz[len(wsz)//2]}  "
                  f"max {wsz[-1]}")
            print("  ^ this is the 'seconds already locked in' term the whole")
            print("    (60-s)^1.5 model was built around -- Kalshi hands it to us.")
        if lat_cf:
            lat_cf.sort()
            print(f"\n  LATENCY  CF timestamp -> Kalshi received_at:")
            print(f"    median {lat_cf[len(lat_cf)//2]:,} ms   "
                  f"p90 {lat_cf[int(len(lat_cf)*.9)]:,} ms")
        if lat_us:
            lat_us.sort()
            print(f"  LATENCY  Kalshi received_at -> our machine:")
            print(f"    median {lat_us[len(lat_us)//2]:,} ms   "
                  f"p90 {lat_us[int(len(lat_us)*.9)]:,} ms")
            print("    (includes any clock offset between your PC and Kalshi --")
            print("     run w32tm /resync before trusting the absolute number;")
            print("     the SPREAD between p90 and median is offset-free.)")


# ==========================================================================
def _settled_for(sess, s, n_markets):
    """The n_markets most recently SETTLED markets of one series.

    Cheap: a few paginated /markets calls. This is the half that has to be
    refreshed on every analysis run, because it is the OUTCOMES -- and until
    2026-08-30 nothing refreshed it. run_all.ps1 records quotes forever while
    fulltape was a manual step nobody re-ran, so three consecutive analysis
    runs read the same 3,600 settled markets while the quoted-market count
    grew 3,638 -> 4,797 -> 6,127. Every settlement-dependent result was
    frozen, and "confirm it on fresh data" was impossible by construction.
    """
    ms, cursor, err = [], None, None
    pages, max_pages = 0, max(2, math.ceil(n_markets / 200.0) + 2)
    while len(ms) < n_markets and pages < max_pages:
        p = {"series_ticker": s, "status": "settled", "limit": 200}
        if cursor:
            p["cursor"] = cursor
        # RETRY, do not break. The first version broke out of the loop on any
        # non-200, and Kalshi rate-limits: asking for twelve series at eight
        # requests a second, five of them came back with ZERO markets --
        # including KXBTC15M, the most liquid series on the exchange -- and
        # the rest stopped on a page boundary at 200 or 400. That silently
        # REPLACED a working 3,600-market file with a 1,999-market one.
        ok = False
        for attempt in range(5):
            try:
                r = sess.get(BASE + "/markets", params=p, timeout=30)
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                time.sleep(1.0 * (2 ** attempt))
                continue
            if r.status_code == 200:
                ok = True
                break
            err = f"HTTP {r.status_code}"
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.0 * (2 ** attempt))
                continue
            break                        # a real error, not a rate limit
        if not ok:
            break
        js = r.json()
        b = js.get("markets", [])
        if not b:
            break
        ms += b
        pages += 1
        cursor = js.get("cursor")
        if not cursor:
            break
        time.sleep(0.35)                 # ~3/sec, not ~8/sec
    good = []
    for m in ms:
        try:
            k = float(m.get("floor_strike") or m.get("strike"))
            v = float(m["expiration_value"])
            c = parse_ts(m.get("close_time"))
            if k and v and c:
                good.append({"ticker": m["ticker"], "series": s, "strike": k,
                             "settle": v, "close": c,
                             "result": 1.0 if v >= k else 0.0})
        except (KeyError, TypeError, ValueError):
            continue
    out = sorted(good, key=lambda m: m["close"], reverse=True)[:n_markets]
    if not out:
        # A silent zero is the "empty loader read as a null result" pattern
        # wearing a fetcher's clothes. Say what went wrong.
        print(f"  *** {s}: ZERO settled markets"
              + (f" -- last error: {err}" if err else
                 " -- the API returned rows but none had a usable"
                 " strike/expiration_value/close_time"), flush=True)
    return out


def _write(out_dir, markets, tapes=None):
    """tmp + os.replace, both of them: markets.json is written first and
    tapes.json second, so an interrupt between the two leaves a state where
    every consumer that checks only markets.json proceeds and then dies on the
    missing tapes.json."""
    os.makedirs(out_dir, exist_ok=True)
    todo = [("markets.json", markets)]
    if tapes is not None:
        todo.append(("tapes.json", tapes))
    for name, obj in todo:
        fp = os.path.join(out_dir, name)
        with open(fp + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        os.replace(fp + ".tmp", fp)


def pull_markets_only(series_list, n_markets, out_dir, force=False):
    """Refresh the OUTCOMES and leave tapes.json alone.

    REFUSES to replace a materially larger existing markets.json. The first
    version of this had no such guard, hit a rate limit, and overwrote 3,600
    settled markets with 1,999 -- five series, including BTC, reduced to zero.
    A refresh that can destroy the thing it refreshes is not a refresh.
    """
    sess = requests.Session()
    markets = {}
    for s in series_list:
        markets[s] = _settled_for(sess, s, n_markets)
        print(f"  {s}: {len(markets[s])} settled markets", flush=True)
    new_n = sum(len(v) for v in markets.values())

    fp = os.path.join(out_dir, "markets.json")
    old_n, old_series = 0, 0
    if os.path.exists(fp):
        try:
            prev = json.load(open(fp, encoding="utf-8"))
            old_n = sum(len(v) for v in prev.values())
            old_series = sum(1 for v in prev.values() if v)
        except (OSError, ValueError, AttributeError):
            pass
    new_series = sum(1 for v in markets.values() if v)

    if not force and old_n and (new_n < 0.9 * old_n
                                or new_series < old_series):
        print(f"\n  *** REFUSING TO WRITE. The fetch returned {new_n:,} "
              f"settled markets across {new_series} series;")
        print(f"  *** the file on disk already has {old_n:,} across "
              f"{old_series}. That is a fetch failure, not a shrinking")
        print("  *** market. markets.json is UNCHANGED. Re-run when the API")
        print("  *** is cooperating, or pass --force if the shrink is real.")
        return prev
    _write(out_dir, markets)
    return markets


def pull_full_tapes(series_list, n_markets, out_dir, max_pages=40):
    sess = requests.Session()
    os.makedirs(out_dir, exist_ok=True)
    markets, tapes = {}, {}
    for s in series_list:
        good = _settled_for(sess, s, n_markets)
        markets[s] = good
        print(f"  {s}: {len(good)} markets, pulling FULL tapes...", flush=True)
        got, capped = [], 0
        for i, m in enumerate(good):
            cursor, pages, mine = None, 0, []
            while pages < max_pages:
                p = {"ticker": m["ticker"], "limit": 200}
                if cursor:
                    p["cursor"] = cursor
                try:
                    r = sess.get(BASE + "/markets/trades", params=p, timeout=30)
                    if r.status_code != 200:
                        break
                    js = r.json()
                except Exception:
                    break
                b = js.get("trades", [])
                if not b:
                    break
                mine += b
                cursor = js.get("cursor")
                pages += 1
                if not cursor:
                    break
                time.sleep(0.05)
            if pages >= max_pages:
                capped += 1
            got += mine
            if (i + 1) % 25 == 0:
                print(f"    {i+1}/{len(good)}  {len(got):,} trades", flush=True)
        tapes[s] = got
        print(f"  {s}: {len(got):,} trades, "
              f"{len(got)/max(len(good),1):.0f}/market"
              f"  ({capped} hit the page cap)", flush=True)
    _write(out_dir, markets, tapes)
    return markets, tapes



# ==========================================================================
def calibration(markets, tapes):
    print("\n" + "=" * 78)
    print("D-FINAL  calibration on FULL tapes, clustered by market")
    print("=" * 78)
    idx = {}
    for s, ms in markets.items():
        for m in ms:
            idx[m["ticker"]] = m

    cells = defaultdict(lambda: defaultdict(list))
    outcome, per_bucket = {}, defaultdict(int)
    for s, ts in tapes.items():
        for t in ts:
            tk = t.get("ticker") or t.get("market_ticker")
            m = idx.get(tk)
            if not m:
                continue
            try:
                p = float(t.get("yes_price_dollars") or t.get("yes_price"))
                if p > 1.5:
                    p /= 100.0
                tt = parse_ts(t.get("created_time") or t.get("ts"))
            except (TypeError, ValueError):
                continue
            if tt is None or not (0 < p < 1):
                continue
            ttc = m["close"] - tt
            if not (0 <= ttc <= 900):
                continue
            tb = ("0-60s" if ttc <= 60 else "60-180s" if ttc <= 180 else
                  "180-480s" if ttc <= 480 else "480-900s")
            per_bucket[tb] += 1
            cells[(tb, round(min(max(p, .01), .99) * 20) / 20.0)][tk].append(p)
            outcome[tk] = m["result"]

    nm = len(idx)
    print("  TRUNCATION DIAGNOSTIC (this is the whole point):")
    print(f"  {'bucket':>10}{'trades':>10}{'per market':>13}   was (truncated)")
    was = {"480-900s": 5.9, "180-480s": 32.3, "60-180s": 82.7, "0-60s": 76.8}
    for tb in ["480-900s", "180-480s", "60-180s", "0-60s"]:
        v = per_bucket.get(tb, 0)
        print(f"  {tb:>10}{v:>10,}{v/max(nm,1):>13.1f}   {was[tb]:>6.1f}")
    print("  If 480-900s is no longer ~6/market, the truncation bias is gone.")
    print("  If the early-window 'edges' vanish with it, they were the artefact.\n")

    print(f"  {'window':>10}{'price':>7}{'mkts':>7}{'avg px':>8}{'realized':>10}"
          f"{'edge':>8}{'t':>7}   verdict")
    surv = []
    for key in sorted(cells, key=lambda k: (k[0], k[1])):
        pm = cells[key]
        if len(pm) < 40:
            continue
        obs = [(sum(v) / len(v), outcome[tk]) for tk, v in pm.items()]
        n = len(obs)
        e = mean([o - p for p, o in obs])
        real = mean([o for _, o in obs]); avgp = mean([p for p, _ in obs])
        ph = min(max(real, 1.0 / (n + 2)), 1 - 1.0 / (n + 2))
        se = math.sqrt(ph * (1 - ph) / n)
        t = e / se if se > 0 else 0.0
        deg = real <= 1e-9 or real >= 1 - 1e-9
        v = ("DEGENERATE" if deg else "MISPRICED" if abs(t) > 3 and abs(e) > 0.02
             else "efficient" if abs(t) < 2 else "watch")
        if v == "MISPRICED":
            surv.append((key, e, t, n))
        print(f"  {key[0]:>10}{key[1]:>7.2f}{n:>7}{avgp:>8.3f}{real:>10.3f}"
              f"{e:>+8.3f}{t:>7.1f}   {v}")

    print(f"\n  {len(surv)} cells survive on full tapes"
          f"{':' if surv else '. If zero, the market is efficient on this test.'}")
    for key, e, t, n in surv:
        print(f"    {key[0]:>10} {key[1]:.2f}  edge {100*e:+.1f}c  t={t:.1f}  n={n}")
    if surv:
        print("\n  STILL NOT TRADEABLE ON THIS EVIDENCE: prints sit at bid or ask,")
        print("  so a taker-side gap is the spread. Verify against the collector's")
        print("  own book before believing any of it.")


# ==========================================================================
def tails_per_series(markets):
    print("\n" + "=" * 78)
    print("C-FINAL  tails PER SERIES  [pooling 9 series was wrong]")
    print("=" * 78)
    print(f"  {'series':>11}{'n':>7}{'kurt':>8}"
          f"{'  90c':>8}{'  95c':>8}{'  98c':>8}{'  99c':>8}{'crossover':>11}")
    for s, ms in sorted(markets.items()):
        if len(ms) < 300:
            continue
        rel = sorted((m["settle"] - m["strike"]) / m["strike"] for m in ms)
        k = max(int(len(rel) * 0.001), 1)
        rel = rel[k:len(rel) - k]                      # winsorize
        sd = pstdev(rel)
        if sd <= 0:
            continue
        z = [r / sd for r in rel]
        n = len(z); mu = mean(z)
        m2 = sum((x - mu) ** 2 for x in z) / n
        m4 = sum((x - mu) ** 4 for x in z) / n
        s2 = math.sqrt(m2)
        ratios = {}
        for zz in [1.282, 1.645, 2.054, 2.326]:
            g = 2 * (1 - ND.cdf(zz))
            o = sum(1 for x in z if abs(x / s2) > zz) / n
            ratios[zz] = o / g if g > 0 else float("nan")
        # crossover where ratio crosses 1
        xs = sorted(ratios)
        cross = None
        for i in range(len(xs) - 1):
            a, b = ratios[xs[i]], ratios[xs[i + 1]]
            if (a - 1) * (b - 1) < 0:
                la, lb = math.log(a), math.log(b)
                tt = (0 - la) / (lb - la)
                cz = xs[i] + tt * (xs[i + 1] - xs[i])
                cross = ND.cdf(cz)
                break
        cs = f"{100*cross:.1f}c" if cross else "none"
        print(f"  {s:>11}{n:>7}{m4/(m2**2):>8.1f}"
              f"{ratios[1.282]:>8.2f}{ratios[1.645]:>8.2f}"
              f"{ratios[2.054]:>8.2f}{ratios[2.326]:>8.2f}{cs:>11}")
    print("\n  Pooled crossover was 96.6c (June archive) and 96.7c (recent) --")
    print("  two independent datasets agreeing. Per-series tells us whether that")
    print("  holds everywhere or is an average over very different assets.")
    print("  Below the crossover a Gaussian model UNDERvalues the favourite;")
    print("  above it, OVERvalues. That is a model-building fact regardless of")
    print("  whether the market itself is exploitable.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    # ALL TWELVE recorded series, not three. The collector subscribes to every
    # one of these (research/replay.py SERIES_TO_INDEX) and the quote tape
    # covers them all, but the settlement fetch defaulted to three -- so nine
    # series had quotes and no outcomes, and every settlement-dependent stage
    # silently measured a quarter of the recording.
    ap.add_argument("--series", nargs="*",
                    default=["KXADA15M", "KXBCH15M", "KXBNB15M", "KXBTC15M",
                             "KXDOGE15M", "KXETH15M", "KXHYPE15M",
                             "KXNEAR15M", "KXSOL15M", "KXTON15M",
                             "KXXRP15M", "KXZEC15M"])
    ap.add_argument("--markets", type=int, default=150)
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="write markets.json even if the fetch came back "
                         "materially smaller than the file already there")
    ap.add_argument("--markets-only", action="store_true",
                    help="fetch settled markets.json and STOP. Skips the "
                         "per-market trade tapes, which are the 10-15 min and "
                         "which only placebo and pathstats read. This is the "
                         "mode an automated refresh wants.")
    a = ap.parse_args()

    feed_check(a.data)
    if a.markets_only:
        # markets.json is CHEAP -- a few paginated /markets calls per series.
        # tapes.json is the expensive part and nothing that needs a fresh
        # settlement needs it. Keeping these separate is what lets an
        # automated run refresh the outcomes every time.
        markets = pull_markets_only(a.series, a.markets, a.out, a.force)
        tails_per_series(markets)
        n = sum(len(v) for v in markets.values())
        print(f"\n  markets.json refreshed: {n:,} settled markets across "
              f"{len(markets)} series. tapes.json left as it was.")
        return
    if a.reuse:
        markets = json.load(open(os.path.join(a.out, "markets.json"), encoding="utf-8"))
        tapes = json.load(open(os.path.join(a.out, "tapes.json"), encoding="utf-8"))
    else:
        print("\nPulling full tapes (10-15 min)...")
        markets, tapes = pull_full_tapes(a.series, a.markets, a.out)
    tails_per_series(markets)
    calibration(markets, tapes)
    print("\nPaste this whole output back.")


if __name__ == "__main__":
    main()
