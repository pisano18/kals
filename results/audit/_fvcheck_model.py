"""READ-ONLY audit of pinrun's fair-value maths. No network, no orders."""
import os, sys, math, random, json, time
sys.path.insert(0, r"C:\kals-repo\research")
os.environ["KALS_SELFTESTED"] = "1"
import pinrun, settlewin, endgame
from engine import var_factor, N_AVG
from statistics import NormalDist
ND = NormalDist()
C = 1_000_000        # a synthetic close second

print("="*78); print("1. sd SCALING: sigma*sqrt(var_factor(r)) vs Monte Carlo")
print("="*78)
random.seed(7)
sigma = 3.0
print(f"{'r':>4} {'analytic sd':>14} {'MC sd (200k)':>14} {'ratio':>8}")
for r in (1,2,5,10,19,29,59,60):
    an = sigma*math.sqrt(var_factor(r,[1.0]))
    tot=[]
    for _ in range(200000):
        s=0.0; x=0.0
        for _ in range(r):
            x += random.gauss(0.0, sigma)
            s += x
        tot.append(s/60.0)
    m=sum(tot)/len(tot); mc=math.sqrt(sum((v-m)**2 for v in tot)/(len(tot)-1))
    print(f"{r:>4} {an:>14.6f} {mc:>14.6f} {mc/an:>8.4f}")

print()
print("="*78); print("2. pinrun.IndexWS.partial() BOUNDARIES vs settlewin.partial()")
print("="*78)
idx = pinrun.IndexWS(["T"])
for s in range(C-200, C+200): idx.ticks["T"][s] = 100.0
flat = {s:100.0 for s in range(C-200, C+200)}
print(f"{'tau':>5} {'pinrun locked_n':>16} {'pinrun r':>9} {'settlewin r':>12} "
      f"{'want r=tau-1':>13} {'agree':>6}")
for tau in (0,1,2,3,4,5,10,20,29,30,31,59,60,61,62):
    p1 = idx.partial("T", C, C-tau); p2 = settlewin.partial(flat, C, C-tau)
    n1 = None if p1 is None else round(p1[0]/100.0)
    r1 = None if p1 is None else p1[1]
    r2 = None if p2 is None else p2[1]
    want = max(0, min(60, tau-1)) if tau>=1 else 0
    print(f"{tau:>5} {str(n1):>16} {str(r1):>9} {str(r2):>12} {want:>13} "
          f"{str(r1==r2):>6}")

print("\n  NOTE tau<=0 (now at/after close): pinrun locks all 60 and r=0.")
print("  fair() then returns a HARD 1.0/0.0.  Reachable only if TAU_MIN<=0.")

print()
print("="*78); print("3. sigma == 0  ->  fair() returns a HARD 0/1 with NO uncertainty")
print("="*78)
z = pinrun.IndexWS(["Z"])
for s in range(C-400, C-2): z.ticks["Z"][s] = 500.0      # perfectly frozen value
sg = z.sigma("Z")
print(f"  frozen-but-printing feed: len(ticks)={len(z.ticks['Z'])}  sigma={sg!r}")
for eps in (1e-9, 1e-6, 0.01):
    f = pinrun.fair(z, "Z", C, C-3, 500.0-eps, sg, round_digits=2)
    print(f"    strike = spot - {eps:<8g} -> fair {f!r}   "
          f"net_edge vs a 0.95 offer = {100*pinrun.net_edge(f,0.95,'yes'):+.2f}c"
          f"   EV {100*pinrun.expected_value(0.95):+.2f}c")
f2 = pinrun.fair(z, "Z", C, C-3, 500.0+1e-9, sg, round_digits=None)
print(f"    strike = spot + 1e-9, no rounding -> fair {f2!r}  (buys the OTHER side)")

print()
print("="*78); print("4. sigma() AFTER A FEED GAP -- how much of the 300 s window is stale")
print("="*78)
g = pinrun.IndexWS(["G"])
random.seed(11)
v = 100.0
# 600 s of QUIET tape, then a 240 s outage, then 60 s of tape 5x more volatile
for s in range(C-1000, C-400):
    v += random.gauss(0, 0.01); g.ticks["G"][s] = v
for s in range(C-160, C-100):
    v += random.gauss(0, 0.05); g.ticks["G"][s] = v
secs = sorted(g.ticks["G"])[-pinrun.SIGMA_WIN:]
pre = sum(1 for s in secs if s < C-400); post = len(secs)-pre
print(f"  quiet sigma 0.01/s for 600 s, 240 s OUTAGE, then 60 s at 0.05/s")
print(f"  sigma() sample = last {len(secs)} PRESENT seconds: "
      f"{pre} pre-outage ({100*pre/len(secs):.0f}%), {post} post-outage")
print(f"  sigma() returns {g.sigma('G'):.5f}   true current sigma 0.05  "
      f"-> understated {0.05/g.sigma('G'):.2f}x")
print(f"  newest tick age at now=close-3: "
      f"{g.spot('G')[0]-(C-3)} s relative to now  -> index-age gate sees a "
      f"FRESH feed")
p = g.partial("G", C, C-3)
print(f"  partial() at tau=3: {'REFUSES' if p is None else 'ACCEPTS r=%d'%p[1]}"
      f"   (window [close-60,close-4] is fully covered by the post-outage tape)")

print()
print("="*78); print("5. STALENESS: what the index-age gate can and cannot see")
print("="*78)
now = time.time()
a = pinrun.IndexWS(["A"])
for s in range(int(now)-400, int(now)-9): a.ticks["A"][s] = 1.0
print(f"  feed frozen 10 s ago  -> spot age {a.spot('A')[2]:.2f}s  "
      f"gate({pinrun.MAX_INDEX_AGE_S}s) = "
      f"{'BLOCKS' if a.spot('A')[2] > pinrun.MAX_INDEX_AGE_S else 'PASSES'}")
b = pinrun.IndexWS(["B"])
for s in range(int(now)-400, int(now)-9): b.ticks["B"][s] = 1.0
b.ticks["B"][int(now)+8] = 1.0          # ONE tick stamped 8 s in the future
print(f"  same feed + ONE future-dated tick (+8 s) -> spot age "
      f"{b.spot('B')[2]:.2f}s  gate = "
      f"{'BLOCKS' if b.spot('B')[2] > pinrun.MAX_INDEX_AGE_S else 'PASSES'}"
      f"   <-- 10 s of stale data reported as fresh")
print(f"  last_rx (LOCAL receive ms) is recorded on every tick and is read "
      f"by NOTHING: {'last_rx' in open(r'C:\kals-repo\research\pinrun.py').read()}"
      f"  occurrences = "
      f"{open(r'C:\kals-repo\research\pinrun.py').read().count('last_rx')}")

print()
print("="*78); print("6. eff_strike vs endgame.settle_threshold (same maths?)")
print("="*78)
for k,d in ((2492.82,2),(0.0906904,7),(78794.73,2),(104.3213,4),(1.4349,None)):
    x, y = pinrun.eff_strike(k,d), endgame.settle_threshold(k,d)
    print(f"  K={k!r:<12} d={str(d):<5} pinrun {x!r:<22} endgame {y!r:<22} "
          f"{'AGREE' if x==y else 'DIFFER'}")
