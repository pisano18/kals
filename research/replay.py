#!/usr/bin/env python3
# VERSION: 2026-08-25-r1
"""
replay.py -- run the engine over RECORDED collector data. "Would this have made
money?", answered without a live connection, without an order, without risk.

    python research/replay.py --selftest
    python research/replay.py --data ./kalshi_data --out ./fulltape

WHY REPLAY RATHER THAN A LIVE CLIENT

A live websocket client cannot be tested offline and cannot answer the question
that gates everything: is there an edge? The collector has been recording the
index, the book and every print since 2026-08-25. Replaying the engine over that
record uses data already on disk, costs nothing, risks nothing, and produces the
same answer a week of paper trading would -- immediately, and repeatably.

It is also the honest order of operations. A live client is worth building after
a measured edge, not before.

THE SIGNIFICANCE TEST -- and this is the part that matters

A strategy P&L number means nothing on its own. 400 markets of coin flips
produce impressive-looking runs routinely, and every large edge in this project
so far has been a measurement artefact.

So P&L is scored against an OUTCOME-REDRAW NULL, the same device as placebo.py:
keep every tick, every quote, every decision the engine made -- and redraw only
the settlement outcomes under the efficient-market null, y ~ Bernoulli(p) with
p the market's own final price. The engine's trades, sizes and entry prices are
held fixed; only whether they won changes.

Anything the strategy earns in that world is luck, by construction. The observed
P&L has to sit outside that distribution to mean anything.

WHAT IS APPROXIMATE, STATED PLAINLY
  * FILLS. We take the recorded best bid/ask and assume our order fills at the
    touch for the recorded size. Real queue position is not knowable from this
    record. Depth beyond the touch is ignored.
  * NO MARKET IMPACT. True only at small size.
  * The engine pays the real quadratic fee and never crosses more than the
    touch, but it does not model partial fills or cancels.
"""

import argparse
import glob
import gzip
import json
import math
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Engine, N_AVG, fee_per_contract, tick_at   # noqa: E402
from doctor import get_path, walk_paths, find_field           # noqa: E402


def load_schema(path="./schema.json"):
    """Field mappings discovered from the REAL collector output by doctor.py.

    Guessing field names is how a loader silently returns nothing, or returns
    something subtly wrong. If this file exists, its paths win over any name
    hard-coded here."""
    for cand in (path, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", path)):
        try:
            with open(cand) as f:
                return json.load(f)
        except (OSError, ValueError):
            continue
    return {}

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


def series_of(ticker):
    return ticker.split("-")[0] if ticker else None


def read_jsonl_gz(pattern, on_error=None):
    part = 0
    for fp in sorted(glob.glob(pattern)):
        try:
            with gzip.open(fp, "rt") as f:
                for line in f:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            part += 1              # file is mid-write; expected, not an error
            continue
    if on_error is not None:
        on_error["partial"] = part


# ===========================================================================
# loading -- forgiving about field names, loud about what it actually found
# ===========================================================================
def load_index(data_dir, verbose=True):
    acc = defaultdict(dict)
    stats = defaultdict(int)
    for m in read_jsonl_gz(os.path.join(data_dir, "cfbenchmarks_value",
                                        "*.jsonl.gz")):
        d = m.get("msg") or {}
        idx = d.get("index_id")
        inner = d.get("data")
        if isinstance(inner, str):
            try:
                inner = json.loads(inner)
            except json.JSONDecodeError:
                stats["bad_nested_json"] += 1
                continue
        if not idx or not isinstance(inner, dict):
            stats["no_index_or_data"] += 1
            continue
        try:
            t = int(round(float(inner["time"]) / 1000.0))
            v = float(inner["value"])
        except (KeyError, TypeError, ValueError):
            stats["no_time_or_value"] += 1
            continue
        acc[idx][t] = v
        stats["ok"] += 1
    if verbose:
        print(f"  index: {dict(stats)}")
        for k, v in sorted(acc.items(), key=lambda x: -len(x[1])):
            if not v:
                continue
            span = (max(v) - min(v)) / 3600.0
            cov = 100 * len(v) / max(span * 3600, 1)
            print(f"    {k:>13}: {len(v):>8,} s   {span:>6.2f} h   "
                  f"{cov:>5.1f}% coverage" + ("" if cov > 85 else "   <-- GAPPY"))
    return acc


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def infer_scale(vals):
    """Decide cents-vs-dollars ONCE, from the whole sample.

    Per-observation inference is a trap: on the tapered deci-cent grid a
    0.5-cent quote is written "0.5", which any `x > 1` test reads as 50 cents.
    That single line produced a 75c/contract edge against a provably fair
    maker. The aggregate is unambiguous -- if anything exceeds 1.5 the feed is
    in cents."""
    mx = max((abs(x) for x in vals if x is not None), default=0.0)
    return 100.0 if mx > 1.5 else 1.0


def load_quotes(data_dir, verbose=True, schema=None):
    """ticker -> sorted [(sec, bid, ask, bid_sz, ask_sz)].

    Field paths come from schema.json when doctor.py has run against the real
    collector output. Otherwise they are discovered on the fly from a sample of
    the data itself. Hard-coded names are the last resort, not the first."""
    if schema is None:
        schema = load_schema()
    tick = (schema or {}).get("ticker") or {}

    msgs = list(read_jsonl_gz(os.path.join(data_dir, "ticker", "*.jsonl.gz")))
    if not msgs:
        if verbose:
            print("  quotes: no ticker messages on disk")
        return {}

    # discover from the data if no schema was supplied
    if not tick.get("yes_bid"):
        paths = defaultdict(lambda: defaultdict(int))
        for m in msgs[:1500]:
            walk_paths(m, out=paths)
        tick = {c: find_field(paths, c) for c in
                ("ticker", "yes_bid", "yes_ask", "bid_size", "ask_size", "ts")}
        tick = {k: v for k, v in tick.items() if v}
        if verbose:
            print(f"  quotes: no schema.json, discovered {tick}")

    p_tk, p_b, p_a = tick.get("ticker"), tick.get("yes_bid"), tick.get("yes_ask")
    if not (p_tk and p_b and p_a):
        if verbose:
            print("  quotes: could not locate ticker/bid/ask fields. Run:")
            print("    python research/doctor.py --data <dir>")
        return {}
    p_bs, p_as, p_ts = tick.get("bid_size"), tick.get("ask_size"), tick.get("ts")

    raw = []
    for m in msgs:
        tk = get_path(m, p_tk)
        if not tk:
            continue
        b, a = _num(get_path(m, p_b)), _num(get_path(m, p_a))
        if b is None or a is None:
            continue
        t = parse_ts(get_path(m, p_ts)) if p_ts else None
        if not t:
            t = (m.get("_rx_ms") or 0) / 1000.0
        if not t:
            continue
        bs = _num(get_path(m, p_bs)) if p_bs else 0.0
        as_ = _num(get_path(m, p_as)) if p_as else 0.0
        raw.append((tk, int(round(t)), b, a, bs or 0.0, as_ or 0.0))

    scale = infer_scale([r[2] for r in raw] + [r[3] for r in raw])
    out = defaultdict(list)
    dropped = 0
    for tk, t, bid, ask, bs, as_ in raw:
        b, a = bid / scale, ask / scale
        if not (0 < b < 1 and 0 < a < 1):
            dropped += 1
            continue
        out[tk].append((t, b, a, bs, as_))
    for v in out.values():
        v.sort()
    if verbose:
        print(f"  quotes: {len(out):,} markets from {len(msgs):,} messages, "
              f"paths {p_b}/{p_a}, price scale /{scale:.0f}, "
              f"{dropped:,} out-of-range dropped")
    return out


def dump_channel(data_dir, chan, n=3):
    print(f"\n  --- raw {chan} records ---")
    i = 0
    for m in read_jsonl_gz(os.path.join(data_dir, chan, "*.jsonl.gz")):
        print("   ", json.dumps(m)[:600])
        i += 1
        if i >= n:
            return
    if i == 0:
        print("    (none found)")


def load_markets(out_dir):
    """strike/close/result per ticker, from the settled pull fulltape made."""
    fp = os.path.join(out_dir, "markets.json")
    if not os.path.exists(fp):
        return {}
    idx = {}
    for s, ms in json.load(open(fp)).items():
        for m in ms:
            idx[m["ticker"]] = m
    return idx


# ===========================================================================
def run(index, quotes, markets, ekw=None, default_size=200):
    """Replay in strict chronological order, exactly as a live feed would
    arrive. Index ticks and quotes are merged into one time-ordered stream.

    Feeding all the index history up front does NOT work: IndexState keeps a
    bounded tick window, so an up-front pass leaves nothing in memory by the
    time the early markets replay. That bug produced 2 trades in 300 markets.
    """
    eng = Engine(**(ekw or {}))
    usable = []
    for tk, q in quotes.items():
        m = markets.get(tk)
        if not m:
            continue
        iid = SERIES_TO_INDEX.get(m.get("series") or series_of(tk))
        if iid not in index:
            continue
        usable.append((tk, m, iid, q))
    if not usable:
        return eng, [], {}

    events = []
    for iid in {u[2] for u in usable}:
        for s, v in index[iid].items():
            events.append((s, 0, iid, v))          # 0 = index tick, first
    for tk, m, iid, q in usable:
        eng.on_market(tk, iid, m["strike"], m["close"])
        for (t, bid, ask, bs, as_) in q:
            events.append((t, 1, tk, (bid, ask, bs, as_)))
    events.sort(key=lambda e: (e[0], e[1]))

    closes = sorted({(int(m["close"]), tk) for tk, m, _, _ in usable})
    ci = 0
    decisions, pnl, traded = [], {}, set()
    for (t, kind, key, payload) in events:
        # settle anything that closed before this event
        while ci < len(closes) and closes[ci][0] < t:
            ctk = closes[ci][1]
            if ctk not in pnl:
                pnl[ctk] = eng.settle(ctk, markets[ctk]["result"])
            ci += 1
        if kind == 0:
            eng.on_index(key, t, payload)
            continue
        bid, ask, bs, as_ = payload
        eng.on_book(key, bid, ask, bs or default_size, as_ or default_size, t)
        if key in traded:
            continue
        d = eng.evaluate(key, t)
        if d:
            eng.record_fill(d)
            decisions.append(d)
            traded.add(key)
    while ci < len(closes):
        ctk = closes[ci][1]
        if ctk not in pnl:
            pnl[ctk] = eng.settle(ctk, markets[ctk]["result"])
        ci += 1
    return eng, decisions, pnl


def summarize(decisions, pnl, label):
    if not decisions:
        print(f"  {label}: no trades")
        return None
    tot = sum(pnl.values())
    n = len(decisions)
    ctr = sum(d.size for d in decisions)
    per = tot / max(ctr, 1)
    # one observation per CLOSE-TIME cluster: the 12 series close together and
    # are ~0.8 correlated, so the ticker is not the unit of independence
    by_close = defaultdict(float)
    for d in decisions:
        by_close[int(d.ts + d.ttc)] += pnl.get(d.ticker, 0.0)
    obs = list(by_close.values())
    mu = mean(obs)
    se = pstdev(obs) / math.sqrt(len(obs)) if len(obs) > 1 else float("inf")
    print(f"  {label:>20}{n:>8}{ctr:>10,}{tot:>12.2f}{100*per:>10.2f}c"
          f"{len(obs):>9}{mu/se if se > 0 else 0:>8.1f}")
    return {"pnl": tot, "n": n, "contracts": ctr, "per": per,
            "clusters": len(obs), "t": mu / se if se > 0 else 0.0}


def null_pnl(decisions, markets, quotes, reps=500, seed=0):
    """Hold the engine's trades, sizes and entry prices fixed; redraw only
    whether each won, under the null that THE PRICE IT PAID WAS FAIR:

        win ~ Bernoulli(entry price)

    Expected P&L in that world is exactly minus the fee, so anything above it
    is the strategy's claimed edge. Deliberately NOT drawn from the market's
    own last price: if the book is wrong -- which is the hypothesis under test
    -- that null inherits the same error and the test loses its power.
    """
    rnd = random.Random(seed)
    out = []
    for _ in range(reps):
        tot = 0.0
        for d in decisions:
            won = rnd.random() < d.price
            tot += d.size * ((1 - d.price) if won else -d.price)
            tot -= d.size * fee_per_contract(d.price)
        out.append(tot)
    return out


# ===========================================================================
def make_fake_collector(tmp, n_markets=120, sigma=6.0, seed=5, lag=0,
                        naming="kalshi"):
    """Write synthetic files in the collector's own format so the whole loader
    + replay path is exercised, not just the engine."""
    from statistics import NormalDist
    ND = NormalDist()
    from engine import var_factor
    rnd = random.Random(seed)
    os.makedirs(os.path.join(tmp, "cfbenchmarks_value"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "ticker"), exist_ok=True)
    t0 = 1_760_000_000
    total = 60 + n_markets * 900 + 120
    S, ticks = 80_000.0, {}
    for k in range(total):
        S += rnd.gauss(0, sigma)
        ticks[t0 + k] = S
    markets = {}
    with gzip.open(os.path.join(tmp, "cfbenchmarks_value",
                                "20260825T00.jsonl.gz"), "wt") as f:
        for s in sorted(ticks):
            f.write(json.dumps({"type": "cfbenchmarks_value",
                                "msg": {"index_id": "BRTI",
                                        "data": json.dumps({"time": s * 1000,
                                                            "value": ticks[s]})}
                                }) + "\n")
    with gzip.open(os.path.join(tmp, "ticker", "20260825T00.jsonl.gz"), "wt") as f:
        for w in range(n_markets):
            open_s = t0 + 60 + w * 900
            close_s = open_s + 900
            if close_s not in ticks:
                break
            strike = sum(ticks[s] for s in range(open_s - 59, open_s + 1)) / 60.0
            settle = sum(ticks[s] for s in range(close_s - 59, close_s + 1)) / 60.0
            tk = f"KXBTC15M-SYN{w:05d}"
            markets[tk] = {"ticker": tk, "series": "KXBTC15M", "strike": strike,
                           "settle": settle, "close": float(close_s),
                           "result": 1.0 if settle >= strike else 0.0}
            for s in range(open_s, close_s + 1):
                src = max(s - lag, open_s)
                spot = ticks[src]
                lo = close_s - N_AVG + 1
                hi = min(src, close_s)
                locked = [ticks[x] for x in range(lo, hi + 1) if x in ticks]
                r = N_AVG - max(0, hi - lo + 1)
                mu = (sum(locked) + r * spot) / N_AVG
                vf = var_factor(close_s - s, [1.0])
                if vf <= 0:
                    continue
                fair = 1.0 - ND.cdf((strike - mu) / (math.sqrt(vf) * sigma))
                step = 0.001 if (fair > 0.90 or fair < 0.10) else 0.01
                half = step / 2.0
                bid = max(round((fair - half) / step) * step, 0.001)
                ask = min(round((fair + half) / step) * step, 0.999)
                if ask <= bid:
                    ask = bid + step
                if naming == "kalshi":
                    body = {"market_ticker": tk,
                            "yes_bid": round(bid * 100, 1),
                            "yes_ask": round(ask * 100, 1),
                            "yes_bid_size": 500, "yes_ask_size": 500, "ts": s}
                elif naming == "short":          # dollars, short names
                    body = {"ticker": tk, "bid": round(bid, 4),
                            "ask": round(ask, 4), "bid_size": 500,
                            "ask_size": 500, "timestamp": s}
                else:                             # best_* prefixed, ISO time
                    body = {"market": tk, "best_bid": round(bid * 100, 1),
                            "best_ask": round(ask * 100, 1),
                            "best_bid_size": 500, "best_ask_size": 500,
                            "created_time": datetime.fromtimestamp(
                                s, timezone.utc).isoformat().replace(
                                    "+00:00", "Z")}
                f.write(json.dumps({"type": "ticker", "msg": body}) + "\n")
    return markets


def selftest():
    import tempfile, shutil
    print("=" * 78)
    print("SELF-TEST -- full loader + replay path on synthetic collector files")
    print("=" * 78)
    fails = []
    print(f"  {'scenario':>20}{'trades':>8}{'contracts':>10}{'P&L':>12}"
          f"{'per ctr':>10}{'clusters':>9}{'t':>8}")
    res = {}
    for label, lag in (("fair maker", 0), ("quote 20s stale", 20)):
        tmp = tempfile.mkdtemp()
        try:
            mk = make_fake_collector(tmp, n_markets=300, seed=5, lag=lag)
            idx = load_index(tmp, verbose=False)
            qs = load_quotes(tmp, verbose=False)
            if not qs:
                fails.append("loader parsed no quotes from its own format")
                break
            eng, ds, pnl = run(idx, qs, mk)
            res[label] = (summarize(ds, pnl, label), ds, qs, mk)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if "fair maker" in res:
        s = res["fair maker"][0]
        if s and s["n"] > 300 * 0.05:
            fails.append(f"traded a fair maker {s['n']} times in 300 markets")
    if "quote 20s stale" in res:
        s = res["quote 20s stale"][0]
        if not s or s["n"] < 300 * 0.10:
            fails.append("failed to trade a maker with 20s stale quotes")
        elif s["pnl"] <= 0:
            fails.append("lost money against a maker with stale quotes")

    print("\n  SCHEMA INDEPENDENCE -- same data, three field namings.")
    print("  The loader is told nothing; it discovers the fields itself.")
    print(f"  {'naming':>20}{'markets':>10}{'quotes':>12}{'trades':>9}"
          f"{'per ctr':>10}")
    base = None
    for naming in ("kalshi", "short", "best"):
        tmp = tempfile.mkdtemp()
        try:
            mk = make_fake_collector(tmp, n_markets=120, seed=5, lag=20,
                                     naming=naming)
            idx = load_index(tmp, verbose=False)
            qs = load_quotes(tmp, verbose=False, schema={})
            eng, ds, pnl = run(idx, qs, mk)
            ctr = sum(d.size for d in ds)
            per = (sum(pnl.values()) / ctr) if ctr else 0.0
            print(f"  {naming:>20}{len(qs):>10}{sum(len(v) for v in qs.values()):>12,}"
                  f"{len(ds):>9}{100*per:>9.2f}c")
            if not qs:
                fails.append(f"loader found no quotes under '{naming}' naming")
            if base is None:
                base = (len(qs), len(ds))
            elif (len(qs), len(ds)) != base:
                fails.append(f"'{naming}' naming gave a different result "
                             f"{(len(qs), len(ds))} vs {base}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print("\n  OUTCOME-REDRAW NULL (is the P&L luck?)")
    for label in ("quote 20s stale",):
        if label not in res:
            continue
        s, ds, qs, mk = res[label]
        if not ds:
            continue
        nulls = sorted(null_pnl(ds, mk, qs, reps=400, seed=3))
        lo, hi = nulls[int(.025 * len(nulls))], nulls[int(.975 * len(nulls))]
        pc = 100.0 * sum(1 for x in nulls if x <= s["pnl"]) / len(nulls)
        print(f"  {label:>20}  observed {s['pnl']:>10.2f}   "
              f"null 95% [{lo:.2f}, {hi:.2f}]   pctile {pc:.1f}%")
        if not (pc > 97.5):
            fails.append("a genuinely profitable strategy did not clear "
                         "its own outcome-redraw null")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- loader reads the collector format, replay stays")
    print("flat against a fair maker, profits against a stale one, and the")
    print("outcome-redraw null separates the two.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--reps", type=int, default=500)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dump-ticker", action="store_true")
    a = ap.parse_args()

    if a.dump_ticker:
        for ch in ("ticker", "trade", "orderbook_delta", "cfbenchmarks_value"):
            dump_channel(a.data, ch)
        return

    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    index = load_index(a.data)
    if not index:
        print("\n  No cfbenchmarks_value data -- that feed gates everything.")
        print("  RUNBOOK: the channel needs param `index_ids`, and a")
        print("  {'type':'subscribed'} reply is NOT success, only a data frame is.")
        return
    quotes = load_quotes(a.data)
    if not quotes:
        print("  ticker gave nothing usable -- rebuilding the book from"
              " orderbook deltas instead")
        try:
            from book import rebuild
            quotes, _ = rebuild(a.data)
        except Exception as e:
            print(f"  book rebuild failed: {type(e).__name__}: {e}")
            quotes = {}
    markets = load_markets(a.out)
    print(f"  markets with strike+result: {len(markets):,}")
    both = [tk for tk in quotes if tk in markets]
    print(f"  markets with BOTH quotes and a settled result: {len(both):,}")
    if not both:
        print("\n  Nothing to replay yet. Either the recording does not cover a")
        print("  market that has since settled, or fulltape/markets.json is")
        print("  stale -- re-run kalshi_fulltape.py to refresh settled outcomes.")
        if not quotes:
            print("\n  Run with --dump-ticker and send the output back.")
        return

    print(f"\n  {'scenario':>20}{'trades':>8}{'contracts':>10}{'P&L':>12}"
          f"{'per ctr':>10}{'clusters':>9}{'t':>8}")
    eng, ds, pnl = run(index, quotes, markets)
    s = summarize(ds, pnl, "engine")
    if not s or not ds:
        print("\n  The engine took no trades. Why:")
        for k, v in sorted(eng.skips.items(), key=lambda x: -x[1])[:8]:
            print(f"    {k:>34}: {v:,}")
        print("\n  That is a RESULT, not a failure: against this book, no edge")
        print("  survived fees and the sigma stress test.")
        return

    nulls = sorted(null_pnl(ds, markets, quotes, reps=a.reps, seed=99))
    lo, hi = nulls[int(.025 * len(nulls))], nulls[int(.975 * len(nulls))]
    pc = 100.0 * sum(1 for x in nulls if x <= s["pnl"]) / len(nulls)
    print(f"\n  OUTCOME-REDRAW NULL over {a.reps} draws")
    print(f"    observed P&L {s['pnl']:.2f}   null 95% [{lo:.2f}, {hi:.2f}]"
          f"   percentile {pc:.1f}%")
    print("    " + ("*** OUTSIDE the null -- a real effect, given these fills ***"
                    if pc > 97.5 or pc < 2.5 else
                    "inside the null -- consistent with luck. No edge shown."))
    print("\n  Fills are the weak assumption here: we take the touch at the")
    print("  recorded size and ignore queue position. Treat this as an upper")
    print("  bound and confirm against the collector's own book before")
    print("  believing it.")
    if eng.halted:
        print(f"\n  NOTE: engine halted mid-run -- {eng.halt_reason}")


if __name__ == "__main__":
    main()
