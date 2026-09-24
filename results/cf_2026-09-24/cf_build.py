"""Counterfactual dataset: for every market the live bot entered, the per-second
picture from 45 s to close -- OUR-SIDE belief rebuilt from the index tape with
pinrun's own maths, and what the market offered on our side (ask, ask size)
from the ticker tape -- so entry-timing / top-up / hedge rules can be priced
against Kalshi's real result for that market.

Sources, in the project's order of trust: index tape, ticker tape, our own
fills + Kalshi's ledger. For the 09-23 hours the recorder was deaf, the bot's
own per-second belief log (pintraj) stands in.

Output: one line per market with lists indexed by tau (0..45):
  conf[tau]  our-side belief at tau (None = no print)
  ask[tau]   our-side ask (yes_ask for YES, 1 - yes_bid for NO), None = none
  asz[tau]   size on offer at that ask (contracts)
  opp[tau]   the OTHER side's ask (what a hedge would cost), None = none
  osz[tau]   size on offer at that
"""
import json, glob, gzip, os, sys, time, math, collections
sys.path.insert(0, r"C:\kals-repo\research")
import pinledger as L, pinflat, settlewin
from engine import var_factor
import pinrun
from replay import SERIES_TO_INDEX

SP = r"C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad"
OUT = os.path.join(SP, "cf_dataset.jsonl")
IDX = r"C:\kals\kalshi_data\cfbenchmarks_value"
TKR = r"C:\kals\kalshi_data\ticker"
TAUS = list(range(0, 46))

rows = [json.loads(l) for l in open(os.path.join(SP, "rebuild_spike.jsonl"), encoding="utf-8")]
rows = [r for r in rows if r.get("close_s") and r.get("iid")]
print("markets:", len(rows), flush=True)

# ---- ledger: our contracts / cost on each side -----------------------------
led = L.load_cache(L.LEDGER)
lg = {s["ticker"]: s for s in led.values() if s.get("ticker")}
def f(x):
    try: return float(x or 0)
    except Exception: return 0.0

# ---- hour files ---------------------------------------------------------------
def hour_name(sec):
    return time.strftime("%Y%m%dT%H", time.gmtime(sec)) + ".jsonl.gz"

def gz_lines(path):
    """Yield lines; a truncated (live) hour file yields what it has."""
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                yield line
    except Exception as e:   # EOFError / zlib.error on a truncated or corrupt hour: keep what was read
        print("  truncated:", os.path.basename(path), type(e).__name__, flush=True)

# which markets need which hour files
need_idx = collections.defaultdict(set)   # hour file -> set(iid)
need_tkr = collections.defaultdict(set)   # hour file -> set(ticker)
for r in rows:
    cs = int(r["close_s"])
    for s in (cs - 75, cs):
        need_idx[hour_name(s)].add(r["iid"])
    for s in (cs - 70, cs + 2):
        need_tkr[hour_name(s)].add(r["tk"])

# ---- index prints -------------------------------------------------------------
idx_ticks = collections.defaultdict(dict)   # iid -> {sec: value}
t0 = time.time()
for i, (hn, iids) in enumerate(sorted(need_idx.items())):
    p = os.path.join(IDX, hn)
    if not os.path.exists(p):
        continue
    for line in gz_lines(p):
        if '"cfbenchmarks_value"' not in line:
            continue
        j = line.find('"index_id":"')
        if j < 0:
            continue
        iid = line[j + 12: line.find('"', j + 12)]
        if iid not in iids:
            continue
        try:
            d = json.loads(line); m = d.get("msg") or {}
            dat = json.loads(m.get("data") or "{}")
            idx_ticks[iid][int(dat["time"]) // 1000] = float(dat["value"])
        except Exception:
            continue
print("index hours read: %d in %.0fs" % (len(need_idx), time.time() - t0), flush=True)

# ---- ticker updates -----------------------------------------------------------
tkr = collections.defaultdict(list)   # ticker -> [(ts_ms, yes_bid, yes_ask, bid_sz, ask_sz)]
t0 = time.time()
for i, (hn, tks) in enumerate(sorted(need_tkr.items())):
    p = os.path.join(TKR, hn)
    if not os.path.exists(p):
        continue
    for line in gz_lines(p):
        j = line.find('"market_ticker":"')
        if j < 0:
            continue
        tk = line[j + 17: line.find('"', j + 17)]
        if tk not in tks:
            continue
        try:
            m = json.loads(line)["msg"]
            tkr[tk].append((int(m.get("ts_ms") or int(m["ts"]) * 1000),
                            f(m.get("yes_bid_dollars")), f(m.get("yes_ask_dollars")),
                            f(m.get("yes_bid_size_fp")), f(m.get("yes_ask_size_fp"))))
        except Exception:
            continue
    if i % 50 == 0:
        print("  ticker hours %d/%d %.0fs" % (i, len(need_tkr), time.time() - t0), flush=True)
print("ticker hours read: %d in %.0fs" % (len(need_tkr), time.time() - t0), flush=True)

# ---- the bot's own per-second belief (stand-in where the tape is deaf) -------
traj = collections.defaultdict(dict)   # tk -> {tau: (conf_ours, ask, ask_size)}
for p in sorted(glob.glob(r"C:\kals-repo\results\pintraj-live-*.jsonl")):
    for line in open(p, encoding="utf-8", errors="replace"):
        if '"conf"' not in line:
            continue
        try: d = json.loads(line)
        except Exception: continue
        tk = d.get("ticker"); tau = d.get("tau")
        if tk is None or tau is None or d.get("conf") is None:
            continue
        traj[tk][int(tau)] = (float(d["conf"]), d.get("fair"), d.get("ask"), d.get("ask_size"), d.get("want"))

# ---- per-market assembly -------------------------------------------------------
def conf_yes(ticks, close_s, now_s, strike, sigma, digits):
    part = settlewin.partial(ticks, close_s, now_s)
    if part is None:
        return None
    locked, r = part
    ks = [k for k in ticks if k <= now_s]
    if not ks:
        return None
    spot = ticks[max(ks)]
    if now_s - max(ks) > 2:
        return None
    K = pinrun.eff_strike(strike, digits)
    mu = (locked + r * spot) / settlewin.N_AVG
    if r <= 0:
        return 1.0 if mu >= K else 0.0
    sd = float(sigma) * math.sqrt(var_factor(int(r), [1.0]))
    if sd <= 0:
        return 1.0 if mu >= K else 0.0
    return pinrun.conf_of((mu - K) / sd)

n_idx = n_traj = n_none = 0
with open(OUT, "w", encoding="utf-8") as out:
    for r in rows:
        cs = int(r["close_s"]); want = r["want"]; tk = r["tk"]
        s = lg.get(tk, {})
        yc, nc = f(s.get("yes_count_fp")), f(s.get("no_count_fp"))
        yd, nd = f(s.get("yes_total_cost_dollars")), f(s.get("no_total_cost_dollars"))
        result = s.get("market_result")
        o = dict(tk=tk, close_s=cs, want=want, tau_entry=r.get("tau"), price_entry=r.get("price"),
                 leg=r.get("leg"), edge_c=r.get("edge"), pnl=r["pnl"], result=result,
                 our_n=(yc if want == "yes" else nc), our_cost=(yd if want == "yes" else nd),
                 opp_n=(nc if want == "yes" else yc), opp_cost=(nd if want == "yes" else yd),
                 strike=r.get("strike"), sigma=r.get("sigma"), digits=r.get("digits"),
                 fair_logged=r.get("fair_logged"), prev_conf=r.get("prev_conf"))
        # belief
        ticks = {t: v for t, v in idx_ticks.get(r["iid"], {}).items() if cs - 75 <= t <= cs}
        conf = [None] * 46
        src = None
        if ticks and all(r.get(k) is not None for k in ("strike", "sigma")):
            for tau in TAUS:
                fy = conf_yes(ticks, cs, cs - tau, r["strike"], r["sigma"], r.get("digits"))
                if fy is not None:
                    conf[tau] = round(fy if want == "yes" else 1.0 - fy, 5)
            if sum(c is not None for c in conf) >= 20:
                src = "index"
        if src is None and tk in traj:
            for tau, (c, fy, ask, asz, w) in traj[tk].items():
                if 0 <= tau <= 45:
                    # traj `conf` is for the bot's CURRENT want at that second; use fair
                    if fy is not None:
                        conf[tau] = round(float(fy) if want == "yes" else 1.0 - float(fy), 5)
            if sum(c is not None for c in conf) >= 20:
                src = "traj"
        if src == "index": n_idx += 1
        elif src == "traj": n_traj += 1
        else: n_none += 1
        o["conf"] = conf; o["conf_src"] = src
        # the market: last ticker update at or before each second
        ups = sorted(tkr.get(tk, []))
        ask = [None] * 46; asz = [None] * 46; opp = [None] * 46; osz = [None] * 46
        bidside = [None] * 46
        k = 0
        for tau in reversed(TAUS):       # walk forward in time
            t_ms = (cs - tau) * 1000 + 999
            while k < len(ups) and ups[k][0] <= t_ms:
                k += 1
            if k == 0:
                continue
            _, yb, ya, bsz, asz_ = ups[k - 1]
            if want == "yes":
                a, az = (ya if 0 < ya < 1 else None), asz_
                op, oz = ((1.0 - yb) if 0 < yb < 1 else None), bsz
                bidside[tau] = yb if 0 < yb < 1 else None
            else:
                a, az = ((1.0 - yb) if 0 < yb < 1 else None), bsz
                op, oz = (ya if 0 < ya < 1 else None), asz_
                bidside[tau] = (1.0 - ya) if 0 < ya < 1 else None
            ask[tau] = round(a, 4) if a is not None else None
            asz[tau] = round(az, 2) if a is not None else None
            opp[tau] = round(op, 4) if op is not None else None
            osz[tau] = round(oz, 2) if op is not None else None
        o["ask"] = ask; o["asz"] = asz; o["opp"] = opp; o["osz"] = osz; o["bid"] = bidside
        o["n_ticker_updates"] = len(ups)
        out.write(json.dumps(o) + "\n")
print("belief from index: %d, from the bot's own log: %d, none: %d" % (n_idx, n_traj, n_none), flush=True)
print("wrote", OUT, flush=True)
