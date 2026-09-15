#!/usr/bin/env python3
"""downtime.py -- hours the live bot could NOT trade, so a bad day is not
mistaken for a weak strategy.

THE OPERATOR, 2026-09-15: "We lost 7 hours of trade time today. Make sure
that's known for any future calculations so it doesn't make our daily
calculations look worse."

That day the bot was unable to trade from 13:29Z to 20:24Z -- a Windows Update
restart, then Kalshi's account block, then a deleted API key -- plus two short
crashes after midnight. A per-calendar-day figure for 2026-09-15 would read as
a quarter-to-a-third weaker than the strategy actually was. Divide by the hours
it could trade instead.

The windows live in results/DOWNTIME.json. Add a window WHEN an outage happens;
reconstructing one later is how the numbers go wrong.

    python research/downtime.py --selftest
    python research/downtime.py            # lost hours per ET day
"""
import calendar
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(os.path.dirname(HERE), "results", "DOWNTIME.json")


def _epoch(s):
    return calendar.timegm(dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").timetuple())


def load(path=PATH):
    """[(start_epoch, end_epoch, cause)], merged where they touch or overlap.

    Merging matters: two windows that share an edge must not count the shared
    second twice, and an accidental duplicate entry must not double a day's
    lost hours."""
    if not os.path.exists(path):
        return []
    raw = json.load(open(path, encoding="utf-8")).get("windows", [])
    spans = sorted((_epoch(w["start"]), _epoch(w["end"]), w.get("cause", ""))
                   for w in raw)
    return merge(spans)


def merge(spans):
    out = []
    for a, b, c in sorted(spans):
        if b <= a:
            continue
        if out and a <= out[-1][1]:
            pa, pb, pc = out[-1]
            out[-1] = (pa, max(pb, b), pc if c in pc else (pc + "; " + c).strip("; "))
        else:
            out.append((a, b, c))
    return out


def lost_seconds(t0, t1, spans=None):
    """Seconds inside [t0, t1) the bot could not trade."""
    spans = load() if spans is None else spans
    return sum(max(0, min(b, t1) - max(a, t0)) for a, b, _ in spans)


def et_offset(epoch):
    """UTC-4 from the second Sunday of March to the first Sunday of November,
    else UTC-5. Presentation only -- the data stays UTC."""
    y = dt.datetime.utcfromtimestamp(epoch).year
    mar = dt.datetime(y, 3, 8)
    dst_start = mar + dt.timedelta(days=(6 - mar.weekday()) % 7, hours=7)
    nov = dt.datetime(y, 11, 1)
    dst_end = nov + dt.timedelta(days=(6 - nov.weekday()) % 7, hours=6)
    t = dt.datetime.utcfromtimestamp(epoch)
    return -4 * 3600 if dst_start <= t < dst_end else -5 * 3600


def lost_by_et_day(spans=None):
    """{'YYYY-MM-DD' (Eastern): lost_hours}."""
    spans = load() if spans is None else spans
    out = {}
    for a, b, _ in spans:
        t = a
        while t < b:
            off = et_offset(t)
            local = dt.datetime.utcfromtimestamp(t + off)
            day_end = calendar.timegm((local.date() + dt.timedelta(days=1)).timetuple()) - off
            seg = min(b, day_end) - t
            k = local.strftime("%Y-%m-%d")
            out[k] = out.get(k, 0.0) + seg / 3600.0
            t += seg
    return out


def hours_up_et_day(day, now_epoch=None, spans=None):
    """Hours the bot COULD trade on an Eastern day, counting only time that has
    already happened.

    The first version used 24 - lost. On an unfinished day that counts hours
    that have not happened yet: at 4:50 PM on 2026-09-15 it spread $57 over
    16.4 "hours up" when only 9.2 had actually passed with the bot able to
    trade, and reported $3.49/h where the truth was about $6.40/h. The operator
    caught it: "It made $58 just between 12:01 am and 9:15"."""
    import time as _time
    spans = load() if spans is None else spans
    now = _time.time() if now_epoch is None else now_epoch
    y, m, d = (int(x) for x in day.split("-"))
    noon_utc = calendar.timegm((y, m, d, 12, 0, 0))
    off = et_offset(noon_utc)
    start = calendar.timegm((y, m, d, 0, 0, 0)) - off
    end = min(start + 86400, now)
    if end <= start:
        return 0.0
    return max(0.0, (end - start - lost_seconds(start, end, spans)) / 3600.0)


def per_trading_hour(amount, day_hours, lost_hours):
    """`amount` spread over the hours the bot could actually trade, or None."""
    up = day_hours - lost_hours
    return None if up <= 0 else amount / up


def selftest():
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok: " if c else "FAIL: ") + m)
        ok = ok and c

    sp = merge([(100, 200, "a"), (150, 300, "b"), (400, 500, "c")])
    ck(sp == [(100, 300, "a; b"), (400, 500, "c")],
       "overlapping windows merge into one and a separate one stays separate")
    ck(merge([(100, 200, "a"), (100, 200, "a")]) == [(100, 200, "a")],
       "an accidental duplicate does not double the lost time")
    ck(merge([(100, 200, "a"), (200, 300, "b")]) == [(100, 300, "a; b")],
       "windows that share an edge merge, so the shared second counts once")
    ck(lost_seconds(0, 1000, sp) == 300,
       "lost seconds inside a range are the sum of the merged overlaps (200 + 100)")
    ck(lost_seconds(250, 450, sp) == 100,
       "a range cutting through two windows counts only its own slice (50 + 50)")
    ck(lost_seconds(0, 50, sp) == 0 and lost_seconds(0, 1000, []) == 0,
       "NULL: no overlap, or no windows at all, is zero lost time")
    ck(merge([(300, 100, "backwards")]) == [],
       "a window that ends before it starts is dropped, never counted negative")
    ck(per_trading_hour(100.0, 24.0, 7.0) == 100.0 / 17.0,
       "$100 on a day that lost 7 hours is $5.88 per trading hour, not $4.17")
    ck(per_trading_hour(10.0, 24.0, 24.0) is None,
       "and a day with no trading hours has no rate at all, not a division by zero")
    # hours up count only time that has HAPPENED
    day_sp = [(_epoch("2026-09-15T17:00:00Z"), _epoch("2026-09-15T19:00:00Z"), "x")]
    at_1650 = _epoch("2026-09-15T20:50:00Z")          # 4:50 PM Eastern
    ck(abs(hours_up_et_day("2026-09-15", at_1650, day_sp) - (16 + 50 / 60.0 - 2)) < 1e-9,
       "at 4:50 PM a day that lost 2 hours has 14.83 hours up, NOT 22 -- the "
       "hours after 4:50 PM have not happened yet")
    ck(abs(hours_up_et_day("2026-09-15", _epoch("2026-09-17T00:00:00Z"), day_sp) - 22.0) < 1e-9,
       "and once the day is over it has 24 - 2 = 22")
    ck(hours_up_et_day("2026-09-20", at_1650, day_sp) == 0.0,
       "a day that has not started has no hours up")
    sep15 = _epoch("2026-09-15T13:29:10Z")
    ck(et_offset(sep15) == -4 * 3600, "September is EDT, UTC-4")
    ck(et_offset(_epoch("2026-12-15T13:00:00Z")) == -5 * 3600, "December is EST, UTC-5")
    d = lost_by_et_day([(_epoch("2026-09-16T02:00:00Z"), _epoch("2026-09-16T06:00:00Z"), "x")])
    ck(abs(d.get("2026-09-15", 0) - 2.0) < 1e-9 and abs(d.get("2026-09-16", 0) - 2.0) < 1e-9,
       "an outage from 10 PM to 2 AM Eastern splits 2 hours to each Eastern day")
    real = load()
    sep = lost_by_et_day(real).get("2026-09-15")
    if sep is not None:
        # only THAT day is pinned; adding later outages must not break this
        ck(6.9 < sep < 7.7,
           "2026-09-15 reads %.2f hours lost (6h55m main + ~40m of crashes)" % sep)
    print("downtime selftest:", "OK" if ok else "FAILED")
    return ok


def main():
    if not selftest():
        return 1
    if "--selftest" in sys.argv:
        return 0
    spans = load()
    if not spans:
        print("loaded nothing -- no downtime recorded")
        return 0
    print("\nHours the live bot could NOT trade, by Eastern day:")
    for k, v in sorted(lost_by_et_day(spans).items()):
        print("  %s  %5.2f h lost  ->  %5.2f h it could trade" % (k, v, 24 - v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
