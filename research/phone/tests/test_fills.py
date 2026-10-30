"""test_fills.py -- phone/commands/fills.py (/fills /bets) against Phone.text_fills (v-tg-rebuild step 9, lane D2).

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_fills.py   (exit 0 = every test passed)
Planted: the pin bot's orders today (filled, empty, an oil-era one without a 'tau'), every other bot's fills
(botstats.fills_since: more than shown, a paused bot's, a race leg, one with no time, one from yesterday, an unread log),
no pin orders, and botstats failing (only the other bots' lines are lost, as before).
"""
import copy

from _dlane import (CM, ORDERS, T, Html, botstats, boom, chart_and_help, fake_ledger, new_reply, order_row, patched,
                    phone, quiet, run, same)

ACTIVE = ["pin", "race", "fx", "ladder"]


def _fills():
    out = [{"bot": "fx", "t": T - 60 * k, "what": "EURUSD %d" % k, "side": "yes", "act": "bought", "contracts": 10.0,
            "price": 0.42} for k in range(1, 10)]
    out += [{"bot": "race", "t": T - 30, "what": "race SOL", "side": "no", "act": "bought", "contracts": 2.5,
             "price": 0.5},
            {"bot": "forecaster", "t": T - 45, "what": "ETH 4,000", "side": "yes", "act": "sold", "contracts": 1.0,
             "price": None},
            {"bot": "ladder", "t": None, "what": "BTC rung", "side": None, "act": "bought", "contracts": 3.0,
             "price": 0.97},
            {"bot": "ladder", "t": T - 86400 * 2, "what": "BTC rung", "side": "yes", "act": "bought", "contracts": 3.0,
             "price": 0.97}]
    return sorted(out, key=lambda f: f["t"] or 0)


def _patches(fills_since=None):
    data = (_fills(), {"ladder": "HTTP 500", "weather": "no log file found", "forecaster": "unreadable"})
    return ((botstats, "active_bots", lambda procs=None: list(ACTIVE)),
            (botstats, "fills_since", fills_since or (lambda since, names: copy.deepcopy(data))))


def _both(ph, text="/fills"):
    old = ph.text_fills()
    return old, new_reply("phone.commands.fills", ph, text)


def test_declaration():
    (c,) = CM.of_module("phone.commands.fills")
    assert c.names == ("/fills", "/bets") and c.section == "now" and c.order == 30
    chart_and_help("phone.commands.fills")


def test_orders_and_other_bots_like_text_fills():
    led = fake_ledger(orders=ORDERS + [dict(order_row(T - 50, 3.0), tau=None, price=None, ask_seen=0.96),
                                       order_row(T - 86400, 5.0)])
    ph = phone(led)
    with patched(*_patches()):
        for text in ("/fills", "/bets"):
            old, new = _both(ph, text)
            same(old, new, text)
    s = str(new)
    assert isinstance(new, Html) and "Pin bot orders today: 5" in s and "(oil)" in s and "the newest 8 of 11" in s
    assert "earlier bots" in s and "could not read: ladder, earlier bots" in s and " SOL NO " in s


def test_no_pin_orders():
    ph = phone(fake_ledger())
    with patched(*_patches()):
        old, new = _both(ph)
    same(old, new, "/fills, no orders")
    assert str(new).startswith("No pin bot orders today (")


def test_botstats_fails():
    ph = phone(fake_ledger(orders=ORDERS))
    with patched(*_patches(fills_since=boom)), quiet():
        old, new = _both(ph)
    same(old, new, "/fills, botstats failing")
    assert "The other bots' fills could not be read." in str(new)


if __name__ == "__main__":
    raise SystemExit(run(globals(), "test_fills"))
