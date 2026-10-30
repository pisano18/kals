"""phone/smoke.py -- `pinphone.py --smoke`: every command rendered once on REAL data, read-only, before a deploy.

v-tg-rebuild step 11 (2026-10-30), DESIGN risk 1/3: a process that passes the self-test but crashes on the server's
own files leaves the phone dark. The smoke renders every declared command (the router's path: the paired chat, the
ledger refresh, the paused-bot answer, the command module) on the real results folder -- or on --results DIR, a copy --
and builds every picture's ChartCtx (nothing is drawn: no matplotlib, no memory spike on the server). It is the last
stage of `pinphone.py --selftest` (the /update gate).

READ-ONLY, PROVEN, NOT PROMISED. Before anything is imported from the phone:
  * KALS_TESTING=1 (botdata/paths.py's fence: no write under the live results\\ or C:\\kals);
  * an explicit guard on every write: builtins.open in a writing mode, os.remove / unlink / replace / rename / makedirs /
    mkdir / rmdir and shutil's copies refuse any path outside this run's temp folder (logged as a violation);
  * no network: socket connect / create_connection and urllib's urlopen refuse; no process: subprocess.Popen refuses
    (botdata.procs' WMI fallback and /bars' watcher scripts read as 'could not run'; the native process read is ctypes);
  * Kalshi: botdata.kalshi.set_readonly(True) -- botstats is served from botstats_cache.json, never refreshed or
    written; /funds' and botstats' getters are planted to refuse; AWS is the not-connected path;
  * pindesk.do_start / do_pause / do_stop are replaced by refusals, and no command that starts a worker (/pause /start
    /stop yes /update), writes the config (/pair) or the mute flag (/mute /unmute) is run.
Any violation, any exception out of a command, any 'this command failed to load' or 'Could not build' (except the
commands that need the network: /funds) FAILS the smoke: exit 1, 'pinphone smoke: FAILED -- ...'. Pass: exit 0,
'pinphone smoke: OK (N replies, M chart contexts, X s)'.
"""
import builtins
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request

NETWORK_ONLY = ("/funds", "/bank", "/accounts")          # their page is a live Kalshi read: 'Could not build' is fine
SKIP = ("/pair", "/mute", "/unmute")                     # they write state; the workers (runs_in_worker) are skipped too
EXTRA = ("/server help", "/stop")                        # /stop alone only explains (STOP_ASK); nothing is stopped
SMOKE_CHAT = 424242


class Guard:
    """The write / network / process guard. Everything refused is recorded in .violations."""

    def __init__(self, allow_dir):
        self.allow = os.path.normcase(os.path.abspath(allow_dir))
        self.violations = []                # writes, network: each one FAILS the smoke
        self.processes = []                 # refused process starts: shown, not a failure (/bars' watcher scripts)
        self.saved = []

    def _ok_path(self, p):
        try:
            p = os.path.normcase(os.path.abspath(os.fspath(p)))
        except TypeError:
            return True                                     # a file descriptor: not a path we can judge (never ours)
        return p == self.allow or p.startswith(self.allow + os.sep)

    def refuse(self, what):
        self.violations.append(what)
        raise PermissionError("pinphone --smoke: refused %s" % what)

    def put(self, obj, name, fn):
        self.saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, fn)

    def install(self):
        g = self
        real_open = builtins.open

        def open_(file, mode="r", *a, **k):
            if any(c in str(mode) for c in "wax+") and not g._ok_path(file):
                g.refuse("a write to %s (mode %s)" % (file, mode))
            return real_open(file, mode, *a, **k)
        self.put(builtins, "open", open_)
        for name in ("remove", "unlink", "replace", "rename", "rmdir", "mkdir", "makedirs", "utime"):
            real = getattr(os, name)

            def wrap(*a, _real=real, _name=name, **k):
                paths = [x for x in a[:2] if isinstance(x, (str, bytes, os.PathLike))]
                if any(not g._ok_path(x) for x in paths):
                    g.refuse("os.%s%r" % (_name, tuple(paths)))
                return _real(*a, **k)
            self.put(os, name, wrap)
        for name in ("copy", "copy2", "copyfile", "move", "rmtree"):
            real = getattr(shutil, name)

            def wrap_sh(*a, _real=real, _name=name, **k):
                dst = a[1] if _name != "rmtree" and len(a) > 1 else a[0] if a else None
                if dst is not None and not g._ok_path(dst):
                    g.refuse("shutil.%s to %s" % (_name, dst))
                return _real(*a, **k)
            self.put(shutil, name, wrap_sh)

        def no_net(*a, **k):
            g.refuse("a network connection %r" % (a[:1],))
        self.put(socket, "create_connection", no_net)
        self.put(socket, "getaddrinfo", no_net)
        self.put(socket.socket, "connect", lambda self_, *a, **k: no_net(*a))
        self.put(socket.socket, "connect_ex", lambda self_, *a, **k: no_net(*a))
        self.put(urllib.request, "urlopen", no_net)

        class NoPopen:
            def __init__(self_, *a, **k):
                g.processes.append(repr(a[:1])[:200])
                raise PermissionError("pinphone --smoke: refused a process %r" % (a[:1],))
        self.put(subprocess, "Popen", NoPopen)

    def uninstall(self):
        for obj, name, v in reversed(self.saved):
            setattr(obj, name, v)
        self.saved = []


def _refusing_getter(path, params=None, auth=True):
    return 599, "pinphone --smoke: no Kalshi request (read-only run)"


def _refuse_aws(method, url, headers=None, body=None, timeout=None):
    raise PermissionError("pinphone --smoke: no AWS request")


def repoint_results(new):
    """Every loaded research module's path constant under the real results folder -> the same path under `new` (the
    golden fixture's copy): RESULTS, LOG, UPDATE_FLAG, the ledger file, log globs ... (pindesk, pinday, pinledger,
    pinflat, pinbrief, botdata.paths, phone.shared ...). Paths bound as default arguments are not moved (read-only
    anyway)."""
    from botdata import paths
    research = os.path.normcase(paths.RESEARCH)
    olds = {os.path.normcase(paths.RESULTS), os.path.normcase(paths.LIVE_RESULTS)}
    paths.set_results(new)
    moved = 0
    for m in list(sys.modules.values()):
        f = getattr(m, "__file__", None)
        if not f or not os.path.normcase(os.path.abspath(f)).startswith(research + os.sep):
            continue
        for k, v in list(vars(m).items()):
            if not isinstance(v, str) or k.startswith("__"):
                continue
            nv = os.path.normcase(v)
            for o in olds:
                if nv == o or nv.startswith(o + os.sep):
                    setattr(m, k, new + v[len(o):])
                    moved += 1
                    break
    return moved


def main(argv=()):
    argv = list(argv)
    t_start = time.time()
    results = None
    if "--results" in argv:
        i = argv.index("--results")
        results = os.path.abspath(argv[i + 1]) if i + 1 < len(argv) else None
        if not results or not os.path.isdir(results):
            print("pinphone smoke: FAILED -- --results needs a folder")
            return 2
    os.environ["KALS_TESTING"] = "1"
    sys.dont_write_bytecode = True                          # an import here writes no .pyc
    tmp = tempfile.mkdtemp(prefix="pinphone_smoke_")
    guard = Guard(tmp)
    guard.install()
    bad = []
    try:
        import pindesk
        from botdata import kalshi
        from phone import shared as S
        if results:
            repoint_results(results)
        S.LOG = os.path.join(tmp, "pinphone.log")              # every log line of the run stays in the temp folder
        kalshi.set_readonly(True)
        for name in ("do_start", "do_pause", "do_stop"):
            guard.put(pindesk, name, lambda *a, _n=name, **k: guard.refuse("pindesk.%s" % _n))
        import botstats
        guard.put(botstats, "default_getter", lambda *a, **k: _refusing_getter)
        from phone import app, router
        from phone.transport import FakeTelegram
        failed = router.discover()
        for m, e in sorted(failed.items()):
            bad.append("%s failed to load: %s" % (m, e))
        led = pindesk.Ledger(results) if results else pindesk.Ledger()
        ph = app.Phone({"chat_id": SMOKE_CHAT, "secret": "smoke"}, FakeTelegram(), ledger=led)
        ph.bs_getter = ph.funds_getter = _refusing_getter
        ph.aws_http = _refuse_aws
        ph.ping_fn = lambda: {"host": S.KALSHI_HOST, "ms": [], "ip": None, "dns_ms": None, "t": time.time(),
                              "err": "not measured (pinphone --smoke: no network)"}
        ph.ledger.refresh()
        texts = []
        for c in router.commands():
            if c.runs_in_worker or c.name in SKIP:
                continue
            texts.append(c.name)
        texts += [t for t in EXTRA if t not in texts]
        n = 0
        for text in texts:
            t0 = time.time()
            try:
                r = ph.handle(SMOKE_CHAT, text)
            except Exception as e:                              # noqa: BLE001
                bad.append("%s raised %s: %s" % (text, type(e).__name__, e))
                print("  FAIL %-12s raised %s" % (text, traceback.format_exc()[-600:]), flush=True)
                continue
            n += 1
            body = "" if r is None else str(r)
            words = body if not getattr(r, "is_html", False) else S.html_to_plain(r)
            parts = S.split_html(r) if getattr(r, "is_html", False) else S.split_text(body)
            why = None
            if r is None:
                why = "no reply"
            elif "this command failed to load" in words:
                why = "failed to load"
            elif words.startswith("Could not build") and text not in NETWORK_ONLY:
                why = words.split("\n")[0][:160]
            elif getattr(r, "is_html", False) and any(S.tg_html_problems(p) for p in parts):
                why = "invalid Telegram HTML"
            if why:
                bad.append("%s: %s" % (text, why))
            print("  %s %-12s %6d chars %2d msg %5.1f s%s" % ("FAIL" if why else "ok  ", text, len(body), len(parts),
                                                             time.time() - t0, ("  -- " + why) if why else ""),
                  flush=True)
        # every picture's context (what the drawing thread would get), without drawing
        import tgcharts
        kinds = sorted(set(router.chart_kinds().values()))
        for kind in kinds:
            try:
                ph._chart_ctx(kind, tgcharts)
            except Exception as e:                              # noqa: BLE001
                bad.append("chart context %s raised %s: %s" % (kind, type(e).__name__, e))
        # the alerts: the first tick learns the state and sends nothing
        try:
            ph.alerts_tick()
        except Exception as e:                                  # noqa: BLE001
            bad.append("alerts tick raised %s: %s" % (type(e).__name__, e))
        bad += ["guard: %s" % v for v in guard.violations]
        if guard.processes:
            print("  (refused %d process start(s), not a failure: %s)" % (len(guard.processes),
                                                                     "; ".join(guard.processes)[:300]), flush=True)
        secs = time.time() - t_start
        if bad:
            print("pinphone smoke: FAILED -- %s" % "; ".join(bad)[:1500], flush=True)
            return 1
        print("pinphone smoke: OK (%d replies, %d chart contexts, %.1f s%s)" % (
            n, len(kinds), secs, (", results %s" % results) if results else ""), flush=True)
        return 0
    finally:
        guard.uninstall()
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:                                       # noqa: BLE001
            pass


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
