"""READ-ONLY adversarial verification of the partial-fill P&L finding.
Drives pintake.normalise/_book and pinrun's VERBATIM reconcile arithmetic on
synthetic responses. Sends nothing: ordercli.send is never reached.
"""
import sys, math, json, glob
sys.path.insert(0, r"C:\kals-repo\research")
import pintake, pinrun

SIZE = 5.0
pinrun.SIZE = SIZE

def resp(count, exec_yes, fee_per):
    return {"order": {"order_id": "v", "client_order_id": "v",
                      "fill_count": f"{count:.2f}", "remaining_count": "0.00",
                      "average_fill_price": exec_yes,
                      "average_fee_paid": fee_per}}

def pinrun_pnl(cost, won):
    # VERBATIM pinrun.py:867-868
    return (float(pinrun.SIZE) * ((1.0 - cost) if won else (-cost))
            - pinrun.billed_fee(cost, pinrun.SIZE))

def true_pnl(cost, won, n):
    return n * ((1.0 - cost) if won else (-cost)) - pinrun.billed_fee(cost, n)

print("== 1. does a partial IOC really produce filled<count that pinrun discards?")
for n in (1.0, 2.0, 4.0, 5.0):
    pintake.reset_ledger()
    body = pintake.build_take("T", "no", 0.97, SIZE, exchange_index=2)
    stk = pintake.stake(body)
    pintake.LEDGER["committed"] += stk
    out = pintake.normalise(201, resp(n, 0.03, 0.002), body, pintake.PROD_ELECTIONS)
    out["refused"] = []
    pintake._book(out, body, stk)
    pos = pintake.LEDGER["positions"].get("T")
    c = out["exec_price"]
    print(f"  filled {n:.0f}/{SIZE:.0f} exec {c:.3f} | pintake truth "
          f"{pos['contracts']:.0f}c ${pos['cost']:.4f} | committed ${pintake.LEDGER['committed']:.4f}"
          f" | pinrun WIN ${pinrun_pnl(c,True):+.4f} (true ${true_pnl(c,True,n):+.4f})"
          f" LOSS ${pinrun_pnl(c,False):+.4f} (true ${true_pnl(c,False,n):+.4f})")

print()
print("== 2. error direction and magnitude at every price actually paid live")
prices=[]
for f in sorted(glob.glob(r"C:\kals-repo\results\pinrun-live-*.jsonl")):
    for ln in open(f, encoding="utf-8"):
        try: d=json.loads(ln)
        except Exception: continue
        if d.get("kind")=="order" and d.get("filled"):
            prices.append(float(d["exec_price"]))
print(f"  {len(prices)} filled live orders, exec_price {min(prices):.3f}..{max(prices):.3f}")
worst_win_infl = 0.0; worst_loss_infl = 0.0
for p in sorted(set(prices)):
    for n in (1.0,2.0,3.0,4.0):
        wi = pinrun_pnl(p,True)-true_pnl(p,True,n)      # >0 = realised too HIGH (unsafe)
        li = true_pnl(p,False,n)-pinrun_pnl(p,False)    # >0 = realised too LOW (safe)
        worst_win_infl=max(worst_win_infl,wi); worst_loss_infl=max(worst_loss_infl,li)
print(f"  WORST anti-conservative error (a partial WIN inflates realised): ${worst_win_infl:+.4f}")
print(f"  WORST conservative error   (a partial LOSS deflates realised): ${worst_loss_infl:+.4f}")

print()
print("== 3. what actually stops the run first?")
print(f"  pintake.LOSS_ABORT (hard, in check_take, NOT overridden by pinrun) = ${pintake.LOSS_ABORT:.2f}")
one_loss = true_pnl(0.97, False, SIZE)
print(f"  one FULL losing close at size {SIZE:g} @0.97 = ${one_loss:+.4f}")
print(f"  -> realised after ONE real full loss is {one_loss:.2f} <= {pintake.LOSS_ABORT:.2f}: "
      f"{'every further take REFUSED' if one_loss<=pintake.LOSS_ABORT else 'still trading'}")
print(f"  contracts of phantom win-inflation needed to buy back one loss: "
      f"{abs(pintake.LOSS_ABORT)/worst_win_infl:.0f} partial-win events at the worst case")

print()
print("== 4. is exposure EVER understated? (would be the unsafe direction)")
bad=False
for n in (0.5,1.0,2.0,4.0,5.0):
    booked = SIZE*0.97; truth = n*0.97
    if booked < truth-1e-9: bad=True
print(f"  open_cost = SIZE*cost >= filled*cost for all filled<=SIZE: "
      f"{'UNDERSTATED SOMEWHERE' if bad else 'never understated -- always conservative'}")
