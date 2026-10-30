"""test_running.py -- the coin race's settings in words (v-race40's daily loss stop).

v-tg-rebuild step 7 (2026-10-30): moved out of botstats.py's one-piece self-test (its checks verbatim, every botstats
name read through the botstats facade, RESULTS set through botdata.paths). Run:
    C:\\Python314\\python.exe research\\botdata\\tests\\test_running.py      (or all of them: research\\botstats.py --selftest)
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


def test_running():
    _s40, _t40 = bs.settings_race(None, "python -u research/pinracearm.py --live --max-contracts 40 --max-stake 120 "
                                     "--live-max-losses 2")
    ck("40 contracts a bet" in _t40 and "stops for the rest of the ET day after 2 losing races" in _t40
       and "first loss" not in _t40, "v-race40: the race's rules read 40 a bet and the daily 2-loss stop")
    _s1, _t1 = bs.settings_race({"live_rails": {"stop_on_loss": True}}, "python -u research/pinracearm.py --live")
    ck("stops after its first loss" in _t1, "NULL: without --live-max-losses the old first-loss stop is still described")


if __name__ == "__main__":
    sys.exit(run(dict(globals()), "test_running"))
