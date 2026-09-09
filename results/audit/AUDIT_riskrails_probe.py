#!/usr/bin/env python3
"""READ-ONLY probe. Imports pintake, drives its LEDGER in-process with a fake
wire, and reproduces the exact arithmetic pinrun.reconcile() performs at
--size 5. Sends nothing: ordercli.send is monkeypatched before any call.
Run: python results/audit/AUDIT_riskrails_probe.py
"""
import os, sys, math
sys.path.insert(0, r"C:\kals-repo\research")
import ordercli, pintake

SIZE = 5.0                      # the live process's --size
MAX_PER_CLOSE = 2               # pinrun.MAX_PER_CLOSE
LOSS_ABORT_FLAG = -21.00        # the live process's --loss-abort

def billed_fee(price, count=1):
    return math.ceil(pintake.expected_fee(price, count) * 10000.0) / 10000.0

def fake_fill(price):
    """A fake wire that fills the whole order at `price`."""
    def fs(base, pk, key_id, method, path, body=None, query=None):
        return 201, {"client_order_id": body["client_order_id"],
                     "fill_count": body["count"],
                     "remaining_count": "0.00",
                     "average_fill_price": body["price"],
                     "average_fee_paid": f"{pintake.expected_fee(price,1):.4f}",
                     "order_id": "probe-" + body["client_order_id"][-6:],
                     "ts_ms": 1}
    return fs

print("=" * 78)
print("PROBE 1 -- pintake.LOSS_ABORT is a size-1 literal and pinrun never sets it")
print("=" * 78)
print(f"  pintake.LOSS_ABORT      = ${pintake.LOSS_ABORT:.2f}")
print(f"  pinrun --loss-abort     = ${LOSS_ABORT_FLAG:.2f}")
one_loss = SIZE * 0.976 + billed_fee(0.976, SIZE)
print(f"  ONE ordinary loss at size {SIZE:g}, price 97.6c = -${one_loss:.2f}")
pintake.reset_ledger()
pintake.record_pnl(-one_loss, "one ordinary size-5 loss")
body = pintake.build_take("KXBTC15M-X", "yes", 0.976, SIZE, 2, "probe-1")
v = pintake.check_take(body, 1_800_000_030.0, 1_800_000_000.0,
                       base=pintake.DEMO)
print(f"  after that single loss, realised = ${pintake.LEDGER['realised']:+.2f}")
print(f"  check_take on the NEXT signal -> {'REFUSED' if v else 'allowed'}")
for s in v:
    print("      - " + s)
print(f"  pinrun.risk_abort would NOT fire: realised {pintake.LEDGER['realised']:+.2f} "
      f"> {LOSS_ABORT_FLAG:.2f}")

print()
print("=" * 78)
print("PROBE 2 -- the settlement stake release is per-CONTRACT, the commit is per-ORDER")
print("=" * 78)
pintake.reset_ledger()
real = ordercli.send
ordercli.send = fake_fill(0.97)
try:
    for i in range(6):
        out = pintake.take(pintake.DEMO, None, "k", f"TK{i}", "yes", 0.97,
                           SIZE, 1_800_000_030.0, exchange_index=2,
                           client_id=f"probe-2-{i}", now_epoch=1_800_000_000.0)
        assert not out.get("refused"), out.get("refused")
        cost = out["exec_price"]          # per contract, exactly as pinrun stores it
        committed_before = pintake.LEDGER["committed"]
        # ---- pinrun.reconcile(), copied verbatim ----
        pnl = (float(SIZE) * ((1.0 - cost)) - billed_fee(cost, SIZE))   # a WIN
        pintake.record_pnl(pnl)
        pintake.LEDGER["committed"] = max(
            0.0, float(pintake.LEDGER.get("committed", 0.0)) - cost)
        pintake.LEDGER["positions"].pop(f"TK{i}", None)
        # ---------------------------------------------
        print(f"  trade {i+1}: committed after fill ${committed_before:.4f} "
              f"-> after settlement ${pintake.LEDGER['committed']:.4f}   "
              f"(should be $0.0000; leaked ${pintake.LEDGER['committed']:.4f})")
finally:
    ordercli.send = real
print(f"  MAX_RUN_STAKE = ${pintake.MAX_RUN_STAKE:.2f};  committed now "
      f"${pintake.LEDGER['committed']:.4f} after 6 SETTLED WINS")
leak = SIZE * 0.97 - 0.97
print(f"  leak per settled trade = SIZE*price - price = ${leak:.4f}")
print(f"  trades until the stake cap halts the run: "
      f"{math.ceil(pintake.MAX_RUN_STAKE / leak)}")

print()
print("=" * 78)
print("PROBE 3 -- forward loss bound allows MAX_PER_CLOSE buys but budgets one")
print("=" * 78)
print(f"  risk_abort() tests:  realised - open_cost - 1.00*SIZE >= loss_abort")
print(f"  at SIZE={SIZE:g} that budgets ${SIZE:.2f} of further exposure,")
print(f"  but one loop pass can fire MAX_PER_CLOSE={MAX_PER_CLOSE} takes "
      f"= ${SIZE*MAX_PER_CLOSE:.2f}")
print(f"  shortfall per pass = ${SIZE*(MAX_PER_CLOSE-1):.2f}")
print(f"  worst case per close claimed in VERSIONS.md = "
      f"${1.00*SIZE*MAX_PER_CLOSE:.2f}  (arithmetic checks out)")
