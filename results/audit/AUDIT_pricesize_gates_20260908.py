#!/usr/bin/env python3
"""AUDIT_pricesize_gates -- unbiased review of pinrun's PRICE and SIZE gates.

READ ONLY. Imports nothing that can send an order.

Reviews four gates as wired in research/pinrun.py (v9, sha d6826548c653):

  1. PIN            model confidence floor          (0.98)
  2. EDGE_FLOOR     model edge after fee            (0.003)  }  redundancy
     EV_FLOOR       measured-flip EV after fee      (0.003)  }  question
  3. PRICE_CEILING  hard price cap                  (0.988)
  4. size >= max(MIN_LEVEL, SIZE)  resting size at the touch

MEASURED ON results/pindata/rows.jsonl -- one row per (market, second) where a
resting offer actually existed on the model's favoured side.

RECONSTRUCTING THE MODEL FROM THE ROWS, and why it is exact:
  pindata stores  req = (60/r) * (K - mu),  so  mu - K = -req*r/60  exactly,
  and sd = sig*sqrt(var_factor(r,[1.0])) is the same expression pinrun.fair()
  uses. conf = Phi((mu-K)/sd) on the YES side, 1-that on the NO side. No
  lookahead: every input is at or before that second; `flip` is the outcome and
  is only ever used as an answer, never as an input.

CAVEAT STATED UP FRONT: rows.jsonl was built by pindata's partial(), which
scales the observed locked sum by want/got, and by an RMS-of-first-differences
sigma. pinrun uses CORRECTION 3 (locked window ends at the newest print held)
and a sample-sd sigma. So conf here is pindata's model, not bit-identical to
the live one. Everything below compares gate SETTINGS on one consistent model,
which is what a sweep needs; absolute confidences are the backtest's.
"""
import argparse
import json
import math
import os
import sys
from collections import defaultdict
from statistics import NormalDist

sys.path.insert(0, r"C:\kals-repo\research")
from engine import var_factor                              # noqa: E402

ND = NormalDist()
ROWS = r"C:\kals-repo\results\pindata\rows.jsonl"

# live constants, 2026-09-08 v9
PIN = 0.98
TAU_MIN, TAU_MAX = 3, 30
EDGE_FLOOR = 0.003
EV_FLOOR = 0.003
PRICE_CEILING = 0.988
MEASURED_FLIP = 0.0090
FLIP_UB = 0.0231           # exact one-sided 95% Clopper-Pearson upper bound
MIN_LEVEL = 1.0
SIZE = 5.0
MAX_PER_CLOSE = 2
IMPROVE_BY = 0.005


def billed_fee(p, n=1.0):
    return math.ceil(0.07 * p * (1 - p) * n * 10000.0) / 10000.0


def conf_of(row):
    """Model confidence ON THE SIDE WE WOULD BUY. None if unreconstructable."""
    r = row.get("r")
    sig = row.get("sig")
    if r is None or r < 1 or sig is None:
        return None
    mu_minus_K = -row["req"] * r / 60.0
    sd = sig * math.sqrt(var_factor(int(r), [1.0]))
    if sd <= 0:
        f = 1.0 if mu_minus_K >= 0 else 0.0
    else:
        f = ND.cdf(mu_minus_K / sd)
    return f if row["side_yes"] else (1.0 - f)


def net_edge(conf, price, size=SIZE):
    return conf - price - billed_fee(price, size) / size


def expected_value(price, flip=MEASURED_FLIP):
    # (1-f)(1-p) - f*p - fee  ==  (1-p) - f - fee
    return (1.0 - price) - flip - billed_fee(price, 1.0)


def breakeven_flip(price):
    """f at which EV(price) == 0, i.e. (1-p) - f - fee = 0."""
    return (1.0 - price) - billed_fee(price, 1.0)


# ---------------------------------------------------------------------------
def walk(rows, pin=PIN, edge_floor=EDGE_FLOOR, ev_floor=EV_FLOOR,
         ceiling=PRICE_CEILING, size_req=SIZE, flip=MEASURED_FLIP,
         max_per_close=MAX_PER_CLOSE, tau_lo=TAU_MIN, tau_hi=TAU_MAX,
         min_level=MIN_LEVEL, use_ceiling=True, use_edge=True, use_ev=True):
    """Replay pinrun's decision order over rows grouped by CLOSE.

    Refusal counters are FIRST-BINDING, in pinrun's own order.
    """
    byclose = defaultdict(list)
    for r in rows:
        byclose[r["close"]].append(r)
    buys = []
    ref = defaultdict(int)
    fired_closes = set()
    for cs in sorted(byclose):
        rs = sorted(byclose[cs], key=lambda x: (x["sec"], x["tk"]))
        n = 0
        best = None
        for r in rs:
            if not (tau_lo <= r["tau"] <= tau_hi):
                ref["tau"] += 1
                continue
            if n >= max_per_close:
                ref["per_close_cap"] += 1
                continue
            c = r.get("_conf")
            if c is None:
                ref["no_model"] += 1
                continue
            if not (c >= pin):
                ref["pin"] += 1
                continue
            if r["size"] < max(min_level, size_req):
                ref["size"] += 1
                continue
            e = net_edge(c, r["price"], size_req)
            if use_edge and e < edge_floor:
                ref["edge"] += 1
                continue
            if best is not None and r["price"] >= best - IMPROVE_BY:
                ref["improve"] += 1
                continue
            if use_ceiling and r["price"] > ceiling:
                ref["ceiling"] += 1
                continue
            ev = expected_value(r["price"], flip)
            if use_ev and ev < ev_floor:
                ref["ev"] += 1
                continue
            n += 1
            best = r["price"] if best is None else min(best, r["price"])
            fired_closes.add(cs)
            buys.append({"close": cs, "tk": r["tk"], "sr": r["sr"],
                         "price": r["price"], "conf": c, "tau": r["tau"],
                         "size": r["size"], "edge": e, "ev": ev,
                         "flip": bool(r["flip"])})
    return {"buys": buys, "ref": dict(ref), "closes": len(fired_closes),
            "closes_available": len(byclose)}


def score(buys, size_req=SIZE, flip=MEASURED_FLIP, stress=FLIP_UB):
    """Per-CONTRACT and per-CLOSE economics. n is reported as CLOSES."""
    if not buys:
        return {"buys": 0, "closes": 0}
    closes = sorted({b["close"] for b in buys})
    ev_c = [expected_value(b["price"], flip) for b in buys]
    ev_s = [expected_value(b["price"], stress) for b in buys]
    real = [((1.0 - b["price"]) if not b["flip"] else (-b["price"]))
            - billed_fee(b["price"], 1.0) for b in buys]
    be = [breakeven_flip(b["price"]) for b in buys]
    per_close_ev = defaultdict(float)
    for b, v in zip(buys, ev_c):
        per_close_ev[b["close"]] += v * size_req
    return {
        "buys": len(buys), "closes": len(closes),
        "buys_per_close": len(buys) / len(closes),
        "avg_price": sum(b["price"] for b in buys) / len(buys),
        "ev_c_per_contract": 100.0 * sum(ev_c) / len(ev_c),
        "ev_c_per_close": 100.0 * sum(per_close_ev.values()) / len(closes),
        "ev_c_stress_per_contract": 100.0 * sum(ev_s) / len(ev_s),
        "ev_total_dollars": size_req * sum(ev_c),
        "realised_c_per_contract": 100.0 * sum(real) / len(real),
        "flips": sum(1 for b in buys if b["flip"]),
        "blended_breakeven_flip": sum(be) / len(be),
        "headroom_vs_ub": (sum(be) / len(be)) / FLIP_UB,
    }


# ---------------------------------------------------------------------------
def mkrow(close, sec, tau, price, size, conf_target, flip=False, tk="T"):
    """A synthetic row whose reconstructed conf is exactly conf_target."""
    rr, sg = 10, 0.5
    s = sg * math.sqrt(var_factor(rr, [1.0]))
    z = ND.inv_cdf(min(max(conf_target, 1e-12), 1 - 1e-12))
    return {"close": close, "sec": sec, "tau": tau, "r": rr, "sig": sg,
            "req": -(z * s) * 60.0 / rr, "price": price, "size": size,
            "side_yes": True, "flip": flip, "tk": tk, "sr": "KXTEST"}


def selftest():
    print("SELF-TEST -- AUDIT_pricesize_gates")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # --- the algebra the whole audit rests on ---
    long_form = (1 - 0.0090) * (1 - 0.95) - 0.0090 * 0.95 - billed_fee(0.95)
    ck(abs(expected_value(0.95) - long_form) < 1e-15,
       f"EV identity (1-p)-f-fee equals the long form ({100*long_form:+.4f}c)")
    ck(abs(breakeven_flip(0.9386) - 0.0573) < 1e-4,
       f"blended break-even at the published 93.86c avg is "
       f"{100*breakeven_flip(0.9386):.2f}% -- reproduces HANDOFF's 5.75%")

    # --- conf reconstruction: plant a KNOWN fair value ---
    r_, sig_ = 10, 0.5
    sd = sig_ * math.sqrt(var_factor(r_, [1.0]))
    row = {"r": r_, "sig": sig_, "req": -(2.0 * sd) * 60.0 / r_,
           "side_yes": True}
    ck(abs(conf_of(row) - ND.cdf(2.0)) < 1e-12,
       f"planted z=2 recovers conf {conf_of(row):.6f} "
       f"(Phi(2)={ND.cdf(2.0):.6f})")
    ck(abs(conf_of(dict(row, side_yes=False)) - (1 - ND.cdf(2.0))) < 1e-12,
       "the NO side reports 1-Phi(z)")
    ck(conf_of({"r": 5, "sig": 0.0, "req": -1.0, "side_yes": True}) == 1.0,
       "a dead-flat index (sigma 0) with mu above K is certainty, not a crash")

    # --- PLANTED WORLD: exactly 2 rows must survive the full live rule ---
    planted = [
        mkrow(1000, 1, 20, 0.950, 100, 0.9995),          # PASSES
        mkrow(1000, 2, 20, 0.949, 100, 0.9995),          # improve < 0.5c
        mkrow(1000, 3, 20, 0.940, 100, 0.9995),          # PASSES (2nd buy)
        mkrow(1000, 4, 20, 0.900, 100, 0.9995),          # per-close cap
        mkrow(2000, 1, 40, 0.950, 100, 0.9995),          # tau
        mkrow(2000, 2, 20, 0.950, 100, 0.9000),          # pin
        mkrow(2000, 3, 20, 0.950, 3, 0.9995),            # size (3 < 5)
        # EDGE binds, EV does NOT: model only 98.0% sure at 97.8c
        mkrow(2000, 4, 20, 0.978, 100, 0.9800),          # edge
        # EV binds, EDGE does NOT: model 99.99% sure but the price is 98.75c
        mkrow(2000, 5, 20, 0.9875, 100, 0.9999),         # ev
        mkrow(2000, 6, 20, 0.9885, 100, 0.9999),         # ceiling
    ]
    for p in planted:
        p["_conf"] = conf_of(p)
    out = walk(planted)
    ck(len(out["buys"]) == 2 and out["closes"] == 1,
       f"planted world: exactly 2 buys on 1 close ({len(out['buys'])} buys, "
       f"{out['closes']} closes)")
    ck([round(b["price"], 3) for b in out["buys"]] == [0.950, 0.940],
       f"and they are the 95.0c and 94.0c rows "
       f"({[b['price'] for b in out['buys']]})")
    for g, want in (("tau", 1), ("pin", 1), ("size", 1), ("edge", 1),
                    ("improve", 1), ("per_close_cap", 1), ("ceiling", 1),
                    ("ev", 1)):
        ck(out["ref"].get(g, 0) == want,
           f"gate {g!r} refused exactly {want} planted row "
           f"({out['ref'].get(g, 0)})")
    off = walk(planted, use_ceiling=False)
    ck(off["ref"].get("ev", 0) == 2 and len(off["buys"]) == 2,
       f"with the ceiling REMOVED the 98.85c row is refused by the EV gate "
       f"instead ({off['ref'].get('ev', 0)} ev refusals) and nothing extra "
       f"trades ({len(off['buys'])} buys)")
    # and the converse: the two floors are NOT redundant, each binds alone
    no_edge = walk(planted, use_edge=False)
    ck(len(no_edge["buys"]) == 3,
       f"removing EDGE_FLOOR lets the 97.8c row through -- EV does not catch "
       f"it ({len(no_edge['buys'])} buys vs 2)")
    no_ev = walk(planted, use_ev=False)
    ck(len(no_ev["buys"]) == 3,
       f"removing EV_FLOOR lets the 98.75c row through -- EDGE does not catch "
       f"it ({len(no_ev['buys'])} buys vs 2)")

    # --- NULL WORLD: nothing planted, nothing found ---
    null = [mkrow(3000, i, 20, 0.9995, 100, 0.9995) for i in range(50)]
    for p in null:
        p["_conf"] = conf_of(p)
    nout = walk(null)
    ck(len(nout["buys"]) == 0 and nout["closes"] == 0,
       f"null world (every price 99.95c, no edge anywhere): 0 buys "
       f"({len(nout['buys'])})")
    ck(score(nout["buys"])["buys"] == 0, "and score() reports nothing")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


def load(path=ROWS, limit=None):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            d["_conf"] = conf_of(d)
            rows.append(d)
            if limit and len(rows) >= limit:
                break
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")
    print("\nloading rows ...")
    rows = load()
    print(f"  {len(rows):,} rows, "
          f"{len({r['close'] for r in rows}):,} distinct closes")
