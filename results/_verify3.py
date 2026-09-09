"""Independent check of the FLIP null and the exceedance grid."""
import json, math, sys, random
from collections import defaultdict
from statistics import NormalDist
sys.path.insert(0, r"C:\kals-repo\research")
from engine import var_factor
ND=NormalDist()
rows=[]
for line in open(r"C:\kals-repo\results\pindata\rows.jsonl",encoding="utf-8"):
    line=line.strip()
    if line: rows.append(json.loads(line))
def strat(r):
    p=r["price"]
    pb=(0 if p<0.70 else 1 if p<0.80 else 2 if p<0.90 else 3 if p<0.95 else 4 if p<0.98 else 5)
    return (pb, min(int(r["tau"]//10),5))
def imb(r):
    take=r["dep_n"] if r["side_yes"] else r["dep_y"]
    join=r["dep_y"] if r["side_yes"] else r["dep_n"]
    t=take+join
    return (join-take)/t if t>0 else 0.0
def lage(r): return math.log10(1.0+max(r["age_ms"],0))

print("A. FLIP RATE BY PRICE AND TAU (why strata are mandatory)")
for lo,hi in ((0.5,0.7),(0.7,0.8),(0.8,0.9),(0.9,0.95),(0.95,0.98),(0.98,1.0)):
    s=[r for r in rows if lo<=r["price"]<hi]
    if s: print(f"   price [{lo},{hi})  n={len(s):6d}  flip {100*sum(r['flip'] for r in s)/len(s):6.2f}%")
for lo,hi in ((2,10),(10,20),(20,30),(30,60),(60,201)):
    s=[r for r in rows if lo<=r["tau"]<hi]
    if s: print(f"   tau   [{lo},{hi})  n={len(s):6d}  flip {100*sum(r['flip'] for r in s)/len(s):6.2f}%")

def split_effect(sub,key,cut):
    bys=defaultdict(lambda:[[0,0],[0,0]])
    for r in sub:
        s=strat(r); hi=1 if key(r)>=cut else 0
        bys[s][hi][0]+= 1.0 if r["flip"] else 0.0; bys[s][hi][1]+=1
    num=0.0;den=0
    for s,(lo_,hi_) in bys.items():
        if lo_[1]<20 or hi_[1]<20: continue
        w=lo_[1]+hi_[1]; num+=w*(hi_[0]/hi_[1]-lo_[0]/lo_[1]); den+=w
    return num/den if den else None
def boot(sub,key,cut,B=1500,seed=3):
    cl=defaultdict(list)
    for r in sub: cl[r["close"]].append(r)
    ks=list(cl); rng=random.Random(seed); out=[]
    for _ in range(B):
        samp=[]
        for _ in range(len(ks)): samp.extend(cl[rng.choice(ks)])
        e=split_effect(samp,key,cut)
        if e is not None: out.append(e)
    out.sort(); return out[int(.025*len(out))], out[int(.975*len(out))]

print("\nB. FLIP: stratum-adjusted HIGH-minus-LOW, 95% CI, CLOSE block bootstrap")
print("   base flip rate %.3f pp   n=%d  closes=%d" % (100*sum(r['flip'] for r in rows)/len(rows), len(rows), len({r['close'] for r in rows})))
for lab,key in (("imbalance toward us", imb), ("log10 level age", lage),
                ("log10 size", lambda r: math.log10(1+r["size"])),
                ("spread c", lambda r: 100*(r["spread"] or 0.0))):
    vals=sorted(key(r) for r in rows); cut=vals[len(vals)//2]
    e=split_effect(rows,key,cut); lo,hi=boot(rows,key,cut)
    print(f"   {lab:<22} cut {cut:8.3f}  effect {100*e:+6.3f} pp  95% CI [{100*lo:+.3f}, {100*hi:+.3f}]")

print("\nC. EXCEEDANCE, and the |z|>3 grid vs volcheck")
spot={(r["sr"],r["sec"]):r["spot"] for r in rows}
n=e2=e3=0; bysr=defaultdict(lambda:[0,0])
for r in rows:
    s1=spot.get((r["sr"],r["sec"]+5))
    if s1 is None or r["sig"]<=0: continue
    z=(s1-r["spot"])/(r["sig"]*math.sqrt(5)); n+=1
    if abs(z)>2: e2+=1
    if abs(z)>3: e3+=1; bysr[r["sr"]][0]+=1
    bysr[r["sr"]][1]+=1
print(f"   n={n}  |z|>2 {100*e2/n:.2f}%  |z|>3 {100*e3/n:.2f}%")
for sr,(a,b) in sorted(bysr.items(), key=lambda kv:-kv[1][0]/max(kv[1][1],1)):
    print(f"     {sr:<12} n={b:6d}  |z|>3 {100*a/b:5.2f}%")
