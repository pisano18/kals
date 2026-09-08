"""Deployment-gate cross-check. READ-ONLY. New file."""
import json, math, os, sys, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor
ROWS = os.path.join(os.path.dirname(HERE), "results", "pindata", "rows.jsonl")
F = 0.0090

def phi(z): return 0.5*math.erfc(-z/math.sqrt(2.0))
def move_sd(sig, r):
    if r <= 0 or sig <= 0: return 0.0
    return sig*math.sqrt(var_factor(int(r), [1.0]))*(60.0/float(r))
def pmodel(d):
    sd = move_sd(d["sig"], d["r"])
    return 0.0 if sd <= 0 else phi(-abs(d["req"])/sd)
def fee(p, n=1): return math.ceil(0.07*p*(1-p)*n*10000.0)/10000.0
def ev(p, f): return (1-f)*(1-p) - f*p

rows = []
with open(ROWS, encoding="utf-8") as fh:
    for ln in fh:
        ln = ln.strip()
        if ln: rows.append(json.loads(ln))
for d in rows:
    d["pm"] = pmodel(d)
    d["z"] = abs(d["req"])/move_sd(d["sig"], d["r"]) if move_sd(d["sig"], d["r"])>0 else 0.0
print("rows", len(rows), "flips", sum(1 for d in rows if d["flip"]))

def gate(taumin, taumax, evfloor=0.003, pmax=0.02):
    k=[d for d in rows if taumin<=d["tau"]<=taumax and d["pm"]<=pmax
       and ev(d["price"],F)-fee(d["price"],1) >= evfloor]
    return k
def summ(tag, k):
    cl = sorted(set(d["close"] for d in k))
    fl = sum(1 for d in k if d["flip"])
    flc = len(set(d["close"] for d in k if d["flip"]))
    print(f"{tag:38s} rows {len(k):6d}  closes {len(cl):4d}  flips {fl:5d} on {flc:4d} closes")
    return k

print("\n=== A. gate reproduction ===")
e = summ("tau 3-20, pm<=.02, EV>=0.3c  [STUDY]", gate(3,20))
summ("tau 3-20, pm<=.02, no EV floor", gate(3,20,-9))
summ("tau 3-30, pm<=.02, EV>=0.3c  [LIVE now]", gate(3,30))
summ("tau 21-30, pm<=.02, EV>=0.3c", gate(21,30))
summ("tau 31-45, pm<=.02, EV>=0.3c", gate(31,45))
summ("tau 46-60, pm<=.02, EV>=0.3c", gate(46,60))
summ("tau 3-60, pm<=.02, EV>=0.3c", gate(3,60))
summ("tau 3-20, pm<=.02, EV>=0.5c(old)", gate(3,20,0.005))

print("\n=== B. marginal-gate rows (pm in [0.01,0.02]) ===")
for lo,hi,tmin,tmax in ((0.01,0.02,3,20),(0.01,0.02,3,30),(0.01,0.02,3,60),
                        (0.002,0.01,3,60),(0.0,0.002,3,60)):
    k=[d for d in rows if tmin<=d["tau"]<=tmax and lo<d["pm"]<=hi
       and ev(d["price"],F)-fee(d["price"],1)>=0.003]
    fl=sum(1 for d in k if d["flip"])
    mp=sum(d["price"] for d in k)/len(k) if k else 0
    print(f"  pm ({lo},{hi}] tau {tmin}-{tmax}: n={len(k):6d} flips={fl:5d} rate={100.0*fl/max(1,len(k)):7.3f}%  meanpx={mp:.4f}")

print("\n=== C. is PRICE informative about flips inside the gate? (tau 31-60, where flips exist) ===")
k = gate(31,60)
k.sort(key=lambda d: d["price"])
nb=6; step=max(1,len(k)//nb)
for i in range(0,len(k),step):
    b=k[i:i+step]
    if len(b)<20: continue
    fl=sum(1 for d in b if d["flip"])
    print(f"  px [{b[0]['price']:.4f},{b[-1]['price']:.4f}] n={len(b):5d} flips={fl:4d} rate={100.0*fl/len(b):7.3f}%  EV@0.9%={100*(ev(sum(d['price'] for d in b)/len(b),F)):.2f}c  EV@realised={100*ev(sum(d['price'] for d in b)/len(b), fl/len(b)):.2f}c")

print("\n=== D. same, tau 3-60 all gated ===")
k = gate(3,60)
k.sort(key=lambda d: d["price"])
step=max(1,len(k)//8)
for i in range(0,len(k),step):
    b=k[i:i+step]
    if len(b)<20: continue
    fl=sum(1 for d in b if d["flip"])
    print(f"  px [{b[0]['price']:.4f},{b[-1]['price']:.4f}] n={len(b):5d} flips={fl:4d} rate={100.0*fl/len(b):7.3f}%")

print("\n=== E. study population: days, closes, price distribution ===")
import datetime
days={}
for d in e:
    dt=datetime.datetime.fromtimestamp(d["close"], datetime.UTC).strftime("%Y-%m-%d")
    days.setdefault(dt,set()).add(d["close"])
for dt in sorted(days): print(f"  {dt}: {len(days[dt])} closes")
px=sorted(d["price"] for d in e)
print(f"  price min {px[0]:.4f} p25 {px[len(px)//4]:.4f} med {px[len(px)//2]:.4f} p75 {px[3*len(px)//4]:.4f} max {px[-1]:.4f}")
print(f"  rows with price < 0.93 (TIER's 2-contract trigger): {sum(1 for d in e if d['price']<0.93)}")
print(f"  z: min {min(d['z'] for d in e):.2f} med {sorted(d['z'] for d in e)[len(e)//2]:.2f} max {max(d['z'] for d in e):.2f}")
