"""The LIP score with the TAPERED TICK, which my first implementation got wrong.

Kalshi's rule, verbatim: "Orders priced below the Reference Price get reduced
credit: the Discount Factor raised to the number of TICKS away."

The tick on this exchange is TAPERED -- 0.1c below 10c and above 90c, 1c
between (engine.tick_at, and CLAUDE.md hard rule 5). My first pass computed
ticks as (ref - price) * 100, i.e. 1c everywhere. In the tapered zone that
understates the distance TENFOLD: a 1-cent gap is 10 ticks, so the multiplier
is 0.5^10 = 0.001, not 0.5.

This matters because the live books stack enormous size at 1-2c, and the
reference price often sits down there too. Scoring that size too generously
inflates the DENOMINATOR, which understates our share -- so the first pass was
conservative, but wrong, and "conservative but wrong" is still wrong.

Reports both, side by side, so the size of the error is visible.
"""
import sys

sys.path.insert(0, r"C:\kals-repo\research")
sys.path.insert(0, r"C:\Users\Joe\AppData\Local\Temp\kals-work")
from kauth import get
from engine import tick_at

TARGET = 1000.0
DISC = 0.50
POOL = 20.00


def ticks_between(lo, hi):
    """Number of TICKS from lo up to hi on the tapered grid."""
    if hi <= lo:
        return 0
    n = 0
    p = lo
    while p < hi - 1e-9 and n < 100000:
        p += tick_at(p)
        n += 1
    return n


def score_side(levels, flat_ticks):
    lv = sorted(((float(p), float(s)) for p, s in levels), reverse=True)
    if not lv:
        return 0.0, 0.0, None
    depth = sum(s for _, s in lv)
    cum = 0.0
    ref = lv[-1][0]
    for p, s in lv:
        cum += s
        if cum >= TARGET / 5.0:
            ref = p
            break
    tot = 0.0
    for p, s in lv:
        if p >= ref - 1e-9:
            tot += s
        else:
            t = (int(round((ref - p) * 100.0)) if flat_ticks
                 else ticks_between(p, ref))
            tot += s * (DISC ** max(t, 0))
    return tot, depth, ref


st, b = get("/markets", {"series_ticker": "KXCRYPTOLEAD15M",
                         "status": "open", "limit": "10"})
mks = [m["ticker"] for m in b.get("markets", [])]
print(f"  {len(mks)} live Coin Race markets\n")
print(f"  {'market / side':<26}{'depth':>8}{'ref':>6}"
      f"{'SCORE flat':>12}{'SCORE tapered':>15}{'share flat':>12}"
      f"{'share tapered':>15}")
sf = st_ = 0.0
n = 0
for tk in mks:
    st2, ob = get("/markets/" + tk + "/orderbook", {"depth": "100"})
    if st2 != 200:
        continue
    o = ob.get("orderbook_fp") or {}
    for lbl, lv in (("yes", o.get("yes_dollars") or []),
                    ("no", o.get("no_dollars") or [])):
        a, d, r = score_side(lv, True)
        c, _, _ = score_side(lv, False)
        s1 = 50.0 / (a + 50.0)
        s2 = 50.0 / (c + 50.0)
        sf += s1
        st_ += s2
        n += 1
        print(f"  {tk.split('-')[-1] + '/' + lbl:<26}{d:>8.0f}"
              f"{(r or 0):>6.2f}{a:>12.1f}{c:>15.1f}"
              f"{100*s1:>11.1f}%{100*s2:>14.1f}%")

if n:
    mf, mt = sf / n, st_ / n
    print(f"\n  MEAN share of a side at S=50:")
    print(f"    flat 1c tick (my first pass)  {100*mf:.2f}%")
    print(f"    TAPERED tick (correct)        {100*mt:.2f}%"
          f"   -> {mt/mf:.2f}x")
    print(f"\n  $/day across 5 coins, 96 windows, BEFORE the 28.9% "
          f"qualifying haircut:")
    print(f"    average-of-sides reading:  flat ${POOL*mf*96*5:,.0f}   "
          f"tapered ${POOL*mt*96*5:,.0f}")
    print(f"    AFTER the 28.9% haircut:   flat ${POOL*mf*96*5*0.289:,.0f}   "
          f"tapered ${POOL*mt*96*5*0.289:,.0f}")
    print(f"\n  If 'share of yes PLUS share of no' is literal rather than an")
    print(f"  average, DOUBLE both: tapered becomes "
          f"${POOL*mt*96*5*0.289*2:,.0f}/day. That ambiguity is unresolved.")
