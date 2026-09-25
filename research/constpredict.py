#!/usr/bin/env python3
# VERSION: 2026-09-25-cp1
"""constpredict.py -- CAN WE PROJECT THE LAST PRINTS BETTER THAN "FLAT AT SPOT"?

THE QUESTION. Settlement is the mean of the 60 one-second CF prints over
[close-60, close-1]. With r prints still to come, pinrun projects every one of
them at the newest print it holds (`spot`):

    mu0 = (locked_sum + r*spot) / 60          (pinrun.projection)

Everything the bot believes rests on that line. If something known at the
decision -- the constituent exchange books (feed_data/index_replica), or the
last few prints' own drift / bounce -- predicts the MEAN OF THE REMAINING
PRINTS better than `spot`, then

    mu1 = mu0 + r * yhat / 60,   yhat = predicted (mean of remaining - spot)

is a better settlement forecast, and some of the markets the bot bought would
have shown a lower confidence and been refused.

This is NOT the killed FEED_LEAD loss gate (results/FEED_LEAD_2026-09-24.md):
that asked whether the books had moved against us BEFORE the entry. This asks
whether the books (and the prints' own dynamics) say where the REST of the
window goes, and it scores that on the settlement itself.

WHAT IS MEASURED
  A. Projection error on every quarter-hour close in the recorded window, per
     coin, at r = 45, 30, 20, 10 prints left:
       e = settle - mu   (basis points of spot)
     for four projections:
       M0 flat      -- what the bot does
       M1 index     -- + the coin's own last 1/3/10/30 s print moves
       M2 const     -- + the replica's weighted mid, median mid and Coinbase
                        mid minus spot, and the replica's own 3 s move, all
                        read at the SAME second as spot (information-matched)
       M3 fresh     -- + the replica one second newer than spot. The replica
                        second s is recorded ~3 ms after s; CF's print for s
                        reaches the bot 0.2-1.0 s after s. So for that window
                        a live replica is one print ahead. It is a variant,
                        not the headline: it needs a live replica in the bot.
     Fit: least squares with NO intercept (flat = 0 stays the null), fitted on
     the first half of the days, scored on the second half. Reported: MSE
     reduction, its t across closes (cluster = close), and wrong-side calls
     against the strike (strike(N+1) == settle(N) on these series).
  B. The live bot's own entries (results/pinrun-live-*.jsonl, first filled
     entry per market). Each entry's fair is REBUILT from the tape (locked
     prints, spot second matched by value, the logged sigma) and checked
     against the logged fair before anything is counted; then the projection
     is shifted by the cross-fitted model (fit on the OTHER half of the days,
     so every entry is out of sample) and the run's own gates are re-applied:
       refused if conf1 < pin  or  edge1 < edge_floor   (from the run's start
       record; edge1 = logged edge + (conf1 - conf0)).
     Money per market is Kalshi's ledger (pinday.ledger_markets), never the
     log's own P&L.

WHAT WOULD MAKE A GOOD NUMBER AN ARTEFACT, and where it is checked
  - Look-ahead: every feature is read at a second <= the spot second (M3 at
    spot+1, labelled). The target uses Kalshi's own avg_60s_data at the close.
  - In-sample fitting: train/test split by day; the live part is cross-fitted.
  - Clock artefact: the replica is stamped by our recorder; if it were late
    it would LAG and the fit would find nothing, not something.
  - Fat tails: MSE is quoted with the median absolute error beside it.

UNITS: closes (one per coin per quarter hour), never trades. Pooled rows are
summed within a close before the standard error is taken.

READ-ONLY: streams C:\\kals\\kalshi_data\\cfbenchmarks_value and
C:\\kals\\feed_data\\index_replica one hour file at a time; writes only a cache
under --scratch and a table file. No orders, no API calls, no replay.

    python research/constpredict.py --selftest
    python research/constpredict.py --extract   # build the scratch cache
    python research/constpredict.py             # analyse (extracts if needed)
"""
import argparse
import array
import calendar
import glob
import gzip
import json
import math
import os
import pickle
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gzsalvage                                               # noqa: E402
from engine import var_factor, N_AVG                           # noqa: E402

DATA = r"C:\kals\kalshi_data"
FEED = r"C:\kals\feed_data"
RESULTS = os.path.normpath(os.path.join(HERE, "..", "results"))
SCRATCH = (r"C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo"
           r"\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad\creative"
           r"\constituent-predictor")

W = 150                      # seconds kept before each close: [C-150, C-1]
LOOK = 30                    # longest lookback a feature uses
RS = (45, 30, 20, 10)
NAN = float("nan")
IDS = {"BRTI": "BTC", "ETHUSD_RTI": "ETH", "SOLUSD_RTI": "SOL",
       "XRPUSD_RTI": "XRP", "DOGEUSD_RTI": "DOGE", "BNBUSD_RTI": "BNB",
       "HYPEUSD_RTI": "HYPE", "NEARUSD_RTI": "NEAR", "ZECUSD_RTI": "ZEC"}
COINS = tuple(IDS.values())
FEED_COINS = ("BTC", "ETH", "SOL", "XRP", "DOGE")
SERIES_COIN = {"KX%s15M" % c: c for c in COINS}
MODELS = ("M1", "M2", "M3")
MODEL_NAME = {"M0": "flat at spot (the bot)", "M1": "own last prints",
              "M2": "+ exchange books, same second",
              "M3": "+ exchange books, 1 s fresher"}

T_TIME = '\\"time\\":'           # inside the escaped `data` string
T_VALUE = '\\"value\\":\\"'
T_ID = '"index_id":"'


# ---------------------------------------------------------------------------
# small numerics
# ---------------------------------------------------------------------------
def phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def is_nan(x):
    return x != x


def slot(sec):
    """(close, index into the W-array) for a second, or None if the second is
    not in the last W seconds before a quarter-hour close."""
    m = sec % 900
    if m < 900 - W:
        return None
    return sec - m + 900, m - (900 - W)


def solve(A, b):
    """Gaussian elimination with partial pivoting; A is n x n (lists)."""
    n = len(b)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda i: abs(M[i][c]))
        if abs(M[p][c]) < 1e-15:
            return [0.0] * n
        M[c], M[p] = M[p], M[c]
        for i in range(c + 1, n):
            f = M[i][c] / M[c][c]
            if f:
                for j in range(c, n + 1):
                    M[i][j] -= f * M[c][j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))) / M[i][i]
    return x


def ols(rows, ridge=1e-6):
    """No-intercept least squares on [(x_vector, y)]. Tiny ridge, scaled to the
    diagonal, only so a constant-zero column cannot make it singular."""
    if not rows:
        return None
    k = len(rows[0][0])
    A = [[0.0] * k for _ in range(k)]
    b = [0.0] * k
    for x, y in rows:
        for i in range(k):
            xi = x[i]
            if xi:
                b[i] += xi * y
                Ai = A[i]
                for j in range(i, k):
                    Ai[j] += xi * x[j]
    for i in range(k):
        for j in range(i):
            A[i][j] = A[j][i]
    for i in range(k):
        A[i][i] += ridge * (A[i][i] + 1e-12)
    return solve(A, b)


def dot(w, x):
    return sum(a * b for a, b in zip(w, x))


# ---------------------------------------------------------------------------
# extraction -- one hour file at a time, only the last W seconds of each close
# ---------------------------------------------------------------------------
def parse_index_line(line, want_ids):
    """(iid, sec, value, avg_or_None) or None. Fast path on the escaped
    `data` string; falls back to json when the tokens are not where expected.
    avg is Kalshi's avg_60s_data when its window ends exactly at `sec`."""
    a = line.find(T_ID)
    if a < 0:
        return None
    e = line.find('"', a + len(T_ID))
    iid = line[a + len(T_ID):e]
    if iid not in want_ids:
        return None
    i = line.find(T_TIME)
    if i < 0:
        return _parse_index_json(line, want_ids)
    j = i + len(T_TIME)
    k = j
    while k < len(line) and line[k].isdigit():
        k += 1
    try:
        ms = int(line[j:k])
    except ValueError:
        return None
    sec = int(round(ms / 1000.0))
    if sec % 900 and slot(sec) is None:
        return None
    v = line.find(T_VALUE, i)
    if v < 0:
        return _parse_index_json(line, want_ids)
    ve = line.find('\\"', v + len(T_VALUE))
    try:
        val = float(line[v + len(T_VALUE):ve])
    except ValueError:
        return None
    avg = None
    if sec % 900 == 0:
        try:
            m = json.loads(line)
            ad = (m.get("msg") or {}).get("avg_60s_data") or {}
            if int(ad.get("window_end_ts_exclusive", -1)) == sec * 1000:
                avg = float(ad["value"])
        except (ValueError, KeyError, TypeError):
            avg = None
    return iid, sec, val, avg


def _parse_index_json(line, want_ids):
    try:
        m = json.loads(line)
    except ValueError:
        return None
    d = m.get("msg") or {}
    iid = d.get("index_id")
    if iid not in want_ids:
        return None
    inner = d.get("data")
    if isinstance(inner, str):
        try:
            inner = json.loads(inner)
        except ValueError:
            return None
    try:
        sec = int(round(float(inner["time"]) / 1000.0))
        val = float(inner["value"])
    except (KeyError, TypeError, ValueError):
        return None
    if sec % 900 and slot(sec) is None:
        return None
    avg = None
    if sec % 900 == 0:
        ad = d.get("avg_60s_data") or {}
        try:
            if int(ad.get("window_end_ts_exclusive", -1)) == sec * 1000:
                avg = float(ad["value"])
        except (TypeError, ValueError):
            pass
    return iid, sec, val, avg


def extract_index(files, want_ids=IDS, say=print):
    """P[coin][close] = array('d', W) of prints (nan = missing);
    S[coin][close] = Kalshi's 60-print average at the close."""
    P = {c: {} for c in want_ids.values()}
    S = {c: {} for c in want_ids.values()}
    stats = {}
    for n, path in enumerate(files):
        for line in gzsalvage.iter_lines(path, stats=stats):
            r = parse_index_line(line, want_ids)
            if r is None:
                continue
            iid, sec, val, avg = r
            coin = want_ids[iid]
            if avg is not None:
                S[coin][sec] = avg
            sl = slot(sec)
            if sl is None:
                continue
            C, i = sl
            arr = P[coin].get(C)
            if arr is None:
                arr = P[coin][C] = array.array("d", [NAN] * W)
            arr[i] = val
        if say and (n + 1) % 100 == 0:
            say("    index %d/%d files" % (n + 1, len(files)))
    return P, S, stats


def extract_replica(files, coins=FEED_COINS, say=print):
    """R[coin][close] = (wmid, median_mid, coinbase_mid) arrays('d', W)."""
    R = {c: {} for c in coins}
    stats = {}
    for n, path in enumerate(files):
        for line in gzsalvage.iter_lines(path, stats=stats):
            a = line.find('"sec":')
            if a < 0:
                continue
            k = a + 6
            e = k
            while e < len(line) and line[e].isdigit():
                e += 1
            try:
                sec = int(line[k:e])
            except ValueError:
                continue
            sl = slot(sec)
            if sl is None:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            C, i = sl
            for c in coins:
                x = d.get(c)
                if not isinstance(x, dict):
                    continue
                t = R[c].get(C)
                if t is None:
                    t = R[c][C] = tuple(array.array("d", [NAN] * W)
                                        for _ in range(3))
                try:
                    t[0][i] = float(x.get("wmid"))
                except (TypeError, ValueError):
                    pass
                try:
                    t[1][i] = float(x.get("median_mid"))
                except (TypeError, ValueError):
                    pass
                cb = (x.get("per_ex") or {}).get("coinbase") or {}
                try:
                    t[2][i] = 0.5 * (float(cb["b"]) + float(cb["a"]))
                except (KeyError, TypeError, ValueError):
                    pass
        if say and (n + 1) % 100 == 0:
            say("    replica %d/%d files" % (n + 1, len(files)))
    return R, stats


# ---------------------------------------------------------------------------
# features and target
# ---------------------------------------------------------------------------
def features(P, R, i0, kind):
    """Feature vector (bps of spot) for the spot at array index i0, or None.
    kind 1: own prints; 2: + replica same second; 3: + replica one second on."""
    if i0 - LOOK < 0:
        return None
    spot = P[i0]
    if is_nan(spot) or spot <= 0:
        return None
    q = 1e4 / spot
    x = []
    for k in (1, 3, 10, 30):
        v = P[i0 - k]
        if is_nan(v):
            return None
        x.append((spot - v) * q)
    if kind >= 2:
        if R is None:
            return None
        wm, md, cb = R
        for v in (wm[i0], md[i0], cb[i0], wm[i0 - 3]):
            if is_nan(v):
                return None
        x += [(wm[i0] - spot) * q, (md[i0] - spot) * q, (cb[i0] - spot) * q,
              (wm[i0] - wm[i0 - 3]) * q]
    if kind >= 3:
        if i0 + 1 >= W:
            return None
        for v in (wm[i0 + 1], md[i0 + 1]):
            if is_nan(v):
                return None
        x += [(wm[i0 + 1] - spot) * q, (md[i0 + 1] - spot) * q]
    return x


def target(P, settle, i0):
    """(y_bps, locked, r): y = mean of the remaining prints implied by the
    settlement, minus spot, in bps of spot. None if the locked prints are not
    all held (a missing locked print makes settlement unreconstructable)."""
    lo = W - N_AVG
    r = W - 1 - i0
    if r <= 0 or i0 < lo:
        return None
    locked = 0.0
    for s in range(lo, i0 + 1):
        v = P[s]
        if is_nan(v):
            return None
        locked += v
    spot = P[i0]
    rem_mean = (N_AVG * settle - locked) / r
    return (rem_mean - spot) / spot * 1e4, locked, r


def twap(P):
    v = P[W - N_AVG:]
    if any(is_nan(x) for x in v):
        return None
    return sum(v) / float(N_AVG)


# ---------------------------------------------------------------------------
# the close-level study
# ---------------------------------------------------------------------------
def build_rows(P, S, R, coin, r, kind):
    """[(close, x, y)] for one coin at r prints left."""
    out = []
    i0 = W - 1 - r
    for C, arr in P.items():
        st = S.get(C)
        if st is None:
            st = twap(arr)
            if st is None:
                continue
        t = target(arr, st, i0)
        if t is None:
            continue
        rr = R.get(C) if R is not None else None
        x = features(arr, rr, i0, kind)
        if x is None:
            continue
        out.append((C, x, t[0]))
    return out


def day_of(C):
    return time.strftime("%Y-%m-%d", time.gmtime(C - 1))


def split_days(closes):
    days = sorted({day_of(C) for C in closes})
    half = len(days) // 2
    return set(days[:half]), set(days[half:])


def score(test_rows, w, r):
    """Per-close (e0^2, e1^2, |e0|, |e1|) in settlement bps."""
    f = r / float(N_AVG)
    out = {}
    for C, x, y in test_rows:
        yh = dot(w, x) if w is not None else 0.0
        e0 = f * y
        e1 = f * (y - yh)
        out[C] = (e0 * e0, e1 * e1, abs(e0), abs(e1))
    return out


def summarise(per_close):
    """MSE reduction, its t across closes, median abs errors."""
    n = len(per_close)
    if n < 30:
        return None
    d = [a - b for a, b, _, _ in per_close.values()]
    m0 = sum(a for a, _, _, _ in per_close.values()) / n
    m1 = sum(b for _, b, _, _ in per_close.values()) / n
    md = sum(d) / n
    sd = math.sqrt(sum((x - md) ** 2 for x in d) / (n - 1)) if n > 1 else 0.0
    t = md / (sd / math.sqrt(n)) if sd > 0 else 0.0
    a0 = sorted(x[2] for x in per_close.values())
    a1 = sorted(x[3] for x in per_close.values())
    return {"n": n, "rmse0": math.sqrt(m0), "rmse1": math.sqrt(m1),
            "red": (m0 - m1) / m0 if m0 > 0 else 0.0, "t": t,
            "mae0": a0[n // 2], "mae1": a1[n // 2]}


def pooled(per_coin):
    """Sum the per-coin squared errors within a close, then summarise."""
    acc = {}
    for pc in per_coin:
        for C, (a, b, c, d) in pc.items():
            s = acc.setdefault(C, [0.0, 0.0, 0.0, 0.0, 0])
            s[0] += a
            s[1] += b
            s[2] += c
            s[3] += d
            s[4] += 1
    per = {C: (s[0], s[1], s[2] / s[4], s[3] / s[4]) for C, s in acc.items()}
    return summarise(per)


def wrong_side(test_rows, w, r, P, S, coin):
    """(n with a strike, wrong-side calls flat, wrong-side calls model).
    strike(C) == settle(C-900) on these series."""
    f = r / float(N_AVG)
    n = w0 = w1 = 0
    i0 = W - 1 - r
    for C, x, y in test_rows:
        K = S.get(C - 900)
        st = S.get(C)
        arr = P.get(C)
        if K is None or st is None or arr is None:
            continue
        spot = arr[i0]
        mu0 = st - f * y * spot / 1e4          # settle - e0 (in price)
        yh = dot(w, x)
        mu1 = mu0 + f * yh * spot / 1e4
        if st == K:
            continue
        n += 1
        up = st > K
        w0 += (mu0 > K) != up
        w1 += (mu1 > K) != up
    return n, w0, w1


def study(P, S, R, rs=RS, coins=None, say=print):
    """{(coin, r, model): summary} on the second half of days, fitted on the
    first; plus pooled rows and wrong-side counts."""
    coins = coins or [c for c in COINS if c in P]
    res, pool, ws = {}, {}, {}
    allC = set()
    for c in coins:
        allC |= set(P[c])
    train_days, test_days = split_days(allC)
    for r in rs:
        for model in MODELS:
            kind = int(model[1])
            pcs = []
            for c in coins:
                if kind >= 2 and c not in R:
                    continue
                rows = build_rows(P[c], S[c], R.get(c) if kind >= 2 else None,
                                  c, r, kind)
                tr = [(x, y) for C, x, y in rows if day_of(C) in train_days]
                te = [(C, x, y) for C, x, y in rows if day_of(C) in test_days]
                if len(tr) < 50 or len(te) < 30:
                    continue
                w = ols(tr)
                pc = score(te, w, r)
                s = summarise(pc)
                if s is None:
                    continue
                s["w"] = w
                s["n_train"] = len(tr)
                res[(c, r, model)] = s
                ws[(c, r, model)] = wrong_side(te, w, r, P[c], S[c], c)
                pcs.append(pc)
            if pcs:
                pool[(r, model)] = pooled(pcs)
    return res, pool, ws, (min(train_days), max(train_days),
                           min(test_days), max(test_days))


# ---------------------------------------------------------------------------
# live entries
# ---------------------------------------------------------------------------
def load_live(paths):
    """First filled entry per market with the signal that produced it, and
    the run's gates. Returns (entries, counts)."""
    entries, counts = {}, {"orders_filled": 0, "no_signal": 0, "files": 0}
    for p in sorted(paths):
        counts["files"] += 1
        gates = {"pin": None, "edge_floor": None}
        last_sig = {}
        try:
            fh = open(p, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"kind"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                k = d.get("kind")
                if k == "start":
                    gates = {"pin": d.get("pin"),
                             "edge_floor": d.get("edge_floor")}
                elif k == "signal" and d.get("live", True):
                    # keyed by ticker alone: order records before 09-20 carry
                    # no `want`, and the signal is written just before its order
                    last_sig[d.get("ticker")] = d
                elif k == "order":
                    try:
                        filled = float(d.get("filled") or 0)
                    except (TypeError, ValueError):
                        filled = 0.0
                    if filled <= 0:
                        continue
                    counts["orders_filled"] += 1
                    tk = d.get("ticker")
                    if tk in entries:
                        continue
                    sig = last_sig.get(tk)
                    if sig is None or (d.get("want") and sig.get("want")
                                       and d.get("want") != sig.get("want")):
                        counts["no_signal"] += 1
                        continue
                    entries[tk] = {"ticker": tk,
                                   "want": d.get("want") or sig.get("want"),
                                   "sig": sig, "order": d, "gates": dict(gates),
                                   "file": os.path.basename(p)}
    return entries, counts


def close_of(entry):
    o = entry["order"]
    try:
        t = float(o.get("t_ms_decide")) / 1000.0
    except (TypeError, ValueError):
        t = calendar.timegm(time.strptime(entry["sig"]["t"][:19],
                                          "%Y-%m-%dT%H:%M:%S"))
    tau = entry["sig"].get("tau") or o.get("tau_at_send") or 0
    return int(round((t + float(tau)) / 900.0)) * 900, t


def rebuild(entry, arr):
    """Rebuild the bot's projection from the tape. Returns dict or a reason."""
    sig = entry["sig"]
    C, t_dec = close_of(entry)
    spot = sig.get("spot")
    sigma = sig.get("sigma")
    K = sig.get("strike")
    if spot is None or sigma is None or K is None or sig.get("fair") is None:
        return "signal lacks spot/sigma/strike/fair"
    base = C - W
    hit = None
    for s in range(int(t_dec), int(t_dec) - 6, -1):
        i = s - base
        if 0 <= i < W and not is_nan(arr[i]) and abs(arr[i] - spot) <= 1e-9 * max(1.0, abs(spot)):
            hit = i
            break
    if hit is None:
        return "spot value not found in the tape near the decision"
    r = W - 1 - hit
    if r <= 0 or r > 58:
        return "r out of range"
    lo = W - N_AVG
    locked = 0.0
    for s in range(lo, hit + 1):
        if is_nan(arr[s]):
            return "a locked print is missing from the tape"
        locked += arr[s]
    mu0 = (locked + r * spot) / N_AVG
    digits = sig.get("digits")
    Keff = float(K) - (0.5 * 10.0 ** (-int(digits)) if digits is not None else 0.0)
    sd = float(sigma) * math.sqrt(var_factor(int(r), [1.0]))
    if sd <= 0:
        return "zero sd"
    z0 = (mu0 - Keff) / sd
    return {"C": C, "i0": hit, "r": r, "mu0": mu0, "sd": sd, "Keff": Keff,
            "z0": z0, "fair0": phi(z0), "spot": spot}


def conf_of_side(fair, want):
    return fair if want == "yes" else 1.0 - fair


def gate(conf, edge, gates):
    pin = gates.get("pin")
    ef = gates.get("edge_floor")
    if pin is not None and conf < float(pin) - 1e-9:
        return False
    if ef is not None and edge < float(ef) - 1e-9:
        return False
    return True


def counterfactual(entries, P, S, R, ledger, say=print):
    """Cross-fitted: each entry gets a model fitted on the OTHER half of days."""
    allC = set()
    for c in P:
        allC |= set(P[c])
    A, B = split_days(allC)
    cache = {}

    def model(coin, r, kind, other):
        key = (coin, r, kind, other)
        if key not in cache:
            rows = build_rows(P[coin], S[coin],
                              R.get(coin) if kind >= 2 else None, coin, r, kind)
            days = A if other == "A" else B
            tr = [(x, y) for C, x, y in rows if day_of(C) in days]
            cache[key] = ols(tr) if len(tr) >= 50 else None
        return cache[key]

    out, drop = [], {}
    for tk, e in sorted(entries.items()):
        coin = SERIES_COIN.get(tk.split("-")[0])
        if coin is None or coin not in P:
            drop["series with no index extracted"] = drop.get("series with no index extracted", 0) + 1
            continue
        led = ledger.get(tk)
        if led is None:
            drop["not in Kalshi ledger (unsettled)"] = drop.get("not in Kalshi ledger (unsettled)", 0) + 1
            continue
        C, _ = close_of(e)
        arr = P[coin].get(C)
        if arr is None:
            drop["no tape for that close"] = drop.get("no tape for that close", 0) + 1
            continue
        rb = rebuild(e, arr)
        if isinstance(rb, str):
            drop[rb] = drop.get(rb, 0) + 1
            continue
        sig = e["sig"]
        want = e["want"]
        fair_log = float(sig["fair"])
        conf0 = conf_of_side(fair_log, want)
        edge0 = float(sig.get("edge_c") or 0.0) / 100.0
        rec = {"ticker": tk, "coin": coin, "want": want, "r": rb["r"],
               "fair_log": fair_log, "fair_rebuilt": rb["fair0"],
               "price": sig.get("price"), "dollars": led["dollars"],
               "loser": led["dollars"] < 0, "day": day_of(C), "C": C,
               "gates": e["gates"], "passed_old": gate(conf0, edge0, e["gates"]),
               "index_age_s": sig.get("index_age_s"), "edge0": edge0,
               "conf0": conf0}
        other = "B" if day_of(C) in A else "A"
        for kind in (1, 2, 3):
            if kind >= 2 and coin not in R:
                rec["M%d" % kind] = None
                continue
            w = model(coin, rb["r"], kind, other)
            x = features(arr, R.get(coin).get(C) if kind >= 2 and R.get(coin) else None,
                         rb["i0"], kind)
            if w is None or x is None:
                rec["M%d" % kind] = None
                continue
            yh = dot(w, x)
            mu1 = rb["mu0"] + rb["r"] * yh * rb["spot"] / 1e4 / N_AVG
            # shift the LOGGED z by the model's move, so the rebuild's small
            # disagreements with the bot do not leak into the answer
            zl = _z_of(fair_log)
            z1 = zl + (mu1 - rb["mu0"]) / rb["sd"]
            f1 = phi(z1)
            conf1 = conf_of_side(f1, want)
            edge1 = edge0 + (conf1 - conf0)
            rec["M%d" % kind] = {"yhat_bps": yh, "fair1": f1, "conf1": conf1,
                                 "dz": z1 - zl,
                                 "refused": not gate(conf1, edge1, e["gates"])}
        # ML, what a live replica could have used AT THAT MOMENT: the replica
        # for the second after spot exists only if the bot's newest print was
        # already more than a second old (index_age_s >= 1.01); otherwise the
        # newest replica second IS the spot second (M2).
        age = rec["index_age_s"]
        pick = "M3" if (age is not None and float(age) >= 1.01) else "M2"
        rec["ML"] = rec.get(pick)
        rec["ML_from"] = pick if rec.get(pick) else None
        out.append(rec)
    return out, drop


def _z_of(p):
    """Inverse of phi by bisection; saturates at +/-8."""
    p = min(max(p, 1e-15), 1 - 1e-15)
    lo, hi = -8.0, 8.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if phi(mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# self-test: planted worlds
# ---------------------------------------------------------------------------
def _world(n_closes, mode, seed):
    """Synthetic P, S, R. mode: 'lead' (published lags the books by 1 s),
    'bounce' (prints = efficient price + iid bounce), 'null' (books carry no
    information beyond the print)."""
    rnd = random.Random(seed)
    P, S, R = {}, {}, {}
    C0 = 1790000100 - (1790000100 % 900) + 900
    for n in range(n_closes):
        C = C0 + 900 * n
        X = [100000.0]
        for _ in range(W + 1):
            X.append(X[-1] * (1.0 + rnd.gauss(0, 1e-4)))
        # X[j] is the efficient price at second C-W-1+j
        pa, wm, md, cb = [], [], [], []
        for i in range(W):
            j = i + 1
            if mode == "lead":
                p = X[j - 1] * (1 + rnd.gauss(0, 5e-6))
                b = X[j]
            elif mode == "bounce":
                p = X[j] * (1 + rnd.gauss(0, 2e-4))
                b = X[j - 1] * (1 + rnd.gauss(0, 3e-4))
            else:
                # the books are a stale, noisy copy of the print: they know
                # nothing the print has not already said, at either second
                p = X[j]
                b = X[j - 1] * (1 + rnd.gauss(0, 1e-4))
            pa.append(p)
            wm.append(b * (1 + rnd.gauss(0, 2e-6)))
            md.append(b * (1 + rnd.gauss(0, 2e-6)))
            cb.append(b * (1 + rnd.gauss(0, 2e-6)))
        arr = array.array("d", pa)
        P[C] = arr
        S[C] = sum(pa[W - N_AVG:]) / float(N_AVG)
        R[C] = tuple(array.array("d", v) for v in (wm, md, cb))
    return P, S, R


def selftest(verbose=True):
    ok = [True]

    def ck(cond, msg):
        if verbose or not cond:
            print("  [%s] %s" % ("ok" if cond else "FAIL", msg))
        if not cond:
            ok[0] = False

    print("constpredict self-test")
    # 1. parser on the collector's exact escaped format
    C = 1790251200
    line = ('{"type":"cfbenchmarks_value","sid":2,"seq":1,"msg":{"index_id":'
            '"BRTI","received_at":%d,"data":"{\\"type\\":\\"value\\",\\"time'
            '\\":%d,\\"id\\":\\"BRTI\\",\\"value\\":\\"83467.12\\"}",'
            '"avg_60s_data":{"value":"83460.50000000","window_size":60,'
            '"window_start_ts_ms":%d,"window_end_ts_exclusive":%d}}}'
            % (C * 1000 + 30, C * 1000, (C - 60) * 1000, C * 1000))
    r = parse_index_line(line, IDS)
    ck(r is not None and r[0] == "BRTI" and r[1] == C and r[2] == 83467.12
       and r[3] == 83460.5, "index line parsed: id, second, value, avg at close")
    line2 = line.replace("%d," % (C * 1000), "%d," % ((C - 10) * 1000), 1)
    line2 = line2.replace('\\"time\\":%d' % (C * 1000), '\\"time\\":%d' % ((C - 10) * 1000))
    r2 = parse_index_line(line2, IDS)
    ck(r2 is not None and r2[1] == C - 10 and r2[3] is None
       and slot(C - 10) == (C, W - 10), "second inside the window lands in the right slot, no avg")
    line3 = line.replace('\\"time\\":%d' % (C * 1000), '\\"time\\":%d' % ((C - 400) * 1000))
    ck(parse_index_line(line3, IDS) is None, "second outside the last %d s is skipped" % W)
    ck(parse_index_line(line.replace('"BRTI"', '"TONUSD_RTI"', 1), IDS) is None,
       "an index not asked for is skipped")

    # 2. target arithmetic: settle rebuilt from locked + remaining
    arr = array.array("d", [100.0 + 0.01 * i for i in range(W)])
    st = twap(arr)
    t = target(arr, st, W - 1 - 20)
    rem = sum(arr[W - 20:]) / 20.0
    ck(t is not None and abs(t[0] - (rem - arr[W - 21]) / arr[W - 21] * 1e4) < 1e-6,
       "target = mean of remaining prints minus spot (bps)")

    # 3. planted worlds
    def run(mode, seed):
        P, S, R = _world(700, mode, seed)
        # put half the closes on later days: _world spaces them 900 s apart,
        # 700 closes = 7.3 days, so split_days has days on both sides
        res, pool, ws, _ = study({"BTC": P}, {"BTC": S}, {"BTC": R},
                                 rs=(30, 10), coins=["BTC"], say=None)
        return res

    lead = run("lead", 1)
    s = lead.get(("BTC", 10, "M2"))
    ck(s is not None and s["red"] > 0.10 and s["t"] > 3,
       "LEAD world: books-at-same-second model cuts error at r=10 "
       "(%.0f%%, t=%.1f)" % (100 * s["red"], s["t"]) if s else "LEAD world: no result")
    s1 = lead.get(("BTC", 10, "M1"))
    ck(s1 is not None and s["red"] > s1["red"] + 0.05,
       "LEAD world: the books add over own-prints (%.0f%% vs %.0f%%)"
       % (100 * s["red"], 100 * s1["red"]) if s1 else "LEAD world: M1 missing")

    bounce = run("bounce", 2)
    s = bounce.get(("BTC", 10, "M1"))
    ck(s is not None and s["red"] > 0.10 and s["t"] > 3,
       "BOUNCE world: own-prints model finds the mean reversion "
       "(%.0f%%, t=%.1f)" % (100 * s["red"], s["t"]) if s else "BOUNCE world: no result")
    ck(s is not None and s["w"][0] < 0, "BOUNCE world: the 1 s move carries a NEGATIVE weight")

    for seed in (3, 4):
        null = run("null", seed)
        worst = max((v["t"] for v in null.values()), default=0)
        best = max((v["red"] for v in null.values()), default=0)
        which = max(null, key=lambda k: null[k]["red"]) if null else None
        ck(len(null) == 6 and worst < 3.0 and best < 0.03,
           "NULL world %d: nothing found (best cut %.1f%% at %s, largest t %.1f, %d cells)"
           % (seed, 100 * best, which, worst, len(null)))

    # 4. the live rebuild and gate
    arr = array.array("d", [100.0] * W)
    Cx = 1790251200
    e = {"sig": {"spot": 100.0, "sigma": 0.02, "strike": 99.95, "digits": 2,
                 "fair": 0.0, "tau": 20, "t": "2026-09-25T00:00:00Z"},
         "order": {"t_ms_decide": (Cx - 21) * 1000 + 300}, "want": "yes"}
    rb = rebuild(e, arr)
    sd = 0.02 * math.sqrt(var_factor(20, [1.0]))
    ck(isinstance(rb, dict) and rb["r"] == 20 and rb["C"] == Cx
       and abs(rb["fair0"] - phi((100.0 - (99.95 - 0.005)) / sd)) < 1e-12,
       "rebuild: r, close and fair match pinrun's formula")
    ck(abs(_z_of(phi(2.5)) - 2.5) < 1e-9, "inverse normal round-trips")
    ck(not gate(0.990, 0.01, {"pin": 0.995, "edge_floor": 0.003})
       and gate(0.996, 0.004, {"pin": 0.995, "edge_floor": 0.003})
       and not gate(0.999, 0.002, {"pin": 0.995, "edge_floor": 0.003}),
       "gate refuses below pin or below edge floor, passes otherwise")
    # 5. the shuffle control: a shift aimed at the losers must beat luck; the
    #    same shifts dealt at random must not
    g = {"pin": 0.995, "edge_floor": 0.003}
    sc = []
    for i in range(100):
        los = i < 5
        sc.append({"fair_log": 0.998, "want": "yes", "conf0": 0.998,
                   "edge0": 0.01, "gates": g, "loser": los,
                   "dollars": -50.0 if los else 1.0,
                   "T": {"dz": -3.0 if los else 0.0},
                   "N": {"dz": -3.0 if i in (7, 30, 51, 77, 90) else 0.0}})
    aimed = shuffle_control(sc, "T", 5, draws=400)
    blind = shuffle_control(sc, "N", 0 + sum(1 for x in sc if x["loser"] and refused_with(x, x["N"]["dz"])), draws=400)
    ck(aimed[3] is not None and aimed[3] < 0.01,
       "shuffle control: shifts aimed at the 5 losers beat luck (p=%.3f)" % aimed[3])
    ck(abs(aimed[0] - 0.25) < 0.15 and abs(aimed[1] - 4.75) < 0.3,
       "shuffle control: random deal refuses ~0.25 losers / ~4.75 winners (%.2f / %.2f)"
       % (aimed[0], aimed[1]))
    ck(blind[3] is None or blind[3] > 0.2,
       "shuffle control: shifts that miss the losers are not called skill")
    print("self-test %s" % ("PASSED" if ok[0] else "FAILED"))
    return ok[0]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def cache_path(scratch):
    return os.path.join(scratch, "cp_cache.pkl.gz")


def do_extract(args, say=print):
    os.makedirs(args.scratch, exist_ok=True)
    t0 = time.time()
    ifiles = sorted(glob.glob(os.path.join(args.data, "cfbenchmarks_value", "*.jsonl.gz")))
    rfiles = sorted(glob.glob(os.path.join(args.feed, "index_replica", "*.jsonl.gz")))
    say("extracting index from %d hour files" % len(ifiles))
    P, S, ist = extract_index(ifiles, say=say)
    say("  index done in %.0fs; closes per coin: %s; salvaged files %s"
        % (time.time() - t0, {c: len(v) for c, v in P.items()},
           ist.get("salvaged_files", 0)))
    t1 = time.time()
    say("extracting replica from %d hour files" % len(rfiles))
    R, rst = extract_replica(rfiles, say=say)
    say("  replica done in %.0fs; closes per coin: %s; salvaged %s"
        % (time.time() - t1, {c: len(v) for c, v in R.items()},
           rst.get("salvaged_files", 0)))
    with gzip.open(cache_path(args.scratch), "wb") as f:
        pickle.dump({"P": P, "S": S, "R": R,
                     "files": (len(ifiles), len(rfiles)),
                     "written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, f)
    say("cache written: %s (%.1f MB)" % (cache_path(args.scratch),
                                         os.path.getsize(cache_path(args.scratch)) / 1e6))


def et(epoch):
    """ET clock string for the operator (EDT until 2026-11-01)."""
    off = 4 * 3600 if epoch < calendar.timegm((2026, 11, 1, 6, 0, 0)) else 5 * 3600
    return time.strftime("%m-%d %H:%M", time.gmtime(epoch - off)) + " ET"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--feed", default=FEED)
    ap.add_argument("--scratch", default=SCRATCH)
    ap.add_argument("--results", default=RESULTS)
    args = ap.parse_args()
    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1":
        if not selftest(verbose=False):
            print("self-test FAILED -- refusing to touch real data")
            sys.exit(1)
    if args.extract or not os.path.exists(cache_path(args.scratch)):
        do_extract(args)
        if args.extract:
            return
    with gzip.open(cache_path(args.scratch), "rb") as f:
        cache = pickle.load(f)
    P, S, R = cache["P"], cache["S"], cache["R"]
    lines = []
    say = lambda s="": (print(s), lines.append(s))   # noqa: E731

    # --- data health: Kalshi's avg vs our own 60-print mean
    say("## Data health")
    for c in COINS:
        n = len(P.get(c, {}))
        have = sum(1 for C in P[c] if C in S[c])
        full = [C for C, a in P[c].items() if twap(a) is not None]
        agree = sum(1 for C in full if C in S[c]
                    and abs(twap(P[c][C]) - S[c][C]) / S[c][C] * 1e4 < 0.01)
        both = sum(1 for C in full if C in S[c])
        say("- %s: %d closes seen, %d with Kalshi's close average, %d with all 60 "
            "prints held; our 60-print mean matches Kalshi's to 0.01 bps on %d of %d"
            % (c, n, have, len(full), agree, both))

    res, pool, ws, span = study(P, S, R)
    say("")
    say("Train days %s..%s, test days %s..%s (UTC days)" % span)
    say("")
    say("## Per coin, test half (error of the settlement forecast, bps of price)")
    say("| coin | prints left | model | closes | flat error (rms) | model error (rms) | cut in squared error | t | median miss flat -> model | wrong side flat -> model |")
    say("|---|---|---|---|---|---|---|---|---|---|")
    for c in COINS:
        for r in RS:
            for m in MODELS:
                s = res.get((c, r, m))
                if s is None:
                    continue
                n, w0, w1 = ws.get((c, r, m), (0, 0, 0))
                say("| %s | %d | %s | %d | %.3f | %.3f | %+.1f%% | %.1f | %.3f -> %.3f | %d -> %d of %d |"
                    % (c, r, m, s["n"], s["rmse0"], s["rmse1"], 100 * s["red"],
                       s["t"], s["mae0"], s["mae1"], w0, w1, n))
    say("")
    looks = len(res)
    say("Multiple looks: %d cells; a two-sided 5%% bar across all of them is |t| > %.1f"
        % (looks, _bonf_t(looks)))
    say("")
    say("## Pooled over coins (a close is one row; coins summed inside it)")
    say("| prints left | model | closes | cut in squared error | t |")
    say("|---|---|---|---|---|")
    for r in RS:
        for m in MODELS:
            s = pool.get((r, m))
            if s:
                say("| %d | %s | %d | %+.1f%% | %.1f |" % (r, m, s["n"], 100 * s["red"], s["t"]))
    say("")
    say("## Fitted weights, BTC, test-half models (bps of the remaining-print mean per bps of feature)")
    names = ["move1s", "move3s", "move10s", "move30s", "wmid-spot", "median-spot",
             "coinbase-spot", "wmid 3s move", "wmid(+1s)-spot", "median(+1s)-spot"]
    for r in RS:
        for m in MODELS:
            s = res.get(("BTC", r, m))
            if s:
                say("- r=%d %s: %s" % (r, m, ", ".join("%s %+.3f" % (a, b)
                                                        for a, b in zip(names, s["w"]))))

    # --- live entries
    say("")
    say("## Live entries")
    import pinday
    paths = glob.glob(os.path.join(args.results, "pinrun-live-*.jsonl"))
    entries, cnt = load_live(paths)
    led, why = pinday.load_ledger(os.path.join(args.results, "kalshi_ledger.json"))
    if led is None:
        say("LEDGER UNREADABLE: %s -- live part not run" % why)
        _write(args, lines)
        return
    lm, skipped = pinday.ledger_markets(led["rows"])
    say("- %d live logs, %d filled orders, %d markets with a first filled entry, "
        "%d orders with no preceding signal; ledger %d markets (written %s), %d rows skipped"
        % (cnt["files"], cnt["orders_filled"], len(entries), cnt["no_signal"],
           len(lm), led.get("written"), skipped))
    recs, drop = counterfactual(entries, P, S, R, lm)
    say("- rebuilt %d entries; dropped: %s" % (len(recs), drop))
    good = [x for x in recs if abs(x["fair_rebuilt"] - x["fair_log"]) < 0.002
            or (x["fair_log"] > 0.9999 and x["fair_rebuilt"] > 0.999)
            or (x["fair_log"] < 0.0001 and x["fair_rebuilt"] < 0.001)]
    say("- fair rebuilt from the tape within 0.2c of the logged fair: %d of %d"
        % (len(good), len(recs)))
    passed = [x for x in good if x["passed_old"]]
    say("- of those, the logged fair passes the run's own pin/edge gates as rebuilt here: %d"
        % len(passed))
    losers = [x for x in passed if x["loser"]]
    winners = [x for x in passed if not x["loser"]]
    say("- population: %d markets, %d losers ($%.2f), %d winners ($%.2f)"
        % (len(passed), len(losers), sum(x["dollars"] for x in losers),
           len(winners), sum(x["dollars"] for x in winners)))
    say("")
    say("| model | markets it could score | losers refused | loser $ avoided | winners refused | winner $ forgone | net $ | same-size random shifts: losers / winners / net $ | chance of >= this many losers by luck |")
    say("|---|---|---|---|---|---|---|---|---|")
    for m in MODELS + ("ML",):
        sc = [x for x in passed if x.get(m)]
        lr = [x for x in sc if x["loser"] and x[m]["refused"]]
        wr = [x for x in sc if not x["loser"] and x[m]["refused"]]
        la = -sum(x["dollars"] for x in lr)
        wf = sum(x["dollars"] for x in wr)
        ctl = shuffle_control(sc, m, len(lr))
        say("| %s | %d (%d losers) | %d | $%.2f | %d | $%.2f | $%+.2f | %.2f / %.1f / $%+.2f | %s |"
            % (m, len(sc), sum(1 for x in sc if x["loser"]), len(lr), la,
               len(wr), wf, la - wf, ctl[0], ctl[1], ctl[2],
               ("%.2f" % ctl[3]) if ctl[3] is not None else "-"))
    say("")
    say("ML = what a live replica could have used at that moment: M3 when the "
        "bot's newest print was already >= 1.01 s old at the signal, else M2. "
        "Split: %s" % {k: sum(1 for x in passed if x.get("ML_from") == k)
                       for k in ("M2", "M3")})
    say("")
    say("### Every loser, what each projection said (conf = model's chance our side wins)")
    say("| market | ET close | side | prints left | paid | logged conf | M1 conf | M2 conf | M3 conf | ML conf | newest print age s | ledger $ |")
    say("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for x in sorted(losers, key=lambda x: x["ticker"]):
        cells = []
        for m in MODELS + ("ML",):
            v = x.get(m)
            cells.append("-" if not v else ("%.4f%s" % (v["conf1"], " REFUSED" if v["refused"] else "")))
        say("| %s | %s | %s | %d | %.3f | %.4f | %s | %s | %s | %s | %s | %.2f |"
            % (x["ticker"], et(x["C"]), x["want"], x["r"], float(x["price"] or 0),
               conf_of_side(x["fair_log"], x["want"]), cells[0], cells[1], cells[2],
               cells[3], x.get("index_age_s"), x["dollars"]))
    # confidence shift, losers vs winners
    say("")
    say("### Average change in confidence, losers vs winners (cents of probability)")
    for m in MODELS + ("ML",):
        L = [x[m]["conf1"] - conf_of_side(x["fair_log"], x["want"]) for x in losers if x.get(m)]
        Wn = [x[m]["conf1"] - conf_of_side(x["fair_log"], x["want"]) for x in winners if x.get(m)]
        if L and Wn:
            say("- %s: losers %+.3fc (n=%d), winners %+.3fc (n=%d)"
                % (m, 100 * sum(L) / len(L), len(L), 100 * sum(Wn) / len(Wn), len(Wn)))
    _write(args, lines, recs)


def refused_with(x, dz):
    """Would entry x be refused if its logged z moved by dz?"""
    c1 = conf_of_side(phi(_z_of(x["fair_log"]) + dz), x["want"])
    return not gate(c1, x["edge0"] + (c1 - x["conf0"]), x["gates"])


def shuffle_control(sc, m, observed_losers, draws=2000, seed=7):
    """Deal the model's own shifts out at random across the same entries.
    (mean losers refused, mean winners refused, mean net $, P(losers refused
    >= observed)). A model with no skill refuses winners at the same rate as
    this; the question is whether it picks out the losers better."""
    if not sc:
        return (0.0, 0.0, 0.0, None)
    rnd = random.Random(seed)
    dzs = [x[m]["dz"] for x in sc]
    zl = [_z_of(x["fair_log"]) for x in sc]
    tl = tw = tn = 0.0
    ge = 0
    for _ in range(draws):
        rnd.shuffle(dzs)
        nl = nw = 0
        net = 0.0
        for x, z, dz in zip(sc, zl, dzs):
            c1 = conf_of_side(phi(z + dz), x["want"])
            if not gate(c1, x["edge0"] + (c1 - x["conf0"]), x["gates"]):
                if x["loser"]:
                    nl += 1
                    net -= x["dollars"]
                else:
                    nw += 1
                    net -= x["dollars"]
        tl += nl
        tw += nw
        tn += net
        ge += nl >= observed_losers
    return (tl / draws, tw / draws, tn / draws,
            ge / float(draws) if observed_losers > 0 else None)


def _bonf_t(k, alpha=0.05):
    """Two-sided normal critical value at alpha/k (bisection)."""
    p = 1 - alpha / (2.0 * k)
    return _z_of(p)


def _write(args, lines, recs=None):
    os.makedirs(args.scratch, exist_ok=True)
    out = os.path.join(args.scratch, "cp_tables.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    if recs is not None:
        with open(os.path.join(args.scratch, "cp_live.json"), "w", encoding="utf-8") as f:
            json.dump(recs, f)
    print("tables: %s" % out)


if __name__ == "__main__":
    main()
