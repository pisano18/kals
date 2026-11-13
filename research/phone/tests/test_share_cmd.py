"""test_share_cmd.py -- /share and /share_today /share_days /share_funds /share_bots (v-tg-share, 2026-11-12): the words,
the picture after each, /help's line. The pictures themselves: phone/charts/tests/test_share.py.

Run:  C:\\Python314\\python.exe research\\phone\\tests\\test_share_cmd.py   (exit 0 = every test passed)
"""
import os
import sys
import time
import traceback

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RESEARCH not in sys.path:
    sys.path.insert(0, RESEARCH)
os.environ["KALS_TESTING"] = "1"

from phone import router as R                                        # noqa: E402
from phone.commands import share as S                                # noqa: E402
from phone.context import FakeCtx                                    # noqa: E402

T0 = 1793370120.0


def run(text):
    ctx = FakeCtx(text=text, now=T0)
    cmd = S.COMMANDS[0] if ctx.cmd == "/share" else S.COMMANDS[1]
    return str(cmd.run(ctx))


def test_menu_lists_the_three_tappable():
    r = run("/share")
    for n in ("/share_brag", "/share_today", "/share_yesterday", "/share_days", "/share_funds"):
        assert n in r, (n, r)
    assert r.index("Safe to post") < r.index("/share_brag") < r.index("For you only") < r.index("/share_today"), \
        "only /share_brag is under 'Safe to post'; the real-order pictures are for the operator only"
    assert "screenshot of this chat" in r, r


def test_share_with_a_word_points_at_its_command():
    assert "Tap /share_days" in run("/share days"), run("/share days")
    assert "Tap /share_funds" in run("/share bots"), run("/share bots")
    assert "Tap /share_today" in run("/share /today")
    assert "Tap /share_yesterday" in run("/share yesterday")
    assert "Pictures of the results" in run("/share nonsense")


def test_each_share_command_names_its_picture():
    for n, kind in (("/share_today", "share_today"), ("/share_yesterday", "share_yesterday"),
                    ("/share_days", "share_days"), ("/share_funds", "share_funds"), ("/share_bots", "share_funds"),
                    ("/share_brag", "share_brag")):
        r = run(n)
        if n == "/share_brag":
            assert r.startswith("📸 <b>Postable 60-day timeline picture coming.</b>"), r
        else:
            assert r.startswith("📸 <b>%s picture coming, for you only.</b>" % S.WHAT[n]), r
        assert R.kind_of(n) == kind, (n, R.kind_of(n))
    assert R.kind_of("/share") is None


def test_listed_in_help_and_needs_no_ledger():
    assert S.COMMANDS[0].section == "money" and S.COMMANDS[0].help_line.startswith("/share — ")
    assert S.COMMANDS[1].section is None
    assert not any(c.needs_ledger for c in S.COMMANDS)


def main():
    tests = [(k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed, failed = 0, []
    t0 = time.time()
    R.discover()
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print("  ok   %s" % name, flush=True)
        except Exception:                                       # noqa: BLE001
            failed.append(name)
            print("  FAIL %s\n%s" % (name, traceback.format_exc()), flush=True)
    print("test_share_cmd: %d passed, %d failed (%.1f s)" % (passed, len(failed), time.time() - t0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
