"""test_market.py -- phone/commands/market.py (/market) against Phone.text_market on planted ledgers (lane D6, rebuild
step 9).

    C:\\Python314\\python.exe research\\phone\\tests\\test_market.py

Branches: sellers known / unknown; closes the pin bot bought on (with a hedge), lost the race on, passed on; other bots'
buys on those closes (botstats.fills_since planted), a log it could not read, and fills_since failing; health()'s
supply lines fresh, stale, missing, and health() raising (the block is dropped silently, as before).
"""
import calendar
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _d36_world as W                                               # noqa: E402
import phone.commands.market as market                               # noqa: E402

C0 = float(calendar.timegm((2026, 9, 16, 14, 0, 0)))     # 2026-09-16 10:00 AM ET: four quarter-hours to 10:45
CLOSES = [{"close": C0 + 900 * k, "looks": 20, "no_offer": 20 - 4 * k, "fired": k in (1, 3), "why": None,
           "gates": {"price": 3} if k == 0 else {}, "best_want": "no", "best_ticker": "KXBTC15M-26SEP161%d-15" % k}
          for k in range(4)] + [{"close": None, "looks": 0, "no_offer": 0, "fired": False, "why": "NOBODY OFFERED"}]
ORDERS = [{"close": C0 + 900, "tk": "KXBTC15M-26SEP161015-15", "filled": 40.0, "asked": 50.0, "t": C0 + 870},
          {"close": C0 + 900, "tk": "KXETHD-26SEP1611-T4500", "filled": 5.0, "asked": 5.0, "t": C0 + 871},
          {"close": C0 + 1800, "tk": "KXSOL15M-26SEP161030-30", "filled": 0.0, "asked": 30.0, "t": C0 + 1790},
          {"close": C0 + 2700, "tk": "KXXRP15M-26SEP161045-45", "filled": 12.0, "asked": 12.0, "t": C0 + 2690}]
SIGNALS = [{"tk": "KXBTC15M-26SEP161015-15", "want": "no", "t": C0 + 860},
           {"tk": "KXXRP15M-26SEP161045-45", "want": "yes", "t": C0 + 2680}]
HEDGES = [{"kind": "hedge", "status": "executed", "tk": "KXBTC15M-26SEP161015-15", "n": 4, "side": "yes"}]
FILLS = [{"bot": "race", "close": C0 + 900, "ticker": "KXCRYPTOLEAD15M-26SEP161015-SOL", "side": "yes", "contracts": 2},
         {"bot": "forecaster", "close": C0 + 2700, "ticker": "KXETH15M-26SEP161045-45", "side": "yes", "contracts": 26},
         {"bot": "ladder", "close": C0 + 2700, "ticker": "KXBTCD-26SEP1611-T1", "side": "no", "contracts": 3}]
SUPPLY = {"alive": True, "supply_lines": ["Sellers per day: 40 -> 31 (-22%)", "Depth: steady"], "supply_age_d": 1.5}


def _led(closes=CLOSES, orders=ORDERS):
    return W.PlantLedger(W.results_dir(races=False), closes=list(closes), orders=list(orders), signals=list(SIGNALS),
                         hedges=list(HEDGES))


def _check(ph, what, **kw):
    with W.patched(**kw):
        old, new = W.old_new(ph, "/market", ph.text_market)
    W.same(old, new, what)
    return str(new)


def test_full_page():
    fs = lambda since, bots: ([dict(f) for f in FILLS], {"weather": "no log file found", "fx": "unreadable"})  # noqa
    r = _check(W.phone(_led(), health_fn=lambda: dict(SUPPLY)), "full", fills_since=fs,
               active=("pin", "race", "forecaster"))
    assert "IS THE OPPORTUNITY GOING AWAY?" in r and "pin bot bought 45" in r and "+ hedge 4 YES" in r, r
    assert "LOST THE RACE" in r and "coin race 2 (SOL YES)" in r and "could not read" in r, r


def test_failures_and_stale_trend():
    _check(W.phone(_led(), health_fn=lambda: dict(SUPPLY, supply_age_d=9.0)), "stale trend + fills_since raising")
    _check(W.phone(_led(), health_fn=lambda: W._raise()), "health raising")
    _check(W.phone(_led(), health_fn=lambda: None), "health None")
    _check(W.phone(_led(closes=[], orders=[])), "no closes at all")


def test_declared():
    import tgcharts
    c = market.COMMAND
    assert c.names == ("/market",) and c.section == "now" and c.order == 40 and c.kind_of("/market") == "market"
    assert c.kind_of("/market") == tgcharts.kind_of("/market")
    assert c.help_line == "/market — how active sellers are, and which bot bought what at each of the last closes"


if __name__ == "__main__":
    sys.exit(W.run_tests(dict(globals()), "test_market"))
