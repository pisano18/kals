"""money.py -- one settled market in the operator's terms, and money over windows of ET days: describe, market,
window, windows (today / yesterday / 7 days / 30 days / month / all time + days_7 / days_30 / all_days), avg_day / avg_words (the
30-day average day), window_span. Money is Kalshi's (pinledger.pnl); a market belongs to the ET day of its CLOSE.

v-tg-rebuild step 7 (2026-10-30): split out of botstats.py verbatim (botstats.py is now a facade over botdata).
"""
import re
import time

import pinday
import pinledger
from botdata import tables as _tables
from botdata.clock import ampm as _ampm, day_label, et_day, shift_day, utc_epoch as _epoch


def describe(ticker):
    """A market in words, on the ticker's own ET clock: 'HYPE 12:15 AM', 'race XRP 9:15 PM',
    'BTC hourly 11 AM'. No timezone arithmetic -- the ticker is already Eastern."""
    parts = str(ticker or "").split("-")
    series, stamp = parts[0], (parts[1] if len(parts) > 1 else "")
    clock = ""
    try:
        if len(stamp) >= 11:
            clock = _ampm(int(stamp[7:9]), int(stamp[9:11]))
        elif len(stamp) >= 9:
            h = int(stamp[7:9])
            clock = "%d %s" % (h % 12 or 12, "AM" if h < 12 else "PM")
    except ValueError:
        clock = ""
    if series in pinday.RACE:
        return ("race %s %s" % (parts[-1], clock)).strip()
    m = re.match(r"^KX([A-Z0-9]+?)15M$", series)
    if m:
        return ("%s %s" % (m.group(1), clock)).strip()
    if series in _tables.PIN_HOURLY:
        return ("%s hourly %s" % (series[2:-1], clock)).strip()
    m = re.match(r"^KXHIGHT?([A-Z]+)$", series)              # KXHIGHNY / KXHIGHTSFO-26SEP29-B72.5
    if m and len(parts) > 2:
        return "%s high %s" % (m.group(1), parts[-1])
    return str(ticker)


# v-tg-fast (2026-10-31): market() is a pure function of these fields of a settlement row (pinledger.money/pnl/payout,
# the ticker's day and words, the settled time). One /today turned 16k rows into markets (botstats' cache is copied
# afresh on every read, so the same rows come back as new dicts), ~1 s of CPU; the answer is remembered on the
# fields' values (a missing field is its own value) and handed out as a fresh dict each time.
_MARKET_FIELDS = ("ticker", "settled_time", "market_result", "value", "yes_count_fp", "no_count_fp",
                  "yes_total_cost_dollars", "no_total_cost_dollars", "fee_cost")
_MISSING = object()
_MARKETS = {}
_MARKETS_MAX = 200_000


def market(s):
    """One settled market, in the terms the operator reads. Money is pinledger.pnl -- Kalshi's. (v-tg-fast: the
    answer for the same field values is remembered; a new dict each call.)"""
    try:
        key = tuple(s.get(f, _MISSING) for f in _MARKET_FIELDS)
        hash(key)
    except TypeError:                                    # an unhashable field value: worked out, not remembered
        return _market(s)
    got = _MARKETS.get(key)
    if got is None:
        got = _market(s)
        if len(_MARKETS) >= _MARKETS_MAX:
            _MARKETS.clear()
        _MARKETS[key] = got
    return dict(got)


def _market(s):
    yn, nn = pinledger.money(s, "yes_count_fp"), pinledger.money(s, "no_count_fp")
    side = "both" if yn > 0 and nn > 0 else ("yes" if yn > 0 else ("no" if nn > 0 else "-"))
    tk = s.get("ticker") or ""
    d = pinday.et_day_of_ticker(tk)
    t = _epoch(s.get("settled_time"))
    if d is None and t is not None:
        d = et_day(t)
    return {"ticker": tk, "what": describe(tk), "day": d, "t": t, "side": side,
            "contracts": round(yn if side == "yes" else (nn if side == "no" else yn + nn), 2),
            "money": pinledger.pnl(s),
            "put_in": pinledger.money(s, "yes_total_cost_dollars") + pinledger.money(s, "no_total_cost_dollars"),
            "fees": pinledger.money(s, "fee_cost"),
            "result": str(s.get("market_result") or "")}


def window(ms, label, days=None):
    """Totals over the markets `ms` (already filtered). Worst/best are single markets."""
    won = [m for m in ms if m["money"] > 0.004]
    lost = [m for m in ms if m["money"] < -0.004]
    money = sum(m["money"] for m in ms)
    put_in = sum(m["put_in"] for m in ms)
    by_day = {}
    for m in ms:
        by_day[m["day"]] = by_day.get(m["day"], 0.0) + m["money"]

    def pick(m):
        return None if m is None else {k: m[k] for k in ("ticker", "what", "day", "side", "contracts", "money")}
    return {"label": label, "days": days, "markets": len(ms), "won": len(won), "lost": len(lost),
            "flat": len(ms) - len(won) - len(lost), "hedged": sum(1 for m in ms if m["side"] == "both"),
            "money": round(money, 4), "put_in": round(put_in, 4),
            "fees": round(sum(m["fees"] for m in ms), 4),
            "return_pct": (round(100.0 * money / put_in, 2) if put_in > 0 else None),
            "worst": pick(min(ms, key=lambda m: m["money"]) if ms else None),
            "best": pick(max(ms, key=lambda m: m["money"]) if ms else None),
            "active_days": len(by_day),
            "days_up": sum(1 for v in by_day.values() if v > 0.004),
            "days_down": sum(1 for v in by_day.values() if v < -0.004)}


LONG_DAYS = 30                  # the long average day (2026-10-29): the 30 full ET days before today


def avg_day(rows):
    """The average FULL day over `rows` (a block's days_30 or all_bots' total_days_30; days_7[1:] works too):
    {"days": days counted, "money": mean $ a day, "pot_pct": mean of each day's % of what its pot held THAT day (days
    whose pot is unknown are left out of this mean only), "pct_days": days in that mean, "first": the oldest day
    counted, "young": True when the bot's first market falls inside the span (so this is every day it has)}, or None
    when no day counts.
    WHICH DAYS COUNT -- the 7-day line's rule, kept the same so the two can be read side by side: every day from the
    bot's first settled market on counts, a day with nothing settled as $0 and 0%; a day before its first market is
    left out. Kalshi's books cannot tell a paused day from a quiet one, so a paused bot's days after its pause count as
    $0 days here exactly as they do in its 7-day line (a pot emptied when it stopped has no known % those days, so
    they drop out of its % mean)."""
    ds = [r for r in rows or [] if not r.get("before_first")]
    if not ds:
        return None
    pc = [r["pot_pct"] for r in ds if r.get("pot_pct") is not None]
    return {"days": len(ds), "money": round(sum(r["money"] for r in ds) / len(ds), 4),
            "pot_pct": round(sum(pc) / len(pc), 4) if pc else None, "pct_days": len(pc),
            "first": min(r["day"] for r in ds), "young": any(r.get("before_first") for r in rows)}


def avg_words(a, n=LONG_DAYS):
    """'last 30 full days' -- or, for a bot younger than that, 'since Oct 25, 4 days' (its every full day)."""
    if a is None:
        return None
    if a["young"]:
        return "since %s, %d day%s" % (day_label(a["first"]), a["days"], "" if a["days"] == 1 else "s")
    return "last %d full days" % n


# v-tg-30d (2026-10-30, the operator: "in many places the telegram bot displays the month's gains as the spot between 7
# days and lifetime ... adding the last 30 days total would be good"): a 'last 30 days' window next to the month. It is
# the 7-day window's rule with 30: the LAST_DAYS ET days ENDING TODAY (today, still running, and the 29 calendar days
# before it), by the ET close day of each market -- calendar days (shift_day), so a 25-hour or 23-hour day is one day.
# Not LONG_DAYS' average (the 30 FULL days before today): a window's total includes today, as the 7-day one does.
LAST_DAYS = 30


def windows(ms, today):
    """today / yesterday / last 7 days / last 30 days / this month / all time, plus the per-day lists."""
    yday = shift_day(today, -1)
    week = set(shift_day(today, -k) for k in range(7))
    days30 = set(shift_day(today, -k) for k in range(LAST_DAYS))
    month = today[:7]
    out = {"today": window([m for m in ms if m["day"] == today], "Today", [today]),
           "yesterday": window([m for m in ms if m["day"] == yday], "Yesterday", [yday]),
           "last_7_days": window([m for m in ms if m["day"] in week], "Last 7 days",
                                 [shift_day(today, -6), today]),
           "last_30_days": window([m for m in ms if m["day"] in days30], "Last %d days" % LAST_DAYS,
                                  [shift_day(today, -(LAST_DAYS - 1)), today]),
           "this_month": window([m for m in ms if (m["day"] or "")[:7] == month],
                                time.strftime("%B", time.strptime(today, "%Y-%m-%d")), [month + "-01", today]),
           "all_time": window(ms, "All time", None)}
    days = sorted(set(m["day"] for m in ms if m["day"]))
    first = days[0] if days else None
    out["first_day"] = first
    out["days_7"] = []
    for k in range(7):
        d = shift_day(today, -k)
        w = window([m for m in ms if m["day"] == d], day_label(d), [d])
        out["days_7"].append({"day": d, "label": day_label(d), "markets": w["markets"], "won": w["won"],
                              "lost": w["lost"], "money": w["money"], "put_in": w["put_in"],
                              "return_pct": w["return_pct"], "before_first": first is None or d < first})
    # 2026-10-29, the operator: "For bots with 7 day average can we also add a lifetime or month average whichever is
    # better". A 30-day one (ET days), not lifetime: the rules and bet sizes changed a lot since August, so a lifetime
    # average describes old versions. The LONG_DAYS FULL ET days before today, newest first (today, still running,
    # never averages itself); a day before the bot's first settled market is before_first and left out of every
    # average, as days_7's is. attach_pots gives each its pot_pct; avg_day averages them.
    by_day = {}
    for m in ms:
        if m["day"]:
            x = by_day.setdefault(m["day"], [0, 0.0, 0.0])
            x[0] += 1
            x[1] += m["money"]
            x[2] += m["put_in"]
    out["days_30"] = []
    for k in range(1, LONG_DAYS + 1):
        d = shift_day(today, -k)
        n, mo, pi = by_day.get(d, (0, 0.0, 0.0))
        out["days_30"].append({"day": d, "markets": n, "money": round(mo, 4), "put_in": round(pi, 4),
                               "before_first": first is None or d < first})
    out["all_days"] = []
    for d in reversed(days):
        w = window([m for m in ms if m["day"] == d], day_label(d), [d])
        out["all_days"].append({"day": d, "markets": w["markets"], "won": w["won"], "lost": w["lost"],
                                "money": w["money"], "put_in": w["put_in"], "return_pct": w["return_pct"]})
    return out


# the six windows every money block has (botdata/pots.py gives each its pot %), in the order the phone shows them
WINDOW_KEYS = ("today", "yesterday", "last_7_days", "last_30_days", "this_month", "all_time")


def window_span(key, today):
    """(first ET day, ET day it ends before -- None = now) of a window; all time -> (None, None)."""
    if key == "today":
        return today, None
    if key == "yesterday":
        return shift_day(today, -1), today
    if key == "last_7_days":
        return shift_day(today, -6), None
    if key == "last_30_days":
        return shift_day(today, -(LAST_DAYS - 1)), None
    if key == "this_month":
        return today[:7] + "-01", None
    return None, None
