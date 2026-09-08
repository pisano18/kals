"""What does the hedge COST us on bets that would have been fine?

The operator: "check if it kills profits on normal bets that would've been fine
and how much that hurts us". It was measured -- it is the 'cost' column -- but
it was never broken out, and it is the number that decides the whole idea.
"""
import json, math, sys
from collections import defaultdict
sys.path.insert(0, r"C:\kals-repo\research")
from pinhedge import (model_pflip, hedge_price, hedged_pnl, unhedged_pnl,
                      ev, fee, CEILING, PIN_P)

rows = [json.loads(l) for l in
        open(r"C:\kals-repo\results\pindata\rows.jsonl", encoding="utf-8")
        if l.strip()]
bym = defaultdict(list)
for r in rows:
    bym[(r["tk"], r["close"])].append(r)
for k in bym:
    bym[k].sort(key=lambda x: -x["tau"])


def entries(tau_hi):
    out = []
    for k, seq in bym.items():
        e = None
        for x in seq:
            if not (3 <= x["tau"] <= tau_hi):
                continue
            pf = model_pflip(x)
            if pf is None or pf > PIN_P:
                continue
            if x["price"] > CEILING or ev(x["price"]) < 0.003:
                continue
            e = x
            break
        if e is not None:
            out.append((e, [x for x in seq if x["tau"] < e["tau"]]))
    return out


def split(ent, thresh):
    """Separate the hedge's effect on WINNERS from its effect on LOSERS."""
    fa_n = fa_cost = 0.0          # false alarms: hedged, would have won
    sv_n = sv_gain = 0.0          # true saves: hedged, would have lost
    miss = 0                      # lost and the hedge never fired
    clean = 0                     # would have won, never hedged
    base = 0.0
    for e, later in ent:
        u = unhedged_pnl(e["price"], not e["flip"])
        base += u
        hp = None
        for x in later:
            pf = model_pflip(x)
            if pf is None:
                continue
            if x["side_yes"] != e["side_yes"]:
                pf = 1.0 - pf
            if pf >= thresh:
                q = hedge_price(x, e["side_yes"])
                if 0.0 < q < 1.0:
                    hp = q
                    break
        if hp is None:
            if e["flip"]:
                miss += 1
            else:
                clean += 1
            continue
        h = hedged_pnl(e["price"], hp)
        if e["flip"]:
            sv_n += 1
            sv_gain += h - u
        else:
            fa_n += 1
            fa_cost += u - h
    return dict(n=len(ent), base=base, fa_n=fa_n, fa_cost=fa_cost,
                sv_n=sv_n, sv_gain=sv_gain, miss=miss, clean=clean)


for tau_hi, lab in ((30, "THE LIVE WINDOW (tau 3-30) -- zero losers, so this is PURE COST"),
                    (200, "THE WIDE WINDOW (tau 3-200) -- 12 real losers")):
    ent = entries(tau_hi)
    nl = sum(1 for e, _ in ent if e["flip"])
    print(f"\n  {lab}")
    print(f"  {len(ent)} positions, {nl} losers, "
          f"base profit {100*sum(unhedged_pnl(e['price'], not e['flip']) for e,_ in ent):.1f}c\n")
    print(f"  {'trigger':>10}{'FALSE ALARMS':>14}{'they cost':>12}"
          f"{'each':>9}{'% of profit':>13}{'true saves':>12}{'they gain':>12}")
    for th in (0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 0.90):
        d = split(ent, th)
        pct = 100 * d["fa_cost"] / d["base"] if d["base"] else 0.0
        each = 100 * d["fa_cost"] / d["fa_n"] if d["fa_n"] else 0.0
        print(f"  {100*th:>9.0f}%{d['fa_n']:>14.0f}{100*d['fa_cost']:>11.1f}c"
              f"{each:>8.1f}c{pct:>12.1f}%{d['sv_n']:>12.0f}"
              f"{100*d['sv_gain']:>11.1f}c")

print("\n  THE BREAK-EVEN FLIP RATE FOR THE HEDGE ITSELF")
print("  The hedge is worth having only if  flip_rate x saving_per_loss  >")
print("  cost_per_position. Saving is measured on the wide window (the only")
print("  place losses exist); cost is measured on the LIVE window (the only")
print("  place that reflects what we actually trade).\n")
live = entries(30)
wide = entries(200)
print(f"  {'trigger':>10}{'cost/position':>16}{'saving/loss':>14}"
      f"{'break-even flip':>18}{'verdict at 0.90%':>20}")
for th in (0.20, 0.35, 0.50, 0.75, 0.90):
    dl = split(live, th)
    dw = split(wide, th)
    cpp = dl["fa_cost"] / dl["n"]
    spl = (dw["sv_gain"] / dw["sv_n"]) if dw["sv_n"] else 0.0
    be = (cpp / spl) if spl > 0 else float("inf")
    v = "PAYS" if be < 0.0090 else ("marginal" if be < 0.0231 else "COSTS")
    print(f"  {100*th:>9.0f}%{100*cpp:>15.3f}c{100*spl:>13.1f}c"
          f"{100*be:>17.2f}%{v:>20}")
print("\n  'marginal' means it does not pay at the 0.90% we measured but DOES")
print("  pay before the 2.31% exact upper bound we cannot rule out. That is")
print("  the honest description: it is insurance against our own flip rate")
print("  being wrong, not a profit centre.")
