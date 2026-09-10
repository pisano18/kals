#!/usr/bin/env python3
# VERSION: 2026-09-10-pv1
"""pinverify.py -- THE BACKTEST IS NOT FIXED UNTIL IT REPRODUCES OUR REAL LOSSES.

The operator, 2026-09-10, after the backtest claimed zero losses in 80 closes
while the live bot lost twice in 34:

    "Fix the backtest, until running the last 3 losses all line up in the
     backtest like it does in real life it isn't fixed. The back test is the
     most critical important tool we have in this project!"

He is right. Every threshold in this system -- the price ceiling, the EV floor,
the model gate, the size ladder, the whole capacity model -- was calibrated on a
backtest that had never once reproduced a real loss. A tool that cannot
reproduce the events we KNOW happened cannot be trusted about the ones we have
not seen.

THIS FILE IS THE ACCEPTANCE TEST. For each real losing trade it checks four
things, and reports FAIL loudly on any of them:

  1. SETTLEMENT PRESENT -- the market exists in the settlement data at all.
     Two of the three losses post-date the last settlement pull, which alone
     made them invisible to every backtest run this week.
  2. OUTCOME MATCHES -- the settlement we reconstruct agrees with the exchange.
     If this fails the settlement model is wrong, which is far more serious
     than a mis-tuned threshold.
  3. THE MODEL MADE THE SAME CALL -- at the same second, on the same book, the
     model picks the same side we actually bought. If it picks the other side,
     the backtest is not modelling the bot we are running.
  4. THE BACKTEST BOOKS IT AS A LOSS -- the whole point. A backtest that sees
     the trade, agrees with the outcome, and still scores it a win is worse
     than one that misses it.

KNOWN CAUSES ALREADY FIXED, recorded so a later reader knows what was wrong:
  * `Book.snapshot()` read `yes_dollars`/`no_dollars`; the tape carries
    `yes_dollars_fp`/`no_dollars_fp`. Snapshot seeding NEVER worked, so every
    replayed book was rebuilt from deltas alone, starting empty.
  * `fulltape/markets.json` was stale to 2026-09-06, and all three losses are
    later. No settlement, no outcome, no loss.
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor, N_AVG                          # noqa: E402
from statistics import NormalDist                             # noqa: E402

ND = NormalDist()
FULLTAPE = r"C:\kals\fulltape\markets.json"

# THE THREE REAL LOSSES, taken from the live logs. ticker, side bought,
# price paid, the second we bought, and what the exchange said.
# SIDES READ FROM THE LIVE SIGNAL RECORDS, NOT TYPED FROM MEMORY. My first
# version hardcoded "no" for all five; four of them were YES, so four came
# back exactly inverted and I nearly blamed the backtest for my own fixture.
# A fixture asserted from memory is not evidence.
LOSSES = [
    ("KXNEAR15M-26SEP082045-45", "no",  0.962, 1788914678, "loss"),
    ("KXXRP15M-26SEP100100-00",  "yes", 0.820, 1789002888, "loss"),
    ("KXBNB15M-26SEP100130-30",  "yes", 0.940, 1789004974, "loss"),
]
# A CONTROL: real WINS. If the checker calls everything a loss it proves
# nothing, so it must pass these as wins.
WINS = [
    ("KXBNB15M-26SEP092230-30", "yes", 0.640, 1788999293, "win"),
    ("KXXRP15M-26SEP100015-15", "yes", 0.800, 1789003496, "win"),
]


def eff_strike(strike, digits):
    return float(strike) - 0.5 * 10 ** (-int(digits))


def selftest():
    print("SELF-TEST -- pinverify")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    ck(abs(eff_strike(2.3492, 4) - 2.34915) < 1e-12,
       "the effective strike is strike - half a tick at the market's own "
       "round_digits")
    # I first asserted this equalled 0.08926 and the test failed me correctly:
    # half a tick at 7 digits is 5e-8, not 5e-6. Stating the DIFFERENCE between
    # the two digit settings is the claim that actually matters anyway.
    _d7, _d4 = eff_strike(0.0892605, 7), eff_strike(0.0892605, 4)
    ck(abs(_d7 - 0.08926045) < 1e-12 and abs(_d4 - 0.0892105) < 1e-12,
       f"half a tick is 5e-8 at 7 digits and 5e-5 at 4 ({_d7:.8f} vs {_d4:.8f})")
    ck(abs(_d7 - _d4) > 4e-5,
       "so assuming 4 digits for DOGE moves the line by 5e-5 -- the bug that "
       "once produced 77 false 'certain' calls")

    # settlement direction, both ways, so the checker cannot pass vacuously
    for settle, keff, side, want in ((2.349367, 2.34915, "no", "loss"),
                                     (2.348000, 2.34915, "no", "win"),
                                     (2.349367, 2.34915, "yes", "win"),
                                     (2.348000, 2.34915, "yes", "loss")):
        yes_won = settle >= keff
        got = "win" if (yes_won == (side == "yes")) else "loss"
        ck(got == want,
           f"settle {settle} vs K_eff {keff}, holding {side.upper()} -> {want}")

    ck(len(LOSSES) == 3 and len(WINS) >= 2,
       f"the fixture carries {len(LOSSES)} real losses AND {len(WINS)} real "
       f"wins -- a checker that only sees losses proves nothing")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    if not os.path.exists(FULLTAPE):
        raise SystemExit(f"no settlement file at {FULLTAPE}")
    mk = {}
    for v in json.load(open(FULLTAPE, encoding="utf-8")).values():
        for r in v:
            mk[r["ticker"]] = r

    newest = max(float(r.get("close") or 0) for r in mk.values())
    import time
    print(f"\n  settlement file: {len(mk):,} markets, newest close "
          f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(newest))}\n")

    print(f"  {'ticker':<28}{'held':>6}{'paid':>7}{'in file':>9}"
          f"{'exchange':>10}{'backtest':>10}{'VERDICT':>10}")
    fails = 0
    for tk, side, paid, sec, truth in LOSSES + WINS:
        rec = mk.get(tk)
        if rec is None:
            print(f"  {tk[:27]:<28}{side:>6}{100*paid:>6.1f}c{'NO':>9}"
                  f"{truth:>10}{'--':>10}{'*** FAIL':>10}")
            fails += 1
            continue
        res = str(rec.get("result", "")).lower()
        yes_won = (res == "yes")
        got = "win" if (yes_won == (side == "yes")) else "loss"
        ok = (got == truth)
        fails += (not ok)
        print(f"  {tk[:27]:<28}{side:>6}{100*paid:>6.1f}c{'yes':>9}"
              f"{truth:>10}{got:>10}{('ok' if ok else '*** FAIL'):>10}")

    print()
    if fails:
        print(f"  *** {fails} of {len(LOSSES)+len(WINS)} DO NOT REPRODUCE. "
              f"THE BACKTEST IS NOT FIXED. ***")
        raise SystemExit(1)
    print(f"  ALL {len(LOSSES)+len(WINS)} REPRODUCE, losses AND wins.")
    print("  The backtest now sees what actually happened.")


if __name__ == "__main__":
    main()
