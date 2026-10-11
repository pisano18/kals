"""10-05 reads: revert-0925b / revert-0914 (arm vs twin vs live on shared closes) + the HYPE question.
Read-only; streams each log once, one at a time. Live money from Kalshi (scratchpad ledger_1009b.json)."""
import json, os, sys, calendar, time, collections, random
sys.path.insert(0, r"C:\kals-repo\research")
import pinledger
SP = os.path.dirname(os.path.abspath(__file__))
R = r"C:\kals-repo\results\\"
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
HY = ("KXHYPE15M-26OCT042015-15", "KXHYPE15M-26OCT050030-30")

def close_of(tk):
    s = tk.split("-")[1]
    yy, mo, dd = int(s[0:2]), MON[s[2:5]], int(s[5:7]); hh = int(s[7:9]); mm = int(s[9:11]) if len(s) >= 11 else 0
    return calendar.timegm((2000 + yy, mo, dd, hh, mm, 0)) + 4 * 3600
def T(s):
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))
def etday(e):
    return time.strftime("%Y-%m-%d", time.gmtime(e - 4 * 3600))
def et(e):
    return time.strftime("%m-%d %H:%M ET", time.gmtime(e - 4 * 3600))
def is_coin15(tk):
    ser = tk.split("-")[0]
    return ser.endswith("15M") and ser.startswith("KX") and ser not in ("KXCRYPTOLEAD15M", "KXCRYPTOCOMP15M", "KXGOLD15M", "KXWTI15M", "KXSILVER15M", "KXCOPPER15M", "KXNATGAS15M")

LOGS = {"live": ["pinrun-live-20261003T081552Z.jsonl", "pinrun-live-20261004T032252Z.jsonl", "pinrun-live-20261004T092040Z.jsonl", "pinrun-live-20261005T044615Z.jsonl", "pinrun-live-20261005T142402Z.jsonl", "pinrun-live-20261006T154122Z.jsonl", "pinrun-live-20261007T133039Z.jsonl"],
        "twin": ["pinrun-paper-20260929T185918Z.jsonl", "pinrun-paper-20261006T185948Z.jsonl"], "a0925b": ["pinrun-paper-20261004T003604Z.jsonl"], "a0914": ["pinrun-paper-20261004T031214Z.jsonl"]}
SK = ("code_sha", "size", "arm_name", "early_max_price", "early_min_price", "price_ceiling", "toxic_fresh", "max_full_bets", "one_full_bet", "hedge_belief", "mode")
info = {}
for who, fns in LOGS.items():
    I = {"up": set(), "settled": [], "hy": [], "trim": [], "logs": []}
    for fn in fns:
        first = last = None; start = None; closes = set(); odd = collections.Counter(); tail = []
        with open(R + fn, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                k = r.get("kind"); t = r.get("t")
                if isinstance(t, str):
                    first = first or t; last = t
                if k == "start" and start is None:
                    start = {x: r.get(x) for x in SK if x in r}
                elif k == "close_summary" and r.get("close"):
                    closes.add(int(r["close"]))
                elif k == "settled":
                    I["settled"].append((r.get("ticker"), r.get("want"), r.get("result"), r.get("cost"), r.get("pnl_c"), t))
                elif k == "full_cap_trim":
                    I["trim"].append(r)
                if r.get("ticker") in HY and k not in ("hedge_quote", "ladder", "watch", "unwatch", "universe"):
                    I["hy"].append({x: r.get(x) for x in ("t", "kind", "gate", "want", "side", "price", "tau", "take_n", "n", "filled", "status", "cost", "pnl_c", "leg", "entry", "belief", "fair", "edge_c", "level_age_ms", "sell_share_3s", "was", "now", "avg", "count", "why") if r.get(x) is not None})
                if k not in ("loop", "universe", "hedge_quote", "ladder", "refused", "watch", "unwatch", "close_summary", "signal", "settled", "order", "universe_deferred"):
                    odd[k] += 1
                tail.append((t, k)); tail = tail[-4:]
        f0 = T(first)
        I["up"] |= {c for c in closes if c - 60 >= f0}
        I["logs"].append((fn, first, last, start, dict(odd), tail))
    info[who] = I
    for L in I["logs"]:
        print(who, L[0], L[1], "->", L[2], L[3]); print("   kinds:", L[4]); print("   tail:", L[5])

# paper money per market
def paper(who):
    m = {}
    for tk, want, res, cost, pnl_c, t in info[who]["settled"]:
        if not tk or cost is None or pnl_c is None or not is_coin15(tk):
            continue
        pnl = pnl_c / 100.0; c = float(cost); f = 0.07 * c * (1 - c)
        per = ((1 - c) - f) if res == want else -(c + f)
        n = pnl / per if per else 0.0
        d = m.setdefault(tk, {"pnl": 0.0, "stake": 0.0, "close": close_of(tk), "n": 0.0, "legs": []})
        d["pnl"] += pnl; d["stake"] += max(n, 0) * c; d["n"] += n; d["legs"].append((want, round(c, 4), round(n, 1), round(pnl, 2)))
    return m
LED = json.load(open(os.path.join(SP, "ledger_1009b.json")))["settlements"]
def live_all():
    m = {}
    for s in LED.values():
        tk = s.get("ticker") or ""
        if not is_coin15(tk):
            continue
        try:
            c = close_of(tk)
        except Exception:
            continue
        put = pinledger.money(s, "yes_total_cost_dollars") + pinledger.money(s, "no_total_cost_dollars")
        m[tk] = {"pnl": pinledger.pnl(s), "stake": put, "close": c, "n": None, "legs": [], "settled_time": s.get("settled_time")}
    return m
M = {"live": live_all(), "twin": paper("twin"), "a0925b": paper("a0925b"), "a0914": paper("a0914")}

def summ(ms, closes):
    pnl = stake = 0.0; n = 0; losers = []
    for tk, d in ms.items():
        if d["close"] not in closes:
            continue
        pnl += d["pnl"]; stake += d["stake"]; n += 1
        if d["pnl"] < -0.005:
            losers.append((tk, round(d["pnl"], 2)))
    return {"pnl": round(pnl, 2), "stake": round(stake, 2), "pct": round(100 * pnl / stake, 2) if stake else None, "n": n,
            "nl": len(losers), "losers": sorted(losers, key=lambda x: x[1])}

OUT = {}
for arm in ("a0925b", "a0914"):
    sh = info[arm]["up"] & info["twin"]["up"] & info["live"]["up"]
    print("\n==== %s vs twin vs live: %d shared closes, %s .. %s" % (arm, len(sh), et(min(sh)), et(max(sh))))
    # closes missing per bot inside arm's span
    span = [c for c in range(min(sh), max(sh) + 1, 900)]
    for who in (arm, "twin", "live"):
        miss = [c for c in span if c not in info[who]["up"]]
        print("   %s down at %d closes in span: %s" % (who, len(miss), [et(c) for c in miss][:12]))
    days = sorted({etday(c) for c in sh}); res = {}
    for d in days + ["ALL"]:
        dc = {c for c in sh if d == "ALL" or etday(c) == d}
        row = {who: summ(M[who], dc) for who in (arm, "twin", "live")}
        res[d] = row; row["closes"] = len(dc)
        print("  %s (%d closes)" % (d, len(dc)))
        for who in (arm, "twin", "live"):
            x = row[who]
            print("     %-7s $%+8.2f bet $%8.2f (%+.2f%%) mk %3d lost %d %s" % (who, x["pnl"], x["stake"], x["pct"] or 0, x["n"], x["nl"], x["losers"]))
    # live losers -> arm
    print("  LIVE losing markets in shared window -> %s / twin" % arm)
    for tk, v in sorted(res["ALL"]["live"]["losers"], key=lambda x: x[1]):
        a = M[arm].get(tk); tw = M["twin"].get(tk)
        print("     %s live %+.2f | %s %s | twin %s" % (tk, v, arm, ("%+.2f n=%.1f legs=%s" % (a["pnl"], a["n"], a["legs"])) if a else "did not buy",
                                                        ("%+.2f n=%.1f legs=%s" % (tw["pnl"], tw["n"], tw["legs"])) if tw else "did not buy"))
    OUT[arm] = res
json.dump(OUT, open(os.path.join(SP, "rv1009b.json"), "w"), indent=1, default=str)


print("\n==== revert0925-live: main bot on Kalshi since the revert start 2026-10-04T03:22:52Z, per ET day of close")
def mainbot(tk):
    return is_coin15(tk) or tk.startswith("KXBTCD-")
REV = "2026-10-04T03:22:52"
day = collections.defaultdict(lambda: {"n": 0, "pnl": 0.0, "stake": 0.0, "lost": []})
tot = {"n": 0, "pnl": 0.0, "stake": 0.0}
for s in LED.values():
    tk = s.get("ticker") or ""
    if not mainbot(tk):
        continue
    try:
        c = close_of(tk)
    except Exception:
        continue
    if c < T(REV):
        continue
    p = pinledger.pnl(s); put = pinledger.money(s, "yes_total_cost_dollars") + pinledger.money(s, "no_total_cost_dollars")
    d = day[etday(c)]; d["n"] += 1; d["pnl"] += p; d["stake"] += put
    tot["n"] += 1; tot["pnl"] += p; tot["stake"] += put
    if p < -0.005:
        d["lost"].append((tk, round(p, 2)))
for k in sorted(day):
    d = day[k]
    print("  %s mk %3d net %+8.2f bet %8.2f (%+.2f%%) lost %d %s" % (k, d["n"], d["pnl"], d["stake"], 100 * d["pnl"] / d["stake"] if d["stake"] else 0, len(d["lost"]), sorted(d["lost"], key=lambda x: x[1])))
print("  TOTAL mk %d net %+.2f bet %.2f (%+.2f%%); vs bank at revert $1025.69: %+.2f%%" % (tot["n"], tot["pnl"], tot["stake"], 100 * tot["pnl"] / tot["stake"], 100 * tot["pnl"] / 1025.69))
race = sum(pinledger.pnl(s) for s in LED.values() if (s.get("ticker") or "").startswith("KXCRYPTOLEAD") and (s.get("settled_time") or "") >= REV)
print("  race legs in main account since revert (not the main bot): %+.2f" % race)
