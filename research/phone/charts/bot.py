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
                               annotate_change, bot_headline, clock_axis, etdt, fig_new, free_corner, mark_empty,
                               mark_last,
                               money_axis, note, pct_axis, pct_of_axis, pctx, png, ref, roll, time_axis, usd,
                               value_axis)

PACE_DAYS, LONG_DAYS = series.PACE_DAYS, series.LONG_DAYS
_at_h = series.at_hour


def stop_refs(name, now, today_dist=None):
    """The bot's own stop lines (its registry stop_gauges: the jump band's stop line and day stop, the ladder's day-stop
    rail, the pin bot's loss abort), as how far each is below where the bot stands now: [(gauge, dollars to go)].
    A day's stop goes on the pace panel, the others on the running total. Nothing when the log cannot be read."""
    try:
        from botdata import watch
        return [(g, g.money - g.line) for g in watch.gauges(name, now) if not g.tripped]
    except Exception:                                   # noqa: BLE001 -- a stop line never costs the picture
        return []


def _is_day(g):
    return g.key == "day" or g.counted == "settled today"


def draw_pace(ax, pc, now_h, goal=None, stops=(), base=None):
    """Today (blue, to now) over yesterday (grey), the 7-day average day (orange dashes) and the 30-day one (slate
    dash-dots, when it counts more days than the 7), as % of the bank --
    or in dollars when the bank could not be read (pc['unit'] == '$')."""
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
    ys = [v for k in ("avg7", "avg30", "yesterday", "today") for _h, v in (pc.get(k) or [])]
    if goal is not None:
        ys += [0.0, goal]
    refs = []
    now_v = pc["today"][-1][1] if pc["today"] else 0.0
    for g, dist in stops:                               # a day stop: where today's line would trip it
        if _is_day(g) and (dollars or base):
            y = now_v - (dist if dollars else 100.0 * dist / base)
            refs.append(ref(y, "%s: %s below now" % (g.what, usd(dist, False)), color=DOWN, ls=":", optional=True))
    lim = value_axis(ax, ys, unit="$" if dollars else "%", kind="pnl", xs=[h for h, _v in (pc["today"] or [])],
                     refs=refs, room_top=0.32)
    clock_axis(ax)
    if dollars:
        ax.set_title("Money made today in dollars, by ET clock (its bank could not be read for the %)")
    else:
        ax.set_title("Today's pace, % of its bank, by ET clock (dotted line = now)")
    ax.legend(loc="best", frameon=True, facecolor=SURF, edgecolor="none", framealpha=0.92)
    return lim


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
    stops = stop_refs(name, now)
    try:
        pc = series.pace_curves(bs, pctx_, sub, ms, today, now)
        draw_pace(axs3[0], pc, (now - bs.day_start(today)) / 3600.0, goal=reg.goal_pct if reg is not None else None,
                  stops=[(g, d) for g, d in stops if _is_day(g)], base=series.day_base(bs, pctx_, sub, today))
    except Exception as e:                              # noqa: BLE001 -- the pace panel never costs the rest
        axs3[0].set_title("Today's pace: could not be drawn (%s)" % str(e)[:60])
        mark_empty(axs3[0], "")
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
    col = BOT_COLOUR.get(name, BLUE)                    # its /stats colour (10-26)
    # 10-30: the line starts where the total stood before the first market drawn ($0 for a young bot), so the change
    # written on it is the change over what is drawn
    X0, R0 = [X[0]] + X, [R[0] - W[0]["money"]] + R
    ax.step(X0, R0, where="post", color=col, lw=2.0, zorder=3, marker="o" if len(X) < 3 else None, ms=4)
    lx = [x for x, m in zip(X, W) if m["money"] < -0.004]
    ly = [y for y, m in zip(R, W) if m["money"] < -0.004]
    base, _k, _why = bs.pot_for(pctx_, sub, "all_time")
    refs = [ref(R[-1] - dist, "%s: %s below now" % (g.what, usd(dist, False)), color=DOWN, ls=":", optional=True)
            for g, dist in stops if not _is_day(g)]
    lim = money_axis(ax, R0, kind="pnl", xs=X0, refs=refs, room_top=0.12)
    mark_last(ax, X[-1], R[-1], usd(R[-1]), color=col)
    annotate_change(ax, X0, R0, base=base or False, extra=[r["label"] for r in lim["far"]], lows=False)
    if lx:
        ax.scatter(lx, ly, s=22, color=DOWN, edgecolor=SURF, linewidth=1.0, zorder=4, label="a losing %s" % unit)
        ax.legend(loc=free_corner(ax), frameon=True, facecolor=SURF, edgecolor="none", framealpha=0.92)
    pct_of_axis(ax, base, (("%% of the %s's %s put in" % (bs.SUB_NAME[sub], usd(base, False))) if len(subs) == 1 else
                           ("%% of the %s put into %s" % (usd(base, False), bs.sub_name(sub)))) if base else "")
    ax.set_title("Money made, running total, market by market (Kalshi's books, %s)" % bs.sub_name(sub))
    ax = axs[1]
    # a rolling rate is drawn only where its window is full (n markets / races behind it)
    wy = []
    if unit == "leg":                                   # the race: a race = the legs of one event
        races = series.race_rows(bs, c, name)
        n = min(ROLL, max(5, len(races) // 4))
        rr = roll([100.0 if w else 0.0 for _t, _v, w, _tie in races], n)
        j0 = max(n - 1, next((i for i, r in enumerate(races) if r[0] >= cut), len(races)))
        ax.plot([etdt(r[0]) for r in races[j0:]], rr[j0:], color=col, lw=2.0,
                label="won %% of the last %d races" % n, zorder=3)
        wy = rr[j0:]
        have, what = len(races), "races (a tie counts as not won)"
    else:
        n = min(ROLL, max(5, len(ms) // 4))
        j0 = max(n - 1, i0)
        wr = roll([100.0 if m["money"] > 0.004 else 0.0 for m in ms], n)[j0:]
        ax.plot(Xall[j0:], wr, color=col, lw=2.0, label="won %% of the last %d markets" % n, zorder=3)
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
        be = [a for a in acc[j0:] if a is not None]
        ax.plot([x for x, a in zip(Xall[j0:], acc[j0:]) if a is not None], be,
                color=MUTED, lw=1.6, ls="--", label="break-even % (what its prices needed)", zorder=2)
        wy = wr + be
        have, what = len(ms), "markets"
    ax.set_title("Win rate over time (%s)" % what)
    if wy:
        value_axis(ax, wy, unit="%", kind="level", floor=0.0, cap=100.0, room_bottom=0.25)
        ax.legend(loc="lower left", frameon=True, facecolor=SURF, edgecolor="none", framealpha=0.92)
    else:                                               # 10-30: never an empty frame dated Jan 1
        mark_empty(ax, "a win rate needs %d %s; it has %d so far" % (n, "races" if unit == "leg" else "markets", have))
    time_axis(axs[-1], X0[0], X0[-1])
    at, td = blk.get("all_time") or {}, blk.get("today") or {}
    # v-tg-money-words (2026-10-31): its pot NOW first (what Kalshi holds there: cash + open bets), then money made
    from botdata import pots as _pots
    nows = [_pots._pv(pctx_, s_, sub)["now"] for s_ in subs]
    bot_headline(fig, label, None if any(v is None for v in nows) else sum(nows), at.get("money"), td.get("money"))
    cap = ("%s: today's pace against yesterday and its average day of the last %d and %d days (slate dash-dots, "
           "drawn once it has more days than the %d), every settled %s from Kalshi's books (botstats, %s), its running total and its win rate "
           "over time (the last %d days drawn; the total counts all). Right axis: the same dollars as %% of the money put "
           "into that account." % (label, PACE_DAYS, LONG_DAYS, PACE_DAYS, unit, bs.sub_name(sub),
                                   WINDOW_DAYS))
    return png(fig), cap
