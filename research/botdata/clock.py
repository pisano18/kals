"""clock.py -- ET days and clocks for people, UTC inside. The EXISTING implementations, copied verbatim.

v-tg-rebuild step 2 (2026-10-30). Nothing in production calls these yet (the registry's bot files do); botstats,
pinphone and tgcharts keep their own copies until their steps move them. Where the old copies differ they are NOT
merged here -- each is kept under its own name so every caller can stay on its own behaviour:

  et_day        botstats.et_day (= pinday.et_day_of_epoch: float(epoch) first). pindesk.et_day, which pinphone and
                tgcharts import, does the same arithmetic without the float() -- identical for every number.
  day_start     botstats.day_start (offset read at 05:00Z of that date, 2026-10-30). pindesk.et_day_start is the same
                rule written out with a local; same results.
  shift_day     botstats.shift_day: calendar days by way of noon UTC.
  prev_day      tgcharts.prev_day: date arithmetic (2026-10-29: the old et_day(et_day_start(day) - 3600) never left
                2026-11-01). Same answers as shift_day(day, -1).
  day_minus     pinphone.day_minus / days_between: datetime.date arithmetic.
  day_label     botstats.day_label: 'Sep 5'.
  et_clock      botstats.et_clock: 'Sep 30 12:15 AM ET'. NOT tgcharts.et_clock(e, fmt), which is pindesk.et_str ('3:15 PM',
                no 'ET', leading zero stripped): a different function with the same name -- step 8 renames it.
  utc_epoch     botstats._epoch: '2026-09-30T04:15:06.437143Z' -> epoch (pindesk.parse_t is the same but returns an int).
"""
import calendar
import datetime
import os
import sys
import time

_RESEARCH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RESEARCH not in sys.path:
    sys.path.insert(0, _RESEARCH)
from downtime import et_offset                                   # noqa: E402  (pinday's and pindesk's offset)


def utc_epoch(t):
    """'2026-09-30T04:15:06.437143Z' or '...:06Z' -> UTC epoch, or None.  (botstats._epoch)"""
    try:
        return float(calendar.timegm(time.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S")))
    except (TypeError, ValueError):
        return None


def et_day(epoch):
    """'YYYY-MM-DD' in Eastern, from a UTC epoch.  (botstats.et_day -> pinday.et_day_of_epoch)"""
    e = float(epoch) + et_offset(float(epoch))
    return time.strftime("%Y-%m-%d", time.gmtime(e))


def day_start(day):
    """Epoch of midnight ET at the start of 'YYYY-MM-DD' (pindesk.et_day_start).

    2026-10-30: the offset is read at 05:00Z of that date (00:00 EST or 01:00 EDT, always before the 2 AM clock
    change), not at noon, which put 2026-11-01's midnight an hour late and 2026-03-08's an hour early."""
    y, m, d = (int(x) for x in day.split("-"))
    return calendar.timegm((y, m, d, 0, 0, 0)) - et_offset(calendar.timegm((y, m, d, 5, 0, 0)))


def shift_day(day, k):
    """(botstats.shift_day)"""
    y, m, d = (int(x) for x in day.split("-"))
    return time.strftime("%Y-%m-%d", time.gmtime(calendar.timegm((y, m, d, 12, 0, 0)) + 86400 * k))


def prev_day(day):
    """The ET day before `day`, by the calendar. 2026-10-29: it was et_day(et_day_start(day) - 3600), which never left
    2026-11-01 (the 25-hour day the clocks go back: et_day_start puts its midnight an hour late), so from Nov 2 every
    7-day line would have counted Nov 1 over and over instead of the days before it.  (tgcharts.prev_day)"""
    return (datetime.date.fromisoformat(day) - datetime.timedelta(days=1)).isoformat()


def day_minus(day, k):
    """(pinphone.day_minus)"""
    d = datetime.date.fromisoformat(day) - datetime.timedelta(days=k)
    return d.isoformat()


def days_between(day0, day1):
    """Calendar days from day0 to day1 inclusive (1 when equal).  (pinphone.days_between)"""
    return (datetime.date.fromisoformat(day1) - datetime.date.fromisoformat(day0)).days + 1


def day_label(day):
    """'2026-09-05' -> 'Sep 5'.  (botstats.day_label)"""
    try:
        tm = time.strptime(day, "%Y-%m-%d")
    except (TypeError, ValueError):
        return str(day)
    return "%s %d" % (time.strftime("%b", tm), tm.tm_mday)


def ampm(h, m):
    """(botstats._ampm)"""
    return "%d:%02d %s" % (h % 12 or 12, m, "AM" if h < 12 else "PM")


def et_clock(epoch, with_day=True):
    """UTC epoch -> 'Sep 30 12:15 AM ET' (or '12:15 AM ET').  (botstats.et_clock)"""
    if epoch is None:
        return None
    tm = time.gmtime(float(epoch) + et_offset(float(epoch)))
    hm = ampm(tm.tm_hour, tm.tm_min)
    return ("%s %d %s ET" % (time.strftime("%b", tm), tm.tm_mday, hm)) if with_day else hm + " ET"
