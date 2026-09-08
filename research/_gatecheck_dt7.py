import json, math, os, sys
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
    return c
print("=== depth: TIER wants 2 units in ONE order. What does the resting level hold? ===")
for tag,(a,b) in (("tau 3-20",(3,20)),("tau 3-30 (live window)",(3,30))):
    C=gate(a,b)
    for unit in (1,5):
        for name,mode,fn,cap in (("SCALE_IMPROVE(live)","improve",P._one,2),
                                 ("TIER_IMPROVE","improve",P._price_tier,2)):
            buys,tr,sk=P.replay(C,mode,fn,cap,unit)
            print(f"  {tag:22s} unit={unit}  {name:20s} orders={len(buys):4d} contracts={sum(x.n for x in buys):5d} truncated={tr:3d} thin-level skips={sk:4d}")
    # how often is the FIRST eligible row's resting size < 2*unit ?
    for unit in (1,5):
        need=2*unit; short=0; tot=0
        for c,v in C.items():
            tot+=1
            if math.floor(v[0]["size"])<need: short+=1
        print(f"  {tag:22s} unit={unit}: first eligible row holds < {need} contracts on {short}/{tot} closes "
              f"({100.0*short/tot:.0f}%) -- pinrun's guard only requires {max(1.0,unit)}")

print("\n=== is the tau 30/31 'wall' statistically a wall? Fisher exact, CLOSES ===")
def fisher(a,b,c,d):
    n=a+b+c+d
    def C_(n,k): return math.comb(n,k)
    p0=C_(a+b,a)*C_(c+d,c)/C_(n,a+c)
    tot=0.0
    for i in range(0,min(a+b,a+c)+1):
        j=a+c-i
        if j<0 or j>c+d: continue
        p=C_(a+b,i)*C_(c+d,j)/C_(n,a+c)
        if p<=p0+1e-15: tot+=p
    return tot
print(f"  tau 21-30: 0 flip-closes / 118   vs  tau 31-45: 5 / 131   Fisher p = {fisher(0,118,5,126):.4f}")
print(f"  tau  3-30: 0 flip-closes / 118   vs  tau 46-60: 9 / 132   Fisher p = {fisher(0,118,9,123):.4f}")
