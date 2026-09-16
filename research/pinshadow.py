#!/usr/bin/env python3
"""pinshadow.py -- what the shadows WOULD have done, against what the bot did.

THE OPERATOR, 2026-09-16: "Make it notice but not do anything yet. Have it
notice, make a decision on what it would do, and track it. Then track what
pinbot does and compare those totals."

Two paper arms were started alongside the live bot on 2026-09-16:

  control   identical flags to live. It exists to measure the PAPER-VERSUS-
            LIVE gap itself, which is not zero and has been enormous before:
            the tape said 0.11% loss and live said 3.4%, a 31x difference, on
            intervals that did not overlap. A shadow that beats live by less
            than the control does has beaten nothing.
  loose     --max-positions 5 and --take-dumps. Two of the very few levers
            still untested: more concurrent positions, and switching off the
            dump guard, which once refused an XRP contract at 45c that our
            model called 99.5% and which then settled against us by one part
            in ten thousand. That guard may be too wide or exactly right;
            paper is where that gets answered.

WHAT THIS IS NOT. It is not a claim that any shadow's number transfers. A
paper arm cannot model whether an offer would still be ours once we take it,
and the population that hurts us -- an adverse fill at extreme confidence --
is precisely the one it cannot see. Treat a shadow win as a reason to
pre-register a live test, never as a reason to deploy.

    python research/pinshadow.py --selftest
    python research/pinshadow.py
"""
import argparse
import collections
import glob
import json
import os
import sys

LIVE = r"C:\kals-repo\results\pinrun-live-*.jsonl"
PAPER = r"C:\kals-repo\results\pinrun-paper-*.jsonl"


def config_of(rows):
    """A short label for what this arm was configured to do."""
    for r in rows:
        if r.get("kind") == "start":
            bits = []
            for k, short in (("max_positions", "pos"), ("max_per_market", "mkt"),
                             ("take_dumps", "dumps"), ("hedge_belief", "hedge"),
                             ("size", "size")):
                v = r.get(k)
                if v not in (None, False):
                    bits.append("%s=%s" % (short, v))
            return " ".join(bits) or "(no config recorded)"
    return "(no start record)"


def tally(rows):
    d = {"fills": 0, "contracts": 0.0, "closes": 0, "won": 0, "lost": 0,
         "pnl": 0.0, "signals": 0}
    for r in rows:
        k = r.get("kind")
        if k == "signal":
            d["signals"] += 1
        elif k == "order" and (r.get("filled") or 0) > 0:
            d["fills"] += 1
            d["contracts"] += float(r["filled"])
        elif k == "settled" and isinstance(r.get("pnl_c"), (int, float)):
            d["closes"] += 1
            p = r["pnl_c"] / 100.0
            d["pnl"] += p
            d["won" if p >= 0 else "lost"] += 1
    return d


def read(fp):
    rows = []
    for line in open(fp, encoding="utf-8", errors="replace"):
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    return rows


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " + m) if c else ("FAIL: " + m))
        ok = ok and c

    rows = [{"kind": "start", "max_positions": 5, "take_dumps": True, "size": 20},
            {"kind": "signal"},
            {"kind": "order", "filled": 10},
            {"kind": "order", "filled": 0},
            {"kind": "settled", "pnl_c": 150.0},
            {"kind": "settled", "pnl_c": -9700.0}]
    c = config_of(rows)
    ck("pos=5" in c and "dumps=True" in c,
       "the arm labels itself from its own start record: %s" % c)
    ck("dumps" not in config_of([{"kind": "start", "take_dumps": False}]),
       "NULL: a flag that is off is not listed as if it were on")
    t = tally(rows)
    ck(t["fills"] == 1, "an unfilled order is not a fill")
    ck(t["closes"] == 2 and t["won"] == 1 and t["lost"] == 1,
       "wins and losses are counted separately")
    ck(abs(t["pnl"] - (-95.5)) < 1e-9,
       "pnl_c is the whole trade in cents: 150 and -9700 net to -$95.50, not "
       "-$9550")
    ck(tally([])["closes"] == 0, "NULL: an empty arm tallies to nothing")
    print("pinshadow selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--min-closes", type=int, default=1)
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0

    arms = []
    for fp in sorted(glob.glob(LIVE)):
        rows = read(fp)
        t = tally(rows)
        if t["closes"] >= a.min_closes:
            arms.append(("LIVE", os.path.basename(fp), config_of(rows), t))
    for fp in sorted(glob.glob(PAPER)):
        rows = read(fp)
        t = tally(rows)
        if t["closes"] >= a.min_closes:
            arms.append(("paper", os.path.basename(fp), config_of(rows), t))
    if not arms:
        print("no arm has settled a close yet. The shadows were started at")
        print("2026-09-16 20:46Z; give them a few closes.")
        return 0

    print("\n%-6s %-34s %7s %7s %6s %10s %11s"
          % ("arm", "config", "closes", "fills", "losses", "contracts", "money"))
    print("-" * 88)
    for kind, name, cfg, t in sorted(arms, key=lambda x: (x[0] != "LIVE", -x[3]["closes"])):
        print("%-6s %-34s %7d %7d %6d %10.0f %11.2f"
              % (kind, cfg[:34], t["closes"], t["fills"], t["lost"],
                 t["contracts"], t["pnl"]))

    live = [t for k, _, _, t in arms if k == "LIVE"]
    if live:
        lc = sum(t["closes"] for t in live)
        lp = sum(t["pnl"] for t in live)
        print("\n  LIVE so far: %d closes, $%+.2f, %.2f cents a close."
              % (lc, lp, 100 * lp / lc if lc else 0))
    print("\n  A shadow only means something once it has 30+ closes, and even")
    print("  then it is a reason to pre-register a live test, never a reason")
    print("  to deploy. Paper cannot model whether the offer would still have")
    print("  been ours.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
