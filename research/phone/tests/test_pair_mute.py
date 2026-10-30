"""test_pair_mute.py -- phone/commands/pair.py (/pair) and mute.py (/mute /unmute) against Phone.handle.

v-tg-rebuild step 9 (2026-10-30, lane D7). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_pair_mute.py
KALS_TESTING=1; the config is a temp file; active() is planted (no process table).
"""
import json
import os
import sys
import tempfile
import time
import traceback
import types

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import pinphone as pp                                                # noqa: E402
from phone import command as CM                                     # noqa: E402
from phone.commands import mute as M                                # noqa: E402
from phone.commands import pair as P                                # noqa: E402
from phone.context import Ctx, FakeCtx                               # noqa: E402
from phone.html import Html                                          # noqa: E402

T = 1793448000.0
TMP = tempfile.mkdtemp(prefix="test_pair_mute_")
pp.LOG = os.path.join(TMP, "pinphone.log")                          # log() lines land here, never in results\


def _phone(cfg, path, act=("pin", "fx")):
    led = types.SimpleNamespace(results=TMP, refresh=lambda: None)
    ph = pp.Phone(cfg, pp.FakeTelegram(), ledger=led, cfg_path=path, now_fn=lambda: T)
    ph.active = lambda: tuple(act)
    return ph


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def _log_tail():
    return (_read(pp.LOG) or "").splitlines()[-1:]


def test_pair_vs_phone():
    for text, chat in (("/pair open sesame", 5), ("/pair@PinBotBot open sesame", 5), ("/pair   open sesame  ", 9),
                       ("/pair wrong", 5), ("/pair", 5), ("/pair  ", 5), ("/PAIR open sesame", 6)):
        out = []
        for side in ("old", "new"):
            path = os.path.join(TMP, "%s-telegram.json" % side)
            if os.path.exists(path):
                os.remove(path)
            ph = _phone({"chat_id": None, "secret": "open sesame", "token": "x"}, path)
            if side == "old":
                r = ph.handle(chat, text)
            else:
                c = Ctx.from_phone(ph, text, chat_id=chat)
                c.active = ph.active
                r = CM.by_name("/pair").run(c)
            out.append((type(r).__name__, None if r is None else str(r), dict(ph.cfg), _read(path),
                        [x.split("  ", 1)[1] for x in _log_tail()]))
        assert out[0] == out[1], (text, out)


def test_pair_right_and_wrong_words():
    path = os.path.join(TMP, "t.json")
    cfg = {"chat_id": None, "secret": " s3 "}
    c = FakeCtx(text="/pair s3", now=T, active=("pin",), pp=pp, cfg=cfg, cfg_path=path, chat_id=42)
    r = P.handle(c)
    assert isinstance(r, Html) and str(r).startswith("<b>Paired.</b> This chat now controls the bot.\n\n📱 <b>Commands</b>")
    assert cfg["chat_id"] == 42 and json.loads(_read(path))["chat_id"] == 42
    cfg2 = {"chat_id": 1, "secret": "s3"}
    assert P.handle(FakeCtx(text="/pair nope", now=T, pp=pp, cfg=cfg2, cfg_path=path, chat_id=9)) is None
    assert P.handle(FakeCtx(text="/pair", now=T, pp=pp, cfg=cfg2, cfg_path=path, chat_id=9)) is None
    assert cfg2["chat_id"] == 1, "a wrong secret pairs nothing"


def test_pair_save_failure_is_logged_not_raised():
    bad = os.path.join(TMP, "no-such-dir", "x", "telegram.json")
    cfg = {"secret": "k"}
    r = P.handle(FakeCtx(text="/pair k", now=T, active=(), pp=pp, cfg=cfg, cfg_path=bad, chat_id=3))
    assert isinstance(r, Html) and cfg["chat_id"] == 3
    assert any("could not save config" in x for x in (_read(pp.LOG) or "").splitlines())


def test_pair_declaration():
    c = CM.by_name("/pair")
    assert c.names == ("/pair",) and c.section is None and c.needs_ledger is False and c.kind_of() is None


def test_mute_vs_phone():
    for seq in (["/mute"], ["/unmute"], ["/mute", "/mute", "/unmute"], ["/Mute@PinBotBot", "/unmute x"]):
        ph = _phone({"chat_id": 7}, os.path.join(TMP, "m.json"))
        st = types.SimpleNamespace(muted=False)
        for text in seq:
            old = ph.handle(7, text)
            new = CM.by_name(Ctx.from_phone(ph, text).cmd).run(FakeCtx(text=text, state=st))
            assert type(old) is type(new) is Html and str(old) == str(new), text
            assert ph.muted is st.muted, text


def test_mute_words_and_declaration():
    st = types.SimpleNamespace(muted=False)
    assert str(M.handle(FakeCtx(text="/mute", state=st))) == "🔕 Alerts off. /unmute to turn them back on." and st.muted
    assert str(M.handle(FakeCtx(text="/unmute", state=st))) == "🔔 Alerts on." and not st.muted
    c = CM.by_name("/unmute")
    assert c is CM.by_name("/mute") and c.section == "controls" and c.order == 40 and c.kind_of("/unmute") is None


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
    print("test_pair_mute: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
