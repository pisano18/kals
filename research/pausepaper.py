#!/usr/bin/env python3
"""pausepaper.py -- freeze the PAPER-only bots to hand their RAM to the operator, and unfreeze them later.

Operator 2026-09-29: "I'm going to be 3d modeling for about an hour. Is there anything we can cut off or pause so I
can get some ram back."

--pause   suspends every paper-only python process (NtSuspendProcess) and empties its working set (EmptyWorkingSet),
          so Windows moves its memory to the page file; the pids go to results/pausepaper.json.
--resume  resumes the pids in results/pausepaper.json (they reconnect their feeds on their own).
--list    shows what would be paused and how much memory each holds; changes nothing.

NEVER paused (the selector refuses them by rule, and the self-test proves it on real command lines): anything with
--live, the recorders (kalshi_collector, crypto_feeds, cdc_record), ladder_live, forecaster_live, and the watchers
(kalshiwatch, pinphone, pinledgerd, quakewatch, watch_bot).
"""
import argparse
import ctypes
import json
import os
import subprocess
import sys
import time

STATE = r"C:\kals-repo\results\pausepaper.json"
PAPER = ("pinrun.py", "polypaper.py", "pinracearm.py", "bettor_paper.py", "locked_average_ladder_re_paper.py",
         "fc_variants_paper.py")
NEVER = ("--live", "kalshi_collector", "crypto_feeds", "cdc_record", "ladder_live", "forecaster_live", "bettor_live",
         "kalshiwatch", "pinphone", "pinledgerd", "quakewatch", "watch_bot", "restart_bot")


def is_paper(cmd):
    c = (cmd or "").replace("\\", "/")
    if any(n in c for n in NEVER):
        return False
    if "pinracearm.py" in c and "--paper-live" not in c:
        return False
    return "research/" in c and any(p in c for p in PAPER)


def procs():
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                          "Select-Object ProcessId, WorkingSetSize, CommandLine | ConvertTo-Json -Compress"],
                         capture_output=True, text=True).stdout
    rows = json.loads(out or "[]")
    return [rows] if isinstance(rows, dict) else rows


def _call(pid, what):
    k32, nt, ps = ctypes.windll.kernel32, ctypes.windll.ntdll, ctypes.windll.psapi
    h = k32.OpenProcess(0x0800 | 0x0400 | 0x0100, False, int(pid))   # SUSPEND_RESUME | QUERY_INFORMATION | SET_QUOTA
    if not h:
        return "open failed"
    try:
        if what == "pause":
            st = nt.NtSuspendProcess(h)
            ps.EmptyWorkingSet(h)
        else:
            st = nt.NtResumeProcess(h)
        return "ok" if st == 0 else "status %d" % st
    finally:
        k32.CloseHandle(h)


def free_gb():
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_uint32), ("dwMemoryLoad", ctypes.c_uint32), ("ullTotalPhys", ctypes.c_uint64),
                    ("ullAvailPhys", ctypes.c_uint64), ("ullTotalPageFile", ctypes.c_uint64),
                    ("ullAvailPageFile", ctypes.c_uint64), ("ullTotalVirtual", ctypes.c_uint64),
                    ("ullAvailVirtual", ctypes.c_uint64), ("ullAvailExtendedVirtual", ctypes.c_uint64)]
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return round(m.ullAvailPhys / 2 ** 30, 2)


def selftest():
    must_pause = [r'"C:\Python314\python.exe" -u C:\kals-repo\research\pinrun.py --size 20 --minutes 10080 --loss-abort 60',
                  r'"C:\Python314\python.exe" -u research\polypaper.py --minutes 4320',
                  r'C:\Python314\python.exe -u research/pinracearm.py --paper-live --minutes 10080 --size 1',
                  r'"C:\Python314\python.exe" research\cleanroom\bettor_paper.py --minutes 10080',
                  r'"C:\Python314\python.exe" research\cleanroom\locked_average_ladder_re_paper.py --minutes 10080',
                  r'"C:\Python314\python.exe" -u research\cleanroom\fc_variants_paper.py --minutes 10080']
    never = [r'"C:\Python314\python.exe" -u C:\kals-repo\research\pinrun.py --live --size 20 --minutes 4320',
             r'"C:\Python314\python.exe" -u research/pinracearm.py --live --max-contracts 20 --max-stake 60',
             r'"C:\Python314\python.exe" kalshi_collector.py --key-id x',
             r'"C:\Python314\python.exe" crypto_feeds.py --out ./feed_data',
             r'"C:\Python314\python.exe" -u C:\kals\cdc_record.py --seconds 2',
             r'"C:\Python314\python.exe" -u research\cleanroom\ladder_live.py --subaccount 1 --live',
             r'"C:\Python314\python.exe" -u research\cleanroom\forecaster_live.py --subaccount 2 --live',
             r'"C:\Python314\python.exe" -u C:\kals-repo\research\kalshiwatch.py --loop',
             r'"C:\Python314\python.exe" -u C:\kals-repo\research\pinphone.py',
             r'C:\Python314\python.exe -u research/pinledgerd.py',
             r'"C:\Python314\python.exe" -u C:\kals-repo\research\quakewatch.py',
             r'C:\Python314\python.exe -u research/pinracearm.py --minutes 100', None, ""]
    bad = [c for c in must_pause if not is_paper(c)] + [c for c in never if is_paper(c)]
    print("pausepaper self-test " + ("PASSED" if not bad else "FAILED: %s" % bad))
    return not bad


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pause", action="store_true")
    g.add_argument("--resume", action="store_true")
    g.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if not selftest():
        raise SystemExit(1)
    if a.resume:
        st = json.load(open(STATE, encoding="utf-8"))
        for pid in st["pids"]:
            print(pid, _call(pid, "resume"))
        os.replace(STATE, STATE + ".resumed")
        print("resumed %d; free RAM now %.2f GB" % (len(st["pids"]), free_gb()))
        return 0
    rows = [r for r in procs() if is_paper(r.get("CommandLine"))]
    mb = sum(r["WorkingSetSize"] for r in rows) / 2 ** 20
    for r in rows:
        print("%8d %5.0f MB  %s" % (r["ProcessId"], r["WorkingSetSize"] / 2 ** 20, (r["CommandLine"] or "")[:110]))
    print("%d paper processes, %.0f MB; free RAM %.2f GB" % (len(rows), mb, free_gb()))
    if a.list:
        return 0
    if os.path.exists(STATE):
        raise SystemExit("already paused (results/pausepaper.json exists) -- run --resume first")
    before = free_gb()
    done = [r["ProcessId"] for r in rows if _call(r["ProcessId"], "pause") == "ok"]
    json.dump({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pids": done}, open(STATE, "w", encoding="utf-8"))
    time.sleep(2)
    print("paused %d of %d; free RAM %.2f -> %.2f GB" % (len(done), len(rows), before, free_gb()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
