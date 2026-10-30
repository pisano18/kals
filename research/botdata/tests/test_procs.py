"""test_procs.py -- botdata/procs.py: the one process table, its cache and refresher, botstats' names and seams.

v-tg-rebuild step 4 (2026-10-30). Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_procs.py
"""
import os
import re
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import ck, run, sandbox                                   # noqa: E402

from botdata import procs                                           # noqa: E402
import botstats as bs                                               # noqa: E402


def test_read_only_by_construction():
    """procs.py may look at processes, never change one: every handle QUERY_LIMITED_INFORMATION, no kill / start."""
    with open(procs.__file__, encoding="utf-8") as fh:
        src = fh.read()
    masks = re.findall(r"k32\." + r"OpenProcess\(\s*([^,]+),", src)
    ck(masks and all(m.strip() == "0x1000" for m in masks), "every OpenProcess asks QUERY_LIMITED_INFORMATION: %s" % masks)
    bad = [p for p in ("Terminate" + "Process", "Create" + "Process", r"os\." + "kill", r"\." + r"terminate\(",
                       "task" + "kill", "Stop-" + "Process", "Start-" + "Process", "Shell" + "Execute") if re.search(p, src)]
    ck(not bad, "no process-control call in procs.py (found: %s)" % bad)


def test_native_table_shape():
    rows = procs.native_rows()
    ck(rows is None or all(isinstance(r[0], int) and isinstance(r[1], str) and isinstance(r[2], str) for r in rows),
       "native_rows: None (unreadable) or [pid, started, command line] rows (%s rows here)"
       % (None if rows is None else len(rows)))
    if rows is not None:
        me = [r for r in rows if r[0] == os.getpid()]
        ck(len(me) == 1 and "python" in me[0][2].lower(), "this very python.exe is in the table: %s" % me)
        ours = procs.ours(rows)
        ck(all(procs.is_ours(r[2]) for r in ours) and set(map(tuple, ours)) <= set(map(tuple, rows)),
           "ours(): only the bots' scripts, a part of the whole table")


def test_botstats_names_and_seams():
    ck(bs._norm_procs is procs._norm_procs and bs.procs_for is procs.procs_for and bs.PROC_STALE_S == 300,
       "botstats' process names are botdata.procs' objects")
    saved = procs._procs_native
    try:
        planted = [[7, "", "python research/pinrun.py --live"]]
        bs._procs_native = lambda: planted                      # the golden harness's seam
        ck(procs._procs_native() == planted and procs.read_procs() == planted and bs.read_procs() == planted,
           "setting botstats._procs_native reaches botdata.procs (and read_procs, which asks it first)")
    finally:
        bs._procs_native = saved
    ck(procs._procs_native is saved, "and setting it back restores botdata.procs' own")


def test_procs_for():
    c = {}
    rows, ok, ch = procs.procs_for(c, 1000.0, [(1, "python pinrun.py --live")])
    ck(rows == [[1, "", "python pinrun.py --live"]] and ok and not ch and c == {},
       "a held table is used as it is (two-field rows normalised), nothing cached")
    rows, ok, ch = procs.procs_for(c, 1000.0, lambda: [(2, "s", "x")])
    ck(rows == [[2, "s", "x"]] and ok and ch and c["procs"] == {"t": 1000.0, "rows": [[2, "s", "x"]]},
       "a callable's table is cached in the botstats cache")
    rows, ok, ch = procs.procs_for(c, 1100.0, lambda: None)
    ck(rows == [[2, "s", "x"]] and ok and not ch, "a failed read inside PROC_STALE_S falls back to the cached table")
    rows, ok, ch = procs.procs_for(c, 1000.0 + procs.PROC_STALE_S + 1, lambda: None)
    ck(rows is None and not ok, "older than PROC_STALE_S: could not tell (None, never [])")


def test_table_cache_and_refresher():
    with sandbox():
        calls = []
        saved = procs.read_all
        try:
            procs.read_all = lambda timeout=40: (calls.append(1) or [[1, "", "python x.py"]])
            ck(procs.cached() is None, "an empty cache gives None, never asks Windows")
            ck(procs.table() == [[1, "", "python x.py"]] and len(calls) == 1 and procs.table() and len(calls) == 1,
               "table(): read once, then from the cache")
            procs._TABLE["t"] = time.time() - 3 * procs.TABLE_TTL_S
            ck(procs.cached() is None and procs.table() and len(calls) == 2, "a stale cache is read again")
            ck(procs.pid_cmd(procs.table()) == [(1, "python x.py")], "pid_cmd: pinphone's [(pid, cmdline)] shape")
            procs.read_all = lambda timeout=40: None
            procs._TABLE["t"] = time.time() - 3 * procs.TABLE_TTL_S
            ck(procs.table() is None and procs._TABLE["rows"] == [[1, "", "python x.py"]],
               "a failed read answers None and keeps the last good table for later")
        finally:
            procs.read_all = saved


def test_refresher_only_when_asked():
    ck(not any(t.name == "botdata-procs" for t in threading.enumerate()) or procs._REFRESHER["thread"] is not None,
       "importing botdata.procs starts no thread")
    with sandbox():
        saved = procs.read_all
        try:
            procs.read_all = lambda timeout=40: [[9, "", "python y.py"]]
            th = procs.start_refresher(period=3600)
            t0 = time.time()
            while procs.cached() is None and time.time() - t0 < 5:
                time.sleep(0.01)
            ck(th.daemon and th.is_alive() and procs.start_refresher() is th and procs.cached() == [[9, "", "python y.py"]],
               "start_refresher: one daemon thread (a second call returns it), the cache filled")
        finally:
            procs.read_all = saved


if __name__ == "__main__":
    sys.exit(run(dict(globals()), "test_procs"))
