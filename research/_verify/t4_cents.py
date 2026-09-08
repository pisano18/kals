"""How many CENTS does the spot lead move the fair value, ON THE CLOSES WHERE
pin COULD TRADE -- and does it move it the right way?

The all-closes |dp| is ~0 because at tau<=20s almost every BTC market is
already decided (|z| in the tens).  The only population that matters is the
near-the-money subset.  This measures the size of that population and the
signed value of the shift there, against the ACTUAL settled outcome.

Read-only."""
import os, sys, math, json, array, random
from statistics import NormalDist
sys.path.insert(0, r"C:\kals-repo\research")
from engine import var_factor, N_AVG

ND = NormalDist()
NAN = float("nan")
CACHE = r"C:\Users\Joe\AppData\Local\Temp\verify_btc_cache.bin"
with open(CACHE, "rb") as f:
    t0 = int.from_bytes(f.read(8), "little")
    n = int.from_bytes(f.read(8), "little")
    idx = array.array("d"); idx.fromfile(f, n)
    rep = array.array("d"); rep.fromfile(f, n)
    cbm = array.array("d"); cbm.fromfile(f, n)

W = 300


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


imean = causal_mean(idx)
sig = causal_sigma(idx)
mk = json.load(open(r"C:\kals\fulltape\markets.json"))
closes = []
for r_ in mk["KXBTC15M"]:
    c = int(r_["close"]); i = c - t0
    if not (60 <= i < n):
        continue
    if any(idx[i - k] != idx[i - k] for k in range(1, 61)):
        continue
    closes.append((c, float(r_["strike"]), float(r_["result"])))
closes.sort()
split = closes[int(len(closes) * 0.60)][0]


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
    if len(d) < 2:
        return 0.0
    m = sum(d) / len(d)
    v = sum((x - m) ** 2 for x in d) / (len(d) - 1)
    return m / math.sqrt(v / len(d)) if v > 0 else 0.0


def collect(repsrc, rep_lead, r, mode):
    tr_, te_ = [], []
    for (c, K, res) in closes:
        t = c - 1 - r; tt = t + rep_lead
        i = t - t0; itr = tt - t0
        if i < W + 5 or itr < 0 or itr >= n:
            continue
        ix = idx[i]
        if ix != ix:
            continue
        d1 = ix - idx[i - 1]; d2 = idx[i - 1] - idx[i - 2]
        m1 = imean[i] - ix
        rp = repsrc[itr]; rp0 = repsrc[i]; sg = sig[i]
        lock = [idx[c - t0 - k] for k in range(r + 1, 61)]
        unk = [idx[c - t0 - k] for k in range(1, r + 1)]
        if any(x != x for x in lock + unk):
            continue
        if not (rp == rp and rp0 == rp0 and sg == sg and sg > 0
                and d1 == d1 and d2 == d2 and m1 == m1):
            continue
        bs = (rp - rp0) / sg if mode == "delta" else NAN
        y = (sum(unk) / r - ix) / sg
        rec = ((bs, d1 / sg, d2 / sg, m1 / sg), y, c, K, res, sum(lock), ix, sg)
        (tr_ if c < split else te_).append(rec)
    return tr_, te_


BANDS = [(0.02, 0.98), (0.05, 0.95), (0.10, 0.90), (0.20, 0.80)]
print("BTC / KXBTC15M -- DELTA construction (rep[t+1]-rep[t]), the strongest form.")
print("p_model = production endgame.fair() with sigma = causal 300s sd of 1s index moves.")
print("dp = p_fit - p_model in CENTS.  dBrier>0 and dLL>0 mean the SPOT-ADJUSTED")
print("probability was closer to the settled outcome.  t is over closes.")
for src, name in ((cbm, "coinbase"), (rep, "wmid")):
    print("")
    print("=" * 112)
    print("SOURCE: %s" % name)
    print("   r   n_test | frac p_model in (.05,.95) |  near-money n | med|dp| p90|dp| max|dp| |"
          "  dBrier(near)   t  |  dLL(near)")
    pool = {b: [] for b in BANDS}
    poolbr = {b: [] for b in BANDS}
    for r in range(2, 20):
        tr_, te_ = collect(src, 1, r, "delta")
        if len(tr_) < 30 or len(te_) < 30:
            continue
        cF = olsk([list(q[0]) for q in tr_], [q[1] for q in tr_])
        vf = var_factor(r, [1.0])
        rows = []
        for (row, y, c, K, res, lock, ix, sg) in te_:
            sd = sg * math.sqrt(vf)
            if sd <= 0:
                continue
            pm = ND.cdf(((lock + r * ix) / N_AVG - K) / sd)
            yh = ap(cF, list(row))
            pf = ND.cdf(((lock + r * (ix + sg * yh)) / N_AVG - K) / sd)
            rows.append((pm, pf, res))
        nm = [q for q in rows if 0.05 < q[0] < 0.95]
        for b in BANDS:
            sub = [q for q in rows if b[0] < q[0] < b[1]]
            pool[b].extend(sub)
            poolbr[b].extend([((q[0] - q[2]) ** 2 - (q[1] - q[2]) ** 2) for q in sub])
        if not nm:
            print("  %3d %6d | %22.4f | %13d | (none near the money)" % (r, len(rows), 0.0, 0))
            continue
        dps = sorted(abs(q[1] - q[0]) * 100 for q in nm)
        brd = [((q[0] - q[2]) ** 2 - (q[1] - q[2]) ** 2) for q in nm]
        e = 1e-6
        lld = [(-(q[2] * math.log(max(q[0], e)) + (1 - q[2]) * math.log(max(1 - q[0], e)))
                + (q[2] * math.log(max(q[1], e)) + (1 - q[2]) * math.log(max(1 - q[1], e))))
               for q in nm]
        print("  %3d %6d | %22.4f | %13d | %7.3f %7.3f %7.2f | %+12.5f %5.2f | %+9.5f"
              % (r, len(rows), len(nm) / len(rows), len(nm),
                 dps[len(dps) // 2], dps[int(len(dps) * .9)], dps[-1],
                 sum(brd) / len(brd), tstat(brd), sum(lld) / len(lld)))
    print("  POOLED over all r (nested windows on the same closes -- NOT 18 independent tests):")
    for b in BANDS:
        sub = pool[b]; brd = poolbr[b]
        if len(sub) < 5:
            print("    p_model in (%.2f,%.2f): n=%d  too few" % (b[0], b[1], len(sub)))
            continue
        dps = sorted(abs(q[1] - q[0]) * 100 for q in sub)
        distinct = len(set())
        print("    p_model in (%.2f,%.2f): n=%-5d med|dp| %6.3fc  p90 %6.3fc  max %6.2fc | "
              "dBrier %+.5f  t %5.2f | frac dp>0.05c %.3f"
              % (b[0], b[1], len(sub), dps[len(dps) // 2], dps[int(len(dps) * .9)],
                 dps[-1], sum(brd) / len(brd), tstat(brd),
                 sum(1 for x in dps if x > 0.05) / len(dps)))
