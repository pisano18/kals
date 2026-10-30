"""/alive -- the outside 'is it alive' check (v-tg-rebuild step 12, lane Q, 2026-10-30): its state and how to set it.

  /alive              on or off, the last ping and its answer, and how to set it up
  /alive set <url>    ping this URL every 5 min while the phone and the bots are healthy (saved in telegram.json)
  /alive off          stop pinging

phone/alive.py has the pinger; the URL is the operator's, made at a free monitoring service. Nothing here opens a URL.
"""
from phone import alive as _alive
from phone.command import Command, declare
from phone.commands.pair import save_cfg
from phone.html import Html, esc, i_

HOW = ("How: at a free monitoring service (healthchecks.io: New check, period 5 minutes, grace 10 minutes) copy the "
       "check's ping URL, then send <code>/alive set &lt;the URL&gt;</code>. Every 5 minutes, while the phone runs and no "
       "bot is DOWN, the phone GETs it; when the GETs stop -- the server off, the phone dead, a bot down -- the service "
       "emails or texts you.")


def _state(ctx):
    m = getattr(ctx.state, "monitor", None)
    return getattr(m, "alive", None)


def page(ctx, head):
    from phone.monitor import when_words
    url = _alive.url_of(ctx.cfg)
    lines = [head]
    if url is None:
        lines.append("The phone pings nothing now, so nobody outside would notice if the server stopped.")
        lines.append(HOW)
    else:
        now = ctx.now()
        lines.append("Pinging <code>%s</code> every %d minutes while the phone runs and no bot is DOWN." % (
            esc(_alive.masked(url)), _alive.EVERY_S // 60))
        a = _state(ctx)
        if not getattr(ctx.state, "monitor_on", False):
            lines.append("<b>The watch is off in this phone</b> (a test or preview): nothing is pinged.")
        elif a is None or a.last_t is None:
            lines.append("No ping yet%s." % ((": %s" % esc(a.skipped_why)) if a is not None and a.skipped_why else
                                              " (the first goes within %d minutes)" % (_alive.EVERY_S // 60)))
        else:
            lines.append("Last ping %s ET: %s · %d answered, %d failed since the phone started." % (
                esc(when_words(a.last_t, now)), esc(("answered %s" % a.last_status) if isinstance(a.last_status, int)
                                                    else str(a.last_status or "in flight")), a.ok, a.failed))
            if a.skipped_why:
                lines.append("<b>Not pinging now: %s</b> -- the service will notice the silence." % esc(a.skipped_why))
        lines.append(i_("/alive set <url> to change it · /alive off to stop"))
    return Html("\n".join(lines))


def handle(ctx):
    cfg = ctx.cfg
    words = ctx.arg.strip().split()
    verb = words[0].lower() if words else ""
    if verb == "set":
        url = words[1] if len(words) > 1 else ""
        if not _alive.valid(url):
            return Html("🛰 I did not change it: send the whole ping URL, starting https:// -- "
                        "<code>/alive set https://hc-ping.com/…</code>")
        cfg[_alive.KEY] = url
        save_cfg(cfg, ctx.cfg_path)
        return page(ctx, "🛰 <b>Outside check: ON</b>")
    if verb == "off":
        cfg[_alive.KEY] = ""
        save_cfg(cfg, ctx.cfg_path)
        return page(ctx, "🛰 <b>Outside check: OFF</b>")
    return page(ctx, "🛰 <b>Outside check: %s</b>" % ("ON" if _alive.url_of(cfg) else "OFF -- no URL set"))


COMMAND = declare(Command(
    names=("/alive",), section="server", order=30,
    help_line="/alive: the outside 'is it alive' check -- a ping every 5 min to a monitoring service that texts you when "
              "the pings stop (<code>/alive set &lt;url&gt;</code>)",
    chart=None, handle=handle, needs_ledger=False, examples=("/alive off", "/alive set nonsense")))
