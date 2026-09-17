#!/usr/bin/env python3
"""pinproject.py -- an honest compounding projection, with the measured ceiling.

THE OPERATOR, 2026-09-16: an earlier session projected the bank compounding to
$3,476 by 26 September and $570/day thereafter. He asked for it redone
accurately.

DAYS HERE ARE EASTERN, and that correction came from him too -- the first
version of this bucketed by UTC, which cuts the trading day at 8pm ET and
counted a fifth of the previous evening into each day. On Eastern days:

    Sep 14   3,319 contracts   +$81.14   full day
    Sep 15   2,511             +$76.32   full day, 5.7 h of downtime
    Sep 16   2,557             +$62.69   PARTIAL, 20 h in, on pace for ~$75

Sep 15's $76.32 is the number he quoted from his own screen; the UTC bucketing
had reported it as $91.72, which was a different slice of time altogether.

Against that, the old table projected +$93.02 for the 15th and +$113.97 for the
16th. The 15th came in at 82% of prediction with 5.7 hours lost; the 16th is on
pace for about 66% with no downtime at all. So downtime explains one day and
nothing explains the other -- which is what sent me looking at the books.

THE PROJECTION'S ONE FATAL ASSUMPTION: that daily contract VOLUME scales
linearly with our order size. It does not, and the reason is in the order books
themselves.

Measured over 446 real signals, the offer waiting for us when we decide:

    p10   10 contracts      p50   67       p90   536
    p25   23                p75  202       p95   957

HALF OF ALL OPPORTUNITIES HAVE FEWER THAN 67 CONTRACTS ON OFFER. Raising our
size above that does nothing for those closes. Replaying the same signals at
different sizes:

    size   90 -> 25,753 contracts   (today)
    size  200 -> 43,383             2.22x the size, 1.68x the volume
    size  500 -> 62,892             5.56x the size, 2.44x the volume
    size 1000 -> 80,062            11.11x the size, 3.11x the volume

So volume grows roughly as the SQUARE ROOT of size. Going 5.6x bigger buys 2.4x
the contracts, not 5.6x. A linear model overstates the bank at day 12 by about
2.3x and the steady-state daily rate by more.

WHAT THIS STILL CANNOT MODEL, and both errors point the same way (too
optimistic):

  MARKET IMPACT. We take 24% of the book at the median today. At size 500 we
  would be taking most of it, and the last contracts of a large take come at
  worse prices. Swept fills currently earn the same 2.40c per contract as
  unswept ones, but that is measured over 20-to-90-contract takes, not 500.
  ADVERSE SELECTION. The bigger the slice, the more of it is somebody's
  informed sell. Our live loss rate has run 31x the tape's for exactly this
  reason.

So treat every number here as a CEILING on the mechanical arithmetic, not a
forecast.

    python research/pinproject.py --selftest
    python research/pinproject.py
"""
import argparse
import sys

# (size, contracts over the same 446 signals) -- measured, not modelled
LADDER = [(90, 25753), (150, 36314), (200, 43383), (300, 52080),
          (500, 62892), (1000, 80062)]
BANK_BRAKE = 3.0
MAX_PER_CLOSE = 2
PRICE_CEILING = 0.98
BASE_SIZE = 90
BASE_CONTRACTS = 3100      # per day at size 90, from 2026-09-16 (3,017 at 84)


def size_for(bank):
    """The bot's own rule: size = bank / (BANK_BRAKE * MAX_PER_CLOSE * ceiling)."""
    return bank / (BANK_BRAKE * MAX_PER_CLOSE * PRICE_CEILING)


def volume_multiplier(size):
    """How much more volume than today, by interpolating the MEASURED ladder.

    Never extrapolates past the largest size we have evidence for -- beyond
    that it flattens, which is the honest thing to do with no data."""
    base = LADDER[0][1]
    if size <= LADDER[0][0]:
        return (size / LADDER[0][0]) * 1.0
    for (s0, v0), (s1, v1) in zip(LADDER, LADDER[1:]):
        if size <= s1:
            f = (size - s0) / (s1 - s0)
            return (v0 + f * (v1 - v0)) / base
    return LADDER[-1][1] / base


def project(bank, days, cents, uptime=0.95):
    """Day by day. Returns [(day, bank, size, contracts, net)]."""
    out = []
    for d in range(1, days + 1):
        s = size_for(bank)
        contracts = BASE_CONTRACTS * volume_multiplier(s) * uptime
        net = contracts * cents / 100.0
        bank += net
        out.append((d, bank, s, contracts, net))
    return out


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " + m) if c else ("FAIL: " + m))
        ok = ok and c

    ck(abs(size_for(529.98) - 90.1) < 0.5,
       "the live bank of $529.98 gives size %.0f, which is what the bot is "
       "actually running" % size_for(529.98))
    ck(abs(volume_multiplier(90) - 1.0) < 1e-9,
       "today's size is the baseline, multiplier exactly 1")
    ck(abs(volume_multiplier(500) - 62892 / 25753) < 1e-6,
       "a ladder point returns its measured value (%.3f), not an interpolation"
       % volume_multiplier(500))
    m2 = volume_multiplier(200)
    ck(1.0 < m2 < 200 / 90,
       "THE WHOLE POINT: 2.22x the size gives %.2fx the volume, which is more "
       "than 1 and far less than 2.22" % m2)
    ck(volume_multiplier(175) > volume_multiplier(150)
       and volume_multiplier(175) < volume_multiplier(200),
       "an in-between size interpolates between its neighbours")
    ck(volume_multiplier(5000) == volume_multiplier(1000),
       "NULL: past the largest size we have measured, it STOPS GROWING rather "
       "than extrapolating into fantasy")

    flat = project(1000.0, 3, 0.0)
    ck(all(abs(r[1] - 1000.0) < 1e-9 for r in flat),
       "NULL: zero cents a contract compounds to nothing, forever")
    neg = project(1000.0, 2, -1.0)
    ck(neg[-1][1] < 1000.0, "and a losing edge shrinks the bank")
    p = project(529.98, 2, 2.4)
    ck(p[0][1] > 529.98 and p[1][2] > p[0][2],
       "a winning day raises the bank, and the next day's size with it")
    print("pinproject selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--bank", type=float, default=529.98)
    ap.add_argument("--days", type=int, default=21)
    ap.add_argument("--uptime", type=float, default=0.95)
    a = ap.parse_args()
    if not selftest():
        return 1
    if a.selftest:
        return 0

    print("\nStarting bank $%.2f, uptime %.0f%%, size = bank / 5.88 (the bot's "
          "own rule).\n" % (a.bank, 100 * a.uptime))
    for name, cents in (("CAUTIOUS  2.0c/contract", 2.0),
                        ("EXPECTED  2.4c/contract", 2.4),
                        ("RECENT    3.0c/contract", 3.0)):
        rows = project(a.bank, a.days, cents, a.uptime)
        print("=== %s ===" % name)
        print("  %-5s %11s %7s %11s %11s" % ("day", "bank", "size", "contracts", "that day"))
        for d, bank, s, c, net in rows:
            if d <= 7 or d % 7 == 0 or d == a.days:
                print("  %-5d %11s %7.0f %11.0f %11s"
                      % (d, "$" + format(bank, ",.2f"), s, c, "+$%.2f" % net))
        print("  day %d: $%s, earning $%.2f a day\n"
              % (a.days, format(rows[-1][1], ",.2f"), rows[-1][4]))

    print("For contrast, the earlier projection assumed volume grows in step")
    print("with size. On that assumption day 12 reads $3,476 and the steady")
    print("rate $570 a day. The measured books do not support it: the same")
    print("5.6x increase in size buys 2.4x the contracts, not 5.6x.")
    print("\nAnd two things push the real number BELOW even these: taking a far")
    print("larger share of each book costs price, and a bigger slice is more")
    print("of somebody's informed sell. Neither is in the arithmetic.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
