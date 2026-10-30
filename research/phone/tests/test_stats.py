"""test_stats.py -- phone/commands/stats.py (/stats) against Phone.text_stats on planted worlds (lane D6, rebuild step 9).

    C:\\Python314\\python.exe research\\phone\\tests\\test_stats.py

Branches: nothing settled since the first live day (nothing more read); the full page with the race active and paused
(its summary line and race arms said only while it is active); the pin bot's lifetime pot from botstats read and
failing (logged, '-'); the process table unreadable / the live bot missing; no VERSIONS header; the pin bot's own size,
high-water and day-loss files present and absent.
"""
import calendar
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _d36_world as W                                               # noqa: E402
import phone.commands.stats as stats                                 # noqa: E402
from phone import context as CX                                     # noqa: E402

ORDERS = [{"tk": W.PIN_B, "t": calendar.timegm((2026, 9, 15, 14, 14, 40)), "filled": 40.0, "tau": 20, "close": None},
          {"tk": W.PIN_C, "t": calendar.timegm((2026, 9, 14, 14, 29, 30)), "filled": 20.0, "tau": 30, "close": None},
          {"tk": W.PIN_D, "t": calendar.timegm((2026, 9, 16, 12, 59, 50)), "filled": 50.0, "tau": None, "close": None}]


def _pin_pot(name, now=None, getter=None, procs=None):
    return {"money": {"all_time": {"pot": 500.0}}}


def _check(ph, what, **kw):
    with W.patched(**kw):
        old, new = W.old_new(ph, "/stats", ph.text_stats)
    W.same(old, new, what)
    return str(new)


def _ph(procs=W.PROCS, **kw):
    return W.phone(W.PlantLedger(W.results_dir(**kw), orders=list(ORDERS)), procs=procs)


def test_full_page_race_active_and_paused():
    r = _check(_ph(), "race active, pot read", bot=_pin_pot)
    assert "Coin race: " in r and "race arms" in r and "LIVE v-pinfix" in r and "Halt if the bank falls" in r, r
    r = _check(_ph(), "race paused, pot failing", active=("pin",))
    assert "Coin race: " not in r and "race arms" not in r, r


def test_process_table_and_files():
    r = _check(_ph(procs=None), "table unreadable", bot=_pin_pot)
    assert "(process table could not be read)" in r and "Paper arms: the process table could not be read." in r, r
    _check(_ph(procs=[], pin_files=False), "no live bot, no pin files", bot=_pin_pot)
    led = W.PlantLedger(W.results_dir(), orders=list(ORDERS))
    with open(os.path.join(led.results, "VERSIONS.md"), "w", encoding="utf-8") as fh:
        fh.write("no header here\n")
    r = _check(W.phone(led), "no version", bot=_pin_pot)
    assert "no readable header in VERSIONS.md" in r, r


def test_nothing_settled():
    led = W.PlantLedger(W.results_dir(races=False, pins=False))
    r = _check(W.phone(led), "empty")
    assert r == "No Kalshi settlements on file since 2026-09-08 (results/kalshi_ledger.json).", r
    c = CX.FakeCtx(text="/stats", now=W.T, ledger=led, pp=W.pp, markets={})
    assert str(stats.COMMAND.run(c)) == r               # procs, VERSIONS, botstats: not planted, never read


def test_race_summary():
    c = CX.FakeCtx(pp=W.pp)
    assert stats.race_summary(c, {}, W.RACE30) == "no real races on Kalshi's books since v-race30."


def test_declared():
    import tgcharts
    c = stats.COMMAND
    assert c.names == ("/stats",) and c.section == "money" and c.order == 30
    assert c.kind_of("/stats") == tgcharts.kind_of("/stats") == "stats" and c.help_line in W.pp.HELP_TEXT.split("\n")


if __name__ == "__main__":
    sys.exit(W.run_tests(dict(globals()), "test_stats"))
