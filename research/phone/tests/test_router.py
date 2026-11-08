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
    from _step12 import rows as _s12_rows                                # lane R's lines: '/pause jb' starts with an OLD name
    if line in {h for _s, _o, h in _s12_rows()}:
        return True
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


_QUOTED_RX = __import__("re").compile(r'^I did not understand that\. You sent ".*?"( as a reply to my message)?\.\n\n')


def _legacy_head(r):
    """The new unknown-message answer with its quote dropped (v-tg-unknown): the legacy first line, for the comparisons
    against the frozen phone, which never quoted."""
    if r is None:
        return r
    return type(r)(_QUOTED_RX.sub("I did not understand that.\n\n", str(r), count=1))


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
            b = _legacy_head(b)                                               # v-tg-unknown: the quote is new
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


def _log_tail(mark):
    """The log lines written after `mark` (a byte offset: _log_mark())."""
    with open(pindesk_log(), encoding="utf-8") as fh:
        fh.seek(mark)
        return fh.read()


def _log_mark():
    try:
        return os.path.getsize(pindesk_log())
    except OSError:
        return 0


# ---- v-tg-unknown (2026-11-08): what arrived is logged and quoted back; stickers get one line; edits are silent ----
from phone import incoming as I                                     # noqa: E402

HELP_TOP = "\n\n📱 <b>Commands</b>"


def _msg(chat=7, **fields):
    """One getUpdates entry holding a message with `fields` (a text, a photo, a sticker ...)."""
    m = {"message_id": 5, "date": int(T), "chat": {"id": chat, "type": "private"}, "from": {"id": chat, "is_bot": False}}
    m.update(fields)
    return {"update_id": 1, "message": m}


def _reply_to_phone(**fields):
    """A message that answers one of the phone's (reply_to_message from a bot)."""
    return dict(reply_to_message={"message_id": 4, "from": {"id": 1, "is_bot": True}, "text": "📊 Today"}, **fields)


def test_unknown_text_is_quoted_back_and_logged():
    with _world(("pin",)), quiet():
        _old, new = _phones()
        mark = _log_mark()
        r = new.handle(7, "what")
        assert isinstance(r, Html) and str(r).startswith('I did not understand that. You sent "what".' + HELP_TOP), r
        assert "I did not understand that." in str(r), "the legacy words stay (legacy_selftest looks for them)"
        assert 'not understood from chat 7: text "what"' in _log_tail(mark), _log_tail(mark)
        # the poll loop's description: a reply to a phone message says so, in the words and in the log
        mark = _log_mark()
        inc = I.describe(_msg(**_reply_to_phone(text="why")))
        r = new.handle(7, "why", about=inc)
        assert str(r).startswith('I did not understand that. You sent "why" as a reply to my message.' + HELP_TOP), r
        assert 'not understood from chat 7: text "why" (a reply to the phone\'s message)' in _log_tail(mark)
        # long, multi-line, with markup: 60 characters in the reply, 80 in the log, newlines one space, HTML escaped
        long = "<b>line one</b>\nline two " + "x" * 100
        mark = _log_mark()
        r = new.handle(7, long)
        head = str(r).split("\n\n", 1)[0]
        assert head == 'I did not understand that. You sent "&lt;b&gt;line one&lt;/b&gt; line two %s...".' % ("x" * 35), head
        line = [x for x in _log_tail(mark).splitlines() if "not understood" in x][0]
        assert '<b>line one</b> line two ' + "x" * 55 + '..."' in line and "\n" not in line and len(line) < 200, line
        # an empty message: the legacy answer, byte for byte
        _old, new = _phones()
        assert str(new.handle(7, "")).startswith("I did not understand that." + HELP_TOP)
        # a caption that is not a command: quoted like text, the log says what it captioned
        mark = _log_mark()
        inc = I.describe(_msg(photo=[{"file_id": "p"}], caption="look at this"))
        r = new.handle(7, inc.text, about=inc)
        assert str(r).startswith('I did not understand that. You sent "look at this".' + HELP_TOP), r
        assert 'not understood from chat 7: caption "look at this" on a photo' in _log_tail(mark)
        # a caption that IS a command runs it
        inc = I.describe(_msg(photo=[{"file_id": "p"}], caption="/help"))
        assert str(new.handle(7, inc.text, about=inc)).startswith("📱 <b>Commands</b>")


def test_unknown_text_never_logs_or_repeats_a_secret():
    with _world(("pin",)), quiet():
        _old, new = _phones(cfg={"chat_id": 7, "secret": "open sesame"})
        for text, shown in (("pair open sesame", "/pair"),                   # the slash forgotten: Command.echo's rule
                            ("the words are open sesame ok", "the words are [secret] ok"),
                            ("OPEN SESAME", "[secret]"),
                            ("see https://hc-ping.com/abc-123/x and http://a.b/c", "see [url] and [url]"),
                            ("alive set https://hc-ping.com/abcdef-uuid-1234", "/alive set hc-ping.com/…d-1234")):
            mark = _log_mark()
            r = new.handle(7, text)
            assert str(r).startswith('I did not understand that. You sent "%s".' % shown), (text, str(r)[:120])
            tail = _log_tail(mark)
            assert 'text "%s"' % shown in tail, (text, tail)
            for secret in ("sesame", "hc-ping.com/abc", "abcdef-uuid", "a.b/c"):
                assert secret not in tail and secret not in str(r), (text, secret)
        # /pair itself (any case, @bot) is the pairing rule's, not the unknown answer's
        assert "I did not understand" not in str(new.handle(7, "/Pair@kalsbot open sesame") or "")
        assert R.safe_text(new.ctx(), None) == "" and R.safe_text(new.ctx(), "  ") == ""


def test_media_gets_one_line_without_the_help_list():
    with _world(("pin",)), quiet():
        for fields, what, logged in (
                ({"sticker": {"file_id": "s", "emoji": "👍"}}, "a sticker", "sticker"),
                ({"photo": [{"file_id": "p"}]}, "a photo", "photo"),
                ({"photo": [{"file_id": "p"}], "forward_origin": {"type": "user"}}, "a forwarded photo",
                 "photo (forwarded)"),
                ({"voice": {"file_id": "v"}}, "a voice message", "voice"),
                ({"document": {"file_id": "d"}}, "a file", "document"),
                ({"video": {"file_id": "v"}}, "a video", "video"),
                ({"location": {"latitude": 1, "longitude": 2}}, "a location", "location"),
                (_reply_to_phone(sticker={"file_id": "s"}), "a sticker", "sticker (a reply to the phone's message)")):
            _old, new = _phones()
            n = []
            new.ledger.refresh = lambda: n.append(1)
            mark = _log_mark()
            inc = I.describe(_msg(**fields))
            r = new.handle(7, inc.text, about=inc)
            assert r == "I got %s. I only read typed commands: /help lists them." % what, (fields, r)
            assert "Commands" not in r and n == [], (fields, "no /help list, no ledger refresh")
            assert "not understood from chat 7: %s" % logged in _log_tail(mark), (fields, _log_tail(mark))
            # a stranger's sticker: silence, as every stranger's message
            assert new.handle(8, inc.text, about=I.describe(_msg(chat=8, **fields))) is None
            # the poll loop end to end: the one line is sent, no picture is queued
            _old, new = _phones()
            queued = []
            new.chart_after = lambda chat, text: queued.append(text)
            new.tg.incoming.append(_msg(**fields))
            new.poll_once(timeout=0)
            assert [str(m) for _c, m in new.tg.sent] == ["I got %s. I only read typed commands: /help lists them." % what]
            assert queued == [""], queued                 # chart_after with no text: no picture (kind_of('') is None)


def test_silent_kinds_are_never_run_or_answered_but_logged():
    with _world(("pin",)), quiet():
        updates = (
            ("edited", {"update_id": 1, "edited_message": {"chat": {"id": 7}, "date": int(T), "edit_date": int(T),
                                                           "text": "/stop yes"}}, 'edited message "/stop yes"'),
            ("service", _msg(pinned_message={"message_id": 4, "text": "📊 Today"}), "service message (pinned_message)"),
            ("callback", {"update_id": 1, "callback_query": {"id": "1", "data": "go", "message": {"chat": {"id": 7}}}},
             'callback "go"'),
            ("reaction", {"update_id": 1, "message_reaction": {"chat": {"id": 7}, "date": int(T), "new_reaction": []}},
             "reaction"),
            ("other", {"update_id": 1, "my_chat_member": {"chat": {"id": 7}}}, "unrecognised update (my_chat_member)"))
        for kind, u, logged in updates:
            inc = I.describe(u)
            assert inc.kind == kind and inc.silent, (kind, inc)
            _old, new = _phones()
            n = []
            new.ledger.refresh = lambda: n.append(1)
            mark = _log_mark()
            chat = inc.chat if inc.chat is not None else 7
            assert new.handle(chat, inc.text, about=inc) is None, kind
            assert n == [] and not new.busy, kind
            tail = _log_tail(mark)
            assert "ignored from chat %s: %s (no reply)" % (chat, logged) in tail, (kind, tail)
            # end to end through the poll loop: nothing sent
            new.tg.incoming.append(u)
            new.poll_once(timeout=0)
            assert new.tg.sent == [], kind
        # an edited /pair from a stranger while unpaired never pairs; an edited /stop yes never stops (busy stays False)
        _old, new = _phones(cfg={"chat_id": None, "secret": "s"})
        u = {"update_id": 1, "edited_message": {"chat": {"id": 99}, "date": int(T), "text": "/pair s"}}
        assert new.handle(99, "/pair s", about=I.describe(u)) is None and new.cfg.get("chat_id") is None
        # the stranger's edit is not even logged (strangers were always silence); the paired chat's is
        _old, new = _phones()
        mark = _log_mark()
        assert new.handle(8, "/stop yes", about=I.describe({"update_id": 1, "edited_message": {
            "chat": {"id": 8}, "text": "/stop yes"}})) is None
        assert "ignored from chat 8" not in _log_tail(mark)


def test_describe_every_update_kind():
    d = I.describe
    t = d(_msg(text="/today"))
    assert (t.kind, t.text, t.chat, t.sent_at, t.reply, t.forwarded) == ("text", "/today", 7, int(T), False, False)
    assert d(_msg(**_reply_to_phone(text="x"))).reply is True
    assert d(_msg(text="x", reply_to_message={"from": {"id": 7, "is_bot": False}, "text": "y"})).reply is False, \
        "a reply to the operator's own message is not a reply to the phone's"
    assert d(_msg(text="x", forward_date=1)).forwarded is True
    c = d(_msg(video={"file_id": "v"}, caption="  hi "))
    assert (c.kind, c.text, c.keys) == ("caption", "  hi ", ("video",))
    assert d(_msg(video={"file_id": "v"}, caption="   ")).kind == "video", "a blank caption is no caption"
    for key in ("sticker", "photo", "voice", "video_note", "video", "animation", "document", "audio", "contact",
                "location", "venue", "poll", "dice", "game", "story"):
        inc = d(_msg(**{key: {}}))
        assert inc.kind == key and not inc.is_text and not inc.silent and I.words(inc).startswith(("a ", "an ")), key
    assert I.words(d(_msg(photo=[], forward_origin={}))) == "a forwarded photo"
    assert I.words(d(_msg(audio={}, forward_origin={}))) == "a forwarded audio file"
    s = d(_msg(new_chat_members=[{"id": 1}]))
    assert (s.kind, s.keys, s.silent) == ("service", ("new_chat_members",), True)
    assert d(_msg()).kind == "other" and d({"update_id": 3}).kind == "other" and d(None).kind == "other"
    assert d({"update_id": 3, "poll": {"id": "1"}}).keys == ("poll",), "an update-level poll is not a message's"
    e = d({"update_id": 1, "edited_message": {"chat": {"id": 7}, "date": 5, "edit_date": 9, "text": "/x"}})
    assert (e.kind, e.text, e.chat, e.sent_at) == ("edited", "/x", 7, 5)
    assert d({"update_id": 1, "channel_post": {"chat": {"id": -1}, "text": "x"}}).kind == "text"
    assert I.quote("a\n\n  b\tc", 60) == "a b c" and I.quote("x" * 70, 60) == "x" * 60 + "..." and I.quote(None) == ""
    assert I.quote("abcd efgh", 5) == "abcd..."
    assert I.line(d(_msg(text="")), "") == "text (empty)"
    assert I.line(d(_msg(sticker={})), None) == "sticker"
    assert I.line(d(_msg(**_reply_to_phone(voice={}, forward_date=1))), None) == \
        "voice (forwarded; a reply to the phone's message)"
    assert set(I.KINDS) >= {"text", "caption", "sticker", "photo", "edited", "callback", "reaction", "service", "other"}


def test_keyboard_forms_of_a_command_are_the_command():
    from phone.context import split_command
    for text in ("/Today", "/today ", " /today", "/today@kalsbot", "/TODAY@KalsBot ", "📊 /today", "📊/today",
                 "• /today", "/today.", "/Today!", "/today@kalsbot.", " 📊 /today"):
        _t, cmd, arg = split_command(text)
        assert cmd == "/today" and arg == "", (text, cmd, arg)
    assert split_command("/Stop@kalsbot yes")[1:] == ("/stop", "yes")
    assert split_command("⏹ /stop yes")[1:] == ("/stop", "yes")
    assert split_command("/?")[1] == "/?" and split_command("/?.")[1] == "/?" and split_command("/")[1] == "/"
    assert split_command("hello /today")[1] == "hello", "words before the slash are not guessed at"
    assert split_command("📊 today")[1] == "📊", "no slash: not a command"
    assert split_command("/server help")[1:] == ("/server", "help")
    with _world(("pin",)), quiet():
        _old, new = _phones()
        want = str(new.handle(7, "/help"))
        for text in ("/Help", "/help ", "/help@kalsbot", "📱 /help", "📱/help", "/help.", "/HELP@KalsBot."):
            _old, new = _phones()
            assert str(new.handle(7, text)) == want, text
        _old, new = _phones()
        assert "I did not understand that." in str(new.handle(7, "hello /help")), "still unknown"


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
