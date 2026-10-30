"""/pin /forecaster (/fc) /ladder /weather (/wx) /fx /jb (/jumpband) -- one bot in full: running or not and why, version,
the money table, the last 7 days, open bets, cash; every sentence behind a tap; the bot's own footer line.

v-tg-rebuild step 9, lane D2 (2026-10-30): Phone.text_bot as command modules (load + render), byte-identical (golden
shadow). ONE Command per registry bot without a page of its own (pinphone.BOT_CMDS: every alias of it), so adding a bot
to research/bots adds its page here with no edit. The bot's main command (BOT_CMD_OF) comes first; the race has /race
(lane D3). A paused or retired bot's command is answered by the router (Phone.text_hidden), not here.
"""
import bots as _bots
from phone.command import Command, declare
from phone.html import Html, i_
from phone.render.botcards import BOT_CMD_OF, BOT_CMDS, PAGE_FOOTER, bs_bot_html


def page(name):
    """The Command for bot `name`'s page (Phone.text_bot(name))."""
    cmd = BOT_CMD_OF.get(name, "/" + name)

    def load(ctx):
        """botstats' dict for the bot (Phone._bs_get(name)), then the clock in its words (the same order)."""
        b = ctx.bs_get(name)
        return b, ctx.bs().et_clock(ctx.now())

    def render(data):
        b, now_et = data
        out = bs_bot_html(b, now_et)
        more = PAGE_FOOTER.get(name)                    # v-tg-rebuild step 5: the registry's Bot.page_footer
        return Html("\n".join(out) + ("\n\n" + i_(more) if more else ""))

    def fail(e):
        return ("Could not build %s: %s\nEverything else still works -- /stats and /race carry the "
                "main account's numbers." % (cmd, str(e)[:200]))

    names = [c for c in BOT_CMDS if BOT_CMDS[c] == name]
    names.sort(key=lambda c: c != cmd)                  # the one command the phone names for the bot, first
    b = _bots.get(name)
    return Command(names=tuple(names), section="one_bot", help_line=None, order=b.order if b is not None else 0,
                   chart="bot:%s" % name, load=load, render=render, fail=fail)


BOT_NAMES = tuple(dict.fromkeys(BOT_CMDS.values()))   # registry order
COMMANDS = declare(*[page(n) for n in BOT_NAMES])
