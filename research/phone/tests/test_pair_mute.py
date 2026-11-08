"""test_pair_mute.py -- phone/commands/pair.py (/pair) and mute.py (/mute /unmute) against Phone.handle.

v-tg-rebuild step 9 (2026-10-30, lane D7). Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_pair_mute.py
KALS_TESTING=1; the config is a temp file; active() is planted (no process table).
v-tg-pairlock (2026-11-07): once paired, another chat's right secret only ASKS (the paired chat must reply /pair allow
within 2 minutes), every try from another chat is reported to the paired chat, wrong secrets are rate-limited (5 a chat,
20 from all other chats, an hour), and telegram.json is written in one step (a temp file, then os.replace).
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

from _legacy import pp, NEW                                         # noqa: E402  (pp: pinphone_legacy + NEW)
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


# ---- v-tg-pairlock (2026-11-07) ------------------------------------------------------------------------------------------
def _pctx(text, chat, cfg, path, now=T):
    return FakeCtx(text=text, now=now, active=("pin",), pp=pp, cfg=cfg, cfg_path=path, chat_id=chat)


def _said(c, chat=None):
    return [str(t) for cid, t in c.said if chat is None or cid == chat]


def test_first_pairing_is_unchanged():
    P.reset()
    path = os.path.join(TMP, "first.json")
    cfg = {"chat_id": None, "secret": "s3"}
    c = _pctx("/pair s3", 42, cfg, path)
    r = P.handle(c)
    assert isinstance(r, Html) and str(r).startswith("<b>Paired.</b>") and cfg["chat_id"] == 42 and c.said == []
    assert json.loads(_read(path))["chat_id"] == 42


def test_another_chat_with_the_right_secret_only_asks():
    P.reset()
    path = os.path.join(TMP, "take.json")
    cfg = {"chat_id": 1, "secret": "s3", "token": "keep"}
    P.save_cfg(cfg, path)
    c = _pctx("/pair s3", 9, cfg, path)
    r = P.handle(c)
    assert "already paired with another chat" in str(r) and "/pair allow</code> within 2 minutes" in str(r), r
    assert cfg["chat_id"] == 1 and json.loads(_read(path))["chat_id"] == 1, "nothing re-paired"
    told = _said(c, 1)
    assert len(told) == 1 and "chat (id 9) sent /pair with the RIGHT secret" in told[0], c.said
    assert "<code>/pair allow</code> within 2 minutes" in told[0] and "ET)" in told[0] and "do not allow it" in told[0]
    # the paired chat allows: control moves, the new chat is told it is paired
    a = _pctx("/pair allow", 1, cfg, path, now=T + 60)
    r = P.handle(a)
    assert "Control moved</b> to chat 9" in str(r) and cfg["chat_id"] == 9, r
    assert json.loads(_read(path)) == {"chat_id": 9, "secret": "s3", "token": "keep"}, "saved whole"
    assert any(str(t).startswith("<b>Paired.</b>") for cid, t in a.said if cid == 9), a.said
    # nothing waits any more
    r = P.handle(_pctx("/pair allow", 9, cfg, path, now=T + 61))
    assert "No other chat is waiting" in str(r)


def test_a_takeover_expires_and_can_be_denied():
    P.reset()
    path = os.path.join(TMP, "exp.json")
    cfg = {"chat_id": 1, "secret": "s3"}
    P.handle(_pctx("/pair s3", 9, cfg, path))
    r = P.handle(_pctx("/pair allow", 1, cfg, path, now=T + P.TAKEOVER_S + 1))
    assert "No other chat is waiting" in str(r) and cfg["chat_id"] == 1, r
    P.handle(_pctx("/pair s3", 9, cfg, path, now=T + 500))
    r = P.handle(_pctx("/pair deny", 1, cfg, path, now=T + 510))
    assert "Refused: chat 9 does not get control" in str(r) and cfg["chat_id"] == 1
    assert "No other chat is waiting" in str(P.handle(_pctx("/pair allow", 1, cfg, path, now=T + 511)))
    # the paired chat's own /pair <secret> still pairs it again and shows /help, as before
    r = P.handle(_pctx("/pair s3", 1, cfg, path, now=T + 512))
    assert str(r).startswith("<b>Paired.</b>") and cfg["chat_id"] == 1
    assert P.handle(_pctx("/pair nope", 1, cfg, path, now=T + 513)) is None, "the paired chat's wrong secret: nothing"


def test_wrong_secrets_are_reported_then_limited():
    P.reset()
    path = os.path.join(TMP, "wrong.json")
    cfg = {"chat_id": 1, "secret": "s3"}
    told = []
    for k in range(1, P.WRONG_MAX + 1):
        c = _pctx("/pair guess%d" % k, 9, cfg, path, now=T + k)
        assert P.handle(c) is None
        told += _said(c, 1)
    assert len(told) == P.WRONG_MAX, told
    assert "wrong secret" in told[0] and "1 of 5" in told[0] and "4 of 5" in told[3], told
    assert "sent 5 wrong /pair secrets in the last hour" in told[4] and "ignored until" in told[4], told[4]
    # past the limit: ignored -- even the RIGHT secret -- and no more reports
    for text in ("/pair guess6", "/pair s3"):
        c = _pctx(text, 9, cfg, path, now=T + 30)
        assert P.handle(c) is None and c.said == [] and cfg["chat_id"] == 1, (text, c.said)
    assert P.limited(9, T + 30) == "chat" and P.limited(10, T + 30) is None, "one chat's limit is its own"
    # an hour later it may try again
    c = _pctx("/pair s3", 9, cfg, path, now=T + 1 + P.WRONG_WINDOW_S)
    assert "already paired" in str(P.handle(c)), "after the hour the right secret asks again"


def test_every_other_chat_together_is_limited():
    P.reset()
    path = os.path.join(TMP, "flood.json")
    cfg = {"chat_id": 1, "secret": "s3"}
    told = []
    for k in range(P.WRONG_ALL_MAX):
        c = _pctx("/pair x", 100 + k, cfg, path, now=T + k)
        P.handle(c)
        told += _said(c, 1)
    assert len(told) == P.WRONG_ALL_MAX and "20 wrong /pair secrets from other chats" in told[-1], told[-1]
    c = _pctx("/pair s3", 500, cfg, path, now=T + 40)
    assert P.handle(c) is None and c.said == [] and P.limited(500, T + 40) == "all"
    P.reset()


def test_unpaired_wrong_secrets_are_limited_too():
    P.reset()
    path = os.path.join(TMP, "unp.json")
    cfg = {"chat_id": None, "secret": "s3"}
    for k in range(P.WRONG_MAX - 1):
        assert P.handle(_pctx("/pair no%d" % k, 9, cfg, path, now=T + k)) is None, "a wrong secret: no answer, as before"
    # FIRST SETUP: nobody is paired to be told, so the asking chat is -- the try that reaches the limit and every one
    # after (the operator, phone only, could not otherwise tell why the right secret now does nothing)
    r = P.handle(_pctx("/pair no4", 9, cfg, path, now=T + 4))
    assert "Too many wrong /pair secrets</b> (5 from this chat in the last hour)" in str(r), r
    import pindesk
    assert "until %s ET" % pindesk.et_str(T + P.WRONG_WINDOW_S) in str(r), "free an hour after the oldest try (T)"
    r = P.handle(_pctx("/pair s3", 9, cfg, path, now=T + 9))
    assert cfg["chat_id"] is None and "Too many wrong /pair secrets" in str(r) and "Nothing is paired yet" in str(r), r
    assert "s3" not in str(r).replace("secrets", ""), "the reply never repeats the secret"
    assert P.free_at("chat", 9, T + 9) == T + P.WRONG_WINDOW_S
    assert str(P.handle(_pctx("/pair s3", 8, cfg, path, now=T + 9))).startswith("<b>Paired.</b>"), "another chat may"
    # an hour after the OLDEST try (not after the latest) the chat may pair again
    cfg["chat_id"] = None
    assert P.limited(9, T + P.WRONG_WINDOW_S + 0.5) is None
    assert str(P.handle(_pctx("/pair s3", 9, cfg, path, now=T + P.WRONG_WINDOW_S + 0.5))).startswith("<b>Paired.</b>")
    P.reset()


def test_the_config_is_written_in_one_step():
    path = os.path.join(TMP, "atomic.json")
    P.save_cfg({"chat_id": 5, "secret": "a", "token": "t"}, path)
    assert json.loads(_read(path)) == {"chat_id": 5, "secret": "a", "token": "t"}
    assert not [f for f in os.listdir(TMP) if f.endswith(".tmp")], "no temp file is left behind"
    before = _read(path)
    try:
        P.save_cfg({"chat_id": 6, "bad": object()}, path)          # cannot be written as JSON
    except TypeError:
        pass
    assert _read(path) == before, "a write that fails leaves the old file whole (it used to leave half of one)"
    # ONE STEP, proven by behaviour (not by a word in the source): with the final swap refused, the old file is still
    # whole and no temp file is left -- an in-place rewrite (even one that builds the JSON first) changes the file
    from botdata import paths as _paths
    real_replace = os.replace

    def refuse(a, b):
        raise PermissionError(13, "planted: the swap is refused")
    for label, save in (("pair.save_cfg", lambda cfg: P.save_cfg(cfg, path)),
                        ("the fallback phone's save_cfg (pinphone_legacy)",
                         lambda cfg: pp.Phone.save_cfg(types.SimpleNamespace(cfg=cfg, cfg_path=path)))):
        swaps = []
        _paths.os.replace = lambda a, b: (swaps.append((a, b)), real_replace(a, b))
        try:
            save({"chat_id": 7, "secret": "a", "token": "t"})
        finally:
            _paths.os.replace = real_replace
        assert json.loads(_read(path))["chat_id"] == 7 and [b for _a, b in swaps] == [path], (label, swaps)
        before = _read(path)
        saved_sleep = _paths.time.sleep
        _paths.os.replace, _paths.time.sleep = refuse, (lambda s: None)
        try:
            save({"chat_id": 8, "secret": "a", "token": "t"})          # logged, never raised
        finally:
            _paths.os.replace, _paths.time.sleep = real_replace, saved_sleep
        assert _read(path) == before, "%s: a refused swap left the old file whole" % label
        assert not [f for f in os.listdir(TMP) if f.endswith(".tmp")], "%s: no temp file left" % label
    for mod in ("quiet_cmd", "alive_cmd"):
        with open(os.path.join(os.path.dirname(P.__file__), mod + ".py"), encoding="utf-8") as fh:
            s2 = fh.read()
        assert "save_cfg(" in s2 and 'open(' not in s2, "%s writes telegram.json only through pair.save_cfg" % mod


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
