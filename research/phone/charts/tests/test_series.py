"""test_series.py -- botdata.series: the 7-day and 30-day averages and the clock-change days.

v-tg-rebuild step 8 (2026-10-30): moved out of tgcharts.selftest unchanged (series' tests live here: botdata/tests is
lane A's).
"""
import calendar
import time

from pindesk import et_day, et_day_start
from botdata import series
from botdata.series import AVG_DAYS, LONG_DAYS, avg_by_day, day_avg, ledger_days, prev_day
from phone.charts.base import usd
from phone.charts.tests.planted import NOW, ck, empty_ledger, planted_ledger


def test_seven_day_lines():
    led = planted_ledger()
    today = et_day(NOW)
    avg, navg = day_avg(led, today)
    nets = dict(ledger_days(led))
    want, d = [], today
    for _ in range(AVG_DAYS):
        d = prev_day(d)
        want.append(nets.get(d, 0.0))
    ck(navg == AVG_DAYS and len(avg) == 97 and abs(avg[-1][1] - sum(want) / AVG_DAYS) < 1e-9 and avg[0][1] == 0.0,
       "/today's 7-day line: the %d days before today, ends at their mean day %s (= the ledger's own day totals)"
       % (navg, usd(avg[-1][1] if avg else None)))
    ab = avg_by_day({"2026-10-10": 7.0, "2026-10-12": 14.0}, ["2026-10-10", "2026-10-12", "2026-10-20"])
    ck(ab == {"2026-10-10": 7.0, "2026-10-12": 7.0, "2026-10-20": 0.0},
       "/days' 7-day line: a gap day counts $0, days before the first are left out: %s" % ab)
    ck(day_avg(empty_ledger(), today) == ([], 0), "/today: nothing on the books -> no 7-day line")


def test_thirty_day_lines():
    # the 30-day lines (2026-10-29): the same rule over 30 days, so a young record averages the days it has
    led = planted_ledger()
    today = et_day(NOW)
    avg, navg = day_avg(led, today)
    nets = dict(ledger_days(led))
    _a30, _n30 = day_avg(led, today, LONG_DAYS)
    _listed = [x for x in led.days() if x < today]
    ck(_n30 == len(_listed) > AVG_DAYS and abs(_a30[-1][1] - sum(nets.get(x, 0.0) for x in _listed) / _n30) < 1e-9
       and day_avg(led, today) == (avg, navg),
       "/today's 30-day line: every day on the books before today (%d, under 30 here), its mean day %s; the 7-day line "
       "unchanged" % (_n30, usd(_a30[-1][1] if _a30 else None)))
    _ab30 = avg_by_day({"2026-10-01": 30.0, "2026-10-20": 60.0}, ["2026-10-01", "2026-10-20", "2026-10-30", "2026-11-05"],
                       LONG_DAYS)
    ck(_ab30 == {"2026-10-01": 30.0, "2026-10-20": 4.5, "2026-10-30": 3.0, "2026-11-05": 2.0}
       and [prev_day(x) for x in ("2026-11-02", "2026-11-01", "2026-03-09", "2026-03-01")]
       == ["2026-11-01", "2026-10-31", "2026-03-08", "2026-02-28"]
       and avg_by_day({"2026-10-01": 30.0, "2026-10-20": 60.0}, ["2026-11-05"]) == {"2026-11-05": 0.0},
       "/days' 30-day line: that day and the 29 before, a gap day $0, days before the first left out (Oct 20: 90 / 20 "
       "days; Oct 30: 90 / 30; Nov 5: the Oct 1 day has left the 30), across the Nov 1 clock change: %s" % _ab30)


def test_by_now():
    """by_now: today so far against the average of the days before at the same quarter-hour (the /today pace words)."""
    import botstats as _bsc
    day = "2026-10-20"
    t0 = _bsc.day_start(day)
    rows = [("2026-10-19", _bsc.day_start("2026-10-19") + 3600, 2.0, "pin"),
            ("2026-10-19", _bsc.day_start("2026-10-19") + 20 * 3600, 5.0, "pin"),
            ("2026-10-18", _bsc.day_start("2026-10-18") + 1800, -1.0, "ladder"),
            (day, t0 + 600, 1.5, "pin")]
    so_far, avg, n = series.by_now(rows, _bsc, day, t0 + 2 * 3600 + 100)
    ck(so_far == 1.5 and n == 2 and abs(avg - (2.0 - 1.0) / 2) < 1e-9 and series.by_now(rows[3:], _bsc, day, t0 + 60) == (1.5, None, 0),
       "by_now: $1.50 so far vs the 2 days before at 2 AM ($2 and -$1: +$0.50 a day); no earlier day -> no average")


def test_clock_change_days():
    # 2026-10-30: the clock-change days. Every chart's day boundary is et_day_start / bs.day_start, which read the ET
    # offset at NOON until today: on 2026-11-01 (clocks back at 2 AM) that put midnight at 05:00Z, an hour late, so
    # /today and /yesterday on Nov 1 would have dropped the 12-1 AM hour; on 2026-03-08 an hour early.
    import botstats as _bsc
    _starts = {"2026-10-29": (2026, 10, 29, 4), "2026-11-01": (2026, 11, 1, 4), "2026-11-02": (2026, 11, 2, 5),
               "2026-03-08": (2026, 3, 8, 5), "2026-03-09": (2026, 3, 9, 4)}
    ck(all(et_day_start(k) == _bsc.day_start(k) == calendar.timegm(v + (0, 0)) for k, v in _starts.items()),
       "et_day_start and bs.day_start across both clock changes: Oct 29 04:00Z, Nov 1 04:00Z, Nov 2 05:00Z, Mar 8 "
       "05:00Z, Mar 9 04:00Z")
    _len = {k: (et_day_start(_bsc.shift_day(k, 1)) - et_day_start(k)) / 3600.0 for k in _starts}
    ck(_len == {"2026-10-29": 24.0, "2026-11-01": 25.0, "2026-11-02": 24.0, "2026-03-08": 23.0, "2026-03-09": 24.0}
       and all(prev_day(_bsc.shift_day(k, 1)) == k and et_day(et_day_start(k) - 1) == prev_day(k) for k in _starts),
       "prev_day and shift_day agree with the clock across both changes and the days join up (Nov 1 is 25 hours, "
       "Mar 8 is 23): %s" % _len)



def _neutral_world():
    """A fake botstats over botdata's own money / pot code: the main account (0) and the ladder's subaccount (1), with a
    deposit, a withdrawal, transfers 0 -> 1 and 1 -> 2 (between pots), and ONE trading gain in each pot."""
    import types
    import pinxfer
    from botdata import money, pots
    T = 1793000000.0                                    # 2026-10-26, a whole hour

    def row(tk, t):
        return {"ticker": tk, "settled_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t)), "market_result": "yes",
                "yes_count_fp": "50.00", "no_count_fp": "0.00", "yes_total_cost_dollars": "40.00",
                "no_total_cost_dollars": "0.00", "fee_cost": "0.50", "revenue": 5000, "value": 100}
    g0, g1 = T - 25 * 3600 + 120, T - 20 * 3600 + 60   # the two trading gains (sub 0, sub 1)
    led = {"fetched": T, "tried": T,
           "deposits": [{"amount_cents": 200000, "fee_cents": 0, "status": "applied", "created_ts": int(T - 45 * 3600),
                         "finalized_ts": int(T - 45 * 3600)}],
           "withdrawals": [{"amount_cents": 30000, "fee_cents": 0, "status": "applied", "created_ts": int(T - 15 * 3600),
                            "finalized_ts": int(T - 15 * 3600)}],
           "transfers": [{"amount_cents": 50000, "from_subaccount": 0, "to_subaccount": 1, "exchange_index": 2,
                          "created_ts": int(T - 40 * 3600)},
                         {"amount_cents": 10000, "from_subaccount": 1, "to_subaccount": 2, "exchange_index": 2,
                          "created_ts": int(T - 30 * 3600)},
                         {"amount_cents": 20000, "from_subaccount": 0, "to_subaccount": 1, "exchange_index": 2,
                          "created_ts": int(T - 10 * 3600)}]}
    c = {"ledgers": led, "subs": {"0": {"rows": {"a": row("KXA-0", g0)}}, "1": {"rows": {"b": row("KXB-1", g1)}}}}
    gain = money.market(row("KXA-0", g0))["money"]
    real = {"0": 2000.0 - 500.0 - 300.0 - 200.0 + gain, "1": 500.0 - 100.0 + 200.0 + gain}
    bs = types.SimpleNamespace(market=money.market, pot_rows=pots.pot_rows, pinxfer=pinxfer, _int=pots._int,
                               xfer_in_pot=pots.xfer_in_pot, flows=pots.flows,
                               _pot_now=lambda c_, s_, own=False: (real[s_], None))
    return bs, c, T, gain, (g0, g1), real


def test_deposit_neutral_series():
    """v-tg-neutral (step 12): a deposit, a withdrawal, a transfer between pots and a trading gain -- only the gain moves
    the line, and its last point is the real balance now."""
    from botdata.series import account_series, trading_only
    ck(trading_only([0, 10, 20, 30], [(5, 2.0), (25, -1.0), (31, 9.0)], 100.0) == [(0, 99.0), (10, 101.0), (20, 101.0),
                                                                                  (30, 100.0)],
       "trading_only: the money now minus the trading after each point (a trade after 'now' is not counted)")
    bs, c, T, gain, (g0, g1), real = _neutral_world()
    for sub, g in (("0", g0), ("1", g1)):
        raw, v, why, _each = account_series(bs, c, sub, T, window_days=3)
        pts, v2, _w, _e = account_series(bs, c, sub, T, window_days=3, neutral=True)
        ck(v == v2 == real[sub] and why is None and [t for t, _y in raw] == [t for t, _y in pts],
           "pot %s: the same hours, the pot now $%.2f" % (sub, real[sub]))
        steps = [(t, y - y0) for (t, y), (_t0, y0) in zip(pts[1:], pts[:-1]) if abs(y - y0) > 1e-9]
        ck(len(steps) == 1 and abs(steps[0][1] - gain) < 1e-9 and steps[0][0] - 3600 < g <= steps[0][0],
           "pot %s deposit-neutral: ONE step, the trading gain %s in its hour; the deposit, the withdrawal and the "
           "transfers between pots move nothing (%s)" % (sub, usd(gain), steps))
        ck(abs(pts[-1][1] - real[sub]) < 1e-9 and abs(pts[0][1] - (real[sub] - gain)) < 1e-9,
           "pot %s: the last point is the real balance now (%s), the first is it less the gain" % (sub, usd(pts[-1][1])))
        rsteps = [1 for (_t, y), (_t0, y0) in zip(raw[1:], raw[:-1]) if abs(y - y0) > 1e-9]
        ck(len(rsteps) >= 3, "pot %s: the balance as it was (raw) does jump at the money moves (%d steps)" % (sub, len(rsteps)))
    # the real pot unknown: the books' figure now is the end, the shape is the same
    bs._pot_now = lambda c_, s_, own=False: (None, "the last cash read failed")
    pts, v, why, _e = account_series(bs, c, "1", T, window_days=3, neutral=True)
    raw, _v, _w, _e = account_series(bs, c, "1", T, window_days=3)
    ck(v is None and why and abs(pts[-1][1] - raw[-1][1]) < 1e-9
       and len([1 for (_t, y), (_t0, y0) in zip(pts[1:], pts[:-1]) if abs(y - y0) > 1e-9]) == 1,
       "pot 1 unread now: the line ends at the books' figure and still steps only at the gain")


def test_status_and_funds_pictures_are_neutral():
    """/status' bank picture and /funds draw the deposit-neutral line and say so in the caption."""
    from phone.charts import build
    from phone.charts.tests.planted import planted_botstats
    led = planted_ledger()
    got = build("status", {"now": NOW, "ledger": led, "pp": None})
    ck(got is not None and "deposits and transfers removed" in got[1], "/status picture: 'deposits and transfers removed'")
    with planted_botstats(fx=True) as (_BS, _c, _procs, _td, ctx3):
        got = build("funds", ctx3)
        ck(got is not None and "deposits and transfers removed" in got[1] and "only trading does" in got[1],
           "/funds picture: deposit-neutral, and its caption says so")


TESTS = [test_seven_day_lines, test_thirty_day_lines, test_by_now, test_clock_change_days, test_deposit_neutral_series,
         test_status_and_funds_pictures_are_neutral]
