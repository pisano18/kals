"""procs.py -- ONE process table: every python.exe on this machine, [pid, started_utc, command line].

v-tg-rebuild step 4 (2026-10-30). There were two readers with two caches (DESIGN 1.6, tangle 4): pinphone's
list_python_procs / python_procs / cached_python_procs / proc_refresher (PowerShell WMI only, 10-35 s, every python.exe,
[(pid, cmdline)]) and botstats' _procs_native / read_procs / procs_for (Windows itself through ctypes in milliseconds,
WMI only when that fails, the bots' scripts only, cached in botstats_cache.json). This module is the one reader:

  native_rows()       Windows itself (Toolhelp snapshot + NtQueryInformationProcess + GetProcessTimes), every python.exe,
                      opened with QUERY_LIMITED_INFORMATION (0x1000) -- the right to look, nothing else. None when any
                      step is unavailable or any python.exe could not be read (it might be one of ours: "could not
                      tell", never "not running").
  wmi_rows(timeout)   the PowerShell WMI read, every python.exe; None on failure.
  read_all(timeout)   native first, WMI only when it fails.
  table(max_age_s)    the cached table (TTL TABLE_TTL_S), read at once when stale -- for the phone (pinphone switches over
                      later; until then it keeps its own reader).
  cached(max_age_s)   the cached table while fresh, else None; never asks Windows (a page that can live with "unknown").
  start_refresher()   a daemon thread re-reading the table every TABLE_TTL_S; only ever started by the caller (never at
                      import: a test or the golden replay must not be left with a thread running).
  pid_cmd(rows)       [(pid, cmdline)]: pinphone's shape.

botstats' names, kept exactly (the golden harness and the phone patch them; their callers here look them up at call time
so a patched one is the one used):
  _procs_native()     native_rows() narrowed to the bots' live scripts (the registry's), None when unreadable.
  read_procs(timeout) _procs_native() first, then WMI narrowed the same way.
  _norm_procs, procs_for(c, now, procs)   botstats' cached-in-botstats_cache.json table, unchanged.

Every text read here is the OS's; this module opens no file. Only subprocess user in botdata (DESIGN section 2 rule).
"""
import subprocess
import threading
import time

import bots as _reg

REFRESH_S = 60                  # botstats' table in its cache is re-read at most this often (botstats.REFRESH_S)
PROC_STALE_S = 300              # an older process table is "could not tell", not "not running"
TABLE_TTL_S = 90                # the shared table's age limit / refresher period (pinphone.PROC_REFRESH_S)

_PS = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ForEach-Object { "
       "$s = ''; if ($_.CreationDate) { $s = $_.CreationDate.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') }; "
       "\"$($_.ProcessId)" + chr(96) + "t$s" + chr(96) + "t$(($_.CommandLine -replace '\\s+', ' '))\" }")

_TABLE = {"t": 0.0, "rows": None}               # every python.exe, the last good read (table / cached / refresher)
_LOCK = threading.Lock()
_REFRESHER = {"thread": None}


# ---- the readers ----------------------------------------------------------------------------------------------------
def native_rows():
    """Every python.exe straight from Windows in milliseconds: a Toolhelp snapshot of process names, then, for each
    python.exe only, its command line (NtQueryInformationProcess class 60) and start time (GetProcessTimes). Every handle
    is opened with QUERY_LIMITED_INFORMATION -- the right to look, nothing else. WMI (the fallback) took 25-35 s on the
    operator's box on 2026-09-30. None when any step is unavailable, or when a python.exe could not be read.
    (botstats._procs_native's body, 2026-09-30, without its narrowing to the bots' scripts)"""
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
        rows.append([pid, started, " ".join(cl.split())])
    # a python.exe we could not read might be one of ours: say "could not tell", not "not running"
    return None if unread else rows


def wmi_rows(timeout=40):
    """Every python.exe through PowerShell WMI ([pid, started, command line]), or None when it fails. Slow (10-35 s):
    only ever a fallback."""
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
        if len(f) < 3:
            continue
        try:
            rows.append([int(f[0].strip()), f[1].strip(), f[2].strip()])
        except ValueError:
            pass
    return rows


def read_all(timeout=40):
    """Every python.exe: the native read first, WMI only when it fails. None when neither could be read."""
    try:
        rows = native_rows()
    except Exception:                                           # noqa: BLE001
        rows = None
    if rows is not None:
        return rows
    return wmi_rows(timeout)


def is_ours(cl):
    """True when a command line runs one of the bots' scripts (any copy: live, paper, dry run)."""
    return any(b.script in cl for b in _reg.all_bots())


def ours(rows):
    """The rows of `rows` that run one of the bots' scripts (botstats' narrowing)."""
    return None if rows is None else [r for r in rows if is_ours(r[2])]


def pid_cmd(rows):
    """[(pid, command line)], pinphone's shape, or None."""
    return None if rows is None else [(int(r[0]), str(r[2])) for r in rows]


# ---- botstats' names (the golden seams patch these two) -----------------------------------------------------------
def _procs_native():
    """botstats._procs_native: the native table narrowed to the bots' scripts, or None."""
    return ours(native_rows())


def read_procs(timeout=40):
    """[[pid, started_utc_or_'', command line]] for OUR scripts, or None when Windows could not be asked. None, never
    [] -- an empty list would read as 'nothing is running'. The native read first; WMI through PowerShell only when it
    fails.  (botstats.read_procs)"""
    try:
        rows = _procs_native()
    except Exception:                                           # noqa: BLE001
        rows = None
    if rows is not None:
        return rows
    return ours(wmi_rows(timeout))


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
    read (and cache in botstats' cache `c`) it here.  (botstats.procs_for)"""
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


# ---- the shared table: cache + refresher (for the phone) ------------------------------------------------------------
def _store(rows, t=None):
    with _LOCK:
        _TABLE.update(t=time.time() if t is None else float(t), rows=rows)


def cached(max_age_s=None):
    """The table last read while it is fresh (under max_age_s, default TABLE_TTL_S + the refresher's slack), else None
    = 'could not be read'. Never asks Windows."""
    lim = max_age_s or 2 * TABLE_TTL_S
    with _LOCK:
        rows, t = _TABLE["rows"], _TABLE["t"]
    if rows is not None and 0.0 <= time.time() - t < lim:
        return rows
    return None


def table(max_age_s=None, timeout=40):
    """The table, from the cache while fresh; stale or empty, one read now (native, WMI fallback). None when it
    cannot be read."""
    rows = cached(max_age_s)
    if rows is not None:
        return rows
    rows = read_all(timeout)
    if rows is not None:
        _store(rows)
    return rows


def refresh_once(timeout=40):
    """One read into the cache now; the rows, or None (the cache keeps its last good table)."""
    rows = read_all(timeout)
    if rows is not None:
        _store(rows)
    return rows


def start_refresher(period=None):
    """Start (once) the daemon thread that keeps the table fresh; returns it. Never started at import."""
    th = _REFRESHER["thread"]
    if th is not None and th.is_alive():
        return th

    def loop():
        while True:
            try:
                refresh_once()
            except Exception:                                   # noqa: BLE001  (a refresher never dies)
                pass
            time.sleep(period or TABLE_TTL_S)
    th = threading.Thread(target=loop, name="botdata-procs", daemon=True)
    _REFRESHER["thread"] = th
    th.start()
    return th
