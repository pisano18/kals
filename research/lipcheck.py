"""ARTEFACT CHECK on the LIP slice.

The slice is share = S / (total_score + S). If my delta-reconstructed book is
MISSING resting orders, total_score is too small and the slice is inflated.
That is the one thing that would make $64/day/market fiction.

Independent test: the `ticker` channel publishes yes_bid_size_fp and
yes_ask_size_fp -- top-of-book sizes Kalshi computed itself. My reconstructed
best-level size must match. It is a different feed, produced by the exchange,
so agreement is real corroboration and disagreement is my bug.
"""
import glob
import gzip
import json
import os
from collections import defaultdict

DATA = r"C:\kals\kalshi_data"
SERIES = "KXCRYPTOLEAD15M"
DAY = "20260906"

ev = defaultdict(list)
for ch, kind in (("orderbook_snapshot", "S"), ("orderbook_delta", "D")):
    for fp in sorted(glob.glob(os.path.join(DATA, ch, DAY + "T1[0-3].jsonl.gz"))):
        try:
            for line in gzip.open(fp, "rt"):
                if SERIES not in line:
                    continue
                m = json.loads(line)
                d = m.get("msg") or {}
                tk = d.get("market_ticker")
                if not tk:
                    continue
                ev[tk].append((m.get("seq") or 0, kind, d,
                               d.get("ts_ms") or m.get("_rx_ms")))
        except Exception:
            continue

# reconstructed best bid/ask size per (ticker, second)
recon = {}
for tk, evs in ev.items():
    evs.sort(key=lambda x: x[0])
    yes, no = {}, {}
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
        by = max(yes) if yes else None
        bn = max(no) if no else None
        recon[(tk, sec)] = (
            yes.get(by, 0.0) if by is not None else 0.0,
            no.get(bn, 0.0) if bn is not None else 0.0,
            by, bn)

# ticker's own top-of-book sizes
pairs = []
for fp in sorted(glob.glob(os.path.join(DATA, "ticker", DAY + "T1[0-3].jsonl.gz"))):
    try:
        for line in gzip.open(fp, "rt"):
            if SERIES not in line:
                continue
            m = json.loads(line)
            d = m.get("msg") or {}
            tk = d.get("market_ticker")
            ts = d.get("ts_ms")
            if not tk or ts is None:
                continue
            r = recon.get((tk, int(ts) // 1000))
            if r is None:
                continue
            bsz = d.get("yes_bid_size_fp")
            asz = d.get("yes_ask_size_fp")
            if bsz is None or asz is None:
                continue
            pairs.append((float(bsz), r[0], float(asz), r[1]))
    except Exception:
        continue

print(f"  {len(recon):,} reconstructed market-seconds, "
      f"{len(pairs):,} matched to a ticker message")
if not pairs:
    raise SystemExit("  no overlap -- cannot validate")

ok_b = sum(1 for b, rb, a, ra in pairs if abs(b - rb) <= max(1.0, 0.02 * b))
ok_a = sum(1 for b, rb, a, ra in pairs if abs(a - ra) <= max(1.0, 0.02 * a))
n = len(pairs)
print(f"\n  YES-BID top size: reconstruction matches ticker within 2%  "
      f"{ok_b:,}/{n:,} = {100.0*ok_b/n:.1f}%")
print(f"  YES-ASK top size: reconstruction matches ticker within 2%  "
      f"{ok_a:,}/{n:,} = {100.0*ok_a/n:.1f}%")

from statistics import median
mb = median([rb - b for b, rb, a, ra in pairs])
ma = median([ra - a for b, rb, a, ra in pairs])
print(f"\n  median (reconstructed - ticker): bid {mb:+.1f}  ask {ma:+.1f}")
print("  A large NEGATIVE median means my book is MISSING size, which would")
print("  inflate our modelled share. A large POSITIVE means I am double")
print("  counting, which would deflate it.")
under = sum(1 for b, rb, a, ra in pairs if rb < b * 0.9)
print(f"  reconstructed bid more than 10% BELOW ticker: "
      f"{under:,}/{n:,} = {100.0*under/n:.1f}%")
