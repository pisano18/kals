import json, math, os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import pinsize as P
rows=[]
for ln in open(P.ROWS,encoding="utf-8"):
    ln=ln.strip()
    if ln: rows.append(json.loads(ln))
for d in rows: d["pm"]=P.p_flip_model(d)

print("=== VERIFY AMENDMENT 4's table (pm<=0.02, NO EV floor) ===")
for lo,hi in ((3,10),(11,20),(21,30),(31,45),(46,60)):
    k=[d for d in rows if lo<=d["tau"]<=hi and d["pm"]<=0.02]
    fl=sum(1 for d in k if d["flip"]); cl=len(set(d["close"] for d in k))
    flc=len(set(d["close"] for d in k if d["flip"]))
    print(f"  tau {lo:2d}-{hi:2d}: {len(k):6d} moments  {fl:4d} flips on {flc} of {cl} closes"
          f"   model expects {sum(d['pm'] for d in k):7.2f}")

print("\n=== VERIFY 'the deep tail is entirely long-horizon': flips where p_model < 1e-6 ===")
for lo,hi in ((3,20),(21,40),(41,60)):
    k=[d for d in rows if lo<=d["tau"]<=hi and d["pm"]<1e-6]
    fl=sum(1 for d in k if d["flip"])
    print(f"  tau {lo:2d}-{hi:2d}: n={len(k):6d}  flips={fl:4d}")
k=[d for d in rows if d["pm"]<1e-6]
print(f"  ALL tau: n={len(k)} flips={sum(1 for d in k if d['flip'])}")

print("\n=== SIGMA: noisy or biased? what a stress multiplier costs at the gate ===")
def gate_n(mult,tmin=3,tmax=30):
    n=0; cl=set(); fl=0
    for d in rows:
        if not (tmin<=d["tau"]<=tmax): continue
        sd=P.move_sd(d["sig"]*mult, d["r"])
        pm=0.0 if sd<=0 else 0.5*math.erfc(abs(d["req"])/sd/math.sqrt(2.0))
        if pm>0.02: continue
        if P.ev_per_contract(d["price"],P.MEASURED_FLIP)-P.billed_fee(d["price"],1)<P.EV_FLOOR: continue
        n+=1; cl.add(d["close"]); fl+=d["flip"]
    return n,len(cl),fl
for m in (1.0,1.183,1.25,1.327,1.5):
    n,c,f=gate_n(m)
    print(f"  SIGMA_STRESS {m:5.3f}: eligible rows {n:5d} over {c:3d} closes, flips {f}")
