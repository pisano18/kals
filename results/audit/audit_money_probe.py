"""READ-ONLY probe. Reproduces the exact live code paths at --size 5 with
synthetic exchange responses. Sends nothing: ordercli.send is never called
because we drive pintake._book() and pinrun's own arithmetic directly."""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"C:\kals-repo\research")
import pintake

SIZE = 5.0
PRICE = 0.97          # buying NO at 97c -> ask at yes 0.03

def fill_response(count, exec_yes, fee_per):
    return {"order": {"order_id": "probe", "client_order_id": "probe",
                      "fill_count": f"{count:.2f}", "remaining_count": "0.00",
                      "average_fill_price": exec_yes,
                      "average_fee_paid": fee_per}}

print("="*74)
print("PROBE 1 -- does the committed stake come back on settlement at size 5?")
print("="*74)
pintake.reset_ledger()
pintake.arm_prod("probe (no wire call is made)")
for i in range(20):
    body = pintake.build_take(f"T{i}", "no", PRICE, SIZE, exchange_index=2)
    stk = pintake.stake(body)
    v = pintake.check_take(body, 1e12, 1e12 - 10, base=pintake.PROD_ELECTIONS)
    if v:
        print(f"  trade {i+1:2d}: REFUSED by check_take -> {v}")
        break
    pintake.LEDGER["committed"] += stk          # take(): intent
    out = pintake.normalise(201, fill_response(SIZE, 1.0 - PRICE, 0.002),
                            body, pintake.PROD_ELECTIONS)
    out["refused"] = []
    pintake._book(out, body, stk)
    committed_after_fill = pintake.LEDGER["committed"]
    # ---- pinrun.reconcile(), verbatim arithmetic ----
    cost = out["exec_price"]                       # per-contract price paid
    won = True
    pnl = SIZE * ((1.0 - cost) if won else (-cost)) - math.ceil(
        pintake.expected_fee(cost, SIZE) * 10000.0) / 10000.0
    pintake.record_pnl(pnl)
    pintake.LEDGER["committed"] = max(
        0.0, float(pintake.LEDGER.get("committed", 0.0)) - cost)
    pintake.LEDGER["positions"].pop(f"T{i}", None)
    print(f"  trade {i+1:2d}: stake ${stk:6.2f}  committed after fill "
          f"${committed_after_fill:6.2f}  after 'release' "
          f"${pintake.LEDGER['committed']:6.2f}  realised "
          f"${pintake.LEDGER['realised']:+.4f}")
print(f"\n  positions open: {len(pintake.LEDGER['positions'])}   "
      f"committed still held: ${pintake.LEDGER['committed']:.2f}   "
      f"MAX_RUN_STAKE ${pintake.MAX_RUN_STAKE:.2f}")

print()
print("="*74)
print("PROBE 2 -- pintake.LOSS_ABORT vs the process's --loss-abort -21.00")
print("="*74)
pintake.reset_ledger()
loss = SIZE * (-PRICE) - math.ceil(pintake.expected_fee(PRICE, SIZE)*1e4)/1e4
print(f"  one ordinary losing close at size {SIZE:g} @ {PRICE:.2f} = ${loss:+.4f}")
pintake.record_pnl(loss)
body = pintake.build_take("T-next", "no", PRICE, SIZE, exchange_index=2)
v = pintake.check_take(body, 1e12, 1e12 - 10, base=pintake.PROD_ELECTIONS)
print(f"  pintake.LOSS_ABORT = ${pintake.LOSS_ABORT:.2f}")
print(f"  next take -> {'REFUSED' if v else 'ALLOWED'}: {v}")
class A:
    loss_abort = -21.00
    max_positions = 3
sys.path.insert(0, r"C:\kals-repo\research")
import pinrun
pinrun.SIZE = SIZE
stop = pinrun.risk_abort({"halted": False, "errors": 0, "open_cost": 0.0}, A)
print(f"  pinrun.risk_abort() with the SAME ledger -> {stop!r}")
print("  => the order path is dead while the process believes it is healthy"
      if v and not stop else "  => consistent")

print()
print("="*74)
print("PROBE 3 -- two buys on the SAME ticker in one close (MAX_PER_CLOSE=2)")
print("="*74)
open_pos = {}
tk = "KXBTC15M-PROBE"
for cost in (0.970, 0.960):
    open_pos[tk] = (1_000_000, "no", cost)      # verbatim pinrun line
print(f"  after 2 fills of {SIZE:g} contracts each, open_pos = {open_pos}")
contracts_held = 2 * SIZE
booked = SIZE
print(f"  contracts actually held {contracts_held:g}; reconcile() books {booked:g}")
lose_real = -(0.970 + 0.960) * SIZE
lose_booked = -0.960 * SIZE
print(f"  a losing close really costs ${lose_real:+.2f}; the ledger books "
      f"${lose_booked:+.2f}  ({100*(1-lose_booked/lose_real):.0f}% of the loss "
      f"is invisible to the abort)")

print()
print("="*74)
print("PROBE 4 -- a PARTIAL fill")
print("="*74)
pintake.reset_ledger()
body = pintake.build_take("T-part", "no", PRICE, SIZE, exchange_index=2)
stk = pintake.stake(body)
pintake.LEDGER["committed"] += stk
out = pintake.normalise(201, fill_response(2.0, 1.0 - PRICE, 0.002), body,
                        pintake.PROD_ELECTIONS)
out["refused"] = []
pintake._book(out, body, stk)
print(f"  requested {SIZE:g}, filled {out['filled']:g}, exec_price "
      f"{out['exec_price']}")
print(f"  pintake books contracts={pintake.LEDGER['positions']['T-part']['contracts']:g}"
      f" cost=${pintake.LEDGER['positions']['T-part']['cost']:.4f}")
cost = out["exec_price"]
pnl_pinrun = SIZE * (1.0 - cost) - math.ceil(pintake.expected_fee(cost, SIZE)*1e4)/1e4
pnl_true = out["filled"] * (1.0 - cost) - math.ceil(pintake.expected_fee(cost, out["filled"])*1e4)/1e4
print(f"  pinrun would book a WIN of ${pnl_pinrun:+.4f}; the truth is "
      f"${pnl_true:+.4f}  (overstated {pnl_pinrun/pnl_true:.1f}x)")
pnl_pinrun_l = SIZE * (-cost) - math.ceil(pintake.expected_fee(cost, SIZE)*1e4)/1e4
pnl_true_l = out["filled"] * (-cost) - math.ceil(pintake.expected_fee(cost, out["filled"])*1e4)/1e4
print(f"  and a LOSS of ${pnl_pinrun_l:+.4f} where the truth is ${pnl_true_l:+.4f}")

print()
print("="*74)
print("PROBE 5 -- billed_fee vs every real live fill on record")
print("="*74)
import glob
rows = 0
for f in sorted(glob.glob(r"C:\kals-repo\results\pinrun-live-*.jsonl")):
    for ln in open(f, encoding="utf-8"):
        try: d = json.loads(ln)
        except Exception: continue
        if d.get("kind") != "order" or not d.get("filled"):
            continue
        n = float(d["filled"]); ep = float(d["exec_price"])
        billed = math.ceil(pintake.expected_fee(ep, n) * 1e4) / 1e4
        rep = d.get("fee")
        rows += 1
        print(f"  {d['ticker'][:24]:24s} n={n:5.2f} exec={ep:.4f} "
              f"billed_fee=${billed:.4f}  exchange avg_fee_paid=${rep}  "
              f"x n = ${(rep or 0)*n:.4f}")
print(f"  {rows} filled orders on record")
