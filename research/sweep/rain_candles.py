"""rain_candles.py -- the SJ02 rain tail NO desk candle measurement, weekly re-run (read-only).

Re-derives the 2026-10-02 sweep refuter's number (.sweep/run-2026-10-02/refute-20261002-02/refute.py)
on EVERY settled KXRAIN market, extended forward each week: pull the settled list fresh (paginated
/markets, series KXRAIN), fetch hourly candles (close-30h .. close, one GET a market) for markets not
yet cached, then at decision time D = close - 22 h take the last hourly candle's YES bid close as the
price we would HIT (buy NO at 1 - bid). Fee 0.07*p*(1-p)*lot, ceil to the cent per order.

Bar (IDEA_LEDGER U10 / SJ02, pre-registered 2026-10-02): 400+ markets at the 3-10c rung, losses
<= 2.5 per 100, net >= +1.5c a contract at the 25-lot fill, and 15+ October/November dates.

    python research/sweep/rain_candles.py --selftest
    python research/sweep/rain_candles.py                 # pull + fetch new + report (~1-3 min)
    python research/sweep/rain_candles.py --verify 30     # also re-fetch 30 cached markets, assert equal
    python research/sweep/rain_candles.py --refetch       # ignore the candle cache (one GET a market)

Cache: .sweep/rain_candles/candles.jsonl (gitignored; seeded from the sweep's two candle files on first
run so the 1,502 markets measured on 10-02 are not re-pulled). Candles of a settled market never change,
and --verify checks that claim against the live API every run it is asked to.
NOT the backtest: nothing here touches pinsim/pindata; the only data is Kalshi's own candle history.
"""
import argparse
import collections
import datetime as dt
import json
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "research"))
CACHE_DIR = os.path.join(ROOT, ".sweep", "rain_candles")
CACHE = os.path.join(CACHE_DIR, "candles.jsonl")
SEEDS = [os.path.join(ROOT, ".sweep", "run-2026-10-02", "refute-20261002-02", "candles_more.jsonl"),
         os.path.join(ROOT, ".sweep", "run-2026-10-02", "check-20261002-02", "candles_hourly.jsonl")]
UTC = dt.timezone.utc
H_DECIDE = 22
LOT = 25
BAR = dict(n=400, loss_per_100=2.5, net_c=1.5, octnov_dates=15)
BUCKETS = [("1c", 0.01, 0.01), ("2c", 0.02, 0.02), ("3-5c", 0.03, 0.05), ("6-10c", 0.06, 0.10),
           ("1-2c", 0.01, 0.02), ("3-10c", 0.03, 0.10), ("1-10c", 0.01, 0.10), ("11-20c", 0.11, 0.20)]


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def fee_c(p_no, lot):
    """Taker fee in cents per contract, the order's fee ceiled to the cent then spread over the lot."""
    return math.ceil(0.07 * p_no * (1 - p_no) * lot * 100) / lot


def binom_upper(k, n, conf=0.95):
    """Upper 95% bound on the loss rate (exact binomial, bisection, stdlib only)."""
    def cdf(p):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if cdf(mid) > 1 - conf:
            lo = mid
        else:
            hi = mid
    return hi


def decide(r, H=H_DECIDE):
    """YES bid/ask close of the last hourly candle ending at or before close - H hours, or None."""
    cut = r["close"] - H * 3600
    cands = [c for c in r["c"] if c["e"] <= cut and c["yb"] is not None]
    if not cands:
        return None
    c = max(cands, key=lambda x: x["e"])
    if r["close"] - c["e"] > (H + 6) * 3600:
        return None
    yb = float(c["yb"])
    ya = float(c["ya"]) if c["ya"] else None
    return yb, ya


def date_of(r):
    return dt.datetime.strptime(r["ticker"].split("-")[1], "%y%b%d").date()


def run(rows, H=H_DECIDE, lot=LOT, label="", out=print):
    out(f"\n== {label}  (decide at close-{H}h, lot {lot}, hit the YES bid, taker fee)")
    out(f"{'rung':>7} {'n':>5} {'dates':>5} {'octnov':>6} {'loss':>4} {'loss/100':>8} {'95%up':>6} "
        f"{'be/100':>6} {'net c':>6} {'$/mkt':>6} {'avgbid':>6}  loss tickers")
    res = {}
    for name, lo, hi in BUCKETS:
        n = loss = 0
        pnl = 0.0
        dates, losses, bids = set(), [], []
        for r in rows:
            d = decide(r, H)
            if d is None:
                continue
            yb, _ = d
            if not (lo - 1e-9 <= yb <= hi + 1e-9):
                continue
            p_no = 1 - yb
            lost = r["result"] == "yes"
            n += 1
            loss += lost
            bids.append(yb)
            dates.add(date_of(r))
            pnl += (-(p_no * 100) if lost else yb * 100) - fee_c(p_no, lot)
            if lost:
                losses.append((r["ticker"].split("KXRAIN-")[1], round(yb * 100)))
        if n == 0:
            out(f"{name:>7} {0:5}")
            continue
        avg = sum(bids) / n
        be = 100 * (avg - fee_c(1 - avg, lot) / 100)
        up = 100 * binom_upper(loss, n)
        octnov = sum(1 for x in dates if x.month in (10, 11))
        out(f"{name:>7} {n:5} {len(dates):5} {octnov:6} {loss:4} {100 * loss / n:8.2f} {up:6.1f} {be:6.1f} "
            f"{pnl / n:6.2f} {pnl / n * lot / 100:6.2f} {avg * 100:6.1f}  {losses[:8]}")
        res[name] = dict(n=n, loss=loss, loss_per_100=100 * loss / n, net=pnl / n, dates=len(dates),
                         octnov=octnov, oct=sum(1 for x in dates if x.month == 10), losses=losses)
    return res


def verdict(res):
    """The pre-registered bar on the 3-10c rung. Returns (all_pass, lines)."""
    r = res.get("3-10c")
    if not r:
        return False, ["3-10c: no markets -- bar FAIL"]
    checks = [("n >= %d" % BAR["n"], r["n"] >= BAR["n"], "%d" % r["n"]),
              ("losses <= %.1f per 100" % BAR["loss_per_100"], r["loss_per_100"] <= BAR["loss_per_100"],
               "%.2f per 100 (%d of %d)" % (r["loss_per_100"], r["loss"], r["n"])),
              ("net >= +%.1fc a contract" % BAR["net_c"], r["net"] >= BAR["net_c"], "%+.2fc" % r["net"]),
              ("Oct/Nov dates >= %d" % BAR["octnov_dates"], r["octnov"] >= BAR["octnov_dates"],
               "%d (Oct %d)" % (r["octnov"], r["oct"]))]
    lines = ["3-10c bar: " + "; ".join("%s: %s %s" % (c, v, "PASS" if ok else "FAIL") for c, ok, v in checks)]
    return all(ok for _, ok, _ in checks), lines


def selftest():
    close = 2_000_000
    rows = []
    for i in range(60):
        cs = [{"e": close - h * 3600, "yb": "0.0300", "ya": "0.0500"} for h in range(29, -1, -1)]
        rows.append({"ticker": "KXRAIN-26OCT%02d-ATL" % (i % 20 + 1), "close": close,
                     "result": "yes" if i < 3 else "no", "c": cs})
    # a market whose last candle before the cut is too old (> H+6 h) must be skipped
    rows.append({"ticker": "KXRAIN-26AUG01-OLD", "close": close, "result": "no",
                 "c": [{"e": close - 29 * 3600, "yb": "0.0300", "ya": "0.0500"}]})
    quiet = lambda *_: None
    a = run(rows, label="st", out=quiet)
    e = run([], label="empty", out=quiet)
    assert a["3-5c"]["n"] == 60 and a["3-5c"]["loss"] == 3, a["3-5c"]
    exp = (57 * 3 - 3 * 97) / 60 - fee_c(0.97, 25)
    assert abs(a["3-5c"]["net"] - exp) < 1e-9, (a["3-5c"]["net"], exp)
    assert a["3-10c"]["octnov"] == 20 and a["3-10c"]["oct"] == 20, a["3-10c"]
    assert "3-5c" not in e and "1-10c" not in e
    assert abs(fee_c(0.97, 25) - 0.24) < 1e-9 and abs(fee_c(0.99, 25) - 0.08) < 1e-9
    assert abs(binom_upper(0, 100) - 0.0295) < 0.001, binom_upper(0, 100)
    ok, _ = verdict(a)
    assert not ok, "60 markets must FAIL the 400-market bar"
    big = [dict(r, ticker=r["ticker"].replace("-ATL", "-C%02d" % k)) for k in range(8) for r in rows[3:]]
    ok, lines = verdict(run(big, label="big", out=quiet))
    assert ok, lines
    # no replay import anywhere in this file's working code
    for ln in open(__file__, encoding="utf-8"):
        s = ln.strip()
        assert not (s.startswith(("import ", "from ")) and any(w in s for w in ("replay", "pinsim", "pindata"))), s
    print("selftest ok")


def pull_settled(kauth):
    ms, cursor = [], None
    while True:
        p = {"series_ticker": "KXRAIN", "status": "settled", "limit": "200"}
        if cursor:
            p["cursor"] = cursor
        st, b = kauth.get("/markets", p)
        if st != 200:
            raise SystemExit("HTTP %s on /markets: %s" % (st, str(b)[:200]))
        ms += b.get("markets", [])
        cursor = b.get("cursor")
        if not cursor:
            break
        time.sleep(0.15)
    return ms


def fetch_candles(kauth, m):
    t = m["ticker"]
    close = int(ts(m["close_time"]))
    st, b = kauth.get("/series/KXRAIN/markets/%s/candlesticks" % t,
                      {"start_ts": str(close - 30 * 3600), "end_ts": str(close + 60), "period_interval": "60"})
    if st != 200:
        return None, (st, str(b)[:120])
    cs = []
    for c in b.get("candlesticks") or []:
        cs.append({"e": c["end_period_ts"],
                   "yb": c["yes_bid"].get("close_dollars"), "ya": c["yes_ask"].get("close_dollars"),
                   "ybh": c["yes_bid"].get("high_dollars"), "ybl": c["yes_bid"].get("low_dollars"),
                   "v": c.get("volume_fp"), "oi": c.get("open_interest_fp")})
    return {"ticker": t, "close": close, "result": m["result"], "c": cs}, None


def load_cache(refetch):
    rows = {}
    if refetch:
        return rows
    os.makedirs(CACHE_DIR, exist_ok=True)
    srcs = [CACHE] if os.path.exists(CACHE) else [f for f in SEEDS if os.path.exists(f)]
    for f in srcs:
        for line in open(f, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            rows.setdefault(r["ticker"], r)
    if srcs and srcs != [CACHE]:
        with open(CACHE, "w", encoding="utf-8") as fh:
            for r in rows.values():
                fh.write(json.dumps(r) + "\n")
        print("cache seeded from the 10-02 sweep files:", len(rows), "markets")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--refetch", action="store_true", help="ignore the candle cache; one GET a market")
    ap.add_argument("--verify", type=int, default=0, help="re-fetch N random cached markets and assert equal")
    a = ap.parse_args()
    selftest()
    if a.selftest:
        return
    import kauth
    t0 = time.time()
    ms = pull_settled(kauth)
    ms = [m for m in ms if m.get("result") in ("yes", "no")]
    dates = sorted({dt.datetime.strptime(m["ticker"].split("-")[1], "%y%b%d").date() for m in ms})
    print("settled KXRAIN markets", len(ms), "dates", len(dates), "first", dates[0] if dates else None,
          "last", dates[-1] if dates else None, "(%.0f s)" % (time.time() - t0))
    rows = load_cache(a.refetch)
    todo = [m for m in ms if m["ticker"] not in rows]
    print("cached", len(rows), "to fetch", len(todo), flush=True)
    errs = []
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE, "a" if not a.refetch else "w", encoding="utf-8") as fh:
        for i, m in enumerate(todo):
            r, err = fetch_candles(kauth, m)
            if err:
                errs.append((m["ticker"], err))
                time.sleep(1.0)
                if len(errs) > 10:
                    print("too many HTTP errors, stopping:", errs[-3:])
                    break
                continue
            rows[r["ticker"]] = r
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            if (i + 1) % 100 == 0:
                print("fetched", i + 1, flush=True)
            time.sleep(0.15)
    if errs:
        print("fetch errors:", len(errs), errs[:5])
    if a.verify:
        pick = random.sample([m for m in ms if m["ticker"] in rows and m not in todo], min(a.verify, len(rows)))
        bad = 0
        for m in pick:
            r, err = fetch_candles(kauth, m)
            if err or r["c"] != rows[m["ticker"]]["c"] or r["result"] != rows[m["ticker"]]["result"]:
                bad += 1
                print("VERIFY MISMATCH", m["ticker"], err or "candles differ")
            time.sleep(0.15)
        print("verify: %d of %d cached markets re-fetched equal" % (len(pick) - bad, len(pick)))
    data = [rows[m["ticker"]] for m in ms if m["ticker"] in rows]
    print("markets measured", len(data), "with candles", sum(1 for r in data if r["c"]),
          "dates", len({date_of(r) for r in data}), "(%.0f s)" % (time.time() - t0))
    res = run(data, label="ALL settled KXRAIN markets, decide at close-22h")
    by_month = collections.defaultdict(list)
    for r in data:
        by_month[date_of(r).strftime("%Y-%m")].append(r)
    for k in sorted(by_month):
        run(by_month[k], label="month %s (%d markets)" % (k, len(by_month[k])))
    ok, lines = verdict(res)
    print()
    for ln in lines:
        print(ln)
    print("BAR", "PASS" if ok else "FAIL", "(pre-registered 2026-10-02: 400+ markets at 3-10c, losses <= 2.5 per 100,"
          " net >= +1.5c at the 25-lot fill, 15+ Oct/Nov dates)")


if __name__ == "__main__":
    main()
