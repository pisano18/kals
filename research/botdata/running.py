"""running.py -- one bot right now: running or not (its live copy in the process table), its stop file, its log,
the start record its settings are read from, its settings in words, halted or not, its version, the problems to say.

v-tg-rebuild step 7 (2026-10-30): split out of botstats.py verbatim (botstats.py is now a facade over botdata). The
settings_* names are the bot files' own functions (research/bots), kept under their old names.
"""
import json
import os

import bots as _reg
from bots import fx as _b_fx, jumpband as _b_jb, pin as _b_pin
from bots import forecaster as _b_fc, ladder as _b_lad, race as _b_race, weather as _b_wx
from bots.spec import SettingsIn as _SettingsIn
from botdata import activity as _activity
from botdata import logs as _logs
from botdata import paths as _paths
from botdata import status as _status
from botdata import tables as _tables
from botdata import versions as _versions
from botdata.clock import et_clock, et_day, utc_epoch as _epoch


def _toks(cl):
    return str(cl or "").replace('"', " ").split()


def opt(cl, flag):
    t = _toks(cl)
    return t[t.index(flag) + 1] if flag in t and t.index(flag) + 1 < len(t) else None


# v-tg-rebuild step 3 (2026-10-30): each bot's settings words live in its registry file (research/bots/<name>.py,
# verbatim); these are the old names, kept for the phone (pinphone uses settings_race) and the registry's test.
settings_pin = _b_pin.settings_pin
settings_race = _b_race.settings_race
settings_fx = _b_fx.settings_fx
settings_jumpband = _b_jb.settings_jumpband
settings_weather = _b_wx.settings_weather


def settings_clean(name, start, cl):
    """The clean-room bots' settings (the forecaster's, else the ladder's) -- the old name for the two hooks."""
    if name == "forecaster":
        return _b_fc.settings_forecaster(start, cl)
    return _b_lad.settings_ladder(start, cl)


def _read_json(name):
    """A RESULTS json file, or None (a settings hook's reader: the pin bot's pinrun-live-size.json)."""
    try:
        with open(os.path.join(_paths.RESULTS, name), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def running(name, rows, ok, now):
    spec = _tables.SPEC[name]
    stop = os.path.join(_paths.RESULTS, spec["stop"])
    out = {"alive": None, "pid": None, "pids": [], "started_utc": None, "started_et": None, "command": None,
           "keepalive": spec["keepalive"], "stop_flag": os.path.exists(stop), "stop_flag_et": None,
           "stop_flag_text": None, "halted": None, "log": None, "log_age_s": None, "log_last_et": None,
           "version": None, "version_et": None, "version_title": None, "settings": {}, "settings_text": "",
           "problems": []}
    if out["stop_flag"]:
        try:
            out["stop_flag_et"] = et_clock(os.path.getmtime(stop))
            with open(stop, encoding="utf-8", errors="replace") as fh:
                out["stop_flag_text"] = fh.read(200).strip() or None
        except OSError:
            pass
    mine = [r for r in rows or [] if _status.is_bot(name, r[2])] if ok else []
    if ok:
        out["alive"] = bool(mine)
        out["pids"] = [r[0] for r in mine]
        if mine:
            out["pid"], out["command"] = mine[0][0], mine[0][2]
            if mine[0][1]:
                out["started_utc"] = mine[0][1]
        if len(mine) > 1:
            out["problems"].append("%d live copies running (pids %s)" % (len(mine), ", ".join(map(str, out["pids"]))))
    # its log, its latest start record, its settings. v-tg-rebuild step 3 (2026-10-30): the registry says which rule
    # finds the start record (Logs.start_rule: 'first_line' = the pin bot's newest log's first record; 'pid_then_live' =
    # the start record of the running pid, else the newest live one; 'live' = the newest live one), how its settings
    # read (the bot's settings hook), which records halt it and which lift a halt (Records.halts / halt_lifts /
    # halt_lifts_next_day: the jump band's day stop lifts itself the next ET day)
    b = _reg.get(name)
    if b.logs.glob:
        logs = _logs.pin_logs()
        log = logs[-1] if logs else None
    else:
        log = os.path.join(_paths.RESULTS, spec["log"])
        log = log if os.path.exists(log) else None
    start = None
    if log:
        out["log"] = os.path.basename(log)
        try:
            mt = os.path.getmtime(log)
            out["log_age_s"] = round(max(0.0, now - mt), 1)
            out["log_last_et"] = et_clock(mt)
        except OSError:
            pass
        if b.logs.start_rule == "first_line":
            try:
                with open(log, encoding="utf-8") as fh:
                    r = json.loads(fh.readline() or "{}")
                start = r if r.get("kind") == "start" else None
            except (OSError, ValueError):
                start = None
        else:
            pid = out["pid"]
            if pid is not None and b.logs.start_rule == "pid_then_live":
                start = _logs.last_record(log, ("start",), lambda r: r.get("pid") == pid)
            if start is None:
                start = _logs.last_record(log, ("start",), lambda r: r.get("live") is not False)
    if out["started_utc"] is None and start and start.get("t"):
        out["started_utc"] = str(start["t"])[:19] + "Z"
    out["started_et"] = et_clock(_epoch(out["started_utc"])) if out["started_utc"] else None
    out["settings"], out["settings_text"] = b.settings(_SettingsIn(start, out["command"], _read_json))
    if out["settings"].get("variant_mismatch"):
        out["problems"].append("variant: " + out["settings"]["variant_mismatch"])
    # halted since its start?
    if log:
        paths = [log]
        st_t = _logs._t_of(start) if start else None
        lifts = tuple(b.records.halt_lifts)
        for p in paths:
            # 2026-10-26: a 'pause' the bot lifted itself ('resume', pinrun AMENDMENT 14) is not a halt -- the pin bot
            # paused 27 s on its open cap at 10-25 05:59Z and /pin and /bots said HALTED for two days after
            h = _logs.last_record(p, _tables.HALT_KINDS[name] + lifts)
            if h and (h.get("kind") or h.get("ev")) in lifts:
                continue
            ht = _logs._t_of(h) if h else None
            # 2026-10-30: the jump band's day stop names its ET day and lifts by itself the next day (no restart)
            if h and h.get("kind") in b.records.halt_lifts_next_day and h.get("day") and h["day"] != et_day(now):
                continue
            if h and ht is not None and (st_t is None or ht >= st_t):
                out["halted"] = {"t_et": et_clock(ht), "what": h.get("kind") or h.get("ev"),
                                 "why": str(h.get("why") or h.get("day_pnl") or h.get("run_pnl") or _activity._halt_why(h) or "")[:160]}
    v = _versions.version_of(name)
    if v:
        out["version"], out["version_et"], out["version_title"] = v[0], et_clock(v[1]), v[2][:300]
    if ok and not mine and not out["stop_flag"]:
        out["problems"].append("NOT RUNNING and no stop file -- it stopped on its own")
    if ok and mine and out["stop_flag"]:
        out["problems"].append("stop file is set but it is still running (it stops at its next check)")
    if not ok:
        out["problems"].append("could not read the Windows process list")
    return out
