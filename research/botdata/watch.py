"""watch.py -- what the phone's monitor reads about each bot, through the registry's hooks (v-tg-rebuild step 12, lane Q,
2026-10-30). DATA only: no words, never imports the phone.

  watch_in(now)         the WatchIn a hook gets: RESULTS, the clock, the ET day, and the log readers (botdata.logs)
  gauges(name, now)     Bot.stop_gauges: where each of its stops stands now (the early warnings)
  gauge_level(g)        how many of a Gauge's warning levels it is through (len(warn_at) + 1 = tripped)

A hook that raises costs only that bot's check (the caller logs it); a bot without the hook has nothing to say.
"""
import bots as _bots
from botdata import clock as _clock
from botdata import logs as _logs
from botdata import paths as _paths
from bots.spec import WatchIn


def watch_in(now):
    """The readers a monitor hook gets, at clock `now`."""
    now = float(now)
    return WatchIn(results=_paths.RESULTS, now=now, today=_clock.et_day(now), last_record=_logs.last_record,
                   read_since=_logs.read_since, epoch=_clock.utc_epoch, et_day=_clock.et_day)


def gauges(name, now, wi=None):
    """[Gauge] of bot `name` now ([] when it has no stop_gauges hook)."""
    b = _bots.get(name)
    hook = getattr(b, "stop_gauges", None) if b is not None else None
    if hook is None:
        return []
    return list(hook(wi or watch_in(now)) or [])


def gauge_level(g):
    """0 = above every warning level; k = through the first k of g.warn_at; len(warn_at) + 1 = tripped (money at or
    under the line, or its own record says so)."""
    if g.tripped or g.money <= g.line + 1e-9:
        return len(g.warn_at) + 1
    return sum(1 for lv in g.warn_at if g.money <= lv + 1e-9)


__all__ = ["watch_in", "gauges", "gauge_level"]
