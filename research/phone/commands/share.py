"""/share, /share_brag, /share_today, /share_yesterday, /share_days, /share_funds (/share_bots) -- results pictures.

v-tg-share (2026-11-12, the operator: "Make a share command to get safe, postable charts" -- /today, /yesterday, /days,
/bots /funds -- "exactly the same as their originals except for what must be hidden"). The picture is the original drawn
with share=True (phone/charts/share.py: what is hidden, and the leak check that refuses any picture with a date, a clock
time, a bot, account or market word on it). /share alone lists them, tappable.

v-tg-brag (2026-11-13, the operator: safe "even to that team of quants" whose full-time job is to work it out):
/share_brag is the one to post -- the last 60 days with dollars, percents and the bankroll, the days shuffled inside
10-15 day stretches. The others keep the real order of days or hours, which such a team lines up with market history
once the post date dates it, so /share lists them as for the operator only.
"""
from phone.command import Command, declare
from phone.html import Html

WHAT = {"/share_brag": "60-day timeline", "/share_today": "/today", "/share_yesterday": "/yesterday",
        "/share_days": "/days", "/share_funds": "/funds", "/share_bots": "/bots"}
BRAG = ("/share_brag",)
LISTED = ("/share_today", "/share_yesterday", "/share_days", "/share_funds")
BRAG_NOTE = ("The one to post: the last 60 days, every real day's money and %, after fees, and the real bankroll. The "
             "days are shuffled only inside 10-15 day stretches (a new shuffle every time), so early days stay early, "
             "every stretch's total is real, the bankroll ends exactly where it really is, and no day sits on its date. "
             "No hours or names. Post it once; a new one every week would date the newest days.")
PRIVATE_NOTE = ("For you, not for posting: these keep the real order of days or hours. A team whose job is to work it "
                "out dates them from when you post and lines them up with market history.")
LEAVES_OUT = ("The same picture with names, clock times and single markets hidden -- but in the real order of days or "
              "hours, so not safe against a team that studies it. For you, not for posting.")
TIP = "Save the picture itself to post it -- a screenshot of this chat shows when it was sent."


def render_menu(_data, ctx):
    asked = (ctx.arg or "").strip().lower().lstrip("/")
    tap = "/share_" + ("funds" if asked == "bots" else asked)
    if tap in WHAT:
        return Html("📸 Tap %s for that picture.\n\n%s" % (tap, BRAG_NOTE if tap in BRAG else LEAVES_OUT))
    return Html("📸 <b>Pictures of the results</b>\n\n<b>Safe to post:</b>\n%s\n%s\n\n<b>For you only:</b>\n%s\n%s\n\n%s"
                % ("\n".join("%s — %s" % (n, WHAT[n]) for n in BRAG), BRAG_NOTE,
                   "\n".join("%s — %s, names hidden" % (n, WHAT[n]) for n in LISTED), PRIVATE_NOTE, TIP))


def render_one(_data, ctx):
    if ctx.cmd in BRAG:
        return Html("📸 <b>Postable %s picture coming.</b>\n\n%s\n\n%s" % (WHAT[ctx.cmd], BRAG_NOTE, TIP))
    return Html("📸 <b>%s picture coming, for you only.</b>\n\n%s" % (WHAT.get(ctx.cmd, "?"), LEAVES_OUT))


COMMANDS = declare(
    Command(names=("/share",), section="money", order=90,
            help_line="/share — pictures of the results: one safe to post publicly (no dates, times or names)",
            chart=None, needs_ledger=False, load=lambda ctx: None, render=render_menu),
    Command(names=("/share_brag", "/share_today", "/share_yesterday", "/share_days", "/share_funds", "/share_bots"),
            section=None,
            chart={"/share_brag": "share_brag", "/share_today": "share_today", "/share_yesterday": "share_yesterday",
                   "/share_days": "share_days", "/share_funds": "share_funds", "/share_bots": "share_funds"},
            needs_ledger=False, load=lambda ctx: None, render=render_one))
