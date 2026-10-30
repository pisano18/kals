"""/days -- EVERY bot's last 7 ET days: the week's headline, a day table with each day's % of all pots and its return on
the bets, the week bot by bot, the 30-day averages, the all-time line; the main account's own days behind a tap; the
pin bot's running version. Falls back to the main account's table alone when botstats cannot be read.

v-tg-rebuild step 9, lane D1 (2026-10-30): Phone.text_days, _main_days and _version_line as a command module (load +
render), byte-identical (golden shadow). No wall around the whole (as before): a botstats failure is logged and answered
with the main account's own days.
"""
import traceback

from botdata.fmt import dollars, usd                  # == pinphone.dollars / usd
from phone.command import Command, declare
from phone.commands.day import day_data, day_lines
from phone.html import Html, details, esc, hbar, i_, pre, table
from phone.log import log
from phone.render.botcards import _bs, _nof, bots_avg_table, bots_window_table, bs_headline, main_words
from pindesk import Ledger, et_day_start, et_str, pct


def main_days(ctx):
    """Phone._main_days: the main account's (pin + race) last 7 ET days from the bot's own ledger: [(day, net, % of the
    bank that began it or None, lost closes, closes)], newest first."""
    out = []
    for d in list(reversed(ctx.ledger.days()))[:7]:
        s_ = Ledger.summary(ctx.ledger.settled_on(d))
        b0 = ctx.ledger.bank_at(et_day_start(d))
        out.append((d, s_["net"], (s_["net"] / b0) if b0 else None, s_["lost"], s_["closes"]))
    return out


def version_data(ctx):
    """Phone._version_line's reads: (the pin bot's running version, the main-account markets closed since it) or None
    (no version; the markets unreadable)."""
    ver = ctx.pp.live_version(ctx.versions_path)
    if not ver:
        return None
    try:
        vs = [m for m in ctx.markets().values() if m["close"] is not None and m["close"] >= ver[1]]
    except Exception:                                    # noqa: BLE001
        return None
    return ver, vs


def version_line(v, pp):
    """'🏷 SINCE v-x (10/23 09:45 PM ET): +$58.11, 97 markets, 5 lost (5.2%)' or None. 2026-10-01, the operator: "/days
    doesn't show any recent negative days on this version" -- a deploy day mixes two versions, so the running one gets
    its own line (Kalshi's books, main account, markets closing after its deploy)."""
    if v is None:
        return None
    ver, vs = v
    lost = sum(1 for m in vs if m["pnl"] < -0.004)
    if not vs:
        return "🏷 <b>Pin bot since %s</b> (%s ET): nothing settled since" % (
            esc(ver[0]), esc(et_str(ver[1], "%m/%d %I:%M %p")))
    return "🏷 <b>Pin bot since %s</b> (%s ET): <b>%s</b>, %d markets, %d lost%s" % (
        esc(ver[0]), esc(et_str(ver[1], "%m/%d %I:%M %p")), esc(usd(sum(m["pnl"] for m in vs))), len(vs),
        lost, (" (%s)" % pp.pct_of(lost, len(vs), 1)) if vs else "")


def load(ctx):
    """Phone.text_days' reads, in its order: botstats (a failure logged -> None), the main account's days, the all-time
    day (only without botstats), the running version."""
    try:
        a = ctx.bs_get("all")
    except Exception:                                        # noqa: BLE001
        log(traceback.format_exc())
        a = None
    d = {"a": a, "main": main_days(ctx)}
    if a is None:
        d["all_time"] = day_data(ctx, ctx.ledger.settled, None)
    d["version"] = version_data(ctx)
    return d


def render(d, ctx):
    a, main = d["a"], d["main"]
    out = []
    if a is not None:
        bs = _bs()
        tot = a["total"]
        out.append(bs_headline(tot["last_7_days"], "of all pots", "All bots", when="last 7 days"))
        at = tot["all_time"]
        if at["markets"]:
            out.append(i_("all time %s%s · %s, %d lost · every pot, Kalshi's books; ET days" % (
                usd(at["money"]), (" (%s on the %s put in)" % (bs.pot_pct_txt(at["pot_pct"]), dollars(at["pot"])))
                if at.get("pot_pct") is not None and at.get("pot") else "", _nof(at["markets"], "market"), at["lost"])))
        firsts = [mm.get("first_day") for mm in [a["bots"][x]["money"] for x in bs.BOTS] + [a["other"]]
                  if mm.get("first_day")]               # every bot's books, hidden ones too: the totals' days
        days = [x for x in a["total_days_7"] if not (firsts and x["day"] < min(firsts))]
        if days:
            mx = max([abs(x["money"]) for x in days if x["markets"]] or [0])
            rows = [("Day", "Money", "of pots", "Return", "Lost", "")]
            for x in days:
                if not x["markets"]:
                    rows.append((x["label"], "nothing settled"))
                    continue
                rows.append((x["label"], usd(x["money"]),
                             bs.pot_pct_txt(x["pot_pct"]) if x.get("pot_pct") is not None else "-",
                             bs.pct(x["return_pct"]) if x.get("return_pct") is not None else "-",
                             "%d/%d" % (x["lost"], x["markets"]), hbar(x["money"], mx, 4)))
            out += ["", "📅 <b>Last 7 days, every bot</b>", pre(table(rows, "lrrrrl")),
                    i_("of pots = share of all the pots when that day began · Return = on what the bets cost · "
                       "Lost = markets lost / settled")]
        tbl = bots_window_table(a, "last_7_days", "7 days")
        if tbl:
            out += ["", "📊 <b>Last 7 days, by bot</b>"] + tbl
        out += bots_avg_table(a)
        det = ["%s: <b>%s</b> (%s of the bank) · %d of %d closes lost" % (
            esc(bs.day_label(x)), esc(usd(v)), esc(pct(r)), lost, closes) for x, v, r, lost, closes in main]
        if det:
            mw = main_words(a.get("active"))
            out += ["", details(det, "🏦 %s (main account), day by day -- tap" % (mw[:1].upper() + mw[1:]))]
    else:
        rows, vals = [("Day", "Money", "% bank", "Lost", "")], []
        for x, v, r, lost, closes in main:
            vals.append(v)
            rows.append((x[5:], usd(v), pct(r), "%d/%d" % (lost, closes)))
        mx = max([abs(v) for v in vals] or [0])
        rows = [rows[0]] + [r + (hbar(v, mx, 4),) for r, v in zip(rows[1:], vals)]
        at_ = day_lines(d["all_time"], "All time", ctx.pp)
        out = [at_[0]] + at_[1:] + ["", "📅 <b>Last %d days</b> <i>(Kalshi's books, main account; ET days)</i>"
                                    % len(vals), pre(table(rows, "lrrrl")),
                                    i_("% bank = of the bank at the start of that day · Lost 1/25 = 1 losing close of 25")]
    vl = version_line(d["version"], ctx.pp)
    if vl:
        out += ["", vl]
    return Html("\n".join(out))


COMMAND = declare(Command(
    names=("/days",), section="money", order=20,
    help_line="/days — the last 7 days, every bot: each day's % of all pots, each bot's week",
    chart="days", load=load, render=render))
