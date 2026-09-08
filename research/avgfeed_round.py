"""Is Kalshi's settle = ROUND-HALF-UP of the exchange's own 60s mean?

avgfeed_m1.py found 132/8738 closes where round(avg60, d) != settle, and
EVERY ONE sits at exactly -1.00 half-bands: the mean lands exactly on the
rounding tie.  Python's round() is half-to-EVEN.  If Kalshi is half-UP the
disagreement should vanish completely.  If it does not, there is a real
data problem and this is the wrong explanation.
"""
import decimal
import glob
import os
import sys
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from replay import SERIES_TO_INDEX                             # noqa: E402
from avgfeed import ROUND_DIGITS, read_hour, load_markets, N_AVG  # noqa: E402


def half_up(v, d):
    return float(decimal.Decimal(repr(v)).quantize(
        decimal.Decimal(1).scaleb(-d), rounding=decimal.ROUND_HALF_UP))


def half_even(v, d):
    return round(v, d)


def main():
    markets = load_markets("C:/kals/fulltape/markets.json")
    by_close = {}
    for m in markets:
        by_close.setdefault(m["close"], []).append(m)
    files = sorted(glob.glob("C:/kals/kalshi_data/cfbenchmarks_value/*.jsonl.gz"))
    ticks, avgs = {}, {}
    n = 0
    hit = {"half_up_exch": 0, "half_even_exch": 0,
           "half_up_mine": 0, "half_even_mine": 0}
    reldiff = []

    def flush(h0):
        nonlocal n
        for C in sorted(c for c in by_close if h0 <= c < h0 + 3600):
            for m in by_close[C]:
                iid = SERIES_TO_INDEX[m["series"]]
                tk, av = ticks.get(iid), avgs.get(iid)
                if not tk or not av or av.get(C) is None:
                    continue
                if not all(s in tk for s in range(C - N_AVG, C)):
                    continue
                d = ROUND_DIGITS[m["series"]]
                mine = sum(tk[s] for s in range(C - N_AVG, C)) / N_AVG
                e = av[C]
                st = m["settle"]
                n += 1
                tol = 0.51 * (10.0 ** -d)
                hit["half_up_exch"] += abs(half_up(e, d) - st) <= tol
                hit["half_even_exch"] += abs(half_even(e, d) - st) <= tol
                hit["half_up_mine"] += abs(half_up(mine, d) - st) <= tol
                hit["half_even_mine"] += abs(half_even(mine, d) - st) <= tol
                reldiff.append(abs(e - mine) / max(1e-12, abs(e)))

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

    print(f"closes compared: {n}")
    for k in ("half_even_exch", "half_up_exch",
              "half_even_mine", "half_up_mine"):
        print(f"  {k:>16} matches published settle: {hit[k]:>6}/{n} "
              f"({100.0*hit[k]/n:.3f}%)")
    r = sorted(reldiff)
    print(f"\n  |exchange avg60 - our own 60-print mean|, RELATIVE:")
    print(f"    p50={r[len(r)//2]:.3e}  p95={r[int(len(r)*0.95)]:.3e}  "
          f"max={r[-1]:.3e}   (8-decimal publication precision is the floor)")


if __name__ == "__main__":
    main()
