"""test_stale.py -- v-tg-stale (2026-11-07, the phone audit): a CONTROL whose Telegram message is older than 5 minutes is
never run late, and the chat is told why.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_stale.py   (exit 0 = every test passed)
The phone polls with offset None after a restart, so whatever queued while it was down arrives first: before this a
'/stop yes' sent at 9 PM ran when the phone came back at 1 AM. Proves, through the real poll loop (phone.app.Phone with a
FakeTelegram whose messages carry a `date`):
  - an old '/stop yes', '/start', '/pause', '/mute', '/move yes 1234', '/approve ...' runs NOTHING and answers 'Not done';
  - the same message fresh (or with no date: every older self-test) runs as before;
  - a read-only page (/help, /today ...) is answered however old;
  - an old /pair: told when unpaired or from the paired chat; a stranger's gets no answer but the paired chat is told
    (a wrong secret counts toward the limit); the secret never echoed;
  - an old '/alive set <url>' changes nothing, and the URL (the operator's secret) is in neither the reply nor the log;
  - MORE THAN ONE BATCH QUEUED (the 2026-11-07 tests review's hole): Telegram hands over 100 messages a poll, so the
    101st comes on the next poll, armed at once -- an old '/stop yes' there is judged by its date too, never run;
  - the bars are pinned as numbers: 5 minutes (STALE_S), 60 s (PROMPT_GAP_S), 100 a poll (POLL_LIMIT);
  - a takeover through the real Phone: the paired chat is asked, '/pair allow' moves control, the old chat is ignored;
  - Command.is_control: every 'controls' command, /pair and /alive; no page.
NEVER the real controls: pindesk.do_start / do_pause / do_stop are recording stubs for the whole run. KALS_TESTING=1.
"""
import json
import os
import sys
import tempfile
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from _dlane import HEALTH, ORDERS, SETTLED, T, botstats, fake_ledger, patched, pindesk, quiet, run   # noqa: E402

CALLS = []
_REAL = {n: getattr(pindesk, n) for n in ("do_start", "do_pause", "do_stop")}
for _n in _REAL:
    setattr(pindesk, _n, (lambda name: (lambda *a, **k: CALLS.append(name)))(_n))
assert all(getattr(pindesk, n) is not _REAL[n] for n in _REAL), "the real pindesk controls are still in place"

from phone import app as A                                          # noqa: E402
from phone import command as CM                                     # noqa: E402
from phone import router as R                                       # noqa: E402
from phone import transport as TR                                   # noqa: E402
from phone.commands import controls as K                            # noqa: E402
from phone.commands import pair as PR                               # noqa: E402
from phone.log import log_path                                      # noqa: E402

K.time = types.SimpleNamespace(sleep=lambda s: None)                # the worker's 3 s pause
K.status_reply = lambda ctx: "STATUS"


TMP = tempfile.mkdtemp(prefix="test_stale_")


def _phone(chat=7):
    ph = A.Phone({"chat_id": chat, "secret": "open sesame", "token": "x"}, A.FakeTelegram(),
                 ledger=fake_ledger(settled=SETTLED, orders=ORDERS), now_fn=lambda: T,
                 health_fn=lambda: dict(HEALTH), procs_fn=lambda: [], cfg_path=os.path.join(TMP, "telegram.json"))
    return ph


def _log():
    with open(log_path(), encoding="utf-8") as fh:
        return fh.read()


def _push(ph, chat, text, date):
    ph.tg.n += 1
    m = {"chat": {"id": chat}, "text": text}
    if date is not None:
        m["date"] = int(date)
    ph.tg.incoming.append({"update_id": ph.tg.n, "message": m})


def _poll(ph, chat, text, date):
    """One message through the real poll loop; [(chat, words)] it sent. A dated message is delivered as by the first
    poll after a restart (judged by its date); a poll re-armed at once trusts its messages (test_app pins that)."""
    _push(ph, chat, text, date)
    if date is not None:
        ph._poll_end = None
    before = len(ph.tg.sent)
    ph.poll_once(timeout=0)
    t_end = time.monotonic() + 5
    while ph.busy and time.monotonic() < t_end:
        time.sleep(0.01)
    for t in list(threading.enumerate()):
        if t is not threading.current_thread() and t.daemon and t.name.startswith("Thread"):
            t.join(2)
    return [(c, str(m)) for c, m in ph.tg.sent[before:]]


def _world():
    return patched((botstats, "active_bots", lambda procs=None, now=None: ["pin"]))


def test_an_old_control_runs_nothing_and_says_why():
    with _world(), quiet():
        for text in ("/stop yes", "/start", "/pause", "/start yes", "/resume pin"):
            ph = _phone()
            del CALLS[:]
            sent = _poll(ph, 7, text, T - 3 * 3600 - 12 * 60)
            assert CALLS == [], (text, CALLS)
            assert len(sent) == 1 and sent[0][0] == 7, (text, sent)
            w = sent[0][1]
            assert "Not done now: %s</b> was sent 3 h 12 min ago" % text in w and "older than 5 minutes" in w, w
            assert "send it again if you still want it" in w and " ET)" in w, w
            assert "If you already got an answer to it then, it was done then" in w, "a resent message may have run"
            assert ph.offset == ph.tg.n + 1, "the old message is still confirmed (it never comes back)"
        ph = _phone()
        _poll(ph, 7, "/mute", T - 600)
        assert ph.muted is False, "an old /mute changes nothing"


def test_an_old_move_or_approve_runs_nothing():
    with _world(), quiet():
        for text in ("/move yes 1234", "/move 50 main jb", "/approve pinrestart yes 1234", "/approve pinrestart"):
            ph = _phone()
            sent = _poll(ph, 7, text, T - 900)
            assert len(sent) == 1 and "Not done now: %s</b> was sent 15 min ago" % text in sent[0][1], (text, sent)
            assert "No move is waiting" not in sent[0][1] and "No waiting change" not in sent[0][1], sent


def test_an_old_alive_set_changes_nothing_and_never_repeats_the_url():
    url = "https://hc-ping.com/0123abcd-4567-89ef-secret-part-c0ffee"
    with _world(), quiet():
        ph = _phone()
        sent = _poll(ph, 7, "/alive set " + url, T - 900)
        assert "alive_url" not in ph.cfg and not any(url in str(v) for v in ph.cfg.values()), ph.cfg
        assert not os.path.exists(os.path.join(TMP, "telegram.json")), "nothing saved"
        assert len(sent) == 1 and "Not done now: /alive set hc-ping.com/…c0ffee</b>" in sent[0][1], sent
        log = _log()
        assert "ignored /alive set hc-ping.com/…c0ffee: sent 900 s ago" in log, log[-2000:]
        for secret in (url, "0123abcd-4567-89ef-secret-part"):
            assert secret not in sent[0][1] and secret not in log, "the ping URL is the operator's secret: %s" % secret
        sent = _poll(ph, 7, "/alive off", T - 900)
        assert "Not done now: /alive off</b>" in sent[0][1], sent
    for text, want in (("/alive set " + url, "/alive set hc-ping.com/…c0ffee"), ("/alive " + url, "/alive"),
                       ("/alive@bot SET " + url + " x", "/alive set hc-ping.com/…c0ffee"), ("/alive", "/alive")):
        assert CM.by_name("/alive").echo_of(text) == want, (text, CM.by_name("/alive").echo_of(text))
    assert CM.by_name("/pair").echo_of("/pair open sesame") == "/pair"
    assert CM.by_name("/stop").echo_of("/stop yes") == "/stop yes", "a command with no secret is repeated as typed"
    bad = CM.Command(names=("/zzecho",), section=None, handle=lambda c: 1, echo=lambda t: 1 / 0)
    assert bad.echo_of("/zzecho the secret") == "/zzecho", "a failing echo repeats only the name"


def test_more_than_one_batch_queued_after_a_restart():
    """101 messages queued while the phone was down, the last an old '/stop yes': the first poll hands over 100, the
    second (armed at once) the 101st -- judged by its date too, so it never runs (it RAN before this fix)."""
    assert TR.POLL_LIMIT == 100
    with _world(), quiet():
        ph = _phone()
        del CALLS[:]
        for k in range(TR.POLL_LIMIT):
            _push(ph, 7, "/mute", T - 3 * 3600 + k)
        _push(ph, 7, "/stop yes", T - 3 * 3600)
        ph.poll_once(timeout=0)
        assert ph.offset == TR.POLL_LIMIT + 1 and ph._backlog is True, (ph.offset, ph._backlog)
        assert len(ph.tg.sent) == TR.POLL_LIMIT and ph.muted is False, len(ph.tg.sent)
        ph.poll_once(timeout=0)                     # armed at once, but after a FULL batch: judged by the date
        time.sleep(0.05)
        assert CALLS == [], "the 101st message, an old /stop yes, was RUN: %s" % CALLS
        assert "Not done now: /stop yes</b>" in str(ph.tg.sent[-1][1]) and ph._backlog is False, ph.tg.sent[-1]
        # a short batch clears it: the next prompt poll trusts its messages again (a fast server clock never locks out
        # /stop yes -- test_app pins that side)
        _push(ph, 7, "/stop yes", None)
        ph.poll_once(timeout=0)
        t_end = time.monotonic() + 5
        while ph.busy and time.monotonic() < t_end:
            time.sleep(0.01)
        assert CALLS == ["do_stop"], CALLS


def test_the_bars_are_pinned():
    assert R.STALE_S == 300, "a control older than 5 minutes is not run"
    assert A.PROMPT_GAP_S == 60, "a poll armed within 60 s of the last answered one delivers fresh messages"
    assert TR.POLL_LIMIT == 100, "Telegram's batch"


def test_a_takeover_through_the_real_phone():
    PR.reset()
    with _world(), quiet():
        ph = _phone(chat=7)
        sent = _poll(ph, 99, "/pair open sesame", None)
        to99 = [w for c, w in sent if c == 99]
        to7 = [w for c, w in sent if c == 7]
        assert len(to99) == 1 and "already paired with another chat" in to99[0], sent
        assert len(to7) == 1 and "chat (id 99) sent /pair with the RIGHT secret" in to7[0], sent
        assert ph.chat_id == 7, "nothing re-paired yet"
        sent = _poll(ph, 7, "/pair allow", None)
        assert ph.chat_id == 99, ph.cfg
        assert any(c == 7 and "Control moved</b> to chat 99" in w for c, w in sent), sent
        assert any(c == 99 and w.startswith("<b>Paired.</b>") for c, w in sent), sent
        with open(os.path.join(TMP, "telegram.json"), encoding="utf-8") as fh:
            assert json.load(fh)["chat_id"] == 99, "saved"
        assert _poll(ph, 7, "/status", None) == [], "the old chat is not answered any more"
    PR.reset()


def test_a_fresh_or_undated_control_runs_as_before():
    with _world(), quiet():
        for date in (T - 30, T - 299, None):
            ph = _phone()
            del CALLS[:]
            sent = _poll(ph, 7, "/stop yes", date)
            assert CALLS == ["do_stop"] and any("Stopping now" in w for _c, w in sent), (date, CALLS, sent)
            assert not any("Not done" in w for _c, w in sent), sent
        ph = _phone()
        _poll(ph, 7, "/mute", T - 60)
        assert ph.muted is True


def test_an_old_page_is_answered():
    with _world(), quiet():
        ph = _phone()
        sent = _poll(ph, 7, "/help", T - 86400)
        assert sent and "Commands" in sent[0][1] and "Not done" not in sent[0][1], sent
        assert R.message_age(ph.ctx("/help"), T - 86400) == 86400 and R.message_age(ph.ctx("/x"), None) is None
        assert R.message_age(ph.ctx("/x"), "junk") is None and R.message_age(ph.ctx("/x"), T - 300) is None


def test_an_old_pair():
    PR.reset()
    with _world(), quiet():
        ph = _phone(chat=None)                       # unpaired: the chat that pairs is told, nothing pairs
        sent = _poll(ph, 42, "/pair open sesame", T - 900)
        assert ph.chat_id is None and len(sent) == 1 and "Not done now: /pair</b>" in sent[0][1], sent
        assert "open sesame" not in sent[0][1], "the stale answer never echoes the secret"
        assert "open sesame" not in _log(), "nor its log line"
        sent = _poll(ph, 42, "/pair open sesame", T - 10)
        assert ph.chat_id == 42 and "Paired." in sent[0][1], "the same message fresh pairs as before"
        # paired: a stranger's old /pair gets no answer, but the paired chat is told (every try from another chat is)
        ph = _phone(chat=7)
        sent = _poll(ph, 99, "/pair open sesame", T - 900)
        assert ph.chat_id == 7 and [c for c, _w in sent] == [7], sent
        assert "chat (id 99) sent /pair with the RIGHT secret 15 min ago" in sent[0][1], sent
        assert "not acted on" in sent[0][1] and "someone knows the secret" in sent[0][1], sent
        assert "No other chat is waiting" in _poll(ph, 7, "/pair allow", None)[0][1], "nothing waits for /pair allow"
        # an old WRONG secret is reported too, and counts toward the limit
        for k in range(PR.WRONG_MAX):
            sent = _poll(ph, 98, "/pair guess%d" % k, T - 900)
            assert [c for c, _w in sent] == [7], sent
        assert "wrong secret 15 min ago (it reached the phone only now)" in str(ph.tg.sent[-PR.WRONG_MAX][1])
        assert "sent 5 wrong /pair secrets in the last hour" in sent[0][1] and PR.limited(98, T) == "chat", sent
        assert _poll(ph, 98, "/pair open sesame", T - 900) == [], "past the limit: ignored, nobody told again"
    PR.reset()


def test_is_control_marks_every_control_and_no_page():
    R.discover()
    ctl = sorted(n for c in R.commands() if c.is_control for n in c.names)
    for n in ("/pause", "/start", "/stop", "/resume", "/play", "/mute", "/unmute", "/quiet", "/update", "/approve",
              "/move", "/pair", "/alive", "/watch"):
        assert n in ctl, (n, ctl)
    for c in R.commands():
        if c.section == "controls":
            assert c.is_control, c.name
    for n in ("/today", "/status", "/bots", "/pin", "/help", "/funds", "/server", "/losses"):
        assert not CM.by_name(n).is_control, n
    assert CM.Command(names=("/zzx",), section="now", handle=lambda c: 1, control=True).is_control
    assert not CM.Command(names=("/zzy",), section="controls", handle=lambda c: 1, control=False).is_control


def test_every_command_that_writes_through_actions_is_a_control():
    """THE CLASS RULE (11-08 merge review: /watch writes the Kalshi watch's stop file through phone.actions but was not
    a control, so an old '/watch off yes' queued while the phone was down still ran late). phone/actions is the ONLY way
    the phone changes the outside world (test_actions_safety), so every command whose module imports it changes
    something and must be a control -- a command added later is covered without touching this list."""
    import re
    R.discover()
    rx = re.compile(r"^\s*(from\s+phone\.actions\b|from\s+phone\s+import\s+actions\b|import\s+phone\.actions\b)", re.M)
    writers, bad = set(), []
    for c in R.commands():
        mod = sys.modules.get(c.module)
        path = getattr(mod, "__file__", None)
        assert path, (c.name, c.module)
        with open(path, encoding="utf-8") as fh:
            if not rx.search(fh.read()):
                continue
        writers.add(c.module)
        if not c.is_control:
            bad.append("%s (%s)" % (c.name, c.module))
    assert not bad, "commands that write through phone.actions but are not controls: %s" % bad
    assert {"phone.commands.approve", "phone.commands.botctl", "phone.commands.move",
            "phone.commands.watch_cmd"} <= writers, ("the scan finds the known writers", sorted(writers))


def main():
    try:
        return run(globals(), "test_stale")
    finally:
        for n, f in _REAL.items():
            setattr(pindesk, n, f)


if __name__ == "__main__":
    sys.exit(main())
