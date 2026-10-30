"""Golden capture: render every golden case ONCE against the real results/ (read-only), learn which files they touch,
and copy only those into a fixture folder OUTSIDE the repo. Run on the server (where the live phone's data is);
never imported by production code.

    C:\\Python314\\python.exe C:\\kals\\golden\\tools\\capture.py --code C:\\kals-repo\\research --root C:\\kals\\golden

SAFETY (the server runs live money bots):
  * runs at below-normal priority; refuses to start with under --min-free-mb (800) of free memory
  * the fence is installed BEFORE the code under test is imported: any write outside --root raises (pinphone.log,
    the heartbeat, botstats_cache.json, pinphone.update stay untouched); no process can be started or signalled;
    no network except the recorder below
  * Kalshi: the phone's own read-only getter (kauth.get, GET only by construction) is wrapped; each distinct request
    is asked ONCE and its answer kept (kalshi.json). botstats' part is served from a COPY of botstats_cache.json
    whose read stamps are moved to the capture clock (so botstats does not re-read Kalshi). --no-kalshi: no Kalshi
    at all (the laptop: every request is answered 599 and recorded as missing)
  * pindesk.do_start / do_pause / do_stop are stubs; telegram.json is never read (a fake one goes in the fixture);
    *.pem / key / secret files are never copied
Output: <root>/fixtures/<stamp>/ = results/ (copied files, mtimes kept; big logs read only near their end copied as
that tail), repo/boot_all.ps1, research/<data files read>, kals/telegram.json (fake), manifest.json, env.json,
health.json, procs.json, kalshi.json, trace.json, capture.json.
"""
import argparse
import json
import ntpath
import os
import re
import shutil
import sys
import time
import types

sys.dont_write_bytecode = True
GOLDEN = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, GOLDEN)
import gl_common as C          # noqa: E402
import gl_fence                # noqa: E402
import gl_worlds               # noqa: E402

SECRET_RX = re.compile(r"(\.pem$|\.key$|secret|token|telegram\.json$|server\.json$|password|credential|"
                       r"[\\/]\.ssh[\\/]|_key\.json$|kalshi_key|\.env$)", re.I)
SMALL = 64 * 1024                # a file only stat'ed / listed is copied whole up to this size, else a 0-byte stand-in
MAX_LISTED = 5000                # a listed folder with more entries than this gets no stand-ins


# ======================================================================================================== machine
def set_below_normal():
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)      # BELOW_NORMAL_PRIORITY_CLASS
        return True
    except Exception:                                           # noqa: BLE001
        return False


def free_mb():
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullAvailPhys / 2 ** 20
    except Exception:                                           # noqa: BLE001
        return None


def peak_mb():
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                               "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                               "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        k = ctypes.WinDLL("kernel32")
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.K32GetProcessMemoryInfo.argtypes = (ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD)
        k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return int(c.PeakWorkingSetSize / 2 ** 20)
    except Exception:                                           # noqa: BLE001
        return None


def native_procs():
    """[[pid, started_utc, command line]] for EVERY python.exe (Toolhelp + NtQueryInformationProcess, the right to
    look only: PROCESS_QUERY_LIMITED_INFORMATION). Unreadable ones are skipped and counted."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    nt = ctypes.WinDLL("ntdll")

    class PE(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("pid", wintypes.DWORD),
                    ("heap", ctypes.c_size_t), ("mod", wintypes.DWORD), ("threads", wintypes.DWORD),
                    ("ppid", wintypes.DWORD), ("prio", ctypes.c_long), ("flags", wintypes.DWORD),
                    ("exe", ctypes.c_wchar * 260)]

    class US(ctypes.Structure):
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
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
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
        h = k32.OpenProcess(0x1000, False, pid)
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
                started = time.strftime("%Y-%m-%dT%H:%M:%SZ", gl_fence.ORIG.get("time.gmtime", time.gmtime)(
                    (ft[0].value - 116444736000000000) / 1e7))
        finally:
            k32.CloseHandle(h)
        rows.append([pid, started, " ".join(cl.split())])
    rows.sort()
    return rows, unread


def git_head(repo):
    try:
        with open(os.path.join(repo, ".git", "HEAD"), encoding="utf-8") as fh:
            h = fh.read().strip()
        if not h.startswith("ref:"):
            return h
        ref = h.split(None, 1)[1]
        p = os.path.join(repo, ".git", *ref.split("/"))
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                return fh.read().strip()
        with open(os.path.join(repo, ".git", "packed-refs"), encoding="utf-8") as fh:
            for line in fh:
                if line.strip().endswith(ref):
                    return line.split()[0]
    except OSError:
        pass
    return None


# ======================================================================================================== copying
def _under(p, d):
    p, d = ntpath.normcase(p), ntpath.normcase(d).rstrip("\\")
    return p == d or p.startswith(d + "\\")


def copy_file(src, dst, mode, tail_from=0):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    st = os.stat(src)
    if mode == "placeholder":
        with open(dst, "wb"):
            pass
    elif mode == "tail":
        with open(src, "rb") as a, open(dst, "wb") as b:
            a.seek(tail_from)
            shutil.copyfileobj(a, b, 1 << 20)
    else:
        with open(src, "rb") as a, open(dst, "wb") as b:
            shutil.copyfileobj(a, b, 1 << 20)
    os.utime(dst, (st.st_mtime, st.st_mtime))
    return st


OLD_PAPER = re.compile(r"^pinrun-paper-.*\.jsonl$", re.I)


def plan_and_copy(touched, extra, repo, code, fx, max_full, margin, log, skip=(), old_before=None):
    """touched: real path -> {ops, lo, hi}. Returns the manifest. `skip`: paths written separately (the cache)."""
    man = {}
    skip = {ntpath.normcase(p) for p in skip}
    res = os.path.join(repo, "results")
    listed = []

    def dest_of(p):
        if SECRET_RX.search(p):
            return None, "secret: never copied"
        if _under(p, res):
            return os.path.join(fx, "results", os.path.relpath(p, res)), None
        if _under(p, code):
            if "__pycache__" in p or "\\golden\\" in ntpath.normcase(p):
                return None, "code"
            return os.path.join(fx, "research", os.path.relpath(p, code)), None
        if _under(p, repo):
            if "\\.git" in ntpath.normcase(p):
                return None, "git"
            return os.path.join(fx, "repo", os.path.relpath(p, repo)), None
        return None, "outside the repo (C:\\kals: health / machine are recorded instead)"

    def one(p, info, why):
        if ntpath.normcase(p) in skip:
            return
        dst, skip_why = dest_of(p)
        rel_key = os.path.relpath(dst, fx).replace("\\", "/") if dst else p
        if dst is None:
            man.setdefault("_skipped", {})[p] = skip_why
            return
        if rel_key in man:
            return
        if not os.path.exists(p):
            man[rel_key] = {"src": p, "mode": "absent", "ops": sorted(info.get("ops", ()))}
            return
        if os.path.isdir(p):
            if "list" in info.get("ops", ()):
                listed.append(p)
            return
        size = os.path.getsize(p)
        lo = info.get("lo")
        if (old_before is not None and OLD_PAPER.match(os.path.basename(p)) and size > SMALL
                and os.path.getmtime(p) < old_before):
            # 704 MB of paper-arm logs on the server, read whole only by /brief and /bars: the old ones are 0-byte
            # stand-ins (mtime kept), so those two pages see only the recent arms
            mode, tf = "placeholder", 0
        elif lo is not None and (lo == 0 or size <= max_full):
            mode, tf = "full", 0
        elif lo is not None:
            mode, tf = "tail", max(0, lo - margin)
        elif why == "extra":
            mode, tf = ("full", 0) if size <= max_full else ("tail", max(0, size - 64 * 2 ** 20))
        elif size <= SMALL:
            mode, tf = "full", 0
        else:
            mode, tf = "placeholder", 0
        st = copy_file(p, dst, mode, tf)
        man[rel_key] = {"src": p, "mode": mode, "mtime": st.st_mtime, "size": st.st_size, "tail_from": tf,
                        "lo": lo, "ops": sorted(info.get("ops", ())), "why": why}

    for p in sorted(touched):
        one(p, touched[p], "touched")
    for name in extra:
        p = os.path.join(res, name)
        one(p, touched.get(p) or {"ops": {"extra"}}, "extra")
    for d in sorted(set(listed)):
        try:
            names = os.listdir(d)
        except OSError:
            continue
        if len(names) > MAX_LISTED:
            man.setdefault("_listing_skipped", []).append(d)
            continue
        for n in names:
            p = os.path.join(d, n)
            if os.path.isfile(p):
                one(p, {"ops": {"listed"}}, "listed")
    log("copied: %d full, %d tail, %d stand-ins, %d absent" % tuple(
        sum(1 for k, v in man.items() if not k.startswith("_") and v["mode"] == m)
        for m in ("full", "tail", "placeholder", "absent")))
    return man


# ======================================================================================================== main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--code", default=os.path.dirname(GOLDEN) if os.path.basename(GOLDEN) == "golden"
                    else r"C:\kals-repo\research")
    ap.add_argument("--root", default=r"C:\kals\golden", help="everything is written under here, nothing else")
    ap.add_argument("--stamp", default=None)
    ap.add_argument("--no-kalshi", action="store_true", help="no Kalshi request at all (the laptop)")
    ap.add_argument("--extra-names", default=None, help="JSON list of results/ file names to copy as well")
    ap.add_argument("--only", default=None, help="regex over case ids (testing the capture itself)")
    ap.add_argument("--max-full-mb", type=float, default=32.0)
    ap.add_argument("--tail-margin-mb", type=float, default=4.0)
    ap.add_argument("--min-free-mb", type=float, default=800.0)
    ap.add_argument("--old-paper-days", type=float, default=7.0,
                    help="pinrun-paper-*.jsonl older than this become 0-byte stand-ins (only /brief, /bars read them)")
    a = ap.parse_args()

    t_start = time.time()
    below = set_below_normal()
    fm = free_mb()
    print("capture: below-normal priority %s; free memory %s MB" % (below, None if fm is None else int(fm)), flush=True)
    if fm is not None and fm < a.min_free_mb:
        print("capture: ABORT -- under %d MB free" % a.min_free_mb, flush=True)
        return 4
    code = os.path.abspath(a.code)
    repo = os.path.dirname(code)
    root = os.path.abspath(a.root)
    T = time.time()
    stamp = a.stamp or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(T))
    fx = os.path.join(root, "fixtures", stamp)
    if os.path.exists(fx):
        print("capture: %s exists" % fx)
        return 2
    for d in (fx, os.path.join(root, "mpl"), os.path.join(root, "tmp"), os.path.join(fx, "kals")):
        os.makedirs(d, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = os.path.join(root, "mpl")
    os.environ["MPLBACKEND"] = "Agg"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["TMP"] = os.environ["TEMP"] = os.path.join(root, "tmp")
    import tempfile
    tempfile.tempdir = os.path.join(root, "tmp")
    sha = git_head(repo)
    logf = open(os.path.join(fx, "capture.log"), "w", encoding="utf-8")

    def log(s):
        line = "%s  %s" % (time.strftime("%H:%M:%S", gl_fence.ORIG.get("time.gmtime", time.gmtime)(
            gl_fence.real_time())), s)
        logf.write(line + "\n")
        logf.flush()
        print(line, flush=True)
    log("code %s at %s; fixture %s; T=%s" % (code, sha, fx, T))

    # ---- the cache, re-stamped to the capture clock, read once, before the fence ----
    real_cache = os.path.join(repo, "results", "botstats_cache.json")
    fx_cache = os.path.join(fx, "results", "botstats_cache.json")
    os.makedirs(os.path.dirname(fx_cache), exist_ok=True)
    with open(real_cache, "rb") as fh:
        raw = fh.read()
    cst = os.stat(real_cache)
    cache = json.loads(raw.decode("utf-8"))
    newest = gl_worlds.newest_read(cache)
    delta = (T - 5.0 - newest) if newest else 0.0
    gl_worlds.shift_cache_dict(cache, delta)
    with open(fx_cache, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, separators=(",", ":"))
    os.utime(fx_cache, (cst.st_mtime, cst.st_mtime))
    log("botstats cache: newest read %.0f s before the capture clock; re-stamped by %+.0f s" % (T - (newest or T), delta))

    # ---- the fence ----
    sink = os.path.join(root, "tmp", "writes")
    os.makedirs(sink, exist_ok=True)
    wmaps = [(os.path.join(repo, "results", n), os.path.join(sink, n)) for n in ("pinphone.log", "pinphone.heartbeat")]
    fence = gl_fence.Fence("trace", maps=[(real_cache, fx_cache)] + wmaps, allow_write=[root],
                           trace_roots=[repo, r"C:\kals"], trace_skip=[root])
    gl_fence.install(fence)
    clock = gl_fence.Clock(T)
    gl_fence.install_clock(clock)
    import gl_cases                                             # noqa: E402
    if a.no_kalshi:
        rec = gl_cases.KalshiStore({}, "record")
        sys.modules["kauth"] = gl_cases.fake_kauth(rec)
        rec.calls = {}
        rec.real_requests = 0
    else:
        sys.path.insert(0, code)
        import kauth                                            # noqa: E402  (reads the key: never copied)
        kauth.time = types.SimpleNamespace(time=gl_fence.real_time)    # signatures need the real clock
        rec = gl_cases.KalshiRecorder(kauth.get, fence)
        kauth.get = rec.get
    if code not in sys.path:
        sys.path.insert(0, code)
    mods = {}
    for name in ("pindesk", "botstats", "pinphone", "tgcharts"):
        mods[name] = __import__(name)
    pp, pd = mods["pinphone"], mods["pindesk"]

    # ---- the machine, recorded once ----
    L = pd.Ledger()
    L.refresh()
    try:
        health = pd.health(L)
    except Exception:                                           # noqa: BLE001
        import traceback
        log("ABORT: pindesk.health failed under the fence: " + traceback.format_exc())
        return 6
    procs, unread = native_procs()
    machine = pp.machine_read()
    if a.no_kalshi:
        ping = pp.kalshi_ping()                                 # refused by the fence: the failure shape
    else:
        with fence.allow_net():
            ping = pp.kalshi_ping()
    du = shutil.disk_usage("C:\\")
    import matplotlib
    env = {"T": T, "T_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", gl_fence.ORIG["time.gmtime"](T)), "machine": machine,
           "ping": ping, "disk_usage": [du.total, du.used, du.free], "code_sha": sha, "code": code,
           "python": sys.version.split()[0], "matplotlib": matplotlib.__version__, "cache_delta_s": delta,
           "procs_unread": unread, "no_kalshi": bool(a.no_kalshi), "host": os.environ.get("COMPUTERNAME")}
    env["_code"] = code
    log("recorded: health (%d keys), %d python processes (%d unreadable), machine, ping" % (len(health), len(procs),
                                                                                             unread))

    # ---- every case once, traced ----
    rt = gl_cases.Runtime(fence, clock, env, health, procs, rec, "capture", None, C.Normaliser([]),
                          cfg_path=os.path.join(root, "tmp", "telegram.json"))
    rt.mods = mods
    gl_cases.apply_seams(rt)
    gl_cases.snapshot_caches(rt)
    rt.ledger = L
    cases = gl_cases.case_list(rt)
    if a.only:
        cases = [c for c in cases if re.search(a.only, c[0])]
    summary = {}
    for case in cases:
        fm = free_mb()
        if fm is not None and fm < a.min_free_mb * 0.75:
            log("ABORT: free memory fell to %d MB" % fm)
            return 5
        res, secs, trace = gl_cases.run_case(rt, case)
        summary[case[0]] = {"status": res["status"], "s": round(secs, 2), "kalshi": len(res["kalshi_asked"]),
                            "fence": [e for e in res["fence"] if e["kind"] != "control_stubbed"][:20],
                            "fail_why": res.get("fail_why")}
        log("%-4s %6.2fs kalshi %3d %s%s" % (res["status"], secs, len(res["kalshi_asked"]), case[0],
                                             (" " + str(res.get("fail_why"))) if res.get("fail_why") else ""))
        if trace:
            log(trace)
    touched = {k: dict(v, ops=set(v["ops"])) for k, v in fence.touched.items()}
    log("touched %d paths; Kalshi: %d distinct requests, %d asked of Kalshi itself" % (
        len(touched), len(rec.calls), getattr(rec, "real_requests", 0)))

    # ---- copy what was touched ----
    extra = []
    if a.extra_names:
        with open(a.extra_names, encoding="utf-8") as fh:
            extra = json.load(fh)
    man = plan_and_copy(touched, extra, repo, code, fx, int(a.max_full_mb * 2 ** 20), int(a.tail_margin_mb * 2 ** 20),
                        log, skip=[real_cache], old_before=T - a.old_paper_days * 86400)
    # THE REPLAY CLOCK = the moment the copy finished, so nothing in the fixture is newer than the clock (the trace
    # ran at T, a few minutes earlier); the fixture's cache is re-stamped once more to read as fresh at that clock.
    T_end = gl_fence.real_time()
    gl_worlds.shift_cache(fx_cache, T_end - T)
    delta += T_end - T
    env["T_trace"], env["T"] = T, T_end
    env["T_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", gl_fence.ORIG["time.gmtime"](T_end))
    env["cache_delta_s"] = delta
    man["results/botstats_cache.json"] = {"src": real_cache, "mode": "restamped", "mtime": cst.st_mtime,
                                          "size": cst.st_size, "delta_s": delta}
    with open(os.path.join(fx, "kals", "telegram.json"), "w", encoding="utf-8") as fh:
        json.dump(C.FAKE_TELEGRAM_JSON, fh, indent=2)
    C.dump_json(os.path.join(fx, "manifest.json"), man, codec=False)
    C.dump_json(os.path.join(fx, "env.json"), {k: v for k, v in env.items() if k != "_code"})
    C.dump_json(os.path.join(fx, "health.json"), health)
    C.dump_json(os.path.join(fx, "procs.json"), procs)
    C.dump_json(os.path.join(fx, "kalshi.json"), {k: {"status": s, "body": b} for k, (s, b) in sorted(rec.calls.items())})
    C.dump_json(os.path.join(fx, "trace.json"), {k: {"ops": sorted(v["ops"]), "lo": v["lo"], "hi": v["hi"],
                                                     "cases": sorted(v.get("cases") or ())}
                                                 for k, v in sorted(touched.items())}, codec=False)
    C.dump_json(os.path.join(fx, "capture.json"), {"cases": summary, "seconds": round(time.time() - t_start, 1),
                                                   "stamp": stamp, "code_sha": sha}, codec=False)
    total = 0
    for r, _d, files in os.walk(fx):
        total += sum(os.path.getsize(os.path.join(r, f)) for f in files)
    log("done in %.0f s; fixture %.1f MB at %s; peak memory %s MB" % (gl_fence.real_time() - t_start, total / 2 ** 20,
                                                                         fx, peak_mb()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
