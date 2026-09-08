#!/usr/bin/env python3
"""gzstream.py -- memory-bounded salvage reader for the collector's gzips.

WHY THIS EXISTS AND WHY IT IS NOT research/gzsalvage.py

gzsalvage.iter_lines is correct and is the reference for the member-splitting
logic below. It is not usable on the orderbook_delta tape from this job,
because its salvage pass does

    text = chunk.decode(...)      # one whole member, decompressed
    lines = text.split("\\n")     # and again, as a list

An 80 MB delta hour decompresses to ~700 MB, so that pair of lines is ~1.5 GB
per file. This box has ~3 GB free with a live trader and two collectors on it,
and the collector outranks this job. So the member loop here is streamed: the
decompressor is fed 1 MB at a time and lines are yielded as they complete, and
the peak is the member's compressed bytes plus a few MB.

THE BUG BEING SALVAGED (kalshi_collector.py, documented in gzsalvage.py):
the collector appends to each hour file and a restart inside the hour writes a
SECOND gzip member behind an untrailered first one. The standard reader then
raises `zlib.error: Error -3 ... invalid block type` -- usually before it has
yielded a single line, so the whole hour reads as EMPTY with no error anywhere.
Measured on this tape 2026-09-08: 204 of 322 orderbook_delta hours have more
than one member, and 2 of them (20260827T07, 20260903T07) yielded under 1,600
lines to the standard reader against ~2-5 MILLION for a healthy hour.
"""
import gzip
import os
import zlib

MAGIC = b"\x1f\x8b\x08"


def _member_offsets(raw):
    """Offsets of plausible member headers, chance hits filtered out.

    The magic bytes occur inside compressed data by accident. A candidate that
    will not decompress is dropped, because keeping it would also truncate the
    REAL member before it (each member is bounded by the next offset).
    """
    cand, i = [], 0
    while True:
        j = raw.find(MAGIC, i)
        if j < 0:
            break
        cand.append(j)
        i = j + 1
    good = []
    for k, off in enumerate(cand):
        # VALIDATE ON THE CANDIDATE'S OWN BYTES ONLY. Handing the validator
        # the following member's header as deflate data makes a perfectly
        # good member look like a chance magic hit -- which is exactly how
        # the first (untrailered) member got dropped in the first draft, and
        # with it every line the collector wrote before the restart.
        nxt = cand[k + 1] if k + 1 < len(cand) else len(raw)
        ok = False
        for end in (min(off + 4096, nxt), off + 4096):
            d = zlib.decompressobj(16 + zlib.MAX_WBITS)
            try:
                if d.decompress(raw[off:end]):
                    ok = True
                    break
            except zlib.error:
                continue
        if ok:
            good.append(off)
    return good


def _member_lines(blob):
    """Yield complete lines from one member, holding only a small buffer."""
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    tail = ""
    step = 1 << 20
    pos = 0
    while pos < len(blob):
        try:
            out = d.decompress(blob[pos:pos + step])
        except zlib.error:
            break
        pos += step
        if out:
            tail += out.decode("utf-8", "replace")
            if "\n" in tail:
                parts = tail.split("\n")
                tail = parts.pop()
                for ln in parts:
                    if ln:
                        yield ln + "\n"
        if d.eof:
            break
    try:
        out = d.flush()
    except zlib.error:
        out = b""
    if out:
        tail += out.decode("utf-8", "replace")
        parts = tail.split("\n")
        tail = parts.pop()
        for ln in parts:
            if ln:
                yield ln + "\n"
    # a trailing fragment is a TRUNCATED record, not a continuation: a record
    # never spans two members. gzsalvage.py makes the same call.


def lines(path, stat=None):
    """Lines from a gzip file, salvaging a broken one. Fast path first."""
    n = 0
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                n += 1
                yield line
        return
    except (EOFError, zlib.error, OSError):
        pass
    if stat is not None:
        stat["salvaged_files"] = stat.get("salvaged_files", 0) + 1
        stat["fastpath_lines_before_break"] = \
            stat.get("fastpath_lines_before_break", 0) + n
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return
    offs = _member_offsets(raw)
    skip = n
    got = 0
    for i, off in enumerate(offs):
        stop = offs[i + 1] if i + 1 < len(offs) else len(raw)
        for ln in _member_lines(raw[off:stop]):
            if skip:
                skip -= 1
                continue
            got += 1
            yield ln
    if stat is not None:
        stat["salvaged_lines"] = stat.get("salvaged_lines", 0) + got


# ---------------------------------------------------------------- selftest --
def selftest(tmpdir=None):
    print("SELF-TEST -- gzstream")
    import tempfile
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    tmp = tmpdir or tempfile.mkdtemp(prefix="gzstream")
    # 1) a HEALTHY file reads normally and salvage never runs
    p1 = os.path.join(tmp, "healthy.jsonl.gz")
    want = ["line %d\n" % i for i in range(5000)]
    with gzip.open(p1, "wt") as f:
        f.writelines(want)
    st = {}
    got = list(lines(p1, st))
    ck(got == want and not st,
       "healthy file: %d lines, salvage not invoked (%s)" % (len(got), st))

    # 2) THE REAL BUG. Member one is flushed per line and never trailered
    #    (the collector is killed); member two is a complete gzip appended
    #    behind it by the restarted collector.
    p2 = os.path.join(tmp, "broken.jsonl.gz")
    a = ["a %d\n" % i for i in range(3000)]
    b = ["b %d\n" % i for i in range(3000)]
    co = zlib.compressobj(9, zlib.DEFLATED, 31)
    blob = b""
    for ln in a:
        blob += co.compress(ln.encode())
        blob += co.flush(zlib.Z_SYNC_FLUSH)     # flushed, NEVER closed
    with open(p2, "wb") as f:
        f.write(blob)
    with gzip.open(p2, "ab") as f:              # the restart appends member 2
        f.writelines([x.encode() for x in b])
    std = 0
    try:
        with gzip.open(p2, "rt") as f:
            for _ in f:
                std += 1
    except Exception as e:
        std = "%s after %d" % (type(e).__name__, std)
    print("       the standard reader gets: %s of %d lines" % (std, len(a + b)))
    st2 = {}
    got2 = list(lines(p2, st2))
    ck(got2 == a + b,
       "broken file: recovered %d of %d lines in order (salvage stats %s)"
       % (len(got2), len(a + b), st2))
    ck(st2.get("salvaged_files") == 1, "salvage was invoked exactly once")

    # 3) NOTHING PLANTED -> NOTHING INVENTED. A file of pure garbage must not
    #    yield lines just because the magic bytes appear in it.
    p3 = os.path.join(tmp, "garbage.gz")
    with open(p3, "wb") as f:
        f.write(b"\x1f\x8b\x08" + os.urandom(50000))
    got3 = list(lines(p3))
    ck(got3 == [], "a garbage file yields nothing (%d)" % len(got3))

    # 4) a TRUNCATED live file (no trailer, single member) keeps what parsed
    p4 = os.path.join(tmp, "live.jsonl.gz")
    co = zlib.compressobj(9, zlib.DEFLATED, 31)
    blob = b""
    for ln in a:
        blob += co.compress(ln.encode())
        blob += co.flush(zlib.Z_SYNC_FLUSH)
    with open(p4, "wb") as f:
        f.write(blob)
    got4 = list(lines(p4))
    ck(got4 == a, "a live truncated gzip yields all %d flushed lines (%d)"
       % (len(a), len(got4)))

    print("SELF-TEST " + ("PASSED" if not fails
                          else "*** FAILED (%d) ***" % len(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
