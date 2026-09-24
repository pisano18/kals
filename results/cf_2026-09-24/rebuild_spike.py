"""Rebuild, for every first live fill, the model's confidence at the entry
print and at the print before it, from the index recording, with pinrun's own
functions -- then apply the v-nospike rules and price them on Kalshi's ledger."""
import json, glob, gzip, os, sys, time, math, collections
sys.path.insert(0, r"C:\kals-repo\research")
import pinledger as L, pinflat, settlewin
from engine import var_factor
import pinrun
from replay import SERIES_TO_INDEX

OUT = r"C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad\rebuild_spike.jsonl"
TAPE = r"C:\kals\kalshi_data\cfbenchmarks_value"
COMM = {"KXGOLD15M", "KXWTI15M", "KXSILVER15M", "KXCOPPER15M", "KXNATGAS15M"}

led = L.load_cache(L.LEDGER)
pnl = {s["ticker"]: L.pnl(s) for s in led.values() if s.get("ticker")}

# ---- first fill per market, with its signal ------------------------------
fills = {}
for p in sorted(glob.glob(r"C:\kals-repo\results\pinrun-live-*.jsonl")):
    sig = None
    for line in open(p, encoding="utf-8", errors="replace"):
        if '"kind": "signal"' in line:
            try: sig = json.loads(line)
            except Exception: continue
        elif '"kind": "order"' in line:
            try: d = json.loads(line)
            except Exception: continue
            if (d.get("filled") or 0) <= 0: continue
            tk = d["ticker"]
            if tk in fills or not sig or sig.get("ticker") != tk or tk not in pnl: continue
            if tk.split("-")[0] in COMM or "CRYPTOLEAD" in tk: continue
            want = d.get("want") or sig.get("want")
            if want not in ("yes", "no"): continue
            t_ms = d.get("t_ms_send")
            if t_ms:
                t_send = float(t_ms) / 1000.0
            else:
                cid = d.get("client_order_id") or ""
                try: t_send = float(cid.split("-")[1]) / 1000.0
                except Exception:
                    ts = d.get("t", "")
                    try: t_send = time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
                    except Exception: continue
            fills[tk] = dict(tk=tk, want=want, t_send=t_send, tau=d.get("tau_at_send") or sig.get("tau"),
                             fair_logged=sig.get("fair"), strike=sig.get("strike"), digits=sig.get("digits"),
                             sigma=sig.get("sigma"), edge=sig.get("edge_c"), price=d.get("exec_price") or sig.get("price"),
                             leg=d.get("leg"), pnl=pnl[tk], close_s=pinflat.close_epoch(tk),
                             iid=SERIES_TO_INDEX.get(tk.split("-")[0]))
print("first fills:", len(fills), flush=True)

# ---- index prints, one hour file at a time, small cache ------------------
_cache = collections.OrderedDict()
def hour_file(sec):
    return os.path.join(TAPE, time.strftime("%Y%m%dT%H", time.gmtime(sec)) + ".jsonl.gz")
def load_hour(path):
    if path in _cache:
        _cache.move_to_end(path); return _cache[path]
    out = collections.defaultdict(dict)
    if os.path.exists(path):
        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if '"cfbenchmarks_value"' not in line: continue
                    try:
                        d = json.loads(line); m = d.get("msg") or {}
                        iid = m.get("index_id")
                        dat = json.loads(m.get("data") or "{}")
                        t = int(dat.get("time")) // 1000; v = float(dat.get("value"))
                    except Exception: continue
                    out[iid][t] = v
        except Exception as e:
            print("bad file", path, e, flush=True)
    _cache[path] = out
    while len(_cache) > 4: _cache.popitem(last=False)
    return out
def ticks_for(iid, lo, hi):
    d = {}
    for h in sorted({hour_file(s) for s in range(lo, hi + 1, 1800)} | {hour_file(lo), hour_file(hi)}):
        d.update({t: v for t, v in load_hour(h).get(iid, {}).items() if lo <= t <= hi})
    return d

def conf_yes(ticks, close_s, now_s, strike, sigma, digits):
    part = settlewin.partial(ticks, close_s, now_s)
    if part is None: return None
    locked, r = part
    ks = [k for k in ticks if k <= now_s]
    if not ks: return None
    spot = ticks[max(ks)]
    if now_s - max(ks) > 2: return None
    K = pinrun.eff_strike(strike, digits)
    mu = (locked + r * spot) / settlewin.N_AVG
    if r <= 0: return 1.0 if mu >= K else 0.0
    sd = float(sigma) * math.sqrt(var_factor(int(r), [1.0]))
    if sd <= 0: return 1.0 if mu >= K else 0.0
    return pinrun.conf_of((mu - K) / sd)

rows = []
n = 0
for tk, f in sorted(fills.items(), key=lambda x: x[1]["close_s"] or 0):
    n += 1
    r = dict(f)
    ok = all(f.get(k) is not None for k in ("close_s", "iid", "strike", "sigma", "fair_logged"))
    if not ok:
        r["status"] = "no_signal_fields"; rows.append(r); continue
    cs = int(f["close_s"]); ent = int(math.floor(f["t_send"]))
    ticks = ticks_for(f["iid"], cs - 70, ent + 1)
    if not ticks:
        r["status"] = "no_tape"; rows.append(r); continue
    fy_now = conf_yes(ticks, cs, ent, f["strike"], f["sigma"], f["digits"])
    fy_prev = conf_yes(ticks, cs, ent - 1, f["strike"], f["sigma"], f["digits"])
    if fy_now is None or fy_prev is None:
        r["status"] = "tape_gap"; rows.append(r); continue
    r["fair_rebuilt"] = round(fy_now, 5)
    r["fair_prev"] = round(fy_prev, 5)
    r["match"] = abs(fy_now - float(f["fair_logged"]))
    ours_prev = fy_prev if f["want"] == "yes" else 1.0 - fy_prev
    r["prev_conf"] = round(ours_prev, 5)
    r["spike"] = bool(ours_prev < 0.90 and (f["tau"] or 99) > 5)
    r["cap"] = bool(f["edge"] is not None and f["edge"] > 10.0)
    r["status"] = "ok" if r["match"] < 0.02 else "mismatch"
    rows.append(r)
    if n % 100 == 0: print("...", n, flush=True)

with open(OUT, "w", encoding="utf-8") as fh:
    for r in rows: fh.write(json.dumps(r) + "\n")
st = collections.Counter(r["status"] for r in rows)
print("status:", dict(st), flush=True)
ok = [r for r in rows if r["status"] == "ok"]
print("matched the logged fair within 0.02 on %d of %d rebuilt" % (len(ok), sum(1 for r in rows if r["status"] in ("ok", "mismatch"))))
def summ(sel, label):
    n = len(sel); l = [r for r in sel if r["pnl"] < 0]; w = [r for r in sel if r["pnl"] >= 0]
    print("  %-34s %4d markets | losers %2d (%+9.2f) | winners %3d (%+9.2f) | net %+9.2f" % (label, n, len(l), sum(r["pnl"] for r in l), len(w), sum(r["pnl"] for r in w), sum(r["pnl"] for r in sel)))
print("\nWHOLE RECORD, rebuilt rows only:")
summ(ok, "all")
summ([r for r in ok if r["spike"]], "SPIKE would refuse")
summ([r for r in ok if r["cap"]], "EDGE CAP would refuse")
summ([r for r in ok if r["spike"] or r["cap"]], "EITHER would refuse")
summ([r for r in ok if not (r["spike"] or r["cap"])], "KEPT under the new rules")
print("\nevery LOSING market, rebuilt:")
for r in sorted(ok, key=lambda x: x["close_s"]):
    if r["pnl"] < 0:
        print("  %s ET %-6s %-3s tau %2s fair %.4f prev %.4f edge %5.1fc  %s%s  %+8.2f" % (
            time.strftime("%m-%d %I:%M%p", time.gmtime(r["close_s"] - 4 * 3600)), r["tk"].split("-")[0][2:-3], r["want"], r["tau"],
            r["fair_rebuilt"], r["prev_conf"], r["edge"] or 0, "SPIKE " if r["spike"] else "      ", "CAP" if r["cap"] else "   ", r["pnl"]))
print("\nlosses NOT rebuilt (no tape / gap / mismatch):")
for r in rows:
    if r["status"] != "ok" and r["pnl"] < 0:
        print("  %s %-6s %s %+.2f" % (time.strftime("%m-%d %I:%M%p", time.gmtime((r["close_s"] or 0) - 4 * 3600)), r["tk"].split("-")[0][2:-3], r["status"], r["pnl"]))
