#!/usr/bin/env python3
"""READ-ONLY probe 2. Reproduces pinrun.reconcile()'s arithmetic exactly for
(a) two buys on the SAME ticker in one close, and (b) a partial fill.
Nothing is sent; nothing is imported that can send.
"""
import math, sys
sys.path.insert(0, r"C:\kals-repo\research")
import pintake

SIZE = 5.0
def billed_fee(price, count=1):
    return math.ceil(pintake.expected_fee(price, count) * 10000.0) / 10000.0

print("=" * 78)
print("A -- TWO BUYS ON THE SAME TICKER IN ONE CLOSE (allowed: MAX_PER_CLOSE=2,")
print("     the improve-by gate does NOT check the ticker)")
print("=" * 78)
p1, p2 = 0.980, 0.970           # second is 1.0c cheaper -> passes IMPROVE_BY
real_contracts = 2 * SIZE
real_stake = SIZE * p1 + SIZE * p2
real_fee = billed_fee(p1, SIZE) + billed_fee(p2, SIZE)
print(f"  buy 1: {SIZE:g} @ {p1}   buy 2: {SIZE:g} @ {p2}")
print(f"  TRUE position: {real_contracts:g} contracts, stake ${real_stake:.4f}, "
      f"fees ${real_fee:.4f}")
# pinrun: open_pos[tk] = (close_s, want, cost)  -- a dict ASSIGNMENT
open_pos = {}
open_pos["TK"] = (0, "no", p1)
open_pos["TK"] = (0, "no", p2)          # OVERWRITES buy 1
_, want, cost = open_pos["TK"]
booked_open = SIZE * cost
print(f"  what open_pos holds after both fills: cost {cost} (buy 1 is GONE)")
print(f"  state['open_cost'] = SIZE * cost = ${booked_open:.4f}  "
      f"(true ${real_stake:.4f}; understated by ${real_stake-booked_open:.4f})")
loss_booked = SIZE * (-cost) - billed_fee(cost, SIZE)
loss_true = -(real_stake) - real_fee
print(f"  if it LOSES: reconcile books  ${loss_booked:+.4f}")
print(f"               the account loses ${loss_true:+.4f}")
print(f"               realised UNDER-REPORTS the loss by "
      f"${abs(loss_true - loss_booked):.4f}  ({100*(1-loss_booked/loss_true):.0f}%)")
print(f"  -> a -$21.00 abort fed halved losses stops at a TRUE "
      f"${-21.00 * (loss_true/loss_booked):.2f} drawdown")
win_booked = SIZE * (1 - cost) - billed_fee(cost, SIZE)
win_true = real_contracts - real_stake - real_fee
print(f"  if it WINS:  reconcile books  ${win_booked:+.4f}, true ${win_true:+.4f} "
      f"(realised UNDER-reports the win too)")
rel = cost
print(f"  committed released on settlement = ${rel:.4f} against "
      f"${real_stake:.4f} committed -> ${real_stake-rel:.4f} leaks")

print()
print("=" * 78)
print("B -- A PARTIAL IOC FILL (the fill count is read and then discarded)")
print("=" * 78)
filled = 2.0
price = 0.975
print(f"  order for {SIZE:g}, IOC filled {filled:g} at {price} "
      f"(the touch had thinned between the book snapshot and the send)")
print(f"  pinrun stores only the PRICE: open_pos[tk] = (close_s, want, {price})")
for won, label in ((True, "WIN "), (False, "LOSS")):
    booked = SIZE * ((1 - price) if won else -price) - billed_fee(price, SIZE)
    true = filled * ((1 - price) if won else -price) - billed_fee(price, filled)
    print(f"  {label}: reconcile books ${booked:+.4f}; true ${true:+.4f}; "
          f"error ${booked-true:+.4f}")
print("  a partial WIN inflates `realised`, which is the number the loss abort")
print("  reads -- the brake is handed headroom that does not exist.")
