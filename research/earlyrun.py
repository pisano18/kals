#!/usr/bin/env python3
# VERSION: 2026-09-08-er1
"""earlyrun.py -- the measurements and the backtest for IMPROVEMENT 5.

Three plain facts first (the operator asked for these BEFORE any strategy):
  (a) resting size at the touch, both sides, as a function of tau
  (b) the distribution of available net edge as a function of tau
  (c) how many markets the arithmetic lock decides at each tau, and how
      often the lock is WRONG

then the early rule, then the current rule on the same markets so the two
are comparable, then the money decomposition:

      $/day = edge  x  fillable size  x  opportunities

reported as three separate numbers, because a rule that earns 1c on 200
contracts beats one that earns 2.5c on 3.

Everything causal. See early.py's docstring for what is enforced where, and
earlyleak.py for the deliberately-leaking variants that must score better.
"""
import argparse, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import early                                                # noqa: E402
import earlym                                               # noqa: E402
from early import (billed_fee, net_edge, state, tstat, q, MIN_SIZE,
                   EDGE_FLOOR, CAP, MAX_QUOTE_AGE, SERIES_TO_INDEX)

DAY = 86400
# row layout, kept as a tuple because there are millions of them
(C_, TK_, SER_, TAU_, SIDE_, PRICE_, SIZE_, REQ_, M_, RES_, AGE_,
 YB_, YA_, BS_, AS_) = range(15)


def rows_for(ix, meta, grid, mtab, taus, back_days=3, mult=1.0, mfun=None):
    """Every (market, tau) cell with a usable state, quote and M.

    `mult`/`mfun` exist only so earlyleak.py can drive this exact code path
    with a corrupted M. The honest run passes neither.
    """
    YB, YA, BS, AS, AGE = grid
    W = meta["W"]
    out = []
    for i, tk in enumerate(meta["order"]):
        m = meta["markets"][tk]
        iid = SERIES_TO_INDEX.get(m["series"])
        if iid is None:
            continue
        C, K, d, res = m["close_s"], m["K"], m["d"], m["result"]
        for tau in taus:
            if mfun is None:
                Mv, got = earlym.M_for(mtab, iid, tau, C, back_days)
                if Mv is None or got < back_days or Mv <= 0:
                    continue
                Mv *= mult
            else:
                Mv = mfun(ix, iid, C, tau, m)
                if Mv is None or Mv <= 0:
                    continue
            st = state(ix, iid, C, tau, K, d)
            if st is None:
                continue
            k = i * W + tau
            age = AGE[k]
            if age < 0 or age > MAX_QUOTE_AGE:
                continue
            if st["side"] == "yes":
                price, size = YA[k], AS[k]
            else:
                price, size = 1.0 - YB[k], BS[k]
            out.append((C, tk, m["series"], tau, st["side"], float(price),
                        float(size), st["req"], Mv, res, float(age),
                        float(YB[k]), float(YA[k]), float(BS[k]), float(AS[k])))
    return out


# ------------------------------------------------------ (a) (b) (c) ------
def measure(rows, taus, cs=(1.0, 1.5, 2.0, 3.0)):
    print("\n" + "=" * 76)
    print("(a) RESTING SIZE AT THE TOUCH, by tau   [contracts]")
    print("=" * 76)
    print("   tau      n   |  YES-ask side (buy YES)       |  YES-bid side "
          "(buy NO)")
    print("                |   p25  median    p75    mean  |   p25  median"
          "    p75    mean")
    for tau in taus:
        a = [r[AS_] for r in rows if r[TAU_] == tau and r[YA_] < 0.9999]
        b = [r[BS_] for r in rows if r[TAU_] == tau and r[YB_] > 0.0001]
        n = sum(1 for r in rows if r[TAU_] == tau)
        if not a or not b:
            continue
        print("   %3d %7d  | %5.0f %6.0f %6.0f %7.0f  | %5.0f %6.0f %6.0f "
              "%7.0f" % (tau, n, q(a, .25), q(a, .5), q(a, .75),
                         sum(a) / len(a), q(b, .25), q(b, .5), q(b, .75),
                         sum(b) / len(b)))
    print("\n   Cells with no offer at all are excluded from the ask side:")
    print("   yes_ask==1.00 with size 0 is Kalshi's 'nothing offered'.")

    print("\n   share of cells with a REAL offer on the side the model wants")
    print("   (price < 1.00 and at least %g non-fractional contract):" % MIN_SIZE)
    for tau in taus:
        sel = [r for r in rows if r[TAU_] == tau]
        if not sel:
            continue
        ok = sum(1 for r in sel if r[PRICE_] < 0.9999 and r[SIZE_] >= MIN_SIZE)
        print("     tau %3d : %5.1f%%   (%d of %d)"
              % (tau, 100.0 * ok / len(sel), ok, len(sel)))

    print("\n" + "=" * 76)
    print("(b) AVAILABLE NET EDGE on the model's side, by tau  [cents/contract]")
    print("    edge = (1 - price) - fee: what a CERTAIN contract would pay")
    print("=" * 76)
    print("   tau       n     p50     p75     p90     p99   share>=%.1fc"
          % (100 * EDGE_FLOOR))
    for tau in taus:
        e = [100.0 * net_edge(r[PRICE_], max(1.0, min(r[SIZE_], CAP)))
             for r in rows
             if r[TAU_] == tau and r[PRICE_] < 0.9999 and r[SIZE_] >= MIN_SIZE]
        if not e:
            continue
        print("   %3d %7d  %6.2f  %6.2f  %6.2f  %6.2f   %6.1f%%"
              % (tau, len(e), q(e, .5), q(e, .75), q(e, .9), q(e, .99),
                 100.0 * sum(1 for x in e if x >= 100 * EDGE_FLOOR) / len(e)))

    print("\n" + "=" * 76)
    print("(c) HOW MANY MARKETS THE ARITHMETIC LOCK DECIDES, by tau")
    print("    lock: required_move > c * M(index, tau, prior 3 whole days)")
    print("    flip = the lock held and the market settled the OTHER way")
    print("=" * 76)
    for c in cs:
        print("\n   c = %.1f" % c)
        print("     tau       n    locked  locked%    flips   flip%    "
              "median req/M")
        for tau in taus:
            sel = [r for r in rows if r[TAU_] == tau]
            if not sel:
                continue
            lk = [r for r in sel if r[REQ_] > c * r[M_]]
            fl = sum(1 for r in lk if r[RES_] != r[SIDE_])
            rat = [r[REQ_] / r[M_] for r in sel]
            print("     %3d %7d  %8d  %6.1f%%  %7d  %6.3f%%   %9.3f"
                  % (tau, len(sel), len(lk), 100.0 * len(lk) / len(sel), fl,
                     (100.0 * fl / len(lk)) if lk else float("nan"),
                     q(rat, .5)))


# ------------------------------------------------------- the backtest ----
def fire_early(rows, c, cap=CAP, edge_floor=EDGE_FLOOR, taumin=0, taumax=999):
    """Largest tau at which the lock holds AND there is a tradeable quote."""
    per = {}
    for r in rows:
        if taumin <= r[TAU_] <= taumax:
            per.setdefault(r[TK_], []).append(r)
    out = []
    for tk, rs in per.items():
        rs.sort(key=lambda x: -x[TAU_])            # largest tau first
        for r in rs:
            if r[REQ_] <= c * r[M_]:
                continue
            price, size = r[PRICE_], r[SIZE_]
            if price >= 0.9999 or size < MIN_SIZE:
                continue
            cnt = max(1.0, min(size, cap))
            if net_edge(price, cnt) < edge_floor:
                continue
            win = 1.0 if r[RES_] == r[SIDE_] else 0.0
            fee = billed_fee(price, cnt) / cnt
            out.append({"close": r[C_], "tk": tk, "series": r[SER_],
                        "tau": r[TAU_], "side": r[SIDE_], "price": price,
                        "size": size, "cnt": cnt, "win": win, "age": r[AGE_],
                        "pnl_c": 100.0 * (win - price - fee),
                        "edge_c": 100.0 * net_edge(price, cnt),
                        "ratio": r[REQ_] / r[M_]})
            break
    return out


def one_per_close(fires):
    best = {}
    for f in fires:
        b = best.get(f["close"])
        if b is None or f["tau"] > b["tau"] or (
                f["tau"] == b["tau"] and f["edge_c"] > b["edge_c"]):
            best[f["close"]] = f
    return list(best.values())


def report(fires, label, days, indent="  "):
    if not fires:
        print("%s%-30s no fires" % (indent, label))
        return None
    per_close = {}
    for f in fires:
        per_close.setdefault(f["close"], []).append(f)
    cl = [sum(x["pnl_c"] for x in v) for v in per_close.values()]
    pnl = [f["pnl_c"] for f in fires]
    flips = sum(1 for f in fires if f["win"] == 0.0)
    dollars = sum(f["pnl_c"] * f["cnt"] for f in fires) / 100.0
    sizes = [f["cnt"] for f in fires]
    rest = [f["size"] for f in fires]
    mean_edge = sum(f["edge_c"] for f in fires) / len(fires)
    t = tstat(cl)
    print("%s%s" % (indent, label))
    print("%s  n=%d fires over %d closes (%.1f fires/day), %d flips (%.2f%%)"
          % (indent, len(fires), len(per_close), len(fires) / days, flips,
             100.0 * flips / len(fires)))
    print("%s  realised   %+7.3f c/contract    t=%+5.2f  clustered on close "
          "(n=%d closes)" % (indent, sum(pnl) / len(pnl), t, len(cl)))
    print("%s  breakeven flip rate at this edge: %.2f%%   (a flip costs "
          "~%.0fc)" % (indent, mean_edge, 100.0 * (1 - sum(
              f["price"] for f in fires) / len(fires)) + mean_edge))
    print("%s  tau        median %.0f   p25 %.0f   p75 %.0f"
          % (indent, q([f["tau"] for f in fires], .5),
             q([f["tau"] for f in fires], .25),
             q([f["tau"] for f in fires], .75)))
    print("%s  MONEY      edge %+0.3f c  x  fillable %.1f contracts  x  "
          "%.1f fires/day" % (indent, sum(pnl) / len(pnl),
                              sum(sizes) / len(sizes), len(fires) / days))
    print("%s             resting at the touch: median %.0f  p25 %.0f  "
          "p75 %.0f  (cap %d)" % (indent, q(rest, .5), q(rest, .25),
                                  q(rest, .75), CAP))
    peak = max(sum(x["price"] * x["cnt"] for x in v)
               for v in per_close.values())
    print("%s             $/day %+8.2f    peak concurrent capital $%.2f"
          "    %.1f%%/day" % (indent, dollars / days, peak,
                              100.0 * (dollars / days) / peak if peak else
                              float("nan")))
    return {"n": len(fires), "closes": len(cl), "pnl_c": sum(pnl) / len(pnl),
            "t": t, "flips": flips, "dollars_day": dollars / days,
            "size": sum(sizes) / len(sizes), "per_day": len(fires) / days,
            "rest_med": q(rest, .5), "tau_med": q([f["tau"] for f in fires], .5)}


# --------------------------------------------- the CURRENT rule, same set --
def baseline(ix, meta, grid, keep_closes, pin=0.98, taumin=3, taumax=20):
    """pinrun's frozen rule, on exactly the markets the early rule saw.

    fair = Phi((mu-K_eff)/sd), sd = sigma*sqrt(var_factor(r,[1.0])), sigma the
    SD of 1-second index diffs over the trailing 300 s. Fires at the LARGEST
    tau at which it qualifies, which is what an event-driven live loop does
    as the clock runs down.
    """
    from engine import var_factor
    from statistics import NormalDist
    ND = NormalDist()
    YB, YA, BS, AS, AGE = grid
    W = meta["W"]
    out = []
    for i, tk in enumerate(meta["order"]):
        m = meta["markets"][tk]
        iid = SERIES_TO_INDEX.get(m["series"])
        if iid is None or m["close_s"] not in keep_closes:
            continue
        C, K, d, res = m["close_s"], m["K"], m["d"], m["result"]
        for tau in range(taumax, taumin - 1, -1):
            st = state(ix, iid, C, tau, K, d)
            if st is None:
                continue
            k = i * W + tau
            age = AGE[k]
            if age < 0 or age > MAX_QUOTE_AGE:
                continue
            sg = ix.sigma(iid, C - tau, C - tau)
            if sg is None or sg <= 0:
                continue
            sd = sg * math.sqrt(var_factor(int(st["r"]), [1.0]))
            if sd <= 0:
                continue
            f = ND.cdf((st["mu"] - st["Ke"]) / sd)
            if f >= pin:
                side, price, size = "yes", YA[k], AS[k]
            elif f <= 1 - pin:
                side, price, size = "no", 1.0 - YB[k], BS[k]
            else:
                continue
            if price >= 0.9999 or size < MIN_SIZE:
                continue
            cnt = max(1.0, min(size, CAP))
            if net_edge(price, cnt) < EDGE_FLOOR:
                continue
            win = 1.0 if res == side else 0.0
            fee = billed_fee(price, cnt) / cnt
            out.append({"close": C, "tk": tk, "series": m["series"],
                        "tau": tau, "side": side, "price": price,
                        "size": float(size), "cnt": cnt, "win": win,
                        "age": float(age),
                        "pnl_c": 100.0 * (win - price - fee),
                        "edge_c": 100.0 * net_edge(price, cnt), "ratio": 0.0})
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backdays", type=int, default=3)
    ap.add_argument("--cap", type=int, default=CAP)
    ap.add_argument("--nomeasure", action="store_true")
    a = ap.parse_args()

    import earlyself
    if not earlyself.run():
        raise SystemExit("self-test failed; refusing to touch real data")
    print()

    print("Loading caches ...")
    ix, meta, grid, taus, mtab = early.load_all()
    print("  %d markets in the book grid, taus %s" % (meta["N"], taus))

    rows = rows_for(ix, meta, grid, mtab, taus, back_days=a.backdays)
    closes = sorted(set(r[C_] for r in rows))
    days = (closes[-1] - closes[0]) / float(DAY)
    import time as _t
    print("  %d usable (market,tau) cells over %d closes, "
          "%s .. %s  (%.2f days)"
          % (len(rows), len(closes),
             _t.strftime("%Y-%m-%d %H:%M", _t.gmtime(closes[0])),
             _t.strftime("%Y-%m-%d %H:%M", _t.gmtime(closes[-1])), days))
    print("  markets touched: %d" % len(set(r[TK_] for r in rows)))

    if not a.nomeasure:
        measure(rows, taus)

    print("\n" + "=" * 76)
    print("THE EARLY RULE -- fire at the LARGEST tau where the lock holds")
    print("=" * 76)
    for c in (1.0, 1.5, 2.0, 3.0):
        print("\n  --- c = %.1f ---" % c)
        f = fire_early(rows, c, cap=a.cap)
        report(f, "one per MARKET (all coins)", days, indent="    ")
        report(one_per_close(f), "one per CLOSE", days, indent="    ")

    print("\n" + "=" * 76)
    print("THE EARLY RULE RESTRICTED TO tau >= 25 (strictly earlier than pin)")
    print("=" * 76)
    for c in (1.0, 1.5, 2.0, 3.0):
        f = fire_early(rows, c, cap=a.cap, taumin=25)
        report(f, "c=%.1f, tau>=25, one per MARKET" % c, days, indent="    ")

    print("\n" + "=" * 76)
    print("THE CURRENT RULE (pin, tau 3-20, fair>=0.98) ON THE SAME CLOSES")
    print("=" * 76)
    b = baseline(ix, meta, grid, set(closes))
    report(b, "pin tau<=20, one per MARKET", days, indent="    ")
    report(one_per_close(b), "pin tau<=20, one per CLOSE", days, indent="    ")


if __name__ == "__main__":
    main()
