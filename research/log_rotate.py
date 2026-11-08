#!/usr/bin/env python3
r"""log_rotate.py -- gzip FINISHED logs of a few families into results\archive\ so the server's disk lasts (2026-11-07).

WHY. On 11-07 the server had 26.3 GB free and was losing ~1.46 GB a week with nothing ever rotated: full around
March 2027. The biggest growers (MB written over the 14 days to 11-07): pintraj-live-*.jsonl 592, ladder-live.jsonl
501, cleanroom-locked_average_ladder_re.jsonl 476, forecaster-live.jsonl 75, pinrun-paper-*.jsonl 52, rows.jsonl 44,
pinrun-live-*.jsonl 44. These logs pack 9x to 13x under gzip (measured 11-07 on the laptop's copies).

WHAT IS MOVED: a file in results\ (the top folder only) whose name matches a POLICY family below, and that
  - is not the NEWEST of its family (by modified time) -- a bot's current run is never touched;
  - was not modified for the family's age (48 h; pinrun-live-*: 60 days, small and read by many tools) and never
    one modified in the last 24 h whatever a row says (HARD_FLOOR_S);
  - is not tracked by git (a tracked file deleted from the live repo is a change a merge can trip on);
  - can be opened EXCLUSIVELY (Windows: no other process holds it open). The run then HOLDS that handle while it
    copies, checks and deletes, so nothing can write to the file in between.
It becomes results\archive\<name>.gz (gzip level 6, its modified time kept). The plain file is deleted ONLY after
the .gz has been read back to the same sha256 and length; anything else keeps the plain file and says why.
EVERY OTHER FILE IS LEFT ALONE -- a single ever-growing log (ladder-live.jsonl, cleanroom-*.jsonl,
forecaster-live.jsonl, rows.jsonl) is the newest of its own family and cannot be rotated from outside; the dry run
lists the biggest of them so it stays visible. Archives are never deleted.

READERS. Every tool that reads a family's history reads the archive too, through research\logfiles.py
(logfiles.glob / logfiles.open). Adding a family to POLICY means converting its readers first (CHANGES_ops.md has
the reader audit of 11-07), never the other way round. server_sync.py copies results\ top level only, so an archived
file simply stops changing on the laptop (the laptop's plain copy stays).

NEVER COMPETES WITH THE BOTS: below-normal priority, and no file is started inside the busy window of a quarter-hour
close (BUSY_BEFORE_S before it to BUSY_AFTER_S after, the time pin buys and hedges); stops when free disk is short
(a .gz needs room) or the run's byte budget is spent.

OUTPUT: one line per action and a summary line, printed and appended to results\log_rotate.log; the run's numbers
and the free-disk history (for the weeks-left projection) in results\log_rotate_status.json. An --apply run writes a
"started" line and a "running" status FIRST, so a run that dies part way still leaves a trace.

THE PHONE SEES IT (11-07 review: a rotation that silently moved nothing would have let the disk fill anyway).
health() reads the status and the installer's marker (results\log_rotate_installed.json); phone/monitor.py alerts
once when it turns bad -- never ran, stuck, stale (no run for 36 h), failed, git unreadable (moved nothing), or the
disk within 8 weeks of the 6 GB line -- and once when it is ok again; /server shows the last run. git is looked for on
the PATH, then in Program Files (find_git), and the installer passes the one it found (--git).

    python research\log_rotate.py                 # dry run (default): what would move, and the headroom
    python research\log_rotate.py --apply         # do it (the scheduled task KalsLogRotate, daily)
    python research\log_rotate.py --self-test     # planted worlds; nothing outside a temp folder is touched

Standard library only. No network, no Kalshi, no key; never touches kalshi_data or feed_data.
"""
import argparse
import collections
import fnmatch
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
if HERE not in sys.path:
    sys.path.append(HERE)               # under python -I too (the task); appended: never shadows a stdlib name
import logfiles                                                  # noqa: E402

Family = collections.namedtuple("Family", "pattern min_age_s why")
DAY = 86400.0
HOUR = 3600.0

# THE ONLY FILES THIS SCRIPT MAY EVER MOVE. A row needs its readers converted to research\logfiles.py FIRST.
POLICY = (
    Family("pintraj-live-*.jsonl", 2 * DAY, "pin's 1 Hz trajectory, one file a run; read by changes_watch only"),
    Family("pinrun-paper-*.jsonl", 2 * DAY, "paper arms' decision logs, one file a run"),
    Family("pinrun-live-*.jsonl", 60 * DAY, "pin's own live log: small, read by many tools, kept plain 60 days"),
)
HARD_FLOOR_S = 24 * HOUR       # never a file modified in the last 24 h, whatever a POLICY row says
LEVEL = 6
CHUNK = 1 << 20
BUSY_BEFORE_S = 120            # no file is started this long before a quarter-hour close ...
BUSY_AFTER_S = 30              # ... until this long after it
RATE_BPS = 20e6                # assumed bytes a second (pack + read back), to judge whether a file fits before a close
MAX_BYTES = 8 << 30            # raw bytes one run may move (the first run on the server clears the backlog)
RESERVE_BYTES = 1 << 30        # free disk kept after a .gz (estimated at a quarter of the file) is written
GUARD_GB = 6.0                 # CLAUDE.md: below 6 GB free stop all analysis -- the line the projection counts to
BASELINE_GB_WEEK = 1.46        # measured 11-07 (server, before rotation); used until this script has its own history
HISTORY_KEEP = 120
LOCK_STALE_S = 6 * HOUR
LOG_NAME = "log_rotate.log"
STATUS_NAME = "log_rotate_status.json"
LOCK_NAME = ".log_rotate.lock"             # inside the archive folder
_STAMP = re.compile(r"\d{8}T\d{6}Z")


def _utc(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def family_of(name):
    """The POLICY row a file name belongs to, or None (case-blind, as Windows names are)."""
    n = name.lower()
    for f in POLICY:
        if fnmatch.fnmatch(n, f.pattern.lower()):
            return f
    return None


def family_key(name):
    """A name's family for the report of what is NOT moved: its run stamp replaced by '*'."""
    return _STAMP.sub("*", name, count=1)


# ---- facts about a file ---------------------------------------------------------------------------------------
# Where git is when it is not on the PATH: the scheduled task runs as SYSTEM, whose PATH is the MACHINE Path, and a
# per-user Git install is not on it (11-07 review: every run would then have moved nothing, silently).
GIT_PLACES = (r"C:\Program Files\Git\cmd\git.exe", r"C:\Program Files\Git\bin\git.exe",
              r"C:\Program Files (x86)\Git\cmd\git.exe")


def find_git(places=GIT_PLACES):
    """git's path: on the PATH, else the usual install folders; None when there is none."""
    g = shutil.which("git")
    if g:
        return g
    for p in places:
        if os.path.isfile(p):
            return p
    return None


def git_tracked(repo, results, git=None):
    """Lower-cased names of the files git tracks in `results` (top folder), set() when `repo` is no git work tree,
    None when git could not answer (then nothing is moved: a tracked file must never be deleted by mistake).
    `git` = the git to run (the installer passes the one it found); None = find_git()."""
    if not os.path.exists(os.path.join(repo, ".git")):
        return set()
    git = git or find_git()
    if not git:
        return None
    rel = os.path.relpath(results, repo).replace("\\", "/")
    try:
        # safe.directory: the task runs as SYSTEM, which does not own C:\kals-repo (git >= 2.35.2 refuses without it)
        r = subprocess.run([git, "-c", "safe.directory=*", "-C", repo, "ls-files", "-z", "--", rel],
                           capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    out = set()
    for p in r.stdout.decode("utf-8", "replace").split("\0"):
        if not p:
            continue
        head, _sep, name = p.rpartition("/")
        if head == rel:
            out.add(name.lower())
    return out


class Held:
    """A file opened so that no other process can open it while this is held; `.fh` reads it, `.delete()` removes it
    (Windows: marked for deletion on the held handle, so the name goes when it is closed). Elsewhere a plain open,
    with the size and time checked again before the delete."""

    def __init__(self, path):
        self.path = path
        self.fh = None
        self.fd = None
        self._mark = False
        self.st = os.stat(path)

    @staticmethod
    def open(path):
        """(Held, None) or (None, why)."""
        h = Held(path)
        if os.name != "nt":
            h.fh = open(path, "rb")
            return h, None
        import ctypes
        import msvcrt
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        cf = k32.CreateFileW
        cf.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                       wintypes.DWORD, wintypes.HANDLE]
        cf.restype = wintypes.HANDLE
        generic_read, delete, open_existing, sequential = 0x80000000, 0x00010000, 3, 0x08000000
        hd = cf(os.path.abspath(path), generic_read | delete, 0, None, open_existing, sequential, None)
        if hd is None or hd == ctypes.c_void_p(-1).value:
            err = ctypes.get_last_error()
            return None, ("held open by another process" if err == 32
                          else "cannot open it alone (Windows error %d)" % err)
        h.fd = msvcrt.open_osfhandle(hd, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        h.fh = os.fdopen(h.fd, "rb", buffering=0)
        return h, None

    def delete(self):
        """Remove the file when this is closed. Returns None or why it could not be."""
        if os.name != "nt":
            st = os.stat(self.path)
            if (st.st_size, st.st_mtime_ns) != (self.st.st_size, self.st.st_mtime_ns):
                return "it changed while it was being archived"
            self._mark = True
            return None
        import ctypes
        import msvcrt
        from ctypes import wintypes

        class Disp(ctypes.Structure):
            _fields_ = [("DeleteFile", wintypes.BOOLEAN)]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        sf = k32.SetFileInformationByHandle
        sf.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        sf.restype = wintypes.BOOL
        d = Disp(True)
        if not sf(msvcrt.get_osfhandle(self.fd), 4, ctypes.byref(d), ctypes.sizeof(d)):   # 4 = FileDispositionInfo
            return "Windows refused the delete (error %d)" % ctypes.get_last_error()
        return None

    def close(self):
        if self.fh is not None:
            self.fh.close()
            self.fh = None
        if self._mark:
            os.remove(self.path)


def _hash_gz(path):
    """(sha256 hex, unpacked length) of a .gz, or (None, why)."""
    h = hashlib.sha256()
    n = 0
    try:
        with gzip.open(path, "rb") as fh:
            while True:
                b = fh.read(CHUNK)
                if not b:
                    break
                h.update(b)
                n += len(b)
    except (OSError, EOFError, ValueError) as e:
        return None, "%s: %s" % (type(e).__name__, e)
    return h.hexdigest(), n


def pack(src_fh, name, mtime, part):
    """Write the held source into `part` as gzip; (sha256 hex, length) of the bytes read."""
    h = hashlib.sha256()
    n = 0
    with open(part, "wb") as raw:
        with gzip.GzipFile(filename=name, mode="wb", compresslevel=LEVEL, fileobj=raw, mtime=int(mtime)) as gz:
            while True:
                b = src_fh.read(CHUNK)
                if not b:
                    break
                h.update(b)
                n += len(b)
                gz.write(b)
        raw.flush()
        os.fsync(raw.fileno())
    return h.hexdigest(), n


# ---- the plan --------------------------------------------------------------------------------------------------
def plan(results, now, tracked, policy=None):
    """(moves, kept, others): moves = [(path, family, size, mtime)] oldest first; kept = [(name, why)] for every
    POLICY file not moved; others = {family key: [files, bytes]} for every file no POLICY row covers."""
    policy = POLICY if policy is None else policy
    try:
        entries = sorted(os.scandir(results), key=lambda e: e.name)
    except OSError:
        return [], [("results", "cannot list %s" % results)], {}
    fams = collections.defaultdict(list)
    others = collections.defaultdict(lambda: [0, 0])
    for e in entries:
        try:
            if not e.is_file():
                continue
            st = e.stat()
        except OSError:
            continue
        f = None
        for row in policy:
            if fnmatch.fnmatch(e.name.lower(), row.pattern.lower()):
                f = row
                break
        if f is None:
            o = others[family_key(e.name)]
            o[0] += 1
            o[1] += st.st_size
            continue
        fams[f].append((e.path, e.name, st.st_size, st.st_mtime))
    moves, kept = [], []
    for f, files in fams.items():
        newest = max(files, key=lambda x: (x[3], x[1]))
        for path, name, size, mtime in files:
            age = now - mtime
            if path == newest[0]:
                why = "the newest of %s" % f.pattern
            elif age < HARD_FLOOR_S:
                why = "modified %.1f h ago (never under 24 h)" % (age / HOUR)
            elif age < f.min_age_s:
                why = "modified %.1f days ago (%s waits %.0f days)" % (age / DAY, f.pattern, f.min_age_s / DAY)
            elif tracked is None:
                why = "git could not say whether it tracks the file"
            elif name.lower() in tracked:
                why = "tracked by git"
            else:
                moves.append((path, f, size, mtime))
                continue
            kept.append((name, why))
    moves.sort(key=lambda x: x[3])
    return moves, kept, dict(others)


def _wait_quiet(est_s, now_fn, sleep_fn, say):
    """Hold off while a quarter-hour close is near: start a file only if it ends BUSY_BEFORE_S before the next close,
    else sleep until BUSY_AFTER_S after that close. Returns the seconds slept."""
    slept = 0.0
    for _ in range(4):
        t = now_fn()
        nxt = (int(t // 900) + 1) * 900.0
        prev = nxt - 900.0
        if t - prev < BUSY_AFTER_S:
            wake = prev + BUSY_AFTER_S
        elif t + est_s > nxt - BUSY_BEFORE_S:
            wake = nxt + BUSY_AFTER_S
        else:
            return slept
        if not slept:
            say("waiting %.0f s: a quarter-hour close is near (the bots' busy minute)" % (wake - t))
        sleep_fn(max(0.0, wake - t))
        slept += max(0.0, wake - t)
    return slept


def archive_one(path, size, mtime, archive, say):
    """Move one file. Returns (status, info): status 'moved' / 'kept' / 'error'; info has why / gz bytes."""
    name = os.path.basename(path)
    gz = os.path.join(archive, name + logfiles.GZ)
    part = gz + ".part"
    held, why = Held.open(path)
    if held is None:
        return "kept", {"why": why}
    try:
        if os.path.exists(gz):
            sha_src = hashlib.sha256()
            n = 0
            while True:
                b = held.fh.read(CHUNK)
                if not b:
                    break
                sha_src.update(b)
                n += len(b)
            sha_gz, n_gz = _hash_gz(gz)
            if sha_gz != sha_src.hexdigest() or n_gz != n:
                return "kept", {"why": "the archive already holds a DIFFERENT %s.gz; both kept, look by hand" % name}
            why = held.delete()
            if why:
                return "error", {"why": "archived copy is identical but the plain file was not deleted: " + why}
            return "moved", {"gz": os.path.getsize(gz), "dup": True}
        try:
            sha, n = pack(held.fh, name, mtime, part)
        except OSError as e:
            _rm(part)
            return "error", {"why": "could not write the archive: %s" % e}
        if n != held.st.st_size:
            _rm(part)
            return "error", {"why": "read %d bytes of a %d-byte file" % (n, held.st.st_size)}
        sha_gz, n_gz = _hash_gz(part)
        if sha_gz != sha or n_gz != n:
            _rm(part)
            return "error", {"why": "the archive did not read back to the same bytes (%s); plain file kept"
                             % (n_gz if sha_gz is None else "sha256 differs")}
        os.replace(part, gz)
        os.utime(gz, (mtime, mtime))
        why = held.delete()
        if why:
            return "error", {"why": "archived and checked, but the plain file was not deleted: " + why}
        return "moved", {"gz": os.path.getsize(gz), "sha256": sha}
    finally:
        held.close()


def _rm(p):
    try:
        os.remove(p)
    except OSError:
        pass


# ---- the run ---------------------------------------------------------------------------------------------------
def _below_normal():
    """Never compete with the bots for the CPU."""
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x00004000)
    except Exception:                                                # noqa: BLE001
        pass


def _lock(archive, now):
    """Take the run lock (inside the archive folder). None, or why not."""
    p = os.path.join(archive, LOCK_NAME)
    for _ in range(2):
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, ("%d %s" % (os.getpid(), _utc(now))).encode())
            os.close(fd)
            return None
        except FileExistsError:
            try:
                age = now - os.path.getmtime(p)
            except OSError:
                continue
            if age < LOCK_STALE_S:
                return "another rotation holds %s (%.0f min old)" % (p, age / 60)
            _rm(p)
    return "could not take the lock %s" % p


def _unlock(archive):
    _rm(os.path.join(archive, LOCK_NAME))


def projection(history, free_now, now):
    """(GB a week the disk fills, weeks to the 6 GB guard, weeks to empty, how it was measured). Measured from this
    script's own free-disk history once it spans 3 days (the first run's backlog skipped), else the 11-07 baseline."""
    hs = [h for h in history if isinstance(h, dict) and h.get("free") is not None and h.get("t") is not None]
    rate = None
    how = None
    if len(hs) >= 3:
        a = hs[1]                                   # after the first run, which cleared the backlog
        b = hs[-1]
        span = float(b["t"]) - float(a["t"])
        if span >= 3 * DAY:
            rate = (float(a["free"]) - float(b["free"])) / span * 7 * DAY / 1e9
            how = "measured over the last %.0f days of runs" % (span / DAY)
    if rate is None:
        rate = BASELINE_GB_WEEK
        how = "the 11-07 baseline, measured before rotation; this script's own runs take over once they span 3 days"
    gb = free_now / 1e9
    if rate <= 0:
        return rate, None, None, how
    return rate, max(0.0, (gb - GUARD_GB) / rate), gb / rate, how


def run(results=RESULTS, repo=REPO, apply=False, now_fn=time.time, sleep_fn=time.sleep, disk_fn=shutil.disk_usage,
        tracked_fn=git_tracked, max_bytes=MAX_BYTES, policy=None, out=print, write_files=True):
    """One rotation. Returns (exit code, summary dict). Exit 0 = done (some files may be kept, each with its why),
    1 = a file failed (its plain copy kept), 2 = the run could not start."""
    t0 = now_fn()
    archive = logfiles.archive_dir(results)
    lines = []

    def say(m):
        lines.append("%s  %s" % (_utc(now_fn()), m))
        out(m)

    if not os.path.isdir(results):
        say("STOPPED: no results folder at %s" % results)
        return 2, {"ok": False, "why": "no results folder"}
    old = _read_status(results)
    hist = [h for h in (old.get("history") or []) if isinstance(h, dict)]
    if write_files and apply:
        # a run that dies part way (killed, out of memory, the 2 h task limit) still leaves a trace: the log line now,
        # and a status saying "running" since t0, which the phone calls stuck after STUCK_S (health below)
        _append_log(results, ["%s  started (pid %d)" % (_utc(t0), os.getpid())], out)
        _write_status(results, dict({k: v for k, v in old.items() if k != "history"}, state="running",
                                    started_t=t0, pid=os.getpid(), history=hist), out)
    tracked = tracked_fn(repo, results)
    moves, kept, others = plan(results, t0, tracked, policy)
    raw_total = sum(m[2] for m in moves)
    say("%s: %d file(s) to archive, %.1f MB plain; %d kept where they are; git %s"
        % ("APPLY" if apply else "DRY RUN (nothing is changed; --apply does it)", len(moves), raw_total / 1e6,
           len(kept), "unreadable (nothing moves)" if tracked is None else "read"))
    summary = {"t": t0, "apply": bool(apply), "planned": len(moves), "planned_mb": round(raw_total / 1e6, 1),
               "moved": 0, "raw_mb": 0.0, "gz_mb": 0.0, "freed_mb": 0.0, "errors": [], "kept": {},
               "git": "unreadable" if tracked is None else "read"}
    code = 0
    if apply and moves:
        os.makedirs(archive, exist_ok=True)
        why = _lock(archive, t0)
        if why:
            say("STOPPED: " + why)
            if write_files:
                _append_log(results, lines, out)       # the run holding the lock writes the status
            return 2, dict(summary, ok=False, why=why)
        try:
            _below_normal()
            for p in os.listdir(archive):                       # a crash mid-write leaves a .part: ours, drop it
                if p.endswith(".gz.part"):
                    _rm(os.path.join(archive, p))
            used = 0
            for path, fam, size, mtime in moves:
                name = os.path.basename(path)
                if used and used + size > max_bytes:
                    say("stopped for this run: %.0f MB moved, the budget is %.0f MB (the rest goes next run)"
                        % (used / 1e6, max_bytes / 1e6))
                    break
                free = disk_fn(results).free
                if free < size / 4 + RESERVE_BYTES:
                    say("STOPPED: %.2f GB free is too little to write %s's archive safely" % (free / 1e9, name))
                    summary["errors"].append("low disk")
                    code = 1
                    break
                _wait_quiet(2 + size / RATE_BPS, now_fn, sleep_fn, say)
                st, info = archive_one(path, size, mtime, archive, say)
                if st == "moved":
                    used += size
                    summary["moved"] += 1
                    summary["raw_mb"] += size / 1e6
                    summary["gz_mb"] += info["gz"] / 1e6
                    say("moved %s: %.1f MB -> %.1f MB%s" % (name, size / 1e6, info["gz"] / 1e6,
                                                           " (identical archive already there)" if info.get("dup")
                                                           else " (read back: same sha256)"))
                elif st == "kept":
                    kept.append((name, info["why"]))
                    say("kept %s: %s" % (name, info["why"]))
                else:
                    code = 1
                    summary["errors"].append("%s: %s" % (name, info["why"]))
                    say("FAILED %s: %s" % (name, info["why"]))
        finally:
            _unlock(archive)
    elif not apply:
        for path, fam, size, mtime in moves:
            say("would move %s (%.1f MB, last written %s)" % (os.path.basename(path), size / 1e6, _utc(mtime)))
    reasons = collections.Counter(re.sub(r"[\d.]+ (h|days) ago", "* ago", w) for _n, w in kept)
    summary["kept"] = dict(reasons)
    for w, n in sorted(reasons.items(), key=lambda x: -x[1]):
        say("kept %d: %s" % (n, w))
    big = sorted(others.items(), key=lambda x: -x[1][1])[:8]
    if big:
        say("left alone (no rotation rule): " + ", ".join("%s %.0f MB" % (k, v[1] / 1e6) for k, v in big))
    summary["raw_mb"] = round(summary["raw_mb"], 1)
    summary["gz_mb"] = round(summary["gz_mb"], 1)
    summary["freed_mb"] = round(summary["raw_mb"] - summary["gz_mb"], 1)
    free = disk_fn(results).free
    if apply:
        hist = (hist + [{"t": t0, "free": free, "freed": round(summary["freed_mb"] * 1e6)}])[-HISTORY_KEEP:]
    rate, wk_guard, wk_empty, how = projection(hist, free, t0)
    summary.update(free_gb=round(free / 1e9, 2), gb_week=round(rate, 3),
                   weeks_to_guard=None if wk_guard is None else round(wk_guard, 1),
                   weeks_to_empty=None if wk_empty is None else round(wk_empty, 1), rate_from=how, ok=code == 0)
    if apply:
        say("done: moved %d file(s), %.1f MB -> %.1f MB, freed %.1f MB; %d error(s)"
            % (summary["moved"], summary["raw_mb"], summary["gz_mb"], summary["freed_mb"], len(summary["errors"])))
    else:
        say("would free about %.0f MB (gzip packs these logs 9x to 13x)" % (raw_total * 0.9 / 1e6))
    if wk_empty is None:
        say("disk: %.1f GB free, not filling (%s)" % (free / 1e9, how))
    else:
        say("disk: %.1f GB free, filling %.2f GB a week (%s): about %.0f weeks to the 6 GB line, %.0f weeks to empty"
            % (free / 1e9, rate, how, wk_guard, wk_empty))
    if write_files and apply:
        _append_log(results, lines, out)
        _write_status(results, dict(summary, state="done", started_t=t0, finished_t=now_fn(), history=hist), out)
    return code, summary


def _read_status(results):
    try:
        with open(os.path.join(results, STATUS_NAME), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _append_log(results, lines, out=print):
    try:
        with open(os.path.join(results, LOG_NAME), "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError as e:
        out("could not write the log: %s" % e)


def _write_status(results, rec, out=print):
    p = os.path.join(results, STATUS_NAME)
    try:
        with open(p + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1)
        os.replace(p + ".tmp", p)
    except OSError as e:
        out("could not write the status file: %s" % e)


# ---- what the phone shows (phone/monitor.py check_rotation; /server) -------------------------------------------
INSTALLED_NAME = "log_rotate_installed.json"   # results\log_rotate_install.ps1 writes it; -Uninstall removes it
STALE_S = 36 * HOUR            # a daily task with no finished run for this long has stopped running
STUCK_S = 3 * HOUR             # a run "running" for this long died part way (the task's own limit is 2 h)
SHORT_WEEKS = 8.0              # the disk reaching the 6 GB line within this many weeks is said early
BAD = ("never", "stuck", "stale", "failed", "nogit", "short")


def health(results=RESULTS, now=None):
    """The rotation's state for the phone, from results\\log_rotate_status.json and the installer's marker. Never
    raises. {"state", "bad", ...the last run's numbers}. state:
      none     not installed (no marker, no status): the phone says nothing
      waiting  installed, its first run not due yet
      running  a run started under STUCK_S ago and has not finished
      ok       the last run finished and moved what it could
    and the BAD ones (the phone alerts once on entering one, and once when it is ok again):
      never    installed over STALE_S ago and never ran
      stuck    a run started over STUCK_S ago and never finished
      stale    no finished run for STALE_S
      failed   the last run hit an error (the plain files it could not move are kept)
      nogit    the last run could not ask git what it tracks, so it moved nothing
      short    the disk reaches the 6 GB line within SHORT_WEEKS at the last run's rate"""
    now = time.time() if now is None else now
    out = {"state": "none"}
    try:
        st = _read_status(results)
        try:
            with open(os.path.join(results, INSTALLED_NAME), encoding="utf-8-sig") as fh:
                inst = json.load(fh)
            out["installed_t"] = float(inst["installed_t"])
        except (OSError, ValueError, TypeError, KeyError):
            out["installed_t"] = None
        if not st:
            if out["installed_t"] is not None:
                out["state"] = "never" if now - out["installed_t"] > STALE_S else "waiting"
        else:
            for k in ("started_t", "moved", "planned", "raw_mb", "gz_mb", "freed_mb", "free_gb", "gb_week",
                      "weeks_to_guard", "weeks_to_empty", "rate_from", "git"):
                out[k] = st.get(k)
            out["errors"] = [str(e) for e in (st.get("errors") or [])]
            running = st.get("state") == "running"
            # the last FINISHED run: this one, or (while one is running) the one before it, which left no own time
            fin = None if running else (st.get("finished_t") or st.get("t"))
            out["last_t"] = fin
            nogit = st.get("git") == "unreadable" or any("git could not say" in str(k) for k in (st.get("kept") or {}))
            if running and now - float(st.get("started_t") or 0) > STUCK_S:
                out["state"] = "stuck"
            elif running:
                out["state"] = "running"
            elif fin is None or now - float(fin) > STALE_S:
                out["state"] = "stale"
            elif out["errors"] or st.get("ok") is False:
                out["state"] = "failed"
            elif nogit:
                out["state"] = "nogit"
            elif st.get("weeks_to_guard") is not None and float(st["weeks_to_guard"]) < SHORT_WEEKS:
                out["state"] = "short"
            else:
                out["state"] = "ok"
    except Exception as e:                                           # noqa: BLE001
        out = {"state": "none", "err": "%s: %s" % (type(e).__name__, str(e)[:120])}
    out["bad"] = out["state"] in BAD
    return out


# ---- self-test -------------------------------------------------------------------------------------------------
def selftest():
    import tempfile

    fails = []

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg, flush=True)
        if not cond:
            fails.append(msg)

    Disk = collections.namedtuple("Disk", "total used free")
    now = 1794050400.0                                  # 2026-11-07T11:20:00Z, 5 min past a close, 10 to the next
    quiet = []

    def w(path, text, age_s):
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.utime(path, (now - age_s, now - age_s))

    def sha(path):
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()

    def go(td, apply=True, tracked=frozenset(), disk=100e9, **kw):
        lines = []
        code, s = run(results=td, repo=td, apply=apply, now_fn=lambda: now, sleep_fn=quiet.append,
                      disk_fn=lambda p: Disk(0, 0, disk), tracked_fn=lambda r, d: tracked, out=lines.append, **kw)
        return code, s, lines

    body = "".join('{"kind": "traj", "t": "2026-11-0%dT00:00:%02dZ", "fair": 0.97%02d}\n' % (1 + i % 5, i % 60, i % 97)
                   for i in range(5000))
    td = tempfile.mkdtemp(prefix="log_rotate-selftest-")
    try:
        T = lambda n: os.path.join(td, n)                                       # noqa: E731
        w(T("pintraj-live-20261028T011720Z.jsonl"), body, 8 * DAY)                    # old: moves
        w(T("pintraj-live-20261030T213241Z.jsonl"), body[:999] + "{\"cut", 3 * DAY)   # old, cut mid-line: moves as is
        w(T("pintraj-live-20261104T101500Z.jsonl"), body, 30 * HOUR)                 # 30 h: under 48 h, stays
        w(T("pintraj-live-20261107T051700Z.jsonl"), body, 9 * DAY)                   # NEWEST by name but ... see below
        os.utime(T("pintraj-live-20261107T051700Z.jsonl"), (now - 60, now - 60))     # ... written a minute ago: newest
        w(T("pinrun-live-20260908T062046Z.jsonl"), "{}\n", 61 * DAY)                  # 61 days: moves
        w(T("pinrun-live-20261020T000000Z.jsonl"), "{}\n", 18 * DAY)                  # 18 days: stays (60-day rule)
        w(T("pinrun-live-20261106T000000Z.jsonl"), "{}\n", 200)                       # newest
        w(T("pinrun-paper-20261001T000000Z.jsonl"), "{}\n", 30 * DAY)                 # tracked by git: stays
        w(T("pinrun-paper-20261101T000000Z.jsonl"), "{}\n", 5 * DAY)                  # moves
        w(T("pinrun-paper-20261107T000000Z.jsonl"), "{}\n", 100)                      # newest
        w(T("ladder-live.jsonl"), body, 40 * DAY)                                     # no rule: never touched
        w(T("cleanroom-locked_average_ladder_re.jsonl"), body, 40 * DAY)
        w(T("pintraj-live-20261029T000000Z.jsonl.bak"), "x", 40 * DAY)                # not the family's name shape
        tracked = {"pinrun-paper-20261001t000000z.jsonl"}
        before = {n: sha(T(n)) for n in os.listdir(td)}

        # DRY RUN: nothing changes
        code, s, lines = go(td, apply=False, tracked=tracked)
        ck(code == 0 and s["planned"] == 4 and {n: sha(T(n)) for n in os.listdir(td)} == before
           and not os.path.exists(logfiles.archive_dir(td)) and not os.path.exists(T(STATUS_NAME)),
           "dry run: 4 files planned, nothing written, no archive folder, no status file")
        ck(any("would move pintraj-live-20261028T011720Z.jsonl" in x for x in lines)
           and any(x.startswith("left alone") and "ladder-live.jsonl" in x for x in lines),
           "dry run names each move and the biggest files no rule covers")

        # NULL: git unreadable -> nothing moves at all
        code, s, lines = go(td, apply=True, tracked=None)
        ck(s["moved"] == 0 and {n: sha(T(n)) for n in os.listdir(td) if n in before} == before
           and s["kept"].get("git could not say whether it tracks the file") == 5,      # the 4 + the tracked one
           "NULL: git unreadable -> nothing is moved, every candidate kept with that reason: %s" % s["kept"])

        # HELD OPEN (Windows): another handle on a candidate keeps it
        hold = open(T("pinrun-paper-20261101T000000Z.jsonl"), "rb") if os.name == "nt" else None
        try:
            code, s, lines = go(td, apply=True, tracked=tracked)
        finally:
            if hold:
                hold.close()
        ad = logfiles.archive_dir(td)
        moved = sorted(os.listdir(ad))
        want = ["pinrun-live-20260908T062046Z.jsonl.gz", "pintraj-live-20261028T011720Z.jsonl.gz",
                "pintraj-live-20261030T213241Z.jsonl.gz"]
        if os.name == "nt":
            ck(moved == want and os.path.exists(T("pinrun-paper-20261101T000000Z.jsonl"))
               and any("held open by another process" in x for x in lines),
               "a file another process holds open is kept (Windows exclusive open)")
        else:
            want.insert(1, "pinrun-paper-20261101T000000Z.jsonl.gz")
        ck(moved == want and code == 0, "apply: exactly the eligible files moved: %s" % moved)
        ck(all(not os.path.exists(T(n[:-3])) for n in moved), "each moved file's plain copy is gone")
        for n in moved:
            with gzip.open(os.path.join(ad, n), "rb") as fh:
                ck(hashlib.sha256(fh.read()).hexdigest() == before[n[:-3]],
                   "%s reads back to the original bytes (a line cut by a crash kept as it was)" % n)
            ck(abs(os.path.getmtime(os.path.join(ad, n)) - (now - {"pinrun-live-20260908T062046Z.jsonl": 61 * DAY,
                                                                  "pintraj-live-20261028T011720Z.jsonl": 8 * DAY,
                                                                  "pintraj-live-20261030T213241Z.jsonl": 3 * DAY,
                                                                  "pinrun-paper-20261101T000000Z.jsonl": 5 * DAY}[n[:-3]]))
               < 2, "%s keeps its source's modified time" % n)
        for n in ("pintraj-live-20261104T101500Z.jsonl", "pintraj-live-20261107T051700Z.jsonl",
                  "pinrun-live-20261020T000000Z.jsonl", "pinrun-live-20261106T000000Z.jsonl",
                  "pinrun-paper-20261001T000000Z.jsonl", "pinrun-paper-20261107T000000Z.jsonl", "ladder-live.jsonl",
                  "cleanroom-locked_average_ladder_re.jsonl", "pintraj-live-20261029T000000Z.jsonl.bak"):
            ck(os.path.exists(T(n)) and sha(T(n)) == before[n], "untouched: %s" % n)
        ck(s["kept"].get("tracked by git") == 1 and s["kept"].get("the newest of pintraj-live-*.jsonl") == 1
           and s["kept"].get("modified * ago (pinrun-live-*.jsonl waits 60 days)") == 1
           and s["kept"].get("modified * ago (pintraj-live-*.jsonl waits 2 days)") == 1,
           "every kept file says why: %s" % s["kept"])
        ck(os.path.exists(T(STATUS_NAME)) and os.path.exists(T(LOG_NAME)) and not os.path.exists(os.path.join(ad, LOCK_NAME)),
           "apply writes the log and the status file and releases its lock")

        # READERS: logfiles.glob sees the whole family, archived or not, with the same bytes
        got = logfiles.glob(T("pintraj-live-*.jsonl"))
        ck([logfiles.log_name(p) for p in got] == ["pintraj-live-20261028T011720Z.jsonl",
                                                   "pintraj-live-20261030T213241Z.jsonl",
                                                   "pintraj-live-20261104T101500Z.jsonl",
                                                   "pintraj-live-20261107T051700Z.jsonl"]
           and all(hashlib.sha256(logfiles.read_bytes(p)).hexdigest() == before[logfiles.log_name(p)] for p in got),
           "a reader through logfiles.glob/open still sees all 4 runs, byte for byte")

        # RE-RUN: idempotent; the held file now moves
        code, s, lines = go(td, apply=True, tracked=tracked)
        ck(code == 0 and s["moved"] == (1 if os.name == "nt" else 0) and s["planned"] == s["moved"],
           "a second run moves only what the first could not")

        # HARD FLOOR: a row asking for 0 h still waits 24 h (the 30 h file moves under it, the 20 h one does not)
        w(T("pintraj-live-20261106T000000Z.jsonl"), body, 20 * HOUR)
        zero = (Family("pintraj-live-*.jsonl", 0.0, "test"),)
        code, s, lines = go(td, apply=True, tracked=tracked, policy=zero)
        ck(s["moved"] == 1 and not os.path.exists(T("pintraj-live-20261104T101500Z.jsonl"))
           and os.path.exists(T("pintraj-live-20261106T000000Z.jsonl"))
           and s["kept"].get("modified * ago (never under 24 h)") == 1,
           "HARD FLOOR: nothing modified in the last 24 h moves, whatever the row says")

        # CONFLICT: a different archive of the same name keeps both; an identical one just drops the plain copy
        w(T("pinrun-live-20260909T000000Z.jsonl"), "plain\n", 70 * DAY)
        with gzip.open(os.path.join(ad, "pinrun-live-20260909T000000Z.jsonl.gz"), "wb") as fh:
            fh.write(b"other\n")
        code, s, lines = go(td, apply=True, tracked=tracked)
        ck(os.path.exists(T("pinrun-live-20260909T000000Z.jsonl")) and any("DIFFERENT" in x for x in lines),
           "a DIFFERENT archive of the same name: both kept, said loudly")
        with gzip.open(os.path.join(ad, "pinrun-live-20260909T000000Z.jsonl.gz"), "wb") as fh:
            fh.write(b"plain\n")
        code, s, lines = go(td, apply=True, tracked=tracked)
        ck(not os.path.exists(T("pinrun-live-20260909T000000Z.jsonl")) and s["moved"] == 1
           and any("identical archive already there" in x for x in lines),
           "an IDENTICAL archive (a run cut before its delete): the plain copy is dropped")

        # VERIFY FAILS: a pack that writes the wrong bytes keeps the plain file and fails the run
        w(T("pinrun-live-20260910T000000Z.jsonl"), "good\n", 70 * DAY)
        real = globals()["pack"]

        def bad_pack(src_fh, name, mtime, part):
            h, n = real(src_fh, name, mtime, part)
            with gzip.open(part, "wb") as fh:
                fh.write(b"bad!\n")
            return h, n
        globals()["pack"] = bad_pack
        try:
            code, s, lines = go(td, apply=True, tracked=tracked)
        finally:
            globals()["pack"] = real
        ck(code == 1 and os.path.exists(T("pinrun-live-20260910T000000Z.jsonl"))
           and not os.path.exists(os.path.join(ad, "pinrun-live-20260910T000000Z.jsonl.gz"))
           and not any(n.endswith(".part") for n in os.listdir(ad))
           and any("did not read back to the same bytes" in x for x in lines),
           "VERIFY FAILS: plain file kept, no archive left behind, exit 1, said why")

        # A LEFTOVER .part from a crash is removed; LOW DISK stops before writing
        with open(os.path.join(ad, "x.jsonl.gz.part"), "wb") as fh:
            fh.write(b"junk")
        code, s, lines = go(td, apply=True, tracked=tracked, disk=0.5e9)
        ck(code == 1 and os.path.exists(T("pinrun-live-20260910T000000Z.jsonl"))
           and not os.path.exists(os.path.join(ad, "x.jsonl.gz.part")) and any("too little" in x for x in lines),
           "LOW DISK: stops before writing (and a crash's leftover .part is cleared)")

        # LOCK: a fresh lock held by another run -> refuses; a stale one is taken over
        with open(os.path.join(ad, LOCK_NAME), "w") as fh:
            fh.write("1")
        os.utime(os.path.join(ad, LOCK_NAME), (now - 60, now - 60))
        code, s, lines = go(td, apply=True, tracked=tracked)
        ck(code == 2 and os.path.exists(T("pinrun-live-20260910T000000Z.jsonl")), "LOCK: a second run refuses")
        os.utime(os.path.join(ad, LOCK_NAME), (now - 7 * HOUR, now - 7 * HOUR))
        code, s, lines = go(td, apply=True, tracked=tracked)
        ck(code == 0 and not os.path.exists(T("pinrun-live-20260910T000000Z.jsonl")), "LOCK: a 7-hour-old lock is stale")

        # BUDGET: stops after the first file once over budget
        for i in range(3):
            w(T("pinrun-live-2026091%dT000000Z.jsonl" % (i + 1)), body, 70 * DAY)
        code, s, lines = go(td, apply=True, tracked=tracked, max_bytes=len(body) + 10)
        ck(s["moved"] == 1 and any("the budget is" in x for x in lines), "BUDGET: one run moves at most max_bytes")
    finally:
        shutil.rmtree(td, ignore_errors=True)
    selftest_more(ck, w, go, body, now, Disk)
    selftest_health(ck, now)

    # QUIET WINDOW: never start a file in a close's busy window
    slept = []
    ck(_wait_quiet(10, lambda: 1794050400.0, slept.append, lambda m: None) == 0 and not slept,
       "QUIET: 10 min before a close, a 10 s file starts at once")
    clock = [1794051000.0 - 60]                                                 # 11:29:00Z, a minute to the close

    def sl(s):
        slept.append(s)
        clock[0] += s
    ck(_wait_quiet(10, lambda: clock[0], sl, lambda m: None) == 90 and clock[0] == 1794051030.0,
       "QUIET: a minute before a close -> waits until 30 s after it")
    clock[0] = 1794051000.0 + 5
    slept.clear()
    ck(_wait_quiet(10, lambda: clock[0], sl, lambda m: None) == 25, "QUIET: 5 s after a close -> waits 25 s more")
    clock[0] = 1794051000.0 + 400
    ck(_wait_quiet(600, lambda: clock[0], sl, lambda m: None) > 0, "QUIET: a file too long to finish before the next "
                                                                   "close waits for it")

    # PROJECTION: baseline until 3 days of runs, then measured (the backlog run skipped)
    r, g, e, how = projection([], 26.3e9, now)
    ck(abs(r - 1.46) < 1e-9 and abs(e - 26.3 / 1.46) < 1e-6 and abs(g - (26.3 - 6) / 1.46) < 1e-6 and "baseline" in how,
       "PROJECTION: no history -> the 1.46 GB a week baseline, 18 weeks to empty")
    hist = [{"t": now, "free": 28e9}, {"t": now + DAY, "free": 27.9e9}, {"t": now + 8 * DAY, "free": 26.9e9}]
    r, g, e, how = projection(hist, 26.9e9, now + 8 * DAY)
    ck(abs(r - 1.0) < 1e-9 and abs(e - 26.9) < 1e-6 and "measured" in how,
       "PROJECTION: measured from the 2nd run on (1.0 GB in 7 days -> 1.0 GB a week)")
    ck(projection([{"t": 0, "free": 1}, {"t": 1, "free": 2}, {"t": 9 * DAY, "free": 5e9}], 5e9, 9 * DAY)[1] is None,
       "PROJECTION: a disk that is not filling has no date")
    ck(family_of("PINRUN-LIVE-20260908T062046Z.JSONL").min_age_s == 60 * DAY and family_of("ladder-live.jsonl") is None
       and family_of("ladder-live-orders.jsonl") is None, "family_of: case-blind; the ladder's logs have no rule")
    ck(all(f.min_age_s >= 2 * DAY for f in POLICY) and HARD_FLOOR_S >= DAY,
       "every POLICY row waits at least 48 h, and nothing under 24 h ever moves")
    if fails:
        print("log_rotate self-test: FAILED (%d) -- %s" % (len(fails), fails[0]))
        return 1
    print("log_rotate self-test: OK")
    return 0


def _share_all_holder(path):
    """Windows: open `path` for read and write SHARING read, write and delete (what a lenient writer does); returns a
    closer. The exclusive open must still refuse while it is held."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    cf = k32.CreateFileW
    cf.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                   wintypes.DWORD, wintypes.HANDLE]
    cf.restype = wintypes.HANDLE
    h = cf(os.path.abspath(path), 0x80000000 | 0x40000000, 0x1 | 0x2 | 0x4, None, 3, 0x80, None)
    if h is None or h == ctypes.c_void_p(-1).value:
        raise OSError("could not open the holder (Windows error %d)" % ctypes.get_last_error())
    return lambda: k32.CloseHandle(wintypes.HANDLE(h))


def selftest_more(ck, w, go, body, now, Disk):
    """The 11-07 review's gaps: the newest file of a family when it is old, newest by TIME not name, a short read, a
    holder that shares everything, the command line's default and --apply, and git_tracked against a real repo."""
    import tempfile
    td = tempfile.mkdtemp(prefix="log_rotate-more-")
    try:
        T = lambda n: os.path.join(td, n)                                       # noqa: E731
        # NEWEST, EVEN WHEN OLD: no paper arm has written for 3 days -- its last log is still the newest of its family
        w(T("pinrun-paper-20261020T000000Z.jsonl"), "{}\n", 5 * DAY)
        w(T("pinrun-paper-20261025T000000Z.jsonl"), "{}\n", 3 * DAY)
        # NEWEST BY TIME, NOT NAME: the older-named log is the one still written to
        w(T("pintraj-live-20261101T000000Z.jsonl"), body, 3 * DAY)
        w(T("pintraj-live-20261105T000000Z.jsonl"), body, 5 * DAY)
        code, s, lines = go(td, apply=True)
        ad = logfiles.archive_dir(td)
        ck(sorted(os.listdir(ad)) == ["pinrun-paper-20261020T000000Z.jsonl.gz", "pintraj-live-20261105T000000Z.jsonl.gz"]
           and os.path.exists(T("pinrun-paper-20261025T000000Z.jsonl")) and os.path.exists(T("pintraj-live-20261101T000000Z.jsonl"))
           and s["kept"].get("the newest of pinrun-paper-*.jsonl") == 1 and s["kept"].get("the newest of pintraj-live-*.jsonl") == 1,
           "NEWEST: a family's newest file stays even 3 days old, and newest means last WRITTEN, not the latest name: %s"
           % sorted(os.listdir(ad)))
        # SHORT READ: fewer bytes than the file holds -> nothing archived, plain kept, exit 1
        w(T("pinrun-paper-20261021T000000Z.jsonl"), body, 4 * DAY)
        real = globals()["pack"]

        def short_pack(src_fh, name, mtime, part):
            h, n = real(src_fh, name, mtime, part)
            return h, n - 1
        globals()["pack"] = short_pack
        try:
            code, s, lines = go(td, apply=True)
        finally:
            globals()["pack"] = real
        ck(code == 1 and os.path.exists(T("pinrun-paper-20261021T000000Z.jsonl"))
           and not os.path.exists(os.path.join(ad, "pinrun-paper-20261021T000000Z.jsonl.gz"))
           and not any(n.endswith(".part") for n in os.listdir(ad)) and any("read %d bytes of a %d-byte file"
                                                                             % (len(body) - 1, len(body)) in x
                                                                             for x in lines),
           "SHORT READ: a copy shorter than the file keeps the plain file, leaves no archive, exit 1")
        # A HOLDER THAT SHARES EVERYTHING (read, write and delete) still keeps the file (Windows)
        if os.name == "nt":
            close = _share_all_holder(T("pinrun-paper-20261021T000000Z.jsonl"))
            try:
                code, s, lines = go(td, apply=True)
            finally:
                close()
            ck(os.path.exists(T("pinrun-paper-20261021T000000Z.jsonl")) and s["moved"] == 0
               and any("held open by another process" in x for x in lines),
               "HELD OPEN by a writer that shares read, write AND delete: still kept (the exclusive open asks for no "
               "sharing at all)")
            code, s, lines = go(td, apply=True)
            ck(s["moved"] == 1 and not os.path.exists(T("pinrun-paper-20261021T000000Z.jsonl")), "...and moves once let go")
    finally:
        shutil.rmtree(td, ignore_errors=True)

    # THE COMMAND LINE: no flag is a dry run; --apply moves; both together refuse (real clock, no wait)
    td = tempfile.mkdtemp(prefix="log_rotate-main-")
    try:
        res = os.path.join(td, "results")
        os.makedirs(res)
        t = time.time()
        for n, age in (("pinrun-paper-20261001T000000Z.jsonl", 9 * DAY), ("pinrun-paper-20261002T000000Z.jsonl", 60)):
            with open(os.path.join(res, n), "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            os.utime(os.path.join(res, n), (t - age, t - age))
        snap = sorted(os.listdir(res))
        quiet = []
        printed = []
        ck(main(["--results", res], sleep_fn=quiet.append, out=printed.append) == 0 and sorted(os.listdir(res)) == snap
           and any(x.startswith("DRY RUN") for x in printed) and any("would move pinrun-paper-20261001T000000Z" in x
                                                                    for x in printed),
           "main([]): a DRY RUN by default -- nothing written (no archive, no log, no status)")
        ck(main(["--apply", "--dry-run", "--results", res], out=printed.append) == 2 and sorted(os.listdir(res)) == snap,
           "main(): --apply with --dry-run refuses")
        ck(main(["--apply", "--results", res], sleep_fn=quiet.append, out=printed.append) == 0
           and os.path.exists(os.path.join(logfiles.archive_dir(res), "pinrun-paper-20261001T000000Z.jsonl.gz"))
           and not os.path.exists(os.path.join(res, "pinrun-paper-20261001T000000Z.jsonl"))
           and os.path.exists(os.path.join(res, "pinrun-paper-20261002T000000Z.jsonl"))
           and health(res)["state"] in ("ok", "short"),
           "main(['--apply']): the old log moved, the newest kept, the status written")
    finally:
        shutil.rmtree(td, ignore_errors=True)

    # FINDING GIT: the PATH first, then the install folders (SYSTEM's PATH may not hold a per-user Git)
    td = tempfile.mkdtemp(prefix="log_rotate-findgit-")
    try:
        planted = os.path.join(td, "git.exe")
        with open(planted, "w") as fh:
            fh.write("")
        real_which = shutil.which
        shutil.which = lambda name, *a, **k: None
        try:
            ck(find_git(places=(os.path.join(td, "none.exe"), planted)) == planted
               and find_git(places=(os.path.join(td, "none.exe"),)) is None,
               "find_git: not on the PATH -> the first install folder that has git.exe; none at all -> None")
        finally:
            shutil.which = real_which
        ck(real_which("git") is None or find_git() == real_which("git"), "find_git: on the PATH -> that one")
    finally:
        shutil.rmtree(td, ignore_errors=True)

    # GIT, FOR REAL: a temp repository (git_tracked is what keeps 492 tracked pin logs in C:\kals-repo\results safe)
    git = find_git()
    if not git:
        print("  skip git_tracked against a real repository: no git on this machine (the fake-list checks above "
              "still ran)")
        return
    td = tempfile.mkdtemp(prefix="log_rotate-git-")
    try:
        res = os.path.join(td, "results")
        os.makedirs(os.path.join(res, "sub"))
        for n in ("pinrun-live-20260908T062046Z.jsonl", "pinrun-live-20261001T000000Z.jsonl", os.path.join("sub", "x.jsonl")):
            with open(os.path.join(res, n), "w", encoding="utf-8") as fh:
                fh.write("{}\n")
        try:
            for g in (["init", "-q"], ["add", "results/pinrun-live-20260908T062046Z.jsonl", "results/sub/x.jsonl"]):
                subprocess.run([git, "-C", td] + g, capture_output=True, timeout=60, check=True)
        except (OSError, subprocess.SubprocessError) as e:
            print("  skip git_tracked against a real repository: git could not make one here (%s)" % str(e)[:120])
            return
        got = git_tracked(td, res)
        ck(got == {"pinrun-live-20260908t062046z.jsonl"},
           "git_tracked, a real repository: the tracked log in results\\ (lower-cased), not the untracked one, not a "
           "subfolder's: %s" % sorted(got or []))
        ck(git_tracked(td, res, git=os.path.join(td, "no-such-git.exe")) is None, "git_tracked: a git that cannot run "
                                                                                  "-> None (nothing moves)")
        os.rename(os.path.join(td, ".git"), os.path.join(td, ".git-real"))
        with open(os.path.join(td, ".git"), "w") as fh:
            fh.write("gitdir: no-such-folder\n")                                   # a broken work tree
        ck(git_tracked(td, res) is None, "git_tracked: a broken .git -> None, never an empty set (which would make "
                                         "every tracked log movable)")
        code, s = run(results=res, repo=td, apply=True, now_fn=lambda: time.time() + 70 * DAY,
                             sleep_fn=lambda x: None, disk_fn=lambda p: Disk(0, 0, 100e9), out=lambda m: None)
        ck(s["moved"] == 0 and s["git"] == "unreadable" and os.path.exists(os.path.join(res, "pinrun-live-20260908T062046Z.jsonl")),
           "run() with that broken repository moves NOTHING and says git was unreadable")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def selftest_health(ck, now):
    """health(): what the phone alerts on, from planted status files and a real run."""
    import tempfile
    td = tempfile.mkdtemp(prefix="log_rotate-health-")
    try:
        def put(name, rec):
            with open(os.path.join(td, name), "w", encoding="utf-8") as fh:
                json.dump(rec, fh)

        def st(**kw):
            rec = {"t": now - 2 * HOUR, "state": "done", "started_t": now - 2 * HOUR, "finished_t": now - 2 * HOUR,
                   "ok": True, "errors": [], "git": "read", "moved": 3, "freed_mb": 900.0, "weeks_to_guard": 20.0,
                   "kept": {}}
            rec.update(kw)
            put(STATUS_NAME, rec)
            return health(td, now)["state"]
        ck(health(td, now) == {"state": "none", "installed_t": None, "bad": False}, "health: not installed -> none")
        put(INSTALLED_NAME, {"installed_t": now - HOUR})
        ck(health(td, now)["state"] == "waiting", "health: installed an hour ago, no run yet -> waiting")
        put(INSTALLED_NAME, {"installed_t": now - 40 * HOUR})
        h = health(td, now)
        ck(h["state"] == "never" and h["bad"], "health: installed 40 h ago and never ran -> never (bad)")
        ck(st() == "ok" and not health(td, now)["bad"], "health: a clean run 2 h ago -> ok")
        ck(st(finished_t=now - 40 * HOUR) == "stale", "health: no finished run for 40 h -> stale")
        ck(st(state="running", started_t=now - HOUR) == "running", "health: a run started an hour ago -> running")
        ck(st(state="running", started_t=now - 4 * HOUR) == "stuck", "health: running for 4 h -> stuck (it died part way)")
        ck(st(errors=["x.jsonl: could not write the archive"], ok=False) == "failed", "health: an error -> failed")
        ck(st(git="unreadable") == "nogit" and st(git=None, kept={"git could not say whether it tracks the file": 4})
           == "nogit", "health: git unreadable -> nogit (it moved nothing), from the new field or the old kept reason")
        ck(st(weeks_to_guard=5.0) == "short" and st(weeks_to_guard=None) == "ok",
           "health: 5 weeks to the 6 GB line -> short; no projection -> ok")
        with open(os.path.join(td, STATUS_NAME), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        ck(health(td, now)["state"] == "never", "health: an unreadable status file counts as no run")
        os.remove(os.path.join(td, STATUS_NAME))
        os.remove(os.path.join(td, INSTALLED_NAME))
        # a REAL run, then one that dies part way: the trace it leaves
        Disk = collections.namedtuple("Disk", "total used free")
        with open(os.path.join(td, "pinrun-paper-20261001T000000Z.jsonl"), "w", encoding="utf-8") as fh:
            fh.write("{}\n")
        kw = dict(results=td, repo=td, apply=True, now_fn=lambda: now, sleep_fn=lambda x: None,
                  disk_fn=lambda p: Disk(0, 0, 100e9), out=lambda m: None)
        run(tracked_fn=lambda r, d: set(), **kw)
        ck(health(td, now + HOUR)["state"] == "ok", "health after a real run: ok")
        run(tracked_fn=lambda r, d: None, **kw)
        ck(health(td, now + HOUR)["state"] == "nogit", "health after a real run git could not answer: nogit")

        def crash(r, d):
            raise MemoryError("planted")
        try:
            run(tracked_fn=crash, **kw)
            ck(False, "the planted crash did not raise")
        except MemoryError:
            pass
        with open(os.path.join(td, LOG_NAME), encoding="utf-8") as fh:
            tail = fh.read().splitlines()[-1]
        ck(health(td, now + HOUR)["state"] == "running" and health(td, now + 4 * HOUR)["state"] == "stuck"
           and tail.endswith("started (pid %d)" % os.getpid()),
           "a run that dies part way leaves its trace: the log's 'started' line, and a status the phone calls stuck "
           "after 3 h")
    finally:
        shutil.rmtree(td, ignore_errors=True)


def main(argv=None, **run_kw):
    """The command line. `run_kw` reaches run() (the self-test passes a sleep that does not wait)."""
    ap = argparse.ArgumentParser(description="gzip finished logs into results\\archive (dry run by default)")
    ap.add_argument("--apply", action="store_true", help="move the files (default: only say what would move)")
    ap.add_argument("--dry-run", action="store_true", help="the default: change nothing")
    ap.add_argument("--self-test", "--selftest", dest="selftest", action="store_true")
    ap.add_argument("--results", default=RESULTS)
    ap.add_argument("--max-mb", type=float, default=MAX_BYTES / 1e6)
    ap.add_argument("--git", default=None, help="the git to ask what it tracks (default: PATH, then Program Files)")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.apply and a.dry_run:
        run_kw.get("out", print)("--apply and --dry-run together: pick one")
        return 2
    run_kw.setdefault("tracked_fn", lambda repo, res: git_tracked(repo, res, a.git))
    code, _s = run(results=os.path.abspath(a.results), repo=os.path.dirname(os.path.abspath(a.results)),
                   apply=a.apply, max_bytes=int(a.max_mb * 1e6), **run_kw)
    return code


if __name__ == "__main__":
    sys.exit(main())
