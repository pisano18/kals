"""The golden harness's fence: file-system virtualisation, write guard, network / subprocess guards, frozen clock and a
thread registry. Installed BEFORE any code under test is imported. Never imported by production code.

Two modes:
  trace   (capture.py, on the server): paths are left alone except an explicit map (the shifted botstats cache);
          every access under the traced roots is RECORDED (with the lowest byte offset read, so a log read only for
          its tail can be copied as a tail); every write outside the allowed folder RAISES.
  replay  (gl_child.py): every real data path (the tree's results/, C:\\kals-repo\\results, boot_all.ps1, C:\\kals,
          fixture copies of research data files) is transparently REDIRECTED into the world's scratch copy; a read
          of any other repo / C:\\kals / live path RAISES and is recorded as a fence event (the case shows it).
"""
import builtins
import datetime as _dt
import io
import ntpath
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request


class FenceError(PermissionError):
    pass


def norm(p):
    """normcased absolute path of a str / bytes / PathLike, or None for an fd or anything else."""
    if isinstance(p, int):
        return None
    try:
        p = os.fspath(p)
    except TypeError:
        return None
    if isinstance(p, bytes):
        p = os.fsdecode(p)
    if not isinstance(p, str) or not p:
        return None
    return ntpath.abspath(p)


def _under(nc, prefix):
    return nc == prefix or nc.startswith(prefix.rstrip("\\") + "\\")


# ======================================================================================================== the fence
class Fence:
    def __init__(self, mode, maps=(), allow_write=(), allow_read=(), deny=(), trace_roots=(), trace_skip=()):
        assert mode in ("trace", "replay")
        self.mode = mode
        # (normcased real prefix, real prefix as given, target prefix) -- longest first
        self.maps = sorted(((ntpath.normcase(ntpath.abspath(a)), b) for a, b in maps), key=lambda m: -len(m[0]))
        self.allow_write = [ntpath.normcase(ntpath.abspath(p)) for p in allow_write]
        self.allow_read = [ntpath.normcase(ntpath.abspath(p)) for p in allow_read]
        # raw prefixes: "c:\\kals\\" (also matches "c:\\kals" itself), "c:\\kals-live" (matches c:\\kals-live-0925n)
        self.deny = [ntpath.normcase(p) for p in deny]
        self.trace_roots = [ntpath.normcase(ntpath.abspath(p)) for p in trace_roots]
        self.trace_skip = [ntpath.normcase(ntpath.abspath(p)) for p in trace_skip]
        self.lock = threading.RLock()
        self.events = []            # this case's fence events (violations, network, subprocess ...)
        self.touched = {}           # trace mode: real path -> {"ops": set, "lo": int|None, "hi": int|None}
        self.local = threading.local()
        self.track_root = None       # replay: the scratch copy; files written there are restored after each case
        self.track_skip = ("\\pinphone.log",)   # appended by every say(); nothing reads it back
        self.saved = {}
        self.standins = set()        # replay: normcased scratch paths of 0-byte stand-ins (a read of one is noted)
        self.case = "(setup)"         # the case running now (trace mode: who touched what)
        self.stub_selftest = True   # subprocess.run([... '--selftest']) answers exit 0 (the /update gate), recorded

    # ---- bookkeeping ----
    def event(self, kind, detail):
        with self.lock:
            self.events.append({"kind": kind, "detail": str(detail)})

    def take_events(self):
        with self.lock:
            ev, self.events = self.events, []
        return ev

    def _note(self, real_abs, op, lo=None, n=None):
        nc = ntpath.normcase(real_abs)
        if not any(_under(nc, r) for r in self.trace_roots) or any(_under(nc, r) for r in self.trace_skip):
            return
        with self.lock:
            t = self.touched.setdefault(real_abs, {"ops": set(), "lo": None, "hi": None, "cases": set()})
            t["ops"].add(op)
            t["cases"].add(self.case)
            if lo is not None:
                t["lo"] = lo if t["lo"] is None else min(t["lo"], lo)
                end = lo + (n or 0)
                t["hi"] = end if t["hi"] is None else max(t["hi"], end)

    # ---- path resolution ----
    def resolve(self, p, write, op):
        """The path the OS call should use, or FenceError."""
        out = self._resolve(p, write, op)
        if write and self.track_root and out is not None and not isinstance(out, int):
            self._save_before_write(out)
        return out

    # ---- replay: a file a case writes in the scratch copy is put back after the case (cases stay independent) ----
    def _save_before_write(self, path):
        a = norm(path)
        if a is None:
            return
        nc = ntpath.normcase(a)
        if not _under(nc, self.track_root) or nc in self.saved or any(nc.endswith(x) for x in self.track_skip):
            return
        try:
            st = ORIG["os.stat"](a)
            with ORIG["open"](a, "rb") as fh:
                self.saved[nc] = (a, fh.read(), st.st_atime, st.st_mtime)
        except FileNotFoundError:
            self.saved[nc] = (a, None, None, None)
        except OSError:
            pass

    def restore_writes(self):
        """Put back every file written since the last call; remove the ones created. Returns their names."""
        names = []
        for nc, (a, data, at, mt) in sorted(self.saved.items()):
            try:
                if data is None:
                    if ORIG["path.exists"](a):
                        ORIG["os.remove"](a)
                else:
                    with ORIG["open"](a, "wb") as fh:
                        fh.write(data)
                    ORIG["os.utime"](a, (at, mt))
                names.append(os.path.basename(a))
            except OSError:
                pass
        self.saved = {}
        return names

    def _resolve(self, p, write, op):
        a = norm(p)
        if a is None:
            return p
        nc = ntpath.normcase(a)
        for pre, target in self.maps:
            if _under(nc, pre):
                out = target + a[len(pre):]
                if self.mode == "trace":
                    self._note(a, op + ("(mapped)" if not write else ""))
                elif not write and op == "open" and self.standins and ntpath.normcase(out) in self.standins:
                    self.event("standin_read", a)
                if write and self.mode == "trace" and not any(_under(ntpath.normcase(out), w) for w in self.allow_write):
                    self.event("write_denied", a)
                    raise FenceError("golden fence: write refused: %s" % a)
                return out
        if any(_under(nc, w) for w in self.allow_write):
            return a
        if write:
            self.event("write_denied", a)
            raise FenceError("golden fence: write refused: %s" % a)
        if self.mode == "trace":
            self._note(a, op)
            return a
        if any(_under(nc, r) for r in self.allow_read):
            return a
        if any(nc == d.rstrip("\\") or nc.startswith(d) for d in self.deny):
            self.event("read_denied", a)
            raise FenceError("golden fence: read outside the fixture refused: %s" % a)
        return a

    # ---- net / subprocess permission (capture's Kalshi recorder and ping only) ----
    def net_allowed(self):
        return getattr(self.local, "net", 0) > 0

    class _Allow:
        def __init__(self, f):
            self.f = f

        def __enter__(self):
            self.f.local.net = getattr(self.f.local, "net", 0) + 1

        def __exit__(self, *a):
            self.f.local.net -= 1

    def allow_net(self):
        return Fence._Allow(self)


# ======================================================================================================== tracing reads
class _TracingFileIO(io.FileIO):
    """FileIO that tells the fence the lowest byte offset each read started at (trace mode only)."""

    def _gl_init(self, fence, real):
        self._gl_f, self._gl_p = fence, real

    def readinto(self, b):
        pos = self.tell()
        n = super().readinto(b)
        self._gl_f._note(self._gl_p, "read", pos, n or 0)
        return n

    def readall(self):
        pos = self.tell()
        d = super().readall()
        self._gl_f._note(self._gl_p, "read", pos, len(d or b""))
        return d

    def read(self, size=-1):
        pos = self.tell()
        d = super().read(size)
        self._gl_f._note(self._gl_p, "read", pos, len(d or b""))
        return d


def _traced_open(fence, path, mode, buffering, encoding, errors, newline):
    raw = _TracingFileIO(path, "r")
    raw._gl_init(fence, norm(path))
    if "b" in mode and buffering == 0:
        return raw
    buf = io.BufferedReader(raw, buffering if buffering and buffering > 1 else io.DEFAULT_BUFFER_SIZE)
    if "b" in mode:
        return buf
    t = io.TextIOWrapper(buf, encoding=encoding, errors=errors, newline=newline)
    try:
        t.mode = mode
    except (AttributeError, TypeError):
        pass
    return t


# ======================================================================================================== scandir proxy
class _Entry:
    def __init__(self, e, base):
        self._e = e
        self.name = e.name
        self.path = os.path.join(base, e.name) if isinstance(base, str) else e.path

    def is_dir(self, *, follow_symlinks=True):
        return self._e.is_dir(follow_symlinks=follow_symlinks)

    def is_file(self, *, follow_symlinks=True):
        return self._e.is_file(follow_symlinks=follow_symlinks)

    def is_symlink(self):
        return self._e.is_symlink()

    def is_junction(self):
        return getattr(self._e, "is_junction", lambda: False)()

    def stat(self, *, follow_symlinks=True):
        return self._e.stat(follow_symlinks=follow_symlinks)

    def inode(self):
        return self._e.inode()

    def __fspath__(self):
        return self.path

    def __repr__(self):
        return "<DirEntry %r>" % self.name


class _ScanIt:
    def __init__(self, it, base):
        self._it, self._base = it, base

    def __iter__(self):
        return self

    def __next__(self):
        return _Entry(next(self._it), self._base)

    def close(self):
        self._it.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


# ======================================================================================================== install
ORIG = {}


def install(fence):
    """Patch builtins / os / io / shutil / socket / subprocess / threading for `fence`. Idempotent per process."""
    if ORIG:
        raise RuntimeError("fence already installed")
    f = fence
    o = ORIG
    o["open"] = io.open
    for name in ("open", "stat", "lstat", "listdir", "scandir", "remove", "unlink", "rename", "replace", "mkdir",
                 "rmdir", "utime", "access", "chmod", "truncate", "startfile", "system", "popen"):
        if hasattr(os, name):
            o["os." + name] = getattr(os, name)
    for name in ("exists", "lexists", "isfile", "isdir", "islink", "getsize", "getmtime", "getatime", "getctime"):
        o["path." + name] = getattr(os.path, name)

    def _open(file, mode="r", buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
        if isinstance(file, int):
            return o["open"](file, mode, buffering, encoding, errors, newline, closefd, opener)
        write = any(c in mode for c in "wax+")
        p = f.resolve(file, write, "open")
        if (f.mode == "trace" and not write and opener is None and p is not None and
                any(_under(ntpath.normcase(norm(p) or ""), r) for r in f.trace_roots) and
                not any(_under(ntpath.normcase(norm(p) or ""), r) for r in f.trace_skip)):
            return _traced_open(f, p, mode, buffering, encoding, errors, newline)
        return o["open"](p, mode, buffering, encoding, errors, newline, closefd, opener)

    builtins.open = _open
    io.open = _open

    def _os_open(path, flags, mode=0o777, *, dir_fd=None):
        write = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC))
        return o["os.open"](f.resolve(path, write, "os.open"), flags, mode, dir_fd=dir_fd)
    os.open = _os_open

    def _wrap1(name, write, op):
        fn = o["os." + name]

        def w(path, *a, **k):
            if isinstance(path, int):
                return fn(path, *a, **k)
            return fn(f.resolve(path, write, op), *a, **k)
        w.__name__ = name
        return w
    os.stat = _wrap1("stat", False, "stat")
    os.lstat = _wrap1("lstat", False, "stat")
    os.remove = _wrap1("remove", True, "remove")
    os.unlink = _wrap1("unlink", True, "remove")
    os.mkdir = _wrap1("mkdir", True, "mkdir")
    os.rmdir = _wrap1("rmdir", True, "rmdir")
    os.utime = _wrap1("utime", True, "utime")
    os.chmod = _wrap1("chmod", True, "chmod")
    if "os.truncate" in o:
        os.truncate = _wrap1("truncate", True, "truncate")

    def _access(path, mode, *a, **k):
        if isinstance(path, int):
            return o["os.access"](path, mode, *a, **k)
        try:
            return o["os.access"](f.resolve(path, bool(mode & os.W_OK), "access"), mode, *a, **k)
        except FenceError:
            return False
    os.access = _access

    def _listdir(path="."):
        if isinstance(path, int):
            return o["os.listdir"](path)
        r = o["os.listdir"](f.resolve(path, False, "list"))
        return r
    os.listdir = _listdir

    def _scandir(path="."):
        if isinstance(path, int):
            return o["os.scandir"](path)
        it = o["os.scandir"](f.resolve(path, False, "list"))
        return _ScanIt(it, os.fspath(path) if not isinstance(path, bytes) else None)
    os.scandir = _scandir

    def _two(name):
        fn = o["os." + name]

        def w(src, dst, *a, **k):
            return fn(f.resolve(src, True, name), f.resolve(dst, True, name), *a, **k)
        return w
    os.rename = _two("rename")
    os.replace = _two("replace")

    def _pathq(name, default):
        fn = o["path." + name]

        def w(path):
            if isinstance(path, int):
                return fn(path)
            try:
                return fn(f.resolve(path, False, "stat"))
            except FenceError:
                return default
        w.__name__ = name
        return w
    for name in ("exists", "lexists", "isfile", "isdir", "islink"):
        setattr(os.path, name, _pathq(name, False))

    def _pathv(name):
        fn = o["path." + name]

        def w(path):
            if isinstance(path, int):
                return fn(path)
            return fn(f.resolve(path, False, "stat"))
        w.__name__ = name
        return w
    for name in ("getsize", "getmtime", "getatime", "getctime"):
        setattr(os.path, name, _pathv(name))

    # ---- processes ----
    def _no_proc(*a, **k):
        f.event("subprocess_refused", repr(a[:1])[:300])
        raise FenceError("golden fence: no process may be started: %r" % (a[:1],))
    for name in ("startfile", "system", "popen"):
        if "os." + name in o:
            setattr(os, name, _no_proc)
    o["os.kill"] = os.kill

    def _kill(pid, sig):                                # on Windows even signal 0 is TerminateProcess: never
        f.event("kill_refused", "%s %s" % (pid, sig))
        raise FenceError("golden fence: no process may be signalled: %s" % pid)
    os.kill = _kill
    o["subprocess.Popen"] = subprocess.Popen
    o["subprocess.run"] = subprocess.run

    class _Popen(subprocess.Popen):
        def __init__(self, args, *a, **k):
            f.event("subprocess_refused", repr(args)[:300])
            raise FenceError("golden fence: no process may be started: %r" % (args,))
    subprocess.Popen = _Popen

    def _run(args, *a, **k):
        if f.stub_selftest and isinstance(args, (list, tuple)) and "--selftest" in [str(x) for x in args]:
            f.event("subprocess_stubbed", " ".join(os.path.basename(str(x)) if i else "python"
                                                   for i, x in enumerate(args)))
            return subprocess.CompletedProcess(args, 0, "", "")
        return _no_proc(args)
    subprocess.run = _run
    subprocess.call = subprocess.check_call = subprocess.check_output = subprocess.getoutput = \
        subprocess.getstatusoutput = lambda *a, **k: _no_proc(*a)

    # ---- network ----
    o["socket.connect"] = socket.socket.connect
    o["socket.connect_ex"] = socket.socket.connect_ex
    o["socket.getaddrinfo"] = socket.getaddrinfo
    o["socket.create_connection"] = socket.create_connection
    o["urlopen"] = urllib.request.urlopen

    def _guard_net(what):
        f.event("network_refused", what)
        raise FenceError("golden fence: no network: %s" % what)

    def _connect(self, addr):
        if f.net_allowed():
            return o["socket.connect"](self, addr)
        return _guard_net("connect %r" % (addr,))

    def _connect_ex(self, addr):
        if f.net_allowed():
            return o["socket.connect_ex"](self, addr)
        return _guard_net("connect %r" % (addr,))

    def _gai(host, *a, **k):
        if f.net_allowed():
            return o["socket.getaddrinfo"](host, *a, **k)
        return _guard_net("getaddrinfo %s" % host)

    def _cc(address, *a, **k):
        if f.net_allowed():
            return o["socket.create_connection"](address, *a, **k)
        return _guard_net("create_connection %r" % (address,))

    def _urlopen(url, *a, **k):
        if f.net_allowed():
            return o["urlopen"](url, *a, **k)
        u = getattr(url, "full_url", url)
        return _guard_net("urlopen %s" % str(u).split("?")[0])
    socket.socket.connect = _connect
    socket.socket.connect_ex = _connect_ex
    socket.getaddrinfo = _gai
    socket.create_connection = _cc
    urllib.request.urlopen = _urlopen

    # ---- threads: every thread a case starts is joined before its result is written ----
    o["Thread.start"] = threading.Thread.start
    f.threads = []

    def _start(self):
        with f.lock:
            f.threads.append(self)
        return o["Thread.start"](self)
    threading.Thread.start = _start


def join_threads(fence, timeout=120.0):
    """Wait for every thread started since the last call. Returns the names of any still running."""
    left = []
    t_end = time.monotonic() + timeout
    while True:
        with fence.lock:
            ts, fence.threads = list(fence.threads), []
        if not ts:
            break
        for t in ts:
            t.join(max(0.0, t_end - time.monotonic()))
            if t.is_alive():
                left.append(t.name)
    return left


# ======================================================================================================== the clock
class Clock:
    def __init__(self, t):
        self.T = float(t)
        self.slept = 0.0


def install_clock(clock):
    """time.time / time_ns / localtime() / gmtime() / ctime() / strftime(fmt) / datetime.now() all read clock.T;
    time.sleep returns at once (the total is kept). time.monotonic / perf_counter stay real (deadlines only)."""
    o = ORIG
    o["time.time"], o["time.time_ns"] = time.time, time.time_ns
    o["time.localtime"], o["time.gmtime"], o["time.ctime"], o["time.asctime"] = \
        time.localtime, time.gmtime, time.ctime, time.asctime
    o["time.strftime"], o["time.sleep"] = time.strftime, time.sleep
    time.time = lambda: clock.T
    time.time_ns = lambda: int(clock.T * 1e9)
    time.localtime = lambda secs=None: o["time.localtime"](clock.T if secs is None else secs)
    time.gmtime = lambda secs=None: o["time.gmtime"](clock.T if secs is None else secs)
    time.ctime = lambda secs=None: o["time.ctime"](clock.T if secs is None else secs)
    time.asctime = lambda t=None: o["time.asctime"](o["time.localtime"](clock.T) if t is None else t)
    time.strftime = lambda fmt, t=None: o["time.strftime"](fmt, o["time.localtime"](clock.T) if t is None else t)

    def _sleep(s):
        clock.slept += max(0.0, float(s or 0))
    time.sleep = _sleep

    real_dt, real_date = _dt.datetime, _dt.date

    class _MetaDT(type(real_dt)):
        def __instancecheck__(cls, obj):
            return isinstance(obj, real_dt)

        def __subclasscheck__(cls, sub):
            return issubclass(sub, real_dt)

    class _MetaD(type(real_date)):
        def __instancecheck__(cls, obj):
            return isinstance(obj, real_date)

        def __subclasscheck__(cls, sub):
            return issubclass(sub, real_date)

    class FrozenDateTime(real_dt, metaclass=_MetaDT):
        @classmethod
        def now(cls, tz=None):
            return real_dt.fromtimestamp(clock.T, tz)

        @classmethod
        def utcnow(cls):
            return real_dt.fromtimestamp(clock.T, _dt.timezone.utc).replace(tzinfo=None)

        @classmethod
        def today(cls):
            return real_dt.fromtimestamp(clock.T)

    class FrozenDate(real_date, metaclass=_MetaD):
        @classmethod
        def today(cls):
            return real_date.fromtimestamp(clock.T)

    _dt.datetime = FrozenDateTime
    _dt.date = FrozenDate


def real_time():
    return ORIG.get("time.time", time.time)()
