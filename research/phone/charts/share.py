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

THE BRAG PICTURE (/share_brag, /share_brag_8; the operator 11-13: safe "even to that team of quants" whose full-time job
is to work it out; it must never look like more than is earned, preferably not less). Every picture above still carries
a path -- days, hours, drops -- and a path can be lined up with the public record once the post date dates it. This one
carries exactly TWO real numbers: the time-weighted return over the last N whole weeks (each day's money as a share of
what every pot held that morning, compounded: the standard, deposits never count as gains) and N. The curve between is
the steady growth that joins them, and the picture says it is smoothed. The % shown is rounded DOWN to a whole percent.
Nothing else is on it: no dollars (size), no days, no drops, no bots. Two numbers cannot be lined up with anything.
"""
import math
import re

import bots
from botdata import series
from phone.charts.base import (BLUE, category_axis, day_number_axis, fig_new, headline, mark_last, pct_axis, png)
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


# ---- the brag picture: two real numbers, nothing else ----------------------------------------------------------------
def brag_return(ctx, weeks):
    """The time-weighted return of every bot together over the last `weeks` whole weeks, ending yesterday."""
    return window_return(ctx, 7 * weeks)


def window_return(ctx, n_days):
    """The time-weighted return of every bot together over the last n_days whole days, ending yesterday (each day's
    money over what every pot held that morning, compounded), or None: botstats unreadable or partial, or the record
    shorter than the window."""
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
    g = 1.0
    for d in days:
        b = bs.day_pot(pctx_, None, d)
        if not b or b <= 0:
            return None
        g *= 1.0 + per.get(d, 0.0) / b
    return g - 1.0


def brag_pct(r):
    """The whole percent shown: rounded DOWN, never more than was made."""
    return int(math.floor(100.0 * r + 1e-9))


def chart_brag(ctx, weeks):
    r = brag_return(ctx, weeks)
    if r is None or r <= -1.0:
        return None
    n = 7 * weeks
    xs = [t / 7.0 for t in range(n + 1)]
    ys = [100.0 * ((1.0 + r) ** (t / float(n)) - 1.0) for t in range(n + 1)]   # steady growth from 0 to r
    shown = brag_pct(r)
    fig, (ax,) = fig_new(1, 5.6)
    ax.plot(xs, ys, color=BLUE, lw=2.6, zorder=3)
    ax.fill_between(xs, ys, 0, color=BLUE, alpha=0.08, lw=0)
    pct_axis(ax, ys, kind="pnl", room_top=0.12)
    day_number_axis(ax, 0, weeks, pad=0.15, label="weeks")
    mark_last(ax, xs[-1], ys[-1], "%+d%%" % shown, color=BLUE)
    ax.set_title("Account growth, smoothed: the start and the end are real, after fees")
    headline(fig, "%+d%% in %d weeks" % (shown, weeks))
    return finish(fig, "brag")
