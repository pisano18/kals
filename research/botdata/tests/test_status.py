"""test_status.py -- botdata/status.py: each bot's STATE, the SHOWN policy (= v-tg-active's is_active, checked on every
combination), fleet() memo and fail-safe, and botstats' old names.

v-tg-rebuild step 4 (2026-10-30). Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_status.py
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import ck, run, sandbox                                   # noqa: E402

import bots                                                         # noqa: E402
from botdata import procs, status                                   # noqa: E402
import botstats as bs                                               # noqa: E402

LIVE = {"pin": "C:\\Python314\\python.exe -u C:\\kals-live-0925n\\research\\pinrun.py --live --size 20",
        "race": "\"C:\\Python314\\python.exe\" -u research/pinracearm.py --live --max-contracts 20",
        "forecaster": "python -u research\\cleanroom\\forecaster_live.py --subaccount 2 --live",
        "ladder": "\"C:\\Python314\\python.exe\" -u research\\cleanroom\\ladder_live.py --subaccount 1 --live",
        "weather": "python research\\sweep\\dipsell_live.py --subaccount 3 --live",
        "fx": "\"C:\\Python314\\python.exe\" -u research\\cleanroom\\fxtake_live.py --subaccount 5 --live",
        "jumpband": "C:\\Python314\\python.exe -u research\\cleanroom\\jumpband_live.py --live --subaccount 3"}
PAPER = ["python -u research/pinracearm.py --paper-live --live-tau-max 60",
         "C:\\Python314\\python.exe -u research\\cleanroom\\jumpband_live.py --minutes 20160",
         "python research\\cleanroom\\jumpband_live.py --live --dry-run --subaccount 3",
         "python -u research/pinrun.py --size 20 --arm-name arm-x"]


def _stop(td, name, on=True):
    p = os.path.join(td, bots.get(name).stop_file)
    if on:
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("paused")
    elif os.path.exists(p):
        os.remove(p)


def test_states():
    with sandbox() as td:
        for b in ("race", "forecaster", "weather"):
            _stop(td, b)
        rows = [[k + 1, "", LIVE[b]] for k, b in enumerate(("pin", "race", "ladder", "fx", "jumpband"))]
        rows += [[100 + k, "", cl] for k, cl in enumerate(PAPER)]
        f = status.fleet_from(procs._norm_procs(rows), True, 5.0)
        want = {"pin": status.ACTIVE, "race": status.STOPPING, "forecaster": status.STOPPED, "ladder": status.ACTIVE,
                "weather": status.STOPPED, "fx": status.ACTIVE, "jumpband": status.ACTIVE}
        ck({s.name: s.state for s in f.bots} == want,
           "STATES: a live copy without its stop file ACTIVE, with it STOPPING (the race), a stop file and no live copy "
           "STOPPED; paper arms and a --live --dry-run are no bot's live copy: %s" % {s.name: s.state for s in f.bots})
        ck(f.shown == ("pin", "ladder", "fx", "jumpband") and f.hidden == ("race", "forecaster", "weather")
           and f.active == f.shown and f.state("race") == status.STOPPING and f.by_name["race"].stop_since is not None
           and f.by_name["race"].pids == (2,) and f.procs_ok,
           "SHOWN = ACTIVE (+ UNKNOWN + the pin bot); the race's pid and stop time are kept")
        _stop(td, "race", False)
        f2 = status.fleet_from(procs._norm_procs([r for r in rows if r[0] != 1]), True)
        ck(f2.state("race") == status.ACTIVE and f2.state("pin") == status.DOWN and "pin" in f2.shown,
           "the race's stop file removed -> ACTIVE again; the pin bot not running and no stop file -> DOWN, and still "
           "shown (always_shown)")
        f3 = status.fleet_from(None, False)
        ck(f3.state("ladder") == status.UNKNOWN and f3.state("forecaster") == status.STOPPED and not f3.procs_ok
           and f3.shown == ("pin", "race", "ladder", "fx", "jumpband"),
           "the table unreadable: no stop file -> UNKNOWN and shown, a stop file -> STOPPED and hidden")


def test_shown_is_is_active_everywhere():
    """The SHOWN policy == botstats' is_active on every combination of stop file x live copy x paper arm, readable or not."""
    names = bots.names()
    n = 0
    with sandbox() as td:
        for stops in itertools.product((False, True), repeat=len(names)):
            if sum(stops) > 3:
                continue
            for b, on in zip(names, stops):
                _stop(td, b, on)
            for running in ((), ("pin",), ("race", "jumpband"), tuple(names), ("weather", "fx", "ladder")):
                rows = [[k + 1, "", LIVE[b]] for k, b in enumerate(running)] + [[99, "", PAPER[1]]]
                for ok in (True, False):
                    r = procs._norm_procs(rows) if ok else None
                    f = status.fleet_from(r, ok)
                    want = tuple(b for b in names if status.is_active(b, r, ok))
                    if f.shown != want or status.active_from(r, ok) != want:
                        ck(False, "shown %s != is_active %s (stops %s, running %s, ok %s)" % (f.shown, want, stops,
                                                                                              running, ok))
                    n += 1
    ck(n > 500, "SHOWN == is_active on %d combinations" % n)


def test_fleet_memo_and_fail_safe():
    with sandbox() as td:
        _stop(td, "race")
        saved = procs._procs_native
        calls = []
        try:
            procs._procs_native = lambda: (calls.append(1) or [[1, "", LIVE["pin"]], [2, "", LIVE["race"]]])
            a = status.fleet(now=1000.0)
            b = status.fleet(now=1005.0)
            c = status.fleet(now=1000.0 + status.FLEET_TTL_S + 1)
            ck(a is b and len(calls) == 2 and c is not a and a.state("race") == status.STOPPING,
               "fleet(): memoised FLEET_TTL_S, then read again")
            ck(status.active_bots(now=2000.0) == ("pin",) and status.active_bots(now=2001.0) == ("pin",),
               "active_bots(): the shown bots from the same read")

            def boom():
                raise OSError("boom")
            f = status.fleet(procs=boom)
            ck(f.shown == ("pin", "forecaster", "ladder", "weather", "fx", "jumpband") and not f.procs_ok
               and f.state("race") == status.STOPPED,
               "fleet() never raises: a raising read shows every bot without a stop file, UNKNOWN (fail-safe)")
            ck(status.fleet(procs=lambda: None).shown == f.shown and status.active_bots(procs=boom) == f.shown,
               "a failed read (None) and a raising one agree, in fleet() and active_bots()")
        finally:
            procs._procs_native = saved


def test_botstats_names():
    ck(bs.is_active is status.is_active and bs.active_bots is status.active_bots and bs.shown_by is status.shown_by
       and bs.shown_parts is status.shown_parts and bs.shown_name is status.shown_name and bs._ACTIVE is status._ACTIVE
       and bs.ALWAYS_SHOWN == ("pin",) and bs.EARLIER == "earlier" and bs.stop_set is status.stop_set
       and bs.is_bot is status.is_bot and bs.fleet is status.fleet,
       "botstats' v-tg-active names are botdata.status' objects")
    with sandbox() as td:
        ck(bs.RESULTS == td and not status.stop_set("race"), "botstats.RESULTS reads botdata.paths' RESULTS")
        _stop(td, "race")
        ck(status.stop_set("race") and bs.stop_set("race"), "and a stop file there is seen by both")
    old = bs.RESULTS
    bs.RESULTS = os.path.join(old, "elsewhere")
    try:
        from botdata import paths
        ck(paths.RESULTS == os.path.join(old, "elsewhere"), "setting botstats.RESULTS sets botdata.paths.RESULTS")
    finally:
        bs.RESULTS = old


if __name__ == "__main__":
    sys.exit(run(dict(globals()), "test_status"))
