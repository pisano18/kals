"""logs.py -- the bots' own logs, read backwards from the end (what a bot DID; never money): read_since (records
from a moment on), last_record (the newest record of some kinds, memoised on the log's size in _BACK), pin_logs.

v-tg-rebuild step 7 (2026-10-30): split out of botstats.py verbatim (botstats.py is now a facade over botdata).
"""
import glob
import json
import os

from botdata import paths as _paths
from botdata import tables as _tables
from botdata.clock import utc_epoch as _epoch


# ---- the bots' own logs (what they DID; never money) -------------------------
_BACK = {}


def _t_of(r):
    return _epoch(r.get("t"))


def read_since(path, since, chunk=1 << 20):
    """Records with t >= since, reading backwards from the end so a 10 MB log costs only today's
    part. None when the file is missing."""
    try:
        size = os.path.getsize(path)
        fh = open(path, "rb")
    except OSError:
        return None
    with fh:
        pos, buf = size, b""
        while True:
            step = min(chunk, pos)
            pos -= step
            fh.seek(pos)
            buf = fh.read(step) + buf
            lines = buf.split(b"\n")
            body = lines if pos == 0 else lines[1:]
            first_t = None
            for ln in body:
                try:
                    first_t = _t_of(json.loads(ln))
                except ValueError:
                    continue
                if first_t is not None:
                    break
            if pos == 0 or (first_t is not None and first_t < since):
                break
    out = []
    for ln in body:
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        t = _t_of(r)
        if isinstance(r, dict) and t is not None and t >= since:
            out.append(r)
    return out


def last_record(path, kinds, pred=None, max_bytes=64 << 20, chunk=1 << 20):
    """The newest record whose kind/ev is in `kinds` (and passes `pred`), reading backwards.
    Memoised on (path, size, kinds) for the long-running phone process."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    key = (path, size, tuple(kinds), pred is None)
    if pred is None and key in _BACK:
        return _BACK[key]
    needles = [('"%s"' % k).encode() for k in kinds]
    found = None
    with open(path, "rb") as fh:
        pos, tail = size, b""
        while pos > 0 and size - pos < max_bytes and found is None:
            step = min(chunk, pos)
            pos -= step
            fh.seek(pos)
            buf = fh.read(step) + tail
            lines = buf.split(b"\n")
            tail = lines[0] if pos > 0 else b""
            body = lines[1:] if pos > 0 else lines
            if not any(n in buf for n in needles):
                continue
            for ln in reversed(body):
                if not any(n in ln for n in needles):
                    continue
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict) and (r.get("kind") or r.get("ev")) in kinds and (pred is None or pred(r)):
                    found = r
                    break
    if pred is None:
        if len(_BACK) > 64:
            _BACK.clear()
        _BACK[key] = found
    return found


# ---- a running bot's settings NOW (v-tg-settings-now, 2026-10-31) ------------------------------------------------
# The operator, after a $1,000 deposit resized the pin bot by itself (162 -> 279 contracts, loss abort -$268 -> -$459):
# "Why aren't some charts showing the updated pricing on pin ... Shouldn't it happen automatically?" /pin still said
# 'hourly KXBTCD: 1 contract a market' and every page read the bot's START record. THE RULE: a setting a running bot
# changes by itself (its Records.resize kinds: pin autosize / loss_cap, ladder and forecaster rescale, FX resize) is
# read from its newest such record after the start, never from the start record or the launch args alone. Every
# reader goes through settings_now (botdata/tests/test_settings_now.py enforces it).
_META = ("t", "kind", "ev", "pid", "argv")


def settings_now(path, start, kinds, as_start=None):
    """`start` (a start record) with every later self-change record of `kinds` laid over it, oldest first, so the
    newest wins. `as_start(r)` turns one change record into the start record's field names (None = its own fields
    minus t/kind/ev/pid/argv). Adds 'changed_t' / 'changed_kind' (the newest change) when any applied. `start` back
    unchanged when there is no log, no start time, or no kinds."""
    if not start or not kinds or not path:
        return start
    t0 = _t_of(start)
    if t0 is None:
        return start
    got = []
    for k in kinds:
        r = last_record(path, (k,), lambda x, _t0=t0: (_t_of(x) or 0.0) >= _t0)
        if r is not None:
            got.append(r)
    if not got:
        return start
    out = dict(start)
    for r in sorted(got, key=lambda x: _t_of(x) or 0.0):
        fields = as_start(r) if as_start is not None else {k: v for k, v in r.items() if k not in _META}
        out.update({k: v for k, v in (fields or {}).items() if v is not None})
        out["changed_t"], out["changed_kind"] = r.get("t"), r.get("kind") or r.get("ev")
    return out


def pin_logs():
    return sorted(glob.glob(os.path.join(_paths.RESULTS, _tables.SPEC["pin"]["log_glob"])))
