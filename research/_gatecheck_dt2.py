import json, math, os, sys, random, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from engine import var_factor
ROWS = os.path.join(os.path.dirname(HERE), "results", "pindata", "rows.jsonl")
F=0.0090
def phi(z): return 0.5*math.erfc(-z/math.sqrt(2.0))
def msd(s,r): return 0.0 if (r<=0 or s<=0) else s*math.sqrt(var_factor(int(r),[1.0]))*(60.0/float(r))
def fee(p,n=1): return math.ceil(0.07*p*(1-p)*n*10000.0)/10000.0
def ev(p,f): return (1-f)*(1-p)-f*p
rows=[]
for ln in open(ROWS,encoding="utf-8"):
    ln=ln.strip()
    if ln: rows.append(json.loads(ln))
for d in rows:
    sd=msd(d["sig"],d["r"]); d["pm"]=0.0 if sd<=0 else phi(-abs(d["req"])/sd)
G=lambda lo,hi:[d for d in rows if lo<=d["tau"]<=hi and d["pm"]<=0.02 and ev(d["price"],F)-fee(d["price"],1)>=0.003]

print("=== C2. TAU-CONTROLLED: is price informative INSIDE a tau band? ===")
for lo,hi in ((31,45),(46,60),(51,60)):
    k=G(lo,hi); k.sort(key=lambda d:d["price"]); n=len(k); nb=4; st=max(1,n//nb)
    print(f" tau {lo}-{hi}  n={n}")
    for i in range(0,n,st):
        b=k[i:i+st]
        if len(b)<30: continue
        fl=sum(1 for d in b if d["flip"]); mp=sum(d['price'] for d in b)/len(b)
        print(f"   px[{b[0]['price']:.4f},{b[-1]['price']:.4f}] n={len(b):5d} fl={fl:3d} {100.0*fl/len(b):6.2f}%  meanpx {mp:.4f}  EV@0.9%={100*ev(mp,F):5.2f}c EV@obs={100*ev(mp,fl/len(b)):6.2f}c")

print("\n=== C3. TAU-CONTROLLED: is the MODEL's p_flip informative inside a tau band? ===")
for lo,hi in ((31,45),(46,60)):
    k=G(lo,hi); k.sort(key=lambda d:d["pm"]); n=len(k); st=max(1,n//4)
    print(f" tau {lo}-{hi}")
    for i in range(0,n,st):
        b=k[i:i+st]
        if len(b)<30: continue
        fl=sum(1 for d in b if d["flip"])
        print(f"   pm[{b[0]['pm']:.2e},{b[-1]['pm']:.2e}] n={len(b):5d} fl={fl:3d} {100.0*fl/len(b):6.2f}%  model mean {100*sum(d['pm'] for d in b)/len(b):6.3f}%")

print("\n=== F. flip CLUSTERING inside a close (gated tau 3-60) ===")
k=G(3,60); byc={}
for d in k: byc.setdefault(d["close"],[]).append(d)
fc=[(c,sum(1 for d in v if d["flip"]),len(v)) for c,v in byc.items() if any(d["flip"] for d in v)]
print(f"  {len(byc)} gated closes, {len(fc)} contain >=1 flip")
for c,f_,n_ in sorted(fc): print(f"    close {datetime.datetime.fromtimestamp(c,datetime.UTC):%m-%d %H:%M}  {f_}/{n_} rows flipped ({100.0*f_/n_:.0f}%)")

print("\n=== G. exact one-sided 95% upper bounds, CLOSE-clustered ===")
def cp_upper(k_,n_,conf=0.95):
    lo,hi=k_/float(n_),1.0
    for _ in range(200):
        m=0.5*(lo+hi); t=sum(math.comb(n_,i)*m**i*(1-m)**(n_-i) for i in range(k_+1))
        if t>1-conf: lo=m
        else: hi=m
    return 0.5*(lo+hi)
for tag,k_,n_ in (("study pop, per-CLOSE 0 flip-closes in 70",0,70),
                  ("tau3-20 gate (no EV floor), 0 in 111",0,111),
                  ("tau3-30 gate, 0 flip-closes in 83",0,83),
                  ("imported 3 in 333 (per trade)",3,333),
                  ("imported 3 in 333 -> per CLOSE if all 3 on 3 closes of 354",3,354)):
    print(f"  {tag:58s} CP95 upper = {100*cp_upper(k_,n_):6.3f}%")

print("\n=== H. per-DAY split of the study population ===")
e=G(3,20)
byd={}
for d in e:
    dt=datetime.datetime.fromtimestamp(d["close"],datetime.UTC).strftime("%m-%d")
    byd.setdefault(dt,[]).append(d)
for dt in sorted(byd):
    v=byd[dt]; cl=len(set(d["close"] for d in v))
    cheap=sum(1 for d in v if d["price"]<0.93)
    print(f"  {dt}: rows {len(v):4d} closes {cl:3d} meanpx {sum(d['price'] for d in v)/len(v):.4f} rows<93c {cheap:3d}")
