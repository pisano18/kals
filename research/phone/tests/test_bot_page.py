"""test_bot_page.py -- phone/commands/bot_page.py (one page a registry bot) against Phone.text_bot (v-tg-rebuild step 9,
lane D2).

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_bot_page.py   (exit 0 = every test passed)
The golden worlds have the forecaster and the weather seller paused (their pages are the router's 'hidden' answer
there), so every bot's page is compared here on a planted botstats dict, and with botstats failing (the old wall).
"""
from _dlane import CM, Html, botstats, boom, chart_and_help, new_reply, patched, phone, pp, quiet, run, same

import bots


def _bot_dict(name):
    b = bots.get(name)
    return {"name": name, "label": b.label, "what": b.what, "subaccount": b.pots[0].sub,
            "subaccounts": sorted({p.sub for p in b.pots}), "shares_subaccount_with": [],
            "running": {"alive": True, "pid": 11, "started_et": "Oct 30 9:00 AM ET", "stop_flag": False,
                        "stop_flag_et": None, "stop_flag_text": None, "halted": None, "problems": ["odd thing"],
                        "log": "x.jsonl", "log_last_et": "Oct 30 10:39 AM ET", "log_age_s": 42, "version": "v-test",
                        "version_et": "Oct 29 8:00 PM ET", "settings_text": "size 5", "keepalive": "boot_all.ps1"},
            "money": {"ok": False, "error": "HTTP 500"},
            "open": {"ok": True, "count": 0, "at_risk": 0.0, "positions": []},
            "balance": {"ok": True, "dollars": 123.45, "note": "its own pot", "by_sub": None},
            "last_settled": [],
            "activity_today": {"ok": False, "note": "no log yet"}}


def test_declaration_is_bot_cmds():
    cs = CM.of_module("phone.commands.bot_page")
    assert sorted(n for c in cs for n in c.names) == sorted(pp.BOT_CMDS)
    for c in cs:
        name = pp.BOT_CMDS[c.names[0]]
        assert c.names[0] == pp.BOT_CMD_OF[name] and all(pp.BOT_CMDS[n] == name for n in c.names)
        assert c.section == "one_bot" and c.help_line is None and c.kind_of() == "bot:" + name
        assert c.order == bots.get(name).order
    chart_and_help("phone.commands.bot_page")


def test_every_page_like_text_bot():
    ph = phone()

    def bot(name, now, getter, procs):
        return _bot_dict(name)
    with patched((botstats, "bot", bot)):
        for cmd, name in pp.BOT_CMDS.items():
            old, new = ph.text_bot(name), new_reply("phone.commands.bot_page", ph, cmd)
            same(old, new, cmd)
            assert isinstance(new, Html) and "COULD NOT READ KALSHI" in str(new)
            if pp.PAGE_FOOTER.get(name):
                assert str(new).endswith(pp.i_(pp.PAGE_FOOTER[name])), cmd


def test_botstats_fails_like_the_old_wall():
    ph = phone()
    with patched((botstats, "bot", boom)), quiet():
        for cmd, name in pp.BOT_CMDS.items():
            old, new = ph.text_bot(name), new_reply("phone.commands.bot_page", ph, cmd)
            same(old, new, cmd)
            assert isinstance(new, str) and new.startswith("Could not build %s: planted failure" % pp.BOT_CMD_OF[name])


if __name__ == "__main__":
    raise SystemExit(run(globals(), "test_bot_page"))
