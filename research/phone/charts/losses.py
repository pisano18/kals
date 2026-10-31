"""losses.py -- /losses: every bot's losing markets, coloured by bot (and the main account's losing closes when
botstats cannot be read).

v-tg-rebuild step 8 (2026-10-30): moved verbatim out of tgcharts.py (chart_losses, chart_losses_main, _week_of); the
losing markets are botdata.series.all_losses (the words' own source).
"""
import datetime as _dt

import pindesk
from pindesk import Ledger
from botdata import series
from phone.charts.base import (AVG30, BOT_COLOUR, BOT_SHORT, DOWN, GREY, GRID, INK, INK2, SURF, UP, category_axis,
                               et_short, etdt, fig_new, headline, made, money_axis, note, pct_axis, png, time_axis, usd)

LONG_DAYS = series.LONG_DAYS
LOSS_WEEKS = 8                          # /losses: the weekly bars
LOSS_LANE_DAYS = 30                     # /losses: the timeline


def week_of(day):
    """'2026-10-28' -> the Monday that starts its ET week, '2026-10-26'."""
    d = _dt.date.fromisoformat(day)
    return (d - _dt.timedelta(days=d.weekday())).isoformat()


def chart_losses(ctx):
    """/losses (operator 10-26: "That losses chart is pretty bad it's really hard to notice any trends or anything
    meaningful and it's also just hard to see what's what. New kind of chart/graph"). Every bot's losses from
    all_losses (the words' own source), two ways:
      top     each ET week (Monday-Sunday), the last LOSS_WEEKS: what the winning markets made (green, up) against
              what the losing ones cost (down, stacked, one colour a bot) and the week's loss total -- is losing
              growing, which bot does it, and how big it is next to what was won;
      bottom  every loss of the last LOSS_LANE_DAYS days on its own bot's row, the circle's AREA = the dollars, the
              biggest named; each row's label carries its count and total -- what happened when, at a glance.
    The main account's losing closes (chart_losses_main) when botstats cannot be read."""
    try:
        bs, rows, per, missing = series.all_losses(*ctx.bs_args())
    except Exception:                                   # noqa: BLE001 -- no botstats: the main account's picture
        return chart_losses_main(ctx) if ctx.ledger is not None else None
    rows = [r for r in rows if r["t"] and r["day"]]
    if not rows:
        return None
    now = ctx.now
    today = bs.et_day(now)
    order = [b for b in tuple(bs.BOTS) + ("earlier", "other") if b in per]     # all_losses folds hidden bots into 'earlier'
    first = min([r["day"] for r in rows] + [d for p in per.values() for d in p["won_days"]])
    weeks = [week_of(today)]
    while len(weeks) < LOSS_WEEKS:
        w = (_dt.date.fromisoformat(weeks[0]) - _dt.timedelta(days=7)).isoformat()
        if w < week_of(first):
            break
        weeks.insert(0, w)
    wi = {w: k for k, w in enumerate(weeks)}
    won = [0.0] * len(weeks)
    lost = {b: [0.0] * len(weeks) for b in order}
    nlost = [0] * len(weeks)
    for b in order:
        for d, v in per[b]["won_days"].items():
            k = wi.get(week_of(d))
            if k is not None:
                won[k] += v
    for r in rows:
        k = wi.get(week_of(r["day"]))
        if k is not None:
            lost[r["bot"]][k] += r["money"]
            nlost[k] += 1
    fig, axs = fig_new(2, 9.4, ratios=[1.15, 1.0])
    ax = axs[0]
    xs = list(range(len(weeks)))
    ax.bar(xs, won, width=0.62, color=UP, alpha=0.45, zorder=3, label="won")
    base = [0.0] * len(weeks)
    for b in order:
        if not any(lost[b]):
            continue
        ax.bar(xs, lost[b], width=0.62, bottom=base, color=BOT_COLOUR.get(b, GREY), zorder=3,
               label=BOT_SHORT.get(b, b))
        base = [x + y for x, y in zip(base, lost[b])]
    for k in xs:
        if nlost[k]:
            ax.annotate("%s\n%d lost" % (usd(base[k]), nlost[k]), (k, base[k]), xytext=(0, -3),
                        textcoords="offset points", ha="center", va="top", fontsize=8.5, color=DOWN, fontweight="bold",
                        zorder=6, bbox=dict(facecolor=SURF, edgecolor="none", pad=1.5))   # over the 30-day line
        if won[k] > 0.005:
            ax.annotate(usd(won[k]), (k, won[k]), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                        fontsize=8.5, color=INK2)
    # 2026-10-29 ("more charts may benefit from history averages"): what an average week lost over the last 30 FULL ET
    # days (today left out; days before the first market left out, so a young record averages what it has), so this
    # week's bar reads against usual. Every bot's losing markets, the bars' own rows.
    d_hi = bs.shift_day(today, -1)
    d_lo = max(bs.shift_day(today, -LONG_DAYS), first)
    n30 = sum(1 for k in range(1, LONG_DAYS + 1) if bs.shift_day(today, -k) >= first)
    if n30 > 7:
        wk30 = 7.0 * sum(r["money"] for r in rows if d_lo <= r["day"] <= d_hi) / n30
        ax.axhline(wk30, color=AVG30, lw=1.6, ls="-.", zorder=2.5,      # behind the bars and their words
                   label="lost in an average week, last %d days (%s)" % (n30, usd(wk30)))
    # room under the bars for each week's loss words, over them for the key (2 rows)
    money_axis(ax, won + base + ([wk30] if n30 > 7 else []), room_bottom=0.12, room_top=0.24)
    category_axis(ax, [(lambda d: d.strftime("%b ") + str(d.day))(_dt.date.fromisoformat(w))
                       + ("\nso far" if k == len(weeks) - 1 else "") for k, w in enumerate(weeks)], axis="x",
                  pad=0.6)
    ax.set_title("Each week (Mon-Sun ET): money made by every bot, up; lost, down, by bot")
    ax.legend(loc="upper center", fontsize=8.5, ncol=4, frameon=True, facecolor=SURF, edgecolor="none", framealpha=0.92,
              columnspacing=1.0, handlelength=1.2)

    ax = axs[1]
    t_lo = now - LOSS_LANE_DAYS * 86400
    day_lo = bs.et_day(t_lo)
    lane = [r for r in rows if r["t"] >= t_lo]
    active = [b for b in order if any(d >= day_lo for d in per[b]["won_days"]) or any(r["bot"] == b for r in lane)]
    active = active or order
    yi = {b: k for k, b in enumerate(active)}
    biggest = max((-r["money"] for r in lane), default=1.0) or 1.0
    for b in active:
        rs = [r for r in lane if r["bot"] == b]
        if rs:
            ax.scatter([etdt(r["t"]) for r in rs], [yi[b]] * len(rs), s=[24 + 520 * (-r["money"]) / biggest for r in rs],
                       color=BOT_COLOUR.get(b, GREY), alpha=0.75, edgecolor=SURF, linewidth=0.8, zorder=4)
    big = sorted(sorted(lane, key=lambda r: r["money"])[:4], key=lambda r: r["t"])     # the 4 biggest, named,
    for k, r in enumerate(big):                                                      # above / below in turn
        what = r["what"].split(" ")[0] if r["bot"] != "race" else r["what"].replace("race ", "").split(" ")[0]
        up = k % 2 == 0
        ax.annotate("%s %s" % (what, usd(r["money"])), (etdt(r["t"]), yi[r["bot"]]), xytext=(0, 11 if up else -11),
                    textcoords="offset points", ha="center", va="bottom" if up else "top", fontsize=8.5, color=INK,
                    zorder=6)
    labels = []
    for b in active:
        rs = [r for r in lane if r["bot"] == b]
        labels.append("%s\n%s" % (BOT_SHORT.get(b, b), ("%d lost, %s" % (len(rs), usd(sum(r["money"] for r in rs))))
                                  if rs else "no losses"))
    category_axis(ax, labels, axis="y", fontsize=9, top_first=True, pad=0.6, lo_pad=0.75)   # first bot on top
    ax.grid(True, axis="x", color=GRID, lw=0.6)
    for k in range(len(active)):
        ax.axhline(k, color=GRID, lw=0.6, zorder=1)
    time_axis(ax, t_lo, now + 0.6 * 86400, pad=0.0, fixed=True)              # the last 30 days, whatever they hold
    ax.set_title("Every loss, last %d days (circle size = dollars)" % LOSS_LANE_DAYS)

    d7 = bs.shift_day(today, -6)                       # the last 7 ET days, today in -- the words' '7d' count
    d35 = bs.shift_day(today, -34)
    week = [r for r in rows if r["day"] >= d7]
    before = [r for r in rows if d35 <= r["day"] < d7]
    nb = min(4, max(0, sum(1 for k in range(7, 35) if bs.shift_day(today, -k) >= first) // 7))
    head = "Last 7 days: %s lost in %d market%s" % (usd(sum(r["money"] for r in week)), len(week),
                                                    "" if len(week) == 1 else "s")
    if nb >= 1:
        head += " · %s a week before" % usd(sum(r["money"] for r in before) / nb)
    headline(fig, head)
    cap = ("Losses, every bot (Kalshi's books, every pot; colour = the bot). Top: each ET week's winning markets (green) "
           "against its losing ones (down, by bot), the newest week so far. Bottom: each loss of the last %d days on "
           "its bot's row, circle area = dollars. Slate dash-dots: what an average week lost over the 30 full ET days "
           "before today. Last 7 days = today and the 6 ET days before (as /losses counts "
           "them); 'a week before' = the average of the 4 weeks before those.%s" % (
               LOSS_LANE_DAYS, (" Left out (Kalshi could not be read): " + ", ".join(missing) + ".") if missing else ""))
    return png(fig), cap


def chart_losses_main(ctx):
    led = ctx.ledger
    lc = [(k, net, legs) for k, net, legs in led.losing_closes() if k]
    if not lc:
        return None
    lc.sort(key=lambda x: x[0])
    s = Ledger.summary(led.settled)
    X = [etdt(k) for k, _n, _l in lc]
    Y = [net for _k, net, _l in lc]
    P = []
    for k, net, _l in lc:
        b = led.bank_at(k)
        P.append((100.0 * net / b) if b else None)
    fig, axs = fig_new(2, 7.6, sharex=True)
    ax = axs[0]
    ax.vlines(X, 0, Y, color=DOWN, lw=1.4, zorder=3)
    ax.scatter(X, Y, s=26, color=DOWN, edgecolor=SURF, linewidth=1.0, zorder=4)
    mid = lc[0][0] + (lc[-1][0] - lc[0][0]) / 2.0
    for r, i in enumerate(sorted(range(len(Y)), key=lambda i: Y[i])[:3]):       # the 3 worst, staggered
        coins = ", ".join(sorted({pindesk.coin(lg["tk"]) for lg in lc[i][2]}))
        left = lc[i][0] < mid
        note(ax, X[i], Y[i], "%s %s %s" % (coins, et_short(lc[i][0], "%m/%d"), usd(Y[i])), dx=6 if left else -6,
             dy=4 + 13 * r, ha="left" if left else "right", size=8.5, weight="normal")
    money_axis(ax, Y)
    ax.set_title("Each losing close: dollars lost")
    ax = axs[1]
    px = [x for x, p in zip(X, P) if p is not None]
    pv = [p for p in P if p is not None]
    ax.vlines(px, 0, pv, color=DOWN, lw=1.4, zorder=3)
    ax.scatter(px, pv, s=26, color=DOWN, edgecolor=SURF, linewidth=1.0, zorder=4)
    pct_axis(ax, pv)
    ax.set_title("The same loss as % of the bank at that moment")
    time_axis(axs[-1], xs=X)
    headline(fig, "%d losing closes of %d (%.1f%%) · worst lost %s" % (s["lost"], s["closes"], s["loss_rate"] or 0.0, usd(min(Y))))
    cap = ("Every losing close, all time (Kalshi's books, main account; one close = every market settling at that "
           "quarter-hour, as /losses counts them). Bottom: the loss as % of the bank then (pindesk's bank_at).")
    return png(fig), cap
