#!/usr/bin/env python3
# VERSION: 2026-09-11-pr1
"""pinrules.py -- THE STRATEGY AS DATA: params, rules, trackers, profiles.

WHY. The operator wants to "rip this strategy apart without doing the math",
set up his own trackers (the crazy-deal tracker was the first), save the
result as a profile and run it -- without asking. Every one of those needs
the strategy's numbers and rules to be DATA the tool can read and write, not
constants inside pinrun.py. This file is that data's single definition.

THREE THINGS LIVE HERE

1. THE PARAM SCHEMA. Every tunable, declared once, with type, range, default
   and a plain-English explanation. The tool draws a control for every entry
   automatically, and the Learn tab draws its meaning from the same entry, so
   a control can never exist without its explanation. Add a param here and it
   appears everywhere.

2. THE RULE LANGUAGE. A rule is a condition over the DECISION RECORD -- the
   fields the bot sees at the second it decides -- plus an action:
       refuse   do not trade when it fires
       log      trade as normal, but record that it fired   <- A TRACKER
       allow    trade even if a later rule would refuse (rare; explicit)
   Conditions are lists of [field, op, value], combined with "all" / "any" /
   "not". Deliberately small: no arithmetic, no free text, nothing that can
   hide lookahead or a typo. Every rule's outcome is recorded whether or not
   it refused, so trackers and refusals both resolve against settlements.

3. PROFILES. {name, params, rules}. `default.json` is the live rule. Loading
   validates every param against its range and every rule against the field
   list, so a profile that would have made the bot exit silently (the
   --loss-abort incident) is refused at load with a reason.

THE DECISION RECORD is the contract between live and replay. pinrun and
pinsim both build it from the same names; a rule can only see these, and all
of them are backward-looking by construction.
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = os.path.join(os.path.dirname(HERE), "profiles")

# ---------------------------------------------------------------- the schema
# key: (type, min, max, default, one-line meaning, why it matters)
PARAMS = {
    "PIN": ("float", 0.90, 0.9999, 0.995,
            "How sure the model must be before it will buy (0.995 = 99.5%).",
            "Measured at the second the bot fires, the model's own boundary "
            "flips ~2% at 0.98 (2.05 sd) and ~0.5% at 0.995-0.9999 (2.6-4 sd). "
            "Raising it removed the boundary losses that cost -$70 under the "
            "old gate; it costs some fills, because deeper markets are priced "
            "higher."),
    "PRICE_CEILING": ("float", 0.50, 0.999, 0.98,
            "The most it will ever pay for a contract, in dollars.",
            "Break-even loss rate is roughly (1 - price). At 98c you may only "
            "be wrong 1.9% of the time; at 95c, 4.7%. Wins-to-recover one "
            "loss: 49 at 98c, 19 at 95c."),
    "TAU_MIN": ("int", 1, 59, 3,
            "Earliest it may act: seconds before the close.",
            "Below ~3 s an order cannot land before settlement."),
    "TAU_MAX": ("int", 2, 60, 30,
            "Latest it may start looking: seconds before the close.",
            "The model is well calibrated inside 30 s and overconfident "
            "beyond it (3.7x at 31-45 s, 10.9x at 46-60 s)."),
    "EDGE_FLOOR": ("float", 0.0, 0.10, 0.003,
            "Minimum model edge after fees, in dollars per contract.",
            "Below this the trade is noise. 0.3c is where the out-of-sample "
            "test stayed positive."),
    "EV_FLOOR": ("float", 0.0, 0.10, 0.003,
            "Minimum expected value per contract using the MEASURED flip rate.",
            "The model's own confidence is not the flip rate. This gate uses "
            "the rate we actually see."),
    "MEASURED_FLIP": ("float", 0.0, 0.20, 0.009,
            "The loss rate assumed by the EV gate.",
            "The live rate under the current gate is measured, not assumed; "
            "see the Live tab. This value sets where the EV gate bites."),
    "SIZE": ("float", 0.01, 125, 20,
            "Contracts per order.",
            "Capped by the bank: one worst-case losing close may cost at most "
            "25% of the bank. Depth on offer caps it around 100-125."),
    "MAX_PER_CLOSE": ("int", 1, 5, 2,
            "How many buys it may make on one 15-minute close.",
            "A losing close loses every fill on it. Two, measured better than "
            "one and three; three needs a bank the brake can fund."),
    "MIN_FILL_FRAC": ("float", 0.0, 1.0, 0.5,
            "Smallest fraction of SIZE it will accept as a fill.",
            "A scrap fill burns a scale-in slot and raises the improve bar, "
            "which measured worse than not trading."),
    "IMPROVE_BY": ("float", 0.0, 0.20, 0.005,
            "A second buy on the same close must be this much cheaper.",
            "Averaging down wins more AND loses less here; rebuying at the "
            "same price doubles the risk for nothing."),
    "MAX_BOOK_AGE_MS": ("int", 100, 10000, 2000,
            "Refuse if the order book it sees is older than this.",
            "A stale book is an offer that may no longer exist."),
    "MAX_INDEX_AGE_S": ("float", 0.5, 10.0, 2.0,
            "Refuse if the newest index print is older than this.",
            "The model runs on the index; a stale index is a stale model."),
    "SIGMA_STRESS": ("float", 0.5, 3.0, 1.0,
            "Multiply the model's volatility estimate by this.",
            "Above 1 makes the model less sure of everything -- a blunt way "
            "to widen its tail, which is measured 1.3x too thin overall and "
            "worthless beyond 4 sd."),
    "LOSS_ABORT": ("float", -1000.0, -1.0, -60.0,
            "Halt the run when realised P&L for the run falls below this.",
            "A brake, not a target. Must scale with SIZE: at size 40+ one "
            "losing close trips -$60 on its own."),
    "MAX_LOSSES": ("int", 1, 20, 3,
            "Halt after this many losing CLOSES in one run.",
            "Counts closes, not fills, because fills on one close are one "
            "event. A human looks before more money moves."),
}

# ---------------------------------------------------------- decision record
# name: meaning. These are the ONLY fields a rule may reference. Both pinrun
# (live) and pinsim (replay) must produce every one of them.
FIELDS = {
    "fair": "model probability that YES settles in (0-1)",
    "conf": "model probability that the side we would buy wins (0-1)",
    "margin_sd": "how far inside the gate, in standard deviations",
    "want": "'yes' or 'no' -- the side the model favours",
    "price": "the offer we would hit, dollars per contract",
    "discount_c": "cents below the model's fair value the offer sits",
    "edge_c": "model edge after fees, cents per contract",
    "ev_c": "expected value at the MEASURED flip rate, cents per contract",
    "tau": "seconds to the close",
    "depth": "contracts resting at that price",
    "take_n": "contracts we would take",
    "coin": "series ticker, e.g. KXBTC15M",
    "hour_utc": "hour of day, 0-23 UTC",
    "sigma": "the model's per-second volatility estimate",
    "spot": "newest index print",
    "cond_x": "how rough the OTHER coins are vs their own hour (1 = normal)",
    "cond_n": "how many other coins are moving (roughness > 2)",
    "cond_own": "this coin's roughness vs its own hour",
    "book_age_ms": "age of the order book we see",
    "index_age_s": "age of the newest index print",
}
OPS = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
       "<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
       "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
       "in": lambda a, b: a in b, "not in": lambda a, b: a not in b}
ACTIONS = ("refuse", "log", "allow")


# ------------------------------------------------------------------ rules
def check_condition(cond, path="when"):
    """Validate a condition tree. Returns a list of problems (empty = ok)."""
    bad = []
    if isinstance(cond, dict):
        keys = [k for k in cond if k in ("all", "any", "not")]
        if len(keys) != 1 or len(cond) != 1:
            return [f"{path}: expected exactly one of all/any/not"]
        k = keys[0]
        if k == "not":
            return check_condition(cond[k], path + ".not")
        if not isinstance(cond[k], list) or not cond[k]:
            return [f"{path}.{k}: must be a non-empty list"]
        for i, c in enumerate(cond[k]):
            bad += check_condition(c, f"{path}.{k}[{i}]")
        return bad
    if isinstance(cond, list) and len(cond) == 3:
        f, op, v = cond
        if f not in FIELDS:
            bad.append(f"{path}: unknown field {f!r}")
        if op not in OPS:
            bad.append(f"{path}: unknown op {op!r}")
        if op in ("in", "not in") and not isinstance(v, list):
            bad.append(f"{path}: {op} needs a list")
        if op not in ("in", "not in", "==", "!=") and \
                not isinstance(v, (int, float)):
            bad.append(f"{path}: {op} needs a number")
        return bad
    return [f"{path}: a condition is [field, op, value] or {{all|any|not: ...}}"]


def holds(cond, rec):
    """Evaluate a validated condition against a decision record."""
    if isinstance(cond, dict):
        k = next(iter(cond))
        if k == "all":
            return all(holds(c, rec) for c in cond[k])
        if k == "any":
            return any(holds(c, rec) for c in cond[k])
        return not holds(cond[k], rec)
    f, op, v = cond
    a = rec.get(f)
    if a is None:
        return False
    try:
        return bool(OPS[op](a, v))
    except TypeError:
        return False


def decide(profile, rec):
    """Apply a profile's rules to one decision record.

    Returns (verdict, fired) where verdict is 'trade' or 'refuse' and fired
    is the list of rule ids whose condition held, with their actions -- so
    every tracker that fired is recorded whether or not the trade happened.
    An explicit `allow` beats a `refuse`; otherwise any `refuse` refuses.
    """
    fired = []
    refuse = allow = False
    for r in profile.get("rules", []):
        if not r.get("enabled", True):
            continue
        if holds(r["when"], rec):
            fired.append((r["id"], r["action"]))
            if r["action"] == "refuse":
                refuse = True
            elif r["action"] == "allow":
                allow = True
    return ("refuse" if (refuse and not allow) else "trade"), fired


# -------------------------------------------------------------- schedules
# A param may be a NUMBER or a SCHEDULE -- a table of bands over one field of
# the decision record:
#     {"by": "price", "default": 20,
#      "bands": [[0.50, 0.80, 60], [0.80, 0.94, 30], [0.94, 0.99, 20]]}
# meaning: 60 contracts when the price is in [0.50, 0.80), 30 in [0.80, 0.94),
# 20 in [0.94, 0.99), and the default anywhere else. This is how "how many
# contracts at each price point" is expressed, and any value can be promoted
# to a schedule over any numeric field. Bands are [lo, hi) and must not
# overlap; every band value must sit inside the param's own range.
SCHEDULE_KEYS = ("by", "bands", "default")


def is_schedule(v):
    return isinstance(v, dict) and "bands" in v


def check_schedule(name, v, path):
    bad = []
    typ, lo, hi, *_ = PARAMS[name]
    if set(v) - set(SCHEDULE_KEYS) or "by" not in v or "default" not in v:
        return [f"{path}: a schedule is {{by, bands, default}}"]
    if v["by"] not in FIELDS:
        bad.append(f"{path}.by: unknown field {v['by']!r}")
    if v["by"] in ("want", "coin"):
        bad.append(f"{path}.by: {v['by']} is not numeric; use a rule")

    def okval(x, where):
        if typ == "int" and not (isinstance(x, int) and not isinstance(x, bool)):
            bad.append(f"{where}: must be an integer")
        elif not isinstance(x, (int, float)) or isinstance(x, bool):
            bad.append(f"{where}: must be a number")
        elif not (lo <= x <= hi):
            bad.append(f"{where}: {x} outside [{lo}, {hi}]")
    okval(v["default"], f"{path}.default")
    bands = v["bands"]
    if not isinstance(bands, list) or not bands:
        return bad + [f"{path}.bands: non-empty list of [lo, hi, value]"]
    prev_hi = None
    for i, b in enumerate(sorted(bands, key=lambda b: b[0] if isinstance(b, list) and b else 0)):
        if not (isinstance(b, list) and len(b) == 3 and
                all(isinstance(x, (int, float)) for x in b[:2])):
            bad.append(f"{path}.bands[{i}]: [lo, hi, value]")
            continue
        if b[1] <= b[0]:
            bad.append(f"{path}.bands[{i}]: hi must exceed lo")
        if prev_hi is not None and b[0] < prev_hi:
            bad.append(f"{path}.bands[{i}]: overlaps the previous band")
        prev_hi = b[1]
        okval(b[2], f"{path}.bands[{i}].value")
    return bad


def resolve(profile, name, rec):
    """The effective value of a param for THIS decision record."""
    v = profile["params"][name]
    if not is_schedule(v):
        return v
    x = rec.get(v["by"])
    if x is None:
        return v["default"]
    for lo, hi, val in v["bands"]:
        if lo <= x < hi:
            return val
    return v["default"]


# --------------------------------------------------------------- profiles
def validate(profile):
    bad = []
    if not isinstance(profile.get("name"), str) or not profile["name"]:
        bad.append("name: required")
    params = profile.get("params", {})
    for k, v in params.items():
        if k not in PARAMS:
            bad.append(f"params.{k}: unknown param")
            continue
        typ, lo, hi, *_ = PARAMS[k]
        if is_schedule(v):
            bad += check_schedule(k, v, f"params.{k}")
            continue
        if typ == "int" and not (isinstance(v, int) and not isinstance(v, bool)):
            bad.append(f"params.{k}: must be an integer")
            continue
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            bad.append(f"params.{k}: must be a number")
            continue
        if not (lo <= v <= hi):
            bad.append(f"params.{k}: {v} outside [{lo}, {hi}] -- the bot "
                       f"would refuse to start")
    for k in PARAMS:
        if k not in params:
            bad.append(f"params.{k}: missing (every param must be explicit)")
    ids = set()
    for i, r in enumerate(profile.get("rules", [])):
        p = f"rules[{i}]"
        if not isinstance(r.get("id"), str) or not r["id"]:
            bad.append(f"{p}.id: required")
        elif r["id"] in ids:
            bad.append(f"{p}.id: duplicate {r['id']!r}")
        else:
            ids.add(r["id"])
        if r.get("action") not in ACTIONS:
            bad.append(f"{p}.action: must be one of {ACTIONS}")
        if "when" not in r:
            bad.append(f"{p}.when: required")
        else:
            bad += check_condition(r["when"], f"{p}.when")
    return bad


def default_profile():
    return {
        "name": "default",
        "note": "The live rule as of 2026-09-11: AMENDMENT 9 (gate 0.995) and "
                "AMENDMENT 10b (refuse a certainty at a discount, by owner "
                "decision, tracked for review at 40).",
        "params": {k: v[3] for k, v in PARAMS.items()},
        "rules": [
            {"id": "dump", "name": "Crazy deal", "enabled": True,
             "action": "refuse",
             "when": {"all": [["conf", ">=", 0.999], ["discount_c", ">", 5]]},
             "note": "The model calls it certain and someone is still selling "
                     "it 5c+ below fair. Both live losses at extreme "
                     "confidence had this shape. EV undeterminable on six "
                     "fills; owner chose fewer losses. Review at 40 records."},
        ],
    }


def fingerprint(profile):
    s = json.dumps(profile, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def load(name_or_path):
    path = name_or_path if name_or_path.endswith(".json") else \
        os.path.join(PROFILES, f"{name_or_path}.json")
    with open(path, encoding="utf-8") as f:
        p = json.load(f)
    bad = validate(p)
    if bad:
        raise ValueError("profile refused:\n  " + "\n  ".join(bad))
    p["_sha"] = fingerprint({k: v for k, v in p.items() if k != "_sha"})
    p["_path"] = path
    return p


def save(profile, name=None):
    p = {k: v for k, v in profile.items() if not k.startswith("_")}
    if name:
        p["name"] = name
    bad = validate(p)
    if bad:
        raise ValueError("profile refused:\n  " + "\n  ".join(bad))
    os.makedirs(PROFILES, exist_ok=True)
    path = os.path.join(PROFILES, f"{p['name']}.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(p, f, indent=2)
        f.write("\n")
    return path


def worst_case(params, price=None):
    """Dollars a run can lose before its brakes stop it -- computed from the
    profile's own numbers so a looser profile cannot hide what it permits."""
    import math

    def biggest(v):            # a schedule's worst case is its largest band
        if is_schedule(v):
            return max([v["default"]] + [b[2] for b in v["bands"]])
        return v
    p = price if price is not None else biggest(params["PRICE_CEILING"])
    close = biggest(params["MAX_PER_CLOSE"]) * biggest(params["SIZE"]) * p
    n_abort = math.ceil(-biggest(params["LOSS_ABORT"]) / close) \
        if close > 0 else 99
    n = min(n_abort, biggest(params["MAX_LOSSES"]))
    return {"one_losing_close": round(close, 2), "closes_to_halt": n,
            "max_loss": round(n * close, 2)}


# ---------------------------------------------------------------- self-test
def selftest():
    print("SELF-TEST -- pinrules")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    d = default_profile()
    ck(validate(d) == [], "the default profile validates")
    ck(all(len(v) == 6 and v[4] and v[5] for v in PARAMS.values()),
       f"every one of {len(PARAMS)} params carries a meaning AND a why -- the "
       f"tool cannot draw a control without its explanation")
    import pinrun
    live = {"PIN": pinrun.PIN, "PRICE_CEILING": pinrun.PRICE_CEILING,
            "TAU_MIN": pinrun.TAU_MIN, "TAU_MAX": pinrun.TAU_MAX,
            "EDGE_FLOOR": pinrun.EDGE_FLOOR, "EV_FLOOR": pinrun.EV_FLOOR,
            "MEASURED_FLIP": pinrun.MEASURED_FLIP,
            "MAX_PER_CLOSE": pinrun.MAX_PER_CLOSE,
            "MIN_FILL_FRAC": pinrun.MIN_FILL_FRAC,
            "IMPROVE_BY": pinrun.IMPROVE_BY,
            "MAX_BOOK_AGE_MS": pinrun.MAX_BOOK_AGE_MS,
            "MAX_INDEX_AGE_S": pinrun.MAX_INDEX_AGE_S,
            "SIGMA_STRESS": pinrun.SIGMA_STRESS}
    diff = {k: (d["params"][k], v) for k, v in live.items()
            if abs(d["params"][k] - v) > 1e-12}
    ck(not diff, f"default.json params equal pinrun's LIVE constants "
                 f"(mismatches: {diff})")
    ck(d["params"]["PIN"] == 0.995 and d["rules"][0]["action"] == "refuse",
       "and it carries A9 (0.995) and A10b (refuse the crazy deal)")

    # the crazy-deal rule on the two real losses and the real cheap wins
    def rec(conf, price, fair=None):
        fair = conf if fair is None else fair
        return {"conf": conf, "price": price,
                "discount_c": round(100 * (conf - price), 2)}
    v, fired = decide(d, rec(1.0, 0.82))
    ck(v == "refuse" and fired == [("dump", "refuse")],
       "XRP (fair 1.0 at 82c, LOST) is refused by the rule, not by Python")
    v, _ = decide(d, rec(1.0, 0.10))
    ck(v == "refuse", "DOGE (fair 1.0 at 10c, LOST) is refused")
    v, fired = decide(d, rec(0.99735, 0.89))
    ck(v == "trade" and fired == [],
       "BNB (99.7% at 89c, WON) trades -- 99.7% is not 'certain'")
    v, _ = decide(d, rec(1.0, 0.978))
    ck(v == "trade", "a certainty at 97.8c (2.2c discount) trades")

    # a TRACKER: same condition, action log -> trades, but is recorded
    t = json.loads(json.dumps(d))
    t["rules"][0]["action"] = "log"
    v, fired = decide(t, rec(1.0, 0.82))
    ck(v == "trade" and fired == [("dump", "log")],
       "as a TRACKER the same rule lets the trade through AND records it")
    # a user-made tracker on a different field
    t["rules"].append({"id": "quiet_doge", "action": "log",
                       "when": {"all": [["coin", "==", "KXDOGE15M"],
                                        ["cond_own", "<", 0.6]]}})
    ck(validate(t) == [], "a user-written tracker on coin + cond_own validates")
    v, fired = decide(t, {"conf": 0.999, "price": 0.97, "discount_c": 2.9,
                          "coin": "KXDOGE15M", "cond_own": 0.55})
    ck(("quiet_doge", "log") in fired and v == "trade",
       "and it fires without refusing")
    # allow beats refuse, explicitly
    a = json.loads(json.dumps(d))
    a["rules"].append({"id": "cheap_ok", "action": "allow",
                       "when": ["price", "<", 0.30]})
    ck(decide(a, rec(1.0, 0.10))[0] == "trade" and
       decide(a, rec(1.0, 0.82))[0] == "refuse",
       "an explicit allow (price < 30c) overrides the refuse at 10c and not "
       "at 82c")
    # disabled rules are ignored
    a["rules"][0]["enabled"] = False
    ck(decide(a, rec(1.0, 0.82))[0] == "trade", "a disabled rule is ignored")

    # validation refuses what would have hurt us
    b = json.loads(json.dumps(d))
    b["params"]["LOSS_ABORT"] = 5.0
    ck(any("LOSS_ABORT" in x for x in validate(b)),
       "a positive LOSS_ABORT is refused at load (the -60 incident class)")
    b = json.loads(json.dumps(d))
    b["params"]["SIZE"] = 500
    ck(any("SIZE" in x for x in validate(b)), "SIZE 500 is refused")
    b = json.loads(json.dumps(d))
    b["rules"][0]["when"] = {"all": [["fairr", ">", 1]]}
    ck(any("unknown field" in x for x in validate(b)),
       "a misspelled field is refused, not silently false")
    b = json.loads(json.dumps(d))
    del b["params"]["PIN"]
    ck(any("PIN" in x for x in validate(b)),
       "a missing param is refused -- every value must be explicit")
    b = json.loads(json.dumps(d))
    b["rules"].append(dict(b["rules"][0]))
    ck(any("duplicate" in x for x in validate(b)), "duplicate rule ids refused")

    # --- SCHEDULES: "how many contracts at each price point" ------------
    sp = json.loads(json.dumps(d))
    sp["params"]["SIZE"] = {"by": "price", "default": 20,
                            "bands": [[0.50, 0.80, 60], [0.80, 0.94, 30],
                                      [0.94, 0.99, 20]]}
    ck(validate(sp) == [], "SIZE as a schedule over price validates")
    # 22c sits BELOW the first band, so the right answer there is the default
    # -- the first version of this check asked for 60 and the code correctly
    # refused; the fixture was wrong, not resolve()
    ck(resolve(sp, "SIZE", {"price": 0.60}) == 60 and
       resolve(sp, "SIZE", {"price": 0.85}) == 30 and
       resolve(sp, "SIZE", {"price": 0.97}) == 20 and
       resolve(sp, "SIZE", {"price": 0.22}) == 20 and
       resolve(sp, "SIZE", {"price": 0.995}) == 20 and
       resolve(sp, "SIZE", {}) == 20,
       "and resolves 60 at 60c, 30 at 85c, 20 at 97c, and the DEFAULT below "
       "the first band (22c), above the last (99.5c) and when price is missing")
    ck(resolve(sp, "PIN", {"price": 0.22}) == 0.995,
       "a plain number resolves to itself")
    sp2 = json.loads(json.dumps(sp))
    sp2["params"]["SIZE"]["bands"].append([0.70, 0.90, 40])
    ck(any("overlaps" in x for x in validate(sp2)), "overlapping bands refused")
    sp3 = json.loads(json.dumps(sp))
    sp3["params"]["SIZE"]["bands"][0][2] = 900
    ck(any("outside" in x for x in validate(sp3)),
       "a band value outside the param's range is refused")
    sp4 = json.loads(json.dumps(sp))
    sp4["params"]["SIZE"]["by"] = "coin"
    ck(any("not numeric" in x for x in validate(sp4)),
       "a schedule over a non-numeric field is refused (use a rule)")
    sp5 = json.loads(json.dumps(d))
    sp5["params"]["PRICE_CEILING"] = {"by": "margin_sd", "default": 0.98,
                                      "bands": [[4.0, 99.0, 0.996],
                                                [2.6, 4.0, 0.99]]}
    ck(validate(sp5) == [] and resolve(sp5, "PRICE_CEILING",
                                        {"margin_sd": 5.0}) == 0.996,
       "the margin-aware ceiling is expressible as a schedule over margin_sd")

    w = worst_case(d["params"])
    ck(w["one_losing_close"] == 39.2 and w["closes_to_halt"] == 2 and
       w["max_loss"] == 78.4,
       f"worst case from the profile's own numbers: one close ${w['one_losing_close']}, "
       f"halts after {w['closes_to_halt']}, max ${w['max_loss']}")
    ck(fingerprint(d) == fingerprint(json.loads(json.dumps(d))) and
       fingerprint(d) != fingerprint(t),
       "the fingerprint is stable and changes when a rule changes")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--write-default", action="store_true",
                    help="write profiles/default.json from the schema")
    ap.add_argument("--check", help="validate a profile by name or path")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")
    if a.write_default:
        print("  wrote", save(default_profile()))
    if a.check:
        p = load(a.check)
        print(f"  {p['name']}: valid, sha {p['_sha']}, "
              f"{len(p['rules'])} rules, worst case {worst_case(p['params'])}")


if __name__ == "__main__":
    main()
