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
import zlib
import math
import os
import sys
from collections import defaultdict
from statistics import stdev, mean, median, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gzsalvage import iter_lines as salvage_lines   # noqa: E402
from tdist import p_two_sided, crit                       # noqa: E402

LAGS = list(range(-5, 11))          # positive = the replica LEADS the index


def read_gz(pattern, limit=None):
    n = 0
    for fp in sorted(glob.glob(pattern)):
        try:
            for line in salvage_lines(fp):
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    n += 1
                    if limit and n >= limit:
                        return
        except (OSError, EOFError, zlib.error, gzip.BadGzipFile):
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

    # GEMINI. 1,538,050 recorded messages were being silently dropped: this
    # loader covered coinbase, kraken and bitstamp only, so the imbalance
    # regression and the index replica were built from DIFFERENT venue sets.
    # Its top_of_book stream emits incremental `change` events, so bid and ask
    # have to be carried forward the way crypto_feeds.py does when it builds
    # the replica.
    g_bid = g_ask = None
    for m in read_gz(os.path.join(feeds_dir, "gemini", "*.jsonl.gz")):
        for e in m.get("events", []) or []:
            if e.get("type") == "change" and e.get("side") in ("bid", "ask"):
                if e["side"] == "bid":
                    g_bid = (e.get("price"), e.get("remaining"))
                else:
                    g_ask = (e.get("price"), e.get("remaining"))
        if g_bid and g_ask:
            put(m.get("_rx", 0), "gemini", g_bid[0], g_bid[1],
                g_ask[0], g_ask[1])

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
        # sorted(dy), not dy. A dict iterates in INSERTION order, which is the
        # order the feed files happened to be read in -- so the "contiguous
        # blocks" below were contiguous in nothing. A block bootstrap whose
        # blocks are not time-contiguous cannot absorb serial dependence; it
        # collapses to an iid standard error, which is too small, which is a t
        # that is too large. That is the exact shape of every fake edge in
        # this project's history.
        pairs = [(dx[t - k], dy[t]) for t in sorted(dy) if (t - k) in dx]
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
        # stdev, not pstdev: the blocks are a SAMPLE of the process, and the
        # population formula understates the SE by sqrt(B/(B-1)) -- +2.6% on
        # t at 20 blocks, +5.4% at the 10-block floor. Small, but every t in
        # both printed tables carried it.
        m, sd = mean(betas), (stdev(betas) if len(betas) > 1 else 0.0)
        se = sd / math.sqrt(len(betas)) if sd > 0 else float("inf")
        out[k] = {"beta": beta, "n": n, "t": m / se if se > 0 else 0.0,
                  "blocks": len(betas)}
    return out


def show_lags(res, label):
    print(f"\n  {label}")
    if not res:
        print("    not enough overlapping data")
        return None
    # The standard error comes from ~20 blocks, so this is a t on
    # (blocks - 1) degrees of freedom and NOT a z. At |t| = 3 the two-sided
    # p is 0.0074 rather than 0.0027, and at |t| = 4 it is 0.00077 rather
    # than 0.00006 -- twelve times more likely to be noise than it reads.
    # power.py measured the cost of the old reading directly: comparing this
    # column to 1.96 rejects a true null 7.7% of the time, not 5%.
    print(f"  {'lag':>6}{'beta':>10}{'t':>8}{'df':>5}{'p (t)':>10}"
          f"{'pairs':>10}")
    best = max(res, key=lambda k: res[k]["beta"])
    for k in sorted(res):
        r = res[k]
        df = max(r.get("blocks", 20) - 1, 1)
        print(f"  {k:>+6}{r['beta']:>10.3f}{r['t']:>8.1f}{df:>5}"
              f"{p_two_sided(r['t'], df):>10.4f}{r['n']:>10,}"
              + ("   <== peak" if k == best else ""))
    bdf = max(res[best].get("blocks", 20) - 1, 1)
    print(f"\n  peak at lag {best:+d}s   "
          f"|t| for p<0.05 on t({bdf}) is {crit(0.05, bdf):.2f}, "
          f"not 1.96")
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
    print(f"  {'horizon':>9}{'beta ($ per unit imb)':>24}{'t':>8}{'df':>5}"
          f"{'p (t)':>10}{'n':>10}")
    for h in horizons:
        # sorted(imb), not imb. A dict iterates in INSERTION order, which is
        # the order the feed files happened to be read in, so the "contiguous
        # blocks" below were contiguous in nothing and the block bootstrap
        # collapsed to an iid standard error -- too small, so the t is too
        # large. This is the identical defect lag_profile carries a nine-line
        # comment about, in the function next door, and no self-test ever
        # exercised this one.
        pairs = []
        for sec in sorted(imb):
            # imb[sec] is built from the LAST venue message in bucket
            # [sec, sec+1) -- load_tob overwrites on every message and _rx is
            # a local receive stamp -- so a busy venue's entry is dated
            # ~sec+0.99. The index, keyed on CF's own stamp, IS the value at
            # sec. Regressing imb[sec] on index[sec+h]-index[sec] therefore
            # read a predictor observed up to a second INSIDE its own
            # response window: at h=1 that regression was mostly
            # contemporaneous, and the decay across horizons read as
            # "information decay" when it was the overlap shrinking. The
            # predictor is now the PRIOR second's state, which is strictly
            # before the window starts, on every venue and every horizon.
            v = imb.get(sec - 1)
            if v is None:
                continue
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
        t = m / se if se > 0 else 0.0
        # df and a t-based p, like lag_profile: this SE is built from a handful
        # of blocks, so it is a t on (blocks - 1), not a z. It printed a bare
        # t and left the reader to compare it against 1.96.
        df = max(len(bs_) - 1, 1)
        print(f"  {h:>8}s{beta:>24.3f}{t:>8.1f}{df:>5}"
              f"{p_two_sided(t, df):>10.4f}{n:>10,}")
    print(f"\n  |t| for p<0.05 on t({df}) is {crit(0.05, df):.2f}, not 1.96; and")
    print("  the multiple-testing bar in power.py is a NORMAL bar -- on this")
    print("  many degrees of freedom the equivalent is higher still.")
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

    print("\n  BLOCK ORDERING (the bootstrap must not depend on read order)")
    print("  Same data, second series inserted in shuffled order. The blocks")
    print("  the SE is built from are only meaningful if they are contiguous")
    print("  in TIME, so both runs must agree exactly.")
    rnd = random.Random(77)
    t0, n = 1_760_000_000, 6000
    truth, x = {}, 80_000.0
    for k in range(n):
        x += rnd.gauss(0, 6.0)
        truth[t0 + k] = x
    replica = dict(truth)
    idx_sorted = {t: truth[t - 2] + rnd.gauss(0, 0.05)
                  for t in sorted(truth) if (t - 2) in truth}
    keys = list(idx_sorted)
    rnd.shuffle(keys)
    idx_shuffled = {t: idx_sorted[t] for t in keys}
    a_res = lag_profile(replica, idx_sorted)
    b_res = lag_profile(replica, idx_shuffled)
    diffs = [k for k in set(a_res) | set(b_res)
             if k not in a_res or k not in b_res
             or abs(a_res[k]["beta"] - b_res[k]["beta"]) > 1e-12
             or abs(a_res[k]["t"] - b_res[k]["t"]) > 1e-9]
    k2 = 2
    print(f"  {'lag +2 t-stat':>22}   in-order {a_res.get(k2,{}).get('t',0):.2f}"
          f"   shuffled {b_res.get(k2,{}).get('t',0):.2f}"
          f"   lags differing: {len(diffs)}")
    if diffs:
        fails.append(f"lag profile changed when the input dict was reordered "
                     f"at lags {sorted(diffs)} -- the blocks follow read order")

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
