"""Falsification: replay the SAME sizing rules on the only window that HAS flips."""
import json, math, os, sys, datetime
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import pinsize as P
from engine import var_factor

rows=[]
for ln in open(P.ROWS,encoding="utf-8"):
    ln=ln.strip()
    if ln: rows.append(json.loads(ln))
for d in rows:
    d["pm"]=P.p_flip_model(d)

def pop(tmin,tmax):
    k=[d for d in rows if tmin<=d["tau"]<=tmax and d["pm"]<=P.PFLIP_MAX
       and P.ev_per_contract(d["price"],P.MEASURED_FLIP)-P.billed_fee(d["price"],1)>=P.EV_FLOOR]
    k.sort(key=lambda d:(d["close"],d["sec"],d["tk"]))
    c={}
    for d in k: c.setdefault(d["close"],[]).append(d)
    return c

RULES=[("FLAT1","once",P._flat(1),1),("FLAT2","once",P._flat(2),2),
       ("PRICE_TIER cap2","once",P._price_tier,2),
       ("CONF_PROP cap2","once",P._conf_prop,2),
       ("EV_PROP cap2","once",P._ev_prop,2),
       ("SCALE_IMPROVE cap2 LIVE","improve",P._one,2),
       ("TIER_IMPROVE cap2","improve",P._price_tier,2),
       ("EV_IMPROVE cap2","improve",P._ev_prop,2),
       ("TIER_IMPROVE cap4","improve",P._price_tier,4)]

for tag,(tmin,tmax) in (("tau 31-60 (the ONLY window with flips)",(31,60)),
                        ("tau 46-60",(46,60)),
                        ("tau 3-60 (all)",(3,60))):
    C=pop(tmin,tmax)
    nfl=sum(1 for v in C.values() for d in v if d["flip"])
    print(f"\n==== {tag}: {sum(len(v) for v in C.values())} rows, {len(C)} closes, {nfl} flipped rows ====")
    print(f"  {'rule':<24}{'contr':>6}{'avgpx':>8}{'REALISED c/close':>18}{'c/contr':>9}{'worst close $':>14}{'flipped contr':>14}{'negCloses':>10}")
    for name,mode,fn,cap in RULES:
        buys,tr,sk=P.replay(C,mode,fn,cap,1)
        s=P.score(buys)
        fcon=sum(b.n for b in buys if b.flip)
        print(f"  {name:<24}{s['contracts']:>6}{s['avg_price']:>8.4f}{100*s['real_per_close']:>18.2f}"
              f"{100*s['real_per_contract']:>9.2f}{s['real_worst']:>14.2f}{fcon:>14}{s['losing_closes']:>10}")

print("\n==== ADVERSE SELECTION: inside a FLIP close, are the CHEAP rows the flipped ones? ====")
C=pop(31,60)
tot=[0,0]; cheap=[0,0]
import statistics
for c,v in C.items():
    if not any(d["flip"] for d in v): continue
    v2=sorted(v,key=lambda d:d["price"])
    h=len(v2)//2
    lo=v2[:h]; hi=v2[h:]
    cheap[0]+=sum(1 for d in lo if d["flip"]); cheap[1]+=len(lo)
    tot[0]+=sum(1 for d in hi if d["flip"]); tot[1]+=len(hi)
print(f"  within flip-closes: cheaper half {cheap[0]}/{cheap[1]} = {100.0*cheap[0]/cheap[1]:.1f}% flipped; "
      f"dearer half {tot[0]}/{tot[1]} = {100.0*tot[0]/tot[1]:.1f}%")

print("\n==== FIRST-row vs CHEAPEST-row flip rate per close (what 'improve' actually buys) ====")
for tmin,tmax in ((31,60),(3,60)):
    C=pop(tmin,tmax); a=b=n=0
    for c,v in C.items():
        n+=1
        a += 1 if v[0]["flip"] else 0
        b += 1 if min(v,key=lambda d:d["price"])["flip"] else 0
    print(f"  tau {tmin}-{tmax}: {n} closes | first-available row flips {a} ({100.0*a/n:.2f}%) | "
          f"cheapest row flips {b} ({100.0*b/n:.2f}%)")
