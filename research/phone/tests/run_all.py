"""run_all.py -- `pinphone.py --selftest`: EVERY phone test, then the smoke. The /update gate (v-tg-rebuild step 11).

The running phone (the OLD code) runs exactly [sys.executable, "-u", research\\pinphone.py, "--selftest"] -- then the
same for botstats.py -- with cwd = the repo root, 900 s each, capture_output, and keeps its old code unless both exit 0.
So this keeps that contract: exit 0 and the last line 'pinphone selftest: OK' only when every stage passed; else exit 1
and 'pinphone selftest: FAILED -- <stages>' (SystemExit). It must finish well under 900 s on the server (measured: see
the timing line it prints).

STAGES, each its own process (a test's patches never leak into the next), run two at a time:
  1. legacy checks      phone/tests/legacy_selftest.py -- pinphone.py's own 2,400-line self-test, on the rebuilt phone
  2. phone tests        phone/tests/test_*.py (every command module against the frozen legacy phone, the router, the
                        alerts, the chart queue, the controls, /update, the launcher's fallback ...)
  3. registry           bots/tests/test_registry.py
  4. botdata            botstats.py --selftest (research/botdata/tests)
  5. charts             phone/charts/tests/run.py (every picture from planted data; skipped, not failed, without
                        matplotlib)
  6. fallback           pinphone_legacy.py --selftest: the launcher's fallback still runs with today's modules
  7. smoke              pinphone.py --smoke: every command on the REAL results folder, read-only (phone/smoke.py)
Every stage runs with KALS_TESTING=1 (no live file is written), PYTHONIOENCODING=utf-8, OPENBLAS_NUM_THREADS=1.
"""
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

TESTS = os.path.dirname(os.path.abspath(__file__))
PHONE = os.path.dirname(TESTS)
RESEARCH = os.path.dirname(PHONE)
REPO = os.path.dirname(RESEARCH)
STAGE_TIMEOUT_S = 600
JOBS = 2


def stages():
    """[(name, argv)] in the order they are reported."""
    py = [sys.executable, "-u"]
    out = [("legacy checks", py + [os.path.join(TESTS, "legacy_selftest.py")])]
    for fn in sorted(os.listdir(TESTS)):
        if fn.startswith("test_") and fn.endswith(".py"):
            out.append(("phone/tests/" + fn[:-3], py + [os.path.join(TESTS, fn)]))
    out += [("bots/tests/test_registry", py + [os.path.join(RESEARCH, "bots", "tests", "test_registry.py")]),
            ("botdata (botstats.py --selftest)", py + [os.path.join(RESEARCH, "botstats.py"), "--selftest"]),
            ("charts", py + [os.path.join(PHONE, "charts", "tests", "run.py")]),
            ("fallback (pinphone_legacy.py --selftest)", py + [os.path.join(RESEARCH, "pinphone_legacy.py"), "--selftest"])]
    return out


def _env():
    e = dict(os.environ)
    e.update(KALS_TESTING="1", PYTHONIOENCODING="utf-8", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
             MKL_NUM_THREADS="1", MPLBACKEND="Agg", KALS_SELFTESTED="1")
    return e


def run_stage(name, argv):
    t0 = time.time()
    try:
        r = subprocess.run(argv, cwd=REPO, env=_env(), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=STAGE_TIMEOUT_S)
        rc, out = r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired as e:
        rc, out = "timeout", "%s\n(timed out after %d s)" % (e.stdout or "", STAGE_TIMEOUT_S)
    except Exception as e:                                      # noqa: BLE001
        rc, out = "error", "could not run: %s" % e
    return name, rc, out, time.time() - t0


def _say(s):
    try:
        print(s, flush=True)
    except UnicodeEncodeError:
        print(s.encode("ascii", "backslashreplace").decode("ascii"), flush=True)


def main():
    os.environ["KALS_TESTING"] = "1"
    t0 = time.time()
    failed = []
    with ThreadPoolExecutor(JOBS) as ex:
        results = list(ex.map(lambda s: run_stage(*s), stages()))
    results.append(run_stage("smoke (pinphone.py --smoke)", [sys.executable, "-u", os.path.join(RESEARCH, "pinphone.py"),
                                                              "--smoke"]))
    for name, rc, out, secs in results:
        last = [x for x in out.strip().splitlines() if x.strip()][-1:] or [""]
        if rc == 0:
            _say("  ok   %-44s %5.1f s  %s" % (name, secs, last[0][:110]))
        else:
            failed.append(name)
            _say("  FAIL %-44s %5.1f s  exit %s\n%s" % (name, secs, rc, "\n".join(out.strip().splitlines()[-60:])))
    _say("pinphone selftest: %d stages, %d failed, %.1f s" % (len(results), len(failed), time.time() - t0))
    if failed:
        raise SystemExit("pinphone selftest: FAILED -- " + ", ".join(failed))
    print("pinphone selftest: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
