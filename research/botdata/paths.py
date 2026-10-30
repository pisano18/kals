"""paths.py -- where the bots' files are: RESULTS in ONE place, injectable, and the test write fence.

v-tg-rebuild step 2 (2026-10-30). RESULTS was computed separately in pindesk, pinday, pinledger, pinbrief, botstats, bars
and pinflat (pinflat hardcodes C:\\kals-repo\\results). This is the one copy new code reads. RESULTS here is the SAME
string botstats always computed (<repo>\\results, the repo being the folder above research\\), so re-binding botstats.RESULTS
to it changes nothing. pinflat's hardcoded path is NOT re-bound: from another worktree it would point somewhere else.

INJECTABLE: set_results(path) moves RESULTS for code that reads it through this module (paths.RESULTS / results()).
A module that copied the string at import (botstats.RESULTS = paths.RESULTS) keeps its own copy until step 7 makes it
read through here; tests that patch botstats.RESULTS keep working exactly as before.

THE WRITE FENCE (DESIGN risk 2). When the environment says KALS_TESTING=1, check_write(path) refuses -- raises
WriteFenced, a PermissionError, so every caller that already survives an OSError survives this -- any write under the
REAL results folder or C:\\kals. Why: when a path moves during the rebuild, an old test that patches the dead name
(pinphone.UPDATE_FLAG, pinphone.LOG, botstats.RESULTS) would otherwise touch the live files: delete
results\\pinphone.update, append to pinphone.log, overwrite botstats_cache.json. With KALS_TESTING unset (the live phone,
the desktop, server_sync) check_write does nothing at all.
"""
import os

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
