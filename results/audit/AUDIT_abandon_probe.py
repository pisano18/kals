"""READ-ONLY PROBE. Measures what the two give-up branches in pinrun.reconcile()
(lines 856-863) actually do to the risk rails, at the LIVE arguments:
  --size 5 --loss-abort -21.00 --max-positions 3
Sends nothing. Imports pinrun/pintake only for their constants and risk_abort().
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "research"))
import pintake, pinrun


class A:                       # the live argv, exactly
    size = 5.0
    loss_abort = -21.00
    max_positions = 3


setattr(pinrun, "SIZE", 5.0)
a = A()
CEIL = pinrun.PRICE_CEILING
per = a.size * CEIL            # dollars a single filled position costs, at worst
print(f"PRICE_CEILING {CEIL}  SIZE {a.size}  max cost per position ${per:.2f}")
print(f"pintake.MAX_RUN_STAKE ${pintake.MAX_RUN_STAKE:.2f}  "
      f"pintake.LOSS_ABORT ${pintake.LOSS_ABORT:+.2f}  "
      f"pinrun --loss-abort ${a.loss_abort:+.2f}")
print()

def rails(stranded, realised=0.0, open_cost=0.0):
    pintake.reset_ledger()
    L = pintake.LEDGER
    L["realised"] = realised
    L["committed"] = stranded * per + open_cost
    for i in range(stranded):
        L["positions"][f"ABANDONED{i}"] = {"contracts": a.size}
    st = {"halted": False, "errors": 0, "open_cost": open_cost}
    return pinrun.risk_abort(st, a)

print("A. after N abandoned positions (realised untouched, open_cost released):")
for n in range(0, 5):
    r = rails(n)
    print(f"   {n} abandoned -> committed ${n*per:6.2f}  positions {n}  "
          f"risk_abort: {r!r}")
print()

print("B. the same states, but with the loss BOOKED (what _abandon would do):")
for n in range(0, 5):
    r = rails(0, realised=-n * per)
    print(f"   {n} abandoned, realised ${-n*per:+7.2f} -> risk_abort: {r!r}")
print()

# worst-case real loss the run can reach with the leak, vs. the intended bound
# The run keeps trading while risk_abort() is None. Walk it.
print("C. worst case walk: every abandoned position was a LOSS, none booked")
hidden = 0.0
n = 0
while True:
    r = rails(n)
    if r:
        print(f"   halts at {n} abandoned: {r}")
        break
    n += 1
    hidden += per
    if n > 10:
        print("   never halts")
        break
print(f"   hidden (unbooked) real loss at the halt: ${-hidden:.2f}")
# realised floor while still trading: the forward bound allows realised down to
# loss_abort + 1.00*SIZE (with nothing open); pintake's own LOSS_ABORT is tighter.
floor_pinrun = a.loss_abort + 1.00 * a.size
floor_pintake = pintake.LOSS_ABORT
print(f"   realised floor allowed by pinrun's forward bound: ${floor_pinrun:+.2f}")
print(f"   realised floor allowed by pintake's own gate:     ${floor_pintake:+.2f}")
worst_total = hidden + abs(max(floor_pinrun, floor_pintake))
print(f"   WORST REAL LOSS (hidden + visible, pintake gate binding): "
      f"${-(hidden + abs(floor_pintake)):.2f}")
print(f"   WORST REAL LOSS if pintake's -$2 gate were raised to match: "
      f"${-(hidden + abs(floor_pinrun)):.2f}")
print(f"   INTENDED bound: ${a.loss_abort:.2f}")
