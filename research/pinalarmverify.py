#!/usr/bin/env python3
# VERSION: 2026-09-09-pav1
"""pinalarmverify.py -- ADVERSARIAL verification of research/pinalarm.py.

Refutation attempts, each one a thing pinalarm did NOT do:

  A. HOW MANY DAYS is the loser sample? A "split by day" out-of-sample test
     is only possible if there is more than one day with losses in it.
  B. LEAVE-ONE-LOSER-OUT. The top velocity bucket holds 5 entries and 1
     loser. Delete that one loser and the claimed effect must survive.
  C. BUCKET-EDGE SENSITIVITY. top-minus-bottom is a function of where the
     edges were put, and the edges were chosen after the data was seen.
  D. THE BIG ONE -- THE SAME FEATURE IN THE LARGE POPULATION. The live gate
     leaves 10 losing closes. Dropping the gate and sampling on an EXOGENOUS
     grid (a fixed tau, per the house rule) leaves many more losing closes,
     which clears the 30-cluster floor. If price velocity predicts a flip at
     all it must do it there, with the same sign.
  E. THE RELAXED POPULATION with LOSING CLOSES printed.
  F. MULTIPLE LOOKS -- the Bonferroni threshold the house rule asks for.
  G. FIRST-OF-SECOND vs LAST-OF-SECOND. rows.jsonl records the ask at the
     FIRST qualifying delta of each second (pindata emits once per second and
     then skips the rest); pinalarm's live-loss replay reads the LAST delta of
     each second. Tonight's three velocities are therefore measured on a
     different definition from the winner distribution they are scored
     against. Recompute them on rows.jsonl's own definition, and bound them
     by the intra-second range.

Everything here is read-only. Nothing is written outside results/.
"""
import argparse
import json
import os
import random
import sys
import time as _t
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinalarm as PA                                       # noqa: E402

NL = chr(10)


# ---------------------------------------------------------------------------
def by_market(rows):
    d = defaultdict(list)
    for r in rows:
        d[(r["tk"], int(r["close"]))].append(r)
    for k in d:
        d[k].sort(key=lambda x: -int(x["tau"]))
    return d


def series_both(seq):
    """Feature series expressed from BOTH sides, so a moment can be scored
    from whichever side the model favoured at that moment."""
    out = {}
    for S in (True, False):
        fs = []
        idx = {}
        for x in seq:
            f = PA.feat(x, S)
            if f is None:
                continue
            idx[int(x["tau"])] = len(fs)
            fs.append(f)
        PA.enrich(fs)
        out[S] = (fs, idx)
    return out


def grid_sample(rows, tau_target, gate=False):
    """ONE observation per (market, close), taken at the LAST row whose tau is
    at or above tau_target -- an exogenous grid, not a trade-arrival grid.

    gate=True additionally requires the live rule to have been willing to buy
    at that second; gate=False is the whole tape, which is the point.
    """
    out = []
    for k, seq in by_market(rows).items():
        pick = None
        for x in seq:                     # descending tau
            if int(x["tau"]) < tau_target:
                break
            pick = x
        if pick is None:
            continue
        if gate:
            sd = PA.sd_of(pick["r"], pick.get("sig"))
            if PA.p_lose(abs(float(pick["req"])), sd) > PA.PIN_P:
                continue
            p = float(pick["price"])
            if p > PA.CEILING or PA.ev(p) < PA.EV_FLOOR:
                continue
        S = bool(pick["side_yes"])
        fs, idx = series_both(seq)[S]
        i = idx.get(int(pick["tau"]))
        if i is None:
            continue
        out.append({"tk": pick["tk"], "close": int(pick["close"]),
                    "tau": int(pick["tau"]), "flip": bool(pick["flip"]),
                    "at": fs[i], "price": float(pick["price"])})
    return out


# ---------------------------------------------------------------------------
def cells_of(entries, key, edges):
    cells = []
    for i in range(len(edges) - 1):
        cells.append([e for e in entries
                      if key(e) is not None and key(e) == key(e)
                      and edges[i] <= key(e) < edges[i + 1]])
    return cells


def topbot(entries, key, edges):
    c = cells_of(entries, key, edges)
    if not c[0] or not c[-1]:
        return float("nan")
    return (sum(1 for e in c[-1] if e["flip"]) / len(c[-1])
            - sum(1 for e in c[0] if e["flip"]) / len(c[0]))


def shuffle_p(entries, cells, real, reps=400, seed=5):
    """Cluster-preserving permutation, identical in construction to the one
    pinalarm uses: move each close's NUMBER of losers to another close."""
    byc = defaultdict(list)
    for e in entries:
        byc[e["close"]].append(e)
    closes = list(byc)
    ks = [sum(1 for e in byc[cc] if e["flip"]) for cc in closes]
    rnd = random.Random(seed)
    draws = []
    tries = 0
    while len(draws) < reps and tries < reps * 60:
        tries += 1
        order = closes[:]
        rnd.shuffle(order)
        if any(k > len(byc[cc]) for k, cc in zip(ks, order)):
            continue
        lab = {}
        for k, cc in zip(ks, order):
            grp = byc[cc][:]
            rnd.shuffle(grp)
            for j, e in enumerate(grp):
                lab[id(e)] = (j < k)
        a = sum(1 for e in cells[-1] if lab[id(e)]) / len(cells[-1])
        b = sum(1 for e in cells[0] if lab[id(e)]) / len(cells[0])
        draws.append(a - b)
    if len(draws) < 50:
        return float("nan")
    return (sum(1 for d in draws if d >= real) + 1) / (len(draws) + 1)


def table(entries, key, edges, label, reps=400, seed=5):
    """Bucket table + close-clustered bootstrap + cluster-preserving shuffle.
    n is reported as CLOSES, and as LOSING closes, not as positions."""
    print(NL + "  " + label)
    print("    %-20s %8s %8s %8s %8s %9s"
          % ("bucket", "entries", "closes", "losers", "losCl", "flip rate"))
    c = cells_of(entries, key, edges)
    for i in range(len(edges) - 1):
        sel = c[i]
        nl = sum(1 for e in sel if e["flip"])
        nm = "%s to %s" % (("%g" % edges[i] if edges[i] > -1e17 else "-inf"),
                           ("%g" % edges[i + 1] if edges[i + 1] < 1e17
                            else "+inf"))
        print("    %-20s %8d %8d %8d %8d %8.2f%%"
              % (nm, len(sel), len(set(e["close"] for e in sel)), nl,
                 len(set(e["close"] for e in sel if e["flip"])),
                 100 * (nl / len(sel)) if sel else float("nan")))
    miss = [e for e in entries if key(e) is None or key(e) != key(e)]
    if miss:
        nl = sum(1 for e in miss if e["flip"])
        print("    %-20s %8d %8d %8d %8d %8.2f%%"
              % ("(unavailable)", len(miss),
                 len(set(e["close"] for e in miss)), nl,
                 len(set(e["close"] for e in miss if e["flip"])),
                 100 * nl / len(miss)))
    if not c[0] or not c[-1]:
        print("    a terminal bucket is empty -- no statistic")
        return float("nan"), float("nan")
    real = topbot(entries, key, edges)
    units = ([{"close": e["close"], "g": 1, "f": e["flip"]} for e in c[-1]] +
             [{"close": e["close"], "g": 0, "f": e["flip"]} for e in c[0]])

    def dstat(xs):
        A = [x for x in xs if x["g"] == 1]
        B = [x for x in xs if x["g"] == 0]
        if not A or not B:
            return float("nan")
        return (sum(1 for x in A if x["f"]) / len(A)
                - sum(1 for x in B if x["f"]) / len(B))
    lo, hi = PA.boot(units, dstat, B=1200, seed=17)
    print("    top minus bottom %+.2fpp, 95%% CI [%+.2f, %+.2f]pp"
          % (100 * real, 100 * lo, 100 * hi))
    p = shuffle_p(entries, c, real, reps=reps, seed=seed)
    print("    cluster-preserving shuffle p = %s"
          % (("%.3f" % p) if p == p else "n/a"))
    return real, p


# ---------------------------------------------------------------------------
def _fold(cells, s, ask):
    """Accumulate one ask observation into its second. FIRST is the value
    pindata would have written to rows.jsonl; LAST is the value pinalarm's
    replay reports as 'our ask'."""
    c = cells.get(s)
    if c is None:
        cells[s] = {"first": ask, "last": ask, "lo": ask, "hi": ask, "n": 1}
    else:
        c["last"] = ask
        c["lo"] = min(c["lo"], ask)
        c["hi"] = max(c["hi"], ask)
        c["n"] += 1
    return cells


def replay_asks(hours_stamp="20260909T00", tk=None, seed_snapshot=False):
    """Per-second NO-ask series for one market, recording FIRST-of-second and
    LAST-of-second separately, plus the intra-second range and how much
    resting size the delta-only book never saw.

    NO ask = 1 - best YES bid, which is how a NO buyer crosses.
    """
    import gzip
    import zlib
    tk = tk or PA.LOSS_TK
    yes, no = {}, {}
    seeded_levels = 0
    if seed_snapshot:
        sp = os.path.join(PA.TAPE, "orderbook_snapshot",
                          hours_stamp + ".jsonl.gz")
        try:
            with gzip.open(sp, "rt") as fh:
                for ln in fh:
                    if tk not in ln:
                        continue
                    try:
                        m = json.loads(ln)["msg"]
                    except Exception:
                        continue
                    if m.get("market_ticker") != tk:
                        continue
                    if not (m.get("yes_dollars_fp") or m.get("no_dollars_fp")):
                        continue
                    for key, d in (("yes_dollars_fp", yes),
                                   ("no_dollars_fp", no)):
                        for pair in (m.get(key) or []):
                            try:
                                q = float(pair[1])
                                pr = round(float(pair[0]), 4)
                            except Exception:
                                continue
                            if q > 0:
                                d[pr] = q
                                seeded_levels += 1
                    break
        except (EOFError, zlib.error, OSError) as exc:
            print("    snapshot read failed: %r" % (exc,))
    cells = {}
    ndelta = neg = 0
    dp = os.path.join(PA.TAPE, "orderbook_delta", hours_stamp + ".jsonl.gz")
    try:
        with gzip.open(dp, "rt") as fh:
            for ln in fh:
                if tk not in ln:
                    continue
                try:
                    m = json.loads(ln)["msg"]
                except Exception:
                    continue
                if m.get("market_ticker") != tk:
                    continue
                ts = int(m.get("ts_ms") or 0)
                side = str(m.get("side", "")).lower()
                try:
                    pr = round(float(m.get("price_dollars",
                                           m.get("price"))), 4)
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
                ask = (1.0 - yb) if yb is not None else None
                if ask is None:
                    continue
                _fold(cells, ts // 1000, ask)
    except (EOFError, zlib.error, OSError) as exc:
        print("    delta read failed: %r" % (exc,))
    return cells, {"deltas": ndelta, "neg": neg, "seeded": seeded_levels}


def guard_breakeven(buys, thresh):
    """What flip rate the REFUSED buys must carry for the guard to pay.

    A guard gives up the profit on every winner it refuses and avoids the
    stake on every loser it refuses. Break-even is therefore

        p* = (profit destroyed per refusal) / (average loss avoided)

    and the guard only pays if the refused buys really do flip more often
    than p*. Reported next to the MEASURED flip rate among the refused, with
    the rule-of-three upper bound when that measurement is a zero.
    """
    ref = [e for e in buys if e["at"]["pvel"] is not None
           and e["at"]["pvel"] == e["at"]["pvel"]
           and e["at"]["pvel"] >= thresh]
    if not ref:
        return None
    rw = [e for e in ref if not e["flip"]]
    rl = [e for e in ref if e["flip"]]
    destroyed = sum(PA.pnl(e) for e in rw)
    # average loss a refusal avoids: stake plus fee, priced on the refused set
    avg_loss = sum(e["price"] + PA.fee(e["price"]) for e in ref) / len(ref)
    pstar = (destroyed / len(ref)) / avg_loss if avg_loss > 0 else float("nan")
    meas = len(rl) / len(ref)
    ub = 1.0 - 0.05 ** (1.0 / len(ref))          # one-sided 95%, rule of three
    return {"n": len(buys), "ref": len(ref), "rl": len(rl), "rw": len(rw),
            "destroyed": destroyed, "avg_loss": avg_loss, "pstar": pstar,
            "meas": meas, "ub": ub,
            "base": (sum(1 for e in buys if e["flip"]) / len(buys))}


def _row(tk, close, tau, price, sig=0.001, req=0.002, flip=False,
         side_yes=False, spread=0.01):
    return {"tk": tk, "sr": tk.split("-")[0], "close": close,
            "sec": close - tau, "tau": tau, "r": max(1, tau - 1),
            "price": price, "size": 50.0, "spread": spread,
            "dep_y": 100.0, "dep_n": 100.0, "age_ms": 0, "mu": 0.0,
            "req": req, "cov": 1.0, "spot": 0.0, "sig": sig,
            "side_yes": side_yes, "flip": flip}


def selftest():
    print("SELF-TEST -- pinalarmverify")
    ok = [True]

    def ck(c, m):
        print("  %-4s %s" % ("ok" if c else "FAIL", m))
        if not c:
            ok[0] = False

    # --- PLANTED WORLD: the losers' price collapses before the sampling
    #     second, the winners' price rises. The estimator MUST find it.
    rows = []
    for m in range(40):
        close = 1000 + 100 * m
        lose = (m < 20)
        for tau in range(45, 25, -1):
            px = ((0.95 - 0.02 * (45 - tau)) if lose
                  else (0.80 + 0.004 * (45 - tau)))
            px = min(0.98, max(0.55, px))
            rows.append(_row("KX%d-x" % m, close, tau, round(px, 4),
                             flip=lose))
    E = grid_sample(rows, 30)
    ck(len(E) == 40, "planted: one observation per market (%d)" % len(E))
    ck(sum(1 for e in E if e["flip"]) == 20, "planted: 20 of them lose")
    r, p = table(E, lambda e: e["at"]["pvel"], [-1e18, 0.0, 1e18],
                 "planted world -- the estimator MUST find this")
    ck(r > 0.80, "planted: top-minus-bottom is huge (%+.2fpp)" % (100 * r))
    ck(p <= 0.02, "planted: and the shuffle control agrees (p=%.3f)" % p)

    # --- NULL WORLD: identical price paths, labels drawn independently of
    #     them. The estimator must NOT come back with a positive claim.
    rnd = random.Random(3)
    rows = []
    labs = [True] * 20 + [False] * 20
    rnd.shuffle(labs)
    for m in range(40):
        close = 1000 + 100 * m
        falling = (m % 2 == 0)
        for tau in range(45, 25, -1):
            px = ((0.95 - 0.02 * (45 - tau)) if falling
                  else (0.80 + 0.004 * (45 - tau)))
            px = min(0.98, max(0.55, px))
            rows.append(_row("KX%d-x" % m, close, tau, round(px, 4),
                             flip=labs[m]))
    E = grid_sample(rows, 30)
    r, p = table(E, lambda e: e["at"]["pvel"], [-1e18, 0.0, 1e18],
                 "null world -- the estimator MUST find nothing")
    ck(p > 0.05, "null: the shuffle control refuses the claim (p=%.3f)" % p)
    ck(abs(r) < 0.45, "null: and the point estimate is not large (%+.2fpp)"
       % (100 * r))

    # --- the grid must be exogenous, not a trade-arrival grid
    rows = [_row("KXA-x", 5000, 40, 0.95), _row("KXA-x", 5000, 31, 0.90),
            _row("KXA-x", 5000, 12, 0.80)]
    E = grid_sample(rows, 30)
    ck(len(E) == 1 and E[0]["tau"] == 31,
       "grid: the sample is the last row at or above the target tau (tau %d)"
       % E[0]["tau"])
    ck(grid_sample([_row("KXB-x", 5000, 12, 0.80)], 30) == [],
       "grid: a market with nothing at or above the target tau is DROPPED, "
       "never sampled from later")

    # --- leave-one-out arithmetic
    E = [{"close": 1, "flip": True, "at": {"pvel": 5.0}},
         {"close": 2, "flip": False, "at": {"pvel": 5.0}},
         {"close": 3, "flip": False, "at": {"pvel": -5.0}},
         {"close": 4, "flip": False, "at": {"pvel": -5.0}}]
    ck(abs(topbot(E, lambda e: e["at"]["pvel"], [-1e18, 0.0, 1e18]) - 0.5)
       < 1e-9, "leave-one-out: 50% minus 0% is +50pp")
    ck(abs(topbot([e for e in E if e["close"] != 1],
                  lambda e: e["at"]["pvel"], [-1e18, 0.0, 1e18]))
       < 1e-9, "leave-one-out: drop the only loser and it is +0pp")

    # --- first-of-second vs last-of-second bookkeeping
    cells = {}
    for a in (0.90, 0.95, 0.92):
        _fold(cells, 100, a)
    _fold(cells, 101, 0.80)
    ck(abs(cells[100]["first"] - 0.90) < 1e-12,
       "fold: FIRST of the second is the first delta's ask (rows.jsonl's)")
    ck(abs(cells[100]["last"] - 0.92) < 1e-12,
       "fold: LAST of the second is the last delta's ask (the replay's)")
    ck(abs(cells[100]["lo"] - 0.90) < 1e-12
       and abs(cells[100]["hi"] - 0.95) < 1e-12,
       "fold: and the intra-second range brackets both")
    ck(cells[100]["n"] == 3 and cells[101]["n"] == 1,
       "fold: each second counts its own deltas")
    v_last = 100.0 * (cells[100]["last"] - cells[101]["last"]) / 1.0
    v_first = 100.0 * (cells[100]["first"] - cells[101]["first"]) / 1.0
    ck(abs(v_last - 12.0) < 1e-9 and abs(v_first - 10.0) < 1e-9,
       "fold: the two conventions give DIFFERENT velocities on the same "
       "tape (%.1f vs %.1f c/s)" % (v_last, v_first))

    # --- guard break-even arithmetic, hand-computable
    buys = [{"at": {"pvel": 5.0}, "flip": False, "price": 0.90,
             "close": 1, "tk": "a"},
            {"at": {"pvel": 5.0}, "flip": False, "price": 0.90,
             "close": 2, "tk": "b"},
            {"at": {"pvel": -5.0}, "flip": True, "price": 0.90,
             "close": 3, "tk": "c"}]
    g = guard_breakeven(buys, 4.0)
    # each refused winner earns 1-0.90-fee(0.90) = 0.10 - 0.0063 = 0.0937
    ck(abs(g["destroyed"] - 2 * 0.0937) < 1e-6,
       "guard: profit destroyed is the two refused winners (%.4f)"
       % g["destroyed"])
    ck(abs(g["avg_loss"] - (0.90 + PA.fee(0.90))) < 1e-9,
       "guard: a loss costs the stake plus its fee")
    ck(abs(g["pstar"] - (0.0937 / (0.90 + PA.fee(0.90)))) < 1e-6,
       "guard: break-even flip rate among the refused is %.2f%%"
       % (100 * g["pstar"]))
    ck(g["meas"] == 0.0, "guard: and none of the refused actually flipped")
    ck(abs(g["ub"] - (1 - 0.05 ** 0.5)) < 1e-9,
       "guard: 0 of 2 has a one-sided 95%% upper bound of %.1f%%"
       % (100 * g["ub"]))
    ck(guard_breakeven(buys, 99.0) is None,
       "guard: a threshold nothing reaches returns nothing, not a zero")

    # --- NO LOOKAHEAD: an entry's velocity must be identical when every
    #     later row is deleted from the tape.
    rows = []
    for tau in range(45, 5, -1):
        rows.append(_row("KXL-x", 9000, tau, round(0.95 - 0.005 * (45 - tau),
                                                   4)))
    E = grid_sample(rows, 30)
    keep = [r for r in rows if int(r["tau"]) >= 30]
    E2 = grid_sample(keep, 30)
    ck(len(E) == 1 and len(E2) == 1
       and abs(E[0]["at"]["pvel"] - E2[0]["at"]["pvel"]) < 1e-12,
       "no lookahead: deleting every row after the entry leaves the entry "
       "velocity unchanged (%.4f)" % E[0]["at"]["pvel"])

    print("SELF-TEST " + ("PASSED" if ok[0] else "FAILED"))
    return ok[0]


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows",
                    default=r"C:\kals-repo\results\pindata\rows.jsonl")
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
                rows.append(json.loads(ln))
    rows_all = rows
    print(NL + "  %d rows loaded" % len(rows))

    W = PA.build_entries(rows, 3, 200)
    R = PA.build_entries(rows, 3, 200, pin_p=0.20, ceiling=0.995,
                         ev_floor=-1.0)
    EDG = [-1e18, -0.25, 0.0, 0.25, 1.0, 1e18]

    def day(c):
        return _t.strftime("%Y-%m-%d", _t.gmtime(c))

    # ---------------- A. days -------------------------------------------
    print(NL + "=" * 74)
    print("  A. HOW MANY DAYS OF LOSSES ARE THERE? An out-of-sample split by")
    print("     day is only possible if this number is bigger than one.")
    print("=" * 74)
    alld = sorted(set(day(e["close"]) for e in W))
    print("    the entry tape spans %d UTC days" % len(alld))
    for d in alld:
        sub = [e for e in W if day(e["close"]) == d]
        nl = sum(1 for e in sub if e["flip"])
        print("      %s  %4d entries  %3d closes  %2d losers over %2d closes"
              % (d, len(sub), len(set(e["close"] for e in sub)), nl,
                 len(set(e["close"] for e in sub if e["flip"]))))
    print(NL + "    the same for the whole tape, ungated:")
    allrows_d = defaultdict(set)
    flip_d = defaultdict(set)
    for r in rows:
        allrows_d[day(r["close"])].add((r["tk"], r["close"]))
        if r["flip"]:
            flip_d[day(r["close"])].add((r["tk"], r["close"]))
    for d in sorted(allrows_d):
        print("      %s  %4d market-closes, %3d of them flip at some second"
              % (d, len(allrows_d[d]), len(flip_d[d])))

    # ---------------- B. leave-one-out ----------------------------------
    print(NL + "=" * 74)
    print("  B. LEAVE-ONE-LOSER-OUT on the WIDE price-velocity table")
    print("=" * 74)
    base = topbot(W, lambda e: e["at"]["pvel"], EDG)
    print("    all 12 losers in:                              %+.2fpp"
          % (100 * base))
    worst = None
    for e in [x for x in W if x["flip"]]:
        v = topbot([x for x in W if x is not e],
                   lambda z: z["at"]["pvel"], EDG)
        if worst is None or v < worst[0]:
            worst = (v, e)
    print("    drop the most influential single loser:         %+.2fpp   "
          "(%s, tau %d)" % (100 * worst[0], worst[1]["tk"], worst[1]["tau"]))
    wc = None
    for c in sorted(set(e["close"] for e in W if e["flip"])):
        v = topbot([x for x in W if x["close"] != c],
                   lambda z: z["at"]["pvel"], EDG)
        if wc is None or v < wc[0]:
            wc = (v, c)
    print("    drop the most influential single CLOSE:         %+.2fpp   "
          "(%d = %s)" % (100 * wc[0], wc[1], day(wc[1])))
    pw = shuffle_p([x for x in W if x["close"] != wc[1]],
                   cells_of([x for x in W if x["close"] != wc[1]],
                            lambda e: e["at"]["pvel"], EDG), wc[0])
    print("    and its cluster-preserving shuffle p becomes:   %s"
          % (("%.3f" % pw) if pw == pw else "n/a"))

    # ---------------- C. edge sensitivity -------------------------------
    print(NL + "=" * 74)
    print("  C. BUCKET-EDGE SENSITIVITY. The edges were chosen after the data")
    print("     was seen, and top-minus-bottom is a function of them.")
    print("=" * 74)
    for edges, name in (
            ([-1e18, -0.25, 0.0, 0.25, 1.0, 1e18], "as published"),
            ([-1e18, -0.25, 0.0, 0.25, 0.5, 1e18], "top edge 0.5, not 1"),
            ([-1e18, -0.25, 0.0, 0.25, 2.0, 1e18], "top edge 2, not 1"),
            ([-1e18, -0.25, 0.0, 0.25, 4.0, 1e18], "top edge 4 (the rule)"),
            ([-1e18, 0.0, 1e18], "one cut at zero"),
            ([-1e18, -1.0, 0.0, 1.0, 1e18], "symmetric quarters")):
        c = cells_of(W, lambda e: e["at"]["pvel"], edges)
        if not c[0] or not c[-1]:
            print("    %-24s terminal bucket empty -- no statistic" % name)
            continue
        print("    %-24s top %3d entries %2d losers %2d losing closes "
              "-> %+.2fpp"
              % (name, len(c[-1]), sum(1 for e in c[-1] if e["flip"]),
                 len(set(e["close"] for e in c[-1] if e["flip"])),
                 100 * topbot(W, lambda e: e["at"]["pvel"], edges)))

    # ---------------- D. the large population ---------------------------
    print(NL + "=" * 74)
    print("  D. THE SAME FEATURE WHERE THERE IS POWER. One observation per")
    print("     market-close on an EXOGENOUS grid (the last row at or above a")
    print("     fixed tau), NO live gate. If price velocity predicts a flip")
    print("     at all, it has to do it here, with the same sign.")
    print("=" * 74)
    for tt in (30, 45, 60):
        E = grid_sample(rows, tt, gate=False)
        nl = sum(1 for e in E if e["flip"])
        print(NL + "    --- exogenous grid at tau %d: %d market-closes, %d "
              "flips over %d closes"
              % (tt, len(E), nl, len(set(e["close"] for e in E if e["flip"]))))
        table(E, lambda e: e["at"]["pvel"], EDG,
              "flip rate by PRICE VELOCITY, tau %d, no gate" % tt)
        table(E, lambda e: e["at"]["div"],
              [-1e18, 0.0, 0.01, 0.03, 0.08, 1e18],
              "flip rate by DIVERGENCE, tau %d, no gate" % tt)
    E = grid_sample(rows, 30, gate=True)
    nl = sum(1 for e in E if e["flip"])
    print(NL + "    --- the SAME grid WITH the live gate: %d market-closes, "
          "%d flips over %d closes"
          % (len(E), nl, len(set(e["close"] for e in E if e["flip"]))))
    table(E, lambda e: e["at"]["pvel"], EDG,
          "flip rate by PRICE VELOCITY, tau 30, live gate")

    # ---------------- E. relaxed population -----------------------------
    print(NL + "=" * 74)
    print("  E. THE RELAXED POPULATION with LOSING CLOSES printed. The")
    print("     submission's table omits that column, and it is the one the")
    print("     30-cluster floor is measured on.")
    print("=" * 74)
    table(R, lambda e: e["at"]["pvel"], EDG,
          "RELAXED: flip rate by price velocity")

    # ---------------- F. multiple looks ---------------------------------
    print(NL + "=" * 74)
    print("  F. MULTIPLE LOOKS")
    print("=" * 74)
    print("    pinalarm reports 4 cluster-preserving shuffle p-values and 7")
    print("    bucket tables with bootstrap CIs on the same 12 losers.")
    for k in (1, 4, 7, 11):
        print("      %2d looks -> Bonferroni threshold %.4f; published "
              "p = 0.027 %s" % (k, 0.05 / k,
                                "SURVIVES" if 0.027 <= 0.05 / k else "FAILS"))

    # ---------------- G. the two ask conventions ------------------------
    print(NL + "=" * 74)
    print("  G. TONIGHT'S THREE BUYS UNDER THE OTHER ASK CONVENTION.")
    print("     The winner distribution the three buys are scored against is")
    print("     built from rows.jsonl, whose ask is the FIRST delta of each")
    print("     second. pinalarm's replay reports the LAST. Same tape, two")
    print("     answers.")
    print("=" * 74)
    cells, meta = replay_asks()
    if not cells:
        print("    REPLAY FAILED -- no book. Reporting the failure, not a "
              "number.")
    else:
        print("    deltas %d, negative-size events %d, snapshot levels "
              "seeded %d" % (meta["deltas"], meta["neg"], meta["seeded"]))
        c2, m2 = replay_asks(seed_snapshot=True)
        print("    with the snapshot seeded instead: %d levels, negative-size "
              "events %d" % (m2["seeded"], m2["neg"]))
        PAID = {22: 0.962, 21: 0.956, 17: 0.730}
        print(NL + "    %4s %9s %9s %9s %14s %11s %11s"
              % ("tau", "first", "last", "range", "paid", "v(last)",
                 "v(first)"))
        for t in sorted(PAID, reverse=True):
            s = PA.LOSS_CLOSE - t
            here = cells.get(s)
            ref = cells.get(s - 3) or cells.get(s - 2) or cells.get(s - 4)
            if here is None or ref is None:
                print("    tau %2d: not in the replay" % t)
                continue
            dt = 3
            for cand in (3, 2, 4):
                if cells.get(s - cand) is ref:
                    dt = cand
                    break
            vl = 100.0 * (ref["last"] - PAID[t]) / dt
            vf = 100.0 * (ref["first"] - PAID[t]) / dt
            print("    %4d %8.1fc %8.1fc %6.1f-%.1fc %13.1fc %+10.2f %+10.2f"
                  % (t, 100 * here["first"], 100 * here["last"],
                     100 * here["lo"], 100 * here["hi"], 100 * PAID[t],
                     vl, vf))
        print(NL + "    v(last) is pinalarm's published number; v(first) is")
        print("    the same quantity measured the way every winner it is")
        print("    compared against was measured. Positive = FALLING.")
        # the widest honest bound the intra-second range allows
        print(NL + "    THE BOUND THE INTRA-SECOND RANGE ALLOWS "
              "(paid vs the reference second's cheapest and dearest ask):")
        for t in sorted(PAID, reverse=True):
            s = PA.LOSS_CLOSE - t
            ref = cells.get(s - 3) or cells.get(s - 2) or cells.get(s - 4)
            if ref is None:
                continue
            v_lo = 100.0 * (ref["lo"] - PAID[t]) / 3.0
            v_hi = 100.0 * (ref["hi"] - PAID[t]) / 3.0
            print("      tau %2d: fall is somewhere in [%+.2f, %+.2f] c/s"
                  % (t, v_lo, v_hi))

    # ---------------- H. what the proposed rule must be true to pay -----
    print(NL + "=" * 74)
    print("  H. THE PROPOSED RULE. A guard pays only if the buys it refuses")
    print("     really do flip more often than break-even. Break-even is")
    print("     profit destroyed per refusal divided by the loss a refusal")
    print("     avoids -- pure arithmetic, no model.")
    print("=" * 74)
    BW = PA.build_buys(rows_all, 3, 200)
    BL = PA.build_buys(rows_all, 3, 30)
    sets = (("WIDE  all buys", BW),
            ("WIDE  buys 2-3 only", [b for b in BW if b["buy"] > 1]),
            ("LIVE  all buys", BL),
            ("LIVE  buys 2-3 only", [b for b in BL if b["buy"] > 1]))
    print(NL + "    %-24s %6s %8s %7s %8s %10s %10s %10s"
          % ("population, threshold", "buys", "refused", "losers", "base",
             "break-even", "measured", "95% UB"))
    for name, bs in sets:
        for t in (2.0, 4.0, 8.0):
            g = guard_breakeven(bs, t)
            if g is None:
                print("    %-24s %6d %8d %7s %8s %10s %10s %10s"
                      % ("%s, >=%gc/s" % (name, t), len(bs), 0, "-", "-",
                         "-", "-", "-"))
                continue
            print("    %-24s %6d %8d %7d %7.2f%% %9.2f%% %9.2f%% %9.2f%%"
                  % ("%s, >=%gc/s" % (name, t), g["n"], g["ref"], g["rl"],
                     100 * g["base"], 100 * g["pstar"], 100 * g["meas"],
                     100 * g["ub"]))
    print(NL + "    'break-even' is the flip rate the refused buys need to")
    print("    carry. 'measured' is what they actually carried. '95% UB' is")
    print("    the one-sided upper bound on 'measured' given how few")
    print("    refusals there are -- the honest read of a zero.")
    print(NL + "  DONE.")


if __name__ == "__main__":
    main()
