"""phone/monitor.py -- the watch the operator asked for on 10-30 ("yes to every feature you suggested"), run by the alerts
tick (phone/alerts.py) on every poll cycle once the runtime turns it on (Phone.monitor_on: phone/app.py main() does; the
self-tests and the golden harness turn it on only where they test it):

  DOWN       a registry bot that is not running and has NO stop file (botdata/status.py's DOWN: it stopped on its own).
             One alert when it ENTERS DOWN -- after a debounce, so a normal restart never alerts: it must be DOWN on more
             than DOWN_CHECKS checks AND for DOWN_ALERT_S (3 min; telegram.json "down_alert_s" changes it) -- and one when
             it is back up (or paused instead). The jump band has NO keep-alive: this is its only safety net.
             /status and /bots print one warning line per DOWN bot at the top (down_lines), with no debounce: a page
             says what is true now.
  STOPS      early warnings before a stop trips (each bot's own records, through the registry's Bot.stop_gauges hook:
             botdata/watch.py): the pin bot at 60% and 80% of its loss abort, the jump band $10 and $5 from its -$25
             stop line and $5 from its -$15 day stop, the FX taker near its stop line and its day stop, the ladder at 60%
             and 80% of its day-stop rail. Once per level per run / day (Gauge.period), and once more (URGENT) when the
             stop trips. Read every GAUGE_EVERY_S; the first read after a (re)start learns and says nothing.

Every alert leads with what happened and what it means in $; every one goes through `send(msg, urgent)` (alerts.py:
muted -> nothing; quiet hours hold what is not urgent). Each check is inside its own try: one failing never costs the
others or the old alerts. The state lives on the alert state (st.monitor: MonitorState), so a phone restart forgets it
(a bot still DOWN then is alerted again after the debounce).
"""
import time
import traceback
from dataclasses import dataclass, field

import bots as _bots
from botdata import status as _status
from botdata import watch as _watch
from botdata.fmt import usd
from phone.html import Html, esc
from phone.log import log
from pindesk import et_day, et_str, pct

# ---- DOWN: the debounce (operator 10-30: "alert only after it has been DOWN for > 2 checks / ~3 min, configurable") ----
DOWN_CHECKS = 2                         # it must be seen DOWN on MORE than this many checks ...
DOWN_ALERT_S = 180                      # ... and for at least this long (telegram.json "down_alert_s" overrides)
GAUGE_EVERY_S = 60                      # the stops are read at most this often (the first tick always)


@dataclass
class MonitorState:
    """What the monitor remembers between ticks (on the alert state: st.monitor)."""
    down: dict = field(default_factory=dict)        # bot -> {"since", "checks", "sent", "log"} while it is DOWN
    gauge: dict = field(default_factory=dict)       # (bot, gauge key, period) -> the level already told
    gauge_t: float = None                           # when the stops were last read
    gauge_learnt: bool = False                      # the first read (learns, says nothing) is done


def state_of(st):
    """The MonitorState on alert state `st` (made on first use)."""
    m = getattr(st, "monitor", None)
    if not isinstance(m, MonitorState):
        m = MonitorState()
        st.monitor = m
    return m


# ---- words -------------------------------------------------------------------------------------------------------------
def when_words(t, now):
    """'10:42 AM' today (ET), 'Oct 29 10:42 PM' on another day; '?' when unknown."""
    if t is None:
        return "?"
    if et_day(t) == et_day(now):
        return et_str(t)
    return "%s %s" % (et_str(t, "%b %d").replace(" 0", " "), et_str(t))


def span_words(s):
    """3 min, 1 h 05 min, 2 days 3 h."""
    s = max(0, int(s))
    if s < 3600:
        return "%d min" % max(1, s // 60)
    if s < 2 * 86400:
        return "%d h %02d min" % (s // 3600, (s % 3600) // 60)
    return "%d days %d h" % (s // 86400, (s % 86400) // 3600)


def label(name):
    b = _bots.get(name)
    return b.label if b is not None else str(name)


def pot_value(ctx, name):
    """The bot's pot(s) now as botstats' cache last read them (cash + open bets; no Kalshi read), or None."""
    try:
        p = (ctx.pots() or {}).get("pots") or {}
        vals = [(p.get(s) or {}).get("value") for s in _bots.bot_subs(name)]
        return round(sum(vals), 2) if vals and all(v is not None for v in vals) else None
    except Exception:                                           # noqa: BLE001
        return None


def _fleet(ctx):
    return _status.fleet(procs=ctx.bs_procs, now=ctx.now())


# ---- the warning line on /status and /bots ------------------------------------------------------------------------------
def down_line(name, now):
    t = _status.last_log_t(name)
    return "⚠️ <b>%s is not running and was not paused</b> (%s)" % (
        esc(label(name)), ("last log %s" % esc(when_words(t, now))) if t is not None else "no log yet")


def down_lines(ctx):
    """One warning line per DOWN bot, then a blank line ([] when none, or when it cannot be read). Never raises."""
    try:
        now = ctx.now()
        out = [down_line(n, now) for n in _status.down(_fleet(ctx))]
        return out + [""] if out else []
    except Exception:                                           # noqa: BLE001
        log("down_lines failed:\n%s" % traceback.format_exc())
        return []


# ---- the DOWN alerts -----------------------------------------------------------------------------------------------------
def down_alert_text(name, e, now, pot):
    b = _bots.get(name)
    ka = getattr(b, "keepalive", None)
    lines = ["🚨 <b>%s is DOWN</b>: not running, and it was not paused (no stop file) -- it stopped by itself." % esc(
        label(name)),
             "<b>No new bets: it makes $0 until it runs again</b>%s; a bet already open still settles by itself." % (
                 (" (its pot %s sits idle)" % esc(usd(pot).lstrip("+"))) if pot is not None else ""),
             "Seen down for %s; its log last moved %s ET." % (esc(span_words(now - e["since"])),
                                                            esc(when_words(e.get("log"), now)))]
    if ka:
        lines.append("<i>Its keep-alive: %s. Still down after that -> look at the server.</i>" % esc(ka))
    else:
        lines.append("<i>Nothing restarts it by itself (no keep-alive): it must be started again by hand.</i>")
    return Html("\n".join(lines))


def back_text(name, e, now, state):
    if state == _status.STOPPED:
        return Html("⏸ <b>%s was down and is paused now</b> (its stop file is set): no more alerts about it until it "
                    "runs again." % esc(label(name)))
    return Html("✅ <b>%s is back up</b> -- running again after about %s down (from %s to %s ET)." % (
        esc(label(name)), esc(span_words(now - e["since"])), esc(when_words(e["since"], now)),
        esc(when_words(now, now))))


def down_after_s(ctx):
    try:
        v = (ctx.cfg or {}).get("down_alert_s")
        return float(v) if v is not None else DOWN_ALERT_S
    except (TypeError, ValueError, AttributeError):
        return DOWN_ALERT_S


def check_down(ctx, m, send, now):
    """One DOWN check: count each DOWN bot's checks; alert once its debounce passes; say when it is back."""
    f = _fleet(ctx)
    if not f.procs_ok:
        return                                          # the table could not be read: nothing learnt, nothing said
    wait = down_after_s(ctx)
    for s in f.bots:
        name, e = s.name, m.down.get(s.name)
        if s.state == _status.DOWN:
            if e is None:
                e = m.down[name] = {"since": now, "checks": 0, "sent": False, "log": _status.last_log_t(name)}
            e["checks"] += 1
            if not e["sent"] and e["checks"] > DOWN_CHECKS and now - e["since"] >= wait:
                e["sent"] = True
                e["log"] = _status.last_log_t(name)
                send(fmt(lambda: down_alert_text(name, e, now, pot_value(ctx, name)),
                         lambda: "%s is DOWN: not running and not paused (no stop file)." % label(name)), urgent=True)
        elif e is not None:
            del m.down[name]
            if e["sent"]:
                st_ = s.state
                send(fmt(lambda: back_text(name, e, now, st_),
                         lambda: "%s is back (%s)." % (label(name), st_)), urgent=True)


# ---- the stops: early warnings, then the trip --------------------------------------------------------------------------
def _cap(x):
    return x[:1].upper() + x[1:]


def gauge_text(name, g, level, pot):
    """A warning (level 1..len(warn_at)) or the trip (len(warn_at) + 1) of Gauge g, in the operator's words."""
    n = len(g.warn_at)
    of = (" · <b>%s</b> of its pot" % esc(pct(g.money / pot))) if pot else ""
    if level > n:
        return Html("🛑 <b>%s hit %s (%s)</b>: %s %s%s.\n%s." % (
            esc(label(name)), esc(g.what), esc(usd(g.line)), esc(usd(g.money)), esc(g.counted), of, esc(_cap(g.trips))))
    lines = ["⚠️ <b>%s %s %s: %s from %s (%s)</b>%s" % (
        esc(label(name)), esc(usd(g.money)), esc(g.counted), esc(usd(g.money - g.line).lstrip("+")), esc(g.what),
        esc(usd(g.line)), of)]
    way = ("%d%% of the way there. " % round(100.0 * g.money / g.line)) if g.line < 0 and g.money < 0 else ""
    lines.append("%sAt %s %s. %s" % (way, esc(usd(g.line)), esc(g.trips), (
        "Next warning at %s." % esc(usd(g.warn_at[level]))) if level < n else "Next: the stop itself."))
    return Html("\n".join(lines))


def check_gauges(ctx, m, send, now):
    """Read every running bot's stops (at most every GAUGE_EVERY_S); warn once per level per period; the trip is
    urgent. The first read learns the levels already reached and says nothing."""
    if m.gauge_t is not None and 0.0 <= now - m.gauge_t < GAUGE_EVERY_S:
        return
    m.gauge_t = now
    f = _fleet(ctx)
    wi = _watch.watch_in(now)
    for s in f.bots:
        if s.state not in (_status.ACTIVE, _status.UNKNOWN):
            continue
        try:
            gs = _watch.gauges(s.name, now, wi)
        except Exception:                                       # noqa: BLE001
            log("stop gauges of %s failed:\n%s" % (s.name, traceback.format_exc()))
            continue
        for g in gs:
            key = (s.name, g.key, g.period)
            lv, told = _watch.gauge_level(g), m.gauge.get(key, 0)
            if lv <= told:
                continue
            m.gauge[key] = lv
            if not m.gauge_learnt:
                continue
            name = s.name
            send(fmt(lambda: gauge_text(name, g, lv, pot_value(ctx, name)),
                     lambda: "%s %s %s, %s %s" % (label(name), usd(g.money), g.counted, g.what, usd(g.line))),
                 urgent=lv > len(g.warn_at))
    m.gauge_learnt = True


# ---- the tick ------------------------------------------------------------------------------------------------------------
def fmt(build, plain):
    """An alert laid out, or its plain words if the layout fails (alerts.fmt_or_plain's rule)."""
    try:
        return build()
    except Exception:                                           # noqa: BLE001
        log("monitor layout failed, sending the plain words: %s" % traceback.format_exc()[-400:])
        return plain()


CHECKS = (("down", check_down), ("stops", check_gauges))


def tick(ctx, st, send, now=None):
    """Every check once (each in its own try). `send(msg, urgent=False)` is alerts.py's (muted / quiet hours)."""
    m = state_of(st)
    now = ctx.now() if now is None else now
    for name, fn in CHECKS:
        try:
            fn(ctx, m, send, now)
        except Exception:                                       # noqa: BLE001
            log("monitor check %s failed:\n%s" % (name, traceback.format_exc()))
