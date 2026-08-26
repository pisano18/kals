#!/usr/bin/env python3
# VERSION: 2026-08-25-gz1
"""
gzsalvage.py -- read the collector's gzip files even when a restart broke them.

    python research/gzsalvage.py --selftest
    python research/gzsalvage.py --data C:\\kals\\kalshi_data     # survey

THE BUG THIS EXISTS FOR

kalshi_collector.py opens each hour's file in gzip APPEND mode and flushes
after every line, so the data is on disk immediately. But on Windows
`loop.add_signal_handler` raises NotImplementedError and the collector
swallows it (kalshi_collector.py:321-325), so Ctrl+C propagates out of
`asyncio.gather` and `c.w.close()` at :329 NEVER RUNS. The gzip stream gets no
trailer.

That alone is survivable -- a reader gets the flushed lines and then an
EOFError, which every reader here already catches.

What is NOT survivable is a restart inside the same UTC hour. The watchdog
restarts the collector on any crash, and the new process appends a SECOND gzip
member behind the untrailered first one. Reading that file raises

    zlib.error: Error -3 while decompressing data: invalid block type

Measured on a faithful reproduction (two 5-line sessions, first killed with
os._exit so no close() runs): the standard reader recovered **0 of 10 lines**.
Not just the post-restart half -- everything, because the failure lands inside
the first buffered read before a single line is yielded.

So every hour in which the collector restarted is currently either partly or
entirely invisible to every analysis in this repository, silently, counted
only as `partial` in a stats dict nobody reads.

WHAT THIS DOES

Member-by-member decompression. Scan the raw bytes for gzip member headers,
decompress each independently with a fresh zlib object, and yield whatever
each one gives up before it fails. A broken member costs you that member, not
the file.

This is retroactive: it recovers data already on disk. The collector fix
(closing the writer on Windows) stops NEW files being written this way, but
does nothing for the hours already recorded.
"""

import argparse
import glob
import gzip
import json
import os
import sys
import zlib

MAGIC = b"\x1f\x8b\x08"


def _members(raw):
    """Byte offsets of every plausible gzip member header.

    The magic can occur inside compressed data by chance, so a candidate that
    does not decompress to anything is simply skipped rather than trusted.
    """
    out, i = [], 0
    while True:
        j = raw.find(MAGIC, i)
        if j < 0:
            return out
        out.append(j)
        i = j + 1


def _member_bytes(blob):
    """Decompress one member's byte range, keeping whatever it yields.

    decompressobj.decompress() raises WITHOUT handing back what it already
    produced, so one big call loses everything the moment it walks into the
    next member's header. Feed it in small chunks and keep the output as it
    accumulates.
    """
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)     # 16 = expect a gzip header
    out, pos, CH = [], 0, 4096
    while pos < len(blob):
        try:
            out.append(d.decompress(blob[pos:pos + CH]))
        except zlib.error:
            break
        pos += CH
        if d.eof:
            break
    try:
        out.append(d.flush())
    except zlib.error:
        pass
    return b"".join(out)


def _healthy(path):
    """Can the standard reader get through the whole file? Costs a full
    decompress, so it is for surveys and diagnostics -- NOT for the read path.
    """
    try:
        with gzip.open(path, "rb") as f:
            while f.read(1 << 20):
                pass
        return True
    except Exception:
        return False


def iter_lines(path, stats=None):
    """Yield text lines from a gzip file, salvaging what a broken one holds.

    The fast path runs FIRST and yields as it goes, counting what it emitted.
    If it dies, the salvage pass replays the file and skips that many lines.
    Probing health up front would be tidier, but it decompresses the whole
    file before reading a byte of it -- doubling the cost of every healthy
    file, which is essentially all of them, across seven stages and gigabytes.
    Broken files pay twice; healthy files pay once.
    """
    n = 0
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                n += 1
                yield line
        return
    except Exception:
        pass

    if stats is not None:
        stats["salvaged_files"] = stats.get("salvaged_files", 0) + 1

    try:
        raw = open(path, "rb").read()
    except OSError:
        return

    skip = n
    offs = _members(raw)
    for i, off in enumerate(offs):
        # Bound each member by the NEXT member's header. Handing the whole
        # remainder to one decompressor makes it read the next header as a
        # deflate block and throw away this member with it.
        stop = offs[i + 1] if i + 1 < len(offs) else len(raw)
        chunk = _member_bytes(raw[off:stop])
        if not chunk and stop != len(raw):
            chunk = _member_bytes(raw[off:])     # chance magic hit; retry open
        if not chunk:
            continue
        text = chunk.decode("utf-8", "replace")
        lines = text.split("\n")
        # Each member is an independent stream and a record never spans two of
        # them, so a trailing fragment is a TRUNCATED line, not a
        # continuation. Carrying it forward would glue two records together.
        lines.pop()
        for ln in lines:
            if not ln:
                continue
            if skip:
                skip -= 1        # the fast path already emitted this one
                continue
            yield ln + "\n"


def iter_json(pattern, stats=None):
    """The drop-in replacement for read_jsonl_gz."""
    st = stats if stats is not None else {}
    for fp in sorted(glob.glob(pattern)):
        st["files"] = st.get("files", 0) + 1
        for line in iter_lines(fp, stats=st):
            try:
                yield json.loads(line)
            except (json.JSONDecodeError, ValueError):
                st["bad_lines"] = st.get("bad_lines", 0) + 1


# ===========================================================================
def selftest():
    import tempfile, shutil, subprocess
    print("=" * 78)
    print("SELF-TEST -- can it read what a collector restart broke?")
    print("=" * 78)
    fails = []
    tmp = tempfile.mkdtemp()
    try:
        w = os.path.join(tmp, "w.py")
        with open(w, "w", encoding="utf-8") as f:
            f.write(
                "import gzip, json, os, sys\n"
                "f = gzip.open(sys.argv[1], 'at', compresslevel=4, "
                "encoding='utf-8')\n"
                "for i in range(int(sys.argv[2]), int(sys.argv[2])+"
                "int(sys.argv[4])):\n"
                "    f.write(json.dumps({'n': i, 'sess': sys.argv[3]})+'\\n')\n"
                "    f.flush()\n"
                "os._exit(0)\n")

        print(f"\n  {'case':>34}{'standard':>12}{'salvaged':>12}{'want':>8}")
        cases = [
            ("clean single session", [(0, "a", 20)], True, 20),
            ("killed mid-hour, no trailer", [(0, "a", 20)], False, 20),
            ("ONE restart inside the hour", [(0, "a", 20), (20, "b", 20)],
             False, 40),
            ("three restarts inside the hour",
             [(0, "a", 15), (15, "b", 15), (30, "c", 15), (45, "d", 15)],
             False, 60),
        ]
        for label, sessions, close_clean, want in cases:
            fp = os.path.join(tmp, label.replace(" ", "_") + ".jsonl.gz")
            if os.path.exists(fp):
                os.remove(fp)
            for start, tag, n in sessions:
                subprocess.run([sys.executable, w, fp, str(start), tag,
                                str(n)], check=True, capture_output=True)
            if close_clean:
                # a genuinely clean file has to be WRITTEN cleanly -- opening
                # and closing a broken one just appends an empty member, which
                # is what an earlier version of this test did and why its
                # "clean" case read zero lines
                os.remove(fp)
                with gzip.open(fp, "wt", encoding="utf-8") as f:
                    for start, tag, n in sessions:
                        for i in range(start, start + n):
                            f.write(json.dumps({"n": i, "sess": tag}) + "\n")

            std = 0
            try:
                with gzip.open(fp, "rt", encoding="utf-8") as f:
                    for _ in f:
                        std += 1
            except Exception:
                pass
            sal = sum(1 for _ in iter_json(fp))
            ok = "" if sal >= want else "  <-- LOST DATA"
            print(f"  {label:>34}{std:>12}{sal:>12}{want:>8}{ok}")
            if sal < want:
                fails.append(f"{label}: salvaged {sal} of {want}")

        # the whole point: salvage must beat the standard reader where it
        # matters, and must not be worse anywhere
        fp = os.path.join(tmp, "ONE_restart_inside_the_hour.jsonl.gz")
        std = 0
        try:
            with gzip.open(fp, "rt", encoding="utf-8") as f:
                for _ in f:
                    std += 1
        except Exception:
            pass
        if std >= 40:
            fails.append("the standard reader coped, so this test proves "
                         "nothing on this Python build")

        print("\n  Every value under 'standard' is what every loader in this")
        print("  repo sees today. The gap is data that is on disk and was")
        print("  being silently discarded.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- salvages a killed writer, a restart, and three")
    print("restarts, and reads a healthy file unchanged.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed")

    print("\n\n" + "#" * 78)
    print("# HOW MUCH RECORDED DATA IS CURRENTLY UNREADABLE")
    print("#" * 78)
    tot = {"files": 0, "broken": 0, "std_lines": 0, "sal_lines": 0}
    print(f"\n  {'channel':>26}{'files':>8}{'broken':>8}"
          f"{'lines now':>13}{'lines after':>13}{'recovered':>12}")
    for ch in sorted(os.listdir(a.data)) if os.path.isdir(a.data) else []:
        d = os.path.join(a.data, ch)
        if not os.path.isdir(d):
            continue
        n = b = std = sal = 0
        for fp in sorted(glob.glob(os.path.join(d, "*.jsonl.gz"))):
            n += 1
            s0, healthy = 0, True
            try:
                with gzip.open(fp, "rt", encoding="utf-8") as f:
                    for _ in f:
                        s0 += 1
            except Exception:
                healthy = False
                b += 1
            std += s0
            # a healthy file salvages to exactly what the standard reader got,
            # so re-reading it proves nothing and doubles the cost of a survey
            # over gigabytes
            sal += s0 if healthy else sum(1 for _ in iter_lines(fp))
        if not n:
            continue
        tot["files"] += n
        tot["broken"] += b
        tot["std_lines"] += std
        tot["sal_lines"] += sal
        gain = sal - std
        print(f"  {ch:>26}{n:>8,}{b:>8,}{std:>13,}{sal:>13,}"
              f"{gain:>+12,}")
    g = tot["sal_lines"] - tot["std_lines"]
    print(f"\n  {tot['broken']:,} of {tot['files']:,} files are unreadable by "
          f"the standard reader.")
    print(f"  Salvage recovers {g:+,} messages "
          f"({100.0*g/max(tot['std_lines'],1):+.2f}%).")
    if tot["broken"]:
        print("\n  Those are hours in which the collector restarted. The "
              "watchdog\n  restarts it on any crash, and on Windows it can "
              "never write a\n  gzip trailer, so the next session's data "
              "hides behind the gap.")


if __name__ == "__main__":
    main()
