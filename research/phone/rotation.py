"""phone/rotation.py -- the server's log rotation on the phone (ops fixes, 2026-11-07): an alert when it turns bad, one
when it works again, and its line on /server.

WHY. research/log_rotate.py (the scheduled task KalsLogRotate, daily 09:40 UTC) packs finished logs so the server's disk
lasts (26.3 GB free on 11-07, ~1.46 GB a week: full around March 2027 without it). The 11-07 review found it could
fail SILENTLY: its results went only to results\\log_rotate.log, which nobody reads from a phone, and a run that could
not ask git what it tracks moves nothing at all -- the disk would fill anyway with no one told. So the monitor
(phone/monitor.py CHECKS) reads log_rotate.health() every CHECK_EVERY_S and says, ONCE, when it enters a bad state:

  never   installed over 36 h ago and no run has finished       stuck   a run started over 3 h ago never finished
  stale   no finished run for 36 h                             failed  the last run hit an error
  nogit   the last run could not ask git, so it moved nothing   short   the disk within 8 weeks of the 6 GB line

then once when a run is ok again. Not installed (no results\\log_rotate_installed.json, no status file): nothing, ever.
Not urgent (quiet hours hold it: phone/alerts.sender). /server shows one line (server_lines) when it is installed.
Every alert says what it means for the disk in GB and weeks; nothing here touches a file, only reads two small ones.
"""
import calendar
import time

from botdata import paths as _paths
from phone.html import Html, esc
from pindesk import et_day, et_str

CHECK_EVERY_S = 300                     # the two small files are read at most this often
RUN_AT_UTC = (9, 40)                    # the task's daily start (results\log_rotate_install.ps1)


def health(now, results=None):
    """log_rotate.health() on the CURRENT results folder (botdata.paths: a test's temp folder in tests). Never raises:
    a failure is state 'none' with its words in 'err' (the page and the alerts then say nothing)."""
    try:
        import log_rotate
        return log_rotate.health(results or _paths.RESULTS, now)
    except Exception as e:                                      # noqa: BLE001
        return {"state": "none", "bad": False, "err": "%s: %s" % (type(e).__name__, str(e)[:120])}


def when(t, now):
    """'4:40 AM' today (ET), 'Nov 6 4:40 AM' another day; '?' unknown (monitor.when_words' words)."""
    if t is None:
        return "?"
    t = float(t)
    return et_str(t) if et_day(t) == et_day(now) else "%s %s" % (et_str(t, "%b %d").replace(" 0", " "), et_str(t))


def span(s):
    s = max(0, int(s))
    if s < 3600:
        return "%d min" % max(1, s // 60)
    if s < 2 * 86400:
        return "%d h %02d min" % (s // 3600, (s % 3600) // 60)
    return "%d days %d h" % (s // 86400, (s % 86400) // 3600)


def next_run(now):
    """The task's next daily start (epoch)."""
    g = time.gmtime(now)
    t = calendar.timegm((g.tm_year, g.tm_mon, g.tm_mday, RUN_AT_UTC[0], RUN_AT_UTC[1], 0))
    return t if t > now else t + 86400


def disk_words(h):
    """'25.7 GB free, filling about 1.46 GB a week: about 13 weeks to the 6 GB line' or ''."""
    if h.get("free_gb") is None:
        return ""
    s = "%.1f GB free" % float(h["free_gb"])
    if h.get("gb_week") is not None and float(h["gb_week"]) > 0 and h.get("weeks_to_guard") is not None:
        s += ", filling about %.2f GB a week: about %.0f weeks to the 6 GB line" % (float(h["gb_week"]),
                                                                                  float(h["weeks_to_guard"]))
    return s


def _first_error(h):
    e = (h.get("errors") or ["?"])[0]
    return e if len(e) <= 160 else e[:157] + "..."


def alert_text(h, now):
    """The alert for a BAD state (log_rotate.BAD)."""
    s = h.get("state")
    disk = disk_words(h)
    tail = (" Disk: %s." % esc(disk)) if disk else ""
    if s == "never":
        body = ("⚠️ <b>Log rotation has never run</b>: it was installed %s ET (%s ago) and no run has finished since. "
                "Old logs are not being packed, so the disk keeps filling at the old rate (about 1.46 GB a week). "
                "Nothing is lost; the scheduled task KalsLogRotate needs a look on the server."
                % (esc(when(h.get("installed_t"), now)), esc(span(now - float(h.get("installed_t") or now)))))
    elif s == "stuck":
        body = ("⚠️ <b>Log rotation got stuck</b>: a run started %s ET (%s ago) and never finished; it may have died "
                "part way. Nothing is lost: a log is deleted only after its packed copy reads back the same. The next "
                "daily run (%s ET) tries again." % (esc(when(h.get("started_t"), now)),
                                                    esc(span(now - float(h.get("started_t") or now))),
                                                    esc(when(next_run(now), now))))
    elif s == "stale":
        body = ("⚠️ <b>Log rotation has not run for %s</b> (its last finished run: %s ET). Until it runs again the "
                "disk fills at the old rate. Nothing is lost; the scheduled task KalsLogRotate needs a look on the "
                "server." % (esc(span(now - float(h["last_t"]))) if h.get("last_t") else "a long time",
                             esc(when(h.get("last_t"), now))))
    elif s == "failed":
        body = ("⚠️ <b>Log rotation hit an error</b> on its %s ET run: %s. The logs it could not pack stay where they "
                "were (a log is deleted only after its packed copy reads back the same); it moved %s file(s) before "
                "that." % (esc(when(h.get("last_t"), now)), esc(_first_error(h)), esc(h.get("moved") or 0)))
    elif s == "nogit":
        body = ("⚠️ <b>Log rotation moved nothing</b> on its %s ET run: it could not ask git which logs git keeps, and "
                "it never touches a log without knowing. Until git answers, the disk fills at the old rate (about "
                "1.46 GB a week). Nothing is lost; git on the server needs a look." % esc(when(h.get("last_t"), now)))
    elif s == "short":
        body = ("⚠️ <b>Disk: about %.0f weeks left to the 6 GB line</b> (measured by the daily log rotation). Under 6 GB "
                "every analysis stops; at 5 GB the recorders stop for good. It needs more room or less logging soon."
                % float(h.get("weeks_to_guard") or 0))
    else:
        body = "⚠️ <b>Log rotation: %s</b>" % esc(s)
    return Html(body + tail)


def back_text(h, now):
    return Html("✅ <b>Log rotation is working again</b>: its %s ET run moved %s file(s) and freed %s MB.%s" % (
        esc(when(h.get("last_t"), now)), esc(h.get("moved") or 0), esc("{:,.0f}".format(float(h.get("freed_mb") or 0))),
        (" Disk: %s." % esc(disk_words(h))) if disk_words(h) else ""))


def plain(h):
    return "Log rotation: %s (results\\log_rotate.log on the server says more)." % h.get("state")


def check(ctx, m, send, now, fmt=None):
    """The monitor's rotation check (state on the MonitorState: rot_t, rot_bad). `fmt(build, plain)` lays an alert
    out or falls back to its plain words (monitor.fmt)."""
    if m.rot_t is not None and now - m.rot_t < CHECK_EVERY_S:
        return
    m.rot_t = now
    h = health(now)
    s = h.get("state")
    fmt = fmt or (lambda build, plain_: build())
    if s == "none":
        m.rot_bad = None
    elif h.get("bad"):
        if s != m.rot_bad:
            m.rot_bad = s
            send(fmt(lambda: alert_text(h, now), lambda: plain(h)))
    elif s == "ok" and m.rot_bad is not None:
        m.rot_bad = None
        send(fmt(lambda: back_text(h, now), lambda: plain(h)))


def server_lines(h, now):
    """/server's section: [] when not installed; else a headline and the disk line."""
    s = (h or {}).get("state", "none")
    if s == "none":
        return []
    if s == "waiting":
        head = "🗜 <b>Log rotation</b>: installed %s ET; its first run is %s ET (then daily)" % (
            esc(when(h.get("installed_t"), now)), esc(when(next_run(now), now)))
    elif s == "running":
        head = "🗜 <b>Log rotation</b>: running now (started %s ET)" % esc(when(h.get("started_t"), now))
    elif h.get("bad"):
        first = str(alert_text(h, now)).split("</b>")[0].replace("⚠️ <b>", "")
        head = "⚠️ <b>%s</b> · the alert said why; results\\log_rotate.log on the server has every line" % first
    else:
        head = ("🗜 <b>Log rotation</b>: last run %s ET (%s ago): moved %s file(s), %s MB packed to %s MB, freed %s MB"
                % (esc(when(h.get("last_t"), now)), esc(span(now - float(h.get("last_t") or now))),
                   esc(h.get("moved") or 0), esc("{:,.0f}".format(float(h.get("raw_mb") or 0))),
                   esc("{:,.0f}".format(float(h.get("gz_mb") or 0))),
                   esc("{:,.0f}".format(float(h.get("freed_mb") or 0)))))
    out = [head]
    if disk_words(h):
        how = str(h.get("rate_from") or "")
        how = how if how.startswith("measured") else "the 11-07 estimate until 3 days of runs measure it"
        out.append("<i>Disk: %s (%s).</i>" % (esc(disk_words(h)), esc(how)))
    return out
