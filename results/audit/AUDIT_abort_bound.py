#!/usr/bin/env python3
"""READ-ONLY probe 3. Calls pinrun.risk_abort() directly at the LIVE config
(size 5, MAX_PER_CLOSE 2, --loss-abort -21.00, --max-positions 3) and maps
where it fires. Imports pinrun but starts no sockets and sends nothing.
"""
import sys
sys.path.insert(0, r"C:\kals-repo\research")
import pinrun, pintake

pinrun.SIZE = 5.0                      # what main() sets from --size
class A:
    loss_abort = -21.00
    max_positions = 3

def probe(realised, open_cost, positions=0, committed=0.0):
    pintake.reset_ledger()
    pintake.LEDGER["realised"] = realised
    pintake.LEDGER["committed"] = committed
    pintake.LEDGER["positions"] = {f"T{i}": {} for i in range(positions)}
    return pinrun.risk_abort({"halted": False, "errors": 0,
                              "open_cost": open_cost}, A)

print(f"SIZE={pinrun.SIZE:g}  MAX_PER_CLOSE={pinrun.MAX_PER_CLOSE}  "
      f"loss_abort={A.loss_abort}  max_positions={A.max_positions}")
print(f"pintake.MAX_RUN_STAKE=${pintake.MAX_RUN_STAKE:.2f}  "
      f"pintake.LOSS_ABORT=${pintake.LOSS_ABORT:.2f}  "
      f"MAX_TAKE_COUNT={pintake.MAX_TAKE_COUNT:g}  HARD_MAX={pintake.HARD_MAX:g}")
print()
print("  forward bound: realised - open_cost - 1.00*SIZE >= loss_abort")
for oc in (0.0, 4.90, 9.80, 14.70, 15.90, 16.00, 16.10, 19.80):
    r = probe(0.0, oc)
    print(f"    realised $0.00, open ${oc:6.2f} -> "
          f"{'HALT: ' + r if r else 'keeps trading'}")
print()
print("  realised-only ladder (open 0):")
for rl in (-4.89, -9.78, -14.67, -15.99, -16.01, -19.56, -21.00):
    r = probe(rl, 0.0)
    print(f"    realised ${rl:7.2f} -> {'HALT: ' + r if r else 'keeps trading'}")
print()
print("  position cap:")
for n in (0, 1, 2, 3):
    r = probe(0.0, 0.0, positions=n)
    print(f"    {n} open positions -> {'HALT: ' + r if r else 'keeps trading'}")
print()
print("  what one loop pass can add AFTER the check passes:")
print(f"    MAX_PER_CLOSE={pinrun.MAX_PER_CLOSE} takes x SIZE={pinrun.SIZE:g} "
      f"x $1.00 = ${pinrun.MAX_PER_CLOSE*pinrun.SIZE:.2f} of new exposure,")
print(f"    against the ${1.00*pinrun.SIZE:.2f} the bound budgeted.")
print(f"    positions can reach max_positions-1+MAX_PER_CLOSE = "
      f"{A.max_positions-1+pinrun.MAX_PER_CLOSE}, not {A.max_positions}.")
