r"""kalshi_watch.py -- every 30 minutes, a scan for anything Kalshi, the index or the server changed under pin; every
change goes to the phone in plain words, the old value beside the new one.

The operator, 11-07: "add some feedback and alarms where we have something that runs a scan to catch any kalshi
changes". research\kalshiwatch.py (09-25) was the laptop's hourly shape watcher: it never reached the phone and does not
run on the server. This one is built for the server, like research\pinrules_watch.py: the scheduled task KalsKalshiWatch
(results\kalshi_watch_install.ps1) runs ONE scan every 30 minutes as SYSTEM and exits.

THE CHECKS (each its own status, its own baseline in the state file, its own failure streak):
  changelog     Kalshi's API changelog: https://docs.kalshi.com/changelog/rss.xml (its 15 newest entries), else
                changelog.md (the whole history: "**November 12, 2026**" lines, each followed by its text; the older
                <Update> blocks are read too), else the page /changelog and the RSS link it names. Every NEW entry is an
                alert with its date and title. Its date is the day it takes effect (the RSS link's anchor,
                "#november-12-2026", or "TBD"), not the day it was posted (pubDate, said beside it): on 11-07 the feed's
                newest entry was posted Nov 6 for Nov 12. URGENT when its words name any of URGENT_WORDS (remove,
                deprecat, breaking, rename, crypto, 15M, fee, order, orderbook, balance, exchange_index, shard, rate
                limit, websocket, settlement, price_level, tick, subaccount, api key) AND it can reach pin: an entry the
                RSS tags only for Kalshi's Margin exchange or only for FIX is an alert, never urgent (pin trades the
                Predictions exchange over REST and WebSocket; 6 of the 11 word hits on 11-07 were Margin or FIX only).
                Word refinements, all tested: 'tick' is not 'ticker' or 'candlesticks', 'fee' not 'feed', 'order' not
                'border' or 'recorder', '15M' not '215MB'; 'remove' also counts 'removal'. An entry is the same entry
                whichever source it came from (its key, or the first words of its text: changelog.md has no titles),
                so a source switch says nothing: after one, only an entry dated after everything seen or posted since
                the last scan is news (changelog.md holds a year the RSS never listed). A seen entry whose date moves
                (TBD -> a day) is said once. More than CHANGELOG_EACH new entries in one scan are ONE message (a format change never floods
                the phone).
  kalshi_api    SIGNED GETs through research\kauth.py (pin's key, pin's signer), at most MAX_CALLS a scan, at least
                CALL_GAP_S apart, never an unsigned call (the server's address shares a tiny public budget with the FX
                taker's unsigned calls; web_fetch refuses Kalshi's API hosts). Each scan, in this order: GET
                /exchange/status, /series/fee_changes, /markets?series_ticker=S&status=open&limit=5 for each of SERIES
                (10), /exchange/schedule, /portfolio/balance, and /series/S for 6 of the 10 in turn (each series every
                second scan) = 20 reads. Compared with the baseline: every key of every answer (a new key is an alert, a
                missing key URGENT when it was there at the baseline: at once for the series, status and balance
                answers' keys at most 2 deep; after 2 scans in a row for a market's own fields and deeper keys; a key
                that came after the baseline and goes again is said, not urgent; a key that went and came back is never
                said gone again; an empty list is not a missing field); the series' fee type, fee multiplier, settlement
                sources and contract urls; each market's price steps (price_level_structure, price_ranges), settlement
                timer and exchange_index (URGENT), and its rules text (sha256 of rules_primary with dates, clock times
                and numbers blanked by kalshiwatch.norm_rules: a new market is not a change, a new sentence is URGENT;
                the fixed-strike wording, "is at least 2045.23" with ETHUSD_RTI, counts as the opening-price wording
                of the same index, "is at least the simple average ... before 2:15 AM" with ETHUSDRTI: rules_key,
                v-kwfalse 11-13);
                any fee change scheduled on one of our series (URGENT); trading paused outside Kalshi's schedule and
                outside Thursday 3-5 AM ET (URGENT while it lasts); a new maintenance window other than the usual
                Thursday 3-5 AM ET one; the balance answer's SHAPE only (its amount is never stored or said). HTTP
                errors: 401/403 (Kalshi refused pin's own key) and 404/410 (an endpoint or series gone) URGENT at once;
                429 on two scans running; a network error or 5xx counts toward the failure streak (3 network errors in
                a row end the scan's reads).
  contract_pdf  https://assets.kalshi.com/contract_terms/CRYPTO15M.pdf: its sha256 (URGENT on change: the rules of the
                contract pin trades).
  cfb_pdf       CF Benchmarks' constituent exchanges PDF: its sha256 (which exchanges make the index).
                Both hashes leave out what a server may stamp on each copy (/CreationDate, /ModDate, /ID, XMP dates); a
                PDF that still changes on PDF_NOISY scans running says so once, quietly, and then only on /watch until
                it holds still (the CF PDF read the same twice on 11-07). The CF PDF with no answer at all (-1) on
                PDF_REFUSED (48) scans running is marked 'site refuses' the same way: said once, quietly, then only on
                /watch (not a failing check) until it answers (v-kwfalse 11-13: -1 on all 226 scans 11-08..11-13).
  cfb_status    https://status.cfbenchmarks.com/ (its incidents.json, else history.rss / history.atom): every new
                incident is an alert; URGENT only while it is not resolved AND it names an index pin settles on (BRTI,
                ETHUSD_RTI ... HYPEUSD_RTI, "Bitcoin Real Time Index") or all of CF's indices / its platform. On 11-07
                the page listed 50 incidents, none for those indices (volatility indices, funding rates, small coins).
  pin_log       pin's live log, the newest results\pinrun-live-*.jsonl, only what was written since the last scan (a
                remembered byte offset; a half-written last line waits for the next scan). The FIRST scan reads the last
                4 MB only to learn where pin is (its last market list, entries blocked now, recent refusals): nothing in
                it is said one by one (the baseline note counts it). Then, from the records the 0925v pin build writes
                when something is wrong (PIN_ALARM_KINDS): URGENT api_shape, hedge_fail, clock_skew, dayloss_write_fail,
                unbooked (provisional or gave_up), universe_empty (fallback), startup_bank (source none), expiry_exit
                (flat false: the run ended still holding); said quietly: universe_empty recovered, unbooked booked,
                startup_bank from the api after a retry or from the mirror, log_write_fail of the trajectory file;
                never said: expiry_drain (the run's ordinary end, 20 minutes before every planned restart) and
                expiry_exit flat; only written in the watch's log (v-kwfalse 11-13, shape_harmless): two api_shape
                shapes pin writes at a start, an empty book's snapshot (keys 'clock' only) and a /markets floor_strike
                missing under 90 s into the quarter-hour its market opened (Kalshi fills it 20-60 s in). An api_shape
                head names its endpoint and field (a /portfolio/balance shape reads apart from a /markets one).
                A BLOCK (pin's entries_blocked / hedge_broken / clock_skew / log_write_fail /
                dayloss_write_fail records with a reason; entries_resumed ends it; a new pin run starts with none) still
                in force at the scan is an URGENT open condition until pin resumes; one that began and ended between two
                scans is a quiet note. A record more than 2 hours old when read (the watch was off or down) is said
                quietly. More than 5 hedge orders refused in the hour before the scan (URGENT): a hedge or hedge_extra
                record with a 4xx status_code (pin writes it on every live hedge since 0925t, 11-04), or, in a log from
                before that, a live hedge with no order id and nothing filled (the 10-31..11-04 off-grid hedges: 115
                such records in the 10-31 log, up to 30 in one hour). No "universe" record with got > 0 for 10 minutes
                (pin sees no markets: URGENT), counted from the newest of the last market list, the start of pin's log
                and the last scan that saw results\pinrun-live.stop; except Thursday 3-5 AM ET (Kalshi's weekly
                maintenance; a silence that began with it counts from 5 AM) and while pinrun-live.stop stands pin down.
  disk          free space on C: (under 15 GB an alert, under 8 GB URGENT; cleared 1 GB above the line).
  packages      the server's Python packages against results\requirements-server.txt ("name==version" or "name
                version" a line; a missing file means nothing to compare, said in /watch).
  launchers     each file in results\live_launcher_snapshot\SHA256SUMS.txt ("<sha256>  <name>", sha256sum's format)
                against the sha256 of the LIVE file it is a snapshot of: results\live_launcher_snapshot\LIVE_PATHS.txt
                maps each snapshot name to that live path ("<name>  <path>" a line; restart_bot_repo.ps1 ->
                C:\kals-repo\restart_bot.ps1, restart_bot_hand.ps1 -> C:\kals-live-0925n\restart_bot.ps1: both are
                named restart_bot.ps1, so a name alone cannot say which). A name the map does not list is a
                condition of its own (it is never compared with a wrong file); with no map at all, a relative name
                is under the repo, or under a "# root: <dir>" line. A missing SHA256SUMS.txt means nothing to compare.
                (Until 11-08 the names were looked up under the repo: C:\kals-repo\restart_bot_hand.ps1 does not
                exist, so the first scan would have opened two false "missing" alarms and never hashed a live file.)

BASELINE AND ALERTS. The first scan records each check's baseline and sends ONE "baseline set" note (a check that could
not read then records its baseline at its first good read, silently); a condition already open then is listed in that
note, not sent on its own, and the note rings when one of them is urgent. Every later scan compares with the baseline; a
change is said once and the baseline takes the new value. A condition (disk low, a package off the list, a launcher
drift, pin seeing no markets, pin's entries blocked, refused hedges, a refused key, Kalshi paused, a check failing) is
OPEN: said when it starts, listed by the phone's /watch while it lasts, and a quiet "cleared" note when it ends. One that
opens FLAP_MAX times in a day says so on the last of them and is then only on /watch (opening and clearing silently)
until a day has passed. A check that fails 3 scans in a row says so once. Messages go through pinrules_watch.Phone (the
same Telegram path; URGENT rings even in the quiet hours, the rest is silent then). Each urgent alert is its own message
(more than MAX_URGENT_EACH in one scan: one message); the other alerts of a scan go as one message. A message Telegram
did not take stays queued in the state file and goes at the next scan; nothing is said twice (every alert has an id, kept
in the state file). The state is saved BEFORE the messages go (the scan's baselines survive a failed send) and again
after (retried SAVE_TRIES times: the phone's /watch may have the file open for a moment). A scan that crashes says so on
the phone once an ET day (results\kalshi_watch.crash holds the day).

OFF SWITCH. results\kalshi_watch.stop (the phone's "/watch off", asked and confirmed; "/watch on" removes it): every
scheduled run exits at once, scans nothing and sends nothing; /watch says OFF. Nothing else changes.

STATE results\kalshi_watch_state.json (the phone's /watch reads it): the last scan, each check's label, status, detail
and failure streak, the open conditions, the alerts waiting to be sent, the last alerts sent, the last 5 changelog
entries, and each check's baseline. Log: results\kalshi_watch.log.

  python research\kalshi_watch.py              one scan (what the scheduled task runs)
  python research\kalshi_watch.py --once       the same
  python research\kalshi_watch.py --dry-run    one scan; the messages are printed, not sent; the state is not saved
  python research\kalshi_watch.py --self-test [--log PATH ...]  every check on fixtures and fakes: no network, no key,
                                               no Telegram; with --log, pin's real logs replayed through the pin-log check
                                               in 30-minute scans (the 10-31 log must raise the refused-hedge alarm)
  python research\kalshi_watch.py --test-send  one message to the phone, labelled as a test
Every scan runs the self-test first (quietly) and scans nothing when it fails (said once on the phone).
"""
import calendar
import contextlib
import email.utils
import glob
import hashlib
import html as _html
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from botdata import clock  # noqa: E402
from kalshiwatch import UA as BROWSER_UA  # noqa: E402  (assets.kalshi.com refused a request without a browser's)
from kalshiwatch import norm_rules  # noqa: E402

REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
STATE_NAME = "kalshi_watch_state.json"
STOP_NAME = "kalshi_watch.stop"                     # the phone's /watch off: every run exits at once
CRASH_NAME = "kalshi_watch.crash"                   # the ET day a crash was last said on the phone
LOG_NAME = "kalshi_watch.log"
REQS_NAME = "requirements-server.txt"
SUMS_REL = os.path.join("live_launcher_snapshot", "SHA256SUMS.txt")
LIVE_REL = os.path.join("live_launcher_snapshot", "LIVE_PATHS.txt")     # snapshot name -> the live file it copies
PIN_STOP_NAME = "pinrun-live.stop"
INSTALL_PS1 = os.path.join(RESULTS, "kalshi_watch_install.ps1")
TASK = "KalsKalshiWatch"
EVERY_MIN = 30

SERIES = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBNB15M", "KXZEC15M", "KXNEAR15M",
          "KXHYPE15M", "KXBTCD")
MAX_CALLS = 20
CALL_GAP_S = 1.0
FIXED_CALLS = 4                                     # status, fee changes, schedule, balance
SERIES_PER_SCAN = MAX_CALLS - FIXED_CALLS - len(SERIES)       # 6 series answers a scan: each series every 2nd scan
MARKETS_LIMIT = 5
NET_ABORT = 3

CHANGELOG_URLS = ("https://docs.kalshi.com/changelog/rss.xml", "https://docs.kalshi.com/changelog.md",
                  "https://docs.kalshi.com/changelog")
CONTRACT_PDF = "https://assets.kalshi.com/contract_terms/CRYPTO15M.pdf"
CFB_PDF = "https://docs.cfbenchmarks.com/CF%20Constituent%20Exchanges.pdf"
CFB_STATUS = "https://status.cfbenchmarks.com/"
CFB_STATUS_URLS = (CFB_STATUS + "api/v2/incidents.json", CFB_STATUS + "history.rss", CFB_STATUS + "history.atom")
API_HOSTS = ("api.elections.kalshi.com", "trading-api.kalshi.com", "api.kalshi.com", "demo-api.kalshi.co",
             "external-api.kalshi.com")
FETCH_TIMEOUT_S = 20
FETCH_CAP = 25 * 2 ** 20

URGENT_WORDS = ("remove", "deprecat", "breaking", "rename", "crypto", "15M", "fee", "order", "orderbook", "balance",
                "exchange_index", "shard", "rate limit", "websocket", "settlement", "price_level", "tick", "subaccount",
                "api key")
CHANGELOG_EACH = 6
MAX_URGENT_EACH = 6
CL_FP_LEN = 100                                     # the first 100 letters/digits of an entry's text: its fingerprint
CL_PIN_EXCHANGE = "Predictions"                     # the exchange pin trades (RSS category)
CL_PIN_SURFACES = ("REST", "WebSocket")             # ...and how it talks to it (FIX: never)
CL_KEEP = 3000

# the kinds the 0925v pin build writes when something is wrong (pinrun.py v-0925v: hedgefail, apishape, universe,
# unbooked, startbank, clockskew, logfail, expiry); pin_judge says which are urgent, which quiet, which never said
PIN_ALARM_KINDS = ("api_shape", "hedge_fail", "hedge_broken", "universe_empty", "clock_skew", "unbooked",
                   "log_write_fail", "dayloss_write_fail", "expiry_drain", "expiry_exit", "startup_bank",
                   "entries_blocked")
PIN_ALARM_WORDS = {   # "Pin <words>"
    "api_shape": "got a Kalshi answer without the shape it reads",
    "hedge_fail": "had a hedge order fail",
    "hedge_broken": "could not hedge a position",
    "universe_empty": "got an empty market list from Kalshi and asked for the markets another way (GET /events)",
    "clock_skew": "sees the server's clock off from Kalshi's",
    "unbooked": "has a bet it has not booked 15 minutes after its close (counted as a loss until it books)",
    "log_write_fail": "could not write its own log",
    "dayloss_write_fail": "could not write its day-loss file (the day's loss stop)",
    "startup_bank": "could not read its bank at startup (no new bets until it can)",
    "entries_blocked": "stopped opening new bets",
    "expiry_exit": "ended its run still holding a bet (its next run does not know it)",
}
# pin's entry blocks (pinrun _eb_set: a record with a `reason`; entries_resumed with the same reason ends it). Not
# expiry_drain: the last 20 minutes of every run, the ordinary end
BLOCK_KINDS = ("entries_blocked", "hedge_broken", "clock_skew", "log_write_fail", "dayloss_write_fail", "expiry_drain")
BLOCK_IGNORE = ("expiry_drain",)
BLOCK_WORDS = {
    "hedge_broken": "its hedge orders keep failing (3 in a row), so it opens nothing that would need one",
    "clock_skew": "the server's clock is off from Kalshi's",
    "log_write": "it cannot write its own log",
    "dayloss_write": "it cannot write its day-loss file",
    "unbooked": "a bet it has not booked could reach its loss stop",
    "startup_bank": "it has not read its bank since it started",
    "guard_error": "one of its own safety checks broke",
}
HEDGE_KINDS = ("hedge", "hedge_extra")
HEDGE_4XX_MAX = 5
HEDGE_WINDOW_S = 3600
UNIVERSE_SILENT_S = 600
PIN_STALE_S = 2 * 3600                              # a record older than this when read is said quietly
TAIL_FIRST = 4 * 2 ** 20
READ_CAP = 32 * 2 ** 20
READ_KEEP = 8 * 2 ** 20

DISK_WARN_GB = 15.0
DISK_URGENT_GB = 8.0
DISK_HYST_GB = 1.0
FAIL_STREAK = 3
FLAP_MAX = 3                                        # opens of one condition in FLAP_WINDOW_S before it goes quiet
FLAP_WINDOW_S = 86400
SAVE_TRIES = 5
OUTBOX_MAX_AGE_S = 2 * 86400
KEEP_SENT = 3000
KEEP_HISTORY = 40

SERIES_URGENT = ("fee_type", "fee_multiplier", "settlement_sources", "contract_url", "contract_terms_url")
MARKET_URGENT = ("price_level_structure", "price_ranges", "settlement_timer_seconds", "exchange_index")
MEANING = {
    "fee_type": "the fee formula: what every trade costs",
    "fee_multiplier": "the fee multiplier: what every trade costs",
    "settlement_sources": "where the settlement price comes from",
    "contract_url": "the link to the contract's rules",
    "contract_terms_url": "the link to the contract terms document",
    "frequency": "how often a new market opens",
    "price_level_structure": "the price steps: which prices pin may bid",
    "price_ranges": "the price steps: which prices pin may bid",
    "settlement_timer_seconds": "how long after the close the result is fixed",
    "exchange_index": "which exchange shard orders go to (pin sends it on every order)",
}

CHECKS = (   # (id, label for the phone)
    ("changelog", "Kalshi API changelog"),
    ("kalshi_api", "Kalshi's answers (signed reads)"),
    ("contract_pdf", "15-minute crypto contract terms (PDF)"),
    ("cfb_pdf", "CF Benchmarks index exchanges (PDF)"),
    ("cfb_status", "CF Benchmarks status page"),
    ("pin_log", "pin's live log"),
    ("disk", "server disk (C: drive)"),
    ("packages", "Python packages vs the pinned list"),
    ("launchers", "live launchers vs their snapshot"),
)


class Refused(Exception):
    """web_fetch was asked for Kalshi's trading API: every API read goes through kauth, signed."""


# ---------------------------------------------------------------------------- small helpers
def iso(now):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))


def et(epoch, with_day=True):
    return clock.et_clock(epoch, with_day=with_day) if epoch is not None else "?"


def sha256(b):
    if isinstance(b, str):
        b = b.encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def canon(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), default=str)


def show(v, cap=160):
    s = v if isinstance(v, str) else canon(v)
    return s if len(s) <= cap else s[:cap - 3] + "..."


def series_words(s):
    if s == "KXBTCD":
        return "the BTC hourly ladder (KXBTCD)"
    m = re.match(r"^KX([A-Z0-9]+?)15M$", s or "")
    return ("%s 15-minute (%s)" % (m.group(1), s)) if m else str(s)


def mins(s):
    """A span in words: '16 minutes', '5 hours', '41 days'."""
    m = int(round(float(s) / 60.0))
    if m < 120:
        return "%d minute%s" % (m, "" if m == 1 else "s")
    if m < 48 * 60:
        return "%d hours" % (m // 60)
    return "%d days" % (m // 1440)


def span_words(s):
    """'75 seconds' under a minute and a half, else mins()."""
    return "%d seconds" % int(round(s)) if s < 90 else mins(s)


def plural(n, word):
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def entries_words(n):
    return "%d entr%s" % (n, "y" if n == 1 else "ies")


def market_words(ticker, close_s=None):
    """'ZEC 4:15 PM market' (pinrules_watch.market_label); without a close time 'ZEC market'."""
    try:
        import pinrules_watch as _rw
        if close_s:
            return _rw.market_label(ticker, close_s)
        return "%s market" % _rw.coin_label(ticker)
    except Exception:                                           # noqa: BLE001
        return str(ticker)


def http_date_et(s):
    """An HTTP date ('Fri, 06 Nov 2026 10:00:00 GMT') in ET words, or None."""
    t = email.utils.parsedate_tz(s or "")
    return et(email.utils.mktime_tz(t)) if t else None


def _urgent_res():
    out = []
    for w in URGENT_WORDS:
        lw = w.lower()
        if lw == "tick":
            pat = r"(?<![a-z])tick(?!er)"          # tick_size, price ticks; not ticker, not candlesticks
        elif lw == "fee":
            pat = r"(?<![a-z])fee(?!d)"            # fees, fee_type; not feed
        elif lw == "order":
            pat = r"(?<![a-z])order"               # orders, order_id, orderbook; not border, not recorder
        elif lw == "15m":
            pat = r"(?<![0-9])15m(?![b0-9])"       # KXBTC15M, 15m; not 215MB, not 15MB
        elif lw == "remove":
            pat = r"(?<![a-z])remov(e|al|ing)"     # removed, removes, removal, removing
        else:
            pat = "[ _-]?".join(re.escape(x) for x in re.split(r"[ _]", lw))
        out.append((w, re.compile(pat, re.I)))
    return out


_URGENT_RES = _urgent_res()


def urgent_hits(text):
    """The URGENT_WORDS the text names (in URGENT_WORDS order)."""
    return [w for w, rx in _URGENT_RES if rx.search(text or "")]


def maint_window(now):
    """(start, end) epochs of Kalshi's weekly maintenance stretch, Thursday 3:00-5:00 AM ET, of the ET week holding
    `now` (the most recent Thursday on or before today, Eastern). No tz database: botdata.clock's DST rule."""
    tm = time.gmtime(now + clock._et_off(now))
    back = (tm.tm_wday - 3) % 7
    day = clock.shift_day(clock.et_day(now), -back)
    s = clock.day_start(day) + 3 * 3600
    return s, s + 2 * 3600


def in_maint(now):
    a, b = maint_window(now)
    return a <= now < b


# ---------------------------------------------------------------------------- fetching
def web_fetch(url, timeout=FETCH_TIMEOUT_S, cap=FETCH_CAP):
    """(status, bytes, headers). GET only; a failure is a status (-1 = no answer), never a raise. Kalshi's trading API is
    refused here (Refused): an unsigned call from the server spends the public budget the FX taker lives on."""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    if host in API_HOSTS or "/trade-api/" in url:
        raise Refused("%s is Kalshi's trading API: it is read only through kauth (signed)" % host)
    try:
        req = urllib.request.Request(url, headers=dict(BROWSER_UA), method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(cap + 1)
            return r.status, body[:cap], {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, b"", {}
    except Exception as e:                                      # noqa: BLE001
        return -1, ("%s: %s" % (type(e).__name__, str(e)[:160])).encode("utf-8", "replace"), {}


def kauth_get(path, params=None):
    """A SIGNED GET with pin's key through research\\kauth.py (imported here, lazily: the import loads the key file
    C:\\kals\\kalshi.pem; the self-test never comes here)."""
    import kauth
    return kauth.get(path, params, auth=True)


def pkg_version(name):
    try:
        from importlib import metadata
        return metadata.version(name)
    except Exception:                                           # noqa: BLE001
        return None


def disk_free_bytes():
    return shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\").free


class Env:
    """What a scan touches. The real one by default; the self-test plants every piece."""

    def __init__(self, results=RESULTS, repo=REPO, get=None, fetch=None, sleep=time.sleep, mono=time.monotonic,
                 disk_free=None, version_of=None, log_path=None, remap=None):
        self.results, self.repo = results, repo
        self.remap = remap or (lambda p: p)         # a live launcher's path -> where to read it (tests: a temp copy)
        self.get = get or kauth_get
        self.fetch = fetch or web_fetch
        self.sleep, self.mono = sleep, mono
        self.disk_free = disk_free or disk_free_bytes
        self.version_of = version_of or pkg_version
        self.log_path = log_path if log_path is not None else os.path.join(results, LOG_NAME)
        self.lines = []

    def path(self, *parts):
        return os.path.join(self.results, *parts)

    def log(self, msg):
        line = "%s %s" % (iso(time.time()), msg)
        self.lines.append(line)
        print(line)
        if self.log_path:
            try:
                with open(self.log_path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError:
                pass


class Signed:
    """The scan's Kalshi reads: at most MAX_CALLS, at least CALL_GAP_S apart (start to start), every one through env.get
    (kauth.get with auth=True). After NET_ABORT network failures in a row the rest of the scan's reads are skipped."""

    def __init__(self, env):
        self.env = env
        self.calls = []                 # (path, status, monotonic start)
        self.last = None
        self.net = 0

    def __call__(self, path, params=None):
        if len(self.calls) >= MAX_CALLS or self.net >= NET_ABORT:
            return None, None
        if self.last is not None:
            wait = CALL_GAP_S - (self.env.mono() - self.last)
            if wait > 0:
                self.env.sleep(wait)
        self.last = self.env.mono()
        try:
            st, body = self.env.get(path, params)
        except Exception as e:                                  # noqa: BLE001
            st, body = -1, "%s: %s" % (type(e).__name__, str(e)[:160])
        self.calls.append((path, st, self.last))
        self.net = self.net + 1 if st == -1 else 0
        return st, body


# ---------------------------------------------------------------------------- a check's answer
class Result:
    def __init__(self):
        self.status = "ok"              # ok | failed
        self.detail = ""                # one line for /watch
        self.summary = ""               # one line for the baseline note
        self.alerts = []                # one-shot: [{id, head, body, urgent}]
        self.opens = {}                 # conditions open now: {id: {head, body, urgent}}
        self.keep = ()                  # id prefixes of earlier open conditions not judged this scan (carried over)
        self.extra = {}

    def alert(self, aid, head, body, urgent=False):
        self.alerts.append({"id": aid, "head": head, "body": body, "urgent": bool(urgent)})

    def open(self, oid, head, body, urgent=False):
        self.opens[oid] = {"head": head, "body": body, "urgent": bool(urgent)}

    def fail(self, why):
        self.status = "failed"
        self.detail = why
        return self


# ---------------------------------------------------------------------------- 1. the changelog
def _text(s):
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s or "", flags=re.S)
    s = _html.unescape(s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tag(block, name):
    m = re.search(r"<%s\b[^>]*>(.*?)</%s>" % (re.escape(name), re.escape(name)), block, re.S | re.I)
    return m.group(1) if m else ""


def date_iso(s):
    """'November 5, 2026' / 'Nov 5, 2026' / '2026-11-05...' / an RSS date -> '2026-11-05' (an RSS date in UTC);
    anything else as written."""
    s = _text(s)
    if not s:
        return ""
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return time.strftime("%Y-%m-%d", time.strptime(s.replace("Sept ", "Sep "), fmt))
        except ValueError:
            pass
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    t = email.utils.parsedate_tz(s)
    if t:
        return time.strftime("%Y-%m-%d", time.gmtime(email.utils.mktime_tz(t)))
    return s[:40]


def fingerprint(text):
    """An entry's identity whichever source it came from: the first CL_FP_LEN letters and digits of its text, lower
    case (the RSS's HTML and changelog.md's markdown of the same paragraph give the same string)."""
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text or "")          # a markdown link: its words
    t = _html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()[:CL_FP_LEN]


def cl_relevant(cats):
    """False when the RSS tags an entry only for what pin never uses: another exchange (Margin: perps, equities) or
    only FIX. No tags (changelog.md): True."""
    cats = set(cats or [])
    if not cats:
        return True
    return CL_PIN_EXCHANGE in cats and bool(cats & set(CL_PIN_SURFACES))


def _entry(date, title, text, link="", key=None, posted="", cats=(), fp_text=None):
    title = (title or "").strip() or (text or "")[:80]
    hits = urgent_hits(title + " " + (text or "") + " " + (fp_text or ""))
    rel = cl_relevant(cats)
    return {"key": key or "t|%s" % re.sub(r"[^a-z0-9]+", " ", title.lower()).strip(), "date": date, "title": title[:200],
            "text": (text or "")[:1500], "link": link or "", "posted": posted or "", "cats": list(cats),
            "fp": fingerprint(fp_text if fp_text is not None else text), "hits": hits, "relevant": rel,
            "urgent": bool(hits) and rel}


def anchor_date(link):
    """'#november-12-2026' -> '2026-11-12'; '#tbd' -> 'TBD'; else None (the changelog's RSS links to its day)."""
    m = re.search(r"#([a-z]+)-(\d{1,2})-(\d{4})\b", link or "", re.I)
    if m:
        d = date_iso("%s %s, %s" % (m.group(1).capitalize(), m.group(2), m.group(3)))
        return d if re.match(r"^\d{4}-\d{2}-\d{2}$", d) else None
    return "TBD" if re.search(r"#tbd\b", link or "", re.I) else None


def parse_rss(text):
    """RSS items or Atom entries. An entry's date is the day its link's anchor names (when it takes effect), else its
    pubDate; `posted` is the pubDate. Its key is its guid (else its title); its fingerprint comes from its full text."""
    out = []
    items = re.findall(r"<item\b[^>]*>(.*?)</item>", text, re.S | re.I)
    atom = False
    if not items:
        items = re.findall(r"<entry\b[^>]*>(.*?)</entry>", text, re.S | re.I)
        atom = True
    for it in items:
        title = _text(_tag(it, "title"))
        posted = date_iso(_tag(it, "pubDate") or _tag(it, "published") or _tag(it, "updated") or _tag(it, "dc:date"))
        full = _text(_tag(it, "content:encoded") or _tag(it, "content"))
        summ = _text(_tag(it, "description") or _tag(it, "summary"))
        link = _text(_tag(it, "link")) if not atom else ""
        if not link:
            m = re.search(r"<link\b[^>]*href=\"([^\"]+)\"", it)
            link = m.group(1) if m else ""
        guid = _text(_tag(it, "guid") or _tag(it, "id"))
        cats = [_text(c) for c in re.findall(r"<category\b[^>]*>(.*?)</category>", it, re.S | re.I)]
        cats += re.findall(r"<category\b[^>]*\bterm=\"([^\"]+)\"", it)
        out.append(_entry(anchor_date(link) or posted, title, summ or full, link, key=("g|" + guid) if guid else None,
                          posted=posted, cats=[c for c in cats if c], fp_text=full or summ))
    return out


_MD_DATE = re.compile(r"^\*\*([A-Z][a-z]{2,8}\.? \d{1,2},? \d{4}|TBD)\*\*[ \t]*$", re.M)


def parse_md(text):
    """changelog.md: since autumn 2026 each entry is a "**November 12, 2026**" (or "**TBD**") line and the text after it
    (no title: the entry's first sentence stands for it); before that, Mintlify <Update label="..." ... rss={{ title:
    "...", description: "..." }}> body </Update> blocks (both are read)."""
    out = []
    for blk in re.findall(r"<Update\b(.*?)</Update>", text, re.S):
        lab = re.search(r'label="([^"]*)"', blk)
        title = re.search(r'title:\s*"((?:[^"\\]|\\.)*)"', blk) or re.search(r'description="([^"]*)"', blk)
        t = title.group(1) if title else ""
        if not t:
            h = re.search(r"^\s*#+\s*(.+)$", blk, re.M)
            t = h.group(1) if h else ""
        body = re.sub(r'label="[^"]*"', " ", blk)
        out.append(_entry(date_iso(lab.group(1) if lab else ""), t, _text(body)))
    if out:
        return out
    marks = list(_MD_DATE.finditer(text))
    for i, m in enumerate(marks):
        body = text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        words = re.sub(r"\s+", " ", re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", body).replace("`", "")).strip()
        if not words:
            continue
        first = re.split(r"(?<=[.:])\s", words, maxsplit=1)[0]
        title = first if len(first) <= 120 else first[:117].rstrip() + "..."
        date = "TBD" if m.group(1) == "TBD" else date_iso(m.group(1))
        fp = fingerprint(body)
        out.append(_entry(date, title, words, key="md|%s|%s" % (date, fp[:60]), fp_text=body))
    return out


def fetch_changelog(env):
    """(entries, source url, None) or (None, None, why). RSS first, then the markdown page, then the page (its RSS
    link, or <Update> blocks in it)."""
    whys = []
    for url in CHANGELOG_URLS:
        st, body, _hd = env.fetch(url)
        if st != 200 or not body:
            whys.append("%s answered %s" % (url.rsplit("/", 1)[-1] or url, st))
            continue
        txt = body.decode("utf-8", "replace")
        if url.endswith(".xml"):
            es = parse_rss(txt)
        elif url.endswith(".md"):
            es = parse_md(txt)
        else:
            m = re.search(r"<link\b[^>]*application/rss\+xml[^>]*>", txt, re.I)
            href = re.search(r'href="([^"]+)"', m.group(0)) if m else None
            es = []
            if href:
                rss = urllib.parse.urljoin(url, _html.unescape(href.group(1)))
                if rss not in CHANGELOG_URLS:
                    st2, b2, _h = env.fetch(rss)
                    if st2 == 200 and b2:
                        es = parse_rss(b2.decode("utf-8", "replace"))
            if not es:
                es = parse_md(txt) or parse_rss(txt)
        es = [e for e in es if e["title"]]
        if es:
            return es, url, None
        whys.append("%s had no entries I could read" % (url.rsplit("/", 1)[-1] or url))
    return None, None, "; ".join(whys)


def when_words(date, now):
    """'Nov 9, 2026 (in 2 days)' for an entry date 'YYYY-MM-DD'; 'TBD' -> 'a day not set yet (TBD)'."""
    if date == "TBD":
        return "a day not set yet (TBD)"
    try:
        tm = time.strptime(date, "%Y-%m-%d")
    except (TypeError, ValueError):
        return str(date)
    lab = "%s %d, %d" % (time.strftime("%b", tm), tm.tm_mday, tm.tm_year)
    try:
        d = clock.days_between(clock.et_day(now), date) - 1
    except ValueError:
        return lab
    return lab + (" (today)" if d == 0 else (" (in %s)" % plural(d, "day") if d > 0 else ""))


_ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _cl_order(e):
    """Newest first: by the day it was posted when the source says (the RSS), else by its date ('TBD' last)."""
    d = e.get("posted") or e.get("date") or ""
    return d if _ISO_DAY.match(d) else ""


def _cl_when(e, now, lead=True):
    """'It takes effect Nov 12, 2026 (in 5 days); posted Nov 6, 2026' (the date the alert carries); lead False:
    'takes effect ...' / 'is dated ...' / 'its day is not set yet (TBD)'."""
    if e["date"] == "TBD":
        out = "its day is not set yet (TBD)"
    elif e.get("posted") and e["posted"] != e["date"] and _ISO_DAY.match(e["date"]):
        out = "takes effect %s" % when_words(e["date"], now)
    else:
        out = "is dated %s" % when_words(e["date"], now)
    if e.get("posted") and e["posted"] != e["date"]:
        out += "; posted %s" % when_words(e["posted"], now).split(" (")[0]
    if lead:
        out = ("I" + out[1:]) if out.startswith("its") else "It " + out
    return out


def _cl_why(e):
    if e["urgent"]:
        return " Urgent because it mentions: %s." % ", ".join(e["hits"])
    if e["hits"] and not e["relevant"]:
        return (" It mentions %s, but Kalshi tags it %s only: pin trades the Predictions exchange over REST and "
                "WebSocket, so it does not reach pin." % (", ".join(e["hits"]), "/".join(e["cats"])))
    return ""


def check_changelog(env, base, now):
    r = Result()
    es, src, why = fetch_changelog(env)
    if es is None:
        return r.fail("could not read the changelog: %s" % why)
    keys = {e["key"] for e in es}
    fps = {e["fp"] for e in es if e["fp"]}
    newest = sorted(es, key=_cl_order, reverse=True)
    r.extra["changelog_recent"] = [{"date": e["date"], "title": e["title"], "hits": e["hits"] if e["urgent"] else [],
                                    "posted": e.get("posted") or ""} for e in newest[:5]]
    r.detail = "%s; the newest %s (read from %s)" % (entries_words(len(es)), _cl_when(newest[0], now, lead=False),
                                                       src.rsplit("/", 1)[-1])
    seen = set(base.get("seen") or [])
    seen_fp = set(base.get("fps") or [])
    old_src, last_t = base.get("source"), base.get("t")
    base["source"], base["t"] = src, now
    days = [e["date"] for e in es if _ISO_DAY.match(e["date"])]
    top = base.get("newest")
    base["newest"] = max([top] + days if top else days) if (top or days) else None
    dates = base.setdefault("dates", {})
    if not seen and not seen_fp:
        base["seen"], base["fps"] = sorted(keys)[-CL_KEEP:], sorted(fps)[-CL_KEEP:]
        dates.update({e["key"]: e["date"] for e in es if not e["key"].startswith("md|")})
        r.summary = "%s recorded; the newest, \"%s\", %s" % (entries_words(len(es)), newest[0]["title"],
                                                             _cl_when(newest[0], now, lead=False))
        return r
    new = [e for e in newest if e["key"] not in seen and not (e["fp"] and e["fp"] in seen_fp)]
    moved = [(e, dates[e["key"]]) for e in es if e["key"] in seen and dates.get(e["key"])
             and dates[e["key"]] != e["date"]]
    base["seen"] = sorted(seen | keys)[-CL_KEEP:]
    base["fps"] = sorted(seen_fp | fps)[-CL_KEEP:]
    for e in es:
        if not e["key"].startswith("md|"):
            dates[e["key"]] = e["date"]
    if len(dates) > CL_KEEP:
        base["dates"] = dict(sorted(dates.items())[-CL_KEEP:])
    # a source switch (the RSS, which lists only its 15 newest, then changelog.md, which holds a year of entries the
    # RSS never listed, TBD ones among them; or back): only an entry dated after everything seen, or posted since the
    # last scan, is news; the rest join the baseline silently
    if old_src and old_src != src:
        since = time.strftime("%Y-%m-%d", time.gmtime(float(last_t))) if last_t else None
        new = [e for e in new if (top and _ISO_DAY.match(e["date"]) and e["date"] > top)
               or (since and _ISO_DAY.match(e.get("posted") or "") and e["posted"] >= since)]
    for e, was in moved:
        r.alert("cl|moved|%s|%s" % (e["key"], e["date"]), "Kalshi changelog: new day for %s" % e["title"],
                "Kalshi moved the day of its API changelog entry \"%s\": was %s, now %s.%s%s" % (
                    e["title"], when_words(was, now), when_words(e["date"], now), _cl_why(e),
                    ("\nRead it: %s" % e["link"]) if e["link"] else ""), e["urgent"])
    if not new:
        return r
    if len(new) > CHANGELOG_EACH:
        urg = [e for e in new if e["urgent"]]
        lines = ["Kalshi's API changelog shows %d entries I had not seen (newest first):" % len(new)]
        for e in new[:12]:
            lines.append("- %s: %s%s" % (when_words(e["date"], now), e["title"],
                                         (" (mentions %s)" % ", ".join(e["hits"])) if e["urgent"] else ""))
        if len(new) > 12:
            lines.append("- and %d more" % (len(new) - 12))
        lines.append("So many at once can also mean Kalshi changed the page's format. %d of them mention an urgent "
                     "word. /watch lists the newest." % len(urg))
        r.alert("cl|many|%s" % sha256("".join(sorted(e["key"] for e in new)))[:16],
                "Kalshi changelog: %d new entries" % len(new), "\n".join(lines), bool(urg))
        return r
    for e in reversed(new):                     # oldest first, so the phone reads them in order
        body = "Kalshi posted a new API changelog entry: \"%s\". %s.%s" % (e["title"], _cl_when(e, now), _cl_why(e))
        if e["text"] and e["text"] != e["title"]:
            body += "\nWhat it says: %s" % show(e["text"], 400)
        if e["link"]:
            body += "\nRead it: %s" % e["link"]
        r.alert("cl|%s" % e["key"], "Kalshi changelog: %s" % e["title"], body, e["urgent"])
    return r


# ---------------------------------------------------------------------------- 2. Kalshi's answers, signed
def key_paths(obj, pre="", depth=0, out=None):
    """Every key path of a JSON answer ('series.fee_type', 'markets[].ticker'); list elements share one '[]' path."""
    out = set() if out is None else out
    if depth > 6:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = ("%s.%s" % (pre, k)) if pre else str(k)
            out.add(p)
            key_paths(v, p, depth + 1, out)
    elif isinstance(obj, list):
        for x in obj[:20]:
            key_paths(x, pre + "[]", depth + 1, out)
    return out


def _segments(p):
    return len(p.split("."))


def topmost(paths):
    out = []
    for p in sorted(paths, key=lambda x: (len(x), x)):
        if not any(p.startswith(q + ".") or p.startswith(q + "[]") for q in out):
            out.append(p)
    return out


def _under_empty_list(p, keys):
    """True when path p sits under a list that has no element keys in `keys` (an empty list: nothing to judge)."""
    i = p.find("[]")
    while i >= 0:
        q = p[:i]
        if q in keys and not any(k.startswith(q + "[]") for k in keys):
            return True
        i = p.find("[]", i + 2)
    return False


def compare_keys(store, keys_now, ep, r, rid, nested=True, why_missing="", at_once=2):
    """New keys (an alert) and missing keys (URGENT: at once for keys at most `at_once` deep, after 2 scans in a row
    deeper) against store['keys']. nested False: only keys 1 deep are judged. A list that is empty now leaves its
    children unjudged, and children first seen under a list that was empty at the baseline join it silently (an empty
    list of maintenance windows that gains one is not a new field). A key that was said gone and came back is 'flaky'
    (Kalshi leaves it out of some answers): it is never said gone again."""
    keys_now = set(keys_now)
    old = set(store.get("keys") or [])
    if not old:
        store["keys"] = store["base_keys"] = sorted(keys_now)
        return
    base_keys = set(store.get("base_keys") or old)
    if not nested:
        keys_now |= {k for k in old if _segments(k) > 1}
    flaky = set(store.get("flaky") or [])
    said_gone = set(store.get("said_gone") or [])
    added = topmost(k for k in keys_now - old if not _under_empty_list(k, old))
    back = [k for k in added if k in said_gone]
    if back:
        flaky |= set(back)
        said_gone -= set(back)
    gone_all = {k for k in old - keys_now if not _under_empty_list(k, keys_now)
                and not any(k == f or k.startswith(f + ".") or k.startswith(f + "[]") for f in flaky)}
    miss = store.setdefault("miss", {})
    for k in list(miss):
        if k not in gone_all:
            miss.pop(k, None)
    now_gone = []
    for p in topmost(gone_all):
        if _segments(p) <= at_once:
            now_gone.append(p)
        else:
            miss[p] = int(miss.get(p) or 0) + 1
            if miss[p] >= 2:
                now_gone.append(p)
    said_gone |= set(now_gone)
    store["flaky"], store["said_gone"] = sorted(flaky), sorted(said_gone)
    if added:
        r.alert("keys+|%s|%s" % (rid, sha256(canon(sorted(added)))[:12]),
                "Kalshi added %s to %s" % (plural(len(added), "field"), ep),
                "Kalshi's answer to %s has %s it did not have at the baseline: %s. Usually harmless; sometimes the "
                "first half of a rename." % (ep, plural(len(added), "new field"), ", ".join(added[:10])), False)
    if now_gone:
        orig = [p for p in now_gone if p in base_keys]          # there at the baseline: what pin was built against
        r.alert("keys-|%s|%s" % (rid, sha256(canon(sorted(now_gone)))[:12]),
                "Kalshi removed %s from %s" % (plural(len(now_gone), "field"), ep),
                "Kalshi's answer to %s no longer has %s: %s.%s %s" % (
                    ep, plural(len(now_gone), "field"), ", ".join(now_gone[:10]), why_missing,
                    ("If pin reads %s, pin may be trading blind or refusing trades: look for api_shape records in pin's "
                     "log (/watch)." % ("it" if len(now_gone) == 1 else "one of them")) if orig else
                    "None of them was there at the baseline (they came later), so pin was not built on them."),
                bool(orig))
        for p in now_gone:
            miss.pop(p, None)
    gone_drop = {g for g in gone_all if any(g == p or g.startswith(p + ".") or g.startswith(p + "[]")
                                            for p in now_gone)}
    store["keys"] = sorted((old - gone_drop) | keys_now)


# v-kwfalse (2026-11-13): 7 of the watch's 12 URGENT alarms in its first 4.7 days (the 11-13 read) were one sentence.
# Kalshi writes a 15-minute market's rules_primary two ways. Most read the opening-price wording ("If the simple average
# of the sixty seconds of CF Benchmarks' ETHUSDRTI before 12:00 AM EST on Nov 14, 2026 is at least the simple average of
# the sixty seconds of CF Benchmarks' ETHUSDRTI before 11:45 PM EST on November 13, 2026, then the market resolves to
# Yes."); some carry the strike as a number and spell the index with an underscore ("... CF Benchmarks' ETHUSD_RTI
# before 2:30 AM EST on Nov 12, 2026 is at least 2045.23, then the market resolves to Yes."; BTC says BRTI both ways).
# On 11-12 199 of 200 KXETH15M markets read the first, the 2:30 AM one the second. Same contract, same index, same
# second: the fixed-strike wording is hashed as the opening-price wording of the same index (its underscores dropped).
# The hashes on file stay valid (every series' baseline holds its opening-price hash: checked on the server's state of
# 11-13 for all 9 coins), so nothing new rings at the deploy. Any other text (another index, another average, another
# comparison, a sentence added) is not this template and still rings; the alarm shows the text as Kalshi wrote it.
# A whole-number strike ("is at least 2045, then") loses its comma in norm_rules (its number rule takes "2045," whole),
# so the comma after '#' is optional.
RULES_FIXED_STRIKE = re.compile(r"^If the simple average of the sixty seconds of CF Benchmarks' ([A-Za-z0-9_]+) before "
                                r"TIME TZ on DATE is at least #,? then the market resolves to Yes\.$")
RULES_OPEN_PRICE = ("If the simple average of the sixty seconds of CF Benchmarks' %s before TIME TZ on DATE is at "
                    "least the simple average of the sixty seconds of CF Benchmarks' %s before TIME TZ on DATE, then "
                    "the market resolves to Yes.")


def rules_key(t):
    """What a normalised rules text (norm_rules) is hashed as: the fixed-strike wording as the opening-price wording
    of the same index, underscores dropped (ETHUSD_RTI -> ETHUSDRTI; v-kwfalse); any other text as it is."""
    m = RULES_FIXED_STRIKE.match(t or "")
    if not m:
        return t
    idx = m.group(1).replace("_", "")
    return RULES_OPEN_PRICE % (idx, idx)


def market_vals(ms):
    """{field: sorted canonical values over the markets}, {rules sha256 (of rules_key): normalised text as written}."""
    vals = {}
    for m in ms:
        for f in MARKET_URGENT:
            v = m.get(f)
            vals.setdefault(f, set()).add(canon(v))
    rules = {}
    for m in ms:
        t = norm_rules(m.get("rules_primary"))
        if t:
            rules[sha256(rules_key(t))] = t[:400]
    return {f: sorted(v) for f, v in vals.items()}, rules


def _vals_words(vs):
    return " / ".join(show(json.loads(v), 80) for v in vs) if vs else "(none)"


def check_markets(store, s, body, r, now):
    ep = "GET /markets (%s open)" % s
    ms = [m for m in ((body or {}).get("markets") or []) if isinstance(m, dict)] if isinstance(body, dict) else []
    # a market's own fields are judged gone only after 2 scans in a row (each scan reads other markets; Kalshi may leave
    # an empty field out of one), the answer's top level at once
    compare_keys(store.setdefault("shape", {}), key_paths(body), ep, r, "markets|" + s, nested=bool(ms), at_once=1,
                 why_missing=(" It was missing on 2 scans in a row (each scan reads other open markets)." if ms else
                              " No market was open at the time, so only the answer's top level was read."))
    if not ms:
        return "no open market"
    vals, rules = market_vals(ms)
    old = store.setdefault("vals", {})
    for f, vs in vals.items():
        if f not in old:
            old[f] = vs
            continue
        if f == "exchange_index":
            fresh = [v for v in vs if v not in old[f]]
            if fresh:
                r.alert("mval|%s|%s|%s" % (s, f, sha256(canon(fresh))[:12]),
                        "Kalshi changed exchange_index on %s" % series_words(s),
                        "Kalshi changed exchange_index on %s: was %s, now %s. That is %s." % (
                            series_words(s), _vals_words(old[f]), _vals_words(vs), MEANING[f]), True)
                old[f] = sorted(set(old[f]) | set(vs))
            continue
        if vs != old[f]:
            r.alert("mval|%s|%s|%s" % (s, f, sha256(canon(vs))[:12]),
                    "Kalshi changed %s on %s" % (f, series_words(s)),
                    "Kalshi changed %s on %s: was %s, now %s. That is %s." % (
                        f, series_words(s), _vals_words(old[f]), _vals_words(vs), MEANING.get(f, f)), True)
            old[f] = vs
    known = store.setdefault("rules", [])
    if not known:
        store["rules"] = sorted(rules)[-40:]
    else:
        fresh = [h for h in rules if h not in known]
        for h in fresh[:2]:
            r.alert("rules|%s|%s" % (s, h[:16]), "New settlement rules sentence on %s" % series_words(s),
                    "The settlement rules text (rules_primary) of an open %s market has a sentence never seen before "
                    "(dates, times and numbers blanked): \"%s\". Read it before trusting the next trade." % (
                        series_words(s), show(rules[h], 400)), True)
        store["rules"] = (known + fresh)[-40:]
    return "%s open" % plural(len(ms), "market")


def check_series(store, s, body, r):
    ep = "GET /series/%s" % s
    se = (body or {}).get("series") if isinstance(body, dict) else None
    compare_keys(store.setdefault("shape", {}), key_paths(body), ep, r, "series|" + s)
    if not isinstance(se, dict):
        return
    vals = {f: canon(se.get(f)) for f in SERIES_URGENT + ("frequency",)}
    old = store.setdefault("vals", {})
    for f, v in vals.items():
        if f not in old:
            old[f] = v
            continue
        if v != old[f]:
            r.alert("sval|%s|%s|%s" % (s, f, sha256(v)[:12]), "Kalshi changed %s on %s" % (f, series_words(s)),
                    "Kalshi changed %s on %s: was %s, now %s. That is %s." % (
                        f, series_words(s), show(json.loads(old[f])), show(json.loads(v)), MEANING.get(f, f)),
                    f in SERIES_URGENT)
            old[f] = v


def _lists_of_dicts(body):
    out = []
    if isinstance(body, dict):
        for v in body.values():
            if isinstance(v, list):
                out.extend(x for x in v if isinstance(x, dict))
    elif isinstance(body, list):
        out.extend(x for x in body if isinstance(x, dict))
    return out


def _epoch_of(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) / (1000.0 if v > 1e11 else 1.0)
    return clock.utc_epoch(str(v))


def http_note(http, ep, st):
    h = http.setdefault(ep, {"last": None, "streak": 0})
    if st == 200:
        h.update(last=200, streak=0, ever200=True)
        return
    h["streak"] = (int(h.get("streak") or 0) + 1) if h.get("last") == st else 1
    h["last"] = st


def check_kalshi_api(env, base, now):
    r = Result()
    sg = Signed(env)
    http = base.setdefault("http", {})
    rot = int(base.get("rot") or 0) % len(SERIES)
    ser_now = [SERIES[(rot + i) % len(SERIES)] for i in range(SERIES_PER_SCAN)]
    plan = [("status", "GET /exchange/status", "/exchange/status", None),
            ("fees", "GET /series/fee_changes", "/series/fee_changes", None)]
    plan += [("market", "GET /markets (%s open)" % s, "/markets",
              {"series_ticker": s, "status": "open", "limit": str(MARKETS_LIMIT)}) for s in SERIES]
    plan += [("schedule", "GET /exchange/schedule", "/exchange/schedule", None),
             ("balance", "GET /portfolio/balance", "/portfolio/balance", None)]
    plan += [("series", "GET /series/%s" % s, "/series/" + s, None) for s in ser_now]
    got = []
    for what, ep, path, params in plan:
        st, body = sg(path, params)
        if st is None:
            break
        http_note(http, ep, st)
        got.append((what, ep, path, params, st, body))
    base["rot"] = (rot + SERIES_PER_SCAN) % len(SERIES)
    ok = [g for g in got if g[4] == 200]
    bad_net = [g for g in got if g[4] == -1 or (isinstance(g[4], int) and g[4] >= 500)]
    mk_words = {}
    status_body = None
    for what, ep, path, params, st, body in ok:
        if not isinstance(body, (dict, list)):
            continue
        if what == "status":
            status_body = body
            compare_keys(base.setdefault("shape_status", {}), key_paths(body), ep, r, "status")
        elif what == "fees":
            compare_keys(base.setdefault("shape_fees", {}), key_paths(body), ep, r, "fees", nested=False)
            ours = [x for x in _lists_of_dicts(body)
                    if re.search(r"\b(%s)\b" % "|".join(SERIES), canon(x))]
            seen = set(base.get("fees_seen") or [])
            first_read = "fees_seen" not in base
            ahead = 0
            for x in ours:
                h = sha256(canon(x))[:16]
                when = None
                for k in ("scheduled_ts", "effective_ts", "scheduled_time", "effective_time", "start_ts"):
                    when = _epoch_of(x.get(k)) or when
                if when is None or when >= now:
                    ahead += 1
                if h in seen:
                    continue
                seen.add(h)
                if first_read and when is not None and when < now:
                    continue                    # an old change already in force at the baseline
                s = x.get("series_ticker") or next((q for q in SERIES if q in canon(x)), "?")
                today = ((base.get("series") or {}).get(s) or {}).get("vals") or {}
                new = ", ".join("%s %s" % (k.replace("_", " "), show(v, 40)) for k, v in sorted(x.items())
                                if "fee" in k and v is not None) or show(x, 200)
                r.alert("fee|%s" % h, "Fee change scheduled on %s" % series_words(s),
                        "Kalshi has %s a fee change on %s%s: %s (today: %s x %s). Every trade's fee follows it: pin's "
                        "fee and its edge maths must match before then." % (
                            "already scheduled" if first_read else "scheduled", series_words(s),
                            (" from %s" % et(when)) if when else "", new,
                            show(json.loads(today.get("fee_type", "null"))) if today.get("fee_type") else "?",
                            show(json.loads(today.get("fee_multiplier", "null"))) if today.get("fee_multiplier") else "?"),
                        True)
            base["fees_seen"] = sorted(seen)
            base["fees_ahead"] = ahead
        elif what == "market":
            s = params["series_ticker"]
            mk_words[s] = check_markets(base.setdefault("markets", {}).setdefault(s, {}), s, body, r, now)
        elif what == "schedule":
            compare_keys(base.setdefault("shape_schedule", {}), key_paths(body), ep, r, "schedule", nested=False)
            sc = (body.get("schedule") or {}) if isinstance(body, dict) else {}
            hs = sha256(canon(sc.get("standard_hours")))[:16]
            if base.get("hours_sha") and base["hours_sha"] != hs:
                r.alert("hours|%s" % hs, "Kalshi changed its trading hours",
                        "Kalshi changed its standard trading hours (the schedule answer's standard_hours). Pin trades "
                        "every hour of every day: check the new hours do not leave gaps.", False)
            base["hours_sha"] = hs
            wins = [w for w in (sc.get("maintenance_windows") or []) if isinstance(w, dict)]
            wseen = set(base.get("windows_seen") or [])
            first_read = "windows_seen" not in base
            keep = []
            for w in wins:
                a, b = _epoch_of(w.get("start_datetime")), _epoch_of(w.get("end_datetime"))
                if a and b:
                    keep.append([a, b])
                h = sha256(canon(w))[:16]
                if h in wseen:
                    continue
                wseen.add(h)
                if first_read and b and b < now:
                    continue
                if a and b and maint_window(a)[0] <= a and b <= maint_window(a)[1]:
                    continue                    # the usual Thursday 3-5 AM ET stretch: listed by /watch, not said
                r.alert("maint|%s" % h, "Kalshi scheduled maintenance",
                        "Kalshi scheduled maintenance%s. Pin cannot trade or hedge then." % (
                            (" from %s to %s" % (et(a), et(b))) if a and b else ": %s" % show(w)), False)
            base["windows_seen"] = sorted(wseen)
            base["windows"] = [w for w in keep if w[1] > now - 86400][-20:]
        elif what == "balance":
            compare_keys(base.setdefault("shape_balance", {}), key_paths(body), ep, r, "balance",
                         why_missing=" Pin sizes its bets from this answer.")
        elif what == "series":
            check_series(base.setdefault("series", {}).setdefault(path.rsplit("/", 1)[-1], {}),
                         path.rsplit("/", 1)[-1], body, r)
    # trading paused outside the schedule (URGENT while it lasts); not judged when the status read failed
    if status_body is not None and isinstance(status_body, dict):
        ea, ta = status_body.get("exchange_active"), status_body.get("trading_active")
        if ea is False or ta is False:
            sched = any(a <= now < b for a, b in (base.get("windows") or [])) or in_maint(now)
            if not sched:
                r.open("kalshi_paused", "Kalshi has paused trading outside its schedule",
                       "At %s Kalshi's exchange status says %s: outside its maintenance schedule and outside Thursday "
                       "3-5 AM ET. Pin cannot buy or hedge while it lasts." % (
                           et(now), " and ".join(w for w in ("the exchange is closed" if ea is False else "",
                                                             "trading is off" if ta is False else "") if w)), True)
    else:
        r.keep += ("kalshi_paused",)
    # HTTP error patterns, from every endpoint's last answer (one not read this scan keeps its last)
    auth = sorted(ep for ep, h in http.items() if h.get("last") in (401, 403))
    if auth:
        r.open("api_key_refused", "Kalshi refused pin's key",
               "Kalshi answered %s to %s. Pin signs with the same key: while it lasts pin cannot see its bank or "
               "send orders." % ("/".join(sorted({str(http[e]["last"]) for e in auth})), ", ".join(auth[:4])), True)
    for ep, h in sorted(http.items()):
        if h.get("last") in (404, 410):
            r.open("api_gone|%s" % ep, "Kalshi answered 'not found' to %s" % ep,
                   "Kalshi answered %s (not found) to %s, %s. The endpoint or the series may have moved or closed." % (
                       h["last"], ep, "which answered 200 before" if h.get("ever200") else
                       "and it has not answered 200 since the watch started"), True)
    lim = sorted(ep for ep, h in http.items() if h.get("last") == 429 and int(h.get("streak") or 0) >= 2)
    if lim:
        r.open("api_429", "Kalshi is rate-limiting the signed reads",
               "Kalshi answered 429 (too many requests) to %s on 2 scans running. Pin shares this key's budget: if "
               "pin's own reads are limited too, it trades and hedges late." % ", ".join(lim[:4]), False)
    n_ser = len(base.get("series") or {})
    fees = sorted({json.loads((v.get("vals") or {}).get("fee_type", "null")) or "?"
                   for v in (base.get("series") or {}).values()} - {None})
    mults = sorted({show(json.loads((v.get("vals") or {}).get("fee_multiplier", "null")))
                    for v in (base.get("series") or {}).values()})
    r.extra["calls"] = len(sg.calls)
    r.extra["gaps"] = [round(b[2] - a[2], 3) for a, b in zip(sg.calls, sg.calls[1:])]
    nopen = sum(1 for w in mk_words.values() if w != "no open market")
    r.detail = "%d of %d signed reads ok; %d of %d series had an open market; %d series answers on file" % (
        len(ok), len(got), nopen, len(SERIES), n_ser)
    r.summary = ("%d of %d signed reads ok; fees on the %d series read so far: %s x %s; %d fee changes scheduled on our "
                 "series; trading %s; %d maintenance windows listed" % (
                     len(ok), len(got), n_ser, "/".join(fees) or "?", "/".join(mults) or "?",
                     int(base.get("fees_ahead") or 0),
                     "PAUSED" if (status_body or {}).get("trading_active") is False else "active",
                     len(base.get("windows") or [])))
    if not got:
        return r.fail("no signed read was made")
    if not ok or len(bad_net) * 2 >= len(got):
        refused = {}
        for g in got:
            if isinstance(g[4], int) and 400 <= g[4] < 500:
                refused[g[4]] = refused.get(g[4], 0) + 1
        parts = ["%d of %d signed reads ok" % (len(ok), len(got))]
        if refused:
            parts.append("%d refused by Kalshi (%s)" % (sum(refused.values()), ", ".join(
                "HTTP %d x%d" % (c, n) for c, n in sorted(refused.items()))))
        if bad_net:
            parts.append("%d got no answer or a Kalshi server error" % len(bad_net))
        why = "; ".join(parts)
        if sg.net >= NET_ABORT:
            why += "; the rest were skipped after %d network failures in a row" % NET_ABORT
        r.status, r.detail = "failed", why
    return r


# ---------------------------------------------------------------------------- 3. documents
def pdf_norm(body):
    """A PDF without what a server may stamp on every copy it serves (/CreationDate, /ModDate, /ID, the XMP dates):
    its sha256 then changes only when the document does."""
    b = re.sub(rb"/(CreationDate|ModDate)\s*\((?:[^()\\]|\\.)*\)", b"", body)
    b = re.sub(rb"/ID\s*\[\s*<[0-9A-Fa-f]*>\s*<[0-9A-Fa-f]*>\s*\]", b"", b)
    return re.sub(rb"<xmp:(CreateDate|ModifyDate|MetadataDate)>[^<]*</xmp:\1>", b"", b)


PDF_NOISY = 3                                       # changed on this many scans running: its changes go quiet
PDF_REFUSED = 48                                    # v-kwfalse: no answer on this many scans running: 'site refuses'


def check_pdf(env, base, now, url, what, urgent, refused_after=None):
    """refused_after (v-kwfalse, 2026-11-13; the CF PDF only): after that many scans in a row with no answer at all (-1:
    no connection, no HTTP status) the site is marked 'site refuses', said once, quietly, like a PDF that changes on
    every read (PDF_NOISY), and then only on /watch: the check is no longer a failing one (its 'cannot read' condition
    ends without a 'reads again' note), it is still tried every scan, and the first answer of any kind ends the mark
    (said, quietly). The CF PDF answered -1 on all 226 scans from 11-08 to 11-13 and stood on /watch as FAILED. The
    streak is counted here from the deploy on, so on the server the mark comes 48 scans (24 hours) after it."""
    r = Result()
    st, body, hd = env.fetch(url)
    if refused_after:
        if st == -1:
            base["no_answer"] = int(base.get("no_answer") or 0) + 1
            base.setdefault("no_answer_since", iso(now))
            base["no_answer_why"] = show(bytes(body or b"").decode("utf-8", "replace"), 160)
        else:
            was, n = base.pop("refused", None), int(base.get("no_answer") or 0)
            since = clock.utc_epoch(base.get("no_answer_since")) if base.get("no_answer_since") else None
            for k in ("no_answer", "no_answer_since", "no_answer_why"):
                base.pop(k, None)
            if was:
                r.alert("pdf|answers|%s|%s" % (what, iso(now)), "%s: the site answers again" % what,
                        "%s answered again (HTTP %s) after %d scans with no answer%s. From this scan on it is read as "
                        "before%s." % (url, st, n, (" (since %s)" % et(since)) if since is not None else "",
                                       "" if st == 200 else ": a failed read counts toward the usual 3-scan streak"),
                        False)
        if st == -1 and int(base.get("no_answer") or 0) >= refused_after:
            n, since = int(base["no_answer"]), clock.utc_epoch(base["no_answer_since"])
            r.extra["refused"] = True
            r.detail = ("site refuses the server: no answer on %d scans in a row since %s (the last: %s); marked 'site "
                        "refuses' at the %s scan, still tried every scan, said when it answers" % (
                            n, et(since), base.get("no_answer_why") or "-1", _ordinal(refused_after)))
            if not base.get("refused"):
                base["refused"] = iso(now)
                r.alert("pdf|refused|%s|%s" % (what, base["no_answer_since"]), "%s: the site refuses the server" % what,
                        "%s has given no answer at all (-1: no connection, no HTTP status) on %d scans in a row, "
                        "about %s, since %s (the last: %s). Marked 'site refuses': it is still tried every scan but no "
                        "longer counted as a failing check (/watch says so) and nothing more is said until it answers. "
                        "It only says which exchanges make CF's indices; pin's trades do not wait on it." % (
                            url, n, mins(n * EVERY_MIN * 60), et(since), base.get("no_answer_why") or "-1"), False)
            return r
    if st != 200:
        return r.fail("%s answered %s" % (url, st))
    if not body.startswith(b"%PDF"):
        return r.fail("%s answered something that is not a PDF (%s)" % (url, show(body[:40].decode("latin-1"), 60)))
    h = sha256(pdf_norm(body))
    r.detail = "%s bytes, sha256 %s" % ("{:,}".format(len(body)), h[:12])
    if not base.get("sha"):
        base.update(sha=h, bytes=len(body), last_modified=hd.get("last-modified"), t=iso(now), run=0)
        r.summary = "recorded (%s bytes, sha256 %s)" % ("{:,}".format(len(body)), h[:12])
        return r
    if h == base["sha"]:
        base["run"] = 0
        return r
    run = int(base.get("run") or 0) + 1
    base["run"] = run
    if run > PDF_NOISY:
        r.detail += " (it changes on every read: changes not said until it holds still)"
    else:
        lm = http_date_et(hd.get("last-modified"))
        r.alert("pdf|%s|%s" % (what, h[:16]), "%s changed" % what,
                "%s changed: was %s bytes (sha256 %s), now %s bytes (sha256 %s)%s. Read it: %s%s" % (
                    what, "{:,}".format(int(base.get("bytes") or 0)), base["sha"][:12], "{:,}".format(len(body)), h[:12],
                    (", the site says it was last edited %s" % lm) if lm else "", url,
                    ("\nIt has now changed on %d scans running: it may change on every read, so until it holds still "
                     "its changes are only on /watch." % run) if run == PDF_NOISY else ""),
                urgent and run < PDF_NOISY)
    base.update(sha=h, bytes=len(body), last_modified=hd.get("last-modified"), t=iso(now))
    return r


def check_contract_pdf(env, base, now):
    return check_pdf(env, base, now, CONTRACT_PDF, "The 15-minute crypto contract terms (CRYPTO15M.pdf)", True)


def check_cfb_pdf(env, base, now):
    return check_pdf(env, base, now, CFB_PDF, "CF Benchmarks' list of the exchanges in its indices", False,
                     refused_after=PDF_REFUSED)


RESOLVED = ("resolved", "postmortem", "completed")
PIN_COINS = ("BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ZEC", "NEAR", "HYPE")
PIN_COIN_NAMES = ("Bitcoin", "Ether", "Ethereum", "Solana", "XRP", "Dogecoin", "BNB", "Zcash", "NEAR", "Hyperliquid",
                  "HYPE")
OUR_INDEX_RES = (re.compile(r"\bBRTI\b"),
                 re.compile(r"\b(%s)USD[_ ]RTI\b" % "|".join(PIN_COINS)),
                 re.compile(r"\b(%s)(-Dollar)? Real[- ]Time Ind(ex|ices)\b" % "|".join(PIN_COIN_NAMES), re.I))
ALL_INDEX_RE = re.compile(r"\ball (index families|indices|indexes|real[- ]time indices)\b|\bplatform\b", re.I)


def names_our_index(title, text=""):
    """True when an incident names an index pin's markets settle on (BRTI, ETHUSD_RTI, ... 'CME CF Bitcoin Real Time
    Index'; title or text), or its TITLE names all of CF's indices or its platform. 'CME CF Bitcoin Volatility Index',
    'UMAUSD_RTI', funding rates: False."""
    words = "%s %s" % (title or "", text or "")
    return any(rx.search(words) for rx in OUR_INDEX_RES) or bool(ALL_INDEX_RE.search(title or ""))


def parse_incidents(url, txt):
    """[{id, title, status, when, text, resolved}] from Statuspage's incidents.json or an RSS / Atom history."""
    out = []
    if url.endswith(".json"):
        d = json.loads(txt)
        for x in (d.get("incidents") or []) if isinstance(d, dict) else []:
            if not isinstance(x, dict) or not x.get("id"):
                continue
            ups = x.get("incident_updates") or []
            body = _text((ups[0] or {}).get("body") if ups and isinstance(ups[0], dict) else "")
            stt = str(x.get("status") or "")
            out.append({"id": str(x["id"]), "title": str(x.get("name") or "")[:200], "status": stt,
                        "when": _epoch_of(x.get("created_at")), "text": body[:400],
                        "resolved": stt.lower() in RESOLVED, "link": x.get("shortlink") or ""})
        return out
    for e in parse_rss(txt):
        body = re.sub(r"^[A-Z][a-z]{2} \d{1,2}, \d{1,2}:\d{2} UTC\s*", "", e["text"])    # Statuspage's own stamp
        low = body.lower()
        out.append({"id": e["link"] or e["key"], "title": e["title"], "status": "", "when": None,
                    "text": body[:400], "resolved": any(w in low[:80] for w in RESOLVED), "link": e["link"]})
    return out


def check_cfb_status(env, base, now):
    r = Result()
    incs, src, whys = None, None, []
    for url in CFB_STATUS_URLS:
        st, body, _hd = env.fetch(url)
        if st != 200 or not body:
            whys.append("%s answered %s" % (url.rsplit("/", 1)[-1], st))
            continue
        try:
            incs = parse_incidents(url, body.decode("utf-8", "replace"))
        except ValueError:
            incs = None
        if incs is not None and (incs or url.endswith(".json")):
            src = url
            break
        whys.append("%s had nothing I could read" % url.rsplit("/", 1)[-1])
        incs = None
    if incs is None:
        return r.fail("could not read the CF Benchmarks status page: %s" % "; ".join(whys))
    openi = [i for i in incs if not i["resolved"]]
    r.detail = "%s listed, %d not resolved (read from %s)" % (plural(len(incs), "incident"), len(openi),
                                                              src.rsplit("/", 1)[-1])
    seen = set(base.get("seen") or [])
    if "seen" not in base:
        base["seen"] = sorted(i["id"] for i in incs)[-300:]
        r.summary = r.detail
        return r
    for i in incs:
        if i["id"] in seen:
            continue
        seen.add(i["id"])
        ours = names_our_index(i["title"], i["text"])
        r.alert("cfb|%s" % sha256(i["id"])[:16], "CF Benchmarks incident: %s" % i["title"],
                "CF Benchmarks (its indices settle every pin market) posted an incident%s: \"%s\"%s. %s%s%s" % (
                    (" at %s" % et(i["when"])) if i["when"] else "", i["title"],
                    (" (status: %s)" % i["status"]) if i["status"] else "",
                    ("It names an index pin settles on%s." % (" and is not resolved: pin's markets may settle on a "
                                                              "late or wrong price" if not i["resolved"] else "")
                     ) if ours else "It names no index pin settles on (BRTI and the other coins' RTIs).",
                    (" What it says: %s" % show(i["text"], 300)) if i["text"] else "",
                    (" %s" % i["link"]) if i["link"] else ""), ours and not i["resolved"])
    listed = {i["id"] for i in incs}                # what the page lists now is always kept (never said twice)
    base["seen"] = sorted(listed) + sorted(seen - listed)[:300]
    return r


# ---------------------------------------------------------------------------- 4. pin's live log
def _read_from(path, off):
    """(records, new offset, bytes skipped) from byte `off` to the last whole line; nothing when the log is gone
    since the listing (research/log_rotate.py archived it)."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return [], off, 0
    if off > size:
        off = 0
    skipped = 0
    if size - off > READ_CAP:
        skipped = size - READ_KEEP - off
        off = size - READ_KEEP
    with open(path, "rb") as fh:
        fh.seek(off)
        chunk = fh.read(size - off)
    end = chunk.rfind(b"\n") + 1
    recs = []
    for ln in chunk[:end].splitlines():
        try:
            d = json.loads(ln.decode("utf-8", "replace"))
        except ValueError:
            continue
        if isinstance(d, dict):
            recs.append(d)
    return recs, off + end, skipped


def _stamp_epoch(path):
    m = re.search(r"(\d{8}T\d{6})Z", os.path.basename(path))
    if not m:
        return None
    try:
        return float(calendar.timegm(time.strptime(m.group(1), "%Y%m%dT%H%M%S")))
    except ValueError:
        return None


def fields_words(rec, cap=420, skip=()):
    parts = []
    for k, v in rec.items():
        if k in ("t", "kind", "close_s") or k in skip:         # the time and the market label say these
            continue
        s = v if isinstance(v, str) else canon(v)
        parts.append("%s=%s" % (k, s if len(s) <= 80 else s[:77] + "..."))
    out = " ".join(parts)
    return out if len(out) <= cap else out[:cap - 3] + "..."


def pin_judge(d):
    """(urgent, words) for one of pin's alarm records ("Pin <words>"), or None: never said (expiry_drain, the run's
    ordinary end; expiry_exit when flat). Block records (a `reason`) are judged by check_pin_log, not here."""
    k = d.get("kind")
    if k == "universe_empty":
        if d.get("what") == "recovered":
            return False, "has markets again after an empty market list"
        return True, PIN_ALARM_WORDS[k]
    if k == "unbooked":
        if d.get("what") == "booked":
            return False, "booked a bet that had gone unbooked (its real result replaced the provisional loss)"
        if d.get("what") == "gave_up":
            return True, "gave up booking a bet (it stays written off for the run)"
        return True, PIN_ALARM_WORDS[k]
    if k == "startup_bank":
        if d.get("source") == "api":
            return False, "read its bank at startup after a retry"
        if d.get("source") == "mirror":
            return False, "set its day stop from its last known bank (Kalshi's balance did not answer at startup)"
        return True, PIN_ALARM_WORDS[k]
    if k == "log_write_fail" and d.get("which") == "traj":
        return False, "could not write its trajectory file (an instrument: it blocks nothing)"
    if k == "expiry_exit":
        return (True, PIN_ALARM_WORDS[k]) if d.get("flat") is False else None
    if k == "expiry_drain":
        return None
    if k == "api_shape" and (d.get("endpoint") or d.get("field")):
        # v-kwfalse (2026-11-13): the endpoint and the field in the head, so a /portfolio/balance shape reads (and is
        # grouped) apart from a /markets one
        return True, "%s: %s, field %s" % (PIN_ALARM_WORDS[k], show(str(d.get("endpoint") or "?"), 60),
                                           show(str(d.get("field") or "?"), 60))
    if k in PIN_ALARM_WORDS:
        return True, PIN_ALARM_WORDS[k]
    return None


SHAPE_NEW_MARKET_S = 90                             # v-kwfalse: a strike missing this soon after the open is not news
_MON3 = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def shape_harmless(d):
    """v-kwfalse (2026-11-13): why one of pin's api_shape records is a known harmless shape (written in the watch's log,
    results\\kalshi_watch.log, never sent to the phone), or None (it keeps its level: URGENT). 5 of the watch's 12
    URGENT alarms in its first 4.7 days (the 11-13 read) were these two, written once at every pin start (pin writes
    each endpoint / field / what once a process), and exactly these two:
      - a websocket orderbook_snapshot with no yes_dollars_fp / no_dollars_fp whose only other key is 'clock'
        (absent_with_other_keys, keys 'clock'): an empty book's snapshot, no price level on either side. Any other key
        beside it, or none, keeps the alarm.
      - /markets floor_strike missing, written less than SHAPE_NEW_MARKET_S seconds into its quarter-hour, on the market
        that opened then (its ticker closes 15 minutes after that quarter-hour, Eastern): Kalshi fills the strike 20-60
        s after a market opens (11-08 14:45:20Z KXSOL15M 10:00, 18:30:20Z KXDOGE15M 13:45, 11-10 13:15:20Z KXXRP15M
        8:30: each 20 s in). Pin skips such a row until the strike is there. A strike missing later, on another market,
        from /events, or the field gone for good still rings: the signed /markets read here also says a missing
        floor_strike (URGENT after 2 scans)."""
    if d.get("kind") != "api_shape":
        return None
    ep, f, what = (str(d.get(x) or "") for x in ("endpoint", "field", "what"))
    if ep == "ws orderbook_snapshot" and f == "yes_dollars_fp/no_dollars_fp" and what == "absent_with_other_keys":
        ks = d.get("keys")
        ks = [str(x).strip() for x in (ks if isinstance(ks, list) else str(ks or "").split(","))]
        return "an empty book's snapshot: no price levels, only its 'clock' key" if ks == ["clock"] else None
    if ep == "/markets" and f == "floor_strike" and what == "missing":
        te = clock.utc_epoch(d.get("t")) if d.get("t") else None
        if te is None:
            return None
        into = te % 900.0                   # ET is a whole number of hours from UTC: the quarter-hours are the same
        if into >= SHAPE_NEW_MARKET_S:
            return None
        close = te - into + 900.0
        tm = time.gmtime(close + clock._et_off(close))
        stamp = "%02d%s%02d%02d%02d" % (tm.tm_year % 100, _MON3[tm.tm_mon - 1], tm.tm_mday, tm.tm_hour, tm.tm_min)
        m = re.match(r"^KX[A-Z0-9]+?15M-(\d{2}[A-Z]{3}\d{6})-", str(d.get("ticker") or ""))
        if not m or m.group(1) != stamp:
            return None
        return ("a market %d seconds old without its strike yet (Kalshi fills it 20-60 seconds after the open)"
                % int(into))
    return None


def hedge_refused(d):
    """What a hedge / hedge_extra record says Kalshi refused: its 4xx status_code (pin writes it on every live hedge
    since 0925t, v-hedgetick), or 'noid' for a record from before that (no status_code at all) that went live and came
    back with no order id and nothing filled (the 10-31..11-04 off-grid hedges). None: not a refusal (a fill, a 5xx or
    no answer, a hedge pin never sent: its own hedge_fail record says those)."""
    if d.get("kind") not in HEDGE_KINDS:
        return None
    if "status_code" in d:
        try:
            c = int(str(d.get("status_code")).strip())
        except (TypeError, ValueError):
            return None
        return c if 400 <= c < 500 else None
    try:
        n = float(d.get("n") or 0)
    except (TypeError, ValueError):
        n = 0.0
    return "noid" if d.get("live") is True and not d.get("order_id") and n <= 0 else None


def _code_words(c):
    return "no order id, nothing filled" if c == "noid" else "HTTP %s" % c


def check_pin_log(env, base, now):
    r = Result()
    paths = sorted(glob.glob(env.path("pinrun-live-*.jsonl")))
    if not paths:
        r.detail = "no pin live log in the results folder: nothing to read"
        r.keep = ("pin_",)
        return r
    cur = paths[-1]
    prev = base.get("path")
    first = not prev                    # the first read only learns where pin is: nothing in it is said one by one
    if prev == cur:
        reads = [(cur, int(base.get("offset") or 0))]
    elif prev and prev in paths:
        reads = [(prev, int(base.get("offset") or 0)), (cur, 0)]
    elif prev:
        reads = [(cur, 0)]
    else:
        try:
            first_off = max(0, os.path.getsize(cur) - TAIL_FIRST)
        except OSError:             # gone since the listing (log_rotate): _read_from then reads nothing
            first_off = 0
        reads = [(cur, first_off)]
    if prev != cur:
        base["log_start"] = _stamp_epoch(cur)
    blocks = dict(base.get("blocks") or {})       # reason -> {kind, t, fields, said}: pin's entry blocks in force
    h4 = [x for x in (base.get("h4xx") or []) if x[0] >= now - 2 * HEDGE_WINDOW_S]
    alarms, ended, new_ref = {}, [], []
    n_recs, skipped, n_harmless = 0, 0, 0
    for p, off in reads:
        got, end, sk = _read_from(p, off)
        skipped += sk
        n_recs += len(got)
        if p == cur:
            base["path"], base["offset"] = cur, end
            if prev != cur:
                blocks = {}             # a new pin run: the old process's blocks ended with it
        for d in got:
            k = d.get("kind")
            te = clock.utc_epoch(d.get("t")) if d.get("t") else None
            if k == "universe":
                try:
                    if te is not None and float(d.get("got") or 0) > 0:
                        base["last_universe_ok"] = max(float(base.get("last_universe_ok") or 0), te)
                except (TypeError, ValueError):
                    pass
                continue
            code = hedge_refused(d)
            if code is not None:
                if te is not None:
                    h4.append([te, code, d.get("ticker"), str(d.get("err") or "")[:160], d.get("close_s")])
                    new_ref.append(te)
                continue
            if k in BLOCK_KINDS and d.get("reason"):
                why = str(d["reason"])
                if k not in BLOCK_IGNORE and why not in BLOCK_IGNORE and why not in blocks:
                    blocks[why] = {"kind": k, "t": d.get("t"), "fields": fields_words(d, 300, ("reason", "blocks")),
                                   "said": False}
                continue
            if k == "entries_resumed" and d.get("reason"):
                b = blocks.pop(str(d["reason"]), None)
                if b is not None and not b.get("said") and not first:
                    ended.append((str(d["reason"]), b, d))
                continue
            if k in PIN_ALARM_KINDS:
                why = shape_harmless(d)
                if why:                 # v-kwfalse: the watch's log only, never the phone
                    n_harmless += 1
                    env.log("pin api_shape of a known harmless shape, not sent to the phone: %s. Its record: %s%s" % (
                        why, ("%s; " % d["t"]) if d.get("t") else "", fields_words(d, 300)))
                    continue
                j = pin_judge(d)
                if j is None:
                    continue
                stale = te is not None and now - te > PIN_STALE_S
                alarms.setdefault((k, j[1]), []).append((d, j[0] and not stale, stale))
    h4.sort(key=lambda x: x[0])
    base["h4xx"] = h4[-500:]
    n_alarm = sum(len(v) for v in alarms.values())
    if not first:
        for (k, words), items in alarms.items():
            lines = ["Pin wrote %s %s record%s in its log (its fields as written):" % (
                len(items), k, "" if len(items) == 1 else "s")]
            for d, _u, stale in items[:3]:
                te = clock.utc_epoch(d.get("t")) if d.get("t") else None
                lines.append("- %s%s%s: %s" % (
                    et(te), (" · " + market_words(d["ticker"], d.get("close_s"))) if d.get("ticker") else "",
                    (" (written %s before this scan: the watch was not reading then)" % mins(now - te)) if stale else "",
                    fields_words(d)))
            if len(items) > 3:
                lines.append("- and %d more (pin's log has them all)" % (len(items) - 3))
            r.alert("pinrec|%s|%s|%s|%d" % (k, sha256(words)[:6], items[0][0].get("t"), len(items)),
                    "Pin %s (%s)" % (words, k), "\n".join(lines), any(u for _d, u, _s in items))
        for why, b, d in ended:
            t0, t1 = clock.utc_epoch(b.get("t")), clock.utc_epoch(d.get("t"))
            r.alert("pinblk|%s|%s" % (why, b.get("t")), "Pin paused new bets for %s and resumed" % (
                span_words(t1 - t0) if t0 is not None and t1 is not None else "a while"),
                "Between two scans pin stopped opening new bets at %s (%s: %s) and opened them again at %s. Hedges, "
                "cancels and settlement ran as usual. Its record: %s" % (
                    et(t0), why, BLOCK_WORDS.get(why, why), et(t1), b.get("fields")), False)
    for why, b in sorted(blocks.items()):
        t0 = clock.utc_epoch(b.get("t")) if b.get("t") else None
        r.open("pin_block|%s" % why, "Pin has stopped opening new bets: %s" % BLOCK_WORDS.get(why, why),
               "Since %s%s pin's log says new entries are blocked (%s, its %s record): %s. Hedges, cancels and "
               "settlement run as before. It lifts by itself when the cause ends, and the phone says so." % (
                   et(t0), (" (%s ago)" % mins(now - t0)) if t0 is not None else "", why, b.get("kind"),
                   b.get("fields")), True)
        b["said"] = True
    base["blocks"] = blocks
    # refused hedges: the most in any hour that ends at a refusal read now or at this scan, over the last 2 hours
    ends = sorted({now} | {te for te in new_ref if te >= now - 2 * HEDGE_WINDOW_S})
    best, best_end = 0, now
    for e in ends:
        n = sum(1 for x in h4 if e - HEDGE_WINDOW_S < x[0] <= e)
        if n > best:
            best, best_end = n, e
    trailing = sum(1 for x in h4 if now - HEDGE_WINDOW_S < x[0] <= now)
    if not first and best > HEDGE_4XX_MAX:
        win = [x for x in h4 if best_end - HEDGE_WINDOW_S < x[0] <= best_end]
        codes = {}
        for x in win:
            codes[_code_words(x[1])] = codes.get(_code_words(x[1]), 0) + 1
        last = win[-1]
        r.open("pin_hedge_4xx", "Kalshi refused %d of pin's hedge orders in an hour" % best,
               "%d hedge orders in one hour came back refused by Kalshi (%s), the last at %s on the %s%s. A refused "
               "hedge leaves a bet without its insurance. The 11-04 bug (hedges sent at prices Kalshi does not "
               "allow) looked exactly like this." % (
                   best, ", ".join("%s x%d" % (c, n) for c, n in sorted(codes.items())), et(last[0]),
                   market_words(last[2], last[4]), (": '%s'" % last[3]) if last[3] else ""), True)
    stop = os.path.exists(env.path(PIN_STOP_NAME))
    if stop:
        base["stop_seen"] = now
    last_ok = base.get("last_universe_ok")
    # the silence counts from the newest of: the last market list with markets, the start of pin's log (a new run has
    # had no time to list), the last scan that saw pin stood down (a stand-down that just ended)
    refs = [float(x) for x in (last_ok, base.get("log_start"), base.get("stop_seen")) if x]
    ref = max(refs) if refs else None
    m0, m1 = maint_window(now)
    if ref is not None and m0 - UNIVERSE_SILENT_S <= ref < m1 <= now:
        ref = m1                                # a silence that began with the maintenance stretch counts from its end
    try:
        log_age = now - os.path.getmtime(cur)
    except OSError:
        log_age = None
    base["log_age_s"] = log_age
    silent = (now - ref) if ref is not None else None
    if stop:
        r.detail = "pin is stood down (pinrun-live.stop): the market-list alarm is off"
    elif m0 <= now < m1:
        r.detail = "Thursday 3-5 AM ET (Kalshi's maintenance): the market-list alarm waits"
    elif silent is not None and silent > UNIVERSE_SILENT_S:
        r.open("pin_no_markets", "Pin has seen no markets for %s" % mins(silent),
               "Pin's log has no market list with markets in it for %s (the last one: %s). Pin cannot buy or hedge new "
               "markets like that.%s" % (
                   mins(silent), et(float(last_ok)) if last_ok else "none since this pin run started",
                   (" Its log has not been written for %s either: pin may be down (the phone's DOWN alert covers "
                    "that)." % mins(log_age)) if log_age is not None and log_age > UNIVERSE_SILENT_S else ""), True)
    if not r.detail:
        r.detail = "%s read since the last scan; last market list with markets %s; %d hedge refusals in the last hour" % (
            plural(n_recs, "record"), et(float(last_ok)) if last_ok else "none yet", trailing)
    if blocks:
        r.detail += "; new entries blocked: %s" % ", ".join(sorted(blocks))
    if n_harmless:
        r.detail += "; %s of a known harmless shape only logged" % plural(n_harmless, "api_shape record")
    if skipped:
        r.detail += " (%s MB skipped: too much to read in one scan)" % ("%.1f" % (skipped / 2.0 ** 20))
    r.summary = "reading %s; last market list with markets %s" % (
        os.path.basename(cur), et(float(last_ok)) if last_ok else "none yet")
    if first and n_alarm:
        kinds = {}
        for (k, _w), items in alarms.items():
            kinds[k] = kinds.get(k, 0) + len(items)
        r.summary += "; the last %s of its log hold %s from before the watch started (not said one by one: %s)" % (
            "%.0f MB" % (TAIL_FIRST / 2.0 ** 20), plural(n_alarm, "warning record"),
            ", ".join("%s x%d" % (k, n) for k, n in sorted(kinds.items())))
    return r


# ---------------------------------------------------------------------------- 5. the server
def check_disk(env, base, now):
    r = Result()
    gb = float(env.disk_free()) / 1e9
    was = base.get("open") or []
    if gb < DISK_WARN_GB or ("disk_low" in was and gb < DISK_WARN_GB + DISK_HYST_GB):
        r.open("disk_low", "Server disk C: is down to %.1f GB free" % gb,
               "The server's C: drive has %.1f GB free (the alert line is %.0f GB; under %.0f GB it becomes urgent). "
               "Logs grow every day: free space before it runs out." % (gb, DISK_WARN_GB, DISK_URGENT_GB), False)
    if gb < DISK_URGENT_GB or ("disk_very_low" in was and gb < DISK_URGENT_GB + DISK_HYST_GB):
        r.open("disk_very_low", "Server disk C: has only %.1f GB free" % gb,
               "The server's C: drive has only %.1f GB free (under %.0f GB). When it fills, pin and the phone cannot "
               "write their logs or state." % (gb, DISK_URGENT_GB), True)
    base["open"] = sorted(r.opens)
    base["gb"] = round(gb, 2)
    r.detail = r.summary = "%.1f GB free" % gb
    return r


def _norm_pkg(n):
    return re.sub(r"[-_.]+", "-", n).lower()


def read_reqs(path):
    """{normalised name: (name, op, version)} or None when the file is missing. 'name==version', 'name>=version',
    'name version' or 'name: version' a line; '#' starts a comment."""
    try:
        with open(path, encoding="utf-8-sig") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None
    out = {}
    for ln in lines:
        ln = ln.split("#", 1)[0].strip()
        if not ln:
            continue
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.\-]*)\s*(==|>=|~=|:|\s)\s*([^\s;,]+)", ln)
        if m:
            op = m.group(2).strip() or "=="
            out[_norm_pkg(m.group(1))] = (m.group(1), "==" if op == ":" else op, m.group(3))
    return out


def _vtuple(v):
    return tuple(int(x) if x.isdigit() else x for x in re.findall(r"\d+|[a-z]+", str(v).lower()))


def check_packages(env, base, now):
    r = Result()
    reqs = read_reqs(env.path(REQS_NAME))
    if reqs is None:
        r.detail = r.summary = "no pinned list yet (results\\%s): nothing to compare" % REQS_NAME
        return r
    bad = 0
    for k, (name, op, want) in sorted(reqs.items()):
        have = env.version_of(name)
        okv = have is not None and (have == want if op == "==" else
                                    _vtuple(have) >= _vtuple(want) if op in (">=", "~=") else have == want)
        if not okv:
            bad += 1
            r.open("pkg|%s" % k, "Python package %s is %s on the server" % (name, have or "missing"),
                   "The server's Python package %s is %s; results\\%s says %s %s. A package that moved can change "
                   "how pin talks to Kalshi (requests and urllib3 carry its orders, websockets its live feed, "
                   "cryptography signs every order)." % (
                       name, ("version " + have) if have else "not installed", REQS_NAME,
                       "exactly" if op == "==" else "at least", want), False)
    r.detail = r.summary = "%d of %d match the pinned list" % (len(reqs) - bad, len(reqs))
    return r


def read_sums(path):
    """([(sha256, path as listed)], root or None) or (None, None) when the file is missing."""
    try:
        with open(path, encoding="utf-8-sig") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None, None
    out, root = [], None
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        m = re.match(r"^#\s*root\s*:\s*(.+)$", s, re.I)
        if m:
            root = m.group(1).strip()
            continue
        if s.startswith("#"):
            continue
        m = re.match(r"^\\?([0-9a-fA-F]{64})\s+\*?(.+)$", s) or None
        if m:
            out.append((m.group(1).lower(), m.group(2).strip()))
            continue
        m = re.match(r"^(.+?)\s+([0-9a-fA-F]{64})$", s)
        if m:
            out.append((m.group(2).lower(), m.group(1).strip()))
    return out, root


def read_live_paths(path):
    """{snapshot name lower-cased: the live file's path} from LIVE_PATHS.txt ("<name>  <path>" a line, '#' comments),
    or None when the file is missing. A path with spaces is fine: the name is the first word, the path the rest."""
    try:
        with open(path, encoding="utf-8-sig") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None
    out = {}
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split(None, 1)
        if len(parts) == 2:
            out[parts[0].lower()] = parts[1].strip()
    return out


def check_launchers(env, base, now):
    r = Result()
    rows, root = read_sums(env.path(SUMS_REL))
    if rows is None:
        r.detail = r.summary = "no snapshot list yet (results\\%s): nothing to compare" % SUMS_REL
        return r
    live = read_live_paths(env.path(LIVE_REL))
    bad = 0
    for want, p in rows:
        if live is not None:
            full = live.get(os.path.basename(p).lower())
            if not full:
                bad += 1
                r.open("launcher|%s" % p.lower(), "Snapshot launcher %s has no live path" % os.path.basename(p),
                       "results\\%s lists %s, but results\\%s does not say which live file it is a copy of, so it is "
                       "compared with nothing. Add a line '<name>  <live path>' to that file." % (
                           SUMS_REL, os.path.basename(p), LIVE_REL), False)
                continue
            label = full
        else:
            full = p if os.path.isabs(p) else os.path.join(root or env.repo, p)
            label = os.path.basename(p)
        try:
            with open(env.remap(full), "rb") as fh:
                have = sha256(fh.read())
        except OSError:
            have = None
        if have != want:
            bad += 1
            r.open("launcher|%s" % p.lower(), "Live launcher %s %s" % (
                label, "is missing" if have is None else "is not the snapshot"),
                   "The live launcher %s %s. If nobody deployed a change, something edited a file that starts a "
                   "bot." % (full, ("is missing (the snapshot %s has sha256 %s)" % (os.path.basename(p), want[:12]))
                             if have is None else
                             ("changed after the snapshot %s: its sha256 is now %s, the snapshot says %s" % (
                                 os.path.basename(p), have[:12], want[:12]))), False)
    r.detail = r.summary = "%d of %d match the snapshot" % (len(rows) - bad, len(rows))
    return r


CHECK_FN = {"changelog": check_changelog, "kalshi_api": check_kalshi_api, "contract_pdf": check_contract_pdf,
            "cfb_pdf": check_cfb_pdf, "cfb_status": check_cfb_status, "pin_log": check_pin_log, "disk": check_disk,
            "packages": check_packages, "launchers": check_launchers}


# ---------------------------------------------------------------------------- the scan
def new_state():
    return {"version": 1, "runs": 0, "checks": {}, "base": {}, "open": {}, "outbox": [], "sent_ids": [],
            "history": [], "changelog_recent": []}


def queue(st, aid, head, body, urgent, cid, now, kind="alert"):
    if aid in set(st["sent_ids"]) or any(o["id"] == aid for o in st["outbox"]):
        return False
    st["outbox"].append({"id": aid, "head": head, "body": body, "urgent": bool(urgent), "check": cid, "t": iso(now),
                         "kind": kind})
    return True


def _ordinal(n):
    return "%d%s" % (n, "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


def _open(st, oid, o, cid, now, first, at_base):
    """Open condition `oid`. At the first scan it is listed in the baseline note (at_base), not sent; after FLAP_MAX
    opens in FLAP_WINDOW_S it is quiet (on /watch only, opening and clearing silently) until the day has passed."""
    flaps = st.setdefault("flaps", {})
    times = [t for t in (flaps.get(oid) or []) if now - t < FLAP_WINDOW_S] + [now]
    flaps[oid] = times
    for k in [k for k, v in flaps.items() if not any(now - t < FLAP_WINDOW_S for t in v)]:
        del flaps[k]
    st["open"][oid] = {"check": cid, "head": o["head"], "body": o["body"], "urgent": o["urgent"], "since": iso(now),
                       "quiet": len(times) >= FLAP_MAX and not first}
    if first:
        at_base.append(st["open"][oid])
        return
    if len(times) > FLAP_MAX:
        return
    body = o["body"]
    if len(times) == FLAP_MAX:
        body += (" This is the %s time in a day it has started: until a day has passed it opens and clears only on "
                 "/watch, silently." % _ordinal(len(times)))
    queue(st, "open|%s|%s" % (oid, iso(now)), o["head"], body, o["urgent"], cid, now)


def scan(env, st, now, only=None):
    """One scan into state `st`: every check, the open conditions, the failure streaks, the baseline note. Sends
    nothing (deliver() does)."""
    for k, v in new_state().items():
        st.setdefault(k, v)
    first = not st.get("runs") and not only
    at_base = []                                # conditions already open at the first scan: in the baseline note
    for cid, label in CHECKS:
        if only and cid not in only:
            continue
        cs = st["checks"].setdefault(cid, {"fail_streak": 0})
        base = st["base"].setdefault(cid, {})
        try:
            r = CHECK_FN[cid](env, base, now)
        except Exception as e:                                  # noqa: BLE001
            r = Result().fail("the check broke: %s: %s" % (type(e).__name__, str(e)[:160]))
            env.log("check %s broke: %s" % (cid, traceback.format_exc().replace("\n", " | ")[-800:]))
        cs.update(label=label, status=r.status, detail=r.detail, t=iso(now),
                  order=[c for c, _l in CHECKS].index(cid))
        if r.summary:
            cs["summary"] = r.summary
        if r.status == "ok":
            cs["last_ok"] = iso(now)
        if "changelog_recent" in r.extra:
            st["changelog_recent"] = r.extra["changelog_recent"]
        if "calls" in r.extra:
            st["api_calls_last_scan"] = r.extra["calls"]
        for a in r.alerts:
            queue(st, a["id"], a["head"], a["body"], a["urgent"], cid, now)
        prev = {k: v for k, v in st["open"].items() if v.get("check") == cid and not k.startswith("fail|")}
        for oid, o in r.opens.items():
            if oid in st["open"]:
                st["open"][oid].update(head=o["head"], body=o["body"])
                continue
            _open(st, oid, o, cid, now, first, at_base)
        if r.status != "failed":
            for oid, o in prev.items():
                if oid in r.opens or any(oid.startswith(p) for p in r.keep):
                    continue
                del st["open"][oid]
                if o.get("quiet"):
                    continue
                queue(st, "clear|%s|%s" % (oid, iso(now)), "Cleared: %s" % o["head"],
                      "This is over (it started %s)." % et(clock.utc_epoch(o.get("since"))), False, cid, now, "cleared")
        if r.status == "failed":
            cs["fail_streak"] = int(cs.get("fail_streak") or 0) + 1
            if cs["fail_streak"] == 1:
                cs["fail_since"] = iso(now)
            if cs["fail_streak"] >= FAIL_STREAK and not cs.get("fail_alerted"):
                cs["fail_alerted"] = True
                since = cs.get("last_ok")
                head = "The Kalshi watch cannot read %s" % label
                body = ("%d scans in a row (about %s) could not read %s: %s. Until it reads again, changes there are "
                        "not seen.%s" % (cs["fail_streak"], mins(cs["fail_streak"] * EVERY_MIN * 60), label, r.detail,
                                         (" Last good read: %s." % et(clock.utc_epoch(since))) if since else ""))
                st["open"]["fail|" + cid] = {"check": cid, "head": head, "body": body, "urgent": False,
                                             "since": iso(now)}
                queue(st, "open|fail|%s|%s" % (cid, iso(now)), head, body, False, cid, now)
        else:
            cs["fail_streak"] = 0
            if cs.get("fail_alerted"):
                cs["fail_alerted"] = False
                st["open"].pop("fail|" + cid, None)
                fs = clock.utc_epoch(cs.get("fail_since")) if cs.get("fail_since") else None
                if not r.extra.get("refused"):  # v-kwfalse: a site marked 'refuses' does not read again (its note)
                    queue(st, "clear|fail|%s|%s" % (cid, iso(now)), "Cleared: %s reads again" % label,
                          "%s reads again%s." % (label, (" (it could not from %s, about %s)" % (et(fs), mins(now - fs)))
                                                 if fs else ""), False, cid, now, "cleared")
    if first:
        lines = ["From now on a scan every %d minutes compares Kalshi, the index and the server with what it saw now, "
                 "and tells you what changed, old value beside new (urgent ones ring even in quiet hours). /watch "
                 "shows every check." % EVERY_MIN]
        for cid, label in CHECKS:
            cs = st["checks"].get(cid) or {}
            if cs.get("status") == "failed":
                lines.append("- %s: could not read yet (%s); it records its baseline at its first good read" % (
                    label, cs.get("detail")))
            else:
                lines.append("- %s: %s" % (label, cs.get("summary") or cs.get("detail") or "ok"))
        if at_base:
            lines.append("Open already at this first scan (/watch keeps them listed; each gets a 'cleared' note when it "
                         "ends):")
            for o in sorted(at_base, key=lambda o: not o["urgent"]):
                lines.append("- %s%s: %s" % ("URGENT: " if o["urgent"] else "", o["head"], o["body"]))
        queue(st, "baseline", "baseline set", "\n".join(lines), any(o["urgent"] for o in at_base), "watch", now,
              "baseline")
    st["runs"] = int(st.get("runs") or 0) + 1
    st["last_scan"] = iso(now)
    st["last_scan_s"] = now
    return st


EMOJI = {"alert": "🔔", "urgent": "🚨", "cleared": "✅", "baseline": "📸", "test": "🧪"}


def _emoji(o):
    return EMOJI["urgent"] if o["urgent"] else EMOJI.get(o.get("kind"), EMOJI["alert"])


def _head(o, now):
    """The alert's head; one that waited in the outbox says when it was seen."""
    seen = clock.utc_epoch(o.get("t")) if o.get("t") else None
    return o["head"] + ((" (seen %s, sent late)" % et(seen)) if seen is not None and now - seen > 600 else "")


def render_msg(items, urgent, now):
    foot = "Scan of %s. /watch shows every check." % et(now)
    if len(items) == 1:
        o = items[0]
        return "%s KALSHI WATCH%s: %s\n%s\n\n%s" % (_emoji(o), " (urgent)" if urgent else "", _head(o, now), o["body"],
                                                   foot)
    lines = ["%s KALSHI WATCH%s: %d things to know" % (EMOJI["urgent"] if urgent else EMOJI["alert"],
                                                      " (urgent)" if urgent else "", len(items))]
    for i, o in enumerate(items, 1):
        lines += ["", "%d. %s %s" % (i, _emoji(o), _head(o, now)), o["body"]]
    lines += ["", foot]
    return "\n".join(lines)


def deliver(st, phone, now, log=None):
    """Send the outbox: each urgent alert alone (more than MAX_URGENT_EACH: one message), the rest as one message.
    What Telegram took leaves the outbox (its id into sent_ids, its head into history); the rest waits for the next
    scan. Items older than OUTBOX_MAX_AGE_S are dropped (logged)."""
    out = st.get("outbox") or []
    keep = []
    for o in out:
        te = clock.utc_epoch(o.get("t"))
        if te is not None and now - te > OUTBOX_MAX_AGE_S:
            if log:
                log("dropped an alert never sent in 2 days: %s" % o["id"])
            continue
        keep.append(o)
    out = keep
    urg = [o for o in out if o["urgent"]]
    rest = [o for o in out if not o["urgent"]]
    msgs = [([o], True) for o in urg] if len(urg) <= MAX_URGENT_EACH else [(urg, True)]
    if rest:
        msgs.append((rest, False))
    sent = set()
    for items, urgent in msgs:
        if phone.send(render_msg(items, urgent, now), urgent, now):
            sent |= {o["id"] for o in items}
            for o in items:
                st["history"].append({"t": iso(now), "head": o["head"], "urgent": o["urgent"], "check": o.get("check"),
                                      "kind": o.get("kind")})
    st["outbox"] = [o for o in out if o["id"] not in sent]
    st["sent_ids"] = (st.get("sent_ids") or []) + sorted(sent)
    st["sent_ids"] = st["sent_ids"][-KEEP_SENT:]
    st["history"] = st["history"][-KEEP_HISTORY:]
    return len(sent)


def load_state(path):
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else new_state()
    except (OSError, ValueError):
        return new_state()


def save_state(st, path, tries=SAVE_TRIES, sleep=time.sleep, replace=None):
    """Write the state atomically (a .tmp, then os.replace). Retried `tries` times, 0.5 s more each time: on Windows
    the replace fails while another process (the phone's /watch) has the file open. Raises the last error."""
    data = json.dumps(st, indent=1, sort_keys=True, default=str)
    replace = replace or os.replace
    tmp = path + ".tmp"
    last = None
    for i in range(max(1, tries)):
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(data)
            replace(tmp, path)
            return i + 1
        except OSError as e:
            last = e
            if i + 1 < tries:
                sleep(0.5 * (i + 1))
    raise last


def run(env, phone, now=None, dry=False, state_path=None):
    """One scan. The state is saved before the messages go (a send that breaks keeps the scan's new baselines; its
    messages wait in the outbox) and again after (what Telegram took leaves the outbox)."""
    now = time.time() if now is None else now
    sp = state_path or env.path(STATE_NAME)
    st = load_state(sp)
    scan(env, st, now)
    if not dry:
        save_state(st, sp, sleep=env.sleep)
    n = deliver(st, phone, now, env.log)
    o = st["open"]
    env.log("scan %d ok: %s; %d open; %d sent, %d waiting; %s signed reads" % (
        st["runs"], ", ".join("%s %s" % (c, (st["checks"].get(c) or {}).get("status")) for c, _l in CHECKS), len(o), n,
        len(st["outbox"]), st.get("api_calls_last_scan")))
    if not dry:
        save_state(st, sp, sleep=env.sleep)
    return st


def crash_note(env, phone, now, what):
    """A scan that crashed: one quiet phone message an ET day. The day is written to results\\kalshi_watch.crash FIRST:
    when even that cannot be written (a full disk) nothing is sent, rather than a message every 30 minutes."""
    day = clock.et_day(now)
    p = env.path(CRASH_NAME)
    try:
        with open(p, encoding="utf-8") as fh:
            if fh.read().strip() == day:
                return False
    except OSError:
        pass
    try:
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(day + "\n")
    except OSError:
        env.log("crash note not sent: results\\%s cannot be written either" % CRASH_NAME)
        return False
    ok = False
    try:
        ok = phone.send("%s KALSHI WATCH: its scan crashed (%s) at %s. What it found this scan may not be saved; it "
                        "tries again in %d minutes. results\\%s has the lines. (Said once a day.)" % (
                            EMOJI["alert"], what, et(now), EVERY_MIN, LOG_NAME), False, now)
    finally:
        if not ok:                              # not sent: the next crash tries again
            try:
                os.remove(p)
            except OSError:
                pass
    return ok


# ---------------------------------------------------------------------------- the self-test
RSS_HEAD = ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" '
            'xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>'
            '<title><![CDATA[Kalshi API Changelog]]></title>')


def _anchor(date):
    """The changelog RSS link's anchor for a day: '2026-11-12' -> 'november-12-2026'; 'TBD' -> 'tbd'."""
    if date == "TBD":
        return "tbd"
    tm = time.strptime(date, "%Y-%m-%d")
    return "%s-%d-%d" % (time.strftime("%B", tm).lower(), tm.tm_mday, tm.tm_year)


def _rss(entries):
    """entries: (date, title, text[, categories[, posted]]), `code` in text: the RSS as Kalshi's Mintlify writes it
    (title, summary, link to the day's anchor, guid, categories, pubDate, the full text as HTML)."""
    out = [RSS_HEAD]
    for en in entries:
        date, title, text = en[:3]
        cats = en[3] if len(en) > 3 else ("REST", "Predictions")
        posted = en[4] if len(en) > 4 else (date if date != "TBD" else "2026-11-01")
        html_text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        out.append("<item><title><![CDATA[%s]]></title><description><![CDATA[%s]]></description>"
                   "<link>https://docs.kalshi.com/changelog#%s</link><guid isPermaLink=\"false\">%s</guid>%s"
                   "<pubDate>%s</pubDate><content:encoded><![CDATA[<p>%s</p>]]></content:encoded></item>" % (
                       title, text.replace("`", "")[:90], _anchor(date), sha256(title)[:16],
                       "".join("<category><![CDATA[%s]]></category>" % c for c in cats),
                       time.strftime("%a, %d %b %Y 18:45:46 GMT", time.strptime(posted, "%Y-%m-%d")), html_text))
    out.append("</channel></rss>")
    return "".join(out).encode("utf-8")


def _md(entries, old=False):
    """changelog.md as Kalshi writes it since autumn 2026 ("**November 20, 2026**" and the text), or (old) the
    <Update> blocks it had before."""
    out = ["# API Changelog\n\n> Stay updated with API changes and version history\n"]
    for en in entries:
        date, title, text = en[:3]
        if old:
            tm = time.strptime(date, "%Y-%m-%d")
            out.append('<Update\n  label="%s %d, %d"\n  tags={["REST"]}\n  rss={{\n    title: "%s",\n    description: '
                       '"x"\n  }}\n>\n  %s\n</Update>\n' % (time.strftime("%B", tm), tm.tm_mday, tm.tm_year, title,
                                                            text))
            continue
        if date == "TBD":
            lab = "TBD"
        else:
            tm = time.strptime(date, "%Y-%m-%d")
            lab = "%s %d, %d" % (time.strftime("%B", tm), tm.tm_mday, tm.tm_year)
        out.append("**%s**\n\n%s\n" % (lab, text))
    return "\n".join(out).encode("utf-8")


CL_A = [("2026-10-01", "Market tick_size field removed", "The `tick_size` field leaves market responses."),
        ("2026-11-05", "Historical markets support series_ticker filtering", "GET /historical/markets filters."),
        ("2026-11-20", "Event candlesticks endpoint", "A new read for event candlesticks.")]
CL_B = CL_A + [("2026-11-09", "fee_multiplier changes for crypto series", "Crypto series fees move."),
               ("2026-11-08", "Events accept a series ticker filter", "GET /events gains a filter."),
               ("2026-11-08", "New feed for market lifecycle messages", "A lifecycle feed.")]

# four entries of the real feed (docs.kalshi.com/changelog/rss.xml, read once on 11-07) and the same four in the real
# changelog.md: the formats the first real scan will meet (a Predictions entry, a Margin-only one, a TBD FIX/Margin one,
# a Predictions entry naming 'subaccount')
REAL_RSS = (
    '<?xml version="1.0" encoding="UTF-8"?><rss xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom" version="2.0">'
    '<channel><title><![CDATA[API Changelog]]></title><link>https://docs.kalshi.com</link>'
    '<generator>Mintlify</generator>'
    '<item><title><![CDATA[API key signing algorithm metadata]]></title><description><![CDATA[GET /api_keys includes '
    'key_type for RSA and Ed25519 keys.]]></description><link>https://docs.kalshi.com/changelog#november-12-2026</link>'
    '<guid isPermaLink="false">dec4dee21d01018a</guid><category><![CDATA[REST]]></category><category><![CDATA['
    'Predictions]]></category><pubDate>Fri, 06 Nov 2026 18:45:46 GMT</pubDate><content:encoded><![CDATA[<p><code>GET '
    '/api_keys</code> now includes <code>key_type</code> (<code>rsa</code> or <code>ed25519</code>) on each supported '
    'key, including keys created before this change. The field is omitted when the algorithm is unknown.</p>]]>'
    '</content:encoded></item>'
    '<item><title><![CDATA[MCP portfolio access for perps]]></title><description><![CDATA[read::mcp_portfolio OAuth '
    'grants can read margin balances, positions, orders, fills and risk.]]></description><link>https://docs.kalshi.com'
    '/changelog#november-12-2026</link><guid isPermaLink="false">1568eb488b2528bb</guid><category><![CDATA[REST]]>'
    '</category><category><![CDATA[Margin]]></category><pubDate>Fri, 06 Nov 2026 01:31:11 GMT</pubDate>'
    '<content:encoded><![CDATA[<p>Registered MCP clients can read margin balances, positions, orders, fills and risk '
    '(<code>GET /margin/balance</code>, <code>/margin/positions</code>, <code>/margin/orders</code>, <code>/margin/fills'
    '</code>, <code>/margin/risk</code>) using explicitly granted <code>read::mcp_portfolio</code> OAuth access.</p>]]>'
    '</content:encoded></item>'
    '<item><title><![CDATA[Equities orders need an approved stocks application]]></title><description><![CDATA['
    'Kalshi-cleared users without an approved stocks application get stock_perps_application_required on Equities '
    'orders and amends that could grow a position.]]></description><link>https://docs.kalshi.com/changelog#tbd</link>'
    '<guid isPermaLink="false">78e553d0f2614e53</guid><category><![CDATA[REST]]></category><category><![CDATA[FIX]]>'
    '</category><category><![CDATA[Margin]]></category><pubDate>Wed, 04 Nov 2026 23:28:08 GMT</pubDate>'
    '<content:encoded><![CDATA[<p>Kalshi-cleared users need an approved stocks application to trade Equities\n'
    'markets. Without one, an order or amend on an Equities market is rejected\nwith <code>'
    'stock_perps_application_required</code>, unless the order is reduce-only.</p>]]></content:encoded></item>'
    '<item><title><![CDATA[Market positions include netting_enabled]]></title><description><![CDATA[Market positions '
    'now include netting_enabled, showing whether netting applies to the position\'s event.]]></description><link>'
    'https://docs.kalshi.com/changelog#november-5-2026</link><guid isPermaLink="false">c965e41f656cdd45</guid>'
    '<category><![CDATA[REST]]></category><category><![CDATA[Predictions]]></category><pubDate>Tue, 03 Nov 2026 '
    '16:34:56 GMT</pubDate><content:encoded><![CDATA[<p>Market positions from <code>GET /portfolio/positions</code>, '
    '<code>GET /historical/positions</code>\nand <code>GET /fcm/positions</code> now include <code>netting_enabled'
    '</code>, showing whether\nnetting applies to the position\'s event. It is fixed at the subaccount\'s\nfirst order '
    'in the event.</p>]]></content:encoded></item></channel></rss>')
REAL_MD = (
    "> ## Documentation Index\n> Fetch the complete documentation index at: https://docs.kalshi.com/llms.txt\n\n"
    "# API Changelog\n\n> Stay updated with API changes and version history\n\nUse the entry tags to filter by API\n"
    "surface (`REST`, `WebSocket`, `FIX`) or exchange (`Predictions`, `Margin`).\n\n"
    "**November 12, 2026**\n\n`GET /api_keys` now includes `key_type` (`rsa` or `ed25519`) on each supported key, "
    "including keys created before this change. The field is omitted when the algorithm is unknown.\n\n"
    "**November 12, 2026**\n\nRegistered MCP clients can read margin balances, positions, orders, fills and risk "
    "(`GET /margin/balance`, `/margin/positions`, `/margin/orders`, `/margin/fills`, `/margin/risk`) using explicitly "
    "granted `read::mcp_portfolio` OAuth access.\n\n"
    "**TBD**\n\nKalshi-cleared users need an approved stocks application to trade Equities\nmarkets. Without one, an "
    "order or amend on an Equities market is rejected\nwith `stock_perps_application_required`, unless the order is "
    "reduce-only.\n\n"
    "**November 5, 2026**\n\nMarket positions from `GET /portfolio/positions`, `GET /historical/positions`\nand "
    "`GET /fcm/positions` now include `netting_enabled`, showing whether\nnetting applies to the position's event. It "
    "is fixed at the subaccount's\nfirst order in the event.\n\n"
    "**Affected endpoints:**\n\n* `GET /portfolio/positions`\n\n"
    "**October 22, 2026**\n\nAdded support for cache-specific Redis authentication and verified TLS for WebSocket "
    "session and request limits.\n\n")

# a live hedge record from the real 10-31 log (0925r): an off-grid hedge Kalshi refused (limit 0.115), before pin wrote
# status_code on its hedge records (v-hedgetick, 0925t 11-04)
REAL_HEDGE_1031 = {"kind": "hedge", "ticker": "KXHYPE15M-26OCT310730-30", "side": "no", "price": 0.115, "n": 0.0,
                   "limit_sent": 0.115, "asked": 20.98, "order_id": None, "status": None, "live": True,
                   "t": "2026-10-31T11:29:19Z"}
# ...and one from the 11-07 log (0925u): a hedge that filled, its status_code written
REAL_HEDGE_1107 = {"kind": "hedge", "ticker": "KXBNB15M-26NOV070815-15", "side": "yes", "n": 193.81, "asked": 193.81,
                   "limit_sent": 0.8, "order_id": "01a1b625-8e48-787a-b60d-c268e341da96", "status": "executed",
                   "status_code": 201, "err": None, "live": True, "t": "2026-11-07T13:14:37Z"}


class _World:
    """A Kalshi, a docs site, a status page, a server and a pin log in which the answers are known."""

    def __init__(self, td):
        self.td = td
        self.results = os.path.join(td, "results")
        self.repo = os.path.join(td, "repo")
        os.makedirs(self.results)
        os.makedirs(self.repo)
        self.v = "A"
        self.cl = CL_A
        self.cl_src = "rss"
        self.net_down = False
        self.web_down = set()
        self.http = {}                      # path -> status planted
        self.t = 1000.0                     # the monotonic clock
        self.roll = 0                       # each scan the open markets are new ones (new tickers, strikes, times)
        self.calls = []
        self.fetches = []
        self.disk_gb = 40.0
        self.versions = {"certifi": "2026.7.22", "cryptography": "50.0.0", "numpy": "2.5.4", "requests": "2.34.2",
                         "urllib3": "2.7.0", "websockets": "17.0.1"}
        self.pdf = {CONTRACT_PDF: b"%PDF-1.7 crypto15m terms v1", CFB_PDF: b"%PDF-1.4 constituents v1"}
        self.incidents = [{"id": "inc1", "name": "BRTI delayed", "status": "resolved", "impact": "minor",
                           "created_at": "2026-11-01T10:00:00Z", "incident_updates": [{"body": "Resolved."}]}]
        self.cfb_src = "json"
        self.paused = False                 # exchange status: trading_active false
        self.extra_windows = []
        self.pin_cur = "pinrun-live-20261107T120000Z.jsonl"
        self.pin_alive = True               # pin writes a market list with markets a minute before each scan

    def mono(self):
        return self.t

    def sleep(self, s):
        self.t += max(0.0, s)

    def market(self, s, i):
        k = self.roll
        hh, mm = 15 + (k // 4) % 8, 15 * (k % 4)
        close = "26NOV07%02d%02d" % (hh, mm)
        strike = 84000.5 + i + 37.25 * k
        m = {"ticker": "%s-%s-%02d" % (s, close, mm), "event_ticker": "%s-%s" % (s, close), "status": "active",
             "price_level_structure": "tapered_deci_cent" if s != "KXBTCD" else "linear_cent",
             "price_ranges": [{"start": "0.0000", "end": "0.1000", "step": "0.0010"}],
             "settlement_timer_seconds": 1, "exchange_index": 2, "floor_strike": strike,
             "custom_strike": {"round_digits": "2"}, "yes_ask_dollars": "0.%02d00" % (50 + i + k % 9),
             "rules_primary": "If the simple average of the sixty seconds of CF Benchmarks' RTI before %d:%02d PM EST on "
                              "Nov 7, 2026 is at least %s, then the market resolves to Yes." % (
                                  hh - 12, mm, "{:,.2f}".format(strike))}
        if self.v == "B":
            if s == "KXETH15M":
                m["price_level_structure"] = "linear_cent"
            if s == "KXSOL15M":
                m["rules_primary"] = m["rules_primary"].replace("sixty", "thirty")
            if s == "KXXRP15M":
                m["fee_hint"] = "x"
                m.pop("floor_strike")
            if s == "KXDOGE15M":
                m["exchange_index"] = 3
            if s == "KXBNB15M":
                m["settlement_timer_seconds"] = 60
        if self.v == "C" and s == "KXBTC15M":
            m["price_ranges"] = [{"start": "0.0000", "end": "1.0000", "step": "0.0100"}]
        return m

    def series(self, s):
        B, C = self.v == "B", self.v == "C"
        return {"ticker": s, "frequency": "fifteen_min", "title": "x", "fee_type": "quadratic",
                "fee_multiplier": 2 if (B and s == "KXHYPE15M") else 1,
                "settlement_sources": [{"name": "CF Benchmarks", "url": "https://www.cfbenchmarks.com/new" if (
                    C and s == "KXETH15M") else "https://cfbenchmarks.com"}],
                "contract_url": "https://kalshi.com/c2.pdf" if (C and s == "KXSOL15M") else "https://kalshi.com/c.pdf",
                "contract_terms_url": CONTRACT_PDF.replace(".pdf", "_v2.pdf") if (C and s == "KXXRP15M") else CONTRACT_PDF,
                "tags": ["crypto"], "product_metadata": {"important_info": {"markdown": "m"}}}

    def get(self, path, params=None):
        self.t += 0.2
        self.calls.append((path, dict(params or {}), self.t))
        if self.net_down:
            return -1, "URLError: no route"
        if path in self.http:
            return self.http[path], {"error": {"code": "planted"}}
        p = params or {}
        B = self.v == "B"
        if path == "/exchange/status":
            return 200, {"exchange_active": True, "trading_active": not (B or self.paused)}
        if path == "/series/fee_changes":
            arr = [{"id": "f0", "series_ticker": "KXMLBGAME", "fee_type": "quadratic", "fee_multiplier": 3,
                    "scheduled_ts": "2026-12-01T05:00:00Z"},
                   {"id": "f1", "series_ticker": "KXBTC15M", "fee_type": "quadratic", "fee_multiplier": 1,
                    "scheduled_ts": "2026-08-01T04:00:00Z"}]
            if B:
                arr.append({"id": "f2", "series_ticker": "KXBTC15M", "fee_type": "quadratic", "fee_multiplier": 2,
                            "scheduled_ts": "2026-11-12T05:00:00Z"})
            return 200, {"series_fee_change_arr": arr}
        if path == "/markets":
            s = p.get("series_ticker")
            if s == "KXZEC15M" and self.v == "A2":
                return 200, {"markets": [], "cursor": ""}
            return 200, {"markets": [self.market(s, i) for i in range(2)], "cursor": "abc%d" % self.roll}
        if path == "/exchange/schedule":
            w = [{"start_datetime": "2026-11-12T08:00:00Z", "end_datetime": "2026-11-12T10:00:00Z"},    # the usual
                 {"start_datetime": "2026-11-10T14:00:00Z", "end_datetime": "2026-11-10T16:00:00Z"}] if B else []
            return 200, {"schedule": {"standard_hours": [{"monday": []}], "maintenance_windows": w + self.extra_windows}}
        if path == "/portfolio/balance":
            b = {"balance": 345678, "portfolio_value": 12345, "updated_ts": 1}
            if B:
                b = {"balance": 999999, "portfolio_value": 1, "updated_ts": 2, "balance_dollars": "9999.99"}
            return 200, b
        if path.startswith("/series/"):
            return 200, {"series": self.series(path.rsplit("/", 1)[-1])}
        return 404, "404 page not found"

    def fetch(self, url, timeout=None, cap=None):
        self.fetches.append(url)
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        if host in API_HOSTS:
            raise Refused(host)
        if self.net_down or url in self.web_down or any(url.startswith(w) for w in self.web_down):
            return -1, b"URLError: no route", {}
        if url == CHANGELOG_URLS[0]:
            if self.cl_src == "real":
                return 200, REAL_RSS.encode("utf-8"), {}
            return (200, _rss(self.cl), {}) if self.cl_src == "rss" else (404, b"", {})
        if url == CHANGELOG_URLS[1]:
            return (200, _md(self.cl), {}) if self.cl_src in ("md", "rss") else (404, b"", {})
        if url == CHANGELOG_URLS[2]:
            if self.cl_src == "html":
                return 200, (b'<html><head><link rel="alternate" type="application/rss+xml" '
                             b'href="/changelog/feed.xml"></head><body>x</body></html>'), {}
            return 404, b"", {}
        if url == "https://docs.kalshi.com/changelog/feed.xml":
            return 200, _rss(self.cl), {}
        if url in self.pdf:
            return 200, self.pdf[url], {"last-modified": "Fri, 06 Nov 2026 10:00:00 GMT"}
        if url == CFB_STATUS_URLS[0] and self.cfb_src == "json":
            return 200, json.dumps({"incidents": self.incidents}).encode(), {}
        if url == CFB_STATUS_URLS[1] and self.cfb_src == "rss":
            return 200, _cfb_rss(self.incidents), {}
        return 404, b"", {}

    def disk_free(self):
        return self.disk_gb * 1e9

    def version_of(self, name):
        return self.versions.get(name)

    def env(self):
        return Env(results=self.results, repo=self.repo, get=self.get, fetch=self.fetch, sleep=self.sleep,
                   mono=self.mono, disk_free=self.disk_free, version_of=self.version_of, log_path="")

    def tick(self, now):
        self.roll += 1
        if self.pin_alive:
            self.pin_append(self.pin_cur, [{"kind": "universe", "got": 9, "n": 9, "t": iso(now - 60)}])

    def pin_append(self, name, recs, tail=""):
        with open(os.path.join(self.results, name), "a", encoding="utf-8", newline="\n") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")
            fh.write(tail)


def _cfb_rss(incs):
    """Statuspage's history.rss for these incidents (the status page's fallback feed)."""
    out = ['<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>CF Benchmarks Status - Incident '
           'History</title>']
    for x in incs:
        tm = time.gmtime(clock.utc_epoch(x["created_at"]))
        st = "Resolved" if x["status"] == "resolved" else "Investigating"
        out.append("<item><title>%s</title><description>&lt;p&gt;&lt;small&gt;%s&lt;/small&gt;&lt;br&gt;&lt;strong&gt;"
                   "%s&lt;/strong&gt; - %s&lt;/p&gt;</description><pubDate>%s</pubDate><link>https://status."
                   "cfbenchmarks.com/incidents/%s</link><guid>https://status.cfbenchmarks.com/incidents/%s</guid></item>"
                   % (x["name"], time.strftime("%b %d, %H:%M UTC", tm), st, x["incident_updates"][0]["body"],
                      time.strftime("%a, %d %b %Y %H:%M:%S +0000", tm), x["id"], x["id"]))
    out.append("</channel></rss>")
    return "".join(out).encode("utf-8")


class _FakePhone:
    def __init__(self):
        self.sent = []
        self.ok = True
        self.boom = False

    def send(self, text, urgent, now):
        if self.boom:
            raise RuntimeError("planted: the phone broke")
        if not self.ok:
            return False
        self.sent.append((text, urgent))
        return True


def self_test(verbose=True, installer=True, logs=()):
    """Every check on _World's fixtures. installer False (the quiet run before each real scan): the installer file is
    not read, so a missing installer never stops the scans. logs: pin's real logs, replayed through check_pin_log."""
    fails = []
    out = sys.stdout if verbose else io.StringIO()

    def ck(cond, what):
        print("  [%s] %s" % ("ok" if cond else "FAIL", what), file=out)
        if not cond:
            fails.append(what)

    print("kalshi_watch --self-test", file=out)
    real_urlopen = urllib.request.urlopen

    def no_net(*a, **k):
        raise AssertionError("the self-test opened a URL")
    urllib.request.urlopen = no_net
    kauth_before = "kauth" in sys.modules
    td = tempfile.mkdtemp(prefix="kwatch_")
    try:
        for part in (_self_test_body, _self_test_changelog, _self_test_pin, _self_test_false_alarms, _self_test_server,
                     _self_test_main):
            try:
                with contextlib.redirect_stdout(out if verbose else io.StringIO()):
                    part(ck, os.path.join(td, part.__name__), out, installer)
            except Exception:                                   # noqa: BLE001
                fails.append("%s raised" % part.__name__)
                print(traceback.format_exc(), file=out)
        for i, lp in enumerate(logs or ()):
            try:
                _self_test_real_log(ck, os.path.join(td, "real_%d" % i), out, lp)
            except Exception:                                   # noqa: BLE001
                fails.append("the real-log replay of %s raised" % lp)
                print(traceback.format_exc(), file=out)
    finally:
        urllib.request.urlopen = real_urlopen
        shutil.rmtree(td, ignore_errors=True)
    ck(kauth_before or "kauth" not in sys.modules, "the key was never loaded (kauth not imported)")
    print("SELF-TEST %s (%d failure%s)" % ("PASSED" if not fails else "FAILED", len(fails),
                                           "" if len(fails) == 1 else "s"), file=out)
    return not fails


T_SAT = float(calendar.timegm((2026, 11, 7, 20, 30, 0)))          # Sat Nov 7 3:30 PM ET


def _world_files(W):
    """The planted server: pin's log (with warning records from before the watch starts: none may be said one by
    one at the baseline), the pinned list, two launchers and their snapshot list."""
    W.pin_append(W.pin_cur, [{"kind": "start", "t": "2026-11-07T12:00:00Z"},
                             {"kind": "clock_skew", "skew_s": 2.4, "t": "2026-11-07T13:10:00Z"},
                             {"kind": "entries_blocked", "reason": "guard_error", "parts": ["clockskew"],
                              "blocks": "new entries only", "t": "2026-11-07T13:20:00Z"},
                             {"kind": "entries_resumed", "reason": "guard_error", "t": "2026-11-07T13:20:06Z"}] +
                 [dict(REAL_HEDGE_1031, t="2026-11-07T13:3%d:00Z" % i) for i in range(8)] +
                 [{"kind": "hedge_broken", "ticker": "KXETH15M-26NOV070945-45", "n": 50.0,
                   "t": "2026-11-07T14:30:00Z"},
                  {"kind": "universe", "got": 9, "n": 9, "t": "2026-11-07T20:29:00Z"}])
    with open(os.path.join(W.results, REQS_NAME), "w", encoding="utf-8") as fh:
        fh.write("# server pins\ncertifi==2026.7.22\ncryptography==50.0.0\nnumpy==2.5.4\nrequests==2.34.2\n"
                 "urllib3==2.7.0\nwebsockets 17.0.1\n")
    for name, body in (("restart_bot.ps1", b"param()\r\n# launcher\r\n"), ("boot_all.ps1", b"# boot\r\n")):
        with open(os.path.join(W.repo, name), "wb") as fh:
            fh.write(body)
    os.makedirs(os.path.join(W.results, "live_launcher_snapshot"))
    with open(os.path.join(W.results, SUMS_REL), "w", encoding="utf-8") as fh:
        fh.write("%s  restart_bot.ps1\n%s *boot_all.ps1\n" % (sha256(b"param()\r\n# launcher\r\n"),
                                                               sha256(b"# boot\r\n")))


def _plant_b(W, T1):
    """The planted world: every kind of change at once."""
    W.v, W.cl, W.cl_src = "B", CL_B, "rss"
    W.pdf[CONTRACT_PDF] = b"%PDF-1.7 crypto15m terms v2 (new paragraph)"
    W.pdf[CFB_PDF] = b"%PDF-1.4 constituents v2"
    W.incidents = [{"id": "inc2", "name": "ETHUSD_RTI publication delayed", "status": "investigating",
                    "created_at": "2026-11-07T21:50:00Z", "incident_updates": [{"body": "Investigating."}]},
                   {"id": "inc3", "name": "Website maintenance", "status": "resolved",
                    "created_at": "2026-11-07T21:00:00Z", "incident_updates": [{"body": "Resolved."}]},
                   {"id": "inc4", "name": "CALCULATION FAILURE of CME CF Bitcoin Volatility Index - Real Time",
                    "status": "investigating", "created_at": "2026-11-07T21:40:00Z",
                    "incident_updates": [{"body": "Investigating."}]}] + W.incidents
    W.disk_gb = 12.0
    W.versions["certifi"] = "2026.10.1"
    with open(os.path.join(W.repo, "restart_bot.ps1"), "ab") as fh:
        fh.write(b"# edited\r\n")
    W.pin_alive = False
    W.pin_append(W.pin_cur, [{"kind": "universe", "got": 9, "t": iso(T1 - 960)},
                             {"kind": "universe", "got": 0, "t": iso(T1 - 300)},
                             {"kind": "hedge_broken", "ticker": "KXZEC15M-26NOV071615-15", "close_s": T1 - 900,
                              "side": "yes", "n": 120.0, "err": "no depth", "t": iso(T1 - 950)},
                             {"kind": "hedge_broken", "ticker": "KXZEC15M-26NOV071615-15", "side": "yes", "n": 120.0,
                              "t": iso(T1 - 949)},
                             {"kind": "clock_skew", "skew_s": 2.4, "t": iso(T1 - 940)}] +
                 [{"kind": "hedge", "ticker": "KXSOL15M-26NOV071615-15", "close_s": T1 - 900, "status_code": 400,
                   "err": "invalid price", "order_id": None, "live": True, "t": iso(T1 - 1000 + i)}
                  for i in range(6)] +
                 [{"kind": "hedge", "ticker": "KXSOL15M-26NOV071615-15", "status_code": 201, "t": iso(T1 - 990)}],
                 tail='{"kind": "hedge_broken", "t": "%s", "ticker": "KXBTC15M-HALF' % iso(T1 - 10))


def demo_state(td):
    """A real state file's content from the fixtures (the phone's /watch tests read it): the baseline scan, a null scan
    and the planted world's two scans. Nothing leaves `td`."""
    W = _World(td)
    _world_files(W)
    env, ph, st = W.env(), _FakePhone(), new_state()
    for i, now in enumerate((T_SAT, T_SAT + 1800, T_SAT + 9000, T_SAT + 10800)):
        if i == 2:
            _plant_b(W, now)
        W.tick(now)
        scan(env, st, now)
        deliver(st, ph, now)
    return st, ph


def _stepper(W, env, st, ph):
    def one(now, **kw):
        n0 = len(ph.sent)
        W.calls.clear()
        W.tick(now)
        scan(env, st, now, **kw)
        deliver(st, ph, now)
        return ph.sent[n0:]
    return one


def _self_test_body(ck, td, out, installer=True):
    T0 = T_SAT
    W = _World(td)
    env = W.env()
    ph = _FakePhone()
    _world_files(W)
    st = new_state()
    one = _stepper(W, env, st, ph)

    # --- the pure pieces
    a, b = maint_window(float(calendar.timegm((2026, 11, 12, 8, 30, 0))))
    ck(a == calendar.timegm((2026, 11, 12, 8, 0, 0)) and b - a == 7200, "maintenance: Thu Nov 12 3-5 AM ET is 08-10Z")
    a, _b = maint_window(float(calendar.timegm((2026, 10, 29, 7, 30, 0))))
    ck(a == calendar.timegm((2026, 10, 29, 7, 0, 0)), "maintenance: Thu Oct 29 3 AM ET is 07Z (daylight time)")
    a, _b = maint_window(T0)
    ck(a == calendar.timegm((2026, 11, 5, 8, 0, 0)), "maintenance: on a Saturday the week's stretch is Thursday's")
    for url in ("https://api.elections.kalshi.com/trade-api/v2/markets", "https://api.elections.kalshi.com/v1/x",
                "https://example.com/trade-api/v2/portfolio/balance"):
        try:
            web_fetch(url)
            ck(False, "web_fetch refuses %s" % url)
        except Refused:
            ck(True, "web_fetch refuses %s (unsigned calls would spend the public budget)" % url)
    store, rr = {}, Result()
    for ks in ({"a", "m", "m[].x", "m[].y"}, {"a", "m", "m[].x"}):          # the baseline, then y missing once
        compare_keys(store, ks, "EP", rr, "t", at_once=1)
    n1 = len(rr.alerts)
    compare_keys(store, {"a", "m", "m[].x"}, "EP", rr, "t", at_once=1)        # missing twice: said, URGENT
    n2 = len(rr.alerts)
    for ks in ({"a", "m", "m[].x", "m[].y"}, {"a", "m", "m[].x"}, {"a", "m", "m[].x"}):   # back, then gone twice more
        compare_keys(store, ks, "EP", rr, "t", at_once=1)
    ck(n1 == 0 and n2 == 1 and rr.alerts[0]["urgent"] and len(rr.alerts) == 2 and not rr.alerts[1]["urgent"],
       "keys: a market field missing once says nothing, twice URGENT; back = said once; gone again = flaky, quiet")
    compare_keys(store, {"a"}, "EP", rr, "t", at_once=1)
    ck(len(rr.alerts) == 3 and rr.alerts[2]["urgent"] and "m" in rr.alerts[2]["body"], "keys: a top-level key gone: at once")
    s2_, r2_ = {}, Result()
    for ks in ({"w"}, {"w", "w[].s", "w[].e"}, {"w"}):
        compare_keys(s2_, ks, "EP", r2_, "u")
    ck(r2_.alerts == [], "keys: an empty list that gains items, then empties again, is no field change")
    s3_, r3_ = {}, Result()
    for ks in ({"a", "b"}, {"a", "b", "c"}, {"a", "b"}):
        compare_keys(s3_, ks, "EP", r3_, "v")
    ck(len(r3_.alerts) == 2 and not r3_.alerts[1]["urgent"] and "came later" in r3_.alerts[1]["body"],
       "keys: a field that came after the baseline and went again is said, not urgent")
    rq = read_reqs(os.path.join(W.results, REQS_NAME))
    ck(rq and len(rq) == 6 and rq["websockets"] == ("websockets", "==", "17.0.1"),
       "the pinned list reads 'name==version' and 'name version' lines")
    # --- scan 1: the baseline (pin's log already holds warning records, a finished block and 8 refusals: from before
    # the watch, so none of them is said one by one)
    s1 = one(T0)
    ck(len(s1) == 1 and "baseline set" in s1[0][0] and not s1[0][1], "scan 1: ONE message, the baseline note (quiet)")
    txt = s1[0][0] if s1 else ""
    for want in ("Kalshi API changelog: 3 entries recorded", "20 of 20 signed reads ok", "quadratic x 1",
                 "contract terms (PDF): recorded", "40.0 GB free", "6 of 6 match the pinned list",
                 "2 of 2 match the snapshot", "0 not resolved",
                 "hold 2 warning records from before the watch started (not said one by one: clock_skew x1, "
                 "hedge_broken x1)"):
        ck(want in txt, "baseline note says: %s" % want)
    ck(all(c["status"] == "ok" for c in st["checks"].values()) and len(st["checks"]) == len(CHECKS),
       "scan 1: every check ok (%s)" % {k: v["status"] for k, v in st["checks"].items()})
    gaps = [y[2] - x[2] for x, y in zip(W.calls, W.calls[1:])]
    ck(len(W.calls) == 20 and min(gaps) >= 1.0 - 1e-9,
       "signed reads: 20 a scan, each at least 1 s after the one before (smallest gap %.2f s)" % min(gaps))
    ck(all(c[0].startswith("/") for c in W.calls), "every signed read is a path for kauth (never a full URL)")
    sg = Signed(env)
    got = [sg("/exchange/status") for _ in range(25)]
    ck(len(sg.calls) == 20 and got[19][0] == 200 and got[20] == (None, None),
       "Signed: a 21st read in one scan is never made")
    ck(canon(st).find("345678") < 0 and canon(st).find("12345") < 0, "the balance amount is never stored")
    ck(len(st["changelog_recent"]) == 3 and st["changelog_recent"][0]["date"] == "2026-11-20", "/watch's newest entries")
    # --- scans 2-3: the same world (its markets rolled to new tickers, strikes and times) -> nothing
    s2 = one(T0 + 1800)
    s3 = one(T0 + 3600)
    ck(s2 == [] and s3 == [], "NULL WORLD: the same world twice more, new markets each scan, says nothing (%s)"
       % [t[:60] for t, _ in s2 + s3])
    ck(len(st["base"]["kalshi_api"]["series"]) == len(SERIES), "every series answer is on file after 2 scans")
    # --- a harmless world: a series with no open market, the changelog read from changelog.md, then via the page's
    # RSS link, then from the RSS again
    W.v, W.cl_src = "A2", "md"
    s4 = one(T0 + 5400)
    W.cl_src = "html"
    s4 += one(T0 + 7200)
    ck(st["base"]["changelog"]["source"].endswith("/changelog"), "the page's RSS link was followed")
    W.cl_src = "rss"
    s4 += one(T0 + 8100)
    ck(s4 == [], "NULL WORLD: no open market on one series, the changelog from .md, via the page's RSS link, then the "
                 "RSS again: nothing (%s)" % [t[:80] for t, _ in s4])
    # --- the planted world (two scans, so both series rotations are read)
    T1 = T0 + 9000
    _plant_b(W, T1)
    s5 = one(T1)
    ck(not any("Kalshi removed 1 field from GET /markets (KXXRP15M open)" in t for t, _u in s5),
       "a market field missing on the first scan only: not said yet")
    s5 += one(T1 + 1800)
    allt = "\n\n".join(t for t, _u in s5)
    urg = [t for t, u in s5 if u]
    print("    planted world: %d messages, %d urgent" % (len(s5), len(urg)), file=out)
    want_urgent = [("fee_multiplier changes for crypto series", "changelog entry naming fee/crypto -> URGENT"),
                   ("Fee change scheduled on BTC 15-minute (KXBTC15M)", "a fee change scheduled on our series -> URGENT"),
                   ("fee multiplier 2, fee type quadratic (today: quadratic x 1)", "the new fee beside today's, in words"),
                   ("Kalshi changed price_level_structure on ETH 15-minute", "price steps changed -> URGENT"),
                   ("was tapered_deci_cent, now linear_cent", "price steps: old value beside the new"),
                   ("New settlement rules sentence on SOL 15-minute", "a new rules sentence -> URGENT"),
                   ("Kalshi removed 1 field from GET /markets (KXXRP15M open)", "a missing market key -> URGENT"),
                   ("Kalshi changed exchange_index on DOGE 15-minute (KXDOGE15M): was 2, now 3", "shard moved -> URGENT"),
                   ("settlement_timer_seconds on BNB 15-minute (KXBNB15M): was 1, now 60", "settle timer -> URGENT"),
                   ("fee_multiplier on HYPE 15-minute (KXHYPE15M): was 1, now 2", "series fee multiplier -> URGENT"),
                   ("Kalshi has paused trading outside its schedule", "trading paused off-schedule -> URGENT"),
                   ("contract terms (CRYPTO15M.pdf) changed", "contract PDF changed -> URGENT"),
                   ("CF Benchmarks incident: ETHUSD_RTI publication delayed",
                    "an unresolved CF incident naming one of pin's indices -> URGENT"),
                   ("Pin wrote 2 hedge_broken records", "pin alarm records -> URGENT, grouped"),
                   ("Pin wrote 1 clock_skew record", "a second alarm kind -> its own URGENT"),
                   ("Kalshi refused 6 of pin's hedge orders in an hour", "6 refused hedges in an hour -> URGENT"),
                   ("Pin has seen no markets for 16 minutes", "no market list for 16 min -> URGENT")]
    for w, what in want_urgent:
        ck(any(w in t for t in urg), what)
    want_quiet = [("Events accept a series ticker filter", "a plain changelog entry -> an alert, not urgent"),
                  ("New feed for market lifecycle messages", "'feed' is not 'fee' -> not urgent"),
                  ("Kalshi added 1 field to GET /markets (KXXRP15M open)", "a new key -> not urgent"),
                  ("balance_dollars", "a new balance key -> said"),
                  ("Kalshi scheduled maintenance from Nov 10 9:00 AM ET to Nov 10 11:00 AM ET", "an unusual window -> said"),
                  ("CF Benchmarks' list of the exchanges in its indices changed", "constituents PDF changed"),
                  ("was 24 bytes (sha256 ", "a PDF change says the old size and hash beside the new"),
                  ("CF Benchmarks incident: Website maintenance", "a resolved CF incident -> said, not urgent"),
                  ("CF Benchmarks incident: CALCULATION FAILURE of CME CF Bitcoin Volatility Index",
                   "an unresolved CF incident for an index pin does not settle on -> said, not urgent"),
                  ("Server disk C: is down to 12.0 GB free", "disk under 15 GB -> said"),
                  ("certifi is 2026.10.1", "a package off the pinned list -> said"),
                  ("results\\requirements-server.txt says exactly 2026.7.22", "...with the version the list wants"),
                  ("Live launcher restart_bot.ps1 is not the snapshot", "a launcher drift -> said")]
    quiet = "\n\n".join(t for t, u in s5 if not u)
    for w, what in want_quiet:
        ck(w in quiet, what)
    ck(not any("Events accept" in t or "New feed" in t or "Volatility" in t for t in urg),
       "the plain entries and the other index's incident are not in an urgent message")
    ck("It is dated Nov 9, 2026 (in 2 days)" in allt, "a changelog alert carries its date")
    ck("was 1, now 2" in allt and "1 / 2" not in allt, "old value beside the new, in words")
    ck("999999" not in allt and "9999.99" not in allt and "345678" not in allt, "the balance amount is never said")
    ck("KXBTC15M-HALF" not in allt, "a half-written last line of pin's log waits")
    ck(chr(0x2014) not in allt and chr(0x2013) not in allt, "no em dash (or en dash) in any message")
    ck(" GMT" not in allt and "UTC" not in allt and "True" not in allt and "False" not in allt,
       "times in ET only; no Python True/False in the words")
    ck("Nov 12 3:00 AM ET" not in allt, "the usual Thursday 3-5 AM ET maintenance window is not said")
    ck("GET /exchange/schedule" not in allt, "an empty list that gains an item is not 'new fields'")
    ck(all("KALSHI WATCH" in t for t, _u in s5), "every message says it is the Kalshi watch")
    ck(len(urg) >= 1 and all(t.count("\n") >= 2 for t in urg), "each urgent message has its plain-words body")
    # --- dedupe: the same planted world again says nothing new (the half line, now whole, is new)
    W.pin_append(W.pin_cur, [], tail=' more"}\n')
    s6 = one(T1 + 3600)
    t6 = "\n".join(t for t, _u in s6)
    ck(len([1 for t, u in s6 if u]) == 1 and "Pin wrote 1 hedge_broken record" in t6
       and "Cleared: Kalshi refused 6 of pin's hedge orders" in t6 and len(s6) == 2,
       "dedupe: the planted world again says only the half line, now whole, and that the refusals are over (%s)"
       % [t[:70] for t, _ in s6])
    s7 = one(T1 + 5400)
    ck(s7 == [], "dedupe: nothing is said twice (%s)" % [t[:70] for t, _ in s7])
    ck({"kalshi_paused", "disk_low", "pkg|certifi", "launcher|restart_bot.ps1", "pin_no_markets"} <= set(st["open"]),
       "the open conditions are listed for /watch (%s)" % sorted(st["open"]))
    # --- the conditions end: cleared notes, quiet
    W.v = "A"
    W.disk_gb = 7.0
    s8 = one(T1 + 7200)
    ck(any(u and "Server disk C: has only 7.0 GB free" in t for t, u in s8), "disk under 8 GB -> URGENT")
    W.disk_gb = 30.0
    W.versions["certifi"] = "2026.7.22"
    W.pin_alive = True
    s9 = one(T1 + 9000)
    t89 = "\n".join(t for t, _u in s8 + s9)
    for w in ("Cleared: Server disk C: is down", "Cleared: Server disk C: has only", "Cleared: Python package certifi",
              "Cleared: Pin has seen no markets", "Cleared: Kalshi has paused trading"):
        ck(w in t89, "cleared note: %s" % w)
    ck(not any(u and "Cleared" in t for t, u in s8 + s9) and any("Cleared" in t for t, u in s8 + s9 if not u),
       "cleared notes are quiet (the urgent messages then: the planted world going back) (%s)"
       % [t[:120] for t, u in s9 if u])
    ck("disk_low" not in st["open"] and "pkg|certifi" not in st["open"], "cleared conditions leave /watch's list")
    # --- maintenance and the stop flag: no market-list alarm
    Tm = float(calendar.timegm((2026, 11, 12, 8, 40, 0)))         # Thu Nov 12 3:40 AM ET
    m1 = maint_window(Tm)[1]
    pl = json.loads(canon(st["base"]["pin_log"]))
    rm = check_pin_log(env, dict(pl, last_universe_ok=Tm - 1800), Tm)
    ck("pin_no_markets" not in rm.opens and "maintenance" in rm.detail, "Thursday 3-5 AM ET: no market-list alarm")
    rm = check_pin_log(env, dict(pl, last_universe_ok=Tm - 1800), m1 + 300)
    ck("pin_no_markets" not in rm.opens, "5 minutes after the maintenance stretch: not silent yet (counted from 5 AM)")
    rm = check_pin_log(env, dict(pl, last_universe_ok=Tm - 1800), m1 + 700)
    ck("pin_no_markets" in rm.opens, "12 minutes after the stretch with no market list: the alarm")
    rm = check_pin_log(env, dict(pl, last_universe_ok=Tm - 3 * 86400, log_start=None), m1 + 700)
    ck("pin_no_markets" in rm.opens and "for 3 days" in rm.opens["pin_no_markets"]["head"],
       "a silence from before the stretch counts from its start, in days (%s)"
       % (rm.opens.get("pin_no_markets") or {}).get("head"))
    with open(os.path.join(W.results, PIN_STOP_NAME), "w", encoding="utf-8") as fh:
        fh.write("operator PAUSE")
    rm = check_pin_log(env, dict(pl, last_universe_ok=T1), T1 + 20000)
    ck("pin_no_markets" not in rm.opens and "stood down" in rm.detail, "pin stood down: no market-list alarm")
    os.remove(os.path.join(W.results, PIN_STOP_NAME))
    # --- a new pin run: the old log's last lines, then the new one from its start
    W.pin_append(W.pin_cur, [{"kind": "clock_skew", "skew_s": 3.0, "t": iso(T1 + 9100)}])
    W.pin_cur = "pinrun-live-20261108T000000Z.jsonl"
    W.pin_append(W.pin_cur, [{"kind": "start", "t": iso(T1 + 9200)},
                             {"kind": "unbooked", "what": "provisional", "ticker": "KXETH15M-26NOV072000-00", "n": 5,
                              "t": iso(T1 + 9300)}])
    s10 = one(T1 + 10800)
    t10 = "\n".join(t for t, _u in s10)
    ck("1 clock_skew record" in t10 and "1 unbooked record" in t10
       and st["base"]["pin_log"]["path"].endswith(W.pin_cur),
       "a new pin run: the old log's last records and the new log's are both read")
    # --- the failure streak: 3 scans without an answer -> said once; then 'reads again' (the changelog, a PDF, the CF
    # status page)
    for cid, down, label in (("changelog", set(CHANGELOG_URLS), "Kalshi API changelog"),
                             ("contract_pdf", {CONTRACT_PDF}, "15-minute crypto contract terms (PDF)"),
                             ("cfb_status", set(CFB_STATUS_URLS), "CF Benchmarks status page")):
        W.web_down = down
        f1, f2, f3, f4 = (one(T1 + 12600 + 1800 * i, only=(cid,)) for i in range(4))
        ck(f1 == [] and f2 == [] and len(f3) == 1 and ("cannot read %s" % label) in f3[0][0] and f4 == [],
           "%s failing 3 scans in a row says so once (%s)" % (cid, [len(f1), len(f2), len(f3), len(f4)]))
        ck(st["checks"][cid]["fail_streak"] == 4 and ("fail|" + cid) in st["open"], "%s: the streak is on /watch" % cid)
        W.web_down = set()
        f5 = one(T1 + 12600 + 1800 * 4, only=(cid,))
        ck(len(f5) == 1 and ("Cleared: %s reads again" % label) in f5[0][0], "%s back: one quiet 'reads again' note"
           % cid)
    # --- the network down for the signed reads: 3 failures end the scan's reads; the check fails, nothing crashes
    W.net_down = True
    n1 = one(T1 + 23000, only=("kalshi_api",))
    ck(len(W.calls) == NET_ABORT and st["checks"]["kalshi_api"]["status"] == "failed" and n1 == [],
       "network down: %d signed reads tried, then stopped; the check failed quietly" % len(W.calls))
    W.net_down = False
    # --- HTTP patterns: 401 on the balance -> URGENT; 429 twice running -> said; 404 on a series -> URGENT
    W.http = {"/portfolio/balance": 401, "/markets": 429}
    h1 = one(T1 + 25000, only=("kalshi_api",))
    th = "\n".join(t for t, u in h1 if u)
    ck("Kalshi refused pin's key" in th and "401" in th, "401 on a signed read -> URGENT (pin's key)")
    ck("rate-limiting" not in "\n".join(t for t, _ in h1), "429 once -> not yet")
    W.http["/series/KXNEAR15M"] = 404
    W.http["/series/KXETH15M"] = 404
    h2 = one(T1 + 26800, only=("kalshi_api",))
    ck("rate-limiting" in "\n".join(t for t, _ in h2), "429 two scans running -> said")
    ck("not found' to GET /series/" in "\n".join(t for t, u in h2 if u), "404 on a series -> URGENT")
    W.http = {}
    h3 = one(T1 + 28600, only=("kalshi_api",))
    h3 += one(T1 + 30400, only=("kalshi_api",))
    t3 = "\n".join(t for t, _ in h3)
    ck("Cleared: Kalshi refused pin's key" in t3 and "Cleared: Kalshi is rate-limiting" in t3
       and "Cleared: Kalshi answered 'not found'" in t3, "the HTTP conditions clear when the answers are 200 again")
    # every read refused: the detail says so (not "0 failed")
    rb = json.loads(canon(st["base"]["kalshi_api"]))
    W.http = {p: 401 for p in ("/exchange/status", "/series/fee_changes", "/markets", "/exchange/schedule",
                               "/portfolio/balance")}
    W.http.update({"/series/" + s: 401 for s in SERIES})
    ra = check_kalshi_api(env, rb, T1 + 31000)
    W.http = {}
    ck(ra.status == "failed" and "0 of 20 signed reads ok; 20 refused by Kalshi (HTTP 401 x20)" in ra.detail
       and "api_key_refused" in ra.opens, "every read refused: the check fails and its words say 20 refused, HTTP 401")
    # --- world C: the price ranges, the settlement source and both contract links move (two scans: both rotations)
    W.v = "C"
    c1 = one(T1 + 31600, only=("kalshi_api",))
    c1 += one(T1 + 33400, only=("kalshi_api",))
    tc = "\n".join(t for t, u in c1 if u)
    for w in ("Kalshi changed price_ranges on BTC 15-minute (KXBTC15M): was [{\"end\":\"0.1000\"",
              "Kalshi changed settlement_sources on ETH 15-minute (KXETH15M): was [{\"name\":\"CF Benchmarks\","
              "\"url\":\"https://cfbenchmarks.com\"}], now [{\"name\":\"CF Benchmarks\",\"url\":\"https://www."
              "cfbenchmarks.com/new\"}]",
              "Kalshi changed contract_url on SOL 15-minute (KXSOL15M): was https://kalshi.com/c.pdf, now "
              "https://kalshi.com/c2.pdf",
              "Kalshi changed contract_terms_url on XRP 15-minute (KXXRP15M)"):
        ck(w in tc, "URGENT, old beside new: %s" % w[:70])
    W.v = "A"
    one(T1 + 35200, only=("kalshi_api",))
    one(T1 + 37000, only=("kalshi_api",))
    # --- trading paused inside a scheduled window, and on Thursday 3-5 AM ET: no alarm; outside both: the alarm
    W.paused = True
    rb = json.loads(canon(st["base"]["kalshi_api"]))
    Tw = T1 + 38000
    W.extra_windows = [{"start_datetime": iso(Tw - 600), "end_datetime": iso(Tw + 3000)}]
    rw = check_kalshi_api(env, rb, Tw)
    W.extra_windows = []
    rt = check_kalshi_api(env, json.loads(canon(st["base"]["kalshi_api"])), Tm)
    ro = check_kalshi_api(env, json.loads(canon(st["base"]["kalshi_api"])), Tw + 7200)
    W.paused = False
    ck("kalshi_paused" not in rw.opens and "kalshi_paused" not in rt.opens and "kalshi_paused" in ro.opens,
       "paused inside Kalshi's own window or Thursday 3-5 AM ET: no alarm; paused outside both: URGENT")
    # --- the outbox: Telegram down -> kept; up -> sent once
    W.disk_gb = 10.0
    ph.ok = False
    o1 = one(T1 + 42200, only=("disk",))
    ck(o1 == [] and len(st["outbox"]) == 1, "Telegram down: the alert waits in the outbox")
    ph.ok = True
    o2 = one(T1 + 44000, only=("disk",))
    o3 = one(T1 + 45800, only=("disk",))
    ck(len(o2) == 1 and "10.0 GB" in o2[0][0] and o3 == [] and not st["outbox"], "Telegram back: sent once, then quiet")
    ck(len(o2) == 1 and "(seen %s, sent late)" % et(T1 + 42200) in o2[0][0], "a late alert says when it was seen")
    ids = list(st["sent_ids"])
    ck(not queue(st, ids[-1], "again", "the same id", False, "disk", T1 + 45900)
       and not any(o["id"] == ids[-1] for o in st["outbox"]), "an id already sent is never queued again")
    W.disk_gb = 40.0
    one(T1 + 46000, only=("disk",))
    # --- a flood of new changelog entries is ONE message; missing lists are tolerated
    W.cl = CL_B + [("2026-11-%02d" % (10 + i), "Entry number %d" % i, "text %d" % i) for i in range(9)]
    c1 = one(T1 + 47600, only=("changelog",))
    ck(len(c1) == 1 and "9 new entries" in c1[0][0] and "Entry number 0" in c1[0][0], "9 new entries -> ONE message")
    os.remove(os.path.join(W.results, REQS_NAME))
    shutil.rmtree(os.path.join(W.results, "live_launcher_snapshot"))
    mm = one(T1 + 49400, only=("packages", "launchers"))
    ck(st["checks"]["packages"]["status"] == "ok" and "nothing to compare" in st["checks"]["packages"]["detail"]
       and "nothing to compare" in st["checks"]["launchers"]["detail"], "no pinned list / snapshot: nothing compared")
    ck(any("Cleared: Live launcher" in t for t, _u in mm), "the launcher condition clears when its list is gone")
    # --- a check that raises costs only that check
    saved = CHECK_FN["disk"]
    CHECK_FN["disk"] = lambda *a: 1 / 0
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            scan(env, st, T1 + 51200, only=("disk", "packages"))
    finally:
        CHECK_FN["disk"] = saved
    ck(st["checks"]["disk"]["status"] == "failed" and "ZeroDivisionError" in st["checks"]["disk"]["detail"]
       and st["checks"]["packages"]["status"] == "ok", "a check that breaks is a failed check, the others run")
    # --- flapping: a condition that opens a 4th time in a day is only on /watch
    st2, ph2 = new_state(), _FakePhone()
    st2["runs"] = 1
    flap = []
    for i in range(8):
        W.disk_gb = 10.0 if i % 2 == 0 else 40.0
        n0 = len(ph2.sent)
        scan(env, st2, T1 + 60000 + 1800 * i, only=("disk",))
        deliver(st2, ph2, T1 + 60000 + 1800 * i)
        flap.append(ph2.sent[n0:])
    said = ["-" if not m else "open" if "is down to" in m[0][0] and "Cleared" not in m[0][0] else "clear" for m in flap]
    ck(said == ["open", "clear", "open", "clear", "open", "-", "-", "-"] and "3rd time in a day" in flap[4][0][0]
       and "disk_low" not in st2["open"], "a condition opening 4 times in a day: 3 said (the 3rd says so), then only "
                                          "on /watch, silently (%s)" % said)
    W.disk_gb = 10.0
    scan(env, st2, T1 + 60000 + 1800 * 8, only=("disk",))
    ck("disk_low" in st2["open"] and st2["open"]["disk_low"]["quiet"], "...and it is still listed on /watch")
    W.disk_gb = 40.0
    # --- the state file round trip, /watch's fixture, the installer
    sp = os.path.join(W.results, STATE_NAME)
    save_state(st, sp)
    ck(load_state(sp)["runs"] == st["runs"], "the state file round trip")
    ds, dph = demo_state(os.path.join(td, "demo"))
    ck(ds["runs"] == 4 and ds["open"] and ds["changelog_recent"] and len(ds["history"]) >= 10 and len(dph.sent) >= 3,
       "the /watch fixture builds")
    if installer:
        _installer_checks(ck)
    # --- by source: signed only, GET only
    with open(os.path.abspath(__file__), encoding="utf-8") as fh:
        src = fh.read()
    call = "kauth" + ".get("
    ck(("auth=" + "False") not in src and src.count(call) == 1 and src.count(call + "path, params, auth=True)") == 1,
       "every Kalshi API read is signed (kauth's get with auth=True), in one place")
    ck(src.count("urllib.request." + "urlopen(req") == 1 and src.count('method="' + 'GET"') == 1
       and ('method="' + 'P') not in src, "one urlopen in the file, GET only")


def _installer_checks(ck):
    """results\\kalshi_watch_install.ps1, read as text: what it registers, and that NOTHING is registered unless the
    self-test passed (the guard's exit comes before the register) or when the register fails (-ErrorAction Stop in a
    try, its message to the .out file)."""
    try:
        with open(INSTALL_PS1, encoding="utf-8") as fh:
            ps = fh.read()
    except OSError:
        ps = ""
    code = [ln for ln in ps.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    ck('-TaskName "%s"' % TASK in ps and "-RepetitionInterval (New-TimeSpan -Minutes %d)" % EVERY_MIN in ps
       and '-Argument "-I -u C:\\kals-repo\\research\\kalshi_watch.py"' in ps
       and '-Execute "C:\\Python314\\python.exe"' in ps and '-UserId "SYSTEM"' in ps,
       "results\\kalshi_watch_install.ps1: task %s every %d min, python -I -u, as SYSTEM" % (TASK, EVERY_MIN))
    i_st = next((i for i, ln in enumerate(code) if "--self-test" in ln), -1)
    i_guard = next((i for i, ln in enumerate(code) if "$LASTEXITCODE" in ln or "$code -ne 0" in ln and "exit 1" in ln), -1)
    i_exit = next((i for i, ln in enumerate(code) if "$code -ne 0" in ln and "exit 1" in ln), -1)
    i_reg = next((i for i, ln in enumerate(code) if "Register-ScheduledTask" in ln), -1)
    ck(0 <= i_st < i_guard <= i_exit < i_reg, "installer: the self-test runs and its failure exits BEFORE the task is "
                                              "registered (lines %s)" % [i_st, i_guard, i_exit, i_reg])
    reg = code[i_reg] if i_reg >= 0 else ""
    after = " ".join(code[i_reg + 1:i_reg + 4]) if i_reg >= 0 else ""
    ck("-ErrorAction Stop" in reg and i_reg > 0 and code[i_reg - 1].strip().endswith("try {") and "catch" in after
       and "exit 1" in after and "Say" in after,
       "installer: a register that fails stops the script and says why (try, -ErrorAction Stop, catch, Say, exit 1)")
    ck("RepetitionDuration" not in ps and code.count(reg) == 1 and "Unregister-ScheduledTask" not in "\n".join(code),
       "installer: repeats with no end (no -RepetitionDuration), registers once, never unregisters")


def _self_test_changelog(ck, td, out, installer=True):
    """The changelog check on the real formats (REAL_RSS / REAL_MD), the urgent words, sources and dates."""
    os.makedirs(td)
    T0 = T_SAT
    # the urgent words, each with what must count and what must not
    table = [("remove", "Field removed", "Remote access"), ("remove", "Removal of a field", None),
             ("deprecat", "no_sub_title deprecated", None), ("breaking", "A breaking change", None),
             ("rename", "Field renamed to x", None), ("crypto", "Crypto series", None),
             ("15M", "KXBTC15M markets", "a 215MB file"), ("15M", "15m candles", "15MB limit"),
             ("fee", "Fee rounding", "A new feed"), ("order", "Order groups", "border and recorder"),
             ("orderbook", "orderbook_delta", None), ("balance", "GET /portfolio/balance", None),
             ("exchange_index", "exchange_index on orders", None), ("shard", "A new shard", None),
             ("rate limit", "Rate-limit buckets", None), ("websocket", "WebSocket channel", None),
             ("settlement", "Settlement sources", None), ("price_level", "price_level_structure", None),
             ("tick", "tick_size goes", "Market ticker filter"), ("tick", "price ticks change", "Event candlesticks"),
             ("subaccount", "Subaccounts transfer", None), ("api key", "API keys for subaccounts", None),
             ("api key", "api_key header", None)]
    for word, yes, no in table:
        ck(word in urgent_hits(yes) and (no is None or word not in urgent_hits(no)),
           "urgent word '%s': '%s' counts%s" % (word, yes, (", '%s' does not" % no) if no else ""))
    ck(sorted({w for w, _y, _n in table}) == sorted(URGENT_WORDS), "the table covers all %d urgent words"
       % len(URGENT_WORDS))
    # the real RSS: the day it takes effect (the link's anchor), the day posted, the tags, the urgency
    rs = parse_rss(REAL_RSS)
    by = {e["title"]: e for e in rs}
    k = by.get("API key signing algorithm metadata") or {}
    ck(len(rs) == 4 and k.get("date") == "2026-11-12" and k.get("posted") == "2026-11-06"
       and k.get("cats") == ["REST", "Predictions"] and k.get("urgent") and "api key" in k.get("hits"),
       "real RSS: dated by its anchor (Nov 12), posted Nov 6, tagged REST/Predictions, urgent (api key)")
    m = by.get("MCP portfolio access for perps") or {}
    ck(m.get("hits") and not m.get("urgent") and not m.get("relevant"), "real RSS: a Margin-only entry naming "
                                                                        "'order' and 'balance' is not urgent")
    q = by.get("Equities orders need an approved stocks application") or {}
    ck(q.get("date") == "TBD" and not q.get("urgent"), "real RSS: a TBD FIX/Margin entry: day TBD, not urgent")
    n = by.get("Market positions include netting_enabled") or {}
    ck(n.get("date") == "2026-11-05" and n.get("urgent") and "subaccount" in n.get("hits"),
       "real RSS: a Predictions entry naming 'subaccount' is urgent")
    # the real changelog.md: the same four entries (no titles) have the same fingerprints; the rest of its history too
    ms = parse_md(REAL_MD)
    ck(len(ms) == 5 and [e["date"] for e in ms] == ["2026-11-12", "2026-11-12", "TBD", "2026-11-05", "2026-10-22"]
       and {e["fp"] for e in rs} <= {e["fp"] for e in ms},
       "real changelog.md: '**November 12, 2026**' and '**TBD**' entries read, same fingerprints as the RSS (%s)"
       % [e["date"] for e in ms])
    ck(ms[0]["title"].startswith("GET /api_keys now includes key_type") and ms[0]["urgent"],
       "changelog.md: an entry's first sentence stands for its title; its words still judged")
    old = parse_md(_md(CL_A, old=True).decode())
    ck([e["date"] for e in old] == ["2026-10-01", "2026-11-05", "2026-11-20"] and old[0]["title"] ==
       "Market tick_size field removed", "the older <Update> block format is still read")
    # check_changelog over the real feed: the baseline, a switch to changelog.md (nothing new), a new entry there
    feed = {}
    fe = Env(results=td, repo=td, fetch=lambda u, **k: (200, feed[u], {}) if u in feed else (404, b"", {}),
             log_path="")
    b0 = {}
    feed[CHANGELOG_URLS[0]] = REAL_RSS.encode("utf-8")
    r0 = check_changelog(fe, b0, T0)
    ck(r0.alerts == [] and "4 entries recorded" in r0.summary, "real RSS baseline: nothing said (%s)" % r0.summary)
    feed.clear()
    feed[CHANGELOG_URLS[1]] = REAL_MD.encode("utf-8")
    r1 = check_changelog(fe, b0, T0 + 1800)
    ck(r1.alerts == [], "RSS down, changelog.md read: the same entries and its older history say nothing (%s)"
       % [a["head"] for a in r1.alerts])
    feed[CHANGELOG_URLS[1]] = (REAL_MD + "**November 20, 2026**\n\nThe `orderbook_delta` channel drops `price`.\n\n"
                               ).encode("utf-8")
    r2 = check_changelog(fe, b0, T0 + 3600)
    ck(len(r2.alerts) == 1 and r2.alerts[0]["urgent"] and "dated Nov 20, 2026 (in 13 days)" in r2.alerts[0]["body"],
       "changelog.md: a new entry is said with its day, urgent (orderbook) (%s)" % [a["body"][:90] for a in r2.alerts])
    feed.clear()
    feed[CHANGELOG_URLS[0]] = REAL_RSS.replace(
        "<item>", "<item><title><![CDATA[Order group limits]]></title><description><![CDATA[Order groups cap at 10."
        "]]></description><link>https://docs.kalshi.com/changelog#november-19-2026</link><guid isPermaLink=\"false\">"
        "aa11</guid><category><![CDATA[REST]]></category><category><![CDATA[Predictions]]></category><pubDate>Sat, 07 "
        "Nov 2026 19:00:00 GMT</pubDate><content:encoded><![CDATA[<p>Order groups cap at 10 orders.</p>]]>"
        "</content:encoded></item><item>", 1).encode("utf-8")
    r3 = check_changelog(fe, b0, T0 + 5400)
    ck(len(r3.alerts) == 1 and "Order group limits" in r3.alerts[0]["head"] and r3.alerts[0]["urgent"]
       and "It takes effect Nov 19, 2026 (in 12 days); posted Nov 7, 2026" in r3.alerts[0]["body"],
       "back to the RSS: only the entry posted since the last scan is news, with the day it takes effect and the day "
       "posted (%s)" % [a["body"][:120] for a in r3.alerts])
    # a seen entry whose day moves (TBD -> Nov 24) is said once; a Margin-only entry is said but never urgent
    feed[CHANGELOG_URLS[0]] = feed[CHANGELOG_URLS[0]].replace(b"changelog#tbd", b"changelog#november-24-2026")
    r4 = check_changelog(fe, b0, T0 + 7200)
    r5 = check_changelog(fe, b0, T0 + 9000)
    ck(len(r4.alerts) == 1 and "was a day not set yet (TBD), now Nov 24, 2026" in r4.alerts[0]["body"]
       and not r4.alerts[0]["urgent"] and "tags it REST/FIX/Margin only" in r4.alerts[0]["body"] and r5.alerts == [],
       "a TBD entry given a day: said once, not urgent (Margin/FIX only, said why) (%s)"
       % [a["body"][:120] for a in r4.alerts])
    # a short RSS, then the full changelog.md (an old-format world): the older entry joins silently, the new one is said
    b1 = {}
    feed.clear()
    feed[CHANGELOG_URLS[0]] = _rss(CL_A[1:])
    check_changelog(fe, b1, T0)
    feed.clear()
    feed[CHANGELOG_URLS[1]] = _md(CL_A + [("2026-11-21", "A brand new entry", "Something new.")])
    rb = check_changelog(fe, b1, T0 + 1800)
    ck(len(rb.alerts) == 1 and "Something new." in rb.alerts[0]["head"],
       "a short RSS, then the full changelog.md: the older entry joins silently, the new one is said (%s)"
       % [a["head"] for a in rb.alerts])
    ck([e["fp"] for e in parse_rss(_rss(CL_A).decode())] == [e["fp"] for e in parse_md(_md(CL_A).decode())],
       "the same entry has the same fingerprint in the RSS and in changelog.md")


def _pin_world(td, name="pinrun-live-20261107T100000Z.jsonl"):
    W = _World(td)
    W.pin_cur = name
    return W, W.env()


def _self_test_pin(ck, td, out, installer=True):
    """The pin-log check on 0925v's record kinds, its blocks, refused hedges, old records, a stand-down."""
    os.makedirs(td)
    Tp = T_SAT
    # every record kind, judged
    want = {("api_shape", None): True, ("hedge_fail", None): True, ("universe_empty", "fallback"): True,
            ("universe_empty", "recovered"): False, ("unbooked", "provisional"): True, ("unbooked", "gave_up"): True,
            ("unbooked", "booked"): False, ("startup_bank", "none"): True, ("startup_bank", "mirror"): False,
            ("startup_bank", "api"): False, ("log_write_fail", "traj"): False, ("dayloss_write_fail", None): True,
            ("clock_skew", None): True, ("hedge_broken", None): True, ("expiry_exit", False): True,
            ("expiry_exit", True): None, ("expiry_drain", None): None}
    got = {}
    for (k, v), u in want.items():
        d = {"kind": k}
        if k in ("universe_empty", "unbooked"):
            d["what"] = v
        elif k == "startup_bank":
            d["source"] = v
        elif k == "log_write_fail":
            d["which"] = v
        elif k == "expiry_exit":
            d["flat"] = v
        j = pin_judge(d)
        got[(k, v)] = None if j is None else j[0]
    ck(got == want, "every pin record kind judged: urgent / quiet / never said (%s)"
       % {k: (got[k], want[k]) for k in want if got[k] != want[k]})
    ck(hedge_refused(REAL_HEDGE_1031) == "noid" and hedge_refused(REAL_HEDGE_1107) is None
       and hedge_refused(dict(REAL_HEDGE_1107, status_code=400)) == 400
       and hedge_refused(dict(REAL_HEDGE_1107, kind="hedge_extra", status_code="409")) == 409
       and hedge_refused(dict(REAL_HEDGE_1107, status_code=None)) is None
       and hedge_refused(dict(REAL_HEDGE_1107, status_code=503)) is None
       and hedge_refused(dict(REAL_HEDGE_1031, live=False)) is None
       and hedge_refused(dict(REAL_HEDGE_1031, kind="order")) is None,
       "refused hedges: a 4xx (hedge or hedge_extra), or a live send with no order id in a log from before status_code; "
       "not a fill, a 5xx, no answer or a paper hedge")
    # a pin run with a block in force at the first scan, then every kind between two scans
    W, env = _pin_world(os.path.join(td, "kinds"))
    W.pin_append(W.pin_cur, [{"kind": "start", "t": iso(Tp - 4 * 3600)},
                             {"kind": "api_shape", "endpoint": "GET /markets", "field": "close_time", "t": iso(Tp - 3600)},
                             {"kind": "entries_blocked", "reason": "guard_error", "parts": ["unbooked"],
                              "blocks": "new entries only; hedges ...", "t": iso(Tp - 1200)},
                             {"kind": "universe", "got": 9, "t": iso(Tp - 60)}])
    base = {}
    r1 = check_pin_log(env, base, Tp)
    ck(r1.alerts == [] and set(r1.opens) == {"pin_block|guard_error"} and r1.opens["pin_block|guard_error"]["urgent"]
       and "one of its own safety checks broke" in r1.opens["pin_block|guard_error"]["head"]
       and "1 warning record" in r1.summary, "first scan: old records not said one by one; a block in force is open, "
                                             "URGENT (%s / %s)" % ([a["head"] for a in r1.alerts], sorted(r1.opens)))
    t = Tp + 60
    recs = [{"kind": "api_shape", "endpoint": "ws orderbook", "field": "delta_malformed", "what": "counted"},
            {"kind": "hedge_fail", "ticker": "KXSOL15M-26NOV071645-45", "close_s": Tp + 900, "status_code": 400,
             "body": "invalid price"},
            {"kind": "universe_empty", "what": "fallback", "refreshes": 3},
            {"kind": "universe_empty", "what": "recovered", "refreshes": 4},
            {"kind": "unbooked", "what": "provisional", "ticker": "KXETH15M-26NOV071600-00", "close_s": Tp - 600},
            {"kind": "unbooked", "what": "booked", "ticker": "KXETH15M-26NOV071530-30", "close_s": Tp - 1800},
            {"kind": "unbooked", "what": "gave_up", "ticker": "KXBTC15M-26NOV071000-00", "close_s": Tp - 7 * 3600},
            {"kind": "startup_bank", "source": "none", "tries": 6},
            {"kind": "startup_bank", "source": "mirror", "bank": 3100.0},
            {"kind": "startup_bank", "source": "api", "bank": 3100.0},
            {"kind": "log_write_fail", "which": "traj", "err": "OSError"},
            {"kind": "dayloss_write_fail", "reason": "dayloss_write", "path": "x", "blocks": "new entries only"},
            {"kind": "clock_skew", "reason": "clock_skew", "median_ms": 912.0, "blocks": "new entries only"},
            {"kind": "entries_resumed", "reason": "clock_skew", "blocked_s": 75.0, "dt": 75},
            {"kind": "expiry_drain", "reason": "expiry_drain", "end_in_s": 1199.0},
            {"kind": "expiry_exit", "flat": True, "why": "flat"},
            {"kind": "expiry_exit", "flat": False, "why": "grace: still holding 1 position(s)"},
            {"kind": "entries_resumed", "reason": "guard_error", "blocked_s": 1300.0},
            {"kind": "hedge_broken", "ticker": "KXZEC15M-26NOV071615-15", "n": 120.0},
            {"kind": "universe", "got": 9, "dt": 1650}]
    W.pin_append(W.pin_cur, [dict({k: v for k, v in d.items() if k != "dt"}, t=iso(t + i + d.get("dt", 0)))
                             for i, d in enumerate(recs)])
    r2 = check_pin_log(env, base, Tp + 1800)
    heads = {a["head"]: a["urgent"] for a in r2.alerts}
    print("    pin kinds: %s" % sorted(heads.items()), file=out)
    urgent_heads = ["Pin got a Kalshi answer without the shape it reads: ws orderbook, field delta_malformed "
                    "(api_shape)", "Pin had a hedge order fail "
                    "(hedge_fail)", "Pin got an empty market list from Kalshi", "Pin has a bet it has not booked 15 "
                    "minutes", "Pin gave up booking a bet", "Pin could not read its bank at startup",
                    "Pin ended its run still holding a bet", "Pin could not hedge a position (hedge_broken)"]
    quiet_heads = ["Pin has markets again after an empty market list", "Pin booked a bet that had gone unbooked",
                   "Pin set its day stop from its last known bank", "Pin read its bank at startup after a retry",
                   "Pin could not write its trajectory file", "Pin paused new bets for 76 seconds and resumed"]
    for h in urgent_heads:
        ck(any(k.startswith(h) and u for k, u in heads.items()), "URGENT: %s" % h)
    for h in quiet_heads:
        ck(any(k.startswith(h) and not u for k, u in heads.items()), "quiet: %s" % h)
    ck(len(heads) == len(urgent_heads) + len(quiet_heads) and not any("expiry_drain" in k for k in heads),
       "nothing else said: not expiry_drain (the run's ordinary end), not expiry_exit flat (%d alerts)" % len(heads))
    ck(set(r2.opens) == {"pin_block|dayloss_write"} and r2.opens["pin_block|dayloss_write"]["urgent"],
       "a block still in force is an URGENT open condition; one that resumed is not (%s)" % sorted(r2.opens))
    # old records read after the watch was off: said quietly, with their age
    W.pin_append(W.pin_cur, [{"kind": "api_shape", "endpoint": "GET /markets", "field": "x", "t": iso(Tp - 3 * 3600)}])
    r3 = check_pin_log(env, base, Tp + 3600)
    ck(len(r3.alerts) == 1 and not r3.alerts[0]["urgent"] and "the watch was not reading then" in r3.alerts[0]["body"],
       "a record more than 2 hours old when read: said quietly, with its age")
    # refused hedges: exactly 5 in an hour no; a 6th yes; 6 spread over 75 minutes no; hedge_extra and the old shape count
    for name, recs_, now_, want_open, what in (
            ("five", [dict(REAL_HEDGE_1107, status_code=400, n=0.0, order_id=None, t=iso(Tp + 60 * i))
                      for i in range(5)], Tp + 1800, False, "exactly 5 refused in an hour: no alarm"),
            ("six", [dict(REAL_HEDGE_1107, status_code=400, n=0.0, order_id=None, t=iso(Tp + 60 * i))
                     for i in range(6)], Tp + 1800, True, "6 refused in an hour: URGENT"),
            ("spread", [dict(REAL_HEDGE_1107, status_code=400, n=0.0, order_id=None, t=iso(Tp + 900 * i))
                        for i in range(6)], Tp + 4800, False, "6 refused over 75 minutes (5 in any hour): no alarm"),
            ("extra", [dict(REAL_HEDGE_1107, kind="hedge_extra" if i % 2 else "hedge", status_code=409, n=0.0,
                            order_id=None, t=iso(Tp + 60 * i)) for i in range(6)], Tp + 1800, True,
             "hedge_extra refusals count too"),
            ("old", [dict(REAL_HEDGE_1031, t=iso(Tp + 60 * i)) for i in range(6)], Tp + 1800, True,
             "the 10-31 shape (no status_code, no order id) counts"),
            ("filled", [dict(REAL_HEDGE_1107, t=iso(Tp + 60 * i)) for i in range(12)], Tp + 1800, False,
             "12 filled hedges (201): no alarm")):
        Wr, envr = _pin_world(os.path.join(td, "ref_" + name))
        Wr.pin_append(Wr.pin_cur, [{"kind": "start", "t": iso(Tp - 600)}, {"kind": "universe", "got": 9,
                                                                            "t": iso(Tp - 60)}])
        br = {}
        check_pin_log(envr, br, Tp)
        Wr.pin_append(Wr.pin_cur, recs_ + [{"kind": "universe", "got": 9, "t": iso(now_ - 60)}])
        rr = check_pin_log(envr, br, now_)
        ck(("pin_hedge_4xx" in rr.opens) == want_open and (not want_open or rr.opens["pin_hedge_4xx"]["urgent"]),
           "%s (%s)" % (what, (rr.opens.get("pin_hedge_4xx") or {}).get("head")))
        if name == "old":
            ck("no order id, nothing filled x6" in rr.opens["pin_hedge_4xx"]["body"], "...said as 'no order id'")
    # a new pin run ends the old run's blocks (the new process starts with none)
    W.pin_append(W.pin_cur, [{"kind": "universe", "got": 9, "t": iso(Tp + 3500)}])
    W.pin_cur = "pinrun-live-20261107T214000Z.jsonl"
    W.pin_append(W.pin_cur, [{"kind": "start", "t": iso(Tp + 4000)}, {"kind": "universe", "got": 9, "t": iso(Tp + 5300)}])
    r4 = check_pin_log(env, base, Tp + 5400)
    ck("pin_block|dayloss_write" in r3.opens and not any(k.startswith("pin_block|") for k in r4.opens),
       "a new pin run: the old run's block is over (%s)" % sorted(r4.opens))
    # the first read takes only the log's last TAIL_FIRST bytes
    Wt, envt = _pin_world(os.path.join(td, "tail"))
    pad = json.dumps({"kind": "universe", "got": 9, "n": 9, "pad": "x" * 200, "t": iso(Tp - 7200)}) + "\n"
    with open(os.path.join(Wt.results, Wt.pin_cur), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"kind": "clock_skew", "skew_s": 3.0, "t": iso(Tp - 9000)}) + "\n")
        fh.write(pad * (TAIL_FIRST // len(pad) + 50))
        fh.write(json.dumps({"kind": "api_shape", "field": "x", "t": iso(Tp - 120)}) + "\n")
        fh.write(json.dumps({"kind": "universe", "got": 9, "t": iso(Tp - 60)}) + "\n")
    rt = check_pin_log(envt, {}, Tp)
    ck("1 warning record from before" in rt.summary and "api_shape x1" in rt.summary and "clock_skew" not in rt.summary,
       "the first read takes only the last 4 MB of pin's log (%s)" % rt.summary[-120:])
    # a stand-down that just ended, a new pin run 60 s old with no market list yet: no alarm (probe 2, the review)
    Ws, envs = _pin_world(os.path.join(td, "stand"), "pinrun-live-20261107T100000Z.jsonl")
    Ws.pin_append(Ws.pin_cur, [{"kind": "start", "t": iso(Tp - 8 * 3600)},
                               {"kind": "universe", "got": 9, "t": iso(Tp - 6 * 3600)}])
    bs = {}
    check_pin_log(envs, bs, Tp - 6 * 3600 + 60)
    with open(os.path.join(Ws.results, PIN_STOP_NAME), "w", encoding="utf-8") as fh:
        fh.write("operator PAUSE")
    rs1 = check_pin_log(envs, bs, Tp)
    os.remove(os.path.join(Ws.results, PIN_STOP_NAME))
    Ws.pin_cur = "pinrun-live-%s.jsonl" % time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(Tp + 1740))
    Ws.pin_append(Ws.pin_cur, [{"kind": "start", "t": iso(Tp + 1740)}])
    rs2 = check_pin_log(envs, bs, Tp + 1800)
    rs3 = check_pin_log(envs, bs, Tp + 1800 + 900)
    ck("pin_no_markets" not in rs1.opens and "pin_no_markets" not in rs2.opens and "pin_no_markets" in rs3.opens
       and "for 16 minutes" in rs3.opens["pin_no_markets"]["head"],
       "after a 6-hour stand-down: no alarm while stood down, none for a new run 60 s old, the alarm 16 minutes in "
       "(%s)" % (rs3.opens.get("pin_no_markets") or {}).get("head"))


# v-kwfalse (2026-11-13): the real material of the 11-13 read. Each coin's fixed-strike rules text (the wording of the
# KXETH15M 2:30 AM market of 11-12, strike 2045.23) with: its norm_rules hash (the alarm's; ETH's 7f2cdf1b is on file
# since its alarm, BTC and SOL had not rung yet on the server) and the opening-price hash its rules_key gives, which is
# on file in the server's results\kalshi_watch_state.json of 11-13
RULES_FIXED_1112 = ("If the simple average of the sixty seconds of CF Benchmarks' %s before 2:30 AM EST on Nov 12, "
                    "2026 is at least 2045.23, then the market resolves to Yes.")
RULES_1113 = {"KXBTC15M": ("BRTI", "dc071334", "f506e9e4"), "KXETH15M": ("ETHUSD_RTI", "7f2cdf1b", "d214e939"),
              "KXSOL15M": ("SOLUSD_RTI", "9ee63c73", "15e4abe2"), "KXXRP15M": ("XRPUSD_RTI", "39dd39f0", "640e8e9a"),
              "KXDOGE15M": ("DOGEUSD_RTI", "f4171bc2", "af438da7"), "KXBNB15M": ("BNBUSD_RTI", "1f2bf289", "19a76b8a"),
              "KXZEC15M": ("ZECUSD_RTI", "2ff0e359", "496dfe13"), "KXNEAR15M": ("NEARUSD_RTI", "fab70b6b", "71bc77a3"),
              "KXHYPE15M": ("HYPEUSD_RTI", "9998a967", "de6a6034")}
# an open KXETH15M market's rules_primary as Kalshi served it on 11-13 (the opening-price wording, ETHUSDRTI)
RULES_OPEN_ETH_1113 = ("If the simple average of the sixty seconds of CF Benchmarks' ETHUSDRTI before 12:00 AM EST "
                       "on Nov 14, 2026 is at least the simple average of the sixty seconds of CF Benchmarks' "
                       "ETHUSDRTI before 11:45 PM EST on November 13, 2026, then the market resolves to Yes.")
# the server state's whole rules lists of 11-13 for the two series that had not rung yet (each holds only its
# opening-price hash)
RULES_ON_FILE_1113 = {"KXBTC15M": ["f506e9e41976c3be5db68d53862eec1b1b7567d3e13c5433367424aa1248e3cf"],
                      "KXSOL15M": ["15e4abe2b2a59f87329dc4b0c31d38384da5cdf675e1108b3eca6a104ed8afac"]}
# pin's 6 api_shape records behind the 5 api_shape alarms (11-08 14:31 and 17:46 runs, 11-10 12:35 run), as written
REAL_SHAPES = [
    {"keys": "clock", "endpoint": "ws orderbook_snapshot", "field": "yes_dollars_fp/no_dollars_fp",
     "what": "absent_with_other_keys", "t": "2026-11-08T14:45:00Z", "kind": "api_shape"},
    {"ticker": "KXSOL15M-26NOV081000-00", "endpoint": "/markets", "field": "floor_strike", "what": "missing",
     "t": "2026-11-08T14:45:20Z", "kind": "api_shape"},
    {"keys": "clock", "endpoint": "ws orderbook_snapshot", "field": "yes_dollars_fp/no_dollars_fp",
     "what": "absent_with_other_keys", "t": "2026-11-08T18:00:01Z", "kind": "api_shape"},
    {"ticker": "KXDOGE15M-26NOV081345-45", "endpoint": "/markets", "field": "floor_strike", "what": "missing",
     "t": "2026-11-08T18:30:20Z", "kind": "api_shape"},
    {"keys": "clock", "endpoint": "ws orderbook_snapshot", "field": "yes_dollars_fp/no_dollars_fp",
     "what": "absent_with_other_keys", "t": "2026-11-10T12:45:00Z", "kind": "api_shape"},
    {"ticker": "KXXRP15M-26NOV100830-30", "endpoint": "/markets", "field": "floor_strike", "what": "missing",
     "t": "2026-11-10T13:15:20Z", "kind": "api_shape"}]


def _self_test_false_alarms(ck, td, out, installer=True):
    """v-kwfalse (2026-11-13): the 12 URGENT false alarms of the watch's first 4.7 days, from their real records (the
    fixed-strike rules wording, 7; pin's two harmless api_shape shapes, 5), what must still ring, and the CF PDF's
    'site refuses' mark."""
    os.makedirs(td)
    # (a) the rules wording: every coin's fixed-strike text hashes as its opening-price text, the hash on file
    bad = []
    for s, (idx, h_fixed, h_open) in sorted(RULES_1113.items()):
        t = norm_rules(RULES_FIXED_1112 % idx)
        if sha256(t)[:8] != h_fixed or sha256(rules_key(t))[:8] != h_open:
            bad.append((s, sha256(t)[:8], sha256(rules_key(t))[:8]))
    ck(not bad, "rules: the fixed-strike wording of all 9 coins (BRTI, <COIN>USD_RTI) hashes as the opening-price "
                "wording on file in the server's state of 11-13 (%s)" % bad)
    to = norm_rules(RULES_OPEN_ETH_1113)
    ck(rules_key(to) == to and sha256(to)[:8] == "d214e939",
       "rules: the opening-price wording Kalshi served on 11-13 is hashed as it is (d214e939, ETH's baseline)")
    eth_fixed = RULES_FIXED_1112 % "ETHUSD_RTI"
    still = [("thirty seconds", eth_fixed.replace("sixty", "thirty")),
             ("is above", eth_fixed.replace("is at least", "is above")),
             ("another index", eth_fixed.replace("ETHUSD_RTI", "ETHUSD_RR")),
             ("BRTI on ETH", RULES_FIXED_1112 % "BRTI"),
             ("an added sentence", eth_fixed + " If CF Benchmarks does not publish it, the market resolves to No."),
             ("a strike in words", eth_fixed.replace("2045.23", "the strike"))]
    rung = [w for w, v in still if sha256(rules_key(norm_rules(v)))[:8] not in ("d214e939", "7f2cdf1b")]
    ck(len(rung) == len(still), "rules: still new on ETH: %s (%s)" % (", ".join(w for w, _v in still), rung))
    # ...through check_markets: the server's own lists for BTC and SOL (the 2 alarms not rung yet), then ETH from a
    # fixture baseline: the fixed-strike wording says nothing, another sentence is URGENT and shown as Kalshi wrote it
    for s in ("KXBTC15M", "KXSOL15M"):
        store, rk = {"rules": list(RULES_ON_FILE_1113[s])}, Result()
        body = {"markets": [{"ticker": "%s-26NOV120230-30" % s, "rules_primary": RULES_FIXED_1112 % RULES_1113[s][0]}]}
        check_markets(store, s, body, rk, T_SAT)
        ck(not [a for a in rk.alerts if a["id"].startswith("rules|")] and store["rules"] == RULES_ON_FILE_1113[s],
           "rules: %s's fixed-strike market against the server's list of 11-13: nothing said (%s)" % (
               s, [a["head"] for a in rk.alerts]))
    store, rk = {}, Result()
    for i, texts in enumerate(([RULES_OPEN_ETH_1113] * 2, [RULES_OPEN_ETH_1113, eth_fixed],
                               [eth_fixed, eth_fixed.replace("sixty", "thirty")])):
        check_markets(store, "KXETH15M", {"markets": [{"ticker": "KXETH15M-26NOV1202%d0-%d0" % (i, i),
                                                       "rules_primary": x} for x in texts]}, rk, T_SAT + 1800 * i)
    ra = [a for a in rk.alerts if a["id"].startswith("rules|")]
    ck(len(ra) == 1 and ra[0]["urgent"] and "New settlement rules sentence on ETH 15-minute" in ra[0]["head"]
       and "thirty seconds of CF Benchmarks' ETHUSD_RTI" in ra[0]["body"] and len(store["rules"]) == 2,
       "rules: ETH opening-price baseline, then a fixed-strike market: nothing; then 'thirty seconds': URGENT, the "
       "text as Kalshi wrote it (%s)" % [a["head"] for a in ra])
    # (b) pin's api_shape records: the 6 real ones are the two harmless shapes; every near miss keeps its alarm
    ck(all(shape_harmless(d) for d in REAL_SHAPES), "api_shape: the 6 real records of 11-08..11-10 are harmless (%s)"
       % [shape_harmless(d) for d in REAL_SHAPES])
    snap, strike = REAL_SHAPES[0], REAL_SHAPES[1]
    edt = {"kind": "api_shape", "endpoint": "/markets", "field": "floor_strike", "what": "missing",
           "ticker": "KXBTC15M-26OCT200930-30", "t": "2026-10-20T13:15:20Z"}       # 9:30 AM EDT = 13:30Z
    ck(shape_harmless(edt) and shape_harmless(dict(snap, keys=["clock"])),
       "api_shape: the strike rule reads the ticker in Eastern time (daylight time too); keys as a list")
    misses = [("a key beside clock", dict(snap, keys="clock,yes_book")), ("no other key", dict(snap, keys="")),
              ("a snapshot not_a_list", dict(snap, what="not_a_list", field="yes_dollars_fp")),
              ("95 s into the quarter", dict(strike, t="2026-11-08T14:46:35Z")),
              ("the market before (it closes at the quarter)", dict(strike, ticker="KXSOL15M-26NOV080945-45")),
              ("EDT read as EST", dict(edt, t="2026-10-20T14:15:20Z")),
              ("no ticker", {k: v for k, v in strike.items() if k != "ticker"}),
              ("no time", {k: v for k, v in strike.items() if k != "t"}),
              ("from /events", dict(strike, endpoint="/events")), ("unreadable", dict(strike, what="unreadable")),
              ("the balance", {"kind": "api_shape", "endpoint": "/portfolio/balance", "field": "balance",
                               "what": "missing", "t": "2026-11-08T14:45:20Z"}),
              ("another kind", dict(strike, kind="hedge_fail"))]
    loud = [w for w, d in misses if shape_harmless(d) is None]
    ck(len(loud) == len(misses), "api_shape: still an alarm: %s (%s)" % (", ".join(w for w, _d in misses), loud))
    jb = pin_judge(misses[-2][1])
    ck(jb == (True, "got a Kalshi answer without the shape it reads: /portfolio/balance, field balance")
       and pin_judge({"kind": "api_shape"})[1] == PIN_ALARM_WORDS["api_shape"],
       "api_shape: the head names the endpoint and the field (%s)" % (jb,))
    # ...through check_pin_log: the 6 only logged; a balance shape and a close_time shape: 2 URGENT heads, apart
    W, env = _pin_world(os.path.join(td, "shapes"), "pinrun-live-20261110T123539Z.jsonl")
    Tn = float(calendar.timegm((2026, 11, 10, 13, 30, 0)))
    W.pin_append(W.pin_cur, [{"kind": "start", "t": "2026-11-10T12:35:39Z"}, {"kind": "universe", "got": 9,
                                                                               "t": "2026-11-10T12:39:00Z"}])
    bs = {}
    check_pin_log(env, bs, Tn - 3000)
    W.pin_append(W.pin_cur, REAL_SHAPES + [
        {"kind": "api_shape", "endpoint": "/portfolio/balance", "field": "balance", "what": "missing",
         "t": "2026-11-10T13:20:00Z"},
        {"kind": "api_shape", "endpoint": "/markets", "field": "close_time", "what": "unparsable", "value": "x",
         "ticker": "KXBTC15M-26NOV100830-30", "t": "2026-11-10T13:15:20Z"},
        {"kind": "universe", "got": 9, "t": "2026-11-10T13:29:00Z"}])
    n0 = len(env.lines)
    rp = check_pin_log(env, bs, Tn)
    heads = sorted(a["head"] for a in rp.alerts)
    logged = [x for x in env.lines[n0:] if "pin api_shape of a known harmless shape, not sent" in x]
    ck(heads == ["Pin got a Kalshi answer without the shape it reads: /markets, field close_time (api_shape)",
                 "Pin got a Kalshi answer without the shape it reads: /portfolio/balance, field balance (api_shape)"]
       and all(a["urgent"] for a in rp.alerts) and len(logged) == 6
       and "6 api_shape records of a known harmless shape only logged" in rp.detail,
       "pin log: the 6 real harmless records only in the watch's log; the balance and close_time shapes 2 URGENT "
       "alerts, each naming its endpoint and field (%s; %d logged)" % (heads, len(logged)))
    # (c) the CF PDF with no answer: failed 47 scans, marked 'site refuses' at the 48th (one quiet note), then quiet;
    # the contract PDF is never marked; the first answer ends the mark (quietly)
    W.web_down = {CFB_PDF, CONTRACT_PDF}
    bc, bk = {}, {}
    rc = [check_cfb_pdf(env, bc, T_SAT + 1800 * i) for i in range(50)]
    rk_ = [check_contract_pdf(env, bk, T_SAT + 1800 * i) for i in range(50)]
    ck([x.status for x in rc] == ["failed"] * 47 + ["ok"] * 3
       and [[a["urgent"] for a in x.alerts] for x in rc] == [[]] * 47 + [[False], [], []]
       and "the site refuses the server" in rc[47].alerts[0]["head"] and rc[49].extra.get("refused")
       and "site refuses the server: no answer on 50 scans in a row" in rc[49].detail,
       "CF PDF: no answer on 47 scans = failed; the 48th marks 'site refuses' (one quiet note), then quiet (%s)"
       % rc[49].detail)
    ck(all(x.status == "failed" and not x.alerts for x in rk_) and not bk.get("refused"),
       "the contract PDF (urgent on change) is never marked 'site refuses'")
    W.web_down = set()
    rb = check_cfb_pdf(env, bc, T_SAT + 1800 * 50)
    W.web_down = {CFB_PDF}
    rd = [check_cfb_pdf(env, bc, T_SAT + 1800 * (51 + i)) for i in range(2)]
    ck(rb.status == "ok" and [a["urgent"] for a in rb.alerts] == [False] and "answers again" in rb.alerts[0]["head"]
       and "after 50 scans with no answer" in rb.alerts[0]["body"] and bc.get("sha") and "refused" not in bc
       and [x.status for x in rd] == ["failed", "failed"] and not rd[0].alerts,
       "CF PDF answers again: one quiet note, read as before (its first copy recorded); no answer again starts a "
       "new streak (%s)" % [a["head"] for a in rb.alerts])
    # ...through scan(): 'cannot read' once at the 3rd scan, the mark at the 48th WITHOUT a 'reads again' note, the
    # check ok on /watch, its failure condition gone; back: 'answers again', no 'reads again'
    Wf = _World(os.path.join(td, "scan"))
    _world_files(Wf)
    envf, phf, stf = Wf.env(), _FakePhone(), new_state()
    one = _stepper(Wf, envf, stf, phf)
    one(T_SAT)
    Wf.web_down = {CFB_PDF}
    said = [one(T_SAT + 1800 * (i + 1), only=("cfb_pdf",)) for i in range(49)]
    idx = [i for i, m in enumerate(said) if m]
    ck(idx == [2, 47] and "cannot read CF Benchmarks index exchanges (PDF)" in said[2][0][0]
       and "the site refuses the server" in said[47][0][0] and "reads again" not in said[47][0][0]
       and not said[47][0][1] and stf["checks"]["cfb_pdf"]["status"] == "ok"
       and "site refuses" in stf["checks"]["cfb_pdf"]["detail"] and "fail|cfb_pdf" not in stf["open"],
       "scan: 'cannot read' at the 3rd scan, 'site refuses' (quiet) at the 48th with no 'reads again'; /watch shows it "
       "ok, marked, and the failure condition is gone (messages at scans %s)" % [i + 1 for i in idx])
    Wf.web_down = set()
    back = one(T_SAT + 1800 * 51, only=("cfb_pdf",))
    ck(len(back) == 1 and "the site answers again" in back[0][0] and "reads again" not in back[0][0],
       "scan: the CF PDF back: one quiet 'answers again' (%s)" % [t[:90] for t, _u in back])


def _self_test_server(ck, td, out, installer=True):
    """The disk lines, a missing package, a missing launcher, a '# root:' line, the CF status page's RSS, CF urgency."""
    os.makedirs(td)
    W = _World(os.path.join(td, "w"))
    env = W.env()
    for gb, low, very in ((15.1, False, False), (14.9, True, False), (8.1, True, False), (7.9, True, True)):
        W.disk_gb = gb
        rd = check_disk(env, {}, T_SAT)
        ck(("disk_low" in rd.opens) == low and ("disk_very_low" in rd.opens) == very
           and (not low or not rd.opens["disk_low"]["urgent"]) and (not very or rd.opens["disk_very_low"]["urgent"]),
           "disk %.1f GB free: %s" % (gb, "URGENT" if very else "an alert" if low else "nothing"))
    _world_files(W)
    W.versions.pop("numpy")
    rp = check_packages(env, {}, T_SAT)
    ck(set(rp.opens) == {"pkg|numpy"} and "is not installed" in rp.opens["pkg|numpy"]["body"]
       and "says exactly 2.5.4" in rp.opens["pkg|numpy"]["body"] and "5 of 6 match" in rp.detail,
       "a package missing on the server is drift, said with the version the list wants")
    os.remove(os.path.join(W.repo, "boot_all.ps1"))
    rl = check_launchers(env, {}, T_SAT)
    ck(set(rl.opens) == {"launcher|boot_all.ps1"} and "is missing" in rl.opens["launcher|boot_all.ps1"]["head"],
       "a launcher missing from the server is drift")
    other = os.path.join(td, "elsewhere")
    os.makedirs(other)
    with open(os.path.join(other, "pin_0925u.ps1"), "wb") as fh:
        fh.write(b"# deploy\r\n")
    with open(os.path.join(W.results, SUMS_REL), "w", encoding="utf-8") as fh:
        fh.write("# root: %s\n%s  pin_0925u.ps1\n" % (other, sha256(b"# deploy\r\n")))
    rl2 = check_launchers(env, {}, T_SAT)
    ck(rl2.opens == {} and "1 of 1 match" in rl2.detail, "a '# root: <dir>' line: relative paths are under that folder")
    # LIVE_PATHS.txt (11-08): each snapshot name -> the live file it is a copy of (both live files are restart_bot.ps1)
    hand_dir, repo_live = os.path.join(td, "kals-live-0925n"), os.path.join(td, "kals-repo")
    bodies = {hand_dir: b"# hand launcher\n\r\n", repo_live: b"# keep-alive launcher\r\n"}
    for d, body in bodies.items():
        os.makedirs(d)
        with open(os.path.join(d, "restart_bot.ps1"), "wb") as fh:
            fh.write(body)
    with open(os.path.join(W.results, SUMS_REL), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("%s  restart_bot_hand.ps1\n%s  restart_bot_repo.ps1\n" % (sha256(bodies[hand_dir]),
                                                                          sha256(bodies[repo_live])))
    live_map = os.path.join(W.results, LIVE_REL)
    hand_live, repo_file = os.path.join(hand_dir, "restart_bot.ps1"), os.path.join(repo_live, "restart_bot.ps1")
    with open(live_map, "w", encoding="utf-8") as fh:
        fh.write("# snapshot name  live path\nrestart_bot_repo.ps1  %s\nrestart_bot_hand.ps1  %s\n" % (repo_file, hand_live))
    rl3 = check_launchers(env, {}, T_SAT)
    ck(rl3.opens == {} and "2 of 2 match" in rl3.detail, "LIVE_PATHS.txt: each snapshot name is compared with the live "
                                                         "file it copies (both named restart_bot.ps1) -> 2 of 2 match")
    with open(hand_live, "ab") as fh:
        fh.write(b"# edited on the server\r\n")
    rl4 = check_launchers(env, {}, T_SAT)
    o4 = rl4.opens.get("launcher|restart_bot_hand.ps1") or {}
    ck(set(rl4.opens) == {"launcher|restart_bot_hand.ps1"} and "is not the snapshot" in o4.get("head", "")
       and hand_live in o4.get("head", "") and "1 of 2 match" in rl4.detail,
       "a live launcher edited after the snapshot -> drift, named by its live path")
    os.remove(repo_file)
    rl4b = check_launchers(env, {}, T_SAT)
    o4b = rl4b.opens.get("launcher|restart_bot_repo.ps1") or {}
    ck("is missing" in o4b.get("head", "") and repo_file in o4b.get("body", "") and "0 of 2 match" in rl4b.detail,
       "a live launcher gone -> 'is missing', with the live path it looked at")
    with open(live_map, "w", encoding="utf-8") as fh:
        fh.write("restart_bot_repo.ps1  %s\n" % repo_file)
    rl5 = check_launchers(env, {}, T_SAT)
    o5 = rl5.opens.get("launcher|restart_bot_hand.ps1") or {}
    ck("has no live path" in o5.get("head", "") and "compared with nothing" in o5.get("body", "")
       and not any(hand_live in str(v) for v in rl5.opens.values()),
       "a snapshot name LIVE_PATHS.txt does not list is a condition of its own, never compared with a wrong file")
    seen = []
    env_r = Env(results=W.results, repo=W.repo, log_path="", remap=lambda p: seen.append(p) or p)
    check_launchers(env_r, {}, T_SAT)
    ck(seen == [repo_file], "the live paths are read through Env.remap (the test hook; identity on the server)")
    os.remove(live_map)
    # CF Benchmarks: only an index pin settles on is urgent (the real titles of 11-07 are none of them)
    real_titles = ["CME CF Bitcoin Volatility Index - Settlement Publication Delay",
                   "CALCULATION FAILURE of CME CF Bitcoin Volatility Index - Real Time",
                   "CF Bitcoin Kraken Perpetual Funding Rate Index (KFRI) - Review of Published Index Value",
                   "APT_SRR Publication Delay and Republication", "Calculation Failure: UMAUSD_RTI",
                   "U_CMETHUSD_RTI Calculation Failure", "FIX interface connectivity problems",
                   "REST API Historical data delayed"]
    ours = ["BRTI publication delayed", "ETHUSD_RTI Calculation Failure", "Delay in calculating SOLUSD_RTI",
            "CME CF Bitcoin Real Time Index delayed", "CF Zcash-Dollar Real Time Index stale",
            "Publication Delay for 4pm London Prints: All Index Families", "CF Benchmarks Platform Issues"]
    ck(not any(names_our_index(t) for t in real_titles) and all(names_our_index(t) for t in ours)
       and names_our_index("Delay", "We are investigating a delay in HYPEUSD_RTI.")
       and not names_our_index("UMA delay", "the CF Benchmarks platform shows the rest are fine"),
       "CF incidents: urgent only for BRTI / a pin coin's RTI / all indices (%s)"
       % ([t for t in real_titles if names_our_index(t)] + [t for t in ours if not names_our_index(t)],))
    # the status page's RSS when incidents.json is gone
    W.cfb_src = "rss"
    bc = {}
    r0 = check_cfb_status(env, bc, T_SAT)
    W.incidents = [{"id": "inc9", "name": "BRTI publication delayed", "status": "investigating",
                    "created_at": "2026-11-07T21:50:00Z", "incident_updates": [{"body": "We are investigating."}]}
                   ] + W.incidents
    r1 = check_cfb_status(env, bc, T_SAT + 1800)
    ck(r0.status == "ok" and "history.rss" in r0.detail and len(r1.alerts) == 1 and r1.alerts[0]["urgent"]
       and "BRTI publication delayed" in r1.alerts[0]["head"], "CF status from its RSS: a new unresolved BRTI incident "
                                                              "-> URGENT (%s)" % r0.detail)
    W.cfb_src = "none"
    r2 = check_cfb_status(env, bc, T_SAT + 3600)
    ck(r2.status == "failed" and "could not read" in r2.detail, "CF status with neither source: the check fails")
    # a condition already open at the very first scan: in the baseline note (ONE message), which rings when it is urgent
    for gb, urgent in ((10.0, False), (7.0, True)):
        Wb = _World(os.path.join(td, "base%d" % int(gb)))
        _world_files(Wb)
        Wb.disk_gb = gb
        stb, phb = new_state(), _FakePhone()
        Wb.tick(T_SAT)
        scan(Wb.env(), stb, T_SAT)
        deliver(stb, phb, T_SAT)
        ck(len(phb.sent) == 1 and "baseline set" in phb.sent[0][0] and "Open already at this first scan" in phb.sent[0][0]
           and ("Server disk C: is down to %.1f GB free" % gb) in phb.sent[0][0] and phb.sent[0][1] == urgent
           and "disk_low" in stb["open"],
           "disk at %.0f GB at the first scan: ONE message, the baseline note listing it, %s" % (
               gb, "URGENT" if urgent else "quiet"))
    # a PDF that is not a PDF, or not there: a failed check (its streak counts)
    W.pdf[CONTRACT_PDF] = b"<html>moved</html>"
    rq = check_contract_pdf(env, {}, T_SAT)
    W.web_down = {CFB_PDF}
    rq2 = check_cfb_pdf(env, {}, T_SAT)
    ck(rq.status == "failed" and "not a PDF" in rq.detail and rq2.status == "failed",
       "a PDF that is not a PDF, or that does not answer: a failed check")
    # a server that stamps every copy (creation date, document id): no change; a PDF that really changes every read:
    # said 3 times (the 3rd says so, quietly), then only on /watch until it holds still
    W.web_down = set()
    bp = {}
    stamp = b"%%PDF-1.7\n1 0 obj << /CreationDate (D:2026110%d) /ModDate (D:2026110%d) >>\ntrailer << /ID [<%02d><%02d>] >>"
    for i in range(3):
        W.pdf[CONTRACT_PDF] = stamp % (i, i, i, i)
        rs = check_contract_pdf(env, bp, T_SAT + 1800 * i)
        ck(rs.alerts == [] and rs.status == "ok", "a PDF whose only change is its stamps: no change (copy %d)" % i)
    said = []
    for i in range(6):
        W.pdf[CONTRACT_PDF] = b"%PDF-1.7 body " + str(i).encode()
        said.append([a["urgent"] for a in check_contract_pdf(env, bp, T_SAT + 9000 + 1800 * i).alerts])
    W.pdf[CONTRACT_PDF] = b"%PDF-1.7 body 5"
    still = check_contract_pdf(env, bp, T_SAT + 30000)
    W.pdf[CONTRACT_PDF] = b"%PDF-1.7 body 6"
    again = check_contract_pdf(env, bp, T_SAT + 32000)
    ck(said == [[True], [True], [False], [], [], []] and still.alerts == [] and [a["urgent"] for a in again.alerts]
       == [True], "a PDF changing on every read: 2 urgent, a quiet 3rd that says so, then silence; after it holds "
                  "still, a change is urgent again (%s)" % said)


def _self_test_main(ck, td, out, installer=True):
    """main(): --dry-run, --once, the off switch, the self-test gate, a crash, the state saved before sending."""
    os.makedirs(td)
    W = _World(os.path.join(td, "w"))
    _world_files(W)
    env = W.env()
    ph = _FakePhone()
    sp = env.path(STATE_NAME)
    yes, no = (lambda *a, **k: True), (lambda *a, **k: False)
    saved_env = os.environ.pop("KALS_SELFTESTED", None)
    quiet = contextlib.redirect_stdout(io.StringIO())          # main()'s own log lines (planted failures among them)
    quiet.__enter__()
    try:
        rc = main(["--dry-run"], env=env, phone=ph, now=T_SAT, test=yes)
        ck(rc == 0 and not os.path.exists(sp) and len(ph.sent) == 1 and "baseline set" in ph.sent[0][0]
           and len(W.calls) == 20, "--dry-run: one scan, its message, NO state saved")
        rc = main(["--once"], env=env, phone=ph, now=T_SAT + 1800, test=yes)
        ck(rc == 0 and load_state(sp).get("runs") == 1, "--once: one scan, the state saved in %s" % STATE_NAME)
        rc = main([], env=env, phone=ph, now=T_SAT + 3600, test=yes)
        ck(rc == 0 and load_state(sp).get("runs") == 2, "no flag: the same (what the scheduled task runs)")
        with open(env.path(STOP_NAME), "w", encoding="utf-8") as fh:
            fh.write("operator /watch off")
        n0, c0 = len(ph.sent), len(W.calls)
        rc = main([], env=env, phone=ph, now=T_SAT + 5400, test=yes)
        ck(rc == 0 and len(ph.sent) == n0 and len(W.calls) == c0 and load_state(sp).get("runs") == 2,
           "the off switch (results\\%s): nothing scanned, nothing sent, nothing saved" % STOP_NAME)
        os.remove(env.path(STOP_NAME))
        n0, c0 = len(ph.sent), len(W.calls)
        rc = main([], env=env, phone=ph, now=T_SAT + 7200, test=no)
        rc2 = main([], env=env, phone=ph, now=T_SAT + 9000, test=no)
        ck(rc == 1 and rc2 == 1 and len(W.calls) == c0 and len(ph.sent) == n0 + 1
           and "self-test failed" in ph.sent[-1][0] and load_state(sp).get("runs") == 2,
           "a failing self-test: nothing scanned; said once a day (%d messages)" % (len(ph.sent) - n0))
        rc = main(["--test-send"], env=env, phone=ph, now=T_SAT)
        ck(rc == 0 and "TEST from the Kalshi watch" in ph.sent[-1][0], "--test-send: one test message")
        # the state is saved before the messages go: a phone that breaks keeps the scan
        W.disk_gb = 10.0                        # something to send
        ph.boom = True
        rc = main([], env=env, phone=ph, now=T_SAT + 10800, test=yes)
        ph.boom = False
        W.disk_gb = 40.0
        ck(rc == 1 and load_state(sp).get("runs") == 3, "a send that breaks: the scan's state was saved before it")
        # a crash (the state cannot be written): one note a day
        os.remove(sp)
        os.makedirs(sp)
        n0 = len(ph.sent)
        rc = main([], env=env, phone=ph, now=T_SAT + 12600, test=yes)
        rc2 = main([], env=env, phone=ph, now=T_SAT + 14400, test=yes)
        os.rmdir(sp)
        ck(rc == 1 and rc2 == 1 and len(ph.sent) == n0 + 1 and "its scan crashed" in ph.sent[-1][0],
           "a scan that crashes: said on the phone once a day (%d messages)" % (len(ph.sent) - n0))
    finally:
        quiet.__exit__(None, None, None)
        if saved_env is not None:
            os.environ["KALS_SELFTESTED"] = saved_env
    # save_state: retried while the file is held, then the error
    tries = []

    def held(a, b):
        tries.append(1)
        if len(tries) < 3:
            raise PermissionError("planted: /watch has the file open")
        os.replace(a, b)
    ck(save_state({"x": 1}, os.path.join(td, "s.json"), sleep=lambda s: None, replace=held) == 3
       and load_state(os.path.join(td, "s.json")) == {"x": 1}, "the state save is retried while the file is held")
    try:
        save_state({"x": 1}, os.path.join(td, "s.json"), sleep=lambda s: None,
                   replace=lambda a, b: (_ for _ in ()).throw(PermissionError("planted")))
        ck(False, "a save that never works raises")
    except OSError:
        ck(True, "a save that never works raises (the scan says it crashed)")


def replay_log(path, td, step_s=EVERY_MIN * 60):
    """check_pin_log over a copy of pin's real log `path`, written into td as pin wrote it (by its records' t) and
    scanned every step_s: [(now, alerts, opens)]. Nothing is sent; the real log is only read."""
    rows = []
    last = None
    with open(path, "rb") as fh:
        for ln in fh:
            try:
                d = json.loads(ln.decode("utf-8", "replace"))
                te = clock.utc_epoch(d.get("t")) if isinstance(d, dict) and d.get("t") else None
            except ValueError:
                te = None
            last = te if te is not None else last
            rows.append((last, ln if ln.endswith(b"\n") else ln + b"\n"))
    t0 = next((t for t, _ln in rows if t is not None), None)
    if t0 is None:
        return []
    rows = [(t if t is not None else t0, ln) for t, ln in rows]
    res = os.path.join(td, "results")
    os.makedirs(res)
    env = Env(results=res, repo=td, log_path="")
    dst = os.path.join(res, os.path.basename(path))
    base, out, i = {}, [], 0
    now = t0 + step_s
    end = rows[-1][0]                   # the last scan before the log's end (after it, pin's next run writes elsewhere)
    with open(dst, "ab") as fh:
        while now <= end:
            while i < len(rows) and rows[i][0] <= now:
                fh.write(rows[i][1])
                i += 1
            fh.flush()
            r = check_pin_log(env, base, now)
            out.append((now, r.alerts, r.opens))
            now += step_s
    return out


def _self_test_real_log(ck, td, out, path):
    """pin's real log through the pin-log check in 30-minute scans: what it would have said. The refused-hedge alarm
    must open exactly when some hour holds more than 5 refused hedges (counted here apart, by hedge_refused)."""
    os.makedirs(td)
    ts = []
    with open(path, "rb") as fh:
        for ln in fh:
            try:
                d = json.loads(ln.decode("utf-8", "replace"))
            except ValueError:
                continue
            if isinstance(d, dict) and hedge_refused(d) is not None and d.get("t"):
                ts.append(clock.utc_epoch(d["t"]))
    ts.sort()
    worst = max([sum(1 for y in ts if x - HEDGE_WINDOW_S < y <= x) for x in ts] or [0])
    res = replay_log(path, td)
    opened = [now for now, _a, o in res if "pin_hedge_4xx" in o]
    urgent = [(now, a["head"]) for now, al, _o in res for a in al if a["urgent"]]
    opens = sorted({k for _n, _a, o in res for k in o})
    print("    %s: %d scans; most refused hedges in an hour %d; refused-hedge alarm open on %d scans; urgent alerts %d; "
          "conditions ever open %s" % (os.path.basename(path), len(res), worst, len(opened), len(urgent), opens), file=out)
    for now, h in urgent[:8]:
        print("      urgent %s: %s" % (et(now), h), file=out)
    was = set()
    for now, _a, o in res:
        for k in sorted(set(o) - was):
            print("      opened %s: %s" % (et(now), o[k]["head"]), file=out)
        was = set(o)
    ck(bool(opened) == (worst > HEDGE_4XX_MAX), "%s: the refused-hedge alarm opens if and only if an hour holds more "
                                                "than 5 (most in an hour: %d)" % (os.path.basename(path), worst))
    ck(res and res[0][1] == [], "%s: the first scan says nothing one by one" % os.path.basename(path))


def main(argv, env=None, phone=None, now=None, test=None):
    """The command line. env / phone / now / test (the self-test function) are planted by the self-test; the scheduled
    task passes none of them."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--self-test" in argv or "--selftest" in argv:
        logs = [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "--log"]
        return 0 if self_test(True, installer=True, logs=logs) else 1
    env = env or Env()
    dry = "--dry-run" in argv or "--dry" in argv
    if phone is None:
        import pinrules_watch as _rw
        phone = _rw.Phone(dry=dry, log_fn=env.log)
    if "--test-send" in argv:
        ok = phone.send(
            "🧪 TEST from the Kalshi watch (kalshi_watch.py). Nothing happened in trading. Every %d minutes it scans "
            "Kalshi's changelog and answers, the contract and index documents, pin's log and the server, and tells you "
            "what changed. /watch shows every check." % EVERY_MIN, False, time.time() if now is None else now)
        env.log("test message %s" % ("sent" if ok else "NOT sent"))
        return 0 if ok else 1
    if os.path.exists(env.path(STOP_NAME)) and not dry:
        env.log("off: results\\%s is there (the phone's /watch off): nothing scanned, nothing sent" % STOP_NAME)
        return 0
    if os.environ.get("KALS_SELFTESTED") != "1":
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            good = (test or self_test)(False, installer=False)
        if not good:
            env.log("self-test FAILED: nothing scanned. " + buf.getvalue().replace("\n", " | ")[-1500:])
            sp = env.path(STATE_NAME)
            st = load_state(sp)
            for k, v in new_state().items():
                st.setdefault(k, v)
            t = time.time() if now is None else now
            queue(st, "selftest|%s" % clock.et_day(t), "the Kalshi watch's self-test failed",
                  "Its self-test failed, so it scanned nothing (results\\%s has the lines). Until it passes, Kalshi "
                  "changes are not watched." % LOG_NAME, False, "watch", t)
            deliver(st, phone, t, env.log)
            if not dry:
                try:
                    save_state(st, sp, sleep=env.sleep)
                except OSError:
                    env.log("state not saved after the failed self-test")
            return 1
    try:
        run(env, phone, now=now, dry=dry)
    except Exception as e:                                      # noqa: BLE001
        env.log("scan failed: " + traceback.format_exc().replace("\n", " | ")[-1500:])
        if not dry:
            try:
                crash_note(env, phone, time.time() if now is None else now, type(e).__name__)
            except Exception:                                   # noqa: BLE001
                env.log("crash note failed: " + traceback.format_exc().replace("\n", " | ")[-600:])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
