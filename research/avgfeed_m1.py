#!/usr/bin/env python3
"""M1 residual: where does the exchange's OWN published 60s mean at the close
disagree with the settlement Kalshi actually published?

avgfeed.py found that avg_60s_data at t==close rounds to the published
`settle` on 98.50% of closes.  The other 1.5% is a bigger error source than
anything the avg_60s_data improvement removes, so it gets measured on its own
terms: per series, in units of the half rounding band, and split by whether
OUR raw reconstruction agrees with the exchange's own number.

Read-only.  Post-hoc only -- nothing here feeds a decision.
"""
import collections
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import gzsalvage                                   # noqa: E402
from replay import SERIES_TO_INDEX                 # noqa: E402
from avgfeed import ROUND_DIGITS, read_hour, load_markets, N_AVG  # noqa: E402


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "C:/kals/kalshi_data"
    out = sys.argv[2] if len(sys.argv) > 2 else "C:/kals/fulltape"
    markets = load_markets(os.path.join(out, "markets.json"))
    by_close = {}
    for m in markets:
        by_close.setdefault(m["close"], []).append(m)

    files = sorted(glob.glob(os.path.join(data, "cfbenchmarks_value",
                                          "*.jsonl.gz")))
    ticks, avgs = {}, {}
    rows = []
    import datetime as dt

    def flush(h0):
        for C in sorted(c for c in by_close if h0 <= c < h0 + 3600):
            for m in by_close[C]:
                iid = SERIES_TO_INDEX[m["series"]]
                tk, av = ticks.get(iid), avgs.get(iid)
                if not tk or not av or av.get(C) is None:
                    continue
                if not all(s in tk for s in range(C - N_AVG, C)):
                    continue
                mine = sum(tk[s] for s in range(C - N_AVG, C)) / N_AVG
                rows.append((m["series"], m["ticker"], av[C], mine,
                             m["settle"], m["result"], m["strike"]))

    prev = None
    for fn in files:
        for (iid, sec, raw, avv, ws, we, lv, rx, lws) in read_hour(fn):
            ticks.setdefault(iid, {})[sec] = raw
            if avv is not None:
                avgs.setdefault(iid, {})[sec] = avv
        base = os.path.basename(fn)[:11]
        try:
            h0 = int(dt.datetime.strptime(base, "%Y%m%dT%H")
                     .replace(tzinfo=dt.timezone.utc).timestamp())
        except ValueError:
            continue
        if prev is not None:
            flush(prev)
        prev = h0
        cut = h0 - 4000
        for d_ in (ticks, avgs):
            for iid in d_:
                for s in [s for s in d_[iid] if s < cut]:
                    del d_[iid][s]
    if prev is not None:
        flush(prev)

    print(f"closes with a full 60-print window AND the exchange average: "
          f"{len(rows)}")
    print()
    print(f"  {'series':>10} {'n':>6} {'exch==mine':>11} "
          f"{'exch->settle':>13} {'mine->settle':>13} "
          f"{'|exch-settle| in half-bands  p50 / p95 / max':>44}")
    per = collections.defaultdict(list)
    for r in rows:
        per[r[0]].append(r)
    tot_bad = 0
    bad_rows = []
    for series in sorted(per):
        rs = per[series]
        d = ROUND_DIGITS[series]
        band = 0.5 * (10.0 ** -d)
        same = sum(1 for r in rs if abs(r[2] - r[3]) < 1e-9)
        e_ok = sum(1 for r in rs
                   if abs(round(r[2], d) - r[4]) <= 0.51 * (10.0 ** -d))
        m_ok = sum(1 for r in rs
                   if abs(round(r[3], d) - r[4]) <= 0.51 * (10.0 ** -d))
        hb = sorted(abs(r[2] - r[4]) / band for r in rs)
        n = len(rs)
        print(f"  {series:>10} {n:>6} "
              f"{same:>6} {100.0*same/n:5.1f}% "
              f"{e_ok:>6} {100.0*e_ok/n:5.1f}% "
              f"{m_ok:>6} {100.0*m_ok/n:5.1f}%   "
              f"{hb[n//2]:9.3f} {hb[int(n*0.95)]:9.3f} {hb[-1]:9.3f}")
        tot_bad += n - e_ok
        for r in rs:
            if abs(round(r[2], d) - r[4]) > 0.51 * (10.0 ** -d):
                bad_rows.append((series, r, (r[2] - r[4]) / band))

    print()
    print(f"  closes where the EXCHANGE's own 60s mean does not round to the "
          f"published settle: {tot_bad} / {len(rows)} "
          f"({100.0*tot_bad/max(1,len(rows)):.2f}%)")
    if bad_rows:
        ds = sorted(x[2] for x in bad_rows)
        print(f"  signed (exch - settle) in half-bands: "
              f"p5={ds[int(len(ds)*0.05)]:.2f} p50={ds[len(ds)//2]:.2f} "
              f"p95={ds[int(len(ds)*0.95)]:.2f} min={ds[0]:.2f} "
              f"max={ds[-1]:.2f}")
        pos = sum(1 for x in ds if x > 0)
        print(f"  sign split: {pos} above, {len(ds)-pos} below -- a symmetric "
              f"split means a rounding/precision convention, a one-sided one "
              f"means a different window or a revision")
        print()
        print("  worst 12 by |exch - settle| (half-bands):")
        for series, r, dd in sorted(bad_rows, key=lambda x: -abs(x[2]))[:12]:
            print(f"    {r[1]:<30} exch={r[2]:.8f} settle={r[4]:.8f} "
                  f"diff={dd:+.2f} bands  strike={r[6]}  result={r[5]:.0f}")

    # does the disagreement ever land on the wrong side of the strike?
    flip = 0
    checked = 0
    for series, r, dd in bad_rows:
        d = ROUND_DIGITS[series]
        K = r[6]
        if K is None:
            continue
        checked += 1
        if (round(r[2], d) >= K) != (r[5] >= 0.5):
            flip += 1
    print()
    print(f"  of those, closes where using the exchange average would have "
          f"predicted the WRONG binary outcome: {flip} / {checked}")
    print("  (strike here is the fulltape TRUNCATED strike, so this is an "
          "upper bound on the miscall rate, not an exact one)")


if __name__ == "__main__":
    main()
