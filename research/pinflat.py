#!/usr/bin/env python3
"""pinflat.py -- is the live bot holding a bet right now? One answer, one source.

WHY THIS EXISTS. restart_bot.ps1 refused to restart while "filled orders >
settled records" in the newest live log. That is the right refusal while the
bot is ALIVE -- a deliberate restart mid-bet abandons the hedge and the loss
brake. But when the bot has DIED holding a bet, the settled record it would
have written never arrives, the count never balances, and the refusal is
permanent: the watchdog calls restart_bot every minute, restart_bot refuses
every minute, and the account stops trading until a human deletes a file.
That is the deadlock this file removes, and it is the one a two-hour exchange
outage at 3 AM would have walked straight into.

THE RULE.
  bot alive  : ANY fill without a settled record is HOLDING. Wait.
  bot dead   : a fill whose market has not yet CLOSED (plus a short grace) is
               HOLDING -- a new bot could buy the same close again and double
               the exposure the per-close budget exists to cap. A fill whose
               close has passed has settled on the exchange whether or not we
               logged it; nothing a new process could do about it. FLAT.

The close time is read from the ticker itself (KXBNB15M-26SEP161000-00 closes
2026-09-16 10:00Z), not from any log field, so a log that died mid-line still
answers. Fills are matched to settlements PER TICKER, because a hedge leg is a
second filled order on the same ticker and writes its own settled record.

AND KALSHI IS ASKED TOO (2026-11-07): when the log says FLAT and pin is
alive, a signed GET /portfolio/positions must agree (the "KALSHI'S OWN
ANSWER" block below says why, why not for a dead pin, and what happens when
Kalshi cannot answer).

Exit 0 = FLAT, 1 = HOLDING, 2 = could not tell (the caller decides; restart_bot
falls back to its old count). --json prints one machine-readable line.

    python research/pinflat.py --selftest
    python research/pinflat.py [--json] [--grace 180] [--no-kalshi]
"""
import argparse
import calendar
import glob
import json
import os
import re
import sys
import time

# 2026-11-07: research\ on the path even under `python -I` (which leaves the
# script's folder off it): downtime (the ET offset) and kauth (the Kalshi
# read) import from here. Appended, so it can never shadow a stdlib name.
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.append(HERE)

RESULTS = r"C:\kals-repo\results"
PIDFILE = os.path.join(RESULTS, "pinrun-live.pid")
GRACE_S = 180

_MON = {m.upper(): i for i, m in enumerate(calendar.month_abbr) if m}
_TK = re.compile(r"^[A-Z0-9]+-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})(?:-|$)")
# 2026-09-24: the HOURLY strike ladder (KXBTCD-26SEP2417-T95249.99). Its
# date field is yyMONddHH -- four digits after the month, not six -- and the
# close is the top of that Eastern hour. The strike follows as -T<price>.
# Tried ONLY when _TK fails: a 15M ticker has six digits there and the fifth
# and sixth are never "-T", so every answer _TK gave before is unchanged.
_TKH = re.compile(r"^[A-Z0-9]+-(\d{2})([A-Z]{3})(\d{2})(\d{2})-T")


def _et_offset(epoch):
    """Seconds to ADD to an Eastern wall-clock reading to get UTC... negated:
    downtime.et_offset gives UTC->ET (-14400 in summer)."""
    try:
        from downtime import et_offset
        return et_offset(epoch)
    except Exception:                                     # noqa: BLE001
        return _et_offset_rule(epoch)


def _et_offset_rule(epoch):
    """downtime.et_offset's rule, for when downtime cannot load (2026-11-07:
    this fell back to a FIXED -4 h, which in winter put every close an hour
    early -- 'closed' while it still had up to an hour to run). UTC-4 from
    the second Sunday of March 07:00Z to the first Sunday of November 06:00Z,
    else UTC-5."""
    y = time.gmtime(epoch).tm_year
    mar8 = calendar.timegm((y, 3, 8, 7, 0, 0))
    nov1 = calendar.timegm((y, 11, 1, 6, 0, 0))
    start = mar8 + ((6 - time.gmtime(mar8).tm_wday) % 7) * 86400
    end = nov1 + ((6 - time.gmtime(nov1).tm_wday) % 7) * 86400
    return -4 * 3600 if start <= epoch < end else -5 * 3600


def close_epoch(ticker):
    """UTC epoch of a 15-minute market's close, from its ticker. None if the
    ticker is not shaped like one.

    THE TICKER'S CLOCK IS EASTERN. KXXRP15M-26SEP170000-00 settled at
    2026-09-17T04:00:20Z: '26SEP17 0000' is midnight ET, which is 04:00Z.
    The first version read it as UTC and put every close four hours early --
    which for the dead-bot rule below would have called a market 'closed'
    while it still had up to four hours to run. Caught by the operator's
    day totals not matching the app's on 2026-09-17.
    """
    m = _TK.match(str(ticker or ""))
    if m:
        yy, mon, dd, hh, mm = m.groups()
    else:
        m = _TKH.match(str(ticker or ""))
        if not m:
            return None
        yy, mon, dd, hh = m.groups()
        mm = "00"                       # an hourly ladder closes on the hour
    mon_i = _MON.get(mon)
    if not mon_i:
        return None
    try:
        naive = calendar.timegm((2000 + int(yy), mon_i, int(dd), int(hh), int(mm), 0))
    except (ValueError, OverflowError):
        return None
    # naive is the ET wall clock read as if UTC; the true instant is later by
    # the (negative) offset. Two passes so a close near the DST switch lands
    # on the right side of it.
    e = naive - _et_offset(naive)
    return naive - _et_offset(e)


def pid_alive(pid):
    """Same semantics as pinrun._pid_alive: never reads a command line, and
    answers YES when it cannot tell. Reimplemented rather than imported so a
    restart check never imports the bot (kauth, sockets, 6,700 lines)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x00100000, False, pid)   # SYNCHRONIZE only
            if h:
                k32.CloseHandle(h)
                return True
            return k32.GetLastError() == 5                # exists, not ours
        except Exception:                                 # noqa: BLE001
            return True
    try:
        os.kill(pid, 0)
        return True
    except OSError as e:
        import errno
        return getattr(e, "errno", None) == errno.EPERM


def live_pid(pidfile=PIDFILE):
    try:
        with open(pidfile, encoding="utf-8") as fh:
            return int((fh.read() or "0").strip() or 0) or None
    except (OSError, ValueError):
        return None


def _mtime0(path):
    """A file's modified time, 0 once it has gone: log_rotate.py may archive an OLD log between the listing and
    this look (2026-11-07); the newest one is never archived."""
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def newest_log(results=RESULTS):
    logs = glob.glob(os.path.join(results, "pinrun-live-*.jsonl"))
    if not logs:
        return None
    return max(logs, key=_mtime0)


def _filled(rec):
    try:
        return float(rec.get("filled") or 0) > 0
    except (TypeError, ValueError):
        return False


def positions(rows):
    """{ticker: fills - settlements} for every ticker that is net open."""
    fills, done = {}, {}
    for r in rows:
        k = r.get("kind")
        tk = r.get("ticker")
        if not tk:
            continue
        if k == "order" and _filled(r):
            fills[tk] = fills.get(tk, 0) + 1
        elif k == "hedge":
            # a hedge record carries `n` (contracts) and `status`, not `filled`
            try:
                hedged = float(r.get("n") or 0) > 0 and str(r.get("status", "")) == "executed"
            except (TypeError, ValueError):
                hedged = False
            if hedged or _filled(r):
                fills[tk] = fills.get(tk, 0) + 1
        elif k == "settled":
            done[tk] = done.get(tk, 0) + 1
    out = {}
    for tk, n in fills.items():
        open_n = n - done.get(tk, 0)
        if open_n > 0:
            out[tk] = open_n
    return out


def read_rows(path):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue                  # a line cut off by a crash
    return rows


def verdict(rows, alive, now=None, grace=GRACE_S):
    """(status, detail). status in FLAT / HOLDING."""
    now = time.time() if now is None else now
    open_pos = positions(rows)
    if not open_pos:
        return "FLAT", {"open": {}, "alive": alive, "why": "every fill has settled"}
    if alive:
        return "HOLDING", {"open": open_pos, "alive": True,
                           "why": "bot is alive and holding %d open fill(s)"
                                  % sum(open_pos.values())}
    ahead = {}
    for tk, n in open_pos.items():
        c = close_epoch(tk)
        if c is None or c + grace > now:
            ahead[tk] = {"n": n, "closes_in_s": None if c is None else int(c - now)}
    if ahead:
        return "HOLDING", {"open": ahead, "alive": False,
                           "why": "bot is dead but %d market(s) have not closed yet; "
                                  "a new bot could buy the same close twice" % len(ahead)}
    return "FLAT", {"open": {}, "alive": False, "unlogged": open_pos,
                    "why": "bot is dead; %d fill(s) never logged a settlement but "
                           "their markets closed over %ds ago -- settled on the "
                           "exchange, nothing to double" % (sum(open_pos.values()), grace)}


def check(results=RESULTS, pidfile=PIDFILE, now=None, grace=GRACE_S):
    pid = live_pid(pidfile)
    alive = bool(pid) and pid_alive(pid)
    log = newest_log(results)
    if not log:
        return "FLAT", {"open": {}, "alive": alive, "pid": pid, "log": None,
                        "why": "no live log at all"}
    st, d = verdict(read_rows(log), alive, now=now, grace=grace)
    d.update(pid=pid, log=os.path.basename(log))
    return st, d


# --------------------------------------------------------------------------
# KALSHI'S OWN ANSWER (2026-11-07).
#
# WHY. Everything above reads pin's log. If a fill never reached the log (a
# write that failed, a disk that filled, a crash between the order and its
# line), the log check says FLAT while pin holds a bet -- and restart_bot then
# restarts pin, which abandons that bet's hedge and its loss brake. So when the
# log says FLAT, Kalshi is asked too: a signed GET /portfolio/positions for
# pin's main account (subaccount 0, the one pin trades; kauth.get, the signer
# pin uses; GET only). NOT FLAT if EITHER says not flat: any position with a
# nonzero position_fp on a 15-minute market (KX...15M-) or the hourly BTC
# ladder (KXBTCD-) whose close is ahead or within the last GRACE_S seconds.
# A position in another series is not pin's to wait for.
#
# ONLY WHILE PIN IS ALIVE (2026-11-07 review). The hole is a restart that
# KILLS a running pin mid-bet (a deploy, /approve pinrestart). When pin is
# already DEAD (the watchdog's restart), refusing helps nobody: the position
# rides with no hedge until its close (up to ~15 min on a 15M market, ~1 h on
# KXBTCD), while a new pin's v-safety2 startup read adopts a position its
# books lack and hedges it. So a dead pin is restarted on the log's answer
# and Kalshi is not asked (no wait either). pid_alive answers YES when it
# cannot tell, so an unreadable process table still asks Kalshi.
#
# WHEN KALSHI CANNOT ANSWER: 4 reads (the first and 3 retries, 2 + 3 + 5 =
# 10 s apart), each cut off after KALSHI_TIMEOUT_S, and never more than
# KALSHI_BUDGET_S in all, then the log's answer alone with a WARNING line
# before it that says how many tries and how long they took -- so a Kalshi
# outage costs a restart ~30 s (40 s at most) and never blocks every restart
# forever (the deadlock the module docstring is about). The log says
# HOLDING: Kalshi is not asked at all (the answer is already "wait"). Exit
# codes and the verdict line are unchanged: restart_bot.ps1 and
# results\pin_*.ps1 read exit 0 / 1 / 2, and laptop_handover.ps1 reads the
# LAST line starting "FLAT", so a warning always comes BEFORE the verdict
# line. Every printed line is ASCII-safe: the server's Python writes a pipe
# in cp1252, and one character it cannot show would crash the print, exit 1
# and read as HOLDING on every restart while that error text lasted.
# --------------------------------------------------------------------------
KALSHI_SERIES = re.compile(r"^KX[A-Z0-9]*15M-|^KXBTCD-")
KALSHI_WAITS = (2.0, 3.0, 5.0)          # between the 4 reads: ~10 s in all
KALSHI_TIMEOUT_S = 5.0                  # one read waits at most this long (kauth's own is 20 s)
KALSHI_BUDGET_S = 40.0                  # the whole Kalshi check (reads + waits) stops retrying past this
KALSHI_PAGES = 5
KALSHI_PATH = "/portfolio/positions"
KALSHI_PARAMS = {"subaccount": 0, "count_filter": "position", "settlement_status": "unsettled", "limit": 200}


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def kalshi_open(rows, now, grace=GRACE_S):
    """{ticker: {"n": net contracts, "closes_in_s": s or None}} for every row of
    market_positions that keeps pin NOT flat (see the block above). A row whose
    position cannot be read is skipped; one in pin's series whose close cannot
    be read from its ticker counts as open (the safe side)."""
    out = {}
    for x in rows:
        if not isinstance(x, dict):
            continue
        tk = str(x.get("ticker") or x.get("market_ticker") or "")
        if not KALSHI_SERIES.match(tk):
            continue
        n = _num(x.get("position_fp"))
        if n is None:
            n = _num(x.get("position"))
        if n is None or abs(n) < 1e-9:
            continue
        c = close_epoch(tk)
        if c is None or c + grace > now:
            out[tk] = {"n": n, "closes_in_s": None if c is None else int(c - now), "from": "kalshi"}
    return out


def _ascii(s):
    """Text any console can print: a character outside ASCII becomes its \\x / \\u escape."""
    return str(s).encode("ascii", "backslashreplace").decode("ascii")


def kalshi_read(getter, now, grace=GRACE_S, sleep=time.sleep, waits=KALSHI_WAITS, clock=time.monotonic,
                budget=KALSHI_BUDGET_S):
    """("ok", {open}, reads, seconds) or ("failed", why, reads, seconds). Every
    page of the listing must read, or the whole read is tried again; no retry
    starts once the reads and waits so far would pass `budget` seconds.
    `seconds` = the waits plus the time the reads took (what it cost a restart)."""
    from urllib.parse import quote
    why = "no read"
    reads = 0
    spent = 0.0
    for i in range(len(waits) + 1):
        if i:
            if spent + waits[i - 1] > budget:
                why = "%s; no more tries: %.0f s spent, the limit is %.0f s" % (why, spent, budget)
                break
            sleep(waits[i - 1])
            spent += waits[i - 1]
        reads += 1
        rows, why = [], None
        params = dict(KALSHI_PARAMS)
        for _page in range(KALSHI_PAGES):
            t0 = clock()
            try:
                st, body = getter(KALSHI_PATH, params)
            except Exception as e:                        # noqa: BLE001
                st, body = -1, "%s: %s" % (type(e).__name__, e)
            spent += max(0.0, clock() - t0)
            if st != 200 or not isinstance(body, dict) or not isinstance(body.get("market_positions"), list):
                why = "HTTP %s: %s" % (st, _ascii(str(body)[:120]))
                break
            got = body["market_positions"]
            rows += got
            cur = body.get("cursor")
            if not cur or not got:
                break
            # kauth.get joins the query as given: a cursor holding + / = & must be sent encoded
            params = dict(KALSHI_PARAMS, cursor=quote(str(cur), safe=""))
        else:
            why = "more than %d pages of positions" % KALSHI_PAGES
        if why is None:
            return "ok", kalshi_open(rows, now, grace), reads, spent
    return "failed", why, reads, spent


def kalshi_getter(timeout=KALSHI_TIMEOUT_S):
    """(getter, None) -- kauth.get, the signed GET pin uses, cut off after
    `timeout` s on a daemon thread (a late answer is dropped, never used) -- or
    (None, why) when kauth cannot load (no key file on this machine)."""
    try:
        import kauth
    except Exception as e:                                # noqa: BLE001
        return None, "kauth could not load (%s: %s)" % (type(e).__name__, _ascii(str(e)[:80]))

    def get(path, params):
        import threading
        box = {}

        def run():
            try:
                box["r"] = kauth.get(path, params)
            except Exception as e:                        # noqa: BLE001
                box["r"] = (-1, "%s: %s" % (type(e).__name__, e))
        th = threading.Thread(target=run, name="pinflat-kalshi", daemon=True)
        th.start()
        th.join(timeout)
        return box.get("r") or (-1, "no answer in %.0f s" % timeout)
    return get, None


def truthful(grace=GRACE_S, getter=None, now=None, sleep=time.sleep, results=RESULTS, pidfile=PIDFILE,
             use_kalshi=True, make_getter=kalshi_getter):
    """(status, detail, warning): the log check and, when it says FLAT,
    Kalshi's positions. status FLAT / HOLDING / UNKNOWN (the log check failed
    and Kalshi did not say HOLDING). warning is None or one line to print
    BEFORE the verdict."""
    now = time.time() if now is None else now
    try:
        st, d = check(results=results, pidfile=pidfile, now=now, grace=grace)
    except Exception as e:                                # noqa: BLE001
        st, d = "UNKNOWN", {"err": str(e)[:200], "why": "the log check failed: %s" % str(e)[:120]}
        try:                                              # still known: is pin alive (the dead-pin rule below)
            pid = live_pid(pidfile)
            d.update(pid=pid, alive=bool(pid) and pid_alive(pid))
        except Exception:                                 # noqa: BLE001
            pass
    if not use_kalshi:
        d["kalshi"] = {"asked": False, "why": "--no-kalshi"}
        return st, d, None
    if st == "HOLDING":
        d["kalshi"] = {"asked": False, "why": "the log already says HOLDING"}
        return st, d, None
    if d.get("alive") is False:
        # the block above: a dead pin is restarted at once; its successor adopts and hedges what Kalshi holds
        d["kalshi"] = {"asked": False, "why": "pin is not running: a restart now lets the new pin adopt and hedge any "
                                              "position its log missed (v-safety2); waiting would leave it unhedged"}
        return st, d, None
    if getter is None:
        getter, why = make_getter()
        if getter is None:
            d["kalshi"] = {"asked": False, "why": why}
            return st, d, "WARNING: Kalshi not asked (%s); this answer is from pin's log alone" % why
    k, got, reads, spent = kalshi_read(getter, now, grace, sleep)
    if k != "ok":
        d["kalshi"] = {"asked": True, "ok": False, "reads": reads, "seconds": round(spent, 1), "why": got}
        return st, d, ("WARNING: Kalshi's positions could not be read (%d %s in %.0f s; last: %s); this "
                       "answer is from pin's log alone" % (reads, "try" if reads == 1 else "tries", spent, got))
    d["kalshi"] = {"asked": True, "ok": True, "reads": reads, "seconds": round(spent, 1), "open": got}
    if got:
        log_why = d.get("why")
        d["open"] = got
        d["why"] = ("Kalshi shows %d open position(s) on pin's markets that %s (the log: %s)"
                    % (len(got), "the log does not" if st == "FLAT" else "settle the question", log_why))
        return "HOLDING", d, None
    if st == "FLAT":
        d["why"] = "%s; Kalshi agrees (no open position on a 15-minute or hourly BTC market)" % d.get("why")
    return st, d, None


# --------------------------------------------------------------------------
def selftest_kalshi(ck):
    """The Kalshi half, on a fake wire: no network, no key (kauth is never imported here)."""
    import tempfile
    now = calendar.timegm((2026, 11, 7, 15, 5, 0))         # 10:05 AM EST = 15:05Z
    ahead = "KXBTC15M-26NOV071015-15"                       # closes 10:15 AM ET = 15:15Z
    hourly = "KXBTCD-26NOV0711-T101999.99"                  # closes 11:00 AM ET = 16:00Z
    just = "KXETH15M-26NOV071004-04"                        # not a real close: 10:04 ET, 60 s ago
    past = "KXSOL15M-26NOV071000-00"                        # closed 10:00 AM ET, 300 s ago

    class Wire:
        """GET /portfolio/positions answered from `pages` (a list of bodies, or a status int to fail with)."""

        def __init__(self, pages):
            self.pages, self.calls = list(pages), []

        def __call__(self, path, params):
            self.calls.append((path, dict(params)))
            p = self.pages.pop(0) if self.pages else 500
            if isinstance(p, tuple):
                return p                                    # (status, body) as given
            return (p, {"error": "x"}) if isinstance(p, int) else (200, p)

    def pos(tk, n):
        return {"ticker": tk, "position_fp": "%.2f" % n, "market_exposure_dollars": "1.00"}

    slept = []
    rows = [pos(ahead, 85), pos(hourly, 1), pos(just, -40), pos(past, 12), pos("KXETH15M-26NOV071015-15", 0),
            pos("KXINXD-26NOV07H1600-T6000", 5), pos("KXETHD-26NOV0711-T3000", 3), {"ticker": "KXXRP15M-x", "position_fp": "2"}]
    got = kalshi_open(rows, now)
    ck(set(got) == {ahead, hourly, just, "KXXRP15M-x"} and got[just]["n"] == -40 and got[ahead]["closes_in_s"] == 600
       and got["KXXRP15M-x"]["closes_in_s"] is None,
       "KALSHI: open = 15M and KXBTCD with a nonzero position, close ahead or within 180 s (a NO position "
       "counts; 0.00, other series, a close 300 s past do not; an unreadable close counts as open)")
    w = Wire([{"market_positions": [pos(ahead, 85)], "cursor": ""}])
    k, o, n, _s = kalshi_read(w, now, sleep=slept.append)
    ck(k == "ok" and set(o) == {ahead} and n == 1 and not slept and w.calls[0][0] == "/portfolio/positions"
       and w.calls[0][1]["subaccount"] == 0 and w.calls[0][1]["settlement_status"] == "unsettled",
       "KALSHI: one signed read of pin's main account (subaccount 0, unsettled positions)")
    w = Wire([{"market_positions": [pos(past, 1)] * 200, "cursor": "c2"},
              {"market_positions": [pos(hourly, 2)], "cursor": None}])
    k, o, n, _s = kalshi_read(w, now, sleep=slept.append)
    ck(k == "ok" and set(o) == {hourly} and w.calls[1][1].get("cursor") == "c2", "KALSHI: a second page is read")
    w = Wire([{"market_positions": [pos(past, 1)], "cursor": "a+b/c=d&e"}, {"market_positions": [], "cursor": None}])
    k, o, n, _s = kalshi_read(w, now, sleep=slept.append)
    ck(k == "ok" and w.calls[1][1].get("cursor") == "a%2Bb%2Fc%3Dd%26e",
       "KALSHI: a cursor holding + / = & is sent URL-encoded (kauth.get joins the query as given)")
    w = Wire([500, 503, {"market_positions": [], "cursor": None}])
    k, o, n, s = kalshi_read(w, now, sleep=slept.append)
    ck(k == "ok" and o == {} and n == 3 and slept == [2.0, 3.0] and abs(s - 5.0) < 0.5,
       "KALSHI: two failures then an answer: 3 reads, 5 s of waits")
    del slept[:]
    w = Wire([500, 500, {"no": "list"}, 429])
    k, why, n, s = kalshi_read(w, now, sleep=slept.append)
    ck(k == "failed" and n == 4 and slept == [2.0, 3.0, 5.0] and "429" in why and abs(s - 10.0) < 0.5,
       "KALSHI: 4 failed reads (a body without the list is a failure) over 2 + 3 + 5 = 10 s, then it gives up")
    del slept[:]

    class Endless:
        """A listing that never ends: every page full, with a next cursor."""

        def __init__(self):
            self.n = 0

        def __call__(self, path, params):
            self.n += 1
            return 200, {"market_positions": [pos(past, 1)] * 200, "cursor": "p%d" % self.n}
    e = Endless()
    k, why, n, s = kalshi_read(e, now, sleep=slept.append)
    ck(k == "failed" and "more than %d pages" % KALSHI_PAGES in why and n == 4 and e.n == 4 * KALSHI_PAGES,
       "KALSHI: more than %d pages is a FAILED read (never a partial list read as flat), 4 tries" % KALSHI_PAGES)
    del slept[:]
    tick = [0.0]

    def slow(path, params):                                 # every read takes 12 s (a fake clock)
        tick[0] += 12.0
        return 503, {"error": "slow"}
    k, why, n, s = kalshi_read(slow, now, sleep=slept.append, clock=lambda: tick[0])
    ck(k == "failed" and n == 3 and slept == [2.0, 3.0] and "no more tries" in why and s <= KALSHI_BUDGET_S + 1,
       "KALSHI: reads of 12 s each stop at the %.0f s budget (3 reads + 5 s of waits = 41 s; a 4th would pass it)"
       % KALSHI_BUDGET_S)
    del slept[:]
    ck(KALSHI_TIMEOUT_S == 5.0 and kalshi_getter.__defaults__ == (KALSHI_TIMEOUT_S,)
       and 4 * KALSHI_TIMEOUT_S + sum(KALSHI_WAITS) <= KALSHI_BUDGET_S <= 60,
       "KALSHI: one read waits at most 5 s, so a hung Kalshi costs 4 x 5 + 10 = 30 s, inside the 40 s budget "
       "(watch_bot gives restart_bot 180 s)")
    ck(_ascii("snow \u2603 caf\xe9") == "snow \\u2603 caf\\xe9", "_ascii: a character outside ASCII prints as its escape")

    def order(tk, filled):
        return {"kind": "order", "ticker": tk, "filled": filled, "status": "executed"}

    with tempfile.TemporaryDirectory() as td:
        pf = os.path.join(td, "pinrun-live.pid")
        with open(pf, "w") as fh:
            fh.write(str(os.getpid()))                     # alive
        lp = os.path.join(td, "pinrun-live-20261107T051700Z.jsonl")
        with open(lp, "w") as fh:
            fh.write(json.dumps({"kind": "start"}) + "\n")  # the log holds NO fill: it says FLAT

        def go(wire, **kw):
            del slept[:]
            return truthful(getter=wire, now=now, sleep=slept.append, results=td, pidfile=pf, **kw)

        st, d, warn = go(Wire([{"market_positions": [pos(ahead, 85)]}]))
        ck(st == "HOLDING" and warn is None and ahead in d["open"] and "the log does not" in d["why"],
           "THE GAP: the log says FLAT, Kalshi holds 85 contracts on a market 10 min from its close -> HOLDING")
        lines = []
        ck(emit(st, d, warn, out=lines.append) == 1 and lines[0].startswith("HOLDING -- Kalshi shows 1 open")
           and lines[1].startswith("    open: " + ahead), "...exit 1, the verdict line first, then the position")
        st, d, warn = go(Wire([{"market_positions": [pos(past, 12)]}]))
        lines = []
        ck(st == "FLAT" and emit(st, d, warn, out=lines.append) == 0 and len(lines) == 1
           and lines[0].startswith("FLAT -- ") and "Kalshi agrees" in lines[0],
           "both agree FLAT (a position on a market closed 300 s ago is settling, not pin's to wait for) -> exit 0")
        st, d, warn = go(Wire([500, 500, 500, 500]))
        lines = []
        ck(st == "FLAT" and emit(st, d, warn, out=lines.append) == 0 and lines[0].startswith("WARNING: Kalshi")
           and "(4 tries in 10 s;" in lines[0] and lines[-1].startswith("FLAT -- ") and slept == [2.0, 3.0, 5.0],
           "KALSHI DOWN: after 4 tries in 10 s, the log's answer with a WARNING line BEFORE it that says so (the "
           "last line still starts FLAT, as laptop_handover reads it): %r" % (lines[:1],))
        st, d, warn = go(Wire([(503, {"error": "snow \u2603 down"})] * 4))
        d["why"] = d["why"] + " caf\xe9"
        strict = []
        ck(st == "FLAT" and "snow \\u2603" in warn
           and emit(st, d, warn + " \u2603", out=lambda s: strict.append(s.encode("cp1252"))) == 0
           and len(strict) == 2 and all(b.decode("ascii") for b in strict) and b"snow \\u2603" in strict[0]
           and strict[0].endswith(b" \\u2603") and strict[1].endswith(b" caf\\xe9 (pid %d, pinrun-live-20261107T051700Z"
                                                                      b".jsonl)" % os.getpid()),
           "every printed line is ASCII: Kalshi's error text with a snowman reaches a cp1252 pipe (the server's) "
           "as its escape, never a crash")

        def boom(s):
            raise UnicodeEncodeError("cp1252", "x", 0, 1, "planted")
        ck(safe_emit("HOLDING", d, None, out=boom) == 1 and safe_emit("FLAT", d, None, out=boom) == 2,
           "a print that fails anyway: HOLDING still exits 1, FLAT becomes 2 (could not tell), never a silent FLAT")
        st, d, warn = truthful(getter=None, now=now, sleep=slept.append, results=td, pidfile=pf,
                               make_getter=lambda: (None, "no key file"))
        ck(st == "FLAT" and warn and "no key file" in warn and d["kalshi"]["asked"] is False,
           "NO KEY on this machine: the log's answer and a warning, no wait")
        with open(pf, "w") as fh:
            fh.write("999999999")                          # pin is DEAD (not a real pid on any box)
        w = Wire([{"market_positions": [pos(ahead, 85)]}])
        st, d, warn = go(w)
        ck(st == "FLAT" and not w.calls and d["kalshi"]["asked"] is False and "not running" in d["kalshi"]["why"]
           and warn is None and not slept,
           "pin DEAD (the watchdog's restart): Kalshi is not asked and nothing waits -- the new pin adopts and "
           "hedges what Kalshi holds (v-safety2) instead of the bet riding unhedged to its close")
        with open(pf, "w") as fh:
            fh.write(str(os.getpid()))                     # alive again
        with open(lp, "a") as fh:
            fh.write(json.dumps(order(ahead, 85)) + "\n")   # now the log holds an open fill
        w = Wire([{"market_positions": []}])
        st, d, warn = go(w)
        ck(st == "HOLDING" and not w.calls and d["kalshi"]["asked"] is False,
           "the log says HOLDING: Kalshi is not asked at all (the answer is already wait)")
        st, d, warn = go(Wire([]), use_kalshi=False)
        ck(st == "HOLDING" and d["kalshi"]["why"] == "--no-kalshi", "--no-kalshi: the log check alone")
        os.remove(lp)
        os.makedirs(lp)                                    # the newest 'log' cannot be read: the log check fails
        st, d, warn = go(Wire([{"market_positions": [pos(hourly, 1)]}]))
        lines = []
        ck(st == "HOLDING" and emit(st, d, warn, out=lines.append) == 1,
           "the log check FAILS and Kalshi holds a bet -> HOLDING (exit 1), not 'could not tell'")
        st, d, warn = go(Wire([{"market_positions": []}]))
        lines = []
        ck(st == "UNKNOWN" and emit(st, d, warn, out=lines.append) == 2 and lines[0].startswith("pinflat: could not tell"),
           "the log check fails and Kalshi holds nothing -> exit 2 as before (restart_bot falls back to its count)")
        with open(pf, "w") as fh:
            fh.write("999999999")                          # pin DEAD, and the log check fails
        w = Wire([{"market_positions": [pos(hourly, 1)]}])
        st, d, warn = go(w)
        ck(st == "UNKNOWN" and not w.calls and d["alive"] is False,
           "the log check fails with pin DEAD: Kalshi is not asked either (exit 2: restart_bot's own count decides)")
        with open(pf, "w") as fh:
            fh.write(str(os.getpid()))
        lines = []
        emit("HOLDING", {"why": "x", "pid": 1, "log": "l", "open": {ahead: {"n": 1}}}, None, as_json=True,
             out=lines.append)
        ck(json.loads(lines[0])["status"] == "HOLDING" and len(lines) == 1, "--json: one machine-readable line")
    # the real getter's wrapper, around a stand-in kauth (removed again: the real one is never imported here)
    import types
    fake = types.ModuleType("kauth")
    fake.calls = []

    def _get(path, params=None):
        fake.calls.append((path, params))
        if params and params.get("cursor") == "slow":
            time.sleep(0.5)
        return 200, {"market_positions": []}
    fake.get = _get
    sys.modules["kauth"] = fake
    try:
        g, why = kalshi_getter(timeout=0.1)
        ck(g is not None and g("/portfolio/positions", {"subaccount": 0}) == (200, {"market_positions": []})
           and fake.calls[0][0] == "/portfolio/positions", "the real getter: kauth.get, the answer passed through")
        t0 = time.time()
        st9, b9 = g("/portfolio/positions", {"cursor": "slow"})
        ck(st9 == -1 and "no answer" in b9 and time.time() - t0 < 0.4,
           "...and a read that hangs is cut off at the timeout (a late answer is dropped)")
    finally:
        sys.modules.pop("kauth", None)
    ck("kauth" not in sys.modules, "the self-test never loaded kauth (no key was read)")
    # the command line, end to end, as restart_bot runs it (log check only: a self-test never reads Kalshi)
    import subprocess
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "pinrun-live-20261107T051700Z.jsonl"), "w") as fh:
            fh.write(json.dumps({"kind": "start"}) + "\n")
        r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--no-kalshi", "--results", td],
                           capture_output=True, text=True, timeout=60)
        ck(r.returncode == 0 and r.stdout.startswith("FLAT -- ") and r.stderr == "",
           "the command line: exit 0, the verdict on stdout, NOTHING on stderr (restart_bot runs it 2>&1 under "
           "ErrorActionPreference Stop) -- got exit %s, stderr %r" % (r.returncode, r.stderr[:80]))
        selftest_main(ck, td)


# main() WITH the Kalshi read, in a child `python -I` (the server's pipe: cp1252 stdout), through a stand-in kauth
# planted in sys.modules before pinflat loads -- the real kauth (and the key) is never imported. The stand-in writes
# to stderr (with a character cp1252 cannot show) and raises a warning on every read, as a library might.
_MAIN_DRIVER = r"""
import sys, time, types, warnings, importlib.util
path, mode, tk = sys.argv[1], sys.argv[2], sys.argv[3]
time.sleep = lambda s: None                      # the retry waits, before pinflat binds time.sleep
fake = types.ModuleType("kauth")
def get(p, params=None):
    sys.stderr.write("stand-in kauth on stderr \u2603\n")
    warnings.warn("stand-in kauth warning")
    if mode == "down":
        return 503, {"error": "snow \u2603 down"}
    return 200, {"market_positions": [{"ticker": tk, "position_fp": "85.00"}] if mode == "hold" else []}
fake.get = get
sys.modules["kauth"] = fake
spec = importlib.util.spec_from_file_location("pinflat_under_test", path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
sys.exit(m.main(sys.argv[4:]))
"""


def selftest_main(ck, td):
    """The command line's Kalshi path, end to end (`td` holds a FLAT log)."""
    import subprocess
    pf = os.path.join(td, "pinrun-live.pid")

    def run(mode, tk, *args, alive=True):
        with open(pf, "w") as fh:
            fh.write(str(os.getpid()) if alive else "999999999")      # this test's own pid is alive
        return subprocess.run([sys.executable, "-I", "-c", _MAIN_DRIVER, os.path.abspath(__file__), mode, tk,
                               "--results", td] + list(args), capture_output=True, timeout=120)

    def lines(r):
        return r.stdout.decode("ascii").splitlines()            # ASCII, or this raises (and the check fails)

    t = time.time()
    c = t + 600
    ahead = "KXBTC15M-%s-00" % time.strftime("%y%b%d%H%M", time.gmtime(c + _et_offset(c))).upper()
    j = (int(t) // 60) * 60 - 60                                 # a close 60 to 119 s ago
    just = "KXETH15M-%s-00" % time.strftime("%y%b%d%H%M", time.gmtime(j + _et_offset(j))).upper()
    ck(close_epoch(just) == j and abs(close_epoch(ahead) - (int(c) // 60) * 60) < 1, "main: the planted tickers "
                                                                                       "close where they should")
    r = run("hold", ahead)
    ls = lines(r)
    ck(r.returncode == 1 and r.stderr == b"" and any(x.startswith("HOLDING -- Kalshi shows 1 open") for x in ls)
       and ls[-1].startswith("    open: " + ahead),
       "main() ASKS KALSHI by default: the log says FLAT, Kalshi holds 85 -> exit 1 HOLDING, nothing on stderr "
       "(the stand-in's stderr line and warning went to stdout or nowhere): exit %s, stderr %r"
       % (r.returncode, r.stderr[:120]))
    ck(any("stand-in kauth on stderr \\u2603" in x for x in ls),
       "main(): a library's stderr line comes out on stdout, a character cp1252 cannot show as its escape")
    r = run("down", ahead)
    ls = lines(r)
    ck(r.returncode == 0 and r.stderr == b"" and any(x.startswith("WARNING: Kalshi's positions could not be read (4 "
                                                                 "tries in") for x in ls)
       and any("snow \\u2603 down" in x for x in ls) and ls[-1].startswith("FLAT -- "),
       "main(): Kalshi down with a snowman in its error -> a WARNING line, then FLAT (exit 0), no crash: exit %s %r"
       % (r.returncode, ls[-1:]))
    r0, r1 = run("hold", just), run("hold", just, "--grace", "0")
    ck(r0.returncode == 1 and r1.returncode == 0 and lines(r1)[-1].startswith("FLAT -- "),
       "main(): --grace reaches the Kalshi rule (a market closed 60-119 s ago: HOLDING with 180 s, FLAT with 0): "
       "exits %s / %s" % (r0.returncode, r1.returncode))
    r = run("hold", ahead, alive=False)
    ls = lines(r)
    ck(r.returncode == 0 and not any("stand-in" in x for x in ls) and ls[-1].startswith("FLAT -- "),
       "main(): pin DEAD -> FLAT at once, Kalshi never asked (the new pin adopts the position)")
    r = run("hold", ahead, "--no-kalshi")
    ck(r.returncode == 0 and b"stand-in" not in r.stdout, "main(): --no-kalshi never asks")


def selftest():
    import tempfile

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinflat selftest: FAILED -- " + msg)

    # ticker -> close. THE TICKER CLOCK IS EASTERN: the live log settled
    # KXBNB15M-26SEP161000-00 at 2026-09-16T14:00:20Z and
    # KXXRP15M-26SEP170000-00 at 2026-09-17T04:00:20Z.
    ck(close_epoch("KXBNB15M-26SEP161000-00") == calendar.timegm((2026, 9, 16, 14, 0, 0)),
       "26SEP161000 is 10:00 AM ET = 14:00Z (the live log settled it at 14:00:20Z)")
    ck(close_epoch("KXXRP15M-26SEP170000-00") == calendar.timegm((2026, 9, 17, 4, 0, 0)),
       "26SEP170000 is midnight ET = 04:00Z, NOT 00:00Z")
    ck(close_epoch("KXBTC15M-26JAN151200-00") == calendar.timegm((2026, 1, 15, 17, 0, 0)),
       "and in January the offset is five hours")
    ck(close_epoch("garbage") is None and close_epoch(None) is None,
       "NULL: a non-ticker has no close")
    # 2026-11-07: the fallback when downtime cannot load is the same rule, not a fixed -4 h
    from downtime import et_offset as _dt_off
    probes = [calendar.timegm((y, m, d, h, 0, 0)) for y in (2026, 2027, 2028) for m in (1, 3, 6, 11, 12)
              for d in (1, 7, 8, 9, 14, 15) for h in (0, 5, 6, 7, 12)]
    ck(all(_et_offset_rule(e) == _dt_off(e) for e in probes),
       "the inline ET rule equals downtime.et_offset on %d probes round both clock changes" % len(probes))
    # 2026-09-24: the hourly ladder. GET /markets read KXBTCD-26SEP2417's
    # close_time as 2026-09-24T21:00:00Z (5 PM EDT) and KXBTCD-26SEP2500's
    # as 2026-09-25T04:00:00Z (midnight EDT).
    ck(close_epoch("KXBTCD-26SEP2417-T95249.99") == calendar.timegm((2026, 9, 24, 21, 0, 0)),
       "hourly ladder: KXBTCD-26SEP2417-T95249.99 closes 17:00 ET = 21:00Z")
    ck(close_epoch("KXBTCD-26SEP2500-T80099.99") == calendar.timegm((2026, 9, 25, 4, 0, 0)),
       "hourly ladder: ...26SEP2500 is midnight ET = 04:00Z the same UTC day")
    ck(close_epoch("KXBTCD-26JAN1512-T80099.99") == calendar.timegm((2026, 1, 15, 17, 0, 0)),
       "hourly ladder in January: five hours, not four")
    ck(close_epoch("KXETHD-26SEP2423-T3444.99") == calendar.timegm((2026, 9, 25, 3, 0, 0))
       and close_epoch("KXSOLD-26SEP2423-T99.9999") == calendar.timegm((2026, 9, 25, 3, 0, 0))
       and close_epoch("KXDOGED-26SEP2423-T0.2749999") == calendar.timegm((2026, 9, 25, 3, 0, 0))
       and close_epoch("KXXRPD-26SEP2500-T2.2399") == calendar.timegm((2026, 9, 25, 4, 0, 0))
       and close_epoch("KXBNBD-26SEP2423-T969.99") == calendar.timegm((2026, 9, 25, 3, 0, 0))
       and close_epoch("KXHYPED-26SEP2423-T99.9999") == calendar.timegm((2026, 9, 25, 3, 0, 0)),
       "the other hourly ladders (lad3, read live 2026-09-25): same yyMONddHH "
       "date, 2-, 4- and 7-decimal strikes, 11 PM EDT = 03:00Z next UTC day")
    ck(_TKH.match("KXBTC15M-26SEP240045-45") is None
       and _TKH.match("KXBNB15M-26SEP161000-00") is None,
       "the hourly pattern never matches a 15M ticker, so every 15M answer is "
       "the one _TK gave before")
    ck(close_epoch("KXBTCD-26SEP2417") is None and close_epoch("KXBTCD-26SEP24-T1") is None,
       "NULL: an hourly EVENT ticker (no -T strike) and a short date are not markets")

    def order(tk, filled, kind="order"):
        return {"kind": kind, "ticker": tk, "filled": filled, "status": "executed"}

    def settled(tk):
        return {"kind": "settled", "ticker": tk, "pnl_c": 1.0}

    now = calendar.timegm((2026, 9, 16, 14, 5, 0))          # 10:05 AM ET = 14:05Z
    past = "KXBNB15M-26SEP161000-00"                        # closed 10:00 AM ET = 14:00Z
    ahead = "KXBTC15M-26SEP161015-15"                       # closes 10:15 AM ET = 14:15Z

    st, d = verdict([order(past, 85), settled(past)], alive=True, now=now)
    ck(st == "FLAT", "a fill with its settlement is flat")
    st, d = verdict([order(past, 85), order(ahead, 0)], alive=True, now=now)
    ck(st == "HOLDING" and d["open"] == {past: 1},
       "alive + an unsettled fill = HOLDING, and a zero-fill order is not a fill")
    st, d = verdict([order(past, 85)], alive=False, now=now)
    ck(st == "FLAT" and d.get("unlogged") == {past: 1},
       "THE DEADLOCK: dead bot, fill never logged a settlement, market closed 5 min "
       "ago -> FLAT (it settled on the exchange; refusing forever helps nobody)")
    st, d = verdict([order(past, 85)], alive=False, now=now, grace=600)
    ck(st == "HOLDING", "...but inside the grace window it still waits")
    st, d = verdict([order(ahead, 40)], alive=False, now=now)
    ck(st == "HOLDING" and d["open"][ahead]["closes_in_s"] == 600,
       "dead bot, market still 10 min from closing -> HOLDING (a new bot could "
       "buy that close again)")
    # hedge legs are fills on the same ticker and write their own settled record
    rows = [order(past, 85), {"kind": "hedge", "ticker": past, "n": 1.0,
                              "status": "executed"}, settled(past), settled(past)]
    ck(verdict(rows, alive=True, now=now)[0] == "FLAT",
       "a hedge leg is a second fill on the same ticker; two settlements clear it")
    rows = rows[:-1]
    ck(verdict(rows, alive=True, now=now)[0] == "HOLDING",
       "...and with only one settlement the pair is still open")
    # max-per-market 2: two fills, two settlements
    rows = [order(past, 40), order(past, 45), settled(past), settled(past)]
    ck(verdict(rows, alive=True, now=now)[0] == "FLAT", "two fills, two settlements")
    ck(verdict([], alive=True, now=now)[0] == "FLAT", "NULL: an empty log is flat")

    # end to end on a temp directory, with a dead pid
    with tempfile.TemporaryDirectory() as td:
        pf = os.path.join(td, "pinrun-live.pid")
        with open(pf, "w") as fh:
            fh.write("999999999")            # not a real pid on any box
        lp = os.path.join(td, "pinrun-live-20260916T100000Z.jsonl")
        with open(lp, "w") as fh:
            fh.write(json.dumps(order(past, 85)) + "\n")
            fh.write('{"kind": "close_summary", "trunc')     # a crash mid-line
        st, d = check(results=td, pidfile=pf, now=now)
        ck(st == "FLAT" and d["log"].startswith("pinrun-live-") and not d["alive"],
           "end to end: a truncated last line is skipped, the dead pid is seen as "
           "dead, the past close is flat")
        st, d = check(results=os.path.join(td, "nothing"), pidfile=pf, now=now)
        ck(st == "FLAT" and d["log"] is None, "NULL: no log at all is flat")
    selftest_kalshi(ck)
    ck(pid_alive(os.getpid()), "our own pid is alive")
    ck(not pid_alive(0) and not pid_alive("x"), "pid 0 / junk is not")
    print("pinflat selftest: OK")


def emit(st, d, warn, as_json=False, out=print):
    """Print the answer the way restart_bot.ps1, results\\pin_*.ps1 and
    laptop_handover.ps1 read it (a warning first, the verdict line, then each
    open position); return the exit code: 0 FLAT, 1 HOLDING, 2 could not tell.
    Every line is ASCII (json.dumps escapes by itself; text lines through _ascii)."""
    if as_json:
        rec = dict({"status": st}, **d)
        if warn:
            rec["warning"] = warn
        out(json.dumps(rec, default=str))
    else:
        if warn:
            out(_ascii(warn))
        if st == "UNKNOWN":
            out(_ascii("pinflat: could not tell -- %s" % d.get("err")))
        else:
            out(_ascii("%s -- %s (pid %s, %s)" % (st, d["why"], d.get("pid"), d.get("log"))))
            for tk, v in (d.get("open") or {}).items():
                out(_ascii("    open: %s %s" % (tk, v)))
    return {"FLAT": 0, "HOLDING": 1}.get(st, 2)


def safe_emit(st, d, warn, as_json=False, out=print):
    """emit, and if printing itself fails: HOLDING keeps exit 1 (wait), anything else is exit 2 (could not tell:
    restart_bot falls back to its count) -- never a FLAT that was not printed."""
    try:
        return emit(st, d, warn, as_json, out)
    except Exception:                                     # noqa: BLE001
        return 1 if st == "HOLDING" else 2


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--grace", type=int, default=GRACE_S)
    ap.add_argument("--no-kalshi", action="store_true",
                    help="the log check alone (no Kalshi read); restart_bot never passes it")
    ap.add_argument("--results", default=RESULTS, help="the results folder (tests)")
    ap.add_argument("--pidfile", default=None, help="the live pid file (default: pinrun-live.pid in --results)")
    a = ap.parse_args(argv)
    if a.selftest:
        selftest()
        return 0
    # NOTHING ON STDERR. Both restart_bot.ps1 copies run `& $py pinflat.py 2>&1` under $ErrorActionPreference =
    # "Stop", and in Windows PowerShell 5.1 the first stderr line of a native command is then a TERMINATING error:
    # the restart would die mid-check. The Kalshi read imports kauth (and so cryptography), which this file never
    # did before; any warning it or the network code might print goes to stdout instead, as an ordinary line.
    # And a character the pipe's code page cannot show is printed as its escape, never a crash (emit is ASCII
    # already; this covers anything else that prints).
    import warnings
    warnings.simplefilter("ignore")
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except Exception:                                     # noqa: BLE001
        pass
    sys.stderr = sys.stdout
    try:
        st, d, warn = truthful(grace=a.grace, use_kalshi=not a.no_kalshi, results=a.results,
                               pidfile=a.pidfile or os.path.join(a.results, "pinrun-live.pid"))
    except Exception as e:                                # noqa: BLE001
        try:
            print(json.dumps({"status": "UNKNOWN", "err": str(e)[:200]}) if a.json
                  else _ascii("pinflat: could not tell -- %s" % e))
        except Exception:                                 # noqa: BLE001
            pass
        return 2
    return safe_emit(st, d, warn, a.json)


if __name__ == "__main__":
    sys.exit(main())
