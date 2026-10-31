"""test_fast.py -- v-tg-fast (2026-10-31): the phone's two hot readers made cheap without changing one answer.

The operator: "I do do a lot of /today and /bots each day." One /today or /bots cost ~2-4 s of CPU, mostly two readers:
time.strptime in botdata.clock.utc_epoch (30-40k timestamps a command) and botdata.logs.read_since re-reading the
bots' logs from midnight on every call. The rules this file enforces:

  1. utc_epoch gives exactly the old strptime answer for every input (its fast path takes only canonical, ordinary
     timestamps; everything else falls back to the old code);
  2. read_since remembers what it read per (path, since) and gives exactly what a fresh backward read of the file gives
     -- unchanged, appended (whole lines, a half-written last line, many small steps), shrunk, rewritten -- and its
     memory is bounded;
  3. last_record's memo for settings_now (memo=) gives the same newest record as an unmemoised read, and follows growth.

Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_fast.py      (or all of them: research\\botstats.py --selftest)
"""
import calendar
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import ck, run, sandbox                                   # noqa: E402

from botdata import clock, logs                                      # noqa: E402


# ---- 1. utc_epoch ----------------------------------------------------------------------------------------------------
def test_utc_epoch_matches_strptime():
    rnd = random.Random(31)
    cases = [None, 0, 12.5, b"2026-10-31T04:15:06Z", "", "2026", "2026-10-31", "2026-10-31T04:15", "garbage",
             "2026-10-31 04:15:06", "2026-10-31T04:15:06", "2026-10-31T04:15:06Z", "2026-10-31T04:15:06.437143Z",
             "2026-10-31T04:15:06+00:00", " 2026-10-31T04:15:06Z", "2026-1-31T04:15:06Z", "2026-10-31T4:15:06Z",
             "0000-01-01T00:00:00Z", "0001-01-01T00:00:00Z", "9999-12-31T23:59:59Z", "2026-00-10T00:00:00Z",
             "2026-13-10T00:00:00Z", "2026-02-29T00:00:00Z", "2024-02-29T00:00:00Z", "2100-02-29T00:00:00Z",
             "2000-02-29T00:00:00Z", "2026-04-31T00:00:00Z", "2026-04-30T23:59:59Z", "2026-10-32T00:00:00Z",
             "2026-10-00T00:00:00Z", "2026-10-31T24:00:00Z", "2026-10-31T23:60:00Z", "2026-10-31T23:59:60Z",
             "2026-10-31T23:59:61Z", "2026-10-31T23:59:62Z", "\u0662\u0660\u0662\u0666-10-31T04:15:06Z",
             "2026-10-31T04:15:\u0660\u0666Z", "2026-11-01T06:00:00Z", "1970-01-01T00:00:00Z", "1969-12-31T23:59:59Z"]
    for _ in range(20000):
        y = rnd.choice([1970, 1999, 2000, 2024, 2025, 2026, 2027, 2038, 2100, rnd.randint(1, 9999)])
        cases.append("%04d-%02d-%02dT%02d:%02d:%02d%s" % (
            y, rnd.randint(0, 13), rnd.randint(0, 32), rnd.randint(0, 24), rnd.randint(0, 60), rnd.randint(0, 62),
            rnd.choice(["Z", ".123456Z", "", "+00:00"])))
    bad = [c for c in cases if clock.utc_epoch(c) != clock._utc_epoch_strptime(c)]
    ck(not bad, "utc_epoch == the old strptime reader on %d inputs (edge dates, 60/61 s, other digits, junk)%s"
       % (len(cases), "" if not bad else ": %r" % bad[:5]))
    ck(clock.utc_epoch("2026-10-31T04:15:06.437143Z") == float(calendar.timegm((2026, 10, 31, 4, 15, 6))),
       "utc_epoch reads the bots' own timestamp shape")


def test_et_day_and_offset_per_hour():
    import time as _t
    from downtime import et_offset
    old_day = lambda e: _t.strftime("%Y-%m-%d", _t.gmtime(float(e) + et_offset(float(e))))           # noqa: E731
    rnd = random.Random(5)
    es = []
    for y in (2025, 2026, 2027):                         # every clock change and ET midnight +- a few seconds
        for edge in [calendar.timegm((y, 3, d, 7, 0, 0)) for d in range(8, 15)] + \
                    [calendar.timegm((y, 11, d, 6, 0, 0)) for d in range(1, 8)] + \
                    [calendar.timegm((y, m, 1, h, 0, 0)) for m in range(1, 13) for h in (4, 5)]:
            es += [edge + k for k in (-3601, -3599.5, -2, -1.0000001, -1, -0.5, -1e-7, 0, 1e-7, 0.5, 1, 1.0000001, 2,
                                      3599, 3600)]
    es += [rnd.uniform(1.7e9, 1.9e9) for _ in range(30000)] + [rnd.randint(1700000000, 1900000000) for _ in range(30000)]
    for _pass in (1, 2):                                 # cold, then from the per-hour memo
        bad = [e for e in es if clock.et_day(e) != old_day(e) or clock._et_off(e) != et_offset(e)]
        ck(not bad, "et_day / the ET offset == downtime.et_offset's, pass %d, %d moments incl. every clock change%s"
           % (_pass, len(es), "" if not bad else ": %r" % bad[:5]))
    ck(clock.et_clock(calendar.timegm((2026, 11, 1, 5, 59, 59))) == "Nov 1 1:59 AM ET"
       and clock.et_clock(calendar.timegm((2026, 11, 1, 6, 0, 0))) == "Nov 1 1:00 AM ET",
       "et_clock across the November clock change")


# ---- 2. read_since ---------------------------------------------------------------------------------------------------
def _reference(path, since, chunk):
    """The ORIGINAL read_since (before v-tg-fast), verbatim: the answer the remembered one must give."""
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
                    first_t = logs._t_of(json.loads(ln))
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
        t = logs._t_of(r)
        if isinstance(r, dict) and t is not None and t >= since:
            out.append(r)
    return out


T0 = 1793419200.0                      # 2026-10-31 04:00Z = midnight ET


def _line(i, t):
    return json.dumps({"t": "%sZ" % __import__("time").strftime("%Y-%m-%dT%H:%M:%S", __import__("time").gmtime(t)),
                       "kind": "order" if i % 3 else "settled", "i": i, "pad": "x" * (i % 37)}) + "\n"


def _same(path, since, chunk, what):
    got, want = logs.read_since(path, since, chunk), _reference(path, since, chunk)
    ck(got == want, "%s: %s records, the same as a fresh read" % (what, "none" if want is None else len(want)))
    return got


def test_read_since_matches_a_fresh_read():
    with sandbox() as td:
        p = os.path.join(td, "bot.jsonl")
        since = T0
        ck(logs.read_since(p, since) is None and _reference(p, since, 1 << 20) is None, "missing file -> None")
        with open(p, "w", encoding="utf-8", newline="") as fh:
            for i in range(400):
                fh.write(_line(i, T0 - 7200 + 30 * i))      # 2 h before midnight to ~1.3 h after
        for chunk in (64, 1000, 1 << 20):
            _same(p, since, chunk, "first read (chunk %d)" % chunk)
            _same(p, since, chunk, "the same file again (chunk %d)" % chunk)
        rnd = random.Random(7)
        i = 400
        for step in range(60):                             # many appends: whole lines, then a half line, then its end
            with open(p, "a", encoding="utf-8", newline="") as fh:
                for _ in range(rnd.randint(0, 5)):
                    fh.write(_line(i, T0 - 7200 + 30 * i))
                    i += 1
                if step % 4 == 1:
                    half = _line(i, T0 - 7200 + 30 * i)
                    fh.write(half[:len(half) // 2])
            for chunk in (64, 1 << 20):
                _same(p, since, chunk, "after append %d (chunk %d)" % (step, chunk))
            if step % 4 == 1:
                with open(p, "a", encoding="utf-8", newline="") as fh:
                    fh.write(half[len(half) // 2:])
                i += 1
        e = logs._SINCE[(p, float(since), 1 << 20)]
        ck(e["end"] == os.path.getsize(p) and not e["tail"], "the kept offset is the end of the last complete line")
        # an append that grows the file reads only the new bytes (the entry is extended, not rebuilt)
        before = len(e["recs"])
        with open(p, "a", encoding="utf-8", newline="") as fh:
            fh.write(_line(i, T0 + 99999))
        got = _same(p, since, 1 << 20, "one more line")
        ck(len(logs._SINCE[(p, float(since), 1 << 20)]["recs"]) == before + 1 and got[-1]["i"] == i,
           "the new line was added to the kept records")
        # shrunk and rewritten files are read afresh
        with open(p, "r", encoding="utf-8") as fh:
            keep = fh.readlines()
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.writelines(keep[:300])
        _same(p, since, 1 << 20, "shrunk")
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.writelines([_line(j, T0 + 60 * j) for j in range(500)])
        _same(p, since, 1 << 20, "rewritten longer (other bytes before the kept offset)")
        lines = [_line(j, T0 + 60 * j) for j in range(500)]
        lines[10] = lines[10].replace('"order"', '"ORDER"')
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.writelines(lines)
        _same(p, since, 1 << 20, "rewritten the same length")
        _same(p, since - 1e9, 1 << 20, "a different `since` is its own entry")
        out = logs.read_since(p, since)
        out.append("x")
        ck(logs.read_since(p, since) == _reference(p, since, 1 << 20), "a caller's list is its own (changing it changes no entry)")
        os.remove(p)
        ck(logs.read_since(p, since) is None, "a removed file -> None again")


def test_read_since_memory_is_bounded():
    with sandbox() as td:
        old = (logs.SINCE_KEYS, logs.SINCE_RECORDS)
        try:
            logs.SINCE_KEYS, logs.SINCE_RECORDS = 4, 250
            ps = []
            for k in range(6):
                p = os.path.join(td, "b%d.jsonl" % k)
                with open(p, "w", encoding="utf-8", newline="") as fh:
                    fh.writelines([_line(i, T0 + i) for i in range(100)])
                ps.append(p)
                logs.read_since(p, T0)
            n = sum(len(e["recs"]) for e in logs._SINCE.values())
            ck(len(logs._SINCE) <= 4 and n <= 250, "at most SINCE_KEYS entries and SINCE_RECORDS records (%d, %d)"
               % (len(logs._SINCE), n))
            ck((ps[-1], float(T0), 1 << 20) in logs._SINCE and (ps[0], float(T0), 1 << 20) not in logs._SINCE,
               "the least recently used entry goes first")
            ck(all(logs.read_since(p, T0) == _reference(p, T0, 1 << 20) for p in ps), "a dropped entry reads afresh")
        finally:
            logs.SINCE_KEYS, logs.SINCE_RECORDS = old


# ---- 4. money.market's memo -----------------------------------------------------------------------------------------
def test_market_memo():
    from botdata import money
    rnd = random.Random(3)
    tks = ["KXBTC15M-26OCT310430-30", "KXCRYPTOLEAD15M-26OCT310415", "KXBTCD-26OCT3023-T77299.99", "KXHIGHNY-26OCT31-B72.5",
           "KXHYPE15M-26OCT302300-00", "", None, "weird"]
    rows = []
    for i in range(3000):
        r = {"ticker": rnd.choice(tks), "settled_time": rnd.choice(["2026-10-31T04:30:13.572Z", "2026-10-31T09:00:00Z",
                                                                  None, "bad"]),
             "market_result": rnd.choice(["yes", "no", "scalar", "", None]),
             "yes_count_fp": rnd.choice(["0", "10", "92.91", None, 5]), "no_count_fp": rnd.choice(["0", "280.00", "3"]),
             "yes_total_cost_dollars": rnd.choice(["0", "9.80", "271.88"]), "no_total_cost_dollars": rnd.choice(["0", "1.5"]),
             "fee_cost": rnd.choice(["0", "0.19", "x"]), "value": rnd.choice([None, 100, 0, 50, "50", 7.5])}
        for k in list(r):
            if rnd.random() < 0.08:
                del r[k]
        rows.append(r)
    rows.append({"ticker": "T", "value": [1]})                     # an unhashable value: worked out, not remembered
    for _pass in (1, 2):
        bad = [r for r in rows if money.market(r) != money._market(r)]
        ck(not bad, "market() == the old function on %d rows, pass %d%s" % (len(rows), _pass, "" if not bad else
                                                                           ": %r" % bad[:2]))
    a = money.market(rows[0])
    a["money"] = 1e9
    ck(money.market(rows[0]) == money._market(rows[0]), "each call gets its own dict (a caller's change sticks to it)")


# ---- 3. last_record's memo for settings_now --------------------------------------------------------------------------
def test_last_record_memo():
    with sandbox() as td:
        p = os.path.join(td, "pin.jsonl")
        recs = [{"t": "2026-10-31T0%d:00:00Z" % h, "kind": k, "size": h} for h, k in
                ((1, "start"), (2, "autosize"), (3, "loss_cap"), (4, "autosize"))]
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.writelines(json.dumps(r) + "\n" for r in recs)
        t0 = calendar.timegm((2026, 10, 31, 1, 0, 0))
        pred = lambda x: (logs._t_of(x) or 0.0) >= t0                       # noqa: E731
        a = logs.last_record(p, ("autosize",), pred, memo=("since", t0))
        ck(a == logs.last_record(p, ("autosize",), pred) and a["size"] == 4, "memoised == unmemoised (newest autosize)")
        with open(p, "a", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps({"t": "2026-10-31T05:00:00Z", "kind": "autosize", "size": 5}) + "\n")
        ck(logs.last_record(p, ("autosize",), pred, memo=("since", t0))["size"] == 5, "a grown log is read again")
        st = logs.settings_now(p, recs[0], ("autosize", "loss_cap"))
        ck(st["size"] == 5 and st["changed_kind"] == "autosize", "settings_now still lays the newest change over the start")


if __name__ == "__main__":
    raise SystemExit(run(globals(), "test_fast"))
