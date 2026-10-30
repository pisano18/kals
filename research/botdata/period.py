"""period.py -- every bot's money over a span of ET days, for the phone's weekly and monthly reports and /week /month
(v-tg-rebuild step 12, lane Q, 2026-10-30). DATA only: no words, never imports the phone.

  weeks(today) / months(today)    the spans the reports use: this week (Mon..Sun) and the one before; this month and the
                                  one before; with which=last, the one before each
  span(markets, pctx, first, last, bs)   the money of [(bot key, botstats.market row)] whose ET close day is in
                                  first..last: by bot (markets, lost, $ lost, worst), the total, every day's total, the
                                  best and worst day, the % of each bot's pot and of all pots (pot_for's 'start' rule
                                  over the span: what the pot held when the span began + money moved in during it)
  report(bs, now, first, last, prev_first, prev_last, getter, procs)   both spans from ONE botstats read

Every market is Kalshi's (botstats' cache, the /bots source); a hidden bot is counted as 'earlier' (series.fold).
"""
import datetime

from botdata import pots as _pots
from botdata import series as _series
from botdata import tables as _tables
from botdata.clock import day_start, shift_day


def _d(day):
    return datetime.date.fromisoformat(day)


def weeks(today, which="this"):
    """((first, last), (prev_first, prev_last)): this Mon..Sun week (last = its Sunday, may be in the future) and the
    week before; which='last': the week before this one and the one before that."""
    mon = _d(today) - datetime.timedelta(days=_d(today).weekday())
    if which == "last":
        mon -= datetime.timedelta(days=7)
    a = (mon.isoformat(), (mon + datetime.timedelta(days=6)).isoformat())
    p = ((mon - datetime.timedelta(days=7)).isoformat(), (mon - datetime.timedelta(days=1)).isoformat())
    return a, p


def months(today, which="this"):
    """((first, last), (prev_first, prev_last)) of this calendar month and the one before; which='last': the month
    before this one and the one before that."""
    first = _d(today).replace(day=1)
    if which == "last":
        first = (first - datetime.timedelta(days=1)).replace(day=1)
    nxt = (first + datetime.timedelta(days=32)).replace(day=1)
    prev = (first - datetime.timedelta(days=1)).replace(day=1)
    return (first.isoformat(), (nxt - datetime.timedelta(days=1)).isoformat()), \
        (prev.isoformat(), (first - datetime.timedelta(days=1)).isoformat())


def days_in(first, last, today=None):
    """ET days of first..last that have begun (up to `today` when given): the divisor of an average day."""
    end = min(last, today) if today else last
    if end < first:
        return 0
    return (_d(end) - _d(first)).days + 1


def span_pot(pctx, sub, first, last):
    """pot_for's 'start' rule over first..last for pot `sub` (a sub, a tuple of subs, None = all pots): what it held at
    midnight ET starting `first` + money moved in during the span. None when it cannot be worked out."""
    led = pctx["led"]
    subs = _tables.SUBS if sub is None else (sub if isinstance(sub, tuple) else (sub,))
    now_v = settled = 0.0
    for s in subs:
        p = _pots._pv(pctx, s, sub)
        if p["now"] is None or not p["complete"]:
            return None
        now_v += p["now"]
        settled += sum(v for d, v in p["days"].items() if d and d >= first)
    t0, t1 = day_start(first), day_start(shift_day(last, 1))
    cut = pctx.get("as_of")
    if cut is not None and t0 > cut:
        return None
    start = now_v - settled - _pots.flows(led, sub, t0, cut)
    if start < -_pots.MIN_POT:
        return None
    pot = max(0.0, start) + max(0.0, _pots.flows(led, sub, t0, t1))
    return pot if pot >= _pots.MIN_POT else None


def _pot_key(bs, name):
    subs = bs.bot_subs(name)
    return subs if len(subs) > 1 else subs[0]


def span(markets, pctx, first, last, bs):
    """The money of first..last (see the module note). markets: [(key, row)] (series.all_markets)."""
    by, days = {}, {}
    worst = None
    for key, m in markets:
        if not m["day"] or not (first <= m["day"] <= last):
            continue
        b = by.setdefault(key, {"money": 0.0, "markets": 0, "lost": 0, "money_lost": 0.0, "worst": None})
        b["money"] += m["money"]
        b["markets"] += 1
        days[m["day"]] = days.get(m["day"], 0.0) + m["money"]
        if m["money"] < -0.004:
            b["lost"] += 1
            b["money_lost"] += m["money"]
            if b["worst"] is None or m["money"] < b["worst"]["money"]:
                b["worst"] = m
            if worst is None or m["money"] < worst[1]["money"]:
                worst = (key, m)
    total = sum(b["money"] for b in by.values())
    for key, b in by.items():
        b["money"] = round(b["money"], 4)
        b["money_lost"] = round(b["money_lost"], 4)
        pot = span_pot(pctx, _pot_key(bs, key), first, last) if key in getattr(bs, "SPEC", {}) else None
        b["pot"] = None if pot is None else round(pot, 2)
        b["pot_pct"] = round(100.0 * b["money"] / pot, 2) if pot else None
    allpot = span_pot(pctx, None, first, last)
    ds = sorted(days.items())
    return {"first": first, "last": last, "by_bot": by, "money": round(total, 4),
            "markets": sum(b["markets"] for b in by.values()), "lost": sum(b["lost"] for b in by.values()),
            "money_lost": round(sum(b["money_lost"] for b in by.values()), 4),
            "pot": None if allpot is None else round(allpot, 2),
            "pot_pct": round(100.0 * total / allpot, 2) if allpot and by else None,
            "days": dict(ds), "best": max(ds, key=lambda kv: kv[1]) if ds else None,
            "worst_day": min(ds, key=lambda kv: kv[1]) if ds else None,
            "worst": None if worst is None else {"bot": worst[0], **worst[1]}}


def report(bs, now, first, last, prev_first, prev_last, getter=None, procs=None):
    """{'now', 'today', 'this': span, 'prev': span, 'missing': [bots whose pots could not be read], 'order': [keys]} from
    one botstats read (the /bots source)."""
    bs_, _c, _prows, _ok, pctx, ms, missing = _series.all_markets(bs, now, getter, procs)
    today = bs.et_day(now)
    keys = []
    for k, _m in ms:
        if k not in keys:
            keys.append(k)
    rank = {b: i for i, b in enumerate(tuple(bs.BOTS) + ("earlier", "other"))}
    keys.sort(key=lambda k: rank.get(k, 99))
    return {"now": now, "today": today, "this": span(ms, pctx, first, last, bs),
            "prev": span(ms, pctx, prev_first, prev_last, bs), "missing": list(missing), "order": keys}


__all__ = ["weeks", "months", "days_in", "span_pot", "span", "report"]
