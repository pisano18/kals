"""/hedges -- the pin bot's insurance: the last 8 hedges, newest first, whether each was needed, % of the bank.

v-tg-rebuild step 9 (2026-10-30): Phone.text_hedges as a command module (load + render), byte-identical (golden shadow).
No Kalshi read, no file of its own: the Ledger's hedge outcomes and its bank at each hedge.
"""
from botdata.fmt import usd                       # == pinphone.usd (botdata/fmt.py)
from phone.command import Command, declare
from phone.html import Html, esc, i_
from pindesk import et_str, pct

SHOWN = 8


def load(ctx):
    """[(hedge outcome, bank at its time or None)] newest first, at most SHOWN."""
    ho = list(reversed(ctx.ledger.hedge_outcomes()))[:SHOWN]
    return [(g, ctx.ledger.bank_at(g["t"]) if g.get("t") and g.get("net") is not None else None) for g in ho]


def render(rows, ctx):
    if not rows:
        return Html("No hedges yet.")
    nice_coin = ctx.pp.nice_coin
    out = ["🛡 <b>Pin bot's insurance</b> (the last %d hedges, newest first)" % len(rows)]
    for g, b0 in rows:
        mark = {"NEEDED": "✅", "WASTED": "➖"}.get(g["verdict"], "⏳")
        out.append("%s <b>%s</b> · %s %s · belief %.0f%% · net <b>%s</b>%s" % (
            mark, esc(g["verdict"] or "pending"),
            esc(et_str(g["t"], "%a %b %d %I:%M %p").replace(" 0", " ") if g["t"] else "?"),
            esc(nice_coin(g["tk"])), 100 * float(g.get("belief") or 0),
            esc(usd(g["net"]) if g["net"] is not None else "-"),
            (" (%s of the bank)" % esc(pct(g["net"] / b0))) if b0 else ""))
    out.append(i_("belief = the bot's odds its side wins when it bought the insurance · NEEDED = the bet lost and "
                  "the insurance covered part of it; WASTED = the bet held and the insurance expired (its premium)"))
    return Html("\n".join(out))


COMMAND = declare(Command(
    names=("/hedges",), section="now", order=60,
    help_line="/hedges — the pin bot's insurance, whether it was needed, % of the bank",
    chart="hedges", load=load, render=render))
