#!/usr/bin/env python3
"""Same chain probe, with pintake's production flag set the way the LIVE run
sets it (pinrun.arm() -> pintake.arm_prod), so the base rail stops masking the
loss rail. Opens no socket. Calls check_take only -- take() is never called.
"""
import sys
sys.path.insert(0, r"C:\kals-repo\research")
import pinrun, pintake
pintake.arm_prod("READ-ONLY AUDIT: check_take only, take() is never called")
pinrun.SIZE = 5.0
class A:
    loss_abort = -21.00
    max_positions = 3
NOW = 1_800_000_000.0
CLOSE = NOW + 15.0
PRICE = pinrun.PRICE_CEILING

def chain(realised, open_cost, positions=0, committed=0.0, price=PRICE):
    pintake.reset_ledger()
    pintake.LEDGER["realised"] = realised
    pintake.LEDGER["committed"] = committed
    pintake.LEDGER["positions"] = {f"T{i}": {} for i in range(positions)}
    stop = pinrun.risk_abort({"halted": False, "errors": 0,
                              "open_cost": open_cost}, A)
    body = pintake.build_take("KXBTC15M-X", "yes", price, pinrun.SIZE, 2, "cid")
    viol = pintake.check_take(body, CLOSE, NOW, base=pintake.PROD_ELECTIONS)
    return stop, viol

print(f"{'realised':>9} | {'pinrun.risk_abort':<10} | pintake.check_take")
for rl in (0.0, -1.00, -1.90, -1.99, -2.00, -2.01, -5.00, -16.00, -20.99, -21.00):
    stop, viol = chain(rl, 0.0)
    print(f"{rl:9.2f} | {('HALT' if stop else 'allows'):<10} | "
          f"{'SENDS' if not viol else 'REFUSED: ' + viol[0][:60]}")
print()
print("committed / MAX_RUN_STAKE ladder at realised 0 (concurrent exposure):")
for cm in (0.0, 40.0, 50.0, 55.06, 55.07, 59.0):
    stop, viol = chain(0.0, cm, committed=cm)
    print(f"  committed ${cm:6.2f} -> risk_abort "
          f"{'HALT: '+stop[:40] if stop else 'allows':<46} pintake "
          f"{'SENDS' if not viol else 'REFUSED: ' + viol[0][:48]}")
