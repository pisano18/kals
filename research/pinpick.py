#!/usr/bin/env python3
# VERSION: 2026-09-13-pk1
"""pinpick.py -- FIRST or BEST? which of several passing candidates to buy.

THE OPERATOR'S QUESTION, 2026-09-13: "I'm not certain if it should take the
first or scan for the best because prices move quick but also what if there's
better options so I'm not sure. Is that calculatable?"

IT IS CALCULABLE, and this file calculates it in two parts that must not be
confused with one another.

PART 1 -- STRUCTURE (fully trustworthy). Does a choice even exist? In one
scan second, how often is more than one market offering a gate-passing buy,
and how far apart are they in edge? This is a statement about what the market
offered. The tape is valid for exactly that -- CLAUDE.md's rule 5 forbids
loss rates from the tape, not counts of what was quoted. If two passers almost
never coincide, the question is moot and nothing should change.

PART 2 -- OUTCOME (caveated, and the caveat is not a formality). Replaying
each close under different choice rules and scoring with the tape's own `won`
uses a population -- "an offer was sitting there" -- that is NOT the one we
trade, "someone actively sold it to us". Measured 2026-09-11: 0.11% vs 3.4%,
a 31x gap, intervals disjoint. Worse, the bias is ASYMMETRIC here: a rule that
picks the biggest discount is deliberately selecting the offer most likely to
be cheap because its seller knew something. So the tape flatters best-by-edge.
Part 2 is reported as a direction, never as a P/L forecast, and anything it
suggests goes through the what-if tracker before it goes live.

WHAT THE LIVE BOT DOES TODAY. pinrun iterates `seen_markets` and fires on the
FIRST market that clears every gate; `nb["best"]` is computed but only for the
report. Iteration order is dict insertion order -- discovery order -- so it is
stable and therefore systematically favours the same few coins.

WHAT PICKING THE BEST WOULD COST IN TIME. Nothing that races anyone. The loop
already evaluates every market on every pass; `fair()` and `book.best()` are
local reads. Choosing the best defers the take to the end of a pass already
being run, not to the next pass.
"""
import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("KALS_SELFTESTED", "1")
import pinrun                                                  # noqa: E402

PIN = pinrun.PIN
EDGE_FLOOR = pinrun.EDGE_FLOOR
DUMP_DISCOUNT = pinrun.DUMP_DISCOUNT
MIN_LEVEL = pinrun.MIN_LEVEL
MIN_FILL_FRAC = pinrun.MIN_FILL_FRAC


def passes(r, size, pin=PIN):
    """Would the LIVE gate have bought this row? pinrun's own arithmetic."""
    if r.get("verdict") != "trade":
        return None
    conf = float(r.get("conf") or 0.0)
    if conf < pin:
        return None
    price = float(r["price"])
    want = r["want"]
    f = float(r["fair"])
    e = pinrun.net_edge(f, price, want)
    if e < EDGE_FLOOR:
        return None
    if pinrun.expected_value(price) <= 0:
        return None
    # AMENDMENT 10: a certainty at a discount is someone else's information.
    if float(r.get("discount_c") or 0.0) / 100.0 > DUMP_DISCOUNT:
        return None
    depth = float(r.get("depth") or 0.0)
    if depth < max(MIN_LEVEL, MIN_FILL_FRAC * float(size)):
        return None
    take = min(float(size), depth)
    return {"tk": r["ticker"], "cs": int(r["cs"]), "sec": int(r["entry_sec"]),
            "ts": float(r.get("entry_ts") or 0.0), "price": price,
            "want": want, "fair": f, "conf": conf, "edge": e,
            "depth": depth, "take": take, "won": bool(r.get("won")),
            "tau": int(r.get("tau") or 0)}


def load(path, size):
    out = []
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if r.get("kind") != "row":
                continue
            c = passes(r, size)
            if c:
                out.append(c)
    return out


# --------------------------------------------------------------- PART 1
def passes_by_second(cands):
    """{(cs, sec): [candidate]} -- one scan pass of the live loop."""
    g = defaultdict(list)
    for c in cands:
        g[(c["cs"], c["sec"])].append(c)
    for k in g:
        g[k].sort(key=lambda c: c["ts"])
    return g


def structure(cands, say=print):
    g = passes_by_second(cands)
    n_pass = len(g)
    multi = {}
    for k, v in g.items():
        tks = set(c["tk"] for c in v)
        if len(tks) >= 2:
            multi[k] = v
    lines = []
    w = lines.append
    w("  PART 1 -- DOES A CHOICE EVEN EXIST? (counts of what was quoted)")
    w("")
    w("  gate-passing candidate rows      : %d" % len(cands))
    w("  distinct scan seconds with one+  : %d" % n_pass)
    w("  scan seconds offering 2+ MARKETS : %d  (%.1f%% of passes)"
      % (len(multi), 100.0 * len(multi) / max(1, n_pass)))
    w("")
    hist = defaultdict(int)
    for v in g.values():
        hist[len(set(c["tk"] for c in v))] += 1
    w("  markets passing in the same second:")
    for k in sorted(hist):
        w("    %2d market(s) : %6d  (%5.1f%%)"
          % (k, hist[k], 100.0 * hist[k] / max(1, n_pass)))
    w("")
    if multi:
        gaps, pgaps, same = [], [], 0
        for v in multi.values():
            best = max(v, key=lambda c: c["edge"])
            first = v[0]
            gaps.append(100.0 * (best["edge"] - first["edge"]))
            pgaps.append(100.0 * (first["price"] - best["price"]))
            if best["tk"] == first["tk"]:
                same += 1
        gaps.sort()
        w("  when 2+ markets pass, the BEST-EDGE one is ALSO the first seen "
          "in %d of %d (%.1f%%)" % (same, len(multi),
                                    100.0 * same / len(multi)))
        w("  edge given up by taking the first, cents/contract:")
        w("    mean %+.2fc   median %+.2fc   p90 %+.2fc   max %+.2fc"
          % (sum(gaps) / len(gaps), gaps[len(gaps) // 2],
             gaps[int(0.90 * (len(gaps) - 1))], gaps[-1]))
        w("    price paid is %+.2fc higher on the first than on the best "
          "(mean)" % (sum(pgaps) / len(pgaps)))
    txt = "\n".join(lines)
    if say:
        say(txt)
    return txt, g, multi


# --------------------------------------------------------------- PART 3
# SAME-MARKET SECOND BUYS. The operator, 2026-09-13: "you can buy the same coin
# again if all the metrics line up ... because if it's really going to flip
# then the confidence should be dropping."
#
# THE ONE FACT THAT SHAPES THIS WHOLE TEST: a second buy is in the SAME market
# on the SAME close, so it has the SAME outcome as the first. Re-buying can
# never turn a winning close into a losing one. It only changes HOW MUCH is on
# that outcome. So the question is not "does the second leg lose more often" --
# it is whether the closes that OFFER a cheaper second leg are
# disproportionately the closes that were going to lose. If they are, re-buying
# is a machine for putting extra money on exactly the bad ones.
#
# That is why a time-only measurement (research/pinwarn.py, which shows the
# gate still passing means 0.37x the loss odds) cannot settle it. pinwarn never
# conditions on the PRICE having fallen, and the price falling is the whole
# trigger here.
IMPROVE_BY = pinrun.IMPROVE_BY


def second_buys(cands, improve_by=IMPROVE_BY):
    """One record per (close, market): the first buy, and whether a cheaper
    second buy that STILL PASSES THE GATE ever appeared.

    `improve_by` is pinrun's own bar (AMENDMENT 3): a second buy is only
    allowed at a price at least this much better than the best already paid.
    """
    by_mkt = defaultdict(list)
    for c in cands:
        by_mkt[(c["cs"], c["tk"])].append(c)
    out = []
    for (cs, tk), v in by_mkt.items():
        v.sort(key=lambda c: c["ts"])
        first = v[0]
        bar = first["price"] - improve_by
        later = [c for c in v[1:] if c["price"] <= bar + 1e-12]
        out.append({"cs": cs, "tk": tk, "first": first,
                    "n_second": len(later),
                    "second": later[0] if later else None,
                    "lost": not first["won"]})
    return out


def _rate(sel):
    n = len(sel)
    bad = sum(1 for r in sel if r["lost"])
    return n, bad, (100.0 * bad / n if n else float("nan"))


def _boot_diff(a_rows, b_rows, draws=2000, seed=7):
    """Bootstrap the (b - a) difference in loss rate, RESAMPLING CLOSES, not
    markets. Twelve coins settle on one second at rho ~ 0.8; resampling markets
    would treat one bad close as twelve independent bad markets and shrink the
    interval by ~3x."""
    import random
    rnd = random.Random(seed)
    by_close = defaultdict(lambda: ([], []))
    for r in a_rows:
        by_close[r["cs"]][0].append(r)
    for r in b_rows:
        by_close[r["cs"]][1].append(r)
    keys = list(by_close)
    if not keys:
        return (float("nan"), float("nan"))
    out = []
    for _ in range(draws):
        an = ab = bn = bb = 0
        for _i in range(len(keys)):
            k = keys[rnd.randrange(len(keys))]
            ar, br = by_close[k]
            an += len(ar)
            ab += sum(1 for r in ar if r["lost"])
            bn += len(br)
            bb += sum(1 for r in br if r["lost"])
        if an and bn:
            out.append(100.0 * (bb / bn - ab / an))
    if not out:
        return (float("nan"), float("nan"))
    out.sort()
    return (out[int(0.025 * (len(out) - 1))], out[int(0.975 * (len(out) - 1))])


DROP_BANDS = ((0.5, 1.0), (1.0, 2.0), (2.0, 5.0), (5.0, 10.0), (10.0, 1e9))


def leg_pl(x, n=1.0):
    """Realised dollars on one leg, using pinrun's own billed fee."""
    fee = pinrun.billed_fee(x["price"], n)
    if x["won"]:
        return n * (1.0 - x["price"]) - fee
    return -n * x["price"] - fee


def drop_bands(recs, bands=DROP_BANDS):
    """Group markets that offered a second buy by HOW MUCH CHEAPER it was.

    This is the thing available at decision time: we know the first price we
    paid and the price now on offer. If the loss rate rises with the size of
    the improvement, then 'the price got better' is not one signal but two --
    a small improvement is liquidity, a large one is information.
    """
    out = []
    for lo, hi in bands:
        sel = []
        for r in recs:
            if not r["second"]:
                continue
            d = 100.0 * (r["first"]["price"] - r["second"]["price"])
            if lo <= d < hi:
                sel.append(r)
        out.append(((lo, hi), sel))
    return out


def bands_table(recs, bands=DROP_BANDS, label=""):
    lines = []
    w = lines.append
    w("  how much cheaper the second buy was%s:" % label)
    w("    drop      | markets | lost | loss rate | second leg, c/contract")
    w("    ----------|---------|------|-----------|-----------------------")
    for (lo, hi), sel in drop_bands(recs, bands):
        if not sel:
            continue
        bad = sum(1 for r in sel if r["lost"])
        pls = [leg_pl(r["second"]) for r in sel]
        name = ("%.1f-%.0fc" % (lo, hi)) if hi < 1e8 else ("%.0fc+" % lo)
        w("    %-9s | %7d | %4d | %8.2f%% | %+21.2fc"
          % (name, len(sel), bad, 100.0 * bad / len(sel),
             100.0 * sum(pls) / len(pls)))
    return "\n".join(lines)


def seconds_report(cands, say=print):
    recs = second_buys(cands)
    no2 = [r for r in recs if r["n_second"] == 0]
    yes2 = [r for r in recs if r["n_second"] > 0]
    lines = []
    w = lines.append
    w("  PART 3 -- SHOULD A SECOND BUY IN THE SAME MARKET BE ALLOWED?")
    w("")
    w("  A second buy shares the first buy's outcome, so the only thing that")
    w("  matters is WHICH CLOSES offer one. Both groups below are markets the")
    w("  live gate would have bought once.")
    w("")
    for lab, sel in (("no cheaper second ever appeared ", no2),
                     ("a cheaper second DID appear     ", yes2)):
        n, bad, rate = _rate(sel)
        w("    %s: %5d markets, %4d lost (%6.2f%%)" % (lab, n, bad, rate))
    lo, hi = _boot_diff(no2, yes2)
    n1, b1, r1 = _rate(no2)
    n2, b2, r2 = _rate(yes2)
    w("")
    w("    difference: %+.2f pp, 95%% CI [%+.2f, %+.2f] pp, bootstrapped over"
      % (r2 - r1, lo, hi))
    w("    CLOSES (hard rule 4 -- twelve coins settle on one second at rho~0.8)")
    w("")
    # Haldane-corrected odds ratio, so a zero cell does not make it undefined
    o1 = (b1 + 0.5) / (n1 - b1 + 0.5)
    o2 = (b2 + 0.5) / (n2 - b2 + 0.5)
    w("    Haldane-corrected loss odds ratio (second-available / not): %.2fx"
      % (o2 / o1 if o1 else float("nan")))
    w("")
    w("  distinct closes involved: %d  (n is markets above, and markets are"
      % len(set(r["cs"] for r in recs)))
    w("  NOT independent within a close)")
    w("")
    w(bands_table(recs))
    w("")
    # HOLDOUT. A monotone table found once is a table; found again on closes
    # it was not fitted to, it is a finding. Split on close TIME, not at
    # random, because the eras in this tape differ (see results/VERSIONS.md).
    closes = sorted(set(r["cs"] for r in recs))
    if len(closes) >= 40:
        cut = closes[int(0.60 * len(closes))]
        early = [r for r in recs if r["cs"] < cut]
        late = [r for r in recs if r["cs"] >= cut]
        w("  HOLDOUT -- split on close time at %d:" % cut)
        w("")
        w(bands_table(early, label=", FIRST 60% of closes"))
        w("")
        w(bands_table(late, label=", LAST 40% of closes (not fitted)"))
    txt = "\n".join(lines)
    if say:
        say(txt)
    return txt, no2, yes2


# --------------------------------------------------------------- PART 2
RULES = {
    "first (LIVE today)": lambda v: v[0],
    "best edge":          lambda v: max(v, key=lambda c: c["edge"]),
    "best edge per $":    lambda v: max(v, key=lambda c: c["edge"] / c["price"]),
    "highest confidence": lambda v: max(v, key=lambda c: c["conf"]),
    "cheapest price":     lambda v: min(v, key=lambda c: c["price"]),
    "deepest book":       lambda v: max(v, key=lambda c: c["depth"]),
}


def replay_close(cands, rule, per_close, max_per_market=1):
    """Walk one close second by second, buying at most `per_close` contracts,
    at most `max_per_market` per market, choosing with `rule`. Returns
    (contracts, dollars_pl, n_losses)."""
    by_sec = defaultdict(list)
    for c in cands:
        by_sec[c["sec"]].append(c)
    bought = 0.0
    per_tk = defaultdict(float)
    pl = 0.0
    losses = 0
    for sec in sorted(by_sec):
        if bought >= per_close - 1e-9:
            break
        v = [c for c in by_sec[sec] if per_tk[c["tk"]] < max_per_market]
        if not v:
            continue
        v.sort(key=lambda c: c["ts"])
        pick = rule(v)
        n = min(pick["take"], per_close - bought)
        if n <= 0:
            continue
        fee = pinrun.billed_fee(pick["price"], n)
        if pick["won"]:
            pl += n * (1.0 - pick["price"]) - fee
        else:
            pl += -n * pick["price"] - fee
            losses += 1
        bought += n
        per_tk[pick["tk"]] += n
    return bought, pl, losses


def outcomes(cands, per_close, rules=None, say=print, label=""):
    rules = rules or RULES
    by_close = defaultdict(list)
    for c in cands:
        by_close[c["cs"]].append(c)
    res = {}
    for name, fn in rules.items():
        tot_n = tot_pl = 0.0
        losses = 0
        closes = 0
        for cs, v in by_close.items():
            n, pl, l = replay_close(v, fn, per_close)
            if n > 0:
                closes += 1
            tot_n += n
            tot_pl += pl
            losses += l
        res[name] = (closes, tot_n, tot_pl, losses)
    lines = []
    w = lines.append
    w("  PART 2 -- REPLAYED OUTCOME, %g contract(s) per close%s"
      % (per_close, label))
    w("  (TAPE population, not ours -- direction only, never a P/L forecast)")
    w("")
    w("  rule                 | closes | contracts |      P/L | c/contract | losses")
    w("  ---------------------|--------|-----------|----------|------------|-------")
    for name in rules:
        closes, n, pl, l = res[name]
        w("  %-20s | %6d | %9.0f | %+8.2f | %+10.2f | %5d"
          % (name, closes, n, pl, 100.0 * pl / max(1e-9, n), l))
    txt = "\n".join(lines)
    if say:
        say(txt)
    return txt, res


# --------------------------------------------------------------- selftest
def selftest():
    n = [0]

    def ck(cond, msg):
        n[0] += 1
        if not cond:
            print("SELFTEST FAIL: " + msg)
            raise SystemExit(1)
        print("  ok: " + msg)

    def cand(tk, cs, sec, ts, price, won, conf=0.999, depth=100.0,
             fair=None, want="yes"):
        f = fair if fair is not None else conf
        return {"tk": tk, "cs": cs, "sec": sec, "ts": ts, "price": price,
                "want": want, "fair": f, "conf": conf,
                "edge": pinrun.net_edge(f, price, want), "depth": depth,
                "take": 1.0, "won": won, "tau": 10}

    # ---- the gate is pinrun's, not a paraphrase --------------------------
    hot = {"kind": "row", "verdict": "trade", "conf": 0.999, "price": 0.95,
           "want": "yes", "fair": 0.999, "discount_c": 4.9, "depth": 100.0,
           "ticker": "A", "cs": 900, "entry_sec": 890, "entry_ts": 1.0,
           "won": True, "tau": 10}
    ck(passes(hot, 1) is not None, "an ordinary 95c candidate passes the gate")
    ck(passes(dict(hot, verdict="refuse"), 1) is None,
       "a row the live bot REFUSED is not counted as a candidate -- the "
       "2,699 refused rows in this file once manufactured a 10pp gap")
    ck(passes(dict(hot, price=0.995), 1) is None,
       "a 99.5c buy is refused: above the 99.1c break-even, expected_value "
       "is negative however confident the model is")
    ck(passes(dict(hot, discount_c=20.0), 1) is None,
       "a 20c discount to fair is refused -- AMENDMENT 10, that is someone "
       "else's information")
    ck(passes(dict(hot, depth=0.4), 1) is None,
       "a book holding 0.4 contracts is refused at size 1")
    ck(passes(dict(hot, conf=0.99), 1) is None,
       "confidence under the 0.995 gate is refused")

    # ---- PART 1 structure -------------------------------------------------
    v = [cand("A", 900, 890, 1.0, 0.95, True),
         cand("B", 900, 890, 2.0, 0.90, True),
         cand("A", 900, 891, 3.0, 0.95, True)]
    txt, g, multi = structure(v, say=None)
    ck(len(g) == 2, "two distinct scan seconds are found")
    ck(len(multi) == 1, "exactly one of them offered two different markets")
    ck("2+ MARKETS" in txt, "the structure report states the multi-market rate")

    # a second where the SAME market appears twice is NOT a choice
    v2 = [cand("A", 900, 890, 1.0, 0.95, True),
          cand("A", 900, 890, 2.0, 0.94, True)]
    _, _, m2 = structure(v2, say=None)
    ck(len(m2) == 0,
       "two rows for the SAME ticker in one second is not a choice between "
       "markets -- MAX_PER_MARKET is 1, so only one of them is buyable")

    # ---- PART 2, PLANT: cheap candidate always wins -----------------------
    good = []
    for i in range(200):
        cs = 900 * (i + 1)
        good.append(cand("A", cs, cs - 10, 1.0, 0.97, True))   # first, dear
        good.append(cand("B", cs, cs - 10, 2.0, 0.90, True))   # later, cheap
    _, res = outcomes(good, 1, say=None)
    ck(res["best edge"][2] > res["first (LIVE today)"][2],
       "when the cheaper candidate also wins, best-edge beats first "
       "(%+.2f vs %+.2f)" % (res["best edge"][2],
                             res["first (LIVE today)"][2]))

    # ---- PART 2, NULL: cheap candidate is cheap BECAUSE it loses ---------
    # This is the adverse-selection world the caveat is about. The estimator
    # must report best-edge LOSING here; if it cannot, it can only ever say
    # "pick the biggest discount", which is the failure mode that matters.
    bad = []
    for i in range(200):
        cs = 900 * (i + 1)
        bad.append(cand("A", cs, cs - 10, 1.0, 0.97, True))
        bad.append(cand("B", cs, cs - 10, 2.0, 0.90, i % 4 != 0))
    _, res2 = outcomes(bad, 1, say=None)
    ck(res2["best edge"][2] < res2["first (LIVE today)"][2],
       "when the discount is adverse, best-edge LOSES (%+.2f vs %+.2f) -- "
       "the estimator is not hard-wired to prefer a discount"
       % (res2["best edge"][2], res2["first (LIVE today)"][2]))

    # ---- PART 3: second buys in the same market --------------------------
    # the improve-by bar is pinrun's, and a second at the SAME price is not a
    # second buy at all
    v3 = [cand("A", 900, 880, 1.0, 0.960, True),
          cand("A", 900, 885, 2.0, 0.958, True),      # only 0.2c better
          cand("B", 900, 880, 3.0, 0.960, True),
          cand("B", 900, 885, 4.0, 0.950, True)]      # 1.0c better -> counts
    recs = dict(((r["cs"], r["tk"]), r) for r in second_buys(v3))
    ck(recs[(900, "A")]["n_second"] == 0,
       "a price only 0.2c better does not clear IMPROVE_BY (0.5c), so it is "
       "not a second buy")
    ck(recs[(900, "B")]["n_second"] == 1,
       "a price 1.0c better does clear it and counts as one second buy")

    # THE PLANT: make cheaper-second markets the LOSING ones and the estimator
    # must say so. This is the operator's own worry -- "a very slippery slope
    # into buying a flipping coin" -- and an estimator that cannot see it is
    # worthless for this decision.
    plant = []
    for i in range(300):
        cs = 900 * (i + 1)
        plant.append(cand("A", cs, cs - 20, 1.0, 0.96, True))
        plant.append(cand("B", cs, cs - 20, 2.0, 0.96, i % 5 != 0))
        if i % 5 == 0:                       # only the losers go cheaper
            plant.append(cand("B", cs, cs - 10, 3.0, 0.93, False))
    t3, no2, yes2 = seconds_report(plant, say=None)
    ck(_rate(yes2)[2] > _rate(no2)[2],
       "when only the doomed markets go cheaper, the cheaper-second group is "
       "measured as worse (%.1f%% vs %.1f%%)"
       % (_rate(yes2)[2], _rate(no2)[2]))

    # THE DOSE-RESPONSE PLANT: the bigger the price drop, the worse the
    # market. The band table must recover the ordering it was given.
    dose = []
    for i in range(500):
        cs = 900 * (i + 1)
        big = (i % 10) == 0                       # a big drop, mostly doomed
        won = (i % 4 != 0) if big else True
        dose.append(cand("A", cs, cs - 20, 1.0, 0.96, won))
        dose.append(cand("A", cs, cs - 10, 2.0,
                         0.96 - (0.06 if big else 0.008), won))
    db = dict((k, v) for k, v in drop_bands(second_buys(dose)))
    small = db[(0.5, 1.0)]
    large = db[(5.0, 10.0)]
    r_small = 100.0 * sum(1 for r in small if r["lost"]) / max(1, len(small))
    r_large = 100.0 * sum(1 for r in large if r["lost"]) / max(1, len(large))
    ck(len(small) > 0 and len(large) > 0,
       "both a small-drop (%d) and a large-drop (%d) band are populated"
       % (len(small), len(large)))
    ck(r_large > r_small,
       "a bigger price drop is measured as a worse market (%.1f%% vs %.1f%%)"
       % (r_large, r_small))
    ck("second leg, c/contract" in bands_table(second_buys(dose)),
       "the band table reports the second leg's own P/L, not just a rate")

    # THE NULL: cheaper seconds appear on winners and losers alike, so the
    # estimator must NOT report a gap. Without this it could only ever say
    # "second buys are dangerous", whatever the data.
    null = []
    for i in range(300):
        cs = 900 * (i + 1)
        null.append(cand("A", cs, cs - 20, 1.0, 0.96, i % 5 != 0))
        null.append(cand("B", cs, cs - 20, 2.0, 0.96, i % 5 != 0))
        null.append(cand("B", cs, cs - 10, 3.0, 0.93, i % 5 != 0))
    _, n0, y0 = seconds_report(null, say=None)
    ck(abs(_rate(y0)[2] - _rate(n0)[2]) < 1e-9,
       "with no relationship planted, the two groups come back identical "
       "(%.1f%% vs %.1f%%)" % (_rate(y0)[2], _rate(n0)[2]))
    lo, hi = _boot_diff(n0, y0)
    ck(lo <= 0.0 <= hi,
       "and the bootstrap interval [%+.2f, %+.2f] covers zero" % (lo, hi))

    # ---- the budget and the per-market cap are respected -----------------
    many = []
    for j, tkr in enumerate("ABCDE"):
        many.append(cand(tkr, 900, 880 + j, float(j), 0.95, True))
    nb, pl, _ = replay_close(many, RULES["first (LIVE today)"], 3)
    ck(abs(nb - 3.0) < 1e-9, "a 3-contract close budget buys exactly 3")
    rep = [cand("A", 900, 880 + j, float(j), 0.95, True) for j in range(5)]
    nb2, _, _ = replay_close(rep, RULES["first (LIVE today)"], 3)
    ck(abs(nb2 - 1.0) < 1e-9,
       "MAX_PER_MARKET 1 stops the same market being bought five times")

    print("pinpick selftest: %d checks OK" % n[0])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows", default=os.path.join(REPO, "results",
                                                   "pinlevels_rows.jsonl"))
    ap.add_argument("--size", type=float, default=1.0)
    ap.add_argument("--out", default=os.path.join(REPO, "results",
                                                  "RESULTS_pick.md"))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if os.environ.get("KALS_PICK_SELFTESTED") != "1":
        rc = selftest()
        if rc:
            return rc
    if not os.path.exists(a.rows):
        print("pinpick: loaded nothing -- %s is missing" % a.rows)
        return 0
    cands = load(a.rows, a.size)
    if not cands:
        print("pinpick: loaded nothing -- no row clears the live gate")
        return 0
    t1, g, multi = structure(cands)
    print("")
    t3, _, _ = seconds_report(cands)
    print("")
    parts = [t1, t3]
    for per in (1, 2, 3):
        t2, _ = outcomes(cands, per)
        print("")
        parts.append(t2)
    # HOLDOUT on close time, for the same reason PART 3 has one: a ranking
    # rule chosen on the whole sample is fitted to it.
    closes = sorted(set(c["cs"] for c in cands))
    if len(closes) >= 40:
        cut = closes[int(0.60 * len(closes))]
        for lab, sel in ((", FIRST 60% of closes",
                          [c for c in cands if c["cs"] < cut]),
                         (", LAST 40% of closes (not fitted)",
                          [c for c in cands if c["cs"] >= cut])):
            t2, _ = outcomes(sel, 1, label=lab)
            print("")
            parts.append(t2)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("# RESULTS_pick -- first or best?\n\n")
        for p in parts:
            fh.write("```\n" + p + "\n```\n\n")
    print("  wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
