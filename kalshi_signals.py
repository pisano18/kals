#!/usr/bin/env python3
# VERSION: 2026-08-25-v1
"""
kalshi_signals.py  --  Mine the fields I threw away.

    python kalshi_signals.py --out ./fulltape

The calibration test asked one narrow question: "at price P, does the market
settle P% of the time?" Answer: yes, it's efficient. But that used only price
and outcome. Each trade also carries:

    taker_side        who was AGGRESSIVE (crossed the spread)
    count_fp          how BIG the trade was
    is_block_trade    whether it was a block
    created_time      the full price PATH through the window

An efficient AVERAGE price is completely compatible with a large exploitable
edge hiding in flow. Vegas lines are efficient on average while sharp money
still wins. That is the gap this script attacks.

EIGHT HYPOTHESES

 H1 AGGRESSOR    Do spread-crossers win or lose? If aggressive flow is
                 systematically wrong, fade it.
 H2 SIZE         Are big takers smarter than small ones? ("copy the winners")
 H3 BLOCK        Do block trades predict?
 H4 FLOW         Does taker imbalance predict the outcome BEYOND the price?
                 This is the real test: signal orthogonal to price is tradeable.
 H5 OPEN         Strike = opening TWAP, so the true value at open is EXACTLY
                 50c. If early prices are systematically off 50, that is a
                 structural, mechanical edge with no forecasting required.
 H6 REVERSION    After a sharp contract-price jump, does it continue or revert?
 H7 HOUR         Is the market worse overnight when retail dominates and desks
                 are thin?
 H8 ROUND        Do prices cluster at round numbers, and is clustering
                 associated with mispricing?

Every test clusters by MARKET (hundreds of trades share one outcome) and
reports the number of markets, not trades. That was the bug that produced
fake 21c edges earlier.
"""

import argparse, json, math, os
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, pstdev, median

def parse_ts(s):
    if isinstance(s,(int,float)): return float(s if s<1e12 else s/1000.0)
    try: return datetime.fromisoformat(str(s).replace("Z","+00:00")).timestamp()
    except ValueError: return None

def clustered(pairs, label, min_n=40):
    """pairs = [(edge, market_ticker)]; one observation per market."""
    by = defaultdict(list)
    for e,tk in pairs: by[tk].append(e)
    obs = [mean(v) for v in by.values()]
    n = len(obs)
    if n < min_n: return None
    m = mean(obs); sd = pstdev(obs)
    se = sd/math.sqrt(n) if sd>0 else float("inf")
    return {"label":label,"n":n,"edge":m,"t":m/se if se>0 else 0.0,
            "trades":sum(len(v) for v in by.values())}

def show(rows, note=""):
    print(f"  {'group':>26}{'markets':>9}{'trades':>10}{'edge':>9}{'t':>8}   verdict")
    for r in rows:
        if not r: continue
        v = ("SIGNAL" if abs(r['t'])>3 and abs(r['edge'])>0.01 else
             "weak"   if abs(r['t'])>2 else "nothing")
        print(f"  {r['label']:>26}{r['n']:>9}{r['trades']:>10,}"
              f"{100*r['edge']:>+8.2f}c{r['t']:>8.1f}   {v}")
    if note: print(note)

def load(out):
    markets = json.load(open(os.path.join(out,"markets.json")))
    tapes   = json.load(open(os.path.join(out,"tapes.json")))
    idx = {}
    for s,ms in markets.items():
        for m in ms: idx[m["ticker"]] = m
    rows = []
    for s,ts in tapes.items():
        for t in ts:
            tk = t.get("ticker") or t.get("market_ticker")
            m = idx.get(tk)
            if not m: continue
            try:
                p = float(t.get("yes_price_dollars") or t.get("yes_price"))
                if p>1.5: p/=100.0
                tt = parse_ts(t.get("created_time"))
                sz = float(t.get("count_fp") or t.get("count") or 1)
            except (TypeError,ValueError): continue
            if tt is None or not (0<p<1): continue
            ttc = m["close"]-tt
            if not (0<=ttc<=900): continue
            rows.append({"tk":tk,"p":p,"ttc":ttc,"sz":sz,
                         "side":str(t.get("taker_side","")).lower(),
                         "blk":bool(t.get("is_block_trade")),
                         "res":m["result"],"close":m["close"]})
    return idx, rows

def taker_edge(r):
    """Profit to the AGGRESSOR, per contract. Positive => takers win."""
    return (r["res"]-r["p"]) if r["side"]=="yes" else (r["p"]-r["res"])

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",default="./fulltape")
    a=ap.parse_args()
    idx, rows = load(a.out)
    print(f"loaded {len(rows):,} trades across {len(set(r['tk'] for r in rows)):,} markets")
    sided=[r for r in rows if r["side"] in ("yes","no")]
    print(f"  with taker_side: {len(sided):,}")

    print("\n"+"="*78); print("H1  AGGRESSOR -- do spread-crossers win?"); print("="*78)
    show([clustered([(taker_edge(r),r["tk"]) for r in sided],"all takers"),
          clustered([(taker_edge(r),r["tk"]) for r in sided if r["side"]=="yes"],"yes-aggressors"),
          clustered([(taker_edge(r),r["tk"]) for r in sided if r["side"]=="no"],"no-aggressors")],
         "\n  Negative = takers lose. Some loss is the spread they pay and is NOT\n"
         "  capturable (we would have to be the resting maker, and the queue is\n"
         "  ~3,767 deep). Only a LARGE, side-asymmetric loss is actionable.")

    if sided:
        szs=sorted(r["sz"] for r in sided)
        q=[szs[int(len(szs)*f)] for f in (0.25,0.5,0.75,0.95)]
        print("\n"+"="*78); print("H2  SIZE -- are big takers informed?"); print("="*78)
        print(f"  size quartiles: {q[0]:.1f} / {q[1]:.1f} / {q[2]:.1f}  p95={q[3]:.1f}")
        show([clustered([(taker_edge(r),r["tk"]) for r in sided if r["sz"]<=q[0]],"smallest 25%"),
              clustered([(taker_edge(r),r["tk"]) for r in sided if q[0]<r["sz"]<=q[1]],"25-50%"),
              clustered([(taker_edge(r),r["tk"]) for r in sided if q[1]<r["sz"]<=q[2]],"50-75%"),
              clustered([(taker_edge(r),r["tk"]) for r in sided if q[2]<r["sz"]<=q[3]],"75-95%"),
              clustered([(taker_edge(r),r["tk"]) for r in sided if r["sz"]>q[3]],"largest 5%")],
             "\n  A monotone rise here = size carries information. That is the\n"
             "  measurable version of 'follow the good bettors'.")

        blk=[r for r in sided if r["blk"]]
        if len(blk)>200:
            print("\n"+"="*78); print("H3  BLOCK TRADES"); print("="*78)
            show([clustered([(taker_edge(r),r["tk"]) for r in blk],"block"),
                  clustered([(taker_edge(r),r["tk"]) for r in sided if not r["blk"]],"non-block")])

    print("\n"+"="*78)
    print("H4  FLOW IMBALANCE -- signal ORTHOGONAL to price  [the real test]")
    print("="*78)
    print("  Within each price bucket, split markets by taker imbalance. If the")
    print("  market is efficient, outcome depends ONLY on price. If high-imbalance")
    print("  markets settle differently AT THE SAME PRICE, flow carries alpha.")
    cells=defaultdict(lambda: defaultdict(lambda: [0.0,0.0,0.0]))
    for r in sided:
        tb = "0-180s" if r["ttc"]<=180 else "180-480s" if r["ttc"]<=480 else "480-900s"
        pb = round(min(max(r["p"],.05),.95)*10)/10.0
        c = cells[(tb,pb)][r["tk"]]
        c[0]+= r["sz"] if r["side"]=="yes" else -r["sz"]
        c[1]+= r["sz"]; c[2]=r["res"]
    print(f"  {'bucket':>12}{'price':>7}{'mkts':>7}{'lowflow out':>13}"
          f"{'highflow out':>14}{'gap':>8}{'t':>7}   verdict")
    found=0
    for key in sorted(cells):
        per=cells[key]
        if len(per)<60: continue
        arr=sorted(((v[0]/v[1] if v[1] else 0.0), v[2]) for v in per.values())
        k=len(arr)//3
        lo=[o for _,o in arr[:k]]; hi=[o for _,o in arr[-k:]]
        if len(lo)<20: continue
        gap=mean(hi)-mean(lo)
        se=math.sqrt(max(mean(hi)*(1-mean(hi)),1e-6)/len(hi)
                     +max(mean(lo)*(1-mean(lo)),1e-6)/len(lo))
        t=gap/se if se>0 else 0
        v="SIGNAL" if abs(t)>3 else "weak" if abs(t)>2 else "nothing"
        if abs(t)>3: found+=1
        print(f"  {key[0]:>12}{key[1]:>7.1f}{len(per):>7}{mean(lo):>13.3f}"
              f"{mean(hi):>14.3f}{gap:>+8.3f}{t:>7.1f}   {v}")
    print(f"\n  {found} cells with |t|>3. Flow predicting outcome at fixed price")
    print("  is the single most tradeable thing this script can find.")

    print("\n"+"="*78)
    print("H5  OPENING PRICE -- structural, no forecasting needed")
    print("="*78)
    print("  The strike IS the opening 60s TWAP, so fair value at open is exactly")
    print("  50c. Any systematic deviation is mechanical free money.")
    first={}
    for r in rows:
        if r["ttc"]>=870:
            if r["tk"] not in first or r["ttc"]>first[r["tk"]]["ttc"]: first[r["tk"]]=r
    if len(first)>=40:
        dev=[(f["p"]-0.5) for f in first.values()]
        outc=[(f["res"]-f["p"]) for f in first.values()]
        n=len(dev)
        print(f"  markets with a trade in the first 30s: {n}")
        print(f"  mean opening price      {0.5+mean(dev):.4f}   (fair = 0.5000)")
        print(f"  deviation from 50c      {100*mean(dev):+.2f}c  "
              f"t={mean(dev)/(pstdev(dev)/math.sqrt(n)):+.1f}")
        print(f"  edge to buying at open  {100*mean(outc):+.2f}c  "
              f"t={mean(outc)/(pstdev(outc)/math.sqrt(n)):+.1f}")
    else:
        print("  too few early trades captured")

    print("\n"+"="*78); print("H6  REVERSION after sharp contract-price moves"); print("="*78)
    bytk=defaultdict(list)
    for r in rows: bytk[r["tk"]].append(r)
    jump=[]
    for tk,rs in bytk.items():
        rs.sort(key=lambda x:-x["ttc"])
        for i in range(20,len(rs)):
            d=rs[i]["p"]-rs[i-20]["p"]
            if abs(d)>0.10 and rs[i]["ttc"]>120:
                jump.append(((rs[i]["res"]-rs[i]["p"])*(1 if d>0 else -1),tk))
    r6=clustered(jump,"after >10c jump")
    if r6:
        show([r6],"\n  Positive = the jump UNDER-shot (momentum). Negative = the book\n"
                  "  OVERREACTED and reverts, so fade sharp moves.")
    else:
        print("  too few jump events")

    print("\n"+"="*78); print("H7  HOUR OF DAY -- is it worse when desks are thin?"); print("="*78)
    hh=defaultdict(list)
    for r in sided:
        h=datetime.fromtimestamp(r["close"],timezone.utc).hour
        blk3=(h//3)*3
        hh[blk3].append((taker_edge(r),r["tk"]))
    show([clustered(v,f"UTC {k:02d}-{k+3:02d}") for k,v in sorted(hh.items())],
         "\n  US overnight (UTC 04-12) is when retail dominates. A different\n"
         "  answer there than in UTC 13-21 would be a real, exploitable regime.")

    print("\n"+"="*78); print("H8  ROUND-NUMBER CLUSTERING"); print("="*78)
    cnt=defaultdict(int)
    for r in rows: cnt[round(r["p"]*100)]+=1
    tot=sum(cnt.values())
    print(f"  {'price':>7}{'share':>9}   (uniform-ish would be flat)")
    for c in [10,25,33,50,66,75,90,95,99]:
        print(f"  {c:>6}c{100*cnt.get(c,0)/tot:>8.2f}%")
    print("\n  Heavy clustering at 50/75/90 suggests humans placing round-number")
    print("  orders. Those are the orders most likely to be lazily priced.")

if __name__=="__main__":
    main()
