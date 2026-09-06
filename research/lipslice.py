"""Our realistic slice of Kalshi's Liquidity Incentive Program, MEASURED.

Rules, from Kalshi's help centre:
  * Target Size is "the depth that must be resting on each side for a snapshot
    to count" -- AGGREGATE market depth, not per participant.
  * Snapshots once per second. Excluded if the market is closed or EITHER side
    is below Target Size. Reward scales by non-excluded / total.
  * Reference Price: "walking down from the best bid, the first price level at
    which cumulative resting size reaches one fifth of the Target Size".
  * Raw score = size x multiplier; 1.0 at or better than the Reference Price,
    else discount_factor ^ ticks away. bps 5000 -> 0.50, halving per tick.
  * Your share = your raw score / total raw score on that side, pro rata.

BUG FIXED FROM THE FIRST ATTEMPT: ts_ms lives inside `msg`, not at the top
level of the record. Reading it from the top level made every timestamp None,
collapsed every second to 0, and produced exactly one sample per market -- from
which the first run wrongly concluded "no snapshot ever qualified".

orderbook_snapshot messages for this series carry NO level arrays at all (just
market_ticker and market_id), which is correct: a 15-minute market opens with
an empty book. The book is therefore built from deltas alone.
"""
import glob
import gzip
import json
import os
import sys
from collections import defaultdict

DATA = r"C:\kals\kalshi_data"
SERIES = "KXCRYPTOLEAD15M"
TARGET = 1000.0
DISC = 0.50
PERIOD_REWARD = 20.00
DAYS = ["20260905", "20260906"]

ev = defaultdict(list)
for ch, kind in (("orderbook_snapshot", "S"), ("orderbook_delta", "D")):
    for d_ in DAYS:
        for fp in sorted(glob.glob(os.path.join(DATA, ch, d_ + "T*.jsonl.gz"))):
            try:
                for line in gzip.open(fp, "rt"):
                    if SERIES not in line:
                        continue
                    try:
                        m = json.loads(line)
                    except Exception:
                        continue
                    d = m.get("msg") or {}
                    tk = d.get("market_ticker")
                    if not tk:
                        continue
                    ts = d.get("ts_ms") or m.get("_rx_ms")   # <-- the fix
                    ev[tk].append((m.get("seq") or 0, kind, d, ts))
            except Exception:
                continue
print(f"  {len(ev)} {SERIES} markets, "
      f"{sum(len(v) for v in ev.values()):,} book events")
if not ev:
    sys.exit("no data")


def score_side(book, target=TARGET, disc=DISC):
    lv = sorted(((p, s) for p, s in book.items() if s > 0), reverse=True)
    if not lv:
        return 0.0, 0.0
    depth = sum(s for _, s in lv)
    cum = 0.0
    ref = lv[-1][0]
    for p, s in lv:
        cum += s
        if cum >= target / 5.0:
            ref = p
            break
    tot = 0.0
    for p, s in lv:
        if p >= ref - 1e-9:
            tot += s
        else:
            tot += s * (disc ** max(int(round((ref - p) * 100.0)), 0))
    return tot, depth


inc = exc = 0
snaps = []
dep_y, dep_n = [], []
for tk, evs in ev.items():
    evs.sort(key=lambda x: x[0])
    yes, no = {}, {}
    last = None
    for seq, kind, d, ts in evs:
        if kind == "S":
            yes, no = {}, {}
        else:
            p = d.get("price_dollars", d.get("price"))
            if p is None:
                continue
            p = float(p)
            if p > 1.5:
                p /= 100.0
            p = round(p, 4)
            dl = float(d.get("delta_fp") or d.get("delta") or 0.0)
            bk = yes if str(d.get("side", "")).lower() == "yes" else no
            bk[p] = bk.get(p, 0.0) + dl
            if bk[p] <= 0:
                bk.pop(p, None)
        if ts is None:
            continue
        sec = int(ts) // 1000
        if sec == last:
            continue
        last = sec
        ys, yd = score_side(yes)
        ns, nd = score_side(no)
        dep_y.append(yd)
        dep_n.append(nd)
        if yd >= TARGET and nd >= TARGET:
            inc += 1
            snaps.append((ys, ns))
        else:
            exc += 1

tot = inc + exc
print(f"\n  snapshots reconstructed: {tot:,}  "
      f"({tot / max(len(ev),1):.0f} per market)")
print(f"    INCLUDED (both sides >= {TARGET:.0f}): {inc:,} "
      f"({100.0 * inc / max(tot,1):.1f}%)")
print(f"    excluded                            : {exc:,} "
      f"({100.0 * exc / max(tot,1):.1f}%)")


def g(v, f):
    v = sorted(v)
    return v[min(len(v) - 1, int(f * len(v)))] if v else 0.0


print(f"\n  ACTUAL DEPTH SEEN, all snapshots (target is {TARGET:.0f}):")
for lbl, v in (("yes side", dep_y), ("no side", dep_n)):
    print(f"    {lbl}: p10 {g(v,.10):>8.0f}  median {g(v,.50):>8.0f}  "
          f"p75 {g(v,.75):>8.0f}  p90 {g(v,.90):>8.0f}  max {max(v or [0]):>9.0f}")

if not snaps:
    print(f"\n  *** NO SNAPSHOT QUALIFIED at target {TARGET:.0f}. If that")
    print("  holds, the pool is never paid on this series TO ANYONE and the")
    print("  headline pool is not money. Check the depth line above: if the")
    print("  median is far below target, that is the finding.")
    sys.exit(0)

print("\n" + "=" * 78)
print("OUR SLICE if we rest S contracts at the touch on BOTH sides")
print("=" * 78)
print(f"  {'S':>6}{'share/side':>13}{'$/period':>11}{'$/day 1 mkt':>14}"
      f"{'$/day 5 coins':>15}")
for S in (10, 25, 50, 100, 300):
    sh = sum(0.5 * (S / (ys + S)) + 0.5 * (S / (ns + S))
             for ys, ns in snaps) / len(snaps)
    per = sh * PERIOD_REWARD * (inc / max(tot, 1))
    print(f"  {S:>6}{100.0*sh:>12.2f}%{per:>11.4f}{per*96:>14.2f}"
          f"{per*96*5:>15.2f}")
print("\n  96 fifteen-minute windows a day. Coin Race lists 5 coins.")
print("  Two-sided quoting locks capital on BOTH books.")
