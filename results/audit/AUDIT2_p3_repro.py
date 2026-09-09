"""READ-ONLY independent repro of the P3 claim: sigma()==0 -> fair() hard 1/0
-> every downstream gate in pinrun's loop passes.  No network, no orders."""
import os, sys, math
sys.path.insert(0, r"C:\kals-repo\research")
os.environ["KALS_SELFTESTED"] = "1"
import pinrun
from engine import var_factor

C = 1_000_000
print("== 1. is sigma() exactly 0.0 on a frozen-but-printing feed? ==")
z = pinrun.IndexWS(["Z"])
for s in range(C - 400, C - 2):
    z.ticks["Z"][s] = 500.0
sg = z.sigma("Z")
print(f"   held seconds {len(z.ticks['Z'])}   sigma() -> {sg!r}   "
      f"is None? {sg is None}")

print("\n== 2. how FEW frozen seconds are enough? (sparse-tick variant) ==")
for flat in (500, 302, 301, 300, 100, 30, 22, 21, 20):
    y = pinrun.IndexWS(["Y"])
    for s in range(C - flat, C):
        y.ticks["Y"][s] = 7.0
    v = y.sigma("Y")
    print(f"   {flat:4d} consecutive frozen seconds, nothing else -> sigma {v!r}")
# sparse variant: 300 held seconds of which only 25 are consecutive, all frozen
w = pinrun.IndexWS(["W"])
s = C - 5000
import random
random.seed(3)
val = 100.0
for i in range(275):                       # 275 held seconds, all >1s apart
    val += random.gauss(0, 0.5)
    w.ticks["W"][s] = val
    s += 3
for k in range(26):                        # then a 26-second FLAT run
    w.ticks["W"][s + k] = val
print(f"   275 sparse (3 s apart) + a 26 s flat run -> sigma "
      f"{w.sigma('W')!r}   (held {len(w.ticks['W'])})")

print("\n== 3. fair() with sigma == 0 ==")
for eps in (1e-9, 1e-6, 0.01, 1.0):
    f_hi = pinrun.fair(z, "Z", C, C - 3, 500.0 - eps, 0.0, round_digits=2)
    f_lo = pinrun.fair(z, "Z", C, C - 3, 500.0 + eps, 0.0, round_digits=None)
    print(f"   strike = spot-{eps:<8g} -> fair {f_hi!r}    "
          f"strike = spot+{eps:<8g} -> fair {f_lo!r}")

print("\n== 4. do the downstream gates pass?  (live args: SIZE 5) ==")
pinrun.SIZE = 5.0
f = 1.0
print(f"   {'price':>7} {'net_edge':>10} {'>=EDGE_FLOOR':>13} "
      f"{'<=CEILING':>10} {'EV':>9} {'>=EV_FLOOR':>11} {'FIRES?':>7} "
      f"{'true EV @p*=0.5':>16}")
for price in (0.50, 0.52, 0.60, 0.75, 0.90, 0.95, 0.988, 0.99):
    e = pinrun.net_edge(f, price, "yes")
    ev = pinrun.expected_value(price)
    fires = (e >= pinrun.EDGE_FLOOR and price <= pinrun.PRICE_CEILING
             and ev >= pinrun.EV_FLOOR)
    true_ev = 0.5 * (1 - price) - 0.5 * price - pinrun.billed_fee(price, 1)
    print(f"   {price:7.3f} {100*e:9.2f}c {str(e>=pinrun.EDGE_FLOOR):>13} "
          f"{str(price<=pinrun.PRICE_CEILING):>10} {100*ev:8.2f}c "
          f"{str(ev>=pinrun.EV_FLOOR):>11} {str(fires):>7} "
          f"{100*true_ev:14.2f}c")

print("\n== 5. is the r<=0 branch reachable at TAU_MIN=3? ==")
t = pinrun.IndexWS(["T"])
for s in range(C - 400, C + 5):
    t.ticks["T"][s] = 100.0
for tau in range(1, 8):
    p = t.partial("T", C, C - tau)
    print(f"   tau={tau}: partial -> r={None if p is None else p[1]}"
          f"   (TAU_MIN={pinrun.TAU_MIN})")

print("\n== 6. can var_factor make sd<=0 with a healthy sigma? ==")
bad = [r for r in range(1, 61) if var_factor(r, [1.0]) <= 0]
print(f"   r in 1..60 with var_factor<=0: {bad}   -> sd<=0 requires sigma==0")

print("\n== 7. is there any guard between sigma() and fair() in the loop? ==")
src = open(r"C:\kals-repo\research\pinrun.py", encoding="utf-8").read()
i = src.index("sg = idx.sigma(iid)", src.index("def run("))
print("   " + "\n   ".join(src[i:i+260].splitlines()))
