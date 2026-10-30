"""The golden alert scripts for the phone's monitor (v-tg-rebuild step 12, lane Q): DOWN bots (with the debounce), the
early warnings before a stop trips, the balance check, the weekly / monthly reports, quiet hours and the outside 'is it
alive' pinger. gl_cases.py adds these TICKS to its own and hands run(...) the tick case. Never imported by production.

Each script turns the monitor on (Phone.monitor_on) on the case's phone and moves the world's frozen clock itself
(run_case puts the clock back after the case); files it writes in the scratch copy are put back by the fence. A tree
without phone/monitor.py answers {"skipped": ...}.
"""
import copy
import os
import sys

TICKS = ["alerts-down"]


def _monitor_state(ph):
    m = getattr(ph, "monitor", None)
    if m is None:
        return None
    return {"down": {k: {"checks": v.get("checks"), "sent": v.get("sent")} for k, v in sorted(m.down.items())}}


def _set_procs(rt, ph, rows):
    rt.procs = rows
    ph.bs_procs = rt.bs_procs_arg()


def run(rt, ph, which, tick):
    """The script `which` on phone `ph`; tick(rt, ph, label) runs one alerts tick and returns what it sent."""
    if "phone.monitor" not in sys.modules:
        try:
            __import__("phone.monitor")
        except ImportError:
            return {"skipped": "this tree has no phone/monitor.py"}
    ph.monitor_on = True
    T0 = rt.clock.T
    ticks = []

    def at(dt, label):
        rt.clock.T = T0 + dt
        d = tick(rt, ph, "+%ds %s" % (dt, label))
        d["monitor"] = _monitor_state(ph)
        ticks.append(d)

    if which == "alerts-down":
        rows0 = copy.deepcopy(rt.procs)
        at(0, "first (learns, sends nothing)")
        if rows0 is None:
            return {"ticks": ticks, "note": "the process table is unreadable here: every bot UNKNOWN, nothing learnt"}
        gone = [r for r in rows0 if "ladder_live.py" not in str(r[2])]
        _set_procs(rt, ph, gone)
        at(30, "ladder's live copy gone, no stop file: check 1")
        at(60, "check 2")
        at(150, "check 3, 2 min: under the 3 min debounce, nothing")
        at(215, "check 4, 3 min 05 s: DOWN alert")
        at(245, "still down: nothing more")
        _set_procs(rt, ph, copy.deepcopy(rows0))
        at(275, "ladder back: back-up alert")
        _set_procs(rt, ph, gone)
        at(300, "a normal restart: gone (check 1)")
        at(330, "check 2")
        _set_procs(rt, ph, copy.deepcopy(rows0))
        at(360, "back within 1 min: nothing was ever sent")
        return {"ticks": ticks}
    return {"skipped": "unknown script %s" % which}
