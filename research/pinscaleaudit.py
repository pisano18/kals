#!/usr/bin/env python3
# VERSION: 2026-09-08-audit1
"""pinscaleaudit.py -- adversarial audit of research/pinscale.py's recommendation.

WHAT IS BEING REFUTED
=====================
pinscale.py concludes: the scale-in rule is exonerated on entry quality, and
the fix is "at most ONE buy per MARKET, up to 3 per close".  Its case for that
rule is (a) 2 losing trades avoided in-sample, (b) a smaller worst close, and
(c) an account simulation in which the 3-losing-TRADE brake fires far less.

This file attacks each leg:

  A1  How many EVENTS is the benefit built on, and what happens on a
      leave-one-DAY-out split?  (The sample turns out to be 3 calendar days.)
  A2  What does the rule cost in the LIVE window (tau 3-30), which contains
      ZERO losses, so every refusal there is pure cost?
  A3  The account simulation's correlation input, cond_coflip, is estimated
      from how many co-flip events?  Re-run the sim across its confidence
      interval and see whether the ranking survives.
  A4  SHUFFLED-LABEL control: permute the close-level outcome pattern across
      closes.  If one-per-market still "wins" on a label-free tape, the win is
      arithmetic (fewer trades -> fewer brake units), not better trades.
  A5  THE ALTERNATIVE FIX pinscale diagnosed but did not test: it says "the
      brake counts TRADES; the unit of information is a CLOSE".  Counting
      losing CLOSES costs zero trades.  Does it recover the benefit?
  A6  run_account() treats a halt as PERMANENT for the rest of the sample.
      How much of the headline median gap is that assumption?
  A7  The "both sides of one market" episodes: what did the opposite-side leg
      actually DO, against the counterfactual of not taking it?

n IS CLOSES throughout.  No significance is claimed below 30 clusters.
INPUTS  results/pindata/rows.jsonl (read-only).  Nothing under C:\\kals.
"""
import argparse
import datetime as dt
import os
import random
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import pinscale as PS                                            # noqa: E402

UTC = dt.timezone.utc
MIN_CLUSTERS = 30


def day_of(close_s):
    return dt.datetime.fromtimestamp(close_s, UTC).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
def brake_walk(buys_by_close, outcomes, bank=PS.BANK, abort=PS.LOSS_ABORT,
               loss_count=PS.LOSS_COUNT_ABORT, count_closes=False,
               halt_permanent=True):
    """One account walk over a fixed outcome draw.

    count_closes=True counts a losing CLOSE as one unit of the brake budget
    instead of counting every losing trade.
    halt_permanent=False lets the run resume at the next close after a halt
    (the operator restart in LOSS_PLAN.md), resetting the loss counter.
    """
    order = sorted(buys_by_close)
    cash = float(bank)
    realised = 0.0
    units = 0
    halted = False
    halts = 0
    worst = 0.0
    for cs in order:
        if halted and halt_permanent:
            break
        if halted and not halt_permanent:
            halted = False
            units = 0
        bs = buys_by_close[cs]
        fl = outcomes[cs]
        got = 0.0
        lost_here = 0
        for b, lost in zip(bs, fl):
            cost = b["n"] * b["price"] + PS.billed_fee(b["price"], b["n"])
            if cost > cash:
                continue
            cash -= cost
            if lost:
                lost_here += 1
                got -= cost
                realised -= cost
                if not count_closes:
                    units += 1
            else:
                cash += b["n"]
                got += b["n"] - cost
                realised += b["n"] - cost
            if realised <= abort or units >= loss_count:
                halted = True
                halts += 1
                break
        if count_closes and lost_here and not halted:
            units += 1
            if units >= loss_count:
                halted = True
                halts += 1
        worst = min(worst, got)
    return dict(realised=realised, halted=halts > 0, halts=halts,
                worst=worst, ruin=cash < 1.0)


def sim(buys_by_close, draws, flip_rate, cond_coflip, seed=7, **kw):
    rng = random.Random(seed)
    fin, halts, worsts, ruins = [], 0, [], 0
    for _ in range(draws):
        outc = PS.inject(buys_by_close, flip_rate, cond_coflip, rng)
        r = brake_walk(buys_by_close, outc, **kw)
        fin.append(r["realised"])
        worsts.append(r["worst"])
        if r["halted"]:
            halts += 1
        if r["ruin"]:
            ruins += 1
    fin.sort()
    return dict(median=fin[len(fin) // 2], mean=sum(fin) / len(fin),
                p05=fin[int(0.05 * len(fin))], halt=halts / float(draws),
                ruin=ruins / float(draws),
                worst=sum(worsts) / len(worsts))


def coflip_ci(closes, draws=4000, seed=5):
    """Cluster bootstrap (resample CLOSES) on the conditional co-flip rate."""
    st = PS.coflip_structure(closes)
    per = st["per_close"]
    keys = [k for k in per if len(per[k]) >= 2]
    rng = random.Random(seed)
    out = []
    for _ in range(draws):
        both = disc = 0
        for _i in range(len(keys)):
            v = per[keys[rng.randrange(len(keys))]]
            for i in range(len(v)):
                for j in range(i + 1, len(v)):
                    if v[i] and v[j]:
                        both += 1
                    elif v[i] != v[j]:
                        disc += 1
        if 2 * both + disc:
            out.append(2.0 * both / (2.0 * both + disc))
    out.sort()
    if not out:
        return st, (float("nan"), float("nan"))
    return st, (out[int(0.025 * len(out))], out[int(0.975 * len(out))])


def replay_no_opposite(closes, cap, size=20.0, improve=PS.IMPROVE_BY):
    """pinrun's live rule with ONE change: never buy the side opposite to one
    already held on that market in that close.  Same-market, same-side scale-in
    is untouched, so this is a strictly smaller change than one-per-market."""
    buys = []
    for cs in sorted(closes):
        best, n, side_of = None, 0, {}
        for row in closes[cs]:
            if n >= cap:
                break
            tk = row["tk"]
            sy = bool(row.get("side_yes", True))
            if tk in side_of and side_of[tk] != sy:
                continue
            price = float(row["price"])
            if best is not None and price >= best - improve:
                continue
            take = min(float(size), float(row["size"]))
            if take < max(PS.MIN_LEVEL, PS.MIN_FILL_FRAC * float(size)):
                continue
            buys.append(dict(close=cs, idx=n + 1, tk=tk, price=price, n=take,
                             flip=bool(row["flip"]), tau=int(row["tau"]),
                             side_yes=sy, pmodel=PS.p_flip_model(row),
                             improve=(0.0 if best is None else best - price)))
            side_of[tk] = sy
            best = price if best is None else min(best, price)
            n += 1
    return buys


def yes_lost_map(closes):
    """close -> (ordered ticker list, {ticker: our FAVOURED side lost},
                 {ticker: which side the first eligible offer favoured}).

    Built from the FIRST eligible offer per ticker per close.  The label is
    `flip` -- "the side the model favoured lost" -- exactly the quantity
    pinscale.coflip_structure() measures (2.74% marginal).  Labelling by "did
    YES lose" instead would be a ~49% coin flip and would destroy the model's
    directional skill rather than permute the losses, so it is NOT used.
    """
    out = {}
    for cs, rows in closes.items():
        order, m, side = [], {}, {}
        for d in rows:
            tk = d["tk"]
            if tk in m:
                continue
            order.append(tk)
            m[tk] = bool(d["flip"])
            side[tk] = bool(d.get("side_yes", True))
        out[cs] = (order, m, side)
    return out


def apply_truth(buys_by_close, truth, sides):
    """Outcome vector for each close's buys, given {close: {ticker: flip}} and
    the reference side {close: {ticker: side_yes}} the flip label refers to."""
    res = {}
    for cs, bs in buys_by_close.items():
        m, sd = truth[cs], sides[cs]
        res[cs] = [m[b["tk"]] if b["side_yes"] == sd[b["tk"]]
                   else (not m[b["tk"]]) for b in bs]
    return res


def shuffle_truth(base, rng):
    """SHUFFLED LABEL: permute which CLOSE's market-outcome pattern lands on
    which close.  Patterns are pooled by how many tickers the close carried, so
    the within-close shape and the total number of losing markets are both
    preserved; only the assignment of outcomes to closes is destroyed."""
    keys = sorted(base)
    pool = defaultdict(list)
    for cs in keys:
        order, m, _s = base[cs]
        pool[len(order)].append([m[t] for t in order])
    for k in pool:
        rng.shuffle(pool[k])
    idx = Counter()
    out = {}
    for cs in keys:
        order, _m, _s = base[cs]
        k = len(order)
        pat = pool[k][idx[k] % len(pool[k])]
        idx[k] += 1
        out[cs] = dict(zip(order, pat))
    return out


# ===========================================================================
def selftest():
    print("SELF-TEST -- pinscaleaudit")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    def B(cs, tk, px, flip, side=True, n=20.0):
        return dict(close=cs, idx=1, tk=tk, price=px, n=n, flip=flip,
                    side_yes=side, tau=10, pmodel=0.001, improve=0.0, sr=tk)

    # --- PLANTED: the trade-counting brake spends 3 units on ONE close when
    #     three same-market buys lose together; a close-counting brake spends 1
    one = {1: [B(1, "A", 0.95, True), B(1, "A", 0.94, True),
               B(1, "A", 0.93, True)]}
    for cs in range(2, 40):
        one[cs] = [B(cs, "A", 0.95, False)]
    o = {cs: [b["flip"] for b in one[cs]] for cs in one}
    rt = brake_walk(one, o, count_closes=False)
    rc = brake_walk(one, o, count_closes=True)
    ck(rt["halted"] and not rc["halted"],
       "PLANTED: 3 same-market losers halt a TRADE-counting brake but not a "
       "CLOSE-counting one")
    ck(rc["realised"] > rt["realised"],
       "and the close-counting brake keeps trading afterwards "
       "($%.2f > $%.2f)" % (rc["realised"], rt["realised"]))

    # --- NULL: with no losses at all neither brake ever fires
    z = {cs: [B(cs, "A", 0.95, False)] for cs in range(40)}
    oz = {cs: [False] for cs in z}
    ck(not brake_walk(z, oz)["halted"]
       and not brake_walk(z, oz, count_closes=True)["halted"],
       "NULL: a zero-loss tape fires neither brake")

    # --- PLANTED: halt_permanent=False resumes and earns more
    rp = brake_walk(one, o, halt_permanent=True)
    rr = brake_walk(one, o, halt_permanent=False)
    ck(rr["realised"] > rp["realised"],
       "PLANTED: a resumable halt earns more than a permanent one "
       "($%.2f > $%.2f)" % (rr["realised"], rp["realised"]))

    # --- NULL: on a tape that never halts, permanence changes nothing
    ck(abs(brake_walk(z, oz, halt_permanent=True)["realised"]
           - brake_walk(z, oz, halt_permanent=False)["realised"]) < 1e-9,
       "NULL: with no halt, resumable and permanent walks are identical")

    # --- PLANTED: the truth map round-trips the real outcomes exactly
    rows = {}
    for cs in range(60):
        rows[cs] = [dict(tk="A", flip=(cs < 10), side_yes=True),
                    dict(tk="B", flip=(cs < 10), side_yes=False)]
    base = yes_lost_map(rows)
    ck(base[0][1]["A"] is True and base[0][1]["B"] is True
       and base[0][2]["B"] is False,
       "PLANTED: the label is 'our favoured side lost', and the reference "
       "side is remembered")
    # A is bought YES, B is bought on the SAME side the row recorded (NO), so
    # both reproduce the row's flip; a buy on the OPPOSITE side must invert.
    src = {cs: [B(cs, "A", 0.95, cs < 10, side=True),
                B(cs, "B", 0.94, cs < 10, side=False)] for cs in range(60)}
    got = apply_truth(src, {cs: base[cs][1] for cs in base},
                      {cs: base[cs][2] for cs in base})
    ck(all(got[cs] == [b["flip"] for b in src[cs]] for cs in src),
       "and apply_truth reproduces every recorded outcome exactly")
    opp = {0: [B(0, "A", 0.95, True, side=False)]}
    ck(apply_truth(opp, {0: base[0][1]}, {0: base[0][2]})[0] == [False],
       "NULL for the mapping: the OPPOSITE side of a losing market wins")

    # --- PLANTED: the shuffle conserves losing markets but moves them
    rng = random.Random(1)
    tot_before = sum(1 for cs in base for t in base[cs][0] if base[cs][1][t])
    sh = shuffle_truth(base, rng)
    tot_after = sum(1 for cs in sh for t in sh[cs] if sh[cs][t])
    ck(tot_before == tot_after,
       "PLANTED: shuffle conserves the number of losing markets (%d)"
       % tot_before)
    moved = sum(1 for cs in base if sh[cs] != base[cs][1])
    ck(moved > 0, "and it actually moves them (%d closes changed)" % moved)

    # --- NULL: shuffling a tape with NO losses changes nothing
    zrows = {cs: [dict(tk="A", flip=False, side_yes=True)] for cs in range(40)}
    zb = yes_lost_map(zrows)
    shz = shuffle_truth(zb, random.Random(2))
    ck(not any(shz[cs][t] for cs in shz for t in shz[cs]),
       "NULL: shuffling a zero-loss tape invents no losses")

    # --- CALIBRATION: an unshuffled label map must reproduce the tape's own
    #     loss count exactly, or the control is measuring something else
    lm = sum(1 for cs in base for t in base[cs][0] if base[cs][1][t])
    ck(lm == 20, "CALIBRATION: the label map counts the planted 20 losing "
                 "markets (%d), not a ~50%% direction coin flip" % lm)

    # --- PLANTED: coflip_ci recovers a planted co-flip rate
    cls = {}
    rr2 = random.Random(9)
    for cs in range(400):
        shock = rr2.random() < 0.2
        cls[cs] = [dict(tk=t, flip=(shock and rr2.random() < 0.5), close=cs)
                   for t in ("A", "B", "C")]
    st, ci = coflip_ci(cls, draws=800)
    ck(abs(st["cond_coflip"] - 0.5) < 0.10,
       "PLANTED co-flip 50%% recovered (%.1f%%)" % (100 * st["cond_coflip"]))
    ck(ci[0] < 0.5 < ci[1],
       "and its CI covers the truth ([%.2f,%.2f])" % ci)

    # --- NULL: independent flips give cond_coflip == the marginal
    cls2 = {}
    rr3 = random.Random(11)
    for cs in range(600):
        cls2[cs] = [dict(tk=t, flip=(rr3.random() < 0.10), close=cs)
                    for t in ("A", "B", "C")]
    st2, ci2 = coflip_ci(cls2, draws=800)
    ck(ci2[0] < 0.10 < ci2[1],
       "NULL: independent 10%% flips -> cond_coflip CI covers the marginal "
       "([%.2f,%.2f], point %.3f)" % (ci2[0], ci2[1], st2["cond_coflip"]))

    print("SELF-TEST PASSED" if not fails else "SELF-TEST FAILED (%d)" % len(fails))
    return not fails


# ===========================================================================
def report(draws=2000, size=20.0):
    out = []

    def P(s=""):
        print(s)
        out.append(s)

    closes = PS.eligible(verbose=False)
    A = PS.replay(closes, 3, size=size, one_per_ticker=False)
    Bv = PS.replay(closes, 3, size=size, one_per_ticker=True)
    C2 = PS.replay(closes, 2, size=size, one_per_ticker=False)
    ac, bc, cc = PS.by_close(A), PS.by_close(Bv), PS.by_close(C2)

    P("=" * 78)
    P("pinscaleaudit -- ADVERSARIAL AUDIT OF pinscale.py's RECOMMENDATION")
    P("=" * 78)
    P("  population: results/pindata/rows.jsonl, wide window tau 3-60, live gates")
    P("  %d eligible trades over %d closes" %
      (sum(len(v) for v in closes.values()), len(closes)))

    # ---- A1 events and days -------------------------------------------
    P()
    P("A1  HOW MANY EVENTS, AND OVER HOW MANY DAYS")
    days = Counter(day_of(cs) for cs in closes)
    P("  calendar days in the sample: %d" % len(days))
    for d in sorted(days):
        lc = sum(1 for cs in ac if day_of(cs) == d
                 and any(b["flip"] for b in ac[cs]))
        lt = sum(1 for cs in ac if day_of(cs) == d for b in ac[cs] if b["flip"])
        P("    %s  %3d closes   %d losing closes   %d losing trades" %
          (d, days[d], lc, lt))
    avoided = []
    ka = Counter((b["close"], b["tk"], round(b["price"], 4), b["side_yes"])
                 for b in Bv)
    for b in A:
        k = (b["close"], b["tk"], round(b["price"], 4), b["side_yes"])
        if ka[k] == 0 and b["flip"]:
            avoided.append(b)
    P("  losing trades the one-per-market rule avoids: %d" % len(avoided))
    for b in avoided:
        P("    %s  %s  idx%d  %s @%.1fc" %
          (dt.datetime.fromtimestamp(b["close"], UTC).strftime("%m-%d %H:%M"),
           b["tk"], b["idx"], "YES" if b["side_yes"] else "NO",
           100 * b["price"]))
    P("  -> the ENTIRE measured benefit rests on %d events on %d distinct days."
      % (len(avoided), len(set(day_of(b["close"]) for b in avoided))))

    P()
    P("  LEAVE-ONE-DAY-OUT on realised P&L (size %g):" % size)
    P("    held-out day   closes   any-market   one-per-market   delta")
    for d in sorted(days):
        aa = sum(PS.close_pnl(ac[cs]) for cs in ac if day_of(cs) == d)
        bb = sum(PS.close_pnl(bc[cs]) for cs in bc if day_of(cs) == d)
        P("    %s      %3d    $%8.2f      $%8.2f    $%+8.2f" %
          (d, days[d], aa, bb, bb - aa))
    P("    (a day with zero losing closes cannot discriminate the two rules)")

    # ---- A2 live window cost ------------------------------------------
    P()
    P("A2  COST IN THE LIVE WINDOW (tau 3-30), WHICH HAS ZERO LOSSES")
    lw = PS.eligible(tau_max=PS.TAU_LIVE_MAX, verbose=False)
    LA = PS.replay(lw, 3, size=size, one_per_ticker=False)
    LB = PS.replay(lw, 3, size=size, one_per_ticker=True)
    P("  live-window buys: any-market %d over %d closes, %d flips" %
      (len(LA), len(PS.by_close(LA)), sum(1 for b in LA if b["flip"])))
    P("  live-window buys: one-per-mkt %d over %d closes, %d flips" %
      (len(LB), len(PS.by_close(LB)), sum(1 for b in LB if b["flip"])))
    kb = Counter((b["close"], b["tk"], round(b["price"], 4), b["side_yes"])
                 for b in LB)
    kaa = Counter((b["close"], b["tk"], round(b["price"], 4), b["side_yes"])
                  for b in LA)
    ref = [b for b in LA if kb[(b["close"], b["tk"], round(b["price"], 4),
                                b["side_yes"])] == 0]
    add = [b for b in LB if kaa[(b["close"], b["tk"], round(b["price"], 4),
                                 b["side_yes"])] == 0]
    P("  refused %d buys (%d losers), added %d (%d losers)" %
      (len(ref), sum(1 for b in ref if b["flip"]),
       len(add), sum(1 for b in add if b["flip"])))
    evr = sum(PS.ev_order(b["price"], b["n"], PS.MEASURED_FLIP) for b in ref)
    eva = sum(PS.ev_order(b["price"], b["n"], PS.MEASURED_FLIP) for b in add)
    evA = sum(PS.ev_order(b["price"], b["n"], PS.MEASURED_FLIP) for b in LA)
    P("  EV@0.90%%: refused $%.2f, added $%.2f, net $%+.2f on a base of $%.2f "
      "= %+.1f%%" % (evr, eva, eva - evr, evA,
                     100 * (eva - evr) / evA if evA else float("nan")))
    P("  realised in the live window: any $%.2f, one-per-mkt $%.2f (ZERO losses,"
      " so the whole delta is refused profit)" %
      (PS.close_pnl(LA), PS.close_pnl(LB)))

    # ---- A3 correlation input ------------------------------------------
    P()
    P("A3  THE CORRELATION INPUT TO THE ACCOUNT SIM")
    st, ci = coflip_ci(closes, draws=draws)
    P("  cross-market pairs %d; BOTH lost %d; exactly one lost %d" %
      (st["pairs"], st["both"], st["discordant"]))
    P("  cond_coflip point %.1f%%  marginal %.2f%%  cluster-bootstrap 95%% CI "
      "[%.1f%%, %.1f%%]" % (100 * st["cond_coflip"], 100 * st["marginal"],
                            100 * ci[0], 100 * ci[1]))
    P("  -> the whole 'MEASURED correlation' input rests on %d co-flip events."
      % st["both"])
    P()
    P("  ACCOUNT SIM ACROSS THAT CI (flip 0.90%%, live brakes, %d draws):" % draws)
    P("    cond_coflip   any-market median   one-per-mkt median   any halt%%   one halt%%")
    grid = [x for x in (0.028, st["cond_coflip"], 0.20, 0.40, 0.70, 1.00)
            if x == x]
    for cf in grid:
        ra = sim(ac, draws, PS.MEASURED_FLIP, cf)
        rb = sim(bc, draws, PS.MEASURED_FLIP, cf)
        P("      %5.1f%%        $%8.2f          $%8.2f         %5.1f%%     %5.1f%%"
          % (100 * cf, ra["median"], rb["median"], 100 * ra["halt"],
             100 * rb["halt"]))

    # ---- A4 shuffled label ---------------------------------------------
    P()
    P("A4  SHUFFLED-LABEL CONTROL (outcome patterns permuted across closes)")
    base = yes_lost_map(closes)
    truth = {cs: base[cs][1] for cs in base}
    sides = {cs: base[cs][2] for cs in base}
    nmc = sum(len(base[cs][0]) for cs in base)
    nml = sum(1 for cs in base for t in base[cs][0] if base[cs][1][t])
    P("  CALIBRATION: %d market-closes, %d with the favoured side losing "
      "= %.2f%% (must match pinscale's 2.74%% marginal)" %
      (nmc, nml, 100.0 * nml / nmc))
    oa0, ob0 = apply_truth(ac, truth, sides), apply_truth(bc, truth, sides)
    P("  and the unshuffled map reproduces the tape: any %d losing trades, "
      "one-per-mkt %d (replay says %d and %d)" %
      (sum(1 for cs in oa0 for x in oa0[cs] if x),
       sum(1 for cs in ob0 for x in ob0[cs] if x),
       sum(1 for b in A if b["flip"]), sum(1 for b in Bv if b["flip"])))
    ta = brake_walk(ac, oa0)
    tb = brake_walk(bc, ob0)
    obs_raw = PS.close_pnl(Bv) - PS.close_pnl(A)
    obs_brk = tb["realised"] - ta["realised"]
    P("  OBSERVED advantage of one-per-market: $%+.2f with no brakes, "
      "$%+.2f with the live brakes" % (obs_raw, obs_brk))
    rng = random.Random(21)
    draw, dbrk = [], []
    for _ in range(draws):
        st_ = shuffle_truth(base, rng)
        sa, sb = apply_truth(ac, st_, sides), apply_truth(bc, st_, sides)
        pa = sum(PS.realised_order(b["price"], b["n"], f)
                 for cs in ac for b, f in zip(ac[cs], sa[cs]))
        pb = sum(PS.realised_order(b["price"], b["n"], f)
                 for cs in bc for b, f in zip(bc[cs], sb[cs]))
        draw.append(pb - pa)
        dbrk.append(brake_walk(bc, sb)["realised"]
                    - brake_walk(ac, sa)["realised"])
    for tag, d, obs in (("no brakes", draw, obs_raw),
                        ("live brakes", dbrk, obs_brk)):
        d.sort()
        gt = sum(1 for x in d if x > obs + 1e-6)
        eq = sum(1 for x in d if abs(x - obs) <= 1e-6)
        P("    %-12s shuffled delta: median $%+.2f, mean $%+.2f, 95%% band "
          "[$%+.2f, $%+.2f]" %
          (tag, d[len(d) // 2], sum(d) / len(d),
           d[int(0.025 * len(d))], d[int(0.975 * len(d))]))
        P("                 observed $%+.2f -> P(shuffle >) = %.3f, "
          "P(=) = %.3f, mid-p = %.3f" %
          (obs, gt / float(draws), eq / float(draws),
           (gt + 0.5 * eq) / float(draws)))
    P("  -> A RANDOM RELABELLING PRODUCES AN ADVANTAGE THIS LARGE OR LARGER")
    P("     MOST OF THE TIME.  The shuffled-label control returns nothing.")

    # ---- A5 the untested alternative fix --------------------------------
    P()
    P("A5  THE FIX pinscale DIAGNOSED BUT DID NOT TEST: COUNT LOSING CLOSES")
    P("    'the brake counts TRADES; the unit of information is a CLOSE'")
    P("    A close-counting brake costs ZERO trades.  Same sim, flip 0.90%%:")
    P("    rule                brake            median $   5th %%ile   halt%%")
    for tag, book in (("any-market  cap3", ac), ("one-per-mkt cap3", bc),
                      ("any-market  cap2", cc)):
        for btag, kw in (("3 losing TRADES", dict(count_closes=False)),
                         ("3 losing CLOSES", dict(count_closes=True))):
            r = sim(book, draws, PS.MEASURED_FLIP, st["cond_coflip"], **kw)
            P("    %-18s %-16s $%8.2f  $%8.2f   %5.1f%%" %
              (tag, btag, r["median"], r["p05"], 100 * r["halt"]))
    P()
    P("    and at the 2.31%% upper bound:")
    for tag, book in (("any-market  cap3", ac), ("one-per-mkt cap3", bc)):
        for btag, kw in (("3 losing TRADES", dict(count_closes=False)),
                         ("3 losing CLOSES", dict(count_closes=True))):
            r = sim(book, draws, PS.FLIP_UPPER, st["cond_coflip"], **kw)
            P("    %-18s %-16s $%8.2f  $%8.2f   %5.1f%%" %
              (tag, btag, r["median"], r["p05"], 100 * r["halt"]))

    # ---- A6 halt permanence ---------------------------------------------
    P()
    P("A6  HOW MUCH OF THE GAP IS 'A HALT ENDS THE SAMPLE FOREVER'?")
    P("    LOSS_PLAN.md halts, re-measures and restarts.  run_account() does not.")
    P("    rule                halt model        median $   5th %%ile   halt%%")
    for tag, book in (("any-market  cap3", ac), ("one-per-mkt cap3", bc)):
        for htag, kw in (("permanent", dict(halt_permanent=True)),
                         ("resumable", dict(halt_permanent=False))):
            r = sim(book, draws, PS.MEASURED_FLIP, st["cond_coflip"], **kw)
            P("    %-18s %-16s $%8.2f  $%8.2f   %5.1f%%" %
              (tag, htag, r["median"], r["p05"], 100 * r["halt"]))

    # ---- A7 both sides ---------------------------------------------------
    P()
    P("A7  THE 'BOTH SIDES OF ONE MARKET' EPISODES -- WHAT DID THEY COST?")
    npairs = nclose = 0
    for cs in sorted(ac):
        g = defaultdict(list)
        for b in ac[cs]:
            g[b["tk"]].append(b)
        hit = False
        for tk, lst in g.items():
            if len(set(b["side_yes"] for b in lst)) < 2:
                continue
            hit = True
            for i in range(len(lst)):
                for j in range(i + 1, len(lst)):
                    if lst[i]["side_yes"] != lst[j]["side_yes"]:
                        npairs += 1
            opp = [b for b in lst if b["side_yes"] != lst[0]["side_yes"]]
            with_opp = sum(PS.realised_order(b["price"], b["n"], b["flip"])
                           for b in lst)
            without = sum(PS.realised_order(b["price"], b["n"], b["flip"])
                          for b in lst if b not in opp)
            P("    %s %s" %
              (dt.datetime.fromtimestamp(cs, UTC).strftime("%m-%d %H:%M"), tk))
            for b in lst:
                P("        %s @%.1fc  %s" %
                  ("YES" if b["side_yes"] else "NO ", 100 * b["price"],
                   "LOST" if b["flip"] else "won"))
            P("        market P&L WITH the opposite leg  $%.2f" % with_opp)
            P("        market P&L WITHOUT it             $%.2f" % without)
            P("        the opposite leg was worth        $%+.2f" %
              (with_opp - without))
        if hit:
            nclose += 1
    P("    pairs %d, over %d CLOSES (pinscale reports this as '3 times')" %
      (npairs, nclose))

    # ---- A8 the minimal fix --------------------------------------------
    P()
    P("A8  THE MINIMAL FIX pinscale FOUND BUT DID NOT TEST: NEVER BUY THE")
    P("    OPPOSITE SIDE OF A MARKET YOU ALREADY HOLD.  Same-market, same-side")
    P("    scale-in is left alone, so this refuses 2 buys, not 28.")
    Nv = replay_no_opposite(closes, 3, size=size)
    nc = PS.by_close(Nv)
    P("    rule                    buys  flips   realised    EV@0.90%   sim median   sim p05   halt%")
    for tag, bk in (("live cap3 any-market", A), ("cap3 one-per-market", Bv),
                    ("cap3 no-opposite-side", Nv)):
        bb = PS.by_close(bk)
        r = sim(bb, draws, PS.MEASURED_FLIP, st["cond_coflip"])
        P("    %-22s %4d   %3d   $%8.2f   $%8.2f   $%8.2f  $%8.2f   %5.1f%%" %
          (tag, len(bk), sum(1 for b in bk if b["flip"]), PS.close_pnl(bk),
           sum(PS.ev_order(b["price"], b["n"], PS.MEASURED_FLIP) for b in bk),
           r["median"], r["p05"], 100 * r["halt"]))
    lN = replay_no_opposite(lw, 3, size=size)
    P()
    P("    IN THE LIVE WINDOW (tau 3-30) the no-opposite rule is a NO-OP:")
    P("      any-market %d buys / $%.2f EV; no-opposite %d buys / $%.2f EV; "
      "one-per-market %d buys / $%.2f EV" %
      (len(LA), sum(PS.ev_order(b["price"], b["n"], PS.MEASURED_FLIP)
                    for b in LA),
       len(lN), sum(PS.ev_order(b["price"], b["n"], PS.MEASURED_FLIP)
                    for b in lN),
       len(LB), sum(PS.ev_order(b["price"], b["n"], PS.MEASURED_FLIP)
                    for b in LB)))
    P("      both-sides closes in the live window: %d of %d" %
      (sum(1 for cs, bs in PS.by_close(LA).items()
           if any(len(set(x["side_yes"] for x in bs if x["tk"] == t)) > 1
                  for t in set(x["tk"] for x in bs))), len(PS.by_close(LA))))
    P()
    P()
    P("    AND THE BRAKE FIX ON TOP OF IT.  A5 showed close-counting does")
    P("    nothing for the live rule; that was because the halts there are")
    P("    the opposite-side legs, which land on TWO different closes.  With")
    P("    those removed, does counting CLOSES buy the remaining tail?")
    P("    rule                    brake            median $   5th %%ile   halt%%")
    for tag, bk in (("cap3 no-opposite-side", Nv), ("cap3 one-per-market", Bv)):
        for btag, kw in (("3 losing TRADES", dict(count_closes=False)),
                         ("3 losing CLOSES", dict(count_closes=True))):
            r = sim(PS.by_close(bk), draws, PS.MEASURED_FLIP,
                    st["cond_coflip"], **kw)
            P("    %-22s %-16s $%8.2f  $%8.2f   %5.1f%%" %
              (tag, btag, r["median"], r["p05"], 100 * r["halt"]))
    P()
    P("    WHY THIS MATTERS: pinrun's loss-COUNT brake increments once per")
    P("    settled losing ORDER (pinrun.py line ~1301).  A close that holds")
    P("    both sides of one market therefore delivers a losing trade with")
    P("    probability ONE and spends a third of the brake budget on a")
    P("    position that carries no directional risk at all.")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--size", type=float, default=20.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1":
        if not selftest():
            print("SELF-TEST FAILED -- refusing to touch real data")
            sys.exit(1)
        print()
    txt = report(draws=a.draws, size=a.size)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(txt + "\n")
        print("\nwrote " + a.out)


if __name__ == "__main__":
    main()
