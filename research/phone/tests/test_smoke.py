"""test_smoke.py -- research/phone/smoke.py's guard (v-tg-rebuild step 11): `pinphone.py --smoke` is read-only BY PROOF.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_smoke.py   (exit 0 = every test passed)
The smoke itself (every command on the real results folder) is the last stage of `pinphone.py --selftest`; this checks
the guard it runs under: a write anywhere but its temp folder, a network connection, a name lookup and an AWS / Telegram
urlopen are refused AND recorded (each fails the smoke); a process start is refused and listed (not a failure); the guard
puts everything back; repoint_results moves every results path of the loaded modules to a copy.
"""
import builtins
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import traceback
import urllib.request

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

from botdata import paths                                            # noqa: E402
from phone import smoke                                              # noqa: E402


def _refused(fn):
    try:
        fn()
    except PermissionError:
        return True
    return False


def test_guard_refuses_and_records():
    ok_dir = tempfile.mkdtemp(prefix="test_smoke_ok_")
    outside = tempfile.mkdtemp(prefix="test_smoke_out_")
    real = (builtins.open, os.remove, os.replace, socket.create_connection, urllib.request.urlopen, subprocess.Popen,
            shutil.copy2)
    g = smoke.Guard(ok_dir)
    g.install()
    try:
        with open(os.path.join(ok_dir, "fine.txt"), "w", encoding="utf-8") as fh:      # its own temp folder: allowed
            fh.write("x")
        assert _refused(lambda: open(os.path.join(outside, "x.txt"), "w", encoding="utf-8"))
        assert _refused(lambda: open(os.path.join(paths.DEFAULT_RESULTS, "pinphone.log"), "a", encoding="utf-8"))
        assert _refused(lambda: os.remove(os.path.join(outside, "nothing")))
        assert _refused(lambda: os.replace(os.path.join(ok_dir, "fine.txt"), os.path.join(outside, "moved.txt")))
        assert _refused(lambda: shutil.copy2(os.path.join(ok_dir, "fine.txt"), os.path.join(outside, "c.txt")))
        assert _refused(lambda: socket.create_connection(("api.elections.kalshi.com", 443), 1))
        assert _refused(lambda: socket.getaddrinfo("api.elections.kalshi.com", 443))
        assert _refused(lambda: urllib.request.urlopen("https://api.telegram.org/"))
        assert _refused(lambda: socket.socket().connect(("169.254.169.254", 80)))
        n_bad = len(g.violations)
        assert _refused(lambda: subprocess.Popen(["python", "-c", "0"]))
        assert len(g.violations) == n_bad and len(g.processes) == 1, "a process start is listed, not a violation"
        with open(os.path.join(ok_dir, "fine.txt"), encoding="utf-8") as fh:              # reading is never refused
            assert fh.read() == "x"
    finally:
        g.uninstall()
    assert n_bad == 9, g.violations
    assert not os.listdir(outside), "nothing was written outside the temp folder"
    assert (builtins.open, os.remove, os.replace, socket.create_connection, urllib.request.urlopen, subprocess.Popen,
            shutil.copy2) == real, "the guard put everything back"


def test_repoint_results_moves_every_results_path():
    import pinday
    import phone.shared as S
    saved = {(m, k): getattr(m, k) for m in (pinday, S) for k in ("RESULTS", "LIVE_GLOB" if m is pinday else "LOG")}
    old_paths = paths.RESULTS
    new = tempfile.mkdtemp(prefix="test_smoke_res_")
    try:
        n = smoke.repoint_results(new)
        assert n > 5 and paths.RESULTS == new
        assert S.RESULTS == new and S.LOG == os.path.join(new, "pinphone.log")
        assert S.UPDATE_FLAG == os.path.join(new, "pinphone.update") and pinday.RESULTS == new
        assert pinday.LIVE_GLOB.startswith(new + os.sep)
    finally:
        smoke.repoint_results(old_paths)            # the reverse move: every module's paths (and paths.RESULTS) back
        for (m, k), v in saved.items():
            setattr(m, k, v)
    assert paths.RESULTS == old_paths and pinday.RESULTS == saved[(pinday, "RESULTS")]


def main():
    tests = [(k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = []
    for k, fn in tests:
        try:
            fn()
            print("  ok   %s" % k, flush=True)
        except Exception:                                       # noqa: BLE001
            failed.append(k)
            print("  FAIL %s\n%s" % (k, traceback.format_exc()), flush=True)
    print("test_smoke: %d passed, %d failed" % (len(tests) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
