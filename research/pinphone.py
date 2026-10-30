#!/usr/bin/env python3
r"""pinphone.py -- the bot in your pocket: the Telegram phone link (the LAUNCHER boot_all.ps1 starts).

v-tg-rebuild step 11 (2026-10-30). The phone lives in research/phone/: app.py (the runtime: poll loop, ticks, hello),
router.py + commands/ (every reply), alerts.py, chartq.py (pictures), shared.py (the helpers). This file only starts it:

    python research/pinphone.py                  # run (needs C:\kals\telegram.json; setup: research/phone/app.py)
    python research/pinphone.py --selftest       # every phone test, then --smoke (the /update gate: exit code + last line)
    python research/pinphone.py --preview [--html]   # what each command would send (reads Kalshi, GET only)
    python research/pinphone.py --smoke [--results DIR]   # every command rendered read-only on real data: no network,
                                                 # no write, Kalshi from botstats' cache only

FALLBACK. If phone.app cannot be imported, or fails before its first answered Telegram poll, this logs why, sends
nothing, and runs research/pinphone_legacy.py -- the frozen pre-rebuild phone -- so the phone still answers (deleted at
step 14, after 7 clean days). A failure after the first poll is not a start failure: it propagates as before.

THE /update GATE never changes (the OLD running process runs it): [sys.executable, "-u", research\pinphone.py,
"--selftest"] then the same for botstats.py, cwd = the repo root, 900 s, capture_output; exit 0 and a last line
'pinphone selftest: OK' = pass. boot_all finds the phone by CommandLine -like '*pinphone.py*': keep this a file run
directly (never -m).

The old module-level names (research/bars.py's imports, phone_alert.py's CONFIG / Telegram, the golden harness) are
phone.shared's, re-exported below on first use; Phone is phone.app's.
"""
import os
import sys

# 2026-10-26: numpy's OpenBLAS commits a work buffer per CPU thread (+614 MB on the first chart, +131 MB with one
# thread). Set before numpy is first imported -- here, before anything else.
for _blas in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_blas, "1")

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def __getattr__(name):
    """pinphone.<name> for the old importers: phone.shared's names, then phone.app's (Phone)."""
    if name.startswith("__"):
        raise AttributeError(name)
    import phone.shared as shared
    if hasattr(shared, name):
        return getattr(shared, name)
    from phone import app
    if hasattr(app, name):
        return getattr(app, name)
    raise AttributeError("module 'pinphone' has no attribute %r" % name)


def _note(msg):
    """A line to pinphone.log (and stdout) that never raises, even when phone.log itself is what broke."""
    try:
        from phone.log import log
        log(msg)
    except Exception:                                           # noqa: BLE001
        try:
            print(msg.encode("ascii", "backslashreplace").decode("ascii"), flush=True)
        except Exception:                                       # noqa: BLE001
            pass


def fallback(why):
    """phone.app could not start: log it (send nothing) and run the frozen pre-rebuild phone instead."""
    import traceback
    _note("pinphone: the new phone failed to start (%s) -- running pinphone_legacy.py instead; nothing was sent.\n%s"
          % (why, traceback.format_exc()))
    import pinphone_legacy
    return pinphone_legacy.main()


def run(argv=()):
    """The phone, with the legacy fallback for a failure before the first answered poll."""
    state = {}
    try:
        from phone import app
    except Exception:                                           # noqa: BLE001
        return fallback("phone.app could not be imported")
    try:
        return app.main(argv, state=state)
    except KeyboardInterrupt:
        raise
    except BaseException:                                       # noqa: BLE001
        ph = state.get("phone")
        if ph is not None and getattr(ph, "polled_ok", False):
            raise                                               # it had started: not a start failure
        return fallback("phone.app failed before its first answered poll")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if "--selftest" in argv:
        import importlib.util
        spec = importlib.util.spec_from_file_location("phone_selftest", os.path.join(HERE, "phone", "tests",
                                                                                     "run_all.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.main()
    if "--smoke" in argv:
        from phone import smoke
        return smoke.main(argv)
    if "--preview" in argv:
        from phone import app
        return app.preview(argv)
    return run(argv)


if __name__ == "__main__":
    sys.exit(main())
