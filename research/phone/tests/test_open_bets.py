"""test_open_bets.py -- phone/commands/open_bets.py (/open) against Phone.text_open (v-tg-rebuild step 9, lane D2).

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_open_bets.py   (exit 0 = every test passed)
Planted: the pin bot's open positions (pinflat), every other bot's open bets (a hand-made all_bots dict: an active bot
holding bets, one unread, a paused one still holding a bet, a paused one holding none), botstats failing outright, and
failing half-way through the bots (the lines before the failure stay, as before).
"""
from _dlane import CM, HEALTH, Html, botstats, boom, chart_and_help, new_reply, patched, phone, quiet, run, same

import pinflat

TK = "KXBTC15M-26OCT301045-45"


def _bot(nm, open_, cash=100.0):
    return {"label": nm.capitalize() + " bot", "open": open_, "balance": {"dollars": cash}}


def _all_bots():
    none = {"ok": True, "count": 0}
    a = {"active": ["pin", "fx", "ladder", "jumpband"], "bots": {nm: _bot(nm, none) for nm in botstats.BOTS}}
    a["bots"]["fx"] = _bot("fx", {"ok": True, "count": 9, "at_risk": 45.5, "positions": [
        {"what": "EURUSD %d" % k, "side": "yes" if k % 2 else "no", "contracts": 10 + k, "at_risk": 4.5 + k}
        for k in range(9)]})
    a["bots"]["ladder"] = _bot("ladder", {"ok": False, "error": "HTTP 500"})
    a["bots"]["forecaster"] = _bot("forecaster", {"ok": True, "count": 1, "at_risk": 3.0, "positions": [
        {"what": "ETH above 4,000", "side": "yes", "contracts": 2.5, "at_risk": 3.0}]}, cash=None)
    return a


def _both(ph):
    return ph.text_open(), new_reply("phone.commands.open_bets", ph, "/open")


def test_declaration():
    (c,) = CM.of_module("phone.commands.open_bets")
    assert c.names == ("/open",) and c.section == "now" and c.order == 20 and c.kind_of() is None
    chart_and_help("phone.commands.open_bets")


def test_pin_and_every_pot_like_text_open():
    ph = phone(health=dict(HEALTH, alive=True))
    with patched((pinflat, "positions", lambda rows: {TK: 5, "KXETH15M-26OCT301100-00": 2}),
                 (botstats, "all_bots", lambda now, getter, procs: _all_bots())):
        old, new = _both(ph)
    same(old, new, "/open")
    s = str(new)
    assert isinstance(new, Html) and "Pin bot: 2 open" in s and "Fx bot: 9 open" in s and "Earlier bot (not running)" in s
    assert "could not read: ladder bot" in s and "EURUSD 7" in s and "EURUSD 8" not in s


def test_nothing_open():
    ph = phone()
    a = _all_bots()
    a["bots"] = {nm: _bot(nm, {"ok": True, "count": 0}) for nm in botstats.BOTS}
    with patched((botstats, "all_bots", lambda now, getter, procs: a)):
        old, new = _both(ph)
    same(old, new, "/open, none")
    assert "No open bets" in str(new)


def test_botstats_fails():
    ph = phone(health=dict(HEALTH, alive=True))
    with patched((pinflat, "positions", lambda rows: {TK: 1}), (botstats, "all_bots", boom)), quiet():
        old, new = _both(ph)
    same(old, new, "/open, botstats failing")
    assert "the other bots (Kalshi could not be read)" in str(new)


def test_fails_half_way_keeps_the_lines_before():
    ph = phone()
    a = _all_bots()
    del a["bots"]["jumpband"]                     # a KeyError after fx's lines were made
    with patched((botstats, "all_bots", lambda now, getter, procs: a)), quiet():
        old, new = _both(ph)
    same(old, new, "/open, half-way")
    order = list(botstats.BOTS)
    if order.index("fx") < order.index("jumpband"):
        assert "Fx bot: 9 open" in str(new)
    assert "the other bots (Kalshi could not be read)" in str(new)


if __name__ == "__main__":
    raise SystemExit(run(globals(), "test_open_bets"))
