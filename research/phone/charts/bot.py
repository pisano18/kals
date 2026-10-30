"""bot.py -- one bot's page picture (/pin /fc /ladder /weather /fx /jb /race /racestats): today's pace against
yesterday and its average days, its running total, and its win rate over its last ROLL markets (races for the race)
against break-even.

v-tg-rebuild step 8 (2026-10-30): moved verbatim out of tgcharts.py (chart_bot, draw_pace, _at_h). Per-bot facts from
the registry: the pace goal (Bot.goal_pct: the ladder's 1% a day; was `1.0 if name == "ladder"`) and the unit a bot
settles in (Bot.unit: the race's 'leg'; was `"leg" if name == "race"`). The race's win rate is per RACE (its legs
grouped by event, botdata.series.race_rows): drawn for the bot whose unit is a leg.
"""
import bots
from botdata import series
from phone.charts.base import (AVG30, AXIS, BLUE, BOT_COLOUR, DOWN, GREY, MUTED, ORANGE, ROLL, SURF, WINDOW_DAYS,
                               date_axis, etdt, fig_new, headline, legend, money_axis, mpl, note, pct_of_axis,
                               pct_ticks, pctx, png, roll, usd, zero_line)

PACE_DAYS, LONG_DAYS = series.PACE_DAYS, series.LONG_DAYS
_at_h = series.at_hour


def draw_pace(ax, pc, now_h, goal=None):
    """Today (blue, to now) over yesterday (grey), the 7-day average day (orange dashes) and the 30-day one (slate
    dash-dots, when it counts more days than the 7), as % of the bank --
    or in dollars when the bank could not be read (pc['unit'] == '$')."""
    T = mpl()["ticker"]
    dollars = pc.get("unit") == "$"

    def f(v):
        return usd(v) if dollars else pctx(v / 100.0, 2)
    if pc["avg7"]:
        ax.plot([h for h, _ in pc["avg7"]], [v for _, v in pc["avg7"]], color=ORANGE, lw=1.8, ls="--", zorder=2,
                label="average of the last %d days (%s by now)" % (pc["n7"], f(_at_h(pc["avg7"], now_h))))
    if pc.get("avg30"):
        ax.plot([h for h, _ in pc["avg30"]], [v for _, v in pc["avg30"]], color=AVG30, lw=1.6, ls="-.", zorder=2,
                label="average of the last %d days (%s by now)" % (pc["n30"], f(_at_h(pc["avg30"], now_h))))
    if pc["yesterday"]:
        ax.step([h for h, _ in pc["yesterday"]], [v for _, v in pc["yesterday"]], where="post", color=GREY, lw=1.6,
                zorder=2, label="yesterday %s (%s by now)" % (f(pc["yesterday"][-1][1]), f(_at_h(pc["yesterday"], now_h))))
    if pc["today"]:
        ax.step([h for h, _ in pc["today"]], [v for _, v in pc["today"]], where="post", color=BLUE, lw=2.4, zorder=3,
                label="today %s" % f(pc["today"][-1][1]))
        note(ax, pc["today"][-1][0], pc["today"][-1][1], f(pc["today"][-1][1]), dx=-4, ha="right")
    if dollars:
        goal = None                                       # the goal is a % of the bank: nothing to draw it against
    if goal is not None:
        ax.plot([0, 24], [0, goal], color=MUTED, lw=1.0, ls=":", zorder=1, label="goal %s a day, spread evenly" % pctx(goal / 100.0, 1, False))
    ax.axvline(now_h, color=AXIS, lw=1.0, ls=":", zorder=1)
    zero_line(ax)
    ax.set_xlim(0, 24)
    ax.xaxis.set_major_locator(T.FixedLocator(list(range(0, 25, 3))))
    ax.xaxis.set_major_formatter(T.FuncFormatter(lambda v, _p: "%d %s" % ((int(v) % 12) or 12, "AM" if int(v) % 24 < 12 else "PM")))
    if dollars:
        money_axis(ax)
        ax.set_title("Today's pace in dollars, by ET clock (its bank could not be read for the %)")
    else:
        ax.yaxis.set_major_formatter(T.FuncFormatter(lambda v, _p: "%+.2f%%" % v if abs(v) >= 0.005 else "0%"))
        ax.set_title("Today's pace, % of its bank, by ET clock (dotted line = now)")
    legend(ax)


def chart_bot(ctx, name):
    bs, c, prows, ok = ctx.bs_load()
    if name not in bs.SPEC or series.bot_stopped(bs, name, prows, ok):
        return None
    now = ctx.now
    today = bs.et_day(now)
    pctx_ = bs.pot_context(c, today)
    blk = bs._money_block(c, name, today, pctx_)
    if not blk.get("ok") or not blk.get("markets"):
        return None
    reg = bots.get(name)
    unit = reg.unit if reg is not None else "market"    # 'leg' for the race (bots/race.py)
    ms = sorted((m for m in blk["markets"] if m["t"] is not None), key=lambda m: m["t"])
    subs = bs.bot_subs(name)                            # the FX taker: 5 + 4, one picture
    sub = subs if len(subs) > 1 else subs[0]
    label = bs.SPEC[name]["label"]
    fig, axs3 = fig_new(3, 11.0, ratios=[1.15, 1.25, 1])
    try:
        pc = series.pace_curves(bs, pctx_, sub, ms, today, now)
        draw_pace(axs3[0], pc, (now - bs.day_start(today)) / 3600.0, goal=reg.goal_pct if reg is not None else None)
    except Exception as e:                              # noqa: BLE001 -- the pace panel never costs the rest
        axs3[0].set_title("Today's pace: could not be drawn (%s)" % str(e)[:60])
    axs = axs3[1:]
    axs[0].sharex(axs[1])
    ax = axs[0]
    run, cum = [], 0.0
    for m in ms:                                        # the running total counts every market ...
        cum += m["money"]
        run.append(cum)
    cut = now - WINDOW_DAYS * 86400                     # ... the picture shows the last WINDOW_DAYS
    i0 = next((i for i, m in enumerate(ms) if m["t"] >= cut), len(ms) - 1)
    Xall = [etdt(m["t"]) for m in ms]
    X, R, W = Xall[i0:], run[i0:], ms[i0:]
    ax.step(X, R, where="post", color=BOT_COLOUR.get(name, BLUE), lw=2.0, zorder=3)    # its /stats colour (10-26)
    lx = [x for x, m in zip(X, W) if m["money"] < -0.004]
    ly = [y for y, m in zip(R, W) if m["money"] < -0.004]
    run = R
    if lx:
        ax.scatter(lx, ly, s=22, color=DOWN, edgecolor=SURF, linewidth=1.0, zorder=4, label="a losing %s" % unit)
        legend(ax)
    zero_line(ax)
    money_axis(ax)
    note(ax, X[-1], run[-1], usd(run[-1]), dx=-4, ha="right")
    base, _k, _why = bs.pot_for(pctx_, sub, "all_time")
    pct_of_axis(ax, base, (("%% of the %s's %s put in" % (bs.SUB_NAME[sub], usd(base, False))) if len(subs) == 1 else
                           ("%% of the %s put into %s" % (usd(base, False), bs.sub_name(sub)))) if base else "")
    ax.set_title("Running total, market by market (Kalshi's books, %s)" % bs.sub_name(sub))
    ax = axs[1]
    # a rolling rate is drawn only where its window is full (n markets / races behind it)
    if unit == "leg":                                   # the race: a race = the legs of one event
        races = series.race_rows(bs, c, name)
        n = min(ROLL, max(5, len(races) // 4))
        rr = roll([100.0 if w else 0.0 for _t, _v, w, _tie in races], n)
        j0 = max(n - 1, next((i for i, r in enumerate(races) if r[0] >= cut), len(races)))
        ax.plot([etdt(r[0]) for r in races[j0:]], rr[j0:], color=BOT_COLOUR.get(name, BLUE), lw=2.0,
                label="won %% of the last %d races" % n, zorder=3)
        what = "races (a tie counts as not won)"
    else:
        n = min(ROLL, max(5, len(ms) // 4))
        j0 = max(n - 1, i0)
        ax.plot(Xall[j0:], roll([100.0 if m["money"] > 0.004 else 0.0 for m in ms], n)[j0:], color=BOT_COLOUR.get(name, BLUE),
                lw=2.0, label="won %% of the last %d markets" % n, zorder=3)
        pe = [((m["put_in"] + m["fees"]) / m["contracts"], 1.0) if m["contracts"] > 0 else (0.0, 0.0) for m in ms]
        acc = []
        sv = sw = 0.0
        for i, (v, w) in enumerate(pe):
            sv += v
            sw += w
            if i >= n:
                sv -= pe[i - n][0]
                sw -= pe[i - n][1]
            acc.append(100.0 * sv / sw if sw else None)
        ax.plot([x for x, a in zip(Xall[j0:], acc[j0:]) if a is not None], [a for a in acc[j0:] if a is not None],
                color=MUTED, lw=1.6, ls="--", label="break-even % (what its prices needed)", zorder=2)
        what = "markets"
    pct_ticks(ax, signed=False)
    ax.set_title("Win rate over time (%s)" % what)
    legend(ax)
    date_axis(axs[-1])
    at, td = blk.get("all_time") or {}, blk.get("today") or {}
    headline(fig, "%s: all time %s%s · today %s" % (
        label, usd(at.get("money")), (" (%+.1f%% of its bank)" % at["pot_pct"]) if at.get("pot_pct") is not None else "",
        usd(td.get("money") or 0.0)))
    cap = ("%s: today's pace against yesterday and its average day of the last %d and %d days (slate dash-dots, "
           "drawn once it has more days than the %d), every settled %s from Kalshi's books (botstats, %s), its running total and its win rate "
           "over time (the last %d days drawn; the total counts all). Right axis: the same dollars as %% of the money put "
           "into that account." % (label, PACE_DAYS, LONG_DAYS, PACE_DAYS, unit, bs.sub_name(sub),
                                   WINDOW_DAYS))
    return png(fig), cap
