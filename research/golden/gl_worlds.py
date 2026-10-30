"""The golden worlds: one fixture, thirteen situations (eight + five with the coin race active). Each world has a file step (prepare: run by replay.py on the
world's scratch copy of the fixture, before the child starts) and a runtime step (the clock, the process table and
Kalshi's answers, applied by gl_child.py). Never imported by production code."""
import calendar
import json
import os
import time

DST_T = calendar.timegm((2026, 11, 1, 13, 30, 0))      # 8:30 AM EST, the morning the clocks went back (06:00Z)
STALE_S = 7200                                          # kalshi-down: the cache is this much older than the clock
JB_SCRIPT = "jumpband_live.py"
RACE_STOP = "pinracepenny.stop"
JB_STOP = "jumpband-live.stop"
FAKE_PY = r"C:\Python314\python.exe -u C:\kals-repo\research"


def _iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


# ---- the cache's clock fields ----
def shift_cache(path, delta):
    """Move every 'when it was read' stamp in botstats_cache.json by delta seconds (the rows are untouched), keeping
    the file's mtime. delta > 0 = fresher."""
    if not delta or not os.path.exists(path):
        return
    st = os.stat(path)
    with open(path, encoding="utf-8") as fh:
        c = json.load(fh)
    shift_cache_dict(c, delta)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(c, fh, separators=(",", ":"))
    os.utime(path, (st.st_atime, st.st_mtime))


def shift_cache_dict(c, delta):
    def mv(d, keys):
        for k in keys:
            if isinstance(d, dict) and isinstance(d.get(k), (int, float)) and not isinstance(d.get(k), bool):
                d[k] = d[k] + delta
    for x in (c.get("subs") or {}).values():
        mv(x, ("tried", "fetched", "pos_t", "bal_t"))
    mv(c.get("ledgers") or {}, ("tried", "fetched"))
    mv(c.get("good") or {}, ("t",))
    mv(c.get("procs") or {}, ("t",))
    return c


def newest_read(c):
    ts = [float(x.get("tried")) for x in (c.get("subs") or {}).values() if isinstance(x.get("tried"), (int, float))]
    lt = (c.get("ledgers") or {}).get("tried")
    if isinstance(lt, (int, float)):
        ts.append(float(lt))
    return max(ts) if ts else None


def _touch(path, text, mtime):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.utime(path, (mtime, mtime))


def _rm(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


# ---- process-table edits ----
def _without(rows, script):
    return [r for r in rows if script not in str(r[2])]


def _jb_row(T, extra):
    return [99903, _iso(T - 3 * 3600), "%s\\cleanroom\\%s --live --subaccount 3 --max-contracts 5%s" % (FAKE_PY, JB_SCRIPT, extra)]


def _race_row(T):
    return [99902, _iso(T - 5 * 3600), "%s\\pinracearm.py --live --penny --log pinracepenny-live.jsonl" % FAKE_PY]


# ======================================================================================================== worlds
def _base(rows, T):
    return rows


def _race_stop_procs(rows, T):
    if rows is None:
        return rows
    live = [r for r in rows if "pinracearm.py" in str(r[2]) and "--live" in str(r[2]).split()
            and "--paper-live" not in str(r[2]).split()]
    return rows if live else rows + [_race_row(T)]


def _race_stop_files(res, T):
    _touch(os.path.join(res, RACE_STOP), "golden: race stopped by its stop file\n", T - 3600)


def _jb_files(res, T):
    _rm(os.path.join(res, JB_STOP))


def _empty_logs(res, T):
    for name in os.listdir(res):
        p = os.path.join(res, name)
        if os.path.isfile(p) and name.lower().endswith((".jsonl", ".log", ".out")):
            st = os.stat(p)
            with open(p, "w", encoding="utf-8"):
                pass
            os.utime(p, (st.st_atime, st.st_mtime))


def _no_cached_procs(res, T):
    p = os.path.join(res, "botstats_cache.json")
    if os.path.exists(p):
        st = os.stat(p)
        with open(p, encoding="utf-8") as fh:
            c = json.load(fh)
        c["procs"] = None
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(c, fh, separators=(",", ":"))
        os.utime(p, (st.st_atime, st.st_mtime))


WORLDS = {
    "base": dict(desc="the fixture as captured", procs=_base),
    "race-stopfile": dict(desc="the coin race's live copy running WITH pinracepenny.stop set (it refuses every trade)",
                          procs=_race_stop_procs, files=_race_stop_files),
    "jumpband-live": dict(desc="jumpband_live.py --live running, no stop file",
                          procs=lambda rows, T: None if rows is None else _without(rows, JB_SCRIPT) + [_jb_row(T, "")],
                          files=_jb_files),
    "jumpband-dry-run": dict(desc="jumpband_live.py --live --dry-run running (sends nothing), no stop file",
                             procs=lambda rows, T: None if rows is None else
                             _without(rows, JB_SCRIPT) + [_jb_row(T, " --dry-run")], files=_jb_files),
    "procs-unreadable": dict(desc="the process table cannot be read (every reader None, no cached table)",
                             procs=lambda rows, T: None, files=_no_cached_procs),
    "kalshi-down": dict(desc="Kalshi answers 500 to everything; botstats' cache is %d s stale" % STALE_S,
                        procs=_base, kalshi="down", cache_delta=lambda env, T: -STALE_S),
    "dst-2026-11-01": dict(desc="the clock at 2026-11-01 13:30Z (8:30 AM EST, after the clocks went back); the cache "
                                "re-stamped fresh at that clock",
                           procs=_base, T=lambda env: DST_T, cache_delta=lambda env, T: T - float(env["T"])),
    "empty-logs": dict(desc="every *.jsonl / *.log / *.out in results/ emptied (sizes 0, mtimes kept)",
                       procs=_base, files=_empty_logs),
}


# ---- the coin race ACTIVE (folded in from shadow_race_world.py at rebuild step 10): each is a golden world with the
# race's stop file removed and its live copy in the process table (the fixture has the race paused, so in the eight
# worlds above /race and /racestats are only the router's 'hidden' answer)
RACE_BASES = {"race-active": "base", "race-active-procs-unreadable": "procs-unreadable",
              "race-active-kalshi-down": "kalshi-down", "race-active-dst": "dst-2026-11-01",
              "race-active-empty-logs": "empty-logs"}


def _no_race_stop(files):
    def f(res, T):
        if files:
            files(res, T)
        _rm(os.path.join(res, RACE_STOP))
    return f


def _race_live(procs):
    def p(rows, T):
        return _race_stop_procs(procs(rows, T), T)        # a live race row unless one is there (None stays None)
    return p


for _name, _base_name in RACE_BASES.items():
    _w = dict(WORLDS[_base_name])
    _w["desc"] = "%s; the coin race ACTIVE (its live copy running, pinracepenny.stop removed)" % _w["desc"]
    _w["files"] = _no_race_stop(_w.get("files"))
    _w["procs"] = _race_live(_w["procs"])
    WORLDS[_name] = _w
ORDER = list(WORLDS)


def world_T(name, env):
    w = WORLDS[name]
    return float(w["T"](env)) if w.get("T") else float(env["T"])


def prepare(name, res_dir, env):
    """The world's file step, on its scratch results/ folder."""
    w = WORLDS[name]
    T = world_T(name, env)
    if w.get("cache_delta"):
        shift_cache(os.path.join(res_dir, "botstats_cache.json"), w["cache_delta"](env, T))
    if w.get("files"):
        w["files"](res_dir, T)


def procs_for(name, rows, env):
    import copy
    return WORLDS[name]["procs"](copy.deepcopy(rows), world_T(name, env))


def kalshi_mode(name):
    return WORLDS[name].get("kalshi", "record")
