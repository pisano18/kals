"""status.py -- which bots are running, and which the phone SHOWS (v-tg-active), in one place.

v-tg-rebuild step 4 (2026-10-30). Moved here from botstats (is_bot, stop_set, is_active, active_from, active_bots,
shown_parts, shown_by, shown_name, verbatim) and put in words a bot's STATE (DESIGN 3.3):

  ACTIVE    a live copy runs (the registry's is_bot: its script and its live rule) and its stop file is absent
  STOPPING  a live copy runs WITH its stop file set (the coin race since 10-27: it keeps running, refusing every trade)
  STOPPED   its stop file is set and no live copy runs (or the table could not be read)
  DOWN      no live copy runs and no stop file: it stopped on its own (crashed)
  UNKNOWN   no stop file, and the process table could not be read
  RETIRED   the registry says retired=True

SHOWN = ACTIVE + UNKNOWN, plus every always_shown bot (the pin bot: /status, /pause and /start are about it) -- exactly
v-tg-active's is_active: a stop-filed bot is hidden, a failed read hides nothing else. Nothing here hides money: every
total keeps every bot's markets, and all_bots puts a hidden bot's past money on one line, 'earlier bots'.

fleet(procs=None, now=None) -> Fleet: every bot's BotStatus at once, memoised FLEET_TTL_S, never raising (on any error
every non-retired bot without a stop file is shown, UNKNOWN). active_bots() is fleet().shown, as a tuple in bot order.
pinphone.fleet() (its paper arms, by role) is a different view; the phone switches to this table in a later step.
"""
import os
import time
from dataclasses import dataclass, field

import bots as _reg
from botdata import paths as _paths
from botdata import procs as _procs

ACTIVE, STOPPING, STOPPED, DOWN, UNKNOWN, RETIRED = "active", "stopping", "stopped", "down", "unknown", "retired"
SHOWN_STATES = (ACTIVE, UNKNOWN)
ALWAYS_SHOWN = _reg.table("ALWAYS_SHOWN")       # ("pin",)
ACTIVE_TTL_S = 10               # the process table + stop files are re-read at most this often for active_bots()
FLEET_TTL_S = ACTIVE_TTL_S
_ACTIVE = {"t": 0.0, "v": None}
_FLEET = {"t": 0.0, "v": None}

EARLIER = _reg.EARLIER          # all_bots' one line for every hidden bot's past money
EARLIER_LABEL = "Earlier bots"


@dataclass(frozen=True)
class BotStatus:
    name: str
    state: str
    pids: tuple = ()
    stop_since: object = None           # the stop file's mtime (epoch) when it is set
    shown: bool = False


@dataclass(frozen=True)
class Fleet:
    t: float
    procs_ok: bool
    bots: tuple = ()                    # BotStatus, bot order
    active: tuple = ()                  # state ACTIVE
    shown: tuple = ()                   # what the phone lists bot by bot (the SHOWN policy)
    hidden: tuple = ()
    by_name: dict = field(default_factory=dict, compare=False, repr=False)

    def state(self, name):
        s = self.by_name.get(name)
        return None if s is None else s.state


# ---- one bot ---------------------------------------------------------------------------------------------------------
def is_bot(name, cl):
    """Is this command line the LIVE copy of `name`? Paper arms of the same script are not (the registry's rule: its
    script and its is_live -- the race's --paper-live and the jump band's --live --dry-run are not the live copy)."""
    return _reg.is_bot(name, cl)


def _stop_path(name):
    return os.path.join(_paths.RESULTS, _reg.get(name).stop_file)


def stop_set(name):
    """True when bot `name`'s stop file exists (False when it cannot be looked at)."""
    try:
        return os.path.exists(_stop_path(name))
    except (OSError, KeyError, TypeError, AttributeError):
        return False


def _stop_since(name):
    try:
        return os.path.getmtime(_stop_path(name))
    except (OSError, KeyError, TypeError, AttributeError):
        return None


def status_of(name, rows, ok):
    """BotStatus of bot `name` from a process table already read ([pid, started, cmdline] rows; ok False = unreadable)."""
    b = _reg.get(name)
    stop = stop_set(name)
    pids = tuple(r[0] for r in rows or [] if is_bot(name, r[2])) if ok and rows is not None else ()
    if b.retired:
        state = RETIRED
    elif not ok or rows is None:
        state = STOPPED if stop else UNKNOWN
    elif pids:
        state = STOPPING if stop else ACTIVE
    else:
        state = STOPPED if stop else DOWN
    shown = bool(b.always_shown) or state in SHOWN_STATES
    return BotStatus(name, state, pids, _stop_since(name) if stop else None, shown)


def is_active(name, rows, ok):
    """Shown on the phone? The pin bot always; any other bot when its stop file is absent and a live copy of it is in the
    process table `rows`. A table that could not be read (ok False) hides nothing but a stop-filed bot: never hidden on a
    failed read.  (botstats.is_active, v-tg-active)"""
    if name in ALWAYS_SHOWN:
        return True
    if stop_set(name):
        return False
    if not ok or rows is None:
        return True
    return any(is_bot(name, r[2]) for r in rows)


def active_from(rows, ok):
    """The active bots, in BOTS order, from a process table already read (botstats' [pid, started, cmdline] rows)."""
    return tuple(b for b in _reg.names() if is_active(b, rows, ok))


# ---- the fleet -------------------------------------------------------------------------------------------------------
def fleet_from(rows, ok, now=None):
    """Fleet from a table already read."""
    st = tuple(status_of(b, rows, ok) for b in _reg.names())
    return Fleet(t=time.time() if now is None else float(now), procs_ok=bool(ok and rows is not None), bots=st,
                 active=tuple(s.name for s in st if s.state == ACTIVE), shown=tuple(s.name for s in st if s.shown),
                 hidden=tuple(s.name for s in st if not s.shown), by_name={s.name: s for s in st})


def _cached_table(t):
    """botstats' cached process table (botstats_cache.json 'procs'), when under PROC_STALE_S old, else None."""
    from botdata import kalshi as _kalshi                       # (lazy: status is imported by modules kalshi needs)
    p = _kalshi.load_cache().get("procs") or {}
    if p.get("rows") is not None and 0.0 <= t - float(p.get("t") or 0) < _procs.PROC_STALE_S:
        return p["rows"]
    return None


def _read_rows(procs, t):
    """(rows or None) as active_bots always read them: a callable's answer, else the native read (milliseconds; when it
    fails, the cached table if under PROC_STALE_S old -- never the 30 s WMI read inside a command)."""
    if callable(procs):
        return procs()
    try:
        rows = _procs._procs_native()
    except Exception:                                           # noqa: BLE001
        rows = None
    if rows is None:
        rows = _cached_table(t)
    return rows


def _fail_safe(now):
    """Every non-retired bot without a stop file shown, UNKNOWN (the pin bot always)."""
    st = []
    for b in _reg.all_bots():
        stop = stop_set(b.name)
        state = RETIRED if b.retired else (STOPPED if stop else UNKNOWN)
        st.append(BotStatus(b.name, state, (), None, bool(b.always_shown) or state == UNKNOWN))
    st = tuple(st)
    return Fleet(t=time.time() if now is None else float(now), procs_ok=False, bots=st, active=(),
                 shown=tuple(s.name for s in st if s.shown), hidden=tuple(s.name for s in st if not s.shown),
                 by_name={s.name: s for s in st})


def fleet(procs=None, now=None):
    """Every bot's status. `procs` as botstats.procs_for takes it -- a table the caller holds, a callable, or None to
    read Windows here. Memoised FLEET_TTL_S when Windows is read here. Never raises."""
    try:
        if procs is not None and not callable(procs):
            return fleet_from(_procs._norm_procs(procs), True, now)
        t = time.time() if now is None else float(now)
        if callable(procs) or _FLEET["v"] is None or not (0.0 <= t - _FLEET["t"] < FLEET_TTL_S):
            rows = _read_rows(procs, t)
            v = fleet_from(None if rows is None else _procs._norm_procs(rows), rows is not None, t)
            if callable(procs):
                return v
            _FLEET.update(t=t, v=v)
        return _FLEET["v"]
    except Exception:                                           # noqa: BLE001
        return _fail_safe(now)


def active_bots(procs=None, now=None):
    """The active bots (BOTS order) for a page that does not read all_bots: `procs` as procs_for takes it -- a table the
    caller holds, a callable, or None to read Windows here (the native read, milliseconds; when it fails, the cached
    table if under PROC_STALE_S old, never the 30 s WMI read inside a command). Memoised ACTIVE_TTL_S. Never raises: on
    any error every bot without a stop file is shown.  (botstats.active_bots)"""
    try:
        if procs is not None and not callable(procs):
            return active_from(_procs._norm_procs(procs), True)
        t = time.time() if now is None else float(now)
        if callable(procs) or _ACTIVE["v"] is None or not (0.0 <= t - _ACTIVE["t"] < ACTIVE_TTL_S):
            rows = _read_rows(procs, t)
            v = active_from(None if rows is None else _procs._norm_procs(rows), rows is not None)
            if callable(procs):
                return v
            _ACTIVE.update(t=t, v=v)
        return _ACTIVE["v"]
    except Exception:                                            # noqa: BLE001
        return tuple(b for b in _reg.names() if not stop_set(b) or b in ALWAYS_SHOWN)


# ---- shown lists (v-tg-active) ---------------------------------------------------------------------------------------
def shown_parts(a):
    """[(key, money block)] for a per-bot list that must add up to all_bots' totals: each ACTIVE bot, then 'earlier'
    (every hidden bot's markets on one line) when it has a market or could not be read, then 'other'."""
    act = a.get("active") or _reg.names()
    out = [(b, a["bots"][b]["money"]) for b in act if b in a["bots"]]
    e = a.get("earlier")
    if e and (not e.get("ok") or (e.get("all_time") or {}).get("markets")):
        out.append((EARLIER, e))
    out.append(("other", a["other"]))
    return out


def shown_by(a, d, how="sum"):
    """A by-bot dict of all_bots (a window's by_bot, by_bot_markets, by_bot_put_in, by_bot_pot_pct, a day's by_bot) with
    the hidden bots folded into one 'earlier' entry: added up (how='sum'), or None (how='none', for a % of a pot, which
    has no meaning summed over pots). Order: active bots, 'earlier', then the rest ('other')."""
    act = set(a.get("active") or _reg.names())
    names = set(_reg.names())
    out, hid = {}, []
    for k, v in (d or {}).items():
        if k in names and k not in act:
            hid.append(v)
        elif k != "other":
            out[k] = v
    if hid:
        out[EARLIER] = None if how == "none" else round(sum(x or 0 for x in hid), 4)
    if "other" in (d or {}):
        out["other"] = d["other"]
    return out


def shown_name(a, name):
    """'earlier' for a hidden bot's name (a missing pot, an error line), the name itself otherwise."""
    return EARLIER if name in _reg.names() and name not in (a.get("active") or _reg.names()) else name


__all__ = ["ACTIVE", "STOPPING", "STOPPED", "DOWN", "UNKNOWN", "RETIRED", "SHOWN_STATES", "BotStatus", "Fleet",
           "fleet", "fleet_from", "status_of", "is_bot", "stop_set", "is_active", "active_from", "active_bots",
           "shown_parts", "shown_by", "shown_name", "EARLIER", "EARLIER_LABEL", "ALWAYS_SHOWN"]
