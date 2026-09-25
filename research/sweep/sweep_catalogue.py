"""sweep_catalogue.py -- build the market catalogue the money-idea sweep reads.

READ-ONLY (GET via research/kauth.py). Enumerates every open Kalshi market,
aggregates per series, joins GET /series (settlement sources, frequency, fee),
and writes one plain-text file per category that an agent can read cheaply:

    .sweep/catalogue/INDEX.txt              category | series | 24h volume | ...
    .sweep/catalogue/cat_<Category>.txt     one line per series, by 24h volume
    .sweep/catalogue/series.json            the per-series aggregates

Run from the repo root:

    python research/sweep/sweep_catalogue.py --selftest
    python research/sweep/sweep_catalogue.py              # ~5-15 min without parlays
    python research/sweep/sweep_catalogue.py --with-mve   # ~45 min, adds 4.7M parlay markets
    python research/sweep/sweep_catalogue.py --max-pages 3   # smoke test

Changes from the 2026-09-24 scratch version (scan_enum.py + build_catalogue.py):
- multi-leg combination ("MVE"/parlay) markets are skipped by default: they
  were 4.7M of 5.7M rows and 80% of the 45-minute run, and the per-series
  table excluded them anyway. `--with-mve` counts them per collection.
- the raw per-market dump (236 MB) is not written unless `--keep-markets`.
- output lives in .sweep/ (gitignored), not a session temp folder.
"""
import argparse, collections, gzip, json, os, sys, time, calendar

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(REPO, ".sweep", "catalogue")
sys.path.insert(0, os.path.join(REPO, "research"))
MIN_GAP = 0.1
_last = [0.0]


def get(path, params=None):
    import kauth
    gap = time.time() - _last[0]
    if gap < MIN_GAP:
        time.sleep(MIN_GAP - gap)
    _last[0] = time.time()
    st, b = None, None
    for attempt in range(4):
        st, b = kauth.get(path, params)
        if st == 200:
            return st, b
        time.sleep(1.5 * (attempt + 1))
    return st, b


def epoch(ts):
    try:
        return calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
    except Exception:
        return None


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def new_agg(series):
    return {"series": series, "n_open": 0, "events": set(), "closes": set(), "v24": 0.0,
            "oi": 0.0, "next_close": None, "closes_24h": set(), "closes_7d": set(),
            "sample": None, "sample_v24": -1.0, "n_two_sided": 0}


def add_market(agg, m, now):
    """Fold one /markets row into the per-series aggregate. Returns the series."""
    tk = m.get("ticker") or ""
    ev = m.get("event_ticker") or ""
    series = ev.split("-")[0] if ev else tk.split("-")[0]
    a = agg.get(series)
    if a is None:
        a = agg[series] = new_agg(series)
    a["n_open"] += 1
    a["events"].add(ev)
    ct = epoch(m.get("close_time") or "")
    if ct:
        a["closes"].add(ct)
        if a["next_close"] is None or ct < a["next_close"]:
            a["next_close"] = ct
        if ct - now < 86400:
            a["closes_24h"].add(ct)
        if ct - now < 7 * 86400:
            a["closes_7d"].add(ct)
    v24 = f(m.get("volume_24h_fp")) or 0.0
    a["v24"] += v24
    a["oi"] += f(m.get("open_interest_fp")) or 0.0
    yb, ya = f(m.get("yes_bid_dollars")), f(m.get("yes_ask_dollars"))
    if ya and yb and 0 < yb < ya < 1:
        a["n_two_sided"] += 1
    if v24 > a["sample_v24"]:
        a["sample_v24"] = v24
        a["sample"] = {"t": tk, "title": (m.get("title") or "")[:160],
                       "rules": (m.get("rules_primary") or "")[:600], "ct": m.get("close_time"),
                       "sts": m.get("settlement_timer_seconds"), "cce": m.get("can_close_early")}
    return series


def finish(agg, meta, mve_counts):
    rows = []
    for s, a in agg.items():
        rows.append(dict({"series": s, "n_open": a["n_open"], "n_events": len(a["events"]),
                          "closes_24h": len(a["closes_24h"]), "closes_7d": len(a["closes_7d"]),
                          "next_close": a["next_close"], "v24": a["v24"], "oi": a["oi"],
                          "n_two_sided": a["n_two_sided"], "sample": a["sample"],
                          "mve_markets": mve_counts.get(s, 0)}, **meta.get(s, {})))
    rows.sort(key=lambda r: -(r["v24"] or 0))
    return rows


def line(r):
    sm = r.get("sample") or {}
    src = ",".join((x or {}).get("name", "") for x in (r.get("settlement_sources") or []))
    return " | ".join(str(x) for x in (
        r["series"], r.get("title"), r.get("frequency"), int(r.get("v24") or 0), int(r.get("oi") or 0),
        r.get("n_open"), r.get("closes_7d"), r.get("n_two_sided"),
        "%s x%s" % (r.get("fee_type"), r.get("fee_multiplier")), src[:80],
        sm.get("t"), (sm.get("rules") or "").replace("\n", " ")[:220]))


def write_catalogue(rows, out_dir, stamp):
    os.makedirs(out_dir, exist_ok=True)
    by = collections.defaultdict(list)
    for r in rows:
        by[r.get("category") or "Unknown"].append(r)
    summary = []
    for cat, rs in sorted(by.items()):
        fn = "cat_%s.txt" % "".join(ch if ch.isalnum() else "_" for ch in cat)
        with open(os.path.join(out_dir, fn), "w", encoding="utf-8") as fh:
            fh.write("# Kalshi series in category %r, read %s. Sorted by 24h volume (contracts).\n" % (cat, stamp))
            fh.write("# series | title | freq | v24 | open_interest | n_open | closes_7d | two_sided | "
                     "fee_type x mult | settlement sources | sample ticker | sample rules\n")
            for r in rs:
                fh.write(line(r) + "\n")
        summary.append((cat, len(rs), int(sum(r.get("v24") or 0 for r in rs)), fn))
    with open(os.path.join(out_dir, "INDEX.txt"), "w", encoding="utf-8") as fh:
        fh.write("# read %s\ncategory | series | 24h volume | file\n" % stamp)
        for s in sorted(summary, key=lambda s: -s[2]):
            fh.write(" | ".join(str(x) for x in s) + "\n")
    return summary


def build(get_fn, with_mve=False, max_pages=None, keep_markets=None, log=print):
    now = time.time()
    st, b = get_fn("/series", {"limit": "5000"})
    meta = {}
    if st == 200 and isinstance(b, dict):
        for s in b.get("series") or []:
            meta[s["ticker"]] = {k: s.get(k) for k in ("frequency", "title", "category", "tags",
                                                        "settlement_sources", "fee_type", "fee_multiplier")}
    log("series meta: %d (status %s)" % (len(meta), st))
    agg, mve_counts, pages, n, cursor = {}, collections.Counter(), 0, 0, None
    raw = gzip.open(keep_markets, "wt", encoding="utf-8") if keep_markets else None
    try:
        while True:
            p = {"status": "open", "limit": "1000"}
            if not with_mve:
                p["mve_filter"] = "exclude"
            if cursor:
                p["cursor"] = cursor
            st, b = get_fn("/markets", p)
            pages += 1
            if st != 200 or not isinstance(b, dict):
                log("page %d http %s %s" % (pages, st, str(b)[:200]))
                break
            ms = b.get("markets") or []
            for m in ms:
                n += 1
                if raw:
                    raw.write(json.dumps(m, separators=(",", ":")) + "\n")
                if m.get("mve_collection_ticker"):
                    mve_counts[m.get("mve_collection_ticker")] += 1
                    continue
                add_market(agg, m, now)
            cursor = b.get("cursor")
            if pages % 20 == 0:
                log("pages %d markets %d series %d" % (pages, n, len(agg)))
            if not cursor or not ms or (max_pages and pages >= max_pages):
                break
    finally:
        if raw:
            raw.close()
    return finish(agg, meta, mve_counts), {"markets": n, "pages": pages, "mve": sum(mve_counts.values())}


def selftest():
    fails = []
    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)
    now = time.time()
    close = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + 3600))
    pages = [
        {"markets": [
            {"ticker": "KXRAIN-A-1", "event_ticker": "KXRAIN-A", "close_time": close, "volume_24h_fp": "10",
             "open_interest_fp": "5", "yes_bid_dollars": "0.40", "yes_ask_dollars": "0.45", "title": "rain", "rules_primary": "r"},
            {"ticker": "KXMVE-X", "event_ticker": "KXMVE-X", "mve_collection_ticker": "KXMVECOLL", "close_time": close}],
         "cursor": "c1"},
        {"markets": [{"ticker": "KXRAIN-B-1", "event_ticker": "KXRAIN-B", "close_time": close, "volume_24h_fp": "30",
                      "yes_bid_dollars": "0", "yes_ask_dollars": "0.02"}], "cursor": None},
    ]
    calls = []
    def fake(path, p):
        calls.append((path, dict(p or {})))
        if path == "/series":
            return 200, {"series": [{"ticker": "KXRAIN", "category": "Climate and Weather", "title": "Rain",
                                     "frequency": "daily", "fee_type": "quadratic", "fee_multiplier": 1,
                                     "settlement_sources": [{"name": "NWS"}]}]}
        return 200, pages[0 if "cursor" not in p else 1]
    rows, info = build(fake, log=lambda *a: None)
    r = {x["series"]: x for x in rows}
    ck(set(r) == {"KXRAIN"} and r["KXRAIN"]["n_open"] == 2 and r["KXRAIN"]["n_events"] == 2
       and r["KXRAIN"]["v24"] == 40.0 and r["KXRAIN"]["n_two_sided"] == 1
       and r["KXRAIN"]["closes_24h"] == 1 and r["KXRAIN"]["category"] == "Climate and Weather",
       "aggregates two pages into one series; the one-sided market is not two-sided (%s)" % r.get("KXRAIN"))
    ck(info == {"markets": 3, "pages": 2, "mve": 1},
       "the parlay row is counted, not aggregated (%s)" % info)
    ck(all(c[1].get("mve_filter") == "exclude" for c in calls if c[0] == "/markets"),
       "default asks the API to exclude parlays")
    rows2, info2 = build(fake, with_mve=True, max_pages=1, log=lambda *a: None)
    ck(info2["pages"] == 1 and all("mve_filter" not in c[1] for c in calls[-1:]),
       "--max-pages stops early; --with-mve does not filter")
    import tempfile
    d = tempfile.mkdtemp()
    s = write_catalogue(rows, d, "test")
    txt = open(os.path.join(d, "cat_Climate_and_Weather.txt"), encoding="utf-8").read()
    ck(len(s) == 1 and "KXRAIN | Rain | daily | 40" in txt and os.path.exists(os.path.join(d, "INDEX.txt")),
       "catalogue files written")
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    ck("kauth.get" in src and "urlopen" not in src.replace('"urlopen"', ""), "GET only via kauth")
    print("SELF-TEST", "PASSED" if not fails else "FAILED (%d)" % len(fails))
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--with-mve", action="store_true")
    ap.add_argument("--max-pages", type=int, default=None)
    ap.add_argument("--keep-markets", action="store_true")
    a = ap.parse_args()
    ok = selftest()
    if a.selftest or not ok:
        sys.exit(0 if ok else 1)
    t0 = time.time()
    stamp = time.strftime("%Y-%m-%d %H:%MZ", time.gmtime())
    rows, info = build(get, with_mve=a.with_mve, max_pages=a.max_pages,
                       keep_markets=os.path.join(OUT, "markets.jsonl.gz") if a.keep_markets else None)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "series.json"), "w", encoding="utf-8") as fh:
        json.dump({"t": time.time(), "read": stamp, "info": info, "series": rows}, fh)
    summary = write_catalogue(rows, OUT, stamp)
    print("done: %d markets, %d pages, %d parlay rows skipped, %d series, %d categories, %.0fs -> %s"
          % (info["markets"], info["pages"], info["mve"], len(rows), len(summary), time.time() - t0, OUT))


if __name__ == "__main__":
    main()
