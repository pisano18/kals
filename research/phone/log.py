"""phone/log.py -- the phone's log line: to stdout and to results\\pinphone.log. log() and cprint() NEVER RAISE.

v-tg-rebuild step 6 (2026-10-30): moved verbatim out of research/pinphone.py, which re-exports both names (pinphone.log,
pinphone.cprint). One change, for the self-tests and the golden harness: the log FILE is whatever path_of() gives at
the moment of each call, and pinphone points it at its own module global (set_path(lambda: LOG)). A test that patches
pinphone's LOG (globals()["LOG"] = <temp>) therefore still moves every log() line there -- the transport's too.
Before, LOG lived in pinphone; had it simply moved here, such a patch would hit a dead name and the test would append
to the real log (DESIGN risk 2). Under KALS_TESTING=1 the write fence (botdata.paths.check_write) refuses the real log
anyway, so a slip costs a missing line, never a live-file write.
"""
import os
import time

from botdata import paths as _paths

LOG = os.path.join(_paths.RESULTS, "pinphone.log")      # the file while nothing has called set_path
_path_of = None                                         # a function giving the log file's path, set by set_path


def set_path(path_of, replace=False):
    """Point log() at path_of() -- a function asked on EVERY line (pinphone: lambda: LOG, its own global). The FIRST
    caller keeps it (replace=True overrides): `python research\pinphone.py` runs as __main__, and tgcharts later imports
    a second copy named pinphone, whose import calls this again -- the running program's LOG (the one its self-test
    patches) must stay the one every line goes to. (Before the move each copy logged to its own LOG; both are the same
    file outside a test.)"""
    global _path_of
    if _path_of is None or replace:
        _path_of = path_of


def log_path():
    """The file log() appends to now."""
    return _path_of() if _path_of is not None else LOG


def log(msg):
    """One line to stdout and to LOG. NEVER RAISES (2026-10-18): boot_all starts this program with stdout
    redirected to results/pinphone.out, and a redirected stdout on this box is cp1252 -- the emoji and box
    characters the phone's replies carry cannot be written there. Before this fix a raise here came out of
    say() AFTER the message had gone, and out of poll_once() BEFORE Telegram was told the update was
    handled: the process died, and the restart answered the same command again. So the console copy falls
    back to escapes; the log file (utf-8) keeps the real characters."""
    line = "%s  %s" % (time.strftime("%Y-%m-%dT%H:%M:%S"), msg)
    try:
        print(line, flush=True)
    except Exception:                                           # noqa: BLE001
        try:
            print(line.encode("ascii", "backslashreplace").decode("ascii"), flush=True)
        except Exception:                                       # noqa: BLE001
            pass
    try:
        path = log_path()                    # v-tg-rebuild step 6: the owner's LOG at this moment (set_path)
        _paths.check_write(path)             # v-tg-rebuild step 2: never the live log under KALS_TESTING=1 (an OSError)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def cprint(s):
    """print() that never raises on a console that cannot show a character (the self-test's and --preview's
    output carries emoji; a redirected console here is cp1252): the line falls back to escapes."""
    try:
        print(s, flush=True)
    except UnicodeEncodeError:
        print(str(s).encode("ascii", "backslashreplace").decode("ascii"), flush=True)
