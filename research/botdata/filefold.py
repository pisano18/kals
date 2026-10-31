"""filefold.py -- a log file folded line by line into a summary, remembered between calls (v-tg-fast2, 2026-10-31).

The phone's slow pages read whole logs on every tap to boil them down to a few numbers: /bars read every pinrun
paper log (633 files, 704 MB on the server, ~10 s), /brief every paper arm's settles. fold() keeps each fold's state
per (path, spec): a log whose bytes did not change is not read again, one that only grew has just its new lines fed.

  fold(path, spec, new, feed, copy) -> (state, entry) or (None, None) when the file cannot be opened

  spec     anything hashable that names what is folded (the caller's settings); the path is added to it
  new()    a fresh state;  feed(state, line) folds one line in;  copy(state) an independent copy
  state    a COPY the caller may keep or change, exactly what folding every line of the file now gives: the lines a
           text-mode read (utf-8, errors="replace", universal newlines) yields, the last one even without its newline
  entry    the remembered entry: entry["memo"] is the caller's own cache of anything derived from the file's bytes
           (e.g. the time of its last record); it is emptied whenever the bytes changed

"Did not change" is decided on the bytes, never on a directory time stamp alone (Windows lags the directory entry of
a file a bot holds open): the size from the open file, and either (unchanged size, unchanged os.stat size and mtime,
same crc32 of the first and last 64 KB) or a crc32 of every byte already folded (a log that only grew; ~1 ms a MB).
A file whose last line has no newline yet is folded up to its last newline; the rest is fed into a copy each call.
"""
import collections
import io
import os
import zlib

SPAN = 65536                 # the first / last bytes re-checked for a file that did not grow
MAX_ENTRIES = 4096           # remembered (path, spec) pairs; the oldest is dropped first

_E = collections.OrderedDict()


def clear():
    _E.clear()


def lines(raw):
    """The lines of `raw` (bytes) exactly as a text-mode read (utf-8, errors='replace', universal newlines) gives
    them."""
    return io.StringIO(raw.decode("utf-8", "replace"), newline=None)


def _ends(fh, size):
    fh.seek(0)
    a = zlib.crc32(fh.read(min(SPAN, size)))
    fh.seek(max(0, size - SPAN))
    return a, zlib.crc32(fh.read(SPAN))


def fold(path, spec, new, feed, copy):
    key = (os.path.normcase(os.path.abspath(path)), spec)
    try:
        st = os.stat(path)
        fh = open(path, "rb")
    except OSError:
        _E.pop(key, None)
        return None, None
    stat = (st.st_size, st.st_mtime_ns)
    with fh:
        fh.seek(0, 2)
        size = fh.tell()
        e = _E.pop(key, None)
        if e is not None and size == e["end"] and e["stat"] == stat and e["ends"] is not None \
                and _ends(fh, size) == e["ends"]:
            _E[key] = e                                   # unchanged: nothing is read
            return copy(e["state"]), e
        if e is not None and size >= e["end"]:
            fh.seek(0)
            kept = fh.read(e["end"])
            if len(kept) != e["end"] or zlib.crc32(kept) != e["crc"]:
                e = None
        else:
            e = None
        if e is None:
            e = {"end": 0, "crc": 0, "state": new(), "memo": {}}
        e["memo"] = {} if e["end"] != size else e["memo"]
        fh.seek(e["end"])
        raw = fh.read()
        e["stat"], e["ends"] = None, None
    cut = raw.rfind(b"\n") + 1
    if cut:
        for line in lines(raw[:cut]):
            feed(e["state"], line)
        e["crc"] = zlib.crc32(raw[:cut], e["crc"])
        e["end"] += cut
    frag = raw[cut:]
    out = copy(e["state"])
    if frag:
        for line in lines(frag):
            feed(out, line)
    elif e["end"] == size:                                # complete lines only: next time it may be "unchanged"
        try:
            with open(path, "rb") as fh2:
                fh2.seek(0, 2)
                if fh2.tell() == size:
                    e["stat"], e["ends"] = stat, _ends(fh2, size)
        except OSError:
            pass
    while len(_E) >= MAX_ENTRIES:
        _E.popitem(last=False)
    _E[key] = e
    return out, e
