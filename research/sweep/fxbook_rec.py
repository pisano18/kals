#!/usr/bin/env python3
"""fxbook_rec.py -- READ-ONLY recorder for the FX 15-minute reward paper (spec 20261015-R1-C2-03, `fxreward`).

WHY IT EXISTS
  The paper quoter (fxreward_paper.py) must see the moment the other makers LEAVE a price and the moment a new order
  arrives that would have crossed our stale quote -- the pick-off the public trade tape cannot show. Only the
  order-book DELTA stream shows it, and the collector does not record FX (its CRYPTO_15M list holds crypto, Coin Race
  and the commodity series only) and must not be touched. So FX gets its own recorder, writing its OWN hour files.

WHAT IT RECORDS (one small process; no tape loads; no order verb exists in this file -- the self-test scans for one)
  Kalshi WebSocket (signed handshake only because the socket requires it -- the collector's scheme; market data only):
    channels orderbook_delta (snapshot + deltas), trade, ticker for every market of the FX 15M series
    (KXEURUSD15M KXGBPUSD15M KXUSDJPY15M KXAUDUSD15M KXUSDCAD15M; --stage2 adds KXPALLADIUM15M KXPLATINUM15M),
    plus market_lifecycle_v2 (filtered to those series; `created` frames feed discovery, `determined` the result).
    A market is subscribed AS SOON AS IT IS LISTED (REST status=unopened, or a lifecycle `created` frame), before it
    opens, so its first snapshot is captured (the collector subscribes ~2 min late -- makersim's A5). It is dropped
    10 min after its close.
    Seq is checked per sid over every frame that carries one. A gap on the book sid marks every subscribed market
    SUSPECT (a `suspect` start frame), unsubscribes that sid and subscribes the book again for a fresh snapshot,
    exactly once per gap episode; each market's fresh snapshot ends its suspect span (a `suspect` end frame). A
    disconnect marks every subscribed market suspect the same way. The paper skips suspect spans and counts them.
  Kraken public WebSocket v2 (no key): book depth 10 + trade for EUR/USD GBP/USD USD/JPY AUD/USD USD/CAD (the list
    is checked against Kraken's AssetPairs at start; a pair Kraken does not list is dropped and logged). Every book
    message is validated with Kraken's CRC32 checksum (top 10 asks low->high then top 10 bids high->low, each price
    and qty at the pair's precision with the '.' and leading zeros removed); a failure is counted, written with
    `_crc_ok: false`, and that symbol's book is resubscribed for a fresh snapshot.
  Kalshi public REST (unauthenticated GETs only, paced: >= 2.0 s between calls, <= 30 calls in any 60 s, a 429
    backs off 10 s): GET /markets?series_ticker=S&status=unopened|open every 300 s; GET /incentive_programs every
    15 min (cursor paging, newest first, stopped at programs that began over 1 h ago; rows on the recorded series
    kept); GET /markets/{t} 6 min after each close (result,
    expiration_value, floor_strike, volume_fp: the settlement and the V2 volume check).

OUTPUT
  C:\\kals-repo\\results\\fxbook\\<channel>\\<YYYYMMDDTHH>.jsonl.gz (UTC hour), each line the frame exactly as received
  plus `_rx_ms` (local receive ms) and `_rx_n` (this process's receive counter, so snapshot/delta order is exact) --
  the collector's format, so makersim-style readers work unchanged. Kalshi channels are named by frame `type`
  (orderbook_snapshot, orderbook_delta, trade, ticker, market_lifecycle_v2, subscribed, ok, error, unsubscribed);
  alongside them: suspect, kraken_book, kraken_trade, kraken_status, markets (REST market rows, written when new or
  changed), programs (program rows, when new or changed), programs_poll, settled, and heartbeat (every 5 s, with
  both sockets' state: a recorder that was down leaves no frames, so the paper reads a heartbeat gap > 15 s as a
  suspect span for every market until its next snapshot). Gzip members are flushed once a
  second and closed at the hour roll and on a clean stop (a hard kill leaves an untrailered member; gzsalvage reads
  it). Nothing is ever written under C:\\kals.
  Event log results/fxbook-rec.jsonl: start (argv, code sha256[:12]), `health` every 60 s (connected per socket,
  frames/s per channel, seq gaps, resubscribes, suspect seconds, Kraken checksum failures, trade lag and delta lag
  medians (_rx_ms - ts_ms), bytes this hour, fxbook total, free disk GB, RSS MB, REST calls and 429s), errors, stop.

RAILS (code, not flags)
  stop file results/fxbook-rec.stop ends it cleanly (files closed with trailers); one process at a time (OS lock
  results/fxbook-rec.lock, racereward_live's InstanceLock pattern -- the OS drops it when the holder dies); free disk
  < 15 GB -> stop writing, log low_disk, exit; results/fxbook over 3 GB -> stop, log, exit; the first FULL recorded
  hour in which the FX books traded (>= 600 book deltas; an hour recorded while FX is closed does not count) over
  40 MB gz -> drop AUD and CAD (Kalshi and Kraken); RSS over 150 MB -> log rss_abort, exit (the build order's
  per-process cap; the spec said 200). --live is refused (there is no live mode).
  A socket counts as alive on ANY received frame (text, ping or pong); 60 s with no frame at all reconnects it.

REVIEW FIXES 2026-10-17 (v2): any frame keeps a socket alive (must-fix 5: a healthy socket that only pinged was
  dropped every 60 s); the 40 MB rule waits for an hour with trading FX books; the self-test now drives the real
  socket loops against fake sockets (ping-only kept, silent dropped at 60 s, a drop marks every subscribed market
  suspect, a reconnect resubscribes every tracked market) and checks the disk / cap / RSS rails at their thresholds.
  DISCOVERY EVERY 300 s, NOT THE SPEC'S 60 s (builder's call, 2026-10-17): the public REST limit is per IP and shared
  with the live bots, which already draw 429s (ladder-live 10, forecaster-live 14 on 10-17 by 06:30Z); the v2 smoke
  drew 2 x 429 in 25 calls at 2 s spacing and a paper bot drew one inside our first-minute burst. FX markets are
  listed hours ahead and the lifecycle `created` frame tracks a new one at once, so the REST pass is a backup;
  300 s cuts it from 10 calls a minute to 2. One constant to revert (DISCOVER_S).

THE BAR this recorder feeds (spec section 5, quoted exactly; read by fxreward_paper.py --report):

  "Read **after 5 complete weekdays of recording** (target Mon 10-19 to Fri 10-23, about 450-470 rewarded windows per
  pair; minimum 400 per pair with V1-V5 passing). Due **2026-10-24T12:00Z**. Variant of record: S = 60, join, T_STOP 300 s,
  net cap 60, band 10-90c, payout 0.9, `fifo_prorata`. Primary metric: **net per window = credit + fills marked at 60 s**
  (markout, 4-5x less noisy than settlement); settlement P&L is the cross-check. n = windows; EURUSD and GBPUSD share
  close times, so the pooled SE clusters by close.

  - **GO to a live micro (operator sign-off still required) for a pair if ALL of:**
    - G1 at L = 300 ms: mean net >= **+$1.00 per window**, 95% lower bound of the mean > $0, and the late half (days 3-5)
      mean >= +$0.50.
    - G2 at L = 300 ms under `last` (worst queue): mean net >= $0.
    - G3 settlement mean net is not below the markout mean by more than 2 SE (the markout is not hiding a drift).
    - G4 the engine sees pick-offs: >= 1 stale fill per 10 windows at L = 300 (zero means it is blind -> void, not GO).
    - G5 tails at S = 60 (settlement): worst window >= -$45, worst ET day >= -$150.
  - **KILL the family for a pair if:** at L = 150 ms `fifo_prorata` the mean net < $0 with the 95% upper bound < +$1.00
    (even a fast quoter pays the credit away), OR the mean credit at S = 60 < $1.50 per window (the share collapsed or
    the pot was cut).
  - **Otherwise INCONCLUSIVE:** extend once by 5 weekdays (about 930 windows per pair), then GO only on G1-G5, else KILL.
  - **MDE:** per-window SD of the markout net is estimated at $4-6 (refuter: 0.62c/contract SE over 100 windows at ~70
    fills) -> SE about $0.25 over 470 windows -> smallest detectable effect about **$0.70 per window** (95%, 80% power),
    below the $1.00 GO line. Settlement alone (SD ~$28/window) detects only about $3.60 -- it cannot decide. If the
    measured markout SD exceeds $10/window the report must say "no power", not "no effect"."

USAGE
    python research/sweep/fxbook_rec.py --selftest
    python research/sweep/fxbook_rec.py                      # until the stop file (start_fxbook_rec.ps1)
    python research/sweep/fxbook_rec.py --minutes 3 --out <dir> --log <file> --extra-series KXBTC15M   # smoke

stdlib only, plus research/kauth.py for the RSA-PSS WebSocket handshake headers and its GET helper (imported lazily,
so the self-test needs neither the key nor the network). The WebSocket client is portwatch_rec.WSClient, imported.
"""
import argparse
import collections
import ctypes
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import shutil
import socket
import sys
import threading
import time
import urllib.request
import zlib
from decimal import Decimal, InvalidOperation

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)
REPO = os.path.dirname(RESEARCH)
RESULTS = os.path.join(REPO, "results")
sys.path.insert(0, RESEARCH)
sys.path.insert(0, HERE)
from portwatch_rec import WSClient                                   # noqa: E402  (stdlib RFC 6455 client)

UTC = dt.timezone.utc
SERIES_STAGE1 = ("KXEURUSD15M", "KXGBPUSD15M", "KXUSDJPY15M", "KXAUDUSD15M", "KXUSDCAD15M")
SERIES_STAGE2 = ("KXPALLADIUM15M", "KXPLATINUM15M")
SERIES_PAIR = {"KXEURUSD15M": "EUR/USD", "KXGBPUSD15M": "GBP/USD", "KXUSDJPY15M": "USD/JPY",
               "KXAUDUSD15M": "AUD/USD", "KXUSDCAD15M": "USD/CAD"}
KRAKEN_SYMBOLS = ("EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD")
KRAKEN_ALT = {"EUR/USD": "EURUSD", "GBP/USD": "GBPUSD", "USD/JPY": "USDJPY", "AUD/USD": "AUDUSD",
              "USD/CAD": "USDCAD"}
DROP_IF_BIG_SERIES = ("KXAUDUSD15M", "KXUSDCAD15M")
DROP_IF_BIG_SYMBOLS = ("AUD/USD", "USD/CAD")
KALSHI_WS_HOST = "api.elections.kalshi.com"
KALSHI_WS_PATH = "/trade-api/ws/v2"
KRAKEN_WS_HOST = "ws.kraken.com"
KRAKEN_WS_PATH = "/v2"
KRAKEN_ASSETPAIRS = "https://api.kraken.com/0/public/AssetPairs?pair=" + ",".join(KRAKEN_ALT.values())
KRAKEN_DEPTH = 10
DATA_CHANNELS = ["orderbook_delta", "trade", "ticker"]
BOOK = "orderbook_delta"
OUT_ROOT = os.path.join(RESULTS, "fxbook")
LOG_PATH = os.path.join(RESULTS, "fxbook-rec.jsonl")
STOP_PATH = os.path.join(RESULTS, "fxbook-rec.stop")
LOCK_PATH = os.path.join(RESULTS, "fxbook-rec.lock")
FORBIDDEN_ROOT = os.path.normcase(os.path.abspath(r"C:\kals"))
DISCOVER_S = 300.0                # the spec said 60 s: see the docstring (REST share with the live bots)
PROGRAMS_S = 900.0
PROGRAMS_LOOKBACK_S = 3600.0      # rows come newest-first: stop paging past programs that began > 1 h ago
SETTLE_AFTER_S = 360.0
SETTLE_RETRY_S = 600.0
SETTLE_TRIES = 3
DROP_AFTER_MS = 600 * 1000
REST_GAP_S = 2.0                  # >= this between two REST calls of this process (1.0 drew a 429 in the smoke)
REST_WINDOW_S, REST_WINDOW_MAX = 60.0, 30     # <= 30 calls in any 60 s (1 per 2 s average)
REST_BACKOFF_S = 10.0             # a 429 backs off this long
HEALTH_S = 60.0
HEARTBEAT_S = 5.0                 # a `heartbeat` row this often: the paper treats a gap > 15 s as recorder downtime
FLUSH_S = 1.0
FREE_DISK_STOP_GB = 15.0
CAP_BYTES = 3 * 1024 ** 3
BIG_HOUR_BYTES = 40 * 1024 ** 2
BIG_HOUR_MIN_DELTAS = 600         # an hour with fewer FX book deltas was a closed market: the 40 MB rule waits
RSS_ABORT_MB = 150.0
WS_RECV_TIMEOUT_S = 5.0
WS_IDLE_RECONNECT_S = 60.0
WS_PING_S = 20.0
CHAN_RE = re.compile(r"^[a-z0-9_]{1,40}$")


class UnitError(ValueError):
    pass


# ------------------------------------------------------------------------------------------------ small helpers
def utc_iso(t):
    return dt.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def hour_tag(t):
    return dt.datetime.fromtimestamp(t, UTC).strftime("%Y%m%dT%H")


def iso_ms(s):
    """'2026-10-16T17:00:00Z' -> epoch ms (UTC); None if unreadable."""
    try:
        return int(dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


def now_ms():
    return int(time.time() * 1000)


def cc_to_usd(x):
    """`period_reward` is in CENTI-CENTS -- decided by the FIELD (Kalshi's program schema), never by the magnitude
    (hard rule 5): 500000 -> 50.00 dollars."""
    return float(Decimal(str(x)) / Decimal(10000))


def price_dollars(s):
    """A `*_dollars` field: a dollar price as a string ('0.5500' -> 0.55). Outside [0, 1] is a unit error, never a
    rescale (hard rule 5)."""
    try:
        v = float(Decimal(str(s)))
    except (InvalidOperation, ValueError, TypeError):
        raise UnitError("unreadable dollar price %r" % (s,))
    if not (0.0 <= v <= 1.0):
        raise UnitError("dollar price outside [0, 1]: %r" % (s,))
    return v


def code_sha():
    with open(os.path.abspath(__file__), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:12]


def rss_mb():
    """Working set in MB (stdlib; makersim.rss_mb's Windows path)."""
    try:
        if sys.platform == "win32":
            class PMC(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            k32 = ctypes.windll.kernel32
            fn = getattr(k32, "K32GetProcessMemoryInfo", None) or ctypes.windll.psapi.GetProcessMemoryInfo
            fn.restype = ctypes.c_int
            fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
            if not fn(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
                return -1.0
            return pmc.WorkingSetSize / 1048576.0
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return -1.0


def free_disk_gb(path):
    try:
        return shutil.disk_usage(path).free / 1e9
    except Exception:
        return -1.0


def dir_bytes(root):
    n = 0
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            try:
                n += os.path.getsize(os.path.join(dp, fn))
            except OSError:
                pass
    return n


def median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    k = len(xs) // 2
    return xs[k] if len(xs) % 2 else 0.5 * (xs[k - 1] + xs[k])


def inside(path, root):
    p, r = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(root))
    try:
        return os.path.commonpath([p, r]) == r
    except ValueError:
        return False


def check_out_root(root):
    """The output root must be inside this repo and never under C:\\kals (the collector's tree)."""
    if inside(root, FORBIDDEN_ROOT) or os.path.normcase(os.path.abspath(root)).startswith(FORBIDDEN_ROOT + os.sep):
        raise SystemExit("REFUSING: output root %s is under C:\\kals" % root)
    if not inside(root, REPO):
        raise SystemExit("REFUSING: output root %s is outside %s" % (root, REPO))
    return os.path.abspath(root)


class Log:
    """The small event log (jsonl, one object a line, every 't' in UTC)."""

    def __init__(self, path=None, sink=None, echo=False):
        self.path, self.sink, self.echo = path, sink, echo
        self.fh = open(path, "a", encoding="utf-8") if path else None
        self.lock = threading.Lock()

    def write(self, ev, **kw):
        r = {"t": utc_iso(time.time()), "ev": ev}
        r.update(kw)
        line = json.dumps(r, default=str, separators=(",", ":"))
        with self.lock:
            if self.sink is not None:
                self.sink.append(r)
            if self.fh is not None:
                try:
                    self.fh.write(line + "\n")
                    self.fh.flush()
                except Exception:
                    pass
        if self.echo and ev not in ("health",):
            print(line[:400], flush=True)
        return r

    def close(self):
        if self.fh:
            self.fh.close()
            self.fh = None


class InstanceLock:
    """One recorder at a time: an OS byte-range lock (racereward_live.InstanceLock, copied). The OS drops it when the
    holder dies, so a crash never leaves a stale lock (never probe a pid with os.kill on Windows -- it kills)."""
    OFFSET = 4096

    def __init__(self, path):
        self.path, self.fd = path, None

    def acquire(self):
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, self.OFFSET, 0)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        self.fd = fd
        try:
            os.lseek(fd, 0, 0)
            os.write(fd, ("pid %d since %s" % (os.getpid(), utc_iso(time.time()))).ljust(80).encode() + b"\n")
        except OSError:
            pass
        return True

    def holder(self):
        try:
            with open(self.path, encoding="utf-8", errors="replace") as fh:
                return fh.readline().strip()
        except OSError:
            return "?"

    def release(self):
        if self.fd is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(self.fd, self.OFFSET, 0)
                msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass
        self.fd = None


# ------------------------------------------------------------------------------------------------ the hour writer
class HourWriter:
    """Hourly gzip JSONL per channel (the collector's Writer pattern, copied, not imported): rolls at the UTC hour,
    flushes at most once a second (better compression than a flush per line; a crash costs <= 1 s), closes members
    at the roll and on close(). It can only write under its root: the channel name is checked against
    [a-z0-9_] and the final path against the root."""

    def __init__(self, root, clock=time.time, flush_s=FLUSH_S):
        self.root = os.path.abspath(root)
        self.clock = clock
        self.flush_s = flush_s
        self.fh = {}
        self.hour = None
        self.lock = threading.Lock()
        self.last_flush = 0.0
        self.lines = collections.Counter()
        self.hour_lines = collections.Counter()      # lines per channel in the CURRENT hour
        self.rolled_lines = {}                       # closed hour -> {channel: lines} (the 40 MB rule reads it)
        self.disabled = None             # reason string once writing has been stopped
        self.rolled = []                 # hour tags closed by a roll (the main loop reads them)
        self.write_errors = 0

    def path_for(self, chan, hour):
        if not CHAN_RE.match(chan or ""):
            raise ValueError("bad channel name %r" % (chan,))
        p = os.path.join(self.root, chan, hour + ".jsonl.gz")
        if not inside(p, self.root):
            raise ValueError("path escapes the root: %r" % p)
        return p

    def _roll(self):
        h = hour_tag(self.clock())
        if h != self.hour:
            for f in self.fh.values():
                try:
                    f.close()
                except Exception:
                    pass
            if self.hour is not None:
                self.rolled.append(self.hour)
                self.rolled_lines[self.hour] = dict(self.hour_lines)
            self.hour_lines = collections.Counter()
            self.fh, self.hour = {}, h

    def write(self, chan, obj):
        with self.lock:
            if self.disabled:
                return False
            self._roll()
            f = self.fh.get(chan)
            if f is None:
                p = self.path_for(chan, self.hour)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                f = self.fh[chan] = gzip.open(p, "at", compresslevel=6, encoding="utf-8")
            try:
                f.write(json.dumps(obj, separators=(",", ":"), default=float) + "\n")
                self.lines[chan] += 1
                self.hour_lines[chan] += 1
            except (OSError, ValueError):
                self.write_errors += 1
                try:
                    self.fh.pop(chan).close()
                except Exception:
                    self.fh.pop(chan, None)
                return False
            t = self.clock()
            if t - self.last_flush >= self.flush_s:
                self._flush_all(t)
            return True

    def _flush_all(self, t):
        self.last_flush = t
        for c, f in list(self.fh.items()):
            try:
                f.flush()
            except (OSError, ValueError):
                self.write_errors += 1
                try:
                    self.fh.pop(c).close()
                except Exception:
                    self.fh.pop(c, None)

    def tick(self):
        """Called by the main loop: roll at the hour even when no frame arrives, flush on the 1 s timer."""
        with self.lock:
            if self.disabled:
                return
            t = self.clock()
            if hour_tag(t) != self.hour and self.hour is not None:
                self._roll()
            if t - self.last_flush >= self.flush_s:
                self._flush_all(t)

    def hour_bytes(self, hour):
        n = 0
        for chan in os.listdir(self.root) if os.path.isdir(self.root) else []:
            p = os.path.join(self.root, chan, hour + ".jsonl.gz")
            try:
                n += os.path.getsize(p)
            except OSError:
                pass
        return n

    def disable(self, why):
        with self.lock:
            self.disabled = why
            for f in self.fh.values():
                try:
                    f.close()
                except Exception:
                    pass
            self.fh = {}

    def close(self):
        with self.lock:
            for f in self.fh.values():
                try:
                    f.close()
                except Exception:
                    pass
            self.fh = {}


def chan_of(frame_type):
    t = str(frame_type or "unknown").lower()
    return t if CHAN_RE.match(t) else "other"


# ------------------------------------------------------------------------------------------------ Kalshi side
class KalshiCore:
    """Frame handling and subscription bookkeeping for the Kalshi socket. No I/O of its own: outgoing commands are
    queued in self.out (the socket thread sends them; the self-test reads them)."""

    def __init__(self, writer, series, log=None, clock_ms=now_ms):
        self.w = writer
        self.log = log
        self.clock_ms = clock_ms
        self.lock = threading.RLock()
        self.set_series(series)
        self.tracked = {}            # ticker -> {"open_ms", "close_ms", "since_ms"}
        self.subscribed = set()      # tickers sent in a data subscribe on THIS connection
        self.want_add = set()
        self.sids = {}               # channel -> sid
        self.seq = {}                # sid -> last seq
        self.dead = set()            # sids we unsubscribed (their seq is no longer checked)
        self.resub_pending = False
        self.suspect = {}            # ticker -> suspect start (rx ms)
        self.suspect_ms_closed = 0
        self.stats = collections.Counter()
        self.lag_trade = collections.deque(maxlen=4000)
        self.lag_delta = collections.deque(maxlen=4000)
        self.cid = 0
        self.out = []
        self.cmd_kind = {}           # command id -> kind
        self.no_delete = False
        self.connected = False
        self.rx_n = 0

    def set_series(self, series):
        self.series = tuple(series)
        self.prefixes = tuple(s + "-" for s in self.series)

    def matches(self, tk):
        return isinstance(tk, str) and tk.startswith(self.prefixes)

    def _note(self, ev, **kw):
        if self.log is not None:
            self.log.write(ev, **kw)

    def _cmd(self, cmd, params, kind):
        self.cid += 1
        d = {"id": self.cid, "cmd": cmd, "params": params}
        self.cmd_kind[self.cid] = kind
        self.out.append(d)
        return d

    def take_out(self):
        with self.lock:
            o, self.out = self.out, []
        return o

    def track(self, tk, open_ms, close_ms, src):
        """A market of a recorded series was listed: subscribe it at the next pump (before it opens)."""
        with self.lock:
            if not self.matches(tk):
                return False
            r = self.tracked.get(tk)
            if r is not None:
                if close_ms:
                    r["close_ms"] = close_ms
                if open_ms:
                    r["open_ms"] = open_ms
                return False
            if close_ms and close_ms + DROP_AFTER_MS < self.clock_ms():
                return False                       # already past its drop time
            self.tracked[tk] = {"open_ms": open_ms, "close_ms": close_ms, "since_ms": self.clock_ms(), "src": src}
            self.want_add.add(tk)
            self.stats["tracked_new"] += 1
            return True

    def on_connect(self):
        with self.lock:
            self.connected = True
            self.sids.clear()
            self.seq.clear()
            self.dead.clear()
            self.resub_pending = False
            self.subscribed.clear()
            self._cmd("subscribe", {"channels": ["market_lifecycle_v2"]}, "lifecycle")
            tks = sorted(self.tracked)
            if tks:
                self._cmd("subscribe", {"channels": list(DATA_CHANNELS), "market_tickers": tks}, "data")
                self.subscribed |= set(tks)
            self.want_add.clear()

    def on_disconnect(self, why):
        with self.lock:
            self.connected = False
            self.start_suspect(sorted(self.subscribed), self.clock_ms(), "disconnect", {"err": str(why)[:160]})
            self.subscribed.clear()

    def pump(self):
        """Adds and drops (called every ~0.5 s by the socket thread)."""
        with self.lock:
            if not self.connected:
                return
            now = self.clock_ms()
            adds = sorted(t for t in self.want_add if t in self.tracked and t not in self.subscribed)
            self.want_add.clear()
            if adds:
                self._cmd("subscribe", {"channels": list(DATA_CHANNELS), "market_tickers": adds}, "data")
                self.subscribed |= set(adds)
                self.stats["subscribe_adds"] += len(adds)
            drops = sorted(t for t, r in self.tracked.items()
                           if r.get("close_ms") and r["close_ms"] + DROP_AFTER_MS < now)
            if drops:
                for t in drops:
                    self.tracked.pop(t, None)
                    if t in self.suspect:
                        self.end_suspect(t, now, "dropped")
                live = [t for t in drops if t in self.subscribed]
                self.subscribed -= set(drops)
                if live and not self.no_delete:
                    for ch in DATA_CHANNELS:
                        sid = self.sids.get(ch)
                        if sid is not None:
                            self._cmd("update_subscription", {"sids": [sid], "market_tickers": live,
                                                              "action": "delete_markets"}, "delete")
                self.stats["dropped"] += len(drops)

    def drop_series(self, series):
        """Stop recording these series (the 40 MB first-hour rule)."""
        with self.lock:
            keep = tuple(s for s in self.series if s not in series)
            self.set_series(keep)
            gone = sorted(t for t in self.tracked if t.split("-")[0] in series)
            for t in gone:
                self.tracked[t]["close_ms"] = self.clock_ms() - DROP_AFTER_MS - 1
            self.pump()
            return gone

    # -- suspect spans
    def start_suspect(self, tks, rx, why, info=None):
        new = [t for t in tks if t not in self.suspect]
        for t in new:
            self.suspect[t] = rx
        if new:
            fr = {"type": "suspect", "state": "start", "tickers": new, "why": why, "_rx_ms": rx}
            if info:
                fr.update(info)
            self.w.write("suspect", fr)
            self.stats["suspect_starts"] += len(new)
        return new

    def end_suspect(self, tk, rx, why="snapshot"):
        st = self.suspect.pop(tk, None)
        if st is None:
            return None
        self.suspect_ms_closed += max(0, rx - st)
        self.w.write("suspect", {"type": "suspect", "state": "end", "tickers": [tk], "why": why,
                                 "suspect_ms": rx - st, "_rx_ms": rx})
        return rx - st

    def suspect_open_ms(self, now):
        return sum(max(0, now - s) for s in self.suspect.values())

    def resubscribe_book(self, rx, why, info=None):
        """Exactly one unsubscribe + subscribe per gap episode; later gaps while it is pending are only counted."""
        if self.resub_pending:
            self.stats["gap_while_resub"] += 1
            return False
        self.resub_pending = True
        self.stats["book_resubscribes"] += 1
        tks = sorted(self.subscribed)
        self.start_suspect(tks, rx, why, info)
        old = self.sids.pop(BOOK, None)
        if old is not None:
            self.dead.add(old)
            self._cmd("unsubscribe", {"sids": [old]}, "unsubscribe")
        if tks:
            self._cmd("subscribe", {"channels": [BOOK], "market_tickers": tks}, "book_resub")
        self._note("book_resubscribe", why=why, info=info, tickers=len(tks), old_sid=old)
        return True

    def _seq(self, sid, seq, t, rx):
        if sid is None or seq is None:
            return
        if sid in self.dead:
            self.stats["dead_sid_frames"] += 1
            return
        prev = self.seq.get(sid)
        self.seq[sid] = seq
        if prev is not None and seq != prev + 1:
            self.stats["seq_gaps"] += 1
            info = {"sid": sid, "expected": prev + 1, "got": seq, "frame_type": t}
            if sid == self.sids.get(BOOK):
                self.resubscribe_book(rx, "seq_gap", info)
            elif sid == self.sids.get("trade"):
                self.stats["trade_seq_gaps"] += 1
                self.w.write("suspect", dict({"type": "trade_gap", "_rx_ms": rx}, **info))
            else:
                self.stats["other_seq_gaps"] += 1

    def on_frame(self, raw, rx=None):
        rx = self.clock_ms() if rx is None else rx
        try:
            m = json.loads(raw)
        except Exception:
            self.stats["unparsed"] += 1
            return None
        if not isinstance(m, dict):
            self.stats["not_object"] += 1
            return None
        with self.lock:
            t = m.get("type") or "unknown"
            self.stats["f_" + str(t)[:30]] += 1
            msg = m.get("msg") if isinstance(m.get("msg"), dict) else {}
            # seq is per sid over EVERY frame that carries one, so it is checked before the series filter
            self._seq(m.get("sid"), m.get("seq"), t, rx)
            if t == "market_lifecycle_v2":
                tk = msg.get("market_ticker")
                if not self.matches(tk):
                    self.stats["lifecycle_other"] += 1
                    return None
                if msg.get("event_type") == "created":
                    o, c = msg.get("open_ts"), msg.get("close_ts")
                    self.track(tk, int(o) * 1000 if isinstance(o, (int, float)) else None,
                               int(c) * 1000 if isinstance(c, (int, float)) else None, "lifecycle")
            elif t == "event_lifecycle":
                if msg.get("series_ticker") not in self.series:
                    self.stats["event_lifecycle_other"] += 1
                    return None
            m["_rx_ms"] = rx
            self.rx_n += 1
            m["_rx_n"] = self.rx_n
            if t == "subscribed":
                ch, sid = msg.get("channel"), msg.get("sid")
                if ch:
                    old = self.sids.get(ch)
                    self.sids[ch] = sid
                    if old is not None and old != sid:
                        self.dead.add(old)
                    if ch == BOOK:
                        self.resub_pending = False
            elif t == "orderbook_snapshot":
                self.end_suspect(msg.get("market_ticker"), rx)
            elif t == "orderbook_delta":
                ts = msg.get("ts_ms")
                if isinstance(ts, (int, float)):
                    self.lag_delta.append(rx - ts)
            elif t == "trade":
                ts = msg.get("ts_ms")
                if isinstance(ts, (int, float)):
                    self.lag_trade.append(rx - ts)
            elif t == "error":
                code = msg.get("code")
                kind = self.cmd_kind.get(m.get("id"))
                self._note("ws_error_frame", frame=m)
                if kind == "delete":
                    self.no_delete = True
                if code == 25 and (m.get("sid") is None or m.get("sid") == self.sids.get(BOOK)):
                    self.resubscribe_book(rx, "buffer_overflow", {"code": code, "sid": m.get("sid")})
            self.w.write(chan_of(t), m)
            return t


def recv_any(ws):
    """One receive. (True, text) for a text frame; (True, None) for a control frame -- a server ping (answered with a
    pong inside WSClient.recv_text) or a pong -- which proves the socket alive just as well; (False, None) only when
    the receive timed out with no frame at all. (Review 2026-10-17, must-fix 5: the idle clock used to count text
    frames only, so a healthy socket that only pinged was dropped after 60 s.)"""
    try:
        return True, ws.recv_text()
    except socket.timeout:
        return False, None


def kalshi_thread(core, stop, headers_fn, log, host=KALSHI_WS_HOST, path=KALSHI_WS_PATH, ws_factory=None,
                  clock=None, wait=None):
    """The Kalshi socket. ws_factory / clock / wait are injected only by the self-test (a fake socket, a fake clock)."""
    ws_factory = ws_factory or WSClient
    clock = clock or time.time
    wait = wait or stop.wait
    backoff = 1
    while not stop.is_set():
        ws = None
        try:
            ws = ws_factory(headers_fn(), host=host, path=path)
            ws.connect()
            ws.sock.settimeout(WS_RECV_TIMEOUT_S)
            core.on_connect()
            for c in core.take_out():
                ws.send(json.dumps(c))
            log.write("ws_connected", side="kalshi", tracked=len(core.tracked))
            backoff = 1
            last_rx = last_ping = clock()
            last_pump = 0.0
            while not stop.is_set():
                got, txt = recv_any(ws)
                t = clock()
                if got:
                    last_rx = t                  # ANY frame, a server ping included, proves the socket alive
                elif t - last_rx > WS_IDLE_RECONNECT_S:
                    raise ConnectionError("no frame in %d s" % WS_IDLE_RECONNECT_S)
                if txt is not None:
                    core.on_frame(txt, int(t * 1000))
                if t - last_ping > WS_PING_S and t - last_rx > WS_PING_S / 2:
                    ws.send(b"", 0x9)
                    last_ping = t
                if t - last_pump >= 0.5:
                    last_pump = t
                    core.pump()
                    for c in core.take_out():
                        ws.send(json.dumps(c))
        except Exception as e:                                   # noqa: BLE001
            if stop.is_set():
                break
            log.write("ws_error", side="kalshi", err=repr(e)[:240], retry_s=backoff)
            core.on_disconnect(repr(e))
            wait(backoff)
            backoff = min(backoff * 2, 30)
        finally:
            if ws is not None and ws.sock is not None:
                ws.close()
    log.write("ws_stopped", side="kalshi")


# ------------------------------------------------------------------------------------------------ Kraken side
def kr_fmt(x, dp):
    """Kraken's checksum field: the value at the pair's precision, '.' removed, leading zeros removed."""
    s = format(Decimal(str(x)), "." + str(int(dp)) + "f").replace(".", "").lstrip("0")
    return s if s else "0"


def kraken_checksum(bids, asks, pdp, qdp):
    """CRC32 (unsigned) over the top 10 asks (low -> high) then the top 10 bids (high -> low)."""
    parts = []
    for p in sorted(asks)[:KRAKEN_DEPTH]:
        parts.append(kr_fmt(p, pdp) + kr_fmt(asks[p], qdp))
    for p in sorted(bids, reverse=True)[:KRAKEN_DEPTH]:
        parts.append(kr_fmt(p, pdp) + kr_fmt(bids[p], qdp))
    return zlib.crc32("".join(parts).encode()) & 0xFFFFFFFF


class KrakenCore:
    def __init__(self, writer, symbols, precisions, log=None, clock_ms=now_ms):
        self.w = writer
        self.log = log
        self.clock_ms = clock_ms
        self.lock = threading.RLock()
        self.symbols = list(symbols)
        self.prec = dict(precisions)          # symbol -> (price_dp, qty_dp)
        self.books = {}                       # symbol -> {"bids": {Decimal: Decimal}, "asks": {...}}
        self.resync = set()                   # symbols waiting for a fresh snapshot after a checksum failure
        self.stats = collections.Counter()
        self.out = []
        self.connected = False
        self.mid = {}

    def take_out(self):
        with self.lock:
            o, self.out = self.out, []
        return o

    def on_connect(self):
        with self.lock:
            self.connected = True
            self.books.clear()
            self.resync.clear()
            if self.symbols:
                self.out.append({"method": "subscribe", "params": {"channel": "book", "symbol": list(self.symbols),
                                                                   "depth": KRAKEN_DEPTH, "snapshot": True}})
                self.out.append({"method": "subscribe", "params": {"channel": "trade", "symbol": list(self.symbols),
                                                                   "snapshot": False}})

    def drop_symbols(self, syms):
        with self.lock:
            gone = [s for s in self.symbols if s in syms]
            self.symbols = [s for s in self.symbols if s not in syms]
            if gone and self.connected:
                for ch in ("book", "trade"):
                    p = {"channel": ch, "symbol": gone}
                    if ch == "book":
                        p["depth"] = KRAKEN_DEPTH
                    self.out.append({"method": "unsubscribe", "params": p})
            return gone

    def _apply(self, sym, item, snapshot):
        bk = self.books.get(sym)
        if snapshot or bk is None:
            bk = self.books[sym] = {"bids": {}, "asks": {}}
        for side in ("bids", "asks"):
            for lv in item.get(side) or []:
                p, q = Decimal(str(lv["price"])), Decimal(str(lv["qty"]))
                if q == 0:
                    bk[side].pop(p, None)
                else:
                    bk[side][p] = q
        # keep only the subscribed depth (Kraken: levels pushed out of the top N are not deleted explicitly)
        if len(bk["bids"]) > KRAKEN_DEPTH:
            for p in sorted(bk["bids"], reverse=True)[KRAKEN_DEPTH:]:
                del bk["bids"][p]
        if len(bk["asks"]) > KRAKEN_DEPTH:
            for p in sorted(bk["asks"])[KRAKEN_DEPTH:]:
                del bk["asks"][p]
        return bk

    def on_frame(self, raw, rx=None):
        rx = self.clock_ms() if rx is None else rx
        try:
            m = json.loads(raw, parse_float=Decimal)
        except Exception:
            self.stats["unparsed"] += 1
            return None
        if not isinstance(m, dict):
            self.stats["not_object"] += 1
            return None
        with self.lock:
            ch = m.get("channel")
            if ch == "heartbeat":
                self.stats["heartbeat"] += 1
                return "heartbeat"
            m["_rx_ms"] = rx
            if ch == "book" and m.get("type") in ("snapshot", "update"):
                snap = m["type"] == "snapshot"
                oks = []
                for item in m.get("data") or []:
                    sym = item.get("symbol")
                    if sym not in self.prec:
                        self.stats["book_unknown_symbol"] += 1
                        continue
                    if not snap and sym in self.resync:
                        self.stats["book_update_while_resync"] += 1
                        oks.append(None)
                        continue
                    if not snap and sym not in self.books:
                        self.stats["book_update_before_snapshot"] += 1
                        oks.append(None)
                        continue
                    try:
                        bk = self._apply(sym, item, snap)
                    except (KeyError, InvalidOperation, TypeError, ValueError):
                        self.stats["book_bad_level"] += 1
                        oks.append(None)
                        continue
                    if snap:
                        self.resync.discard(sym)
                    want = item.get("checksum")
                    pdp, qdp = self.prec[sym]
                    got = kraken_checksum(bk["bids"], bk["asks"], pdp, qdp)
                    ok = want is not None and int(want) == got
                    oks.append(ok)
                    if ok:
                        self.stats["crc_ok"] += 1
                        if bk["bids"] and bk["asks"]:
                            self.mid[sym] = (max(bk["bids"]) + min(bk["asks"])) / 2
                    else:
                        self.stats["crc_fail"] += 1
                        self.books.pop(sym, None)
                        self.resync.add(sym)
                        self.out.append({"method": "unsubscribe", "params": {"channel": "book", "symbol": [sym],
                                                                             "depth": KRAKEN_DEPTH}})
                        self.out.append({"method": "subscribe", "params": {"channel": "book", "symbol": [sym],
                                                                           "depth": KRAKEN_DEPTH, "snapshot": True}})
                        if self.log is not None:
                            self.log.write("kraken_crc_fail", symbol=sym, want=want, got=got, type=m["type"])
                m["_crc_ok"] = oks[0] if len(oks) == 1 else oks
                self.w.write("kraken_book", m)
                return "book"
            if ch == "trade":
                self.stats["trade_frames"] += 1
                self.w.write("kraken_trade", m)
                return "trade"
            self.stats["status_" + str(ch or m.get("method"))[:20]] += 1
            self.w.write("kraken_status", m)
            return "status"


def kraken_precisions(fetch=None):
    """Kraken AssetPairs (public REST, one call): {wsname: (pair_decimals, lot_decimals)}; None on failure."""
    try:
        if fetch is None:
            req = urllib.request.Request(KRAKEN_ASSETPAIRS, headers={"User-Agent": "fxbook_rec"})
            with urllib.request.urlopen(req, timeout=15) as r:
                body = json.loads(r.read().decode())
        else:
            body = fetch()
        out = {}
        for _k, v in (body.get("result") or {}).items():
            ws = v.get("wsname")
            if ws in KRAKEN_SYMBOLS and v.get("status", "online") == "online":
                out[ws] = (int(v["pair_decimals"]), int(v["lot_decimals"]))
        return out
    except Exception:
        return None


def kraken_thread(core, stop, log, host=KRAKEN_WS_HOST, path=KRAKEN_WS_PATH, ws_factory=None, clock=None,
                  wait=None):
    ws_factory = ws_factory or WSClient
    clock = clock or time.time
    wait = wait or stop.wait
    backoff = 1
    while not stop.is_set():
        ws = None
        try:
            ws = ws_factory({}, host=host, path=path)
            ws.connect()
            ws.sock.settimeout(WS_RECV_TIMEOUT_S)
            core.on_connect()
            for c in core.take_out():
                ws.send(json.dumps(c))
            log.write("ws_connected", side="kraken", symbols=core.symbols)
            backoff = 1
            last_rx = last_ping = clock()
            while not stop.is_set():
                got, txt = recv_any(ws)
                t = clock()
                if got:
                    last_rx = t                  # any frame (Kraken also sends a text heartbeat every second)
                elif t - last_rx > WS_IDLE_RECONNECT_S:
                    raise ConnectionError("no frame in %d s" % WS_IDLE_RECONNECT_S)
                if txt is not None:
                    core.on_frame(txt, int(t * 1000))
                if t - last_ping > WS_PING_S:
                    ws.send(json.dumps({"method": "ping"}))
                    last_ping = t
                for c in core.take_out():
                    ws.send(json.dumps(c))
        except Exception as e:                                   # noqa: BLE001
            if stop.is_set():
                break
            log.write("ws_error", side="kraken", err=repr(e)[:240], retry_s=backoff)
            with core.lock:
                core.connected = False
            wait(backoff)
            backoff = min(backoff * 2, 30)
        finally:
            if ws is not None and ws.sock is not None:
                ws.close()
    log.write("ws_stopped", side="kraken")


# ------------------------------------------------------------------------------------------------ REST side
class RestPacer:
    """>= REST_GAP_S between calls, <= REST_WINDOW_MAX calls in any REST_WINDOW_S, and a 429 backs off
    REST_BACKOFF_S. The per-IP limit is shared with the live bots' discovery."""

    def __init__(self, fetch, clock=time.time, sleep=time.sleep):
        self.fetch, self.clock, self.sleep = fetch, clock, sleep
        self.last = -1e18
        self.calls = collections.deque()
        self.n = 0
        self.n429 = 0
        self.nerr = 0

    def get(self, path, params=None, tries=3):
        for _ in range(tries):
            t = self.clock()
            wait = self.last + REST_GAP_S - t
            while self.calls and self.calls[0] < t - REST_WINDOW_S:
                self.calls.popleft()
            if len(self.calls) >= REST_WINDOW_MAX:
                wait = max(wait, self.calls[0] + REST_WINDOW_S - t)
            if wait > 0:
                self.sleep(wait)
            t = self.clock()
            self.last = t
            self.calls.append(t)
            self.n += 1
            st, body = self.fetch(path, params)
            if st == 429:
                self.n429 += 1
                self.sleep(REST_BACKOFF_S)
                self.last = self.clock()
                continue
            if st != 200:
                self.nerr += 1
            return st, body
        return 429, None


class RestSide:
    def __init__(self, writer, kcore, pacer, log=None, clock=time.time):
        self.w, self.k, self.p, self.log, self.clock = writer, kcore, pacer, log, clock
        self.seen = {}                 # ticker -> (status, floor_strike, result)
        self.closes = {}               # ticker -> close_ms
        self.settled = {}              # ticker -> tries
        self.settle_next = {}          # ticker -> next try (s)
        self.prog_seen = {}            # id -> json of the row
        self.next_discover = 0.0
        self.next_programs = 0.0
        self.stats = collections.Counter()

    def discover(self):
        for s in self.k.series:
            for status in ("unopened", "open"):
                cursor = None
                for _page in range(3):
                    q = {"series_ticker": s, "status": status, "limit": "200"}
                    if cursor:
                        q["cursor"] = cursor
                    st, b = self.p.get("/markets", q)
                    if st != 200 or not isinstance(b, dict):
                        self.stats["discover_err"] += 1
                        if self.log is not None:
                            self.log.write("rest_error", path="/markets", series=s, status=st, body=str(b)[:160])
                        break
                    rx = int(self.clock() * 1000)
                    for mk in b.get("markets") or []:
                        tk = mk.get("ticker")
                        if not self.k.matches(tk):
                            continue
                        o, c = iso_ms(mk.get("open_time")), iso_ms(mk.get("close_time"))
                        if c:
                            self.closes[tk] = c
                        key = (mk.get("status"), mk.get("floor_strike"), mk.get("result"))
                        if self.seen.get(tk) != key:
                            self.seen[tk] = key
                            self.w.write("markets", {"type": "rest_market", "market": mk, "_rx_ms": rx})
                        self.k.track(tk, o, c, "rest_" + status)
                    cursor = b.get("cursor") or None
                    if not cursor or not b.get("markets"):
                        break

    def programs(self):
        cursor, pages, kept, rows_n = None, 0, 0, 0
        ok = True
        while pages < 12:
            q = {"limit": "1000"}
            if cursor:
                q["cursor"] = cursor
            st, b = self.p.get("/incentive_programs", q)
            pages += 1
            if st != 200 or not isinstance(b, dict):
                ok = False
                if self.log is not None:
                    self.log.write("rest_error", path="/incentive_programs", status=st, body=str(b)[:160])
                break
            rows = b.get("incentive_programs") or []
            rows_n += len(rows)
            rx = int(self.clock() * 1000)
            oldest = None
            for r in rows:
                s0 = iso_ms(r.get("start_date"))
                if s0 is not None and (oldest is None or s0 < oldest):
                    oldest = s0
                if not self.k.matches(r.get("market_ticker")):
                    continue
                kept += 1
                key = json.dumps(r, sort_keys=True)
                if self.prog_seen.get(r.get("id")) != key:
                    self.prog_seen[r.get("id")] = key
                    self.w.write("programs", {"type": "program", "row": r, "_rx_ms": rx})
            cursor = b.get("next_cursor") or b.get("cursor") or None
            if not cursor or not rows:
                break
            if oldest is not None and oldest < rx - PROGRAMS_LOOKBACK_S * 1000:
                break                          # newest-first: everything still to come began over an hour ago
        self.w.write("programs_poll", {"type": "programs_poll", "ok": ok, "pages": pages, "rows": rows_n,
                                       "kept": kept, "distinct_kept": len(self.prog_seen),
                                       "_rx_ms": int(self.clock() * 1000)})
        return ok, kept

    def settle_due(self):
        now = self.clock()
        for tk, c in list(self.closes.items()):
            if tk in self.settled and self.settled[tk] < 0:
                continue
            due = self.settle_next.get(tk, c / 1000.0 + SETTLE_AFTER_S)
            if now < due:
                continue
            st, b = self.p.get("/markets/%s" % tk)
            tries = self.settled.get(tk, 0) + 1
            mk = (b or {}).get("market") if isinstance(b, dict) else None
            rx = int(self.clock() * 1000)
            if st == 200 and isinstance(mk, dict):
                keep = {k: mk.get(k) for k in ("ticker", "status", "result", "expiration_value", "floor_strike",
                                               "volume_fp", "volume", "open_time", "close_time",
                                               "settlement_value_dollars", "settlement_ts", "open_interest_fp",
                                               "price_level_structure")}
                self.w.write("settled", {"type": "settled", "market": keep, "try": tries, "_rx_ms": rx})
                if mk.get("result") in ("yes", "no") or tries >= SETTLE_TRIES:
                    self.settled[tk] = -1
                    self.closes.pop(tk, None)
                    continue
            elif tries >= SETTLE_TRIES:
                self.settled[tk] = -1
                self.closes.pop(tk, None)
                if self.log is not None:
                    self.log.write("settle_giveup", ticker=tk, status=st)
                continue
            self.settled[tk] = tries
            self.settle_next[tk] = now + SETTLE_RETRY_S

    def step(self):
        t = self.clock()
        if t >= self.next_discover:
            self.next_discover = t + DISCOVER_S
            self.discover()
        t = self.clock()
        if t >= self.next_programs:
            self.next_programs = t + PROGRAMS_S
            self.programs()
        self.settle_due()


def rest_thread(rest, stop, log):
    while not stop.is_set():
        try:
            rest.step()
        except Exception as e:                                   # noqa: BLE001
            log.write("rest_thread_error", err=repr(e)[:240])
            stop.wait(5)
        stop.wait(1.0)


def kauth_fetch(path, params):
    import kauth
    return kauth.get(path, params, auth=False)


# ------------------------------------------------------------------------------------------------ the rails
def rails_check(free_gb, total_bytes, rss):
    """The stop rails, in order: free disk < 15 GB, results/fxbook > 3 GB, RSS > 150 MB. None = keep going.
    (A free-disk read that failed is -1 and does not stop the recorder; the health row shows it.)"""
    if 0 <= free_gb < FREE_DISK_STOP_GB:
        return "low_disk"
    if total_bytes > CAP_BYTES:
        return "fxbook_cap"
    if rss > RSS_ABORT_MB:
        return "rss_abort"
    return None


def big_hour_decision(hour, start_hour, hour_bytes, hour_deltas):
    """The 40 MB rule is applied once, to the first FULL hour (not the partial start hour) in which the FX books were
    actually trading (>= BIG_HOUR_MIN_DELTAS book deltas). An hour recorded while FX is closed (a start before Sunday
    17:00 ET) is skipped, so the rule is not spent on an empty hour (review 2026-10-17, should-fix).
    Returns 'skip_partial' | 'skip_closed' | 'drop' | 'keep'."""
    if hour == start_hour:
        return "skip_partial"
    if hour_deltas < BIG_HOUR_MIN_DELTAS:
        return "skip_closed"
    return "drop" if hour_bytes > BIG_HOUR_BYTES else "keep"


# ------------------------------------------------------------------------------------------------ the run
def run(args):
    if "--live" in sys.argv:
        raise SystemExit("REFUSING: there is no live mode in a read-only recorder")
    out_root = check_out_root(args.out)
    os.makedirs(out_root, exist_ok=True)
    lock = InstanceLock(args.lock)
    if not lock.acquire():
        raise SystemExit("another fxbook_rec holds %s (%s)" % (args.lock, lock.holder()))
    log = Log(args.log, echo=True)
    series = list(SERIES_STAGE1) + (list(SERIES_STAGE2) if args.stage2 else []) + list(args.extra_series or [])
    t0 = time.time()
    try:
        prec = kraken_precisions() if not args.no_kraken else {}
        prec_src = "assetpairs"
        if prec is None:
            prec = {s: ((3 if s == "USD/JPY" else 5), 8) for s in KRAKEN_SYMBOLS}
            prec_src = "default (AssetPairs unreadable)"
        symbols = [s for s in KRAKEN_SYMBOLS if s in prec]
        missing = [s for s in KRAKEN_SYMBOLS if s not in prec]
        log.write("start", argv=sys.argv, code_sha=code_sha(), pid=os.getpid(), python=sys.version.split()[0],
                  out=out_root, series=series, kraken_symbols=symbols, kraken_missing=missing,
                  kraken_precisions={k: list(v) for k, v in prec.items()}, kraken_prec_src=prec_src,
                  minutes=args.minutes, rss_mb=round(rss_mb(), 1), free_disk_gb=round(free_disk_gb(out_root), 1),
                  fxbook_bytes=dir_bytes(out_root))
        writer = HourWriter(out_root)
        kcore = KalshiCore(writer, series, log=log)
        krcore = KrakenCore(writer, symbols, prec, log=log)
        pacer = RestPacer(kauth_fetch)
        rest = RestSide(writer, kcore, pacer, log=log)
        stop = threading.Event()
        ths = []
        if not args.no_kalshi:
            import kauth
            ths.append(threading.Thread(target=kalshi_thread, name="kalshi",
                                        args=(kcore, stop, lambda: kauth.headers("GET", KALSHI_WS_PATH), log),
                                        daemon=True))
            ths.append(threading.Thread(target=rest_thread, name="rest", args=(rest, stop, log), daemon=True))
        if not args.no_kraken and symbols:
            ths.append(threading.Thread(target=kraken_thread, name="kraken", args=(krcore, stop, log),
                                        daemon=True))
        for th in ths:
            th.start()
        end_at = t0 + args.minutes * 60 if args.minutes and args.minutes > 0 else None
        start_hour = hour_tag(t0)
        big_checked = False
        last_health = t0
        last_hb = 0.0
        prev_lines = collections.Counter()
        why = None
        while True:
            time.sleep(0.5)
            t = time.time()
            if t - last_hb >= HEARTBEAT_S:
                last_hb = t
                writer.write("heartbeat", {"type": "heartbeat", "kalshi": kcore.connected,
                                           "kraken": krcore.connected, "pid": os.getpid(),
                                           "suspect_now": len(kcore.suspect), "_rx_ms": int(t * 1000)})
            if os.path.exists(STOP_PATH if args.stop is None else args.stop):
                why = "stop_file"
                break
            if end_at is not None and t >= end_at:
                why = "minutes_elapsed"
                break
            writer.tick()
            while writer.rolled:
                h = writer.rolled.pop(0)
                if not big_checked:
                    nb = writer.hour_bytes(h)
                    nd = (writer.rolled_lines.get(h) or {}).get(BOOK, 0)
                    dec = big_hour_decision(h, start_hour, nb, nd)
                    log.write("big_hour_check", hour=h, bytes=nb, book_deltas=nd, decision=dec,
                              limit=BIG_HOUR_BYTES, min_deltas=BIG_HOUR_MIN_DELTAS)
                    if dec in ("drop", "keep"):
                        big_checked = True          # the first full hour with trading FX books
                    if dec == "drop":
                        gone = kcore.drop_series(DROP_IF_BIG_SERIES)
                        gk = krcore.drop_symbols(DROP_IF_BIG_SYMBOLS)
                        log.write("dropped_aud_cad", hour_bytes=nb, tickers=gone, kraken=gk)
            if t - last_health >= HEALTH_S:
                span = t - last_health
                last_health = t
                lines = writer.lines.copy()
                rate = {c: round((lines[c] - prev_lines.get(c, 0)) / span, 2) for c in lines}
                prev_lines = lines
                nowm = int(t * 1000)
                with kcore.lock:
                    susp = (kcore.suspect_ms_closed + kcore.suspect_open_ms(nowm)) / 1000.0
                    kst = dict(kcore.stats)
                    lt, ld = list(kcore.lag_trade), list(kcore.lag_delta)
                    ntr, nsub = len(kcore.tracked), len(kcore.subscribed)
                    kconn = kcore.connected
                fd = free_disk_gb(out_root)
                tot = dir_bytes(out_root)
                rss = rss_mb()
                log.write("health", kalshi_connected=kconn, kraken_connected=krcore.connected,
                          lines_per_s=rate, seq_gaps=kst.get("seq_gaps", 0),
                          trade_seq_gaps=kst.get("trade_seq_gaps", 0),
                          book_resubscribes=kst.get("book_resubscribes", 0), suspect_s_total=round(susp, 1),
                          suspect_now=len(kcore.suspect), kraken_crc_ok=krcore.stats.get("crc_ok", 0),
                          kraken_crc_fail=krcore.stats.get("crc_fail", 0),
                          trade_lag_ms_median=median(lt), delta_lag_ms_median=median(ld),
                          bytes_this_hour=writer.hour_bytes(writer.hour) if writer.hour else 0,
                          fxbook_bytes=tot, free_disk_gb=round(fd, 2), rss_mb=round(rss, 1), tracked=ntr,
                          subscribed=nsub, rest_calls=pacer.n, rest_429=pacer.n429, rest_err=pacer.nerr,
                          programs_kept=len(rest.prog_seen), kalshi_stats=kst, kraken_stats=dict(krcore.stats),
                          write_errors=writer.write_errors)
                rail = rails_check(fd, tot, rss)
                if rail == "low_disk":
                    writer.disable("low_disk")
                    log.write("low_disk", free_disk_gb=round(fd, 2), limit_gb=FREE_DISK_STOP_GB)
                elif rail == "fxbook_cap":
                    writer.disable("cap")
                    log.write("fxbook_cap", bytes=tot, cap=CAP_BYTES)
                elif rail == "rss_abort":
                    log.write("rss_abort", rss_mb=round(rss, 1), limit_mb=RSS_ABORT_MB)
                if rail is not None:
                    why = rail
                    break
    except KeyboardInterrupt:
        why = "interrupted"
    finally:
        try:
            stop.set()
            for th in ths:
                th.join(timeout=8)
        except NameError:
            pass
        try:
            writer.close()
            log.write("stop", why=why, secs=round(time.time() - t0, 1), lines=dict(writer.lines),
                      kalshi_stats=dict(kcore.stats), kraken_stats=dict(krcore.stats), rest_calls=pacer.n,
                      rest_429=pacer.n429, suspect_s=round(kcore.suspect_ms_closed / 1000.0, 1))
        except NameError:
            pass
        log.close()
        lock.release()
    return 0


# ------------------------------------------------------------------------------------------------ self-test
def selftest():
    """Planted frames and a fake clock through the real classes; returns True or raises AssertionError. The temp
    directory is removed whether it passes or fails."""
    import tempfile
    tmp = tempfile.mkdtemp(prefix="fxbook_selftest_")
    try:
        return _selftest_body(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _selftest_body(tmp):
    n_checks = [0]

    def ck(cond, what):
        n_checks[0] += 1
        if not cond:
            raise AssertionError("SELFTEST FAIL: " + what)

    # -- units: decided from the field names, never from magnitudes
    ck(abs(cc_to_usd(500000) - 50.00) < 1e-12, "500000 centi-cents -> $50.00")
    ck(abs(cc_to_usd("200000") - 20.00) < 1e-12, "200000 centi-cents -> $20.00")
    ck(abs(price_dollars("0.5500") - 0.55) < 1e-12, "'0.5500' -> 0.55")
    for bad in ("55", "1.01", "-0.01", "x"):
        try:
            price_dollars(bad)
            ck(False, "a price %r must abort" % bad)
        except UnitError:
            ck(True, "unit abort")

    root = os.path.join(tmp, "fxbook")
    clock = [dt.datetime(2026, 10, 19, 13, 59, 59, tzinfo=UTC).timestamp()]
    wclock = lambda: clock[0]                                     # noqa: E731
    cms = lambda: int(clock[0] * 1000)                            # noqa: E731

    def read_lines(chan, hour):
        p = os.path.join(root, chan, hour + ".jsonl.gz")
        if not os.path.exists(p):
            return []
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            return [json.loads(x) for x in fh if x.strip()]

    # -- writer: rolls at the UTC hour, never writes outside its root
    wroot = os.path.join(tmp, "wtest")
    w = HourWriter(wroot, clock=wclock, flush_s=0.0)
    w.write("ticker", {"a": 1})
    clock[0] += 2                                                 # 14:00:01 -> a new hour
    w.write("ticker", {"a": 2})
    w.close()

    def wlines(hour):
        with gzip.open(os.path.join(wroot, "ticker", hour + ".jsonl.gz"), "rt", encoding="utf-8") as fh:
            return [json.loads(x)["a"] for x in fh if x.strip()]
    ck(wlines("20261019T13") == [1], "hour 13 file holds the first line")
    ck(wlines("20261019T14") == [2], "hour 14 file holds the second line")
    ck(w.rolled == ["20261019T13"], "one roll recorded")
    ck(w.rolled_lines == {"20261019T13": {"ticker": 1}} and dict(w.hour_lines) == {"ticker": 1},
       "per-hour line counts kept for the closed hour and restarted for the new one: %r" % w.rolled_lines)
    ck(sorted(os.listdir(wroot)) == ["ticker"], "nothing written outside the channel dirs")
    for bad in ("../evil", "a/b", "", "UPPER", "x" * 60):
        try:
            w.path_for(bad, "20261019T14")
            ck(False, "channel %r must be refused" % bad)
        except ValueError:
            ck(True, "bad channel refused")
    for bad_root in (r"C:\kals\kalshi_data\x", r"C:\kals\fxbook", os.path.join(tmp, "elsewhere")):
        try:
            check_out_root(bad_root)
            ck(False, "out root %s must be refused" % bad_root)
        except SystemExit:
            ck(True, "bad out root refused")
    ck(check_out_root(OUT_ROOT) == os.path.abspath(OUT_ROOT), "the default out root is accepted")

    # -- Kalshi frames (shapes from the collector's tape and livebook's protocol notes)
    sink = []
    log = Log(None, sink=sink)
    clock[0] = dt.datetime(2026, 10, 19, 14, 10, 0, tzinfo=UTC).timestamp()
    w = HourWriter(root, clock=wclock, flush_s=0.0)
    k = KalshiCore(w, SERIES_STAGE1, log=log, clock_ms=cms)
    TK = "KXEURUSD15M-26OCT191030-30"            # opens 14:15Z, closes 14:30Z
    TK2 = "KXGBPUSD15M-26OCT191030-30"
    open_ms = int(dt.datetime(2026, 10, 19, 14, 15, tzinfo=UTC).timestamp() * 1000)
    close_ms = open_ms + 900000
    k.on_connect()
    first = k.take_out()
    ck(len(first) == 1 and first[0]["params"] == {"channels": ["market_lifecycle_v2"]},
       "connect subscribes lifecycle only when nothing is tracked")
    # lifecycle: a non-FX frame is not written, an FX `created` frame tracks the market before it opens
    k.on_frame(json.dumps({"type": "market_lifecycle_v2", "sid": 1, "seq": 1, "msg": {
        "event_type": "determined", "market_ticker": "KXBTC15M-26OCT191030-30", "result": "yes"}}), cms())
    k.on_frame(json.dumps({"type": "market_lifecycle_v2", "sid": 1, "seq": 2, "msg": {
        "market_ticker": TK, "exchange_index": 0, "open_ts": open_ms // 1000, "close_ts": close_ms // 1000,
        "event_type": "created"}}), cms())
    k.on_frame(json.dumps({"type": "subscribed", "id": 1, "msg": {"channel": "market_lifecycle_v2", "sid": 1}}),
               cms())
    ck(TK in k.tracked and k.tracked[TK]["close_ms"] == close_ms, "created frame tracks the FX market")
    ck(k.stats["lifecycle_other"] == 1, "a non-FX lifecycle frame is counted, not written")
    k.track(TK2, open_ms, close_ms, "rest_unopened")
    k.track("KXBTC15M-26OCT191030-30", open_ms, close_ms, "rest_open")
    ck("KXBTC15M-26OCT191030-30" not in k.tracked, "a series not recorded is never tracked")
    k.pump()
    cmds = k.take_out()
    ck(len(cmds) == 1 and cmds[0]["cmd"] == "subscribe" and cmds[0]["params"]["market_tickers"] == [TK, TK2]
       and cmds[0]["params"]["channels"] == DATA_CHANNELS, "both FX markets subscribed at the next pump: %r" % cmds)
    for ch, sid in (("orderbook_delta", 4), ("trade", 5), ("ticker", 6)):
        k.on_frame(json.dumps({"type": "subscribed", "id": 2, "msg": {"channel": ch, "sid": sid}}), cms())
    k.on_frame(json.dumps({"type": "orderbook_snapshot", "sid": 4, "seq": 1, "msg": {
        "market_ticker": TK, "market_id": "x", "yes_dollars_fp": [["0.5500", "562.50"]],
        "no_dollars_fp": [["0.4000", "10.00"], ["0.3900", "75.00"]]}}), cms())
    k.on_frame(json.dumps({"type": "orderbook_snapshot", "sid": 4, "seq": 2, "msg": {
        "market_ticker": TK2, "market_id": "y"}}), cms())
    k.on_frame(json.dumps({"type": "orderbook_delta", "sid": 4, "seq": 3, "msg": {
        "market_ticker": TK, "market_id": "x", "price_dollars": "0.5500", "delta_fp": "-12.50", "side": "yes",
        "ts": "2026-10-19T14:10:00Z", "ts_ms": cms() - 30}}), cms())
    k.on_frame(json.dumps({"type": "trade", "sid": 5, "seq": 1, "msg": {
        "trade_id": "t1", "market_ticker": TK, "yes_price_dollars": "0.5500", "no_price_dollars": "0.4500",
        "count_fp": "12.50", "taker_side": "no", "is_block_trade": False, "ts": cms() // 1000,
        "ts_ms": cms() - 4000}}), cms())
    k.on_frame(json.dumps({"type": "ticker", "sid": 6, "msg": {
        "market_ticker": TK, "price_dollars": "0.5500", "yes_bid_dollars": "0.5500", "yes_ask_dollars": "0.6000",
        "yes_bid_size_fp": "550.00", "yes_ask_size_fp": "10.00", "volume_fp": "12.50", "ts_ms": cms()}}), cms())
    ck(k.stats["seq_gaps"] == 0, "no gap on a clean sequence")
    ck(list(k.lag_delta) == [30] and list(k.lag_trade) == [4000], "delta and trade lags measured from ts_ms")
    # a planted seq gap on the book sid: exactly one resubscribe and one suspect span
    clock[0] += 1
    k.on_frame(json.dumps({"type": "orderbook_delta", "sid": 4, "seq": 6, "msg": {
        "market_ticker": TK, "price_dollars": "0.5500", "delta_fp": "5.00", "side": "yes", "ts_ms": cms()}}), cms())
    gap_ms = cms()
    clock[0] += 0.25
    k.on_frame(json.dumps({"type": "orderbook_delta", "sid": 4, "seq": 9, "msg": {
        "market_ticker": TK, "price_dollars": "0.5500", "delta_fp": "5.00", "side": "yes", "ts_ms": cms()}}), cms())
    # a buffer-overflow error inside the same episode must not start a second resubscribe
    k.on_frame(json.dumps({"type": "error", "msg": {"code": 25, "msg": "Subscription buffer overflow"}}), cms())
    ck(k.stats["gap_while_resub"] == 1, "a second trigger while the resubscribe is pending is only counted")
    cmds = k.take_out()
    ck([c["cmd"] for c in cmds] == ["unsubscribe", "subscribe"], "one unsubscribe + one subscribe: %r" % cmds)
    ck(cmds[0]["params"] == {"sids": [4]} and cmds[1]["params"]["channels"] == [BOOK]
       and cmds[1]["params"]["market_tickers"] == [TK, TK2], "the book sid is replaced for every market")
    ck(k.stats["book_resubscribes"] == 1 and k.stats["seq_gaps"] == 1 and k.stats["dead_sid_frames"] == 1,
       "a later frame on the dead sid is not a second gap: %r" % dict(k.stats))
    k.on_frame(json.dumps({"type": "subscribed", "id": 9, "msg": {"channel": "orderbook_delta", "sid": 7}}), cms())
    clock[0] += 0.25
    k.on_frame(json.dumps({"type": "orderbook_snapshot", "sid": 7, "seq": 1, "msg": {
        "market_ticker": TK, "yes_dollars_fp": [["0.5500", "560.00"]], "no_dollars_fp": [["0.4000", "10.00"]]}}),
        cms())
    clock[0] += 0.5
    k.on_frame(json.dumps({"type": "orderbook_snapshot", "sid": 7, "seq": 2, "msg": {"market_ticker": TK2}}), cms())
    k.on_frame(json.dumps({"type": "orderbook_delta", "sid": 7, "seq": 3, "msg": {
        "market_ticker": TK, "price_dollars": "0.5500", "delta_fp": "1.00", "side": "yes", "ts_ms": cms()}}), cms())
    ck(k.stats["seq_gaps"] == 1 and not k.suspect, "suspect spans closed by the fresh snapshots")
    ck(k.suspect_ms_closed == (gap_ms + 500 - gap_ms) + (gap_ms + 1000 - gap_ms), "suspect ms = 500 + 1000")
    # a trade-sid gap is counted and written, never a book resubscribe
    k.on_frame(json.dumps({"type": "trade", "sid": 5, "seq": 3, "msg": {"market_ticker": TK, "ts_ms": cms()}}),
               cms())
    ck(k.stats["trade_seq_gaps"] == 1 and k.stats["book_resubscribes"] == 1, "trade gap counted, no resubscribe")
    # buffer overflow error on the book sid -> resubscribe (a new episode)
    k.on_frame(json.dumps({"type": "error", "sid": 7, "msg": {"code": 25, "msg": "Subscription buffer overflow"}}),
               cms())
    ck(k.stats["book_resubscribes"] == 2, "code 25 on the book sid resubscribes")
    k.take_out()
    k.on_frame(json.dumps({"type": "subscribed", "id": 12, "msg": {"channel": "orderbook_delta", "sid": 8}}), cms())
    for tk in (TK, TK2):
        k.on_frame(json.dumps({"type": "orderbook_snapshot", "sid": 8, "seq": 1 if tk == TK else 2,
                               "msg": {"market_ticker": tk}}), cms())
    # drop 10 min after close: update_subscription delete on each data sid
    clock[0] = close_ms / 1000.0 + 599
    k.pump()
    ck(not k.take_out() and TK in k.tracked, "not dropped before close + 10 min")
    clock[0] = close_ms / 1000.0 + 601
    k.pump()
    cmds = k.take_out()
    ck(len(cmds) == 3 and all(c["cmd"] == "update_subscription" and c["params"]["action"] == "delete_markets"
                              for c in cmds) and sorted(c["params"]["sids"][0] for c in cmds) == [5, 6, 8]
       and TK not in k.tracked, "dropped 10 min after close on sids 8/5/6: %r" % cmds)
    # disconnect -> every subscribed market suspect (none left here after the drop, so nothing is started)
    k.on_disconnect("test")
    ck(not k.suspect, "a disconnect with nothing subscribed starts no span")
    w.close()
    h = "20261019T14"
    ck(len(read_lines("orderbook_snapshot", h)) == 6 and len(read_lines("orderbook_delta", h)) == 4,
       "snapshot/delta frames written to their channel files")
    ck(len(read_lines("trade", h)) == 2 and len(read_lines("ticker", h)) == 1, "trade and ticker written")
    lc = read_lines("market_lifecycle_v2", h)
    ck(len(lc) == 1 and lc[0]["msg"]["market_ticker"] == TK and "_rx_ms" in lc[0] and "_rx_n" in lc[0],
       "lifecycle: only the FX frame, with _rx_ms and _rx_n")
    sp = read_lines("suspect", h)
    starts = [s for s in sp if s.get("state") == "start"]
    ends = [s for s in sp if s.get("state") == "end"]
    ck(len(starts) == 2 and starts[0]["why"] == "seq_gap" and starts[0]["tickers"] == [TK, TK2]
       and starts[0]["expected"] == 4 and starts[0]["got"] == 6, "one suspect span per gap episode: %r" % starts)
    ck(len(ends) == 4 and ends[0]["tickers"] == [TK] and ends[0]["suspect_ms"] == 500, "suspect ends: %r" % ends)
    ck(any(s.get("type") == "trade_gap" for s in sp), "trade gap row written")
    rxn = [r["_rx_n"] for c in ("orderbook_snapshot", "orderbook_delta") for r in read_lines(c, h)]
    ck(len(set(rxn)) == len(rxn), "receive counters are unique")

    # -- Kraken: checksum string built by hand (the format rules), then a planted mismatch is caught
    ck(kr_fmt(Decimal("1.12365"), 5) == "112365" and kr_fmt(Decimal("1606"), 8) == "160600000000"
       and kr_fmt(Decimal("0.00000500"), 8) == "500" and kr_fmt(Decimal("0.05005"), 5) == "5005",
       "Kraken field format: '.' and leading zeros removed at the pair precision")
    bids = {Decimal("1.12365"): Decimal("1606"), Decimal("1.12364"): Decimal("0.5")}
    asks = {Decimal("1.12366"): Decimal("8900"), Decimal("1.12370"): Decimal("2.25")}
    hand = "112366" + "890000000000" + "112370" + "225000000" + "112365" + "160600000000" + "112364" + "50000000"
    ck(kraken_checksum(bids, asks, 5, 8) == (zlib.crc32(hand.encode()) & 0xFFFFFFFF),
       "checksum = CRC32 of asks low->high then bids high->low")
    w2 = HourWriter(root, clock=wclock, flush_s=0.0)
    kr = KrakenCore(w2, ["EUR/USD"], {"EUR/USD": (5, 8)}, log=log, clock_ms=cms)
    kr.on_connect()
    sub = kr.take_out()
    ck(sub[0]["params"]["channel"] == "book" and sub[0]["params"]["depth"] == 10, "book depth 10 subscribed")
    good = kraken_checksum(bids, asks, 5, 8)
    snap = {"channel": "book", "type": "snapshot", "data": [{"symbol": "EUR/USD",
            "bids": [{"price": 1.12365, "qty": 1606.0}, {"price": 1.12364, "qty": 0.5}],
            "asks": [{"price": 1.12366, "qty": 8900.0}, {"price": 1.1237, "qty": 2.25}], "checksum": good}]}
    kr.on_frame(json.dumps(snap), cms())
    ck(kr.stats["crc_ok"] == 1 and kr.stats["crc_fail"] == 0, "a correct snapshot checksum passes")
    ck(kr.mid["EUR/USD"] == Decimal("1.123655"), "Kraken mid from the validated book")
    b2 = dict(bids)
    b2[Decimal("1.12364")] = Decimal("3")
    upd_ok = {"channel": "book", "type": "update", "data": [{"symbol": "EUR/USD",
              "bids": [{"price": 1.12364, "qty": 3.0}], "asks": [], "checksum": kraken_checksum(b2, asks, 5, 8),
              "timestamp": "2026-10-19T14:10:01.000000Z"}]}
    kr.on_frame(json.dumps(upd_ok), cms())
    ck(kr.stats["crc_ok"] == 2, "a correct update checksum passes")
    upd_bad = {"channel": "book", "type": "update", "data": [{"symbol": "EUR/USD",
               "bids": [{"price": 1.12363, "qty": 7.0}], "asks": [], "checksum": 12345,
               "timestamp": "2026-10-19T14:10:02.000000Z"}]}
    kr.on_frame(json.dumps(upd_bad), cms())
    out = kr.take_out()
    ck(kr.stats["crc_fail"] == 1 and "EUR/USD" in kr.resync and [o["method"] for o in out] ==
       ["unsubscribe", "subscribe"], "a planted checksum mismatch is caught and resubscribed")
    kr.on_frame(json.dumps(upd_ok), cms())
    ck(kr.stats["book_update_while_resync"] == 1, "updates are not applied until the fresh snapshot")
    kr.on_frame(json.dumps(snap), cms())
    ck("EUR/USD" not in kr.resync and kr.stats["crc_ok"] == 3, "the fresh snapshot ends the resync")
    kr.on_frame(json.dumps({"channel": "heartbeat"}), cms())
    kr.on_frame(json.dumps({"channel": "trade", "type": "update", "data": [{"symbol": "EUR/USD", "side": "buy",
                "price": 1.12366, "qty": 3.0, "ord_type": "market", "trade_id": 1,
                "timestamp": "2026-10-19T14:10:03.000000Z"}]}), cms())
    # depth truncation: 12 bid levels in a snapshot keep only the best 10 in the checksum book
    many = [{"price": float(Decimal("1.12300") + Decimal(i) / Decimal(100000)), "qty": 1.0} for i in range(12)]
    bk12 = {Decimal("1.12300") + Decimal(i) / Decimal(100000): Decimal("1") for i in range(2, 12)}
    kr.on_frame(json.dumps({"channel": "book", "type": "snapshot", "data": [{"symbol": "EUR/USD", "bids": many,
                "asks": [{"price": 1.124, "qty": 1.0}],
                "checksum": kraken_checksum(bk12, {Decimal("1.124"): Decimal("1")}, 5, 8)}]}), cms())
    ck(kr.stats["crc_ok"] == 4 and len(kr.books["EUR/USD"]["bids"]) == 10, "book truncated to depth 10")
    w2.close()
    kb = read_lines("kraken_book", h)
    ck([r["_crc_ok"] for r in kb] == [True, True, False, None, True, True], "_crc_ok flags written: %r"
       % [r["_crc_ok"] for r in kb])
    ck(len(read_lines("kraken_trade", h)) == 1 and kr.stats["heartbeat"] == 1, "trade written, heartbeat counted")
    ck(kraken_precisions(lambda: {"error": [], "result": {"ZEURZUSD": {"wsname": "EUR/USD", "pair_decimals": 5,
       "lot_decimals": 8, "status": "online"}, "X": {"wsname": "BTC/USD", "pair_decimals": 1,
       "lot_decimals": 8}}}) == {"EUR/USD": (5, 8)}, "AssetPairs: only the FX pairs listed are kept")

    # -- REST: pacing, the 429 back-off, discovery, programs, settlement 6 min after close
    rclock = [1000.0]
    slept = []

    def fsleep(s):
        slept.append(round(s, 3))
        rclock[0] += s
    calls = []
    replies = collections.deque([(429, {"error": "too many"})])

    def ffetch(path, params):
        calls.append((round(rclock[0], 3), path, dict(params or {})))
        if replies:
            return replies.popleft()
        if path == "/markets":
            if params.get("status") == "unopened" and params.get("series_ticker") == "KXEURUSD15M":
                return 200, {"markets": [{"ticker": TK, "status": "initialized",
                                          "open_time": "2026-10-19T14:15:00Z", "close_time": "2026-10-19T14:30:00Z"}],
                             "cursor": ""}
            return 200, {"markets": [], "cursor": ""}
        if path == "/incentive_programs":
            if not params.get("cursor"):
                return 200, {"incentive_programs": [
                    {"id": "p1", "market_ticker": TK, "period_reward": 500000, "target_size_fp": "300.00",
                     "discount_factor_bps": 5000, "start_date": "2026-10-19T14:15:00Z",
                     "end_date": "2026-10-19T14:30:00Z", "paid_out": False},
                    {"id": "p2", "market_ticker": "KXBTC15M-X", "period_reward": 1}], "next_cursor": "c2"}
            if params.get("cursor") == "c2":
                return 200, {"incentive_programs": [
                    {"id": "p4", "market_ticker": TK2, "period_reward": 500000, "target_size_fp": "300.00",
                     "discount_factor_bps": 5000, "start_date": "2026-10-19T11:00:00Z",
                     "end_date": "2026-10-19T11:15:00Z", "paid_out": True}], "next_cursor": "c3"}
            return 200, {"incentive_programs": [{"id": "p9", "market_ticker": TK2}], "next_cursor": ""}
        if path.startswith("/markets/"):
            return 200, {"market": {"ticker": path.split("/")[-1], "status": "finalized", "result": "yes",
                                    "volume_fp": "12.50", "expiration_value": "1.12370", "floor_strike": 1.1236}}
        return 404, {}
    pacer = RestPacer(ffetch, clock=lambda: rclock[0], sleep=fsleep)
    w3 = HourWriter(root, clock=wclock, flush_s=0.0)
    k3 = KalshiCore(w3, SERIES_STAGE1, log=log, clock_ms=lambda: int(rclock[0] * 1000))
    rclock[0] = open_ms / 1000.0 - 3600
    rest = RestSide(w3, k3, pacer, log=log, clock=lambda: rclock[0])
    rest.discover()
    ck(pacer.n429 == 1 and 10.0 in slept, "a 429 backs off 10 s: %r" % slept)
    gaps = [b[0] - a[0] for a, b in zip(calls, calls[1:])]
    ck(all(g >= 2.0 - 1e-9 for g in gaps), "calls >= 2 s apart: %r" % gaps)
    ck(len(calls) == 11, "10 discovery calls + the retried one: %d" % len(calls))
    ck(TK in k3.tracked and k3.tracked[TK]["src"] == "rest_unopened", "unopened market tracked before its open")
    np0 = sum(1 for c in calls if c[1] == "/incentive_programs")
    ok, kept = rest.programs()
    ck(ok and kept == 2, "programs: the FX rows kept, the other series dropped: %d" % kept)
    ck(sum(1 for c in calls if c[1] == "/incentive_programs") - np0 == 2,
       "paging stops at a page whose oldest program began over an hour ago (page c3 never read)")
    rest.programs()
    n_before = len(calls)
    rclock[0] = close_ms / 1000.0 + SETTLE_AFTER_S - 1
    rest.settle_due()
    ck(len(calls) == n_before, "no settlement GET before close + 6 min")
    rclock[0] = close_ms / 1000.0 + SETTLE_AFTER_S + 1
    rest.settle_due()
    rest.settle_due()
    ck(len(calls) == n_before + 1 and calls[-1][1] == "/markets/" + TK, "one settlement GET at close + 6 min")
    w3.close()
    pr = read_lines("programs", h)
    ck(len(pr) == 2 and pr[0]["row"]["period_reward"] == 500000 and abs(cc_to_usd(pr[0]["row"]["period_reward"])
       - 50.0) < 1e-12, "program rows are written once (unchanged on the 2nd poll) and parse to $50.00")
    ck(len(read_lines("programs_poll", h)) == 2 and len(read_lines("markets", h)) == 1, "poll rows + market row")
    st = read_lines("settled", h)
    ck(len(st) == 1 and st[0]["market"]["result"] == "yes" and st[0]["market"]["volume_fp"] == "12.50",
       "settled row written with result and volume_fp")
    # pacing window: 40 back-to-back calls never exceed 30 in 60 s
    calls.clear()
    replies.clear()
    for _ in range(40):
        pacer.get("/markets", {"series_ticker": "KXGBPUSD15M", "status": "open"})
    ts = [c[0] for c in calls]
    ck(max(sum(1 for y in ts if x <= y < x + REST_WINDOW_S) for x in ts) <= REST_WINDOW_MAX,
       "<= 30 calls in any 60 s")

    # -- the REAL socket loops (kalshi_thread, kraken_thread) against fake sockets on a fake clock (review
    #    2026-10-17): a socket that only pings is kept; total silence reconnects at 60 s; a drop marks every
    #    subscribed market suspect and the reconnect resubscribes every tracked market
    def drive(side, script, setup=None, max_fake_s=400.0):
        fclock = [dt.datetime(2026, 10, 19, 14, 0, tzinfo=UTC).timestamp()]
        t_start = fclock[0]
        env = {"connects": [], "sent": [], "seen": {}}
        stop = threading.Event()
        lsink = []
        flog = Log(None, sink=lsink)
        fw = HourWriter(os.path.join(tmp, "drive_" + side), clock=lambda: fclock[0], flush_s=0.0)
        fcms = lambda: int(fclock[0] * 1000)                       # noqa: E731
        if side == "kalshi":
            core = KalshiCore(fw, SERIES_STAGE1, log=flog, clock_ms=fcms)
        else:
            core = KrakenCore(fw, ["EUR/USD"], {"EUR/USD": (5, 8)}, log=flog, clock_ms=fcms)
        if setup:
            setup(core, fclock)

        class FakeWS(object):
            def __init__(self, headers, host=None, path=None):
                self.sock = self
                self.n = 0
                self.conn = 0

            def connect(self):
                env["connects"].append(fclock[0])
                self.conn = len(env["connects"])

            def settimeout(self, s):
                pass

            def send(self, payload, opcode=0x1):
                if opcode == 0x1:
                    env["sent"].append((self.conn, json.loads(payload)))

            def recv_text(self):
                self.n += 1
                if fclock[0] - t_start > max_fake_s:
                    stop.set()
                    return None
                return script(self, fclock, stop, core, env)

            def close(self):
                pass

        def fwait(s):
            fclock[0] += s
            return stop.is_set()
        if side == "kalshi":
            kalshi_thread(core, stop, lambda: {}, flog, ws_factory=FakeWS, clock=lambda: fclock[0], wait=fwait)
        else:
            kraken_thread(core, stop, flog, ws_factory=FakeWS, clock=lambda: fclock[0], wait=fwait)
        fw.close()
        env["errors"] = [r.get("err") for r in lsink if r.get("ev") == "ws_error"]
        env["core"] = core
        return env

    def ping_only(ws, fclock, stop, core, env):
        fclock[0] += 5.0                         # a 5 s receive timeout ...
        if ws.n % 2 == 0:
            return None                          # ... or a server ping (answered with a pong inside recv_text)
        raise socket.timeout()

    def silent(ws, fclock, stop, core, env):
        fclock[0] += 5.0
        if len(env["connects"]) >= 2:
            stop.set()
            return None
        raise socket.timeout()
    for side in ("kalshi", "kraken"):
        e = drive(side, ping_only)
        ck(len(e["connects"]) == 1 and not e["errors"], "%s: a socket that only pings (every 10 s, no text for 400 s) "
           "is kept: %d connects, errors %r" % (side, len(e["connects"]), e["errors"][:1]))
        e = drive(side, silent)
        gap = e["connects"][1] - e["connects"][0] if len(e["connects"]) > 1 else None
        ck(gap is not None and WS_IDLE_RECONNECT_S < gap <= WS_IDLE_RECONNECT_S + 10 and e["errors"]
           and "no frame in 60 s" in e["errors"][0], "%s: 60 s with no frame at all reconnects: gap %r, %r"
           % (side, gap, e["errors"][:1]))
    TKa = "KXEURUSD15M-26OCT191030-30"
    TKb = "KXGBPUSD15M-26OCT191030-30"

    def track_two(core, fclock):
        o = int(dt.datetime(2026, 10, 19, 14, 15, tzinfo=UTC).timestamp() * 1000)
        core.track(TKa, o, o + 900000, "rest_unopened")
        core.track(TKb, o, o + 900000, "rest_unopened")

    def drop_once(ws, fclock, stop, core, env):
        fclock[0] += 0.2
        if ws.conn == 1 and ws.n >= 3:
            raise ConnectionError("socket closed")
        if ws.conn == 2:
            env["seen"].setdefault("suspect_on_reconnect", sorted(core.suspect))
            if ws.n >= 3:
                stop.set()
        return None
    e = drive("kalshi", drop_once, setup=track_two)
    subs2 = [c for conn, c in e["sent"] if conn == 2 and c.get("cmd") == "subscribe"]
    ck(e["seen"].get("suspect_on_reconnect") == [TKa, TKb], "a drop marks every subscribed market suspect: %r"
       % e["seen"].get("suspect_on_reconnect"))
    ck(any(c["params"].get("channels") == DATA_CHANNELS and c["params"].get("market_tickers") == [TKa, TKb]
           for c in subs2) and any(c["params"].get("channels") == ["market_lifecycle_v2"] for c in subs2),
       "the reconnect resubscribes lifecycle and every tracked market: %r" % subs2)
    sp_drop = [json.loads(x) for x in gzip.open(os.path.join(tmp, "drive_kalshi", "suspect", "20261019T14.jsonl.gz"),
                                                "rt", encoding="utf-8")]
    ck(len(sp_drop) == 1 and sp_drop[0]["why"] == "disconnect" and sp_drop[0]["tickers"] == [TKa, TKb],
       "the drop is written as one suspect start frame: %r" % sp_drop)

    # -- the rails at their thresholds, and the 40 MB first-hour rule
    ck(rails_check(14.9, 0, 50.0) == "low_disk" and rails_check(15.1, 0, 50.0) is None,
       "free disk under 15 GB stops the recorder, over it does not")
    ck(rails_check(100.0, int(3.01 * 1024 ** 3), 50.0) == "fxbook_cap"
       and rails_check(100.0, int(2.99 * 1024 ** 3), 50.0) is None, "results/fxbook over 3 GB stops it")
    ck(rails_check(100.0, 0, 150.5) == "rss_abort" and rails_check(100.0, 0, 149.5) is None, "RSS over 150 MB stops it")
    ck(rails_check(-1.0, 0, 50.0) is None, "an unreadable free-disk value (-1) does not stop it")
    mb = 1024 ** 2
    ck(big_hour_decision("20261018T20", "20261018T19", 50 * mb, 0) == "skip_closed"
       and big_hour_decision("20261018T19", "20261018T19", 50 * mb, 9000) == "skip_partial"
       and big_hour_decision("20261018T22", "20261018T19", 41 * mb, 9000) == "drop"
       and big_hour_decision("20261018T22", "20261018T19", 39 * mb, 9000) == "keep",
       "40 MB rule: not spent on the partial start hour or a closed-FX hour; drops AUD/CAD only over 40 MB")

    # -- no order verb, no tape loader: the source scan (tokens built so the scan does not find itself)
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    for bad in ("PO" + "ST", "DEL" + "ETE", "/port" + "folio", "am" + "end", "bat" + "ched", "load_" + "quotes",
                "import " + "replay", "from replay" + " import"):
        ck(bad not in src, "forbidden token in source: %s" % bad)
    ck(re.search(r"Request\([^)]*\bdata\s*=", src) is None, "no request body anywhere")
    ck(re.search(r"method\s*=\s*['\"](?!GET)", src) is None, "no non-GET method")
    print("fxbook_rec selftest OK: %d checks (units, hour roll, out-root guard, frame routing, 1 resubscribe per "
          "gap episode, suspect spans 500+1000 ms, drop at close+10 min, Kraken CRC pass/mismatch/resync, "
          "depth-10 truncation, REST 429 back-off + pacing, programs, settlement at close+6 min, the real socket loops "
          "on fake sockets (ping-only kept, silence reconnects at 60 s, a drop marks markets suspect, the reconnect "
          "resubscribes them), the disk / cap / RSS rails at their thresholds, the 40 MB rule, source scan)"
          % n_checks[0])
    return True


def main():
    ap = argparse.ArgumentParser(description="READ-ONLY FX 15M book recorder (fxreward paper)",
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--minutes", type=float, default=0.0, help="0 = run until the stop file")
    ap.add_argument("--stage2", action="store_true", help="also KXPALLADIUM15M and KXPLATINUM15M")
    ap.add_argument("--extra-series", nargs="*", default=[], help="smoke only: also record these series")
    ap.add_argument("--out", default=OUT_ROOT)
    ap.add_argument("--log", default=LOG_PATH)
    ap.add_argument("--lock", default=LOCK_PATH)
    ap.add_argument("--stop", default=None, help="stop file (default results/fxbook-rec.stop)")
    ap.add_argument("--no-kalshi", action="store_true")
    ap.add_argument("--no-kraken", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return 0 if selftest() else 1
    if os.environ.get("KALS_SELFTESTED") != "1":
        selftest()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
