#!/usr/bin/env python3
"""How often is the SECOND buy of a close on the SAME ticker as the first?

Read-only replay of the LIVE rule (pinrun.py v d6826548c653) over
results/pindata/rows.jsonl -- the same 28,479 replayed tradeable moments
pinbook.py uses. Sends nothing, touches nothing.

The live loop keys `fired` on close_s, which pools every series settling on
that quarter hour, so the second buy may land on the same ticker (open_pos
OVERWRITES) or a different one (open_pos keeps both). This measures the split.
"""
import sys, os, json, collections
sys.path.insert(0, r"C:\kals-repo\research")
import pinbook as P

rows = [P.derive(json.loads(l)) for l in
        open(P.ROWS, encoding="utf-8") if l.strip()]
LIVE_SIZE = 5.0                       # --size 5, so the level must hold >= 5
def elig(r):
    return (P.TAU_MIN <= r["tau"] <= P.TAU_MAX and r["pw"] >= P.PIN
            and r["edge"] >= P.EDGE_FLOOR and r["price"] <= P.PRICE_CEILING
            and r["ev"] >= P.EV_FLOOR
            and r["size"] >= max(P.MIN_LEVEL, LIVE_SIZE))

el = [r for r in rows if elig(r)]
byclose = collections.defaultdict(list)
for r in el:
    byclose[r["close"]].append(r)

n_close = n_two = n_same = n_diff = 0
same_pairs = []
for cs, rs in byclose.items():
    rs.sort(key=lambda r: (r["sec"], r["tk"]))     # live order: second, then scan order
    fired = []                                     # (tk, price)
    for r in rs:
        if len(fired) >= 2:                        # MAX_PER_CLOSE
            break
        if fired and r["price"] >= min(p for _, p in fired) - P.IMPROVE_BY:
            continue
        fired.append((r["tk"], r["price"]))
    if not fired:
        continue
    n_close += 1
    if len(fired) == 2:
        n_two += 1
        if fired[0][0] == fired[1][0]:
            n_same += 1
            same_pairs.append((cs, fired[0][0], fired[0][1], fired[1][1]))
        else:
            n_diff += 1

print(f"eligible rows (live gate, size>=5)   {len(el)}")
print(f"closes that fire at least once       {n_close}")
print(f"closes that fire TWICE               {n_two}  ({100*n_two/max(1,n_close):.1f}% of fired closes)")
print(f"   second buy on the SAME ticker     {n_same}  ({100*n_same/max(1,n_two):.1f}% of doubled closes)")
print(f"   second buy on a DIFFERENT ticker  {n_diff}")
print(f"OVERWRITE RATE per fired close       {100*n_same/max(1,n_close):.1f}%")
print()
for cs, tk, p1, p2 in same_pairs[:12]:
    print(f"   close {cs}  {tk}  {p1:.4f} -> {p2:.4f}")
