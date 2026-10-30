"""/bots -- every bot running now, in one page: the all-pots money table, the week by bot, one card a bot, every pot's
cash, the last 7 days; every sentence of the plain /bots behind a tap.

v-tg-rebuild step 9, lane D2 (2026-10-30): Phone.text_bots as a command module (load + render), byte-identical (golden
shadow). The page is render/botcards.bs_all_html over botstats.all_bots (Kalshi read at most once a minute).
"""
from phone.command import Command, declare
from phone.html import Html
from phone.render.botcards import bs_all_html


def load(ctx):
    """botstats' all-bots dict (Phone._bs_get('all'))."""
    return ctx.bs_get("all")


def render(a):
    return Html("\n".join(bs_all_html(a)))


def fail(e):
    """Phone.text_bots' wall: any error (the read or the page) -> these words, the traceback logged."""
    return ("Could not build /bots: %s\nEverything else still works -- /stats and /race carry the "
            "main account's numbers." % str(e)[:200])


COMMAND = declare(Command(
    names=("/bots",), section="money", order=50,
    help_line="/bots — every bot running now: money today / 7 days / all time, each pot's cash, and the total of all of "
              "them",
    chart="funds", load=load, render=render, fail=fail))
