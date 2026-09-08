import gzip, json, math, sys, statistics as st

HRS = ["20260907T10","20260907T11","20260907T12","20260907T13"]
IDX = {"BRTI":"BTC", "ETHUSD_RTI":"ETH"}

def load_index(hrs):
    out = {k: {} for k in IDX}
    for h in hrs:
        p = f"C:/kals/kalshi_data/cfbenchmarks_value/{h}.jsonl.gz"
        try:
            with gzip.open(p, "rt") as f:
                for l in f:
                    try: o = json.loads(l)
                    except Exception: continue
                    m = o.get("msg") or {}
                    iid = m.get("index_id")
                    if iid not in IDX: continue
                    try: d = json.loads(m["data"])
                    except Exception: continue
                    out[iid][d["time"]//1000] = float(d["value"])
        except (EOFError, OSError) as e:
            print("skip", h, type(e).__name__)
    return out

def load_rep(hrs, assets):
    out = {a: {} for a in assets}
    perex = {a: {} for a in assets}
    for h in hrs:
        p = f"C:/kals/feed_data/index_replica/{h}.jsonl.gz"
        try:
            with gzip.open(p, "rt") as f:
                for l in f:
                    try: o = json.loads(l)
                    except Exception: continue
                    s = o.get("sec")
                    for a in assets:
                        d = o.get(a)
                        if isinstance(d, dict):
                            out[a][s] = d.get("wmid")
                            perex[a][s] = {k: (v["b"]+v["a"])/2.0 for k, v in (d.get("per_ex") or {}).items()}
        except (EOFError, OSError) as e:
            print("skip rep", h, type(e).__name__)
    return out, perex

def corr(x, y):
    n = len(x)
    if n < 3: return float("nan")
    mx, my = sum(x)/n, sum(y)/n
    sxy = sum((a-mx)*(b-my) for a, b in zip(x, y))
    sxx = sum((a-mx)**2 for a in x); syy = sum((b-my)**2 for b in y)
    if sxx <= 0 or syy <= 0: return float("nan")
    return sxy/math.sqrt(sxx*syy)

I = load_index(HRS)
R, PE = load_rep(HRS, ["BTC","ETH"])
for iid, a in IDX.items():
    idx, rep = I[iid], R[a]
    secs = sorted(set(idx) & set(rep))
    print(f"\n=== {iid} / {a}   aligned seconds n={len(secs)}")
    # contiguity
    run = [s for s in secs]
    dI = {}; dC = {}
    for s in secs:
        if s-1 in idx: dI[s] = idx[s]-idx[s-1]
        if s-1 in rep and rep[s] and rep[s-1]: dC[s] = rep[s]-rep[s-1]
    common = sorted(set(dI) & set(dC))
    print(f"  first-diff pairs n={len(common)}   sd(dI)={st.pstdev([dI[s] for s in common]):.4f}  sd(dC)={st.pstdev([dC[s] for s in common]):.4f}")
    print("  lag k: corr( dI(t) , dC(t+k) )   [k<0 => replica LEADS index]")
    for k in range(-4, 5):
        xs = [dI[s] for s in common if s+k in dC]
        ys = [dC[s+k] for s in common if s+k in dC]
        print(f"    k={k:+d}  n={len(xs):5d}  corr={corr(xs,ys):+.4f}")
    # basis
    bas = [rep[s]-idx[s] for s in secs]
    print(f"  basis replica-index: mean={st.mean(bas):+.3f} sd={st.pstdev(bas):.3f}")
