"""Break the constant-flip-rate assumption that Table 2 rests on."""
import json, math, os, sys, datetime
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import pinsize as P
rows=[]
for ln in open(P.ROWS,encoding="utf-8"):
    ln=ln.strip()
    if ln: rows.append(json.loads(ln))
def gate(tmin,tmax):
    k=[d for d in rows if tmin<=d["tau"]<=tmax and P.p_flip_model(d)<=P.PFLIP_MAX
       and P.ev_per_contract(d["price"],P.MEASURED_FLIP)-P.billed_fee(d["price"],1)>=P.EV_FLOOR]
    k.sort(key=lambda d:(d["close"],d["sec"],d["tk"])); c={}
    for d in k: c.setdefault(d["close"],[]).append(d)
    return c,k

# --- relative risk by price, MEASURED on tau 31-60 (the only flips we have) --
_,L=gate(31,60)
EDGES=[0.0,0.955,0.970,0.978,0.984,1.01]
def bin_(p):
    for i in range(len(EDGES)-1):
        if EDGES[i]<=p<EDGES[i+1]: return i
    return len(EDGES)-2
cnt=[0]*5; fl=[0]*5
for d in L:
    b=bin_(d["price"]); cnt[b]+=1; fl[b]+=d["flip"]
base=sum(fl)/sum(cnt)
RR=[(fl[i]/cnt[i])/base if cnt[i] else 1.0 for i in range(5)]
print("relative risk by price, fitted on tau 31-60 gated (n=%d, %d flips, base %.3f%%)"%(sum(cnt),sum(fl),100*base))
for i in range(5):
    print(f"  px [{EDGES[i]:.3f},{EDGES[i+1]:.3f}) n={cnt[i]:5d} flips={fl[i]:3d} rate={100*fl[i]/max(1,cnt[i]):6.3f}%  RR={RR[i]:5.2f}")

C,E=gate(3,20)
RULES=[("FLAT1","once",P._flat(1),1),("FLAT2","once",P._flat(2),2),
       ("PRICE_TIER cap2","once",P._price_tier,2),
       ("EV_PROP cap2","once",P._ev_prop,2),
       ("SCALE_IMPROVE cap2 LIVE","improve",P._one,2),
       ("TIER_IMPROVE cap2","improve",P._price_tier,2),
       ("EV_IMPROVE cap2","improve",P._ev_prop,2)]

def run(fmap, tag, target=0.0090):
    # normalise so the mean flip prob over the eligible population is `target`
    m=sum(fmap(d["price"]) for d in E)/len(E)
    k=target/m
    print(f"\n--- {tag} (scaled so mean f over 593 eligible rows = {100*target:.2f}%) ---")
    print(f"  {'rule':<24}{'contr':>7}{'Ec/close':>10}{'Ec/contract':>13}{'vs LIVE':>10}")
    base=None
    for name,mode,fn,cap in RULES:
        buys,_,_=P.replay(C,mode,fn,cap,1)
        byc={}
        for b in buys:
            f=min(0.5,k*fmap(b.price))
            byc[b.close]=byc.get(b.close,0.0)+P.ev_order(b.price,b.n,f)
        tot=sum(byc.values()); nc=len(byc); ncon=sum(b.n for b in buys)
        if name.endswith("LIVE"): base=tot/nc
        print(f"  {name:<24}{ncon:>7}{100*tot/nc:>10.2f}{100*tot/ncon:>13.2f}"
              f"{'' if base is None else format(100*(tot/nc-base),'>+10.2f')}")

run(lambda p:1.0, "A. CONSTANT f -- the study's assumption")
run(lambda p:RR[bin_(p)], "B. f PROPORTIONAL TO MEASURED RISK-BY-PRICE (tau 31-60 shape)")
run(lambda p:(1.0-p), "C. f PROPORTIONAL TO (1-price) -- the market is proportionally right")
run(lambda p:max(P.p_flip_model_price if False else 1e-9, 1.0), "D. dummy")
# E. f proportional to the MODEL's own p_flip (model ordering is informative)
pm={}
for d in E: pm[(d["close"],d["tk"],round(d["price"],4))]=P.p_flip_model(d)
def fmodel(p):
    return 1.0  # placeholder, replaced below
print("\n--- E. f PROPORTIONAL TO THE MODEL's p_flip (ordering informative, level rescaled) ---")
mm=sum(max(P.p_flip_model(d),1e-9)**0.5 for d in E)/len(E)
print(f"  (using sqrt(p_model) as the shape; mean shape {mm:.4f})")
print(f"  {'rule':<24}{'contr':>7}{'Ec/close':>10}{'Ec/contract':>13}")
lookup={}
for d in E: lookup.setdefault((d["close"],d["tk"]),[]).append((d["price"],max(P.p_flip_model(d),1e-12)))
k=0.0090/mm
for name,mode,fn,cap in RULES:
    buys,_,_=P.replay(C,mode,fn,cap,1)
    byc={}
    for b in buys:
        cand=lookup.get((b.close,b.tk),[])
        pmv=min((abs(px-b.price),pv) for px,pv in cand)[1] if cand else 1e-6
        f=min(0.5,k*math.sqrt(pmv))
        byc[b.close]=byc.get(b.close,0.0)+P.ev_order(b.price,b.n,f)
    tot=sum(byc.values()); nc=len(byc); ncon=sum(b.n for b in buys)
    print(f"  {name:<24}{ncon:>7}{100*tot/nc:>10.2f}{100*tot/ncon:>13.2f}")
