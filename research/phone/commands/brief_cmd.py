"""/brief /summary -- the daily briefing: every pot's money today first (the /today top, with its %), then pinbrief's
words for the main account, unchanged (the phone quotes pinbrief, never rebuilds it: one daily summary to keep honest).

v-tg-rebuild step 9 (2026-10-30): Phone.text_brief as a command module (load + render), byte-identical (golden
shadow). The old method's wall covers everything and logs NOTHING, so it is kept here as written (no `fail`: Command.run
would log a traceback). The every-pot top is commands/day.py's all_bots_day (Phone._all_bots_day with its pace line):
v-tg-rebuild step 10 keeps ONE copy, shared with /today, /yesterday and the 8 AM alert.
"""
from phone.command import Command, declare
from phone.commands.day import all_bots_day           # the ONE copy of Phone._all_bots_day (with its pace line)
from phone.html import Html, esc
from pindesk import et_day


def failed(e):
    return ("Could not build today's briefing: %s\n"
            "Everything else still works -- try /today again, or "
            "/days for the plain numbers." % str(e)[:160])


def load(ctx):
    """{'body': pinbrief's words laid out, 'top': every pot's lines for today ([] = none), 'mw': the main account's
    bots in words} or {'err': exception} (nothing logged, as before)."""
    try:
        import pinbrief
        body = ctx.pp.brief_html(pinbrief.text(pinbrief.brief(ledger=ctx.ledger)))
        top = all_bots_day(ctx, et_day(ctx.now()), "Today")      # 2026-10-26: every pot first, with its %
        if not top:
            return {"body": body, "top": top}
        return {"body": body, "top": top, "mw": ctx.pp.main_words(ctx.active())}
    except Exception as e:                                      # noqa: BLE001
        return {"err": e}


def render(d):
    if "err" in d:
        return failed(d["err"])
    try:
        body, top = d["body"], d["top"]
        if not top:
            return body
        mw = d["mw"]
        return Html("\n".join(top + ["", "🏦 <b>%s (main account)</b>" % esc(mw[:1].upper() + mw[1:]), str(body)]))
    except Exception as e:                                      # noqa: BLE001
        return failed(e)


COMMAND = declare(Command(
    names=("/brief", "/summary"), section="now", order=70,
    help_line="/brief — the daily briefing: money, what changed, what it did, the market, what to watch",
    chart="days", load=load, render=render))
