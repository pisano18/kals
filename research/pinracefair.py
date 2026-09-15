#!/usr/bin/env python3
"""pinracefair.py -- a real probability for every Coin Race leg, and a test of
whether it beats the gap table and the market.

THE OPERATOR, 2026-09-15: "figure out a formula to reliably predict a winner or
gauge confidence in a way that you can bet on. It may not be as simple as 15
minute market is, be creative and find something."

WHY THE GAP TABLE FAILED. arm2 lost 73 bets / -$1,560 on paper, almost all on
photo finishes: a 1bp lead at tau 29 read ~89% and flipped. The table buckets a
lead by SIZE and TIME alone. It cannot see the two things that decide whether a
lead survives:

  1. HOW MUCH THE COINS ARE MOVING AGAINST EACH OTHER RIGHT NOW. A race is
     decided by the SPREAD between two coins' paths, not by either coin's move.
     Coins that co-move tightly make a small lead safe; a quiet BTC against a
     jumpy HYPE makes a large lead unsafe. The table averages over all of that.
  2. HOW MUCH OF THE FINAL AVERAGE IS ALREADY LOCKED. The same collapse the pin
     rests on: with r of 60 prints still to come, the unlocked part of the mean
     has variance s^2 * r(r+1)(2r+1) / (6 * 3600), not s^2 * r.

THE FORMULA. Each coin's final return is today's projection plus a random part:

    R_i(final) = R_i(now, locked + spot-imputed) + e_i
    e ~ MultivariateNormal(0, K(tau) * kappa^2 * C)

  C      5x5 covariance of 1-second log returns across the five indices, from
         the trailing W seconds (or the larger of a short and a long window --
         the pin's own finding that a 300 s ruler is too short after calm
         stretches)
  K(tau) the variance-collapse factor above, plus (tau - 60) for moves before
         the settlement window opens, which shift all 60 prints alike
  kappa  a fat-tail inflation, FITTED ON THE EARLIER HALF ONLY

P(coin i wins) is the share of simulated worlds where R_i is the largest,
computed with one fixed set of standard normals reused for every moment
(common random numbers), so two moments differ only by their inputs.

EVALUATION, and what keeps it honest:
  * the races split by TIME; W and kappa are chosen on the first half and
    everything reported is on the second half
  * the gap table baseline is also built on the first half only
  * log loss, Brier score and a reliability table, with photo finishes (top two
    within 2bp) reported separately because that is where the money was lost
  * then the trade tape: would betting on fair value have made money where the
    table lost? -- tape numbers are what the MARKET did, never our loss rate

INDEX TAPE ONLY for the forecast. No numpy (stdlib only, per the repo).

    python research/pinracefair.py --selftest
    python research/pinracefair.py
"""
import collections
import glob
import gzip
import json
import math
import os
import random
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import idxload                                               # noqa: E402
import pinracemodel as M                                     # noqa: E402

COINS = list(M.COINS)                  # BTC ETH SOL XRP HYPE
IIDS = [M.COINS[c] for c in COINS]
N_AVG, WINDOW = M.N_AVG, M.WINDOW
DRAWS = 1000
TAUS = [5, 10, 15, 20, 25, 30, 45, 60]
WINDOWS = ("300", "3600", "max")
KAPPAS = (1.0, 1.25, 1.5, 2.0, 2.5)
DATA = r"C:\kals\kalshi_data"


# ---------------------------------------------------------------- the maths
def var_factor(tau):
    """Variance of the unlocked part of the final 60-print mean, in units of
    one second's return variance.

    Inside the window (tau <= 60), r = tau prints are still to come and their
    mean moves by (1/60) * sum_k W_k, with Var = r(r+1)(2r+1)/6 / 3600.
    Before the window opens, the (tau - 60) seconds of drift shift every print
    alike, adding (tau - 60) in full."""
    if tau <= 0:
        return 0.0
    r = min(int(tau), N_AVG)
    k = r * (r + 1) * (2 * r + 1) / 6.0 / (N_AVG * N_AVG)
    if tau > N_AVG:
        k += (tau - N_AVG)
    return k


def cholesky(a):
    """Lower-triangular L with L L^T = a, for a small symmetric PSD matrix.
    A tiny jitter keeps near-singular matrices (two coins printing identically)
    from failing."""
    n = len(a)
    jit = 1e-12 * max(1e-30, sum(a[i][i] for i in range(n)) / n)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = a[i][j] - sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                L[i][j] = math.sqrt(max(s + jit, jit))
            else:
                L[i][j] = s / L[j][j]
    return L


_ZCACHE = {}


def normals(n=DRAWS, dim=5, seed=20260915):
    """One fixed matrix of standard normals per (n, dim, seed), reused for
    every moment. Keyed on all three: the first version cached one matrix and
    silently regenerated it at the default size, so a test that asked for
    20,000 draws was scored on 1,000."""
    key = (n, dim, seed)
    if key not in _ZCACHE:
        rng = random.Random(seed)
        _ZCACHE[key] = [[rng.gauss(0.0, 1.0) for _ in range(dim)] for _ in range(n)]
    return _ZCACHE[key]


def win_probs(rnow, cov, k, kappas=(1.0,), Z=None):
    """{kappa: [P(coin i wins) for i]} for projected returns `rnow` (list),
    per-second covariance `cov` (5x5), variance factor `k`."""
    n = len(rnow)
    L = cholesky([[cov[i][j] * k for j in range(n)] for i in range(n)])
    Z = normals(dim=n) if Z is None else Z
    eps = [[sum(L[i][j] * z[j] for j in range(i + 1)) for i in range(n)] for z in Z]
    out = {}
    for kap in kappas:
        wins = [0] * n
        for e in eps:
            best, bi = None, 0
            for i in range(n):
                v = rnow[i] + kap * e[i]
                if best is None or v > best:
                    best, bi = v, i
            wins[bi] += 1
        out[kap] = [w / float(len(eps)) for w in wins]
    return out


# ------------------------------------------------------ inputs, no look-ahead
class RaceSeries:
    """1-second log returns for the five indices over one race's history, with
    prefix sums so the covariance of ANY trailing window is O(1).

    Missing prints are carried forward (a zero return), and each window reports
    its coverage so a mostly-empty window is refused."""

    def __init__(self, idx, close, lookback=3700):
        self.t0 = close - WINDOW - N_AVG - lookback
        self.t1 = close
        n = self.t1 - self.t0
        dims = len(IIDS)
        last = [None] * dims
        self.have = [0] * (n + 1)
        self.s = [[0.0] * (n + 1) for _ in range(dims)]
        self.ss = {}
        for i in range(dims):
            for j in range(i, dims):
                self.ss[(i, j)] = [0.0] * (n + 1)
        ds = [idx.get(iid) for iid in IIDS]
        for step in range(n):
            sec = self.t0 + step + 1
            r = [0.0] * dims
            ok = True
            for i, D in enumerate(ds):
                v = D.get(sec) if D is not None else None
                if v is None or v <= 0:
                    ok = False
                else:
                    if last[i] is not None:
                        r[i] = math.log(v / last[i])
                    else:
                        ok = False
                    last[i] = v
            self.have[step + 1] = self.have[step] + (1 if ok else 0)
            for i in range(dims):
                self.s[i][step + 1] = self.s[i][step] + r[i]
            for (i, j), arr in self.ss.items():
                arr[step + 1] = arr[step] + r[i] * r[j]

    def cov(self, now, w):
        """(cov 5x5, coverage) over returns in (now - w, now]."""
        b = min(now, self.t1) - self.t0
        a = max(0, b - w)
        m = b - a
        if m < 30:
            return None, 0.0
        cover = (self.have[b] - self.have[a]) / float(m)
        dims = len(IIDS)
        mean = [(self.s[i][b] - self.s[i][a]) / m for i in range(dims)]
        c = [[0.0] * dims for _ in range(dims)]
        for (i, j), arr in self.ss.items():
            v = (arr[b] - arr[a]) / m - mean[i] * mean[j]
            c[i][j] = c[j][i] = v
        return c, cover


def pick_cov(series, now, which):
    """The covariance ruler: 300 s, 3600 s, or whichever of the two is larger
    in total variance -- never a shorter ruler after a calm stretch."""
    if which in ("300", "3600"):
        c, cov_ok = series.cov(now, int(which))
        return c if cov_ok >= 0.8 else None
    a, ca = series.cov(now, 300)
    b, cb = series.cov(now, 3600)
    if ca < 0.8 or cb < 0.8:
        return None
    return a if sum(a[i][i] for i in range(5)) >= sum(b[i][i] for i in range(5)) else b


def fair_at(idx, series, close, tau, which, kappas):
    """({kappa: {coin: P(win)}}, rnow) at `tau` seconds out, or (None, None).
    Everything read is at or before second close - tau."""
    rets = M.returns_at(idx, close, tau)
    if len(rets) < 5:
        return None, None
    c = pick_cov(series, close - tau, which)
    if c is None:
        return None, None
    rnow = [math.log(rets[k]) for k in COINS]
    pr = win_probs(rnow, c, var_factor(tau), kappas)
    return {k: dict(zip(COINS, v)) for k, v in pr.items()}, rets


# ---------------------------------------------------------------- scoring
def logloss(p, y):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return -math.log(p if y else 1 - p)


def fee(p):
    return math.ceil(0.07 * p * (1 - p) * 10000 - 1e-9) / 10000


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    # the collapse factor
    ck(var_factor(0) == 0.0, "nothing left to come, no uncertainty")
    ck(abs(var_factor(1) - 1.0 / 3600) < 1e-12,
       "one print left moves the mean by 1/60 of one second's move: 1/3600")
    ck(abs(var_factor(60) - 60 * 61 * 121 / 6.0 / 3600) < 1e-9,
       "a fresh window: 60*61*121/6/3600 = %.2f seconds' worth, not 60" % var_factor(60))
    ck(var_factor(10) < 10 / 30.0,
       "10 s out is %.3f seconds' worth -- far below the naive sqrt-time 10"
       % var_factor(10))
    ck(all(var_factor(t) < var_factor(t + 1) for t in range(0, 200)),
       "uncertainty only grows with time left")
    ck(abs(var_factor(90) - (var_factor(60) + 30)) < 1e-9,
       "30 s before the window adds 30 in full: it shifts every print alike")

    # cholesky
    a = [[4.0, 2.0], [2.0, 3.0]]
    L = cholesky(a)
    rec = [[sum(L[i][k] * L[j][k] for k in range(2)) for j in range(2)] for i in range(2)]
    ck(all(abs(rec[i][j] - a[i][j]) < 1e-9 for i in range(2) for j in range(2)),
       "cholesky reconstructs its matrix")

    # two coins: the MC must match the closed form Phi(gap / sd_diff)
    nd = math.erf
    s1, s2, rho, k = 1e-4, 2e-4, 0.5, 400.0
    cov2 = [[s1 * s1, rho * s1 * s2], [rho * s1 * s2, s2 * s2]]
    sd_diff = math.sqrt(k * (s1 * s1 + s2 * s2 - 2 * rho * s1 * s2))
    gap = 0.5 * sd_diff
    closed = 0.5 * (1 + nd(gap / sd_diff / math.sqrt(2)))
    Z2 = normals(n=40000, dim=2, seed=7)
    pr = win_probs([gap, 0.0], cov2, k, Z=Z2)[1.0]
    ck(abs(pr[0] - closed) < 0.008,
       "2 coins, lead of half a spread-sd, 40,000 draws: simulated %.4f vs "
       "closed form %.4f" % (pr[0], closed))
    ck(len(normals(n=40000, dim=2, seed=7)) == 40000 and len(normals(dim=5)) == DRAWS,
       "a test that asks for 40,000 draws gets 40,000 -- the cache no longer "
       "swaps in the default size")
    # perfect co-movement: any lead is safe
    covp = [[s1 * s1, s1 * s1], [s1 * s1, s1 * s1]]
    pr = win_probs([1e-7, 0.0], covp, 3600.0, Z=Z2)[1.0]
    ck(pr[0] > 0.99,
       "two coins that move IDENTICALLY: a tiny lead wins %.3f -- a common "
       "move cannot decide a race, which the gap table cannot see" % pr[0])
    # kappa widens
    pr = win_probs([gap, 0.0], cov2, k, kappas=(1.0, 2.0), Z=Z2)
    ck(pr[2.0][0] < pr[1.0][0],
       "fat-tail inflation lowers a leader's chance (%.3f -> %.3f)"
       % (pr[1.0][0], pr[2.0][0]))
    # null: identical coins, no lead -> uniform
    Z5 = normals(n=40000, dim=5, seed=9)
    ident = [[(1e-8 if i == j else 0.0) for j in range(5)] for i in range(5)]
    pr = win_probs([0.0] * 5, ident, 100.0, Z=Z5)[1.0]
    ck(all(abs(p - 0.2) < 0.02 for p in pr),
       "NULL: five identical independent coins level on points each win ~1 in 5 %s"
       % [round(p, 3) for p in pr])
    ck(abs(sum(pr) - 1.0) < 1e-9, "and the probabilities sum to one")

    # the series: covariance and NO LOOK-AHEAD
    base = 9_000_000 - (9_000_000 % WINDOW)
    close = base + 10 * WINDOW
    idx = {}
    rng = random.Random(3)
    for iid in IIDS:
        D = idxload.Dense(iid, close - 6000, 7000)
        lvl = 100.0
        for s in range(close - 6000, close + 900):
            lvl *= math.exp(rng.gauss(0, 1e-4))
            D.v[s - D.base] = lvl
        D.hi_used = -1
        idx[iid] = D
    ser = RaceSeries(idx, close)
    c, cover = ser.cov(close - 30, 300)
    ck(cover > 0.99 and all(abs(c[i][i] - 1e-8) < 0.35e-8 for i in range(5)),
       "planted 1e-4 per-second moves read back as variance ~1e-8 %s"
       % [round(c[i][i] * 1e8, 2) for i in range(5)])
    ck(all(abs(c[i][j]) < 0.35e-8 for i in range(5) for j in range(5) if i != j),
       "and independent coins read back with near-zero covariance")
    for D in idx.values():
        D.hi_used = -1
    fair_idx = {k: v for k, v in idx.items()}
    pr, _ = fair_at(fair_idx, RaceSeries(fair_idx, close), close, 20, "300", (1.0,))
    ck(pr is not None, "a fair value is produced on a full planted race")
    # RaceSeries reads up to close by construction; the forecast itself must not:
    for D in idx.values():
        D.hi_used = -1
    c_early, _ = ser.cov(close - 500, 300)
    # plant a huge move AFTER close-500 and confirm the early window ignores it
    for iid in IIDS:
        D = idx[iid]
        for s in range(close - 400, close):
            D.v[s - D.base] = D.v[s - D.base] * (1.0 + (0.05 if s % 2 else -0.05))
    ser3 = RaceSeries(idx, close)
    c_early2, _ = ser3.cov(close - 500, 300)
    ck(all(abs(c_early[i][j] - c_early2[i][j]) < 1e-15 for i in range(5) for j in range(5)),
       "NO LOOK-AHEAD: violent moves planted after second close-500 leave the "
       "covariance at close-500 exactly unchanged")
    c_late, _ = ser3.cov(close - 100, 300)
    ck(c_late[0][0] > 100 * c_early2[0][0],
       "while a window that includes them sees them (%.1fx)" % (c_late[0][0] / c_early2[0][0]))
    ck(abs(logloss(0.9, True) - (-math.log(0.9))) < 1e-12 and logloss(1.0, False) < 10,
       "log loss is clipped, so one confident miss cannot read as infinity")
    print("pinracefair selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0
    truth = json.load(open(M.TRUTH, encoding="utf-8"))
    idx = idxload.load(sorted(IIDS), verbose=False)
    D = idx.get("BRTI")
    if D is None:
        print("loaded nothing -- no index on disk")
        return 0
    races = []
    for stamp, legs in truth.items():
        c = M.close_of(stamp)
        if c is None or c - WINDOW - N_AVG - 3700 < D.base or c > D.base + D.n:
            continue
        w = [k for k, v in legs.items() if v == "yes"]
        if len(w) == 1:
            races.append((stamp, c, w[0]))
    races.sort(key=lambda r: r[1])
    if len(races) < 100:
        print("loaded nothing -- only %d races with an hour of history" % len(races))
        return 0
    cut = races[len(races) // 2][1]
    early = [r for r in races if r[1] < cut]
    late = [r for r in races if r[1] >= cut]
    print("\n%d races with an hour of index history: %d FIT, %d TEST (split by time)"
          % (len(races), len(early), len(late)))

    import pinraceno
    table = pinraceno.build_table(idx, early, sorted(set(TAUS) | set(M.TAUS)))

    # ---- compute every forecast once --------------------------------------
    rows = []          # (half, stamp, close, tau, which, kappa, probs, winner, top2gap)
    done = 0
    for half, group in (("fit", early), ("test", late)):
        for stamp, close, won in group:
            ser = RaceSeries(idx, close)
            for tau in TAUS:
                for which in WINDOWS:
                    pr, rets = fair_at(idx, ser, close, tau, which, KAPPAS)
                    if pr is None:
                        continue
                    srt = sorted(rets.values(), reverse=True)
                    top2 = (srt[0] - srt[1]) * 1e4
                    g = M.gaps(rets)
                    tab = {}
                    for coin in COINS:
                        pw = M.p_win(table, tau, g[coin] * 1e4, point=True)
                        tab[coin] = pw
                    for kap, probs in pr.items():
                        rows.append((half, stamp, close, tau, which, kap, probs, won, top2, tab))
            done += 1
            if done % 100 == 0:
                print("  ... %d races forecast" % done, flush=True)

    def score(sel, source):
        """(n legs, logloss, brier) for model 'fair' or 'table'."""
        n = ll = br = 0.0
        for r in sel:
            probs = r[6] if source == "fair" else r[9]
            for coin in COINS:
                p = probs[coin]
                if p is None:
                    p = 0.2
                y = coin == r[7]
                ll += logloss(p, y)
                br += (p - (1.0 if y else 0.0)) ** 2
                n += 1
        return int(n), (ll / n if n else float("nan")), (br / n if n else float("nan"))

    # ---- choose W and kappa on the FIT half only --------------------------
    best = None
    print("\nFIT HALF -- choosing the ruler and the fat-tail factor (lower is better)")
    print("  %-6s %6s %10s %10s" % ("ruler", "kappa", "log loss", "brier"))
    for which in WINDOWS:
        for kap in KAPPAS:
            sel = [r for r in rows if r[0] == "fit" and r[4] == which and r[5] == kap]
            n, ll, br = score(sel, "fair")
            print("  %-6s %6.2f %10.5f %10.5f" % (which, kap, ll, br))
            if best is None or ll < best[0]:
                best = (ll, which, kap)
    _, WHICH, KAP = best
    print("  -> chosen on the fit half: ruler %s, kappa %.2f" % (WHICH, KAP))

    # ---- report on the TEST half ------------------------------------------
    test = [r for r in rows if r[0] == "test" and r[4] == WHICH and r[5] == KAP]
    # the table rows are identical across ruler/kappa; take them from the same set
    print("\nTEST HALF (never used to choose anything): fair value vs the gap table")
    print("  %-22s %8s %10s %10s %10s %10s" % ("", "legs", "fair LL", "table LL", "fair Brier", "table Brier"))
    for label, f in (("all moments", lambda r: True),
                     ("photo finish (<2bp)", lambda r: r[8] < 2.0),
                     ("clear lead (>=4bp)", lambda r: r[8] >= 4.0)):
        for tl, tf in (("", lambda r: True), (" tau<=30", lambda r: r[3] <= 30)):
            sel = [r for r in test if f(r) and tf(r)]
            if not sel:
                continue
            n, fll, fbr = score(sel, "fair")
            _, tll, tbr = score(sel, "table")
            print("  %-22s %8d %10.5f %10.5f %10.5f %10.5f" % (label + tl, n, fll, tll, fbr, tbr))

    print("\nRELIABILITY on the TEST half -- when it says X, how often does it happen?")
    print("  %-12s %8s %9s %9s   %8s %9s %9s" % ("claimed", "fair n", "claimed", "actual", "table n", "claimed", "actual"))
    bins = [(0.0, 0.05), (0.05, 0.2), (0.2, 0.5), (0.5, 0.8), (0.8, 0.9), (0.9, 0.95), (0.95, 0.99), (0.99, 1.01)]
    for lo, hi in bins:
        agg = {"fair": [0, 0.0, 0], "table": [0, 0.0, 0]}
        for r in test:
            for src in ("fair", "table"):
                probs = r[6] if src == "fair" else r[9]
                for coin in COINS:
                    p = probs[coin]
                    if p is None:
                        continue
                    if lo <= p < hi:
                        a = agg[src]
                        a[0] += 1
                        a[1] += p
                        a[2] += 1 if coin == r[7] else 0
        f, t = agg["fair"], agg["table"]
        print("  %4.0f-%3.0f%%   %8d %8.1f%% %8.1f%%   %8d %8.1f%% %8.1f%%"
              % (100 * lo, min(100, 100 * hi), f[0], 100 * f[1] / f[0] if f[0] else 0,
                 100.0 * f[2] / f[0] if f[0] else 0, t[0], 100 * t[1] / t[0] if t[0] else 0,
                 100.0 * t[2] / t[0] if t[0] else 0))

    # ---- the tape: would betting on it have made money? --------------------
    print("\nTHE TRADE TAPE, TEST HALF, tau 2-30. Every figure is what the MARKET did")
    print("(an offer that existed and was taken), NOT our loss rate.")
    late_close = {c: (s, w) for s, c, w in late}
    files = sorted(glob.glob(os.path.join(DATA, "trade", "2026*.jsonl.gz")))[:-1]
    prints = []
    for fp in files:
        try:
            with gzip.open(fp, "rt") as fh:
                for line in fh:
                    if "CRYPTOLEAD" not in line or '"trade"' not in line:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                    except Exception:                        # noqa: BLE001
                        continue
                    _e, _, leg = (m.get("market_ticker") or "").rpartition("-")
                    if leg not in M.COINS:
                        continue
                    ts = int(m.get("ts_ms") or 0)
                    if not ts:
                        continue
                    sec = ts // 1000
                    cs = ((sec + WINDOW - 1) // WINDOW) * WINDOW
                    if cs not in late_close:
                        continue
                    tau = cs - sec
                    if not (2 <= tau <= 30):
                        continue
                    try:
                        yp = float(m["yes_price_dollars"])
                    except Exception:                        # noqa: BLE001
                        continue
                    if 0 < yp < 1:
                        prints.append((cs, leg, tau, yp, m.get("taker_side")))
        except (EOFError, zlib.error, OSError):
            pass
    print("  %d race prints in the test half, tau 2-30" % len(prints))
    cache = {}
    series_cache = {}

    def fair_leg(cs, tau):
        if (cs, tau) not in cache:
            if cs not in series_cache:
                series_cache.clear()
                series_cache[cs] = RaceSeries(idx, cs)
            pr, rets = fair_at(idx, series_cache[cs], cs, tau, WHICH, (KAP,))
            cache[(cs, tau)] = pr[KAP] if pr else None
        return cache[(cs, tau)]

    prints.sort()
    bets = collections.defaultdict(list)
    for cs, leg, tau, yp, side in prints:
        pr = fair_leg(cs, tau)
        if pr is None:
            continue
        if side == "yes":
            buy, px, worth = "yes", yp, pr[leg]
        elif side == "no":
            buy, px, worth = "no", round(1 - yp, 4), 1 - pr[leg]
        else:
            continue
        edge = worth - px - fee(px)
        key = (cs, leg, buy)
        bets[key].append((tau, px, worth, edge))

    won_of = {c: w for s, c, w in late}
    print("\n  rule: buy the FIRST print in a race where fair value beats the price")
    print("  by at least the edge shown. One bet per race, leg and side.")
    print("  %-10s %-9s %6s %6s %7s %9s %11s   %s" % ("edge >=", "price", "bets", "races", "won", "avg paid", "c/contract", "lost (TAPE)"))
    for emin in (0.02, 0.05):
        for plo, phi, pl in ((0.0, 0.99, "any"), (0.90, 0.99, "90c+"), (0.0, 0.90, "<90c")):
            sel = []
            for (cs, leg, buy), v in bets.items():
                for tau, px, worth, edge in sorted(v, reverse=True):
                    if edge >= emin and plo <= px < phi:
                        win = (leg == won_of[cs]) if buy == "yes" else (leg != won_of[cs])
                        sel.append((cs, px, win))
                        break
            if not sel:
                print("  %-10s %-9s %6d" % ("%.0fc" % (100 * emin), pl, 0))
                continue
            n = len(sel)
            w = sum(1 for s in sel if s[2])
            pnl = sum(((1 - px) if win else -px) - fee(px) for _, px, win in sel)
            print("  %-10s %-9s %6d %6d %7d %8.1fc %+10.2fc   %d of %d"
                  % ("%.0fc" % (100 * emin), pl, n, len({s[0] for s in sel}), w,
                     100 * sum(s[1] for s in sel) / n, 100 * pnl / n, n - w, n))
    print("\n  Counted in bets and races, never trades. The tape shows offers that")
    print("  were there; whether we would win them, and whether the ones we win")
    print("  are the bad ones, only live or paper fills can say.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
