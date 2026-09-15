#!/usr/bin/env python3
"""pinstrat.py -- which earns the most, ACCOUNTING FOR LOSSES: buy-then-hedge,
wait-then-buy, or a blend?

THE OPERATOR'S QUESTION, 2026-09-14: "given all those ideas and yours are you
able to figure out what earns the most total accounting for losses? ... I'm
not certain which is better if it's buy then hedge harder once we know, or if
it's wait then buy and lose 1/3, or is it a third option, or is it a dynamic
blend?"

ONE FRAMEWORK, SAME MARKETS, EVERY STRATEGY. Each strategy is scored on the
SAME set of markets from results/pinlevels_rows.jsonl, one row per market
(hard rule 4), so the numbers are comparable. Per-contract, then a bootstrap
over CLOSES, then a 60/40 holdout on close time so a strategy that only wins
on the half it was chosen on is exposed.

WHAT THE CACHE CAN AND CANNOT SAY. It holds, per market: entry price, whether
the side won, the lowest the model's belief ever went, the second it crossed
0.90 / 0.80 / 0.70, and the hedge LADDER the market showed at each of those
crossings. For a WAIT strategy it also holds the same market sampled a few
seconds later, so "did the offer survive and was the model still sure" is
answerable. It does NOT hold our fill rate, our latency, or the quote's age.

RULE 5 IS RESPECTED. The tape's mix of winners to losers (2.1%) is not ours
(3.4%). Every total is therefore shown twice: at the tape's mix, and with the
losers re-weighted to our live rate. The RANKING is what this file is for; the
absolute dollars are not a forecast.

    python research/pinstrat.py --selftest
    python research/pinstrat.py
"""
import collections
import json
import os
import random
import sys

ROWS = os.path.join("results", "pinlevels_rows.jsonl")
CEIL = 0.98
LIVE_LOSS_RATE = 12.0 / 348.0        # our own fills, 2026-09-14
FEE = lambda p: 0.07 * p * (1.0 - p)


# ---------------------------------------------------------------------------
# one market -> per-contract outcome under each strategy
# ---------------------------------------------------------------------------
def hedge_ask(m, t):
    h = (m.get("hedge") or {}).get(t)
    return None if not h else h.get("ask")


def alarm(m, t):
    return (m.get("alarm_tau") or {}).get(t)


def plain(m):
    """Buy now, never hedge."""
    p = m["price"]
    return (1.0 - p - FEE(p)) if m["won"] else (-p - FEE(p))


def hedged(m, t):
    """Buy now; if belief ever fell under t (at or after 3 s), buy the other
    side at the ask the market showed at that crossing. Holding both sides
    pays exactly $1.00, so the outcome is locked whatever settles."""
    if m["min_belief_t3"] >= float(t):
        return plain(m)
    a = hedge_ask(m, t)
    if a is None or a >= 1.0:
        return plain(m)
    p = m["price"]
    return 1.0 - p - a - FEE(p) - FEE(a)


def waited(m, k, later, then_hedge=None):
    """See the signal at tau t; wait k seconds; buy only if the offer is still
    there (>= 20 contracts at or under the price we saw) and the model is
    still >= 0.90 sure. `later` is the same market's row at tau t-k, or None.
    Returns None when the wait means no trade -- the caller counts those."""
    if later is None:
        return None
    avail = sum(sz for px, sz in (later.get("ladder") or [])
                if px <= m["price"] + 1e-9)
    if avail < 20 or later.get("want") != m.get("want"):
        return None
    if (later.get("conf") or 0.0) < 0.90:
        return None
    if then_hedge is None:
        return plain(m)
    return hedged(m, then_hedge)


# ---------------------------------------------------------------------------
def selftest():
    ok = True

    def ck(c, msg):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + msg)
        ok = ok and c

    # a losing market whose belief collapsed to 0.05, hedge asks stored
    loser = {"price": 0.95, "won": False, "min_belief_t3": 0.05,
             "hedge": {"0.90": {"ask": 0.20}, "0.80": {"ask": 0.35},
                       "0.70": {"ask": 0.50}}, "want": "no"}
    ck(plain(loser) < -0.95, "unhedged, a loser costs the whole entry (%.3f)" % plain(loser))
    ck(hedged(loser, "0.90") > hedged(loser, "0.80") > hedged(loser, "0.70") > plain(loser),
       "hedging EARLIER locks a smaller loss: 0.90 (%.3f) > 0.80 (%.3f) > 0.70 (%.3f) > none"
       % (hedged(loser, "0.90"), hedged(loser, "0.80"), hedged(loser, "0.70")))
    # a winner that never wobbled: every hedge strategy equals plain
    winner = {"price": 0.95, "won": True, "min_belief_t3": 0.999, "hedge": {}, "want": "no"}
    ck(hedged(winner, "0.80") == plain(winner) and plain(winner) > 0,
       "a winner that never dipped is untouched by any trigger (+%.4f)" % plain(winner))
    # a winner that DID wobble to 0.75: hedged at 0.80 it is a false alarm and LOSES
    wobble = {"price": 0.95, "won": True, "min_belief_t3": 0.75,
              "hedge": {"0.80": {"ask": 0.30}, "0.90": {"ask": 0.20}}, "want": "no"}
    ck(hedged(wobble, "0.80") < 0 < plain(wobble),
       "a winner that wobbled to 0.75 is a FALSE ALARM at 0.80: +%.3f becomes %.3f"
       % (plain(wobble), hedged(wobble, "0.80")))
    ck(hedged(wobble, "0.70") == plain(wobble),
       "and is NOT touched by a 0.70 trigger -- the trigger level is the false-alarm dial")
    # waiting: offer gone -> no trade; offer there + still sure -> plain
    gone = {"ladder": [[0.99, 500.0]], "conf": 0.999, "want": "no"}
    there = {"ladder": [[0.95, 40.0]], "conf": 0.999, "want": "no"}
    unsure = {"ladder": [[0.95, 40.0]], "conf": 0.60, "want": "no"}
    ck(waited(loser, 3, gone) is None, "wait: offer gone -> no trade")
    ck(waited(loser, 3, unsure) is None, "wait: offer there but model no longer sure -> no trade")
    ck(waited(winner, 3, there) == plain(winner), "wait: offer there and still sure -> the plain trade")
    ck(waited(winner, 3, None) is None, "wait: no later sample -> cannot say, counted as no trade")

    # THE NULL: on a world where nothing ever collapses, every strategy that
    # trades is identical and waiting only loses the offers that vanished.
    calm = [{"price": 0.95, "won": True, "min_belief_t3": 0.999, "hedge": {}, "want": "no"}] * 50
    ck(all(abs(hedged(m, "0.80") - plain(m)) < 1e-12 for m in calm) and
       all(abs(hedged(m, "0.90") - plain(m)) < 1e-12 for m in calm),
       "NULL: with no collapses anywhere, every hedge trigger equals no hedge exactly")
    print("pinstrat selftest:", "OK" if ok else "FAILED")
    return ok


# ---------------------------------------------------------------------------
def load():
    by = collections.defaultdict(list)
    for line in open(ROWS, encoding="utf-8"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("kind") != "row" or d.get("verdict") != "trade":
            continue
        if d.get("price", 1.0) > CEIL + 1e-9 or (d.get("depth") or 0) < 20:
            continue
        if not d.get("ladder"):
            continue
        by[d["ticker"]].append(d)
    return by


def boot(vals_by_close, n=4000, seed=5):
    rnd = random.Random(seed)
    v = list(vals_by_close.values())
    k = len(v)
    if k < 2:
        return (0.0, 0.0)
    ms = sorted(sum(v[rnd.randrange(k)] for _ in range(k)) / k for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n)]


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0

    by = load()
    if not by:
        print("loaded nothing -- %s missing or empty" % ROWS)
        return 0

    # one row per market = the EARLIEST tau sampled (longest hold), plus that
    # market's rows 3 s and 5 s later if they exist
    mk = []
    for tk, rows in by.items():
        rows.sort(key=lambda r: -r["tau"])
        m = rows[0]
        bt = {r["tau"]: r for r in rows}
        # nearest later sample inside a window: [k-1, k+2] seconds after t.
        # Demanding EXACTLY t-3 and t-5 left 29 markets and one loser, and
        # one loser decides a ranking. The window keeps the meaning (a wait of
        # roughly k seconds) and the sample.
        def near(k):
            for d in (k, k + 1, k - 1, k + 2):
                if bt.get(m["tau"] - d) is not None:
                    return bt[m["tau"] - d]
            return None
        m["_l3"] = near(3)
        m["_l5"] = near(5)
        mk.append(m)
    # apples to apples: only markets that HAVE a later sample for both waits
    mk = [m for m in mk if m["_l3"] is not None and m["_l5"] is not None]
    W = [m for m in mk if m["won"]]
    L = [m for m in mk if not m["won"]]
    closes = sorted(set(m["cs"] for m in mk))
    print("\n%d markets with samples at t, t-3 and t-5 over %d closes: %d won, %d lost (%.2f%%)"
          % (len(mk), len(closes), len(W), len(L), 100.0 * len(L) / len(mk)))
    print("our live loss rate is %.2f%% -- second column re-weights losers to it\n"
          % (100 * LIVE_LOSS_RATE))

    STRATS = [
        ("A  buy now, no hedge",            lambda m: plain(m)),
        ("B  buy now, hedge at 0.90",       lambda m: hedged(m, "0.90")),
        ("C  buy now, hedge at 0.80 (LIVE)", lambda m: hedged(m, "0.80")),
        ("D  buy now, hedge at 0.70",       lambda m: hedged(m, "0.70")),
        ("E  wait 3s, no hedge",            lambda m: waited(m, 3, m["_l3"])),
        ("F  wait 3s, then hedge at 0.80",  lambda m: waited(m, 3, m["_l3"], "0.80")),
        ("G  wait 5s, no hedge",            lambda m: waited(m, 5, m["_l5"])),
        ("H  wait 5s, then hedge at 0.80",  lambda m: waited(m, 5, m["_l5"], "0.80")),
    ]

    cut = closes[int(0.6 * len(closes))]
    wl = LIVE_LOSS_RATE / (len(L) / float(len(mk)))     # loser re-weight

    print("  %-34s %7s %7s %9s %10s %11s %11s %9s"
          % ("strategy", "trades", "losses", "c/market", "c/mkt@our", "95% by close", "first60%", "last40%"))
    print("  " + "-" * 104)
    for name, fn in STRATS:
        outs = [(m, fn(m)) for m in mk]
        traded = [(m, v) for m, v in outs if v is not None]
        n = len(traded)
        if n == 0:
            print("  %-34s   none" % name)
            continue
        losses = sum(1 for m, v in traded if v < 0)
        tot = sum(v for _, v in traded)
        # re-weighted to our loss rate: losers count wl times
        totw = sum(v * (wl if not m["won"] else 1.0) for m, v in traded)
        nw = sum((wl if not m["won"] else 1.0) for m, _ in traded)
        # per close for the bootstrap: sum per close / markets that traded
        pc = collections.defaultdict(float)
        for m, v in traded:
            pc[m["cs"]] += v
        lo, hi = boot(pc)
        # holdout
        a = [v for m, v in traded if m["cs"] < cut]
        b = [v for m, v in traded if m["cs"] >= cut]
        print("  %-34s %7d %7d %+8.2fc %+9.2fc [%+5.2f,%+5.2f] %+8.2fc %+8.2fc"
              % (name, n, losses, 100 * tot / n, 100 * totw / nw, 100 * lo, 100 * hi,
                 100 * sum(a) / max(1, len(a)), 100 * sum(b) / max(1, len(b))))
    print()
    print("  c/market = cents per contract per market TRADED. A wait strategy trades fewer")
    print("  markets; its per-trade number is not its total. TOTAL at the tape mix, per 100")
    print("  markets SEEN (so waiting is charged for the trades it never made):")
    print()
    print("  %-34s %10s %12s" % ("strategy", "per 100 seen", "@ our loss rate"))
    for name, fn in STRATS:
        outs = [(m, fn(m)) for m in mk]
        tot = sum(v for _, v in outs if v is not None)
        totw = sum(v * (wl if not m["won"] else 1.0) for m, v in outs if v is not None)
        print("  %-34s %+9.1fc %+11.1fc" % (name, 100 * 100 * tot / len(mk), 100 * 100 * totw / len(mk)))
    print()
    print("  READ THE RANKING, NOT THE DOLLARS. The tape cannot see our fill rate, our")
    print("  latency, or the quote's age, and a wait strategy's survivors are the resting")
    print("  quotes, which on our own fills earn a third of what fresh ones do.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
