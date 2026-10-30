"""test_reports.py -- the weekly and monthly reports (v-tg-rebuild step 12, lane Q): botdata/period.py's spans and money
(by bot, % of each pot and of all pots, best / worst day, losses), phone/reports.py's page, /week and /month (and 'last'),
and phone/monitor.py's schedule: Sunday 8 PM ET this week, the 1st 8 AM ET the month just ended, each once, a report
already due when the phone starts marked done (never sent late).

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_reports.py   (exit 0 = every test passed)
Planted markets and pots; a fake clock. KALS_TESTING=1; no network, no Kalshi.
"""
import calendar
import os
import sys
import tempfile
import time
import traceback
import types

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import botstats                                                      # noqa: E402
from botdata import period, paths                                    # noqa: E402
from botdata import tables                                           # noqa: E402
from phone import command as CM                                      # noqa: E402
from phone import log as plog                                        # noqa: E402
from phone import monitor as M                                       # noqa: E402
from phone import reports as R                                       # noqa: E402
from phone.context import FakeCtx                                    # noqa: E402

TMP = tempfile.mkdtemp(prefix="test_reports_")
paths.set_results(TMP)
plog.set_path(lambda: os.path.join(TMP, "pinphone.log"), replace=True)


def et(y, mo, d, h, mi=0):
    """An ET wall-clock time in late Oct / early Nov 2026 -> epoch (EDT until Nov 1 06:00Z)."""
    t = calendar.timegm((y, mo, d, h, mi, 0))
    return t + (4 if t + 4 * 3600 < calendar.timegm((2026, 11, 1, 6, 0, 0)) else 5) * 3600


def mk(day, money, what="BTC 9:15 PM"):
    return {"day": day, "money": money, "what": what, "t": 0, "ticker": "KX-" + day}


def pctx(now_v=1000.0):
    return {"led": {}, "as_of": None, "today": "2026-10-30",
            "subs": {s: {"now": now_v, "why": None, "days": {}, "complete": True} for s in tables.SUBS}}


def test_spans():
    assert period.weeks("2026-10-30") == (("2026-10-26", "2026-11-01"), ("2026-10-19", "2026-10-25"))
    assert period.weeks("2026-11-01") == (("2026-10-26", "2026-11-01"), ("2026-10-19", "2026-10-25"))     # Sunday
    assert period.weeks("2026-10-30", "last") == (("2026-10-19", "2026-10-25"), ("2026-10-12", "2026-10-18"))
    assert period.months("2026-10-30") == (("2026-10-01", "2026-10-31"), ("2026-09-01", "2026-09-30"))
    assert period.months("2026-11-01", "last") == (("2026-10-01", "2026-10-31"), ("2026-09-01", "2026-09-30"))
    assert period.months("2027-01-01", "last") == (("2026-12-01", "2026-12-31"), ("2026-11-01", "2026-11-30"))
    assert period.days_in("2026-10-26", "2026-11-01", "2026-10-30") == 5
    assert period.days_in("2026-10-26", "2026-11-01") == 7 and period.days_in("2026-11-02", "2026-11-08", "2026-11-01") == 0


def test_span_money_pots_days_losses():
    ms = [("pin", mk("2026-10-26", 10.0)), ("pin", mk("2026-10-27", -40.0, "ETH 2:15 PM")),
          ("ladder", mk("2026-10-27", 5.0)), ("ladder", mk("2026-10-29", 25.0)), ("earlier", mk("2026-10-28", -2.0)),
          ("pin", mk("2026-10-25", 99.0))]                                       # the day before: not in it
    sp = period.span(ms, pctx(), "2026-10-26", "2026-11-01", botstats)
    assert sp["money"] == -2.0 and sp["markets"] == 5 and sp["lost"] == 2 and sp["money_lost"] == -42.0, sp
    assert sp["by_bot"]["pin"]["money"] == -30.0 and sp["by_bot"]["pin"]["lost"] == 1
    assert sp["by_bot"]["pin"]["pot"] == 1000.0 and sp["by_bot"]["pin"]["pot_pct"] == -3.0
    assert sp["by_bot"]["earlier"]["pot_pct"] is None
    assert sp["best"] == ("2026-10-29", 25.0) and sp["worst_day"] == ("2026-10-27", -35.0)
    assert sp["worst"]["bot"] == "pin" and sp["worst"]["money"] == -40.0
    assert sp["pot"] == len(tables.SUBS) * 1000.0                         # nothing settled in pctx's days: all now


def _report(today="2026-10-30"):
    ms = [("pin", mk("2026-10-26", 10.0)), ("pin", mk("2026-10-27", -40.0, "ETH 2:15 PM")),
          ("ladder", mk("2026-10-29", 25.0)), ("pin", mk("2026-10-20", 30.0)), ("ladder", mk("2026-10-21", 5.5))]
    p = pctx()
    d = {"now": 0, "today": today, "this": period.span(ms, p, "2026-10-26", "2026-11-01", botstats),
         "prev": period.span(ms, p, "2026-10-19", "2026-10-25", botstats), "missing": [], "order": ["pin", "ladder"],
         "kind": "week", "which": "this"}
    return d


def test_the_page():
    s = str(R.report_html(_report()))
    lines = s.split("\n")
    assert lines[0] == "📅 <b>THIS WEEK -$5.00 (-0.08% of all pots)</b> · Mon Oct 26 to Sun Nov 1 (today so far)", lines[0]
    assert lines[1] == ("vs the week before: +$35.50 (+0.59%) · a day -$1.00 now, +$5.07 then (<b>$6.07 a day "
                        "worse</b>)"), lines[1]
    assert "<pre>Bot        Money  % pot  Before Lost\nPin bot  -$30.00  -3.0% +$30.00    1\nLadder   +$25.00 " \
           " +2.5%  +$5.50    0\nAll bots  -$5.00 -0.08% +$35.50    1</pre>" in s, s
    assert "📈 Best day <b>Thu Oct 29 +$25.00</b> · 📉 worst day <b>Tue Oct 27 -$40.00</b> (of 3 days with a market)" in s
    assert ("🔴 Losses: 1 market lost, -$40.00 in all (0 the week before); the worst: Pin bot ETH 2:15 PM on Tue Oct "
            "27, <b>-$40.00</b>") in s, s
    d = _report(today="2026-11-02")                                          # the week is over: no 'so far'
    assert str(R.report_html(d)).startswith("📅 <b>WEEK -$5.00")
    d["kind"] = "month"
    assert R.titles(d)[0] == "OCTOBER" and R.titles(d)[3] == "Oct"


def test_week_and_month_commands():
    (w,) = [c for c in CM.of_module("phone.commands.week") if c.name == "/week"]
    (m,) = [c for c in CM.of_module("phone.commands.week") if c.name == "/month"]
    assert w.section == m.section == "money" and w.kind_of("/week") is None and "/week last" in w.examples
    import phone.commands.week as W
    asked = []
    saved = W.build
    W.build = lambda bs, now, kind, which, getter=None, procs=None: asked.append((kind, which, getter, procs)) or \
        _report()
    try:
        for text in ("/week", "/week last", "/month", "/month LAST"):
            ctx = FakeCtx(text=text, now=1793370120.0, bs=botstats, bs_getter="G", bs_procs="P")
            assert str((w if text.startswith("/week") else m).run(ctx)).startswith("📅")
    finally:
        W.build = saved
    assert asked == [("week", "this", "G", "P"), ("week", "last", "G", "P"), ("month", "this", "G", "P"),
                     ("month", "last", "G", "P")], asked
    boom = FakeCtx(text="/week", now=1.0, bs=types.SimpleNamespace())             # botstats unreadable: the wall
    assert str(w.run(boom)).startswith("Could not build the report: ")


def test_the_schedule():
    sent, made = [], []
    saved = M.report_msg
    M.report_msg = lambda ctx, now, kind, which: made.append((kind, which, now)) or "%s %s" % (kind, which)
    try:
        st = types.SimpleNamespace()
        ctx = FakeCtx(now=0)
        tick = lambda t: M.check_reports(ctx, M.state_of(st), lambda msg, urgent=False: sent.append((msg, urgent)), t)  # noqa: E731
        tick(et(2026, 11, 1, 20, 30))            # the phone starts on a Sunday after 8 PM: due, marked done, not sent
        tick(et(2026, 11, 1, 21, 0))
        assert sent == [] and M.state_of(st).weekly == "2026-11-01"
        st2 = types.SimpleNamespace()
        tick2 = lambda t: M.check_reports(ctx, M.state_of(st2), lambda msg, urgent=False: sent.append((msg, urgent)), t)  # noqa: E731
        tick2(et(2026, 10, 31, 23, 0))           # Saturday night: learns, nothing due
        tick2(et(2026, 11, 1, 7, 59))
        assert sent == []
        tick2(et(2026, 11, 1, 8, 0))             # the 1st, 8 AM: the month just ended
        assert sent == [("month last", False)], sent
        tick2(et(2026, 11, 1, 19, 59))
        tick2(et(2026, 11, 1, 20, 0))            # Sunday 8 PM: this week
        assert sent[-1] == ("week this", False) and len(sent) == 2
        for h in (20, 21, 23):
            tick2(et(2026, 11, 1, h, 30))
        assert len(sent) == 2                    # once each
        tick2(et(2026, 11, 8, 20, 1))            # next Sunday
        assert sent[-1] == ("week this", False) and len(sent) == 3
    finally:
        M.report_msg = saved


def main():
    tests = [(k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed, failed = 0, []
    t0 = time.time()
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print("  ok   %s" % name, flush=True)
        except Exception:                                       # noqa: BLE001
            failed.append(name)
            print("  FAIL %s\n%s" % (name, traceback.format_exc()), flush=True)
    print("test_reports: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
