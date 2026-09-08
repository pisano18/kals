"""Is the depth study's conditioning worth anything ON TOP of simply fixing the
level of the incumbent sigma?  And how fragile is the flow factor live?

Compares four sigma models on the SAME test closes, all fitted on training
closes only:
   M0  sd = sigma300 * sqrt(var_factor(r))                  (production today)
   M1  M0 * one global scale                                (level fix only)
   M2  M0 * scale per vol300 quintile                       (the depth study)
   M3  M0 * scale per ntr60 quintile                        (trade count)
Scored by log loss and Brier against the ACTUAL settled outcome, clustered on
close.  Read-only."""
import gzip, sys, math, json, array, random
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

mk = json.load(open(r"C:\kals\fulltape\markets.json"))
closes = []
for r_ in mk["KXBTC15M"]:
    c = int(r_["close"]); i = c - t0
    if 60 <= i < n and not any(idx[i - k] != idx[i - k] for k in range(1, 61)):
        closes.append((c, float(r_["strike"]), float(r_["result"])))
closes.sort()
split = closes[int(len(closes) * 0.60)][0]
RS = list(range(2, 20))
want = set(c - 1 - r for (c, K, res) in closes for r in RS)

brti = {}; feat = {}
nex_hist = {}
with gzip.open(CSV, "rt") as f:
    f.readline()
    ix = {k: i for i, k in enumerate(f.readline().strip().split(","))}
    for line in f:
        p = line.rstrip("\n").split(",")
        try:
            s = int(p[ix["sec"]]); brti[s] = float(p[ix["brti"]])
        except (ValueError, IndexError):
            continue
        try:
            nex_hist[int(float(p[ix["n_ex"]]))] = nex_hist.get(int(float(p[ix["n_ex"]])), 0) + 1
        except ValueError:
            pass
        if s in want:
            try:
                feat[s] = (float(p[ix["vol300"]]), float(p[ix["ntr60"]]),
                           float(p[ix["vol60"]]))
            except ValueError:
                pass

print("LIVE FRAGILITY -- venues present in the replica second by second:")
tot = sum(nex_hist.values())
for k in sorted(nex_hist):
    print("   n_ex = %d : %9d seconds (%6.2f%%)" % (k, nex_hist[k], 100.0 * nex_hist[k] / tot))

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

cells = []
for (c, K, res) in closes:
    for r in RS:
        t = c - 1 - r; i = t - t0
        if i < 5 or c - t0 >= n:
            continue
        ix_ = idx[i]; sg = sig.get(t); fv = feat.get(t)
        if ix_ != ix_ or sg is None or sg != sg or fv is None:
            continue
        lock = [idx[c - t0 - k] for k in range(r + 1, 61)]
        unk = [idx[c - t0 - k] for k in range(1, r + 1)]
        if any(x != x for x in lock + unk):
            continue
        sd = (sg * ix_ / 1e4) * math.sqrt(var_factor(r, [1.0]))
        if sd <= 0:
            continue
        mu = (sum(lock) + r * ix_) / N_AVG
        settle = (sum(lock) + sum(unk)) / N_AVG
        cells.append([c, r, mu, sd, K, res, settle, fv[0], fv[1], c < split])
tr = [x for x in cells if x[9]]; te = [x for x in cells if not x[9]]
print("")
print("cells: train %d  test %d  (test closes %d)"
      % (len(tr), len(te), len(set(x[0] for x in te))))


def scales(rows, col, nq=5):
    if col is None:
        u = [(x[6] - x[2]) / x[3] for x in rows]
        return None, [math.sqrt(sum(z * z for z in u) / len(u))] * 5
    v = sorted(x[col] for x in rows)
    cuts = [v[int(len(v) * q / nq)] for q in range(1, nq)]

    def q(x):
        b = 0
        while b < nq - 1 and x >= cuts[b]:
            b += 1
        return b
    g = []
    for b in range(nq):
        u = [(x[6] - x[2]) / x[3] for x in rows if q(x[col]) == b]
        g.append(math.sqrt(sum(z * z for z in u) / len(u)))
    return q, g


models = [("M0 production", None, [1.0] * 5),
          ("M1 global scale", None, None),
          ("M2 vol300 quintile", 7, None),
          ("M3 ntr60 quintile", 8, None)]
out = {}
for (name, col, fixed) in models:
    if fixed is None:
        qf, g = scales(tr, col)
    else:
        qf, g = None, fixed
    ll = {}; br = {}; dps = []
    for x in te:
        (c, r, mu, sd, K, res, settle, v3, nt, _) = x
        f = g[0] if qf is None else g[qf(x[col])]
        p = ND.cdf((mu - K) / (sd * f))
        e = 1e-6
        ll.setdefault(c, []).append(-(res * math.log(max(p, e))
                                      + (1 - res) * math.log(max(1 - p, e))))
        br.setdefault(c, []).append((p - res) ** 2)
        dps.append(p)
    out[name] = (ll, br, g, dps)
    print("  %-20s scales %s" % (name, " ".join("%.3f" % z for z in g)))

base_ll = {c: sum(v) / len(v) for c, v in out["M0 production"][0].items()}
base_br = {c: sum(v) / len(v) for c, v in out["M0 production"][1].items()}
print("")
print("  model                 mean logloss/close   dLL vs M0    t      "
      "mean Brier/close   dBrier vs M0    t")
for (name, _, _) in models:
    ll = {c: sum(v) / len(v) for c, v in out[name][0].items()}
    br = {c: sum(v) / len(v) for c, v in out[name][1].items()}
    dl = [base_ll[c] - ll[c] for c in ll]
    db = [base_br[c] - br[c] for c in br]

    def tt(v):
        m = sum(v) / len(v)
        s = sum((z - m) ** 2 for z in v) / (len(v) - 1)
        return m, (m / math.sqrt(s / len(v)) if s > 0 else 0.0)
    ml, tl = tt(dl); mb, tb = tt(db)
    print("  %-20s %18.6f %+12.6f %6.2f %18.6f %+14.7f %6.2f"
          % (name, sum(ll.values()) / len(ll), ml, tl,
             sum(br.values()) / len(br), mb, tb))

print("")
print("  Cents: |p(M2) - p(M0)| and |p(M1) - p(M0)| on the SAME test cells")
p0 = out["M0 production"][3]
for nm in ("M1 global scale", "M2 vol300 quintile", "M3 ntr60 quintile"):
    d = sorted(abs(a - b) * 100 for a, b in zip(out[nm][3], p0))
    nz = [x for x in d if x > 0.05]
    print("    %-20s p50 %.4fc p90 %.4fc p99 %.4fc max %.2fc | >0.05c on %.2f%% of cells"
          % (nm, d[len(d) // 2], d[int(len(d) * .9)], d[int(len(d) * .99)], d[-1],
             100.0 * len(nz) / len(d)))
