"""test_racestats.py -- phone/commands/racestats.py (/racestats) against Phone.text_racestats on planted worlds (lane D3,
rebuild step 9).

    C:\\Python314\\python.exe research\\phone\\tests\\test_racestats.py

The golden shadow proves the bytes on the real fixture (research/golden/shadow_race_world.py); these check: no races
(nothing else read), arms running / stopped / not in the table / no log, an arm re-scored on Kalshi (fresh) and one
starred (its own log's money), the z3 bar, and the process table read through the cached reader only.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _d36_world as W                                               # noqa: E402
import phone.commands.racestats as racestats                         # noqa: E402
from phone import context as CX                                     # noqa: E402


def _check(ph, what):
    with W.patched():
        old, new = W.old_new(ph, "/racestats", ph.text_racestats)
    W.same(old, new, what)
    return str(new)


def test_arms_scored_and_starred():
    r = _check(W.phone(W.PlantLedger(W.results_dir(scored=True))), "scored")
    assert "COIN RACE STATS" in r and "z3 bar" in r and "Scored once on" in r, r
    r = _check(W.phone(W.PlantLedger(W.results_dir())), "not scored")
    assert "* = the arm's own log money (no Kalshi re-scoring on file)" in r, r


def test_process_table_states():
    _check(W.phone(W.PlantLedger(W.results_dir()), procs=[]), "no arm running")
    _check(W.phone(W.PlantLedger(W.results_dir()), procs=None), "table unreadable")
    _check(W.phone(W.PlantLedger(W.results_dir(arms=False))), "no arm logs")


def test_no_races_reads_nothing_else():
    led = W.PlantLedger(W.results_dir(races=False))
    r = _check(W.phone(led), "no races")
    assert r == "No coin-race settlements on Kalshi's books yet.", r
    c = CX.FakeCtx(text="/racestats", now=W.T, ledger=led, pp=W.pp, markets={})
    assert str(racestats.COMMAND.run(c)) == r          # procs, race30_epoch, botstats: not planted, never read


def test_cached_procs_only():
    led = W.PlantLedger(W.results_dir())
    seen = []
    c = CX.FakeCtx(text="/racestats", now=W.T, ledger=led, pp=W.pp, markets=CX.Ctx.markets(
        CX.FakeCtx(ledger=led, pp=W.pp)), race30_epoch=W.RACE30, procs_fn=lambda: seen.append(1) or W.PROCS)
    assert "PAPER ARMS" in str(racestats.COMMAND.run(c)) and seen == [1]


def test_declared():
    import tgcharts
    c = racestats.COMMAND
    assert c.names == ("/racestats",) and c.section == "one_bot" and c.help_line is None
    assert c.kind_of("/racestats") == tgcharts.kind_of("/racestats") == "bot:race"


if __name__ == "__main__":
    sys.exit(W.run_tests(dict(globals()), "test_racestats"))
