"""scan_poly_ws_report.py -- real-time Polymarket US book (scan_poly_ws.jsonl.gz,
full MARKET_DATA frames with local rx time) joined second-by-second to Kalshi's
KXBTC15M ticker channel on the collector tape (yes_bid/ask + sizes, _rx_ms) and
to the BRTI tape (projected settle). For every second inside the last 120 s of
each closed 15m window:
  winner side (>= 10 bps margin), the winner's best ask + size on each venue,
  the cross-venue package cost incl. both taker fees, and the lag: when Kalshi's
  touch moved by >= 5c, how many seconds until Polymarket's moved the same way.
Read-only. Tolerant of files still being written.
"""
import gzip, json, os, sys, time, calendar, collections, bisect, glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"C:\kals-repo\research")
import gzsalvage  # noqa: E402

TAPE = r"C:\kals\kalshi_data"
WS = os.path.join(HERE, "scan_poly_ws.jsonl.gz")


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load_ws():
    books = collections.defaultdict(list)     # slug -> [(rx, best_bid, bid_sz, best_ask, ask_sz, bids, asks)]
    trades = collections.defaultdict(list)
    n = 0
    try:
        with gzip.open(WS, "rt", encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                    fr = json.loads(r["f"])
                except Exception:
                    continue
                n += 1
                md = fr.get("marketData")
                if md:
                    bids = sorted(((f(x["px"]["value"]), f(x["qty"])) for x in md.get("bids") or []), reverse=True)
                    asks = sorted(((f(x["px"]["value"]), f(x["qty"])) for x in md.get("offers") or md.get("asks") or []))
                    books[md["marketSlug"]].append((r["rx"], bids[0][0] if bids else None, bids[0][1] if bids else 0,
                                                    asks[0][0] if asks else None, asks[0][1] if asks else 0, bids[:5], asks[:5]))
                tr = fr.get("trade")
                if tr:
                    trades[tr["marketSlug"]].append((r["rx"], f(tr["price"]["value"]), f(tr["quantity"]["value"]),
                                                     (tr.get("taker") or {}).get("intent")))
    except EOFError:
        pass
    return books, trades, n


def slug_close(slug):
    st = calendar.timegm(time.strptime(slug.split("-15m-")[1], "%Y-%m-%d-%H%Mz"))
    return st + 900


def kalshi_ticker(close):
    """[(rx_s, yes_bid, yes_bid_sz, yes_ask, yes_ask_sz)] for the KXBTC15M market closing at `close`."""
    et = time.gmtime(close - 4 * 3600)   # ticker encodes Eastern; EDT in September
    tk = "KXBTC15M-%02d%s%02d%02d%02d-" % (et.tm_year % 100, time.strftime("%b", et).upper(), et.tm_mday, et.tm_hour, et.tm_min)
    out = []
    for dt in (-3600, 0):
        h = time.strftime("%Y%m%dT%H", time.gmtime(close - 1 + dt))
        fn = os.path.join(TAPE, "ticker", h + ".jsonl.gz")
        if not os.path.exists(fn):
            continue
        for line in gzsalvage.iter_lines(fn):
            if tk not in line:
                continue
            try:
                r = json.loads(line)
                m = r["msg"]
                if not m["market_ticker"].startswith(tk):
                    continue
                out.append((r["_rx_ms"] / 1000.0, f(m["yes_bid_dollars"]), f(m["yes_bid_size_fp"]), f(m["yes_ask_dollars"]), f(m["yes_ask_size_fp"])))
            except Exception:
                continue
    out.sort()
    return out


def brti(close):
    d = {}
    for dt in (-3600, 0):
        h = time.strftime("%Y%m%dT%H", time.gmtime(close - 1 + dt))
        fn = os.path.join(TAPE, "cfbenchmarks_value", h + ".jsonl.gz")
        if not os.path.exists(fn):
            continue
        for line in gzsalvage.iter_lines(fn):
            if '"BRTI"' not in line:
                continue
            try:
                m = json.loads(line)["msg"]
                if m["index_id"] != "BRTI":
                    continue
                dd = json.loads(m["data"])
                d[int(dd["time"]) // 1000] = float(dd["value"])
            except Exception:
                continue
    return d


def fee_k(p):
    return 0.07 * p * (1 - p)


def fee_p(p):
    return 0.0695 * p * (1 - p)


def main():
    books, trades, n = load_ws()
    print("ws frames:", n, "slugs with books:", {k: len(v) for k, v in books.items()})
    now = time.time()
    done = [s for s in books if "-15m-" in s and slug_close(s) < now - 30]
    bands = [(0, 20), (21, 45), (46, 90), (91, 120)]
    agg = collections.defaultdict(lambda: collections.defaultdict(float))
    lags = []
    for slug in sorted(done):
        close = slug_close(slug)
        kt = kalshi_ticker(close)
        bx = brti(close)
        bts = sorted(bx)
        pb = books[slug]
        pts = [b[0] for b in pb]
        kts = [k[0] for k in kt]
        if not kt or not bts:
            print(slug, "missing kalshi ticker or brti on tape", len(kt), len(bts))
            continue
        strike = None
        # strike: the previous window's settle = mean of the 60 BRTI prints ending at close-900
        prev = [bx[t] for t in bts if close - 960 < t <= close - 900]
        if len(prev) >= 55:
            strike = round(sum(prev) / len(prev), 2)
        if strike is None:
            print(slug, "no strike from tape")
            continue
        print("\n== %s close %s strike %.2f | poly frames %d trades %d | kalshi ticker rows %d" % (
            slug, time.strftime("%H:%M:%SZ", time.gmtime(close)), strike, len(pb), len(trades.get(slug, [])), len(kt)))
        print("   tau  proj-K(bps) | Poly bid/ask (sz)      | Kalshi bid/ask (sz)     | winner ask P / K | package")
        for sec in range(close - 120, close + 1):
            tau = close - sec
            j = bisect.bisect_right(bts, sec)
            if j == 0:
                continue
            spot = bx[bts[j - 1]]
            locked = [bx[t] for t in bts[bisect.bisect_right(bts, close - 60):j] if close - 60 < t <= close]
            proj = (sum(locked) + (60 - len(locked)) * spot) / 60.0
            margin = (proj - strike) / strike * 1e4
            jp = bisect.bisect_right(pts, sec + 0.999) - 1
            jk = bisect.bisect_right(kts, sec + 0.999) - 1
            if jp < 0 or jk < 0:
                continue
            _, pbb, pbs, pba, pas, _, _ = pb[jp]
            _, kbb, kbs, kba, kas = kt[jk]
            win_yes = proj >= strike
            p_win = (pba, pas) if win_yes else ((round(1 - pbb, 4), pbs) if pbb is not None else (None, 0))
            k_win = (kba, kas) if win_yes else ((round(1 - kbb, 4), kbs) if kbb is not None else (None, 0))
            pkg = None
            if None not in (pbb, pba, kbb, kba):
                c1 = kba + (1 - pbb) + fee_k(kba) + fee_p(pbb)
                c2 = pba + (1 - kbb) + fee_p(pba) + fee_k(kbb)
                pkg = min(c1, c2)
            band = next((b for b in bands if b[0] <= tau <= b[1]), None)
            if band and abs(margin) >= 10:
                a = agg[band]
                a["n"] += 1
                if p_win[0] is not None and p_win[0] <= 0.98:
                    a["p_le98"] += 1
                    a["p_le98_sz"] += p_win[1] or 0
                if k_win[0] is not None and k_win[0] <= 0.98:
                    a["k_le98"] += 1
                    a["k_le98_sz"] += k_win[1] or 0
                if pkg is not None:
                    a["pkg_n"] += 1
                    if pkg < 1.0:
                        a["pkg_lt1"] += 1
                        a["pkg_edge_c"] += (1 - pkg) * 100
            if tau % 5 == 0 or tau <= 20:
                print("   %3d  %+8.1f     | %s/%s (%s/%s) | %s/%s (%s/%s) | %s / %s | %s" % (
                    tau, margin, pbb, pba, int(pbs or 0), int(pas or 0), kbb, kba, int(kbs or 0), int(kas or 0),
                    p_win[0], k_win[0], ("%.4f" % pkg) if pkg is not None else "-"))
        # lag: Kalshi touch mid moves >= 5c between consecutive seconds -> seconds until Poly mid moves >= 3c same direction
        for sec in range(close - 120, close):
            jk0 = bisect.bisect_right(kts, sec + 0.999) - 1
            jk1 = bisect.bisect_right(kts, sec - 0.001) - 1
            if jk0 < 0 or jk1 < 0:
                continue
            k0, k1 = kt[jk1], kt[jk0]
            if None in (k0[1], k0[3], k1[1], k1[3]):
                continue
            dm = (k1[1] + k1[3]) / 2 - (k0[1] + k0[3]) / 2
            if abs(dm) < 0.05:
                continue
            jp0 = bisect.bisect_right(pts, sec - 0.001) - 1
            if jp0 < 0 or None in (pb[jp0][1], pb[jp0][3]):
                continue
            pm0 = (pb[jp0][1] + pb[jp0][3]) / 2
            lag = None
            for b in pb[jp0 + 1:]:
                if b[1] is None or b[3] is None:
                    continue
                if (b[1] + b[3]) / 2 - pm0 >= 0.03 if dm > 0 else pm0 - (b[1] + b[3]) / 2 >= 0.03:
                    lag = b[0] - k1[0]
                    break
            lags.append((slug[-9:], close - sec, round(dm, 3), None if lag is None else round(lag, 2)))
    print("\nSUMMARY over closed windows, seconds with >= 10 bps margin:")
    print("band     n   P_win<=98 (avg sz)   K_win<=98 (avg sz)   pkg_n  pkg<1  avg edge c when <1")
    for b in bands:
        a = agg.get(b)
        if not a:
            continue
        print("%-7s %4d   %5d (%6.0f)        %5d (%6.0f)        %5d  %5d  %s" % (
            "%d-%ds" % b, a["n"], a["p_le98"], a["p_le98_sz"] / a["p_le98"] if a["p_le98"] else 0,
            a["k_le98"], a["k_le98_sz"] / a["k_le98"] if a["k_le98"] else 0, a["pkg_n"], a["pkg_lt1"],
            ("%.2f" % (a["pkg_edge_c"] / a["pkg_lt1"])) if a["pkg_lt1"] else "-"))
    print("\nKalshi >=5c mid jumps inside 120 s and Polymarket's lag to follow (s), None = did not follow within the recording:")
    for l in lags[:40]:
        print("  ", l)
    fl = [l[3] for l in lags if l[3] is not None]
    if fl:
        fl.sort()
        print("  followed %d of %d; lag median %.2f s, p90 %.2f s" % (len(fl), len(lags), fl[len(fl) // 2], fl[int(len(fl) * 0.9)]))


if __name__ == "__main__":
    main()
