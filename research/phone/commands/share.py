"""/share, /share_today, /share_days, /share_funds (/share_bots) -- pictures safe to post publicly.

v-tg-share (2026-11-12, the operator: "Make a share command to get safe, postable charts" -- /today, /days, /bots
/funds). The words say what the picture leaves out; the picture is phone/charts/share.py (its leak check refuses any
picture with a date, a clock time, a bot, account or market word on it). /share alone lists the three, tappable.
"""
from phone.command import Command, declare
from phone.html import Html

WHAT = {"/share_today": "today, every bot together, hour by hour",
        "/share_days": "the last 30 whole days: each day, as % of the account, and the running total",
        "/share_funds": "the account over the last 30 days (deposits do not move the line)",
        "/share_bots": "the account over the last 30 days (deposits do not move the line)"}
LEAVES_OUT = ("No dates, weekdays or clock times (days are numbered), no bot, account or market names, never market by "
              "market. If anything on it could give one away, the picture is not sent.")
TIP = ("Save the picture itself to post it -- a screenshot of this chat shows when it was sent. Day numbers end "
       "yesterday, so posting a few days later stops anyone counting back to dates.")


def render_menu(_data, ctx):
    asked = (ctx.arg or "").strip().lower().lstrip("/")
    tap = "/share_" + ("funds" if asked == "bots" else asked)
    if tap in WHAT:
        return Html("📸 Tap %s for that picture.\n\n%s" % (tap, LEAVES_OUT))
    return Html("📸 <b>Pictures safe to post</b>\n%s\n\n%s\n\n%s" % (
        "\n".join("%s — %s" % (n, WHAT[n]) for n in ("/share_today", "/share_days", "/share_funds")), LEAVES_OUT, TIP))


def render_one(_data, ctx):
    return Html("📸 <b>Postable picture coming</b>: %s.\n\n%s\n\n%s" % (WHAT.get(ctx.cmd, "?"), LEAVES_OUT, TIP))


COMMANDS = declare(
    Command(names=("/share",), section="money", order=90,
            help_line="/share — pictures of the results safe to post publicly (no dates, times or names)",
            chart=None, needs_ledger=False, load=lambda ctx: None, render=render_menu),
    Command(names=("/share_today", "/share_days", "/share_funds", "/share_bots"), section=None,
            chart={"/share_today": "share_today", "/share_days": "share_days", "/share_funds": "share_funds",
                   "/share_bots": "share_funds"},
            needs_ledger=False, load=lambda ctx: None, render=render_one))
