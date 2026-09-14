#!/usr/bin/env python3
"""What does it COST to buy more? -- price impact and fill rate by order size.

THE QUESTION. `SIZE` is capped at 250 and set to bank/5.88. Before spending
real money to grow the bank, we need to know whether the book can absorb a
bigger order at a price that keeps the edge. Two things could go wrong and
they are different: the order might not FILL (depth), or it might fill at a
WORSE AVERAGE PRICE (impact). This measures both.

SOURCE, and why it is allowed. `results/pinlevels_rows.jsonl` -- the cached
candidate rows, 422 book hours, each carrying the ask LADDER it saw. This asks
only "what did the market offer", which is exactly what CLAUDE.md's rule 5
block says the tape IS valid for. It makes no claim about our loss rate, our
fill rate in a race, or what a rule would have cost us. Those come from live
fills only.

WHAT IT DOES NOT MEASURE, stated up front:
  - Whether we WIN the race for those contracts. A crossing IOC fills at the
    resting price, but only if we get there first.
  - Whether deeper fills are adversely selected. Sweeping more levels means
    more of the order rests further from fair, and the counterparty in this
    window is informed (RESULTS_select.md).
  - The close's own contract budget, which binds before any of this.

So read it as a CEILING on what the book allows, not a forecast.

    python research/pincap.py --selftest
    python research/pincap.py
"""
import json
import os
import sys

CEILING = 0.98          # the deployed price ceiling; nothing above it is ours
SIZES = (10, 25, 50, 75, 125, 250, 500)
ROWS = os.path.join("results", "pinlevels_rows.jsonl")


def fee_per_contract(price):
    """Kalshi taker fee, 0.07*p*(1-p), per contract."""
    return 0.07 * float(price) * (1.0 - float(price))


def vwap_fill(ladder, target, ceiling=CEILING):
    """Walk an ascending ask ladder buying up to `target` contracts, never
    paying above `ceiling`.

    Returns (contracts_filled, average_price). (0.0, None) if nothing at or
    under the ceiling. The ceiling stop is a BREAK, not a skip: the ladder is
    ordered, so the first level above the ceiling ends the walk.
    """
    got = 0.0
    cost = 0.0
    for level in ladder or ():
        px = float(level[0])
        sz = float(level[1])
        if px > ceiling + 1e-9:
            break
        take = min(sz, target - got)
        if take <= 0:
            break
        got += take
        cost += take * px
    if got <= 0:
        return 0.0, None
    return got, cost / got


def edge_of(fair, price, want):
    """Edge in dollars per contract after the taker fee, the same arithmetic
    pinrun.net_edge uses at full size."""
    gross = (fair - price) if want == "yes" else ((1.0 - fair) - price)
    return gross - fee_per_contract(price)


def selftest():
    ok = True

    def ck(cond, msg):
        nonlocal ok
        if not cond:
            print("FAIL:", msg)
            ok = False
        else:
            print("  ok:", msg)

    # ---- a world where the answer is known by construction ---------------
    lad = [[0.90, 10.0], [0.95, 40.0], [0.99, 1000.0]]

    got, px = vwap_fill(lad, 10)
    ck(got == 10.0 and abs(px - 0.90) < 1e-12,
       "a 10-lot comes entirely off the 90c level at 90c")

    got, px = vwap_fill(lad, 50)
    ck(got == 50.0 and abs(px - (10 * 0.90 + 40 * 0.95) / 50) < 1e-12,
       "a 50-lot sweeps two levels and pays their weighted mean, 94.0c")

    got, px = vwap_fill(lad, 250)
    ck(got == 50.0 and abs(px - 0.94) < 1e-12,
       "the 99c level is OVER the 98c ceiling, so a 250-lot stops at 50 -- "
       "the ceiling binds before the depth does")

    got, px = vwap_fill([[0.99, 500.0]], 50)
    ck(got == 0.0 and px is None,
       "a ladder entirely above the ceiling fills nothing at all")

    ck(vwap_fill([], 50) == (0.0, None), "an empty ladder fills nothing")
    ck(vwap_fill(None, 50) == (0.0, None), "a missing ladder fills nothing")

    # ---- THE NULL: a world with no price impact planted ------------------
    # One infinitely deep level. Every size must pay the SAME price. An
    # estimator that manufactured impact out of nothing would fail here.
    flat = [[0.95, 10000.0]]
    prices = [vwap_fill(flat, n)[1] for n in SIZES]
    ck(len(set(prices)) == 1 and abs(prices[0] - 0.95) < 1e-12,
       "one infinitely deep level shows EXACTLY ZERO impact at every size -- "
       "the null a fake impact number would trip")

    # ---- and a world where impact IS planted, by a known amount ----------
    steep = [[0.90, 50.0], [0.96, 50.0]]
    _, p50 = vwap_fill(steep, 50)
    _, p100 = vwap_fill(steep, 100)
    ck(abs(p50 - 0.90) < 1e-12 and abs(p100 - 0.93) < 1e-12,
       "planted impact is recovered exactly: 50 pays 90.0c, 100 pays 93.0c")

    # ---- edge arithmetic, both sides -------------------------------------
    ck(abs(edge_of(1.0, 0.95, "yes") - (0.05 - fee_per_contract(0.95))) < 1e-12,
       "a YES edge is fair minus price, after fee")
    ck(abs(edge_of(0.0, 0.95, "no") - (0.05 - fee_per_contract(0.95))) < 1e-12,
       "and a NO edge is (1-fair) minus price -- the mirror, same number")
    ck(edge_of(0.5, 0.95, "yes") < 0,
       "a coin-flip bought at 95c has a NEGATIVE edge")

    print("pincap selftest:", "OK" if ok else "FAILED")
    return ok


def load(path=ROWS, ceiling=CEILING):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("kind") != "row":
                continue
            if d.get("verdict") != "trade":        # pinlevels' own gate
                continue
            if d.get("price", 1.0) > ceiling + 1e-9:
                continue
            if not d.get("ladder"):
                continue
            rows.append(d)
    return rows


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0

    rows = load()
    if not rows:
        print("loaded nothing -- %s is missing or holds no gate-passing rows "
              "with a ladder" % ROWS)
        return 0

    closes = len(set(r["cs"] for r in rows))
    print("\ngate-passing candidate moments with a ladder: %s over %s closes"
          % (f"{len(rows):,}", f"{closes:,}"))
    print("ceiling %.0fc; a moment that cannot fill ONE contract under it is "
          "counted as no fill\n" % (100 * CEILING))

    print("  size |  filled in full | median filled | mean price | mean edge |"
          "   contracts | vs a 50-lot")
    print("  -----|-----------------|---------------|------------|-----------|"
          "-------------|------------")
    ref = None
    for n in SIZES:
        fills = []
        for r in rows:
            got, px = vwap_fill(r["ladder"], n)
            if got <= 0:
                continue
            fills.append((got, px, edge_of(r["fair"], px, r["want"])))
        if not fills:
            continue
        full = sum(1 for g, _, _ in fills if g >= n - 1e-9)
        sizes = sorted(g for g, _, _ in fills)
        total = sum(g for g, _, _ in fills)
        mean_px = sum(g * p for g, p, _ in fills) / total
        mean_ed = sum(g * e for g, _, e in fills) / total
        money = sum(g * e for g, _, e in fills)
        if n == 50:
            ref = money
        rel = ("%9.2fx" % (money / ref)) if ref else "          "
        print("  %4d | %13.1f%% | %13.0f | %9.2fc | %8.3fc | %11s |%s"
              % (n, 100.0 * full / len(rows), sizes[len(sizes) // 2],
                 100 * mean_px, 100 * mean_ed, f"{total:,.0f}", rel))

    print("\n  READ THE LAST COLUMN AS A CEILING, NOT A FORECAST. It assumes we")
    print("  win every race and that deeper fills are no more adversely")
    print("  selected than shallow ones. Neither is measured here, and the")
    print("  close's own contract budget binds before any of it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
