"""dirlist.py -- glob.glob for one folder's file names, the folder listed once per phone tap (v-tg-fast2, 2026-10-31).

The phone's pages glob the results folder (2,267 files on the server) 5-13 times a tap -- pin logs, paper arms, race
arms, bots' logs -- and every glob lists the whole folder again and matches every name (0.1-0.3 s a tap). glob() here
answers exactly what glob.glob(pattern) answers for a pattern whose wildcards are all in its last part: the folder's
names in listing order, matched as glob does (fnmatch, case-blind on Windows, a leading '.' only for a pattern that
starts with one), each joined to the folder as written. Anything else -- wildcards in a folder part, '**' -- is
glob.glob itself.

A listing is reused only INSIDE one tap (with tap(): the router around a command's words, the chart queue around a
picture), and only while the folder's modified time is the same; outside a tap every call lists the folder afresh,
so code and tests that are not a tap see glob.glob's behaviour exactly.
"""
import contextlib
import fnmatch
import glob as _glob
import os
import threading

_LOCAL = threading.local()


@contextlib.contextmanager
def tap():
    """One phone tap: inside it a folder is listed once (per modified time) for every glob of it. Re-entrant."""
    outer = getattr(_LOCAL, "dirs", None)
    if outer is None:
        _LOCAL.dirs = {}
    try:
        yield
    finally:
        if outer is None:
            _LOCAL.dirs = None


def _listing(folder):
    dirs = getattr(_LOCAL, "dirs", None)
    try:
        mt = os.stat(folder).st_mtime_ns
    except OSError:
        return None
    e = dirs.get(folder) if dirs is not None else None
    if e is not None and e[0] == mt:
        return e
    try:
        names = os.listdir(folder)
    except OSError:
        return None
    e = (mt, names, {})
    if dirs is not None:
        dirs[folder] = e
    return e


def glob(pattern):
    """glob.glob(pattern); inside a tap, from the folder's listing for that tap when only its last part has wildcards."""
    if getattr(_LOCAL, "dirs", None) is None:
        return _glob.glob(pattern)
    folder, base = os.path.split(pattern)
    if not base or _glob.has_magic(folder) or "**" in base or not _glob.has_magic(base):
        return _glob.glob(pattern)
    e = _listing(folder or os.curdir)
    if e is None:
        return _glob.glob(pattern)
    hit = e[2].get(base)
    if hit is None:
        names = e[1]
        if not base.startswith("."):
            names = [n for n in names if not n.startswith(".")]
        hit = e[2][base] = fnmatch.filter(names, base)
    return [os.path.join(folder, n) for n in hit]
