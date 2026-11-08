#!/usr/bin/env python3
r"""logfiles.py -- read a results\ log whether it is still plain or already archived by log_rotate.py (2026-11-07).

WHY. The server's disk fills around March 2027 (26.3 GB free on 11-07, ~1.46 GB a week, no rotation). log_rotate.py
moves a FINISHED log of a few families (pintraj-live-*, pinrun-paper-*, and pinrun-live-* once 60 days old) into
results\archive\<name>.gz -- gzip, the same bytes, read back and checked before the plain file goes. A reader that
wants a family's HISTORY (every run since a date, a lifetime tally) asks here instead of glob.glob / open:

    for p in logfiles.glob(os.path.join(RESULTS, "pinrun-live-*.jsonl")):    # plain + archived, oldest name first
        with logfiles.open(p, encoding="utf-8", errors="replace") as fh:      # a .gz is unpacked on the fly
            ...

glob(pattern) is what glob.glob(pattern) finds PLUS every results\archive\<name>.gz whose <name> matches the
pattern's last part and is not also still plain (a run cut between the archive write and the delete leaves both:
the plain one is read). The list is sorted by log_name -- the file name with any .gz dropped -- so a stamped family
comes out in start order whichever folder a file sits in (a plain sorted() of the mixed paths would put every
archived file first, ahead of an older plain one git still tracks). open() is the builtin open, argument for
argument, for any path not ending in .gz; a .gz opens for reading only, as text (mode "r"/"rt") or bytes ("rb").
An archived file keeps its source's modified time (log_rotate sets it), so a filter on os.path.getmtime picks the
same files it did before the move.

WHAT A .gz CANNOT DO: seek from its end, or tell its unpacked size (os.path.getsize is the PACKED size). A reader
that reads backwards from the end (botdata.logs.read_since / last_record) reads a .gz forward with read_bytes().
The newest log of a family is never archived (log_rotate.py refuses it), so a reader of the newest file alone needs
no change, and neither does one whose window is shorter than a family's archive age (log_rotate.POLICY).

Standard library only; imports nothing from the bots.

    python research/logfiles.py --selftest
"""
import builtins
import glob as _glob
import gzip
import os
import sys

ARCHIVE = "archive"             # results\archive\ -- log_rotate.py's one destination
GZ = ".gz"


def archive_dir(results):
    """The archive folder of a results folder."""
    return os.path.join(results, ARCHIVE)


def is_gz(path):
    return str(path).lower().endswith(GZ)


def log_name(path):
    """The log's own name: the file name with an archive's .gz dropped (pinrun-live-20261031T101116Z.jsonl)."""
    b = os.path.basename(str(path))
    return b[:-len(GZ)] if is_gz(b) else b


def sort_key(path):
    """Start order for a stamped family, plain and archived alike: by log_name, then by the path."""
    return (log_name(path), str(path))


def glob(pattern, globber=None):
    """glob.glob(pattern) plus the archived copies of matching names (see the module docstring), by log_name.
    `globber` replaces glob.glob for BOTH folders (the phone passes botdata.dirlist.glob). Only the pattern's last
    part may hold wildcards for the archive half; a folder wildcard finds plain files alone."""
    g = globber or _glob.glob
    plain = list(g(pattern))
    folder, base = os.path.split(pattern)
    arch = []
    if base and not _glob.has_magic(folder):
        seen = {os.path.basename(p).lower() for p in plain}
        arch = [p for p in g(os.path.join(folder, ARCHIVE, base + GZ)) if log_name(p).lower() not in seen]
    return sorted(plain + arch, key=sort_key)


def resolve(folder, name):
    """Where the log called `name` is now: folder\\name while it is plain, else folder\\archive\\name.gz, else None
    (for a reader that knows a log by name -- an arm's .out file names its own log)."""
    p = os.path.join(folder, name)
    if os.path.exists(p):
        return p
    q = os.path.join(folder, ARCHIVE, name + GZ)
    return q if os.path.exists(q) else None


def open(path, mode="r", buffering=-1, encoding=None, errors=None, newline=None):     # noqa: A001 (drop-in)
    """builtins.open for a plain file; a .gz opened for reading (text or bytes) and unpacked as it is read."""
    if not is_gz(path):
        return builtins.open(path, mode, buffering, encoding, errors, newline)
    m = mode.replace("t", "")
    if m not in ("r", "rb"):
        raise ValueError("an archived log is read-only (mode %r): %s" % (mode, path))
    if m == "rb":
        return gzip.open(path, "rb")
    return gzip.open(path, "rt", encoding=encoding, errors=errors, newline=newline)


def read_bytes(path):
    """The whole log as bytes, unpacked if archived."""
    with open(path, "rb") as fh:
        return fh.read()


def mtime(path, default=None):
    """os.path.getmtime, or `default` when the file has gone: log_rotate can archive a log between a reader's listing
    and its look at the file (11-07 review: before rotation no log was ever deleted, so no reader expected that)."""
    try:
        return os.path.getmtime(path)
    except OSError:
        return default


def by_mtime(path):
    """A sort key for max() / sorted() by modified time that survives a file archived since the listing: its time, or
    0 once it has gone (so it sorts oldest and is never picked as the newest)."""
    return mtime(path, 0.0)


# --------------------------------------------------------------------------
def selftest():
    import shutil
    import tempfile

    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("logfiles selftest: FAILED -- " + msg)

    td = tempfile.mkdtemp(prefix="logfiles-selftest-")
    try:
        ad = archive_dir(td)
        os.makedirs(ad)
        body = {"pinrun-live-20260908T062046Z.jsonl": '{"kind": "start", "t": "a"}\n',
                "pinrun-live-20260920T000000Z.jsonl": '{"kind": "settled", "pnl_c": 1}\n',
                "pinrun-live-20261101T000000Z.jsonl": '{"kind": "order", "filled": 5}\n'}
        # the oldest stays PLAIN (git tracks it), the middle one is archived, the newest is plain
        for n in ("pinrun-live-20260908T062046Z.jsonl", "pinrun-live-20261101T000000Z.jsonl"):
            with builtins.open(os.path.join(td, n), "w", encoding="utf-8", newline="") as fh:
                fh.write(body[n])
        mid = "pinrun-live-20260920T000000Z.jsonl"
        with gzip.open(os.path.join(ad, mid + GZ), "wb") as fh:
            fh.write(body[mid].encode("utf-8"))
        with builtins.open(os.path.join(td, "pinrun-paper-20261101T000000Z.jsonl"), "w", encoding="utf-8") as fh:
            fh.write("{}\n")
        ps = glob(os.path.join(td, "pinrun-live-*.jsonl"))
        ck([log_name(p) for p in ps] == sorted(body), "glob: plain + archived, in start order (an old plain file is "
                                                      "not pushed after the archived one)")
        ck(sum(1 for p in ps if is_gz(p)) == 1 and os.path.dirname(ps[1]) == ad, "the middle one is read from the archive")
        ck(sorted(ps, key=sort_key) == ps and [p for p in ps if "paper" in p] == [], "sorted by log_name; another family "
                                                                                   "never leaks in")
        got = []
        for p in ps:
            with open(p, encoding="utf-8", errors="replace") as fh:
                got.append(fh.read())
        ck(got == [body[n] for n in sorted(body)], "open: text read back identical, plain or gzip")
        ck(read_bytes(ps[1]) == body[mid].encode("utf-8"), "read_bytes unpacks an archive")
        ck(resolve(td, mid) == ps[1] and resolve(td, "pinrun-live-20261101T000000Z.jsonl") == ps[2]
           and resolve(td, "nope.jsonl") is None, "resolve: a log by name, plain or archived, or None")
        # both plain and archived (a rotation cut before its delete): the plain one is read, once
        with builtins.open(os.path.join(td, mid), "w", encoding="utf-8", newline="") as fh:
            fh.write(body[mid])
        ps2 = glob(os.path.join(td, "pinrun-live-*.jsonl"))
        ck(len(ps2) == 3 and not any(is_gz(p) for p in ps2), "a name both plain and archived is listed ONCE, plain")
        try:
            open(ps[1], "a")
            ck(False, "an archive must refuse a write mode")
        except ValueError:
            ck(True, "an archive refuses a write mode")
        ck(glob(os.path.join(td, "nothing-*.jsonl")) == [], "NULL: no match anywhere -> []")
        shutil.rmtree(ad)
        ck(len(glob(os.path.join(td, "pinrun-live-*.jsonl"))) == 3, "NULL: no archive folder at all -> plain only")
        calls = []
        glob(os.path.join(td, "pinrun-live-*.jsonl"), globber=lambda p: calls.append(p) or _glob.glob(p))
        ck(len(calls) == 2 and calls[1].endswith(os.path.join(ARCHIVE, "pinrun-live-*.jsonl.gz")),
           "a globber (the phone's dirlist) lists both folders")
        ck(log_name(r"C:\x\archive\a.jsonl.gz") == "a.jsonl" and log_name("b.jsonl") == "b.jsonl", "log_name")
        ck(mtime(ps[0]) == os.path.getmtime(ps[0]) and mtime(os.path.join(td, "gone.jsonl")) is None
           and mtime(os.path.join(td, "gone.jsonl"), 0.0) == 0.0, "mtime: the file's time, or the default once it "
                                                                  "has gone (moved mid-read)")
        ck(max([os.path.join(td, "gone.jsonl"), ps[0]], key=by_mtime) == ps[0], "by_mtime: a file gone since the "
                                                                                "listing sorts oldest, never a crash")
    finally:
        shutil.rmtree(td, ignore_errors=True)
    print("logfiles selftest: OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        selftest()
        sys.exit(0)
    print(__doc__)
