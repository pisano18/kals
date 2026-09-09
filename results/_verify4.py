import json, math, sys
from collections import defaultdict
rows=[json.loads(l) for l in open(r"C:\kals-repo\results\pindata\rows.jsonl",encoding="utf-8") if l.strip()]
spot={(r["sr"],r["sec"]):r["spot"] for r in rows}
# their quoted raw split: tau 3-30, median level age 795ms, fwd/past exceedance
sub=[]
for r in rows:
    if not (3<=r["tau"]<=30): continue
    s1=spot.get((r["sr"],r["sec"]+5)); s0=spot.get((r["sr"],r["sec"]-5))
    if s1 is None or s0 is None or r["sig"]<=0: continue
    zf=(s1-r["spot"])/(r["sig"]*math.sqrt(5)); zb=(r["spot"]-s0)/(r["sig"]*math.sqrt(5))
    sub.append((r,1.0 if abs(zf)>3 else 0.0,1.0 if abs(zb)>3 else 0.0))
ages=sorted(r["age_ms"] for r,_,_ in sub); med=ages[len(ages)//2]
print("tau 3-30 with both windows: n=",len(sub)," median level age ms=",med)
for lab,sel in (("FRESH (< median)", lambda a:a<med),("OLD (>= median)", lambda a:a>=med)):
    s=[x for x in sub if sel(x[0]["age_ms"])]
    print(f"   {lab:<18} n={len(s):5d}  forward |z|>3 {100*sum(x[1] for x in s)/len(s):.2f}%   past |z|>3 {100*sum(x[2] for x in s)/len(s):.2f}%")

# price-cell 2x2, both boundary conventions
import math as _m
from statistics import NormalDist
sys.path.insert(0,r"C:\kals-repo\research")
from engine import var_factor
ND=NormalDist()
def fee(p,n=1): return _m.ceil(0.07*p*(1-p)*n*10000)/10000
for r in rows:
    rr=int(r["r"]); sd=r["sig"]*_m.sqrt(var_factor(rr,[1.0])) if rr>0 else 0.0
    fair=(1.0 if r["req"]<=0 else 0.0) if sd<=0 else ND.cdf(-r["req"]/(sd*(60.0/rr)))
    r["pw"]=fair if r["side_yes"] else 1.0-fair
    r["edge"]=r["pw"]-r["price"]-fee(r["price"],1)
    r["ev"]=(1-0.009)*(1-r["price"])-0.009*r["price"]-fee(r["price"])
idx={(r["tk"],r["sec"]):r for r in rows}
el=[r for r in rows if (3<=r["tau"]<=30 and r["pw"]>=0.98 and r["edge"]>=0.003
        and r["price"]<=0.988 and r["ev"]>=0.003 and r["size"]>=1.0)]
def goneof(r):
    nx=idx[(r["tk"],r["sec"]+1)]
    return 1 if (nx["side_yes"]!=r["side_yes"] or nx["price"]>r["price"] or nx["size"]<1.0) else 0
for lab,lo,hi,inc in (("[0.95,0.988)",0.95,0.988,False),("[0.95,0.988]",0.95,0.988,True)):
    cell=[r for r in el if (r["tk"],r["sec"]+1) in idx and lo<=r["price"] and (r["price"]<=hi if inc else r["price"]<hi)]
    a=sorted(r["age_ms"] for r in cell); m=a[len(a)//2]
    old=[r for r in cell if r["age_ms"]>=m]; new=[r for r in cell if r["age_ms"]<m]
    sp=sorted(100*(r["spread"] or 0) for r in cell); ms=sp[len(sp)//2]
    w=[r for r in cell if 100*(r["spread"] or 0)>=ms]; t=[r for r in cell if 100*(r["spread"] or 0)<ms]
    print(f"\nprice {lab}: n={len(cell)} median age {m}ms  median spread {ms:.2f}c")
    print(f"   old {100*sum(map(goneof,old))/len(old):.1f}% (n={len(old)})  new {100*sum(map(goneof,new))/len(new):.1f}% (n={len(new)})")
    print(f"   wide {100*sum(map(goneof,w))/len(w):.1f}% (n={len(w)})  tight {100*sum(map(goneof,t))/len(t):.1f}% (n={len(t)})")
