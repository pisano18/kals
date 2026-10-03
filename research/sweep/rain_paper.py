"""rain_paper.py -- PAPER bot for the SJ02 rain tail NO desk (IDEA_SWEEP_2026-10-02 / IDEA_LEDGER U10).

PAPER ONLY. This file sends GETs only: no order endpoint, no non-GET method, no money. The self-test
asserts that from the source text (the way research/cleanroom/locked_average_favourite_paper.py does).
Nothing here touches kalshi_data, feed_data or the tape; the only inputs are Kalshi's public market list,
one orderbook GET per eligible market, and api.weather.gov's hourly forecast.

What it does, every 5 minutes (the sweep's live rules, verbatim where they are numbers):
  * list the open KXRAIN markets (GET /markets?series_ticker=KXRAIN&status=open, paginated);
  * for each market whose close is 21.5-22.5 h away and not yet decided, read the book, record the
    YES-bid depth at 1-10c and at 3-10c and the NWS rain chance for that city/day (null when the city
    is not in the map); if the best YES bid is in the 3-10c rung and carries >= 25 contracts, paper-fill
    25 NO at 1 - yes_bid (a taker hitting that bid), fee per rain_candles.fee_c (0.07*p*(1-p)*lot,
    ceiled to the cent per order, spread over the lot) -- the SAME function, imported, not re-derived;
  * at most 2 cities per region and 6 cities a night (a night = the ET date the markets close on);
  * the forecast gate (rain chance > 20%) is RECORDED, not applied -- the bar asks what it would remove;
  * once a filled market settles (GET /markets/{ticker} result yes|no), book the result and the money.
A market whose best bid has no supply yet is re-checked on later scans inside its window (the first
refusal is logged, a later fill is logged, and a 'window passed' record closes it); a cap refusal is final.

Log: results/rain-paper.jsonl, one JSON object a line, UTC `t`, `type` in
  start(pid, argv, rules) | scan(n_open, n_eligible) | decision(ticker, city, region, close, yes_bid,
  depth_1_10, depth_3_10, pop, filled, why) | settled(ticker, result, pnl_c, day_total_c) | error.
Money fields: `pnl_c` is cents PER CONTRACT (rain_candles' arithmetic, so the bar's "net >= +1.5c at the
25-lot fill" is read straight off it); `pnl_lot_c` is the 25-lot total; `day_total_c` is the running
25-lot total for the ET day the market settled on.

    python research/sweep/rain_paper.py --selftest
    python research/sweep/rain_paper.py --once                  # one scan + settlement check, then exit
    python -u research/sweep/rain_paper.py --minutes 43200      # the 30-day paper log
results/rain-paper.stop makes a running instance exit at its next scan. On start the bot rebuilds its
open fills, the per-night caps and the day totals from the log, so a restart does not double-fill.
"""
import argparse
import collections
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, HERE)
import rain_candles  # noqa: E402  -- fee_c and LOT are reused, never re-derived

LOG = os.path.join(ROOT, "results", "rain-paper.jsonl")
STOP = os.path.join(ROOT, "results", "rain-paper.stop")
UTC = dt.timezone.utc
EPS = 1e-9
RULES = dict(series="KXRAIN", window_h=[21.5, 22.5], rung=[0.03, 0.10], lot=rain_candles.LOT, min_depth=25,
             max_cities_per_region=2, max_cities_per_night=6, pop_gate_pct=20, pop_gate_applied=False,
             scan_s=300, fee="rain_candles.fee_c (taker, ceil to the cent per order)", paper_only=True)
assert RULES["lot"] == 25

# api.weather.gov points, copied from the sweep's nws_now.py (city code = last ticker segment)
CITIES = {"ATL": (33.64, -84.43), "BOS": (42.36, -71.01), "CMH": (39.99, -82.89), "LEX": (38.04, -84.61),
          "MIA": (25.79, -80.29), "NYC": (40.78, -73.97), "EWR": (40.69, -74.17), "PHIL": (39.87, -75.24),
          "PIT": (40.49, -80.23), "PVD": (41.72, -71.43), "TTN": (40.28, -74.81), "DC": (38.85, -77.04),
          "AUS": (30.19, -97.67), "CHI": (41.98, -87.90), "CLL": (30.59, -96.36), "DAL": (32.90, -97.04),
          "HOU": (29.98, -95.34), "MKE": (42.95, -87.90), "MIN": (44.88, -93.22), "NOLA": (29.99, -90.26),
          "OKC": (35.39, -97.60), "SATX": (29.53, -98.47), "SGF": (37.24, -93.39), "ABQ": (35.04, -106.61),
          "DEN": (39.86, -104.67), "PHX": (33.43, -112.01), "LV": (36.08, -115.15), "LAX": (33.94, -118.41),
          "SFO": (37.62, -122.38), "SEA": (47.45, -122.31)}
# Regions = cities one weather system can soak in one night (the sweep: "NYC/EWR/TTN/PHIL/PVD/BOS are one
# weather event"). A judgement call, written down; a city not listed is its own region.
REGION = {}
for _name, _cities in {"NE": "BOS PVD NYC EWR TTN PHIL", "MIDATL": "DC PIT", "OHIOV": "CMH LEX",
                       "SE": "ATL MIA", "TXGULF": "AUS CLL DAL HOU SATX NOLA", "PLAINS": "OKC SGF",
                       "MIDWEST": "CHI MKE MIN DTW", "DESERT": "ABQ PHX LV", "ROCKIES": "DEN",
                       "CA": "LAX SFO", "PACNW": "SEA"}.items():
    for _c in _cities.split():
        REGION[_c] = _name
NWS_HDR = {"User-Agent": "kals-research (joepisano18@gmail.com)", "Accept": "application/geo+json"}


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def iso(t):
    return dt.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def et_date(t):
    """The ET calendar date of a UTC timestamp (EDT 2nd Sunday of March 07:00Z .. 1st Sunday of Nov 06:00Z)."""
    y = dt.datetime.fromtimestamp(t, UTC).year
    def nth_sunday(month, n):
        d = dt.date(y, month, 1)
        d += dt.timedelta(days=(6 - d.weekday()) % 7)
        return d + dt.timedelta(days=7 * (n - 1))
    start = dt.datetime.combine(nth_sunday(3, 2), dt.time(7), UTC).timestamp()
    end = dt.datetime.combine(nth_sunday(11, 1), dt.time(6), UTC).timestamp()
    off = 4 if start <= t < end else 5
    return (dt.datetime.fromtimestamp(t, UTC) - dt.timedelta(hours=off)).strftime("%Y-%m-%d")


def market_date(ticker):
    """KXRAIN-26OCT04-TTN -> '2026-10-04' (the local day the market is about)."""
    return dt.datetime.strptime(ticker.split("-")[1], "%y%b%d").strftime("%Y-%m-%d")


def parse_book(ob):
    """Resting YES bids as [(price_dollars, qty)], unit decided by the KEY, never the magnitude."""
    if "orderbook_fp" in ob:
        side = (ob["orderbook_fp"] or {}).get("yes_dollars") or []
        return [(float(p), float(q)) for p, q in side]
    side = ((ob.get("orderbook") or {}).get("yes")) or []
    return [(float(p) / 100.0, float(q)) for p, q in side]       # legacy shape: integer cents


def depth(yes, lo, hi):
    return round(sum(q for p, q in yes if lo - EPS <= p <= hi + EPS), 2)


def pnl_per_contract(yes_bid, result, lot=RULES["lot"]):
    """rain_candles.run's money line for one market: win keeps the YES bid, a loss pays 1 - bid; taker fee."""
    p_no = 1 - yes_bid
    gross = -(p_no * 100) if result == "yes" else yes_bid * 100
    return gross - rain_candles.fee_c(p_no, lot)


class Log:
    def __init__(self, path=None):
        self.path = path
        self.rows = []
        self.fh = open(path, "a", encoding="utf-8") if path else None

    def write(self, type_, **kw):
        r = {"t": iso(time.time()), "type": type_}
        r.update(kw)
        if self.fh:
            self.fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            self.fh.flush()
        else:
            self.rows.append(r)
        return r

    def close(self):
        if self.fh:
            self.fh.close()
            self.fh = None


class NWS:
    """Max hourly rain chance (%) for a city on a local date, or None. Points URL cached per city,
    answers cached 30 min. Public GET only."""
    def __init__(self, fetch=None):
        self.fetch = fetch or self._fetch
        self.points = {}
        self.cache = {}

    @staticmethod
    def _fetch(url):
        req = urllib.request.Request(url, headers=NWS_HDR)
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())

    def pop(self, city, date, now=None):
        if city not in CITIES:
            return None
        now = time.time() if now is None else now
        k = (city, date)
        if k in self.cache and now - self.cache[k][0] < 1800:
            return self.cache[k][1]
        try:
            if city not in self.points:
                la, lo = CITIES[city]
                p = self.fetch("https://api.weather.gov/points/%.4f,%.4f" % (la, lo))
                self.points[city] = (p.get("properties") or {}).get("forecastHourly")
                time.sleep(0.3)
            if not self.points[city]:
                return None
            h = self.fetch(self.points[city])
            vals = []
            for q in (h.get("properties") or {}).get("periods") or []:
                if str(q.get("startTime", ""))[:10] == date:
                    v = (q.get("probabilityOfPrecipitation") or {}).get("value")
                    vals.append(0 if v is None else v)
            val = max(vals) if vals else None
        except Exception:
            val = None
        self.cache[k] = (now, val)
        return val


class Bot:
    def __init__(self, api_get, log, nws=None, now=time.time, rules=RULES):
        self.get = api_get
        self.log = log
        self.nws = nws or NWS()
        self.now = now
        self.R = rules
        self.final = set()                      # tickers with a final decision (filled, cap-refused, window passed)
        self.tries = {}                         # ticker -> {"n", "why"} for supply refusals still inside the window
        self.pending = {}                       # ticker -> fill awaiting settlement
        self.night = collections.defaultdict(lambda: {"cities": set(), "regions": collections.Counter()})
        self.day_total = collections.defaultdict(float)
        self.sleep = time.sleep

    # ---- state ----
    def restore(self, path):
        if not path or not os.path.exists(path):
            return 0
        n = 0
        for line in open(path, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("type") == "decision" and r.get("filled"):
                self._book_fill(r)
                n += 1
            elif r.get("type") == "settled":
                self.pending.pop(r["ticker"], None)
                self.day_total[r["day"]] = r["day_total_c"]
        return n

    def _book_fill(self, d):
        t = d["ticker"]
        self.pending[t] = dict(ticker=t, city=d["city"], region=d["region"], close=d["close"], yes_bid=d["yes_bid"])
        ng = self.night[d["night"]]
        ng["cities"].add(d["city"])
        ng["regions"][d["region"]] += 1
        self.final.add(t)

    # ---- API ----
    def list_open(self):
        ms, cursor = [], None
        while True:
            p = {"series_ticker": self.R["series"], "status": "open", "limit": "200"}
            if cursor:
                p["cursor"] = cursor
            st, b = self.get("/markets", p)
            if st != 200 or not isinstance(b, dict):
                raise RuntimeError("HTTP %s on /markets: %s" % (st, str(b)[:160]))
            ms += b.get("markets", [])
            cursor = b.get("cursor")
            if not cursor:
                return ms
            self.sleep(0.15)

    def book(self, ticker):
        st, ob = self.get("/markets/%s/orderbook" % ticker, {"depth": "40"})
        if st != 200 or not isinstance(ob, dict):
            raise RuntimeError("HTTP %s on orderbook %s: %s" % (st, ticker, str(ob)[:160]))
        return parse_book(ob)

    # ---- the desk ----
    def eligible(self, m, now):
        lo, hi = self.R["window_h"]
        h = (ts(m["close_time"]) - now) / 3600
        return lo - EPS <= h <= hi + EPS and m.get("ticker") not in self.final

    def scan(self):
        now = self.now()
        ms = self.list_open()
        elig = [m for m in ms if self.eligible(m, now)]
        self.log.write("scan", n_open=len(ms), n_eligible=len(elig),
                       pending=len(self.pending), tries=len(self.tries))
        for m in sorted(elig, key=lambda x: x["ticker"]):
            try:
                self.decide(m, now)
            except Exception as e:
                self.log.write("error", where="decide", ticker=m.get("ticker"), err=repr(e)[:300])
            self.sleep(0.12)
        # markets whose window passed without a fill
        lo = self.R["window_h"][0]
        for t in list(self.tries):
            if ts(self.tries[t]["close"]) - now < lo * 3600 - EPS:
                tr = self.tries.pop(t)
                self.final.add(t)
                self.log.write("decision", ticker=t, city=tr["city"], region=tr["region"], close=tr["close"],
                               yes_bid=tr.get("yes_bid"), depth_1_10=tr.get("depth_1_10"),
                               depth_3_10=tr.get("depth_3_10"), pop=tr.get("pop"), filled=False,
                               why="window passed; last: %s" % tr["why"], attempts=tr["n"])
        self.settle(now)

    def decide(self, m, now):
        t = m["ticker"]
        city = t.split("-")[-1]
        region = REGION.get(city, city)
        close = m["close_time"]
        night = et_date(ts(close))
        yes = self.book(t)
        best = max(yes, key=lambda x: x[0]) if yes else None
        d110, d310 = depth(yes, 0.01, 0.10), depth(yes, *self.R["rung"])
        pop = self.nws.pop(city, market_date(t), now)
        lo, hi = self.R["rung"]
        ng = self.night[night]
        why = None
        if best is None:
            why = "no YES bid"
        elif best[0] < lo - EPS:
            why = "best bid %.1fc below the 3c rung" % (best[0] * 100)
        elif best[0] > hi + EPS:
            why = "best bid %.1fc above the 10c rung" % (best[0] * 100)
        elif best[1] < self.R["min_depth"] - EPS:
            why = "depth %g < %d at the best bid" % (best[1], self.R["min_depth"])
        elif len(ng["cities"]) >= self.R["max_cities_per_night"] and city not in ng["cities"]:
            why = "night cap %d cities" % self.R["max_cities_per_night"]
        elif ng["regions"][region] >= self.R["max_cities_per_region"]:
            why = "region cap %d (%s)" % (self.R["max_cities_per_region"], region)
        supply_refusal = why is not None and not why.endswith("cities") and not why.startswith("region cap")
        rec = dict(ticker=t, city=city, region=region, close=close, night=night, hours_to_close=round((ts(close) - now) / 3600, 2),
                   yes_bid=best[0] if best else None, best_depth=best[1] if best else None,
                   depth_1_10=d110, depth_3_10=d310, pop=pop,
                   pop_gate=(pop is not None and pop > self.R["pop_gate_pct"]), filled=why is None, why=why)
        if why is None:
            p_no = 1 - best[0]
            rec.update(p_no=round(p_no, 4), lot=self.R["lot"], fee_c=rain_candles.fee_c(p_no, self.R["lot"]),
                       attempts=self.tries.get(t, {}).get("n", 0) + 1)
            self.tries.pop(t, None)
            self.log.write("decision", **rec)
            self._book_fill(rec)
            return rec
        if supply_refusal:
            tr = self.tries.setdefault(t, dict(n=0, city=city, region=region, close=close))
            tr["n"] += 1
            tr.update(why=why, yes_bid=rec["yes_bid"], depth_1_10=d110, depth_3_10=d310, pop=pop)
            if tr["n"] == 1:
                self.log.write("decision", **rec)
            return rec
        self.tries.pop(t, None)
        self.final.add(t)
        self.log.write("decision", **rec)
        return rec

    def settle(self, now):
        for t in sorted(self.pending):
            f = self.pending[t]
            if ts(f["close"]) > now:
                continue
            st, b = self.get("/markets/%s" % t, None)
            if st != 200 or not isinstance(b, dict):
                self.log.write("error", where="settle", ticker=t, err="HTTP %s %s" % (st, str(b)[:120]))
                continue
            mk = b.get("market") or {}
            res = mk.get("result")
            if res not in ("yes", "no"):
                continue
            pc = pnl_per_contract(f["yes_bid"], res, self.R["lot"])
            lot_c = pc * self.R["lot"]
            day = et_date(now)
            self.day_total[day] += lot_c
            self.log.write("settled", ticker=t, city=f["city"], region=f["region"], close=f["close"], result=res,
                           lost=(res == "yes"), yes_bid=f["yes_bid"], lot=self.R["lot"],
                           pnl_c=round(pc, 4), pnl_lot_c=round(lot_c, 2), day=day,
                           day_total_c=round(self.day_total[day], 2))
            del self.pending[t]
            self.sleep(0.12)


# ---------------------------------------------------------------- self-test
def selftest():
    NOW = ts("2026-10-04T07:00:00Z")           # 03:00 ET Oct 4; a market 22 h out closes 05:00Z Oct 5 = 01:00 ET Oct 5
    T = {"ticker": None}

    def mk(code, hours, date="26OCT04"):
        return {"ticker": "KXRAIN-%s-%s" % (date, code), "status": "active",
                "close_time": iso(NOW + hours * 3600)}

    class Fake:
        def __init__(self, markets, books, results=None, pages=1):
            self.markets, self.books, self.results, self.pages = markets, books, results or {}, pages
            self.calls = []

        def get(self, path, params=None):
            self.calls.append((path, dict(params or {})))
            if path == "/markets":
                n = max(1, math.ceil(len(self.markets) / self.pages))
                i = int(params.get("cursor", "0") or 0)
                page = self.markets[i * n:(i + 1) * n]
                nxt = str(i + 1) if (i + 1) * n < len(self.markets) else None
                return 200, {"markets": page, "cursor": nxt}
            if path.endswith("/orderbook"):
                t = path.split("/")[2]
                return 200, {"orderbook_fp": {"yes_dollars": self.books.get(t, []), "no_dollars": []}}
            t = path.split("/")[2]
            return 200, {"market": {"ticker": t, "result": self.results.get(t, "")}}

    def bot(api, pops=None):
        nws = NWS(fetch=lambda url: {})
        nws.pop = lambda city, date, now=None: (pops or {}).get(city)
        return Bot(api.get, Log(), nws=nws, now=lambda: NOW), nws

    def decisions(b, **flt):
        rows = [r for r in b.log.rows if r["type"] == "decision"]
        return [r for r in rows if all(r.get(k) == v for k, v in flt.items())]

    SUPPLY = [["0.0100", "500.00"], ["0.0300", "30.00"]]          # best bid 3c x 30 (>= 25); 1-10c depth 530
    checks = 0

    # 1. eligibility window: 21.5 and 22.5 h inclusive, 21.0 and 23.0 out; pagination walks both pages
    api = Fake([mk("ATL", 21.0), mk("DC", 21.5), mk("CHI", 22.0), mk("DEN", 22.5), mk("SEA", 23.0)],
               {m: SUPPLY for m in ["KXRAIN-26OCT04-" + c for c in "ATL DC CHI DEN SEA".split()]}, pages=2)
    b, _ = bot(api)
    b.scan()
    sc = [r for r in b.log.rows if r["type"] == "scan"][0]
    assert sc["n_open"] == 5 and sc["n_eligible"] == 3, sc
    assert sorted(r["city"] for r in decisions(b)) == ["CHI", "DC", "DEN"], decisions(b)
    assert all(r["filled"] for r in decisions(b))
    assert sum(1 for p, _ in api.calls if p == "/markets") == 2, "two pages"
    checks += 1

    # 2. the 25-lot depth rule and the 3-10c rung on the BEST bid
    books = {"KXRAIN-26OCT04-ATL": [["0.0100", "900.00"], ["0.0500", "24.00"]],      # 24 < 25
             "KXRAIN-26OCT04-CHI": [["0.0100", "900.00"], ["0.0500", "25.00"]],      # exactly 25 fills
             "KXRAIN-26OCT04-DEN": [["0.0200", "5000.00"]],                          # best bid below the rung
             "KXRAIN-26OCT04-SEA": [["0.0500", "100.00"], ["0.1200", "100.00"]],     # best bid above the rung
             "KXRAIN-26OCT04-MIA": []}                                               # no bid
    api = Fake([mk(c, 22.0) for c in "ATL CHI DEN SEA MIA".split()], books)
    b, _ = bot(api)
    b.scan()
    d = {r["city"]: r for r in decisions(b)}
    assert not d["ATL"]["filled"] and d["ATL"]["why"].startswith("depth 24"), d["ATL"]
    assert d["CHI"]["filled"] and abs(d["CHI"]["yes_bid"] - 0.05) < EPS and abs(d["CHI"]["p_no"] - 0.95) < EPS
    assert abs(d["CHI"]["depth_1_10"] - 925) < EPS and abs(d["CHI"]["depth_3_10"] - 25) < EPS
    assert not d["DEN"]["filled"] and "below" in d["DEN"]["why"] and abs(d["DEN"]["depth_1_10"] - 5000) < EPS
    assert not d["SEA"]["filled"] and "above" in d["SEA"]["why"] and abs(d["SEA"]["depth_3_10"] - 100) < EPS
    assert not d["MIA"]["filled"] and d["MIA"]["why"] == "no YES bid" and d["MIA"]["yes_bid"] is None
    # a supply refusal is re-checked, logged once, and fills when supply appears; the window passing closes it
    api.books["KXRAIN-26OCT04-ATL"] = [["0.0500", "60.00"]]
    b.scan()
    assert len(decisions(b, city="MIA")) == 1 and b.tries["KXRAIN-26OCT04-MIA"]["n"] == 2
    atl = decisions(b, city="ATL")
    assert len(atl) == 2 and atl[1]["filled"] and atl[1]["attempts"] == 2, atl
    b.now = lambda: NOW + 1.0 * 3600 + 1          # 20.99 h to close: out of the window
    b.scan()
    mia = decisions(b, city="MIA")
    assert len(mia) == 2 and mia[1]["why"].startswith("window passed") and mia[1]["attempts"] == 2, mia
    assert "KXRAIN-26OCT04-MIA" in b.final and "KXRAIN-26OCT04-MIA" not in b.tries
    checks += 1

    # 3. region cap 2 and night cap 6; a cap refusal is final (not re-tried)
    ne = "BOS PVD NYC EWR TTN PHIL".split()
    api = Fake([mk(c, 22.0) for c in ne], {"KXRAIN-26OCT04-" + c: SUPPLY for c in ne})
    b, _ = bot(api)
    b.scan()
    assert sum(r["filled"] for r in decisions(b)) == 2, decisions(b)
    assert all(r["why"] == "region cap 2 (NE)" for r in decisions(b, filled=False))
    assert not b.tries and len(b.final) == 6
    many = "ATL DC CHI DEN SEA LAX HOU OKC".split()      # 8 regions, one city each
    api = Fake([mk(c, 22.0) for c in many], {"KXRAIN-26OCT04-" + c: SUPPLY for c in many})
    b, _ = bot(api)
    b.scan()
    assert sum(r["filled"] for r in decisions(b)) == 6, decisions(b)
    assert sorted(r["why"] for r in decisions(b, filled=False)) == ["night cap 6 cities"] * 2
    # the night is the ET date of the close: 05:00Z Oct 5 and 08:00Z Oct 5 are one night, Oct 6 another
    api = Fake([mk(c, 22.0) for c in many] + [mk("MIN", 22.0 + 24, "26OCT05")],
               {"KXRAIN-26OCT04-" + c: SUPPLY for c in many} | {"KXRAIN-26OCT05-MIN": SUPPLY})
    b, _ = bot(api)
    b.scan()                                          # 26OCT05-MIN is 46 h out: not eligible yet
    assert len(b.night) == 1 and len(next(iter(b.night.values()))["cities"]) == 6
    b.now = lambda: NOW + 24 * 3600
    b.scan()
    assert decisions(b, city="MIN")[0]["filled"], "a new night starts a new cap"
    assert et_date(ts("2026-10-05T05:00:00Z")) == "2026-10-05" and et_date(ts("2026-10-05T03:59:00Z")) == "2026-10-04"
    assert et_date(ts("2026-11-01T05:30:00Z")) == "2026-11-01" and et_date(ts("2026-11-02T04:59:00Z")) == "2026-11-01"
    checks += 1

    # 4. fee arithmetic against rain_candles on one example: bid 3c, 25 lots -> fee 0.24c, win +2.76c, loss -97.24c
    assert abs(rain_candles.fee_c(0.97, 25) - 0.24) < EPS
    assert abs(pnl_per_contract(0.03, "no") - 2.76) < EPS and abs(pnl_per_contract(0.03, "yes") - (-97.24)) < EPS
    exp = (57 * 3 - 3 * 97) / 60 - rain_candles.fee_c(0.97, 25)          # rain_candles' own self-test number
    got = (57 * pnl_per_contract(0.03, "no") + 3 * pnl_per_contract(0.03, "yes")) / 60
    assert abs(got - exp) < EPS, (got, exp)
    assert abs(pnl_per_contract(0.05, "no") - (5 - math.ceil(0.07 * 0.95 * 0.05 * 25 * 100) / 25)) < EPS
    checks += 1

    # 5. settlement booking, day running total, and restore from the log
    tmp = os.path.join(os.environ.get("TEMP", HERE), "rain_paper_selftest_%d.jsonl" % os.getpid())
    try:
        api = Fake([mk("ATL", 22.0), mk("CHI", 22.0)],
                   {"KXRAIN-26OCT04-ATL": SUPPLY, "KXRAIN-26OCT04-CHI": [["0.0500", "40.00"]]})
        nws = NWS(fetch=lambda url: {})
        nws.pop = lambda city, date, now=None: {"ATL": 10, "CHI": 60}.get(city)
        b = Bot(api.get, Log(tmp), nws=nws, now=lambda: NOW)
        b.scan()
        assert len(b.pending) == 2
        b.now = lambda: NOW + 23 * 3600                   # after close, nothing settled yet
        b.scan()
        assert len(b.pending) == 2 and not [p for p, _ in api.calls if p.endswith("/orderbook") and "OCT04" not in p]
        api.results = {"KXRAIN-26OCT04-ATL": "no", "KXRAIN-26OCT04-CHI": "yes"}
        b.scan()
        assert not b.pending
        b.log.close()
        rows = [json.loads(l) for l in open(tmp, encoding="utf-8")]
        st = [r for r in rows if r["type"] == "settled"]
        assert [r["ticker"][-3:] for r in st] == ["ATL", "CHI"]
        assert abs(st[0]["pnl_c"] - 2.76) < EPS and abs(st[0]["pnl_lot_c"] - 69.0) < EPS and not st[0]["lost"]
        assert abs(st[1]["pnl_c"] - pnl_per_contract(0.05, "yes")) < EPS and st[1]["lost"]
        assert abs(st[0]["day_total_c"] - 69.0) < EPS and abs(st[1]["day_total_c"] - (69.0 + st[1]["pnl_lot_c"])) < EPS
        dec = {r["city"]: r for r in rows if r["type"] == "decision"}
        assert dec["ATL"]["pop"] == 10 and not dec["ATL"]["pop_gate"] and dec["CHI"]["pop"] == 60 and dec["CHI"]["pop_gate"]
        assert dec["ATL"]["filled"] and dec["CHI"]["filled"], "the forecast gate is recorded, not applied"
        # restore: a fresh bot sees the fills, the caps and the totals (log cut before settlement)
        with open(tmp, "w", encoding="utf-8") as fh:
            for r in rows:
                if r["type"] != "settled":
                    fh.write(json.dumps(r) + "\n")
        b2 = Bot(api.get, Log(), nws=nws, now=lambda: NOW)
        assert b2.restore(tmp) == 2 and set(b2.pending) == {"KXRAIN-26OCT04-ATL", "KXRAIN-26OCT04-CHI"}
        assert b2.night["2026-10-05"]["regions"]["SE"] == 1 and "KXRAIN-26OCT04-ATL" in b2.final
        b2.scan()
        assert not decisions(b2), "restored fills are not decided twice"
        with open(tmp, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(st[0]) + "\n")
        b4 = Bot(api.get, Log(), nws=nws, now=lambda: NOW)
        b4.restore(tmp)
        assert set(b4.pending) == {"KXRAIN-26OCT04-CHI"} and abs(b4.day_total[st[0]["day"]] - 69.0) < EPS
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    checks += 1

    # 6. the NULL: open markets, none in the window -> a scan record and no decision; empty list too
    api = Fake([mk("ATL", 30.0), mk("CHI", 5.0)], {})
    b, _ = bot(api)
    b.scan()
    sc = [r for r in b.log.rows if r["type"] == "scan"][0]
    assert sc["n_open"] == 2 and sc["n_eligible"] == 0 and not decisions(b) and not b.pending
    assert not [p for p, _ in api.calls if p.endswith("/orderbook")], "no book read outside the window"
    b, _ = bot(Fake([], {}))
    b.scan()
    assert not decisions(b) and [r for r in b.log.rows if r["type"] == "scan"][0]["n_open"] == 0
    checks += 1

    # 7. book parsing by key (dollars vs legacy cents); NWS day pick; the market date
    assert parse_book({"orderbook_fp": {"yes_dollars": [["0.0350", "12.00"]]}}) == [(0.035, 12.0)]
    assert parse_book({"orderbook": {"yes": [[3, 12]]}}) == [(0.03, 12.0)]
    assert parse_book({"orderbook_fp": {"yes_dollars": None}}) == [] and parse_book({}) == []
    n = NWS(fetch=lambda url: {"properties": {"forecastHourly": "H"}} if "points" in url else
            {"properties": {"periods": [{"startTime": "2026-10-04T23:00:00-04:00", "probabilityOfPrecipitation": {"value": 7}},
                                        {"startTime": "2026-10-05T00:00:00-04:00", "probabilityOfPrecipitation": {"value": 55}},
                                        {"startTime": "2026-10-05T01:00:00-04:00", "probabilityOfPrecipitation": {"value": None}}]}})
    n.points["ATL"] = "H"          # skip the points call (and its sleep)
    assert n.pop("ATL", "2026-10-05", NOW) == 55 and n.pop("ATL", "2026-10-04", NOW) == 7
    assert n.pop("ATL", "2026-10-09", NOW) is None and n.pop("XXX", "2026-10-05", NOW) is None
    assert market_date("KXRAIN-26OCT04-TTN") == "2026-10-04"
    checks += 1

    # 8. PAPER ONLY: no order endpoint, no non-GET method, no request body, anywhere in this file
    src = open(__file__, encoding="utf-8").read()
    assert ("portfolio/" + "orders") not in src
    assert ("PO" + "ST") not in src and ("DEL" + "ETE") not in src and ("meth" + "od=" + chr(34)) not in src
    assert ("urlopen(req, " + "da" + "ta") not in src and ("da" + "ta=" + "body") not in src
    for ln in src.splitlines():
        s = ln.strip()
        assert not (s.startswith(("import ", "from ")) and any(w in s for w in ("replay", "pinsim", "pindata"))), s
    checks += 1

    print("selftest ok: %d check groups" % checks)
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--once", action="store_true", help="one scan + settlement check, then exit")
    ap.add_argument("--minutes", type=float, default=43200, help="run length (default 30 days)")
    ap.add_argument("--log", default=LOG)
    a = ap.parse_args()
    try:
        selftest()
    except AssertionError as e:
        print("SELFTEST FAILED:", repr(e))
        sys.exit(2)
    if a.selftest:
        return
    import kauth                                     # GET-only signed helper; opens the key file, so after the self-test
    log = Log(a.log)
    bot = Bot(kauth.get, log)
    restored = bot.restore(a.log)
    log.write("start", pid=os.getpid(), argv=sys.argv, rules=RULES, regions=REGION, once=a.once,
              minutes=a.minutes, restored_fills=restored, pending=sorted(bot.pending))
    print("rain_paper start pid", os.getpid(), "restored fills", restored, "pending", len(bot.pending), flush=True)
    end = time.time() + a.minutes * 60
    while True:
        if os.path.exists(STOP):
            log.write("stop", why="stop file")
            print("stop file present; exiting", flush=True)
            return
        t0 = time.time()
        try:
            bot.scan()
        except Exception as e:
            log.write("error", where="scan", err=repr(e)[:300])
            print("scan error", repr(e)[:200], flush=True)
        if a.once:
            rows = [r for r in open(a.log, encoding="utf-8")][-40:]
            last = [json.loads(r) for r in rows]
            sc = [r for r in last if r["type"] == "scan"]
            print("scan:", json.dumps(sc[-1]) if sc else "none", flush=True)
            print("decisions this scan:", sum(1 for r in last if r["type"] == "decision" and r["t"] >= sc[-1]["t"]) if sc else 0, flush=True)
            return
        if time.time() >= end:
            log.write("stop", why="minutes elapsed")
            return
        time.sleep(max(5, RULES["scan_s"] - (time.time() - t0)))


if __name__ == "__main__":
    main()
