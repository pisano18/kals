#!/usr/bin/env python3
# VERSION: 2026-09-09-pdc1
"""pindrawcase.py -- replay ONE close, second by second, with the hedge rules.

Built for the 2026-09-09 00:45Z loss on KXNEAR15M-26SEP082045-45 (-$52.60), the
close that started this work. The study in `pindraw.py` cannot include it: the
settlement file `C:\\kals\\fulltape\\markets.json` stops at 2026-09-06 08:30Z, so
that market has no `result` record and is outside the sample by construction.
This file reads the SAME tape for that one close and asks the only question the
operator actually cares about:

    after we bought, when did it start looking different from a winning bet,
    and what would the other side have cost at that moment?

It reuses pindraw's index maths, quote plumbing, P&L arithmetic and triggers, so
anything wrong here is wrong there too. Settlement is computed FROM THE TAPE
(mean of the 60 one-second prints in [close-60, close-1]) and the self-test
requires it to reproduce the settlement the operator recorded, 2.349367, before
the file is allowed to say anything about the hedge.
"""
import argparse
import glob
import gzip
import json
import math
import os
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pindraw as PD                                          # noqa: E402

CASE = {
    "tk": "KXNEAR15M-26SEP082045-45",
    "iid": "NEARUSD_RTI",
    "close_s": 1788914700,
    "K": 2.34915,
    "settle": 2.349367,
    "won_yes": True,
    "buys": [(22, 0.962, 20.0), (21, 0.956, 20.0), (17, 0.730, 19.0)],
    "want": "no",
}


def load_one_index(iid, close_s, span=1200):
    lo, hi = close_s - span, close_s + 10
    files = PD.pick_files("cfbenchmarks_value", lo, hi)
    return PD.load_index(files, verbose=False)[0].get(iid)


def load_one_market(tk, close_s):
    files = PD.pick_files("ticker", close_s - PD.PANEL_TAU - 60, close_s + 60)
    msgs = []
    for f in files:
        try:
            with gzip.open(f, "rt") as fh:
                for ln in fh:
                    if tk not in ln or '"ticker"' not in ln:
                        continue
                    p = PD.parse_ticker_line(ln)
                    if p is None or p[0] != tk:
                        continue
                    if close_s - PD.PANEL_TAU <= p[1] // 1000 < close_s:
                        msgs.append(p[1:])
        except (EOFError, zlib.error, OSError):
            pass
    return msgs


def selftest():
    print("SELF-TEST -- pindrawcase")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    ck(PD.selftest(), "pindraw's own self-test passes (this file is a thin "
                      "wrapper over it and inherits every guarantee)")
    n = sum(b[2] for b in CASE["buys"])
    cost = sum(b[1] * b[2] for b in CASE["buys"])
    fees = sum(PD.billed_fee(b[1], b[2]) for b in CASE["buys"])
    ck(abs(cost + fees - 52.60) < 0.25,
       f"the recorded -$52.60 is reproduced from the three fills "
       f"(${cost + fees:.2f} at {n:g} contracts) -- if this fails the case "
       f"data is wrong and nothing below can be trusted")
    ck(CASE["K"] < CASE["settle"],
       f"the settlement {CASE['settle']} landed ABOVE K_eff {CASE['K']}, so "
       f"YES won and every NO contract paid zero")
    lost = sum(PD.leg_pnl(b[2], b[1], False) for b in CASE["buys"])
    ck(abs(lost + 52.60) < 0.25,
       f"and leg_pnl agrees on the loss (${lost:.2f})")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    close_s = CASE["close_s"]
    print(f"\n  {CASE['tk']}  close "
          f"{time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime(close_s))}")
    ix = load_one_index(CASE["iid"], close_s)
    if ix is None:
        raise SystemExit("index not in the tape window")
    tape_settle = ix.settle(close_s)
    print(f"  settlement from the tape: {tape_settle:.6f}  "
          f"(operator recorded {CASE['settle']:.6f}, "
          f"difference {abs(tape_settle - CASE['settle']):.6f})")
    if abs(tape_settle - CASE["settle"]) > 1e-4:
        print("  *** the tape does not reproduce the recorded settlement. "
              "Stopping: nothing below")
        print("  would be about the close the operator lost on.")
        return
    msgs = load_one_market(CASE["tk"], close_s)
    print(f"  {len(msgs):,} ticker updates in the last {PD.PANEL_TAU}s")
    qs = PD.Quotes(close_s, msgs, PD.PANEL_TAU) if msgs else None
    mk = {"close_s": close_s, "K": CASE["K"]}
    rows = PD.build_panel(mk, ix, qs, PD.PANEL_TAU)
    rows = [r for r in rows if r[0] <= 40]

    print(f"\n  {'tau':>4}{'spot':>11}{'spot-K':>11}{'side?':>7}{'mu':>11}"
          f"{'model p(lose)':>15}{'our bid':>9}{'hedge px':>10}"
          f"{'hedge size':>11}")
    for r in rows:
        tau, spot, mu, K, fair, sg, yb, ya, ybs, yas, age = r
        pl = fair                      # we hold NO, so p(lose) = P(YES wins)
        wrong = spot >= K
        ourbid = (1.0 - ya) if ya is not None else float("nan")
        hpx = ya if ya is not None else float("nan")
        hsz = yas if ya is not None else 0.0
        print(f"  {tau:>4}{spot:>11.5f}{spot-K:>+11.5f}"
              f"{('WRONG' if wrong else 'ok'):>7}{mu:>11.5f}{pl:>15.6f}"
              f"{ourbid:>9.3f}{hpx:>10.3f}{hsz:>11.1f}")

    print(f"\n  WHAT EACH TRIGGER WOULD HAVE DONE (position: "
          f"{sum(b[2] for b in CASE['buys']):g} NO contracts)")
    T = PD.make_triggers()
    base = sum(PD.leg_pnl(b[2], b[1], False) for b in CASE["buys"])
    print(f"  {'trigger':<20}{'fires at tau':>13}{'hedge px':>10}"
          f"{'hedged':>8}{'result $':>10}{'vs -52.60':>11}")
    for name in sorted(T):
        fn = T[name][0]
        tot = 0.0
        ft_min = None
        hq_all = 0.0
        pxs = []
        for tau, px, n in CASE["buys"]:
            pos = {"tk": CASE["tk"], "tau": tau, "want": CASE["want"],
                   "price": px, "n": n}
            h, ft, wn = PD.run_hedge(dict(pos), rows, fn)
            tot += PD.leg_pnl(n, px, False, h)
            if ft is not None:
                ft_min = ft if ft_min is None else max(ft_min, ft)
            hq = sum(q for q, _ in h)
            hq_all += hq
            if hq:
                pxs.append(sum(q * x for q, x in h) / hq)
        mpx = sum(pxs) / len(pxs) if pxs else float("nan")
        print(f"  {name:<20}{(ft_min if ft_min else 0):>13}{mpx:>10.3f}"
              f"{hq_all:>8.1f}{tot:>10.2f}{tot - base:>+11.2f}")
    print(f"\n  AND WITH A PRICE CAP ON THE HEDGE -- 'only buy the other "
          f"side if it is cheap',")
    print(f"  which is the operator's idea in its original form:")
    print(f"  {'trigger':<20}{'cap':>6}{'hedged':>8}{'result $':>10}"
          f"{'vs -52.60':>11}")
    for name in ("SPOT_CROSS", "MU_CROSS", "MODEL_P90"):
        for cap in (0.05, 0.10, 0.25, 0.50, None):
            tot = 0.0
            hq_all = 0.0
            for tau, px, n in CASE["buys"]:
                pos = {"tk": CASE["tk"], "tau": tau, "want": CASE["want"],
                       "price": px, "n": n}
                h, ft, wn = PD.run_hedge(dict(pos), rows, T[name][0],
                                         max_px=cap)
                tot += PD.leg_pnl(n, px, False, h)
                hq_all += sum(q for q, _ in h)
            print(f"  {name:<20}"
                  f"{('none' if cap is None else f'{100*cap:.0f}c'):>6}"
                  f"{hq_all:>8.1f}{tot:>10.2f}{tot - base:>+11.2f}")

    print(f"\n  'vs -52.60' is dollars better (+) or worse (-) than what "
          f"actually happened.")
    print(f"  Every one of these assumes we WIN THE RACE for the hedge at "
          f"the displayed touch,")
    print(f"  which is the same assumption the entry backtest makes and the "
          f"same one that is")
    print(f"  wrong 26% of the time on entries.")


if __name__ == "__main__":
    main()
