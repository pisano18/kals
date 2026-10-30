"""test_days.py -- phone/commands/days.py (/days) against Phone.text_days (v-tg-rebuild step 9, lane D1).

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_days.py   (exit 0 = every test passed)
Planted: a Ledger over several ET days, Kalshi's main-account markets, a VERSIONS.md with the pin bot's running version
(markets since it, none since it, no file), every bot's week from a hand-made all_bots dict, and botstats failing (the
main account's own table and its all-time line).
"""
import os

from _dlane import (CM, ORDERS, SETTLED, TMP, Html, botstats, boom, chart_and_help, fake_ledger, new_reply, patched,
                    phone, pindesk, pp, quiet, run, same)

import phone.commands.day as D

VERSIONS = os.path.join(TMP, "VERSIONS.md")
with open(VERSIONS, "w", encoding="utf-8") as _fh:
    _fh.write("# Versions\n\n# v-race-tie1 -- LIVE 2026-10-30 23:00Z  the coin race\n\n"
              "# v-pin-test -- LIVE 2026-10-30 20:00Z  the pin bot\nwords\n")


def market(s):
    return {"tk": s["tk"] + str(s["close"]), "day": pindesk.et_day(s["close"]), "pnl": s["pnl"], "close": s["close"],
            "n": 5.0, "paid": 4.85, "fee": 0.02, "won": s["pnl"] >= 0, "hedged": False, "hedge_pnl": None,
            "payout": 4.85 + s["pnl"]}


def day_row(k, markets_):
    return {"day": "2026-10-%02d" % (31 - k), "label": "Day %d" % k, "markets": markets_, "money": 1.5 - k,
            "pot_pct": (0.2 * k) if k % 2 else None, "return_pct": 1.1 if k % 3 else None, "lost": k % 2}


def all_bots(first="2026-10-26"):
    w = {"markets": 12, "money": 7.75, "return_pct": 1.8, "pot_pct": 0.6, "pot": 1300.0, "put_in": 400.0,
         "lost": 2, "won": 10, "partial": False}
    return {"active": ["pin", "fx"],
            "total": {"last_7_days": w, "all_time": dict(w, markets=900, money=210.0, pot_pct=18.2, pot=1150.0)},
            "bots": {b: {"money": {"first_day": first if b == "pin" else None}} for b in botstats.BOTS},
            "other": {"first_day": None}, "total_days_7": [day_row(k, k % 3) for k in range(7)],
            "total_days_30": []}


def _patches(a, ms=None):
    ms = {m["tk"]: m for m in map(market, SETTLED)} if ms is None else ms
    return [(botstats, "all_bots", (lambda now, getter, procs: a) if a is not None else boom),
            (botstats, "shown_parts", lambda a_: [(b, {"ok": True, "last_7_days": dict(a_["total"]["last_7_days"])})
                                                  for b in a_["active"]]),
            (pp, "markets_from", lambda rows, sides=None: ms),
            (pp, "hours_up_et_day", lambda day, until: 2.0), (D, "hours_up_et_day", lambda day, until: 2.0)]


def _both(ph):
    return ph.text_days(), new_reply("phone.commands.days", ph, "/days")


def test_declaration():
    (c,) = CM.of_module("phone.commands.days")
    assert c.names == ("/days",) and c.section == "money" and c.order == 20 and c.kind_of() == "days"
    chart_and_help("phone.commands.days")


def test_like_text_days():
    n = 0
    for led in (fake_ledger(settled=SETTLED, orders=ORDERS, bank_at=1250.0, deposited=1100.0),
                fake_ledger(bank_at=None, deposited=None)):
        for vp in (VERSIONS, os.path.join(TMP, "none.md")):
            ph = phone(led)
            ph.versions_path = vp
            for a in (all_bots(), all_bots(first="2026-10-29"), None):
                for ms in (None, {}):
                    with patched(*_patches(a, ms)), quiet():
                        old, new = _both(ph)
                    same(old, new, "/days versions=%s all=%s" % (os.path.basename(vp), a is not None))
                    assert isinstance(new, Html)
                    n += 1
    assert n == 2 * 2 * 3 * 2


def test_lines_present():
    ph = phone(fake_ledger(settled=SETTLED, bank_at=1250.0))
    ph.versions_path = VERSIONS
    with patched(*_patches(all_bots())):
        s = str(new_reply("phone.commands.days", ph, "/days"))
    for want in ("All bots last 7 days", "Last 7 days, every bot", "Last 7 days, by bot", "Pin bot since v-pin-test"):
        assert want in s, want
    with patched(*_patches(None)), quiet():
        s = str(new_reply("phone.commands.days", ph, "/days"))
    assert "All time" in s and "main account; ET days" in s


if __name__ == "__main__":
    raise SystemExit(run(globals(), "test_days"))
