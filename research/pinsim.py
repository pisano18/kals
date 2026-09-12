#!/usr/bin/env python3
# VERSION: 2026-09-10-ps1
"""pinsim.py -- THE BACKTEST THE OPERATOR ASKED FOR, AND HE WAS RIGHT.

His words, 2026-09-10:

    "I don't get why the backtest is so hard for you to do right, you must be
     over complicating it or doing it in a dumb way. It literally just 'its
     3:14:30, do I buy or no?' Then run the program we have. Then at 3:15 see
     the price that actually happened"

HE IS RIGHT AND THIS FILE IS THE ADMISSION. Before this, the decision was
REIMPLEMENTED three separate times -- pincross.passes_live_gate,
pintail.window_state + its own fair, pinfirst.crossings -- none of which ran
the code the bot runs. Three copies of one decision is three chances to
diverge from live, and divergence is the exact thing the backtest exists to
rule out. It already bit once: pinrun computes sigma as an sd about the mean
with (n-1), the tape stages used a plain RMS. They happened to agree to 0.08%.
That was luck, not design.

SO THIS FILE REIMPLEMENTS NOTHING. It calls pinrun's own functions:

    pinrun.fair()            the model
    pinrun.net_edge()        the edge test
    pinrun.expected_value()  the EV test
    pinrun.billed_fee()      the fee
    pinrun.PIN, PRICE_CEILING, EDGE_FLOOR, EV_FLOOR, TAU_MIN, TAU_MAX,
    MIN_FILL_FRAC, MIN_LEVEL, MAX_BOOK_AGE_MS, SIGMA_STRESS

and it feeds them from the tape through pinrun's OWN IndexWS class. The only
override is `spot()`, whose age is measured against wall-clock `time.time()`
in live and must be measured against the simulated second here. One method,
two lines, and it is the only place a divergence can hide.

NO LOOKAHEAD BY CONSTRUCTION: ticks are inserted into the index only as the
simulated clock reaches them, exactly as they arrive live. `partial()` and
`sigma()` are then the untouched live code reading an untouched live
structure.

WHAT THIS STILL CANNOT TELL US, and no replay can: whether the offer would
have been OURS. Live we fill 70% of the attempts we make. Every number here
assumes we win every race, so it is an UPPER BOUND and says so in its output.
"""
import argparse
import glob
import gzip
import json
import os
import sys
import tempfile
import time
import zlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinrun                                                # noqa: E402
import pindata                                               # noqa: E402
import pinrules                                              # noqa: E402
from statistics import NormalDist                            # noqa: E402
_ND = NormalDist()

DATA = r"C:\kals\kalshi_data"
FULLTAPE = r"C:\kals\fulltape\markets.json"
LIVE_FILL_RATE = 0.70          # measured: 50 fills from 72 attempts


class TapeIndex(pinrun.IndexWS):
    """pinrun's OWN index, fed from the tape.

    `spot()` is the single method that reads the wall clock, so it is the
    single method overridden. `partial()` and `sigma()` -- the two that
    actually decide the trade -- are inherited untouched, which is the whole
    point of this class existing.
    """

    def __init__(self, ids):
        super().__init__(ids)
        self.now = 0

    def spot(self, iid):
        s, v, _ = super().spot(iid)
        return (s, v, (self.now - s)) if s is not None else (None, None, None)

    def feed_upto_ms(self, series_ticks, ms):
        """Feed the index to a MILLISECOND, and set the clock to it.

        A book event at second S + 440 ms must see the print STAMPED S -- it
        is on the wire by then -- and must NOT see the print stamped S+1,
        which does not exist yet. `feed_upto` takes seconds, so the rule is
        `ms // 1000`, stated here once instead of at every call site.

        `now` is kept FRACTIONAL because live measures the index's age against
        `time.time()`: at S+440 ms with the newest print stamped S the live
        bot logs `index_age_s` 0.44, and pinreplay recovers the decision
        millisecond from exactly that field. An integer clock would report 0
        and the replayed record would not match the live log.
        """
        self.feed_upto(series_ticks, ms // 1000)
        self.now = ms / 1000.0

    def feed_upto(self, series_ticks, upto):
        """Insert every tick at or before `upto` and no others."""
        for iid, pend in series_ticks.items():
            while pend and pend[0][0] <= upto:
                sec, val = pend.pop(0)
                self.on_frame({"type": "cfbenchmarks_value",
                               "msg": {"index_id": iid,
                                       "data": json.dumps(
                                           {"time": sec * 1000,
                                            "value": str(val)})}})


def book_view(bk, now_ms):
    """pindata's rebuilt book in the shape pinrun's livebook.best() returns."""
    yb, nb = bk.best()
    out = {"suspect": False,
           "age_ms": (now_ms - bk.last_ts) if bk.last_ts else None}
    out["yes_ask"] = round(1.0 - nb, 4) if nb is not None else None
    out["yes_ask_size"] = bk.no.get(nb, 0.0) if nb is not None else 0.0
    out["no_ask"] = round(1.0 - yb, 4) if yb is not None else None
    out["no_ask_size"] = bk.yes.get(yb, 0.0) if yb is not None else 0.0
    return out


def decide(idx, iid, close_s, now_s, strike, digits, b, size):
    """EXACTLY pinrun's decision, by calling pinrun. Nothing reimplemented.

    Returns (want, price, take_n, fair) or (None, reason, None, fair).
    """
    sg = idx.sigma(iid)
    if sg is None:
        return None, "no_sigma", None, None
    f = pinrun.fair(idx, iid, close_s, now_s, strike,
                    sg * pinrun.SIGMA_STRESS, round_digits=digits)
    if f is None:
        return None, "no_fair", None, None
    want = price = avail = None
    if f >= pinrun.PIN:
        ya, ys = b.get("yes_ask"), b.get("yes_ask_size")
        if ya and ys and ya < 1.0:
            want, price, avail = "yes", ya, ys
    elif f <= 1.0 - pinrun.PIN:
        na, ns = b.get("no_ask"), b.get("no_ask_size")
        if na and ns and na < 1.0:
            want, price, avail = "no", na, ns
    if want is None:
        return None, ("no_offer" if (f >= pinrun.PIN or f <= 1 - pinrun.PIN)
                      else "undecided"), None, f
    take_n = min(float(size), float(avail))
    if take_n < max(pinrun.MIN_LEVEL, pinrun.MIN_FILL_FRAC * float(size)):
        return None, "too_shallow", None, f
    if price > pinrun.PRICE_CEILING:
        return None, "over_ceiling", None, f
    if pinrun.net_edge(f, price, want) < pinrun.EDGE_FLOOR:
        return None, "no_edge", None, f
    if pinrun.expected_value(price) < pinrun.EV_FLOOR:
        return None, "neg_ev", None, f
    return want, price, take_n, f


def record(f, want, price, take_n, avail, tau, series, sec, sg, spot,
           book_age_ms, index_age_s, cond=(None, None, None)):
    """THE DECISION RECORD -- the contract between live and replay
    (pinrules.FIELDS). Everything a rule may see, all backward-looking."""
    conf = f if want == "yes" else 1.0 - f
    cc = min(max(conf, 1e-12), 1 - 1e-12)
    return {
        "fair": round(f, 6), "conf": round(conf, 6),
        "margin_sd": round(_ND.inv_cdf(cc), 3), "want": want,
        "price": round(price, 4),
        "discount_c": round(100.0 * (conf - price), 2),
        "edge_c": round(100.0 * pinrun.net_edge(f, price, want), 3),
        "ev_c": round(100.0 * pinrun.expected_value(price), 3),
        "tau": int(tau), "depth": float(avail), "take_n": float(take_n),
        "coin": series, "hour_utc": time.gmtime(sec).tm_hour,
        "sigma": sg, "spot": spot,
        "cond_x": cond[0], "cond_n": cond[1], "cond_own": cond[2],
        "book_age_ms": book_age_ms, "index_age_s": index_age_s,
    }


def apply_profile(profile):
    """Run pinrun's OWN decision code under a profile's params -- the
    constants are module attributes read at call time, so setting them is
    exactly what a restart with those values would do."""
    for k, v in profile["params"].items():
        if hasattr(pinrun, k):
            # a schedule is resolved per decision (see resolve_for); the
            # module gets the schedule's default so nothing reads a dict
            setattr(pinrun, k, v["default"] if pinrules.is_schedule(v) else v)


def resolve_for(profile, rec):
    """Set the schedulable params for THIS decision from the record so far.
    SIZE by price, PRICE_CEILING by margin, SIGMA_STRESS by conditions -- the
    live code reads them as module constants, so they are set right before
    the decision and mean exactly what a restart with those values would."""
    for k in ("SIZE", "PRICE_CEILING", "SIGMA_STRESS", "MAX_PER_CLOSE",
              "MIN_FILL_FRAC", "IMPROVE_BY", "EDGE_FLOOR", "EV_FLOOR",
              "MEASURED_FLIP", "PIN"):
        v = profile["params"].get(k)
        if pinrules.is_schedule(v):
            setattr(pinrun, k, pinrules.resolve(profile, k, rec))


# ------------------------------------------------------------------ self-test
def selftest():
    print("SELF-TEST -- pinsim")
    # ---- AMENDMENT 15: the hedge REPORT must run, on a fixture that hits
    # every branch. A 72-hour holdout completed all 162 buys on 2026-09-12
    # and died in hedge_report on a NameError, because nothing ever called
    # it before real data did. A report that cannot print is a run lost.
    _thrs = (0.70, 0.90)
    _fake = {
        "W1": {"w": "yes", "px": 0.96, "n": 20.0, "cs": 1000, "iid": "X",
               "strike": 1.0, "digits": 2, "won": True, "pnl": 0.75,
               "tau_in": 25, "min_belief": 0.65,
               "h": {0.70: {"filled": 20.0, "ask": 0.30, "tau": 12,
                            "belief": 0.65, "edge_c": 5.0}, 0.90: None},
               "alarm_tau": {0.70: 12, 0.90: 14}, "tries": {0.70: 1, 0.90: 1}},
        "L1": {"w": "no", "px": 0.96, "n": 20.0, "cs": 1000, "iid": "X",
               "strike": 1.0, "digits": 2, "won": False, "pnl": -19.24,
               "tau_in": 22, "min_belief": 0.0,
               "h": {0.70: {"filled": 20.0, "ask": 0.55, "tau": 15,
                            "belief": 0.40, "edge_c": 5.0},
                     0.90: {"filled": 20.0, "ask": 0.50, "tau": 16,
                            "belief": 0.84, "edge_c": -34.0}},
               "alarm_tau": {0.70: 15, 0.90: 16}, "tries": {0.70: 1, 0.90: 1}},
        "L2": {"w": "no", "px": 0.979, "n": 20.0, "cs": 1000, "iid": "X",
               "strike": 1.0, "digits": 2, "won": False, "pnl": -19.61,
               "tau_in": 30, "min_belief": 0.0,
               "h": {0.70: {"filled": 0.0, "why": "no_ask_in_time"},
                     0.90: {"filled": 0.0, "why": "no_ask_in_time"}},
               "alarm_tau": {0.70: 11, 0.90: 11}, "tries": {0.70: 6, 0.90: 6}},
    }
    _out = []
    try:
        hedge_report(_fake, _thrs, say=_out.append)
        _txt = "\n".join(_out)
        _ok = ("AMENDMENT 15 HOLDOUT" in _txt and "0.70" in _txt
               and "0.90" in _txt and "3 simulated positions" in _txt
               and "2 lost" in _txt)
        print(("  ok   " if _ok else "  FAIL ")
              + "hedge_report runs on a fixture with a false alarm, a hedged "
                "loser and an unfilled loser, and names all three thresholds' "
                "rows")
        if not _ok:
            print("SELF-TEST *** FAILED ***")
            return False
    except Exception as _e:                                      # noqa: BLE001
        print(f"  FAIL hedge_report raised: {_e!r}")
        print("SELF-TEST *** FAILED ***")
        return False
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    ck(TapeIndex.partial is pinrun.IndexWS.partial,
       "partial() is pinrun's own code, not a copy")
    ck(TapeIndex.sigma is pinrun.IndexWS.sigma,
       "sigma() is pinrun's own code, not a copy")
    ck(TapeIndex.spot is not pinrun.IndexWS.spot,
       "spot() is the ONLY override -- it is the only wall-clock read")

    C = 1_000_000
    ix = TapeIndex(["T"])
    pend = {"T": [(s, 100.0) for s in range(C - 400, C)]}
    ix.now = C - 30
    ix.feed_upto(pend, C - 30)
    ck(max(ix.ticks["T"]) == C - 30,
       f"NO LOOKAHEAD: at now=close-30 the index holds nothing past it "
       f"(newest {max(ix.ticks['T']) - C})")
    _, _, age = ix.spot("T")
    ck(age == 0, f"spot age is measured against the simulated clock ({age})")
    ix.now = C - 25
    ck(ix.spot("T")[2] == 5, "and it advances with it")

    # the decision must be pinrun's: a certain market with a cheap offer buys
    ix2 = TapeIndex(["T"])
    p2 = {"T": [(s, 100.0) for s in range(C - 700, C)]}
    ix2.now = C - 10
    ix2.feed_upto(p2, C - 10)
    b = {"yes_ask": 0.97, "yes_ask_size": 500.0, "no_ask": 0.02,
         "no_ask_size": 500.0, "age_ms": 5, "suspect": False}
    w, px, n, f = decide(ix2, "T", C, C - 10, 50.0, 2, b, 20)
    ck(w == "yes" and px == 0.97,
       f"a certain YES with a 97c offer is bought (got {w} {px}, fair {f})")
    b2 = dict(b, yes_ask=0.99)
    w2, why, _, _ = decide(ix2, "T", C, C - 10, 50.0, 2, b2, 20)
    ck(w2 is None and why == "over_ceiling",
       f"and the same market at 99c is refused by pinrun's OWN ceiling "
       f"({pinrun.PRICE_CEILING}) -> {why}")
    b3 = dict(b, yes_ask_size=3.0)
    w3, why3, _, _ = decide(ix2, "T", C, C - 10, 50.0, 2, b3, 20)
    ck(w3 is None and why3 == "too_shallow",
       f"and refused when only 3 contracts rest against size 20 -> {why3}")
    ck(abs(pinrun.PIN - 0.995) < 1e-9,
       f"and it is reading the LIVE gate right now ({pinrun.PIN})")

    # --- profiles: the same decision code under DATA ------------------------
    prof = pinrules.default_profile()
    r_ = record(1.0, "yes", 0.82, 20.0, 500.0, 21, "KXXRP15M", C - 21,
                0.00008, 1.39075, 2, 0.18)
    ck(set(r_) == set(pinrules.FIELDS),
       "record() produces EXACTLY the fields a rule may see -- no more, no less")
    v_, fired_ = pinrules.decide(prof, r_)
    ck(v_ == "refuse" and fired_ == [("dump", "refuse")],
       "the XRP loss, rebuilt as a decision record, is refused by the "
       "default profile's rule")
    saved = pinrun.PIN
    p2 = json.loads(json.dumps(prof))
    p2["params"]["PIN"] = 0.98
    apply_profile(p2)
    ck(abs(pinrun.PIN - 0.98) < 1e-12,
       "apply_profile() changes the live constant the decision code reads")
    w4, why4, _, _ = decide(ix2, "T", C, C - 10, 50.0, 2, b2, 20)
    apply_profile(prof)
    ck(abs(pinrun.PIN - saved) < 1e-12,
       "and applying the default puts it back exactly")
    # a SIZE schedule by price changes what the live code takes
    p3 = json.loads(json.dumps(prof))
    p3["params"]["SIZE"] = {"by": "price", "default": 20,
                            "bands": [[0.50, 0.90, 60], [0.90, 0.99, 10]]}
    apply_profile(p3)
    resolve_for(p3, {"price": 0.85})
    w5, px5, n5, _ = decide(ix2, "T", C, C - 10, 50.0, 2,
                            dict(b, yes_ask=0.85), pinrun.SIZE)
    resolve_for(p3, {"price": 0.97})
    w6, px6, n6, _ = decide(ix2, "T", C, C - 10, 50.0, 2, b, pinrun.SIZE)
    apply_profile(prof)
    ck(w5 == "yes" and n5 == 60 and w6 == "yes" and n6 == 10,
       f"SIZE by price: 60 contracts at 85c, 10 at 97c, through the live "
       f"decision code (got {n5}, {n6})")

    # --- THE 2026-09-12 REBUILD: the book, the clock, and the gate ---------
    # Each of these is one of the four things results/RESULTS_replay.md said
    # was wrong. A world is built where the answer is already known, and the
    # test fails if the estimator misses it OR finds it in a world with
    # nothing planted.

    # (i) the index must be fed to a MILLISECOND, not to a second boundary
    ixm = TapeIndex(["T"])
    S = C - 20
    pm = {"T": [(sec, 100.0) for sec in range(C - 400, C + 2)]}
    ixm.feed_upto_ms(pm, S * 1000 + 440)
    ck(S in ixm.ticks["T"] and (S + 1) not in ixm.ticks["T"],
       f"an event at S+440 ms sees the print stamped S and NOT the one "
       f"stamped S+1 (newest held {max(ixm.ticks['T']) - S:+d} from S)")
    ck(abs(ixm.now - (S + 0.44)) < 1e-9,
       f"and the clock it reads its own age against is fractional "
       f"({ixm.now - S:+.2f} s into the second), as live's time.time() is")

    # (ii) SEQ ORDER: a snapshot arriving mid-stream must OVERWRITE the book,
    #      not be pre-applied to an empty one. Planted: a 50c bid, then a
    #      snapshot that does not contain it, then a 55c bid.
    T0 = 1_700_000_000_000
    _snap_msg = {"market_ticker": "M", "yes_dollars_fp": [["0.60", "7"]]}
    _lines = [
        {"type": "orderbook_delta", "sid": 4, "seq": 10, "_rx_ms": T0 + 17,
         "msg": {"market_ticker": "M", "price_dollars": "0.50",
                 "delta_fp": "100", "side": "yes", "ts_ms": T0}},
        {"type": "orderbook_delta", "sid": 4, "seq": 30, "_rx_ms": T0 + 117,
         "msg": {"market_ticker": "M", "price_dollars": "0.55",
                 "delta_fp": "40", "side": "yes", "ts_ms": T0 + 100}},
        {"type": "orderbook_delta", "sid": 4, "seq": 40, "_rx_ms": T0 + 217,
         "msg": {"market_ticker": "OTHER", "price_dollars": "0.10",
                 "delta_fp": "1", "side": "yes", "ts_ms": T0 + 200}},
    ]
    _fp = os.path.join(tempfile.gettempdir(),
                       f"pinsim_selftest_{os.getpid()}.jsonl.gz")
    with gzip.open(_fp, "wt") as _f:
        for _d in _lines:
            _f.write(json.dumps(_d) + "\n")
    _snaps = [("M", _snap_msg, 20, T0 + 50)]
    try:
        ev_seq = list(EventStream(_fp, _snaps, {"M": 1}, order="seq"))
        ev_old = list(EventStream(_fp, _snaps, {"M": 1}, order="snapfirst"))
        # a snapshot whose RECEIPT trails the exchange stamp of the delta it
        # precedes in seq order: the median lag on this tape is 17 ms, so this
        # is the normal case, not a corner one
        ev_clamp = list(EventStream(_fp, [("M", _snap_msg, 20, T0 + 900)],
                                    {"M": 1}))
    finally:
        try:
            os.remove(_fp)
        except OSError:
            pass
    b_seq, b_old = pindata.Book(), pindata.Book()
    for _bk, _ev in ((b_seq, ev_seq), (b_old, ev_old)):
        for _ts, _kind, _tk, _pl in _ev:
            if _tk is None:
                continue
            if _kind == 0:
                _bk.snapshot(_pl, _ts)
            else:
                _bk.delta(_pl[0], _pl[1], _pl[2], _ts)
    ck(0.50 not in b_seq.yes and b_seq.yes.get(0.60) == 7.0
       and b_seq.yes.get(0.55) == 40.0,
       f"SEQ ORDER: the mid-stream snapshot WIPES the 50c level that preceded "
       f"it and keeps the 55c delta that followed it ({dict(b_seq.yes)})")
    ck(b_old.yes.get(0.50) == 100.0,
       f"and snapshots-first -- what this file did until today -- leaves that "
       f"50c level standing, because the snapshot was applied before it "
       f"({dict(b_old.yes)})")
    _snap_ev = [e for e in ev_seq if e[1] == 0]
    ck(len(_snap_ev) == 1 and _snap_ev[0][0] == T0 + 50,
       f"the snapshot carries its REAL receipt _rx_ms, never 0 "
       f"({_snap_ev[0][0] - T0:+d} ms from the first delta)")
    ck([e[0] for e in ev_old if e[1] == 0] == [0],
       "whereas the old order stamped it 0, which is why it could never "
       "overwrite anything")
    _cl = [e for e in ev_clamp if e[1] == 0]
    ck(len(_cl) == 1 and _cl[0][0] == T0 + 100,
       f"and a receipt that trails the delta it precedes is clamped DOWN to "
       f"that delta's ts_ms ({_cl[0][0] - T0:+d} ms, not +900), so the "
       f"merge's own clock cannot run backwards")

    # (iii) EVENT-DRIVEN EVALUATION: an offer that exists for 400 ms inside
    #       one second must be bought; the same offer sampled at the second
    #       boundary must be missed.
    def _walk_buys(per_event):
        ixw = TapeIndex(["BRTI"])
        pw = {"BRTI": [(sec, 100.0) for sec in range(C - 700, C)]}
        mkw = {"M": {"ticker": "M", "series": "KXBTC15M", "close": float(C),
                     "strike": 50.0, "result": "yes"}}
        evs = [(S * 1000, 1, None, None),
               (S * 1000 + 300, 1, "M", ("no", 0.03, 500.0)),
               (S * 1000 + 700, 1, "M", ("no", 0.03, -500.0)),
               ((S + 1) * 1000, 1, None, None),
               ((S + 1) * 1000 + 10, 1, None, None)]
        wkw = Walk(mkw, ixw, pw, per_event=per_event)
        out = []
        for _kind, _tk, _sec, _ts in wkw.drive(evs):
            if _kind == 0 or _tk != "M" or out:
                continue
            tau = C - _sec
            if not (pinrun.TAU_MIN <= tau <= pinrun.TAU_MAX):
                continue
            bw = book_view(wkw.books["M"], _ts)
            if bw["age_ms"] is None or bw["age_ms"] > pinrun.MAX_BOOK_AGE_MS:
                continue
            w_, px_, n_, _f_ = decide(ixw, "BRTI", C, _sec, 50.0, 2, bw, 20)
            out.append((w_, px_, n_, _ts - S * 1000))
        return out
    _ev_buys = _walk_buys(True)
    _sec_buys = _walk_buys(False)
    ck(_ev_buys and _ev_buys[0][0] == "yes" and _ev_buys[0][1] == 0.97
       and _ev_buys[0][3] == 300,
       f"a 97c offer alive for 400 ms inside second S IS bought, at "
       f"S+300 ms ({_ev_buys[0] if _ev_buys else None})")
    ck(_sec_buys and _sec_buys[0][0] is None,
       f"and the SAME tape sampled once a second misses it entirely "
       f"({_sec_buys[0] if _sec_buys else None}) -- which is the 2026-09-12 "
       f"diagnosis in one line")

    # (iv) GATE AS OF: a planted `start` record changes what pinrun reads
    _saved = {k: getattr(pinrun, k) for k in GATE_KEYS if hasattr(pinrun, k)}
    _gp = os.path.join(tempfile.gettempdir(),
                       f"pinsim_selftest_gate_{os.getpid()}.jsonl")
    with open(_gp, "w", encoding="utf-8") as _f:
        _f.write(json.dumps({"kind": "other", "pin": 0.5}) + "\n")
        _f.write(json.dumps({"mode": "live", "pin": 0.98,
                             "price_ceiling": 0.988, "size": 33.0,
                             "measured_flip": 0.02, "tau_max": 20,
                             "t": "2026-09-08T06:20:46Z",
                             "kind": "start"}) + "\n")
    try:
        _g = read_gate(_gp)
        apply_gate(_g)
        ck(abs(pinrun.PIN - 0.98) < 1e-12
           and abs(pinrun.PRICE_CEILING - 0.988) < 1e-12
           and pinrun.SIZE == 33.0 and pinrun.TAU_MAX == 20,
           f"--gate-from puts back the gate a live run STARTED with "
           f"(PIN {pinrun.PIN}, ceiling {pinrun.PRICE_CEILING}, size "
           f"{pinrun.SIZE}, tau_max {pinrun.TAU_MAX})")
        ck("MEASURED_FLIP" not in _g,
           "and it does NOT claim to restore MEASURED_FLIP, which "
           "expected_value binds at definition in live too")
        ck(_g.get("_log") == os.path.basename(_gp),
           "and it names the log it came from, so a report can print it")
    finally:
        for _k, _v in _saved.items():
            setattr(pinrun, _k, _v)
        try:
            os.remove(_gp)
        except OSError:
            pass
    ck(abs(pinrun.PIN - 0.995) < 1e-12,
       f"and the live constants are put back exactly ({pinrun.PIN})")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ------------------------------------------------------------------ real data
def load_ticks(lo, hi):
    lo_h = time.strftime("%Y%m%dT%H", time.gmtime(lo - 3700))
    hi_h = time.strftime("%Y%m%dT%H", time.gmtime(hi + 60))
    out = defaultdict(list)
    for fp in sorted(glob.glob(os.path.join(DATA, "cfbenchmarks_value",
                                            "2026*.jsonl.gz"))):
        if not (lo_h <= os.path.basename(fp)[:11] <= hi_h):
            continue
        try:
            with gzip.open(fp, "rt") as fh:
                for line in fh:
                    if '"cfbenchmarks_value"' not in line:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                        dd = json.loads(m["data"])
                        s = int(dd["time"]) // 1000
                    except Exception:
                        continue
                    if lo - 3700 <= s <= hi + 60:
                        out[m["index_id"]].append((s, float(dd["value"])))
        except (EOFError, zlib.error, OSError):
            pass
    for k in out:
        out[k].sort()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--size", type=float, default=None,
                    help="override the profile's SIZE")
    ap.add_argument("--profile", default="default",
                    help="profile name in profiles/ or a path")
    ap.add_argument("--end", default=None,
                    help="last book hour to include, e.g. 20260910T05")
    ap.add_argument("--json", default=None,
                    help="also write the summary as JSON here (the tool reads it)")
    ap.add_argument("--hedge", default=None,
                    help="AMENDMENT 15 holdout: comma-separated belief "
                         "thresholds, e.g. 0.70,0.80,0.90. Replays the live "
                         "hedge pass through pinrun's own functions and prints "
                         "one row per threshold. Off by default.")
    ap.add_argument("--sweep", default=None,
                    help="PARAM=v1,v2,... run once per value in THIS process "
                         "so the tape cache serves every value")
    ap.add_argument("--stream", default=None,
                    help="START,END epoch seconds: print one JSON frame per "
                         "tape second (the replay player)")
    ap.add_argument("--coins", default=None,
                    help="comma-separated series to include in --stream")
    ap.add_argument("--gate-from", default=None,
                    help="a results/pinrun-live-*.jsonl whose `start` record "
                         "holds the gate that was ACTUALLY LIVE then. Applied "
                         "on top of the profile, so a historical window is "
                         "judged by the rule it was traded under.")
    ap.add_argument("--per-second", action="store_true",
                    help="decide once a second at the first event of the "
                         "second -- the sampling this file used until "
                         "2026-09-12. For scoring the rebuild against what it "
                         "replaced; never for a result.")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    profile = pinrules.load(a.profile)
    gate = read_gate(a.gate_from) if a.gate_from else None
    per_event = not a.per_second
    if a.stream:
        s0, s1 = (int(x) for x in a.stream.split(","))
        coins = set(a.coins.split(",")) if a.coins else None
        for fr in stream(profile, s0, s1, size=a.size, coins=coins):
            sys.stdout.write(json.dumps(fr, separators=(",", ":")) + "\n")
            sys.stdout.flush()
        return
    if a.sweep:
        name, vals = a.sweep.split("=", 1)
        typ = pinrules.PARAMS[name][0]
        results = []
        for v in vals.split(","):
            val = int(v) if typ == "int" else float(v)
            p2 = {k: x for k, x in profile.items() if not k.startswith("_")}
            p2 = json.loads(json.dumps(p2))
            p2["params"][name] = val
            bad = pinrules.validate(p2)
            if bad:
                results.append({"value": val, "error": bad})
                continue
            p2["_sha"] = pinrules.fingerprint(p2)
            print(f"\n  ===== {name} = {val} =====")
            s = run(p2, a.hours, a.end, size=a.size, log=print,
                    gate=gate, per_event=per_event)
            results.append({"value": val, "summary": s})
        if a.json:
            with open(a.json, "w", encoding="utf-8") as fh:
                json.dump(results, fh, indent=1)
            print(f"  sweep written to {a.json}")
        return
    _thrs = tuple(float(x) for x in a.hedge.split(",")) if a.hedge else None
    summary = run(profile, a.hours, a.end, size=a.size, log=print,
                  hedge_thrs=_thrs, gate=gate, per_event=per_event)
    if summary and a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=1)
        print(f"  summary written to {a.json}")


# ------------------------------------------------------------ the tape cache
# A goal search replays the same hours N times. Parsing an hour of deltas is
# the expensive part, so parsed hours are cached in-process -- capped, because
# the collector outranks this tool for RAM (CLAUDE.md resource protocol).
_HOUR_CACHE = {}
HOUR_CACHE_MAX = 12


def load_markets():
    mk = {}
    for v in json.load(open(FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] in pindata.SERIES_TO_INDEX and \
                    r.get("result") is not None:
                mk[r["ticker"]] = r
    return mk


def newest_settlement(mk):
    return max(float(r["close"]) for r in mk.values()) if mk else 0


def book_hours(hours, end=None):
    bfiles = sorted(glob.glob(os.path.join(
        DATA, "orderbook_delta", "2026*.jsonl.gz")))[:-1]
    if end:
        bfiles = [f for f in bfiles if os.path.basename(f)[:11] <= end]
    return [os.path.basename(f)[:11] for f in bfiles[-hours:]]


class DeltaStream:
    """A re-iterable, file-backed stream of (ts_ms, ticker, side, price, dq).

    Each __iter__ re-opens the gzip and yields in file order, so iterating
    twice gives identical results (the replay player relies on that) and
    nothing is held between iterations. `bad` counts deltas that failed to
    parse on the MOST RECENT iteration; read it after the loop, not before.
    """

    def __init__(self, path, mk):
        self.path = path
        self.mk = mk
        self.bad = 0

    def __iter__(self):
        self.bad = 0
        try:
            with gzip.open(self.path, "rt") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        m = d["msg"]
                    except Exception:
                        continue
                    tk = m.get("market_ticker")
                    ts = int(m.get("ts_ms") or 0)
                    if not ts:
                        continue
                    if tk in self.mk:
                        # VERBATIM from pindata's fixed reader. The tape says
                        # `price_dollars`; a first version read
                        # `price_dollars_fp`, every delta raised, the except
                        # swallowed it, and six settled hours "bought 0".
                        try:
                            yield (ts, tk, str(m.get("side", "")).lower(),
                                   float(m.get("price_dollars", m.get("price"))),
                                   float(m.get("delta_fp", m.get("delta")) or 0.0))
                        except Exception:
                            self.bad += 1
                    else:
                        yield (ts, None, None, None, None)      # a clock tick
        except (EOFError, zlib.error, OSError):
            return


class EventStream:
    """One book hour as ONE stream, in the exchange's own `seq` order.

    THIS IS THE FIX FOR results/RESULTS_replay.md. Until 2026-09-12 this file
    applied every `orderbook_snapshot` in the hour BEFORE any delta, stamped
    ts 0 (the reader looked for `ts_ms`, which a snapshot record does not
    carry). Snapshots arrive throughout the hour -- one as each market opens,
    and again on a resubscribe -- so a snapshot belonging to 02:31 was used to
    seed the book at 02:00 and then never allowed to overwrite anything.
    Scored against the price the live bot logged on 210 real fills, that book
    reproduced 69; the same deltas merged with the same snapshots in `seq`
    order and read at the decision millisecond reproduced 158
    (results/RESULTS_replay_rebuild.md). pinreplay.py, whose reconstruction
    was written separately, gets 68/207 and 156/207 on its own sample -- two
    implementations of the merge landing on the same number.

    Both channels carry a top-level `seq` from the SAME subscription (`sid` 4
    on this tape, on both channels), so the merge needs no clock estimate: a
    snapshot goes exactly where the exchange put it. Measured on 20260912T11:
    1,667,366 deltas with ZERO backward `seq` steps in file order, and 159
    snapshots whose `seq` values interleave the whole hour.

    Yields (ts_ms, kind, ticker, payload):

        kind 0  SNAPSHOT -- payload is the message. Its timestamp is its real
                receipt `_rx_ms`, NEVER 0, clamped down to the `ts_ms` of the
                delta it precedes when the collector's receipt trails the
                exchange's own stamp (median 17 ms), so the clock cannot run
                backwards inside the merge.
        kind 1  DELTA -- payload is (side, price, dq).
        ticker None -- a message on a market we do not track, kept only so the
                simulated clock advances. payload is None.

    STREAMING, like DeltaStream and for the same reason: an hour of deltas
    materialised as tuples is ~1 GB and OOM-killed three runs. Each __iter__
    re-opens the gzip; the only thing held is the hour's snapshot list, ~159
    records.

    order='snapfirst' reproduces the OLD behaviour (every snapshot first, at
    ts 0) and exists only so the rebuild can be scored against what it
    replaced. run() always uses 'seq'.

    KNOWN LIMIT -- A COLLECTOR RECONNECT RESTARTS `seq`, AND THIS DOES NOT
    SEGMENT ON IT. Measured on 20260911T12: at message 925,953 of 4,504,521
    the sequence drops from 13,803,396 to 3, and the hour's 181 snapshots
    then span seq 1 to 12,911,772 -- two numbering epochs in one list. A
    snapshot sent by the RESUBSCRIBE carries a low seq, sorts to the front,
    and is therefore applied near the start of the hour instead of at the
    reconnect. For a market that opened AFTER the reconnect that is harmless
    (its book is empty until its own deltas arrive); for a market that
    existed BEFORE it, it is the old snapshots-first bug for that one market.
    `seq_back` counts the resets and run() prints the total, so an affected
    hour is visible rather than silent: 2 of the 7 hours that hold a losing
    fill have exactly one. THE FIX is to place a pending snapshot when
    EITHER the delta's `seq` has passed it OR the delta's `_rx_ms` has, which
    needs no second pass; it is not done here because it would invalidate a
    72-hour holdout already running, and it is the first thing to do next.
    """

    def __init__(self, path, snaps, mk, order="seq"):
        self.path = path
        self.mk = mk
        self.order = order
        # (seq, rx_ms, ticker, msg), sorted on the exchange's sequence number
        self.snaps = sorted(((sq, rx, tk, m) for tk, m, sq, rx in snaps
                             if sq is not None), key=lambda e: e[0])
        self.noseq = [(tk, m, rx) for tk, m, sq, rx in snaps if sq is None]
        self.bad = 0
        self.seq_back = 0
        self.snaps_used = 0

    def __iter__(self):
        self.bad = 0
        self.seq_back = 0
        self.snaps_used = 0
        snaps = self.snaps
        i = 0
        if self.order == "snapfirst":
            for _sq, _rx, tk, m in snaps:
                self.snaps_used += 1
                yield (0, 0, tk, m)
            i = len(snaps)
        for tk, m, rx in self.noseq:      # a record without `seq` cannot be
            self.snaps_used += 1          # placed; its receipt is all there is
            yield (rx or 0, 0, tk, m)
        prev = None
        try:
            with gzip.open(self.path, "rt") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        m = d["msg"]
                    except Exception:
                        continue
                    ts = int(m.get("ts_ms") or 0)
                    if not ts:
                        continue
                    sq = d.get("seq")
                    if sq is not None:
                        if prev is not None and sq < prev:
                            self.seq_back += 1
                        prev = sq
                        while i < len(snaps) and snaps[i][0] <= sq:
                            _sq, rx, stk, sm = snaps[i]
                            i += 1
                            self.snaps_used += 1
                            yield ((rx if (rx and rx <= ts) else ts), 0,
                                   stk, sm)
                    tk = m.get("market_ticker")
                    if tk in self.mk:
                        try:
                            yield (ts, 1, tk,
                                   (str(m.get("side", "")).lower(),
                                    float(m.get("price_dollars",
                                                m.get("price"))),
                                    float(m.get("delta_fp",
                                                m.get("delta")) or 0.0)))
                        except Exception:
                            self.bad += 1
                    else:
                        yield (ts, 1, None, None)     # a clock tick
        except (EOFError, zlib.error, OSError):
            pass
        while i < len(snaps):                 # snapshots after the last delta
            _sq, rx, stk, sm = snaps[i]
            i += 1
            self.snaps_used += 1
            yield (rx, 0, stk, sm)


class Walk:
    """The event walk: books, the simulated clock, and the moments at which a
    decision is taken.

    Live, pinrun's trade loop reads whatever book it holds, ~20 times a
    second, and this product's book changes ~100 times a second. Until
    2026-09-12 this file decided ONCE PER SECOND, at the first event of the
    second, and that single choice is most of why the backtest could not
    reproduce our own trades: of 195 real fills the offer we hit was on the
    book at the start of the second for 76% and at the millisecond we actually
    decided for 100% (results/RESULTS_replay.md).

    So a decision point ("moment") is

      * EVERY event on a market we track, at that event's millisecond, and
      * a sweep of every tracked book at the first event of each new second,
        so a market whose own book is quiet is still re-checked as the index
        moves.

    `drive` is a GENERATOR of moments rather than a callback loop, so run()
    and the replay player can both consume it while yielding their own output.
    It yields (0, None, sec, ts) once per second BEFORE that second's sweep
    (live runs the hedge pass first), then (1, ticker, sec, ts) per moment.

    per_event=False restores the old once-a-second sampling and exists only so
    the two can be scored against each other.
    """

    def __init__(self, mk, idx, pend, per_event=True):
        self.mk = mk
        self.idx = idx
        self.pend = pend
        self.per_event = per_event
        self.books = {}
        self.bad = 0
        self.ts_back = 0
        self.events = 0
        self.moments = 0

    def drive(self, events):
        books = self.books
        last_sec = None
        for ts, kind, tk, payload in events:
            self.events += 1
            if tk is not None:
                bk = books.get(tk)
                if bk is None:
                    bk = books[tk] = pindata.Book()
                if kind == 0:
                    bk.snapshot(payload, ts)
                else:
                    try:
                        bk.delta(payload[0], payload[1], payload[2], ts)
                    except Exception:                          # noqa: BLE001
                        self.bad += 1
            sec = ts // 1000
            if last_sec is not None and sec < last_sec:
                # a snapshot's receipt can precede the delta it follows in
                # seq order; the simulated clock never runs backwards
                self.ts_back += 1
                sec = last_sec
            if sec != last_sec:
                last_sec = sec
                self.idx.feed_upto_ms(self.pend, ts)
                yield (0, None, sec, ts)
                for tkk in list(books):
                    self.moments += 1
                    yield (1, tkk, sec, ts)
            elif self.per_event and tk is not None:
                self.moments += 1
                yield (1, tk, sec, ts)


# ------------------------------------------------------------------ the gate
# The constants a live `start` record can put back. MEASURED_FLIP is NOT here:
# pinrun.expected_value(price, flip=MEASURED_FLIP) binds the default AT
# DEFINITION, so setting the module attribute cannot change the EV gate --
# and live has the same binding, so reproducing live means leaving it alone.
GATE_KEYS = ("PIN", "PRICE_CEILING", "EDGE_FLOOR", "EV_FLOOR", "SIZE",
             "TAU_MIN", "TAU_MAX", "MIN_FILL_FRAC", "MIN_LEVEL",
             "MAX_BOOK_AGE_MS", "MAX_INDEX_AGE_S", "SIGMA_STRESS",
             "SIGMA_WIN", "IMPROVE_BY", "DUMP_DISCOUNT", "DUMP_ENABLED",
             "MAX_PER_CLOSE", "MAX_PER_MARKET", "EV_IMPLIED_CEILING",
             "HEDGE_ENABLED", "HEDGE_BELIEF", "HEDGE_MAX_ASK",
             "HEDGE_MAX_TRIES", "HEDGE_PILOT_CONTRACTS")


def read_gate(path):
    """The gate a live run was STARTED with, from its own `start` record.

    A backtest run under today's constants cannot reproduce a trade taken
    under yesterday's: 85 of our 195 fills were taken at PIN 0.98 and today's
    0.995 refuses them as `undecided`. That is a gate change, not a replay
    defect, and the two must not be confused -- so the gate is replayable.
    """
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:                                  # noqa: BLE001
                continue
            if r.get("kind") == "start":
                g = {k: r[k.lower()] for k in GATE_KEYS
                     if r.get(k.lower()) is not None}
                g["_log"] = os.path.basename(path)
                g["_t"] = r.get("t")
                return g
    raise SystemExit(f"no `start` record in {path}")


def apply_gate(gate):
    """Set those constants on pinrun. Same mechanism as apply_profile: the
    decision code reads them as module attributes at call time."""
    for k, v in gate.items():
        if not k.startswith("_") and hasattr(pinrun, k):
            setattr(pinrun, k, v)
    return gate


def load_hour(stamp, mk):
    """Everything one book hour needs, parsed once: index ticks, snapshots,
    and the delta stream as (ts_ms, ticker, side, price, dq) tuples."""
    if stamp in _HOUR_CACHE:
        return _HOUR_CACHE[stamp]
    import calendar
    # UTC, explicitly. time.mktime() is LOCAL time and time.timezone is the
    # non-DST offset, so the hour once landed 3600 s off and 6,813 moments
    # skipped as no_fair with nothing else wrong.
    hstart = calendar.timegm(time.strptime(stamp, "%Y%m%dT%H"))
    ticks = load_ticks(int(hstart) - 400, int(hstart) + 3700)
    snaps = []
    sf = os.path.join(DATA, "orderbook_snapshot", f"{stamp}.jsonl.gz")
    if os.path.exists(sf):
        try:
            with gzip.open(sf, "rt") as f:
                for line in f:
                    if '"orderbook_snapshot"' not in line:
                        continue
                    try:
                        d = json.loads(line)
                        m = d["msg"]
                    except Exception:
                        continue
                    if m.get("market_ticker") in mk:
                        # `seq` PLACES IT and `_rx_ms` TIMES IT. This read
                        # `d.get("ts_ms") or 0` -- a top-level field that is
                        # on ZERO snapshot records -- so every snapshot in
                        # this project's history was stamped 0 and applied
                        # before the hour began. See EventStream.
                        snaps.append((m["market_ticker"], m, d.get("seq"),
                                      int(d.get("_rx_ms") or 0)))
        except (EOFError, zlib.error, OSError):
            pass
    # THE DELTA STREAM IS NOT MATERIALISED. A first version built a Python
    # list of one 5-tuple per delta message in the hour -- including a
    # placeholder for every message on markets we do not track, kept so the
    # replay clock advances -- and an hour of order-book deltas is millions
    # of messages. That list was ~1 GB per hour; with the 12-hour cache it
    # reached 3.3 GB after four hours and the OS killed the run (2026-09-12,
    # twice: once with the cache, once with eviction but still one hour
    # resident while the next was being parsed). The collector survived both
    # times. DeltaStream holds no data: it re-opens the file on every
    # iteration and yields the same tuples in the same order, so run() and
    # stream() consume it unchanged and the cache may keep it for free.
    bf = os.path.join(DATA, "orderbook_delta", f"{stamp}.jsonl.gz")
    deltas = DeltaStream(bf, mk)
    # `events` is the seq-ordered merge of BOTH channels and is what run() and
    # the replay player consume. `deltas` is kept, unchanged, because it is
    # another stage's input (research/pinentry.py iterates it directly) and
    # because neither stream holds any data, so offering both is free.
    hour = {"stamp": stamp, "ticks": ticks, "snaps": snaps,
            "deltas": deltas, "events": EventStream(bf, snaps, mk),
            "bad_deltas": 0}
    if len(_HOUR_CACHE) >= HOUR_CACHE_MAX:
        _HOUR_CACHE.pop(next(iter(_HOUR_CACHE)))
    _HOUR_CACHE[stamp] = hour
    return hour


def hedge_try_ask(hp, thr, bk, ts, belief):
    """Price the hedge from the book AT THIS INSTANT; True if it filled.

    Live, the hedge order is sent against whatever ask is on the book when the
    alarm fires and on each retry -- not against the ask at a second
    boundary. An ask can appear and be gone inside one second exactly as an
    entry can, so this is called per event, while the alarm, the belief and
    the retry COUNT stay per second, which is what HEDGE_MAX_TRIES means.
    """
    hb = book_view(bk, ts)
    opp = "no" if hp["w"] == "yes" else "yes"
    ask = hb.get(f"{opp}_ask")
    asz = hb.get(f"{opp}_ask_size") or 0.0
    if not ask or asz <= 0 or not pinrun.hedge_ask_ok(ask):
        return False
    hp["h"][thr] = {"filled": min(hp["n"], asz), "ask": ask,
                    "tau": hp["cs"] - (ts // 1000), "belief": belief,
                    "edge_c": pinrun.hedge_edge_c(belief, ask)}
    return True


def hedge_report(sim_open, thrs, say=print):
    """AMENDMENT 15 holdout table, one row per threshold, in the units that
    decide it: positions, alarms, false alarms and their cost, losers caught
    and cents recovered, and the net change to P&L with the hedge on.

    RECOVERY is (unhedged loss) - (locked loss) = (1 - ask) per contract on a
    position that went on to LOSE; a hedge on a WINNER costs (ask) - (what the
    win paid) ... no: on a winner the pair pays $1 and we paid px + ask, so the
    hedged result is (1 - px - ask) versus the unhedged win (1 - px), a cost
    of exactly `ask` per contract. Fees on the hedge leg are charged as live
    would be. Every number here is a CEILING on live -- the replayed book is
    delta-only (the known snapshot bug) and we always win the race for the
    ask in a replay.
    """
    from pincross import cp_interval
    P = list(sim_open.values())
    n_pos = len(P)
    n_lose = sum(1 for p in P if not p["won"])
    base = sum(p["pnl"] for p in P)
    say("\n  " + "=" * 100)
    say(f"  AMENDMENT 15 HOLDOUT -- {n_pos:,} simulated positions, "
        f"{n_lose} lost ({100.0 * n_lose / max(1, n_pos):.2f}%), unhedged P&L "
        f"${base:+.2f}")
    say("  every figure is a CEILING: delta-only book, and the replay always "
        "wins the race for the ask")
    say(f"  {'threshold':>10}{'alarms':>8}{'false':>7}{'  fa-cost $':>12}"
        f"{'caught':>8}{'of':>4}{'  filled':>9}{'  rec c/ct':>11}"
        f"{'  net dP&L $':>13}{'  hedged P&L $':>15}")
    for thr in thrs:
        alarms = [p for p in P if p["alarm_tau"][thr] is not None]
        fa = [p for p in alarms if p["won"]]
        caught = [p for p in alarms if not p["won"]]
        filled = [p for p in alarms if p["h"][thr] and p["h"][thr].get("filled", 0) > 0]
        fa_cost = 0.0
        rec = []
        d = 0.0
        for p in filled:
            h = p["h"][thr]
            fee = pinrun.billed_fee(h["ask"], h["filled"])
            if p["won"]:
                # pair pays $1 on the hedged part; we forgo (1-px) and pay ask
                cost = h["filled"] * h["ask"] + fee
                fa_cost += cost
                d -= cost
            else:
                # on the hedged contracts the loss shrinks from px to px+ask-1
                gain = h["filled"] * (1.0 - h["ask"]) - fee
                rec.append(100.0 * (1.0 - h["ask"]))
                d += gain
        lo, hi = cp_interval(len(fa), max(1, n_pos))
        say(f"  {thr:>10.2f}{len(alarms):>8}{len(fa):>7}{fa_cost:>12.2f}"
            f"{len(caught):>8}{n_lose:>4}{len(filled):>9}"
            f"{(sum(rec) / len(rec)) if rec else 0.0:>11.1f}"
            f"{d:>13.2f}{base + d:>15.2f}"
            f"   false-alarm rate {100.0 * len(fa) / max(1, n_pos):.2f}% "
            f"[{100 * lo:.2f}, {100 * hi:.2f}]")
    say("  'caught' = alarm fired on an eventual loser; 'filled' = an ask "
        "existed under $1 within HEDGE_MAX_TRIES seconds; 'rec' = cents of the "
        "loss recovered per hedged contract")
    # alarm timing on losers, so the live latency budget is visible
    for thr in thrs:
        taus = sorted((p["alarm_tau"][thr] for p in P
                       if not p["won"] and p["alarm_tau"][thr] is not None),
                      reverse=True)
        if taus:
            say(f"  thr {thr:.2f}: alarm fired on losers at tau {taus}")
    say("  " + "=" * 100)


def run(profile, hours, end=None, size=None, log=None, progress=None,
        hedge_thrs=None, gate=None, per_event=True):
    """Replay `hours` settled book hours (ending at `end`) under `profile`
    through pinrun's own decision code. Returns the summary dict the tool
    reads, or None if nothing could be decided.

    gate: a dict of pinrun constants (see read_gate) applied AFTER the
    profile, so a historical window is replayed under the gate that was
    actually live then rather than the one that is live today.

    per_event: decide after EVERY book event, which is what live does -- the
    trade loop reads the book it holds, not the book at a second boundary.
    False restores the once-a-second sampling this file used until 2026-09-12
    and exists only so the two can be scored against each other.

    hedge_thrs: AMENDMENT 15 holdout. A tuple of belief thresholds, e.g.
    (0.70, 0.80, 0.90). For every simulated buy, belief is recomputed each
    later second with pinrun.fair() -- the SAME function the live hedge pass
    calls -- and at each threshold the first second belief falls below it is
    the alarm; the opposite side's best ask in the replayed book at that
    second prices the hedge, gated by pinrun.hedge_ask_ok(). All thresholds
    are tracked in ONE tape pass. None (the default) changes nothing.
    """
    say = log or (lambda *a, **k: None)
    apply_profile(profile)
    if gate:
        apply_gate(gate)
    if size is not None:
        pinrun.SIZE = size
    size = pinrun.SIZE
    say(f"\n  profile {profile['name']} sha {profile['_sha']}: "
        f"{len(profile['rules'])} rules, worst case "
        f"{pinrules.worst_case(profile['params'])}")
    if gate:
        say(f"  GATE AS OF {gate.get('_log')} ({gate.get('_t')}): "
            + ", ".join(f"{k_}={gate[k_]}" for k_ in GATE_KEYS if k_ in gate))
        say("  of these the replayed DECISION reads PIN, PRICE_CEILING, "
            "EDGE_FLOOR, EV_FLOOR, SIZE, TAU_MIN/MAX, MIN_FILL_FRAC, "
            "MIN_LEVEL, MAX_BOOK_AGE_MS and SIGMA_STRESS/WIN; the hedge pass "
            "reads HEDGE_*. MAX_PER_CLOSE, MAX_ATTEMPTS_PER_CLOSE, "
            "MAX_INDEX_AGE_S and EV_IMPLIED_CEILING are printed but NOT "
            "enforced here -- live caps positions per close and the replay "
            "does not. MEASURED_FLIP is not re-applied at all: "
            "expected_value binds it at definition, in live too.")
    mk = load_markets()
    stamps = book_hours(hours, end)
    ns = newest_settlement(mk)
    say(f"  newest settlement on file: "
        f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(ns))} "
        f"-- book hours after it cannot resolve and count as nothing")
    say(f"\n  {len(mk):,} settled markets, {len(stamps)} book hours, "
        f"size {size:g}, gate {pinrun.PIN}, ceiling {pinrun.PRICE_CEILING}")
    say("  book: snapshots and deltas merged in the exchange's own `seq` "
        "order; decisions taken "
        + ("at EVERY book event (live-like)" if per_event
           else "ONCE A SECOND (the old sampling)"))

    bought, refused, rule_tally = [], [], {}
    sim_open = {}          # A15 holdout: ticker -> simulated position + hedge
    skips = defaultdict(int)
    skip_seen = set()
    bad_deltas = 0
    seq_back = 0
    ts_back = 0
    moments = 0
    decided = set()

    def _skip(reason, tkk):
        # COUNTED ONCE PER MARKET PER REASON. Event-driven evaluation visits a
        # market thousands of times before it decides, so a per-visit tally
        # would say "too_shallow 77,000" and mean nothing. CLAUDE.md: n is
        # markets or closes, never trades.
        if (tkk, reason) not in skip_seen:
            skip_seen.add((tkk, reason))
            skips[reason] += 1

    for hi, stamp in enumerate(stamps):
        hour = load_hour(stamp, mk)
        if not hour["ticks"]:
            continue
        idx = TapeIndex(sorted(hour["ticks"]))
        pend = {k: list(v) for k, v in hour["ticks"].items()}
        wk = Walk(mk, idx, pend, per_event=per_event)
        for kind, tkk, sec, ts in wk.drive(hour["events"]):
            # ---- AMENDMENT 15 holdout: the hedge pass, replayed -----------
            # Mirrors pinrun's live pass: one belief recompute per open
            # simulated position per second, through the same fair(),
            # hedge_should_fire() and hedge_ask_ok(). Runs BEFORE the entry
            # scan, as live does.
            if kind == 0:
                if not (hedge_thrs and sim_open):
                    continue
                for htk, hp in sim_open.items():
                    if sec >= hp["cs"] - 1:
                        continue
                    if all(hp["h"][t] is not None for t in hedge_thrs):
                        continue            # every threshold already resolved
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
                    hp["last_belief"] = belief
                    hbk = wk.books.get(htk)
                    for thr in hedge_thrs:
                        if hp["h"][thr] is not None:
                            continue
                        if not pinrun.hedge_should_fire(belief, thr):
                            continue
                        if hp["alarm_tau"][thr] is None:
                            hp["alarm_tau"][thr] = hp["cs"] - sec
                        hp["tries"][thr] = hp["tries"].get(thr, 0) + 1
                        if hbk is not None:
                            hedge_try_ask(hp, thr, hbk, ts, belief)
                        if hp["h"][thr] is None and \
                                hp["tries"][thr] > pinrun.HEDGE_MAX_TRIES:
                            hp["h"][thr] = {"filled": 0.0,
                                            "why": "no_ask_in_time"}
                continue
            # ---- end AMENDMENT 15 holdout pass ----------------------------
            bkk = wk.books[tkk]
            # the hedge's per-event retry: an ask that exists for 400 ms
            # inside a second is an ask, on the way out as on the way in
            if hedge_thrs:
                hp = sim_open.get(tkk)
                if hp is not None and sec < hp["cs"] - 1 and \
                        hp.get("last_belief") is not None:
                    for thr in hedge_thrs:
                        if hp["h"][thr] is None and \
                                hp["alarm_tau"][thr] is not None:
                            hedge_try_ask(hp, thr, bkk, ts,
                                          hp["last_belief"])
            r = mk.get(tkk)
            if r is None:
                continue
            # one decision per market: bought OR refused. A first version only
            # excluded bought markets, so a refused one was re-refused every
            # second and one market counted 16 times in a rule's tally.
            if tkk in decided:
                continue
            cs = int(float(r["close"]))
            tau = cs - sec
            if not (pinrun.TAU_MIN <= tau <= pinrun.TAU_MAX):
                continue
            iid = pindata.SERIES_TO_INDEX[r["series"]]
            if iid not in idx.ticks:
                continue
            moments += 1
            b = book_view(bkk, ts)
            if b["age_ms"] is None or b["age_ms"] > pinrun.MAX_BOOK_AGE_MS:
                _skip("stale_book", tkk)
                continue
            # SCHEDULES resolve on what is known BEFORE deciding: the model's
            # view and the offer in front of it.
            sg0 = idx.sigma(iid)
            f0 = pinrun.fair(idx, iid, cs, sec, float(r["strike"]),
                             (sg0 or 0) * pinrun.SIGMA_STRESS,
                             round_digits=pindata.ROUND_DIGITS.get(
                                 r["series"])) if sg0 else None
            if f0 is not None:
                side0 = "yes" if f0 >= 0.5 else "no"
                px0 = b.get(f"{side0}_ask")
                _, spot0, iage0 = idx.spot(iid)
                pre = record(f0, side0, px0 or 0.0, 0.0,
                             b.get(f"{side0}_ask_size") or 0.0,
                             tau, r["series"], sec, sg0, spot0,
                             b["age_ms"], iage0)
                resolve_for(profile, pre)
            w, px, n, fv = decide(
                idx, iid, cs, sec, float(r["strike"]),
                pindata.ROUND_DIGITS.get(r["series"]), b, pinrun.SIZE)
            if w is None:
                _skip(px, tkk)
                continue
            res = r["result"]
            yes = (str(res).lower() == "yes") if \
                isinstance(res, str) else float(res) >= 0.5
            won = (yes == (w == "yes"))
            # THE PROFILE'S RULES, on the same record live sees
            sg_ = idx.sigma(iid)
            _, spot_, iage_ = idx.spot(iid)
            rc = record(fv, w, px, n, b.get(f"{w}_ask_size"),
                        tau, r["series"], sec, sg_, spot_,
                        b["age_ms"], iage_)
            verdict, fired = pinrules.decide(profile, rc)
            pnl = (n * (1 - px) if won else -n * px) - \
                pinrun.billed_fee(px, n)
            for rid, act in fired:
                rule_tally.setdefault(rid, []).append((cs, act, won, pnl, px))
            decided.add(tkk)
            if verdict == "refuse":
                refused.append((tkk, w, px, n, tau, won, pnl, cs))
                continue
            bought.append((tkk, w, px, n, tau, won, pnl, cs))
            if hedge_thrs:
                # A15 holdout: hold this position open so the hedge pass can
                # watch its belief every later second
                sim_open[tkk] = {
                    "w": w, "px": px, "n": n, "cs": cs, "iid": iid,
                    "strike": float(r["strike"]),
                    "digits": pindata.ROUND_DIGITS.get(r["series"]),
                    "won": won, "pnl": pnl, "tau_in": tau,
                    "min_belief": 1.0, "last_belief": None,
                    "h": {t: None for t in hedge_thrs},
                    "alarm_tau": {t: None for t in hedge_thrs},
                    "tries": {}}
        bad_deltas += wk.bad + (getattr(hour["events"], "bad", 0) or 0)
        seq_back += getattr(hour["events"], "seq_back", 0) or 0
        ts_back += wk.ts_back
        say(f"    {stamp}  bought {len(bought):,}", flush=True)
        # MEMORY. _HOUR_CACHE (cap 12) exists for the replay player, which
        # scrubs back and forth over a few hours. A one-pass run visits each
        # hour once and never again, so caching it is pure waste: on
        # 2026-09-12 a 72-hour run reached 3.3 GB after FOUR hours (~800 MB
        # per hour of order-book deltas) and the OS killed it for low memory
        # while the collector -- which outranks every job here -- was live.
        # Collectors survived; the run did not. Evict the hour we just used.
        _HOUR_CACHE.pop(stamp, None)
        if progress:
            progress(hi + 1, len(stamps))

    say(f"  {moments:,} decision moments evaluated"
        + (f"; {seq_back:,} backward `seq` steps in the tape" if seq_back
           else "; seq monotone throughout")
        + (f"; {ts_back:,} events whose ts_ms precedes the second before "
           f"them -- the TAPE's own clock inversions, not the merge's "
           f"(12.7% of deltas carry a ts_ms already seen in seq order, "
           f"measured on 20260909T00: 595,337 of 4,692,864). The simulated "
           f"clock is held, never rewound" if ts_back else ""))
    if bad_deltas:
        say(f"  *** {bad_deltas:,} DELTAS FAILED TO PARSE -- the book is "
            f"incomplete and every number below is suspect ***")
    if not bought and not refused:
        say(f"  loaded nothing -- skips: {dict(skips)}")
        return None
    if hedge_thrs and sim_open:
        # DUMP FIRST, REPORT SECOND. On 2026-09-12 a 72-hour holdout finished
        # all 162 buys and then died in hedge_report on a NameError -- `say`
        # is a closure inside run() and the report was module-level. Ninety
        # minutes of compute lost at the print step, because the self-test
        # never called the report. The positions now hit disk before any
        # printing, so a reporting bug can never again eat the data, and the
        # table can be regenerated offline from this file.
        _dump = os.path.join(HERE, "..", "results", "pinsim_hedge_positions.json")
        try:
            with open(_dump, "w", encoding="utf-8") as _f:
                json.dump({"thrs": list(hedge_thrs),
                           "positions": {k: {kk: ({str(t): vv for t, vv in v.items()}
                                                  if isinstance(v, dict) else v)
                                             for kk, v in hp.items()}
                                         for k, hp in sim_open.items()}}, _f)
            say(f"  hedge positions written to {os.path.abspath(_dump)}")
        except Exception as _e:                                  # noqa: BLE001
            say(f"  *** could not write hedge positions: {_e}")
        hedge_report(sim_open, hedge_thrs, say=say)
    return report(bought, refused, rule_tally, skips, profile,
                  size=size, hours=len(stamps), log=say,
                  bad_deltas=bad_deltas, newest_settle=ns)


# ------------------------------------------------------------ the replay player
def stream(profile, start_sec, end_sec, size=None, coins=None):
    """THE SIMULATION AS A LIVE CHART. Yields one FRAME per tape second from
    `start_sec` to `end_sec`, through pinrun's own decision code under
    `profile`, driven by the SAME Walk that run() drives -- so what the
    operator watches IS the backtest, not a picture of it.

    A frame is emitted when the second it describes has FINISHED, because
    since 2026-09-12 a decision can be taken at any millisecond inside the
    second (see Walk) and a frame published at the first event of the second
    would show the book before the trade that happened in it. Each market's
    row therefore holds its state at the last event of that second it had.

    A frame: {"t": sec, "index": {coin: spot}, "markets": [per market inside
    its last 60 s: ticker, coin, close, tau, strike, mu, fair, margin_sd,
    yes_ask, no_ask, sway (the average the remaining prints must hit to land
    the settlement ON the strike), want, price, verdict, fired, bought],
    "tally": {fills, wins, losses, pnl, refused}, "events": [what settled or
    was bought this second]}. The operator asked for this to see, with his
    own eyes, that the backtest behaves like the live bot -- peace of mind is
    a legitimate deliverable.
    """
    apply_profile(profile)
    if size is not None:
        pinrun.SIZE = size
    mk = load_markets()
    if coins:
        mk = {k: v for k, v in mk.items() if v["series"] in coins}
    stamps = []
    s_ = start_sec - (start_sec % 3600)
    while s_ <= end_sec:
        stamps.append(time.strftime("%Y%m%dT%H", time.gmtime(s_)))
        s_ += 3600
    tally = {"fills": 0, "wins": 0, "losses": 0, "pnl": 0.0, "refused": 0}
    open_pos = {}          # ticker -> (want, price, n)
    decided = set()
    settled_done = set()
    for stamp in stamps:
        hour = load_hour(stamp, mk)
        if not hour["ticks"]:
            continue
        idx = TapeIndex(sorted(hour["ticks"]))
        pend = {k: list(v) for k, v in hour["ticks"].items()}
        wk = Walk(mk, idx, pend)
        frame = None
        rows = {}
        for kind, tkk, sec, ts in wk.drive(hour["events"]):
            if kind == 0:
                if frame is not None:
                    frame["markets"] = list(rows.values())
                    frame["tally"] = dict(tally)
                    yield frame
                    frame, rows = None, {}
                if sec < start_sec:
                    continue
                if sec > end_sec:
                    return
                frame = {"t": sec, "index": {}, "markets": [], "events": []}
                for iid in idx.ticks:
                    _, sp, _ = idx.spot(iid)
                    if sp is not None:
                        frame["index"][iid] = sp
                # settlements that landed this second
                for tk2, (w, px, n) in list(open_pos.items()):
                    cs = int(float(mk[tk2]["close"]))
                    if sec >= cs and tk2 not in settled_done:
                        res = mk[tk2]["result"]
                        yes = (str(res).lower() == "yes") \
                            if isinstance(res, str) else float(res) >= 0.5
                        won = yes == (w == "yes")
                        pnl = (n * (1 - px) if won else -n * px) - \
                            pinrun.billed_fee(px, n)
                        tally["fills"] += 1
                        tally["wins" if won else "losses"] += 1
                        tally["pnl"] = round(tally["pnl"] + pnl, 4)
                        settled_done.add(tk2)
                        open_pos.pop(tk2, None)
                        frame["events"].append({"kind": "settled",
                                                "ticker": tk2, "won": won,
                                                "pnl": round(pnl, 4)})
                continue
            if frame is None:
                continue
            bkk = wk.books[tkk]
            r = mk[tkk]
            cs = int(float(r["close"]))
            tau = cs - sec
            if not (0 < tau <= 60):
                continue
            iid = pindata.SERIES_TO_INDEX[r["series"]]
            if iid not in idx.ticks:
                continue
            b = book_view(bkk, ts)
            sg = idx.sigma(iid)
            dg = pindata.ROUND_DIGITS.get(r["series"])
            K = pinrun.eff_strike(float(r["strike"]), dg)
            part = idx.partial(iid, cs, sec)
            _, spot, iage = idx.spot(iid)
            row = {"ticker": tkk, "coin": r["series"], "close": cs,
                   "tau": tau, "strike": float(r["strike"]), "spot": spot,
                   "yes_ask": b.get("yes_ask"), "no_ask": b.get("no_ask"),
                   "yes_ask_size": b.get("yes_ask_size"),
                   "no_ask_size": b.get("no_ask_size")}
            prev = rows.get(tkk)
            if prev is not None and prev.get("bought"):
                row["bought"] = True       # keep the badge for the second
            rows[tkk] = row
            if part and sg and spot is not None:
                locked, rr = part
                mu = (locked + rr * spot) / pinrun.N_AVG
                row["mu"] = mu
                row["sway"] = ((pinrun.N_AVG * K - locked) / rr) \
                    if rr > 0 else None
                f = pinrun.fair(idx, iid, cs, sec, float(r["strike"]),
                                sg * pinrun.SIGMA_STRESS, round_digits=dg)
                if f is not None:
                    conf = f if f >= 0.5 else 1 - f
                    row["fair"] = round(f, 6)
                    row["conf"] = round(conf, 6)
                    row["margin_sd"] = round(_ND.inv_cdf(
                        min(max(conf, 1e-12), 1 - 1e-12)), 3)
                    if tkk not in decided and \
                            pinrun.TAU_MIN <= tau <= pinrun.TAU_MAX and \
                            b["age_ms"] is not None and \
                            b["age_ms"] <= pinrun.MAX_BOOK_AGE_MS:
                        side0 = "yes" if f >= 0.5 else "no"
                        pre = record(f, side0, b.get(f"{side0}_ask") or 0.0,
                                     0.0, b.get(f"{side0}_ask_size") or 0.0,
                                     tau, r["series"], sec, sg, spot,
                                     b["age_ms"], iage)
                        resolve_for(profile, pre)
                        w, px, n, fv = decide(idx, iid, cs, sec,
                                              float(r["strike"]), dg, b,
                                              pinrun.SIZE)
                        if w is None:
                            row["why_not"] = px
                        else:
                            rc = record(fv, w, px, n,
                                        b.get(f"{w}_ask_size"), tau,
                                        r["series"], sec, sg, spot,
                                        b["age_ms"], iage)
                            verdict, fired = pinrules.decide(profile, rc)
                            row.update(want=w, price=px, take_n=n,
                                       verdict=verdict,
                                       fired=[x[0] for x in fired])
                            decided.add(tkk)
                            if verdict == "refuse":
                                tally["refused"] += 1
                                frame["events"].append(
                                    {"kind": "refused", "ticker": tkk,
                                     "rules": [x[0] for x in fired],
                                     "price": px})
                            else:
                                open_pos[tkk] = (w, px, n)
                                row["bought"] = True
                                frame["events"].append(
                                    {"kind": "bought", "ticker": tkk,
                                     "want": w, "price": px, "n": n})
        if frame is not None:
            frame["markets"] = list(rows.values())
            frame["tally"] = dict(tally)
            yield frame
        _HOUR_CACHE.pop(stamp, None)


def _stats(rows):
    """fills / closes / wins / losses / P&L / mean price / loss-rate CI."""
    from pincross import cp_interval
    if not rows:
        return {"fills": 0, "closes": 0, "wins": 0, "losses": 0, "pnl": 0.0,
                "mean_price": None, "loss_rate": None, "ci": None}
    L = [x for x in rows if not x[5]]
    lo, hi = cp_interval(len(L), len(rows))
    return {"fills": len(rows), "closes": len(set(x[7] for x in rows)),
            "wins": len(rows) - len(L), "losses": len(L),
            "pnl": round(sum(x[6] for x in rows), 2),
            "mean_price": round(100 * sum(x[2] for x in rows) / len(rows), 2),
            "loss_rate": round(100 * len(L) / len(rows), 2),
            "ci": [round(100 * lo, 2), round(100 * hi, 2)]}


def _line(tag, s):
    if not s["fills"]:
        return f"  {tag:<34}{'--':>8}"
    return (f"  {tag:<34}{s['fills']:>6} fills {s['closes']:>5} closes "
            f"{s['wins']:>5}W {s['losses']:>3}L  {s['loss_rate']:>6.2f}% "
            f"[{s['ci'][0]:.2f}, {s['ci'][1]:.2f}]  ${s['pnl']:>+9.2f}  "
            f"{s['mean_price']:>6.2f}c")


def report(bought, refused, rule_tally, skips, profile, size, hours, log,
           bad_deltas=0, newest_settle=0):
    """FIT and HOLDOUT side by side, always. n as markets AND closes. Every
    rate with its interval. The 70%-fill pair. Per rule, the would-be outcome
    of everything it fired on, so a tracker and a refusal read the same."""
    print = log                          # every line below goes to the caller

    class _A:                            # the old arg-namespace shape
        pass
    a = _A()
    a.size, a.hours = size, hours
    allrows = bought + refused
    closes = sorted(set(x[7] for x in allrows))
    cut = closes[int(0.70 * len(closes))] if closes else 0
    fit = [x for x in bought if x[7] < cut]
    hold = [x for x in bought if x[7] >= cut]
    S = {"profile": profile["name"], "sha": profile["_sha"],
         "size": a.size, "hours": a.hours, "split_close": cut,
         "upper_bound": True, "live_fill_rate": LIVE_FILL_RATE,
         "bad_deltas": bad_deltas, "newest_settlement": newest_settle,
         "traded": {"all": _stats(bought), "fit": _stats(fit),
                    "holdout": _stats(hold)},
         "refused": _stats(refused), "skips": dict(skips), "rules": {}}
    print(f"\n  {'='*100}")
    print(f"  PROFILE {profile['name']} (sha {profile['_sha']}), size "
          f"{a.size:g}, {a.hours} book hours -- UPPER BOUND: every offer "
          f"assumed ours; live we fill ~{100*LIVE_FILL_RATE:.0f}%")
    print(f"  {'='*100}")
    print(_line("TRADED, all", S["traded"]["all"]))
    print(_line("  fit (first 70% of closes)", S["traded"]["fit"]))
    print(_line("  HOLDOUT (last 30%)", S["traded"]["holdout"]))
    pa = S["traded"]["all"]["pnl"]
    print(f"  at the {100*LIVE_FILL_RATE:.0f}% live fill rate: "
          f"${pa*LIVE_FILL_RATE:+,.2f}")
    print(_line("REFUSED by rules (would-be)", S["refused"]))
    print(f"\n  PER RULE -- what it fired on, and what would have happened")
    for r in profile["rules"]:
        rows = rule_tally.get(r["id"], [])
        conv = [(None, None, px, None, None, won, pnl, cs)
                for cs, act, won, pnl, px in rows]
        f_ = [x for x in conv if x[7] < cut]
        h_ = [x for x in conv if x[7] >= cut]
        S["rules"][r["id"]] = {"name": r.get("name", r["id"]),
                               "action": r["action"],
                               "all": _stats(conv), "fit": _stats(f_),
                               "holdout": _stats(h_)}
        print(_line(f"{r['id']} [{r['action']}] all", S["rules"][r["id"]]["all"]))
        print(_line(f"    fit", S["rules"][r["id"]]["fit"]))
        print(_line(f"    HOLDOUT", S["rules"][r["id"]]["holdout"]))
    print(f"\n  why other markets never fired (MARKETS, counted once per "
          f"market per reason): {dict(skips)}")
    L = [x for x in bought if not x[5]]
    for t, w, px, n, tau, won, pnl, cs in L[:20]:
        print(f"    LOSS {t[:28]:<29} {w:>3} {100*px:>5.1f}c tau {tau:>2} "
              f"${pnl:+.2f}")
    return S


if __name__ == "__main__":
    main()
