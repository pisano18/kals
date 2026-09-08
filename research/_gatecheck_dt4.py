import json, math, os, sys, random, datetime
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import pinsize as P
random.seed(20260908)

def pop(tmin,tmax,unitless=True):
    rows=[]
    for ln in open(P.ROWS,encoding="utf-8"):
        ln=ln.strip()
        if ln: rows.append(json.loads(ln))
    k=[d for d in rows if tmin<=d["tau"]<=tmax and P.p_flip_model(d)<=P.PFLIP_MAX
       and P.ev_per_contract(d["price"],P.MEASURED_FLIP)-P.billed_fee(d["price"],1)>=P.EV_FLOOR]
    k.sort(key=lambda d:(d["close"],d["sec"],d["tk"]))
    c={}
    for d in k: c.setdefault(d["close"],[]).append(d)
    return c

RULES=[("FLAT1","once",P._flat(1),1),("FLAT2","once",P._flat(2),2),
       ("PRICE_TIER cap2","once",P._price_tier,2),
       ("EV_PROP cap2","once",P._ev_prop,2),
       ("SCALE_IMPROVE cap2 LIVE","improve",P._one,2),
       ("TIER_IMPROVE cap2","improve",P._price_tier,2),
       ("EV_IMPROVE cap2","improve",P._ev_prop,2)]

for tag,(a,b),unit in (("STUDY WINDOW tau 3-20, unit 1",(3,20),1),
                       ("LIVE WINDOW tau 3-30, unit 1",(3,30),1),
                       ("LIVE WINDOW tau 3-30, unit 5 (the running config)",(3,30),5)):
    C=pop(a,b)
    print(f"\n==== {tag} : {sum(len(v) for v in C.values())} rows / {len(C)} closes ====")
    print(f"  {'rule':<24}{'contr':>7}{'Ec/cl@0.9%':>11}{'Ec/cl@2.31%':>12}{'maxExp$':>9}"
          f"{'Ec per $maxExp':>15}{'Ec per $Eloss':>14}{'badCl->abort':>13}")
    for name,mode,fn,cap in RULES:
        buys,tr,sk=P.replay(C,mode,fn,cap,unit)
        s=P.score(buys)
        ab = 3.00 if unit==1 else 21.00
        eloss = P.MEASURED_FLIP*sum(x.n*x.price for x in buys)
        e9 = s["ev0.0090_total"]; 
        per_exp = (100*s["ev0.0090_per_close"]/s["max_exposure"]) if s["max_exposure"] else 0
        per_l = (e9/eloss) if eloss>0 else 0
        print(f"  {name:<24}{s['contracts']:>7}{100*s['ev0.0090_per_close']:>11.2f}"
              f"{100*s['ev0.0231_per_close']:>12.2f}{s['max_exposure']:>9.3f}"
              f"{per_exp:>15.2f}{per_l:>14.2f}{math.ceil(ab/s['max_exposure']):>13}")

print("\n==== BOOTSTRAP: TIER_IMPROVE cap2 minus SCALE_IMPROVE cap2 (LIVE), study window ====")
C=pop(3,20)
def percl(mode,fn,cap,f):
    buys,_,_=P.replay(C,mode,fn,cap,1)
    d={}
    for x in buys: d[x.close]=d.get(x.close,0.0)+P.ev_order(x.price,x.n,f)
    return d
for f,lab in ((P.MEASURED_FLIP,"0.90%"),(P.FLIP_HI,"1.80%"),(P.FLIP_CP,"2.31%")):
    a=percl("improve",P._price_tier,2,f); b=percl("improve",P._one,2,f)
    cls=sorted(set(a)|set(b))
    diff=[a.get(c,0.0)-b.get(c,0.0) for c in cls]
    m=sum(diff)/len(diff)
    # close-level bootstrap
    B=[]
    for _ in range(4000):
        s=sum(diff[random.randrange(len(diff))] for _ in range(len(diff)))/len(diff)
        B.append(s)
    B.sort()
    # day-block bootstrap
    byd={}
    for c,dv in zip(cls,diff):
        byd.setdefault(datetime.datetime.fromtimestamp(c,datetime.UTC).strftime("%m-%d"),[]).append(dv)
    days=list(byd.values())
    D=[]
    for _ in range(4000):
        pick=[days[random.randrange(len(days))] for _ in range(len(days))]
        flat=[x for g in pick for x in g]
        D.append(sum(flat)/len(flat))
    D.sort()
    nz=sum(1 for d_ in diff if abs(d_)>1e-12)
    print(f"  @{lab}: mean diff {100*m:+.3f} c/close on {len(diff)} closes ({nz} closes differ) | "
          f"close-boot 95% [{100*B[100]:+.3f}, {100*B[3899]:+.3f}] | "
          f"DAY-boot(3 blocks) 95% [{100*D[100]:+.3f}, {100*D[3899]:+.3f}]")

print("\n==== which closes carry the TIER-LIVE difference? ====")
a=percl("improve",P._price_tier,2,P.FLIP_HI); b=percl("improve",P._one,2,P.FLIP_HI)
cls=sorted(set(a)|set(b)); diff=sorted(((a.get(c,0)-b.get(c,0)),c) for c in cls)
tot=sum(d for d,_ in diff)
top=sorted(diff,reverse=True)[:5]
print(f"  total {100*tot:.2f}c over 70 closes; top 5 closes = {100*sum(d for d,_ in top):.2f}c "
      f"({100*sum(d for d,_ in top)/tot:.0f}% of it)")
for d_,c in top: print(f"    {datetime.datetime.fromtimestamp(c,datetime.UTC):%m-%d %H:%M} {100*d_:+.2f}c")
