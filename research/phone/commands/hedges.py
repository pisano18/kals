"""/hedges -- the pin bot's insurance: the last 8 hedges, newest first, whether each was needed, % of the bank; then what
the hedges did all time by what fired them, and the last 7 days market by market: the bet, the hedge, the outcome.

v-tg-rebuild step 9 (2026-10-30): Phone.text_hedges as a command module (load + render), byte-identical (golden shadow).
No Kalshi read, no file of its own: the Ledger's hedge outcomes and its bank at each hedge.
v-hedge-split (2026-11-01, the operator: "add a seperate area wherever you fix that to show how many times and what the
hedge did so it's still tracked and appreciated" and "break down the losses as what I originally bought, what I bought
as hedge, and what was the outcome"): the trigger table (botdata/hedgeplay.tally over the ledger's split markets) and
the 7-day list (botdata/hedgeplay.play_lines), under the old list.
"""
from botdata import hedgeplay as _hedgeplay
from botdata.fmt import usd                       # == pinphone.usd (botdata/fmt.py)
from phone.command import Command, declare
from phone.html import MAX_LEN, Html, esc, i_, pre, table
from pindesk import et_str, pct

SHOWN = 8
WEEK_S = 7 * 86400
WEEK_SHOWN = 12                                   # the 7-day list's newest markets (the message has a size limit)


def load(ctx):
    """{"rows": [(hedge outcome, bank at its time or None)] newest first, at most SHOWN; "all": hedgeplay.tally of every
    split market; "week": the split markets that closed in the last 7 days, newest first}."""
    ho = list(reversed(ctx.ledger.hedge_outcomes()))[:SHOWN]
    rows = [(g, ctx.ledger.bank_at(g["t"]) if g.get("t") and g.get("net") is not None else None) for g in ho]
    split = [s for s in ctx.ledger.settled if s.get("play")]
    now = ctx.now()
    week = [s for s in split if (s.get("close") or s.get("t") or 0) >= now - WEEK_S]
    week.sort(key=lambda s: -(s.get("close") or s.get("t") or 0))
    return {"rows": rows, "all": _hedgeplay.tally(split), "week": week}


def _cell(x):
    return "%+.2f" % x


def trigger_table(t):
    """What the hedges did by what fired them: Fired, Need (the bet lost), Got back (the hedge legs on those), Cost
    (the hedge legs on bets that won), Net (every hedge leg). Html lines."""
    rows = [("Hedge", "Fired", "Need", "Got back", "Cost", "Net")]
    for k in _hedgeplay.TRIGGERS:
        x = t["by_trigger"].get(k)
        if x:
            rows.append((_hedgeplay.TRIGGER_WORDS[k].replace(" hedge", "").replace("trigger ", ""), x["fired"],
                         x["needed"], _cell(x["got_back"]), _cell(x["cost"]), _cell(x["net"])))
    rows.append(("ALL", t["fired"], t["needed"], _cell(t["got_back"]), _cell(t["cost"]), _cell(t["net"])))
    return [pre(table(rows, "lrrrrr")),
            i_("odds = fired because the bot's odds its side wins fell under the hedge line · jump = fired because the "
               "price jumped 6+ standard deviations right after the buy · not logged = before the bot wrote which · "
               "Need = the bet lost, so the hedge was needed · Got back = what the hedge made on those · Cost = what "
               "it cost on bets that won · Net = the two together")]


def week_lines(week, nice_coin):
    """The last 7 days, market by market: when, which coin, then the bet, the hedge, any buy after the flip, and the
    outcome (hedgeplay.play_lines). Html lines."""
    out = []
    for s in week[:WEEK_SHOWN]:
        p = s["play"]
        L = _hedgeplay.play_lines(p)
        mark = "✅" if not p["bet_won"] else "➖"
        out.append("%s <b>%s %s</b> · %s" % (mark, esc(et_str(s.get("close") or s["t"], "%a %b %d %I:%M %p")
                                                       .replace(" 0", " ")), esc(nice_coin(s["tk"])), esc(L[0])))
        out += ["   %s" % esc(x) for x in L[1:-1]]
        out.append("   <b>%s</b>" % esc(L[-1]))
    if len(week) > WEEK_SHOWN:
        out.append(i_("and %d more this week" % (len(week) - WEEK_SHOWN)))
    return out


def render(d, ctx):
    rows = d["rows"]
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
    tail = []
    if d.get("all"):
        tail += ["", "🧮 <b>What the hedges did, all time</b>", esc(_hedgeplay.hedge_line(d["all"]))]
        tail += trigger_table(d["all"])
    week = d.get("week") or []
    n = min(len(week), WEEK_SHOWN)
    while True:
        if week:
            wk = (["", "📋 <b>Last 7 days, market by market</b> (what was bought, what the hedge bought, how it ended)"]
                  + week_lines(week[:n], nice_coin))
            if n < len(week):
                wk.append(i_("and %d more this week" % (len(week) - n)))
        else:
            wk = ["", i_("No hedge fired in the last 7 days.")] if d.get("all") else []
        msg = "\n".join(out + tail + wk)
        if len(msg) <= MAX_LEN or n <= 1:
            return Html(msg)
        n -= 2


COMMAND = declare(Command(
    names=("/hedges",), section="now", order=60,
    help_line="/hedges — the pin bot's insurance, whether it was needed, % of the bank",
    chart="hedges", load=load, render=render))
