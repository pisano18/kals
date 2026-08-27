"""whatate.py -- WHAT ATE MY DISK?

Read-only. This program does not delete, move, or modify anything. It measures
and prints. Two checks (shadow-copy storage, other users' profiles) report
"needs admin" rather than a size when run without elevation.

WHY IT EXISTS
    Free space on the machine running the collector swung 71.5 -> 36.5 -> 44.7
    GB in five hours while the recorded data grew only ~100 MB/h. Something
    else took ~35 GB and later handed ~8 GB back. The watchdog halts the
    collector below 5 GB, so this is worth measuring rather than guessing at.

WHY IT REPORTS DENIALS INSTEAD OF ZEROES
    The obvious way to size a folder is to sum what you can read and ignore
    the rest. That is exactly how a 40 GB folder hides: every entry under it
    denied, sum zero, printed as "0.00 GB", and the one place worth looking is
    the one place the report says is empty. Every unreadable directory is
    counted and shown.

USAGE
    python research/whatate.py                 # targeted checks, seconds
    python research/whatate.py --deep          # whole-drive passes, minutes
    python research/whatate.py --selftest
"""

import argparse
import os
import shutil
import subprocess
import sys
import time

WIN = os.name == "nt"
GB = 1024.0 ** 3
MB = 1024.0 ** 2


# ===========================================================================
def du(path, follow=False):
    """(bytes, files, denied_dirs) under `path`, or None if it does not exist.

    Iterative, not recursive: a deep tree (node_modules, a game's asset dirs)
    is a real thing on these machines and Python's recursion limit is 1000.
    Hard links and junctions are not followed, so a folder is never counted
    twice and C:\\Users\\All Users does not send this around a loop.
    """
    if not os.path.exists(path):
        return None
    total = files = denied = 0
    seen = set()
    stack = [path]
    while stack:
        d = stack.pop()
        try:
            st = os.stat(d, follow_symlinks=False)
            key = (st.st_dev, st.st_ino)
            if key in seen:
                continue
            seen.add(key)
        except OSError:
            denied += 1
            continue
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=follow):
                            stack.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            total += e.stat(follow_symlinks=False).st_size
                            files += 1
                    except OSError:
                        denied += 1
        except OSError:
            denied += 1
    return total, files, denied


def fsize(path):
    """Size of one file, or None. Uses stat rather than getsize so a locked
    file (pagefile.sys is always locked) still reports its length."""
    try:
        return os.stat(path, follow_symlinks=False).st_size
    except OSError:
        return None


def fmt(n):
    return "     absent" if n is None else f"{n / GB:9.2f} GB"


def row(label, val, note=""):
    if isinstance(val, tuple):
        b, files, denied = val
        s = f"{b / GB:9.2f} GB"
        if denied:
            s += f"  (+{denied} unreadable)"
        elif files == 0:
            s += "  (empty)"
    else:
        s = fmt(val)
    print(f"  {label:<44}{s}  {note}".rstrip())


def mtime(path):
    try:
        return time.strftime("%Y-%m-%d %H:%M",
                             time.localtime(os.stat(path).st_mtime))
    except OSError:
        return ""


# ===========================================================================
def steam_roots():
    roots = []
    if WIN:
        try:
            import winreg
            for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                              (winreg.HKEY_LOCAL_MACHINE,
                               r"SOFTWARE\WOW6432Node\Valve\Steam")):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        for name in ("SteamPath", "InstallPath"):
                            try:
                                roots.append(winreg.QueryValueEx(k, name)[0]
                                             .replace("/", "\\"))
                            except OSError:
                                pass
                except OSError:
                    pass
        except ImportError:
            pass
    roots += [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam",
              os.path.expanduser("~/.steam/steam"),
              os.path.expanduser("~/.local/share/Steam")]
    out, seen = [], set()
    for r in roots:
        if r and os.path.isdir(r) and os.path.normcase(r) not in seen:
            seen.add(os.path.normcase(r))
            out.append(r)
    return out


def steam_libraries(root):
    """Extra library folders on other drives, from libraryfolders.vdf.

    Parsed with a plain scan rather than a VDF library: the only thing wanted
    is every "path" value, and adding a dependency to this script so it can
    run on a machine that is short of disk is the wrong trade.
    """
    vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
    out = []
    try:
        with open(vdf, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s.startswith('"path"'):
                    continue
                parts = s.split('"')
                if len(parts) >= 4:
                    out.append(parts[3].replace("\\\\", "\\"))
    except OSError:
        pass
    return [p for p in out if os.path.isdir(p)
            and os.path.normcase(p) != os.path.normcase(root)]


# ===========================================================================
def report(args):
    print("=" * 78)
    print("  WHAT ATE MY DISK   --   read-only, nothing is deleted")
    print("  " + time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 78)

    print("\nDRIVES")
    drives = [f"{c}:\\" for c in "CDEFG"] if WIN else ["/"]
    for d in drives:
        if not os.path.exists(d):
            continue
        try:
            t, _used, free = shutil.disk_usage(d)
        except OSError:
            continue
        print(f"  {d:<6} size {t / GB:8.1f} GB   free {free / GB:8.1f} GB"
              f"   ({100.0 * free / max(t, 1):.1f}% free)")

    print("\nTHE USUAL SUSPECTS")
    print("  A large sudden drop that later partly recovers is a crash dump")
    print("  more often than anything else: Windows writes one at the crash,")
    print("  and cleanup or the next crash reclaims it.\n")

    if WIN:
        win = os.environ.get("SystemRoot", r"C:\Windows")
        dmp = os.path.join(win, "MEMORY.DMP")
        row("MEMORY.DMP  (kernel/full crash dump)", fsize(dmp),
            mtime(dmp) and "written " + mtime(dmp))
        row("Minidump", du(os.path.join(win, "Minidump")))
        row("LiveKernelReports", du(os.path.join(win, "LiveKernelReports")))
        row("pagefile.sys", fsize(r"C:\pagefile.sys"), "grows under RAM pressure")
        row("swapfile.sys", fsize(r"C:\swapfile.sys"))
        row("hiberfil.sys", fsize(r"C:\hiberfil.sys"), "~40% of RAM when on")
        row("SoftwareDistribution\\Download",
            du(os.path.join(win, "SoftwareDistribution", "Download")),
            "Windows Update staging")
        row("Windows\\Temp", du(os.path.join(win, "Temp")))
        row("Windows\\Installer", du(os.path.join(win, "Installer")),
            "MSI cache -- never delete by hand")
        row("$Recycle.Bin", du(r"C:\$Recycle.Bin"))
        row("Defender", du(r"C:\ProgramData\Microsoft\Windows Defender"))
    tmp = os.environ.get("TEMP") or os.environ.get("TMPDIR") or "/tmp"
    row("TEMP  (" + tmp + ")", du(tmp))

    print("\nSTEAM")
    roots = steam_roots()
    if not roots:
        print("  no Steam install found")
    for r in roots:
        print(f"  root: {r}")
        sa = os.path.join(r, "steamapps")
        row("  common  (installed games)", du(os.path.join(sa, "common")))
        row("  downloading", du(os.path.join(sa, "downloading")),
            "a paused or failed update parks here")
        row("  temp", du(os.path.join(sa, "temp")))
        row("  workshop", du(os.path.join(sa, "workshop")))
        row("  shadercache", du(os.path.join(sa, "shadercache")),
            "built on first launch of a game")
        row("  depotcache", du(os.path.join(r, "depotcache")))
        for lib in steam_libraries(r):
            row(f"  library: {lib}",
                du(os.path.join(lib, "steamapps", "common")))

    print("\nBROWSERS")
    print("  Many tabs cost RAM, and RAM pressure grows the pagefile. The")
    print("  caches themselves are rarely the answer -- check pagefile above.\n")
    la = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    for label, sub in (("Chrome (all profiles)", r"Google\Chrome\User Data"),
                       ("Edge (all profiles)", r"Microsoft\Edge\User Data"),
                       ("Firefox profiles", r"Mozilla\Firefox\Profiles")):
        row(label, du(os.path.join(la, sub)))

    print("\nTHIS PROJECT   (should grow ~100 MB/hour, no more)")
    for d in (args.data, args.feeds, args.fulltape, os.getcwd()):
        if d:                       # an unset --feeds must not print a blank row
            row(d, du(d))

    if WIN:
        print("\nSYSTEM RESTORE / SHADOW COPIES")
        try:
            p = subprocess.run(["vssadmin", "list", "shadowstorage"],
                               capture_output=True, text=True, timeout=60)
            out = (p.stdout or "") + (p.stderr or "")
            if p.returncode != 0 or "denied" in out.lower():
                print("  needs admin -- rerun from an elevated prompt")
            else:
                for ln in out.splitlines():
                    if any(k in ln for k in ("Used", "Allocated", "Maximum",
                                             "volume")):
                        print("  " + ln.strip())
        except (OSError, subprocess.SubprocessError):
            print("  vssadmin unavailable")

    if not args.deep:
        print("\n  The targeted checks above are fast and usually name it.")
        print("  Add  --deep  for the two slow passes: every top-level folder")
        print("  sized, and every large recently-changed file listed by name.")
        print("  Those read the whole drive and take several minutes.")
        print("\n" + "=" * 78)
        print("  Nothing above was deleted. Read it, then decide.")
        print("=" * 78)
        return

    print("\nBIGGEST FOLDERS   (whole-drive read, several minutes)")
    roots = ([r"C:\\", la, os.environ.get("APPDATA", la), r"C:\ProgramData",
              r"C:\Program Files", r"C:\Program Files (x86)"]
             if WIN else ["/", os.path.expanduser("~")])
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        print(f"\n  under {root}")
        sizes = []
        try:
            with os.scandir(root) as it:
                for e in it:
                    if e.is_dir(follow_symlinks=False):
                        r = du(e.path)
                        sizes.append((r[0] if r else 0, r[2] if r else 0,
                                      e.path))
        except OSError:
            print("    unreadable")
            continue
        for b, denied, path in sorted(sizes, reverse=True)[:8]:
            extra = f"  (+{denied} unreadable)" if denied else ""
            print(f"    {b / GB:9.2f} GB  {path}{extra}")

    print("\n" + "=" * 78)
    print(f"  FILES OVER {args.min_mb} MB CHANGED IN THE LAST {args.days} DAYS")
    print("  This is the direct answer to 'what changed'.")
    print("=" * 78)
    hits = big_recent(r"C:\\" if WIN else "/", args.min_mb, args.days)
    if not hits:
        print("  nothing that large changed that recently")
    for size, when, path in hits[:40]:
        print(f"  {size / GB:9.2f} GB  {when}  {path}")

    print("\n" + "=" * 78)
    print("  Nothing above was deleted. Read it, then decide.")
    print("=" * 78)


def big_recent(root, min_mb, days, now=None):
    """Every file over min_mb changed in the last `days`, largest first."""
    cut = (now if now is not None else time.time()) - days * 86400.0
    lim = min_mb * MB
    out, stack, seen = [], [root], set()
    while stack:
        d = stack.pop()
        try:
            st = os.stat(d, follow_symlinks=False)
            key = (st.st_dev, st.st_ino)
            if key in seen:
                continue
            seen.add(key)
        except OSError:
            continue
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            s = e.stat(follow_symlinks=False)
                            if s.st_size >= lim and s.st_mtime >= cut:
                                out.append((s.st_size,
                                            time.strftime("%Y-%m-%d %H:%M",
                                                          time.localtime(s.st_mtime)),
                                            e.path))
                    except OSError:
                        pass
        except OSError:
            pass
    return sorted(out, reverse=True)


# ===========================================================================
def selftest():
    import tempfile
    print("=" * 78)
    print("SELF-TEST -- measured against trees of a KNOWN size")
    print("=" * 78)
    fails = []
    tmp = tempfile.mkdtemp()
    try:
        # a known tree: 3 files of known length, two levels deep
        os.makedirs(os.path.join(tmp, "a", "b"))
        for path, n in ((("a", "f1"), 1000), (("a", "b", "f2"), 2500),
                        (("f3",), 7)):
            with open(os.path.join(tmp, *path), "wb") as f:
                f.write(b"x" * n)
        got = du(tmp)
        print(f"  known tree: 3 files / 3,507 bytes  ->  du reports "
              f"{got[1]} files / {got[0]:,} bytes")
        if got[:2] != (3507, 3):
            fails.append(f"du read {got[0]} bytes in {got[1]} files, "
                         "expected 3,507 in 3")

        if du(os.path.join(tmp, "nope")) is not None:
            fails.append("du invented a size for a path that does not exist")

        # an empty directory must not look like an unreadable one
        os.makedirs(os.path.join(tmp, "empty"))
        e = du(os.path.join(tmp, "empty"))
        if e != (0, 0, 0):
            fails.append(f"empty directory reported {e}")

        # An UNREADABLE directory must be COUNTED, not silently summed to
        # zero. This is the whole point of the denied counter: a locked
        # folder printed as "0.00 GB" is exactly how the thing you are
        # hunting hides from the report.
        #
        # Tested by making os.scandir refuse, rather than by chmod 000: chmod
        # does nothing when the process is root or on Windows, so a
        # privilege-based fixture SKIPS on both machines that matter and the
        # check would silently never run.
        locked = os.path.join(tmp, "locked")
        os.makedirs(os.path.join(locked, "inner"))
        with open(os.path.join(locked, "inner", "big"), "wb") as f:
            f.write(b"y" * 5000)
        with open(os.path.join(tmp, "readable_sibling"), "wb") as f:
            f.write(b"z" * 111)
        real_scandir = os.scandir
        key = os.path.normcase(locked)

        def refusing_scandir(path):
            if os.path.normcase(str(path)).startswith(key):
                raise PermissionError(13, "Permission denied", str(path))
            return real_scandir(path)

        os.scandir = refusing_scandir
        try:
            g = du(locked)
            whole = du(tmp)
        finally:
            os.scandir = real_scandir
        print(f"  unreadable directory -> bytes={g[0]} denied={g[2]}")
        if g[2] == 0:
            fails.append("an unreadable directory was reported as readable "
                         "and empty -- 5,000 hidden bytes would print as "
                         "0.00 GB")
        if g[0] != 0:
            fails.append(f"read {g[0]} bytes out of a directory that refused "
                         "to be read")
        print(f"  partly-unreadable tree -> bytes={whole[0]:,} "
              f"denied={whole[2]}")
        if whole[2] == 0:
            fails.append("a tree containing an unreadable branch reported no "
                         "denials")
        if whole[0] != 3507 + 111:
            fails.append(f"partly-unreadable tree summed {whole[0]}, expected "
                         "the 3,618 readable bytes")

        # big_recent must key on BOTH size and age
        now = time.time()
        os.makedirs(os.path.join(tmp, "scan"))
        spec = [("big_new", 3 * MB, now - 3600, True),
                ("big_old", 3 * MB, now - 30 * 86400, False),
                ("small_new", 1024, now - 3600, False)]
        for name, size, when, _want in spec:
            p = os.path.join(tmp, "scan", name)
            with open(p, "wb") as f:
                f.seek(int(size) - 1)
                f.write(b"\0")
            os.utime(p, (when, when))
        found = {os.path.basename(p)
                 for _s, _w, p in big_recent(os.path.join(tmp, "scan"),
                                             min_mb=2, days=4, now=now)}
        print(f"  recent-and-large filter -> {sorted(found)}")
        for name, _s, _w, want in spec:
            if want and name not in found:
                fails.append(f"big_recent missed {name}")
            if not want and name in found:
                fails.append(f"big_recent returned {name}, which it should "
                             "have filtered out")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- sizes are exact, absent is not zero, denied is")
    print("not empty, and the recent-file filter keys on size AND age.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deep", action="store_true")
    ap.add_argument("--days", type=int, default=4)
    ap.add_argument("--min-mb", type=int, default=300)
    ap.add_argument("--data", default=r"C:\kals\kalshi_data" if WIN
                    else "./kalshi_data")
    ap.add_argument("--feeds", default=r"C:\kals\feed_data" if WIN
                    else "./feed_data")
    ap.add_argument("--fulltape", default=r"C:\kals\fulltape" if WIN
                    else "./fulltape")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to report numbers")
    print()
    report(a)


if __name__ == "__main__":
    main()
