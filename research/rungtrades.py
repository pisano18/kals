"""rungtrades.py -- READ-ONLY: how much far-rung SAFE-SIDE supply was actually
TAKEN on Kalshi's hourly BTC ladder in the last 45 s of each close.

Why: results/FAR_RUNG_2026-09-25.md section 2a found no safe-side offer at all
at the two overnight closes. The recorder does not record KXBTCD books, so past
depth is not on disk -- but Kalshi's /markets/trades history is. A contract a
taker BOUGHT on the safe side at 97-99c inside the last 45 s is a lower bound
on the supply that existed (it says nothing about what rested and was not
taken, and nothing about whether WE would have been first).

Cushion without the index: rungs settle YES below the settlement and NO above,
so the settlement lies between the highest YES strike (K_y) and the lowest NO
strike (K_n), $100 apart. A YES rung at K is at least K_y - K from the
settlement; a NO rung at least K - K_n. That LOWER bound is what is banded;
the true cushion is up to $100 more. Cushion vs the SETTLEMENT, not the
projection at the trade -- the largest 45-s miss in 2,136 closes was $136
(section 1), so a $250+ band is >= $114 from the projection at every trade.

    python research/rungtrades.py --selftest
    python research/rungtrades.py --days 2026-09-22 2026-09-23 2026-09-24

GET only, through research/kauth.py. Writes results/rungtrades-<days>.json.
"""
import argparse, calendar, collections, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(os.path.dirname(HERE), "results")
BANDS = [(100, 150), (150, 250), (250, 400), (400, 700), (700, 10**9)]
WINDOW_S = 45
MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()


def et_offset(close_s):
    """EDT (-4) from the 2nd Sunday of March to the 1st Sunday of November."""
    y = time.gmtime(close_s).tm_year
    def nth_sunday(month, n):
        d = calendar.timegm((y, month, 1, 0, 0, 0))
        wd = time.gmtime(d).tm_wday          # Mon=0
        first = d + ((6 - wd) % 7) * 86400
        return first + (n - 1) * 7 * 86400
    start = nth_sunday(3, 2) + 7 * 3600      # 2 AM EST = 07:00Z
    end = nth_sunday(11, 1) + 6 * 3600       # 2 AM EDT = 06:00Z
    return -4 if start <= close_s < end else -5


def event_ticker(close_s):
    t = time.gmtime(close_s + et_offset(close_s) * 3600)
    return "KXBTCD-%02d%s%02d%02d" % (t.tm_year % 100, MONTHS[t.tm_mon - 1], t.tm_mday, t.tm_hour)


def strike_of(m):
    v = m.get("floor_strike")
    if v in (None, ""):
        v = (m.get("custom_strike") or {}).get("floor_strike")
    return None if v in (None, "") else float(v)


def boundary(markets):
    """(K_y, K_n) from settled rungs, or None if the results do not bracket."""
    ys = [strike_of(m) for m in markets if m.get("result") == "yes" and strike_of(m) is not None]
    ns = [strike_of(m) for m in markets if m.get("result") == "no" and strike_of(m) is not None]
    if not ys or not ns:
        return None
    ky, kn = max(ys), min(ns)
    if ky >= kn:
        return None                            # results not monotone: refuse
    return ky, kn


def safe_side(k, ky, kn):
    """('yes'|'no', lower-bound cushion) for a rung, or None inside the bracket."""
    if k <= ky:
        return "yes", ky - k
    if k >= kn:
        return "no", k - kn
    return None


def band_of(c):
    for lo, hi in BANDS:
        if lo <= c < hi:
            return "%d-%s" % (lo, "up" if hi > 10**8 else hi)
    return None


def taken(trades, side, close_s, window_s=WINDOW_S):
    """Contracts a taker BOUGHT on `side`, by price cent, inside the window."""
    out = collections.Counter()
    for t in trades:
        ts = t.get("created_time") or ""
        try:
            sec = calendar.timegm(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            continue
        if not (close_s - window_s <= sec < close_s):
            continue
        if t.get("taker_side") != side:
            continue
        px = float(t.get("yes_price_dollars" if side == "yes" else "no_price_dollars") or 0)
        out[round(px, 2)] += float(t.get("count_fp") or t.get("count") or 0)
    return out


def tally(closes):
    """closes: list of {close_s, rungs: [{k, side, cush, taken: Counter}]} ->
    per band: closes seen, closes with any >=97c take, contracts at 97/98/99."""
    agg = collections.defaultdict(lambda: {"rung_closes": 0, "closes": set(),
                                            "closes_with_take": set(),
                                            "c97": 0.0, "c98": 0.0, "c99": 0.0})
    for c in closes:
        for r in c["rungs"]:
            b = band_of(r["cush"])
            if b is None:
                continue
            a = agg[b]
            a["rung_closes"] += 1
            a["closes"].add(c["close_s"])
            for px, n in r["taken"].items():
                if px >= 0.97 - 1e-9:
                    a["closes_with_take"].add(c["close_s"])
                    key = "c%d" % int(round(px * 100))
                    if key in a:
                        a[key] += n
    return {b: {"rung_closes": a["rung_closes"], "closes": len(a["closes"]),
                "closes_with_take": len(a["closes_with_take"]),
                "c97": round(a["c97"], 2), "c98": round(a["c98"], 2), "c99": round(a["c99"], 2)}
            for b, a in agg.items()}


# ------------------------------------------------------------------ network
def fetch_event(get, ev):
    rows, cursor = [], None
    for _ in range(3):
        p = {"event_ticker": ev, "limit": "200"}
        if cursor:
            p["cursor"] = cursor
        st, body = get("/markets", p)
        if st != 200 or not isinstance(body, dict):
            return None
        rows += body.get("markets") or []
        cursor = body.get("cursor")
        if not cursor:
            break
    return rows


def fetch_trades(get, tk, close_s, window_s):
    out, cursor = [], None
    for _ in range(20):
        p = {"ticker": tk, "min_ts": str(close_s - window_s - 5), "max_ts": str(close_s + 1), "limit": "1000"}
        if cursor:
            p["cursor"] = cursor
        st, body = get("/markets/trades", p)
        if st != 200 or not isinstance(body, dict):
            return None
        out += body.get("trades") or []
        cursor = body.get("cursor")
        if not cursor:
            break
        time.sleep(0.05)
    return out


def run(days, get, band_max=700, sleep=0.05, log=print):
    closes, misses = [], []
    for d in days:
        y, mo, da = (int(x) for x in d.split("-"))
        # every UTC hour whose close falls on this ET calendar day
        noon = calendar.timegm((y, mo, da, 16, 0, 0))
        off = et_offset(noon)
        day0 = calendar.timegm((y, mo, da, 0, 0, 0)) - off * 3600   # ET midnight in UTC
        for h in range(1, 25):
            close_s = day0 + h * 3600
            ev = event_ticker(close_s)
            rows = fetch_event(get, ev)
            time.sleep(sleep)
            if not rows:
                misses.append((ev, "no markets"))
                continue
            br = boundary(rows)
            if br is None:
                misses.append((ev, "no bracket (unsettled or not monotone)"))
                continue
            ky, kn = br
            rungs = []
            for m in rows:
                k = strike_of(m)
                if k is None:
                    continue
                ss = safe_side(k, ky, kn)
                if ss is None or not (100 <= ss[1] <= band_max):
                    continue
                tr = fetch_trades(get, m["ticker"], close_s, WINDOW_S)
                time.sleep(sleep)
                if tr is None:
                    misses.append((m["ticker"], "trades GET failed"))
                    continue
                rungs.append({"tk": m["ticker"], "k": k, "side": ss[0], "cush": ss[1],
                              "taken": taken(tr, ss[0], close_s)})
            closes.append({"close_s": close_s, "event": ev, "ky": ky, "kn": kn, "rungs": rungs})
            tot = sum(n for r in rungs for px, n in r["taken"].items() if px >= 0.97 - 1e-9)
            log("%s  %s  bracket %.2f-%.2f  rungs %d  taken >=97c: %.0f"
                % (time.strftime("%m-%d %H:%MZ", time.gmtime(close_s)), ev, ky, kn, len(rungs), tot))
    return closes, misses


# ----------------------------------------------------------------- selftest
def selftest():
    fails = []
    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)
    ck(event_ticker(calendar.timegm((2026, 9, 25, 3, 0, 0))) == "KXBTCD-26SEP2423",
       "03:00Z Sep 25 is the 11 PM ET Sep 24 event (read live)")
    ck(event_ticker(calendar.timegm((2026, 9, 24, 17, 0, 0))) == "KXBTCD-26SEP2413",
       "17:00Z is the 1 PM ET event (the live bot's T84499.99 refusal at 16:59Z)")
    ck(event_ticker(calendar.timegm((2026, 1, 15, 18, 0, 0))) == "KXBTCD-26JAN1513",
       "January is EST: 18:00Z is 1 PM ET")
    mk = [{"floor_strike": k, "result": ("yes" if k < 84200 else "no")} for k in
          (83799.99, 83899.99, 83999.99, 84099.99, 84199.99, 84299.99, 84399.99, 84499.99)]
    ck(boundary(mk) == (84199.99, 84299.99), "bracket from settled rungs")
    ck(boundary([{"floor_strike": 1.0, "result": "no"}, {"floor_strike": 2.0, "result": "yes"}]) is None,
       "NULL: non-monotone results are refused, not banded")
    ck(boundary([{"floor_strike": 1.0, "result": ""}]) is None, "NULL: unsettled -> None")
    ck(safe_side(83899.99, 84199.99, 84299.99) == ("yes", 300.0)
       and safe_side(84499.99, 84199.99, 84299.99) == ("no", 200.0)
       and safe_side(84250.0, 84199.99, 84299.99) is None, "safe side and lower-bound cushion")
    ck(strike_of({"floor_strike": None, "custom_strike": {"floor_strike": "0.0949999"}}) == 0.0949999,
       "DOGE-shaped custom strike read")
    close = calendar.timegm((2026, 9, 24, 17, 0, 0))
    tr = [
        {"created_time": "2026-09-24T16:59:30.1Z", "taker_side": "no", "no_price_dollars": "0.9900", "yes_price_dollars": "0.0100", "count_fp": "50.00"},
        {"created_time": "2026-09-24T16:59:31.1Z", "taker_side": "no", "no_price_dollars": "0.9800", "yes_price_dollars": "0.0200", "count_fp": "7.00"},
        {"created_time": "2026-09-24T16:59:32.1Z", "taker_side": "yes", "no_price_dollars": "0.9900", "yes_price_dollars": "0.0100", "count_fp": "900.00"},
        {"created_time": "2026-09-24T16:58:00.0Z", "taker_side": "no", "no_price_dollars": "0.9900", "yes_price_dollars": "0.0100", "count_fp": "1000.00"},
        {"created_time": "2026-09-24T17:00:00.5Z", "taker_side": "no", "no_price_dollars": "0.9900", "yes_price_dollars": "0.0100", "count_fp": "1000.00"},
    ]
    t = taken(tr, "no", close)
    ck(t == collections.Counter({0.99: 50.0, 0.98: 7.0}),
       "taken: only takers BUYING the safe side, inside the last 45 s -- the 1c "
       "lottery buyer, the 16:58 trade and the post-close trade are not supply (%s)" % dict(t))
    tl = tally([{"close_s": close, "rungs": [{"cush": 300.0, "taken": t},
                                              {"cush": 120.0, "taken": collections.Counter()}]}])
    ck(tl["250-400"] == {"rung_closes": 1, "closes": 1, "closes_with_take": 1, "c97": 0.0, "c98": 7.0, "c99": 50.0}
       and tl["100-150"]["closes_with_take"] == 0, "tally by band (%s)" % tl)
    # a fake network drives run() end to end
    def fake_get(path, p):
        if path == "/markets":
            if p["event_ticker"] != "KXBTCD-26SEP2413":
                return 200, {"markets": []}
            return 200, {"markets": [{"ticker": "KXBTCD-26SEP2413-T%.2f" % k, "floor_strike": k,
                                      "result": ("yes" if k < 84200 else "no")}
                                     for k in (83699.99, 83999.99, 84199.99, 84299.99, 84599.99)]}
        if path == "/markets/trades":
            return 200, {"trades": tr if p["ticker"].endswith("84599.99") else []}
        return 404, None
    cl, miss = run(["2026-09-24"], fake_get, sleep=0, log=lambda *a: None)
    ok = [c for c in cl if c["event"] == "KXBTCD-26SEP2413"]
    ck(len(ok) == 1 and sorted(r["k"] for r in ok[0]["rungs"]) == [83699.99, 83999.99, 84599.99]
       and len(miss) == 23,
       "run(): the one listed event is banded (rungs 100+ from the bracket), the other 23 hours are "
       "reported as misses, not silently dropped (%d misses)" % len(miss))
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    ck("kauth" in src and "urlopen" not in src.replace('"urlopen"', "") and "POST" not in src.replace('"POST"', ""),
       "GET only: the network is kauth.get")
    print("SELF-TEST", "PASSED" if not fails else "FAILED (%d)" % len(fails))
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--days", nargs="+", default=[])
    a = ap.parse_args()
    ok = selftest()
    if a.selftest or not ok:
        sys.exit(0 if ok else 1)
    sys.path.insert(0, HERE)
    import kauth
    closes, misses = run(a.days, kauth.get)
    tl = tally(closes)
    print("\nper band (lower-bound cushion from the settlement), last %d s:" % WINDOW_S)
    print("band      closes  closes-with->=97c-take  contracts@97  @98  @99")
    for b in sorted(tl, key=lambda s: int(s.split("-")[0])):
        v = tl[b]
        print("%-9s %6d  %22d  %12.0f  %4.0f  %5.0f" % (b, v["closes"], v["closes_with_take"], v["c97"], v["c98"], v["c99"]))
    print("misses:", len(misses), misses[:6])
    out = os.path.join(RESULTS, "rungtrades-%s.json" % "_".join(a.days))
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"days": a.days, "window_s": WINDOW_S, "tally": tl, "misses": misses,
                   "closes": [dict(c, rungs=[dict(r, taken={str(k): v for k, v in r["taken"].items()})
                                             for r in c["rungs"]]) for c in closes]}, f, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
