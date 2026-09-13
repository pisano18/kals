#!/usr/bin/env python3
# VERSION: 2026-09-13-bk1
"""pinbook.py -- does the ORDER BOOK on the source exchanges warn of a jump?

THE OPERATOR, 2026-09-13: "You can look into that 7gb."

WHAT IT IS. `feed_data/bitstamp` is 8.3 GB of order-book snapshots for the
eight pairs behind the settlement index -- BTC, ETH, XRP, SOL, DOGE, ADA, LTC,
BCH -- roughly 114,000 snapshots an hour, each carrying the top five bids and
asks with sizes, and a `_depth` field saying 100 levels existed behind them.
Recorded since 2026-08-25. Never opened by any analysis in this repository.

WHY IT MIGHT SUCCEED WHERE THE OTHER TWO FAILED. The index lead-lag test failed
(we lag CF, we do not lead it) and exchange disagreement failed (no power,
flipped in the holdout). Both of those used PRICES. This is the first thing
tried that is not a price at all: it is how much SIZE is standing behind the
price, which no price series can contain.

The mechanism worth betting on, stated before the measurement: a jump needs two
things, an order to trade and nothing standing in its way. Price data sees only
the first. If the book thins out -- market makers pulling size -- the same
order moves the price further. That is the standard microstructure story and
this project has never tested it.

THE FIVE FEATURES, all read at T = close - 60, the instant the settlement
window opens, so the bot would have them with at least 30 seconds to spare:

    spread_rel   (best ask - best bid) / mid
    depth5       size in the top five levels each side, valued in dollars
    imbalance    (bid depth - ask depth) / total -- which side is thicker
    touch        size at the best bid and ask only
    withdrawal   depth5 now divided by depth5 sixty seconds earlier.
                 THE ONE I WOULD BET ON: not how thin the book is, but whether
                 it is being PULLED.

The outcome and the scoring are `pinflood`'s -- a flood is a close where the
model missed by more than 3 of its own standard deviations, quintiles are
ranked WITHIN coin, the lift carries a by-close bootstrap, and the MDE is
stated before the estimate. Nothing is reimplemented.

NO KALSHI ORDER BOOK, NO REPLAY, NO FILLS, NO P&L.
"""
import argparse
import glob
import gzip
import json
import math
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pincalib                                                # noqa: E402
import pinflood                                                # noqa: E402
import gzsalvage                                               # noqa: E402

PAIR_TO_INDEX = {
    "btcusd": "BRTI", "ethusd": "ETHUSD_RTI", "xrpusd": "XRPUSD_RTI",
    "solusd": "SOLUSD_RTI", "dogeusd": "DOGEUSD_RTI", "adausd": "ADAUSD_RTI",
    "ltcusd": "LTCUSD_RTI", "bchusd": "BCHUSD_RTI",
}
WINDOW = 60          # the settlement window
BACK = 60            # how far back `withdrawal` looks
KEYS = ("spread_rel", "depth5", "imbalance", "touch", "withdrawal")
FLOOD_Z = 3.0
Z_TAU = 20

MTS = '"microtimestamp":"'
CHAN = '"channel":"order_book_'


def _levels(blob, key, limit=5):
    """[(price, size)] for the first `limit` levels under `key`.

    Parsed off the raw line rather than through json.loads: the feed is 8.3 GB
    and a full parse of every line costs about twenty times this.

    THE FIRST VERSION WAS WRONG and the self-test caught it on the first run.
    It matched `"bids":[[` and then stepped past BOTH brackets, landing inside
    the first pair rather than at the start of it, so it saw a quote where it
    expected `[` and returned nothing at all. A parser that silently returns
    zero levels is the worst kind here -- every close would simply have "no
    book" and the whole study would report a clean null.
    """
    i = blob.find('"%s":[' % key)
    if i < 0:
        return []
    pos = blob.find("[", i + len(key) + 3)
    if pos < 0:
        return []
    pos += 1
    out = []
    n = len(blob)
    while len(out) < limit and pos < n:
        if blob[pos] != "[":
            break
        q1 = blob.find('"', pos)
        q2 = blob.find('"', q1 + 1)
        q3 = blob.find('"', q2 + 1)
        q4 = blob.find('"', q3 + 1)
        if q1 < 0 or q2 < 0 or q3 < 0 or q4 < 0:
            break
        try:
            out.append((float(blob[q1 + 1:q2]), float(blob[q3 + 1:q4])))
        except ValueError:
            break
        end = blob.find("]", q4)
        if end < 0:
            break
        pos = end + 1
        if pos < n and blob[pos] == ",":
            pos += 1
    return out


def tape_range(data_dir):
    """(first, last) epoch seconds covered by the index tape, FROM THE FILE
    NAMES.

    THE WHOLE POINT IS NOT LOADING THE INDEX. The first version of this file
    called replay.load_index() just to find out which seconds to keep, which
    holds all twelve series -- about 2.5 GB -- for the entire duration of an
    8.3 GB book scan. The job was killed for memory, and CLAUDE.md's resource
    protocol exists because an analysis job once OOM-killed the COLLECTOR, and
    the tape is unreproducible while an analysis result is not.

    The close grid is every 900 seconds. The tape's range is in the filenames.
    Nothing needs to be decompressed to work out which seconds matter.
    """
    stamps = sorted(os.path.basename(p)[:11] for p in glob.glob(
        os.path.join(data_dir, "cfbenchmarks_value", "*.jsonl.gz")))
    if not stamps:
        return None, None

    def to_epoch(st):
        return int(time.mktime(time.strptime(st, "%Y%m%dT%H"))
                   - time.timezone)
    return to_epoch(stamps[0]), to_epoch(stamps[-1]) + 3600


def wanted_seconds(first, last):
    """The seconds a snapshot is worth keeping: T and T-BACK for every close."""
    keep = set()
    c = first - (first % 900) + 900
    while c <= last:
        keep.add(c - WINDOW)
        keep.add(c - WINDOW - BACK)
        c += 900
    return keep


def load_one_index(data_dir, index_id, say=None):
    """{second: value} for ONE index id -- a twelfth of the memory of loading
    them all, and the reason this file can now run beside the live bot."""
    out = {}
    key = '"%s"' % index_id
    for path in sorted(glob.glob(os.path.join(data_dir, "cfbenchmarks_value",
                                              "*.jsonl.gz"))):
        for line in gzsalvage.iter_lines(path):
            if key not in line:
                continue
            try:
                m = json.loads(line)
            except ValueError:
                continue
            d = m.get("msg") or {}
            if d.get("index_id") != index_id:
                continue
            inner = d.get("data")
            if isinstance(inner, str):
                try:
                    inner = json.loads(inner)
                except ValueError:
                    continue
            if not isinstance(inner, dict):
                continue
            try:
                out[int(round(float(inner["time"]) / 1000.0))] = float(
                    inner["value"])
            except (KeyError, TypeError, ValueError):
                continue
    if say:
        say("    %s: %d seconds" % (index_id, len(out)))
    return out


def scan(feed_dir, keep_secs, say=print):
    """{(pair, second): (bid_px, bid_sz, ask_px, ask_sz, bid5, ask5)}.

    Last snapshot at or before each wanted second wins, which is what the bot
    would have had. Only the wanted seconds are held, so 8.3 GB of book becomes
    a few hundred thousand tuples.
    """
    out = {}
    files = sorted(glob.glob(os.path.join(feed_dir, "bitstamp",
                                          "*.jsonl.gz")))
    seen = kept = 0
    stats = {}
    for n, path in enumerate(files):
        for line in gzsalvage.iter_lines(path, stats=stats):
            seen += 1
            i = line.find(MTS)
            if i < 0:
                continue
            try:
                sec = int(line[i + len(MTS):i + len(MTS) + 10])
            except ValueError:
                continue
            if sec not in keep_secs:
                continue
            j = line.find(CHAN)
            if j < 0:
                continue
            pair = line[j + len(CHAN):line.find('"', j + len(CHAN))]
            if pair not in PAIR_TO_INDEX:
                continue
            bids = _levels(line, "bids")
            asks = _levels(line, "asks")
            if not bids or not asks:
                continue
            b5 = sum(p * s for p, s in bids)
            a5 = sum(p * s for p, s in asks)
            out[(pair, sec)] = (bids[0][0], bids[0][1], asks[0][0],
                                asks[0][1], b5, a5)
            kept += 1
        if say and (n + 1) % 60 == 0:
            say("    ...%d/%d book hours, %d snapshots held of %d lines"
                % (n + 1, len(files), len(out), seen))
    if say:
        say("    book: %d files, %d lines, %d snapshots held%s"
            % (len(files), seen, len(out),
               (", %d salvaged" % stats.get("salvaged_files", 0))
               if stats.get("salvaged_files") else ""))
    return out


def features(book, pair, close_s):
    """The five features at T = close - 60, or None."""
    T = close_s - WINDOW
    cur = book.get((pair, T))
    if not cur:
        return None
    bpx, bsz, apx, asz, b5, a5 = cur
    mid = 0.5 * (bpx + apx)
    if mid <= 0 or (b5 + a5) <= 0:
        return None
    f = {"spread_rel": (apx - bpx) / mid,
         "depth5": b5 + a5,
         "imbalance": (b5 - a5) / (b5 + a5),
         "touch": bpx * bsz + apx * asz}
    prev = book.get((pair, T - BACK))
    if prev and (prev[4] + prev[5]) > 0:
        f["withdrawal"] = (b5 + a5) / (prev[4] + prev[5])
    return f


def build(data_dir, book, z_tau=Z_TAU, say=print):
    """pinflood-shaped rows: [(close, pair, features, |z|)].

    ONE COIN AT A TIME, released before the next is read. The book dict is
    already in memory; holding twelve index series alongside it is what got the
    first version killed.
    """
    rows = []
    n_noz = n_nofeat = 0
    for pair, iid in PAIR_TO_INDEX.items():
        ser = load_one_index(data_dir, iid, say=say)
        if not ser:
            continue
        lo, hi = min(ser), max(ser)
        c = lo - (lo % 900) + 900
        while c <= hi:
            r = pincalib.zscore(ser, c, z_tau)
            if r is None:
                n_noz += 1
                c += 900
                continue
            f = features(book, pair, c)
            if f is None:
                n_nofeat += 1
                c += 900
                continue
            rows.append((c, pair, f, abs(r[0])))
            c += 900
        ser.clear()
        del ser
    if say:
        say("  rows: %d (%d closes had no z, %d had no book snapshot at the "
            "window open)" % (len(rows), n_noz, n_nofeat))
    return rows


# ---------------------------------------------------------------------------
def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    raw = ('{"data":{"timestamp":"1789318800","microtimestamp":"178931880000'
           '6324","bids":[["77258.65","0.90423046"],["77258.23","0.06250000"]'
           ',["77258.19","0.53931711"],["77257.86","0.06250000"],["77257.66",'
           '"0.05000000"],["77250.00","9.99"]],"asks":[["77258.66","1.2787902'
           '9"],["77258.67","0.00133136"],["77259.52","0.05000000"],["77259.6'
           '3","0.06471685"],["77260.35","0.12589109"]],"_depth":{"bids":100,'
           '"asks":100,"kept":5}},"channel":"order_book_btcusd","event":"data"'
           ',"_rx":1789318800.1}')
    b = _levels(raw, "bids")
    a = _levels(raw, "asks")
    ck(len(b) == 5 and len(a) == 5,
       "exactly five levels are read, never the sixth (%d bids, %d asks)"
       % (len(b), len(a)))
    ck(abs(b[0][0] - 77258.65) < 1e-6 and abs(b[0][1] - 0.90423046) < 1e-9,
       "the best bid parses to price AND size (%s)" % (b[0],))
    ck(abs(a[0][0] - 77258.66) < 1e-6,
       "and the best ask (%s)" % (a[0],))
    ck(a[0][0] > b[0][0], "ask above bid, so the sides are not swapped")
    ck(all(b[i][0] >= b[i + 1][0] for i in range(4)),
       "bids come back descending")
    ck(all(a[i][0] <= a[i + 1][0] for i in range(4)),
       "and asks ascending -- if these ever swap, imbalance changes sign and "
       "every conclusion inverts")
    i = raw.find(MTS)
    ck(int(raw[i + len(MTS):i + len(MTS) + 10]) == 1789318800,
       "the second is read off the microtimestamp without parsing the line")
    j = raw.find(CHAN)
    ck(raw[j + len(CHAN):raw.find('"', j + len(CHAN))] == "btcusd",
       "and the pair off the channel")

    # features, and the withdrawal ratio
    book = {("btcusd", 1789318740): (100.0, 1.0, 101.0, 1.0, 500.0, 500.0),
            ("btcusd", 1789318680): (100.0, 1.0, 101.0, 1.0, 1000.0, 1000.0)}
    f = features(book, "btcusd", 1789318740 + WINDOW)
    ck(f is not None, "features compute when the snapshot is there")
    ck(abs(f["withdrawal"] - 0.5) < 1e-9,
       "a book that halved in the last minute reads withdrawal 0.5 (%.3f) -- "
       "that is the feature worth betting on" % f["withdrawal"])
    ck(abs(f["imbalance"]) < 1e-9, "a symmetric book is imbalance 0")
    book2 = dict(book)
    book2[("btcusd", 1789318740)] = (100.0, 1.0, 101.0, 1.0, 900.0, 100.0)
    f2 = features(book2, "btcusd", 1789318740 + WINDOW)
    ck(abs(f2["imbalance"] - 0.8) < 1e-9,
       "and a book nine-tenths on the bid reads +0.8 (%.3f)" % f2["imbalance"])
    ck(features(book, "ethusd", 1789318740 + WINDOW) is None,
       "a pair with no snapshot returns None rather than a guess")

    # NO LOOKAHEAD: the features cannot see inside the settlement window
    want = wanted_seconds(1789318000, 1789319000)
    ck(want and all((s % 900) in (840, 780) for s in want),
       "only close-60 and close-120 are ever requested, both at or before the "
       "window open (%s)" % sorted(s % 900 for s in want))

    # planted world: thin books precede floods
    import random
    rnd = random.Random(5)
    rows = []
    for k in range(600):
        c = 1788700000 + 900 * k
        thin = rnd.random() < 0.3
        z = 9.0 if (thin and rnd.random() < 0.25) else 0.4
        rows.append((c, "btcusd",
                     {"depth5": 100.0 if thin else 1000.0,
                      "withdrawal": 0.4 if thin else 1.0,
                      "spread_rel": 0.001, "imbalance": 0.0, "touch": 5.0},
                     z))
    L, q = pinflood.lift(rows, "withdrawal", flood_z=FLOOD_Z)
    ck(L < 0.6,
       "when a PULLED book precedes floods, the lift points down (%.2fx: "
       "bottom fifth %.1f%%, top fifth %.1f%%) -- a low withdrawal ratio is "
       "the dangerous end" % (L, 100 * q[0][3], 100 * q[-1][3]))
    rows2 = [(r[0], r[1], r[2], 0.4 if rnd.random() > 0.075 else 9.0)
             for r in rows]
    L2, _ = pinflood.lift(rows2, "withdrawal", flood_z=FLOOD_Z)
    lo2, hi2 = pinflood.boot_lift(rows2, "withdrawal", flood_z=FLOOD_Z, b=400)
    ck(lo2 <= 1.0 <= hi2,
       "and with the SAME books but floods scattered at random, the interval "
       "covers 1.0 (%.2f [%.2f, %.2f])" % (L2, lo2, hi2))
    print("pinbook selftest: %d checks OK" % n[0])
    return 0


def report(rows, out_path, say=print, flood_z=FLOOD_Z, window=""):
    lines = []
    w = lines.append
    n = len(rows)
    fl = sum(1 for r in rows if r[3] > flood_z)
    mde = pinflood.mde_lift(rows, flood_z)
    w("# RESULTS_book -- does the order book warn of a jump?")
    w("")
    w("*`research/pinbook.py`, %s. %d coin-closes over %d closes, %s. From "
      "`feed_data/bitstamp` -- 8.3 GB of order-book snapshots on the exchanges "
      "behind the index, never opened before. No Kalshi order book, no replay, "
      "no fills, no P&L.*"
      % (time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), n,
         len({r[0] for r in rows}), window))
    w("")
    w("**This is the first thing tried here that is not a price.** The index "
      "lead-lag test failed and exchange disagreement failed; both used "
      "prices. This is how much SIZE stands behind the price, which no price "
      "series can contain.")
    w("")
    w("Floods: **%d of %d (%.2f%%)**. MDE, stated before the estimate: "
      "**%.2fx**. Under that is NO POWER, not NO EFFECT."
      % (fl, n, 100.0 * fl / max(1, n), mde))
    w("")
    w("| feature | bottom fifth | top fifth | lift | 95% by-close | strength "
      "| beats MDE? |")
    w("|---|---|---|---|---|---|---|")
    scored = []
    for k in KEYS:
        L, q = pinflood.lift(rows, k, flood_z)
        if L != L or L <= 0 or len(q) < 5:
            continue
        lo, hi = pinflood.boot_lift(rows, k, flood_z)
        st = max(L, 1.0 / L)
        clear = (lo > 1.0 or hi < 1.0)
        scored.append((st, L, k, lo, hi, q))
        w("| `%s` | %.2f%% | %.2f%% | **%.2fx** | [%.2f, %.2f] | %.2fx | %s |"
          % (k, 100 * q[0][3], 100 * q[-1][3], L, lo, hi, st,
             "**yes**" if (clear and st >= mde) else "no"))
    w("")
    scored.sort(reverse=True)
    if scored:
        st, L, k, lo, hi, q = scored[0]
        ok = st >= mde and (lo > 1.0 or hi < 1.0)
        w("Strongest: **`%s`**, lift %.2fx [%.2f, %.2f], strength %.2fx "
          "against an MDE of %.2fx. %s"
          % (k, L, lo, hi, st, mde,
             "**Clears the bar.**" if ok else
             "**Does not clear it** -- no power, not no effect."))
        if ok:
            w("")
            w("| fifth of `%s` | coin-closes | floods | flood rate |" % k)
            w("|---|---|---|---|")
            for qi, nn, f_, rate, med in q:
                w("| %d | %d | %d | %.2f%% |" % (qi + 1, nn, f_, 100 * rate))
    w("")
    w("## Holdout")
    w("")
    a, b = pinflood.split_time(rows)
    w("| feature | first 70% | last 30% | same direction? |")
    w("|---|---|---|---|")
    for _st, _L, k, _lo, _hi, _q in scored:
        La, _ = pinflood.lift(a, k, flood_z)
        Lb, _ = pinflood.lift(b, k, flood_z)
        w("| `%s` | %.2fx | %.2fx | %s |"
          % (k, La, Lb, "yes" if (La - 1.0) * (Lb - 1.0) > 0 else "**no**"))
    w("")
    txt = "\n".join(lines) + "\n"
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(txt)
    say(txt)
    return txt


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--feed", default="C:/kals/feed_data")
    ap.add_argument("--data", default="C:/kals/kalshi_data")
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(HERE), "results", "RESULTS_book.md"))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    first, last = tape_range(a.data)
    if first is None:
        print("pinbook: no cfbenchmarks_value on disk -- nothing to analyse")
        return 0
    keep = wanted_seconds(first, last)
    print("  tape spans %s .. %s; %d seconds wanted from the book"
          % (time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(first)),
             time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(last)), len(keep)))
    book = scan(a.feed, keep)
    if not book:
        print("pinbook: no book snapshot landed on a wanted second -- nothing "
              "to analyse")
        return 0
    rows = build(a.data, book)
    if not rows:
        print("pinbook: no close had both a z-score and a book snapshot -- "
              "nothing to analyse")
        return 0
    lo = min(r[0] for r in rows)
    hi = max(r[0] for r in rows)
    report(rows, a.out,
           window="%s .. %s (%.1f days)"
                  % (time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(lo)),
                     time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(hi)),
                     (hi - lo) / 86400.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
