"""/watch -- the Kalshi watch: when it last scanned, each check's last status, what is open now, the newest entries of
Kalshi's API changelog and the last alerts it sent. /watch off and /watch on: its off switch.

v-kwatch (2026-11-07; the operator: "add some feedback and alarms where we have something that runs a scan to catch any
kalshi changes"). research/kalshi_watch.py (the server's scheduled task KalsKalshiWatch, every 30 minutes) writes
results/kalshi_watch_state.json; the page only reads that file. Nothing here reads Kalshi or the network.

  /watch           the page (read only)
  /watch off       asks: 'Turn the Kalshi watch off? ... Reply /watch off yes' (5 minutes)
  /watch off yes   writes results\\kalshi_watch.stop (phone/actions/stopfiles.py: the phone's only stop-file writer):
                   every scheduled scan exits at once, scans nothing, sends nothing (the page says OFF); nothing else
                   changes
  /watch on        removes it (no question: it only turns the alarms back on); the next scan says, once, what changed
                   while it was off
Each action is one line in results\\phone_actions.jsonl (phone/actions/journal.py). Only the paired chat reaches here.
"""
import traceback

from botdata import clock as _clock
from botdata import paths as _paths
from phone.actions import confirm as _confirm
from phone.actions import journal as _journal
from phone.actions import stopfiles as _stop
from phone.command import Command, declare
from phone.html import MAX_LEN, Html, esc, i_
from phone.log import log

STATE = "kalshi_watch_state.json"
STOP = _stop.WATCH                              # research/kalshi_watch.py STOP_NAME: every run exits while it is there
EVERY_MIN = 30
LATE_MIN = 70                                   # past two missed scans: the page says LATE
ASK_TTL_S = 300                                 # /watch off's question stands 5 minutes
HEAD = "👁 <b>Kalshi watch</b> (a scan every %d minutes for anything Kalshi, the index or the server changed)" % EVERY_MIN
NOT_YET = ("👁 <b>Kalshi watch</b>: it has not scanned yet (results\\kalshi_watch_state.json is not there). Once the "
           "server task KalsKalshiWatch is installed (results\\kalshi_watch_install.ps1) it scans every %d minutes, "
           "and its first scan sends a 'baseline set' note." % EVERY_MIN)
FOOT = ("Urgent alerts ring even in quiet hours; the rest come silently then. /watch off stops it (asks first), /watch "
        "on starts it again. This page reads results\\kalshi_watch_state.json.")
OFF_ASK = ("⏸ <b>Turn the Kalshi watch off?</b> Its scans every %d minutes stop: no Kalshi change, no warning from pin's "
           "log and no disk alarm reaches the phone until <code>/watch on</code>. Pin and every bot keep trading as "
           "before.\nReply <code>/watch off yes</code> within %d minutes." % (EVERY_MIN, ASK_TTL_S // 60))
USAGE = ("👁 <code>/watch</code> shows the Kalshi watch. <code>/watch off</code> stops it (asks first); "
         "<code>/watch on</code> starts it again.")


def _off_since():
    """When /watch off was sent (epoch), or None when the watch is on."""
    return _stop.watch_since()


def load(ctx):
    """{"state": the scanner's state file (None when missing or unreadable), "now": ctx.now(), "off": when /watch off
    was sent (None: on)}."""
    return {"state": _paths.read_json(_paths.results(STATE)), "now": ctx.now(), "off": _off_since()}


def _ago(t, now):
    m = max(0, int(round((now - t) / 60.0)))
    if m < 120:
        return "%d minute%s ago" % (m, "" if m == 1 else "s")
    h = m // 60
    if h < 48:
        return "%d hours ago" % h
    return "%d days ago" % (h // 24)


def _et(iso_t):
    e = _clock.utc_epoch(iso_t) if iso_t else None
    return _clock.et_clock(e) if e is not None else "?"


def _date_words(d):
    if d == "TBD":
        return "day not set (TBD)"
    try:
        y, m, dd = (int(x) for x in str(d).split("-"))
        return "%s, %d" % (_clock.day_label(d), y) if 1 <= m <= 12 and 1 <= dd <= 31 else str(d)
    except ValueError:
        return str(d)


def _cut(s, n):
    s = str(s or "")
    return s if n is None or len(s) <= n else s[:max(1, n - 1)].rstrip() + "…"


def _check_line(c, cut):
    label = c.get("label") or "?"
    st = c.get("status")
    if st == "failed":
        streak = int(c.get("fail_streak") or 0)
        line = "🔴 %s: <b>FAILED %d scan%s in a row</b>: %s" % (esc(label), streak, "" if streak == 1 else "s",
                                                              esc(_cut(c.get("detail"), cut)))
        if c.get("last_ok"):
            line += " (last good read %s)" % esc(_et(c["last_ok"]))
        return line
    if st == "ok":
        return "🟢 %s: %s" % (esc(label), esc(_cut(c.get("detail") or "ok", cut)))
    return "⚪ %s: not run yet" % esc(label)


def _off_line(off):
    return ("⏸ <b>OFF since %s</b> (/watch off): no scans, no alerts. <code>/watch on</code> starts it again; nothing "
            "below is new." % esc(_clock.et_clock(off)))


# how the page shrinks to one message: (alerts sent shown, changelog entries, open heads cut, check details cut, open
# conditions listed; None = all)
PLAN = ((5, 5, None, None, None), (5, 5, 140, 160, None), (3, 5, 110, 120, None), (3, 3, 90, 90, 30),
        (0, 3, 70, 70, 20), (0, 0, 60, 60, 12))


def render(d, ctx=None):
    st, now, off = d.get("state"), float(d["now"]), d.get("off")
    if not isinstance(st, dict) or not st.get("last_scan"):
        return Html(NOT_YET + ("\n" + _off_line(off) if off else ""))
    last = _clock.utc_epoch(st.get("last_scan"))
    checks = st.get("checks") if isinstance(st.get("checks"), dict) else {}
    opens = st.get("open") if isinstance(st.get("open"), dict) else {}
    hist = [h for h in (st.get("history") or []) if isinstance(h, dict)]
    recent = [e for e in (st.get("changelog_recent") or []) if isinstance(e, dict)]
    waiting = len(st.get("outbox") or [])
    msg = ""
    for n_hist, n_cl, cut_open, cut_check, n_open in PLAN:
        out = [HEAD]
        line = "Last scan: %s (%s) · %d scan%s so far" % (
            esc(_clock.et_clock(last)) if last else "?", esc(_ago(last, now)) if last else "?",
            int(st.get("runs") or 0), "" if int(st.get("runs") or 0) == 1 else "s")
        if st.get("api_calls_last_scan") is not None:
            line += " · %s signed Kalshi reads in the last one" % esc(st["api_calls_last_scan"])
        out.append(line)
        if off:
            out.append(_off_line(off))
        elif last and now - last > LATE_MIN * 60:
            out.append("⚠️ <b>LATE: no scan for %s</b>: it should run every %d minutes (the server's scheduled task "
                       "KalsKalshiWatch). Until it runs again nothing here is new." % (
                           esc(_ago(last, now).replace(" ago", "")), EVERY_MIN))
        out += ["", "<b>Checks</b>"]
        for c in sorted((c for c in checks.values() if isinstance(c, dict)), key=lambda c: c.get("order", 99)):
            out.append(_check_line(c, cut_check))
        ol = sorted((o for o in opens.values() if isinstance(o, dict)),
                    key=lambda o: (not o.get("urgent"), o.get("since") or ""))
        out += ["", "<b>Open now (%d)</b>" % len(ol) if ol else "<b>Open now:</b> nothing"]
        for o in ol[:n_open]:
            out.append("%s %s · since %s%s" % (
                "🚨" if o.get("urgent") else "🔔", esc(_cut(o.get("head"), cut_open)), esc(_et(o.get("since"))),
                " <i>(keeps coming and going: only here until a day has passed)</i>" if o.get("quiet") else ""))
        if n_open is not None and len(ol) > n_open:
            out.append("and %d more (the urgent ones are listed first)" % (len(ol) - n_open))
        if n_cl and recent:
            out += ["", "<b>Kalshi's newest changelog entries</b>"]
            for e in recent[:n_cl]:
                hits = e.get("hits") or []
                out.append("• %s: %s%s" % (esc(_date_words(e.get("date"))), esc(_cut(e.get("title"), cut_open)),
                                           (" <i>(urgent: %s)</i>" % esc(", ".join(hits))) if hits else ""))
        if n_hist and hist:
            out += ["", "<b>Last alerts sent</b>"]
            for h in list(reversed(hist))[:n_hist]:
                out.append("• %s %s %s" % (esc(_et(h.get("t"))), "🚨" if h.get("urgent") else (
                    "✅" if h.get("kind") == "cleared" else "🔔"), esc(_cut(h.get("head"), cut_open))))
        if waiting:
            out += ["", "<b>%d alert%s waiting</b>: Telegram did not take %s yet; %s at the next scan." % (
                waiting, "" if waiting == 1 else "s", "it" if waiting == 1 else "them",
                "it goes" if waiting == 1 else "they go")]
        out += ["", i_(FOOT)]
        msg = "\n".join(out)
        if len(msg) <= MAX_LEN:
            break
    return Html(msg)


# ---- /watch off, /watch on --------------------------------------------------------------------------------------------
def watch_off(ctx, yes):
    chat, now = ctx.chat_id, ctx.now()
    off = _off_since()
    if off is not None:
        _confirm.drop(chat, "watch")
        return Html("⏸ <b>The Kalshi watch is already off</b> (since %s). <code>/watch on</code> starts it again."
                    % esc(_clock.et_clock(off)))
    if not yes:
        _confirm.ask(chat, "watch", "off", now, ASK_TTL_S)
        return Html(OFF_ASK)
    got, why = _confirm.take(chat, "watch", now, key="off")
    if got is None:
        return Html("%s Send <code>/watch off</code> first; nothing changed." % (
            "That question has expired." if why == "expired" else "Nothing is waiting for a yes."))
    try:
        p = _stop.watch_write("operator /watch off", now)
    except Exception as e:                                      # noqa: BLE001
        log(traceback.format_exc())
        _journal.record("watch_off", t=now, chat=chat, ok=False, error=str(e)[:200])
        return "Could not turn the Kalshi watch off: %s\nNothing changed." % str(e)[:200]
    _journal.record("watch_off", t=now, chat=chat, ok=True, stop_file=p)
    return Html("⏸ <b>Kalshi watch off</b> (%s): its next scans exit at once and send nothing. <code>/watch on</code> "
                "starts it again." % esc(_clock.et_clock(now)))


def watch_on(ctx):
    chat, now = ctx.chat_id, ctx.now()
    _confirm.drop(chat, "watch")
    if _off_since() is None:
        return Html("▶️ The Kalshi watch is on already (it is not switched off).")
    try:
        _stop.watch_remove()
    except Exception as e:                                      # noqa: BLE001
        log(traceback.format_exc())
        _journal.record("watch_on", t=now, chat=chat, ok=False, error=str(e)[:200])
        return "Could not turn the Kalshi watch on: %s\nNothing changed." % str(e)[:200]
    _journal.record("watch_on", t=now, chat=chat, ok=True)
    return Html("▶️ <b>Kalshi watch on again</b> (%s): its next scan, within %d minutes, compares with what it saw "
                "before and says once what changed meanwhile." % (esc(_clock.et_clock(now)), EVERY_MIN))


def handle(ctx):
    words = (ctx.arg or "").lower().split()
    if not words:
        return render(load(ctx), ctx)
    if words[0] == "off":
        return watch_off(ctx, len(words) > 1 and words[1] == "yes")
    if words[0] == "on":
        return watch_on(ctx)
    return Html(USAGE)


COMMAND = declare(Command(
    names=("/watch",), section="server", order=40,
    help_line="/watch: the Kalshi watch, a scan every 30 min for anything Kalshi, the index or the server changed: the "
              "last scan, each check, what is open now, Kalshi's newest changelog entries (/watch off, /watch on)",
    chart=None, handle=handle, needs_ledger=False, examples=("/watch help",),
    control=True,               # /watch off yes and /watch on change the watch: an old one is never run late (v-tg-stale)
    fail=lambda e: "Could not build /watch: %s" % str(e)[:200]))
