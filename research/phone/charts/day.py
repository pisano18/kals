"""day.py -- /today /yesterday: every bot's running total market by market on the ET clock.

v-tg-rebuild step 8 (2026-10-30): moved verbatim out of tgcharts.py (chart_day, chart_day_main); the data come from
botdata.series, the ctx is a ChartCtx.
"""
from pindesk import Ledger, et_day, et_day_start
from botdata import series
from phone.charts.base import (AVG30, DOWN, BLUE, GREY, INK, ORANGE, SURF, BOT_SHORT, etdt, fig_new, headline, legend,
                               mark_last, money_axis, pct_of_axis, pctx, place_notes, png, time_axis, usd, wrap)

AVG_DAYS, LONG_DAYS = series.AVG_DAYS, series.LONG_DAYS
LOSS_NAMES = 8                          # /today: the losing markets named on the picture (the biggest, when more)


def chart_day(ctx, which):
    """/today /yesterday: EVERY bot's money that ET day (operator 10-23: "/today doesn't show the right total it
    says 11.22 right now it's really 24.85" -- the old picture was the main account only). Falls back to the main
    account's own ledger (chart_day_main) when botstats cannot be read."""
    try:
        bs, pctx_, rows, missing = series.all_day_markets(*ctx.bs_args())
    except Exception:                                   # noqa: BLE001 -- no botstats: the main account's picture
        return chart_day_main(ctx, which) if ctx.ledger is not None else None
    now = ctx.now
    today = bs.et_day(now)
    day = today if which == "today" else bs.shift_day(today, -1)
    first = min((r[0] for r in rows), default=None)

    def curve(d):
        t0 = bs.day_start(d)
        t1 = bs.day_start(bs.shift_day(d, 1))
        pts, cum, lost = [], 0.0, []
        for dd, t, v, b in rows:
            if dd == d:
                cum += v
                pts.append((min(max(t, t0), t1) - t0, cum))
                if v < -0.004:
                    lost.append((min(max(t, t0), t1) - t0, cum, v, b))
        return pts, lost
    pts, lost = curve(day)
    if not pts:
        return None
    ms = [r for r in rows if r[0] == day]
    net = sum(r[2] for r in ms)
    won = sum(1 for r in ms if r[2] > 0.004)
    d0 = bs.day_start(day)
    b0 = bs.day_pot(pctx_, None, day) if not missing else None
    fig, (ax,) = fig_new(1, 5.6)
    label = "Today" if day == today else "Yesterday"
    end = min(now, d0 + 86400) if day == today else d0 + 86400
    X = [etdt(d0)] + [etdt(d0 + s) for s, _c in pts] + [etdt(max(end, d0 + pts[-1][0]))]
    Y = [0.0] + [c for _s, c in pts] + [pts[-1][1]]
    if day == today:
        ypts, _yl = curve(bs.shift_day(day, -1))
        if ypts:
            ax.step([etdt(d0)] + [etdt(d0 + s) for s, _c in ypts] + [etdt(d0 + 86400)],
                    [0.0] + [c for _s, c in ypts] + [ypts[-1][1]], where="post", color=GREY, lw=1.6,
                    label="Yesterday %s" % usd(ypts[-1][1]), zorder=2)

    def at(c, g):
        v = 0.0
        for s, y in c:
            if s > g:
                break
            v = y
        return v
    n7 = 0
    for n_, col, ls in ((AVG_DAYS, ORANGE, "--"), (LONG_DAYS, AVG30, "-.")):
        ds, d = [], day
        for _ in range(n_):
            d = bs.shift_day(d, -1)
            if first is not None and d >= first:
                ds.append(d)
        if not ds or len(ds) <= n7:                     # the 30-day line only when it counts more days than the 7
            continue
        n7 = n7 or len(ds)
        cs = [curve(x)[0] for x in ds]
        avg = [(g, sum(at(c, g) for c in cs) / len(cs)) for g in range(0, 86400 + 1, 900)]
        if day == today:
            by_now = at(avg, now - d0)
            alab = "Average of the last %d days %s (%s by now)" % (len(ds), usd(avg[-1][1]), usd(by_now))
        else:
            alab = "Average of the %d days before %s" % (len(ds), usd(avg[-1][1]))
        ax.plot([etdt(d0 + g) for g, _v in avg], [v for _g, v in avg], color=col, lw=1.8 if col == ORANGE else 1.6,
                ls=ls, label=alab, zorder=2)
    # every bot together is the dark line (/stats' 'all bots'); blue is the pin bot's own colour now (10-26)
    ax.step(X, Y, where="post", color=INK, lw=2.2, label="%s %s" % (label, usd(net)), zorder=3)
    named = sorted(sorted(lost, key=lambda x: x[2])[:LOSS_NAMES], key=lambda x: x[0])
    if lost:
        ax.scatter([etdt(d0 + s) for s, _c, _v, _b in lost], [c for _s, c, _v, _b in lost], s=46, color=DOWN,
                   edgecolor=SURF, linewidth=1.5, zorder=5,
                   label="a losing market, named by bot" if len(named) == len(lost)
                   else "a losing market (the %d biggest named)" % len(named))
    ys = [y for ln in ax.get_lines() for y in ln.get_ydata()]
    lo_all, hi_all = min(ys + [0.0]), max(ys + [0.0])
    low = min([c for _s, c, _v, _b in named] or [hi_all])
    # room under the lowest named loss for its name, when it sits at the bottom
    money_axis(ax, ys, room_bottom=0.12 if low - lo_all < 0.06 * ((hi_all - lo_all) or 1.0) else 0.0, room_top=0.1)
    time_axis(ax, d0, d0 + 86400, clock=True)
    mark_last(ax, X[-1], Y[-1], usd(Y[-1]), color=INK)
    pct_of_axis(ax, b0, "%% of all pots at midnight ET (%s)" % usd(b0, False) if b0 else "")
    each = {}                                           # each bot's money that day: who made the day
    for _d, _t, v, b in ms:
        each[b] = each.get(b, 0.0) + v
    by_bot = " · ".join("%s %s" % (BOT_SHORT.get(b, b), usd(v)) for b, v in sorted(each.items(), key=lambda kv: kv[1]))
    ax.set_title("Every bot, running total market by market (ET)\n%s" % wrap("By bot: " + by_bot, 78))
    legend(ax)
    place_notes(ax, [(etdt(d0 + s), c, "%s %s" % (BOT_SHORT.get(b, b), usd(v))) for s, c, v, b in named])
    r = (net / b0) if b0 else None
    headline(fig, "%s %s%s · %d of %d markets won" % (label, usd(net), (" (%s of all pots)" % pctx(r, 2)) if r is not None else "",
                                                    won, len(ms)))
    cap = ("%s: every bot's money market by market (every pot, Kalshi's books; a paused or retired bot's markets are "
           "'earlier bots'; a market counts on the ET day it closed). By bot: %s. Red dots: a losing market, named by its bot. Orange "
           "dashes: the average day of the %d days before, on the same clock; slate dash-dots: of the %d days before. "
           "Right axis: the same dollars as %% of all pots at the start of the ET day.%s" % (
               label, by_bot, AVG_DAYS, LONG_DAYS, (" PARTIAL: leaves out %s (Kalshi could not be read)." % ", ".join(missing)) if missing else ""))
    return png(fig), cap


def chart_day_main(ctx, which):
    led, now = ctx.ledger, ctx.now
    today = et_day(now)
    day = today if which == "today" else et_day(now - 86400)
    rows = led.settled_on(day)
    pts = series.closes_cum(rows)
    if not pts:
        return None
    s = Ledger.summary(rows)
    d0 = et_day_start(day)
    b0 = led.bank_at(d0)
    fig, (ax,) = fig_new(1, 5.6)
    label = "Today" if day == today else "Yesterday"
    end = min(now, d0 + 86400) if day == today else d0 + 86400
    X = [etdt(d0)] + [etdt(k) for k, _c, _v in pts] + [etdt(max(end, pts[-1][0]))]
    Y = [0.0] + [c for _k, c, _v in pts] + [pts[-1][1]]
    if day == today:
        y = et_day(now - 86400)
        ypts = series.closes_cum(led.settled_on(y))
        if ypts:
            sh = d0 - et_day_start(y)
            ax.step([etdt(d0)] + [etdt(k + sh) for k, _c, _v in ypts] + [etdt(d0 + 86400)],
                    [0.0] + [c for _k, c, _v in ypts] + [ypts[-1][1]], where="post", color=GREY, lw=1.6,
                    label="Yesterday %s" % usd(ypts[-1][1]), zorder=2)
    n7 = 0
    for n_, col, ls in ((AVG_DAYS, ORANGE, "--"), (LONG_DAYS, AVG30, "-.")):
        avg, navg = series.day_avg(led, day, n_)
        if not avg or navg <= n7:                       # the 30-day line only when it counts more days than the 7
            continue
        n7 = n7 or navg
        if day == today:
            by_now = avg[0][1]
            for g, v in avg:
                if g > now - d0:
                    break
                by_now = v
            alab = "Average of the last %d days %s (%s by now)" % (navg, usd(avg[-1][1]), usd(by_now))
        else:
            alab = "Average of the %d days before %s" % (navg, usd(avg[-1][1]))
        ax.plot([etdt(d0 + g) for g, _v in avg], [v for _g, v in avg], color=col, lw=1.8 if col == ORANGE else 1.6,
                ls=ls, label=alab, zorder=2)
    ax.step(X, Y, where="post", color=BLUE, lw=2.2, label="%s %s" % (label, usd(s["net"])), zorder=3)
    lost = [(k, c) for k, c, v in pts if v < 0]
    if lost:
        ax.scatter([etdt(k) for k, _c in lost], [c for _k, c in lost], s=46, color=DOWN, edgecolor=SURF,
                   linewidth=1.5, zorder=5, label="a losing close")
    money_axis(ax, [y for ln in ax.get_lines() for y in ln.get_ydata()], room_top=0.1)
    time_axis(ax, d0, d0 + 86400, clock=True)
    mark_last(ax, X[-1], Y[-1], usd(Y[-1]), color=BLUE)
    pct_of_axis(ax, b0, "%% of the %s bank at midnight ET" % usd(b0, False) if b0 else "")
    ax.set_title("Running total, close by close (ET)")
    legend(ax)
    r = (s["net"] / b0) if b0 else None
    headline(fig, "%s %s%s · %d of %d closes won" % (label, usd(s["net"]), (" (%s of the bank)" % pctx(r, 2)) if r is not None else "",
                                                   s["won"], s["closes"]))
    cap = ("%s: the day's money close by close, Kalshi's books, main account (%s). Orange dashes: the "
           "average day of the %d days before, on the same clock; slate dash-dots: of the %d days before. Right axis: "
           "the same dollars as %% of the bank at the start of the ET day." % (label, ctx.words_main(), AVG_DAYS, LONG_DAYS))
    return png(fig), cap
