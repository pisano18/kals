"""test_race.py -- phone/commands/race.py (/race) against Phone.text_race on planted worlds (lane D3, rebuild step 9).

    C:\\Python314\\python.exe research\\phone\\tests\\test_race.py

The golden shadow proves the bytes on the real fixture (research/golden/shadow_race_world.py: the race-active
worlds); these check the branches a fixture may not hold: running / not running / process table unreadable, the stop
file, a fired and a not-fired stop rail, no start record, no races, legs held now and awaiting a result, and the
botstats failure that costs only the money lines.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _d36_world as W                                               # noqa: E402
import phone.commands.race as race                                   # noqa: E402
from phone import context as CX                                     # noqa: E402
from phone.html import Html                                          # noqa: E402


def _check(ph, what):
    with W.patched():
        old, new = W.old_new(ph, "/race", ph.text_race)
    W.same(old, new, what)
    return str(new)


def test_running_with_halt_and_legs():
    r = _check(W.phone(W.PlantLedger(W.results_dir())), "running")
    assert "RUNNING</b>, pid 15" in r and "STOP RAIL FIRED" in r and "holding SOL yes 98c x1" in r, r
    assert "Awaiting Kalshi's result" in r or "older leg(s)" in r, r
    assert "Money by window: could not build it (planted: botstats" in r, r
    assert r.startswith("🟢 <b>Coin race today") or r.startswith("🔴 <b>Coin race today"), r.split("\n")[0]


def test_not_running_unknown_and_stop_file():
    _check(W.phone(W.PlantLedger(W.results_dir()), procs=[]), "not running")
    r = _check(W.phone(W.PlantLedger(W.results_dir(stop=True)), procs=None), "procs unreadable + stop file")
    assert "could not be read" in r and "STOOD DOWN" in r, r


def test_no_start_record_no_races():
    r = _check(W.phone(W.PlantLedger(W.results_dir(races=False, race_log=False))), "nothing at all")
    assert "no races settled yet" in r and "Rails unknown (no start record)." in r and "none on file." in r, r


def test_money_lines_from_botstats_failure_only():
    m = race.money_lines({"err": ValueError("x" * 300)}, CX.FakeCtx(pp=W.pp))
    assert m[0] == "" and m[1].startswith("Money by window: could not build it (" + "x" * 160 + ")"), m


def test_declared():
    c = race.COMMAND
    import tgcharts
    assert c.names == ("/race",) and c.section == "one_bot" and c.help_line is None
    assert c.kind_of("/race") == tgcharts.kind_of("/race") == "bot:race"
    led = W.PlantLedger(W.results_dir())
    with W.patched():
        out = c.run(CX.FakeCtx(text="/race", now=W.T, ledger=led, pp=W.pp, markets={},
                               procs_fn=lambda: [], race30_epoch=W.RACE30, bs_get=lambda n: W._raise()))
    assert isinstance(out, Html) and "NOT RUNNING" in str(out), out


if __name__ == "__main__":
    sys.exit(W.run_tests(dict(globals()), "test_race"))
