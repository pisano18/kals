"""The golden alert scripts for the phone's monitor (v-tg-rebuild step 12, lane Q): DOWN bots (with the debounce), the
early warnings before a stop trips, the balance check, the weekly / monthly reports, quiet hours and the outside 'is it
alive' pinger. gl_cases.py adds these TICKS to its own and hands run(...) the tick case. Never imported by production.

Each script turns the monitor on (Phone.monitor_on) on the case's phone and moves the world's frozen clock itself
(run_case puts the clock back after the case); files it writes in the scratch copy are put back by the fence. A tree
without phone/monitor.py answers {"skipped": ...}.
"""
import copy
import glob
import json
import os
import sys
import time

TICKS = ["alerts-down", "alerts-stops"]


def _iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def _results():
    """The results folder as the code under test names it (the fence maps it to the world's scratch copy)."""
    return sys.modules["botdata.paths"].RESULTS


def _append(name, recs, mtime):
    """Append records to a results log; its mtime is set to `mtime` (the world's clock), never this machine's."""
    p = os.path.join(_results(), name)
    with open(p, "a", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    os.utime(p, (mtime, mtime))


def _monitor_state(ph):
    m = getattr(ph, "monitor", None)
    if m is None:
        return None
    out = {"down": {k: {"checks": v.get("checks"), "sent": v.get("sent")} for k, v in sorted(m.down.items())}}
    if getattr(m, "gauge", None):
        out["stops"] = {" / ".join(k): v for k, v in sorted(m.gauge.items())}
    return out


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
    if which == "alerts-stops":
        T = T0
        pin = sorted(glob.glob(os.path.join(_results(), "pinrun-live-*.jsonl")))
        pin = os.path.basename(pin[-1]) if pin else "pinrun-live-20261028T011720Z.jsonl"
        _append("jumpband-live.jsonl", [{"t": _iso(T - 60), "kind": "start", "live": True, "stop_line": -25.0,
                                         "day_stop": -15.0, "line_money": 0.56}], T)
        _append(pin, [{"t": _iso(T - 60), "kind": "autosize", "loss_abort": -255.3, "why": "bank $1365.22"}], T)
        at(0, "first (learns, sends nothing)")
        _append("jumpband-live.jsonl", [{"t": _iso(T + 30), "kind": "settle", "line_money": -15.5, "day_money": -10.2}],
                T + 30)
        _append(pin, [{"t": _iso(T + 30), "kind": "settled", "realised": 176.97, "day_realised": -160.0}], T + 30)
        at(61, "jump band $9.50 from its stop line and $4.80 from its day stop; pin bot at 63% of its loss abort")
        _append("jumpband-live.jsonl", [{"t": _iso(T + 70), "kind": "settle", "line_money": -25.4, "day_money": -15.4}],
                T + 70)
        at(122, "the jump band trips both (urgent)")
        at(190, "nothing more")
        return {"ticks": ticks}
    return {"skipped": "unknown script %s" % which}
