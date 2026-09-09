"""READ-ONLY v2: same test, with the CORRECT round_digits (4 for SOL/NEAR --
their strikes carry 4 dp in fulltape) and an explicit SIDE-agreement check
between the hard sd<=0 verdict and the verdict a properly estimated sigma gives.
SOL and NEAR are the ONLY indices whose bit-identical flat runs ever reach the
30 s that sigma() needs (census: max run ADA 15, BCH 16, BNB 13, BRTI 5,
DOGE 22, ETH 16, HYPE 10, XRP 17, ZEC 3)."""
import gzip, glob, json, math, os, sys
sys.path.insert(0, r"C:\kals-repo\research")
os.environ["KALS_SELFTESTED"] = "1"
from engine import var_factor, N_AVG
from statistics import NormalDist
ND = NormalDist()
PAIRS = [("KXSOL15M", "SOLUSD_RTI", 4), ("KXNEAR15M", "NEARUSD_RTI", 4)]
TAU_MIN, TAU_MAX, PIN, SIGMA_WIN = 3, 30, 0.98, 300
WANT = {p[1] for p in PAIRS}
T = {i: {} for i in WANT}
for f in sorted(glob.glob(r"C:\kals\kalshi_data\cfbenchmarks_value\*.jsonl.gz")):
    try:
        with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                if "USD_RTI" not in ln: continue
                try: m = (json.loads(ln).get("msg") or {})
                except Exception: continue
                iid = m.get("index_id")
                if iid not in WANT: continue
                data = m.get("data")
                try:
                    data = json.loads(data) if isinstance(data, str) else (data or {})
                    T[iid][int(data["time"]) // 1000] = float(data["value"])
                except Exception: continue
    except Exception: pass
MK = json.load(open(r"C:\kals\fulltape\markets.json"))
for series, iid, digits in PAIRS:
    d = T[iid]
    mk = [m for m in MK[series] if m.get("result") is not None
          and m.get("strike") is not None]
    def flat_run_ending(now):
        if now not in d: return 0
        v = d[now]; L = 1; s = now - 1
        while L < SIGMA_WIN and s in d and d[s] == v:
            L += 1; s -= 1
        return L
    def real_sigma(now):
        secs = [s for s in range(now - SIGMA_WIN + 1, now + 1) if s in d]
        if len(secs) < 30: return None
        diffs = [d[secs[i]] - d[secs[i-1]] for i in range(1, len(secs))
                 if secs[i] - secs[i-1] == 1]
        if len(diffs) < 20: return None
        mu = sum(diffs)/len(diffs)
        return math.sqrt(sum((x-mu)**2 for x in diffs)/(len(diffs)-1))
    cov = elig = wrong = same_side = diff_side = soft_declines = 0
    soft_wrong = 0
    worst = []
    for m in mk:
        c = int(m["close"]); Keff = float(m["strike"]) - 0.5*(10.0**-digits)
        res = float(m["result"]); lo = c - N_AVG
        if (c - TAU_MAX) not in d or (c - TAU_MIN) not in d: continue
        cov += 1
        for tau in range(TAU_MIN, TAU_MAX + 1):
            now = c - tau
            if now not in d: continue
            L = flat_run_ending(now)
            if L < 30: continue
            want = now - lo + 1
            if not any((now - max(lo, now - h + 1) + 1) >= 0.95*want
                       for h in range(30, min(L, SIGMA_WIN) + 1)):
                continue
            have = [s for s in range(lo, now + 1) if s in d]
            if len(have) < 0.95*want: continue
            locked = sum(d[s] for s in have)
            if len(have) < want: locked *= want/len(have)
            r = N_AVG - want
            mu = (locked + r*d[now]) / N_AVG
            elig += 1
            hard_side = 1.0 if mu >= Keff else 0.0
            if hard_side != res:
                wrong += 1
                worst.append((m["ticker"], tau, round(mu, 6), round(Keff, 6), res, L))
            sg = real_sigma(now)
            soft = (ND.cdf((mu - Keff)/(sg*math.sqrt(var_factor(r, [1.0]))))
                    if (sg and r > 0) else None)
            if soft is None or not (soft >= PIN or soft <= 1 - PIN):
                soft_declines += 1
            else:
                s_side = 1.0 if soft >= PIN else 0.0
                if s_side == hard_side: same_side += 1
                else: diff_side += 1
                if s_side != res: soft_wrong += 1
    print(f"\n== {series} / {iid} (round_digits {digits}) ==")
    print(f"  settled markets with index cover in tau[3,30]:      {cov}")
    print(f"  (market,tau) moments where sigma() COULD be 0.0:    {elig}")
    print(f"  hard sd<=0 verdict WRONG vs settlement:             {wrong}")
    print(f"  a real sigma agrees on the side and fires:          {same_side}")
    print(f"  a real sigma fires the OPPOSITE side:               {diff_side}")
    print(f"  a real sigma DECLINES (this is the defect's own trade set): "
          f"{soft_declines}")
    print(f"  (real-sigma fires that were wrong: {soft_wrong})")
    for w in worst[:10]:
        print(f"    WRONG {w}")
