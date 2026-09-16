#!/usr/bin/env python3
"""pincap.py -- what is ACTUALLY capping the live bot's earnings?

THE OPERATOR, 2026-09-16, correcting my priority order: "my first priority is
make max money. Lose less happens to follow closely."

So: where is the money we are not making? There are only four candidates and
they call for completely different work, so guessing is expensive:

  BANK        we cannot size bigger because there is not enough money.
  CAPS        the per-market, per-close and position limits bind.
  BOOK        the gates pass but there is nothing to buy.
  GATES       markets exist but our own rules refuse them.

The bot writes a `refused` record every time it declines something, with the
reason. Counting those against the signals it took says which of the four it
is, from LIVE logs rather than a replay.

WHY THIS BEATS HUNTING VENUES. A second exchange needs somebody else's
permission and has taken a day to reach "still blocked". Whatever is capping
the bot here needs nobody's permission at all.

SOURCE: live logs only.

    python research/pincap.py --selftest
    python research/pincap.py
"""
import argparse
import collections
import glob
import json
import os
import sys

LIVE = r"C:\kals-repo\results\pinrun-live-*.jsonl"


def reason_of(r):
    """The refusal reason, however the record spells it."""
    for k in ("why", "reason", "refused", "gate", "cause"):
        v = r.get(k)
        if isinstance(v, str) and v:
            return v
    return "unlabelled"


def load(pattern=LIVE):
    out = []
    for fp in sorted(glob.glob(pattern)):
        for line in open(fp, encoding="utf-8", errors="replace"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " + m) if c else ("FAIL: " + m))
        ok = ok and c

    ck(reason_of({"why": "edge too thin"}) == "edge too thin",
       "a reason is read from whichever field carries it")
    ck(reason_of({"reason": "max per market"}) == "max per market",
       "and from the alternate spelling")
    ck(reason_of({"kind": "refused"}) == "unlabelled",
       "NULL: a refusal with no reason is counted as unlabelled, never "
       "dropped -- a silent refusal is exactly the kind that hides a cap")
    ck(reason_of({"why": ""}) == "unlabelled",
       "NULL: an empty reason is not a reason")
    print("pincap selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--top", type=int, default=16)
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0
    rows = load()
    if not rows:
        print("loaded nothing -- no live logs")
        return 0

    kinds = collections.Counter(r.get("kind") for r in rows)
    refused = [r for r in rows if r.get("kind") == "refused"]
    signals = [r for r in rows if r.get("kind") == "signal"]
    orders = [r for r in rows if r.get("kind") == "order"]
    filled = [r for r in orders if (r.get("filled") or 0) > 0]
    closes = {r.get("ticker") for r in rows if r.get("kind") == "settled"}

    print("\nLIVE LOGS: %d records, %d settled closes" % (len(rows), len(closes)))
    print("  signals %d -> orders %d -> filled %d      refusals %d"
          % (len(signals), len(orders), len(filled), len(refused)))

    print("\nWHY THE BOT SAID NO (every refusal, live):")
    why = collections.Counter(reason_of(r) for r in refused)
    tot = sum(why.values()) or 1
    for w, n in why.most_common(a.top):
        print("  %-46s %7d  %5.1f%%" % (w[:46], n, 100 * n / tot))

    # WHAT DID WE ACTUALLY SPEND? autosize records what the bot wanted; the
    # fills record what it got. The ratio is the headroom that needs no
    # permission from anyone.
    sizes = [r for r in rows if r.get("kind") == "autosize"]
    if sizes and filled:
        want = sizes[-1].get("new") or 0
        got = [float(f.get("filled") or 0) for f in filled]
        got.sort()
        print("\nSIZE: the bot wanted %g contracts a trade." % want)
        print("  It actually got: median %g, worst %g, best %g."
              % (got[len(got) // 2], got[0], got[-1]))
        short = sum(1 for g in got if g < want * 0.9)
        print("  %d of %d fills came back under 90%% of what it asked for "
              "(%.0f%%)." % (short, len(got), 100 * short / len(got)))
        if short > len(got) * 0.5:
            print("  So the BOOK is the binding constraint, not the bank and")
            print("  not the caps: more than half the time there was not")
            print("  enough on offer to fill the size we already allow.")
        else:
            print("  So the book is usually deep enough and the cap or the")
            print("  bank is what binds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
