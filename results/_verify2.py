"""Independent re-estimation of the persistence result with a DIFFERENT
estimator: stratum-adjusted, block bootstrap over CLOSES. No shared code."""
import json, math, os, sys, random
from collections import defaultdict
from statistics import NormalDist
sys.path.insert(0, r"C:\kals-repo\research")
from engine import var_factor
ND=NormalDist()
def fee(p,n=1): return math.ceil(0.07*p*(1-p)*n*10000)/10000
rows=[]
for line in open(r"C:\kals-repo\results\pindata\rows.jsonl",encoding="utf-8"):
    line=line.strip()
    if not line: continue
    r=json.loads(line); rr=int(r["r"])
    sd=r["sig"]*math.sqrt(var_factor(rr,[1.0])) if rr>0 else 0.0
    fair=(1.0 if r["req"]<=0 else 0.0) if sd<=0 else ND.cdf(-r["req"]/(sd*(60.0/rr)))
    pw=fair if r["side_yes"] else 1.0-fair
    r["pw"]=pw; p=r["price"]
    r["edge"]=pw-p-fee(p,1); r["ev"]=(1-0.009)*(1-p)-0.009*p-fee(p)
    rows.append(r)
idx={(r["tk"],r["sec"]):r for r in rows}
def elig(r):
    return (3<=r["tau"]<=30 and r["pw"]>=0.98 and r["edge"]>=0.003
            and r["price"]<=0.988 and r["ev"]>=0.003 and r["size"]>=1.0)
obs=[]
for r in rows:
    if not elig(r): continue
    nx=idx.get((r["tk"],r["sec"]+1))
    if nx is None: continue
    gone=1.0 if (nx["side_yes"]!=r["side_yes"] or nx["price"]>r["price"] or nx["size"]<1.0) else 0.0
    obs.append((r,gone))
print("n obs",len(obs),"closes",len({r['close'] for r,_ in obs}))

# --- 1. cluster concentration -------------------------------------------
cc=defaultdict(int)
for r,_ in obs: cc[r["close"]]+=1
v=sorted(cc.values(),reverse=True)
tot=sum(v)
print("\n1. CLUSTER CONCENTRATION (rows per close)")
print("   closes",len(v),"  max",v[0]," top5 share %.1f%%"%(100*sum(v[:5])/tot),
      " top10 share %.1f%%"%(100*sum(v[:10])/tot))
# Kish effective number of clusters
print("   Kish effective clusters = %.1f" % (tot*tot/sum(x*x for x in v)))

# --- 2. is 'gone' anti-correlated with the model EDGE? -------------------
print("\n2. ARE THE SURVIVING QUOTES THE LOW-EDGE ONES?")
for lab,f in (("model edge (c)", lambda r:100*r["edge"]),
              ("price (c)",      lambda r:100*r["price"]),
              ("EV (c)",         lambda r:100*r["ev"]),
              ("tau (s)",        lambda r:r["tau"])):
    g=[f(r) for r,y in obs if y>0]; s=[f(r) for r,y in obs if y==0]
    print(f"   {lab:<16} gone {sum(g)/len(g):8.3f}   still {sum(s)/len(s):8.3f}   diff {sum(g)/len(g)-sum(s)/len(s):+8.3f}")

# --- 3. stratum-adjusted 2x2 with a CLOSE block bootstrap ---------------
def strat(r):
    p=r["price"]
    pb=(0 if p<0.70 else 1 if p<0.80 else 2 if p<0.90 else 3 if p<0.95 else 4 if p<0.98 else 5)
    return (pb, min(int(r["tau"]//10),5))
def split_effect(sub, key, cut):
    """within-stratum difference in gone-rate, high minus low on `key`."""
    bys=defaultdict(lambda:[[0,0],[0,0]])
    for r,y in sub:
        s=strat(r); hi=1 if key(r)>=cut else 0
        bys[s][hi][0]+=y; bys[s][hi][1]+=1
    num=0.0; den=0
    for s,(lo,hi) in bys.items():
        if lo[1]<5 or hi[1]<5: continue
        w=lo[1]+hi[1]
        num+=w*(hi[0]/hi[1]-lo[0]/lo[1]); den+=w
    return num/den if den else None
def boot(sub,key,cut,B=2000,seed=1):
    cl=defaultdict(list)
    for r,y in sub: cl[r["close"]].append((r,y))
    ks=list(cl); rng=random.Random(seed); out=[]
    for _ in range(B):
        samp=[]
        for _ in range(len(ks)): samp.extend(cl[rng.choice(ks)])
        e=split_effect(samp,key,cut)
        if e is not None: out.append(e)
    out.sort()
    return out[int(.025*len(out))], out[int(.975*len(out))]
ages=sorted(r["age_ms"] for r,_ in obs); amed=ages[len(ages)//2]
sps=sorted(100*(r["spread"] or 0) for r,_ in obs); smed=sps[len(sps)//2]
szs=sorted(r["size"] for r,_ in obs); zmed=szs[len(szs)//2]
print("\n3. STRATUM-ADJUSTED HIGH-minus-LOW, 95% CI from a CLOSE block bootstrap")
for lab,key,cut in (("level age >= %dms"%amed, lambda r:r["age_ms"], amed),
                    ("spread >= %.2fc"%smed, lambda r:100*(r["spread"] or 0), smed),
                    ("size >= %.1f"%zmed, lambda r:r["size"], zmed)):
    e=split_effect(obs,key,cut); lo,hi=boot(obs,key,cut)
    print(f"   {lab:<22} effect {100*e:+7.2f} pp   95% CI [{100*lo:+.2f}, {100*hi:+.2f}]")

# --- 4. is level age < 1000ms nearly the whole story? --------------------
print("\n4. LEVEL AGE, RAW (no regression), whole eligible sample")
bins=[(0,250),(250,500),(500,1000),(1000,2000),(2000,10**9)]
for lo,hi in bins:
    sub=[(r,y) for r,y in obs if lo<=r["age_ms"]<hi]
    if sub: print(f"   age [{lo},{hi}) n={len(sub):5d}  gone {100*sum(y for _,y in sub)/len(sub):5.1f}%")
