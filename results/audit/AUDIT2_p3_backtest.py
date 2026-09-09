"""READ-ONLY: what would the sd<=0 branch actually have DONE on real SOL tape?

SOLUSD_RTI is quantised to 0.01, so it sits bit-identical for tens of seconds
(census: 1,174 runs >= 30 s in 349 h).  A pinrun process whose whole tick
history lies inside such a run gets sigma() == 0.0 and fair() then returns a
hard 1.0/0.0.  This finds every (market, tau) moment where that is possible,
and scores the hard verdict against the ACTUAL settlement -- and against what
the same model would have said with a properly estimated sigma.
"""
import gzip, glob, json, math, os, sys
from collections import defaultdict
sys.path.insert(0, r"C:\kals-repo\research")
os.environ["KALS_SELFTESTED"] = "1"
from engine import var_factor, N_AVG
from statistics import NormalDist
ND = NormalDist()
SERIES = "KXSOL15M"; IID = "SOLUSD_RTI"; DIGITS = 2
TAU_MIN, TAU_MAX, PIN, SIGMA_WIN = 3, 30, 0.98, 300

d = {}
for f in sorted(glob.glob(r"C:\kals\kalshi_data\cfbenchmarks_value\*.jsonl.gz")):
    try:
        with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                if IID not in ln: continue
                try: m = (json.loads(ln).get("msg") or {})
                except Exception: continue
                if m.get("index_id") != IID: continue
                data = m.get("data")
                try:
                    data = json.loads(data) if isinstance(data, str) else (data or {})
                    d[int(data["time"]) // 1000] = float(data["value"])
                except Exception: continue
    except Exception: pass
print(f"{IID}: {len(d)} index-seconds")

mk = [m for m in json.load(open(r"C:\kals\fulltape\markets.json"))[SERIES]
      if m.get("result") is not None and m.get("strike") is not None]
print(f"{SERIES}: {len(mk)} settled markets in fulltape")

def flat_run_ending(now, cap=SIGMA_WIN):
    """length of the bit-identical consecutive-second run ending at `now`."""
    if now not in d: return 0
    v = d[now]; L = 1
    s = now - 1
    while L < cap and s in d and d[s] == v:
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

covered = eligible = 0
hard_fires = 0; hard_wrong = 0
also_fires_real = 0; only_hard = 0; only_hard_wrong = 0
by_price = []
for m in mk:
    c = int(m["close"]); K0 = float(m["strike"]); res = float(m["result"])
    Keff = K0 - 0.5 * (10.0 ** -DIGITS)
    lo = c - N_AVG
    if (c - TAU_MAX) not in d or (c - TAU_MIN) not in d: continue
    covered += 1
    for tau in range(TAU_MIN, TAU_MAX + 1):
        now = c - tau
        if now not in d: continue
        L = flat_run_ending(now)
        if L < 30: continue                # sigma() cannot be 0.0
        # a feasible process history h in [30, min(L,300)] with partial()
        # coverage >= 95% of [c-60, now]
        want = now - lo + 1
        ok = False
        for h in range(30, min(L, SIGMA_WIN) + 1):
            T = now - h + 1
            got = now - max(lo, T) + 1
            if got >= 0.95 * want:
                ok = True; break
        if not ok: continue
        eligible += 1
        have = [s for s in range(lo, now + 1) if s in d]
        if len(have) < 0.95 * want: continue
        locked = sum(d[s] for s in have)
        # fill interior gaps from the nearest held print (pinrun does this)
        if len(have) < want:
            locked = locked * (want / len(have))
        r = N_AVG - want
        spot = d[now]
        mu = (locked + r * spot) / N_AVG
        hard = 1.0 if mu >= Keff else 0.0
        sg = real_sigma(now)
        soft = None
        if sg is not None and sg > 0 and r > 0:
            soft = ND.cdf((mu - Keff) / (sg * math.sqrt(var_factor(r, [1.0]))))
        fires_hard = (hard >= PIN) or (hard <= 1 - PIN)
        want_side = 1.0 if hard >= PIN else 0.0
        if fires_hard:
            hard_fires += 1
            if want_side != res:
                hard_wrong += 1
            fires_soft = soft is not None and (soft >= PIN or soft <= 1 - PIN)
            if fires_soft:
                also_fires_real += 1
            else:
                only_hard += 1
                if want_side != res:
                    only_hard_wrong += 1
            by_price.append((soft, want_side, res))

print(f"\nmarkets with index cover in tau [{TAU_MIN},{TAU_MAX}]: {covered}")
print(f"(market,tau) moments where sigma() COULD be 0.0:          {eligible}")
print(f"  of those, the hard branch fires (pin {PIN}):            {hard_fires}")
print(f"  hard-branch verdict wrong vs settlement:                {hard_wrong}"
      f"  ({100*hard_wrong/max(1,hard_fires):.2f}%)")
print(f"  a PROPERLY estimated sigma would fire too:              {also_fires_real}")
print(f"  fires ONLY because sigma was 0 (the defect's own trades):{only_hard}")
print(f"    of which wrong vs settlement:                         {only_hard_wrong}")
if by_price:
    ss = [b[0] for b in by_price if b[0] is not None]
    if ss:
        ss.sort()
        print(f"  real-sigma fair at those moments: min {ss[0]:.4f} "
              f"median {ss[len(ss)//2]:.4f} max {ss[-1]:.4f}")
