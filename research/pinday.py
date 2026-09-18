"""pinday.py -- what we made, by EASTERN day. The one place that answers it.

WHY THIS FILE EXISTS. On 2026-09-17 the operator was told the day was "+$47".
It was **+$23**. The query behind the $47 filtered the live log on
`t.startswith("2026-09-17")`, and `t` is UTC, so it swept in every settlement
from 20:00-23:59 ET the PREVIOUS evening. That is the same ticker-clock trap
that was found and fixed inside `pinflat` a day earlier, repeated in a
throwaway one-liner because there was nothing to call.

So: **no session writes another ad-hoc day total.** Call `by_et_day()` or run
this file. It uses `downtime.et_offset`, the same source the desktop app uses,
so the CLI, the app and the phone bot cannot disagree.

A settlement belongs to the ET day of its CLOSE, taken from the ticker
(`KXBTC15M-26SEP170000-00` closes at midnight ET), falling back to the log's
`t` converted to ET when a ticker cannot be parsed. Those two agree on every
record in the live logs today; the ticker is preferred because it is the
exchange's own clock and survives a log being written late.
"""
import argparse
import calendar
import collections
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from downtime import et_offset                                   # noqa: E402

RESULTS = os.path.join(os.path.dirname(HERE), "results")
LIVE_GLOB = os.path.join(RESULTS, "pinrun-live-*.jsonl")
# The COMMODITY bot writes here and nothing used to read it, so every "today"
# figure was crypto-only. On 2026-09-17 that reported +$88 on a day that was
# +$88 crypto and -$58 commodity, and the operator caught the gap himself.
CMD_GLOB = os.path.join(RESULTS, "cmdlive-*.jsonl")

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def et_day_of_epoch(epoch):
    """'YYYY-MM-DD' in Eastern, from a UTC epoch."""
    e = float(epoch) + et_offset(float(epoch))
    return time.strftime("%Y-%m-%d", time.gmtime(e))


def et_day_of_ticker(ticker):
    """'YYYY-MM-DD' from the ET clock encoded in a ticker, or None.

    `KXBTC15M-26SEP170000-00` -> 2026-09-17. No timezone arithmetic: the
    ticker is already Eastern, which is exactly why reading it as UTC moved
    four hours of settlements into the wrong day.
    """
    try:
        stamp = str(ticker).split("-")[1]
        yy, mon, dd = int(stamp[0:2]), _MONTHS[stamp[2:5].upper()], int(stamp[5:7])
    except (AttributeError, IndexError, KeyError, ValueError):
        return None
    return "%04d-%02d-%02d" % (2000 + yy, mon, dd)


def et_day_of_record(r):
    """The ET day a record belongs to: its ticker's, else its timestamp's."""
    d = et_day_of_ticker(r.get("ticker", ""))
    if d:
        return d
    t = r.get("t")
    if not t:
        return None
    try:
        return et_day_of_epoch(calendar.timegm(time.strptime(t, "%Y-%m-%dT%H:%M:%SZ")))
    except (TypeError, ValueError):
        return None


def load(paths):
    """Settled records from the live logs, de-duplicated on (ticker, t) --
    the logs overlap whenever the bot restarts mid-day, and a restart is the
    normal case now that it heals itself."""
    seen, out = set(), []
    for p in paths:
        try:
            fh = open(p, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"settled"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("kind") != "settled":
                    continue
                # DE-DUPLICATE ON THE WHOLE LINE, NOT ON (ticker, t).
                # Two legs of the SAME market settle in the same second with
                # the same ticker, and keying on (ticker, t) silently threw the
                # second one away -- it reported the commodity day as -$23.14
                # when the records summed to -$51.94, because most losing
                # markets carried two legs. The thing we actually need to guard
                # against is a whole line repeated when logs overlap after a
                # restart, and the full line catches exactly that and nothing
                # else.
                k = line.strip()
                if k in seen:
                    continue
                seen.add(k)
                out.append(r)
    return out


def by_et_day(records):
    """{'YYYY-MM-DD': {'n', 'dollars', 'losses', 'lost_dollars'}}"""
    out = collections.defaultdict(
        lambda: {"n": 0, "dollars": 0.0, "losses": 0, "lost_dollars": 0.0})
    for r in records:
        d = et_day_of_record(r)
        if d is None:
            continue
        c = float(r.get("pnl_c") or 0.0) / 100.0
        out[d]["n"] += 1
        out[d]["dollars"] += c
        if c < 0:
            out[d]["losses"] += 1
            out[d]["lost_dollars"] += c
    return dict(out)


def selftest():
    def ck(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            raise SystemExit("pinday selftest: FAILED -- " + msg)

    ck(et_day_of_ticker("KXBTC15M-26SEP170000-00") == "2026-09-17",
       "a ticker closing at midnight ET belongs to that ET day, not the UTC one")
    ck(et_day_of_ticker("KXGOLD15M-26SEP172345-15") == "2026-09-17",
       "and so does one closing at 23:45 ET -- which is 03:45Z the NEXT day")
    ck(et_day_of_ticker("KXBTC15M-26JAN012215-00") == "2026-01-01"
       and et_day_of_ticker("KXBTC15M-26DEC312215-00") == "2026-12-31",
       "January and December parse; the month is read from its name, not a number")
    ck(et_day_of_ticker("junk") is None and et_day_of_ticker(None) is None
       and et_day_of_ticker("KXBTC15M-26XXX170000-00") is None,
       "NULL: an unparseable ticker returns None rather than a wrong day")

    # THE BUG THIS FILE EXISTS FOR: 01:30Z on the 17th is 21:30 ET on the 16th.
    e = calendar.timegm((2026, 9, 17, 1, 30, 0))
    ck(et_day_of_epoch(e) == "2026-09-16",
       "01:30Z on the 17th is 21:30 ET on the 16TH -- the four hours that "
       "turned $23 into $47")
    ck(et_day_of_epoch(calendar.timegm((2026, 9, 17, 4, 0, 0))) == "2026-09-17",
       "04:00Z IS midnight ET, the first moment of the new ET day (EDT)")
    ck(et_day_of_epoch(calendar.timegm((2026, 9, 17, 3, 59, 59))) == "2026-09-16",
       "...and one second earlier is still the old one")
    ck(et_day_of_epoch(calendar.timegm((2026, 1, 15, 4, 30, 0))) == "2026-01-14",
       "in JANUARY the offset is five hours, so 04:30Z is still the 14th -- a "
       "hard-coded -4 would be wrong for half the year")

    rs = [{"kind": "settled", "ticker": "KXBTC15M-26SEP170000-00", "pnl_c": 150.0,
           "t": "2026-09-17T04:00:20Z"},
          {"kind": "settled", "ticker": "KXETH15M-26SEP162300-00", "pnl_c": -80.0,
           "t": "2026-09-17T03:00:20Z"},
          {"kind": "settled", "ticker": "KXSOL15M-26SEP171100-00", "pnl_c": 50.0,
           "t": "2026-09-17T15:00:20Z"}]
    d = by_et_day(rs)
    ck(abs(d["2026-09-17"]["dollars"] - 2.00) < 1e-9 and d["2026-09-17"]["n"] == 2,
       "two of the three land on the 17th and pay $2.00")
    ck(d["2026-09-16"]["n"] == 1 and d["2026-09-16"]["losses"] == 1
       and abs(d["2026-09-16"]["lost_dollars"] + 0.80) < 1e-9,
       "the 23:00 ET market is the 16th's loss, though its log line says 17th")
    ck(len(load([])) == 0 and by_et_day([]) == {},
       "NULL: no files, no records, no invented days")
    # TWO LEGS OF ONE MARKET ARE TWO SETTLEMENTS, NOT A DUPLICATE.
    import tempfile as _tf
    _d = _tf.mkdtemp()
    _f = os.path.join(_d, "cmdlive-x.jsonl")
    _same = {"kind": "settled", "ticker": "KXWTI15M-26SEP171615-15",
             "t": "2026-09-17T20:30:20Z"}
    with open(_f, "w", encoding="utf-8") as _fh:
        _fh.write(json.dumps(dict(_same, pnl_c=-2926.0)) + chr(10))
        _fh.write(json.dumps(dict(_same, pnl_c=-2958.0)) + chr(10))
        _fh.write(json.dumps(dict(_same, pnl_c=-2926.0)) + chr(10))   # a true repeat
    _got = load([_f])
    ck(len(_got) == 2 and abs(sum(float(x["pnl_c"]) for x in _got) + 5884.0) < 1e-9,
       "two DIFFERENT legs on one ticker at one second both count (-$58.84); an "
       "identical line repeated after a restart does not. Keying on (ticker, t) "
       "reported that market as -$29.26 and hid half the loss")
    rec = {"kind": "settled", "ticker": "", "pnl_c": 10.0, "t": "2026-09-17T15:00:20Z"}
    ck(et_day_of_record(rec) == "2026-09-17",
       "with no usable ticker it falls back to the timestamp, converted to ET")
    print("pinday selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--glob", default=LIVE_GLOB)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not os.environ.get("KALS_SELFTESTED"):
        selftest()
    recs = load(sorted(glob.glob(a.glob)))
    # only when reading the default crypto glob -- an explicit --glob means the
    # caller asked for one specific set and must not be handed a second one.
    oil = load(sorted(glob.glob(CMD_GLOB))) if a.glob == LIVE_GLOB else []
    if not recs:
        print("loaded nothing")
        return 0
    days = by_et_day(recs)
    print("\n  live settlements by EASTERN day (%d records)" % len(recs))
    print("  %-12s %6s %10s %8s %10s" % ("ET day", "bets", "made", "losses", "lost"))
    tot = {"n": 0, "dollars": 0.0, "losses": 0}
    for d in sorted(days)[-a.days:]:
        v = days[d]
        print("  %-12s %6d %+10.2f %8d %10.2f"
              % (d, v["n"], v["dollars"], v["losses"], v["lost_dollars"]))
    for v in days.values():
        tot["n"] += v["n"]
        tot["dollars"] += v["dollars"]
        tot["losses"] += v["losses"]
    print("  %-12s %6d %+10.2f %8d" % ("ALL TIME", tot["n"], tot["dollars"], tot["losses"]))
    today = et_day_of_epoch(time.time())
    v = days.get(today)
    print("\n  TODAY (%s ET): %s" % (
        today, "nothing settled yet" if not v else
        "%d settled, %+.2f, %d losses" % (v["n"], v["dollars"], v["losses"])))
    # BOTH BOTS. A total that silently omits one of two live bots is worse than
    # no total: on 2026-09-17 the crypto-only figure read +$88 on a day that was
    # +$88 crypto and -$58 commodity, and the operator found the gap himself.
    if oil:
        od = by_et_day(oil)
        print("\n  COMMODITY bot, by EASTERN day (%d records)" % len(oil))
        print("  %-12s %6s %10s %8s" % ("ET day", "bets", "made", "losses"))
        for dd in sorted(od)[-a.days:]:
            w = od[dd]
            print("  %-12s %6d %+10.2f %8d" % (dd, w["n"], w["dollars"], w["losses"]))
        ov = od.get(today)
        c_d = v["dollars"] if v else 0.0
        o_d = ov["dollars"] if ov else 0.0
        print("\n  ===> BOTH BOTS TODAY: crypto %+.2f  commodity %+.2f  =  %+.2f"
              % (c_d, o_d, c_d + o_d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
