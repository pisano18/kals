"""Independent re-derivation of the LOSS_ABORT finding. Read-only: imports the
real modules in THIS process, calls check_take/risk_abort only. Sends nothing."""
import os, sys, types
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "research"))
import pintake, pinrun

print(f"pintake.LOSS_ABORT      = ${pintake.LOSS_ABORT:.2f}   (module literal)")
print(f"pintake.MAX_TAKE_COUNT  = {pintake.MAX_TAKE_COUNT:g}")
print(f"pintake.MAX_RUN_STAKE   = ${pintake.MAX_RUN_STAKE:.2f}")
print(f"live flag --loss-abort  = $-21.00")
print()

SIZE = 5.0
PRICE = 0.975          # the price the ONE real live fill went off at today
pinrun.SIZE = SIZE     # pinrun.risk_abort reads module-global SIZE

class A:  # stand-in for argparse namespace with the LIVE arguments
    loss_abort = -21.00
    max_positions = 3
    size = SIZE

# --- the loss pinrun itself would book for one ordinary losing close --------
loss = SIZE * (-PRICE) - pinrun.billed_fee(PRICE, SIZE)
print(f"one ordinary LOSS at {PRICE:.3f} x {SIZE:g} = ${loss:+.4f}  "
      f"(pinrun.reconcile arithmetic, incl. billed fee)")

pintake.reset_ledger()
pintake.record_pnl(0.1164, "the one win the live run has actually booked")
print(f"ledger realised starts at ${pintake.LEDGER['realised']:+.4f} "
      f"(from results/pinrun-live-20260908T163644Z.jsonl)")
pintake.record_pnl(loss, "first ordinary loss")
print(f"after ONE loss:  realised = ${pintake.LEDGER['realised']:+.4f}")
print()

now = 1_800_000_000.0
body = pintake.build_take("KXBTC15M-TEST", "no", PRICE, SIZE, 2, "cid")
v = pintake.check_take(body, now + 15.0, now, base=pintake.PROD_ELECTIONS)
print("pintake.check_take (the ORDER rail) ->")
for s in v:
    print("    REFUSED:", s)
if not v:
    print("    ACCEPTED")

state = {"halted": False, "errors": 0, "order_errors": 0, "open_cost": 0.0}
print(f"pinrun.risk_abort (the OPERATOR's brake, -$21) -> {pinrun.risk_abort(state, A)!r}")
print()

# --- how many wins must bank BEFORE a loss for the order rail to survive it --
win = SIZE * (1.0 - PRICE) - pinrun.billed_fee(PRICE, SIZE)
need = (abs(pintake.LOSS_ABORT) + abs(loss)) / win
print(f"one WIN at {PRICE:.3f} x {SIZE:g} = ${win:+.4f}")
print(f"wins needed banked before a loss to stay above ${pintake.LOSS_ABORT:.2f}: "
      f"{need:.1f}")

# --- does anything anywhere assign pintake.LOSS_ABORT? ----------------------
import re
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                        "research", "pinrun.py"), encoding="utf-8").read()
print("assignments to pintake.LOSS_ABORT in pinrun.py:",
      re.findall(r"pintake\.LOSS_ABORT\s*=", src) or "NONE")
