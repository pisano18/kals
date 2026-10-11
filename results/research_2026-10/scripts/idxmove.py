"""Whole-population check of the strongest raw-feed signal from loss_anatomy.md: "the settlement index moved
against our side over the last few seconds before the send". loss_anatomy measured it on 41 losers vs 117
matched winners; this measures it on EVERY filled main-table market (our own fills x the raw 1/sec index
feed, C:\\kals\\kalshi_data\\cfbenchmarks_value, read-only, streamed one hourly gz at a time).

For each market: s = the first filled order's send second. sd = realised sd of 1-s index changes over
[s-305, s-5]. A = (print[s-1] - print[s-4]) / sd signed so that + = AGAINST our side (strictly before the
send second -- always available to the bot). B = (print[s] - print[s-3]) / sd (includes the send second;
available only if the decision came after that print arrived, ~90 ms into the second). n = markets.
In-sample: thresholds are a grid, not fitted; the loss anatomy's own threshold (2 sd / 3 s) is one row.
Self-test: a planted world where markets with a planted 3-s move against them lose -> the rule at 2 sd
catches all of them and no winner; a world with no moves flags nothing."""
import json, gzip, re, os, sys, math, collections, time, calendar, random, zlib

OUT = os.path.dirname(os.path.abspath(__file__))
TAPE = r"C:\kals\kalshi_data\cfbenchmarks_value"
IID = {"BTC": "BRTI", "ETH": "ETHUSD_RTI", "SOL": "SOLUSD_RTI", "XRP": "XRPUSD_RTI", "DOGE": "DOGEUSD_RTI",
       "BNB": "BNBUSD_RTI", "HYPE": "HYPEUSD_RTI", "NEAR": "NEARUSD_RTI", "ZEC": "ZECUSD_RTI"}
RX_ID = re.compile(r'"index_id":"([A-Z_]+)"')
RX_TV = re.compile(r'\\"time\\":(\d+),.*?\\"value\\":\\"([0-9.]+)\\"')

def T(s):
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))

def moves(pr, s):
    """(sd, A, B, worst single 1-s move in the last 3 s) in raw price units; None if prints are missing."""
    xs = [pr.get(t) for t in range(s - 305, s + 1)]
    ch = [b - a for a, b in zip(xs[:-6], xs[1:-5]) if a is not None and b is not None]   # [s-305, s-5]
    if len(ch) < 200: return None
    m = sum(ch) / len(ch); sd = math.sqrt(sum((c - m) ** 2 for c in ch) / (len(ch) - 1))
    if sd <= 0: return None
    p = {k: pr.get(s - k) for k in range(0, 5)}
    if any(p[k] is None for k in (1, 4)): return None
    A = (p[1] - p[4])
    B = (p[0] - p[3]) if p[0] is not None and p[3] is not None else None
    one = [p[k] - p[k + 1] for k in range(1, 4) if p[k] is not None and p[k + 1] is not None]
    return sd, A, B, one

def score(rows, label):
    days = sorted(set(r["etday"] for r in rows)); nd = max(1, len(days)); half = days[len(days) // 2]
    base = sum(r["money"] for r in rows); L = sum(r["money"] < 0 for r in rows)
    print("\n%s: %d markets with index windows, %d ET days, net %+.2f (%+.2f/day), %d lost" % (label, len(rows), nd, base, base / nd, L))
    print("  %-34s %7s %5s %10s %10s %9s | %8s %8s" % ("refuse when the index moved against us", "refused", "lost", "$ refused", "net after", "/day after", "1st half", "2nd half"))
    for key in ("A", "B"):
        for th in (1.0, 1.5, 2.0, 2.5, 3.0):
            hit = [r for r in rows if r.get(key) is not None and r[key] >= th]
            if not hit: continue
            h1 = -sum(r["money"] for r in hit if r["etday"] < half); h2 = -sum(r["money"] for r in hit if r["etday"] >= half)
            ref = sum(r["money"] for r in hit)
            print("  %-34s %7d %5d %+10.2f %+10.2f %+9.2f | %+8.2f %+8.2f" % ("%s >= %.1f sd over 3 s" % (key, th), len(hit), sum(r["money"] < 0 for r in hit), ref, base - ref, (base - ref) / nd, h1, h2))
    print("  ($ refused = what those markets made; negative = the rule SAVES that much; halves = saving per half)")

def selftest():
    rnd = random.Random(4)
    pr = {}; rows = []
    v = 100.0
    for t in range(0, 20000):
        v += rnd.gauss(0, 1.0); pr[t] = v
    for i in range(40):
        s = 1000 + i * 400
        planted = i % 4 == 0
        if planted:                     # a 3-s move of 10.5 sd against a YES buyer, ending at s-1
            for k, t in enumerate(range(s - 3, s + 400)):
                pr[t] = pr[t] - 3.5 * min(k + 1, 3)
        m = moves(pr, s)
        sd, A, B, one = m
        rows.append({"A": -A / sd, "money": -50.0 if planted else 1.0})
    # NOTE: under a pure random walk a 3-s move is sqrt(3) = 1.73 one-second sd wide, so a 2-sd line
    # flags ~12% of unplanted markets by chance alone -- the test uses a line far outside the noise.
    caught = [r for r in rows if r["A"] >= 5.0]
    assert all(r["money"] < 0 for r in caught) and len(caught) == 10, (len(caught), [r["A"] for r in rows][:8])
    assert sum(1 for r in rows if r["money"] > 0 and r["A"] >= 2.0) <= 12, "noise flags far more than a random walk allows"
    flat = {t: 100.0 + 0.001 * ((t * 7919) % 13 - 6) for t in range(0, 2000)}
    sd, A, B, one = moves(flat, 1500)
    assert abs(A) / sd < 2.0
    print("selftest ok")

def main():
    selftest()
    mk = []
    for l in open(os.path.join(OUT, "live_markets.jsonl"), encoding="utf-8"):
        d = json.loads(l)
        if not d.get("in_main_table") or not d.get("traded") or d.get("money") is None: continue
        ff = d.get("first_fill")
        if not ff or d["coin"] not in IID: continue
        legs = [g for g in d.get("legs", []) if (g.get("filled") or 0) > 0]
        g0 = min(legs, key=lambda g: g["t"]) if legs else None
        if g0 is None: continue
        s = int(g0["t_ms_send"] // 1000) if g0.get("t_ms_send") else T(g0["t"])
        mk.append({"ticker": d["ticker"], "iid": IID[d["coin"]], "s": s, "want": ff.get("want") or d.get("want"),
                   "money": float(d["money"]), "etday": d["et_day"], "tau": ff.get("tau"), "price": ff.get("price"),
                   "bot_sigma": ff.get("sigma"), "leg": ff.get("leg")})
    need = collections.defaultdict(set)
    for m in mk:
        need[m["iid"]].update(range(m["s"] - 306, m["s"] + 1))
    hours = sorted(set(t // 3600 for v in need.values() for t in v))
    print("markets", len(mk), "index-hours to read", len(hours))
    pr = collections.defaultdict(dict); missing = []; torn = []
    t0 = time.time()
    for i, h in enumerate(hours):
        fn = os.path.join(TAPE, time.strftime("%Y%m%dT%H", time.gmtime(h * 3600)) + ".jsonl.gz")
        if not os.path.exists(fn): missing.append(os.path.basename(fn)); continue
        try:
            with gzip.open(fn, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    a = RX_ID.search(line)
                    if not a: continue
                    iid = a.group(1)
                    if iid not in need: continue
                    b = RX_TV.search(line)
                    if not b: continue
                    sec = int(b.group(1)) // 1000
                    if sec in need[iid]: pr[iid][sec] = float(b.group(2))
        except (EOFError, OSError, zlib.error):
            torn.append(os.path.basename(fn))      # read up to the tear; nothing after it is used
        if i % 100 == 0: print("  hour %d/%d  %.0f s" % (i, len(hours), time.time() - t0), flush=True)
    print("missing hour files", len(missing), missing[:6], "torn", len(torn), torn[:6])
    rows = []; nowin = 0
    for m in mk:
        r = moves(pr[m["iid"]], m["s"])
        if r is None: nowin += 1; continue
        sd, A, B, one = r
        sign = -1.0 if m["want"] == "yes" else 1.0           # + = against our side
        m["sd"] = sd; m["A"] = sign * A / sd; m["B"] = (sign * B / sd) if B is not None else None
        m["one_max"] = max([sign * x / sd for x in one]) if one else None
        rows.append(m)
    print("markets without a usable index window:", nowin)
    json.dump(rows, open(os.path.join(OUT, "idxmove_rows.json"), "w"))
    los = [r for r in rows if r["money"] < 0]
    print("losers with windows %d; A >= 2 sd: %d; A >= 1 sd: %d (loss_anatomy: 8 and 12 of 41 on its own window)" % (
        len(los), sum(r["A"] >= 2 for r in los), sum(r["A"] >= 1 for r in los)))
    score(rows, "ALL-TIME")
    score([r for r in rows if r["etday"] >= "2026-09-24"], "SINCE 09-24")
    score([r for r in rows if (r["tau"] or 0) > 20], "ALL-TIME, first fill > 20 s left")
    score([r for r in rows if (r["tau"] or 0) <= 20], "ALL-TIME, first fill <= 20 s left")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest": selftest()
    else: main()
