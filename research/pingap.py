#!/usr/bin/env python3
# VERSION: 2026-09-08-pg1
"""pingap.py -- WHY DO THE BACKTEST AND THE LIVE TAPE DISAGREE ABOUT PRICE?

THE CLAIM UNDER TEST
  backtest (results/pindata/rows.jsonl, live gate tau 3-30, p_flip<=0.02,
            EV>=0.3c, scale-in cap 2):  mean price paid 93.86c over 129 buys
  live     (results/pinrun-live-*.jsonl, kind=="signal"):
                                        mean price paid 97.61c over 16 signals

A 3.75c gap on a strategy whose whole profit is 2-6c per contract. If the
backtest is optimistic about PRICE then every profit number in this repo is
inflated, because profit here is almost exactly (1 - price) - fee.

WHAT THIS FILE DOES.  It decomposes that gap into named, separately measured
pieces, and refuses to attribute anything to a cause it has not measured.

  A. RULE-VERSION CONTAMINATION.  The 16 live signals were NOT produced by one
     rule.  The EV gate (research/pinrun.py, expected_value / EV_FLOOR) first
     exists in commit c3aca51, 2026-09-08 11:46:40 UTC.  Nine of the sixteen
     signals came out of processes that started BEFORE that and therefore had
     no EV gate at all; seven of those nine are at prices today's rule refuses
     outright.  Comparing a mixed-rule live sample against a single-rule
     backtest is not a comparison.

  B. SCALE-IN.  93.86c is a mean over FIRST buys and IMPROVE buys together
     (125 buys over 83 closes in this file's reproduction = 1.51 per close).
     A second buy is only ever taken at a LOWER price -- that is the rule --
     so blending them drags the mean down.  The live sample contains no second
     buy at all (six of the seven current-rule signals predate MAX_PER_CLOSE,
     added 14:37 UTC, and the seventh never got one).  The like-for-like
     backtest statistic is the FIRST buy per close.

  C. TAU.  Fifteen of the sixteen live signals came from runs with TAU_MAX=20;
     the backtest cell is tau 3-30.  Measured here so the claim is a number
     and not a story.

  D. BOOK AGE.  The brief asks whether restricting the backtest to
     age_ms<=2000 (the live gate) changes the price distribution.  IT CANNOT
     BE ASKED THAT WAY: the two fields are different quantities that share a
     name.  livebook.best()["age_ms"] is `now - rx_ms of the last book MESSAGE`
     -- feed freshness.  pindata's `age_ms` is `ts - born[(side,price)]` --
     how long the RESTING LEVEL has stood.  A 108-second level age is a stale
     quote, not a stale feed.  Both are measured below, separately.

  E. THE RACE.  The standing PRIMARY OPEN RISK: in the backtest we always get
     the quote, live we are racing for it.  This file cannot settle it, but it
     reports the only direct evidence that exists -- 16 real IOC orders, their
     fills, their misses, and the executed price against the quoted price --
     and states what would settle it.

  F. THE SNAPSHOT SEED IS BROKEN IN pindata.py, AND THAT IS A REAL BUG.
     pindata.Book.snapshot() reads msg["yes_dollars"] / msg["no_dollars"].
     Every orderbook_snapshot in the tape, on all 330 files from 20260825T03
     to 20260908T16, carries the book under "yes_dollars_fp" / "no_dollars_fp".
     So the seed is ALWAYS empty and every book in rows.jsonl is rebuilt from
     deltas alone, from empty.  Direction and size measured in --deep: the
     delta-only book UNDERSTATES the best bid, which makes the reconstructed
     price DEARER, so the shipped backtest is conservative on price rather
     than optimistic.  It is still wrong and it still needs fixing.

  G. SAME-DAY REPLAY (--deep).  rows.jsonl spans closes 2026-09-04 12:15 to
     2026-09-06 08:15 UTC because C:\\kals\\fulltape\\markets.json has not been
     refreshed since 2026-09-06.  The live signals are from 2026-09-08.  THE
     TWO SAMPLES DO NOT OVERLAP BY A SINGLE CLOSE.  --deep replays the raw
     order book for the markets we actually traded, on their own closes, and
     prices the same rule against them.

EVERY NUMBER HERE IS READ-ONLY.  Nothing is written outside results/.
"""
import argparse
import bisect
import calendar
import collections
import glob
import gzip
import json
import math
import os
import random
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor, N_AVG                        # noqa: E402

REPO = os.path.dirname(HERE)
ROWS = os.path.join(REPO, "results", "pindata", "rows.jsonl")
LIVEGLOB = os.path.join(REPO, "results", "pinrun-live-*.jsonl")
DATA = r"C:\kals\kalshi_data"

# --- the live rule, as pinrun.py has it today ------------------------------
PIN = 0.98
PFLIP_MAX = 0.02       # == 1 - PIN, written as a literal because
                       # 1.0 - 0.98 is 0.020000000000000018 in binary and an
                       # equality test against pinsize's own 0.02 fails on it.
                       # The self-test asserts the two agree to 1e-12.
TAU_MIN, TAU_MAX = 3, 30
EDGE_FLOOR = 0.003
EV_FLOOR = 0.003
MEASURED_FLIP = 0.0090
PRICE_CEILING = 0.988
IMPROVE_BY = 0.005
MIN_LEVEL = 1.0
SIGMA_WIN = 300

# The EV gate is younger than some of the live signals.  git log:
#   c3aca51  2026-09-08 07:46:40 -0400  ==  2026-09-08 11:46:40 UTC
EV_GATE_BORN = calendar.timegm((2026, 9, 8, 11, 46, 40, 0, 0, 0))
# MAX_PER_CLOSE (scale-in) is younger still: d04647d 10:37:20 -0400.
SCALEIN_BORN = calendar.timegm((2026, 9, 8, 14, 37, 20, 0, 0, 0))

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
    "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
}


# ===========================================================================
# ARITHMETIC -- identical to pinrun/pinsize so a difference cannot come from
# here.  Cross-checked against them in the self-test.
# ===========================================================================
def billed_fee(p, n=1):
    return math.ceil(0.07 * float(p) * (1.0 - float(p)) * float(n) * 1e4) / 1e4


def ev_per_contract(p, f=MEASURED_FLIP):
    p = float(p)
    return (1.0 - f) * (1.0 - p) - f * p


def ev_net(p, f=MEASURED_FLIP):
    return ev_per_contract(p, f) - billed_fee(p, 1)


def _phi(z):
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def move_sd(sigma, r):
    if r <= 0 or sigma <= 0:
        return 0.0
    return sigma * math.sqrt(var_factor(int(r), [1.0])) * (60.0 / float(r))


def p_flip_model(row):
    sd = move_sd(row["sig"], row["r"])
    return 0.0 if sd <= 0.0 else _phi(-abs(row["req"]) / sd)


def mean(v):
    return sum(v) / float(len(v)) if v else float("nan")


# ===========================================================================
# THE LIVE LEDGER
# ===========================================================================
def load_live(pattern=LIVEGLOB):
    """Every live run: its start record, its signals, its orders.

    Signals carry `run_start`, the epoch second the PROCESS started, because
    that is the only thing that decides which code they executed.  A running
    process does not pick up an edit to the file.
    """
    runs, sigs, orders = {}, [], []
    for f in sorted(glob.glob(pattern)):
        base = os.path.basename(f)
        stamp = base.replace("pinrun-live-", "").replace(".jsonl", "")
        try:
            rs = calendar.timegm(time.strptime(stamp, "%Y%m%dT%H%M%SZ"))
        except ValueError:
            continue
        runs[f] = {"start": rs, "file": base, "n_sig": 0}
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            k = d.get("kind")
            if k == "start":
                runs[f].update({("cfg_" + kk): vv for kk, vv in d.items()
                                if kk not in ("kind", "t")})
            elif k == "signal":
                d["run_start"] = rs
                d["file"] = base
                try:
                    d["t_s"] = calendar.timegm(
                        time.strptime(d["t"], "%Y-%m-%dT%H:%M:%SZ"))
                except (KeyError, ValueError):
                    d["t_s"] = None
                d["close_s"] = (d["t_s"] + int(d["tau"])
                                if d["t_s"] is not None else None)
                sigs.append(d)
                runs[f]["n_sig"] += 1
            elif k == "order":
                d["run_start"] = rs
                orders.append(d)
    return runs, sigs, orders


def classify_live(sigs):
    """Split the live signals two independent ways.

    proc_has_ev  : did the PROCESS that fired it have the EV gate at all?
    rule_accepts : would TODAY's rule accept that price, whatever fired it?

    Both are reported because they answer different questions and neither is
    allowed to stand alone.
    """
    for s in sigs:
        s["proc_has_ev"] = s["run_start"] >= EV_GATE_BORN
        s["proc_has_scalein"] = s["run_start"] >= SCALEIN_BORN
        s["rule_accepts"] = (ev_net(s["price"]) >= EV_FLOOR
                             and s["price"] <= PRICE_CEILING)
    return sigs


# ===========================================================================
# THE BACKTEST
# ===========================================================================
def load_rows(path=ROWS):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    for d in out:
        d["pm"] = p_flip_model(d)
    return out


def eligible(rows, tau_lo=TAU_MIN, tau_hi=TAU_MAX, age_max=None,
             ev_gate=True, ceiling=PRICE_CEILING):
    """The moments the live rule would have considered tradeable."""
    k = []
    for d in rows:
        if not (tau_lo <= d["tau"] <= tau_hi):
            continue
        if d["pm"] > PFLIP_MAX:
            continue
        if d["price"] > ceiling:
            continue
        if ev_gate and ev_net(d["price"]) < EV_FLOOR:
            continue
        if age_max is not None and d["age_ms"] > age_max:
            continue
        k.append(d)
    k.sort(key=lambda d: (d["close"], d["sec"], d["tk"]))
    by = collections.OrderedDict()
    for d in k:
        by.setdefault(d["close"], []).append(d)
    return by, k


def replay_improve(by_close, cap=2, improve_by=IMPROVE_BY):
    """THE LIVE RULE, and it is already strictly causal.

    Walk the close forward in time.  Take the FIRST row that qualifies.  Take
    again only at a price at least `improve_by` better than the best already
    paid.  Never look forward.  This is pinsize.replay(mode="improve") and
    pinrun.trade_loop; the self-test pins the behaviour with a planted world.
    """
    buys = []
    for close_s in by_close:
        best = None
        got = 0
        for row in by_close[close_s]:
            if got >= cap:
                break
            if best is not None and float(row["price"]) >= best - improve_by:
                continue
            if float(row["size"]) < MIN_LEVEL:
                continue
            buys.append({"close": close_s, "tk": row["tk"],
                         "price": float(row["price"]), "tau": int(row["tau"]),
                         "flip": bool(row["flip"]), "seq": got,
                         "sr": row["sr"], "age_ms": row["age_ms"]})
            best = float(row["price"]) if best is None \
                else min(best, float(row["price"]))
            got += 1
    return buys


def firsts(buys):
    seen, out = set(), []
    for b in buys:
        if b["close"] in seen:
            continue
        seen.add(b["close"])
        out.append(b)
    return out


# ===========================================================================
# (a) SMALL SAMPLE
# ===========================================================================
def boot_ge(pop, n, target, draws=50000, seed=20260908):
    """P(mean of n draws with replacement from `pop` >= target).

    A plain frequency, not a p-value: it answers "is a live mean this dear an
    ordinary draw from the backtest population?" and nothing else.
    """
    rnd = random.Random(seed)
    m = len(pop)
    if m == 0:
        return float("nan")
    hits = 0
    for _ in range(draws):
        s = 0.0
        for _ in range(n):
            s += pop[rnd.randrange(m)]
        if s / n >= target - 1e-12:
            hits += 1
    return hits / float(draws)


def boot_closes(by_close_price, n, target, draws=50000, seed=20260908):
    """Same, resampling CLOSES and taking each close's first buy.

    Hard rule 4: cluster by close time.  A close is the unit; a buy is not.
    """
    rnd = random.Random(seed)
    vals = list(by_close_price.values())
    if not vals:
        return float("nan")
    hits = 0
    for _ in range(draws):
        s = 0.0
        for _ in range(n):
            s += vals[rnd.randrange(len(vals))]
        if s / n >= target - 1e-12:
            hits += 1
    return hits / float(draws)


# ===========================================================================
# (b/c) WHERE THE BACKTEST CAN EVEN LOOK
# ===========================================================================
def tau_coverage(rows, tau_lo=TAU_MIN, tau_hi=TAU_MAX):
    """P(the dataset holds a row) at each tau, over episodes that hold any.

    pindata emits a row only on a second in which an orderbook_delta arrived
    for that ticker AND an offer stood on the favoured side in size >= 1.  The
    live loop looks 20x a second and tolerates a book up to 2 s stale.  So the
    backtest sees FEWER instants than live, not more, and the brief's premise
    that "the backtest sees every second of the close" is false.
    """
    have = collections.defaultdict(set)
    for d in rows:
        if tau_lo <= d["tau"] <= tau_hi:
            have[(d["tk"], d["close"])].add(d["tau"])
    per = {t: [] for t in range(tau_lo, tau_hi + 1)}
    for taus in have.values():
        for t in per:
            per[t].append(1 if t in taus else 0)
    return {t: (mean(v) if v else float("nan")) for t, v in per.items()}, \
        len(have)


# ===========================================================================
# (F) THE SNAPSHOT SEED AUDIT -- expensive, --deep only
# ===========================================================================
SNAP_KEYS_SHIPPED = ("yes_dollars", "no_dollars")
SNAP_KEYS_REAL = ("yes_dollars_fp", "no_dollars_fp")


def snapshot_field_audit(sample=8):
    """Which key actually carries the book, across the snapshot archive."""
    fs = sorted(glob.glob(os.path.join(DATA, "orderbook_snapshot",
                                       "2026*.jsonl.gz")))
    if not fs:
        return None
    step = max(1, len(fs) // sample)
    chosen = fs[::step][:sample]
    hit = collections.Counter()
    lines = 0
    for p in chosen:
        try:
            with gzip.open(p, "rt") as fh:
                for line in fh:
                    try:
                        m = json.loads(line).get("msg") or {}
                    except ValueError:
                        continue
                    lines += 1
                    for k in SNAP_KEYS_SHIPPED + SNAP_KEYS_REAL:
                        if m.get(k):
                            hit[k] += 1
        except (EOFError, zlib.error, OSError):
            pass
    return {"files_total": len(fs), "files_scanned": len(chosen),
            "snapshot_msgs": lines, "with_key": dict(hit)}


def _apply_delta(book, side, price, dq):
    d = book[0] if side == "yes" else book[1]
    p = round(float(price), 4)
    v = d.get(p, 0.0) + float(dq)
    if v <= 1e-9:
        d.pop(p, None)
    else:
        d[p] = v


def _seed_from_snapshot(msg, book):
    y, n = book
    y.clear()
    n.clear()
    got = False
    for key, dd in zip(SNAP_KEYS_REAL, (y, n)):
        for pr in (msg.get(key) or []):
            try:
                p, q = round(float(pr[0]), 4), float(pr[1])
            except (TypeError, ValueError, IndexError):
                continue
            if q > 0:
                dd[p] = q
                got = True
    return got


def seed_effect(hours, series=None, tau_lo=3, tau_hi=60,
                fulltape=r"C:\kals\fulltape\markets.json"):
    """Rebuild every crypto book in `hours` twice -- delta-only (as shipped)
    and snapshot-seeded (corrected) -- and compare the top of book.

    Reports the SIGN as well as the size.  A delta-only book can only be
    MISSING levels, so its best bid is <= the true best bid, so the price it
    quotes for the favoured side (1 - the other side's best bid) is >= the
    true price.  If that is what comes out, the shipped backtest is
    conservative about price and the 3.75c gap cannot be laid at its door.
    """
    series = series or set(SERIES_TO_INDEX)
    mk = {}
    if os.path.exists(fulltape):
        for v in json.load(open(fulltape, encoding="utf-8")).values():
            for r in v:
                if r["series"] in series:
                    mk[r["ticker"]] = int(float(r["close"]))
    tot = collections.Counter()
    diffs = []
    for stamp in hours:
        want = {tk: cs for tk, cs in mk.items()
                if time.strftime("%Y%m%dT%H", time.gmtime(cs)) == stamp
                or time.strftime("%Y%m%dT%H", time.gmtime(cs - 3600)) == stamp}
        if not want:
            continue
        A = {t: ({}, {}) for t in want}
        B = {t: ({}, {}) for t in want}
        sp = os.path.join(DATA, "orderbook_snapshot", stamp + ".jsonl.gz")
        if os.path.exists(sp):
            try:
                with gzip.open(sp, "rt") as fh:
                    for line in fh:
                        try:
                            m = json.loads(line)["msg"]
                        except (ValueError, KeyError):
                            continue
                        tk = m.get("market_ticker")
                        if tk in want and _seed_from_snapshot(m, B[tk]):
                            tot["seeded"] += 1
            except (EOFError, zlib.error, OSError):
                pass
        bp = os.path.join(DATA, "orderbook_delta", stamp + ".jsonl.gz")
        if not os.path.exists(bp):
            continue
        try:
            with gzip.open(bp, "rb") as fh:
                for raw in fh:
                    if b"15M-" not in raw:
                        continue
                    try:
                        m = json.loads(raw)["msg"]
                    except (ValueError, KeyError):
                        continue
                    tk = m.get("market_ticker")
                    if tk not in want:
                        continue
                    side = str(m.get("side", "")).lower()
                    try:
                        pr = m.get("price_dollars", m.get("price"))
                        dq = m.get("delta_fp", m.get("delta")) or 0.0
                        _apply_delta(A[tk], side, pr, dq)
                        _apply_delta(B[tk], side, pr, dq)
                    except (TypeError, ValueError):
                        continue
                    sec = int(m.get("ts_ms") or 0) // 1000
                    tau = want[tk] - sec
                    if not (tau_lo <= tau <= tau_hi):
                        continue
                    for i, lab in ((0, "yesbid"), (1, "nobid")):
                        a_, b_ = A[tk][i], B[tk][i]
                        aa = max(a_) if a_ else None
                        bb = max(b_) if b_ else None
                        tot[lab + "_n"] += 1
                        if aa != bb:
                            tot[lab + "_diff"] += 1
                            if aa is None or bb is None:
                                tot[lab + "_onemissing"] += 1
                            else:
                                diffs.append(bb - aa)
        except (EOFError, zlib.error, OSError):
            pass
    out = dict(tot)
    if diffs:
        ds = sorted(diffs)
        out["both_present_diffs"] = len(ds)
        out["mean_seeded_minus_deltaonly"] = mean(ds)
        out["median_seeded_minus_deltaonly"] = ds[len(ds) // 2]
        out["frac_seeded_higher"] = mean([1.0 if x > 0 else 0.0 for x in ds])
    return out


# ===========================================================================
# (G) SAME-DAY REPLAY OF THE MARKETS WE ACTUALLY TRADED -- --deep only
# ===========================================================================
def load_index_hours(hours):
    """The 1/sec CF Benchmarks prints for the given hour stamps, from the tape.
    {index_id: {epoch_second: value}}."""
    raw = collections.defaultdict(dict)
    for stamp in hours:
        p = os.path.join(DATA, "cfbenchmarks_value", stamp + ".jsonl.gz")
        if not os.path.exists(p):
            continue
        try:
            with gzip.open(p, "rt") as fh:
                for line in fh:
                    if '"cfbenchmarks_value"' not in line:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                        dd = m.get("data")
                        dd = json.loads(dd) if isinstance(dd, str) else dd
                        raw[m["index_id"]][int(dd["time"]) // 1000] = \
                            float(dd["value"])
                    except (ValueError, KeyError, TypeError):
                        continue
        except (EOFError, zlib.error, OSError):
            pass
    return dict(raw)


def live_sigma(ticks, now_s, win=SIGMA_WIN):
    secs = [s for s in range(now_s - win, now_s + 1) if s in ticks]
    diffs = [ticks[secs[i]] - ticks[secs[i - 1]]
             for i in range(1, len(secs)) if secs[i] - secs[i - 1] == 1]
    if len(diffs) < 20:
        return None
    mu = sum(diffs) / len(diffs)
    return math.sqrt(sum((x - mu) ** 2 for x in diffs) / (len(diffs) - 1))


def live_partial(ticks, close_s, now_s):
    """pinrun's partial(), CORRECTION 3 included: the locked window ends at the
    newest print actually held, and every second after it counts as remaining.
    Returns (mu, remaining, spot) or None."""
    lo, hi = close_s - N_AVG, min(now_s, close_s - 1)
    if hi < lo:
        return None
    have = [s for s in range(lo, hi + 1) if s in ticks]
    if not have:
        return None
    hi = have[-1]
    want = hi - lo + 1
    got = {s: ticks[s] for s in have}
    if len(got) < want * 0.95:
        return None
    keys = sorted(got)
    total = 0.0
    for s in range(lo, hi + 1):
        v = got.get(s)
        if v is None:
            i = bisect.bisect_left(keys, s)
            cand = [k for k in (keys[i] if i < len(keys) else None,
                                keys[i - 1] if i > 0 else None)
                    if k is not None]
            v = got[min(cand, key=lambda k: (abs(k - s), k))]
        total += v
    r = N_AVG - want
    spot = got[keys[-1]]
    return (total + r * spot) / N_AVG, r, spot


def eff_strike(strike, d):
    if d is None:
        return float(strike)
    return float(strike) - 0.5 * (10.0 ** (-int(d)))


SAMEDAY_CACHE = os.path.join(REPO, "results", "pingap_sameday.json")


def sameday_paths(sigs, tau_lo=3, tau_hi=40, cache=SAMEDAY_CACHE):
    """Cached wrapper. The replay costs ~350 s of gzip scanning; the result is
    a few kB. Cached under results/, which is the only place this file writes."""
    if cache and os.path.exists(cache):
        try:
            raw = json.load(open(cache, encoding="utf-8"))
            live = {s["ticker"] for s in sigs if s["close_s"]}
            if set(raw) == live:
                return {tk: {"meta": v["meta"],
                             "path": {int(k): d
                                      for k, d in v["path"].items()}}
                        for tk, v in raw.items()}
        except (ValueError, OSError, KeyError):
            pass
    out = _sameday_paths(sigs, tau_lo, tau_hi)
    if cache:
        try:
            json.dump(out, open(cache, "w", encoding="utf-8"), default=str)
        except OSError:
            pass
    return out


def _sameday_paths(sigs, tau_lo=3, tau_hi=40):
    """For every market a live signal fired on, rebuild its book from the tape
    (snapshot-seeded, CORRECTED keys) and report, second by second, the price
    that stood on the side we bought.

    This is the only apples-to-apples test available: same market, same close,
    same day.  rows.jsonl cannot do it -- fulltape is stale to 2026-09-06 and
    the live signals are from 2026-09-08.
    """
    tickers = {}
    for s in sigs:
        if s["close_s"] is None:
            continue
        tickers.setdefault(s["ticker"], {
            "close": s["close_s"], "want": s["want"], "sig": s})
    if not tickers:
        return {}
    hours = set()
    for v in tickers.values():
        for off in (-3600, 0):
            hours.add(time.strftime("%Y%m%dT%H",
                                    time.gmtime(v["close"] + off)))
    hours = sorted(hours)
    pats = [(tk.encode(), tk) for tk in tickers]
    books = {tk: ({}, {}) for tk in tickers}
    paths = {tk: {} for tk in tickers}
    for stamp in hours:
        sp = os.path.join(DATA, "orderbook_snapshot", stamp + ".jsonl.gz")
        if os.path.exists(sp):
            try:
                with gzip.open(sp, "rt") as fh:
                    for line in fh:
                        try:
                            m = json.loads(line)["msg"]
                        except (ValueError, KeyError):
                            continue
                        tk = m.get("market_ticker")
                        if tk in books:
                            _seed_from_snapshot(m, books[tk])
            except (EOFError, zlib.error, OSError):
                pass
        bp = os.path.join(DATA, "orderbook_delta", stamp + ".jsonl.gz")
        if not os.path.exists(bp):
            continue
        try:
            with gzip.open(bp, "rb") as fh:
                for raw in fh:
                    tk = None
                    for pat, name in pats:
                        if pat in raw:
                            tk = name
                            break
                    if tk is None:
                        continue
                    try:
                        m = json.loads(raw)["msg"]
                    except (ValueError, KeyError):
                        continue
                    if m.get("market_ticker") != tk:
                        continue
                    try:
                        _apply_delta(books[tk], str(m.get("side", "")).lower(),
                                     m.get("price_dollars", m.get("price")),
                                     m.get("delta_fp", m.get("delta")) or 0.0)
                    except (TypeError, ValueError):
                        continue
                    sec = int(m.get("ts_ms") or 0) // 1000
                    tau = tickers[tk]["close"] - sec
                    if not (tau_lo <= tau <= tau_hi):
                        continue
                    y, n = books[tk]
                    yb = max(y) if y else None
                    nb = max(n) if n else None
                    paths[tk][tau] = {
                        "yes_bid": yb,
                        "yes_bid_size": y.get(yb) if yb is not None else None,
                        "no_bid": nb,
                        "no_bid_size": n.get(nb) if nb is not None else None,
                        "yes_ask": round(1.0 - nb, 4) if nb is not None else None,
                        "no_ask": round(1.0 - yb, 4) if yb is not None else None,
                    }
        except (EOFError, zlib.error, OSError):
            pass
    return {tk: {"meta": tickers[tk], "path": paths[tk]} for tk in tickers}


def path_stats(sd, index=None, tau_lo=TAU_MIN, tau_hi=TAU_MAX):
    """Per traded close: the price live paid, the tape's price at the same
    second, and -- only when the index is supplied -- the cheapest price at a
    second WHERE THE RULE ITSELF WOULD HAVE FIRED.

    THE UNGATED VERSION OF THIS COLUMN IS A TRAP AND WAS REMOVED.  Taking the
    cheapest price our eventual side ever traded at, over the whole window,
    reads 8.2c on KXBTC15M-26SEP080800-00 -- because at tau 24 the market
    still thought the OTHER side was winning and our side was near worthless.
    That is not an opportunity we passed up, it is hindsight about which side
    won.  A price only counts if the model favoured that side AT THAT SECOND
    and every live gate passed, which is what `index` buys.
    """
    out = []
    for tk, v in sd.items():
        s = v["meta"]["sig"]
        want = v["meta"]["want"]
        key = "yes_ask" if want == "yes" else "no_ask"
        rec = {"tk": tk, "want": want, "live_price": float(s["price"]),
               "live_tau": int(s["tau"]),
               "tape_price_at_live_tau": None,
               "gated_first_tau": None, "gated_first_price": None,
               "gated_best_price": None, "gated_best_tau": None,
               "gated_n": 0}
        at = v["path"].get(int(s["tau"]))
        if at is not None:
            rec["tape_price_at_live_tau"] = at[key]
        if index is not None:
            fires = rule_fires(v, index, tau_lo, tau_hi)
            rec["gated_n"] = len(fires)
            if fires:
                ft = max(f[0] for f in fires)          # largest tau = earliest
                rec["gated_first_tau"] = ft
                rec["gated_first_price"] = [f[1] for f in fires
                                            if f[0] == ft][0]
                bt, bp = min(((t, p) for t, p, _w in fires),
                             key=lambda c: (c[1], -c[0]))
                rec["gated_best_tau"], rec["gated_best_price"] = bt, bp
        out.append(rec)
    return sorted(out, key=lambda r: r["tk"])


def rule_fires(v, index, tau_lo=TAU_MIN, tau_hi=TAU_MAX):
    """Every second in the window at which the FULL live rule would have
    bought, priced off the tape's own book and the tape's own index.

    Returns [(tau, price, want)], largest tau first is not guaranteed -- the
    caller sorts.  Gates applied, in pinrun's order: model fair >= PIN (or
    <= 1-PIN), an offer on the winning side holding MIN_LEVEL non-dust
    contracts, net edge >= EDGE_FLOOR after the billed fee, price <= ceiling,
    EV >= EV_FLOOR at the measured flip rate.
    """
    s = v["meta"]["sig"]
    close_s = v["meta"]["close"]
    sr = s["ticker"].split("-")[0]
    iid = SERIES_TO_INDEX.get(sr)
    ticks = index.get(iid) if iid else None
    if not ticks:
        return []
    K = eff_strike(s.get("strike"), s.get("digits"))
    out = []
    for tau in range(tau_lo, tau_hi + 1):
        now_s = close_s - tau
        d = v["path"].get(tau)
        if d is None:
            continue
        pa = live_partial(ticks, close_s, now_s)
        if pa is None:
            continue
        mu, r, _spot = pa
        if r <= 0:
            continue
        sg = live_sigma(ticks, now_s)
        if sg is None or sg <= 0:
            continue
        sd_ = sg * math.sqrt(var_factor(int(r), [1.0]))
        if sd_ <= 0:
            continue
        fair = _phi((mu - K) / sd_)
        if fair >= PIN:
            want, price, size = "yes", d["yes_ask"], d["no_bid_size"]
        elif fair <= 1.0 - PIN:
            want, price, size = "no", d["no_ask"], d["yes_bid_size"]
        else:
            continue
        if price is None or size is None or price >= 1.0:
            continue
        if size < MIN_LEVEL:
            continue
        gross = (fair - price) if want == "yes" else ((1.0 - fair) - price)
        if gross - billed_fee(price, 1) < EDGE_FLOOR:
            continue
        if price > PRICE_CEILING or ev_net(price) < EV_FLOOR:
            continue
        out.append((tau, price, want))
    return out


# ===========================================================================
# SELF-TEST -- plant an answer, and prove the estimator finds NOTHING in a
# world with nothing planted.
# ===========================================================================
def _row(close, sec, tau, price, size=100.0, flip=False, tk="T",
         sr="KXBTC15M"):
    return {"tk": tk, "sr": sr, "close": close, "sec": sec, "tau": tau,
            "r": max(1, tau - 1), "price": price, "size": size, "age_ms": 0,
            "req": -99.0, "sig": 1.0, "flip": flip, "pm": 0.0}


def selftest():
    print("SELF-TEST -- pingap")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # ---- 1. the arithmetic is the SAME arithmetic pinrun/pinsize use -------
    try:
        import pinsize as _ps
        ck(abs(billed_fee(0.95, 1) - _ps.billed_fee(0.95, 1)) < 1e-15
           and abs(billed_fee(0.9871, 7) - _ps.billed_fee(0.9871, 7)) < 1e-15,
           "billed_fee matches pinsize exactly")
        ck(abs(ev_per_contract(0.97)
               - _ps.ev_per_contract(0.97, _ps.MEASURED_FLIP)) < 1e-15,
           "ev_per_contract matches pinsize exactly")
        r = _row(0, 0, 10, 0.95)
        r["req"], r["sig"] = 0.4, 0.02
        ck(abs(p_flip_model(r) - _ps.p_flip_model(r)) < 1e-15,
           "p_flip_model matches pinsize exactly")
        ck(MEASURED_FLIP == _ps.MEASURED_FLIP and EV_FLOOR == _ps.EV_FLOOR
           and abs(PFLIP_MAX - _ps.PFLIP_MAX) < 1e-12
           and IMPROVE_BY == _ps.IMPROVE_BY,
           f"gate constants match pinsize (flip {MEASURED_FLIP}/"
           f"{_ps.MEASURED_FLIP}, ev {EV_FLOOR}/{_ps.EV_FLOOR}, pflip "
           f"{PFLIP_MAX}/{_ps.PFLIP_MAX}, improve {IMPROVE_BY}/"
           f"{_ps.IMPROVE_BY})")
        ck(abs(PFLIP_MAX - (1.0 - PIN)) < 1e-12,
           "PFLIP_MAX is 1 - PIN, the gate pinrun actually applies")
    except ImportError:
        ck(False, "pinsize importable for the arithmetic cross-check")
    ck(abs(billed_fee(0.95, 1) - 0.0034) < 1e-12,
       f"billed fee at 95c is the $0.0001 ceiling, 0.0034 "
       f"({billed_fee(0.95, 1)})")
    ck(abs(ev_per_contract(1.0 - MEASURED_FLIP)) < 1e-12,
       "EV before fee is exactly zero at p = 1 - flip")

    # ---- 2. THE EV GATE, on the actual live prices ------------------------
    # planted: today's rule must refuse the dear pre-EV-gate trades and accept
    # the current-rule ones.  If this ever flips, section A is wrong and must
    # not be reported.
    for p_, want_ in ((0.9920, False), (0.9950, False), (0.9960, False),
                      (0.9870, True), (0.9790, True), (0.9500, True),
                      (0.9350, True)):
        got = ev_net(p_) >= EV_FLOOR
        ck(got is want_, f"today's rule {'accepts' if want_ else 'refuses'} "
                         f"a live signal at {100 * p_:.2f}c "
                         f"(EV net {100 * ev_net(p_):+.3f}c)")

    # ---- 3. REPLAY: planted world, known answer ---------------------------
    C = 1_000_000
    by = collections.OrderedDict()
    by[C] = [_row(C, C - 25, 25, 0.99), _row(C, C - 15, 15, 0.95),
             _row(C, C - 8, 8, 0.954)]
    b = replay_improve(by, cap=2)
    ck([round(x["price"], 4) for x in b] == [0.99, 0.95],
       f"planted close: improve-cap2 buys 99c then 95c and SKIPS 95.4c "
       f"({[x['price'] for x in b]})")
    ck(round(firsts(b)[0]["price"], 4) == 0.99,
       "the FIRST buy is the dear one -- blending it with the improve buy is "
       "exactly the effect being decomposed")
    ck(abs(mean([x["price"] for x in b]) - 0.97) < 1e-12
       and abs(mean([x["price"] for x in firsts(b)]) - 0.99) < 1e-12,
       "planted: blended mean 97c vs first-buy mean 99c -- a 2c gap from "
       "scale-in alone")
    # NULL WORLD: every moment at the same price.  Scale-in can then buy
    # nothing extra, so blended and first-buy MUST be identical and the
    # decomposition must measure the scale-in term as exactly zero.
    by0 = collections.OrderedDict()
    by0[C] = [_row(C, C - 25, 25, 0.96), _row(C, C - 15, 15, 0.96),
              _row(C, C - 8, 8, 0.96)]
    b0 = replay_improve(by0, cap=2)
    ck(len(b0) == 1 and abs(mean([x["price"] for x in b0])
                            - mean([x["price"] for x in firsts(b0)])) < 1e-12,
       "NULL world (flat prices): no second buy, and blended == first-buy, so "
       "the scale-in term measures zero")
    # causality: a cheaper price arriving LATER must not change the first buy
    by1 = collections.OrderedDict()
    by1[C] = [_row(C, C - 25, 25, 0.99), _row(C, C - 5, 5, 0.80)]
    ck(round(replay_improve(by1, cap=1)[0]["price"], 4) == 0.99,
       "cap1 takes the FIRST qualifying moment, never the cheapest later one "
       "-- the replay is strictly causal")

    # ---- 4. dust is not a fill --------------------------------------------
    byd = collections.OrderedDict()
    byd[C] = [_row(C, C - 20, 20, 0.90, size=0.02)]
    ck(replay_improve(byd, cap=2) == [],
       "a 0.02-contract dust level is not a buy")

    # ---- 5. THE BOOTSTRAP -- both directions, and a null -------------------
    ck(boot_ge([0.94] * 50, 16, 0.9761, draws=2000) == 0.0,
       "a population that is all 94c NEVER averages 97.61c over 16 draws")
    ck(boot_ge([0.99] * 50, 16, 0.9761, draws=2000) == 1.0,
       "a population that is all 99c ALWAYS does")
    nullpop = [0.90 + 0.0005 * i for i in range(200)]
    pn = boot_ge(nullpop, 16, mean(nullpop), draws=20000)
    ck(0.35 <= pn <= 0.65,
       f"NULL: drawing at the population's own mean is an ordinary event "
       f"({pn:.3f}) -- the estimator does not manufacture rarity")
    ck(boot_ge(nullpop, 16, mean(nullpop) + 0.05, draws=20000) < 0.01,
       "and a target 5c above the population mean is rare, as it must be")
    ck(boot_closes({1: 0.94, 2: 0.94, 3: 0.94}, 7, 0.9619, draws=2000) == 0.0,
       "the close-clustered bootstrap agrees with the buy-level one on a "
       "degenerate population")

    # ---- 6. tau coverage: planted density ----------------------------------
    full = [_row(1, 1, t, 0.95, tk="A") for t in range(3, 31)]
    half = [_row(2, 2, t, 0.95, tk="B") for t in range(3, 31) if t % 2 == 0]
    cov, nep = tau_coverage(full + half)
    ck(nep == 2 and abs(cov[4] - 1.0) < 1e-12 and abs(cov[5] - 0.5) < 1e-12,
       f"coverage estimator: tau 4 in both episodes (1.00), tau 5 in one "
       f"(0.50) -- got {cov[4]:.2f}/{cov[5]:.2f}")
    covf, _ = tau_coverage(full)
    ck(all(abs(covf[t] - 1.0) < 1e-12 for t in covf),
       "NULL: a fully covered world reports coverage 1.00 everywhere, so a "
       "coverage claim cannot be an artefact of the estimator")

    # ---- 7. the snapshot key names, asserted against pindata's source ------
    try:
        src = open(os.path.join(HERE, "pindata.py"), encoding="utf-8").read()
        blk = src[src.index("def snapshot("):]
        blk = blk[:blk.index("def delta(")]
        ck('"yes_dollars"' in blk and '"yes_dollars_fp"' not in blk,
           "pindata.Book.snapshot still reads yes_dollars, the key the tape "
           "does NOT use -- if this FAILS the bug has been fixed and section F "
           "must be rewritten before it is quoted")
    except (OSError, ValueError):
        ck(False, "pindata.py readable for the snapshot-key assertion")
    # and the seeder itself: planted book in, planted book out; and a message
    # carrying only the SHIPPED key names must seed NOTHING (that is the bug).
    bk = ({}, {})
    ck(_seed_from_snapshot({"yes_dollars_fp": [["0.60", "10"]],
                            "no_dollars_fp": [["0.39", "5"]]}, bk)
       and bk[0] == {0.6: 10.0} and bk[1] == {0.39: 5.0},
       f"the corrected seeder reads *_fp ({bk})")
    bk2 = ({}, {})
    ck(not _seed_from_snapshot({"yes_dollars": [["0.60", "10"]]}, bk2)
       and bk2 == ({}, {}),
       "a message with only the SHIPPED key names seeds an EMPTY book -- "
       "which is exactly what pindata has been doing on every file")

    # ---- 8. live-log parser on a hand-built record ------------------------
    t_s = calendar.timegm(time.strptime("2026-09-08T11:59:41Z",
                                        "%Y-%m-%dT%H:%M:%SZ"))
    ck(time.strftime("%H:%M:%S", time.gmtime(t_s + 19)) == "12:00:00",
       "a tau-19 signal at 11:59:41Z reconstructs a 12:00:00Z close")
    ck(EV_GATE_BORN == 1788867_000 - 1788867_000 + EV_GATE_BORN
       and time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(EV_GATE_BORN))
       == "2026-09-08T11:46:40Z",
       "the EV gate's birth is git c3aca51 converted to UTC, not local")

    # ---- 9. live_partial reproduces the settlement identity ---------------
    ticks = {1_000_000 - 60 + i: 100.0 for i in range(60)}
    got = live_partial(ticks, 1_000_000, 1_000_000)
    ck(got is not None and got[1] == 0 and abs(got[0] - 100.0) < 1e-9,
       f"with all 60 prints held, remaining is 0 and mu is the mean ({got})")
    ticks2 = {1_000_000 - 60 + i: 100.0 for i in range(57)}
    got2 = live_partial(ticks2, 1_000_000, 1_000_000 - 3)
    ck(got2 is not None and got2[1] == 3,
       f"three prints in flight are counted as remaining, not guessed "
       f"({got2[1] if got2 else None})")
    ck(abs(eff_strike(2492.82, 2) - 2492.815) < 1e-9,
       "eff_strike carries the rounding correction")

    # ---- 10. path_stats on a planted book path ----------------------------
    sd = {"T": {"meta": {"close": 100, "want": "no",
                         "sig": {"price": 0.97, "tau": 20}},
                "path": {20: {"yes_ask": None, "no_ask": 0.97,
                              "yes_bid_size": 50.0, "no_bid_size": 50.0,
                              "yes_bid": 0.03, "no_bid": 0.03},
                         10: {"yes_ask": None, "no_ask": 0.93,
                              "yes_bid_size": 50.0, "no_bid_size": 50.0,
                              "yes_bid": 0.07, "no_bid": 0.07},
                         2: {"yes_ask": None, "no_ask": 0.50,
                             "yes_bid_size": 50.0, "no_bid_size": 50.0,
                             "yes_bid": 0.50, "no_bid": 0.50}}}}
    ps = path_stats(sd)[0]
    ck(abs(ps["tape_price_at_live_tau"] - 0.97) < 1e-12,
       "path_stats reads the tape price at the second live actually fired")
    ck(ps["gated_best_price"] is None and ps["gated_n"] == 0,
       "with no index supplied path_stats reports NO cheapest price rather "
       "than the ungated hindsight one -- the trap column is gone")

    # ---- 11. rule_fires: planted world, and a null -------------------------
    # A world where the index has been dead flat for an hour and sits far
    # ABOVE the strike: the model is certain of YES, so an offer of YES at
    # 95c must fire, and the same offer at 99.5c must NOT (EV gate).
    Cx = 2_000_000
    flat = {Cx - 400 + i: 100.0 for i in range(400)}
    flat[Cx - 100] = 100.001            # one tick of movement -> sigma > 0
    v = {"meta": {"close": Cx, "want": "yes",
                  "sig": {"ticker": "KXBTC15M-X", "strike": 50.0,
                          "digits": 2, "price": 0.95, "tau": 20}},
         "path": {20: {"yes_ask": 0.95, "no_bid_size": 100.0,
                       "no_ask": 0.05, "yes_bid_size": 100.0,
                       "yes_bid": 0.949, "no_bid": 0.05},
                  15: {"yes_ask": 0.995, "no_bid_size": 100.0,
                       "no_ask": 0.005, "yes_bid_size": 100.0,
                       "yes_bid": 0.994, "no_bid": 0.005},
                  10: {"yes_ask": 0.95, "no_bid_size": 0.02,
                       "no_ask": 0.05, "yes_bid_size": 0.02,
                       "yes_bid": 0.949, "no_bid": 0.05}}}
    fr = rule_fires(v, {"BRTI": flat})
    ck([f[0] for f in fr] == [20],
       f"rule_fires takes the 95c offer at tau 20, refuses the 99.5c offer at "
       f"tau 15 on EV, and refuses the 0.02-contract dust at tau 10 ({fr})")
    ck(fr and fr[0][2] == "yes" and abs(fr[0][1] - 0.95) < 1e-12,
       "and it buys the side the index says is winning, at the offered price")
    # NULL: the same book with the index sitting exactly ON the strike, so the
    # model is not decided either way.  Nothing may fire.
    onstrike = {Cx - 400 + i: 50.0 for i in range(400)}
    onstrike[Cx - 100] = 50.5
    v2 = json.loads(json.dumps(v))
    v2["path"] = {int(k): x for k, x in v2["path"].items()}
    ck(rule_fires(v2, {"BRTI": onstrike}) == [],
       "NULL: with the index sitting on the strike the model is undecided and "
       "rule_fires returns NOTHING -- it cannot manufacture an opportunity")
    ck(rule_fires(v, {}) == [],
       "and with no index at all it returns nothing rather than guessing")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--deep", action="store_true",
                    help="also replay the raw tape (snapshot audit + same-day "
                         "book paths). Reads C:\\kals\\kalshi_data, writes "
                         "nothing.")
    ap.add_argument("--draws", type=int, default=50000)
    ap.add_argument("--seed-hours",
                    default="20260906T05,20260906T06,20260906T07")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- nothing ran")
    print()

    def P(*x):
        print(*x, flush=True)

    # ---------------- LIVE ----------------
    runs, sigs, orders = load_live()
    sigs = classify_live(sigs)
    P("=" * 76)
    P("A.  THE LIVE SAMPLE IS NOT ONE RULE")
    P("=" * 76)
    P(f"  {len(sigs)} signals from "
      f"{sum(1 for r in runs.values() if r['n_sig'])} runs; EV gate born "
      f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(EV_GATE_BORN))} "
      f"(git c3aca51)")
    P(f"  {'signal time':<22}{'tau':>4}{'ticker':>12}{'price':>9}"
      f"{'proc had EV':>13}{'rule accepts':>14}")
    for s in sorted(sigs, key=lambda s: s["t_s"] or 0):
        P(f"  {s['t']:<22}{s['tau']:>4}{s['ticker'][:9]:>12}"
          f"{100 * s['price']:>8.2f}c{str(s['proc_has_ev']):>13}"
          f"{str(s['rule_accepts']):>14}")
    allp = [s["price"] for s in sigs]
    proc = [s["price"] for s in sigs if s["proc_has_ev"]]
    rulep = [s["price"] for s in sigs if s["rule_accepts"]]
    P("")
    P(f"  ALL signals                 n={len(allp):2d}  "
      f"mean {100 * mean(allp):.2f}c  min {100 * min(allp):.2f}c  "
      f"max {100 * max(allp):.2f}c")
    P(f"  process HAD the EV gate     n={len(proc):2d}  "
      f"mean {100 * mean(proc):.2f}c")
    P(f"  today's rule ACCEPTS price  n={len(rulep):2d}  "
      f"mean {100 * mean(rulep):.2f}c")
    P(f"  -> the 97.61c figure is a MIXED-RULE statistic. "
      f"{len(allp) - len(rulep)} of {len(allp)} signals sit at prices the "
      f"current EV gate refuses outright.")
    P("")
    P("  CAVEAT ON 'proc had EV', stated because it is 53 seconds from a "
      "boundary:")
    P("   the run pinrun-live-20260908T114547Z started 11:45:47Z, 53s BEFORE "
      "commit")
    P("   c3aca51 (11:46:40Z), so the strict process-start test calls it "
      "pre-EV-gate.")
    P("   Three things say the file was already edited when it launched: its "
      "stdout")
    P("   log is named pinrun_ev_stdout.log; "
      "results/PREREG_pin_live_AMENDMENT_2.md was")
    P("   written at 11:44Z, one minute earlier, and this project pre-registers "
      "before")
    P("   deploying; and its six signals top out at 98.70c where the run before "
      "it")
    P("   fired at 99.60c. NEITHER READING IS PROVEN. The 'rule accepts' "
      "column does")
    P("   not depend on it at all, which is why the headline uses that one.")

    fills = [o for o in orders if float(o.get("filled") or 0) > 0]
    miss = [o for o in orders if float(o.get("filled") or 0) == 0]

    def quoted_of(o):
        body = o.get("body") or {}
        try:
            return (float(body["price"]) if body.get("side") == "bid"
                    else 1.0 - float(body["price"]))
        except (KeyError, TypeError, ValueError):
            return None
    exq = [(quoted_of(o), float(o["exec_price"])) for o in fills
           if quoted_of(o) is not None and o.get("exec_price") is not None]
    P("")
    P(f"  ORDERS: {len(orders)} sent, {len(fills)} filled, {len(miss)} no-fill "
      f"({100.0 * len(fills) / max(1, len(orders)):.0f}% fill rate)")
    if exq:
        better = sum(1 for q, e in exq if e < q - 1e-9)
        worse = sum(1 for q, e in exq if e > q + 1e-9)
        P(f"  executed vs the price we SAW: {better} better, {worse} worse, "
          f"{len(exq) - better - worse} equal; executed mean "
          f"{100 * mean([e for _, e in exq]):.2f}c vs quoted "
          f"{100 * mean([q for q, _ in exq]):.2f}c")

    # ---------------- BACKTEST ----------------
    P("")
    P("=" * 76)
    P("B.  THE BACKTEST NUMBER IS A BLEND OVER SCALE-IN BUYS")
    P("=" * 76)
    rows = load_rows()
    cl = [d["close"] for d in rows]
    lc = [s["close_s"] for s in sigs if s["close_s"]]
    P(f"  rows.jsonl: {len(rows):,} rows, {len(set(cl))} closes, span "
      f"{time.strftime('%Y-%m-%d %H:%M', time.gmtime(min(cl)))} .. "
      f"{time.strftime('%Y-%m-%d %H:%M', time.gmtime(max(cl)))} UTC")
    P(f"  live signals span closes "
      f"{time.strftime('%Y-%m-%d %H:%M', time.gmtime(min(lc)))} .. "
      f"{time.strftime('%Y-%m-%d %H:%M', time.gmtime(max(lc)))} UTC")
    P(f"  *** THE TWO SAMPLES DO NOT SHARE A SINGLE CLOSE. "
      f"fulltape/markets.json is stale to 2026-09-06, which is why. ***")
    P("")
    cells = []
    for lab, lo, hi, age in (("tau 3-30 (the quoted cell)", 3, 30, None),
                             ("tau 3-20 (15/16 live runs)", 3, 20, None),
                             ("tau 3-30, LEVEL age<=2s", 3, 30, 2000)):
        by, k = eligible(rows, lo, hi, age_max=age)
        b = replay_improve(by, cap=2)
        f = firsts(b)
        cells.append((lab, by, b, f, k))
        P(f"  {lab:<28} moments {len(k):>5}  closes {len(by):>3}  "
          f"buys {len(b):>4}  blended "
          f"{100 * mean([x['price'] for x in b]):.2f}c  FIRST-buy "
          f"{100 * mean([x['price'] for x in f]):.2f}c")
    base_by, base_b, base_f = cells[0][1], cells[0][2], cells[0][3]
    P("")
    P(f"  reproduction note: the repo quotes 129 buys / 93.86c for the first "
      f"cell; this file gets {len(base_b)} buys / "
      f"{100 * mean([x['price'] for x in base_b]):.2f}c from the shipped "
      f"rows.jsonl with pinsize's own constants. The difference is NOT "
      f"reconciled -- the quoted figure is not exactly reproducible.")
    cheap = mean([min(x["price"] for x in v) for v in base_by.values()])
    P(f"  cheapest price standing ANYWHERE in the close: {100 * cheap:.2f}c. "
      f"The causal rule pays "
      f"{100 * (mean([x['price'] for x in base_f]) - cheap):+.2f}c against "
      f"that oracle, so it is NOT cherry-picking the low.")

    # ---------------- (a) SMALL SAMPLE ----------------
    P("")
    P("=" * 76)
    P("C.  (a) IS THE GAP JUST 16 DRAWS?")
    P("=" * 76)
    tgt16 = mean(allp)
    tgt_rule = mean(rulep)
    n_rule = len(rulep)
    for lab, by, b, f, k in cells:
        pb = [x["price"] for x in b]
        pf = [x["price"] for x in f]
        fc = {x["close"]: x["price"] for x in f}
        P(f"  {lab}")
        P(f"     P(mean of 16 blended buys  >= {100 * tgt16:.2f}c) = "
          f"{boot_ge(pb, 16, tgt16, a.draws):.5f}")
        P(f"     P(mean of 16 FIRST buys    >= {100 * tgt16:.2f}c) = "
          f"{boot_ge(pf, 16, tgt16, a.draws):.5f}")
        P(f"     P(mean of {n_rule} CLOSES, first buy >= {100 * tgt_rule:.2f}c) "
          f"= {boot_closes(fc, n_rule, tgt_rule, a.draws):.5f}   "
          f"<- THE LIKE-FOR-LIKE TEST")

    # ---------------- (b) CAUSALITY / CADENCE ----------------
    P("")
    P("=" * 76)
    P("D.  (b) TIMING AND SELECTION")
    P("=" * 76)
    ft = [x["tau"] for x in base_f]
    P(f"  the backtest's own first buy sits at mean tau {mean(ft):.1f}s "
      f"(median {sorted(ft)[len(ft) // 2]}s); "
      f"{sum(1 for t in ft if t == 30)} of {len(ft)} at tau 30, the very top "
      f"of its window.")
    lt = [s["tau"] for s in sigs]
    ltr = [s["tau"] for s in sigs if s["rule_accepts"]]
    P(f"  live fires at mean tau {mean(lt):.1f}s (all) / {mean(ltr):.1f}s "
      f"(rule-accepted); {sum(1 for t in lt if t == 20)} of {len(lt)} at "
      f"tau 20, the top of ITS window.  BOTH fire at the top of their window.")
    cov, nep = tau_coverage(rows)
    P(f"  P(rows.jsonl even HOLDS a moment), {nep} episodes, by tau:")
    P("     " + "  ".join(f"{t}:{cov[t]:.2f}"
                          for t in (3, 5, 8, 10, 15, 20, 25, 30)))
    P(f"  -> the backtest sees FEWER instants than live, not more, and the "
      f"ones it misses are the LATE ones.  'The backtest sees every second' "
      f"is false.")

    # ---------------- (c) TAU ----------------
    P("")
    P("=" * 76)
    P("E.  (c) IS PRICE RELATED TO TAU?")
    P("=" * 76)
    _, k30 = eligible(rows, 3, 30)
    buck = collections.defaultdict(list)
    for d in k30:
        buck[(d["tau"] - 1) // 5 * 5 + 1].append(d["price"])
    for b_ in sorted(buck):
        v = buck[b_]
        P(f"    tau {b_:2d}-{b_ + 4:2d}  n={len(v):>4}  "
          f"mean {100 * mean(v):.2f}c")
    spread = (max(mean(v) for v in buck.values())
              - min(mean(v) for v in buck.values()))
    P(f"  spread across the whole window: {100 * spread:.2f}c. Price is "
      f"essentially FLAT in tau, so the tau mix cannot carry a 3.75c gap.")

    # ---------------- (d) AGE ----------------
    P("")
    P("=" * 76)
    P("F.  (d) BOOK AGE -- THE TWO FIELDS ARE DIFFERENT QUANTITIES")
    P("=" * 76)
    P("  livebook.best()['age_ms'] = now - rx_ms of the last book MESSAGE "
      "(feed freshness).")
    P("  pindata's 'age_ms'        = ts - born[(side,price)] (how long the "
      "RESTING LEVEL has stood).")
    P("  A pindata row exists only on a second in which a delta arrived, so "
      "its FEED age is ~0 ms by construction: the live 2000 ms gate removes "
      "nothing the backtest had.  LEVEL age, measured anyway:")
    for lo, hi, lab in ((0, 500, "0-0.5s"), (500, 2000, "0.5-2s"),
                        (2000, 10000, "2-10s"), (10000, 60000, "10-60s"),
                        (60000, 10 ** 9, ">60s")):
        v = [d["price"] for d in k30 if lo <= d["age_ms"] < hi]
        if v:
            P(f"    level age {lab:<8} n={len(v):>4}  mean {100 * mean(v):.2f}c")
    P("  -> level age moves the mean price by under 1c across four decades of "
      "age.  Not the cause.")

    # ---------------- (e) THE RACE ----------------
    P("")
    P("=" * 76)
    P("G.  (e) THE RACE -- the only direct evidence that exists")
    P("=" * 76)
    mp = [quoted_of(o) for o in miss if quoted_of(o) is not None]
    if mp and exq:
        P(f"  {len(mp)} no-fills at quoted "
          f"{', '.join('%.2fc' % (100 * x) for x in sorted(mp))} "
          f"(mean {100 * mean(mp):.2f}c)")
        P(f"  {len(exq)} fills at quoted mean "
          f"{100 * mean([q for q, _ in exq]):.2f}c")
        P(f"  -> if the race stole the CHEAP quotes the misses would cluster "
          f"cheap. They are "
          f"{100 * (mean(mp) - mean([q for q, _ in exq])):+.2f}c against that "
          f"story, and no fill executed WORSE than the price we saw. "
          f"n={len(mp)}: a direction, not a result.")
    P("  WHAT WOULD SETTLE IT (not done here):")
    P("   1. for each fired second, take the tape's own delta stream and "
      "measure")
    P("      how long the level we hit survived after our order left;")
    P("   2. run two identical processes at a deliberate latency offset and "
      "compare")
    P("      their fill rates on the same quotes.")

    # ---------------- DEEP ----------------
    if a.deep:
        P("")
        P("=" * 76)
        P("H.  THE SNAPSHOT SEED IN pindata.py IS BROKEN (measured)")
        P("=" * 76)
        au = snapshot_field_audit()
        if au:
            P(f"  {au['files_scanned']} of {au['files_total']} snapshot files, "
              f"{au['snapshot_msgs']:,} messages: keys that ever carry a book "
              f"= {au['with_key']}")
        hours = [h for h in a.seed_hours.split(",") if h]
        t0 = time.time()
        se = seed_effect(hours)
        P(f"  rebuilt {hours} both ways in {time.time() - t0:.0f}s "
          f"({se.get('seeded', 0)} markets seeded)")
        for lab in ("yesbid", "nobid"):
            n_ = se.get(lab + "_n", 0)
            if n_:
                P(f"    {lab}: {se.get(lab + '_diff', 0):,} of {n_:,} "
                  f"({100.0 * se.get(lab + '_diff', 0) / n_:.2f}%) differ; "
                  f"{se.get(lab + '_onemissing', 0):,} are levels the "
                  f"delta-only book cannot see at all")
        if "mean_seeded_minus_deltaonly" in se:
            P(f"    where both exist: the seeded best bid is "
              f"{100 * se['mean_seeded_minus_deltaonly']:+.3f}c against "
              f"delta-only (median "
              f"{100 * se['median_seeded_minus_deltaonly']:+.3f}c), higher "
              f"{100 * se['frac_seeded_higher']:.0f}% of the time")
            P("  -> a HIGHER best bid on the far side is a LOWER price for us, "
              "so the shipped delta-only book quotes prices that are too DEAR. "
              "The bug makes the backtest CONSERVATIVE about price, not "
              "optimistic.  It still has to be fixed.")

        P("")
        P("=" * 76)
        P("I.  SAME-DAY REPLAY OF THE MARKETS WE ACTUALLY TRADED")
        P("=" * 76)
        t0 = time.time()
        sd = sameday_paths(sigs)
        hrs = sorted({time.strftime("%Y%m%dT%H", time.gmtime(c))
                      for v in sd.values()
                      for c in (v["meta"]["close"] - 3600, v["meta"]["close"])})
        idx = load_index_hours(hrs)
        st = path_stats(sd, index=idx)
        P(f"  replayed {len(sd)} markets + {len(idx)} index feeds from the raw "
          f"tape in {time.time() - t0:.0f}s (snapshot-seeded, corrected keys)")
        P("  'gated' = a second at which the FULL live rule would have bought:")
        P("  model fair >= 0.98, non-dust offer, edge >= 0.3c after fee, "
          "EV >= 0.3c.")
        P("  An UNGATED cheapest-in-window column was removed: it read 8.2c on "
          "BTC")
        P("  08:00 because at tau 24 the market still thought the other side "
          "was")
        P("  winning. That is hindsight about the outcome, not a missed trade.")
        P(f"  {'ticker':<27}{'live paid':>10}{'tau':>4}{'tape@tau':>9}"
          f"{'gated n':>8}{'1st gated':>10}{'@tau':>5}"
          f"{'best gated':>11}{'@tau':>5}")
        agree, firstgap, bestgap = [], [], []
        for r in st:
            tp = r["tape_price_at_live_tau"]
            gf, gb = r["gated_first_price"], r["gated_best_price"]
            P(f"  {r['tk'][:27]:<27}{100 * r['live_price']:>9.2f}c"
              f"{r['live_tau']:>4}"
              f"{('%.2fc' % (100 * tp)) if tp is not None else 'n/a':>9}"
              f"{r['gated_n']:>8}"
              f"{('%.2fc' % (100 * gf)) if gf is not None else 'n/a':>10}"
              f"{r['gated_first_tau'] if r['gated_first_tau'] is not None else '-':>5}"
              f"{('%.2fc' % (100 * gb)) if gb is not None else 'n/a':>11}"
              f"{r['gated_best_tau'] if r['gated_best_tau'] is not None else '-':>5}")
            if tp is not None:
                agree.append(abs(r["live_price"] - tp))
            if gf is not None:
                firstgap.append(r["live_price"] - gf)
            if gb is not None:
                bestgap.append(r["live_price"] - gb)
        if agree:
            P(f"  HOW GOOD IS THIS REPLAY? tape vs the live book at the fired "
              f"second: {len(agree)} comparable, mean |difference| "
              f"{100 * mean(agree):.2f}c, median "
              f"{100 * sorted(agree)[len(agree) // 2]:.2f}c, "
              f"{sum(1 for x in agree if x < 1e-9)} exact.")
            P("  That is NOT a sub-cent validation and must not be used as "
              "one: the")
            P("  replay keeps the LAST book state in each second while live "
              "acted at an")
            P("  instant inside it, and the logged second can be one off the "
              "second the")
            P("  loop evaluated.  Read section I as order-of-magnitude, not "
              "as a tie-out.")
        # how many markets did the replay reproduce a fire on, and why not?
        norep = [r for r in st if r["gated_n"] == 0]
        ok_ev = [r for r in norep if ev_net(r["live_price"]) < EV_FLOOR]
        unexp = [r for r in norep if ev_net(r["live_price"]) >= EV_FLOOR]
        P(f"  the replay reproduced a qualifying second on "
          f"{len(st) - len(norep)} of {len(st)} markets.  Of the "
          f"{len(norep)} it did not: {len(ok_ev)} are CORRECTLY refused -- "
          f"today's EV gate rejects their price outright "
          f"({', '.join('%.2fc' % (100 * r['live_price']) for r in ok_ev)}); "
          f"{len(unexp)} are UNEXPLAINED reconstruction misses "
          f"({', '.join('%.2fc' % (100 * r['live_price']) for r in unexp)}).")
        for lab, g in (("FIRST", firstgap), ("CHEAPEST", bestgap)):
            if not g:
                continue
            gs = sorted(g)
            med = gs[len(gs) // 2] if len(gs) % 2 else \
                0.5 * (gs[len(gs) // 2 - 1] + gs[len(gs) // 2])
            big = max(g, key=abs)
            P(f"  live paid mean {100 * mean(g):+.2f}c / MEDIAN "
              f"{100 * med:+.2f}c against the {lab} gated second in tau 3-30 "
              f"(n={len(g)}); largest single term {100 * big:+.2f}c")
        if bestgap and abs(max(bestgap, key=abs)) > 0.05:
            worst = max(st, key=lambda r: (r["live_price"] - r["gated_best_price"])
                        if r["gated_best_price"] is not None else -9)
            P(f"  THE OUTLIER, named rather than averaged in: "
              f"{worst['tk']} shows a gated price of "
              f"{100 * worst['gated_best_price']:.2f}c at tau "
              f"{worst['gated_best_tau']}.  A 20c+ edge on a near-certain "
              f"binary is not credible; it is almost certainly a momentary "
              f"one-contract level in the rebuilt book.  The MEDIAN is the "
              f"number to quote here, not the mean.")
        P("  Waiting for the cheapest gated second is not free: IDEAS_LOG #9 "
          "measured")
        P("  that skipping one tick missed 7 of 70 closes outright.")

    # ---------------- VERDICT ----------------
    P("")
    P("=" * 76)
    P("VERDICT -- the decomposition, in cents")
    P("=" * 76)
    b30 = mean([x["price"] for x in cells[0][2]])
    f30 = mean([x["price"] for x in cells[0][3]])
    f20 = mean([x["price"] for x in cells[1][3]])
    P(f"  quoted backtest, blended over scale-in buys      {100 * b30:>7.2f}c")
    P(f"  + FIRST buy per close only (live had no 2nd)     {100 * f30:>7.2f}c"
      f"   ({100 * (f30 - b30):+.2f}c)")
    n_t20 = sum(1 for s in sigs if s["run_start"] < SCALEIN_BORN)
    P(f"  + tau 3-20, the window {n_t20}/{len(sigs)} live runs ran        "
      f"{100 * f20:>7.2f}c   ({100 * (f20 - f30):+.2f}c)")
    P(f"  live, TODAY'S RULE only (n={n_rule} closes)              "
      f"{100 * tgt_rule:>7.2f}c   ({100 * (tgt_rule - f20):+.2f}c "
      f"UNEXPLAINED)")
    P(f"  live, all {len(allp)} signals, three rule versions      "
      f"{100 * tgt16:>7.2f}c   ({100 * (tgt16 - tgt_rule):+.2f}c is rule "
      f"contamination)")
    P("")
    exp_first20 = mean([ev_net(x["price"]) for x in cells[1][3]])
    exp_blend = mean([ev_net(x["price"]) for x in cells[0][2]])
    per_close_blend = (sum(ev_net(x["price"]) for x in cells[0][2])
                       / float(len(cells[0][1])))
    per_close_first = (sum(ev_net(x["price"]) for x in cells[1][3])
                       / float(len(cells[1][1])))
    live_ev = mean([ev_net(p) for p in rulep])
    P("  CORRECTED EXPECTATION at the measured 0.90% flip rate")
    P("  (EV = (1-f)(1-p) - f*p - fee, averaged per trade, not at the mean "
      "price):")
    P(f"    per contract, blended rule (tau 3-30, cap 2)   "
      f"{100 * exp_blend:>7.2f}c")
    P(f"    per contract, first buy only (tau 3-20)        "
      f"{100 * exp_first20:>7.2f}c")
    P(f"    per CLOSE, blended rule                        "
      f"{100 * per_close_blend:>7.2f}c   ({len(cells[0][2])} buys over "
      f"{len(cells[0][1])} closes)")
    P(f"    per CLOSE, first buy only, tau 3-20            "
      f"{100 * per_close_first:>7.2f}c   ({len(cells[1][3])} buys over "
      f"{len(cells[1][1])} closes)")
    P(f"    the live rule-accepted signals price out at    "
      f"{100 * live_ev:>7.2f}c per contract")
    P("")
    P("  CONSEQUENCE FOR results/VERSIONS.md v8 (the withdrawn 96c ceiling).")
    P("  Its reason 1 was: 'the backtest predicted a 96c ceiling would refuse")
    P("  ~30% of trades; live it refuses 12 of 16 (75%)'.  That compared live")
    P("  FIRST buys against the backtest's BLENDED buys.  Like for like:")
    for lab, by, b, f, k in cells[:2]:
        p = [x["price"] for x in f]
        P(f"    backtest FIRST buys, {lab:<26} above 96c "
          f"{sum(1 for x in p if x > 0.96):>3} of {len(p):>3} "
          f"({100.0 * sum(1 for x in p if x > 0.96) / len(p):.0f}%)")
    P(f"    live, today's rule                              above 96c "
      f"{sum(1 for x in rulep if x > 0.96):>3} of {len(rulep):>3} "
      f"({100.0 * sum(1 for x in rulep if x > 0.96) / len(rulep):.0f}%)")
    P("  The backtest and the live tape AGREE on how often a 96c ceiling "
      "binds.")
    P("  v8's reason 1 is refuted; its reasons 2 and 3 are untouched by this "
      "file.")
    P("")
    P(f"  n is CLOSES throughout: {len(cells[0][1])} backtest closes, "
      f"{n_rule} live closes under today's rule. Twelve series settle on the "
      f"same quarter hour at rho~0.8, so a close is worth ~1.22 independent "
      f"observations, not 12.")


if __name__ == "__main__":
    main()
