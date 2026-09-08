"""Two checks on the DEPTH study.

(1) Re-derive its headline conditional-quantile lifts straight from its own
    cache, independently of its ranking code, at r=19 on the settlement target.
(2) The economic translation it never made: take the PRODUCTION fair-value
    model, rescale its sigma by a factor learned per volume quintile on
    TRAINING closes only, and score the resulting probability against the
    ACTUAL settled outcome of BTC markets.  Report the price move in cents.

Read-only."""
import gzip, sys, math, json, array, random
from statistics import NormalDist
sys.path.insert(0, r"C:\kals-repo\research")
from engine import var_factor, N_AVG

ND = NormalDist(); NAN = float("nan")
CSV = r"C:\Users\Joe\AppData\Local\Temp\spotdepth_v5.csv.gz"
CACHE = r"C:\Users\Joe\AppData\Local\Temp\verify_btc_cache.bin"

with open(CACHE, "rb") as f:
    t0 = int.from_bytes(f.read(8), "little"); n = int.from_bytes(f.read(8), "little")
    idx = array.array("d"); idx.fromfile(f, n)

# ---- which seconds do we need for part 2? decision seconds of BTC closes ----
mk = json.load(open(r"C:\kals\fulltape\markets.json"))
closes = []
for r_ in mk["KXBTC15M"]:
    c = int(r_["close"]); i = c - t0
    if 60 <= i < n and not any(idx[i - k] != idx[i - k] for k in range(1, 61)):
        closes.append((c, float(r_["strike"]), float(r_["result"])))
closes.sort()
split = closes[int(len(closes) * 0.60)][0]
RS = list(range(2, 20))
want = set()
for (c, K, res) in closes:
    for r in RS:
        want.add(c - 1 - r)

# ---- one streaming pass over the 90 MB cache -------------------------------
hdr = None
feat = {}          # sec -> (sig300, vol300, vol60, ntr60)
qs = {"sig": [], "v300": [], "v60": [], "ntr": [], "am19": [], "mv19": []}
brti_by_sec = {}
rows_for_lift = []
print("streaming cache ...", flush=True)
with gzip.open(CSV, "rt") as f:
    f.readline()
    hdr = f.readline().strip().split(",")
    ix = {k: i for i, k in enumerate(hdr)}
    need = ("sec", "brti", "vol300", "vol60", "ntr60")
    for line in f:
        p = line.rstrip("\n").split(",")
        try:
            s = int(p[ix["sec"]])
        except (ValueError, IndexError):
            continue
        try:
            b = float(p[ix["brti"]]); v3 = float(p[ix["vol300"]])
            v6 = float(p[ix["vol60"]]); nt = float(p[ix["ntr60"]])
        except ValueError:
            continue
        brti_by_sec[s] = b
        if s in want:
            feat[s] = (v3, v6, nt)
        rows_for_lift.append((s, v3, nt))
print("  cache rows %d, decision seconds matched %d of %d"
      % (len(rows_for_lift), len(feat), len(want)))

# ---------------------------------------------------------------------------
# (1) INDEPENDENT LIFT CHECK.  sig300 is not in the cache, so rebuild it here
#     from the cache's own brti column, exactly as the study describes:
#     trailing 300 s sd of 1 s log returns in bps, half-open [t-300, t).
# ---------------------------------------------------------------------------
secs = sorted(brti_by_sec)
lo, hi = secs[0], secs[-1]
sig = {}
from collections import deque
dq = deque(); s1 = s2 = 0.0
prev = None
for s in secs:
    while dq and dq[0][0] < s - 300:
        j, v = dq.popleft(); s1 -= v; s2 -= v * v
    if len(dq) >= 30:
        m = s1 / len(dq); v = s2 / len(dq) - m * m
        sig[s] = math.sqrt(v) if v > 0 else NAN
    b = brti_by_sec[s]
    pb = brti_by_sec.get(s - 1)
    if pb and b > 0 and pb > 0:
        r_ = math.log(b / pb) * 1e4
        dq.append((s, r_)); s1 += r_; s2 += r_ * r_

# settlement-relevant target am19 = |mean(next 19 prints) - now| in bps
def am(s, r=19):
    b = brti_by_sec.get(s)
    if not b:
        return None
    acc = 0.0
    for k in range(1, r + 1):
        v = brti_by_sec.get(s + k)
        if v is None:
            return None
        acc += v
    return abs(acc / r - b) / b * 1e4


print("")
print("(1) INDEPENDENT LIFT CHECK -- r=19, target am19 = |mean(next 19 prints) - now| bps")
lift_rows = []
for (s, v3, nt) in rows_for_lift:
    sg = sig.get(s)
    if sg is None or sg != sg:
        continue
    a = am(s)
    if a is None:
        continue
    lift_rows.append((sg, v3, nt, a))
print("    n = %d seconds with sigma, volume and a contiguous 19s forward window"
      % len(lift_rows))


def quint(rows, key):
    v = sorted(r[key] for r in rows)
    cuts = [v[int(len(v) * q / 5)] for q in range(1, 5)]
    buckets = [[] for _ in range(5)]
    for r in rows:
        x = r[key]; b = 0
        while b < 4 and x >= cuts[b]:
            b += 1
        buckets[b].append(r[3])
    return buckets


allam = sorted(r[3] for r in lift_rows)
p99u = allam[int(len(allam) * .99)]
print("    unconditional am19: p50 %.3f  p99 %.3f  p99.9 %.3f bps"
      % (allam[len(allam) // 2], p99u, allam[int(len(allam) * .999)]))
for key, name in ((0, "sig300_bps (incumbent)"), (1, "vol300_btc"), (2, "ntr60")):
    bk = quint(lift_rows, key)
    ps = []
    for b in bk:
        b.sort()
        ps.append(b[int(len(b) * .99)])
    print("    %-24s Q1 p99 %6.3f (%+6.1f%%) ... Q5 p99 %6.3f (%+6.1f%%)  Q5/Q1 = %.2fx"
          % (name, ps[0], 100 * (ps[0] / p99u - 1), ps[4],
             100 * (ps[4] / p99u - 1), ps[4] / ps[0]))

# ---------------------------------------------------------------------------
# (2) THE ECONOMIC TEST
# ---------------------------------------------------------------------------
print("")
print("(2) DOES CONDITIONING SIGMA ON VOLUME IMPROVE THE QUOTED PROBABILITY?")
print("    sd_model = sig300*brti/1e4 * sqrt(var_factor(r));  sd_cond = sd_model * g(q)")
print("    g(q) = sd of the standardised residual in volume quintile q, learned on")
print("    TRAINING closes only.  Scored on TEST closes against the settled result.")
cells = []
for (c, K, res) in closes:
    for r in RS:
        t = c - 1 - r
        i = t - t0
        if i < 5 or c - t0 >= n:
            continue
        ix_ = idx[i]
        sg = sig.get(t)
        fv = feat.get(t)
        if ix_ != ix_ or sg is None or sg != sg or fv is None:
            continue
        lock = [idx[c - t0 - k] for k in range(r + 1, 61)]
        unk = [idx[c - t0 - k] for k in range(1, r + 1)]
        if any(x != x for x in lock + unk):
            continue
        sigma_usd = sg * ix_ / 1e4
        sd = sigma_usd * math.sqrt(var_factor(r, [1.0]))
        if sd <= 0:
            continue
        mu = (sum(lock) + r * ix_) / N_AVG
        settle = (sum(lock) + sum(unk)) / N_AVG
        cells.append((c, r, mu, sd, K, res, settle, fv[0], c < split))
print("    usable (close, r) cells: %d  train %d  test %d"
      % (len(cells), sum(1 for x in cells if x[8]), sum(1 for x in cells if not x[8])))

tr = [x for x in cells if x[8]]
te = [x for x in cells if not x[8]]
cuts = sorted(x[7] for x in tr)
qc = [cuts[int(len(cuts) * q / 5)] for q in range(1, 5)]


def qof(v):
    b = 0
    while b < 4 and v >= qc[b]:
        b += 1
    return b


g = []
for q in range(5):
    u = [(x[6] - x[2]) / x[3] for x in tr if qof(x[7]) == q]
    m = sum(u) / len(u)
    v = sum((z - m) ** 2 for z in u) / (len(u) - 1)
    g.append(math.sqrt(v))
gm_all = math.sqrt(sum(((x[6] - x[2]) / x[3]) ** 2 for x in tr) / len(tr))
print("    learned scale by vol300 quintile (train): "
      + "  ".join("Q%d %.3f" % (q + 1, g[q]) for q in range(5))
      + "   (pooled %.3f)" % gm_all)
dps = []
by_close = {}
near = []
for x in te:
    (c, r, mu, sd, K, res, settle, v3, _) = x
    pm = ND.cdf((mu - K) / sd)
    pf = ND.cdf((mu - K) / (sd * g[qof(v3)]))
    dps.append(abs(pf - pm) * 100)
    by_close.setdefault(c, []).append((pm - res) ** 2 - (pf - res) ** 2)
    if 0.05 < pm < 0.95:
        near.append((c, abs(pf - pm) * 100, (pm - res) ** 2 - (pf - res) ** 2))
dps.sort()
print("    |dp| over ALL test cells (n=%d): p50 %.4fc  p90 %.4fc  p99 %.4fc  max %.2fc"
      % (len(dps), dps[len(dps) // 2], dps[int(len(dps) * .9)],
         dps[int(len(dps) * .99)], dps[-1]))
for thr in (0.05, 0.5, 2.0):
    print("      |dp| > %4.2fc on %6.3f%% of cells"
          % (thr, 100.0 * sum(1 for z in dps if z > thr) / len(dps)))
nd = sorted(z[1] for z in near)
print("    NEAR-MONEY (p_model .05-.95): %d cells over %d distinct closes; "
      "|dp| p50 %.3fc p90 %.3fc max %.2fc"
      % (len(near), len(set(z[0] for z in near)),
         nd[len(nd) // 2], nd[int(len(nd) * .9)], nd[-1]))
per = [sum(v) / len(v) for v in by_close.values()]
m = sum(per) / len(per)
vv = sum((z - m) ** 2 for z in per) / (len(per) - 1)
print("    Brier gain per CLOSE, all test closes: %+.6f  t %.2f  over %d closes"
      % (m, m / math.sqrt(vv / len(per)), len(per)))
nb = {}
for (c, d, b) in near:
    nb.setdefault(c, []).append(b)
pn = [sum(v) / len(v) for v in nb.values()]
if len(pn) > 2:
    m2 = sum(pn) / len(pn)
    v2 = sum((z - m2) ** 2 for z in pn) / (len(pn) - 1)
    rnd = random.Random(3); bs = []
    for _ in range(4000):
        s = [pn[rnd.randrange(len(pn))] for _ in pn]
        bs.append(sum(s) / len(s))
    bs.sort()
    print("    Brier gain per NEAR-MONEY close: %+.5f  t %.2f  n=%d  "
          "bootstrap 95%% CI [%+.5f, %+.5f]"
          % (m2, m2 / math.sqrt(v2 / len(pn)), len(pn), bs[100], bs[3900]))
    print("    per-close gains: %s" % " ".join("%+.3f" % z for z in sorted(pn)))
