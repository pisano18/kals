"""READ-ONLY. (a) sigma after a feed gap, with a window partial() ACCEPTS.
(b) how wrong sigma has to be before each REAL live trade loses money."""
import os, sys, math, random, json, glob
sys.path.insert(0, r"C:\kals-repo\research")
os.environ["KALS_SELFTESTED"] = "1"
import pinrun
from statistics import NormalDist
ND = NormalDist(); C = 1_000_000

print("="*78)
print("4b. sigma() AFTER A FEED GAP, window fully covered so partial() ACCEPTS")
print("="*78)
random.seed(11); g = pinrun.IndexWS(["G"]); v = 100.0
for s in range(C-1300, C-700):          # 600 s quiet
    v += random.gauss(0, 0.01); g.ticks["G"][s] = v
for s in range(C-460, C-2):             # 240 s OUTAGE, then 458 s at 5x vol
    v += random.gauss(0, 0.05); g.ticks["G"][s] = v
for nsec in (61, 120, 240, 300, 458):
    h = pinrun.IndexWS(["H"]); vv = 100.0
    random.seed(11)
    for s in range(C-1300, C-700):
        vv += random.gauss(0, 0.01); h.ticks["H"][s] = vv
    for s in range(C-2-nsec, C-2):
        vv += random.gauss(0, 0.05); h.ticks["H"][s] = vv
    secs = sorted(h.ticks["H"])[-pinrun.SIGMA_WIN:]
    pre = sum(1 for s in secs if s < C-700)
    p = h.partial("H", C, C-3)
    sg = h.sigma("H")
    print(f"  {nsec:>4} s of fresh tape since the outage: "
          f"partial(tau=3) {'ACCEPTS' if p else 'refuses'}   "
          f"sigma sample {pre}/{len(secs)} pre-outage   "
          f"sigma {sg:.5f} vs true 0.05  -> {0.05/sg:.2f}x too small")

print()
print("="*78)
print("6. THE 16 REAL LIVE TRADES: how wrong can sigma be before each loses?")
print("="*78)
print("  breakeven flip rate at price p is f* = 1 - p - fee(p)   (exact)")
print("  model flip     = 1-fair (yes) or fair (no)")
print("  k = the factor by which TRUE sigma must exceed the estimate for the")
print("      model's own flip to reach f*  (z scales as 1/k)")
print()
rows=[]
for fn in sorted(glob.glob(r"C:\kals-repo\results\pinrun-live-*.jsonl")):
    for ln in open(fn, encoding="utf-8"):
        try: d = json.loads(ln)
        except Exception: continue
        if d.get("kind") == "signal": rows.append(d)
print(f"{'ticker':<26}{'tau':>4}{'price':>8}{'fair':>9}{'f_model':>10}"
      f"{'f_break':>9}{'z_mod':>7}{'z_brk':>7}{'k':>7}")
ks=[]
for d in rows:
    p = d["price"]; f = d["fair"]
    fee = math.ceil(0.07*p*(1-p)*10000)/10000
    fbrk = 1.0 - p - fee
    fmod = (1.0-f) if d["want"]=="yes" else f
    fmod = max(fmod, 1e-12)
    zmod = ND.inv_cdf(1.0-fmod); zbrk = ND.inv_cdf(1.0-fbrk)
    k = zmod/zbrk if zbrk>0 else float('inf')
    ks.append(k)
    print(f"{d['ticker']:<26}{d['tau']:>4}{p:>8.4f}{f:>9.5f}"
          f"{100*fmod:>9.3f}%{100*fbrk:>8.2f}%{zmod:>7.2f}{zbrk:>7.2f}{k:>7.2f}")
ks_s = sorted(ks)
print(f"\n  sigma-error headroom k: min {min(ks):.2f}x  median "
      f"{ks_s[len(ks_s)//2]:.2f}x  max {max(ks):.2f}x")
print(f"  trades with k < 1.5x (a 50% vol miss kills them): "
      f"{sum(1 for k in ks if k<1.5)} of {len(ks)}")
print(f"  trades with k < 2.0x: {sum(1 for k in ks if k<2.0)} of {len(ks)}")
print()
print("  AT THE GATE ITSELF (fair exactly 0.98, the worst allowed trade):")
for p in (0.95, 0.97, 0.976, 0.985, 0.988):
    fee = math.ceil(0.07*p*(1-p)*10000)/10000
    fbrk = 1.0-p-fee
    if fbrk <= 0:
        print(f"    p={p:.3f}  breakeven flip {100*fbrk:+.2f}% -- NEGATIVE, "
              f"no flip rate makes this pay"); continue
    zb = ND.inv_cdf(1-fbrk)
    print(f"    p={p:.3f}  f_break {100*fbrk:5.2f}%  z_break {zb:.2f}  "
          f"k = {2.0537/zb:.2f}x   (model z at fair 0.98 = 2.054)")
