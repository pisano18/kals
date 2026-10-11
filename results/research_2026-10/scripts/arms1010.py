"""Final reads for the paper arms toxic15 / toxic0 / norebuy vs arm-live-twin (2026-10-03 .. now). Paper money only:
per-market money = sum of settled pnl_c/100. Shared window = after the later start and before the earlier last record."""
import json, collections, calendar, time
R = r"C:\kals-repo\results\\"
ARMS = {"toxic15": ["pinrun-paper-20261003T050709Z.jsonl"], "toxic0": ["pinrun-paper-20261003T050810Z.jsonl"],
        "norebuy": ["pinrun-paper-20261003T050909Z.jsonl"],
        "twin": ["pinrun-paper-20260929T185918Z.jsonl", "pinrun-paper-20261006T185948Z.jsonl"]}
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
def close_of(tk):
    s = tk.split("-")[1]
    return calendar.timegm((2000 + int(s[0:2]), MON[s[2:5]], int(s[5:7]), int(s[7:9]), int(s[9:11]) if len(s) >= 11 else 0, 0)) + 4 * 3600
def T(s): return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))
def etday(e): return time.strftime("%m-%d", time.gmtime(e - 4 * 3600))
data = {}
for arm, fns in ARMS.items():
    money = collections.defaultdict(float); refused = collections.defaultdict(list); first = last = None; rebuy = set()
    for fn in fns:
        for l in open(R + fn, encoding="utf-8"):
            if '"kind": "settled"' not in l and '"kind": "refused"' not in l and '"kind": "loop"' not in l and '"kind": "order"' not in l:
                continue
            try: d = json.loads(l)
            except Exception: continue
            t = d.get("t")
            if t:
                e = T(t); first = e if first is None else min(first, e); last = e if last is None else max(last, e)
            k = d.get("kind")
            if k == "settled" and d.get("ticker") and "15M-" in d["ticker"] and "CRYPTOLEAD" not in d["ticker"]:
                money[d["ticker"]] += float(d.get("pnl_c") or 0) / 100.0
            elif k == "refused" and d.get("gate") == "toxic_fresh":
                refused[d["ticker"]].append(d.get("tau"))
            elif k == "order" and d.get("leg") in ("rebuy", "a68", "rebuy_hedged") :
                rebuy.add(d.get("ticker"))
    data[arm] = dict(money=money, refused=refused, first=first, last=last)
tw = data["twin"]
for arm in ("toxic15", "toxic0", "norebuy"):
    a = data[arm]
    lo, hi = max(a["first"], tw["first"]), min(a["last"], tw["last"])
    keys = {k for k in set(a["money"]) | set(tw["money"]) if lo + 60 <= close_of(k) <= hi - 60}
    am = sum(a["money"].get(k, 0) for k in keys); tm = sum(tw["money"].get(k, 0) for k in keys)
    days = collections.defaultdict(lambda: [0.0, 0.0])
    for k in keys:
        dd = etday(close_of(k)); days[dd][0] += a["money"].get(k, 0); days[dd][1] += tw["money"].get(k, 0)
    cum = 0.0; worst = 0.0; line = []
    for dd in sorted(days):
        cum += days[dd][0] - days[dd][1]; worst = min(worst, cum); line.append("%s %+.2f" % (dd, cum))
    print("%-8s window %s..%s ET  arm %+.2f vs twin %+.2f (diff %+.2f), arm lost %d, twin lost %d; cum diff by day: %s; worst %+.2f" % (
        arm, time.strftime("%m-%d %H:%M", time.gmtime(lo - 4 * 3600)), time.strftime("%m-%d %H:%M", time.gmtime(hi - 4 * 3600)),
        am, tm, am - tm, sum(a["money"].get(k, 0) < 0 for k in keys), sum(tw["money"].get(k, 0) < 0 for k in keys), ", ".join(line), worst))
    if arm.startswith("toxic"):
        inside = {k: v for k, v in a["refused"].items() if k in keys and any(x is not None and x <= 20 for x in v)}
        twin_bought = {k: tw["money"][k] for k in inside if k in tw["money"]}
        won = sum(1 for v in twin_bought.values() if v >= 0); lost = sum(1 for v in twin_bought.values() if v < 0)
        print("   refused at <=20 s: %d markets; twin bought %d of them: won %d (+%.2f), lost %d (%.2f)" % (
            len(inside), len(twin_bought), won, sum(v for v in twin_bought.values() if v >= 0), lost, sum(v for v in twin_bought.values() if v < 0)))
