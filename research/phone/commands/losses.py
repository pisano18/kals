"""/losses -- EVERY bot's losing markets: the last LOSSES_SHOWN by ET day, each with its bot, the market, side and
contracts, $ and % of that bot's pot; then every bot's count, last 7 days, $ lost and worst. When botstats cannot be
read at all: the main account's losing closes from its own ledger (the /losses of before 10-26).

v-tg-rebuild step 9, lane D2 (2026-10-30): Phone.text_losses + Phone.text_losses_main as a command module (load +
render), byte-identical (golden shadow). The data is the chart's own: tgcharts.all_losses (botstats, Kalshi's books,
every pot), asked exactly as the old method asked it (the dict context with the old pinphone module as 'pp').
"""
import traceback

import bots as _bots
from botdata import hedgeplay as _hedgeplay
from botdata.fmt import cnt as _cnt                    # == pinphone._cnt
from botdata.fmt import usd                            # == pinphone.usd
from phone.command import Command, declare
from phone.html import MAX_LEN, Html, esc, i_, pre, table
from phone.log import log
from phone.render.botcards import _day_long, main_shared, main_sharers, nice_coin
from pindesk import Ledger, et_str, pct


def load(ctx):
    """('all', (botstats, rows, per, missing, BOT_SHORT)) from tgcharts.all_losses, or ('main', ...) -- the main
    account's losing closes -- when that fails (logged) or knows no bot."""
    try:
        from botdata import series          # v-tg-rebuild step 10: the numbers straight from botdata (was via tgcharts)
        bs, rows, per, missing = series.all_losses(ctx.bs(), ctx.now(), ctx.bs_getter, ctx.bs_procs)
    except Exception:                                       # noqa: BLE001
        log(traceback.format_exc())
        return "main", load_main(ctx)
    if not per:
        return "main", load_main(ctx)
    return "all", (bs, rows, per, missing, _bots.BOT_SHORT)


def load_main(ctx):
    """Phone.text_losses_main's reads: ([(close, net, legs, bank just before)], the all-time summary) or None (none)."""
    rows = ctx.ledger.losing_closes()[:ctx.pp.LOSSES_SHOWN]
    if not rows:
        return None
    s = Ledger.summary(ctx.ledger.settled)
    return [(close, net, legs, ctx.ledger.bank_at(close - 1) if close else None) for close, net, legs in rows], s


def render(data, ctx):
    kind, d = data
    if kind == "main":
        return render_main(d, ctx)
    bs, rows, per, missing, short = d
    lost = sum(p["lost"] for p in per.values())
    settled = sum(p["settled"] for p in per.values())
    if not rows:
        return Html("No losing markets in any pot (%s settled)." % _cnt(settled)
                    + (" ⚠️ Leaves out %s (Kalshi could not be read)." % esc(", ".join(missing)) if missing else ""))

    def line(r):
        what = r["what"][5:] if r["bot"] in ("race", "earlier") and r["what"].startswith("race ") else r["what"]
        held = ("hedged x%s" % _cnt(r["contracts"])) if r["side"] == "both" else \
            ("%s x%s" % (r["side"].upper(), _cnt(r["contracts"])) if r["side"] in ("yes", "no") else "")
        p = r.get("play")
        if p:                       # v-hedge-split: what the bet lost and what the hedge (and a buy after the flip) got back
            held = "bet %s x%s %s · hedge %s%s" % (
                p["bet"]["side"].upper(), _cnt(p["bet"]["n"]), usd(p["bet"]["money"]), usd(p["hedge"]["money"]),
                (" · after the flip %s" % usd(p["flip"]["money"])) if p["flip"] else "")
        return "<b>%s</b>%s · %s · %s" % (esc(usd(r["money"])),
                                         (" (%s)" % esc(bs.pot_pct_txt(r["pct"]))) if r["pct"] is not None else "",
                                         esc(short.get(r["bot"], r["bot"])), esc(" ".join(x for x in (what, held) if x)))

    tbl = [("Bot", "Lost", "7d", "$ lost", "Worst")]
    for nm in tuple(bs.BOTS) + ("earlier", "other"):         # all_losses folds hidden bots into one row
        p = per.get(nm)
        if p and p["settled"]:
            tbl.append((short.get(nm, nm), _hedgeplay.lost_cell(p["lost"], p.get("hedge_costs", 0), p["settled"]),
                        ("%d+%dh" % (p["lost_7d"], p["hedge_costs_7d"])) if p.get("hedge_costs_7d") else str(p["lost_7d"]),
                        "%.2f" % p["money_lost"], "%.2f" % p["worst"] if p["worst"] is not None else "-"))
    worst = min((p["worst"] for p in per.values() if p["worst"] is not None), default=None)
    hc, hc7 = sum(p.get("hedge_costs", 0) for p in per.values()), sum(p.get("hedge_costs_7d", 0) for p in per.values())
    lost7 = sum(p["lost_7d"] for p in per.values())
    tbl.append(("ALL", _hedgeplay.lost_cell(lost, hc, settled), ("%d+%dh" % (lost7, hc7)) if hc7 else str(lost7),
                "%.2f" % sum(p["money_lost"] for p in per.values()), "%.2f" % worst if worst is not None else "-"))
    tail = ["", "📊 <b>By bot, all time</b>", pre(table(tbl, "lrrrr")),
            i_("Lost = markets lost / settled · 7d = lost in the last 7 days · $ lost = all its losing markets "
               "added up · Worst = its worst single market%s · /losses chart: every loss, coloured by bot"
               % (" · 1+4h = 1 lost, 4 hedge costs (the bet won; its hedge cost more than it made, not a loss)"
                  if hc else ""))]
    # v-hedge-split (2026-11-01): the hedge area -- how many times the hedge fired and what it did, so a hedge cost is
    # still tracked (operator 11-01: "add a seperate area ... so it's still tracked and appreciated")
    hz = [(nm, p) for nm, p in per.items() if p.get("hedges")]
    if hz:
        tail += ["", "🛡️ <b>Hedges</b> (%s)" % esc(", ".join(short.get(nm, nm) for nm, _p in hz))]
        for nm, p in hz:
            if p.get("hedges_7d"):
                tail.append("Last 7 days: " + esc(_hedgeplay.hedge_line(p["hedges_7d"], emoji=False)[len("Hedges: "):]))
            tail.append("All time: " + esc(_hedgeplay.hedge_line(p["hedges"], emoji=False)[len("Hedges: "):]))
        tail.append(i_("needed = the bet lost and the hedge paid some back · not needed = the bet won and the hedge "
                       "cost a little · /hedges for every one"))
    n = min(ctx.pp.LOSSES_SHOWN, len(rows))
    while True:
        out = ["🔴 <b>%s losing markets</b> of %s settled, every bot (%.1f%%) · %d in the last 7 days" % (
                   _cnt(lost), _cnt(settled), 100.0 * lost / settled if settled else 0.0,
                   sum(p["lost_7d"] for p in per.values())),
               i_("the last %d, newest first · %% = of that bot's pot when its day began (%s) · Kalshi's books, "
                  "every pot" % (n, ("%s share the main account" % main_shared(per)) if main_sharers(per) else
                                 "earlier bots = the paused or stopped ones"))]
        if missing:
            out.append("⚠️ PARTIAL: leaves out %s (Kalshi could not be read)" % esc(", ".join(missing)))
        day = None
        for r in rows[:n]:
            if r["day"] != day:
                day = r["day"]
                out += ["", "<b>%s</b>" % esc(_day_long(day))]
            out.append(line(r))
        msg = "\n".join(out + tail)
        if len(msg) <= MAX_LEN or n <= 5:
            return Html(msg)
        n -= 5


def render_main(d, ctx):
    """Phone.text_losses_main's page."""
    if d is None:
        return Html("No losing closes.")
    rows, s = d
    out = ["🔴 <b>%d losing closes</b> of %d all time (%.1f%%)%s" % (
               s["lost"], s["closes"], s["loss_rate"],
               (" · %d hedge cost%s (the bet won)" % (s["hedge_costs"], "" if s["hedge_costs"] == 1 else "s"))
               if s.get("hedge_costs") else ""),
           i_("the last %d, newest first · %% = of the bank just before it (Kalshi's books, main account: pin + "
              "race)" % len(rows))]
    for close, net, legs, b0 in rows:
        out.append("<b>%s</b>%s · %s · %s" % (
            esc(usd(net)), (" (%s)" % esc(pct(net / b0))) if b0 else "",
            esc(et_str(close, "%a %b %d %I:%M %p").replace(" 0", " ") if close else "?"),
            esc(", ".join(sorted({nice_coin(l["tk"]) for l in legs})))))
    return Html("\n".join(out))


COMMAND = declare(Command(
    names=("/losses",), section="now", order=50,
    help_line="/losses — every bot's losing markets: which bot, $ and % of its pot",
    chart="losses", load=load, render=render))
