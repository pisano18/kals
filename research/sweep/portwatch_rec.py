"""portwatch_rec.py -- READ-ONLY recorder for the SJ04 PortWatch Tuesday (IDEA_LEDGER U13, READS_DUE portwatch-1006).

What it records, in one small process (target < 150 MB, no tape loads, no orders -- the self-test
asserts no order-sending verb exists in this file):

  (a) LAYER  a 2-s poller on the IMF PortWatch ArcGIS layer Daily_Chokepoints_Data/0, the settlement
      source. Every poll is cache-busted with a nonce query param (the CDN caches 30 s; the sweep's
      cache_test.py showed a nonce gives TCP_MISS every time). Per poll it logs the layer's editingInfo
      stamps, the row count per chokepoint for date >= the settlement week's Monday, the first time each
      of Suez / Panama / Bab el-Mandeb / Hormuz shows all 7 days of that week ("layer_complete"), and any
      value change between polls ("layer_change" -- a partial reload is the thing the bar fears).
  (b) BOOKS  a Kalshi WebSocket subscription (orderbook_delta -> snapshot + deltas, the collector's
      channels) on every market in the eight PortWatch series that closes on --date. A per-market book
      is kept; at each chokepoint's layer-complete time and +5 s and +30 s it logs, for that chokepoint's
      markets, the TRUE-SIDE asks <= 95c (contracts and dollars) plus the full book. The true side is
      computed from the market's own strike fields and the layer's numbers; a market whose rule cannot be
      decided with certainty from the layer gets side "unknown" and its book is logged anyway.
  (c) TRADES the trade channel on the same tickers; every print is logged, and at layer-complete the
      first true-side taker trade (since recorder start, and after completion) is marked per chokepoint,
      with its lag to the layer stamp -- the bar's "first informed trade".

Mapping used for the true side (from rules_primary / strike fields, read 2026-10-03):
  KX{SUEZ,PANAMA,BABELMANDEB,HORMUZ}WEEKLY-T<N>  strike greater N   YES iff weekly SUM of n_total  > N
      (checked on the 09-27 week: Suez summed to exactly 280 and T280 settled NO, so "above" is strict)
  KXHORMUZPEAK-T<N>                            strike greater N   YES iff MAX daily n_total > N
  KXHORMUZMAX-<DAY>                custom_strike Day              YES iff that day's n_total is the
      unique maximum of the week; a tie at the max -> "unknown" (the rule does not say how a tie settles)
  KXMAXSHIPSHORMUZ-AL<N>   greater_or_equal N, "in Oct 2026"      YES is certain once any October day
      in the layer is >= N, otherwise "unknown" (the month is not over)
  KXHORMUZNORM                      7-day moving average rule     "unknown" (not a weekly-layer market)

    python research/sweep/portwatch_rec.py --selftest
    python research/sweep/portwatch_rec.py --date 2026-10-06 --start 11:30Z --end 13:30Z --dry-run
    python research/sweep/portwatch_rec.py --date 2026-10-06 --start 11:30Z --end 13:30Z

Log: results/portwatch-rec-<date>.jsonl (dry run: results/portwatch-rec-<date>-dry.jsonl), one JSON
object a line, every "t" in UTC. stdout/stderr go wherever the launcher redirects them
(start_portwatch_1006.ps1 -> results/portwatch-rec-<date>.stdout.log / .stderr.log).

stdlib only, plus research/kauth.py for the RSA-PSS signature the WebSocket handshake needs (the same
scheme as kalshi_collector.make_signer; GET-only by construction). The WebSocket client here is a
minimal RFC 6455 implementation on socket+ssl because the repo convention is no third-party packages.
"""
import argparse
import base64
import collections
import datetime as dt
import hashlib
import json
import os
import random
import re
import socket
import ssl
import struct
import sys
import threading
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "research"))
RESULTS = os.path.join(ROOT, "results")
UTC = dt.timezone.utc

LAYER = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
         "Daily_Chokepoints_Data/FeatureServer/0")
WS_HOST = "api.elections.kalshi.com"
WS_PATH = "/trade-api/ws/v2"
SERIES = ["KXHORMUZWEEKLY", "KXSUEZWEEKLY", "KXPANAMAWEEKLY", "KXBABELMANDEBWEEKLY",
          "KXHORMUZMAX", "KXHORMUZPEAK", "KXMAXSHIPSHORMUZ", "KXHORMUZNORM"]
# layer portid -> short name; the four the bars are written on
CHOKEPOINTS = collections.OrderedDict([("chokepoint1", "suez"), ("chokepoint2", "panama"),
                                       ("chokepoint4", "bab"), ("chokepoint6", "hormuz")])
SERIES_CP = {"KXSUEZWEEKLY": "chokepoint1", "KXPANAMAWEEKLY": "chokepoint2",
             "KXBABELMANDEBWEEKLY": "chokepoint4", "KXHORMUZWEEKLY": "chokepoint6",
             "KXHORMUZMAX": "chokepoint6", "KXHORMUZPEAK": "chokepoint6",
             "KXMAXSHIPSHORMUZ": "chokepoint6", "KXHORMUZNORM": "chokepoint6"}
POLL_S = 2.0
SNAP_OFFSETS = (0.0, 5.0, 30.0)
ASK_CAP = 0.95
BURST_CONTRACTS = 100.0        # true-side taker contracts in one second = "informed" burst


def iso(t):
    return dt.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def ms_iso(x):
    try:
        return dt.datetime.fromtimestamp(x / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return str(x)


def ms_date(x):
    """ArcGIS date attribute (epoch ms) -> 'YYYY-MM-DD' (UTC)."""
    if isinstance(x, str):
        return x[:10]
    return dt.datetime.fromtimestamp(x / 1000, UTC).strftime("%Y-%m-%d")


def parse_hm(s):
    """'11:30Z' -> (11, 30)."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})Z?", s.strip())
    if not m:
        raise ValueError("time must look like 11:30Z: %r" % s)
    return int(m.group(1)), int(m.group(2))


def week_days(monday):
    return [(monday + dt.timedelta(d)).isoformat() for d in range(7)]


# --------------------------------------------------------------------------
# market -> (chokepoint, kind, strike, week) and the true side
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
                                      "Sep", "Oct", "Nov", "Dec"], 1)}
DATE_RE = re.compile(r"([A-Z][a-z]{2})[a-z]* (\d{1,2}), (\d{4})")


def parse_day(s):
    m = DATE_RE.search(s or "")
    if not m or m.group(1) not in MONTHS:
        return None
    return dt.date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)))


def classify(mk):
    """Market dict (REST /markets fields) -> record with chokepoint, kind, strike, week_monday."""
    tk = mk["ticker"]
    series = tk.split("-")[0]
    rec = {"ticker": tk, "series": series, "cp": SERIES_CP.get(series), "kind": "unknown",
           "strike": mk.get("floor_strike"), "day": None, "week_monday": None,
           "close_time": mk.get("close_time"), "rules": (mk.get("rules_primary") or "")[:200]}
    rules = mk.get("rules_primary") or ""
    span = re.search(r"from ([A-Z][a-z]+ \d{1,2}, \d{4}) to ([A-Z][a-z]+ \d{1,2}, \d{4})", rules)
    if span:
        a, b = parse_day(span.group(1)), parse_day(span.group(2))
        if a and b and (b - a).days == 6 and a.weekday() == 0:
            rec["week_monday"] = a.isoformat()
    if series.endswith("WEEKLY") and mk.get("strike_type") == "greater" and rec["strike"] is not None:
        rec["kind"] = "weekly_sum"
    elif series == "KXHORMUZPEAK" and mk.get("strike_type") == "greater" and rec["strike"] is not None:
        rec["kind"] = "weekly_max"
    elif series == "KXHORMUZMAX":
        d = parse_day((mk.get("custom_strike") or {}).get("Day") or mk.get("yes_sub_title"))
        if d:
            rec["kind"] = "argmax_day"
            rec["day"] = d.isoformat()
            rec["week_monday"] = (d - dt.timedelta(d.weekday())).isoformat()
    elif series == "KXMAXSHIPSHORMUZ" and mk.get("strike_type") == "greater_or_equal" \
            and rec["strike"] is not None:
        rec["kind"] = "month_max_ge"
        mo = re.search(r"in ([A-Z][a-z]{2})[a-z]* (\d{4})", rules)
        rec["month"] = ("%04d-%02d" % (int(mo.group(2)), MONTHS[mo.group(1)])) if mo else None
    return rec


def decide(rec, values, week_monday):
    """True side of a market from the layer. `values`: {date: n_total} for the market's chokepoint.
    Returns 'yes' | 'no' | 'unknown' plus a short reason; never guesses."""
    days = week_days(week_monday)
    if rec["kind"] in ("weekly_sum", "weekly_max", "argmax_day"):
        if rec["week_monday"] and rec["week_monday"] != week_monday.isoformat():
            return "unknown", "market week %s != run week %s" % (rec["week_monday"], week_monday)
        if any(d not in values for d in days):
            return "unknown", "week incomplete in layer"
        wk = [values[d] for d in days]
        if rec["kind"] == "weekly_sum":
            s = sum(wk)
            return ("yes" if s > rec["strike"] else "no"), "sum %d vs > %s" % (s, rec["strike"])
        if rec["kind"] == "weekly_max":
            m = max(wk)
            return ("yes" if m > rec["strike"] else "no"), "max %d vs > %s" % (m, rec["strike"])
        m = max(wk)
        v = values.get(rec["day"])
        if v is None or rec["day"] not in days:
            return "unknown", "day %s not in run week" % rec["day"]
        if v < m:
            return "no", "day %d < max %d" % (v, m)
        if wk.count(m) == 1:
            return "yes", "day %d is the unique max" % v
        return "unknown", "tie at the max %d (%d days)" % (m, wk.count(m))
    if rec["kind"] == "month_max_ge" and rec.get("month"):
        mv = [v for d, v in values.items() if d.startswith(rec["month"])]
        if mv and max(mv) >= rec["strike"]:
            return "yes", "october max so far %d >= %s" % (max(mv), rec["strike"])
        return "unknown", "month not over (max so far %s)" % (max(mv) if mv else None)
    return "unknown", "rule not mapped to the layer"


# --------------------------------------------------------------------------
# layer poller
class LayerPoller:
    """One poll = one cache-busted query for the four chokepoints' rows since week Monday, plus the
    layer metadata (editingInfo). `fetch(kind, params)` is injectable for the self-test; it returns
    (json_dict, headers_dict, latency_s)."""

    def __init__(self, week_monday, fetch=None, now=time.time):
        self.week_monday = week_monday
        self.fetch = fetch or self._http_fetch
        self.now = now
        self.n = 0
        self.values = {cp: {} for cp in CHOKEPOINTS}        # cp -> {date: n_total}
        self.full = {}                                       # (cp, date) -> (n_total, n_cargo, n_tanker)
        self.complete_at = {}                                # cp -> poll time it first had all 7 days
        self.last_edit = None
        self.nonces = []

    def nonce(self):
        self.n += 1
        n = "%d-%d-%04x" % (int(self.now() * 1000), self.n, random.getrandbits(16))
        self.nonces.append(n)
        return n

    @staticmethod
    def _http_fetch(kind, params):
        url = (LAYER + "/query" if kind == "query" else LAYER) + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 portwatch_rec"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=6) as r:
            hdr = {k.lower(): v for k, v in r.headers.items()}
            body = r.read()
        return json.loads(body), hdr, time.time() - t0

    def poll(self):
        """Returns a list of log events (dicts without 't')."""
        t = self.now()
        events = []
        where = "date >= DATE '%s' AND portid IN (%s)" % (
            self.week_monday.isoformat(), ",".join("'%s'" % c for c in CHOKEPOINTS))
        qp = {"f": "json", "where": where, "outFields": "ObjectId,date,portid,n_total,n_cargo,n_tanker",
              "returnGeometry": "false", "orderByFields": "ObjectId", "resultRecordCount": "500",
              "_n": self.nonce()}
        try:
            q, qh, ql = self.fetch("query", qp)
        except Exception as e:
            return [{"ev": "poll_error", "what": "query", "err": repr(e)[:200]}]
        try:
            m, mh, ml = self.fetch("meta", {"f": "json", "_n": self.nonce()})
            ei = m.get("editingInfo") or {}
            edit = {k: ms_iso(ei[k]) for k in ("lastEditDate", "dataLastEditDate", "schemaLastEditDate")
                    if k in ei}
        except Exception as e:
            edit, mh, ml = {"err": repr(e)[:120]}, {}, None
        if "error" in q:
            return [{"ev": "poll_error", "what": "query", "err": json.dumps(q["error"])[:300]}]
        rows = {cp: 0 for cp in CHOKEPOINTS}
        maxdate = {cp: None for cp in CHOKEPOINTS}
        changes = []
        seen = {}
        for ft in q.get("features") or []:
            a = ft.get("attributes") or {}
            cp, d = a.get("portid"), a.get("date")
            if cp not in CHOKEPOINTS or d is None or a.get("n_total") is None:
                continue
            d = ms_date(d)
            rows[cp] += 1
            if maxdate[cp] is None or d > maxdate[cp]:
                maxdate[cp] = d
            tup = (a.get("n_total"), a.get("n_cargo"), a.get("n_tanker"))
            seen[(cp, d)] = tup
            old = self.full.get((cp, d))
            if old is None:
                changes.append({"cp": CHOKEPOINTS[cp], "date": d, "old": None, "new": tup})
            elif old != tup:
                changes.append({"cp": CHOKEPOINTS[cp], "date": d, "old": old, "new": tup})
            self.full[(cp, d)] = tup
            self.values[cp][d] = a["n_total"]
        for key in list(self.full):
            if key not in seen:                      # a row vanished -- also a change
                changes.append({"cp": CHOKEPOINTS[key[0]], "date": key[1], "old": self.full[key],
                                "new": None})
                del self.full[key]
                self.values[key[0]].pop(key[1], None)
        if edit != self.last_edit:
            events.append({"ev": "layer_edit_stamp", "edit": edit, "prev": self.last_edit})
            self.last_edit = edit
        events.append({"ev": "poll", "n": self.n // 2, "lat_ms": int(ql * 1000),
                       "meta_lat_ms": None if ml is None else int(ml * 1000),
                       "x_cache": qh.get("x-cache"), "etag": qh.get("etag"), "age": qh.get("age"),
                       "edit": edit, "rows": {CHOKEPOINTS[c]: rows[c] for c in CHOKEPOINTS},
                       "maxdate": {CHOKEPOINTS[c]: maxdate[c] for c in CHOKEPOINTS},
                       "n_changes": len(changes)})
        if changes:
            events.append({"ev": "layer_change", "changes": changes,
                           "values": {CHOKEPOINTS[c]: dict(sorted(self.values[c].items()))
                                      for c in CHOKEPOINTS}})
        days = week_days(self.week_monday)
        for cp in CHOKEPOINTS:
            if cp not in self.complete_at and all(d in self.values[cp] for d in days):
                self.complete_at[cp] = t
                wk = [self.values[cp][d] for d in days]
                events.append({"ev": "layer_complete", "cp": CHOKEPOINTS[cp], "portid": cp,
                               "week": days, "n_total": wk, "sum": sum(wk), "max": max(wk),
                               "argmax": [days[i] for i, v in enumerate(wk) if v == max(wk)],
                               "edit": edit})
        return events


# --------------------------------------------------------------------------
# order books (the collector's frames; units per livebook.py: dollars as strings, sizes as strings)
class Books:
    def __init__(self):
        self.b = {}              # ticker -> {"yes": {px: size}, "no": {px: size}}
        self.have_snapshot = set()
        self.seq = {}            # sid -> last seq
        self.gaps = 0
        self.lock = threading.Lock()

    def reset(self):
        with self.lock:
            self.b.clear()
            self.have_snapshot.clear()
            self.seq.clear()

    def track_seq(self, sid, seq):
        if sid is None or seq is None:
            return None
        prev = self.seq.get(sid)
        self.seq[sid] = seq
        if prev is not None and seq != prev + 1:
            self.gaps += 1
            return {"expected": prev + 1, "got": seq}
        return None

    def snapshot(self, msg):
        tk = msg.get("market_ticker")
        if not tk:
            return
        book = {"yes": {}, "no": {}}
        for side, key in (("yes", "yes_dollars_fp"), ("no", "no_dollars_fp")):
            for lv in msg.get(key) or []:
                try:
                    p, s = round(float(lv[0]), 4), round(float(lv[1]), 2)
                except (TypeError, ValueError, IndexError):
                    continue
                if s > 0:
                    book[side][p] = s
        with self.lock:
            self.b[tk] = book
            self.have_snapshot.add(tk)

    def delta(self, msg):
        tk, side = msg.get("market_ticker"), msg.get("side")
        if not tk or side not in ("yes", "no"):
            return False
        try:
            p, d = round(float(msg["price_dollars"]), 4), round(float(msg["delta_fp"]), 2)
        except (KeyError, TypeError, ValueError):
            return False
        with self.lock:
            if tk not in self.have_snapshot:
                return False
            lv = self.b[tk][side]
            new = round(lv.get(p, 0.0) + d, 2)
            if new <= 0:
                lv.pop(p, None)
            else:
                lv[p] = new
        return True

    def asks(self, tk, side, cap=ASK_CAP):
        """Resting asks on `side` ('yes' asks = 1 - NO bids) priced <= cap: [[price, size], ...]."""
        with self.lock:
            bk = self.b.get(tk)
            if not bk:
                return None
            opp = bk["no" if side == "yes" else "yes"]
            out = sorted((round(1 - p, 4), s) for p, s in opp.items())
        return [[p, s] for p, s in out if p <= cap + 1e-9]

    def dump(self, tk):
        with self.lock:
            bk = self.b.get(tk)
            if bk is None:
                return None
            yb = sorted(bk["yes"].items(), reverse=True)
            nb = sorted(bk["no"].items(), reverse=True)
        return {"yes_bids": [[p, s] for p, s in yb], "no_bids": [[p, s] for p, s in nb],
                "best": {"yes_bid": yb[0][0] if yb else None, "no_bid": nb[0][0] if nb else None,
                         "yes_ask": round(1 - nb[0][0], 4) if nb else None,
                         "no_ask": round(1 - yb[0][0], 4) if yb else None}}


# --------------------------------------------------------------------------
# the recorder: glue, timers, trade marks, log
class Recorder:
    def __init__(self, markets, week_monday, log_path, fetch=None, now=time.time, quiet=False):
        self.now = now
        self.recs = [classify(m) for m in markets]
        self.by_tk = {r["ticker"]: r for r in self.recs}
        self.week_monday = week_monday
        self.poller = LayerPoller(week_monday, fetch=fetch, now=now)
        self.books = Books()
        self.log_path = log_path
        self._fh = open(log_path, "a", encoding="utf-8") if log_path else None
        self.quiet = quiet
        self.pending = []            # (fire_at, cp, label, complete_t)
        self.sides = {}              # ticker -> (side, reason) once its chokepoint completed
        self.trades = []             # (ts, ticker, taker_side, price_paid, count)
        self.first_after = {}        # cp -> True once the first true-side trade after complete is logged
        self.frames = collections.Counter()
        self.lock = threading.Lock()
        self.next_poll = 0.0

    # -- log
    def log(self, ev):
        ev = dict(ev)
        ev["t"] = iso(self.now())
        line = json.dumps(ev, ensure_ascii=False, default=str)
        if self._fh:
            self._fh.write(line + "\n")
            self._fh.flush()
        if not self.quiet and ev["ev"] not in ("poll", "trade", "book_snap"):
            print(line[:400], flush=True)

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None

    # -- layer
    def poll_once(self):
        t = self.now()
        for ev in self.poller.poll():
            self.log(ev)
            if ev["ev"] == "layer_complete":
                self.on_complete(ev["portid"], t)

    def on_complete(self, cp, t):
        cps = CHOKEPOINTS[cp]
        vals = self.poller.values[cp]
        decided = {}
        for r in self.recs:
            if r["cp"] == cp:
                side, why = decide(r, vals, self.week_monday)
                self.sides[r["ticker"]] = (side, why)
                decided[r["ticker"]] = {"side": side, "why": why}
        self.log({"ev": "sides", "cp": cps, "complete_t": iso(t), "markets": decided})
        with self.lock:
            for off in SNAP_OFFSETS:
                self.pending.append((t + off, cp, "complete+%ds" % int(off), t))
        self.mark_first_informed(cp, t)

    def tick(self):
        """Fire due snapshots. Called from the main loop (and the self-test)."""
        t = self.now()
        with self.lock:
            due = [p for p in self.pending if p[0] <= t]
            self.pending = [p for p in self.pending if p[0] > t]
        for fire_at, cp, label, ct in sorted(due):
            self.snapshot(cp, label, ct)

    def snapshot(self, cp, label, complete_t):
        t = self.now()
        mk = []
        tot_c = tot_d = 0.0
        n_with = 0
        for r in self.recs:
            if r["cp"] != cp:
                continue
            side, why = self.sides.get(r["ticker"], ("unknown", "not decided"))
            d = self.books.dump(r["ticker"])
            row = {"ticker": r["ticker"], "side": side, "why": why, "book": d,
                   "has_snapshot": r["ticker"] in self.books.have_snapshot}
            if side in ("yes", "no") and d is not None:
                a = self.books.asks(r["ticker"], side)
                c = sum(s for _, s in a)
                dol = sum(p * s for p, s in a)
                row.update(true_asks_le95=a, true_contracts=round(c, 2), true_dollars=round(dol, 2))
                tot_c += c
                tot_d += dol
                n_with += 1 if dol >= 20 else 0
            mk.append(row)
        self.log({"ev": "book_snap", "cp": CHOKEPOINTS[cp], "label": label, "complete_t": iso(complete_t),
                  "lag_s": round(t - complete_t, 3), "n_markets": len(mk),
                  "true_contracts_le95": round(tot_c, 2), "true_dollars_le95": round(tot_d, 2),
                  "markets_with_ge_20usd": n_with, "markets": mk})
        print("[snap] %s %s: %d markets, true-side asks<=95c $%.0f (%.0f contracts), %d markets >= $20"
              % (CHOKEPOINTS[cp], label, len(mk), tot_d, tot_c, n_with), flush=True)

    # -- websocket frames
    def on_frame(self, raw):
        try:
            m = json.loads(raw)
        except Exception:
            self.frames["unparsed"] += 1
            return
        t = m.get("type", "unknown")
        self.frames[t] += 1
        msg = m.get("msg") or {}
        gap = self.books.track_seq(m.get("sid"), m.get("seq"))
        if gap:
            self.log({"ev": "seq_gap", "sid": m.get("sid"), "gap": gap, "type": t})
        if t == "orderbook_snapshot":
            self.books.snapshot(msg)
        elif t == "orderbook_delta":
            self.books.delta(msg)
        elif t == "trade":
            self.on_trade(msg)
        elif t in ("subscribed", "ok", "error"):
            self.log({"ev": "ws_" + t, "frame": m})

    def on_trade(self, msg):
        tk = msg.get("market_ticker")
        side = msg.get("taker_side")
        try:
            yp = float(msg.get("yes_price_dollars"))
            cnt = float(msg.get("count_fp") or msg.get("count") or 0)
        except (TypeError, ValueError):
            return
        ts = msg.get("ts_ms")
        ts = ts / 1000.0 if isinstance(ts, (int, float)) else self.now()
        paid = yp if side == "yes" else round(1 - yp, 4)
        with self.lock:
            self.trades.append((ts, tk, side, paid, cnt))
        r = self.by_tk.get(tk)
        true = self.sides.get(tk, ("unknown", ""))[0]
        ev = {"ev": "trade", "ticker": tk, "taker_side": side, "paid": paid, "count": cnt,
              "ts": iso(ts), "true_side": true, "informed": true in ("yes", "no") and side == true}
        self.log(ev)
        if r and r["cp"] and ev["informed"] and cnt > 0 and not self.first_after.get(r["cp"]):
            ct = self.poller.complete_at.get(r["cp"])
            if ct is not None and ts >= ct:
                self.first_after[r["cp"]] = True
                self.log({"ev": "first_informed_trade_after_complete", "cp": CHOKEPOINTS[r["cp"]],
                          "ticker": tk, "taker_side": side, "paid": paid, "count": cnt,
                          "trade_ts": iso(ts), "lag_s": round(ts - ct, 3)})

    def mark_first_informed(self, cp, complete_t):
        """At completion the sides are known, so the buffer since start can be re-read: the first
        true-side taker trade (any size) and the first true-side burst (>= BURST_CONTRACTS in one
        second) on this chokepoint's markets, each with its lag to the layer stamp (negative = the
        trade came BEFORE the layer completed, which is what the 09-29 tape showed)."""
        with self.lock:
            tr = sorted(self.trades)
        first = None
        per_sec = collections.OrderedDict()
        for ts, tk, side, paid, cnt in tr:
            r = self.by_tk.get(tk)
            if not r or r["cp"] != cp or cnt <= 0:
                continue
            true = self.sides.get(tk, ("unknown",))[0]
            if true not in ("yes", "no") or side != true:
                continue
            if first is None:
                first = {"ticker": tk, "taker_side": side, "paid": paid, "count": cnt,
                         "trade_ts": iso(ts), "lag_s": round(ts - complete_t, 3)}
            k = int(ts)
            per_sec[k] = per_sec.get(k, 0.0) + cnt
        burst = None
        for k, c in per_sec.items():
            if c >= BURST_CONTRACTS:
                burst = {"second": iso(k), "contracts": round(c, 2), "lag_s": round(k - complete_t, 3)}
                break
        self.log({"ev": "first_informed_trade", "cp": CHOKEPOINTS[cp], "complete_t": iso(complete_t),
                  "first_true_side_trade": first, "first_true_side_burst": burst,
                  "n_trades_seen": len(tr)})
        if first is not None and first["lag_s"] >= 0 and not self.first_after.get(cp):
            self.first_after[cp] = True
            self.log(dict(first, ev="first_informed_trade_after_complete", cp=CHOKEPOINTS[cp]))


# --------------------------------------------------------------------------
# a minimal RFC 6455 client (stdlib): text frames in, masked text frames out, ping/pong, close
class WSClient:
    def __init__(self, headers, host=WS_HOST, path=WS_PATH):
        self.host, self.path, self.headers = host, path, headers
        self.sock = None
        self.wlock = threading.Lock()
        self.buf = b""

    def connect(self):
        raw = socket.create_connection((self.host, 443), timeout=15)
        ctx = ssl.create_default_context()
        s = ctx.wrap_socket(raw, server_hostname=self.host)
        key = base64.b64encode(os.urandom(16)).decode()
        lines = ["GET %s HTTP/1.1" % self.path, "Host: %s" % self.host, "Upgrade: websocket",
                 "Connection: Upgrade", "Sec-WebSocket-Key: %s" % key, "Sec-WebSocket-Version: 13",
                 "User-Agent: portwatch_rec"] + ["%s: %s" % kv for kv in self.headers.items()]
        s.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = s.recv(4096)
            if not chunk:
                raise ConnectionError("handshake: connection closed")
            resp += chunk
        head, _, rest = resp.partition(b"\r\n\r\n")
        status = head.split(b"\r\n")[0].decode(errors="replace")
        if " 101 " not in status:
            raise ConnectionError("handshake: %s %s" % (status, head[:300].decode(errors="replace")))
        want = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode())
                                .digest()).decode()
        acc = [l.split(b":", 1)[1].strip().decode() for l in head.split(b"\r\n")
               if l.lower().startswith(b"sec-websocket-accept:")]
        if not acc or acc[0] != want:
            raise ConnectionError("handshake: bad Sec-WebSocket-Accept")
        s.settimeout(30)
        self.sock, self.buf = s, rest

    def _recv(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(max(65536, n - len(self.buf)))
            if not chunk:
                raise ConnectionError("socket closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, payload, opcode=0x1):
        if isinstance(payload, str):
            payload = payload.encode()
        n = len(payload)
        hdr = bytes([0x80 | opcode])
        if n < 126:
            hdr += bytes([0x80 | n])
        elif n < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            hdr += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        body = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        with self.wlock:
            self.sock.sendall(hdr + mask + body)

    def recv_text(self):
        """Next complete text message; None for a control frame handled here. Raises on close/error.
        socket.timeout propagates so the caller can ping."""
        frag = b""
        started = False
        while True:
            try:
                b1, b2 = self._recv(2)
                started = True
                fin, op = b1 & 0x80, b1 & 0x0F
                masked, n = b2 & 0x80, b2 & 0x7F
                if n == 126:
                    n = struct.unpack(">H", self._recv(2))[0]
                elif n == 127:
                    n = struct.unpack(">Q", self._recv(8))[0]
                mk = self._recv(4) if masked else None
                data = self._recv(n)
            except socket.timeout:
                if started or frag:
                    raise ConnectionError("timeout in the middle of a frame")
                raise
            started = False
            if mk:
                data = bytes(b ^ mk[i % 4] for i, b in enumerate(data))
            if op == 0x8:
                raise ConnectionError("server close %r" % data[:64])
            if op == 0x9:
                self.send(data, 0xA)
                return None
            if op == 0xA:
                return None
            if op in (0x1, 0x2, 0x0):
                frag += data
                if fin:
                    return frag.decode(errors="replace")

    def close(self):
        try:
            self.send(b"", 0x8)
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


def ws_thread(rec, tickers, stop, auth_headers_fn):
    """Connect, subscribe to orderbook_delta + trade for `tickers`, feed frames to rec.on_frame;
    reconnect with backoff; the books are reset on every (re)connect so a stale book never survives."""
    backoff = 1
    cid = 0
    while not stop.is_set():
        ws = WSClient(auth_headers_fn())
        try:
            ws.connect()
            rec.books.reset()
            rec.log({"ev": "ws_connected", "n_tickers": len(tickers)})
            cid += 1
            ws.send(json.dumps({"id": cid, "cmd": "subscribe",
                                "params": {"channels": ["orderbook_delta", "trade"],
                                           "market_tickers": tickers}}))
            backoff = 1
            last_rx = time.time()
            while not stop.is_set():
                try:
                    txt = ws.recv_text()
                except socket.timeout:
                    if time.time() - last_rx > 120:
                        raise ConnectionError("no frame in 120 s")
                    ws.send(b"", 0x9)
                    continue
                last_rx = time.time()
                if txt is not None:
                    rec.on_frame(txt)
        except Exception as e:
            if stop.is_set():
                break
            rec.log({"ev": "ws_error", "err": repr(e)[:200], "retry_s": backoff})
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
        finally:
            ws.close()
    rec.log({"ev": "ws_stopped", "frames": dict(rec.frames), "seq_gaps": rec.books.gaps})


# --------------------------------------------------------------------------
# discovery (REST, GET only via kauth)
def discover(date_str):
    import kauth
    out = []
    for s in SERIES:
        cursor = None
        for _ in range(5):
            p = {"series_ticker": s, "status": "open", "limit": "200"}
            if cursor:
                p["cursor"] = cursor
            st, b = kauth.get("/markets", p)
            if st != 200 or not isinstance(b, dict):
                print("[discover] %s -> %s %s" % (s, st, str(b)[:120]), flush=True)
                break
            for m in b.get("markets") or []:
                if (m.get("close_time") or "").startswith(date_str):
                    out.append(m)
            cursor = b.get("cursor")
            if not cursor:
                break
            time.sleep(0.15)
        time.sleep(0.15)
    return out


def layer_newest_date():
    """One statistics query: newest `date` in the whole layer and its row count."""
    p = {"f": "json", "where": "1=1", "outStatistics": json.dumps([
        {"statisticType": "max", "onStatisticField": "date", "outStatisticFieldName": "dmax"},
        {"statisticType": "count", "onStatisticField": "ObjectId", "outStatisticFieldName": "n"}]),
        "_n": str(int(time.time() * 1000))}
    q, _, _ = LayerPoller._http_fetch("query", p)
    a = (q.get("features") or [{}])[0].get("attributes") or {}
    return {"newest_date": ms_date(a["dmax"]) if a.get("dmax") else None, "rows": a.get("n")}


# --------------------------------------------------------------------------
def run(args):
    import kauth
    date = dt.date.fromisoformat(args.date)
    sh, sm = parse_hm(args.start)
    eh, em = parse_hm(args.end)
    t_start = dt.datetime(date.year, date.month, date.day, sh, sm, tzinfo=UTC).timestamp()
    t_end = dt.datetime(date.year, date.month, date.day, eh, em, tzinfo=UTC).timestamp()
    tag = args.date.replace("-", "")
    log_path = os.path.join(RESULTS, "portwatch-rec-%s%s.jsonl" % (tag, "-dry" if args.dry_run else ""))

    markets = discover(args.date)
    recs = [classify(m) for m in markets]
    # the settlement week: the week the markets' rules name (most common), else the Monday 8 days back
    weeks = collections.Counter(r["week_monday"] for r in recs if r["week_monday"])
    week_monday = dt.date.fromisoformat(weeks.most_common(1)[0][0]) if weeks \
        else date - dt.timedelta(days=date.weekday() + 7)
    rec = Recorder(markets, week_monday, log_path, quiet=True)
    per_series = collections.Counter(r["series"] for r in recs)
    rec.log({"ev": "start", "mode": "dry" if args.dry_run else "run", "date": args.date,
             "window": [iso(t_start), iso(t_end)], "week_monday": week_monday.isoformat(),
             "weeks_seen": dict(weeks), "n_markets": len(recs), "per_series": dict(per_series),
             "pid": os.getpid(), "log": log_path})
    rec.log({"ev": "markets", "markets": recs})
    print("[start] %s markets closing %s: %s; settlement week Monday %s; log %s"
          % (len(recs), args.date, dict(per_series), week_monday, log_path), flush=True)
    try:
        nd = layer_newest_date()
        rec.log(dict(nd, ev="layer_newest"))
        print("[layer] newest date in layer %s (%s rows)" % (nd["newest_date"], nd["rows"]), flush=True)
    except Exception as e:
        rec.log({"ev": "layer_newest_error", "err": repr(e)[:200]})
    if not recs:
        print("[start] no markets -- nothing to subscribe to; polling only", flush=True)

    tickers = [r["ticker"] for r in recs]
    stop = threading.Event()
    th = threading.Thread(target=ws_thread, args=(rec, tickers, stop, lambda: kauth.headers("GET", WS_PATH)),
                          daemon=True)
    if tickers:
        th.start()

    now = time.time()
    if args.dry_run:
        poll_until, end_at = now + 20, now + 30
    else:
        poll_until, end_at = t_end, t_end + 60          # books stay up a minute past the end
        if now < t_start:
            print("[wait] polling starts at %s (in %.0f s); books are warming now"
                  % (iso(t_start), t_start - now), flush=True)
    next_poll = max(now, t_start if not args.dry_run else now)
    last_status = 0
    try:
        while time.time() < end_at:
            t = time.time()
            if t >= next_poll and t < poll_until:
                rec.poll_once()
                next_poll = max(next_poll + POLL_S, t + 0.2)
            rec.tick()
            if t - last_status >= 60:
                last_status = t
                with rec.books.lock:
                    nb = len(rec.books.have_snapshot)
                rec.log({"ev": "status", "polls": rec.poller.n // 2, "books": nb, "frames": dict(rec.frames),
                         "seq_gaps": rec.books.gaps, "complete": {CHOKEPOINTS[c]: iso(v) for c, v in
                                                                   rec.poller.complete_at.items()},
                         "trades": len(rec.trades), "pending_snaps": len(rec.pending)})
            time.sleep(0.1)
    except KeyboardInterrupt:
        rec.log({"ev": "interrupted"})
    stop.set()
    if tickers:
        th.join(timeout=5)
    with rec.books.lock:
        nb = len(rec.books.have_snapshot)
    done = {CHOKEPOINTS[c]: iso(v) for c, v in rec.poller.complete_at.items()}
    rec.log({"ev": "end", "polls": rec.poller.n // 2, "books": nb, "frames": dict(rec.frames),
             "seq_gaps": rec.books.gaps, "complete": done,
             "incomplete": [CHOKEPOINTS[c] for c in CHOKEPOINTS if c not in rec.poller.complete_at],
             "trades": len(rec.trades), "nonces_unique": len(set(rec.poller.nonces)) == len(rec.poller.nonces),
             "last_edit": rec.poller.last_edit})
    print("[end] polls %d, books with snapshot %d of %d, frames %s, seq gaps %d, trades %d, complete %s"
          % (rec.poller.n // 2, nb, len(tickers), dict(rec.frames), rec.books.gaps, len(rec.trades), done),
          flush=True)
    rec.close()


# --------------------------------------------------------------------------
def selftest():
    """A planted world: the layer fills in (6 days -> 7 days for two chokepoints -> a value change),
    a fake book, fake trades before and after completion. Checks the complete-time detection per
    chokepoint, the +0/+5/+30 s snapshots, the first-informed-trade marks, that the nonce changes on
    every poll, the side logic, and that this file sends nothing (read-only source)."""
    monday = dt.date(2026, 9, 28)
    days = week_days(monday)
    clock = [1_000_000.0]
    now = lambda: clock[0]
    T = {"suez": "KXSUEZWEEKLY-26OCT04-T270", "suez2": "KXSUEZWEEKLY-26OCT04-T280",
         "bab": "KXBABELMANDEBWEEKLY-26OCT04-T175", "peak": "KXHORMUZPEAK-26OCT04-T6",
         "max": "KXHORMUZMAX-26OCT04-OCT02", "max2": "KXHORMUZMAX-26OCT04-OCT03",
         "ships": "KXMAXSHIPSHORMUZ-26OCT01-AL5", "norm": "KXHORMUZNORM-26MAR17-B261001"}
    rules_w = "If the number of transit calls through X as reported by the IMF PortWatch is above %d from Sep 28, 2026 to Oct 4, 2026, then the market resolves to Yes."
    markets = [
        {"ticker": T["suez"], "strike_type": "greater", "floor_strike": 270, "rules_primary": rules_w % 270},
        {"ticker": T["suez2"], "strike_type": "greater", "floor_strike": 280, "rules_primary": rules_w % 280},
        {"ticker": T["bab"], "strike_type": "greater", "floor_strike": 175, "rules_primary": rules_w % 175},
        {"ticker": T["peak"], "strike_type": "greater", "floor_strike": 6,
         "rules_primary": "If the highest single-day number of transit calls through the Strait of Hormuz as reported by the IMF PortWatch is above 6 from Sep 28, 2026 to Oct 4, 2026, then the market resolves to Yes."},
        {"ticker": T["max"], "strike_type": "custom", "custom_strike": {"Day": "Oct 2, 2026"},
         "rules_primary": "If Oct 2, 2026 is the date with the highest number ..."},
        {"ticker": T["max2"], "strike_type": "custom", "custom_strike": {"Day": "Oct 3, 2026"},
         "rules_primary": "If Oct 3, 2026 is the date with the highest number ..."},
        {"ticker": T["ships"], "strike_type": "greater_or_equal", "floor_strike": 5,
         "rules_primary": "If the highest daily number of transit calls through the Strait of Hormuz as reported by the IMF PortWatch is at least 5 in Oct 2026, then the market resolves to Yes."},
        {"ticker": T["norm"], "strike_type": "custom", "custom_strike": {"date": "before October 1, 2026"},
         "rules_primary": "If the 7-day moving average ... is above 60 before October 1, 2026 ..."},
    ]
    # planted layer values: Suez sums to exactly 280 (T270 YES, T280 NO -- strict 'above');
    # Bab 190 (T175 YES); Hormuz [2,3,4,9,7,9,1]: max 9 > 6 (PEAK YES), argmax tie 10-01/10-03 -> OCT03
    # unknown, OCT02 NO; October max so far 9 >= 5 -> SHIPS YES.
    suez = [38, 47, 32, 41, 37, 48, 37]
    bab = [27, 22, 25, 31, 29, 29, 27]
    hormuz = [2, 3, 4, 9, 7, 9, 1]
    panama = [25, 32, 27, 26, 24, 25, 30]
    state = {"stage": 0}
    nonces_seen = []

    def feat(cp, i, vals):
        ms = int(dt.datetime(2026, 9, 28 + 0, tzinfo=UTC).timestamp() * 1000) + i * 86400000
        return {"attributes": {"ObjectId": 1000 + i, "date": ms, "portid": cp, "n_total": vals[i],
                               "n_cargo": vals[i] - 1, "n_tanker": 1}}

    def fake_fetch(kind, params):
        assert "_n" in params
        nonces_seen.append(params["_n"])
        if kind == "meta":
            return {"editingInfo": {"lastEditDate": 1_000_000_000, "dataLastEditDate": 1_000_000_000}}, {}, 0.01
        st = state["stage"]
        feats = []
        n_suez = 6 if st == 0 else 7
        n_bab = 6 if st <= 1 else 7
        n_hz = 6 if st <= 1 else 7
        feats += [feat("chokepoint1", i, suez) for i in range(n_suez)]
        feats += [feat("chokepoint4", i, bab) for i in range(n_bab)]
        hz = list(hormuz)
        if st >= 3:
            hz[0] = 5                     # a value change after completion
        feats += [feat("chokepoint6", i, hz) for i in range(n_hz)]
        feats += [feat("chokepoint2", i, panama) for i in range(6)]   # panama never completes
        return {"features": feats}, {"x-cache": "TCP_MISS"}, 0.02

    rec = Recorder(markets, monday, None, fetch=fake_fetch, now=now, quiet=True)
    events = []
    rec.log = lambda ev: events.append(dict(ev, t=iso(now())))     # capture instead of writing

    def evs(kind):
        return [e for e in events if e["ev"] == kind]

    # classification
    k = {r["ticker"]: r["kind"] for r in rec.recs}
    assert k[T["suez"]] == "weekly_sum" and k[T["peak"]] == "weekly_max" and k[T["max"]] == "argmax_day"
    assert k[T["ships"]] == "month_max_ge" and k[T["norm"]] == "unknown", k
    assert rec.by_tk[T["suez"]]["week_monday"] == "2026-09-28"

    # a fake book: Suez T270 has YES asks at 0.80 (300) and 0.97 (50); NO bids carry them
    rec.on_frame(json.dumps({"type": "subscribed", "id": 1, "msg": {"channel": "orderbook_delta", "sid": 7}}))
    rec.on_frame(json.dumps({"type": "orderbook_snapshot", "sid": 7, "seq": 1, "msg": {
        "market_ticker": T["suez"], "yes_dollars_fp": [["0.7000", "100.00"]],
        "no_dollars_fp": [["0.2000", "300.00"], ["0.0300", "50.00"]]}}))
    rec.on_frame(json.dumps({"type": "orderbook_snapshot", "sid": 7, "seq": 2, "msg": {
        "market_ticker": T["suez2"], "yes_dollars_fp": [["0.1000", "40.00"]],
        "no_dollars_fp": [["0.8000", "10.00"]]}}))
    rec.on_frame(json.dumps({"type": "orderbook_snapshot", "sid": 7, "seq": 3, "msg": {
        "market_ticker": T["peak"], "yes_dollars_fp": [], "no_dollars_fp": [["0.4000", "20.00"]]}}))
    # a delta: 100 more NO bids at 0.20 -> YES asks at 0.80 become 400
    rec.on_frame(json.dumps({"type": "orderbook_delta", "sid": 7, "seq": 4, "msg": {
        "market_ticker": T["suez"], "price_dollars": "0.2000", "delta_fp": "100.00", "side": "no"}}))
    # a seq gap must be logged
    rec.on_frame(json.dumps({"type": "orderbook_delta", "sid": 7, "seq": 6, "msg": {
        "market_ticker": T["suez"], "price_dollars": "0.5000", "delta_fp": "1.00", "side": "no"}}))
    assert len(evs("seq_gap")) == 1 and rec.books.gaps == 1
    assert rec.books.asks(T["suez"], "yes") == [[0.5, 1.0], [0.8, 400.0]], rec.books.asks(T["suez"], "yes")
    assert rec.books.asks(T["suez"], "no") == [[0.3, 100.0]]

    # trades BEFORE the layer completes: an uninformed 2-lot on the wrong side, then an informed
    # 150-lot burst on the true side at t0+10 (true side of T270 is YES)
    t0 = now()
    rec.on_frame(json.dumps({"type": "trade", "sid": 9, "seq": 1, "msg": {
        "market_ticker": T["suez"], "taker_side": "no", "yes_price_dollars": "0.3000",
        "count_fp": "2.00", "ts_ms": int((t0 + 5) * 1000)}}))
    rec.on_frame(json.dumps({"type": "trade", "sid": 9, "seq": 2, "msg": {
        "market_ticker": T["suez"], "taker_side": "yes", "yes_price_dollars": "0.8000",
        "count_fp": "150.00", "ts_ms": int((t0 + 10) * 1000)}}))

    # poll 1 at t0+20: everything partial -> no completion, 1 poll event, a layer_change (first load)
    clock[0] = t0 + 20
    rec.poll_once(); rec.tick()
    assert len(evs("layer_complete")) == 0 and len(evs("poll")) == 1
    assert evs("poll")[0]["rows"] == {"suez": 6, "panama": 6, "bab": 6, "hormuz": 6}, evs("poll")[0]["rows"]
    assert len(evs("layer_change")) == 1 and len(evs("layer_edit_stamp")) == 1
    # poll 2 at t0+22: Suez completes
    state["stage"] = 1
    clock[0] = t0 + 22
    rec.poll_once(); rec.tick()
    lc = evs("layer_complete")
    assert len(lc) == 1 and lc[0]["cp"] == "suez" and lc[0]["sum"] == 280, lc
    assert rec.poller.complete_at["chokepoint1"] == t0 + 22
    sides = evs("sides")[0]["markets"]
    assert sides[T["suez"]]["side"] == "yes" and sides[T["suez2"]]["side"] == "no", sides
    # the +0 snapshot fired at once with the true-side asks <= 95c: [0.5 x1, 0.8 x400] = $320.50
    sn = evs("book_snap")
    assert len(sn) == 1 and sn[0]["label"] == "complete+0s" and sn[0]["cp"] == "suez"
    row = {m["ticker"]: m for m in sn[0]["markets"]}
    assert row[T["suez"]]["true_asks_le95"] == [[0.5, 1.0], [0.8, 400.0]]
    assert abs(row[T["suez"]]["true_dollars"] - 320.5) < 1e-6, row[T["suez"]]
    assert row[T["suez2"]]["side"] == "no" and row[T["suez2"]]["true_asks_le95"] == [[0.9, 40.0]], row[T["suez2"]]
    assert sn[0]["markets_with_ge_20usd"] == 2
    # first informed trade: the 150-lot YES at t0+10, 12 s BEFORE completion; the 2-lot NO is ignored
    fi = evs("first_informed_trade")
    assert len(fi) == 1 and fi[0]["cp"] == "suez"
    assert fi[0]["first_true_side_trade"]["count"] == 150.0 and fi[0]["first_true_side_trade"]["lag_s"] == -12.0, fi
    assert fi[0]["first_true_side_burst"]["contracts"] == 150.0 and fi[0]["first_true_side_burst"]["lag_s"] == -12.0
    assert len(evs("first_informed_trade_after_complete")) == 0
    # a true-side trade AFTER completion is marked once, with its lag
    rec.on_frame(json.dumps({"type": "trade", "sid": 9, "seq": 3, "msg": {
        "market_ticker": T["suez2"], "taker_side": "no", "yes_price_dollars": "0.7000",
        "count_fp": "20.00", "ts_ms": int((t0 + 25) * 1000)}}))
    rec.on_frame(json.dumps({"type": "trade", "sid": 9, "seq": 4, "msg": {
        "market_ticker": T["suez"], "taker_side": "yes", "yes_price_dollars": "0.9000",
        "count_fp": "5.00", "ts_ms": int((t0 + 26) * 1000)}}))
    fa = evs("first_informed_trade_after_complete")
    assert len(fa) == 1 and fa[0]["ticker"] == T["suez2"] and fa[0]["lag_s"] == 3.0, fa
    tr = evs("trade")
    assert [e["informed"] for e in tr] == [False, False, True, True], [e["informed"] for e in tr]
    # +5 s snapshot fires at t0+27, not before
    clock[0] = t0 + 26.9; rec.tick()
    assert len(evs("book_snap")) == 1
    clock[0] = t0 + 27.0; rec.tick()
    assert len(evs("book_snap")) == 2 and evs("book_snap")[1]["label"] == "complete+5s"
    assert abs(evs("book_snap")[1]["lag_s"] - 5.0) < 1e-6
    # poll 3 at t0+28: Bab and Hormuz complete together -> two completions, sides for the Hormuz family
    state["stage"] = 2
    clock[0] = t0 + 28
    rec.poll_once(); rec.tick()
    lc = evs("layer_complete")
    assert [e["cp"] for e in lc] == ["suez", "bab", "hormuz"], [e["cp"] for e in lc]
    assert lc[2]["max"] == 9 and lc[2]["argmax"] == ["2026-10-01", "2026-10-03"]
    hs = {t: s["side"] for e in evs("sides") for t, s in e["markets"].items()}
    assert hs[T["bab"]] == "yes" and hs[T["peak"]] == "yes" and hs[T["ships"]] == "yes", hs
    assert hs[T["max"]] == "no" and hs[T["max2"]] == "unknown" and hs[T["norm"]] == "unknown", hs
    # the Hormuz +0 snapshot logs the unknown-side books too (no true_asks for them) and peak's asks
    hz = [e for e in evs("book_snap") if e["cp"] == "hormuz"][0]
    pr = {m["ticker"]: m for m in hz["markets"]}
    assert pr[T["peak"]]["true_asks_le95"] == [[0.6, 20.0]] and "true_asks_le95" not in pr[T["norm"]]
    assert pr[T["norm"]]["book"] is None and pr[T["norm"]]["has_snapshot"] is False
    # +30 s snapshot for Suez fires at t0+52 and not at t0+51
    clock[0] = t0 + 51; rec.tick()
    assert not [e for e in evs("book_snap") if e["label"] == "complete+30s"]
    clock[0] = t0 + 52; rec.tick()
    s30 = [e for e in evs("book_snap") if e["label"] == "complete+30s"]
    assert len(s30) == 1 and s30[0]["cp"] == "suez" and abs(s30[0]["lag_s"] - 30.0) < 1e-6
    # poll 4 at t0+54: a value change after completion is logged as layer_change with old/new
    state["stage"] = 3
    clock[0] = t0 + 54
    rec.poll_once(); rec.tick()
    ch = evs("layer_change")[-1]["changes"]
    assert ch == [{"cp": "hormuz", "date": "2026-09-28", "old": (2, 1, 1), "new": (5, 4, 1)}], ch
    assert len(evs("layer_complete")) == 3            # no re-completion
    # nonce: two per poll (query + meta), all distinct, and it reached the fetch every time
    assert len(nonces_seen) == 8 and len(set(nonces_seen)) == 8, nonces_seen
    assert rec.poller.nonces == nonces_seen
    # panama never completed and is never snapshotted
    assert "chokepoint2" not in rec.poller.complete_at
    assert not [e for e in evs("book_snap") if e["cp"] == "panama"]
    # all 12 snapshots arrive eventually (3 chokepoints x 3 offsets)
    clock[0] = t0 + 120; rec.tick()
    assert len(evs("book_snap")) == 9, len(evs("book_snap"))
    # decide(): the strict 'above', the ties, the wrong-week guard
    r = classify({"ticker": "KXSUEZWEEKLY-26OCT11-T280", "strike_type": "greater", "floor_strike": 280,
                  "rules_primary": rules_w.replace("Sep 28, 2026 to Oct 4, 2026", "Oct 5, 2026 to Oct 11, 2026") % 280})
    assert decide(r, dict(zip(days, suez)), monday)[0] == "unknown"

    # no order-sending verb anywhere in this file (tokens built by concatenation so the check does not find itself)
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    for bad in ("PO" + "ST", "/portfolio/" + "orders", "method=" + "\"P", "data" + "=body"):
        assert bad not in src, "forbidden token in source: %s" % bad
    assert re.search(r"Request\([^)]*\bdata\s*=", src) is None
    assert "websockets" + " import" not in src and "import " + "requests" not in src
    print("selftest OK: 3 completions, 9 snapshots, first-informed marks, %d distinct nonces, read-only source"
          % len(set(nonces_seen)))
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--date", default="2026-10-06")
    ap.add_argument("--start", default="11:30Z")
    ap.add_argument("--end", default="13:30Z")
    ap.add_argument("--dry-run", action="store_true",
                    help="discover tickers, poll the layer 20 s, subscribe 10 s; log to -dry only")
    args = ap.parse_args()
    if args.selftest:
        return 0 if selftest() else 1
    if os.environ.get("KALS_SELFTESTED") != "1":
        selftest()
    run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
