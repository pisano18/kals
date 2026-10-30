"""test_versions.py -- version_of: a combined VERSIONS.md heading is each named bot's version; an INSTALLED /
PREPARED heading is not the running one.

v-tg-rebuild step 7 (2026-10-30): moved out of botstats.py's one-piece self-test (its checks verbatim, every botstats
name read through the botstats facade, RESULTS set through botdata.paths). Run:
    C:\\Python314\\python.exe research\\botdata\\tests\\test_versions.py      (or all of them: research\\botstats.py --selftest)
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


def test_versions():
    # 2026-10-01: a heading that ships several bots at once is each bot's own version, by name
    td2 = tempfile.mkdtemp(prefix="botstats_v_")
    saved2 = _paths.RESULTS
    try:
        _paths.set_results(td2)
        with open(os.path.join(td2, bs.VERSIONS_NAME), "w", encoding="utf-8") as fh:
            fh.write("# Versions\n\n"
                     "# v-topup -- LIVE 2026-09-30 12:12:02Z (pid 4447780): top-up to one bet\n"
                     "# v-race40 + v-forecaster-scale + v-ladder-size + v-crash-guard -- LIVE 2026-09-30 12:25:53Z: x\n"
                     "# v-race20 -- 2026-09-28 02:50Z (pid 3739628; pinracearm.py) -- LIVE: coin race 20\n")
        ck(bs.version_of("race")[0] == "v-race40" and bs.version_of("ladder")[0] == "v-ladder-size"
           and bs.version_of("forecaster")[0] == "v-forecaster-scale + v-crash-guard"
           and bs.version_of("pin")[0] == "v-topup",
           "a combined heading is each named bot's version (race v-race40, not the older v-race20); pin keeps its own")
        # 2026-10-18: a heading written before it goes live is not the running version
        with open(os.path.join(td2, bs.VERSIONS_NAME), "w", encoding="utf-8") as fh:
            fh.write("# Versions\n\n"
                     "# v-nopause -- INSTALLED 2026-10-18 ~10:4xZ in restart_bot.ps1, LIVE at the next restart\n\n"
                     "# v-floor95 -- PREPARED 2026-10-03 12:15Z (NOT LIVE until the main bot restarts)\n\n"
                     "# v-ladderboost -- LIVE 2026-10-18T04:42:46Z (pid 923780): ladder boost fix\n")
        ck(bs.version_of("pin")[0] == "v-ladderboost",
           "an INSTALLED / PREPARED heading (live only at the next restart) is not the running version: pin is "
           "still v-ladderboost -- the phone's /stats parser has always skipped them")
    finally:
        _paths.set_results(saved2)
        shutil.rmtree(td2, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(run(dict(globals()), "test_versions"))
