#!/usr/bin/env python3
"""ADVERSARIAL RE-CHECK of the claim "the real floor is -$25.90, not -$21.00".

The cited probe (AUDIT_abort_bound.py) called pinrun.risk_abort() ALONE. An
order does not leave this process through risk_abort; it leaves through
pintake.take(), whose check_take() is a SECOND, INDEPENDENT rail. This probe
runs the whole chain at the live config. It opens no socket and sends nothing.
"""
import sys
sys.path.insert(0, r"C:\kals-repo\research")
import pinrun, pintake

pinrun.SIZE = 5.0
class A:
    loss_abort = -21.00
    max_positions = 3

NOW = 1_800_000_000.0
CLOSE = NOW + 15.0           # tau 15 s, inside the live 3-30 s window
PRICE = pinrun.PRICE_CEILING # 0.988, the dearest the run will pay

def chain(realised, open_cost, positions=0, committed=0.0):
    pintake.reset_ledger()
    pintake.LEDGER["realised"] = realised
    pintake.LEDGER["committed"] = committed
    pintake.LEDGER["positions"] = {f"T{i}": {} for i in range(positions)}
    stop = pinrun.risk_abort({"halted": False, "errors": 0,
                              "open_cost": open_cost}, A)
    body = pintake.build_take("KXBTC15M-X", "yes", PRICE, pinrun.SIZE, 2, "cid")
    viol = pintake.check_take(body, CLOSE, NOW, base=pintake.PROD_ELECTIONS)
    return stop, viol

print(f"live config: SIZE={pinrun.SIZE:g} MAX_PER_CLOSE={pinrun.MAX_PER_CLOSE} "
      f"loss_abort={A.loss_abort} max_positions={A.max_positions} "
      f"price_ceiling={PRICE}")
print(f"pintake rails: LOSS_ABORT=${pintake.LOSS_ABORT:.2f}  "
      f"MAX_RUN_STAKE=${pintake.MAX_RUN_STAKE:.2f}  "
      f"MAX_TAKE_COUNT={pintake.MAX_TAKE_COUNT:g}")
print(f"pintake.LOSS_ABORT overridden by pinrun anywhere? "
      f"{'YES' if 'pintake.LOSS_ABORT' in open(r'C:\kals-repo\research\pinrun.py', encoding='utf-8').read() else 'NO'}")
print()
print("THE CLAIMED PATH: realised walks down to -16.00 with nothing open,")
print("then one pass fires 2 x 5 contracts. Does an order actually get sent?")
print(f"{'realised':>10} {'open':>7} | {'pinrun.risk_abort':<22} | pintake.check_take")
for rl in (0.0, -1.00, -1.99, -2.00, -2.01, -5.00, -10.00, -16.00, -20.99):
    stop, viol = chain(rl, 0.0)
    a = ("HALT" if stop else "allows")
    b = ("SENDS" if not viol else "REFUSED: " + viol[0][:46])
    print(f"{rl:10.2f} {0.0:7.2f} | {a:<22} | {b}")
print()
print("Binary search for the LEAST negative realised at which pintake refuses:")
lo = 0.0
for rl in [-x/100 for x in range(0, 400)]:
    _, viol = chain(rl, 0.0)
    if viol:
        print(f"  first refusal at realised ${rl:.2f}  ({viol[0]})")
        break
print()
print("WORST CASE THE CHAIN ACTUALLY PERMITS")
print("  takes are possible only while realised > pintake.LOSS_ABORT, i.e. > "
      f"${pintake.LOSS_ABORT:.2f}")
per = pinrun.SIZE * PRICE
print(f"  one position costs at most SIZE*ceiling = ${per:.2f}")
for n_open in (0, 1, 2, 3, 4):
    stop, viol = chain(-1.99, n_open * per, positions=n_open)
    print(f"  realised -1.99 with {n_open} open (${n_open*per:6.2f}) -> "
          f"risk_abort {'HALT: '+stop if stop else 'allows'}; "
          f"pintake {'REFUSED' if viol else 'SENDS'}")
print()
print("  floor = pintake.LOSS_ABORT + (positions reachable) x cost, all lost:")
for n in (3, 4):
    print(f"    {n} positions: ${pintake.LOSS_ABORT:.2f} - {n} x ${per:.2f} "
          f"= ${pintake.LOSS_ABORT - n*per:.2f}")
