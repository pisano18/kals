#!/usr/bin/env python3
# VERSION: 2026-09-08-ec1
"""earlycross.py -- a book-free test of whether the ticker touch is real.

The orderbook_delta rebuild cannot arbitrate the ticker channel, because the
collector never recorded the snapshot levels the deltas are increments on.
The trade channel can, and it needs no book at all.

  A taker who BUYS YES lifts an offer, so the print must be at or above the
  best yes ask standing just before it.
  A taker who BUYS NO  lifts a no offer, i.e. hits the yes bid, so the print
  must be at or below the best yes bid standing just before it.

A print strictly INSIDE the ticker's quoted spread means the ticker touch was
not the real touch. Trades exactly AT the quoted touch mean it was.

The comparison uses the last ticker message with ts_ms STRICTLY BEFORE the
trade's ts_ms, so it can never see the ticker update the trade itself causes.
"""
import argparse, bisect, calendar, gc, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gzsalvage                                            # noqa: E402
import earlybook                                            # noqa: E402

TKDIR = r"C:\kals\kalshi_data\ticker"
TRDIR = r"C:\kals\kalshi_data\trade"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", default="20260906T12,20260903T18,20260830T09")
    ap.add_argument("--taumax", type=int, default=140)
    a = ap.parse_args()
    meta, _ = earlybook.load()
    mk = meta["markets"]
    close_of = {t: m["close_s"] for t, m in mk.items()}

    at = inside = through = 0
    n = 0
    bytau = {}
    for stamp in a.files.split(","):
        q = {}
        fp = os.path.join(TKDIR, stamp + ".jsonl.gz")
        if not os.path.exists(fp):
            continue
        for line in gzsalvage.iter_lines(fp):
            if '"ticker"' not in line:
                continue
            try:
                m = json.loads(line)["msg"]
            except Exception:
                continue
            tk = m.get("market_ticker")
            if tk not in close_of or m.get("ts_ms") is None:
                continue
            b, s = m.get("yes_bid_dollars"), m.get("yes_ask_dollars")
            if b is None or s is None:
                continue
            q.setdefault(tk, []).append((int(m["ts_ms"]), float(b), float(s),
                                         float(m.get("yes_bid_size_fp") or 0),
                                         float(m.get("yes_ask_size_fp") or 0)))
        for tk in q:
            q[tk].sort()
        ts_of = {tk: [r[0] for r in rows] for tk, rows in q.items()}

        fp = os.path.join(TRDIR, stamp + ".jsonl.gz")
        for line in gzsalvage.iter_lines(fp):
            if '"trade"' not in line:
                continue
            try:
                m = json.loads(line)["msg"]
            except Exception:
                continue
            tk = m.get("market_ticker")
            rows = q.get(tk)
            if not rows:
                continue
            ts = int(m.get("ts_ms", 0))
            tau = close_of[tk] - ts // 1000
            if not (0 <= tau <= a.taumax):
                continue
            j = bisect.bisect_left(ts_of[tk], ts) - 1
            if j < 0:
                continue
            _, yb, ya, _, _ = rows[j]
            p = float(m.get("yes_price_dollars"))
            side = m.get("taker_outcome_side") or m.get("taker_side")
            n += 1
            key = min(tau // 20 * 20, 120)
            c = bytau.setdefault(key, [0, 0, 0])
            if side == "yes":
                d = p - ya
            else:
                d = yb - p
            c[0] += 1
            if abs(d) < 5e-4:
                at += 1
                c[1] += 1
            elif d > 0:
                through += 1
                c[2] += 1
            else:
                inside += 1
        q.clear()
        ts_of.clear()
        gc.collect()

    if not n:
        print("  no trades matched")
        return
    print("TRADES vs THE TICKER TOUCH STANDING JUST BEFORE THEM\n")
    print("  %d trades within tau <= %d s of close" % (n, a.taumax))
    print("    printed exactly AT the quoted touch : %8d  %6.2f%%"
          % (at, 100.0 * at / n))
    print("    printed THROUGH it (deeper level)   : %8d  %6.2f%%"
          % (through, 100.0 * through / n))
    print("    printed INSIDE the quoted spread    : %8d  %6.2f%%"
          % (inside, 100.0 * inside / n))
    print("\n  INSIDE is the failure mode: it means the touch the ticker")
    print("  reported was not the real touch.\n")
    print("  by tau bucket:      n        AT%   THROUGH%   INSIDE%")
    for k in sorted(bytau):
        c = bytau[k]
        print("    tau %3d-%3d %8d   %6.2f   %6.2f    %6.2f"
              % (k, k + 19, c[0], 100.0*c[1]/c[0], 100.0*c[2]/c[0],
                 100.0*(c[0]-c[1]-c[2])/c[0]))


if __name__ == "__main__":
    main()
