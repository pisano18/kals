#!/usr/bin/env python3
"""pinsure.py -- does 100% ever lose, and does the hedge fire when it shouldn't?

THE OPERATOR, 2026-09-16: "how can it possibly say 100% when 100% means
physically impossible to lose... Has 100% ever flipped sides in the current
version of the confidence system? Is there any solution that would've removed
hedges on the ones that were fine and still hedges the flipping ones?"

Two separate questions, both answerable from live fills, and NOTHING here
changes the bot.

  1. CALIBRATION. Group our live trades by the confidence the model had at the
     moment it decided, and count how many lost. If the 99.99%+ bucket ever
     loses, the model is overstating certainty and the printed "100%" is a
     rounded number, not a physical impossibility.

  2. THE HEDGE'S BOOK. Every hedge that fires on a position that would have
     won anyway costs money -- it buys the losing side of a bet we were
     winning. Every hedge on a position that was going to lose saves money.
     Both are countable, and the difference is what hedging is actually worth.
     If the unnecessary ones dominate, there is room for a better trigger; if
     they do not, the trigger is already close to right.

  3. IS THERE A TELL? For the hedges that fired, compare the ones that proved
     necessary against the ones that did not, on what was knowable AT THE
     MOMENT THE HEDGE FIRED: the belief it had collapsed to, how far into the
     window it was, the entry price. If the two groups look identical, no
     smarter trigger exists on this evidence and the current one is doing as
     well as anything could.

SOURCE: live logs only, per the 2026-09-10 amendment.

    python research/pinsure.py --selftest
    python research/pinsure.py
"""
import argparse
import collections
import glob
import json
import statistics
import sys

LIVE = r"C:\kals-repo\results\pinrun-live-*.jsonl"
BUCKETS = [(0.0, 0.99), (0.99, 0.999), (0.999, 0.9999), (0.9999, 1.01)]


def confidence(fair, want):
    """The model's probability that OUR side wins."""
    if fair is None or want is None:
        return None
    return float(fair) if want == "yes" else 1.0 - float(fair)


def bucket_of(c):
    for lo, hi in BUCKETS:
        if lo <= c < hi:
            return (lo, hi)
    return None


def label(b):
    lo, hi = b
    if hi > 1.0:
        return "99.99%+ (prints as 100%)"
    return "%.2f%% to %.2f%%" % (100 * lo, 100 * hi)


def scan(rows):
    """[(confidence, won, hedged, belief_at_hedge, tau_at_hedge, entry)]"""
    sig, hedge, out = {}, {}, []
    for r in rows:
        k, tk = r.get("kind"), r.get("ticker")
        if not tk:
            continue
        if k == "signal":
            c = confidence(r.get("fair"), r.get("want"))
            if c is not None:
                sig[tk] = (c, r.get("price"))
        elif k == "hedge":
            hedge[tk] = (r.get("belief"), r.get("tau"), r.get("entry"))
        elif k == "settled":
            if tk not in sig:
                continue
            c, price = sig.pop(tk)
            h = hedge.pop(tk, None)
            won = (r.get("want") == r.get("result"))
            out.append((c, won, h is not None,
                        (h[0] if h else None), (h[1] if h else None), price))
    return out


def load():
    out = []
    for fp in sorted(glob.glob(LIVE)):
        rows = []
        for line in open(fp, encoding="utf-8", errors="replace"):
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
        out.extend(scan(rows))
    return out


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " + m) if c else ("FAIL: " + m))
        ok = ok and c

    ck(confidence(1.0, "yes") == 1.0, "wanting yes at fair 1.0 is full confidence")
    ck(confidence(0.00463, "no") > 0.995,
       "AND WANTING NO AT FAIR 0.00463 IS ALSO 99.5%% CONFIDENT (%.5f). Reading"
       " `fair` as our confidence without flipping for the NO side would score"
       " every NO trade as a near-zero-confidence bet."
       % confidence(0.00463, "no"))
    ck(confidence(None, "yes") is None and confidence(1.0, None) is None,
       "NULL: a missing field yields no confidence, never a default")
    ck(bucket_of(1.0) == (0.9999, 1.01),
       "exactly 1.0 lands in the top bucket rather than falling off the end")
    ck(bucket_of(0.9995) == (0.999, 0.9999), "and 99.95% sits below it")

    rows = [{"kind": "signal", "ticker": "A", "fair": 1.0, "want": "yes",
             "price": 0.97},
            {"kind": "hedge", "ticker": "A", "belief": 0.4, "tau": 15,
             "entry": 0.97},
            {"kind": "settled", "ticker": "A", "want": "yes", "result": "no"}]
    got = scan(rows)
    ck(len(got) == 1 and got[0][0] == 1.0 and got[0][1] is False
       and got[0][2] is True,
       "a 100% trade that LOST and was hedged is recorded as exactly that")
    ck(scan([{"kind": "settled", "ticker": "B", "want": "yes",
              "result": "yes"}]) == [],
       "NULL: a settlement with no signal is dropped, not scored as a win")
    print("pinsure selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0
    rows = load()
    if not rows:
        print("loaded nothing")
        return 0

    print("\n1. DOES THE MODEL'S CERTAINTY HOLD UP? (live trades only)\n")
    print("  %-28s %8s %8s %10s" % ("confidence at decision", "trades", "lost", "loss rate"))
    print("  " + "-" * 58)
    for b in BUCKETS:
        got = [r for r in rows if bucket_of(r[0]) == b]
        if not got:
            continue
        lost = sum(1 for r in got if not r[1])
        print("  %-28s %8d %8d %9.2f%%"
              % (label(b), len(got), lost, 100 * lost / len(got)))
    top = [r for r in rows if r[0] >= 0.9999]
    tl = [r for r in top if not r[1]]
    print()
    if top:
        print("  The bucket that prints as 100%%: %d trades, %d lost."
              % (len(top), len(tl)))
        if tl:
            print("  SO YES, 'CERTAIN' HAS LOST. The number is a rounded")
            print("  probability, not a physical impossibility, and the hedge")
            print("  firing against one is not a contradiction.")
        else:
            print("  It has NEVER lost. On this evidence a hedge against a")
            print("  100%% call has never once been necessary.")

    print("\n2. WHAT IS THE HEDGE ACTUALLY WORTH?\n")
    hedged = [r for r in rows if r[2]]
    unhedged = [r for r in rows if not r[2]]
    need = [r for r in hedged if not r[1]]
    waste = [r for r in hedged if r[1]]
    print("  %d trades hedged, %d not." % (len(hedged), len(unhedged)))
    if hedged:
        print("  Of the hedged: %d went on to LOSE (the hedge was needed) and"
              % len(need))
        print("  %d went on to WIN anyway (the hedge cost us)." % len(waste))
        print("  So %.0f%% of hedges fired on a position that was fine."
              % (100 * len(waste) / len(hedged)))

    print("\n3. IS THERE A TELL THAT SEPARATES THEM?\n")
    for name, group in (("needed", need), ("unnecessary", waste)):
        b = [r[3] for r in group if isinstance(r[3], (int, float))]
        t = [r[4] for r in group if isinstance(r[4], (int, float))]
        if b:
            print("  %-12s n=%-4d belief when it fired: median %.3f  range "
                  "%.3f-%.3f" % (name, len(group), statistics.median(b),
                                 min(b), max(b)))
        if t:
            print("  %-12s      seconds left: median %.0f  range %.0f-%.0f"
                  % ("", statistics.median(t), min(t), max(t)))
    if need and waste:
        bn = [r[3] for r in need if isinstance(r[3], (int, float))]
        bw = [r[3] for r in waste if isinstance(r[3], (int, float))]
        if bn and bw:
            print("\n  If those two belief ranges overlap heavily, no threshold")
            print("  on belief alone can separate them, and a 'smarter trigger'")
            print("  would just be a differently-wrong one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
