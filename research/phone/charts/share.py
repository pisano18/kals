"""share.py -- /share_today /share_days /share_funds (/share_bots): the /today, /days and /funds pictures, safe to post.

THE OPERATOR, 2026-11-12: "I'd like to post about it, without letting anybody into the market or be able to know how
it's being done. Even institutional investors doing full research on my posts" ... "Make a share command to get safe,
postable charts" (/today, /days, /bots /funds). Dollars stay (the operator's call); everything that can lead back to the
trades goes:

  * no dates, weekdays or clock times -- days are numbered (day 1 = the first day drawn), today runs in hours 0-24;
  * never market by market -- /today's line is sampled once an hour, so no step is one market closing (Kalshi's public
    trade tape has every trade's time, price and size: a timed step is a fingerprint);
  * no bot, account, pot, exchange, coin or market words -- every bot together is one line, every account one total;
  * whole days only on /share_days (today's half day would date the post).

THE LEAK CHECK (one rule for every share picture, now and later): leaks() reads EVERY text on the drawn figure -- the
headline, titles, axis labels, tick labels, the right-hand axis, the legend, every note -- and the caption, against
FORBIDDEN (dates, times, the exchange, market words, coins) plus every name the bot registry knows (bots, labels,
commands, accounts, pots). One hit and the picture is not sent (logged); phone/charts/tests/test_share.py plants every
leak it guards against. Numbers come from the same botdata.series functions /today, /days and /funds use.
"""
import bisect
import re

import bots
from botdata import series
from phone.charts.base import (BLUE, INK, ORANGE, fig_new, headline, legend, made, mark_last, money_axis, pct_axis,
                               pct_of_axis, png, ups_downs, usd, value_axis)
from phone.log import log

SHARE_DAYS = 30                         # /share_days and /share_funds: the last 30 whole days
AVG_DAYS = series.AVG_DAYS
CAPTION = "Save the picture itself to post it: a screenshot of this chat shows when it was sent."

_MONTHS = ("jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|june|july|august|"
           "september|october|november|december")
_WEEKDAYS = "mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
FORBIDDEN = [re.compile(p, re.I) for p in (
    r"\b(%s)\b" % _MONTHS, r"\b(%s)\b" % _WEEKDAYS,
    r"\b\d{1,2}/\d{1,2}\b", r"\b\d{4}-\d{2}-\d{2}\b", r"\b20\d\d\b",             # dates, years
    r"\b\d{1,2}:\d{2}\b", r"\b(am|pm|et|est|edt|utc|gmt|midnight|noon)\b",      # clock times
    r"kalshi", r"sub-?accounts?", r"\bmain account\b", r"\bpots?\b",             # the exchange, its accounts
    r"\b(crypto|coins?|bitcoin|btc|eth|ether|ethereum|sol|solana|xrp|doge|hype|bnb|near|zec|ada|avax|link|ltc|bch|"
    r"sui|shib)\b",
    r"\b(markets?|contracts?|hedge\w*|strikes?|settle\w*|orders?|fills?|bets?|odds|prices?|cents?|"
    r"15m|15-min|minutes?|expir\w*|binary|options?|predictions?|events?|tickers?|ladders?)\b",
    r"\b\d+(\.\d+)?c\b")]                                                          # a price in cents


def registry_words():
    """Every name the bot registry knows: bots, labels, short names, words, commands, accounts, pots, extra pools."""
    words = set()
    for b in bots.all_bots():
        words.update([b.name, b.label, b.short, b.word] + [c.lstrip("/") for c in b.commands + tuple(b.extra_commands)])
    words.update(bots.ACCOUNT_NAME.values())
    words.update(bots.POT_WHAT.values())
    words.add(bots.NOT_BOT_WORD[bots.EARLIER])
    for pools in bots.EXTRA_POOLS.values():
        words.update(pools.values())
    return sorted(w for w in words if w and len(w) >= 2)


def leaks(texts):
    """['<the text>: <what it gives away>', ...] -- empty when every text is safe to post."""
    pats = FORBIDDEN + [re.compile(r"(?<![a-z])%s(?![a-z])" % re.escape(w), re.I) for w in registry_words()]
    out = []
    for t in texts:
        for p in pats:
            m = p.search(t or "")
            if m:
                out.append("%r: %r" % (t, m.group(0)))
                break
    return out


def figure_texts(fig):
    """Every text the drawn figure shows (draws it once so the tick labels exist)."""
    fig.canvas.draw()
    out = [t.get_text() for t in fig.texts]
    if fig._suptitle is not None:
        out.append(fig._suptitle.get_text())
    for ax in fig.axes:
        out += [ax.get_title(loc=w) for w in ("left", "center", "right")]
        out += [ax.get_xlabel(), ax.get_ylabel()]
        for axis_obj in (ax.xaxis, ax.yaxis):
            out += [t.get_text() for t in axis_obj.get_ticklabels()]
        out += [t.get_text() for t in ax.texts]
        for ch in getattr(ax, "child_axes", []):
            out += [ch.get_ylabel()] + [t.get_text() for t in ch.yaxis.get_ticklabels()]
        leg = ax.get_legend()
        if leg is not None:
            out += [t.get_text() for t in leg.get_texts()]
    return [t for t in out if t]


def finish(fig, kind, caption=CAPTION):
    """(png, caption), or None (logged) when any text on the picture or the caption would give something away."""
    found = leaks(figure_texts(fig) + [caption])
    if found:
        log("share picture %s NOT sent, it would give away: %s" % (kind, "; ".join(found)))
        fig.clear()
        return None
    return png(fig), caption


def day_axis(ax, n, label="day"):
    """Days numbered 1..n (or hours 0..24) through the axis engine, no calendar anywhere."""
    value_axis(ax, [1, n] if label == "day" else [0, n], unit="", kind="level", axis="x", integer=True)
    ax.set_xlabel(label, color=INK)


def _all_days(ctx):
    """(botstats, pot context, {ET day: money made by every bot}, today) or None (botstats unreadable or partial)."""
    try:
        bs, pctx_, rows, missing = series.all_day_markets(*ctx.bs_args())
    except Exception:                                   # noqa: BLE001 -- no botstats: nothing safe to draw
        return None
    if missing or not rows:
        return None
    return bs, pctx_, rows, bs.et_day(ctx.now)


def chart_share_today(ctx):
    got = _all_days(ctx)
    if got is None:
        return None
    bs, pctx_, rows, today = got
    first = min(r[0] for r in rows)

    def hourly(d, upto_h):
        t0 = bs.day_start(d)
        ts = sorted((min(max(r[1], t0), t0 + 86400), r[2]) for r in rows if r[0] == d)   # as /today: on its day
        out, cum, k = [], 0.0, 0
        for h in range(0, upto_h + 1):
            while k < len(ts) and ts[k][0] <= t0 + h * 3600:
                cum += ts[k][1]
                k += 1
            out.append(cum)
        return out
    d0 = bs.day_start(today)
    h_now = int(max(0, min(24, (ctx.now - d0) // 3600)))
    net = sum(r[2] for r in rows if r[0] == today)
    ys = hourly(today, h_now)
    xs = list(range(len(ys)))
    if abs(ys[-1] - net) > 0.004:                       # the money since the last full hour: one point at the hour
        xs.append(h_now + 1 if h_now < 24 else 24)       # after, never at the minute
        ys.append(net)
    prev, d = [], today
    for _ in range(AVG_DAYS):
        d = bs.shift_day(d, -1)
        if d >= first:
            prev.append(hourly(d, 24))
    fig, (ax,) = fig_new(1, 5.6)
    every = list(ys)
    if prev:
        avg = [sum(p[h] for p in prev) / len(prev) for h in range(25)]
        ax.plot(range(25), avg, color=ORANGE, lw=1.8, ls="--", zorder=2,
                label="Average day, last %d (%s)" % (len(prev), usd(avg[-1])))
        every += avg
    ax.plot(xs, ys, color=INK, lw=2.2, zorder=3, label="Today %s" % usd(net))
    early = xs[-1] < 12                                 # early in the day the value goes right of the dot, off the axis
    mark_last(ax, xs[-1], ys[-1], usd(ys[-1]), color=INK, dx=6 if early else -4, ha="left" if early else "right")
    money_axis(ax, every, room_top=0.1)
    day_axis(ax, 24, "hours into the day")
    b0 = bs.day_pot(pctx_, None, today)
    pct_of_axis(ax, b0, "% of the account at the start of the day" if b0 else "")
    ax.set_title("Money made today, every bot together, hour by hour")
    legend(ax)
    headline(fig, "Today: %s%s" % (made(net), (" (%+.2f%% of the account)" % (100.0 * net / b0)) if b0 else ""))
    return finish(fig, "today")


def chart_share_days(ctx):
    got = _all_days(ctx)
    if got is None:
        return None
    bs, pctx_, rows, today = got
    per = {}
    for d, _t, v, _b in rows:
        per[d] = per.get(d, 0.0) + v
    days, d = [], today
    while len(days) < SHARE_DAYS:                       # whole days only: today's half day would date the post
        d = bs.shift_day(d, -1)
        if d < min(per):
            break
        days.append(d)
    days.reverse()
    if not days:
        return None
    nets = [per.get(d, 0.0) for d in days]
    banks = [bs.day_pot(pctx_, None, d) for d in days]
    pcs = [(100.0 * v / b) if b else 0.0 for v, b in zip(nets, banks)]
    run, cum = [], 0.0
    for v in nets:
        cum += v
        run.append(cum)
    xs = list(range(1, len(days) + 1))
    fig, axs = fig_new(3, 10.2, sharex=True)
    axs[0].bar(xs, nets, width=0.78, color=ups_downs(nets), zorder=3)
    money_axis(axs[0], nets, room_top=0.08)
    axs[0].set_title("Money made each day")
    axs[1].bar(xs, pcs, width=0.78, color=ups_downs(pcs), zorder=3)
    pct_axis(axs[1], pcs, room_top=0.08)
    axs[1].set_title("Each day as % of the account that morning")
    axs[2].plot(xs, run, color=BLUE, lw=2.2, zorder=3, marker="o", ms=3.5)
    axs[2].fill_between(xs, run, 0, color=BLUE, alpha=0.08, lw=0)
    money_axis(axs[2], run, room_top=0.12)
    mark_last(axs[2], xs[-1], run[-1], usd(run[-1]))
    # the % made is deposit-neutral, as /share_funds: of the account now less what the 30 days made (every deposit
    # counted from day 1). Of day 1's own account it would credit later deposits' earnings to the first money in.
    base = bs.day_pot(pctx_, None, today) - run[-1]
    base = base if base and base > 0 else None
    pct_of_axis(axs[2], base, "% made, deposits counted from day 1" if base else "")
    axs[2].set_title("Money made, running total")
    day_axis(axs[2], len(days))
    up = sum(1 for v in nets if v > 0.004)
    headline(fig, "Last %d days: %s%s · %d of %d days up" % (
        len(days), made(run[-1]), (" (%+.1f%%)" % (100.0 * run[-1] / base)) if base else "", up, len(days)))
    return finish(fig, "days")


def chart_share_funds(ctx):
    try:
        bs, c, prows, ok = ctx.bs_load()
    except Exception:                                   # noqa: BLE001
        return None
    lines = []
    keys = sorted({bs.bot_subs(b) for b in bs.BOTS})
    for key in keys:                                    # every RUNNING account (as /funds), added up: one line
        live = [b for b in bs.BOTS if bs.bot_subs(b) == key and not series.bot_stopped(bs, b, prows, ok)]
        if not live:
            continue
        pts, v, _why, _each = series.account_series(bs, c, key if len(key) > 1 else key[0], ctx.now,
                                                    window_days=SHARE_DAYS, neutral=True)
        if pts:
            lines.append((pts, v if v is not None else pts[-1][1]))
    if not lines:
        return None
    t0 = min(p[0][0] for p, _v in lines)
    grid = list(range(int(t0), int(ctx.now), 3600)) + [ctx.now]

    def at(pts, t):
        k = bisect.bisect_right([p[0] for p in pts], t)
        return pts[max(k, 1) - 1][1]
    tot = [sum(at(p, g) for p, _v in lines) for g in grid]
    tot[-1] = sum(v for _p, v in lines)                 # the dot: every account now
    xs = [(g - t0) / 86400.0 for g in grid]
    fig, (ax,) = fig_new(1, 5.6)
    ax.plot(xs, tot, color=BLUE, lw=2.2, zorder=3)
    ax.fill_between(xs, tot, min(tot), color=BLUE, alpha=0.07, lw=0)
    money_axis(ax, tot, kind="balance", room_top=0.12)
    mark_last(ax, xs[-1], tot[-1], usd(tot[-1], False), color=BLUE)
    day_axis(ax, max(1, int(round(xs[-1]))), "days")
    ax.set_title("The account over time; deposits do not move the line, only trading does")
    gain = tot[-1] - tot[0]
    headline(fig, "Account %s · %s in %d days%s" % (usd(tot[-1], False), made(gain), int(round(xs[-1])),
                                                     (" (%+.1f%%)" % (100.0 * gain / tot[0])) if tot[0] else ""))
    return finish(fig, "funds")

