"""Pot math on OUR live fills only (the ledger-joined rows in live_markets.jsonl).
Independent of the agents' tables: a second way of thinking about the same rows.
  1. per price bucket: loss probability posterior (Jeffreys Beta(0.5,0.5)), avg win $/market, avg loss $/market,
     expected $/market and the break-even loss rate; last-14-day and all-time.
  2. cluster bootstrap BY CLOSE (markets at one close share the outcome) of the daily money -> 30-day
     distribution: expected $/30d, P(30 days < 0), 5th percentile.
  3. what-ifs: a gate that removes a fraction f_L of losing markets and f_W of winning markets.
Self-test: a planted world where the answer is known (loss rate 5/100, win $1, loss $30 -> EV = -0.55/market).
"""
import json, random, sys, collections, math, calendar, time, os

OUT = os.path.dirname(os.path.abspath(__file__))

def beta_ci(k, n, lo=0.025, hi=0.975, draws=20000, seed=3):
    rnd = random.Random(seed)
    xs = sorted(rnd.betavariate(k + 0.5, n - k + 0.5) for _ in range(draws))
    return xs[int(lo * draws)], xs[int(hi * draws)], (k + 0.5) / (n + 1.0)

def bucket_price(p):
    if p is None: return "?"
    c = p * 100 if p <= 1 else p
    for lo, hi, name in ((0, 90, "<90"), (90, 93, "90-93"), (93, 95, "93-95"), (95, 96, "95-96"), (96, 97, "96-97"), (97, 98, "97-98"), (98, 101, ">=98")):
        if lo <= c < hi: return name
    return "?"

def table(rows, label):
    by = collections.defaultdict(list)
    for r in rows: by[bucket_price(r["price"])].append(r)
    print("\n%s: %d markets, net %+.2f, %d lost" % (label, len(rows), sum(r["money"] for r in rows), sum(r["money"] < 0 for r in rows)))
    print("  %-7s %5s %4s %-24s %9s %9s %9s %10s" % ("price", "mk", "lost", "loss/100 [95% CI]", "avg win$", "avg loss$", "EV$/mk", "break-even"))
    for b in ("<90", "90-93", "93-95", "95-96", "96-97", "97-98", ">=98", "?"):
        xs = by.get(b)
        if not xs: continue
        L = [r for r in xs if r["money"] < 0]; W = [r for r in xs if r["money"] >= 0]
        k, n = len(L), len(xs)
        lo, hi, m = beta_ci(k, n)
        aw = sum(r["money"] for r in W) / max(1, len(W)); al = sum(r["money"] for r in L) / max(1, len(L))
        ev = sum(r["money"] for r in xs) / n
        be = aw / (aw - al) * 100 if al < 0 else float("nan")   # loss rate per 100 at which EV = 0
        print("  %-7s %5d %4d %5.1f [%4.1f, %5.1f]       %9.2f %9.2f %9.2f %7.1f/100" % (b, n, k, 100 * m, 100 * lo, 100 * hi, aw, al, ev, be))

def close_key(r):
    return r.get("close") or r["ticker"].split("-")[1]

def bootstrap_30d(rows, label, draws=4000, seed=5):
    rnd = random.Random(seed)
    days = collections.defaultdict(lambda: collections.defaultdict(float))
    for r in rows: days[r["etday"]][close_key(r)] += r["money"]
    full = [d for d in days if d not in (min(days), max(days))]   # drop the partial first/last days
    if len(full) < 3:
        print("\n%s: only %d full days, no bootstrap" % (label, len(full))); return
    per_day = [list(days[d].values()) for d in full]
    rate = sum(len(x) for x in per_day) / len(per_day)
    tot = []
    for _ in range(draws):
        s = 0.0
        for _d in range(30):
            closes = rnd.choice(per_day)                       # a random day's closes, resampled with replacement
            s += sum(rnd.choice(closes) for _ in range(len(closes)))
        tot.append(s)
    tot.sort()
    print("\n%s: %d full days, %.0f closes/day traded; 30-day money: mean %+.0f, 5th pct %+.0f, median %+.0f, P(<0) %.0f/100"
          % (label, len(full), rate, sum(tot) / draws, tot[int(0.05 * draws)], tot[draws // 2], 100 * sum(t < 0 for t in tot) / draws))

def whatif(rows, label):
    L = [r["money"] for r in rows if r["money"] < 0]; W = [r["money"] for r in rows if r["money"] >= 0]
    n = len(rows); days = len(set(r["etday"] for r in rows)) or 1
    print("\n%s what-ifs (per day): base %+.2f/day over %d days" % (label, sum(L + W) / days, days))
    for fL in (0.25, 0.5, 0.75):
        for fW in (0.0, 0.1, 0.2, 0.3, 0.4):
            print("  remove %2.0f%% of losses and %2.0f%% of wins -> %+7.2f/day" % (100 * fL, 100 * fW, ((1 - fL) * sum(L) + (1 - fW) * sum(W)) / days))

def load(path):
    rows = []
    for l in open(path, encoding="utf-8"):
        d = json.loads(l)
        if d.get("money") is None or not d.get("in_main_table") or not d.get("traded"): continue
        ff = d.get("first_fill") or {}
        rows.append({"ticker": d["ticker"], "money": float(d["money"]), "price": ff.get("price"),
                     "etday": d.get("et_day") or d.get("etday"), "close": d.get("close_utc") or d.get("close")})
    return rows

def selftest():
    rnd = random.Random(1)
    rows = []
    for i in range(4000):
        lost = (i % 20) == 0                      # exactly 5 per 100, planted, so the EV is exact
        rows.append({"ticker": "KXT-%06d-00" % i, "money": -30.0 if lost else 1.0, "price": 0.965, "etday": "d%02d" % (i // 100), "close": "c%d" % i})
    by = [r for r in rows]
    ev = sum(r["money"] for r in by) / len(by)
    assert abs(ev - (-0.55)) < 1e-9, ev
    lo, hi, m = beta_ci(sum(r["money"] < 0 for r in by), len(by))
    assert lo < 0.05 < hi, (lo, hi)
    aw, al = 1.0, -30.0
    assert abs(aw / (aw - al) * 100 - 3.2258) < 1e-3
    empty = [{"ticker": "KXT-%06d-00" % i, "money": 1.0, "price": 0.965, "etday": "d%02d" % (i // 100), "close": "c%d" % i} for i in range(400)]
    lo, hi, m = beta_ci(0, 400)
    assert hi < 0.01, hi        # a world with nothing planted does not get a loss rate
    print("selftest ok")

if __name__ == "__main__":
    selftest()
    if len(sys.argv) > 1:
        rows = load(sys.argv[1])
        rows.sort(key=lambda r: r["etday"] or "")
        table(rows, "ALL TIME")
        last = sorted(set(r["etday"] for r in rows if r["etday"]))[-14:]
        r14 = [r for r in rows if r["etday"] in last]
        table(r14, "LAST 14 ET DAYS (%s..%s)" % (last[0], last[-1]))
        bootstrap_30d(rows, "ALL TIME"); bootstrap_30d(r14, "LAST 14 DAYS")
        whatif(r14, "LAST 14 DAYS")
