"""phone/actions/launch.py -- start ONE PowerShell script detached through WMI, and read its log back.

v-tg-step12 (2026-10-30, lane R). The ONLY phone code that starts a process for an action (the /update worker keeps its
own self-test run). Why WMI: a process the phone started directly would be the phone's child; Win32_Process.Create
starts it under WMI's provider host instead, so it outlives the phone and any ssh session (measured 2026-10-27, see
pindesk's --action notes; results\\jb_deploy.ps1 and pin_size15_nohedgejump.ps1 start their bots the same way).

What runs is always  powershell -NoProfile -ExecutionPolicy Bypass -File "<a .ps1 inside RESULTS>" <fixed args>  --
the caller (a registry Start recipe, or an approvals.json entry) names the script; nothing typed in the chat reaches a
command line. ps_file_cmdline refuses a path outside the allowed roots, a non-.ps1 file and any argument with a quote,
a semicolon, a pipe, a redirect or an ampersand.

SEAMS for the tests: SPAWN(cmdline, cwd) -> (pid or None, error or None) and WAIT(pid, timeout_s) -> exit code / None.
Under KALS_TESTING=1 the real ones refuse (a test never starts a process); the tests plant stubs.
"""
import os
import re
import subprocess
import time

from botdata import paths as _paths

POWERSHELL = "powershell.exe"
CREATE_NO_WINDOW = 0x08000000
SPAWN_TIMEOUT_S = 60
_BAD_ARG = re.compile(r"""["'`;|&<>$\r\n]""")


def roots():
    """Folders a launched script may live in: the results folder (botdata.paths.RESULTS at call time)."""
    return (os.path.normcase(os.path.realpath(_paths.RESULTS)),)


def inside_roots(path):
    p = os.path.normcase(os.path.realpath(path))
    return any(p.startswith(r.rstrip("\\/") + os.sep) for r in roots())


def resolve_script(name):
    """The full path of a .ps1 named relative to RESULTS, after checking it stays inside the allowed roots and exists.
    Raises ValueError with the reason in words."""
    if not name or os.path.isabs(str(name)) or ".." in str(name).replace("\\", "/").split("/"):
        raise ValueError("the script must be named relative to the results folder, with no '..': %r" % (name,))
    full = os.path.join(_paths.RESULTS, str(name))
    if not full.lower().endswith(".ps1"):
        raise ValueError("only a .ps1 script can be run: %s" % name)
    if not inside_roots(full):
        raise ValueError("the script is not inside the results folder: %s" % name)
    if not os.path.isfile(full):
        raise ValueError("the script is not there: %s" % full)
    return full


def psq(s):
    """A PowerShell single-quoted literal.  (pindesk.psq)"""
    return "'" + str(s).replace("'", "''") + "'"


def ps_file_cmdline(path, args=()):
    """The command line WMI runs: powershell -NoProfile -ExecutionPolicy Bypass -File "<path>" <args>."""
    if not inside_roots(path) or not str(path).lower().endswith(".ps1"):
        raise ValueError("refusing a script outside the results folder: %s" % path)
    for a in args:
        if not isinstance(a, str) or not a or _BAD_ARG.search(a) or " " in a:
            raise ValueError("refusing an argument: %r" % (a,))
    return " ".join(['%s -NoProfile -ExecutionPolicy Bypass -File "%s"' % (POWERSHELL, path)] + list(args))


def wmi_create(cmdline, cwd):
    """Win32_Process.Create(cmdline, cwd) through PowerShell's Invoke-CimMethod: (pid, None) or (None, why)."""
    if _paths.testing():
        return None, "refused: KALS_TESTING=1 (a test never starts a process)"
    script = ("$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
              "@{CommandLine = %s; CurrentDirectory = %s}; Write-Output ('WMI {0} {1}' -f $r.ReturnValue, $r.ProcessId)"
              % (psq(cmdline), psq(cwd)))
    try:
        r = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True,
                           text=True, timeout=SPAWN_TIMEOUT_S, creationflags=CREATE_NO_WINDOW)
    except Exception as e:                                      # noqa: BLE001
        return None, "could not run PowerShell: %s" % str(e)[:200]
    m = re.search(r"WMI (\d+) (\d*)", r.stdout or "")
    if not m:
        return None, "WMI gave no answer: %s" % ((r.stdout or "") + (r.stderr or "")).strip()[:200]
    if m.group(1) != "0" or not m.group(2):
        return None, "WMI refused (return %s)" % m.group(1)
    return int(m.group(2)), None


def wait_exit(pid, timeout_s, poll_s=5.0):
    """Wait up to timeout_s for process `pid` to end: its exit code, -1 when it ended but the code is unknown, None
    when it still runs. Windows only (ctypes); a handle opened with SYNCHRONIZE + QUERY_LIMITED_INFORMATION only."""
    import ctypes
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x00100000 | 0x1000, False, int(pid))
    if not h:
        return -1                                               # gone already (or not ours to see)
    try:
        t_end = time.monotonic() + float(timeout_s)
        while True:
            if k32.WaitForSingleObject(h, 0) == 0:
                code = ctypes.c_ulong()
                return int(code.value) if k32.GetExitCodeProcess(h, ctypes.byref(code)) else -1
            if time.monotonic() >= t_end:
                return None
            time.sleep(poll_s)
    finally:
        k32.CloseHandle(h)


SPAWN = wmi_create
WAIT = wait_exit


def run_script(path, args=(), cwd=None):
    """Start the script detached: (pid, None) or (None, why). cwd defaults to the repo folder."""
    try:
        cl = ps_file_cmdline(path, args)
    except ValueError as e:
        return None, str(e)
    return SPAWN(cl, cwd or _paths.REPO)


def tail(path, n=12, max_bytes=65536):
    """The last n non-empty lines of a text log (utf-8, a BOM or odd bytes tolerated); [] when unreadable."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - max_bytes))
            raw = fh.read()
    except OSError:
        return []
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        txt = raw.decode("utf-16", errors="replace")
    else:
        txt = raw.decode("utf-8", errors="replace").lstrip("﻿")
    lines = [x.rstrip() for x in txt.splitlines() if x.strip()]
    return lines[-n:]
