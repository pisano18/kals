"""test_help_cmd.py -- phone/commands/help_cmd.py: /help /? and the unknown-command answer, against pinphone's own.

v-tg-rebuild step 9 (2026-10-30, lane D7). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_help_cmd.py
Plain test_* functions and a tiny runner. KALS_TESTING=1; no network, no real process table (active() is planted).
"""
import itertools
import os
import sys
import time
import traceback
import types

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import bots                                                          # noqa: E402
from _legacy import pp, NEW                                         # noqa: E402  (pp: pinphone_legacy + NEW)
from phone import command as CM                                     # noqa: E402
from phone.commands import help_cmd as H                            # noqa: E402
from phone.context import Ctx, FakeCtx                               # noqa: E402
from phone.html import Html                                          # noqa: E402
import _step12 as S12                                                # noqa: E402  (step 12's added /help lines)

T = 1793448000.0
BOTS = tuple(b for b, _w in bots.HELP_BOT_LINES)
ALL_BOTS = tuple(dict.fromkeys(BOTS))


def subsets():
    yield None
    for n in range(len(ALL_BOTS) + 1):
        for c in itertools.combinations(ALL_BOTS, n):
            yield c


def test_template_is_pinphones():
    assert H.template() == pp._HELP_TPL, "the generated template differs from pinphone's HELP_TEXT template"
    assert str(H.help_html(None, pp)) == str(pp.HELP_TEXT), "the whole roster (active=None)"


def test_help_for_every_active_set():
    n = 0
    for act in subsets():
        new, old = H.help_html(act, pp), pp.help_text(act)
        assert type(new) is type(old) is Html and str(new) == str(old), act
        n += 1
    assert n == 2 ** len(ALL_BOTS) + 1


def test_help_command_and_unknown_vs_phone():
    led = types.SimpleNamespace(results=RESEARCH, refresh=lambda: None)
    for act in (("pin",), ("pin", "race", "fx"), ALL_BOTS, ()):
        ph = pp.Phone({"chat_id": 7, "secret": "s"}, pp.FakeTelegram(), ledger=led, now_fn=lambda: T)
        ph.active = lambda a=act: tuple(a)
        for text in ("/help", "/?", "/HELP", "/help@PinBotBot x"):
            c = FakeCtx(text=text, now=T, active=act, pp=pp)
            new, old = CM.by_name(c.cmd).run(c), ph.handle(7, text)
            assert type(new) is type(old) is Html and str(new) == str(old), (act, text)
        for text in ("what", "", "/nosuchcommand", "hello there", "?"):
            new = H.unknown_reply(FakeCtx(text=text, now=T, active=act, pp=pp))
            old = ph.handle(7, text)
            assert type(new) is type(old) is Html and str(new) == str(old), (act, text)
            assert str(new).startswith("I did not understand that.\n\n📱 <b>Commands</b>")


def test_from_phone_ctx_reads_active_once_like_the_phone():
    ph = pp.Phone({"chat_id": 7}, pp.FakeTelegram(), ledger=types.SimpleNamespace(results=RESEARCH), now_fn=lambda: T)
    c = Ctx.from_phone(ph, "/help")
    calls = []
    c.active = lambda: calls.append(1) or ("pin",)
    assert str(H.COMMAND.run(c)) == str(pp.help_text(("pin",))) and calls == [1]


def test_declaration():
    c = CM.of_module("phone.commands.help_cmd")
    assert len(c) == 1 and c[0].names == ("/help", "/?") and c[0].section is None and c[0].help_line is None
    import tgcharts
    for n in c[0].names:
        assert c[0].kind_of(n) is None and tgcharts.kind_of(n) is None


def _new_since_legacy(line):
    """A /help line of a command the legacy phone never had (step 12 adds /week /month /quiet /alive ...): its first
    /name is nowhere in the legacy template. They are checked on their own below; the legacy comparisons leave them out."""
    import re
    m = re.match(r"(?:<code>)?(/[a-z_]+)", line)
    return bool(m) and not re.search(re.escape(m.group(1)) + r"\b", str(pp.help_text(None)))


def test_rows_off_declared_commands_match_the_table():
    """Step 10 switches /help to the declared Commands (use_commands): every Command declared now carries exactly its
    HELP_ENTRIES row, no two rows share a place, and the template built from them (plus the rows of modules not merged
    in this tree yet) is byte-identical."""
    failed = CM.discover()
    assert not failed, failed
    allc = CM.commands()
    new = [c for c in allc if c.help_line and _new_since_legacy(c.help_line)]
    assert all(c.section in CM.SECTIONS and c.section != "one_bot" for c in new), new
    cmds = [c for c in allc if c not in new]
    rows = H.entries(cmds)
    assert rows, "no listed command declared"
    added = S12.rows()                                   # v-tg-step12 (lane R): /resume, /approve, /move -- new rows
    assert added and all(r not in H.HELP_ENTRIES for r in added)
    for r in rows:
        assert r in H.HELP_ENTRIES or r in added, "a declared Command's /help row is not in HELP_ENTRIES: %r" % (r,)
    places = [(s, o) for s, o, _l in H.HELP_ENTRIES]
    assert len(places) == len(set(places)), "two HELP_ENTRIES rows share a (section, order)"
    assert len(rows) == len(set(rows)), "two Commands declare the same /help row"
    for c in cmds:
        if c.section == "one_bot":
            assert c.help_line is None, "%s: a one-bot page's line is the registry's Bot.help" % c.name
    legacy_places = {(se, o) for se, o, _l in H.HELP_ENTRIES}
    assert not any((se, o) in legacy_places for se, o, _l in added), "a step-12 row takes a legacy row's place"
    rows = [r for r in rows if r not in added]
    merged = rows + [r for r in H.HELP_ENTRIES if r not in rows]
    assert H.template(merged) == H.template() == pp._HELP_TPL
    saved = H._TPL[0]
    try:
        H.use_commands(cmds + [CM.Command(names=("/zz_missing_%d" % i,), section=s, order=o, help_line=l,
                                          handle=lambda c: None)
                               for i, (s, o, l) in enumerate(r for r in H.HELP_ENTRIES if r not in rows)])
        assert str(H.help_html(("pin",), pp)) == S12.with_step12(pp.help_text(("pin",)))
        assert str(H.help_html(("pin",), pp)) != str(pp.help_text(("pin",))), "the step-12 lines are listed"
    finally:
        H._TPL[0] = saved
    for name, line in (("/pause", "/pause — "), ("/start", "/start — "), ("/stop", "<code>/stop yes</code>"),
                       ("/mute", "/mute · /unmute"), ("/update", "/update — "), ("/hedges", "/hedges — ")):
        c = CM.by_name(name)
        assert c is not None and c.help_line.startswith(line), name


def test_sections_order_and_section_heads():
    assert tuple(H.HEADS) == CM.SECTIONS
    assert sorted({s for s, _o, _l in H.HELP_ENTRIES}) == sorted(set(CM.SECTIONS) - {"one_bot"})


def main():
    tests = [(k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed, failed = 0, []
    t0 = time.time()
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print("  ok   %s" % name, flush=True)
        except Exception:                                       # noqa: BLE001
            failed.append(name)
            print("  FAIL %s\n%s" % (name, traceback.format_exc()), flush=True)
    print("test_help_cmd: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
