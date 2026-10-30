"""test_launcher.py -- research/pinphone.py, the launcher (v-tg-rebuild step 11): the legacy fallback, the re-exports.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_launcher.py   (exit 0 = every test passed)
  - phone.app failing to IMPORT, or failing to START (before its first answered poll), runs pinphone_legacy.main()
    and sends nothing; a failure AFTER the first poll is not a start failure (it propagates); Ctrl-C propagates;
  - end to end in a fresh process: `pinphone.py` with phone.app made unimportable falls back to the legacy phone;
  - the fallback really starts the legacy Phone on the config (its run loop planted to return at once);
  - the old names other files import (bars.py, phone_alert.py, the golden harness) still come from pinphone.
KALS_TESTING=1; no network, no real Telegram, nothing under results\\ written.
"""
import os
import subprocess
import sys
import tempfile
import traceback

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

import pinphone as L                                                 # noqa: E402  (the launcher)
import pinphone_legacy                                               # noqa: E402
import phone.shared as S                                             # noqa: E402

TMP = tempfile.mkdtemp(prefix="test_launcher_")
S.LOG = pinphone_legacy.LOG = os.path.join(TMP, "pinphone.log")   # phone.log follows whichever module claimed it first


class _Swap:
    """Set attributes for a with-block, put back after."""

    def __init__(self, *triples):
        self.triples = triples
        self.saved = []

    def __enter__(self):
        for obj, name, v in self.triples:
            self.saved.append((obj, name, getattr(obj, name, None), hasattr(obj, name)))
            setattr(obj, name, v)
        return self

    def __exit__(self, *exc):
        for obj, name, v, had in reversed(self.saved):
            if had:
                setattr(obj, name, v)
            else:
                delattr(obj, name)


def _legacy_recorder(calls):
    def main():
        calls.append("legacy")
        return 7
    return main


def _log():
    try:
        with open(S.LOG, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def test_start_failure_before_the_first_poll_runs_legacy():
    from phone import app
    calls, sent = [], []

    class Ph:
        polled_ok = False

    def boom(argv=(), state=None):
        state["phone"] = Ph()
        raise RuntimeError("planted: the new phone failed at start")
    with _Swap((app, "main", boom), (pinphone_legacy, "main", _legacy_recorder(calls))):
        rc = L.run(())
    assert rc == 7 and calls == ["legacy"], (rc, calls)
    assert "running pinphone_legacy.py instead; nothing was sent" in _log() and "planted: the new phone" in _log()
    assert not sent


def test_failure_before_the_phone_exists_runs_legacy():
    from phone import app
    calls = []

    def boom(argv=(), state=None):
        raise ValueError("planted: no Phone yet")
    with _Swap((app, "main", boom), (pinphone_legacy, "main", _legacy_recorder(calls))):
        assert L.run(()) == 7 and calls == ["legacy"]


def test_failure_after_the_first_poll_propagates():
    from phone import app
    calls = []

    class Ph:
        polled_ok = True

    def boom(argv=(), state=None):
        state["phone"] = Ph()
        raise RuntimeError("planted: after the first poll")
    with _Swap((app, "main", boom), (pinphone_legacy, "main", _legacy_recorder(calls))):
        try:
            L.run(())
            raised = None
        except RuntimeError as e:
            raised = e
    assert raised is not None and calls == [], "a running phone's failure is not a start failure"


def test_ctrl_c_propagates():
    from phone import app
    calls = []

    def stop(argv=(), state=None):
        raise KeyboardInterrupt
    with _Swap((app, "main", stop), (pinphone_legacy, "main", _legacy_recorder(calls))):
        try:
            L.run(())
            ok = False
        except KeyboardInterrupt:
            ok = True
    assert ok and calls == []


def test_import_failure_runs_legacy():
    import phone
    calls = []
    saved_mod = sys.modules.get("phone.app")
    saved_attr = getattr(phone, "app", None)
    try:
        sys.modules["phone.app"] = None                      # `from phone import app` -> ImportError
        if hasattr(phone, "app"):
            delattr(phone, "app")
        with _Swap((pinphone_legacy, "main", _legacy_recorder(calls))):
            assert L.run(()) == 7 and calls == ["legacy"]
        assert "phone.app could not be imported" in _log()
    finally:
        if saved_mod is not None:
            sys.modules["phone.app"] = saved_mod
        else:
            sys.modules.pop("phone.app", None)
        if saved_attr is not None:
            phone.app = saved_attr


def test_the_fallback_starts_the_legacy_phone():
    """pinphone_legacy.main() for real, on a planted config, with its Telegram planted and its run loop planted to return:
    the legacy Phone is built on the config and started."""
    cfg = os.path.join(TMP, "telegram.json")
    with open(cfg, "w", encoding="utf-8") as fh:
        fh.write('{"token": "123:planted", "chat_id": 5, "secret": "s", "charts": false}')
    ran = []
    from phone import app

    def boom(argv=(), state=None):
        raise RuntimeError("planted")
    with _Swap((app, "main", boom), (pinphone_legacy, "CONFIG", cfg),
               (pinphone_legacy, "Telegram", lambda token: pinphone_legacy.FakeTelegram()),
               (pinphone_legacy.Phone, "run", lambda self: ran.append((self.chat_id, self.charts_on)))):
        saved_argv = sys.argv
        sys.argv = [os.path.join(RESEARCH, "pinphone.py")]
        try:
            rc = L.run(())
        finally:
            sys.argv = saved_argv
    assert rc == 0 and ran == [(5, False)], (rc, ran)


SITE = '''
import sys, types, importlib.abc
class _NoApp(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == "phone.app":
            raise ImportError("planted: phone.app is broken")
        return None
sys.meta_path.insert(0, _NoApp())
leg = types.ModuleType("pinphone_legacy")
def main():
    print("LEGACY PHONE RUNNING", flush=True)
    return 0
leg.main = main
sys.modules["pinphone_legacy"] = leg
'''


def test_end_to_end_unimportable_app_falls_back():
    """A fresh `python pinphone.py` (no arguments: the live run) whose phone.app cannot be imported: it logs why, sends
    nothing, and runs the legacy phone (planted by sitecustomize to print and exit 0)."""
    d = tempfile.mkdtemp(prefix="test_launcher_site_")
    with open(os.path.join(d, "sitecustomize.py"), "w", encoding="utf-8") as fh:
        fh.write(SITE)
    env = dict(os.environ, PYTHONPATH=d, KALS_TESTING="1", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-u", os.path.join(RESEARCH, "pinphone.py")], cwd=os.path.dirname(RESEARCH),
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "phone.app could not be imported" in out and "running pinphone_legacy.py instead" in out, out
    assert out.strip().splitlines()[-1] == "LEGACY PHONE RUNNING", out


def test_old_names_still_come_from_pinphone():
    from phone import app
    for n in ("CONFIG", "Telegram", "MAX_LEN", "RACE", "RESULTS", "_leg_name", "arm_results", "et_str", "log_records",
              "log_span", "markets_from", "pinday", "race_tally", "race_tally_line", "races_from", "raw_ledger",
              "split_text", "RACE30_UTC", "z3_progress", "money", "UPDATE_FLAG", "help_text", "BOT_CMDS", "fleet_roles"):
        if n == "RACE" and not hasattr(S, "RACE"):
            continue
        assert getattr(L, n) is getattr(S, n), n
    assert L.Phone is app.Phone and L.Phone.pp is S
    try:
        L.no_such_name_here
        ok = False
    except AttributeError:
        ok = True
    assert ok


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
    print("test_launcher: %d passed, %d failed" % (len(tests) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
