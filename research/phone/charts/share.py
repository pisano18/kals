"""share.py -- what /share_today /share_yesterday /share_days /share_funds (/share_bots) hide, and the leak check.

THE OPERATOR, 2026-11-12: "I'd like to post about it, without letting anybody into the market or be able to know how
it's being done. Even institutional investors doing full research on my posts" ... "Make a share command to get safe,
postable charts" ... "Make sure they're exactly the same as their originals except for what must be hidden".

So each share picture IS its original (day.chart_day, days.chart_days, funds.chart_funds with share=True): the same
lines, averages, bars, panels, headline money and colours. Dollars stay (the operator's call). Hidden, because each
leads back to the trades or names the venue:
  * dates, weekdays, clock times -- days are numbered (days_axis), a day runs in hours 0-24 (hours_axis);
  * every market's own step and dot -- the day's own lines are sampled once an hour (hourly), so no step is one
    market closing (Kalshi's public trade tape has every trade's time, price and size: a timed step is a fingerprint);
    no losing-market dots, no 'N of M markets won' (it says how many markets a day it trades);
  * bot, account and pot names -- 'Bot 1', 'Account 1' (ANON), no pot names; 'the account', not pots or ET days;
  * the long captions (they name Kalshi, markets, bots) -- CAPTION instead.

THE LEAK CHECK (one rule for every share picture, now and later): finish() reads EVERY text on the drawn figure -- the
headline, titles, axis labels, tick labels, the right-hand axis, the legend, every note -- and the caption, against
FORBIDDEN (dates, times, the exchange, market words, coins) plus every name the bot registry knows (bots, labels,
commands, accounts, pots). One hit and the picture is not sent (logged). phone/charts/tests/test_share.py plants every
leak it guards against.

THE BRAG PICTURE (/share_brag, the last 30 days; the operator 11-13: safe "even to that team of quants" whose
full-time job is to work it out; never more than is earned, preferably not less). Every picture above carries the path
in its real order, and once the post date dates it, a path lines up with the public record (a loss on the day prices
flipped late). A two-number smooth curve was safe but proved nothing ("literally anybody could just make that"). This
one shows EVERY real day of the window -- each day's money over what every pot held that morning, after fees -- and the
growth they compound to, but in a fresh random order each time (random.SystemRandom): compounding does not care about
order, so the end is exactly the real time-weighted total, and no day sits on its date, so nothing can be lined up.
The picture says so. The % is rounded DOWN. No dollars, hours, bots or names. What it still shows: the spread of good
and bad days -- it can test a guess about the strategy, never make one. 30 days only: a 60-day window (+424% on 11-13)
was mostly September's small-account days, and would read as earning faster now than the account does.
"""
import math
import random
import re

import bots
from botdata import series
from phone.charts.base import (BLUE, category_axis, day_number_axis, fig_new, headline, mark_last, pct_axis, png,
                               ups_downs)
from phone.log import log

CAPTION = "Save the picture itself to post it: a screenshot of this chat shows when it was sent."
# bots by registry order, never by name; every retired or paused bot's past money is one line, as on the originals
ANON = dict({b.name: "Bot %d" % (i + 1) for i, b in enumerate(bots.all_bots())},
            **{bots.EARLIER: "Retired bots", bots.OTHER: "Other"})

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


def hourly(pts, upto_s):
    """[(seconds into the day, running total)] sampled on every full hour up to upto_s, then the total at upto_s when
    money came after the last full hour: no step is one market."""
    out, k, cum = [], 0, 0.0
    for h in range(0, int(upto_s // 3600) + 1):
        while k < len(pts) and pts[k][0] <= h * 3600:
            cum = pts[k][1]
            k += 1
        out.append((h * 3600, cum))
    if k < len(pts):
        out.append((max(upto_s, out[-1][0]), pts[-1][1]))
    return out


def hours_axis(ax):
    """The day in hours 0..24 (the originals' 12 AM .. 12 AM clock, without the clock)."""
    category_axis(ax, [str(h) for h in range(0, 25, 3)], positions=list(range(0, 25, 3)), pad=0.0)
    ax.set_xlabel("hours into the day")


def days_axis(ax, lo, hi, pad=0.6, label="day"):
    """Days numbered (lo..hi), never a date or a weekday: base.day_number_axis (only base.py sets ticks and limits)."""
    day_number_axis(ax, lo, hi, pad=pad, label=label)


# ---- the brag picture: every real day, in shuffled order ---------------------------------------------------------------
def window_days(ctx, n_days):
    """Each of the last n_days whole days' return, oldest first, ending yesterday: every bot's money that day over
    what every pot held that morning. None: botstats unreadable or partial, or the record shorter than the window."""
    try:
        bs, pctx_, rows, missing = series.all_day_markets(*ctx.bs_args())
    except Exception:                                   # noqa: BLE001
        return None
    if missing or not rows:
        return None
    per = {}
    for d, _t, v, _b in rows:
        per[d] = per.get(d, 0.0) + v
    days, d = [], bs.et_day(ctx.now)
    for _ in range(n_days):
        d = bs.shift_day(d, -1)
        days.append(d)
    if min(days) < min(per):
        return None
    out = []
    for d in reversed(days):
        b = bs.day_pot(pctx_, None, d)
        if not b or b <= 0:
            return None
        out.append(per.get(d, 0.0) / b)
    return out


def window_return(ctx, n_days):
    """The time-weighted return over the last n_days whole days (window_days compounded), or None."""
    rs = window_days(ctx, n_days)
    if rs is None:
        return None
    g = 1.0
    for r in rs:
        g *= 1.0 + r
    return g - 1.0


def brag_pct(r):
    """The whole percent shown: rounded DOWN, never more than was made."""
    return int(math.floor(100.0 * r + 1e-9))


def shuffled_growth(rs, rng):
    """(the days in a shuffled order, the running growth in % from 0 over them). Compounding does not care about
    order, so the last point is exactly the real total, whatever the shuffle."""
    order = list(rs)
    rng.shuffle(order)
    growth, g = [0.0], 1.0
    for r in order:
        g *= 1.0 + r
        growth.append(100.0 * (g - 1.0))
    return order, growth


def chart_brag(ctx, n_days, rng=None):
    rs = window_days(ctx, n_days)
    if rs is None:
        return None
    order, growth = shuffled_growth(rs, rng or random.SystemRandom())   # a fresh order every time: nothing to undo
    if growth[-1] <= -100.0:
        return None
    total = growth[-1] / 100.0
    shown = brag_pct(total)
    bars = [100.0 * r for r in order]
    up = sum(1 for r in rs if r > 0)
    fig, axs = fig_new(2, 8.6, ratios=[3, 2], sharex=True)
    xs = list(range(0, n_days + 1))
    axs[0].plot(xs, growth, color=BLUE, lw=2.4, zorder=3)
    axs[0].fill_between(xs, growth, 0, color=BLUE, alpha=0.08, lw=0)
    pct_axis(axs[0], growth, kind="pnl", room_top=0.12)
    mark_last(axs[0], xs[-1], growth[-1], "%+d%%" % shown, color=BLUE)
    axs[0].set_title("Account growth after fees: every day and the total are real")
    axs[1].bar(xs[1:], bars, width=0.78, color=ups_downs(bars), zorder=3)
    pct_axis(axs[1], bars, kind="pnl", room_top=0.1)
    axs[1].set_title("Each day, % of the account that morning, shuffled so none sits on its real date")
    day_number_axis(axs[1], 0, n_days, pad=0.6)
    headline(fig, "%+d%% in %d days · %d of %d days up" % (shown, n_days, up, n_days))
    return finish(fig, "brag")
