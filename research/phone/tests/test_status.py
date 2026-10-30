"""test_status.py -- phone/commands/status.py (/status /s) against Phone.text_status (v-tg-rebuild step 9, lane D1).

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_status.py   (exit 0 = every test passed)
Planted: the health reading (running with open bets, not running, the stand-down flag, the watchdog silent, the
recorders failing), the main account's bank (and none), every pot from a hand-made all_bots dict (with and without its
all-time %), the coin race sharing the main account or not, and botstats failing (both of its lines left out, logged).
"""
from _dlane import (CM, HEALTH, ORDERS, SETTLED, Html, botstats, boom, chart_and_help, fake_ledger, new_reply, patched,
                    phone, pp, quiet, run, same)

import pinflat

import phone.commands.day as D


def all_bots(pct=True, today_markets=3):
    at = {"money": 120.5, "pot_pct": 9.5 if pct else None, "pot": 1268.0}
    return {"total": {"all_time": at, "today": {"markets": today_markets, "money": -3.25,
                                                "pot_pct": -0.21 if pct else None}},
            "balances": {"all": 1390.0}}


def _patches(a, active=("pin", "race")):
    return [(botstats, "all_bots", (lambda now, getter, procs: a) if a is not None else boom),
            (botstats, "active_bots", lambda procs=None: list(active)),
            (pp, "hours_up_et_day", lambda day, until: 2.0), (D, "hours_up_et_day", lambda day, until: 2.0),
            (pinflat, "positions", lambda rows: {"KXBTC15M-26OCT310815-15": 5, "KXETH15M-26OCT310815-15": 2})]


def _both(ph, text="/status"):
    return ph.text_status(), new_reply("phone.commands.status", ph, text)


def test_declaration():
    (c,) = CM.of_module("phone.commands.status")
    assert c.names == ("/status", "/s") and c.section == "now" and c.order == 10 and c.kind_of("/s") == "status"
    chart_and_help("phone.commands.status")


def test_like_text_status():
    healths = [dict(HEALTH), dict(HEALTH, alive=True, pid=4242, quiet_s=12, watchdog_s=None),
               dict(HEALTH, alive=True, pid=4242, flag=True, open={"KXBTC15M-26OCT310815-15": 1}, kalshi_ok=False),
               dict(HEALTH, watchdog_s=300, feeds_ok=False, disk_gb=None)]
    banks = [None, {"bank": 1268.35, "size": 5}, {"bank": 900.0}]
    alls = [all_bots(), all_bots(pct=False, today_markets=0), {"total": {}}, None]
    n = 0
    for h in healths:
        for bank in banks:
            led = fake_ledger(settled=SETTLED, orders=ORDERS, bank=bank, bank_at=1250.0)
            ph = phone(led, health=h)
            for a in alls:
                for active in (("pin", "race"), ("pin",)):
                    with patched(*_patches(a, active)), quiet():
                        for text in ("/status", "/s"):
                            old, new = _both(ph, text)
                            same(old, new, "%s health=%s bank=%s all=%s active=%s" % (text, h, bank, a, active))
                            assert isinstance(new, Html)
                            n += 1
    assert n == 4 * 3 * 4 * 2 * 2


def test_lines_present():
    ph = phone(fake_ledger(settled=SETTLED, bank={"bank": 1268.35, "size": 5}), health=dict(HEALTH, alive=True))
    with patched(*_patches(all_bots())):
        s = str(new_reply("phone.commands.status", ph, "/status"))
    for want in ("Main account $1,268.35", "All pots $1,390.00", "All bots today", "Pin bot open:", "Watchdog ok"):
        assert want in s, want


if __name__ == "__main__":
    raise SystemExit(run(globals(), "test_status"))
