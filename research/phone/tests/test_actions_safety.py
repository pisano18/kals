"""test_actions_safety.py -- the phone writes to the outside world ONLY through phone/actions, each kind of write in ONE
file (a source scan of every research/phone/**.py but the tests, which name the forbidden words to look for them).

v-tg-step12 (2026-10-30, lane R). Until step 12 the phone was GET-only by construction (botdata/tests/test_safety.py
still holds botstats + botdata to that). The operator asked for controls from the phone, so the rule is now:
  - a POST to Kalshi, the two money-moving paths, ordercli and kauth's signing: phone/actions/money.py ONLY; the one
    other "POST" in the phone is /server's AWS Cost Explorer read (commands/server/aws.py: AWS, never Kalshi);
  - Win32_Process.Create (WMI) and subprocess in phone/actions: phone/actions/launch.py ONLY;
  - a bot's stop file: phone/actions/stopfiles.py ONLY (imported by the /pause /resume module alone);
  - money.py names exactly two write paths and refuses every other one at run time (test_move.py runs that);
  - no Kalshi order, cancel or amend path anywhere in the phone.
Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_actions_safety.py
"""
import os
import re
import sys
import time
import traceback

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PHONE = os.path.join(RESEARCH, "phone")

MONEY = "actions/money.py"
LAUNCH = "actions/launch.py"
STOPFILES = "actions/stopfiles.py"
AWS = "commands/server/aws.py"


def sources():
    """{'commands/botctl.py': text} for every .py under research/phone except the tests."""
    out = {}
    for root, dirs, files in os.walk(PHONE):
        rel = os.path.relpath(root, PHONE).replace(os.sep, "/")
        if "tests" in rel.split("/"):
            continue
        for f in files:
            if f.endswith(".py"):
                k = (f if rel == "." else rel + "/" + f)
                with open(os.path.join(root, f), encoding="utf-8") as fh:
                    out[k] = fh.read()
    return out


def users(pattern, src=None):
    rx = re.compile(pattern)
    return sorted(k for k, v in (src or sources()).items() if rx.search(v))


# the forbidden words, assembled from pieces so this file does not find itself
POST = r"""["']""" + "PO" + r"""ST["']"""
WRITE_PATHS = ("intra_exchange_instance_" + "transfer", r"subaccounts/" + r"transfer(?!s)")
ORDER_PATHS = (r"portfolio/" + r"orders\b", r"events/" + r"orders", r"/" + r"amend", r"batched")


def test_post_only_in_money_and_aws():
    assert set(users(POST)) <= {MONEY, AWS}, users(POST)


def test_money_moving_paths_only_in_money():
    for p in WRITE_PATHS:
        assert set(users(p)) <= {MONEY}, (p, users(p))
    assert set(users(r"\bordercli\b")) <= {MONEY}, users(r"\bordercli\b")
    assert set(users(r"\bkauth\.(headers|_PK|KEY_ID)\b")) <= {MONEY}, "only money.py signs with kauth's key"


def test_no_order_paths_anywhere():
    for p in ORDER_PATHS:
        assert users(p) == [], (p, users(p))
    # the AWS module's token PUT goes to the instance's own metadata service (169.254.169.254), never Kalshi
    assert set(users(r"\b(DEL" + r"ETE|PA" + r"TCH|PU" + r"T)\b")) <= {AWS}


def test_aws_post_is_aws_only():
    src = sources()[AWS]
    assert "kauth" not in src and "kalshi" not in src.lower().replace("kalshi_ping", ""), \
        "the /server AWS module never talks to Kalshi"


def test_process_start_only_in_launch():
    assert set(users(r"Win32_" + r"Process|Invoke-" + r"CimMethod|Create" + r"Process")) <= {LAUNCH}
    act = {k: v for k, v in sources().items() if k.startswith("actions/")}
    assert set(users(r"\bsubprocess\b", act)) <= {LAUNCH}, users(r"\bsubprocess\b", act)
    assert users(r"os\." + r"kill|\." + r"terminate\(|Stop-" + r"Process|task" + r"kill") == []


def test_stop_files_only_in_stopfiles():
    assert set(users(r"phone\.actions\.stopfiles|from phone\.actions import stopfiles|actions import .*\bstopfiles\b")) \
        <= {"commands/botctl.py"}
    # a stop file name written anywhere else: an open(..., "w") on a *.stop path
    assert set(users(r"""\.stop["'][^\n]*["']w["']""")) <= {STOPFILES}


def test_actions_package_only_imported_by_the_controls():
    allowed = {"commands/botctl.py", "commands/approve.py", "commands/move.py", "commands/controls.py"}
    u = [k for k in users(r"\bphone\.actions\b|from phone import actions") if not k.startswith("actions/")]
    assert set(u) <= allowed, u
    assert set(users(r"phone\.actions\.money|actions import .*\bmoney\b")) <= {"commands/move.py"}


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
    print("test_actions_safety: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
