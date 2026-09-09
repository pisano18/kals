"""Which rail actually binds first at --size 5 --loss-abort -21 --max-positions 3?
Read-only. No network, no orders."""
import os, sys, types
sys.path.insert(0, r"C:\kals-repo\research")
import pintake, pinrun
pinrun.SIZE = 5.0
a = types.SimpleNamespace(loss_abort=-21.00, max_positions=3)
P = pinrun.PRICE_CEILING
close = 2_000_000_000

print("ordinary ONE-CLOSE loss at size 5, price %.3f  = $%.2f" % (P, 5 * P))
print("pintake.LOSS_ABORT (module literal)            = $%.2f" % pintake.LOSS_ABORT)
print("pinrun --loss-abort (operator's flag)          = $%.2f" % a.loss_abort)

for realised in (0.0, -1.99, -2.00, -4.94, -9.88, -20.99, -21.00):
    pintake.reset_ledger()
    pintake.LEDGER["realised"] = realised
    body = pintake.build_take("T", "yes", P, count=5.0, exchange_index=2)
    v = pintake.check_take(body, close, close - 10)
    state = {"halted": False, "errors": 0, "open_cost": 0.0, "order_errors": 0}
    stop = pinrun.risk_abort(state, a)
    print("  realised $%7.2f -> pinrun.risk_abort: %-28s | pintake.check_take: %s"
          % (realised, stop or "ok", (v[0][:60] if v else "ALLOWED")))
