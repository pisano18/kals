"""/server's machine readings: this Windows machine from kernel32 and the registry (machine_read: CPU, memory, disk,
uptime, a waiting restart, the python processes) and the time to Kalshi (kalshi_ping: a bare TCP connect, no request).

v-tg-rebuild step 9 (2026-10-30, lane D5): MOVED VERBATIM out of research/pinphone.py, which re-exports every name here
(pinphone.machine_read / kalshi_ping stay the seams Ctx.machine() / Ctx.ping() resolve at call time, so a planted or
patched pinphone.machine_read is still the one /server reads). No edit but the imports.
"""
import os
import time

KALSHI_HOST = "api.elections.kalshi.com"
KALSHI_PING_TTL_S = 60
KALSHI_PING_TRIES = 3


# ---- /server: the machine, from Windows itself --------------------------------------------------------------------
_W32 = {}


def _w32():
    """kernel32 through ctypes, set up once in a private handle (its argtypes never touch ctypes.windll's shared one)."""
    if "k32" not in _W32:
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        ft = ctypes.POINTER(wintypes.FILETIME)
        k.GetSystemTimes.argtypes = (ft, ft, ft)
        k.GetSystemTimes.restype = wintypes.BOOL
        k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k.OpenProcess.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = (wintypes.HANDLE,)
        k.CloseHandle.restype = wintypes.BOOL
        k.GetProcessTimes.argtypes = (wintypes.HANDLE, ft, ft, ft, ft)
        k.GetProcessTimes.restype = wintypes.BOOL
        k.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                 ctypes.POINTER(wintypes.DWORD))
        k.QueryFullProcessImageNameW.restype = wintypes.BOOL
        k.K32EnumProcesses.argtypes = (ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
        k.K32EnumProcesses.restype = wintypes.BOOL
        k.K32GetProcessMemoryInfo.argtypes = (wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD)
        k.K32GetProcessMemoryInfo.restype = wintypes.BOOL
        k.GlobalMemoryStatusEx.argtypes = (ctypes.c_void_p,)
        k.GlobalMemoryStatusEx.restype = wintypes.BOOL
        k.GetTickCount64.argtypes = ()
        k.GetTickCount64.restype = ctypes.c_ulonglong
        _W32.update(k32=k, ct=ctypes, wt=wintypes)
    return _W32["k32"], _W32["ct"], _W32["wt"]


def _ft(f):
    return (f.dwHighDateTime << 32) | f.dwLowDateTime          # 100-ns units


def _python_handles(k, ct, wt):
    """{pid: open handle} for every python.exe / pythonw.exe this account may query (the caller closes them)."""
    n = 4096
    while True:
        arr = (wt.DWORD * n)()
        got = wt.DWORD()
        if not k.K32EnumProcesses(arr, ct.sizeof(arr), ct.byref(got)):
            raise OSError("EnumProcesses failed (%d)" % ct.get_last_error())
        if got.value < ct.sizeof(arr):
            break
        n *= 2
    out = {}
    buf = ct.create_unicode_buffer(1024)
    for pid in arr[:got.value // ct.sizeof(wt.DWORD)]:
        if not pid:
            continue
        h = k.OpenProcess(0x1000 | 0x0010, False, pid)            # QUERY_LIMITED_INFORMATION | VM_READ
        if not h:
            h = k.OpenProcess(0x1000, False, pid)
        if not h:
            continue
        size = wt.DWORD(len(buf))
        if k.QueryFullProcessImageNameW(h, 0, buf, ct.byref(size)) \
                and os.path.basename(buf.value).lower() in ("python.exe", "pythonw.exe"):
            out[pid] = h
        else:
            k.CloseHandle(h)
    return out


REBOOT_KEYS = (r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
               r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending")


def reboot_pending():
    """(True, by what) when Windows Update or a Windows component update waits for a restart (either key is there),
    (False, None) when neither is, (None, why) when the registry could not be read."""
    import winreg
    for path in REBOOT_KEYS:
        try:
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path))
            return True, ("Windows Update" if "WindowsUpdate" in path else "a Windows component update")
        except FileNotFoundError:
            continue
        except OSError as e:
            return None, str(e)[:80]
    return False, None


def machine_read(sample_s=0.5):
    """This machine now, from Windows itself. Every figure is None when its call fails, and why goes in `errs`.
    cpu = % busy over `sample_s` seconds, every core; py_cpu = the python processes' (the bots, the recorders, this
    phone link) share of the whole machine over the same seconds; py_mem = the RAM they hold (working sets, bytes)."""
    out = {"host": os.environ.get("COMPUTERNAME"), "ncpu": os.cpu_count(), "cpu": None, "py_cpu": None, "py_n": None,
           "py_mem": None, "mem_total": None, "mem_avail": None, "mem_load": None, "commit": None, "commit_limit": None,
           "disk_free": None, "disk_total": None, "uptime_s": None, "reboot": None, "reboot_why": None,
           "sample_s": sample_s, "errs": []}
    try:
        import shutil
        du = shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
        out["disk_free"], out["disk_total"] = float(du.free), float(du.total)
    except Exception as e:                                      # noqa: BLE001
        out["errs"].append("disk: %s" % str(e)[:80])
    try:
        out["reboot"], out["reboot_why"] = reboot_pending()
    except Exception as e:                                      # noqa: BLE001
        out["errs"].append("restart check: %s" % str(e)[:80])
    try:
        k, ct, wt = _w32()
    except Exception as e:                                      # noqa: BLE001
        out["errs"].append("Windows calls: %s" % str(e)[:80])
        return out
    try:
        class _MS(ct.Structure):
            _fields_ = [("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD), ("ullTotalPhys", ct.c_ulonglong),
                        ("ullAvailPhys", ct.c_ulonglong), ("ullTotalPageFile", ct.c_ulonglong),
                        ("ullAvailPageFile", ct.c_ulonglong), ("ullTotalVirtual", ct.c_ulonglong),
                        ("ullAvailVirtual", ct.c_ulonglong), ("ullAvailExtendedVirtual", ct.c_ulonglong)]
        ms = _MS()
        ms.dwLength = ct.sizeof(_MS)
        if not k.GlobalMemoryStatusEx(ct.byref(ms)):
            raise OSError("GlobalMemoryStatusEx failed (%d)" % ct.get_last_error())
        out.update(mem_total=float(ms.ullTotalPhys), mem_avail=float(ms.ullAvailPhys), mem_load=int(ms.dwMemoryLoad),
                   commit=float(ms.ullTotalPageFile - ms.ullAvailPageFile), commit_limit=float(ms.ullTotalPageFile))
    except Exception as e:                                      # noqa: BLE001
        out["errs"].append("memory: %s" % str(e)[:80])
    try:
        out["uptime_s"] = k.GetTickCount64() / 1000.0
    except Exception as e:                                      # noqa: BLE001
        out["errs"].append("uptime: %s" % str(e)[:80])

    def sys_times():
        i, kk, u = wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
        if not k.GetSystemTimes(ct.byref(i), ct.byref(kk), ct.byref(u)):
            raise OSError("GetSystemTimes failed (%d)" % ct.get_last_error())
        return _ft(i), _ft(kk) + _ft(u)                         # kernel time includes the idle time

    def proc_times(hs):
        tot = {}
        for pid, h in hs.items():
            c, e, kk, u = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
            if k.GetProcessTimes(h, ct.byref(c), ct.byref(e), ct.byref(kk), ct.byref(u)):
                tot[pid] = _ft(kk) + _ft(u)
        return tot
    hs = {}
    try:
        try:
            hs = _python_handles(k, ct, wt)
        except Exception as e:                                  # noqa: BLE001
            out["errs"].append("process list: %s" % str(e)[:80])
        idle0, all0 = sys_times()
        p0 = proc_times(hs)
        time.sleep(max(0.05, float(sample_s)))
        idle1, all1 = sys_times()
        p1 = proc_times(hs)
        d_all = all1 - all0
        if d_all > 0:
            out["cpu"] = max(0.0, min(100.0, 100.0 * (d_all - (idle1 - idle0)) / d_all))
            if hs:
                out["py_cpu"] = max(0.0, min(100.0, 100.0 * sum(p1[p] - p0[p] for p in p1 if p in p0) / d_all))
        if hs:
            class _PMC(ct.Structure):
                _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ct.c_size_t),
                            ("WorkingSetSize", ct.c_size_t), ("QuotaPeakPagedPoolUsage", ct.c_size_t),
                            ("QuotaPagedPoolUsage", ct.c_size_t), ("QuotaPeakNonPagedPoolUsage", ct.c_size_t),
                            ("QuotaNonPagedPoolUsage", ct.c_size_t), ("PagefileUsage", ct.c_size_t),
                            ("PeakPagefileUsage", ct.c_size_t)]
            mem, seen = 0, 0
            for h in hs.values():
                pm = _PMC()
                pm.cb = ct.sizeof(_PMC)
                if k.K32GetProcessMemoryInfo(h, ct.byref(pm), pm.cb):
                    mem += pm.WorkingSetSize
                    seen += 1
            out["py_n"] = len(hs)
            out["py_mem"] = float(mem) if seen else None
        elif not out["errs"]:
            out["py_n"] = 0
    except Exception as e:                                      # noqa: BLE001
        out["errs"].append("CPU: %s" % str(e)[:80])
    finally:
        for h in hs.values():
            try:
                k.CloseHandle(h)
            except Exception:                                   # noqa: BLE001
                pass
    return out


# ---- /server: the time to Kalshi -----------------------------------------------------------------------------------
_PING = {}


def kalshi_connect(host=KALSHI_HOST, port=443, tries=KALSHI_PING_TRIES, timeout=2.0):
    """A bare TCP connect to Kalshi's API, `tries` times: the handshake only (no TLS, no request), so it costs no
    Kalshi rate limit. {"ms": [each connect], "ip", "dns_ms", "err", "t"}."""
    import socket
    out = {"host": host, "ms": [], "ip": None, "dns_ms": None, "err": None, "t": time.time()}
    try:
        t0 = time.perf_counter()
        ai = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        out["dns_ms"] = (time.perf_counter() - t0) * 1000.0
        addr = ai[0][4]
        out["ip"] = addr[0]
    except Exception as e:                                      # noqa: BLE001
        out["err"] = "name lookup failed (%s)" % (str(e)[:60] or type(e).__name__)
        return out
    for _ in range(tries):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            t0 = time.perf_counter()
            s.connect(addr)
            out["ms"].append((time.perf_counter() - t0) * 1000.0)
        except Exception as e:                                  # noqa: BLE001
            out["err"] = "connect failed (%s)" % (str(e)[:60] or type(e).__name__)
        finally:
            s.close()
    return out


def kalshi_ping(max_age_s=KALSHI_PING_TTL_S):
    """kalshi_connect, at most once every `max_age_s` seconds (the last answer in between)."""
    hit = _PING.get("res")
    if hit and time.time() - hit["t"] < max_age_s:
        return hit
    _PING["res"] = kalshi_connect()
    return _PING["res"]
