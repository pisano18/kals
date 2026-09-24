"""Paper arms vs live, head to head on the SAME settled markets over closes both
were up for. Read-only. Money = the bot's own `settled.pnl_c` / 100 (the
`realised` field is a running day total, not the market's money).

Arm identity: a paper log's start record differs from live's start record of
the same moment in exactly the flag it carries (sync_arms.ps1), so logs are
grouped by that difference -- the arm-*.out files only name the CURRENT run."""
import json, glob, os, re, collections, calendar, time, sys
R = r"C:\kals-repo\results"
SINCE = sys.argv[1] if len(sys.argv) > 1 else "2026-09-20T14:23:00Z"
def ep(t): return calendar.timegm(time.strptime(t[:19], "%Y-%m-%dT%H:%M:%S"))
SINCE_E = ep(SINCE)
MON = {m: i for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}
def close_of(tk):
    s = tk.split("-")[1]
    return calendar.timegm((2000 + int(s[:2]), MON[s[2:5]], int(s[5:7]), int(s[7:9]), int(s[9:11]), 0)) + 4 * 3600
NOISE = {"t", "day_loss_at_start", "kind", "mode", "code_sha", "size", "minutes", "pid", "traj_file",
         "live", "paper", "log", "out", "arm_name", "attempts_on_send", "doubt_hist_tau_s",
         "doubt_mult", "traj_tau_max", "traj_every_s", "traj_near_tau_s", "hedge_belief_src"}
FLAG_KINDS = ("hedge", "hedge_alarm", "hedge_prop", "hedge_panic", "late_boost", "doubt_boost",
              "band_boost", "dumped", "spike", "edge_cap")

def load(p):
    settled = {}; lo = hi = None; kinds = collections.Counter(); start = None; gates = collections.Counter()
    try: fh = open(p, encoding="utf-8", errors="replace")
    except OSError: return None
    for line in fh:
        try: d = json.loads(line)
        except Exception: continue
        k = d.get("kind"); t = d.get("t")
        if t:
            e = ep(t); lo = e if lo is None else min(lo, e); hi = e if hi is None else max(hi, e)
        if k == "start" and start is None: start = d
        elif k == "settled":
            tk = d.get("ticker")
            if tk and d.get("pnl_c") is not None and t and ep(t) >= SINCE_E:
                settled[tk] = settled.get(tk, 0.0) + float(d["pnl_c"]) / 100.0
        elif k == "refused": gates[d.get("gate")] += 1
        if k: kinds[k] += 1
    return dict(settled=settled, lo=lo, hi=hi, kinds=kinds, start=start or {}, gates=gates, path=p)

live = [load(p) for p in sorted(glob.glob(os.path.join(R, "pinrun-live-2026092*.jsonl")))]
live = [x for x in live if x and x["start"] and x["hi"] and x["hi"] >= SINCE_E]
L = {}; Lspans = []
for x in live:
    L.update(x["settled"]); Lspans.append((x["lo"], x["hi"]))
def live_start_at(t):
    c = [x["start"] for x in live if x["lo"] and x["lo"] <= t + 120]
    return c[-1] if c else live[0]["start"]
def up(spans, c): return any(lo and lo <= c - 50 and hi and hi >= c for lo, hi in spans)
print("live: %d logs, %d settled markets since %s, money %+.2f (own log; Kalshi is the authority)" % (len(live), len(L), SINCE[:16], sum(L.values())))

# name the current runs from arm-*.out
cur_name = {}
for o in glob.glob(os.path.join(R, "arm-*.out")):
    nm = os.path.basename(o)[4:-4]
    try: txt = open(o, encoding="utf-8", errors="replace").read()
    except OSError: continue
    for s in re.findall(r"pinrun-paper-(2026\d{4}T\d{6}Z)\.jsonl", txt):
        cur_name[s] = nm

groups = collections.defaultdict(list)     # signature -> [log]
for p in sorted(glob.glob(os.path.join(R, "pinrun-paper-2026092*.jsonl"))):
    if os.path.basename(p) < "pinrun-paper-20260920T142347Z.jsonl": continue
    x = load(p)
    if not x or not x["start"] or not x["lo"]: continue
    ls = live_start_at(x["lo"])
    diff = tuple(sorted((k, json.dumps(x["start"].get(k)), json.dumps(ls.get(k))) for k in set(x["start"]) | set(ls)
                        if k not in NOISE and x["start"].get(k) != ls.get(k)))
    sig = tuple((k, a) for k, a, b in diff)
    x["diff"] = diff
    groups[sig].append(x)

rows = []
for sig, logs in groups.items():
    names = {cur_name.get(re.search(r"paper-(\d{8}T\d{6}Z)", x["path"]).group(1)) for x in logs} - {None}
    nm = ",".join(sorted(names)) if names else "?"
    A = {}; spans = []; kinds = collections.Counter(); gates = collections.Counter()
    for x in logs:
        A.update(x["settled"]); spans.append((x["lo"], x["hi"])); kinds.update(x["kinds"]); gates.update(x["gates"])
    common = [tk for tk in A if tk in L and up(spans, close_of(tk)) and up(Lspans, close_of(tk))]
    a_sum = sum(A[tk] for tk in common); l_sum = sum(L[tk] for tk in common)
    arm_only = [tk for tk in A if tk not in L and up(Lspans, close_of(tk)) and up(spans, close_of(tk))]
    live_only = [tk for tk in L if tk not in A and up(spans, close_of(tk)) and up(Lspans, close_of(tk))]
    fired = {k: kinds[k] for k in FLAG_KINDS if kinds.get(k)}
    hours = sum((hi - lo) for lo, hi in spans if lo and hi) / 3600.0
    ao = sum(A[t] for t in arm_only); lo_ = sum(L[t] for t in live_only)
    rows.append((nm, sig, len(logs), hours, len(common), a_sum, l_sum, len(arm_only), ao, len(live_only), lo_, fired, gates))
rows.sort(key=lambda r: -((r[5] - r[6]) + r[8] - r[10]))
print("\n%-16s %4s %5s | %4s %8s %8s %8s | %4s %8s | %4s %8s | total edge | flag / fired" % ("arm", "logs", "hours", "same", "arm$", "live$", "h2h", "+arm", "$", "+live", "$"))
for nm, sig, nl, hrs, n, a, l, nao, ao, nlo, lo_, fired, gates in rows:
    flag = " ".join("%s=%s" % (k, v) for k, v in sig)[:60]
    print("%-16s %4d %5.0f | %4d %+8.2f %+8.2f %+8.2f | %4d %+8.2f | %4d %+8.2f | %+8.2f | %s | %s" % (
        nm, nl, hrs, n, a, l, a - l, nao, ao, nlo, lo_, (a - l) + ao - lo_, flag, dict(fired) or "-"))
print("\nh2h = arm minus live on the SAME markets; +arm = markets only the arm took (its money), +live = markets only live took (live's money);")
print("total edge = h2h + arm-only money - live-only money = what the arm would have made over live on those closes, on its own paper log.")
