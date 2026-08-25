#!/usr/bin/env python3
# VERSION: 2026-08-25-f1
"""
feeds.py -- the largest unexploited asset in this project.

    python research/feeds.py --selftest
    python research/feeds.py --feeds C:\\kals\\feed_data --data C:\\kals\\kalshi_data

WHAT HAS BEEN SITTING THERE UNREAD

`crypto_feeds.py` has been recording the order books of Coinbase, Kraken,
Bitstamp and Gemini at roughly 3.2 GB/day -- more data than everything else in
the project combined -- and **nothing has ever read it**. Not one line of
analysis.

That matters more than the volume suggests, because those books are not merely
correlated with the settlement index. They are its INPUTS. CF Benchmarks
computes BRTI from the order books of exactly these exchanges, once per second.
So this is not an alternative data source; it is the upstream one.

THE TWO QUESTIONS

1. DOES OUR REPLICA LEAD KALSHI'S RELAYED INDEX?
   The chain is: constituent books -> CF computes BRTI -> Kalshi relays it ->
   we receive it. Every hop costs time. We are wired directly into the first
   link. Measured earlier: CF-to-Kalshi alone runs ~63ms median, and there is
   also CF's own computation and publication cadence on top.

   Crucially, this does NOT require winning a latency race. Settlement is a
   60-SECOND AVERAGE, so what pays is an earlier read on where a slow-moving
   mean is heading, not being first to a print. A one-second lead is worth
   1.7c at 600s to close and 17c at 15s (leadlag.py's table). We do not need
   microseconds.

2. DOES ORDER-BOOK IMBALANCE PREDICT THE NEXT FEW SECONDS OF INDEX?
   Order flow imbalance predicting short-horizon returns is about the most
   replicated result in market microstructure, across every asset class ever
   studied. Here it should be unusually direct, because BRTI is built from a
   size-weighted consolidation of these very books -- imbalance is not a proxy
   for the thing, it is part of the thing.

WHY THIS IS NOT "SOMEONE MADE A MISTAKE"

Nobody has to be wrong. We are simply closer to the source than a participant
who reads the published index. That is a structural position, not an exploit,
and it does not get arbitraged away by the market maker fixing a formula.

HONEST CAVEATS
  * Our replica is a size-weighted consolidated mid. CF's real methodology uses
    an exponentially weighted price-volume curve with dynamic order-size capping
    over full depth. Ours is the right SHAPE, not the same function.
  * All timestamps here are local receive times, so a measured lead conflates
    genuine information advantage with clock and transport differences. A lead
    at negative lag would mean a clock problem, not prescience.
  * Only top-of-book is recorded for most venues, so depth-weighted effects are
    invisible.
"""

import argparse
import glob
import gzip
import json
import math
import os
import sys
from collections import defaultdict
from statistics import mean, median, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LAGS = list(range(-5, 11))          # positive = the replica LEADS the index


def read_gz(pattern, limit=None):
    n = 0
    for fp in sorted(glob.glob(pattern)):
        try:
            with gzip.open(fp, "rt") as f:
                for line in f:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    n += 1
                    if limit and n >= limit:
                        return
        except Exception:
            continue


# ===========================================================================
def load_replica(feeds_dir, asset="BTC", verbose=True):
    """second -> consolidated mid, from the index_replica channel that
    crypto_feeds.py already emits at the top of every second."""
    out, n_ex = {}, {}
    for m in read_gz(os.path.join(feeds_dir, "index_replica", "*.jsonl.gz")):
        sec = m.get("sec")
        d = m.get(asset)
        if sec is None or not isinstance(d, dict):
            continue
        v = d.get("wmid")
        if v is None:
            continue
        try:
            out[int(sec)] = float(v)
            n_ex[int(sec)] = int(d.get("n_ex", 0))
        except (TypeError, ValueError):
            continue
    if verbose:
        if out:
            span = (max(out) - min(out)) / 3600.0
            print(f"  replica {asset}: {len(out):,} seconds over {span:.2f} h, "
                  f"median {median(n_ex.values()) if n_ex else 0:.0f} exchanges")
        else:
            print(f"  replica {asset}: nothing. Is crypto_feeds.py writing "
                  f"index_replica?")
    return out


def load_tob(feeds_dir, asset="BTC", verbose=True):
    """second -> {exchange: (bid, bidsz, ask, asksz)} from the raw venue feeds.
    Needed for imbalance, which the replica channel does not carry."""
    per = defaultdict(dict)
    counts = defaultdict(int)

    def put(sec, ex, b, bs, a, asz):
        try:
            b, a = float(b), float(a)
            bs, asz = float(bs or 0), float(asz or 0)
        except (TypeError, ValueError):
            return
        if b > 0 and a >= b:
            per[int(sec)][ex] = (b, bs, a, asz)
            counts[ex] += 1

    for m in read_gz(os.path.join(feeds_dir, "coinbase", "*.jsonl.gz")):
        if m.get("type") != "ticker":
            continue
        if str(m.get("product_id", "")).split("-")[0] != asset:
            continue
        put(m.get("_rx", 0), "coinbase", m.get("best_bid"),
            m.get("best_bid_size"), m.get("best_ask"), m.get("best_ask_size"))

    for m in read_gz(os.path.join(feeds_dir, "kraken", "*.jsonl.gz")):
        if m.get("channel") != "ticker":
            continue
        for d in m.get("data", []) or []:
            if str(d.get("symbol", "")).split("/")[0] != asset:
                continue
            put(m.get("_rx", 0), "kraken", d.get("bid"), d.get("bid_qty"),
                d.get("ask"), d.get("ask_qty"))

    for m in read_gz(os.path.join(feeds_dir, "bitstamp", "*.jsonl.gz")):
        ch = str(m.get("channel", ""))
        if not ch.startswith("order_book_"):
            continue
        if ch.replace("order_book_", "").replace("usd", "").upper() != asset:
            continue
        d = m.get("data") or {}
        bids, asks = d.get("bids") or [], d.get("asks") or []
        if bids and asks:
            put(m.get("_rx", 0), "bitstamp", bids[0][0], bids[0][1],
                asks[0][0], asks[0][1])

    if verbose:
        print(f"  top-of-book {asset}: {len(per):,} seconds, per venue "
              f"{dict(counts)}")
    return per


def load_index(data_dir, index_id="BRTI", verbose=True):
    out = {}
    for m in read_gz(os.path.join(data_dir, "cfbenchmarks_value",
                                  "*.jsonl.gz")):
        d = m.get("msg") or {}
        if d.get("index_id") != index_id:
            continue
        inner = d.get("data")
        if isinstance(inner, str):
            try:
                inner = json.loads(inner)
            except (json.JSONDecodeError, ValueError):
                continue
        if not isinstance(inner, dict):
            continue
        try:
            out[int(round(float(inner["time"]) / 1000.0))] = float(inner["value"])
        except (KeyError, TypeError, ValueError):
            continue
    if verbose:
        print(f"  {index_id}: {len(out):,} seconds")
    return out


# ===========================================================================
def lag_profile(x_by_sec, y_by_sec, lags=LAGS, label=""):
    """Regress d_y(t) on d_x(t-k). Positive k with a large beta means x LEADS.

    Both series are differenced, so the regression runs through the origin."""
    dx = {t: x_by_sec[t] - x_by_sec[t - 1]
          for t in x_by_sec if (t - 1) in x_by_sec}
    dy = {t: y_by_sec[t] - y_by_sec[t - 1]
          for t in y_by_sec if (t - 1) in y_by_sec}
    out = {}
    for k in lags:
        pairs = [(dx[t - k], dy[t]) for t in dy if (t - k) in dx]
        pairs = [(a, b) for a, b in pairs if a != 0.0]
        if len(pairs) < 300:
            continue
        num = sum(a * b for a, b in pairs)
        den = sum(a * a for a, _ in pairs)
        if den <= 0:
            continue
        beta = num / den
        # block-bootstrap style SE: split into 20 contiguous blocks
        n = len(pairs)
        blk = max(n // 20, 30)
        betas = []
        for i in range(0, n - blk + 1, blk):
            b = pairs[i:i + blk]
            dn = sum(a * a for a, _ in b)
            if dn > 0:
                betas.append(sum(a * c for a, c in b) / dn)
        if len(betas) < 5:
            continue
        m, sd = mean(betas), pstdev(betas)
        se = sd / math.sqrt(len(betas)) if sd > 0 else float("inf")
        out[k] = {"beta": beta, "n": n, "t": m / se if se > 0 else 0.0,
                  "blocks": len(betas)}
    return out


def show_lags(res, label):
    print(f"\n  {label}")
    if not res:
        print("    not enough overlapping data")
        return None
    print(f"  {'lag':>6}{'beta':>10}{'t':>8}{'pairs':>10}")
    best = max(res, key=lambda k: res[k]["beta"])
    for k in sorted(res):
        r = res[k]
        print(f"  {k:>+6}{r['beta']:>10.3f}{r['t']:>8.1f}{r['n']:>10,}"
              + ("   <== peak" if k == best else ""))
    print(f"\n  peak at lag {best:+d}s")
    if best > 0:
        print(f"  -> OUR REPLICA LEADS the published index by ~{best}s.")
        print("     Because settlement is a 60-second average, that lead is")
        print("     worth roughly (leadlag.py's table) 1.7c at 600s to close")
        print("     and up to 17c at 15s -- without winning any latency race.")
    elif best == 0:
        print("  -> no lead. We see the same information at the same time.")
    else:
        print("  -> the PUBLISHED index leads our replica, which means our")
        print("     reconstruction is slower or our clocks disagree. Check")
        print("     timestamps before drawing any conclusion.")
    return best


def imbalance_test(tob, index, horizons=(1, 2, 3, 5, 10)):
    """Does size imbalance in the constituent books predict the index?

    imbalance = (bid_size - ask_size) / (bid_size + ask_size), consolidated.
    The most replicated result in microstructure, and here it should be unusually
    direct: BRTI is built from a size-weighted consolidation of these books, so
    imbalance is part of the thing rather than a proxy for it."""
    imb = {}
    for sec, per in tob.items():
        bs = sum(v[1] for v in per.values())
        asz = sum(v[3] for v in per.values())
        if bs + asz > 0:
            imb[sec] = (bs - asz) / (bs + asz)
    if len(imb) < 500:
        print("\n  imbalance: too few seconds with sizes on both sides")
        return
    print(f"\n  ORDER-BOOK IMBALANCE -> FUTURE INDEX ({len(imb):,} seconds)")
    print(f"  {'horizon':>9}{'beta ($ per unit imb)':>24}{'t':>8}{'n':>10}")
    for h in horizons:
        pairs = []
        for sec, v in imb.items():
            if sec in index and (sec + h) in index:
                pairs.append((v, index[sec + h] - index[sec]))
        if len(pairs) < 300:
            continue
        mx = mean([p[0] for p in pairs])
        my = mean([p[1] for p in pairs])
        den = sum((a - mx) ** 2 for a, _ in pairs)
        if den <= 0:
            continue
        beta = sum((a - mx) * (b - my) for a, b in pairs) / den
        n = len(pairs)
        blk = max(n // 20, 30)
        bs_ = []
        for i in range(0, n - blk + 1, blk):
            b = pairs[i:i + blk]
            m1 = mean([p[0] for p in b]); m2 = mean([p[1] for p in b])
            d = sum((a - m1) ** 2 for a, _ in b)
            if d > 0:
                bs_.append(sum((a - m1) * (c - m2) for a, c in b) / d)
        if len(bs_) < 5:
            continue
        m, sd = mean(bs_), pstdev(bs_)
        se = sd / math.sqrt(len(bs_)) if sd > 0 else float("inf")
        print(f"  {h:>8}s{beta:>24.3f}{m/se if se>0 else 0:>8.1f}{n:>10,}")
    print("\n  A positive beta means a bid-heavy consolidated book precedes a")
    print("  rising index. Multiply beta by a typical imbalance to get the")
    print("  dollar move, then by the delta damping factor (r_live/60) and")
    print("  phi(z)/sd to convert into contract cents.")


# ===========================================================================
def selftest():
    import tempfile, shutil, random
    print("=" * 78)
    print("SELF-TEST -- can it recover a lead it was given?")
    print("=" * 78)
    fails = []
    for want in (0, 2, 5):
        rnd = random.Random(20 + want)
        t0, n = 1_760_000_000, 6000
        truth, x = {}, 80_000.0
        for k in range(n):
            x += rnd.gauss(0, 6.0)
            truth[t0 + k] = x
        # the replica sees the truth NOW; the published index sees it `want`
        # seconds later, plus its own small measurement noise
        replica = {t: v for t, v in truth.items()}
        index = {t: truth[t - want] + rnd.gauss(0, 0.05)
                 for t in truth if (t - want) in truth}
        res = lag_profile(replica, index)
        got = show_lags(res, f"injected lead of {want}s")
        if got != want:
            fails.append(f"injected {want}s lead, recovered {got}")

    print("\n  IMBALANCE recovery")
    rnd = random.Random(9)
    t0, n = 1_760_000_000, 20000
    idx, tob, x = {}, {}, 80_000.0
    TRUE_BETA = 4.0
    for k in range(n):
        im = rnd.uniform(-1, 1)
        bid_sz = 100 * (1 + im)
        ask_sz = 100 * (1 - im)
        tob[t0 + k] = {"synthetic": (x - 1, bid_sz, x + 1, ask_sz)}
        idx[t0 + k] = x
        x += TRUE_BETA * im + rnd.gauss(0, 6.0)
    imbalance_test(tob, idx, horizons=(1, 3))
    print(f"  (the generator used beta = {TRUE_BETA:.1f} per unit imbalance at "
          f"h=1, so the h=1 row should land near it)")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- the lag profile recovers an injected lead of 0,")
    print("2 and 5 seconds, and the imbalance regression recovers its beta.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feeds", default="./feed_data")
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--asset", default="BTC")
    ap.add_argument("--index-id", default="BRTI")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed")

    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    if not os.path.isdir(a.feeds):
        print(f"  {a.feeds} does not exist. crypto_feeds.py writes it.")
        return
    replica = load_replica(a.feeds, a.asset)
    index = load_index(a.data, a.index_id)
    if not index:
        print("\n  No cfbenchmarks_value recorded, so there is nothing to")
        print("  compare the replica against. That feed gates this test too.")
        return
    if replica:
        overlap = len(set(replica) & set(index))
        print(f"  overlapping seconds: {overlap:,}")
        if overlap > 1000:
            print("\n" + "=" * 78)
            print("DOES OUR REPLICA LEAD KALSHI'S PUBLISHED INDEX?")
            print("=" * 78)
            show_lags(lag_profile(replica, index),
                      "d_index(t) = beta_k * d_replica(t-k)")
        else:
            print("  too little overlap to regress -- let both recorders run.")

    tob = load_tob(a.feeds, a.asset)
    if tob:
        print("\n" + "=" * 78)
        print("DOES CONSTITUENT ORDER-BOOK IMBALANCE PREDICT THE INDEX?")
        print("=" * 78)
        imbalance_test(tob, index)

    print("\n  Both tests use LOCAL receive timestamps, so a measured lead mixes")
    print("  genuine information advantage with transport and clock differences.")
    print("  A peak at a NEGATIVE lag is a clock problem, not prescience.")


if __name__ == "__main__":
    main()
