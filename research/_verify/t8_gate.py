"""THE DECISIVE ECONOMIC TEST FOR pin's FROZEN RULE.

pinrun.py fires only when the model's fair value is >= 0.98 (buy YES) or
<= 0.02 (buy NO), at tau <= 20 s.  So the question is not "does RMSE fall" and
not "does the price move on near-money closes" -- it is:

    how often does each proposed adjustment change which side of the 0.98/0.02
    gate the fair value lands on, and when it does, WHICH ONE WAS RIGHT?

Adjustments compared, all fitted on the first 60% of closes by time:
    SPOT   mu shifted by the fitted replica increment (spotlead, delta form)
    SIG1   sigma multiplied by one global scale        (depth study, level only)
    SIG5   sigma multiplied by a vol300-quintile scale (depth study, as sold)

Read-only.  Book prices are NOT loaded, so the 0.5c edge leg of the rule is not
simulated: this measures the model half of the gate only, which is the half the
two studies claim to improve."""
import gzip, sys, math, json, array
from collections import deque
from statistics import NormalDist
sys.path.insert(0, r"C:\kals-repo\research")
from engine import var_factor, N_AVG

ND = NormalDist(); NAN = float("nan")
CSV = r"C:\Users\Joe\AppData\Local\Temp\spotdepth_v5.csv.gz"
CACHE = r"C:\Users\Joe\AppData\Local\Temp\verify_btc_cache.bin"
with open(CACHE, "rb") as f:
    t0 = int.from_bytes(f.read(8), "little"); n = int.from_bytes(f.read(8), "little")
    idx = array.array("d"); idx.fromfile(f, n)
    rep = array.array("d"); rep.fromfile(f, n)
    cbm = array.array("d"); cbm.fromfile(f, n)

mk = json.load(open(r"C:\kals\fulltape\markets.json"))
closes = []
for r_ in mk["KXBTC15M"]:
    c = int(r_["close"]); i = c - t0
    if 60 <= i < n and not any(idx[i - k] != idx[i - k] for k in range(1, 61)):
        closes.append((c, float(r_["strike"]), float(r_["result"])))
closes.sort()
split = closes[int(len(closes) * 0.60)][0]
RS = list(range(2, 20))                       # tau = r+1, so tau 3..20
want = set(c - 1 - r for (c, K, res) in closes for r in RS)

brti = {}; vol = {}
with gzip.open(CSV, "rt") as f:
    f.readline()
    ix = {k: i for i, k in enumerate(f.readline().strip().split(","))}
    for line in f:
        p = line.rstrip("\n").split(",")
        try:
            s = int(p[ix["sec"]]); brti[s] = float(p[ix["brti"]])
        except (ValueError, IndexError):
            continue
        if s in want:
            try:
                vol[s] = float(p[ix["vol300"]])
            except ValueError:
                pass
secs = sorted(brti); sig = {}
dq = deque(); s1 = s2 = 0.0
for s in secs:
    while dq and dq[0][0] < s - 300:
        j, v = dq.popleft(); s1 -= v; s2 -= v * v
    if len(dq) >= 30:
        m = s1 / len(dq); v = s2 / len(dq) - m * m
        sig[s] = math.sqrt(v) if v > 0 else NAN
    b = brti[s]; pb = brti.get(s - 1)
    if pb and b > 0 and pb > 0:
        r_ = math.log(b / pb) * 1e4
        dq.append((s, r_)); s1 += r_; s2 += r_ * r_


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
                fq = A[q][i]
                for j in range(i, m + 1):
                    A[q][j] -= fq * A[i][j]
    return [A[i][m] for i in range(m)]


for SRC, SNAME in ((cbm, "coinbase"), (rep, "wmid")):
    cells = []
    for r in RS:
        rows = []
        for (c, K, res) in closes:
            t = c - 1 - r; i = t - t0
            if i < 305 or c - t0 >= n:
                continue
            ix_ = idx[i]; sg = sig.get(t); v3 = vol.get(t)
            rp1 = SRC[i + 1]; rp0 = SRC[i]
            if ix_ != ix_ or sg is None or sg != sg or v3 is None:
                continue
            if rp1 != rp1 or rp0 != rp0:
                continue
            lock = [idx[c - t0 - k] for k in range(r + 1, 61)]
            unk = [idx[c - t0 - k] for k in range(1, r + 1)]
            if any(x != x for x in lock + unk):
                continue
            su = sg * ix_ / 1e4
            if su <= 0:
                continue
            sd = su * math.sqrt(var_factor(r, [1.0]))
            if sd <= 0:
                continue
            rows.append((c, r, (sum(lock) + r * ix_) / N_AVG, sd, K, res,
                         (sum(lock) + sum(unk)) / N_AVG, v3,
                         (rp1 - rp0) / su, su, sum(lock), ix_))
        tr = [x for x in rows if x[0] < split]
        te = [x for x in rows if x[0] >= split]
        if len(tr) < 30 or len(te) < 30:
            continue
        cF = olsk([[x[8]] for x in tr], [(x[6] * N_AVG - x[10] - r * x[11]) / (r * x[9])
                                         for x in tr])
        for x in te:
            yh = cF[0] + cF[1] * x[8]
            mu_s = (x[10] + r * (x[11] + x[9] * yh)) / N_AVG
            cells.append(list(x) + [mu_s])
    tr_all = [x for x in cells if x[0] < split]
    # sigma scales fitted on training closes
    te_all = [x for x in cells if x[0] >= split]
    trc = []
    for r in RS:
        for (c, K, res) in closes:
            pass
    # refit sigma scales on the same training cells (recomputed inline)
    trs = []
    for r in RS:
        for (c, K, res) in closes:
            if c >= split:
                continue
            t = c - 1 - r; i = t - t0
            if i < 305 or c - t0 >= n:
                continue
            ix_ = idx[i]; sg = sig.get(t); v3 = vol.get(t)
            if ix_ != ix_ or sg is None or sg != sg or v3 is None:
                continue
            lock = [idx[c - t0 - k] for k in range(r + 1, 61)]
            unk = [idx[c - t0 - k] for k in range(1, r + 1)]
            if any(x != x for x in lock + unk):
                continue
            sd = (sg * ix_ / 1e4) * math.sqrt(var_factor(r, [1.0]))
            if sd <= 0:
                continue
            mu = (sum(lock) + r * ix_) / N_AVG
            trs.append((((sum(lock) + sum(unk)) / N_AVG - mu) / sd, v3))
    g1 = math.sqrt(sum(u * u for u, _ in trs) / len(trs))
    vv = sorted(v for _, v in trs)
    cuts = [vv[int(len(vv) * q / 5)] for q in range(1, 5)]

    def qf(v):
        b = 0
        while b < 4 and v >= cuts[b]:
            b += 1
        return b
    g5 = []
    for b in range(5):
        u = [z for z, v in trs if qf(v) == b]
        g5.append(math.sqrt(sum(x * x for x in u) / len(u)))

    print("=" * 100)
    print("SOURCE %s   test cells %d over %d closes   (tau 3..20)"
          % (SNAME, len(te_all), len(set(x[0] for x in te_all))))
    print("  global sigma scale %.3f ; quintile scales %s"
          % (g1, " ".join("%.3f" % z for z in g5)))

    def gate(p):
        if p >= 0.98:
            return 1          # buy YES
        if p <= 0.02:
            return -1         # buy NO
        return 0

    def score(name, pfun):
        fire_m = fire_a = agree = 0
        only_m = []; only_a = []; flip = []
        for x in te_all:
            (c, r, mu, sd, K, res, settle, v3, bs, su, lock, ix_, mu_s) = x
            pm = ND.cdf((mu - K) / sd)
            pa = pfun(x)
            gm_, ga = gate(pm), gate(pa)
            if gm_:
                fire_m += 1
            if ga:
                fire_a += 1
            if gm_ and ga and gm_ == ga:
                agree += 1
            # correctness: a YES fire wins if result==1, a NO fire wins if 0
            win = lambda g_: (res == 1.0) if g_ == 1 else (res == 0.0)
            if gm_ and not ga:
                only_m.append(win(gm_))
            if ga and not gm_:
                only_a.append(win(ga))
            if gm_ and ga and gm_ != ga:
                flip.append((win(gm_), win(ga)))
        print("  %-28s fires model %4d | fires adj %4d | both-same %4d"
              % (name, fire_m, fire_a, agree))
        if only_m:
            print("      %3d fires the model takes and the adjustment KILLS: "
                  "%d would have WON, %d would have LOST"
                  % (len(only_m), sum(only_m), len(only_m) - sum(only_m)))
        else:
            print("      0 fires killed by the adjustment")
        if only_a:
            print("      %3d fires the adjustment ADDS: %d win, %d lose"
                  % (len(only_a), sum(only_a), len(only_a) - sum(only_a)))
        else:
            print("      0 fires added by the adjustment")
        if flip:
            print("      %3d fires whose SIDE flips: model right %d, adjustment right %d"
                  % (len(flip), sum(1 for a, b in flip if a),
                     sum(1 for a, b in flip if b)))
        # net contracts won/lost, one contract per fire, ignoring price/fees
        return only_m, only_a, flip

    score("SPOT (replica increment)",
          lambda x: ND.cdf((x[12] - x[4]) / x[3]))
    score("SIG1 (global sigma x%.3f)" % g1,
          lambda x: ND.cdf((x[2] - x[4]) / (x[3] * g1)))
    score("SIG5 (vol300 quintile sigma)",
          lambda x: ND.cdf((x[2] - x[4]) / (x[3] * g5[qf(x[7])])))
    score("SPOT + SIG1 together",
          lambda x: ND.cdf((x[12] - x[4]) / (x[3] * g1)))
