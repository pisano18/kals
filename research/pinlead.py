#!/usr/bin/env python3
# VERSION: 2026-09-11-pl1
"""pinlead.py -- THE COIN RACE: can we name the leader, and what is it priced at?

KXCRYPTOLEAD15M asks "which of BTC, ETH, SOL, XRP, HYPE has the highest return
over this 15 minutes". Five legs per close, exactly one wins (ties resolve
YES on every tied leg), fee_type quadratic with multiplier 1 so MAKERS PAY
NOTHING -- checked against /series on 2026-09-11.

WHY IT IS DIFFERENT FROM pin, AND WHY IT MIGHT BE BETTER
  pin bets on a LEVEL: will this coin finish above a strike. The race bets on
  an ORDER: which of five coins finishes highest. An ordering survives common
  moves -- if everything rallies together the leader does not change -- so the
  race is short exactly the correlated risk that makes twelve pin markets
  settle as ~1.22 independent bets instead of 12.

THE SETTLEMENT ARITHMETIC, which is the whole idea
  Return is measured between two 60-second CF Benchmarks averages, the window
  open and the window close. Because strike(N+1) == settle(N) on this product,
  THE DENOMINATOR IS ALREADY KNOWN AT THE MOMENT THE WINDOW OPENS. Only the
  numerator is unresolved, and it is the same quantity pin already forecasts:
  with tau seconds left, 60-tau prints are locked and tau are not.

  So the leader becomes progressively CALCULATED rather than forecast, and the
  question this file exists to answer is whether the market marks that down
  before we can act on it. Naming the leader is worth nothing if a leader we
  can name is already priced at 99c.

WHAT IS MEASURED, in order, and each stage can kill the next
  A. THE RULE. Recompute every coin's return from the index tape and check the
     argmax against Kalshi's own published expiration_value. Two candidate
     denominators are scored side by side (the 60s TWAP at the open versus the
     single spot print) and the file REFUSES to pick one by preference -- it
     reports both and uses whichever reproduces settlement.
  B. PREDICTABILITY BY TAU. How often the leader named at tau is the leader
     that settles, walking tau down. Reported against the 20% base rate, and
     against the margin between first and second place.
  C. THE PRICE. Written out for pinleadprice.py, which reads the TRADE tape --
     the instrument validated in pintrades.py, which unlike a book replay
     cannot miss an execution that really happened.

UNITS: events (a close), never legs and never trades. Five legs share one
outcome and all twelve crypto series settle on the same second.
"""
import argparse
import calendar
import glob
import gzip
import json
import math
import os
import random
import sys
import time
import zlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pincross import cp_interval                              # noqa: E402

DATA = r"C:\kals\kalshi_data"
LEAD = r"C:\kals\fulltape\lead.json"
COINS = {"BTC": "BRTI", "ETH": "ETHUSD_RTI", "SOL": "SOLUSD_RTI",
         "XRP": "XRPUSD_RTI", "HYPE": "HYPEUSD_RTI"}
N_AVG = 60


def twap(ticks, t):
    """Mean of the 60 one-second prints over [t-60, t-1], or None if short.

    This is the settlement average. It is NOT a trailing mean of whatever
    arrived -- a missing print makes the window unreconstructable and the
    honest answer is None, because settlement used a print we do not hold.
    """
    lo, hi = t - N_AVG, t - 1
    v = [x for s, x in ticks if lo <= s <= hi]
    if len(v) < N_AVG:
        return None
    return sum(v) / float(N_AVG)


def partial(ticks, close_s, now_s):
    """(locked_sum, n_locked, spot) at now_s for the window closing close_s.

    Only prints stamped STRICTLY BEFORE now_s count as locked; the print
    stamped now_s has not been published to us at now_s.
    """
    lo = close_s - N_AVG
    tot = 0.0
    n = 0
    spot = None
    for s, x in ticks:
        if s < now_s:
            spot = x
        if lo <= s <= min(now_s - 1, close_s - 1):
            tot += x
            n += 1
    return tot, n, spot


def leader(rets):
    """(winner set, margin) -- margin is first minus second, in return units."""
    if not rets:
        return set(), 0.0
    o = sorted(rets.items(), key=lambda kv: -kv[1])
    top = o[0][1]
    w = {k for k, v in rets.items() if v >= top - 1e-15}
    m = (top - o[1][1]) if len(o) > 1 else 0.0
    return w, m


def parse_winner(ev):
    """Kalshi writes ties as 'BTC,ETH' and has written 'Hype' at least once."""
    return {p.strip().upper() for p in str(ev).split(",") if p.strip()}


def fee(p, n=1.0):
    return math.ceil(0.07 * n * p * (1 - p) * 10000 - 1e-9) / 10000


def selftest():
    print("SELF-TEST -- pinlead")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # --- twap is the settlement average, exactly ---------------------------
    t = 1000
    ck(twap([(s, 2.0) for s in range(940, 1000)], t) == 2.0,
       "a flat 60-print window averages to the level")
    ck(twap([(s, float(s)) for s in range(940, 1000)], t) == 969.5,
       "and a ramp averages to the midpoint of [t-60, t-1]")
    ck(twap([(s, 1.0) for s in range(941, 1000)], t) is None,
       "59 prints is NOT a settlement window -- returns None, never a mean")
    ck(twap([(s, 1.0) for s in range(940, 1001)], t) == 1.0,
       "and the print stamped t itself is excluded, not averaged in")

    # --- partial: what is locked at tau ------------------------------------
    tk = [(s, float(s)) for s in range(940, 1000)]
    tot, n, sp = partial(tk, 1000, 980)          # tau = 20
    ck(n == 40 and abs(tot - sum(range(940, 980))) < 1e-9,
       "at tau=20, exactly 40 of the 60 prints are locked")
    ck(sp == 979.0, "spot at 980 is the print stamped 979, not 980")

    # --- the ordering, including the tie Kalshi actually publishes ---------
    w, m = leader({"BTC": 0.01, "ETH": 0.02, "SOL": -0.01})
    ck(w == {"ETH"} and abs(m - 0.01) < 1e-12,
       "the leader is the largest return and the margin is first minus second")
    w, _ = leader({"BTC": 0.02, "ETH": 0.02, "SOL": 0.0})
    ck(w == {"BTC", "ETH"}, "an exact tie names both legs, as Kalshi settles it")
    ck(parse_winner("BTC,ETH") == {"BTC", "ETH"} and
       parse_winner("Hype") == {"HYPE"},
       "Kalshi's tie string and its one mis-cased 'Hype' both parse")

    # --- PLANTED WORLD: a leader that is already decided at tau ------------
    rnd = random.Random(11)
    hit = 0
    for _ in range(200):
        close = 10000
        ticks = {}
        opens = {}
        for c in COINS:
            base = 100.0
            drift = 0.02 if c == "HYPE" else 0.0     # HYPE planted to win
            pre = [(s, base) for s in range(close - 960, close - 900)]
            win = [(s, base * (1 + drift) + rnd.gauss(0, 1e-5))
                   for s in range(close - 60, close)]
            ticks[c] = pre + win
            opens[c] = twap(pre, close - 900)
        rets = {}
        for c in COINS:
            tot, n, sp = partial(ticks[c], close, close - 20)
            mu = (tot + (60 - n) * sp) / 60.0
            rets[c] = mu / opens[c] - 1.0
        w, _ = leader(rets)
        hit += (w == {"HYPE"})
    ck(hit == 200, f"a planted 2% leader is named at tau=20 every time ({hit}/200)")

    # --- NULL WORLD: nothing knowable, accuracy must sit at the base rate --
    hit = 0
    trials = 600
    for _ in range(trials):
        close = 10000
        ticks = {}
        opens = {}
        truth = {}
        for c in COINS:
            base = 100.0
            pre = [(s, base) for s in range(close - 960, close - 900)]
            v = base
            win = []
            for s in range(close - 60, close):
                v += rnd.gauss(0, 0.05)          # pure random walk in-window
                win.append((s, v))
            ticks[c] = pre + win
            opens[c] = twap(pre, close - 900)
            truth[c] = twap(win, close) / opens[c] - 1.0
        rets = {}
        for c in COINS:
            tot, n, sp = partial(ticks[c], close, close - 58)   # 2 prints in
            mu = (tot + (60 - n) * sp) / 60.0
            rets[c] = mu / opens[c] - 1.0
        w, _ = leader(rets)
        tw, _ = leader(truth)
        hit += (w == tw)
    r = hit / float(trials)
    ck(0.10 < r < 0.34,
       "with nothing knowable, tau=58 accuracy sits near the 20%% base rate "
       "(%.1f%%) -- the estimator does not invent skill" % (100 * r))

    ck(abs(fee(0.16, 12.37) - 0.1164) < 1e-9,
       "the fee matches the account's own reconciled charge")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for x in f:
        print("   - " + x)
    return not f


def load_ticks(lo, hi, ids):
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
                        if m["index_id"] not in ids:
                            continue
                        dd = json.loads(m["data"])
                        s = int(dd["time"]) // 1000
                    except Exception:
                        continue
                    if lo - 100 <= s <= hi + 60:
                        out[m["index_id"]].append((s, float(dd["value"])))
        except (EOFError, zlib.error, OSError):
            pass
    for k in out:
        out[k].sort()
    return out


def window(ticks, lo, hi):
    """The slice of prints in [lo, hi] -- keeps the per-event scan bounded."""
    import bisect
    i = bisect.bisect_left(ticks, (lo, -1e18))
    j = bisect.bisect_right(ticks, (hi, 1e18))
    return ticks[i:j]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--days", type=int, default=4)
    ap.add_argument("--taus", default="60,45,30,25,20,15,10,5,3")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed")

    ev = json.load(open(LEAD, encoding="utf-8"))
    events = sorted(((e["close"], k, e) for k, e in ev.items()
                     if len(e["legs"]) == 5))
    newest = events[-1][0]
    events = [e for e in events if e[0] > newest - a.days * 86400]
    print("\n  %d five-leg events in the last %d days (%s .. %s)\n"
          % (len(events), a.days,
             time.strftime("%m-%d %H:%MZ", time.gmtime(events[0][0])),
             time.strftime("%m-%d %H:%MZ", time.gmtime(newest))))

    ids = set(COINS.values())
    taus = [int(x) for x in a.taus.split(",")]
    hit = {"twap": 0, "spot": 0}
    seen = 0
    ties = 0
    acc = {t: [0, 0] for t in taus}
    margins = []
    by_day = defaultdict(lambda: [0, 0])
    pred = {}
    skipped = defaultdict(int)

    day = None
    ticks = {}
    for close, evt, e in events:
        d = time.strftime("%Y%m%d", time.gmtime(close))
        if d != day:
            day = d
            t0 = calendar.timegm(time.strptime(d, "%Y%m%d"))
            ticks = load_ticks(t0 - 1000, t0 + 86400, ids)
            print("    %s  index prints %s..%s" % (
                d, min((len(v) for v in ticks.values()), default=0),
                max((len(v) for v in ticks.values()), default=0)), flush=True)
        if not ticks:
            skipped["no_tape"] += 1
            continue
        opn = close - 900
        cut = {c: window(ticks.get(i) or [], opn - N_AVG - 5, close)
               for c, i in COINS.items()}
        rt, rs = {}, {}
        ok = True
        for c in COINS:
            tk = cut[c]
            o_t = twap(tk, opn)
            c_t = twap(tk, close)
            sp = None
            for s, x in tk:
                if s < opn:
                    sp = x
            if o_t is None or c_t is None or not o_t or not sp:
                ok = False
                break
            rt[c] = c_t / o_t - 1.0
            rs[c] = c_t / sp - 1.0
        if not ok:
            skipped["window_incomplete"] += 1
            continue
        want = parse_winner(e["winner"])
        if len(want) > 1:
            ties += 1
        seen += 1
        wt, mg = leader(rt)
        ws, _ = leader(rs)
        hit["twap"] += (wt == want)
        hit["spot"] += (ws == want)
        margins.append(mg)

        for t in taus:
            now = close - t
            pr = {}
            good = True
            for c in COINS:
                tk = cut[c]
                tot, n, sp = partial(tk, close, now)
                o_t = twap(tk, opn)
                if sp is None or not o_t:
                    good = False
                    break
                pr[c] = ((tot + (N_AVG - n) * sp) / N_AVG) / o_t - 1.0
            if not good:
                continue
            w, _ = leader(pr)
            acc[t][1] += 1
            acc[t][0] += (w == want)
            if t == 20:
                by_day[d][1] += 1
                by_day[d][0] += (w == want)
            if len(w) == 1:
                # ONE PREDICTION PER TAU. Scoring a tau-45 purchase against a
                # tau-20 prediction is look-ahead and it inflated this file's
                # first result from ~91% to 98.9%. Found 2026-09-11.
                pred.setdefault(evt, {})[str(t)] = {
                    "coin": sorted(w)[0], "close": close,
                    "right": bool(w == want), "winner": sorted(want)}

    print("\n  " + "=" * 94)
    print("  A. THE SETTLEMENT RULE, on %d events (%d of them ties)"
          % (seen, ties))
    for k in ("twap", "spot"):
        n = hit[k]
        lo_, hi_ = cp_interval(seen - n, seen) if seen else (0, 0)
        print("     denominator = %4s-at-open : reproduces Kalshi's own "
              "winner on %d/%d = %6.2f%%  [miss %.2f, %.2f]"
              % (k, n, seen, 100.0 * n / max(1, seen), 100 * lo_, 100 * hi_))
    margins.sort()
    if margins:
        q = [margins[int(p * (len(margins) - 1))] for p in (.05, .25, .5, .75)]
        print("     margin first-to-second (return units): p05 %.5f  p25 %.5f"
              "  median %.5f  p75 %.5f" % tuple(q))

    print("\n  B. CAN WE NAME THE LEADER EARLY?  base rate is 20%% (five legs)")
    print("     %5s%9s%14s%20s" % ("tau", "events", "named right", "95% CI"))
    for t in taus:
        n, N = acc[t]
        if not N:
            continue
        lo_, hi_ = cp_interval(n, N)
        print("     %5d%9d%13.1f%%%20s"
              % (t, N, 100.0 * n / N,
                 "[%.1f, %.1f]" % (100 * lo_, 100 * hi_)))
    if by_day:
        print("     by day at tau 20: " + "  ".join(
            "%s %.0f%%" % (d[4:], 100.0 * v[0] / max(1, v[1]))
            for d, v in sorted(by_day.items())))
    print("\n  skipped: %s" % dict(skipped))
    op = os.path.join(HERE, "_lead_pred.json")
    json.dump(pred, open(op, "w"))
    print("  %d tau-20 predictions written to %s for the price stage"
          % (len(pred), op))


if __name__ == "__main__":
    main()
