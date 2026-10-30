"""/update -- load the newest phone code: self-test the files on disk, then exit so boot_all starts the new code. Also the
update-flag tick (results\\pinphone.update). The ONLY module of the phone that starts a process.

v-tg-rebuild step 9 (2026-10-30): Phone.text_update and Phone.update_flag_tick as a module, byte-identical (golden shadow
for /update; research/golden/shadow_more.py for the update-flag tick).

THE GATE IS A CONTRACT (DESIGN risk 2): the process that RUNS this gate is the OLD code, testing the NEW files. So the
gate never changes: exactly [sys.executable, "-u", <research>\\pinphone.py, "--selftest"], then the same for
botstats.py, cwd = the repo root, 900 s each, capture_output, utf-8 with errors=replace; any non-zero exit keeps the old
code. Only when both pass does it set `_exit_now` (ctx.state: the Phone until step 11); the poll loop then confirms the
handled messages to Telegram and exits; boot_all.ps1 (every 10 min) starts the phone on the new code.
"""
import os
import subprocess
import sys
import threading
import traceback

from botdata import paths as _paths
from phone.command import Command, declare
from phone.html import Html, esc, i_
from phone.log import log

RESEARCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # == pinphone.HERE
GATE_TIMEOUT_S = 900                            # each self-test's limit (the old process runs them: never change)


def start_update(ctx):
    """Phone.text_update, verbatim: the reply now; the self-tests on a daemon thread that says how it went."""
    st = ctx.state
    if getattr(st, "_updating", False):
        return Html("🔄 An update check is already running.")
    st._updating = True
    chat = ctx.chat_id                              # Phone.text_update: self.chat_id (the paired chat that sent it)

    def work():
        try:
            bad = []
            for f in (os.path.join(RESEARCH, "pinphone.py"), os.path.join(RESEARCH, "botstats.py")):
                r = subprocess.run([sys.executable, "-u", f, "--selftest"], cwd=os.path.dirname(RESEARCH),
                                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=GATE_TIMEOUT_S)
                if r.returncode != 0:
                    bad.append("%s (exit %s)" % (os.path.basename(f), r.returncode))
            if bad:
                ctx.say(Html("⚠️ <b>Update NOT applied</b>: the new code failed its self-test: %s. The phone keeps "
                             "running the old code." % esc(", ".join(bad))), chat_id=chat)
                return
            ctx.say(Html("✅ <b>New code passed its self-test.</b> Restarting the phone link now; it is back on "
                         "the new code within ~10 minutes (boot_all) and says hello."), chat_id=chat)
            st._exit_now = True                       # the poll loop confirms the offset, then exits
        except Exception as e:                       # noqa: BLE001
            log(traceback.format_exc())
            ctx.say("Update check failed: %s" % str(e)[:200], chat_id=chat)
        finally:
            st._updating = False
    threading.Thread(target=work, daemon=True).start()
    return Html("🔄 <b>Checking the newest phone code</b> (self-test, a few minutes)…")


def flag_tick(ctx, start=None):
    """Phone.update_flag_tick, verbatim: results\\pinphone.update (ctx.pp.UPDATE_FLAG, read at call time: the tests and
    the golden harness patch it) runs /update exactly as the command does. The file is removed before anything runs, so
    it fires once. The reply said, or None when there is no flag (or no paired chat). `start` = start_update (a test
    may plant its own, as the old self-test planted Phone.text_update)."""
    flag = ctx.pp.UPDATE_FLAG
    if ctx.chat_id is None or not os.path.exists(flag):
        return None
    try:
        _paths.check_write(flag)                    # v-tg-rebuild step 2: never the live flag under KALS_TESTING=1
        os.remove(flag)
    except OSError:
        return None
    log("update flag %s found: running /update" % flag)
    r = Html(str((start or start_update)(ctx)) + "\n" + i_("asked for by the update flag file, not a message"))
    ctx.say(r)
    return r


COMMAND = declare(Command(
    names=("/update",), section="controls", order=50,
    help_line="/update — load the newest phone code (self-tests it first; back within ~10 min)",
    chart=None, handle=start_update, runs_in_worker=True))
