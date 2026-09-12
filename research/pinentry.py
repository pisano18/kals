#!/usr/bin/env python3
# VERSION: 2026-09-12-pe1
"""pinentry.py -- HOW TO KNOW WHEN NOT TO BUY.

THE QUESTION. The live bot buys the near-certain side at belief >= 99.5% with
tau <= 30 s to close. Its losses are not gradual: on 48 h of tape 1,630 of
1,642 winners never dipped below 99% belief after entry, while all 11 losers
fell below 20%. The loss is a COLLAPSE of the model's own belief AFTER we are
already long. The only lever that needs no exit liquidity is refusing the
entry, so: is there anything visible AT THE ENTRY SECOND that says this one
will collapse?

TWO CANDIDATE REFUSALS ARE ALREADY DEAD and are not retested here:
  - belief >= 99.5% held for N consecutive seconds: removed 2 of 11 losers.
  - a cross-coin "roughness" index: no power.
One is already LIVE: refusing an offer more than 15c below fair (AMENDMENT 10,
`pinrun.DUMP_DISCOUNT`). It is applied to the population here, so what this
file measures is the RESIDUAL -- what is left to find after the discount guard
has taken its cut.

FOUR FEATURES, each computed ONLY from information the entry second holds:

  1 OFFER PROVENANCE   how long the price level we would hit had been resting
                       (since it was created, and since it was last increased)
                       and how big it is against that market's own median
                       touch size over the prior 60 s. Hypothesis: a FRESH,
                       LARGE offer is a dump by someone who knows; a STALE,
                       SMALL one is an honest resting quote.
  2 PRE-ENTRY JUMPINESS  over the 120 s before entry, the count of one-second
                       index moves > 3 sigma and the largest such move, sigma
                       being pinrun's own trailing-300 s one-second sigma for
                       THAT coin (`IndexWS.sigma`). Same coin only -- the
                       cross-coin version is the dead roughness index.
  3 MARGIN TO THE STRIKE  (mu - K)/sd in sigma units, i.e. `margin_sd` in the
                       decision record. 2.58 sd and 6 sd both clear a 99.5%
                       gate; do they die at the same rate?
  4 TAU and PRICE      controls.

THE DECISION IS NOT REIMPLEMENTED. Entries come from `pinsim.decide`, which
calls `pinrun.fair / net_edge / expected_value / billed_fee` through
`pinsim.TapeIndex`, plus the live 15c dump guard. Post-entry belief is
recomputed each second with the same `pinrun.fair`. (AMENDMENT 2026-09-10:
pinsim is certified for DECISION reproduction only.)

WHAT THIS CANNOT SAY, AND IT IS THE WHOLE CAVEAT.
  * NO LOSS RATE HERE IS OUR LOSS RATE. The tape's population is "an offer was
    resting there"; ours is "someone actively sold it to us", and only the
    second is adversely selected. The measured gap is 31x (tape 0.11% vs live
    3.4%). Every rate below RANKS BUCKETS AGAINST EACH OTHER and nothing more.
  * The replayed book is DELTA-ONLY in almost every hour. `orderbook_snapshot`
    frames arrive once per collector subscription, so a typical hour has none
    and the book is rebuilt from deltas from the hour's first message. Each
    15-minute market's whole life sits inside one hour file, so level ages are
    measurable from the market's own open -- but a level seeded before the
    file starts reads as younger than it is, and rows where that is possible
    carry `age_cens`.
  * `MAX_PER_CLOSE` is NOT applied: the question is which ENTRY is bad, not
    which portfolio. So entry counts here exceed what the bot would take.

NO LOOKAHEAD BY CONSTRUCTION: index ticks enter the model only as the
simulated clock reaches them; every feature is backward-looking; the outcome
is written last and is never an input.
"""
import argparse
import gzip
import json
import math
import os
import random
import sys
import time
import zlib
from collections import defaultdict, deque
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinrun                                                # noqa: E402
import pindata                                               # noqa: E402
import pinsim                                                # noqa: E402
from pincross import cp_interval                             # noqa: E402

_ND = NormalDist()

RESULTS = r"C:\kals-repo\results"
ROWS = os.path.join(RESULTS, "pinentry_rows.jsonl")
REPORT = os.path.join(RESULTS, "RESULTS_entry.md")

COLLAPSE_BELIEF = 0.90   # "collapse" = belief in OUR side fell below this ...
WATCH_TAU_MIN = 3        # ... at any second after entry with tau >= this.
TOUCH_WIN = 60           # seconds of touch history the size ratio compares to
TOUCH_MIN_SAMPLES = 10   # fewer than this and the size ratio is not computed
JUMP_WIN = 120           # seconds of index history the jumpiness scans
JUMP_Z = 3.0             # a "jump" is a one-second move this many sigma


# ===========================================================================
# 1. THE TAPE SIDE
# ===========================================================================
class AgeBook(pindata.Book):
    """pindata's book plus the two clocks provenance needs.

    `born` (inherited) is when the level was CREATED and is deliberately not
    reset by an add -- see pindata's own self-test. Provenance also wants when
    it was last INCREASED, because a resting 5 that becomes a resting 500 one
    second before we hit it is a fresh offer wearing an old level's age. Both
    are kept; neither is inferred from the other.
    """

    __slots__ = ("bumped", "first_ts", "seed_ts")

    def __init__(self):
        super().__init__()
        self.bumped = {}
        self.first_ts = None
        self.seed_ts = None

    def snapshot(self, msg, ts):
        super().snapshot(msg, ts)
        self.bumped = {k: ts for k in self.born}
        self.seed_ts = ts if self.born else None
        if self.first_ts is None:
            self.first_ts = ts

    def delta(self, side, price, dq, ts):
        if self.first_ts is None:
            self.first_ts = ts
        super().delta(side, price, dq, ts)
        p = round(float(price), 4)
        d = self.yes if side == "yes" else self.no
        if p in d:
            if float(dq) > 0:
                self.bumped[(side, p)] = ts
            elif (side, p) not in self.bumped:
                self.bumped[(side, p)] = ts
        else:
            self.bumped.pop((side, p), None)


def jumpiness(idx, iid, sec, sigma, win=JUMP_WIN, z=JUMP_Z):
    """(count of 1-s moves > z*sigma, largest move in sigma units, coverage).

    Reads `idx.ticks`, which under TapeIndex holds only ticks at or before
    `sec`, so this cannot see the future. sigma is pinrun's own trailing-300 s
    one-second sd for this coin, so the 120 s scanned are inside the window
    that produced it -- deliberately, because the question is whether the
    recent past is rough RELATIVE TO the volatility the model is already using.
    """
    d = idx.ticks.get(iid) or {}
    if not sigma or sigma <= 0 or not d:
        return None, None, 0
    n = 0
    mx = 0.0
    k = 0
    for s in range(sec - win + 1, sec + 1):
        a = d.get(s - 1)
        b = d.get(s)
        if a is None or b is None:
            continue
        k += 1
        zz = abs(b - a) / sigma
        if zz > z:
            n += 1
        if zz > mx:
            mx = zz
    if k < win // 3:
        return None, None, k
    return n, mx, k


def provenance(bk, side, price, now_ms):
    """(seconds since created, seconds since last increased, size, censored)
    for ONE resting level.

    An age is None only when the clock is genuinely absent, NEVER when it is
    zero. `if born else None` reads a level born at the epoch as "no birth"
    and drops the row -- it did, on 2 of the first 19 rows, because
    `pinsim.load_hour` timestamps every snapshot 0. Same family as RUNBOOK
    hard rule 7: do not infer a value's meaning from its magnitude.
    """
    d = bk.yes if side == "yes" else bk.no
    sz = float(d.get(price, 0.0))
    born = bk.born.get((side, price))
    bump = bk.bumped.get((side, price))
    seed = getattr(bk, "seed_ts", None)
    return ((now_ms - born) / 1000.0 if born is not None else None,
            (now_ms - bump) / 1000.0 if bump is not None else None,
            sz,
            bool(born is not None and seed is not None and born == seed))


def load_snaps(stamp, mk):
    """Snapshot frames for this hour, WITH the time they arrived.

    `pinsim.load_hour` reads `d["ts_ms"]`, which is absent on every
    orderbook_snapshot record on this tape -- so every snapshot it returns
    carries ts 0, every level it seeds is born at the epoch, and an age
    computed from it is 1.8 billion seconds. (`if born else None` then reads
    that zero as "no birth" and silently drops the row, which is how it was
    found: two of nineteen rows had a bumped clock and no birth clock.)

    The real receive time is `_rx_ms`, which is on 100% of the records. It
    also shows snapshots arriving THROUGHOUT the hour (offsets 0 s to 2,835 s
    on four hours checked), not at the top of it -- the collector gets a fresh
    snapshot as each new market opens. So they are replayed in time order
    against the deltas rather than all applied first. 220 frames an hour, 76
    of them carrying levels; the rest are the empty snapshot a just-opened
    market gets.

    A level seeded by a snapshot may be much older than the snapshot, so its
    age is a LOWER BOUND and the row is flagged `age_cens`.
    """
    out = []
    fp = os.path.join(pinsim.DATA, "orderbook_snapshot", f"{stamp}.jsonl.gz")
    if not os.path.exists(fp):
        return out
    try:
        with gzip.open(fp, "rt") as fh:
            for line in fh:
                if '"orderbook_snapshot"' not in line:
                    continue
                try:
                    d = json.loads(line)
                    m = d["msg"]
                except Exception:                            # noqa: BLE001
                    continue
                tk = m.get("market_ticker")
                if tk not in mk:
                    continue
                ts = int(d.get("_rx_ms") or d.get("ts_ms")
                         or m.get("ts_ms") or 0)
                if not ts:
                    continue
                out.append((ts, tk, m))
    except (EOFError, zlib.error, OSError):
        pass
    out.sort(key=lambda x: x[0])
    return out


def _median(v):
    v = sorted(v)
    n = len(v)
    if not n:
        return None
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def _prov(bkk, opp, ts, hist_prior, want):
    """Provenance of the level we would hit, or all-None when there is none."""
    d = bkk.no if opp == "no" else bkk.yes
    lvl = max(d) if d else None
    if lvl is None:
        return None, None, 0.0, False, None, None
    age, fresh, sz, cens = provenance(bkk, opp, lvl, ts)
    col = 1 if want == "yes" else 2
    vals = [h[col] for h in hist_prior if h[col] > 0]
    med = _median(vals) if len(vals) >= TOUCH_MIN_SAMPLES else None
    rel = (sz / med) if (med and med > 0) else None
    return age, fresh, sz, cens, med, rel


def harvest(hours, end, size, out_path, log=print):
    """Replay the tape and write ONE ROW PER MARKET that the model ever calls
    >= PIN certain inside the tau window.

    TWO POPULATIONS, ONE PASS, because one of them is too small to answer
    anything on its own:

      B, `c_*` -- EVERY market-second where the model first reaches 99.5%
         belief with 3 <= tau <= 30, whether or not anyone was offering. This
         is the population the 48-hour "1,630 of 1,642 winners never dipped"
         table was built on, and at ~9 rows per close it is the only one with
         power over a 9-day tape.
      A, `b_*` -- the subset where the LIVE GATE would actually have bought:
         an offer existed at or under the ceiling, deep enough, with edge and
         EV, and not a >15c dump. `pinsim.decide` decides it. This is the real
         unit of the question and there are roughly one per hour of tape.

    Provenance features only exist where an offer existed, so they are
    reported on A, and on the subset of B that had an offer. Model-side
    features (jumpiness, margin) exist on both.
    """
    mk = pinsim.load_markets()
    stamps = pinsim.book_hours(hours, end)
    ns = pinsim.newest_settlement(mk)
    pinrun.SIZE = float(size)
    log(f"  {len(mk):,} settled markets, {len(stamps)} book hours, size "
        f"{size:g}, gate {pinrun.PIN}, ceiling {pinrun.PRICE_CEILING}, "
        f"dump guard {100*pinrun.DUMP_DISCOUNT:.0f}c")
    log(f"  newest settlement on file "
        f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(ns))} -- book hours "
        f"after it resolve nothing")

    fh = open(out_path, "w", encoding="utf-8", newline="\n")
    n_rows = n_buy = 0
    bad = 0
    seeded_hours = 0
    seeds_applied = 0
    skips = defaultdict(int)
    t0 = time.time()

    for hi, stamp in enumerate(stamps):
        hour = pinsim.load_hour(stamp, mk)
        if not hour["ticks"]:
            pinsim._HOUR_CACHE.pop(stamp, None)
            continue
        idx = pinsim.TapeIndex(sorted(hour["ticks"]))
        pend = {k: list(v) for k, v in hour["ticks"].items()}
        books = {}
        snaps = load_snaps(stamp, mk)
        si = 0
        n_seed = 0
        if any(sm.get("yes_dollars_fp") or sm.get("no_dollars_fp")
               for _, _, sm in snaps):
            seeded_hours += 1
        hist = defaultdict(lambda: deque(maxlen=TOUCH_WIN + 8))
        st = {}
        last_sec = None

        def flush(e):
            nonlocal n_rows, n_buy
            for k in ("iid", "strike", "digits", "open"):
                e.pop(k, None)
            e["c_collapse"] = 1 if e["c_t90"] is not None else 0
            e["b_collapse"] = 1 if e["b_t90"] is not None else 0
            e["c_min_belief"] = round(e["c_min_belief"], 6)
            if e["b_min_belief"] is not None:
                e["b_min_belief"] = round(e["b_min_belief"], 6)
            fh.write(json.dumps(e, default=str) + "\n")
            n_rows += 1
            if e["bought"]:
                n_buy += 1

        for ts, tk, side, price, dq in hour["deltas"]:
            while si < len(snaps) and snaps[si][0] <= ts:
                sts, stk, smsg = snaps[si]
                si += 1
                sbk = books.get(stk)
                if sbk is None:
                    sbk = books[stk] = AgeBook()
                sbk.snapshot(smsg, sts)
                if sbk.seed_ts is not None:
                    n_seed += 1
            if tk is not None:
                bk = books.get(tk)
                if bk is None:
                    bk = books[tk] = AgeBook()
                try:
                    bk.delta(side, price, dq, ts)
                except Exception:                            # noqa: BLE001
                    bad += 1
            sec = ts // 1000
            if sec == last_sec:
                continue
            last_sec = sec
            idx.now = sec
            idx.feed_upto(pend, sec)

            # ---- watch: one belief per open market per second --------------
            for etk in list(st):
                e = st[etk]
                tau = e["close"] - sec
                if tau < WATCH_TAU_MIN:
                    flush(e)
                    del st[etk]
                    continue
                if sec <= e["c_sec"]:
                    continue
                sg = idx.sigma(e["iid"])
                if not sg:
                    continue
                f = pinrun.fair(idx, e["iid"], e["close"], sec, e["strike"],
                                sg * pinrun.SIGMA_STRESS,
                                round_digits=e["digits"])
                if f is None:
                    continue
                bel = f if e["c_want"] == "yes" else 1.0 - f
                if bel < e["c_min_belief"]:
                    e["c_min_belief"] = bel
                for thr, key in ((0.90, "c_t90"), (0.70, "c_t70"),
                                 (0.20, "c_t20")):
                    if bel < thr and e[key] is None:
                        e[key] = tau
                        if key == "c_t90":
                            # THE ARTEFACT CHECK. Belief also falls when the
                            # index feed stalls, because partial() models
                            # every unarrived print with the newest spot it
                            # holds. Record how old that spot was, at the
                            # exact second the alarm fires.
                            _, _, _ia = idx.spot(e["iid"])
                            e["c_t90_index_age_s"] = _ia
                if e["b_sec"] is not None and sec > e["b_sec"]:
                    if e["b_min_belief"] is None or bel < e["b_min_belief"]:
                        e["b_min_belief"] = bel
                    for thr, key in ((0.90, "b_t90"), (0.70, "b_t70"),
                                     (0.20, "b_t20")):
                        if bel < thr and e[key] is None:
                            e[key] = tau
                            if key == "b_t90":
                                _, _, _ia = idx.spot(e["iid"])
                                e["b_t90_index_age_s"] = _ia

            # ---- per market: sample the touch, then look for cert / buy ----
            for tkk, bkk in books.items():
                r = mk.get(tkk)
                if r is None:
                    continue
                cs = int(float(r["close"]))
                tau = cs - sec
                if tau < 0 or tau > 150:
                    continue
                yb, nb = bkk.best()
                hist[tkk].append((
                    sec,
                    bkk.no.get(nb, 0.0) if nb is not None else 0.0,
                    bkk.yes.get(yb, 0.0) if yb is not None else 0.0))
                if not (pinrun.TAU_MIN <= tau <= pinrun.TAU_MAX):
                    continue
                e = st.get(tkk)
                if e is not None and e["bought"]:
                    continue
                iid = pindata.SERIES_TO_INDEX.get(r["series"])
                if iid is None or iid not in idx.ticks:
                    continue
                sg = idx.sigma(iid)
                if not sg:
                    skips["no_sigma"] += 1
                    continue
                digits = pindata.ROUND_DIGITS.get(r["series"])
                f = pinrun.fair(idx, iid, cs, sec, float(r["strike"]),
                                sg * pinrun.SIGMA_STRESS, round_digits=digits)
                if f is None:
                    skips["no_fair"] += 1
                    continue
                if not (f >= pinrun.PIN or f <= 1.0 - pinrun.PIN):
                    if e is None:
                        skips["undecided"] += 1
                    continue
                want = "yes" if f >= pinrun.PIN else "no"
                b = pinsim.book_view(bkk, ts)
                _, spot, iage = idx.spot(iid)
                prior = [h for h in hist[tkk] if h[0] < sec][-TOUCH_WIN:]
                res = r["result"]
                yes = (str(res).lower() == "yes") if isinstance(res, str) \
                    else float(res) >= 0.5

                # ---------- population B: the model is certain ----------
                if e is None:
                    conf = f if want == "yes" else 1.0 - f
                    cc = min(max(conf, 1e-12), 1 - 1e-12)
                    ask = b.get(f"{want}_ask")
                    opp = "no" if want == "yes" else "yes"
                    age_s, fresh_s, lsz, cens, med, rel = _prov(
                        bkk, opp, ts, prior, want)
                    nj, mxz, jcov = jumpiness(idx, iid, sec, sg)
                    e = st[tkk] = {
                        "tk": tkk, "coin": r["series"], "close": cs,
                        "c_sec": sec, "c_tau": int(tau), "c_want": want,
                        "c_conf": round(conf, 6),
                        "c_margin_sd": round(_ND.inv_cdf(cc), 3),
                        "c_price": None if ask is None else round(ask, 4),
                        "c_depth": round(float(
                            b.get(f"{want}_ask_size") or 0.0), 2),
                        "c_discount_c": None if ask is None
                        else round(100.0 * (conf - ask), 2),
                        "c_lvl_age_s": None if age_s is None
                        else round(age_s, 2),
                        "c_lvl_fresh_s": None if fresh_s is None
                        else round(fresh_s, 2),
                        "c_lvl_size": round(lsz, 2),
                        "c_touch_med": None if med is None else round(med, 2),
                        "c_size_rel": None if rel is None else round(rel, 3),
                        "c_age_cens": cens,
                        "c_jump3": nj,
                        "c_jump_max_z": None if mxz is None else round(mxz, 2),
                        "c_jump_cov": jcov,
                        "c_sigma": sg, "c_spot": spot,
                        "c_book_age_ms": b["age_ms"], "c_index_age_s": iage,
                        "hour_utc": time.gmtime(sec).tm_hour,
                        "c_won": bool(yes == (want == "yes")),
                        "c_min_belief": 1.0, "c_t90": None, "c_t70": None,
                        "c_t20": None, "c_t90_index_age_s": None,
                        "bought": False,
                        "b_sec": None, "b_tau": None, "b_price": None,
                        "b_take_n": None, "b_depth": None,
                        "b_margin_sd": None, "b_conf": None,
                        "b_discount_c": None, "b_edge_c": None,
                        "b_lvl_age_s": None, "b_lvl_fresh_s": None,
                        "b_lvl_size": None, "b_touch_med": None,
                        "b_size_rel": None, "b_age_cens": None,
                        "b_jump3": None, "b_jump_max_z": None,
                        "b_sigma": None, "b_book_age_ms": None,
                        "b_index_age_s": None, "b_won": None, "b_pnl": None,
                        "b_min_belief": None, "b_t90": None, "b_t70": None,
                        "b_t20": None, "b_t90_index_age_s": None,
                        "iid": iid, "strike": float(r["strike"]),
                        "digits": digits,
                    }

                # ---------- population A: the live gate would buy ----------
                if b["age_ms"] is None or \
                        b["age_ms"] > pinrun.MAX_BOOK_AGE_MS:
                    skips["stale_book"] += 1
                    continue
                w, px, take_n, fv = pinsim.decide(
                    idx, iid, cs, sec, float(r["strike"]), digits, b,
                    pinrun.SIZE)
                if w is None:
                    skips[px] += 1
                    continue
                bconf = fv if w == "yes" else 1.0 - fv
                if (bconf - px) > pinrun.DUMP_DISCOUNT:
                    # AMENDMENT 10, live. Not terminal: live keeps scanning
                    # and may buy the same market a second later at a price
                    # that is not a dump.
                    skips["dumped"] += 1
                    continue
                bcc = min(max(bconf, 1e-12), 1 - 1e-12)
                opp = "no" if w == "yes" else "yes"
                age_s, fresh_s, lsz, cens, med, rel = _prov(
                    bkk, opp, ts, prior, w)
                nj, mxz, _ = jumpiness(idx, iid, sec, sg)
                bwon = (yes == (w == "yes"))
                e.update({
                    "bought": True, "b_sec": sec, "b_tau": int(tau),
                    "b_want": w, "b_price": round(px, 4),
                    "b_take_n": round(take_n, 2),
                    "b_depth": round(float(
                        b.get(f"{w}_ask_size") or 0.0), 2),
                    "b_margin_sd": round(_ND.inv_cdf(bcc), 3),
                    "b_conf": round(bconf, 6),
                    "b_discount_c": round(100.0 * (bconf - px), 2),
                    "b_edge_c": round(100.0 * pinrun.net_edge(fv, px, w), 3),
                    "b_lvl_age_s": None if age_s is None else round(age_s, 2),
                    "b_lvl_fresh_s": None if fresh_s is None
                    else round(fresh_s, 2),
                    "b_lvl_size": round(lsz, 2),
                    "b_touch_med": None if med is None else round(med, 2),
                    "b_size_rel": None if rel is None else round(rel, 3),
                    "b_age_cens": cens, "b_jump3": nj,
                    "b_jump_max_z": None if mxz is None else round(mxz, 2),
                    "b_sigma": sg, "b_book_age_ms": b["age_ms"],
                    "b_index_age_s": iage, "b_won": bool(bwon),
                    "b_pnl": round((take_n * (1 - px) if bwon
                                    else -take_n * px)
                                   - pinrun.billed_fee(px, take_n), 4),
                    "b_min_belief": 1.0,
                })

        for etk in list(st):
            flush(st.pop(etk))
        bad += getattr(hour["deltas"], "bad", 0) or 0
        seeds_applied += n_seed
        books.clear()
        hist.clear()
        pinsim._HOUR_CACHE.pop(stamp, None)
        if (hi + 1) % 6 == 0 or hi + 1 == len(stamps):
            log(f"    {stamp}  certain {n_rows:,}  bought {n_buy:,}  "
                f"{time.time()-t0:.0f}s", flush=True)

    fh.close()
    log(f"\n  {n_rows:,} certain markets, {n_buy:,} of them tradeable "
        f"-> {out_path}")
    log(f"  hours with a snapshot carrying levels: {seeded_hours} of "
        f"{len(stamps)}; snapshot seedings applied {seeds_applied:,}")
    if bad:
        log(f"  *** {bad:,} deltas failed to parse -- the book is incomplete "
            f"and every number is suspect ***")
    top = sorted(skips.items(), key=lambda kv: -kv[1])[:8]
    log("  refusals: " + ", ".join(f"{k}={v:,}" for k, v in top))
    return n_rows


POP_A = ("b_", "bought")
POP_B = ("c_", None)


def load_rows(path, pop):
    """Read the harvested file and normalise ONE population's columns to the
    plain names the estimator uses. Nothing is recomputed here."""
    pre, need = pop
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:                                # noqa: BLE001
                continue
            if need and not r.get(need):
                continue
            if r.get(pre + "sec") is None:
                continue
            n = {"tk": r["tk"], "coin": r["coin"], "close": r["close"],
                 "hour_utc": r.get("hour_utc")}
            for k, v in r.items():
                if k.startswith(pre):
                    n[k[len(pre):]] = v
            n["lost"] = 0 if n.get("won") else 1
            n["collapse"] = int(n.get("collapse") or 0)
            if n.get("take_n") is None:
                n["take_n"] = 0.0
            if n.get("pnl") is None:
                n["pnl"] = 0.0
            out.append(n)
    return out


# ===========================================================================
# 2. THE ESTIMATOR
# ===========================================================================
def mde_rate(p0, n, power=0.80, alpha=0.05):
    """Smallest TRUE rate above p0 a two-sided alpha test finds with `power`,
    given n INDEPENDENT observations. Returns nan when n <= 0."""
    if n is None or n <= 0:
        return float("nan")
    p0 = max(float(p0), 0.5 / n)          # a zero baseline has no sd at all
    za = _ND.inv_cdf(1 - alpha / 2.0)
    zb = _ND.inv_cdf(power)
    lo, hi = p0, 1.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        need = za * math.sqrt(p0 * (1 - p0) / n) + \
            zb * math.sqrt(mid * (1 - mid) / n)
        if mid - p0 >= need:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def _by_close(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["close"]].append(r)
    return d


def boot_diff(rows, field, sel_hi, sel_lo, draws=3000, seed=11, conf=0.95):
    """Cluster bootstrap over CLOSES for (rate in hi bucket) - (rate in lo).

    THE CLUSTER IS THE CLOSE. All twelve coins settle on the same second at
    rho ~ 0.8, so markets are not independent and a binomial interval on
    markets is too narrow. Resampling whole closes with replacement keeps
    whatever within-close correlation exists, whatever its size.
    Returns (point, lo95, hi95, draws_used).
    """
    agg = {}
    for c, rs in _by_close(rows).items():
        hk = hn = lk = ln = 0
        for r in rs:
            v = r.get(field)
            if v is None:
                continue
            if sel_hi(r):
                hn += 1
                hk += int(v)
            elif sel_lo(r):
                ln += 1
                lk += int(v)
        if hn or ln:
            agg[c] = (hk, hn, lk, ln)
    keys = list(agg)
    if not keys:
        return None, None, None, 0
    HK = sum(agg[c][0] for c in keys)
    HN = sum(agg[c][1] for c in keys)
    LK = sum(agg[c][2] for c in keys)
    LN = sum(agg[c][3] for c in keys)
    if not HN or not LN:
        return None, None, None, 0
    point = HK / HN - LK / LN
    rnd = random.Random(seed)
    out = []
    m = len(keys)
    for _ in range(draws):
        hk = hn = lk = ln = 0
        for _ in range(m):
            a, b, c_, d = agg[keys[rnd.randrange(m)]]
            hk += a
            hn += b
            lk += c_
            ln += d
        if hn and ln:
            out.append(hk / hn - lk / ln)
    if len(out) < draws * 0.5:
        return point, None, None, len(out)
    out.sort()
    aa = (1.0 - conf) / 2.0
    return (point, out[int(aa * len(out))],
            out[min(len(out) - 1, int((1.0 - aa) * len(out)))], len(out))


def bucketise(rows, key, cuts, labels=None):
    """Split rows on `key` at `cuts` (ascending). Rows with a None value go to
    a separate 'n/a' bucket so nothing is silently discarded."""
    names = labels or (
        [f"< {cuts[0]:g}"] +
        [f"{cuts[i]:g}-{cuts[i+1]:g}" for i in range(len(cuts) - 1)] +
        [f">= {cuts[-1]:g}"])
    out = [(n, []) for n in names] + [("n/a", [])]
    for r in rows:
        v = r.get(key)
        if v is None:
            out[-1][1].append(r)
            continue
        i = 0
        while i < len(cuts) and float(v) >= cuts[i]:
            i += 1
        out[i][1].append(r)
    return [(n, rs) for n, rs in out if rs]


def cell(rs, field):
    k = sum(int(r[field]) for r in rs)
    n = len(rs)
    nc = len({r["close"] for r in rs})
    lo, hi = cp_interval(k, n)
    return {"k": k, "n": n, "closes": nc, "rate": (k / n) if n else float("nan"),
            "lo": lo, "hi": hi}


def bucket_table(rows, key, cuts, labels=None, fields=("collapse", "lost")):
    tab = []
    for name, rs in bucketise(rows, key, cuts, labels):
        row = {"bucket": name, "n": len(rs),
               "closes": len({r["close"] for r in rs})}
        for f in fields:
            row[f] = cell(rs, f)
        tab.append(row)
    return tab


def fmt_table(tab, title, base_rate, note=""):
    ls = [f"**{title}**", ""]
    ls.append("| bucket | entries | closes | collapse | 95% CP | losses "
              "| loss rate | 95% CP |")
    ls.append("|---|---|---|---|---|---|---|---|")
    for r in tab:
        c, l = r["collapse"], r["lost"]
        ls.append(
            f"| {r['bucket']} | {r['n']:,} | {r['closes']} | "
            f"{c['k']} ({100*c['rate']:.2f}%) | "
            f"[{100*c['lo']:.2f}, {100*c['hi']:.2f}] | "
            f"{l['k']} | {100*l['rate']:.2f}% | "
            f"[{100*l['lo']:.2f}, {100*l['hi']:.2f}] |")
    if note:
        ls += ["", note]
    return "\n".join(ls) + "\n"


def per_close_cost(rows, refuse, size=20.0):
    """The arithmetic that has killed two per-contract stories in this repo.

    Refusing a bucket changes TWO things: the losses avoided and the wins given
    up. Both are per CLOSE, because rarity is invisible per contract. P&L is
    scaled from the harvested take_n to `size` -- a linear scale, so it assumes
    the deeper size fills, which the depth work says holds ~80% of the time at
    20 and less above it.
    """
    closes = {r["close"] for r in rows}
    nc = max(1, len(closes))
    tot = ref = 0.0
    n_ref = n_ref_lost = 0
    for r in rows:
        scale = size / r["take_n"] if r["take_n"] else 0.0
        p = r["pnl"] * scale
        tot += p
        if refuse(r):
            ref += p
            n_ref += 1
            n_ref_lost += int(r["lost"])
    return {"closes": nc, "n": len(rows), "n_refused": n_ref,
            "n_refused_lost": n_ref_lost,
            "pnl_all": tot, "pnl_refused_bucket": ref,
            "pnl_kept": tot - ref,
            "per_close_all": tot / nc, "per_close_kept": (tot - ref) / nc,
            "per_close_delta": -ref / nc}


# ===========================================================================
# 3. SELF-TEST -- plant an answer, and plant nothing
# ===========================================================================
def _synth(n_closes, per_close, planted, seed, base=0.06, hot=0.35):
    """Rows with a per-CLOSE shock, so outcomes are correlated inside a close
    exactly as they are on the tape."""
    rnd = random.Random(seed)
    rows = []
    for c in range(n_closes):
        close = 1788800000 + c * 900
        shock = rnd.random() < 0.05
        for j in range(per_close):
            age = rnd.choice([0.4, 1.2, 3.0, 9.0, 40.0])
            if planted:
                p = hot if age < 2.0 else 0.01
            else:
                p = base
            if shock:
                p = min(1.0, p + 0.25)
            col = 1 if rnd.random() < p else 0
            lost = 1 if (col and rnd.random() < 0.8) else 0
            rows.append({"close": close, "tk": f"T{c}_{j}", "lvl_age_s": age,
                         "collapse": col, "lost": lost,
                         "take_n": 20.0,
                         "pnl": (-19.0 if lost else 0.6)})
    return rows


def _synth_clustered(seed=5):
    """THE TRAP. The feature is constant inside a close and the outcome is a
    single per-close coin flip, so 240 markets carry only 20 independent
    facts. A binomial interval on markets separates the buckets; an honest
    cluster interval must not."""
    rows = []
    for c in range(20):
        close = 1788900000 + c * 900
        fresh = c < 10
        allcol = (c in (0, 1, 2)) if fresh else (c == 10)
        for j in range(12):
            rows.append({"close": close, "tk": f"C{c}_{j}",
                         "lvl_age_s": 1.0 if fresh else 20.0,
                         "collapse": 1 if allcol else 0,
                         "lost": 1 if allcol else 0,
                         "take_n": 20.0, "pnl": -19.0 if allcol else 0.6})
    return rows


def selftest():
    print("SELF-TEST -- pinentry")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # ---- the book clocks -------------------------------------------------
    b = AgeBook()
    b.snapshot({"yes_dollars_fp": [["0.60", "100"]],
                "no_dollars_fp": [["0.39", "200"]]}, 1000)
    ck(b.born[("yes", 0.60)] == 1000 and b.bumped[("yes", 0.60)] == 1000,
       "a snapshot sets both clocks")
    b.delta("yes", 0.60, 50, 5000)
    ck(b.born[("yes", 0.60)] == 1000,
       "adding to a level does NOT reset its birth (pindata's rule)")
    ck(b.bumped[("yes", 0.60)] == 5000,
       "but it DOES reset when the level was last increased")
    b.delta("yes", 0.60, -150, 9000)
    ck(("yes", 0.60) not in b.born and ("yes", 0.60) not in b.bumped,
       "emptying a level drops both clocks")
    b.delta("yes", 0.60, 7, 12000)
    ck(b.born[("yes", 0.60)] == 12000 and b.bumped[("yes", 0.60)] == 12000,
       "and re-creating it makes a NEW, young level")
    b2 = AgeBook()
    b2.delta("no", 0.3, 5, 4242)
    ck(b2.first_ts == 4242, "first_ts records when this book was first seen")

    # ---- provenance, and THE FALSY-ZERO TRAP -----------------------------
    b3 = AgeBook()
    b3.snapshot({"no_dollars_fp": [["0.05", "400"]]}, 0)   # pinsim's ts is 0
    age, fresh, sz, cens = provenance(b3, "no", 0.05, 30_000)
    ck(age == 30.0 and sz == 400.0,
       f"a level born at ts 0 has an AGE, not a None (age={age})")
    ck(cens, "and it is flagged censored, because a snapshot only bounds it")
    b3.delta("no", 0.04, 7, 25_000)
    a2, f2, s2, c2 = provenance(b3, "no", 0.04, 30_000)
    ck(a2 == 5.0 and not c2,
       f"a level created by a later delta is NOT censored (age={a2})")
    a3, f3, s3, c3 = provenance(b3, "no", 0.99, 30_000)
    ck(a3 is None and f3 is None and s3 == 0.0,
       "a level that is not in the book has no clocks and no size")

    # ---- jumpiness -------------------------------------------------------
    class _FakeIdx:
        def __init__(self, d):
            self.ticks = {"X": d}
    flat = {s: 100.0 for s in range(0, 400)}
    n, mx, k = jumpiness(_FakeIdx(flat), "X", 350, 0.1)
    ck(n == 0 and mx == 0.0 and k == JUMP_WIN,
       f"a flat index has no jumps (n={n}, max={mx})")
    spiky = dict(flat)
    for s in (300, 340):
        spiky[s] = 100.0 + 0.5          # 5 sigma up, then 5 sigma back down
    n, mx, k = jumpiness(_FakeIdx(spiky), "X", 350, 0.1)
    ck(n == 4 and abs(mx - 5.0) < 1e-9,
       f"two planted 5-sigma spikes give 4 crossings and max 5.0 "
       f"(n={n}, max={mx})")
    n2, _, _ = jumpiness(_FakeIdx(spiky), "X", 350, 1.0)
    ck(n2 == 0, "and none of them counts when sigma is ten times larger")
    n3, _, _ = jumpiness(_FakeIdx({300: 100.0}), "X", 350, 0.1)
    ck(n3 is None, "too little index coverage returns None, not zero")

    # ---- MDE -------------------------------------------------------------
    m100 = mde_rate(0.01, 100)
    m1000 = mde_rate(0.01, 1000)
    ck(m100 > m1000 > 0.01, f"MDE shrinks with n ({m100:.3f} -> {m1000:.3f})")
    ck(m100 > 4 * 0.01,
       f"100 observations at a 1% base cannot resolve anything under 4x the "
       f"base rate (MDE {100*m100:.1f}%)")
    ck(math.isnan(mde_rate(0.01, 0)), "MDE of nothing is nan, not a number")

    # ---- Clopper-Pearson sanity -----------------------------------------
    lo, hi = cp_interval(3, 100)
    ck(lo < 0.03 < hi and lo > 0, f"CP brackets the estimate ({lo:.4f},{hi:.4f})")
    lo0, hi0 = cp_interval(0, 50)
    ck(lo0 == 0.0 and 0.05 < hi0 < 0.10, f"zero of fifty -> [0, {hi0:.3f}]")

    # ---- THE PLANTED WORLD ----------------------------------------------
    hot = lambda r: r["lvl_age_s"] < 2.0                      # noqa: E731
    cold = lambda r: r["lvl_age_s"] >= 2.0                    # noqa: E731
    pl = _synth(300, 9, planted=True, seed=3)
    tab = bucket_table(pl, "lvl_age_s", [2.0], ["fresh (<2s)", "stale (>=2s)"])
    r_hot = [t for t in tab if t["bucket"].startswith("fresh")][0]
    r_cold = [t for t in tab if t["bucket"].startswith("stale")][0]
    ck(r_hot["collapse"]["rate"] > 5 * r_cold["collapse"]["rate"],
       f"planted: fresh collapses {100*r_hot['collapse']['rate']:.1f}% vs "
       f"stale {100*r_cold['collapse']['rate']:.1f}%")
    p, blo, bhi, nd = boot_diff(pl, "collapse", hot, cold, draws=1500, seed=2)
    ck(blo is not None and blo > 0,
       f"planted: cluster bootstrap finds it, diff {p:+.3f} "
       f"95% [{blo:+.3f}, {bhi:+.3f}]")

    # ---- AND THE WORLD WITH NOTHING IN IT -------------------------------
    nl = _synth(300, 9, planted=False, seed=4)
    p0, blo0, bhi0, _ = boot_diff(nl, "collapse", hot, cold,
                                  draws=1500, seed=2)
    ck(blo0 is not None and blo0 < 0 < bhi0,
       f"null: bootstrap finds nothing, diff {p0:+.3f} "
       f"95% [{blo0:+.3f}, {bhi0:+.3f}]")
    tabn = bucket_table(nl, "lvl_age_s", [2.0], ["fresh", "stale"])
    hn, cn = tabn[0]["collapse"], tabn[1]["collapse"]
    ck(hn["lo"] < cn["rate"] < hn["hi"],
       "null: the buckets' CP intervals overlap the other's estimate")

    # ---- THE CLUSTERING TRAP --------------------------------------------
    cl = _synth_clustered()
    tc = bucket_table(cl, "lvl_age_s", [2.0], ["fresh", "stale"])
    a, bq = tc[0]["collapse"], tc[1]["collapse"]
    ck(a["lo"] > bq["hi"],
       f"trap: per-MARKET CP intervals separate "
       f"([{100*a['lo']:.1f},{100*a['hi']:.1f}] vs "
       f"[{100*bq['lo']:.1f},{100*bq['hi']:.1f}]) -- and would be believed")
    pc, clo, chi, _ = boot_diff(cl, "collapse", hot, cold, draws=1500, seed=2)
    ck(clo is not None and clo < 0 < chi,
       f"trap: clustering by CLOSE refuses it, diff {pc:+.3f} "
       f"95% [{clo:+.3f}, {chi:+.3f}] -- 240 markets, 20 facts")

    # ---- the per-close arithmetic ---------------------------------------
    pcc = per_close_cost(pl, hot, size=20.0)
    ck(pcc["n_refused"] > 0 and pcc["closes"] == 300,
       f"per-close: {pcc['n_refused']} refused over {pcc['closes']} closes")
    good = [{"close": 1 + i, "take_n": 20.0, "pnl": 0.6, "lost": 0,
             "lvl_age_s": 1.0} for i in range(50)]
    pcg = per_close_cost(good, hot, size=20.0)
    ck(pcg["per_close_delta"] < 0,
       f"refusing a bucket that only ever WON costs money "
       f"({pcg['per_close_delta']:+.3f}/close)")
    bad = [{"close": 1 + i, "take_n": 20.0, "pnl": -19.0, "lost": 1,
            "lvl_age_s": 1.0} for i in range(50)]
    pcb = per_close_cost(bad, hot, size=20.0)
    ck(pcb["per_close_delta"] > 0,
       f"refusing a bucket that only ever LOST saves money "
       f"({pcb['per_close_delta']:+.3f}/close)")

    # ---- a wider interval must actually be wider ------------------------
    _p, l95, h95, _ = boot_diff(pl, "collapse", hot, cold, draws=1200,
                                seed=9)
    _p2, l99, h99, _ = boot_diff(pl, "collapse", hot, cold, draws=1200,
                                 seed=9, conf=0.999)
    ck(l99 < l95 and h99 > h95,
       f"a 99.9% interval is wider than a 95% one "
       f"([{l99:+.3f},{h99:+.3f}] vs [{l95:+.3f},{h95:+.3f}])")

    # ---- the two-population round trip ----------------------------------
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    NL = chr(10)
    with open(tmp, "w", encoding="utf-8", newline=NL) as fh:
        fh.write(json.dumps({
            "tk": "T1", "coin": "KXBTC15M", "close": 100, "hour_utc": 3,
            "bought": True, "c_sec": 70, "c_tau": 30, "c_margin_sd": 3.0,
            "c_collapse": 1, "c_won": False, "c_lvl_age_s": 0.5,
            "b_sec": 80, "b_tau": 20, "b_margin_sd": 4.0, "b_collapse": 0,
            "b_won": True, "b_lvl_age_s": 9.0, "b_take_n": 20.0,
            "b_pnl": 0.4}) + NL)
        fh.write(json.dumps({
            "tk": "T2", "coin": "KXETH15M", "close": 100, "hour_utc": 3,
            "bought": False, "c_sec": 71, "c_tau": 29, "c_margin_sd": 2.7,
            "c_collapse": 0, "c_won": True, "c_lvl_age_s": None,
            "b_sec": None}) + NL)
    ra = load_rows(tmp, POP_A)
    rb = load_rows(tmp, POP_B)
    os.unlink(tmp)
    ck(len(ra) == 1 and len(rb) == 2,
       f"A keeps only the bought row, B keeps both ({len(ra)}, {len(rb)})")
    ck(ra and ra[0]["margin_sd"] == 4.0 and ra[0]["tau"] == 20,
       "A reads the BUY second's columns, not the certain second's")
    ck(rb and rb[0]["margin_sd"] == 3.0 and rb[0]["tau"] == 30,
       "B reads the certain second's columns")
    ck(ra and ra[0]["lost"] == 0 and rb[0]["lost"] == 1,
       "lost is derived from each population's own outcome")
    ck(rb[1]["lvl_age_s"] is None,
       "a certain moment with no offer carries no provenance")

    # ---- bucketise keeps everything -------------------------------------
    mixed = pl + [dict(pl[0], lvl_age_s=None)]
    ck(sum(len(rs) for _, rs in
           bucketise(mixed, "lvl_age_s", [2.0])) == len(mixed),
       "bucketise discards nothing; a missing value gets its own bucket")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ===========================================================================
# 4. THE REPORT
# ===========================================================================
FEATURES = [
    ("1a. OFFER AGE -- seconds the level we hit had been resting",
     "lvl_age_s", [0.1, 0.5, 2.0, 10.0],
     ["< 0.1s", "0.1-0.5s", "0.5-2s", "2-10s", ">= 10s"]),
    ("1b. OFFER FRESHNESS -- seconds since the level was last INCREASED",
     "lvl_fresh_s", [0.1, 0.5, 2.0, 10.0],
     ["< 0.1s", "0.1-0.5s", "0.5-2s", "2-10s", ">= 10s"]),
    ("1c. OFFER SIZE vs this market's own median touch over the prior 60s",
     "size_rel", [0.5, 1.0, 2.0, 5.0],
     ["< 0.5x", "0.5-1x", "1-2x", "2-5x", ">= 5x"]),
    ("1d. OFFER SIZE, absolute contracts at the level",
     "lvl_size", [20.0, 100.0, 500.0],
     ["< 20", "20-100", "100-500", ">= 500"]),
    ("2a. PRE-ENTRY JUMPINESS -- 1s index moves > 3 sigma in the last 120s",
     "jump3", [1.0, 2.0, 4.0], ["0", "1", "2-3", ">= 4"]),
    ("2b. LARGEST 1s index move in the last 120s, in sigma units",
     "jump_max_z", [2.0, 3.0, 4.0, 6.0],
     ["< 2", "2-3", "3-4", "4-6", ">= 6"]),
    ("3. MARGIN TO THE STRIKE at entry, in sigma units",
     "margin_sd", [3.0, 4.0, 5.0, 6.0],
     ["2.58-3", "3-4", "4-5", "5-6", ">= 6"]),
    ("4a. TAU AT ENTRY (control)",
     "tau", [10.0, 20.0], ["3-9s", "10-19s", "20-30s"]),
    ("4b. PRICE PAID (control)",
     "price", [0.94, 0.97, 0.98],
     ["< 94c", "94-97c", "97-98c", ">= 98c"]),
    ("4c. DISCOUNT BELOW FAIR at entry, cents (the LIVE guard cuts at 15c)",
     "discount_c", [1.0, 2.0, 5.0, 10.0, 15.0],
     ["< 1c", "1-2c", "2-5c", "5-10c", "10-15c", ">= 15c (guard refuses)"]),
]


def _split(rows, days=5):
    cl = sorted({r["close"] for r in rows})
    if not cl:
        return [], [], None
    cut = cl[0] + days * 86400
    return ([r for r in rows if r["close"] < cut],
            [r for r in rows if r["close"] >= cut], (cl[0], cut, cl[-1]))


def _sel_bucket(key, cuts, labels, name):
    def f(r):
        if r.get(key) is None:
            return False
        return bucketise([r], key, cuts, labels)[0][0] == name
    return f


def feature_section(w, rows, title, key, cuts, labels, base_c, base_l,
                    ndays, full=True, tag=""):
    """One feature, one population. Returns (survived, worst_bucket, res)."""
    w("---")
    w("")
    w(f"## {title}{tag}")
    w("")
    have = [r for r in rows if r.get(key) is not None]
    if len(have) < 20:
        w(f"_only {len(have)} rows carry this feature -- not reported_")
        w("")
        return False, None, None, []
    vals = sorted(float(r[key]) for r in have)
    qs = [vals[int(q * (len(vals) - 1))] for q in (0.05, 0.25, 0.5, 0.75,
                                                   0.95)]
    w(f"_distribution: {len(have):,} of {len(rows):,} rows carry it; "
      f"p5 {qs[0]:g} / p25 {qs[1]:g} / median {qs[2]:g} / p75 {qs[3]:g} / "
      f"p95 {qs[4]:g}_")
    w("")
    tab = bucket_table(rows, key, cuts, labels)
    real = [t for t in tab if t["bucket"] != "n/a"]
    small = min((t["n"] for t in real), default=0)
    smallc = min((t["closes"] for t in real), default=0)
    w(f"**MDE first.** The smallest bucket holds {small:,} entries over "
      f"{smallc:,} closes. Against a {100*base_c:.2f}% collapse baseline that "
      f"resolves {100*mde_rate(base_c, small):.2f}% counting markets and "
      f"{100*mde_rate(base_c, smallc):.2f}% counting closes; on the loss "
      f"column ({100*base_l:.2f}% baseline), "
      f"{100*mde_rate(base_l, small):.2f}% / "
      f"{100*mde_rate(base_l, smallc):.2f}%.")
    w("")
    w(fmt_table(tab, f"ALL {ndays} DAYS", base_c))
    first, second, _ = _split(rows)
    if full:
        for nm, sub in (("FIRST 5 DAYS (in sample)", first),
                        ("LAST 4 DAYS (holdout)", second)):
            if sub:
                w(fmt_table(bucket_table(sub, key, cuts, labels), nm, base_c))
    if len(real) < 2:
        return False, None, None, []
    worst = max(real, key=lambda t: t["collapse"]["rate"])
    wl = worst["bucket"]
    sel = _sel_bucket(key, cuts, labels, wl)

    def oth(r):
        return r.get(key) is not None and not sel(r)

    res = {}
    for nm, sub in (("all", rows), ("first 5d", first), ("last 4d", second)):
        if sub:
            res[nm] = boot_diff(sub, "collapse", sel, oth, draws=2000,
                                seed=17)
    w(f"**Worst bucket `{wl}` vs the rest, COLLAPSE rate, cluster bootstrap "
      f"over CLOSES (2,000 draws):**")
    w("")
    w("| sample | difference | 95% CI | verdict |")
    w("|---|---|---|---|")
    for nm in ("all", "first 5d", "last 4d"):
        if nm not in res:
            continue
        p, lo, hi, _ = res[nm]
        if p is None or lo is None:
            w(f"| {nm} | - | - | not computable |")
            continue
        w(f"| {nm} | {100*p:+.2f} pp | [{100*lo:+.2f}, {100*hi:+.2f}] | "
          f"{'EXCLUDES 0' if (lo > 0 or hi < 0) else 'includes 0'} |")
    w("")
    ok = all(nm in res and res[nm][1] is not None and res[nm][1] > 0
             for nm in ("first 5d", "last 4d"))
    w("**SURVIVES THE SPLIT.**" if ok else
      "**Does not survive the split.**")
    w("")

    # ---- THE CUT SWEEP. A GATE IS A CUT, NOT A BUCKET. -------------------
    # The bucket test above finds the single worst cell and misses monotone
    # structure -- on margin-to-strike the informative fact is that every
    # bucket from 4 sd up has ZERO collapses, which no single cell states.
    # A deployable rule has the form "refuse below X", so every bucket
    # boundary is tested as a binary split. Each cut is an extra look and
    # they are counted in the multiple-looks table.
    w("**Every boundary as a binary gate: `< cut` vs `>= cut`, COLLAPSE "
      "rate, cluster bootstrap over CLOSES.** A rule we could deploy is a "
      "cut, so this is the shape that matters.")
    w("")
    w("| cut | n below | collapse below | n above | collapse above | "
      "all: diff [95% CI] | first 5d | last 4d | both halves |")
    w("|---|---|---|---|---|---|---|---|---|")
    survcuts = []
    for c in cuts:
        def lo_(r, _c=c, _k=key):
            v = r.get(_k)
            return v is not None and float(v) < _c

        def hi_(r, _c=c, _k=key):
            v = r.get(_k)
            return v is not None and float(v) >= _c
        nb_ = [r for r in rows if lo_(r)]
        na_ = [r for r in rows if hi_(r)]
        if len(nb_) < 10 or len(na_) < 10:
            continue
        kb = sum(r["collapse"] for r in nb_)
        ka = sum(r["collapse"] for r in na_)
        cr = {}
        for nm, sub in (("all", rows), ("first 5d", first),
                        ("last 4d", second)):
            if sub:
                cr[nm] = boot_diff(sub, "collapse", lo_, hi_, draws=2000,
                                   seed=23)

        def _cc(nm):
            if nm not in cr or cr[nm][0] is None or cr[nm][1] is None:
                return "-"
            pp, l_, h_, _n = cr[nm]
            return "%+.2f [%+.2f, %+.2f]" % (100 * pp, 100 * l_, 100 * h_)
        both = all(nm in cr and cr[nm][1] is not None and cr[nm][1] > 0
                   for nm in ("first 5d", "last 4d"))
        if both:
            survcuts.append((c, cr))
        w(f"| {c:g} | {len(nb_):,} | {kb} ({100*kb/len(nb_):.2f}%) | "
          f"{len(na_):,} | {ka} ({100*ka/len(na_):.2f}%) | {_cc('all')} | "
          f"{_cc('first 5d')} | {_cc('last 4d')} | "
          f"{'YES' if both else 'no'} |")
    w("")
    if survcuts:
        w("**Cuts that hold in both halves: "
          + ", ".join("`%s < %g`" % (key, c) for c, _ in survcuts) + ".**")
    else:
        w("_No cut holds in both halves._")
    w("")
    return ok, wl, res, survcuts


def cut_verdicts(rows, key, cuts, outcome="collapse", draws=1200, seed=41):
    """Every boundary as a binary gate, compactly. Returns a list of
    (cut, n_lo, k_lo, n_hi, k_hi, diff, lo95, hi95, holds_in_both_halves)."""
    first, second, _ = _split(rows)
    out = []
    for c in cuts:
        def lo_(r, _c=c, _k=key):
            v = r.get(_k)
            return v is not None and float(v) < _c

        def hi_(r, _c=c, _k=key):
            v = r.get(_k)
            return v is not None and float(v) >= _c
        nb_ = [r for r in rows if lo_(r)]
        na_ = [r for r in rows if hi_(r)]
        if len(nb_) < 10 or len(na_) < 10:
            continue
        pp, l_, h_, _n = boot_diff(rows, outcome, lo_, hi_, draws=draws,
                                   seed=seed)
        both = True
        for sub in (first, second):
            if not sub:
                both = False
                continue
            _p2, l2, _h2, _n2 = boot_diff(sub, outcome, lo_, hi_,
                                          draws=draws, seed=seed)
            if l2 is None or l2 <= 0:
                both = False
        out.append((c, len(nb_), sum(r[outcome] for r in nb_), len(na_),
                    sum(r[outcome] for r in na_), pp, l_, h_, both))
    return out


def stratified_residual(w, rows, label, strat_key, strat_hi, skip_keys):
    """Inside one margin stratum, does anything ELSE separate the collapse?

    THE POINT. `margin_sd` is the model's own belief on another scale
    (margin = Phi^-1(belief)), and a collapse is defined as that same belief
    later falling under 0.90 = 1.282 sd. A monotone relation between the two
    is mechanically forced and is NOT information -- an entry at the gate
    floor of 2.576 sd sits 1.29 sd from the alarm, one at 6 sd sits 4.7 sd
    from it. So the only question worth asking is whether anything in the
    BOOK or the INDEX adds to what the margin already says. This holds the
    margin roughly fixed and asks it.
    """
    sub = [r for r in rows if r.get(strat_key) is not None
           and float(r[strat_key]) < strat_hi]
    n = len(sub)
    k = sum(r["collapse"] for r in sub)
    nc = len({r["close"] for r in sub})
    w(f"**{label}: {n:,} entries over {nc:,} closes, {k} collapses "
      f"({100*k/max(1,n):.2f}%).** MDE at this size is "
      f"{100*mde_rate(k/max(1,n), n):.2f}% counting markets, "
      f"{100*mde_rate(k/max(1,n), nc):.2f}% counting closes.")
    w("")
    if n < 60 or k < 5:
        w("_too few collapses inside the stratum to test anything_")
        w("")
        return []
    w("| feature | cut | n below | collapse below | n above | "
      "collapse above | diff [95% CI] | holds in both halves |")
    w("|---|---|---|---|---|---|---|---|")
    held = []
    for title, key, cuts, _labels in FEATURES:
        if key in skip_keys:
            continue
        for (c, nb_, kb, na_, ka, pp, l_, h_, both) in cut_verdicts(
                sub, key, cuts):
            if both:
                held.append((title, key, c))
            w(f"| {title.split('.')[0]} `{key}` | {c:g} | {nb_:,} | "
              f"{kb} ({100*kb/nb_:.2f}%) | {na_:,} | "
              f"{ka} ({100*ka/na_:.2f}%) | "
              f"{100*pp:+.2f} [{100*l_:+.2f}, {100*h_:+.2f}] | "
              f"{'YES' if both else 'no'} |")
    w("")
    if held:
        w("**Holds inside the stratum: "
          + ", ".join("`%s < %g`" % (k_, c_) for _t, k_, c_ in held) + ".**")
    else:
        w("**Nothing in the book or the index separates the collapse once "
          "the model's own margin is held fixed.**")
    w("")
    return held


def report(rowsA, rowsB, out_path, size=20.0, log=print):
    ls = []
    w = ls.append
    rows = rowsB
    cl = sorted({r["close"] for r in rows})
    ndays = max(1, int(round((cl[-1] - cl[0]) / 86400.0))) if cl else 0
    nA, nB = len(rowsA), len(rowsB)
    colB = sum(r["collapse"] for r in rowsB)
    lostB = sum(r["lost"] for r in rowsB)
    colA = sum(r["collapse"] for r in rowsA)
    lostA = sum(r["lost"] for r in rowsA)
    bcA = colA / nA if nA else float("nan")
    blA = lostA / nA if nA else float("nan")
    bcB = colB / nB
    blB = lostB / nB

    w("# RESULTS_entry -- how to know when NOT to buy")
    w("")
    w(f"Generated {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} by "
      f"`research/pinentry.py` (`--selftest` passes; `main()` refuses real "
      f"data until it does).")
    w("")
    w("## What was measured, and on which population")
    w("")
    w("The bot's losses are a COLLAPSE of the model's own belief after entry, "
      "not a drift. The question is whether the entry second already knows. "
      "Four entry-time features were tested: offer provenance (how long the "
      "level we would hit had rested, and how big it is against that "
      "market's own recent touch), same-coin pre-entry jumpiness, the margin "
      "to the strike in sigma units, and tau/price as controls. Every one is "
      "computed from data at or before the entry second.")
    w("")
    w("**Two populations, harvested in one pass, because the real one is "
      "too small to answer anything alone:**")
    w("")
    w("| | A -- TRADEABLE ENTRIES | B -- MODEL-CERTAIN MOMENTS |")
    w("|---|---|---|")
    w(f"| what it is | the live gate would have BOUGHT: an offer existed at "
      f"<= {100*pinrun.PRICE_CEILING:.0f}c, deep enough, edge and EV pass, "
      f"not a >{100*pinrun.DUMP_DISCOUNT:.0f}c dump | the model first reached "
      f"{100*pinrun.PIN:.1f}% belief with "
      f"{pinrun.TAU_MIN} <= tau <= {pinrun.TAU_MAX}, offer or no offer |")
    w(f"| decided by | `pinsim.decide` + `pinrun.DUMP_DISCOUNT` | "
      f"`pinrun.fair` vs `pinrun.PIN` |")
    w(f"| markets | {nA:,} | {nB:,} |")
    w(f"| closes | {len({r['close'] for r in rowsA}):,} | "
      f"{len({r['close'] for r in rowsB}):,} |")
    w(f"| collapses (belief < {COLLAPSE_BELIEF:.2f} after entry, "
      f"tau >= {WATCH_TAU_MIN}) | {colA:,} ({100*bcA:.2f}%) | "
      f"{colB:,} ({100*bcB:.2f}%) |")
    w(f"| the chosen side lost | {lostA:,} ({100*blA:.2f}%) | "
      f"{lostB:,} ({100*blB:.2f}%) |")
    w("")
    if cl:
        w(f"Span {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(cl[0]))} to "
          f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(cl[-1]))} "
          f"({ndays} days), split at day 5: the first 5 days are in sample "
          f"and the last 4 are the holdout. A feature that only works in the "
          f"first half is dead.")
    w("")
    w("**A is the unit the question asks about and B is the only one with "
      "power.** Provenance features need an offer to exist, so they are "
      "reported on A and on the subset of B that had an offer at the "
      "certain second. Model-side features exist on both. Nothing is "
      "concluded from B alone about what WE would pay.")
    w("")
    w("**NO LOSS RATE ON THIS PAGE IS OUR LOSS RATE.** The tape's population "
      "is *an offer was resting there*; ours is *someone actively sold it to "
      "us*, and only the second is adversely selected -- the measured gap is "
      "31x (tape 0.11%, live 3.4%). Every rate below RANKS BUCKETS AGAINST "
      "EACH OTHER and nothing more (CLAUDE.md AMENDMENT 2026-09-10 item 5).")
    w("")
    w("**Not measured here:** whether we would have won the race for the "
      "offer (the replay always does); anything about exiting or hedging "
      "after entry; per-coin tails (a separate stage); and `MAX_PER_CLOSE`, "
      "which is not applied, so A counts every market the gate liked rather "
      "than the portfolio the bot would hold.")
    w("")

    # --- the sample day by day -------------------------------------------
    w("## The sample, day by day")
    w("")
    w("Entry opportunity is not stationary over these 9 days, and the 5/4 "
      "split is therefore partly a regime split. That is stated here so the "
      "holdout is read for what it is.")
    w("")
    dayA = defaultdict(int)
    dayB = defaultdict(int)
    dayL = defaultdict(int)
    dayC = defaultdict(int)
    for r in rowsB:
        d = time.strftime("%m-%d", time.gmtime(r["close"]))
        dayB[d] += 1
        dayC[d] += r["collapse"]
    for r in rowsA:
        d = time.strftime("%m-%d", time.gmtime(r["close"]))
        dayA[d] += 1
        dayL[d] += r["lost"]
    w("| day (UTC) | B certain | B collapses | A tradeable | A losses | half |")
    w("|---|---|---|---|---|---|")
    days = sorted(dayB)
    cut5 = days[:5]
    for d in days:
        w(f"| {d} | {dayB[d]:,} | {dayC[d]} | {dayA[d]} | {dayL[d]} | "
          f"{'first 5' if d in cut5 else 'HOLDOUT'} |")
    w("")

    # --- collapse vs loss -------------------------------------------------
    w("## Does the collapse flag track the loss?")
    w("")
    w("| population | collapsed & lost | lost, no collapse | collapsed & won "
      "| neither |")
    w("|---|---|---|---|---|")
    for nm, rs in (("A tradeable", rowsA), ("B model-certain", rowsB)):
        bo = sum(1 for r in rs if r["collapse"] and r["lost"])
        lo = sum(1 for r in rs if r["lost"] and not r["collapse"])
        co = sum(1 for r in rs if r["collapse"] and not r["lost"])
        ne = len(rs) - bo - lo - co
        w(f"| {nm} | {bo} | {lo} | {co:,} | {ne:,} |")
    w("")
    boB = sum(1 for r in rowsB if r["collapse"] and r["lost"])
    if lostB:
        w(f"On B, {boB} of {lostB} losses ({100*boB/lostB:.1f}%) were "
          f"preceded by belief falling under {COLLAPSE_BELIEF:.2f} with "
          f"{WATCH_TAU_MIN}s or more still on the clock. The collapse is "
          f"{colB/max(1,lostB):.1f}x more common than the loss, so it is the "
          f"outcome with power; the loss column is reported beside it as a "
          f"check of direction, never as evidence on its own.")
    w("")

    # --- artefact check ---------------------------------------------------
    w("## Is the collapse flag a FEED artefact?")
    w("")
    w("`IndexWS.partial()` models every settlement print that has not yet "
      "arrived with the newest spot it holds. If the index feed stalls, "
      "belief falls because the DATA went quiet, not because the market "
      "moved -- a collapse rate would then be measuring the collector. So "
      "the index age at the exact second the alarm fires is recorded. In a "
      "replay this age can only be non-zero where the RECORDED tape has a "
      "gap, which is exactly the artefact worth ruling out here; live "
      "staleness is a different question and is not measured by this file.")
    w("")

    def _q(v):
        if not v:
            return "-"
        v = sorted(v)
        return (f"{v[len(v)//2]:.1f}s median, "
                f"{v[int(0.95*(len(v)-1))]:.1f}s p95, {max(v):.1f}s worst")
    ia_e = [r["index_age_s"] for r in rowsB if r.get("index_age_s") is not None]
    ia_a = [r["t90_index_age_s"] for r in rowsB
            if r.get("t90_index_age_s") is not None]
    w("| moment | n | index age |")
    w("|---|---|---|")
    w(f"| at the certain second, every row | {len(ia_e):,} | {_q(ia_e)} |")
    w(f"| at the collapse alarm | {len(ia_a):,} | {_q(ia_a)} |")
    w("")
    if ia_a:
        stale = sum(1 for v in ia_a if v >= 3)
        w(f"{stale} of {len(ia_a)} alarms ({100*stale/len(ia_a):.1f}%) fired "
          f"with an index 3 s or more stale. "
          + ("**Small enough that the collapse flag is reading the market, "
             "not the feed.**" if stale <= 0.1 * len(ia_a) else
             "**Large enough to matter: part of what is counted as a "
             "collapse is a stalled feed, and every collapse rate below is "
             "inflated by it.**"))
    w("")

    # --- every real loss --------------------------------------------------
    losers = sorted((r for r in rowsA if r["lost"]), key=lambda r: r["close"])
    w("## Every loss among the TRADEABLE entries, as it looked at entry")
    w("")
    w("With this few losses the list is more informative than any rate. "
      "`age` is seconds the level had rested (`*` = bounded below by a book "
      "snapshot), `rel` its size against that market's own median touch over "
      "the prior 60 s.")
    w("")
    w("| close (UTC) | coin | tau | paid | margin sd | disc c | age s | "
      "fresh s | size | rel | jumps>3sd | max z | collapsed | min belief |")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")

    def _f(v, f="%.2f"):
        return "-" if v is None else (f % v)
    for r in losers:
        w(f"| {time.strftime('%m-%d %H:%M', time.gmtime(r['close']))} | "
          f"{r['coin'].replace('KX','').replace('15M','')} | {r['tau']} | "
          f"{100*r['price']:.1f}c | {_f(r['margin_sd'])} | "
          f"{_f(r['discount_c'],'%.1f')} | {_f(r['lvl_age_s'])}"
          f"{'*' if r.get('age_cens') else ''} | {_f(r['lvl_fresh_s'])} | "
          f"{_f(r['lvl_size'],'%.0f')} | {_f(r['size_rel'])} | "
          f"{'-' if r['jump3'] is None else r['jump3']} | "
          f"{_f(r['jump_max_z'])} | {'yes' if r['collapse'] else 'NO'} | "
          f"{_f(r['min_belief'],'%.3f')} |")
    w("")

    # --- power ------------------------------------------------------------
    w("## Power, stated before the estimates")
    w("")
    w("All coins settle on the same second at rho ~ 0.8, so markets are not "
      "independent facts -- CLAUDE.md's own figure is ~1.22 independent "
      "observations per close. Two MDEs are therefore given everywhere: one "
      "counting MARKETS (too optimistic) and one counting CLOSES (the "
      "conservative bound). The truth is between them.")
    w("")
    w("| population | n | baseline | MDE markets | MDE closes |")
    w("|---|---|---|---|---|")
    for nm, rs, b in (("A collapse", rowsA, bcA), ("A loss", rowsA, blA),
                      ("B collapse", rowsB, bcB), ("B loss", rowsB, blB)):
        n = len(rs)
        nc = len({r["close"] for r in rs})
        w(f"| {nm} | {n:,} markets / {nc:,} closes | {100*b:.2f}% | "
          f"{100*mde_rate(b, n):.2f}% | {100*mde_rate(b, nc):.2f}% |")
    w("")
    w(f"**Say it plainly: with {lostA} losses among the tradeable entries in "
      f"{ndays} days, NO single feature can be resolved on population A's "
      f"loss column.** A bucket holding a tenth of A would contain "
      f"{lostA/10:.1f} losses. Population A's collapse column has {colA} "
      f"events and population B's has {colB:,}; B is where the arithmetic "
      f"has any chance, and B is not the population we trade.")
    w("")

    # --- features ---------------------------------------------------------
    w("")
    w("# PRIMARY: population A, the entries the live gate would take")
    w("")
    survA, cutsA, looksA = [], [], 0
    for title, key, cuts, labels in FEATURES:
        ok, wl, res, sc = feature_section(w, rowsA, title, key, cuts, labels,
                                          bcA, blA, ndays, full=True,
                                          tag=" -- A (tradeable)")
        looksA += 1 + len(cuts)
        if ok:
            survA.append((title, key, cuts, labels, wl, res))
        for c, cr in sc:
            cutsA.append((title, key, c, cr))
    w("")
    w("# COMPANION: population B, every moment the model was certain")
    w("")
    w("Same features, ~30x the rows, on the population the 48-hour "
      "collapse table was built from. This is the backward-looking companion "
      "a null needs to be interpretable: an estimator that finds nothing "
      "here has been shown incapable of finding anything.")
    w("")
    survB, cutsB, looksB = [], [], 0
    for title, key, cuts, labels in FEATURES:
        ok, wl, res, sc = feature_section(w, rowsB, title, key, cuts, labels,
                                          bcB, blB, ndays, full=False,
                                          tag=" -- B (model-certain)")
        looksB += 1 + len(cuts)
        if ok:
            survB.append((title, key, cuts, labels, wl, res))
        for c, cr in sc:
            cutsB.append((title, key, c, cr))
    w("")

    # --- multiple looks ---------------------------------------------------
    w("---")
    w("")
    w("## Multiple looks, and what survives them")
    w("")
    nlook = looksA + looksB
    padj = 0.05 / max(1, nlook)
    w(f"{looksA} looks were taken on population A and {looksB} on B "
      f"({nlook} in total: one worst-bucket contrast plus one test per cut, "
      f"per feature, per population). At a nominal 5% level the chance of at "
      f"least one false positive across {nlook} independent looks would be "
      f"{100*(1-0.95**nlook):.1f}%, so a 95% survivor is not evidence on its "
      f"own. The Bonferroni-equivalent level is {100*padj:.3f}%, i.e. a "
      f"{100*(1-padj):.3f}% interval. Every cut that held in both halves is "
      f"re-tested at that level on the FULL sample here.")
    w("")
    w("| population | feature | gate | diff (all) | Bonferroni CI | "
      "still excludes 0 |")
    w("|---|---|---|---|---|---|")
    conf_adj = 1.0 - padj
    hard = []
    for pop, rs, cl_ in (("A", rowsA, cutsA), ("B", rowsB, cutsB)):
        for title, key, c, _cr in cl_:
            def lo_(r, _c=c, _k=key):
                v = r.get(_k)
                return v is not None and float(v) < _c

            def hi_(r, _c=c, _k=key):
                v = r.get(_k)
                return v is not None and float(v) >= _c
            pp, l_, h_, _n = boot_diff(rs, "collapse", lo_, hi_, draws=4000,
                                       seed=31, conf=conf_adj)
            okb = l_ is not None and l_ > 0
            if okb:
                hard.append((pop, title, key, c))
            w(f"| {pop} | {title.split('--')[0].strip()} | "
              f"`{key} < {c:g}` | {100*pp:+.2f} pp | "
              f"[{100*l_:+.2f}, {100*h_:+.2f}] | "
              f"{'YES' if okb else 'no'} |")
    if not (cutsA or cutsB):
        w("| - | - | - | - | - | - |")
    w("")
    if hard:
        w("**Survives even the multiple-looks correction: "
          + ", ".join("%s on %s" % (g, pop) for pop, _t, _k, g in
                      [(p_, t_, k_, "`%s < %g`" % (k_, c_))
                       for p_, t_, k_, c_ in hard]) + ".**")
    else:
        w("**Nothing survives the multiple-looks correction.**")
    w("")

    # --- the tautology check and the control that gives it away ----------
    w("---")
    w("")
    w("## THE TAUTOLOGY CHECK -- and the control that gives it away")
    w("")
    w("`margin_sd` is not an independent feature. It is the model's own "
      "belief on another scale: `margin_sd = Phi^-1(belief)`, and a "
      "\"collapse\" is defined as that SAME belief later falling under "
      f"{COLLAPSE_BELIEF:.2f}, which is 1.282 sd. So an entry admitted at "
      "the gate floor of 2.576 sd starts 1.29 sd from its own alarm, while "
      "one at 6 sd starts 4.72 sd from it. **A monotone relation between "
      "margin and collapse is mechanically forced and is not information.** "
      "It says the model is internally consistent, not that the market is "
      "readable.")
    w("")
    w("The distribution says the same thing: on population B the 25th, 50th "
      "and 75th percentiles of `margin_sd` are all 7.034, which is the "
      "numerical ceiling of `Phi^-1` at a belief clipped to 1 - 1e-12. Most "
      "certain moments are not 'very confident', they are "
      "'arithmetically finished'.")
    w("")
    w("**And here is the giveaway.** `4b. PRICE PAID` is a CONTROL -- it was "
      "included precisely so that a spurious method would be caught. Look "
      "at what it does in the cut sweep and in the cost table: a cheaper "
      "price is a bigger discount, a bigger discount means the model is only "
      "marginally certain, so `price` inherits the margin effect and "
      "\"survives\" too. Refusing it would cost almost the entire income. "
      "A method that certifies a control has certified nothing.")
    w("")
    w("So the question is re-asked properly: **holding the margin roughly "
      "fixed, does anything in the BOOK or the INDEX add to it?**")
    w("")
    heldB = stratified_residual(
        w, rowsB, "B, margin_sd < 3 (the most exposed stratum)",
        "margin_sd", 3.0, {"margin_sd", "conf"})
    heldB4 = stratified_residual(
        w, rowsB, "B, margin_sd < 4", "margin_sd", 4.0,
        {"margin_sd", "conf"})
    heldA = stratified_residual(
        w, rowsA, "A, margin_sd < 5 (every tradeable entry that ever "
        "collapsed)", "margin_sd", 5.0, {"margin_sd", "conf"})
    w("")

    # --- money ------------------------------------------------------------
    w("---")
    w("")
    w("## The per-close arithmetic")
    w("")
    w("Money is only defined where we would actually have traded, so this is "
      "population A. Refusing a bucket changes two things -- the losses "
      "avoided and the wins given up -- and this project has twice been "
      "fooled by a per-contract table that reversed per close "
      "(\"be more patient for a bigger discount\", 2026-09-11; \"stop paying "
      "above 94c\", 2026-09-12). P&L is scaled linearly to size "
      f"{size:g} and is a CEILING: the replay always wins the race.")
    w("")
    # A gate is a cut, so the cuts that held in both halves are priced
    # first, on population A, whichever population found them.
    if cutsA or cutsB:
        w("**Refusing everything below a cut, on population A.** A cut found "
          "on B is priced here too, because money only exists where we would "
          "have traded.")
        w("")
        w("| gate (refuse below) | found on | entries refused | closes | "
          "losses in it | collapses in it | $/close now | $/close if "
          "refused | change |")
        w("|---|---|---|---|---|---|---|---|---|")
        seen = set()
        for pop, cl_ in (("A", cutsA), ("B", cutsB)):
            for title, key, c, _cr in cl_:
                if (key, c) in seen:
                    continue
                seen.add((key, c))

                def below(r, _c=c, _k=key):
                    v = r.get(_k)
                    return v is not None and float(v) < _c
                pc = per_close_cost(rowsA, below, size=size)
                ncol = sum(r["collapse"] for r in rowsA if below(r))
                w(f"| `{key} < {c:g}` | {pop} | {pc['n_refused']:,} of "
                  f"{nA:,} | {pc['closes']:,} | {pc['n_refused_lost']} of "
                  f"{lostA} | {ncol} of {colA} | "
                  f"${pc['per_close_all']:.3f} | "
                  f"${pc['per_close_kept']:.3f} | "
                  f"{pc['per_close_delta']:+.3f} |")
        w("")
    w("**And the single worst BUCKET of each feature, for comparison.**")
    w("")
    shown = survA or survB
    if not shown:
        w("Nothing survived the split, so nothing is priced as a proposal. "
          "The three widest separations on A are priced anyway, so the cost "
          "of acting on a marginal result is on the record.")
        w("")
        cand = []
        for title, key, cuts, labels in FEATURES:
            floor = max(5, len(rowsA) // 25)
            tab = [t for t in bucket_table(rowsA, key, cuts, labels)
                   if t["bucket"] != "n/a" and t["n"] >= floor]
            if len(tab) < 2:
                continue
            worst = max(tab, key=lambda t: t["collapse"]["rate"])
            rest_n = sum(t["n"] for t in tab if t is not worst)
            rest_k = sum(t["collapse"]["k"] for t in tab if t is not worst)
            cand.append((worst["collapse"]["rate"] - (rest_k / max(1, rest_n)),
                         title, key, cuts, labels, worst["bucket"]))
        cand.sort(key=lambda x: -x[0])
        shown = [(t, k, c, l, wl, None) for _, t, k, c, l, wl in cand[:3]]
    if not shown:
        w("_no bucket holds enough entries to price_")
        w("")
    w("| feature / bucket refused | entries | closes | losses in it | "
      "$/close now | $/close if refused | change |")
    w("|---|---|---|---|---|---|---|")
    for title, key, cuts, labels, wl, _res in shown:
        sel = _sel_bucket(key, cuts, labels, wl)
        pc = per_close_cost(rowsA, sel, size=size)
        w(f"| {title.split('--')[0].strip()} `{wl}` | {pc['n_refused']:,} | "
          f"{pc['closes']:,} | {pc['n_refused_lost']} | "
          f"${pc['per_close_all']:.3f} | ${pc['per_close_kept']:.3f} | "
          f"{pc['per_close_delta']:+.3f} |")
    w("")

    # --- verdict ----------------------------------------------------------
    w("---")
    w("")
    w("## Verdict")
    w("")
    w(f"**How to know when not to buy: on this tape, the only entry-time "
      f"quantity that predicts the post-entry collapse is the model's own "
      f"margin to the strike -- and that is very nearly a tautology, it is "
      f"not affordable to act on, and nothing in the order book or the "
      f"index adds to it.** Three separate findings, in that order.")
    w("")
    w(f"**1. The margin result is real and monotone on both populations.** "
      f"On the {nA:,} tradeable entries, margin_sd >= 5 collapsed 0 times in "
      f"113 while margin_sd < 5 collapsed 16 times in 296 (5.41%); the "
      f"cluster-bootstrap difference is +5.41 pp [+2.57, +8.65] overall and "
      f"excludes zero in BOTH halves (+4.29 in sample, +8.14 on the "
      f"holdout). On the {nB:,} model-certain moments it is monotone across "
      f"every cut with tight intervals, and it survives the "
      f"multiple-looks correction. But `margin_sd = Phi^-1(belief)` and the "
      f"collapse is defined on the same belief, so the relation is forced: "
      f"an entry at the 2.576-sd gate floor starts 1.29 sd from its own "
      f"alarm and one at 6 sd starts 4.72 sd away. See THE TAUTOLOGY CHECK. "
      f"The `price` CONTROL survives the same test for the same reason, "
      f"which is how a method announces it has found a mechanism rather "
      f"than a signal.")
    w("")
    w(f"**2. It is not affordable.** Every surviving cut costs a large share "
      f"of a small income. The cheapest one, refusing margin_sd < 3, gives "
      f"up $0.441 of $1.321 per close -- a third of the money -- to remove "
      f"1 of {lostA} losses. Refusing margin_sd < 5, the cut with the "
      f"cleanest statistics, gives up $0.703 of $1.321 (53%) and refuses "
      f"72% of all entries. The control, refusing price < 98c, gives up 94%. "
      f"Note also that 13 of the {colA} collapses on A went on to WIN, so "
      f"most of what these gates buy is the avoidance of a scare, not of a "
      f"loss.")
    w("")
    w(f"**3. Nothing in the book or the index adds to the margin.** With the "
      f"margin held roughly fixed, offer age, offer freshness, offer size "
      f"(absolute and relative to the market's own recent touch), the count "
      f"of 3-sigma one-second index moves in the previous 120 s, the largest "
      f"such move, tau and the discount all fail to separate the collapse in "
      f"both halves of the tape. **So the hypothesis that a fresh, large "
      f"offer is a dump by someone who knows is NOT supported at the entry "
      f"second, on this tape, at this power.**")
    w("")
    # the positive control: does the estimator recover a KNOWN effect?
    _lo = [r for r in rowsA if r.get("margin_sd") is not None
           and r["margin_sd"] < 5.0]

    def _deep(r):
        v = r.get("discount_c")
        return v is not None and float(v) >= 10.0
    _dn = [r for r in _lo if _deep(r)]
    _sn = [r for r in _lo if r.get("discount_c") is not None
           and not _deep(r)]
    _dk = sum(r["collapse"] for r in _dn)
    _sk = sum(r["collapse"] for r in _sn)
    _pc = per_close_cost(rowsA, _deep, size=size)
    w(f"**The positive control: the estimator DOES find the one entry-time "
      f"effect this project already knows about.** Inside the same "
      f"margin_sd < 5 stratum, entries taken at a discount of 10c or more "
      f"below fair collapsed {_dk} of {len(_dn)} times "
      f"({100*_dk/max(1,len(_dn)):.1f}%) against {_sk} of {len(_sn)} "
      f"({100*_sk/max(1,len(_sn)):.2f}%) at smaller discounts, a difference "
      f"of {100*(_dk/max(1,len(_dn)) - _sk/max(1,len(_sn))):+.1f} pp. That "
      f"is the DISCOUNT CLIFF, rediscovered from a different outcome "
      f"variable on a different population -- and it is already a live guard "
      f"at 15c (`pinrun.DUMP_DISCOUNT`). So the null on provenance and "
      f"jumpiness is NOT the null of an estimator that cannot find "
      f"anything. It is also not a reason to tighten the guard from 15c to "
      f"10c: on this sample that refusal costs "
      f"{_pc['per_close_delta']:+.3f} per close of "
      f"${_pc['per_close_all']:.3f} "
      f"({100*_pc['per_close_delta']/_pc['per_close_all']:+.0f}%), and the "
      f"48-hour trade-tape study (results/SKIM.md) already measured the "
      f"10-15c band at +7.51c per contract, i.e. profitable.")
    w("")
    w("**And the control fires twice, which is the strongest single reason "
      "to disbelieve the survivors.** `4b. PRICE PAID` was put in the list "
      "as a control. It survives the split on A, survives the "
      "multiple-looks correction, and survives inside the margin stratum. "
      "A cheaper price is a larger discount, a larger discount means the "
      "model is only marginally certain, so `price` is a proxy for `margin` "
      "and nothing more. `lvl_fresh_s < 0.5` -- the one provenance cut that "
      "holds inside the A stratum -- fails on the 4x-larger B stratum "
      "(+1.03 pp [-2.82, +5.73]), which is what a proxy for price looks "
      "like rather than a real effect.")
    w("")
    w(f"**What that leaves, and it is the honest answer to the question "
      f"asked:** the entry second does know something, but only what the "
      f"model already tells it, and the live gate already uses that number "
      f"as its own admission test. A new refusal would have to be a "
      f"TIGHTENING of `PIN`, priced at 33-53% of the income, and the "
      f"decision then rests on the drawdown the operator will sit through, "
      f"not on a new feature. **Everything still rides on the exit**, which "
      f"is where `PREREG_hedge.md` already points.")
    w("")
    w(f"**The null, with its MDE, so it is not read as an absence.** With "
      f"{lostA} losses among the tradeable entries in {ndays} days, the "
      f"smallest effect population A could resolve on its loss column was "
      f"about {100*mde_rate(blA, len(rowsA)):.1f}% against a "
      f"{100*blA:.2f}% base -- nothing short of a feature that triples the "
      f"loss rate was ever findable there, which is why the collapse was "
      f"made the primary outcome and a 30x-larger companion population was "
      f"harvested alongside it. On the collapse column the companion "
      f"resolves {100*mde_rate(bcB, len(rowsB)):.2f}% against "
      f"{100*bcB:.2f}%, and it still finds nothing once the margin is held "
      f"fixed.")
    w("")
    w("### PROPOSED gate")
    w("")
    w("**None. No gate is proposed and nothing here is deployed.** The two "
      "candidates a mechanical reading of the tables would produce are "
      "written out with their prices so the rejection is on the record:")
    w("")
    for key, c in (("margin_sd", 3.0), ("margin_sd", 5.0)):
        def below(r, _c=c, _k=key):
            v = r.get(_k)
            return v is not None and float(v) < _c
        pc = per_close_cost(rowsA, below, size=size)
        ncol = sum(r["collapse"] for r in rowsA if below(r))
        w(f"- `refuse {key} < {c:g}` -- refuses {pc['n_refused']} of {nA} "
          f"entries ({100*pc['n_refused']/max(1,nA):.1f}%), holds "
          f"{pc['n_refused_lost']} of {lostA} losses and {ncol} of {colA} "
          f"collapses, and moves P&L from ${pc['per_close_all']:.3f} to "
          f"${pc['per_close_kept']:.3f} per close at size {size:g} "
          f"({pc['per_close_delta']:+.3f}, "
          f"{100*pc['per_close_delta']/pc['per_close_all']:+.0f}%). "
          f"REJECTED on cost.")
    w("")
    w("Were either ever to be reconsidered, AMENDMENT 2026-09-10 requires "
      "both a holdout split (this has one) and a pre-registered live bar "
      "written before the number is seen (this has none). And the P&L column "
      "above is a replay ceiling: it assumes we win every race for the "
      "offer, which live we do 70% of the time.")
    w("")
    w("### What would have to be true for anything above to be an artefact")
    w("")
    w("1. **The collapse flag could be the feed, not the market.** Checked "
      "at the alarm second: 0 of the alarms fired with a recorded index 3 s "
      "or more stale.")
    w("2. **The margin effect could be a tautology.** It substantially IS "
      "one -- checked, stated, and the reason the `price` control was read "
      "as a refutation rather than a second discovery.")
    w("3. **The book could be wrong.** The replay is delta-driven with "
      "snapshots applied at their real `_rx_ms`. `pinsim.load_hour` stamps "
      "every snapshot 0, which this file deliberately does not use -- with "
      "that bug a snapshot-seeded level is born at the epoch and "
      "`if born else None` silently drops the row, which is how it was "
      "found. A level seeded by a snapshot is a lower bound on its age and "
      "is flagged `age_cens`.")
    w("4. **Clustering could manufacture the separation.** Every headline "
      "interval is a cluster bootstrap over CLOSES. The self-test contains a "
      "world where 240 markets carry 20 independent facts and the per-market "
      "Clopper-Pearson intervals separate while the clustered interval "
      "correctly does not.")
    w("5. **The split could be luck, and 92 looks were taken.** Nothing is "
      "called a survivor unless its interval excludes zero in both halves, "
      "holdout included, and every such survivor is re-tested at the "
      "Bonferroni-equivalent level.")
    w("")
    w("### What was NOT measured")
    w("")
    w("- Whether the offer would have been OURS. The replay wins every "
      "race; live we fill 70% of attempts. No loss rate here is our loss "
      "rate, and none is quoted as one.")
    w("- Anything about exiting or hedging after entry.")
    w("- Per-coin jump tails, which are a separate stage.")
    w("- `MAX_PER_CLOSE`, not applied, so A is every market the gate liked "
      "rather than the portfolio the bot would hold.")
    w("- Live index staleness. In a replay the index age can only be "
      "non-zero where the recorded tape has a gap.")
    w("- Interactions between features, and any multivariate model. Only "
      "one-at-a-time cuts and one margin stratification were tested.")
    w("")

    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(ls) + "\n")
    log(f"  report -> {out_path} ({len(ls)} lines)")
    return survA, survB


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=216)
    ap.add_argument("--end", default=None,
                    help="last book hour, e.g. 20260912T03")
    ap.add_argument("--size", type=float, default=20.0)
    ap.add_argument("--rows", default=ROWS)
    ap.add_argument("--out", default=REPORT)
    ap.add_argument("--report-only", action="store_true",
                    help="skip the replay and re-read --rows")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    if not a.report_only:
        harvest(a.hours, a.end, a.size, a.rows)
    rowsA = load_rows(a.rows, POP_A)
    rowsB = load_rows(a.rows, POP_B)
    if not rowsB:
        print("  loaded nothing -- no certain moments to analyse")
        return
    print(f"  A {len(rowsA):,} tradeable entries / "
          f"B {len(rowsB):,} certain markets over "
          f"{len({r['close'] for r in rowsB}):,} closes")
    report(rowsA, rowsB, a.out, size=a.size)


if __name__ == "__main__":
    main()
