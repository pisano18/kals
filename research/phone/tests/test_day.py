"""test_day.py -- phone/commands/day.py (/today /yesterday) against Phone.text_day (v-tg-rebuild step 9, lane D1).

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_day.py   (exit 0 = every test passed)
Planted: a Ledger with closes today, yesterday and before; Kalshi's markets for the main account (so 'on the $ staked'
shows); hours up (and hours up failing); every bot's day from a hand-made all_bots dict with the pace line (and the pace
read failing); botstats failing (the warning line + the main account); botstats' clock on another day (the main
account's own page, yesterday beside today).
"""
from _dlane import (CM, DAY, SETTLED, ORDERS, T, Html, botstats, boom, chart_and_help, fake_ledger, new_reply, patched,
                    phone, pindesk, pp, quiet, run, same, tgcharts)

import phone.commands.day as M
from botdata import series


def market(day, pnl, close):
    return {"tk": "KXBTC15M-%d" % close, "day": day, "pnl": pnl, "close": close, "n": 5.0, "paid": 4.85, "fee": 0.02, "won": pnl >= 0,
            "hedged": False, "hedge_pnl": None, "payout": 4.85 + pnl}


def markets():
    today = [s for s in SETTLED if pindesk.et_day(s["close"]) == DAY]
    return {"M%d" % k: market(DAY, s["pnl"], s["close"]) for k, s in enumerate(today)}


def window(money, markets_=3, partial=False):
    return {"partial": partial, "markets": markets_, "won": max(0, markets_ - 1), "lost": min(1, markets_),
            "money": money, "return_pct": 2.5, "pot_pct": 0.31, "pot": 1350.0, "put_in": 160.0, "missing": ["ladder"]}


def all_bots(today=DAY, partial=False):
    money = {"ok": True, "first_day": "2026-10-01",
             "all_days": [{"day": "2026-10-%02d" % d, "money": 1.0 + d / 10.0} for d in range(1, 31)]}
    return {"today_et": today, "active": ["pin", "race"],
            "total": {"today": window(4.2, partial=partial), "yesterday": window(-2.0), "last_7_days": window(9.0)},
            "bots": {b: {"money": dict(money)} for b in botstats.BOTS}, "other": {"ok": True, "first_day": None}}


def _patches(a=None, up=lambda day, until: 3.5, pace=True, procs_active=("pin", "race")):
    ps = [(pp, "markets_from", lambda rows, sides=None: markets()), (pp, "hours_up_et_day", up), (M, "hours_up_et_day", up),
          (botstats, "active_bots", lambda procs=None: list(procs_active)),
          (botstats, "shown_parts", lambda a_: [(b, {"ok": True, "today": window(1.0), "yesterday": window(0.5)})
                                                for b in a_["active"]]),
          (botstats, "all_bots", (lambda now, getter, procs: a) if a is not None else boom)]
    # the legacy Phone asks tgcharts; the module botdata.series (v-tg-rebuild step 10): the same planted numbers to both
    by_now = (lambda rows, b_, day, now, n=7: (1.0, 2.5 if n == 7 else 3.1, 7 if n == 7 else 30))
    if pace:
        ps += [(tgcharts, "all_day_markets", lambda ctx: (botstats, None, ["rows"], [])), (tgcharts, "by_now", by_now),
               (series, "all_day_markets", lambda bs, now, getter=None, procs=None: (botstats, None, ["rows"], [])),
               (series, "by_now", by_now)]
    else:
        ps += [(tgcharts, "all_day_markets", boom), (series, "all_day_markets", boom)]
    return ps


def _both(ph, text):
    old = ph.text_day(*((pindesk.et_day(T), "Today") if text == "/today" else (pindesk.et_day(T - 86400), "Yesterday")))
    return old, new_reply("phone.commands.day", ph, text)


def _led():
    return fake_ledger(settled=SETTLED, orders=ORDERS, bank_at=1300.0)


def test_declaration():
    (c,) = CM.of_module("phone.commands.day")
    assert c.names == ("/today", "/yesterday") and c.section == "money" and c.order == 10
    assert (c.kind_of("/today"), c.kind_of("/yesterday")) == ("today", "yesterday")
    chart_and_help("phone.commands.day")


def test_every_bot_top_with_pace():
    ph = phone(_led())
    for kw in ({}, {"pace": False}, {"up": boom}, {"procs_active": ("pin",)}):
        for partial in (False, True):
            with patched(*_patches(all_bots(partial=partial), **kw)), quiet():
                for text in ("/today", "/yesterday"):
                    old, new = _both(ph, text)
                    same(old, new, "%s %s partial=%s" % (text, kw, partial))
                    assert isinstance(new, Html) and "All bots" in str(new)
    with patched(*_patches(all_bots())):
        s = str(new_reply("phone.commands.day", ph, "/today"))
    assert "Behind pace" not in s and "Ahead of pace" in s and "on the $" in s and "staked" in s


def test_botstats_fails():
    ph = phone(_led())
    with patched(*_patches(None)), quiet():
        for text in ("/today", "/yesterday"):
            old, new = _both(ph, text)
            same(old, new, text + ", botstats failing")
            assert "could not be read" in str(new)


def test_botstats_on_another_day_main_account_page():
    for led in (_led(), fake_ledger()):
        ph = phone(led)
        with patched(*_patches(all_bots(today="2026-10-01"))):
            for text in ("/today", "/yesterday"):
                old, new = _both(ph, text)
                same(old, new, text + ", no top")
                assert ("<i>Yesterday " in str(new)) == (text == "/today"), text


if __name__ == "__main__":
    raise SystemExit(run(globals(), "test_day"))
