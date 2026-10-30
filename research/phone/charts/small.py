"""small.py -- the pin bot's own pictures, from its own log (each says "pin bot"): /hedges (what its insurance legs
made), /status (the main account's bank, last 7 days), /fills /bets (today's orders), /market (sellers' share of its
looks against the record's quartiles).

v-tg-rebuild step 8 (2026-10-30): moved verbatim out of tgcharts.py (chart_hedges, chart_status, chart_fills,
chart_market). /hedges' markets come from the ChartCtx (ctx.main_account_markets: was markets_of(ctx) over pp).
"""
from pindesk import Ledger, et_day, et_day_start
from botdata import series
from phone.charts.base import (BLUE, BOT_COLOUR, GREY, INK, INK2, MUTED, SURF, date_axis, etdt, fig_new, headline,
                               legend, money_axis, mpl, note, png, usd, zero_line)


def chart_hedges(ctx):
    led = ctx.ledger
    hm = sorted((m for m in ctx.main_account_markets().values() if m["hedged"] and m["hedge_pnl"] is not None and m["close"]),
                key=lambda m: m["close"])
    ho = [g for g in led.hedge_outcomes() if g.get("t") and g.get("net") is not None]
    if not hm and not ho:
        return None
    fig, axs = fig_new(2, 7.6, sharex=True)
    ax = axs[0]
    tot = 0.0
    if hm:
        run, cum = [], 0.0
        for m in hm:
            cum += m["hedge_pnl"]
            run.append(cum)
        tot = cum
        X = [etdt(m["close"]) for m in hm]
        ax.step(X, run, where="post", color=BLUE, lw=2.0, zorder=3)
        note(ax, X[-1], run[-1], usd(run[-1]), dx=-4, ha="right")
    zero_line(ax)
    money_axis(ax)
    ax.set_title("What the insurance legs made on their own, running total")
    ax = axs[1]
    for verdict, col, lab in (("WASTED", GREY, "WASTED (the bet held)"), ("NEEDED", BLUE, "NEEDED (the bet lost)"),
                              (None, INK, "not settled")):           # not orange: the coin race's colour
        g = [x for x in ho if x.get("verdict") == verdict]
        if g:
            ax.scatter([etdt(x["t"]) for x in g], [x["net"] for x in g], s=30, color=col, edgecolor=SURF, linewidth=1.0,
                       zorder=4, label="%s: %d" % (lab, len(g)))
    zero_line(ax)
    money_axis(ax)
    if ho:
        legend(ax)
    ax.set_title("Each hedged bet: what the whole market netted")
    date_axis(axs[-1])
    headline(fig, "Pin bot insurance: %s all time on %d hedged markets" % (usd(tot), len(hm)))
    cap = ("The pin bot's insurance. Top: each hedged market's other side, on its own (pinphone.markets_from's "
           "hedge_pnl, Kalshi's books, main account), added up. Bottom: every executed hedge (the pin bot's records) "
           "and its market's net, by verdict.")
    return png(fig), cap


def chart_status(ctx):
    """/status: the main account's bank over the last 7 days, hour by hour, deposit-neutral (v-tg-neutral, rebuild step
    12; the operator: "Robinhood ... a withdrawal or deposit doesn't spike or change it at all"): the bank now (pindesk's
    bank_at, the figure /status shows) minus the settlements after each hour (botdata.series.trading_only), so only
    trading moves the line; a deposit, withdrawal or transfer is marked where it happened and moves nothing."""
    led, now = ctx.ledger, ctx.now
    t0 = now - 7 * 86400
    grid = list(range(int(t0), int(now), 3600)) + [now]
    end = led.bank_at(now)
    if end is None:
        return None
    pts = series.trading_only(grid, [(s_["t"], s_["pnl"]) for s_ in led.settled if s_["t"]], end)
    if len(pts) < 2:
        return None
    fig, (ax,) = fig_new(1, 5.4)
    X = [etdt(g) for g, _b in pts]
    Y = [b for _g, b in pts]
    ax.plot(X, Y, color=BLUE, lw=2.0, zorder=3)
    mv = [e for e in led.external if e.get("t") and e["t"] >= t0 and abs(float(e.get("amount") or 0)) >= Ledger.TRANSFER_MIN]
    for e in mv:
        ax.axvline(etdt(e["t"]), color=INK2, lw=1.2, ls=":", zorder=2)
    if mv:
        ax.plot([], [], color=INK2, lw=1.2, ls=":", label="money moved in or out (left out of the line)")
    note(ax, X[-1], Y[-1], usd(Y[-1], False), dx=-4, ha="right")
    money_axis(ax, signed=False)
    date_axis(ax, 7)
    ax.set_title("Main account (%s), hour by hour, last 7 days (%s)" % (ctx.words_main(), series.NEUTRAL_NOTE))
    if mv:
        legend(ax)
    headline(fig, "Bank %s · trading, last 7 days %s" % (usd(Y[-1], False), usd(Y[-1] - Y[0])))
    cap = ("The main account's bank (" + ctx.words_main() + ") over the last 7 days, " + series.NEUTRAL_NOTE + ": the "
           "bank now (the pin bot's last bank read plus every settlement since -- pindesk's bank_at, the figure /status "
           "shows) minus the trading after each hour, so only trading moves the line -- a deposit, withdrawal or "
           "transfer never does (dotted lines mark where one happened).")
    return png(fig), cap


def chart_fills(ctx):
    led, now = ctx.ledger, ctx.now
    day = et_day(now)
    rows = sorted((o for o in led.orders if o.get("t") and et_day(o["t"]) == day), key=lambda o: o["t"])
    if not rows:
        return None

    def px(o, *keys):
        for k in keys:
            try:
                v = float(o.get(k))
                if v > 0:
                    return 100.0 * v
            except (TypeError, ValueError):
                pass
        return None
    got = [(o, px(o, "price", "ask_seen")) for o in rows if float(o.get("filled") or 0) > 0]
    zero = [(o, px(o, "ask_seen", "limit_sent", "price")) for o in rows if float(o.get("filled") or 0) <= 0]
    fig, (ax,) = fig_new(1, 5.6)
    g = [(o, p) for o, p in got if p is not None]
    if g:
        ax.scatter([etdt(o["t"]) for o, _p in g], [p for _o, p in g],
                   s=[min(220, 18 + 4 * float(o.get("filled") or 0)) for o, _p in g], color=BOT_COLOUR["pin"], alpha=0.85,
                   edgecolor=SURF, linewidth=1.0, zorder=4, label="filled: %d (dot size = contracts)" % len(got))
    z = [(o, p) for o, p in zero if p is not None]
    if z:                                               # dark, not orange: orange is the coin race's colour (10-26)
        ax.scatter([etdt(o["t"]) for o, _p in z], [p for _o, p in z], marker="x", s=40, color=INK, linewidth=1.8,
                   zorder=5, label="filled nothing: %d (at the price it saw)" % len(zero))
    d0 = et_day_start(day)
    ax.set_xlim(etdt(d0), etdt(d0 + 86400))
    date_axis(ax, 1)
    T = mpl()["ticker"]
    ax.yaxis.set_major_locator(T.MaxNLocator(nbins=7, steps=[1, 2, 5, 10]))
    ax.yaxis.set_major_formatter(T.FuncFormatter(lambda v, _p: ("%.1fc" if abs(ax.get_ylim()[1] - ax.get_ylim()[0]) < 6
                                                               else "%.0fc") % v))
    ax.set_title("Each order today: the price, by time sent (ET) · got %g of %g contracts" % (
        sum(float(o.get("filled") or 0) for o in rows), sum(float(o.get("asked") or 0) for o in rows)))
    legend(ax)
    headline(fig, "Pin bot orders today: %d · %d filled · %d filled nothing" % (len(rows), len(got), len(zero)))
    cap = ("Today's orders from the pin bot's own records (main account): what it paid, and the ones that lost the "
           "race. Pin bot only.")
    return png(fig), cap


def chart_market(ctx):
    led = ctx.ledger
    cl = [c for c in led.closes[-48:] if c.get("close")]
    pts = [(c, Ledger.offer_share(c)) for c in cl]
    pts = [(c, s) for c, s in pts if s is not None]
    if len(pts) < 2:
        return None
    act = led.activity()
    fig, (ax,) = fig_new(1, 5.6)
    X = [etdt(c["close"]) for c, _s in pts]
    Y = [100.0 * s for _c, s in pts]
    ax.plot(X, Y, color=BLUE, lw=1.8, zorder=3)
    f = [(x, y) for (c, _s), x, y in zip(pts, X, Y) if c.get("fired")]
    if f:
        ax.scatter([x for x, _y in f], [y for _x, y in f], s=34, color=BLUE, edgecolor=SURF, linewidth=1.2, zorder=4,
                   label="a quarter-hour the pin bot bought")
    for k, ls, lab in (("p25", ":", "quiet below"), ("median", "--", "typical"), ("p75", ":", "busy above")):
        if act.get(k) is not None:
            ax.axhline(100.0 * act[k], color=MUTED, lw=1.1, ls=ls, zorder=2)
            note(ax, X[0], 100.0 * act[k], "%s %.0f%%" % (lab, 100.0 * act[k]), dx=2, dy=2, ha="left", color=INK2,
                 weight="normal", size=8.5)
    ax.yaxis.set_major_formatter(mpl()["ticker"].FuncFormatter(lambda v, _p: "%.0f%%" % v))
    date_axis(ax, (pts[-1][0]["close"] - pts[0][0]["close"]) / 86400.0)
    ax.set_title("Share of looks with someone selling the winning side, each quarter-hour")
    if f:
        legend(ax)
    headline(fig, "Sellers: %s%s" % (act["level"], (" · %.0f%% of looks lately" % (100 * act["recent"])) if act.get("recent") is not None else ""))
    cap = ("The last %d quarter-hours from the pin bot's close summaries (as /market reads them); the dashed and dotted "
           "lines are the whole record's typical and quartile levels." % len(pts))
    return png(fig), cap
