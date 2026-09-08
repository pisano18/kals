#!/usr/bin/env python3
# VERSION: 2026-09-08-ev2
"""earlyverify2.py -- validate the ticker top-of-book AFTER repairing the
delta rebuild's missing base.

WHAT THE FIRST ATTEMPT FOUND, AND WHY IT WAS THE REBUILD THAT WAS WRONG

earlyverify.py rebuilt each market's book from orderbook_delta starting
empty and agreed with the ticker channel only 78% of the time. The cause is
not the ticker channel:

  * the delta stream is complete -- 13 seq gaps in 2,205,782 messages in the
    hour tested, and each gap is exactly the orderbook_snapshot messages,
    which the collector writes to a different file.
  * the collector writes every frame verbatim (kalshi_collector.py:348), and
    the orderbook_snapshot frames it wrote carry ONLY market_ticker and
    market_id -- 159 snapshot lines in that hour, 0 with level arrays.
  * so a rebuild that starts empty starts in the wrong place. For
    KXBTC15M-26SEP060815-15, a market that opened at 12:00:00, the FIRST
    delta on tape is `no 0.39 delta_fp -75.00` at 12:00:54: 75 contracts
    were already resting there before the collector was subscribed.
    14,366 level-negative events across 15 markets in one hour say the same.

CONSEQUENCE BEYOND THIS FILE: any depth or queue number in this repository
produced by replaying orderbook_delta from an empty book is biased low by
whatever was resting at subscribe time.

THE REPAIR, AND IT IS VALIDATION-ONLY
  Per (market, side, price), take the running sum of deltas over the whole
  hour and seed the level with max(0, -min(running)). That is the smallest
  base consistent with a book that never goes negative, so the repaired book
  is a LOWER BOUND on the truth.

  IT USES THE WHOLE FILE, INCLUDING THE FUTURE. That is deliberate and it is
  confined to this file, which decides nothing and trades nothing -- it only
  asks whether the ticker channel reports the touch faithfully. No backtest
  imports it.
"""
import argparse, calendar, gc, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gzsalvage                                            # noqa: E402
import earlybook                                            # noqa: E402
import earlyverify                                          # noqa: E402

DELTA = r"C:\kals\kalshi_data\orderbook_delta"


def rebuild_repaired(fp, want):
    raw = {t: [] for t in want}
    for line in gzsalvage.iter_lines(fp):
        if '"orderbook_delta"' not in line:
            continue
        try:
            m = json.loads(line)["msg"]
        except Exception:
            continue
        tk = m.get("market_ticker")
        if tk not in raw:
            continue
        p = m.get("price_dollars")
        p = round(float(p) if p is not None else float(m.get("price", 0))/100.0, 4)
        dv = m.get("delta_fp")
        dv = float(dv) if dv is not None else float(m.get("delta", 0))
        raw[tk].append((int(m.get("ts_ms", 0)) // 1000,
                        str(m.get("side", "")).lower(), p, dv))

    out = {}
    for tk, ev in raw.items():
        if not ev:
            continue
        run, mn = {}, {}
        for ts, side, p, dv in ev:
            k = (side, p)
            run[k] = run.get(k, 0.0) + dv
            if run[k] < mn.get(k, 0.0):
                mn[k] = run[k]
        base = {k: -v for k, v in mn.items() if v < 0}
        y, n = {}, {}
        for (side, p), b in base.items():
            (y if side == "yes" else n)[p] = b
        rows, last = [], None
        for ts, side, p, dv in ev:
            bk = y if side == "yes" else n
            bk[p] = bk.get(p, 0.0) + dv
            if bk[p] <= 0.0005:
                bk.pop(p, None)
            byb = max(y) if y else 0.0
            bnb = max(n) if n else 0.0
            rec = (ts, byb, (1.0 - bnb) if n else 1.0,
                   y.get(byb, 0.0), n.get(bnb, 0.0))
            if last != rec[1:]:
                rows.append(rec)
                last = rec[1:]
        out[tk] = rows
    raw.clear()
    gc.collect()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", default="20260906T12,20260903T18,20260830T09")
    a = ap.parse_args()
    meta, (YB, YA, BS, AS, AGE) = earlybook.load()
    W = meta["W"]
    idx = {t: i for i, t in enumerate(meta["order"])}
    mk = meta["markets"]

    print("VERIFY 2 -- ticker vs the BASE-REPAIRED delta rebuild\n")
    grand = [0, 0, 0]
    for stamp in a.files.split(","):
        fp = os.path.join(DELTA, stamp + ".jsonl.gz")
        if not os.path.exists(fp):
            print("  missing %s" % fp)
            continue
        hs = calendar.timegm((int(stamp[0:4]), int(stamp[4:6]), int(stamp[6:8]),
                              int(stamp[9:11]), 0, 0, 0, 0, 0))
        want = {t: m["close_s"] for t, m in mk.items()
                if hs < m["close_s"] <= hs + 3600}
        reb = rebuild_repaired(fp, want)
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
                st = earlyverify.state_at(rows, close_s - tau)
                if st is None:
                    continue
                n += 1
                okp += (abs(st[1] - YB[k]) < 5e-4 and abs(st[2] - YA[k]) < 5e-4)
                oks += (abs(st[3] - BS[k]) < 0.5 and abs(st[4] - AS[k]) < 0.5)
        if n:
            print("  %s : %d markets, %d cells -- prices %5.2f%%  sizes %5.2f%%"
                  % (stamp, len(want), n, 100.0*okp/n, 100.0*oks/n))
            grand[0] += n
            grand[1] += okp
            grand[2] += oks
        reb.clear()
        gc.collect()
    if grand[0]:
        print("\n  TOTAL %d cells : touch prices %.2f%%  touch sizes %.2f%%"
              % (grand[0], 100.0*grand[1]/grand[0], 100.0*grand[2]/grand[0]))


if __name__ == "__main__":
    main()
