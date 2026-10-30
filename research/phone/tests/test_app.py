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
