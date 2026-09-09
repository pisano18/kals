"""INDEPENDENT VERIFICATION of the claim:
   risk_abort()'s forward loss bound reserves ONE buy where MAX_PER_CLOSE
   allows two.

Read-only. Imports pinrun, drives risk_abort() directly with the LIVE
arguments (--size 5 --loss-abort -21.00 --max-positions 3), and replays the
inner-loop gate sequence to see how many buys can occur between two
consecutive risk_abort() calls.  Sends nothing.  Touches no data dir.
"""
import os, sys
os.environ["KALS_SELFTESTED"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "research"))
import pinrun, pintake


class A:                      # the LIVE arguments
    size = 5.0
    loss_abort = -21.00
    max_positions = 3
    minutes = 720.0


pinrun.SIZE = A.size          # main() does globals()["SIZE"] = a.size
saved = dict(pintake.LEDGER)
pintake.reset_ledger()

print("CONSTANTS")
print(f"  SIZE                 {pinrun.SIZE:g}")
print(f"  MAX_PER_CLOSE        {pinrun.MAX_PER_CLOSE}")
print(f"  IMPROVE_BY           {pinrun.IMPROVE_BY}")
print(f"  PRICE_CEILING        {pinrun.PRICE_CEILING}")
print(f"  pintake.LOSS_ABORT   {pintake.LOSS_ABORT:.2f}   <-- module constant")
print(f"  pintake.MAX_RUN_STAKE ${pintake.MAX_RUN_STAKE:.2f}")
print(f"  pinrun --loss-abort  {A.loss_abort:.2f}")
print()

# ---- 1. where does the forward bound actually halt? -----------------------
print("1. FORWARD BOUND: scan open_cost with realised = 0")
edge = None
oc = 0.0
while oc <= 30.0:
    s = pinrun.risk_abort({"halted": False, "errors": 0, "open_cost": oc}, A)
    if s and edge is None:
        edge = oc
        print(f"   first halt at open_cost ${oc:.2f}: {s}")
        break
    oc += 0.01
last_ok = round(edge - 0.01, 2)
print(f"   last open_cost that still TRADES: ${last_ok:.2f}")
print(f"   -> worst-case at that point = -${last_ok:.2f}")
print(f"   room reserved = 1.00*SIZE = ${1.00*A.size:.2f}")
print(f"   room needed if a close can buy MAX_PER_CLOSE = "
      f"${1.00*A.size*pinrun.MAX_PER_CLOSE:.2f}")
print()

# ---- 2. how many buys fit between two risk_abort() calls? ----------------
# Replay the inner loop's own gate sequence over two tickers that share a
# close_s (all crypto 15M series settle on the same quarter hour).
print("2. BUYS PER PASS: replay the inner-loop gates over one pass")
fired = {}
close_s = 1788886800
book = [("KXBTC15M-...", 0.985), ("KXETH15M-...", 0.975)]   # 2nd is cheaper
buys = []
for tk, price in book:
    prev = fired.get(close_s)                      # keyed by CLOSE, not ticker
    if prev is not None and prev["n"] >= pinrun.MAX_PER_CLOSE:
        print(f"   {tk} skipped: MAX_PER_CLOSE reached")
        continue
    if prev is not None and price >= prev["best"] - pinrun.IMPROVE_BY:
        print(f"   {tk} skipped: not {pinrun.IMPROVE_BY} cheaper than "
              f"{prev['best']}")
        continue
    if price > pinrun.PRICE_CEILING:
        print(f"   {tk} skipped: over the price ceiling")
        continue
    if prev is None:
        fired[close_s] = {"n": 1, "best": price, "tk": tk}
    else:
        prev["n"] += 1
        prev["best"] = min(prev["best"], price)
    buys.append((tk, price))
    print(f"   {tk} BUYS at {price}  (cost ${price*A.size:.2f})")
cost = sum(p for _, p in buys) * A.size
print(f"   buys in ONE pass: {len(buys)}   total cost ${cost:.2f}")
print("   risk_abort() runs ONCE per pass (line 940), before this loop;")
print("   state['open_cost'] is only recomputed by reconcile() (line 893),")
print("   also once per pass -- so nothing re-checks between these two buys.")
print()

# ---- 3. the overshoot, and what upstream rails leave of it ---------------
print("3. OVERSHOOT")
print(f"   worst at top of pass (bound allows): -${last_ok:.2f}")
print(f"   after {len(buys)} same-pass buys:      "
      f"-${last_ok + cost:.2f}   vs abort ${A.loss_abort:.2f}")
print(f"   nominal overshoot: ${last_ok + cost + A.loss_abort:.2f}")
print()
print("   BUT two upstream rails cap how negative `worst` can be while a")
print("   take is still permitted:")
print(f"     a) pintake.LOSS_ABORT = {pintake.LOSS_ABORT:.2f} refuses EVERY take")
print(f"        once realised <= {pintake.LOSS_ABORT:.2f}. --loss-abort does NOT change it.")
print(f"     b) --max-positions {A.max_positions} halts at the top of the pass, so at")
print(f"        most {A.max_positions-1} positions are open when a buy is allowed.")
max_open = (A.max_positions - 1) * pinrun.PRICE_CEILING * A.size
reach_worst = pintake.LOSS_ABORT - max_open
print(f"   => reachable worst at top of a trading pass >= "
      f"${reach_worst:.2f}  (realised >{pintake.LOSS_ABORT:.2f}, "
      f"open<=${max_open:.2f})")
add = pinrun.MAX_PER_CLOSE * pinrun.PRICE_CEILING * A.size
print(f"   => after {pinrun.MAX_PER_CLOSE} same-pass buys: "
      f"${reach_worst - add:.2f}")
print(f"   => REACHABLE overshoot past ${A.loss_abort:.2f}: "
      f"${abs(min(0.0, reach_worst - add - A.loss_abort)):.2f}")
print()

# ---- 4. does the proposed fix close it? ---------------------------------
print("4. WITH room = SIZE * MAX_PER_CLOSE, would that state have halted?")
room_fix = 1.00 * A.size * pinrun.MAX_PER_CLOSE
print(f"   room {room_fix:.2f}: halt when worst < {A.loss_abort + room_fix:.2f}")
print(f"   reachable worst {reach_worst:.2f} < {A.loss_abort + room_fix:.2f}"
      f"  -> {'HALTS (fix closes it)' if reach_worst < A.loss_abort + room_fix else 'still trades'}")

pintake.LEDGER.clear(); pintake.LEDGER.update(saved)
