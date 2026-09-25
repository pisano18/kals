#!/usr/bin/env python3
"""kalshiwatch.py -- catch Kalshi changing something under us BEFORE it costs money.

WHY. Kalshi renamed an orderbook field once and 68,976,084 of 68,976,084
deltas went unparsed while every stage exited 0. Nothing here checked whether
the exchange's answers still had the shape the bot reads. This does, once an
hour, and it never trades: every Kalshi call is a signed GET through
kauth.get (GET-only by construction, and the self-test checks this file builds
no other method).

WHAT ONE SNAPSHOT TAKES (all read-only):
  1. The SHAPE (every JSON key path and its value type) of the GET answers the
     live bots make -- read off pinrun.py / pintake.py / pinracearm.py /
     livebook.py 2026-09-25:
        GET /markets?series_ticker=S&status=open&limit=4   (pinrun refresh, 15M)
        GET /markets?series_ticker=KXCRYPTOLEAD15M&status=open&limit=200 (race)
        GET /markets?series_ticker=KXBTCD&status=open  (ladder fallback path)
        GET /markets/{tk}            (pinrun settlement read: status, result)
        GET /markets/{tk}/orderbook  (pintake, pinracearm, livebook)
        GET /portfolio/balance       (pinrun sizing: balance, balance_dollars)
        GET /portfolio/orders/{oid}  (pintake order-record reconcile)
     plus GET /series/{S}, /events/{E}, /portfolio/fills, /portfolio/settlements
     (the ledger), /series/fee_changes, /events/fee_changes, /exchange/status,
     /exchange/schedule. Shapes are keyed PER SERIES, so a series with no open
     market this hour is "not seen", never "removed".
  2. Per series: fee_type, fee_multiplier, settlement_timer_seconds,
     price_level_structure, price_ranges, strike_type, settlement sources,
     contract URLs, and a hash of rules_primary / rules_secondary with the
     times, dates and strikes blanked out (so a new market is not a "change"
     but a new sentence is).
  3. Public pages: the API changelog (docs.kalshi.com/changelog.md -- parsed
     into entries, including FUTURE-dated ones, each checked for field names
     our live code uses), the fee schedule PDF, and the docs pages of every
     endpoint / WebSocket channel we use.
  4. The recorder's own tape (read-only, one hour file at a time): the shape
     of the newest COMPLETE hour of each WebSocket channel, and every
     event_fee_update line naming one of our series.

WHAT COUNTS AS A CHANGE (and the guards against crying wolf):
  ALERT  a field the bot reads (its name is a quoted string in the live code)
         disappears or changes type; a fee / timer / tick / strike-type /
         settlement-source value changes; a new rules sentence; a fee change
         scheduled for one of our series; a fee override on our series in the
         tape; a new changelog entry that names a field our code uses; the fee
         schedule PDF changed; a bot endpoint answers 404/410; maintenance
         scheduled.
  WARN   a new field; a field the bot does NOT read gone two snapshots running;
         a docs page edited; a series' last_updated_ts moved; a page unreadable
         for 24 runs.
  INFO   a changelog entry that touches nothing we use.
  Not a change: a failed fetch (the old value is kept), an empty list, a null,
  a series with no open market, a new type seen only as null/"".

MEASURED ON REAL DATA 2026-09-25 (scratch runs, not in results/):
  * null, REST + pages: two real snapshots 34 s apart -> 0 alerts.
  * null, tape: 8 different real hours (2 h to 50 h back) diffed in turn
    against the real baseline -> 0 alerts. The first version raised 30 false
    WARNs there (lifecycle messages for sports markets carry per-sport
    custom_strike keys); tape rows are now kept only for our series.
  * history: 16 hours spread over the whole tape (08-25 .. 09-25) replayed in
    order -> no removed or retyped field in our markets' feed messages; one
    added field (market_lifecycle_v2 'created' gained additional_metadata.
    floor_strike by 09-05). So on real data it has only ever been shown to
    stay QUIET; the catches are the planted ones in --selftest. The first real
    catch is pre-registered: Kalshi's changelog says liquidity_dollars leaves
    market answers on 2026-10-01; the bot does not read it, so the watcher
    must WARN "field gone" for it within two snapshots of the release.

OUTPUT. Every alert is appended to results/kalshiwatch-alerts.jsonl (UTC `t`,
`level`, `kind`, `msg` in plain words with times in ET) and printed as a loud
line. It does NOT send Telegram. The hook for research/pinphone.py (not
edited here) is ONE line in Phone.alerts_tick():

    for m in kalshiwatch.poll_alerts(self): self.muted or self.say(m)

poll_alerts keeps its read offset on the object it is given, learns the file
end on the first call without sending the backlog (pinphone's own rule), and
returns only ALERT-level messages by default. Importing this module does not
load the API key.

RUN.
    python research/kalshiwatch.py --selftest
    python research/kalshiwatch.py              # one snapshot now, then exit
    python research/kalshiwatch.py --loop       # every hour until the stop file
Stop file: results/kalshiwatch.stop (checked every 10 s). State:
results/kalshiwatch-state.json (last snapshot + everything ever seen).
"""
import argparse
import ast
import datetime
import gzip
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
ALERTS = os.path.join(RESULTS, "kalshiwatch-alerts.jsonl")
STATE = os.path.join(RESULTS, "kalshiwatch-state.json")
STOP = os.path.join(RESULTS, "kalshiwatch.stop")
TAPE = r"C:\kals\kalshi_data"
LIVE_SOURCES = ("pinrun.py", "pintake.py", "livebook.py", "pinracearm.py")

FALLBACK_15M = ["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
                "KXBNB15M", "KXBCH15M", "KXZEC15M", "KXHYPE15M", "KXNEAR15M",
                "KXADA15M"]
RACE = "KXCRYPTOLEAD15M"
LADDER = "KXBTCD"

UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/126 Safari/537.36"),
      "Accept": "text/html,text/markdown,application/pdf,*/*"}
DOCS = "https://docs.kalshi.com/"
CHANGELOG_URL = DOCS + "changelog.md"
FEE_PDF_URL = "https://kalshi.com/docs/kalshi-fee-schedule.pdf"
DOC_PAGES = {   # endpoint / channel -> docs page (titles read from llms.txt 2026-09-25)
    "Get Markets": "api-reference/market/get-markets.md",
    "Get Market": "api-reference/market/get-market.md",
    "Get Market Orderbook": "api-reference/market/get-market-orderbook.md",
    "Get Series": "api-reference/market/get-series.md",
    "Get Event": "api-reference/events/get-event.md",
    "Get Balance": "api-reference/portfolio/get-balance.md",
    "Get Order": "api-reference/orders/get-order.md",
    "Create Order (V2)": "api-reference/orders/create-order-v2.md",
    "Cancel Order (V2)": "api-reference/orders/cancel-order-v2.md",
    "Get Settlements": "api-reference/portfolio/get-settlements.md",
    "Get Fills": "api-reference/portfolio/get-fills.md",
    "Get Series Fee Changes": "api-reference/exchange/get-series-fee-changes.md",
    "Get Event Fee Changes": "api-reference/events/get-event-fee-changes.md",
    "WS Orderbook Updates": "websockets/orderbook-updates.md",
    "WS Market Ticker": "websockets/market-ticker.md",
    "WS Public Trades": "websockets/public-trades.md",
    "WS CF Benchmarks Value": "websockets/cfbenchmarks-value.md",
    "WS Market & Event Lifecycle": "websockets/market-and-event-lifecycle.md",
    "Rate Limits": "getting_started/rate_limits.md",
    "Fee Rounding": "getting_started/fee_rounding.md",
    "Orderbook Responses": "getting_started/orderbook_responses.md",
    "Market Lifecycle": "getting_started/market_lifecycle.md",
}
TAPE_CHANNELS = ("orderbook_delta", "orderbook_snapshot", "ticker", "trade",
                 "cfbenchmarks_value", "market_lifecycle_v2", "event_lifecycle")
TAPE_LINES = 3000          # per channel per snapshot -- enough for every message type

# values whose change is an ALERT; anything else in `values` is a WARN
ALERT_VALUES = {"fee_type", "fee_multiplier", "settlement_timer_seconds",
                "price_level_structure", "price_ranges", "strike_type",
                "market_type", "notional_value_dollars", "settlement_sources",
                "exchange_index", "round_digits", "custom_strike_keys",
                "open_to_close_s", "close_to_expected_exp_s", "can_close_early",
                "standard_hours_sha",
                "collateral_return_type"}
MEANING = {
    "fee_type": "this changes what every trade costs",
    "fee_multiplier": "this changes what every trade costs",
    "settlement_timer_seconds": "how long after the close the result is fixed",
    "price_level_structure": "the price steps -- which prices we are allowed to bid",
    "price_ranges": "the price steps -- which prices we are allowed to bid",
    "strike_type": "how the strike is compared (above / at least)",
    "settlement_sources": "where the settlement price comes from",
    "exchange_index": "which shard orders must be routed to -- the bot sends this on every order",
    "round_digits": "how the settlement average is rounded",
    "notional_value_dollars": "what one contract pays",
    "trading_active": "whether Kalshi is accepting trades",
    "exchange_active": "whether Kalshi is open",
}
GENERIC_IDS = {"ticker", "max", "min", "sum", "false", "true", "yes", "no", "side",
               "price", "count", "status", "type", "id", "data", "msg", "limit",
               "cursor", "action", "market", "markets", "event", "series", "sid",
               "seq", "subaccount"}
_MONTHS = ("January|February|March|April|May|June|July|August|September|October|"
           "November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec")


# ---------------------------------------------------------------- small helpers
def utc_iso(epoch):
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def et_offset(epoch):
    """US Eastern offset in seconds for a UTC epoch: EDT (-4 h) from 2 AM local
    on the 2nd Sunday of March to 2 AM local on the 1st Sunday of November."""
    y = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).year

    def nth_sunday(month, n):
        d = datetime.datetime(y, month, 1, tzinfo=datetime.timezone.utc)
        d += datetime.timedelta(days=(6 - d.weekday()) % 7 + 7 * (n - 1))
        return d
    start = nth_sunday(3, 2) + datetime.timedelta(hours=7)    # 2 AM EST = 07Z
    end = nth_sunday(11, 1) + datetime.timedelta(hours=6)     # 2 AM EDT = 06Z
    t = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc)
    return -4 * 3600 if start <= t < end else -5 * 3600


def et_str(epoch):
    t = datetime.datetime.fromtimestamp(epoch + et_offset(epoch), datetime.timezone.utc)
    return t.strftime("%b %d %I:%M %p ET").replace(" 0", " ")


def iso_epoch(s):
    try:
        s = str(s).replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(s).timestamp()
    except (TypeError, ValueError):
        return None


def sha(x):
    if not isinstance(x, (bytes, bytearray)):
        x = json.dumps(x, sort_keys=True).encode() if not isinstance(x, str) else x.encode()
    return hashlib.sha256(x).hexdigest()[:16]


def norm_rules(text):
    """Blank out what legitimately differs market to market -- dates, clock
    times, time zones, numbers -- so only a new SENTENCE changes the hash."""
    t = str(text or "")
    t = re.sub(r"\b(%s)\.?\s+\d{1,2}(st|nd|rd|th)?,?\s+\d{4}" % _MONTHS, "DATE", t)
    t = re.sub(r"\b(%s)\.?\s+\d{1,2}\b" % _MONTHS, "DATE", t)
    t = re.sub(r"\b\d{1,2}(:\d{2})?\s*(AM|PM|am|pm)\b", "TIME", t)
    t = re.sub(r"\b(EDT|EST|ET|UTC)\b", "TZ", t)
    t = re.sub(r"\$?\d[\d,]*(\.\d+)?", "#", t)
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------- shapes
def tname(v, key=""):
    """Type label. Numbers are one type (84000 and 84000.5 are the same field).
    Numeric strings in fixed-point fields (*_dollars, *_fp, orderbook arrays)
    carry their decimal count, because "0.9600" -> "0.96" or -> "96" is exactly
    the kind of silent change that breaks a parser."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        if v == "":
            return "str:empty"
        m = re.fullmatch(r"-?\d+(?:\.(\d+))?", v)
        if m:
            if key.endswith("_dollars") or key.endswith("_fp"):
                return "str:dec%d" % len(m.group(1) or "")
            return "str:num"
        return "str"
    if isinstance(v, dict):
        return "dict"
    if isinstance(v, list):
        return "list"
    return type(v).__name__


QUIET = {"null", "str:empty"}      # a value that is absent-ish, never a "new type"


def shape_into(obj, out, cap=60):
    """Add obj's {path: set(types)} into out. List elements share one path
    '[]'; the fixed-point context (last dict key) flows into list elements."""
    def walk(v, p, key):
        out.setdefault(p, set()).add(tname(v, key))
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, p + "." + str(k), str(k))
        elif isinstance(v, list):
            for x in v[:cap]:
                walk(x, p + "[]", key)
    walk(obj, "", "")
    return out


def leaf_of(path):
    seg = path.rsplit(".", 1)[-1]
    return seg.replace("[]", "")


def parent_of(path):
    if path.endswith("[]"):
        return path[:-2]
    return path.rsplit(".", 1)[0] if "." in path else ""


# ---------------------------------------------------------------- live code ids
def live_ids(root=HERE, files=LIVE_SOURCES):
    """Every quoted identifier in the live bots' source: if Kalshi removes a
    field with one of these names, the bot is the one reading it."""
    ids = set()
    for f in files:
        try:
            with open(os.path.join(root, f), encoding="utf-8", errors="replace") as fh:
                ids.update(re.findall(r"""["']([A-Za-z_][A-Za-z0-9_]{2,40})["']""", fh.read()))
        except OSError:
            pass
    return ids


def series_15m(root=HERE):
    """pinrun's own SERIES_TO_INDEX keys, read as text (never imported)."""
    try:
        with open(os.path.join(root, "pinrun.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.index("\nSERIES_TO_INDEX = {") + 1
        j = src.index("}", i) + 1
        return sorted(ast.literal_eval(src[i:j].split("=", 1)[1].strip()))
    except (OSError, ValueError, SyntaxError):
        return list(FALLBACK_15M)


# ---------------------------------------------------------------- fetchers
def kalshi_get(path, params=None):
    sys.path.insert(0, HERE)
    import kauth                                    # lazy: import never loads the key
    return kauth.get(path, params)


def web_fetch(url, timeout=25):
    """(status, bytes, headers). GET only; a failure is a status, never a raise."""
    try:
        req = urllib.request.Request(url, headers=UA, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, b"", {}
    except Exception as e:                                      # noqa: BLE001
        return -1, str(e)[:200].encode(), {}


# ---------------------------------------------------------------- changelog
def parse_changelog(text):
    """[(label, tags, title, ids)] from the Mintlify <Update> blocks."""
    out = []
    for blk in re.findall(r"<Update\b(.*?)</Update>", text, re.S):
        lab = re.search(r'label="([^"]*)"', blk)
        tags = re.search(r"tags=\{\[([^\]]*)\]\}", blk)
        title = re.search(r'title:\s*"([^"]*)"', blk)
        ids = set()
        for x in re.findall(r"`([A-Za-z_][A-Za-z0-9_./{}-]*)`", blk):
            ids.update(p for p in re.split(r"[./{}-]", x) if p)
        out.append({"label": lab.group(1) if lab else "",
                    "tags": [t.strip().strip('"') for t in tags.group(1).split(",")] if tags else [],
                    "title": title.group(1) if title else blk.strip()[:80],
                    "ids": sorted(ids),
                    "breaking": "breaking" in blk.lower()})
    return out


def label_epoch(label):
    try:
        return datetime.datetime.strptime(label.strip(), "%B %d, %Y").replace(
            tzinfo=datetime.timezone.utc).timestamp()
    except ValueError:
        return None


def entry_key(e):
    return e["label"] + " | " + e["title"]


def touches(e, ids):
    """Field names in the entry that our live code uses -- only for entries
    about the exchange we trade (Predictions) over REST or WebSocket. A
    Margin-only or FIX-only entry cannot touch us (real run 2026-09-25: a
    Margin perps entry named `ts_ms`)."""
    tags = set(e.get("tags") or [])
    if tags and ("Predictions" not in tags or not tags & {"REST", "WebSocket"}):
        return []
    return sorted(i for i in e["ids"] if i in ids and i not in GENERIC_IDS and len(i) >= 4)


# ---------------------------------------------------------------- tape
def newest_complete(chan_dir, now):
    """The newest hour file whose hour is over (the current one is being written)."""
    cur = time.strftime("%Y%m%dT%H", time.gmtime(now))
    try:
        names = sorted(n for n in os.listdir(chan_dir)
                       if re.fullmatch(r"\d{8}T\d{2}\.jsonl\.gz", n) and n[:11] < cur)
    except OSError:
        return None
    return names[-1] if names else None


def read_gz_lines(path, cap):
    """Stream up to cap parsed dict lines. A torn last block ends the read, it
    does not raise. Returns (rows, error-or-None)."""
    rows, err = [], None
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                try:
                    d = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(d, dict):
                    rows.append(d)
                if len(rows) >= cap:
                    break
    except (EOFError, zlib.error, OSError) as e:
        err = "%s: %s" % (type(e).__name__, str(e)[:80])
    return rows, err


def tape_is_ours(d, pref):
    """A message about a market is kept only if the market is one of ours
    (REAL-DATA NULL 2026-09-25: market_lifecycle_v2 'created' carries a
    custom_strike whose keys differ per sport -- 30 false WARNs over 8 hours
    before this filter). A message naming no market (the index feed) is kept."""
    m = d.get("msg")
    if not isinstance(m, dict):
        return True
    for k in ("market_ticker", "event_ticker", "ticker", "series_ticker"):
        v = m.get(k)
        if isinstance(v, str) and v:
            return v.split("-")[0] in pref
    return True


def tape_root(d):
    m = d.get("msg")
    r = "ws:" + str(d.get("type"))
    if isinstance(m, dict) and isinstance(m.get("event_type"), str):
        r += "/" + m["event_type"]
    return r


# ---------------------------------------------------------------- the snapshot
def snapshot(get=None, fetch=None, tape=TAPE, now=None, s15=None, fee_tape_seen=None,
             ours=None, pause=0.25):
    """Collect one snapshot. Returns a dict; no diffing, no writing."""
    get = get or kalshi_get
    fetch = fetch or web_fetch
    now = time.time() if now is None else now
    s15 = s15 if s15 is not None else series_15m()
    ours = ours or (list(s15) + [RACE, LADDER])
    snap = {"t": utc_iso(now), "shapes": {}, "values": {}, "rules": {}, "calls": {},
            "fee_changes": [], "maintenance": [], "pages": {}, "changelog": [],
            "tape": {}, "fee_tape_hits": [], "fee_tape_seen": dict(fee_tape_seen or {}),
            "errors": []}

    def call(label, root, path, params=None, bot=False):
        try:
            st, b = get(path, params)
        except Exception as e:                                  # noqa: BLE001
            st, b = -1, str(e)[:120]
        snap["calls"][root] = {"label": label, "path": path, "status": st, "bot": bot}
        if pause:
            time.sleep(pause)
        if st == 200 and isinstance(b, dict):
            snap["shapes"][root] = shape_into(b, {})
            return b
        snap["errors"].append("%s %s -> %s" % (label, path, st))
        return None

    def put(where, field, v):
        snap["values"]["%s|%s" % (where, field)] = v

    def market_values(where, ms, durations=True):
        acc = {}
        for m in ms:
            cs = m.get("custom_strike")
            row = {"settlement_timer_seconds": m.get("settlement_timer_seconds"),
                   "price_level_structure": m.get("price_level_structure"),
                   "price_ranges": json.dumps(m.get("price_ranges"), sort_keys=True),
                   "strike_type": m.get("strike_type"),
                   "market_type": m.get("market_type"),
                   "notional_value_dollars": m.get("notional_value_dollars"),
                   "can_close_early": m.get("can_close_early"),
                   "exchange_index": m.get("exchange_index"),
                   "custom_strike_keys": sorted(cs) if isinstance(cs, dict) else None,
                   "round_digits": cs.get("round_digits") if isinstance(cs, dict) else None}
            if durations:
                c, o = iso_epoch(m.get("close_time")), iso_epoch(m.get("open_time"))
                x = iso_epoch(m.get("expected_expiration_time"))
                row["open_to_close_s"] = int(c - o) if c and o else None
                row["close_to_expected_exp_s"] = int(x - c) if c and x else None
            for k, v in row.items():
                acc.setdefault(k, set()).add(json.dumps(v, sort_keys=True))
        for k, vs in acc.items():
            vs = sorted(vs)
            put(where, k, json.loads(vs[0]) if len(vs) == 1 else [json.loads(v) for v in vs])

    def rules_of(series, ms):
        for fld in ("rules_primary", "rules_secondary"):
            hs = {}
            for m in ms:
                n = norm_rules(m.get(fld))
                if n:
                    hs[sha(n)] = n[:400]
            if hs:
                snap["rules"]["%s|%s" % (series, fld)] = hs

    # 1-2. series, markets, the reads the bot makes
    for s in ours:
        b = call("GET /series/%s" % s, "series[%s]" % s, "/series/" + s)
        se = (b or {}).get("series") if b else None
        if isinstance(se, dict):
            where = "series[%s]" % s
            for k in ("fee_type", "fee_multiplier", "frequency", "contract_url",
                      "contract_terms_url", "exchange_index", "last_updated_ts"):
                put(where, k, se.get(k))
            put(where, "settlement_sources",
                json.dumps(se.get("settlement_sources"), sort_keys=True))
            ii = ((se.get("product_metadata") or {}).get("important_info") or {})
            put(where, "important_info", (ii.get("markdown") or "")[:600])
    first = {}
    for s in ours:
        if s == LADDER:
            params = {"series_ticker": s, "status": "open", "limit": "20"}
        elif s == RACE:
            params = {"series_ticker": s, "status": "open", "limit": "200"}
        else:
            params = {"series_ticker": s, "status": "open", "limit": "4"}
        b = call("GET /markets (%s open)" % s, "markets[%s]" % s, "/markets", params, bot=True)
        ms = [m for m in ((b or {}).get("markets") or []) if isinstance(m, dict)]
        if ms:
            first[s] = ms[0]
            market_values("markets[%s]" % s, ms, durations=(s != LADDER))
            rules_of(s, ms)
    btc = s15[0] if s15 else None
    btc = "KXBTC15M" if "KXBTC15M" in first else btc
    if btc in first:
        tk = first[btc].get("ticker")
        call("GET /markets/{ticker} (open)", "market[open]", "/markets/%s" % tk, bot=True)
        call("GET /markets/{ticker}/orderbook (15M)", "orderbook[15M]",
             "/markets/%s/orderbook" % tk, {"depth": "5"}, bot=True)
        ev = first[btc].get("event_ticker")
        if ev:
            b = call("GET /events/{event}", "event[15M]", "/events/%s" % ev)
            e = (b or {}).get("event") if b else None
            if isinstance(e, dict):
                put("event[15M]", "settlement_sources",
                    json.dumps(e.get("settlement_sources"), sort_keys=True))
                put("event[15M]", "collateral_return_type", e.get("collateral_return_type"))
                put("event[15M]", "mutually_exclusive", e.get("mutually_exclusive"))
    for s, root in ((RACE, "orderbook[race]"), (LADDER, "orderbook[ladder]")):
        if s in first:
            call("GET /markets/{ticker}/orderbook (%s)" % s, root,
                 "/markets/%s/orderbook" % first[s].get("ticker"), {"depth": "5"}, bot=True)
    if btc:
        b = call("GET /markets (settled)", "markets[settled]", "/markets",
                 {"series_ticker": btc, "status": "settled", "limit": "2"}, bot=True)
        ms = (b or {}).get("markets") or [] if b else []
        if ms and isinstance(ms[0], dict) and ms[0].get("ticker"):
            call("GET /markets/{ticker} (settled)", "market[settled]",
                 "/markets/%s" % ms[0]["ticker"], bot=True)
    # fee changes Kalshi has SCHEDULED -- the earliest warning there is
    b = call("GET /series/fee_changes", "series_fee_changes", "/series/fee_changes")
    items = []
    for v in (b or {}).values() if b else []:
        if isinstance(v, list):
            items.extend(x for x in v if isinstance(x, dict))
    cursor, pages = None, 0
    while pages < 3:
        b = call("GET /events/fee_changes", "event_fee_changes", "/events/fee_changes",
                 {"cursor": cursor} if cursor else None)
        pages += 1
        if not b:
            break
        for v in b.values():
            if isinstance(v, list):
                items.extend(x for x in v if isinstance(x, dict))
        cursor = b.get("cursor")
        if not cursor:
            break
    pat = re.compile(r"\b(%s)\b" % "|".join(re.escape(s) for s in ours))
    for x in items:
        if pat.search(json.dumps(x)):
            snap["fee_changes"].append(x)
    # exchange
    b = call("GET /exchange/status", "exchange_status", "/exchange/status")
    if b:
        put("exchange", "trading_active", b.get("trading_active"))
        put("exchange", "exchange_active", b.get("exchange_active"))
    b = call("GET /exchange/schedule", "exchange_schedule", "/exchange/schedule")
    if b:
        sc = b.get("schedule") or {}
        put("exchange", "standard_hours_sha", sha(sc.get("standard_hours")))
        snap["maintenance"] = [w for w in (sc.get("maintenance_windows") or [])
                               if isinstance(w, dict)]
    # portfolio: SHAPES ONLY -- no value from these is stored anywhere
    call("GET /portfolio/balance", "balance", "/portfolio/balance", bot=True)
    b = call("GET /portfolio/orders", "orders", "/portfolio/orders", {"limit": "1"})
    od = ((b or {}).get("orders") or [None])[0] if b else None
    if isinstance(od, dict) and od.get("order_id"):
        call("GET /portfolio/orders/{id}", "order[record]",
             "/portfolio/orders/%s" % od["order_id"], bot=True)
    call("GET /portfolio/fills", "fills", "/portfolio/fills", {"limit": "1"})
    call("GET /portfolio/settlements", "settlements", "/portfolio/settlements",
         {"limit": "1"}, bot=True)

    # 3. public pages
    st, body, hd = fetch(CHANGELOG_URL)
    if st == 200 and body:
        txt = body.decode("utf-8", "replace")
        snap["pages"]["changelog"] = {"status": st, "sha": sha(txt), "bytes": len(body)}
        snap["changelog"] = parse_changelog(txt)
    else:
        snap["pages"]["changelog"] = {"status": st}
    st, body, hd = fetch(FEE_PDF_URL)
    if st == 200 and body[:5] == b"%PDF-":
        snap["pages"]["fee_schedule_pdf"] = {"status": st, "sha": sha(bytes(body)),
                                             "bytes": len(body),
                                             "last_modified": hd.get("last-modified")}
    else:
        snap["pages"]["fee_schedule_pdf"] = {"status": st}
    for name, rel in DOC_PAGES.items():
        st, body, hd = fetch(DOCS + rel)
        if st == 200 and body:
            txt = body.decode("utf-8", "replace")
            txt = re.sub(r"(?m)^\s*version:\s*\S+\s*$", "", txt)   # global spec version
            snap["pages"]["doc:" + name] = {"status": st, "sha": sha(txt), "bytes": len(body)}
        else:
            snap["pages"]["doc:" + name] = {"status": st}
        if pause:
            time.sleep(pause)

    # 4. the recorder's tape (read-only)
    pref = set(ours)
    for ch in TAPE_CHANNELS:
        d = os.path.join(tape, ch)
        fn = newest_complete(d, now)
        if not fn:
            snap["tape"][ch] = {"file": None}
            continue
        rows, err = read_gz_lines(os.path.join(d, fn), TAPE_LINES)
        kept = 0
        for r in rows:
            if not tape_is_ours(r, pref):
                continue                    # lifecycle covers ALL of Kalshi: sports keys vary
            kept += 1
            # _rx_ms, _seq_gap, ...: the COLLECTOR's annotations, not Kalshi's fields
            r = {k: v for k, v in r.items() if not str(k).startswith("_")}
            shape_into(r, snap["shapes"].setdefault(tape_root(r), {}))
        snap["tape"][ch] = {"file": fn, "lines": len(rows), "ours": kept, "err": err}
    fdir = os.path.join(tape, "event_fee_update")
    try:
        names = sorted(n for n in os.listdir(fdir) if n.endswith(".jsonl.gz"))
    except OSError:
        names = []
    pref = set(ours)
    for n in names:
        done = snap["fee_tape_seen"].get(n, 0)
        if n in snap["fee_tape_seen"] and n not in names[-3:]:
            continue                        # an old hour already read in full
        rows, err = read_gz_lines(os.path.join(fdir, n), 10 ** 6)
        for r in rows[done:]:
            m = r.get("msg") if isinstance(r.get("msg"), dict) else {}
            ev = str(m.get("event_ticker") or m.get("series_ticker") or m.get("market_ticker") or "")
            if ev.split("-")[0] in pref:
                snap["fee_tape_hits"].append({"file": n, "msg": m})
        snap["fee_tape_seen"][n] = max(done, len(rows))
    # sets -> sorted lists so the snapshot is JSON
    snap["shapes"] = {r: {p: sorted(t) for p, t in s.items()} for r, s in snap["shapes"].items()}
    return snap


# ---------------------------------------------------------------- the diff
def diff(prev, snap, ids, now=None):
    """Compare snap with the saved state. Returns (alerts, new_state)."""
    now = time.time() if now is None else now
    prev = prev or {}
    first = not prev
    alerts = []

    def alert(level, kind, msg, **kw):
        a = {"t": utc_iso(now), "level": level, "kind": kind, "msg": msg}
        a.update(kw)
        alerts.append(a)

    known = {k: set(v) for k, v in (prev.get("known_types") or {}).items()}
    pending = dict(prev.get("pending_missing") or {})
    prev_shapes = prev.get("shapes") or {}
    shapes = snap.get("shapes") or {}
    labels = {r: c.get("label", r) for r, c in (snap.get("calls") or {}).items()}

    def where(root):
        if root.startswith("ws:"):
            return "the live feed's %s messages" % root[3:]
        return "Kalshi's answer to %s" % labels.get(root, root)

    for root, paths in shapes.items():
        root_known = any(k.startswith(root + "|") for k in known)
        for p, types in paths.items():
            key = root + "|" + p
            ts = set(types)
            if key not in known:
                if root_known and not first and not (ts <= QUIET):
                    alert("WARN", "field_added",
                          "Kalshi added a field '%s' to %s. Usually harmless -- sometimes "
                          "the first half of a rename." % (leaf_of(p) or p, where(root)),
                          where=root, path=p, after=sorted(ts))
                known[key] = ts
                continue
            loud = known[key] - QUIET
            new = ts - QUIET - known[key]
            if new and loud and not first:
                read = leaf_of(p) in ids
                alert("ALERT" if read else "WARN", "type_changed",
                      "Kalshi changed the field '%s' in %s from %s to %s.%s"
                      % (leaf_of(p), where(root), "/".join(sorted(loud)), "/".join(sorted(new)),
                         " The bot reads a field with that name -- check it now." if read else ""),
                      where=root, path=p, before=sorted(loud), after=sorted(new))
            known[key] |= ts
        old = prev_shapes.get(root) or {}
        cand = set(old) | {k.split("|", 1)[1] for k in pending if k.startswith(root + "|")}
        for p in sorted(cand):
            key = root + "|" + p
            if p in paths or p.endswith("[]") or not p:
                pending.pop(key, None)
                continue
            ptypes = set(paths.get(parent_of(p)) or []) - QUIET
            if not ptypes or ptypes == {"list"}:
                continue                    # parent absent / null / empty: nothing to judge
            leaf = leaf_of(p)
            if leaf in ids:
                alert("ALERT", "field_removed",
                      "%s no longer has the field '%s'. The bot reads a field with that "
                      "name -- it may be trading blind or refusing trades. Check it now."
                      % (where(root)[0].upper() + where(root)[1:], leaf),
                      where=root, path=p)
                pending.pop(key, None)
            else:
                pending[key] = pending.get(key, 0) + 1
                if pending[key] == 2:
                    alert("WARN", "field_removed",
                          "%s has not had the field '%s' for two snapshots running. The bot "
                          "does not read it." % (where(root), leaf), where=root, path=p)
                    pending.pop(key, None)          # said once; not again
    # a bot endpoint that is suddenly not there
    gone = set(prev.get("gone_seen") or [])
    for root, c in (snap.get("calls") or {}).items():
        if c.get("status") == 200:
            gone.discard(root)
        if c.get("bot") and c.get("status") in (404, 410) and root not in gone:
            gone.add(root)
            alert("ALERT", "endpoint_gone",
                  "Kalshi answered 'not found' (%s) to %s, which the bot calls every trade "
                  "cycle. The endpoint may have moved." % (c["status"], c.get("label")),
                  where=root)
    # values
    pv = prev.get("values") or {}
    for k, v in (snap.get("values") or {}).items():
        if k in pv and pv[k] != v and not first:
            wh, fld = k.split("|", 1)
            lvl = "ALERT" if fld in ALERT_VALUES else "WARN"
            mean = MEANING.get(fld)
            alert(lvl, "value_changed",
                  "Kalshi changed %s on %s: was %s, now %s.%s"
                  % (fld, wh.replace("series[", "").replace("markets[", "").rstrip("]"),
                     json.dumps(pv[k])[:200], json.dumps(v)[:200],
                     (" That is " + mean + ".") if mean else ""),
                  where=wh, field=fld, before=pv[k], after=v)
    # rules sentences
    rk = {k: set(v) for k, v in (prev.get("rules_known") or {}).items()}
    for k, hs in (snap.get("rules") or {}).items():
        seen = rk.setdefault(k, set())
        fresh = [h for h in hs if h not in seen]
        if fresh and seen and not first:
            s, fld = k.split("|")
            alert("ALERT", "rules_changed",
                  "The settlement rules text for %s (%s) has a sentence we have never seen: "
                  "\"%s\". Read it before trusting the next trade."
                  % (s, fld.replace("_", " "), hs[fresh[0]][:300]),
                  where=s, field=fld, after=hs[fresh[0]])
        seen.update(hs)
    # scheduled fee changes on our series
    fseen = set(prev.get("fee_changes_seen") or [])
    for x in snap.get("fee_changes") or []:
        h = sha(x)
        if h not in fseen:
            when = iso_epoch(x.get("scheduled_ts") or x.get("effective_ts") or "")
            alert("ALERT", "fee_change_scheduled",
                  "Kalshi scheduled a fee change on our market %s%s: %s. Every trade's cost "
                  "is computed from the fee -- check pinrun's fee before then."
                  % (x.get("series_ticker") or x.get("event_ticker") or "?",
                     (" for " + et_str(when)) if when else "",
                     json.dumps({k: v for k, v in x.items() if "fee" in k})[:200]),
                  detail=x)
            fseen.add(h)
    # maintenance windows
    mseen = set(prev.get("maintenance_seen") or [])
    for w in snap.get("maintenance") or []:
        h = sha(w)
        if h not in mseen:
            a_, b_ = (iso_epoch(w.get(k)) for k in ("start_datetime", "end_datetime"))
            alert("ALERT", "maintenance",
                  "Kalshi scheduled maintenance%s. The bot cannot trade or hedge then."
                  % ((" from %s to %s" % (et_str(a_), et_str(b_))) if a_ and b_
                     else ": " + json.dumps(w)[:200]), detail=w)
            mseen.add(h)
    # fee overrides seen on the tape
    for hit in snap.get("fee_tape_hits") or []:
        m = hit["msg"]
        alert("ALERT", "tape_fee_override",
              "The recorder saw Kalshi override the fee on %s: %s x%s (tape file %s)."
              % (m.get("event_ticker") or m.get("series_ticker"), m.get("fee_type_override"),
                 m.get("fee_multiplier_override"), hit["file"]), detail=hit)
    # changelog
    cseen = set(prev.get("changelog_seen") or [])
    cl = snap.get("changelog") or []
    if cl:
        for e in cl:
            k = entry_key(e)
            if k in cseen:
                continue
            cseen.add(k)
            if first or not prev.get("changelog_seen"):
                continue
            hit = touches(e, ids)
            lvl = "ALERT" if hit else ("WARN" if e["breaking"] else "INFO")
            alert(lvl, "changelog_new",
                  "Kalshi's API changelog has a new entry dated %s: \"%s\".%s"
                  % (e["label"], e["title"],
                     (" It names %s, which our bot's code uses." % ", ".join(hit)) if hit
                     else (" Marked breaking." if e["breaking"] else "")),
                  entry=e)
    # pages
    pp = prev.get("pages") or {}
    pages_state = {}
    for name, cur in (snap.get("pages") or {}).items():
        old = dict(pp.get(name) or {})
        if cur.get("status") == 200 and cur.get("sha"):
            if old.get("sha") and old["sha"] != cur["sha"] and name != "changelog":
                if name == "fee_schedule_pdf":
                    alert("ALERT", "page_changed",
                          "Kalshi's fee schedule document changed (%s -> %s bytes). Read it: %s"
                          % (old.get("bytes"), cur.get("bytes"), FEE_PDF_URL), page=name)
                else:
                    alert("WARN", "page_changed",
                          "Kalshi edited the documentation page '%s' (%s)."
                          % (name[4:], DOCS + DOC_PAGES.get(name[4:], "")), page=name)
            pages_state[name] = dict(cur, fail_streak=0)
        else:
            old["fail_streak"] = int(old.get("fail_streak") or 0) + 1
            old["last_status"] = cur.get("status")
            if old["fail_streak"] == 24:
                alert("WARN", "page_unreadable",
                      "Could not read %s for 24 snapshots running (last answer %s)."
                      % (name, cur.get("status")), page=name)
            pages_state[name] = old
    state = {"t": snap.get("t"), "shapes": shapes,
             "known_types": {k: sorted(v) for k, v in known.items()},
             "pending_missing": pending, "values": dict(pv, **(snap.get("values") or {})),
             "rules_known": {k: sorted(v)[-40:] for k, v in rk.items()},
             "fee_changes_seen": sorted(fseen), "maintenance_seen": sorted(mseen),
             "gone_seen": sorted(gone),
             "changelog_seen": sorted(cseen), "pages": pages_state,
             "fee_tape_seen": snap.get("fee_tape_seen") or {},
             "errors": snap.get("errors") or []}
    return alerts, state


def upcoming(snap, ids, now):
    """Changelog entries dated today or later -- what Kalshi has announced."""
    out = []
    for e in snap.get("changelog") or []:
        t = label_epoch(e["label"])
        if t is not None and t >= now - 86400:
            out.append(dict(e, hits=touches(e, ids)))
    return out


# ---------------------------------------------------------------- output
def write_alerts(alerts, path=ALERTS):
    if not alerts:
        return
    with open(path, "a", encoding="utf-8") as fh:
        for a in alerts:
            fh.write(json.dumps(a, sort_keys=True, default=str) + "\n")


def poll_alerts(holder, path=ALERTS, levels=("ALERT",)):
    """THE PINPHONE HOOK. New alert messages since the last call, keeping the
    byte offset on `holder` (any object). The first call learns the file end
    and returns nothing, so a (re)start never replays old alerts."""
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    off = getattr(holder, "_kalshiwatch_off", None)
    if off is None or size < off:
        setattr(holder, "_kalshiwatch_off", size)
        return []
    if size == off:
        return []
    out = []
    with open(path, "rb") as fh:
        fh.seek(off)
        chunk = fh.read(size - off)
    end = chunk.rfind(b"\n") + 1               # never consume a half-written line
    for ln in chunk[:end].splitlines():
        try:
            a = json.loads(ln)
        except ValueError:
            continue
        if a.get("level") in levels:
            out.append("KALSHI CHANGED SOMETHING: " + str(a.get("msg")))
    setattr(holder, "_kalshiwatch_off", off + end)
    return out


def save_state(state, path=STATE):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True, default=str)
    os.replace(tmp, path)


def load_state(path=STATE):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def summarise(snap, alerts, ids, now):
    calls = snap["calls"]
    ok = sum(1 for c in calls.values() if c["status"] == 200)
    print("kalshiwatch snapshot %s (%s)" % (et_str(now), snap["t"]))
    print("  Kalshi GETs: %d ok of %d; shapes recorded for %d answers/channels, %d field paths"
          % (ok, len(calls), len(snap["shapes"]),
             sum(len(v) for v in snap["shapes"].values())))
    for e in snap["errors"]:
        print("    not read: " + e)
    print("  per series (fee type x multiplier | settle timer s | price steps):")
    v = snap["values"]
    for root in sorted(k for k in calls if k.startswith("markets[") and k != "markets[settled]"):
        s = root[8:-1]
        print("    %-16s %s x%s | %s | %s" % (
            s, v.get("series[%s]|fee_type" % s), v.get("series[%s]|fee_multiplier" % s),
            v.get("%s|settlement_timer_seconds" % root, "-"),
            v.get("%s|price_level_structure" % root, "- (no open market)")))
    print("  scheduled fee changes on our series: %d; maintenance windows: %d"
          % (len(snap["fee_changes"]), len(snap["maintenance"])))
    for n, p in sorted(snap["pages"].items()):
        if p.get("status") != 200:
            print("    page NOT read: %s -> %s" % (n, p.get("status")))
    pg = sum(1 for p in snap["pages"].values() if p.get("status") == 200)
    print("  public pages read: %d of %d; changelog entries parsed: %d"
          % (pg, len(snap["pages"]), len(snap["changelog"])))
    for e in upcoming(snap, ids, now):
        print("    ANNOUNCED %s: %s%s" % (e["label"], e["title"],
                                         ("  <-- names %s, used in our code" % ", ".join(e["hits"]))
                                         if e["hits"] else ""))
    for ch, t in snap["tape"].items():
        print("  tape %-20s %s %s lines%s" % (ch, t.get("file"), t.get("lines", 0),
                                            (" ERR " + t["err"]) if t.get("err") else ""))
    print("  fee overrides on our series in the recorder's fee tape: %d (files scanned %d)"
          % (len(snap["fee_tape_hits"]), len(snap["fee_tape_seen"])))
    for a in alerts:
        if a["level"] == "ALERT":
            print("!!!!!!!! KALSHIWATCH ALERT %s: %s" % (et_str(now), a["msg"]))
        else:
            print("kalshiwatch %s: %s" % (a["level"], a["msg"]))
    if not alerts:
        print("  no change against the previous snapshot" if snap.get("_had_prev")
              else "  first snapshot: baseline written, nothing to compare yet")


def run_once(state_path=STATE, alerts_path=ALERTS):
    now = time.time()
    prev = load_state(state_path)
    ids = live_ids()
    snap = snapshot(now=now, fee_tape_seen=prev.get("fee_tape_seen"))
    snap["_had_prev"] = bool(prev)
    alerts, state = diff(prev, snap, ids, now=now)
    write_alerts(alerts, alerts_path)
    save_state(state, state_path)
    summarise(snap, alerts, ids, now)
    return snap, alerts


def run_loop(every=3600, hours=None, state_path=STATE, alerts_path=ALERTS):
    if os.path.exists(STOP):
        print("kalshiwatch: stop file %s exists -- delete it to run the loop." % STOP)
        return
    end = time.time() + hours * 3600 if hours else float("inf")
    while time.time() < end:
        try:
            run_once(state_path, alerts_path)
        except Exception as e:                                  # noqa: BLE001
            print("kalshiwatch: snapshot FAILED %s: %s" % (type(e).__name__, e))
        sys.stdout.flush()
        nxt = time.time() + every
        while time.time() < nxt:
            if os.path.exists(STOP):
                print("kalshiwatch: stop file seen, exiting.")
                return
            time.sleep(10)


# ---------------------------------------------------------------- self-test
def _fake_world(v):
    """A Kalshi in which the answer is known. v: 'A' baseline, 'A2' same world
    with harmless absences, 'B' planted changes."""
    B = v == "B"
    def mk(s, i):
        m = {"ticker": "%s-26SEP250345-%d" % (s, i), "event_ticker": "%s-26SEP250345" % s,
             "close_time": "2026-09-25T07:45:00Z", "open_time": "2026-09-25T07:30:00Z",
             "expected_expiration_time": "2026-09-25T07:50:00Z",
             "status": "active", "result": "", "exchange_index": 2,
             "custom_strike": {"round_digits": "2"}, "strike_type": "greater_or_equal",
             "price_level_structure": "tapered_deci_cent", "settlement_timer_seconds": 1,
             "notional_value_dollars": "1.0000", "yes_bid_dollars": "0.9500",
             "liquidity_dollars": "0.0000", "market_type": "binary",
             "rules_primary": "If the simple average of the sixty seconds of CF Benchmarks' "
                              "BRTI before 3:45 AM EDT on Sep 25, 2026 is at least 84036.19, "
                              "then the market resolves to Yes.",
             "price_ranges": [{"start": "0.0000", "end": "0.1000", "step": "0.0010"}]}
        if v == "A2":       # a different market: other time, date, strike
            m["rules_primary"] = ("If the simple average of the sixty seconds of CF Benchmarks' "
                                  "BRTI before 11:00 PM EST on October 3, 2026 is at least "
                                  "101,250.5, then the market resolves to Yes.")
            m["close_time"], m["open_time"] = "2026-10-04T04:00:00Z", "2026-10-04T03:45:00Z"
            m["expected_expiration_time"] = "2026-10-04T04:05:00Z"
        if B:
            m["floor_strike_dollars"] = "84036.19"          # rename: floor_strike gone
            m["fee_hint"] = "x"                            # additive field
            m["rules_primary"] = m["rules_primary"].replace("sixty", "thirty")
            m.pop("liquidity_dollars")                     # not read by the bot
        else:
            m["floor_strike"] = 84036.19 + i
        return m
    calls = []

    def get(path, params=None):
        calls.append(("GET", path, dict(params or {})))
        p = params or {}
        if path.startswith("/series/") and path != "/series/fee_changes":
            s = path.split("/")[2]
            return 200, {"series": {"ticker": s, "fee_type": "quadratic",
                                    "fee_multiplier": 2 if (B and s == "KXAAA15M") else 1,
                                    "settlement_sources": [{"name": "CF Benchmarks"}],
                                    "last_updated_ts": "2026-09-18T15:20:18Z"}}
        if path == "/markets":
            s = p.get("series_ticker")
            if p.get("status") == "settled":
                return 200, {"markets": [dict(mk(s, 9), status="finalized", result="yes")]}
            if v == "A2" and s == "KXBBB15M":
                return 200, {"markets": [], "cursor": ""}        # no open market this hour
            return 200, {"markets": [mk(s, 0)], "cursor": ""}
        if path.startswith("/markets/") and path.endswith("/orderbook"):
            if v == "A2":
                return 200, {"orderbook_fp": {"yes_dollars": [], "no_dollars": [["0.9600", "10.00"]]}}
            px = 0.96 if B else "0.9600"                    # type change str -> number
            return 200, {"orderbook_fp": {"yes_dollars": [["0.0300", "5.00"]],
                                          "no_dollars": [[px, "10.00"]]}}
        if path.startswith("/markets/"):
            return 200, {"market": mk("KXAAA15M", 0)}
        if path.startswith("/events/") and path != "/events/fee_changes":
            return 200, {"event": {"settlement_sources": [{"name": "CF Benchmarks"}]}}
        if path == "/series/fee_changes":
            arr = [{"series_ticker": "KXMLBGAME", "fee_multiplier": 3}]
            if B:
                arr.append({"series_ticker": "KXAAA15M", "fee_type": "quadratic",
                            "fee_multiplier": 2, "scheduled_ts": "2026-10-01T04:00:00Z"})
            return 200, {"series_fee_change_arr": arr}
        if path == "/events/fee_changes":
            return 200, {"event_fee_changes": [], "cursor": ""}
        if path == "/exchange/status":
            return 200, {"trading_active": True, "exchange_active": True}
        if path == "/exchange/schedule":
            return 200, {"schedule": {"standard_hours": [1], "maintenance_windows": []}}
        if path == "/portfolio/balance":
            return (404, "404 page not found") if B else (200, {"balance": 100, "balance_dollars": "1.0000"})
        if path == "/portfolio/orders":
            return 200, {"orders": [{"order_id": "o1", "status": "canceled"}], "cursor": ""}
        if path.startswith("/portfolio/orders/"):
            return 200, {"order": {"order_id": "o1", "fill_count_fp": "0.00"}}
        if path in ("/portfolio/fills", "/portfolio/settlements"):
            return 200, {path.rsplit("/", 1)[1]: [], "cursor": ""}
        return 404, "404 page not found"

    cl_a = ('<Update\n  label="September 24, 2026"\n  tags={["REST"]}\n  rss={{\n'
            'title: "Old thing",\ndescription: "x"\n}}\n>\n  `tick_size` added.\n</Update>\n')
    cl_b = ('<Update\n  label="October 1, 2026"\n  tags={["REST", "Predictions"]}\n  rss={{\n'
            'title: "floor_strike renamed",\ndescription: "y"\n}}\n>\n  Breaking Change: '
            '`floor_strike` becomes `floor_strike_dollars`.\n</Update>\n'
            '<Update\n  label="October 1, 2026"\n  tags={["WebSocket", "Margin"]}\n  rss={{\n'
            'title: "perps thing",\ndescription: "m"\n}}\n>\n  `floor_strike` on perps.\n</Update>\n'
            '<Update\n  label="October 1, 2026"\n  tags={["FIX"]}\n  rss={{\n'
            'title: "FIX tag thing",\ndescription: "z"\n}}\n>\n  `ClearingBusinessDate` added.\n</Update>\n')

    def fetch(url, timeout=25):
        if url == CHANGELOG_URL:
            return 200, ((cl_b if B else "") + cl_a).encode(), {}
        if url == FEE_PDF_URL:
            if v == "A2":
                return 429, b"", {}                               # blocked: not a change
            return 200, b"%PDF-1.7 fees " + (b"v2" if B else b"v1"), {}
        return 200, b"doc page\nversion: 3.31.%d\n" % (7 if B else 1), {}   # version-only edit
    return get, fetch, calls


def _write_gz(path, rows, torn=False):
    data = gzip.compress("".join(json.dumps(r) + "\n" for r in rows).encode())
    with open(path, "wb") as fh:
        fh.write(data[:-12] if torn else data)


def selftest():
    fails = []

    def ck(cond, what):
        print("  [%s] %s" % ("ok" if cond else "FAIL", what))
        if not cond:
            fails.append(what)

    print("kalshiwatch --selftest")
    # time
    ck(et_str(iso_epoch("2026-09-25T07:45:00Z")) == "Sep 25 3:45 AM ET", "ET in September is UTC-4")
    ck(et_str(iso_epoch("2026-12-01T12:00:00Z")) == "Dec 1 7:00 AM ET", "ET in December is UTC-5")
    ck(et_offset(iso_epoch("2026-11-01T05:59:00Z")) == -4 * 3600 and
       et_offset(iso_epoch("2026-11-01T06:00:00Z")) == -5 * 3600, "the November switch lands at 06:00Z")
    # rules normalisation: a new market is not a change, a new sentence is
    r1 = "average of the sixty seconds before 3:45 AM EDT on Sep 25, 2026 is at least 84036.19"
    r2 = "average of the sixty seconds before 11:00 PM EST on October 3, 2026 is at least 101,250.5"
    ck(sha(norm_rules(r1)) == sha(norm_rules(r2)), "rules: times, dates, strikes blanked (null)")
    ck(sha(norm_rules(r1)) != sha(norm_rules(r1.replace("sixty", "thirty"))), "rules: a new word is caught")
    # shapes
    sh = shape_into({"a": 1, "b": 2.5, "c": "0.9600", "x_dollars": "0.9600", "n": None,
                     "l": [["0.03", "5.00"]], "orderbook_fp": {"yes_dollars": [["0.0300", "5.00"]]}}, {})
    ck(sh[".a"] == {"number"} and sh[".b"] == {"number"}, "shape: int and float are one type")
    ck(sh[".c"] == {"str:num"} and sh[".x_dollars"] == {"str:dec4"}, "shape: decimals only on fixed-point keys")
    ck(sh[".orderbook_fp.yes_dollars[][]"] == {"str:dec4", "str:dec2"}, "shape: book price/size decimals")
    ck(parent_of(".m[].k") == ".m[]" and leaf_of(".m[].k") == "k" and parent_of(".m[]") == ".m",
       "shape: parent/leaf")
    # GET-only by construction
    tree = ast.parse(open(os.path.abspath(__file__), encoding="utf-8").read())
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) == "Request":
            for kw in node.keywords:
                if kw.arg == "method" and not (isinstance(kw.value, ast.Constant) and kw.value.value == "GET"):
                    bad.append(ast.dump(kw))
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and \
                node.value.startswith("/portfolio/events/" + "orders"):
            bad.append(node.value)
    ck(not bad, "this file builds GET requests only and never names the order endpoint")
    # the fake world, end to end
    ids = {"floor_strike", "no_dollars", "yes_dollars", "orderbook_fp", "balance",
           "custom_strike", "round_digits", "exchange_index", "result", "price_dollars"}
    td = tempfile.mkdtemp(prefix="kwtest")
    tape = os.path.join(td, "tape")
    now = iso_epoch("2026-09-25T08:10:00Z")
    for ch in TAPE_CHANNELS + ("event_fee_update",):
        os.makedirs(os.path.join(tape, ch))
    obd = os.path.join(tape, "orderbook_delta")
    _write_gz(os.path.join(obd, "20260925T06.jsonl.gz"),
              [{"type": "orderbook_delta", "sid": 1, "seq": 1, "_rx_ms": 1,
                "msg": {"market_ticker": "KXAAA15M-X", "price_dollars": "0.9600",
                        "delta_fp": "5.00", "side": "no"}}] * 5)
    _write_gz(os.path.join(obd, "20260925T08.jsonl.gz"), [{"type": "junk"}])   # current hour
    _write_gz(os.path.join(tape, "market_lifecycle_v2", "20260925T06.jsonl.gz"),
              [{"type": "market_lifecycle_v2", "msg": {"market_ticker": "KXMLBHR-26SEP24-X",
                                                       "event_type": "created",
                                                       "additional_metadata": {"custom_strike": {"baseball_team": "SD"}}}},
               {"type": "market_lifecycle_v2", "msg": {"market_ticker": "KXAAA15M-26SEP250345-45",
                                                       "event_type": "created"}}])
    ck(newest_complete(obd, now) == "20260925T06.jsonl.gz", "tape: current hour is never read")
    fdir = os.path.join(tape, "event_fee_update")
    _write_gz(os.path.join(fdir, "20260925T01.jsonl.gz"),
              [{"type": "event_fee_update", "msg": {"event_ticker": "KXMLBHR-26SEP24",
                                                    "fee_type_override": "quadratic",
                                                    "fee_multiplier_override": 1}},
               {"type": "event_fee_update", "msg": {"event_ticker": "KXMLB15M-1215X",
                                                    "fee_type_override": "quadratic",
                                                    "fee_multiplier_override": 1}}])
    s15 = ["KXAAA15M", "KXBBB15M"]
    kw = dict(tape=tape, now=now, s15=s15, pause=0)
    g, f, calls = _fake_world("A")
    s1 = snapshot(get=g, fetch=f, **kw)
    ck(all(c[0] == "GET" for c in calls) and len(calls) > 10, "every Kalshi call is a GET (%d)" % len(calls))
    a1, st1 = diff({}, s1, ids, now=now)
    ck(a1 == [], "first snapshot: baseline, no alerts (got %d)" % len(a1))
    ck(s1["fee_tape_hits"] == [], "fee tape: MLB and '1215M' look-alike are not ours")
    lc = s1["shapes"].get("ws:market_lifecycle_v2/created") or {}
    ck(lc and not any("baseball" in p for p in lc) and s1["tape"]["market_lifecycle_v2"]["ours"] == 1,
       "tape: someone else's market leaves no shape, ours does")
    g, f, _ = _fake_world("A")
    s2 = snapshot(get=g, fetch=f, fee_tape_seen=st1["fee_tape_seen"], **kw)
    a2, st2 = diff(st1, s2, ids, now=now + 3600)
    ck(a2 == [], "NULL WORLD: same world twice, no alerts (got %s)" % [a["kind"] for a in a2])
    g, f, _ = _fake_world("A2")
    s3 = snapshot(get=g, fetch=f, fee_tape_seen=st2["fee_tape_seen"], **kw)
    a3, st3 = diff(st2, s3, ids, now=now + 7200)
    ck(a3 == [], "NULL WORLD: new market/date/strike, series with no market, empty book side, "
                 "blocked PDF, version-only doc edit -> no alerts (got %s)"
       % [(a["kind"], a.get("path") or a.get("field") or a.get("page")) for a in a3])
    ck(st3["pages"]["fee_schedule_pdf"].get("sha") == st2["pages"]["fee_schedule_pdf"]["sha"]
       and st3["pages"]["fee_schedule_pdf"]["fail_streak"] == 1, "blocked page keeps its old hash")
    # plant: a new tape hour with a renamed field, and a fee override on our series
    # (the planted snapshot runs at 11:10Z, so its newest complete hour is 10)
    _write_gz(os.path.join(obd, "20260925T10.jsonl.gz"),
              [{"type": "orderbook_delta", "sid": 1, "seq": 2,
                "msg": {"market_ticker": "KXAAA15M-X", "price": "0.9600",
                        "delta_fp": "5.00", "side": "no"}}])
    _write_gz(os.path.join(fdir, "20260925T02.jsonl.gz"),
              [{"type": "event_fee_update", "msg": {"event_ticker": "KXAAA15M-26SEP250345",
                                                    "fee_type_override": "quadratic",
                                                    "fee_multiplier_override": 2}}])
    _write_gz(os.path.join(fdir, "20260925T03.jsonl.gz"), [{"type": "x"}] * 50, torn=True)
    g, f, _ = _fake_world("B")
    s4 = snapshot(get=g, fetch=f, fee_tape_seen=st3["fee_tape_seen"], now=now + 3600 * 3,
                  tape=tape, s15=s15, pause=0)
    a4, st4 = diff(st3, s4, ids, now=now + 3600 * 3)
    got = {}
    for a in a4:
        got.setdefault((a["kind"], a["level"]), []).append(a)
    kinds = sorted(got)
    print("    planted world raised: %s" % kinds)
    rem = [a.get("path") for a in got.get(("field_removed", "ALERT"), [])]
    ck(any(p.endswith(".floor_strike") for p in rem), "RENAME: floor_strike gone -> ALERT")
    ck(any(p == ".msg.price_dollars" for p in rem), "RENAME on the live feed tape -> ALERT")
    ck(not any("liquidity_dollars" in (p or "") for p in rem) and
       ("field_removed", "WARN") not in got, "a field the bot does not read waits a second snapshot")
    ck(("field_added", "WARN") in got, "additive field -> WARN")
    tc = got.get(("type_changed", "ALERT"), [])
    ck(any(a["path"].endswith("no_dollars[][]") for a in tc), "orderbook price str -> number -> ALERT")
    vc = [a for a in got.get(("value_changed", "ALERT"), []) if a["field"] == "fee_multiplier"]
    ck(len(vc) == 1 and vc[0]["where"] == "series[KXAAA15M]", "fee_multiplier 1 -> 2 on one series -> ALERT")
    ck(len(got.get(("rules_changed", "ALERT"), [])) >= 1, "rules sentence changed -> ALERT")
    fc = got.get(("fee_change_scheduled", "ALERT"), [])
    ck(len(fc) == 1 and "KXAAA15M" in fc[0]["msg"] and "ET" in fc[0]["msg"],
       "scheduled fee change on our series -> ALERT with an ET time; MLB ignored")
    ck(len(got.get(("tape_fee_override", "ALERT"), [])) == 1, "fee override on our series in the tape -> ALERT")
    ck(len(got.get(("endpoint_gone", "ALERT"), [])) == 1, "bot endpoint 404 -> ALERT")
    cln = got.get(("changelog_new", "ALERT"), [])
    ck(len(cln) == 1 and "floor_strike" in cln[0]["msg"], "changelog entry naming our field -> ALERT")
    ck(len(got.get(("changelog_new", "INFO"), [])) == 2,
       "changelog entry touching nothing, or a Margin-only one naming our field -> INFO")
    ck(len(got.get(("page_changed", "ALERT"), [])) == 1, "fee schedule PDF changed -> ALERT")
    ck(("page_changed", "WARN") not in got, "a docs page whose only edit is the spec version -> nothing")
    allowed = {("field_removed", "ALERT"), ("field_added", "WARN"), ("type_changed", "ALERT"),
               ("type_changed", "WARN"), ("value_changed", "ALERT"), ("value_changed", "WARN"),
               ("rules_changed", "ALERT"), ("fee_change_scheduled", "ALERT"),
               ("tape_fee_override", "ALERT"), ("endpoint_gone", "ALERT"),
               ("changelog_new", "ALERT"), ("changelog_new", "INFO"), ("page_changed", "ALERT")}
    ck(set(kinds) <= allowed, "nothing unplanted fired: %s" % sorted(set(kinds) - allowed))
    ck(s4["tape"]["orderbook_delta"]["file"] == "20260925T10.jsonl.gz", "tape: the newest complete hour is read")
    ck("20260925T03.jsonl.gz" in s4["fee_tape_seen"], "a torn gzip is survived, not raised")
    # the second B snapshot: the non-read field's absence now WARNs; nothing re-alerts
    g, f, _ = _fake_world("B")
    s5 = snapshot(get=g, fetch=f, fee_tape_seen=st4["fee_tape_seen"], now=now + 3600 * 4,
                  tape=tape, s15=s15, pause=0)
    a5, st5 = diff(st4, s5, ids, now=now + 3600 * 4)
    k5 = sorted({(a["kind"], a["level"]) for a in a5})
    ck(("field_removed", "WARN") in k5 and
       all(a["path"].endswith("liquidity_dollars") for a in a5 if a["kind"] == "field_removed"
           and a["level"] == "WARN"), "second miss of an unread field -> WARN")
    ck(not any(k in k5 for k in [("value_changed", "ALERT"), ("rules_changed", "ALERT"),
                                 ("endpoint_gone", "ALERT"),
                                 ("fee_change_scheduled", "ALERT"), ("changelog_new", "ALERT"),
                                 ("tape_fee_override", "ALERT"), ("page_changed", "ALERT")]),
       "a change is announced once, not every hour (got %s)" % k5)
    # the pinphone hook
    ap = os.path.join(td, "alerts.jsonl")

    class H:
        pass
    h = H()
    write_alerts([{"level": "ALERT", "msg": "old"}], ap)
    ck(poll_alerts(h, ap) == [], "hook: first call learns the file end, sends no backlog")
    write_alerts([{"level": "WARN", "msg": "w"}, {"level": "ALERT", "msg": "fee up"}], ap)
    with open(ap, "a") as fh:
        fh.write('{"level": "ALERT", "msg": "half')          # a line still being written
    r = poll_alerts(h, ap)
    ck(r == ["KALSHI CHANGED SOMETHING: fee up"], "hook: new ALERT only, half line left for later (%s)" % r)
    with open(ap, "a") as fh:
        fh.write(' done"}\n')
    ck(poll_alerts(h, ap) == ["KALSHI CHANGED SOMETHING: half done"], "hook: the half line arrives whole")
    ck(poll_alerts(h, ap) == [], "hook: nothing new, nothing sent")
    ck("kauth" not in sys.modules, "nothing so far has imported kauth (the key loads lazily)")
    # live-code ids really come from the live code
    real = live_ids()
    ck({"floor_strike", "orderbook_fp", "custom_strike", "exchange_index"} <= real,
       "live ids: the fields the bot reads are found in its source")
    ck("liquidity_dollars" not in real, "live ids: a field the bot never reads is not in the set")
    ck("KXBTC15M" in series_15m() and len(series_15m()) >= 9, "series list read from pinrun's own map")
    try:
        import shutil
        shutil.rmtree(td)
    except OSError:
        pass
    print("SELFTEST %s (%d failure%s)" % ("PASSED" if not fails else "FAILED", len(fails),
                                          "" if len(fails) == 1 else "s"))
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--loop", action="store_true", help="snapshot every --every s until the stop file")
    ap.add_argument("--every", type=float, default=3600.0)
    ap.add_argument("--hours", type=float, default=None, help="loop at most this long")
    ap.add_argument("--state", default=STATE, help="state file (default results/)")
    ap.add_argument("--alerts", default=ALERTS, help="alerts file (default results/)")
    a = ap.parse_args(argv)
    if a.selftest:
        return 0 if selftest() else 1
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        print("kalshiwatch: self-test FAILED -- not touching the real API.")
        return 1
    if a.loop:
        run_loop(a.every, a.hours, a.state, a.alerts)
    else:
        run_once(a.state, a.alerts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
