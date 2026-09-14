#!/usr/bin/env python3
"""pinhedgelive.py -- every hedge we have actually placed, what it cost or
saved, and what an EV gate WOULD have done. A tracker, not a gate.

WHY THIS EXISTS. `pinhedge.py` derived the rule on 2026-09-08: a hedge is worth
taking exactly when `hedge_ask < 1 - belief`, because holding both sides of a
Kalshi binary pays exactly $1.00 and so ENDS the trade at a certain price.
`pinrun.hedge_edge_c()` computes that number on every hedge and its own
docstring calls it "DIAGNOSTIC, not a gate". Nothing has ever read it back.

So: this reads it back. It answers three questions from LIVE FILLS ONLY --

  1. what has the hedge actually cost or saved, close by close
  2. what would a `hedge_edge_c >= 0` gate have changed
  3. what would a different trigger than the live one have changed

RULE 5 OF THE REPO APPLIES AND IS RESPECTED. Every number here comes from our
own orders and our own settlements. Nothing is replayed, nothing is simulated,
and no loss rate is quoted from the tape.

THE ARITHMETIC, done from money in and money out rather than from the log's
own `pnl_c`. Those rows under-count the entry leg after a partial hedge fill:
on 2026-09-12 the ETH 11:15 close logged a 6-contract entry settle against a
20-contract fill. Cost and payout are unambiguous, so they are used instead.

    python research/pinhedgelive.py --selftest
    python research/pinhedgelive.py
    python research/pinhedgelive.py --trigger 0.30
"""
import glob
import json
import os
import sys

FEE = lambda p, n: 0.07 * float(p) * (1.0 - float(p)) * float(n)


def close_pnl(entries, hedges, result):
    """Dollars for one market: what we paid, against what it paid back.

    `entries` and `hedges` are lists of (side, contracts, price). Exactly one
    of yes/no pays $1.00 per contract, so the payout is simply the contracts
    held on the winning side.
    """
    spent = 0.0
    payout = 0.0
    for side, n, px in list(entries) + list(hedges):
        spent += n * px + FEE(px, n)
        if side == result:
            payout += n
    return payout - spent


def would_fire(belief, trigger):
    """The live rule: hedge when belief in OUR side falls under the trigger."""
    return belief is not None and float(belief) < float(trigger)


def ev_gate_ok(belief, hedge_ask):
    """pinhedge.py's rule: the hedge leg must cost less than the model's own
    probability that we are WRONG. Otherwise we are paying over the odds to
    end a trade we still expect to win."""
    if belief is None or hedge_ask is None:
        return False
    return float(hedge_ask) < (1.0 - float(belief))


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        if not c:
            print("FAIL:", m)
            ok = False
        else:
            print("  ok:", m)

    # --- a world where the answer is known ---------------------------------
    # 20 NO at 90c, hedged 20 YES at 14c, result NO. We hold 20 of the winner.
    got = close_pnl([("no", 20, 0.90)], [("yes", 20, 0.14)], "no")
    want = 20.0 - (20*0.90 + FEE(0.90, 20) + 20*0.14 + FEE(0.14, 20))
    ck(abs(got - want) < 1e-9 and got < 0,
       "BTC 09-12: 20 NO at 90c hedged with 20 YES at 14c and the NO WON -- "
       "the pair still lost $%.2f, because we paid 104c for a dollar" % -got)

    unhedged = close_pnl([("no", 20, 0.90)], [], "no")
    ck(unhedged > 0 and unhedged - got > 2.0,
       "and unhedged the same close MADE $%.2f -- the hedge is what turned it "
       "negative, by $%.2f" % (unhedged, unhedged - got))

    # the hedge that paid: our side lost
    got2 = close_pnl([("no", 60, 0.972)], [("yes", 60, 0.58)], "yes")
    un2 = close_pnl([("no", 60, 0.972)], [], "yes")
    ck(got2 > un2 and abs((got2 - un2) - (60.0 - 60*0.58 - FEE(0.58, 60))) < 1e-9,
       "BTC 09-14 05:30: 60 NO at 97.2c hedged 60 YES at 58c and our side "
       "LOST -- the hedge saved $%.2f" % (got2 - un2))

    # --- THE NULL: no hedge at all must equal the plain entry --------------
    for res in ("yes", "no"):
        a = close_pnl([("no", 10, 0.95)], [], res)
        b = 10.0 * (1.0 if res == "no" else 0.0) - (10*0.95 + FEE(0.95, 10))
        ck(abs(a - b) < 1e-12,
           "with NO hedge the close is exactly the entry (%s)" % res)

    # --- the two rules ------------------------------------------------------
    ck(would_fire(0.21, 0.80) and not would_fire(0.21, 0.10),
       "belief 0.214 fires at the live 0.80 trigger and NOT at 0.10 -- which "
       "is why 0.10 would have missed the hedge that saved $24")
    ck(not would_fire(None, 0.80), "no belief never fires")
    ck(ev_gate_ok(0.214, 0.58),
       "the EV rule ALLOWS a 58c hedge when the model says we are 78.6% likely "
       "to be wrong -- 58c for something worth 78.6c")
    ck(not ev_gate_ok(0.887, 0.14),
       "and REFUSES a 14c hedge when the model still gives us 88.7% -- 14c for "
       "something worth 11.3c")
    ck(not ev_gate_ok(0.525, 0.81),
       "and refuses 81c against a 47.5% chance of being wrong")
    ck(not ev_gate_ok(None, 0.5) and not ev_gate_ok(0.5, None),
       "a missing belief or a missing ask never passes the gate")

    print("pinhedgelive selftest:", "OK" if ok else "FAILED")
    return ok


def load():
    """Every LIVE market that carried a hedge, with both legs and the result."""
    out = {}
    for path in sorted(glob.glob(os.path.join("results", "pinrun-live-*.jsonl"))):
        sigs, orders, hedges, alarms, results = {}, [], [], {}, {}
        for line in open(path, encoding="utf-8"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            k, tk = d.get("kind"), d.get("ticker")
            if k == "signal":
                sigs.setdefault(tk, []).append(d)
            elif k == "order" and (d.get("filled") or 0) > 0:
                orders.append(d)
            elif k == "hedge" and (d.get("n") or 0) > 0:
                hedges.append(d)
            elif k == "hedge_alarm":
                alarms.setdefault(tk, d)
            elif k == "settled":
                results[tk] = d.get("result")
        for h in hedges:
            tk = h["ticker"]
            if tk not in results:
                continue
            ss = sigs.get(tk) or [{}]
            ent = [(ss[0].get("want"), o["filled"], o["exec_price"])
                   for o in orders if o["ticker"] == tk]
            if not ent:
                continue
            rec = out.setdefault(tk, {
                "t": h.get("t"), "entries": ent, "hedges": [],
                "result": results[tk],
                "belief": (alarms.get(tk) or {}).get("belief"),
                "side": ss[0].get("want"),
            })
            rec["hedges"].append((h["side"], float(h["n"]), float(h["price"])))
    return out


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0

    trigger = 0.80
    if "--trigger" in sys.argv:
        trigger = float(sys.argv[sys.argv.index("--trigger") + 1])

    mk = load()
    if not mk:
        print("loaded nothing -- no live hedge has settled yet")
        return 0

    print("\n  EVERY HEDGE WE HAVE ACTUALLY PLACED  (live fills only, n=%d)\n"
          % len(mk))
    print("  %-30s %7s %8s %9s %9s %8s" %
          ("close", "belief", "hedge", "unhedged", "hedged", "effect"))
    print("  " + "-" * 76)
    tot = 0.0
    ev_saved = 0.0
    trig_saved = 0.0
    for tk in sorted(mk, key=lambda k: mk[k]["t"]):
        r = mk[tk]
        hedged = close_pnl(r["entries"], r["hedges"], r["result"])
        plain = close_pnl(r["entries"], [], r["result"])
        eff = hedged - plain
        tot += eff
        ask = r["hedges"][0][2]
        # what an EV gate would have done: block it, so we keep `plain`
        if not ev_gate_ok(r["belief"], ask):
            ev_saved -= eff
        # what a different trigger would have done
        if not would_fire(r["belief"], trigger):
            trig_saved -= eff
        b = "n/a" if r["belief"] is None else "%.3f" % r["belief"]
        print("  %-30s %7s %7.0fc %+9.2f %+9.2f %+8.2f"
              % (tk.split("-")[0] + " " + (r["t"] or "")[5:16],
                 b, 100 * ask, plain, hedged, eff))
    print("  " + "-" * 76)
    print("  %-30s %7s %8s %9s %9s %+8.2f" % ("NET EFFECT OF HEDGING", "", "",
                                              "", "", tot))
    print("\n  WHAT A DIFFERENT RULE WOULD HAVE DONE (same closes, live money)")
    print("    live trigger %.2f, no EV gate       : %+8.2f" % (0.80, tot))
    print("    with an EV gate (ask < 1-belief)    : %+8.2f  (%+.2f)"
          % (tot + ev_saved, ev_saved))
    print("    trigger %.2f instead                : %+8.2f  (%+.2f)"
          % (trigger, tot + trig_saved, trig_saved))
    print("\n  n = %d hedges. Read nothing here as settled." % len(mk))
    return 0


if __name__ == "__main__":
    sys.exit(main())
