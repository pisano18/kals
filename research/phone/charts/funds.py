"""funds.py -- /bots /funds /bank /accounts: every RUNNING account's money over time (cash + open bets at cost), a
panel each, in its bot's colour; deposit-neutral since v-tg-neutral (rebuild step 12): only trading moves a line.

v-tg-rebuild step 8 (2026-10-30): moved verbatim out of tgcharts.py (chart_funds); the series is
botdata.series.account_series (was tgcharts._account_series).
"""
from botdata import series
from phone.charts.base import (BLUE, BOT_COLOUR, INK, POT_WHAT, account_name, annotate_change, etdt, fig_new, headline,
                               mark_last, money_axis, png, time_axis, usd)


def chart_funds(ctx):
    bs, c, prows, ok = ctx.bs_load()
    now = ctx.now
    drawn, stopped = [], []
    groups = {}
    for b in bs.BOTS:
        groups.setdefault(bs.bot_subs(b), []).append(b)
    for key in sorted(groups, key=lambda k: bs.SUBS.index(k[0]) if k[0] in bs.SUBS else len(bs.SUBS)):
        bots = groups[key]
        live = [b for b in bots if not series.bot_stopped(bs, b, prows, ok)]
        if not live:                                    # v-tg-active: an account no active bot runs is not named
            stopped.append(account_name(key).lower())
            continue
        pts, v, why, each = series.account_series(bs, c, key if len(key) > 1 else key[0], now, neutral=True)
        if pts:
            drawn.append((key, live, pts, v, why, each))
    for k, w in sorted((ctx.funds_what or {}).items()):
        if str(k) not in bs.SUBS:
            ws = " ".join(w.values()) if isinstance(w, dict) else str(w)
            if "stopped" in ws:
                stopped.append("subaccount %s" % k)
    if not drawn:
        return None
    # 10-30 (operator: "ladder chart is 0-800 ... only goes up a tiny tiny bit"): each panel is its own account on its
    # own scale -- the y axis zoomed to that account's money and the way it moves, the time axis to that account's own
    # span (a pot live for 5 days gets 5 days), its start, its end and the change between them written on it
    fig, axs = fig_new(len(drawn), 2.7 * len(drawn) + 1.0)
    total, whole = 0.0, True
    for ax, (key, live, pts, v, why, each) in zip(axs, drawn):
        X = [etdt(t) for t, _y in pts]
        Y = [y for _t, y in pts]
        col = BOT_COLOUR.get(live[0], BLUE)             # the account's (first) bot's colour, as on /stats (10-26)
        nowv = v if v is not None else Y[-1]
        total += nowv
        whole = whole and v is not None
        ax.plot(X, Y, color=col, lw=2.0, zorder=3)
        money_axis(ax, Y + [nowv], kind="balance", xs=X, room_top=0.12)
        ax.fill_between(X, Y, min(Y + [nowv]), color=col, alpha=0.07, lw=0)       # to the panel's own low, never $0
        time_axis(ax, X[0], X[-1])
        mark_last(ax, X[-1], nowv, usd(nowv, False), color=col)
        parts = (" + ".join("%s (%s) %s" % (POT_WHAT.get(k, "subaccount " + k), k, usd(x, False))
                            for k, x in zip(key, each)),) if each and None not in each else ()   # each pot's part
        annotate_change(ax, X, Y[:-1] + [nowv], extra=parts, ends=True)
        ax.set_title("%s · %s: %s%s" % (account_name(key), " + ".join(bs.SPEC[b]["label"].lower() for b in live),
                                        usd(nowv, False), " now" if v is not None else " (from the books)"),
                     color=INK, fontsize=11)
    headline(fig, "Every running account: %s%s" % ("" if whole else "about ", usd(total, False)))
    # v-tg-neutral (step 12, the operator: "Robinhood ... a withdrawal or deposit doesn't spike or change it at all"):
    # each line is the account now minus the trading after each hour (botdata.series.trading_only)
    cap = ("Each running account's money over time, %s: the account now (cash + open bets at cost) minus the trading "
           "after each moment -- every settlement on Kalshi's books, fees in (botstats) -- so money moved in or out, or "
           "between pots, never moves a line; only trading does. The dot is the account now.%s"
           % (series.NEUTRAL_NOTE, (" Not drawn (no bot runs there now): " + "; ".join(stopped) + ".") if stopped else ""))
    return png(fig), cap
