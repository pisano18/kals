#!/usr/bin/env python3
# VERSION: 2026-09-08-pxr1
"""pinexit_run.py -- the real-data half of pinexit.py.

Kept in its own file so that `python research/pinexit.py --selftest` imports
nothing that reads C:\\kals, and so main() cannot run at all unless the
self-test in pinexit.py has already passed.

It answers, in order:

  1. Does the replay reproduce rows.jsonl exactly? (28,479 of 28,479 or stop.)
  2. What is the MDE, before any estimate is printed?
  3. Separation by SECOND AFTER ENTRY  -- the operator's question.
  4. Separation by TAU                 -- the executable question.
  5. When does the projected settlement actually CROSS the strike?
  6. For each candidate alarm: how often it fires on a loser, how often on a
     winner, how many seconds are left when it fires, and whether it fires
     BEFORE or AFTER the cross -- with the hedge price the market is showing at
     that exact instant, in cents and in WINS TO RECOVER.
  7. Tonight's loss, second by second, with every alarm evaluated.
"""
import argparse
import array
import glob
import gzip
import json
import math
import os
import pickle
import sys
import time
import zlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gzsalvage                                                # noqa: E402
import pinexit as PX                                            # noqa: E402
from pinexit import (FEATS, SHORT, NICE, IndexTape, state, p_lose, our_mid,
                     walk, table, auc, mde_auc, eff_strike,
                     SERIES_TO_INDEX, ROUND_DIGITS, MIN_CLUSTERS, USABLE_TAU,
                     ClusterAUC)                                # noqa: E402
from engine import N_AVG                                        # noqa: E402

DATA = PX.DATA
FULLTAPE = PX.FULLTAPE
ROWS = PX.ROWS
WORK = PX.WORK

# the pin rule, as frozen in pinrun.py
PIN_P = 0.02
CEILING = 0.988
EV_FLOOR = 0.003
MEASURED_FLIP = 0.0090
HEDGE_LAG = 1          # seconds between seeing the alarm and buying the hedge


def fee(p, n=1):
    return math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000


def ev(p):
    return (1 - MEASURED_FLIP) * (1 - p) - MEASURED_FLIP * p - fee(p)


def other_ask(row, our_yes):
    """What we must PAY to buy the side we did NOT buy (pinhedge.hedge_price)."""
    px = float(row["price"])
    sp = float(row.get("spread") or 0.0)
    if bool(row["side_yes"]) != bool(our_yes):
        return px
    return 1.0 - (px - sp)


# ===========================================================================
def load_index_cache(lo_h, hi_h, path):
    if os.path.exists(path):
        with open(path, "rb") as fh:
            return pickle.load(fh)
    want = set(SERIES_TO_INDEX.values())
    raw = defaultdict(dict)
    s = lo_h
    files = 0
    while s <= hi_h:
        st = time.strftime("%Y%m%dT%H", time.gmtime(s))
        f = os.path.join(DATA, "cfbenchmarks_value", st + ".jsonl.gz")
        s += 3600
        if not os.path.exists(f):
            print(f"    MISSING index hour {st}")
            continue
        files += 1
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    if '"cfbenchmarks_value"' not in line:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                        iid = m["index_id"]
                        if iid not in want:
                            continue
                        dd = json.loads(m["data"])
                        raw[iid][int(dd["time"]) // 1000] = float(dd["value"])
                    except Exception:
                        continue
        except (EOFError, zlib.error, OSError) as e:
            print(f"    truncated index hour {st}: {e}")
    out = {}
    for iid, d in raw.items():
        lo, hi = min(d), max(d)
        a = array.array("d", [float("nan")] * (hi - lo + 1))
        for sec, v in d.items():
            a[sec - lo] = v
        out[iid] = (lo, a)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump(out, fh, 4)
    print(f"    built index cache from {files} hours -> {path}")
    return out


def load_rows(path, tau_lo, tau_hi):
    by = defaultdict(dict)
    n = 0
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            n += 1
            by[(r["tk"], r["close"])][r["sec"]] = r
    return by, n


# ===========================================================================
def verify(by, tapes, mk):
    """Reproduce every stored mu/req from the raw index tape. Stop on any miss."""
    bad = unres = ok = 0
    worst = 0.0
    for (tk, close), secs in by.items():
        m = mk.get(tk)
        if m is None:
            unres += len(secs)
            continue
        tp = tapes.get(SERIES_TO_INDEX[m["series"]])
        if tp is None:
            unres += len(secs)
            continue
        K = eff_strike(m["strike"], ROUND_DIGITS[m["series"]])
        for sec, r in secs.items():
            st = state(tp, close, sec, K)
            if st is None:
                unres += 1
                continue
            d1 = abs(st["mu"] - r["mu"]) / max(abs(r["mu"]), 1e-30)
            d2 = abs(st["req"] - r["req"]) / max(abs(r["req"]), 1e-30)
            sg1, sg2 = st["sig"], r["sig"]
            if sg1 is None or sg2 is None:
                d3 = 0.0 if (sg1 is None and sg2 is None) else 1.0
            else:
                d3 = abs(sg1 - sg2) / max(abs(sg2), 1e-30)
            # mu and required_move are summed exactly as pindata sums them,
            # in the same order, so they must agree BIT FOR BIT -- the test is
            # d > 0.0, not a tolerance. sigma is a difference of two whole-tape
            # prefix sums of squared 1 s moves, so it agrees to a few parts in
            # 1e9 rather than exactly. sigma enters only through
            # z = (K - mu) / (sigma * sqrt(880)), so a 3e-9 relative wobble in
            # it moves z by 3e-9 of a standard deviation and cannot change a
            # reported digit. That is stated rather than hidden.
            if d1 > 0.0 or d2 > 0.0 or d3 > 1e-6:
                bad += 1
                if bad <= 3:
                    print(f"      MISMATCH {tk} tau {r['tau']}: "
                          f"mu rel {d1:.3e} req rel {d2:.3e} sig rel {d3:.3e}")
            else:
                ok += 1
            worst = max(worst, max(d1, d2, d3))
    return ok, bad, unres, worst


# ===========================================================================
def build_entries(by, tapes, mk, tau_lo, tau_hi, gated, first_only,
                  min_tau=0, entry_p=None):
    """One entry per (market, second) at which we could have bought."""
    ents = []
    for (tk, close), secs in by.items():
        m = mk.get(tk)
        if m is None:
            continue
        tp = tapes.get(SERIES_TO_INDEX[m["series"]])
        if tp is None:
            continue
        K = eff_strike(m["strike"], ROUND_DIGITS[m["series"]])
        cand = sorted(secs.values(), key=lambda x: -x["tau"])
        for r in cand:
            if not (tau_lo <= r["tau"] <= tau_hi):
                continue
            if r["tau"] < min_tau:
                continue
            if gated or entry_p is not None:
                st = state(tp, close, r["sec"], K)
                pf = p_lose(st, K, bool(r["side_yes"]))
                cap = PIN_P if gated else entry_p
                if pf is None or pf > cap:
                    continue
                if gated and (r["price"] > CEILING
                              or ev(r["price"]) < EV_FLOOR):
                    continue
            ents.append((tk, close, K, tp, r["sec"], bool(r["side_yes"]),
                         bool(r["flip"]), float(r["price"]), secs,
                         m["series"]))
            if first_only:
                break
    return ents


def paths_of(ents, kmax):
    for (tk, close, K, tp, sec, yes, lose, price, secs, sr) in ents:
        cells = list(walk(tp, close, K, yes, sec, secs, kmax))
        if cells:
            yield (close, lose, cells)


# ===========================================================================
ALARMS = [
    ("p_gain", [0.01, 0.05, 0.10, 0.25, 0.50]),
    ("sd_loss", [0.5, 1.0, 1.5, 2.0, 3.0]),
    ("p_model", [0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 0.90]),
    ("p_mkt", [0.05, 0.10, 0.20, 0.35, 0.50]),
    ("mkt_lead", [0.02, 0.05, 0.10, 0.20, 0.35]),
    ("diverge", [0.02, 0.05, 0.10, 0.20]),
    ("rv_ratio", [1.5, 2.0, 3.0]),
    ("neg_cush_sd", [-3.0, -2.0, -1.5, -1.0, -0.5, 0.0]),
    ("neg_reqmv_bp", [-20.0, -10.0, -5.0, -2.0, 0.0]),
]


def pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[max(0, min(len(xs) - 1, int(q * len(xs))))]



def ledger(rows, ents, typical_win):
    """THE OPERATOR'S TABLE. Everything in WINS TO RECOVER, not in cents.

    The operator's objective is not expected value: "losing small amounts of
    money (maybe 1-5 wins worth) a bit more frequently is better than one huge
    loss that takes tens to a hundred wins to earn back." So each rule is
    scored on the shape of its loss distribution, not only its mean:

      worst      the single worst trade the rule leaves on the table
      p99 / p95  the 1-in-100 and 1-in-20 bad trade
      total      the whole population's P&L, which is where the false alarms
                 show up -- a rule that removes the tail by taxing every
                 winner will look wonderful in the first three columns and
                 terrible here

    A HEDGE IS NOT INSURANCE, and the arithmetic says so: holding both sides of
    a Kalshi binary pays exactly $1.00, so buying the other side does not
    reduce a risk, it ENDS the trade at a known price. Hedging a winner turns
    a win into a certain small loss. That is the tax, and it is in `total`.

    UPPER BOUND, stated once and meant: every hedge here is assumed to fill in
    full at the displayed ask. IDEAS_LOG #32 measured that only 6 of 12 were
    deep enough at size 20. So the saving is an upper bound and the false-alarm
    cost is NOT -- the tax is paid whether or not the hedge is deep.
    """
    base = []
    for (tk, close, K, tp, sec0, yes, lose, price, secs, sr) in ents:
        if price is None:
            continue
        base.append(((-price) if lose else (1.0 - price)) - fee(price))
    if not base:
        return
    bs = sorted(base)
    n = len(bs)

    def wins(c):
        return c / typical_win

    print("\n" + "=" * 78)
    print("  THE OPERATOR'S TABLE -- EVERYTHING IN WINS TO RECOVER")
    print("=" * 78)
    print(f"  one typical win = {100 * typical_win:.2f}c per contract, so "
          f"'wins' below means")
    print(f"  'how many winning trades of that size it takes to get it back'.")
    print(f"  n = {n:,} trades. Negative = a loss. `total` is the whole")
    print(f"  population, so the false-alarm tax is fully inside it.")
    hdr = (f"  {'rule':>26}{'hedged%':>9}{'worst':>9}{'p99':>8}{'p95':>8}"
           f"{'mean':>9}{'total':>11}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    print(f"  {'NO HEDGE (what we do now)':>26}{'-':>9}"
          f"{wins(bs[0]):>9.1f}{wins(bs[int(0.01 * n)]):>8.1f}"
          f"{wins(bs[int(0.05 * n)]):>8.1f}"
          f"{wins(sum(bs) / n):>9.2f}{wins(sum(bs)):>11.1f}")
    for r in rows:
        pn = r["pnl"]
        if len(pn) < n * 0.9:
            continue
        ps = sorted(pn)
        m = len(ps)
        hd = (r["fl"] + r["fw"]) / max(r["nl"] + r["nw"], 1)
        print(f"  {r['feat'] + ' >= ' + str(r['th']):>26}{100 * hd:>8.1f}%"
              f"{wins(ps[0]):>9.1f}{wins(ps[int(0.01 * m)]):>8.1f}"
              f"{wins(ps[int(0.05 * m)]):>8.1f}"
              f"{wins(sum(ps) / m):>9.2f}{wins(sum(ps)):>11.1f}")
    print("\n  hedged% = share of ALL trades the rule hedges, winners included.")
    print("  A rule beats 'no hedge' on this operator's objective only if it")
    print("  lifts `worst` (and p99) a long way WITHOUT collapsing `total`.")


def placebo(ents, seed=4242):
    """Move the LOSER labels to different markets, keeping everything else.

    The self-test proves the estimator finds nothing in a synthetic null. This
    proves it on the REAL tape: the same paths, the same clustering, the same
    number of losing markets, but the label moved to markets that did not lose.
    Every column of every table must come back at 0.500 and every alarm must
    fire on losers and winners at the same rate. Labels move at the MARKET
    level, never per entry, because a market's ~15 entries share one outcome
    and permuting them separately would destroy exactly the correlation that
    makes the real table hard to read.
    """
    import random as _r
    keys = []
    lab = {}
    for e in ents:
        k = (e[0], e[1])
        if k not in lab:
            lab[k] = e[6]
            keys.append(k)
    vals = [lab[k] for k in keys]
    _r.Random(seed).shuffle(vals)
    newlab = dict(zip(keys, vals))
    out = []
    for e in ents:
        e = list(e)
        e[6] = newlab[(e[0], e[1])]
        out.append(tuple(e))
    return out


def crossings(cr):
    """The crossing timeline, reported PER MARKET.

    One losing market contributes up to 58 entries, so a per-entry percentile
    is really a per-market percentile weighted by how many seconds happened to
    qualify -- which over-weights exactly the markets that stayed qualifying
    longest. Every figure below is per market, and the per-entry count is
    printed beside it so the difference is visible rather than assumed.
    """
    print("\n  WHEN DOES mu -- the projected settlement -- CROSS THE STRIKE?")
    print("  Reported PER MARKET. `final cross` is the tau at which mu went to")
    print("  the wrong side and never came back; `warning` is how many seconds")
    print("  passed between our entry and that crossing.")
    for grp in ("loser", "winner"):
        v = cr[grp]
        bym = {}
        for x in v:
            key = x[4]
            # keep the EARLIEST entry for each market, which is the one whose
            # "seconds from entry to the cross" is longest and therefore the
            # most favourable to the idea being tested
            if key not in bym or x[5] < bym[key][5]:
                bym[key] = x
        w = list(bym.values())
        finals = [x[1] for x in w if x[1] is not None]
        firsts = [x[0] for x in w if x[0] is not None]
        never = sum(1 for x in w if x[0] is None)
        print(f"\n  {grp.upper()}S: {len(w):,} markets ({len(v):,} entries)")
        print(f"    mu NEVER crossed:   {never:,} "
              f"({100 * never / max(len(w), 1):.1f}%)")
        if finals:
            print(f"    tau of FINAL cross: p10 {pct(finals, 0.10)}  "
                  f"p25 {pct(finals, 0.25)}  MEDIAN {pct(finals, 0.5)}  "
                  f"p75 {pct(finals, 0.75)}  p90 {pct(finals, 0.90)}")
        if firsts:
            print(f"    tau of FIRST cross: p10 {pct(firsts, 0.10)}  "
                  f"p25 {pct(firsts, 0.25)}  MEDIAN {pct(firsts, 0.5)}  "
                  f"p75 {pct(firsts, 0.75)}  p90 {pct(firsts, 0.90)}")


def analyse(ents, kmax, nbins=128):
    """ONE walk per entry, feeding the separation tables, the crossing
    timeline and every alarm at once."""
    from pinexit import FEATS as _F
    byk = {f: defaultdict(lambda: ClusterAUC(nbins)) for f in _F}
    bytau = {f: defaultdict(lambda: ClusterAUC(nbins)) for f in _F}
    ak = defaultdict(lambda: [0, 0])
    at = defaultdict(lambda: [0, 0])
    cross = {"loser": [], "winner": []}
    al = {}
    for feat, ths in ALARMS:
        for th in ths:
            al[(feat, th)] = {"nl": 0, "nw": 0, "fl": 0, "fw": 0,
                              "taus": [], "lead": [], "usable": 0,
                              "hedge": [], "hloss": [],
                              "whedge": [], "pnl": [], "nofill": 0,
                              "depth": []}
    done = 0
    for (tk, close, K, tp, sec0, yes, lose, price, secs, sr) in ents:
        cells = list(walk(tp, close, K, yes, sec0, secs, kmax))
        done += 1
        if not cells:
            continue
        li = 1 if lose else 0
        for k, tau, f in cells:
            ak[k][li] += 1
            at[tau][li] += 1
            for name in _F:
                v = f.get(name)
                if v is None:
                    continue
                byk[name][k].add(v, lose, close)
                bytau[name][tau].add(v, lose, close)
        # ---- the crossing timeline --------------------------------------
        first = None
        tau_pnr = None
        for k, tau, f in cells:
            if f["_cush"] <= 0 and first is None:
                first = tau
            if f["_cush"] > 0:
                tau_pnr = tau
        final = None
        for k, tau, f in reversed(cells):
            if f["_cush"] > 0:
                break
            final = tau
        cross["loser" if lose else "winner"].append(
            (first, final, tau_pnr, cells[-1][1], (tk, close), sec0))
        # ---- every alarm -------------------------------------------------
        for feat, ths in ALARMS:
            for th in ths:
                d = al[(feat, th)]
                if lose:
                    d["nl"] += 1
                else:
                    d["nw"] += 1
                fire = None
                for k, tau, f in cells:
                    v = f.get(feat)
                    if v is not None and v >= th:
                        fire = (k, tau)
                        break
                base = None
                if price is not None:
                    base = ((-price) if lose else (1.0 - price)) - fee(price)
                if fire is None:
                    if base is not None:
                        d["pnl"].append(base)
                    continue
                k, tau = fire
                if lose:
                    d["fl"] += 1
                    d["taus"].append(tau)
                    if tau >= USABLE_TAU:
                        d["usable"] += 1
                    if tau_pnr is not None:
                        d["lead"].append(tau - tau_pnr)
                else:
                    d["fw"] += 1
                # ---- THE LOOK-AHEAD THIS NEARLY WALKED INTO ----------
                # The alarm is computed from the index print for second s.
                # rows.jsonl stores the book at the FIRST orderbook delta of
                # second s, which can be milliseconds after s.000 -- i.e.
                # BEFORE the market has seen the print that fired our alarm.
                # Pricing the hedge there buys at the pre-news price and would
                # have made every rule below look free. HEDGE_LAG seconds are
                # added, so the hedge is bought from a book strictly later
                # than the information that triggered it. LAG=0 is available
                # only to show how much the bug was worth.
                q = None
                for lag in range(HEDGE_LAG, HEDGE_LAG + 3):
                    row = secs.get(close - tau + lag)
                    if row is None:
                        continue
                    qq = other_ask(row, yes)
                    if 0.0 < qq < 1.0:
                        q = qq
                        # the size that could actually fill the hedge is the
                        # size resting on the side we are buying INTO, which
                        # rows.jsonl records only when the model has already
                        # switched to that side. IDEAS_LOG #32 measured only
                        # 6 of 12 hedges deep enough at size 20, so a ledger
                        # that assumes a full fill is an UPPER bound and is
                        # labelled as one.
                        if bool(row["side_yes"]) != bool(yes):
                            d["depth"].append(float(row.get("size") or 0.0))
                        break
                if q is None:
                    d["nofill"] += 1
                    if base is not None:
                        d["pnl"].append(base)
                    continue
                if price is not None:
                    h = (1.0 - price - q) - fee(price) - fee(q)
                    d["pnl"].append(h)
                    if lose:
                        d["hedge"].append(q)
                        d["hloss"].append(h)
                    else:
                        d["whedge"].append(q)
    rows = []
    for (feat, th), d in al.items():
        if d["nl"] == 0:
            continue
        rows.append({
            "feat": feat, "th": th, "nl": d["nl"], "nw": d["nw"],
            "fl": d["fl"], "fw": d["fw"],
            "rate_l": d["fl"] / d["nl"],
            "rate_w": d["fw"] / d["nw"] if d["nw"] else 0.0,
            "tau_med": pct(d["taus"], 0.5),
            "usable": d["usable"] / d["fl"] if d["fl"] else 0.0,
            "lead_med": pct(d["lead"], 0.5),
            "lead_pos": (sum(1 for x in d["lead"] if x > 0) / len(d["lead"]))
            if d["lead"] else None,
            "hedge_med": pct(d["hedge"], 0.5),
            "hloss_med": pct(d["hloss"], 0.5),
            "nhedge": len(d["hedge"]),
            "whedge_med": pct(d["whedge"], 0.5),
            "pnl": d["pnl"], "nofill": d["nofill"],
            "depth_med": pct(d["depth"], 0.5),
            "depth_n": len(d["depth"])})
    order = {f: i for i, (f, _t) in enumerate(ALARMS)}
    rows.sort(key=lambda r: (order[r["feat"]], r["th"]))
    return byk, bytau, ak, at, cross, rows



# ===========================================================================
# THE LARGE COMPANION: index-only, no order book required
# ===========================================================================
"""Why this exists, and what it can and cannot say.

rows.jsonl holds one row per moment where somebody was ACTUALLY OFFERING the
model-favoured side. That is the right population for "what would we have paid",
and it is the only population where a real trade existed -- but in 44 hours it
contains just 10 closes in which a trade our own rule would take went on to
lose. Ten clusters is a third of this project's floor of 30, so nothing about
timing can be claimed from it alone.

This companion drops the order-book requirement. It asks the settlement model at
every second of every settled market, takes every moment the model was at least
98% sure, and follows those to settlement. The population is much larger and
covers many more closes.

WHAT IT CANNOT SAY, STATED FIRST. pindata.py's own docstring makes the point:
scoring all the moments the model feels certain gives a flip rate near 0.01%;
scoring the moments somebody actually offered us the winning side cheap gives
0.90% -- ninety times worse, because a near-certainty is only sold cheaply when
the seller may know something. So this companion MUST NOT be used to estimate
how often we lose, or what a hedge is worth. It is used for one thing only:
CONDITIONAL ON A MODEL-CERTAIN POSITION LOSING, WHAT DOES THE INDEX PATH DO, AND
WHEN? That is a question about the shape of a loss, and the index path does not
know whether a maker happened to be quoting.

It also carries no market columns at all -- no book, so no p_mkt, no mkt_lead,
no divergence. Those stay with the 44-hour book dataset and its 10 closes.
"""


def load_index_span(lo_h, hi_h, path):
    """Index arrays built straight into fixed-size buffers -- no intermediate
    dict, because 150 hours x 9 indices of Python dict entries is about a
    gigabyte and there is a live trader on this box."""
    if os.path.exists(path):
        with open(path, "rb") as fh:
            return pickle.load(fh)
    want = list(SERIES_TO_INDEX.values())
    n = hi_h + 3600 - lo_h
    arrs = {iid: array.array("d", [float("nan")] * n) for iid in want}
    ws = set(want)
    files = miss = salvfail = 0
    s = lo_h
    while s < hi_h + 3600:
        st = time.strftime("%Y%m%dT%H", time.gmtime(s))
        f = os.path.join(DATA, "cfbenchmarks_value", st + ".jsonl.gz")
        s += 3600
        if not os.path.exists(f):
            miss += 1
            continue
        files += 1
        # gzsalvage, not gzip.open: the collector appends a second gzip member
        # behind an untrailered first one whenever the watchdog restarts it
        # inside a UTC hour, and the plain reader then recovers ZERO lines from
        # that file, not half of them. Eleven of 151 index hours were lost that
        # way on the first pass here, which is 6.1% of the tape thrown out
        # silently -- exactly the failure gzsalvage.py was written for.
        try:
            for line in gzsalvage.iter_lines(f):
                if '"cfbenchmarks_value"' not in line:
                    continue
                try:
                    m = json.loads(line)["msg"]
                    iid = m["index_id"]
                    if iid not in ws:
                        continue
                    dd = json.loads(m["data"])
                    i = int(dd["time"]) // 1000 - lo_h
                    if 0 <= i < n:
                        arrs[iid][i] = float(dd["value"])
                except Exception:
                    continue
        except Exception as e:
            salvfail += 1
            print(f"    unreadable index hour {st}: {e}")
    out = {iid: (lo_h, a) for iid, a in arrs.items()}
    with open(path, "wb") as fh:
        pickle.dump(out, fh, 4)
    print(f"    index span: {files} hours read, {miss} missing, "
          f"{salvfail} unreadable even after salvage -> {path}")
    return out


def index_only(a):
    print("\n" + "=" * 78)
    print("  THE LARGE COMPANION -- index only, no order book required")
    print("=" * 78)
    cap = a.entry_p if a.entry_p is not None else PIN_P
    print(f"  Population: every second of every settled market at which the")
    print(f"  settlement model was at least {100 * (1 - cap):.0f}% sure,")
    print(f"  followed to settlement. NO book, so no market-implied columns.")
    print(f"  This CANNOT say how often we lose -- the population that is")
    print(f"  actually OFFERED to us is about 90x worse. It is here only to")
    print(f"  say, CONDITIONAL ON LOSING, when the index gives it away.")

    hi_h = (int(time.time()) // 3600) * 3600 - 2 * 3600
    lo_h = hi_h - a.hours * 3600
    cache = os.path.join(WORK, "pinexit_idxspan_%d.pkl" % a.hours)
    idx = load_index_span(lo_h, hi_h, cache)
    tapes = {}
    for k, v in idx.items():
        nn = sum(1 for x in v[1] if x == x)
        if nn > 1000:
            tapes[k] = IndexTape(*v)
            print(f"    {k:<12} {nn:,} of {len(v[1]):,} prints "
                  f"({100 * nn / len(v[1]):.1f}%)")
    del idx

    mk = []
    for v in json.load(open(FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] not in SERIES_TO_INDEX:
                continue
            cs = int(float(r["close"]))
            if lo_h + 400 <= cs <= hi_h + 3600:
                mk.append(r)
    print(f"    {len(mk):,} settled markets inside that span")

    ents = []
    for r in mk:
        tp = tapes.get(SERIES_TO_INDEX[r["series"]])
        if tp is None:
            continue
        close = int(float(r["close"]))
        K = eff_strike(r["strike"], ROUND_DIGITS[r["series"]])
        won_yes = float(r["result"]) >= 0.5
        for tau in range(a.tau_hi, a.tau_lo - 1, -1):
            sec = close - tau
            st = state(tp, close, sec, K)
            if st is None or st["sig"] is None:
                continue
            yes = st["req"] <= 0
            pf = p_lose(st, K, yes)
            if pf is None or pf > cap:
                continue
            ents.append((r["ticker"], close, K, tp, sec, yes,
                         (yes != won_yes), None, {}, r["series"]))
    if a.placebo:
        ents = placebo(ents)
        print("\n  *** PLACEBO: the loser labels have been moved to other")
        print("  *** markets. Everything below must read 0.500 and every")
        print("  *** alarm must fire equally on both groups.")
    nl = sum(1 for e in ents if e[6])
    ncl = len({e[1] for e in ents})
    lcl = len({e[1] for e in ents if e[6]})
    lmk = len({(e[0], e[1]) for e in ents if e[6]})
    print(f"\n  POPULATION: {len(ents):,} entries, {nl:,} losers over "
          f"{lcl} LOSING CLOSES ({lmk} losing markets) out of {ncl} closes")
    if lcl < MIN_CLUSTERS:
        print(f"  *** {lcl} losing closes is below the floor of "
              f"{MIN_CLUSTERS}. Point estimates only, no significance claim.")
    else:
        print(f"  {lcl} losing closes CLEARS the floor of {MIN_CLUSTERS}.")
    if nl == 0:
        print("  nothing to measure.")
        return

    fl = mde_auc(nl, len(ents) - nl)
    print(f"\n  MDE, BEFORE THE ESTIMATE: {fl:.4f} on |AUC - 0.500| treating")
    print(f"  rows as independent; the measured design effect restates it.")

    kmax = a.kmax
    print("\n  replaying ...", flush=True)
    t0 = time.time()
    byk, bytau, ak, at, cr, rows = analyse(ents, kmax)
    print(f"    {time.time() - t0:.0f}s")

    c0 = byk["p_model"][0]
    plo, phi = c0.ci(draws=a.draws, seed=77)
    if plo is not None and c0.npos() and c0.n() - c0.npos():
        se_b = (phi - plo) / 3.92
        se_i = math.sqrt((c0.n() + 1.0) /
                         (12.0 * c0.npos() * (c0.n() - c0.npos())))
        infl = se_b / se_i if se_i > 0 else None
        if infl:
            print(f"    measured design effect {infl:.1f}x -> real MDE "
                  f"{mde_auc(nl, len(ents) - nl, infl):.4f}")

    print("\n  SEPARATION BY SECOND AFTER ENTRY (index signals only)")
    table(byk, ak, [k for k in range(0, min(kmax, 40) + 1)], "k")
    print("\n  SEPARATION BY TAU (seconds LEFT)")
    table(bytau, at, list(range(a.tau_hi, a.tau_lo - 1, -1)), "tau")

    crossings(cr)

    print("\n  ALARMS (index-only ones; the book alarms need the book)")
    hdr = ("  %26s%9s%9s%8s%9s%7s%10s%8s"
           % ("alarm", "fires%L", "fires%W", "W/L", "tau med", ">=3s",
              "lead med", "lead>0"))
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for r in rows:
        if r["feat"] in ("p_mkt", "mkt_lead", "diverge"):
            continue
        wl = (r["fw"] / r["fl"]) if r["fl"] else float("inf")
        lp = ("%.0f%%" % (100 * r["lead_pos"])) if r["lead_pos"] is not None \
            else "."
        print("  %26s%8.1f%%%8.1f%%%8.1f%9s%6.0f%%%10s%8s" % (
            r["feat"] + " >= " + str(r["th"]), 100 * r["rate_l"],
            100 * r["rate_w"], wl,
            r["tau_med"] if r["tau_med"] is not None else ".",
            100 * r["usable"],
            r["lead_med"] if r["lead_med"] is not None else ".", lp))


# ===========================================================================
def loss_night(args):
    """Tonight's loss, second by second, with every alarm evaluated."""
    TK = "KXNEAR15M-26SEP082045-45"
    CLOSE = 1788914700
    IID = "NEARUSD_RTI"
    K = 2.34915
    BUYS = [(22, 0.962, 20), (21, 0.956, 20), (17, 0.730, 19)]
    print("\n" + "=" * 78)
    print("  TONIGHT'S LOSS, SECOND BY SECOND")
    print("=" * 78)
    print(f"  {TK}   close {CLOSE}   K_eff {K}")
    print(f"  bought NO at tau 22 (96.2c x20), tau 21 (95.6c x20), "
          f"tau 17 (73.0c x19)")

    cache = os.path.join(WORK, "pinexit_idx_loss.pkl")
    idx = load_index_cache(CLOSE - 3 * 3600, CLOSE + 3600, cache)
    if IID not in idx:
        print("  *** the index tape does not carry NEARUSD_RTI for that hour.")
        return
    base, arr = idx[IID]
    tape = IndexTape(base, arr)

    # rebuild the book for this one market, with the CORRECT snapshot keys
    book = rebuild_book(TK, CLOSE)
    if book is None:
        print("  (order book could not be rebuilt; market columns blank)")
        book = {}

    print()
    hdr = (f"  {'tau':>4}{'spot':>11}{'mu':>11}{'mu-K':>10}{'cushSD':>8}"
           f"{'reqMV':>10}{'p_model':>9}{'p_mkt':>8}{'diverg':>8}"
           f"{'rvrat':>7}{'otherAsk':>9}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    entry_sec = CLOSE - 22
    ent = state(tape, CLOSE, entry_sec, K)
    sig0 = ent["sig"] if ent else None
    fires = {}
    for sec in range(CLOSE - 40, CLOSE):
        st = state(tape, CLOSE, sec, K)
        if st is None:
            continue
        tau = CLOSE - sec
        cush = -(st["mu"] - K)                       # we hold NO
        cush_sd = cush / st["sd"] if st["sd"] else None
        reqmv = st["req"]                            # >0 = must rise vs us
        pm = p_lose(st, K, False)
        bb = book.get(sec)
        pmkt = oa = None
        if bb:
            yb, nb = bb
            if yb is not None and nb is not None:
                # we hold NO: our ask = 1 - yb, our bid = nb
                pmkt = 1.0 - (nb + (1.0 - yb)) / 2.0
                oa = 1.0 - nb                        # ask to buy YES
        rv = tape.rms(entry_sec, sec, need=3) if sec - entry_sec >= 3 else None
        rvr = (rv / sig0) if (rv and sig0) else None
        mark = ""
        if tau == 22 or tau == 21 or tau == 17:
            mark = "  <-- BUY"
        print(f"  {tau:>4}{st['spot']:>11.5f}{st['mu']:>11.5f}"
              f"{st['mu'] - K:>10.5f}"
              f"{(f'{cush_sd:.2f}' if cush_sd is not None else '.'):>8}"
              f"{reqmv:>10.5f}{pm:>9.4f}"
              f"{(f'{pmkt:.4f}' if pmkt is not None else '.'):>8}"
              f"{(f'{pm - pmkt:+.4f}' if pmkt is not None else '.'):>8}"
              f"{(f'{rvr:.2f}' if rvr is not None else '.'):>7}"
              f"{(f'{oa:.4f}' if oa is not None else '.'):>9}{mark}")
        if sec >= entry_sec:
            for feat, ths in ALARMS:
                v = {"p_model": pm, "p_mkt": pmkt,
                     "mkt_lead": (pmkt - pm) if pmkt is not None else None,
                     "diverge": (pm - pmkt) if pmkt is not None else None,
                     "rv_ratio": rvr,
                     "neg_cush_sd": (-cush_sd) if cush_sd is not None else None,
                     "neg_reqmv_bp": -1e4 * reqmv / st["spot"]}.get(feat)
                if v is None:
                    continue
                for th in ths:
                    if v >= th and (feat, th) not in fires:
                        fires[(feat, th)] = tau

    print("\n  WHEN EACH ALARM WOULD HAVE FIRED (tau = seconds left)")
    print(f"  {'alarm':>28}{'fires at tau':>14}{'time to act?':>14}")
    for feat, ths in ALARMS:
        for th in ths:
            t = fires.get((feat, th))
            if t is None:
                s = "never"
                act = "-"
            else:
                s = str(t)
                act = "YES" if t >= USABLE_TAU else f"NO ({t}s)"
            print(f"  {feat + ' >= ' + str(th):>28}{s:>14}{act:>14}")


def rebuild_book(ticker, close_s):
    """Rebuild one market's top of book per second, using the CORRECT keys.

    SKIM.md item 5: pindata.Book.snapshot() reads `yes_dollars`/`no_dollars`,
    but the tape writes `yes_dollars_fp`/`no_dollars_fp`, so every book in
    rows.jsonl is delta-only. This function reads the _fp keys, and main()
    prints how far the two disagree so the size of that bug is a measured
    number rather than an assumption.
    """
    stamp = time.strftime("%Y%m%dT%H", time.gmtime(close_s))
    prev = time.strftime("%Y%m%dT%H", time.gmtime(close_s - 3600))
    yes, no = {}, {}
    seen = {}
    tk = f'"{ticker}"'
    for st in (prev, stamp):
        sf = os.path.join(DATA, "orderbook_snapshot", st + ".jsonl.gz")
        if os.path.exists(sf):
            try:
                with gzip.open(sf, "rt") as fh:
                    for line in fh:
                        if ticker not in line:
                            continue
                        m = json.loads(line).get("msg", {})
                        if m.get("market_ticker") != ticker:
                            continue
                        yes.clear()
                        no.clear()
                        for key, d in (("yes_dollars_fp", yes),
                                       ("no_dollars_fp", no)):
                            for pr, q in (m.get(key) or []):
                                q = float(q)
                                if q > 0:
                                    d[round(float(pr), 4)] = q
            except (EOFError, zlib.error, OSError):
                pass
        df = os.path.join(DATA, "orderbook_delta", st + ".jsonl.gz")
        if not os.path.exists(df):
            continue
        try:
            with gzip.open(df, "rt") as fh:
                for line in fh:
                    if tk not in line:
                        continue
                    m = json.loads(line).get("msg", {})
                    if m.get("market_ticker") != ticker:
                        continue
                    d = yes if str(m.get("side", "")).lower() == "yes" else no
                    p = round(float(m.get("price_dollars")), 4)
                    q = d.get(p, 0.0) + float(m.get("delta_fp") or 0.0)
                    if q <= 1e-9:
                        d.pop(p, None)
                    else:
                        d[p] = q
                    sec = int(m.get("ts_ms") or 0) // 1000
                    seen[sec] = (max(yes) if yes else None,
                                 max(no) if no else None)
        except (EOFError, zlib.error, OSError):
            pass
    if not seen:
        return None
    # forward-fill: the book persists between messages
    out = {}
    last = None
    for sec in range(min(seen), close_s + 1):
        if sec in seen:
            last = seen[sec]
        if last is not None:
            out[sec] = last
    return out


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", default=ROWS)
    ap.add_argument("--tau-lo", type=int, default=3)
    ap.add_argument("--tau-hi", type=int, default=60)
    ap.add_argument("--kmax", type=int, default=57)
    ap.add_argument("--gated", action="store_true",
                    help="restrict to entries the live pin rule would take")
    ap.add_argument("--first-only", action="store_true",
                    help="one entry per market, at the earliest tradeable sec")
    ap.add_argument("--cohort-tau", type=int, default=0,
                    help="only entries with tau >= this, to hold the surviving "
                         "pool fixed across seconds-after-entry")
    ap.add_argument("--entry-p", type=float, default=None,
                    help="only entries whose model p(lose) at entry is <= this "
                         "-- the population that LOOKED SAFE when we bought")
    ap.add_argument("--hedge-lag", type=int, default=1,
                    help="seconds between the alarm and the book we buy the "
                         "hedge from; 0 reproduces the look-ahead")
    ap.add_argument("--draws", type=int, default=200)
    ap.add_argument("--loss-only", action="store_true")
    ap.add_argument("--index-only", action="store_true",
                    help="the large companion: no order book required")
    ap.add_argument("--hours", type=int, default=150)
    ap.add_argument("--placebo", action="store_true",
                    help="move the loser labels to other markets: every table "
                         "must then come back empty")
    a = ap.parse_args()

    print("=" * 78)
    print("  pinexit -- after we bought, when does a loser look different?")
    print("=" * 78)
    globals()["HEDGE_LAG"] = a.hedge_lag
    print(f"  hedge bought from the book {a.hedge_lag} s AFTER the alarm "
          f"(0 = look-ahead)")

    if a.loss_only:
        loss_night(a)
        return
    if a.index_only:
        index_only(a)
        return

    by, nrows = load_rows(a.rows, a.tau_lo, a.tau_hi)
    lo = min(min(s.keys()) for s in by.values())
    hi = max(max(s.keys()) for s in by.values())
    print(f"\n  rows.jsonl: {nrows:,} rows, {len(by):,} markets, "
          f"{len({k[1] for k in by}):,} closes")
    print(f"  span {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(lo))} .. "
          f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(hi))}")

    cache = os.path.join(WORK, "pinexit_idx_wide.pkl")
    idx = load_index_cache(lo - 400, hi + 120, cache)
    tapes = {k: IndexTape(*v) for k, v in idx.items()}
    print(f"  index tape: {len(tapes)} indices")

    mk = {}
    for v in json.load(open(FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] in SERIES_TO_INDEX:
                mk[r["ticker"]] = r

    print("\n  STEP 1 -- does the replay reproduce the dataset it is extending?")
    ok, bad, unres, worst = verify(by, tapes, mk)
    print(f"    mu, req and sigma reproduced on {ok:,} of {ok + bad:,} rows; "
          f"{bad:,} mismatches, {unres:,} unresolvable")
    print(f"    worst relative disagreement on any of the three: "
          f"{worst:.3e}")
    if bad:
        raise SystemExit("  *** replay does not reproduce rows.jsonl. STOP.")

    ents = build_entries(by, tapes, mk, a.tau_lo, a.tau_hi, a.gated,
                         a.first_only, a.cohort_tau, a.entry_p)
    if a.placebo:
        ents = placebo(ents)
        print("\n  *** PLACEBO: the loser labels have been moved to other")
        print("  *** markets. Everything below must read 0.500 and every")
        print("  *** alarm must fire equally on both groups.")
    nl = sum(1 for e in ents if e[6])
    ncl = len({e[1] for e in ents})
    lose_cl = len({e[1] for e in ents if e[6]})
    print(f"\n  POPULATION: {len(ents):,} entries, {nl:,} losers, "
          f"{ncl} closes ({lose_cl} of them contain a loser)")
    if ncl < MIN_CLUSTERS:
        print(f"  *** only {ncl} closes -- below the floor of {MIN_CLUSTERS}. "
              f"No significance will be claimed.")

    wins = [1.0 - e[7] - fee(e[7]) for e in ents if not e[6]]
    typical_win = sum(wins) / len(wins) if wins else 0.05
    losses = [e[7] + fee(e[7]) for e in ents if e[6]]
    typical_loss = sum(losses) / len(losses) if losses else 0.95
    print(f"  a typical WIN in this population is "
          f"{100 * typical_win:.2f}c per contract; a typical LOSS is "
          f"{100 * typical_loss:.2f}c")
    print(f"  so ONE LOSS COSTS {typical_loss / typical_win:.1f} WINS "
          f"to recover, at the same size. That ratio is the whole problem.")

    print(f"\n  STEP 2 -- THE MDE, STATED BEFORE ANY ESTIMATE")
    if nl == 0:
        print("    *** ZERO LOSERS in this population. There is nothing to")
        print("    *** separate, the MDE is undefined, and no exit rule can be")
        print("    *** scored here at all. That is a RESULT, not a failure: it")
        print("    *** means the 44 hours of order-book tape contain not one")
        print("    *** losing trade of the shape we actually take, so the PRICE")
        print("    *** of a hedge at the alarm can only be measured on a window")
        print("    *** wider than the one we trade.")
        loss_night(a)
        return
    fl = mde_auc(nl, len(ents) - nl)
    print(f"    treating rows as independent, the smallest |AUC - 0.500| a")
    print(f"    95% two-sided test could find at 80% power is {fl:.4f}.")
    print(f"    Rows are NOT independent (one market contributes ~40")
    print(f"    consecutive seconds; nine coins share a close), so that is a")
    print(f"    FLOOR. The design effect is measured below from the")
    print(f"    close-clustered bootstrap at k = 0 and the MDE restated.")

    kmax = a.kmax
    print("\n  replaying paths ...", flush=True)
    t0 = time.time()
    byk, bytau, ak, at, cr, rows = analyse(ents, kmax)
    print(f"    {time.time() - t0:.0f}s")

    # ---- measured design effect ----------------------------------------
    c0 = byk["p_model"][0]
    plo, phi = c0.ci(draws=a.draws, seed=101)
    if plo is not None:
        se_boot = (phi - plo) / 3.92
        se_ind = math.sqrt((c0.npos() + (c0.n() - c0.npos()) + 1.0) /
                           (12.0 * c0.npos() * (c0.n() - c0.npos())))
        infl = se_boot / se_ind if se_ind > 0 else None
        print(f"\n    MEASURED design effect at k=0: the close-clustered SE is")
        print(f"    {infl:.1f}x the independent-rows SE, so the real MDE on")
        print(f"    |AUC - 0.500| is {mde_auc(nl, len(ents) - nl, infl):.4f}, "
              f"not {fl:.4f}.")
        mde = mde_auc(nl, len(ents) - nl, infl)
    else:
        mde = fl
        infl = None

    print("\n" + "=" * 78)
    print("  STEP 3 -- SEPARATION BY SECOND AFTER ENTRY  (the operator's")
    print("  question: after we bought, when did it start looking different?)")
    print("  AUC 0.500 = a loser and a winner are indistinguishable.")
    print(f"  Anything within {mde:.3f} of 0.500 is inside the MDE.")
    print("=" * 78)
    keys = [k for k in range(0, kmax + 1) if k <= 40]
    t_k = table(byk, ak, keys, "k")

    print("\n" + "=" * 78)
    print("  STEP 4 -- SEPARATION BY TAU (seconds LEFT). This is the one that")
    print("  decides whether a signal is actionable: a hedge needs >= 3 s.")
    print("=" * 78)
    t_t = table(bytau, at, list(range(a.tau_hi, a.tau_lo - 1, -1)), "tau")

    # ---- CIs on the leading signals -------------------------------------
    print("\n  CLOSE-CLUSTERED 95% CIs on the two leading signals")
    print(f"  {'signal':>14}{'k':>5}{'AUC':>9}{'95% CI':>20}")
    for f in ("p_model", "neg_cush_sd", "p_mkt", "mkt_lead"):
        for k in (0, 3, 5, 10, 15, 20, 30):
            c = byk[f].get(k)
            if c is None or not c.npos():
                continue
            g = c.point()
            l2, h2 = c.ci(draws=a.draws, seed=200 + k)
            print(f"  {SHORT[f]:>14}{k:>5}{g:>9.3f}"
                  f"{f'[{l2:.3f}, {h2:.3f}]':>20}")

    # ---- crossings -------------------------------------------------------
    print("\n" + "=" * 78)
    print("  STEP 5 -- WHEN DOES THE PROJECTED SETTLEMENT ACTUALLY CROSS?")
    print("  mu is the model's projected settlement. While mu is on our side")
    print("  we are winning on paper. `final cross` is the tau at which mu")
    print("  went to the wrong side and never came back.")
    print("=" * 78)
    for grp in ("loser", "winner"):
        v = cr[grp]
        firsts = [x[0] for x in v if x[0] is not None]
        finals = [x[1] for x in v if x[1] is not None]
        never = sum(1 for x in v if x[0] is None)
        print(f"\n  {grp.upper()}S  n = {len(v):,}")
        print(f"    mu never crossed at all:            "
              f"{never:,} ({100 * never / max(len(v), 1):.1f}%)")
        if finals:
            print(f"    tau of the FINAL crossing:          "
                  f"p25 {pct(finals, 0.25)}  median {pct(finals, 0.5)}  "
                  f"p75 {pct(finals, 0.75)}   max {max(finals)}")
        if firsts:
            print(f"    tau of the FIRST (maybe transient): "
                  f"p25 {pct(firsts, 0.25)}  median {pct(firsts, 0.5)}  "
                  f"p75 {pct(firsts, 0.75)}   max {max(firsts)}")

    # ---- alarms ----------------------------------------------------------
    print("\n" + "=" * 78)
    print("  STEP 6 -- EVERY CANDIDATE ALARM: does it fire in time, and is")
    print("  the hedge still cheap when it does?")
    print("  'lead' = seconds between the alarm and mu's final crossing.")
    print("  A POSITIVE lead is a warning. Zero or negative is a report.")
    print("=" * 78)
    hdr = (f"  {'alarm':>26}{'fires%L':>9}{'fires%W':>9}{'W/L':>7}"
           f"{'tau med':>9}{'>=3s':>7}{'lead med':>10}{'lead>0':>8}"
           f"{'hedge':>8}{'hedgeW':>8}{'locked':>9}{'wins':>7}{'depth':>8}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for r in rows:
        wl = (r["fw"] / r["fl"]) if r["fl"] else float("inf")
        hm = r["hedge_med"]
        hl = r["hloss_med"]
        wins_rec = (-hl / typical_win) if hl is not None else None
        print(f"  {r['feat'] + ' >= ' + str(r['th']):>26}"
              f"{100 * r['rate_l']:>8.1f}%{100 * r['rate_w']:>8.1f}%"
              f"{wl:>7.1f}"
              f"{(r['tau_med'] if r['tau_med'] is not None else '.'):>9}"
              f"{100 * r['usable']:>6.0f}%"
              f"{(r['lead_med'] if r['lead_med'] is not None else '.'):>10}"
              f"{(f'{100 * r['lead_pos']:.0f}%' if r['lead_pos'] is not None else '.'):>8}"
              f"{(f'{100 * hm:.1f}c' if hm is not None else '.'):>8}"
              f"{(f'{100 * r['whedge_med']:.1f}c' if r['whedge_med'] is not None else '.'):>8}"
              f"{(f'{100 * hl:+.1f}c' if hl is not None else '.'):>9}"
              f"{(f'{wins_rec:.1f}' if wins_rec is not None else '.'):>7}"
              f"{(f'{r['depth_med']:.0f}' if r['depth_med'] is not None else '.'):>8}")
    print("\n  fires%L / fires%W = share of LOSERS / WINNERS the alarm fires on.")
    print("  W/L = winners hedged per loser caught (the false-alarm price).")
    print("  hedge = median ask on the OTHER side at the instant it fires.")
    print("  locked = the P&L that hedge locks in, entry + hedge - $1.00 - fees.")
    print("  wins = how many typical wins that locked loss still costs.")

    ledger(rows, ents, typical_win)

    loss_night(a)


if __name__ == "__main__":
    if not PX.selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")
    main()
