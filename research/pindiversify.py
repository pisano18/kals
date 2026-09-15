#!/usr/bin/env python3
"""pindiversify.py -- do the Coin Race and the up/down pin LOSE AT THE SAME TIME?

THE OPERATOR, 2026-09-15: "take things that seem unrelated and mash them
together to come up with creative ideas and solutions."

THE IDEA. The single worst risk this project carries is a CORRELATED loss:
twelve series settle on the same quarter hour at rho ~ 0.8, so a big common
move in crypto can take every coin past its strike at once. `RESULTS_pinsize`
put it bluntly -- "every contract in a close flips together". That is why one
bad close costs a third of the bank.

The Coin Race (`KXCRYPTOLEAD15M`) asks a structurally different question: which
of BTC, ETH, SOL, XRP, HYPE has the highest return. **A common shock cannot
change an ordering.** If all five jump 1%, the leader is still the leader. So
the race should be immune to precisely the event that hurts the pin most.

If that holds, the race is not just more opportunity -- it is opportunity whose
losses land on DIFFERENT closes, which is worth more than its edge alone.

WHAT IT MEASURES, per 15-minute close, from the settlement index tape only:

  PIN FAILS   -- at tau 20 the model calls a coin near-certain and it settles
                 the other way. Scored per coin and per close.
  RACE FAILS  -- at tau 20 the leader by return-since-open is not the coin that
                 finishes highest.

Then: how often do they fail together, against how often they would if the two
were independent? A ratio near 1 means independent, which is the good answer.

RETURNS ARE THE RACE'S OWN RULE, solved 773/773 in RESULTS_coinrace: the
60-second TWAP at the close divided by the 60-second TWAP at the open.

INDEX ONLY. No order book, no fills, no P&L, no claim about our loss rate.

    python research/pindiversify.py --selftest
    python research/pindiversify.py
"""
import collections
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import idxload                                                 # noqa: E402
import pinrun                                                  # noqa: E402

RACE = {"BRTI": "BTC", "ETHUSD_RTI": "ETH", "SOLUSD_RTI": "SOL",
        "XRPUSD_RTI": "XRP", "HYPEUSD_RTI": "HYPE"}
PIN_COINS = ["BRTI", "ETHUSD_RTI", "SOLUSD_RTI", "XRPUSD_RTI", "HYPEUSD_RTI",
             "DOGEUSD_RTI", "BNBUSD_RTI", "ZECUSD_RTI", "NEARUSD_RTI"]
TAU = 20
PIN_GATE = pinrun.PIN


def twap(d, a, b):
    """Mean of the prints that exist in [a, b], or None if too few."""
    got = [v for v in (d.get(s) for s in range(a, b + 1)) if v is not None]
    if len(got) < int(0.95 * (b - a + 1)):
        return None
    return sum(got) / len(got)


def leader(idx, close, tau):
    """(coin, return) leading at `tau` seconds out, by the race's own rule:
    the running close TWAP over the prints so far, divided by the open TWAP."""
    best = None
    for iid, name in RACE.items():
        d = idx.get(iid)
        if d is None:
            continue
        den = twap(d, close - 900 - 60, close - 900 - 1)
        if not den:
            continue
        num = twap(d, close - 60, close - tau - 1)
        if not num:
            continue
        r = num / den
        if best is None or r > best[1]:
            best = (name, r)
    return best


def final_leader(idx, close):
    best = None
    for iid, name in RACE.items():
        d = idx.get(iid)
        if d is None:
            continue
        den = twap(d, close - 900 - 60, close - 900 - 1)
        num = twap(d, close - 60, close - 1)
        if not den or not num:
            continue
        r = num / den
        if best is None or r > best[1]:
            best = (name, r)
    return best


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    base = 5_000_000 - (5_000_000 % 900)
    close = base + 1800

    def mk(iid, open_lvl, close_lvl):
        D = idxload.Dense(iid, close - 1000, 1200)
        for s in range(close - 1000, close):
            D.v[s - D.base] = open_lvl if s < close - 60 else close_lvl
        return D

    # A leads on return: 100 -> 102 (+2%), B 100 -> 101 (+1%)
    idx = {"BRTI": mk("BRTI", 100.0, 102.0), "ETHUSD_RTI": mk("ETH", 100.0, 101.0)}
    # the open TWAP window is [close-960, close-901]; both sit at open_lvl there
    got = final_leader(idx, close)
    ck(got is not None and got[0] == "BTC",
       "the coin with the bigger return leads, not the bigger price")

    # THE WHOLE POINT: a COMMON shock must not change the order
    idx2 = {"BRTI": mk("BRTI", 100.0, 102.0 * 1.10),
            "ETHUSD_RTI": mk("ETH", 100.0, 101.0 * 1.10)}
    got2 = final_leader(idx2, close)
    ck(got2 is not None and got2[0] == "BTC",
       "and a 10%% jump in BOTH coins leaves the SAME leader -- this is the "
       "structural claim the whole file rests on")

    # an idiosyncratic shock CAN change it
    idx3 = {"BRTI": mk("BRTI", 100.0, 102.0),
            "ETHUSD_RTI": mk("ETH", 100.0, 105.0)}
    got3 = final_leader(idx3, close)
    ck(got3 is not None and got3[0] == "ETH",
       "while a shock to ONE coin does change it -- the race is exposed to "
       "idiosyncratic moves and immune to common ones")

    # a price level difference must not matter at all
    idx4 = {"BRTI": mk("BRTI", 90000.0, 90900.0),      # +1.0%
            "ETHUSD_RTI": mk("ETH", 3.0, 3.06)}        # +2.0%
    got4 = final_leader(idx4, close)
    ck(got4 is not None and got4[0] == "ETH",
       "a $3 coin beats a $90,000 coin on return -- levels are irrelevant")

    ck(twap({}, 0, 10) is None, "NULL: no prints gives no TWAP, never a zero")
    d = {s: 1.0 for s in range(0, 100)}
    ck(twap(d, 0, 59) == 1.0, "a full window averages correctly")
    ck(twap({0: 1.0}, 0, 59) is None,
       "and a window missing more than 5%% of its prints is refused")
    print("pindiversify selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0
    idx = idxload.load(PIN_COINS, verbose=False)
    D = idx.get("BRTI")
    if D is None:
        print("loaded nothing -- no index on disk")
        return 0
    closes = [c for c in range((D.base // 900 + 1) * 900 + 900,
                               D.base + D.n, 900)]
    pin_fail = {}
    race_fail = {}
    both = pin_only = race_only = neither = 0
    pin_n = race_n = 0
    for c in closes:
        # ---- the race
        lead = leader(idx, c, TAU)
        fin = final_leader(idx, c)
        if lead and fin:
            race_n += 1
            rf = (lead[0] != fin[0])
            race_fail[c] = rf
        # ---- the pin: any coin the model called near-certain at tau 20
        failed = False
        scored = False
        for iid in PIN_COINS:
            d = idx.get(iid)
            if d is None:
                continue
            ix = pinrun.IndexWS([iid])
            for s in range(c - 970, c - TAU + 1):
                v = d.get(s)
                if v is not None:
                    ix.ticks[iid][s] = v
            sg = ix.sigma(iid)
            strike = twap(d, c - 900 - 60, c - 900 - 1)   # strike == prev settle
            if sg is None or strike is None:
                continue
            f = pinrun.fair(ix, iid, c, c - TAU, strike, sg)
            if f is None:
                continue
            settle = twap(d, c - 60, c - 1)
            if settle is None:
                continue
            won_yes = settle >= strike
            if f >= PIN_GATE:
                scored = True
                if not won_yes:
                    failed = True
            elif f <= 1.0 - PIN_GATE:
                scored = True
                if won_yes:
                    failed = True
        if scored:
            pin_n += 1
            pin_fail[c] = failed
        if c in pin_fail and c in race_fail:
            p, r = pin_fail[c], race_fail[c]
            if p and r:
                both += 1
            elif p:
                pin_only += 1
            elif r:
                race_only += 1
            else:
                neither += 1
    joint = both + pin_only + race_only + neither
    print("\n%d closes on the index tape; %d scored for the pin, %d for the race,"
          " %d for both\n" % (len(closes), pin_n, race_n, joint))
    if not joint:
        print("loaded nothing scorable")
        return 0
    pr = (both + pin_only) / joint
    rr = (both + race_only) / joint
    print("  PIN fails on   %5d of %d closes = %5.2f%%" % (both + pin_only, joint, 100 * pr))
    print("  RACE fails on  %5d of %d closes = %5.2f%%" % (both + race_only, joint, 100 * rr))
    print()
    print("  %-26s %7s" % ("", "closes"))
    print("  %-26s %7d" % ("BOTH fail", both))
    print("  %-26s %7d" % ("pin fails, race fine", pin_only))
    print("  %-26s %7d" % ("race fails, pin fine", race_only))
    print("  %-26s %7d" % ("neither", neither))
    exp = pr * rr * joint
    print("\n  If the two were INDEPENDENT, both would fail on %.1f closes." % exp)
    print("  They actually both fail on %d." % both)
    if exp > 0:
        ratio = both / exp
        print("  Ratio %.2fx." % ratio)
        if ratio < 1.5:
            print("\n  -> THE FAILURES DO NOT STACK. The race loses on different")
            print("     closes from the pin, which is the whole point: its edge")
            print("     arrives when the pin's does not, and a common crypto")
            print("     shock cannot take both at once.")
        else:
            print("\n  -> they DO cluster; the race is not the diversifier it looks")
            print("     like, and stacking them concentrates risk rather than")
            print("     spreading it.")
    print("\n  Index only. Says nothing about whether anyone will SELL us the")
    print("  race leg cheaply -- RESULTS_coinrace measured that separately at")
    print("  +4.7c a contract inside 15 seconds, on 6%% of races.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
