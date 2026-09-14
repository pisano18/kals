#!/usr/bin/env python3
"""pinsep.py -- is there ANY combination of things, visible at the moment we
buy, that separates our losers from our winners?

THE OPERATOR'S QUESTION, 2026-09-14: "there MUST be something we can look at
all of our losses and see something in common that winners don't have, like
some kind of threshold of 2 or 3 or 4 things being in a certain range."

It is the right question and it has a trap in it. We have ~350 live fills and
about a DOZEN losses. Search a dozen features at twenty thresholds each and
that is ~300 single rules; pair them and it is ~45,000. With twelve losses,
SOMETHING will separate them perfectly by chance alone. A search that only
reports its best find is guaranteed to find one and guaranteed to be useless.

So this file does three things, and the third is the one that matters:

  1. SEARCH -- every single-feature threshold, and every PAIR of them, scored
     on the first 60% of closes only.
  2. HOLDOUT -- the winner is then scored on the last 40%, which the search
     never saw. A rule that reverses here is an artefact, and the first one
     tried on 2026-09-14 did exactly that (+5.36c became -8.51c).
  3. PLACEBO -- the ENTIRE search is re-run many times on SHUFFLED win/loss
     labels. That measures how good a "finding" looks when there is provably
     nothing to find. If the real search does not clearly beat the shuffled
     ones, the answer to the question is no.

Money is per CLOSE, not per fill (hard rule 4). Live fills only.

    python research/pinsep.py --selftest
    python research/pinsep.py
    python research/pinsep.py --placebos 400
"""
import collections
import glob
import json
import os
import random
import sys

# features read straight off the signal record, plus two derived
FEATURES = [
    "conf", "tau", "edge_c", "price", "cushion", "index_age_s",
    "book_age_ms", "level_age_ms", "sigma_rel", "touch", "ladder_total",
]


def cushion(sig):
    """How far the LIVE index sits on the safe side of the strike, in
    one-second moves. Positive = our way."""
    sg, st, sp = sig.get("sigma"), sig.get("strike"), sig.get("spot")
    if not sg or st is None or sp is None:
        return None
    return ((st - sp) if sig.get("want") == "no" else (sp - st)) / sg


def featurise(sig):
    f = sig.get("fair")
    out = {
        "conf": None if f is None else ((1.0 - f) if sig.get("want") == "no" else f),
        "tau": sig.get("tau"),
        "edge_c": sig.get("edge_c"),
        "price": sig.get("price"),
        "cushion": cushion(sig),
        "index_age_s": sig.get("index_age_s"),
        "book_age_ms": sig.get("book_age_ms"),
        "level_age_ms": sig.get("level_age_ms"),
        "touch": sig.get("size"),
        "ladder_total": sig.get("ladder_total"),
    }
    sp, sg = sig.get("spot"), sig.get("sigma")
    out["sigma_rel"] = (sg / sp) if (sp and sg) else None
    return out


def rule_hits(rows, feat, op, thr):
    """Rows a single condition selects. Rows missing the feature never hit --
    absent data is not evidence."""
    out = []
    for r in rows:
        v = r["f"].get(feat)
        if v is None:
            continue
        if (v < thr) if op == "<" else (v > thr):
            out.append(r)
    return out


def score(hits, rows):
    """What blocking `hits` would do, in dollars, and what it costs.

    Returns (money_saved, winners_given_up, losses_avoided). Money saved is
    just minus the P&L of what we would have refused.
    """
    saved = -sum(r["pnl"] for r in hits)
    w = sum(1 for r in hits if r["won"])
    l = len(hits) - w
    return saved, w, l


def candidates(rows, feat, n=12):
    vals = sorted({r["f"][feat] for r in rows if r["f"].get(feat) is not None})
    if len(vals) < 4:
        return []
    step = max(1, len(vals) // n)
    return vals[step::step]


def search(rows, min_losses=2, max_cost_ratio=12.0):
    """Best single rule and best PAIR, by money saved, subject to actually
    catching losses and not costing an absurd number of winners."""
    best = []
    for feat in FEATURES:
        for thr in candidates(rows, feat):
            for op in ("<", ">"):
                h = rule_hits(rows, feat, op, thr)
                if not h:
                    continue
                s, w, l = score(h, rows)
                if l < min_losses or w > max_cost_ratio * max(1, l):
                    continue
                best.append((s, [(feat, op, thr)], w, l))
    singles = sorted(best, reverse=True)[:1]

    pairs = []
    top = sorted(best, reverse=True)[:25]
    for s1, r1, _, _ in top:
        for feat in FEATURES:
            for thr in candidates(rows, feat):
                for op in ("<", ">"):
                    if (feat, op, thr) in r1:
                        continue
                    conds = r1 + [(feat, op, thr)]
                    h = rows
                    for c in conds:
                        h = rule_hits(h, *c)
                    if not h:
                        continue
                    s, w, l = score(h, rows)
                    if l < min_losses or w > max_cost_ratio * max(1, l):
                        continue
                    pairs.append((s, conds, w, l))
    return singles + sorted(pairs, reverse=True)[:1]


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        if not c:
            print("FAIL:", m)
            ok = False
        else:
            print("  ok:", m)

    rnd = random.Random(1)

    # --- A WORLD WITH A PLANTED SEPARATOR -------------------------------
    # every row with tau > 25 loses $10; everything else wins $1.
    planted = []
    for i in range(300):
        tau = rnd.randint(3, 30)
        bad = tau > 25
        planted.append({"f": {k: None for k in FEATURES} | {"tau": tau},
                        "pnl": -10.0 if bad else 1.0, "won": not bad,
                        "close": "c%d" % i})
    found = search(planted)
    ck(any(c[0] == "tau" and c[1] == ">" for _, conds, _, _ in found
           for c in conds),
       "a planted 'tau above 25 always loses' world IS found by the search")

    # --- A WORLD WITH NOTHING PLANTED -----------------------------------
    # same loss rate, but assigned at random and unrelated to any feature.
    null = []
    for i in range(300):
        bad = rnd.random() < 0.05
        null.append({"f": {k: rnd.random() for k in FEATURES},
                     "pnl": -10.0 if bad else 1.0, "won": not bad,
                     "close": "c%d" % i})
    nf = search(null)
    ck(nf, "the search still RETURNS a best rule on pure noise -- which is "
           "exactly why a best rule proves nothing on its own")
    real_saved = found[0][0] if found else 0
    ck(real_saved > 0 and nf and nf[0][0] > 0,
       "and the noise rule even shows a positive dollar saving (%.0f), so "
       "dollars saved is NOT evidence" % (nf[0][0] if nf else 0))

    # --- the placebo must separate those two worlds ---------------------
    def placebo_beat(rows, n=40):
        real = search(rows)
        if not real:
            return 0.0
        target = real[0][0]
        beat = 0
        for _ in range(n):
            sh = [dict(r) for r in rows]
            pnls = [r["pnl"] for r in sh]
            wons = [r["won"] for r in sh]
            idx = list(range(len(sh)))
            rnd.shuffle(idx)
            for j, r in enumerate(sh):
                r["pnl"] = pnls[idx[j]]
                r["won"] = wons[idx[j]]
            s = search(sh)
            if s and s[0][0] >= target:
                beat += 1
        return beat / float(n)

    p_planted = placebo_beat(planted)
    p_null = placebo_beat(null)
    ck(p_planted < 0.10,
       "PLACEBO: shuffling the labels almost never matches the PLANTED "
       "effect (%.0f%% of shuffles)" % (100 * p_planted))
    ck(p_null > p_planted,
       "and it matches the NOISE 'finding' far more often (%.0f%% vs %.0f%%) "
       "-- the placebo is what tells the two apart" % (100 * p_null, 100 * p_planted))

    print("pinsep selftest:", "OK" if ok else "FAILED")
    return ok


def load():
    runs = collections.defaultdict(lambda: {"o": [], "s": [], "g": []})
    for p in sorted(glob.glob(os.path.join("results", "pinrun-live-*.jsonl"))):
        for line in open(p, encoding="utf-8"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            k = d.get("kind")
            if k in ("order", "settled", "signal"):
                runs[p]["osg"[("order", "settled", "signal").index(k)]
                         if False else {"order": "o", "settled": "s",
                                        "signal": "g"}[k]].append(d)
    rows = []
    for _, r in runs.items():
        res = {}
        for s in r["s"]:
            res[(s["ticker"], s.get("want"))] = s.get("result")
        sig = {}
        for s in r["g"]:
            sig.setdefault(s["ticker"], []).append(s)
        for o in r["o"]:
            n = o.get("filled") or 0
            px = o.get("exec_price")
            tk = o["ticker"]
            ss = sig.get(tk)
            if n <= 0 or px is None or not ss:
                continue
            side = ss[0].get("want")
            rr = res.get((tk, side))
            if rr is None:
                continue
            won = (rr == side)
            fee = o.get("fee_total") or 0
            rows.append({
                "f": featurise(ss[0]),
                "pnl": n * (1.0 - px) - fee if won else -(n * px + fee),
                "won": won,
                "close": (o.get("t") or "")[:10] + "|" + tk.rsplit("-", 2)[-2],
                "t": o.get("t") or "",
            })
    return rows


def show(conds):
    return " AND ".join("%s %s %.4g" % c for c in conds)


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0

    n_pl = 200
    if "--placebos" in sys.argv:
        n_pl = int(sys.argv[sys.argv.index("--placebos") + 1])

    rows = load()
    if not rows:
        print("loaded nothing -- no live fills with a matched signal")
        return 0
    losses = sum(1 for r in rows if not r["won"])
    print("\n%d live fills, %d of them losers, over %d closes"
          % (len(rows), losses, len(set(r["close"] for r in rows))))
    print("THE WHOLE QUESTION IS WHETHER %d LOSSES CAN SUPPORT A RULE.\n" % losses)

    closes = sorted(set(r["close"] for r in rows))
    cut = closes[int(0.6 * len(closes))]
    train = [r for r in rows if r["close"] < cut]
    hold = [r for r in rows if r["close"] >= cut]
    print("  search set : %d fills, %d losses (first 60%% of closes)"
          % (len(train), sum(1 for r in train if not r["won"])))
    print("  holdout    : %d fills, %d losses (last 40%%, never searched)\n"
          % (len(hold), sum(1 for r in hold if not r["won"])))

    found = search(train)
    if not found:
        print("  no rule cleared the minimum bar on the search set")
        return 0

    rnd = random.Random(7)
    for saved, conds, w, l in found:
        print("  RULE: block when  %s" % show(conds))
        print("    on the search set : saves $%.2f, gives up %d winners to "
              "avoid %d losses" % (saved, w, l))
        h = hold
        for c in conds:
            h = rule_hits(h, *c)
        hs, hw, hl = score(h, hold)
        print("    ON THE HOLDOUT    : %s $%.2f, gives up %d winners, avoids "
              "%d losses" % ("saves" if hs >= 0 else "COSTS", abs(hs), hw, hl))
        if hs <= 0:
            print("    -> REVERSES OR DOES NOTHING OUT OF SAMPLE. Dead.")
        # placebo on the full set
        beat = 0
        for _ in range(n_pl):
            sh = [dict(r) for r in train]
            pn = [r["pnl"] for r in sh]
            wo = [r["won"] for r in sh]
            idx = list(range(len(sh)))
            rnd.shuffle(idx)
            for j, r in enumerate(sh):
                r["pnl"], r["won"] = pn[idx[j]], wo[idx[j]]
            s = search(sh)
            if s and s[0][0] >= saved:
                beat += 1
        print("    PLACEBO           : %d of %d searches on SHUFFLED "
              "win/loss labels found a rule at least this good = %.0f%%"
              % (beat, n_pl, 100.0 * beat / n_pl))
        if beat > 0.10 * n_pl:
            print("    -> A COIN FLIP FINDS THIS. Not a signal.\n")
        else:
            print("    -> survives the placebo; check the holdout line above.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
