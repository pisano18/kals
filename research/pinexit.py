#!/usr/bin/env python3
# VERSION: 2026-09-12-pe1
"""pinexit.py -- CAN WE SELL THE WINNER BEFORE IT SETTLES, OR ONLY WHEN IT
WAS GOING TO WIN ANYWAY?

THE IDEA. `pin` buys the near-certain side ~20-30 s before close at ~96c and
HOLDS to settlement. That pays $1 if right and $0 if wrong: a small expected
gain carried on a rare, total loss. `results/RESULTS_count.md` established
that in 140,989 of 140,990 model-certain market-seconds there is an ask on the
LOSING side; in a binary where YES+NO = $1, an ask on the loser at q IS a bid
on the winner at (1-q). So somebody is very often willing to buy our position
back at 97-99c. Selling instead of holding would lock ~+2.7c per contract and
delete the tail.

THE ONE WAY IT FAILS, and the reason this file is a MEASUREMENT and not a
proposal: if the bid on our side vanishes precisely when the position is about
to go wrong, we sell only the trades we would have won anyway -- giving up ~1c
on every winner while still eating every loser in full. That is strictly WORSE
than holding. It is the same adverse-selection trap that killed the resting-bid
idea in `results/RESULTS_maker.md` (a resting bid filled on 100% of eventual
losers and 29% of winners). SO THE ADVERSE-SELECTION CONTROL IS NOT AN EXTRA
HERE; IT IS THE RESULT.

WHAT IS REIMPLEMENTED: NOTHING ABOUT THE DECISION. Entries come from
`pinsim.decide()` -- which is `pinrun`'s own fair / net_edge / expected_value /
constants -- behind `pinsim.close_slot_ok` / `close_slot_book` (the per-close
rails) and the profile's rules, exactly as `pinsim.run()` opens a position.
This file adds one thing: it keeps the position open and watches the book.

CEILINGS, STATED ONCE AND REPEATED IN THE REPORT.
  * A "bid" reconstructed from the opposite side's ask is what we could sell
    into ONLY IF WE WIN THE RACE FOR IT, exactly as the buy side assumes. Live
    we fill ~70% of the attempts we make. Every exit-fill figure here is an
    UPPER BOUND for the same reason every pinsim entry figure is.
  * A sale is a TAKER trade -- we hit their bid -- so `pinrun.billed_fee` is
    charged on the exit leg at the exit price. There is no maker-fee-free
    version of this without resting an ask, which is a DIFFERENT question and
    is not tested here.
  * CLAUDE.md AMENDMENT 2026-09-10, rule 5: this file may say what the index
    did, what the model computed and what the market did. It may NOT be quoted
    for OUR live loss rate. Loss rates here are the REPLAY's population ("an
    offer was sitting there"), not ours ("someone actively sold it to us").

UNITS: n is reported as CLOSES and as POSITIONS, never as decision moments.
Money is priced PER CLOSE at size 20, counting closes we trade nothing on as
zero -- the per-close unit has killed three ideas in this project and it is the
verdict column here too.
"""
import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinsim                                                  # noqa: E402
import pinrun                                                  # noqa: E402
import pindata                                                 # noqa: E402
import pinrules                                                # noqa: E402
from pincross import cp_interval                               # noqa: E402

_ND = NormalDist()

# the exit rule's two knobs, as specified by the brief
EXIT_TAUS = (15, 10, 8, 5, 3)
EXIT_FLOORS = (0.985, 0.99, 0.995)
GRID_TAUS = (15, 10, 8, 5, 3)
TRACK_TAU_MIN = 3          # we stop watching at tau 3; below it a fill is not
                           # reachable and pinrun refuses to act there anyway
COMPANION_PIN = 0.97       # THE COMPANION POPULATION'S THRESHOLD, and it is
                           # deliberately LOOSER than the live gate's 0.995.
                           # CLAUDE.md: "any forward-looking test needs a
                           # backward-looking companion that must be large",
                           # and what makes this one large is LOSERS, not
                           # markets. At 0.995 the model is right ~99.9% of
                           # the time, so a 216-hour window holds only a
                           # handful of flips and the decisive table would
                           # have no power at all. The 0.97-0.995 band flips
                           # an order of magnitude more often, and the
                           # question -- when a near-certain position goes
                           # wrong, does the bid on our side survive? -- is
                           # the same question. Markets are recorded from the
                           # first moment they cross 0.97, and `certain_tau`
                           # marks the moment (if any) they reached the live
                           # gate, so the two strata are reported separately
                           # and never pooled. `cap` is keyed on tau, not on
                           # when tracking began, so the 0.995 stratum's
                           # numbers are identical to what a 0.995-only run
                           # would have produced.
DEFAULT_OUT = os.path.join(HERE, "..", "results", "pinexit_positions.jsonl")


# ---------------------------------------------------------------- primitives
def our_bid(b, want):
    """THE BEST BID ON OUR SIDE, from the opposite side's ask.

    `pinsim.book_view` returns asks, because that is what a BUYER needs. In a
    binary with YES+NO = $1 an ask on the opposite side at q is a bid on ours
    at 1-q, and the SIZE resting behind it is the same quantity -- it is
    literally the same order. Concretely, pindata's Book stores bids on both
    sides; book_view computes `no_ask = 1 - best_yes_bid` with
    `no_ask_size = book.yes[best_yes_bid]`, so inverting it returns exactly
    the yes-bid level and its size.

    Returns (bid, size). (None, 0.0) when nobody is bidding for our side.
    """
    opp = "no" if want == "yes" else "yes"
    a = b.get(opp + "_ask")
    if a is None:
        return None, 0.0
    return round(1.0 - float(a), 4), float(b.get(opp + "_ask_size") or 0.0)


def pct(vals, q):
    """Linear-interpolated quantile; None on an empty list."""
    if not vals:
        return None
    v = sorted(vals)
    if len(v) == 1:
        return float(v[0])
    k = q * (len(v) - 1)
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    if lo == hi:
        return float(v[lo])
    return float(v[lo]) + (float(v[hi]) - float(v[lo])) * (k - lo)


def _binom_cdf(k, n, p):
    """P(K <= k) for K ~ Binomial(n, p), in logs so a large n cannot overflow."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0
    lg = math.lgamma
    tot = 0.0
    for i in range(k + 1):
        tot += math.exp(lg(n + 1) - lg(i + 1) - lg(n - i + 1)
                        + i * math.log(p) + (n - i) * math.log1p(-p))
    return min(1.0, tot)


def mde_two_prop(k_ref, n_ref, n_test, power=0.80):
    """MDE, STATED BEFORE THE ESTIMATE, on the test this project actually
    uses: two Clopper-Pearson intervals that DO NOT OVERLAP.

    Returns the smallest drop below the reference rate that would be detected
    with `power`, given `n_test` observations in the small group. With 2-4%
    losers that group is tiny, so this is the honest ceiling on what the
    decisive table could ever have found -- "no effect" and "no power" are
    different results and the report must not conflate them.

    A normal-approximation MDE is useless here: the winners' rate sits at or
    near 1.0, where its variance is zero and the usual formula returns 0.
    This one is exact and stays finite there (at p_ref = 1.0 any single
    failure separates the groups, so the MDE is 1 - power^(1/n_test)).
    """
    if not n_ref or not n_test:
        return None
    p_ref = k_ref / n_ref
    ref_lo = cp_interval(k_ref, n_ref)[0]
    kstar = -1
    for k in range(n_test + 1):          # cp upper bound is monotone in k
        if cp_interval(k, n_test)[1] < ref_lo:
            kstar = k
        else:
            break
    if kstar < 0:
        return None                      # even 0 of n_test would not separate
    lo, hi = 0.0, p_ref
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if _binom_cdf(kstar, n_test, mid) >= power:
            lo = mid
        else:
            hi = mid
    return max(0.0, p_ref - lo)


# ------------------------------------------------------- the exit simulation
def simulate_exit(pos, exit_tau, floor, max_book_age_ms=None):
    """Sell the position at the FIRST book event, at tau <= exit_tau and
    tau >= 3, where the bid on our side is at or above `floor`.

    Returns a dict. `exited` means the WHOLE position was sold in one event
    (the displayed size covered it). A level that qualifies on price but is
    too thin sells what is there and the remainder holds to settlement; that
    partial case is reported separately so the binary column stays honest.

    ONE EVENT ONLY. Re-reading the same resting level at the next event would
    let one order fill us twice, which is the sort of arithmetic this project
    has been burned by; the remainder is therefore held, which understates the
    exit rather than flattering it.
    """
    px, n, won = pos["price"], pos["n"], pos["won"]
    entry_fee = pinrun.billed_fee(px, n)
    hold_pnl = (n * (1.0 - px) if won else -n * px) - entry_fee
    hit = None
    for ob in pos["obs"]:
        tau, bid, sz, age = ob[0], ob[1], ob[2], ob[3]
        bel = ob[4] if len(ob) > 4 else None
        if tau > exit_tau or tau < TRACK_TAU_MIN:
            continue
        if max_book_age_ms is not None and (age is None or age > max_book_age_ms):
            continue
        if bid is None or bid < floor or sz <= 0:
            continue
        hit = (tau, bid, sz, bel)
        break
    if hit is None:
        return {"exited": False, "partial": False, "qty": 0.0, "bid": None,
                "tau": None, "belief": None, "pnl": hold_pnl,
                "hold_pnl": hold_pnl}
    tau, bid, sz, bel = hit
    qty = min(float(n), float(sz))
    rest = float(n) - qty
    pnl = qty * (bid - px) - pinrun.billed_fee(bid, qty) - entry_fee
    if rest > 0:
        pnl += (rest * (1.0 - px) if won else -rest * px)
    return {"exited": qty >= float(n) - 1e-9, "partial": rest > 1e-9,
            "qty": qty, "bid": bid, "tau": tau, "belief": bel, "pnl": pnl,
            "hold_pnl": hold_pnl}


def price_rule(positions, exit_tau, floor, n_closes, max_book_age_ms=None):
    """THE VERDICT COLUMN: total P&L held vs exited, priced PER CLOSE over
    `n_closes` closes in the window -- closes we traded nothing on count as
    zero, because picking fewer opportunities has to be paid for."""
    hold = exit_ = 0.0
    filled = part = 0
    fill_by_outcome = {True: [0, 0], False: [0, 0]}     # won -> [exits, n]
    bids = []
    for p in positions:
        r = simulate_exit(p, exit_tau, floor, max_book_age_ms)
        hold += r["hold_pnl"]
        exit_ += r["pnl"]
        ok = r["qty"] > 0
        filled += 1 if r["exited"] else 0
        part += 1 if (ok and not r["exited"]) else 0
        fill_by_outcome[bool(p["won"])][1] += 1
        if ok:
            fill_by_outcome[bool(p["won"])][0] += 1
            bids.append(r["bid"])
    n = len(positions)
    return {
        "exit_tau": exit_tau, "floor": floor, "positions": n,
        "closes_traded": len(set(p["close"] for p in positions)),
        "closes_window": n_closes,
        "hold_pnl": hold, "exit_pnl": exit_, "delta": exit_ - hold,
        "hold_per_close": hold / n_closes if n_closes else 0.0,
        "exit_per_close": exit_ / n_closes if n_closes else 0.0,
        "full_exits": filled, "partial_exits": part,
        "fill_rate": filled / n if n else 0.0,
        "any_fill_rate": (filled + part) / n if n else 0.0,
        "win_fill": fill_by_outcome[True], "lose_fill": fill_by_outcome[False],
        "median_exit_bid": pct(bids, 0.5),
    }


ASSUMED_LOSS_RATES = (0.01, 0.02, 0.03, 0.04)


def delta_at(e_w, e_l, g, p):
    """Change in cents per contract from exiting rather than holding, at an
    ASSUMED live loss rate `p`.

        exiting a WINNER costs  c_w = 1 - g      (g = bid - fee, per contract)
        exiting a LOSER  gains  g_l = g
        delta = -(1 - p) * e_w * c_w  +  p * e_l * g_l

    `p` is a PARAMETER and never a tape number. CLAUDE.md's 2026-09-10 rule 5
    forbids reading the replay's loss rate as ours, and this is the shape that
    obeys it: the operator supplies the loss rate from LIVE FILLS and reads
    off the column.
    """
    if e_w is None or e_l is None or g is None:
        return None
    return 100.0 * (-(1.0 - p) * e_w * (1.0 - g) + p * e_l * g)


def break_even(positions, exit_tau, floor, max_book_age_ms=None):
    """THE BREAK-EVEN LOSS RATE -- how this rule is priced WITHOUT quoting a
    tape loss rate as ours.

    CLAUDE.md, 2026-09-10 amendment rule 5, is absolute: the tape is valid for
    what the market did and INVALID for how often WE lose (0.11% on the tape
    against 3.4% live, intervals that do not overlap). But section 3's dollar
    columns are a function of the tape's loss rate, so read alone they would
    flatter HOLDING for exactly the forbidden reason. This function removes
    the loss rate from the comparison and hands back the rate at which the two
    are equal, so it can be set against a LIVE number.

    The arithmetic, per contract, for a position bought at `px` and sold at
    `b`, both legs taker:

        exiting a WINNER   costs  c_w = (1 - b) + fee_out
        exiting a LOSER    gains  g_l =      b  - fee_out

    so c_w + g_l = 1 exactly, and with exit rates e_w on winners and e_l on
    losers the rule beats holding when

        p * e_l * g_l  >  (1 - p) * e_w * c_w
        p* = e_w*c_w / (e_w*c_w + e_l*g_l)

    Two scenarios are returned because the whole question is whether the
    second one holds:
      `optimistic` -- losers exit as often and at the same price as winners
                      (e_l = e_w, b from the winners' own realised exits)
      `measured`   -- e_l and b as actually measured on the tape's losers,
                      which is the number with the wide interval
    """
    W = [p for p in positions if p["won"]]
    L = [p for p in positions if not p["won"]]
    bw, bl = [], []
    for grp, acc in ((W, bw), (L, bl)):
        for p in grp:
            r = simulate_exit(p, exit_tau, floor, max_book_age_ms)
            if r["exited"]:
                acc.append(r["bid"] - pinrun.billed_fee(r["bid"], p["n"])
                           / float(p["n"]))
    e_w = (len(bw) / len(W)) if W else None
    e_l = (len(bl) / len(L)) if L else None
    out = {"exit_tau": exit_tau, "floor": floor, "e_w": e_w, "e_l": e_l,
           "n_w": len(W), "n_l": len(L), "exits_w": len(bw),
           "exits_l": len(bl)}
    g_w = pct(bw, 0.5)                      # median (bid - fee) on winners
    out["g_opt"] = g_w
    out["p_opt"] = ((1.0 - g_w) / ((1.0 - g_w) + g_w)) if g_w else None
    if e_w and bl and e_l:
        g_m = pct(bl, 0.5)
        out["g_meas"] = g_m
        den = e_w * (1.0 - g_w) + e_l * g_m
        out["p_meas"] = (e_w * (1.0 - g_w) / den) if den else None
    elif L and e_l == 0.0 and e_w:
        # every loser failed to exit: the rule NEVER beats holding, at any
        # loss rate, and that must read as 100% rather than as "no data"
        out["g_meas"] = None
        out["p_meas"] = 1.0
    else:
        out["g_meas"] = None
        out["p_meas"] = None
    return out


def decisive_table(positions, taus=GRID_TAUS):
    """THE DECISIVE TABLE. Split by what the position eventually DID.

    For each tau and each outcome group: how many positions were open at that
    tau, what fraction had ANY bid on our side, the median and p10 of that
    bid, and the median size resting at it. If the losers keep a ~99c bid as
    often as the winners, the exit works. If it vanishes or collapses, it does
    not.
    """
    rows = []
    for tau in taus:
        row = {"tau": tau}
        for won, key in ((True, "won"), (False, "lost")):
            grp = [p for p in positions if bool(p["won"]) is won
                   and str(tau) in p["grid"]]
            g = [p["grid"][str(tau)] for p in grp]
            have = [x for x in g if x[0] is not None and x[1] > 0]
            bids = [x[0] for x in have]
            szs = [x[1] for x in have]
            lo, hi = cp_interval(len(have), len(g)) if g else (None, None)
            row[key] = {
                "n": len(g), "closes": len(set(p["close"] for p in grp)),
                "have": len(have),
                "have_frac": (len(have) / len(g)) if g else None,
                "ci": [lo, hi],
                "med_bid": pct(bids, 0.5), "p10_bid": pct(bids, 0.10),
                "med_size": pct(szs, 0.5),
                "med_belief": pct([x[2] for x in g if x[2] is not None], 0.5),
            }
        rows.append(row)
    return rows


def adverse_control(positions, exit_tau, floor, max_book_age_ms=None):
    """RESULTS_maker.md's control, in its own units: the exit fill rate on
    eventual LOSERS against eventual WINNERS, each with a Clopper-Pearson
    interval, plus the MDE that says how small an asymmetry was detectable."""
    w = [p for p in positions if p["won"]]
    l = [p for p in positions if not p["won"]]
    out = {"exit_tau": exit_tau, "floor": floor}
    for grp, key in ((w, "won"), (l, "lost")):
        k = sum(1 for p in grp
                if simulate_exit(p, exit_tau, floor,
                                 max_book_age_ms)["qty"] > 0)
        lo, hi = cp_interval(k, len(grp)) if grp else (None, None)
        out[key] = {"n": len(grp), "closes": len(set(p["close"] for p in grp)),
                    "exits": k, "rate": (k / len(grp)) if grp else None,
                    "ci": [lo, hi]}
    out["mde"] = (mde_two_prop(out["won"]["exits"], len(w), len(l))
                  if (w and l) else None)
    return out


# ------------------------------------------------------------------ the tape
def observe(rec, b, tau, belief, age_ms, size_n):
    """Append one observation, de-duplicated on (tau, bid, size).

    Event-driven: a bid that exists for 400 ms inside a second is a bid, on
    the way out as on the way in (the 2026-09-12 rebuild's whole point). The
    de-duplication keeps the FIRST occurrence of every distinct book state, so
    nothing an exit could have hit is lost, and the per-second grid row is the
    LAST state of that second.

    THREE THINGS ARE KEPT, and the third is why this function has a size
    argument:

      `obs`  the full per-event trace, only for positions we actually bought,
             because that is what prices the rule to the cent.
      `grid` the last state of each of the five report taus.
      `cap`  for EVERY tracked market including the companion population: the
             BEST bid seen at or below each EXIT_TAU, once for any size and
             once for a size that covers the whole order. That is exactly what
             an exit FILL RATE needs, it is 10 numbers instead of a thousand,
             and it is the only reason the companion population -- the one
             with enough losers to have power -- fits on disk at all.
    """
    bid, sz = our_bid(b, rec["want"])
    if rec["bought"]:
        last = rec["obs"][-1] if rec["obs"] else None
        if last is None or last[0] != tau or last[1] != bid or last[2] != sz:
            rec["obs"].append([tau, bid, sz, age_ms, belief])
    if tau in GRID_TAUS:
        rec["grid"][str(tau)] = [bid, sz, belief]
    if bid is not None and sz > 0:
        for T in EXIT_TAUS:
            if tau > T:
                continue
            c = rec["cap"].get(str(T))
            if c is None:
                c = rec["cap"][str(T)] = [None, None]
            if c[0] is None or bid > c[0]:
                c[0] = bid
            if sz >= size_n and (c[1] is None or bid > c[1]):
                c[1] = bid


def cap_fill(rec, exit_tau, floor, full=True):
    """Would an exit at (exit_tau, floor) have found a bid? From `cap`, so it
    works on the companion population where no per-event trace was kept.

    EXISTENCE only -- it says a qualifying bid was there at some event at or
    below `exit_tau`, which is what a fill RATE measures. It deliberately does
    not price anything, because the companion markets have no entry price.
    """
    c = rec.get("cap", {}).get(str(exit_tau))
    if not c:
        return False
    v = c[1] if full else c[0]
    return v is not None and v >= floor


def cap_control(pop, exit_tau, floor, full=True):
    """The adverse-selection control on a population that has only `cap`."""
    out = {"exit_tau": exit_tau, "floor": floor}
    W = [r for r in pop if r["won"]]
    L = [r for r in pop if not r["won"]]
    for grp, key in ((W, "won"), (L, "lost")):
        k = sum(1 for r in grp if cap_fill(r, exit_tau, floor, full))
        lo, hi = cp_interval(k, len(grp)) if grp else (None, None)
        out[key] = {"n": len(grp), "closes": len(set(r["close"] for r in grp)),
                    "exits": k, "rate": (k / len(grp)) if grp else None,
                    "ci": [lo, hi]}
    out["mde"] = (mde_two_prop(out["won"]["exits"], len(W), len(L))
                  if (W and L) else None)
    return out


def walk_tape(hours, end=None, size=20.0, out_path=DEFAULT_OUT, log=print):
    """One pass over `hours` settled book hours. Entries are pinsim's, the
    watching is ours, and each hour's stream is iterated ONCE."""
    profile = pinrules.load("default")
    pinsim.apply_profile(profile)
    if size is not None:
        pinrun.SIZE = float(size)
    mk = pinsim.load_markets()
    stamps = pinsim.book_hours(hours, end)
    ns = pinsim.newest_settlement(mk)
    log(f"  profile {profile['name']} sha {profile['_sha']}; gate PIN "
        f"{pinrun.PIN}, ceiling {pinrun.PRICE_CEILING}, tau "
        f"{pinrun.TAU_MIN}-{pinrun.TAU_MAX}, size {pinrun.SIZE:g}")
    log(f"  {len(mk):,} settled markets, {len(stamps)} book hours, newest "
        f"settlement {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(ns))}")

    per_close, decided = {}, set()
    n_pos = n_cand = 0
    closes_seen = set()
    gap_flags = seq_back = bad = 0
    fh = open(out_path, "w", encoding="utf-8")
    try:
        for hi, stamp in enumerate(stamps):
            hour = pinsim.load_hour(stamp, mk)
            if not hour["ticks"]:
                pinsim._HOUR_CACHE.pop(stamp, None)
                continue
            idx = pinsim.TapeIndex(sorted(hour["ticks"]))
            pend = {k: list(v) for k, v in hour["ticks"].items()}
            wk = pinsim.Walk(mk, idx, pend, per_event=True)
            track = {}                  # ticker -> open record being watched
            cand = {}                   # ticker -> model-certain companion
            bel = {}                    # ticker -> (sec, fair) cache
            for kind, tkk, sec, ts in wk.drive(hour["events"]):
                if kind == 0:
                    continue
                r = mk.get(tkk)
                if r is None:
                    continue
                cs = int(float(r["close"]))
                tau = cs - sec
                if not (TRACK_TAU_MIN <= tau <= 60):
                    continue
                iid = pindata.SERIES_TO_INDEX[r["series"]]
                if iid not in idx.ticks:
                    continue
                bkk = wk.books[tkk]
                b = pinsim.book_view(bkk, ts)
                age = b["age_ms"]
                # belief is a function of the SECOND (the index prints once a
                # second), so it is computed once per second per market
                c = bel.get(tkk)
                if c is None or c[0] != sec:
                    sg = idx.sigma(iid)
                    f = pinrun.fair(idx, iid, cs, sec, float(r["strike"]),
                                    (sg or 0.0) * pinrun.SIGMA_STRESS,
                                    round_digits=pindata.ROUND_DIGITS.get(
                                        r["series"])) if sg else None
                    bel[tkk] = c = (sec, f)
                f = c[1]
                # ---- watch every open position and every companion --------
                for store in (track, cand):
                    rc = store.get(tkk)
                    if rc is not None:
                        bl = (f if rc["want"] == "yes"
                              else (1.0 - f)) if f is not None else None
                        observe(rc, b, tau, bl, age, float(pinrun.SIZE))
                # ---- the COMPANION population: model-certain, offer or not
                # (the large backward-looking group the decisive table needs
                # for power; see the report)
                if tkk not in cand and f is not None and \
                        pinrun.TAU_MIN <= tau <= pinrun.TAU_MAX and \
                        (f >= COMPANION_PIN or f <= 1.0 - COMPANION_PIN):
                    side = "yes" if f >= 0.5 else "no"
                    nrc = _new_rec(r, tkk, cs, side, tau, None, 0.0,
                                   bought=False)
                    nrc["conf_in"] = round(max(f, 1.0 - f), 6)
                    cand[tkk] = nrc
                    n_cand += 1
                crc = cand.get(tkk)
                if crc is not None and crc.get("certain_tau") is None and \
                        f is not None and \
                        pinrun.TAU_MIN <= tau <= pinrun.TAU_MAX:
                    cbl = f if crc["want"] == "yes" else 1.0 - f
                    if cbl >= pinrun.PIN:
                        crc["certain_tau"] = tau
                # ---- ENTRY: pinsim's own decision and pinsim's own rails ---
                if tkk in decided:
                    continue
                if not (pinrun.TAU_MIN <= tau <= pinrun.TAU_MAX):
                    continue
                closes_seen.add(cs)
                slot = pinsim.close_slot_ok(per_close.get(cs), tkk, None)
                if slot:
                    continue
                if age is None or age > pinrun.MAX_BOOK_AGE_MS:
                    continue
                sg0 = idx.sigma(iid)
                if sg0 and f is not None:
                    side0 = "yes" if f >= 0.5 else "no"
                    _, sp0, ia0 = idx.spot(iid)
                    pinsim.resolve_for(profile, pinsim.record(
                        f, side0, b.get(side0 + "_ask") or 0.0, 0.0,
                        b.get(side0 + "_ask_size") or 0.0, tau, r["series"],
                        sec, sg0, sp0, age, ia0))
                w, px, n, fv = pinsim.decide(
                    idx, iid, cs, sec, float(r["strike"]),
                    pindata.ROUND_DIGITS.get(r["series"]), b, pinrun.SIZE)
                if w is None:
                    continue
                if pinsim.close_slot_ok(per_close.get(cs), tkk, px):
                    continue
                sg_ = idx.sigma(iid)
                _, sp_, ia_ = idx.spot(iid)
                verdict, _fired = pinrules.decide(profile, pinsim.record(
                    fv, w, px, n, b.get(w + "_ask_size"), tau, r["series"],
                    sec, sg_, sp_, age, ia_))
                decided.add(tkk)
                if verdict == "refuse":
                    continue
                pinsim.close_slot_book(per_close, cs, tkk, px)
                track[tkk] = _new_rec(r, tkk, cs, w, tau, px, n, bought=True)
                n_pos += 1
            for store in (track, cand):
                for rc in store.values():
                    if rc["bought"] or rc["grid"] or rc["cap"]:
                        rc["obs"] = rc["obs"] if rc["bought"] else []
                        fh.write(json.dumps(rc, separators=(",", ":")) + "\n")
            gap_flags += getattr(hour["events"], "gap_flags", 0) or 0
            seq_back += getattr(hour["events"], "seq_back", 0) or 0
            bad += wk.bad + (getattr(hour["events"], "bad", 0) or 0)
            log(f"    {stamp}  positions {n_pos:,}  certain-markets "
                f"{n_cand:,}  closes {len(closes_seen):,}", flush=True)
            pinsim._HOUR_CACHE.pop(stamp, None)
    finally:
        fh.close()
    meta = {"positions": n_pos, "certain_markets": n_cand,
            "closes_window": len(closes_seen), "hours": len(stamps),
            "stamps": [stamps[0], stamps[-1]] if stamps else [],
            "gap_flags": gap_flags, "seq_back": seq_back, "bad_deltas": bad,
            "gate": {"PIN": pinrun.PIN, "PRICE_CEILING": pinrun.PRICE_CEILING,
                     "TAU_MIN": pinrun.TAU_MIN, "TAU_MAX": pinrun.TAU_MAX,
                     "SIZE": pinrun.SIZE},
            "companion_pin": COMPANION_PIN}
    try:
        # the per-close DENOMINATOR is a property of the tape pass, not of the
        # rows, so --analyse must read it back rather than re-derive it from
        # the closes we happened to trade -- that would quietly drop every
        # close we looked at and refused, which is the unit the brief calls
        # the verdict column
        with open(out_path + ".meta.json", "w", encoding="utf-8") as mh:
            json.dump(meta, mh, indent=1)
    except OSError as e:                                        # noqa: BLE001
        log(f"  *** could not write the meta sidecar: {e}")
    log(f"  wrote {out_path}")
    if bad:
        log(f"  *** {bad:,} deltas failed to parse -- the book is incomplete "
            f"and every number below is suspect ***")
    log(f"  {gap_flags:,} collector `_seq_gap` flags, {seq_back:,} backward "
        f"`seq` steps (a reconnect restarts the exchange's numbering)")
    return meta


def _new_rec(r, tkk, cs, side, tau, px, n, bought):
    res = r["result"]
    yes = (str(res).lower() == "yes") if isinstance(res, str) \
        else float(res) >= 0.5
    return {"ticker": tkk, "coin": r["series"], "close": cs,
            "want": side, "tau_in": tau, "price": px, "n": float(n),
            "won": (yes == (side == "yes")), "bought": bought,
            "certain_tau": None, "conf_in": None,
            "grid": {}, "obs": [], "cap": {}}


def load_positions(path):
    P, C = [], []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            (P if d["bought"] else C).append(d)
    return P, C


# ------------------------------------------------------------------ the report
def write_report(P, C, meta, path, log=print):
    out = []

    def w(s=""):
        out.append(s)

    closes_all = meta.get("closes_window") or len(set(p["close"] for p in P))
    P = sorted(P, key=lambda p: p["close"])
    closes = sorted(set(p["close"] for p in P))
    cut = closes[int(0.70 * len(closes))] if closes else 0
    fit = [p for p in P if p["close"] < cut]
    hold = [p for p in P if p["close"] >= cut]
    nl = sum(1 for p in P if not p["won"])
    span = ""
    if P:
        span = (time.strftime("%Y-%m-%dT%HZ", time.gmtime(P[0]["close"]))
                + " -> "
                + time.strftime("%Y-%m-%dT%HZ", time.gmtime(P[-1]["close"])))

    w("# RESULTS_exit -- can we SELL the winner before it settles?")
    w()
    w(f"Generated {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())} by "
      f"`research/pinexit.py`.")
    w()
    w(f"**Window:** {meta.get('hours', '?')} book hours, {span}, "
      f"{len(closes):,} traded closes out of {closes_all:,} closes in the "
      f"window, **{len(P):,} positions** ({nl} of them eventually lost).")
    w(f"Companion population (model called it near-certain, conf >= "
      f"{COMPANION_PIN}, offer or not): **{len(C):,} markets**, "
      f"{sum(1 for c in C if not c['won']):,} of which the model's own side "
      f"eventually lost.")
    w()
    w("**CEILINGS.** A bid reconstructed from the opposite side's ask is what "
      "we could sell into ONLY IF WE WIN THE RACE FOR IT -- live we fill ~70% "
      "of the attempts we make, and every exit-fill number below assumes we "
      "win every race. A sale is a TAKER trade, so `pinrun.billed_fee` is "
      "charged on the exit leg at the exit price; there is no maker-fee-free "
      "version of this without resting an ask, which is a different question "
      "and is not tested here. In the other direction, one deliberate "
      "conservatism: only the TOP bid level is ever sold into, so 5 contracts "
      "at 99c plus 500 at 98c counts as a partial and not a fill -- it "
      "understates the exit rather than flattering it, and the median size at "
      "the top bid below shows how rarely it binds. Per CLAUDE.md "
      "(2026-09-10 amendment, rule 5) "
      "**no loss rate on this page is OUR live loss rate** -- this is the "
      "replay's population, not ours.")
    w()

    # ---- 2. THE DECISIVE TABLE -------------------------------------------
    w("## 1. THE DECISIVE TABLE -- does the bid survive on the LOSERS?")
    w()
    ac = adverse_control(P, 10, 0.99)
    mde = ac.get("mde")
    w(f"**MDE, stated before the estimate.** {ac['won']['n']:,} winners and "
      f"**{ac['lost']['n']} losers**. Against a winner rate of "
      f"{100 * (ac['won']['rate'] or 0):.1f}%, the smallest drop in the "
      f"losers' rate detectable at 80% power / 5% two-sided is "
      + (f"**{100 * mde:.1f} percentage points**" if mde else "**undefined "
         "(one of the groups is empty)**")
      + ". Anything smaller than that is NO POWER, not NO EFFECT, and this "
        "page must not be read as ruling it out.")
    w()
    w("`have` = a bid existed on our side with size > 0 at that tau; `med` "
      "and `p10` are that bid in cents; `size` is the contracts resting at "
      "it. Positions opened later than a given tau are simply absent from "
      "that row (`n` says how many were open).")
    w()
    for name, pop in (("POSITIONS the gate opened", P),
                      ("COMPANION: every model-certain market", C)):
        w(f"### {name}")
        w()
        w("| tau | group | n pos | closes | have a bid | 95% CI | med bid | "
          "p10 bid | med size | med belief |")
        w("|---|---|---|---|---|---|---|---|---|---|")
        for row in decisive_table(pop):
            for key, lab in (("won", "WON"), ("lost", "LOST")):
                d = row[key]
                if not d["n"]:
                    w(f"| {row['tau']} | {lab} | 0 | 0 | -- | -- | -- | -- "
                      f"| -- | -- |")
                    continue
                ci = d["ci"]
                w(f"| {row['tau']} | {lab} | {d['n']:,} | {d['closes']:,} | "
                  f"{100 * d['have_frac']:.1f}% | "
                  f"[{100 * ci[0]:.1f}, {100 * ci[1]:.1f}] | "
                  + (f"{100 * d['med_bid']:.1f}c | " if d['med_bid'] is not None else "-- | ")
                  + (f"{100 * d['p10_bid']:.1f}c | " if d['p10_bid'] is not None else "-- | ")
                  + (f"{d['med_size']:.0f} | " if d['med_size'] is not None else "-- | ")
                  + (f"{100 * d['med_belief']:.2f}% |" if d['med_belief'] is not None else "-- |"))
        w()

    # ---- 4. ADVERSE SELECTION -------------------------------------------
    w("## 2. ADVERSE-SELECTION CONTROL -- exit fill rate, losers vs winners")
    w()
    w("The test `results/RESULTS_maker.md` ran on the resting bid, in its own "
      "units. There a bid filled on **100% of eventual losers and 29% of "
      "winners** and the idea died. Here the question is the mirror image: an "
      "exit that fills on the winners and not the losers is worse than "
      "holding.")
    w()
    w("| exit tau | floor | winners exit | 95% CI | losers exit | 95% CI | "
      "MDE (pp) |")
    w("|---|---|---|---|---|---|---|")
    for t in EXIT_TAUS:
        for fl in EXIT_FLOORS:
            a = adverse_control(P, t, fl)
            ww, ll = a["won"], a["lost"]
            w(f"| {t} | {fl:.3f} | "
              f"{ww['exits']}/{ww['n']} = {100 * (ww['rate'] or 0):.1f}% | "
              f"[{100 * ww['ci'][0]:.1f}, {100 * ww['ci'][1]:.1f}] | "
              f"{ll['exits']}/{ll['n']} = "
              + (f"{100 * ll['rate']:.1f}%" if ll['rate'] is not None else "--")
              + " | "
              + (f"[{100 * ll['ci'][0]:.1f}, {100 * ll['ci'][1]:.1f}]"
                 if ll['ci'][0] is not None else "--")
              + " | " + (f"{100 * a['mde']:.1f}" if a['mde'] else "--") + " |")
    w()

    # ---- the COMPANION control, where the power is -----------------------
    w("### 2b. The same control on the COMPANION population")
    w()
    w("The positions the gate opens are few and their losers are fewer, so "
      "the table above can only ever refute a very large asymmetry. This is "
      "the backward-looking companion CLAUDE.md requires: every market the "
      "model called near-certain inside the entry window, whether or not an "
      "offer existed for us to buy. Same book, same side, same question, and "
      "**an order of magnitude more losers** -- which is the point, because "
      "losers are what the decisive table is short of. It cannot be priced "
      "(those markets have no entry price), so it reports the FILL RATE only, "
      "from the same `cap` summary the position table is cross-checked "
      "against in the self-test. The two strata are reported separately and "
      "never pooled: the first is the live gate exactly, the second is the "
      f"{COMPANION_PIN}-{pinrun.PIN} band, which is where the flips live.")
    w()
    w("| exit tau | floor | winners exit | 95% CI | losers exit | 95% CI | "
      "MDE (pp) |")
    w("|---|---|---|---|---|---|---|")
    strata = [
        (f"reached the LIVE gate (conf >= {pinrun.PIN})",
         [c for c in C if c.get("certain_tau") is not None]),
        (f"near-certain only ({COMPANION_PIN} <= conf < {pinrun.PIN})",
         [c for c in C if c.get("certain_tau") is None]),
    ]
    for lab, pop in strata:
        nl_ = sum(1 for c in pop if not c["won"])
        w(f"**{lab}** -- {len(pop):,} markets, "
          f"{len(set(c['close'] for c in pop)):,} closes, {nl_:,} of which "
          f"the model's side eventually LOST.")
        w()
        w("| exit tau | floor | winners exit | 95% CI | losers exit | 95% CI "
          "| MDE (pp) |")
        w("|---|---|---|---|---|---|---|")
        for t in EXIT_TAUS:
            for fl in EXIT_FLOORS:
                a = cap_control(pop, t, fl)
                ww, ll = a["won"], a["lost"]
                w(f"| {t} | {fl:.3f} | {ww['exits']:,}/{ww['n']:,} = "
                  f"{100 * (ww['rate'] or 0):.1f}% | "
                  + (f"[{100 * ww['ci'][0]:.1f}, {100 * ww['ci'][1]:.1f}]"
                     if ww['ci'][0] is not None else "--") + " | "
                  f"{ll['exits']:,}/{ll['n']:,} = "
                  + (f"{100 * ll['rate']:.1f}%" if ll['rate'] is not None
                     else "--") + " | "
                  + (f"[{100 * ll['ci'][0]:.1f}, {100 * ll['ci'][1]:.1f}]"
                     if ll['ci'][0] is not None else "--")
                  + " | " + (f"{100 * a['mde']:.1f}" if a['mde'] else "--")
                  + " |")
        w()

    # ---- 3. PRICE THE RULE ----------------------------------------------
    w("## 3. PRICE THE RULE -- per close, size 20")
    w()
    w(f"Denominator is **every close in the window ({closes_all:,})**, so a "
      f"close we trade nothing on counts as zero. `hold` is the same "
      f"population held to settlement, which is what `pin` does today. "
      f"Positions that fail to exit keep their original outcome.")
    w()
    w("| exit tau | floor | full exits | partial | hold $ | exit $ | delta $ "
      "| hold $/close | exit $/close | med exit bid |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    best = None
    for t in EXIT_TAUS:
        for fl in EXIT_FLOORS:
            s = price_rule(P, t, fl, closes_all)
            if best is None or s["delta"] > best["delta"]:
                best = s
            w(f"| {t} | {fl:.3f} | {s['full_exits']}/{s['positions']} = "
              f"{100 * s['fill_rate']:.1f}% | {s['partial_exits']} | "
              f"{s['hold_pnl']:+.2f} | {s['exit_pnl']:+.2f} | "
              f"**{s['delta']:+.2f}** | {s['hold_per_close']:+.4f} | "
              f"{s['exit_per_close']:+.4f} | "
              + (f"{100 * s['median_exit_bid']:.1f}c |"
                 if s['median_exit_bid'] is not None else "-- |"))
    w()

    # ---- BREAK-EVEN, the loss-rate-free pricing --------------------------
    w("## 4. THE BREAK-EVEN LOSS RATE -- pricing this without a tape loss rate")
    w()
    w("Section 3's dollar columns are a function of how often the REPLAY's "
      "positions lost, and CLAUDE.md's 2026-09-10 rule 5 forbids reading that "
      "as how often WE lose (0.11% on the tape against 3.4% live, intervals "
      "that do not overlap). Read alone they would therefore flatter HOLDING "
      "for exactly the forbidden reason. So the loss rate is taken out of the "
      "comparison. Per contract, buying at `px` and selling at `b` with both "
      "legs taker, exiting a winner costs `(1-b) + fee` and exiting a loser "
      "gains `b - fee`; those sum to 1. The rule beats holding above")
    w()
    w("    p* = e_w*c_w / (e_w*c_w + e_l*g_l)")
    w()
    w("**Compare p-star against the LIVE loss rate, which comes from live fills "
      "only.** `optimistic` assumes the losers exit as often and as dear as "
      "the winners; `measured` uses the losers actually observed.")
    w()
    w("| exit tau | floor | e_w | e_l | med net exit (win) | p* optimistic | "
      "med net exit (lose) | p* measured |")
    w("|---|---|---|---|---|---|---|---|")
    for t in EXIT_TAUS:
        for fl in EXIT_FLOORS:
            be = break_even(P, t, fl)
            w(f"| {t} | {fl:.3f} | "
              + (f"{100 * be['e_w']:.1f}% ({be['exits_w']}/{be['n_w']})"
                 if be['e_w'] is not None else "--") + " | "
              + (f"{100 * be['e_l']:.1f}% ({be['exits_l']}/{be['n_l']})"
                 if be['e_l'] is not None else "--") + " | "
              + (f"{100 * be['g_opt']:.2f}c" if be['g_opt'] else "--") + " | "
              + (f"**{100 * be['p_opt']:.2f}%**" if be['p_opt'] else "--")
              + " | "
              + (f"{100 * be['g_meas']:.2f}c" if be['g_meas'] else "--")
              + " | "
              + (f"**{100 * be['p_meas']:.2f}%**" if be['p_meas'] else "--")
              + " |")
    w()

    # ---- 4b: the rule priced at ASSUMED live loss rates -------------------
    w("### 4b. What the rule is worth at an ASSUMED live loss rate")
    w()
    w("The same arithmetic, read the other way. The loss rate is a PARAMETER "
      "here -- supply it from live fills, never from this page. `e_w` is the "
      "winners' exit rate measured on the positions; `e_l` is the losers' "
      "exit rate taken from the COMPANION live-gate stratum, because that is "
      "where the losers are. Cents per contract, exiting minus holding; "
      "positive means sell.")
    w()
    w("| exit tau | floor | e_w | e_l (companion) | "
      + " | ".join(f"at {100 * q:.0f}% loss" for q in ASSUMED_LOSS_RATES)
      + " |")
    w("|---|---|---|" + "---|" * (len(ASSUMED_LOSS_RATES) + 1))
    Cg = [c for c in C if c.get("certain_tau") is not None]
    for t in EXIT_TAUS:
        for fl in EXIT_FLOORS:
            be = break_even(P, t, fl)
            cc = cap_control(Cg, t, fl)
            e_w, g = be["e_w"], be["g_opt"]
            e_l = cc["lost"]["rate"]
            cells = [delta_at(e_w, e_l, g, q) for q in ASSUMED_LOSS_RATES]
            w(f"| {t} | {fl:.3f} | "
              + (f"{100 * e_w:.1f}%" if e_w is not None else "--") + " | "
              + (f"{100 * e_l:.1f}% ({cc['lost']['exits']}/"
                 f"{cc['lost']['n']})" if e_l is not None else "--") + " | "
              + " | ".join((f"**{v:+.2f}c**" if v is not None else "--")
                           for v in cells) + " |")
    w()
    w("Read the row you can actually fill and the column that matches the "
      "live loss rate. A cell is positive only because a loser is worth ~99c "
      "to get out of and a winner only ~1c to give up -- which is why `e_l` "
      "is the number that decides this and not `e_w`.")
    w()

    # ---- ARTEFACT CHECKS -------------------------------------------------
    w("## 5. WHAT WOULD HAVE TO BE TRUE FOR THIS TO BE AN ARTEFACT")
    w()
    w("**(a) A STALE BOOK.** If the collector went quiet, the replayed book "
      "keeps showing the last bid it saw. A position going wrong is exactly "
      "when the real book would reprice, so a stale book manufactures "
      "surviving bids on losers -- the artefact that would fake this result. "
      "`results/RESULTS_tapegaps.md` measures 3.28% of seconds inside this "
      "tau band falling in a silent run of >= 10 s. So every headline is "
      "re-run with live's own freshness rail, `MAX_BOOK_AGE_MS = "
      f"{pinrun.MAX_BOOK_AGE_MS}`, applied to the exit moment as live applies "
      "it to the entry moment.")
    w()
    w("| exit tau | floor | full exits (no age gate) | full exits (age gate) "
      "| delta $ (no gate) | delta $ (age gate) |")
    w("|---|---|---|---|---|---|")
    for t in EXIT_TAUS:
        for fl in EXIT_FLOORS:
            s0 = price_rule(P, t, fl, closes_all)
            s1 = price_rule(P, t, fl, closes_all, pinrun.MAX_BOOK_AGE_MS)
            w(f"| {t} | {fl:.3f} | {s0['full_exits']}/{s0['positions']} | "
              f"{s1['full_exits']}/{s1['positions']} | {s0['delta']:+.2f} | "
              f"{s1['delta']:+.2f} |")
    w()
    ages = []
    bels_w, bels_l = [], []
    for p in P:
        r = simulate_exit(p, 10, 0.99)
        if r["qty"] > 0:
            (bels_w if p["won"] else bels_l).append(r["belief"])
    for p in P:
        for ob in p["obs"]:
            if ob[3] is not None:
                ages.append(ob[3])
    w(f"Book age across every observation in the watch window: median "
      + (f"{pct(ages, 0.5):.0f} ms, p90 {pct(ages, 0.90):.0f} ms, p99 "
         f"{pct(ages, 0.99):.0f} ms" if ages else "--")
      + ".")
    w()
    w("**(b) THE MODEL STILL BELIEVED AT THE EXIT.** If a losing position "
      "exits at 99c only because the model had not yet noticed it was losing, "
      "the bid is real but the rule is not selling a doomed position -- it is "
      "selling a position that looks fine, which is the same thing the "
      "winners are. The model's belief at the exit moment, at exit tau 10 / "
      "floor 0.99:")
    w()
    w(f"- winners that exited: median belief "
      + (f"{100 * pct([b for b in bels_w if b is not None], 0.5):.3f}%"
         if [b for b in bels_w if b is not None] else "--")
      + f" ({len(bels_w)} exits)")
    w(f"- losers that exited: median belief "
      + (f"{100 * pct([b for b in bels_l if b is not None], 0.5):.3f}%"
         if [b for b in bels_l if b is not None] else "--")
      + f" ({len(bels_l)} exits)")
    w()
    w("**(c) THE BID IS OUR OWN RACE TO WIN.** Everything above assumes we "
      "reach the resting bid first. Live we win ~70% of the races we enter on "
      "the BUY side; there is no reason the sell side is easier, and a "
      "collapsing book is precisely where the race is hardest. Multiply every "
      "fill rate by roughly that factor before believing any dollar figure.")
    w()

    # ---- 5. HOLDOUT ------------------------------------------------------
    w("## 6. FIT / HOLDOUT -- first 70% of closes vs last 30%")
    w()
    w(f"Split at close {cut} "
      f"({time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(cut)) if cut else '--'}). "
      f"Nothing here is a survivor unless the holdout agrees.")
    w()
    w("| slice | positions | closes | exit tau | floor | full exits | hold $ "
      "| exit $ | delta $ |")
    w("|---|---|---|---|---|---|---|---|---|")
    for lab, pop in (("fit (first 70%)", fit), ("HOLDOUT (last 30%)", hold)):
        ncl = len(set(p["close"] for p in pop))
        for t in EXIT_TAUS:
            for fl in EXIT_FLOORS:
                s = price_rule(pop, t, fl, max(1, ncl))
                w(f"| {lab} | {s['positions']} | {ncl} | {t} | {fl:.3f} | "
                  f"{s['full_exits']} = {100 * s['fill_rate']:.1f}% | "
                  f"{s['hold_pnl']:+.2f} | {s['exit_pnl']:+.2f} | "
                  f"{s['delta']:+.2f} |")
    w()
    txt = "\n".join(out) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(txt)
    log(f"  report written to {os.path.abspath(path)}")
    return {"best": best, "cut": cut, "closes_all": closes_all,
            "fit": fit, "hold": hold}


# ------------------------------------------------------------------ self-test
def _plant(n_win, n_lose, bid_win, bid_lose, px=0.96, n=20.0, size=500.0,
           taus=range(30, 2, -1)):
    """A world where the answer is already known.

    `bid_win` / `bid_lose` are the bid on OUR side for the two groups, or
    None for "nobody is bidding". One position per close, so the per-close
    unit and the position unit agree and the arithmetic can be done by hand.
    """
    P = []
    for i in range(n_win + n_lose):
        won = i < n_win
        bid = bid_win if won else bid_lose
        rec = {"ticker": f"T{i}", "coin": "KXBTC15M", "close": 1000 + i,
               "want": "yes", "tau_in": 30, "price": px, "n": n, "won": won,
               "bought": True, "grid": {}, "obs": [], "cap": {}}
        bk = pindata.Book()
        for t in taus:
            bk.yes.clear()
            if bid is not None:
                bk.yes[round(bid, 4)] = size
            bk.no[0.001] = 1.0
            bk.last_ts = 0
            observe(rec, pinsim.book_view(bk, 0), t,
                    0.999 if won else 0.5, 0, n)
        P.append(rec)
    return P


def selftest():
    print("SELF-TEST -- pinexit")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # --- (iii) THE FEE ARITHMETIC, HAND-CHECKED AT TWO PRICES -------------
    # billed_fee = ceil(0.07 * count * p * (1-p) to the next $0.0001).
    #   0.07 * 20 * 0.96 * 0.04 = 0.053760 -> 0.0538   (the entry)
    #   0.07 * 20 * 0.99 * 0.01 = 0.013860 -> 0.0139   (the exit)
    f_in = pinrun.billed_fee(0.96, 20)
    f_out = pinrun.billed_fee(0.99, 20)
    ck(abs(f_in - 0.0538) < 1e-9 and abs(f_out - 0.0139) < 1e-9,
       f"fee at 96c x20 = ${f_in:.4f} and at 99c x20 = ${f_out:.4f}, both "
       f"ceilinged to $0.0001 exactly as billed_fee documents")
    hand = 20 * (0.99 - 0.96) - f_in - f_out            # 0.60 - 0.0677
    ck(abs(hand - 0.5323) < 1e-9,
       f"BY HAND: buy 20 at 96c, sell 20 at 99c, both legs taker -> "
       f"${hand:.4f} = {100 * hand / 20:.4f}c per contract "
       f"(the brief's +2.66c, reconciled)")
    one = _plant(1, 0, 0.99, None)
    r1 = simulate_exit(one[0], 10, 0.99)
    ck(abs(r1["pnl"] - hand) < 1e-9 and r1["exited"],
       f"and simulate_exit() reproduces that number from a planted book "
       f"(${r1['pnl']:.4f}), so the estimator's fee arithmetic IS the hand "
       f"arithmetic")
    # a second price pair, so the check is not a single lucky rounding
    f2i, f2o = pinrun.billed_fee(0.90, 20), pinrun.billed_fee(0.985, 20)
    hand2 = 20 * (0.985 - 0.90) - f2i - f2o
    two = _plant(1, 0, 0.985, None, px=0.90)
    r2 = simulate_exit(two[0], 10, 0.985)
    ck(abs(f2i - 0.1260) < 1e-9 and abs(f2o - 0.0207) < 1e-9
       and abs(r2["pnl"] - hand2) < 1e-9,
       f"second price pair: 90c->98.5c, fees ${f2i:.4f} + ${f2o:.4f}, net "
       f"${hand2:.4f} ({100 * hand2 / 20:.3f}c/contract), matched")

    # --- our_bid INVERTS book_view AGAINST A REAL pindata.Book -----------
    bk = pindata.Book()
    bk.delta("yes", 0.99, 250.0, 1000)       # somebody bids 99c for YES
    bk.delta("no", 0.03, 400.0, 1000)        # and 3c for NO -> yes_ask 97c
    bv = pinsim.book_view(bk, 1000)
    yb, ysz = our_bid(bv, "yes")
    nb, nsz = our_bid(bv, "no")
    ck(abs(yb - 0.99) < 1e-9 and ysz == 250.0,
       f"our_bid recovers the REAL 99c yes bid and its 250 contracts from "
       f"book_view's no_ask ({yb}, {ysz}) -- the inversion is not assumed")
    ck(abs(nb - 0.03) < 1e-9 and nsz == 400.0,
       f"and the 3c no bid with its 400 ({nb}, {nsz})")
    empty = pinsim.book_view(pindata.Book(), 1000)
    ck(our_bid(empty, "yes") == (None, 0.0),
       "and an empty book reports NO bid rather than a price of zero")

    # --- (i) A WORLD WHERE THE BID PERSISTS ON LOSERS ---------------------
    # 96 winners + 4 losers at 96c is EXACTLY break-even before fees:
    #   96 * 0.04 = 3.84  and  4 * 0.96 = 3.84.
    # So holding is (0 - fees) and any real exit gain must show up as a gain.
    W1 = _plant(96, 4, 0.99, 0.99)
    s1 = price_rule(W1, 10, 0.99, 100)
    a1 = adverse_control(W1, 10, 0.99)
    ck(abs(s1["hold_pnl"] + 100 * f_in) < 1e-6,
       f"planted world (i): holding is break-even minus fees "
       f"(${s1['hold_pnl']:.4f} vs -${100 * f_in:.4f})")
    ck(s1["fill_rate"] == 1.0 and a1["lost"]["rate"] == 1.0,
       "the bid PERSISTS on the losers by construction: 100% exit both sides")
    ck(s1["delta"] > 0 and abs(s1["exit_pnl"] - (100 * hand)) < 1e-6,
       f"and the estimator reports the GAIN, to the cent: exit "
       f"${s1['exit_pnl']:.2f} vs hold ${s1['hold_pnl']:.2f}, delta "
       f"${s1['delta']:+.2f} = 100 x ${hand:.4f}")
    d1 = decisive_table(W1)
    ck(all(r["lost"]["have_frac"] == 1.0 and r["won"]["have_frac"] == 1.0
           for r in d1),
       "and the decisive table shows the bid present on BOTH groups at "
       "every tau")

    # --- (ii) A WORLD WHERE THE BID VANISHES ON LOSERS --------------------
    # Same outcomes, same prices; the only change is that the losers have no
    # bid. The exit then sells only the trades we would have won anyway.
    W2 = _plant(96, 4, 0.99, None)
    s2 = price_rule(W2, 10, 0.99, 100)
    a2 = adverse_control(W2, 10, 0.99)
    ck(a2["won"]["rate"] == 1.0 and a2["lost"]["rate"] == 0.0,
       f"planted world (ii): winners exit {100 * a2['won']['rate']:.0f}%, "
       f"losers {100 * a2['lost']['rate']:.0f}% -- the RESULTS_maker.md trap, "
       f"planted")
    exp2 = 96 * hand + 4 * (-4 * 0.96 / 4 - f_in)       # 96 exits + 4 held
    exp2 = 96 * hand + 4 * (-20 * 0.96 - f_in)
    ck(abs(s2["exit_pnl"] - exp2) < 1e-6,
       f"the exiting P&L is 96 x ${hand:.4f} + 4 full losses = "
       f"${s2['exit_pnl']:.2f}, hand-checked against ${exp2:.2f}")
    ck(s2["delta"] < 0 and s2["exit_pnl"] < s2["hold_pnl"],
       f"AND THE ESTIMATOR REPORTS THE LOSS, not a gain: exit "
       f"${s2['exit_pnl']:.2f} vs hold ${s2['hold_pnl']:.2f}, delta "
       f"${s2['delta']:+.2f}. An estimator that scored only the fills it got "
       f"would have said {100 * 96 * hand / 96:.4f} and called this a win.")
    d2 = decisive_table(W2)
    ck(all(r["lost"]["have_frac"] == 0.0 for r in d2)
       and all(r["won"]["have_frac"] == 1.0 for r in d2),
       "and the decisive table SEPARATES them: 0% of losers keep a bid, 100% "
       "of winners do")

    # --- `cap` MUST AGREE WITH THE PER-EVENT SIMULATION -------------------
    # The companion population is scored from `cap` alone, so if the two ever
    # disagreed the large table and the small one would be measuring
    # different things and nobody would notice.
    _agree = True
    for _w in (W1, W2, _plant(10, 0, 0.987, None), _plant(10, 0, 0.99, None,
                                                          size=5.0)):
        for _t in EXIT_TAUS:
            for _f in EXIT_FLOORS:
                for _p in _w:
                    if cap_fill(_p, _t, _f, True) !=                             simulate_exit(_p, _t, _f)["exited"]:
                        _agree = False
                    if cap_fill(_p, _t, _f, False) !=                             (simulate_exit(_p, _t, _f)["qty"] > 0):
                        _agree = False
    ck(_agree,
       "the compact `cap` summary and the full per-event simulation agree on "
       "BOTH fill definitions, at every exit tau and floor, on four planted "
       "worlds including a partial-fill one -- so the companion table and the "
       "position table measure the same event")
    _cc = cap_control(W2, 10, 0.99)
    ck(_cc["won"]["rate"] == 1.0 and _cc["lost"]["rate"] == 0.0,
       f"and cap_control reproduces world (ii)'s asymmetry from `cap` alone "
       f"({100 * _cc['won']['rate']:.0f}% vs {100 * _cc['lost']['rate']:.0f}%)")

    # --- the BREAK-EVEN LOSS RATE, hand-checked ---------------------------
    # b = 0.99, n = 20: fee_out $0.0139 = 0.0695c per contract, so exiting a
    # winner costs (1 - 0.99) + 0.000695 = 1.0695c and exiting a loser gains
    # 0.99 - 0.000695 = 98.9305c. They sum to $1.00 exactly, and with both
    # groups exiting every time p* = 1.0695 / 100 = 1.0695%.
    be1 = break_even(W1, 10, 0.99)
    ck(abs(be1["p_opt"] - 0.010695) < 1e-9
       and abs(be1["p_meas"] - 0.010695) < 1e-9,
       f"break-even in world (i): p* = {100 * be1['p_opt']:.4f}% optimistic "
       f"and {100 * be1['p_meas']:.4f}% measured, hand-checked against "
       f"1.0695% = (1 - 0.99 + 0.000695)")
    be2 = break_even(W2, 10, 0.99)
    ck(abs(be2["p_opt"] - 0.010695) < 1e-9 and be2["p_meas"] == 1.0,
       f"and in world (ii) the OPTIMISTIC figure is unchanged "
       f"({100 * be2['p_opt']:.4f}%) while the MEASURED one is "
       f"{100 * be2['p_meas']:.0f}% -- no loss rate makes an exit that never "
       f"reaches a loser worth taking. Quoting only the optimistic column "
       f"is how this idea would be sold wrongly.")

    # --- delta_at MUST AGREE WITH break_even AT THE BREAK-EVEN POINT ------
    # Two ways of writing the same arithmetic; if they ever disagreed, the
    # table the verdict is read off and the table that sets the bar would be
    # describing different rules.
    _g = be1["g_opt"]
    ck(abs(delta_at(1.0, 1.0, _g, be1["p_opt"])) < 1e-9,
       f"at the break-even loss rate {100 * be1['p_opt']:.4f}% the change from "
       f"exiting is exactly zero ({delta_at(1.0, 1.0, _g, be1['p_opt']):+.2e}c)")
    ck(delta_at(1.0, 1.0, _g, 0.02) > 0 and delta_at(1.0, 1.0, _g, 0.005) < 0,
       f"above it the rule pays ({delta_at(1.0, 1.0, _g, 0.02):+.2f}c at a 2% "
       f"loss rate) and below it the rule costs "
       f"({delta_at(1.0, 1.0, _g, 0.005):+.2f}c at 0.5%)")
    ck(all(delta_at(1.0, 0.0, _g, q) < 0 for q in ASSUMED_LOSS_RATES),
       "and with the losers never reachable it is negative at EVERY assumed "
       "loss rate -- no loss rate rescues an exit that only sells winners")
    _hand = 100.0 * (-(1 - 0.02) * 0.9 * (1 - 0.989305)
                     + 0.02 * 0.6 * 0.989305)
    ck(abs(delta_at(0.9, 0.6, 0.989305, 0.02) - _hand) < 1e-9,
       f"hand-check with asymmetric fills (e_w 0.9, e_l 0.6, 2% losses): "
       f"{delta_at(0.9, 0.6, 0.989305, 0.02):+.4f}c = {_hand:+.4f}c")

    # --- a NULL world: nothing planted, nothing found ---------------------
    W3 = _plant(96, 4, None, None)
    s3 = price_rule(W3, 10, 0.99, 100)
    ck(s3["fill_rate"] == 0.0 and abs(s3["delta"]) < 1e-12,
       f"NULL: with no bid anywhere the exit never fires and the delta is "
       f"exactly zero ({s3['delta']:+.6f}) -- the estimator does not "
       f"manufacture an edge out of a world with nothing in it")

    # --- the FLOOR and the TAU window must actually bind -------------------
    W4 = _plant(10, 0, 0.987, None)
    ck(price_rule(W4, 10, 0.985, 10)["fill_rate"] == 1.0
       and price_rule(W4, 10, 0.99, 10)["fill_rate"] == 0.0,
       "a 98.7c bid clears the 0.985 floor and is refused by the 0.99 floor")
    W5 = _plant(10, 0, 0.99, None, taus=[20, 19, 18])
    ck(price_rule(W5, 15, 0.99, 10)["fill_rate"] == 0.0
       and price_rule(W5, 20, 0.99, 10)["fill_rate"] == 1.0,
       "a bid that only exists at tau 18-20 is invisible to EXIT_TAU 15 and "
       "reachable at EXIT_TAU 20 -- the tau window binds")
    W6 = _plant(10, 0, 0.99, None, taus=[2, 1])
    ck(price_rule(W6, 15, 0.99, 10)["fill_rate"] == 0.0,
       "and a bid that only appears below tau 3 is never used, because the "
       "measurement window stops there")

    # --- PARTIAL fills must not be counted as full exits -------------------
    W7 = _plant(10, 0, 0.99, None, size=5.0)
    s7 = price_rule(W7, 10, 0.99, 10)
    ck(s7["fill_rate"] == 0.0 and s7["partial_exits"] == 10,
       f"5 contracts resting against a 20-lot is a PARTIAL, not an exit "
       f"(full {s7['full_exits']}, partial {s7['partial_exits']})")
    r7 = simulate_exit(W7[0], 10, 0.99)
    hand7 = 5 * (0.99 - 0.96) - pinrun.billed_fee(0.99, 5) - f_in + 15 * 0.04
    ck(abs(r7["pnl"] - hand7) < 1e-9,
       f"and its P&L is 5 sold + 15 held to settlement = ${r7['pnl']:.4f}, "
       f"hand-checked against ${hand7:.4f}")

    # --- the MDE must shrink with n and be honest about a tiny group -------
    m_small = mde_two_prop(500, 500, 4)
    m_big = mde_two_prop(500, 500, 400)
    m_pure = mde_two_prop(10 ** 6, 10 ** 6, 4)
    ck(m_small is not None and m_big is not None and m_small > m_big,
       f"MDE with 4 in the small group ({100 * m_small:.1f} pp) is far larger "
       f"than with 400 ({100 * m_big:.1f} pp) -- 'no effect' and 'no power' "
       f"stay distinguishable")
    ck(abs(m_pure - (1.0 - 0.20 ** 0.25)) < 0.005,
       f"and with the reference rate known exactly it collapses to the closed "
       f"form 1 - 0.2^(1/4) = {100 * (1 - 0.20 ** 0.25):.1f} pp (got "
       f"{100 * m_pure:.1f}); the {100 * m_small:.1f} pp above is larger "
       f"because the REFERENCE group's own interval is priced in too")
    ck(mde_two_prop(490, 500, 1) is None,
       "and against a 98.0% reference with only ONE observation in the test "
       "group, no outcome could separate the two intervals -- the MDE is "
       "reported as undefined rather than as a number")

    # --- the stage must refuse to be read as a live loss rate -------------
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    ck("not OUR live loss rate" in src or "no loss rate on this page is OUR" in src,
       "the report carries the CLAUDE.md 2026-09-10 rule-5 warning in text")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=216)
    ap.add_argument("--end", default=None)
    ap.add_argument("--size", type=float, default=20.0)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--report", default=os.path.join(HERE, "..", "results",
                                                     "RESULTS_exit.md"))
    ap.add_argument("--analyse", default=None,
                    help="skip the tape and report from an existing jsonl")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")
    if a.analyse:
        P, C = load_positions(a.analyse)
        try:
            with open(a.analyse + ".meta.json", encoding="utf-8") as mh:
                meta = json.load(mh)
        except OSError:
            meta = {"hours": "?",
                    "closes_window": len(set(p["close"] for p in P))}
            print("  *** no meta sidecar: the per-close denominator falls "
                  "back to TRADED closes, which flatters $/close ***")
    else:
        meta = walk_tape(a.hours, a.end, size=a.size, out_path=a.out)
        P, C = load_positions(a.out)
    if not P:
        print("  loaded nothing -- no positions opened in this window")
        return
    write_report(P, C, meta, a.report)


if __name__ == "__main__":
    main()
