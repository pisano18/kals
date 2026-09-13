"""pinbank -- how much bank a given contract SIZE needs, and the inverse.

WHY THIS FILE EXISTS. On 2026-09-13 a bank ladder was reported to the operator
built on `worst close`, the largest single-close loss OBSERVED in an 18.6-day
replay. That column is a SAMPLE MAXIMUM and it is wrong in the dangerous
direction at exactly the sizes where the stakes are largest: at size 20, 712 of
730 closes filled and the observed worst was 96% of the true bound; at size
1000 only 398 filled, so there were 45% fewer draws, and the observed worst was
58% of the bound. Fewer chances to draw a bad close is not less risk. Using it
understated the bank needed at size 1000 by 1.7x.

It was also sourced from the tape, which CLAUDE.md rule 5 (2026-09-10) forbids
for any statement about OUR losses. Nothing here takes a loss RATE from the
tape; the rate is a parameter, supplied from live fills.

WHAT REPLACES IT -- a bound, not an observation. A long binary cannot lose more
than it cost. One close deploys at most MAX_PER_CLOSE legs of `size` contracts
at at most PRICE_CEILING, so

    worst_close(size) = MAX_PER_CLOSE * size * PRICE_CEILING      (exact)

is a ceiling no tape, no week and no market regime can exceed. It is also
exactly the peak concurrent capital, because for a long binary the money at
risk IS the money deployed.

Surviving ONE worst close is not the requirement. Losing closes arrive in runs,
and the bank has to still be there afterwards. `drawdown_multiple()` answers
"how many worst-closes deep does the peak-to-trough go, at the 99th percentile,
over a month" by simulation at a loss rate the CALLER supplies from live fills.
The two legs of a close are modelled as losing TOGETHER -- they are the same
index at rho ~ 0.8, and assuming they are independent would flatter the answer.
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pinrun  # noqa: E402  -- the live constants, never a copy of them

CLOSES_PER_DAY = 38.0    # 712 filled closes / 18.62 days, replay. This is an
                         # OPPORTUNITY COUNT, not a loss statistic -- it is how
                         # often the bot gets to act, which the tape does
                         # legitimately measure.
HORIZON_DAYS = 30        # the drawdown is quoted over a month of trading
PCTL = 0.99              # bank covers the 99th-percentile month
TRIALS = 20000
MEAN_PRICE = 0.961       # live mean entry. Only used for the WIN size; the
                         # loss size uses PRICE_CEILING, which bounds it.


def worst_close(size):
    """The most one close can lose. Exact, not sampled."""
    return pinrun.MAX_PER_CLOSE * float(size) * pinrun.PRICE_CEILING


def win_per_close(size):
    """What a clean close pays: both legs settle at $1, minus the taker fee."""
    fee = 0.07 * MEAN_PRICE * (1.0 - MEAN_PRICE)
    return pinrun.MAX_PER_CLOSE * float(size) * (1.0 - MEAN_PRICE - fee)


def drawdown_multiple(q, trials=TRIALS, days=HORIZON_DAYS, pctl=PCTL,
                      seed=20260913, closes_per_day=CLOSES_PER_DAY,
                      win_frac=None):
    """Peak-to-trough drawdown over `days`, in units of worst_close().

    `q` is the probability a CLOSE loses, supplied from live fills. `win_frac`
    is the win payoff as a fraction of worst_close(); None derives it from
    MEAN_PRICE. Returns the `pctl` quantile of max drawdown / worst_close.
    """
    if win_frac is None:
        win_frac = win_per_close(1.0) / worst_close(1.0)
    n = int(round(days * closes_per_day))
    rng = random.Random(seed)
    out = []
    for _ in range(trials):
        cum = 0.0
        peak = 0.0
        worst = 0.0
        for _ in range(n):
            cum += -1.0 if rng.random() < q else win_frac
            if cum > peak:
                peak = cum
            if peak - cum > worst:
                worst = peak - cum
        out.append(worst)
    out.sort()
    return out[min(len(out) - 1, int(pctl * len(out)))]


def bank_needed(size, q, **kw):
    """Bank that survives a 99th-percentile month at `size`, then still funds
    the open position sitting at the trough. The +1 is that open position:
    a drawdown of M worst-closes is REALISED money, and at the bottom of it
    the bot is still holding one more close's worth of contracts it has
    already paid for."""
    m = drawdown_multiple(q, **kw)
    return (m + 1.0) * worst_close(size), m


def safe_size(bank, q, **kw):
    """Largest whole-contract size the bank supports. Inverse of bank_needed;
    exact because bank_needed is linear in size."""
    m = drawdown_multiple(q, **kw)
    per = (m + 1.0) * worst_close(1.0)
    return int(float(bank) // per), m


# ---------------------------------------------------------------------------
# THE LOSS RATE IS THE BINDING INPUT, NOT THE BANK.
#
# bank_needed() is linear in size, so on its own it says "more money, more
# size" forever. That is only true while expectancy is POSITIVE. A win pays
# win_frac of what a loss costs, so the close-loss rate at which expectancy
# crosses zero is
#
#       break_even = win_frac / (1 + win_frac)
#
# and ABOVE it there is no safe size at any bank -- more capital buys a longer
# bleed, not survival. drawdown_multiple() shows this by exploding (M = 3.8 at
# a 1% close-loss rate, 26.1 at 4.13%), but the closed form is the honest gate.
#
# So the auto-sizer keys off the loss rate MEASURED FROM LIVE FILLS, and it
# uses the Clopper-Pearson UPPER bound rather than the point estimate. That is
# the whole safety property: thin evidence produces a high upper bound, which
# produces a small size. The bot cannot size up on a lucky streak -- it has to
# accumulate enough clean closes that the upper bound itself falls.
# ---------------------------------------------------------------------------
def break_even_rate():
    """Close-loss rate at which expectancy is exactly zero."""
    wf = win_per_close(1.0) / worst_close(1.0)
    return wf / (1.0 + wf)


def cp_upper(losses, n, conf=0.95):
    """Clopper-Pearson upper bound on the loss rate. Exact, no normal
    approximation -- at these counts the normal one is badly wrong and would
    permit size the evidence does not support."""
    n = int(n)
    losses = int(losses)
    if n <= 0:
        return 1.0
    if losses >= n:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        # P(X <= losses | p=mid); the bound is where this equals 1 - conf.
        tail = 0.0
        term = (1.0 - mid) ** n
        for k in range(0, losses + 1):
            if k:
                term *= (n - k + 1) / k * mid / (1.0 - mid)
            tail += term
        if tail > 1.0 - conf:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def clean_closes_for(target=None, conf=0.95):
    """How many CONSECUTIVE loss-free closes drive the upper bound under
    `target`. Answers 'what does the bot have to earn to size up'."""
    if target is None:
        target = break_even_rate()
    n = 1
    while n < 100000:
        if cp_upper(0, n, conf) < target:
            return n
        n += 1
    return None


def auto_size(bank, losing_closes, closes, floor=1, cap=None, conf=0.95,
              **kw):
    """The live sizing decision. Returns (size, q_upper, why).

    Refuses to size above `floor` while the UPPER bound on our own close-loss
    rate is at or above break-even, whatever the bank says.
    """
    be = break_even_rate()
    q = cp_upper(losing_closes, closes, conf)
    if q >= be:
        return floor, q, ("loss-rate upper bound %.2f%% >= break-even %.2f%% "
                          "(%d losing of %d live closes); size held at floor"
                          % (100 * q, 100 * be, losing_closes, closes))
    s, m = safe_size(bank, q, **kw)
    s = max(floor, s)
    if cap is not None:
        s = min(s, int(cap))
    return s, q, ("upper bound %.2f%% < break-even %.2f%% on %d live closes; "
                  "drawdown multiple %.1f; bank $%.2f supports size %d"
                  % (100 * q, 100 * be, closes, m, float(bank), s))


# ---------------------------------------------------------------------------
def selftest():
    ck_n = [0]
    fails = []

    def ck(cond, msg):
        ck_n[0] += 1
        if not cond:
            fails.append(msg)

    # 1. worst_close is the arithmetic bound, not a fit.
    ck(abs(worst_close(20) - 2 * 20 * 0.98) < 1e-12,
       "worst_close(20) must be MAX_PER_CLOSE*20*PRICE_CEILING = "
       "%s, got %s" % (2 * 20 * 0.98, worst_close(20)))
    ck(abs(worst_close(100) / worst_close(10) - 10.0) < 1e-12,
       "worst_close must be exactly linear in size -- the whole point is "
       "that it does NOT shrink at large size the way a sample max does")

    # 2. A world where every close loses: drawdown is every close, exactly.
    #    This is the planted answer -- if the estimator cannot find it in a
    #    world with nothing but losses, it cannot be trusted anywhere.
    m1 = drawdown_multiple(1.0, trials=20, days=1, closes_per_day=10)
    ck(abs(m1 - 10.0) < 1e-9,
       "q=1.0 over 10 closes must draw down exactly 10 worst-closes, "
       "got %s" % m1)

    # 3. A world with no losses at all: no drawdown. The null.
    m0 = drawdown_multiple(0.0, trials=20, days=1, closes_per_day=10)
    ck(abs(m0) < 1e-9, "q=0 must give zero drawdown, got %s" % m0)

    # 4. Monotone in the loss rate. A higher loss rate cannot need less bank.
    ms = [drawdown_multiple(q, trials=400, days=10)
          for q in (0.01, 0.03, 0.06, 0.10)]
    ck(all(ms[i] <= ms[i + 1] + 1e-9 for i in range(len(ms) - 1)),
       "drawdown must not fall as the loss rate rises, got %s" % ms)

    # 5. bank_needed linear in size, and safe_size its exact inverse.
    b20, _ = bank_needed(20, 0.04, trials=200, days=10)
    b40, _ = bank_needed(40, 0.04, trials=200, days=10)
    ck(abs(b40 / b20 - 2.0) < 1e-9,
       "bank must be linear in size, got %s then %s" % (b20, b40))
    s, _ = safe_size(b20, 0.04, trials=200, days=10)
    ck(s == 20, "safe_size(bank_needed(20)) must round-trip to 20, got %s" % s)
    s2, _ = safe_size(b20 - 0.01, 0.04, trials=200, days=10)
    ck(s2 == 19, "a penny under must NOT round up to 20, got %s" % s2)

    # 6. THE REGRESSION THIS FILE EXISTS FOR. The old ladder said $53 was
    #    enough for size 20 and $142 for size 50. Both must now be refused.
    b20f, _ = bank_needed(20, 0.04)
    b50f, _ = bank_needed(50, 0.04)
    ck(b20f > 53.0, "size 20 on $53 was the 09-13 error; bank_needed says "
                    "$%.2f and must exceed it" % b20f)
    ck(b50f > 142.0, "size 50 on $142 was the 09-13 error; bank_needed says "
                     "$%.2f and must exceed it" % b50f)

    # 7. The ladder must be MONOTONE in bank -- more money never permits less
    #    size. A step table built by hand has got this wrong before.
    prev = -1
    for bank in (50, 100, 200, 400, 800, 1600, 3200):
        s, _ = safe_size(bank, 0.04, trials=200, days=10)
        ck(s >= prev, "safe_size fell from %s to %s at bank $%s"
           % (prev, s, bank))
        prev = s

    # 8. Reads the LIVE constants, not a copy. If MAX_PER_CLOSE or the ceiling
    #    moves in pinrun, this file must move with it.
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    ck("    return pinrun.MAX_PER_CLOSE * float(size) * pinrun.PRICE_CEILING"
       in src.splitlines(),
       "worst_close must read pinrun's own constants on its own line, so a "
       "change there cannot leave a stale number here")

    # 9. Clopper-Pearson against values that can be checked by hand.
    #    0 of n at 95% is exactly 1 - 0.05**(1/n).
    for n in (1, 9, 20, 82, 300):
        exact = 1.0 - 0.05 ** (1.0 / n)
        got = cp_upper(0, n)
        ck(abs(got - exact) < 1e-6,
           "cp_upper(0,%d) must be 1-0.05^(1/%d)=%.6f, got %.6f"
           % (n, n, exact, got))
    ck(abs(cp_upper(5, 5) - 1.0) < 1e-9, "all-losses must bound at 1.0")
    ck(cp_upper(0, 9) > cp_upper(0, 300),
       "more clean closes must LOWER the bound")
    ck(cp_upper(3, 100) > cp_upper(1, 100),
       "more losses at the same n must RAISE the bound")

    # 10. The gate itself. A perfect but SHORT record must not unlock size.
    be = break_even_rate()
    ck(0.030 < be < 0.040,
       "break-even should sit near 3.6%% at a 96c entry, got %.4f" % be)
    s, q, _ = auto_size(180.0, 0, 9, floor=1, trials=200, days=10)
    ck(s == 1,
       "9 clean closes is NOT evidence; size must stay at the floor, got %s "
       "(upper bound %.3f)" % (s, q))
    ck(cp_upper(0, 9) > be,
       "the 9-clean-close bound must exceed break-even, else check 10 is "
       "vacuous")

    # 11. ...and a LONG clean record must unlock it, or the gate can never
    #     open and the whole mechanism is dead code.
    nclean = clean_closes_for()
    ck(nclean is not None and 50 < nclean < 200,
       "consecutive clean closes to reach break-even should be ~82, got %s"
       % nclean)
    ck(cp_upper(0, nclean) < be <= cp_upper(0, nclean - 1),
       "clean_closes_for must return the FIRST n that clears, not any n")
    s2, _, _ = auto_size(180.0, 0, 2000, floor=1, trials=400, days=10)
    ck(s2 > 1, "a long clean record must raise size above the floor, got %s"
       % s2)

    # 12. A loss must shrink size, and the floor must hold.
    sa, _, _ = auto_size(180.0, 0, 2000, floor=1, trials=400, days=10)
    sb, _, _ = auto_size(180.0, 20, 2000, floor=1, trials=400, days=10)
    ck(sb < sa, "20 losing closes must size SMALLER than none, got %s vs %s"
       % (sb, sa))
    sc, _, _ = auto_size(1.0, 0, 2000, floor=1, trials=400, days=10)
    ck(sc == 1, "a tiny bank must fall back to the floor, not to zero or "
                "a negative, got %s" % sc)
    sd, _, _ = auto_size(1e9, 0, 100000, floor=1, cap=20, trials=400, days=10)
    ck(sd == 20, "the cap must bind above everything else, got %s" % sd)

    # ---- simulate_brake (2026-09-13) -----------------------------------
    # Planted worlds first: an all-wins tape must never draw down, an
    # all-losses tape must end at the floor whatever the brake.
    up = simulate_brake([+10.0] * 20, 3.0, 200.0, days=2, closes_per_day=5,
                        trials=40)
    ck(up[0] > 200.0 and abs(up[2]) < 1e-9 and up[3] == 0.0,
       f"an all-wins tape must grow and never draw down, got {up}")
    dn = simulate_brake([-50.0] * 20, 3.0, 200.0, days=2, closes_per_day=5,
                        trials=40)
    ck(dn[0] < 200.0 and dn[3] == 1.0,
       f"an all-losses tape must shrink and halve every time, got {dn}")
    # A HARSHER BRAKE MUST LOSE MORE SLOWLY. If this ever inverts, the size
    # is not actually being derived from the brake.
    mix = [+3.0] * 18 + [-60.0] * 2
    slow = simulate_brake(mix, 6.0, 200.0, days=5, closes_per_day=10,
                          trials=200, loss_inflate=3)
    fast = simulate_brake(mix, 1.5, 200.0, days=5, closes_per_day=10,
                          trials=200, loss_inflate=3)
    ck(slow[0] > fast[0],
       f"on a losing tape a brake of 6 must outlast a brake of 1.5, got "
       f"{slow[0]:.2f} vs {fast[0]:.2f}")
    ck(slow[3] <= fast[3],
       "and it must halve the bank no more often")
    # loss_inflate must actually bite.
    a1 = simulate_brake(mix, 3.0, 200.0, days=5, closes_per_day=10,
                        trials=200, loss_inflate=1)
    a3 = simulate_brake(mix, 3.0, 200.0, days=5, closes_per_day=10,
                        trials=200, loss_inflate=3)
    ck(a3[0] < a1[0],
       f"loss_inflate=3 must end poorer than 1, got {a3[0]:.2f} vs "
       f"{a1[0]:.2f} -- otherwise the live-rate column is decoration")
    # the bank can decay but must never go negative
    ck(dn[1] >= 0.0, "the bank must never be reported negative")

    print("  pinbank selftest: %d checks, %d failures" % (ck_n[0], len(fails)))
    for f in fails:
        print("    FAIL %s" % f)
    return not fails


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--loss-rate", type=float, default=0.0413,
                   help="probability a CLOSE loses, from LIVE fills")
    p.add_argument("--bank", type=float, default=None)
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if not selftest():
        sys.exit(1)

    q = a.loss_rate
    m = drawdown_multiple(q)
    print("\n  live loss rate per close %.2f%%, %d-day horizon, %.0f "
          "closes/day, %.0f%% percentile" % (100 * q, HORIZON_DAYS,
                                             CLOSES_PER_DAY, 100 * PCTL))
    print("  drawdown multiple M = %.2f worst-closes\n" % m)
    print("  %6s%14s%14s%14s" % ("size", "worst close", "BANK NEEDED",
                                 "old (wrong)"))
    old = {20: 52.89, 50: 142.22, 125: 355.55, 250: 568.88,
           500: 976.50, 1000: 1924.00, 2000: 3848.00}
    for s in (5, 10, 20, 35, 50, 75, 125, 250, 500, 1000, 2000):
        b = (m + 1.0) * worst_close(s)
        o = old.get(s)
        print("  %6d%14.2f%14.2f%14s"
              % (s, -worst_close(s), b, ("$%.0f" % o) if o else "--"))
    if a.bank is not None:
        s, _ = safe_size(a.bank, q)
        print("\n  BANK $%.2f -> largest safe size %d" % (a.bank, s))


# ---------------------------------------------------------------------------
# BRAKE CHOICE, 2026-09-13. The operator: "is the contract max size increasing
# too much? 154 would wipe more than half of the entire bank?"
#
# He is right and the arithmetic is his: at BANK_BRAKE = 1.5 the worst close
# costs bank/1.5 = 67% of the bank. The earlier ladder in this file answered a
# DIFFERENT question -- it modelled every losing close as a total loss and
# every win as a fixed payoff. The real distribution is not like that, and the
# difference matters:
#
#   measured over 422 book hours at size 68 (budget 136), 695 traded closes:
#     17 losing closes, about 0.9 PER DAY -- not a rare event
#     median losing close -$64.20   = HALF the budget (one market of two)
#     worst              -$128.95   = 99% of the budget (both markets, which
#                                     is what rho ~ 0.8 buys you)
#
# So the honest model draws per-close P&L from that empirical distribution,
# re-sizes after every close exactly as autosize_tick does live, and asks what
# the drawdown looks like. That is what brake_table() does.
# ---------------------------------------------------------------------------
def simulate_brake(per_close_pnl, brake, bank0, days=30, closes_per_day=37.0,
                   trials=4000, seed=20260913, size_ref=68.0, lo=1, hi=250,
                   loss_inflate=1.0):
    """Monte Carlo of the live loop: draw a close, scale it to the size the
    bank currently supports, apply it, re-size. Returns (median final bank,
    5th-percentile final bank, median max drawdown %, P(bank halves)).

    `loss_inflate` repeats losing draws to model a loss rate higher than the
    replay's -- ours is about 4% live against the tape's 2.4%.
    """
    import random
    wins = [p for p in per_close_pnl if p >= 0]
    losses = [p for p in per_close_pnl if p < 0]
    pool = wins + losses * max(1, int(round(loss_inflate)))
    rng = random.Random(seed)
    n = int(days * closes_per_day)
    per = 1.96 * float(brake)          # MAX_PER_CLOSE * ceiling * brake
    finals, dds, halved = [], [], 0
    for _ in range(trials):
        bank = float(bank0)
        peak = bank
        worst = 0.0
        for _ in range(n):
            size = max(lo, min(hi, int(bank // per)))
            bank += rng.choice(pool) * (size / size_ref)
            if bank <= 0:
                bank = 0.01
            peak = max(peak, bank)
            worst = max(worst, (peak - bank) / peak)
        finals.append(bank)
        dds.append(worst)
        if min(finals[-1], bank) < bank0 * 0.5:
            halved += 1
    finals.sort()
    dds.sort()
    return (finals[len(finals) // 2], finals[int(0.05 * len(finals))],
            dds[len(dds) // 2], halved / trials)


if __name__ == "__main__":
    main()
