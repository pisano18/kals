"""/share, /share_today, /share_yesterday, /share_days, /share_funds (/share_bots), /share_brag, /share_brag_8 --
pictures safe to post publicly.

v-tg-share (2026-11-12, the operator: "Make a share command to get safe, postable charts" -- /today, /yesterday, /days,
/bots /funds -- "exactly the same as their originals except for what must be hidden"). The words say what the picture
leaves out; the picture is the original drawn with share=True (phone/charts/share.py: what is hidden, and the leak check
that refuses any picture with a date, a clock time, a bot, account or market word on it). /share alone lists them,
tappable.

v-tg-brag (2026-11-13, the operator: safe "even to that team of quants" whose full-time job is to work it out):
/share_brag (4 weeks) and /share_brag_8 (8 weeks) carry only two real numbers, the return and the weeks; listed first,
as the one to post.
"""
from phone.command import Command, declare
from phone.html import Html

WHAT = {"/share_brag": "4-week growth", "/share_brag_8": "8-week growth", "/share_today": "/today",
        "/share_yesterday": "/yesterday", "/share_days": "/days", "/share_funds": "/funds", "/share_bots": "/bots"}
BRAG = ("/share_brag", "/share_brag_8")
LISTED = ("/share_today", "/share_yesterday", "/share_days", "/share_funds")
BRAG_NOTE = ("The safest picture: it carries only two real numbers, the return over the weeks (time-weighted, after "
             "fees; deposits never count) and the weeks. The curve between them is smoothed, and the picture says so. "
             "No dollars, days, drops or bots, so there is nothing to line up with anything. Post it once; a new "
             "number every week would give the weeks away.")
LEAVES_OUT = ("The same picture with only this hidden: dates and clock times (days are numbered, a day runs in hours), "
              "each market's own step and dot (the day's line is drawn hour by hour), the market count, and bot, "
              "account and market names. If anything on it could still give one away, the picture is not sent.")
TIP = ("Save the picture itself to post it -- a screenshot of this chat shows when it was sent. Posting a few days "
       "later stops anyone counting the day numbers back to dates.")


def render_menu(_data, ctx):
    asked = (ctx.arg or "").strip().lower().lstrip("/")
    tap = "/share_" + ("funds" if asked == "bots" else asked)
    if tap in WHAT:
        return Html("📸 Tap %s for that picture.\n\n%s" % (tap, BRAG_NOTE if tap in BRAG else LEAVES_OUT))
    return Html("📸 <b>Pictures safe to post</b>\n\n<b>Safest, to brag with:</b>\n%s\n%s\n\n<b>Your own charts, "
                "with the giveaways hidden:</b>\n%s\n%s\n\n%s" % (
                    "\n".join("%s — %s" % (n, WHAT[n]) for n in BRAG), BRAG_NOTE,
                    "\n".join("%s — %s, safe to post" % (n, WHAT[n]) for n in LISTED), LEAVES_OUT, TIP))


def render_one(_data, ctx):
    return Html("📸 <b>Postable %s picture coming.</b>\n\n%s\n\n%s" % (
        WHAT.get(ctx.cmd, "?"), BRAG_NOTE if ctx.cmd in BRAG else LEAVES_OUT, TIP))


COMMANDS = declare(
    Command(names=("/share",), section="money", order=90,
            help_line="/share — pictures of the results safe to post publicly (no dates, times or names)",
            chart=None, needs_ledger=False, load=lambda ctx: None, render=render_menu),
    Command(names=("/share_today", "/share_yesterday", "/share_days", "/share_funds", "/share_bots", "/share_brag",
                   "/share_brag_8"), section=None,
            chart={"/share_today": "share_today", "/share_yesterday": "share_yesterday", "/share_days": "share_days",
                   "/share_funds": "share_funds", "/share_bots": "share_funds", "/share_brag": "share_brag",
                   "/share_brag_8": "share_brag_8"},
            needs_ledger=False, load=lambda ctx: None, render=render_one))
