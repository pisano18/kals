"""test_router.py -- phone/router.py: the integration flip (v-tg-rebuild step 10).

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_router.py   (exit 0 = every test passed)
What it proves (the golden replay proves the bytes of every command in 13 worlds; these cover what those never reach):
  - the chart after a reply is the declaring Command's, and the router's map is the drawing side's CMD_KIND;
  - the routing rules against the frozen legacy Phone.handle: pairing first (the message's chat), silence for another
    or no chat, the unknown-message answer, /help, a paused bot's own command (Phone.text_hidden);
  - a command module that does not import costs only its own names ('this command failed to load', logged, the rest
    answer), is tried again on the next such message, and answers once the file is fixed;
  - the help template off the declared Commands is the legacy one.
KALS_TESTING=1; no network, no real process table, nothing under results\\ read or written.
"""
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from _dlane import (CM, HEALTH, SETTLED, ORDERS, T, botstats, fake_ledger, patched, pindesk, pp, quiet, run,  # noqa: E402
                    tgcharts)
from _legacy import NEW, OLD                                         # noqa: E402
from phone import router as R                                       # noqa: E402
from phone.html import Html                                          # noqa: E402
import phone.commands.day as D                                       # noqa: E402
from _step12 import with_step12                                      # noqa: E402  (step 12's added /help lines)

def _new_since_legacy(line):
    """A /help line of a command the legacy phone never had (step 12 adds /week /month /quiet /alive ...): its first
    /name is nowhere in the legacy template. The legacy comparisons below leave those lines out."""
    import re
    m = re.match(r"(?:<code>)?(/[a-z_]+)", line)
    return bool(m) and not re.search(re.escape(m.group(1)) + r"\b", str(OLD.help_text(None)))


def _legacy_only(text):
    return "\n".join(x for x in str(text).split("\n") if not _new_since_legacy(x))


try:                                                                 # the runtime's module (step 11: phone.app)
    import phone.app as NEW_PHONE_MOD                                # noqa: E402
except ModuleNotFoundError:                                          # step 10: the runtime was pinphone's Phone
    NEW_PHONE_MOD = NEW


def _phones(active=("pin",), cfg=None):
    """(legacy Phone, new Phone) on the same planted ledger, clock, health and process table."""
    out = []
    for mod in (OLD, NEW_PHONE_MOD):
        led = fake_ledger(settled=SETTLED, orders=ORDERS, bank_at=1300.0)
        ph = mod.Phone(dict(cfg if cfg is not None else {"chat_id": 7, "secret": "s"}), mod.FakeTelegram(), ledger=led,
                       now_fn=lambda: T, health_fn=lambda: dict(HEALTH), procs_fn=lambda: [],
                       versions_path=os.path.join(tempfile.gettempdir(), "none.md"), cfg_path=os.path.join(
                           tempfile.mkdtemp(prefix="test_router_cfg_"), "telegram.json"))
        out.append(ph)
    return out


def _world(active=("pin",)):
    def boom(*a, **k):
        raise RuntimeError("planted: botstats is not asked here")
    return patched((botstats, "all_bots", boom), (botstats, "bot", boom),
                   (botstats, "active_bots", lambda procs=None, now=None: list(active)),
                   (pp, "hours_up_et_day", lambda day, until: 2.0), (D, "hours_up_et_day", lambda day, until: 2.0))


def _view(r):
    return (type(r).__name__, None if r is None else str(r))


def test_chart_kinds_are_the_charts_table():
    assert R.chart_kinds() == tgcharts.CMD_KIND, "the router's {name: kind} must be phone.charts.CMD_KIND"
    for name, kind in tgcharts.CMD_KIND.items():
        assert R.kind_of(name) == kind == tgcharts.kind_of(name), name
    for name in ("/help", "/pause", "/stop", "/open", "/speed", "/server", "/nosuch", ""):
        assert R.kind_of(name) is None and tgcharts.kind_of(name) is None, name


def test_discover_imports_every_module_once():
    assert R.discover() == {}, "a command module failed to import"
    mods = {c.module.rsplit(".", 1)[-1] for c in R.commands()}
    for m in ("status", "day", "days", "open_bets", "fills", "brief_cmd", "market", "losses", "hedges", "stats", "race",
              "racestats", "bots_page", "bot_page", "bars_cmd", "funds", "speed", "server", "features", "help_cmd",
              "pair", "mute", "controls", "update"):
        assert m in mods, m
    names = [n for c in R.commands() for n in c.names]
    assert len(names) == len(set(names)), "a name is declared twice"


def test_routing_rules_like_the_legacy_handle():
    texts = ("/help", "/HELP", "/?@kalsbot", "hello there", "", "/nosuchcommand", "/mute", "/unmute", "/stop",
             "/stop no", "/hedges", "/race", "/racestats", "/fc", "/wx", "/jb")
    with _world(("pin",)), quiet():
        for text in texts:
            old, new = _phones()
            a, b = old.handle(7, text), new.handle(7, text)
            b = type(b)(_legacy_only(b)) if b is not None else b             # step 12: new commands' /help lines
            assert _view(a) == _view(b), (text, _view(a), _view(b))
            assert old.muted == new.muted, text
            # another chat, and no paired chat: silence on both
            assert old.handle(8, text) is None and new.handle(8, text) is None, text
            o2, n2 = _phones(cfg={"chat_id": None, "secret": "s"})
            assert o2.handle(7, text) is None and n2.handle(7, text) is None, text


def test_hidden_bot_pages_like_text_hidden():
    with _world(("pin",)), quiet():
        for text in ("/race", "/racestats", "/fc", "/forecaster", "/weather", "/fx", "/jumpband", "/ladder"):
            old, new = _phones()
            a, b = old.handle(7, text), new.handle(7, text)
            assert _view(a) == _view(b) and "is not running now" in str(b), (text, _view(b))


def test_pair_first_with_the_messages_chat():
    with _world(("pin",)), quiet():
        for text, chat in (("/pair s", 99), ("/pair@kalsbot s", 99), ("/pair wrong", 99), ("/pair", 99)):
            old, new = _phones(cfg={"chat_id": None, "secret": "s"})
            refreshed = []
            new.ledger.refresh = lambda: refreshed.append(1)
            a, b = old.handle(chat, text), new.handle(chat, text)
            b = type(b)(_legacy_only(b)) if b is not None else b             # step 12: new commands' /help lines
            assert _view(a) == _view(b), (text, _view(a), _view(b))
            assert old.cfg.get("chat_id") == new.cfg.get("chat_id"), text
            assert not refreshed, "/pair runs before the ledger refresh"
            if b is not None:
                assert new.cfg["chat_id"] == 99 and new.handle(99, "/help") is not None
                with open(new.cfg_path, encoding="utf-8") as fh:
                    assert '"chat_id": 99' in fh.read()


def test_ledger_refreshed_for_commands_and_unknown_text():
    with _world(("pin",)), quiet():
        for text in ("/help", "what", "", "/mute"):
            _old, new = _phones()
            n = []
            new.ledger.refresh = lambda: n.append(1)
            new.handle(7, text)
            assert n == [1], text
            n[:] = []
            new.handle(8, text)
            assert n == [], "another chat: nothing read"


def test_help_template_is_the_legacy_one():
    from phone.commands import help_cmd as H
    R.discover()
    assert _legacy_only(H._TPL[0]) == OLD._HELP_TPL, \
        "/help off the declared commands differs from the legacy HELP_TEXT template"
    for act in ((), ("pin",), ("pin", "race", "fx", "jumpband"), None):
        assert _legacy_only(NEW.help_text(act)) == str(OLD.help_text(act)), act


def _broken_pkg(body):
    """A temp package 'zzbrokencmds' with one module (zzz.py: `body`), on sys.path; returns its folder."""
    d = tempfile.mkdtemp(prefix="test_router_pkg_")
    os.makedirs(os.path.join(d, "zzbrokencmds"))
    with open(os.path.join(d, "zzbrokencmds", "__init__.py"), "w", encoding="utf-8"):
        pass
    with open(os.path.join(d, "zzbrokencmds", "zzz.py"), "w", encoding="utf-8") as fh:
        fh.write(body)
    sys.path.insert(0, d)
    return d


BROKEN = ('raise ImportError("planted: this module is broken")\n'
          'NAMES = ("/zzz", "/zzz2")\n')
FIXED = ('from phone.command import Command, declare\n'
         'COMMAND = declare(Command(names=("/zzz", "/zzz2"), handle=lambda ctx: "zzz works"))\n')


def test_a_broken_module_costs_only_its_commands():
    d = _broken_pkg(BROKEN)
    saved = dict(R._STATE["failed"])
    try:
        from phone import command as C
        failed = C.discover("zzbrokencmds")
        assert list(failed) == ["zzbrokencmds.zzz"], failed
        R._STATE["failed"].update(failed)
        with _world(("pin",)), quiet():
            _old, new = _phones()
            r = new.handle(7, "/zzz")
            assert isinstance(r, str) and r.startswith("/zzz: this command failed to load: ImportError: planted"), r
            assert "failed to load" in new.handle(7, "/zzz2@kalsbot")
            assert "Commands" in str(new.handle(7, "/help")), "the rest of the phone answers"
            assert "I did not understand that." in str(new.handle(7, "/other")), "an unknown name is still unknown"
            with open(pindesk_log(), encoding="utf-8") as fh:
                assert "/zzz: this command failed to load" in fh.read(), "logged"
            # the file is fixed on disk: the next message imports it and the command answers (no restart)
            with open(os.path.join(d, "zzbrokencmds", "zzz.py"), "w", encoding="utf-8") as fh:
                fh.write(FIXED)
            sys.modules.pop("zzbrokencmds.zzz", None)
            r2 = new.handle(7, "/zzz")
            assert r2 == "zzz works" and "zzbrokencmds.zzz" not in R._STATE["failed"], r2
    finally:
        R._STATE["failed"].clear()
        R._STATE["failed"].update(saved)
        from phone import command as C
        for n in ("/zzz", "/zzz2"):
            C._BY_NAME.pop(n, None)
        C._BY_MODULE.pop("zzbrokencmds.zzz", None)
        sys.path.remove(d)


def test_a_broken_bot_page_module_answers_for_its_registry_commands():
    saved = dict(R._STATE["failed"])
    from phone import command as C
    keep = {n: C._BY_NAME.pop(n) for n in list(C._BY_NAME) if C._BY_NAME[n].module == "phone.commands.bot_page"}
    try:
        R._STATE["failed"]["phone.commands.bot_page"] = ImportError("planted")
        orig = R._retry_failed
        R._retry_failed = lambda: None              # the real module is fine on disk: keep it 'broken' for this test
        with _world(("pin",)), quiet():
            _old, new = _phones()
            r = new.handle(7, "/pin")
            assert isinstance(r, str) and "failed to load" in r, r
        R._retry_failed = orig
    finally:
        R._STATE["failed"].clear()
        R._STATE["failed"].update(saved)
        C._BY_NAME.update(keep)


def pindesk_log():
    from phone.log import log_path
    return log_path()


def test_error_without_a_wall_reaches_the_poll_loop():
    """A command with no `fail` that raises: the router lets it out; the poll loop answers 'error: ...' and sends no
    picture (as Phone.poll_once always did)."""
    from phone import command as C
    c = C.Command(names=("/zzboom",), handle=lambda ctx: 1 / 0)
    C._BY_NAME["/zzboom"] = c
    try:
        with _world(("pin",)), quiet():
            _old, new = _phones()
            new.charts_on = True
            queued = []
            new.chart_after = lambda chat, text: queued.append(text)
            new.tg.push(7, "/zzboom")
            new.poll_once(timeout=0)
            assert [str(m) for _c, m in new.tg.sent] == ["error: division by zero"] and queued == []
    finally:
        C._BY_NAME.pop("/zzboom", None)


if __name__ == "__main__":
    sys.exit(run(globals(), "test_router"))
