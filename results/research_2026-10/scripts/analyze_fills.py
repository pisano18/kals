"""Which decision-time facts separate our LOSING fills from our winning ones -- on our own live fills only
(live_markets.jsonl, Kalshi money). n = markets. In-sample: every threshold here was chosen after seeing
the losses, so a rule's gain is an upper bound until it is pre-registered and watched live.
Self-test: a planted world where exactly the markets with edge > 4c lose -> the edge rule removes every
loss and no winner; an empty world (no losses) -> no rule shows a gain."""
import json, sys, os, collections, random

OUT = os.path.dirname(os.path.abspath(__file__))

def load(path):
    rows = []
    for l in open(path, encoding="utf-8"):
        d = json.loads(l)
        if not d.get("in_main_table") or not d.get("traded") or d.get("money") is None: continue
        ff = d.get("first_fill")
        if not ff: continue
        r = dict(ff)
        r.update(ticker=d["ticker"], coin=d["coin"], money=float(d["money"]), etday=d["et_day"], hour=d["hour_et"],
                 weekday=d["weekday"], version=(d.get("version") or {}).get("name"), bet_count=d.get("bet_count"),
                 bet_cost=d.get("bet_cost"), result_class=d.get("result_class"), lost=float(d["money"]) < 0)
        rows.append(r)
    return rows

def cell(xs):
    n = len(xs); k = sum(r["lost"] for r in xs); net = sum(r["money"] for r in xs)
    return "%5d mk %3d lost (%4.1f/100) net %+9.2f" % (n, k, 100.0 * k / n if n else 0, net)

def by(rows, key, order=None, title=""):
    g = collections.defaultdict(list)
    for r in rows: g[key(r)].append(r)
    ks = order or sorted(g, key=lambda k: (k is None, str(k)))
    print("\n" + title)
    for k in ks:
        if k in g: print("  %-14s %s" % (k, cell(g[k])))

def tau_b(r):
    t = r.get("tau")
    if t is None: return None
    return "<=10" if t <= 10 else "11-20" if t <= 20 else "21-30" if t <= 30 else "31-45" if t <= 45 else ">45"

def price_b(r):
    p = r.get("price")
    if p is None: return None
    c = p * 100
    return "<90" if c < 90 else "90-93" if c < 93 else "93-95" if c < 95 else "95-96" if c < 96 else "96-97" if c < 97 else "97-98" if c < 98 else ">=98"

def edge_b(r):
    e = r.get("edge_c")
    if e is None: return None
    return "<=1.5" if e <= 1.5 else "1.5-2.5" if e <= 2.5 else "2.5-4" if e <= 4 else "4-7" if e <= 7 else "7-15" if e <= 15 else ">15"

def under_b(r):
    a, p = r.get("ask_seen"), r.get("price")
    if a is None or p is None: return None
    u = (a - p) * 100          # positive = filled BELOW the ask we saw (the book had moved down)
    return "above ask" if u < -0.5 else "at ask" if u <= 0.5 else "0.5-3c under" if u < 3 else ">=3c under"

RULES = {
    "R1 edge>4c at tau>=20":            lambda r: (r.get("edge_c") or 0) > 4 and (r.get("tau") or 0) >= 20,
    "R1b edge>3c at tau>=20":           lambda r: (r.get("edge_c") or 0) > 3 and (r.get("tau") or 0) >= 20,
    "R2 price<95c at tau>=20":          lambda r: (r.get("price") or 1) < 0.95 and (r.get("tau") or 0) >= 20,
    "R3 no 21-30s first leg":           lambda r: 20 < (r.get("tau") or 0) <= 30,
    "R4 seller: share>0.55&age<500":    lambda r: r.get("sell_share_3s") is not None and r["sell_share_3s"] > 0.55 and (r.get("level_age_ms") or 9e9) < 500 and (r.get("tau") or 0) >= 20,
    "R4b seller: taker_n>3000 tau>=20": lambda r: r.get("taker_n_3s") is not None and r["taker_n_3s"] > 3000 and (r.get("tau") or 0) >= 20,
    "R4c seller any-tau share>0.55&age<500": lambda r: r.get("sell_share_3s") is not None and r["sell_share_3s"] > 0.55 and (r.get("level_age_ms") or 9e9) < 500,
    "R5 Saturday off":                  lambda r: r.get("weekday") == "Sat",
    "R6 BTC off":                       lambda r: r.get("coin") == "BTC",
    "R7 >=3c under seen ask (not preventable by a limit)": lambda r: r.get("ask_seen") is not None and r.get("price") is not None and (r["ask_seen"] - r["price"]) * 100 >= 3,
}
RULES["R8 = R1 + R2 + R4"] = lambda r: RULES["R1 edge>4c at tau>=20"](r) or RULES["R2 price<95c at tau>=20"](r) or RULES["R4 seller: share>0.55&age<500"](r)
RULES["R9 = R1b + R2 + R4c"] = lambda r: RULES["R1b edge>3c at tau>=20"](r) or RULES["R2 price<95c at tau>=20"](r) or RULES["R4c seller any-tau share>0.55&age<500"](r)

def rules(rows, title):
    days = sorted(set(r["etday"] for r in rows)); nd = max(1, len(days))
    base = sum(r["money"] for r in rows)
    print("\n%s: %d markets, %d ET days, net %+.2f (%+.2f/day), %d lost" % (title, len(rows), nd, base, base / nd, sum(r["lost"] for r in rows)))
    print("  %-52s %7s %5s %10s %10s | %8s %8s" % ("rule (markets it would have REFUSED)", "refused", "lost", "$ refused", "net after", "1st half", "2nd half"))
    half = days[len(days) // 2]
    for name, f in RULES.items():
        hit = [r for r in rows if f(r)]
        if not hit: continue
        h1 = sum(r["money"] for r in hit if r["etday"] < half); h2 = sum(r["money"] for r in hit if r["etday"] >= half)
        print("  %-52s %7d %5d %+10.2f %+10.2f | %+8.2f %+8.2f" % (name, len(hit), sum(r["lost"] for r in hit), sum(r["money"] for r in hit), base - sum(r["money"] for r in hit), -h1, -h2))
    print("  ($ refused = money those markets made; negative means the rule would have SAVED that much. 1st/2nd half = the saving in each half of the days)")

def selftest():
    rnd = random.Random(2)
    rows = []
    for i in range(600):
        e = rnd.choice([1.0, 2.0, 3.5, 5.0, 8.0])
        rows.append({"edge_c": e, "tau": 25, "price": 0.97, "money": -40.0 if e > 4 else 1.5, "lost": e > 4, "etday": "d%02d" % (i % 10),
                     "weekday": "Mon", "coin": "ETH", "ask_seen": 0.97, "sell_share_3s": None, "level_age_ms": 100, "taker_n_3s": None, "ticker": "t%d" % i})
    f = RULES["R1 edge>4c at tau>=20"]
    hit = [r for r in rows if f(r)]
    assert all(r["lost"] for r in hit) and sum(r["lost"] for r in rows) == len(hit), "planted rule must catch every loss and no winner"
    empty = [dict(r, money=1.5, lost=False) for r in rows]
    for name, g in RULES.items():
        assert sum(r["money"] for r in empty if g(r)) >= 0, name + " shows a gain in a world with no losses"
    print("selftest ok")

if __name__ == "__main__":
    selftest()
    rows = load(sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT, "live_markets.jsonl"))
    rows.sort(key=lambda r: r["etday"])
    print("loaded %d filled main-table markets, %s..%s" % (len(rows), rows[0]["etday"], rows[-1]["etday"]))
    by(rows, tau_b, ["<=10", "11-20", "21-30", "31-45", ">45", None], "A) tau of first fill (all-time)")
    for tb in ("<=10", "11-20", "21-30", "31-45"):
        by([r for r in rows if tau_b(r) == tb], price_b, ["<90", "90-93", "93-95", "95-96", "96-97", "97-98", ">=98"], "   price of first fill | tau " + tb)
    by(rows, edge_b, ["<=1.5", "1.5-2.5", "2.5-4", "4-7", "7-15", ">15", None], "B) edge (fair - price, cents) of first fill, all-time")
    by([r for r in rows if (r.get("tau") or 0) >= 20], edge_b, ["<=1.5", "1.5-2.5", "2.5-4", "4-7", "7-15", ">15", None], "   edge | tau >= 20")
    by([r for r in rows if (r.get("tau") or 0) < 20], edge_b, ["<=1.5", "1.5-2.5", "2.5-4", "4-7", "7-15", ">15", None], "   edge | tau < 20")
    by(rows, under_b, ["above ask", "at ask", "0.5-3c under", ">=3c under", None], "C) fill price vs the ask the bot saw")
    tf = [r for r in rows if r.get("sell_share_3s") is not None]
    print("\nD) trade-feed fields present: %d markets, %s.. (%d lost)" % (len(tf), tf[0]["etday"] if tf else "-", sum(r["lost"] for r in tf)))
    by(tf, lambda r: "share>0.55" if r["sell_share_3s"] > 0.55 else "share<=0.55", None, "   taker sell share, last 3 s")
    by(tf, lambda r: "taker_n>3000" if (r.get("taker_n_3s") or 0) > 3000 else "taker_n<=3000", None, "   taker contracts, last 3 s")
    by(tf, lambda r: "age<500ms" if (r.get("level_age_ms") or 9e9) < 500 else "age>=500ms", None, "   age of the offer level")
    by(rows, lambda r: "age<500ms" if (r.get("level_age_ms") or 9e9) < 500 else "age>=500ms" if r.get("level_age_ms") is not None else None, None, "   age of the offer level, all rows")
    by(rows, lambda r: r["weekday"], ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "E) weekday (ET)")
    by(rows, lambda r: "%02d" % r["hour"], None, "   hour of day (ET)")
    by(rows, lambda r: r["coin"], None, "   coin")
    recent = [r for r in rows if r["etday"] >= "2026-09-24"]
    by(recent, tau_b, ["<=10", "11-20", "21-30", "31-45", ">45", None], "A2) tau of first fill, since 09-24")
    by(recent, lambda r: r.get("leg"), None, "    first leg type, since 09-24")
    print("\nG) every LOSS since 09-24 and which rule flags it (x):")
    names = list(RULES)
    print("  %-26s %7s %5s %4s %5s %5s %6s %5s  %s" % ("ticker", "$", "price", "tau", "edge", "share", "age_ms", "leg", " ".join("R%d" % (i + 1) for i in range(len(names)))))
    for r in sorted((r for r in recent if r["lost"]), key=lambda r: r["money"]):
        print("  %-26s %7.2f %5.1f %4s %5.1f %5s %6s %5s  %s" % (r["ticker"][:26], r["money"], (r.get("price") or 0) * 100, r.get("tau"), r.get("edge_c") or 0,
              ("%.2f" % r["sell_share_3s"]) if r.get("sell_share_3s") is not None else "-", r.get("level_age_ms") if r.get("level_age_ms") is not None else "-", r.get("leg"),
              "  ".join("x" if f(r) else "." for f in RULES.values())))
    print("  (columns R1..R%d in the order of the RULES table)" % len(names))
    RULES["R10 = R8 + R3"] = lambda r: RULES["R8 = R1 + R2 + R4"](r) or RULES["R3 no 21-30s first leg"](r)
    RULES["R11 = R4 only on the FULL leg"] = lambda r: RULES["R4 seller: share>0.55&age<500"](r) and r.get("leg") == "full"
    RULES["R12 = R4 only on the EARLY leg"] = lambda r: RULES["R4 seller: share>0.55&age<500"](r) and r.get("leg") == "early"
    RULES["R13 = R1 + R4"] = lambda r: RULES["R1 edge>4c at tau>=20"](r) or RULES["R4 seller: share>0.55&age<500"](r)
    RULES["R14 edge>5c at tau>=20"] = lambda r: (r.get("edge_c") or 0) > 5 and (r.get("tau") or 0) >= 20
    RULES["R15 seller share>=0.5&age<500 tau>=20 (twin's parameters)"] = lambda r: r.get("sell_share_3s") is not None and r["sell_share_3s"] >= 0.5 and (r.get("level_age_ms") or 9e9) < 500 and (r.get("tau") or 0) >= 20
    RULES["R16 = R14 + R15"] = lambda r: RULES["R14 edge>5c at tau>=20"](r) or RULES["R15 seller share>=0.5&age<500 tau>=20 (twin's parameters)"](r)
    RULES["R17 = R14 + R15 + under-ask>=3c"] = lambda r: RULES["R16 = R14 + R15"](r) or RULES["R7 >=3c under seen ask (not preventable by a limit)"](r)
    rules(rows, "F) RULES, all-time")
    last = sorted(set(r["etday"] for r in rows))[-14:]
    rules([r for r in rows if r["etday"] in last], "F) RULES, last 14 ET days")
    rules([r for r in rows if r["etday"] >= "2026-09-24"], "F) RULES, since 09-24 (trade-feed era)")
