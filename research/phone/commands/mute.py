"""/mute /unmute -- alerts off / on (the alerts tick still tracks every change while muted, so an unmute replays nothing).

v-tg-rebuild step 9 (2026-10-30): the /mute and /unmute branches of Phone.handle as a command module, byte-identical
(golden shadow). The one state it writes is the runtime's `muted` flag (ctx.state.muted: the Phone until step 11), which
phone/alerts.py reads.
"""
from phone.command import Command, declare
from phone.html import Html


def handle(ctx):
    if ctx.cmd == "/mute":
        ctx.state.muted = True
        return Html("🔕 Alerts off. /unmute to turn them back on.")
    ctx.state.muted = False
    return Html("🔔 Alerts on.")


COMMAND = declare(Command(
    names=("/mute", "/unmute"), section="controls", order=40, help_line="/mute · /unmute — alerts off / on",
    chart=None, handle=handle))
