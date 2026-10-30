"""funds.py -- /bots /funds /bank /accounts: every RUNNING account's money over time (cash + open bets at cost), a
panel each, in its bot's colour.

v-tg-rebuild step 8 (2026-10-30): moved verbatim out of tgcharts.py (chart_funds); the series is
botdata.series.account_series (was tgcharts._account_series).
"""
from botdata import series
from phone.charts.base import (BLUE, BOT_COLOUR, GRID, INK, INK2, POT_WHAT, SURF, account_name, date_axis, etdt,
                               fig_new, headline, money_axis, note, png, usd)


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
        pts, v, why, each = series.account_series(bs, c, key if len(key) > 1 else key[0], now)
        if pts:
            drawn.append((key, live, pts, v, why, each))
    for k, w in sorted((ctx.funds_what or {}).items()):
        if str(k) not in bs.SUBS:
            ws = " ".join(w.values()) if isinstance(w, dict) else str(w)
            if "stopped" in ws:
                stopped.append("subaccount %s" % k)
    if not drawn:
        return None
    fig, axs = fig_new(len(drawn), 2.7 * len(drawn) + 1.0, sharex=True)
    total, whole = 0.0, True
    for ax, (key, live, pts, v, why, each) in zip(axs, drawn):
        X = [etdt(t) for t, _y in pts]
        Y = [y for _t, y in pts]
        col = BOT_COLOUR.get(live[0], BLUE)             # the account's (first) bot's colour, as on /stats (10-26)
        ax.plot(X, Y, color=col, lw=2.0, zorder=3)
        ax.fill_between(X, Y, 0, color=col, alpha=0.08, lw=0)
        nowv = v if v is not None else Y[-1]
        total += nowv
        whole = whole and v is not None
        ax.scatter([X[-1]], [nowv], s=50, color=col, edgecolor=SURF, linewidth=1.5, zorder=5)
        note(ax, X[-1], nowv, usd(nowv, False), dx=-4, ha="right")
        lo = min(Y + [nowv])
        ax.set_ylim(bottom=min(0.0, lo))
        money_axis(ax, signed=False)
        if each:                                        # each pot's part, inside the panel (the title has no room)
            ax.text(0.01, 0.95, " + ".join("%s (%s) %s" % (POT_WHAT.get(k, "subaccount " + k), k, usd(x, False))
                                           for k, x in zip(key, each)),
                    transform=ax.transAxes, va="top", ha="left", fontsize=9.5, color=INK2, zorder=6,
                    bbox=dict(facecolor=SURF, edgecolor=GRID, boxstyle="round,pad=0.3"))
        ax.set_title("%s · %s: %s%s" % (account_name(key), " + ".join(bs.SPEC[b]["label"].lower() for b in live),
                                        usd(nowv, False), " now" if v is not None else " (from the books)"),
                     color=INK, fontsize=11)
    date_axis(axs[-1])
    headline(fig, "Every running account: %s%s" % ("" if whole else "about ", usd(total, False)))
    cap = ("Each running account's money over time = cash + open bets at cost, worked forward from Kalshi's own "
           "deposits, transfers and settlements (botstats); the dot is the account now.%s"
           % ((" Not drawn (no bot runs there now): " + "; ".join(stopped) + ".") if stopped else ""))
    return png(fig), cap
