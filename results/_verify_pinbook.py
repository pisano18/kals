#!/usr/bin/env python3
"""INDEPENDENT hand-reconciliation of pinbook's headline arithmetic.
Written without importing pinbook. Only engine.var_factor is shared (it is
the settlement variance identity, established elsewhere)."""
import json, math, os, sys
from collections import defaultdict
from statistics import NormalDist
sys.path.insert(0, r"C:\kals-repo\research")
from engine import var_factor
ND = NormalDist()
P = r"C:\kals-repo\results\pindata\rows.jsonl"

def fee(p, n=1):
    return math.ceil(0.07*p*(1-p)*n*10000)/10000

rows = []
with open(P, encoding="utf-8") as fh:
    for line in fh:
        line=line.strip()
        if not line: continue
        r=json.loads(line)
        rr=int(r["r"])
        sd = r["sig"]*math.sqrt(var_factor(rr,[1.0])) if rr>0 else 0.0
        fair = (1.0 if r["req"]<=0 else 0.0) if sd<=0 else ND.cdf(-r["req"]/(sd*(60.0/rr)))
        pw = fair if r["side_yes"] else 1.0-fair
        p = r["price"]
        r["pw"]=pw
        r["edge"]=pw-p-fee(p,1)
        r["ev"]=(1-0.0090)*(1-p)-0.0090*p-fee(p)
        rows.append(r)

print("A. WHOLE TABLE")
print("   rows        ", len(rows))
print("   markets     ", len({r['tk'] for r in rows}))
print("   closes      ", len({r['close'] for r in rows}))
print("   flips       ", sum(1 for r in rows if r['flip']))
print("   flip rate pp", 100.0*sum(1 for r in rows if r['flip'])/len(rows))

def elig(r):
    return (3<=r["tau"]<=30 and r["pw"]>=0.98 and r["edge"]>=0.003
            and r["price"]<=0.988 and r["ev"]>=0.003 and r["size"]>=1.0)
el=[r for r in rows if elig(r)]
print("\nB. ELIGIBLE (live v7 rule)")
print("   rows        ", len(el))
print("   closes      ", len({r['close'] for r in el}))
print("   markets     ", len({r['tk'] for r in el}))
print("   flips       ", sum(1 for r in el if r['flip']))
print("   tau range   ", min(r['tau'] for r in el), max(r['tau'] for r in el))
print("   price range ", min(r['price'] for r in el), max(r['price'] for r in el))

# C. price improvement, first tradeable moment per market
bym=defaultdict(list)
for r in el: bym[r['tk']].append(r)
nimp=0; tot=0; gains=[]
for tk,rs in bym.items():
    rs.sort(key=lambda r:r['sec'])
    first=rs[0]; later=[x for x in rs[1:] if x['sec']>first['sec']]
    tot+=1
    bl=min((x['price'] for x in later), default=None)
    g=0.0 if bl is None else max(0.0, first['price']-bl)
    gains.append(100*g)
    if bl is not None and bl <= first['price']-0.005: nimp+=1
print("\nC. PRICE IMPROVEMENT")
print("   first moments (= markets with >=1 eligible row)", tot)
print("   closes                                        ", len({bym[t][0]['close'] for t in bym}))
print("   improved by >=0.5c                            ", nimp, f"{100.0*nimp/tot:.2f}%")
print("   mean best improvement incl zeros (c)          ", f"{sum(gains)/len(gains):.4f}")

# D. persistence
idx={}
dup=0
for r in rows:
    k=(r['tk'],r['sec'])
    if k in idx: dup+=1
    idx[k]=r
print("\nD. PERSISTENCE  (duplicate (tk,sec) keys in whole table:", dup, ")")
have=0; gone=0; why=defaultdict(int); worse=[]
nonext=0
for r in el:
    nx=idx.get((r['tk'], r['sec']+1))
    if nx is None:
        nonext+=1; continue
    have+=1
    if nx['side_yes']!=r['side_yes']: g,w=1,'side'
    elif nx['price']>r['price']: g,w=1,'price_worse'
    elif nx['size']<1.0: g,w=1,'dust'
    else: g,w=0,'still'
    gone+=g; why[w]+=1
    if w=='price_worse': worse.append(100*(nx['price']-r['price']))
worse.sort()
print("   eligible moments      ", len(el))
print("   have next-second row  ", have, f"({100.0*have/len(el):.2f}%)   no next: {nonext}")
print("   gone/worse            ", gone, f"= {100.0*gone/have:.2f}%")
print("   why                   ", dict(why))
print("   median worse (c)      ", f"{worse[len(worse)//2]:.2f}", " p10", f"{worse[len(worse)//10]:.2f}", " p90", f"{worse[9*len(worse)//10]:.2f}")
print("   closes in persist set ", len({r['close'] for r in el if (r['tk'],r['sec']+1) in idx}))

# E. jump
spot={}
best={}
for r in rows:
    spot[(r['sr'],r['sec'])]=r['spot']
    k=(r['sr'],r['sec'])
    c=best.get(k)
    if c is None or r['tau']<c['tau']: best[k]=r
n=0;miss=0;e2=0;e3=0
for k in best:
    sr,sec=k; r=best[k]
    s1=spot.get((sr,sec+5))
    if s1 is None: miss+=1; continue
    if r['sig']<=0: continue
    z=(s1-r['spot'])/(r['sig']*math.sqrt(5))
    n+=1
    if abs(z)>2: e2+=1
    if abs(z)>3: e3+=1
print("\nE. JUMP GRID")
print("   (series,second) with 5s forward window", n, "  without", miss)
print("   |z|>2", e2, f"{100.0*e2/n:.2f}%   |z|>3 {e3} {100.0*e3/n:.2f}%")
print("   closes in jump set", len({best[k]['close'] for k in best if (best[k]['sr'],best[k]['sec']+5) in spot}))

# F. hand 2x2 inside one price cell, no regression
cell=[r for r in el if 0.95<=r['price']<0.988 and (r['tk'],r['sec']+1) in idx]
print("\nF. HAND 2x2 inside price 0.95-0.988, n =", len(cell))
ages=sorted(r['age_ms'] for r in cell); med=ages[len(ages)//2]
print("   median level age ms", med)
def goneof(r):
    nx=idx[(r['tk'],r['sec']+1)]
    return 1 if (nx['side_yes']!=r['side_yes'] or nx['price']>r['price'] or nx['size']<1.0) else 0
old=[r for r in cell if r['age_ms']>=med]; new=[r for r in cell if r['age_ms']<med]
print(f"   OLD levels gone {100.0*sum(goneof(r) for r in old)/len(old):.1f}%  (n={len(old)})")
print(f"   NEW levels gone {100.0*sum(goneof(r) for r in new)/len(new):.1f}%  (n={len(new)})")
sp=sorted(100*(r['spread'] or 0.0) for r in cell); msp=sp[len(sp)//2]
wide=[r for r in cell if 100*(r['spread'] or 0)>=msp]; tight=[r for r in cell if 100*(r['spread'] or 0)<msp]
print("   median spread c", f"{msp:.2f}")
print(f"   WIDE  spread gone {100.0*sum(goneof(r) for r in wide)/len(wide):.1f}%  (n={len(wide)})")
print(f"   TIGHT spread gone {100.0*sum(goneof(r) for r in tight)/len(tight):.1f}%  (n={len(tight)})")
