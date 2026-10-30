"""/quiet -- quiet hours: when only urgent alerts come (v-tg-rebuild step 12, lane Q, 2026-10-30).

  /quiet          the setting, whether it is quiet now, and what is held
  /quiet 23-7     quiet from 11 PM to 7 AM ET (two hours of the 24-hour clock, ET)
  /quiet off      every alert comes at any hour
  /quiet on       back to the default, 11 PM to 7 AM ET

Stored in the phone's config file next to the pairing (telegram.json "quiet_hours"; never the repo). phone/quiet.py has
the rule; phone/alerts.py holds what is not urgent and sends it as one summary when quiet hours end.
"""
from phone import quiet as _quiet
from phone.command import Command, declare
from phone.commands.pair import save_cfg
from phone.html import Html, esc, i_

URGENT_WORDS = ("a bot DOWN (and back up), a stop tripped, a single loss over $50 or 3% of its pot, a balance "
                "mismatch, and the pin bot's state changes")


def _held(ctx):
    m = getattr(ctx.state, "monitor", None)
    return len(getattr(m, "held", None) or [])


def page(ctx, head):
    cfg = ctx.cfg
    h = _quiet.hours(cfg)
    lines = [head]
    if h is None:
        lines.append("Every alert comes at any hour.")
    else:
        now = ctx.now()
        quiet = _quiet.is_quiet(cfg, now)
        lines.append("From %s to %s ET only urgent alerts come: %s. The rest wait and come as ONE summary at %s." % (
            esc(_quiet.hour_words(h[0])), esc(_quiet.hour_words(h[1])), esc(URGENT_WORDS),
            esc(_quiet.hour_words(h[1]))))
        lines.append("Now: <b>%s</b>%s." % ("quiet" if quiet else "not quiet", (" · %d alert%s held" % (
            _held(ctx), "" if _held(ctx) == 1 else "s")) if _held(ctx) else ""))
    if getattr(ctx.state, "muted", False):
        lines.append("<b>Alerts are muted</b> (/unmute): nothing comes, urgent or not.")
    lines.append(i_("/quiet 23-7 sets the hours (ET, 24-hour clock) · /quiet off · /quiet on (back to 11 PM - 7 AM)"))
    return Html("\n".join(lines))


def handle(ctx):
    what = _quiet.parse(ctx.arg)
    cfg = ctx.cfg
    if what[0] == "show":
        return page(ctx, "🌙 <b>Quiet hours: %s</b>" % esc(_quiet.words(cfg)))
    if what[0] == "bad":
        return Html("🌙 I did not change the quiet hours: %s." % esc(what[1]))
    if what[0] == "off":
        cfg[_quiet.KEY] = _quiet.OFF
    elif what[0] == "on":
        cfg[_quiet.KEY] = list(_quiet.DEFAULT)
    else:
        cfg[_quiet.KEY] = list(what[1])
    save_cfg(cfg, ctx.cfg_path)
    return page(ctx, "🌙 <b>Quiet hours %s</b>" % ("off" if what[0] == "off" else "now %s" % esc(_quiet.words(cfg))))


COMMAND = declare(Command(
    names=("/quiet",), section="controls", order=45,
    help_line="/quiet — quiet hours: only urgent alerts overnight (<code>/quiet 23-7</code>, <code>/quiet off</code>)",
    chart=None, handle=handle, needs_ledger=False, examples=("/quiet 22-6", "/quiet off", "/quiet on", "/quiet 25-7")))
