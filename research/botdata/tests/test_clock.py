"""test_clock.py -- day_start / et_day / shift_day across both clock changes (2026-10-30).

v-tg-rebuild step 7 (2026-10-30): moved out of botstats.py's one-piece self-test (its checks verbatim, every botstats
name read through the botstats facade, RESULTS set through botdata.paths). Run:
    C:\\Python314\\python.exe research\\botdata\\tests\\test_clock.py      (or all of them: research\\botstats.py --selftest)
"""
import calendar
import json
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import ck, run                                            # noqa: E402

import botstats as bs                                               # noqa: E402
import pinledger                                                    # noqa: E402,F401
from botdata import paths as _paths                                 # noqa: E402,F401


def test_clock():
    # 2026-10-30: the clock-change days. day_start read the ET offset at NOON until today: on 2026-11-01 (clocks back
    # at 2 AM, so noon is EST but midnight was EDT) that put midnight at 05:00Z, an hour late, and every day total,
    # pace and 'since midnight' figure for Nov 1 would have missed its first hour; on 2026-03-08 an hour early.
    _starts = {"2026-10-29": (2026, 10, 29, 4), "2026-11-01": (2026, 11, 1, 4), "2026-11-02": (2026, 11, 2, 5),
               "2026-03-08": (2026, 3, 8, 5), "2026-03-09": (2026, 3, 9, 4)}
    ck(all(bs.day_start(k) == calendar.timegm(v + (0, 0)) for k, v in _starts.items()),
       "day_start across both clock changes: Oct 29 04:00Z, Nov 1 04:00Z, Nov 2 05:00Z, Mar 8 05:00Z, Mar 9 04:00Z")
    ck(all(bs.et_day(bs.day_start(k)) == k and bs.et_day(bs.day_start(k) - 1) == bs.shift_day(k, -1) for k in _starts),
       "midnight belongs to its day and the second before it to the day before, on every one of them")
    _len = {k: (bs.day_start(bs.shift_day(k, 1)) - bs.day_start(k)) / 3600.0 for k in _starts}
    ck(_len == {"2026-10-29": 24.0, "2026-11-01": 25.0, "2026-11-02": 24.0, "2026-03-08": 23.0, "2026-03-09": 24.0}
       and all(bs.shift_day(bs.shift_day(k, 1), -1) == k for k in _starts)
       and bs.shift_day("2026-10-31", 1) == "2026-11-01" and bs.shift_day("2026-11-02", -1) == "2026-11-01",
       "shift_day walks the calendar across both changes and the days join up: Nov 1 is 25 hours, Mar 8 is 23, the "
       "rest 24 (%s)" % _len)


if __name__ == "__main__":
    sys.exit(run(dict(globals()), "test_clock"))
