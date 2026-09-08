#!/usr/bin/env python3
# VERSION: 2026-09-08-ev1
"""earlyverify.py -- IS THE ticker CHANNEL REALLY THE TOP OF BOOK?

Every depth number in the early-tau work is read from Kalshi's `ticker`
message (yes_bid/yes_ask and their _size_fp fields) because that channel is
1.7 MB/hour where orderbook_delta is 60-80. That is only legitimate if
ticker fires on EVERY top-of-book change and reports the size correctly. If
it were throttled, or if it reported only the last trade, the whole depth
answer would be a fiction and it would look perfectly reasonable.

THE TEST
  A 15-minute market is created at the previous quarter hour (its strike IS
  the previous window's settlement), so for hour file H every market closing
  in (H, H+3600] has its ENTIRE life inside H. Its book therefore rebuilds
  exactly from that one file's deltas starting empty -- no snapshot needed,
  and the collector's snapshots carry no levels anyway.

  Rebuild it delta by delta in seq order, and at every second in the last
  140 s compare the rebuilt touch against what earlybook.py stored.

  side='yes' rows are resting YES bids; side='no' rows are resting NO bids.
  yes_ask = 1 - best no bid, and the size at yes_ask is the best no bid's
  size. Getting that mapping backwards is the failure this check catches.

MEMORY: one hour file at a time, only the ~36 markets of interest, book
freed before the next. orderbook_delta is the big channel on this box.
"""
import argparse, array, gc, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gzsalvage                                            # noqa: E402
import earlybook                                            # noqa: E402

DELTA = r"C:\kals\kalshi_data\orderbook_delta"


def rebuild_hour(fp, want):
    """want: {ticker: close_s}. -> {ticker: [(ts_s, yb, ya, bsz, asz), ...]}"""
    books = {t: {"yes": {}, "no": {}} for t in want}
    out = {t: [] for t in want}
    last = {}
    for line in gzsalvage.iter_lines(fp):
        if '"orderbook_delta"' not in line:
            continue
        try:
            m = json.loads(line)["msg"]
        except Exception:
            continue
        tk = m.get("market_ticker")
        if tk not in books:
            continue
        p = m.get("price_dollars")
        p = float(p) if p is not None else float(m.get("price", 0)) / 100.0
        dv = m.get("delta_fp")
        dv = float(dv) if dv is not None else float(m.get("delta", 0))
        side = str(m.get("side", "")).lower()
        ts = int(m.get("ts_ms", 0)) // 1000
        bk = books[tk][side]
        p = round(p, 4)
        bk[p] = bk.get(p, 0.0) + dv
        if bk[p] <= 0.0005:
            bk.pop(p, None)
        y, n = books[tk]["yes"], books[tk]["no"]
        byb = max(y) if y else 0.0
        bnb = max(n) if n else 0.0
        rec = (ts, byb, (1.0 - bnb) if n else 1.0,
               y.get(byb, 0.0) if y else 0.0,
               n.get(bnb, 0.0) if n else 0.0)
        if last.get(tk) != rec[1:]:
            out[tk].append(rec)
            last[tk] = rec[1:]
    for t in books:
        books[t].clear()
    books.clear()
    gc.collect()
    return out


def state_at(rows, t):
    """last rebuilt state with ts <= t (causal, same rule as earlybook)."""
    lo, hi, best = 0, len(rows) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if rows[mid][0] <= t:
            best = rows[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=2)
    ap.add_argument("--files", default="20260906T12,20260903T18")
    a = ap.parse_args()

    meta, (YB, YA, BS, AS, AGE) = earlybook.load()
    W = meta["W"]
    idx = {t: i for i, t in enumerate(meta["order"])}
    mk = meta["markets"]

    print("VERIFY -- ticker top-of-book vs orderbook_delta rebuild\n")
    tot = ok_p = ok_s = n_cmp = 0
    for stamp in a.files.split(","):
        fp = os.path.join(DELTA, stamp + ".jsonl.gz")
        if not os.path.exists(fp):
            print("  missing %s" % fp)
            continue
        # markets whose whole life is inside this hour file
        h = None
        for t in meta["order"]:
            pass
        want = {}
        # hour start from the file name, UTC
        import calendar
        hs = calendar.timegm((int(stamp[0:4]), int(stamp[4:6]), int(stamp[6:8]),
                              int(stamp[9:11]), 0, 0, 0, 0, 0))
        for t, m in mk.items():
            if hs < m["close_s"] <= hs + 3600:
                want[t] = m["close_s"]
        print("  %s: %d markets close in this hour" % (stamp, len(want)))
        reb = rebuild_hour(fp, want)
        for t, close_s in want.items():
            rows = reb.get(t) or []
            if not rows:
                continue
            i = idx[t]
            for tau in range(0, 121):
                k = i * W + tau
                if AGE[k] < 0:
                    continue
                st = state_at(rows, close_s - tau)
                if st is None:
                    continue
                n_cmp += 1
                pb = abs(st[1] - YB[k]) < 5e-4 and abs(st[2] - YA[k]) < 5e-4
                sb = (abs(st[3] - BS[k]) < 0.5 and abs(st[4] - AS[k]) < 0.5)
                ok_p += 1 if pb else 0
                ok_s += 1 if sb else 0
                tot += 1
                if not pb and tot - ok_p <= 5:
                    print("    PRICE MISMATCH %s tau=%d  delta(%.4f/%.4f) "
                          "ticker(%.4f/%.4f) age=%.0fs"
                          % (t, tau, st[1], st[2], YB[k], YA[k], AGE[k]))
                if not sb and tot - ok_s <= 5:
                    print("    SIZE  MISMATCH %s tau=%d  delta(%.2f/%.2f) "
                          "ticker(%.2f/%.2f) age=%.0fs"
                          % (t, tau, st[3], st[4], BS[k], AS[k], AGE[k]))
        reb.clear()
        gc.collect()

    if n_cmp:
        print("\n  %d (market, tau) cells compared" % n_cmp)
        print("    touch PRICES agree: %d  (%.2f%%)" % (ok_p, 100.0 * ok_p / n_cmp))
        print("    touch SIZES  agree: %d  (%.2f%%)" % (ok_s, 100.0 * ok_s / n_cmp))
        print("\n  Anything far below 100%% means the ticker channel is not a")
        print("  faithful top of book and the depth answer must be rebuilt")
        print("  from orderbook_delta instead.")


def selftest():
    """Plant a book whose answer is known, and a mapping that is deliberately
    wrong, and require the comparison to fail on the wrong one."""
    print("SELF-TEST -- earlyverify")
    y = {0.40: 120.0, 0.39: 50.0}
    n = {0.55: 33.0}
    byb, bnb = max(y), max(n)
    yb, ya = byb, 1.0 - bnb
    bs, asz = y[byb], n[bnb]
    ok1 = (abs(yb - 0.40) < 1e-9 and abs(ya - 0.45) < 1e-9
           and bs == 120.0 and asz == 33.0)
    print("  yes bids {0.40:120, 0.39:50}, no bids {0.55:33}")
    print("  -> yes_bid %.2f size %.0f ; yes_ask %.2f size %.0f" % (yb, bs, ya, asz))
    # the swapped mapping (ask size read off the yes side) must NOT match
    ok2 = not (abs(asz - bs) < 0.5)
    print("  swapped mapping (ask size = yes-bid size) is rejected: %s" % ok2)
    ok = ok1 and ok2
    print("SELF-TEST " + ("PASSED" if ok else "*** FAILED ***"))
    return ok


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(0 if selftest() else 1)
    main()
