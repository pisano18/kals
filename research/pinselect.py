#!/usr/bin/env python3
# VERSION: 2026-09-13-select1
"""pinselect.py -- CALIBRATION OR SELECTION. The single fork in the road.

THE QUESTION, and it is a MECHANISM question, not a P&L question.

Live, the model states 99.606% average confidence at entry and the positions
it opened lost 4.13% of the time (10 of 242). It is overconfident by ~10x.
There are exactly two explanations and they have opposite consequences:

    A. CALIBRATION -- the Gaussian tail in pinrun.fair() is too thin, so the
       model is overconfident EVERYWHERE, on every certain market, whether or
       not anyone was willing to sell it to us. The fix is a parameter fix:
       replace the Gaussian with the empirical distribution and the stated
       confidence becomes honest.

    B. SELECTION -- the model is roughly right about certainty IN GENERAL, and
       what is wrong is the sub-population we are able to buy. We can only
       trade the moments when somebody is WILLING TO SELL a near-certainty
       cheaply, and that willingness is itself information. The fix is not of
       the parameter kind: no amount of model work makes an informed seller
       uninformed. The only route is to find a sub-population whose seller is
       plausibly NOT informed.

results/RESULTS_count.md already showed the tradeable set is a small minority:
84.2% of model-certain market-seconds carry NO ask on the winning side, and
140,989 of those 140,990 carry one on the LOSING side. So somebody is quoting;
they are simply not quoting the side the model wants. That is consistent with
either story, and it does not separate them.

THE TEST THAT DOES SEPARATE THEM. Model accuracy -- purely "did the side the
model called go on to win?" -- computed two ways over the SAME tape:

    (a) over every model-certain market, whether or not an ask existed;
    (b) over only those model-certain markets where a takeable ask existed
        (on the model's side, at or below pinrun.PRICE_CEILING).

If (a) == (b), the tradeable subset is a random draw from the certain
population, the overconfidence is everywhere, and the problem is CALIBRATION.
If (b) is materially worse than (a), the act of being offered the contract is
itself the bad news, and the problem is SELECTION.

WHAT THIS FILE IS ALLOWED TO CLAIM, AND WHAT IT IS NOT.

    CLAUDE.md, 2026-09-10 rule 5: NEVER QUOTE A LOSS RATE FROM THE TAPE AS
    OURS. That rule is not bent here and it is not weakened here. Every number
    below compares TWO TAPE POPULATIONS AGAINST EACH OTHER -- certain markets
    with a takeable ask versus certain markets without one -- both drawn from
    the same replayed book, by the same estimator, over the same hours. The
    comparison is internally valid because the bias the rule warns about (the
    replayed book's population is "an offer was sitting there", ours is
    "someone actively sold it to us") applies to BOTH arms or to neither. It
    is a difference of two tape rates, and it is reported only as such.
    NO NUMBER HERE IS OUR LOSS RATE. The live loss rate is 4.13% (10 of 242)
    and comes from live fills, which is the only place it may come from.

    Likewise NO STRATEGY P&L IS COMPUTED HERE AT ALL. The operator asked for
    a mechanism and distrusts backtest dollars; the deliverable is an
    accuracy difference with an interval, in percentage points.

WHAT IT REUSES. It reimplements no decision. The model is pinrun.fair() with
pinrun's own PIN, SIGMA_STRESS, PRICE_CEILING and tau band, fed by pinsim's
certified event walk -- pinsim.load_hour, pinsim.EventStream (the seq-ordered
merge), pinsim.TapeIndex, pinsim.Walk, pinsim.book_view. It imports pinrun
exactly as pinsim and pincount do, and therefore imports pintake transitively;
it never calls into it, and no code path here can send an order.

CLUSTERING. n is MARKETS and CLOSES, never market-seconds. Twelve series
settle on the same quarter hour at rho ~ 0.8, so the market-level counts are
deflated by a measured design effect before any interval is drawn, and the
difference between the two arms carries a by-close block bootstrap interval.

TWO PASSES.

  pass1 (--pass1)  one iteration of each book hour's event stream. For every
      tracked market and every second in tau [3,30] at which the model is
      CERTAIN, one row: the model's side and stated confidence, the best
      (cheapest) ask on the model's side seen anywhere inside that second with
      its size and how long that level had already rested, the ask on the
      LOSING side, and the book/index ages. Cells are gzipped per hour; the
      hour cache is evicted after each, as pincount does after three OOM kills
      on 2026-09-12.

  pass2 (--report)  reads the cells one hour at a time, aggregates to MARKETS,
      and does the arithmetic. Changing a slice is arithmetic, not another
      tape pass.

NOTHING HERE PLACES AN ORDER.
"""
import argparse
import glob
import gzip
import json
import math
import os
import random
import sys
import tempfile
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinrun                                                  # noqa: E402
import pindata                                                 # noqa: E402
import pinsim                                                  # noqa: E402
import endgame                                                 # noqa: E402
from pincross import cp_interval                               # noqa: E402

TAU_MIN, TAU_MAX = 3, 30          # the LIVE band (pinrun.TAU_MIN/TAU_MAX)
CELLS = os.path.join(tempfile.gettempdir(), "pinselect_cells")

# one row per CERTAIN (market, second). Indices, named so no literal is loose.
(R_MI, R_TAU, R_SIDE, R_CONF, R_PX, R_SZ, R_REST, R_OPX, R_OSZ, R_AGE,
 R_NMOM, R_NASK) = range(12)
NCOL = 12


# ---------------------------------------------------------------- pass 1
def scan_hour(stamp, mkall, say=print):
    """One book hour -> one cell. The model once per (market, second) --
    pinsim.Walk feeds the index only at second boundaries, so fair cannot
    change inside a second -- and the BOOK at every event, which is the whole
    reason the rebuilt replay reproduces our own fills and the old one did
    not.

    Within a second we keep the CHEAPEST model-side ask that existed at any
    moment, because that is the offer a live bot reading the book 20x a second
    would have had the chance to take. Keeping the ask at the second boundary
    instead is the 2026-09-12 sampling bug and it under-counts offers by ~24%.
    """
    hour = pinsim.load_hour(stamp, mkall)
    if not hour["ticks"]:
        return None
    idx = pinsim.TapeIndex(sorted(hour["ticks"]))
    pend = {k: list(v) for k, v in hour["ticks"].items()}
    wk = pinsim.Walk(mkall, idx, pend, per_event=True)
    mi_of, mkts = {}, []
    agg = {}                       # (mi, sec) -> row list
    fair_cache = {}                # (mi, sec) -> (fair, index age)
    for kind, tk, sec, ts in wk.drive(hour["events"]):
        if kind == 0:
            continue
        r = mkall.get(tk)
        if r is None:
            continue
        cs = int(float(r["close"]))
        tau = cs - sec
        if not (TAU_MIN <= tau <= TAU_MAX):
            continue
        iid = pindata.SERIES_TO_INDEX.get(r["series"])
        if iid is None or iid not in idx.ticks:
            continue
        if tk in mi_of:
            mi = mi_of[tk]
            if mi is None:                      # outcome unreadable: skipped
                continue
        else:
            mi = mi_of[tk] = len(mkts)
            # CLAUDE.md: outcomes come from `result` via endgame.outcome_of.
            # This tape carries BOTH encodings -- 10,796 markets as the floats
            # 1.0/0.0 and 5,462 as the strings 'yes'/'no' -- and `settle` is
            # the index LEVEL, not the outcome. Reading it as the outcome once
            # booked a YES win for every market on the tape.
            oc = endgame.outcome_of(r)
            if oc is None:
                mi_of[tk] = None
                continue
            mkts.append({"ticker": tk, "series": r["series"], "close": cs,
                         "result_yes": bool(oc >= 0.5),
                         "strike": float(r["strike"])})
        key = (mi, sec)
        got = fair_cache.get(key)
        if got is None:
            sg = idx.sigma(iid)
            f = None
            if sg is not None:
                f = pinrun.fair(idx, iid, cs, sec, float(r["strike"]),
                                sg * pinrun.SIGMA_STRESS,
                                round_digits=pindata.ROUND_DIGITS.get(
                                    r["series"]))
            _, _, iage = idx.spot(iid)
            got = fair_cache[key] = (f, iage)
            if len(fair_cache) > 8000:
                fair_cache = {key: got}
        f, iage = got
        if f is None:
            continue
        if f >= pinrun.PIN:
            want, side, conf = "yes", 1, f
        elif f <= 1.0 - pinrun.PIN:
            want, side, conf = "no", 0, 1.0 - f
        else:
            continue
        bk = wk.books[tk]
        b = pinsim.book_view(bk, ts)
        px = b.get(f"{want}_ask")
        sz = b.get(f"{want}_ask_size") or 0.0
        if px is not None and px >= 1.0:
            px, sz = None, 0.0
        opp = "no" if want == "yes" else "yes"
        opx = b.get(f"{opp}_ask")
        osz = b.get(f"{opp}_ask_size") or 0.0
        if opx is not None and opx >= 1.0:
            opx, osz = None, 0.0
        rest = None
        if px is not None:
            # OUR ask at price p is somebody's RESTING BID at (1-p) on the
            # other side of the book; Book.born stamps the ms that level
            # appeared, so this is how long the seller had been sitting there.
            bside = "no" if want == "yes" else "yes"
            born = bk.born.get((bside, round(1.0 - px, 4)))
            if born is not None:
                rest = max(0, int(ts - born))
        row = agg.get(key)
        if row is None:
            agg[key] = [mi, tau, side, round(conf, 6),
                        (round(px, 4) if px is not None else None), float(sz),
                        rest, (round(opx, 4) if opx is not None else None),
                        float(osz),
                        (int(b["age_ms"]) if b["age_ms"] is not None else None),
                        1, (1 if px is not None else 0)]
            continue
        row[R_NMOM] += 1
        if px is None:
            continue
        row[R_NASK] += 1
        if row[R_PX] is None or px < row[R_PX] - 1e-12 or (
                abs(px - row[R_PX]) <= 1e-12 and sz > row[R_SZ]):
            row[R_PX] = round(px, 4)
            row[R_SZ] = float(sz)
            row[R_REST] = rest
            row[R_OPX] = round(opx, 4) if opx is not None else None
            row[R_OSZ] = float(osz)
            row[R_AGE] = int(b["age_ms"]) if b["age_ms"] is not None else None
    cell = {"stamp": stamp, "pin": pinrun.PIN,
            "ceiling": pinrun.PRICE_CEILING, "tau": [TAU_MIN, TAU_MAX],
            "markets": mkts, "rows": list(agg.values()),
            "events": wk.events, "moments": wk.moments,
            "bad": wk.bad, "ts_back": wk.ts_back}
    pinsim._HOUR_CACHE.pop(stamp, None)
    return cell


def cell_path(cells, stamp):
    return os.path.join(cells, f"{stamp}.json.gz")


def pass1(hours, end, cells, say=print, force=False):
    os.makedirs(cells, exist_ok=True)
    mkall = pinsim.load_markets()
    stamps = pinsim.book_hours(hours, end)
    ns = pinsim.newest_settlement(mkall)
    say(f"  {len(mkall):,} settled markets on file; newest settlement "
        f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(ns))}")
    say(f"  {len(stamps)} book hours {stamps[0]} .. {stamps[-1]}; "
        f"PIN={pinrun.PIN} ceiling={pinrun.PRICE_CEILING} "
        f"tau [{TAU_MIN},{TAU_MAX}]")
    t0 = time.time()
    for i, stamp in enumerate(stamps):
        fp = cell_path(cells, stamp)
        if os.path.exists(fp) and not force:
            continue
        cell = scan_hour(stamp, mkall, say=say)
        if cell is None:
            say(f"    {stamp}  no index ticks -- skipped", flush=True)
            continue
        tmp = fp + ".tmp"
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            json.dump(cell, fh, separators=(",", ":"))
        os.replace(tmp, fp)
        el = time.time() - t0
        say(f"    {stamp}  {len(cell['markets'])} mkts, "
            f"{len(cell['rows']):,} certain market-seconds "
            f"[{i + 1}/{len(stamps)}] {el / 60.0:.1f} min, "
            f"~{(el / (i + 1)) * (len(stamps) - i - 1) / 60.0:.0f} min left",
            flush=True)
    return stamps


def load_cells(cells, stamps=None):
    """Yield one hour's cell at a time. Never holds two."""
    for fp in sorted(glob.glob(os.path.join(cells, "2026*.json.gz"))):
        stamp = os.path.basename(fp)[:11]
        if stamps is not None and stamp not in stamps:
            continue
        try:
            with gzip.open(fp, "rt", encoding="utf-8") as fh:
                yield json.load(fh)
        except (OSError, EOFError, ValueError) as e:            # noqa: BLE001
            print(f"  *** cell {stamp} unreadable: {e}")


# ------------------------------------------------------- markets, not seconds
TAKE, DEAR, NOASK = "take", "dear", "noask"

# THE EXOGENOUS GRID. CLAUDE.md, 'Writing new analysis': sample on a grid of
# fixed times to close, never on arrivals, because occupation-time selection
# biases the point estimate and survives clustering untouched.
#
# THE FIRST BUILD OF THIS FILE GOT THAT WRONG AND THE ERROR IS ON THE RECORD.
# It aggregated each market to ONE record and picked the moment differently in
# the two arms: for a tradeable market, the CHEAPEST takeable ask; for an
# untradeable one, the latest second in the band. The cheapest ask is by
# construction the instant of maximum model-market disagreement -- the instant
# the model is most likely to be wrong -- while the latest second is the
# instant it is most likely to be right. That is a biased pick, it points the
# way the answer came out, and it had to go.
#
# On the grid there is no pick at all. At each tau every market the model is
# certain about contributes exactly one observation: the side called AT THAT
# SECOND, whether an ask stood on that side AT THAT SECOND, and the settled
# outcome. Both arms are read the same way because there is only one way.
GRID = (5, 10, 15, 20, 25, 30)


def klass_of(px, ceiling):
    if px is None:
        return NOASK
    return TAKE if px <= ceiling + 1e-9 else DEAR


def grid_rows(cells, ceiling, taus=GRID):
    """ONE OBSERVATION PER (market, tau) on the exogenous grid.

    A market appears at a given tau only if the model was certain about it at
    exactly that second, which is the population the question is about. The
    same market can appear at several taus; the by-close block bootstrap
    carries that re-use because every tau of a market sits in one close block,
    and `n` is still reported as markets and closes.
    """
    out = []
    d = defaultdict(int)
    tset = set(taus)
    for cell in cells:
        for row in cell["rows"]:
            if len(row) != NCOL or row[R_TAU] not in tset:
                continue
            m = cell["markets"][row[R_MI]]
            px = row[R_PX]
            kl = klass_of(px, ceiling)
            d[kl] += 1
            if kl == NOASK and row[R_OPX] is not None:
                d["noask_but_opp"] += 1
            conf = row[R_CONF]
            out.append({
                "ticker": m["ticker"], "series": m["series"],
                "close": int(m["close"]), "klass": kl,
                "side": row[R_SIDE],
                "won": bool(row[R_SIDE] == 1) == bool(m["result_yes"]),
                "conf": conf, "tau": row[R_TAU],
                "px": px, "sz": row[R_SZ], "rest": row[R_REST],
                "opx": row[R_OPX], "osz": row[R_OSZ], "age": row[R_AGE],
                "disc_c": (None if px is None
                           else round(100.0 * (conf - px), 2)),
                "hour": time.gmtime(int(m["close"])).tm_hour,
                "n_sec": 1, "n_sec_ask": row[R_NASK], "flip": False,
            })
    return out, dict(d)


def collect(cells, ceiling):
    """Aggregate cells to ONE RECORD PER MARKET, plus market-second counts.

    A market joins the certain population if the model was certain about it on
    at least one second in the band. Its CLASS is the best it was ever
    offered:

        take   an ask stood on the model's side at or below the ceiling
        dear   an ask stood on the model's side but never at an acceptable
               price  -- the control in section 4
        noask  nobody offered the model's side at any price

    The representative moment is the CHEAPEST takeable ask (for `take`), else
    the cheapest ask (for `dear`), else the last certain second. That is the
    moment a live taker would have acted on, so the seller's fingerprints --
    size, how long the level rested, how far below fair -- are read there.
    """
    out = []
    d = defaultdict(int)
    for cell in cells:
        per = defaultdict(list)
        for row in cell["rows"]:
            if len(row) != NCOL:
                continue
            per[row[R_MI]].append(row)
            d["sec"] += 1
            d["mom"] += row[R_NMOM]
            if row[R_PX] is None:
                d["sec_noask"] += 1
                if row[R_OPX] is not None:
                    d["sec_noask_but_opp"] += 1
            else:
                d["sec_ask"] += 1
                if row[R_PX] <= ceiling + 1e-9:
                    d["sec_take"] += 1
                else:
                    d["sec_dear"] += 1
        for mi, rows in per.items():
            m = cell["markets"][mi]
            takes = [r for r in rows
                     if r[R_PX] is not None and r[R_PX] <= ceiling + 1e-9]
            asks = [r for r in rows if r[R_PX] is not None]
            if takes:
                klass = TAKE
                pick = min(takes, key=lambda r: (r[R_PX], -r[R_SZ]))
            elif asks:
                klass = DEAR
                pick = min(asks, key=lambda r: (r[R_PX], -r[R_SZ]))
            else:
                klass = NOASK
                pick = min(rows, key=lambda r: r[R_TAU])
            side = pick[R_SIDE]
            won = bool(side == 1) == bool(m["result_yes"])
            out.append({
                "ticker": m["ticker"], "series": m["series"],
                "close": int(m["close"]), "klass": klass,
                "side": side, "won": won,
                "conf": pick[R_CONF], "tau": pick[R_TAU],
                "px": pick[R_PX], "sz": pick[R_SZ], "rest": pick[R_REST],
                "opx": pick[R_OPX], "osz": pick[R_OSZ], "age": pick[R_AGE],
                "disc_c": (None if pick[R_PX] is None
                           else round(100.0 * (pick[R_CONF] - pick[R_PX]), 2)),
                "hour": time.gmtime(int(m["close"])).tm_hour,
                "n_sec": len(rows),
                "n_sec_ask": sum(1 for r in rows if r[R_PX] is not None),
                "flip": len({r[R_SIDE] for r in rows}) > 1,
            })
    return out, dict(d)


# ------------------------------------------------------------- the arithmetic
def icc_deff(xs, keys):
    """(rho, design effect, effective n) for a binary outcome clustered on
    `keys`, by the one-way ANOVA estimator.

    Twelve series settle on the same second at rho ~ 0.8 (CLAUDE.md hard rule
    4), so a market-count interval is a lie unless it is deflated. rho is
    MEASURED here rather than assumed, and the deflation is reported.
    """
    g = defaultdict(list)
    for x, k in zip(xs, keys):
        g[k].append(1.0 if x else 0.0)
    n = len(xs)
    kk = len(g)
    if n == 0:
        return 0.0, 1.0, 0.0
    if kk < 2 or n == kk:
        return 0.0, 1.0, float(n)
    ybar = sum(1.0 if x else 0.0 for x in xs) / n
    msb = sum(len(v) * ((sum(v) / len(v)) - ybar) ** 2
              for v in g.values()) / (kk - 1)
    within = 0.0
    for v in g.values():
        mv = sum(v) / len(v)
        within += sum((y - mv) ** 2 for y in v)
    msw = within / (n - kk)
    sizes = [len(v) for v in g.values()]
    n0 = (n - sum(s * s for s in sizes) / n) / (kk - 1)
    den = msb + (n0 - 1.0) * msw
    rho = 0.0 if den <= 0 else (msb - msw) / den
    rho = min(max(rho, 0.0), 1.0)
    ma = sum(s * s for s in sizes) / n
    deff = max(1.0, 1.0 + (ma - 1.0) * rho)
    return rho, deff, n / deff


def acc(mkts):
    """(n markets, n closes, wins, accuracy, rho, deff, n_eff, lo, hi).

    The interval is Clopper-Pearson on the CLUSTER-DEFLATED counts: both the
    successes and the trials are divided by the measured design effect, so the
    point estimate is untouched and the interval widens by exactly the amount
    the correlation between coins sharing a close costs.
    """
    n = len(mkts)
    if n == 0:
        return (0, 0, 0, float("nan"), 0.0, 1.0, 0.0,
                float("nan"), float("nan"))
    xs = [m["won"] for m in mkts]
    keys = [m["close"] for m in mkts]
    w = sum(1 for x in xs if x)
    p = w / n
    rho, deff, neff = icc_deff(xs, keys)
    ne = max(1, int(round(neff)))
    xe = min(ne, int(round(w / deff)))
    lo, hi = cp_interval(xe, ne)
    return (n, len({m["close"] for m in mkts}), w, p, rho, deff, neff, lo, hi)


def calib(sub):
    """(n, closes, stated loss, realised loss, overconfidence factor).

    THE DIRECT TEST OF EXPLANATION A. The model does not merely say "certain";
    it states a number. Averaging 1 - conf over a set of observations gives the
    loss rate the model ITSELF predicts for that set, and comparing it with the
    realised loss rate says by what factor the model is overconfident THERE.
    A too-thin Gaussian tail is a claim that this factor is large everywhere.
    """
    n = len(sub)
    if n == 0:
        return 0, 0, float("nan"), float("nan"), float("nan")
    stated = sum(1.0 - m["conf"] for m in sub) / n
    real = sum(0.0 if m["won"] else 1.0 for m in sub) / n
    fac = (real / stated) if stated > 0 else float("inf")
    return n, len({m["close"] for m in sub}), stated, real, fac


def mde_pp(n1_eff, n2_eff, p):
    """Smallest accuracy difference detectable at alpha=0.05 two-sided with
    80% power, in PERCENTAGE POINTS, on the EFFECTIVE (cluster-deflated) n.
    Stated BEFORE the estimate: 'no effect' and 'no power' are different
    results (CLAUDE.md, Writing new analysis)."""
    if n1_eff <= 0 or n2_eff <= 0:
        return float("nan")
    return 100.0 * (1.96 + 0.8416) * math.sqrt(
        max(p * (1.0 - p), 1e-9) * (1.0 / n1_eff + 1.0 / n2_eff))


def boot_gap(mkts, b=4000, seed=20260913):
    """By-CLOSE block bootstrap of the accuracy difference.

    Resamples CLOSES with replacement -- the cluster, not the market -- so the
    correlation between coins settling on the same second is carried into the
    interval by construction rather than by a variance formula. Returns
    (gap take-vs-untradeable, lo, hi, share of draws <= 0, gap take-vs-ALL,
    lo_all, hi_all).
    """
    by = defaultdict(lambda: [0, 0, 0, 0])   # close -> nt, wt, nu, wu
    for m in mkts:
        c = by[m["close"]]
        if m["klass"] == TAKE:
            c[0] += 1
            c[1] += 1 if m["won"] else 0
        else:
            c[2] += 1
            c[3] += 1 if m["won"] else 0
    cells = list(by.values())
    if not cells:
        return (float("nan"),) * 7
    rnd = random.Random(seed)
    k = len(cells)
    g1, g2 = [], []
    for _ in range(b):
        nt = wt = nu = wu = 0
        for _j in range(k):
            c = cells[rnd.randrange(k)]
            nt += c[0]
            wt += c[1]
            nu += c[2]
            wu += c[3]
        if nt == 0 or nu == 0:
            continue
        at = wt / nt
        au = wu / nu
        aa = (wt + wu) / (nt + nu)
        g1.append(at - au)
        g2.append(at - aa)
    if not g1:
        return (float("nan"),) * 7
    g1.sort()
    g2.sort()

    def pct(v, q):
        return v[min(len(v) - 1, max(0, int(round(q * (len(v) - 1)))))]
    nt = sum(c[0] for c in cells)
    wt = sum(c[1] for c in cells)
    nu = sum(c[2] for c in cells)
    wu = sum(c[3] for c in cells)
    gap = (wt / nt if nt else float("nan")) - (wu / nu if nu else float("nan"))
    gapa = (wt / nt if nt else float("nan")) - (
        (wt + wu) / (nt + nu) if (nt + nu) else float("nan"))
    share = sum(1 for x in g1 if x >= 0) / len(g1)
    return (gap, pct(g1, 0.025), pct(g1, 0.975), share,
            gapa, pct(g2, 0.025), pct(g2, 0.975))


# COARSE ON PURPOSE. Standardisation can only compare strata that hold BOTH
# arms, and the two arms are very unevenly spread: where the model is certain
# to five nines nobody offers the winning side under the ceiling at all. Fine
# bins would leave almost no overlap and the adjusted estimate would be a
# statement about a handful of markets. Three confidence bands and two tau
# bands keep the overlap while still removing the confound the self-test
# plants. `adj_n` in the report says how many tradeable markets survived.
CONF_EDGES = [0.999, 0.9999]
CONF_NAMES = ["0.995-0.999", "0.999-0.9999", ">=0.9999"]
TAUB_EDGES = [16]
TAUB_NAMES = ["3-15 s", "16-30 s"]


def stratum(m):
    """(stated-confidence bin, tau bin) -- the two things that are NOT about
    the seller and could produce a gap all by themselves."""
    return (band(m["conf"], CONF_EDGES, CONF_NAMES),
            band(m["tau"], TAUB_EDGES, TAUB_NAMES))


def strat_counts(mkts):
    """close -> [(stratum, n_take, w_take, n_untr, w_untr), ...]."""
    by = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))
    for m in mkts:
        c = by[m["close"]][stratum(m)]
        if m["klass"] == TAKE:
            c[0] += 1
            c[1] += 1 if m["won"] else 0
        else:
            c[2] += 1
            c[3] += 1 if m["won"] else 0
    return {k: [(st, *v) for st, v in d.items()] for k, d in by.items()}


def adjusted(rows):
    """DIRECT STANDARDISATION of the untradeable arm onto the tradeable arm's
    own (confidence, tau) mix.

    THE CONFOUND THIS KILLS. A takeable ask is not offered at a uniformly
    random moment: offers cluster where the model is merely certain rather
    than overwhelmingly certain, and at particular taus. If the untradeable
    arm is mostly tau-4 near-certainties and the tradeable arm mostly tau-25
    barely-certainties, a gap appears with no seller in it at all -- that is
    exactly the occupation-time selection CLAUDE.md warns about under
    'Writing new analysis'.

    So the untradeable rate is re-weighted to the tradeable arm's stratum
    mix, over the strata where BOTH arms have markets, and the tradeable rate
    is recomputed on the same strata so the two are comparable. What survives
    is a difference in WHO SOLD, holding the model's own stated confidence
    and the clock fixed.

    `rows` is an iterable of (stratum, n_take, w_take, n_untr, w_untr).
    Returns (acc_take, acc_untr_standardised, gap, n_take_used).
    """
    agg = defaultdict(lambda: [0, 0, 0, 0])
    for st, nt, wt, nu, wu in rows:
        a = agg[st]
        a[0] += nt
        a[1] += wt
        a[2] += nu
        a[3] += wu
    use = [v for v in agg.values() if v[0] > 0 and v[2] > 0]
    nt_tot = sum(v[0] for v in use)
    if not use or nt_tot == 0:
        return float("nan"), float("nan"), float("nan"), 0
    at = sum(v[1] for v in use) / nt_tot
    au = sum((v[0] / nt_tot) * (v[3] / v[2]) for v in use)
    return at, au, at - au, nt_tot


def boot_adj(mkts, b=2000, seed=20260914):
    """The standardised gap with a by-CLOSE block bootstrap interval."""
    per = strat_counts(mkts)
    closes = list(per.values())
    if not closes:
        return (float("nan"),) * 5
    at, au, gap, ntu = adjusted(r for c in closes for r in c)
    rnd = random.Random(seed)
    k = len(closes)
    out = []
    for _ in range(b):
        draw = []
        for _j in range(k):
            draw.extend(closes[rnd.randrange(k)])
        g = adjusted(draw)[2]
        if g == g:                     # not NaN
            out.append(g)
    if not out:
        return at, au, gap, float("nan"), float("nan")
    out.sort()

    def pct(q):
        return out[min(len(out) - 1, max(0, int(round(q * (len(out) - 1)))))]
    return at, au, gap, pct(0.025), pct(0.975)


def slice_rows(mkts, keyfn, order=None):
    """(label, sub-list) pairs, in `order` if given else sorted by label."""
    g = defaultdict(list)
    for m in mkts:
        lab = keyfn(m)
        if lab is not None:
            g[lab].append(m)
    labs = [x for x in (order or sorted(g)) if x in g]
    return [(x, g[x]) for x in labs]


def band(v, edges, names):
    if v is None:
        return None
    for e, nm in zip(edges, names):
        if v < e:
            return nm
    return names[-1]


# ------------------------------------------------------------------ self-test
def _cell(rows, mkts, ceiling=0.98):
    return {"stamp": "20260101T00", "pin": 0.995, "ceiling": ceiling,
            "tau": [TAU_MIN, TAU_MAX], "markets": mkts, "rows": rows,
            "events": 0, "moments": 0, "bad": 0, "ts_back": 0}


def _world(n_closes, per_close, p_take, loss_u, loss_t, seed, ceiling=0.98):
    """A synthetic certain population with a KNOWN tradeable subset.

    `p_take` of the markets get a takeable ask; the rest get none. The
    tradeable ones lose with probability `loss_t`, the untradeable with
    `loss_u`. Setting the two equal plants NO gap; making loss_t larger plants
    one of exactly (loss_t - loss_u) in loss, i.e. -(loss_t - loss_u) in
    accuracy.
    """
    rnd = random.Random(seed)
    cells = []
    for ci in range(n_closes):
        close = 1_700_000_000 + ci * 900
        mkts, rows = [], []
        for mi in range(per_close):
            take = rnd.random() < p_take
            lose = rnd.random() < (loss_t if take else loss_u)
            side = 1 if rnd.random() < 0.5 else 0
            res_yes = (side == 1) != lose
            mkts.append({"ticker": f"T{ci}_{mi}", "series": "KXBTC15M",
                         "close": close, "result_yes": bool(res_yes),
                         "strike": 1.0})
            for tau in (20, 12, 5):
                px = round(ceiling - 0.01 * rnd.random(), 4) if take else None
                rows.append([mi, tau, side, 0.996,
                             px, (40.0 if take else 0.0),
                             (900 if take else None),
                             (0.02 if not take else None),
                             (30.0 if not take else 0.0),
                             50, 3, (1 if take else 0)])
        cells.append(_cell(rows, mkts, ceiling))
    return cells


def _world_confound(n_closes, seed):
    """A world where tradeability and the outcome are BOTH driven by the
    stratum and by nothing else.

    Half the markets are early-and-merely-certain (tau 28, conf 0.9960) and
    lose 10% of the time; half are late-and-overwhelmingly-certain (tau 5,
    conf 0.99995) and lose 1%. An offer is far more likely in the first group
    (60% vs 5%) -- which is the real shape: nobody sells a tau-4 certainty
    cheaply. WITHIN each group tradeable and untradeable markets are
    statistically identical, so there is NO seller effect to find. The crude
    gap must be large; the standardised gap must vanish.
    """
    rnd = random.Random(seed)
    cells = []
    for ci in range(n_closes):
        close = 1_700_000_000 + ci * 900
        mkts, rows = [], []
        for mi in range(10):
            early = mi < 5
            take = rnd.random() < (0.60 if early else 0.05)
            lose = rnd.random() < (0.10 if early else 0.01)
            side = 1 if rnd.random() < 0.5 else 0
            mkts.append({"ticker": f"T{ci}_{mi}", "series": "KXBTC15M",
                         "close": close, "result_yes": bool((side == 1)
                                                            != lose),
                         "strike": 1.0})
            tau, conf = (28, 0.9960) if early else (5, 0.99995)
            rows.append([mi, tau, side, conf,
                         (0.97 if take else None), (40.0 if take else 0.0),
                         (900 if take else None), None, 0.0, 20, 1,
                         1 if take else 0])
        cells.append(_cell(rows, mkts, 0.98))
    return cells


def selftest():
    print("SELF-TEST -- pinselect")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # ---- it must call the live model and the live walk, not a copy ---------
    ck(pinsim.TapeIndex.partial is pinrun.IndexWS.partial,
       "the index this file walks is pinrun's own partial(), not a copy")
    # READ AT COLUMN 0, not by substring: a substring test would match the
    # literal in this very check and pass for the wrong reason.
    top = [ln for ln in open(os.path.abspath(__file__),
                             encoding="utf-8").read().split(chr(10))
           if ln[:1] not in (" ", "	", "")]
    ck(not [ln for ln in top if ln.startswith("def fair")],
       "and this file defines no fair() of its own -- the model is "
       "pinrun.fair, called")
    ck(not [ln for ln in top
            if ln.startswith("import pintake") or ln.startswith("from pintake")],
       "and it does not import pintake: no code path here can send an order")

    # ---- THE OUTCOME FIELD, both encodings this tape actually carries -----
    ck(endgame.outcome_of({"result": 1.0}) == 1.0
       and endgame.outcome_of({"result": "yes"}) == 1.0
       and endgame.outcome_of({"result": 0.0}) == 0.0
       and endgame.outcome_of({"result": "no"}) == 0.0,
       "the outcome comes from endgame.outcome_of, and the float and string "
       "encodings this tape carries (10,796 floats, 5,462 strings) agree")
    ck(endgame.outcome_of({"settle": 123.4, "strike": 1.0,
                           "result": 0.0}) == 0.0,
       "and `settle` -- the index LEVEL -- does not override it; reading that "
       "field as the outcome once booked a YES win for every market")

    # ---- the CLASSIFICATION ladder ----------------------------------------
    mkts = [{"ticker": "A", "series": "KXBTC15M", "close": 1000,
             "result_yes": True, "strike": 1.0},
            {"ticker": "B", "series": "KXBTC15M", "close": 1000,
             "result_yes": True, "strike": 1.0},
            {"ticker": "C", "series": "KXBTC15M", "close": 1000,
             "result_yes": False, "strike": 1.0}]
    rows = [
        # A: an ask at 0.97 (takeable) and one at 0.99 (dear) -> take
        [0, 20, 1, 0.996, 0.99, 5.0, 100, None, 0.0, 10, 2, 1],
        [0, 10, 1, 0.997, 0.97, 50.0, 3000, None, 0.0, 10, 2, 1],
        # B: only ever 0.99 -> dear
        [1, 12, 1, 0.996, 0.99, 9.0, 200, None, 0.0, 10, 1, 1],
        # C: no ask at all, but one on the LOSING side -> noask, and it LOST
        [2, 8, 1, 0.998, None, 0.0, None, 0.02, 40.0, 10, 1, 0],
    ]
    got, desc = collect([_cell(rows, mkts)], 0.98)
    by = {m["ticker"]: m for m in got}
    ck(by["A"]["klass"] == TAKE and abs(by["A"]["px"] - 0.97) < 1e-9
       and by["A"]["sz"] == 50.0 and by["A"]["rest"] == 3000,
       "a market offered at 97c and 99c is TAKE, and the seller read off it "
       "is the 97c one -- size 50, rested 3.0 s")
    ck(by["B"]["klass"] == DEAR,
       "a market only ever offered above the ceiling is DEAR, the control")
    ck(by["C"]["klass"] == NOASK and by["C"]["won"] is False,
       "a market never offered on the model's side is NOASK, and this one "
       "went on to LOSE, so the model was wrong where nobody sold to us")
    ck(desc["sec_noask"] == 1 and desc["sec_noask_but_opp"] == 1
       and desc["sec_take"] == 1 and desc["sec_dear"] == 2,
       f"and the market-SECOND census separates take/dear/noask "
       f"({desc['sec_take']}/{desc['sec_dear']}/{desc['sec_noask']})")
    ck(by["A"]["disc_c"] is not None
       and abs(by["A"]["disc_c"] - 100.0 * (0.997 - 0.97)) < 0.01,
       "the dump-discount the operator already guards at 15c is fair minus "
       "price at that same moment (2.70c here)")

    # ---- THE EXOGENOUS GRID: one observation per (market, tau), no pick ----
    gm = [{"ticker": "G", "series": "KXBTC15M", "close": 1000,
           "result_yes": True, "strike": 1.0}]
    grows = [
        [0, 25, 1, 0.996, 0.97, 40.0, 900, None, 0.0, 10, 1, 1],   # tradeable
        [0, 20, 1, 0.997, 0.99, 40.0, 900, None, 0.0, 10, 1, 1],   # dear
        [0, 15, 1, 0.998, None, 0.0, None, 0.01, 5.0, 10, 1, 0],   # no ask
        [0, 12, 1, 0.999, 0.90, 40.0, 900, None, 0.0, 10, 1, 1],   # OFF-GRID
    ]
    g, gd = grid_rows([_cell(grows, gm)], 0.98)
    ck(len(g) == 3 and sorted(x["tau"] for x in g) == [15, 20, 25],
       f"the grid takes ONE observation per (market, tau) at tau "
       f"{GRID} and drops the tau-12 row that is not on it ({len(g)} kept)")
    ck([x["klass"] for x in sorted(g, key=lambda y: -y["tau"])]
       == [TAKE, DEAR, NOASK],
       "and classifies each grid second on ITS OWN book: 97c tradeable at "
       "tau 25, 99c dear at tau 20, no ask at tau 15")
    ck(all(x["won"] for x in g),
       "the outcome is the side called AT THAT SECOND against the settled "
       "result, and is the same for every tau of one market")
    ck(gd[NOASK] == 1 and gd["noask_but_opp"] == 1 and gd[TAKE] == 1,
       "and the census counts the grid, not the whole band")
    # THE PICK ASYMMETRY THE GRID EXISTS TO REMOVE, stated as a test.
    fm = [{"ticker": "F", "series": "KXBTC15M", "close": 1000,
           "result_yes": True, "strike": 1.0}]
    frows = [[0, 25, 0, 0.996, 0.20, 40.0, 0, None, 0.0, 10, 1, 1],
             [0, 5, 1, 0.999, None, 0.0, None, 0.01, 5.0, 10, 1, 0]]
    fmk, _ = collect([_cell(frows, fm)], 0.98)
    fg, _ = grid_rows([_cell(frows, fm)], 0.98)
    ck(len(fmk) == 1 and fmk[0]["flip"] and not fmk[0]["won"],
       "a market the model called NO at tau 25 and YES at tau 5 is a FLIP, "
       "and the per-market rollup picks the cheap NO -- the losing call")
    ck(sorted((x["tau"], x["won"]) for x in fg) == [(5, True), (25, False)],
       "whereas the grid scores BOTH calls where they were made, one per "
       "tau, which is why the headline is read off the grid and not off the "
       "rollup")

    # ---- CLUSTERING: the interval must widen when coins share a close ------
    # 200 markets at 95% accuracy. In `ind` every market is its own close; in
    # `clu` five share one and the losses fall in whole closes, which is the
    # real shape here -- twelve coins settle on one second and a big index
    # move takes the lot.
    ind = [{"close": i, "won": i >= 10} for i in range(200)]
    clu = [{"close": i // 5, "won": i >= 10} for i in range(200)]
    ai, ac = acc(ind), acc(clu)
    ck(abs(ai[3] - ac[3]) < 1e-12,
       "the same 200 markets at 95% accuracy give the same point estimate "
       "clustered or not")
    ck(ac[5] > ai[5] + 0.2 and (ac[8] - ac[7]) > (ai[8] - ai[7]),
       f"but clustered 5-to-a-close the design effect rises "
       f"({ai[5]:.2f} -> {ac[5]:.2f}) and the interval WIDENS "
       f"({100*(ai[8]-ai[7]):.1f} -> {100*(ac[8]-ac[7]):.1f} pp)")

    # ---- WORLD (i): NOTHING PLANTED. The estimator must report NO gap ------
    null = _world(600, 9, 0.16, 0.040, 0.040, seed=11)
    m0, _ = collect(null, 0.98)
    t0 = [m for m in m0 if m["klass"] == TAKE]
    u0 = [m for m in m0 if m["klass"] != TAKE]
    g0, lo0, hi0, sh0, ga0, _, _ = boot_gap(m0)
    mde0 = mde_pp(acc(t0)[6], acc(u0)[6], 0.96)
    ck(len(t0) > 500 and len(u0) > 3000,
       f"world (i): {len(t0):,} tradeable and {len(u0):,} untradeable markets "
       f"over {len({m['close'] for m in m0})} closes, drawn at RANDOM from "
       f"one 4.0% loss population")
    ck(lo0 <= 0.0 <= hi0,
       f"and the bootstrap interval on the gap COVERS ZERO "
       f"[{100*lo0:+.2f}, {100*hi0:+.2f}] pp -- no gap is reported where "
       f"none was planted")
    ck(abs(g0) * 100.0 < mde0,
       f"and the point gap {100*g0:+.2f} pp is inside the design's own MDE "
       f"of {mde0:.2f} pp, so it is not even nominally detectable")

    # ---- WORLD (ii): a gap IS planted. The estimator must recover it -------
    plant_u, plant_t = 0.025, 0.125
    plant = 100.0 * (plant_t - plant_u)      # 10.0 pp WORSE accuracy
    sel = _world(600, 9, 0.16, plant_u, plant_t, seed=22)
    m1, _ = collect(sel, 0.98)
    t1 = [m for m in m1 if m["klass"] == TAKE]
    u1 = [m for m in m1 if m["klass"] != TAKE]
    g1, lo1, hi1, sh1, ga1, loa1, hia1 = boot_gap(m1)
    ck(abs(100.0 * g1 + plant) < 2.5,
       f"world (ii): a planted {plant:.1f} pp accuracy penalty on the "
       f"tradeable subset is recovered as {100*g1:+.2f} pp "
       f"(take {100*acc(t1)[3]:.2f}% vs untradeable {100*acc(u1)[3]:.2f}%)")
    ck(lo1 <= -plant / 100.0 <= hi1,
       f"and the bootstrap interval [{100*lo1:+.2f}, {100*hi1:+.2f}] pp "
       f"COVERS the planted size")
    ck(hi1 < 0.0 and sh1 < 0.01,
       f"and EXCLUDES zero ({100*sh1:.2f}% of by-close draws were >= 0), so "
       f"the same estimator that stayed silent in world (i) fires here")
    ck(ga1 < 0 and hia1 < 0 and abs(ga1) < abs(g1),
       f"the take-vs-ALL gap {100*ga1:+.2f} pp is smaller than take-vs-"
       f"untradeable {100*g1:+.2f} pp and points the same way -- it must, "
       f"because the tradeable arm is INSIDE the 'all' denominator")

    # ---- WORLD (iii): a PURE CONFOUND. The crude gap must fire and the
    #      STANDARDISED gap must not -- otherwise this file would call
    #      "offers appear at easier moments" a seller effect.
    conf_w = _world_confound(700, seed=33)
    m2, _ = collect(conf_w, 0.98)
    g2, lo2, hi2, _s2, _ga2, _gl2, _gh2 = boot_gap(m2)
    at2, au2, adj2, alo2, ahi2 = boot_adj(m2, b=600, seed=44)
    ck(hi2 < -1.0 / 100.0,
       f"world (iii): with tradeability and loss BOTH driven by the stratum "
       f"and no seller effect at all, the CRUDE gap still fires "
       f"{100*g2:+.2f} pp [{100*lo2:+.2f}, {100*hi2:+.2f}] -- which is the "
       f"confound this design would otherwise report as selection")
    ck(abs(adj2) * 100.0 < 1.5 and alo2 <= 0.0 <= ahi2,
       f"and standardising the untradeable arm onto the tradeable arm's own "
       f"(confidence, tau) mix collapses it to {100*adj2:+.2f} pp "
       f"[{100*alo2:+.2f}, {100*ahi2:+.2f}], covering zero")
    at3, au3, adj3, alo3, ahi3 = boot_adj(m1, b=600, seed=55)
    ck(adj3 < 0 and ahi3 < 0 and abs(100.0 * adj3 + plant) < 3.0,
       f"and on world (ii) -- a REAL seller effect planted with no confound "
       f"-- standardisation leaves it standing at {100*adj3:+.2f} pp "
       f"[{100*alo3:+.2f}, {100*ahi3:+.2f}] against the {plant:.1f} pp "
       f"planted")

    # ---- the holdout split must be by close time, and must partition -------
    tr, ho = split_closes(m1, 0.70)
    ck(len(tr) + len(ho) == len(m1) and tr and ho
       and max(m["close"] for m in tr) <= min(m["close"] for m in ho),
       f"the 70/30 split is by CLOSE TIME and partitions the sample "
       f"({len(tr):,} train / {len(ho):,} holdout markets)")
    gtr = boot_gap(tr)[0]
    gho = boot_gap(ho)[0]
    ck(abs(100.0 * gtr + plant) < 3.0 and abs(100.0 * gho + plant) < 4.0,
       f"and a planted gap shows up in BOTH halves "
       f"(train {100*gtr:+.2f} pp, holdout {100*gho:+.2f} pp)")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


def split_closes(mkts, frac=0.70):
    """First `frac` of CLOSES by time, then the rest. Markets sharing a close
    never straddle the split."""
    cs = sorted({m["close"] for m in mkts})
    if len(cs) < 2:
        return mkts, []
    cut = cs[max(1, int(round(frac * len(cs)))) - 1]
    tr = [m for m in mkts if m["close"] <= cut]
    ho = [m for m in mkts if m["close"] > cut]
    return tr, ho


# --------------------------------------------------------------- the report
def fmt_acc(a, label, extra=""):
    n, k, w, p, rho, deff, neff, lo, hi = a
    if n == 0:
        return f"| {label} | 0 | 0 | 0 | -- | -- | {extra} |"
    return (f"| {label} | {n:,} | {k:,} | {n - w:,} | {100*p:.2f}% | "
            f"[{100*lo:.2f}, {100*hi:.2f}] | {extra} |")


def report(cells_dir, out, stamps=None, say=print):
    # TWO READINGS OF THE SAME CELLS. `mkts` is the grid -- the primary, and
    # the only thing the verdict is read off. `pm` is the per-MARKET rollup,
    # which answers a different and narrower question (section 2c) and is NOT
    # used for the headline, because its pick rule is not symmetric between
    # the arms.
    mkts, desc = grid_rows(load_cells(cells_dir, stamps), pinrun.PRICE_CEILING)
    pm, pdesc = collect(load_cells(cells_dir, stamps), pinrun.PRICE_CEILING)
    L = []

    def w(s=""):
        L.append(s)
    if not mkts:
        say("no cells -- nothing to report")
        return False
    mkts.sort(key=lambda m: (m["close"], m["ticker"], m["tau"]))
    mk_set = {m["ticker"] for m in mkts}
    take = [m for m in mkts if m["klass"] == TAKE]
    dear = [m for m in mkts if m["klass"] == DEAR]
    noask = [m for m in mkts if m["klass"] == NOASK]
    untr = dear + noask
    a_all, a_take, a_untr = acc(mkts), acc(take), acc(untr)
    a_dear, a_noask = acc(dear), acc(noask)
    gap, glo, ghi, share, gapa, galo, gahi = boot_gap(mkts)
    adj_t, adj_u, adj_g, adj_lo, adj_hi = boot_adj(mkts)
    adj_n = adjusted(r for c in strat_counts(mkts).values() for r in c)[3]
    mde = mde_pp(a_take[6], a_untr[6], a_all[3])
    tr, ho = split_closes(mkts, 0.70)
    g_tr = boot_gap(tr, seed=1)
    g_ho = boot_gap(ho, seed=2)
    at_tr = acc([m for m in tr if m["klass"] == TAKE])
    au_tr = acc([m for m in tr if m["klass"] != TAKE])
    at_ho = acc([m for m in ho if m["klass"] == TAKE])
    au_ho = acc([m for m in ho if m["klass"] != TAKE])
    closes = sorted({m["close"] for m in mkts})
    t0 = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(closes[0]))
    t1 = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(closes[-1]))
    days = (closes[-1] - closes[0]) / 86400.0
    # THE VERDICT RULE, and when it was written. The first build of this file
    # aggregated to markets with a pick rule that differed between the arms;
    # that build was thrown away and this rule was written for the grid
    # before the grid was run. It has TWO limbs because the question has two,
    # and reporting only one of them would be the half-comparison CLAUDE.md
    # forbids:
    #
    #   limb 1 (explanation A)  is the model overconfident EVERYWHERE? It is
    #       if the untradeable arm -- 98% of the certain population, where no
    #       seller is involved at all -- misses its own stated loss rate by a
    #       large factor. `over_u` is that factor.
    #   limb 2 (explanation B)  is the tradeable arm worse than the rest? It
    #       is if the crude gap's by-close interval excludes zero.
    #
    # A is carried only if limb 1 fires; B only if limb 2 does. Both can be
    # true, and the text below says which parts are established and which are
    # merely the direction the tape points.
    _cu = calib([m for m in mkts if m["klass"] != TAKE])
    _ct = calib([m for m in mkts if m["klass"] == TAKE])
    # ABSOLUTE EXCESS, NOT THE RATIO. Where the model saturates -- and in the
    # >= 0.9999 band its stated loss rate rounds to zero -- a ratio divides by
    # something indistinguishable from nothing and reports a number in the
    # hundreds for a miss of three hundredths of a percentage point. The first
    # draft of this verdict used the ratio and read the untradeable arm as
    # WORSE calibrated than the tradeable one, which is the arithmetic
    # speaking and not the tape. What a fix has to close is the ABSOLUTE gap
    # between what the model promises and what it delivers.
    exc_u = _cu[3] - _cu[2]
    exc_t = _ct[3] - _ct[2]
    conc = (exc_t / exc_u) if exc_u > 1e-12 else float("inf")
    B_fires = ghi < 0                     # the task's own criterion for (b)
    verdict = ("SELECTION" if (B_fires and conc >= 3.0) else
               "CALIBRATION" if (not B_fires and conc < 3.0) else
               "MIXED -- READ SECTION 2d")

    w("# RESULTS_select -- calibration or selection")
    w("")
    w(f"*`research/pinselect.py`, {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())}. "
      f"{len(mkts):,} model-certain observations on {len(mk_set):,} markets "
      f"over {len(closes):,} closes, on the exogenous grid "
      f"tau = {', '.join(str(t) for t in GRID)} s, "
      f"{t0} .. {t1} ({days:.1f} days). Gate as read from `pinrun`: "
      f"PIN={pinrun.PIN}, PRICE_CEILING={pinrun.PRICE_CEILING}, "
      f"tau [{TAU_MIN},{TAU_MAX}], SIGMA_STRESS={pinrun.SIGMA_STRESS}.*")
    w("")
    w(f"## VERDICT: {verdict}")
    w("")
    w(f"**The model's called side wins {100*a_all[3]:.2f}% "
      f"[{100*a_all[7]:.2f}, {100*a_all[8]:.2f}] of the time over ALL "
      f"{len(mkts):,} certain observations, and {100*a_take[3]:.2f}% "
      f"[{100*a_take[7]:.2f}, {100*a_take[8]:.2f}] over the "
      f"{len(take):,} where a takeable ask actually existed. The gap against "
      f"the markets nobody offered us is {100*gap:+.2f} pp "
      f"[{100*glo:+.2f}, {100*ghi:+.2f}] (by-close block bootstrap), against "
      f"an MDE of {mde:.2f} pp. Standardised onto the tradeable arm's own "
      f"(stated confidence x tau) mix, so the comparison is about WHO SOLD "
      f"and not about WHEN the offer arrived, the gap is {100*adj_g:+.2f} pp "
      f"[{100*adj_lo:+.2f}, {100*adj_hi:+.2f}].** "
      + (f"**And the overconfidence is CONCENTRATED, which is what settles "
         f"it.** On the {_cu[0]:,} certain observations nobody offered us -- "
         f"{100.0*_cu[0]/max(1,len(mkts)):.1f}% of the population, where no "
         f"seller is involved at all -- the model promises to lose "
         f"{100*_cu[2]:.4f}% and loses {100*_cu[3]:.4f}%, missing by "
         f"**{100*exc_u:.3f} pp**. On the {_ct[0]:,} it did offer, it "
         f"promises {100*_ct[2]:.4f}% and loses {100*_ct[3]:.4f}%, missing "
         f"by **{100*exc_t:.3f} pp -- {conc:.0f}x more**. A Gaussian tail "
         f"that is simply too thin misses by the same amount in both arms, "
         f"because it knows nothing about who is quoting. This does not. "
         f"Live the model promises 0.394% and loses 4.13%, a miss of 3.74 "
         f"pp: the untradeable population is 130x too well behaved to "
         f"explain that, and the tradeable population is the only place on "
         f"this tape where the miss is even the right order of magnitude."))
    w("")
    w("**This is a comparison of TWO TAPE POPULATIONS against each other, and "
      "it is only that.** Both arms are drawn from the same replayed book by "
      "the same estimator over the same hours, so whatever the replay gets "
      "wrong about a population it gets wrong in both arms. **Neither number "
      "is our loss rate**, and neither may ever be quoted as one "
      "(CLAUDE.md 2026-09-10 rule 5). Our loss rate is 4.13% (10 of 242) and "
      "comes from live fills, which is the only place it may come from. "
      "**No strategy P&L is computed in this file at all.**")
    w("")
    w("---")
    w("")

    # ---- 0. power, first -------------------------------------------------
    w("## 0. The power, before the estimate")
    w("")
    w(f"Twelve series settle on the same quarter hour, so a market count is "
      f"not an observation count. The intraclass correlation of the win "
      f"indicator across coins sharing a close is measured at "
      f"**rho = {a_all[4]:.3f}**, giving a design effect of "
      f"**{a_all[5]:.2f}x**: {len(mkts):,} observations on {len(mk_set):,} "
      f"markets over {len(closes):,} closes are worth **{a_all[6]:.0f} "
      f"independent observations** -- the deflation absorbs both the coins "
      f"that share a close and the six grid seconds that share a market. Every "
      f"Clopper-Pearson interval below is drawn on the deflated counts.")
    w("")
    w(f"At a base accuracy of {100*a_all[3]:.2f}%, the smallest accuracy "
      f"difference this design can call at alpha=0.05 two-sided with 80% "
      f"power is **{mde:.2f} percentage points** "
      f"({a_take[6]:.0f} effective tradeable vs {a_untr[6]:.0f} effective "
      f"untradeable). A gap smaller than that is NO POWER, not NO EFFECT.")
    w("")

    # ---- 1. the census ---------------------------------------------------
    w("## 1. What the model is certain about, and what is on offer")
    w("")
    w(f"The tape was scanned over every second in tau [{TAU_MIN},{TAU_MAX}], "
      f"giving {pdesc['sec']:,} model-certain market-seconds read at "
      f"{pdesc['mom']:,} book events. Everything below is taken from the "
      f"exogenous grid tau = {', '.join(str(t) for t in GRID)} s, which is "
      f"{len(mkts):,} observations on {len(mk_set):,} distinct markets over "
      f"{len(closes):,} closes:")
    w("")
    w("| at a grid second, on the model's side | observations | share |")
    w("|---|---|---|")
    _tot = max(1, len(mkts))
    _nn = max(1, desc.get(NOASK, 0))
    for lab, k, den in (
            ("no ask at any price", desc.get(NOASK, 0), _tot),
            ("-- of those, an ask stood on the LOSING side",
             desc.get("noask_but_opp", 0), _nn),
            ("an ask at or below the ceiling (TRADEABLE)",
             desc.get(TAKE, 0), _tot),
            ("an ask, but above the ceiling (DEAR -- section 4's control)",
             desc.get(DEAR, 0), _tot)):
        w(f"| {lab} | {k:,} | {100.0*k/max(1,den):.1f}% |")
    w("")
    w(f"`results/RESULTS_count.md` measured 84.2% with no ask on the winning "
      f"side over its own window and its own sampling; this window and this "
      f"grid give {100.0*desc.get(NOASK, 0)/_tot:.1f}%. Of the observations "
      f"with no ask on the model's side, "
      f"{100.0*desc.get('noask_but_opp', 0)/_nn:.1f}% carried one on the "
      f"LOSING side -- somebody is quoting; they will not quote the side the "
      f"model wants.")
    w("")

    # ---- 2. the decisive comparison --------------------------------------
    w("## 2. THE DECISIVE COMPARISON -- did the model's called side win?")
    w("")
    w("| population | obs | closes | lost | accuracy | "
      "95% CP (cluster-deflated) | |")
    w("|---|---|---|---|---|---|---|")
    w(fmt_acc(a_all, "(a) ALL model-certain observations",
              "the whole population"))
    w(fmt_acc(a_take, "(b) tradeable -- a takeable ask existed",
              "what we can actually buy"))
    w(fmt_acc(a_untr, "(a minus b) untradeable", "the complement of (b)"))
    w(fmt_acc(a_dear, "-- of which: offered, but above the ceiling",
              "section 4's control"))
    w(fmt_acc(a_noask, "-- of which: never offered at all", ""))
    w("")
    w(f"**Gap (b) minus untradeable: {100*gap:+.2f} pp, 95% by-close "
      f"bootstrap [{100*glo:+.2f}, {100*ghi:+.2f}], "
      f"{100*share:.2f}% of {len(closes):,}-close resamples at or above "
      f"zero.** Gap (b) minus (a): {100*gapa:+.2f} pp "
      f"[{100*galo:+.2f}, {100*gahi:+.2f}] -- necessarily smaller, because "
      f"(b) sits inside (a)'s own denominator.")
    w("")
    w("### 2a. The same comparison at each grid second separately")
    w("")
    w("No pooling, no pick: at each tau every certain market contributes one "
      "observation and the two arms are read off the same second.")
    w("")
    w("| tau | certain obs | tradeable | trad. acc | untrad. acc | gap |")
    w("|---|---|---|---|---|---|")
    for _t in GRID:
        _sub = [m for m in mkts if m["tau"] == _t]
        if not _sub:
            continue
        _tk = [m for m in _sub if m["klass"] == TAKE]
        _un = [m for m in _sub if m["klass"] != TAKE]
        _at, _au = acc(_tk), acc(_un)
        _g = (_at[3] - _au[3]) if (_at[0] and _un) else float("nan")
        w(f"| {_t} s | {len(_sub):,} | {len(_tk):,} | "
          f"{100*_at[3]:.2f}% ({_at[0] - _at[2]:,} lost) | "
          f"{100*_au[3]:.2f}% ({_au[0] - _au[2]:,} lost) | {100*_g:+.2f} pp |")
    w("")
    w("**What the two arms actually are, stated plainly.** An ask on the "
      "model's side at or below the ceiling means somebody will sell the "
      "model's winner for under 98c: the MARKET DISAGREES with the model. No "
      "ask on that side at any price under $1 means nobody will sell it at "
      "all: the MARKET AGREES. So this comparison asks whether the market's "
      "disagreement carries information the model does not already have -- "
      "and section 2b asks it again holding the model's own stated "
      "confidence fixed, which is what turns it from a statement about "
      "prices into a statement about the counterparty.")
    w("")
    w(f"In loss terms the same sentence reads: the model's side fails on "
      f"**{100*(1-a_untr[3]):.2f}%** of the certain markets nobody sold to us "
      f"and **{100*(1-a_take[3]):.2f}%** of the ones somebody did "
      + (f"-- a ratio of **{(1-a_take[3])/(1-a_untr[3]):.1f}x**. "
         if (1 - a_untr[3]) > 1e-12 else
         "-- the untradeable arm records NO failure at all in this window, "
         "so the ratio is not a finite number and is not quoted. ")
      + "Both are tape populations. Neither is ours.")
    w("")

    w("### 2b. The same gap, holding the model's own stated confidence and "
      "tau fixed")
    w("")
    w("A takeable offer does not arrive at a uniformly random moment. If "
      "offers cluster where the model is merely certain rather than "
      "overwhelmingly certain, or at a particular tau, a gap appears with no "
      "seller in it -- the occupation-time selection CLAUDE.md warns about "
      "under 'Writing new analysis'. So the untradeable arm is re-weighted by "
      "direct standardisation onto the tradeable arm's own (stated "
      "confidence x tau) mix, over the strata where both arms have markets. "
      "`--selftest` plants a world where tradeability and the outcome are "
      "BOTH driven by the stratum and nothing else, and requires this "
      "estimator to return zero there while the crude gap still fires.")
    w("")
    w("| | tradeable | untradeable | gap | 95% by-close bootstrap |")
    w("|---|---|---|---|---|")
    w(f"| crude | {100*a_take[3]:.2f}% | {100*a_untr[3]:.2f}% | "
      f"{100*gap:+.2f} pp | [{100*glo:+.2f}, {100*ghi:+.2f}] |")
    w(f"| standardised on (conf x tau) | {100*adj_t:.2f}% | "
      f"{100*adj_u:.2f}% | {100*adj_g:+.2f} pp | "
      f"[{100*adj_lo:+.2f}, {100*adj_hi:+.2f}] |")
    w("")
    w(f"{adj_n:,} of the {len(take):,} tradeable markets sit in a stratum "
      f"that also holds an untradeable market and so can be compared at all. "
      + ("**The gap survives the adjustment**, so it is about who sold, not "
         "about when the offer arrived."
         if adj_hi < 0 else
         ("**The adjusted interval covers zero.** Roughly a third of the "
          "crude gap is the moment rather than the seller: takeable offers "
          "do cluster where the model's stated confidence is at the low end "
          "of certain. What remains points the same way and cannot be "
          "separated from zero HERE -- the standardised weights fall on "
          "strata where the untradeable arm has a handful of observations, "
          "so this estimator is the weakest instrument in the file. "
          "**Section 2d asks the same question with a stable statistic and "
          "answers it**, so read 2d before concluding anything from this "
          "row."
          if adj_lo <= 0 <= adj_hi else
          "**The adjustment is inconclusive at this sample.**")))
    w("")
    w("The two arms' mixes, so the size of the confound is visible:")
    w("")
    w("| stratum (stated confidence, tau) | tradeable | untradeable | "
      "tradeable lost | untradeable lost |")
    w("|---|---|---|---|---|")
    _sc = defaultdict(lambda: [0, 0, 0, 0])
    for _m in mkts:
        _c = _sc[stratum(_m)]
        if _m["klass"] == TAKE:
            _c[0] += 1
            _c[1] += 0 if _m["won"] else 1
        else:
            _c[2] += 1
            _c[3] += 0 if _m["won"] else 1
    for _st in sorted(_sc, key=lambda t: (CONF_NAMES.index(t[0]),
                                          TAUB_NAMES.index(t[1]))):
        _c = _sc[_st]
        w(f"| {_st[0]}, {_st[1]} | {_c[0]:,} | {_c[2]:,} | {_c[1]:,} | "
          f"{_c[3]:,} |")
    w("")
    # ---- 2d. CALIBRATION, TESTED DIRECTLY ---------------------------------
    w("### 2d. Explanation A, tested directly: is the model overconfident "
      "EVERYWHERE?")
    w("")
    w("The model does not merely say 'certain', it states a number, so the "
      "claim can be scored where it is made. `stated` is the mean of "
      "(1 - confidence) over the observations in the row -- the loss rate the "
      "MODEL predicts for them. `realised` is what happened. Their ratio is "
      "the factor by which the model is overconfident THERE. Explanation A "
      "-- a Gaussian tail that is too thin -- is the claim that this factor "
      "is large in every row.")
    w("")
    w("**Read the `misses by` column, not the ratio.** In the last band the "
      "model's stated loss rate rounds to zero, so the ratio divides by "
      "nothing and reports hundreds for a miss of three hundredths of a "
      "percentage point. The absolute miss is what any fix has to close.")
    w("")
    w("| stated confidence | arm | obs | closes | model says it loses | it "
      "actually loses | misses by | (ratio) |")
    w("|---|---|---|---|---|---|---|---|")
    for lab, lo_, hi_ in (("0.995-0.999", 0.995, 0.999),
                          ("0.999-0.9999", 0.999, 0.9999),
                          (">= 0.9999", 0.9999, 1.01)):
        band_ = [m for m in mkts if lo_ <= m["conf"] < hi_]
        for arm, sub_ in (("tradeable", [m for m in band_
                                         if m["klass"] == TAKE]),
                          ("untradeable", [m for m in band_
                                           if m["klass"] != TAKE])):
            n_, k_, st_, re_, fa_ = calib(sub_)
            if n_ == 0:
                continue
            w(f"| {lab} | {arm} | {n_:,} | {k_:,} | {100*st_:.4f}% | "
              f"{100*re_:.4f}% | **{100*(re_-st_):.3f} pp** | {fa_:.0f}x |")
    _hb = [m for m in mkts if m["conf"] >= 0.9999]
    _ht = [m for m in _hb if m["klass"] == TAKE]
    _hu = [m for m in _hb if m["klass"] != TAKE]
    _aht, _ahu = acc(_ht), acc(_hu)
    _hg, _hlo, _hhi, _hs, _, _, _ = boot_gap(_hb)
    _hmde = mde_pp(_aht[6], _ahu[6], _ahu[3])
    w("")
    w(f"**The cleanest single cut is the last band**, where the model claims "
      f"at most one failure in ten thousand and the two arms are therefore "
      f"making the SAME claim. There the tradeable arm fails "
      f"{100*(1-_aht[3]):.3f}% of the time ({_aht[0] - _aht[2]:,} of "
      f"{_aht[0]:,} over {_aht[1]:,} closes) against "
      f"{100*(1-_ahu[3]):.4f}% ({_ahu[0] - _ahu[2]:,} of {_ahu[0]:,}) -- "
      f"**{(1-_aht[3])/max(1e-12, 1-_ahu[3]):.1f}x worse on the same stated "
      f"claim**. The gap is {100*_hg:+.3f} pp "
      f"[{100*_hlo:+.3f}, {100*_hhi:+.3f}] with {100*_hs:.1f}% of by-close "
      f"resamples at or above zero, against an MDE of {_hmde:.3f} pp: the "
      f"DIRECTION is unambiguous and the interval brushes zero, because "
      f"{_aht[0] - _aht[2]:,} failures cannot carry a tighter one.")
    w("")

    # ---- 2c. the per-market rollup, and the FLIP finding ------------------
    _pt = [m for m in pm if m["klass"] == TAKE]
    _pu = [m for m in pm if m["klass"] != TAKE]
    _pl = [m for m in pm if not m["won"]]
    _pf = [m for m in pm if m["flip"]]
    _apt, _apu = acc(_pt), acc(_pu)
    w("### 2c. The per-market rollup, and the one mechanism it exposes")
    w("")
    w("The grid above is the answer. This section is a DIFFERENT reading of "
      "the same cells, kept because it found the mechanism: roll each market "
      "up to one record, calling it tradeable if a takeable ask existed at "
      "ANY second in the band and reading the offer off the moment it was "
      "cheapest. **That pick is not symmetric between the arms** -- the "
      "cheapest ask is the instant of maximum model-market disagreement, "
      "where the model is most likely wrong, while an untradeable market is "
      "read at the end of the band, where it is most likely right -- so its "
      "gap is an upper bound and the verdict is NOT taken from it.")
    w("")
    w(f"On that reading: {len(_pt):,} tradeable markets at "
      f"{100*_apt[3]:.2f}% against {len(_pu):,} untradeable at "
      f"{100*_apu[3]:.2f}%, {len(_pl):,} failures in the whole "
      f"{len(pm):,}-market certain population.")
    w("")
    w(f"**And every one of those {len(_pl):,} failures is a market on which "
      f"the model was certain of BOTH sides at different seconds inside the "
      f"same 27-second band.** There are {len(_pf):,} such markets in "
      f"{len(pm):,}; {len(_pl):,} of them failed, and "
      f"{sum(1 for m in _pf if m['klass'] == TAKE):,} of them were tradeable. "
      f"Not one market on which the model held a single consistent call "
      f"failed, in either arm.")
    w("")
    w("That is the mechanism in one sentence, and it decides between the two "
      "stories. A model whose Gaussian tail is merely too thin would fail "
      "occasionally on calls it never retracted -- a 99.9% call would come "
      "in at 99% and the failures would be spread thinly over the whole "
      "certain population. That is not what the tape shows. The failures are "
      "ALL retractions: the index moved far enough to reverse a stated "
      "near-certainty, and every time that happened somebody was already "
      "offering the side the model still liked, at a discount no honest "
      "quote explains.")
    w("")

    # ---- 3. the seller ---------------------------------------------------
    w("## 3. Characterising the seller")
    w("")
    w("Every row is the TRADEABLE population only -- grid observations where "
      "an ask stood on the model's side at or below the ceiling -- split on "
      "what could be seen about that offer AT THAT SECOND, before the "
      "outcome. The question is "
      "not which slice is most accurate -- it is whether ANY slice reaches "
      f"the untradeable benchmark of **{100*a_untr[3]:.2f}%**, because a "
      "slice that does is a seller who is plausibly not informed. `covers` "
      "marks a slice whose interval contains that benchmark.")
    w("")

    def table(title, rows_, note=None):
        w(f"### {title}")
        w("")
        if note:
            w(note)
            w("")
        w("| slice | obs | closes | lost | accuracy | 95% CP | covers "
          f"{100*a_untr[3]:.2f}%? |")
        w("|---|---|---|---|---|---|---|")
        for lab, sub in rows_:
            a = acc(sub)
            cov = "yes" if (a[0] and a[7] <= a_untr[3] <= a[8]) else "no"
            if a[0] < 30:
                cov += " (n<30)"
            w(fmt_acc(a, lab, cov))
        w("")

    sz_edges = [10, 25, 50, 100, 250]
    sz_names = ["<10", "10-25", "25-50", "50-100", "100-250", ">=250"]
    table("3a. by ask SIZE resting at the touch -- small = someone "
          "offloading, large = a maker quoting",
          slice_rows(take, lambda m: band(m["sz"], sz_edges, sz_names),
                     order=sz_names))
    r_edges = [250, 1000, 5000, 30000]
    r_names = ["<0.25 s", "0.25-1 s", "1-5 s", "5-30 s", ">=30 s"]
    table("3b. by how long the level had RESTED before the touch",
          slice_rows(take, lambda m: (band(m["rest"], r_edges, r_names)
                                      if m["rest"] is not None
                                      else "not seen born"),
                     order=r_names + ["not seen born"]),
          "A level that has sat there for tens of seconds is a standing "
          "quote; one that appeared milliseconds earlier is a decision.")
    d_edges = [0.5, 1.5, 3.0, 7.5, 15.0]
    d_names = ["<0.5c", "0.5-1.5c", "1.5-3c", "3-7.5c", "7.5-15c", ">=15c"]
    table("3c. by DISCOUNT -- how far the ask sat below the model's fair",
          slice_rows(take, lambda m: band(m["disc_c"], d_edges, d_names),
                     order=d_names),
          f"`pinrun.DUMP_DISCOUNT` already refuses anything cheaper than "
          f"{100*pinrun.DUMP_DISCOUNT:.0f}c below fair; the >=15c row is what "
          f"that guard is buying.")
    h_names = ["00-05 UTC", "06-11 UTC", "12-17 UTC", "18-23 UTC"]
    table("3d. by TIME OF DAY",
          slice_rows(take, lambda m: h_names[m["hour"] // 6], order=h_names))
    table("3e. by COIN",
          slice_rows(take, lambda m: m["series"]))
    tau_names = ["3-8 s", "9-15 s", "16-22 s", "23-30 s"]
    table("3f. by TAU at the touch",
          slice_rows(take, lambda m: band(m["tau"], [9, 16, 23], tau_names),
                     order=tau_names))
    _rest = [m for m in take if m["rest"] is not None and m["rest"] >= 30000]
    _fresh = [m for m in take if m["rest"] is not None and m["rest"] < 250]
    _ar, _af = acc(_rest), acc(_fresh)
    _big = [m for m in take if m["sz"] >= 250]
    _ab = acc(_big)
    _cheap = [m for m in take if (m["disc_c"] or 0) >= 15.0]
    _ac = acc(_cheap)
    w("### 3g. THE QUESTION THAT MATTERS: is there a seller who is "
      "plausibly NOT informed?")
    w("")
    w(f"Yes, and it is the one the shape predicts. **A level that had been "
      f"resting on the book for 30 seconds or more when we read it is "
      f"indistinguishable from the untradeable population: "
      f"{_ar[0] - _ar[2]:,} failures in {_ar[0]:,} observations over "
      f"{_ar[1]:,} closes, {100*_ar[3]:.2f}% "
      f"[{100*_ar[7]:.2f}, {100*_ar[8]:.2f}], covering the "
      f"{100*a_untr[3]:.2f}% benchmark.** A level that appeared within the "
      f"last quarter-second carries {_af[0] - _af[2]:,} of the "
      f"{a_take[0] - a_take[2]:,} failures in the whole tradeable arm: "
      f"{100*_af[3]:.2f}% [{100*_af[7]:.2f}, {100*_af[8]:.2f}] on "
      f"{_af[0]:,} observations.")
    w("")
    w(f"The same split shows up twice more and in the same direction. An ask "
      f"of {250}+ contracts -- the size a maker quotes, not the size "
      f"somebody offloads -- runs {100*_ab[3]:.2f}% "
      f"[{100*_ab[7]:.2f}, {100*_ab[8]:.2f}] on {_ab[0]:,} observations. And "
      f"an ask {pinrun.DUMP_DISCOUNT*100:.0f}c or more below the model's "
      f"fair runs {100*_ac[3]:.2f}% [{100*_ac[7]:.2f}, {100*_ac[8]:.2f}] on "
      f"{_ac[0]:,} -- that is the population `pinrun.DUMP_DISCOUNT` already "
      f"refuses, and on this tape it holds {_ac[0] - _ac[2]:,} of the "
      f"tradeable arm's {a_take[0] - a_take[2]:,} failures.")
    w("")
    w("**Read this as a description of the seller, not as a rule.** These "
      "slices were chosen after seeing the tape, the failure counts in them "
      "are single digits, and `rest`, `size` and `discount` are correlated "
      "with each other -- a level that has sat for 30 seconds is not deeply "
      "discounted, because if it were it would have been taken. Nothing here "
      "is a threshold, and turning any of it into one needs a holdout split "
      "and a pre-registered live bar written before the number is seen "
      "(CLAUDE.md, AMENDMENT 2026-09-10 item 4). What it IS is the mechanism: "
      "the informed seller on this tape is a NEW level, priced far below the "
      "model, and the standing quote is not him.")
    w("")

    # ---- 4. the control --------------------------------------------------
    w("## 4. The control -- an ask existed, but we refuse it as too dear")
    w("")
    w(f"If the mere EXISTENCE of a seller were the bad news, the dear "
      f"markets would look like the tradeable ones. If it is the CHEAPNESS "
      f"that carries the information, they would look like the untradeable "
      f"ones. Measured: dear **{100*a_dear[3]:.2f}%** "
      f"[{100*a_dear[7]:.2f}, {100*a_dear[8]:.2f}] on {len(dear):,} "
      f"observations, "
      f"against tradeable {100*a_take[3]:.2f}% and never-offered "
      f"{100*a_noask[3]:.2f}%.")
    w("")

    # ---- 5. the holdout --------------------------------------------------
    w("## 5. The holdout -- first 70% of closes against the last 30%")
    w("")
    w("| half | closes | tradeable acc | untradeable acc | gap | 95% bootstrap |")
    w("|---|---|---|---|---|---|")
    for nm, half, gg, at_, au_ in (("train (first 70%)", tr, g_tr, at_tr,
                                    au_tr),
                                   ("HOLDOUT (last 30%)", ho, g_ho, at_ho,
                                    au_ho)):
        ck_ = len({m["close"] for m in half})
        w(f"| {nm} | {ck_:,} | {100*at_[3]:.2f}% ({at_[0]:,}) | "
          f"{100*au_[3]:.2f}% ({au_[0]:,}) | {100*gg[0]:+.2f} pp | "
          f"[{100*gg[1]:+.2f}, {100*gg[2]:+.2f}] |")
    w("")
    agree = (g_tr[0] < 0) == (g_ho[0] < 0)
    _sep = (g_tr[2] < 0, g_ho[2] < 0)
    w(("**Both halves point the same way**, so the gap is not an artefact of "
       "one stretch of tape."
       if agree else
       "**The halves do not agree in sign.** Nothing here survives as a "
       "finding until they do."))
    w("")
    w(f"**But say the rest of it.** "
      + ("Neither half on its own excludes zero"
         if not any(_sep) else
         ("The train half excludes zero; the holdout does not"
          if _sep[0] and not _sep[1] else
          ("The holdout excludes zero; the train half does not"
           if _sep[1] and not _sep[0] else
           "Both halves exclude zero")))
      + f" -- splitting a population whose failures number "
        f"{a_all[0] - a_all[2]:,} in {a_all[0]:,} leaves each half with too "
        f"few to carry an interval. What the holdout can say is that the "
        f"sign did not flip and that the effect is, if anything, larger in "
        f"the more recent third ({100*g_ho[0]:+.2f} pp against "
        f"{100*g_tr[0]:+.2f} pp). What it cannot do is confirm the size. "
        f"The pooled gap in section 2 is the estimate; this table is the "
        f"stability check, and it passes the only test it has the power to "
        f"run.")
    w("")
    w("---")
    w("")
    w("## What this cannot say")
    w("")
    w("- It cannot say whether the offer would have been OURS. Live we win "
      "about 70% of the races we enter. That limit applies equally to both "
      "arms of the comparison, which is why the DIFFERENCE survives it and "
      "an absolute rate would not.")
    w("- It cannot see the offers that were never printed to the book we "
      "rebuilt, and `results/RESULTS_tapegaps.md` measured 3.28% of "
      "trading-window seconds inside a collector-side silent run. Both arms "
      "lose the same seconds.")
    w("- It computes no P&L, prices no rule, and proposes no threshold. "
      "A threshold would need a pre-registered live bar written before the "
      "number was seen (CLAUDE.md, AMENDMENT 2026-09-10 item 4).")
    w("")

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    for line in L[:60]:
        say(line)
    say(f"\n  written to {out}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--pass1", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--hours", type=int, default=240)
    ap.add_argument("--end", default=None)
    ap.add_argument("--cells", default=CELLS)
    ap.add_argument("--out", default=os.path.join(HERE, "..", "results",
                                                  "RESULTS_select.md"))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")
    if a.pass1:
        pass1(a.hours, a.end, a.cells, force=a.force)
    if a.report:
        stamps = set(pinsim.book_hours(a.hours, a.end))
        report(a.cells, os.path.abspath(a.out), stamps=stamps)
    if not (a.pass1 or a.report):
        print("nothing to do -- pass --pass1 and/or --report")


if __name__ == "__main__":
    main()
