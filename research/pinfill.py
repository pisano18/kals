#!/usr/bin/env python3
"""pinfill.py -- what fraction of what it ASKED FOR, at the time, did it get?

THE OPERATOR, 2026-09-16, pushing back on pincap: "I thought this was just a
momentary thing... didn't yesterday have many full maxed out orders of our max
size?"

HE IS RIGHT AND pincap WAS WRONG. It took the LAST autosize record -- 86
contracts, set this morning on a $511 bank -- and measured every fill in our
whole live history against it. But autosize moves with the bank: the bot wanted
20 when the bank was small, and a 20-contract fill then was a COMPLETE fill,
not a 23% one. pincap called those shortfalls and concluded the book was
starving us. That conclusion was an artefact of comparing old fills to a new
target.

This tracks the wanted size THROUGH TIME, so each fill is scored against what
the bot was actually asking for at that moment. It also breaks the answer down
by day, because his other point is that thin books come in lulls rather than
being a permanent state, and an average over a fortnight hides exactly that.

SOURCE: live logs only.

    python research/pinfill.py --selftest
    python research/pinfill.py
"""
import argparse
import collections
import glob
import json
import sys


LIVE = r"C:\kals-repo\results\pinrun-live-*.jsonl"


def walk(rows):
    """[(day, wanted_at_the_time, filled)] -- autosize tracked as it moves."""
    want = None
    out = []
    for r in rows:
        k = r.get("kind")
        if k == "autosize":
            n = r.get("new")
            if isinstance(n, (int, float)):
                want = float(n)
        elif k == "start":
            n = r.get("size")
            if isinstance(n, (int, float)) and want is None:
                want = float(n)
        elif k == "order" and (r.get("filled") or 0) > 0 and want:
            out.append((str(r.get("t") or "")[:10], want, float(r["filled"])))
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
        out.extend(walk(rows))
    return out


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " + m) if c else ("FAIL: " + m))
        ok = ok and c

    rows = [{"kind": "autosize", "new": 20},
            {"kind": "order", "filled": 20, "t": "2026-09-14T01:00:00Z"},
            {"kind": "autosize", "new": 86},
            {"kind": "order", "filled": 20, "t": "2026-09-16T01:00:00Z"}]
    got = walk(rows)
    ck(len(got) == 2, "both fills are scored")
    ck(got[0][1] == 20 and got[1][1] == 86,
       "THE POINT: the same 20-contract fill is a FULL fill under the old "
       "target and a quarter of the new one. Scoring both against 86 is the "
       "bug this file exists to fix.")
    ck(got[0][0] == "2026-09-14" and got[1][0] == "2026-09-16",
       "and each fill carries its own day, so a lull cannot hide in an average")
    ck(walk([{"kind": "order", "filled": 5}]) == [],
       "NULL: a fill before any known target is dropped, not scored against a "
       "guess")
    ck(walk([{"kind": "autosize", "new": 20},
             {"kind": "order", "filled": 0}]) == [],
       "NULL: an unfilled order is not a fill")
    print("pinfill selftest:", "OK" if ok else "FAILED")
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

    by = collections.defaultdict(list)
    for day, want, got in rows:
        by[day].append((want, got))
    print("\nFILL AS A FRACTION OF WHAT THE BOT ASKED FOR **AT THE TIME**\n")
    print("  %-12s %7s %9s %9s %11s %11s"
          % ("day", "fills", "wanted", "median got", "full fills", "median %"))
    print("  " + "-" * 64)
    for day in sorted(by):
        v = by[day]
        fr = sorted(g / w for w, g in v)
        gots = sorted(g for _, g in v)
        full = sum(1 for f in fr if f >= 0.9)
        wants = sorted({w for w, _ in v})
        print("  %-12s %7d %9s %9.0f %7d/%-3d %10.0f%%"
              % (day, len(v),
                 "%g" % wants[0] if len(wants) == 1 else "%g-%g" % (wants[0], wants[-1]),
                 gots[len(gots) // 2], full, len(v), 100 * fr[len(fr) // 2]))
    allfr = sorted(g / w for _, w, g in rows)
    full = sum(1 for f in allfr if f >= 0.9)
    print("\n  Overall: %d fills, %d of them 90%% or more of the ask (%.0f%%), "
          "median %.0f%%." % (len(allfr), full, 100 * full / len(allfr),
                              100 * allfr[len(allfr) // 2]))
    print("\n  pincap said 94%% of fills came back short. Measured against what")
    print("  the bot actually wanted at the time, it is %.0f%%."
          % (100 * (1 - full / len(allfr))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
