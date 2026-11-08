"""paths.py -- where the bots' files are: RESULTS in ONE place, injectable, and the test write fence.

v-tg-rebuild step 2 (2026-10-30). RESULTS was computed separately in pindesk, pinday, pinledger, pinbrief, botstats, bars
and pinflat (pinflat hardcodes C:\\kals-repo\\results). This is the one copy new code reads. RESULTS here is the SAME
string botstats always computed (<repo>\\results, the repo being the folder above research\\), so re-binding botstats.RESULTS
to it changes nothing. pinflat's hardcoded path is NOT re-bound: from another worktree it would point somewhere else.

INJECTABLE: set_results(path) moves RESULTS for code that reads it through this module (paths.RESULTS / results()).
Since step 4 (2026-10-30) botstats and every botdata module read paths.RESULTS at call time, and botstats.RESULTS is a
property over it: a test that sets botstats.RESULTS = <temp dir> calls set_results.

THE WRITE FENCE (DESIGN risk 2). When the environment says KALS_TESTING=1, check_write(path) refuses -- raises
WriteFenced, a PermissionError, so every caller that already survives an OSError survives this -- any write under the
REAL results folder or C:\\kals. Why: when a path moves during the rebuild, an old test that patches the dead name
(pinphone.UPDATE_FLAG, pinphone.LOG, botstats.RESULTS) would otherwise touch the live files: delete
results\\pinphone.update, append to pinphone.log, overwrite botstats_cache.json. With KALS_TESTING unset (the live phone,
the desktop, server_sync) check_write does nothing at all.

ATOMIC WRITES (2026-11-07): write_atomic / write_json_atomic -- a temp file then os.replace, so a config or heartbeat is
never left half-written (the phone's telegram.json writers and its heartbeat use them).
"""
import json
import os
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))               # <repo>\research\botdata
RESEARCH = os.path.dirname(HERE)                                # <repo>\research
REPO = os.path.dirname(RESEARCH)
# botstats: os.path.join(os.path.dirname(HERE), "results") with HERE = <repo>\research -- the same string
DEFAULT_RESULTS = os.path.join(REPO, "results")
RESULTS = DEFAULT_RESULTS
KALS = r"C:\kals"
LIVE_RESULTS = r"C:\kals-repo\results"                          # pinflat / pinentry / pinlive's hardcoded copy

TESTING_ENV = "KALS_TESTING"


class WriteFenced(PermissionError):
    """A write to a live file while KALS_TESTING=1."""


def set_results(path):
    """Point RESULTS somewhere else (a test's temp folder, a golden fixture); returns the old value."""
    global RESULTS
    old, RESULTS = RESULTS, path
    return old


def results(*parts):
    """A path inside the CURRENT RESULTS."""
    return os.path.join(RESULTS, *parts)


def testing():
    """True when the environment says this is a test run (KALS_TESTING=1)."""
    return os.environ.get(TESTING_ENV) == "1"


def _norm(p):
    return os.path.normcase(os.path.abspath(str(p)))


def fenced_roots():
    """The live folders a test must never write: the real results (both spellings) and C:\\kals."""
    out = []
    for r in (DEFAULT_RESULTS, LIVE_RESULTS, KALS):
        n = _norm(r)
        if n not in out:
            out.append(n)
    return out


def is_live_path(path):
    """True when `path` is inside one of fenced_roots()."""
    p = _norm(path)
    return any(p == r or p.startswith(r.rstrip("\\/") + os.sep) for r in fenced_roots())


def check_write(path):
    """Raise WriteFenced when this is a test run (KALS_TESTING=1) and `path` is a live file; else nothing."""
    if testing() and is_live_path(path):
        raise WriteFenced("KALS_TESTING=1: refusing to write the live file %s" % path)


def write_atomic(path, text, encoding="utf-8", tries=3):
    """Write `text` to `path` as ONE step: a temp file beside it, then os.replace (2026-11-07, the phone audit: telegram.json
    was rewritten in place, so a crash or a full disk mid-write left half a file -- no token, no pairing -- and the phone
    could not start again). A reader sees the old file or the new one, never a part. check_write first (the test fence).
    A replace refused because a reader holds the file open (Windows) is tried again `tries` times. Raises OSError on
    failure; the temp file is removed then."""
    check_write(path)
    tmp = "%s.%d.%d.tmp" % (path, os.getpid(), threading.get_ident())      # one temp file per writer, never shared
    try:
        with open(tmp, "w", encoding=encoding) as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        for k in range(tries):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if k == tries - 1:
                    raise
                time.sleep(0.2)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def write_json_atomic(path, obj, **dump_kw):
    """json.dumps(obj, **dump_kw) written by write_atomic (one step; raises OSError)."""
    write_atomic(path, json.dumps(obj, **dump_kw))


def read_json(path):
    """A JSON object file -> dict, or None when it is missing, unreadable or not an object.  (pinphone.read_json; rebuild
    step 12: /funds' bet-size readers had a copy)"""
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None
