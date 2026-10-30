"""stats.py -- /stats: every bot's money from botstats, one colour a bot.

v-tg-rebuild step 8 (2026-10-30): moved verbatim out of tgcharts.py (chart_stats); data from botdata.series.
"""
from botdata import series
from phone.charts.base import (AVG30, BOT_COLOUR, BOT_ORDER, BOT_SHORT, GREY, INK, INK2, SURF, WINDOW_DAYS, etdt,
                               fig_new, headline, legend, mark_empty, mark_last, money_axis, note, pct_axis, pct_of_axis,
                               pctx, png, time_axis, ups_downs, usd)
from phone.charts.days import chart_stats_main

AVG_DAYS, LONG_DAYS = series.AVG_DAYS, series.LONG_DAYS


def chart_stats(ctx):
    """/stats (operator 10-26: "The command slash stats graph shows only pins bank. Perhaps every bank in different
    colors would be better."): EVERY bot's money from botstats (Kalshi's books, every pot), one colour a bot
    (BOT_COLOUR, the same as /losses, /bots and each bot's page):
      top     $ each ET day stacked by bot, gains up and losses down; the dark dot is the day's net over every bot;
      middle  that net as % of what all the pots held when the day began (botstats.day_pot, the /bots and /days base;
              a day whose pots are unknown is left out, never guessed), with its 7-day average;
      bottom  the running total: every bot together (dark, thick) and each big bot; then the bots too small to see
              on that scale, on their own; each key carries each bot's all-time $ (a stopped bot says so).
    The won % against break-even panel of the old picture is not drawn: the bots buy at very different prices (race
    legs near 50c, the pin bot and the ladder near 96-98c), so one won % over all of them follows the mix of bots
    that day, not how well any one did; each bot's own is on its page (/pin /fc /ladder /race /fx).
    The main account's picture (chart_stats_main) when botstats cannot be read."""
    try:
        bs, _c, prows, ok, pctx_, ms, missing = series.all_markets(*ctx.bs_args())
    except Exception:                                   # noqa: BLE001 (no botstats: the main account's picture)
        return chart_stats_main(ctx) if ctx.ledger is not None else None
    if not ms:
        return chart_stats_main(ctx) if ctx.ledger is not None else None
    now = ctx.now
    today = bs.et_day(now)
    names = {n for n, _m in ms}
    bots = [b for b in BOT_ORDER if b in names] + sorted(names - set(BOT_ORDER))
    per = {}                                            # (ET day, bot) -> that bot's money that day
    for n, m in ms:
        per[(m["day"], n)] = per.get((m["day"], n), 0.0) + m["money"]
    first = min(m["day"] for _n, m in ms)
    days_all, d = [], first
    while d <= today:
        days_all.append(d)
        d = bs.shift_day(d, 1)
    cut = bs.et_day(now - WINDOW_DAYS * 86400)          # the picture shows the last WINDOW_DAYS; totals count all
    days = [d for d in days_all if d >= cut] or days_all
    acc = {b: 0.0 for b in bots}
    run = {b: {} for b in bots}
    for d in days_all:
        for b in bots:
            acc[b] += per.get((d, b), 0.0)
            run[b][d] = acc[b]
    life = {b: acc[b] for b in bots}
    total = sum(life.values())
    born = {b: min(m["day"] for n, m in ms if n == b) for b in bots}
    stopped = {b for b in bots if b in bs.SPEC and series.bot_stopped(bs, b, prows, ok)}

    def name(b):
        return BOT_SHORT.get(b, b) + (" (stopped)" if b in stopped else "")
    xs = [etdt(bs.day_start(d) + 43200) for d in days]
    nets = [sum(per.get((d, b), 0.0) for b in bots) for d in days]
    allv = [sum(run[b][d] for b in bots) for d in days]
    # a bot whose running total is small next to every bot's would be a flat line at $0: it gets a panel of its
    # own scale under the big ones
    big_span = max([abs(v) for v in allv] + [1.0])
    reach = {b: max([abs(run[b][d]) for d in days if d >= born[b]] + [0.0]) for b in bots}
    big = [b for b in bots if reach[b] >= 0.3 * big_span]
    small = [b for b in bots if b not in big and any(d >= born[b] for d in days)]
    n = 4 if small else 3
    fig, axs = fig_new(n, 14.4 if small else 11.6, ratios=[1.2, 0.8, 1.0, 1.0][:n], sharex=True)

    # top: each day's money, stacked by bot
    ax = axs[0]
    up, dn = [0.0] * len(days), [0.0] * len(days)
    for b in bots:
        v = [per.get((d, b), 0.0) for d in days]
        if not any(abs(x) > 0.004 for x in v):
            continue
        pv = [max(0.0, x) for x in v]
        nv = [min(0.0, x) for x in v]
        ax.bar(xs, pv, width=0.8, bottom=up, color=BOT_COLOUR.get(b, GREY), edgecolor=SURF, linewidth=0.5, zorder=3,
               label=BOT_SHORT.get(b, b))
        ax.bar(xs, nv, width=0.8, bottom=dn, color=BOT_COLOUR.get(b, GREY), edgecolor=SURF, linewidth=0.5, zorder=3)
        up = [a + x for a, x in zip(up, pv)]
        dn = [a + x for a, x in zip(dn, nv)]
    ax.scatter(xs, nets, s=16, color=INK, edgecolor=SURF, linewidth=0.8, zorder=5, label="net, every bot")
    money_axis(ax, up + dn + nets, room_top=0.24)       # headroom: the key, two rows
    note(ax, xs[-1], nets[-1], usd(nets[-1]), dy=8 if nets[-1] >= 0 else -8, ha="right", dx=4)
    ax.set_title("$ each ET day, by bot: gains up, losses down (dot = the day's net)")
    ax.legend(loc="upper left", fontsize=8.5, ncol=4, frameon=True, facecolor=SURF, edgecolor="none", framealpha=0.92,
              columnspacing=1.0, handlelength=1.2)

    # middle: the day's net as % of all pots when it began
    ax = axs[1]
    pot = {}
    lo_d = days[0]
    for _ in range(LONG_DAYS - 1):                      # the 30-day line reaches 29 days left of the picture
        lo_d = bs.shift_day(lo_d, -1)
    for d in days_all:
        if d >= lo_d:
            pot[d] = bs.day_pot(pctx_, None, d) if not missing else None
    pct = {d: 100.0 * sum(per.get((d, b), 0.0) for b in bots) / pot[d] for d in pot if pot[d]}
    px = [x for x, d in zip(xs, days) if d in pct]
    pv = [pct[d] for d in days if d in pct]
    if pv:
        ax.bar(px, pv, width=0.8, color=ups_downs(pv), zorder=3)
        note(ax, px[-1], pv[-1], "%+.2f%%" % pv[-1], dy=6 if pv[-1] >= 0 else -6, ha="right", dx=4)
        for n_, col, ls in ((AVG_DAYS, INK2, "--"), (LONG_DAYS, AVG30, "-.")):
            ax_x, ax_v = [], []                         # the average of that day and the n-1 before it (known days)
            for x, d in zip(xs, days):
                if d >= today:
                    continue
                span_d, e = [], d
                for _ in range(n_):
                    if e in pct:
                        span_d.append(pct[e])
                    e = bs.shift_day(e, -1)
                if span_d and (n_ == AVG_DAYS or len(span_d) > AVG_DAYS):
                    ax_x.append(x)
                    ax_v.append(sum(span_d) / len(span_d))
            if ax_v:
                ax.plot(ax_x, ax_v, color=col, lw=1.6, ls=ls, zorder=4,
                        label="%d-day average, to yesterday (%+.2f%% a day)" % (n_, ax_v[-1]))
        if ax.get_lines():
            legend(ax)
        pct_axis(ax, pv + [y for ln in ax.get_lines() for y in ln.get_ydata()], room_top=0.1)
    else:
        mark_empty(ax, "what the pots held could not be worked out")
    ax.set_title("% of all pots each day (what they held when that ET day began)")

    # the running totals: every bot (dark) and the big bots; then the small ones on their own scale
    def lines(ax, which):
        vals = []
        for b in which:
            bx = [x for x, d in zip(xs, days) if d >= born[b]]
            by = [run[b][d] for d in days if d >= born[b]]
            if bx:
                ax.plot(bx, by, color=BOT_COLOUR.get(b, GREY), lw=2.0, zorder=3, label="%s %s" % (name(b), usd(life[b])))
                vals += by
        return vals
    ax = axs[2]
    vals = lines(ax, big)
    ax.plot(xs, allv, color=INK, lw=2.8, zorder=4, label="Every bot %s" % usd(total))
    money_axis(ax, allv + vals, xs=xs, room_top=0.1)
    mark_last(ax, xs[-1], allv[-1], usd(allv[-1]), color=INK)
    dep = bs.pot_for(pctx_, None, "all_time")[0] if not missing else None
    pct_of_axis(ax, dep, "%% of the %s put in" % usd(dep, False) if dep else "")
    bign = ["the " + BOT_SHORT.get(b, b).lower() for b in big]
    ax.set_title("Running total: every bot together (dark)%s" % (
        (" and " + (", ".join(bign[:-1]) + " and " if len(bign) > 1 else "") + bign[-1]) if bign else ""))
    h, lab = ax.get_legend_handles_labels()
    ax.legend(h[-1:] + h[:-1], lab[-1:] + lab[:-1], loc="upper left", fontsize=9, frameon=True,
              facecolor=SURF, edgecolor="none", framealpha=0.92, handlelength=1.4)
    if small:
        ax = axs[3]
        vals = lines(ax, small)
        money_axis(ax, vals, room_top=0.36)                      # headroom: the key
        ax.set_title("Running total of the other bots, on their own scale")
        ax.legend(loc="upper left", fontsize=8.5, ncol=2, frameon=True, facecolor=SURF, edgecolor="none",
                  framealpha=0.92, columnspacing=1.0, handlelength=1.4)
    time_axis(axs[-1], xs[0], xs[-1], pad_days=0.6)
    headline(fig, "Every bot, all time %s%s" % (usd(total), (" (%s on the %s put in)" % (pctx(total / dep, 1), usd(dep, False)))
                                                if dep else ""))
    cap = ("/stats: every bot, every pot (Kalshi's books through botstats), one colour a bot; the last %d days drawn, "
           "the totals count every day since %s. Top: each ET day's money by bot, gains up and losses down; the dark "
           "dot is the day's net over every bot. Middle: that net as %% of what all the pots held when the day began "
           "(a day whose pots are unknown is left out); dashes: its %d-day average, to yesterday; slate dash-dots: its "
           "%d-day one. Bottom: each bot's running total and every bot together. All time: %s.%s" % (
               len(days), first, AVG_DAYS, LONG_DAYS, ", ".join("%s %s" % (name(b), usd(life[b])) for b in bots),
               (" PARTIAL: leaves out %s (Kalshi could not be read)." % ", ".join(missing)) if missing else ""))
    return png(fig), cap
