"""test_alive.py -- the outside 'is it alive' check (v-tg-rebuild step 12, lane Q): phone/alive.py's pinger (a GET every
5 min while no bot is DOWN, off without a URL, failures counted, never raising, on its own thread) and /alive (its state,
/alive set <url>, /alive off; saved in the phone's config file). No real URL is ever called: the GET is planted.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_alive.py   (exit 0 = every test passed)
A fake clock and a temp config file. KALS_TESTING=1; no network.
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

from botdata import paths                                            # noqa: E402
from phone import alive as AL                                        # noqa: E402
from phone import log as plog                                        # noqa: E402
from phone import monitor as M                                       # noqa: E402
from phone.commands import alive_cmd as AC                           # noqa: E402
from phone.context import FakeCtx                                    # noqa: E402

TMP = tempfile.mkdtemp(prefix="test_alive_")
paths.set_results(TMP)
plog.set_path(lambda: os.path.join(TMP, "pinphone.log"), replace=True)
T0 = 1793370120.0               # 2026-10-30 14:22Z = 10:22 AM ET
URL = "https://hc-ping.example.invalid/0123456789abcdef"
CALLS = []


def fake_get(answers):
    it = iter(answers)

    def get(url, timeout=10):
        CALLS.append((url, timeout))
        a = next(it)
        if isinstance(a, Exception):
            raise a
        return a
    return get


def setup(answers, url=URL):
    AL.RUN_IN_THREAD = False
    AL.GET = fake_get(answers)
    del CALLS[:]
    m = M.MonitorState()
    ctx = FakeCtx(now=T0, cfg={"alive_url": url} if url is not None else {})
    return m, ctx


def test_url_rules():
    assert AL.valid(URL) and AL.valid("http://a.b/c") and not AL.valid("hc-ping.com/x") and not AL.valid("https://x")
    assert not AL.valid("") and not AL.valid(None)
    assert AL.masked(URL) == "hc-ping.example.invalid/…abcdef" and AL.masked("https://a.io/") == "a.io"
    assert AL.url_of({"alive_url": "  "}) is None and AL.url_of({}) is None and AL.url_of({"alive_url": URL}) == URL


def test_every_five_minutes_while_healthy():
    m, ctx = setup([200, 200, 503, OSError("no route"), 200])
    for dt in (0, 60, 299):
        AL.check(ctx, m, None, T0 + dt)
    assert CALLS == [(URL, AL.TIMEOUT_S)] and m.alive.ok == 1 and m.alive.last_ok_t == T0
    AL.check(ctx, m, None, T0 + 300)
    AL.check(ctx, m, None, T0 + 600)                # HTTP 503: counted as failed, logged, no raise
    AL.check(ctx, m, None, T0 + 900)                # a network error: the same
    assert len(CALLS) == 4 and m.alive.ok == 2 and m.alive.failed == 2 and m.alive.last_status.startswith("OSError")
    m.down["jumpband"] = {"since": T0, "checks": 5, "sent": True}
    AL.check(ctx, m, None, T0 + 1200)               # a bot DOWN: no ping (the outside service sees the silence)
    assert len(CALLS) == 4 and m.alive.skipped_why == "Jump band is down"
    m.down["ladder"] = {"since": T0, "checks": 1, "sent": False}      # still inside its debounce: not counted
    del m.down["jumpband"]
    AL.check(ctx, m, None, T0 + 1260)
    assert len(CALLS) == 5 and m.alive.skipped_why is None and m.alive.ok == 3


def test_off_and_bad_urls_never_call():
    for url in (None, "", "not a url"):
        m, ctx = setup([200], url=url)
        AL.check(ctx, m, None, T0)
        assert CALLS == [], url


def test_on_its_own_thread():
    m, ctx = setup([200])
    AL.RUN_IN_THREAD = True
    try:
        AL.check(ctx, m, None, T0)
        AL.check(ctx, m, None, T0 + 1)              # in flight or done: never a second GET inside 5 min
        for _ in range(200):
            if not m.alive.busy:
                break
            time.sleep(0.01)
    finally:
        AL.RUN_IN_THREAD = False
    assert CALLS == [(URL, AL.TIMEOUT_S)] and m.alive.ok == 1 and not m.alive.busy


def test_through_the_monitor_tick():
    m, ctx = setup([200, 200])
    st = types.SimpleNamespace(monitor=m)
    ctx.bs_procs = lambda: None                     # the table unreadable: nothing DOWN
    ctx.bs_getter = lambda path, params: (599, "tests: no Kalshi")
    M.tick(ctx, st, lambda msg, urgent=False: None, T0)
    assert len(CALLS) == 1


def test_the_alive_command():
    cfgp = os.path.join(TMP, "telegram.json")
    cfg = {"chat_id": 7, "secret": "s"}

    def run(text, mon=None, on=True):
        ctx = FakeCtx(text=text, now=T0 + 400, cfg=cfg, cfg_path=cfgp)
        ctx.state = types.SimpleNamespace(muted=False, monitor_on=on, monitor=mon)
        return str(AC.COMMAND.run(ctx))
    r = run("/alive")
    assert r.startswith("🛰 <b>Outside check: OFF -- no URL set</b>\nThe phone pings nothing now") and "healthchecks.io" in r
    assert run("/alive set nonsense").startswith("🛰 I did not change it: send the whole ping URL")
    assert not os.path.exists(cfgp)
    r = run("/alive set " + URL)
    assert r.startswith("🛰 <b>Outside check: ON</b>\nPinging <code>hc-ping.example.invalid/…abcdef</code> every 5 "
                        "minutes while the phone runs and no bot is DOWN.\nNo ping yet (the first goes within 5 "
                        "minutes)."), r
    with open(cfgp, encoding="utf-8") as fh:
        assert json.load(fh)["alive_url"] == URL
    m, _ctx = setup([200], url=URL)
    AL.check(_ctx, m, None, T0)
    r = run("/alive", mon=m)
    assert "Last ping 10:22 AM ET: answered 200 · 1 answered, 0 failed since the phone started." in r, r
    assert "The watch is off in this phone" in run("/alive", mon=m, on=False)
    assert run("/alive off").startswith("🛰 <b>Outside check: OFF</b>")
    with open(cfgp, encoding="utf-8") as fh:
        assert json.load(fh)["alive_url"] == ""
    assert AC.COMMAND.section == "server" and not AC.COMMAND.needs_ledger and AC.COMMAND.kind_of("/alive") is None


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
    print("test_alive: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
