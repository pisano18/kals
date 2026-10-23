#!/usr/bin/env python3
# VERSION: 2026-10-23-hourly-v1   (verify with: python <file> --version-check)
r"""hourly_collector.py -- READ-ONLY WebSocket recorder for the HOURLY crypto markets.

Clean-room counterpart of C:\kals\kalshi_collector.py (v4) for the hourly series
KXBTCD / KXETHD / KXSOLD. It records to a SEPARATE root, C:\kals\kalshi_data_hourly,
in the v4 record shape, so .sweep/q-2026-10-23/recorder/queue97_exact.py's rebuild
(seed from the subscribe-time orderbook_snapshot, apply deltas with the same sid and
seq > snapshot seq) works on it unchanged.

It cannot place an order. The only HTTP verb in this file is GET (the REST signer
takes no method argument), and the only WebSocket commands it can send are
subscribe / unsubscribe / update_subscription (whitelisted in _send). --selftest
scans this source for the three HTTP write verbs and for any other WebSocket cmd.

RECORD FORMAT (one JSON object per line, gzip, hourly files, UTC hour in the name)
    C:\kals\kalshi_data_hourly\<channel>\YYYYMMDDTHH.jsonl.gz
    <channel> is Kalshi's frame "type": orderbook_snapshot, orderbook_delta, trade,
    market_lifecycle_v2, event_lifecycle, subscribed, ok, error, unsubscribed.
    Each line is Kalshi's frame verbatim --
        {"type": ..., "sid": <int>, "seq": <int>, "msg": {...}, "sending_ts_ms": <int>}
    -- plus two local annotations:
        "_rx_ms"   local receive time, ms since epoch (same meaning as in v4)
        "_conn"    index of the WebSocket connection the frame arrived on (0, 1, ...).
                   Kalshi numbers sids PER CONNECTION, so with several connections a
                   (sid, seq) pair is unique only together with _conn. A single-
                   connection reader can ignore it; queue97_exact.py does.
    and, exactly as v4 does, "_seq_gap": {"expected", "got"} on a frame whose seq is
    not the previous seq + 1 for its (connection, sid). Unlike v4 the gap check sees
    every frame type that carries a seq (snapshot, ok, delta), so a snapshot that
    shares the delta sid's counter is not reported as a gap.
    orderbook_snapshot.msg carries "yes_dollars_fp" / "no_dollars_fp" lists of
    [price, size] strings when the book is non-empty (the subscribe-time snapshot);
    orderbook_delta.msg carries market_ticker, price_dollars, delta_fp, side, ts_ms.

WHAT IT SUBSCRIBES (bytes stay down by subscribing only what matters)
    Every 60 s (and 10 s after each top of the hour) one signed GET
    /markets?series_ticker=<S>&status=open&limit=1000 per series, at most ONE REST
    request every 2 s overall, every 429 logged. Rows are hourly iff the ticker's
    date part is YYMMMDDHH AND close_time - open_time <= 3700 s (the weekly markets
    also carry an HH -- e.g. KXBTCD-26OCT2317 opens 7 days before its close -- so the
    ticker alone cannot tell them apart).
    NEAR strikes: yes price (mid, or the quoted side alone when only one side is
    quoted) between 0.03 and 0.97, OR strike within 1.5 % of the ladder's implied
    centre (the strike where the yes price crosses 0.5). In the LAST 15 MINUTES of
    the hour, ALL strikes of that hour (decided strikes matter then). A market stays
    subscribed 90 s past its close so the final deltas, the determination and the
    cleared-book snapshot are on tape.
    Channels per market: orderbook_delta (Kalshi sends the snapshot on subscribe)
    and trade. market_lifecycle_v2 is subscribed once, on connection 0 (it is
    exchange-wide; it also delivers event_lifecycle frames), and only frames for
    the configured series are written (--lifecycle-all keeps every one).
    No 'ticker' channel.

MEASURED (2 x 2-minute smoke runs against the exchange, 2026-10-23 07:58-08:04Z)
    Open rows per series: KXBTCD 188 hourly + 50 weekly, KXETHD 300 + 50,
    KXSOLD 300 + 50 -> 788 hourly markets an hour. Near mode kept 25 / 69 / 51
    (145 markets, 2 connections); the last 15 minutes carried all 788 on 7
    connections, subscribed within 11 s of start. 0 REST 429s (9 GETs / run),
    0 ws errors, 0 seq gaps. Every subscribed market got a subscribe-time snapshot
    with levels (1-73 levels; a market with an EMPTY book gets a level-less one),
    and the queue97_exact rebuild applied 14,047 real deltas with 0 skips and 0
    negative levels; after the close one side of every book is empty (784/784),
    as in the 15-minute tape.
    Timing after the top of the hour: final deltas at +0 s, the cleared-book
    (level-less) snapshot at +0.7..+15 s, market_lifecycle_v2 'determined' at
    +60..+105 s and 'settled' at +125..+165 s (v4 tape, 06Z and 07Z).
    Bytes: near mode 534 deltas/s -> ~35 MB/h gzip (22 MB/h raw -> 1.2 MB gz per
    2 min); the all-strikes close phase 117 deltas/s -> ~13 MB/h gzip. Expect
    ~25-35 MB/h, 0.6-0.8 GB/day, 4-6 GB/week; the 15-minute v4 tape is 225 MB/h.
    At most 120 markets per WebSocket connection; more connections are opened as
    needed (up to --max-conns), markets never move between connections while they
    live, and a connection with nothing assigned for 5 minutes is closed.
    ONE discovery loop, ONE manager loop, one task per connection -- a reconnect
    re-subscribes that connection's own set and never spawns another loop (the v4
    refresher leaked one lookup loop per reconnect; that was its REST 429 source).

OPERATIONS
    Disk guard: refuses to start, and stops writing and exits (code 2) with a clear
    log line, when C: has < 8 GB free. One [health] line per minute. Gzip members
    are closed every 60 s and flushed every second, so a hard kill costs <= 1 s of
    tape, and on start a truncated last member left by a kill is repaired before
    anything is appended (appending behind an untrailered member made the v4 files
    unreadable). BELOW_NORMAL priority. Pid file refused when its pid is alive.

    python hourly_collector.py --selftest
    python hourly_collector.py --minutes 2 --out C:\kals\kalshi_data_hourly\smoke
    python hourly_collector.py --minutes 10080            (what the start script runs)
"""
import argparse
import asyncio
import base64
import ctypes
import gzip
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

__VERSION__ = "2026-10-23-hourly-v1"

REST_BASE = "https://api.elections.kalshi.com"
REST_PREFIX = "/trade-api/v2"
WS_PROD = "wss://api.elections.kalshi.com/trade-api/ws/v2"
WS_PATH = "/trade-api/ws/v2"
KEY_ID = "5163259c-ecb0-4966-9053-0d2776cf061e"
KEY_FILE = os.environ.get("KALSHI_KEY_FILE", r"C:\kals\kalshi.pem")
DEFAULT_OUT = r"C:\kals\kalshi_data_hourly"
DEFAULT_PIDFILE = r"C:\kals-repo\results\hourly-collector.pid"
DEFAULT_SERIES = ["KXBTCD", "KXETHD", "KXSOLD"]
DATA_CHANNELS = ["orderbook_delta", "trade"]
LIFECYCLE_CHANNEL = "market_lifecycle_v2"
ALLOWED_CMDS = ("subscribe", "unsubscribe", "update_subscription")
RECORD_KEYS = ("type", "sid", "seq", "msg", "sending_ts_ms", "_rx_ms", "_conn")
HOURLY_DATE_RE = re.compile(r"^\d{2}[A-Z]{3}\d{2}\d{2}$")      # YYMMMDDHH, e.g. 26OCT2204
MAX_HOURLY_LIFE_S = 3700


def utcnow_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(*parts):
    print(utcnow_str(), *parts, flush=True)


def below_normal_priority():
    try:
        k32 = ctypes.windll.kernel32
        k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        k32.SetPriorityClass(k32.GetCurrentProcess(), 0x4000)   # BELOW_NORMAL_PRIORITY_CLASS
        return True
    except Exception:
        return False


# ----------------------------------------------------------------------------
# pure functions (all exercised by --selftest)
# ----------------------------------------------------------------------------
def parse_ts(s):
    """Kalshi ISO-8601 ('2026-10-23T07:00:00Z') -> epoch seconds, or None."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def ticker_date_part(ticker):
    parts = (ticker or "").split("-")
    return parts[1] if len(parts) >= 2 else ""


def is_hourly_ticker(ticker):
    """Ticker rule alone: the date part carries an hour (YYMMMDDHH). NECESSARY, not
    sufficient -- the weekly markets carry one too (KXBTCD-26OCT2317 lives 7 days)."""
    return bool(HOURLY_DATE_RE.match(ticker_date_part(ticker)))


def is_hourly(ticker, open_ts=None, close_ts=None):
    """Hourly market: the ticker has the HH AND (when both times are known) the
    market lives <= 3700 s. Daily tickers (KXBTCD-26OCT23-...) fail the ticker rule;
    weekly tickers pass it and fail the life rule."""
    if not is_hourly_ticker(ticker):
        return False
    if open_ts is not None and close_ts is not None:
        return 0 < (close_ts - open_ts) <= MAX_HOURLY_LIFE_S
    return True


def to_float(x):
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def yes_price(bid, ask):
    """bid/ask in dollars. Mid when both sides are quoted; the quoted side alone when
    only one is; None when the book is empty (bid 0 / ask 1 or missing)."""
    hb = bid is not None and bid > 0.0
    ha = ask is not None and ask < 1.0
    if hb and ha:
        return (bid + ask) / 2.0
    if hb:
        return bid
    if ha:
        return ask
    return None


def implied_centre(points):
    """points: iterable of (strike, yes_price-or-None). The strike where the yes
    price crosses 0.5. Median of the strikes priced 0.35..0.65 when there are any;
    else the interpolated crossing of the first adjacent pair that straddles 0.5;
    else None."""
    pts = sorted((s, p) for s, p in points if s is not None and p is not None)
    mid = [s for s, p in pts if 0.35 <= p <= 0.65]
    if mid:
        return mid[len(mid) // 2]
    for (s0, p0), (s1, p1) in zip(pts, pts[1:]):
        if (p0 - 0.5) * (p1 - 0.5) <= 0 and p0 != p1:
            return s0 + (s1 - s0) * (p0 - 0.5) / (p0 - p1)
    return None


def select_markets(markets, now, lo=0.03, hi=0.97, near_pct=0.015, all_last_s=900,
                   grace_s=90, prev_centres=None):
    """The near-strike rule.
    markets: {ticker: {"series", "event", "strike", "bid", "ask", "close_ts"}}.
    Returns (wanted: set, prio: {ticker: sort key, lower = more important},
             info: {event: {"mode", "centre", "n", "kept", "close_ts"}}).
    A market is wanted when its hour is in its last `all_last_s` seconds (ALL
    strikes), or its yes price is within [lo, hi], or its strike is within near_pct
    of the ladder's implied centre. Closed markets stay wanted for grace_s seconds
    (final deltas, determination, cleared-book snapshot) at the lowest priority."""
    wanted, prio, info = set(), {}, {}
    by_ev = defaultdict(list)
    for tk, m in markets.items():
        if m.get("close_ts") is None or m["close_ts"] + grace_s < now:
            continue
        by_ev[m.get("event") or tk].append((tk, m))
    for ev, items in by_ev.items():
        close = items[0][1]["close_ts"]
        series = items[0][1].get("series")
        pts = [(m.get("strike"), yes_price(m.get("bid"), m.get("ask"))) for _, m in items]
        centre = implied_centre(pts)
        if centre is None and prev_centres:
            centre = prev_centres.get(series)
        if centre is None:
            strikes = sorted(s for s, _ in pts if s is not None)
            centre = strikes[len(strikes) // 2] if strikes else None
        last = (close - now) <= all_last_s
        closed = close < now
        kept = 0
        for tk, m in items:
            p = yes_price(m.get("bid"), m.get("ask"))
            s = m.get("strike")
            dist = abs(s - centre) / centre if (centre and s is not None) else 1.0
            if last or (p is not None and lo <= p <= hi) or dist <= near_pct:
                wanted.add(tk)
                prio[tk] = (100.0 if closed else 0.0) + dist
                kept += 1
        info[ev] = {"mode": "closed" if closed else ("all" if last else "near"),
                    "centre": centre, "n": len(items), "kept": kept, "close_ts": close}
    return wanted, prio, info


def plan(wanted, assigned, cap, max_conns, prio=None, home=None):
    """Partition `wanted` over connections. assigned: list of sets (one per existing
    connection). Returns (adds: list of lists, one per connection -- longer than
    `assigned` when new connections are needed; removes: list of sets; overflow:
    tickers that fit nowhere). Tickers already placed stay where they are; new ones
    go to their `home` connection when it has room, else the first with room, else a
    new connection (up to max_conns), in priority order (lower prio first)."""
    prio = prio or {}
    home = home or {}
    removes = [a - wanted for a in assigned]
    cur = [a & wanted for a in assigned]
    have = set().union(*cur) if cur else set()
    new = sorted(wanted - have, key=lambda t: (prio.get(t, 1e9), t))
    adds = [[] for _ in cur]
    overflow = []

    def room(i):
        return len(cur[i]) + len(adds[i]) < cap

    for t in new:
        h = home.get(t)
        if h is not None and h < len(cur) and room(h):
            adds[h].append(t)
            continue
        for i in range(len(cur)):
            if room(i):
                adds[i].append(t)
                break
        else:
            if len(cur) < max_conns:
                cur.append(set())
                adds.append([t])
            else:
                overflow.append(t)
    return adds, removes, overflow


def chunks(seq, n):
    seq = list(seq)
    return [seq[i:i + n] for i in range(0, len(seq), n)]


def disk_free_bytes(path):
    drive = os.path.splitdrive(os.path.abspath(path))[0] or os.path.abspath(path)
    return shutil.disk_usage(drive + os.sep if drive and not drive.endswith(os.sep) else drive).free


def disk_ok(free_bytes, min_free_gb):
    return free_bytes >= min_free_gb * 1e9


class DiskGuard(RuntimeError):
    pass


def repair_gz(path):
    """Streams a gzip file member by member. If the last member is incomplete (the
    writer was killed before closing it), rewrites the file as the complete members
    verbatim plus one new member holding the complete lines that still decoded.
    Returns (repaired, lines_salvaged, bytes_of_the_replaced_member)."""
    size = os.path.getsize(path)
    if size == 0:
        return False, 0, 0
    member_start = 0
    offset = 0
    d = zlib.decompressobj(31)
    tail = bytearray()
    carry = b""
    with open(path, "rb") as f:
        while True:
            if carry:
                data, carry = carry, b""
            else:
                data = f.read(1 << 20)
                if not data:
                    break
                offset += len(data)
            try:
                tail += d.decompress(data)
            except zlib.error:
                break
            if d.eof:
                un = d.unused_data
                member_start = offset - len(un)
                d = zlib.decompressobj(31)
                tail = bytearray()
                carry = un
    if member_start >= size:
        return False, 0, 0
    good = bytes(tail)
    cut = good.rfind(b"\n") + 1
    good = good[:cut]
    with open(path, "r+b") as f:
        f.truncate(member_start)
    if good:
        with gzip.open(path, "ab", compresslevel=4) as g:
            g.write(good)
    return True, good.count(b"\n"), size - member_start


def scan_source_for_write_verbs(src):
    """Returns [(lineno, reason, text)] for anything that could write to the
    exchange: the three HTTP write verbs (as words or method calls), a non-GET
    request method, a request body, an order path, or a WebSocket cmd outside
    ALLOWED_CMDS. The patterns are assembled from fragments so this function's own
    text is clean."""
    verbs = ["PO" + "ST", "PU" + "T", "DEL" + "ETE", "PAT" + "CH"]
    bad_words = re.compile(r"\b(" + "|".join(verbs) + r")\b")
    bad_calls = re.compile(r"\.(" + "|".join(v.lower() for v in verbs) + r")\s*\(")
    non_get = re.compile(r"method\s*=\s*[\"'](?!GET[\"'])")
    body = re.compile(r"(urlopen|Request)\([^)]*\bdata\s*=")
    order_path = re.compile(r"order" + "s\\b|create_" + "order|portfolio/" + "ord")
    cmd_re = re.compile(r"[\"']cmd[\"']\s*:\s*[\"'](\w+)[\"']")
    out = []
    for i, line in enumerate(src.splitlines(), 1):
        if bad_words.search(line):
            out.append((i, "http write verb", line.strip()))
        if bad_calls.search(line):
            out.append((i, "write method call", line.strip()))
        if non_get.search(line):
            out.append((i, "non-GET request", line.strip()))
        if body.search(line):
            out.append((i, "request body", line.strip()))
        if order_path.search(line):
            out.append((i, "order path", line.strip()))
        for m in cmd_re.finditer(line):
            if m.group(1) not in ALLOWED_CMDS:
                out.append((i, "ws cmd not allowed", line.strip()))
    return out


def annotate(frame, conn_idx, seq_state, rx_ms=None):
    """The v4 handle() annotation, on a parsed frame, in place: _rx_ms, _conn, and
    _seq_gap when this (connection, sid) skipped a seq. seq_state: {sid: last seq}
    for the connection. Returns the frame's type."""
    t = frame.get("type", "unknown")
    frame["_rx_ms"] = int(time.time() * 1000) if rx_ms is None else rx_ms
    frame["_conn"] = conn_idx
    sid, sq = frame.get("sid"), frame.get("seq")
    if sid is not None and sq is not None:
        prev = seq_state.get(sid)
        if prev is not None and sq != prev + 1:
            frame["_seq_gap"] = {"expected": prev + 1, "got": sq}
        seq_state[sid] = sq
    return t


def q97_rebuild(snap_path, delta_path):
    """Mirror of queue97_exact.py's book rebuild (recorder folder, lines 56-109):
    seed each market from the snapshot record that carries yes_dollars_fp /
    no_dollars_fp (Decimal keys, sizes > 0), then apply every delta once, in file
    order, only with the same sid and seq > the snapshot seq; a level is removed at
    size <= 0; a market with no snapshot starts empty (delta-only fallback).
    Returns {ticker: {"yes": {Decimal: Decimal}, "no": {...}, "seeded": bool}}."""
    Z = Decimal(0)
    books = {}
    if os.path.exists(snap_path):
        with gzip.open(snap_path, "rb") as f:
            for line in f:
                r = json.loads(line)
                m = r["msg"]
                if "yes_dollars_fp" not in m and "no_dollars_fp" not in m:
                    continue
                b = {"yes": {}, "no": {}, "seq": r["seq"], "sid": r["sid"], "seeded": True}
                for side, key in (("yes", "yes_dollars_fp"), ("no", "no_dollars_fp")):
                    for p, s in (m.get(key) or []):
                        if Decimal(s) > 0:
                            b[side][Decimal(p)] = Decimal(s)
                books[m["market_ticker"]] = b
    with gzip.open(delta_path, "rb") as f:
        for line in f:
            r = json.loads(line)
            m = r["msg"]
            tk = m.get("market_ticker")
            if tk is None or "delta_fp" not in m:
                continue
            b = books.get(tk)
            if b is None:
                b = books[tk] = {"yes": {}, "no": {}, "seq": -1, "sid": r.get("sid"), "seeded": False}
            if r["seq"] <= b["seq"] or r.get("sid") != b["sid"]:
                continue
            lad = b[m["side"]]
            px = Decimal(m["price_dollars"])
            s = lad.get(px, Z) + Decimal(m["delta_fp"])
            if s <= 0:
                lad.pop(px, None)
            else:
                lad[px] = s
    return books


# ----------------------------------------------------------------------------
# signer (GET only), REST client (GET only, rate limited), writer
# ----------------------------------------------------------------------------
class Signer:
    """RSA-PSS signature over ts + 'GET' + path, as kauth.py / kalshi_collector.py.
    There is no method parameter: nothing built on this class can sign anything
    but a GET."""
    def __init__(self, key_id, key_file):
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        self._hashes, self._padding = hashes, padding
        self.key_id = key_id
        with open(key_file, "rb") as f:
            self._pk = serialization.load_pem_private_key(f.read(), password=None)

    def headers(self, path):
        ts = str(int(time.time() * 1000))
        sig = self._pk.sign((ts + "GET" + path).encode(),
                            self._padding.PSS(mgf=self._padding.MGF1(self._hashes.SHA256()),
                                              salt_length=self._padding.PSS.DIGEST_LENGTH),
                            self._hashes.SHA256())
        return {"KALSHI-ACCESS-KEY": self.key_id,
                "KALSHI-ACCESS-TIMESTAMP": ts,
                "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode()}


class Rest:
    """Signed GETs, at most one every `gap` seconds across the whole process.
    Counts requests, 429s and other failures; a 429 adds `penalty` s of silence."""
    def __init__(self, signer, gap=2.0, penalty=10.0):
        self.signer, self.gap, self.penalty = signer, gap, penalty
        self.next_ok = 0.0
        self.n = self.n429 = self.nerr = 0
        self.last_429 = None

    def _get_sync(self, path, params):
        full = REST_PREFIX + path
        url = REST_BASE + full + ("?" + urllib.parse.urlencode(params) if params else "")
        req = urllib.request.Request(url, method="GET")
        for k, v in self.signer.headers(full).items():
            req.add_header(k, v)
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode()[:300]
            except Exception:
                body = ""
            return e.code, body
        except Exception as e:
            return -1, f"{type(e).__name__}: {e}"

    async def get(self, path, params=None):
        wait = self.next_ok - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        self.next_ok = time.monotonic() + self.gap
        self.n += 1
        st, body = await asyncio.to_thread(self._get_sync, path, params)
        if st == 429:
            self.n429 += 1
            self.last_429 = time.time()
            self.next_ok = time.monotonic() + self.gap + self.penalty
            log(f"[rest] 429 on GET {path} {params} (429s so far {self.n429}; pausing {self.penalty:.0f}s)")
        elif st != 200:
            self.nerr += 1
            log(f"[rest] GET {path} {params} -> {st} {str(body)[:200]}")
        return st, body


class Writer:
    r"""Hourly-rotated gzip JSONL, one stream per channel, v4 file layout
    (<root>\<channel>\YYYYMMDDTHH.jsonl.gz). Differences from v4: the gzip member is
    closed and a new one appended every `member_seconds` and the stream is flushed
    every `flush_seconds` (v4 flushed every line: ~3x the bytes); a truncated last
    member found at open is repaired first; a disk guard raises DiskGuard (and
    closes everything) when the drive's free space drops under min_free_gb."""
    def __init__(self, root, member_seconds=60, flush_seconds=1.0, min_free_gb=8.0,
                 free_fn=None, disk_check_seconds=30):
        self.root = root
        self.member_seconds, self.flush_seconds = member_seconds, flush_seconds
        self.min_free_gb = min_free_gb
        self.free_fn = free_fn or (lambda: disk_free_bytes(root))
        self.disk_check_seconds = disk_check_seconds
        self.fh, self.hour = {}, None
        self.opened_at, self.last_flush, self.start_off = {}, {}, {}
        self.repaired = set()
        self.raw_bytes = 0
        self.gz_bytes_closed = 0
        self.lines = 0
        self.lines_by_chan = defaultdict(int)
        self.last_disk_check = 0.0
        self.last_free = None
        self.halted = None

    def check_disk(self):
        free = self.free_fn()
        self.last_free = free
        if not disk_ok(free, self.min_free_gb):
            self.halted = (f"DISK GUARD: {free / 1e9:.2f} GB free on the tape drive < "
                           f"{self.min_free_gb:g} GB -- recording stopped")
            self.close()
            raise DiskGuard(self.halted)
        return free

    def _roll(self, now):
        h = datetime.fromtimestamp(now, timezone.utc).strftime("%Y%m%dT%H")
        if h != self.hour:
            self.close()
            self.hour = h

    def _open(self, chan, now):
        d = os.path.join(self.root, chan)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"{self.hour}.jsonl.gz")
        if p not in self.repaired:
            self.repaired.add(p)
            if os.path.exists(p) and os.path.getsize(p) > 0:
                try:
                    fixed, kept, replaced = repair_gz(p)
                    if fixed:
                        log(f"[writer] repaired truncated last member in {p}: kept its {kept} complete "
                            f"lines, rewrote {replaced} bytes")
                except Exception as e:
                    log(f"[writer] could not check {p}: {type(e).__name__}: {e}")
        f = gzip.open(p, "ab", compresslevel=4)
        self.fh[chan] = f
        self.opened_at[chan] = now
        self.last_flush[chan] = now
        self.start_off[chan] = f.fileobj.tell()

    def _close_chan(self, chan):
        f = self.fh.pop(chan, None)
        if f is None:
            return
        try:
            f.flush()
            self.gz_bytes_closed += max(0, f.fileobj.tell() - self.start_off.get(chan, 0))
        except Exception:
            pass
        try:
            f.close()
        except Exception:
            pass

    def write(self, chan, obj, now=None):
        if self.halted:
            raise DiskGuard(self.halted)
        now = time.time() if now is None else now
        if now - self.last_disk_check >= self.disk_check_seconds:
            self.last_disk_check = now
            self.check_disk()
        self._roll(now)
        f = self.fh.get(chan)
        if f is not None and now - self.opened_at[chan] >= self.member_seconds:
            self._close_chan(chan)
            f = None
        if f is None:
            self._open(chan, now)
            f = self.fh[chan]
        line = (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            f.write(line)
            if now - self.last_flush[chan] >= self.flush_seconds:
                f.flush()
                self.last_flush[chan] = now
        except (OSError, ValueError):
            # a dead handle must not stay in self.fh (v4 lesson): drop it, reopen next time
            try:
                self.fh.pop(chan).close()
            except Exception:
                self.fh.pop(chan, None)
            raise
        self.raw_bytes += len(line)
        self.lines += 1
        self.lines_by_chan[chan] += 1

    def gz_bytes(self):
        tot = self.gz_bytes_closed
        for chan, f in self.fh.items():
            try:
                f.flush()
                tot += max(0, f.fileobj.tell() - self.start_off.get(chan, 0))
            except Exception:
                pass
        return tot

    def flush(self):
        for chan, f in list(self.fh.items()):
            try:
                f.flush()
                self.last_flush[chan] = time.time()
            except Exception:
                pass

    def close(self):
        for chan in list(self.fh):
            self._close_chan(chan)


# ----------------------------------------------------------------------------
# the collector
# ----------------------------------------------------------------------------
class Conn:
    def __init__(self, idx):
        self.idx = idx
        self.ws = None
        self.up = False
        self.task = None
        self.retire = False
        self.assigned = set()          # tickers this connection should carry
        self.pending_add = set()       # assigned but not yet sent on the current socket
        self.pending_del = set()       # removed from assigned, delete not yet sent
        self.sids = {}                 # channel -> sid on the current socket
        self.seq = {}                  # sid -> last seq on the current socket
        self.cmd = 0
        self.connects = 0
        self.empty_since = time.time()
        self.connected_at = None


class Collector:
    def __init__(self, a):
        self.a = a
        self.series = list(a.series)
        self.prefixes = tuple(s + "-" for s in self.series)
        self.signer = Signer(a.key_id, a.key_file)
        self.rest = Rest(self.signer, gap=a.rest_gap)
        self.w = Writer(a.out, member_seconds=a.member_seconds, min_free_gb=a.min_free_gb)
        self.markets = {}              # ticker -> info (hourly only)
        self.centres = {}              # series -> last implied centre
        self.sel_info = {}
        self.home = {}                 # ticker -> conn idx it was first placed on
        self.evicted = set()           # closed markets dropped early to make room; never re-wanted
        self.conns = []
        self.overflow = 0
        self.stats = defaultdict(int)
        self.minute = defaultdict(int) # per-minute counters for the health line
        self.stop = False
        self.stop_reason = None
        self.stopped = asyncio.Event()
        self.exit_code = 0
        self.t_start = time.time()
        self.max_subs = 0
        self.last_gz = 0
        self.last_health = time.time()
        self.skipped_nonhourly = 0

    # ---------------- discovery (ONE loop) ----------------
    def ingest(self, series, m, now):
        tk = m.get("ticker")
        if not tk:
            return
        o, c = parse_ts(m.get("open_time")), parse_ts(m.get("close_time"))
        if not is_hourly(tk, o, c):
            self.skipped_nonhourly += 1
            return
        self.markets[tk] = {"series": series, "event": m.get("event_ticker") or tk,
                            "strike": to_float(m.get("floor_strike")),
                            "bid": to_float(m.get("yes_bid_dollars")),
                            "ask": to_float(m.get("yes_ask_dollars")),
                            "open_ts": o, "close_ts": c, "seen": now}

    async def discover_once(self):
        now = time.time()
        found = 0
        for series in self.series:
            if self.stop:
                return
            cursor, pages = None, 0
            while True:
                params = {"series_ticker": series, "status": "open", "limit": 1000}
                if cursor:
                    params["cursor"] = cursor
                st, body = await self.rest.get("/markets", params)
                if st != 200 or not isinstance(body, dict):
                    break
                for m in body.get("markets") or []:
                    self.ingest(series, m, now)
                    found += 1
                cursor = body.get("cursor")
                pages += 1
                if not cursor or pages >= 3:
                    break
        # forget markets long past their close that discovery no longer returns
        cutoff = now - self.a.grace_seconds - 600
        for tk in [tk for tk, m in self.markets.items()
                   if (m.get("close_ts") or 0) < cutoff]:
            self.markets.pop(tk, None)
            self.home.pop(tk, None)
        self.stats["discoveries"] += 1
        if self.a.verbose:
            log(f"[discover] rows {found} hourly tracked {len(self.markets)} "
                f"non-hourly skipped so far {self.skipped_nonhourly}")

    async def discovery_loop(self):
        while not self.stop:
            t0 = time.time()
            try:
                await self.discover_once()
            except Exception as e:
                log(f"[discover] {type(e).__name__}: {e}")
            now = time.time()
            nxt = t0 + self.a.discover_seconds
            top = (int(now // 3600) + 1) * 3600 + 10        # 10 s after the next top of the hour
            nxt = min(nxt, top)
            await asyncio.sleep(max(1.0, nxt - now))

    # ---------------- subscription manager (ONE loop) ----------------
    def new_conn(self):
        c = Conn(len(self.conns))
        self.conns.append(c)
        c.task = asyncio.create_task(self.run_conn(c))
        return c

    async def manage_once(self):
        now = time.time()
        wanted, prio, info = select_markets(
            self.markets, now, lo=self.a.band_lo, hi=self.a.band_hi,
            near_pct=self.a.near_pct / 100.0, all_last_s=self.a.all_last_minutes * 60,
            grace_s=self.a.grace_seconds, prev_centres=self.centres)
        self.sel_info = info
        for ev, i in info.items():
            if i["centre"]:
                self.centres[ev.split("-")[0]] = i["centre"]      # event ticker = <series>-<YYMMMDDHH>
        self.evicted &= set(self.markets)
        wanted -= self.evicted
        assigned = [c.assigned for c in self.conns]
        adds, removes, overflow = plan(wanted, assigned, self.a.per_conn, self.a.max_conns, prio, self.home)
        if overflow:
            # make room by evicting markets that closed > 10 s ago (their final frames are on tape)
            closed = {tk for c in self.conns for tk in c.assigned
                      if (self.markets.get(tk, {}).get("close_ts") or 0) < now - 10}
            if closed:
                self.evicted |= closed
                wanted = wanted - closed
                adds, removes, overflow = plan(wanted, assigned, self.a.per_conn, self.a.max_conns, prio, self.home)
                log(f"[manage] capacity: evicted {len(closed)} closed markets to place new ones")
        if overflow and self.overflow != len(overflow):
            log(f"[manage] capacity exhausted: {len(overflow)} wanted markets not subscribed "
                f"(max_conns {self.a.max_conns} x per_conn {self.a.per_conn})")
        self.overflow = len(overflow)
        for i, rm in enumerate(removes):
            if not rm:
                continue
            c = self.conns[i]
            never_sent = rm & c.pending_add
            c.pending_add -= rm
            c.assigned -= rm
            c.pending_del |= (rm - never_sent)
            self.stats["removed"] += len(rm)
        for i, ad in enumerate(adds):
            if not ad:
                continue
            while i >= len(self.conns):
                self.new_conn()
            c = self.conns[i]
            c.assigned |= set(ad)
            c.pending_add |= set(ad)
            c.pending_del -= set(ad)
            for t in ad:
                self.home.setdefault(t, i)
            self.stats["added"] += len(ad)
        for c in self.conns:
            if c.assigned:
                c.empty_since = None
                if c.retire or c.task is None or c.task.done():
                    c.retire = False
                    c.task = asyncio.create_task(self.run_conn(c))
            else:
                if c.empty_since is None:
                    c.empty_since = now
                if c.idx > 0 and not c.retire and now - c.empty_since > 300 and c.ws is not None:
                    c.retire = True
                    log(f"[ws{c.idx}] idle 5 min -- closing")
                    try:
                        await c.ws.close()
                    except Exception:
                        pass
            if not c.up or c.ws is None:
                continue
            if c.pending_del:
                sids = [c.sids.get(ch) for ch in DATA_CHANNELS]
                if all(s is not None for s in sids):
                    dels = sorted(c.pending_del)
                    c.pending_del.clear()
                    for sid in sids:
                        for part in chunks(dels, 100):
                            await self._send(c, "update_subscription",
                                             {"sids": [sid], "market_tickers": part, "action": "delete_markets"})
                    if self.a.verbose:
                        log(f"[ws{c.idx}] -{len(dels)} markets")
            if c.pending_add:
                adds_now = sorted(c.pending_add)
                c.pending_add.clear()
                for part in chunks(adds_now, 100):
                    await self._send(c, "subscribe", {"channels": DATA_CHANNELS, "market_tickers": part})
                if self.a.verbose:
                    log(f"[ws{c.idx}] +{len(adds_now)} markets (carrying {len(c.assigned)})")
        self.max_subs = max(self.max_subs, sum(len(c.assigned) for c in self.conns if c.up))

    async def manager_loop(self):
        while not self.stop:
            try:
                await self.manage_once()
            except Exception as e:
                log(f"[manage] {type(e).__name__}: {e}")
            await asyncio.sleep(self.a.manage_seconds)

    # ---------------- websocket (one task per connection) ----------------
    async def _send(self, c, cmd, params):
        if cmd not in ALLOWED_CMDS:
            raise RuntimeError(f"refusing WebSocket cmd {cmd!r}")
        c.cmd += 1
        await c.ws.send(json.dumps({"id": c.cmd, "cmd": cmd, "params": params}))

    async def run_conn(self, c):
        import websockets
        backoff = 1
        if c.idx > 0:
            await asyncio.sleep(min(c.idx, 5))         # stagger handshakes
        while not self.stop and not c.retire:
            try:
                hdrs = self.signer.headers(WS_PATH)
                async with websockets.connect(WS_PROD, additional_headers=hdrs, ping_interval=20,
                                              ping_timeout=20, max_size=8 * 1024 * 1024,
                                              open_timeout=20) as ws:
                    c.ws, c.up = ws, True
                    c.sids, c.seq, c.cmd = {}, {}, 0
                    c.connected_at = time.time()
                    if c.connects:
                        self.stats["reconnects"] += 1
                    c.connects += 1
                    backoff = 1
                    log(f"[ws{c.idx}] connected (connection #{c.connects}, carrying {len(c.assigned)})")
                    if c.idx == 0:
                        await self._send(c, "subscribe", {"channels": [LIFECYCLE_CHANNEL]})
                    tickers = sorted(c.assigned)
                    c.pending_add.clear()
                    c.pending_del.clear()
                    for part in chunks(tickers, 100):
                        await self._send(c, "subscribe", {"channels": DATA_CHANNELS, "market_tickers": part})
                    async for raw in ws:
                        self.handle(c, raw)
                        if self.stop:
                            break
            except DiskGuard:
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.stop or c.retire:
                    break
                log(f"[ws{c.idx}] {type(e).__name__}: {e} -- retry in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
            finally:
                c.up, c.ws = False, None
        if c.retire:
            log(f"[ws{c.idx}] closed (idle)")

    def handle(self, c, raw):
        try:
            m = json.loads(raw)
        except Exception:
            return
        t = annotate(m, c.idx, c.seq)
        self.stats[t] += 1
        self.minute[t] += 1
        if "_seq_gap" in m:
            self.stats["SEQ_GAPS"] += 1
        msg = m.get("msg") or {}
        if t == "subscribed":
            ch, sid = msg.get("channel"), msg.get("sid")
            if ch and sid is not None:
                c.sids[ch] = sid
        elif t == "error":
            self.stats["ws_errors"] += 1
            log(f"[ws{c.idx} error] {raw[:300]}")
        elif t == "orderbook_snapshot":
            if "yes_dollars_fp" in msg or "no_dollars_fp" in msg:
                self.stats["snap_levels"] += 1
                self.minute["snap_levels"] += 1
        elif t == "ticker":
            return                                   # never subscribed; never written
        elif t in (LIFECYCLE_CHANNEL, "event_lifecycle") and not self.a.lifecycle_all:
            # the lifecycle subscription is exchange-wide; keep only the configured series
            tk = msg.get("market_ticker") or msg.get("event_ticker") or ""
            if not (tk.startswith(self.prefixes) or msg.get("series_ticker") in self.series):
                self.stats["lifecycle_dropped"] += 1
                return
        try:
            self.w.write(t, m)
        except DiskGuard as e:
            self.request_stop(str(e), code=2)
            raise
        except Exception as e:
            self.stats["write_errors"] += 1
            if self.stats["write_errors"] <= 20:
                log(f"[writer] {type(e).__name__}: {e}")

    # ---------------- health / lifetime ----------------
    def health_line(self):
        now = time.time()
        dt = max(1e-6, now - self.last_health)
        self.last_health = now
        gz = self.w.gz_bytes()
        gz_rate_h = (gz - self.last_gz) * 3600.0 / dt
        self.last_gz = gz
        up = sum(1 for c in self.conns if c.up)
        subs = sum(len(c.assigned) for c in self.conns if c.up)
        wanted = sum(len(c.assigned) for c in self.conns) + self.overflow
        try:
            free = self.w.check_disk()
        except DiskGuard as e:
            self.request_stop(str(e), code=2)
            return
        modes = ",".join(f"{ev.split('-')[0]}:{i['mode']}:{i['kept']}/{i['n']}" +
                         (f"@{i['centre']:.4g}" if i['centre'] else "")
                         for ev, i in sorted(self.sel_info.items()))
        log(f"[health] conns {up}/{len(self.conns)} up subs={subs} wanted={wanted} overflow={self.overflow} "
            f"deltas/s={self.minute['orderbook_delta'] / dt:.1f} trades={self.minute['trade']} "
            f"snaps={self.minute['orderbook_snapshot']}(lvl {self.minute['snap_levels']}) "
            f"lifecycle={self.minute[LIFECYCLE_CHANNEL]} "
            f"gz={gz / 1e6:.2f}MB (~{gz_rate_h / 1e6:.1f}MB/h) raw={self.w.raw_bytes / 1e6:.1f}MB "
            f"rest={self.rest.n} 429={self.rest.n429} resterr={self.rest.nerr} "
            f"reconn={self.stats['reconnects']} gaps={self.stats['SEQ_GAPS']} wserr={self.stats['ws_errors']} "
            f"free={free / 1e9:.1f}GB [{modes}]")
        self.minute.clear()

    async def health_loop(self):
        while not self.stop:
            await asyncio.sleep(60)
            if self.stop:
                break
            try:
                self.health_line()
            except Exception as e:
                log(f"[health] {type(e).__name__}: {e}")

    async def deadline(self, seconds):
        await asyncio.sleep(seconds)
        self.request_stop(f"--minutes {self.a.minutes} elapsed")

    def request_stop(self, reason, code=0):
        if self.stop:
            return
        self.stop = True
        self.stop_reason = reason
        self.exit_code = code
        log(f"[stop] {reason}")
        self.stopped.set()

    async def shutdown(self, tasks):
        self.stop = True
        for c in self.conns:
            if c.ws is not None:
                try:
                    await asyncio.wait_for(c.ws.close(), timeout=5)
                except Exception:
                    pass
        for t in tasks + [c.task for c in self.conns if c.task]:
            if t and not t.done():
                t.cancel()
        await asyncio.gather(*[t for t in tasks + [c.task for c in self.conns if c.task] if t],
                             return_exceptions=True)

    def summary(self):
        run_s = max(1e-6, time.time() - self.t_start)
        gz = self.w.gz_bytes()
        s = self.stats
        lines = [
            f"[summary] ran {run_s / 60:.1f} min; stop reason: {self.stop_reason}",
            f"[summary] connections opened {sum(c.connects for c in self.conns)} over {len(self.conns)} slot(s); "
            f"reconnects {s['reconnects']}; max markets subscribed at once {self.max_subs}; "
            f"final {sum(len(c.assigned) for c in self.conns)}; overflow now {self.overflow}",
            f"[summary] frames: orderbook_delta {s['orderbook_delta']} ({s['orderbook_delta'] / run_s:.1f}/s), "
            f"orderbook_snapshot {s['orderbook_snapshot']} (with levels {s['snap_levels']}), "
            f"trade {s['trade']}, {LIFECYCLE_CHANNEL} {s[LIFECYCLE_CHANNEL]} (dropped non-series {s['lifecycle_dropped']}), "
            f"subscribed {s['subscribed']}, ok {s['ok']}, ws errors {s['ws_errors']}, seq gaps {s['SEQ_GAPS']}",
            f"[summary] bytes written: gz {gz / 1e6:.2f} MB (raw json {self.w.raw_bytes / 1e6:.1f} MB) in {run_s / 3600:.3f} h "
            f"=> ~{gz * 3600 / run_s / 1e6:.1f} MB/h gz at this subscription set",
            f"[summary] REST: {self.rest.n} GETs, 429s {self.rest.n429}, other errors {self.rest.nerr}; "
            f"discoveries {s['discoveries']}; hourly markets tracked {len(self.markets)}, non-hourly rows skipped {self.skipped_nonhourly}",
            f"[summary] per-channel lines: " + ", ".join(f"{k}={v}" for k, v in sorted(self.w.lines_by_chan.items())),
        ]
        try:
            ct = os.times()
            lines.append(f"[summary] cpu: user {ct.user:.1f}s sys {ct.system:.1f}s = "
                         f"{100.0 * (ct.user + ct.system) / run_s:.1f}% of one core over the run")
        except Exception:
            pass
        if self.sel_info:
            lines.append("[summary] selection at exit: " + ", ".join(
                f"{ev}:{i['mode']} {i['kept']}/{i['n']}" + (f" centre {i['centre']:.6g}" if i['centre'] else "")
                for ev, i in sorted(self.sel_info.items())))
        for ln in lines:
            log(ln)


# ----------------------------------------------------------------------------
# pid file
# ----------------------------------------------------------------------------
def pid_alive(pid):
    try:
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, int(pid))     # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == 259              # STILL_ACTIVE
    except Exception:
        try:
            os.kill(int(pid), 0)
            return True
        except Exception:
            return False


def claim_pidfile(path, force=False):
    if os.path.exists(path):
        try:
            with open(path) as f:
                info = json.load(f)
            old = int(info.get("pid", 0))
        except Exception:
            old = 0
        if old and old != os.getpid() and pid_alive(old):
            if not force:
                return False, f"another hourly_collector is alive: pid {old} ({path}); use --force to override"
            log(f"[pid] --force: ignoring live pid {old} in {path}")
        elif old != os.getpid():
            log(f"[pid] stale pid file ({old}) -- taking over")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"pid": os.getpid(), "started": utcnow_str(), "argv": sys.argv}, f)
    return True, None


def release_pidfile(path):
    try:
        with open(path) as f:
            if int(json.load(f).get("pid", 0)) != os.getpid():
                return
        os.remove(path)
    except Exception:
        pass


# ----------------------------------------------------------------------------
# self-test
# ----------------------------------------------------------------------------
def selftest():
    import tempfile
    n = [0]

    def ck(cond, what):
        n[0] += 1
        if not cond:
            raise AssertionError(f"selftest check {n[0]} failed: {what}")

    # (1) planted-record round trip through the real Writer + annotate, rebuilt with the queue97_exact logic
    tmp = tempfile.mkdtemp(prefix="hourlycol-")
    now = 1792738800.0                                     # 2026-10-23T07:00:00Z -> file 20261023T07
    w = Writer(tmp, member_seconds=60, flush_seconds=0, min_free_gb=8.0, free_fn=lambda: 50e9)
    seqs = {}
    A = "KXBTCD-26OCT2204-T110999.99"
    B = "KXBTCD-26OCT2204-T110899.99"

    def rec(t, sid, seq, msg, ts):
        fr = {"type": t, "sid": sid, "seq": seq, "msg": msg, "sending_ts_ms": ts}
        annotate(fr, 0, seqs, rx_ms=ts + 11)
        w.write(t, fr, now=now + (ts - 1792738800000) / 1000.0)
        return fr
    rec("orderbook_snapshot", 4, 100, {"market_ticker": A, "market_id": "m-a",
                                       "yes_dollars_fp": [["0.5200", "100.00"], ["0.9800", "50.00"], ["0.0100", "0.00"]],
                                       "no_dollars_fp": [["0.4600", "80.00"]]}, 1792738800000)
    rec("orderbook_delta", 4, 101, {"market_ticker": A, "market_id": "m-a", "price_dollars": "0.9800", "delta_fp": "25.00",
                                    "side": "yes", "ts": "2026-10-23T08:00:01Z", "ts_ms": 1792738801000}, 1792738801003)
    rec("orderbook_delta", 4, 102, {"market_ticker": A, "market_id": "m-a", "price_dollars": "0.4600", "delta_fp": "-80.00",
                                    "side": "no", "ts": "2026-10-23T08:00:02Z", "ts_ms": 1792738802000}, 1792738802003)
    rec("orderbook_delta", 4, 103, {"market_ticker": A, "market_id": "m-a", "price_dollars": "0.9700", "delta_fp": "10.00",
                                    "side": "yes", "ts": "2026-10-23T08:00:03Z", "ts_ms": 1792738803000}, 1792738803003)
    rec("orderbook_delta", 5, 104, {"market_ticker": A, "market_id": "m-a", "price_dollars": "0.9800", "delta_fp": "1000.00",
                                    "side": "yes", "ts": "2026-10-23T08:00:04Z", "ts_ms": 1792738804000}, 1792738804003)   # wrong sid -> ignored
    rec("orderbook_delta", 4, 99, {"market_ticker": A, "market_id": "m-a", "price_dollars": "0.9800", "delta_fp": "-1000.00",
                                   "side": "yes", "ts": "2026-10-23T08:00:05Z", "ts_ms": 1792738805000}, 1792738805003)    # seq <= snapshot -> ignored
    rec("orderbook_delta", 4, 105, {"market_ticker": B, "market_id": "m-b", "price_dollars": "0.9900", "delta_fp": "5.00",
                                    "side": "yes", "ts": "2026-10-23T08:00:06Z", "ts_ms": 1792738806000}, 1792738806003)   # no snapshot -> delta-only
    # second member (61 s later) and the hour roll
    fr = rec("orderbook_delta", 4, 106, {"market_ticker": B, "market_id": "m-b", "price_dollars": "0.9900", "delta_fp": "1.00",
                                         "side": "yes", "ts": "2026-10-23T08:01:05Z", "ts_ms": 1792738865000}, 1792738865003)
    ck("_seq_gap" not in fr, "no false gap on consecutive seq")
    rec("orderbook_delta", 4, 108, {"market_ticker": B, "market_id": "m-b", "price_dollars": "0.9900", "delta_fp": "1.00",
                                    "side": "yes", "ts": "2026-10-23T09:00:01Z", "ts_ms": 1792742401000}, 1792742401003)
    w.close()
    snap = os.path.join(tmp, "orderbook_snapshot", "20261023T07.jsonl.gz")
    delt = os.path.join(tmp, "orderbook_delta", "20261023T07.jsonl.gz")
    delt9 = os.path.join(tmp, "orderbook_delta", "20261023T08.jsonl.gz")
    ck(os.path.exists(snap) and os.path.exists(delt) and os.path.exists(delt9), "files land at <root>/<channel>/YYYYMMDDTHH.jsonl.gz")
    ck(sorted(os.listdir(tmp)) == ["orderbook_delta", "orderbook_snapshot"], "one folder per channel")
    with gzip.open(delt, "rt", encoding="utf-8") as f:
        rows = [json.loads(x) for x in f]
    ck(len(rows) == 7, f"7 deltas in the 07Z file, got {len(rows)}")
    ck(all(list(r.keys())[:7] == list(RECORD_KEYS) for r in rows if "_seq_gap" not in r),
       f"record keys are exactly {RECORD_KEYS} (+_seq_gap when flagged); got {list(rows[0].keys())}")
    with gzip.open(delt9, "rt", encoding="utf-8") as f:
        r9 = [json.loads(x) for x in f]
    ck(len(r9) == 1 and r9[0]["_seq_gap"] == {"expected": 107, "got": 108}, "seq gap flagged like v4")
    books = q97_rebuild(snap, delt)
    bA = books[A]
    ck(bA["seeded"] and bA["yes"] == {Decimal("0.5200"): Decimal("100.00"), Decimal("0.9800"): Decimal("75.00"),
                                      Decimal("0.9700"): Decimal("10.00")} and bA["no"] == {},
       f"queue97_exact rebuild reproduces the planted book: {bA}")
    ck(not books[B]["seeded"] and books[B]["yes"] == {Decimal("0.9900"): Decimal("6.00")}, "delta-only fallback book")
    # member rotation produced two members, both readable in one pass (done above), and a truncated member repairs
    size = os.path.getsize(delt)
    with open(delt, "r+b") as f:
        f.truncate(size - 6)                               # chop the trailer of the last member
    try:
        with gzip.open(delt, "rb") as f:
            list(f)
        broken = False
    except EOFError:
        broken = True
    ck(broken, "a chopped trailer is unreadable before repair")
    fixed, kept, replaced = repair_gz(delt)
    ck(fixed and kept == 1 and 6 < replaced < size, f"repair replaced the truncated member, keeping its line: {fixed, kept, replaced}")
    with gzip.open(delt, "rb") as f:
        ck(len(list(f)) == 7, "all 7 lines readable after repair")
    with gzip.open(delt, "ab", compresslevel=4) as g:
        g.write(b'{"type":"orderbook_delta","sid":4,"seq":109,"msg":{},"sending_ts_ms":1,"_rx_ms":1,"_conn":0}\n')
    with gzip.open(delt, "rb") as f:
        ck(len(list(f)) == 8, "appending behind a repaired file reads cleanly (the v4 failure mode)")
    ck(repair_gz(delt)[0] is False, "a clean file is left alone")

    # (2) near-strike selection rule
    centre_true = 82050.0
    mk = {}
    for k in range(-25, 26):
        s = 82000.0 + 100.0 * k
        p = 1.0 / (1.0 + 2.718281828 ** ((s - centre_true) / 250.0))     # yes price falls with the strike
        bid = round(max(0.0, p - 0.01), 2)
        ask = round(min(1.0, p + 0.01), 2)
        mk[f"KXBTCD-26OCT2304-T{s - 0.01:.2f}"] = {"series": "KXBTCD", "event": "KXBTCD-26OCT2304", "strike": s,
                                                   "bid": bid, "ask": ask, "close_ts": 1792742400.0}
    mk["KXBTCD-26OCT2304-T86999.99"] = {"series": "KXBTCD", "event": "KXBTCD-26OCT2304", "strike": 87000.0,
                                        "bid": 0.0, "ask": 1.0, "close_ts": 1792742400.0}          # empty book, far away
    t_mid = 1792742400.0 - 1800                            # 30 min before close -> near mode
    wanted, prio, info = select_markets(mk, t_mid)
    i = info["KXBTCD-26OCT2304"]
    ck(i["mode"] == "near" and abs(i["centre"] - centre_true) < 100, f"implied centre ~{centre_true}: {i}")
    ck("KXBTCD-26OCT2304-T81999.99" in wanted, "at-the-money strike kept")
    ck("KXBTCD-26OCT2304-T82999.99" in wanted, "strike 950 away (1.16 %) kept by the 1.5 % rule although its price is ~0.02")
    ck("KXBTCD-26OCT2304-T83999.99" not in wanted, "strike 1950 away (2.4 %) with price ~0.0005 dropped")
    ck("KXBTCD-26OCT2304-T79499.99" not in wanted, "far in-the-money strike (price ~0.9999) dropped")
    ck("KXBTCD-26OCT2304-T86999.99" not in wanted, "empty-book far strike dropped (no price, outside 1.5 %)")
    ck(yes_price(0.0, 1.0) is None and yes_price(0.92, 1.0) == 0.92 and yes_price(0.0, 0.01) == 0.01
       and abs(yes_price(0.54, 0.56) - 0.55) < 1e-9, "yes_price: mid / one side / empty")
    ck(prio["KXBTCD-26OCT2304-T81999.99"] < prio["KXBTCD-26OCT2304-T82999.99"], "priority = distance from centre")
    ck(0 < len(wanted) < len(mk), f"near mode keeps a subset ({len(wanted)} of {len(mk)})")
    wanted_all, prio_all, info_all = select_markets(mk, 1792742400.0 - 14 * 60)
    ck(wanted_all == set(mk) and info_all["KXBTCD-26OCT2304"]["mode"] == "all", "last 15 minutes: ALL strikes")
    wanted_c, prio_c, info_c = select_markets(mk, 1792742400.0 + 30)
    ck(wanted_c == set(mk) and all(v >= 100 for v in prio_c.values()) and info_c["KXBTCD-26OCT2304"]["mode"] == "closed",
       "closed < 90 s ago: still wanted, lowest priority")
    ck(select_markets(mk, 1792742400.0 + 120)[0] == set(), "closed > 90 s ago: dropped")
    mk2 = {tk: dict(m, bid=0.0, ask=1.0) for tk, m in mk.items()}
    w2, _, i2 = select_markets(mk2, t_mid, prev_centres={"KXBTCD": 82050.0})
    ck(i2["KXBTCD-26OCT2304"]["centre"] == 82050.0 and "KXBTCD-26OCT2304-T81999.99" in w2, "no quotes at all: previous centre carries")

    # (3) hourly-vs-daily/weekly ticker filter
    ck(is_hourly("KXBTCD-26OCT2204-T110999.99"), "hourly ticker (HH) by ticker alone")
    ck(is_hourly("KXBTCD-26OCT2304-T81599.99", parse_ts("2026-10-23T07:00:00Z"), parse_ts("2026-10-23T08:00:00Z")),
       "hourly by ticker and 3600 s life")
    ck(not is_hourly("KXBTCD-26OCT23-T82000"), "daily ticker (no HH) rejected")
    ck(not is_hourly("KXBTCD-26OCT2317-T82499.99", parse_ts("2026-10-16T20:00:00Z"), parse_ts("2026-10-23T21:00:00Z")),
       "weekly ticker carries an HH but lives 7 days -> rejected")
    ck(is_hourly_ticker("KXBTCD-26OCT2317-T82499.99"), "(the ticker rule alone would have let the weekly through)")
    ck(not is_hourly("KXBTCD-26OCT2304-T1", parse_ts("2026-10-23T07:00:00Z"), parse_ts("2026-10-23T09:00:00Z")), "2 h life rejected")
    ck(not is_hourly("KXBTC15M-26OCT230215-15"), "15-minute ticker (12-char date part) rejected")
    ck(not is_hourly("") and not is_hourly("KXBTCD"), "junk rejected")

    # (4) disk guard
    ck(disk_ok(8.0e9, 8.0) and not disk_ok(7.99e9, 8.0), "disk_ok threshold")
    wd = Writer(tempfile.mkdtemp(prefix="hourlycol-dg-"), free_fn=lambda: 7.5e9)
    try:
        wd.write("orderbook_delta", {"type": "orderbook_delta", "sid": 1, "seq": 1, "msg": {}, "sending_ts_ms": 0, "_rx_ms": 0, "_conn": 0})
        tripped = False
    except DiskGuard as e:
        tripped = "DISK GUARD" in str(e) and "7.50 GB" in str(e)
    ck(tripped and wd.halted and not wd.fh, "write refused, handles closed, clear message when free < 8 GB")
    try:
        wd.write("orderbook_delta", {})
        again = False
    except DiskGuard:
        again = True
    ck(again, "stays halted")
    ck(isinstance(disk_free_bytes(tmp), int) and disk_free_bytes(tmp) > 0, "disk_free_bytes reads the drive")

    # (5) no write verb in this source; the scanner itself catches planted offenders
    with open(os.path.abspath(__file__), encoding="utf-8") as fsrc:
        src = fsrc.read()
    hits = scan_source_for_write_verbs(src)
    ck(not hits, "source scan: write verbs / order paths / foreign ws cmds found: " + "; ".join(f"L{i} {r}: {t[:60]}" for i, r, t in hits[:5]))
    planted = ["requests." + "po" + "st(url)", "meth" + 'od="' + "DEL" + 'ETE"', '{"cmd": ' + '"create_' + 'order"}',
               "urlop" + "en(req, data=b'x')", "x = '/portfolio/" + "ord" + "ers'", "if m == '" + "PU" + "T':"]
    for p in planted:
        ck(scan_source_for_write_verbs(p), f"scanner catches planted: {p}")
    ck(not scan_source_for_write_verbs('{"cmd": "subscribe"} GET "orderbook_delta" update_subscription'), "scanner passes clean text")
    ck(not hasattr(Signer, "sign") and "GET" in Signer.headers.__code__.co_consts, "signer signs GET only (no method argument)")

    # (6) connection planner
    adds, removes, overflow = plan({"a", "b", "c", "d", "e"}, [], 2, 3, {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4})
    ck(adds == [["a", "b"], ["c", "d"], ["e"]] and removes == [] and overflow == [], f"fills 120-caps in priority order: {adds}")
    adds, removes, overflow = plan({"a", "c", "e", "f", "g", "h"}, [{"a", "b"}, {"c", "d"}, {"e"}], 2, 3, {}, {"f": 0})
    ck(removes == [{"b"}, {"d"}, set()] and adds == [["f"], ["g"], ["h"]] and overflow == [],
       f"removes unwanted, home connection honoured, rest first-fit: {adds} {removes}")
    adds, removes, overflow = plan({"a", "b", "c", "d", "e", "f", "g"}, [{"a", "b"}, {"c", "d"}, {"e", "f"}], 2, 3, {})
    ck(overflow == ["g"] and adds == [[], [], []], "overflow when every connection is full")
    ck(chunks(range(5), 2) == [[0, 1], [2, 3], [4]], "chunks")

    # (7) hourly tape root layout matches the v4 reader's expectations (channel folders are frame types)
    ck(set(DATA_CHANNELS) == {"orderbook_delta", "trade"} and "ticker" not in DATA_CHANNELS, "no ticker channel")
    shutil.rmtree(tmp, ignore_errors=True)
    ck(pid_alive(os.getpid()) and not pid_alive(4000000), "pid liveness check")
    pf = os.path.join(tempfile.mkdtemp(prefix="hourlycol-pid-"), "x.pid")
    with open(pf, "w") as f:
        json.dump({"pid": os.getpid(), "started": "now"}, f)
    ok_, why = claim_pidfile(pf)              # our own pid counts as "not another process"
    with open(pf) as fpf:
        ck(ok_ and json.load(fpf)["pid"] == os.getpid(), "pid file claimed")
    release_pidfile(pf)
    ck(not os.path.exists(pf), "pid file released")

    # (8) the live frame path: handle() keeps the series' lifecycle frames, drops foreign ones and 'ticker'
    import types as _types
    if os.path.exists(KEY_FILE):
        root8 = tempfile.mkdtemp(prefix="hourlycol-h-")
        a8 = _types.SimpleNamespace(key_id=KEY_ID, key_file=KEY_FILE, out=root8, series=DEFAULT_SERIES, rest_gap=2.0,
                                    member_seconds=60, min_free_gb=8.0, lifecycle_all=False, verbose=False, minutes=0,
                                    per_conn=120, max_conns=8, band_lo=0.03, band_hi=0.97, near_pct=1.5,
                                    all_last_minutes=15, grace_seconds=90, manage_seconds=5, discover_seconds=60)
        col = Collector(a8)
        c8 = Conn(0)
        T = "KXBTCD-26OCT2304-T81599.99"
        for fr in ({"type": "subscribed", "id": 1, "msg": {"channel": "orderbook_delta", "sid": 2}, "sending_ts_ms": 1},
                   {"type": "market_lifecycle_v2", "sid": 1, "seq": 1, "msg": {"market_ticker": T, "event_type": "determined", "result": "yes"}, "sending_ts_ms": 1},
                   {"type": "market_lifecycle_v2", "sid": 1, "seq": 2, "msg": {"market_ticker": "KXBTC15M-26OCT230815-15", "event_type": "determined"}, "sending_ts_ms": 1},
                   {"type": "event_lifecycle", "sid": 1, "seq": 3, "msg": {"event_ticker": "KXESOCCERGAME-26OCT230656X", "series_ticker": "KXESOCCERGAME"}, "sending_ts_ms": 1},
                   {"type": "event_lifecycle", "sid": 1, "seq": 4, "msg": {"event_ticker": "KXETHD-26OCT2305", "series_ticker": "KXETHD"}, "sending_ts_ms": 1},
                   {"type": "ticker", "sid": 9, "seq": 1, "msg": {"market_ticker": T}, "sending_ts_ms": 1},
                   {"type": "orderbook_delta", "sid": 2, "seq": 1, "msg": {"market_ticker": T, "price_dollars": "0.5000", "delta_fp": "1.00", "side": "yes", "ts_ms": 1}, "sending_ts_ms": 1},
                   "not json at all"):
            col.handle(c8, fr if isinstance(fr, str) else json.dumps(fr))
        col.w.close()
        ck(c8.sids == {"orderbook_delta": 2}, "subscribed frame records the channel sid")
        ck(col.stats["lifecycle_dropped"] == 2 and col.w.lines_by_chan["market_lifecycle_v2"] == 1
           and col.w.lines_by_chan["event_lifecycle"] == 1,
           f"lifecycle filter: series kept, foreign dropped: {dict(col.stats)} {dict(col.w.lines_by_chan)}")
        ck(sorted(os.listdir(root8)) == ["event_lifecycle", "market_lifecycle_v2", "orderbook_delta", "subscribed"],
           f"channel folders (no ticker): {sorted(os.listdir(root8))}")
        d8 = os.path.join(root8, "market_lifecycle_v2")
        with gzip.open(os.path.join(d8, os.listdir(d8)[0]), "rt", encoding="utf-8") as f:
            r = json.loads(f.readline())
        ck(r["msg"]["market_ticker"] == T and r["_conn"] == 0 and "_rx_ms" in r and r["seq"] == 1, "lifecycle record shape")
        shutil.rmtree(root8, ignore_errors=True)
    else:
        print("  (key file not present: live frame-path check skipped)")
    print(f"hourly_collector selftest: {n[0]} checks OK (version {__VERSION__})")
    return 0


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
async def main_async(a):
    c = Collector(a)
    tasks = [asyncio.create_task(c.discovery_loop()),
             asyncio.create_task(c.manager_loop()),
             asyncio.create_task(c.health_loop())]
    if a.minutes > 0:
        tasks.append(asyncio.create_task(c.deadline(a.minutes * 60)))
    c.new_conn()                                   # connection 0 carries market_lifecycle_v2
    try:
        await c.stopped.wait()
    except asyncio.CancelledError:
        c.request_stop("cancelled (Ctrl+C)")
    finally:
        try:
            await c.shutdown(tasks)
        finally:
            c.w.close()
            c.summary()
    return c.exit_code


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--key-id", default=KEY_ID)
    ap.add_argument("--key-file", default=KEY_FILE)
    ap.add_argument("--out", default=DEFAULT_OUT, help="tape root (never C:\\kals\\kalshi_data)")
    ap.add_argument("--series", nargs="*", default=DEFAULT_SERIES)
    ap.add_argument("--minutes", type=float, default=0, help="stop after this many minutes (0 = run until stopped)")
    ap.add_argument("--per-conn", type=int, default=120, help="max markets per WebSocket connection")
    ap.add_argument("--max-conns", type=int, default=8)
    ap.add_argument("--discover-seconds", type=float, default=60)
    ap.add_argument("--manage-seconds", type=float, default=5)
    ap.add_argument("--rest-gap", type=float, default=2.0, help="minimum seconds between REST requests")
    ap.add_argument("--band-lo", type=float, default=0.03)
    ap.add_argument("--band-hi", type=float, default=0.97)
    ap.add_argument("--near-pct", type=float, default=1.5, help="strike within this %% of the implied centre")
    ap.add_argument("--all-last-minutes", type=float, default=15, help="subscribe ALL strikes in the hour's last N minutes")
    ap.add_argument("--grace-seconds", type=float, default=90, help="keep a closed market this long after its close")
    ap.add_argument("--member-seconds", type=float, default=60, help="close the gzip member this often")
    ap.add_argument("--min-free-gb", type=float, default=8.0)
    ap.add_argument("--pidfile", default=DEFAULT_PIDFILE)
    ap.add_argument("--lifecycle-all", action="store_true", help="write every market_lifecycle_v2 frame, not only the series'")
    ap.add_argument("--force", action="store_true", help="start even if the pid file names a live process")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--version-check", action="store_true")
    a = ap.parse_args()
    if a.version_check:
        print(__VERSION__)
        return 0
    if a.selftest:
        return selftest()
    if os.path.normcase(os.path.abspath(a.out)).startswith(os.path.normcase(r"C:\kals\kalshi_data") + os.sep) \
            or os.path.normcase(os.path.abspath(a.out)) == os.path.normcase(r"C:\kals\kalshi_data"):
        print("refusing: --out must not be inside the v4 tape root C:\\kals\\kalshi_data", flush=True)
        return 4
    below_normal_priority()
    os.makedirs(a.out, exist_ok=True)
    free = disk_free_bytes(a.out)
    if not disk_ok(free, a.min_free_gb):
        log(f"DISK GUARD: {free / 1e9:.2f} GB free < {a.min_free_gb:g} GB -- not starting")
        return 2
    ok, why = claim_pidfile(a.pidfile, force=a.force)
    if not ok:
        log(f"[pid] REFUSED: {why}")
        return 3
    log(f"[start] {__VERSION__} out={a.out} series={a.series} per_conn={a.per_conn} max_conns={a.max_conns} "
        f"minutes={a.minutes:g} rest_gap={a.rest_gap}s free={free / 1e9:.1f}GB pid={os.getpid()} pidfile={a.pidfile}")
    code = 0
    try:
        code = asyncio.run(main_async(a))
    except KeyboardInterrupt:
        code = 0
    finally:
        release_pidfile(a.pidfile)
        log(f"[exit] code {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
