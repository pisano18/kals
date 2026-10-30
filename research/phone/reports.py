"""phone/reports.py -- the weekly and monthly reports (v-tg-rebuild step 12, lane Q, 2026-10-30): every bot running now
plus the earlier bots on one line, the money and its % of each pot and of all pots, the best and worst day, the losses,
and the same against the week / month before (the average day too, so a span still running compares fairly).

Sent by the monitor (phone/monitor.py: Sunday 8 PM ET, this Mon..Sun week; the 1st of the month 8 AM ET, the month
just ended) and shown on demand by /week and /month (phone/commands/week.py). The data is botdata/period.py's, from one
botstats read (the /bots source: Kalshi's books, every pot).
"""
import time

import bots as _bots
from botdata import period as _period
from botdata.fmt import pot_pct_txt, usd
from phone.html import Html, esc, i_, pre, table


def day_words(day):
    """'2026-10-25' -> 'Sun Oct 25'."""
    try:
        return time.strftime("%a %b %d", time.strptime(day, "%Y-%m-%d")).replace(" 0", " ")
    except (TypeError, ValueError):
        return str(day)


def month_words(day):
    """'2026-10-01' -> 'October'."""
    try:
        return time.strftime("%B", time.strptime(day, "%Y-%m-%d"))
    except (TypeError, ValueError):
        return str(day)


def short(key):
    b = _bots.get(key)
    if b is not None:
        return b.short
    return _bots.NOT_BOT_SHORT.get(key, str(key))


def _pp(x):
    return pot_pct_txt(x) if x is not None else "-"


def build(bs, now, kind, which="this", getter=None, procs=None):
    """The report's data: kind 'week' or 'month', which 'this' (the span running now) or 'last' (the one before)."""
    today = bs.et_day(now)
    (a, b), (pa, pb) = (_period.weeks if kind == "week" else _period.months)(today, which)
    d = _period.report(bs, now, a, b, pa, pb, getter, procs)
    d.update(kind=kind, which=which)
    return d


def titles(d):
    """(headline word, the span's name, the one before's name, the column word for it)."""
    t, p = d["this"], d["prev"]
    running = d["today"] <= t["last"]
    if d["kind"] == "week":
        return (("THIS WEEK" if running else "WEEK"), "%s to %s" % (day_words(t["first"]), day_words(t["last"])),
                "the week before", "Before")
    return ((month_words(t["first"]).upper() + (" SO FAR" if running else "")), "%s to %s" % (
        day_words(t["first"]), day_words(min(t["last"], d["today"]))), month_words(p["first"]), month_words(
        p["first"])[:3])


def report_html(d):
    """The report as the phone shows it."""
    t, p = d["this"], d["prev"]
    head, span_name, prev_name, col = titles(d)
    icon = "📅" if d["kind"] == "week" else "🗓"
    nd = _period.days_in(t["first"], t["last"], d["today"])
    npv = _period.days_in(p["first"], p["last"], d["today"])
    out = ["%s <b>%s %s%s</b> · %s%s" % (
        icon, esc(head), esc(usd(t["money"])), (" (%s of all pots)" % esc(pot_pct_txt(t["pot_pct"])))
        if t["pot_pct"] is not None else "", esc(span_name), " (today so far)" if d["today"] <= t["last"] else "")]
    a_now = t["money"] / nd if nd else None
    a_then = p["money"] / npv if npv else None
    if p["markets"]:
        better = (a_now - a_then) if (a_now is not None and a_then is not None) else None
        out.append("vs %s: %s%s · a day %s now, %s then%s" % (
            esc(prev_name), esc(usd(p["money"])), (" (%s)" % esc(pot_pct_txt(p["pot_pct"])))
            if p["pot_pct"] is not None else "", esc(usd(a_now)), esc(usd(a_then)),
            (" (<b>%s a day %s</b>)" % (esc(usd(abs(better)).lstrip("+")), "better" if better >= 0 else "worse"))
            if better is not None else ""))
    else:
        out.append(i_("Nothing settled in %s to compare with." % prev_name))
    if not t["markets"]:
        out.append(i_("Nothing has settled in it yet."))
    keys = [k for k in d["order"] if k in t["by_bot"] or k in p["by_bot"]]
    if keys:
        rows = [("Bot", "Money", "% pot", col, "Lost")]
        for k in keys:
            b, pb = t["by_bot"].get(k), p["by_bot"].get(k)
            rows.append((short(k), usd(b["money"]) if b else "-", _pp(b["pot_pct"]) if b else "-",
                         usd(pb["money"]) if pb else "-", ("%d" % b["lost"]) if b else "-"))
        rows.append(("All bots", usd(t["money"]), _pp(t["pot_pct"]), usd(p["money"]), "%d" % t["lost"]))
        out.append(pre(table(rows)))
        out.append(i_("%% pot: of what the pot held when %s began, plus money moved in since. Lost: markets lost."
                      % ("the week" if d["kind"] == "week" else "the month")))
    if t["best"]:
        out.append("📈 Best day <b>%s %s</b> · 📉 worst day <b>%s %s</b> (of %d day%s with a market)" % (
            esc(day_words(t["best"][0])), esc(usd(t["best"][1])), esc(day_words(t["worst_day"][0])),
            esc(usd(t["worst_day"][1])), len(t["days"]), "" if len(t["days"]) == 1 else "s"))
    if t["lost"]:
        w = t["worst"]
        out.append("🔴 Losses: %d market%s lost, %s in all%s; the worst: %s %s on %s, <b>%s</b>" % (
            t["lost"], "" if t["lost"] == 1 else "s", esc(usd(t["money_lost"])), (
                " (%d the %s before)" % (p["lost"], "week" if d["kind"] == "week" else "month")),
            esc(short(w["bot"])), esc(w["what"]), esc(day_words(w["day"])), esc(usd(w["money"]))))
    elif t["markets"]:
        out.append("🟢 No market lost.")
    if d["missing"]:
        out.append(i_("Not counted (their pots could not be read now): %s." % ", ".join(short(k) for k in d["missing"])))
    out.append(i_("/week · /month (add 'last' for the one before) · /days for day by day"))
    return Html("\n".join(out))


__all__ = ["build", "report_html", "titles", "day_words", "month_words"]
