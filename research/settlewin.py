#!/usr/bin/env python3
# VERSION: 2026-09-08-s2
"""
settlewin.py -- the settlement-window partial average, in ONE place.

This existed in six copies. Two were right (engine.partial, leadlag.fair_series)
and four were wrong in the same way: they summed the ticks actually present but
divided using the count that SHOULD be present, so a few missing seconds put mu
thousands of dollars off and pinned fair value at 0 or 1.

The correct handling of a gap is to rescale the sum to the expected count, and
to refuse entirely when too much is missing. Both rules live here now.

THE WINDOW IS [close-60, close-1]. IT WAS WRONG UNTIL 2026-09-08.
--------------------------------------------------------------------------
Every version of this file before today used [close-59, close] -- it counted
the print stamped AT the close and dropped the print at close-60. That is off
by one second in the wrong direction and it is measurable three separate ways,
all of which were run on this tape before the change:

 1. Kalshi's own avg_60s_data block, carried on every cfbenchmarks_value
    message, states the window explicitly and states it EXCLUSIVE at the top:
        window_start_ts_ms      = (close-60)*1000
        window_end_ts_exclusive = close*1000
    so the last print in the settlement is close-1, not close.

 2. The mean of the ticks. Over 44 quarter-hour closes on four indices
    (BRTI, ETHUSD_RTI, SOLUSD_RTI, BNBUSD_RTI, 2026-09-05 20:00-23:00Z),
    mean(ticks[close-60 .. close-1]) reproduced Kalshi's published average
    44 times out of 44. mean(ticks[close-59 .. close]) reproduced it 11
    times, and only where the two end ticks happened to be equal.

 3. The strike identity strike(N+1) == settle(N). Against the settled market
    records in fulltape/markets.json over the same window, the [close-60,
    close-1] mean was the closer match to the next window's floor_strike on
    39 of 43 markets; e.g. KXBTC15M-26SEP052030-30 settled 79936.50 with
    mean[c-60..c-1] = 79936.5013 and mean[c-59..c] = 79936.2710.

CONSEQUENCE, and it is not cosmetic. At tau seconds to close the ticks
[close-60 .. close-tau] are already printed -- 61-tau of them -- and tau-1
remain. The old code called that 60-tau locked and tau remaining: it threw
away one locked print and substituted the current spot for it. Harmless where
|mu - K| >> sd; at tau = 2 it is the difference between one unknown print and
two, i.e. between sd = sigma/60 and sd = sigma*sqrt(5)/60.

partial() returns the number of prints STILL TO COME. A caller that needs the
variance of what is left must use that count (equivalently tau-1), never tau
-- see endgame.fair().
"""

N_AVG = 60


def partial(ticks, close_sec, now_sec, min_frac=0.95):
    """(locked_sum, n_still_to_come) for the settlement window, or None.

    The window is [close-60, close-1] inclusive -- 60 one-second prints, the
    last of them one second BEFORE the close. See the module docstring for
    the three measurements that establish that.

    locked_sum is rescaled to the number of ticks that SHOULD be present, so a
    dropped second does not silently shrink the mean. Returns None when more
    than (1 - min_frac) of the locked stretch is missing, because at that point
    the reconstruction is not trustworthy and a wrong answer is worse than no
    answer.
    """
    lo = close_sec - N_AVG
    hi = min(now_sec, close_sec - 1)
    if hi < lo:
        return 0.0, N_AVG                     # nothing locked in yet
    want = hi - lo + 1
    got = [ticks[s] for s in range(lo, hi + 1) if s in ticks]
    if not got or len(got) < want * min_frac:
        return None
    return sum(got) * (want / len(got)), N_AVG - want


def cond_mean(ticks, close_sec, now_sec, spot, min_frac=0.95):
    """E[settle | info at now_sec], or None if the window cannot be trusted."""
    p = partial(ticks, close_sec, now_sec, min_frac)
    if p is None:
        return None
    locked_sum, n_future = p
    return (locked_sum + n_future * spot) / N_AVG


# ===========================================================================
def selftest():
    """Plant a wild tick AT the close and at close-60 and check where each
    lands. The close tick must be EXCLUDED and the close-60 tick INCLUDED.

    This is the whole of bug 1 expressed as an assertion: under the old
    window both verdicts below came out exactly reversed.
    """
    print("=" * 78)
    print("SELF-TEST -- settlewin.partial(): the window is [close-60, close-1]")
    print("=" * 78)
    fails = []
    C = 1_760_000_000

    # ---- 1. membership: close-60 counts, close does not -------------------
    base = {s: 100.0 for s in range(C - 200, C + 200)}
    at_close = dict(base)
    at_close[C] = 100.0 + 60_000.0            # +1000 on the mean if counted
    at_lo = dict(base)
    at_lo[C - N_AVG] = 100.0 + 60_000.0

    p = partial(at_close, C, C)
    mu_close = None if p is None else p[0] / N_AVG
    p = partial(at_lo, C, C)
    mu_lo = None if p is None else p[0] / N_AVG
    print("\n  flat tape at 100.0, one tick moved by +60000")
    print(f"    spike AT close      -> locked mean {mu_close}")
    print(f"    spike at close-60   -> locked mean {mu_lo}")
    if mu_close is None or abs(mu_close - 100.0) > 1e-9:
        fails.append(f"a tick stamped AT the close changed the settlement "
                     f"mean to {mu_close} -- close is OUTSIDE the window "
                     f"[close-60, close-1] and must not be counted")
    if mu_lo is None or abs(mu_lo - 1100.0) > 1e-9:
        fails.append(f"a tick at close-60 gave a settlement mean of {mu_lo}, "
                     f"not 1100.0 -- close-60 is INSIDE the window and must "
                     f"be counted")

    # ---- 2. the locked/remaining split at every tau -----------------------
    print("\n  locked/remaining split, flat tape "
          "(want locked = 61-tau, remaining = tau-1):")
    for tau in (1, 2, 3, 5, 10, 20, 40, 60, 61):
        pr = partial(base, C, C - tau)
        if pr is None:
            fails.append(f"partial refused a complete tape at tau={tau}")
            continue
        locked_sum, r = pr
        n_locked = round(locked_sum / 100.0)
        want_locked = max(0, min(N_AVG, 61 - tau))
        want_r = N_AVG - want_locked
        ok = (n_locked == want_locked and r == want_r)
        print(f"    tau={tau:>3}  locked={n_locked:>3} (want {want_locked:>3})"
              f"   remaining={r:>3} (want {want_r:>3})   "
              f"{'ok' if ok else 'WRONG'}")
        if not ok:
            fails.append(f"tau={tau}: locked {n_locked}/remaining {r}, "
                         f"want {want_locked}/{want_r}")
    # tau=1 is the case that decides the endgame: nothing is left to happen.
    if partial(base, C, C - 1)[1] != 0:
        fails.append("at tau=1 the settlement is already fully determined "
                     "(the last print is close-1) but partial() still reports "
                     "prints to come")

    # ---- 3. the gap rule still holds --------------------------------------
    holed = {s: 100.0 for s in range(C - 200, C + 200)}
    for s in range(C - 30, C - 20):           # 10 of 60 missing = 16.7%
        holed.pop(s)
    if partial(holed, C, C) is not None:
        fails.append("partial accepted a window missing 10 of 60 ticks; the "
                     "min_frac guard is not firing")
    holed2 = {s: 100.0 for s in range(C - 200, C + 200)}
    holed2.pop(C - 30)                        # 1 of 60 missing
    pr = partial(holed2, C, C)
    if pr is None or abs(pr[0] / N_AVG - 100.0) > 1e-9:
        fails.append("partial did not rescale a single missing tick back to "
                     "the expected count")
    print("\n  gap rule: 10/60 missing refused, 1/60 rescaled -- ok")

    print()
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   - " + f)
        return False
    print("SELF-TEST PASSED -- the window is [close-60, close-1], the tick at")
    print("the close is excluded, and tau seconds out leaves tau-1 unknown.")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if selftest() else 1)
