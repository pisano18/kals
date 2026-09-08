#!/usr/bin/env python3
# VERSION: 2026-09-08-sd1
"""
spotdepth.py -- does the SPOT ORDER BOOK bound how far the index can move?

    python research/spotdepth.py --selftest
    python research/spotdepth.py --feeds C:\\kals\\feed_data --data C:\\kals\\kalshi_data

READ-ONLY. Reads feed_data and kalshi_data. Writes ONLY its own cache file.
Places no orders. Touches nothing under C:\\kals.

WHY THIS QUESTION AND NOT ANOTHER ONE

The strategy is a bet that the r settlement prints still unpublished will NOT
average a move of (60/r)*(K_eff - mu) away from spot. Today that probability
comes from a gaussian on a trailing-300s sigma. Over 230M windows of this tape
the index has reached 37-127 sigma, where a gaussian calls 5 extraordinary. So
the tail is the whole risk and the gaussian does not have it.

How far price CAN move in r seconds is not a free parameter. BRTI is computed
by CF Benchmarks from the ORDER BOOKS of Coinbase, Kraken, Bitstamp and
Gemini -- the same books crypto_feeds.py has recorded since 2026-08-25. A
given amount of volume moves price further through a thin book than a thick
one. If that mechanism is visible, depth belongs inside p_flip and the
threshold price should widen and tighten with it in real time.

This is not a correlated alternative signal. It is the INPUT to the thing we
are trying to predict.

WHAT IS BUILT, PER SECOND, FROM DATA STRICTLY AT OR BEFORE t
  (a) DEPTH     touch size per venue and summed, in USD notional and in BTC;
                Bitstamp's 5 kept book levels: cumulative size, the price span
                they cover, and bps of price impact per BTC consumed.
  (b) DISPERSION range / sd / max-adjacent-gap of the per-venue mids, in bps,
                from index_replica's per_ex block (already top-of-second).
  (c) SPREAD    per venue and consolidated (min ask - max bid), in bps. The
                consolidated one goes NEGATIVE when venues cross.
  (d) VOLUME    Coinbase last_size summed per second, signed by `side`, over
                trailing 1s / 60s / 300s windows.
  (e) SIZE/FLOW mean trade size over 300s divided by touch depth -- if one
                normal trade clears the touch, price is one order from moving.
  (i) INCUMBENT sig300, the trailing-300s realised sd of 1-second index log
                returns, in bps. This is what the strategy uses TODAY. A
                factor that only reproduces sig300 is worth nothing.

WHAT IS MEASURED
  1. Spearman rank correlation with |index move over the next r seconds|,
     r in {2,4,9,14,19}. Correlation is the weak version.
  2. The strong version: quintile the factor and report p50/p99/p99.9 of the
     r-second move inside each quintile, plus the RATIO p99(Q5)/p99(Q1).
  3. The lift: how far the conditional tail sits from the unconditional one,
     in percent. That number is the value of the factor.

NO PEEKING, ENFORCED BY CONSTRUCTION
  A feature for second t is venue state carried forward from the last record
  with _rx < t (the last update in second t-1 or earlier), and volume over
  half-open windows [t-W, t). The move is measured strictly after t. The
  self-test plants a step change in depth at a known second and FAILS if the
  cache row for that second already knows about it.

TARGETS
  mv_r = |BRTI(t+r) - BRTI(t)|                  (the direct target)
  am_r = |mean(BRTI(t+1..t+r)) - BRTI(t)|       (what actually settles)
  both in bps of BRTI(t).
"""

import argparse
import glob
import gzip
import json
import math
import os
import random
import sys
import zlib
from array import array
from collections import defaultdict, deque

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

try:
    from gzsalvage import iter_lines as _salvage_lines
except Exception:                                    # pragma: no cover
    _salvage_lines = None

HORIZONS = (2, 4, 9, 14, 19)
CACHE_VERSION = 4

# The cache schema. Order matters: it is the CSV column order.
COLS = [
    "sec", "brti",
    "wmid", "n_ex",
    "dep_bid_usd", "dep_ask_usd", "dep_tot_usd", "dep_min_usd",
    "dep_cb_usd", "dep_kr_usd", "dep_bs_usd", "dep_gm_usd",
    "dep_tot_base",
    "bs_cum5_base", "bs_span5_bps", "bs_impact_bps_per_btc",
    "bs_nlev", "bs_d1bp_base", "bs_d5bp_base", "bs_d10bp_base",
    "disp_range_bps", "disp_sd_bps", "disp_adjgap_bps",
    "spr_cons_bps", "spr_mean_bps", "spr_max_bps",
    "vol1", "buy1", "sell1", "ntr1",
    "vol60", "buy60", "sell60", "ntr60",
    "vol300", "ntr300",
]


# ==========================================================================
# reading
# ==========================================================================
def iter_gz(path):
    """Lines from one gzip file. The NEWEST hour of any channel is being
    appended to right now, so a truncated stream is normal, not an error."""
    if _salvage_lines is not None:
        try:
            for ln in _salvage_lines(path):
                yield ln
            return
        except (OSError, EOFError, zlib.error, gzip.BadGzipFile):
            return
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for ln in fh:
                yield ln
    except (OSError, EOFError, zlib.error, gzip.BadGzipFile):
        return


def hour_keys(feeds, data):
    """Hour stems present in the two mandatory channels. A venue may be
    missing for an hour; index_replica and BRTI may not."""
    def stems(d):
        return {os.path.basename(p).split(".")[0]
                for p in glob.glob(os.path.join(d, "*.jsonl.gz"))}
    a = stems(os.path.join(feeds, "index_replica"))
    b = stems(os.path.join(data, "cfbenchmarks_value"))
    return sorted(a & b)


# ==========================================================================
# per-hour channel readers -> {second: state}
# ==========================================================================
def _obj(ln):
    """json.loads of one salvaged line, or None if it is not an object.

    gzsalvage recovers whatever survives a gzip member broken by a collector
    restart, and the tail of a truncated record can be a bare number. The
    kraken file for 20260906T15 holds lines that read exactly "7", "9", "68"
    and "84547512460261". JSON accepts a scalar at top level, so json.loads
    hands back an int and the next .get raises AttributeError. That killed a
    325-hour build at hour ~250 with 809,369 rows already written, so the
    type is checked here once instead of trusted six times.
    """
    try:
        m = json.loads(ln)
    except (json.JSONDecodeError, ValueError):
        return None
    return m if isinstance(m, dict) else None


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def read_coinbase(path, asset="BTC"):
    """-> (tob_by_sec, trades_by_sec)
    tob_by_sec[s]    = (bid, bidsz, ask, asksz) LAST seen inside second s
    trades_by_sec[s] = (vol, buyvol, sellvol, ntrades) during [s, s+1)

    VOLUME SOURCE, decided by measurement. `volume_24h` is a ROLLING 24-hour
    figure, so its change over an hour is (this hour) minus (the same hour
    yesterday). On 2026-09-06T12 it read 4.16 BTC against 71.38 BTC of summed
    `last_size` -- a factor of 17. The delta is therefore useless as a volume
    measure and `last_size` is what is summed.

    SIGN CONVENTION, measured not assumed. On that same hour, prints with
    side=="buy" sat nearer the ask 4504 times against 348 nearer the bid, and
    carried a mean price change of +0.1422 against -0.0983 for "sell". So
    side=="buy" is an aggressive BUY and takes +1."""
    tag = ('"%s-USD"' % asset)
    tob, tr = {}, defaultdict(lambda: [0.0, 0.0, 0.0, 0])
    for ln in iter_gz(path):
        if tag not in ln:
            continue
        m = _obj(ln)
        if m is None:
            continue
        if m.get("type") != "ticker":
            continue
        if str(m.get("product_id", "")).split("-")[0] != asset:
            continue
        rx = _f(m.get("_rx"))
        if rx is None:
            continue
        s = int(rx)
        b, bs = _f(m.get("best_bid")), _f(m.get("best_bid_size"))
        a, asz = _f(m.get("best_ask")), _f(m.get("best_ask_size"))
        if b and a and a >= b:
            tob[s] = (b, bs or 0.0, a, asz or 0.0)
        sz = _f(m.get("last_size")) or 0.0
        if sz > 0:
            row = tr[s]
            row[0] += sz
            if m.get("side") == "buy":
                row[1] += sz
            elif m.get("side") == "sell":
                row[2] += sz
            row[3] += 1
    return tob, {k: tuple(v) for k, v in tr.items()}


def read_kraken(path, asset="BTC"):
    tob = {}
    for ln in iter_gz(path):
        m = _obj(ln)
        if m is None:
            continue
        if m.get("channel") != "ticker":
            continue
        rx = _f(m.get("_rx"))
        if rx is None:
            continue
        for d in m.get("data") or []:
            if not isinstance(d, dict):
                continue
            if str(d.get("symbol", "")).split("/")[0] != asset:
                continue
            b, bs = _f(d.get("bid")), _f(d.get("bid_qty"))
            a, asz = _f(d.get("ask")), _f(d.get("ask_qty"))
            if b and a and a >= b:
                tob[int(rx)] = (b, bs or 0.0, a, asz or 0.0)
    return tob


BS_DEEP_MIN_LEVELS = 50          # below this a bps-band depth is censored


def read_bitstamp(path, asset="BTC"):
    """-> {second: (bid, bidsz, ask, asksz, cum5, span5_bps, nlev,
                    d1bp, d5bp, d10bp)}

    THE TRIM CHANGED MID-TAPE, AND IGNORING THAT WOULD HAVE INVENTED A REGIME.
    crypto_feeds.py trims Bitstamp to 5 levels a side, but not from the
    beginning: binary search over the 326 hour files puts the last 100-level
    hour at 20260827T23 and the first 5-level hour at 20260828T00. So a naive
    "sum every level present" is 100 levels for the first 49 hours and 5
    levels for the remaining 277 -- measured, that reads 128.8 BTC and 83.7
    bps of span in the early hours against ~1.2 BTC and ~0.5 bps later. A
    factor built that way would carry a 100x step change on 2026-08-28 that
    has nothing to do with the market.

    Two consequences, both taken:

    1. The comparable feature uses EXACTLY the first 5 levels everywhere.
       That is the deepest cut available on the whole tape.
    2. The bps-band depths the task asks for (1/5/10 bps) are computed ONLY
       where the book is genuinely deep (>= %d levels) and are NaN elsewhere,
       so a censored reading is never mixed with an uncensored one. On the
       5-level portion those bands are not merely noisy, they are unmeasured:
       5 levels span a median 0.353 bps, reach 1 bp 6.6%% of the time and
       5 bps never.

    `nlev` is carried so the homogeneity is checkable from the cache itself.
    """ % BS_DEEP_MIN_LEVELS
    ch = ("order_book_%susd" % asset.lower())
    out = {}
    for ln in iter_gz(path):
        if ch not in ln:
            continue
        m = _obj(ln)
        if m is None:
            continue
        if m.get("channel") != ch:
            continue
        rx = _f(m.get("_rx"))
        d = m.get("data") or {}
        bids, asks = d.get("bids") or [], d.get("asks") or []
        if rx is None or not bids or not asks:
            continue
        try:
            b, bs = float(bids[0][0]), float(bids[0][1])
            a, asz = float(asks[0][0]), float(asks[0][1])
        except (TypeError, ValueError, IndexError):
            continue
        if not (b > 0 and a >= b):
            continue
        mid = (a + b) / 2.0
        nlev = min(len(bids), len(asks))
        try:
            cum5 = (sum(float(x[1]) for x in bids[:5])
                    + sum(float(x[1]) for x in asks[:5]))
            span5 = ((float(bids[0][0]) - float(bids[:5][-1][0]))
                     + (float(asks[:5][-1][0]) - float(asks[0][0]))) / mid * 1e4
        except (TypeError, ValueError, IndexError):
            continue
        if nlev >= BS_DEEP_MIN_LEVELS:
            band = [None, None, None]
            for bi, bps in enumerate((1.0, 5.0, 10.0)):
                w = mid * bps / 1e4
                tot = 0.0
                try:
                    for px, sz in bids:
                        if mid - float(px) > w:
                            break
                        tot += float(sz)
                    for px, sz in asks:
                        if float(px) - mid > w:
                            break
                        tot += float(sz)
                except (TypeError, ValueError):
                    tot = None
                band[bi] = tot
            d1, d5, d10 = band
        else:
            d1 = d5 = d10 = None
        out[int(rx)] = (b, bs, a, asz, cum5, span5, nlev, d1, d5, d10)
    return out


def read_gemini(path, carry):
    """Gemini publishes incremental top_of_book `change` events, so bid and
    ask are carried forward exactly as crypto_feeds.py does when it builds the
    replica. `carry` is the state that survived the previous hour."""
    tob = {}
    bid, bsz, ask, asz = carry
    for ln in iter_gz(path):
        m = _obj(ln)
        if m is None:
            continue
        evs = m.get("events") or []
        if not evs:
            continue
        rx = _f(m.get("_rx"))
        if rx is None:
            continue
        touched = False
        for e in evs:
            if not isinstance(e, dict):
                continue
            if e.get("type") != "change" or e.get("side") not in ("bid", "ask"):
                continue
            p, q = _f(e.get("price")), _f(e.get("remaining"))
            if p is None or q is None:
                continue
            if e["side"] == "bid":
                bid, bsz = p, q
            else:
                ask, asz = p, q
            touched = True
        if touched and bid and ask and ask >= bid:
            tob[int(rx)] = (bid, bsz, ask, asz)
    return tob, (bid, bsz, ask, asz)


def read_replica(path, asset="BTC"):
    """-> {second: (wmid, n_ex, {ex: (b, a)})}. Already emitted at the top of
    the second, which is the alignment BRTI itself is stamped on."""
    out = {}
    for ln in iter_gz(path):
        m = _obj(ln)
        if m is None:
            continue
        s = m.get("sec")
        d = m.get(asset)
        if s is None or not isinstance(d, dict):
            continue
        w = _f(d.get("wmid"))
        if w is None or w <= 0:
            continue
        per = {}
        for ex, ba in (d.get("per_ex") or {}).items():
            if not isinstance(ba, dict):
                continue
            b, a = _f(ba.get("b")), _f(ba.get("a"))
            if b and a and a >= b:
                per[ex] = (b, a)
        if per:
            out[int(s)] = (w, int(d.get("n_ex") or len(per)), per)
    return out


def read_index(path, index_id="BRTI"):
    tag = '"%s"' % index_id
    out = {}
    for ln in iter_gz(path):
        if tag not in ln:
            continue
        m = _obj(ln)
        if m is None:
            continue
        d = m.get("msg") or {}
        if not isinstance(d, dict):
            continue
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
        t, v = _f(inner.get("time")), _f(inner.get("value"))
        if t is None or v is None or v <= 0:
            continue
        out[int(round(t / 1000.0))] = v
    return out


# ==========================================================================
# the builder
# ==========================================================================
class VolWindows:
    """Prefix sums of per-second Coinbase trade flow, so a trailing window is
    two lookups instead of 300. The window is HALF-OPEN, [t-w, t): second t
    itself is excluded because its trades happen after the index print
    stamped t. Everything this returns is strictly in the past."""

    __slots__ = ("lo", "cum")

    def __init__(self, by_sec, lo, hi):
        self.lo = lo
        cum = [(0.0, 0.0, 0.0, 0)]
        v = b = s = 0.0
        n = 0
        for t in range(lo, hi + 1):
            r = by_sec.get(t)
            if r:
                v += r[0]
                b += r[1]
                s += r[2]
                n += r[3]
            cum.append((v, b, s, n))
        self.cum = cum                 # cum[k] = totals over [lo, lo+k)

    def win(self, t, w):
        a = t - w - self.lo
        z = t - self.lo
        if z <= 0:
            return (0.0, 0.0, 0.0, 0)
        if a < 0:
            a = 0
        if z >= len(self.cum):
            z = len(self.cum) - 1
        ca, cz = self.cum[a], self.cum[z]
        return (cz[0] - ca[0], cz[1] - ca[1], cz[2] - ca[2], cz[3] - ca[3])


def carry_forward(by_sec, first, last, prior):
    """snap[t] = the last state observed in a second STRICTLY BEFORE t.

    This is the no-peek rule in one function. A record stamped _rx = t + 0.4
    lands in second t but arrived AFTER the index print stamped t, so it may
    never touch the feature row for t."""
    snap = {}
    state = prior
    for t in range(first, last + 1):
        snap[t] = state
        nxt = by_sec.get(t)
        if nxt is not None:
            state = nxt
    return snap, state


def build(feeds, data, cache_path, asset="BTC", index_id="BRTI",
          limit_hours=None, verbose=True):
    hs = hour_keys(feeds, data)
    if limit_hours:
        hs = hs[:limit_hours]
    if not hs:
        print("  loaded nothing: no overlapping hours in %s and %s"
              % (feeds, data))
        return 0

    d = os.path.dirname(os.path.abspath(cache_path))
    if d:
        os.makedirs(d, exist_ok=True)
    st = {"coinbase": None, "kraken": None, "bitstamp": None, "gemini": None}
    gem_carry = (None, 0.0, None, 0.0)
    volhist = {}          # sec -> (vol, buy, sell, ntr) during [sec, sec+1)
    n_rows = 0
    stats = defaultdict(int)

    with gzip.open(cache_path, "wt", encoding="utf-8", compresslevel=6) as out:
        out.write("# spotdepth cache v%d asset=%s index=%s\n"
                  % (CACHE_VERSION, asset, index_id))
        out.write(",".join(COLS) + "\n")
        for hi, h in enumerate(hs):
            idx = read_index(os.path.join(data, "cfbenchmarks_value",
                                          h + ".jsonl.gz"), index_id)
            rep = read_replica(os.path.join(feeds, "index_replica",
                                            h + ".jsonl.gz"), asset)
            if not idx or not rep:
                stats["empty_hours"] += 1
                continue
            cb_tob, cb_tr = read_coinbase(
                os.path.join(feeds, "coinbase", h + ".jsonl.gz"), asset)
            kr_tob = read_kraken(
                os.path.join(feeds, "kraken", h + ".jsonl.gz"), asset)
            bs_tob = read_bitstamp(
                os.path.join(feeds, "bitstamp", h + ".jsonl.gz"), asset)
            gm_tob, gem_carry = read_gemini(
                os.path.join(feeds, "gemini", h + ".jsonl.gz"), gem_carry)
            secs = sorted(idx)
            lo, hi_s = secs[0], secs[-1]
            cb_s, st["coinbase"] = carry_forward(cb_tob, lo, hi_s,
                                                 st["coinbase"])
            kr_s, st["kraken"] = carry_forward(kr_tob, lo, hi_s, st["kraken"])
            bs_s, st["bitstamp"] = carry_forward(bs_tob, lo, hi_s,
                                                 st["bitstamp"])
            gm_s, st["gemini"] = carry_forward(gm_tob, lo, hi_s, st["gemini"])
            volhist.update(cb_tr)
            for k in [k for k in volhist if k < lo - 400]:
                del volhist[k]
            vw = VolWindows(volhist, lo - 400, hi_s)

            for t in secs:
                r = rep.get(t)
                if r is None:
                    stats["no_replica"] += 1
                    continue
                wmid, n_ex, per = r
                row = feature_row(t, idx[t], wmid, n_ex, per,
                                  cb_s.get(t), kr_s.get(t), bs_s.get(t),
                                  gm_s.get(t), vw)
                if row is None:
                    stats["no_features"] += 1
                    continue
                out.write(",".join(row) + "\n")
                n_rows += 1
                stats["rows"] += 1
            if verbose and (hi + 1) % 40 == 0:
                print("    %d/%d hours, %s rows" % (hi + 1, len(hs),
                                                    format(n_rows, ",")))
    if verbose:
        print("  build: %s  ->  %s" % (dict(stats), cache_path))
    return n_rows


def _fmt(x):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return ""
    return "%.6g" % x


def feature_row(t, brti, wmid, n_ex, per, cb, kr, bs, gm, volhist):
    """All of (a)-(e) for one second. Everything here is state as of the top
    of second t, or flow strictly before it."""
    # ---- (a) depth, from the raw venue touch, carried forward -------------
    dep = {}
    base_bid = base_ask = 0.0
    usd_bid = usd_ask = 0.0
    for name, s in (("cb", cb), ("kr", kr), ("bs", bs), ("gm", gm)):
        if not s:
            dep[name] = None
            continue
        b, bsz, a, asz = s[0], s[1], s[2], s[3]
        if not b or not a:
            dep[name] = None
            continue
        dep[name] = (bsz * b) + (asz * a)
        base_bid += bsz
        base_ask += asz
        usd_bid += bsz * b
        usd_ask += asz * a
    if usd_bid <= 0 or usd_ask <= 0:
        return None

    # bitstamp's book: the only multi-level depth on this tape. cum5/span5 are
    # the first 5 levels everywhere (comparable across the trim change); the
    # bps bands are present only on the un-trimmed 49 hours.
    if bs and len(bs) >= 10:
        cum5, span5, nlev, d1, d5, d10 = bs[4], bs[5], bs[6], bs[7], bs[8], bs[9]
        impact = (span5 / cum5) if (cum5 and cum5 > 0) else None
    else:
        cum5 = span5 = impact = nlev = d1 = d5 = d10 = None

    # ---- (b) dispersion across venue mids ---------------------------------
    mids = sorted(((b + a) / 2.0) for b, a in per.values())
    if len(mids) >= 2:
        rng = (mids[-1] - mids[0]) / wmid * 1e4
        mu = sum(mids) / len(mids)
        sd = math.sqrt(sum((m - mu) ** 2 for m in mids) / (len(mids) - 1))
        sd = sd / wmid * 1e4
        adj = max(mids[i + 1] - mids[i] for i in range(len(mids) - 1))
        adj = adj / wmid * 1e4
    else:
        rng = sd = adj = 0.0

    # ---- (c) spread -------------------------------------------------------
    spreads = [(a - b) / wmid * 1e4 for b, a in per.values()]
    best_bid = max(b for b, a in per.values())
    best_ask = min(a for b, a in per.values())
    spr_cons = (best_ask - best_bid) / wmid * 1e4
    spr_mean = sum(spreads) / len(spreads)
    spr_max = max(spreads)

    # ---- (d) volume, over windows that END at t ---------------------------
    v1, b1, s1, n1 = volhist.win(t, 1)
    v60, b60, s60, n60 = volhist.win(t, 60)
    v300, _, _, n300 = volhist.win(t, 300)

    vals = [t, brti, wmid, n_ex,
            usd_bid, usd_ask, usd_bid + usd_ask, min(usd_bid, usd_ask),
            dep["cb"], dep["kr"], dep["bs"], dep["gm"],
            base_bid + base_ask,
            cum5, span5, impact,
            nlev, d1, d5, d10,
            rng, sd, adj,
            spr_cons, spr_mean, spr_max,
            v1, b1, s1, n1,
            v60, b60, s60, n60,
            v300, n300]
    return [("%d" % t) if i == 0 else _fmt(v) for i, v in enumerate(vals)]


# ==========================================================================
# cache load
# ==========================================================================
# Feature columns are stored as float32. The cache is written with "%.6g", so
# every value on disk carries SIX significant figures and float32 holds 7.2 --
# the narrower type therefore loses nothing that was ever recorded, and halves
# a 1.2M-row table. `sec` (a unix second, ~1.79e9) and `brti` (a price to the
# cent) are the two that genuinely need float64, and they keep it.
WIDE = ("sec", "brti")


def _zeros(n, typ="f"):
    return array(typ, bytes(n * array(typ).itemsize))


def load_cache(path, verbose=True):
    cols = {}
    hdr = None
    n = 0
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for ln in fh:
            if ln.startswith("#"):
                continue
            parts = ln.rstrip("\n").split(",")
            if hdr is None:
                hdr = parts
                cols = {c: array("d" if c in WIDE else "f") for c in hdr}
                continue
            if len(parts) != len(hdr):
                continue
            for c, p in zip(hdr, parts):
                cols[c].append(float(p) if p else float("nan"))
            n += 1
    if verbose:
        print("  cache: %s seconds, %d columns" % (format(n, ","), len(hdr)))
    return cols


# ==========================================================================
# statistics -- stdlib only
# ==========================================================================
def ranks(x, idx):
    """Average ranks of x over the positions in idx."""
    order = sorted(idx, key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def pearson_on(a, b, idx):
    n = len(idx)
    if n < 3:
        return 0.0
    ma = sum(a[i] for i in idx) / n
    mb = sum(b[i] for i in idx) / n
    sa = sb = sab = 0.0
    for i in idx:
        da, db = a[i] - ma, b[i] - mb
        sa += da * da
        sb += db * db
        sab += da * db
    if sa <= 0 or sb <= 0:
        return 0.0
    return sab / math.sqrt(sa * sb)


def quant(sorted_vals, q):
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    p = q * (len(sorted_vals) - 1)
    lo = int(math.floor(p))
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (p - lo)


def bucket_tails(f, y, idx, nb=5, qs=(0.5, 0.99, 0.999)):
    """Quantiles of |move| inside each factor quantile bucket."""
    order = sorted(idx, key=lambda i: f[i])
    n = len(order)
    if n < nb * 200:
        return [], {}
    out = []
    for k in range(nb):
        lo = (n * k) // nb
        hi = (n * (k + 1)) // nb
        chunk = sorted(y[i] for i in order[lo:hi])
        out.append({
            "k": k, "n": len(chunk),
            "f_lo": f[order[lo]], "f_hi": f[order[hi - 1]],
            "q": dict((q, quant(chunk, q)) for q in qs),
        })
    allv = sorted(y[i] for i in idx)
    uncond = dict((q, quant(allv, q)) for q in qs)
    return out, uncond


def report_factor(name, f, y, idx, nb=5):
    b, u = bucket_tails(f, y, idx, nb=nb)
    if not b:
        return None
    rf, ry = ranks(f, idx), ranks(y, idx)
    rho = pearson_on(rf, ry, idx)
    p99_lo, p99_hi = b[0]["q"][0.99], b[-1]["q"][0.99]
    p999_lo, p999_hi = b[0]["q"][0.999], b[-1]["q"][0.999]
    nan = float("nan")
    return {
        "name": name, "n": len(idx), "rho": rho,
        "buckets": b, "uncond": u,
        "p99_ratio": (p99_hi / p99_lo) if p99_lo > 0 else nan,
        "p999_ratio": (p999_hi / p999_lo) if p999_lo > 0 else nan,
        "lift_top_pct": 100.0 * (p99_hi / u[0.99] - 1.0) if u[0.99] > 0 else nan,
        "lift_bot_pct": 100.0 * (p99_lo / u[0.99] - 1.0) if u[0.99] > 0 else nan,
        "p50_ratio": (b[-1]["q"][0.5] / b[0]["q"][0.5])
                     if b[0]["q"][0.5] > 0 else nan,
    }


def print_bucket_table(res, tgt_name):
    b, u = res["buckets"], res["uncond"]
    print("\n  %s  vs  %s   n=%s   spearman rho=%+.4f"
          % (res["name"], tgt_name, format(res["n"], ","), res["rho"]))
    print("    bucket  n          factor range              p50      p99"
          "     p99.9   p99 vs uncond")
    for r in b:
        d = (100.0 * (r["q"][0.99] / u[0.99] - 1.0)) if u[0.99] > 0 \
            else float("nan")
        print("    Q%d      %-10d [%9.4g,%9.4g] %8.3f %8.3f %9.3f  %+8.1f%%"
              % (r["k"] + 1, r["n"], r["f_lo"], r["f_hi"],
                 r["q"][0.5], r["q"][0.99], r["q"][0.999], d))
    print("    ALL     %-10d %-23s %8.3f %8.3f %9.3f"
          % (res["n"], "", u[0.5], u[0.99], u[0.999]))
    print("    p99 Qtop/Qbot = %.2fx     p99.9 Qtop/Qbot = %.2fx"
          % (res["p99_ratio"], res["p999_ratio"]))


def day_consistency(f, y, idx, sec, nb=5):
    """The p99 ratio recomputed inside each UTC day. Overlapping r-second
    windows make the pooled n a fiction; if the effect is real it should show
    up on most days on its own."""
    byday = defaultdict(list)
    for i in idx:
        byday[int(sec[i]) // 86400].append(i)
    out = []
    for d in sorted(byday):
        sub = byday[d]
        if len(sub) < nb * 2000:
            continue
        b, u = bucket_tails(f, y, sub, nb=nb)
        if not b:
            continue
        lo, hi = b[0]["q"][0.99], b[-1]["q"][0.99]
        out.append(hi / lo if lo > 0 else float("nan"))
    return out


# ==========================================================================
# factor construction
# ==========================================================================
def derive(cols):
    """Factors, all oriented so that HIGHER = the condition we think permits a
    BIGGER move. A factor whose lift comes out negative is telling us the
    orientation was wrong, which is itself information."""
    n = len(cols["sec"])
    sec, brti = cols["sec"], cols["brti"]
    nan = float("nan")

    def blank():
        return _zeros(n)

    def col(name):
        return cols[name]

    def ratio(a, b):
        out = blank()
        for i in range(n):
            bb = b[i]
            out[i] = (a[i] / bb) if (bb == bb and bb > 0) else nan
        return out

    def neg(a):
        out = blank()
        for i in range(n):
            out[i] = -a[i]
        return out

    def logof(a):
        out = blank()
        for i in range(n):
            v = a[i]
            out[i] = math.log(v) if (v == v and v > 0) else nan
        return out

    # ---- the INCUMBENT: trailing-300s realised sd of 1s index log returns,
    # in bps, over the half-open window [t-300, t). Contiguity is required: a
    # gap in the index makes the window undefined rather than merely short.
    sig = blank()
    ret = array("d", bytes(8 * n))     # log returns feed a variance; keep 64
    for i in range(1, n):
        if sec[i] == sec[i - 1] + 1 and brti[i] > 0 and brti[i - 1] > 0:
            ret[i] = math.log(brti[i] / brti[i - 1]) * 1e4
        else:
            ret[i] = nan
    ret[0] = nan
    W = 300
    s1 = s2 = 0.0
    cnt = 0
    dq = deque()
    for i in range(n):
        while dq and dq[0][0] < i - W:
            j, v = dq.popleft()
            s1 -= v
            s2 -= v * v
            cnt -= 1
        if cnt >= 30:
            mu = s1 / cnt
            sig[i] = math.sqrt(max(s2 / cnt - mu * mu, 0.0))
        else:
            sig[i] = nan
        v = ret[i]
        if v == v:
            dq.append((i, v))
            s1 += v
            s2 += v * v
            cnt += 1
        else:
            dq.clear()
            s1 = s2 = 0.0
            cnt = 0
    cols["sig300_bps"] = sig

    fac = {}
    # ---- (a) DEPTH. Thin permits big moves, so depth is NEGATED.
    fac["thin_touch_usd"] = neg(logof(col("dep_tot_usd")))
    fac["thin_touch_min"] = neg(logof(col("dep_min_usd")))
    fac["thin_cb_usd"] = neg(logof(col("dep_cb_usd")))
    fac["thin_kr_usd"] = neg(logof(col("dep_kr_usd")))
    fac["thin_bs_usd"] = neg(logof(col("dep_bs_usd")))
    fac["thin_gm_usd"] = neg(logof(col("dep_gm_usd")))
    fac["thin_bs_cum5"] = neg(logof(col("bs_cum5_base")))
    fac["bs_span5_bps"] = col("bs_span5_bps")
    fac["bs_impact_per_btc"] = logof(col("bs_impact_bps_per_btc"))
    # bps-band depth exists only on the 49 un-trimmed hours; NaN elsewhere, so
    # these are automatically scored on that sub-sample alone.
    fac["thin_bs_1bp"] = neg(logof(col("bs_d1bp_base")))
    fac["thin_bs_5bp"] = neg(logof(col("bs_d5bp_base")))
    fac["thin_bs_10bp"] = neg(logof(col("bs_d10bp_base")))
    # ---- (b) DISPERSION
    fac["disp_range_bps"] = col("disp_range_bps")
    fac["disp_sd_bps"] = col("disp_sd_bps")
    fac["disp_adjgap_bps"] = col("disp_adjgap_bps")
    # ---- (c) SPREAD
    fac["spr_cons_bps"] = col("spr_cons_bps")
    fac["spr_mean_bps"] = col("spr_mean_bps")
    fac["spr_max_bps"] = col("spr_max_bps")
    # ---- (d) VOLUME
    fac["vol60_btc"] = col("vol60")
    fac["vol300_btc"] = col("vol300")
    fac["ntr60"] = col("ntr60")
    imb = blank()
    b60, s60 = col("buy60"), col("sell60")
    for i in range(n):
        tot = b60[i] + s60[i]
        imb[i] = (abs(b60[i] - s60[i]) / tot) if tot > 0 else nan
    fac["abs_imb60"] = imb
    # ---- (e) SIZE vs FLOW
    meansz = blank()
    v300, n300 = col("vol300"), col("ntr300")
    for i in range(n):
        meansz[i] = (v300[i] / n300[i]) if n300[i] > 0 else nan
    fac["clear_ratio"] = logof(ratio(meansz, col("dep_tot_base")))
    fac["press60"] = logof(ratio(col("vol60"), col("dep_tot_base")))
    # ---- (i) INCUMBENT
    fac["sig300_bps"] = sig
    return fac


def targets(cols, horizons=HORIZONS):
    """|move| over the next r seconds in bps, plus the settlement-relevant
    |mean of the next r prints - now|. Contiguity is enforced: a row whose
    t+k is missing for any k<=r is dropped, not stretched."""
    n = len(cols["sec"])
    sec, brti = cols["sec"], cols["brti"]
    nan = float("nan")
    pos = {}
    for i in range(n):
        pos[int(sec[i])] = i
    out = {}
    for r in horizons:
        mv = _zeros(n)
        am = _zeros(n)
        for i in range(n):
            t = int(sec[i])
            if brti[i] <= 0:
                mv[i] = am[i] = nan
                continue
            ok = True
            acc = 0.0
            last = 0.0
            for k in range(1, r + 1):
                jj = pos.get(t + k)
                if jj is None:
                    ok = False
                    break
                last = brti[jj]
                acc += last
            if not ok:
                mv[i] = am[i] = nan
                continue
            mv[i] = abs(last - brti[i]) / brti[i] * 1e4
            am[i] = abs(acc / r - brti[i]) / brti[i] * 1e4
        out["mv%d" % r] = mv
        out["am%d" % r] = am
    return out


def valid_idx(*arrs):
    n = len(arrs[0])
    out = []
    for i in range(n):
        ok = True
        for a in arrs:
            v = a[i]
            if v != v or v in (float("inf"), float("-inf")):
                ok = False
                break
        if ok:
            out.append(i)
    return out


# ==========================================================================
# SELF-TEST
# ==========================================================================
def _synth(n, seed, coupling, leak=False):
    """A world where the |move| scale is set by 1/depth, and a matched world
    where it is not. `coupling` = 0 plants nothing."""
    rng = random.Random(seed)
    depth = array("d", bytes(8 * n))
    move = array("d", bytes(8 * n))
    for i in range(n):
        d = math.exp(rng.gauss(0, 1))
        depth[i] = -math.log(d)                     # oriented: thin = high
        scale = 1.0 / (d ** coupling)
        move[i] = abs(rng.gauss(0, scale)) \
            + 0.02 * abs(rng.gauss(0, scale)) ** 3
    if leak:
        for i in range(n):
            depth[i] = move[i]                      # the deliberate leak
    return depth, move


def selftest():
    print("=" * 78)
    print("SELF-TEST -- spotdepth.py")
    print("=" * 78)
    fails = []

    # ---- 1. PLANTED: thin book -> bigger tail. The estimator must see it.
    n = 60000
    idx = list(range(n))
    d, m = _synth(n, 11, coupling=1.0)
    r = report_factor("planted", d, m, idx)
    print("\n[1] planted 1/depth coupling: rho=%+.3f  p99 Q5/Q1=%.2fx  "
          "top lift=%+.1f%%" % (r["rho"], r["p99_ratio"], r["lift_top_pct"]))
    if r["p99_ratio"] < 2.0:
        fails.append("planted world: p99 Q5/Q1 = %.2f, expected >= 2.0"
                     % r["p99_ratio"])
    if r["rho"] < 0.20:
        fails.append("planted world: rho = %.3f, expected >= 0.20" % r["rho"])

    # ---- 2. NULL: same marginals, no coupling. It must find NOTHING.
    d0, m0 = _synth(n, 12, coupling=0.0)
    r0 = report_factor("null", d0, m0, idx)
    print("[2] null (no coupling):      rho=%+.3f  p99 Q5/Q1=%.2fx  "
          "top lift=%+.1f%%" % (r0["rho"], r0["p99_ratio"], r0["lift_top_pct"]))
    if abs(r0["rho"]) > 0.03:
        fails.append("null world: rho = %+.3f, expected |rho| <= 0.03"
                     % r0["rho"])
    if not (0.80 < r0["p99_ratio"] < 1.25):
        fails.append("null world: p99 Q5/Q1 = %.2f, expected ~1.0"
                     % r0["p99_ratio"])

    # ---- 3. LEAK CONTROL. An estimator never shown capable of finding
    #         anything is uninterpretable. Hand it the answer; it must fire.
    dl, ml = _synth(20000, 13, coupling=0.0, leak=True)
    rl = report_factor("leak", dl, ml, list(range(20000)))
    print("[3] leaking control:         rho=%+.3f  p99 Q5/Q1=%.2fx"
          % (rl["rho"], rl["p99_ratio"]))
    # The bar on the ratio is 5x, not something larger: with the answer
    # handed over, p99(Q5)/p99(Q1) is capped by the MOVE distribution's own
    # quantile spread (here 11.4x), not by the strength of the relationship.
    # The null scores 0.99x on the same statistic, so 5x separates them by a
    # wide margin without pretending the ceiling is higher than it is.
    if rl["rho"] < 0.99 or rl["p99_ratio"] < 5.0:
        fails.append("leak control failed to fire: rho=%.3f ratio=%.1f"
                     % (rl["rho"], rl["p99_ratio"]))

    # ---- 4. the quantile helper against a distribution with known answers
    v = sorted(float(i) for i in range(1001))
    for q, want in ((0.5, 500.0), (0.99, 990.0), (0.999, 999.0)):
        got = quant(v, q)
        if abs(got - want) > 1e-6:
            fails.append("quant(%.3f) = %.4f, expected %.4f" % (q, got, want))

    # ---- 5. NO-PEEK, END TO END. Plant a depth step at a known second and
    #         fail if the row for that second already knows about it.
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="spotdepth_st_")
    feeds = os.path.join(tmp, "feed_data")
    data = os.path.join(tmp, "kalshi_data")
    for sub in ("coinbase", "kraken", "bitstamp", "gemini", "index_replica"):
        os.makedirs(os.path.join(feeds, sub), exist_ok=True)
    os.makedirs(os.path.join(data, "cfbenchmarks_value"), exist_ok=True)
    T0 = 1788696000
    STEP = T0 + 50

    def wr(path, rows):
        """A str row is written verbatim -- that is how the garbled lines
        gzsalvage yields are planted."""
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            for o in rows:
                fh.write(o if isinstance(o, str) else json.dumps(o))
                fh.write("\n")

    cb, kr, bs, gm, rp, ix = [], [], [], [], [], []
    for k in range(120):
        t = T0 + k
        px = 80000.0 + k                       # a clean +1 USD/s ramp
        sz = 0.5 if t < STEP else 500.0        # depth jumps 1000x at STEP
        cb.append({"type": "ticker", "product_id": "BTC-USD",
                   "price": "%f" % px,
                   "best_bid": "%f" % (px - 0.5), "best_bid_size": "%f" % sz,
                   "best_ask": "%f" % (px + 0.5), "best_ask_size": "%f" % sz,
                   "side": "buy", "last_size": "0.01", "volume_24h": "1",
                   "_rx": t + 0.30})
        kr.append({"channel": "ticker", "type": "update", "_rx": t + 0.4,
                   "data": [{"symbol": "BTC/USD", "bid": px - 0.6,
                             "bid_qty": 1.0, "ask": px + 0.6,
                             "ask_qty": 1.0}]})
        # The collector's Bitstamp trim changed mid-tape, so the fake tape
        # changes too: 100 levels for the first 60s, 5 after. The first 5
        # levels are IDENTICAL in both regimes, so any jump in cum5 across
        # k=60 is the reader summing whatever it was handed.
        nlev = 100 if k < 60 else 5
        bs.append({"channel": "order_book_btcusd", "event": "data",
                   "_rx": t + 0.5, "data": {
                       "bids": [["%f" % (px - 0.5 - i * 0.1), "0.2"]
                                for i in range(nlev)],
                       "asks": [["%f" % (px + 0.5 + i * 0.1), "0.2"]
                                for i in range(nlev)]}})
        gm.append({"type": "update", "_rx": t + 0.6, "events": [
            {"type": "change", "side": "bid", "price": "%f" % (px - 0.7),
             "reason": "top-of-book", "remaining": "0.3"},
            {"type": "change", "side": "ask", "price": "%f" % (px + 0.7),
             "reason": "top-of-book", "remaining": "0.3"}]})
        rp.append({"_rx": t + 0.003, "sec": t, "BTC": {
            "wmid": px, "median_mid": px, "n_ex": 4, "per_ex": {
                "coinbase": {"b": px - 0.5, "a": px + 0.5},
                "kraken": {"b": px - 0.6, "a": px + 0.6},
                "bitstamp": {"b": px - 0.5, "a": px + 0.5},
                "gemini": {"b": px - 0.7, "a": px + 0.7}}}})
        ix.append({"type": "cfbenchmarks_value", "msg": {
            "index_id": "BRTI", "received_at": t * 1000 + 40,
            "data": json.dumps({"type": "value", "time": t * 1000,
                                "id": "BRTI", "value": "%f" % px})}})
    # SALVAGE DEBRIS. gzsalvage yields the surviving tail of a record broken
    # by a collector restart, and that tail can be a bare number, a fragment,
    # or a JSON array. Every one of these is valid or invalid JSON that is not
    # an object, and each used to crash a reader on the following .get.
    # Planted in every channel, because the fix had to be made in all six.
    debris = ["7", "84547512460261", '"a string"', "[1,2,3]", "null",
              '{"channel":"ticker","data":[42]}', "{not json at all",
              '{"events":[7]}', '{"sec":123,"BTC":9}', '{"msg":5}']
    for lst in (cb, kr, bs, gm, rp, ix):
        lst.extend(debris)
    h = "20260906T12"
    wr(os.path.join(feeds, "coinbase", h + ".jsonl.gz"), cb)
    wr(os.path.join(feeds, "kraken", h + ".jsonl.gz"), kr)
    wr(os.path.join(feeds, "bitstamp", h + ".jsonl.gz"), bs)
    wr(os.path.join(feeds, "gemini", h + ".jsonl.gz"), gm)
    wr(os.path.join(feeds, "index_replica", h + ".jsonl.gz"), rp)
    wr(os.path.join(data, "cfbenchmarks_value", h + ".jsonl.gz"), ix)
    cpath = os.path.join(tmp, "cache.csv.gz")
    nrows = build(feeds, data, cpath, verbose=False)
    if nrows != 119:
        fails.append("salvage debris changed the row count: %d, expected 119"
                     % nrows)
    cc = load_cache(cpath, verbose=False)
    at = dict((int(s), i) for i, s in enumerate(cc["sec"]))
    if STEP not in at or (STEP + 1) not in at:
        fails.append("no-peek probe: cache is missing the step seconds")
    else:
        before = cc["dep_cb_usd"][at[STEP]]
        after = cc["dep_cb_usd"][at[STEP + 1]]
        print("[5] no-peek probe: dep_cb_usd at the step second = %.0f, at "
              "step+1 = %.0f  (rows=%d)" % (before, after, nrows))
        if before > 1e6:
            fails.append("NO-PEEK VIOLATED: the row for the step second "
                         "already carries the post-step depth (%.0f)" % before)
        if after < 1e6:
            fails.append("carry-forward failed: step+1 should see the new "
                         "depth, got %.0f" % after)

    # ---- 5b. THE TRIM CHANGE. cum5 must not move when the collector starts
    #          throwing levels away, and the bps bands must vanish rather
    #          than quietly become a 5-level number.
    deep_s, shal_s = T0 + 30, T0 + 90
    if deep_s in at and shal_s in at:
        c_deep = cc["bs_cum5_base"][at[deep_s]]
        c_shal = cc["bs_cum5_base"][at[shal_s]]
        d_deep = cc["bs_d5bp_base"][at[deep_s]]
        d_shal = cc["bs_d5bp_base"][at[shal_s]]
        print("[5b] trim change: cum5 deep=%.4f shallow=%.4f (must match); "
              "d5bp deep=%.4f shallow=%s (must be nan)"
              % (c_deep, c_shal, d_deep, d_shal))
        if abs(c_deep - c_shal) > 1e-6:
            fails.append("cum5 jumped across the trim change: %.6f -> %.6f"
                         % (c_deep, c_shal))
        if not (d_deep > 0):
            fails.append("bps-band depth missing on a 100-level second")
        if d_shal == d_shal:
            fails.append("bps-band depth was computed on a 5-level second "
                         "(%.4f) -- censored data leaked in" % d_shal)
    else:
        fails.append("trim-change probe: cache missing the probe seconds")

    # ---- 6. targets on a known ramp of +1 USD/s
    tg = targets(cc, horizons=(2, 9))
    if T0 + 10 in at:
        i = at[T0 + 10]
        want2 = 2.0 / cc["brti"][i] * 1e4
        want_am2 = 1.5 / cc["brti"][i] * 1e4
        print("[6] targets on a known ramp: mv2=%.6f bps (want %.6f), "
              "am2=%.6f bps (want %.6f)"
              % (tg["mv2"][i], want2, tg["am2"][i], want_am2))
        if abs(tg["mv2"][i] - want2) > 1e-6:
            fails.append("mv2 on a known ramp = %.6f, expected %.6f"
                         % (tg["mv2"][i], want2))
        if abs(tg["am2"][i] - want_am2) > 1e-6:
            fails.append("am2 on a known ramp = %.6f, expected %.6f"
                         % (tg["am2"][i], want_am2))
    else:
        fails.append("no-peek probe: cache missing T0+10")

    # ---- 7. carry_forward IS the no-peek rule; test it in isolation
    snap, last = carry_forward({10: "a", 12: "b"}, 10, 14, None)
    if snap[10] is not None or snap[11] != "a" or snap[12] != "a" \
            or snap[13] != "b" or last != "b":
        fails.append("carry_forward leaked: %r" % (snap,))

    shutil.rmtree(tmp, ignore_errors=True)

    print()
    if fails:
        print("SELF-TEST FAILED")
        for f in fails:
            print("  -", f)
        return 1
    print("SELF-TEST PASSED -- planted found, null clean, leak fires, "
          "no-peek holds, targets exact")
    return 0


# ==========================================================================
def analyse(cols, nb=5, horizons=HORIZONS, detail=6):
    sec = cols["sec"]
    fac = derive(cols)
    tg = targets(cols, horizons)

    print("\n" + "=" * 78)
    print("COVERAGE")
    print("=" * 78)
    n = len(sec)
    span = (sec[-1] - sec[0]) / 86400.0
    print("  %s seconds, %.2f days, %.1f%% of the wall clock covered"
          % (format(n, ","), span, 100.0 * n / max(span * 86400, 1)))
    for name in ("dep_tot_usd", "bs_cum5_base", "bs_d5bp_base", "vol60",
                 "sig300_bps"):
        a = cols[name]
        ok = sum(1 for v in a if v == v)
        print("    %-16s present on %s seconds (%.1f%%)"
              % (name, format(ok, ","), 100.0 * ok / n))
    # The Bitstamp trim changed on 2026-08-28. If a bps-band depth ever showed
    # up on a 5-level second the whole depth story would be an artefact of the
    # collector, so this is checked from the cache rather than assumed.
    nl = cols["bs_nlev"]
    deep = sum(1 for v in nl if v == v and v >= BS_DEEP_MIN_LEVELS)
    shallow = sum(1 for v in nl if v == v and v < BS_DEEP_MIN_LEVELS)
    bad = sum(1 for i in range(n)
              if nl[i] == nl[i] and nl[i] < BS_DEEP_MIN_LEVELS
              and cols["bs_d5bp_base"][i] == cols["bs_d5bp_base"][i])
    print("    bitstamp levels: %s deep seconds, %s shallow; "
          "bps-band depth present on a shallow second: %d (must be 0)"
          % (format(deep, ","), format(shallow, ","), bad))

    # The raw columns have all been folded into `fac` by now, and on the full
    # tape they are ~170 MB that nothing reads again. The collector outranks
    # this job, so they go back to the allocator here rather than at exit.
    for k in [k for k in cols if k not in ("sec", "brti", "sig300_bps")]:
        del cols[k]

    ranked = {}
    for r in horizons:
        y = tg["mv%d" % r]
        rows = []
        for name in fac:
            f = fac[name]
            idx = valid_idx(f, y)
            if len(idx) < 20000:
                continue
            res = report_factor(name, f, y, idx, nb=nb)
            if res:
                rows.append(res)
        rows.sort(key=lambda z: -(z["p99_ratio"]
                                  if z["p99_ratio"] == z["p99_ratio"] else 0))
        ranked[r] = rows
        print("\n" + "=" * 78)
        print("r = %ds   FACTOR RANKING by conditional-tail lift  "
              "(target: |BRTI(t+%d)-BRTI(t)| in bps)" % (r, r))
        print("=" * 78)
        print("  %-20s %10s %9s %10s %10s %10s %9s"
              % ("factor", "n", "rho", "p99 Q5/Q1", "top lift", "bot lift",
                 "p50 Q5/Q1"))
        for z in rows:
            print("  %-20s %10s %+9.4f %9.2fx %+9.1f%% %+9.1f%% %8.2fx"
                  % (z["name"], format(z["n"], ","), z["rho"],
                     z["p99_ratio"], z["lift_top_pct"], z["lift_bot_pct"],
                     z["p50_ratio"]))

    # full quintile tables for the leaders at the horizon that matters most
    r = horizons[-1]
    y = tg["mv%d" % r]
    print("\n" + "=" * 78)
    print("QUINTILE TABLES at r = %ds -- the practical deliverable" % r)
    print("=" * 78)
    for z in ranked[r][:detail]:
        f = fac[z["name"]]
        idx = valid_idx(f, y)
        print_bucket_table(z, "mv%d" % r)
        dc = day_consistency(f, y, idx, sec, nb=nb)
        if dc:
            pos = sum(1 for v in dc if v == v and v > 1.0)
            print("    per-day p99 ratio over %d days: %s  "
                  "(%d/%d days above 1.0)"
                  % (len(dc), " ".join("%.2f" % v for v in dc), pos, len(dc)))

    # settlement-relevant companion
    print("\n" + "=" * 78)
    print("COMPANION -- the same factors against |mean(next r prints) - now|,")
    print("which is what actually settles, at r = %ds" % r)
    print("=" * 78)
    ya = tg["am%d" % r]
    rows = []
    for name in fac:
        f = fac[name]
        idx = valid_idx(f, ya)
        if len(idx) < 20000:
            continue
        res = report_factor(name, f, ya, idx, nb=nb)
        if res:
            rows.append(res)
    rows.sort(key=lambda z: -(z["p99_ratio"]
                              if z["p99_ratio"] == z["p99_ratio"] else 0))
    print("  %-20s %10s %9s %10s %10s"
          % ("factor", "n", "rho", "p99 Q5/Q1", "top lift"))
    for z in rows:
        print("  %-20s %10s %+9.4f %9.2fx %+9.1f%%"
              % (z["name"], format(z["n"], ","), z["rho"], z["p99_ratio"],
                 z["lift_top_pct"]))

    # does anything survive conditioning on the incumbent sigma?
    print("\n" + "=" * 78)
    print("THE ONLY QUESTION THAT PAYS -- lift WITHIN trailing-sigma terciles")
    print("(a factor that merely reproduces sig300 adds nothing to the model")
    print(" the strategy already runs), at r = %ds" % r)
    print("=" * 78)
    sig = cols["sig300_bps"]
    sidx = valid_idx(sig, y)
    sorder = sorted(sidx, key=lambda i: sig[i])
    terc = []
    for k in range(3):
        lo = (len(sorder) * k) // 3
        hi = (len(sorder) * (k + 1)) // 3
        terc.append(set(sorder[lo:hi]))
    print("  %-20s %12s %12s %12s"
          % ("factor", "calm p99 Q5/Q1", "mid", "stormy"))
    for z in ranked[r][:detail + 4]:
        name = z["name"]
        if name == "sig300_bps":
            continue
        f = fac[name]
        base = valid_idx(f, y)
        out = []
        for k in range(3):
            tk = terc[k]
            idx = [i for i in base if i in tk]
            res = report_factor(name, f, y, idx, nb=nb) if len(idx) > 20000 \
                else None
            out.append(res["p99_ratio"] if res else float("nan"))
        del base
        print("  %-20s %11.2fx %11.2fx %11.2fx"
              % (name, out[0], out[1], out[2]))

    # ---- where the strategy actually stands ------------------------------
    # Everything above is sampled on every second of the tape. pin only acts
    # in the last ~20s before a quarter-hour close, and a factor that works
    # on average but not there is worth nothing to it.
    print("\n" + "=" * 78)
    print("WHERE THE STRATEGY ACTUALLY STANDS -- the same factors restricted")
    print("to the last 20s before a quarter-hour close, r = %ds" % r)
    print("=" * 78)
    late = set()
    for i in range(len(sec)):
        if (int(sec[i]) % 900) >= 880:
            late.add(i)
    print("  %s of %s seconds qualify (%.1f%%)"
          % (format(len(late), ","), format(len(sec), ","),
             100.0 * len(late) / len(sec)))
    print("  %-20s %10s %9s %10s %10s"
          % ("factor", "n", "rho", "p99 Q5/Q1", "top lift"))
    for z in ranked[r][:detail + 4]:
        f = fac[z["name"]]
        idx = [i for i in valid_idx(f, y) if i in late]
        if len(idx) < 5000:
            continue
        res = report_factor(z["name"], f, y, idx, nb=nb)
        if res:
            print("  %-20s %10s %+9.4f %9.2fx %+9.1f%%"
                  % (res["name"], format(res["n"], ","), res["rho"],
                     res["p99_ratio"], res["lift_top_pct"]))
    return ranked, fac, tg


def gaussian_tail_check(cols, fac, tg, horizons=HORIZONS, nb=5):
    """The question in the form the strategy actually asks it.

    p_flip today is Phi(z) with z built on sig300. If the index reaches 37-127
    sigma, the model's tail is not slightly wrong, it is absent. Two things
    are reported here:

      1. how far the move actually gets, in units of the sigma the model
         would have used -- sig300 * sqrt(r), the iid scaling the gaussian
         assumes;
      2. whether CONDITIONING on a factor pulls that maximum in. A factor
         that lowers the worst z in its calm bucket is doing exactly the job
         the strategy needs: it says "right now the tail is shorter than the
         unconditional one, so the threshold can tighten".

    A factor can raise p99 and still not move the max, and vice versa, so
    both are printed."""
    print("\n" + "=" * 78)
    print("HOW BADLY THE GAUSSIAN MISSES, AND WHETHER CONDITIONING HELPS")
    print("=" * 78)
    sig = cols["sig300_bps"]
    for r in horizons:
        y = tg["mv%d" % r]
        idx = valid_idx(sig, y)
        idx = [i for i in idx if sig[i] > 0]
        if len(idx) < 20000:
            continue
        s = math.sqrt(r)
        z = [y[i] / (sig[i] * s) for i in idx]
        z.sort()
        n = len(z)
        # gaussian exceedance for |N(0,1)| -- two-sided
        def gexp(k):
            return n * math.erfc(k / math.sqrt(2.0))
        print("\n  r = %ds   n = %s   max z = %.1f sigma" % (r, format(n, ","),
                                                             z[-1]))
        print("    %6s %12s %12s %10s" % ("z", "observed", "gaussian", "ratio"))
        for k in (3, 4, 5, 6, 8, 10):
            obs = sum(1 for v in z if v >= k)
            exp = gexp(k)
            print("    %6d %12s %12.2f %9.1fx"
                  % (k, format(obs, ","), exp,
                     (obs / exp) if exp > 0 else float("inf")))

    # does conditioning pull the worst case in?
    r = horizons[-1]
    y = tg["mv%d" % r]
    print("\n  Worst z by factor quintile, r = %ds. A factor earns its place" % r)
    print("  if Q1 (calm) carries a materially SHORTER tail than Q5.")
    print("  %-20s %10s %9s %9s %9s %9s %9s"
          % ("factor", "n", "maxz Q1", "Q2", "Q3", "Q4", "maxz Q5"))
    rows = []
    for name in fac:
        f = fac[name]
        idx = [i for i in valid_idx(f, sig, y) if sig[i] > 0]
        if len(idx) < 20000:
            continue
        order = sorted(idx, key=lambda i: f[i])
        s = math.sqrt(r)
        mx = []
        for k in range(nb):
            lo = (len(order) * k) // nb
            hi = (len(order) * (k + 1)) // nb
            mx.append(max(y[i] / (sig[i] * s) for i in order[lo:hi]))
        rows.append((name, len(idx), mx))
    rows.sort(key=lambda t: -(t[2][-1] - t[2][0]))
    for name, nn, mx in rows:
        print("  %-20s %10s %9.1f %9.1f %9.1f %9.1f %9.1f"
              % (name, format(nn, ","), mx[0], mx[1], mx[2], mx[3], mx[4]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feeds", default=r"C:\kals\feed_data")
    ap.add_argument("--data", default=r"C:\kals\kalshi_data")
    ap.add_argument("--cache", default=None)
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--hours", type=int, default=None)
    ap.add_argument("--buckets", type=int, default=5)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc

    cache = a.cache or os.path.join(HERE, "_spotdepth_cache.csv.gz")
    if a.rebuild or not os.path.exists(cache):
        print("BUILDING per-second feature cache ...")
        n = build(a.feeds, a.data, cache, limit_hours=a.hours)
        if not n:
            print("loaded nothing")
            return 0
    cols = load_cache(cache)
    if len(cols["sec"]) < 1000:
        print("loaded nothing: cache has %d rows" % len(cols["sec"]))
        return 0
    fac, tg = analyse(cols, nb=a.buckets)[1:]
    gaussian_tail_check(cols, fac, tg, nb=a.buckets)
    return 0


if __name__ == "__main__":
    sys.exit(main())
