"""_kit.py -- what the botdata tests share: a check that prints like the old botstats self-test, a sandbox that points
RESULTS at a temp folder and empties every botdata cache (restoring both after), and a runner for test_* functions.

v-tg-rebuild step 4 (2026-10-30). Plain functions, no pytest (C:\\Python314 has none). Every text open() names utf-8.
"""
import contextlib
import os
import shutil
import sys
import tempfile
import time
import traceback

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)

# a test never writes a LIVE file (botdata/paths.py's fence, v-tg-rebuild step 2)
os.environ["KALS_TESTING"] = "1"


def ck(cond, msg):
    """One check: '  ok   <msg>' or '  FAIL <msg>' and an AssertionError (the old botstats self-test's words)."""
    print(("  ok   " if cond else "  FAIL ") + msg, flush=True)
    if not cond:
        raise AssertionError(msg)


# the botdata caches a sandbox empties, by name -> their just-imported state (any other module dict is left alone)
FRESH = {"_MEMO": {"key": None, "data": None}, "_BACK": {}, "_ACTIVE": {"t": 0.0, "v": None},
         "_FLEET": {"t": 0.0, "v": None}, "_TABLE": {"t": 0.0, "rows": None},
         "_SINCE": {}, "_MARKETS": {}}                               # v-tg-fast: read_since's and market()'s memos


def _caches():
    """[(cache dict, its fresh state)] for every botdata module's caches named in FRESH."""
    out = []
    for name, m in sorted(sys.modules.items()):
        if not (name == "botdata" or name.startswith("botdata.")) or name.startswith("botdata.tests"):
            continue
        for k, v in list(vars(m).items()):
            if k in FRESH and isinstance(v, dict):
                out.append((v, FRESH[k]))
    return out


@contextlib.contextmanager
def sandbox(prefix="botdata-test-"):
    """A temp RESULTS folder for the duration; every botdata cache emptied on the way in and put back on the way out."""
    from botdata import paths
    td = tempfile.mkdtemp(prefix=prefix)
    saved = [(d, dict(d), f) for d, f in _caches()]
    old = paths.set_results(td)
    try:
        for d, _v, f in saved:
            d.clear()
            d.update(f)
        yield td
    finally:
        paths.set_results(old)
        for d, v, _f in saved:
            d.clear()
            d.update(v)
        shutil.rmtree(td, ignore_errors=True)


def run(glb, title):
    """Run every test_* function in the module globals `glb`; print a summary line; return the exit code."""
    tests = [(k, v) for k, v in glb.items() if k.startswith("test_") and callable(v)]
    passed, failed = 0, []
    t0 = time.time()
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print("  ok   %s" % name, flush=True)
        except Exception:                                       # noqa: BLE001
            failed.append(name)
            print("  FAIL %s\n%s" % (name, traceback.format_exc()), flush=True)
    print("%s: %d passed, %d failed (%.1f s)" % (title, passed, len(failed), time.time() - t0), flush=True)
    return 1 if failed else 0
