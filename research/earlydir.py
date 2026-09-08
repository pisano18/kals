#!/usr/bin/env python3
# VERSION: 2026-09-08-ed1
"""earlydir.py -- WHICH SIDE IS WRONG: the ticker channel, or the rebuild?

The from-empty orderbook_delta rebuild is missing whatever was resting when
the collector subscribed (proved in earlyverify2's docstring). If THAT is the
whole story, the disagreement has a signature that is not symmetric:

    rebuilt yes_bid <= ticker yes_bid       (rebuild misses resting YES bids)
    rebuilt yes_ask >= ticker yes_ask       (it misses resting NO bids, so its
                                             best no bid is too low and
                                             1-that is too high)
    rebuilt size    <= ticker size at the same price

If instead the ticker channel were throttled or stale, the disagreement would
point both ways about equally, because a stale quote is as likely to be too
high as too low.

It also reports agreement against time since the market's FIRST delta: a
missing base washes out as the pre-subscription orders are filled or
cancelled, so agreement must RISE toward the close. A throttled ticker would
get worse toward the close, where the book moves fastest.
"""
import argparse, calendar, gc, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import earlybook                                            # noqa: E402
import earlyverify                                          # noqa: E402

DELTA = r"C:\kals\kalshi_data\orderbook_delta"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", default="20260906T12,20260903T18,20260830T09")
    a = ap.parse_args()
    meta, (YB, YA, BS, AS, AGE) = earlybook.load()
    W = meta["W"]
    idx = {t: i for i, t in enumerate(meta["order"])}
    mk = meta["markets"]

    print("DIRECTION OF THE DISAGREEMENT  (rebuild starts EMPTY)\n")
    bid_lo = bid_hi = ask_hi = ask_lo = 0
    sz_lo = sz_hi = 0
    bytau = {}
    for stamp in a.files.split(","):
        fp = os.path.join(DELTA, stamp + ".jsonl.gz")
        if not os.path.exists(fp):
            continue
        hs = calendar.timegm((int(stamp[0:4]), int(stamp[4:6]), int(stamp[6:8]),
                              int(stamp[9:11]), 0, 0, 0, 0, 0))
        want = {t: m["close_s"] for t, m in mk.items()
                if hs < m["close_s"] <= hs + 3600}
        reb = earlyverify.rebuild_hour(fp, want)
        for t, close_s in want.items():
            rows = reb.get(t) or []
            if not rows:
                continue
            i = idx[t]
            for tau in range(3, 121):
                k = i * W + tau
                if AGE[k] < 0:
                    continue
                st = earlyverify.state_at(rows, close_s - tau)
                if st is None:
                    continue
                b = bytau.setdefault(tau // 10 * 10, [0, 0])
                b[0] += 1
                if abs(st[1] - YB[k]) < 5e-4 and abs(st[2] - YA[k]) < 5e-4:
                    b[1] += 1
                if abs(st[1] - YB[k]) >= 5e-4:
                    if st[1] < YB[k]:
                        bid_lo += 1
                    else:
                        bid_hi += 1
                if abs(st[2] - YA[k]) >= 5e-4:
                    if st[2] > YA[k]:
                        ask_hi += 1
                    else:
                        ask_lo += 1
                if abs(st[1] - YB[k]) < 5e-4 and abs(st[3] - BS[k]) >= 0.5:
                    if st[3] < BS[k]:
                        sz_lo += 1
                    else:
                        sz_hi += 1
        reb.clear()
        gc.collect()

    def pct(x, y):
        return 100.0 * x / (x + y) if (x + y) else float("nan")

    print("  when the BID price differs:")
    print("    rebuild BELOW ticker (rebuild missing bids): %6d  %5.1f%%"
          % (bid_lo, pct(bid_lo, bid_hi)))
    print("    rebuild ABOVE ticker (ticker would be stale): %6d  %5.1f%%"
          % (bid_hi, pct(bid_hi, bid_lo)))
    print("  when the ASK price differs:")
    print("    rebuild ABOVE ticker (rebuild missing no-bids): %6d  %5.1f%%"
          % (ask_hi, pct(ask_hi, ask_lo)))
    print("    rebuild BELOW ticker (ticker would be stale):   %6d  %5.1f%%"
          % (ask_lo, pct(ask_lo, ask_hi)))
    print("  when the bid PRICE matches but the SIZE differs:")
    print("    rebuild size BELOW ticker (missing base): %6d  %5.1f%%"
          % (sz_lo, pct(sz_lo, sz_hi)))
    print("    rebuild size ABOVE ticker:                %6d  %5.1f%%"
          % (sz_hi, pct(sz_hi, sz_lo)))

    print("\n  AGREEMENT vs TAU (a washing-out base must improve toward close)")
    for tb in sorted(bytau):
        n, ok = bytau[tb]
        print("    tau %3d-%3d : %5.1f%%  (n=%d)" % (tb, tb + 9,
                                                     100.0 * ok / n, n))


if __name__ == "__main__":
    main()
