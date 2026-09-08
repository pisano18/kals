"""How OFTEN does the spot lead move the quoted price at all, how many
DISTINCT closes carry the near-money result, and does a cluster bootstrap on
closes keep the calibration gain away from zero?

Read-only."""
import sys, math, json, array, random
from statistics import NormalDist
sys.path.insert(0, r"C:\kals-repo\research")
from engine import var_factor, N_AVG

ND = NormalDist(); NAN = float("nan")
CACHE = r"C:\Users\Joe\AppData\Local\Temp\verify_btc_cache.bin"
with open(CACHE, "rb") as f:
    t0 = int.from_bytes(f.read(8), "little"); n = int.from_bytes(f.read(8), "little")
    idx = array.array("d"); idx.fromfile(f, n)
    rep = array.array("d"); rep.fromfile(f, n)
    cbm = array.array("d"); cbm.fromfile(f, n)
W = 300


def causal(a, kind):
    out = array.array("d", [NAN]) * n
    s1 = s2 = 0.0; c = 0; ring = []; head = 0
    for t in range(n):
        if c >= 60:
            if kind == "mean":
                out[t] = s1 / c
            else:
                m = s1 / c; v = s2 / c - m * m
                out[t] = math.sqrt(v) if v > 0 else NAN
        if kind == "mean":
            v = a[t]
            ok = v == v
        else:
            x = a[t]; y = a[t - 1] if t else NAN
            ok = x == x and y == y
            v = x - y if ok else 0.0
        if ok:
            ring.append((t, v)); s1 += v; s2 += v * v; c += 1
        while head < len(ring) and ring[head][0] <= t - W:
            v = ring[head][1]; s1 -= v; s2 -= v * v; c -= 1; head += 1
        if head > 8192:
            del ring[:head]; head = 0
    return out


imean = causal(idx, "mean"); sig = causal(idx, "sd")
mk = json.load(open(r"C:\kals\fulltape\markets.json"))
closes = []
for r_ in mk["KXBTC15M"]:
    c = int(r_["close"]); i = c - t0
    if 60 <= i < n and not any(idx[i - k] != idx[i - k] for k in range(1, 61)):
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
            if q != i and A[q][i]:
                f = A[q][i]
                for j in range(i, m + 1):
                    A[q][j] -= f * A[i][j]
    return [A[i][m] for i in range(m)]


def ap(c, row):
    v = c[0]
    for cc, x in zip(c[1:], row):
        v += cc * x
    return v


allrows = []          # (close, r, pm, pf, res, |dp|c)
for src, nm in ((cbm, "coinbase"), (rep, "wmid")):
    rows_src = []
    for r in range(2, 20):
        tr_, te_ = [], []
        for (c, K, res) in closes:
            t = c - 1 - r; i = t - t0; itr = i + 1
            if i < W + 5 or itr >= n:
                continue
            ix = idx[i]
            if ix != ix:
                continue
            d1 = ix - idx[i - 1]; d2 = idx[i - 1] - idx[i - 2]; m1 = imean[i] - ix
            rp = src[itr]; rp0 = src[i]; sg = sig[i]
            lock = [idx[c - t0 - k] for k in range(r + 1, 61)]
            unk = [idx[c - t0 - k] for k in range(1, r + 1)]
            if any(x != x for x in lock + unk):
                continue
            if not (rp == rp and rp0 == rp0 and sg == sg and sg > 0
                    and d1 == d1 and d2 == d2 and m1 == m1):
                continue
            rec = (((rp - rp0) / sg, d1 / sg, d2 / sg, m1 / sg),
                   (sum(unk) / r - ix) / sg, c, K, res, sum(lock), ix, sg)
            (tr_ if c < split else te_).append(rec)
        if len(tr_) < 30 or len(te_) < 30:
            continue
        cF = olsk([list(q[0]) for q in tr_], [q[1] for q in tr_])
        vf = var_factor(r, [1.0])
        for (row, y, c, K, res, lock, ix, sg) in te_:
            sd = sg * math.sqrt(vf)
            if sd <= 0:
                continue
            pm = ND.cdf(((lock + r * ix) / N_AVG - K) / sd)
            pf = ND.cdf(((lock + r * (ix + sg * ap(cF, list(row)))) / N_AVG - K) / sd)
            rows_src.append((c, r, pm, pf, res, abs(pf - pm) * 100))
    print("=" * 100)
    print("SOURCE %s -- %d (close, r) test observations over %d distinct closes"
          % (nm, len(rows_src), len(set(q[0] for q in rows_src))))
    dp = sorted(q[5] for q in rows_src)
    for thr in (0.05, 0.5, 2.0, 10.0):
        print("   |dp| > %5.2fc on %6.3f%% of all (close,r) cells"
              % (thr, 100.0 * sum(1 for x in dp if x > thr) / len(dp)))
    print("   |dp| percentiles over ALL cells: p50 %.4fc  p90 %.4fc  p99 %.4fc  max %.2fc"
          % (dp[len(dp) // 2], dp[int(len(dp) * .9)], dp[int(len(dp) * .99)], dp[-1]))
    near = [q for q in rows_src if 0.05 < q[2] < 0.95]
    dcl = sorted(set(q[0] for q in near))
    print("   NEAR-MONEY (p_model in .05-.95): %d cells over %d DISTINCT closes"
          % (len(near), len(dcl)))
    br = {}
    for q in near:
        br.setdefault(q[0], []).append((q[2] - q[4]) ** 2 - (q[3] - q[4]) ** 2)
    per_close = [sum(v) / len(v) for v in br.values()]
    m = sum(per_close) / len(per_close)
    print("   mean per-CLOSE Brier gain (model minus fit): %+.5f  over %d closes"
          % (m, len(per_close)))
    rnd = random.Random(11)
    bs = []
    for _ in range(4000):
        s = [per_close[rnd.randrange(len(per_close))] for _ in per_close]
        bs.append(sum(s) / len(s))
    bs.sort()
    print("   cluster bootstrap 95%% CI on that gain: [%+.5f, %+.5f]   (excludes 0? %s)"
          % (bs[100], bs[3900], "YES" if bs[100] > 0 or bs[3900] < 0 else "NO"))
    print("   per-close gains, sorted: %s"
          % " ".join("%+.3f" % x for x in sorted(per_close)))
