#!/usr/bin/env python3
# VERSION: 2026-08-25-s1
"""
settlewin.py -- the settlement-window partial average, in ONE place.

This existed in six copies. Two were right (engine.partial, leadlag.fair_series)
and four were wrong in the same way: they summed the ticks actually present but
divided using the count that SHOULD be present, so a few missing seconds put mu
thousands of dollars off and pinned fair value at 0 or 1.

The correct handling of a gap is to rescale the sum to the expected count, and
to refuse entirely when too much is missing. Both rules live here now.
"""

N_AVG = 60


def partial(ticks, close_sec, now_sec, min_frac=0.95):
    """(locked_sum, n_still_to_come) for the settlement window, or None.

    locked_sum is rescaled to the number of ticks that SHOULD be present, so a
    dropped second does not silently shrink the mean. Returns None when more
    than (1 - min_frac) of the locked stretch is missing, because at that point
    the reconstruction is not trustworthy and a wrong answer is worse than no
    answer.
    """
    lo = close_sec - N_AVG + 1
    hi = min(now_sec, close_sec)
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
