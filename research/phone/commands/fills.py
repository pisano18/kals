"""/fills (/bets) -- the pin bot's orders today: what filled, what it paid, how late (zero-fill orders SHOWN: an order
that filled nothing is a race lost); then every other bot's fills that day, each line naming its bot.

v-tg-rebuild step 9, lane D2 (2026-10-30): Phone.text_fills + Phone._other_fills_html as a command module (load +
render), byte-identical (golden shadow). No wall around the whole (as before); the other bots' part keeps its own: a
failure there costs only those lines ('The other bots' fills could not be read.'), the traceback logged.
"""
import traceback

from phone.command import Command, declare
from phone.html import Html, esc, i_, pre, table
from phone.log import log
from phone.render.botcards import BOT_WORD, DESK_BOT, _day_long, _nof
from botdata.fmt import cnt as _cnt                    # == pinphone._cnt
from pindesk import coin, et_day, et_day_start, pct

SHOWN = 8                                              # the other bots' newest fills listed (_other_fills_html's shown)


def load(ctx):
    """{'day', 'rows': the pin bot's orders that ET day (time order), 'other': the other bots' part or None (failed)}.
    The reads in the old order: the clock, the Ledger's orders, then botstats (active bots, fills_since), the clock."""
    day = et_day(ctx.now())
    rows = [o for o in ctx.ledger.orders
            if o.get("t") and et_day(o["t"]) == day]
    return {"day": day, "rows": rows, "other": _other(ctx, day)}


def _other(ctx, day):
    """Phone._other_fills_html's reads: {'fl': that day's fills, 'unread', 'names', 'when'}; None when botstats failed
    (logged)."""
    try:
        bs = ctx.bs()
        act = ctx.active()
        fl, unread = bs.fills_since(et_day_start(day), [b for b in bs.BOTS if b != DESK_BOT])
        # v-tg-active: a paused or retired bot's fills (there should be none) are 'earlier bots', never its name
        names = [b for b in act if b != DESK_BOT] + ["earlier"]
        for f in fl:
            if f["bot"] not in act:
                f["bot"] = "earlier"
        unread = {(b if b in act else "earlier"): w for b, w in unread.items()}
    except Exception:                                       # noqa: BLE001
        log(traceback.format_exc())
        return None
    fl = [f for f in fl if f["t"] is not None and et_day(f["t"]) == day]
    when = "today" if day == et_day(ctx.now()) else _day_long(day)
    return {"fl": fl, "unread": unread, "names": names, "when": when}


def other_lines(o, hm, shown=SHOWN):
    """Phone._other_fills_html's lines from _other's data (Html lines)."""
    if o is None:
        return ["", i_("The other bots' fills could not be read.")]
    fl, unread, names = o["fl"], o["unread"], o["names"]
    L = ["", "🧾 <b>Other bots' fills %s: %d</b> <i>(each bot's own log)</i>" % (esc(o["when"]), len(fl))]
    if fl:
        per = []
        for b in names:
            mine = [f for f in fl if f["bot"] == b]
            if mine:
                per.append("%s %s, %s contracts" % (BOT_WORD.get(b, b), _nof(len(mine), "fill"),
                                                    _cnt(sum(f["contracts"] for f in mine))))
        L.append(esc(" · ".join(per)))
        for f in list(reversed(fl))[:shown]:
            side = " ".join(x for x in ("sold" if f["act"] == "sold" else "", (f["side"] or "").upper()) if x)
            what = f["what"][5:] if f["bot"] == "race" and f["what"].startswith("race ") else f["what"]
            L.append(esc("%s · %s · %s%s x%s%s" % (
                hm(f["t"]), BOT_WORD.get(f["bot"], f["bot"]), what, (" " + side) if side else "",
                _cnt(f["contracts"]), (" · %.1fc" % (100.0 * f["price"])) if f["price"] else "")))
        if len(fl) > shown:
            L.append(i_("the newest %d of %d, newest first" % (shown, len(fl))))
    else:
        L.append("None.")
    bad = [BOT_WORD.get(b, b) for b, why in unread.items() if why != "no log file found"]
    if bad:
        L.append(i_("could not read: %s" % ", ".join(bad)))
    return L


def render(d, ctx):
    hm, pct_of = ctx.pp.hm, ctx.pp.pct_of
    day, rows = d["day"], d["rows"]
    other = other_lines(d["other"], hm)
    if not rows:
        return Html("\n".join(["No pin bot orders today (%s)." % esc(day)] + other))
    rows.sort(key=lambda o: o["t"])
    tbl = [("Time", "Coin", "Got/asked", "Paid", "Left")]
    nf = got = asked = 0.0
    zero = 0
    for o in rows:
        f = float(o.get("filled") or 0)
        a = float(o.get("asked") or 0)
        got += f
        asked += a
        if f <= 0:
            zero += 1
        else:
            nf += 1
        px = o.get("price") or o.get("ask_seen")
        tau = o.get("tau")
        tbl.append((hm(o["t"]), coin(o.get("tk") or ""), ("%g/%g" % (f, a)) if a else ("%g" % f),
                    ("%.1fc" % (100 * float(px))) if px else "-",
                    ("%ss" % tau) if tau is not None else "(oil)"))
    out = ["🧾 <b>Pin bot orders today: %d</b> · %d filled · %d filled nothing%s" % (
        len(rows), int(nf), zero, (" (%s)" % pct_of(zero, len(rows))) if rows else ""),
        i_("%s ET · Left = seconds before the close when it was sent" % day),
        pre(table(tbl, "llrrr")),
        "Asked %g contracts, got <b>%g</b> (<b>%s</b>). %d orders: %d filled, %d lost the race." % (
            asked, got, esc(pct(got / asked, False) if asked else "-"), len(rows), int(nf), zero)]
    return Html("\n".join(out + other))


COMMAND = declare(Command(
    names=("/fills", "/bets"), section="now", order=30,
    help_line="/fills — the pin bot's orders today: filled, price paid, seconds out; then every other bot's fills, each "
              "named",
    chart="fills", load=load, render=render))
