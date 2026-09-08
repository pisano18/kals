"""Independent re-run of the DECISIVE settlement test, plus the economic
translation the studies never made: how many CENTS does the fair value move,
and is the resulting probability better against ACTUAL settled outcomes?

Read-only.  Uses the production fair-value model from research/engine.py
(var_factor / N_AVG) so the cents are the ones pin would actually quote."""
import os, sys, math, json, array, random
from statistics import NormalDist
sys.path.insert(0, r"C:\kals-repo\research")
from engine import var_factor, N_AVG          # repo module, imported FIRST

ND = NormalDist()
NAN = float("nan")
CACHE = r"C:\Users\Joe\AppData\Local\Temp\verify_btc_cache.bin"

with open(CACHE, "rb") as f:
    t0 = int.from_bytes(f.read(8), "little")
    n = int.from_bytes(f.read(8), "little")
    idx = array.array("d"); idx.fromfile(f, n)
    rep = array.array("d"); rep.fromfile(f, n)
    cbm = array.array("d"); cbm.fromfile(f, n)
print("span %d s from %d" % (n, t0))

W = 300


def causal_offset(a, b, w=W, minp=60):
    out = array.array("d", [NAN]) * n
    s = 0.0; c = 0; ring = []; head = 0
    for t in range(n):
        if c >= minp:
            out[t] = s / c
        x, y = a[t], b[t]
        if x == x and y == y:
            ring.append((t, y - x)); s += y - x; c += 1
        while head < len(ring) and ring[head][0] <= t - w:
            s -= ring[head][1]; c -= 1; head += 1
        if head > 8192:
            del ring[:head]; head = 0
    return out


def causal_mean(a, w=W, minp=60):
    out = array.array("d", [NAN]) * n
    s = 0.0; c = 0; ring = []; head = 0
    for t in range(n):
        if c >= minp:
            out[t] = s / c
        v = a[t]
        if v == v:
            ring.append((t, v)); s += v; c += 1
        while head < len(ring) and ring[head][0] <= t - w:
            s -= ring[head][1]; c -= 1; head += 1
        if head > 8192:
            del ring[:head]; head = 0
    return out


def causal_sigma(a, w=W, minp=60):
    out = array.array("d", [NAN]) * n
    s1 = s2 = 0.0; c = 0; ring = []; head = 0
    for t in range(n):
        if c >= minp:
            m = s1 / c; v = s2 / c - m * m
            out[t] = math.sqrt(v) if v > 0 else NAN
        x = a[t]; y = a[t - 1] if t else NAN
        if x == x and y == y:
            d = x - y; ring.append((t, d)); s1 += d; s2 += d * d; c += 1
        while head < len(ring) and ring[head][0] <= t - w:
            d = ring[head][1]; s1 -= d; s2 -= d * d; c -= 1; head += 1
        if head > 8192:
            del ring[:head]; head = 0
    return out


print("building causal ebar/mean/sigma ...", flush=True)
ebar_w = causal_offset(idx, rep)
ebar_c = causal_offset(idx, cbm)
imean = causal_mean(idx)
sig = causal_sigma(idx)

# ---------------- settlement convention check ----------------
mk = json.load(open(r"C:\kals\fulltape\markets.json"))
rows = mk["KXBTC15M"]
closes = []
errs_a, errs_b = [], []
for r_ in rows:
    c = int(r_["close"]); i = c - t0
    if not (60 <= i < n):
        continue
    v = [idx[i - k] for k in range(1, 61)]
    if any(x != x for x in v):
        continue
    closes.append((c, float(r_["strike"]), float(r_["result"])))
    s = r_.get("settle")
    if s:
        errs_a.append(abs(sum(v) / 60.0 - float(s)))
        v2 = [idx[i - k] for k in range(0, 60)]
        if not any(x != x for x in v2):
            errs_b.append(abs(sum(v2) / 60.0 - float(s)))
errs_a.sort(); errs_b.sort()
print("")
print("SETTLEMENT CONVENTION, n=%d markets with a published settle" % len(errs_a))
print("  mean(index[c-60..c-1]) vs settle : median $%.4f  p95 $%.4f"
      % (errs_a[len(errs_a) // 2], errs_a[int(len(errs_a) * .95)]))
print("  mean(index[c-59..c])  (1s shift) : median $%.4f"
      % errs_b[len(errs_b) // 2])
print("usable closes with a full 60-print window: %d" % len(closes))


def olsk(X, y):
    k = len(X[0]); m = k + 1
    A = [[0.0] * (m + 1) for _ in range(m)]
    for row, yy in zip(X, y):
        v = [1.0] + list(row)
        for a in range(m):
            for b in range(m):
                A[a][b] += v[a] * v[b]
            A[a][m] += v[a] * yy
    for i in range(m):
        p = max(range(i, m), key=lambda q: abs(A[q][i]))
        if abs(A[p][i]) < 1e-12:
            return [sum(y) / len(y)] + [0.0] * k
        A[i], A[p] = A[p], A[i]
        pv = A[i][i]
        for j in range(i, m + 1):
            A[i][j] /= pv
        for q in range(m):
            if q == i:
                continue
            f = A[q][i]
            if f:
                for j in range(i, m + 1):
                    A[q][j] -= f * A[i][j]
    return [A[i][m] for i in range(m)]


def ap(c, row):
    v = c[0]
    for cc, x in zip(c[1:], row):
        v += cc * x
    return v


def tstat(d):
    m = sum(d) / len(d)
    v = sum((x - m) ** 2 for x in d) / max(len(d) - 1, 1)
    return m / math.sqrt(v / len(d)) if v > 0 else 0.0


R_VALUES = list(range(2, 20))
TRAIN = 0.60
closes.sort()
split = closes[int(len(closes) * TRAIN)][0]


def run(repsrc, ebar, rep_lead, label, mode="basis", seed=None):
    print("")
    print("--- %s  (rep_lead=%d, mode=%s%s) ---"
          % (label, rep_lead, mode, (", PERMUTED seed=%d" % seed) if seed is not None else ""))
    print("    r  n_te  RMSEmod  RMSEctl  RMSEfit  fit-ctl%   b_rep  t_vs_ctl"
          "  MAEimp%   |dp|med    |dp|p95   |dp|max    dBrier    dLogL")
    agg = {}
    for r in R_VALUES:
        trX, te = [], []
        for (c, K, res) in closes:
            t = c - 1 - r; tr = t + rep_lead
            i = t - t0; itr = tr - t0
            if i < W + 5 or itr < 0 or itr >= n or c - t0 >= n:
                continue
            ix = idx[i]
            if ix != ix:
                continue
            d1 = ix - idx[i - 1]; d2 = idx[i - 1] - idx[i - 2]
            m1 = imean[i] - ix
            rp = repsrc[itr]; eb = ebar[itr]; sg = sig[i]
            lock = [idx[c - t0 - k] for k in range(r + 1, 61)]
            unk = [idx[c - t0 - k] for k in range(1, r + 1)]
            if any(x != x for x in lock + unk):
                continue
            if not (rp == rp and eb == eb and sg == sg and sg > 0
                    and d1 == d1 and d2 == d2 and m1 == m1):
                continue
            if mode == "basis":
                bs = ((rp - eb) - ix) / sg
            else:
                rp0 = repsrc[i]
                if rp0 != rp0:
                    continue
                bs = (rp - rp0) / sg
            true = sum(unk) / r
            y = (true - ix) / sg
            row = (bs, d1 / sg, d2 / sg, m1 / sg)
            rec = (row, y, c, K, res, sum(lock), ix, sg)
            (trX if c < split else te).append(rec)
        if len(trX) < 30 or len(te) < 30:
            continue
        if seed is not None:
            rnd = random.Random(seed * 100 + r)
            for grp in (trX, te):
                perm = [q[0][0] for q in grp]
                rnd.shuffle(perm)
                for j in range(len(grp)):
                    grp[j] = ((perm[j],) + grp[j][0][1:],) + grp[j][1:]
        trY = [q[1] for q in trX]
        Xtr = [list(q[0]) for q in trX]
        cC = olsk([[x[1], x[2], x[3]] for x in Xtr], trY)
        cF = olsk(Xtr, trY)
        e_mod = [q[1] for q in te]
        e_ctl = [ap(cC, (q[0][1], q[0][2], q[0][3])) - q[1] for q in te]
        e_fit = [ap(cF, list(q[0])) - q[1] for q in te]
        rm = lambda e: math.sqrt(sum(x * x for x in e) / len(e))
        med = lambda e: sorted(abs(x) for x in e)[len(e) // 2]
        t_c = tstat([a * a - b * b for a, b in zip(e_ctl, e_fit)])
        vf = var_factor(r, [1.0])
        dps = []; br_m = br_f = 0.0; ll_m = ll_f = 0.0; nn = 0
        for (row, y, c, K, res, lock, ix, sg) in te:
            sd = sg * math.sqrt(vf)
            if sd <= 0:
                continue
            mu_m = (lock + r * ix) / N_AVG
            yhat = ap(cF, list(row))
            mu_f = (lock + r * (ix + sg * yhat)) / N_AVG
            pm = ND.cdf((mu_m - K) / sd); pf = ND.cdf((mu_f - K) / sd)
            dps.append(abs(pf - pm) * 100.0)
            br_m += (pm - res) ** 2; br_f += (pf - res) ** 2
            e = 1e-6
            ll_m += -(res * math.log(max(pm, e)) + (1 - res) * math.log(max(1 - pm, e)))
            ll_f += -(res * math.log(max(pf, e)) + (1 - res) * math.log(max(1 - pf, e)))
            nn += 1
        dps.sort()
        agg[r] = (100 * (1 - rm(e_fit) / rm(e_ctl)), t_c, dps[nn // 2],
                  dps[int(nn * .95)], (br_m - br_f) / nn, (ll_m - ll_f) / nn)
        print("  %4d %5d %8.4f %8.4f %8.4f %9.2f %7.3f %9.2f %8.2f "
              "%9.4f %10.4f %9.3f %+9.5f %+8.5f"
              % (r, len(te), rm(e_mod), rm(e_ctl), rm(e_fit),
                 100 * (1 - rm(e_fit) / rm(e_ctl)), cF[1], t_c,
                 100 * (1 - med(e_fit) / med(e_mod)),
                 dps[nn // 2], dps[int(nn * .95)], dps[-1],
                 (br_m - br_f) / nn, (ll_m - ll_f) / nn))
    if agg:
        v = list(agg.values())
        print("  MEAN over r: fit-ctl%% %+.2f | max t %.2f | r with t>2: %d/%d | "
              "median |dp| %.4fc | p95 |dp| %.4fc | dBrier %+.5f | dLogLoss %+.5f"
              % (sum(x[0] for x in v) / len(v), max(abs(x[1]) for x in v),
                 sum(1 for x in v if x[1] > 2), len(v),
                 sum(x[2] for x in v) / len(v), sum(x[3] for x in v) / len(v),
                 sum(x[4] for x in v) / len(v), sum(x[5] for x in v) / len(v)))
    return agg


print("")
print("=" * 100)
print("A. wmid replica, their construction")
run(rep, ebar_w, 0, "wmid rep_lead=0 (no arrival advantage)")
run(rep, ebar_w, 1, "wmid rep_lead=1 (the claimed real-time position)")
run(rep, ebar_w, -60, "wmid rep_lead=-60 PLACEBO (minute-stale)")
print("")
print("=" * 100)
print("B. LEVEL-vs-CHANGE: pure replica increment rep[t+1]-rep[t], NO rebasing")
run(rep, ebar_w, 1, "wmid rep_lead=1 DELTA", mode="delta")
print("")
print("=" * 100)
print("C. PERMUTATION PLACEBO: replica column shuffled across closes")
run(rep, ebar_w, 1, "wmid rep_lead=1 PERMUTED", seed=7)
print("")
print("=" * 100)
print("D. coinbase-only reading (the study's best variant)")
run(cbm, ebar_c, 1, "coinbase rep_lead=1")
run(cbm, ebar_c, 1, "coinbase rep_lead=1 DELTA", mode="delta")
