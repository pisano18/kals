#!/usr/bin/env python3
"""vfy_pinexit3.py -- THE BREAK-EVEN LOSS RATE, and the depth on the LOSERS.

H  BREAK-EVEN LOSS RATE. The recommended rule's whole value is
       E[delta per trade] = P(lose)*P(fire|lose)*save
                          - P(win)*P(fire|win)*tax
   where save and tax are MEASURED here, not assumed. Solving for the loss
   rate at which the rule stops paying turns the study's "+39% total" into a
   single number that can be compared against what we actually know about how
   often we lose. That comparison, not the +39%, is the decision.

I  DEPTH ON THE LOSERS ONLY. The study's median depth mixes winners and
   losers and is quoted from a different population than the one that
   produced the ledger. What matters is: on the 12 trades where the hedge
   would have SAVED money, how many contracts were resting?

SELFTEST: a planted world where the break-even rate is known in closed form,
and a null world where the rule fires on nobody and the break-even rate is
undefined rather than invented.
"""
import argparse
import json
import os
import sys

HERE = r"C:\kals-repo\research"
sys.path.insert(0, HERE)
sys.path.insert(0, r"C:\kals-repo\results\_verify")
import pinexit as PX                                            # noqa: E402
import pinexit_run as PR                                        # noqa: E402
from pinexit import IndexTape, walk                             # noqa: E402
from vfy_pinexit import score_rule, pctl                        # noqa: E402


def breakeven(save, tax, fire_l, fire_w):
    """Loss rate at which hedging stops paying. None if the rule never taxes."""
    if save <= 0 or fire_l <= 0:
        return None
    num = tax * fire_w
    den = save * fire_l + tax * fire_w
    if den <= 0:
        return None
    return num / den


def selftest():
    print("SELF-TEST -- vfy_pinexit3")
    ok = []

    def ck(c, m):
        ok.append(bool(c))
        print(("  ok   " if c else "  FAIL ") + m)

    # PLANTED: save 9, tax 9, fires on 100% of losers and 10% of winners.
    # Break-even loss rate p solves p*9 = (1-p)*0.1*9  ->  p = 0.1/1.1
    b = breakeven(9.0, 9.0, 1.0, 0.1)
    ck(abs(b - 0.1 / 1.1) < 1e-12,
       "PLANTED: save 9 / tax 9 / fires on 100%% of losers and 10%% of "
       "winners breaks even at %.4f, the closed form" % b)
    # PLANTED: a tax-free rule breaks even at a loss rate of zero
    ck(breakeven(9.0, 0.0, 1.0, 0.0) == 0.0,
       "PLANTED: a rule that never fires on a winner pays at ANY loss rate")
    # NULL: a rule that never fires on a loser has no break-even, not a
    # flattering one
    ck(breakeven(9.0, 9.0, 0.0, 0.1) is None,
       "NULL: a rule that never catches a loser returns None, not a number")
    ck(breakeven(0.0, 9.0, 1.0, 0.1) is None,
       "NULL: a hedge that saves nothing returns None, not a number")
    # monotone: a costlier tax raises the break-even rate
    ck(breakeven(9.0, 18.0, 1.0, 0.1) > breakeven(9.0, 9.0, 1.0, 0.1),
       "a costlier false alarm requires a HIGHER loss rate to justify -- the "
       "sign of the dependence is right")
    ck(pctl([1, 2, 3, 4], 0.0) == 1, "the percentile helper is the study's")
    print("SELF-TEST " + ("PASSED" if all(ok) else "FAILED"))
    return all(ok)


RULES = [("p_model", 0.5), ("p_model", 0.9), ("sd_loss", 2.0),
         ("p_gain", 0.25)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows", default=PX.ROWS)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed; refusing real data")

    by, nrows = PR.load_rows(a.rows, 3, 60)
    lo = min(min(s.keys()) for s in by.values())
    hi = max(max(s.keys()) for s in by.values())
    idx = PR.load_index_cache(lo - 400, hi + 120,
                              os.path.join(PX.WORK, "pinexit_idx_wide.pkl"))
    tapes = {k: IndexTape(*v) for k, v in idx.items()}
    mk = {}
    for v in json.load(open(PX.FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] in PX.SERIES_TO_INDEX:
                mk[r["ticker"]] = r

    ents = PR.build_entries(by, tapes, mk, 3, 60, True, True)
    live = PR.build_entries(by, tapes, mk, 3, 30, True, True)
    wl = [1.0 - e[7] - PR.fee(e[7]) for e in ents if not e[6]]
    tw = sum(wl) / len(wl)
    keep = [e for e in ents if e[7] is not None]

    print("\n" + "=" * 78)
    print("  H -- THE BREAK-EVEN LOSS RATE")
    print("  The +39%% headline is not a property of the rule. It is the")
    print("  product of the rule and THIS population's 2.7%% loss rate.")
    print("  Below, save and tax are measured; the loss rate is solved for.")
    print("=" * 78)
    print("  typical win %.2fc; population loss rate %.2f%% "
          "(%d of %d one-per-market trades)"
          % (100 * tw, 100 * sum(1 for e in ents if e[6]) / len(ents),
             sum(1 for e in ents if e[6]), len(ents)))
    print("\n  %16s%7s%8s%9s%9s%12s%12s"
          % ("rule", "save", "tax", "fire|L", "fire|W", "break-even",
             "live fire|W"))
    print("  " + "-" * 74)
    for feat, th in RULES:
        r = score_rule(ents, feat, th, 1)
        sav, tax = [], []
        for e, (p, l, h) in zip(keep, r["pnl"]):
            if not h:
                continue
            b = ((-e[7]) if e[6] else (1.0 - e[7])) - PR.fee(e[7])
            (sav if e[6] else tax).append((p - b) / tw)
        if not sav or not tax:
            continue
        ms = sum(sav) / len(sav)
        mt = abs(sum(tax) / len(tax))
        nl = sum(1 for e in ents if e[6])
        nw = len(ents) - nl
        fl = r["fired_l"] / nl
        fw = r["fired_w"] / nw
        # the same rule's winner fire rate on the window we actually trade
        rl = score_rule(live, feat, th, 1)
        fwl = rl["fired_w"] / max(len(live), 1)
        be = breakeven(ms, mt, fl, fw)
        bel = breakeven(ms, mt, fl, fwl)
        print("  %16s%7.1f%8.1f%8.0f%%%8.2f%%%11.2f%%%11.2f%%"
              % (feat + ">=" + str(th), ms, mt, 100 * fl, 100 * fw,
                 100 * be, 100 * fwl))
        print("      -> at the LIVE window's own false-alarm rate "
              "(%d of %d trades) it breaks even at a loss rate of %.2f%%"
              % (rl["fired_w"], len(live), 100 * bel))

    print("\n  WHAT WE KNOW ABOUT THE LOSS RATE, for comparison:")
    print("    pinrun's own MEASURED_FLIP constant .............. %.2f%%"
          % (100 * PR.MEASURED_FLIP))
    print("    this study's tau 3-60 gated population ........... %.2f%%"
          % (100 * sum(1 for e in ents if e[6]) / len(ents)))
    print("    the LIVE window tau 3-30 gated population ........ %.2f%% "
          "(%d of %d)"
          % (100 * sum(1 for e in live if e[6]) / max(len(live), 1),
             sum(1 for e in live if e[6]), len(live)))
    print("    the live record in SKIM.md ....................... "
          "3 losses / 33 trades, but 1 losing CLOSE")

    print("\n" + "=" * 78)
    print("  I -- DEPTH ON THE TRADES THAT WOULD ACTUALLY BE SAVED")
    print("  The study quotes a median depth of 150 from the 4,696-entry")
    print("  population. The ledger comes from these 438. What was resting")
    print("  on the 12 trades where the hedge would have paid?")
    print("=" * 78)
    for feat, th in RULES:
        dl, dw = [], []
        for (tk, close, K, tp, sec0, yes, lose, price, secs, sr) in ents:
            cells = list(walk(tp, close, K, yes, sec0, secs, 200))
            fire = None
            for k, tau, f in cells:
                v = f.get(feat)
                if v is not None and v >= th:
                    fire = tau
                    break
            if fire is None:
                continue
            for lg in (1, 2, 3):
                row = secs.get(close - fire + lg)
                if row is None:
                    continue
                q = PR.other_ask(row, yes)
                if not (0.0 < q < 1.0):
                    continue
                if bool(row["side_yes"]) != bool(yes):
                    (dl if lose else dw).append(float(row.get("size") or 0.0))
                break
        if dl:
            print("  %s >= %s: LOSERS n=%d depth min %.0f  p25 %.0f  "
                  "median %.0f  max %.0f  |  below size 20: %d of %d"
                  % (feat, th, len(dl), min(dl), pctl(dl, 0.25),
                     pctl(dl, 0.5), max(dl),
                     sum(1 for x in dl if x < 20), len(dl)))
        else:
            print("  %s >= %s: LOSERS n=0 -- no row on the hedge side at all"
                  % (feat, th))
        if dw:
            print("      winners n=%d median depth %.0f"
                  % (len(dw), pctl(dw, 0.5)))


if __name__ == "__main__":
    main()
