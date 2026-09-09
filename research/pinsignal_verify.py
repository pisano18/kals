#!/usr/bin/env python3
# VERSION: 2026-09-08-psv1
"""pinsignal_verify.py -- ADVERSARIAL VERIFICATION of research/pinsignal.py.

pinsignal.py answered the operator's question ("did anything at entry signal
the loss?") with "nothing survives once the model's own cushion `z` is held
fixed, so deploy no new gate."  This file tries to REFUTE that, and it tests
the three things pinsignal did not:

  1  TEMPORAL SPLIT.  A discriminator adopted after one painful loss is the
     most likely thing in this project to be an overfit.  pinsignal never
     split its tape.  Here every feature is estimated on the FIRST half of
     the closes and the SECOND half separately.  A real effect keeps its sign
     and rough size; an artefact does not.  The cluster floor is reported per
     half, and where a half holds fewer than 30 loss-carrying closes NO
     significance is claimed for it.

  2  `lgap` WAS NEVER STRATIFIED.  pinsignal's prose names `lgap`
     (log(market p / model p)) among the strong columns that "the model
     already charges for", but `lgap` is absent from its PAIRS list, so that
     sentence is an assertion, not a measurement.  `lgap` is also the feature
     that most directly matches the live loss's own third buy (market 27%,
     model 0.17%).  It is stratified here.

  3  THE CALIBRATION RATIO IS NOT CLUSTERED.  pinsignal reports "3.0x more
     losses than the gaussian says" in P2 as a point estimate and recommends
     acting on it, in a population its own 30-close floor forbids claims in.
     Here the ratio gets a close-cluster bootstrap interval.

Estimators for (2) are IMPORTED from pinsignal so the same tested code is
used; everything else is written independently and has its own planted/null
self-test below.

n IS CLOSES.  Bootstraps resample closes, carrying every market and row of a
close together.  Nothing here is claimed on fewer than 30 loss-carrying
closes.
"""
import argparse
import collections
import json
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinsignal as PS                                          # noqa: E402

FEATS = [n for n, _ in PS.FEATS]
ROWS_F = os.path.join("C:\\kals-repo", "results",
                      "RESULTS_pinsignal_rows.jsonl")
RAW_F = os.path.join("C:\\kals-repo", "results", "pindata", "rows.jsonl")


# ---------------------------------------------------------------------------
# top-vs-bottom quintile loss-rate difference, with a close-cluster bootstrap
# ---------------------------------------------------------------------------
def topbot(rows, name, nb=5, boots=1500, seed=17):
    use = [r for r in rows if r["f"].get(name) is not None]
    if len(use) < 200:
        return None
    cuts = PS.quantile_cuts([r["f"][name] for r in use], nb)
    if not cuts:
        return None
    for r in use:
        r["_b"] = PS.bucket_of(r["f"][name], cuts)
    seen = sorted({r["_b"] for r in use})
    if len(seen) < 2:
        return None
    remap = {b: k for k, b in enumerate(seen)}
    for r in use:
        r["_b"] = remap[r["_b"]]
    hi, lo = len(seen) - 1, 0
    byc = collections.defaultdict(lambda: [[0, 0], [0, 0]])
    for r in use:
        if r["_b"] == hi:
            c = byc[r["close"]][1]
        elif r["_b"] == lo:
            c = byc[r["close"]][0]
        else:
            continue
        c[0] += 1
        c[1] += 1 if r["flip"] else 0
    gs = list(byc.values())
    nc = len(gs)
    a = [sum(g[1][i] for g in gs) for i in (0, 1)]
    b = [sum(g[0][i] for g in gs) for i in (0, 1)]
    if not a[0] or not b[0]:
        return None
    obs = a[1] / a[0] - b[1] / b[0]
    rnd = random.Random(seed)
    ds = []
    for _ in range(boots):
        a0 = a1 = b0 = b1 = 0
        for _k in range(nc):
            g = gs[rnd.randrange(nc)]
            a0 += g[1][0]
            a1 += g[1][1]
            b0 += g[0][0]
            b1 += g[0][1]
        if a0 and b0:
            ds.append(a1 / a0 - b1 / b0)
    ds.sort()
    if len(ds) < 20:
        return None
    ci = (ds[int(0.025 * len(ds))], ds[int(0.975 * len(ds))])
    m = sum(ds) / len(ds)
    se = math.sqrt(sum((d - m) ** 2 for d in ds) / (len(ds) - 1))
    return {"obs": obs, "ci": ci, "se": se, "mde": 2.80 * se,
            "rows": len(use), "n_closes": nc,
            "loss_closes": len({r["close"] for r in use if r["flip"]})}


def calib(rows, boots=3000, seed=23):
    """Observed loss rate over model-predicted, with a close-cluster CI."""
    byc = collections.defaultdict(lambda: [0, 0, 0.0])
    for r in rows:
        pm = r["f"].get("pmod")
        if pm is None:
            continue
        g = byc[r["close"]]
        g[0] += 1
        g[1] += 1 if r["flip"] else 0
        g[2] += pm
    gs = list(byc.values())
    nc = len(gs)
    if nc < 2:
        return None
    n = sum(g[0] for g in gs)
    f = sum(g[1] for g in gs)
    p = sum(g[2] for g in gs)
    rnd = random.Random(seed)
    rs = []
    for _ in range(boots):
        bf = bp = 0.0
        for _k in range(nc):
            g = gs[rnd.randrange(nc)]
            bf += g[1]
            bp += g[2]
        if bp > 0:
            rs.append(bf / bp)
    rs.sort()
    return {"obs": f / n, "pred": p / n,
            "ratio": (f / p) if p else float("nan"),
            "ci": (rs[int(0.025 * len(rs))], rs[int(0.975 * len(rs))]),
            "p_le_1": sum(1 for x in rs if x <= 1) / len(rs),
            "n": n, "closes": nc,
            "loss_closes": sum(1 for g in gs if g[1])}


def split_by_close(rows):
    cs = sorted({r["close"] for r in rows})
    mid = cs[len(cs) // 2]
    return ([r for r in rows if r["close"] < mid],
            [r for r in rows if r["close"] >= mid], mid)


# ---------------------------------------------------------------------------
def _world(kind, seed=4, nclose=200, nmk=6, nrow=20):
    """kind: null | both | firsthalf | overconf | calibrated."""
    rnd = random.Random(seed)
    rows = []
    for c in range(nclose):
        close = 1788000000 + c * 900
        first = c < nclose // 2
        for m in range(nmk):
            q = rnd.random()
            if kind == "null":
                p = 0.12
            elif kind == "both":
                p = 0.02 + 0.40 * q ** 3
            elif kind == "firsthalf":
                p = (0.02 + 0.40 * q ** 3) if first else 0.12
            elif kind == "overconf":
                p = 0.15
            else:
                p = 0.05 + 0.10 * q
            pm = p if kind == "calibrated" else 0.05
            won = rnd.random() > 0.5
            lost = rnd.random() < p
            for k in range(nrow):
                sy = (not won) if lost else won
                rows.append({"tk": "T%d-%d" % (c, m), "close": close,
                             "sec": close - 90 + k, "price": 0.95,
                             "side_yes": sy, "flip": sy != won,
                             "f": {"q": q + rnd.random() * 1e-9,
                                   "noise": rnd.random(), "pmod": pm}})
    return rows


def selftest():
    print("SELF-TEST -- pinsignal_verify")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    g = topbot(_world("both", seed=4), "q")
    ck(g["obs"] > 0.20 and g["ci"][0] > 0,
       "planted world: top-vs-bottom is large and its CI excludes zero "
       "(%.3f %s)" % (g["obs"], tuple(round(x, 3) for x in g["ci"])))
    bad = 0
    for s in (11, 12, 13, 14, 15):
        g = topbot(_world("null", seed=s), "q")
        if g["ci"][0] > 0 or g["ci"][1] < 0:
            bad += 1
    ck(bad == 0, "null world: the CI excludes zero in %d of 5 seeds" % bad)
    g = topbot(_world("both", seed=4), "noise")
    ck(g["ci"][0] <= 0 <= g["ci"][1],
       "a pure-noise feature finds nothing in a world that HAS a signal (%s)"
       % (tuple(round(x, 3) for x in g["ci"]),))

    w = _world("both", seed=6)
    A, B, _ = split_by_close(w)
    ga, gb = topbot(A, "q"), topbot(B, "q")
    ck(ga["ci"][0] > 0 and gb["ci"][0] > 0,
       "a REAL effect survives in BOTH halves of the tape")
    w = _world("firsthalf", seed=6)
    A, B, _ = split_by_close(w)
    ga, gb = topbot(A, "q"), topbot(B, "q")
    ck(ga["ci"][0] > 0, "a half-only effect is found in the half that has it")
    ck(gb["ci"][0] <= 0 <= gb["ci"][1],
       "and is NOT found in the other half -- the split detects an overfit "
       "(%s)" % (tuple(round(x, 3) for x in gb["ci"]),))

    c = calib(_world("overconf", seed=8))
    ck(c["ci"][0] > 1.0,
       "an overconfident model: ratio CI excludes 1 (%.2f %s)"
       % (c["ratio"], tuple(round(x, 2) for x in c["ci"])))
    c = calib(_world("calibrated", seed=8))
    ck(c["ci"][0] <= 1.0 <= c["ci"][1],
       "a CALIBRATED model: ratio CI contains 1 (%.2f %s)"
       % (c["ratio"], tuple(round(x, 2) for x in c["ci"])))

    ck(abs(PS.trade_pnl(0.95, False) - 4.66) < 1e-9,
       "a 95c winner nets 4.66c after the 0.34c fee")
    ck(abs(PS.trade_pnl(0.95, True) + 95.34) < 1e-9,
       "a 95c loser costs 95.34c")
    ck(abs(PS.billed_fee(0.16, 12.37) - 0.1164) < 1e-9,
       "the fee reproduces the operator's real charge (12.37 @ 0.16 = 0.1164)")

    print("SELF-TEST " + ("PASSED" if not fails
                          else "FAILED (%d)" % len(fails)))
    return not fails


# ---------------------------------------------------------------------------
def load():
    side = {}
    with open(RAW_F, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            side[(d["tk"], d["sec"])] = d["side_yes"]
    rows = []
    miss = 0
    with open(ROWS_F, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            s = side.get((d["tk"], d["sec"]))
            if s is None:
                miss += 1
                continue
            d["side_yes"] = s
            rows.append(d)
    return rows, miss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", default=os.path.join(
        "C:\\kals-repo", "results", "RESULTS_pinsignal_verify.md"))
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    rows, miss = load()
    print("  %d rows joined (%d lost the side_yes join)" % (len(rows), miss))
    if not rows:
        print("  loaded nothing")
        return
    L = ["# pinsignal_verify -- adversarial check of pinsignal.py\n",
         "Generated %s. %d rows joined, %d lost the join.\n"
         % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            len(rows), miss)]

    P1 = rows
    P2 = [r for r in rows if r["in_p2"]]
    P1H = [r for r in P1 if r["tau"] >= 45]
    POPS = [("P1", P1), ("P1_tau45+", P1H), ("P2", P2)]

    L.append("\n## 1. TEMPORAL SPLIT -- does anything hold out of sample?\n")
    for tag, P in POPS:
        A, B, mid = split_by_close(P)
        la = len({r["close"] for r in A if r["flip"]})
        lb = len({r["close"] for r in B if r["flip"]})
        L.append("\n### %s: split at close %d (%s)\n"
                 % (tag, mid, time.strftime("%Y-%m-%dT%H:%MZ",
                                            time.gmtime(mid))))
        L.append("early half %d rows / %d closes / **%d loss-carrying "
                 "closes**; late half %d rows / %d closes / **%d "
                 "loss-carrying closes**.\n"
                 % (len(A), len({r["close"] for r in A}), la,
                    len(B), len({r["close"] for r in B}), lb))
        if la < 30 or lb < 30:
            L.append("\n**AT LEAST ONE HALF IS BELOW THE 30-CLOSE FLOOR "
                     "(%d / %d). NO SIGNIFICANCE IS CLAIMED FOR THIS SPLIT "
                     "-- it is a sign-and-size consistency check only.**\n"
                     % (la, lb))
        L.append("| feature | full | early | late | same sign? | early CI "
                 "| late CI |")
        L.append("|---|---|---|---|---|---|---|")
        for nm in FEATS:
            gf, ga, gb = topbot(P, nm), topbot(A, nm), topbot(B, nm)
            if gf is None or ga is None or gb is None:
                L.append("| `%s` | NOT TESTED (too few rows) | | | | | |"
                         % nm)
                continue
            same = "yes" if ga["obs"] * gb["obs"] > 0 else "**NO**"
            L.append("| `%s` | %+.2f | %+.2f | %+.2f | %s | [%+.1f,%+.1f] | "
                     "[%+.1f,%+.1f] |"
                     % (nm, 100 * gf["obs"], 100 * ga["obs"],
                        100 * gb["obs"], same,
                        100 * ga["ci"][0], 100 * ga["ci"][1],
                        100 * gb["ci"][0], 100 * gb["ci"][1]))
            print("    %-10s %-12s full %+7.2f early %+7.2f late %+7.2f %s"
                  % (tag, nm, 100 * gf["obs"], 100 * ga["obs"],
                     100 * gb["obs"], same), flush=True)

    L.append("\n---\n\n## 2. `lgap` and friends with `z` held fixed -- the "
             "test pinsignal's prose asserts but its PAIRS list omits\n")
    L.append("\n| population | feature | held fixed | rows | loss-closes | "
             "top-bottom | 95% CI | MDE | permutation p |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for tag, P in POPS:
        for nm, sc in (("lgap", "z"), ("pmod", "lgap"), ("z", "lgap"),
                       ("gap", "z"), ("price", "z")):
            g = PS.analyse_strat(P, nm, sc, nb=3, ns=5, boots=1000, shufs=250)
            if g is None:
                L.append("| %s | `%s` | `%s` | NOT TESTED | | | | | |"
                         % (tag, nm, sc))
                continue
            L.append("| %s | `%s` | `%s` | %d | %d | **%+.2f pp** | "
                     "[%+.2f, %+.2f] | %.2f pp | %.4f |"
                     % (tag, nm, sc, g["rows"], g["loss_closes"],
                        100 * g["obs"], 100 * g["ci"][0], 100 * g["ci"][1],
                        100 * g["mde"], g["p_shuffle"]))
            print("    STRAT %-10s %-6s|%-6s %+7.2fpp CI [%+.2f,%+.2f] "
                  "p %.4f" % (tag, nm, sc, 100 * g["obs"],
                              100 * g["ci"][0], 100 * g["ci"][1],
                              g["p_shuffle"]), flush=True)
    L.append("\nNOTE: `analyse_strat` runs 250 shuffles here, so its "
             "permutation p CANNOT go below 1/251 = **0.0040** -- which is "
             "ABOVE pinsignal's own Bonferroni threshold of 0.0022. No "
             "stratified test in either file can clear that bar by "
             "construction.\n")

    L.append("\n---\n\n## 3. the calibration ratio with a close-cluster "
             "interval\n")
    L.append("\n| population | rows | closes | loss-closes | observed | "
             "model said | ratio | 95% CI on the ratio |")
    L.append("|---|---|---|---|---|---|---|---|")
    for tag, P in POPS + [("P2M (one trade/market)",
                           PS.first_per_market(P2)),
                          ("P1M (one trade/market)",
                           PS.first_per_market(P1))]:
        c = calib(P)
        L.append("| %s | %d | %d | %d | %.3f%% | %.3f%% | **%.2fx** | "
                 "[%.2f, %.2f] |"
                 % (tag, c["n"], c["closes"], c["loss_closes"],
                    100 * c["obs"], 100 * c["pred"], c["ratio"],
                    c["ci"][0], c["ci"][1]))
        print("    CALIB %-24s %.2fx [%.2f,%.2f] loss-closes %d"
              % (tag, c["ratio"], c["ci"][0], c["ci"][1], c["loss_closes"]),
              flush=True)

    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n  wrote %s" % a.out)


if __name__ == "__main__":
    main()
