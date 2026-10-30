"""test_series.py -- botdata.series: the 7-day and 30-day averages and the clock-change days.

v-tg-rebuild step 8 (2026-10-30): moved out of tgcharts.selftest unchanged (series' tests live here: botdata/tests is
lane A's).
"""
import calendar

from pindesk import et_day, et_day_start
from botdata import series
from botdata.series import AVG_DAYS, LONG_DAYS, avg_by_day, day_avg, ledger_days, prev_day
from phone.charts.base import usd
from phone.charts.tests.planted import NOW, ck, empty_ledger, planted_ledger


def test_seven_day_lines():
    led = planted_ledger()
    today = et_day(NOW)
    avg, navg = day_avg(led, today)
    nets = dict(ledger_days(led))
    want, d = [], today
    for _ in range(AVG_DAYS):
        d = prev_day(d)
        want.append(nets.get(d, 0.0))
    ck(navg == AVG_DAYS and len(avg) == 97 and abs(avg[-1][1] - sum(want) / AVG_DAYS) < 1e-9 and avg[0][1] == 0.0,
       "/today's 7-day line: the %d days before today, ends at their mean day %s (= the ledger's own day totals)"
       % (navg, usd(avg[-1][1] if avg else None)))
    ab = avg_by_day({"2026-10-10": 7.0, "2026-10-12": 14.0}, ["2026-10-10", "2026-10-12", "2026-10-20"])
    ck(ab == {"2026-10-10": 7.0, "2026-10-12": 7.0, "2026-10-20": 0.0},
       "/days' 7-day line: a gap day counts $0, days before the first are left out: %s" % ab)
    ck(day_avg(empty_ledger(), today) == ([], 0), "/today: nothing on the books -> no 7-day line")


def test_thirty_day_lines():
    # the 30-day lines (2026-10-29): the same rule over 30 days, so a young record averages the days it has
    led = planted_ledger()
    today = et_day(NOW)
    avg, navg = day_avg(led, today)
    nets = dict(ledger_days(led))
    _a30, _n30 = day_avg(led, today, LONG_DAYS)
    _listed = [x for x in led.days() if x < today]
    ck(_n30 == len(_listed) > AVG_DAYS and abs(_a30[-1][1] - sum(nets.get(x, 0.0) for x in _listed) / _n30) < 1e-9
       and day_avg(led, today) == (avg, navg),
       "/today's 30-day line: every day on the books before today (%d, under 30 here), its mean day %s; the 7-day line "
       "unchanged" % (_n30, usd(_a30[-1][1] if _a30 else None)))
    _ab30 = avg_by_day({"2026-10-01": 30.0, "2026-10-20": 60.0}, ["2026-10-01", "2026-10-20", "2026-10-30", "2026-11-05"],
                       LONG_DAYS)
    ck(_ab30 == {"2026-10-01": 30.0, "2026-10-20": 4.5, "2026-10-30": 3.0, "2026-11-05": 2.0}
       and [prev_day(x) for x in ("2026-11-02", "2026-11-01", "2026-03-09", "2026-03-01")]
       == ["2026-11-01", "2026-10-31", "2026-03-08", "2026-02-28"]
       and avg_by_day({"2026-10-01": 30.0, "2026-10-20": 60.0}, ["2026-11-05"]) == {"2026-11-05": 0.0},
       "/days' 30-day line: that day and the 29 before, a gap day $0, days before the first left out (Oct 20: 90 / 20 "
       "days; Oct 30: 90 / 30; Nov 5: the Oct 1 day has left the 30), across the Nov 1 clock change: %s" % _ab30)


def test_by_now():
    """by_now: today so far against the average of the days before at the same quarter-hour (the /today pace words)."""
    import botstats as _bsc
    day = "2026-10-20"
    t0 = _bsc.day_start(day)
    rows = [("2026-10-19", _bsc.day_start("2026-10-19") + 3600, 2.0, "pin"),
            ("2026-10-19", _bsc.day_start("2026-10-19") + 20 * 3600, 5.0, "pin"),
            ("2026-10-18", _bsc.day_start("2026-10-18") + 1800, -1.0, "ladder"),
            (day, t0 + 600, 1.5, "pin")]
    so_far, avg, n = series.by_now(rows, _bsc, day, t0 + 2 * 3600 + 100)
    ck(so_far == 1.5 and n == 2 and abs(avg - (2.0 - 1.0) / 2) < 1e-9 and series.by_now(rows[3:], _bsc, day, t0 + 60) == (1.5, None, 0),
       "by_now: $1.50 so far vs the 2 days before at 2 AM ($2 and -$1: +$0.50 a day); no earlier day -> no average")


def test_clock_change_days():
    # 2026-10-30: the clock-change days. Every chart's day boundary is et_day_start / bs.day_start, which read the ET
    # offset at NOON until today: on 2026-11-01 (clocks back at 2 AM) that put midnight at 05:00Z, an hour late, so
    # /today and /yesterday on Nov 1 would have dropped the 12-1 AM hour; on 2026-03-08 an hour early.
    import botstats as _bsc
    _starts = {"2026-10-29": (2026, 10, 29, 4), "2026-11-01": (2026, 11, 1, 4), "2026-11-02": (2026, 11, 2, 5),
               "2026-03-08": (2026, 3, 8, 5), "2026-03-09": (2026, 3, 9, 4)}
    ck(all(et_day_start(k) == _bsc.day_start(k) == calendar.timegm(v + (0, 0)) for k, v in _starts.items()),
       "et_day_start and bs.day_start across both clock changes: Oct 29 04:00Z, Nov 1 04:00Z, Nov 2 05:00Z, Mar 8 "
       "05:00Z, Mar 9 04:00Z")
    _len = {k: (et_day_start(_bsc.shift_day(k, 1)) - et_day_start(k)) / 3600.0 for k in _starts}
    ck(_len == {"2026-10-29": 24.0, "2026-11-01": 25.0, "2026-11-02": 24.0, "2026-03-08": 23.0, "2026-03-09": 24.0}
       and all(prev_day(_bsc.shift_day(k, 1)) == k and et_day(et_day_start(k) - 1) == prev_day(k) for k in _starts),
       "prev_day and shift_day agree with the clock across both changes and the days join up (Nov 1 is 25 hours, "
       "Mar 8 is 23): %s" % _len)


TESTS = [test_seven_day_lines, test_thirty_day_lines, test_by_now, test_clock_change_days]
