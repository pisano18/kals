#!/usr/bin/env python3
# VERSION: 2026-09-14-fl1
"""pinflip.py -- can a hedge turn being WRONG into a profit?

THE OPERATOR, 2026-09-14: "be creative to figure out a strategy to either find
the winning side or find a reliable way to get on the opposite winning side
when that's clear ... Because remember eventually you do know the winning side,
so that should help." And earlier: "hopefully if hedge in time we can
consistently get more than 0."

THE IDEA, STATED AS ARITHMETIC. Buying both sides AT THE SAME INSTANT can
never pay: the NO ask is 1 - yes_bid, so

    yes_ask + no_ask  ==  1 + (yes_ask - yes_bid)  ==  1 + spread

which is over a dollar by exactly the spread, always, on every market in
existence. That is an identity, not a market quirk, and it kills the obvious
version of the idea outright.

Buying them at DIFFERENT TIMES is a different animal, because the two prices
are drawn from two different moments:

    buy side A at t1 for  a
    buy side B at t2 for  b        (only if the model has flipped to B)

    one of them settles at $1.00, so the pair returns  1 - a - b

If a + b < 1.00 the pair is PROFITABLE EVEN THOUGH WE WERE WRONG. That is the
operator's "consistently get more than 0", and it is not obviously impossible,
because our edge is precisely that we learn the answer BEFORE the market fully
reprices -- we compute the settlement average from prints already on disk.

WHAT THIS MEASURES. For every market, the first second the model is confident
(the entry), and then, if the model later flips, the other side's price at the
moment of the flip. Then: how often is a + b under a dollar, and what does
hedging do to the average outcome, at several flip triggers.

WHAT IT CANNOT SHOW. Prices here are QUOTES, not fills -- rule 5, and a hedge
is a race like any other take. Worse, a hedge is the one order most likely to
be racing informed flow, because everyone else can see the same flip. So every
number here is a ceiling.
"""
import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SWEEP_SELFTESTED", "1")
import pinsweep                                                # noqa: E402

WINDOW = pinsweep.WINDOW
fee_per = pinsweep.fee_per


def walk_market(tk, mk, px, bel, pin, tau_max, ceiling, flip_at):
    """Entry, then the flip and its hedge price, for ONE market.

    `flip_at` is the belief in the side WE HOLD at which we give up on it and
    buy the other. 0.50 means "the model now favours the other side"; 0.20
    means "wait until it is fairly sure" -- later, but the hedge is cheaper
    the EARLIER we act, so the trigger is a real trade-off and not a detail.
    """
    entry = None
    for tau in range(min(tau_max, WINDOW - 1), 0, -1):
        b = bel.get((tk, tau))
        p = px.get((tk, tau))
        if b is None or not p:
            continue
        if b >= pin:
            side, price = "yes", p[0]
        elif b <= 1.0 - pin:
            side, price = "no", p[1]
        else:
            continue
        if price is None or price > ceiling:
            continue
        entry = {"tau": tau, "side": side, "price": price}
        break
    if entry is None:
        return None
    held = entry["side"]
    won = (held == mk["result"])
    out = {"tk": tk, "entry": entry, "won": won, "hedge": None}
    # after entry, watch belief in the side WE HOLD
    for tau in range(entry["tau"] - 1, 0, -1):
        b = bel.get((tk, tau))
        if b is None:
            continue
        mine = b if held == "yes" else 1.0 - b
        if mine > flip_at:
            continue
        p = px.get((tk, tau))
        if not p:
            continue
        other = p[1] if held == "yes" else p[0]
        if other is None:
            continue
        out["hedge"] = {"tau": tau, "price": other, "belief": mine}
        break
    return out


def summarise(rows, say=print, label=""):
    n = len(rows)
    if not n:
        return ""
    lost = [r for r in rows if not r["won"]]
    hedged = [r for r in rows if r["hedge"]]
    lines = []
    w = lines.append
    w("  %s" % label)
    w("    entries %d, of which the side we bought LOST %d (%.2f%%)"
      % (n, len(lost), 100.0 * len(lost) / n))
    w("    the model flipped and a hedge was available on %d (%.1f%%)"
      % (len(hedged), 100.0 * len(hedged) / n))
    # did the hedge fire on the ones that actually went wrong?
    hl = [r for r in lost if r["hedge"]]
    hw = [r for r in rows if r["won"] and r["hedge"]]
    w("      on LOSING entries : %d of %d (%.1f%%)  <- the rescues"
      % (len(hl), len(lost), 100.0 * len(hl) / max(1, len(lost))))
    w("      on WINNING entries: %d of %d (%.1f%%)  <- the false alarms"
      % (len(hw), n - len(lost), 100.0 * len(hw) / max(1, n - len(lost))))
    pairs = [r["entry"]["price"] + r["hedge"]["price"] for r in hedged]
    if pairs:
        pairs.sort()
        under = sum(1 for x in pairs if x < 1.0)
        w("    the two prices added: median %.1fc, p25 %.1fc, best %.1fc"
          % (100 * pairs[len(pairs) // 2], 100 * pairs[len(pairs) // 4],
             100 * pairs[0]))
        w("      UNDER 100c (a profit despite being wrong): %d of %d (%.1f%%)"
          % (under, len(pairs), 100.0 * under / len(pairs)))

    def pl(r, hedge):
        a = r["entry"]["price"]
        v = -fee_per(a)
        if hedge and r["hedge"]:
            b = r["hedge"]["price"]
            return 1.0 - a - b - fee_per(a) - fee_per(b)
        return v + ((1.0 - a) if r["won"] else -a)
    no_h = sum(pl(r, False) for r in rows)
    with_h = sum(pl(r, True) for r in rows)
    w("    per contract, NO hedging  : %+.2fc   total %+.2f" %
      (100 * no_h / n, no_h))
    w("    per contract, WITH hedging: %+.2fc   total %+.2f" %
      (100 * with_h / n, with_h))
    w("    hedging is worth %+.2fc per contract here" % (100 * (with_h - no_h) / n))
    txt = "\n".join(lines)
    if say:
        say(txt)
    return txt


def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    # THE IDENTITY THAT KILLS THE SIMULTANEOUS VERSION
    for yb, ya in ((0.90, 0.92), (0.10, 0.11), (0.50, 0.55)):
        ck(abs((ya + (1.0 - yb)) - (1.0 + (ya - yb))) < 1e-12,
           "buying BOTH sides at one instant costs 1 + the spread (%.2f + "
           "%.2f = %.4f) -- never under a dollar, on any market, ever"
           % (ya, 1 - yb, ya + 1 - yb))

    mk = {"ser": "X", "close": 1000, "strike": 1.0, "result": "no"}
    # model sure of YES from 40s, YES costs 90c; flips to NO at 20s, NO at 5c
    bel, px = {}, {}
    for tau in range(1, 60):
        bel[("T", tau)] = 0.999 if tau > 20 else 0.001
        px[("T", tau)] = (0.90, 0.05)
    r = walk_market("T", mk, px, bel, 0.995, 40, 0.98, 0.50)
    ck(r["entry"]["tau"] == 40 and r["entry"]["side"] == "yes",
       "it enters YES at 40s, the earliest confident second")
    ck(r["won"] is False, "and YES lost, because the market settled NO")
    ck(r["hedge"] and r["hedge"]["tau"] == 20,
       "the hedge fires at 20s, the second the model turns against us")
    ck(abs(r["hedge"]["price"] - 0.05) < 1e-9,
       "and it buys the OTHER side at ITS price (5c), not ours")
    tot = r["entry"]["price"] + r["hedge"]["price"]
    ck(tot < 1.0,
       "90c + 5c = %.0fc, UNDER a dollar -- so being wrong still pays. This "
       "is the operator's idea and it is arithmetically possible" % (100 * tot))

    # a hedge that costs too much must NOT be scored as a rescue
    px2 = dict((k, (0.90, 0.40)) for k in px)
    r2 = walk_market("T", mk, px2, bel, 0.995, 40, 0.98, 0.50)
    ck(r2["entry"]["price"] + r2["hedge"]["price"] > 1.0,
       "90c + 40c is over a dollar -- the hedge cuts the loss but does not "
       "turn it into a profit, and the report must not confuse the two")

    # THE TRIGGER MATTERS: a stricter trigger waits, and may miss entirely
    bel3 = dict(bel)
    for tau in range(1, 21):
        bel3[("T", tau)] = 0.30           # drifts, never collapses
    r3 = walk_market("T", mk, px, bel3, 0.995, 40, 0.98, 0.10)
    ck(r3["hedge"] is None,
       "a trigger of 0.10 never fires on a belief that only falls to 0.30 -- "
       "waiting for certainty can mean never hedging at all")
    r4 = walk_market("T", mk, px, bel3, 0.995, 40, 0.98, 0.50)
    ck(r4["hedge"] is not None,
       "while a trigger of 0.50 does fire on the same market")

    txt = summarise([r, r2], say=None, label="x")
    ck("despite being wrong" in txt and "false alarms" in txt,
       "the report shows both the rescues and the cost of false alarms")
    print("pinflip selftest: %d checks OK" % n[0])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--ticks", default="C:/kals/kalshi_data/ticker")
    ap.add_argument("--data", default="C:/kals/kalshi_data")
    ap.add_argument("--markets", default="C:/kals/fulltape/markets.json")
    ap.add_argument("--files", type=int, default=120)
    ap.add_argument("--pin", type=float, default=0.990)
    ap.add_argument("--tau-max", type=int, default=55)
    ap.add_argument("--ceiling", type=float, default=0.98)
    ap.add_argument("--out", default=os.path.join(REPO, "results",
                                                  "RESULTS_flip.md"))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_FLIP_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    import replay
    import pinwarn
    mk = pinsweep.load_markets(a.markets, set(replay.SERIES_TO_INDEX))
    px = pinsweep.prices(a.ticks, mk, limit=(a.files or None))
    keep = set(t for t, _ in px)
    mk = dict((k, v) for k, v in mk.items() if k in keep)
    print("  %d markets with quotes" % len(mk))
    cache = {}

    def index(iid):
        if iid not in cache:
            cache.clear()
            cache[iid] = pinwarn.load_one_index(a.data, iid)
        return cache[iid]
    bel = pinsweep.beliefs(index, mk)
    print("  %d beliefs" % len(bel))
    parts = []
    for flip_at in (0.90, 0.70, 0.50, 0.30, 0.10):
        rows = []
        for tk, m in mk.items():
            r = walk_market(tk, m, px, bel, a.pin, a.tau_max, a.ceiling,
                            flip_at)
            if r:
                rows.append(r)
        t = summarise(rows, label="HEDGE WHEN BELIEF IN OUR SIDE FALLS UNDER "
                                  "%.0f%%" % (100 * flip_at))
        print("")
        parts.append(t)
    nl = chr(10)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("# RESULTS_flip -- can a hedge turn being wrong into a "
                 "profit?" + nl + nl)
        fh.write("gate %.3f, entry from %ds, ceiling %.0fc%s%s"
                 % (a.pin, a.tau_max, 100 * a.ceiling, nl, nl))
        fh.write("```" + nl + (nl + nl).join(parts) + nl + "```" + nl)
    print("  wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
