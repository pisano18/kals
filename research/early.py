#!/usr/bin/env python3
# VERSION: 2026-09-08-e1
"""early.py -- IMPROVEMENT 5: trade EARLIER, on an arithmetic lock.

THE IDEA (the operator's)
  pin only trades tau in [3, 20]. By 20 seconds out everybody can see the
  outcome is decided, so the book is thin and the edge is small. Earlier --
  tau 20 to 120 -- fewer participants have done the settlement arithmetic, so
  there should be MORE resting depth and LARGER mispricings.

  The probability rule cannot go there: the tau<=60 cell is dead (+0.17c,
  t=+0.5) because far from the close the Gaussian is doing all the work. An
  ARITHMETIC LOCK does not need the Gaussian. It asks only whether the move
  required to flip the market exceeds what this index has EVER ACTUALLY DONE
  over that horizon.

THE ARITHMETIC
  Settlement is the mean of the 60 one-second prints in [close-60, close-1].
  With tau to go, `locked` of them are published and r are not, and the r
  unpublished ones sit at offsets [max(1,tau-60), tau-1] from now.
  Settlement lands exactly on the effective strike when the mean of those r
  prints equals

      x = (60*K_eff - locked_sum) / r        so     required_move = |x - spot|

  and with mu = (locked_sum + r*spot)/60 that is exactly (60/r)*|mu - K_eff|.

      K_eff = floor_strike - 0.5*10^-round_digits, round_digits READ from the
      exchange per series (earlypull.py), never assumed: it is 2 for BTC/ETH/
      BNB, 4 for SOL/XRP/ZEC/HYPE/NEAR and 7 for DOGE, and a wrong one moves
      the threshold by more than DOGE's whole 15-minute move.

  LOCK:  required_move > c * M(index, tau, trailing days)   (earlym.py)

NO-LOOKAHEAD -- WHAT IS ENFORCED AND WHERE
  1. M comes from earlym's per-UTC-day maxima and a close in day D may read
     only days D-1..D-3. Anchors that cross their own day's end are dropped,
     so no value feeding a day's maximum is stamped outside it.
  2. The quote is the last ticker message at or before close-tau
     (earlybook.py). The grid is filled by streaming forward in time.
  3. locked_sum, spot and sigma read the index only at seconds <= close-tau,
     through causal_sum()/causal_spot(), which take an explicit `hi` and
     assert on any request past it. The assert is not decoration: it is what
     makes "the code cannot express a leak" checkable.
  4. earlyleak.py builds three leaking variants of the SAME pipeline and
     shows each scores implausibly better. A discipline nobody tried to break
     is not a discipline.
"""
import argparse, json, math, os, sys
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor                               # noqa: E402
import earlyidx                                             # noqa: E402
import earlybook                                            # noqa: E402
import earlym                                               # noqa: E402

ND = NormalDist()
DAY = 86400
N_AVG = 60

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
    "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
}

MAX_QUOTE_AGE = 120       # a ticker row older than this is not "the book"
MIN_SIZE = 1.0            # non-fractional contracts; the book carries dust
EDGE_FLOOR = 0.005        # dollars per contract, AFTER the fee
CAP = 50                  # the fillable cap pin's depth work settled on


# ---------------------------------------------------------------- fees ----
def billed_fee(price, count):
    """Kalshi's taker fee as ACTUALLY charged: 0.07*p*(1-p)*count, ceilinged
    to the next $0.0001 (pinrun.billed_fee, measured on real fills)."""
    raw = 0.07 * price * (1.0 - price) * float(count)
    return math.ceil(raw * 10000.0) / 10000.0


def net_edge(price, count):
    """Dollars per contract left after the fee if the contract is CERTAIN."""
    return (1.0 - price) - billed_fee(price, count) / float(count)


# ------------------------------------------------------- causal index ----
class Index:
    """Forward-filled second-indexed index history with a hard causal gate.

    Every read takes `hi`, the newest second the caller is allowed to see.
    Asking for anything past it raises. That is the no-lookahead rule made
    into a runtime error instead of a comment.
    """

    def __init__(self, T0, arrays):
        import array
        self.T0 = T0
        self.F, self.P, self.LO = {}, {}, {}
        for iid, v in arrays.items():
            n = len(v)
            F = array.array("d", v)
            P = array.array("d", bytes(8 * (n + 1)))
            LO = array.array("i", bytes(4 * n))
            last, lastk = 0.0, -1
            for i in range(n):
                x = F[i]
                if x == 0.0:
                    F[i] = last
                else:
                    last, lastk = x, i
                LO[i] = lastk
                P[i + 1] = P[i] + F[i]
            self.F[iid], self.P[iid], self.LO[iid] = F, P, LO

    def _k(self, s):
        return s - self.T0

    def last_obs(self, iid, s, hi):
        assert s <= hi, "LOOKAHEAD: asked for second %d with hi=%d" % (s, hi)
        k = self._k(s)
        lo = self.LO.get(iid)
        if lo is None or not (0 <= k < len(lo)):
            return None
        j = lo[k]
        return None if j < 0 else j + self.T0

    def value(self, iid, s, hi):
        assert s <= hi, "LOOKAHEAD: asked for second %d with hi=%d" % (s, hi)
        k = self._k(s)
        F = self.F.get(iid)
        if F is None or not (0 <= k < len(F)):
            return None
        return F[k] or None

    def csum(self, iid, s0, s1, hi):
        """sum of forward-filled values over [s0, s1] inclusive."""
        assert s1 <= hi, "LOOKAHEAD: asked to %d with hi=%d" % (s1, hi)
        P = self.P.get(iid)
        if P is None:
            return None
        a, b = self._k(s0), self._k(s1)
        if a < 0 or b + 1 >= len(P) or b < a:
            return None
        return P[b + 1] - P[a]

    def sigma(self, iid, now, hi, win=300):
        """SD of 1-second index diffs over the trailing `win` seconds."""
        assert now <= hi, "LOOKAHEAD in sigma"
        F, LO = self.F.get(iid), self.LO.get(iid)
        if F is None:
            return None
        k = self._k(now)
        lo = k - win
        if lo < 1:
            return None
        d, prev = [], None
        for i in range(lo, k + 1):
            if LO[i] != i:
                prev = None
                continue
            if prev is not None:
                d.append(F[i] - F[prev])
            prev = i
        if len(d) < 20:
            return None
        m = sum(d) / len(d)
        return math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1))


# ---------------------------------------------------------- the model ----
def partial(ix, iid, close_s, now, hi):
    """(locked_sum, r) for the window [close-60, close-1].

    Follows pinrun.partial: the locked window ends at the NEWEST PRINT
    ACTUALLY HELD, and every second after it counts as remaining and is
    modelled with spot. A second whose print has not arrived is a print still
    to come, not a locked print to be guessed at.
    """
    lo, hi_w = close_s - N_AVG, min(now, close_s - 1)
    if hi_w < lo:
        return 0.0, N_AVG
    s = ix.last_obs(iid, hi_w, hi)
    if s is None or s < lo:
        return 0.0, N_AVG
    tot = ix.csum(iid, lo, s, hi)
    if tot is None:
        return None
    return tot, N_AVG - (s - lo + 1)


def eff_strike(K, d):
    return float(K) - 0.5 * (10.0 ** (-int(d)))


def state(ix, iid, close_s, tau, K, d):
    """Everything the decision needs at close-tau, and nothing after it."""
    now = close_s - tau
    hi = now                                # THE CAUSAL HORIZON
    spot = ix.value(iid, now, hi)
    if spot is None:
        return None
    obs = ix.last_obs(iid, now, hi)
    if obs is None or now - obs > 5:        # the index feed is stale
        return None
    p = partial(ix, iid, close_s, now, hi)
    if p is None:
        return None
    locked, r = p
    if r <= 0:
        return None
    Ke = eff_strike(K, d)
    mu = (locked + r * spot) / N_AVG
    req = (N_AVG / float(r)) * abs(mu - Ke)
    return {"now": now, "spot": spot, "locked": locked, "r": r,
            "Ke": Ke, "mu": mu, "req": req,
            "side": "yes" if mu >= Ke else "no"}


# ------------------------------------------------------------- t-stat ----
def tstat(xs):
    n = len(xs)
    if n < 2:
        return float("nan")
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m / math.sqrt(v / n) if v > 0 else float("nan")


def q(xs, p):
    if not xs:
        return float("nan")
    s = sorted(xs)
    return s[min(len(s) - 1, int(p * len(s)))]


# ------------------------------------------------------------- loader ----
def load_all():
    T0, arrays = earlyidx.load()
    meta, grid = earlybook.load()
    # only the nine indices that have settled markets on this tape; ADA and
    # BCH return zero settled markets and building their prefix arrays would
    # cost 20 s and 50 MB for nothing.
    used = set(SERIES_TO_INDEX.values())
    for k in [k for k in arrays if k not in used]:
        del arrays[k]
    ix = Index(T0, arrays)
    arrays.clear()
    mT0, taus, mtab = earlym.load()
    assert mT0 == T0, "index cache and M table disagree on T0"
    return ix, meta, grid, taus, mtab
