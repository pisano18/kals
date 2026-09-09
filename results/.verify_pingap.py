import sys, os, json, math, random, statistics
sys.path.insert(0, r"C:\kals-repo\research")
os.environ["KALS_SELFTESTED"]="1"
import pinsize as ps

def run(taumax, ceiling=None):
    ps.TAU_MAX = taumax
    closes, kept = ps.eligible(verbose=False)
    if ceiling is not None:
        closes = {c:[r for r in v if float(r["price"])<=ceiling+1e-12] for c,v in closes.items()}
        closes = {c:v for c,v in closes.items() if v}
    buys,_,_ = ps.replay(closes, "improve", ps._one, 2, unit=1)
    return closes, kept, buys

for tm in (30,20):
    closes, kept, buys = run(tm)
    moments = sum(len(v) for v in closes.values())
    blended = [b.price for b in buys]
    firsts = {}
    for b in buys:
        if b.close not in firsts: firsts[b.close]=b.price
    fb = list(firsts.values())
    print(f"tau 3-{tm}: moments {moments}  closes {len(closes)}  buys {len(buys)}  "
          f"blended {100*sum(blended)/len(blended):.2f}c  FIRST {100*sum(fb)/len(fb):.2f}c  nfirst {len(fb)}")
    print(f"   blended >96c: {sum(1 for p in blended if p>0.96)} of {len(blended)} = {100*sum(1 for p in blended if p>0.96)/len(blended):.1f}%")
    print(f"   first   >96c: {sum(1 for p in fb if p>0.96)} of {len(fb)} = {100*sum(1 for p in fb if p>0.96)/len(fb):.1f}%")
    print(f"   first-buy sd {100*statistics.pstdev(fb):.3f}c  min {100*min(fb):.2f} max {100*max(fb):.2f}")
    # 96c-ceiling re-replay: closes surviving
    c2,_,b2 = run(tm, ceiling=0.96)
    print(f"   with a 96c ceiling re-replayed: closes {len(c2)} buys {len(b2)} avg {100*sum(x.price for x in b2)/len(b2):.2f}c")
    ps.TAU_MAX = tm
