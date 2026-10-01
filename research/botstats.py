"""botstats.py -- every live bot's numbers, in ONE place the phone and the desktop both read.

WHY THIS EXISTS. The operator, 2026-09-30: *"Can you make a spot in the bot to see each sub account,
what's running, and as much details about them as possible? Also telegram commands for each sub
account type so I can see everything I can about them like pin. Including day performance, long
performance, everything you can. And are their totals added to the main pages total stats?"*

Four bots trade real money from one Kalshi key, in three separate pots:

    bot         pot (subaccount)   its markets
    pin         0 (main)           the 15-minute coin series (pinday.CRYPTO) + the hourly ladders (KXBTCD...)
    race        0 (main)           KXCRYPTOLEAD / KXCRYPTOCOMP -- the coin race
    forecaster  2                  everything subaccount 2 settled (the 30-minute bettor test before it sent 0 orders)
    ladder      1                  everything subaccount 1 settled

**THE ANSWER TO "ARE THEIR TOTALS IN THE MAIN PAGE?"** The main page reads `kalshi_ledger.json`,
which since 2026-09-29 holds subaccount 0 only -- pin + race (+ the old oil bot's rows, shown here as
`other`). The forecaster and the ladder are NOT in it. `all_bots()` is the only total with all four.

**MONEY COMES FROM KALSHI, PER SUBACCOUNT.** `/portfolio/settlements` with NO subaccount mixes every
pot's rows under the same (ticker, settled_time) key -- the bug fixed in pinledger.py on 2026-09-29 --
so every request here names its subaccount, and the self-test fails if one does not. Per market:
payout on the winning side - both sides' cost - fee (`pinledger.pnl`, which a hedged market needs:
Kalshi reports its revenue as 0). A log number never becomes money here; the logs only say what the
bot DID today (orders sent, filled, refused). A bank difference is never profit (deposits move it).

A market belongs to the ET day of its CLOSE, read from the ticker (`pinday.et_day_of_ticker`), the
same rule pinday and pinledger use, so this cannot disagree with them.

**"Money put in"** is what the contracts cost, both sides (yes cost + no cost). Fees are inside the
money figure, not the put-in. Return = money / put in.

READ ONLY. Kalshi is reached only through a `getter(path, params) -> (status, body)` -- by default
`kauth.get`, which can only send a GET -- and only three paths are ever asked for (settlements,
positions, balance). This file holds no HTTP code of its own, starts and stops nothing, and writes
exactly one file: `results/botstats_cache.json`. The self-test scans this source for any order,
transfer or process-control call and fails if it finds one.

**THE CACHE.** Per subaccount: the settlement rows (trimmed to the ten fields the money needs), when
they were last read, and whether the whole history has been walked once. A read is made at most
every REFRESH_S (60 s); after the first full walk it pages backwards from the newest settlement and
stops at the first page it already holds (pinledger.fetch's rule), so the normal cost is one request
per pot. A first walk cut short is RESUMED, never mistaken for the whole history -- until it finishes,
every figure is flagged `complete: False`. The process table (10-12 s to read on this box) is cached
the same way; pass `procs=` to reuse a table the caller already holds (pinphone.python_procs()).

A failed read is reported as a failure, never as $0: money is None with the error, alive is None
("could not tell"), and a total missing a bot says which.
"""
import argparse
import calendar
import glob
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import pinday                                                    # noqa: E402
import pinledger                                                 # noqa: E402

RESULTS = os.path.join(os.path.dirname(HERE), "results")
REPO = os.path.dirname(HERE)
CACHE_NAME = "botstats_cache.json"
VERSIONS_NAME = "VERSIONS.md"
REFRESH_S = 60                  # Kalshi and the process table are re-read at most this often
PROC_STALE_S = 300              # an older process table is "could not tell", not "not running"
PAGE = 200
MAX_PAGES = 200                 # 40,000 settlements a pot: a runaway pager stops loudly
POOL = 2                        # Kalshi's crypto & commodities cash pool, where every bot's cash sits
BOTS = ("pin", "race", "forecaster", "ladder")
SUBS = ("0", "1", "2")
# the only three things this file ever asks Kalshi for
PATHS = ("/portfolio/settlements", "/portfolio/positions", "/portfolio/balance")
KEEP = ("ticker", "settled_time", "market_result", "value", "yes_count_fp", "no_count_fp",
        "yes_total_cost_dollars", "no_total_cost_dollars", "fee_cost", "revenue")

# The hourly ladders pinrun knows (v-ladder7); only KXBTCD trades live today. A new series in
# subaccount 0 that is in neither list lands in `other`, loudly -- never folded into a bot.
PIN_HOURLY = frozenset(["KXBTCD", "KXETHD", "KXSOLD", "KXXRPD", "KXDOGED", "KXBNBD", "KXHYPED"])

SPEC = {
    "pin": {"label": "Pin bot", "what": "15-minute coin markets + hourly Bitcoin", "sub": "0",
            "script": "pinrun.py", "stop": "pinrun-live.stop", "log_glob": "pinrun-live-*.jsonl",
            "keepalive": "watch_bot.ps1 restarts it unless the stop file is there"},
    "race": {"label": "Coin race", "what": "which coin gains most in 15 minutes", "sub": "0",
             "script": "pinracearm.py", "stop": "pinracepenny.stop", "log": "pinracepenny-live.jsonl",
             "keepalive": None},        # boot_all.ps1 starts race PAPER arms only; nothing restarts the live one
    "forecaster": {"label": "Forecaster", "what": "clean-room forecaster, 1/20 of paper size", "sub": "2",
                   "script": "forecaster_live.py", "stop": "forecaster-live.stop",
                   "log": "forecaster-live-orders.jsonl",
                   "keepalive": "boot_all.ps1 (every 10 min) restarts it unless the stop file is there"},
    "ladder": {"label": "Penny ladder", "what": "clean-room ladder, 1-contract resting bids", "sub": "1",
               "script": "ladder_live.py", "stop": "ladder-live.stop", "log": "ladder-live-orders.jsonl",
               "keepalive": "boot_all.ps1 (every 10 min) restarts it unless the stop file is there"},
}
SUB_NAME = {"0": "main account", "1": "subaccount 1", "2": "subaccount 2"}

# what counts as sent / filled / refused / stopped in each bot's own log
HALT_KINDS = {"pin": ("halt", "entries_stopped", "pause"), "race": ("live_halt",),
              "forecaster": ("halt", "day_stop", "run_stop"), "ladder": ("day_stop",)}


# ---- clocks (ET for people, UTC inside) -------------------------------------
def _epoch(t):
    """'2026-09-30T04:15:06.437143Z' or '...:06Z' -> UTC epoch, or None."""
    try:
        return float(calendar.timegm(time.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S")))
    except (TypeError, ValueError):
        return None


def et_day(epoch):
    return pinday.et_day_of_epoch(epoch)


def day_start(day):
    """Epoch of midnight ET at the start of 'YYYY-MM-DD' (pindesk.et_day_start)."""
    y, m, d = (int(x) for x in day.split("-"))
    return calendar.timegm((y, m, d, 0, 0, 0)) - pinday.et_offset(calendar.timegm((y, m, d, 12, 0, 0)))


def shift_day(day, k):
    y, m, d = (int(x) for x in day.split("-"))
    return time.strftime("%Y-%m-%d", time.gmtime(calendar.timegm((y, m, d, 12, 0, 0)) + 86400 * k))


def day_label(day):
    """'2026-09-05' -> 'Sep 5'."""
    try:
        tm = time.strptime(day, "%Y-%m-%d")
    except (TypeError, ValueError):
        return str(day)
    return "%s %d" % (time.strftime("%b", tm), tm.tm_mday)


def _ampm(h, m):
    return "%d:%02d %s" % (h % 12 or 12, m, "AM" if h < 12 else "PM")


def et_clock(epoch, with_day=True):
    """UTC epoch -> 'Sep 30 12:15 AM ET' (or '12:15 AM ET')."""
    if epoch is None:
        return None
    tm = time.gmtime(float(epoch) + pinday.et_offset(float(epoch)))
    hm = _ampm(tm.tm_hour, tm.tm_min)
    return ("%s %d %s ET" % (time.strftime("%b", tm), tm.tm_mday, hm)) if with_day else hm + " ET"


def describe(ticker):
    """A market in words, on the ticker's own ET clock: 'HYPE 12:15 AM', 'race XRP 9:15 PM',
    'BTC hourly 11 AM'. No timezone arithmetic -- the ticker is already Eastern."""
    parts = str(ticker or "").split("-")
    series, stamp = parts[0], (parts[1] if len(parts) > 1 else "")
    clock = ""
    try:
        if len(stamp) >= 11:
            clock = _ampm(int(stamp[7:9]), int(stamp[9:11]))
        elif len(stamp) >= 9:
            h = int(stamp[7:9])
            clock = "%d %s" % (h % 12 or 12, "AM" if h < 12 else "PM")
    except ValueError:
        clock = ""
    if series in pinday.RACE:
        return ("race %s %s" % (parts[-1], clock)).strip()
    m = re.match(r"^KX([A-Z0-9]+?)15M$", series)
    if m:
        return ("%s %s" % (m.group(1), clock)).strip()
    if series in PIN_HOURLY:
        return ("%s hourly %s" % (series[2:-1], clock)).strip()
    return str(ticker)


def usd(x):
    if x is None:
        return "?"
    s = "{:,.2f}".format(abs(x))
    return ("+$" if x > 0.004 else ("-$" if x < -0.004 else "$")) + s


def pct(x):
    return "n/a" if x is None else "%+.1f%%" % x


# ---- which bot a settlement belongs to --------------------------------------
def owner(ticker, sub):
    series = str(ticker or "").split("-")[0]
    if sub == "1":
        return "ladder"
    if sub == "2":
        return "forecaster"
    if series in pinday.RACE or series.startswith("KXCRYPTOLEAD"):
        return "race"
    if series in pinday.CRYPTO or series in PIN_HOURLY:
        return "pin"
    return "other"


def market(s):
    """One settled market, in the terms the operator reads. Money is pinledger.pnl -- Kalshi's."""
    yn, nn = pinledger.money(s, "yes_count_fp"), pinledger.money(s, "no_count_fp")
    side = "both" if yn > 0 and nn > 0 else ("yes" if yn > 0 else ("no" if nn > 0 else "-"))
    tk = s.get("ticker") or ""
    d = pinday.et_day_of_ticker(tk)
    t = _epoch(s.get("settled_time"))
    if d is None and t is not None:
        d = et_day(t)
    return {"ticker": tk, "what": describe(tk), "day": d, "t": t, "side": side,
            "contracts": round(yn if side == "yes" else (nn if side == "no" else yn + nn), 2),
            "money": pinledger.pnl(s),
            "put_in": pinledger.money(s, "yes_total_cost_dollars") + pinledger.money(s, "no_total_cost_dollars"),
            "fees": pinledger.money(s, "fee_cost"),
            "result": str(s.get("market_result") or "")}


def window(ms, label, days=None):
    """Totals over the markets `ms` (already filtered). Worst/best are single markets."""
    won = [m for m in ms if m["money"] > 0.004]
    lost = [m for m in ms if m["money"] < -0.004]
    money = sum(m["money"] for m in ms)
    put_in = sum(m["put_in"] for m in ms)
    by_day = {}
    for m in ms:
        by_day[m["day"]] = by_day.get(m["day"], 0.0) + m["money"]

    def pick(m):
        return None if m is None else {k: m[k] for k in ("ticker", "what", "day", "side", "contracts", "money")}
    return {"label": label, "days": days, "markets": len(ms), "won": len(won), "lost": len(lost),
            "flat": len(ms) - len(won) - len(lost), "hedged": sum(1 for m in ms if m["side"] == "both"),
            "money": round(money, 4), "put_in": round(put_in, 4),
            "fees": round(sum(m["fees"] for m in ms), 4),
            "return_pct": (round(100.0 * money / put_in, 2) if put_in > 0 else None),
            "worst": pick(min(ms, key=lambda m: m["money"]) if ms else None),
            "best": pick(max(ms, key=lambda m: m["money"]) if ms else None),
            "active_days": len(by_day),
            "days_up": sum(1 for v in by_day.values() if v > 0.004),
            "days_down": sum(1 for v in by_day.values() if v < -0.004)}


def windows(ms, today):
    """today / yesterday / last 7 days / this month / all time, plus the per-day lists."""
    yday = shift_day(today, -1)
    week = set(shift_day(today, -k) for k in range(7))
    month = today[:7]
    out = {"today": window([m for m in ms if m["day"] == today], "Today", [today]),
           "yesterday": window([m for m in ms if m["day"] == yday], "Yesterday", [yday]),
           "last_7_days": window([m for m in ms if m["day"] in week], "Last 7 days",
                                 [shift_day(today, -6), today]),
           "this_month": window([m for m in ms if (m["day"] or "")[:7] == month],
                                time.strftime("%B", time.strptime(today, "%Y-%m-%d")), [month + "-01", today]),
           "all_time": window(ms, "All time", None)}
    days = sorted(set(m["day"] for m in ms if m["day"]))
    first = days[0] if days else None
    out["first_day"] = first
    out["days_7"] = []
    for k in range(7):
        d = shift_day(today, -k)
        w = window([m for m in ms if m["day"] == d], day_label(d), [d])
        out["days_7"].append({"day": d, "label": day_label(d), "markets": w["markets"], "won": w["won"],
                              "lost": w["lost"], "money": w["money"], "put_in": w["put_in"],
                              "return_pct": w["return_pct"], "before_first": first is None or d < first})
    out["all_days"] = []
    for d in reversed(days):
        w = window([m for m in ms if m["day"] == d], day_label(d), [d])
        out["all_days"].append({"day": d, "markets": w["markets"], "won": w["won"], "lost": w["lost"],
                                "money": w["money"], "put_in": w["put_in"], "return_pct": w["return_pct"]})
    return out


# ---- the cache and the Kalshi reads -----------------------------------------
_MEMO = {"key": None, "data": None}


def cache_path():
    return os.path.join(RESULTS, CACHE_NAME)


def load_cache():
    p = cache_path()
    try:
        st = os.stat(p)
        key = (p, st.st_mtime, st.st_size)
        if _MEMO["key"] == key:
            return json.loads(json.dumps(_MEMO["data"]))         # a private copy
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        if not isinstance(d, dict):
            raise ValueError("not a dict")
        _MEMO.update(key=key, data=d)
        return json.loads(json.dumps(d))
    except (OSError, ValueError):
        return {"v": 1, "subs": {}, "procs": None}


def save_cache(c):
    p = cache_path()
    c["written"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    tmp = "%s.%d.tmp" % (p, os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(c, fh, separators=(",", ":"))
        for _ in range(3):
            try:
                os.replace(tmp, p)
                st = os.stat(p)
                _MEMO.update(key=(p, st.st_mtime, st.st_size), data=json.loads(json.dumps(c)))
                return True
            except PermissionError:          # a reader on Windows holds it open; the next call retries
                time.sleep(0.2)
    except OSError:
        pass
    try:
        os.remove(tmp)
    except OSError:
        pass
    return False


def default_getter():
    """kauth.get: signed, and GET only by construction (kauth has no other method)."""
    import kauth

    def get(path, params):
        return kauth.get(path, params)
    return get


def fetch_settlements(c, sub, getter):
    """Walk /portfolio/settlements for one pot. Until a walk has reached the end once, every walk
    is a full one (so a cut-short first walk is resumed, not trusted); after that it stops at the
    first page it already holds. Returns an error string or None."""
    rows = c.setdefault("rows", {})
    backfill = not c.get("complete")
    cursor, pages = None, 0
    while True:
        q = {"limit": PAGE, "subaccount": sub}
        if cursor:
            q["cursor"] = cursor
        st, d = getter("/portfolio/settlements", q)
        pages += 1
        if st != 200 or not isinstance(d, dict):
            return "settlements read failed (HTTP %s)" % st
        got = d.get("settlements") or []
        new = 0
        for s in got:
            if not isinstance(s, dict):
                continue
            k = pinledger.key_of(s)
            if k not in rows:            # append-only: Kalshi's record of a settlement never changes
                rows[k] = {f: s[f] for f in KEEP if f in s}
                new += 1
        cursor = d.get("cursor")
        if not got or not cursor:
            c["complete"] = True
            return None
        if not backfill and new == 0:
            return None
        if pages >= MAX_PAGES:
            return "settlements: stopped after %d pages without reaching the end" % pages


def fetch_positions(sub, getter):
    st, d = getter("/portfolio/positions", {"subaccount": sub, "settlement_status": "unsettled",
                                            "count_filter": "position", "limit": PAGE})
    if st != 200 or not isinstance(d, dict) or not isinstance(d.get("market_positions"), list):
        return None, "positions read failed (HTTP %s)" % st
    out = []
    for x in d["market_positions"]:
        if not isinstance(x, dict):
            continue
        tk = x.get("ticker") or x.get("market_ticker")
        n = pinledger.money(x, "position_fp", "position")
        if not tk or abs(n) < 1e-9:
            continue
        out.append({"ticker": tk, "net": n,
                    "at_risk": pinledger.money(x, "market_exposure_dollars"),
                    "fees": pinledger.money(x, "fees_paid_dollars")})
    return out, None


def fetch_balance(sub, getter):
    """balance_dollars is DOLLARS; `balance` is cents. The unit is read from the field name, never
    guessed from the size (hard rule 5), so a body with no balance_dollars is unreadable."""
    st, d = getter("/portfolio/balance", {"subaccount": sub, "exchange_index": POOL})
    if st != 200 or not isinstance(d, dict) or "balance_dollars" not in d:
        return None, "balance read failed (HTTP %s)" % st
    try:
        return float(d["balance_dollars"]), None
    except (TypeError, ValueError):
        return None, "balance unreadable: %r" % d.get("balance_dollars")


def refresh(c, now, getter):
    """Bring each pot up to date, at most once every REFRESH_S. Returns True when anything was read."""
    subs = c.setdefault("subs", {})
    did = False
    for sub in SUBS:
        x = subs.setdefault(sub, {"rows": {}, "complete": False})
        if now - float(x.get("tried") or 0) < REFRESH_S:
            continue
        if getter is None:
            getter = default_getter()
        did = True
        x["tried"] = now
        err = fetch_settlements(x, sub, getter)
        x["err"] = err
        if err is None:
            x["fetched"] = now
        pos, perr = fetch_positions(sub, getter)
        x["pos_err"] = perr
        if pos is not None:
            x["positions"], x["pos_t"] = pos, now
        bal, berr = fetch_balance(sub, getter)
        x["bal_err"] = berr
        if bal is not None:
            x["balance"], x["bal_t"] = bal, now
    return did


# ---- the process table -------------------------------------------------------
_PS = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ForEach-Object { "
       "$s = ''; if ($_.CreationDate) { $s = $_.CreationDate.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') }; "
       "\"$($_.ProcessId)" + chr(96) + "t$s" + chr(96) + "t$(($_.CommandLine -replace '\\s+', ' '))\" }")


def _procs_native():
    """The same table straight from Windows in milliseconds: a Toolhelp snapshot of process names,
    then, for each python.exe only, its command line (NtQueryInformationProcess class 60) and start
    time (GetProcessTimes). Every handle is opened with QUERY_LIMITED_INFORMATION -- the right to
    look, nothing else. WMI (the fallback below) took 25-35 s on the operator's box on 2026-09-30.
    None when any step is unavailable."""
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        nt = ctypes.WinDLL("ntdll")
    except (ImportError, OSError, AttributeError):
        return None

    class PE(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("pid", wintypes.DWORD),
                    ("heap", ctypes.c_size_t), ("mod", wintypes.DWORD), ("threads", wintypes.DWORD),
                    ("ppid", wintypes.DWORD), ("prio", ctypes.c_long), ("flags", wintypes.DWORD),
                    ("exe", ctypes.c_wchar * 260)]

    class US(ctypes.Structure):                  # UNICODE_STRING
        _fields_ = [("Length", ctypes.c_ushort), ("MaximumLength", ctypes.c_ushort), ("Buffer", ctypes.c_void_p)]

    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.Process32FirstW.argtypes = k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PE)]
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    k32.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
    nt.NtQueryInformationProcess.restype = ctypes.c_long
    nt.NtQueryInformationProcess.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
                                             ctypes.POINTER(ctypes.c_ulong)]
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)                     # TH32CS_SNAPPROCESS
    if not snap or snap == ctypes.c_void_p(-1).value:
        return None
    pids = []
    try:
        pe = PE()
        pe.dwSize = ctypes.sizeof(PE)
        more = k32.Process32FirstW(snap, ctypes.byref(pe))
        while more:
            if pe.exe.lower() == "python.exe":
                pids.append(int(pe.pid))
            more = k32.Process32NextW(snap, ctypes.byref(pe))
    finally:
        k32.CloseHandle(snap)
    rows, unread = [], 0
    for pid in pids:
        h = k32.OpenProcess(0x1000, False, pid)                     # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            unread += 1
            continue
        try:
            need = ctypes.c_ulong(0)
            buf = ctypes.create_string_buffer(4096)
            st = nt.NtQueryInformationProcess(h, 60, buf, len(buf), ctypes.byref(need))
            if st != 0 and need.value > len(buf):
                buf = ctypes.create_string_buffer(need.value)
                st = nt.NtQueryInformationProcess(h, 60, buf, len(buf), ctypes.byref(need))
            if st != 0:
                unread += 1
                continue
            us = US.from_buffer(buf)
            cl = ctypes.wstring_at(us.Buffer, us.Length // 2) if us.Buffer else ""
            ft = [ctypes.c_ulonglong(0) for _ in range(4)]
            started = ""
            if k32.GetProcessTimes(h, *[ctypes.byref(x) for x in ft]) and ft[0].value:
                started = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                        time.gmtime((ft[0].value - 116444736000000000) / 1e7))
        finally:
            k32.CloseHandle(h)
        cl = " ".join(cl.split())
        if any(SPEC[b]["script"] in cl for b in BOTS):
            rows.append([pid, started, cl])
    # a python.exe we could not read might be one of ours: say "could not tell", not "not running"
    return None if unread else rows


def read_procs(timeout=40):
    """[[pid, started_utc_or_'', command line]] for OUR four scripts, or None when Windows could not
    be asked. None, never [] -- an empty list would read as 'nothing is running'. The native read
    first; WMI through PowerShell only when it fails."""
    try:
        rows = _procs_native()
    except Exception:                                           # noqa: BLE001
        rows = None
    if rows is not None:
        return rows
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", _PS], capture_output=True, text=True,
                             timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if out.returncode != 0:
            return None
    except Exception:                                           # noqa: BLE001
        return None
    rows = []
    for line in (out.stdout or "").splitlines():
        f = line.split("\t", 2)
        if len(f) < 3 or not any(SPEC[b]["script"] in f[2] for b in BOTS):
            continue
        try:
            rows.append([int(f[0].strip()), f[1].strip(), f[2].strip()])
        except ValueError:
            pass
    return rows


def _norm_procs(rows):
    out = []
    for r in rows or []:
        r = list(r)
        if len(r) == 2:
            r = [r[0], "", r[1]]
        out.append([int(r[0]), str(r[1] or ""), str(r[2] or "")])
    return out


def procs_for(c, now, procs):
    """(rows, ok, cache_changed). `procs` may be a table the caller already holds ([(pid, cmdline)]
    or [(pid, started_utc, cmdline)]), a callable returning one (or None on failure), or None to
    read (and cache) it here."""
    if procs is not None and not callable(procs):
        return _norm_procs(procs), True, False
    p = c.get("procs") or {}
    if procs is None and p.get("rows") is not None and now - float(p.get("t") or 0) < REFRESH_S:
        return _norm_procs(p["rows"]), True, False
    rows = procs() if callable(procs) else read_procs()
    if rows is not None:
        c["procs"] = {"t": now, "rows": _norm_procs(rows)}
        return _norm_procs(rows), True, True
    if p.get("rows") is not None and now - float(p.get("t") or 0) < PROC_STALE_S:
        return _norm_procs(p["rows"]), True, False
    return None, False, False


def _toks(cl):
    return str(cl or "").replace('"', " ").split()


def opt(cl, flag):
    t = _toks(cl)
    return t[t.index(flag) + 1] if flag in t and t.index(flag) + 1 < len(t) else None


def is_bot(name, cl):
    """Is this command line the LIVE copy of `name`? Paper arms of the same script are not."""
    t = _toks(cl)
    script = SPEC[name]["script"]
    if not any(re.search(r"(^|[\\/])" + re.escape(script) + "$", x) for x in t):
        return False
    if "--live" not in t:
        return False
    return not (name == "race" and "--paper-live" in t)


# ---- the bots' own logs (what they DID; never money) -------------------------
_BACK = {}


def _t_of(r):
    return _epoch(r.get("t"))


def read_since(path, since, chunk=1 << 20):
    """Records with t >= since, reading backwards from the end so a 10 MB log costs only today's
    part. None when the file is missing."""
    try:
        size = os.path.getsize(path)
        fh = open(path, "rb")
    except OSError:
        return None
    with fh:
        pos, buf = size, b""
        while True:
            step = min(chunk, pos)
            pos -= step
            fh.seek(pos)
            buf = fh.read(step) + buf
            lines = buf.split(b"\n")
            body = lines if pos == 0 else lines[1:]
            first_t = None
            for ln in body:
                try:
                    first_t = _t_of(json.loads(ln))
                except ValueError:
                    continue
                if first_t is not None:
                    break
            if pos == 0 or (first_t is not None and first_t < since):
                break
    out = []
    for ln in body:
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        t = _t_of(r)
        if isinstance(r, dict) and t is not None and t >= since:
            out.append(r)
    return out


def last_record(path, kinds, pred=None, max_bytes=64 << 20, chunk=1 << 20):
    """The newest record whose kind/ev is in `kinds` (and passes `pred`), reading backwards.
    Memoised on (path, size, kinds) for the long-running phone process."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    key = (path, size, tuple(kinds), pred is None)
    if pred is None and key in _BACK:
        return _BACK[key]
    needles = [('"%s"' % k).encode() for k in kinds]
    found = None
    with open(path, "rb") as fh:
        pos, tail = size, b""
        while pos > 0 and size - pos < max_bytes and found is None:
            step = min(chunk, pos)
            pos -= step
            fh.seek(pos)
            buf = fh.read(step) + tail
            lines = buf.split(b"\n")
            tail = lines[0] if pos > 0 else b""
            body = lines[1:] if pos > 0 else lines
            if not any(n in buf for n in needles):
                continue
            for ln in reversed(body):
                if not any(n in ln for n in needles):
                    continue
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict) and (r.get("kind") or r.get("ev")) in kinds and (pred is None or pred(r)):
                    found = r
                    break
    if pred is None:
        if len(_BACK) > 64:
            _BACK.clear()
        _BACK[key] = found
    return found


def pin_logs():
    return sorted(glob.glob(os.path.join(RESULTS, SPEC["pin"]["log_glob"])))


def activity(name, since):
    """Counts from the bot's own log since `since` (midnight ET): what it DID, not what it made."""
    if name == "pin":
        paths = [p for p in pin_logs() if os.path.getmtime(p) >= since]
        if not pin_logs():
            paths = None
    else:
        p = os.path.join(RESULTS, SPEC[name]["log"])
        paths = [p] if os.path.exists(p) else None
    out = {"ok": paths is not None, "source": None, "sent": 0, "filled": 0, "contracts_filled": 0.0,
           "not_filled": 0, "refused": 0, "refused_why": {}, "cancelled": 0, "hedges": 0,
           "halts": [], "note": None}
    if paths is None:
        out["note"] = "no log file found"
        return out
    out["source"] = [os.path.basename(p) for p in paths]
    why = {}
    for p in paths:
        for r in read_since(p, since) or []:
            k = r.get("kind") or r.get("ev")
            if name == "pin":
                if k == "order":
                    out["sent"] += 1
                    f = pinledger.money(r, "filled")
                    out["filled" if f > 0 else "not_filled"] += 1
                    out["contracts_filled"] += f
                elif k == "hedge":
                    out["hedges"] += 1
                elif k in ("refused", "late_refused"):
                    out["refused"] += 1
                    g = str(r.get("gate") or k)
                    why[g] = why.get(g, 0) + 1
            elif name == "race":
                if k == "live_order":
                    out["sent"] += 1
                    f = pinledger.money(r, "filled")
                    out["filled" if f > 0 else "not_filled"] += 1
                    out["contracts_filled"] += f
                elif k == "live_refused":
                    out["refused"] += 1
                    w = r.get("why")
                    # the race writes numbers and coins into its reasons; group them by their shape
                    g = re.sub(r"\d+(\.\d+)?", "N", str((w[0] if isinstance(w, list) and w else w) or "?"))
                    g = re.sub(r"(YES|NO) on [A-Z]+ ", r"\1 on COIN ", g)[:80]
                    why[g] = why.get(g, 0) + 1
            elif name == "forecaster":
                if k == "placed":
                    out["sent"] += 1
                    if pinledger.money(r, "filled") <= 0:
                        out["not_filled"] += 1
                elif k == "live_fill":
                    out["filled"] += 1
                    out["contracts_filled"] += pinledger.money(r, "n")
                elif k in ("refused", "dropped", "body_refused"):
                    out["refused"] += 1
                    g = str(r.get("why") or k)
                    why[g] = why.get(g, 0) + 1
            elif name == "ladder":
                if k == "placed":
                    out["sent"] += 1
                elif k == "cancelled":
                    out["cancelled"] += 1
                elif k == "live_fill":
                    out["filled"] += 1
                    out["contracts_filled"] += pinledger.money(r, "delta")
                elif k == "rail_refused":
                    out["refused"] += 1
                    g = str(r.get("why") or k)
                    why[g] = why.get(g, 0) + 1
            if k in HALT_KINDS[name] or k in ("stop_file", "exit"):
                out["halts"].append({"t_et": et_clock(_t_of(r)), "what": k,
                                     "why": str(r.get("why") or r.get("day_pnl") or r.get("run_pnl") or "")[:120]})
    out["refused_why"] = dict(sorted(why.items(), key=lambda kv: -kv[1]))
    out["contracts_filled"] = round(out["contracts_filled"], 2)
    if name == "ladder":
        out["note"] = "resting bids: most are cancelled unfilled at the close, by design"
    return out


# ---- what is running, and on what settings -----------------------------------
_VER = re.compile(r"^#\s+(v-[\w.-]+(?:\s*\+\s*v-[\w.-]+)*)\s+--\s+(.*)$")
_VER_T = re.compile(r"(\d{4}-\d{2}-\d{2})(?:\s+~?(\d{2}):(\d[\dx])(?::(\d{2}))?Z?)?", re.I)


def version_of(name):
    """The newest VERSIONS.md heading for this bot: (name, epoch or None, title) or None."""
    try:
        with open(os.path.join(RESULTS, VERSIONS_NAME), encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return None
    for line in lines:
        m = _VER.match(line.rstrip())
        if not m:
            continue
        vname, rest = m.group(1), m.group(2)
        low = (vname + " " + rest).lower()
        # 2026-10-01: a heading that ships several bots at once ("v-race40 + v-forecaster-scale + v-ladder-size
        # + v-crash-guard") names every bot, so the text test below claimed it for none of them and the phone
        # showed the race's OLD version. A combined heading belongs to each bot one of its names is about.
        names = [n.strip() for n in vname.split("+")]
        if len(names) > 1:
            own = {"race": [n for n in names if n.startswith("v-race")],
                   "forecaster": [n for n in names if "forecaster" in n or n == "v-crash-guard"],
                   "ladder": [n for n in names if re.match(r"v-ladder-[a-z]", n)]}
            if any(own.values()):
                own["pin"] = []
            elif not re.search(r"cleanroom|clean-room|bettor|penny", low):
                own["pin"] = names
            else:
                own["pin"] = []
            if not own[name]:
                continue
            vname = " + ".join(own[name])
            mt = _VER_T.search(rest)
            t = None
            if mt:
                day, hh, mm = mt.group(1), mt.group(2), mt.group(3)
                try:
                    t = float(calendar.timegm(time.strptime(
                        "%sT%s:%s" % (day, hh or "00", (mm or "00").lower().replace("x", "0")), "%Y-%m-%dT%H:%M")))
                except ValueError:
                    t = None
            return vname, t, rest.strip()
        # An entry naming two clean-room bots (v-keepalive-cleanroom) is infrastructure, not either
        # bot's version; `v-ladder7` is pin's hourly ladder table, not the penny ladder.
        race = vname.startswith("v-race") or bool(re.search(r"coin.?race", low))
        fc = "forecaster" in low
        lad = "ladder_live" in low or "penny ladder" in low
        clean = bool(re.search(r"cleanroom|clean-room|bettor|forecaster|ladder_live|penny", low))
        mine = {"race": race and not fc and not lad, "forecaster": fc and not lad and not race,
                "ladder": lad and not fc and not race, "pin": not (race or fc or lad or clean)}[name]
        if not mine:
            continue
        t = None
        mt = _VER_T.search(rest)
        if mt:
            day, hh, mm = mt.group(1), mt.group(2), mt.group(3)
            try:
                t = float(calendar.timegm(time.strptime(
                    "%sT%s:%s" % (day, hh or "00", (mm or "00").lower().replace("x", "0")), "%Y-%m-%dT%H:%M")))
            except ValueError:
                t = None
        return vname, t, rest.strip()
    return None


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _c(p):
    """0.978 -> '97.8c', 0.98 -> '98c'."""
    if p is None:
        return "?"
    c = round(float(p) * 100, 1)
    return ("%dc" % c) if abs(c - round(c)) < 1e-9 else ("%.1fc" % c)


def settings_pin(start, cl, sizef):
    s = {}
    if start:
        for k in ("size", "price_ceiling", "tau_max", "early_tau_max", "early_frac", "early_min_price",
                  "early_max_price", "hedge_belief", "loss_abort", "loss_cap", "max_positions",
                  "ladder_series", "late_tau", "late_mult", "bank_brake", "code_sha"):
            if k in start:
                s[k] = start[k]
    if cl:
        for flag in ("--series-size", "--max-losses"):
            v = opt(cl, flag)
            if v is not None:
                s[flag[2:].replace("-", "_")] = _num(v)
        for flag in ("--one-full-bet", "--toxic-fresh", "--jump-gate", "--no-hedge-prop"):
            s[flag[2:].replace("-", "_")] = flag in _toks(cl)
    if sizef:
        s["bet_now"] = sizef.get("size")
        s["bank_at_sizing"] = sizef.get("bank")
        s["sized_at_et"] = et_clock(_num(sizef.get("epoch")) or _epoch(sizef.get("at")))
    bits = []
    bet = s.get("bet_now") or s.get("size")
    if bet is not None:
        bits.append("bet %g contracts" % bet + (" (sized on a %s bank)" % usd(s["bank_at_sizing"]).lstrip("+")
                                                  if s.get("bank_at_sizing") else ""))
    if s.get("price_ceiling") is not None:
        bits.append("buys up to %s with %s s or less left" % (_c(s["price_ceiling"]), s.get("tau_max", "?")))
    if s.get("early_tau_max"):
        frac = s.get("early_frac")
        size = ("a third of a bet" if frac is not None and abs(float(frac) - 0.333) < 0.01
                else "%g of a bet" % frac if frac is not None else "?")
        bits.append("early bet from %s s left: %s, %s to %s" % (s["early_tau_max"], size, _c(s.get("early_min_price")),
                                                              _c(s.get("early_max_price") or s.get("price_ceiling"))))
    if s.get("hedge_belief") is not None:
        bits.append("hedges if our odds fall under %d%%" % round(100 * float(s["hedge_belief"])))
    stops = []
    if s.get("max_losses"):
        stops.append("%d losing bets" % s["max_losses"])
    if s.get("loss_cap"):
        stops.append("a %s run loss" % usd(float(s["loss_cap"])).lstrip("+"))
    if stops:
        bits.append("halts after " + " or ".join(stops))
    if s.get("ladder_series"):
        bits.append("hourly %s: %g contract a market" % ("/".join(s["ladder_series"]), s.get("series_size") or 1))
    return s, "; ".join(bits)


def settings_race(start, cl):
    s = {}
    rails = (start or {}).get("live_rails") or {}
    src = cl or " ".join((start or {}).get("argv") or [])
    for flag, key in (("--max-contracts", "contracts_per_bet"), ("--max-stake", "max_in_play"),
                      ("--live-tau-max", "buys_within_s"), ("--live-min-price", "min_price"),
                      ("--live-max-legs", "max_bets_per_race"), ("--live-confirm", "confirm_s")):
        v = _num(opt(src, flag))
        if v is not None:
            s[key] = v
    s["stop_on_first_loss"] = bool(rails.get("stop_on_loss", (start or {}).get("stop_on_loss")))
    # v-race40 (2026-09-30): --live-max-losses N > 1 stops for the rest of the ET day after N losing races
    ml = _num(opt(src, "--live-max-losses"))
    if ml is not None and ml > 1:
        s["max_losses_per_day"] = ml
        s["stop_on_first_loss"] = False
    if start and start.get("version"):
        s["code_version"] = start["version"]
    bits = []
    if "contracts_per_bet" in s:
        bits.append("%g contracts a bet" % s["contracts_per_bet"])
    if "min_price" in s or "buys_within_s" in s:
        bits.append("buys at %s or more with %g s or less left" % (_c(s.get("min_price")), s.get("buys_within_s", 0)))
    if "max_in_play" in s:
        bits.append("at most %s in play" % usd(s["max_in_play"]).lstrip("+"))
    if "max_bets_per_race" in s:
        bits.append("up to %g bets a race" % s["max_bets_per_race"])
    if s.get("max_losses_per_day"):
        bits.append("stops for the rest of the ET day after %g losing races" % s["max_losses_per_day"])
    elif s["stop_on_first_loss"]:
        bits.append("stops after its first loss")
    return s, "; ".join(bits)


def settings_clean(name, start, cl):
    s = {}
    r = (start or {}).get("rails") or {}
    s["rails"] = r
    if name == "forecaster":
        s["variant"] = (start or {}).get("variant") or opt(cl, "--variant")
        s["variant_params"] = (start or {}).get("variant_params")
        if cl and opt(cl, "--variant") and s["variant"] != opt(cl, "--variant"):
            s["variant_mismatch"] = "log says %s, command line says %s" % (s["variant"], opt(cl, "--variant"))
        bits = ["variant %s" % (s["variant"] or "none")]
        if r.get("scale") is not None:
            bits.append("%g%% of paper size" % (100 * float(r["scale"])))
        if r.get("per_side") is not None:
            bits.append("up to %s a side, %s a quarter-hour" % (r["per_side"], r.get("per_close", "?")))
        if r.get("max_commit") is not None:
            bits.append("at most %s in play" % usd(float(r["max_commit"])).lstrip("+"))
        if r.get("px"):
            bits.append("buys %s to %s" % (_c(r["px"][0]), _c(r["px"][1])))
        if r.get("day_stop") is not None:
            bits.append("stops the day at %s, the run at %s" % (usd(float(r["day_stop"])), usd(float(r.get("run_stop") or 0))))
    else:
        bits = []
        lv = r.get("live_levels")
        bits.append("%s-contract resting bids%s" % (r.get("size", 1), " on the top rung" if lv == [0] else ""))
        if r.get("max_live_per_close") is not None:
            bits.append("up to %s coins a quarter-hour" % r["max_live_per_close"])
        if r.get("max_contracts") is not None:
            bits.append("at most %s contracts / %s in play" % (r["max_contracts"], usd(float(r.get("max_commit") or 0)).lstrip("+")))
        if r.get("day_stop") is not None:
            bits.append("stops the day at %s" % usd(float(r["day_stop"])))
    return s, "; ".join(bits)


def running(name, rows, ok, now):
    spec = SPEC[name]
    stop = os.path.join(RESULTS, spec["stop"])
    out = {"alive": None, "pid": None, "pids": [], "started_utc": None, "started_et": None, "command": None,
           "keepalive": spec["keepalive"], "stop_flag": os.path.exists(stop), "stop_flag_et": None,
           "stop_flag_text": None, "halted": None, "log": None, "log_age_s": None, "log_last_et": None,
           "version": None, "version_et": None, "version_title": None, "settings": {}, "settings_text": "",
           "problems": []}
    if out["stop_flag"]:
        try:
            out["stop_flag_et"] = et_clock(os.path.getmtime(stop))
            with open(stop, encoding="utf-8", errors="replace") as fh:
                out["stop_flag_text"] = fh.read(200).strip() or None
        except OSError:
            pass
    mine = [r for r in rows or [] if is_bot(name, r[2])] if ok else []
    if ok:
        out["alive"] = bool(mine)
        out["pids"] = [r[0] for r in mine]
        if mine:
            out["pid"], out["command"] = mine[0][0], mine[0][2]
            if mine[0][1]:
                out["started_utc"] = mine[0][1]
        if len(mine) > 1:
            out["problems"].append("%d live copies running (pids %s)" % (len(mine), ", ".join(map(str, out["pids"]))))
    # its log, its latest start record, its settings
    if name == "pin":
        logs = pin_logs()
        log = logs[-1] if logs else None
    else:
        log = os.path.join(RESULTS, spec["log"])
        log = log if os.path.exists(log) else None
    start = None
    if log:
        out["log"] = os.path.basename(log)
        try:
            mt = os.path.getmtime(log)
            out["log_age_s"] = round(max(0.0, now - mt), 1)
            out["log_last_et"] = et_clock(mt)
        except OSError:
            pass
        if name == "pin":
            try:
                with open(log, encoding="utf-8") as fh:
                    r = json.loads(fh.readline() or "{}")
                start = r if r.get("kind") == "start" else None
            except (OSError, ValueError):
                start = None
        else:
            pid = out["pid"]
            if pid is not None and name in ("forecaster", "ladder"):
                start = last_record(log, ("start",), lambda r: r.get("pid") == pid)
            if start is None:
                start = last_record(log, ("start",), lambda r: r.get("live") is not False)
    if out["started_utc"] is None and start and start.get("t"):
        out["started_utc"] = str(start["t"])[:19] + "Z"
    out["started_et"] = et_clock(_epoch(out["started_utc"])) if out["started_utc"] else None
    if name == "pin":
        sizef = None
        try:
            with open(os.path.join(RESULTS, "pinrun-live-size.json"), encoding="utf-8") as fh:
                sizef = json.load(fh)
        except (OSError, ValueError):
            sizef = None
        out["settings"], out["settings_text"] = settings_pin(start, out["command"], sizef)
    elif name == "race":
        out["settings"], out["settings_text"] = settings_race(start, out["command"])
    else:
        out["settings"], out["settings_text"] = settings_clean(name, start, out["command"])
        if out["settings"].get("variant_mismatch"):
            out["problems"].append("variant: " + out["settings"]["variant_mismatch"])
    # halted since its start?
    if log:
        paths = [log]
        st_t = _t_of(start) if start else None
        for p in paths:
            h = last_record(p, HALT_KINDS[name])
            ht = _t_of(h) if h else None
            if h and ht is not None and (st_t is None or ht >= st_t):
                out["halted"] = {"t_et": et_clock(ht), "what": h.get("kind") or h.get("ev"),
                                 "why": str(h.get("why") or h.get("day_pnl") or h.get("run_pnl") or "")[:160]}
    v = version_of(name)
    if v:
        out["version"], out["version_et"], out["version_title"] = v[0], et_clock(v[1]), v[2][:300]
    if ok and not mine and not out["stop_flag"]:
        out["problems"].append("NOT RUNNING and no stop file -- it stopped on its own")
    if ok and mine and out["stop_flag"]:
        out["problems"].append("stop file is set but it is still running (it stops at its next check)")
    if not ok:
        out["problems"].append("could not read the Windows process list")
    return out


# ---- the per-bot report ------------------------------------------------------
def _money_block(c, name, today):
    sub = SPEC[name]["sub"] if name in SPEC else "0"
    x = (c.get("subs") or {}).get(sub) or {}
    rows = x.get("rows") or {}
    have = bool(x.get("fetched")) or bool(rows)
    base = {"ok": have, "subaccount": int(sub), "source": "Kalshi settlements, %s" % SUB_NAME[sub],
            "complete": bool(x.get("complete")), "error": x.get("err"),
            "as_of_et": et_clock(x.get("fetched")) if x.get("fetched") else None,
            "stale": bool(x.get("err")) and have}
    if not have:
        for k in ("today", "yesterday", "last_7_days", "this_month", "all_time", "first_day"):
            base[k] = None
        base["days_7"], base["all_days"], base["markets"] = [], [], []
        base["error"] = base["error"] or "Kalshi has not been read yet"
        return base
    ms = [market(s) for s in rows.values() if owner(s.get("ticker"), sub) == name]
    ms.sort(key=lambda m: (m["t"] or 0), reverse=True)
    base.update(windows(ms, today))
    base["markets"] = ms
    return base


def _open_block(c, name):
    sub = SPEC[name]["sub"]
    x = (c.get("subs") or {}).get(sub) or {}
    if x.get("positions") is None:
        return {"ok": False, "error": x.get("pos_err") or "not read yet", "positions": [], "count": None,
                "at_risk": None}
    ps = []
    for p in x["positions"]:
        if owner(p["ticker"], sub) != name:
            continue
        ps.append({"ticker": p["ticker"], "what": describe(p["ticker"]), "side": "yes" if p["net"] > 0 else "no",
                   "contracts": abs(p["net"]), "at_risk": p["at_risk"]})
    return {"ok": True, "error": x.get("pos_err"), "stale": bool(x.get("pos_err")),
            "as_of_et": et_clock(x.get("pos_t")), "positions": ps, "count": len(ps),
            "at_risk": round(sum(p["at_risk"] for p in ps), 4)}


def _balance_block(c, name):
    sub = SPEC[name]["sub"]
    x = (c.get("subs") or {}).get(sub) or {}
    shared = [b for b in BOTS if b != name and SPEC[b]["sub"] == sub]
    note = ("shared: the %s's cash sits in the same pot" % " and ".join(SPEC[b]["label"].lower() for b in shared)
            if shared else "its own pot (%s)" % SUB_NAME[sub])
    return {"ok": x.get("balance") is not None, "dollars": x.get("balance"), "subaccount": int(sub),
            "shared_with": shared, "note": note, "as_of_et": et_clock(x.get("bal_t")),
            "error": x.get("bal_err")}


def _bot_from(c, name, now, rows, ok):
    today = et_day(now)
    money = _money_block(c, name, today)
    last = [{"time_et": et_clock(m["t"]), "ticker": m["ticker"], "what": m["what"], "side": m["side"],
             "contracts": m["contracts"], "money": round(m["money"], 4), "put_in": round(m["put_in"], 4),
             "result": m["result"]} for m in (money.get("markets") or [])[:5]]
    money.pop("markets", None)
    out = {"name": name, "label": SPEC[name]["label"], "what": SPEC[name]["what"],
           "subaccount": int(SPEC[name]["sub"]),
           "shares_subaccount_with": [b for b in BOTS if b != name and SPEC[b]["sub"] == SPEC[name]["sub"]],
           "running": running(name, rows, ok, now), "money": money, "open": _open_block(c, name),
           "balance": _balance_block(c, name), "last_settled": last,
           "activity_today": activity(name, day_start(today)), "errors": []}
    for k in ("money", "open", "balance"):
        if out[k].get("error"):
            out["errors"].append("%s: %s" % (k, out[k]["error"]))
    return out


def _load(now, getter, procs):
    c = load_cache()
    changed = refresh(c, now, getter)
    rows, ok, pchanged = procs_for(c, now, procs)
    if changed or pchanged:
        save_cache(c)
    return c, rows, ok


def bot(name, now=None, getter=None, procs=None):
    """One bot's full report (see the module docstring for what each block means)."""
    if name not in SPEC:
        raise ValueError("unknown bot %r (one of %s)" % (name, ", ".join(BOTS)))
    now = time.time() if now is None else float(now)
    c, rows, ok = _load(now, getter, procs)
    return _bot_from(c, name, now, rows, ok)


def all_bots(now=None, getter=None, procs=None):
    """Every bot, the `other` main-account markets, and the ALL-BOTS total with each bot's share."""
    now = time.time() if now is None else float(now)
    c, rows, ok = _load(now, getter, procs)
    today = et_day(now)
    bots = {b: _bot_from(c, b, now, rows, ok) for b in BOTS}
    other = _money_block(c, "other", today)
    other.pop("markets", None)
    other["label"] = "Other main-account markets (the old oil bot, anything unlisted)"
    total, missing = {}, [b for b in BOTS if not bots[b]["money"]["ok"]] + ([] if other["ok"] else ["other"])
    parts = [(b, bots[b]["money"]) for b in BOTS] + [("other", other)]
    for w in ("today", "yesterday", "last_7_days", "this_month", "all_time"):
        got = [(b, m[w]) for b, m in parts if m.get(w)]
        mk = sum(x["markets"] for _, x in got)
        money = sum(x["money"] for _, x in got)
        put_in = sum(x["put_in"] for _, x in got)
        total[w] = {"label": got[0][1]["label"] if got else w, "markets": mk,
                    "won": sum(x["won"] for _, x in got), "lost": sum(x["lost"] for _, x in got),
                    "money": round(money, 4), "put_in": round(put_in, 4),
                    "return_pct": round(100.0 * money / put_in, 2) if put_in > 0 else None,
                    "by_bot": {b: round(x["money"], 4) for b, x in got},
                    "by_bot_put_in": {b: round(x["put_in"], 4) for b, x in got},
                    "by_bot_markets": {b: x["markets"] for b, x in got},
                    "partial": bool(missing), "missing": missing}
    days_7 = []
    for k in range(7):
        d = shift_day(today, -k)
        by = {}
        for b, m in parts:
            for x in m.get("days_7") or []:
                if x["day"] == d:
                    by[b] = x
        days_7.append({"day": d, "label": day_label(d), "markets": sum(x["markets"] for x in by.values()),
                       "money": round(sum(x["money"] for x in by.values()), 4),
                       "put_in": round(sum(x["put_in"] for x in by.values()), 4),
                       "by_bot": {b: x["money"] for b, x in by.items()}})
    bal = {"main": bots["pin"]["balance"]["dollars"], "forecaster": bots["forecaster"]["balance"]["dollars"],
           "ladder": bots["ladder"]["balance"]["dollars"]}
    bal["all"] = round(sum(bal.values()), 4) if all(v is not None for v in bal.values()) else None
    bal["main_holds"] = ["pin", "race"]
    note = ("The main account's cash%s holds the pin bot and the coin race together; the forecaster "
            "(subaccount 2) and the ladder (subaccount 1) are separate pots and are NOT in the main account's "
            "cash or its money totals." % (" (%s)" % usd(bal["main"]).lstrip("+") if bal["main"] is not None else ""))
    errors = [("%s: %s" % (b, e)) for b in BOTS for e in bots[b]["errors"]]
    return {"as_of_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "as_of_et": et_clock(now),
            "today_et": today, "bots": bots, "other": other, "total": total, "total_days_7": days_7,
            "balances": bal, "note": note, "errors": sorted(set(errors))}


# ---- words for a phone screen -------------------------------------------------
# The bots' refusal reasons in ordinary words (the dict keeps the raw names).
PLAIN = [(r"^no_offer$", "nothing for sale"), (r"^edge_floor$", "edge too thin"),
         (r"^price_ceiling$", "price over the cap"), (r"^confidence$", "not sure enough"),
         (r"^depth_floor$", "too few for sale"), (r"^book_stale$", "order book too old"),
         (r"^index_stale$", "price feed too old"), (r"^toxic_fresh$", "sellers dumping"),
         (r"^jump_against$", "price jumped against us"), (r"^early_dear$", "early price too high"),
         (r"^early_once$", "early bet already taken"), (r"^max_per_market$", "market already full"),
         (r"^market_attempts$", "tried this market enough"), (r"^close_budget", "quarter-hour budget used"),
         (r"^tau N is past", "too early"), (r"already holding", "already holds that coin"),
         (r"^halted", "halted after a loss"), (r"confirmation", "still confirming"),
         (r"^price N is under", "price under its floor"), (r"under one contract", "bet under 1 contract"),
         (r"^in_flight$", "order already in flight"), (r"^late$", "too late to send"),
         (r"^stale$", "decision went stale"), (r"^cap$", "at its cap"), (r"^price$", "price out of range"),
         (r"^max_contracts$", "contract cap"), (r"^max_commit$", "money cap")]


def plain(why):
    for pat, words in PLAIN:
        if re.search(pat, str(why)):
            return words
    return str(why)


def _n(k, word):
    return "%d %s%s" % (k, word, "" if k == 1 else "s")


def _wline(w, name):
    if w is None:
        return "%s: COULD NOT READ KALSHI" % name
    if not w["markets"]:
        return "%s: nothing settled" % name
    return "%s: %s on %s in (%s), %d won, %d lost" % (
        name, usd(w["money"]), usd(w["put_in"]).lstrip("+"), pct(w["return_pct"]), w["won"], w["lost"])


def _bot_text(b):
    L = []
    r = b["running"]
    L.append("%s -- %s" % (b["label"].upper(), b["what"]))
    L.append("Pot: %s" % (SUB_NAME[str(b["subaccount"])] + (" (shared with %s)" % ", ".join(
        SPEC[x]["label"].lower() for x in b["shares_subaccount_with"]) if b["shares_subaccount_with"] else "")))
    if r["alive"] is None:
        L.append("Running: COULD NOT TELL (process list unreadable)")
    elif r["alive"]:
        L.append("Running: yes, since %s (pid %s)" % (r["started_et"] or "?", r["pid"]))
    else:
        L.append("Running: NO" + (" -- stopped by its stop file (%s)" % r["stop_flag_et"] if r["stop_flag"] else ""))
    if r["halted"]:
        L.append("HALTED %s: %s" % (r["halted"]["t_et"], r["halted"]["why"] or r["halted"]["what"]))
    for p in r["problems"]:
        if not p.startswith("stop file is set") or r["alive"]:
            L.append("! " + p)
    if r["version"]:
        L.append("Version: %s (%s)" % (r["version"], r["version_et"] or "no time"))
    if r["settings_text"]:
        L.append("Settings: " + r["settings_text"])
    if not r["keepalive"]:
        L.append("Keep-alive: none -- if it dies nothing restarts it")
    m = b["money"]
    L.append("")
    if not m["ok"]:
        L.append("MONEY: COULD NOT READ KALSHI (%s)" % (m["error"] or "?"))
    else:
        head = "Money (Kalshi, by market close day ET)"
        if not m["complete"]:
            head += " -- HISTORY STILL LOADING, all-time is partial"
        if m["stale"]:
            head += " -- last read failed, showing %s" % (m["as_of_et"] or "?")
        L.append(head + ":")
        for k in ("today", "yesterday", "last_7_days", "this_month", "all_time"):
            L.append(_wline(m[k], m[k]["label"]))
        for k in ("today", "all_time"):
            w = m[k]
            if w["markets"]:
                wd = "" if k == "today" else " (%s)" % day_label(w["worst"]["day"])
                bd = "" if k == "today" else " (%s)" % day_label(w["best"]["day"])
                L.append("  %s worst %s %s%s, best %s %s%s" % (w["label"].lower(), usd(w["worst"]["money"]),
                                                              w["worst"]["what"], wd, usd(w["best"]["money"]),
                                                              w["best"]["what"], bd))
        if m["all_time"]["hedged"]:
            L.append("  hedged markets: %d all time" % m["all_time"]["hedged"])
        days = [d for d in m["days_7"] if not d["before_first"]]
        if days:
            L.append("By day:")
            for d in days:
                L.append("  %s: %s" % (d["label"], "nothing settled" if not d["markets"] else
                                       "%s, %s (%d won)" % (usd(d["money"]), _n(d["markets"], "market"), d["won"])))
        if m["first_day"]:
            L.append("First settled: %s" % day_label(m["first_day"]))
    o = b["open"]
    if not o["ok"]:
        L.append("Open now: COULD NOT READ (%s)" % o["error"])
    elif not o["count"]:
        L.append("Open now: none")
    else:
        L.append("Open now: %d, %s at risk" % (o["count"], usd(o["at_risk"]).lstrip("+")))
        for p in o["positions"][:6]:
            L.append("  %s %s x%g" % (p["what"], p["side"].upper(), p["contracts"]))
    bal = b["balance"]
    L.append("Cash: %s (%s)" % ((usd(bal["dollars"]).lstrip("+") if bal["ok"] else "COULD NOT READ"), bal["note"]))
    if b["last_settled"]:
        L.append("Last settled:")
        for x in b["last_settled"]:
            day = pinday.et_day_of_ticker(x["ticker"])
            L.append("  %s %s %s x%g %s" % (day_label(day) if day else (x["time_et"] or "?"), x["what"],
                                            {"both": "BOTH SIDES", "-": "-"}.get(x["side"], x["side"].upper()),
                                            x["contracts"], usd(x["money"])))
    a = b["activity_today"]
    if not a["ok"]:
        L.append("Today's log: %s" % a["note"])
    else:
        s = "Today (its log): %s sent, %d filled (%g contracts)" % (_n(a["sent"], "order"), a["filled"],
                                                                    a["contracts_filled"])
        if b["name"] == "pin" and a["hedges"]:
            s += ", " + _n(a["hedges"], "hedge")
        if b["name"] == "ladder":
            s += ", %d cancelled" % a["cancelled"]
        L.append(s)
        if a["refused"]:
            grouped = {}
            for k, v in a["refused_why"].items():
                grouped[plain(k)] = grouped.get(plain(k), 0) + v
            top = ", ".join("%s %d" % (k, v) for k, v in sorted(grouped.items(), key=lambda kv: -kv[1])[:3])
            L.append("  %s %d times (%s)" % ("passed" if b["name"] == "pin" else "refused", a["refused"], top))
        for h in a["halts"][-3:]:
            L.append("  %s %s %s" % (h["t_et"], h["what"], h["why"]))
    return "\n".join(L)


def text_summary(name="all", now=None, getter=None, procs=None):
    """Plain words, ET, short lines, for a phone screen. `name` is a bot or 'all'."""
    if name != "all":
        return _bot_text(bot(name, now=now, getter=getter, procs=procs))
    a = all_bots(now=now, getter=getter, procs=procs)
    L = ["ALL BOTS -- %s" % a["as_of_et"]]
    for w in ("today", "yesterday", "last_7_days", "this_month", "all_time"):
        t = a["total"][w]
        L.append(_wline(t, t["label"]))
        bits = ["%s %s" % (b, usd(v) if t["by_bot_markets"][b] else "none") for b, v in t["by_bot"].items()
                if b != "other" or t["by_bot_markets"][b]]
        if t["markets"]:
            L.append("  " + " | ".join(bits))
        if t["partial"]:
            L.append("  PARTIAL -- could not read: %s" % ", ".join(t["missing"]))
    L.append("By day:")
    for d in a["total_days_7"]:
        L.append("  %s: %s" % (d["label"], "nothing settled" if not d["markets"] else
                               "%s, %s" % (usd(d["money"]), _n(d["markets"], "market"))))
    bal = a["balances"]

    def cash(x):
        return "?" if x is None else usd(x).lstrip("+")
    L.append("Cash: main %s (pin + race), forecaster %s, ladder %s, all %s" % (
        cash(bal["main"]), cash(bal["forecaster"]), cash(bal["ladder"]), cash(bal["all"])))
    L.append("Main-page totals include pin + race only; forecaster and ladder are separate pots.")
    run = []
    for b in BOTS:
        r = a["bots"][b]["running"]
        s = "?" if r["alive"] is None else ("yes" if r["alive"] else ("stopped (flag)" if r["stop_flag"] else "NO"))
        if r["halted"]:
            s += ", HALTED"
        run.append("%s %s" % (b, s))
    L.append("Running: " + ", ".join(run))
    for b in BOTS:
        o = a["bots"][b]["open"]
        if o["ok"] and o["count"]:
            L.append("Open: %s %d (%s at risk)" % (b, o["count"], usd(o["at_risk"]).lstrip("+")))
    for e in a["errors"]:
        L.append("! " + e)
    return "\n".join(L)


# ---- self-test -----------------------------------------------------------------
def selftest():
    import shutil
    import tempfile

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("botstats selftest: FAILED -- " + msg)

    # 0. READ ONLY, BY CONSTRUCTION. The forbidden words are assembled from pieces so this check
    # does not find itself; everything else in the file is scanned.
    with open(os.path.abspath(__file__), encoding="utf-8") as fh:
        src = fh.read()
    bad = [p for p in (r"\b" + "PO" + r"ST\b", r"\b" + "DEL" + r"ETE\b", r"\b" + "PA" + r"TCH\b", r"\b" + "PU" + r"T\b",
                       "portfolio/" + "orders", "events/" + "orders", "subaccounts/" + "transfer", "order" + "cli",
                       "pin" + "take", "url" + "open", "urllib" + ".request", "Stop-" + "Process", "Start-" + "Process",
                       "task" + "kill", r"os\." + "kill", r"\." + r"terminate\(", "Invoke-" + "WebRequest",
                       "Terminate" + "Process", "Create" + "Process", "Write" + "ProcessMemory", "Shell" + "Execute")
           if re.search(p, src)]
    ck(not bad, "this file contains no order, cancel, transfer or process-control call (found: %s)" % bad)
    masks = re.findall(r"k32\." + r"OpenProcess\(\s*([^,]+),", src)
    ck(masks and all(m.strip() == "0x1000" for m in masks),
       "every process handle is opened with QUERY_LIMITED_INFORMATION (0x1000) only: %s" % masks)

    NOW = float(calendar.timegm((2026, 9, 30, 16, 30, 0)))          # 12:30 PM ET, Wed Sep 30

    def S(tk, st, res, yn=0.0, yc=0.0, nn=0.0, nc=0.0, fee=0.0, value=None):
        v = {"yes": 100, "no": 0}.get(res) if value is None else value
        return {"ticker": tk, "settled_time": st, "market_result": res, "value": v, "event_ticker": tk[:20],
                "yes_count_fp": "%.2f" % yn, "yes_total_cost_dollars": "%.6f" % yc,
                "no_count_fp": "%.2f" % nn, "no_total_cost_dollars": "%.6f" % nc, "fee_cost": "%.6f" % fee,
                "revenue": 0, "exchange_index": 2}
    sub0 = [S("KXBTC15M-26SEP301145-45", "2026-09-30T15:45:05Z", "no", nn=50, nc=49.00, fee=0.10),        # +0.90
            S("KXETH15M-26SEP301100-00", "2026-09-30T15:00:05Z", "yes", yn=40, yc=38.80, nn=40, nc=12.00,
              fee=0.50),                                                                                 # -11.30 hedged
            S("KXCRYPTOLEAD15M-26SEP301030-XRP", "2026-09-30T14:31:10Z", "yes", yn=20, yc=19.60, fee=0.03),   # +0.37
            S("KXCRYPTOLEAD15M-26SEP301015-HYPE", "2026-09-30T14:16:00Z", "scalar", nn=10, nc=9.80, fee=0.01,
              value=50),                                                                                 # -4.81 tie
            S("KXXRP15M-26SEP300000-00", "2026-09-30T04:00:05Z", "yes", yn=10, yc=9.70, fee=0.02),            # +0.28 today
            S("KXSOL15M-26SEP292345-45", "2026-09-30T03:45:05Z", "yes", yn=30, yc=29.40, fee=0.06),           # +0.54 the 29th
            S("KXWTI15M-26SEP291400-00", "2026-09-29T18:00:05Z", "no", yn=5, yc=4.50, fee=0.01),             # -4.51 other
            S("KXBTCD-26SEP2911-T82899.99", "2026-09-29T15:00:05Z", "yes", yn=1, yc=0.98),                   # +0.02
            S("KXHYPE15M-26SEP241200-00", "2026-09-24T16:00:05Z", "yes", yn=10, yc=9.80, fee=0.02),           # +0.18
            S("KXDOGE15M-26SEP221200-00", "2026-09-22T16:00:05Z", "no", nn=20, nc=19.00, fee=0.04),           # +0.96
            S("KXBNB15M-26AUG311500-00", "2026-08-31T19:00:05Z", "no", yn=10, yc=9.50, fee=0.02)]             # -9.52
    sub1 = [S("KXNEAR15M-26SEP301130-30", "2026-09-30T15:30:05Z", "yes", yn=2, yc=1.958),                  # +0.042
            S("KXBNB15M-26SEP291745-45", "2026-09-29T21:45:06Z", "yes", yn=2, yc=1.96)]                     # +0.04
    sub2 = [S("KXETH15M-26SEP301200-00", "2026-09-30T16:00:06Z", "no", yn=5, yc=2.45, fee=0.0875),         # -2.5375
            S("KXNEAR15M-26SEP300030-30", "2026-09-30T04:30:06Z", "yes", yn=2, yc=1.93, fee=0.0048),          # +0.0652
            S("KXXRP15M-26SEP292300-00", "2026-09-30T03:00:06Z", "yes", yn=3, yc=2.42, fee=0.0328)]           # +0.5472
    world = {"0": sub0, "1": sub1, "2": sub2}
    poss = {"0": [{"ticker": "KXBTC15M-26SEP301245-45", "position_fp": "-30.00", "market_exposure_dollars": "29.10"},
                  {"ticker": "KXCRYPTOLEAD15M-26SEP301230-SOL", "position_fp": "20.00",
                   "market_exposure_dollars": "19.60"}],
            "1": [{"ticker": "KXNEAR15M-26SEP301245-45", "position_fp": "1.00", "market_exposure_dollars": "0.98"}],
            "2": []}
    bals = {"0": "1000.0000", "1": "15.1000", "2": "24.0000"}
    asked = []
    fail = {"page2": False, "all": False}

    def fake(path, q):
        asked.append((path, dict(q or {})))
        if fail["all"]:
            return 401, {"error": "nope"}
        sub = str((q or {}).get("subaccount"))
        if path == "/portfolio/settlements":
            rows = world.get(sub, [])
            if sub == "0":           # two pages, to exercise the cursor
                if not q.get("cursor"):
                    return 200, {"settlements": rows[:6], "cursor": "c-0-2"}
                if fail["page2"]:
                    return 500, "boom"
                return 200, {"settlements": rows[6:], "cursor": ""}
            return 200, {"settlements": rows, "cursor": ""}
        if path == "/portfolio/positions":
            return 200, {"market_positions": poss.get(sub, []), "event_positions": [], "cursor": ""}
        if path == "/portfolio/balance":
            return 200, {"balance": 0, "balance_dollars": bals.get(sub, "0")}
        return 404, {}

    def J(path, recs):
        with open(path, "w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")

    saved = (RESULTS, dict(_MEMO), dict(_BACK))
    td = tempfile.mkdtemp(prefix="botstats-")
    try:
        globals()["RESULTS"] = td
        _MEMO.update(key=None, data=None)
        _BACK.clear()
        # planted logs
        J(os.path.join(td, "pinrun-live-20260928T143553Z.jsonl"), [
            {"kind": "start", "t": "2026-09-28T14:35:53Z", "size": 20.0, "price_ceiling": 0.98, "tau_max": 30,
             "early_tau_max": 45, "early_frac": 0.333, "early_min_price": 0.9, "early_max_price": 0.978,
             "hedge_belief": 0.4, "loss_cap": 200.0, "max_positions": 3, "ladder_series": ["KXBTCD"],
             "code_sha": "abc"},
            {"kind": "order", "t": "2026-09-30T03:00:00Z", "filled": 91.0},        # 11 PM ET on the 29th: not today
            {"kind": "refused", "t": "2026-09-30T13:00:00Z", "gate": "no_offer"},
            {"kind": "refused", "t": "2026-09-30T13:00:01Z", "gate": "no_offer"},
            {"kind": "refused", "t": "2026-09-30T13:00:02Z", "gate": "edge_floor"},
            {"kind": "hedge", "t": "2026-09-30T14:59:30Z", "live": True},
            {"kind": "order", "t": "2026-09-30T15:30:00Z", "filled": 0.0, "status": "canceled"},
            {"kind": "order", "t": "2026-09-30T15:44:40Z", "filled": 50.0}])
        os.utime(os.path.join(td, "pinrun-live-20260928T143553Z.jsonl"), (NOW, NOW))
        with open(os.path.join(td, "pinrun-live-size.json"), "w", encoding="utf-8") as fh:
            json.dump({"size": 92.0, "bank": 1088.7, "at": "2026-09-30T16:00:00Z", "epoch": NOW - 1800}, fh)
        J(os.path.join(td, "pinracepenny-live.jsonl"), [
            {"kind": "start", "t": "2026-09-27T06:01:49Z", "argv": ["--live", "--max-contracts", "10"]},
            {"kind": "live_halt", "t": "2026-09-27T09:00:00Z", "why": "an OLD halt, before the latest start"},
            {"kind": "start", "t": "2026-09-28T02:50:14Z", "version": "2026-09-24-tie1", "stop_on_loss": True,
             "argv": ["--live", "--max-contracts", "20", "--max-stake", "60", "--live-tau-max", "30",
                      "--live-min-price", "0.90", "--live-max-legs", "5"],
             "live_rails": {"stop_on_loss": True}},
            {"kind": "live_order", "t": "2026-09-30T14:30:40Z", "filled": 20.0},
            {"kind": "live_order", "t": "2026-09-30T14:15:40Z", "filled": 0.0, "status": "canceled"},
            {"kind": "live_refused", "t": "2026-09-30T14:15:41Z", "why": ["one position per race"]},
            {"kind": "live_refused", "t": "2026-09-30T14:15:42Z", "why": ["one position per race"]},
            {"kind": "live_refused", "t": "2026-09-30T14:29:01Z", "why": ["tau 54 is past the 30s bar"]},
            {"kind": "live_refused", "t": "2026-09-30T14:29:02Z", "why": ["tau 53 is past the 30s bar"]}])
        J(os.path.join(td, "forecaster-live-orders.jsonl"), [
            {"t": "2026-09-29T04:21:01.848Z", "ev": "start", "pid": 4036456, "live": True, "variant": "race05_98",
             "rails": {"scale": "0.05"}},
            {"t": "2026-09-29T15:35:02.502Z", "ev": "start", "pid": 4196192, "live": True, "variant": "race1_98",
             "variant_params": {"race_x": 1.0, "race_p": 0.98},
             "rails": {"scale": "0.05", "per_side": 5, "per_close": 20, "max_commit": 22.0, "px": [0.75, 0.985],
                       "day_stop": -12.0, "run_stop": -20.0}},
            {"t": "2026-09-30T15:59:30.000Z", "ev": "placed", "filled": 5.0},
            {"t": "2026-09-30T15:59:30.100Z", "ev": "live_fill", "n": 5},
            {"t": "2026-09-30T15:59:40.000Z", "ev": "placed", "filled": 0.0},
            {"t": "2026-09-30T15:59:41.000Z", "ev": "refused", "why": "in_flight"},
            {"t": "2026-09-30T15:59:59.600Z", "ev": "dropped", "why": "late"},
            {"t": "2026-09-30T16:10:00.000Z", "ev": "start", "pid": 999, "live": False, "variant": "dry-run"}])
        J(os.path.join(td, "ladder-live-orders.jsonl"), [
            {"t": "2026-09-29T17:16:12.117Z", "ev": "start", "pid": 4217364, "live": True,
             "rails": {"size": 1, "max_contracts": 10, "max_commit": 12.0, "day_stop": -6.0,
                       "max_live_per_close": 9, "live_levels": [0]}},
            {"t": "2026-09-30T15:29:30Z", "ev": "placed"}, {"t": "2026-09-30T15:29:31Z", "ev": "placed"},
            {"t": "2026-09-30T15:29:32Z", "ev": "placed"},
            {"t": "2026-09-30T15:29:40Z", "ev": "live_fill", "delta": 1},
            {"t": "2026-09-30T15:29:50Z", "ev": "rail_refused", "why": "max_contracts"},
            {"t": "2026-09-30T15:30:00Z", "ev": "cancelled"}, {"t": "2026-09-30T15:30:00Z", "ev": "cancelled"},
            {"t": "2026-09-30T15:40:00Z", "ev": "stop_file"}, {"t": "2026-09-30T15:40:00Z", "ev": "exit"}])
        with open(os.path.join(td, "ladder-live.stop"), "w") as fh:
            fh.write("")
        with open(os.path.join(td, VERSIONS_NAME), "w", encoding="utf-8") as fh:
            fh.write("# Versions\n\n"
                     "# v-ladder-settlefix -- LIVE 2026-09-29 17:16:12Z (pid 4217364; research/cleanroom/ladder_live.py): x\n"
                     "# v-keepalive-cleanroom -- 2026-09-29 15:37Z (boot_all): forecaster_live and ladder_live restart\n"
                     "# v-forecaster-race1 -- LIVE 2026-09-29 15:35:02Z (pid 4196192): race1_98\n"
                     "# v-reopen98 + v-floor90 -- 2026-09-28 14:36:17Z (pid 3882400; no code change) -- LIVE: 98c\n"
                     "# v-race20 -- 2026-09-28 02:50Z (pid 3739628; pinracearm.py) -- LIVE: coin race penny bot 20\n"
                     "# v-ladder7 -- 2026-09-25 03:2xZ -- CODE ON DISK: the ladder table knows seven hourly series\n")
        PROCS = [(3882400, "2026-09-28T14:35:48Z", "C:\\Python314\\python.exe -u C:\\kals-repo\\research\\pinrun.py "
                  "--live --size 20 --max-losses 2 --series KXBTCD --series-size 1 --one-full-bet --toxic-fresh"),
                 (2966252, "2026-09-25T12:25:44Z", "python -u C:\\kals-repo\\research\\pinrun.py --size 20 --arm-name arm-x"),
                 (1111, "", "python -u C:\\kals-repo\\research\\pinrun_afternoon.py --live"),
                 (3739628, "2026-09-28T02:50:10Z", "python -u research/pinracearm.py --live --max-contracts 20 "
                  "--max-stake 60 --live-tau-max 30 --live-min-price 0.90 --live-max-legs 5"),
                 (2574672, "2026-09-24T05:56:08Z", "python -u research/pinracearm.py --paper-live --live-tau-max 60"),
                 (4196192, "2026-09-29T15:34:56Z", "python -u research\\cleanroom\\forecaster_live.py --subaccount 2 "
                  "--live --variant race1_98 --minutes 10080"),
                 (3575912, "2026-09-27T13:47:08Z", "python research\\cleanroom\\locked_average_ladder_re_paper.py")]

        # 1. the planted world, first read: a full walk of every pot
        a = all_bots(now=NOW, getter=fake, procs=PROCS)
        ck(asked and all(q.get("subaccount") in ("0", "1", "2") for _, q in asked),
           "EVERY Kalshi request names its subaccount -- with none, settlements mix every pot's rows")
        ck(set(p for p, _ in asked) <= set(PATHS),
           "and only the three read paths are ever asked for: %s" % sorted(set(p for p, _ in asked)))
        ck(sum(1 for p, q in asked if p == "/portfolio/settlements" and q["subaccount"] == "0") == 2,
           "the first read walks the main account's two settlement pages to the end")
        pin, race, fc, lad = (a["bots"][b] for b in BOTS)
        pm = pin["money"]
        ck(pm["today"]["markets"] == 3 and abs(pm["today"]["money"] - (-10.12)) < 1e-6
           and pm["today"]["won"] == 2 and pm["today"]["lost"] == 1 and pm["today"]["hedged"] == 1,
           "pin TODAY: 3 markets, 2 won 1 lost, -$10.12 (the hedged ETH market pays its winning YES side: "
           "$40 - $50.80 - $0.50 = -$11.30, not the -$51.30 that `revenue: 0` would say)")
        ck(abs(pm["today"]["put_in"] - 109.50) < 1e-6 and abs(pm["today"]["return_pct"] - (-9.24)) < 0.01,
           "put in is both sides' cost ($109.50); return -9.24%")
        ck(pm["yesterday"]["markets"] == 2 and abs(pm["yesterday"]["money"] - 0.56) < 1e-6,
           "yesterday is +$0.56: the SOL market closing 11:45 PM ET on the 29th belongs to the 29th although "
           "Kalshi settled it at 03:45 UTC on the 30th; the XRP one closing at midnight belongs to the 30th")
        ck(pm["last_7_days"]["markets"] == 6 and abs(pm["last_7_days"]["money"] - (-9.38)) < 1e-6,
           "last 7 days (Sep 24-30) -$9.38; the Sep 22 market is outside it")
        ck(pm["this_month"]["markets"] == 7 and abs(pm["this_month"]["money"] - (-8.42)) < 1e-6
           and pm["all_time"]["markets"] == 8 and abs(pm["all_time"]["money"] - (-17.94)) < 1e-6,
           "September -$8.42; all time -$17.94 (the Aug 31 market counts only all-time)")
        ck(pm["all_time"]["worst"]["ticker"] == "KXETH15M-26SEP301100-00"
           and pm["all_time"]["best"]["ticker"] == "KXDOGE15M-26SEP221200-00",
           "worst and best are single markets (-$11.30 ETH, +$0.96 DOGE)")
        ck(len(pm["days_7"]) == 7 and pm["days_7"][0]["day"] == "2026-09-30" and pm["days_7"][6]["day"] == "2026-09-24"
           and abs(pm["days_7"][6]["money"] - 0.18) < 1e-6 and pm["days_7"][3]["markets"] == 0,
           "the per-day list is 7 ET days newest first, empty days kept as empty (not dropped)")
        ck(race["money"]["today"]["markets"] == 2 and abs(race["money"]["today"]["money"] - (-4.44)) < 1e-6
           and race["money"]["today"]["lost"] == 1,
           "race today -$4.44: the tie pays 50c a contract ($5 on 10 NO), a -$4.81 loss, not -$9.81")
        ck(not any(m["ticker"].startswith("KXCRYPTOLEAD") for m in [pm["all_time"]["worst"], pm["all_time"]["best"]])
           and pm["all_time"]["markets"] == 8 and race["money"]["all_time"]["markets"] == 2,
           "race markets are never pin's and pin's never the race's, though they share a pot")
        ck(abs(a["other"]["all_time"]["money"] - (-4.51)) < 1e-6 and a["other"]["all_time"]["markets"] == 1,
           "the old oil bot's WTI market is `other`, shown -- not folded into pin")
        ck(abs(fc["money"]["today"]["money"] - (-2.4723)) < 1e-6 and fc["money"]["today"]["markets"] == 2
           and abs(fc["money"]["yesterday"]["money"] - 0.5472) < 1e-6,
           "forecaster (subaccount 2) today -$2.47 on 2 markets, yesterday +$0.55")
        ck(abs(lad["money"]["today"]["money"] - 0.042) < 1e-6 and abs(lad["money"]["all_time"]["money"] - 0.082) < 1e-6,
           "ladder (subaccount 1) today +$0.04, all time +$0.08")
        t = a["total"]
        ck(abs(t["today"]["money"] - (-10.12 - 4.44 - 2.4723 + 0.042)) < 1e-6
           and abs(t["yesterday"]["money"] - (0.56 + 0.5472 + 0.04 - 4.51)) < 1e-6
           and t["today"]["by_bot"]["forecaster"] == round(-2.4723, 4) and not t["today"]["partial"],
           "the ALL-BOTS total is the four bots plus `other`, each bot's share listed")
        ck(abs(t["all_time"]["money"] - sum(pinledger.pnl(s) for v in world.values() for s in v)) < 1e-6,
           "and all time equals every settlement in every pot, each counted once")
        ck(pin["balance"]["dollars"] == 1000.0 and pin["balance"]["shared_with"] == ["race"]
           and race["balance"]["shared_with"] == ["pin"] and "shared" in pin["balance"]["note"]
           and a["balances"]["all"] == 1039.1 and "NOT in the main" in a["note"],
           "cash: pin and race SHARE the main pot ($1,000) and say so; all pots $1,039.10")
        ck(pin["open"]["count"] == 1 and pin["open"]["positions"][0]["side"] == "no"
           and pin["open"]["positions"][0]["contracts"] == 30 and race["open"]["count"] == 1
           and lad["open"]["count"] == 1 and fc["open"]["count"] == 0,
           "open positions are split by ticker inside the shared pot (pin NO x30, race SOL)")
        ck([x["ticker"] for x in pin["last_settled"]][:2] == ["KXBTC15M-26SEP301145-45", "KXETH15M-26SEP301100-00"]
           and pin["last_settled"][1]["side"] == "both" and len(pin["last_settled"]) == 5,
           "last settled: newest first, five of them, the hedged one marked both sides")
        ck(pin["last_settled"][0]["time_et"] == "Sep 30 11:45 AM ET",
           "times are ET (15:45 UTC shows as 11:45 AM ET)")
        # running
        pr = pin["running"]
        ck(pr["alive"] is True and pr["pids"] == [3882400] and race["running"]["pids"] == [3739628]
           and pr["started_et"] == "Sep 28 10:35 AM ET",
           "pin: the --live pinrun is the bot (the paper arm and pinrun_afternoon are not); started in ET")
        ck(pr["version"] == "v-reopen98 + v-floor90" and race["running"]["version"] == "v-race20"
           and fc["running"]["version"] == "v-forecaster-race1" and lad["running"]["version"] == "v-ladder-settlefix",
           "each bot's newest VERSIONS.md entry (the clean-room keep-alive and v-ladder7 are not the ladder's)")
        ck(pr["settings"]["bet_now"] == 92.0 and "bet 92 contracts" in pr["settings_text"]
           and "97.8c" in pr["settings_text"] and "40%" in pr["settings_text"]
           and pr["settings"].get("max_losses") == 2.0,
           "pin settings: bet size from pinrun-live-size.json, the rest from its start record + command line")
        rr = race["running"]
        ck(rr["alive"] is True and rr["pid"] == 3739628 and rr["settings"]["contracts_per_bet"] == 20
           and rr["halted"] is None and rr["keepalive"] is None and "nothing restarts" in text_summary(
               "race", now=NOW + 1, getter=fake, procs=PROCS),
           "race: the --live copy (not --paper-live), 20 a bet; an OLD halt before its start is not a halt; "
           "no keep-alive, said out loud")
        fr = fc["running"]
        ck(fr["alive"] is True and fr["settings"]["variant"] == "race1_98" and "variant_mismatch" not in fr["settings"],
           "forecaster: variant from the start record whose pid is the running process (not the later dry run)")
        lr = lad["running"]
        ck(lr["alive"] is False and lr["stop_flag"] is True and "top rung" in lr["settings_text"],
           "ladder: the ladder PAPER bot is not the live ladder; not running, stopped by its stop file")
        # activity from the logs
        ap_, ar, af, al = (a["bots"][b]["activity_today"] for b in BOTS)
        ck(ap_["sent"] == 2 and ap_["filled"] == 1 and ap_["contracts_filled"] == 50 and ap_["hedges"] == 1
           and ap_["refused"] == 3 and ap_["refused_why"] == {"no_offer": 2, "edge_floor": 1},
           "pin today: 2 orders, 1 filled (50), 1 hedge, 3 passes by gate -- the 11 PM ET order is yesterday's")
        ck(ar["sent"] == 2 and ar["filled"] == 1 and ar["refused"] == 4
           and ar["refused_why"].get("tau N is past the Ns bar") == 2
           and "too early 2" in _bot_text(race),
           "race today: 2 sent, 1 filled, 4 refused -- reasons that differ only in their numbers group as one "
           "('too early 2'), not one line per second")
        ck(af["sent"] == 2 and af["filled"] == 1 and af["contracts_filled"] == 5 and af["refused"] == 2,
           "forecaster today: 2 sent, 1 filled (5 contracts), refused + dropped 2")
        ck(al["sent"] == 3 and al["filled"] == 1 and al["cancelled"] == 2 and al["refused"] == 1
           and any(h["what"] == "stop_file" for h in al["halts"]),
           "ladder today: 3 bids placed, 1 filled, 2 cancelled, 1 refused, and the stop file seen")

        # 2. the cache: a read within 60 s asks Kalshi nothing; after 60 s one page a pot, no double count
        n0 = len(asked)
        a2 = all_bots(now=NOW + 30, getter=fake, procs=PROCS)
        ck(len(asked) == n0 and a2["total"]["all_time"]["money"] == t["all_time"]["money"],
           "a second read within 60 s makes NO request and gives the same totals")
        a3 = all_bots(now=NOW + 90, getter=fake, procs=PROCS)
        st3 = [q for p, q in asked[n0:] if p == "/portfolio/settlements"]
        ck(len(st3) == 3 and a3["total"]["all_time"]["money"] == t["all_time"]["money"],
           "after 60 s: ONE settlements page a pot (it stops at a page it holds) and nothing counted twice")
        sub2.insert(0, S("KXSOL15M-26SEP301215-15", "2026-09-30T16:15:06Z", "yes", yn=4, yc=3.80, fee=0.01))
        a4 = all_bots(now=NOW + 200, getter=fake, procs=PROCS)
        ck(abs(a4["bots"]["forecaster"]["money"]["today"]["money"] - (-2.4723 + 0.19)) < 1e-6,
           "a new settlement is picked up exactly once (+$0.19)")
        with open(cache_path(), encoding="utf-8") as fh:
            cj = json.load(fh)
        ck(set(cj["subs"]) == set(SUBS) and all(set(r) <= set(KEEP) for r in cj["subs"]["0"]["rows"].values()),
           "the cache holds the three pots, each row trimmed to the fields the money needs")

        # 3. a first walk cut short is RESUMED, and flagged partial until it is
        os.remove(cache_path())
        _MEMO.update(key=None, data=None)
        fail["page2"] = True
        b1 = bot("pin", now=NOW, getter=fake, procs=PROCS)
        ck(b1["money"]["complete"] is False and b1["money"]["all_time"]["markets"] < 8
           and "HISTORY STILL LOADING" in _bot_text(b1),
           "a first walk that fails on page 2 is flagged partial, never shown as the whole history")
        fail["page2"] = False
        b2 = bot("pin", now=NOW + 61, getter=fake, procs=PROCS)
        ck(b2["money"]["complete"] is True and b2["money"]["all_time"]["markets"] == 8
           and abs(b2["money"]["all_time"]["money"] - (-17.94)) < 1e-6,
           "and the next read resumes the walk to the end: all 8 pin markets, -$17.94")

        # 4. failures are failures, never $0 or 'not running'
        os.remove(cache_path())
        _MEMO.update(key=None, data=None)
        fail["all"] = True
        f = all_bots(now=NOW, getter=fake, procs=lambda: None)
        fp = f["bots"]["pin"]
        ck(fp["money"]["ok"] is False and fp["money"]["today"] is None and fp["balance"]["dollars"] is None
           and fp["open"]["ok"] is False and f["total"]["today"]["partial"] and f["balances"]["all"] is None,
           "NULL: Kalshi refusing (401) gives money None and a PARTIAL total -- never $0")
        ck(fp["running"]["alive"] is None and "COULD NOT TELL" in _bot_text(fp) and "COULD NOT READ KALSHI" in _bot_text(fp),
           "NULL: an unreadable process list is 'could not tell', never 'not running'")
        fail["all"] = False
    finally:
        globals()["RESULTS"] = saved[0]
        _MEMO.clear()
        _MEMO.update(saved[1])
        _BACK.clear()
        _BACK.update(saved[2])
        shutil.rmtree(td, ignore_errors=True)

    # 5. the EMPTY world: no settlements, no positions, no logs, nothing running
    td = tempfile.mkdtemp(prefix="botstats-empty-")
    try:
        globals()["RESULTS"] = td
        _MEMO.update(key=None, data=None)
        _BACK.clear()

        def empty(path, q):
            if path == "/portfolio/settlements":
                return 200, {"settlements": [], "cursor": ""}
            if path == "/portfolio/positions":
                return 200, {"market_positions": [], "cursor": ""}
            return 200, {"balance": 0, "balance_dollars": "0.0000"}
        e = all_bots(now=NOW, getter=empty, procs=[])
        ck(all(e["bots"][b]["money"]["ok"] and e["bots"][b]["money"]["complete"]
               and e["bots"][b]["money"]["all_time"]["markets"] == 0
               and e["bots"][b]["money"]["all_time"]["money"] == 0.0
               and e["bots"][b]["money"]["all_time"]["return_pct"] is None
               and e["bots"][b]["money"]["all_time"]["worst"] is None
               and e["bots"][b]["money"]["first_day"] is None for b in BOTS),
           "EMPTY: nothing settled gives zero markets, no return, no worst/best -- nothing invented")
        ck(all(e["bots"][b]["running"]["alive"] is False and e["bots"][b]["activity_today"]["ok"] is False
               and e["bots"][b]["last_settled"] == [] and e["bots"][b]["open"]["count"] == 0 for b in BOTS),
           "EMPTY: nothing running, no logs, no open positions, no last markets")
        txt = text_summary("all", now=NOW + 1, getter=empty, procs=[])
        ck("nothing settled" in txt and "+$" not in txt and "-$" not in txt,
           "EMPTY: the phone text says 'nothing settled' and shows no gain or loss")
        ck(all(d["before_first"] for d in e["bots"]["pin"]["money"]["days_7"]),
           "EMPTY: every day is before the first settlement, so the phone lists none")
    finally:
        globals()["RESULTS"] = saved[0]
        _MEMO.clear()
        _MEMO.update(saved[1])
        _BACK.clear()
        _BACK.update(saved[2])
        shutil.rmtree(td, ignore_errors=True)
    # 2026-10-01: a heading that ships several bots at once is each bot's own version, by name
    td2 = tempfile.mkdtemp(prefix="botstats_v_")
    saved2 = RESULTS
    try:
        globals()["RESULTS"] = td2
        with open(os.path.join(td2, VERSIONS_NAME), "w", encoding="utf-8") as fh:
            fh.write("# Versions\n\n"
                     "# v-topup -- LIVE 2026-09-30 12:12:02Z (pid 4447780): top-up to one bet\n"
                     "# v-race40 + v-forecaster-scale + v-ladder-size + v-crash-guard -- LIVE 2026-09-30 12:25:53Z: x\n"
                     "# v-race20 -- 2026-09-28 02:50Z (pid 3739628; pinracearm.py) -- LIVE: coin race 20\n")
        ck(version_of("race")[0] == "v-race40" and version_of("ladder")[0] == "v-ladder-size"
           and version_of("forecaster")[0] == "v-forecaster-scale + v-crash-guard"
           and version_of("pin")[0] == "v-topup",
           "a combined heading is each named bot's version (race v-race40, not the older v-race20); pin keeps its own")
    finally:
        globals()["RESULTS"] = saved2
        shutil.rmtree(td2, ignore_errors=True)
    _s40, _t40 = settings_race(None, "python -u research/pinracearm.py --live --max-contracts 40 --max-stake 120 "
                                     "--live-max-losses 2")
    ck("40 contracts a bet" in _t40 and "stops for the rest of the ET day after 2 losing races" in _t40
       and "first loss" not in _t40, "v-race40: the race's rules read 40 a bet and the daily 2-loss stop")
    _s1, _t1 = settings_race({"live_rails": {"stop_on_loss": True}}, "python -u research/pinracearm.py --live")
    ck("stops after its first loss" in _t1, "NULL: without --live-max-losses the old first-loss stop is still described")
    print("botstats selftest: OK")


def main():
    ap = argparse.ArgumentParser(description="every live bot's numbers, from Kalshi (read only)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--bot", default="all", choices=("all",) + BOTS)
    ap.add_argument("--json", action="store_true", help="print the dict instead of the phone text")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    if a.json:
        d = all_bots() if a.bot == "all" else bot(a.bot)
        print(json.dumps(d, indent=1, default=str))
    else:
        print(text_summary(a.bot))
    return 0


if __name__ == "__main__":
    sys.exit(main())
