#!/usr/bin/env python3
# VERSION: 2026-09-07-d1
"""densample.py -- log the LIP qualifying denominator, live, once a minute.

WHY THIS EXISTS
  Every scaling number in this project was measured between 03:00 and 04:00 ET
  on US Labor Day -- plausibly the thinnest books of the year. The obvious
  check, replaying busy hours from tape, is IMPOSSIBLE: the collector was only
  subscribed to the five commodity families on 2026-09-06 at 18:00 ET, so no
  weekday or daytime commodity tape exists at all.

  So the question can only be answered forward. This appends one row per family
  per side per minute to a CSV and gets out of the way.

WHAT IT MEASURES
  The filing's procedure verbatim: walk down from the best bid, adding EACH
  PRICE LEVEL WHOLE to the qualifying set; the Reference Price is the first
  level at which cumulative size reaches one fifth of Target Size; the walk
  STOPS once cumulative size reaches Target Size. Score is
  size x discount^ticks_below_reference, summed over qualifying bids only.

  The denominator that results is what our share is measured against, so its
  variation across the day IS the scaling question.

DELIBERATELY TINY
  Read-only. No order endpoint is reachable from here. Holds one book at a
  time, appends a line, drops it. Two prior replays were OOM-killed on this box
  and the collector outranks every analysis job.
"""
import argparse
import datetime as dt
import io
import os
import sys
import time

sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
from kauth import get

FAMS = ["KXNATGAS15M", "KXCOPPER15M", "KXSILVER15M", "KXWTI15M", "KXGOLD15M",
        "KXCRYPTOLEAD15M"]
DISC = 0.50
OUT = r"C:\kals-repo\results\denominator_log.csv"

_GRID = {}


def grid(fam):
    if fam in _GRID:
        return _GRID[fam]
    st, b = get("/markets", {"series_ticker": fam, "status": "settled",
                             "limit": "3"})
    rs = []
    for m in (b or {}).get("markets", []):
        rs = m.get("price_ranges") or []
        break
    bands = [(float(r["start"]), float(r["end"]), float(r["step"]))
             for r in rs] or [(0.0, 1.0, 0.01)]
    _GRID[fam] = bands
    return bands


def ticks(bands, ref, p):
    if p >= ref - 1e-9:
        return 0

    def step_at(q):
        for a, b, s in bands:
            if a - 1e-9 <= q < b - 1e-9:
                return s
        return bands[-1][2]
    n, q = 0, p
    while q < ref - 1e-9 and n < 5000:
        q += step_at(q)
        n += 1
    return n


def walk(levels, bands, target):
    """Returns (ref, qualifying_score, qualifying_size, n_levels) or Nones."""
    lv = sorted(levels, reverse=True)
    cum, ref, qual = 0.0, None, []
    for p, s in lv:
        cum += s
        qual.append((p, s))
        if ref is None and cum >= target / 5.0:
            ref = p
        if cum >= target:
            break
    else:
        return None, 0.0, cum, 0          # never reached target -> excluded
    if ref is None:
        return None, 0.0, cum, 0
    sc = sum(s * (DISC ** ticks(bands, ref, p)) for p, s in qual)
    return ref, sc, cum, len(qual)


def selftest():
    print("SELF-TEST")
    bands = [(0.0, 1.0, 0.01)]
    # a level is added WHOLE, then the stop is checked -- so a single level
    # holding more than the target puts ALL of it in the denominator
    r, sc, cum, nl = walk([(0.50, 900.0)], bands, 300.0)
    print(f"  one level of 900 vs target 300 -> ref {r}, qualifying size {cum},"
          f" score {sc}, levels {nl}")
    ok = (r == 0.50 and cum == 900.0 and abs(sc - 900.0) < 1e-9 and nl == 1)
    if not ok:
        print("  *** FAILED: the whole level must qualify, not 300 of it ***")
        return False
    # never reaching target -> nobody qualifies
    r2, _, _, _ = walk([(0.50, 100.0), (0.49, 50.0)], bands, 300.0)
    print(f"  book of 150 vs target 300 -> ref {r2} (expect None: excluded)")
    if r2 is not None:
        print("  *** FAILED: a book under target must exclude ***")
        return False
    # reference is NOT the touch when the touch is small
    r3, _, _, _ = walk([(0.95, 2.0), (0.94, 29.0), (0.93, 2040.0)], bands, 300.0)
    print(f"  touch of 2 contracts -> ref {r3} (expect 0.93)")
    if r3 != 0.93:
        print("  *** FAILED ***")
        return False
    print("SELF-TEST PASSED\n")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--minutes", type=int, default=1440)
    ap.add_argument("--gap", type=float, default=60.0)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")

    if not os.path.exists(OUT):
        with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
            f.write("utc,family,ticker,side,target,ref,qual_score,qual_size,"
                    "levels,book_depth,share_at_20\n")
    end = time.time() + a.minutes * 60
    rows = 0
    while time.time() < end:
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        lines = []
        for fam in FAMS:
            try:
                st, b = get("/markets", {"series_ticker": fam,
                                         "status": "open", "limit": "2"})
                mk = (b or {}).get("markets", [])
            except Exception:
                continue
            for m in mk[:1]:
                tgt = 1000.0 if fam == "KXCRYPTOLEAD15M" else 300.0
                try:
                    st2, ob = get("/markets/" + m["ticker"] + "/orderbook",
                                  {"depth": "80"})
                except Exception:
                    continue
                o = (ob or {}).get("orderbook_fp") or {}
                bands = grid(fam)
                for side, key in (("yes", "yes_dollars"), ("no", "no_dollars")):
                    lv = [(round(float(p), 4), float(s))
                          for p, s in (o.get(key) or []) if float(s) > 0.005]
                    ref, sc, cum, nl = walk(lv, bands, tgt)
                    depth = sum(s for _, s in lv)
                    share = (20.0 / (sc + 20.0)) if ref is not None else 0.0
                    lines.append(f"{now},{fam},{m['ticker']},{side},{tgt:.0f},"
                                 f"{'' if ref is None else f'{ref:.4f}'},"
                                 f"{sc:.2f},{cum:.2f},{nl},{depth:.2f},"
                                 f"{share:.5f}")
        if lines:
            with io.open(OUT, "a", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(lines) + "\n")
            rows += len(lines)
            print(f"  {now}  +{len(lines)} rows (total {rows})", flush=True)
        time.sleep(a.gap)


if __name__ == "__main__":
    main()
