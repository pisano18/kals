"""days.py -- /days /brief /summary (and /stats' main-account fallback): every ET day's $ bars, % of the bank bars (each
with its 7-day and 30-day average lines) and the running total ($ and % of the money put in).

v-tg-rebuild step 8 (2026-10-30): moved verbatim out of tgcharts.py (chart_days, chart_stats_main, _bars_by_day). The
main account's markets, window_stats and FIRST_LIVE_DAY come from the ChartCtx (they were pp.*); day_minus is
botdata.clock's copy of pinphone's.
"""
from pindesk import Ledger, et_day, et_day_start
from botdata import series
from botdata.clock import prev_day
from phone.charts.base import (AVG30, BLUE, MUTED, ORANGE, WINDOW_DAYS, date_axis, etdt, fig_new, headline, legend,
                               money_axis, note, pct_of_axis, pct_ticks, pctx, png, ups_downs, usd, zero_line)

AVG_DAYS, LONG_DAYS = series.AVG_DAYS, series.LONG_DAYS


def bars_by_day(ax, days, vals, fmt_last):
    xs = [etdt(et_day_start(d) + 43200) for d in days]
    ax.bar(xs, vals, width=0.78, color=ups_downs(vals), zorder=3)
    zero_line(ax)
    if xs:
        note(ax, xs[-1], vals[-1], fmt_last(vals[-1]), dy=6 if vals[-1] >= 0 else -6)
    return xs


def chart_days(ctx, src):
    led, now = ctx.ledger, ctx.now
    today = et_day(now)
    winrate = None
    pct_words = "% of the bank each day (the bank at the start of that ET day)"

    def bank(d):
        return led.bank_at(et_day_start(d))
    if src == "days":
        # 2026-10-26: /days' words cover EVERY bot (operator: "add the percentage anywhere it applied"), so its
        # picture does too -- each day's money over all pots, as % of what all the pots held when it began
        # (botstats.day_pot, the /days table's own rule). The main account alone when botstats cannot be read.
        try:
            bs, pctx_, mrows, missing = series.all_day_markets(*ctx.bs_args())
        except Exception:                               # noqa: BLE001
            bs, mrows, missing = None, [], ["all"]
        if bs is not None and mrows and not missing:
            per = {}
            for d_, _t, v_, _b in mrows:
                per[d_] = per.get(d_, 0.0) + v_
            rows, d_ = [], min(per)
            while d_ <= today:
                rows.append((d_, per.get(d_, 0.0)))
                d_ = bs.shift_day(d_, 1)
            dep = bs.pot_for(pctx_, None, "all_time")[0]
            tot = sum(per.values())
            head = "Every bot, all time %s%s" % (usd(tot), (" (%s on the %s put in)" % (pctx(tot / dep, 2), usd(dep, False)))
                                                if dep else "")
            src_words = "Kalshi's books, every pot (every bot), every ET day"
            pct_words = "% of all pots each day (what they held when that ET day began)"

            def bank(d):                                # noqa: F811 -- all pots, not the main account
                return bs.day_pot(pctx_, None, d)
        else:
            rows = series.ledger_days(led)
            if not rows:
                return None
            s = Ledger.summary(led.settled)
            dep = led.deposited()
            head = "All time %s%s" % (usd(s["net"]), (" (%s on the %s put in)" % (pctx(s["net"] / dep, 2), usd(dep, False))) if dep else "")
            src_words = "Kalshi's books, main account (%s), every ET day it traded" % ctx.words_main()
    else:
        fl = ctx.first_live_day
        if fl is None:
            raise AttributeError("ChartCtx.first_live_day is not set (pinphone.FIRST_LIVE_DAY)")
        ms = [m for m in ctx.main_account_markets().values() if m["day"] >= fl]
        if not ms:
            return None
        life = ctx.window_stats(ms, {})
        dep = led.deposited()
        by = {}
        for m in ms:
            by.setdefault(m["day"], []).append(m)
        days, d = [], fl
        while d <= today:
            days.append(d)
            d = ctx.day_minus(d, -1)
        rows = [(d, sum(m["pnl"] for m in by.get(d, []))) for d in days]
        winrate = []
        for d in days:
            st = ctx.window_stats(by[d], {}) if by.get(d) else None
            winrate.append((d, st["win_c"] if st else None, st["breakeven_c"] if st else None))
        head = "Lifetime %s%s" % (usd(life["net"]), (" (%s on %s risked)" % (pctx(life["net"] / life["risked"], 2),
                                                                         usd(life["risked"], False))) if life["risked"] else "")
        src_words = "Kalshi's books, main account, since %s (the /stats source)" % fl
    cum, runs = 0.0, []
    for _d, v in rows:                                  # the running total counts EVERY day ...
        cum += v
        runs.append(cum)
    cut = et_day(now - WINDOW_DAYS * 86400)             # ... the picture shows the last WINDOW_DAYS of them
    keep = [i for i, (d, _v) in enumerate(rows) if d >= cut] or list(range(len(rows)))
    if winrate is not None:
        winrate = [winrate[i] for i in keep]
    days = [rows[i][0] for i in keep]
    nets = [rows[i][1] for i in keep]
    run = [runs[i] for i in keep]
    lo = days[0]                                        # the % averages reach LONG_DAYS-1 days left of the picture
    for _ in range(LONG_DAYS - 1):
        lo = prev_day(lo)
    b0 = {d: bank(d) for d, _v in rows if d >= lo}
    b0s = [b0[d] for d in days]
    pct_by = {d: ((100.0 * v / b0[d]) if b0[d] else 0.0) for d, v in rows if d >= lo}
    avg_net = series.avg_by_day(dict(rows), days)
    avg_pct = series.avg_by_day(pct_by, days)
    a30_net = series.avg_by_day(dict(rows), days, LONG_DAYS)
    a30_pct = series.avg_by_day(pct_by, days, LONG_DAYS)
    n = 4 if winrate is not None else 3
    fig, axs = fig_new(n, 3.0 * n + 1.2, sharex=True)
    xs = bars_by_day(axs[0], days, nets, usd)
    # the average line stops at yesterday: today's bar is half a day, and the last point then equals /today's
    # "average of the last 7 days"
    an = [avg_net.get(d) if d < today else None for d in days]
    ap = [avg_pct.get(d) if d < today else None for d in days]
    lan = next((a for a in reversed(an) if a is not None), None)
    lap = next((a for a in reversed(ap) if a is not None), None)
    # the 30-day line (10-29), the same rule; only where it averages more days than the 7-day one (a young record's
    # first week would draw the two on top of each other)
    first_d = rows[0][0]

    def n_back(d, n):
        k, e = 0, d
        while k < n and e >= first_d:
            k += 1
            e = prev_day(e)
        return k
    a30n = [a30_net.get(d) if d < today and n_back(d, LONG_DAYS) > AVG_DAYS else None for d in days]
    a30p = [a30_pct.get(d) if d < today and n_back(d, LONG_DAYS) > AVG_DAYS else None for d in days]
    l30n = next((a for a in reversed(a30n) if a is not None), None)
    l30p = next((a for a in reversed(a30p) if a is not None), None)
    if lan is not None:
        axs[0].plot([x for x, a in zip(xs, an) if a is not None], [a for a in an if a is not None], color=ORANGE,
                    lw=1.8, ls="--", zorder=4, label="%d-day average, to yesterday (%s a day)" % (AVG_DAYS, usd(lan)))
        if l30n is not None:
            axs[0].plot([x for x, a in zip(xs, a30n) if a is not None], [a for a in a30n if a is not None], color=AVG30,
                        lw=1.6, ls="-.", zorder=4,
                        label="%d-day average, to yesterday (%s a day)" % (min(LONG_DAYS, n_back(prev_day(today), LONG_DAYS)), usd(l30n)))
        legend(axs[0])
    money_axis(axs[0])
    axs[0].set_title("$ each ET day")
    pc = [(100.0 * v / b) if b else 0.0 for v, b in zip(nets, b0s)]
    bars_by_day(axs[1], days, pc, lambda v: "%+.2f%%" % v)
    if lap is not None:
        axs[1].plot([x for x, a in zip(xs, ap) if a is not None], [a for a in ap if a is not None], color=ORANGE,
                    lw=1.8, ls="--", zorder=4, label="%d-day average, to yesterday (%+.2f%% a day)" % (AVG_DAYS, lap))
        if l30p is not None:
            axs[1].plot([x for x, a in zip(xs, a30p) if a is not None], [a for a in a30p if a is not None], color=AVG30,
                        lw=1.6, ls="-.", zorder=4,
                        label="%d-day average, to yesterday (%+.2f%% a day)" % (min(LONG_DAYS, n_back(prev_day(today), LONG_DAYS)), l30p))
        legend(axs[1])
    pct_ticks(axs[1])
    axs[1].set_title(pct_words)
    ax = axs[2]
    ax.plot(xs, run, color=BLUE, lw=2.2, zorder=3, marker="o", ms=3.5)
    ax.fill_between(xs, run, 0, color=BLUE, alpha=0.08, lw=0)
    zero_line(ax)
    money_axis(ax)
    note(ax, xs[-1], run[-1], usd(run[-1]), dx=-4, ha="right")
    pct_of_axis(ax, dep, "%% of the %s put in" % usd(dep, False) if dep else "")
    ax.set_title("Running total")
    if winrate is not None:
        ax = axs[3]
        wx = [x for x, (_d, w, _b) in zip(xs, winrate) if w is not None]
        wv = [100.0 * w for _d, w, _b in winrate if w is not None]
        bv = [100.0 * b for _d, w, b in winrate if w is not None and b is not None]
        bx = [x for x, (_d, w, b) in zip(xs, winrate) if w is not None and b is not None]
        ax.plot(wx, wv, color=BLUE, lw=2.0, marker="o", ms=3.5, label="won % of markets", zorder=3)
        ax.plot(bx, bv, color=MUTED, lw=1.6, ls="--", label="break-even %", zorder=2)
        w7x, w7v = [], []                               # won % of every market in that day and the 6 before it
        for x, d in zip(xs, days):
            span, e = [], d
            for _ in range(AVG_DAYS):
                if e < fl:
                    break
                span.extend(by.get(e, []))
                e = prev_day(e)
            st = ctx.window_stats(span, {}) if span else None
            if st and st.get("win_c") is not None:
                w7x.append(x)
                w7v.append(100.0 * st["win_c"])
        if w7v:
            ax.plot(w7x, w7v, color=ORANGE, lw=1.8, ls="--", label="won %% over %d days (%.1f%% now)" % (AVG_DAYS, w7v[-1]),
                    zorder=2)
        pct_ticks(ax, signed=False)
        ax.set_title("Each day: won % of markets vs the break-even it needed")
        legend(ax)
    date_axis(axs[-1])
    headline(fig, head)
    cap = ("%s: %s; the last %d days drawn, the running total counts all of them. Top: each day's money; then the "
           "same day as %% of what it began with (orange dashes: the average of that day and the %d before it, "
           "drawn to yesterday; slate dash-dots: of that day and the %d before it); "
           "then the running total (right axis: %% of the money put in)%s." % (
               "/stats" if src == "stats" else "/days", src_words, len(days), AVG_DAYS - 1, LONG_DAYS - 1,
               "; bottom: won % of markets each day against the break-even win rate its prices needed"
               if winrate is not None else ""))
    return png(fig), cap


def chart_stats_main(ctx):
    """The old /stats picture: the main account only (pin bot + coin race, pinphone.markets_from since the first live
    day), with each day's won % of markets against its break-even. Drawn when botstats cannot be read."""
    return chart_days(ctx, "stats")
