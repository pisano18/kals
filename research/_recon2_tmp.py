import gzip, json, math, statistics as st
HRS = ["20260907T10","20260907T11","20260907T12","20260907T13"]
def load_index(hrs, want):
    out = {k: {} for k in want}
    for h in hrs:
        try:
            with gzip.open(f"C:/kals/kalshi_data/cfbenchmarks_value/{h}.jsonl.gz","rt") as f:
                for l in f:
                    try: o=json.loads(l)
                    except Exception: continue
                    m=o.get("msg") or {}; iid=m.get("index_id")
                    if iid not in want: continue
                    try: d=json.loads(m["data"])
                    except Exception: continue
                    out[iid][d["time"]//1000]=float(d["value"])
        except (EOFError,OSError,__import__("zlib").error): pass
    return out
def load_rep(hrs, assets):
    per={a:{} for a in assets}
    for h in hrs:
        try:
            with gzip.open(f"C:/kals/feed_data/index_replica/{h}.jsonl.gz","rt") as f:
                for l in f:
                    try: o=json.loads(l)
                    except Exception: continue
                    s=o.get("sec")
                    for a in assets:
                        d=o.get(a)
                        if isinstance(d,dict):
                            per[a][s]={k:((v["b"]+v["a"])/2.0, v["a"]-v["b"]) for k,v in (d.get("per_ex") or {}).items()}
        except (EOFError,OSError,__import__("zlib").error): pass
    return per
def corr(x,y):
    n=len(x)
    if n<3: return float("nan")
    mx,my=sum(x)/n,sum(y)/n
    sxy=sum((a-mx)*(b-my) for a,b in zip(x,y)); sxx=sum((a-mx)**2 for a in x); syy=sum((b-my)**2 for b in y)
    return sxy/math.sqrt(sxx*syy) if sxx>0 and syy>0 else float("nan")

I=load_index(HRS,{"BRTI","ETHUSD_RTI"}); PE=load_rep(HRS,["BTC","ETH"])
for iid,a in (("BRTI","BTC"),("ETHUSD_RTI","ETH")):
    idx=I[iid]; pe=PE[a]
    secs=sorted(set(idx)&set(pe))
    exs=sorted({e for s in secs[:2000] for e in pe[s]})
    print(f"\n===== {iid}/{a}  n={len(secs)}  exchanges seen: {exs}")
    # per exchange update frequency: fraction of seconds where mid changed
    for e in exs:
        ch=sum(1 for i in range(1,len(secs)) if e in pe[secs[i]] and e in pe[secs[i-1]] and pe[secs[i]][e][0]!=pe[secs[i-1]][e][0])
        cov=sum(1 for s in secs if e in pe[s])
        sp=[pe[s][e][1] for s in secs if e in pe[s]]
        print(f"   {e:9s} coverage {cov/len(secs)*100:5.1f}%  mid changed on {ch/len(secs)*100:5.1f}% of seconds  median spread {st.median(sp):.4f}")
    print("   lag corr( dI(t), dMid_e(t+k) ):  k<0 = exchange LEADS index")
    for e in exs:
        row=[]
        for k in (-2,-1,0,1,2):
            xs=[];ys=[]
            for i in range(1,len(secs)):
                s=secs[i]; sp=secs[i-1]
                if sp!=s-1: continue
                t2=s+k
                if t2 not in pe or (t2-1) not in pe: continue
                if e not in pe[t2] or e not in pe[t2-1]: continue
                if s not in idx or s-1 not in idx: continue
                xs.append(idx[s]-idx[s-1]); ys.append(pe[t2][e][0]-pe[t2-1][e][0])
            row.append(f"k={k:+d}:{corr(xs,ys):+.3f}(n={len(xs)})")
        print(f"   {e:9s} " + "  ".join(row))
