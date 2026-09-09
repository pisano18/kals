import sys, os, json, math
sys.path.insert(0, r"C:\kals-repo\research")
os.environ["KALS_SELFTESTED"]="1"
import pinsize as ps

rows=[json.loads(l) for l in open(ps.ROWS, encoding="utf-8") if l.strip()]

def build(taumax, use_ev=True, use_fee=True, ceiling=None, pfmax=0.02):
    kept=[]
    for d in rows:
        if not (3 <= d["tau"] <= taumax): continue
        if ps.p_flip_model(d) > pfmax: continue
        if use_ev:
            e = ps.ev_per_contract(d["price"], ps.MEASURED_FLIP)
            if use_fee: e -= ps.billed_fee(d["price"],1)
            if e < ps.EV_FLOOR: continue
        if ceiling is not None and float(d["price"])>ceiling+1e-12: continue
        kept.append(d)
    kept.sort(key=lambda d:(d["close"],d["sec"],d["tk"]))
    cl={}
    for d in kept: cl.setdefault(d["close"],[]).append(d)
    return cl

def rep(cl,cap=2):
    b,_,_=ps.replay(cl,"improve",ps._one,cap,unit=1)
    return b

import itertools
for name,cl in [
  ("tau3-30 EVgate(fee)", build(30)),
  ("tau3-30 EVgate(nofee)", build(30,use_fee=False)),
  ("tau3-30 ceiling.988 noEV", build(30,use_ev=False,ceiling=0.988)),
  ("tau3-30 ceiling.988 noEV nopf", build(30,use_ev=False,ceiling=0.988,pfmax=1.0)),
  ("tau3-30 EV+ceiling.988", build(30,ceiling=0.988)),
  ("tau3-60 EVgate", build(60)),
  ("tau3-45 EVgate", build(45)),
]:
    for cap in (2,):
        b=rep(cl,cap)
        pr=[x.price for x in b]
        print(f"{name:34s} cap{cap}: closes {len(cl):4d} buys {len(b):4d} avg {100*sum(pr)/len(pr):.2f}c")
