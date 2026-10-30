"""/market -- how active sellers are, and which bot bought what at each of the last 8 closes; the pin bot's orders
today; the opportunity trend (health's supply lines) while it is fresh.

v-tg-rebuild step 9 (2026-10-30): Phone.text_market (+ Phone._pin_close_words, Phone._close_buys, used by /market
alone: copied here verbatim with ctx for self) as a command module (load + render), byte-identical (golden shadow).
Reads (load, in the old order): the Ledger's activity and closes, every other bot's buys from its own log
(botstats.fills_since; a failure costs those words only, logged), the pin bot's signals and today's fills, then
health() (a failure there drops the trend block silently, as before). No wall around the page.
"""
import traceback

import pinflat
from phone.command import Command, declare
from phone.html import Html, elines, esc, i_
from phone.log import log
from pindesk import Ledger, et_day, et_str, pct

SHOWN = 8


class _Raise:
    """health() raised in load: the trend block's own try in render raises it again there (and drops the block)."""

    def __init__(self, e):
        self.e = e


def load(ctx):
    led = ctx.ledger
    act = led.activity()
    closes = list(reversed(led.closes))[:SHOWN]
    n_closes = len(led.closes)
    others, unread = close_buys(ctx, closes)
    want = {s["tk"]: s["want"] for s in led.signals if s.get("tk") and s.get("want") in ("yes", "no")}
    pin = [pin_close_words(ctx, c, want) for c in closes]
    today = et_day(ctx.now())
    fs = Ledger.fill_stats(led.fills_on(today))
    try:
        h = ctx.health()
    except Exception as e:                                      # noqa: BLE001
        h = _Raise(e)
    return {"act": act, "closes": closes, "n_closes": n_closes, "others": others, "unread": unread, "pin": pin,
            "fs": fs, "health": h}


def render(d, ctx):
    act = d["act"]
    if act["recent"] is not None:
        out = ["🛒 <b>Sellers: %s</b> · <b>%.0f%%</b> of looks" % (esc(act["level"]), 100 * act["recent"]),
               "Last 4 quarter-hours: someone selling the winning side on <b>%.0f%%</b> of looks (quiet &lt; %.0f%%, "
               "typical %.0f%%, busy &gt; %.0f%%)."
               % (100 * act["recent"], 100 * act["p25"], 100 * act["median"], 100 * act["p75"])]
    else:
        out = ["🛒 <b>Sellers: %s</b>" % esc(act["level"])]
    out.append("")
    # 2026-10-26, the operator: "On /market it lists the last closes can you include which bot made the trades". The
    # close summaries and their count are the PIN BOT's own (its log; the coin race's orders are in the race's log),
    # so each close says 'pin bot ...', then every other bot's buys on the markets closing then, from its own log.
    closes, others, unread = d["closes"], d["others"], d["unread"]
    out.append("<b>Last %d closes</b> <i>(who bought, in contracts; sellers = share of the pin bot's looks with a "
               "seller)</i>" % min(SHOWN, d["n_closes"]))
    for c, pin in zip(closes, d["pin"]):
        share = Ledger.offer_share(c)
        parts = [pin] + others.get(int(c["close"]) if c["close"] else None, [])
        out.append("<b>%s</b> · sellers %s · %s" % (esc(et_str(c["close"]) if c["close"] else "?"),
                                                   esc(pct(share, False) if share is not None else "-"),
                                                   esc(" · ".join(parts))))
    if unread:
        out.append(i_("could not read %s, so its buys are not listed" % unread))
    fs = d["fs"]
    out.append("")
    out.append("<b>Pin bot today</b>: %d orders · %d filled · %d got nothing%s · wanted %s contracts, got <b>%s</b> "
               "(%s)." % (fs["orders"], fs["fills"], fs["zero"],
                          (" (%s)" % ctx.pp.pct_of(fs["zero"], fs["orders"])) if fs["orders"] else "",
                          "{:,.0f}".format(fs["asked"] or 0), "{:,.0f}".format(fs["contracts"] or 0),
                          esc(pct(fs["share"], False) if fs["share"] is not None else "-")))
    # IS THE OPPORTUNITY GOING AWAY. Same lines the desktop shows, from the same function, so the phone and the app
    # cannot drift apart. Read from health() rather than recomputed: it is already there.
    try:
        h = d["health"]
        if isinstance(h, _Raise):
            raise h.e
        sl = h.get("supply_lines") or []
        age = h.get("supply_age_d")
        if sl and age is not None and age > ctx.pp.SUPPLY_STALE_D:
            # 2026-10-23: the measurement stopped in September; a month-old trend is not shown as news
            out.append("")
            out.append(i_("The opportunity trend was last measured %.0f days ago, so it is left out." % age))
        elif sl:
            out.append("")
            out.append("📉 <b>IS THE OPPORTUNITY GOING AWAY?</b>")
            out += elines(sl)
            if age is not None:
                out.append(i_("(measured up to %.1f days ago)" % age))
    except Exception:                                   # noqa: BLE001
        pass
    return Html("\n".join(out))


# ---- from pinphone.Phone._pin_close_words / Phone._close_buys (/market alone uses them) -----------------------------
def pin_close_words(ctx, c, want):
    """What the PIN BOT did on one quarter-hour, from its own log (close summary, orders, hedges; `want` = {ticker:
    side} from its signals): 'pin bot bought 115 (NEAR NO)', '... + hedge 4 YES', 'pin bot LOST THE RACE: ordered 50,
    got 0 (someone bought it first)' or 'pin bot passed: <why>'. The count is Ledger.reason's: every pin order filled
    for that close. (Phone._pin_close_words, verbatim)"""
    led = ctx.ledger
    why = led.reason(c)
    if not why.startswith("BOUGHT"):
        if why.startswith("LOST THE RACE"):
            return "pin bot " + why
        return "pin bot passed: " + ("nothing met its rules" if why == "nothing passed" else why)
    _mkt_short, _f = ctx.pp._mkt_short, ctx.pp._f
    legs = []
    for o in led.orders:
        if o["close"] == c["close"] and o["filled"] > 0:
            side = want.get(o["tk"]) or (c.get("best_want") if o["tk"] == c.get("best_ticker") else None)
            k = " ".join(x for x in (_mkt_short(o["tk"]), str(side or "").upper()) if x)
            if k and k not in legs:
                legs.append(k)
    s = "pin bot bought %g%s" % (sum(o["filled"] for o in led.orders if o["close"] == c["close"]),
                                 (" (%s)" % ", ".join(legs)) if legs else "")
    hed = [g for g in led.hedges if g.get("kind") == "hedge" and str(g.get("status")) == "executed"
           and g.get("tk") and pinflat.close_epoch(g["tk"]) == c["close"]]
    if hed:
        s += " + hedge " + ", ".join(" ".join(x for x in ("%g" % _f(g.get("n")), str(g.get("side") or "").upper())
                                              if x) for g in hed)
    return s


def close_buys(ctx, closes):
    """({close epoch: ['coin race 2 (SOL YES)', 'forecaster 26 (ETH YES)', 'FX taker 3 markets x10']}, the bots whose
    log could not be read, in words, or None): what every bot but the pin bot bought on the markets closing at each
    of `closes`, from its own log (botstats.fills_since, back two hours past the oldest close). A failure costs these
    words only. (Phone._close_buys, verbatim)"""
    P = ctx.pp
    DESK_BOT = P.DESK_BOT
    cs = {int(c["close"]) for c in closes if c.get("close")}
    if not cs:
        return {}, None
    try:
        bs = ctx.bs()
        act = ctx.active()
        fl, unread = bs.fills_since(min(cs) - 2 * 3600, [b for b in bs.BOTS if b != DESK_BOT])
        names = [b for b in act if b != DESK_BOT] + ["earlier"]       # v-tg-active, as /fills
        for f in fl:
            if f["bot"] not in act:
                f["bot"] = "earlier"
        unread = {(b if b in act else "earlier"): w for b, w in unread.items()}
    except Exception:                                       # noqa: BLE001
        log(traceback.format_exc())
        return {}, "the other bots' logs"
    by = {}
    for f in fl:
        if f["close"] is not None and int(f["close"]) in cs:
            by.setdefault(int(f["close"]), {}).setdefault(f["bot"], []).append(f)
    out = {k: [P.buys_words(b, v[b]) for b in names if b in v] for k, v in by.items()}
    bad = [P.BOT_WORD.get(b, b) for b, why in unread.items() if why != "no log file found"]
    return out, (", ".join(bad) if bad else None)


COMMAND = declare(Command(
    names=("/market",), section="now", order=40,
    help_line="/market — how active sellers are, and which bot bought what at each of the last closes",
    chart="market", load=load, render=render))
