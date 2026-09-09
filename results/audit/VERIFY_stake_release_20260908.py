"""INDEPENDENT verification of the claimed committed-stake release bug.
READ-ONLY: never calls ordercli.send; drives pintake._book/check_take with
synthetic responses in this process only. Uses base=DEMO so production is
never armed.  Run:  python results/audit/VERIFY_stake_release_20260908.py
"""
import sys, os, re, ast, math, json
sys.path.insert(0, r"C:\kals-repo\research")
import pintake

# ---- 1. read the release line straight out of pinrun.py, no line numbers ----
src = open(r"C:\kals-repo\research\pinrun.py", encoding="utf-8").read()
lines = src.splitlines()
hits = [(i + 1, l) for i, l in enumerate(lines) if 'LEDGER["committed"]' in l]
print("pinrun.py lines touching LEDGER['committed']:")
for n, l in hits:
    print(f"  {n}: {l.strip()}")
# the reconcile tuple unpack
for i, l in enumerate(lines):
    if "close_s, want, cost = open_pos" in l or "open_pos[tk] = (close_s" in l:
        print(f"  {i+1}: {l.strip()}")

# ---- 2. drive the real ledger at the LIVE size and the LIVE fill price ----
SIZE = 5.0
PRICE = 0.975            # today's actual exec_price, buying NO
def resp(count, exec_yes, fee_per):
    return {"order": {"order_id": "probe", "client_order_id": "probe",
                      "fill_count": f"{count:.2f}", "remaining_count": "0.00",
                      "average_fill_price": exec_yes,
                      "average_fee_paid": fee_per}}

pintake.reset_ledger()
print(f"\nMAX_RUN_STAKE ${pintake.MAX_RUN_STAKE:.2f}  "
      f"pintake.LOSS_ABORT ${pintake.LOSS_ABORT:.2f}  "
      f"MAX_TAKE_COUNT {pintake.MAX_TAKE_COUNT}")
n_ok = 0
for i in range(30):
    body = pintake.build_take(f"T{i}", "no", PRICE, SIZE, exchange_index=2)
    stk = pintake.stake(body)
    v = pintake.check_take(body, 1e12, 1e12 - 10, base=pintake.DEMO)
    if v:
        print(f"  take {i+1:2d}: REFUSED -> {v}")
        break
    n_ok += 1
    pintake.LEDGER["committed"] += stk            # take(): intent in flight
    out = pintake.normalise(201, resp(SIZE, 1.0 - PRICE, 0.0017), body,
                            pintake.DEMO)
    out["refused"] = []
    pintake._book(out, body, stk)
    after_fill = pintake.LEDGER["committed"]
    # ---------- pinrun.reconcile(), copied verbatim from the file ----------
    cost = out["exec_price"]
    won = True
    pnl = SIZE * ((1.0 - cost) if won else (-cost))
    pintake.record_pnl(pnl)
    pintake.LEDGER["committed"] = max(
        0.0, float(pintake.LEDGER.get("committed", 0.0)) - cost)
    pintake.LEDGER["positions"].pop(f"T{i}", None)
    # ----------------------------------------------------------------------
    print(f"  take {i+1:2d}: stake ${stk:.4f}  committed after fill "
          f"${after_fill:6.3f} -> after release ${pintake.LEDGER['committed']:6.3f}"
          f"  open positions {len(pintake.LEDGER['positions'])}")
print(f"\n  fills before the rail refused: {n_ok}")
print(f"  committed still held with ZERO open positions: "
      f"${pintake.LEDGER['committed']:.3f}")

# ---- 3. the same loop at --size 1, to show the bug is size-dependent ----
for S in (1.0, 2.0, 5.0, 8.0, 10.0):
    pintake.reset_ledger()
    k = 0
    for i in range(200):
        body = pintake.build_take(f"T{i}", "no", PRICE, S, exchange_index=2)
        stk = pintake.stake(body)
        if pintake.check_take(body, 1e12, 1e12 - 10, base=pintake.DEMO):
            break
        k += 1
        pintake.LEDGER["committed"] += stk
        out = pintake.normalise(201, resp(S, 1.0 - PRICE, 0.0017), body,
                                pintake.DEMO)
        out["refused"] = []
        pintake._book(out, body, stk)
        cost = out["exec_price"]
        pintake.LEDGER["committed"] = max(
            0.0, pintake.LEDGER["committed"] - cost)
        pintake.LEDGER["positions"].pop(f"T{i}", None)
    print(f"  size {S:5g}: {k:3d} settled fills before every further take is "
          f"refused; stranded ${pintake.LEDGER['committed']:.2f}")
