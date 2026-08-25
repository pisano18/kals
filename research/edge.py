#!/usr/bin/env python3
# VERSION: 2026-08-25-e1
"""
edge.py -- model vs market. The only question that matters.

    python research/edge.py --selftest              # synthetic end-to-end first
    python research/edge.py --data ./kalshi_data --out ./fulltape

WHAT THIS DOES THAT NOTHING ELSE IN THE PROJECT DOES

Every previous analysis compared PRICE to OUTCOME. That is a calibration test.
A market can be perfectly calibrated in every price bucket and still be beaten
by a model that conditions on more information -- calibration is a statement
about the marginal distribution, not about efficiency.

This compares a MODEL to the MARKET, head to head, on the same events, and asks
which one predicts the outcome better. That is the efficiency test.

THE MODEL (derived and MC-verified in settlement_math.py)

At any second t, with `locked` = the settle-window ticks already printed and
r = the number still to come:

    E[settle | t] = (sum(locked) + r * S_t) / 60
    Var[settle | t] = (1/3600) * sum_j sum_k w_j w_k gamma(|j-k|)
    P(Yes) = Phi( (E[settle] - strike) / sd )

where w_j counts how many future settle ticks the second-j innovation feeds,
and gamma is the AUTOCOVARIANCE of one-second index increments.

Why gamma and not sigma^2: BRTI is built from order-book mids, once per second.
Mids are smoothed and can be autocorrelated at one-second scale. If we assumed
iid increments and BRTI actually has gamma(1) != 0, every variance we compute
would be wrong by a fixed factor and every probability with it. Estimating
gamma from the recorded index costs nothing and removes the assumption. R1
flagged this as the first thing to check; this is the check.

WHAT IT MEASURES
  1. GATE -- can we reconstruct expiration_value from our own tick record?
  2. VARIANCE CURVE -- is BRTI a random walk at 1s, or smoothed/mean-reverting?
  3. HEAD-TO-HEAD -- log-loss and Brier of model vs market, clustered.
  4. IMPLIED SIGMA -- back sigma out of the market price and compare to
     realized. A slow book sigma is the most durable edge shape available.
  5. DELTA DAMPING -- regress contract move on index move by time bucket.
     The true coefficient falls like r/60. If the book's stays flat, it
     overreacts near expiry and the fade is mechanical.
  6. LEAD-LAG -- does the contract FOLLOW the index? Plumbing, not opinion.

HARD RULES OBSERVED
  * read-only; never writes under kalshi_data/ or feed_data/
  * every n reported is a number of MARKETS or CLOSE-TIME CLUSTERS, never trades
  * clustered on close-time: the 12 series close simultaneously and are ~0.8
    correlated, so ticker-level clustering would inflate t by roughly 10x
"""

import argparse
import glob
import gzip
import json
import math
import os
import random
import time
from collections import defaultdict
from datetime import datetime, timezone
from statistics import NormalDist, mean, median, pstdev

ND = NormalDist()
BASE = "https://api.elections.kalshi.com/trade-api/v2"
N_AVG = 60

# Exogenous evaluation grid, seconds before close. One observation per market
# per gridpoint -- never every trade. See the note above run_pipeline().
TTC_GRID = (600, 480, 360, 240, 180, 120, 90, 60, 45, 30, 20, 10)

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


# ===========================================================================
# loading -- deliberately forgiving, and it reports what it actually found
# ===========================================================================
def read_jsonl_gz(path_glob):
    """The collector holds the current hour's .gz open and flushing. Reading it
    mid-write raises EOFError OR zlib.error OR OSError -- catch broad."""
    n_part = 0
    for fp in sorted(glob.glob(path_glob)):
        try:
            with gzip.open(fp, "rt") as f:
                for line in f:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            n_part += 1
            continue


def load_index(data_dir, verbose=True):
    """index_id -> {second: (value, avg60_or_None)}"""
    acc = defaultdict(dict)
    shapes = defaultdict(int)
    for m in read_jsonl_gz(os.path.join(data_dir, "cfbenchmarks_value",
                                        "*.jsonl.gz")):
        d = m.get("msg") or {}
        idx = d.get("index_id")
        inner = d.get("data")
        if isinstance(inner, str):                 # nested JSON *string*
            try:
                inner = json.loads(inner)
            except json.JSONDecodeError:
                continue
        if not idx or not isinstance(inner, dict):
            shapes["unparsed"] += 1
            continue
        try:
            t = float(inner["time"]) / 1000.0      # CF's own clock
            v = float(inner["value"])
        except (KeyError, TypeError, ValueError):
            shapes["no_time_or_value"] += 1
            continue
        a = None
        av = d.get("avg_60s_data")
        if isinstance(av, dict):
            try:
                a = float(av.get("value"))
            except (TypeError, ValueError):
                a = None
        acc[idx][int(round(t))] = (v, a)
        shapes["ok"] += 1
    if verbose:
        print(f"  index messages parsed: {dict(shapes)}")
        for k, v in sorted(acc.items(), key=lambda x: -len(x[1])):
            span = (max(v) - min(v)) / 3600.0 if v else 0
            rate = len(v) / (span * 3600) if span > 0 else 0
            flag = "" if rate > 0.83 else "   <-- GAPPY"
            print(f"    {k:>13}: {len(v):>7,} seconds, {span:>6.2f} h, "
                  f"{100*rate:>5.1f}% coverage{flag}")
    return acc


def load_trades(data_dir):
    """ticker -> [(sec, yes_price_dollars, size, taker_side)]"""
    out = defaultdict(list)
    for m in read_jsonl_gz(os.path.join(data_dir, "trade", "*.jsonl.gz")):
        d = m.get("msg") or {}
        tk = d.get("market_ticker") or d.get("ticker")
        if not tk:
            continue
        # yes_price_dollars is dollars; yes_price is CENTS (integer 1..99).
        # Never infer the unit from magnitude: a 1-cent price is indistinguishable
        # from $1.00 that way, and guessing wrong drops the whole deep tail.
        if d.get("yes_price_dollars") is not None:
            p = d.get("yes_price_dollars")
            scale = 1.0
        else:
            p = d.get("yes_price")
            scale = 100.0
        if p is None:
            continue
        try:
            p = float(p) / scale
            t = parse_ts(d.get("ts") or d.get("created_time")) or \
                (m.get("_rx_ms", 0) / 1000.0)
            sz = float(d.get("count") or d.get("count_fp") or 1)
        except (TypeError, ValueError):
            continue
        if t and 0 < p < 1:
            out[tk].append((t, p, sz, str(d.get("taker_side", "")).lower()))
    for v in out.values():
        v.sort()
    return out


# ===========================================================================
# the variance engine -- no iid assumption
# ===========================================================================
def autocov_increments(ticks, max_lag=5, sample=200_000):
    """gamma(h) for h=0..max_lag of one-second index increments, as a fraction
    of gamma(0). Estimated on contiguous runs only."""
    secs = sorted(ticks)
    d = []
    for a, b in zip(secs, secs[1:]):
        if b - a == 1:
            d.append(ticks[b][0] - ticks[a][0])
        else:
            d.append(None)
    runs, cur = [], []
    for x in d:
        if x is None:
            if len(cur) > 50:
                runs.append(cur)
            cur = []
        else:
            cur.append(x)
    if len(cur) > 50:
        runs.append(cur)
    if not runs:
        return None
    allr = [x for r in runs for x in r][:sample]
    if len(allr) < 200:
        return None
    m = mean(allr)
    g0 = sum((x - m) ** 2 for x in allr) / len(allr)
    if g0 <= 0:
        return None
    g = [1.0]
    for h in range(1, max_lag + 1):
        s, n = 0.0, 0
        for r in runs:
            for i in range(len(r) - h):
                s += (r[i] - m) * (r[i + h] - m)
                n += 1
        g.append((s / n) / g0 if n > 20 else 0.0)
    return {"g0": g0, "rho": g, "n": len(allr)}


def settle_weights(tau):
    """w_j for the tau seconds before close: how many not-yet-printed settle
    ticks the innovation at that second feeds into.

    Depends only on tau = close - t, never on absolute time, which is what
    makes the variance memoizable. Closed form, no inner scan:
      the last N_AVG seconds carry weights N_AVG..1 counting down to close;
      anything earlier feeds all the live ticks equally.
    """
    if tau <= 0:
        return []
    live = min(tau, N_AVG)                  # settle ticks still in the future
    flat = max(0, tau - N_AVG)              # seconds before the window opens
    return [live] * flat + list(range(live, 0, -1))


_VAR_CACHE = {}


def cond_var_tau(tau, g0, rho):
    """Var(settle | tau seconds to close) under autocovariance rho."""
    key = (tau, len(rho), tuple(round(x, 9) for x in rho))
    hit = _VAR_CACHE.get(key)
    if hit is None:
        w = settle_weights(tau)
        if not w:
            return 0.0
        tot = rho[0] * sum(x * x for x in w)
        for h in range(1, len(rho)):
            if h < len(w):
                tot += 2 * rho[h] * sum(w[i] * w[i + h]
                                        for i in range(len(w) - h))
        hit = tot / (N_AVG ** 2)
        _VAR_CACHE[key] = hit
    return g0 * hit


def cond_var(t, close_sec, g0, rho):
    return cond_var_tau(close_sec - t, g0, rho)


def cond_mean(t, close_sec, ticks, spot):
    """Conditional mean of the 60-print settlement average.

    n_locked_expected seconds of the window are already in the past; only
    len(locked) of them were actually observed. Summing the observed ones and
    then reserving r = N_AVG - n_locked_expected slots for the future
    double-counts nothing but UNDER-counts the past: a 10% tick shortfall on a
    $100k index drops mu by thousands of dollars, which reads as a colossal
    model-vs-market edge and is entirely a data artifact. Rescale the observed
    sum up to the number of seconds it is standing in for.
    """
    lo = close_sec - N_AVG + 1
    locked = [ticks[s][0] for s in range(lo, min(t, close_sec) + 1)
              if s in ticks]
    n_locked_expected = max(0, min(t, close_sec) - lo + 1)
    if n_locked_expected and len(locked) < n_locked_expected * 0.9:
        return None                     # too many missing ticks to trust
    r = N_AVG - n_locked_expected
    locked_sum = (sum(locked) * (n_locked_expected / len(locked))
                  if locked else 0.0)
    return (locked_sum + r * spot) / N_AVG


# ===========================================================================
# scoring
# ===========================================================================
def snap_to_tick(p):
    """Kalshi's tapered_deci_cent grid: 0.1c below $0.10 and above $0.90,
    1.0c in between. The market CANNOT quote off this grid, so a continuous
    model must be snapped to it before any head-to-head scoring. Skipping this
    gives the model a systematic log-loss edge worth t=10 against a book that
    is in fact perfectly fair -- measured, not hypothesised."""
    step = 0.001 if (p > 0.90 or p < 0.10) else 0.01
    q = round(p / step) * step
    return min(max(q, 0.001), 0.999)


def logloss(p, y, eps=1e-6):
    p = min(max(p, eps), 1 - eps)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def clustered_mean(pairs):
    """pairs = [(value, cluster_key)]. One observation per cluster."""
    by = defaultdict(list)
    for v, k in pairs:
        by[k].append(v)
    obs = [mean(v) for v in by.values()]
    n = len(obs)
    if n < 10:
        return None
    m, sd = mean(obs), pstdev(obs)
    se = sd / math.sqrt(n) if sd > 0 else float("inf")
    return {"mean": m, "n": n, "se": se, "t": m / se if se > 0 else 0.0}


# ===========================================================================
# synthetic end-to-end -- writes fake collector files, runs the whole pipeline
# ===========================================================================
def make_synth(tmp, n_windows=140, sigma=6.0, rho1=0.0, seed=5,
               book_mode="fair", book_sigma_mult=1.0, book_lag=0,
               index_id="BRTI", series="KXBTC15M", s0=80_000.0, tag="a"):
    """book_mode: 'fair'  -> market quotes the true model (null: no edge)
                  'stale' -> market uses a sigma that is wrong by a constant
                  'spot'  -> market ignores the averaging (delta = 1, not r/60)

    index_id/series/s0/tag exist so the same generator can lay down a SECOND
    asset in the same directory at a different price level. One index can never
    catch a pipeline that scores every market against whichever index it
    happened to load first.
    """
    rnd = random.Random(seed)
    os.makedirs(os.path.join(tmp, "cfbenchmarks_value"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "trade"), exist_ok=True)
    t0 = 1_760_000_000
    S = s0
    ticks, markets, trades = {}, [], []
    prev_d = 0.0
    total = n_windows * 900 + 120
    for k in range(total):
        e = rnd.gauss(0, sigma)
        d = e + rho1 * prev_d
        prev_d = e
        S += d
        ticks[t0 + k] = S
    tick_view = {x: (ticks[x], None) for x in ticks}   # build ONCE, not per trade
    for w in range(n_windows):
        open_s = t0 + 60 + w * 900
        close_s = open_s + 900
        if close_s not in ticks:
            break
        strike = mean(ticks[s] for s in range(open_s - 59, open_s + 1))
        settle = mean(ticks[s] for s in range(close_s - 59, close_s + 1))
        tk = f"{series}-SYN{w:04d}"
        markets.append({"ticker": tk, "series": series, "strike": strike,
                        "settle": settle, "close": float(close_s),
                        "result": 1.0 if settle >= strike else 0.0})
        g0 = sigma * sigma * (1 + rho1 * rho1)
        for ttc in TTC_GRID:
            s = close_s - ttc
            if s <= open_s or s not in ticks:
                continue
            # 'lag' backdates ONLY the book's view of spot, not the clock
            spot = ticks[max(s - book_lag, open_s)] if book_lag else ticks[s]
            mu = cond_mean(s, close_s, tick_view, spot)
            if mu is None:
                continue
            v = cond_var(s, close_s, g0, [1.0, rho1 / (1 + rho1 * rho1)])
            if v <= 0:
                continue
            if book_mode == "spot":
                # market prices as if the whole 60s average moved with spot
                mu_b = spot
                v_b = v
            elif book_mode == "stale":
                mu_b, v_b = mu, v * (book_sigma_mult ** 2)
            else:
                mu_b, v_b = mu, v
            p = snap_to_tick(1 - ND.cdf((strike - mu_b) / math.sqrt(max(v_b, 1e-9))))
            trades.append({"msg": {"market_ticker": tk,
                                   "yes_price_dollars": p,
                                   "ts": s, "count": 10,
                                   "taker_side": "yes"}, "type": "trade"})
    with gzip.open(os.path.join(tmp, "cfbenchmarks_value",
                                f"20260825T00{tag}.jsonl.gz"), "wt") as f:
        for s in sorted(ticks):
            f.write(json.dumps({"type": "cfbenchmarks_value",
                                "msg": {"index_id": index_id,
                                        "data": json.dumps(
                                            {"time": s * 1000,
                                             "value": ticks[s]})}}) + "\n")
    with gzip.open(os.path.join(tmp, "trade",
                                f"20260825T00{tag}.jsonl.gz"), "wt") as f:
        for t in trades:
            f.write(json.dumps(t) + "\n")
    return markets


def run_pipeline(data_dir, markets, verbose=True):
    """Score every market against the index that actually settles it.

    This used to loop over indices, score ALL markets against whichever index
    came out of the dict first, and break. On the one-index synthetic that is
    invisible; on real data it prices eleven series off BRTI, which is not a
    subtle bias -- an XRP contract scored against a bitcoin index produces
    |p_model - p_mkt| near 1 on essentially every row, and score() would have
    read that as the largest edge this project has ever found.
    """
    idx = load_index(data_dir, verbose=verbose)
    tr = load_trades(data_dir)
    out = {}
    by_index = defaultdict(list)
    unmatched = 0
    for m in markets:
        iid = SERIES_TO_INDEX.get(m.get("series") or
                                  str(m.get("ticker", "")).split("-")[0])
        if iid is None or iid not in idx:
            unmatched += 1
            continue
        by_index[iid].append(m)
    if unmatched and verbose:
        print(f"  {unmatched} market(s) had no matching index feed -- skipped")
    out["unmatched_markets"] = unmatched
    out["autocov_by_index"] = {}
    rows = []
    for index_id, ticks in sorted(idx.items(), key=lambda x: -len(x[1])):
        ac = autocov_increments(ticks)
        if not ac:
            continue
        out["autocov_by_index"][index_id] = ac
        # first (largest) index keeps the old key so existing callers still read
        out.setdefault("autocov", ac)
        g0, rho = ac["g0"], ac["rho"]
        for m in by_index.get(index_id, ()):
            close_s = int(round(m["close"]))
            tape = tr.get(m["ticker"], [])
            if not tape:
                continue
            for ttc in TTC_GRID:
                cut = close_s - ttc
                # last print at or before the gridpoint -- the price a taker
                # would have seen at that moment
                prev = None
                for (t, p, sz, side) in tape:
                    if t <= cut:
                        prev = (t, p)
                    else:
                        break
                if prev is None:
                    continue
                if cut - prev[0] > 60:        # quote too stale to be the market
                    continue
                ts = cut
                if ts not in ticks:
                    continue
                mu = cond_mean(ts, close_s, ticks, ticks[ts][0])
                if mu is None:
                    continue
                v = cond_var(ts, close_s, g0, rho)
                if v <= 0:
                    continue
                pm = snap_to_tick(1 - ND.cdf((m["strike"] - mu) / math.sqrt(v)))
                rows.append({"tk": m["ticker"], "close": close_s, "ttc": ttc,
                             "p_model": pm, "p_mkt": prev[1], "y": m["result"],
                             "spot": ticks[ts][0], "strike": m["strike"],
                             "index_id": index_id})
    out["rows"] = rows
    return out


def fee_per_contract(p):
    """Kalshi quadratic taker fee, large-order limit (the per-contract ceil
    rounding vanishes at size)."""
    return 0.07 * p * (1 - p)


def score(rows, label, edge_min=0.02, verbose=True):
    """Three metrics on the same clustered observations.

    log-loss  unbounded; an overconfident book fails as rare huge losses, so
              this has the right sign but terrible power. Reported, not trusted.
    Brier     bounded, low variance -> the statistical test.
    net P&L   take the model's side when it disagrees by more than edge_min,
              pay the real quadratic fee. The decision metric.
    """
    if len(rows) < 50:
        if verbose:
            print(f"  {label}: only {len(rows)} observations")
        return None
    ll = clustered_mean([(logloss(r["p_mkt"], r["y"]) -
                          logloss(r["p_model"], r["y"]), r["close"]) for r in rows])
    br = clustered_mean([((r["p_mkt"] - r["y"]) ** 2 -
                          (r["p_model"] - r["y"]) ** 2, r["close"]) for r in rows])
    if ll is None or br is None:
        # 50 rows is not 10 clusters. A single close time sampled at every
        # gridpoint clears the row gate and gives one independent observation;
        # clustered_mean correctly refuses it, and unpacking its None here was
        # a TypeError, not a result.
        nclust = len({r["close"] for r in rows})
        if verbose:
            print(f"  {label}: {len(rows)} observations but only "
                  f"{nclust} close-time cluster(s) -- need 10")
        return None
    pnl_rows = []
    for r in rows:
        d = r["p_model"] - r["p_mkt"]
        if abs(d) < edge_min:
            continue
        if d > 0:                                  # model says cheap -> buy yes
            entry, win = r["p_mkt"], r["y"]
        else:                                      # model says rich -> buy no
            entry, win = 1 - r["p_mkt"], 1 - r["y"]
        tick = 0.001 if (entry > 0.90 or entry < 0.10) else 0.01
        entry = min(entry + tick, 0.999)           # lift the offer, never the mid
        pnl_rows.append((((1 - entry) if win else -entry)
                         - fee_per_contract(entry), r["close"]))
    pn = clustered_mean(pnl_rows) if len(pnl_rows) >= 50 else None
    if verbose:
        v = ("MODEL BEATS MARKET" if br["t"] > 3 else
             "market beats model" if br["t"] < -3 else "tie")
        print(f"  {label:>20}{br['n']:>7}{len(rows):>9,}"
              f"{ll['mean']:>+10.4f}{ll['t']:>7.1f}"
              f"{br['mean']:>+10.5f}{br['t']:>7.1f}"
              + (f"{100*pn['mean']:>+9.2f}c{pn['t']:>7.1f}" if pn
                 else f"{'--':>16}")
              + f"   {v}")
    return {"t": br["t"], "ll_t": ll["t"], "brier": br["mean"],
            "pnl": pn["mean"] if pn else None,
            "pnl_t": pn["t"] if pn else None, "clusters": br["n"]}


def selftest():
    import tempfile, shutil
    print("=" * 78)
    print("SELF-TEST -- end to end, on synthetic collector files")
    print("=" * 78)
    print("  Three synthetic markets. The model is the SAME in all three; only")
    print("  the simulated book changes. The harness must find an edge exactly")
    print("  when one was planted, and none when the book is fair.\n")
    print(f"  {'book':>20}{'clstr':>7}{'obs':>9}{'dLogLoss':>10}{'t':>7}"
          f"{'dBrier':>10}{'t':>7}{'net P&L':>10}{'t':>7}   verdict")
    fails = []
    for label, kw in (("fair (null)", dict(book_mode="fair")),
                      ("fair, 2nd null", dict(book_mode="fair", seed=23)),
                      ("sigma 40% too low", dict(book_mode="stale",
                                                 book_sigma_mult=0.6)),
                      ("quote 20s stale", dict(book_mode="fair", book_lag=20)),
                      ("ignores averaging", dict(book_mode="spot"))):
        tmp = tempfile.mkdtemp()
        try:
            kw = dict(kw)
            sd = kw.pop("seed", 17)
            mk = make_synth(tmp, n_windows=1500, seed=sd, **kw)
            res = run_pipeline(tmp, mk, verbose=False)
            r = score(res.get("rows", []), label)
            if label.startswith("fair,") or label.startswith("fair ("):
                if r and abs(r["t"]) > 3:
                    fails.append(f"found an edge (t={r['t']:.1f}) against a FAIR book")
            if label.startswith("sigma") and r and r["t"] < 3:
                fails.append(f"missed a planted sigma error (t={r['t']:.1f})")
            if label.startswith("ignores") and r and r["t"] < 3:
                fails.append(f"missed a planted averaging error (t={r['t']:.1f})")
            if label.startswith("quote") and r and r["t"] < 3:
                fails.append(f"missed a planted stale quote (t={r['t']:.1f})")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print("\n  TWO ASSETS, one directory (the wrong-index check)")
    print("  Both books are fair. BTC settles off BRTI at $80k, ETH off")
    print("  ETHUSD_RTI at $3k. A pipeline that prices ETH against BRTI reads")
    print("  p_model=1 on every row and calls it the edge of the century.")
    tmp = tempfile.mkdtemp()
    try:
        mk = make_synth(tmp, n_windows=400, seed=17, book_mode="fair")
        mk += make_synth(tmp, n_windows=400, seed=41, book_mode="fair",
                         index_id="ETHUSD_RTI", series="KXETH15M",
                         s0=3_000.0, sigma=0.22, tag="b")
        res = run_pipeline(tmp, mk, verbose=False)
        rows = res.get("rows", [])
        seen = sorted({r["index_id"] for r in rows})
        print(f"  {'indices scored':>16}   {', '.join(seen) or '(none)'}")
        if len(seen) < 2:
            fails.append(f"only scored {seen} -- the second asset was dropped")
        for iid, lbl in (("BRTI", "BTC vs BRTI"),
                         ("ETHUSD_RTI", "ETH vs ETHUSD_RTI")):
            sub = [r for r in rows if r["index_id"] == iid]
            r = score(sub, lbl) if sub else None
            if r and abs(r["t"]) > 3:
                fails.append(f"{lbl}: edge t={r['t']:.1f} against a FAIR book")
        # the direct assertion: every market scored against ITS own index
        bad = [r for r in rows
               if SERIES_TO_INDEX.get(r["tk"].split("-")[0]) != r["index_id"]]
        if bad:
            fails.append(f"{len(bad)} row(s) scored against the wrong index")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n  AUTOCOVARIANCE recovery (the no-iid-assumption check)")
    print(f"  {'injected rho1':>16}{'recovered':>12}")
    for rho1 in (0.0, -0.3, 0.3):
        tmp = tempfile.mkdtemp()
        try:
            make_synth(tmp, n_windows=60, rho1=rho1, seed=31)
            idx = load_index(tmp, verbose=False)
            ac = autocov_increments(idx["BRTI"])
            got = ac["rho"][1] if ac else float("nan")
            want = rho1 / (1 + rho1 * rho1)
            print(f"  {rho1:>16.2f}{got:>12.3f}   (theory {want:+.3f})")
            if abs(got - want) > 0.06:
                fails.append(f"autocovariance recovery off at rho1={rho1}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- the harness finds planted edges, reports none")
    print("against a fair book, and recovers index autocorrelation.")
    return True


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    idx = load_index(a.data)
    if not idx:
        print("\n  No cfbenchmarks_value data. That feed is the whole project --")
        print("  see RUNBOOK 'API traps': the channel needs param `index_ids`,")
        print("  and a {'type':'subscribed'} reply is NOT success.")
        return

    print("\n" + "=" * 78)
    print("VARIANCE CURVE -- is BRTI a random walk at one-second scale?")
    print("=" * 78)
    print(f"  {'index':>13}{'n':>10}{'sd/s':>12}" +
          "".join(f"{'rho'+str(h):>9}" for h in range(1, 6)))
    for k, ticks in sorted(idx.items(), key=lambda x: -len(x[1]))[:6]:
        ac = autocov_increments(ticks)
        if not ac:
            continue
        print(f"  {k:>13}{ac['n']:>10,}{math.sqrt(ac['g0']):>12.4f}" +
              "".join(f"{ac['rho'][h]:>9.3f}" for h in range(1, 6)))
    print("\n  rho1 near 0  -> random walk; the iid sigma model is safe.")
    print("  rho1 < 0     -> mids bounce; iid OVERstates true variance.")
    print("  rho1 > 0     -> smoothed/trending; iid UNDERstates it.")
    print("  Any non-zero value here invalidates a plain sigma^2*k model, which")
    print("  is why this script propagates gamma instead.")
    print("\n  Next: pull settled markets for outcomes and run the head-to-head.")
    print("  That needs markets that CLOSED inside the recorded span -- run")
    print("  chain.py first to confirm the contract, then re-run this.")


if __name__ == "__main__":
    main()
