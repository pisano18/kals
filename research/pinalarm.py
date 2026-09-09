#!/usr/bin/env python3
# VERSION: 2026-09-09-pa1
"""pinalarm.py -- once we are ALREADY in a position, does the trajectory of our
own numbers warn us in time to act?

THE OPERATOR'S QUESTION, VERBATIM: "...or also in the way your deviation was
moving to alert you to purchase a bet on the other side to lessen the blow?"

THE FACT THAT PROVOKED IT. In the first live loss (KXNEAR15M, close
2026-09-09 00:45Z) our model got MORE confident while the market got LESS:

    tau 22   NO @ 96.2c   model p(lose) 2.09%   market p(lose) ~3.8%
    tau 21   NO @ 95.6c   model p(lose) 1.42%   market p(lose) ~4.4%
    tau 17   NO @ 73.0c   model p(lose) 0.23%   market p(lose) ~27.0%

Model and market moved in OPPOSITE directions. That divergence, and the speed
of the price collapse that produced it, are the two candidate alarms this file
tests. A third is the trajectory of the required move itself.

WHAT AN ALARM HAS TO BEAT, AND IT IS A HIGH BAR.
An alarm is only worth anything if it fires while there is still time to act.
Our order round trip is ~100 ms plus a decision loop, so one second of warning
is nothing. Every rule here is therefore scored on THREE numbers and never on
accuracy alone:

  1. LEAD TIME -- seconds between the alarm and the moment the position was
     actually lost. "Lost" is marked by the CROSS: the first second at which
     the projected settlement mean moves to the wrong side of the strike.
     An alarm after the cross is worthless however accurate.
  2. FALSE ALARMS ON WINNERS -- what share of positions that were going to win
     anyway does it fire on.
  3. PROFIT DESTROYED -- what those false alarms cost, as a share of the profit
     the un-alarmed strategy makes. IDEAS_LOG #31 killed the model-confidence
     trigger at 5% on exactly this number: 26.5%.

POPULATION. The live window (tau 3-30) contains ZERO flips, so it can only ever
measure an alarm's COST. Every discrimination number here comes from the WIDE
window (tau up to 200), which is the only place losses exist, and every table
says which window it came from. This is the same split pinhedge.py used.

WHAT IS DIFFERENT FROM pinhedge.py, AND WHY IT MIGHT MATTER. pinhedge triggered
on the MODEL's own p(lose). The model is the thing that was wrong tonight -- it
was at 0.23% eleven seconds before the position was lost -- so a trigger that
reads the MARKET (price, and price velocity) instead of the model can in
principle fire earlier and on different evidence. That is the whole hypothesis.

NO LOOKAHEAD. Every feature is built from data at or before its own second.
The outcome is attached separately and is never an input.
"""
import argparse
import json
import math
import os
import random
import sys
from collections import defaultdict
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor                                # noqa: E402

ND = NormalDist()
NL = chr(10)

MEASURED_FLIP = 0.0090     # the live EV gate's flip rate (3 in 333)
EV_FLOOR = 0.003           # live rule
CEILING = 0.988            # live rule
PIN_P = 0.02               # live rule: model p_flip ceiling
LOOKBACK = 3               # seconds every velocity is measured over
ACT_SECONDS = 2            # an alarm must beat the cross by this to be usable
HEDGE_SIZE = 20.0          # live position size, for the depth question


def fee(p, n=1.0):
    return math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000


def ev(p, flip=MEASURED_FLIP):
    return (1 - flip) * (1 - p) - flip * p - fee(p)


def sd_of(r, sig):
    """sd of (settle - strike) with r prints still unpublished."""
    r = int(r)
    if r < 1:
        return 0.0
    s = float(sig or 0.0)
    if s <= 0:
        return 0.0
    return s * math.sqrt(var_factor(r, [1.0])) * (60.0 / r)


def p_lose(cushion, sd):
    """Model probability the side with this cushion LOSES."""
    if sd <= 0:
        return 0.0 if cushion > 0 else 1.0
    return 1.0 - ND.cdf(cushion / sd)


# ---------------------------------------------------------------------------
def feat(row, side_yes):
    """Every alarm input for ONE second, seen from a position on `side_yes`.

    rows.jsonl records the ask on the MODEL-FAVOURED side, and the favoured
    side changes as the index moves, so the first job is always to re-express
    the row from OUR side. On a Kalshi binary bid_A = 1 - ask_B, so:

        our side is the favoured one     ask = price          bid = price - spread
        the model has switched           bid = 1 - price      ask = 1 - (price - spread)

    That is the same derivation pinhedge.py uses, and getting it wrong there
    made hedges look cheaper the longer you waited.
    """
    sp = row.get("spread")
    sp = None if sp is None else float(sp)
    px = float(row["price"])
    same = bool(row["side_yes"]) == bool(side_yes)
    if same:
        ask = px
        bid = (px - sp) if sp is not None else None
    else:
        if sp is None:
            return None                      # cannot re-express: no spread
        bid = 1.0 - px
        ask = 1.0 - (px - sp)
    mid = None if bid is None else 0.5 * (ask + bid)

    cush = float(row["req"]) if not side_yes else -float(row["req"])
    sd = sd_of(row["r"], row.get("sig"))
    z = (cush / sd) if sd > 0 else (float("inf") if cush > 0
                                    else float("-inf"))
    mpf = p_lose(cush, sd)                   # model p(OUR side loses)
    kpf = None if mid is None else (1.0 - mid)   # market p(our side loses)
    return {
        "sec": int(row["sec"]), "tau": int(row["tau"]),
        "ask": ask, "bid": bid, "mid": mid,
        "model_pf": mpf, "mkt_pf": kpf,
        "div": None if kpf is None else (kpf - mpf),
        "cush": cush, "sd": sd, "z": z,
        "hedge_ask": None if bid is None else (1.0 - bid),
        "hedge_dep": float(row["dep_y"] if side_yes else row["dep_n"]),
        # rows.jsonl's `size` is the resting size at the favoured side's touch,
        # i.e. exactly the size available to BUY the favoured side. Once the
        # model has switched, the favoured side IS the side we would hedge
        # into, so `size` is the true touch depth for the hedge. While the
        # model still favours us it is not, and we only have top-3 depth.
        "touch": (float(row.get("size") or 0.0)
                  if bool(row["side_yes"]) != bool(side_yes)
                  else None),
        "flip": bool(row["flip"]),
    }


def deriv(fs, i, key, lookback=LOOKBACK, sign=1.0):
    """Change in fs[j][key] per second, over roughly `lookback` seconds.

    Rows are irregular -- pindata emits a row only when the book moved AND
    somebody was offering -- so the window is [sec-2*lookback, sec-1] and the
    reference is whichever row sits closest to sec-lookback. Returns None when
    the window is empty, rather than silently comparing across a 40-second gap.
    """
    v = fs[i].get(key)
    if v is None:
        return None
    s = fs[i]["sec"]
    lo, hi = s - 2 * lookback, s - 1
    best = None
    for j in range(i - 1, -1, -1):
        sj = fs[j]["sec"]
        if sj < lo:
            break
        if sj > hi or fs[j].get(key) is None:
            continue
        d = abs(sj - (s - lookback))
        if best is None or d < best[0]:
            best = (d, j)
    if best is None:
        return None
    j = best[1]
    dt = s - fs[j]["sec"]
    if dt <= 0:
        return None
    return sign * (v - fs[j][key]) / float(dt)


def enrich(fs):
    """Attach the three velocities. pvel is DECLINE-positive: a price falling
    1c per second scores +1.0, because falling is the direction that worries us.
    """
    for i in range(len(fs)):
        fs[i]["pvel"] = deriv(fs, i, "ask", sign=-100.0)     # cents/s of fall
        fs[i]["dvel"] = deriv(fs, i, "div", sign=1.0)        # prob/s widening
        zz = fs[i]["z"]
        fs[i]["zvel"] = (deriv(fs, i, "z", sign=1.0)
                         if (zz == zz and abs(zz) != float("inf")) else None)
    return fs


# ---------------------------------------------------------------------------
def build_entries(rows, tau_lo, tau_hi, pin_p=PIN_P, ceiling=CEILING,
                  ev_floor=EV_FLOOR):
    """One position per (market, close): the FIRST second that clears the live
    rule. The live rule buys up to three times; the first buy is the one the
    operator asked about, and it is the one that cannot be explained by the
    scale-in rule."""
    bym = defaultdict(list)
    for r in rows:
        bym[(r["tk"], r["close"])].append(r)
    out = []
    for key, seq in bym.items():
        seq.sort(key=lambda x: -int(x["tau"]))
        eidx = None
        for i, x in enumerate(seq):
            t = int(x["tau"])
            if not (tau_lo <= t <= tau_hi):
                continue
            sd = sd_of(x["r"], x.get("sig"))
            pf = p_lose(abs(float(x["req"])), sd)   # favoured side's p(lose)
            if pf > pin_p:
                continue
            p = float(x["price"])
            if p > ceiling or ev(p) < ev_floor:
                continue
            eidx = i
            break
        if eidx is None:
            continue
        e = seq[eidx]
        S = bool(e["side_yes"])
        fs = [f for f in (feat(x, S) for x in seq) if f is not None]
        enrich(fs)
        pre = [f for f in fs if f["tau"] > int(e["tau"])]
        post = [f for f in fs if f["tau"] < int(e["tau"])]
        at = None
        for f in fs:
            if f["tau"] == int(e["tau"]):
                at = f
                break
        if at is None:
            continue
        # the CROSS: first post-entry second whose projected mean sits on the
        # wrong side of the strike. This is the marker "the position is lost".
        cross = None
        for f in post:
            if f["cush"] <= 0:
                cross = f["tau"]
                break
        out.append({
            "tk": e["tk"], "sr": e["sr"], "close": int(e["close"]),
            "tau": int(e["tau"]), "side_yes": S, "price": float(e["price"]),
            "flip": bool(e["flip"]), "at": at, "pre": pre, "post": post,
            "cross": cross, "n_post": len(post),
        })
    return out


# ---------------------------------------------------------------------------
# alarm rules. Each is (label, family, threshold, predicate on a feature dict).
def rules():
    R = []
    for t in (0.02, 0.05, 0.10, 0.20, 0.35):
        R.append((f"DIVERGENCE  mkt-model >= {100*t:.0f}pp", "div", t,
                  (lambda t_: (lambda f: f["div"] is not None
                               and f["div"] >= t_))(t)))
    for t in (0.01, 0.02, 0.05, 0.10):
        R.append((f"DIV VELOCITY  >= {100*t:.0f}pp/s", "dvel", t,
                  (lambda t_: (lambda f: f["dvel"] is not None
                               and f["dvel"] >= t_))(t)))
    for t in (0.25, 0.5, 1.0, 2.0, 4.0, 8.0):
        R.append((f"PRICE VELOCITY  falling >= {t:g}c/s", "pvel", t,
                  (lambda t_: (lambda f: f["pvel"] is not None
                               and f["pvel"] >= t_))(t)))
    for t in (0.05, 0.10, 0.25, 0.50):
        R.append((f"CUSHION SHRINKING  <= -{t:g} sigma/s", "zvel", t,
                  (lambda t_: (lambda f: f["zvel"] is not None
                               and f["zvel"] <= -t_))(t)))
    for t in (0.05, 0.50, 0.90):
        R.append((f"MODEL p(lose) >= {100*t:.0f}%  [the rejected trigger]",
                  "model", t,
                  (lambda t_: (lambda f: f["model_pf"] >= t_))(t)))
    # COMBINATIONS. The market-only triggers fire early and often; the
    # model-only trigger fires late and almost never. Requiring both asks
    # whether an early warning can be made specific enough to be affordable.
    R.append(("COMBO  falling >= 2c/s AND model p(lose) >= 20%", "combo", 1.0,
              lambda f: (f["pvel"] is not None and f["pvel"] >= 2.0
                         and f["model_pf"] >= 0.20)))
    R.append(("COMBO  falling >= 1c/s AND divergence >= 20pp", "combo", 2.0,
              lambda f: (f["pvel"] is not None and f["pvel"] >= 1.0
                         and f["div"] is not None and f["div"] >= 0.20)))
    return R


def first_fire(entry, pred):
    for f in entry["post"]:
        if pred(f):
            return f
    return None


def score(entries, pred, size=HEDGE_SIZE, require_depth=False):
    """Everything an alarm has to answer, in one pass."""
    per = []
    for e in entries:
        f = first_fire(e, pred)
        fired = f is not None
        usable = False
        lead = None
        if fired and e["cross"] is not None:
            lead = f["tau"] - e["cross"]
            usable = lead >= ACT_SECONDS
        elif fired:
            usable = True          # no cross seen: the alarm has room by
            lead = None            # construction, but lead is unmeasurable
        hp = None
        deep = None
        touch = None
        if fired and f["hedge_ask"] is not None and 0.0 < f["hedge_ask"] < 1.0:
            hp = f["hedge_ask"]
            deep = f["hedge_dep"] >= size
            touch = f.get("touch")
        base = (1.0 - e["price"]) if not e["flip"] else -e["price"]
        base -= fee(e["price"])
        if hp is not None and (deep or not require_depth):
            hedged = 1.0 - e["price"] - hp - fee(e["price"]) - fee(hp)
        else:
            hedged = None
        per.append({"close": e["close"], "flip": e["flip"], "fired": fired,
                    "usable": usable, "lead": lead, "tau_fire":
                    (f["tau"] if fired else None), "hp": hp, "deep": deep,
                    "touch": touch, "base": base, "hedged": hedged,
                    "tk": e["tk"], "entry_tau": e["tau"],
                    "entry_price": e["price"], "cross": e["cross"]})
    return per


def agg(per):
    L = [p for p in per if p["flip"]]
    W = [p for p in per if not p["flip"]]
    def rate(xs, k):
        return (sum(1 for x in xs if x[k]) / len(xs)) if xs else float("nan")
    leads = sorted(p["lead"] for p in L if p["fired"] and p["lead"] is not None)
    base_w = sum(p["base"] for p in W)
    dest = 0.0
    net = 0.0
    for p in per:
        u = p["base"]
        h = p["hedged"]
        net += (h if h is not None else u)
        if (not p["flip"]) and h is not None:
            dest += (u - h)
    return {
        "n": len(per), "nL": len(L), "nW": len(W),
        "closes": len({p["close"] for p in per}),
        "closesL": len({p["close"] for p in L}),
        "catch": rate(L, "fired"), "catch_use": rate(L, "usable"),
        "fa": rate(W, "fired"),
        "lead_med": (leads[len(leads) // 2] if leads else float("nan")),
        "lead_n": len(leads),
        "destroyed": (dest / base_w) if base_w > 0 else float("nan"),
        "net": net, "base": sum(p["base"] for p in per),
        "deep": (sum(1 for p in L if p["fired"] and p["deep"]) /
                 max(1, sum(1 for p in L if p["fired"]
                            and p["deep"] is not None))),
        "hp_L": med([p["hp"] for p in L if p["hp"] is not None]),
        "tau_L": med([p["tau_fire"] for p in L if p["fired"]]),
        "lead2": (sum(1 for p in L if p["fired"] and p["lead"] is not None
                      and p["lead"] >= 2) / len(L)) if L else float("nan"),
        "lead5": (sum(1 for p in L if p["fired"] and p["lead"] is not None
                      and p["lead"] >= 5) / len(L)) if L else float("nan"),
        "touch_L": med([p["touch"] for p in L if p["touch"] is not None]),
        "touch_n": sum(1 for p in L if p["touch"] is not None),
    }


def boot(per, stat, B=1500, seed=11):
    """Resample CLOSES with replacement -- all coins share a close and are
    ~0.8 correlated, so the close is the independent unit."""
    rnd = random.Random(seed)
    byc = defaultdict(list)
    for p in per:
        byc[p["close"]].append(p)
    keys = list(byc)
    if len(keys) < 2:
        return (float("nan"), float("nan"))
    outs = []
    for _ in range(B):
        s = []
        for _ in range(len(keys)):
            s.extend(byc[keys[rnd.randrange(len(keys))]])
        v = stat(s)
        if v == v:
            outs.append(v)
    if len(outs) < 20:
        return (float("nan"), float("nan"))
    outs.sort()
    return (outs[int(0.025 * len(outs))], outs[int(0.975 * len(outs))])


def d_fire(xs):
    """Does the alarm fire more often on losers than on winners AT ALL?

    This is the apples-to-apples discrimination statistic, and it is the one
    the null-world control tests: under no signal its expectation is exactly
    zero, in both directions.
    """
    L = [x for x in xs if x["flip"]]
    W = [x for x in xs if not x["flip"]]
    if not L or not W:
        return float("nan")
    return (sum(1 for x in L if x["fired"]) / len(L)
            - sum(1 for x in W if x["fired"]) / len(W))


def d_catch_fa(xs):
    """The statistic that would carry a real claim: USABLE catches on losers
    minus any fire on winners.

    It is deliberately asymmetric -- a catch only counts if it beat the cross
    by ACT_SECONDS, a false alarm counts whenever it fires -- so it is biased
    DOWNWARD under the null. The self-test uses that: in a null world it must
    never claim a positive edge, and the symmetric d_fire must bracket zero.
    Discovering that asymmetry is what the first null run was for; the earlier
    version of this file asserted the wrong thing and the null caught it.
    """
    L = [x for x in xs if x["flip"]]
    W = [x for x in xs if not x["flip"]]
    if not L or not W:
        return float("nan")
    return (sum(1 for x in L if x["usable"]) / len(L)
            - sum(1 for x in W if x["fired"]) / len(W))


def mde_prop(n_per_arm, p, alpha=0.05, power=0.80):
    """Smallest difference in rate detectable, treating each CLOSE as one
    independent observation. Stated BEFORE any estimate, per the house rule."""
    if n_per_arm < 1:
        return float("nan")
    return (1.959964 + 0.8416212) * math.sqrt(2 * p * (1 - p) / n_per_arm)


# ---------------------------------------------------------------------------
# SELF-TEST. A world with a planted alarm the estimator must find, and a world
# with nothing planted where it must find nothing.
def _synth(tk, close, won_yes, fall, cross_tau, sd_t=0.0010, spread=0.01):
    """One synthetic market in rows.jsonl shape.

    Entry lands at tau 40 by construction: earlier seconds carry a cushion of
    1.5 sigma (model p_flip 6.7%, above the 2% gate) at the SAME price, so the
    entry gate -- not a price change -- decides where the position opens. That
    matters: if the price moved at entry the velocity alarm would fire on
    winners too and the planted test would prove nothing.
    """
    out = []
    for tau in range(60, 9, -1):
        r = tau - 1
        vf = math.sqrt(var_factor(r, [1.0])) * (60.0 / r)
        sig = sd_t / vf
        if tau > 40:
            z, ask = 1.5, 0.96
        elif tau == 40:
            z, ask = 2.2, 0.96
        elif cross_tau is None or tau > cross_tau:
            z, ask = 2.2, max(0.55, 0.96 - fall * 0.01 * (40 - tau))
        else:
            z, ask = -0.5, 0.20
        cush = z * sd_t
        side_yes_row = (cush <= 0)
        price = ask if not side_yes_row else (1.0 - (ask - spread))
        if not (0.5 < price < 1.0):
            continue
        out.append({"tk": tk, "sr": "SYN", "close": close, "sec": close - tau,
                    "tau": tau, "r": r, "price": round(price, 4), "size": 50.0,
                    "spread": spread, "dep_y": 100.0, "dep_n": 100.0,
                    "age_ms": 0, "mu": 0.0, "req": cush, "cov": 1.0,
                    "spot": 0.0, "sig": sig, "s30": sig, "s120": sig,
                    "tr5": 0.0, "tr15": 0.0, "dr15": 0.0, "dr60": 0.0,
                    "jump": 0, "hour": 0, "side_yes": side_yes_row,
                    "flip": (side_yes_row != won_yes)})
    return out


def selftest():
    print("SELF-TEST -- pinalarm")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # ---- 1. re-expressing a row from OUR side ---------------------------
    base = {"sec": 0, "tau": 10, "r": 9, "req": 0.001, "sig": 0.0,
            "dep_y": 1.0, "dep_n": 2.0, "flip": False}
    a = feat(dict(base, price=0.95, spread=0.01, side_yes=False), False)
    ck(abs(a["ask"] - 0.95) < 1e-12 and abs(a["bid"] - 0.94) < 1e-12,
       "our side is the favoured one: ask 0.95, bid 0.94 "
       "(got %.4f/%.4f)" % (a["ask"], a["bid"]))
    ck(abs(a["hedge_ask"] - 0.06) < 1e-12,
       "and the hedge costs 1-bid = 6c (%.4f)" % a["hedge_ask"])
    b = feat(dict(base, price=0.81, spread=0.01, side_yes=True), False)
    ck(abs(b["ask"] - 0.20) < 1e-12 and abs(b["bid"] - 0.19) < 1e-12,
       "the model has SWITCHED, so the recorded 81c ask belongs to the OTHER "
       "side and ours is 20c (got %.4f)" % b["ask"])
    ck(abs(b["hedge_ask"] - 0.81) < 1e-12,
       "and hedging now costs the recorded 81c, not 19c (%.4f)"
       % b["hedge_ask"])
    ck(feat(dict(base, price=0.81, spread=None, side_yes=True), False) is None,
       "with no spread a switched row CANNOT be re-expressed, and is dropped "
       "rather than guessed")

    # ---- 2. the model number --------------------------------------------
    ck(abs(p_lose(2.0, 1.0) - 0.02275) < 1e-4,
       "a 2-sigma cushion is a 2.275%% model chance of losing (%.3f%%)"
       % (100 * p_lose(2.0, 1.0)))
    ck(p_lose(-1.0, 1.0) > 0.5 and p_lose(0.0, 0.0) == 1.0,
       "a negative cushion is odds-against, and a dead-flat index with the "
       "cushion already gone is a certain loss")
    c1 = feat(dict(base, price=0.95, spread=0.01, side_yes=False), False)
    ck(c1["cush"] == 0.001, "holding NO, the cushion is +req")
    c2 = feat(dict(base, price=0.95, spread=0.01, side_yes=False), True)
    ck(c2["cush"] == -0.001,
       "holding YES against the same row it is -req -- one second is good "
       "news for one side and bad for the other")

    # ---- 3. velocity across an irregular tape ---------------------------
    fs = [{"sec": 100, "ask": 0.99, "z": 3.0},
          {"sec": 106, "ask": 0.93, "z": 2.0}]
    v = deriv(fs, 1, "ask", lookback=3, sign=-100.0)
    ck(abs(v - 1.0) < 1e-12,
       "a 6c fall across a 6-second gap is 1.0c/s, not 2c/s -- the gap is "
       "divided out (%.4f)" % v)
    fs2 = [{"sec": 100, "ask": 0.99}, {"sec": 120, "ask": 0.93}]
    ck(deriv(fs2, 1, "ask", lookback=3) is None,
       "and with nothing inside the window it returns None rather than "
       "comparing across 20 seconds of silence")

    # ---- 4. PLANTED WORLD: a price collapse before every loss -----------
    rows = []
    for m in range(30):
        rows += _synth("L%d" % m, 3000000 + 900 * m, True, 1.0, 20)
    for m in range(30):
        rows += _synth("W%d" % m, 3000000 + 900 * m, False, 0.0, None)
    E = build_entries(rows, 3, 200)
    ck(len(E) == 60 and all(e["tau"] == 40 for e in E),
       "the gate opens every position at the planted second (%d at tau %s)"
       % (len(E), sorted(set(e["tau"] for e in E))))
    ck(sum(1 for e in E if e["flip"]) == 30, "30 of them lose, by construction")
    ck(all(e["cross"] == 20 for e in E if e["flip"]),
       "and every loser crosses at the planted second")
    pred = [r for r in rules() if r[1] == "pvel" and r[2] == 0.5][0][3]
    A = agg(score(E, pred))
    ck(A["catch"] >= 0.9 and A["fa"] <= 0.1,
       "the velocity alarm finds the planted collapse: catch %.0f%%, false "
       "alarms %.0f%%" % (100 * A["catch"], 100 * A["fa"]))
    ck(A["lead_med"] >= 5,
       "and it fires %.0fs before the cross, not on top of it" % A["lead_med"])
    ck(A["catch_use"] >= 0.9,
       "so the warning is usable (%.0f%%)" % (100 * A["catch_use"]))

    # ---- 5. an alarm that fires ONE SECOND before the cross is worthless -
    late = []
    for m in range(20):
        late += _synth("X%d" % m, 4000000 + 900 * m, True, 0.0, 20)
    for r_ in late:
        if r_["tau"] == 21:
            r_["price"] = round(r_["price"] - 0.03, 4)
    AL = agg(score(build_entries(late, 3, 200), pred))
    ck(AL["catch"] >= 0.9 and AL["catch_use"] == 0.0,
       "a one-second warning is DETECTED (%.0f%%) and scored UNUSABLE "
       "(%.0f%%) -- accuracy is not the test"
       % (100 * AL["catch"], 100 * AL["catch_use"]))

    # ---- 6. cost in a world with nothing to save ------------------------
    won = []
    for m in range(20):
        won += _synth("Z%d" % m, 5000000 + 900 * m, False, 0.0, None)
    AW = agg(score(build_entries(won, 3, 200), lambda x: True))
    hp = 1.0 - (0.96 - 0.01)
    want = (hp + fee(hp)) / (1.0 - 0.96 - fee(0.96))
    ck(AW["nL"] == 0 and abs(AW["destroyed"] - want) < 1e-9,
       "in a world with no losers an always-on alarm destroys %.1f%% of "
       "profit, which is the hand figure %.1f%%"
       % (100 * AW["destroyed"], 100 * want))

    # ---- 7. NULL WORLD: paths drawn independently of the outcome --------
    rnd = random.Random(4)
    nul = []
    for m in range(80):
        wy = rnd.random() < 0.5
        nul += _synth("N%d" % m, 6000000 + 900 * m, wy, rnd.uniform(0.0, 1.5),
                      20 if rnd.random() < 0.5 else None)
    EN = build_entries(nul, 3, 200)
    pn = score(EN, pred)
    AN = agg(pn)
    lo, hi = boot(pn, d_fire, B=600, seed=3)
    ck(lo <= 0.0 <= hi,
       "NULL: with the price path drawn independently of the outcome the "
       "alarm fires %+.0fpp more often on losers, 95%% CI [%+.0f, %+.0f]pp "
       "-- it must contain zero"
       % (100 * (AN["catch"] - AN["fa"]), 100 * lo, 100 * hi))
    lo2, hi2 = boot(pn, d_catch_fa, B=600, seed=3)
    ck(lo2 <= 0.0,
       "NULL: and the claim-carrying statistic (usable catches minus false "
       "alarms) must NOT come back positive: %+.0fpp, 95%% CI [%+.0f, %+.0f]pp"
       % (100 * (AN["catch_use"] - AN["fa"]), 100 * lo2, 100 * hi2))
    ck(AN["nL"] >= 20 and AN["nW"] >= 20,
       "and the null world has both kinds to confuse it (%d losers, %d "
       "winners)" % (AN["nL"], AN["nW"]))

    # ---- 8. the scale-in builder ----------------------------------------
    fall = []
    for m in range(10):
        fall += _synth("S%d" % m, 7000000 + 900 * m, False, 1.0, None)
    B = build_buys(fall, 3, 200)
    b1 = [e for e in B if e["buy"] == 1]
    ck(len(b1) == 10, "one first buy per market (%d)" % len(b1))
    seq = sorted([e for e in B if e["tk"] == "S0"], key=lambda e: e["buy"])
    ck(len(seq) == 3, "a falling price produces three buys (%d)" % len(seq))
    ck(all(seq[i]["price"] <= seq[i - 1]["price"] - IMPROVE_BY + 1e-12
           for i in range(1, len(seq))),
       "and each is at least %.1fc cheaper than the last (%s)"
       % (100 * IMPROVE_BY,
          ", ".join("%.1fc" % (100 * e["price"]) for e in seq)))
    flatB = build_buys(won, 3, 200)
    ck(all(e["buy"] == 1 for e in flatB),
       "a flat price produces exactly one buy, never a scale-in")

    # ---- 8b. the guard's own accounting ---------------------------------
    _g = [{"at": {"pvel": 5.0}, "flip": True, "price": 0.90},
          {"at": {"pvel": 5.0}, "flip": False, "price": 0.90},
          {"at": {"pvel": 5.0}, "flip": False, "price": 0.90},
          {"at": {"pvel": 0.0}, "flip": False, "price": 0.90},
          {"at": {"pvel": None}, "flip": True, "price": 0.90}]
    c = rule_cost(_g, 4.0)
    ck(c["ref"] == 3 and c["rl"] == 1 and c["rw"] == 2,
       "the guard refuses 3 buys, 1 loser and 2 winners (%d/%d/%d)"
       % (c["ref"], c["rl"], c["rw"]))
    ck(abs(c["per_loss"] - 2.0) < 1e-12,
       "two winning trades refused per loss avoided (%.1f)" % c["per_loss"])
    ck(abs(c["destroyed"] - 2 * (0.10 - fee(0.90))) < 1e-12,
       "profit destroyed is the two winners' P&L, fees included")
    ck(abs(c["avoided"] - (0.90 + fee(0.90))) < 1e-12,
       "loss avoided is the loser's stake plus its fee")
    ck(c["net"] > 0, "and here the guard is worth it, because 90c saved beats "
       "two 10c winners given up")
    ck(rule_cost([x for x in _g if x["at"]["pvel"] != 5.0], 4.0)["ref"] == 0,
       "with nothing above the threshold it refuses nothing and a None "
       "velocity is never refused")

    # ---- 9. the break-even arithmetic -----------------------------------
    # cost 0.5c per position, saving 50c per loss => break even at 1.00%
    ck(abs((0.005 / 0.50) - 0.01) < 1e-12,
       "break-even flip rate is cost/saving: 0.5c against 50c is 1.00%")

    # ---- 10. MDE --------------------------------------------------------
    ck(0.10 < mde_prop(30, 0.5) < 0.40,
       "30 closes per arm can only detect a swing of %.0fpp around a 50%% "
       "rate" % (100 * mde_prop(30, 0.5)))

    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


# ---------------------------------------------------------------------------
def pct_of(xs, v):
    """Where v sits in xs, as a percentile. Reported, never smoothed."""
    xs = sorted(x for x in xs if x is not None and x == x)
    if not xs:
        return float("nan")
    return 100.0 * sum(1 for x in xs if x <= v) / len(xs)


def med(xs):
    xs = sorted(x for x in xs if x is not None and x == x)
    return xs[len(xs) // 2] if xs else float("nan")


def pnl(e):
    return ((1.0 - e["price"]) if not e["flip"] else -e["price"]) \
        - fee(e["price"])


def bucket_table(entries, key, edges, label, ci=True):
    """Flip rate by bucket of an ENTRY-TIME feature. n is reported as CLOSES
    as well as positions, because up to nine coins share one close."""
    print("\n  " + label)
    print("    %-22s %8s %8s %8s %9s" %
          ("bucket", "entries", "closes", "losers", "flip rate"))
    cells = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        sel = [e for e in entries
               if key(e) is not None and key(e) == key(e)
               and lo <= key(e) < hi]
        cl = len(set(e["close"] for e in sel))
        nl = sum(1 for e in sel if e["flip"])
        fr = (nl / len(sel)) if sel else float("nan")
        cells.append((lo, hi, sel, cl, nl, fr))
        name = "%s to %s" % (("%g" % lo if lo > -1e17 else "-inf"),
                             ("%g" % hi if hi < 1e17 else "+inf"))
        print("    %-22s %8d %8d %8d %8.2f%%" %
              (name, len(sel), cl, nl, 100 * fr))
    miss = [e for e in entries if key(e) is None or key(e) != key(e)]
    if miss:
        print("    %-22s %8d %8d %8d %8.2f%%" %
              ("(feature unavailable)", len(miss),
               len(set(e["close"] for e in miss)),
               sum(1 for e in miss if e["flip"]),
               100 * sum(1 for e in miss if e["flip"]) / len(miss)))
    if ci and len(cells) >= 2:
        top, bot = cells[-1], cells[0]
        if top[2] and bot[2]:
            units = ([{"close": e["close"], "g": 1, "f": e["flip"]}
                      for e in top[2]] +
                     [{"close": e["close"], "g": 0, "f": e["flip"]}
                      for e in bot[2]])

            def dstat(xs):
                A = [x for x in xs if x["g"] == 1]
                B = [x for x in xs if x["g"] == 0]
                if not A or not B:
                    return float("nan")
                return (sum(1 for x in A if x["f"]) / len(A)
                        - sum(1 for x in B if x["f"]) / len(B))
            lo_, hi_ = boot(units, dstat, B=1200, seed=17)
            print("    top bucket minus bottom: %+.2fpp, 95%% CI "
                  "[%+.2f, %+.2f]pp  (closes resampled)"
                  % (100 * (top[5] - bot[5]), 100 * lo_, 100 * hi_))
    return cells


def guard_table(entries, key, thresholds, label):
    """What an ENTRY guard on this feature would refuse, and what it costs."""
    tot = sum(pnl(e) for e in entries)
    nl = sum(1 for e in entries if e["flip"])
    print("\n  " + label)
    print("    %-14s %9s %9s %9s %11s %11s" %
          ("refuse if >=", "refused", "of them", "winners", "profit lost",
           "flip rate"))
    print("    %-14s %9s %9s %9s %11s %11s" %
          ("", "", "losers", "refused", "cents", "of the rest"))
    for t in thresholds:
        ref = [e for e in entries
               if key(e) is not None and key(e) == key(e) and key(e) >= t]
        kept = [e for e in entries if e not in ref] if False else \
            [e for e in entries
             if not (key(e) is not None and key(e) == key(e)
                     and key(e) >= t)]
        rl = sum(1 for e in ref if e["flip"])
        rw = len(ref) - rl
        lost = sum(pnl(e) for e in ref if not e["flip"])
        kf = (sum(1 for e in kept if e["flip"]) / len(kept)) if kept \
            else float("nan")
        print("    %-14s %9d %9d %9d %11.1f %10.2f%%" %
              ("%g" % t, len(ref), rl, rw, 100 * lost, 100 * kf))
    print("    (base: %d entries, %d losers, %+.1fc total)"
          % (len(entries), nl, 100 * tot))


def alarm_table(entries, title, require_depth=False, ci=False):
    """Every alarm, scored on the three numbers that decide it: how much
    warning, how often it cries wolf, and what the wolf-crying costs."""
    print("\n  " + title)
    print("    %-42s %6s %6s %6s %7s %7s %7s %8s %8s %s" %
          ("alarm", "on los", "lead2", "lead5", "lead s", "on win",
           "hedge c", "tau fire", "profit -",
           "95% CI on fires(lose)-fires(win)" if ci else ""))
    out = []
    for label, fam, thr, pred in rules():
        per = score(entries, pred, require_depth=require_depth)
        A = agg(per)
        out.append((label, fam, thr, A, per))

        def g(v, f="%.0f"):
            return (f % v) if v == v else "n/a"
        cis = ""
        if ci:
            lo_, hi_ = boot(per, d_fire, B=600, seed=29)
            cis = ("  [%+.0f, %+.0f]pp" % (100 * lo_, 100 * hi_))                 if lo_ == lo_ else "  n/a"
        print("    %-42s %5s%% %5s%% %5s%% %7s %6.1f%% %7s %8s %7s%%%s" %
              (label, g(100 * A["catch"]), g(100 * A["lead2"]),
               g(100 * A["lead5"]), g(A["lead_med"]), 100 * A["fa"],
               g(100 * A["hp_L"], "%.1f"), g(A["tau_L"]),
               g(100 * A["destroyed"], "%.1f"), cis))
    return out


def loser_detail(entries, pred, label):
    """With twelve losers, a percentage hides more than it shows. Print them."""
    per = score(entries, pred)
    L = [p for p in per if p["flip"]]
    print("\n  EVERY LOSER, under %s" % label)
    print("    %-30s %6s %7s %7s %6s %6s %7s"
          % ("market", "entry", "paid", "fire at", "cross", "lead", "hedge"))
    for p in sorted(L, key=lambda x: x["tk"]):
        print("    %-30s %5ds %6.1fc %7s %6s %6s %7s"
              % (p["tk"][:30], p["entry_tau"], 100 * p["entry_price"],
                 ("%ds" % p["tau_fire"]) if p["fired"] else "never",
                 ("%ds" % p["cross"]) if p["cross"] is not None else "none",
                 ("%+d" % p["lead"]) if p["lead"] is not None else "-",
                 ("%.1fc" % (100 * p["hp"])) if p["hp"] is not None
                 else "-"))


def shuffle_control(entries, key, edges, label, seed=5, reps=400):
    """THE CONTROL THAT MATTERS, and it has to respect the clustering.

    Permuting labels across POSITIONS would break the fact that up to nine
    coins share one close and can flip together; that makes the null too easy
    to beat and the p-value too small. So this permutation moves each close's
    NUMBER of losers to a different close, then picks at random which of that
    close's positions lost. The close stays the unit of independence, as it is
    everywhere else in this project.
    """
    cells = []
    for i in range(len(edges) - 1):
        cells.append([e for e in entries
                      if key(e) is not None and key(e) == key(e)
                      and edges[i] <= key(e) < edges[i + 1]])
    if not cells[0] or not cells[-1]:
        print("    shuffle control (%s): a terminal bucket is empty, not run"
              % label)
        return
    real = (sum(1 for e in cells[-1] if e["flip"]) / len(cells[-1])
            - sum(1 for e in cells[0] if e["flip"]) / len(cells[0]))
    byc = defaultdict(list)
    for e in entries:
        byc[e["close"]].append(e)
    closes = list(byc)
    ks = [sum(1 for e in byc[c] if e["flip"]) for c in closes]
    rnd = random.Random(seed)
    draws = []
    tries = 0
    while len(draws) < reps and tries < reps * 60:
        tries += 1
        order = closes[:]
        rnd.shuffle(order)
        if any(k > len(byc[c]) for k, c in zip(ks, order)):
            continue
        lab = {}
        for k, c in zip(ks, order):
            grp = byc[c][:]
            rnd.shuffle(grp)
            for j, e in enumerate(grp):
                lab[id(e)] = (j < k)
        a = sum(1 for e in cells[-1] if lab[id(e)]) / len(cells[-1])
        b = sum(1 for e in cells[0] if lab[id(e)]) / len(cells[0])
        draws.append(a - b)
    if len(draws) < 50:
        print("    shuffle control (%s): only %d valid permutations, "
              "not reported" % (label, len(draws)))
        return
    worse = sum(1 for d in draws if d >= real)
    draws.sort()
    print("    CLUSTER-PRESERVING SHUFFLE (%s): real %+.2fpp, shuffled median "
          "%+.2fpp, 95th pct %+.2fpp, p = %.3f on %d draws"
          % (label, 100 * real, 100 * draws[len(draws) // 2],
             100 * draws[int(0.95 * len(draws))],
             (worse + 1) / (len(draws) + 1), len(draws)))


IMPROVE_BY = 0.005


def build_buys(rows, tau_lo, tau_hi, pin_p=PIN_P, ceiling=CEILING,
               ev_floor=EV_FLOOR, max_per_close=3):
    """EVERY buy the live rule would make, not just the first.

    The live rule scales in: up to three buys per close, each at least
    IMPROVE_BY cheaper than the last. The first buy and the third are
    different animals -- the third is only REACHABLE because the price fell --
    so a guard on price velocity lands on them very differently. Positions are
    tagged with their buy index so the two can be scored apart.
    """
    bym = defaultdict(list)
    for r in rows:
        bym[(r["tk"], r["close"])].append(r)
    out = []
    for key, seq in bym.items():
        seq.sort(key=lambda x: -int(x["tau"]))
        best = None
        buys = []
        for i, x in enumerate(seq):
            t = int(x["tau"])
            if not (tau_lo <= t <= tau_hi):
                continue
            sd = sd_of(x["r"], x.get("sig"))
            if p_lose(abs(float(x["req"])), sd) > pin_p:
                continue
            p = float(x["price"])
            if p > ceiling or ev(p) < ev_floor:
                continue
            if best is not None and p > best - IMPROVE_BY:
                continue
            buys.append((i, x))
            best = p
            if len(buys) >= max_per_close:
                break
        if not buys:
            continue
        S0 = bool(buys[0][1]["side_yes"])
        fs = [f for f in (feat(x, S0) for x in seq) if f is not None]
        enrich(fs)
        for k, (i, e) in enumerate(buys):
            at = None
            for f in fs:
                if f["tau"] == int(e["tau"]):
                    at = f
                    break
            if at is None:
                continue
            post = [f for f in fs if f["tau"] < int(e["tau"])]
            cross = None
            for f in post:
                if f["cush"] <= 0:
                    cross = f["tau"]
                    break
            out.append({"tk": e["tk"], "sr": e["sr"], "close": int(e["close"]),
                        "tau": int(e["tau"]), "side_yes": S0,
                        "price": float(e["price"]), "flip": bool(e["flip"]),
                        "at": at, "pre": [], "post": post, "cross": cross,
                        "n_post": len(post), "buy": k + 1})
    return out


def breakeven_table(tabW, entriesL, entriesW):
    """The decisive economics, in the shape IDEAS_LOG #31 used so the two can
    be read line for line.

    COST is measured on the LIVE window -- the population we actually trade,
    which contains no losses at all, so every alarm there is pure waste.
    SAVING is measured on the WIDE window -- the only place losses exist.
    Break-even flip rate = cost per position / saving per loss. Below our
    measured 0.90% the trigger loses money; above the 2.31% Clopper-Pearson
    upper bound we cannot rule out, it pays.
    """
    baseL = sum(pnl(e) for e in entriesL)
    nL = max(1, len(entriesL))
    losers = [e for e in entriesW if e["flip"]]
    print(NL + "    %-42s %10s %12s %11s  %s"
          % ("trigger", "cost/pos", "saving/loss", "break-even", "verdict"))
    for label, fam, thr, A, per in tabW:
        pr = [r for r in rules() if r[0] == label][0][3]
        pl = score(entriesL, pr)
        netL = sum((p["hedged"] if p["hedged"] is not None else p["base"])
                   for p in pl)
        cost = (baseL - netL) / nL
        sav = 0.0
        for p in per:
            if p["flip"] and p["hedged"] is not None:
                sav += p["hedged"] - p["base"]
        sav = sav / max(1, len(losers))
        be = (cost / sav) if sav > 1e-12 else float("inf")
        if cost <= 1e-12:
            verdict = "costs nothing measurable"
        elif be <= 0.0090:
            verdict = "PAYS at the measured 0.90%"
        elif be <= 0.0231:
            verdict = "marginal: pays between 0.90% and 2.31%"
        else:
            verdict = "does not pay even at the 2.31% bound"
        print("    %-42s %9.3fc %11.1fc %10s  %s"
              % (label, 100 * cost, 100 * sav,
                 ("%.2f%%" % (100 * be)) if be < 10 else "never", verdict))


# ---------------------------------------------------------------------------
def rule_cost(buys, thresh):
    """A velocity guard applied to EVERY buy the rule would make.

    Returns the exact accounting the operator has to see: how many winning
    trades are refused for each loss avoided, and whether the profit destroyed
    is bigger than the loss saved. A guard is not free and this is its price.
    """
    ref = [e for e in buys if e["at"]["pvel"] is not None
           and e["at"]["pvel"] == e["at"]["pvel"]
           and e["at"]["pvel"] >= thresh]
    rl = [e for e in ref if e["flip"]]
    rw = [e for e in ref if not e["flip"]]
    destroyed = sum(pnl(e) for e in rw)          # positive: profit given up
    avoided = -sum(pnl(e) for e in rl)           # positive: loss not taken
    winners_total = sum(pnl(e) for e in buys if not e["flip"])
    return {"n": len(buys), "ref": len(ref), "rl": len(rl), "rw": len(rw),
            "destroyed": destroyed, "avoided": avoided,
            "per_loss": (len(rw) / len(rl)) if rl else float("inf"),
            "net": avoided - destroyed,
            "share": (destroyed / winners_total) if winners_total > 0
            else float("nan")}


def rule_table(sets):
    print(NL + "    %-34s %7s %7s %7s %9s %10s %9s %9s"
          % ("population / threshold", "buys", "refused", "losers",
             "winners", "win/loss", "profit -", "net"))
    for name, buys in sets:
        for t in (1.0, 2.0, 4.0, 8.0):
            c = rule_cost(buys, t)
            print("    %-34s %7d %7d %7d %9d %10s %8.1fc %+8.1fc"
                  % ("%s, refuse >= %gc/s" % (name, t), c["n"], c["ref"],
                     c["rl"], c["rw"],
                     ("%.1f" % c["per_loss"]) if c["per_loss"] != float("inf")
                     else "no loss", 100 * c["destroyed"], 100 * c["net"]))


LOSS_TK = "KXNEAR15M-26SEP082045-45"
LOSS_CLOSE = 1788914700
LOSS_KEFF = 2.34915
TAPE = r"C:\kals\kalshi_data"


def replay_live_loss(hours_stamp="20260909T00",
                     seed_snapshot=False):
    """Rebuild the ONE market we lost on, second by second, from the raw tape.

    Uses the `_fp` book keys. pindata.Book.snapshot() reads `yes_dollars` /
    `no_dollars`, which the tape does not carry, so its snapshot seeding has
    never worked and its books are delta-only. This replay seeds properly and
    the report says whether that changed the answer.
    """
    import glob
    import gzip
    import zlib
    import array
    base_arr = None
    ipath = os.path.join(TAPE, "cfbenchmarks_value",
                         hours_stamp + ".jsonl.gz")
    vals = {}
    try:
        with gzip.open(ipath, "rt") as fh:
            for line in fh:
                if "NEARUSD_RTI" not in line:
                    continue
                try:
                    d = json.loads(line)
                    m = d["msg"]
                    if m.get("index_id") != "NEARUSD_RTI":
                        continue
                    dd = json.loads(m["data"])
                    vals[int(dd["time"]) // 1000] = float(dd["value"])
                except Exception:
                    continue
    except (EOFError, zlib.error, OSError) as exc:
        print("    index read failed: %r" % (exc,))
    if not vals:
        return None, None
    lo, hi = min(vals), max(vals)
    arr = array.array("d", [float("nan")] * (hi - lo + 1))
    for s, v in vals.items():
        arr[s - lo] = v
    base_arr = (lo, arr)

    # THE BOOK. A 15-minute market is born and dies inside one hour file, so
    # replaying that file's deltas from the top reconstructs it exactly from
    # birth -- no snapshot needed. The FIRST version of this function seeded
    # from the hour's snapshot and THEN applied every delta in the file,
    # including the ones that came before the snapshot, which double-counts.
    # It was caught because the replay disagreed with two of the three prices
    # we actually paid; a replay that cannot reproduce a known fill is wrong.
    yes, no = {}, {}
    seeded = 0
    if seed_snapshot:
        spath = os.path.join(TAPE, "orderbook_snapshot",
                             hours_stamp + ".jsonl.gz")
        try:
            with gzip.open(spath, "rt") as fh:
                for line in fh:
                    if LOSS_TK not in line:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                    except Exception:
                        continue
                    if m.get("market_ticker") != LOSS_TK:
                        continue
                    yes.clear()
                    no.clear()
                    for side, key in (("yes", "yes_dollars_fp"),
                                      ("no", "no_dollars_fp")):
                        d = yes if side == "yes" else no
                        for pair in (m.get(key) or []):
                            try:
                                q = float(pair[1])
                                pr = round(float(pair[0]), 4)
                            except Exception:
                                continue
                            if q > 0:
                                d[pr] = q
                    seeded += 1
                    break
        except (EOFError, zlib.error, OSError) as exc:
            print("    snapshot read failed: %r" % (exc,))

    book_by_sec = {}
    dpath = os.path.join(TAPE, "orderbook_delta", hours_stamp + ".jsonl.gz")
    ndelta = 0
    neg = 0
    try:
        with gzip.open(dpath, "rt") as fh:
            for line in fh:
                if LOSS_TK not in line:
                    continue
                try:
                    m = json.loads(line)["msg"]
                except Exception:
                    continue
                if m.get("market_ticker") != LOSS_TK:
                    continue
                ts = int(m.get("ts_ms") or 0)
                side = str(m.get("side", "")).lower()
                try:
                    pr = round(float(m.get("price_dollars", m.get("price"))), 4)
                    dq = float(m.get("delta_fp", m.get("delta")) or 0.0)
                except Exception:
                    continue
                d = yes if side == "yes" else no
                nv = d.get(pr, 0.0) + dq
                if nv < -1e-9:
                    neg += 1
                if nv <= 1e-9:
                    d.pop(pr, None)
                else:
                    d[pr] = nv
                ndelta += 1
                yb = max(yes) if yes else None
                nb = max(no) if no else None
                ask = (1.0 - yb) if yb is not None else None
                cell = book_by_sec.get(ts // 1000)
                if cell is None:
                    book_by_sec[ts // 1000] = {"yb": yb, "nb": nb,
                                               "lo": ask, "hi": ask,
                                               "ysz": (yes.get(yb) if yb
                                                       is not None else 0.0)}
                else:
                    cell["yb"], cell["nb"] = yb, nb
                    cell["ysz"] = yes.get(yb) if yb is not None else 0.0
                    if ask is not None:
                        cell["lo"] = ask if cell["lo"] is None                             else min(cell["lo"], ask)
                        cell["hi"] = ask if cell["hi"] is None                             else max(cell["hi"], ask)
    except (EOFError, zlib.error, OSError) as exc:
        print("    delta read failed: %r" % (exc,))
    return base_arr, {"book": book_by_sec, "seeded": seeded,
                      "deltas": ndelta, "neg": neg}


def live_loss_report(dist):
    print("\n" + "=" * 78)
    print("  TONIGHT'S LOSS, REPLAYED FROM THE RAW TAPE")
    print("=" * 78)
    idx, bk = replay_live_loss()
    if idx is None or bk is None:
        print("  REPLAY FAILED -- no index or no book. Reporting the failure "
              "rather than the numbers.")
        return
    lo, arr = idx
    print("  deltas applied %d (snapshot seeds %d, negative-size events %d)"
          % (bk["deltas"], bk["seeded"], bk["neg"]))
    print("\n    %4s %10s %11s %9s %8s %9s %9s %9s"
          % ("tau", "index", "cushion", "sigmas", "model", "our ask",
             "mkt p", "fall c/s"))
    hist = []
    for tau in range(45, 2, -1):
        sec = LOSS_CLOSE - tau
        r = tau - 1
        i = sec - lo
        if i < 320 or i >= len(arr):
            continue
        tot = k = 0
        for j in range(i - 300, i + 1):
            a_, b_ = arr[j - 1], arr[j]
            if a_ == a_ and b_ == b_:
                dd = b_ - a_
                tot += dd * dd
                k += 1
        sig = math.sqrt(tot / k) if k >= 15 else None
        spot = arr[i]
        if spot != spot or sig is None:
            continue
        lo_s, hi_s = LOSS_CLOSE - 60, min(sec, LOSS_CLOSE - 1)
        s_tot = s_got = 0
        for s in range(lo_s, hi_s + 1):
            v = arr[s - lo]
            if v == v:
                s_tot += v
                s_got += 1
        want = hi_s - lo_s + 1
        if s_got < want * 0.95:
            continue
        locked = s_tot * (want / s_got)
        rr = 60 - want
        if rr < 1:
            continue
        mu = (locked + rr * spot) / 60.0
        cush = (60.0 / rr) * (LOSS_KEFF - mu)       # we held NO
        sd = sd_of(rr, sig)
        z = cush / sd if sd > 0 else float("inf")
        mpf = p_lose(cush, sd)
        cell = bk["book"].get(sec) or {}
        yb, nb = cell.get("yb"), cell.get("nb")
        ask = (1.0 - yb) if yb is not None else None
        bid = nb
        mid = (0.5 * (ask + bid)) if (ask is not None and bid is not None) \
            else None
        hist.append({"sec": sec, "tau": tau, "ask": ask, "bid": bid,
                     "mid": mid, "model_pf": mpf, "z": z, "cush": cush,
                     "mkt_pf": (None if mid is None else 1 - mid),
                     "lo": cell.get("lo"), "hi": cell.get("hi"),
                     "div": (None if mid is None else (1 - mid) - mpf),
                     "spot": spot, "sig": sig})
    for i in range(len(hist)):
        hist[i]["pvel"] = deriv(hist, i, "ask", sign=-100.0)
        hist[i]["dvel"] = deriv(hist, i, "div", sign=1.0)
    for h in hist:
        print("    %4d %10.5f %11.6f %9.2f %7.2f%% %9s %8s %9s %13s"
              % (h["tau"], h["spot"], h["cush"], h["z"], 100 * h["model_pf"],
                 ("%.1fc" % (100 * h["ask"])) if h["ask"] is not None else "-",
                 ("%.1f%%" % (100 * h["mkt_pf"]))
                 if h["mkt_pf"] is not None else "-",
                 ("%+.2f" % h["pvel"]) if h["pvel"] is not None else "-",
                 ("%.1f-%.1fc" % (100 * h["lo"], 100 * h["hi"]))
                 if h.get("lo") is not None else "-"))
    PAID = {22: 0.962, 21: 0.956, 17: 0.730}
    print(NL + "  RECONCILING THE REPLAY AGAINST THE THREE PRICES WE ACTUALLY")
    print("  PAID. A book replay that cannot reproduce a known fill is wrong,")
    print("  and this check is what found the seeding bug in the first "
          "version.")
    for t in sorted(PAID, reverse=True):
        h = [x for x in hist if x["tau"] == t]
        if not h:
            print("    tau %d: NOT IN THE REPLAY" % t)
            continue
        h = h[0]
        ok = (h.get("lo") is not None and
              h["lo"] - 0.0011 <= PAID[t] <= h["hi"] + 0.0011)
        print("    tau %2d: paid %.1fc, replayed best NO ask %s, "
              "range within the second %s  --> %s"
              % (t, 100 * PAID[t],
                 ("%.1fc" % (100 * h["ask"])) if h["ask"] is not None else "-",
                 ("%.1f-%.1fc" % (100 * h["lo"], 100 * h["hi"]))
                 if h.get("lo") is not None else "-",
                 "REPRODUCED" if ok else "DOES NOT MATCH"))
    print(NL + "  AND AT THE PRICE WE ACTUALLY PAID. The best ask and our")
    print("  fill differ inside a second, so the velocity a guard would have")
    print("  seen AT THE MOMENT OF THE ORDER is computed from the paid price")
    print("  against the ask three seconds earlier.")
    byt = dict((h["tau"], h) for h in hist)
    for t in sorted(PAID, reverse=True):
        ref = byt.get(t + 3) or byt.get(t + 2) or byt.get(t + 4)
        if ref is None or ref["ask"] is None:
            print("    tau %d: no reference 3s back" % t)
            continue
        dt = ref["tau"] - t
        v = 100.0 * (ref["ask"] - PAID[t]) / dt
        print("    tau %2d: paid %.1fc against %.1fc %ds earlier -> "
              "%+.2f c/s of FALL  (%.1f%%ile of winning trades)"
              % (t, 100 * PAID[t], 100 * ref["ask"], dt, v,
                 pct_of(dist["win_pvel"], v)))
    buys = [22, 21, 17]
    print("\n  WHERE THE THREE BUYS SIT IN THE WINNING-TRADE DISTRIBUTION")
    print("    %5s %10s %10s %10s %10s %10s"
          % ("tau", "our ask", "div pp", "div %ile", "fall c/s", "fall %ile"))
    for t in buys:
        h = [x for x in hist if x["tau"] == t]
        if not h:
            print("    tau %d not in the replay" % t)
            continue
        h = h[0]
        print("    %5d %10s %10s %9.1f%% %10s %9.1f%%"
              % (t,
                 ("%.1fc" % (100 * h["ask"])) if h["ask"] is not None else "-",
                 ("%+.1f" % (100 * h["div"])) if h["div"] is not None else "-",
                 pct_of(dist["win_div"], h["div"]) if h["div"] is not None
                 else float("nan"),
                 ("%+.2f" % h["pvel"]) if h["pvel"] is not None else "-",
                 pct_of(dist["win_pvel"], h["pvel"])
                 if h["pvel"] is not None else float("nan")))
    return hist


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows",
                    default=r"C:\kals-repo\results\pindata\rows.jsonl")
    ap.add_argument("--wide-hi", type=int, default=200)
    ap.add_argument("--live-hi", type=int, default=30)
    ap.add_argument("--no-liveloss", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    rows = []
    with open(a.rows, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass
    print(NL + "  %d rows loaded from %s" % (len(rows), a.rows))

    W = build_entries(rows, 3, a.wide_hi)
    L = build_entries(rows, 3, a.live_hi)
    # A DELIBERATELY LOOSER GATE, to separate "no effect" from "no power".
    # Same tape, same estimator, a population with more losses in it.
    R = build_entries(rows, 3, a.wide_hi, pin_p=0.20, ceiling=0.995,
                      ev_floor=-1.0)
    for name, E in (("WIDE   live gate, tau 3-%d" % a.wide_hi, W),
                    ("LIVE   live gate, tau 3-%d" % a.live_hi, L),
                    ("RELAX  p<=20%, price<=99.5c, no EV floor", R)):
        nl = sum(1 for e in E if e["flip"])
        print("  %-42s %5d positions %4d closes %4d losers over %3d closes"
              % (name, len(E), len(set(e["close"] for e in E)), nl,
                 len(set(e["close"] for e in E if e["flip"]))))

    nl_cl = len(set(e["close"] for e in W if e["flip"]))
    nw_cl = len(set(e["close"] for e in W if not e["flip"]))
    base_fr = sum(1 for e in W if e["flip"]) / max(1, len(W))
    print(NL + "  MDE, STATED BEFORE THE ESTIMATES, per the house rule.")
    print("  Each CLOSE is one independent observation (nine coins share a")
    print("  close at rho ~0.8). The WIDE window has %d LOSING closes against"
          % nl_cl)
    print("  %d winning ones. At 80%% power and alpha 0.05 the smallest"
          % nw_cl)
    print("  detectable difference in flip rate, around the base rate of")
    print("  %.2f%%, is %.1fpp; around a 50%% alarm rate it is %.0fpp."
          % (100 * base_fr, 100 * mde_prop(min(nl_cl, nw_cl), base_fr),
             100 * mde_prop(min(nl_cl, nw_cl), 0.5)))
    print("  THE HOUSE FLOOR IS 30 CLUSTERS AND WE HAVE %d. Nothing below is"
          % nl_cl)
    print("  a significance claim; every loser-side number is descriptive.")

    dist = {
        "win_div": [e["at"]["div"] for e in W if not e["flip"]],
        "win_pvel": [e["at"]["pvel"] for e in W if not e["flip"]],
        "win_z": [e["at"]["z"] for e in W if not e["flip"]],
        "los_div": [e["at"]["div"] for e in W if e["flip"]],
        "los_pvel": [e["at"]["pvel"] for e in W if e["flip"]],
    }

    print(NL + "=" * 78)
    print("  1. AT ENTRY -- is anything different about the ones that lose?")
    print("=" * 78)
    print("  WIDE window. Every feature is built from seconds BEFORE the")
    print("  entry, so all of it was knowable at the moment we bought.")
    print(NL + "    %-28s %12s %12s" % ("median at entry", "winners",
                                        "losers"))
    for k, lab, sc in (("div", "divergence, pp", 100.0),
                       ("pvel", "price fall, cents/s", 1.0),
                       ("dvel", "divergence widening, pp/s", 100.0),
                       ("zvel", "cushion change, sigma/s", 1.0),
                       ("z", "cushion, sigmas", 1.0),
                       ("model_pf", "model p(lose), %", 100.0),
                       ("mkt_pf", "market p(lose), %", 100.0),
                       ("ask", "price paid, cents", 100.0)):
        wv = med([e["at"][k] for e in W if not e["flip"]])
        lv = med([e["at"][k] for e in W if e["flip"]])
        print("    %-28s %12s %12s"
              % (lab, ("%.3f" % (sc * wv)) if wv == wv else "n/a",
                 ("%.3f" % (sc * lv)) if lv == lv else "n/a"))
    nav = sum(1 for e in W if e["at"]["pvel"] is None)
    navl = sum(1 for e in W if e["at"]["pvel"] is None and e["flip"])
    print(NL + "  COVERAGE, AND IT IS THE BIGGEST LIMIT ON PART 2: %d of %d"
          % (nav, len(W)))
    print("  entries -- and %d of the %d losers -- have NO price velocity at"
          % (navl, sum(1 for e in W if e["flip"])))
    print("  all, because rows.jsonl only holds seconds where somebody was")
    print("  offering, and there was no earlier such second within 6s. A LIVE")
    print("  trader sees its own book feed continuously and would not have")
    print("  this hole; this BACKTEST does, and it halves the loser sample.")

    bucket_table(W, lambda e: e["at"]["pvel"],
                 [-1e18, -0.25, 0.0, 0.25, 1.0, 1e18],
                 "FLIP RATE BY PRICE VELOCITY AT ENTRY (cents/s of FALL)")
    shuffle_control(W, lambda e: e["at"]["pvel"],
                    [-1e18, -0.25, 0.0, 0.25, 1.0, 1e18], "price velocity")
    bucket_table(W, lambda e: e["at"]["div"],
                 [-1e18, 0.0, 0.01, 0.03, 0.08, 1e18],
                 "FLIP RATE BY DIVERGENCE AT ENTRY (market minus model)")
    shuffle_control(W, lambda e: e["at"]["div"],
                    [-1e18, 0.0, 0.01, 0.03, 0.08, 1e18], "divergence")
    bucket_table(W, lambda e: e["at"]["ask"], [0.0, 0.94, 0.96, 0.98, 1.0],
                 "FLIP RATE BY PRICE PAID -- the confound divergence has to "
                 "beat, because divergence is very nearly 1 minus the price")
    band = [e for e in W if 0.94 <= e["at"]["ask"] < 0.98]
    print(NL + "  DIVERGENCE INSIDE ONE PRICE BAND (94-98c, %d entries, %d "
          "losers)" % (len(band), sum(1 for e in band if e["flip"])))
    print("  If divergence is only price wearing a hat, it stops separating")
    print("  anything once the price is held roughly fixed.")
    bucket_table(band, lambda e: e["at"]["div"],
                 [-1e18, 0.02, 0.04, 0.06, 1e18], "  divergence within band")
    bucket_table(W, lambda e: e["at"]["zvel"],
                 [-1e18, -0.10, -0.02, 0.02, 0.10, 1e18],
                 "FLIP RATE BY CUSHION TRAJECTORY AT ENTRY (sigma/s; "
                 "negative = the required move SHRINKING)")
    bucket_table(W, lambda e: (e["at"]["z"]
                               if abs(e["at"]["z"]) != float("inf") else None),
                 [-1e18, 2.5, 4.0, 8.0, 1e18],
                 "FLIP RATE BY CUSHION LEVEL AT ENTRY (sigmas) -- what the "
                 "trajectory has to beat")

    print(NL + "  THE SAME TWO TABLES ON THE RELAXED POPULATION (%d entries, "
          "%d losers over %d closes)"
          % (len(R), sum(1 for e in R if e["flip"]),
             len(set(e["close"] for e in R if e["flip"]))))
    print("  This is a DIFFERENT population -- it buys things the live rule")
    print("  refuses -- so it cannot validate the live edge. It exists only")
    print("  to ask whether the signal survives when losses are not scarce.")
    bucket_table(R, lambda e: e["at"]["pvel"],
                 [-1e18, -0.25, 0.0, 0.25, 1.0, 1e18],
                 "RELAXED: flip rate by price velocity at entry")
    shuffle_control(R, lambda e: e["at"]["pvel"],
                    [-1e18, -0.25, 0.0, 0.25, 1.0, 1e18],
                    "price velocity, relaxed")
    bucket_table(R, lambda e: e["at"]["div"],
                 [-1e18, 0.0, 0.01, 0.03, 0.08, 1e18],
                 "RELAXED: flip rate by divergence at entry")
    shuffle_control(R, lambda e: e["at"]["div"],
                    [-1e18, 0.0, 0.01, 0.03, 0.08, 1e18],
                    "divergence, relaxed")

    guard_table(W, lambda e: e["at"]["pvel"], (0.5, 1.0, 2.0, 4.0, 8.0),
                "AN ENTRY GUARD ON PRICE VELOCITY -- WIDE window")
    guard_table(L, lambda e: e["at"]["pvel"], (0.5, 1.0, 2.0, 4.0, 8.0),
                "THE SAME GUARD ON THE LIVE WINDOW (tau 3-%d) -- pure cost, "
                "there is nothing here to save" % a.live_hi)
    guard_table(W, lambda e: e["at"]["div"], (0.03, 0.05, 0.10),
                "AN ENTRY GUARD ON DIVERGENCE -- WIDE window")
    guard_table(L, lambda e: e["at"]["div"], (0.03, 0.05, 0.10),
                "THE SAME DIVERGENCE GUARD ON THE LIVE WINDOW")

    print(NL + "=" * 78)
    print("  2. AFTER ENTRY -- does the trajectory warn us in time?")
    print("=" * 78)
    print("  lead2 / lead5: share of LOSERS warned at least 2 / 5 seconds")
    print("  before the CROSS (the second the projected mean lands on the")
    print("  wrong side of the strike). 'hedge c' is the median price of the")
    print("  other side at the moment the alarm fired -- the cost of acting")
    print("  on it. 'profit -' is the share of winners' profit a hedge at")
    print("  that trigger destroys; IDEAS_LOG #31 killed the 5%% model")
    print("  trigger on that column at 26.5%%.")
    tabW = alarm_table(W, "WIDE window (%d positions, %d losers over %d "
                       "closes)" % (len(W), sum(1 for e in W if e["flip"]),
                                    nl_cl), ci=True)
    print(NL + "  The same alarms on the LIVE window, where there is nothing")
    print("  to catch. This is the honest COST column, and it is the one")
    print("  that has to be compared with 26.5%.")
    alarm_table(L, "LIVE window (%d positions, %d losers)"
                % (len(L), sum(1 for e in L if e["flip"])))

    for lab, fam, thr in (("PRICE VELOCITY falling >= 2c/s", "pvel", 2.0),
                          ("DIV VELOCITY >= 5pp/s", "dvel", 0.05),
                          ("MODEL p(lose) >= 90%", "model", 0.90)):
        pr = [r for r in rules() if r[1] == fam and r[2] == thr][0][3]
        loser_detail(W, pr, lab)

    print(NL + "=" * 78)
    print("  3. THE HEDGE, RE-TRIGGERED")
    print("=" * 78)
    print("  A note that stops a wrong claim: buying the other side and")
    print("  SELLING our own are economically identical here. Hedging pays")
    print("  1-bid and sells nothing; selling takes bid. The fee")
    print("  0.07*p*(1-p) is symmetric in p, so both pay the same fee too.")
    print("  There is no cheaper way to act on an alarm.")
    print(NL + "    %-42s %9s %9s %8s %8s %s"
          % ("trigger", "net (c)", "vs base", "deep@20", "touch", "95% CI"))
    base_pnl = sum(pnl(e) for e in W)
    print("    %-42s %9.1f %9s %8s %8s %s"
          % ("NO HEDGE (what we do today)", 100 * base_pnl, "-", "-", "-", "-"))
    for label, fam, thr, A, per in tabW:
        lo_, hi_ = boot(per, lambda xs: sum(
            (p["hedged"] if p["hedged"] is not None else p["base"])
            for p in xs) / max(1, len(xs)), B=800, seed=23)
        print("    %-42s %9.1f %+9.1f %7.0f%% %8s [%+.2f,%+.2f]c/pos"
              % (label, 100 * A["net"], 100 * (A["net"] - base_pnl),
                 100 * A["deep"],
                 ("%.0f/%d" % (A["touch_L"], A["touch_n"]))
                 if A["touch_n"] else "-", 100 * lo_, 100 * hi_))
    print(NL + "    'deep@20' uses rows.jsonl's TOP-THREE depth on the side we")
    print("    would sell into, so it is an UPPER BOUND and reads 100%")
    print("    everywhere. 'touch' is the exact touch size, median and count,")
    print("    and it is only knowable for alarms firing AFTER the model has")
    print("    switched sides. IDEAS_LOG #32 measured 6 of 12 hedges deep")
    print("    enough at size 20 using the touch; that number, not this one,")
    print("    is the one to believe.")
    print(NL + "    THE NET COLUMN ABOVE IS NOT THE DECISION. It pools a")
    print("    2.74% wide-window flip rate with a live rate of 0.90%, so it")
    print("    flatters every trigger by roughly 3x. The decision is below.")
    breakeven_table(tabW, L, W)

    print(NL + "=" * 78)
    print("  4. THE SCALE-IN BUYS, WHICH IS WHERE THE LIVE LOSS ACTUALLY WENT")
    print("=" * 78)
    BW = build_buys(rows, 3, a.wide_hi)
    BL = build_buys(rows, 3, a.live_hi)
    print("  A second or third buy only EXISTS because the price fell at")
    print("  least %.1fc. So a price-velocity guard is not neutral between"
          % (100 * IMPROVE_BY))
    print("  buys -- it lands almost entirely on the later ones. Tonight the")
    print("  third buy was 22.6c cheaper than the second.")
    for name, B in (("WIDE", BW), ("LIVE", BL)):
        print(NL + "  %s window, by buy index" % name)
        print("    %-8s %9s %8s %9s %11s %12s"
              % ("buy", "positions", "closes", "losers", "flip rate",
                 "med fall c/s"))
        for k in (1, 2, 3):
            sel = [e for e in B if e["buy"] == k]
            if not sel:
                continue
            print("    %-8d %9d %8d %9d %10.2f%% %12s"
                  % (k, len(sel), len(set(e["close"] for e in sel)),
                     sum(1 for e in sel if e["flip"]),
                     100 * sum(1 for e in sel if e["flip"]) / len(sel),
                     ("%+.2f" % med([e["at"]["pvel"] for e in sel]))
                     if med([e["at"]["pvel"] for e in sel]) ==
                     med([e["at"]["pvel"] for e in sel]) else "n/a"))
    later = [e for e in BW if e["buy"] >= 2]
    laterL = [e for e in BL if e["buy"] >= 2]
    if later:
        guard_table(later, lambda e: e["at"]["pvel"], (1.0, 2.0, 4.0, 8.0),
                    "A VELOCITY GUARD ON SECOND AND THIRD BUYS ONLY -- WIDE")
    if laterL:
        guard_table(laterL, lambda e: e["at"]["pvel"], (1.0, 2.0, 4.0, 8.0),
                    "THE SAME GUARD ON SECOND AND THIRD BUYS -- LIVE window, "
                    "pure cost")
        guard_table(laterL, lambda e: e["at"]["div"], (0.10, 0.20, 0.35),
                    "A DIVERGENCE GUARD ON SECOND AND THIRD BUYS -- LIVE "
                    "window, pure cost")

    print(NL + "=" * 78)
    print("  5. THE PROPOSED RULE, AND WHAT IT COSTS")
    print("=" * 78)
    print("  Refuse ANY buy whose price is falling faster than the threshold.")
    print("  'win/loss' is winning trades refused per loss avoided; 'net' is")
    print("  the loss avoided minus the profit destroyed. A guard is only")
    print("  worth having where net is positive.")
    rule_table([("WIDE  all buys", BW), ("LIVE  all buys", BL),
                ("WIDE  buys 2-3 only", [e for e in BW if e["buy"] >= 2]),
                ("LIVE  buys 2-3 only", [e for e in BL if e["buy"] >= 2])])

    if not a.no_liveloss:
        live_loss_report(dist)

    print(NL + "  DONE.")


if __name__ == "__main__":
    main()
