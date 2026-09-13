#!/usr/bin/env python3
# VERSION: 2026-09-13-pc1
"""pincontest.py -- DID ANYONE ELSE WANT THE OFFER WE WOULD HAVE TAKEN?

THE QUESTION, AND WHY IT IS THE MOST VALUABLE ONE OPEN
------------------------------------------------------
CURRENT_STATE.md: "The loss rate itself. Everything hinges on it. Keep
counting." Break-even is a 3.58% close-loss rate; the current version is 2.86%
on 35 closes and all live history is 4.84% on 248. The two straddle break-even
and counting live closes to separate them takes months, because a loss is a
2-3% event and the interval on 35 closes is [0.07, 14.92].

CLAUDE.md's 2026-09-10 rule 5 forbids the obvious shortcut -- the tape may
never be quoted for OUR loss rate -- and gives the reason, which is a
POPULATION mismatch, not a replay bug:

    the tape's population is "an offer was sitting there",
    ours is "someone actively sold it to us",
    and only the second is adversely selected.

That is a statement about a missing filter, and a missing filter is a thing one
can go and build. THIS FILE BUILDS IT. The `trade` channel records every
execution on the exchange with a millisecond stamp and the taker's side, so for
any offer the gate would have hit we can ask a question the book alone cannot
answer: did anybody else take this offer, and how fast?

That splits the tape's tradeable population in two:

    CONTESTED -- another taker bought the same side at our price or dearer,
                 within delta of the moment we would have hit it. Somebody
                 else wanted it. Live we win about 72% of such races
                 (pinver: fill ratio 71.8%), so some of these would be ours.
    CLEAR     -- nobody took it. The offer sat there, for us alone.

NEITHER ARM IS OUR LOSS RATE AND NEITHER MAY EVER BE QUOTED AS ONE. Rule 5 is
not amended by this file and cannot be. What this file may do, and all it may
do, is compare two TAPE populations with each other -- exactly as pinselect.py
compares tradeable with untradeable -- and then report whether the
CONTESTED/CLEAR split moves the tape's failure rate toward the live one. If it
does, the project has a large-n instrument for the number everything hinges
on. If it does not, the instrument is dead and we keep counting live.

WHY THE ANSWER IS NOT OBVIOUS IN EITHER DIRECTION
-------------------------------------------------
Both stories are coherent, which is what makes the measurement worth its cost:

  CLEAR IS POISON. A seller who posts at 96c on the side the model is certain
  about is either slow or informed. If they are slow, every other fast taker on
  the exchange is racing us for it, and the offer is CONTESTED. If they are
  informed -- they have seen an index print we have not -- the other fast
  takers see what the seller sees and stand aside, and the offer is CLEAR and
  ours. Under this story losing 28% of our races is not a cost, it is a FREE
  FILTER, and the fills we win uncontested are the ones that kill us.

  CLEAR IS FINE. Contest measures only how attractive a price is. The
  deepest-discount offers draw the most takers AND are the most likely to be
  real mispricings, so contest and safety rise together, and the 28% of races
  we lose are the best trades on the tape. Under this story the money is in
  racing harder -- section 5 prices exactly that.

The two make opposite trading recommendations from the same data, so the
measurement pays whichever way it lands.

CONFOUNDS, AND WHAT IS DONE ABOUT THEM
--------------------------------------
1. ATTRACTIVENESS. Contest is not assigned at random: cheap offers on
   near-certain sides draw takers. So every gap is also reported STANDARDISED
   on the (stated confidence x tau) grid pinselect already uses, and
   --selftest plants a world where contest and outcome are BOTH driven by the
   stratum and requires the standardised estimator to return zero there while
   the crude gap still fires.
2. OUR OWN FILLS. From 2026-09-07 the bot is live and its own executions are in
   the trade tape. A trade of ours would mark its own offer CONTESTED, by us.
   Every filled order and hedge record in results/pinrun-live-*.jsonl is
   matched and dropped, and the count dropped is printed.
3. CLUSTERING. Twelve series settle on one second at rho ~ 0.8 (hard rule 4).
   Intervals are Clopper-Pearson on cluster-deflated counts and every gap
   carries a by-CLOSE block bootstrap. n is reported as rows AND closes.
4. POWER BEFORE ESTIMATE. The MDE is printed above the table. "No effect" and
   "no power" are different results.
5. A GUARD THAT DISCARDS DATA NEEDS ITS OWN NULL. Section 5 prints what share
   of rows, contracts and dollars each arm holds, so a rule built on this split
   is costed before it is believed.

WHAT IT READS
-------------
results/pinlevels_rows.jsonl -- the candidate offers the gate would have taken,
already cached over 422 book hours (2026-08-25 .. 2026-09-12), each with its
price, depth, ladder, stated confidence, tau and settled outcome. Re-using that
cache is what makes this a two-minute job instead of a 100-minute tape walk.
Plus the raw trade/ channel, streamed with a cheap string prefilter and never
held whole.
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
from pincross import cp_interval                              # noqa: E402
from pinselect import icc_deff, mde_pp                        # noqa: E402
import gzsalvage                                              # noqa: E402
import pinrun                                                 # noqa: E402

REPO = os.path.dirname(HERE)
ROWS_DEFAULT = os.path.join(REPO, "results", "pinlevels_rows.jsonl")
LIVE_GLOB_DEFAULT = os.path.join(REPO, "results", "pinrun-live-*.jsonl")
OUT_DEFAULT = os.path.join(REPO, "results", "RESULTS_contest.md")

PRE_S = 60          # trades kept this many seconds before each quarter hour
POST_S = 3          # ... and this many after it
DELTAS_MS = (250, 1000, 5000, 60000)
PRIMARY_DELTA = 1000
PRICE_EPS = 1e-9
OWN_WINDOW_MS = 4000     # a trade this close in time to one of our fills,
OWN_PRICE_EPS = 0.006    # this close in price, same market and side, is ours

CONTESTED, CLEAR = "contested", "clear"


# ---------------------------------------------------------------------------
# 1. THE CANDIDATE OFFERS
# ---------------------------------------------------------------------------
def load_rows(path):
    """The offers the gate would have hit, from pinlevels' cache.

    One row is one (market, second) at which pinrun's own decision said trade.
    `won` is whether the side it wanted settled correct -- NOT whether we
    traded, and NOT our P&L.
    """
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("kind") != "row":
                continue
            try:
                out.append({
                    "ticker": d["ticker"],
                    "coin": d.get("coin", ""),
                    "close": int(d["cs"]),
                    "tau": int(d["tau"]),
                    "entry_ms": int(d["entry_ts"]),
                    "want": d["want"],
                    "price": float(d["price"]),
                    "depth": float(d.get("depth", 0.0)),
                    "ladder": d.get("ladder") or [],
                    "conf": float(d.get("conf", 0.0)),
                    "discount_c": float(d.get("discount_c", 0.0)),
                    "fair": float(d.get("fair", 0.0)),
                    "verdict": d.get("verdict", "trade"),
                    "fired": list(d.get("fired") or []),
                    "won": bool(d["won"]),
                })
            except (KeyError, TypeError, ValueError):
                continue
    return out


def gate(rows, how, ceiling=0.98, min_depth=20.0):
    """Cut the cached candidates down to the population the LIVE bot trades.

    THIS IS NOT COSMETIC AND THE FIRST RUN OF THIS FILE PROVED IT. pinlevels
    caches every candidate the model calls certain, including the ones
    `pinrun`'s dump guard REFUSES -- offers at 2c on a side the model says is
    certain. There are 2,699 of them, they lose 77% of the time at the cheap
    end, and nobody takes them, so they land in the CLEAR arm en masse and
    manufacture a gap out of a population the bot never trades.

      all   -- everything cached (what the first run used, and why it was wrong)
      trade -- pinlevels' own verdict: the profile rules did not refuse it
      live  -- and inside the deployed ceiling, with depth a real fill needs
    """
    if how == "all":
        return list(rows)
    out = [r for r in rows if r.get("verdict") == "trade"]
    if how == "trade":
        return out
    return [r for r in out
            if r["price"] <= ceiling + PRICE_EPS and r["depth"] >= min_depth]


def hour_stamps(rows, pre_s=PRE_S, post_s=POST_S):
    """Hour stamps whose trade file could hold a trade in any row's window."""
    st = set()
    for r in rows:
        a = r["entry_ms"] // 1000 - pre_s
        b = r["close"] + post_s
        t = a - (a % 3600)
        while t <= b:
            st.add(time.strftime("%Y%m%dT%H", time.gmtime(t)))
            t += 3600
    return st


# ---------------------------------------------------------------------------
# 2. THE TRADE TAPE -- streamed, prefiltered on a string, never held whole
# ---------------------------------------------------------------------------
def _num(line, key):
    """Read a numeric JSON value, quoted or bare, without parsing the object.

    The trade channel is 3.2 GB gzipped. Parsing every line to throw 95% of
    them away costs about 20x what this does, and the 95% is thrown away on a
    timestamp that is always present. `key` is the bare field name in quotes,
    with no colon: whitespace after the colon is legal JSON and the collector
    is not the only thing that ever writes these files (--selftest writes one
    with json.dumps, which spaces them).
    """
    i = line.find(key)
    if i < 0:
        return None
    i += len(key)
    n = len(line)
    while i < n and line[i] in ' 	:"':
        i += 1
    j = i
    while j < n and line[j] not in ',}"':
        j += 1
    try:
        return float(line[i:j])
    except ValueError:
        return None


def _str(line, key):
    """The string value of `key`, same tolerance as _num."""
    i = line.find(key)
    if i < 0:
        return None
    i += len(key)
    n = len(line)
    while i < n and line[i] in ' 	:':
        i += 1
    if i < n and line[i] == '"':
        i += 1
    j = line.find('"', i)
    return line[i:j] if j > 0 else None


def trade_files(data_dir, stamps):
    out = []
    for st in sorted(stamps):
        p = os.path.join(data_dir, "trade", st + ".jsonl.gz")
        if os.path.exists(p):
            out.append(p)
    return out


def scan_trades(data_dir, stamps, tickers, pre_s=PRE_S, post_s=POST_S,
                say=print):
    """ticker -> [(ts_ms, yes_px, no_px, count, taker_outcome_side)], sorted.

    Only trades inside a quarter hour's last `pre_s` seconds (or first
    `post_s`) are kept, and only for markets that carry a candidate row.
    """
    out = defaultdict(list)
    files = trade_files(data_dir, stamps)
    kept = seen = 0
    gz_stats = {}
    for k, path in enumerate(files):
        # A restart inside a UTC hour leaves two gzip members and the standard
        # reader recovers ZERO lines from such a file -- not the second half,
        # everything (gzsalvage.py's docstring). Nine hours of this tape are
        # like that, so the salvaging reader is not optional here.
        if True:
            for line in gzsalvage.iter_lines(path, stats=gz_stats):
                seen += 1
                ts_ms = _num(line, '"ts_ms"')
                if ts_ms is None:
                    continue
                off = (int(ts_ms) // 1000) % 900
                if off < 900 - pre_s and off > post_s:
                    continue
                tk = _str(line, '"market_ticker"')
                if tk is None or tk not in tickers:
                    continue
                y = _num(line, '"yes_price_dollars"')
                if y is None:
                    y = _num(line, '"yes_price"')
                nn = _num(line, '"no_price_dollars"')
                if nn is None:
                    nn = _num(line, '"no_price"')
                c = _num(line, '"count_fp"')
                if c is None:
                    c = _num(line, '"count"')
                side = _str(line, '"taker_outcome_side"')
                if side is None:
                    side = _str(line, '"taker_side"')
                if y is None or side is None:
                    continue
                if nn is None:
                    nn = 1.0 - y
                out[tk].append((int(ts_ms), y, nn, float(c or 0.0), side))
                kept += 1
        if say and (k + 1) % 100 == 0:
            say("    ...%d/%d trade hours, %d kept of %d lines"
                % (k + 1, len(files), kept, seen))
    for tk in out:
        out[tk].sort()
    if say:
        say("    trade tape: %d files, %d lines read, %d trades kept on %d "
            "markets%s" % (len(files), seen, kept, len(out),
                           ("; %d files salvaged"
                            % gz_stats.get("salvaged_files", 0))
                           if gz_stats.get("salvaged_files") else ""))
    return dict(out), seen, kept


def own_fills(live_glob):
    """(ticker, ts_ms, price, side) for every order of OURS that filled.

    Confound 2. Our own executions sit in the same tape and would mark the very
    offers we hit as CONTESTED -- by us.
    """
    out = []
    for path in sorted(glob.glob(live_glob)):
        try:
            fh = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                k = d.get("kind")
                if k not in ("order", "hedge"):
                    continue
                filled = d.get("filled", d.get("n"))
                if not filled:
                    continue
                px = d.get("exec_price", d.get("price"))
                tk = d.get("ticker")
                ts = d.get("t")
                if px is None or tk is None or not ts:
                    continue
                ms = iso_ms(ts)
                if ms is None:
                    continue
                side = d.get("want", d.get("side", "yes"))
                out.append((tk, ms, float(px), side))
    return out


def iso_ms(ts):
    """UTC ISO stamp -> epoch ms. The repo is UTC everywhere inside; only the
    operator-facing text is ET (CLAUDE.md, standing 2026-09-12)."""
    try:
        st = time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return None
    return int(calendar_timegm(st)) * 1000


def calendar_timegm(st):
    import calendar
    return calendar.timegm(st)


def drop_own(trades, own):
    """Remove our own executions from the tape. Returns (trades, n_dropped)."""
    if not own:
        return trades, 0
    by = defaultdict(list)
    for tk, ms, px, side in own:
        by[tk].append((ms, px, side))
    dropped = 0
    for tk, lst in list(trades.items()):
        mine = by.get(tk)
        if not mine:
            continue
        keep = []
        for tr in lst:
            ts_ms, y, nn, c, side = tr
            px = y if side == "yes" else nn
            hit = False
            for oms, opx, oside in mine:
                if (abs(ts_ms - oms) <= OWN_WINDOW_MS and side == oside
                        and abs(px - opx) <= OWN_PRICE_EPS):
                    hit = True
                    break
            if hit:
                dropped += 1
            else:
                keep.append(tr)
        trades[tk] = keep
    return trades, dropped


# ---------------------------------------------------------------------------
# 3. THE SPLIT
# ---------------------------------------------------------------------------
def competing(lst, want, price, t0_ms, t1_ms):
    """(n_trades, contracts, first_ms) for takers buying OUR side at OUR price
    or dearer, in (t0_ms, t1_ms].

    taker_outcome_side == want is the whole test: a taker who BOUGHT the side
    we wanted consumed an ask on that side. A taker on the other side is the
    counterparty to a seller of our side and does not compete with us. A taker
    paying LESS than our price hit a better offer that arrived after ours, and
    that is not the offer we were going to hit.
    """
    n = 0
    vol = 0.0
    first = None
    for ts_ms, y, nn, c, side in lst:
        if ts_ms <= t0_ms or ts_ms > t1_ms:
            continue
        if side != want:
            continue
        px = y if want == "yes" else nn
        if px < price - PRICE_EPS:
            continue
        n += 1
        vol += c
        if first is None or ts_ms < first:
            first = ts_ms
    return n, vol, first


def row_key(r):
    return "%s|%d|%s" % (r["ticker"], r["entry_ms"], r["want"])


def contest_map(rows, trades, deltas=DELTAS_MS, say=None):
    """row key -> {delta: [hits, vol, first_ms, pre_hits, pre_vol]}.

    Built once from the tape and cached, because the tape pass is 57 million
    lines and every question after the first is a re-score. Same reason
    pinlevels caches its candidates: re-walking is hours, re-scoring is
    seconds.
    """
    m = {}
    for r in rows:
        lst = trades.get(r["ticker"], ())
        e = {}
        for d in deltas:
            t0 = r["entry_ms"]
            t1 = min(t0 + d, r["close"] * 1000)
            n, vol, first = competing(lst, r["want"], r["price"], t0, t1)
            pn, pvol, _ = competing(lst, r["want"], r["price"], t0 - d, t0)
            e[str(d)] = [n, vol, (first - t0) if first is not None else None,
                         pn, pvol]
        m[row_key(r)] = e
    if say:
        say("    contest map: %d rows x %d windows" % (len(m), len(deltas)))
    return m


def classify(rows, trades, delta_ms, cmap=None):
    """Attach the contest fields to every row, for one delta.

    `trades` is the tape; `cmap` is contest_map's cached answer. Either drives
    the same fields, so a re-score and a fresh pass cannot disagree.
    """
    out = []
    for r in rows:
        if cmap is not None:
            e = cmap.get(row_key(r))
            if e is None or str(delta_ms) not in e:
                continue
            n, vol, first, pn, pvol = e[str(delta_ms)]
        else:
            lst = trades.get(r["ticker"], ())
            t0 = r["entry_ms"]
            t1 = min(t0 + delta_ms, r["close"] * 1000)
            n, vol, fm = competing(lst, r["want"], r["price"], t0, t1)
            pn, pvol, _ = competing(lst, r["want"], r["price"],
                                    t0 - delta_ms, t0)
            first = (fm - t0) if fm is not None else None
        d = dict(r)
        d["hits"] = n
        d["hit_vol"] = vol
        d["first_ms"] = first
        d["pre_hits"] = pn
        d["pre_vol"] = pvol
        d["klass"] = CONTESTED if n > 0 else CLEAR
        d["klass_pre"] = CONTESTED if pn > 0 else CLEAR
        d["exhausted"] = bool(r["depth"] > 0 and vol >= r["depth"])
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# 4. THE ARITHMETIC -- all of it deflated, none of it ours
# ---------------------------------------------------------------------------
def acc(sub):
    """(n, closes, lost, accuracy, rho, deff, lo, hi) on deflated counts."""
    n = len(sub)
    if n == 0:
        return (0, 0, 0, float("nan"), 0.0, 1.0, float("nan"), float("nan"))
    xs = [m["won"] for m in sub]
    keys = [m["close"] for m in sub]
    w = sum(1 for x in xs if x)
    rho, deff, neff = icc_deff(xs, keys)
    ne = max(1, int(round(neff)))
    xe = min(ne, int(round(w / deff)))
    lo, hi = cp_interval(xe, ne)
    return (n, len({m["close"] for m in sub}), n - w, w / n, rho, deff, lo, hi)


def boot_gap(rows, b=4000, seed=20260913, key="klass"):
    """By-CLOSE block bootstrap of accuracy(CONTESTED) - accuracy(CLEAR).

    Resamples CLOSES with replacement -- the cluster, not the row -- so the
    correlation between coins settling on the same second is carried into the
    interval by construction.
    """
    by = defaultdict(lambda: [0, 0, 0, 0])
    for m in rows:
        c = by[m["close"]]
        if m[key] == CONTESTED:
            c[0] += 1
            c[1] += 1 if m["won"] else 0
        else:
            c[2] += 1
            c[3] += 1 if m["won"] else 0
    cells = list(by.values())
    if not cells:
        return float("nan"), float("nan"), float("nan"), float("nan")
    rnd = random.Random(seed)
    k = len(cells)
    gaps = []
    for _ in range(b):
        nc = wc = nu = wu = 0
        for _j in range(k):
            c = cells[rnd.randrange(k)]
            nc += c[0]
            wc += c[1]
            nu += c[2]
            wu += c[3]
        if nc == 0 or nu == 0:
            continue
        gaps.append(wc / nc - wu / nu)
    nc = sum(c[0] for c in cells)
    wc = sum(c[1] for c in cells)
    nu = sum(c[2] for c in cells)
    wu = sum(c[3] for c in cells)
    point = (wc / nc - wu / nu) if (nc and nu) else float("nan")
    if not gaps:
        return point, float("nan"), float("nan"), float("nan")
    gaps.sort()
    lo = gaps[int(0.025 * len(gaps))]
    hi = gaps[min(len(gaps) - 1, int(0.975 * len(gaps)))]
    share = sum(1 for g in gaps if g >= 0) / len(gaps)
    return point, lo, hi, share


CONF_EDGES = (0.999, 0.9999)
TAU_EDGES = (15,)


def stratum(m):
    """(confidence band, tau band). The same grid pinselect standardises on."""
    c = 0
    for e in CONF_EDGES:
        if m["conf"] >= e:
            c += 1
    t = 0
    for e in TAU_EDGES:
        if m["tau"] > e:
            t += 1
    return (c, t)


def standardised(rows, key="klass"):
    """(contested acc, CLEAR acc re-weighted onto CONTESTED's mix, coverage).

    Confound 1. Only strata where BOTH arms have rows can be compared at all;
    `coverage` is the share of the contested arm living in such a stratum, so a
    thin comparison is visible as thin rather than quoted as a number.
    """
    con = defaultdict(list)
    cle = defaultdict(list)
    for m in rows:
        (con if m[key] == CONTESTED else cle)[stratum(m)].append(m)
    hit = [m for m in rows if m[key] == CONTESTED]
    if not hit:
        return float("nan"), float("nan"), 0.0
    a_con = sum(1 for m in hit if m["won"]) / len(hit)
    num = 0.0
    wsum = 0.0
    for s, v in con.items():
        u = cle.get(s)
        if not u:
            continue
        w = len(v)
        num += w * (sum(1 for m in u if m["won"]) / len(u))
        wsum += w
    if wsum == 0:
        return a_con, float("nan"), 0.0
    return a_con, num / wsum, wsum / len(hit)


# ---------------------------------------------------------------------------
# 5. RACING HARDER -- what the ladder says a lost race would have cost
# ---------------------------------------------------------------------------
def sweep_cost(rows, ceiling=None, edge_floor_c=None):
    """For rows that were CONTESTED, what the NEXT level up would have cost.

    A taker limit above the resting ask does not pay more when it WINS the
    race -- an IOC limit that crosses fills at the resting order's price. It
    pays more only when the level is gone, which is exactly the race we lose.
    So the price of racing harder is (next level - our level) on the lost races
    ONLY, and the gain is the trade.

    THE NUMBER THAT MATTERS IS NOT HOW OFTEN A NEXT LEVEL EXISTS. It is how
    often the next level STILL CLEARS THE GATE WE ALREADY TRUST -- inside the
    ceiling, and with at least the edge floor left after the fee. Sweeping up
    to a price that fails the gate is not racing harder, it is trading a rule
    nobody has tested. So gate_ok is counted separately from next_inside and it
    is the only one a recommendation may be built on.
    """
    if ceiling is None:
        ceiling = pinrun.PRICE_CEILING
    if edge_floor_c is None:
        edge_floor_c = 100.0 * pinrun.EDGE_FLOOR
    out = {"n": 0, "next_inside": 0, "no_next": 0, "next_dear": 0,
           "gate_ok": 0, "gate_fail_edge": 0, "no_fair": 0,
           "cost_c": [], "gate_cost_c": [], "next_depth": []}
    for m in rows:
        if m["klass"] != CONTESTED:
            continue
        out["n"] += 1
        nxt = None
        for px, dep in (m["ladder"] or []):
            if px > m["price"] + PRICE_EPS:
                nxt = (float(px), float(dep))
                break
        if nxt is None:
            out["no_next"] += 1
            continue
        if nxt[0] > ceiling + PRICE_EPS:
            out["next_dear"] += 1
            continue
        out["next_inside"] += 1
        out["cost_c"].append(100.0 * (nxt[0] - m["price"]))
        out["next_depth"].append(nxt[1])
        f = m.get("fair") or 0.0
        if f <= 0:
            out["no_fair"] += 1
            continue
        edge_c = 100.0 * (f - nxt[0]) - 100.0 * pinrun.billed_fee(nxt[0], 1)
        if edge_c >= edge_floor_c:
            out["gate_ok"] += 1
            out["gate_cost_c"].append(100.0 * (nxt[0] - m["price"]))
        else:
            out["gate_fail_edge"] += 1
    return out


def pct(xs, q):
    if not xs:
        return float("nan")
    ys = sorted(xs)
    i = min(len(ys) - 1, max(0, int(q * len(ys))))
    return ys[i]


# ---------------------------------------------------------------------------
# 6. THE SELF-TEST -- the deliverable. The estimator is the easy part.
# ---------------------------------------------------------------------------
def _row(close, i, want="yes", price=0.96, conf=0.9995, tau=20, won=True,
         depth=200.0, entry_ms=None):
    cs = int(close)
    return {"ticker": "KX%s15M-%d-00" % ("ABC"[i % 3], cs), "coin": "KXA15M",
            "close": cs, "tau": tau,
            "entry_ms": entry_ms if entry_ms is not None
            else (cs - tau) * 1000,
            "want": want, "price": price, "depth": depth,
            "ladder": [[price, depth], [min(0.999, price + 0.01), 50.0]],
            "conf": conf, "discount_c": 100.0 * (1.0 - price),
            "won": bool(won)}


def _world(n_closes, p_contest, loss_contested, loss_clear, seed,
           per_close=3):
    """Rows plus a trade tape in which contest and outcome are planted.

    Returns (rows, trades). The trades are real records in the same shape
    scan_trades emits, so classify() is driven, not bypassed.
    """
    rnd = random.Random(seed)
    rows = []
    trades = defaultdict(list)
    for k in range(n_closes):
        cs = 1788700000 + 900 * k
        cs -= cs % 900
        for i in range(per_close):
            contested = rnd.random() < p_contest
            q = loss_contested if contested else loss_clear
            won = rnd.random() >= q
            r = _row(cs, i, won=won)
            r["ticker"] = r["ticker"] + "-%d" % i
            rows.append(r)
            if contested:
                trades[r["ticker"]].append(
                    (r["entry_ms"] + 120, r["price"], 1.0 - r["price"],
                     10.0, r["want"]))
            # noise that must NOT count: wrong side, and too cheap
            trades[r["ticker"]].append(
                (r["entry_ms"] + 130, r["price"], 1.0 - r["price"], 5.0,
                 "no" if r["want"] == "yes" else "yes"))
            trades[r["ticker"]].append(
                (r["entry_ms"] + 140, r["price"] - 0.05,
                 1.0 - (r["price"] - 0.05), 5.0, r["want"]))
    return rows, dict(trades)


def _world_confound(n_closes, seed):
    """Contest and outcome BOTH driven by the stratum, nothing else.

    The crude gap must fire here and the standardised one must not: this is
    the occupation-time/attractiveness confound of section 1, planted.
    """
    rnd = random.Random(seed)
    rows = []
    trades = defaultdict(list)
    for k in range(n_closes):
        cs = 1788700000 + 900 * k
        cs -= cs % 900
        for i in range(6):
            # stratum A: high conf, safe, rarely contested
            # stratum B: low conf, risky, usually contested
            b = (i % 2 == 1)
            conf = 0.99 if b else 0.99999
            loss = 0.20 if b else 0.01
            p_c = 0.90 if b else 0.10
            contested = rnd.random() < p_c
            won = rnd.random() >= loss
            r = _row(cs, i, conf=conf, won=won)
            r["ticker"] = r["ticker"] + "-s%d" % i
            rows.append(r)
            if contested:
                trades[r["ticker"]].append(
                    (r["entry_ms"] + 100, r["price"], 1.0 - r["price"],
                     10.0, r["want"]))
    return rows, dict(trades)


def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    # -- competing(): the four ways a trade can fail to be our competitor ----
    want, px = "yes", 0.96
    base = 1788700000000
    lst = [
        (base + 100, 0.96, 0.04, 10.0, "yes"),   # ours: same side, same price
        (base + 200, 0.97, 0.03, 5.0, "yes"),    # ours: dearer
        (base + 300, 0.95, 0.05, 99.0, "yes"),   # NOT: cheaper offer, later
        (base + 400, 0.96, 0.04, 99.0, "no"),    # NOT: other side
        (base - 100, 0.96, 0.04, 99.0, "yes"),   # NOT: before our moment
        (base + 5000, 0.96, 0.04, 99.0, "yes"),  # NOT: outside the window
    ]
    nn, vol, first = competing(lst, want, px, base, base + 1000)
    ck(nn == 2, "competing() counts the same-side takes at or above our price "
                "(2 of 6 planted records)")
    ck(abs(vol - 15.0) < 1e-9, "and sums their contracts (15.0)")
    ck(first == base + 100, "and reports the FIRST one (+100 ms)")
    nb, _, _ = competing(lst, want, px, base - 1000, base)
    ck(nb == 1, "the pre-window sees the take that happened BEFORE us, and "
                "the after-window does not")
    nn2, _, _ = competing(lst, "no", 0.04, base, base + 1000)
    ck(nn2 == 1, "asking for the NO side reads no_price, not yes_price")

    # -- classify() ---------------------------------------------------------
    rows, trades = _world(40, 0.5, 0.02, 0.02, seed=1)
    cl = classify(rows, trades, 1000)
    ck(len(cl) == len(rows), "classify() returns one record per row")
    ck(all(m["klass"] in (CONTESTED, CLEAR) for m in cl),
       "every row lands in exactly one arm")
    share = sum(1 for m in cl if m["klass"] == CONTESTED) / len(cl)
    ck(0.35 < share < 0.65,
       "with contest planted at 50%% the split recovers it (%.0f%%)"
       % (100 * share))
    ck(all(m["klass"] == CLEAR or m["first_ms"] == 120 for m in cl),
       "and the time to the first competing take is the planted 120 ms")

    # -- THE PLANTED EFFECT: clear is poison --------------------------------
    rows, trades = _world(400, 0.5, 0.005, 0.08, seed=7)
    cl = classify(rows, trades, 1000)
    a_c = acc([m for m in cl if m["klass"] == CONTESTED])
    a_u = acc([m for m in cl if m["klass"] == CLEAR])
    ck(a_c[3] > a_u[3] + 0.03,
       "a world where CLEAR loses 8%% and CONTESTED 0.5%% is found: "
       "%.1f%% vs %.1f%% accuracy" % (100 * a_c[3], 100 * a_u[3]))
    g, lo, hi, sh = boot_gap(cl)
    ck(lo > 0, "and the by-close bootstrap interval excludes zero "
               "(gap %+.2f pp [%+.2f, %+.2f])" % (100 * g, 100 * lo, 100 * hi))

    # -- THE PLANTED EFFECT, REVERSED ---------------------------------------
    rows, trades = _world(400, 0.5, 0.08, 0.005, seed=8)
    cl = classify(rows, trades, 1000)
    g2, lo2, hi2, _ = boot_gap(cl)
    ck(hi2 < 0, "the OPPOSITE world -- contested loses 8%% -- is found with "
                "the opposite sign (%+.2f pp [%+.2f, %+.2f])"
                % (100 * g2, 100 * lo2, 100 * hi2))

    # -- THE NULL: no effect planted ----------------------------------------
    rows, trades = _world(400, 0.5, 0.03, 0.03, seed=9)
    cl = classify(rows, trades, 1000)
    g0, lo0, hi0, _ = boot_gap(cl)
    ck(lo0 <= 0 <= hi0,
       "a world with NOTHING planted returns an interval covering zero "
       "(%+.2f pp [%+.2f, %+.2f])" % (100 * g0, 100 * lo0, 100 * hi0))

    # -- THE CONFOUND: both arms driven by the stratum ----------------------
    rows, trades = _world_confound(500, seed=11)
    cl = classify(rows, trades, 1000)
    gc, loc, hic, _ = boot_gap(cl)
    ck(hic < 0, "in the confound world the CRUDE gap fires (%+.2f pp "
                "[%+.2f, %+.2f]) -- as it must, the arms differ" %
       (100 * gc, 100 * loc, 100 * hic))
    a_con, a_std, cov = standardised(cl)
    ck(cov > 0.95, "the standardiser can compare %.0f%% of the contested arm"
       % (100 * cov))
    ck(abs(a_con - a_std) < 0.03,
       "and standardising on (conf x tau) removes it: %+.2f pp, against a "
       "crude %+.2f pp" % (100 * (a_con - a_std), 100 * gc))

    # -- OUR OWN FILLS are removed ------------------------------------------
    rows, trades = _world(20, 1.0, 0.02, 0.02, seed=3)
    mine = [(r["ticker"], r["entry_ms"] + 120, r["price"], r["want"])
            for r in rows]
    trades2, dropped = drop_own({k: list(v) for k, v in trades.items()}, mine)
    ck(dropped == len(rows),
       "every one of our own %d executions is dropped from the tape"
       % len(rows))
    cl2 = classify(rows, trades2, 1000)
    ck(all(m["klass"] == CLEAR for m in cl2),
       "and with them gone, a tape that was 100%% contested is 100%% clear -- "
       "so the bot cannot contest its own offer")
    trades3, dropped3 = drop_own({k: list(v) for k, v in trades.items()},
                                 [(t, ms + 60000, p, s)
                                  for t, ms, p, s in mine])
    ck(dropped3 == 0, "a fill a minute away is NOT ours and is kept")

    # -- the MDE is real arithmetic, not decoration -------------------------
    m1 = mde_pp(100.0, 100.0, 0.99)
    m2 = mde_pp(10000.0, 10000.0, 0.99)
    ck(m1 > m2 > 0, "the MDE shrinks with n (%.2f pp at 100 vs %.2f pp at "
                    "10000)" % (m1, m2))

    # -- sweep_cost ---------------------------------------------------------
    rows, trades = _world(40, 1.0, 0.02, 0.02, seed=5)
    cl = classify(rows, trades, 1000)
    sw = sweep_cost(cl, ceiling=0.98)
    ck(sw["n"] == len(cl), "sweep_cost looks at every contested row")
    ck(sw["next_inside"] == len(cl),
       "and finds the planted next level inside the ceiling on all of them")
    ck(abs(pct(sw["cost_c"], 0.5) - 1.0) < 1e-6,
       "the planted 1c step up is what it reports as the cost of racing")
    sw2 = sweep_cost(cl, ceiling=0.90)
    ck(sw2["next_dear"] == len(cl),
       "and a ceiling below the next level refuses every sweep")
    # the gate-aware count: the next level must still clear the edge floor
    for m in cl:
        m["fair"] = 0.999            # 0.97 next level -> 2.9c edge, passes
    ck(sweep_cost(cl, ceiling=0.98)["gate_ok"] == len(cl),
       "with fair far above the next level, every sweep still clears the gate")
    for m in cl:
        m["fair"] = 0.9705           # 0.97 next level -> 0.05c, fails
    swg = sweep_cost(cl, ceiling=0.98)
    ck(swg["gate_ok"] == 0 and swg["gate_fail_edge"] == len(cl),
       "and with fair a whisker above it, NONE of them do -- the gate, not "
       "the ladder, is what decides whether racing harder is allowed")

    # -- the loaders, on a real file round trip ------------------------------
    tmp = tempfile.mkdtemp(prefix="pincontest-")
    try:
        rp = os.path.join(tmp, "rows.jsonl")
        with open(rp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": "not-a-row"}) + "\n")
            fh.write(json.dumps({
                "kind": "row", "ticker": "KXBTC15M-26SEP061830-30",
                "coin": "KXBTC15M", "cs": 1788733800, "tau": 21,
                "entry_ts": 1788733779865, "want": "yes", "price": 0.952,
                "depth": 100.0, "ladder": [[0.952, 100.0]], "won": True,
                "conf": 0.999894, "discount_c": 4.79}) + "\n")
            fh.write("not json at all\n")
        got = load_rows(rp)
        ck(len(got) == 1, "load_rows keeps only kind=row and survives junk")
        ck(got[0]["close"] == 1788733800 and got[0]["price"] == 0.952,
           "and reads the fields it will be judged on")
        st = hour_stamps(got)
        ck("20260906T22" in st,
           "hour_stamps covers the hour the candidate sits in (%s)"
           % sorted(st))
        gz = os.path.join(tmp, "trade")
        os.makedirs(gz)
        with gzip.open(os.path.join(gz, "20260906T22.jsonl.gz"), "wt",
                       encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "trade", "msg": {
                "market_ticker": "KXBTC15M-26SEP061830-30",
                "yes_price_dollars": "0.9520", "no_price_dollars": "0.0480",
                "count_fp": "12.00", "taker_outcome_side": "yes",
                "ts_ms": 1788733780000}}) + "\n")
            fh.write(json.dumps({"type": "trade", "msg": {
                "market_ticker": "KXBTC15M-26SEP061830-30",
                "yes_price_dollars": "0.9520", "no_price_dollars": "0.0480",
                "count_fp": "99.00", "taker_outcome_side": "yes",
                "ts_ms": 1788733000000}}) + "\n")   # not near a close
        tr, seen, kept = scan_trades(tmp, st, {got[0]["ticker"]}, say=None)
        ck(kept == 1 and seen == 2,
           "scan_trades reads both lines and keeps only the one inside the "
           "settlement window")
        cl = classify(got, tr, 1000)
        ck(cl[0]["klass"] == CONTESTED and cl[0]["hit_vol"] == 12.0,
           "and the round trip through a real gzip file marks the row "
           "contested with the right size")
    finally:
        for root, dirs, files in os.walk(tmp, topdown=False):
            for f in files:
                os.remove(os.path.join(root, f))
            for d in dirs:
                os.rmdir(os.path.join(root, d))
        os.rmdir(tmp)

    # -- gate(): the filter that the first real run proved is not cosmetic --
    g_rows = [_row(1788700000, 0, price=0.02, won=False),
              _row(1788700900, 1, price=0.96, won=True, depth=200.0),
              _row(1788701800, 2, price=0.96, won=True, depth=3.0)]
    g_rows[0]["verdict"] = "refuse"
    g_rows[0]["fired"] = ["dump"]
    for r in g_rows[1:]:
        r["verdict"] = "trade"
    ck(len(gate(g_rows, "all")) == 3, "gate 'all' keeps everything cached")
    ck(len(gate(g_rows, "trade")) == 2,
       "gate 'trade' drops the candidate pinlevels' own profile REFUSED -- "
       "the 2c offer the dump guard exists for")
    ck(len(gate(g_rows, "live")) == 1,
       "gate 'live' also drops the one too thin to fill at the deployed size")

    # -- the cache and the tape must produce the SAME classification ---------
    rows, trades = _world(50, 0.5, 0.02, 0.05, seed=31)
    cm = contest_map(rows, trades)
    a1 = classify(rows, trades, 1000)
    a2 = classify(rows, {}, 1000, cmap=cm)
    ck(len(a1) == len(a2) and all(
        x["klass"] == y["klass"] and x["klass_pre"] == y["klass_pre"]
        and x["hits"] == y["hits"] and x["first_ms"] == y["first_ms"]
        for x, y in zip(a1, a2)),
       "a re-score from the cache reproduces the tape pass exactly")
    cm2 = json.loads(json.dumps(cm))
    a3 = classify(rows, {}, 1000, cmap=cm2)
    ck(all(x["klass"] == y["klass"] for x, y in zip(a1, a3)),
       "and survives the JSON round trip it is stored through")

    # -- the BACKWARD arm must be blind to anything after the decision -------
    rows, trades = _world(40, 1.0, 0.02, 0.02, seed=33)
    cl = classify(rows, trades, 1000)
    ck(all(m["klass"] == CONTESTED for m in cl),
       "with every offer taken 120 ms AFTER us, the forward arm is contested")
    ck(all(m["klass_pre"] == CLEAR for m in cl),
       "and the backward arm is CLEAR -- it cannot see the future, which is "
       "the whole reason it is the only tradeable one")

    # -- the PUBLISHED ARTEFACT must carry rule 5 on its face ---------------
    # Not prose-policing: the report is what gets read back from git months
    # later, and a table of failure rates with no population caveat on it is
    # exactly how the tape got quoted as our loss rate three times in one day
    # (CLAUDE.md, 2026-09-10). So the disclaimer is a test, not a habit.
    rows, trades = _world(60, 0.5, 0.02, 0.05, seed=21)
    txt = report(rows, trades, None, 0, say=lambda *a, **k: None,
                 window="selftest", live_note="selftest")
    ck("rule 5" in txt and "Neither arm is a loss rate of ours" in txt,
       "the report names rule 5 and disclaims both arms, on its face")
    ck("P&L" in txt and "No P&L is computed" in txt,
       "and states that it computes no P&L")
    ck("NO POWER, not NO EFFECT" in txt,
       "and prints the MDE with the no-power/no-effect distinction")
    ck("LEAKAGE CHECK" in txt,
       "and carries the leakage check above the forward table it qualifies")

    print("pincontest selftest: %d checks OK" % n[0])
    return 0


# ---------------------------------------------------------------------------
# 7. THE REPORT
# ---------------------------------------------------------------------------
def fmt_arm(label, a):
    n, cl, lost, p, rho, deff, lo, hi = a
    if n == 0:
        return "| %s | 0 | 0 | - | - | - |" % label
    return ("| %s | %d | %d | %d | %.2f%% | [%.2f, %.2f] |"
            % (label, n, cl, lost, 100 * p, 100 * lo, 100 * hi))


def report(rows, trades, out_path, dropped, delta_ms=PRIMARY_DELTA,
           say=print, window="", live_note="", pop="live", cmap=None):
    lines = []
    w = lines.append
    cl = classify(rows, trades, delta_ms, cmap)
    con = [m for m in cl if m["klass"] == CONTESTED]
    cle = [m for m in cl if m["klass"] == CLEAR]
    a_con = acc(con)
    a_cle = acc(cle)
    a_all = acc(cl)
    mde = mde_pp(a_con[0] / max(a_con[5], 1.0), a_cle[0] / max(a_cle[5], 1.0),
                 a_all[3] if a_all[3] == a_all[3] else 0.99)
    g, lo, hi, share = boot_gap(cl)
    s_con, s_cle, cov = standardised(cl)

    w("# RESULTS_contest -- did anyone else want the offer?")
    w("")
    w("*`research/pincontest.py`, %s. %d candidate offers on %d closes, %s. "
      "Population `%s`. Contest window %d ms. %d of our own executions removed "
      "from the tape. %s*"
      % (time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), len(cl),
         len({m['close'] for m in cl}), window, pop, delta_ms, dropped,
         live_note))
    w("")
    w("**THIS FILE COMPARES TWO TAPE POPULATIONS WITH EACH OTHER AND DOES "
      "NOTHING ELSE.** Neither arm is a loss rate of ours and neither may be "
      "quoted as one (CLAUDE.md 2026-09-10, rule 5). No P&L is computed here.")
    w("")
    w("## 0. Power, before the estimate")
    w("")
    w("rho between coins sharing a close is measured at %.3f, design effect "
      "%.2fx. The smallest accuracy gap this split can call at alpha=0.05 "
      "two-sided with 80%% power is **%.2f pp**. A gap smaller than that is NO "
      "POWER, not NO EFFECT." % (a_all[4], a_all[5], mde))
    w("")
    w("## 1. The FORWARD split -- who else took it, after our moment")
    w("")
    w("| arm | rows | closes | lost | the model's side won | 95% CP "
      "(deflated) |")
    w("|---|---|---|---|---|---|")
    w(fmt_arm("CONTESTED -- another taker bought it", a_con))
    w(fmt_arm("CLEAR -- nobody did", a_cle))
    w(fmt_arm("all candidates", a_all))
    w("")
    w("**Gap (contested minus clear): %+.2f pp, 95%% by-close bootstrap "
      "[%+.2f, %+.2f], %.1f%% of resamples at or above zero.**"
      % (100 * g, 100 * lo, 100 * hi, 100 * share))
    w("")
    w("Standardised on the contested arm's own (confidence x tau) mix, "
      "covering %.0f%% of it: contested %.2f%%, clear %.2f%%, gap %+.2f pp."
      % (100 * cov, 100 * s_con, 100 * s_cle, 100 * (s_con - s_cle)))
    w("")
    w("## 2. THE LEAKAGE CHECK -- and it fires, so read this before section 1")
    w("")
    w("A forward window sees the future. If the model's side is going to WIN, "
      "its price walks to $1 and any ask left resting below that gets lifted "
      "by somebody -- it is free money and the exchange is full of takers. If "
      "it is going to LOSE, the ask is never lifted at any price. So 'was it "
      "taken' is partly CAUSED by the outcome, and the longer the window the "
      "more of the gap is that mechanism rather than information anyone had at "
      "our moment. The table below is the test: if the split were information, "
      "widening the window would add noise and shrink the gap. It does the "
      "opposite.")
    w("")
    w("| window | contested rows | share | contested acc | clear acc | gap |")
    w("|---|---|---|---|---|---|")
    for d in DELTAS_MS:
        c2 = classify(rows, trades, d, cmap)
        cc = [m for m in c2 if m["klass"] == CONTESTED]
        uu = [m for m in c2 if m["klass"] == CLEAR]
        ac = acc(cc)
        au = acc(uu)
        gg = (ac[3] - au[3]) if (cc and uu) else float("nan")
        w("| %d ms | %d | %.1f%% | %.2f%% | %.2f%% | %+.2f pp |"
          % (d, len(cc), 100.0 * len(cc) / max(1, len(c2)),
             100 * ac[3], 100 * au[3], 100 * gg))
    w("")
    w("**A gap that grows without limit as the window widens is the outcome "
      "leaking in, not a signal.** Section 1 is therefore valid for what it "
      "was built for -- selecting the population that resembles our own fills "
      "-- and INVALID as a trading rule. The tradeable version is section 3, "
      "which can only look backwards.")
    w("")
    w("## 3. The BACKWARD split -- what was knowable at our moment")
    w("")
    pc_ = [m for m in cl if m["klass_pre"] == CONTESTED]
    pu_ = [m for m in cl if m["klass_pre"] == CLEAR]
    ap_c = acc(pc_)
    ap_u = acc(pu_)
    mde_p = mde_pp(ap_c[0] / max(ap_c[5], 1.0), ap_u[0] / max(ap_u[5], 1.0),
                   a_all[3] if a_all[3] == a_all[3] else 0.99)
    gp, lop, hip, shp = boot_gap(cl, key="klass_pre")
    sp_c, sp_u, cov_p = standardised(cl, key="klass_pre")
    w("Same test, same window length, run over the %d ms BEFORE the decision "
      "instead of after. Every input here exists at the moment the order would "
      "be sent, so a rule may be built on it. MDE **%.2f pp**."
      % (delta_ms, mde_p))
    w("")
    w("| arm | rows | closes | lost | the model's side won | 95% CP "
      "(deflated) |")
    w("|---|---|---|---|---|---|")
    w(fmt_arm("someone took this level JUST BEFORE us", ap_c))
    w(fmt_arm("nobody had", ap_u))
    w("")
    w("**Gap: %+.2f pp, 95%% by-close bootstrap [%+.2f, %+.2f], %.1f%% of "
      "resamples at or above zero. Standardised %+.2f pp (coverage %.0f%%).**"
      % (100 * gp, 100 * lop, 100 * hip, 100 * shp,
         100 * (sp_c - sp_u), 100 * cov_p))
    w("")
    w("## 4. How fast the competition arrives")
    w("")
    ms = [m["first_ms"] for m in con if m["first_ms"] is not None]
    if ms:
        w("Of %d contested rows, the first competing take lands after "
          "p10 %.0f ms, median %.0f ms, p90 %.0f ms. %d%% of them are gone "
          "inside 250 ms."
          % (len(ms), pct(ms, 0.10), pct(ms, 0.50), pct(ms, 0.90),
             round(100.0 * sum(1 for x in ms if x <= 250) / len(ms))))
    else:
        w("No contested rows at this window.")
    w("")
    ex = [m for m in con if m["exhausted"]]
    w("The level was fully consumed (competing contracts >= the depth we "
      "measured) on %d of %d contested rows, %.1f%%."
      % (len(ex), len(con), 100.0 * len(ex) / max(1, len(con))))
    w("")
    w("## 5. What each arm holds -- a guard that discards data, costed")
    w("")
    for label, sub in (("CONTESTED", con), ("CLEAR", cle),
                       ("BACKWARD-contested", pc_), ("BACKWARD-clear", pu_)):
        if not sub:
            continue
        dep = sum(m["depth"] for m in sub)
        w("- **%s**: %d rows (%.1f%%), %d closes, %.0f contracts of resting "
          "depth, mean discount %.2fc, mean tau %.1f s."
          % (label, len(sub), 100.0 * len(sub) / len(cl),
             len({m["close"] for m in sub}), dep,
             sum(m["discount_c"] for m in sub) / len(sub),
             sum(m["tau"] for m in sub) / len(sub)))
    w("")
    w("## 6. The price of racing harder")
    w("")
    sw = sweep_cost(cl)
    if sw["n"]:
        w("A taker limit above the resting ask pays the RESTING price when it "
          "wins -- an IOC limit that crosses fills at the resting order's "
          "price -- so racing harder is free on every race we already win. It "
          "costs something only on the races we lose today, and only up to the "
          "next level.")
        w("")
        w("| of %d contested rows | rows | share |" % sw["n"])
        w("|---|---|---|")
        w("| next level inside the %.0fc ceiling | %d | %.1f%% |"
          % (100 * pinrun.PRICE_CEILING, sw["next_inside"],
             100.0 * sw["next_inside"] / sw["n"]))
        w("| **and still clears the SAME gate (edge >= %.1fc after fee)** | "
          "**%d** | **%.1f%%** |"
          % (100 * pinrun.EDGE_FLOOR, sw["gate_ok"],
             100.0 * sw["gate_ok"] / sw["n"]))
        w("| inside the ceiling but under the edge floor | %d | %.1f%% |"
          % (sw["gate_fail_edge"], 100.0 * sw["gate_fail_edge"] / sw["n"]))
        w("| next level above the ceiling | %d | %.1f%% |"
          % (sw["next_dear"], 100.0 * sw["next_dear"] / sw["n"]))
        w("| nothing above at all | %d | %.1f%% |"
          % (sw["no_next"], 100.0 * sw["no_next"] / sw["n"]))
        w("")
        if sw["gate_cost_c"]:
            w("On the rows that still clear the gate the next level costs a "
              "median **%.2fc** more (mean %.2fc, p90 %.2fc) and holds a "
              "median %.0f contracts. The tick above 90c is 0.1c, which is why "
              "the median is what it is."
              % (pct(sw["gate_cost_c"], 0.5),
                 sum(sw["gate_cost_c"]) / len(sw["gate_cost_c"]),
                 pct(sw["gate_cost_c"], 0.9), pct(sw["next_depth"], 0.5)))
    w("")
    txt = "\n".join(lines) + "\n"
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(txt)
    say(txt)
    return txt


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows", default=ROWS_DEFAULT)
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--live-glob", default=LIVE_GLOB_DEFAULT)
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--delta-ms", type=int, default=PRIMARY_DELTA)
    ap.add_argument("--gate", default="live", choices=("all", "trade",
                                                       "live"),
                    help="which cached candidates to use; see gate()")
    ap.add_argument("--cache", default=os.path.join(REPO, "results",
                                                    "pincontest_trades.json"),
                    help="contest fields per row, so a re-score is seconds")
    ap.add_argument("--rescore", action="store_true",
                    help="score from --cache without touching the trade tape")
    ap.add_argument("--keep-own", action="store_true",
                    help="do NOT remove our own executions (diagnostic only)")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc

    t0 = time.time()
    rows = load_rows(a.rows)
    if not rows:
        print("pincontest: no candidate rows in %s -- run pinlevels first; "
              "nothing to analyse" % a.rows)
        return 0
    allrows = rows
    rows = gate(rows, a.gate)
    if not rows:
        print("pincontest: gate %r kept no candidates -- nothing to analyse"
              % a.gate)
        return 0
    print("  candidates: %d of %d cached rows pass gate %r; %d closes, "
          "%d markets"
          % (len(rows), len(allrows), a.gate,
             len({r['close'] for r in rows}), len({r['ticker'] for r in rows})))
    lo = min(r["entry_ms"] for r in rows) // 1000
    hi = max(r["close"] for r in rows)
    window = ("%s .. %s (%.1f days)"
              % (time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(lo)),
                 time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(hi)),
                 (hi - lo) / 86400.0))
    # The tape pass and therefore the cache are built over ALL cached
    # candidates, not the gated subset, so changing --gate is a re-score and
    # never another 57-million-line read.
    stamps = hour_stamps(allrows)
    tickers = {r["ticker"] for r in allrows}
    have = trade_files(a.data, stamps)
    print("  trade hours wanted %d, present %d" % (len(stamps), len(have)))
    if not have:
        print("pincontest: no trade files under %s -- nothing to analyse"
              % os.path.join(a.data, "trade"))
        return 0
    cmap = None
    dropped = 0
    note = ""
    if a.rescore and os.path.exists(a.cache):
        with open(a.cache, encoding="utf-8") as fh:
            blob = json.load(fh)
        cmap = blob.get("map") or {}
        dropped = int(blob.get("dropped", 0))
        note = blob.get("note", "") + " (re-scored from cache)"
        print("  re-scored from %s: %d rows" % (a.cache, len(cmap)))
        trades = {}
    else:
        trades, seen, kept = scan_trades(a.data, stamps, tickers)
        if kept == 0:
            print("pincontest: the trade window held no executions on any "
                  "candidate market -- nothing to analyse")
            return 0
        if not a.keep_own:
            own = own_fills(a.live_glob)
            trades, dropped = drop_own(trades, own)
            note = ("Our own live fills (%d order/hedge records) were matched "
                    "against the tape and %d executions removed."
                    % (len(own), dropped))
            print("  our own executions: %d records, %d trades removed"
                  % (len(own), dropped))
        else:
            note = "**--keep-own: our own executions are STILL IN the tape.**"
        cmap = contest_map(allrows, trades, say=print)
        if a.cache:
            with open(a.cache, "w", encoding="utf-8") as fh:
                json.dump({"map": cmap, "dropped": dropped, "note": note,
                           "built": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                  time.gmtime())}, fh)
            print("  cache written: %s" % a.cache)
    report(rows, trades, a.out, dropped, delta_ms=a.delta_ms,
           window=window, live_note=note, pop=a.gate, cmap=cmap)
    print("  %.1f s" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
