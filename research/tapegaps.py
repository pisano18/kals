#!/usr/bin/env python3
# VERSION: 2026-09-12-tg2
"""tapegaps.py -- a second-by-second census of RECORDING HOLES in the tape.

    python research/tapegaps.py --selftest
    python research/tapegaps.py --data C:\\kals\\kalshi_data --jobs 4

WHY THIS EXISTS

`results/RESULTS_replay.md` found, while chasing nine live fills that would
not reconcile, that the `trade` channel goes BLIND for minutes at a time. In
the hour 20260911T05 it printed nothing at all between 05:27:11 and 05:31:00
-- 230 seconds, across every live market at once -- and 374 of that hour's
3,523 recorded seconds sat inside a silent run of 230, 72 or 53 s. A quiet
second on one market is ordinary. A 230-second run with zero prints on any of
twelve markets is not.

That matters because a standing result counts trades from that channel.
`results/SKIM.md` "THE DISCOUNT CLIFF" is built on 45,287 real fills read off
the `trade` tape (`research/pintrades.py`). If the channel has holes, every
COUNT in that table is a LOWER BOUND, and the operator asked how much lower.

This file answers only that. It measures WHERE the tape is silent, for how
long, on which channel, and what the other channels were doing at the same
seconds. It does not re-measure the cliff.

WHAT IT MEASURES, AND THE WITNESSES

Per channel, per second, presence/absence -- from two independent stamps:

  * the MESSAGE stamp: `msg.ts_ms` on `trade` and `orderbook_delta`, and the
    `time` field inside the JSON string `msg.data` on `cfbenchmarks_value`.
    That is the exchange's clock.
  * the RECEIPT stamp `_rx_ms`, written by our collector when the line landed.

Both are reported, because a hole in one and not the other separates "the
exchange sent nothing" from "we buffered and flushed late".

Three channels, and the point of running all three is that they disagree:

  * `cfbenchmarks_value` is a 1/second metronome per index. If IT is silent,
    our socket was down. It is the cleanest witness of our own health that
    the tape contains.
  * `orderbook_delta` runs at ~1,400 messages/second. Alive while `trade` is
    silent means the socket was up and the hole belongs to `trade`.
  * `trade` is the channel under suspicion.

AND THE DECISIVE ONE: `seq`, the exchange's own per-subscription sequence
number. Measured on this tape it takes exactly three shapes across a hole,
and they mean completely different things:

  * CONTIGUOUS -- `seq` either side differs by one. The exchange sent
    nothing. No trade happened, so no count was lost. The silence is REAL.
  * A FORWARD JUMP -- `seq` skips n. n messages were sent and are not on
    disk. The count over that window is short by exactly n.
  * A RESET TO 1 -- a NEW SUBSCRIPTION. Our socket dropped and reconnected.
    How much was missed is NOT KNOWABLE from `seq`, because the counter that
    would have told us was thrown away with the old connection.

The third case is the one that actually dominates, and conflating it with the
first would report a reconnection as "the market was quiet". Verified by hand
on the 230 s hole above: the record that ends it carries `seq` 1, against
3,833,863 on the record before it.

HOW IT STAYS UNDER 150 MB ON 41 GB OF GZIP

A worker holds only a set of present seconds for one hour (<= 3,600 entries)
and decompresses in 4 MB chunks cut at the last newline, so a record never
straddles a chunk and the needle count per chunk equals the newline count
exactly (checked every chunk; `align_fail`). Distinct seconds accumulate as
10-byte ASCII prefixes and become integers once, at the end -- the reason
this runs in minutes is that no per-record integer is built except `seq`.

The PARENT folds each result into a bitmap of one byte per second of tape
(~1.6 MB per channel per stamp) and then DROPS the second lists. An earlier
version kept them and was heading for ~350 MB in the parent on this tape,
which is the sort of thing the resource protocol in CLAUDE.md exists to stop.
`--cache` writes those bitmaps and the per-file metadata, so changing the
report costs seconds instead of re-reading the tape.

A collector restart inside an hour leaves an untrailered gzip member with a
second member appended behind it, and the standard reader then recovers ZERO
lines (see `research/gzsalvage.py`). Left unhandled that is indistinguishable
from an hour-long hole -- it would FABRICATE the very thing being measured.
So the fast path is retried member-by-member on any read error, from the
beginning: presence-per-second is a set, so re-reading the prefix is
idempotent. Two differently-broken files are planted in the self-test.

WHAT IT CANNOT SAY

Nothing here is about our own fills or our own losses. Hard rule, CLAUDE.md
2026-09-10: loss rates come from live fills only, never from the tape. This
file discounts COUNTS -- how much of the tape's population was never
recorded.

NOTHING HERE PLACES AN ORDER.
"""

import argparse
import base64
import glob
import gzip
import json
import os
import re
import sys
import time
import zlib
from collections import defaultdict

CHANNELS = ("trade", "orderbook_delta", "cfbenchmarks_value")

# The message stamp, per channel. On cfbenchmarks_value the exchange clock is
# inside the ESCAPED json string msg.data -- `\"time\":1789102800000` -- so
# the needle carries the backslashes. Verified 1-per-line on all three
# channels: 189,439 / 4,989,410 / 39,470 needles against exactly that many
# newlines in 20260911T05.
TS_NEEDLE = {
    "trade": b'"ts_ms":',
    "orderbook_delta": b'"ts_ms":',
    "cfbenchmarks_value": b'\\"time\\":',
}
# The leading quote is load-bearing: without it this also matches
# `"window_start_ts_ms":` on the cfbenchmarks_value rows.
RX_NEEDLE = b'"_rx_ms":'
SEQ_RE = re.compile(rb'"seq":(\d+)')

MAGIC = b"\x1f\x8b\x08"
CHUNK = 1 << 22
SUBCHUNK = 1 << 16        # salvage feeds this much at a time, so a broken
                          # member costs 64 KB and not everything it had

MIN_RUN = 10              # "a silent run", for reporting
HOLE_RUN = 60             # any run this long makes the hour a HOLE
DEGRADED_FRAC = 0.02      # more than this fraction silent -> DEGRADED
WINDOW = 30               # pinrun.TAU_MAX: the bot trades the last 30 s
TAU_MIN = 3               # pinrun.TAU_MIN. `pintrades.py` keeps a print only
                          # if TAU_MIN <= tau <= TAU_MAX, so the band that
                          # feeds the discount cliff is 28 s wide, not 30.
                          # Both are reported.
CLOSE_MOD = 900           # 15-minute closes, and epoch is a multiple of 900
SEQ_SLACK = 2             # the message that ENDS a hole carries the break,
                          # and its stamp can land a second either side
JUMP_CAP = 20000          # per file, to bound a pathological seq stream


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def _fast_chunks(path):
    """The ordinary reader. Yields decompressed bytes; may raise part-way."""
    with gzip.open(path, "rb") as f:
        while True:
            c = f.read(CHUNK)
            if not c:
                return
            yield c


def _salvage_chunks(path):
    """Member-by-member, for a file a collector restart broke.

    Streams: member offsets are found with mmap so a 223 MB hour is never
    read into the heap. Yields None at each member boundary -- a truncated
    member's last line is a FRAGMENT, not a continuation, and gluing it to
    the next member's first record puts two records under one newline.
    """
    import mmap
    with open(path, "rb") as fh:
        if os.fstat(fh.fileno()).st_size == 0:
            return
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            offs, i = [], 0
            while True:
                j = mm.find(MAGIC, i)
                if j < 0:
                    break
                offs.append(j)
                i = j + 1
            for k, off in enumerate(offs):
                stop = offs[k + 1] if k + 1 < len(offs) else len(mm)
                yield None
                d = zlib.decompressobj(16 + zlib.MAX_WBITS)
                pos = off
                while pos < stop:
                    try:
                        # `stop` is load-bearing. Hand an untrailered member
                        # the NEXT member's header and zlib reads it as a
                        # deflate block, raises, and discards everything it
                        # had already produced -- which cost member one
                        # entirely until the self-test planted that file.
                        out = d.decompress(mm[pos:min(pos + SUBCHUNK, stop)])
                    except zlib.error:
                        break
                    pos += SUBCHUNK
                    if out:
                        yield out
                    if d.eof:
                        break
        finally:
            mm.close()


def _consume(body, ts_needle, st):
    """Fold one newline-terminated block into the running state.

    `body` ALWAYS ends on a newline, so every record in it is whole and the
    i-th `seq` belongs to the same record as the i-th timestamp. That is what
    lets a seq break be dated without parsing a record.
    """
    n = body.count(b"\n")
    st["records"] += n

    parts = body.split(ts_needle)
    secs = [x[:10] for x in parts[1:]]
    st["tsset"].update(secs)

    parts = body.split(RX_NEEDLE)
    st["rxset"].update(x[:10] for x in parts[1:])

    sq = SEQ_RE.findall(body)
    st["seq_n"] += len(sq)
    if len(sq) != n or len(secs) != n:
        st["align_fail"] += 1

    prev = st["prev_seq"]
    jumps = st["seq_jumps"]
    for i, raw in enumerate(sq):
        v = int(raw)
        if prev is None:
            st["seq_first"] = v
        elif v != prev + 1:
            if len(jumps) < JUMP_CAP:
                sec = secs[i] if i < len(secs) else b""
                jumps.append([sec.decode("latin1"), prev, v])
            else:
                st["jumps_dropped"] += 1
        prev = v
    if prev is not None:
        st["prev_seq"] = prev
        st["seq_last"] = prev


def _fresh_state():
    return {"records": 0, "tsset": set(), "rxset": set(), "seq_n": 0,
            "align_fail": 0, "prev_seq": None, "seq_first": None,
            "seq_last": None, "seq_jumps": [], "jumps_dropped": 0}


def _drain(chunks, ts_needle, st):
    tail = b""
    for c in chunks:
        if c is None:
            tail = b""          # member boundary; see _salvage_chunks
            continue
        buf = tail + c
        k = buf.rfind(b"\n")
        if k < 0:
            tail = buf
            continue
        _consume(buf[:k + 1], ts_needle, st)
        tail = buf[k + 1:]
    if tail.endswith(b"\n"):
        _consume(tail, ts_needle, st)


def _clean(sset, lo, hi):
    """Turn 10-byte ASCII prefixes into seconds, dropping anything absurd.

    The set holds at most a few thousand entries, so validating HERE rather
    than per record costs nothing. Two things get thrown out and counted: a
    prefix that is not ten digits, and a second more than a day from the hour
    the filename claims. CLAUDE.md rule 5 forbids inferring a price's unit
    from its magnitude; the same trap exists for time, and a microsecond
    stamp would read as a second 1,000x out.
    """
    good, odd = [], 0
    for v in sset:
        if len(v) == 10 and v.isdigit():
            s = int(v)
            if lo <= s <= hi:
                good.append(s)
                continue
        odd += 1
    good.sort()
    return good, odd


def scan_file(job):
    """One channel-hour -> which seconds it recorded. Runs in a worker."""
    ch, path = job
    hour = os.path.basename(path)[:11]
    h0 = hour_epoch(hour)
    res = {"channel": ch, "hour": hour, "hour_epoch": h0,
           "bytes": os.path.getsize(path), "read_error": "",
           "salvaged": False, "fast_records": 0}
    ts_needle = TS_NEEDLE[ch]

    st = _fresh_state()
    try:
        _drain(_fast_chunks(path), ts_needle, st)
    except Exception as e:
        res["read_error"] = "%s: %s" % (type(e).__name__, str(e)[:90])
        res["fast_records"] = st["records"]
        st = _fresh_state()
        try:
            _drain(_salvage_chunks(path), ts_needle, st)
            res["salvaged"] = True
        except Exception as e2:
            res["read_error"] += " | salvage %s" % type(e2).__name__

    lo, hi = h0 - 86400, h0 + 3600 + 86400
    ts, odd_ts = _clean(st["tsset"], lo, hi)
    rx, odd_rx = _clean(st["rxset"], lo, hi)
    res.update(records=st["records"], ts_secs=ts, rx_secs=rx,
               odd_ts=odd_ts, odd_rx=odd_rx, seq_n=st["seq_n"],
               align_fail=st["align_fail"], seq_first=st["seq_first"],
               seq_last=st["seq_last"], seq_jumps=st["seq_jumps"],
               jumps_dropped=st["jumps_dropped"])
    return res


# --------------------------------------------------------------------------
# time helpers
# --------------------------------------------------------------------------

def hour_epoch(hour):
    """`YYYYMMDDTHH` -> epoch seconds, UTC."""
    import calendar
    return calendar.timegm((int(hour[0:4]), int(hour[4:6]), int(hour[6:8]),
                            int(hour[9:11]), 0, 0, 0, 0, 0))


def iso(sec):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(sec))


def day_of(sec):
    return time.strftime("%Y-%m-%d", time.gmtime(sec))


def merge(intervals):
    out = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def runs_in(bm, base, intervals):
    """Maximal stretches of zero inside the covered intervals.

    bytearray.find is a memchr, so this costs O(number of runs) and not
    O(tape). A run is never allowed to cross out of a covered interval: an
    hour whose FILE IS ABSENT is not a silent hour, it is an unobserved one,
    and merging the two invents a 3,600-second hole out of a missing file.
    """
    out = []
    for a, b in intervals:
        i, j = a - base, b - base
        pos = i
        while pos < j:
            z = bm.find(b"\x00", pos, j)
            if z < 0:
                break
            o = bm.find(b"\x01", z, j)
            end = j if o < 0 else o
            out.append((base + z, end - z))
            pos = end
    return out


# --------------------------------------------------------------------------
# the census
# --------------------------------------------------------------------------

class Sink(object):
    """One byte per second of tape, per channel per stamp.

    Results are folded in as they arrive and their second lists dropped, so
    the parent's footprint does not grow with the tape.
    """

    def __init__(self, hours):
        allh = sorted({h for hs in hours.values() for h in hs})
        self.hours = {ch: sorted(hs) for ch, hs in hours.items()}
        self.base = allh[0]
        self.end = allh[-1] + 3600
        self.n = self.end - self.base
        self.bm = {}
        for ch in hours:
            for src in ("ts", "rx"):
                self.bm[(ch, src)] = bytearray(self.n)

    def add(self, r):
        base, n = self.base, self.n
        for src, key in (("ts", "ts_secs"), ("rx", "rx_secs")):
            bm = self.bm[(r["channel"], src)]
            for s in r.pop(key):
                k = s - base
                if 0 <= k < n:
                    bm[k] = 1
        return r


class Census(object):
    """Coverage, silent runs and per-run classification, off the bitmaps."""

    def __init__(self, sink, per_file):
        self.per_file = per_file
        self.pf = {(r["channel"], r["hour_epoch"]): r
                   for r in per_file.values()}
        self.hours = sink.hours
        self.base = sink.base
        self.end = sink.end
        self.bm = sink.bm
        self.first, self.last, self.cover = {}, {}, {}
        for ch in self.hours:
            filehours = merge([(h, h + 3600) for h in self.hours[ch]])
            for src in ("ts", "rx"):
                bm = self.bm[(ch, src)]
                f, l = bm.find(b"\x01"), bm.rfind(b"\x01")
                if f < 0:
                    self.first[(ch, src)] = self.last[(ch, src)] = None
                    self.cover[(ch, src)] = []
                    continue
                lo, hi = self.base + f, self.base + l + 1
                self.first[(ch, src)] = lo
                self.last[(ch, src)] = hi - 1
                self.cover[(ch, src)] = [
                    (max(a, lo), min(b, hi)) for a, b in filehours
                    if min(b, hi) > max(a, lo)]
        self.runs = {k: runs_in(self.bm[k], self.base, self.cover[k])
                     for k in self.bm}

    def covered(self, ch, src):
        return sum(b - a for a, b in self.cover[(ch, src)])

    def silent(self, ch, src):
        return sum(L for _, L in self.runs[(ch, src)])

    def active_in(self, ch, src, s, L):
        i = s - self.base
        return self.bm[(ch, src)][i:i + L].count(1)

    def cover_in(self, ch, src, s, L):
        tot = 0
        for a, b in self.cover[(ch, src)]:
            tot += max(0, min(b, s + L) - max(a, s))
        return tot

    def mask(self, ch, src, minlen=0):
        """1 where the channel is silent inside a run of at least minlen."""
        m = bytearray(self.end - self.base)
        one = b"\x01"
        for s, L in self.runs[(ch, src)]:
            if L >= minlen:
                i = s - self.base
                m[i:i + L] = one * L
        return m

    def covmask(self, ch, src):
        m = bytearray(self.end - self.base)
        for a, b in self.cover[(ch, src)]:
            m[a - self.base:b - self.base] = b"\x01" * (b - a)
        return m


def seq_breaks(per_file, ch, census=None):
    """second -> list of (prev, next, kind) for every `seq` discontinuity.

    `kind` is the whole point. A FORWARD jump says exactly how many messages
    were sent and lost. A RESET says a new subscription started and the old
    counter is gone, so the loss is UNKNOWABLE -- reporting the two together
    would let a reconnection be read as a quiet market.

    A worker sees one hour, so a break ACROSS an hour boundary is invisible
    to it -- the first record of a file has nothing to be compared against.
    That is not academic: the longest runs on this tape start exactly on an
    hour boundary and span a whole file, so every one of them was reported
    `QUIET` on a comparison that had never been made. With a `census` in
    hand the parent stitches the boundary from each file's own `seq_first`
    and `seq_last`, and dates the break at the first recorded second of the
    later hour -- which is, by construction of `runs_in`, exactly the second
    the silent run ends on.

    The stitch is only legitimate while COVERAGE is continuous. If an hour
    has no file the counter could have done anything in between, so the
    walk restarts rather than inventing a break. An hour whose file exists
    but holds no records does NOT break the walk: coverage is intact, the
    silence is real, and the comparison across it is exactly the one that
    matters.
    """
    out = defaultdict(list)
    for r in per_file.values():
        if r["channel"] != ch:
            continue
        dmg = bool(r["read_error"])
        for sec, prev, nxt in r["seq_jumps"]:
            if not (len(sec) == 10 and sec.isdigit()):
                continue
            kind = "forward" if nxt > prev else "reset"
            out[int(sec)].append((prev, nxt, kind, dmg))
    if census is None:
        return dict(out)

    bm = census.bm.get((ch, "ts"))
    base = census.base
    prev_last = None
    prev_hour = None
    prev_dmg = False
    for h in sorted(census.hours.get(ch, [])):
        if prev_hour is not None and h != prev_hour + 3600:
            prev_last = None            # a MISSING hour: no claim possible
        prev_hour = h
        r = census.pf.get((ch, h))
        if r is None:
            prev_last = None
            continue
        if r.get("seq_first") is None:  # a file with no records at all
            continue                    # coverage intact, counter untouched
        if prev_last is not None and r["seq_first"] != prev_last + 1:
            i = bm.find(b"\x01", h - base, h + 3600 - base)
            if i >= 0:
                kind = ("forward" if r["seq_first"] > prev_last else "reset")
                # A jump is only evidence of a STREAM loss if both files
                # either side of it decompressed cleanly. Where one needed
                # salvage the missing numbers are records whose bytes are on
                # disk inside a broken gzip member -- a different failure,
                # with a different fix, and 98.4% of the total on this tape.
                out[base + i].append((prev_last, r["seq_first"], kind,
                                      bool(r["read_error"]) or prev_dmg))
        prev_last = r["seq_last"]
        prev_dmg = bool(r["read_error"])
    return dict(out)


def classify(c, s, L, breaks):
    """Two independent axes, and they answer different questions.

    VERDICT, from `seq`: did messages exist that we do not have?
    WITNESS, from the other two channels' density: was our socket up?
    """
    d_act = c.active_in("orderbook_delta", "ts", s, L)
    x_act = c.active_in("cfbenchmarks_value", "ts", s, L)
    d_cov = c.cover_in("orderbook_delta", "ts", s, L)
    x_cov = c.cover_in("cfbenchmarks_value", "ts", s, L)

    reset, lost, dmg = False, 0, False
    for t in range(s, s + L + 1 + SEQ_SLACK):
        for prev, nxt, kind, d in breaks.get(t, ()):
            if kind == "reset":
                reset = True
                dmg = dmg or d
            elif nxt - prev - 1 > lost:
                lost = nxt - prev - 1
                dmg = d
    verdict = "RECONNECT" if reset else ("DROPPED" if lost else "QUIET")

    if d_cov == 0 or x_cov == 0:
        witness = "NO_WITNESS"
    elif d_act == 0 and x_act == 0:
        witness = "BOTH_DOWN"
    elif x_act == 0:
        witness = "INDEX_DOWN"
    elif d_act == 0:
        # The informative cell, and it turns out to be the common one: the
        # book stopped with `trade`, while the 1/s index kept ticking on the
        # same socket. That is a market-data subscription failing, not a
        # dead connection. An earlier version folded this into MIXED and
        # hid it.
        witness = "BOOK_DOWN_INDEX_UP"
    elif d_act >= 0.9 * L and x_act >= 0.9 * L:
        witness = "BOOK_AND_INDEX_UP"
    else:
        witness = "MIXED"

    return {"delta_active": d_act, "index_active": x_act,
            "delta_cover": d_cov, "index_cover": x_cov,
            "verdict": verdict, "witness": witness, "seq_lost": lost,
            "seq_reset": reset, "seq_from_damaged_file": dmg}


VERDICT_MEANS = {
    "QUIET": "`seq` contiguous either side -- the exchange sent nothing, so "
             "no count was lost",
    "DROPPED": "`seq` skipped forward -- that many messages were sent and "
               "are not on disk",
    "RECONNECT": "`seq` reset to 1 -- a new subscription. Our socket "
                 "dropped; how much was missed is NOT knowable from `seq`",
}
WITNESS_MEANS = {
    "BOTH_DOWN": "book and 1/s index silent at the same seconds -- the "
                 "socket was down",
    "BOOK_DOWN_INDEX_UP": "the book went silent too, but the 1/s index kept "
                          "ticking on the same socket -- a market-data "
                          "subscription failed, the connection did not",
    "INDEX_DOWN": "the 1/s index metronome stopped, the book did not",
    "BOOK_AND_INDEX_UP": "book and index both running throughout",
    "MIXED": "partial activity on the other channels",
    "NO_WITNESS": "a witness channel has no file for those seconds",
}


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def build_report(c, hours_all, elapsed, data, prov=""):
    L = []
    P = L.append
    per_file = c.per_file
    pf = c.pf
    brk = seq_breaks(per_file, "trade", c)

    # ---- per hour health -------------------------------------------------
    health = {}
    for ch in CHANNELS:
        if ch not in c.hours:
            continue
        for h in hours_all:
            key = (ch, h)
            if key not in pf:
                health[key] = {"flag": "MISSING", "cov": 0, "silent": 0,
                               "longest": 0, "frac": 0.0, "records": 0,
                               "salvaged": False, "read_error": ""}
                continue
            cov = c.cover_in(ch, "ts", h, 3600)
            sil = cov - c.active_in(ch, "ts", h, 3600)
            longest = 0
            for s, ln in c.runs[(ch, "ts")]:
                if s < h + 3600 and s + ln > h:
                    longest = max(longest, ln)
            frac = (sil / cov) if cov else 0.0
            flag = ("HOLE" if longest >= HOLE_RUN
                    else "DEGRADED" if frac > DEGRADED_FRAC else "OK")
            health[key] = {"flag": flag, "cov": cov, "silent": sil,
                           "longest": longest, "frac": frac,
                           "records": pf[key]["records"],
                           "salvaged": pf[key]["salvaged"],
                           "read_error": pf[key]["read_error"]}

    # ---- the trading window ---------------------------------------------
    m10 = c.mask("trade", "ts", MIN_RUN)
    many = c.mask("trade", "ts", 1)
    cmask = c.covmask("trade", "ts")
    tauw = WINDOW - TAU_MIN + 1
    # day -> [closes, window s, in run>=MIN_RUN, silent at all,
    #         tau-band s, tau in run>=MIN_RUN, tau silent at all]
    win = defaultdict(lambda: [0, 0, 0, 0, 0, 0, 0])
    first_close = ((c.base + CLOSE_MOD - 1) // CLOSE_MOD) * CLOSE_MOD
    for close in range(first_close, c.end + 1, CLOSE_MOD):
        a, b = close - WINDOW, close
        if a < c.base or b > c.end:
            continue
        i, j = a - c.base, b - c.base
        if cmask[i:j].count(1) != WINDOW:
            continue                        # the window is not fully taped
        # tau = close - second, so tau in [TAU_MIN, WINDOW] is the seconds
        # [close - WINDOW, close - TAU_MIN] inclusive
        j2 = j - TAU_MIN + 1
        row = win[day_of(a)]
        row[0] += 1
        row[1] += WINDOW
        row[2] += m10[i:j].count(1)
        row[3] += many[i:j].count(1)
        row[4] += tauw
        row[5] += m10[i:j2].count(1)
        row[6] += many[i:j2].count(1)

    # And again over ONLY the hours flagged OK, which is what a later stage
    # excluding bad hours would actually see. This is the actionable number:
    # the discount that SURVIVES throwing away the known-bad hours.
    masks = {}
    for lab, keep in (("OK", ("OK",)), ("NOHOLE", ("OK", "DEGRADED"))):
        m = bytearray(c.end - c.base)
        for h in hours_all:
            if health.get(("trade", h), {}).get("flag") in keep:
                i = h - c.base
                m[i:i + 3600] = b"\x01" * 3600
        masks[lab] = m
    sub = {lab: [0, 0, 0] for lab in masks}     # closes, window s, in run
    for close in range(first_close, c.end + 1, CLOSE_MOD):
        a, b = close - WINDOW, close
        if a < c.base or b > c.end:
            continue
        i, j = a - c.base, b - c.base
        if cmask[i:j].count(1) != WINDOW:
            continue
        hit = m10[i:j].count(1)
        for lab, m in masks.items():
            if m[i:j].count(1) == WINDOW:
                sub[lab][0] += 1
                sub[lab][1] += WINDOW
                sub[lab][2] += hit
    okclose, oktot, ok10 = sub["OK"]
    nhclose, nhtot, nh10 = sub["NOHOLE"]

    wtot0 = sum(v[1] for v in win.values())
    w10_0 = sum(v[2] for v in win.values())
    wtot = wtot0
    w10 = w10_0
    wany = sum(v[3] for v in win.values())
    ttot = sum(v[4] for v in win.values())
    t10 = sum(v[5] for v in win.values())
    tany = sum(v[6] for v in win.values())
    nclose = sum(v[0] for v in win.values())

    # ---- runs ------------------------------------------------------------
    allruns = []
    for ch in CHANNELS:
        if ch not in c.hours:
            continue
        for src in ("ts", "rx"):
            for s, ln in c.runs[(ch, src)]:
                if ln < MIN_RUN:
                    continue
                rec = {"channel": ch, "source": src, "start": s,
                       "start_iso": iso(s), "length": ln,
                       "s_after_close": s % CLOSE_MOD}
                if ch == "trade" and src == "ts":
                    rec.update(classify(c, s, ln, brk))
                allruns.append(rec)
    allruns.sort(key=lambda r: -r["length"])
    trade_runs = [r for r in allruns
                  if r["channel"] == "trade" and r["source"] == "ts"]
    ge30 = [r for r in trade_runs if r["length"] >= 30]

    # ---- per day ---------------------------------------------------------
    days = sorted({day_of(h) for h in hours_all})
    daily = {}
    for d in days:
        row = {}
        for ch in CHANNELS:
            if ch not in c.hours:
                continue
            cov = sil = covrx = silrx = rec = 0
            nhole = ndeg = nmiss = 0
            for h in hours_all:
                if day_of(h) != d:
                    continue
                k = (ch, h)
                if k not in pf:
                    nmiss += 1
                    continue
                cv = c.cover_in(ch, "ts", h, 3600)
                cov += cv
                sil += cv - c.active_in(ch, "ts", h, 3600)
                cv2 = c.cover_in(ch, "rx", h, 3600)
                covrx += cv2
                silrx += cv2 - c.active_in(ch, "rx", h, 3600)
                rec += pf[k]["records"]
                f = health[k]["flag"]
                nhole += f == "HOLE"
                ndeg += f == "DEGRADED"
            row[ch] = {"cov": cov, "silent": sil, "cov_rx": covrx,
                       "silent_rx": silrx, "records": rec,
                       "hole_hours": nhole, "degraded_hours": ndeg,
                       "missing_hours": nmiss}
        row["window"] = win.get(d, [0, 0, 0, 0, 0, 0, 0])
        daily[d] = row

    # ======================================================================
    P("# RESULTS_tapegaps -- where the tape is SILENT, second by second")
    P("")
    P("`research/tapegaps.py`, run %s. Data `%s`, %d channel-hours, %.1f GB "
      "of gzip.%s" %
      (iso(time.time()), data, len(per_file),
       sum(r["bytes"] for r in per_file.values()) / 2 ** 30,
       prov or (" %.0f s wall." % elapsed)))
    P("")
    tot_rec = sum(r["records"] for r in per_file.values())
    P("**%s records read.** %s." %
      ("{:,}".format(tot_rec),
       "; ".join("`%s` %s records over %d hours" %
                 (ch, "{:,}".format(sum(r["records"] for r in
                                        per_file.values()
                                        if r["channel"] == ch)),
                  len(c.hours.get(ch, [])))
                 for ch in CHANNELS if ch in c.hours)))
    P("")
    bad = sorted((r["channel"], r["hour"], r["read_error"],
                  r["fast_records"], r["records"])
                 for r in per_file.values() if r["read_error"])
    nsalv = sum(1 for r in per_file.values() if r["salvaged"])
    nalign = sum(1 for r in per_file.values() if r["align_fail"])
    nodd = sum(1 for r in per_file.values() if r["odd_ts"] or r["odd_rx"])
    P("Reader integrity: **%d** channel-hours raised on the ordinary reader, "
      "**%d** were recovered member-by-member, **%d** had a chunk whose "
      "needle count disagreed with its newline count, **%d** carried a "
      "timestamp that was not ten digits or was more than a day from its own "
      "filename." % (len(bad), nsalv, nalign, nodd))
    for ch, hr, err, fastn, gotn in bad[:12]:
        P("  * `%s/%s` -- %s (ordinary reader %s records, salvage %s)" %
          (ch, hr, err, "{:,}".format(fastn), "{:,}".format(gotn)))
    P("")

    # ---- headline --------------------------------------------------------
    tcov = c.covered("trade", "ts")
    tsil = c.silent("trade", "ts")
    s10 = sum(L2 for _, L2 in c.runs[("trade", "ts")] if L2 >= MIN_RUN)
    s60 = sum(L2 for _, L2 in c.runs[("trade", "ts")] if L2 >= HOLE_RUN)
    P("## The number that discounts the discount cliff")
    P("")
    P("| `trade` channel | seconds | of covered |")
    P("|---|---|---|")
    P("| covered by a file, between the first and last print | %s | 100%% |"
      % "{:,}".format(tcov))
    P("| with at least one print | %s | %.2f%% |" %
      ("{:,}".format(tcov - tsil), 100.0 * (tcov - tsil) / max(tcov, 1)))
    P("| SILENT | %s | **%.2f%%** |" %
      ("{:,}".format(tsil), 100.0 * tsil / max(tcov, 1)))
    P("| ... inside a silent run >= %d s | %s | %.2f%% |" %
      (MIN_RUN, "{:,}".format(s10), 100.0 * s10 / max(tcov, 1)))
    P("| ... inside a silent run >= %d s | %s | %.2f%% |" %
      (HOLE_RUN, "{:,}".format(s60), 100.0 * s60 / max(tcov, 1)))
    P("")
    P("**The window that matters is the last %d s before each 15-minute "
      "close** (`pinrun.TAU_MAX` = %d). Over **%s fully-taped close "
      "windows** (%s window-seconds):" %
      (WINDOW, WINDOW, "{:,}".format(nclose), "{:,}".format(wtot)))
    P("")
    P("| window seconds | count | fraction |")
    P("|---|---|---|")
    P("| inside a `trade` silent run >= %d s | %s | **%.3f%%** |" %
      (MIN_RUN, "{:,}".format(w10), 100.0 * w10 / max(wtot, 1)))
    P("| silent at all (any run length) | %s | %.3f%% |" %
      ("{:,}".format(wany), 100.0 * wany / max(wtot, 1)))
    P("")
    P("Narrowed to the band `pintrades.py` actually keeps -- `TAU_MIN <= tau "
      "<= TAU_MAX`, so tau in [%d, %d], %d seconds per close rather than %d "
      "(%s window-seconds):" %
      (TAU_MIN, WINDOW, tauw, WINDOW, "{:,}".format(ttot)))
    P("")
    P("| window seconds, tau in [%d, %d] | count | fraction |" %
      (TAU_MIN, WINDOW))
    P("|---|---|---|")
    P("| inside a `trade` silent run >= %d s | %s | **%.3f%%** |" %
      (MIN_RUN, "{:,}".format(t10), 100.0 * t10 / max(ttot, 1)))
    P("| silent at all (any run length) | %s | %.3f%% |" %
      ("{:,}".format(tany), 100.0 * tany / max(ttot, 1)))
    P("")
    P("**And the actionable version -- with a warning about the "
      "threshold.** The tables above pool everything, including the hours "
      "this file flags unusable. Restricting to closes whose whole window "
      "sits in a good hour gives:")
    P("")
    P("| closes kept | closes | window s | in a run >= %d s | fraction |"
      % MIN_RUN)
    P("|---|---|---|---|---|")
    P("| all fully-taped | %s | %s | %s | %.3f%% |" %
      ("{:,}".format(nclose), "{:,}".format(wtot0), "{:,}".format(w10_0),
       100.0 * w10_0 / max(wtot0, 1)))
    P("| hours not flagged `HOLE` | %s | %s | %s | **%.3f%%** |" %
      ("{:,}".format(nhclose), "{:,}".format(nhtot), "{:,}".format(nh10),
       100.0 * nh10 / max(nhtot, 1)))
    P("| hours flagged `OK` (>%.0f%% silent = DEGRADED) | %s | %s | %s | "
      "%.3f%% |" %
      (100 * DEGRADED_FRAC, "{:,}".format(okclose), "{:,}".format(oktot),
       "{:,}".format(ok10), 100.0 * ok10 / max(oktot, 1)))
    P("")
    P("**Read the middle row, not the bottom one, and here is why.** The "
      "`DEGRADED` threshold is %.0f%% of an hour's seconds silent, and on "
      "this channel that is BELOW the baseline: the median `trade` hour is "
      "%.2f%% silent with no long run in it at all. So %.0f%% flags "
      "%s of %s hours and leaves %s `OK`, which is not a measurement of "
      "anything -- it is a threshold set under the noise floor. The "
      "distribution is printed below so a later stage can pick its own. "
      "`HOLE` (any run >= %d s) does not have this problem and is the "
      "exclusion that works." %
      (100 * DEGRADED_FRAC, 100 * _median_frac(health, hours_all, "trade"),
       100 * DEGRADED_FRAC,
       "{:,}".format(sum(1 for h in hours_all
                         if health.get(("trade", h), {}).get("flag")
                         == "DEGRADED")),
       "{:,}".format(sum(1 for h in hours_all
                         if health.get(("trade", h), {}).get("flag")
                         != "MISSING")),
       "{:,}".format(sum(1 for h in hours_all
                         if health.get(("trade", h), {}).get("flag")
                         == "OK")),
       HOLE_RUN))
    P("")

    # ---- where in the cycle ----------------------------------------------
    P("## WHERE in the 15-minute cycle the holes sit")
    P("")
    P("`seq` says whether a hole hid anything; this says whether it hid "
      "anything we would have traded. A market settles at the close and its "
      "replacement has no flow for a while, so silence just AFTER a close is "
      "structural. The bot trades just BEFORE one.")
    P("")
    buck = [(0, 15, "0-15 s after a close (settlement dead zone)"),
            (15, 60, "15-60 s after"),
            (60, 300, "1-5 min after"),
            (300, 870, "5 min after .. 30 s before the next close"),
            (870, 900, "**the last 30 s before a close -- the window**")]
    P("Split by length, because the two populations are nothing alike: the "
      "ordinary %d-%d s gap is a thin book, and a run over %d s is an "
      "outage. Pooling them puts an hour-long outage in the dead-zone "
      "bucket and makes the structural silence look enormous." %
      (MIN_RUN, HOLE_RUN - 1, HOLE_RUN))
    P("")
    P("| start of the run, relative to the 15-min cycle | runs %d-%d s | "
      "their silent s | runs >= %d s | their silent s | longest |" %
      (MIN_RUN, HOLE_RUN - 1, HOLE_RUN))
    P("|---|---|---|---|---|---|")
    for lo, hi, lab in buck:
        sel = [r for r in trade_runs if lo <= r["s_after_close"] < hi]
        sm = [r for r in sel if r["length"] < HOLE_RUN]
        bg = [r for r in sel if r["length"] >= HOLE_RUN]
        P("| %s | %s | %s | %s | %s | %d |" %
          (lab, "{:,}".format(len(sm)),
           "{:,}".format(sum(r["length"] for r in sm)),
           "{:,}".format(len(bg)),
           "{:,}".format(sum(r["length"] for r in bg)),
           max([r["length"] for r in sel] or [0])))
    sm = [r for r in trade_runs if r["length"] < HOLE_RUN]
    bg = [r for r in trade_runs if r["length"] >= HOLE_RUN]
    P("| **all** | **%s** | **%s** | **%s** | **%s** | **%d** |" %
      ("{:,}".format(len(sm)), "{:,}".format(sum(r["length"] for r in sm)),
       "{:,}".format(len(bg)), "{:,}".format(sum(r["length"] for r in bg)),
       max([r["length"] for r in trade_runs] or [0])))
    P("")

    # ---- the seq verdict -------------------------------------------------
    P("## Did the silence hide anything? the `seq` verdict")
    P("")
    P("Every `trade` silent run >= 30 s, on the exchange's own sequence "
      "number. This is not an inference from message density -- it is the "
      "exchange saying how many messages it sent.")
    P("")
    vsplit = defaultdict(lambda: [0, 0, 0, 0])
    for r in ge30:
        row = vsplit[r["verdict"]]
        row[0] += 1
        row[1] += r["length"]
        if r["seq_from_damaged_file"]:
            row[3] += r["seq_lost"]
        else:
            row[2] += r["seq_lost"]
    P("**The two columns of lost messages are not the same failure and must "
      "not be added.** `in a clean file` is a stream loss: the exchange sent "
      "a message, the socket or the collector dropped it, and it was never "
      "written. `next to a damaged gzip` is a DISK loss: the bytes were "
      "written, then a collector restart left a member with no trailer and "
      "the decompressor cannot reach them (see `research/gzsalvage.py`). The "
      "second kind is concentrated in a handful of hours, is already flagged "
      "`HOLE`/`DEGRADED` below, and is excludable; the first kind is spread "
      "thin and is not.")
    P("")
    P("| verdict | runs | silent seconds | lost, in a clean file | lost, "
      "next to a damaged gzip | meaning |")
    P("|---|---|---|---|---|---|")
    for v in ("QUIET", "DROPPED", "RECONNECT"):
        if v not in vsplit:
            continue
        n2, sec, clean, dm = vsplit[v]
        cell = ("unknowable" if v == "RECONNECT" else "{:,}".format(clean))
        P("| `%s` | %d | %s | %s | %s | %s |" %
          (v, n2, "{:,}".format(sec), cell,
           ("unknowable" if v == "RECONNECT" else "{:,}".format(dm)),
           VERDICT_MEANS[v]))
    P("| **total** | **%d** | **%s** | **%s** | **%s** | |" %
      (len(ge30), "{:,}".format(sum(r["length"] for r in ge30)),
       "{:,}".format(sum(v[2] for v in vsplit.values())),
       "{:,}".format(sum(v[3] for v in vsplit.values()))))
    P("")
    P("And the density witnesses on the same runs -- a cross-tab, because "
      "the two axes are independent and the interesting cell is a hole whose "
      "book and index kept running:")
    P("")
    wits = sorted({r["witness"] for r in ge30})
    if wits:
        P("| verdict | " + " | ".join("`%s`" % w for w in wits) + " |")
        P("|---" * (len(wits) + 1) + "|")
        for v in ("QUIET", "DROPPED", "RECONNECT"):
            if v not in vsplit:
                continue
            cells = [sum(1 for r in ge30
                         if r["verdict"] == v and r["witness"] == w)
                     for w in wits]
            P("| `%s` | " % v + " | ".join(str(x) for x in cells) + " |")
        P("")
        for w in wits:
            P("* `%s` -- %s" % (w, WITNESS_MEANS.get(w, "")))
        P("")
    tb = seq_breaks(per_file, "trade", c)
    nfwd = sum(max(0, nxt - prev - 1) for v in tb.values()
               for prev, nxt, k, d in v if k == "forward" and not d)
    nfwdn = sum(1 for v in tb.values() for _, _, k, d in v
                if k == "forward" and not d)
    nres = sum(1 for v in tb.values() for _, _, k, _d in v if k == "reset")
    trec = sum(r["records"] for r in per_file.values()
               if r["channel"] == "trade")
    P("Channel-wide, wherever they fall, and SPLIT ON THE SAME LINE: in "
      "files that decompressed cleanly `trade` has **%s** forward `seq` "
      "jumps totalling **%s missing sequence numbers** against %s records "
      "read -- **%.4f%% of the stream** -- plus **%s subscription resets**. "
      "Everything else sits beside a damaged gzip." %
      ("{:,}".format(nfwdn), "{:,}".format(nfwd), "{:,}".format(trec),
       100.0 * nfwd / max(trec, 1), "{:,}".format(nres)))
    P("")
    P("| channel | records | clean-file jumps | numbers missing | % of "
      "stream | numbers missing beside a damaged gzip | resets |")
    P("|---|---|---|---|---|---|---|")
    for ch in CHANNELS:
        if ch not in c.hours:
            continue
        b = seq_breaks(per_file, ch, c)
        fwd = [(p, n3) for v in b.values() for p, n3, k, d in v
               if k == "forward" and not d]
        dmg = [(p, n3) for v in b.values() for p, n3, k, d in v
               if k == "forward" and d]
        res = sum(1 for v in b.values() for _, _, k, _d in v if k == "reset")
        nrec = sum(r["records"] for r in per_file.values()
                   if r["channel"] == ch)
        miss = sum(n3 - p - 1 for p, n3 in fwd)
        P("| `%s` | %s | %s | %s | %.4f%% | %s | %s |" %
          (ch, "{:,}".format(nrec), "{:,}".format(len(fwd)),
           "{:,}".format(miss), 100.0 * miss / max(nrec, 1),
           "{:,}".format(sum(n3 - p - 1 for p, n3 in dmg)),
           "{:,}".format(res)))
    P("")

    # ---- worst 20 --------------------------------------------------------
    P("## The worst 20 `trade` silent runs")
    P("")
    P("`s after close` is where the run starts in the 15-minute cycle: 0 is "
      "the close itself, 870-899 is the window the bot trades.")
    P("")
    P("| start (UTC) | length s | s after close | book s active | index s "
      "active | `seq` | verdict | witness |")
    P("|---|---|---|---|---|---|---|---|")
    for r in trade_runs[:20]:
        P("| %s | **%d** | %d | %d/%d | %d/%d | %s | `%s` | `%s` |" %
          (r["start_iso"], r["length"], r["s_after_close"],
           r["delta_active"], r["length"], r["index_active"], r["length"],
           (("lost %s%s" % ("{:,}".format(r["seq_lost"]),
                            " (damaged gzip)"
                            if r["seq_from_damaged_file"] else ""))
            if r["seq_lost"] else
            ("reset" if r["seq_reset"] else "contiguous")),
           r["verdict"], r["witness"]))
    P("")
    P("### the worst 10 on each of the other two channels, for contrast")
    P("")
    P("| channel | start (UTC) | length s | s after close |")
    P("|---|---|---|---|")
    for ch in ("orderbook_delta", "cfbenchmarks_value"):
        got = [r for r in allruns
               if r["channel"] == ch and r["source"] == "ts"][:10]
        for r in got:
            P("| `%s` | %s | %d | %d |" %
              (ch, r["start_iso"], r["length"], r["s_after_close"]))
        if not got:
            P("| `%s` | -- | -- | nothing >= %d s |" % (ch, MIN_RUN))
    P("")

    # ---- stamps ----------------------------------------------------------
    P("## message stamp vs receipt stamp")
    P("")
    P("A hole in the exchange clock but not in ours means the exchange sent "
      "nothing; a hole in ours but not the exchange's means we flushed late.")
    P("")
    P("| channel | silent s by `ts_ms` | silent s by `_rx_ms` | runs >= %d s "
      "by `ts_ms` | by `_rx_ms` |" % MIN_RUN)
    P("|---|---|---|---|---|")
    for ch in CHANNELS:
        if ch not in c.hours:
            continue
        P("| `%s` | %s (%.2f%%) | %s (%.2f%%) | %d | %d |" %
          (ch, "{:,}".format(c.silent(ch, "ts")),
           100.0 * c.silent(ch, "ts") / max(c.covered(ch, "ts"), 1),
           "{:,}".format(c.silent(ch, "rx")),
           100.0 * c.silent(ch, "rx") / max(c.covered(ch, "rx"), 1),
           sum(1 for _, L2 in c.runs[(ch, "ts")] if L2 >= MIN_RUN),
           sum(1 for _, L2 in c.runs[(ch, "rx")] if L2 >= MIN_RUN)))
    P("")

    # ---- per day ---------------------------------------------------------
    P("## Per day")
    P("")
    P("`silent` counts seconds with zero messages on that channel, only "
      "inside hours whose file exists. `win` is the last %d s before each "
      "fully-taped 15-minute close; `tau` narrows it to tau in [%d, %d]." %
      (WINDOW, TAU_MIN, WINDOW))
    P("")
    P("| day | hrs | trade silent s | %% | book silent s | %% | index silent "
      "s | %% | closes | win s in run>=%ds | %% | tau s in run>=%ds | %% |"
      % (MIN_RUN, MIN_RUN))
    P("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for d in days:
        row = daily[d]
        t = row.get("trade", {})
        o = row.get("orderbook_delta", {})
        x = row.get("cfbenchmarks_value", {})
        w = row["window"]
        nh = len([h for h in hours_all if day_of(h) == d])
        P("| %s | %d | %s | %.2f | %s | %.2f | %s | %.2f | %d | %s | %.2f | "
          "%s | **%.2f** |" %
          (d, nh,
           "{:,}".format(t.get("silent", 0)),
           100.0 * t.get("silent", 0) / max(t.get("cov", 1), 1),
           "{:,}".format(o.get("silent", 0)),
           100.0 * o.get("silent", 0) / max(o.get("cov", 1), 1),
           "{:,}".format(x.get("silent", 0)),
           100.0 * x.get("silent", 0) / max(x.get("cov", 1), 1),
           w[0], "{:,}".format(w[2]), 100.0 * w[2] / max(w[1], 1),
           "{:,}".format(w[5]), 100.0 * w[5] / max(w[4], 1)))
    P("| **all** | **%d** | **%s** | **%.2f** | **%s** | **%.2f** | **%s** | "
      "**%.2f** | **%d** | **%s** | **%.2f** | **%s** | **%.2f** |" %
      (len(hours_all),
       "{:,}".format(c.silent("trade", "ts")),
       100.0 * c.silent("trade", "ts") / max(c.covered("trade", "ts"), 1),
       "{:,}".format(c.silent("orderbook_delta", "ts")),
       100.0 * c.silent("orderbook_delta", "ts")
       / max(c.covered("orderbook_delta", "ts"), 1),
       "{:,}".format(c.silent("cfbenchmarks_value", "ts")),
       100.0 * c.silent("cfbenchmarks_value", "ts")
       / max(c.covered("cfbenchmarks_value", "ts"), 1),
       nclose, "{:,}".format(w10), 100.0 * w10 / max(wtot, 1),
       "{:,}".format(t10), 100.0 * t10 / max(ttot, 1)))
    P("")

    # ---- health ----------------------------------------------------------
    P("## Per-hour recording health")
    P("")
    P("`HOLE` = a silent run >= %d s overlaps the hour. `DEGRADED` = more "
      "than %.0f%% of its covered seconds silent, with no run that long. "
      "`MISSING` = no file on that channel for that hour. A later stage "
      "wanting a clean tape excludes `HOLE` and `DEGRADED`; the "
      "machine-readable list is `results/tapegaps_hours.json`, and every run "
      ">= %d s with its classification is `results/tapegaps_runs.json`." %
      (HOLE_RUN, 100 * DEGRADED_FRAC, MIN_RUN))
    P("")
    P("Per-hour silent fraction, so the thresholds can be judged rather "
      "than trusted. A channel whose median hour is already above the "
      "`DEGRADED` line cannot be filtered by it.")
    P("")
    P("| channel | hours | p10 | p25 | **p50** | p75 | p90 | p99 | max |")
    P("|---|---|---|---|---|---|---|---|---|")
    for ch in CHANNELS:
        if ch not in c.hours:
            continue
        fr = sorted(health[(ch, h)]["frac"] for h in hours_all
                    if health[(ch, h)]["flag"] != "MISSING")
        if not fr:
            continue
        def q(x, fr=fr):
            return 100.0 * fr[min(len(fr) - 1, int(len(fr) * x))]
        P("| `%s` | %d | %.2f%% | %.2f%% | **%.2f%%** | %.2f%% | %.2f%% | "
          "%.2f%% | %.2f%% |" %
          (ch, len(fr), q(.10), q(.25), q(.50), q(.75), q(.90), q(.99),
           100.0 * fr[-1]))
    P("")
    P("| channel | OK | DEGRADED | HOLE | MISSING |")
    P("|---|---|---|---|---|")
    for ch in CHANNELS:
        if ch not in c.hours:
            continue
        cnt = defaultdict(int)
        for h in hours_all:
            cnt[health[(ch, h)]["flag"]] += 1
        P("| `%s` | %d | %d | %d | %d |" %
          (ch, cnt["OK"], cnt["DEGRADED"], cnt["HOLE"], cnt["MISSING"]))
    P("")
    for ch in CHANNELS:
        if ch not in c.hours:
            continue
        P("**`%s`** -- `hour(longest run s/total silent s)`" % ch)
        P("")
        for lab in ("HOLE", "DEGRADED", "MISSING"):
            got = [h for h in hours_all if health[(ch, h)]["flag"] == lab]
            if lab == "MISSING":
                txt = ", ".join(time.strftime("%m-%dT%H", time.gmtime(h))
                                for h in got)
            else:
                txt = ", ".join(
                    "%s(%d/%d)" % (time.strftime("%m-%dT%H", time.gmtime(h)),
                                   health[(ch, h)]["longest"],
                                   health[(ch, h)]["silent"]) for h in got)
            P("* %s (%d): %s" % (lab, len(got), txt if got else "--"))
        P("")

    # ---- the paragraph ---------------------------------------------------
    P("## What this means for the discount cliff")
    P("")
    P(_paragraph(c, tcov, tsil, s10, wtot, w10, wany, ttot, t10, nclose,
                 ge30, vsplit, trade_runs, nfwd, nres, trec,
                 nhclose, nhtot, nh10))
    P("")
    P("## What this does NOT say")
    P("")
    P("* Nothing here is a loss rate and nothing here is about our own "
      "fills. CLAUDE.md 2026-09-10: loss rates come from live fills only. "
      "This file discounts COUNTS.")
    P("* A silent second is not a second with no trading. It is a second "
      "with no RECORDED trade. Where `seq` is contiguous across the silence "
      "the two are the same thing; where it jumps or resets, they are not.")
    P("* A `RECONNECT` run's loss is unknowable, not zero. `seq` restarting "
      "at 1 destroys the only evidence of how many messages the old "
      "subscription would have carried. Any count over such a window is a "
      "lower bound by an unmeasured amount, and this file will not guess it.")
    P("* The witness columns use `orderbook_delta` and `cfbenchmarks_value` "
      "presence as evidence of socket health. That is density, not proof: a "
      "channel can be subscribed and idle. Only `seq` proves a message "
      "existed and is absent.")
    P("* Runs are cut at the edge of a covered interval, so a hole spanning "
      "a MISSING hour is reported as two runs and not one.")
    P("* A `seq` jump beside a file that needed salvage is NOT a stream "
      "loss. The bytes were written and a broken gzip member is in the way, "
      "so those records may still be recoverable and are certainly not "
      "evidence that the exchange-to-collector path dropped anything. The "
      "two are reported in separate columns everywhere and must never be "
      "added together.")
    P("* The bias this leaves is not measured here and cannot be. A count "
      "over a window containing a hole is biased only if what the hole hid "
      "differs from what it did not, and no test on this tape can settle "
      "that -- the hidden prints are, by construction, not on it.")
    P("")
    return "\n".join(L), health, allruns, daily


def _median_frac(health, hours_all, ch):
    fr = sorted(health[(ch, h)]["frac"] for h in hours_all
                if health.get((ch, h), {}).get("flag") != "MISSING")
    return fr[len(fr) // 2] if fr else 0.0


def _paragraph(c, tcov, tsil, s10, wtot, w10, wany, ttot, t10, nclose, ge30,
               vsplit, trade_runs, nfwd, nres, trec, okclose, oktot, ok10):
    inwin = [r for r in trade_runs if r["s_after_close"] >= CLOSE_MOD - WINDOW]
    deadz = [r for r in trade_runs if r["s_after_close"] < 60]
    nq = vsplit.get("QUIET", [0, 0, 0])[0]
    nd = vsplit.get("DROPPED", [0, 0, 0])[0]
    nr = vsplit.get("RECONNECT", [0, 0, 0])[0]
    worst = trade_runs[0] if trade_runs else None
    return (
        "Over the whole tape the `trade` channel is silent for %s of %s "
        "covered seconds (**%.2f%%**), %s of them inside a run of %d s or "
        "longer. **In the window the bot trades -- the last %d s before a "
        "close -- %.3f%% of window-seconds fall inside a silent run >= %d s** "
        "(%s of %s, over %s fully-taped closes), %.3f%% are silent at any run "
        "length, and **narrowing to the band `pintrades.py` keeps (tau in "
        "[%d, %d]) gives %.3f%%. Excluding only the hours carrying a run "
        ">= 60 s -- the `HOLE` flag, the one whose threshold is above this "
        "channel's noise floor -- it is %.3f%% over the %s closes that "
        "survive.** That is the discount on the counts. Of the "
        "%s `trade` runs >= %d s, **%s start in the last %d s before a "
        "close** and **%s start within 60 s AFTER one**, which is the "
        "settlement dead zone: the old market has settled and its "
        "replacement has no flow yet. **On whether the holes are "
        "collector-side or exchange-side, `seq` is decisive.** Of the %d "
        "silent runs of 30 s or more: %d end with `seq` contiguous (the "
        "exchange sent nothing, so no count was lost), %d end with a forward "
        "`seq` jump (messages sent and missing, and countable), and %d end "
        "with `seq` RESET TO 1 -- a new subscription, meaning our socket "
        "dropped and reconnected. **The size of the loss has to be split or "
        "it is off by two orders of magnitude:** in files that decompressed "
        "cleanly the `trade` stream is missing **%s sequence numbers against "
        "%s records, %.4f%%**, while a further %s sit beside a gzip a "
        "collector restart broke -- bytes that were written and cannot be "
        "decompressed, concentrated in the hours flagged below, a different "
        "failure with a different fix. Plus %s subscription resets. The "
        "reset case is the honest problem: it proves the hole is ours, and "
        "it destroys the evidence of how much it cost, so those windows are "
        "a lower bound by an unmeasured amount rather than by zero.%s" %
        ("{:,}".format(tsil), "{:,}".format(tcov),
         100.0 * tsil / max(tcov, 1), "{:,}".format(s10), MIN_RUN,
         WINDOW, 100.0 * w10 / max(wtot, 1), MIN_RUN,
         "{:,}".format(w10), "{:,}".format(wtot), "{:,}".format(nclose),
         100.0 * wany / max(wtot, 1), TAU_MIN, WINDOW,
         100.0 * t10 / max(ttot, 1),
         100.0 * ok10 / max(oktot, 1), "{:,}".format(okclose),
         "{:,}".format(len(trade_runs)), MIN_RUN,
         "{:,}".format(len(inwin)), WINDOW, "{:,}".format(len(deadz)),
         len(ge30), nq, nd, nr,
         "{:,}".format(nfwd), "{:,}".format(trec),
         100.0 * nfwd / max(trec, 1),
         "{:,}".format(sum(v[3] for v in vsplit.values())),
         "{:,}".format(nres),
         ("" if worst is None else
          " The single worst run is %d s from %s, %d s after a close."
          % (worst["length"], worst["start_iso"], worst["s_after_close"]))))


# --------------------------------------------------------------------------
# cache
# --------------------------------------------------------------------------

def save_cache(path, sink, per_file, scan_seconds=None):
    blob = {"version": 3, "base": sink.base, "end": sink.end,
            "scan_seconds": scan_seconds, "scan_utc": iso(time.time()),
            "hours": {ch: list(hs) for ch, hs in sink.hours.items()},
            "bm": {"%s|%s" % k: base64.b64encode(bytes(v)).decode("ascii")
                   for k, v in sink.bm.items()},
            "per_file": list(per_file.values())}
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(blob, f)


def load_cache(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        blob = json.load(f)
    hours = {ch: [int(h) for h in hs] for ch, hs in blob["hours"].items()}
    sink = Sink(hours)
    if sink.base != blob["base"] or sink.end != blob["end"]:
        raise ValueError("cache span does not match its own hour list")
    for k, v in blob["bm"].items():
        ch, src = k.split("|")
        sink.bm[(ch, src)] = bytearray(base64.b64decode(v))
    per_file = {(r["channel"], r["hour"]): r for r in blob["per_file"]}
    meta = {"scan_seconds": blob.get("scan_seconds"),
            "scan_utc": blob.get("scan_utc")}
    return sink, per_file, meta


# --------------------------------------------------------------------------
# self-test
# --------------------------------------------------------------------------

def _rec_trade(seq, ts_ms, rx_ms):
    return {"type": "trade", "sid": 5, "seq": seq,
            "msg": {"trade_id": "x", "market_ticker": "KXBTC15M-T-0",
                    "yes_price_dollars": "0.5000", "count_fp": "1.00",
                    "taker_side": "yes", "ts": ts_ms // 1000,
                    "ts_ms": ts_ms},
            "_rx_ms": rx_ms}


def _rec_delta(seq, ts_ms, rx_ms):
    return {"type": "orderbook_delta", "sid": 4, "seq": seq,
            "msg": {"market_ticker": "KXBTC15M-T-0", "price_dollars": "0.11",
                    "delta_fp": "-1.00", "side": "yes", "ts_ms": ts_ms},
            "_rx_ms": rx_ms}


def _rec_cfb(seq, ts_ms, rx_ms):
    # the real collector writes msg.data as a JSON STRING with no spaces, so
    # the needle is `\"time\":` with nothing between colon and digit.
    inner = json.dumps({"type": "value", "time": ts_ms, "id": "BRTI",
                        "value": "100.0"}, separators=(",", ":"))
    return {"type": "cfbenchmarks_value", "sid": 2, "seq": seq,
            "msg": {"index_id": "BRTI", "received_at": rx_ms, "data": inner,
                    "avg_60s_data": {"window_start_ts_ms": ts_ms - 60000,
                                     "window_end_ts_exclusive": ts_ms}},
            "_rx_ms": rx_ms}


MAKER = {"trade": _rec_trade, "orderbook_delta": _rec_delta,
         "cfbenchmarks_value": _rec_cfb}


def _dump(recs):
    return "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in recs)


def _write(path, recs):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=1) as f:
        f.write(_dump(recs))


def _write_broken_trailer(path, recs):
    """A collector killed with no trailer, then restarted inside the hour.

    Member one loses its 8-byte CRC/size trailer, exactly as happens when
    `c.w.close()` never runs, and member two is appended behind it. The
    ordinary reader raises on the CRC; no bytes are actually lost.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    h = len(recs) // 2
    b1 = gzip.compress(_dump(recs[:h]).encode("utf-8"), 1)[:-8]
    b2 = gzip.compress(_dump(recs[h:]).encode("utf-8"), 1)
    with open(path, "wb") as f:
        f.write(b1 + b2)


def _write_broken_deflate(path, recs):
    """Member one truncated MID-DEFLATE -- the "invalid block type" case.

    The ordinary reader dies inside member one and never reaches member two.
    Member two must still be recovered, or the census reports the second half
    of the hour as an 1,800-second hole that never happened.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    h = len(recs) // 2
    b1 = gzip.compress(_dump(recs[:h]).encode("utf-8"), 1)
    b2 = gzip.compress(_dump(recs[h:]).encode("utf-8"), 1)
    with open(path, "wb") as f:
        f.write(b1[:int(len(b1) * 0.6)] + b2)


def selftest():
    import shutil
    import tempfile
    print("=" * 78)
    print("SELF-TEST -- plant known holes in one channel and not another")
    print("=" * 78)
    fails = []
    tmp = tempfile.mkdtemp()
    try:
        H0 = hour_epoch("20260101T00")
        H1 = H0 + 3600
        H3 = H0 + 3 * 3600            # 20260101T02 is deliberately ABSENT
        H4 = H0 + 4 * 3600            # trade and book files EXIST but hold
        H5 = H0 + 5 * 3600            # no records; the index keeps ticking

        # ---- the plants, seconds relative to the top of hour 0 ----------
        G1 = (300, 12)      # >= MIN_RUN, < 30 -- reported, not classified
        G2 = (890, 37)      # >= 30, overlaps the 00:15 close window by 10 s;
                            # seq CONTIGUOUS across it -> QUIET
        G3 = (1200, 90)     # >= HOLE_RUN, planted in ALL three channels,
                            # seq JUMPS FORWARD by 500 -> DROPPED
        G4 = (2000, 5)      # under MIN_RUN -- must NOT be reported
        G5 = (1775, 5)      # under MIN_RUN, INSIDE the 00:30 close window
        G6 = (2500, 44)     # >= 30, book and index alive, seq RESETS to 1
                            # -> RECONNECT, which must NOT read as QUIET
        RXG = (2400, 15)    # a receipt-stamp-only hole
        trade_gaps = [G1, G2, G3, G4, G5, G6]
        silent_trade = sum(L for _, L in trade_gaps)

        def gapped(gaps, sec):
            return any(a <= sec < a + L for a, L in gaps)

        # hour 0 -----------------------------------------------------------
        recs, seq = [], 1000
        for s in range(3600):
            if gapped(trade_gaps, s):
                if s == G3[0]:
                    seq += 500              # messages LOST across the hole
                elif s == G6[0]:
                    seq = 0                 # a NEW SUBSCRIPTION: next is 1
                continue
            ts = (H0 + s) * 1000 + 250
            rx = ts + 40
            if RXG[0] <= s < RXG[0] + RXG[1]:
                # the collector buffered 15 s and flushed at once: the
                # exchange clock marches on, ours does not
                rx = (H0 + RXG[0]) * 1000 + 10
            seq += 1
            recs.append(_rec_trade(seq, ts, rx))
        _write(os.path.join(tmp, "trade", "20260101T00.jsonl.gz"), recs)

        for ch in ("orderbook_delta", "cfbenchmarks_value"):
            mk = MAKER[ch]
            rs, q = [], 1
            for s in range(3600):
                if gapped([G3], s):
                    continue
                ts = (H0 + s) * 1000 + 100
                rs.append(mk(q, ts, ts + 20))
                q += 1
            _write(os.path.join(tmp, ch, "20260101T00.jsonl.gz"), rs)

        # hour 1: full on every channel, but trade's file has no trailer
        # (must be fully recovered) and the index channel's is truncated
        # mid-deflate (member two must still be recovered)
        for ch in CHANNELS:
            mk = MAKER[ch]
            rs = [mk(i + 1, (H1 + i) * 1000 + 100, (H1 + i) * 1000 + 120)
                  for i in range(3600)]
            p = os.path.join(tmp, ch, "20260101T01.jsonl.gz")
            if ch == "trade":
                _write_broken_trailer(p, rs)
            elif ch == "cfbenchmarks_value":
                _write_broken_deflate(p, rs)
            else:
                _write(p, rs)

        # hour 3: trade DEGRADED -- 25 runs of 4 s, none of them >= MIN_RUN
        degr = [(100 + 80 * k, 4) for k in range(25)]
        rs, q = [], 1
        for s in range(3600):
            if gapped(degr, s):
                continue
            q += 1
            rs.append(_rec_trade(q, (H3 + s) * 1000 + 100,
                                 (H3 + s) * 1000 + 120))
        _write(os.path.join(tmp, "trade", "20260101T03.jsonl.gz"), rs)
        last3 = rs[-1]["seq"]      # capture BEFORE `rs` is rebound below
        for ch in ("orderbook_delta", "cfbenchmarks_value"):
            mk = MAKER[ch]
            rs = [mk(i + 1, (H3 + i) * 1000 + 100, (H3 + i) * 1000 + 120)
                  for i in range(3600)]
            _write(os.path.join(tmp, ch, "20260101T03.jsonl.gz"), rs)

        # hours 4 and 5: the cross-file `seq` test. Hour 4's trade file
        # EXISTS and holds zero records, so the only evidence of what
        # happened is hour 3's last seq against hour 5's first -- a
        # comparison no single worker can make. 1,000 numbers go missing
        # across it. The book is empty for hour 4 too while the index keeps
        # ticking, which is the BOOK_DOWN_INDEX_UP shape the real tape shows.
        for ch in ("trade", "orderbook_delta"):
            _write(os.path.join(tmp, ch, "20260101T04.jsonl.gz"), [])
        mk = MAKER["cfbenchmarks_value"]
        _write(os.path.join(tmp, "cfbenchmarks_value",
                            "20260101T04.jsonl.gz"),
               [mk(i + 1, (H4 + i) * 1000 + 100, (H4 + i) * 1000 + 120)
                for i in range(3600)])
        for ch in CHANNELS:
            mk = MAKER[ch]
            base_seq = (last3 + 1000) if ch == "trade" else 1
            _write(os.path.join(tmp, ch, "20260101T05.jsonl.gz"),
                   [mk(base_seq + i, (H5 + i) * 1000 + 100,
                       (H5 + i) * 1000 + 120) for i in range(3600)])

        # ---- run the census ----------------------------------------------
        sink, per_file = _collect(tmp, CHANNELS, jobs=1, quiet=True)
        c = Census(sink, per_file)
        hours_all = sorted({h for hs in sink.hours.values() for h in hs})
        brk = seq_breaks(per_file, "trade", c)

        def chk(label, got, want):
            ok = got == want
            print("  %-57s %-15s want %-15s %s" %
                  (label, str(got)[:15], str(want)[:15],
                   "" if ok else "  <-- FAIL"))
            if not ok:
                fails.append("%s: got %r want %r" % (label, got, want))

        print("\n  --- the planted channel (trade, hour 0) ---")
        h0runs = sorted((s - H0, L) for s, L in c.runs[("trade", "ts")]
                        if H0 <= s < H0 + 3600 and L >= MIN_RUN)
        chk("trade runs >= %ds in hour 0" % MIN_RUN, h0runs,
            sorted([G1, G2, G3, G6]))
        chk("longest run in hour 0", max([L for _, L in h0runs] or [0]),
            G3[1])
        chk("seconds with a print, hour 0",
            c.active_in("trade", "ts", H0, 3600), 3600 - silent_trade)
        chk("silent seconds, hour 0",
            c.cover_in("trade", "ts", H0, 3600)
            - c.active_in("trade", "ts", H0, 3600), silent_trade)
        chk("the %ds gaps are NOT reported" % G4[1],
            [a for a, _ in h0runs if a in (G4[0], G5[0])], [])

        print("\n  --- the NEGATIVE control: nothing planted, "
              "nothing found ---")
        for ch in ("orderbook_delta", "cfbenchmarks_value"):
            got = sorted((s - H0, L) for s, L in c.runs[(ch, "ts")]
                         if L >= MIN_RUN and H0 <= s < H0 + 3600)
            chk("%s runs >= %ds in hour 0" % (ch, MIN_RUN), got, [G3])

        print("\n  --- receipt stamp vs message stamp ---")
        rxr = [(s - H0, L) for s, L in c.runs[("trade", "rx")]
               if H0 <= s < H0 + 3600 and L >= MIN_RUN]
        chk("a %ds hole in `_rx_ms` and not `ts_ms`" % (RXG[1] - 1),
            (RXG[0] + 1, RXG[1] - 1) in rxr, True)
        chk("and the message stamp has nothing there",
            any(a == RXG[0] + 1 for a, _ in h0runs), False)

        print("\n  --- the `seq` verdict: quiet / dropped / reconnect ---")
        got = {}
        for s, L in c.runs[("trade", "ts")]:
            if L < 30 or not (H0 <= s < H0 + 3600):
                continue
            d = classify(c, s, L, brk)
            got[(s - H0, L)] = (d["verdict"], d["witness"], d["seq_lost"],
                                d["seq_reset"])
        chk("the 37s run: seq contiguous -> QUIET",
            got.get(G2), ("QUIET", "BOOK_AND_INDEX_UP", 0, False))
        chk("the 90s run: seq jumps 500 -> DROPPED",
            got.get(G3), ("DROPPED", "BOTH_DOWN", 500, False))
        chk("the 44s run: seq resets -> RECONNECT, not QUIET",
            got.get(G6), ("RECONNECT", "BOOK_AND_INDEX_UP", 0, True))
        chk("exactly three runs >= 30 s in hour 0", len(got), 3)

        print("\n  --- where in the 15-minute cycle ---")
        off = sorted(s % CLOSE_MOD for s, L in c.runs[("trade", "ts")]
                     if H0 <= s < H0 + 3600 and L >= MIN_RUN)
        chk("start offsets in the cycle", off,
            sorted(g[0] % CLOSE_MOD for g in (G1, G2, G3, G6)))
        chk("one run starts inside the last %ds before a close" % WINDOW,
            [o for o in off if o >= CLOSE_MOD - WINDOW], [G2[0] % CLOSE_MOD])

        print("\n  --- the close window, and the >= %ds filter ---" % MIN_RUN)
        m10 = c.mask("trade", "ts", MIN_RUN)
        many = c.mask("trade", "ts", 1)
        cmask = c.covmask("trade", "ts")
        nclose = w10 = wany = t10 = ttot = 0
        for close in range(((c.base + CLOSE_MOD - 1) // CLOSE_MOD)
                           * CLOSE_MOD, c.end + 1, CLOSE_MOD):
            a, b = close - WINDOW, close
            if a < c.base or b > c.end:
                continue
            i, j = a - c.base, b - c.base
            if cmask[i:j].count(1) != WINDOW:
                continue
            nclose += 1
            w10 += m10[i:j].count(1)
            wany += many[i:j].count(1)
            ttot += WINDOW - TAU_MIN + 1
            t10 += m10[i:j - TAU_MIN + 1].count(1)
        chk("close windows fully taped (5 hours x 4)", nclose, 20)
        chk("window seconds inside a run >= %ds" % MIN_RUN, w10,
            10 + 4 * WINDOW)
        chk("window seconds silent at ANY run length", wany,
            19 + 4 * WINDOW)
        chk("the band is %d s per close" % (WINDOW - TAU_MIN + 1),
            ttot // max(nclose, 1), WINDOW - TAU_MIN + 1)
        chk("tau in [%d,%d] drops the last %d s of each window"
            % (TAU_MIN, WINDOW, TAU_MIN - 1), t10,
            8 + 4 * (WINDOW - TAU_MIN + 1))

        print("\n  --- a `seq` break ACROSS hour files ---")
        e4 = per_file[("trade", "20260101T04")]
        chk("hour 4's trade file exists and holds no records",
            (e4["records"], e4["seq_first"]), (0, None))
        r4 = [(s2, L2) for s2, L2 in c.runs[("trade", "ts")]
              if s2 == H4]
        chk("that empty hour is one 3,600 s silent run", r4, [(H4, 3600)])
        d4 = classify(c, H4, 3600, brk)
        chk("and it is DROPPED, not QUIET -- the stitch found the jump",
            (d4["verdict"], d4["seq_lost"]), ("DROPPED", 999))
        chk("its witness is BOOK_DOWN_INDEX_UP", d4["witness"],
            "BOOK_DOWN_INDEX_UP")
        chk("no break is invented across the MISSING hour 2",
            [t for t in brk if H3 <= t < H3 + 60], [])

        print("\n  --- clean-file loss vs damaged-gzip loss ---")
        for ch in CHANNELS:
            b = seq_breaks(per_file, ch, c)
            allf = [(p2, n2) for v in b.values() for p2, n2, k, _d in v
                    if k == "forward"]
            cl = [(p2, n2) for v in b.values() for p2, n2, k, d in v
                  if k == "forward" and not d]
            dm = [(p2, n2) for v in b.values() for p2, n2, k, d in v
                  if k == "forward" and d]
            chk("%s: clean + damaged == every forward jump" % ch,
                len(cl) + len(dm), len(allf))
        chk("the hour-4 jump is in CLEAN files (3 and 5 both read fine)",
            classify(c, H4, 3600, brk)["seq_from_damaged_file"], False)
        chk("the index channel has a jump beside its damaged hour 1",
            any(d for v in seq_breaks(per_file, "cfbenchmarks_value",
                                      c).values()
                for _, _, k, d in v if k in ("forward", "reset")), True)

        print("\n  --- broken gzip must not FABRICATE a hole ---")
        tr1 = per_file[("trade", "20260101T01")]
        chk("trade hour 1 raised on the ordinary reader",
            bool(tr1["read_error"]), True)
        chk("trade hour 1 was salvaged", tr1["salvaged"], True)
        chk("trade hour 1 recovered every second",
            c.active_in("trade", "ts", H1, 3600), 3600)
        chk("trade hour 1 has no run >= %ds" % MIN_RUN,
            [(s, L) for s, L in c.runs[("trade", "ts")]
             if H1 <= s < H1 + 3600 and L >= MIN_RUN], [])
        cf1 = per_file[("cfbenchmarks_value", "20260101T01")]
        chk("index hour 1 (mid-deflate) raised", bool(cf1["read_error"]),
            True)
        chk("index hour 1 recovered the SECOND member",
            c.active_in("cfbenchmarks_value", "ts", H1 + 1800, 1800), 1800)
        chk("... and it beat the ordinary reader",
            cf1["records"] > cf1["fast_records"], True)

        print("\n  --- a MISSING hour is not a silent hour ---")
        chk("hour 2 has no file on any channel",
            [h for h in hours_all if h == H0 + 2 * 3600], [])
        chk("no run crosses the missing hour",
            max(L for s2, L in c.runs[("trade", "ts")] if s2 < H3 + 3600),
            G3[1])
        chk("covered seconds on trade = 5 hours", c.covered("trade", "ts"),
            5 * 3600)

        print("\n  --- the health flag ---")
        rep, health, allruns, daily = build_report(c, hours_all, 0.0, tmp)
        chk("hour 0 (90s run) -> HOLE", health[("trade", H0)]["flag"], "HOLE")
        chk("hour 1 (salvaged, full) -> OK", health[("trade", H1)]["flag"],
            "OK")
        chk("hour 3 (100 silent s, no long run) -> DEGRADED",
            health[("trade", H3)]["flag"], "DEGRADED")
        chk("hour 3 silent seconds", health[("trade", H3)]["silent"], 100)
        chk("book hour 3 -> OK", health[("orderbook_delta", H3)]["flag"],
            "OK")
        chk("hour 4 (empty file) -> HOLE", health[("trade", H4)]["flag"],
            "HOLE")
        chk("hour 5 (full) -> OK", health[("trade", H5)]["flag"], "OK")
        chk("the report dates the planted 90s hole", iso(H0 + G3[0]) in rep,
            True)
        chk("the report names RECONNECT", "RECONNECT" in rep, True)

        print("\n  --- the reader's own invariants ---")
        chk("no channel-hour had a needle/newline mismatch",
            sum(r["align_fail"] for r in per_file.values()), 0)
        chk("no channel-hour had an out-of-range timestamp",
            sum(r["odd_ts"] + r["odd_rx"] for r in per_file.values()), 0)
        chk("records == seq needles on every file",
            all(r["records"] == r["seq_n"] for r in per_file.values()), True)
        chk("the parent kept no second lists",
            any("ts_secs" in r for r in per_file.values()), False)

        print("\n  --- the cache reproduces the report exactly ---")
        cp = os.path.join(tmp, "cache.json.gz")
        save_cache(cp, sink, per_file)
        sink2, pf2, _ = load_cache(cp)
        c2 = Census(sink2, pf2)
        rep2, _, runs2, _ = build_report(c2, hours_all, 0.0, tmp)
        chk("runs identical", runs2 == allruns, True)
        chk("report identical apart from its timestamp line",
            rep2.split("\n")[3:] == rep.split("\n")[3:], True)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- finds exactly the four planted runs and no")
    print("others, keeps the 5 s gaps out of the >= 10 s count, separates a")
    print("receipt-stamp hole from an exchange-clock one, tells QUIET from")
    print("DROPPED from RECONNECT on `seq` and from the book/index")
    print("witnesses, places each run in the 15-minute cycle, recovers both")
    print("halves of two differently-broken gzips rather than reporting them")
    print("as holes, refuses to turn a missing hour into a silent one, keeps")
    print("no per-second state in the parent, and round-trips its cache.")
    return True


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def _collect(data, channels, jobs, quiet=False):
    joblist, hours = [], {}
    for ch in channels:
        paths = sorted(glob.glob(os.path.join(data, ch, "*.jsonl.gz")))
        if not paths:
            continue
        hours[ch] = sorted(hour_epoch(os.path.basename(p)[:11])
                           for p in paths)
        joblist += [(ch, p) for p in paths]
    if not joblist:
        print("tapegaps: found zero channel-hours under %s -- stopping."
              % data)
        raise SystemExit(1)
    # Biggest first: an orderbook_delta hour is ~30x a trade hour, so a
    # largest-first schedule keeps every worker busy to the end.
    joblist.sort(key=lambda j: -os.path.getsize(j[1]))
    sink = Sink(hours)
    per_file = {}
    t0 = time.time()
    if jobs <= 1:
        it = map(scan_file, joblist)
        pool = None
    else:
        import multiprocessing
        pool = multiprocessing.Pool(jobs)
        it = pool.imap_unordered(scan_file, joblist, chunksize=1)
    done = 0
    for r in it:
        per_file[(r["channel"], r["hour"])] = sink.add(r)
        done += 1
        if not quiet and (done % 25 == 0 or done == len(joblist)):
            print("  scanned %4d/%d  %6.1f s" %
                  (done, len(joblist), time.time() - t0), flush=True)
    if pool is not None:
        pool.close()
        pool.join()
    return sink, per_file


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default=None,
                    help="ignored; accepted so go.py can pass it")
    ap.add_argument("--report", default=None)
    ap.add_argument("--cache", default=None,
                    help="read the census from here if it exists, else "
                         "write it after scanning")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--channels", default=",".join(CHANNELS))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return 0 if selftest() else 1
    if os.environ.get("KALS_SELFTESTED") != "1":
        if not selftest():
            print("\nREFUSING TO TOUCH REAL DATA -- self-test failed.")
            return 1
        print()

    chans = [x for x in a.channels.split(",") if x.strip()]
    t0 = time.time()
    if a.cache and os.path.exists(a.cache):
        print("tapegaps: reading the census from %s" % a.cache)
        sink, per_file, meta = load_cache(a.cache)
        prov = (" Census scanned in %s s on %s and read back from a cache "
                "here -- the reading code is untouched by the report, so "
                "this is the same census." %
                (("%.0f" % meta["scan_seconds"]) if meta["scan_seconds"]
                 else "an unrecorded number of", meta["scan_utc"]))
    else:
        print("tapegaps: scanning %s, channels %s, jobs %d" %
              (a.data, ",".join(chans), a.jobs))
        sink, per_file = _collect(a.data, chans, a.jobs)
        prov = ""
        if a.cache:
            save_cache(a.cache, sink, per_file, time.time() - t0)
            print("  cached to %s (%.1f MB)" %
                  (a.cache, os.path.getsize(a.cache) / 1e6), flush=True)
    c = Census(sink, per_file)
    hours_all = sorted({h for hs in sink.hours.values() for h in hs})
    rep, health, allruns, daily = build_report(
        c, hours_all, time.time() - t0, a.data, prov)

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(here, "results")
    os.makedirs(outdir, exist_ok=True)
    rp = a.report or os.path.join(outdir, "RESULTS_tapegaps.md")
    with open(rp, "w", encoding="utf-8") as f:
        f.write(rep + "\n")
    hj = {}
    for (ch, h), v in health.items():
        hj.setdefault(ch, {})[time.strftime("%Y%m%dT%H", time.gmtime(h))] = {
            "flag": v["flag"], "covered_s": v["cov"], "silent_s": v["silent"],
            "longest_run_s": v["longest"], "records": v.get("records", 0)}
    hp = os.path.join(outdir, "tapegaps_hours.json")
    with open(hp, "w", encoding="utf-8") as f:
        json.dump({"min_run_s": MIN_RUN, "hole_run_s": HOLE_RUN,
                   "degraded_frac": DEGRADED_FRAC, "channels": hj}, f,
                  indent=1, sort_keys=True)
    qp = os.path.join(outdir, "tapegaps_runs.json")
    with open(qp, "w", encoding="utf-8") as f:
        json.dump({"min_run_s": MIN_RUN, "window_s": WINDOW,
                   "tau_min_s": TAU_MIN, "runs": allruns}, f, indent=1)

    print(rep)
    print("\nwrote %s" % rp)
    print("wrote %s" % hp)
    print("wrote %s (%d runs >= %d s)" % (qp, len(allruns), MIN_RUN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
