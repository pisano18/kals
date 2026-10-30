"""test_windows30.py -- the 'last 30 days' money window (v-tg-30d, rebuild step 12, 2026-10-30).

The operator: "in many places the telegram bot displays the month's gains as the spot between 7 days and lifetime ...
adding the last 30 days total would be good". The window is the 7-day window's rule with 30: the 30 ET days ENDING
TODAY (today and the 29 calendar days before it), by each market's ET close day; its pot is what the pot held at
midnight ET starting the first of those days (+ money moved in during the window), DST-safe through botdata.clock.
Run:  C:\\Python314\\python.exe research\\botdata\\tests\\test_windows30.py   (or research\\botstats.py --selftest)
"""
import calendar
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import ck, run                                            # noqa: E402

from botdata import money, pots                                     # noqa: E402
from botdata.clock import day_start, shift_day                      # noqa: E402


def _m(day, money_=1.0, put_in=10.0):
    return {"ticker": "KXT-" + day, "what": "t " + day, "day": day, "t": float(day_start(day) + 3600), "side": "yes",
            "contracts": 1.0, "money": money_, "put_in": put_in, "fees": 0.0, "result": "yes"}


def test_window_keys_and_order():
    ck(money.WINDOW_KEYS == ("today", "yesterday", "last_7_days", "last_30_days", "this_month", "all_time"),
       "WINDOW_KEYS: today, yesterday, 7 days, 30 days, the month, all time -- the order every page shows")
    ck(money.LAST_DAYS == 30, "LAST_DAYS is 30")


def test_boundaries_plain_day():
    today = "2026-10-30"
    ms = [_m("2026-09-30", 100.0), _m("2026-10-01", 1.0), _m("2026-10-15", 2.0), _m(today, 4.0)]
    w = money.windows(ms, today)
    x = w["last_30_days"]
    ck(x["label"] == "Last 30 days" and x["days"] == ["2026-10-01", today],
       "the window is named 'Last 30 days' and spans Oct 1 .. Oct 30 (30 ET days ending today)")
    ck(x["markets"] == 3 and abs(x["money"] - 7.0) < 1e-9,
       "Oct 1 (today - 29) is in, Sep 30 (today - 30) is out, today counts (%r)" % x["money"])
    ck(money.window_span("last_30_days", today) == ("2026-10-01", None), "window_span: from Oct 1, running to now")
    ck(w["this_month"]["money"] == 7.0 and w["last_7_days"]["money"] == 4.0 and w["all_time"]["money"] == 107.0,
       "the month, the 7 days and all time are unchanged beside it")


def test_boundaries_across_the_clock_change():
    # 2026-11-01: the clocks go back at 2 AM (a 25-hour ET day). The window is calendar days, never 30 x 86400 s.
    today = "2026-11-01"
    ms = [_m("2026-10-02", 100.0), _m("2026-10-03", 1.0), _m("2026-10-31", 2.0), _m(today, 4.0)]
    x = money.windows(ms, today)["last_30_days"]
    ck(x["days"] == ["2026-10-03", today] and x["markets"] == 3 and abs(x["money"] - 7.0) < 1e-9,
       "on Nov 1 (25 hours) the window is Oct 3 .. Nov 1: Oct 3 in, Oct 2 out")
    first, end = money.window_span("last_30_days", today)
    ck(first == "2026-10-03" and end is None and day_start(first) == calendar.timegm((2026, 10, 3, 4, 0, 0)),
       "its start is midnight EDT on Oct 3 (04:00Z)")
    # a few days later the window spans the change: still 30 calendar days, its start still midnight EDT
    today = "2026-11-05"
    ms = [_m("2026-10-06", 100.0), _m("2026-10-07", 1.0), _m("2026-11-01", 2.0), _m("2026-11-02", 4.0)]
    x = money.windows(ms, today)["last_30_days"]
    ck(x["days"][0] == "2026-10-07" and x["markets"] == 3 and abs(x["money"] - 7.0) < 1e-9
       and day_start(money.window_span("last_30_days", today)[0]) == calendar.timegm((2026, 10, 7, 4, 0, 0)),
       "on Nov 5 the window is Oct 7 .. Nov 5 across the change (Oct 6 out), from Oct 7 04:00Z")
    # and in March, across the 23-hour day
    x = money.windows([_m("2026-02-07", 9.0), _m("2026-02-08", 1.0), _m("2026-03-08", 2.0)], "2026-03-09")["last_30_days"]
    ck(x["days"] == ["2026-02-08", "2026-03-09"] and abs(x["money"] - 3.0) < 1e-9,
       "on Mar 9 the window is Feb 8 .. Mar 9 across the 23-hour Mar 8 (Feb 7 out)")


def test_pot_of_the_window():
    # what the pot held when the window began: now - settled in the window - money moved in since its start, + the money
    # moved in during it (pot_for's 'start' rule, the same as the 7-day window's)
    today = "2026-11-01"
    t_in = day_start("2026-10-20") + 600
    t_before = day_start("2026-10-03") - 1                            # a second before the window: not in it
    led = {"fetched": 1.0, "deposits": [], "withdrawals": [],
           "transfers": [{"created_ts": t_in, "amount_cents": 10000, "to_subaccount": 1, "from_subaccount": 0},
                         {"created_ts": t_before, "amount_cents": 5000, "to_subaccount": 1, "from_subaccount": 0}]}
    ctx = {"today": today, "led": led, "as_of": None, "stale_why": None,
           "subs": {"1": {"now": 1000.0, "why": None, "complete": True,
                          "days": {"2026-10-02": 50.0, "2026-10-03": 20.0, today: 10.0}}}}
    pot, kind, why = pots.pot_for(ctx, "1", "last_30_days")
    ck(kind == "start" and why is None and abs(pot - 970.0) < 1e-9,
       "the 30-day pot = 1000 now - 30 settled in the window - 100 moved in, + that 100 = $970 (the transfer a "
       "second before the window is the pot's own money at its start) (%r)" % pot)
    blk = {"last_30_days": dict(money.window([_m("2026-10-03", 20.0), _m(today, 10.0)], "Last 30 days"))}
    pots.attach_pots(blk, ctx, "1")
    ck(abs(blk["last_30_days"]["pot_pct"] - round(100.0 * 30.0 / 970.0, 2)) < 1e-9,
       "attach_pots gives the 30-day window its % of that pot")


if __name__ == "__main__":
    raise SystemExit(run(globals(), "test_windows30"))
