"""test_strategy.py -- v-tg-strategy (2026-10-31; operator: "/fx should give a description and what the bot does for any
bot. Its strategy."): every registry bot carries Bot.strategy, and EVERY page that is one bot's shows it -- the bot
pages (phone/render/botcards.bs_bot_html), /race, and the paused-bot answer (router.hidden_reply, legacy
Phone.text_hidden). A bot added to research/bots without a strategy fails the registry (bots.validate) and here.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_strategy.py   (exit 0 = every test passed)
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _dlane import botstats, new_reply, patched, phone, pp, run          # noqa: E402

import _d36_world as W                                                    # noqa: E402
from phone.commands import race as _race                                   # noqa: E402,F401  (declares /race)
import bots                                                               # noqa: E402
from phone import router                                                  # noqa: E402
from phone.context import FakeCtx                                         # noqa: E402
from phone.html import esc                                                # noqa: E402
from phone.render.botcards import strategy_html                           # noqa: E402
from test_bot_page import _bot_dict                                       # noqa: E402


MAX_CHARS = 600                                                           # the sentences together, a bot


def words(name):
    """What every page of bot `name` must contain: its strategy as the shared block renders it."""
    return esc(" ".join(bots.get(name).strategy))


def test_every_bot_has_a_strategy():
    for b in bots.all_bots():
        assert bots.strategy_problem(b.strategy) is None, (b.name, bots.strategy_problem(b.strategy))
        assert 3 <= len(b.strategy) <= 6, (b.name, len(b.strategy))
        # short enough that the bot's page still fits one Telegram message (legacy check: /pin fits one message)
        assert len(" ".join(b.strategy)) <= MAX_CHARS, (b.name, len(" ".join(b.strategy)))
        assert strategy_html(b.name) == ["🧭 <b>Strategy</b>", words(b.name)], b.name
    assert strategy_html("nobody") == []


def test_the_registry_refuses_a_bot_without_one():
    base = bots.get("ladder")
    for bad in ((), ("",), ("Buys things -- fast.",), ("Buys things \u2014 fast.",), ("No full stop",), ["A list."]):
        assert bots.strategy_problem(bad), bad
        d = {f: getattr(base, f) for f in base.__dataclass_fields__}
        d.update(name="ladder2", order=99, commands=("/l2",), command="/l2", strategy=bad)
        try:
            bots.validate(list(bots.all_bots()) + [bots.spec.Bot(**d)])
        except bots.RegistryError as e:
            assert "strategy" in str(e), e
        else:
            raise AssertionError("a strategy of %r passed the registry" % (bad,))


def test_every_bot_page_shows_it():
    ph = phone()

    def bot(name, now, getter, procs):
        return _bot_dict(name)
    with patched((botstats, "bot", bot)):
        for cmd, name in pp.BOT_CMDS.items():
            new = str(new_reply("phone.commands.bot_page", ph, cmd))
            old = str(ph.text_bot(name))
            for page in (new, old):
                assert "🧭 <b>Strategy</b>\n" + words(name) + "\n" in page, (cmd, page[:600])
                assert page.index("Strategy") < page.index("⚙️ <b>Status</b>"), cmd


def test_the_race_page_shows_it():
    ph = W.phone(W.PlantLedger(W.results_dir()))
    with W.patched():
        old, new = W.old_new(ph, "/race", ph.text_race)
    W.same(old, new, "race")
    r = str(new)
    assert "🧭 <b>Strategy</b>\n" + words("race") + "\n" in r and r.index("Strategy") < r.index("How it bets"), r[:900]


def test_the_paused_answer_shows_it():
    bs = types.SimpleNamespace(SPEC=botstats.SPEC, stop_set=lambda n: True)
    ph = phone()
    for b in bots.all_bots():
        new = str(router.hidden_reply(FakeCtx(bs=bs, active=("pin",)), b.name))
        assert ("🧭 <b>Strategy</b>\n" + words(b.name) + "\n") in new and "is not running now" in new, (b.name, new)
        with patched((ph, "active", lambda: ("pin",))):
            with patched((botstats, "stop_set", lambda n: True)):
                old = str(ph.text_hidden(b.name))
        assert old == new, (b.name, old, new)


if __name__ == "__main__":
    raise SystemExit(run(globals(), "test_strategy"))
