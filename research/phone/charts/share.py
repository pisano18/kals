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

THE BRAG PICTURE (/share_brag; the operator 11-13: safe "even to that team of quants" whose full-time job is to work it
out; never more than is earned, preferably not less; then "full timeline of the two months, shuffled (intelligently so
early gains don't mix with late ones)", with dollars, percents and the bankroll). The pictures above keep the real order
of days or hours, and once the post date dates them, a path lines up with the public record (a loss on the day prices
flipped late): they are for the operator, not for posting against a team. A smooth two-number curve was safe but proved
nothing ("literally anybody could just make that"). This one is the last 60 whole days, every real day with its own
money and %, after fees, and the real bankroll; the days are shuffled only inside random 10-15 day stretches
(random.SystemRandom, a new shuffle every time), and a deposit always ends a stretch, so money in never lands among the
other side's days. So early days stay early, every stretch's total is real, the bankroll line ends exactly at the real
bankroll (checked; else nothing is sent), and no day sits on its date. The % is time-weighted (deposits are not gains)
and rounded DOWN; the dollars show the scale, so the % never reads bigger than the money. What a team still gets:
roughly two-week totals and the spread of good and bad days -- enough to test a guess, never to make one.
"""
import math
import random
import re

import bots
from botdata import series
from phone.charts.base import (BLUE, MUTED, category_axis, day_number_axis, fig_new, headline, mark_last,
                               money_axis, note, pct_axis, png, ups_downs, usd)
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


# ---- the brag picture: the real timeline, shuffled inside short stretches -----------------------------------------------
BRAG_DAYS = 60                          # the window: the last 60 whole days
BLOCK = (10, 15)                        # days are shuffled only inside stretches this long (random lengths)
EVENT_MIN = 25.0                        # money moved in or out of at least this much ends a stretch (a deposit)


def window_book(ctx, n_days):
    """([(money made, every pot that morning, money moved in or out that day)] oldest first for the last n_days whole
    days ending yesterday, every pot at the start of today), or None: botstats unreadable or partial, or the record
    shorter than the window. made + moved = the next morning's pots - this morning's, exactly."""
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
    days.reverse()
    if days[0] < min(per):
        return None
    pots = [bs.day_pot(pctx_, None, d) for d in days] + [bs.day_pot(pctx_, None, bs.et_day(ctx.now))]
    if any(not p or p <= 0 for p in pots):
        return None
    book = [(per.get(d, 0.0), pots[i], pots[i + 1] - pots[i] - per.get(d, 0.0)) for i, d in enumerate(days)]
    return book, pots[-1]


def brag_pct(r):
    """The whole percent shown: rounded DOWN, never more than was made."""
    return int(math.floor(100.0 * r + 1e-9))


def stretches(book, rng, block=BLOCK, event_min=EVENT_MIN):
    """[(first, last)] day indexes the days are shuffled within. A deposit (consecutive days moving money, EVENT_MIN or
    more in all) ends a stretch on its first day, so money in never lands among the other side's days; between deposits
    the days are cut into random stretches of block[0]..block[1] (a short remainder joins the last one)."""
    n = len(book)
    ends, i = set(), 0
    while i < n:
        if abs(book[i][2]) > 0.005:
            j, moved = i, 0.0
            while j < n and abs(book[j][2]) > 0.005:
                moved += book[j][2]
                j += 1
            if abs(moved) >= event_min:
                ends.add(i)
            i = j
        else:
            i += 1
    segs, start = [], 0
    for e in sorted(ends) + [n - 1]:
        if e >= start:
            segs.append((start, e))
            start = e + 1
    out = []
    for a, b in segs:
        while b - a + 1 > block[1] and b - a + 1 >= 2 * block[0]:    # 16..19 days stay one stretch
            k = rng.randint(block[0], min(block[1], b - a + 1 - block[0]))
            out.append((a, a + k - 1))
            a += k
        out.append((a, b))
    return out


def shuffle_book(book, rng, block=BLOCK, event_min=EVENT_MIN):
    """(the order the days are shown in, the stretches). Each day keeps its own money and %; days move only inside
    their stretch, so early days stay early and every stretch's total, and the end, are exactly real."""
    order = []
    for a, b in stretches(book, rng, block, event_min):
        part = list(range(a, b + 1))
        rng.shuffle(part)
        order += part
    return order


def bankroll_path(book, order, start, event_min=EVENT_MIN):
    """The bankroll at day 0..n with the days in `order`: money moved in or out stays on its real day, a deposit's
    spill-over days added with its first day (so it lands at a stretch's end). Ends exactly at the real bankroll."""
    n = len(book)
    moved = [0.0] * n
    i = 0
    while i < n:
        if abs(book[i][2]) > 0.005:
            j, tot = i, 0.0
            while j < n and abs(book[j][2]) > 0.005:
                tot += book[j][2]
                j += 1
            if abs(tot) >= event_min:
                moved[i] += tot
            else:
                for k in range(i, j):
                    moved[k] += book[k][2]
            i = j
        else:
            i += 1
    path = [start]
    for slot, day in enumerate(order):
        path.append(path[-1] + book[day][0] + moved[slot])
    return path, moved


def chart_brag(ctx, n_days=BRAG_DAYS, rng=None):
    got = window_book(ctx, n_days)
    if got is None:
        return None
    book, end = got
    rng = rng or random.SystemRandom()                  # a fresh shuffle every time: nothing to undo
    order = shuffle_book(book, rng)
    path, moved = bankroll_path(book, order, book[0][1])
    if abs(path[-1] - end) > 0.05:                      # the line must end at the real bankroll, or nothing is sent
        log("share picture brag NOT sent: the bankroll line ends at %.2f, the real one is %.2f" % (path[-1], end))
        return None
    made = [book[d][0] for d in order]
    pcts = [100.0 * book[d][0] / book[d][1] for d in order]
    twr = 1.0
    for m, p, _f in book:
        twr *= 1.0 + m / p
    up = sum(1 for m, _p, _f in book if m > 0.004)
    xs = list(range(0, n_days + 1))
    fig, axs = fig_new(3, 11.4, ratios=[3, 2, 2], sharex=True)
    axs[0].plot(xs, path, color=BLUE, lw=2.4, zorder=3)
    axs[0].fill_between(xs, path, min(path), color=BLUE, alpha=0.07, lw=0)
    money_axis(axs[0], path, kind="balance", room_top=0.14)
    mark_last(axs[0], xs[-1], path[-1], usd(path[-1], False), color=BLUE)
    for slot, m in enumerate(moved):
        if abs(m) >= EVENT_MIN:
            note(axs[0], slot + 1, path[slot + 1], "%s %s" % ("deposit" if m > 0 else "withdrawal",
                                                            usd(round(m), True).replace(".00", "")),
                 dy=-14, size=8.5, color=MUTED, weight="normal")
    axs[0].set_title("Bankroll after fees · %+d%% time-weighted, deposits not counted" % brag_pct(twr - 1.0))
    axs[1].bar(xs[1:], made, width=0.78, color=ups_downs(made), zorder=3)
    money_axis(axs[1], made, room_top=0.1)
    axs[1].set_title("Money made each day · days shuffled within 10-15 day stretches")
    axs[2].bar(xs[1:], pcts, width=0.78, color=ups_downs(pcts), zorder=3)
    pct_axis(axs[2], pcts, room_top=0.1)
    axs[2].set_title("Each day as % of the bankroll that morning")
    day_number_axis(axs[2], 0, n_days, pad=0.6)
    headline(fig, "Bankroll %s · made %s in %d days · %d of %d days up" % (
        usd(end, False), usd(sum(m for m, _p, _f in book)), n_days, up, n_days))
    return finish(fig, "brag")
