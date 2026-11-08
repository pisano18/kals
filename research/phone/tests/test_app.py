"""test_app.py -- research/phone/app.py, the runtime (v-tg-rebuild step 11): start, one loop pass, the thread rules.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_app.py   (exit 0 = every test passed)
  - start(): the command modules discovered, the process-table refresher started (botdata.procs), the hello said once;
  - loop_once(): heartbeat, one poll (a message answered, its words sent), then the update flag, the alerts and the
    resend queue -- a tick that raises is logged and the loop goes on; polled_ok is set by the first answered poll;
  - THE ALERTS NEVER READ THE PROCESS TABLE (a slow WMI read can never hold them): alerts_tick with every process
    reader planted to fail;
  - a command's process read goes to botdata.procs' cached table (no synchronous read while the refresher keeps it
    fresh);
  - Phone.pp is phone.shared (what every Ctx reads as ctx.pp).
  - v-tg-hung (2026-11-07): the heartbeat is written in one step (os.replace) with the time (UTC) and the pid, before
    the poll and before every tick; a swap Windows refuses is written in place (the beat always lands); never the live
    file under KALS_TESTING=1. boot_all.ps1's side is run by test_boot_phone.py.
  - v-tg-stale: poll_once hands each message's Telegram date to the router.
KALS_TESTING=1; no network, no real Telegram, nothing under results\\ written.
"""
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from _dlane import HEALTH, ORDERS, SETTLED, T, botstats, fake_ledger, patched, quiet   # noqa: E402
import phone.shared as S                                             # noqa: E402
from phone import app as A                                          # noqa: E402
from botdata import procs as P                                      # noqa: E402

from phone.log import log_path                                       # noqa: E402  (_dlane points the log at a temp file)


def _phone(chat=7):
    return A.Phone({"chat_id": chat, "secret": "s"}, A.FakeTelegram(), ledger=fake_ledger(settled=SETTLED, orders=ORDERS),
                   now_fn=lambda: T, health_fn=lambda: dict(HEALTH), procs_fn=lambda: [])


def _boom(*a, **k):
    raise AssertionError("planted: must not be called")


def test_pp_is_shared():
    assert A.Phone.pp is S and _phone().ctx("/status").pp is S


def test_start_discovers_starts_the_refresher_and_says_hello():
    started = []
    with patched((P, "start_refresher", lambda period=None: started.append(1))), quiet():
        ph = _phone()
        ph.start()
    assert started == [1]
    assert [str(m) for _c, m in ph.tg.sent] == [str(S.UP_TEXT)]
    with patched((P, "start_refresher", lambda period=None: started.append(1))), quiet():
        unpaired = _phone(chat=None)
        unpaired.start()
    assert unpaired.tg.sent == [], "no paired chat: no hello"


def test_loop_once_answers_and_survives_a_failing_tick():
    with patched((botstats, "active_bots", lambda procs=None, now=None: ["pin"])), quiet():
        ph = _phone()
        ph.alerts_tick = _boom                                  # a tick that raises: logged, the loop goes on
        ticks = []
        ph.resend_tick = lambda: ticks.append("resend")
        ph.tg.push(7, "/mute")
        assert not ph.polled_ok
        ph.poll_once = (lambda f: (lambda timeout=25: f(timeout=0)))(ph.poll_once)
        ph.loop_once()
    assert ph.polled_ok and ph.muted and ticks == ["resend"]
    assert [str(m) for _c, m in ph.tg.sent] == ["🔕 Alerts off. /unmute to turn them back on."]
    with open(log_path(), encoding="utf-8") as fh:
        assert "planted: must not be called" in fh.read(), "the failing tick was logged"


def test_heartbeat_is_one_step_with_the_pid():
    import re
    import tempfile
    td = tempfile.mkdtemp(prefix="test_app_hb_")
    hb = os.path.join(td, "pinphone.heartbeat")
    with patched((S, "HEARTBEAT", hb)), quiet():
        _phone().heartbeat()
        with open(hb, encoding="utf-8") as fh:
            txt = fh.read()
        m = re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ pid (\d+)\n$", txt)
        assert m and int(m.group(1)) == os.getpid(), txt
        assert os.listdir(td) == ["pinphone.heartbeat"], "no temp file is left behind"
        _phone().heartbeat()                                     # the second write replaces the first
        assert os.listdir(td) == ["pinphone.heartbeat"]
    with patched((S, "HEARTBEAT", os.path.join(td, "no-such-dir", "hb"))), quiet():
        _phone().heartbeat()                                     # a failed write never raises
    # ONE STEP: the beat is a temp file swapped in by os.replace (a reader never sees half of one) ...
    from botdata import paths as _paths
    swaps = []
    real_replace = os.replace
    with patched((S, "HEARTBEAT", hb), (_paths.os, "replace", lambda a, b: (swaps.append((a, b)), real_replace(a, b)))):
        _phone().heartbeat()
    assert len(swaps) == 1 and swaps[0][1] == hb and swaps[0][0] != hb and swaps[0][0].endswith(".tmp"), swaps
    # ... and a swap Windows refuses (a reader holds the file open) is written in place instead: a beat that did not
    # land would get a working phone killed by boot_all (the 2026-11-07 safety review)
    with open(hb, "w", encoding="utf-8") as fh:
        fh.write("2026-01-01T00:00:00Z pid 1\n")
    with patched((S, "HEARTBEAT", hb), (_paths.os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError(13, "held"))),
                 (_paths.time, "sleep", lambda s: None)), quiet():
        _phone().heartbeat()
    with open(hb, encoding="utf-8") as fh:
        assert fh.read().endswith(" pid %d\n" % os.getpid()), "the refused swap still lands the beat"
    assert os.listdir(td) == ["pinphone.heartbeat"], "and leaves no temp file"
    # the test fence still holds, fallback or not: never the live heartbeat under KALS_TESTING=1
    live = os.path.join(_paths.DEFAULT_RESULTS, "pinphone.heartbeat")
    before = os.stat(live).st_mtime_ns if os.path.exists(live) else None
    with patched((S, "HEARTBEAT", live)):
        _phone().heartbeat()
    assert (os.stat(live).st_mtime_ns if os.path.exists(live) else None) == before, "the live heartbeat was written"
    # boot_all's side is RUN (lifted out of the parsed file) by test_boot_phone.py
    assert os.path.exists(os.path.join(HERE, "test_boot_phone.py"))


def test_loop_beats_before_the_poll_and_every_tick():
    ph = _phone()
    order = []
    ph.heartbeat = lambda: order.append("beat")
    ph.poll_once = lambda timeout=25: order.append("poll")
    ph.update_flag_tick = lambda: order.append("update")
    ph.alerts_tick = lambda: order.append("alerts")
    ph.resend_tick = lambda: order.append("resend")
    ph.loop_once()
    assert order == ["beat", "poll", "beat", "update", "beat", "alerts", "beat", "resend"], order


def test_poll_hands_the_message_date_to_the_router():
    ph = _phone()
    got = []
    ph.handle = lambda chat, text, sent_at=None, about=None: got.append((chat, text, sent_at))
    ph.tg.incoming.append({"update_id": 1, "message": {"chat": {"id": 7}, "text": "/help", "date": 1793447000}})
    ph.tg.incoming.append({"update_id": 2, "message": {"chat": {"id": 7}, "text": "/help"}})
    ph.poll_once(timeout=0)
    assert got == [(7, "/help", 1793447000), (7, "/help", None)], got
    # the next poll is armed at once: what it delivers is fresh by construction, whatever its date says (a server clock
    # running fast can never lock every control out); a prompt message dated over 5 minutes old is a clock warning
    del got[:]
    ph.tg.incoming[:] = [{"update_id": 3, "message": {"chat": {"id": 7}, "text": "/stop yes", "date": T - 3600}}]
    with quiet():
        ph.poll_once(timeout=0)
    assert got == [(7, "/stop yes", None)], got
    with open(log_path(), encoding="utf-8") as fh:
        assert "clock warning: a message delivered at once is dated 3600 s ago" in fh.read()
    # a failed poll is a gap: the next one is judged by the date again
    ph.tg.get_updates = lambda offset, timeout=25: (_ for _ in ()).throw(OSError("planted"))
    saved = A.time.sleep
    A.time.sleep = lambda s: None
    try:
        with quiet():
            ph.poll_once(timeout=0)
    finally:
        A.time.sleep = saved
    ph.tg.get_updates = lambda offset, timeout=25: [{"update_id": 4, "message": {"chat": {"id": 7}, "text": "/stop yes",
                                                                                 "date": T - 3600}}]
    del got[:]
    ph.poll_once(timeout=0)
    assert got == [(7, "/stop yes", T - 3600)], got
    # and a poll armed more than PROMPT_GAP_S after the last answered one is judged by the date too
    ph._poll_end -= A.PROMPT_GAP_S + 1
    del got[:]
    ph.poll_once(timeout=0)
    assert got == [(7, "/stop yes", T - 3600)], got


def test_poll_describes_every_update_for_the_router():
    """v-tg-unknown: the router gets each update described (phone/incoming.Incoming) with its text -- a caption counts
    as the text, a sticker has none, an edited message is its own kind -- and the words sent are the router's."""
    from phone import incoming as I
    ph = _phone()
    got = []
    ph.handle = lambda chat, text, sent_at=None, about=None: got.append((chat, text, sent_at, about.kind, about.reply))
    ph.tg.incoming += [
        {"update_id": 1, "message": {"chat": {"id": 7}, "text": "/help", "date": 1793447000}},
        {"update_id": 2, "message": {"chat": {"id": 7}, "photo": [{"file_id": "p"}], "caption": "/today",
                                     "date": 1793447001}},
        {"update_id": 3, "message": {"chat": {"id": 7}, "sticker": {"file_id": "s"}, "date": 1793447002,
                                     "reply_to_message": {"from": {"is_bot": True}, "text": "x"}}},
        {"update_id": 4, "edited_message": {"chat": {"id": 7}, "text": "/stop yes", "date": 1793447003}},
        {"update_id": 5, "message": {"chat": {"id": 7}, "pinned_message": {"text": "x"}, "date": 1793447004}}]
    ph.poll_once(timeout=0)
    assert got == [(7, "/help", 1793447000, "text", False), (7, "/today", 1793447001, "caption", False),
                   (7, "", 1793447002, "sticker", True), (7, "/stop yes", 1793447003, "edited", False),
                   (7, "", 1793447004, "service", False)], got
    assert ph.offset == 6
    # the real router behind it: the sticker gets one line and the service message nothing, each logged
    ph = _phone()
    ph.tg.incoming += [{"update_id": 1, "message": {"chat": {"id": 7}, "sticker": {"file_id": "s"}}},
                       {"update_id": 2, "message": {"chat": {"id": 7}, "pinned_message": {"text": "x"}}},
                       {"update_id": 3, "message": {"chat": {"id": 7}, "text": "thanks"}}]
    with quiet():
        ph.poll_once(timeout=0)
    sent = [str(m) for _c, m in ph.tg.sent]
    assert sent[0] == "I got a sticker. I only read typed commands: /help lists them." and len(sent) == 2, sent
    assert sent[1].startswith('I did not understand that. You sent "thanks".\n\n📱 <b>Commands</b>'), sent[1][:100]
    with open(log_path(), encoding="utf-8") as fh:
        text = fh.read()
    for line in ("not understood from chat 7: sticker", "ignored from chat 7: service message (pinned_message) (no reply)",
                 'not understood from chat 7: text "thanks"'):
        assert line in text, line
    assert I.describe(ph.tg.incoming[1]).silent


def test_alerts_never_read_the_process_table():
    with patched((P, "read_all", _boom), (P, "native_rows", _boom), (P, "wmi_rows", _boom), (P, "table", _boom),
                 (S, "python_procs", _boom), (S, "list_python_procs", _boom)), quiet():
        ph = _phone()
        ph.procs_fn = _boom
        t0 = time.monotonic()
        assert ph.alerts_tick() == [] and ph.last_state is not None    # the first tick learns, sends nothing
        h2 = dict(HEALTH, disk_gb=5.5)
        ph.health_fn = lambda: dict(h2)
        sent = ph.alerts_tick()
        assert len(sent) == 1 and "DISK" in str(sent[0]) and time.monotonic() - t0 < 5


def test_a_command_reads_the_cached_table():
    saved = dict(P._TABLE)
    try:
        P._store([[11, "", "C:\\Python314\\python.exe -u research\\pinrun.py --live"]])
        with patched((P, "read_all", _boom)):
            assert S.python_procs() == [(11, "C:\\Python314\\python.exe -u research\\pinrun.py --live")]
            assert S.cached_python_procs() == S.python_procs()
    finally:
        P._TABLE.clear()
        P._TABLE.update(saved)


def main():
    tests = [(k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = []
    for k, fn in tests:
        try:
            fn()
            print("  ok   %s" % k, flush=True)
        except Exception:                                       # noqa: BLE001
            failed.append(k)
            print("  FAIL %s\n%s" % (k, traceback.format_exc()), flush=True)
    print("test_app: %d passed, %d failed" % (len(tests) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
