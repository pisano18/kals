#!/usr/bin/env python3
# VERSION: 2026-09-08-el1
"""earlylag.py -- WHY the ticker grid and the delta rebuild disagree.

earlyverify put ticker/delta agreement at 78% on prices. Before any depth
number is quoted, that has to be explained, because there are three very
different explanations with three different consequences:

  (1) the two channels are stamped on different clocks and the grid is
      simply offset by a second -> harmless, fixable, and the direction
      matters (a grid that is LATE has lookahead; one that is EARLY does not)
  (2) the delta rebuild is wrong because the market's book predates the hour
      file -> the rebuild is the broken side, not ticker
  (3) ticker is throttled and genuinely misses top-of-book changes -> the
      cheap channel cannot answer the depth question at all

It reports agreement as a function of applied lag and of tau, and prints
when each market's first delta arrives relative to its close, which
separates (1) from (2).
"""
import argparse, calendar, gc, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import earlybook                                            # noqa: E402
import earlyverify                                          # noqa: E402

DELTA = r"C:\kals\kalshi_data\orderbook_delta"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", default="20260906T12")
    a = ap.parse_args()
    meta, (YB, YA, BS, AS, AGE) = earlybook.load()
    W = meta["W"]
    idx = {t: i for i, t in enumerate(meta["order"])}
    mk = meta["markets"]

    for stamp in a.files.split(","):
        fp = os.path.join(DELTA, stamp + ".jsonl.gz")
        hs = calendar.timegm((int(stamp[0:4]), int(stamp[4:6]), int(stamp[6:8]),
                              int(stamp[9:11]), 0, 0, 0, 0, 0))
        want = {t: m["close_s"] for t, m in mk.items()
                if hs < m["close_s"] <= hs + 3600}
        reb = earlyverify.rebuild_hour(fp, want)

        print("\n  WHEN DOES A MARKET'S BOOK FIRST APPEAR? "
              "(seconds before its own close)")
        firsts = sorted(want[t] - reb[t][0][0] for t in want if reb.get(t))
        if firsts:
            print("    min %d  p25 %d  median %d  p75 %d  max %d  (n=%d)"
                  % (firsts[0], firsts[len(firsts)//4], firsts[len(firsts)//2],
                     firsts[3*len(firsts)//4], firsts[-1], len(firsts)))
            print("    900 s means the whole life is in this file and the "
                  "rebuild starts from a genuinely empty book.")

        print("\n  AGREEMENT vs APPLIED LAG (ticker cell at tau compared to "
              "the rebuild at tau+lag)")
        for lag in (-3, -2, -1, 0, 1, 2, 3):
            n = okp = oks = 0
            for t, close_s in want.items():
                rows = reb.get(t) or []
                if not rows:
                    continue
                i = idx[t]
                for tau in range(3, 121):
                    k = i * W + tau
                    if AGE[k] < 0:
                        continue
                    st = earlyverify.state_at(rows, close_s - tau - lag)
                    if st is None:
                        continue
                    n += 1
                    okp += (abs(st[1] - YB[k]) < 5e-4
                            and abs(st[2] - YA[k]) < 5e-4)
                    oks += (abs(st[3] - BS[k]) < 0.5
                            and abs(st[4] - AS[k]) < 0.5)
            if n:
                print("    lag %+d s : prices %5.2f%%  sizes %5.2f%%  (n=%d)"
                      % (lag, 100.0*okp/n, 100.0*oks/n, n))

        print("\n  AGREEMENT vs TAU at the best lag (0)")
        buckets = [(3, 10), (10, 20), (20, 30), (30, 45), (45, 60),
                   (60, 90), (90, 121)]
        for lo, hi in buckets:
            n = okp = oks = 0
            for t, close_s in want.items():
                rows = reb.get(t) or []
                if not rows:
                    continue
                i = idx[t]
                for tau in range(lo, hi):
                    k = i * W + tau
                    if AGE[k] < 0:
                        continue
                    st = earlyverify.state_at(rows, close_s - tau)
                    if st is None:
                        continue
                    n += 1
                    okp += (abs(st[1] - YB[k]) < 5e-4
                            and abs(st[2] - YA[k]) < 5e-4)
                    oks += (abs(st[3] - BS[k]) < 0.5
                            and abs(st[4] - AS[k]) < 0.5)
            if n:
                print("    tau %3d-%3d : prices %5.2f%%  sizes %5.2f%%  (n=%d)"
                      % (lo, hi - 1, 100.0*okp/n, 100.0*oks/n, n))
        reb.clear()
        gc.collect()


if __name__ == "__main__":
    main()
