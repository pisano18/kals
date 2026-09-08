#!/usr/bin/env python3
# VERSION: 2026-09-08-pfv1
"""pinfeat_vol.py -- FEATURE FAMILY 1: better volatility estimators for p_flip.

    python research/pinfeat_vol.py --selftest
    python research/pinfeat_vol.py --build      # writes results/pinfeat_vol.bin
    python research/pinfeat_vol.py --score

WHAT IS BEING DECIDED

pin buys a near-certain binary in the last seconds of a 15-minute crypto
market.  With r settlement prints still unpublished and locked sum L,

    mu = (L + r*spot)/60          fair = Phi((mu - K_eff)/sd)

and the ONLY estimated input is sd.  Today sd = sigma_300 * sqrt(var_factor(r))
where sigma_300 is the SD of 1-second index diffs over a trailing 300 s.  That
is one arbitrary window, not jump-robust, not regime-aware.  The per-trade
floor the operator wants is

    floor = fee + p_flip * price / (1 - p_flip)

so p_flip IS the deliverable, and an error of one percentage point in p_flip
is worth almost exactly one cent per contract at a 98c price
(EV = (1-q)*(1-price) - q*price, so dEV/dq = -1.00).

WHAT IS MEASURED

For every settled market on the tape and every tau on a FIXED exogenous grid,
the realised deviation e = (settlement mean) - mu is known.  Each estimator
proposes an sd; z = e/sd is its standardized residual.  An estimator is right
iff z has unit scale AND the tail of z matches what the probability map
claims.  Scored with Brier and log-loss on p_flip over a COMMON evaluation
set, because an estimator that simply trades less would otherwise win by
abstaining.

NO PEEKING

Every quantity used at (market, tau) is read from index seconds <= now =
close - tau.  The sampling loop is wrapped in a guard array in --selftest
that raises on any read past `now`.  One estimator, LEAK_fut900, deliberately
reads a window centred on `now` -- it is built to be caught, and the report
prints how much better it scores.

WRITES: results/pinfeat_vol.bin and results/pinfeat_vol.meta.json only.
Reads C:/kals only through the pre-built read-only early_cache.
"""
import argparse
import array
import calendar
import datetime
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import tdist                                                # noqa: E402

CACHE = os.path.join(ROOT, "early_cache")
OUTBIN = os.path.join(ROOT, "results", "pinfeat_vol.bin")
OUTMETA = os.path.join(ROOT, "results", "pinfeat_vol.meta.json")

N_AVG = 60
TAUS = (3, 5, 8, 10, 13, 16, 20)
LONG = 900              # longest backward window any estimator uses
MIN_VALID = 850         # valid 1-second diffs required inside that window

S2I = {"KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
       "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
       "KXBNB15M": "BNBUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
       "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI"}
SERIES = sorted(S2I)

ESTS = ["sd30", "sd60", "sd120", "sd300", "sd900",
        "ew15", "ew60", "ew300", "bp60", "bp300",
        "rm900", "rm3600", "LEAK_fut900"]
BASE = "sd300"
NCOL = 9 + len(ESTS)
# col 0 close 1 tau 2 r 3 dK 4 e 5 hour 6 series_idx 7 sigma300raw 8 vovrel


# ===========================================================================
_VF = {}


def var_factor(r):
    """Var( (1/60) sum_{j=1..r} (P_{t+j}-P_t) ) / sigma^2 for iid increments.

    The j-th future print carries increments 1..j, so increment k appears in
    r-k+1 of the r prints: weights r, r-1, ..., 1.  Identical to
    engine.var_factor(r, [1.0]) -- checked in selftest().
    """
    v = _VF.get(r)
    if v is None:
        v = sum(i * i for i in range(1, r + 1)) / float(N_AVG * N_AVG)
        _VF[r] = v
    return v


def phi(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def ts_of(s):
    return calendar.timegm(datetime.datetime.strptime(
        s, "%Y-%m-%dT%H:%M:%SZ").timetuple())


def numf(x):
    return float(str(x).replace(",", ""))


# ===========================================================================
class Tape:
    """One index's second-indexed values plus O(1) window statistics."""

    HALFLIVES = (15, 60, 300)

    def __init__(self, v, t0):
        n = len(v)
        self.v = v
        self.t0 = t0
        self.n = n
        pres = array.array("i", bytes(4 * (n + 1)))
        csv = array.array("d", bytes(8 * (n + 1)))
        nv = array.array("i", bytes(4 * (n + 1)))
        d1 = array.array("d", bytes(8 * (n + 1)))
        d2 = array.array("d", bytes(8 * (n + 1)))
        bp = array.array("d", bytes(8 * (n + 1)))
        ews = {h: array.array("d", bytes(8 * (n + 1))) for h in self.HALFLIVES}
        lam = {h: 0.5 ** (1.0 / h) for h in self.HALFLIVES}
        cur = {h: 0.0 for h in self.HALFLIVES}
        seeded = {h: False for h in self.HALFLIVES}
        prev_absd = 0.0
        prev_ok = False
        for i in range(n):
            x = v[i]
            ok = x != 0.0
            pres[i + 1] = pres[i] + (1 if ok else 0)
            csv[i + 1] = csv[i] + (x if ok else 0.0)
            dv = None
            if ok and i > 0 and v[i - 1] != 0.0:
                dv = x - v[i - 1]
            if dv is None:
                nv[i + 1] = nv[i]
                d1[i + 1] = d1[i]
                d2[i + 1] = d2[i]
                bp[i + 1] = bp[i]
                prev_ok = False
            else:
                nv[i + 1] = nv[i] + 1
                d1[i + 1] = d1[i] + dv
                d2[i + 1] = d2[i] + dv * dv
                a = abs(dv)
                bp[i + 1] = bp[i] + (a * prev_absd if prev_ok else 0.0)
                prev_absd = a
                prev_ok = True
                for h in self.HALFLIVES:
                    if not seeded[h]:
                        cur[h] = dv * dv
                        seeded[h] = True
                    else:
                        cur[h] = lam[h] * cur[h] + (1.0 - lam[h]) * dv * dv
            for h in self.HALFLIVES:
                ews[h][i + 1] = cur[h]
        self.pres, self.csv, self.nv = pres, csv, nv
        self.d1, self.d2, self.bp, self.ew = d1, d2, bp, ews

    # ---- window statistics.  Windows are (i-H, i] in SECOND index. ----
    def nvalid(self, i, H):
        return self.nv[i + 1] - self.nv[i - H + 1]

    def sd_win(self, i, H):
        lo = i - H + 1
        if lo < 0:
            return None
        m = self.nv[i + 1] - self.nv[lo]
        if m < 10:
            return None
        s = self.d1[i + 1] - self.d1[lo]
        q = self.d2[i + 1] - self.d2[lo]
        var = (q - s * s / m) / (m - 1)
        return math.sqrt(var) if var > 0 else None

    def bp_win(self, i, H):
        """Bipower: sqrt((pi/2) * mean |d_k||d_{k-1}|).  A single jump enters
        only through its two neighbours, so it does not inflate the whole
        window the way a squared term does."""
        lo = i - H + 1
        if lo < 0:
            return None
        m = self.nv[i + 1] - self.nv[lo]
        if m < 10:
            return None
        s = self.bp[i + 1] - self.bp[lo]
        val = (math.pi / 2.0) * s / (m - 1)
        return math.sqrt(val) if val > 0 else None

    def ew_at(self, i, h):
        x = self.ew[h][i + 1]
        return math.sqrt(x) if x > 0 else None

    def vovrel(self, i, H=900, blk=60):
        """SD of the rolling block SD over its mean -- how unstable sigma
        itself is.  Unitless, so comparable across coins."""
        vals = []
        for b in range(H // blk):
            s = self.sd_win(i - b * blk, blk)
            if s is not None and s > 0:
                vals.append(s)
        if len(vals) < 5:
            return None
        m = sum(vals) / len(vals)
        if m <= 0:
            return None
        var = sum((x - m) ** 2 for x in vals) / (len(vals) - 1)
        return math.sqrt(var) / m

    def rmatched(self, i, r, W, step=1):
        """sd of (1/60)*sum_{j=1..r}(P_{s+j}-P_s) measured DIRECTLY over
        anchors s in [i-W, i-r].  No iid assumption and no var_factor:
        whatever autocorrelation the index has is already inside it."""
        if r <= 0:
            return 0.0
        tot = 0.0
        cnt = 0
        v, csv, pres = self.v, self.csv, self.pres
        lo = i - W
        if lo < 1:
            return None
        for s in range(lo, i - r + 1, step):
            if pres[s + r + 1] - pres[s] != r + 1:
                continue
            x = (csv[s + r + 1] - csv[s + 1] - r * v[s]) / N_AVG
            tot += x * x
            cnt += 1
        if cnt < 100:
            return None
        return math.sqrt(tot / cnt)


class Guard:
    """Wraps a Tape and raises if any read touches a second past `now`.
    This is the leak-catcher for the sampling loop itself."""

    def __init__(self, tape, now_idx):
        self.t = tape
        self.now = now_idx
        self.v = tape.v
        self.n = tape.n

    def _ck(self, i):
        if i > self.now:
            raise AssertionError("LOOKAHEAD: read second %d > now %d"
                                 % (i, self.now))

    def sd_win(self, i, H):
        self._ck(i)
        return self.t.sd_win(i, H)

    def bp_win(self, i, H):
        self._ck(i)
        return self.t.bp_win(i, H)

    def ew_at(self, i, h):
        self._ck(i)
        return self.t.ew_at(i, h)

    def vovrel(self, i, H=900, blk=60):
        self._ck(i)
        return self.t.vovrel(i, H, blk)

    def rmatched(self, i, r, W, step=1):
        self._ck(i)
        return self.t.rmatched(i, r, W, step)

    def nvalid(self, i, H):
        self._ck(i)
        return self.t.nvalid(i, H)


# ===========================================================================
def make_row(tape, close_i, tau, dK_num, e_num, hour, sidx, allow_leak=True):
    """All estimators at now = close-tau.  Returns NCOL floats or None."""
    now = close_i - tau
    r = tau - 1
    if tape.nvalid(now, LONG) < MIN_VALID:
        return None
    vf = math.sqrt(var_factor(r))
    out = [0.0] * NCOL
    out[1] = tau
    out[2] = r
    out[3] = dK_num
    out[4] = e_num
    out[5] = hour
    out[6] = sidx
    s300 = tape.sd_win(now, 300)
    if s300 is None:
        return None
    out[7] = s300
    vv = tape.vovrel(now)
    out[8] = vv if vv is not None else -1.0
    vals = {}
    for H, name in ((30, "sd30"), (60, "sd60"), (120, "sd120"),
                    (300, "sd300"), (900, "sd900")):
        s = tape.sd_win(now, H)
        vals[name] = None if s is None else s * vf
    for h, name in ((15, "ew15"), (60, "ew60"), (300, "ew300")):
        s = tape.ew_at(now, h)
        vals[name] = None if s is None else s * vf
    for H, name in ((60, "bp60"), (300, "bp300")):
        s = tape.bp_win(now, H)
        vals[name] = None if s is None else s * vf
    vals["rm900"] = tape.rmatched(now, r, 900, 1)
    vals["rm3600"] = tape.rmatched(now, r, 3600, 4)
    if allow_leak:
        # DELIBERATE LEAK: the window is CENTRED on now, so it eats the
        # settlement window itself.  Must score implausibly better.
        fut = tape.t.sd_win(now + LONG, LONG) if isinstance(tape, Guard) \
            else tape.sd_win(now + LONG, LONG)
        vals["LEAK_fut900"] = None if fut is None else fut * vf
    else:
        vals["LEAK_fut900"] = None
    for j, name in enumerate(ESTS):
        x = vals.get(name)
        if x is None or x <= 0:
            if name == "LEAK_fut900":
                out[9 + j] = -1.0
                continue
            return None
        out[9 + j] = x
    return out


# ===========================================================================
def load_markets():
    st = json.load(open(os.path.join(CACHE, "settled.json")))
    by = {}
    for tk, m in st.items():
        s = m.get("series")
        if s not in S2I:
            continue
        if m.get("result") not in ("yes", "no"):
            continue
        if m.get("floor_strike") is None or m.get("round_digits") is None:
            continue
        d = int(m["round_digits"])
        by.setdefault(s, []).append(
            (ts_of(m["close_ts"]), tk,
             numf(m["floor_strike"]) - 0.5 * (10.0 ** (-d)),
             1.0 if m["result"] == "yes" else 0.0, d))
    for s in by:
        by[s].sort()
    return by


def build(verbose=True, guard=False):
    meta = json.load(open(os.path.join(CACHE, "idx_meta.json")))
    t0 = meta["T0"]
    mk = load_markets()
    rows = array.array("d")
    stat = {"markets_scanned": 0, "markets_used": 0, "nocov": 0,
            "rows": 0, "row_reject": 0, "outcome_reproduced": 0,
            "outcome_missed": 0}
    for sidx, s in enumerate(SERIES):
        iid = S2I[s]
        v = array.array("d")
        with open(os.path.join(CACHE, "idx_%s.bin" % iid), "rb") as f:
            v.frombytes(f.read())
        tape = Tape(v, t0)
        used = 0
        for close_s, tk, K, res, dg in mk.get(s, []):
            stat["markets_scanned"] += 1
            ci = close_s - t0
            if ci - 60 - 3700 < 0 or ci + LONG + 2 >= tape.n:
                stat["nocov"] += 1
                continue
            if tape.pres[ci] - tape.pres[ci - 60] != 60:
                stat["nocov"] += 1
                continue
            settle_mean = sum(v[ci - 60:ci]) / 60.0
            got_res = 1.0 if settle_mean >= K else 0.0
            if got_res == res:
                stat["outcome_reproduced"] += 1
            else:
                stat["outcome_missed"] += 1
            hour = (close_s // 3600) % 24
            got = 0
            for tau in TAUS:
                now = ci - tau
                r = tau - 1
                locked = sum(v[ci - 60:now + 1])
                spot = v[now]
                if spot == 0.0:
                    continue
                mu = (locked + r * spot) / 60.0
                src = Guard(tape, now) if guard else tape
                row = make_row(src, ci, tau, mu - K, settle_mean - mu,
                               hour, sidx)
                if row is None:
                    stat["row_reject"] += 1
                    continue
                row[0] = float(close_s)
                rows.extend(row)
                stat["rows"] += 1
                got += 1
            if got:
                used += 1
        stat["markets_used"] += used
        if verbose:
            print("    %-10s %5d markets, %7d rows so far"
                  % (s, used, stat["rows"]))
        del tape, v
    os.makedirs(os.path.dirname(OUTBIN), exist_ok=True)
    with open(OUTBIN, "wb") as f:
        f.write(rows.tobytes())
    stat["ncol"] = NCOL
    stat["ests"] = ESTS
    stat["taus"] = list(TAUS)
    json.dump(stat, open(OUTMETA, "w"), indent=1)
    if verbose:
        print("\n  %s rows -> %s" % ("{:,}".format(stat["rows"]), OUTBIN))
        print("  markets scanned {:,}  used {:,}  no-coverage {:,}".format(
            stat["markets_scanned"], stat["markets_used"], stat["nocov"]))
        print("  GROUND TRUTH: the settlement window reproduced the settled "
              "outcome on {:,} markets, missed {:,}".format(
                  stat["outcome_reproduced"], stat["outcome_missed"]))
    return stat


# ===========================================================================
def clip(p, lo=1e-6):
    return min(max(p, lo), 1.0 - lo)


def brier_ll(pred, obs):
    b = sum((p - o) ** 2 for p, o in zip(pred, obs)) / len(pred)
    l = -sum(o * math.log(clip(p)) + (1 - o) * math.log(clip(1 - p))
             for p, o in zip(pred, obs)) / len(pred)
    return b, l


def fit_t(zs, grid=(2.5, 3, 4, 5, 6, 8, 10, 15, 20, 30, 60, 1e6)):
    """MLE scale per df on a grid; return the (df, scale) with the best
    log-likelihood.  Fixed-point EM step, stdlib only."""
    n = len(zs)
    best = None
    for df in grid:
        s = math.sqrt(sum(z * z for z in zs) / n)
        if df > 2.2:
            s *= math.sqrt(max(df - 2.0, 0.2) / df)
        for _ in range(80):
            num = sum(z * z / (df + (z / s) ** 2) for z in zs)
            new = math.sqrt((df + 1.0) * num / n)
            if abs(new - s) < 1e-12 * max(s, 1e-12):
                s = new
                break
            s = new
        ll = (n * (math.lgamma((df + 1) / 2.0) - math.lgamma(df / 2.0)
                   - 0.5 * math.log(df * math.pi) - math.log(s))
              - ((df + 1) / 2.0) * sum(math.log(1.0 + (z / s) ** 2 / df)
                                       for z in zs))
        if best is None or ll > best[0]:
            best = (ll, df, s)
    return best[1], best[2]


def t_tail(a, df, s):
    """P(z < -a) for z ~ s * t_df."""
    if df >= 1e5:
        return phi(-a / s)
    return tdist.student_t_cdf(-a / s, df)


def flip_of(a, i):
    """Did the favoured side lose?  The favoured side is sign(mu-K); the
    outcome is sign(mu-K+e).  Same question for every estimator."""
    dK = a[i * NCOL + 3]
    e = a[i * NCOL + 4]
    return 0 if ((dK + e >= 0.0) == (dK >= 0.0)) else 1


def load_rows():
    a = array.array("d")
    with open(OUTBIN, "rb") as f:
        a.frombytes(f.read())
    return a, len(a) // NCOL
