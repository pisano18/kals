"""/week /month -- the weekly and monthly reports on demand (v-tg-rebuild step 12, lane Q, 2026-10-30): every bot's money
this Mon..Sun week (or this calendar month) so far, its % of each pot and of all pots, the best and worst day, the losses,
and the week (month) before beside it. '/week last' and '/month last': the one before. The same page the monitor sends
on Sunday 8 PM ET and on the 1st at 8 AM ET (phone/reports.py).
"""
from phone.command import Command, declare
from phone.reports import build, report_html


def load(ctx):
    which = "last" if ctx.arg.strip().lower() in ("last", "prev", "previous", "before") else "this"
    kind = "week" if ctx.cmd == "/week" else "month"
    return build(ctx.bs(), ctx.now(), kind, which, getter=ctx.bs_getter, procs=ctx.bs_procs)


def render(d):
    return report_html(d)


def fail(e):
    return ("Could not build the report: %s\nEverything else still works -- /days and /bots carry the same money."
            % str(e)[:200])


COMMANDS = declare(
    Command(names=("/week",), section="money", order=22,
            help_line="/week — this week (Mon to Sun) so far, every bot: money, % of its pot, best and worst day, "
                      "losses, against the week before (<code>/week last</code>: the week before)",
            chart=None, load=load, render=render, fail=fail, examples=("/week last",)),
    Command(names=("/month",), section="money", order=24,
            help_line="/month — this month so far, the same, against last month (<code>/month last</code>: last month)",
            chart=None, load=load, render=render, fail=fail, examples=("/month last",)),
)
