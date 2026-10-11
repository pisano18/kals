#!/usr/bin/env python3
"""loss_anatomy.py -- what did the RAW recordings look like around every market
the live bot lost real money on, and does anything available at decision time
separate those markets from the ones it won?

Sources, in the project's order of trust: (1) the raw settlement-index feed
(kalshi_data/cfbenchmarks_value), (2) the raw trade tape and order book
(kalshi_data/trade, orderbook_snapshot + orderbook_delta), the constituent
exchange books (feed_data/*), (3) our own live fills (results/pinrun-live-*.jsonl
joined to results/kalshi_ledger.json). No replay, no pinsim, no load_quotes.

This is index-feed and tape evidence about WHAT HAPPENED around our OWN fills.
It is not, and must never be quoted as, a loss rate from the tape.

Stages (each writes under OUT and can be re-run alone):
    --selftest            planted worlds for every estimator below
    --build               losers + stratified controls      -> markets.json
    --measure             raw windows per market             -> raw/<ticker>.json
    --book [--book-all]   order book at the send (losers, or all) -> raw/<ticker>.book.json
    --report              features, classes, tables -> loss_anatomy.jsonl / .md

Read-only on the tape: every file is opened with gzip.open(..., 'rt') and
streamed line by line; nothing under kalshi_data or feed_data is written.
"""
import argparse
import gzip
import json
import math
import os
import random
import re
import statistics
import sys
import time
import zlib
from collections import defaultdict
from datetime import datetime, timezone, timedelta

OUT = r"C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\final"
REPO = r"C:\kals-repo"
DATA = r"C:\kals\kalshi_data"
FEED = r"C:\kals\feed_data"
sys.path.insert(0, os.path.join(REPO, "research"))
from engine import var_factor, N_AVG                  # noqa: E402  (stdlib-only module)

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI", "KXBNB15M": "BNBUSD_RTI",
    "KXBCH15M": "BCHUSD_RTI", "KXZEC15M": "ZECUSD_RTI", "KXHYPE15M": "HYPEUSD_RTI",
    "KXNEAR15M": "NEARUSD_RTI", "KXADA15M": "ADAUSD_RTI", "KXTON15M": "TONUSD_RTI",
}
FEED_COINS = {"BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "BCH", "LTC"}
DIGITS2 = {"KXBTC15M", "KXETH15M", "KXBNB15M"}          # pinrun: 2 for BTC/ETH/BNB, 4 for the rest
TICK = re.compile(r"^KX(BTC|ETH|SOL|XRP|DOGE|BNB|BCH|ZEC|HYPE|NEAR|ADA|TON)15M-(\d\d)([A-Z]{3})(\d\d)(\d\d)(\d\d)-(\d\d)$")
MON = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
       "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}
SIGMA_WIN = 300
MIN_DIFFS = 20
START_UTC = datetime(2026, 9, 8, tzinfo=timezone.utc).timestamp()   # live since 2026-09-08
ET = timezone(timedelta(hours=-4))                                   # EDT, valid for every date here
N_CONTROLS = 120
SEED = 11
TAU_BUCKETS = [(0, 10), (11, 20), (21, 30), (31, 45), (46, 10 ** 6)]
PRICE_BUCKETS = [(0.0, 0.90), (0.90, 0.95), (0.95, 0.98), (0.98, 1.01)]


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def parse_iso(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def et_str(ts):
    return datetime.fromtimestamp(ts, ET).strftime("%m-%d %H:%M:%S")


def hour_key(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y%m%dT%H")


def hours_between(lo, hi):
    out = []
    h = int(lo // 3600) * 3600
    while h <= hi:
        out.append(hour_key(h))
        h += 3600
    return out


def parse_ticker(tk):
    m = TICK.match(tk)
    if not m:
        return None
    coin, yy, mon, dd, hh, mm, _ = m.groups()
    dt = datetime(2000 + int(yy), MON[mon], int(dd), int(hh), int(mm), tzinfo=timezone.utc)
    assert dt < datetime(2026, 11, 1, tzinfo=timezone.utc), "EDT offset only valid before 2026-11-01"
    return {"coin": coin, "series": "KX%s15M" % coin, "close_s": int(dt.timestamp()) + 4 * 3600}


def gz_lines(path, stats):
    """Stream a gzip file line by line. A torn file (collector killed mid-write,
    or a second member appended behind an untrailered first one) yields what
    precedes the tear and is recorded in stats['torn']; nothing is filled."""
    if not os.path.exists(path):
        stats["missing"].append(path)
        return
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                yield line
    except (EOFError, OSError, gzip.BadGzipFile, zlib.error) as e:
        stats["torn"].append((path, repr(e)[:80]))


def sigma_at(series, t):
    """pinrun.IndexWS.sigma's arithmetic (as copied in pincalib.sigma_at):
    sample sd of 1-second changes over the trailing 300 s ending at t."""
    secs = [s for s in range(t - SIGMA_WIN + 1, t + 1) if s in series]
    if len(secs) < 30:
        return None
    diffs = [series[secs[i]] - series[secs[i - 1]]
             for i in range(1, len(secs)) if secs[i] - secs[i - 1] == 1]
    if len(diffs) < MIN_DIFFS:
        return None
    mu = sum(diffs) / len(diffs)
    return math.sqrt(sum((x - mu) ** 2 for x in diffs) / (len(diffs) - 1))


def fisher_one_sided(a, n1, b, n2):
    """P(X >= a) for X ~ Hypergeom(total n1+n2, flagged a+b, draws n1):
    the chance losers would carry at least `a` flags if flags were spread
    at random across losers and controls."""
    K = a + b
    N = n1 + n2
    denom = math.comb(N, n1)
    p = 0.0
    for x in range(a, min(K, n1) + 1):
        if K - x > n2:
            continue
        p += math.comb(K, x) * math.comb(N - K, n1 - x) / denom
    return min(1.0, p)


def quantile(vals, q):
    v = sorted(vals)
    if not v:
        return None
    k = max(0, min(len(v) - 1, int(math.ceil(q * len(v))) - 1))
    return v[k]


# ---------------------------------------------------------------------------
# STAGE A -- the market list
# ---------------------------------------------------------------------------
def load_ledger():
    d = json.load(open(os.path.join(REPO, "results", "kalshi_ledger.json"), encoding="utf-8"))
    per = {}
    for v in d["settlements"].values():
        tk = v["ticker"]
        pnl = (v["revenue"] / 100.0 + min(float(v["yes_count_fp"]), float(v["no_count_fp"]))
               - float(v["yes_total_cost_dollars"]) - float(v["no_total_cost_dollars"])
               - float(v["fee_cost"]))
        r = per.setdefault(tk, {"pnl": 0.0, "yes_n": 0.0, "no_n": 0.0, "yes_cost": 0.0,
                                "no_cost": 0.0, "fee": 0.0, "result": v["market_result"],
                                "settled_time": v["settled_time"], "rows": 0})
        r["pnl"] += pnl
        r["yes_n"] += float(v["yes_count_fp"])
        r["no_n"] += float(v["no_count_fp"])
        r["yes_cost"] += float(v["yes_total_cost_dollars"])
        r["no_cost"] += float(v["no_total_cost_dollars"])
        r["fee"] += float(v["fee_cost"])
        r["rows"] += 1
    return per


def load_live_logs():
    import glob
    orders, signals, hedges = defaultdict(list), defaultdict(list), defaultdict(list)
    for f in sorted(glob.glob(os.path.join(REPO, "results", "pinrun-live-*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            if '"kind": "order"' not in line and '"kind": "signal"' not in line \
                    and '"kind": "hedge"' not in line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            k = r.get("kind")
            tk = r.get("ticker")
            if not tk or not TICK.match(tk):
                continue
            if k == "order":
                orders[tk].append(r)
            elif k == "signal":
                signals[tk].append(r)
            elif k == "hedge":
                hedges[tk].append(r)
    return orders, signals, hedges


def t_send_of(o, close_s, tau):
    if o.get("t_ms_send"):
        return o["t_ms_send"] / 1000.0, "ms"
    # before 09-22 t_ms_send was not logged, but the client_order_id is "pin-<local ms>-<hex>"
    # (checked against t_ms_send where both exist: equal to within 1 ms)
    cid = o.get("client_order_id") or (o.get("body") or {}).get("client_order_id") or ""
    mm = re.match(r"^pin-(\d{13})-", cid)
    t0 = parse_iso(o["t"])
    if mm:
        tms = int(mm.group(1)) / 1000.0
        if abs(tms - t0) < 5.0:
            return tms, "ms(cid)"
    if tau is None:
        return t0 + 0.5, "sec?"
    lo, hi = max(t0, close_s - tau), min(t0 + 1, close_s - tau + 1)
    if lo < hi:
        return (lo + hi) / 2.0, "sec"
    return t0 + 0.5, "sec?"


def build_market(tk, led, orders, signals, hedges):
    info = parse_ticker(tk)
    fills = [o for o in orders if (o.get("filled") or 0) > 0]
    if not fills:
        return None
    fills.sort(key=lambda o: (o["t"], o.get("t_ms_send") or 0))
    o = fills[0]
    # before 2026-09-20 the order record has no `want`; the body's side says it
    # (a YES buy is a bid at the yes price, a NO buy is an ask at the yes price)
    want = o.get("want") or ("yes" if (o.get("body") or {}).get("side") == "bid" else "no")
    sigs = [s for s in signals if s.get("want") == want and s["t"] <= o["t"]]
    sig = sigs[-1] if sigs else {}
    tau = o.get("tau_at_send", sig.get("tau"))
    t_send, prec = t_send_of(o, info["close_s"], tau)
    digits = sig.get("digits")
    if digits is None:
        digits = 2 if info["series"] in DIGITS2 else 4
    ladder = sig.get("ladder") or []
    m = {
        "ticker": tk, "coin": info["coin"], "series": info["series"],
        "iid": SERIES_TO_INDEX.get(info["series"]), "close_s": info["close_s"],
        "want": want, "pnl": round(led["pnl"], 4), "result": led["result"],
        "yes_n": led["yes_n"], "no_n": led["no_n"], "hedged": led["yes_n"] > 0 and led["no_n"] > 0,
        "t_send": t_send, "t_send_prec": prec, "tau": tau,
        "price": o.get("exec_price") or o.get("ask_seen") or sig.get("price"),
        "ask_seen": o.get("ask_seen"), "limit_sent": o.get("limit_sent"),
        "filled": o.get("filled"), "leg": o.get("leg"),
        "n_fills": len(fills), "fills": [[f.get("tau_at_send"), f.get("exec_price"), f.get("filled")] for f in fills],
        "bot": {
            "fair": sig.get("fair"), "strike": sig.get("strike"), "spot": sig.get("spot"),
            "sigma": sig.get("sigma"), "digits": digits, "sig_tau": sig.get("tau"),
            "index_age_s": o.get("index_age_s", sig.get("index_age_s")),
            "book_age_ms": o.get("book_age_ms"), "level_age_ms": sig.get("level_age_ms"),
            "level_age_exact": sig.get("level_age_exact"),
            "sell_share_3s": o.get("sell_share_3s", sig.get("sell_share_3s")),
            "taker_n_3s": o.get("taker_n_3s", sig.get("taker_n_3s")),
            "trade_age_s": o.get("trade_age_s", sig.get("trade_age_s")),
            "size_at_best": (ladder[0][1] if ladder else sig.get("size")),
            "ladder_under": sig.get("ladder_under"), "ladder_levels": sig.get("ladder_levels"),
            "edge_c": sig.get("edge_c"), "take_n": sig.get("take_n"),
            "cond_x": sig.get("cond_x"), "widened": sig.get("widened"),
        },
        "hedges": [{"t": h.get("t"), "price": h.get("price"), "n": h.get("n"), "tau": h.get("tau"),
                    "belief": h.get("belief"), "status": h.get("status")} for h in hedges],
    }
    return m


def tau_bucket(tau):
    for i, (lo, hi) in enumerate(TAU_BUCKETS):
        if tau is not None and lo <= tau <= hi:
            return i
    return len(TAU_BUCKETS) - 1


def price_bucket(p):
    for i, (lo, hi) in enumerate(PRICE_BUCKETS):
        if p is not None and lo <= p < hi:
            return i
    return len(PRICE_BUCKETS) - 1


def stratified_sample(losers, winners, n, seed):
    """Sample `n` winners so that their (tau bucket, price bucket) mix matches
    the losers'. Largest-remainder allocation; a short cell spills into the
    same price bucket, then anywhere. Deterministic in `seed`."""
    rng = random.Random(seed)
    cells = defaultdict(int)
    for m in losers:
        cells[(tau_bucket(m["tau"]), price_bucket(m["price"]))] += 1
    total = sum(cells.values())
    raw = {c: n * k / total for c, k in cells.items()}
    alloc = {c: int(math.floor(v)) for c, v in raw.items()}
    rem = n - sum(alloc.values())
    for c in sorted(raw, key=lambda c: -(raw[c] - alloc[c]))[:rem]:
        alloc[c] += 1
    pool = defaultdict(list)
    for m in winners:
        pool[(tau_bucket(m["tau"]), price_bucket(m["price"]))].append(m)
    for v in pool.values():
        rng.shuffle(v)
    chosen, short = [], 0
    for c, k in alloc.items():
        got = pool[c][:k]
        del pool[c][:k]
        short += k - len(got)
        chosen.extend(got)
    # spill
    while short > 0:
        cands = [c for c in pool if pool[c]]
        if not cands:
            break
        c = rng.choice(cands)
        chosen.append(pool[c].pop())
        short -= 1
    return chosen, {str(c): k for c, k in alloc.items()}


def build():
    led = load_ledger()
    orders, signals, hedges = load_live_logs()
    losers, winners, skipped = [], [], defaultdict(int)
    for tk, r in led.items():
        info = parse_ticker(tk)
        if not info:
            skipped["not_crypto15M"] += 1
            continue
        if info["close_s"] < START_UTC:
            skipped["before_0908"] += 1
            continue
        m = build_market(tk, r, orders.get(tk, []), signals.get(tk, []), hedges.get(tk, []))
        if m is None:
            skipped["no_live_fill"] += 1
            continue
        if m["pnl"] < 0:
            losers.append(m)
        elif m["pnl"] > 0:
            winners.append(m)
        else:
            skipped["zero_pnl"] += 1
    losers.sort(key=lambda m: m["pnl"])
    controls, alloc = stratified_sample(losers, winners, N_CONTROLS, SEED)
    for m in losers:
        m["group"] = "loser"
    for m in controls:
        m["group"] = "control"
    excluded = []
    for tk, r in led.items():
        info = parse_ticker(tk)
        if info and r["pnl"] < 0 and not any(m["ticker"] == tk for m in losers):
            why = "before 09-08" if info["close_s"] < START_UTC else "no pinrun-live fill"
            excluded.append("%s %.2f (%s)" % (tk, r["pnl"], why))
    meta = {"excluded_losers": excluded,
            "n_losers": len(losers), "n_winners_pool": len(winners), "n_controls": len(controls),
            "losers_dollars": round(sum(m["pnl"] for m in losers), 2),
            "winners_pool_dollars": round(sum(m["pnl"] for m in winners), 2),
            "skipped": dict(skipped), "alloc": alloc, "seed": SEED,
            "tau_buckets": TAU_BUCKETS, "price_buckets": PRICE_BUCKETS}
    json.dump({"meta": meta, "losers": losers, "controls": controls},
              open(os.path.join(OUT, "markets.json"), "w", encoding="utf-8"), indent=1)
    # the whole live-filled population, for the price/tau bucket counts the stratified controls cannot show
    pool = []
    for m in losers + winners:
        q = dict(m)
        q["group"] = "pool"
        q["conf"] = (m["bot"]["fair"] if m["want"] == "yes" else (1.0 - m["bot"]["fair"])) if m["bot"]["fair"] is not None else None
        pool.append(q)
    json.dump(pool, open(os.path.join(OUT, "pool.json"), "w", encoding="utf-8"))
    print("BUILD:", json.dumps(meta))
    for m in losers:
        print("  %-26s %s %8.2f %s tau=%s price=%s fair=%s hedged=%s fills=%d" % (
            m["ticker"], et_str(m["close_s"]), m["pnl"], m["want"], m["tau"], m["price"],
            m["bot"]["fair"], m["hedged"], m["n_fills"]))


# ---------------------------------------------------------------------------
# STAGE B -- raw windows per market
# ---------------------------------------------------------------------------
def windows_of(m):
    c, ts = m["close_s"], m["t_send"]
    if m.get("group") == "pool":        # the whole population: only what the send-time rules need
        return {"idx": (c - 420, c + 1), "trade": (ts - 10, ts + 0.5), "feed": (ts - 4, ts + 0.5)}
    return {"idx": (c - 420, c + 1), "trade": (ts - 60, c + 1), "feed": (ts - 12, c + 1)}


def measure(markets, only=None, rawdir=None):
    stats = {"missing": [], "torn": []}
    rawdir = rawdir or os.path.join(OUT, "raw")
    os.makedirs(rawdir, exist_ok=True)
    todo = [m for m in markets if only is None or m["ticker"] in only]
    todo = [m for m in todo if not os.path.exists(os.path.join(rawdir, m["ticker"] + ".json"))]
    print("MEASURE: %d markets to do" % len(todo), flush=True)
    acc = {m["ticker"]: {"idx": {}, "btc": {}, "rx_lat": {}, "avg60": None, "trades": [],
                         "feeds": defaultdict(list), "replica": []} for m in todo}
    by = {m["ticker"]: m for m in todo}
    # ---- index ------------------------------------------------------------
    groups = defaultdict(list)
    for m in todo:
        lo, hi = windows_of(m)["idx"]
        for h in hours_between(lo, hi):
            groups[h].append(m["ticker"])
    t0 = time.time()
    for n, h in enumerate(sorted(groups)):
        want_iids = set()
        for tk in groups[h]:
            want_iids.add(by[tk]["iid"])
            want_iids.add("BRTI")
        path = os.path.join(DATA, "cfbenchmarks_value", h + ".jsonl.gz")
        for line in gz_lines(path, stats):
            i = line.find('"index_id":"')
            if i < 0:
                continue
            iid = line[i + 12:line.find('"', i + 12)]
            if iid not in want_iids:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            d = r.get("msg") or {}
            inner = d.get("data")
            if isinstance(inner, str):
                try:
                    inner = json.loads(inner)
                except ValueError:
                    continue
            try:
                tms = float(inner["time"])
                sec = int(round(tms / 1000.0))
                v = float(inner["value"])
            except (KeyError, TypeError, ValueError):
                continue
            rx = r.get("_rx_ms")
            for tk in groups[h]:
                m = by[tk]
                lo, hi = windows_of(m)["idx"]
                if not (lo <= sec <= hi):
                    continue
                a = acc[tk]
                if iid == m["iid"]:
                    a["idx"][sec] = v
                    if abs(sec - m["t_send"]) <= 12 and rx:
                        a["rx_lat"][sec] = round(rx / 1000.0 - tms / 1000.0, 3)
                    if sec == m["close_s"]:
                        a60 = (d.get("avg_60s_data") or {}).get("value")
                        a["avg60"] = float(a60) if a60 is not None else None
                if iid == "BRTI":
                    a["btc"][sec] = v
        print("  idx %s (%d/%d) %.0fs" % (h, n + 1, len(groups), time.time() - t0), flush=True)
    # ---- trades -----------------------------------------------------------
    groups = defaultdict(list)
    for m in todo:
        lo, hi = windows_of(m)["trade"]
        for h in hours_between(lo, hi):
            groups[h].append(m["ticker"])
    for n, h in enumerate(sorted(groups)):
        tks = set(groups[h])
        path = os.path.join(DATA, "trade", h + ".jsonl.gz")
        for line in gz_lines(path, stats):
            i = line.find('"market_ticker":"')
            if i < 0:
                continue
            tk = line[i + 17:line.find('"', i + 17)]
            if tk not in tks:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            d = r["msg"]
            t = d.get("ts_ms", 0) / 1000.0
            lo, hi = windows_of(by[tk])["trade"]
            if not (lo <= t <= hi):
                continue
            acc[tk]["trades"].append([round(t, 3), d.get("taker_side"), float(d.get("count_fp", 0)),
                                      float(d.get("yes_price_dollars", 0)), round((r.get("_rx_ms") or 0) / 1000.0, 3)])
        print("  trade %s (%d/%d) %.0fs" % (h, n + 1, len(groups), time.time() - t0), flush=True)
    # ---- constituent feeds -------------------------------------------------
    groups = defaultdict(list)
    for m in todo:
        if m["coin"] not in FEED_COINS:
            continue
        lo, hi = windows_of(m)["feed"]
        for h in hours_between(lo, hi):
            groups[h].append(m["ticker"])
    for n, h in enumerate(sorted(groups)):
        coins = {by[tk]["coin"] for tk in groups[h]}
        tks_by_coin = defaultdict(list)
        for tk in groups[h]:
            tks_by_coin[by[tk]["coin"]].append(tk)

        def keep(coin, ex, t, bid, ask, rx):
            for tk in tks_by_coin[coin]:
                lo, hi = windows_of(by[tk])["feed"]
                if lo <= t <= hi:
                    acc[tk]["feeds"][ex].append([round(t, 3), bid, ask, round(rx or 0, 3)])
        # bitstamp
        tags = {("order_book_%susd" % c.lower()): c for c in coins}
        for line in gz_lines(os.path.join(FEED, "bitstamp", h + ".jsonl.gz"), stats):
            i = line.find('"channel":"')
            if i < 0:
                continue
            ch = line[i + 11:line.find('"', i + 11)]
            coin = tags.get(ch)
            if not coin:
                continue
            try:
                r = json.loads(line)
                d = r["data"]
                t = float(d["microtimestamp"]) / 1e6
                keep(coin, "bitstamp", t, float(d["bids"][0][0]), float(d["asks"][0][0]), r.get("_rx"))
            except (KeyError, IndexError, ValueError, TypeError):
                continue
        # coinbase
        tags = {('"product_id":"%s-USD"' % c): c for c in coins}
        for line in gz_lines(os.path.join(FEED, "coinbase", h + ".jsonl.gz"), stats):
            coin = None
            for tag, c in tags.items():
                if tag in line:
                    coin = c
                    break
            if not coin or '"best_bid"' not in line:
                continue
            try:
                r = json.loads(line)
                t = parse_iso(r["time"])
                keep(coin, "coinbase", t, float(r["best_bid"]), float(r["best_ask"]), r.get("_rx"))
            except (KeyError, ValueError, TypeError):
                continue
        # kraken
        tags = {('"symbol":"%s/USD"' % c): c for c in coins}
        for line in gz_lines(os.path.join(FEED, "kraken", h + ".jsonl.gz"), stats):
            coin = None
            for tag, c in tags.items():
                if tag in line:
                    coin = c
                    break
            if not coin:
                continue
            try:
                r = json.loads(line)
                for d in r.get("data", []):
                    if d.get("symbol") != "%s/USD" % coin:
                        continue
                    t = parse_iso(d["timestamp"])
                    keep(coin, "kraken", t, float(d["bid"]), float(d["ask"]), r.get("_rx"))
            except (KeyError, ValueError, TypeError):
                continue
        # gemini (BTC only): top-of-book changes
        if "BTC" in coins:
            top = {"bid": None, "ask": None}
            for line in gz_lines(os.path.join(FEED, "gemini", h + ".jsonl.gz"), stats):
                if "top-of-book" not in line:
                    continue
                try:
                    r = json.loads(line)
                    t = float(r["timestampms"]) / 1000.0
                    for ev in r.get("events", []):
                        if ev.get("reason") != "top-of-book" or float(ev.get("remaining", 0)) <= 0:
                            continue
                        top[ev["side"]] = float(ev["price"])
                    if top["bid"] and top["ask"] and top["bid"] < top["ask"]:
                        keep("BTC", "gemini", t, top["bid"], top["ask"], r.get("_rx"))
                except (KeyError, ValueError, TypeError):
                    continue
        # index_replica (per-second per-exchange summary written by crypto_feeds)
        for line in gz_lines(os.path.join(FEED, "index_replica", h + ".jsonl.gz"), stats):
            try:
                r = json.loads(line)
                sec = int(r["sec"])
            except (KeyError, ValueError, TypeError):
                continue
            for coin in coins:
                row = r.get(coin)
                if not row:
                    continue
                for tk in tks_by_coin[coin]:
                    lo, hi = windows_of(by[tk])["feed"]
                    if lo <= sec <= hi:
                        acc[tk]["replica"].append({"sec": sec, "wmid": row.get("wmid"),
                                                   "median_mid": row.get("median_mid"),
                                                   "per_ex": row.get("per_ex")})
        print("  feed %s (%d/%d) %.0fs" % (h, n + 1, len(groups), time.time() - t0), flush=True)
    # ---- write --------------------------------------------------------------
    for tk, a in acc.items():
        a["trades"].sort()
        for ex in a["feeds"]:
            a["feeds"][ex].sort()
        a["feeds"] = dict(a["feeds"])
        a["idx"] = {str(k): v for k, v in a["idx"].items()}
        a["btc"] = {str(k): v for k, v in a["btc"].items()}
        a["rx_lat"] = {str(k): v for k, v in a["rx_lat"].items()}
        json.dump(a, open(os.path.join(rawdir, tk + ".json"), "w", encoding="utf-8"))
    json.dump(stats, open(os.path.join(OUT, os.path.basename(rawdir) + "_measure_stats.json"), "w", encoding="utf-8"), indent=1)
    print("MEASURE done: missing files %d, torn files %d, %.0fs" % (
        len(stats["missing"]), len(stats["torn"]), time.time() - t0), flush=True)


# ---------------------------------------------------------------------------
# STAGE B2 -- the order book at the send (snapshot + deltas, one ticker at a time)
# ---------------------------------------------------------------------------
def apply_book(book, side, price, delta, ts, ms):
    lv = book[side].get(price)
    if lv is None:
        lv = book[side][price] = {"q": 0.0, "created": None, "changed": None, "from_snap": False}
    before = lv["q"]
    lv["q"] = before + delta
    lv["changed"] = ts
    if before <= 1e-9 and lv["q"] > 1e-9:
        lv["created"] = ts
        lv["from_snap"] = False
    if lv["q"] < -1e-6:
        ms["negative"] += 1


def book_metrics(book, want, t_send, ask_seen, snap_ts):
    """Offer side for `want`: yes-buyers hit NO bids (yes ask = 1 - no bid)."""
    side = "no" if want == "yes" else "yes"
    lv = [(round(1.0 - float(p), 4), p, d) for p, d in book[side].items() if d["q"] > 1e-6]
    if not lv:
        return {"best_ask": None}
    lv.sort()
    best_ask, _, d = lv[0]
    out = {"best_ask": best_ask, "best_qty": round(d["q"], 2),
           "best_from_snap": d["from_snap"],
           "best_created_age_s": (None if d["created"] is None else round(t_send - d["created"], 3)),
           "best_changed_age_s": (None if d["changed"] is None else round(t_send - d["changed"], 3)),
           "snap_age_s": round(t_send - snap_ts, 1) if snap_ts else None,
           "qty_within_1c": round(sum(x[2]["q"] for x in lv if x[0] <= best_ask + 0.0101), 2),
           "qty_within_3c": round(sum(x[2]["q"] for x in lv if x[0] <= best_ask + 0.0301), 2),
           "n_levels": len(lv), "ask_seen_bot": ask_seen,
           "match_bot": (ask_seen is not None and abs(best_ask - ask_seen) < 0.0005)}
    if ask_seen is not None:
        hit = [x for x in lv if abs(x[0] - ask_seen) < 0.0005]
        if hit:
            dd = hit[0][2]
            out["seen_level_qty"] = round(dd["q"], 2)
            out["seen_level_created_age_s"] = (None if dd["created"] is None else round(t_send - dd["created"], 3))
            out["seen_level_from_snap"] = dd["from_snap"]
    return out


def book_stage(markets, only=None):
    stats = {"missing": [], "torn": []}
    rawdir = os.path.join(OUT, "raw")
    todo = [m for m in markets if only is None or m["ticker"] in only]
    todo = [m for m in todo if not os.path.exists(os.path.join(rawdir, m["ticker"] + ".book.json"))]
    print("BOOK: %d markets" % len(todo), flush=True)
    t0 = time.time()
    # group by the hour of the send; each market needs hours [close-900, t_send]
    groups = defaultdict(list)
    for m in todo:
        for h in hours_between(m["close_s"] - 900, m["t_send"]):
            groups[h].append(m["ticker"])
    by = {m["ticker"]: m for m in todo}
    snaps = {}        # tk -> (seq, sending_ts, yes, no)
    state = {}        # tk -> book dict
    done = set()
    churn = {tk: {"offer_events_10s": 0, "offer_events_3s": 0, "offer_qty_added_3s": 0.0,
                  "offer_qty_removed_3s": 0.0, "negative": 0, "n_deltas": 0} for tk in by}
    for n, h in enumerate(sorted(groups)):
        tks = set(groups[h])
        # snapshots first
        for line in gz_lines(os.path.join(DATA, "orderbook_snapshot", h + ".jsonl.gz"), stats):
            i = line.find('"market_ticker":"')
            if i < 0:
                continue
            tk = line[i + 17:line.find('"', i + 17)]
            if tk not in tks or "yes_dollars_fp" not in line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            ts = (r.get("sending_ts_ms") or 0) / 1000.0
            if ts > by[tk]["t_send"]:
                continue
            seq = r.get("seq", 0)
            if tk not in snaps or seq > snaps[tk][0]:
                d = r["msg"]
                snaps[tk] = (seq, ts, d.get("yes_dollars_fp") or [], d.get("no_dollars_fp") or [])
        # (re)build the book from the latest snapshot seen for each ticker
        for tk in tks:
            if tk in snaps and state.get(tk, {}).get("_seq") != snaps[tk][0]:
                seq, ts, yes, no = snaps[tk]
                b = {"yes": {}, "no": {}, "_seq": seq, "_ts": ts}
                for p, q in yes:
                    b["yes"][p] = {"q": float(q), "created": None, "changed": ts, "from_snap": True}
                for p, q in no:
                    b["no"][p] = {"q": float(q), "created": None, "changed": ts, "from_snap": True}
                state[tk] = b
        # deltas
        path = os.path.join(DATA, "orderbook_delta", h + ".jsonl.gz")
        for line in gz_lines(path, stats):
            i = line.find('"market_ticker":"')
            if i < 0:
                continue
            tk = line[i + 17:line.find('"', i + 17)]
            if tk not in tks or tk in done or tk not in state:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            b = state[tk]
            if r.get("seq", 0) <= b["_seq"]:
                continue
            d = r["msg"]
            ts = d.get("ts_ms", 0) / 1000.0
            m = by[tk]
            if ts > m["t_send"]:
                done.add(tk)
                continue
            side, price, delta = d["side"], d["price_dollars"], float(d["delta_fp"])
            ms = churn[tk]
            ms["n_deltas"] += 1
            apply_book(b, side, price, delta, ts, ms)
            offer_side = "no" if m["want"] == "yes" else "yes"
            if side == offer_side:
                if ts >= m["t_send"] - 10:
                    ms["offer_events_10s"] += 1
                if ts >= m["t_send"] - 3:
                    ms["offer_events_3s"] += 1
                    if delta > 0:
                        ms["offer_qty_added_3s"] += delta
                    else:
                        ms["offer_qty_removed_3s"] -= delta
            if tk in done:
                pass
        print("  book %s (%d/%d) %.0fs" % (h, n + 1, len(groups), time.time() - t0), flush=True)
    for tk, m in by.items():
        b = state.get(tk)
        if b is None:
            out = {"best_ask": None, "why": "no snapshot found before the send"}
        else:
            out = book_metrics(b, m["want"], m["t_send"], m.get("ask_seen"), b["_ts"])
            out["snapshot_seq"] = b["_seq"]
        out.update(churn[tk])
        for k in ("offer_qty_added_3s", "offer_qty_removed_3s"):
            out[k] = round(out[k], 2)
        json.dump(out, open(os.path.join(rawdir, tk + ".book.json"), "w", encoding="utf-8"))
    json.dump(stats, open(os.path.join(OUT, "book_stats.json"), "w", encoding="utf-8"), indent=1)
    print("BOOK done %.0fs; missing %d torn %d" % (time.time() - t0, len(stats["missing"]), len(stats["torn"])), flush=True)


# ---------------------------------------------------------------------------
# STAGE C -- features, classes, tables
# ---------------------------------------------------------------------------
def crossing_times(path_fn, secs, win_side):
    """path_fn(s) -> value-or-None, compared to the winning side via win_side(v) -> bool.
    Returns (last_cross_to_losing, first_losing, ever_winning, ever_losing)."""
    last_cross = None
    first_losing = None
    prev = None
    ever_w = ever_l = False
    for s in secs:
        v = path_fn(s)
        if v is None:
            continue
        w = win_side(v)
        ever_w |= w
        ever_l |= (not w)
        if not w and first_losing is None:
            first_losing = s
        if prev is True and not w:
            last_cross = s
        prev = w
    return last_cross, first_losing, ever_w, ever_l


def index_features(m, raw):
    idx = {int(k): v for k, v in raw["idx"].items()}
    btc = {int(k): v for k, v in raw["btc"].items()}
    close, ts = m["close_s"], m["t_send"]
    s0 = int(math.floor(ts))
    sign = 1.0 if m["want"] == "yes" else -1.0
    bot = m["bot"]
    K = bot["strike"]
    d = bot["digits"]
    f = {}
    if K is None:
        return {"error": "no strike in the bot's signal"}
    Keff = K - 0.5 * 10.0 ** (-d)
    sig_bot = bot["sigma"]
    sig_tape = sigma_at(idx, s0)
    sigma = sig_bot or sig_tape
    f["sigma_bot"] = sig_bot
    f["sigma_tape_5min"] = sig_tape
    f["sigma_ratio"] = (sig_tape / sig_bot) if (sig_bot and sig_tape) else None
    # prints around the send
    have = sorted(s for s in idx if s <= s0)
    if not have:
        return {"error": "no index print at or before the send"}
    s_spot = have[-1]
    spot = idx[s_spot]
    f["spot_tape"] = spot
    f["spot_tape_age_s"] = round(ts - s_spot, 3)
    f["spot_bot"] = bot["spot"]
    f["spot_bot_minus_tape_sigma"] = (round(sign * (bot["spot"] - spot) / sigma, 3) if (bot["spot"] and sigma) else None)
    held = "unknown"
    if bot.get("spot") is not None:
        for lab, sec in (("s0", s0), ("s0-1", s0 - 1), ("s0-2", s0 - 2)):
            if sec in idx and abs(idx[sec] - bot["spot"]) <= 1e-6 * max(1.0, abs(bot["spot"])):
                held = lab
                break
        else:
            held = "other"
    f["bot_held_print"] = held          # which tape print the bot's logged spot equals
    gaps = [s for s in range(s0 - 5, s0 + 1) if s not in idx]
    f["missing_prints_last5s"] = len(gaps)
    lat = [v for k, v in raw["rx_lat"].items() if s0 - 5 <= int(k) <= s0]
    f["collector_lat_max_s"] = max(lat) if lat else None
    f["n_prints_window"] = sum(1 for s in range(close - 420, close) if s in idx)
    # locked split, pinrun CORRECTION 3 (missing seconds are still to come)
    lo, hi = close - 60, min(s0, close - 1)
    present = [idx[s] for s in range(lo, hi + 1) if s in idx] if hi >= lo else []
    r = 60 - len(present)
    mu = (sum(present) + r * spot) / 60.0
    sd = sigma * math.sqrt(var_factor(r, [1.0])) if r > 0 else 0.0
    f["locked_n"] = len(present)
    f["locked_mean"] = (sum(present) / len(present)) if present else None
    f["locked_mean_on_our_side"] = (sign * (f["locked_mean"] - Keff) > 0) if present else None
    f["mu_tape"] = mu
    f["z_tape"] = (round(sign * (mu - Keff) / sd, 3) if sd > 0 else (99.0 if sign * (mu - Keff) > 0 else -99.0))
    f["fair_tape"] = round(norm_cdf(f["z_tape"]), 6)
    f["fair_bot"] = bot["fair"]
    f["dist_spot_sigma"] = round(sign * (spot - Keff) / sigma, 3) if sigma else None
    f["dist_spot_bp"] = round(sign * (spot - Keff) / K * 1e4, 3)
    for k in (1, 3, 5, 10):
        a, b = idx.get(s0), idx.get(s0 - k)
        f["idx_move_against_%ds" % k] = (round(-sign * (a - b) / sigma, 3) if (a is not None and b is not None and sigma) else None)
    # BTC flag for the alts (the verifier's shape: BTC's 1-s moves in the seconds before the send)
    if m["coin"] != "BTC" and btc:
        sb = sigma_at(btc, s0)
        if sb:
            pre = [(-sign * (btc[j] - btc[j - 1]) / sb) for j in (s0 - 3, s0 - 2, s0 - 1) if j in btc and j - 1 in btc]
            inc = pre + ([(-sign * (btc[s0] - btc[s0 - 1]) / sb)] if (s0 in btc and s0 - 1 in btc) else [])
            f["btc_move_against_pre_sd"] = round(max(pre), 3) if pre else None
            f["btc_move_against_incl_sd"] = round(max(inc), 3) if inc else None
    # settlement
    w = [idx.get(s) for s in range(close - 60, close)]
    got = [v for v in w if v is not None]
    f["settle_n_prints"] = len(got)
    settle = sum(got) / len(got) if got else None
    f["settle"] = settle
    f["settle_rounded"] = round(settle, d) if settle is not None else None
    f["avg60_feed"] = raw.get("avg60")
    f["settle_vs_feed_avg"] = (round(settle - raw["avg60"], 6) if (settle is not None and raw.get("avg60") is not None) else None)
    f["result_tape"] = (None if settle is None else ("yes" if round(settle, d) >= K else "no"))
    f["result_ledger"] = m["result"]
    f["settle_minus_K"] = (settle - K) if settle is not None else None
    f["settle_minus_K_bp"] = round(sign * (settle - Keff) / K * 1e4, 3) if settle is not None else None   # toward our side
    f["settle_minus_K_sigma"] = round(sign * (settle - Keff) / sigma, 3) if (settle is not None and sigma) else None
    # thin = decided by a hair: within one rounding tick of the strike, or within a tenth of a one-second move.
    # (The spec's "0.01%" is 1 bp = 9 one-second sd on BTC, which is not thin for a model claiming 99.8%; not used.)
    f["thin"] = (settle is not None and (abs(round(settle, d) - K) <= 10.0 ** (-d) + 1e-12
                                         or (sigma and abs(settle - Keff) <= 0.1 * sigma)))
    # paths after the send
    secs = list(range(close - 60, close))
    cum = {}
    run = 0.0
    cnt = 0
    for s in secs:
        if s in idx:
            run += idx[s]
            cnt += 1
        cum[s] = (run / cnt) if cnt else None
    f["locked_mean_cross_s_before_close"] = None
    lc, fl, ew, el = crossing_times(lambda s: cum[s], secs, lambda v: sign * (v - Keff) > 0)
    f["locked_mean_last_cross_s_before_close"] = (close - lc) if lc is not None else None
    f["locked_mean_ever_winning"] = ew
    # projection mu(s) = (locked up to s + remaining * print(s)) / 60 -- the model's own forecast, tape values
    def mu_at(s):
        if s not in idx:
            return None
        pres = [idx[q] for q in range(close - 60, min(s, close - 1) + 1) if q in idx]
        rr = 60 - len(pres)
        return (sum(pres) + rr * idx[s]) / 60.0
    mc, mf, mw, ml = crossing_times(mu_at, list(range(max(close - 60, s0 - 60), close)), lambda v: sign * (v - Keff) > 0)
    f["mu_last_cross_s_before_close"] = (close - mc) if mc is not None else None
    f["mu_cross_after_send_s"] = (round(mc - ts, 1) if mc is not None else None)
    f["mu_on_our_side_at_send"] = f["z_tape"] > 0
    pc, pf, pw, pl = crossing_times(lambda s: idx.get(s), list(range(s0, close)), lambda v: sign * (v - Keff) > 0)
    f["print_first_losing_after_send_s"] = (pf - ts) if pf is not None else None       # seconds after the send
    f["print_first_losing_sec"] = pf
    f["print_last_cross_s_before_close"] = (close - pc) if pc is not None else None
    f["print_last_cross_sec"] = pc
    # moves after the send
    end = idx.get(close - 1)
    if end is None:
        e2 = [s for s in idx if s < close]
        end = idx[max(e2)] if e2 else None
    f["move_send_to_close_sigma"] = (round(-sign * (end - spot) / sigma, 3) if (end is not None and sigma) else None)
    f["move_send_to_close_bp"] = (round(-sign * (end - spot) / K * 1e4, 3) if end is not None else None)
    mx5 = mx1 = None
    mx5_at = None
    for s in range(s0, close - 1):
        if s in idx:
            for k, store in ((5, "5"), (1, "1")):
                if s + k in idx and s + k <= close - 1:
                    mv = -sign * (idx[s + k] - idx[s]) / sigma if sigma else None
                    if mv is None:
                        continue
                    if k == 5 and (mx5 is None or mv > mx5):
                        mx5, mx5_at = mv, s
                    if k == 1 and (mx1 is None or mv > mx1):
                        mx1 = mv
    f["max_move_against_5s_sigma"] = round(mx5, 3) if mx5 is not None else None
    f["max_move_against_5s_at_s_after_send"] = (round(mx5_at - ts, 1) if mx5_at is not None else None)
    f["max_move_against_1s_sigma"] = round(mx1, 3) if mx1 is not None else None
    f["jump_before_cross"] = bool(mx5 is not None and mx5 > 3.0 and (mc is None or mx5_at <= mc))
    # onset of the move: first print after the send that is >= 2 sd against us from the print at the send
    onset = None
    for s in range(s0 + 1, close):
        if s in idx and sigma and -sign * (idx[s] - spot) / sigma >= 2.0:
            onset = s
            break
    f["idx_onset_sec"] = onset
    f["idx_onset_after_send_s"] = (round(onset - ts, 2) if onset is not None else None)
    return f


def feed_features(m, raw, f):
    """Constituent books: divergence and moves at the send; who crossed first."""
    out = {}
    feeds = raw.get("feeds") or {}
    if not feeds:
        out["feed_available"] = False
        return out
    out["feed_available"] = True
    ts, close = m["t_send"], m["close_s"]
    sign = 1.0 if m["want"] == "yes" else -1.0
    bot = m["bot"]
    K = bot["strike"]
    Keff = K - 0.5 * 10.0 ** (-bot["digits"])
    sigma = f.get("sigma_bot") or f.get("sigma_tape_5min")
    mids_at = {}
    moves1, moves3 = {}, {}
    losing_at_send = {}
    first_losing = {}
    last_cross = {}
    for ex, rows in feeds.items():
        if not rows:
            continue
        # latest quote at or before ts (age <= 2 s)
        def mid_at(t):
            best = None
            for r in rows:
                if r[0] <= t:
                    best = r
                else:
                    break
            if best is None or t - best[0] > 2.0:
                return None
            return (best[1] + best[2]) / 2.0
        m0 = mid_at(ts)
        if m0 is None:
            continue
        mids_at[ex] = m0
        losing_at_send[ex] = sign * (m0 - Keff) < 0
        for w, store in ((1.0, moves1), (3.0, moves3)):
            mw = mid_at(ts - w)
            if mw is not None and sigma:
                store[ex] = round(-sign * (m0 - mw) / sigma, 3)
        # first time at/after the send that this feed's mid is on the losing side; last cross before close
        prev = None
        for r in rows:
            if r[0] < ts:
                continue
            if r[0] > close:
                break
            mid = (r[1] + r[2]) / 2.0
            w = sign * (mid - Keff) > 0
            if not w and ex not in first_losing:
                first_losing[ex] = r[0]
            if prev is True and not w:
                last_cross[ex] = r[0]
            prev = w
    out["feeds_quoting_at_send"] = sorted(mids_at)
    out["mids_at_send"] = {k: round(v, 6) for k, v in mids_at.items()}
    if len(mids_at) >= 2:
        vals = list(mids_at.values())
        out["divergence_bp"] = round((max(vals) - min(vals)) / statistics.median(vals) * 1e4, 3)
    else:
        out["divergence_bp"] = None
    if mids_at:
        med = statistics.median(mids_at.values())
        out["feed_median_vs_strike_sigma"] = round(sign * (med - Keff) / sigma, 3) if sigma else None
        out["feed_median_vs_index_sigma"] = (round(sign * (med - f["spot_tape"]) / sigma, 3) if sigma and f.get("spot_tape") else None)
    out["any_feed_losing_at_send"] = any(losing_at_send.values()) if losing_at_send else None
    out["n_feeds_losing_at_send"] = sum(1 for v in losing_at_send.values() if v)
    out["feed_move_against_1s_max"] = max(moves1.values()) if moves1 else None
    out["feed_move_against_1s_med"] = round(statistics.median(moves1.values()), 3) if moves1 else None
    out["feed_move_against_3s_max"] = max(moves3.values()) if moves3 else None
    out["feed_move_against_3s_med"] = round(statistics.median(moves3.values()), 3) if moves3 else None
    out["feed_first_losing_after_send"] = {k: round(v - ts, 3) for k, v in first_losing.items()}
    out["feed_last_cross"] = {k: round(close - v, 3) for k, v in last_cross.items()}
    pf = f.get("print_first_losing_sec")
    if pf is not None and first_losing:
        ex_first = min(first_losing.values())
        out["lead_first_s"] = round(pf - ex_first, 3)        # + = a constituent was on the losing side before the CF print
        out["lead_first_feed"] = min(first_losing, key=first_losing.get)
    else:
        out["lead_first_s"] = None
    pc = f.get("print_last_cross_sec")
    if pc is not None and last_cross:
        ex_last = min(last_cross.values())
        out["lead_last_s"] = round(pc - ex_last, 3)
    else:
        out["lead_last_s"] = None
    # onset lead, robust to the static price basis between exchanges: first time after the send each book is
    # >= 2 sd against us from ITS OWN mid at the send, vs the print's onset (index_features)
    onsets = {}
    for ex, rows in feeds.items():
        m0 = mids_at.get(ex)
        if m0 is None or not sigma:
            continue
        for r in rows:
            if r[0] < ts:
                continue
            if r[0] > close:
                break
            if -sign * ((r[1] + r[2]) / 2.0 - m0) / sigma >= 2.0:
                onsets[ex] = r[0]
                break
    out["feed_onset_after_send"] = {k: round(v - ts, 3) for k, v in onsets.items()}
    io = f.get("idx_onset_sec")
    if io is not None and onsets:
        out["onset_lead_s"] = round(io - min(onsets.values()), 3)       # + = a book moved first
        out["onset_lead_feed"] = min(onsets, key=onsets.get)
    else:
        out["onset_lead_s"] = None
    # replica cross-check at the send second
    rep = [r for r in (raw.get("replica") or []) if r["sec"] == int(math.floor(ts))]
    if rep and rep[0].get("per_ex"):
        pe = rep[0]["per_ex"]
        mids = [(v["b"] + v["a"]) / 2.0 for v in pe.values() if v.get("b") and v.get("a")]
        if len(mids) >= 2:
            out["replica_divergence_bp"] = round((max(mids) - min(mids)) / statistics.median(mids) * 1e4, 3)
    return out


def flow_features(m, raw):
    ts = m["t_send"]
    want = m["want"]
    tr = raw.get("trades") or []
    out = {}
    for w in (3, 10):
        sel = [t for t in tr if ts - w <= t[0] < ts]
        sold = sum(t[2] for t in sel if t[1] != want)
        bought = sum(t[2] for t in sel if t[1] == want)
        out["sold_%ds" % w] = round(sold, 2)
        out["bought_%ds" % w] = round(bought, 2)
        out["sell_share_%ds" % w] = round(sold / (sold + bought), 4) if sold + bought > 0 else None
        out["n_trades_%ds" % w] = len(sel)
        out["largest_trade_%ds" % w] = round(max((t[2] for t in sel), default=0.0), 2)
        prices = {round(t[3] if want == "yes" else 1.0 - t[3], 3) for t in sel}
        out["levels_hit_%ds" % w] = len(prices)
        # trades AT OR BELOW our price on our side (someone else took the same cheap offer first)
        if m.get("price") is not None:
            out["vol_at_or_below_our_price_%ds" % w] = round(sum(
                t[2] for t in sel if (t[3] if want == "yes" else 1.0 - t[3]) <= m["price"] + 1e-9 and t[1] == want), 2)
    before = [t for t in tr if t[0] < ts]
    out["last_trade_age_s"] = round(ts - before[-1][0], 3) if before else None
    after = [t for t in tr if ts <= t[0] < ts + 2]
    out["vol_next_2s"] = round(sum(t[2] for t in after), 2)
    out["sold_next_2s"] = round(sum(t[2] for t in after if t[1] != want), 2)
    return out


def classify(m, f):
    if "error" in f:
        return "unmeasured"
    if m["group"] == "control":
        return "won"
    if m["result"] == m["want"]:
        return "hedge_false_alarm"          # the market went our way; the hedge cost the money
    bot = m["bot"]
    stale = ((bot.get("index_age_s") or 0) >= 1.5 or f.get("missing_prints_last5s", 0) >= 3
             or (f.get("spot_bot_minus_tape_sigma") is not None and abs(f["spot_bot_minus_tape_sigma"]) > 3))
    if stale:
        return "feed_stale"
    if f["z_tape"] <= 0:
        return "already_lost_at_send"
    if f.get("thin"):
        return "rounding_thin"
    if f.get("jump_before_cross"):
        at = f.get("max_move_against_5s_at_s_after_send")
        return "jump_at_send" if (at is not None and at <= 1.0) else "jump_later"
    if f.get("mu_last_cross_s_before_close") is not None:
        return "drift"
    return "other"


SIGNALS = [
    # key, direction ('high' = suspicious when high), label
    ("conf_bot", "low", "bot's own confidence in OUR side at the send"),
    ("apparent_edge_c", "high", "apparent edge = confidence minus price paid (cents)"),
    ("bot_edge_c", "high", "bot's logged edge_c at the signal"),
    ("price", "low", "price paid (cheap = the market disagreed with us)"),
    ("z_tape", "low", "model margin recomputed from the tape at the send (sd)"),
    ("dist_spot_sigma", "low", "index print minus strike at the send, in 1-s sd"),
    ("sigma_ratio", "high", "tape 5-min sd / bot sigma"),
    ("idx_move_against_1s", "high", "index moved against us in the last 1 s (sd)"),
    ("idx_move_against_3s", "high", "index moved against us in the last 3 s (sd)"),
    ("idx_move_against_10s", "high", "index moved against us in the last 10 s (sd)"),
    ("btc_move_against_pre_sd", "high", "BTC index 1-s move against us, 1-3 s before (alts only, sd)"),
    ("btc_move_against_incl_sd", "high", "BTC index 1-s move against us incl. the send second (alts, sd)"),
    ("feed_move_against_1s_max", "high", "worst constituent book move against us, last 1 s (sd)"),
    ("feed_move_against_3s_max", "high", "worst constituent book move against us, last 3 s (sd)"),
    ("feed_median_vs_index_sigma", "low", "constituent median mid minus CF print, toward our side (sd)"),
    ("divergence_bp", "high", "constituent max-min mid spread at the send (bp)"),
    ("n_feeds_losing_at_send", "high", "constituent books already on the losing side at the send (count)"),
    ("sell_share_3s", "high", "tape: share of taker volume selling our side, last 3 s"),
    ("sell_share_10s", "high", "tape: share of taker volume selling our side, last 10 s"),
    ("sold_3s", "high", "tape: contracts of our side sold by takers, last 3 s"),
    ("sold_10s", "high", "tape: contracts of our side sold by takers, last 10 s"),
    ("largest_trade_10s", "high", "tape: largest single trade, last 10 s (contracts)"),
    ("levels_hit_10s", "high", "tape: distinct price levels traded, last 10 s"),
    ("n_trades_10s", "high", "tape: number of trades, last 10 s"),
    ("vol_at_or_below_our_price_10s", "high", "tape: our side bought at/below our price by others, last 10 s"),
    ("last_trade_age_s", "low", "tape: seconds since the last trade in this market"),
    ("bot_sell_share_3s", "high", "bot's own sell_share_3s at the send"),
    ("bot_level_age_ms", "low", "bot: age of the offer level it hit (ms)"),
    ("bot_book_age_ms", "high", "bot: age of its book at the send (ms)"),
    ("bot_index_age_s", "high", "bot: age of its index print at the send (s)"),
    ("bot_size_at_best", "high", "bot: contracts offered at the level it hit"),
    ("price", "high", "price paid"),
    ("tau", "high", "seconds to close at the send"),
    ("filled", "high", "contracts filled on the first order"),
    ("book_best_created_age_s", "low", "tape book: age of the best offer level (s, losers+controls with a book)"),
    ("book_offer_events_3s", "high", "tape book: offer-side changes in the last 3 s"),
    ("book_qty_within_1c", "high", "tape book: contracts offered within 1c of the best"),
]


def build_rules():
    """Fixed-threshold rules a bot could actually run, incl. the 09-27 seller gate."""
    def _g(r, k):
        return r.get(k)

    def _rule(label, pred):
        return (label, pred)

    def _and(*preds):
        def p(r):
            vals = [q(r) for q in preds]
            if any(v is None for v in vals):
                return None
            return all(vals)
        return p

    def _or(*preds):
        def p(r):
            vals = [q(r) for q in preds]
            known = [v for v in vals if v is not None]
            if not known:
                return None
            return any(known)
        return p

    def _gt(k, t):
        return lambda r: (None if _g(r, k) is None else _g(r, k) > t)

    def _ge(k, t):
        return lambda r: (None if _g(r, k) is None else _g(r, k) >= t)

    def _lt(k, t):
        return lambda r: (None if _g(r, k) is None else _g(r, k) < t)

    RULES = [
        _rule("tape: takers sold more of our side than they bought in the last 3 s (share > 0.5)", _gt("sell_share_3s", 0.5)),
        _rule("bot's own sell_share_3s > 0.5 (logged since 09-25)", _gt("bot_sell_share_3s", 0.5)),
        _rule("bot: offer level younger than 500 ms", _lt("bot_level_age_ms", 500)),
        _rule("the 09-27 seller gate: level < 500 ms AND tape share > 0.5 AND tau > 20", _and(_lt("bot_level_age_ms", 500), _gt("sell_share_3s", 0.5), _gt("tau", 20))),
        _rule("the 09-27 seller gate with the bot's own share (since 09-25)", _and(_lt("bot_level_age_ms", 500), _gt("bot_sell_share_3s", 0.5), _gt("tau", 20))),
        _rule("index moved >= 1 sd against us over the last 3 s", _ge("idx_move_against_3s", 1.0)),
        _rule("index moved >= 2 sd against us over the last 3 s", _ge("idx_move_against_3s", 2.0)),
        _rule("index moved >= 1 sd against us over the last 1 s", _ge("idx_move_against_1s", 1.0)),
        _rule("a constituent book moved >= 2 sd against us in the last 1 s (feed coins)", _ge("feed_move_against_1s_max", 2.0)),
        _rule("a constituent book moved >= 1 sd against us in the last 3 s (feed coins)", _ge("feed_move_against_3s_max", 1.0)),
        _rule("constituent median sits >= 2 sd below the CF print on the losing side (feed coins)", _lt("feed_median_vs_index_sigma", -2.0)),
        _rule("index >= 1 sd / 3 s OR a book >= 2 sd / 1 s", _or(_ge("idx_move_against_3s", 1.0), _ge("feed_move_against_1s_max", 2.0))),
        _rule("BTC's index moved >= 2 sd against us 1-3 s before (alts)", _ge("btc_move_against_pre_sd", 2.0)),
        _rule("index print within 3 sd of the strike at the send", _lt("dist_spot_sigma", 3.0)),
        _rule("model margin on the tape below 2.5 sd", _lt("z_tape", 2.5)),
        _rule("apparent edge (confidence - price) above 10c", _gt("apparent_edge_c", 10.0)),
        _rule("price paid below 90c", _lt("price", 0.90)),
        _rule("bot's index print older than 0.8 s", _gt("bot_index_age_s", 0.8)),
        _rule("index >= 1 sd / 3 s OR level < 500 ms AND share > 0.5", _or(_ge("idx_move_against_3s", 1.0), _and(_lt("bot_level_age_ms", 500), _gt("sell_share_3s", 0.5)))),
    ]
    return RULES


def pop_report():
    """Every rule, on EVERY live-filled market (our own fills): what it refuses, what that costs."""
    pool = json.load(open(os.path.join(OUT, "pool.json"), encoding="utf-8"))
    rawdir = os.path.join(OUT, "raw_pool")
    feats = []
    for m in pool:
        p = os.path.join(rawdir, m["ticker"] + ".json")
        if not os.path.exists(p):
            p = os.path.join(OUT, "raw", m["ticker"] + ".json")
            if not os.path.exists(p):
                continue
        raw = json.load(open(p, encoding="utf-8"))
        f = index_features(m, raw)
        if "error" in f:
            continue
        f.update(feed_features(m, raw, f))
        f.update(flow_features(m, raw))
        for k in ("sell_share_3s", "level_age_ms", "book_age_ms", "index_age_s", "size_at_best", "edge_c"):
            f["bot_" + k] = m["bot"].get(k)
        fb = m["bot"].get("fair")
        f["conf_bot"] = (None if fb is None else (fb if m["want"] == "yes" else 1.0 - fb))
        f["apparent_edge_c"] = (None if (f["conf_bot"] is None or m.get("price") is None) else round(100.0 * (f["conf_bot"] - m["price"]), 2))
        row = {k: m.get(k) for k in ("ticker", "coin", "close_s", "want", "pnl", "price", "tau", "t_send", "hedged", "result", "filled")}
        row.update({k: f.get(k) for k in ("dist_spot_sigma", "z_tape", "idx_move_against_1s", "idx_move_against_3s", "idx_move_against_10s",
                                           "btc_move_against_pre_sd", "feed_available", "feed_move_against_1s_max", "feed_move_against_3s_max",
                                           "feed_median_vs_index_sigma", "sell_share_3s", "sold_3s", "bought_3s", "sell_share_10s",
                                           "bot_sell_share_3s", "bot_level_age_ms", "bot_index_age_s", "conf_bot", "apparent_edge_c",
                                           "bot_held_print", "sigma_bot", "sigma_tape_5min")})
        feats.append(row)
    with open(os.path.join(OUT, "pop_features.jsonl"), "w", encoding="utf-8") as fh:
        for r in feats:
            fh.write(json.dumps(r) + "\n")
    n_tot = len(feats)
    n_lost = sum(1 for r in feats if r["pnl"] < 0)
    out = {"n": n_tot, "lost": n_lost, "dollars": round(sum(r["pnl"] for r in feats), 2), "rules": []}
    for label, pred in build_rules():
        vals = [(r, pred(r)) for r in feats]
        known = [(r, v) for r, v in vals if v is not None]
        if len(known) < 30:
            out["rules"].append({"rule": label, "n": len(known), "note": "too few markets with the inputs"})
            continue
        ref = [r for r, v in known if v]
        kept = [r for r, v in known if not v]
        a = sum(1 for r in ref if r["pnl"] < 0)
        b = sum(1 for r in kept if r["pnl"] < 0)
        p = fisher_one_sided(a, len(ref), b, len(kept)) if ref and kept else 1.0
        out["rules"].append({"rule": label, "n": len(known), "refused": len(ref), "refused_lost": a,
                             "refused_dollars": round(sum(r["pnl"] for r in ref), 2),
                             "refused_lost_dollars": round(sum(r["pnl"] for r in ref if r["pnl"] < 0), 2),
                             "refused_won_dollars": round(sum(r["pnl"] for r in ref if r["pnl"] > 0), 2),
                             "kept": len(kept), "kept_lost": b, "kept_dollars": round(sum(r["pnl"] for r in kept), 2),
                             "p": p})
    json.dump(out, open(os.path.join(OUT, "pop_rules.json"), "w", encoding="utf-8"), indent=1)
    print("POP: %d markets, %d lost, $%.2f" % (n_tot, n_lost, out["dollars"]))
    for r in out["rules"]:
        if "note" in r:
            print("  %-75s %s" % (r["rule"][:75], r["note"]))
        else:
            print("  %-75s refused %4d (lost %2d, $%8.2f = lost %8.2f + won %7.2f) kept %4d (lost %2d, $%8.2f) p=%.4f" % (
                r["rule"][:75], r["refused"], r["refused_lost"], r["refused_dollars"], r["refused_lost_dollars"], r["refused_won_dollars"],
                r["kept"], r["kept_lost"], r["kept_dollars"], r["p"]))


def report():
    mk = json.load(open(os.path.join(OUT, "markets.json"), encoding="utf-8"))
    rows = []
    rawdir = os.path.join(OUT, "raw")
    unmeasured = []
    for m in mk["losers"] + mk["controls"]:
        p = os.path.join(rawdir, m["ticker"] + ".json")
        if not os.path.exists(p):
            unmeasured.append(m["ticker"])
            continue
        raw = json.load(open(p, encoding="utf-8"))
        f = index_features(m, raw)
        if "error" not in f:
            f.update(feed_features(m, raw, f))
            f.update(flow_features(m, raw))
        bp = os.path.join(rawdir, m["ticker"] + ".book.json")
        if os.path.exists(bp):
            b = json.load(open(bp, encoding="utf-8"))
            for k, v in b.items():
                f["book_" + k] = v
        for k in ("sell_share_3s", "level_age_ms", "book_age_ms", "index_age_s", "size_at_best", "taker_n_3s", "trade_age_s", "edge_c", "ladder_under"):
            f["bot_" + k] = m["bot"].get(k)
        fb = m["bot"].get("fair")
        f["conf_bot"] = (None if fb is None else (fb if m["want"] == "yes" else 1.0 - fb))
        f["fair_bot"] = f["conf_bot"]
        f["apparent_edge_c"] = (None if (f["conf_bot"] is None or m.get("price") is None) else round(100.0 * (f["conf_bot"] - m["price"]), 2))
        hs = [h for h in (m.get("hedges") or []) if h.get("t")]
        f["hedge_after_send_s"] = (round(parse_iso(hs[0]["t"]) - m["t_send"], 1) if hs else None)
        f["hedge_tau"] = hs[0].get("tau") if hs else None
        f["hedge_belief"] = hs[0].get("belief") if hs else None
        row = dict(m)
        row.update(f)
        row["class"] = classify(m, f)
        rows.append(row)
    losers = [r for r in rows if r["group"] == "loser"]
    controls = [r for r in rows if r["group"] == "control"]
    with open(os.path.join(OUT, "loss_anatomy.jsonl"), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")

    # ---- settlement sanity ---------------------------------------------------
    mism = [r["ticker"] for r in rows if r.get("result_tape") and r["result_tape"] != r["result_ledger"]]
    short = [(r["ticker"], r.get("settle_n_prints")) for r in rows if r.get("settle_n_prints") is not None and r["settle_n_prints"] < 60]
    feeddiff = [(r["ticker"], r["settle_vs_feed_avg"]) for r in rows if r.get("settle_vs_feed_avg") is not None and abs(r["settle_vs_feed_avg"]) > 1e-6]

    # ---- separation table ----------------------------------------------------
    sep = []
    for key, direction, label in SIGNALS:
        lv = [r[key] for r in losers if r.get(key) is not None]
        cv = [r[key] for r in controls if r.get(key) is not None]
        if len(cv) < 10 or len(lv) < 3:
            sep.append({"key": key, "label": label, "n_losers": len(lv), "n_controls": len(cv), "note": "too few values"})
            continue
        if direction == "high":
            thr = quantile(cv, 0.90)
            flag = lambda v: v > thr
        else:
            thr = quantile(cv, 0.10)
            flag = lambda v: v < thr
        a = sum(1 for v in lv if flag(v))
        b = sum(1 for v in cv if flag(v))
        p = fisher_one_sided(a, len(lv), b, len(cv))
        # out-of-sample split for the signals already looked at on 09-24 (toxicity.md, FEED_LEAD): losers from 09-25 on
        split = datetime(2026, 9, 25, tzinfo=timezone.utc).timestamp()
        pre = [r for r in losers if r.get(key) is not None and r["close_s"] < split]
        post = [r for r in losers if r.get(key) is not None and r["close_s"] >= split]
        a_pre = sum(1 for r in pre if flag(r[key]))
        a_post = sum(1 for r in post if flag(r[key]))
        dol_l = sum(r["pnl"] for r in losers if r.get(key) is not None and flag(r[key]))
        dol_c = sum(r["pnl"] for r in controls if r.get(key) is not None and flag(r[key]))
        sep.append({"key": key, "label": label, "direction": direction, "threshold": thr,
                    "n_losers": len(lv), "losers_flagged": a, "losers_share": round(a / len(lv), 3),
                    "n_controls": len(cv), "controls_flagged": b, "controls_share": round(b / len(cv), 3),
                    "p_one_sided": p, "losers_dollars_flagged": round(dol_l, 2),
                    "pre0925_flagged": a_pre, "pre0925_n": len(pre), "post0925_flagged": a_post, "post0925_n": len(post),
                    "controls_dollars_flagged": round(dol_c, 2),
                    "median_losers": round(statistics.median(lv), 4), "median_controls": round(statistics.median(cv), 4)})
    json.dump(sep, open(os.path.join(OUT, "separation.json"), "w", encoding="utf-8"), indent=1)

    # ---- MDE: the smallest loser flag share that reaches p<0.05 (one look) and p<0.05/len(SIGNALS)
    nL, nC = len(losers), len(controls)
    bC = int(round(0.10 * nC))
    mde = {}
    for bar in (0.05, 0.05 / len(SIGNALS)):
        for a in range(0, nL + 1):
            if fisher_one_sided(a, nL, bC, nC) < bar:
                mde[str(round(bar, 4))] = (a, round(a / nL, 3) if nL else None)
                break

    # ---- write the markdown -------------------------------------------------
    L = []
    L.append("# Loss anatomy -- every live loser against the raw recordings (2026-10-08)\n")
    L.append("Source order: raw settlement-index feed, raw trade tape and order book, constituent exchange books, "
             "our own live fills joined to the ledger. No replay. **This is what happened around OUR fills; it is not a "
             "loss rate from the tape and must not be quoted as one.**\n")
    meta = mk["meta"]
    L.append("## Population\n")
    L.append("- Losers: every crypto 15M market (12 up/down series; KXCRYPTOLEAD, commodities and pre-2026-09-08 excluded) "
             "where the ledger's per-market money (revenue/100 + min(yes,no) - costs - fees) is negative AND pinrun-live has a "
             "filled order: **%d markets, $%.2f**. Ledger markets with no live fill (other bots / manual): %d; losers before 09-08: see skipped.\n"
             % (meta["n_losers"], meta["losers_dollars"], meta["skipped"].get("no_live_fill", 0)))
    L.append("- Controls: %d winners sampled with seed %d from %d live winners (+$%.2f), stratified to the losers' tau x price cells "
             "(tau %s; price %s). Allocation: %s\n" % (meta["n_controls"], meta["seed"], meta["n_winners_pool"], meta["winners_pool_dollars"],
                                                      meta["tau_buckets"], meta["price_buckets"], meta["alloc"]))
    L.append("- Decision time = the first FILLED order's send, to the millisecond: `t_ms_send` where logged (from 09-22), otherwise the "
             "local-clock millisecond embedded in the order's `client_order_id` (`pin-<ms>-<hex>`; equal to t_ms_send within 1 ms where both exist). "
             "Side, price, tau, strike, sigma, fair, spot, offer-level age and the bot's 3-s sell share come from that order and its signal record.\n")
    L.append("- Skipped: %s. Unmeasured (no raw file): %d %s\n" % (meta["skipped"], len(unmeasured), unmeasured[:5]))
    L.append("- Crypto losers in the ledger NOT in this population: %s\n" % meta.get("excluded_losers"))
    L.append("- Send-time precision: losers %d of %d to the millisecond, controls %d of %d; the local clock agrees with the exchanges' "
             "(collector receipt minus exchange stamp: Bitstamp 77 ms, Coinbase 24 ms, Kraken 66 ms, Gemini 50 ms median in these windows), "
             "so 'before the send' leaks at most ~0.1 s of what came after.\n"
             % (sum(1 for r in losers if r["t_send_prec"].startswith("ms")), len(losers), sum(1 for r in controls if r["t_send_prec"].startswith("ms")), len(controls)))
    L.append("- Constituent feed (Bitstamp/Coinbase/Kraken, Gemini for BTC) exists for BTC/ETH/SOL/XRP/DOGE only: losers with a feed %d of %d, controls %d of %d. BNB/NEAR/HYPE/ZEC markets get the index and the Kalshi tape only.\n"
             % (sum(1 for r in losers if r.get("feed_available")), len(losers), sum(1 for r in controls if r.get("feed_available")), len(controls)))
    L.append("- Settlement cross-check: my 60-print mean vs the ledger result disagrees on %d of %d markets %s; markets with fewer than 60 "
             "prints on the tape: %d %s; my mean vs CF's own `avg_60s_data` at the close differs by >1e-6 on %d %s.\n"
             % (len(mism), len(rows), mism[:5], len(short), short[:8], len(feeddiff), feeddiff[:5]))
    st = json.load(open(os.path.join(OUT, "raw_measure_stats.json"), encoding="utf-8")) if os.path.exists(os.path.join(OUT, "raw_measure_stats.json")) else {}
    L.append("- Tape files missing: %d %s; torn (read up to the tear, nothing filled): %d %s\n"
             % (len(st.get("missing", [])), [os.path.basename(x) for x in st.get("missing", [])][:12],
                len(st.get("torn", [])), [os.path.basename(x[0]) for x in st.get("torn", [])][:12]))

    # class counts
    from collections import Counter
    cc = Counter(r["class"] for r in losers)
    cd = defaultdict(float)
    for r in losers:
        cd[r["class"]] += r["pnl"]
    L.append("\n## Loss classes (first match in this order)\n")
    L.append("| class | n | $ | meaning |\n|---|---|---|---|\n")
    meaning = {
        "hedge_false_alarm": "the market settled OUR way; the money went on a hedge bought against a scare",
        "feed_stale": "bot's index print >= 1.5 s old, or >= 3 missing prints in the last 5 s, or the bot's spot differed from the tape print by > 3 sd",
        "already_lost_at_send": "the model's own projection, recomputed with the tape's values at the send, was already on the losing side",
        "rounding_thin": "settlement within 1 unit of the last rounded digit, or within 1 bp, of the strike",
        "jump": "a 5-s index move against us of > 3 one-second sd, before the projection crossed",
        "drift": "the projection crossed to the losing side after the send without such a 5-s jump",
        "other": "none of the above",
        "unmeasured": "no usable index window on the tape",
    }
    meaning["jump_at_send"] = "a 5-s index move against us of > 3 one-second sd that began within 1 s of the send (we bought into the start of the move)"
    meaning["jump_later"] = "the same kind of move, but it began more than 1 s after the send (nothing at the send had moved yet)"
    for k in ("jump_at_send", "jump_later", "drift", "already_lost_at_send", "rounding_thin", "feed_stale", "hedge_false_alarm", "other", "unmeasured"):
        if cc.get(k):
            L.append("| %s | %d | %.2f | %s |\n" % (k, cc[k], cd[k], meaning[k]))

    # per-loss table
    L.append("\n## Every loss (ET close; $ = ledger money; dist = index print minus strike at the send in 1-s sd; "
             "lead = seconds a constituent book was on the losing side before the CF print was, after the send (+ = book first); "
             "sell3 = tape share of taker volume selling our side in the 3 s before; age = bot's offer-level age ms)\n")
    L.append("| ticker | ET close | $ | side | price | tau | class | conf bot | dist sd | z tape | move began (s after send) | crossed (s after send) | max 5-s move sd | idx move 3 s before | book move 1 s before | book lead s | sell3 tape | sell3 bot | age ms | hedge (s after send) |\n")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    for r in losers:
        L.append("| %s | %s | %.2f | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |\n" % (
            r["ticker"], et_str(r["close_s"]), r["pnl"], r["want"], r.get("price"), r.get("tau"), r["class"],
            r.get("conf_bot"), r.get("dist_spot_sigma"), r.get("z_tape"), r.get("idx_onset_after_send_s"), r.get("mu_cross_after_send_s"),
            r.get("max_move_against_5s_sigma"), r.get("idx_move_against_3s"),
            r.get("feed_move_against_1s_max") if r.get("feed_available") else "no feed",
            r.get("onset_lead_s") if r.get("feed_available") else "no feed",
            r.get("sell_share_3s"), r.get("bot_sell_share_3s"), r.get("bot_level_age_ms"),
            ("%s" % r.get("hedge_after_send_s")) if r["hedged"] else ""))

    # separation table
    L.append("\n## Losers vs controls, every candidate signal available at the send\n")
    L.append("Threshold = the value that keeps 90%% of controls (their 90th or 10th percentile); 'flagged' = beyond it. "
             "n = markets. One-sided Fisher p. MDE: with %d losers and %d controls, a signal must flag at least %s losers "
             "(%s of them) to reach p < 0.05 on one look, and %s (%s) to clear the %d-look bar p < %.4f.\n"
             % (nL, nC, mde.get("0.05", ("?", "?"))[0], mde.get("0.05", ("?", "?"))[1],
                mde.get(str(round(0.05 / len(SIGNALS), 4)), ("?", "?"))[0], mde.get(str(round(0.05 / len(SIGNALS), 4)), ("?", "?"))[1],
                len(SIGNALS), 0.05 / len(SIGNALS)))
    L.append("| signal | bad when | threshold | losers flagged | of which before 09-25 / from 09-25 | controls flagged | median losers / controls | p | $ losers flagged | $ controls flagged |\n")
    L.append("|---|---|---|---|---|---|---|---|---|---|\n")
    for s in sep:
        if "note" in s:
            L.append("| %s | - | - | %d values | - | %d values | - | %s | - | - |\n" % (s["label"], s["n_losers"], s["n_controls"], s["note"]))
            continue
        L.append("| %s | %s | %s | %d of %d (%.0f%%) | %d of %d / %d of %d | %d of %d (%.0f%%) | %s / %s | %.4f | %.2f | %.2f |\n" % (
            s["label"], s["direction"], round(s["threshold"], 4) if isinstance(s["threshold"], float) else s["threshold"],
            s["losers_flagged"], s["n_losers"], 100 * s["losers_share"],
            s["pre0925_flagged"], s["pre0925_n"], s["post0925_flagged"], s["post0925_n"],
            s["controls_flagged"], s["n_controls"],
            100 * s["controls_share"], s["median_losers"], s["median_controls"], s["p_one_sided"],
            s["losers_dollars_flagged"], s["controls_dollars_flagged"]))
    RULES = build_rules()
    split = datetime(2026, 9, 25, tzinfo=timezone.utc).timestamp()
    L.append("\n## Fixed rules a bot could run (same population; a rule needs every input it names)\n")
    L.append("| rule | losers refused | of which before 09-25 / from 09-25 | controls refused | p | $ of losers refused | $ of controls refused |\n|---|---|---|---|---|---|---|\n")
    rule_rows = []
    for label, pred in RULES:
        lv = [(r, pred(r)) for r in losers]
        cv = [(r, pred(r)) for r in controls]
        lk = [(r, v) for r, v in lv if v is not None]
        ck_ = [(r, v) for r, v in cv if v is not None]
        if len(ck_) < 10 or len(lk) < 3:
            L.append("| %s | %d values | - | %d values | - | - | - |\n" % (label, len(lk), len(ck_)))
            continue
        a = sum(1 for r, v in lk if v)
        b = sum(1 for r, v in ck_ if v)
        p = fisher_one_sided(a, len(lk), b, len(ck_))
        a_pre = sum(1 for r, v in lk if v and r["close_s"] < split)
        n_pre = sum(1 for r, v in lk if r["close_s"] < split)
        a_post = sum(1 for r, v in lk if v and r["close_s"] >= split)
        n_post = len(lk) - n_pre
        dl = sum(r["pnl"] for r, v in lk if v)
        dc = sum(r["pnl"] for r, v in ck_ if v)
        rule_rows.append({"rule": label, "losers": a, "n_losers": len(lk), "controls": b, "n_controls": len(ck_), "p": p,
                          "pre": [a_pre, n_pre], "post": [a_post, n_post], "dollars_losers": round(dl, 2), "dollars_controls": round(dc, 2)})
        L.append("| %s | %d of %d (%.0f%%) | %d of %d / %d of %d | %d of %d (%.0f%%) | %.4f | %.2f | %.2f |\n" % (
            label, a, len(lk), 100.0 * a / len(lk), a_pre, n_pre, a_post, n_post, b, len(ck_), 100.0 * b / len(ck_), p, dl, dc))
    json.dump(rule_rows, open(os.path.join(OUT, "rules.json"), "w", encoding="utf-8"), indent=1)
    # tape vs bot sell share agreement (both exist since 09-25)
    both = [(r["sell_share_3s"], r["bot_sell_share_3s"]) for r in rows if r.get("sell_share_3s") is not None and r.get("bot_sell_share_3s") is not None]
    if both:
        agree = sum(1 for a_, b_ in both if abs(a_ - b_) <= 0.15)
        L.append("\nTape 3-s sell share vs the bot's own logged share, where both exist: within 0.15 on %d of %d markets (median abs gap %.3f).\n"
                 % (agree, len(both), statistics.median(abs(a_ - b_) for a_, b_ in both)))
    bk = [r for r in rows if r.get("book_best_ask") is not None]
    if bk:
        L.append("Tape order book rebuilt at the send (snapshot + deltas): best offer equals the bot's `ask_seen` on %d of %d markets; "
                 "no negative level on %d of %d.\n" % (sum(1 for r in bk if r.get("book_match_bot")), len(bk),
                                                        sum(1 for r in bk if (r.get("book_negative") or 0) == 0), len(bk)))

    # ---- the two stratification dimensions, on the WHOLE live-filled population (our own fills) ----
    pp = os.path.join(OUT, "pool.json")
    bucket_rows = []
    if os.path.exists(pp):
        pool = json.load(open(pp, encoding="utf-8"))
        L.append("\n## Price and tau on the whole live-filled population (controls are matched on these, so the table above cannot show them)\n")
        L.append("Every crypto 15M market with a pinrun-live fill since 09-08, counted in markets (our own fills, not the tape).\n\n")
        L.append("| bucket | markets | lost | lost per 100 | $ net | $ lost |\n|---|---|---|---|---|---|\n")
        for name, fn in (("price", lambda m: price_bucket(m["price"])), ("tau", lambda m: tau_bucket(m["tau"]))):
            labels = PRICE_BUCKETS if name == "price" else TAU_BUCKETS
            for i, lab in enumerate(labels):
                sel = [m for m in pool if fn(m) == i]
                if not sel:
                    continue
                lost = [m for m in sel if m["pnl"] < 0]
                row = {"dim": name, "bucket": str(lab), "n": len(sel), "lost": len(lost),
                       "net": round(sum(m["pnl"] for m in sel), 2), "lost_dollars": round(sum(m["pnl"] for m in lost), 2)}
                bucket_rows.append(row)
                L.append("| %s %s | %d | %d | %.1f | %.2f | %.2f |\n" % (name, lab, row["n"], row["lost"], 100.0 * row["lost"] / row["n"], row["net"], row["lost_dollars"]))
        # apparent edge (confidence - price) across the pool
        L.append("\n| apparent edge (conf - price, cents) | markets | lost | lost per 100 | $ net |\n|---|---|---|---|---|\n")
        for lo, hi in ((-100, 2), (2, 5), (5, 10), (10, 20), (20, 100)):
            sel = [m for m in pool if m["conf"] is not None and m["price"] is not None and lo <= 100 * (m["conf"] - m["price"]) < hi]
            if not sel:
                continue
            lost = [m for m in sel if m["pnl"] < 0]
            row = {"dim": "edge_c", "bucket": "[%d, %d)" % (lo, hi), "n": len(sel), "lost": len(lost),
                   "net": round(sum(m["pnl"] for m in sel), 2), "lost_dollars": round(sum(m["pnl"] for m in lost), 2)}
            bucket_rows.append(row)
            L.append("| [%d, %d) | %d | %d | %.1f | %.2f |\n" % (lo, hi, row["n"], row["lost"], 100.0 * row["lost"] / row["n"], row["net"]))
    json.dump({"class_counts": cc, "class_dollars": dict(cd), "mde": mde, "n_losers": nL, "n_controls": nC, "buckets": bucket_rows},
              open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"), indent=1)
    pr = os.path.join(OUT, "pop_rules.json")
    if os.path.exists(pr):
        po = json.load(open(pr, encoding="utf-8"))
        L.append("\n## The same rules on EVERY live-filled market since 09-08 (our own fills: %d markets, %d lost, net $%.2f)\n"
                 % (po["n"], po["lost"], po["dollars"]))
        L.append("What each rule would have refused, counted in markets and in the ledger's dollars (refused $ = the money those markets "
                 "made or lost; negative is money a refusal would have SAVED). p = one-sided Fisher, lost-among-refused vs lost-among-kept.\n\n")
        L.append("| rule | markets with the inputs | refused | lost among refused | $ of refused (lost + won) | kept | lost among kept | $ of kept | p |\n|---|---|---|---|---|---|---|---|---|\n")
        for r in po["rules"]:
            if "note" in r:
                L.append("| %s | %d | %s | | | | | | |\n" % (r["rule"], r["n"], r["note"]))
                continue
            L.append("| %s | %d | %d (%.0f%%) | %d | %.2f (%.2f + %.2f) | %d | %d | %.2f | %.4f |\n" % (
                r["rule"], r["n"], r["refused"], 100.0 * r["refused"] / r["n"], r["refused_lost"], r["refused_dollars"],
                r["refused_lost_dollars"], r["refused_won_dollars"], r["kept"], r["kept_lost"], r["kept_dollars"], r["p"]))
    vp = os.path.join(OUT, "verdict.md")
    if os.path.exists(vp):
        L.append("\n" + open(vp, encoding="utf-8").read())
    open(os.path.join(OUT, "loss_anatomy.md"), "w", encoding="utf-8").write("".join(L))
    print("REPORT: losers %d controls %d classes %s" % (nL, nC, dict(cc)))
    print("settlement mismatches:", mism, "short windows:", short[:10], "feed-avg diffs:", feeddiff[:5])
    for s in sep:
        if "note" in s:
            print("  %-70s %s" % (s["label"][:70], s["note"]))
        else:
            print("  %-70s L %2d/%2d  C %2d/%3d  p=%.4f  thr=%s" % (s["label"][:70], s["losers_flagged"], s["n_losers"],
                                                                      s["controls_flagged"], s["n_controls"], s["p_one_sided"],
                                                                      round(s["threshold"], 4) if isinstance(s["threshold"], float) else s["threshold"]))


# ---------------------------------------------------------------------------
# self-test: planted worlds
# ---------------------------------------------------------------------------
def selftest():
    fails = []

    def ck(cond, msg):
        if not cond:
            fails.append(msg)
            print("  FAIL", msg)
        else:
            print("  ok  ", msg)

    close = 1_800_000_000
    # (1) a YES market, strike 100, 40 prints at 101 then a drop to 97 at tau 20: the projection crosses at the first
    #     97 print (close-20); the locked running mean crosses when 40*1 - 3k < 0 -> k = 14 -> second close-60+40+13 = close-7
    idx = {s: 101.0 for s in range(close - 420, close - 20)}
    idx.update({s: 97.0 for s in range(close - 20, close)})
    # a little noise before the window so sigma is defined (sd 1.0 of 1-s changes)
    rng = random.Random(1)
    v = 101.0
    for s in range(close - 420, close - 60):
        v += rng.gauss(0, 1.0)
        idx[s] = v
    idx[close - 61] = 101.0
    m = {"ticker": "KXTEST15M-26OCT010000-00", "coin": "TEST", "series": "KXTEST15M", "iid": "T", "close_s": close,
         "want": "yes", "t_send": close - 30 + 0.4, "tau": 30, "price": 0.97, "result": "no", "group": "loser",
         "hedged": False, "bot": {"strike": 100.0, "digits": 2, "sigma": 1.0, "fair": 0.999, "spot": 101.0, "index_age_s": 0.2}}
    raw = {"idx": {str(k): v for k, v in idx.items()}, "btc": {}, "rx_lat": {}, "avg60": None, "trades": [], "feeds": {}, "replica": []}
    f = index_features(m, raw)
    ck(f["mu_last_cross_s_before_close"] == 20, "projection crossing found at close-20 (got %s)" % f["mu_last_cross_s_before_close"])
    ck(f["locked_mean_last_cross_s_before_close"] == 7, "locked-mean crossing found at close-7 (got %s)" % f["locked_mean_last_cross_s_before_close"])
    ck(f["z_tape"] > 0 and f["locked_n"] == 31, "at the send (close-29.6) the projection is on our side with 31 locked prints (the current second's print has arrived)")
    ck(abs(f["dist_spot_sigma"] - (101.0 - 99.995)) < 1e-9, "distance to the effective strike in sd (got %s)" % f["dist_spot_sigma"])
    ck(f["max_move_against_5s_sigma"] == 4.0 and f["jump_before_cross"], "the 4-sd 5-s drop is found and precedes the crossing")
    ck(abs(f["settle"] - (40 * 101 + 20 * 97) / 60.0) < 1e-9 and f["result_tape"] == "no", "settlement mean and result")
    ck(classify(m, f) == "jump_later", "class = jump_later, the drop starts 10 s after the send (got %s)" % classify(m, f))
    ck(f["idx_onset_after_send_s"] is not None and abs(f["idx_onset_after_send_s"] - 9.6) < 1e-6,
       "onset of the move found 9.6 s after the send (got %s)" % f["idx_onset_after_send_s"])
    m1b = dict(m, t_send=close - 21 + 0.4)
    f1b = index_features(m1b, raw)
    ck(classify(m1b, f1b) == "jump_at_send", "a send 0.6 s before the drop is jump_at_send (got %s)" % classify(m1b, f1b))
    # (1b) the same path with a slow slide instead of a jump -> drift
    idx2 = dict(idx)
    for s in range(close - 61, close - 20):
        idx2[s] = 100.5
    for i, s in enumerate(range(close - 20, close)):
        idx2[s] = 100.5 - 0.5 * (i + 1)      # slides to 90.5; 2.5 sd per 5 s; mean 98.75 -> lost
    raw2 = dict(raw)
    raw2["idx"] = {str(k): v for k, v in idx2.items()}
    f2 = index_features(m, raw2)
    ck(f2["max_move_against_5s_sigma"] <= 2.5 + 1e-9 and f2["result_tape"] == "no" and classify(m, f2) == "drift", "slow slide classifies as drift (got %s, max5 %s)" % (classify(m, f2), f2["max_move_against_5s_sigma"]))
    # (1c) a thin settlement -> rounding_thin; (1d) a stale bot print -> feed_stale; (1e) already lost at send
    idx3 = {s: 100.004 for s in range(close - 420, close)}
    raw3 = dict(raw)
    raw3["idx"] = {str(k): v for k, v in idx3.items()}
    m3 = dict(m)
    m3["bot"] = dict(m["bot"], sigma=0.01, spot=100.004)
    f3 = index_features(m3, raw3)
    ck(f3["thin"] and classify(m3, f3) == "rounding_thin", "settlement 0.4 of a cent from the strike is 'rounding_thin' (got %s)" % classify(m3, f3))
    m4 = dict(m)
    m4["bot"] = dict(m["bot"], index_age_s=2.5)
    ck(classify(m4, f) == "feed_stale", "index_age 2.5 s -> feed_stale")
    m5 = dict(m)
    m5["t_send"] = close - 10 + 0.4
    m5["bot"] = dict(m["bot"], spot=97.0)
    f5 = index_features(m5, raw)
    ck(f5["z_tape"] < 0 and classify(m5, f5) == "already_lost_at_send", "a send after the drop is 'already lost at send' (z %s)" % f5["z_tape"])
    # (1f) an empty world: flat index above the strike, a winner -> nothing crosses, no jump
    idx6 = {s: 101.0 + 0.01 * ((s * 7919) % 3 - 1) for s in range(close - 420, close)}
    raw6 = dict(raw)
    raw6["idx"] = {str(k): v for k, v in idx6.items()}
    m6 = dict(m, result="yes", group="control")
    f6 = index_features(m6, raw6)
    ck(f6["mu_last_cross_s_before_close"] is None and f6["print_first_losing_after_send_s"] is None and not f6["jump_before_cross"],
       "empty world: no crossing, no jump")
    # (2) constituent lead: a feed that crosses to the losing side 2.5 s before the CF print does
    feeds = {"bitstamp": [[t / 10.0, 101.0 - 0.001, 101.0 + 0.001] for t in range((close - 35) * 10, (close - 23) * 10)]
             + [[t / 10.0, 97.0 - 0.001, 97.0 + 0.001] for t in range((close - 23) * 10 + 5, close * 10)]}
    raw7 = dict(raw, feeds=feeds)
    f7 = index_features(m, raw7)
    g7 = feed_features(m, raw7, f7)
    ck(abs(g7["lead_first_s"] - 2.5) < 1e-6, "feed leads the print by 2.5 s (got %s)" % g7["lead_first_s"])
    ck(abs(g7["onset_lead_s"] - 2.5) < 1e-6, "onset lead (2 sd from each source's own send level) is also 2.5 s (got %s)" % g7["onset_lead_s"])
    ck(g7["n_feeds_losing_at_send"] == 0 and g7["feed_move_against_1s_max"] == 0.0, "at the send the feed is on our side and flat")
    # (3) flow: 3 trades before the send, two selling our side
    trades = [[close - 30 - 2.0, "no", 10.0, 0.95, 0], [close - 30 - 1.0, "no", 30.0, 0.94, 0], [close - 30 - 0.5, "yes", 10.0, 0.95, 0],
              [close - 30 - 8.0, "yes", 100.0, 0.97, 0]]
    raw8 = dict(raw, trades=trades)
    g8 = flow_features(m, raw8)
    ck(g8["sold_3s"] == 40.0 and g8["bought_3s"] == 10.0 and abs(g8["sell_share_3s"] - 0.8) < 1e-9, "3-s sell share 0.8")
    ck(g8["largest_trade_10s"] == 100.0 and g8["levels_hit_10s"] == 3 and g8["n_trades_10s"] == 4, "10-s largest trade / levels / count")
    # (4) Fisher: 2 of 2 losers flagged, 0 of 2 controls -> 1/6
    ck(abs(fisher_one_sided(2, 2, 0, 2) - 1 / 6) < 1e-12, "Fisher one-sided 2/2 vs 0/2 = 1/6")
    ck(fisher_one_sided(0, 10, 3, 30) == 1.0, "Fisher with no loser flagged = 1")
    # (5) stratified sampler: 2 cells 3:1 -> 60:20 of 80
    losers = [{"tau": 5, "price": 0.95}] * 3 + [{"tau": 40, "price": 0.99}]
    winners = [{"tau": 5, "price": 0.95, "id": i} for i in range(100)] + [{"tau": 40, "price": 0.99, "id": 100 + i} for i in range(100)]
    ch, alloc = stratified_sample(losers, winners, 80, 11)
    c1 = sum(1 for w in ch if w["tau"] == 5)
    ck(len(ch) == 80 and c1 == 60, "stratified sample 60:20 (got %d:%d)" % (c1, 80 - c1))
    ch2, _ = stratified_sample(losers, winners, 80, 11)
    ck([w["id"] for w in ch] == [w["id"] for w in ch2], "sampler is deterministic in the seed")
    # (6) book: snapshot + deltas -> best offer and its age
    b = {"yes": {}, "no": {"0.0500": {"q": 10.0, "created": None, "changed": 100.0, "from_snap": True}}, "_seq": 1, "_ts": 100.0}
    ms = {"negative": 0}
    apply_book(b, "no", "0.0600", 20.0, 130.0, ms)
    bm = book_metrics(b, "yes", 131.0, 0.94, 100.0)
    ck(bm["best_ask"] == 0.94 and bm["best_qty"] == 20.0 and bm["best_created_age_s"] == 1.0 and bm["match_bot"],
       "book: a fresh NO bid at 6c is the best YES ask 94c, 1.0 s old")
    apply_book(b, "no", "0.0600", -20.0, 131.5, ms)
    bm2 = book_metrics(b, "yes", 132.0, 0.95, 100.0)
    ck(bm2["best_ask"] == 0.95 and bm2["best_from_snap"] and bm2["best_created_age_s"] is None, "book: after the pull the snapshot level is best again")
    # (7) ticker parsing and ET
    info = parse_ticker("KXZEC15M-26OCT070915-15")
    ck(info["close_s"] == 1791378900 and info["coin"] == "ZEC", "ticker -> close 2026-10-07T13:15Z")
    ck(hour_key(1791378900) == "20261007T13" and et_str(1791378900).endswith("09:15:00"), "hour key and ET formatting")
    # (8) sigma_at recovers a planted sd
    ser = {}
    v = 0.0
    rr = random.Random(3)
    for s in range(1000, 1400):
        v += rr.gauss(0, 2.0)
        ser[s] = v
    sg = sigma_at(ser, 1399)
    ck(1.6 < sg < 2.4, "sigma_at recovers sd 2 (got %.2f)" % sg)
    print("SELFTEST: %d failures" % len(fails))
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--book", action="store_true")
    ap.add_argument("--book-all", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--pop", action="store_true", help="measure the send-time rules on EVERY live-filled market")
    ap.add_argument("--pop-report", action="store_true")
    ap.add_argument("--only", default=None, help="comma-separated tickers")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if not selftest():
        print("self-test failed; refusing to touch real data")
        sys.exit(1)
    only = set(a.only.split(",")) if a.only else None
    if a.build:
        build()
    if a.measure or a.book or a.book_all:
        mk = json.load(open(os.path.join(OUT, "markets.json"), encoding="utf-8"))
        allm = mk["losers"] + mk["controls"]
        if a.measure:
            measure(allm, only)
        if a.book or a.book_all:
            book_stage(allm if a.book_all else mk["losers"], only)
    if a.pop:
        pool = json.load(open(os.path.join(OUT, "pool.json"), encoding="utf-8"))
        study = {m["ticker"] for m in json.load(open(os.path.join(OUT, "markets.json"), encoding="utf-8"))["losers"]}
        study |= {m["ticker"] for m in json.load(open(os.path.join(OUT, "markets.json"), encoding="utf-8"))["controls"]}
        measure([m for m in pool if m["ticker"] not in study], only, rawdir=os.path.join(OUT, "raw_pool"))
    if a.pop or a.pop_report:
        pop_report()
    if a.report:
        report()


if __name__ == "__main__":
    main()
