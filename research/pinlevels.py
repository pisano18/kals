#!/usr/bin/env python3
# VERSION: 2026-09-12-pl2
"""pinlevels.py -- WHAT EACH CONTRACT SIZE EARNS, AND HOW FAR IT SCALES.

The operator's question, verbatim: "run it back as much as need so you can to
get the most accurate expectation of what to earn at each level with the
current model", then "MAKE SURE IT CAN ANSWER EVERY SCALE UP AS FAR AS WE CAN
SCALE." `level` = contract SIZE. He is deciding whether to add capital, so the
error bars matter more than the point estimate and every figure here is built
to be an UPPER bound rather than a flattering one.

WHY ONE PASS AND NOT THIRTEEN
-----------------------------
A naive size sweep costs one full tape pass per size -- thirteen passes over
421 book hours. It is also unnecessary, because of what pinrun's decision
actually depends on:

  SIZE-INDEPENDENT, so calling pinrun's own code ONCE is valid for every size:
    PIN / fair()          the model's belief -- no size anywhere in it
    PRICE_CEILING         a price bound
    expected_value()      uses billed_fee(price, 1), fixed by definition
    TAU_MIN / TAU_MAX     a clock
    MAX_BOOK_AGE_MS       a book-staleness bound
    the profile's rules   `dump` reads conf and discount_c only

  SIZE-DEPENDENT, so they are recomputed OFFLINE, per size, by calling
  pinrun's own functions again:
    the `too_shallow` gate   depth >= max(MIN_LEVEL, MIN_FILL_FRAC * SIZE)
    take_n                   min(SIZE, depth)  -- or a ladder sweep, below
    billed_fee(price, n)     the fee, per order
    net_edge()               -- SUBTLE: it reads the MODULE constant SIZE for
                             the per-contract fee, billed_fee(price, SIZE)/SIZE.
                             That is why the pass runs with pinrun.SIZE set to
                             the LARGEST size scored (the smallest possible
                             per-contract fee, because billed_fee ceilings to
                             $0.0001 and the ceiling is diluted by size), so
                             the pass is PERMISSIVE and cannot drop a candidate
                             a larger size would have accepted. The scorer then
                             re-runs pinrun.net_edge() with pinrun.SIZE set to
                             the size being scored, which is exact.
    MAX_PER_CLOSE / MAX_PER_MARKET / IMPROVE_BY -- the per-close rails. NOT
                             size-independent in effect: a candidate too
                             shallow for size 50 never fills, so it never
                             consumes a slot at size 50 although it does at
                             size 5. So the rails are NOT applied in the pass
                             at all; the scorer applies them per size by
                             calling pinsim.close_slot_ok/close_slot_book.

NOTHING IS REIMPLEMENTED. The walk is pinsim's own `load_hour`, `EventStream`,
`TapeIndex`, `Walk`, `book_view` and `decide`, driven in the order
`pinsim.run()` drives them; the decision is pinrun's; the rails are pinsim's;
the fee is pinrun's. This file adds exactly two things: a record of the DEPTH
LADDER at the decision millisecond, and an offline scorer.

THE ONE PLACE THE PASS IS DELIBERATELY NOT pinsim.run()
-------------------------------------------------------
run() retires a market (`decided`) at its first candidate. At size 20 that is
right -- live would have bought it. But a candidate with 5 contracts resting is
NOT a fill at size 50, and live would keep scanning that market. So the pass
never retires a market, and emits a row for every candidate that is not
DOMINATED by an earlier one on the same market: at least as deep at the touch,
at least as deep on the ladder, and no dearer. For any gate that is monotone --
easier with more depth, easier with a lower price, which is the shape of
too_shallow, of the ladder fill and of IMPROVE_BY -- the first CANDIDATE that
passes is therefore an EMITTED one (property test in selftest()).

  THE DEPTH-ONLY VERSION OF THIS RULE WAS WRONG AND THE ANCHOR CAUGHT IT.
  Against pinsim.run()'s own 156 fills on the 72-hour window it produced 153.
  The closes matched 117 to 117 and all three missing fills were SECOND fills
  of a close: a later offer that was CHEAPER but no deeper was never emitted,
  so it could never clear the IMPROVE_BY bar, which is a price test. Price is
  its own axis. The pass was restarted.

  RESIDUAL, STATED: `fair` is not one of the axes, so a candidate whose only
  improvement is that the model grew MORE confident while the book stood still
  is not emitted, though net_edge would read it. fair moves by fractions of a
  percent second to second where price and depth jump.

TWO SCORING MODES, AND ONLY ONE OF THEM IS LIVE-FAITHFUL
--------------------------------------------------------
  TOUCH  -- what pinrun does today: the order sees the best ask and the size
            resting there. depth = the touch, price = the touch. This is the
            mode that reproduces pinsim.run(), and it is the honest number for
            the sizes we actually trade.
  SWEEP  -- what a LARGER order would do: consume the opposite side's bids
            from the best price down (a bid at q sells us a contract at cost
            1-q), pay the VWAP of what we consume, and stop at
            PRICE_CEILING -- applied to EVERY level, not just the touch -- or
            as soon as the running VWAP would fail pinrun's own edge/EV gates.
            REQUIRED for the scale question, because the touch alone
            understates how much we could fill, and IT IS A RULE CHANGE from
            what is deployed: today's MIN_FILL_FRAC bar is measured against
            the touch, so above ~size 125 today's bot would simply refuse. The
            sweep table answers "how far COULD we scale", not "what would the
            current bot do".

WHAT NO REPLAY CAN TELL US, restated because it is the headline caveat
----------------------------------------------------------------------
Whether the offer would have been OURS. Live we fill 70% of the attempts we
make (50 of 72, measured). The replay wins every race it never ran, so the
70%-fill column is itself an upper bound, not a central estimate. And per
CLAUDE.md's 2026-09-10 amendment: THE LOSS RATE HERE IS THE REPLAY'S, NOT
OURS. The tape's population is "an offer was sitting there"; ours is "someone
actively sold it to us", and only the second is adversely selected. Measured
gap at the live gate: tape 0.11% [0.00, 0.61] against live 3.4% [0.4, 11.7].
Cite that gap; never substitute one for the other.
"""
import argparse
import calendar
import json
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinrun                                                  # noqa: E402
import pindata                                                 # noqa: E402
import pinrules                                                # noqa: E402
import pinsim                                                  # noqa: E402

SIZES = (1, 2, 5, 10, 20, 35, 50, 75, 125, 250, 500, 1000, 2000)
HEDGE_THRS = (0.70, 0.80, 0.90)
LIVE_HEDGE_BELIEF = 0.80          # pinrun.HEDGE_BELIEF, the live setting
LADDER_LEVELS = 12
BRAKE_HEADROOM = 1.5              # pinrun line 202: "the deployment rail
                                  # requires a brake of at least 1.5x" the
                                  # worst close
ROWS = os.path.join(HERE, "..", "results", "pinlevels_rows.jsonl")
REPORT = os.path.join(HERE, "..", "results", "RESULTS_levels.md")
BOOT_DRAWS = 4000
BOOT_SEED = 20260912

# ACCEPTANCE ANCHOR 1, run 2026-09-12: this file's scorer at size 20 against
# pinsim.run()'s own report on the same 72 book hours ending 20260910T04,
# same profile sha. It is a mechanical self-consistency check -- if the two
# disagree, the scorer is wrong -- and it found two real bugs before it
# passed (see the commit log: the one-dimensional emission rule, and the sort
# tie-break). Every field now reproduces.
ANCHOR1 = [
    ("fills", "156", "156"), ("closes", "117", "117"),
    ("wins / losses", "150 / 6", "150 / 6"),
    ("loss rate", "3.85% [1.42, 8.18]", "3.85% [1.42, 8.18]"),
    ("P&L", "$-11.01", "$-11.01"),
    ("mean price", "96.14c", "96.14c"),
    ("refused by the dump rule", "9", "9"),
]

# The live record split by the gate each run STARTED with, supplied by the
# coordinating agent 2026-09-12. Printed as CONTEXT ONLY: the longest
# single-gate window is 1.66 days, so no live window is long enough to anchor
# a $/day figure for any gate, which is why the backtest is the primary
# estimate and its own day-block bootstrap is the honest uncertainty.
LIVE_BY_GATE = [
    ("0.98/-",                    11, 0.27,    0.79),
    ("0.98/0.988",                21, 0.40, -110.09),
    ("0.98/0.98",                 50, 1.10,   23.49),
    ("0.995/0.98",                72, 1.66,   21.10),
    ("0.995/0.98/0.15",            3, 0.02, -777.42),
    ("0.995/0.98/0.15/1",         21, 0.22,   -9.06),
    ("0.995/0.98/0.15/1/0.9",     43, 0.34,   42.15),
    ("0.995/0.98/0.15/1/0.8",      7, 0.09,   41.59),
]


def thkey(thr):
    return f"{float(thr):.2f}"


def depth_bar(size):
    """pinrun's own `too_shallow` bar for this size -- decide()'s line, 1:1."""
    return max(float(pinrun.MIN_LEVEL), float(pinrun.MIN_FILL_FRAC) * float(size))


def dominated(prev, depth, lad, price):
    """True iff an EARLIER emitted row on this market was at least as good in
    every dimension a size-dependent gate can read: at least as deep at the
    touch, at least as deep on the ladder, and no dearer.

    THIS IS WHAT MAKES ONE PASS SUFFICIENT, and the first version of it was
    WRONG. It tracked depth only, and on the 72-hour acceptance window that
    cost exactly three fills against pinsim.run()'s own 156 -- the closes
    matched 117 to 117 and every one of the three was a SECOND fill of a
    close. The cause: a later offer that was CHEAPER but no deeper was never
    emitted, so it could never clear the IMPROVE_BY bar, which is a price
    test. Depth and price are separate axes, and a running maximum on one of
    them cannot stand in for the other.

    The property, proved in selftest() against random walks: for ANY gate
    that is monotone -- easier with more depth, easier with a lower price --
    the first CANDIDATE that passes it is emitted. If candidate c passes and
    was suppressed, some earlier emitted row e dominated it, so e passes too,
    so c was not the first. The three gates that matter are exactly of that
    shape: too_shallow (touch depth), the ladder fill (ladder depth) and
    IMPROVE_BY (price).

    RESIDUAL, STATED: `fair` is not a dimension here, so a candidate whose
    only improvement is that the model became MORE confident while the book
    stood still is not emitted, and net_edge would read that. fair moves by
    fractions of a percent second to second where price and depth jump, so
    this is the small term; it is named rather than hidden.
    """
    for d, l, pz in prev:
        if d >= depth - 1e-9 and l >= lad - 1e-9 and pz <= price + 1e-9:
            return True
    return False


def ladder_for(bk, side, k=LADDER_LEVELS):
    """The COST LADDER to buy `side`, ascending by cost.

    To buy YES we consume the NO side's bids, from the highest price down; a
    NO bid at q sells us a YES contract at cost (1-q). So the cheapest YES
    comes from the DEAREST no bid, which is why the touch in pinsim.book_view
    is `1 - max(bk.no)`. Returns [[cost, qty], ...] with ladder[0] equal to
    that touch by construction (checked in the pass, counted if it ever is
    not).
    """
    d = bk.no if side == "yes" else bk.yes
    out = []
    for q in sorted(d, reverse=True)[:k]:
        sz = float(d[q])
        if sz > 0:
            out.append([round(1.0 - float(q), 4), sz])
    return out


# ---------------------------------------------------------------- the fillers
def touch_fill(depth, price, size):
    """pinrun as deployed: one price, one level. Returns (n, price, levels)."""
    n = min(float(size), float(depth))
    return (n, float(price), 1) if n > 0 else (0.0, None, 0)


def sweep_fill(ladder, size, fair, want):
    """Walk the ladder cheapest-first and pay the VWAP of what we consume.

    Three stopping rules, in this order, and all three are pinrun's own:
      * PRICE_CEILING on EVERY level consumed, not merely the touch -- a sweep
        must not be allowed to buy at a price the bot is forbidden to pay.
      * net_edge on the RUNNING VWAP: we buy as deep as the edge survives, at
        the price actually paid, not at the touch we saw.
      * expected_value on the running VWAP, same reason.

    A level is taken whole-or-not: if adding min(level, remaining) would break
    a gate, the walk stops rather than solving for the partial quantity that
    just fits. Conservative by construction.

    Returns (n, vwap, levels_swept).
    """
    n = cost = 0.0
    lv = 0
    for c, q in ladder:
        if n >= size:
            break
        if float(c) > float(pinrun.PRICE_CEILING) + 1e-12:
            break
        take = min(float(q), float(size) - n)
        if take <= 0:
            break
        n2, cost2 = n + take, cost + take * float(c)
        vw = cost2 / n2
        if pinrun.net_edge(fair, vw, want) < pinrun.EDGE_FLOOR:
            break
        if pinrun.expected_value(vw) < pinrun.EV_FLOOR:
            break
        n, cost, lv = n2, cost2, lv + 1
    return (n, cost / n, lv) if n > 0 else (0.0, None, 0)


def hedge_fill(ladder, hold_n):
    """The hedge leg, same ladder arithmetic, gated by pinrun.hedge_ask_ok --
    a hedge helps iff its leg costs less than the $1 the pair pays."""
    n = cost = 0.0
    lv = 0
    for c, q in ladder:
        if n >= hold_n:
            break
        if not pinrun.hedge_ask_ok(c):
            break
        take = min(float(q), float(hold_n) - n)
        if take <= 0:
            break
        n, cost, lv = n + take, cost + take * float(c), lv + 1
    return (n, cost / n, lv) if n > 0 else (0.0, None, 0)


# ------------------------------------------------------------------ the pass
def hedge_try_ask(hp, thr, bk, ts, belief):
    """Record the opposite side's ASK LADDER at this instant; True if any.

    pinsim.hedge_try_ask in shape -- the gate is pinrun's own hedge_ask_ok()
    and the per-event retry is there for pinsim's reason (an ask alive for
    400 ms inside a second is an ask) -- but it stores the ladder for offline
    scoring instead of computing a fill, because how many contracts we hold is
    exactly what is being swept.
    """
    hb = pinsim.book_view(bk, ts)
    opp = "no" if hp["w"] == "yes" else "yes"
    ask = hb.get(f"{opp}_ask")
    asz = hb.get(f"{opp}_ask_size") or 0.0
    if not ask or asz <= 0 or not pinrun.hedge_ask_ok(ask):
        return False
    hp["h"][thr] = {"ask": float(ask), "size": float(asz),
                    "ladder": ladder_for(bk, opp),
                    "tau": int(hp["cs"] - (ts // 1000)),
                    "belief": round(float(belief), 6),
                    "edge_c": pinrun.hedge_edge_c(belief, ask)}
    return True


def walk_hour(stamp, mk, max_bar=None, log=None):
    """One book hour, ONE iteration of its event stream. Returns the rows.

    The order of operations is pinsim.run()'s: per second, the hedge/belief
    pass first (live runs it first); then, at every book event on a tracked
    market, the entry scan at that event's millisecond.
    """
    hour = pinsim.load_hour(stamp, mk)
    try:
        if not hour["ticks"]:
            return [], 0
        idx = pinsim.TapeIndex(sorted(hour["ticks"]))
        pend = {k: list(v) for k, v in hour["ticks"].items()}
        wk = pinsim.Walk(mk, idx, pend, per_event=True)
        watch = {}          # ticker -> belief/hedge state, opened at candidate 1
        # ticker -> the (touch, ladder, price) triples already emitted. See
        # dominated(): a candidate is emitted unless an earlier one was at
        # least as good on every axis a size-dependent gate can read.
        pareto = {}
        rows = []
        mismatch = 0
        for kind, tkk, sec, ts in wk.drive(hour["events"]):
            # ---- per-second belief pass, mirroring pinsim.run()'s A15 pass --
            if kind == 0:
                for htk, hp in watch.items():
                    if sec >= hp["cs"] - 1:
                        continue
                    if all(hp["h"][t] is not None for t in HEDGE_THRS):
                        continue
                    hsg = idx.sigma(hp["iid"])
                    if not hsg:
                        continue
                    hf = pinrun.fair(idx, hp["iid"], hp["cs"], sec,
                                     hp["strike"], hsg * pinrun.SIGMA_STRESS,
                                     round_digits=hp["digits"])
                    if hf is None:
                        continue
                    belief = hf if hp["w"] == "yes" else 1.0 - hf
                    hp["min_belief"] = min(hp["min_belief"], belief)
                    if hp["cs"] - sec >= pinrun.TAU_MIN:
                        hp["min_belief_t3"] = min(hp["min_belief_t3"], belief)
                    hp["last_belief"] = belief
                    hbk = wk.books.get(htk)
                    for thr in HEDGE_THRS:
                        if hp["h"][thr] is not None:
                            continue
                        if not pinrun.hedge_should_fire(belief, thr):
                            continue
                        if hp["alarm_sec"][thr] is None:
                            hp["alarm_sec"][thr] = sec
                            hp["alarm_tau"][thr] = hp["cs"] - sec
                        hp["tries"][thr] = hp["tries"].get(thr, 0) + 1
                        if hbk is not None:
                            hedge_try_ask(hp, thr, hbk, ts, belief)
                        if hp["h"][thr] is None and \
                                hp["tries"][thr] > pinrun.HEDGE_MAX_TRIES:
                            hp["h"][thr] = {"ask": None,
                                            "why": "no_ask_in_time"}
                continue
            bkk = wk.books[tkk]
            # the hedge's per-event retry, exactly as pinsim does it
            hp = watch.get(tkk)
            if hp is not None and sec < hp["cs"] - 1 and \
                    hp.get("last_belief") is not None:
                for thr in HEDGE_THRS:
                    if hp["h"][thr] is None and \
                            hp["alarm_sec"][thr] is not None:
                        hedge_try_ask(hp, thr, bkk, ts, hp["last_belief"])
            r = mk.get(tkk)
            if r is None:
                continue
            cs = int(float(r["close"]))
            tau = cs - sec
            if not (pinrun.TAU_MIN <= tau <= pinrun.TAU_MAX):
                continue
            iid = pindata.SERIES_TO_INDEX[r["series"]]
            if iid not in idx.ticks:
                continue
            b = pinsim.book_view(bkk, ts)
            if b["age_ms"] is None or b["age_ms"] > pinrun.MAX_BOOK_AGE_MS:
                continue
            # pinrun's OWN decision, at MIN_LEVEL so the depth gate admits
            # anything a size-1 order could fill; the ladder is recorded and
            # the depth gate re-applied per size offline.
            w, px, n, fv = pinsim.decide(
                idx, iid, cs, sec, float(r["strike"]),
                pindata.ROUND_DIGITS.get(r["series"]), b,
                float(pinrun.MIN_LEVEL))
            if w is None:
                continue
            depth = float(b.get(f"{w}_ask_size") or 0.0)
            lad = ladder_for(bkk, w)
            if not lad or abs(lad[0][0] - px) > 1e-9 or \
                    abs(lad[0][1] - depth) > 1e-9:
                mismatch += 1      # the ladder's touch must BE pinrun's touch
            sg = idx.sigma(iid)
            _, spot, iage = idx.spot(iid)
            if tkk not in watch:
                watch[tkk] = {
                    "w": w, "cs": cs, "iid": iid,
                    "strike": float(r["strike"]),
                    "digits": pindata.ROUND_DIGITS.get(r["series"]),
                    "min_belief": 1.0, "min_belief_t3": 1.0,
                    "last_belief": None,
                    "h": {t: None for t in HEDGE_THRS},
                    "alarm_sec": {t: None for t in HEDGE_THRS},
                    "alarm_tau": {t: None for t in HEDGE_THRS},
                    "tries": {}}
            # THE EMISSION RULE: three axes, because three gates read them.
            # The touch decides what TOUCH mode can fill; the ladder to the
            # ceiling decides what a SWEEP can fill; the price decides
            # IMPROVE_BY. A market is NEVER retired early -- an offer twenty
            # seconds later can still be the cheapest of the window, and
            # retiring on depth alone is what cost three fills.
            lad_qty = sum(q for c, q in lad
                          if c <= pinrun.PRICE_CEILING + 1e-12)
            prev = pareto.setdefault(tkk, [])
            if dominated(prev, depth, lad_qty, px):
                continue
            prev[:] = [e for e in prev
                       if not (depth >= e[0] - 1e-9 and lad_qty >= e[1] - 1e-9
                               and px <= e[2] + 1e-9)]
            prev.append((depth, lad_qty, px))
            rc = pinsim.record(fv, w, px, min(depth, float(pinrun.MIN_LEVEL)),
                               depth, tau, r["series"], sec, sg, spot,
                               b["age_ms"], iage)
            verdict, fired = pinrules.decide(PROFILE, rc)
            res = r["result"]
            yes = (str(res).lower() == "yes") if isinstance(res, str) \
                else float(res) >= 0.5
            rows.append({
                "kind": "row", "stamp": stamp, "ticker": tkk,
                "coin": r["series"], "cs": cs, "tau": int(tau),
                "entry_sec": int(sec), "entry_ts": int(ts),
                "want": w, "price": float(px), "depth": depth,
                "ladder": lad,
                "won": bool(yes == (w == "yes")),
                "fair": float(fv), "conf": rc["conf"],
                "discount_c": rc["discount_c"],
                "verdict": verdict, "fired": [x[0] for x in fired],
                "sigma": sg, "spot": spot,
                "book_age_ms": b["age_ms"], "index_age_s": iage,
            })
        # attach the belief path and the hedge ladders, the hour being over
        for row in rows:
            hp = watch.get(row["ticker"])
            if hp is None:
                continue
            row["min_belief"] = round(hp["min_belief"], 6)
            row["min_belief_t3"] = round(hp["min_belief_t3"], 6)
            row["hedge"] = {thkey(t): hp["h"][t] for t in HEDGE_THRS}
            row["alarm_sec"] = {thkey(t): hp["alarm_sec"][t]
                                for t in HEDGE_THRS}
            row["alarm_tau"] = {thkey(t): hp["alarm_tau"][t]
                                for t in HEDGE_THRS}
        if log:
            log(f"      events {wk.events:,} moments {wk.moments:,} "
                f"seq_back {getattr(hour['events'], 'seq_back', 0)} "
                f"gap_flags {getattr(hour['events'], 'gap_flags', 0)} "
                f"bad {wk.bad + (getattr(hour['events'], 'bad', 0) or 0)}")
        return rows, mismatch
    finally:
        # MEMORY. A one-pass run visits each hour once; caching it is waste,
        # and ~800 MB/hour of deltas OOM-killed three earlier runs while the
        # collector -- which outranks every job here -- was live.
        pinsim._HOUR_CACHE.pop(stamp, None)


def done_hours(path):
    """Hours already on disk, from their `hour` marker. An hour with ZERO rows
    still writes a marker, so resume never re-walks a quiet hour."""
    out = set()
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:                                   # noqa: BLE001
                continue
            if d.get("kind") == "hour":
                out.add(d["stamp"])
    return out


def run_pass(stamps, rows_path, log=print):
    """Walk `stamps`, checkpointing after EVERY hour.

    THE CHECKPOINT IS NOT OPTIONAL. Three jobs here were OOM-killed and two
    agents were cut off mid-run today; a 421-hour pass that cannot resume is a
    pass that never finishes.
    """
    mk = pinsim.load_markets()
    max_bar = max(depth_bar(s) for s in SIZES)
    done = done_hours(rows_path)
    todo = [s for s in stamps if s not in done]
    log(f"  {len(mk):,} settled markets; {len(stamps)} book hours requested, "
        f"{len(done)} already on disk, {len(todo)} to walk")
    log(f"  pass runs at pinrun.SIZE={pinrun.SIZE:g} (the largest size "
        f"scored, so net_edge's per-contract fee is minimal and the pass "
        f"cannot drop a candidate a larger size would take); depth gate at "
        f"MIN_LEVEL={pinrun.MIN_LEVEL:g}; ladder {LADDER_LEVELS} levels; "
        f"no early retirement -- a market is scanned to the end of its tau "
        f"window because a cheaper offer late in it is still news (largest "
        f"depth bar {max_bar:g})")
    t0 = time.time()
    total = mism = 0
    for i, stamp in enumerate(todo):
        rows, mm = walk_hour(stamp, mk, max_bar)
        mism += mm
        with open(rows_path, "a", encoding="utf-8", newline="\n") as fh:
            for row in rows:
                fh.write(json.dumps(row, separators=(",", ":")) + "\n")
            fh.write(json.dumps({"kind": "hour", "stamp": stamp,
                                 "rows": len(rows), "ladder_mismatch": mm,
                                 "t": int(time.time())}) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        total += len(rows)
        el = time.time() - t0
        log(f"    {stamp}  rows {len(rows):>3}  total {total:>5}  "
            f"[{i + 1}/{len(todo)}]  {el / 60.0:.1f} min elapsed, "
            f"~{(el / (i + 1)) * (len(todo) - i - 1) / 60.0:.0f} min left"
            + (f"  *** {mism} LADDER/TOUCH MISMATCHES ***" if mism else ""),
            flush=True)
    log(f"  pass complete: {total:,} rows over {len(todo)} new hours in "
        f"{(time.time() - t0) / 60.0:.1f} min; ladder/touch mismatches "
        f"{mism}")


def load_rows(path, stamps=None):
    rows, hours = [], []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:                                   # noqa: BLE001
                continue
            if d.get("kind") == "hour":
                if stamps is None or d["stamp"] in stamps:
                    hours.append(d["stamp"])
            elif d.get("kind") == "row":
                if stamps is None or d["stamp"] in stamps:
                    rows.append(d)
    return rows, sorted(set(hours))


# ---------------------------------------------------------------- the scorer
def minfill_sweep(rows, sizes, fracs, days, span, cut, mode="touch",
                  log=print):
    """Does the DEPTH FLOOR earn its keep at the size we now trade?

    `MIN_FILL_FRAC` refuses a moment unless at least that fraction of SIZE is
    resting. It is 0.50, and the 0.50 was measured at sizes 10 and 25 --
    floors of 5 and 12 contracts. At size 67 the same rule asks for 34, and
    nothing has ever tested it there.

    THE OPERATOR'S ARGUMENT, which this is built to test: a lower floor is
    more opportunity, and a small early fill is not purely a cost because
    IMPROVE_BY forces the NEXT buy in that close to be cheaper. The counter-
    argument on file is that the scrap burns one of MAX_PER_CLOSE slots and
    raises that same bar, trading a big cheap buy later for a small dear one
    now. Both are mechanisms; only the tape decides which dominates.

    Pure re-score of the cached ledger -- no tape walk. Every gate is
    pinrun's/pinsim's own, exactly as score() applies them.
    """
    out = {}
    saved = pinrun.MIN_FILL_FRAC
    fitrows = [r for r in rows if r["cs"] < cut]
    holrows = [r for r in rows if r["cs"] >= cut]
    try:
        for size in sizes:
            log(f"\n  SIZE {size}  (floor = max(MIN_LEVEL {pinrun.MIN_LEVEL:g}, "
                f"frac x {size}))")
            log(f"  {'frac':>6}{'floor':>7}{'closes':>8}{'fills':>7}"
                f"{'mean n':>8}{'loss%':>7}{'meanpx':>8}{'$/day@70%':>11}"
                f"{'worst close':>13}{'fit $/d':>9}{'hold $/d':>10}")
            base = None
            for fr in fracs:
                pinrun.MIN_FILL_FRAC = float(fr)
                a = summarise(score(rows, size, mode=mode)[0], days, span)
                fit = summarise(score(fitrows, size, mode=mode)[0], days, span)
                hol = summarise(score(holrows, size, mode=mode)[0], days, span)
                per70 = a["per_day"] * pinsim.LIVE_FILL_RATE
                if base is None:
                    base = per70
                out[(size, fr)] = {"all": a, "fit": fit, "holdout": hol,
                                   "per70": per70,
                                   "floor": depth_bar(size)}
                log(f"  {fr:>6.2f}{depth_bar(size):>7.1f}{a['closes']:>8}"
                    f"{a['fills']:>7}{(a['mean_take'] or 0):>8.1f}"
                    f"{(a['loss_rate'] or 0):>7.2f}"
                    f"{(a['mean_price'] or 0):>8.2f}{per70:>11.2f}"
                    f"{a['worst_close']:>13.2f}"
                    f"{fit['per_day'] * pinsim.LIVE_FILL_RATE:>9.2f}"
                    f"{hol['per_day'] * pinsim.LIVE_FILL_RATE:>10.2f}",
                    flush=True)
    finally:
        pinrun.MIN_FILL_FRAC = saved
    return out


def score(rows, size, hedge_thr=None, mode="touch"):
    """Score the candidate ledger at one SIZE. Returns (fills, refused).

    Every gate re-applied here is re-applied by CALLING pinrun/pinsim:
      pinrun.net_edge / expected_value / billed_fee
      pinsim.close_slot_ok / close_slot_book   (MAX_PER_CLOSE, MAX_PER_MARKET,
                                                IMPROVE_BY)
    in pinsim.run()'s own order, including its two rules that are easy to get
    wrong: failing the improve bar does NOT retire the market, and a market is
    retired the moment a candidate passes every gate -- bought OR refused by
    the profile's rules.

    mode 'touch' is pinrun as deployed. mode 'sweep' walks the ladder and pays
    the VWAP; see the module docstring for why that is a rule change and not
    just a better estimate.
    """
    saved = pinrun.SIZE
    pinrun.SIZE = float(size)          # net_edge reads this for the fee
    try:
        bar = depth_bar(size)
        per_close, decided = {}, set()
        fills, refused = [], []
        # SORT BY THE TIMESTAMP ALONE, AND LET THE SORT'S STABILITY DO THE
        # REST. Rows are appended in the tape's own event order, so a stable
        # sort on entry_ts leaves two candidates at the SAME millisecond in
        # the order the exchange sent them -- which is the order pinsim.run()
        # evaluates them in. Adding `ticker` as a tie-break re-orders those
        # alphabetically instead, and on the 72-hour acceptance window that
        # alone cost one fill of 156 and $0.85: whichever of two simultaneous
        # candidates books the close's slot first sets `best` for the
        # IMPROVE_BY bar, so the tie-break decides whether the other one can
        # still buy. With ts alone the anchor reproduces pinsim exactly.
        for r in sorted(rows, key=lambda x: x["entry_ts"]):
            tk, cs = r["ticker"], r["cs"]
            if tk in decided:
                continue
            lad = r.get("ladder") or [[r["price"], r["depth"]]]
            if mode == "sweep":
                n, px, lv = sweep_fill(lad, size, r["fair"], r["want"])
            else:
                n, px, lv = touch_fill(r["depth"], r["price"], size)
            if n < bar or px is None:
                continue               # pinrun's too_shallow, at THIS size
            if pinrun.net_edge(r["fair"], px, r["want"]) < pinrun.EDGE_FLOOR:
                continue
            if pinrun.expected_value(px) < pinrun.EV_FLOOR:
                continue
            if px > pinrun.PRICE_CEILING + 1e-12:
                continue
            if pinsim.close_slot_ok(per_close.get(cs), tk, None):
                continue
            if pinsim.close_slot_ok(per_close.get(cs), tk, px):
                continue               # the improve bar -- no retirement
            decided.add(tk)
            if r["verdict"] == "refuse":
                refused.append(dict(r, take_n=0.0, pnl=0.0))
                continue
            pnl = (n * (1.0 - px) if r["won"] else -n * px) \
                - pinrun.billed_fee(px, n)
            hedged = None
            if hedge_thr is not None:
                k = thkey(hedge_thr)
                h = (r.get("hedge") or {}).get(k)
                asec = (r.get("alarm_sec") or {}).get(k)
                if h and h.get("ask") and asec is not None \
                        and asec > r["entry_sec"]:
                    hlad = h.get("ladder") or [[h["ask"], h["size"]]]
                    if mode != "sweep":
                        hlad = [[h["ask"], h["size"]]]
                    hn, hpx, hlv = hedge_fill(hlad, n)
                    if hn > 0:
                        fee = pinrun.billed_fee(hpx, hn)
                        if r["won"]:
                            # the pair pays $1: we forgo (1-px), pay the ask
                            pnl -= hn * hpx + fee
                        else:
                            # the loss shrinks from px to px + ask - 1
                            pnl += hn * (1.0 - hpx) - fee
                        hedged = {"ask": hpx, "n": hn, "levels": hlv,
                                  "tau": h.get("tau"), "alarm_sec": asec}
            fills.append(dict(r, take_n=n, price_paid=px, levels=lv,
                              slip_c=round(100.0 * (px - r["price"]), 4),
                              pnl=pnl, hedged=hedged, notional=n * px))
            pinsim.close_slot_book(per_close, cs, tk, px)
        return fills, refused
    finally:
        pinrun.SIZE = saved


# ------------------------------------------------------------------ statistics
def utcday(sec):
    return time.strftime("%Y-%m-%d", time.gmtime(sec))


def span_days(hours, newest_settle=None):
    """The window the $/day denominator divides by: the whole replayed tape,
    idle hours included, truncated at the newest settlement because a book
    hour after it cannot resolve and can earn nothing."""
    if not hours:
        return 0, 0.0, []
    starts = [calendar.timegm(time.strptime(h, "%Y%m%dT%H")) for h in hours]
    lo, hi = min(starts), max(starts) + 3600
    if newest_settle:
        hi = min(hi, float(newest_settle))
    days = []
    d = lo - (lo % 86400)
    while d < hi:
        days.append(utcday(d))
        d += 86400
    return lo, (hi - lo) / 86400.0, days


def summarise(fills, days, span):
    """Everything the operator's constraint needs: money, its interval, and
    the worst single thing that happened."""
    from pincross import cp_interval
    out = {"fills": 0, "closes": 0, "wins": 0, "losses": 0,
           "pnl": 0.0, "mean_price": None, "loss_rate": None, "ci": None,
           "closes_lost": 0, "close_loss_rate": None, "close_ci": None,
           "per_day": 0.0, "peak_capital": 0.0, "roc": None,
           "worst_close": 0.0, "worst_close_id": None,
           "worst_day": 0.0, "worst_day_id": None, "boot": None,
           "days_traded": 0, "days_positive": 0, "mean_levels": None,
           "mean_slip_c": None, "mean_take": None, "bank_needed": 0.0,
           "hedged_fills": 0}
    if not fills:
        return out
    byclose, byday = {}, {}
    for f in fills:
        byclose.setdefault(f["cs"], []).append(f)
        byday[utcday(f["cs"])] = byday.get(utcday(f["cs"]), 0.0) + f["pnl"]
    L = [f for f in fills if not f["won"]]
    lo, hi = cp_interval(len(L), len(fills))
    lost_closes = [c for c, v in byclose.items()
                   if any(not x["won"] for x in v)]
    clo, chi = cp_interval(len(lost_closes), len(byclose))
    out.update(
        fills=len(fills),
        closes=len(byclose), wins=len(fills) - len(L), losses=len(L),
        pnl=round(sum(f["pnl"] for f in fills), 4),
        mean_price=round(100.0 * sum(f["price_paid"] for f in fills)
                         / len(fills), 3),
        mean_take=round(sum(f["take_n"] for f in fills) / len(fills), 2),
        mean_levels=round(sum(f["levels"] for f in fills) / len(fills), 2),
        mean_slip_c=round(sum(f["slip_c"] for f in fills) / len(fills), 3),
        hedged_fills=sum(1 for f in fills if f.get("hedged")),
        loss_rate=round(100.0 * len(L) / len(fills), 3),
        ci=[round(100 * lo, 3), round(100 * hi, 3)],
        closes_lost=len(lost_closes),
        close_loss_rate=round(100.0 * len(lost_closes) / len(byclose), 3),
        close_ci=[round(100 * clo, 3), round(100 * chi, 3)],
        peak_capital=round(max(sum(x["notional"] for x in v)
                               for v in byclose.values()), 2),
        worst_close=round(min(sum(x["pnl"] for x in v)
                              for v in byclose.values()), 4),
        worst_day=round(min(byday.values()), 4),
        days_traded=len(byday),
        days_positive=sum(1 for v in byday.values() if v > 0))
    out["worst_close_id"] = min(byclose,
                                key=lambda c: sum(x["pnl"] for x in byclose[c]))
    out["worst_day_id"] = min(byday, key=lambda d: byday[d])
    out["per_day"] = round(out["pnl"] / span, 4) if span else 0.0
    out["roc"] = round(100.0 * out["per_day"] / out["peak_capital"], 2) \
        if out["peak_capital"] else None
    # THE BANK. pinrun line 202: the deployment rail requires a brake of at
    # least 1.5x the worst close. A size whose worst close needs a bank we do
    # not have is not scalable however good its $/day.
    out["bank_needed"] = round(BRAKE_HEADROOM * abs(out["worst_close"]), 2)
    # BLOCK BOOTSTRAP BY DAY. Resampling FILLS would treat the twelve series
    # that settle on the same second as twelve independent draws (rho ~ 0.8)
    # and a day's whole tape as exchangeable; the block is the DAY, and idle
    # days are in the list so they dilute as they do in life.
    if days:
        vec = [byday.get(d, 0.0) for d in days]
        rnd = random.Random(BOOT_SEED)
        n = len(vec)
        draws = [sum(vec[rnd.randrange(n)] for _ in range(n)) / n
                 for _ in range(BOOT_DRAWS)]
        draws.sort()
        out["boot"] = [round(draws[int(0.025 * BOOT_DRAWS)], 3),
                       round(draws[int(0.975 * BOOT_DRAWS)], 3)]
        out["boot_days"] = n
    return out


def split_closes(rows, frac=0.70):
    """pinsim.report()'s own 70/30 split, on the same rule: order the closes
    and cut at the 70th percentile close, so no close straddles the split."""
    closes = sorted(set(r["cs"] for r in rows))
    return closes[int(frac * len(closes))] if closes else 0


def saturation(curve):
    """(best_size, best_per_day, first_falling_size). `curve` is
    [(size, $/day)] in increasing size."""
    if not curve:
        return None, None, None
    best = max(curve, key=lambda x: x[1])
    fall = None
    for (s0, v0), (s1, v1) in zip(curve, curve[1:]):
        if v1 < v0 and fall is None:
            fall = s1
    return best[0], best[1], fall


# ------------------------------------------------------------------ self-test
def selftest():
    print("SELF-TEST -- pinlevels")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    def fee(p, n):
        return math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000.0

    # ---- (1) ONE PASS IS ENOUGH: the emission rule, as a property ----------
    bars = sorted(depth_bar(s) for s in SIZES)
    mx = max(bars)
    rnd = random.Random(7)
    pool = [1.0, 2.0, 3.0, 5.0, 9.0, 12.0, 20.0, 40.0, 63.0, 100.0, 400.0,
            1500.0]
    prices = [0.80, 0.90, 0.94, 0.95, 0.96, 0.97, 0.975, 0.98]
    bad = 0
    for _ in range(300):
        # each candidate is a TRIPLE: touch quantity, ladder quantity (always
        # at least the touch, since the touch is the ladder's first level),
        # and price
        cand = []
        for _k in range(20):
            t = rnd.choice(pool)
            cand.append((t, t + rnd.choice([0.0, 0.0, 5.0, 500.0]),
                         rnd.choice(prices)))
        rec, prev = [], []
        for i, (t, l, pz) in enumerate(cand):
            if dominated(prev, t, l, pz):
                continue
            prev[:] = [e for e in prev
                       if not (t >= e[0] and l >= e[1] and pz <= e[2])]
            prev.append((t, l, pz))
            rec.append((i, t, l, pz))
        # ANY monotone gate -- deeper is easier, cheaper is easier -- must be
        # first passed by a row that was EMITTED.
        for bar in bars:
            for col in (0, 1):
                for lim in prices:
                    fa = next((i for i, c in enumerate(cand)
                               if c[col] >= bar and c[2] <= lim), None)
                    fr = next((i for i, t, l, pz in rec
                               if (t, l)[col] >= bar and pz <= lim), None)
                    if fa != fr:
                        bad += 1
    ck(bad == 0,
       "EMISSION RULE: for every combination of a depth bar (either measure) "
       "and a price limit -- the shape of too_shallow, of the ladder fill and "
       "of IMPROVE_BY -- the first EMITTED row that passes is the first "
       f"CANDIDATE that passes. 300 random walks, {bad} violations. The "
       f"depth-only version of this rule cost exactly 3 of pinsim's 156 fills "
       f"on the acceptance window, every one a SECOND fill of a close")

    # ---- (2) THE LADDER: orientation, and a VWAP done BY HAND -------------
    bk = pindata.Book()
    # a NO bid at q sells us a YES at (1-q). Bids at 8c, 6c, 4c ->
    # YES costs 92c, 94c, 96c.
    bk.no = {0.08: 10.0, 0.06: 15.0, 0.04: 100.0}
    bk.yes = {0.90: 7.0, 0.88: 30.0}
    lad = ladder_for(bk, "yes")
    ck(lad == [[0.92, 10.0], [0.94, 15.0], [0.96, 100.0]],
       f"LADDER for YES comes from the NO bids, dearest bid first, as cost "
       f"(1-q): {lad}")
    ck(ladder_for(bk, "no") == [[0.10, 7.0], [0.12, 30.0]],
       f"and the NO ladder from the YES bids: {ladder_for(bk, 'no')}")
    bv = pinsim.book_view(bk, 1000)
    ck(abs(bv["yes_ask"] - lad[0][0]) < 1e-12
       and abs(bv["yes_ask_size"] - lad[0][1]) < 1e-12,
       "and ladder[0] IS pinsim.book_view's touch, price and size -- the two "
       "readings of the same book agree")

    sv = {k: getattr(pinrun, k) for k in
          ("MAX_PER_CLOSE", "MAX_PER_MARKET", "IMPROVE_BY", "MIN_FILL_FRAC",
           "MIN_LEVEL", "EDGE_FLOOR", "EV_FLOOR", "PRICE_CEILING", "SIZE")}
    try:
        pinrun.MAX_PER_CLOSE, pinrun.MAX_PER_MARKET = 2, 1
        pinrun.IMPROVE_BY, pinrun.MIN_FILL_FRAC = 0.005, 0.5
        pinrun.MIN_LEVEL, pinrun.EDGE_FLOOR = 1.0, 0.003
        pinrun.EV_FLOOR, pinrun.PRICE_CEILING = 0.003, 0.98
        pinrun.SIZE = 20.0

        # 25 contracts off that ladder: 10 at 92c, 15 at 94c.
        n_, vw_, lv_ = sweep_fill(lad, 25, 0.999, "yes")
        hand = (10 * 0.92 + 15 * 0.94) / 25.0
        ck(n_ == 25.0 and abs(vw_ - hand) < 1e-12 and lv_ == 2,
           f"SWEEP VWAP BY HAND: 25 contracts = 10 at 92c + 15 at 94c, VWAP "
           f"(10*0.92 + 15*0.94)/25 = {100 * hand:.2f}c over 2 levels "
           f"(got {100 * vw_:.2f}c, {lv_} levels)")
        n2, vw2, lv2 = sweep_fill(lad, 8, 0.999, "yes")
        ck(n2 == 8.0 and abs(vw2 - 0.92) < 1e-12 and lv2 == 1,
           "and a size INSIDE the touch pays the touch and sweeps one level")
        n3, vw3, lv3 = sweep_fill(lad, 200, 0.999, "yes")
        hand3 = (10 * 0.92 + 15 * 0.94 + 100 * 0.96) / 125.0
        ck(n3 == 125.0 and abs(vw3 - hand3) < 1e-12,
           f"and size 200 against a 125-deep ladder fills 125 at "
           f"{100 * hand3:.3f}c -- a PARTIAL, priced on what was there")
        # the ceiling stops the walk dead, on EVERY level
        lad_c = [[0.92, 5.0], [0.985, 500.0]]
        n4, vw4, lv4 = sweep_fill(lad_c, 100, 0.999, "yes")
        ck(n4 == 5.0 and abs(vw4 - 0.92) < 1e-12 and lv4 == 1,
           f"PRICE_CEILING applies to EVERY level swept: a 98.5c level is not "
           f"consumed at a ceiling of {pinrun.PRICE_CEILING}, so the fill "
           f"stops at 5 contracts (got {n4})")
        # ... and the running EDGE gate stops the walk where the ceiling
        # would not. (At the LIVE gate the ceiling binds first: EV only falls
        # under its floor above ~98.65c, which is already over the 98c
        # ceiling. So this plants a fair value close to the price, which is
        # the only way the edge gate can bite below the ceiling.)
        lad_e = [[0.96, 5.0], [0.979, 5000.0]]
        n5, vw5, _ = sweep_fill(lad_e, 1000, 0.982, "yes")
        _vw_all = (5 * 0.96 + 995 * 0.979) / 1000.0
        ck(n5 == 5.0,
           f"and the running-VWAP EDGE gate stops the walk where the ceiling "
           f"would not: 97.9c is under the {pinrun.PRICE_CEILING} ceiling, but "
           f"against a fair of 98.2c a VWAP of {100 * _vw_all:.3f}c nets "
           f"{100 * pinrun.net_edge(0.982, _vw_all, 'yes'):+.3f}c against a "
           f"floor of {100 * pinrun.EDGE_FLOOR:.1f}c, so the fill stops at 5 "
           f"(got {n5})")
        ck(pinrun.expected_value(pinrun.PRICE_CEILING) > pinrun.EV_FLOOR,
           f"-- and note which gate is operative at the live numbers: EV at "
           f"the {pinrun.PRICE_CEILING} ceiling is still "
           f"{100 * pinrun.expected_value(pinrun.PRICE_CEILING):+.2f}c, so on "
           f"a real sweep it is the CEILING that stops the walk, not EV")

        # ---- (3) THE SCORER, on a ledger whose answer is done BY HAND -----
        def row(tk, cs, sec, px, depth, won, conf=0.999, verdict="allow",
                hedge=None, alarm=None, ladder=None):
            return {"kind": "row", "stamp": "SELFTEST", "ticker": tk,
                    "coin": "KXBTC15M", "cs": cs, "tau": cs - sec,
                    "entry_sec": sec, "entry_ts": sec * 1000,
                    "want": "yes", "price": px, "depth": depth,
                    "ladder": ladder or [[px, depth]], "won": won,
                    "fair": conf, "conf": conf,
                    "discount_c": round(100.0 * (conf - px), 2),
                    "verdict": verdict, "fired": [],
                    "hedge": {thkey(t): (hedge if t == 0.80 else None)
                              for t in HEDGE_THRS},
                    "alarm_sec": {thkey(t): (alarm if t == 0.80 else None)
                                  for t in HEDGE_THRS}}
        # close A: three markets. The third must be refused by MAX_PER_CLOSE.
        A = [row("A1", 1000, 975, 0.90, 500.0, True),
             row("A2", 1000, 976, 0.89, 500.0, True),
             row("A3", 1000, 977, 0.88, 500.0, True)]
        # close B: ONE market with 6 contracts resting -- fine for size 5
        # (bar 2.5), too shallow for size 20 (bar 10).
        B = [row("B1", 2000, 1975, 0.90, 6.0, True)]
        # close C: a LOSS, deep, so it is scored at every size.
        C = [row("C1", 3000, 2975, 0.90, 500.0, False)]
        led = A + B + C

        f5, r5 = score(led, 5)
        want5 = (5 * 0.10 - fee(0.90, 5)) + (5 * 0.11 - fee(0.89, 5)) \
            + (5 * 0.10 - fee(0.90, 5)) + (-5 * 0.90 - fee(0.90, 5))
        got5 = sum(x["pnl"] for x in f5)
        ck([x["ticker"] for x in f5] == ["A1", "A2", "B1", "C1"],
           f"SIZE 5 fills A1, A2, B1, C1 -- A3 refused by MAX_PER_CLOSE=2 "
           f"(got {[x['ticker'] for x in f5]})")
        ck(abs(got5 - want5) < 1e-9 and abs(got5 - (-3.0788)) < 1e-9,
           f"SIZE 5 P&L is the hand figure -$3.0788 (got ${got5:+.4f})")

        f20, r20 = score(led, 20)
        want20 = (20 * 0.10 - fee(0.90, 20)) + (20 * 0.11 - fee(0.89, 20)) \
            + (-20 * 0.90 - fee(0.90, 20))
        got20 = sum(x["pnl"] for x in f20)
        ck([x["ticker"] for x in f20] == ["A1", "A2", "C1"],
           f"SIZE 20 drops B1 -- 6 contracts resting against a bar of "
           f"{depth_bar(20):g} (got {[x['ticker'] for x in f20]})")
        ck(abs(got20 - want20) < 1e-9 and abs(got20 - (-14.1891)) < 1e-9,
           f"SIZE 20 P&L is the hand figure -$14.1891 (got ${got20:+.4f})")
        ck(f5[2]["ticker"] == "B1" and f5[2]["take_n"] == 5.0,
           "and B1 at size 5 takes 5 of the 6 resting")

        # the SWEEP mode on the same ledger, with a real ladder on B1
        Bl = [row("B1", 2000, 1975, 0.92, 10.0, True,
                  ladder=[[0.92, 10.0], [0.94, 15.0], [0.96, 100.0]])]
        fs, _ = score(Bl, 25, mode="sweep")
        wanth = (10 * 0.92 + 15 * 0.94) / 25.0
        wants = 25 * (1 - wanth) - fee(wanth, 25)
        ck(fs and fs[0]["take_n"] == 25.0
           and abs(fs[0]["pnl"] - wants) < 1e-9
           and fs[0]["levels"] == 2
           and abs(fs[0]["slip_c"] - 100 * (wanth - 0.92)) < 1e-9,
           f"SWEEP SCORING: 25 contracts at a hand VWAP of {100 * wanth:.2f}c "
           f"pays ${wants:+.4f} with {100 * (wanth - 0.92):.2f}c of slippage "
           f"against the touch (got ${fs[0]['pnl']:+.4f}, "
           f"{fs[0]['slip_c']:.2f}c)")
        ft, _ = score(Bl, 25, mode="touch")
        ck(ft == [],
           "and the same row in TOUCH mode does not fill at all -- 10 resting "
           "against a bar of 12.5 -- which is why the sweep table is a RULE "
           "CHANGE and not merely a better estimate")

        # take_n capped by depth in touch mode
        D = [row("D1", 4000, 3975, 0.90, 40.0, True)]
        f75, _ = score(D, 75)
        ck(f75 and f75[0]["take_n"] == 40.0
           and abs(f75[0]["pnl"] - (40 * 0.10 - fee(0.90, 40))) < 1e-9,
           "PARTIAL FILL: 40 resting against size 75 (bar 37.5) takes 40, and "
           "the fee is billed on 40")

        # TIE-BREAK: two candidates at the same millisecond must be scored in
        # the order they arrive, because the first to book the slot sets the
        # IMPROVE_BY bar for the second.
        T = [row("T1", 8000, 7975, 0.90, 500.0, True),
             row("T2", 8000, 7975, 0.899, 500.0, True)]
        T[1]["entry_ts"] = T[0]["entry_ts"]           # the SAME millisecond
        fT, _ = score(T, 20)
        fT2, _ = score([T[1], T[0]], 20)
        ck([x["ticker"] for x in fT] == ["T1"]
           and [x["ticker"] for x in fT2] == ["T2"],
           f"TIE-BREAK: at one millisecond the FIRST row in tape order books "
           f"the slot and the second fails the improve bar -- reversing the "
           f"input reverses the winner ({[x['ticker'] for x in fT]} then "
           f"{[x['ticker'] for x in fT2]}), so the sort must be stable on "
           f"entry_ts and must NOT add a tie-break of its own")

        # the improve bar, and that failing it does NOT retire the market
        E = [row("E1", 5000, 4970, 0.90, 500.0, True),
             row("E2", 5000, 4971, 0.899, 500.0, True),   # not 0.5c cheaper
             row("E3", 5000, 4972, 0.80, 500.0, True)]    # cheaper: allowed
        fE, _ = score(E, 20)
        ck([x["ticker"] for x in fE] == ["E1", "E3"],
           f"IMPROVE_BY: E2 at 89.9c is refused against a best of 90c, and E3 "
           f"at 80c still fills (got {[x['ticker'] for x in fE]})")

        # the profile's dump rule: a refused row RETIRES its market
        F = [row("F1", 6000, 5975, 0.80, 500.0, True, verdict="refuse"),
             row("F2", 6000, 5976, 0.70, 500.0, True)]
        fF, rF = score(F, 20)
        ck([x["ticker"] for x in fF] == ["F2"]
           and [x["ticker"] for x in rF] == ["F1"],
           "a rule-refused candidate is counted as refused and retires ITS "
           "market, while another market in the close still trades")
        ck(score([F[0]], 20)[0] == [],
           "and a refused market alone produces no fill")

        # ---- the HEDGE branch, both signs, priced by hand -----------------
        Ch = [row("C1", 3000, 2975, 0.90, 500.0, False,
                  hedge={"ask": 0.55, "size": 500.0, "tau": 12,
                         "belief": 0.40}, alarm=2988)]
        fh, _ = score(Ch, 20, hedge_thr=0.80)
        want_h = -20 * 0.90 - fee(0.90, 20) + 20 * (1 - 0.55) - fee(0.55, 20)
        # BY HAND IN DECIMAL: -18.00 - 0.1260 + 9.00 - 0.3465 = -$9.4725. The
        # code gives -$9.4726, and the extra $0.0001 is REAL: billed_fee
        # ceilings to the next $0.0001 and 0.07*0.55*0.45*20 lands at
        # 0.3465000000000001 in binary, so the fee bills 0.3466. One fee tick,
        # in the conservative direction, and pinrun's own arithmetic.
        ck(abs(fh[0]["pnl"] - want_h) < 1e-9
           and abs(want_h - (-9.4725)) <= 1.0001e-4,
           f"HEDGE ON a LOSER: the 90c loss is locked with 45c recovered, "
           f"-$9.4725 by hand (billed -$9.4726, one fee tick worse) instead "
           f"of -$18.126 (got ${fh[0]['pnl']:+.4f})")
        Ah = [row("A1", 1000, 975, 0.90, 500.0, True,
                  hedge={"ask": 0.30, "size": 500.0, "tau": 14,
                         "belief": 0.60}, alarm=988)]
        fa, _ = score(Ah, 20, hedge_thr=0.80)
        want_a = 20 * 0.10 - fee(0.90, 20) - 20 * 0.30 - fee(0.30, 20)
        ck(abs(fa[0]["pnl"] - want_a) < 1e-9,
           f"HEDGE ON a WINNER (a false alarm) costs exactly the ask: "
           f"${want_a:+.4f} against ${20 * 0.10 - fee(0.90, 20):+.4f} "
           f"unhedged (got ${fa[0]['pnl']:+.4f})")
        Bh = [row("A1", 1000, 975, 0.90, 500.0, True,
                  hedge={"ask": 0.30, "size": 500.0}, alarm=970)]
        fb, _ = score(Bh, 20, hedge_thr=0.80)
        ck(abs(fb[0]["pnl"] - (20 * 0.10 - fee(0.90, 20))) < 1e-9,
           "and an alarm that fired BEFORE the entry second is not applied -- "
           "we cannot hedge a position we did not hold yet")
        Nh = [row("C1", 3000, 2975, 0.90, 500.0, False,
                  hedge={"ask": None, "why": "no_ask_in_time"}, alarm=2988)]
        fn, _ = score(Nh, 20, hedge_thr=0.80)
        ck(abs(fn[0]["pnl"] - (-20 * 0.90 - fee(0.90, 20))) < 1e-9,
           "and `no_ask_in_time` leaves the loss unhedged, at its full size")
        Ph = [row("C1", 3000, 2975, 0.90, 500.0, False,
                  hedge={"ask": 0.55, "size": 7.0}, alarm=2988)]
        fp, _ = score(Ph, 20, hedge_thr=0.80)
        want_p = -20 * 0.90 - fee(0.90, 20) + 7 * (1 - 0.55) - fee(0.55, 7)
        ck(abs(fp[0]["pnl"] - want_p) < 1e-9,
           f"and a 7-contract ask hedges only 7 of the 20 held "
           f"(${want_p:+.4f})")
        Lh = [row("C1", 3000, 2975, 0.90, 500.0, False,
                  hedge={"ask": 0.55, "size": 7.0,
                         "ladder": [[0.55, 7.0], [0.60, 50.0]]},
                  alarm=2988)]
        fl, _ = score(Lh, 20, hedge_thr=0.80, mode="sweep")
        hv = (7 * 0.55 + 13 * 0.60) / 20.0
        want_l = -20 * 0.90 - fee(0.90, 20) + 20 * (1 - hv) - fee(hv, 20)
        ck(abs(fl[0]["pnl"] - want_l) < 1e-9,
           f"and in SWEEP mode the hedge walks its own ladder too -- 7 at 55c "
           f"then 13 at 60c, VWAP {100 * hv:.2f}c (${want_l:+.4f})")

        # ---- NOTHING PLANTED: a world with no tradeable candidate --------
        Z = [row("Z1", 7000, 6975, 0.99, 500.0, True)]
        ck(score(Z, 20)[0] == [],
           f"a 99c offer produces NO fill at any size -- over the "
           f"{pinrun.PRICE_CEILING} ceiling, and EV there is "
           f"{100 * pinrun.expected_value(0.99):+.3f}c against a floor of "
           f"{100 * pinrun.EV_FLOOR:.1f}c")
        ck(score([row("Z2", 7000, 6975, 0.90, 0.5, True)], 1)[0] == [],
           "and half a contract resting is below MIN_LEVEL at EVERY size, "
           "including size 1")

        # ---- the statistics, on the same hand-computed ledger ------------
        s = summarise(score(led, 20)[0], ["1970-01-01"], 1.0)
        ck(s["fills"] == 3 and s["closes"] == 2 and s["losses"] == 1,
           f"n is reported as FILLS and CLOSES, never decision moments "
           f"({s['fills']} fills, {s['closes']} closes)")
        ck(abs(s["peak_capital"] - (20 * 0.90 + 20 * 0.89)) < 1e-6,
           f"PEAK CONCURRENT CAPITAL is the largest single CLOSE's notional, "
           f"$35.80 -- not the turnover of "
           f"${sum(x['notional'] for x in score(led, 20)[0]):.2f} "
           f"(got ${s['peak_capital']:.2f})")
        ck(abs(s["worst_close"] - (-20 * 0.90 - fee(0.90, 20))) < 1e-9
           and abs(s["bank_needed"] - 1.5 * 18.126) < 0.01,
           f"the WORST SINGLE CLOSE is -$18.126 and the bank it needs at the "
           f"1.5x brake rail is ${s['bank_needed']:.2f}")
        cur = [(5, 1.0), (10, 2.0), (20, 2.5), (50, 2.4), (100, 1.0)]
        ck(saturation(cur) == (20, 2.5, 50),
           f"SATURATION: the curve peaks at size 20 and first falls at 50 "
           f"({saturation(cur)})")
    finally:
        for k, v in sv.items():
            setattr(pinrun, k, v)
    # ---- MIN_FILL_FRAC sweep -------------------------------------------
    # Two invariants. A lower floor can only ADD fills (it never refuses a
    # moment the higher floor accepted), and the sweep must put the live
    # constant back -- it is mutating a module global that pinrun trades on.
    _mf0 = pinrun.MIN_FILL_FRAC
    _sw = [row("MF1", 1000, 980, 0.96, 12.0, True),      # 12 resting
           row("MF2", 2000, 1980, 0.96, 60.0, True)]     # 60 resting
    _r = minfill_sweep(_sw, [50.0], [1.0, 0.5, 0.1], ["d"], 1.0, 0,
                       log=lambda *a, **k: None)
    ck(abs(pinrun.MIN_FILL_FRAC - _mf0) < 1e-12,
       f"the sweep MUST restore pinrun.MIN_FILL_FRAC (was {_mf0}, now "
       f"{pinrun.MIN_FILL_FRAC}) -- it is the live trading constant")
    _f = [_r[(50.0, x)]["all"]["fills"] for x in (1.0, 0.5, 0.1)]
    ck(_f[0] <= _f[1] <= _f[2],
       f"a LOWER floor can only add fills, never remove one: got {_f} at "
       f"fracs 1.0, 0.5, 0.1")
    ck(_r[(50.0, 1.0)]["floor"] == 50.0 and _r[(50.0, 0.5)]["floor"] == 25.0,
       "the floor reported must be frac x size, via pinrun's own depth_bar")
    ck(_f[0] == 1 and _f[2] == 2,
       f"planted: a 12-deep and a 60-deep moment at size 50 -- floor 50 takes "
       f"only the deep one, floor 5 takes both. got {_f}")

    ck(abs(pinrun.PIN - 0.995) < 1e-12 and pinrun.MAX_PER_CLOSE == 2
       and abs(pinrun.PRICE_CEILING - 0.98) < 1e-12,
       f"and the live constants are put back exactly (PIN {pinrun.PIN}, "
       f"MAX_PER_CLOSE {pinrun.MAX_PER_CLOSE}, ceiling "
       f"{pinrun.PRICE_CEILING})")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ---------------------------------------------------------------- the report
def table(rows, hours, sizes=SIZES, log=print, newest=None, mode="touch"):
    lo, span, days = span_days(hours, newest)
    cut = split_closes(rows)
    out = {"span_days": span, "hours": len(hours), "cut_close": cut,
           "days": len(days), "mode": mode, "sizes": {}}
    log(f"\n  MODE {mode.upper()} -- window: {len(hours)} book hours, "
        f"{time.strftime('%Y-%m-%dT%HZ', time.gmtime(lo))} onward, "
        f"span {span:.3f} days over {len(days)} UTC days; 70/30 split at "
        f"close {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(cut))}")
    log(f"  {'size':>6}{'closes':>7}{'fills':>7}{'mean n':>8}{'lvls':>6}"
        f"{'slip c':>8}{'loss%':>7}{'meanpx':>8}{'$/day ceil':>11}"
        f"{'$/day@70%':>11}{'peak $':>10}{'%ROC/d':>8}{'hedge $/d':>11}"
        f"{'worst close':>13}")
    fitrows = [r for r in rows if r["cs"] < cut]
    holrows = [r for r in rows if r["cs"] >= cut]
    for s in sizes:
        a = summarise(score(rows, s, mode=mode)[0], days, span)
        h = summarise(score(rows, s, hedge_thr=LIVE_HEDGE_BELIEF,
                            mode=mode)[0], days, span)
        fit = summarise(score(fitrows, s, mode=mode)[0], days, span)
        hol = summarise(score(holrows, s, mode=mode)[0], days, span)
        out["sizes"][str(s)] = {"all": a, "hedge_on": h, "fit": fit,
                                "holdout": hol}
        log(f"  {s:>6}{a['closes']:>7}{a['fills']:>7}"
            f"{(a['mean_take'] or 0):>8.1f}{(a['mean_levels'] or 0):>6.2f}"
            f"{(a['mean_slip_c'] or 0):>8.3f}"
            f"{(a['loss_rate'] or 0):>7.2f}{(a['mean_price'] or 0):>8.2f}"
            f"{a['per_day']:>11.2f}"
            f"{a['per_day'] * pinsim.LIVE_FILL_RATE:>11.2f}"
            f"{a['peak_capital']:>10.2f}{(a['roc'] or 0):>8.1f}"
            f"{h['per_day']:>11.2f}{a['worst_close']:>13.2f}", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--pass", dest="do_pass", action="store_true",
                    help="walk the tape and append candidate rows")
    ap.add_argument("--score", action="store_true",
                    help="score the rows already on disk")
    ap.add_argument("--rows", default=ROWS)
    ap.add_argument("--hours", type=int, default=10000)
    ap.add_argument("--end", default=None)
    ap.add_argument("--first", default=None,
                    help="END,HOURS -- walk this window FIRST, so the "
                         "acceptance anchor can be scored hours before the "
                         "whole pass finishes")
    ap.add_argument("--anchor", default=None,
                    help="END,HOURS -- score ONLY that window (anchor 1)")
    ap.add_argument("--size", type=float, default=None,
                    help="with --anchor, the single size to score")
    ap.add_argument("--report", default=None,
                    help="write the markdown report here")
    ap.add_argument("--profile", default="default")
    ap.add_argument("--minfill", default=None,
                    help="SIZES:FRACS -- re-score the cached ledger at these "
                         "MIN_FILL_FRAC values, e.g. 20,67:1.0,0.5,0.25,0.1,0")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    global PROFILE
    PROFILE = pinrules.load(a.profile)
    pinsim.apply_profile(PROFILE)
    sched = [k for k, v in PROFILE["params"].items() if pinrules.is_schedule(v)]
    if sched:
        raise SystemExit(
            f"profile {PROFILE['name']} SCHEDULES {sched}. A schedule makes "
            f"the decision depend on the record, so one size-generic pass is "
            f"not valid. Refusing rather than reporting a wrong number.")
    print(f"  profile {PROFILE['name']} sha {PROFILE['_sha']}: "
          f"PIN {pinrun.PIN}, ceiling {pinrun.PRICE_CEILING}, tau "
          f"{pinrun.TAU_MIN}-{pinrun.TAU_MAX}, MAX_PER_CLOSE "
          f"{pinrun.MAX_PER_CLOSE}, MAX_PER_MARKET {pinrun.MAX_PER_MARKET}, "
          f"IMPROVE_BY {pinrun.IMPROVE_BY}, MIN_FILL_FRAC "
          f"{pinrun.MIN_FILL_FRAC}, rules {[r['id'] for r in PROFILE['rules']]}")

    if a.do_pass:
        pinrun.SIZE = float(max(SIZES))       # see the module docstring
        stamps = pinsim.book_hours(a.hours, a.end)
        if a.first:
            e, h = a.first.split(",")
            head = pinsim.book_hours(int(h), e)
            stamps = head + [s for s in stamps if s not in set(head)]
        run_pass(stamps, a.rows)
        return

    mk = pinsim.load_markets()
    newest = pinsim.newest_settlement(mk)

    if a.anchor:
        e, h = a.anchor.split(",")
        want = set(pinsim.book_hours(int(h), e))
        rows, hours = load_rows(a.rows, stamps=want)
        missing = sorted(want - set(hours))
        print(f"  ANCHOR 1 -- window ending {e}, {h} hours: {len(hours)} of "
              f"{len(want)} hours on disk, {len(rows)} candidate rows")
        if missing:
            print(f"  *** {len(missing)} hours NOT YET WALKED "
                  f"({missing[0]}..{missing[-1]}) -- the anchor is INCOMPLETE "
                  f"and must not be called a match ***")
        sizes = [int(a.size)] if a.size else list(SIZES)
        _, span, days = span_days(hours, newest)
        for s in sizes:
            f, r = score(rows, s)
            st = summarise(f, days, span)
            print(f"  SIZE {s} TOUCH mode: {st['fills']} fills, "
                  f"{st['closes']} closes, {st['wins']}W {st['losses']}L, "
                  f"loss {st['loss_rate']}% {st['ci']}, ${st['pnl']:+.2f}, "
                  f"mean price {st['mean_price']}c, {len(r)} rule-refused, "
                  f"peak ${st['peak_capital']:.2f}, worst close "
                  f"${st['worst_close']:+.2f}")
        return

    if a.minfill:
        rows, hours = load_rows(a.rows)
        lo, span, days = span_days(hours, newest)
        cut = split_closes(rows)
        _sz, _fr = a.minfill.split(":")
        sizes = [float(x) for x in _sz.split(",")]
        fracs = [float(x) for x in _fr.split(",")]
        print(f"  MIN_FILL_FRAC sweep on {len(rows)} cached rows, "
              f"{len(hours)} book hours, span {span:.2f} days. "
              f"Deployed value is {pinrun.MIN_FILL_FRAC:g}.")
        minfill_sweep(rows, sizes, fracs, days, span, cut)
        return

    if a.score or a.report:
        rows, hours = load_rows(a.rows)
        res_t = table(rows, hours, newest=newest, mode="touch")
        res_s = table(rows, hours, newest=newest, mode="sweep")
        if a.report:
            write_report(a.report, rows, hours, res_t, res_s, newest)
            print(f"  report written to {os.path.abspath(a.report)}")
        return
    print("  nothing to do -- pass --pass, --score, --anchor or --selftest")


def write_report(path, rows, hours, res_t, res_s, newest):
    lo, span, days = span_days(hours, newest)
    cut = res_t["cut_close"]
    L = []
    W = L.append
    F = pinsim.LIVE_FILL_RATE
    W("# RESULTS_levels -- expected P&L per CONTRACT SIZE, and how far it "
      "scales\n")
    W(f"`research/pinlevels.py`, profile `{PROFILE['name']}` sha "
      f"`{PROFILE['_sha']}`, written "
      f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())}. One tape pass, "
      f"scored at {len(SIZES)} sizes.\n")
    W(f"**Window: {len(hours)} book hours, "
      f"{time.strftime('%Y-%m-%dT%HZ', time.gmtime(lo))} to "
      f"{time.strftime('%Y-%m-%dT%HZ', time.gmtime(lo + span * 86400))}, "
      f"span {span:.2f} days ({len(days)} UTC days). "
      f"{len(rows):,} candidate rows.**\n")
    W("`$/day` is total P&L divided by that span, idle hours included. The "
      "span is truncated at the newest settlement on file, because a book "
      "hour after it cannot resolve and can earn nothing.\n")
    W("## Read the 70% column, not the ceiling -- and even it is an upper "
      "bound\n")
    W("Live we fill 70% of the attempts we make (50 of 72, measured). The "
      "replay wins every race it never ran, so `$/day @70%` is an upper "
      "bound, not a central estimate: it assumes the 70% we win are a random "
      "sample of the offers on the tape, when the ones we lose the race for "
      "are plausibly the better ones. The `ceiling` column assumes we win "
      "every race and should not be quoted at all.\n")
    W("Per CLAUDE.md (2026-09-10, rule 5): **the loss rate below is the "
      "REPLAY's, not ours.** The tape's population is \"an offer was sitting "
      "there\"; ours is \"someone actively sold it to us\", and only the "
      "second is adversely selected. Measured gap at the live gate: tape "
      "0.11% [0.00, 0.61] against live 3.4% [0.4, 11.7] -- intervals "
      "non-overlapping, a 31x gap. Do not substitute one for the other.\n")
    W("## Why there is no live $/day to check this against\n")
    W("The live bank is +$19.77 over about 4.3 days, but that is **eight "
      "different strategies**, not one. Split by the gate each run STARTED "
      "with (supplied by the coordinating agent, 2026-09-12):\n")
    W("| PIN/ceiling/guard/perMkt/hedge | legs | days | $/day |")
    W("|---|---|---|---|")
    for g, legs, dys, pd in LIVE_BY_GATE:
        W(f"| `{g}` | {legs} | {dys:.2f} | ${pd:+.2f} |")
    W(f"\n**The longest single-gate window is "
      f"{max(d for _, _, d, _ in LIVE_BY_GATE):.2f} days**, and the full "
      f"current model (0.995 gate, 0.98 ceiling, 15c dump guard, one fill per "
      f"market, 0.80 hedge) has existed for hours. No live window is long "
      f"enough to anchor a $/day figure for any gate, and the blended "
      f"$4.60/day is dragged down by the -$110/day of the 0.988-ceiling era "
      f"that no longer exists. **So the backtest is the PRIMARY estimate and "
      f"its own day-block bootstrap interval is the honest uncertainty** -- "
      f"agreement with a blended live number would be a coincidence, not a "
      f"check.\n")
    W("## Acceptance anchor 1 -- this scorer reproduces pinsim.run() exactly\n")
    W("Same 72 book hours ending `20260910T04`, same profile sha, size 20, "
      "TOUCH mode. `pinsim.run()` is the certified backtest; this file only "
      "re-scores the candidates it finds, so if the two disagree the scorer "
      "is wrong.\n")
    W("| field | pinsim.run() | pinlevels | ")
    W("|---|---|---|")
    for f_, a_, b_ in ANCHOR1:
        W(f"| {f_} | {a_} | {b_} |")
    W("\n**It did NOT pass first time, and both failures were real bugs in "
      "this file.** (i) The emission rule tracked DEPTH only, so a later "
      "offer that was cheaper but no deeper was never emitted and could never "
      "clear the IMPROVE_BY bar -- 153 fills against 156, with the closes "
      "matching 117 to 117 and all three misses being SECOND fills of a "
      "close. (ii) The scorer sorted rows by `(entry_ts, ticker)`, which "
      "re-orders two candidates at the same millisecond alphabetically "
      "instead of in the exchange's own order; whichever books the close's "
      "slot first sets `best` for the improve bar, so that alone cost one "
      "fill and $0.85. Sorting by `entry_ts` alone -- the sort is stable, so "
      "ties keep tape order -- matched exactly.\n")
    W("**And note what the anchor window itself says:** over those 72 hours "
      "the current model at size 20 LOST $11.01 on 156 fills. Three days is "
      "not a verdict, but it is the same direction as the holdout below.\n")
    for tag, res, note in (
            ("TOUCH -- what the deployed bot would do", res_t,
             "One price, one level: the order sees the best ask and the size "
             "resting there, and `MIN_FILL_FRAC` is measured against that "
             "touch. This is the live rule, so these are the numbers for the "
             "sizes we actually trade."),
            ("SWEEP -- how far it COULD scale", res_s,
             "The order walks the opposite side's bids from the best price "
             "down and pays the VWAP of what it consumes, stopping at "
             "`PRICE_CEILING` on EVERY level or as soon as the running VWAP "
             "would fail pinrun's own edge/EV gates. **This is a RULE CHANGE, "
             "not a better estimate** -- today's bot measures depth at the "
             "touch and would simply refuse most of these fills.")):
        W(f"## {tag}\n")
        W(note + "\n")
        W("| size | closes | fills | mean filled | levels swept | "
          "VWAP slippage | loss rate (fills) | 95% CP | closes lost | "
          "mean price | $/day CEILING | **$/day @70%** | peak concurrent $ | "
          "%ROC/day | hedge ON $/day |")
        W("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for s in SIZES:
            a = res["sizes"][str(s)]["all"]
            h = res["sizes"][str(s)]["hedge_on"]
            if not a["fills"]:
                W(f"| {s} | 0 | 0 |" + " -- |" * 12)
                continue
            W(f"| {s} | {a['closes']} | {a['fills']} | {a['mean_take']:.1f} | "
              f"{a['mean_levels']:.2f} | {a['mean_slip_c']:+.3f}c | "
              f"{a['loss_rate']:.2f}% | [{a['ci'][0]:.2f}, {a['ci'][1]:.2f}] | "
              f"{a['closes_lost']} of {a['closes']} | {a['mean_price']:.2f}c | "
              f"${a['per_day']:+.2f} | **${a['per_day'] * F:+.2f}** | "
              f"${a['peak_capital']:.2f} | "
              f"{(a['roc'] if a['roc'] is not None else 0):.1f}% | "
              f"${h['per_day']:+.2f} |")
        curve = [(s, res["sizes"][str(s)]["all"]["per_day"]) for s in SIZES]
        bs, bv, fall = saturation(curve)
        cap = res["sizes"][str(bs)]["all"]["peak_capital"] if bs else 0.0
        W(f"\n**SATURATION.** $/day peaks at **size {bs}** "
          f"(${bv:+.2f}/day ceiling, ${bv * F:+.2f} at the 70% fill rate), "
          f"which needs **${cap:.2f} of peak concurrent capital**"
          + (f", and first FALLS at size {fall}.\n" if fall else
             ", and never falls inside the sizes tested.\n"))
        W("| size | mean filled | $/day @70% | $/day per contract of size | "
          "peak concurrent $ | %/day on the LAST dollar added | worst close | "
          "bank needed at 1.5x brake |")
        W("|---|---|---|---|---|---|---|---|")
        prev = None
        for s in SIZES:
            a = res["sizes"][str(s)]["all"]
            if not a["fills"]:
                W(f"| {s} |" + " -- |" * 7)
                continue
            marg = "--"
            if prev is not None:
                dcap = a["peak_capital"] - prev["peak_capital"]
                dpnl = (a["per_day"] - prev["per_day"]) * F
                if dcap > 0:
                    marg = f"{100.0 * dpnl / dcap:+.1f}%"
            prev = a
            W(f"| {s} | {a['mean_take']:.1f} | ${a['per_day'] * F:+.2f} | "
              f"${a['per_day'] * F / s:+.4f} | ${a['peak_capital']:.2f} | "
              f"{marg} | ${a['worst_close']:+.2f} | ${a['bank_needed']:.2f} |")
        W("**The last column is the number that answers \"should I add "
          "capital\":** the extra $/day the step bought, divided by the extra "
          "peak capital it required. The average return on capital stays high "
          "long after the MARGINAL return has collapsed, and it is the "
          "marginal one that prices the next dollar.\n")
    W("## 70/30 split by close -- nothing is a claim unless the holdout "
      "agrees\n")
    W(f"Cut at close {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(cut))}. "
      f"Both halves are divided by the SAME full-window span, so the two "
      f"columns add to the whole rather than each being a rate of its own "
      f"half. TOUCH mode.\n")
    W("| size | fit fills | fit $ | fit loss% | holdout fills | holdout $ | "
      "holdout loss% |")
    W("|---|---|---|---|---|---|---|")
    for s in SIZES:
        f_ = res_t["sizes"][str(s)]["fit"]
        h_ = res_t["sizes"][str(s)]["holdout"]
        W(f"| {s} | {f_['fills']} | ${f_['pnl']:+.2f} | "
          f"{(f_['loss_rate'] if f_['loss_rate'] is not None else 0):.2f}% | "
          f"{h_['fills']} | ${h_['pnl']:+.2f} | "
          f"{(h_['loss_rate'] if h_['loss_rate'] is not None else 0):.2f}% |")
    fitp = res_t["sizes"]["20"]["fit"]
    holp = res_t["sizes"]["20"]["holdout"]
    W("\n**THE HOLDOUT IS MUCH WEAKER THAN THE FIT, AND THAT IS THE MOST "
      "DECISION-RELEVANT LINE IN THIS FILE.** At size 20 the first 70% of "
      f"closes made ${fitp['pnl']:+.2f} on {fitp['fills']} fills at a "
      f"{fitp['loss_rate']:.2f}% loss rate; the last 30% made "
      f"${holp['pnl']:+.2f} on {holp['fills']} fills at "
      f"{holp['loss_rate']:.2f}% -- the loss rate DOUBLED. At sizes 1000 and "
      f"2000 the holdout is outright negative. The 72-hour acceptance window "
      f"above, which sits inside the holdout, lost money. Two readings are "
      f"open and this window cannot separate them: the market has got harder, "
      f"or nine days of holdout is too few closes to tell. Nothing here "
      f"should be sized as though the fit half were the expectation.\n")
    W("\n## Block bootstrap BY DAY -- 95% interval on $/day\n")
    W(f"{BOOT_DRAWS:,} resamples of the {len(days)} UTC days with "
      f"replacement, seed {BOOT_SEED}. The block is the DAY and not the fill: "
      f"twelve series settle on the same second at rho ~ 0.8, so fills are "
      f"not independent draws, and idle days stay in the list so they dilute "
      f"as they do in life.\n")
    for tag, res in (("TOUCH", res_t), ("SWEEP", res_s)):
        W(f"### {tag}\n")
        W("| size | $/day ceiling | 95% interval | includes zero? | "
          "$/day @70% | 70% interval |")
        W("|---|---|---|---|---|---|")
        for s in SIZES:
            a = res["sizes"][str(s)]["all"]
            if not a["boot"]:
                W(f"| {s} |" + " -- |" * 5)
                continue
            z = "**YES**" if a["boot"][0] <= 0 <= a["boot"][1] else "no"
            W(f"| {s} | ${a['per_day']:+.2f} | "
              f"[${a['boot'][0]:+.2f}, ${a['boot'][1]:+.2f}] | {z} | "
              f"${a['per_day'] * F:+.2f} | "
              f"[${a['boot'][0] * F:+.2f}, ${a['boot'][1] * F:+.2f}] |")
        W("")
    W("## Drawdown, which is the operator's actual constraint\n")
    W("| size | worst single close | when | worst day | when | days traded | "
      "days positive | bank at 1.5x brake |")
    W("|---|---|---|---|---|---|---|---|")
    for s in SIZES:
        a = res_t["sizes"][str(s)]["all"]
        if not a["fills"]:
            W(f"| {s} |" + " -- |" * 7)
            continue
        W(f"| {s} | ${a['worst_close']:+.2f} | "
          f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(a['worst_close_id']))}"
          f" | ${a['worst_day']:+.2f} | {a['worst_day_id']} | "
          f"{a['days_traded']} | {a['days_positive']} | "
          f"${a['bank_needed']:.2f} |")
    W("\n## What this cannot tell you\n")
    W("- **The race.** Every fill here assumes the offer was ours.")
    W("- **Our loss rate.** See the rule quoted above; the number in the "
      "table is the replay's.")
    W("- **A later cheaper offer on a market whose first deep candidate was "
      "already taken.** The pass emits a row when a candidate offers MORE "
      "depth than any earlier one on that market, not when it offers a lower "
      "price, so a few second-fills-of-a-close that the IMPROVE_BY bar would "
      "have allowed are missed. Conservative.")
    W("- **Whether a sweep would move the market.** The SWEEP table consumes "
      "resting bids at the prices they rest at. A real 2,000-contract order "
      "into a book this thin would be seen, and the levels behind it would "
      "move away. So the sweep column is an upper bound on an upper bound.")
    W("- **An offer whose TOUCH holds less than one contract.** pinrun\'s "
      "MIN_LEVEL refuses those outright, so the pass never records them and "
      "no size can fill from them -- even a sweep that would have taken the "
      "level behind. Live-faithful for TOUCH, conservative for SWEEP.")
    W("- **Anything about the tape\'s recording holes.** 6.42% of covered "
      "seconds are silent (`results/RESULTS_tapegaps.md`), 3.28% inside the "
      "tau band, so every COUNT here is a lower bound by roughly 3%.")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")


PROFILE = pinrules.default_profile()
PROFILE["_sha"] = pinrules.fingerprint(PROFILE)

if __name__ == "__main__":
    main()
