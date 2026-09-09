"""Part 2: how many dollars can this process actually have committed at once,
with --size 5 --loss-abort -21.00 --max-positions 3?  Drives the REAL
pinrun.risk_abort and pintake.check_take. Read-only, no network."""
import os, sys, types
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "research"))
import pintake, pinrun

pinrun.SIZE = 5.0                      # what globals()["SIZE"] = a.size does
a = types.SimpleNamespace(loss_abort=-21.00, max_positions=3)
pintake.reset_ledger()
state = {"halted": False, "errors": 0, "open_cost": 0.0, "order_errors": 0}

P = pinrun.PRICE_CEILING               # 0.988, the dearest we may ever pay
close = 2_000_000_000                  # any future close
peak = 0.0
for i in range(12):
    stop = pinrun.risk_abort(state, a)
    if stop:
        print("  HALT before buy %d: %s" % (i + 1, stop)); break
    body = pintake.build_take("T%d" % i, "yes", P, count=pinrun.SIZE, exchange_index=2)
    v = pintake.check_take(body, close, close - 10)
    if v:
        print("  check_take REFUSED buy %d: %s" % (i + 1, v)); break
    stk = pintake.stake(body)
    # simulate a FULL fill, exactly as _book() would book it
    pintake.LEDGER["committed"] += stk
    pintake.LEDGER["positions"]["T%d" % i] = {"want": "yes", "contracts": pinrun.SIZE,
                                              "cost": stk, "order_ids": []}
    state["open_cost"] = state["open_cost"] + stk    # reconcile(): SIZE * sum(price)
    peak = max(peak, pintake.LEDGER["committed"])
    print("  buy %d: stake $%.2f -> committed $%.2f, open_cost $%.2f, positions %d"
          % (i + 1, stk, pintake.LEDGER["committed"], state["open_cost"],
             len(pintake.LEDGER["positions"])))
print("\nPEAK COMMITTED REACHABLE = $%.2f" % peak)
print("MAX_RUN_STAKE = $%.2f   shard (claimed, live GET) = $38.8255" % pintake.MAX_RUN_STAKE)
print("headroom to shard: $%.2f" % (38.8255 - peak))

# Which rail actually stops a HUGE count?
print("\ncount rails, from pinrun's only call site count=SIZE:")
for c in (5.0, 10.0, 10.01, 25.0, 26.0):
    b = pintake.build_take("T", "yes", P, count=c, exchange_index=2)
    pintake.reset_ledger()
    v = pintake.check_take(b, close, close - 10)
    print("   count %6.2f  stake $%6.2f  -> %s" % (c, pintake.stake(b), v or "ALLOWED"))

# --- adversarial peak: risk_abort only runs at the TOP of the outer loop, so
#     a pass that starts under the cap may still fire MAX_PER_CLOSE buys.
print("\nadversarial peak (2 buys per outer pass, halt checked only at the top):")
pintake.reset_ledger()
state = {"halted": False, "errors": 0, "open_cost": 0.0, "order_errors": 0}
peak = 0.0; n = 0
for pass_ in range(10):
    stop = pinrun.risk_abort(state, a)
    if stop:
        print("  HALT at top of pass %d: %s" % (pass_ + 1, stop)); break
    for k in range(pinrun.MAX_PER_CLOSE):
        n += 1
        body = pintake.build_take("P%d" % n, "yes", P, count=pinrun.SIZE, exchange_index=2)
        v = pintake.check_take(body, close, close - 10)
        if v:
            print("   check_take refused: %s" % v); break
        stk = pintake.stake(body)
        pintake.LEDGER["committed"] += stk
        pintake.LEDGER["positions"]["P%d" % n] = {"want": "yes", "contracts": pinrun.SIZE,
                                                  "cost": stk, "order_ids": []}
        state["open_cost"] += stk
        peak = max(peak, pintake.LEDGER["committed"])
    print("  after pass %d: committed $%.2f, positions %d"
          % (pass_ + 1, pintake.LEDGER["committed"], len(pintake.LEDGER["positions"])))
print("ADVERSARIAL PEAK COMMITTED = $%.2f   vs shard $38.8255   vs MAX_RUN_STAKE $%.2f"
      % (peak, pintake.MAX_RUN_STAKE))
